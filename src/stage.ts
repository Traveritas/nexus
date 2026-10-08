/* 舞台：在自己的小场景里用 3D 画 UI 里的实物（日记本、拿在手里的东西），画进 UI 分辨率的离屏图，再按最近邻铺到屏幕上。
   镜头对着 z = focus 那个平面：平面上一个单位正好是一个 UI 像素，所以正对镜头、停稳的东西和 UI 像素一一对应。
   材质只分三档明暗：正对镜头的一面颜色原样不动，侧过去的面按三色明暗的暗档往下走一到两级，永远落在色板上。 */
import * as THREE from 'three';
import { AUTO_RAMP, paletteRgb } from './palette';
import { UI_SCALE } from './ui';

const VERT = /* glsl */ `
uniform float uFlipU;
out vec2 vUv;
out vec3 vN;
void main() {
  vUv = vec2(uFlipU > 0.5 ? 1.0 - uv.x : uv.x, uv.y);
  vN = normalize(normalMatrix * normal);
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`;

const FRAG = /* glsl */ `
precision highp float;
uniform sampler2D uMap;
uniform float uHasMap;
uniform vec3 uColor;
uniform vec3 uPalRgb[16];
uniform float uDark[16];
in vec2 vUv;
in vec3 vN;
out vec4 fragColor;
void main() {
  vec4 c = uHasMap > 0.5 ? texture(uMap, vUv) : vec4(uColor, 1.0);
  if (c.a < 0.5) discard;
  vec3 n = normalize(vN) * (gl_FrontFacing ? 1.0 : -1.0);
  float d = dot(n, normalize(vec3(0.25, 0.35, 0.9)));
  // 先认出是色板里的哪一色，再按三色明暗的暗档往下走 0 / 1 / 2 级。
  // 正对镜头的一面落在最亮那档：颜色原样不动
  int bi = 0;
  float bd = 1e9;
  for (int i = 0; i < 16; i++) {
    vec3 e = c.rgb - uPalRgb[i];
    float dd = dot(e, e);
    if (dd < bd) { bd = dd; bi = i; }
  }
  if (d <= 0.8) bi = int(uDark[bi]);
  if (d <= 0.45) bi = int(uDark[bi]);
  fragColor = vec4(uPalRgb[bi], 1.0);
}`;

const BLIT_FRAG = /* glsl */ `
precision highp float;
uniform sampler2D tStage;
uniform float uScale;
out vec4 fragColor;
void main() {
  vec4 c = texelFetch(tStage, ivec2(gl_FragCoord.xy / uScale), 0);
  if (c.a < 0.5) discard;
  fragColor = vec4(c.rgb, 1.0);
}`;

/** 每一色暗一档是哪一色（三色明暗的暗档） */
const DARK = AUTO_RAMP.map((r) => r[0]);

export function mat(o: { map?: THREE.Texture; flipU?: boolean; side?: THREE.Side } = {}) {
  return new THREE.ShaderMaterial({
    glslVersion: THREE.GLSL3,
    side: o.side ?? THREE.FrontSide,
    uniforms: {
      uMap: { value: o.map ?? null },
      uHasMap: { value: o.map ? 1 : 0 },
      uColor: { value: new THREE.Color(1, 1, 1) },
      uFlipU: { value: o.flipU ? 1 : 0 },
      uPalRgb: { value: paletteRgb },
      uDark: { value: DARK },
    },
    vertexShader: VERT,
    fragmentShader: FRAG,
  });
}

/** 纯色（色板色）。颜色不经过色彩管理：给的是什么字节，着色器里就是什么 */
export function solid(hex: string) {
  const m = mat();
  const n = parseInt(hex.slice(1), 16);
  (m.uniforms.uColor.value as THREE.Color).setRGB((n >> 16) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255, THREE.LinearSRGBColorSpace);
  return m;
}

export function setMap(m: THREE.Mesh, tex: THREE.Texture) {
  const u = (m.material as THREE.ShaderMaterial).uniforms;
  u.uMap.value = tex;
  u.uHasMap.value = 1;
}

export function canvasTex(c: HTMLCanvasElement) {
  const t = new THREE.CanvasTexture(c);
  t.magFilter = t.minFilter = THREE.NearestFilter;
  t.generateMipmaps = false;
  t.colorSpace = THREE.NoColorSpace;
  return t;
}

/** 一块盒子：x0..x1、y 居中、z0..z1；六面分别给材质（+x −x +y −y +z −z） */
export function box(x0: number, x1: number, h: number, z0: number, z1: number, mats: THREE.Material[]) {
  const g = new THREE.BoxGeometry(x1 - x0, h, z1 - z0);
  g.translate((x0 + x1) / 2, 0, (z0 + z1) / 2);
  return new THREE.Mesh(g, mats);
}

export function plane(w: number, h: number, m: THREE.Material, x = 0, z = 0) {
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(w, h), m);
  mesh.position.set(x, 0, z);
  return mesh;
}

export const ease = (t: number) => t * t * t * (t * (t * 6 - 15) + 10);
export const clamp01 = (t: number) => Math.min(1, Math.max(0, t));

export class Stage {
  readonly scene = new THREE.Scene();
  readonly camera = new THREE.PerspectiveCamera(30, 1, 1, 5000);
  private rt = new THREE.WebGLRenderTarget(1, 1, { minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter });
  private blitScene = new THREE.Scene();
  private blitCam = new THREE.Camera();
  w = 1;
  h = 1;

  /** @param focus 与 UI 像素一一对应的那个平面的 z */
  constructor(private focus = 0) {
    const blit = new THREE.Mesh(
      new THREE.PlaneGeometry(2, 2),
      new THREE.ShaderMaterial({
        glslVersion: THREE.GLSL3,
        depthTest: false,
        depthWrite: false,
        uniforms: { tStage: { value: this.rt.texture }, uScale: { value: UI_SCALE } },
        vertexShader: 'void main() { gl_Position = vec4(position.xy, 0.0, 1.0); }',
        fragmentShader: BLIT_FRAG,
      }),
    );
    blit.frustumCulled = false;
    this.blitScene.add(blit);
  }

  setSize(wUi: number, hUi: number) {
    this.w = wUi;
    this.h = hUi;
    this.rt.setSize(wUi, hUi);
    const d = hUi / 2 / Math.tan((15 * Math.PI) / 180);
    this.camera.aspect = wUi / hUi;
    // 远近裁剪面只框住舞台上东西活动的范围：镜头离焦平面几百单位，near 若取 1，深度精度只有约 0.03，
    // 零点几的间隔就会互相闪
    this.camera.near = Math.max(1, d - 300);
    this.camera.far = d + 300;
    this.camera.position.set(0, 0, this.focus + d);
    this.camera.lookAt(0, 0, this.focus);
    this.camera.updateProjectionMatrix();
  }

  /** 画进离屏图，再铺到当前画面上（透明处不盖） */
  render(r: THREE.WebGLRenderer) {
    const col = r.getClearColor(new THREE.Color());
    const alpha = r.getClearAlpha();
    r.setRenderTarget(this.rt);
    r.setClearColor(0x000000, 0);
    r.clear(true, true, true);
    r.render(this.scene, this.camera);
    r.setRenderTarget(null);
    r.setClearColor(col, alpha);
    r.render(this.blitScene, this.blitCam);
  }
}
