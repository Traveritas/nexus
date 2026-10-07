/* 天空主题：跟着人走的一只球，按主题换着色器与整场的天光、雾色。
   · 天上的东西都在无穷远（只看方向），像素化、量化、描边照常走管线。
   · 想让天上某一块被描边，就给它写一个非零编号（9000 起）和比 1000 小一点的视深；
     编号不同、视深更近的那一侧才落线。雾色必须等于天在地平线处的颜色，地面才接得上。
   · 主题从场景里的 atmosphere 空物体读（nx_sky），?sky=<名字> 可以覆盖；名字后面可以跟 :种子（如 dye:7），程序化的主题按它生成；调试键 K 轮换。
   主题的意图见 docs/sky.md。 */
import * as THREE from 'three';
import { shared, VERT, OUTS } from './materials';

interface Light {
  /** 雾 ＝ 地平线的天色 */
  fog: string;
  zenith: string;
  /** 天光、地面反光、太阳：色值 × 强度 */
  sky: [string, number];
  ground: [string, number];
  sun: [string, number];
  glow?: [string, number];
  fogNear?: number;
  fogFar?: number;
}

interface Theme {
  /** 中文名，显示在提示里 */
  label: string;
  light: Light;
  /** 定义 void theme(vec3 d, inout vec3 col, inout float id, inout float depth)
      d 是视线方向（three 坐标，y 朝上），col 进来时已是雾色→天顶的底色 */
  glsl: string;
}

const BASE_LIGHT: Light = {
  fog: '#ecdde6',
  zenith: '#b7c0e2',
  sky: ['#cdd2f0', 0.58],
  ground: ['#e6cbd2', 0.42],
  sun: ['#fff1e8', 0.78],
  glow: ['#f6c6e2', 0.85],
  fogNear: 16,
  fogFar: 130,
};

/** 色板色（sRGB 十六进制）→ 着色器里的线性色 vec3(...) */
function lin(hex: string) {
  const c = new THREE.Color(hex);
  return `vec3(${c.r.toFixed(4)}, ${c.g.toFixed(4)}, ${c.b.toFixed(4)})`;
}

const NONE = /* glsl */ `void theme(vec3 d, inout vec3 col, inout float id, inout float depth) {}`;

