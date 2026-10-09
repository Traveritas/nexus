/* 渲染管线：世界 → 解析度场像素化 → 合成 → 晶体
   1. 世界以全分辨率画进 rtWorld（颜色 + 数据两张图，颜色带 mip 链）。
   2. 像素化：屏幕按 8×8 分块，每块从「解析度场」取一个级别 L ∈ {0,1,2,3}，格子边长 2^L。
      一格的颜色直接取 mip 第 L 层对应的那个纹素——正好是这一格里所有像素的平均，
      比点采样稳得多，第一人称转头时不蠕动。格子只取 2 的幂，各级永远对齐在同一套网格上。
      L ≥ 1 时落到 16 色色板（OKLab 最近两色之间按格子坐标做 Bayer 抖动）；L = 0 时保留连续色。
      描边两种（Flags.outline）：1 按格子描，线色取这一格自己的暗档（轮廓暗两档、凹角暗一档、凸棱亮一档），远处淡掉；
      2 填色照旧是格子，线按全分辨率勾——细、带一点抗锯齿，压在像素填色上。
   3. 合成：把像素化结果铺到屏幕，同时按每格的视深写回深度。
   4. 晶体以全分辨率画在最上面，深度与像素世界互相遮挡，折射取的是像素化之后的画面。 */
import * as THREE from 'three';
import { AUTO_RAMP, paletteLab, paletteRgb } from './palette';

export const MAX_FIELD = 8;

export interface FieldSource {
  /** 晶体中心的屏幕像素坐标（原点在左下） */
  x: number;
  y: number;
  /** 晶体在屏幕上的半径（像素） */
  r: number;
}

export interface Field {
  /** 镜头前方的晶体，至多 MAX_FIELD 个 */
  sources: FieldSource[];
  /** 离最近的晶体多近，0..1 */
  prox: number;
  /** 正在进入一个入口：0..1，1 时整屏解析到底并化为白 */
  resolve: number;
  /** 世界之间的转场：0..1，格子一路变粗（至 32px），末段蒙上 veilCol；与 resolve 方向相反 */
  dissolve?: number;
  /** 转场蒙上的颜色（sRGB 0..1），通常是新旧世界的雾色 */
  veilCol?: THREE.Color;
  /** 犯困（翻开日记时）：0..1，格子退到最粗一级，颜色按三色明暗的暗档整体暗一级 */
  drowse?: number;
  /** 暗下来的一圈（罗盘的地图）：屏幕像素，原点在左下；圆里每一格暗两档，边缘按格子抖开。不变粗 */
  dim?: { x: number; y: number; r: number };
  /** 星光（罗盘地图的星落到世界上）：屏幕像素，原点在左下，z 是半径；里圈亮两档、外圈一档，边缘按格子抖开 */
  glow?: THREE.Vector3[];
}

export const MAX_GLOW = 16;

export interface Flags {
  /** 关掉像素化，直接看原始世界 */
  raw: boolean;
  palette: boolean;
  /** 0 不描 · 1 按格子描（自身暗档） · 2 全分辨率细线 */
  outline: number;
  /** 给各级染色，看解析度场 */
  field: boolean;
  /** -1 自动；0..3 锁死一个级别 */
  lock: number;
}

const QUAD_VERT = /* glsl */ `
void main() { gl_Position = vec4(position.xy, 0.0, 1.0); }
`;

