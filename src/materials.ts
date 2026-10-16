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
/** 同时亮着的灯（uniform 的槽数）；世界里可以更多，每帧取离人最近的这么多盏 */
export const MAX_LAMPS = 8;

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
  /** 影子图外面算不算在影子里：0 亮（默认）· 1 暗（整片在一块看不见的顶底下的世界，atmosphere 的 nx_shadow_out） */
  uShadowOut: { value: 0 },
  /** 半影（米，atmosphere 的 nx_penumbra）：影子边上软的一圈，明暗之间是渐变而不是一刀切；0 ＝ 硬边 */
  uPenumbra: { value: 0 },
  /** 影子图盖着的宽、高（米）：半影按它换算成影子图上的偏移（shadow.ts 的 bind 写） */
  uShadowSpan: { value: new THREE.Vector2(80, 80) },
  /** 影子多暗：x 影子里的受光档，y 往它压多少（天空主题的 shade，默认 0.22、0.85） */
  uShade: { value: new THREE.Vector2(0.22, 0.85) },
  /** 受光按「朝向 · 太阳」÷ 它算（天空主题的 lift，默认 1）：太阳很低时地面也照得亮 */
  uSunLift: { value: 1 },
  uTexel: { value: TEXEL },
  /** 没写三色明暗的哑光按主色自动配一组（palette.ts 的 AUTO_RAMP），与「主色乘光照」按这个比例混：0 关 · 1 全用三色 */
  uAutoRamp: { value: 0.3 },
  /** 秒；会动的材质（传送物的膜）用 */
  uTime: { value: 0 },
  /** 昼夜：0 白天 … 1 夜里（开关拨过去）。夜里 nx_lit 的灯才发光、灯光（uLamps）才亮 */
  uNight: { value: 0 },
  /** 像素哑光上的灯光亮着多少：max(入夜, 世界常亮)。干净低模仍只看 uNight */
  uLampOn: { value: 0 },
  /** 灯光：xyz 位置，w 照到多远（0 ＝ 空位）；颜色已乘强度。不投影 */
  uLamps: { value: Array.from({ length: MAX_LAMPS }, () => new THREE.Vector4()) },
  /** 灯只照这只盒子里的东西（three 坐标，最低角 / 最高角）：灯光不投影，用房间的盒子挡住隔壁。很大 ＝ 不限 */
  uLampLo: { value: Array.from({ length: MAX_LAMPS }, () => new THREE.Vector3(-1e5, -1e5, -1e5)) },
  uLampHi: { value: Array.from({ length: MAX_LAMPS }, () => new THREE.Vector3(1e5, 1e5, 1e5)) },
  uLampCols: { value: Array.from({ length: MAX_LAMPS }, () => new THREE.Color(0, 0, 0)) },
  /** 灯罩：xyz 罩口朝下的方向，w 下口半角的余弦（2 ＝ 封着）；
      下一组 x 上口半角的余弦、y 别处透出多少、z 往上那一束的倍数、w 光圈边上软的那一圈（弧度） */
  uLampAxis: { value: Array.from({ length: MAX_LAMPS }, () => new THREE.Vector4(0, -1, 0, -1)) },
  uLampShade: { value: Array.from({ length: MAX_LAMPS }, () => new THREE.Vector4(2, 1, 1, 0.07)) },
  /** 下口那一束照到罩口方向多远为止（米；被床面之类挡住，灯光不投影时用它代替影子）。很大 ＝ 不挡 */
  uLampReach: { value: Array.from({ length: MAX_LAMPS }, () => 1e4) },
  /** 切面（xyz 法线，w 距离）：dot(法线, 位置) > w 的不画。透过缝画另一个世界时，只留缝前面的那一半（见 seam.ts）；平时 w 很大 ＝ 不切 */
  uCut: { value: new THREE.Vector4(0, 0, 0, 1e9) },
  /** 循环的大地：纹样按这么大的方块首尾相接（米，0 ＝ 不循环）。走过边界被挪回另一边时，脚下的颗粒、色斑不跳 */
  uWrap: { value: 0 },
  /** 水波光斑（atmosphere 的 nx_caustics）：x 强度（0 ＝ 关）、y 水面高（three 的 y）、z 一格网纹多大（米）、w 离水面多深亮线细一半（米）。
      水面以下、照得到太阳的面上一层慢慢流动的亮网纹（沿太阳方向从水面投下来） */
  uCaustic: { value: new THREE.Vector4(0, 0, 3, 12) },
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