export const THEMES: Record<string, Theme> = {
  // ── 空白：原来的天色，什么都没有 ──
  blank: { label: '空白', light: BASE_LIGHT, glsl: NONE },

  // ── 巨构 · 天环：以人为圆心、悬在天顶的几道细环；有的分段，留大片空隙，一圈顺转一圈逆转 ──
  halo: {
    label: '天环',
    light: {
      fog: '#e4e5f0',
      zenith: '#b8c2e0',
      sky: ['#c9d3ef', 0.6],
      ground: ['#dfe0ea', 0.4],
      sun: ['#fff6ec', 0.8],
    },
    glsl: /* glsl */ `
// 一道环：环心方向 pole，离环心 th 度、宽 w 度；seg>0 时分成 seg 段、每段只留 fill
void ring(vec3 d, vec3 pole, float th, float w, float seg, float fill, float spd, vec3 c, float k, bool line,
          inout vec3 col, inout float id, inout float depth) {
  float a = degrees(acos(clamp(dot(d, pole), -1.0, 1.0)));
  if (abs(a - th) > w * 0.5) return;
  vec3 u = normalize(cross(pole, vec3(0.0, 0.0, 1.0)));
  vec3 v = cross(pole, u);
  float ph = atan(dot(d, v), dot(d, u)) / 6.2831853 + uTime * spd;
  if (seg > 0.0 && fract(ph * seg) > fill) return;
  col = c;
  if (line) { id = 9000.0 + k; depth = 900.0 - k * 10.0; }
}
void theme(vec3 d, inout vec3 col, inout float id, inout float depth) {
  if (d.y < 0.05) return;
  vec3 up = vec3(0.0, 1.0, 0.0);
  ring(d, up, 8.0, 0.7, 0.0, 1.0, 0.0, vec3(0.95, 0.94, 0.97), 0.0, false, col, id, depth);
  ring(d, normalize(vec3(0.06, 1.0, -0.04)), 19.0, 1.6, 12.0, 0.5, 0.003, vec3(0.93, 0.92, 0.97), 1.0, true, col, id, depth);
  ring(d, up, 31.0, 0.6, 0.0, 1.0, 0.0, vec3(0.88, 0.86, 0.94), 2.0, false, col, id, depth);
  ring(d, normalize(vec3(-0.05, 1.0, 0.07)), 45.0, 2.2, 5.0, 0.28, -0.0015, vec3(0.97, 0.9, 0.9), 3.0, true, col, id, depth);
  ring(d, up, 59.0, 0.6, 72.0, 0.45, 0.001, vec3(0.92, 0.9, 0.96), 4.0, false, col, id, depth);
}`,
  },

  // ── 巨构 · 悬锤：从天顶一个小环垂下十几根细线，各在不同的高度挂一枚锤，极慢地摆 ──
  plumb: {
    label: '悬锤',
    light: {
      fog: '#ebe4e8',
      zenith: '#c9c3dc',
      sky: ['#d6d0e6', 0.56],
      ground: ['#e9dadb', 0.44],
      sun: ['#fff2e6', 0.78],
    },
    glsl: /* glsl */ `
float h1(float x) { return fract(sin(x * 91.7 + 3.1 + uSeed * 17.3) * 43758.5453); }
void theme(vec3 d, inout vec3 col, inout float id, inout float depth) {
  if (d.y < 0.05) return;
  float el = asin(clamp(d.y, -1.0, 1.0));
  float az = atan(d.x, -d.z);
  // 天顶的小环，把所有线收住
  float zen = degrees(acos(clamp(d.y, -1.0, 1.0)));
  if (abs(zen - 2.4) < 0.55) { col = vec3(0.84, 0.82, 0.91); id = 9600.0; depth = 890.0; return; }
  for (int i = 0; i < 13; i++) {
    float fi = float(i);
    float a0 = (fi + h1(fi) * 0.7) / 13.0 * 6.2831853 + 0.05 * sin(uTime * 0.05 + fi);
    float da = atan(sin(az - a0), cos(az - a0));
    float endEl = radians(34.0 + 40.0 * h1(fi + 7.0));
    float x = da * cos(el);
    float s = radians(1.2 + 0.9 * h1(fi + 3.0));
    // 线
    if (el > endEl && el < radians(87.6) && abs(x) < radians(0.55)) {
      col = vec3(0.6, 0.57, 0.72);
      id = 9610.0 + fi; depth = 880.0;
      return;
    }
    // 锤：竖长的菱形，挂在线的末端
    vec2 q = vec2(x, el - (endEl - s * 1.2));
    if (abs(q.x) / 0.62 + abs(q.y) < s * 1.2) {
      col = h1(fi + 5.0) > 0.65 ? vec3(0.83, 0.69, 0.36) : vec3(0.93, 0.91, 0.96);
      if (q.x > 0.0) col *= 0.86;
      id = 9630.0 + fi; depth = 870.0;
      return;
    }
  }
}`,
  },

  // ── 巨构 · 远碑：地平线上一圈比山还高的碑、门、拱，近的一圈深、远的一圈浅；有几块在慢慢挪 ──
  horizon: {
    label: '远碑',
    light: {
      fog: '#efdcd8',
      zenith: '#aeb3d6',
      sky: ['#d6cfe6', 0.56],
      ground: ['#efd2cc', 0.44],
      sun: ['#ffe9d6', 0.82],
    },
    glsl: /* glsl */ `
float hash11(float x) { return fract(sin(x * 127.1) * 43758.5453); }
// 返回这个方向上被哪一层（0 远 / 1 近）挡住；挡住时 shade 是明暗
float shape(float az, float el, float layer, out float shade) {
  shade = 1.0;
  float hit = 0.0;
  float n = layer < 0.5 ? 13.0 : 7.0;
  for (float i = 0.0; i < 13.0; i++) {
    if (i >= n) break;
    float s = hash11(i + layer * 31.0);
    float a0 = (i + s * 0.6) / n * 6.2831853 + (layer > 0.5 ? uTime * 0.004 * (s - 0.5) : 0.0);
    float da = atan(sin(az - a0), cos(az - a0));
    float kind = floor(hash11(i * 3.7 + layer) * 4.0);
    float sc = layer < 0.5 ? 0.6 : 1.0;
    if (kind < 1.0) {
      // 碑：高而窄，顶上斜切
      float w = (0.035 + 0.03 * s) * sc, h = (0.22 + 0.25 * s) * sc;
      if (abs(da) < w && el < h - da * 0.6) { hit = 1.0; shade = da < 0.0 ? 1.0 : 0.82; }
    } else if (kind < 2.0) {
      // 门：两柱一楣，门洞里看得见后面
      float w = 0.11 * sc, h = 0.2 * sc, t = 0.022 * sc;
      bool post = abs(abs(da) - w) < t && el < h;
      bool lint = abs(da) < w + t && el > h - t * 1.3 && el < h + t * 0.6;
      if (post || lint) { hit = 1.0; shade = (da < 0.0) ? 1.0 : 0.85; }
    } else if (kind < 3.0) {
      // 拱：半个圆环立在地平线上
      float r = 0.13 * sc, t = 0.025 * sc;
      float rr = length(vec2(da, el));
      if (abs(rr - r) < t && el > 0.0) { hit = 1.0; shade = 0.75 + 0.25 * (el / r); }
    } else {
      // 悬着的立方：斜放，离地平线一段
      vec2 q = vec2(da, el - 0.16 * sc);
      q = mat2(0.7071, -0.7071, 0.7071, 0.7071) * q;
      float h = 0.05 * sc;
      if (max(abs(q.x), abs(q.y)) < h) { hit = 1.0; shade = q.x > q.y ? 0.8 : 1.0; }
    }
  }
  return hit;
}
void theme(vec3 d, inout vec3 col, inout float id, inout float depth) {
  float el = asin(clamp(d.y, -1.0, 1.0));
  if (el < -0.01 || el > 0.6) return;
  float az = atan(d.x, -d.z);
  float sh;
  // 近的一圈在前
  if (shape(az, el, 1.0, sh) > 0.5) {
    vec3 c = mix(vec3(0.5, 0.47, 0.6), vec3(0.64, 0.6, 0.72), sh);
    col = mix(uFogCol, c, smoothstep(-0.005, 0.06, el) * 0.8);
    id = 9301.0; depth = 880.0;
  } else if (shape(az + 1.3, el, 0.0, sh) > 0.5) {
    vec3 c = mix(vec3(0.72, 0.68, 0.78), vec3(0.8, 0.76, 0.84), sh);
    col = mix(uFogCol, c, smoothstep(-0.005, 0.08, el) * 0.6);
  }
}`,
  },

  // ── 巨构 · 天格：天是一块极高的格栅天花，有些格子嵌着磨砂玻璃，上面还有一层转了 45° 的 ──
  lattice: {
    label: '天格',
    light: {
      fog: '#e6e8f1',
      zenith: '#c6cfe8',
      sky: ['#d5dcf0', 0.6],
      ground: ['#e2e2ea', 0.4],
      sun: ['#fbf6f0', 0.76],
    },
    glsl: /* glsl */ `
float hash21(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
void theme(vec3 d, inout vec3 col, inout float id, inout float depth) {
  if (d.y < 0.02) return;
  float fade = smoothstep(0.1, 0.5, d.y);
  // 下层：方格梁
  vec2 p = d.xz / d.y * 6.0;
  vec2 g = fract(p) - 0.5;
  vec2 cell = floor(p);
  float beam = step(0.44, max(abs(g.x), abs(g.y)));
  float pane = step(0.72, hash21(cell));
  // 上层：转 45°、更稀的一层，透过没有玻璃的格子看得见
  vec2 p2 = mat2(0.7071, -0.7071, 0.7071, 0.7071) * (d.xz / d.y * 3.2) + 0.25;
  vec2 g2 = fract(p2) - 0.5;
  float beam2 = step(0.45, max(abs(g2.x), abs(g2.y)));
  vec3 c = col;
  if (beam2 > 0.5) c = mix(c, vec3(0.74, 0.73, 0.84), 0.6 * fade);
  if (pane > 0.5) c = mix(c, vec3(0.93, 0.95, 0.99), 0.75 * fade);
  if (beam > 0.5) c = mix(c, vec3(0.62, 0.6, 0.74), 0.9 * fade);
  // 有几格的玻璃是暖的
  if (pane > 0.5 && hash21(cell + 7.0) > 0.86) c = mix(c, vec3(0.97, 0.88, 0.78), 0.7 * fade);
  col = c;
}`,
  },

  // ── 染梦 · 扎染：天是一顶扎染过的布篷，从一圈挂点垂下、下摆在挂点之间荡成弧；染底上留着白的防染纹（天顶放射的菊纹、一圈圈扎线、或鹿子点），
  //    白纹往外洇出一圈浅一点的染色、边沿是参差的纤维。布在风里缓缓鼓动，明暗褶子扫过去，纹样跟着起伏 ──
  dye: {
    label: '扎染',
    light: {
      fog: '#ece6ee',
      zenith: '#d6d4e6',
      sky: ['#d2d2ea', 0.54],
      ground: ['#e9dce2', 0.46],
      sun: ['#fff2ea', 0.74],
    },
    glsl: /* glsl */ `
float hj(float x) { return fract(sin(x * 91.345 + uSeed * 47.13) * 43758.5453); }
// 防染：离白纹的距离 dist、白纹半宽 w → 0 染底 … 1 纯白；纤维把边咬得参差
float resist(float dist, float w, float jag) {
  return 1.0 - smoothstep(w * 0.6, w * 2.2, dist + jag * w);
}
void theme(vec3 d, inout vec3 col, inout float id, inout float depth) {
  if (d.y < 0.0) return;
  float t = uTime;
  float az0 = atan(d.x, -d.z);
  // 下摆：N 个挂点之间荡成弧，跟着风轻轻摆；s 是从天顶量下来的距离，1 约在地平线以上十几度
  float N = 6.0 + 2.0 * floor(hj(2.0) * 3.0);
  float sway = 0.18 * sin(t * 0.45 + az0 * 2.0);
  float zen = acos(clamp(d.y, -1.0, 1.0)) / 1.33;
  float hem = 0.9 + 0.11 * abs(sin(az0 * N * 0.5 + sway));
  if (zen > hem) return;
  // 布在风里鼓动：两列波斜着跑过去，纹样随之起伏
  vec2 q = zen * vec2(sin(az0), -cos(az0));
  vec2 k1 = vec2(3.6, 1.4), k2 = vec2(-1.8, 3.1);
  float w1 = dot(q, k1) - t * 0.55, w2 = dot(q, k2) - t * 0.41;
  q += 0.025 * (vec2(sin(w1), cos(w2)) + 0.6 * vec2(cos(w2 * 1.7), sin(w1 * 1.3)));
  float s = length(q);
  float az = atan(q.x, -q.y) + t * 0.008;
  float jag = texture(tNoise, q * 22.0 / 256.0).x - 0.5 + 0.5 * (texture(tNoise, q * 70.0 / 256.0).y - 0.5);
  // 种子定纹样：几道菊纹、拧不拧成螺旋、几圈扎线、有没有鹿子点
  float S = 8.0 + 4.0 * floor(hj(3.0) * 3.0);
  float twist = hj(4.0) < 0.4 ? 0.0 : (hj(5.0) - 0.5) * 5.0;
  float Nr = 3.0 + floor(hj(6.0) * 3.0);
  bool dots = hj(7.0) > 0.3;
  float R = 0.0;
  // 天顶：一团白，边上被扎出放射的锯齿
  R = max(R, resist(s - 0.07 - 0.02 * abs(fract(az * S / 6.2831853) - 0.5), 0.02, jag));
  // 菊纹：从天顶放射出去，布折过的地方走成折线
  float f = fract((az + twist * s) * S / 6.2831853 + 0.08 * abs(fract(s * 7.0) - 0.5)) - 0.5;
  R = max(R, resist(abs(f) * 6.2831853 / S * max(s, 0.15) * 3.0, 0.018 + 0.02 * s, jag) * smoothstep(0.08, 0.2, s));
  // 两者取一：一圈圈的扎线，或一圈圈鹿子点（实心的小白点）
  float g = fract(s * Nr) - 0.5;
  if (!dots) {
    R = max(R, resist(abs(g) / Nr * 3.0, 0.012, jag) * step(0.15, s));
  } else if (s > 0.15) {
    float M = floor(6.2831853 * (floor(s * Nr) + 0.5) / Nr / 0.12);
    vec2 cell = vec2(fract(az / 6.2831853 * M) - 0.5, g);
    float dd = length(cell * vec2(6.2831853 * s / M, 1.0 / Nr)) * 3.0;
    R = max(R, resist(dd, 0.04, jag * 0.5));
  }
  // 染色：三套里挑一套（深染底、洇开的浅色、最浅的一圈），白纹是布本来的白
  int sc = int(hj(8.0) * 3.0);
  vec3 deep = sc == 0 ? ${lin('#8fa3c7')} : (sc == 1 ? ${lin('#a8798c')} : ${lin('#5c5378')});
  vec3 mid = sc == 0 ? ${lin('#c3d1e6')} : (sc == 1 ? ${lin('#d9aab5')} : ${lin('#a8a1bf')});
  vec3 pale = sc == 0 ? ${lin('#ece9f2')} : (sc == 1 ? ${lin('#f3d6d6')} : ${lin('#cdc8db')});
  vec3 white = ${lin('#fbf9f7')};
  // 染得不匀：大片的深浅
  float mott = texture(tNoise, q * 3.0 / 256.0).z;
  vec3 c = mix(deep, mid, 0.25 * smoothstep(0.45, 0.8, mott));
  c = mix(c, mid, smoothstep(0.12, 0.3, R));
  c = mix(c, pale, smoothstep(0.45, 0.58, R));
  c = mix(c, white, smoothstep(0.72, 0.84, R));
  // 褶子：风吹出的明暗扫过去，挂点之间还有往下垂的褶
  float shade = 0.1 * (cos(w1) * 0.8 + cos(w2) * 0.6) + 0.07 * cos(az0 * N + sway * 2.0) * smoothstep(0.3, 1.0, zen);
  c *= 1.0 + shade;
  // 下摆压一道深边，像布的折边
  c = mix(c, deep * 0.8, smoothstep(hem - 0.03, hem - 0.01, zen));
  col = c;
  id = 9500.0; depth = 880.0;
}`,
  },

  // ── 染梦 · 绸：按种子横过 2–4 条染色的绸带；起伏和翻折沿着带子往前跑，翻过来是另一面的颜色，一道光泽顺着滑过去 ──
  silk: {
    label: '绸',
    light: {
      fog: '#eadde6',
      zenith: '#9399c6',
      sky: ['#c9c6e4', 0.56],
      ground: ['#e8cdd6', 0.46],
      sun: ['#ffe8dc', 0.78],
    },
    glsl: /* glsl */ `
float sh(float x) { return fract(sin(x * 78.233 + uSeed * 12.9898) * 43758.5453); }
// 沿方位的频率 k、tw 都取整数：绕一圈首尾接得上。spd 带符号，几条带子往不同的方向飘
void ribbon(float az, float el, float base, float amp, float k, float ph, float w0, float tw, float spd,
            vec3 front, vec3 back, vec3 tint, float idn, inout vec3 col, inout float id, inout float depth) {
  float t = uTime * spd;
  // 起伏沿着带子往前跑，上面再叠一层更碎、跑得更快的
  float ce = base + amp * sin(az * k + ph - t) + amp * 0.3 * sin(az * (k + 2.0) + ph * 1.7 - t * 1.9);
  // 翻折也顺着风游走
  float tph = az * tw + ph * 2.0 - t * 1.4;
  float twist = cos(tph);
  float w = w0 * (0.08 + 0.92 * abs(twist));
  float off = (el - ce) / w;
  if (abs(off) > 1.0) return;
  float face = abs(twist);
  vec3 c = twist > 0.0 ? front : back;
  // 沿长度慢慢染到另一种颜色
  c = mix(c, tint, 0.45 * (0.5 + 0.5 * sin(az * 2.0 + ph * 3.0)));
  // 正对着人的亮，侧过去的暗；绸是弯的，横过带子一边亮一边暗，翻过去时亮暗跟着换边
  c *= 0.84 + 0.16 * face + 0.1 * off * sin(tph);
  // 光泽：一道亮沿着带子滑过，只落在正对着人的地方
  float across = 1.0 - off * off;
  float sheen = pow(max(0.0, cos(az * 3.0 + ph * 5.0 - uTime * spd * 2.2)), 10.0) * face * across * across * across;
  c = mix(c, ${lin('#fbf9f7')}, sheen * 0.55);
  col = c;
  id = idn; depth = 900.0 - (idn - 9400.0) * 15.0;
}
void theme(vec3 d, inout vec3 col, inout float id, inout float depth) {
  float el = asin(clamp(d.y, -1.0, 1.0));
  if (el < 0.0) return;
  float az = atan(d.x, -d.z);
  // 正面、反面、沿长度染过去的颜色，都取色板色
  vec3 fronts[4] = vec3[4](${lin('#d9aab5')}, ${lin('#ead7a0')}, ${lin('#86b5a5')}, ${lin('#c3d1e6')});
  vec3 backs[4] = vec3[4](${lin('#8fa3c7')}, ${lin('#d9aab5')}, ${lin('#cdc8db')}, ${lin('#a8a1bf')});
  vec3 tints[4] = vec3[4](${lin('#ead7a0')}, ${lin('#f3d6d6')}, ${lin('#c3d1e6')}, ${lin('#d9aab5')});
  int n = 2 + int(sh(1.0) * 3.0);
  for (int i = 0; i < 4; i++) {
    if (i >= n) break;
    float fi = float(i);
    // 都压在天顶以下：太高的带子在头顶会收成尖
    float base = 0.1 + 0.55 * sh(fi * 2.3 + 1.0);
    float amp = 0.03 + 0.12 * sh(fi * 3.7 + 2.0);
    float k = 1.0 + floor(sh(fi * 5.1 + 3.0) * 3.0);
    float ph = sh(fi * 7.9 + 4.0) * 6.2831853;
    float w0 = 0.02 + 0.03 * sh(fi * 9.3 + 5.0);
    float tw = 1.0 + floor(sh(fi * 4.4 + 6.0) * 5.0);
    float spd = (0.05 + 0.06 * sh(fi * 8.2 + 8.0)) * (mod(fi, 2.0) < 0.5 ? 1.0 : -1.0);
    int ci = int(sh(fi * 6.6 + 7.0) * 4.0);
    ribbon(az, el, base, amp, k, ph, w0, tw, spd, fronts[ci], backs[ci], tints[ci], 9400.0 + fi, col, id, depth);
  }
}`,
  },

  // ── 晨 · 溶金：看不见日头，只有地平线上一层层越来越薄的金条和一团暖雾，像日头已经化开了 ──
  dawn: {
    label: '溶金',
    light: {
      fog: '#f3dfd2',
      zenith: '#c4bedb',
      sky: ['#dcd2e6', 0.52],
      ground: ['#f2d6c6', 0.48],
      sun: ['#ffe2b8', 0.86],
      glow: ['#f8d2c6', 0.85],
    },
    glsl: /* glsl */ `
void theme(vec3 d, inout vec3 col, inout float id, inout float depth) {
  vec3 s = normalize(vec3(0.55, 0.1, -0.83));
  float el = asin(clamp(d.y, -1.0, 1.0));
  float sel = asin(s.y);
  float a = atan(d.x, -d.z) - atan(s.x, -s.z);
  float daz = atan(sin(a), cos(a));
  // 暖晕：横向拉长
  float g = exp(-pow(daz / 0.55, 2.0) - pow((el - sel) / 0.16, 2.0));
  col = mix(col, vec3(0.95, 0.66, 0.5), g * 0.8);
  // 化开的金条：一条条，越往下越薄、越窄
  float k = (sel - 0.07 - el) / 0.011 + 1.0;
  if (k > 0.0 && k < 9.0) {
    float i = floor(k);
    float thick = 0.62 - i * 0.06;
    float half_ = 0.2 * (1.0 - i / 11.0) + 0.04 * sin(i * 2.3);
    if (fract(k) < thick && abs(daz) < half_) col = i < 4.0 ? vec3(0.83, 0.69, 0.36) : mix(col, vec3(0.83, 0.69, 0.36), 0.8);
  }
  // 上面两三条更淡的
  float k2 = (el - sel - 0.09) / 0.02;
  if (k2 > 0.0 && k2 < 3.0) {
    float i = floor(k2);
    if (fract(k2) < 0.35 && abs(daz) < 0.3 - i * 0.08) col = mix(col, vec3(0.9, 0.76, 0.5), 0.6);
  }
}`,
  },

  // ── 夜 · 星纸：深紫的夜，星是大小不一的圆点，少数带一圈柔光，偶尔一颗菱形或短芒；一条淡淡的星河斜着流过 ──
  night: {
    label: '星纸',
    light: {
      fog: '#5d5677',
      zenith: '#231f36',
      sky: ['#8c8fc4', 0.34],
      ground: ['#6b5a76', 0.22],
      sun: ['#c9d6f5', 0.5],
      glow: ['#f6c6e2', 1.15],
      fogNear: 12,
      fogFar: 110,
    },
    glsl: /* glsl */ `
float hash21(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
void theme(vec3 d, inout vec3 col, inout float id, inout float depth) {
  // 一个屏幕像素在方向空间里的两条边：星的形状按屏幕像素量，任何视角下都是圆的
  vec3 ddx = dFdx(d), ddy = dFdy(d);
  if (d.y < -0.02) return;
  float el = asin(clamp(d.y, -1.0, 1.0));
  float az = atan(d.x, -d.z);
  // 星河：一条斜带，带里亮一点
  vec3 rn = normalize(vec3(0.5, 0.35, -0.8));
  float band = exp(-pow(dot(d, rn) / 0.16, 2.0));
  col = mix(col, vec3(0.42, 0.4, 0.58), band * 0.7 * smoothstep(0.0, 0.3, d.y));
  float fade = smoothstep(0.02, 0.12, d.y);
  mat2 G = mat2(dot(ddx, ddx), dot(ddx, ddy), dot(ddx, ddy), dot(ddy, ddy));
  mat2 Gi = inverse(G);
  // 星：按方位/仰角分格放，每格至多一颗；三层，越细的层越密。格只管放在哪，形状另算
  for (int layer = 0; layer < 3; layer++) {
    float sz = layer == 0 ? 0.09 : (layer == 1 ? 0.05 : 0.032);
    // 按仰角分行，每行按周长分成整数个格：格的位置只取决于格本身
    float row = floor(el / sz);
    float nAz = max(1.0, floor(6.2831853 * cos((row + 0.5) * sz) / sz));
    vec2 cell = vec2(floor((az / 6.2831853 + 0.5) * nAz), row);
    float h = hash21(cell + float(layer) * 17.0);
    float chance = (layer == 0 ? 0.976 : (layer == 1 ? 0.952 : 0.92)) - band * 0.08;
    if (h < chance) continue;
    // 星的方向：格心加一点抖动，换回球面上的方向
    vec2 j = cell + 0.5 + (vec2(hash21(cell + 3.1), hash21(cell + 5.7)) - 0.5) * 0.5;
    float sel = j.y * sz;
    float saz = (j.x / nAz - 0.5) * 6.2831853;
    vec3 sdir = vec3(sin(saz) * cos(sel), sin(sel), -cos(saz) * cos(sel));
    // 星心相对这个像素的屏幕偏移（像素）
    vec2 f = Gi * vec2(dot(sdir - d, ddx), dot(sdir - d, ddy));
    float kind = hash21(cell + 13.3);
    float r = (layer == 0 ? 3.0 : (layer == 1 ? 2.2 : 1.6)) * (0.7 + 0.7 * hash21(cell + 2.2));
    float tone = hash21(cell + 9.0);
    vec3 sc = tone > 0.9 ? vec3(0.9, 0.72, 0.76) : (tone > 0.7 ? vec3(0.92, 0.84, 0.62) : vec3(0.95, 0.94, 0.97));
    float st;
    if (layer == 0 && kind > 0.9) {
      // 菱形
      st = step(abs(f.x) + abs(f.y), r * 1.5);
    } else if (layer == 0 && kind > 0.84) {
      // 短芒：圆点加一道很短的竖芒（屏幕上竖着）
      st = max(step(length(f), r * 0.75), step(abs(f.x), 0.9) * step(abs(f.y), r * 2.4));
    } else {
      st = step(length(f), r);
      // 很少几颗带一圈柔光
      if (layer == 0 && kind < 0.1) col = mix(col, sc, (1.0 - smoothstep(r, r * 3.2, length(f))) * 0.3 * fade);
    }
    col = mix(col, sc, st * fade);
  }
}`,
  },
};