const PIX_FRAG = /* glsl */ `
precision highp float;
precision highp int;
uniform sampler2D tColor;
uniform sampler2D tData;
uniform vec2 uRes;
uniform vec3 uCrystals[${MAX_FIELD}];
uniform int uCrystalCount;
uniform float uProx, uResolve;
uniform vec3 uPal[16];
uniform vec3 uPalRgb[16];
uniform float uDark[16];
uniform float uLight[16];
uniform vec3 uDim;
uniform vec3 uGlow[${MAX_GLOW}];
uniform int uGlowCount;
uniform mat3 uView;
uniform float uRaw, uPaletteOn, uOutline, uFieldView, uLock, uDissolve, uDrowse;
out vec4 fragColor;

float bayer4(ivec2 p) {
  int m[16] = int[16](0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5);
  return (float(m[(p.y & 3) * 4 + (p.x & 3)]) + 0.5) / 16.0;
}

vec3 toSrgb(vec3 c) {
  c = max(c, 0.0);
  return mix(c * 12.92, 1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, step(0.0031308, c));
}

vec3 oklab(vec3 c) {
  vec3 lms = vec3(
    0.4122214708 * c.r + 0.5363325363 * c.g + 0.0514459929 * c.b,
    0.2119034982 * c.r + 0.6806995451 * c.g + 0.1073969566 * c.b,
    0.0883024619 * c.r + 0.2817188376 * c.g + 0.6299787005 * c.b);
  lms = pow(max(lms, 0.0), vec3(1.0 / 3.0));
  return vec3(
    0.2104542553 * lms.x + 0.7936177850 * lms.y - 0.0040720468 * lms.z,
    1.9779984951 * lms.x - 2.4285922050 * lms.y + 0.4505937099 * lms.z,
    0.0259040371 * lms.x + 0.7827717662 * lms.y - 0.8086757660 * lms.z);
}

vec3 octDecode(vec2 e) {
  vec3 n = vec3(e, 1.0 - abs(e.x) - abs(e.y));
  float t = max(-n.z, 0.0);
  n.x += n.x >= 0.0 ? -t : t;
  n.y += n.y >= 0.0 ? -t : t;
  return normalize(n);
}

/** 只看源（晶体、物品的焦点）时这一块该是几级：越靠近源越细，0..2 */
float srcLevel(ivec2 px) {
  ivec2 blk = px / 8;
  vec2 bc = vec2(blk * 8) + 4.0;
  float lc = 2.0;
  for (int i = 0; i < ${MAX_FIELD}; i++) {
    if (i >= uCrystalCount) break;
    vec3 c = uCrystals[i];
    float d = length(bc - c.xy) / max(c.z, 6.0);
    lc = min(lc, log2(1.0 + d) + 0.2);
  }
  return lc;
}

int levelAt(ivec2 px) {
  if (uLock >= 0.0) return int(uLock);
  ivec2 blk = px / 8;
  float lc = srcLevel(px);
  lc -= 1.7 * uProx + 3.0 * uResolve;
  lc = clamp(lc, 0.0, 2.0);
  // 级别交界处按块抖开一窄条：不画出一道圆，也不满屏碎块
  return int(clamp(floor(lc + 0.5 + (bayer4(blk) - 0.5) * 0.7), 0.0, 2.0));
}

void main() {
  ivec2 px = ivec2(gl_FragCoord.xy);
  ivec2 hi = ivec2(uRes) - 1;

  if (uRaw > 0.5) {
    vec4 d = texelFetch(tData, px, 0);
    fragColor = vec4(toSrgb(texelFetch(tColor, px, 0).rgb), d.z);
    return;
  }

  int L = levelAt(px);
  // 转场：整屏一路粗到 32px 一格，按块抖开，不是齐刷刷地跳
  if (uDissolve > 0.0) {
    float ld = uDissolve * 5.0 + (bayer4(px / 8) - 0.5) * 0.9;
    L = max(L, int(clamp(floor(ld + 0.5), 0.0, 5.0)));
  }
  // 犯困：格子退粗、颜色暗一档；源（晶体、正看着的物品）附近照旧清醒
  float awake = 0.0;
  if (uDrowse > 0.0) {
    float ls = srcLevel(px);
    awake = 1.0 - clamp(ls - 0.6, 0.0, 1.0);
    float lz = min(uDrowse * 2.4 + (bayer4(px / 8) - 0.5) * 0.9, ls);
    L = max(L, int(clamp(floor(lz + 0.5), 0.0, 2.0)));
  }
  int s = 1 << L;
  ivec2 cell = px >> L;
  ivec2 cpx = min(cell * s + s / 2, hi);

  vec3 col = texelFetch(tColor, cell, L).rgb;
  vec4 dat = texelFetch(tData, cpx, 0);
  float depth = dat.z;
  float id = dat.w;

  vec3 outc;
  int ci = -1;
  bool dimmed = false;
  if (L == 0 || uPaletteOn < 0.5) {
    outc = toSrgb(col);
  } else {
    vec3 lab = oklab(col);
    int i1 = 0, i2 = 1;
    float d1 = 1e9, d2 = 1e9;
    for (int i = 0; i < 16; i++) {
      vec3 e = lab - uPal[i];
      float d = dot(e, e);
      if (d < d1) { d2 = d1; i2 = i1; d1 = d; i1 = i; }
      else if (d < d2) { d2 = d; i2 = i; }
    }
    vec3 a = uPal[i1], b = uPal[i2];
    float t = clamp(dot(lab - a, b - a) / max(dot(b - a, b - a), 1e-6), 0.0, 1.0);
    // 靠近某一色时就是平涂，只在两色之间的那一段才抖
    t = clamp((t - 0.3) / 0.2, 0.0, 1.0) * 0.5;
    ci = t > bayer4(cell) ? i2 : i1;
    // 犯困：每一格按三色明暗的暗档往下走一级；过渡时按格子抖开，走完就是整片暗一档，没有网点
    if (uDrowse > 0.0 && bayer4(cell + ivec2(2, 1)) < uDrowse * (1.0 - awake)) ci = int(uDark[ci]);
    if (uDim.z > 0.0) {
      float dd = length(vec2(cell * s + s / 2) - uDim.xy) - uDim.z;
      dimmed = dd + (bayer4(cell + ivec2(3, 0)) - 0.5) * 24.0 < 0.0;
    }
    // 星光：星本身是连续的光（画在 #glow 上），落到世界上是一格一格亮回来的——
    // 外圈撤回一档暗、里圈两档（回到原色）；圈的边缘按格子抖开
    int up = 0;
    for (int i = 0; i < ${MAX_GLOW}; i++) {
      if (i >= uGlowCount) break;
      vec3 g = uGlow[i];
      float dd = length(vec2(cell * s + s / 2) - g.xy) / g.z + (bayer4(cell + ivec2(1, 2)) - 0.5) * 0.35;
      up = max(up, dd < 0.5 ? 2 : dd < 1.0 ? 1 : 0);
    }
    // 入夜：暗两档
    int down = dimmed ? 2 - up : -up;
    for (int i = 0; i < 2; i++) if (i < down) ci = int(uDark[ci]);
    if (down < 0) ci = int(uLight[ci]);
    outc = uPalRgb[ci];
  }

  if (uOutline > 0.5 && uOutline < 1.5) {
    vec3 n = octDecode(dat.xy);
    float edge = 0.0, crease = 0.0, ridge = 0.0;
    vec3 nv = uView * n;
    ivec2 offs[4] = ivec2[4](ivec2(1, 0), ivec2(-1, 0), ivec2(0, 1), ivec2(0, -1));
    vec4 nb[4];
    for (int k = 0; k < 4; k++) nb[k] = texelFetch(tData, clamp(cpx + offs[k] * s, ivec2(0), hi), 0);
    float inv0 = 1.0 / depth;
    for (int k = 0; k < 4; k++) {
      vec4 nd = nb[k];
      if (abs(nd.w - id) > 0.5) {
        // 不同物件：线画在靠前的那一边
        if (nd.z > depth * 1.01) edge = 1.0;
      } else if (id > 0.5 && (k == 0 || k == 2)) {
        // 同一物件：平面上 1/深度 沿屏幕是线性的，看二阶差分——掠射的地面不会被误描
        vec4 nd2 = nb[k + 1];
        float lap = 1.0 / nd.z + 1.0 / nd2.z - 2.0 * inv0;
        if (abs(lap) > 0.08 * inv0 && max(nd.z, nd2.z) > depth * 1.02) edge = 1.0;
        else if (dot(octDecode(nd.xy), n) < 0.6) {
          // 折痕分凸凹：往右（上）走法线也往右（上）转＝凸棱，亮一档；凹角暗一档
          vec3 dn = uView * octDecode(nd.xy) - nv;
          if ((k == 0 ? dn.x : dn.y) > 0.0) ridge = 1.0;
          else crease = 1.0;
        }
      }
    }
    // 线色取这一格自己的暗档（sel-out）：粉的东西描深玫瑰，白的描雾蓝。
    // 远处按深度分段少走一档（不抖：细东西抖开会变成虚线）；天上的东西（编号 9000 起）照旧描
    float far = id > 8999.5 ? 0.0 : depth < 70.0 ? 0.0 : depth < 160.0 ? 1.0 : 2.0;
    int st = int(max((edge > 0.5 ? 2.0 : crease > 0.5 ? 1.0 : 0.0) - far, 0.0));
    // 暗下去的地方不描亮棱：让给星光
    bool lit = edge < 0.5 && crease < 0.5 && ridge > 0.5 && far < 1.0 && !dimmed;
    if (ci >= 0) {
      for (int i = 0; i < 2; i++) if (i < st) ci = int(uDark[ci]);
      if (lit) ci = int(uLight[ci]);
      outc = uPalRgb[ci];
    } else {
      outc *= mix(vec3(1.0), vec3(0.5, 0.48, 0.6), float(st) * 0.5);
      if (lit) outc = mix(outc, vec3(1.0), 0.3);
    }
  } else if (uOutline > 1.5) {
    // 全分辨率细线：按屏幕像素看数据图，不看格子，线落在靠前的那一边。
    // 八邻里「后面的另一物件」占几分就盖几分：直边一整像素，台阶的角只盖一点，像抗锯齿；近处再往外加一圈淡的
    vec4 d0 = texelFetch(tData, px, 0);
    float z0 = d0.z, id0 = d0.w;
    vec3 n0 = octDecode(d0.xy);
    float sil = 0.0, cr = 0.0, rd = 0.0;
    ivec2 dirs[8] = ivec2[8](ivec2(1, 0), ivec2(-1, 0), ivec2(0, 1), ivec2(0, -1), ivec2(1, 1), ivec2(-1, -1), ivec2(1, -1), ivec2(-1, 1));
    vec4 q[8];
    for (int k = 0; k < 8; k++) q[k] = texelFetch(tData, clamp(px + dirs[k], ivec2(0), hi), 0);
    for (int k = 0; k < 8; k++) {
      if (abs(q[k].w - id0) > 0.5 && q[k].z > z0 * 1.01) sil += k < 4 ? 1.0 : 0.5;
    }
    if (id0 > 0.5) {
      float inv0 = 1.0 / z0;
      for (int k = 0; k < 4; k += 2) {
        vec4 a = q[k], b = q[k + 1];
        if (abs(a.w - id0) > 0.5 || abs(b.w - id0) > 0.5) continue;
        float lap = 1.0 / a.z + 1.0 / b.z - 2.0 * inv0;
        if (abs(lap) > 0.08 * inv0 && max(a.z, b.z) > z0 * 1.02) sil += 1.0;
        else if (dot(octDecode(a.xy), n0) < 0.6) {
          vec3 dn = uView * octDecode(a.xy) - uView * n0;
          if ((k == 0 ? dn.x : dn.y) > 0.0) rd = 1.0;
          else cr = 1.0;
        }
      }
    }
    float wide = 1.0 - smoothstep(2.5, 8.0, z0);
    if (wide > 0.0) {
      for (int k = 0; k < 4; k++) {
        vec4 a = texelFetch(tData, clamp(px + dirs[k] * 2, ivec2(0), hi), 0);
        if (abs(a.w - id0) > 0.5 && a.z > z0 * 1.01) sil += 0.6 * wide;
      }
    }
    // 远处的线淡下去；天上的东西照旧描
    float f = 1.0 - (id0 > 8999.5 ? 0.0 : clamp((z0 - 30.0) / 120.0, 0.0, 1.0));
    float cov = clamp(sil / 2.0, 0.0, 1.0) * f;
    vec3 dark = ci >= 0 ? uPalRgb[int(uDark[int(uDark[ci])])] : outc * vec3(0.5, 0.48, 0.6);
    vec3 dim = ci >= 0 ? uPalRgb[int(uDark[ci])] : outc * vec3(0.75, 0.74, 0.8);
    vec3 light = ci >= 0 ? uPalRgb[int(uLight[ci])] : mix(outc, vec3(1.0), 0.3);
    outc = mix(outc, dim, cr * 0.6 * f * (1.0 - cov));
    outc = mix(outc, light, rd * (dimmed ? 0.0 : 0.45) * f * (1.0 - cov));
    outc = mix(outc, dark, cov * 0.92);
  }

  if (uFieldView > 0.5) {
    vec3 tint[4] = vec3[4](vec3(1.0, 1.0, 1.0), vec3(0.6, 0.85, 1.0), vec3(1.0, 0.75, 0.85), vec3(0.75, 0.7, 0.95));
    outc *= tint[L];
  }


  fragColor = vec4(outc, depth);
}
`;

