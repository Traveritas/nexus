/* 世界层的材质（晶体另在 crystal.ts）。
   每种材质都写两张图：颜色（线性）与数据（八面体编码法线 xy、视深 z、物体编号 w），
   后面的像素化 pass 用数据图描边。
   · 像素哑光：三平面投影的世界空间纹素格，固定每米 TEXEL 格——全场纹素密度一致，像素才「连成一片」。
     颜色只能取色板编号；阴影按纹素中心取样，影子边缘也落在同一套纹素格上。
   · 纸片：平面手绘精灵，Nearest 采样，同样每米 TEXEL 像素；背面是空白的纸。
   · 天空：在 skybox.ts，按主题换。
   · 器物（charm）：会动的小东西用，三档受光直接取三枚色板色，不铺世界纹素格（见下）。
   每种可投影的材质都带一个只写深度的影子版本（shadowVariant）。 */
import * as THREE from 'three';
import { PALETTE, AUTO_RAMP } from './palette';

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
  /** 没写三色明暗的哑光按主色自动配一组（palette.ts 的 AUTO_RAMP），与「主色乘光照」按这个比例混：0 关 · 1 全用三色 */
  uAutoRamp: { value: 0.3 },
  /** 秒；会动的材质（传送物的膜）用 */
  uTime: { value: 0 },
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
// 格点上取哈希、中间平滑插值；s 区分不同的层
float vnoise(vec2 p, float s) {
  vec2 i = floor(p), f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash13(vec3(i, s)), hash13(vec3(i + vec2(1.0, 0.0), s)), f.x),
             mix(hash13(vec3(i + vec2(0.0, 1.0), s)), hash13(vec3(i + 1.0, s)), f.x), f.y);
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
  /** 顶面色的色板编号：朝上的面整片，并沿侧面上沿垂下参差的几格；不给就没有 */
  top?: number;
  /** 物体在世界里的高度范围（最低、最高）；侧面的上下渐变、贴地变暗、顶面垂边都按它 */
  yRange?: [number, number];
  /** 三色明暗：暗、中、亮三个色板编号。给了就由受光档直接查这三色（可以跨色相，暗偏冷、亮偏暖），
      纹样把它往暗处挪半档或一档；主副色不再参与。不给就是主色乘光照 */
  ramp?: [number, number, number];
  id?: number;
}

const lum = (c: THREE.Color) => 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b;
/** 默认天色下「中档」的照度：三色明暗按它归一，默认天色里看到的就是色板原色，换天时跟着明暗与冷暖走 */
const RAMP_REF = lum(shared.uGroundCol.value.clone().lerp(shared.uSkyCol.value, 0.5).add(shared.uSunCol.value.clone().multiplyScalar(0.6)));