export const SKY_NAMES = Object.keys(THEMES);

function bump(dst: THREE.Color, [hex, k]: [string, number]) {
  dst.set(hex).multiplyScalar(k);
}

const uTime = { value: 0 };
/** 程序化主题的种子：`dye:7` 里的 7；不写时为 1，截图可复现 */
const uSeed = { value: 1 };
const cache = new Map<string, THREE.ShaderMaterial>();

/** 噪声纹理：256² 的随机格，双线性插值后就是可平铺的值噪声；四个通道互不相干。
    按固定的数列生成，每次都一样。比在着色器里逐格算 hash 便宜得多 */
function noiseTexture() {
  const N = 256;
  const data = new Uint8Array(N * N * 4);
  let x = 0x9e3779b9;
  for (let i = 0; i < data.length; i++) {
    x ^= x << 13;
    x ^= x >>> 17;
    x ^= x << 5;
    data[i] = x & 255;
  }
  const t = new THREE.DataTexture(data, N, N);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.magFilter = THREE.LinearFilter;
  t.minFilter = THREE.LinearMipmapLinearFilter;
  t.generateMipmaps = true;
  t.needsUpdate = true;
  return t;
}
const tNoise = { value: noiseTexture() };

function material(name: string) {
  let m = cache.get(name);
  if (m) return m;
  m = new THREE.ShaderMaterial({
    glslVersion: THREE.GLSL3,
    side: THREE.BackSide,
    depthWrite: false,
    uniforms: { uFogCol: shared.uFogCol, uZenith: shared.uZenith, uSun: shared.uSun, uTime, uSeed, tNoise },
    vertexShader: VERT,
    fragmentShader: /* glsl */ `
precision highp float;
${OUTS}
uniform vec3 uFogCol, uZenith, uSun;
uniform float uTime, uSeed;
uniform sampler2D tNoise;
in vec3 vWorld; in vec3 vNormal; in vec2 vUv; in float vDepth;

${THEMES[name].glsl}
void main() {
  vec3 d = normalize(vWorld - cameraPosition);
  vec3 col = mix(uFogCol, uZenith, smoothstep(0.02, 0.75, d.y));
  float id = 0.0, depth = 1000.0;
  theme(d, col, id, depth);
  oColor = vec4(col, 1.0);
  oData = vec4(0.0, 0.0, depth, id);
}
`,
  });
  cache.set(name, m);
  return m;
}