const COMP_FRAG = /* glsl */ `
precision highp float;
uniform sampler2D tPix;
uniform float uNear, uFar, uVeil;
uniform vec3 uVeilCol;
out vec4 fragColor;
void main() {
  vec4 c = texelFetch(tPix, ivec2(gl_FragCoord.xy), 0);
  fragColor = vec4(mix(c.rgb, uVeilCol, uVeil), 1.0);
  float d = c.a;
  float ndc = (uFar + uNear) / (uFar - uNear) - 2.0 * uFar * uNear / ((uFar - uNear) * max(d, uNear));
  gl_FragDepth = d >= 999.0 ? 1.0 : clamp(ndc * 0.5 + 0.5, 0.0, 1.0);
}
`;

export class Pipeline {
  readonly flags: Flags = { raw: false, palette: true, outline: 0, field: false, lock: -1 };
  rtWorld!: THREE.WebGLRenderTarget;
  rtPix!: THREE.WebGLRenderTarget;
  private quadScene = new THREE.Scene();
  private quadCam = new THREE.Camera();
  private quad: THREE.Mesh;
  private pixMat: THREE.ShaderMaterial;
  private compMat: THREE.ShaderMaterial;
  private veilMat: THREE.ShaderMaterial;
  private w = 0;
  private h = 0;

