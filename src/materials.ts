/* 世界层的材质（晶体另在 crystal.ts）。
   每种材质都写两张图：颜色（线性）与数据（八面体编码法线 xy、视深 z、物体编号 w），
   后面的像素化 pass 用数据图描边。
   · 像素哑光：三平面投影的世界空间纹素格，固定每米 TEXEL 格——全场纹素密度一致，像素才「连成一片」。
     颜色只能取色板编号；阴影按纹素中心取样，影子边缘也落在同一套纹素格上。
   · 纸片：平面手绘精灵，Nearest 采样，同样每米 TEXEL 像素；背面是空白的纸。
   · 天空：在 skybox.ts，按主题换。
   每种可投影的材质都带一个只写深度的影子版本（shadowVariant）。 */
import * as THREE from 'three';
import { PALETTE } from './palette';

export const TEXEL = 16;
export const MAX_GLOWS = 4;

const lin = (hex: string) => new THREE.Color(hex);
/** 色板编号 → 线性色 */
export const pal = (i: number) => lin(PALETTE[THREE.MathUtils.clamp(Math.round(i), 0, PALETTE.length - 1)]);

/** 所有世界材质共享的光照、雾与影子；各材质的 uniforms 直接引用同一批对象 */
export const shared = {
  uSun: { value: new THREE.Vector3(-0.5, 0.55, 0.67).normalize() },
  uSunCol: { value: lin('#fff1e8').multiplyScalar(0.78) },
  uSkyCol: { value: lin('#cdd2f0').multiplyScalar(0.58) },
  uGroundCol: { value: lin('#e6cbd2').multiplyScalar(0.42) },
  uFogCol: { value: lin('#ecdde6') },
  uZenith: { value: lin('#b7c0e2') },
  uFogNear: { value: 16 },
  uFogFar: { value: 130 },
  /** 晶体的光：xyz 位置，w 强度（0 ＝ 空位） */
  uGlows: { value: Array.from({ length: MAX_GLOWS }, () => new THREE.Vector4()) },
  uGlowCol: { value: lin('#f6c6e2').multiplyScalar(0.85) },
  tShadow: { value: null as THREE.Texture | null },
  uShadowMat: { value: new THREE.Matrix4() },
  uShadowOn: { value: 0 },
  uTexel: { value: TEXEL },
};

const COMMON = /* glsl */ `
vec2 octEncode(vec3 n) {
  n /= abs(n.x) + abs(n.y) + abs(n.z);
  return n.z >= 0.0 ? n.xy : (1.0 - abs(n.yx)) * vec2(n.x >= 0.0 ? 1.0 : -1.0, n.y >= 0.0 ? 1.0 : -1.0);
}
float hash13(vec3 p) {
  p = fract(p * 0.1031);
  p += dot(p, p.zyx + 31.32);
  return fract((p.x + p.y) * p.z);
}
`;

export const VERT = /* glsl */ `
out vec3 vWorld;
out vec3 vNormal;
out vec2 vUv;
out float vDepth;
void main() {
  vec4 w = modelMatrix * vec4(position, 1.0);
  vWorld = w.xyz;
  // 物件可以带非等比缩放（Blender 里没应用缩放的物体），法线用逆转置
  vNormal = normalize(transpose(inverse(mat3(modelMatrix))) * normal);
  vUv = uv;
  vec4 v = viewMatrix * w;
  vDepth = -v.z;
  gl_Position = projectionMatrix * v;
}
`;

export const OUTS = /* glsl */ `
layout(location = 0) out vec4 oColor;
layout(location = 1) out vec4 oData;
`;

const LIGHT_UNIFORMS = /* glsl */ `
uniform vec3 uSun, uSunCol, uSkyCol, uGroundCol, uFogCol, uGlowCol;
uniform float uFogNear, uFogFar, uTexel, uShadowOn;
uniform vec4 uGlows[${MAX_GLOWS}];
uniform sampler2D tShadow;
uniform mat4 uShadowMat;
`;

let nextId = 1;
/** 每个物件一个编号；描边只看编号与远近 */
export const newId = () => nextId++;

export interface MatteOpts {
  /** 主色、副色的色板编号 */
  a: number;
  b: number;
  /** 0 颗粒 · 1 一米方砖 · 2 横纹 · 3 竖条 · 4 素面 */
  pattern?: number;
  id?: number;
}