/** 切面：放在每种世界材质的 main() 开头 */
const CUT = /* glsl */ `if (dot(uCut.xyz, vWorld) > uCut.w) discard;`;

const LIGHT_UNIFORMS = /* glsl */ `
uniform vec4 uCut;
uniform vec3 uSun, uSunCol, uSkyCol, uGroundCol, uFogCol, uGlowCol;
uniform float uFogNear, uFogFar, uTexel, uShadowOn, uShadowOut, uSunLift, uPenumbra;
uniform vec2 uShade, uShadowSpan;
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
  /** 0 颗粒 · 1 一米方砖 · 2 横纹 · 3 竖条 · 4 素面 · 5 漂（大片的地：几米一块的过渡，沿等高线拉成一道道）· 6 流（水面：几道慢慢漂过的细带，没有颗粒） */
  pattern?: number;
  /** 顶面色的色板编号：朝上的面整片，并沿侧面上沿垂下参差的几格；不给就没有 */
  top?: number;
  /** 物体在世界里的高度范围（最低、最高）；侧面的上下渐变、贴地变暗、顶面垂边都按它 */
  yRange?: [number, number];
  /** 三色明暗：暗、中、亮三个色板编号。给了就由受光档直接查这三色（可以跨色相，暗偏冷、亮偏暖），
      纹样把它往暗处挪半档或一档；主副色不再参与。不给就是主色乘光照 */
  ramp?: [number, number, number];
  /** 自己发亮（0..1）：不受光照，取色板原色（亮着的灯罩、窗缝里漏进来的光） */
  emit?: number;
  /** 只在光里：背着太阳、在影子里的纹素不画 */
  litOnly?: boolean;
  /** 虚像：[最浓, 近, 远]——离人近于「近」米时看不见，远于「远」米时按「最浓」半透（屏幕上按 Bayer 格子筛掉一部分像素，像素化时混成半透） */
  ghost?: [number, number, number];
  id?: number;
}

const lum =(c: THREE.Color) => 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b;
/** 默认天色下「中档」的照度：三色明暗按它归一，默认天色里看到的就是色板原色，换天时跟着明暗与冷暖走 */
const RAMP_REF = lum(shared.uGroundCol.value.clone().lerp(shared.uSkyCol.value, 0.5).add(shared.uSunCol.value.clone().multiplyScalar(0.6)));

/** 像素哑光上的灯光：和干净低模同一套灯罩（下口、上口、透出、reach），另外只照灯自己那只盒子里的东西；
    受光按纹素中心取、按法线分三档，总亮度再落成四档——灯下是一圈圈的光，不是平滑的渐变 */
const LAMP_GLSL = /* glsl */ `
uniform float uLampOn;
uniform vec4 uLamps[${MAX_LAMPS}];
uniform vec3 uLampCols[${MAX_LAMPS}];
uniform vec4 uLampAxis[${MAX_LAMPS}], uLampShade[${MAX_LAMPS}];
uniform float uLampReach[${MAX_LAMPS}];
uniform vec3 uLampLo[${MAX_LAMPS}], uLampHi[${MAX_LAMPS}];
vec3 lampLight(vec3 p, vec3 n) {
  vec3 sum = vec3(0.0);
  for (int i = 0; i < ${MAX_LAMPS}; i++) {
    vec4 L = uLamps[i];
    if (L.w <= 0.0) continue;
    if (any(lessThan(p, uLampLo[i])) || any(greaterThan(p, uLampHi[i]))) continue;
    vec3 dv = L.xyz - p;
    float d = length(dv);
    if (d >= L.w) continue;
    vec3 l = dv / max(d, 1e-4);
    float ndl = dot(n, l);
    if (ndl <= 0.0) continue;
    float win = 1.0 - d * d / (L.w * L.w);
    float att = win * win / (1.0 + 0.6 * d * d);
    vec4 S = uLampShade[i];
    float a = acos(clamp(dot(-l, uLampAxis[i].xyz), -1.0, 1.0));
    float aDown = uLampAxis[i].w > 1.0 ? -1.0 : acos(uLampAxis[i].w);
    float aUp = S.x > 1.0 ? -1.0 : acos(S.x);
    float down = aDown < 0.0 ? 0.0 : smoothstep(-S.w, S.w, aDown - a);
    down *= 1.0 - smoothstep(uLampReach[i], uLampReach[i] + 0.04, dot(-dv, uLampAxis[i].xyz));
    float up = aUp < 0.0 ? 0.0 : S.z * smoothstep(-S.w, S.w, aUp - (3.14159265 - a));
    float shade = max(S.y, max(down, up));
    float band = ndl > 0.55 ? 1.0 : (ndl > 0.2 ? 0.62 : 0.3);
    sum += uLampCols[i] * att * shade * band;
  }
  float I = max(sum.r, max(sum.g, sum.b));
  if (I <= 0.0) return sum;
  float q = min(floor(I * 4.0 + 0.3) / 4.0, 1.5);
  return sum * (q / I);
}
`;

export function matte({ a, b, pattern = 0, top, yRange = [0, 0], ramp, emit = 0, litOnly = false, ghost, id = newId() }: MatteOpts) {
  return new THREE.ShaderMaterial({
    glslVersion: THREE.GLSL3,
    uniforms: {
      ...shared,
      uEmit: { value: emit },
      uLitOnly: { value: litOnly ? 1 : 0 },
      uGhost: { value: new THREE.Vector3(...(ghost ?? [0, 0, 0])) },
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
uniform float uPattern, uHasTop, uHasRamp, uAutoRamp, uRampRef, uId, uEmit, uWrap, uLitOnly, uTime;
uniform vec3 uGhost;
uniform vec4 uCaustic;
uniform vec2 uYRange;
in vec3 vWorld; in vec3 vNormal; in vec2 vUv; in float vDepth;
${COMMON}
${LAMP_GLSL}
void main() {
  ${CUT}
  if (uGhost.x > 0.0) {
    // 虚像：远处半透，走近散掉
    float al = uGhost.x * smoothstep(uGhost.y, uGhost.z, vDepth);
    ivec2 q = ivec2(gl_FragCoord.xy) & 3;
    int bm[16] = int[16](0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5);
    if ((float(bm[q.y * 4 + q.x]) + 0.5) / 16.0 >= al) discard;
  }
  vec3 n = normalize(vNormal);
  vec3 an = abs(n);
  float T = uTexel;
  // 循环的大地：纹样的坐标按方块折回来，四周的几份复制和中间这一份长得一样
  vec3 pw = vWorld;
  if (uWrap > 0.0) pw.xz -= uWrap * floor(pw.xz / uWrap + 0.5);
  vec2 uv = an.x > an.y && an.x > an.z ? pw.zy : (an.y > an.z ? pw.xz : pw.xy);
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
  } else if (uPattern == 5.0) {
    // 漂：大片的地（原野）。几米一块、慢慢过渡的色块，沿等高线拉成一道道；颗粒照旧压在上面。
    // k 是连续的，落色板时主副两色之间抖出过渡，大片的坡不会落成一整片纯色
    vec2 m = pw.xz;
    float warp = vnoise(m / 15.0, face + 47.0) * 5.0;
    float stripe = vnoise(vec2(tp.y * 0.9 + warp, m.x * 0.02 + m.y * 0.015), face + 45.0);
    float blot = vnoise(m / 4.5, face + 41.0) * 0.6 + vnoise(m / 1.6, face + 43.0) * 0.4;
    float drift = smoothstep(0.2, 0.8, stripe * 0.5 + blot * 0.5);
    // 颗粒推得过一档：一整块同色的里面也有成团的另一色
    k = clamp(drift * 0.85 + k * 0.7 - 0.1, 0.0, 1.0);
  } else if (uPattern == 6.0) {
    // 流：水面。不反射，平的主色上几道副色的细带，弯弯的、慢慢漂过去；没有颗粒
    vec2 m = tp.xz;
    float warp = vnoise(m / 11.0 + vec2(uTime * 0.03, -uTime * 0.02), face + 51.0) * 6.0;
    float v = m.x * 0.21 + m.y * 0.08 + warp - uTime * 0.12;
    float gap = 2.6 + 1.4 * vnoise(vec2(floor(v / 3.0), face), 53.0);
    float band = fract(v / gap);
    float thin = vnoise(m / 5.0 - vec2(uTime * 0.05, 0.0), face + 55.0);
    k = band < 0.07 && thin > 0.42 ? 0.8 : 0.0;
    // 远一点的地方再淡淡一层大块的过渡
    k = max(k, smoothstep(0.8, 0.95, vnoise(m / 18.0 + vec2(0.0, uTime * 0.015), face + 57.0)) * 0.3);
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
  float ndl = clamp(dot(n, uSun) / uSunLift, 0.0, 1.0);
  float band = ndl > 0.62 ? 1.0 : (ndl > 0.22 ? 0.6 : 0.22);

  float sh = 0.0;
  // 有半影的世界：影子按这个像素真实的位置取，不落在材质的纹素格上——明暗的过渡在世界里是连续的，
  // 只在最后的屏幕像素化里变成格子（纹素格上取会在斜着的影子边上留下一道道锯齿）
  vec3 sp = uPenumbra > 0.0 ? vWorld + n * 0.04 : tp + n * (0.6 / T);
  vec4 sc = uShadowMat * vec4(sp, 1.0);
  vec3 s = sc.xyz / sc.w;
  // 接收面在影子图里的斜度（屏幕导数要在分支外面取）
  vec3 sdx = dFdx(s), sdy = dFdy(s);
  if (uShadowOn > 0.5 && (ndl > 0.0 || uLitOnly > 0.5)) {
    if (all(greaterThan(s, vec3(0.0))) && all(lessThan(s, vec3(1.0)))) {
      if (uPenumbra > 0.0) {
        // 半影：4 × 4 的规则网格铺满半影的宽度，每一点按影子图的四个纹素双线性地比（不是非黑即白），
        // 几成在影子里是连续变化的，没有一圈圈的台阶
        vec2 ts = vec2(textureSize(tShadow, 0));
        vec2 r = uPenumbra / uShadowSpan;
        // 接收面在影子图里是斜的：取样点挪开多少，比较的深度也跟着这个面挪多少（否则平地上一半的点会被当成挡住）
        float det = sdx.x * sdy.y - sdx.y * sdy.x;
        vec2 dz = abs(det) > 1e-12 ? vec2(sdy.y * sdx.z - sdx.y * sdy.z, sdx.x * sdy.z - sdy.x * sdx.z) / det : vec2(0.0);
        dz = clamp(dz, -4.0, 4.0);
        for (int j = 0; j < 4; j++)
          for (int i = 0; i < 4; i++) {
            vec2 o = (vec2(float(i), float(j)) - 1.5) / 1.5 * r;
            float z = s.z + dot(dz, o) - 0.0006;
            vec2 p = (s.xy + o) * ts - 0.5;
            vec2 f = fract(p);
            vec2 b = (floor(p) + 0.5) / ts;
            vec2 e = 1.0 / ts;
            float s00 = texture(tShadow, b).r < z ? 1.0 : 0.0;
            float s10 = texture(tShadow, b + vec2(e.x, 0.0)).r < z ? 1.0 : 0.0;
            float s01 = texture(tShadow, b + vec2(0.0, e.y)).r < z ? 1.0 : 0.0;
            float s11 = texture(tShadow, b + e).r < z ? 1.0 : 0.0;
            sh += mix(mix(s00, s10, f.x), mix(s01, s11, f.x), f.y);
          }
        sh = smoothstep(0.0, 1.0, sh / 16.0);
      } else {
        sh = texture(tShadow, s.xy).r < s.z - 0.0006 ? 1.0 : 0.0;
      }
    } else {
      sh = uShadowOut;
    }
  }
  // 只在光里的东西：落在影子里的纹素不画（按位置算，背光的那一面照样在）
  if (uLitOnly > 0.5 && sh > 0.5) discard;
  if (ndl <= 0.0) sh = 0.0;
  band = mix(band, uShade.x, sh * uShade.y);

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
    // 影子压得比默认（0.85）更狠的世界，这一项的太阳也跟着压，影子里才暗得下去（光斑：压到底，影子里几乎全黑）
    float sunK = 1.0 - sh * clamp((uShade.y - 0.85) / 0.15, 0.0, 1.0);
    col = mix(col, rc * (amb + uSunCol * 0.6 * sunK) / uRampRef * ground, rampMix);
    base = mix(base, rc, rampMix);
  }

  // 水波光斑：从水面沿太阳方向投下来的两族弯弯的亮线交成网，慢慢流动；只落在照得到太阳的面上，越深线越细
  if (uCaustic.x > 0.0 && ndl > 0.0 && sh < 0.5 && tp.y < uCaustic.y - 0.05 && uEmit <= 0.0) {
    float dep = uCaustic.y - tp.y;
    vec2 q = (tp.xz + uSun.xz / max(uSun.y, 0.2) * dep) / uCaustic.z;
    float t = uTime;
    q += 0.55 * vec2(vnoise(q * 0.45 + vec2(t * 0.07, 0.0), 61.0), vnoise(q * 0.45 - vec2(0.0, t * 0.06), 63.0));
    float la = abs(sin(q.x * 2.2 + t * 0.35 + 1.3 * sin(q.y * 1.6 - t * 0.27)));
    float lb = abs(sin(q.y * 2.0 - t * 0.31 + 1.3 * sin(q.x * 1.4 + t * 0.22)));
    float line = 1.0 - smoothstep(0.0, 0.32, min(la, lb));
    float fade = uCaustic.w / (uCaustic.w + dep);
    // 非亮即暗：亮线是一格格的整块，落色板时整块跳到偏冷的浅色上，不糊成抖点；颜色是水透下来的冷白，不跟着地的颜色
    float c = step(0.45 + 0.4 * (1.0 - fade), line);
    col += vec3(0.62, 0.70, 0.86) * uCaustic.x * c * min(ndl * 1.6, 1.0);
  }

  for (int i = 0; i < ${MAX_GLOWS}; i++) {
    vec4 gl = uGlows[i];
    if (gl.w <= 0.0) continue;
    float gd = length(tp - gl.xyz);
    float g = floor(4.0 / (1.0 + gd * gd * 0.35)) / 4.0;
    col += base * uGlowCol * g * gl.w * (0.6 + 0.4 * max(dot(n, normalize(gl.xyz - tp)), 0.0));
  }

  if (uLampOn > 0.0) col += base * lampLight(tp, n) * uLampOn;
  if (uEmit > 0.0) col = mix(col, base * 1.08, uEmit);

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
  ${CUT}
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
uniform vec4 uCut;
uniform vec2 uSize;
uniform float uTime, uId, uFogNear, uFogFar, uTexel;
in vec3 vWorld; in vec3 vNormal; in vec2 vUv; in float vDepth;
${COMMON}
void main() {
  ${CUT}
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
      uCutout: { value: o.cutout ? 1 : 0 },
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
uniform float uCutout, uTint, uSmooth, uId;
in vec3 vWorld; in vec3 vNormal; in vec2 vUv; in float vDepth;
${COMMON}
void main() {
  ${CUT}
  vec4 t = texture(tMap, vUv);
  if (uCutout > 0.5 && t.a < 0.5) discard;
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

export interface CleanOpts {
  /** 线性色 */
  color: THREE.Color;
  /** 0..1：自己发光（灯罩、亮着的窗），1 ＝ 不吃明暗 */
  emit?: number;
  /** 接不接影子 */
  recv?: boolean;
  fog?: boolean;
  /** 双面（纸、布条） */
  double?: boolean;
  /** 窗里的景：用自己的一套光（下午的太阳），不用这个世界的 */
  view?: boolean;
  /** 灯（灯罩、灯泡）：白天关着，emit 只在夜里起作用 */
  lit?: boolean;
  id?: number;
}

/** 干净低模（现实的世界用）：每个面一个法线（按屏幕导数算，导出的法线怎样都行），平滑受光、柔和的影子（3×3 PCF），
    颜色是任意的线性色，不落色板、不铺纹素格。管线在 clean 世界里不做像素化、落色板与描边 */
export function clean(o: CleanOpts) {
  return new THREE.ShaderMaterial({
    glslVersion: THREE.GLSL3,
    side: o.double ? THREE.DoubleSide : THREE.FrontSide,
    uniforms: {
      ...shared,
      uColor: { value: o.color },
      uEmit: { value: o.emit ?? 0 },
      uRecv: { value: o.recv === false ? 0 : 1 },
      uUseFog: { value: o.fog === false ? 0 : 1 },
      uView: { value: o.view ? 1 : 0 },
      uLit: { value: o.lit ? 1 : 0 },
      uId: { value: o.id ?? newId() },
    },
    vertexShader: VERT,
    fragmentShader: /* glsl */ `