  constructor(private renderer: THREE.WebGLRenderer) {
    this.pixMat = new THREE.ShaderMaterial({
      glslVersion: THREE.GLSL3,
      depthTest: false,
      depthWrite: false,
      uniforms: {
        tColor: { value: null },
        tData: { value: null },
        uRes: { value: new THREE.Vector2() },
        uCrystals: { value: Array.from({ length: MAX_FIELD }, () => new THREE.Vector3()) },
        uCrystalCount: { value: 0 },
        uProx: { value: 0 },
        uResolve: { value: 0 },
        uPal: { value: paletteLab },
        uPalRgb: { value: paletteRgb },
        uView: { value: new THREE.Matrix3() },
        uRaw: { value: 0 },
        uPaletteOn: { value: 1 },
        uOutline: { value: 0 },
        uFieldView: { value: 0 },
        uLock: { value: -1 },
        uDissolve: { value: 0 },
        uDrowse: { value: 0 },
        uDim: { value: new THREE.Vector3() },
        uGlow: { value: Array.from({ length: MAX_GLOW }, () => new THREE.Vector3()) },
        uGlowCount: { value: 0 },
        uDark: { value: AUTO_RAMP.map((r) => r[0]) },
        uLight: { value: AUTO_RAMP.map((r) => r[2]) },
      },
      vertexShader: QUAD_VERT,
      fragmentShader: PIX_FRAG,
    });
    this.compMat = new THREE.ShaderMaterial({
      glslVersion: THREE.GLSL3,
      depthTest: true,
      depthWrite: true,
      depthFunc: THREE.AlwaysDepth,
      uniforms: {
        tPix: { value: null },
        uNear: { value: 0.1 },
        uFar: { value: 400 },
        uVeil: { value: 0 },
        uVeilCol: { value: new THREE.Vector3(0.984, 0.976, 0.969) },
      },
      vertexShader: QUAD_VERT,
      fragmentShader: COMP_FRAG,
    });
    this.veilMat = new THREE.ShaderMaterial({
      glslVersion: THREE.GLSL3,
      depthTest: false,
      depthWrite: false,
      transparent: true,
      uniforms: { uVeil: { value: 0 }, uVeilCol: this.compMat.uniforms.uVeilCol },
      vertexShader: QUAD_VERT,
      fragmentShader: /* glsl */ `
precision highp float;
uniform float uVeil;
uniform vec3 uVeilCol;
out vec4 fragColor;
void main() { fragColor = vec4(uVeilCol, uVeil); }`,
    });
    this.quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), this.pixMat);
    this.quad.frustumCulled = false;
    this.quadScene.add(this.quad);
  }

  /** w、h 须是 8 的倍数：mip 第 3 层的一个纹素正好是 8×8 */
  setSize(w: number, h: number) {
    this.w = w;
    this.h = h;
    this.rtWorld?.dispose();
    this.rtPix?.dispose();
    this.rtWorld = new THREE.WebGLRenderTarget(w, h, {
      count: 2,
      type: THREE.HalfFloatType,
      minFilter: THREE.LinearMipmapLinearFilter,
      magFilter: THREE.NearestFilter,
      generateMipmaps: true,
      depthBuffer: true,
    });
    this.rtPix = new THREE.WebGLRenderTarget(w, h, {
      type: THREE.HalfFloatType,
      minFilter: THREE.NearestFilter,
      magFilter: THREE.NearestFilter,
      depthBuffer: false,
    });
    this.pixMat.uniforms.uRes.value.set(w, h);
  }

  get pixTexture() {
    return this.rtPix.texture;
  }

  /** overlay：手边的东西（拿在手里的、环绕展示的）。世界画完后清掉深度再画进同一张图，所以不会插进墙里；
      之后和世界一起像素化、落色板、描边 */
  render(world: THREE.Scene, crystal: THREE.Scene, camera: THREE.PerspectiveCamera, field: Field, overlay?: THREE.Scene) {
    const r = this.renderer;
    const f = this.flags;
    const u = this.pixMat.uniforms;
    u.tColor.value = this.rtWorld.textures[0];
    u.tData.value = this.rtWorld.textures[1];
    const n = Math.min(field.sources.length, MAX_FIELD);
    for (let i = 0; i < n; i++) {
      const c = field.sources[i];
      u.uCrystals.value[i].set(c.x, c.y, c.r);
    }
    u.uCrystalCount.value = n;
    u.uProx.value = field.prox;
    u.uResolve.value = field.resolve;
    // 最后一段化成白：晶体本身也被盖住；世界转场则蒙上雾色
    const dissolve = field.dissolve ?? 0;
    u.uDissolve.value = dissolve;
    u.uDrowse.value = field.drowse ?? 0;
    const dm = field.dim;
    (u.uDim.value as THREE.Vector3).set(dm?.x ?? 0, dm?.y ?? 0, dm?.r ?? 0);
    const gl = field.glow ?? [];
    const ng = Math.min(gl.length, MAX_GLOW);
    for (let i = 0; i < ng; i++) u.uGlow.value[i].copy(gl[i]);
    u.uGlowCount.value = ng;
    const veilWhite = THREE.MathUtils.smoothstep(field.resolve, 0.55, 1);
    const veilDream = THREE.MathUtils.smoothstep(dissolve, 0.6, 1);
    this.compMat.uniforms.uVeil.value = Math.max(veilWhite, veilDream);
    const vc = this.compMat.uniforms.uVeilCol.value as THREE.Vector3;
    if (veilDream > veilWhite && field.veilCol) vc.set(field.veilCol.r, field.veilCol.g, field.veilCol.b);
    else vc.set(0.984, 0.976, 0.969);
    u.uRaw.value = f.raw ? 1 : 0;
    u.uPaletteOn.value = f.palette ? 1 : 0;
    u.uOutline.value = Number(f.outline);
    u.uFieldView.value = f.field ? 1 : 0;
    u.uLock.value = f.lock;

    r.autoClear = false;
    r.setRenderTarget(this.rtWorld);
    r.clear(true, true, true);
    r.render(world, camera);
    if (overlay && overlay.children.length) {
      r.clearDepth();
      r.render(overlay, camera);
    }
    // 世界画完后 matrixWorldInverse 才是这一帧的；描边判断凸凹要视空间法线
    u.uView.value.setFromMatrix4(camera.matrixWorldInverse);

    this.quad.material = this.pixMat;
    r.setRenderTarget(this.rtPix);
    r.render(this.quadScene, this.quadCam);

    this.quad.material = this.compMat;
    this.compMat.uniforms.tPix.value = this.rtPix.texture;
    this.compMat.uniforms.uNear.value = camera.near;
    this.compMat.uniforms.uFar.value = camera.far;
    r.setRenderTarget(null);
    r.clear(true, true, true);
    r.render(this.quadScene, this.quadCam);
    r.render(crystal, camera);
    if (this.compMat.uniforms.uVeil.value > 0) {
      this.quad.material = this.veilMat;
      this.veilMat.uniforms.uVeil.value = this.compMat.uniforms.uVeil.value;
      r.render(this.quadScene, this.quadCam);
    }
  }

  get size() {
    return { w: this.w, h: this.h };
  }
}