export function matte({ a, b, pattern = 0, top, yRange = [0, 0], ramp, id = newId() }: MatteOpts) {
  return new THREE.ShaderMaterial({
    glslVersion: THREE.GLSL3,
    uniforms: {
      ...shared,
      uA: { value: pal(a) },
      uB: { value: pal(b) },
      uPattern: { value: pattern },
      uTop: { value: pal(top ?? 0) },
      uHasTop: { value: top === undefined ? 0 : 1 },
      uYRange: { value: new THREE.Vector2(...yRange) },
      uRamp: { value: (ramp ?? AUTO_RAMP[THREE.MathUtils.clamp(Math.round(a), 0, AUTO_RAMP.length - 1)]).map(pal) },
      uHasRamp: { value: ramp ? 1 : 0 },
      uRampRef: { value: RAMP_REF },
      uId: { value: id },
    },
    vertexShader: VERT,
    fragmentShader: /* glsl */ `
precision highp float;
${OUTS}
${LIGHT_UNIFORMS}
uniform vec3 uA, uB, uTop;
uniform vec3 uRamp[3];
uniform float uPattern, uHasTop, uHasRamp, uAutoRamp, uRampRef, uId;
uniform vec2 uYRange;
in vec3 vWorld; in vec3 vNormal; in vec2 vUv; in float vDepth;
${COMMON}
void main() {
  vec3 n = normalize(vNormal);
  vec3 an = abs(n);
  float T = uTexel;
  vec2 uv = an.x > an.y && an.x > an.z ? vWorld.zy : (an.y > an.z ? vWorld.xz : vWorld.xy);
  vec2 tc = floor(uv * T + 1e-3);
  float axis = an.x > an.y && an.x > an.z ? 1.0 : (an.y > an.z ? 2.0 : 3.0);
  float face = axis * sign(dot(n, vec3(1.0)));
  float h = hash13(vec3(tc, face));
  bool side = an.y < 0.7;

  // 纹素中心：受光、影子、晶体光、渐变都按它取，边缘落在纹素格上
  vec3 tp = (floor(vWorld * T) + 0.5) / T;

  // k：从主色往副色走多少。落色板时管线在最近两色之间抖动，k 的连续变化会变成像素抖动的过渡
  float k = 0.0;
  if (uPattern != 4.0) {
    // 大色斑：约 1.5 米一块。不整片挪颜色——整片的中间色落色板时会一起跳到同一枚上，成一大块平涂；
    // 而是让斑里跳副色的纹素变多（最多约四成），斑仍是一格格的
    float spot = smoothstep(0.45, 0.85, vnoise(tc / 24.0, face + 7.0)) * 0.4;
    // 颗粒成团：低频噪声加一点逐格扰动再取阈值，长成 2–4 格的小团而不是孤立单点
    float clump = vnoise(tc / 3.0, face + 13.0) * 0.8 + h * 0.2;
    k = step(0.72, clump) * 0.55;
    if (hash13(vec3(tc, face + 29.0)) < spot) k = 0.55;
  }
  if (uPattern == 1.0) {
    // 方砖：每块自己一点色偏，少数整块换色
    float th = hash13(vec3(floor(tc / T), face + 3.0));
    k = clamp(k + (th - 0.5) * 0.3, 0.0, 1.0);
    if (th > 0.88) k = max(k, 0.5);
    vec2 m = mod(tc, T);
    if (m.x == 0.0 || m.y == 0.0) k = 0.75;
  } else if (uPattern == 2.0) {
    // 横纹：每条一点色偏；侧面上按不等长断开，像一排排木板
    float row = floor(vWorld.y * T / 8.0);
    float rh = hash13(vec3(row, face, 5.0));
    k = clamp(k + (rh - 0.5) * 0.25, 0.0, 1.0);
    if (mod(floor(vWorld.y * T), 8.0) == 0.0) k = 0.8;
    else if (side && mod(tc.x + floor(rh * 40.0), 20.0 + floor(rh * 12.0)) == 0.0) k = 0.7;
  } else if (uPattern == 3.0) {
    // 竖条：每条一点色偏
    float sh3 = hash13(vec3(floor(tc.x / 6.0), face, 9.0));
    k = clamp(k + (sh3 - 0.5) * 0.3, 0.0, 1.0);
    if (mod(tc.x, 6.0) == 0.0) k = 0.7;
  }

  // 侧面自上而下渐渐偏向副色，越近底越重
  float hgt = uYRange.y - uYRange.x;
  float above = tp.y - uYRange.x;
  if (side && hgt > 0.3) {
    float t = clamp(above / hgt, 0.0, 1.0);
    k = min(k + (1.0 - t) * (1.0 - t) * 0.5, 1.0);
  }
  vec3 base = mix(uA, uB, k);

  // 顶面色：朝上的面整片，侧面上沿垂下 1–4 格参差的边
  bool onTop = false;
  if (uHasTop > 0.5) {
    float below = (uYRange.y - tp.y) * T;
    float drip = floor(1.0 + 2.6 * vnoise(vec2(tc.x / 2.5, face), 17.0) + hash13(vec3(tc.x, face, 19.0)) * 0.9);
    onTop = n.y > 0.7 || (side && below < drip);
    if (onTop) base = uTop;
  }

  // 贴地：侧面最低的几格压暗，物体是放在地上的而不是浮着
  float ground = side && hgt > 0.6 ? (above < 2.0 / T ? 0.72 : (above < 4.0 / T ? 0.86 : 1.0)) : 1.0;

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
  vec3 col = base * (amb + uSunCol * band) * ground;

  // 写了三色的全用三色；自动配的按总强度和旧的混
  float rampMix = uHasRamp > 0.5 ? 1.0 : uAutoRamp;
  if (rampMix > 0.0 && !onTop) {
    // 三色明暗：受光档 → 暗 0 · 中 1 · 亮 2；纹样挪半档或一档——
    // 半档正好落在两枚色板色正中，管线抖成棋盘格，整档就是平涂的相邻一色。
    // 中、亮档往暗处挪；暗档底下没有更暗的了，往亮处挪（否则影子里的地板细节全被压平）
    float idx = band > 0.8 ? 2.0 : (band > 0.4 ? 1.0 : 0.0);
    float st = floor(k * 2.0 + 0.5) * 0.5;
    float pos = idx > 0.5 ? idx - st : st;
    vec3 rc = pos >= 1.0 ? mix(uRamp[1], uRamp[2], pos - 1.0) : mix(uRamp[0], uRamp[1], pos);
    // 色板原色乘「中档照度 ÷ 默认天色的中档照度」：默认天下所见即所选，换天时随之变暗变色
    col = mix(col, rc * (amb + uSunCol * 0.6) / uRampRef * ground, rampMix);
    base = mix(base, rc, rampMix);
  }

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

/** 器物：会动的小东西（物品的装置、拿在手里的、环绕展示的）。三档受光直接取 ramp 的暗、中、亮三色，
    不铺世界空间的纹素格——跟着镜头走、自己转都不会让纹样游动。像素化、落色板、描边照样由管线做。
    glow 0..1：整体往亮处挪（1 ＝ 全亮），捏到底时发光用 */
export function charm(ramp: [number, number, number], id = newId()) {
  return new THREE.ShaderMaterial({
    glslVersion: THREE.GLSL3,
    side: THREE.DoubleSide,
    uniforms: {
      uSun: shared.uSun,
      uRamp: { value: ramp.map(pal) },
      uGlow: { value: 0 },
      uId: { value: id },
    },
    vertexShader: VERT,
    fragmentShader: /* glsl */ `
precision highp float;
${OUTS}
uniform vec3 uSun;
uniform vec3 uRamp[3];
uniform float uGlow, uId;
in vec3 vWorld; in vec3 vNormal; in vec2 vUv; in float vDepth;
${COMMON}
void main() {
  vec3 n = normalize(vNormal) * (gl_FrontFacing ? 1.0 : -1.0);
  float d = dot(n, uSun);
  int k = d > 0.3 ? 2 : d > -0.25 ? 1 : 0;
  k = min(2, k + int(uGlow * 2.0 + 0.5));
  oColor = vec4(uRamp[k], 1.0);
  oData = vec4(octEncode(n), vDepth, uId);
}
`,
  });
}

/** 膜：门洞、窗洞、衣柜里的一层，颜色是要去的那个世界的。远处没有；走近时从洞口中心长出来，参差的边一路铺满洞口，
    里面是慢慢往上流的两色纹和往上飘的亮点。不吃光、不投影、不挡人。
    边是实的（不抖开）：只在边上描一道线，洞口里的颜色变化不勾线 */
export function veil(opts: { a: number; b: number; size: [number, number]; id?: number }) {
  return new THREE.ShaderMaterial({
    glslVersion: THREE.GLSL3,
    side: THREE.DoubleSide,
    uniforms: {
      ...shared,
      uA: { value: pal(opts.a) },
      uB: { value: pal(opts.b) },
      uSize: { value: new THREE.Vector2(...opts.size) },
      uId: { value: opts.id ?? newId() },
    },
    vertexShader: VERT,
    fragmentShader: /* glsl */ `
precision highp float;
${OUTS}
uniform vec3 uA, uB, uFogCol;
uniform vec2 uSize;
uniform float uTime, uId, uFogNear, uFogFar, uTexel;
in vec3 vWorld; in vec3 vNormal; in vec2 vUv; in float vDepth;
${COMMON}
void main() {
  // 离得越近铺得越满：8m 外没有，2m 内满
  float cover = 1.0 - smoothstep(2.0, 8.0, distance(cameraPosition, vWorld));
  if (cover <= 0.0) discard;
  // 按纹素格取样：边和纹都落在每米 TEXEL 格上
  vec2 q = (floor(vUv * uSize * uTexel) + 0.5) / uTexel;
  vec2 e = abs(q / uSize - 0.5) * 2.0;
  float r = pow(pow(e.x, 4.0) + pow(e.y, 4.0), 0.25);
  vec2 c = q - uSize * 0.5;
  float wob = vnoise(vec2(atan(c.y, c.x) * 2.5, uTime * 0.9), 7.0) - 0.5;
  if (r + wob * 0.5 * (1.0 - cover * 0.8) > cover * 1.3) discard;
  // 往上流的两色纹，越往中心越偏主色
  float f = vnoise(vec2(q.x * 1.3, q.y * 0.7 - uTime * 0.45), 1.0) * 0.65 + vnoise(q * 3.1 + vec2(0.0, -uTime * 1.1), 2.0) * 0.35;
  vec3 col = mix(uB, uA, step(0.48 - (1.0 - r) * 0.12, f));
  vec2 sp = floor(vec2(q.x, q.y - uTime * 0.6) * uTexel * 0.5);
  if (hash13(vec3(sp, 5.0)) > 0.985) col = vec3(1.0);
  col = mix(col, uFogCol, smoothstep(uFogNear, uFogFar, vDepth) * 0.6);
  vec3 n = normalize(vNormal) * (gl_FrontFacing ? 1.0 : -1.0);
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