precision highp float;
${OUTS}
${LIGHT_UNIFORMS}
uniform vec3 uColor;
uniform float uEmit, uRecv, uUseFog, uView, uId, uLit, uNight;
uniform vec4 uLamps[${MAX_LAMPS}];
uniform vec3 uLampCols[${MAX_LAMPS}];
uniform vec4 uLampAxis[${MAX_LAMPS}], uLampShade[${MAX_LAMPS}];
uniform float uLampReach[${MAX_LAMPS}];
in vec3 vWorld; in vec3 vNormal; in vec2 vUv; in float vDepth;
${COMMON}
void main() {
  ${CUT}
  // 面法线：低模的每个面一块平的颜色；朝向镜头的那一面
  vec3 n = normalize(cross(dFdx(vWorld), dFdy(vWorld)));
  if (dot(n, cameraPosition - vWorld) < 0.0) n = -n;
  bool view = uView > 0.5;
  // 窗里的景：傍晚的暖光，太阳低低地在西北（与 wake_fragment.py 里画的太阳同一方向：Blender (-0.56, 0.8, 0.2)）
  vec3 sunD = view ? normalize(vec3(-0.56, 0.2, -0.8)) : uSun;
  vec3 sunC = view ? vec3(1.15, 0.86, 0.6) : uSunCol * 1.2;
  vec3 skyC = view ? vec3(0.56, 0.58, 0.78) : uSkyCol;
  vec3 gndC = view ? vec3(0.62, 0.5, 0.42) : uGroundCol;
  float ndl = max(dot(n, sunD), 0.0);
  float sh = 1.0;
  if (!view && uRecv > 0.5 && uShadowOn > 0.5 && ndl > 0.0) {
    // 斜着受光的面往法线方向多推一点（影子图一个纹素约 4cm，推少了会长出一片斜纹）
    vec4 sc = uShadowMat * vec4(vWorld + n * (0.05 + 0.1 * (1.0 - ndl)), 1.0);
    vec3 s = sc.xyz / sc.w;
    if (all(greaterThan(s, vec3(0.0))) && all(lessThan(s, vec3(1.0)))) {
      vec2 sz = vec2(textureSize(tShadow, 0));
      float z = s.z - 0.0003;
      float lit = 0.0;
      // 3×3 个点，每个点在四个纹素之间双线性地比：影子边是软的、没有台阶
      for (int i = -1; i <= 1; i++)
        for (int j = -1; j <= 1; j++) {
          vec2 p = (s.xy + vec2(float(i), float(j)) / sz) * sz - 0.5;
          vec2 f = fract(p);
          vec2 b = (floor(p) + 0.5) / sz;
          float a00 = step(z, texture(tShadow, b).r);
          float a10 = step(z, texture(tShadow, b + vec2(1.0, 0.0) / sz).r);
          float a01 = step(z, texture(tShadow, b + vec2(0.0, 1.0) / sz).r);
          float a11 = step(z, texture(tShadow, b + vec2(1.0, 1.0) / sz).r);
          lit += mix(mix(a00, a10, f.x), mix(a01, a11, f.x), f.y);
        }
      sh = lit / 9.0;
    }
  }
  vec3 amb = mix(gndC, skyC, n.y * 0.5 + 0.5);
  // 夜里的灯光：近似平方反比地暗下去，到 w 米收成 0；不投影。
  // 灯罩把光拢在罩口里：下口一束（光圈），上口一束（S.z 倍），边上软 S.w 弧度；别的方向只透出 S.y
  vec3 lamp = vec3(0.0);
  if (!view && uNight > 0.0)
    for (int i = 0; i < ${MAX_LAMPS}; i++) {
      vec4 L = uLamps[i];
      if (L.w <= 0.0) continue;
      vec3 dv = L.xyz - vWorld;
      float d = length(dv);
      vec3 l = dv / max(d, 1e-4);
      float win = clamp(1.0 - d * d / (L.w * L.w), 0.0, 1.0);
      float att = win * win / (1.0 + d * d);
      vec4 S = uLampShade[i];
      // 按角度比：离罩口的边多少弧度（正 ＝ 在光束里）
      float a = acos(clamp(dot(-l, uLampAxis[i].xyz), -1.0, 1.0));
      float aDown = uLampAxis[i].w > 1.0 ? -1.0 : acos(uLampAxis[i].w);
      float aUp = S.x > 1.0 ? -1.0 : acos(S.x);
      float down = aDown < 0.0 ? 0.0 : smoothstep(-S.w, S.w, aDown - a);
      // 下口那一束照到 reach 米（沿罩口方向）就被挡住，再往下只剩透出来的那一点
      down *= 1.0 - smoothstep(uLampReach[i], uLampReach[i] + 0.04, dot(-dv, uLampAxis[i].xyz));
      float up = aUp < 0.0 ? 0.0 : S.z * smoothstep(-S.w, S.w, aUp - (3.14159265 - a));
      float shade = max(S.y, max(down, up));
      lamp += uLampCols[i] * att * shade * max(dot(n, l), 0.0);
    }
  vec3 col = uColor * (amb + sunC * ndl * sh + lamp * uNight);
  col = mix(col, uColor * 1.1, uEmit * (uLit > 0.5 ? uNight : 1.0));
  if (uUseFog > 0.5) col = mix(col, uFogCol, smoothstep(uFogNear, uFogFar, vDepth));
  oColor = vec4(col, 1.0);
  oData = vec4(octEncode(n), vDepth, uId);
}
`,
  });
}

/** 窗玻璃：什么颜色也不画，只在模板里记一笔——窗里的景（clean 的 view）只画在这一笔里。
    单面朝屋里：从外面看进窗来，看见的是屋里，不是窗外的景 */
export function pane() {
  return new THREE.ShaderMaterial({
    glslVersion: THREE.GLSL3,
    colorWrite: false,
    depthWrite: false,
    stencilWrite: true,
    stencilRef: 1,
    stencilFunc: THREE.AlwaysStencilFunc,
    stencilZPass: THREE.ReplaceStencilOp,
    vertexShader: /* glsl */ `void main() { gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: /* glsl */ `
precision highp float;
${OUTS}
void main() { oColor = vec4(0.0); oData = vec4(0.0); }
`,
  });
}

/** 让一种材质只画在窗玻璃记过的地方 */
export function throughPane(m: THREE.Material) {
  m.stencilWrite = true;
  m.stencilRef = 1;
  m.stencilFunc = THREE.EqualStencilFunc;
  m.stencilFail = THREE.KeepStencilOp;
  m.stencilZFail = THREE.KeepStencilOp;
  m.stencilZPass = THREE.KeepStencilOp;
  return m;
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