export function matte({ a, b, pattern = 0, id = newId() }: MatteOpts) {
  return new THREE.ShaderMaterial({
    glslVersion: THREE.GLSL3,
    uniforms: {
      ...shared,
      uA: { value: pal(a) },
      uB: { value: pal(b) },
      uPattern: { value: pattern },
      uId: { value: id },
    },
    vertexShader: VERT,
    fragmentShader: /* glsl */ `
precision highp float;
${OUTS}
${LIGHT_UNIFORMS}
uniform vec3 uA, uB;
uniform float uPattern, uId;
in vec3 vWorld; in vec3 vNormal; in vec2 vUv; in float vDepth;
${COMMON}
void main() {
  vec3 n = normalize(vNormal);
  vec3 an = abs(n);
  float T = uTexel;
  vec2 uv = an.x > an.y && an.x > an.z ? vWorld.zy : (an.y > an.z ? vWorld.xz : vWorld.xy);
  vec2 tc = floor(uv * T + 1e-3);
  float axis = an.x > an.y && an.x > an.z ? 1.0 : (an.y > an.z ? 2.0 : 3.0);
  float h = hash13(vec3(tc, axis * sign(dot(n, vec3(1.0)))));

  // 颗粒：只在少数纹素上跳一档，平面保持干净
  vec3 base = uPattern == 4.0 ? uA : mix(uA, uB, step(0.82, h) * 0.55);
  if (uPattern == 1.0) {
    vec2 m = mod(tc, T);
    if (m.x == 0.0 || m.y == 0.0) base = mix(uA, uB, 0.75);
  } else if (uPattern == 2.0) {
    if (mod(floor(vWorld.y * T), 8.0) == 0.0) base = mix(uA, uB, 0.8);
  } else if (uPattern == 3.0) {
    if (mod(tc.x, 6.0) == 0.0) base = mix(uA, uB, 0.7);
  }

  // 纹素中心：受光、影子、晶体光都按它取，边缘落在纹素格上
  vec3 tp = (floor(vWorld * T) + 0.5) / T;

  // 三档受光，不要平滑的明暗
  float ndl = max(dot(n, uSun), 0.0);
  float band = ndl > 0.62 ? 1.0 : (ndl > 0.22 ? 0.6 : 0.22);

  float sh = 0.0;
  if (uShadowOn > 0.5 && ndl > 0.0) {
    vec4 sc = uShadowMat * vec4(tp + n * (0.6 / T), 1.0);
    vec3 s = sc.xyz / sc.w;
    if (all(greaterThan(s, vec3(0.0))) && all(lessThan(s, vec3(1.0)))) {
      sh = texture(tShadow, s.xy).r < s.z - 0.0006 ? 1.0 : 0.0;
    }
  }
  band = mix(band, 0.22, sh * 0.85);

  vec3 amb = mix(uGroundCol, uSkyCol, n.y * 0.5 + 0.5);
  vec3 col = base * (amb + uSunCol * band);

  for (int i = 0; i < ${MAX_GLOWS}; i++) {
    vec4 gl = uGlows[i];
    if (gl.w <= 0.0) continue;
    float gd = length(tp - gl.xyz);
    float g = floor(4.0 / (1.0 + gd * gd * 0.35)) / 4.0;
    col += base * uGlowCol * g * gl.w * (0.6 + 0.4 * max(dot(n, normalize(gl.xyz - tp)), 0.0));
  }

  col = mix(col, uFogCol, smoothstep(uFogNear, uFogFar, vDepth));
  oColor = vec4(col, 1.0);
  oData = vec4(octEncode(n), vDepth, uId);
}
`,
  });
}

/** 纸片：tex 已按每米 TEXEL 像素画好；背面是空白的纸 */
export function paper(tex: THREE.Texture, opts: { back?: number; fog?: boolean; id?: number } = {}) {
  return new THREE.ShaderMaterial({
    glslVersion: THREE.GLSL3,
    side: THREE.DoubleSide,
    uniforms: {
      ...shared,
      tMap: { value: tex },
      uBack: { value: pal(opts.back ?? 6) },
      uUseFog: { value: opts.fog === false ? 0 : 1 },
      uId: { value: opts.id ?? newId() },
    },
    vertexShader: VERT,
    fragmentShader: /* glsl */ `
precision highp float;
${OUTS}
${LIGHT_UNIFORMS}
uniform sampler2D tMap;
uniform vec3 uBack;
uniform float uUseFog, uId;
in vec3 vWorld; in vec3 vNormal; in vec2 vUv; in float vDepth;
${COMMON}
void main() {
  vec4 t = texture(tMap, vUv);
  if (t.a < 0.5) discard;
  vec3 n = normalize(vNormal) * (gl_FrontFacing ? 1.0 : -1.0);
  vec3 col = gl_FrontFacing ? t.rgb : uBack;
  // 纸不吃明暗，只在背光时轻一点
  col *= 0.9 + 0.1 * step(0.0, dot(n, uSun));
  if (uUseFog > 0.5) col = mix(col, uFogCol, smoothstep(uFogNear, uFogFar, vDepth));
  oColor = vec4(col, 1.0);
  oData = vec4(octEncode(n), vDepth, uId);
}
`,
  });
}