export interface SkyBox {
  mesh: THREE.Mesh;
  name: string;
  /** 最近一次 set 的完整写法（带种子），用来重新套用 */
  spec: string;
  /** "名字" 或 "名字:种子" */
  set(spec: string): void;
  update(t: number, camera: THREE.Camera): void;
}

export function makeSky(): SkyBox {
  // 半径只要在远裁面（400）以内；最后画，被世界挡住的像素靠深度测试直接跳过，不跑天空的着色器
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(370, 24, 12), material('blank'));
  mesh.frustumCulled = false;
  mesh.renderOrder = 1e6;
  const box: SkyBox = {
    mesh,
    name: 'blank',
    spec: 'blank',
    set(spec) {
      box.spec = spec;
      const [name, seed] = spec.split(':');
      const theme = THEMES[name] ?? THEMES.blank;
      box.name = THEMES[name] ? name : 'blank';
      uSeed.value = seed !== undefined && seed !== '' && Number.isFinite(Number(seed)) ? Number(seed) : 1;
      mesh.material = material(box.name);
      const L = { ...BASE_LIGHT, ...theme.light };
      shared.uFogCol.value.set(L.fog);
      shared.uZenith.value.set(L.zenith);
      bump(shared.uSkyCol.value, L.sky);
      bump(shared.uGroundCol.value, L.ground);
      bump(shared.uSunCol.value, L.sun);
      bump(shared.uGlowCol.value, L.glow ?? BASE_LIGHT.glow!);
      shared.uFogNear.value = L.fogNear ?? BASE_LIGHT.fogNear!;
      shared.uFogFar.value = L.fogFar ?? BASE_LIGHT.fogFar!;
    },
    update(t, camera) {
      mesh.position.copy(camera.position);
      uTime.value = t;
    },
  };
  box.set('blank');
  return box;
}

export function skyLabel(name: string) {
  return THEMES[name]?.label ?? name;
}