export interface AssetOpts {
  /** 模型自带的底色贴图（没有就用纯色） */
  map: THREE.Texture | null;
  color: THREE.Color;
  /** 透明度挖空（叶子之类）；同时双面 */
  cutout: boolean;
  /** 0..1：把贴图的明暗映射到色板两色（暗 b → 亮 a）的程度，0 ＝ 保留原色 */
  tint: number;
  a: number;
  b: number;
  /** 0 三档受光（与像素哑光一致）· 1 平滑受光 */
  smooth: number;
  id?: number;
}

const WHITE = new THREE.DataTexture(new Uint8Array([255, 255, 255, 255]), 1, 1);
WHITE.needsUpdate = true;

/** 现成的模型（贴图、颜色都是它自己的）：受光、影子、雾、晶体光与像素哑光同一套；
    像素化、落色板、描边都交给管线——这就是「风格化滤镜」 */
export function asset(o: AssetOpts) {
  return new THREE.ShaderMaterial({
    glslVersion: THREE.GLSL3,
    side: o.cutout ? THREE.DoubleSide : THREE.FrontSide,
    uniforms: {
      ...shared,
      tMap: { value: o.map ?? WHITE },
      uColor: { value: o.color },
      uCut: { value: o.cutout ? 1 : 0 },
      uTint: { value: o.tint },
      uA: { value: pal(o.a) },
      uB: { value: pal(o.b) },
      uSmooth: { value: o.smooth },
      uId: { value: o.id ?? newId() },
    },
    vertexShader: VERT,
    fragmentShader: /* glsl */ `
precision highp float;
${OUTS}
${LIGHT_UNIFORMS}
uniform sampler2D tMap;
uniform vec3 uColor, uA, uB;
uniform float uCut, uTint, uSmooth, uId;
in vec3 vWorld; in vec3 vNormal; in vec2 vUv; in float vDepth;
${COMMON}
void main() {
  vec4 t = texture(tMap, vUv);
  if (uCut > 0.5 && t.a < 0.5) discard;
  vec3 base = t.rgb * uColor;
  float lum = dot(base, vec3(0.2126, 0.7152, 0.0722));
  base = mix(base, mix(uB, uA, smoothstep(0.02, 0.6, lum)), uTint);

  vec3 n = normalize(vNormal) * (gl_FrontFacing ? 1.0 : -1.0);
  float ndl = max(dot(n, uSun), 0.0);
  float band = uSmooth > 0.5 ? 0.22 + 0.78 * smoothstep(0.0, 0.8, ndl) : (ndl > 0.62 ? 1.0 : (ndl > 0.22 ? 0.6 : 0.22));

  vec3 tp = (floor(vWorld * uTexel) + 0.5) / uTexel;
  if (uShadowOn > 0.5 && ndl > 0.0) {
    vec4 sc = uShadowMat * vec4(tp + n * (0.6 / uTexel), 1.0);
    vec3 s = sc.xyz / sc.w;
    if (all(greaterThan(s, vec3(0.0))) && all(lessThan(s, vec3(1.0))) && texture(tShadow, s.xy).r < s.z - 0.0006)
      band = mix(band, 0.22, 0.85);
  }
  vec3 amb = mix(uGroundCol, uSkyCol, n.y * 0.5 + 0.5);
  vec3 col = base * (amb + uSunCol * band);
  for (int i = 0; i < ${MAX_GLOWS}; i++) {
    vec4 gl = uGlows[i];
    if (gl.w <= 0.0) continue;
    float gd = length(tp - gl.xyz);
    float g = floor(4.0 / (1.0 + gd * gd * 0.35)) / 4.0;
    col += base * uGlowCol * g * gl.w * (0.6 + 0.4 * max(dot(n, normalize(gl.xyz - tp)), 0.0));
  }
  col = mix(col, uFogCol, smoothstep(uFogNear, uFogFar, vDepth));
  oColor = vec4(col, 1.0);
  oData = vec4(octEncode(n), vDepth, uId);
}
`,
  });
}

/** 影子版本：只写深度；纸片按贴图透明度挖空 */
export function shadowVariant(mat: THREE.ShaderMaterial) {
  const tMap = mat.uniforms.tMap;
  const m = new THREE.ShaderMaterial({
    glslVersion: THREE.GLSL3,
    side: tMap ? THREE.DoubleSide : THREE.FrontSide,
    colorWrite: false,
    uniforms: tMap ? { tMap } : {},
    vertexShader: /* glsl */ `
out vec2 vUv;
void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: /* glsl */ `
precision highp float;
${tMap ? 'uniform sampler2D tMap;' : ''}
in vec2 vUv;
out vec4 o;
void main() {
  ${tMap ? 'if (texture(tMap, vUv).a < 0.5) discard;' : ''}
  o = vec4(0.0);
}`,
  });
  return m;
}
