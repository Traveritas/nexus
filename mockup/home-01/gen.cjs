/* 梦里的家 · 样板 01：生成 layouts/*.json（家具、墙、家家家的房间网格都在这里算）
   这份脚本是唯一来源；layouts/ 是它的产物，改布局改这里。

   node mockup/home-01/gen.cjs          只生成 JSON
   node mockup/home-01/all.cjs          生成 → 展开 → 白模 → 地图
*/
const fs = require('fs');
const path = require('path');

const OUT = path.join(__dirname, 'layouts');
const F = 0.3;     // 地板面高（地板是 0.3 厚的 deck）
const T = 0.14;    // 墙厚
const r2 = (v) => Math.round(v * 1000) / 1000;
const rad = (d) => (d * Math.PI) / 180;

// ── 小工具 ──────────────────────────────────────────

function rng(seed) {
  let s = seed >>> 0;
  return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; };
}

// 3×3 旋转：R = Rz(yaw)·Ry(ry)·Rx(rx)，与 Blender 的 Euler XYZ 一致
function rotm(rx, ry, yaw) {
  const [a, b, c] = [rad(rx), rad(ry), rad(yaw)];
  const Rx = [[1, 0, 0], [0, Math.cos(a), -Math.sin(a)], [0, Math.sin(a), Math.cos(a)]];
  const Ry = [[Math.cos(b), 0, Math.sin(b)], [0, 1, 0], [-Math.sin(b), 0, Math.cos(b)]];
  const Rz = [[Math.cos(c), -Math.sin(c), 0], [Math.sin(c), Math.cos(c), 0], [0, 0, 1]];
  const mul = (A, B) => A.map((r) => B[0].map((_, j) => r.reduce((s, v, k) => s + v * B[k][j], 0)));
  return mul(Rz, mul(Ry, Rx));
}
const apply = (M, v) => M.map((r) => r[0] * v[0] + r[1] * v[1] + r[2] * v[2]);

// 家具：本地坐标里一组方块 [dx, dy, dz, sx, sy, sz]（方块的底面中心），正面朝本地 +Y
const FURN = {
  bed: [[0, 0, 0, 1.4, 2.0, 0.3], [0, 0.05, 0.3, 1.36, 1.85, 0.18], [0, -0.72, 0.48, 0.9, 0.36, 0.12], [0, -0.97, 0, 1.4, 0.08, 1.0]],
  nightstand: [[0, 0, 0, 0.45, 0.4, 0.55]],
  wardrobe: [[0, 0, 0, 1.2, 0.6, 2.1]],
  desk: [[0, 0, 0.71, 1.1, 0.55, 0.04], [-0.5, -0.22, 0, 0.05, 0.05, 0.71], [0.5, -0.22, 0, 0.05, 0.05, 0.71], [-0.5, 0.22, 0, 0.05, 0.05, 0.71], [0.5, 0.22, 0, 0.05, 0.05, 0.71]],
  chair: [[0, 0, 0.42, 0.42, 0.42, 0.05], [-0.18, -0.18, 0, 0.04, 0.04, 0.42], [0.18, -0.18, 0, 0.04, 0.04, 0.42], [-0.18, 0.18, 0, 0.04, 0.04, 0.42], [0.18, 0.18, 0, 0.04, 0.04, 0.42], [0, -0.19, 0.47, 0.42, 0.04, 0.45]],
  sofa: [[0, 0, 0, 1.9, 0.85, 0.42], [0, -0.33, 0.42, 1.9, 0.2, 0.4], [-0.87, 0, 0.42, 0.16, 0.85, 0.2], [0.87, 0, 0.42, 0.16, 0.85, 0.2]],
  table: [[0, 0, 0.71, 1.2, 0.8, 0.04], [-0.55, -0.35, 0, 0.05, 0.05, 0.71], [0.55, -0.35, 0, 0.05, 0.05, 0.71], [-0.55, 0.35, 0, 0.05, 0.05, 0.71], [0.55, 0.35, 0, 0.05, 0.05, 0.71]],
  lowtable: [[0, 0, 0, 1.0, 0.55, 0.38]],
  sidetable: [[0, 0, 0, 0.45, 0.45, 0.6]],
  lamp: [[0, 0, 0, 0.3, 0.3, 0.04], [0, 0, 0.04, 0.04, 0.04, 1.35], [0, 0, 1.3, 0.42, 0.42, 0.3]],
  shelf: [[0, 0, 0, 0.9, 0.32, 1.8]],
  tvstand: [[0, 0, 0, 1.6, 0.4, 0.5], [0, -0.05, 0.5, 1.1, 0.06, 0.62]],
  tub: [[0, 0, 0, 1.6, 0.75, 0.55]],
  sink: [[0, 0, 0, 0.6, 0.45, 0.85]],
  toilet: [[0, 0.05, 0, 0.4, 0.55, 0.42], [0, -0.22, 0.42, 0.4, 0.16, 0.4]],
  shoes: [[0, 0, 0, 0.9, 0.35, 0.9]],
  // 小东西（传送物落在上面）
  book: [[0, 0, 0, 0.32, 0.24, 0.04]],
  vase: [[0, 0, 0, 0.14, 0.14, 0.3]],
  glass: [[0, 0, 0, 0.08, 0.08, 0.12]],
};
const NAME = { bed: '床', wardrobe: '衣柜', desk: '书桌', sofa: '沙发', table: '餐桌', shelf: '书架', tvstand: '电视柜', tub: '浴缸', lamp: '落地灯', lowtable: '茶几', chair: '椅子' };

class Layout {
  constructor() { this.prims = []; this.portals = []; this.arrives = []; this.regions = []; this.n = {}; }
  uid(base) { this.n[base] = (this.n[base] || 0) + 1; return `${base}_${this.n[base]}`; }
  box(name, at, size, style, extra = {}) { this.prims.push({ kind: 'box', name: this.uid(name), at: at.map(r2), size: size.map(r2), style, ...extra }); }
  // 一件家具：at 是脚底中心 [x, y, z]，yaw 正面朝向；rx / ry 整件倾斜（反重力用）
  furn(kind, at, yaw = 0, o = {}) {
    const M = rotm(o.rx || 0, o.ry || 0, yaw);
    FURN[kind].forEach(([dx, dy, dz, sx, sy, sz], i) => {
      const w = apply(M, [dx, dy, dz]);
      const extra = { rot: r2(yaw) };
      if (o.rx) extra.rx = r2(o.rx);
      if (o.ry) extra.ry = r2(o.ry);
      if (o.plan) extra.plan = o.plan;
      if (i === 0 && o.label !== undefined) extra.label = o.label;
      this.box(o.name || kind, [at[0] + w[0], at[1] + w[1], at[2] + w[2]], [sx, sy, sz], o.style || 'prop', extra);
    });
  }
  // 沿 X 的墙（在 y 处），openings: [{c, w, h}]，开口上方补门楣到墙顶
  wallX(y, x0, x1, H, openings = [], style = 'wall', z0 = F) {
    this._wall(x0, x1, openings, H, style, z0, (c, len, z, h, ex) => this.box('wall', [c, y, z], [len, T, h], style, ex));
  }
  wallY(x, y0, y1, H, openings = [], style = 'wall', z0 = F) {
    this._wall(y0, y1, openings, H, style, z0, (c, len, z, h, ex) => this.box('wall', [x, c, z], [T, len, h], style, ex));
  }
  _wall(a0, a1, openings, H, style, z0, put) {
    let cur = a0;
    for (const o of [...openings].sort((p, q) => p.c - q.c)) {
      const l = o.c - o.w / 2, r = o.c + o.w / 2;
      if (l - cur > 0.02) put((cur + l) / 2, l - cur, z0, H);
      if (H - o.h > 0.02) put(o.c, o.w, z0 + o.h, H - o.h, { plan: 'ghost' }); // 门楣
      cur = r;
    }
    if (a1 - cur > 0.02) put((cur + a1) / 2, a1 - cur, z0, H);
  }
  // 房间地板：矩形 [x0, y0, x1, y1]
  floor(name, r, label, style = 'deck') {
    this.box(name, [(r[0] + r[2]) / 2, (r[1] + r[3]) / 2, 0], [r[2] - r[0], r[3] - r[1], F], style, label ? { label } : {});
  }
  portal(p) { this.portals.push({ pair: false, ...p }); }
  arrive(name, at, face) { this.arrives.push({ name, at: at.map(r2), face }); }
  region(label, at, size) { this.regions.push({ label, shape: 'rect', at, size }); }
  circle(label, at, r, label_at) { this.regions.push({ label, shape: 'circle', at, r, ...(label_at ? { label_at } : {}) }); }
}

const DOOR = { w: 0.9, h: 2.05 };
const door = (c, w = DOOR.w, h = DOOR.h) => ({ c, w, h });

// ── 核心：卧室与小客厅 ──────────────────────────────

function core() {
  const L = new Layout();
  const H = 2.5; // 天花板（样板里不盖，只按这个高度砌墙）
  // 房间（x0, y0, x1, y1）
  const R = {
    hall: [-4.6, -0.55, 3.4, 0.55],
    bed: [-4.6, 0.55, -0.6, 4.15],
    bath: [-0.6, 0.55, 1.6, 2.75],
    store: [1.6, 0.55, 3.4, 2.15],
    living: [-4.6, -4.55, 0.2, -0.55],
    dining: [0.2, -3.55, 3.0, -0.55],
    porch: [-1.6, -5.55, 0.2, -4.55],
  };
  L.floor('floor_bed', R.bed, '卧室');
  L.floor('floor_hall', R.hall, '走廊');
  L.floor('floor_bath', R.bath, '浴室');
  L.floor('floor_store', R.store, '储物间');
  L.floor('floor_living', R.living, '小客厅');
  L.floor('floor_dining', R.dining, '餐桌一角');
  L.floor('floor_porch', R.porch, '玄关');

  // 外墙
  L.wallX(4.15, -4.6 - T / 2, -0.6, H);                                 // 卧室北
  L.wallX(2.75, -0.6, 1.6, H);                                          // 浴室北
  L.wallX(2.15, 1.6, 3.4 + T / 2, H);                                   // 储物间北
  L.wallY(-4.6, -4.55, 4.15, H, [{ c: -2.6, w: 2.2, h: 2.3 }]);         // 西墙：客厅的落地窗
  L.wallY(-0.6, 2.75, 4.15, H);                                         // 卧室东墙北段
  L.wallY(1.6, 2.15, 2.75, H);
  L.wallY(3.4, -0.55, 2.15, H, [door(0)]);                              // 走廊尽头的门 → 家家家
  L.wallY(3.0, -3.55, -0.55, H);                                        // 餐桌东
  L.wallX(-3.55, 0.2, 3.0 + T / 2, H, []);                              // 餐桌南
  L.wallX(-4.55, -4.6 - T / 2, -1.6, H);                                // 客厅南西段
  L.wallY(0.2, -4.55, -3.55, H);
  L.wallY(-1.6, -5.55, -4.55, H);                                       // 玄关两侧
  L.wallY(0.2, -5.55, -4.55, H);
  L.wallX(-5.55, -1.6 - T / 2, 0.2 + T / 2, H, [door(-0.7, 1.0, 2.1)]);  // 玄关的门 → 室外
  // 内墙
  L.wallX(0.55, -4.6, 3.4, H, [door(-1.4), door(0.5), door(2.5, 0.8)]); // 走廊北：卧室、浴室、储物间
  L.wallX(-0.55, -4.6, 3.0, H, [{ c: -1.2, w: 1.6, h: 2.2 }, { c: 1.6, w: 2.0, h: 2.2 }]); // 走廊南：客厅、餐桌（宽口）
  L.wallY(0.2, -3.55, -0.55, H, [{ c: -2.1, w: 2.2, h: 2.2 }]);         // 客厅与餐桌之间的宽口
  L.wallY(-0.6, 0.55, 2.75, H, []);                                     // 卧室与浴室
  L.wallY(1.6, 0.55, 2.15, H, []);                                      // 浴室与储物间
  L.wallX(-4.55, -1.6, 0.2, H, [door(-0.7, 1.2, 2.2)]);                 // 客厅与玄关
  // 落地窗的玻璃（走出去 → 云阶）
  L.box('window_glass', [-4.6, -2.6, F], [0.04, 2.2, 2.3], 'glass', { collide: false, label: '落地窗' });

  // 卧室
  L.furn('bed', [-3.6, 3.1, F], 180, { label: '床' });
  L.furn('nightstand', [-2.6, 3.85, F], 180);
  L.furn('wardrobe', [-0.95, 3.2, F], 90, { label: '衣柜' });
  L.furn('desk', [-4.3, 1.35, F], -90, { label: '书桌' });
  L.furn('chair', [-3.75, 1.35, F], 90);
  L.furn('book', [-4.3, 1.35, F + 0.75], -90);
  L.furn('shelf', [-2.2, 0.8, F], 0);
  // 浴室
  L.furn('tub', [0.5, 2.3, F], 180, { label: '浴缸' });
  L.furn('sink', [1.25, 1.2, F], -90);
  L.furn('toilet', [-0.3, 1.1, F], 90);
  // 储物间：几只箱子
  L.box('crate', [2.1, 1.7, F], [0.6, 0.5, 0.5], 'prop');
  L.box('crate', [2.1, 1.7, F + 0.5], [0.5, 0.45, 0.4], 'prop');
  L.box('crate', [3.0, 1.2, F], [0.5, 0.6, 1.2], 'prop');
  // 小客厅
  L.furn('tvstand', [-2.6, -0.85, F], 180, { label: '电视柜' });
  L.furn('sofa', [-2.4, -3.95, F], 0, { label: '沙发' });
  L.furn('lowtable', [-2.4, -2.5, F], 0);
  L.furn('sidetable', [-3.85, -4.1, F], 0);
  L.furn('vase', [-3.85, -4.1, F + 0.6], 0);
  L.furn('lamp', [-0.5, -4.1, F], 0);
  // 餐桌一角
  L.furn('table', [1.6, -2.0, F], 0, { label: '餐桌' });
  L.furn('chair', [1.6, -2.75, F], 0);
  L.furn('chair', [1.6, -1.25, F], 180);
  L.furn('glass', [1.85, -2.0, F + 0.75], 0);
  // 玄关
  L.furn('shoes', [-1.3, -5.05, F], -90);

  // 出入口（arrive 都写成脚底高度；名字＝从哪儿来）
  L.portal({ name: 'p_bed', kind: 'world', to: 'descent', mode: 'key', title: '睡', at: [-3.6, 2.6, 1.0], label: '→ 下沉' });
  L.portal({ name: 'p_wardrobe', kind: 'world', to: 'room', mode: 'walk', at: [-0.95, 3.2, 1.3], rot: 90, label: '→ 无墙之屋', note: '走进衣柜' });
  L.portal({ name: 'p_book', kind: 'world', to: 'arcade', mode: 'key', title: '翻开', at: [-4.3, 1.35, 1.2], label: '→ 回廊' });
  L.portal({ name: 'p_window', kind: 'world', to: 'isles', mode: 'walk', at: [-4.6, -2.6, 1.4], rot: 90, label: '→ 云阶', note: '走出落地窗' });
  L.portal({ name: 'p_vase', kind: 'world', to: 'glasshouse', mode: 'key', title: '凑近', at: [-3.85, -4.1, 1.3], label: '→ 花房' });
  L.portal({ name: 'p_glass', kind: 'world', to: 'shoal', mode: 'key', title: '一杯水', at: [1.85, -2.0, 1.3], label: '→ 浅滩' });
  L.portal({ name: 'p_out', kind: 'world', to: 'home-outside', at_node: 'home-core', mode: 'walk', at: [-0.7, -5.55, 1.3], rot: 180, label: '→ 室外', note: '推开玄关的门' });
  L.portal({ name: 'p_rooms', kind: 'world', to: 'home-rooms', at_node: 'home-core', mode: 'walk', at: [3.4, 0, 1.3], rot: -90, label: '→ 家家家', note: '走廊尽头那扇门' });
  L.arrive('descent', [-3.6, 1.4, F], 180);
  L.arrive('room', [-1.9, 3.2, F], -90);
  L.arrive('arcade', [-3.2, 1.35, F], 90);
  L.arrive('isles', [-3.6, -2.6, F], -90);
  L.arrive('glasshouse', [-3.85, -3.2, F], 180);
  L.arrive('shoal', [1.85, -1.1, F], 180);
  L.arrive('home-outside', [-0.7, -4.9, F], 0);
  L.arrive('home-rooms', [2.6, 0, F], 90);
  L.arrive('home-rooms-bed', [-2.6, 1.6, F], 180);  // 家家家里那间「和卧室一样的」走进来落在这里

  return {
    id: 'home-core',
    title: '家 · 核心',
    en: 'Home · Core',
    role: '比记忆里更小、更窄的家：卧室、走廊、小客厅、餐桌一角、浴室、储物间、玄关。墙离人近，天花板 2.5m；浅梦的六个世界从这里出发。',
    extent: 16,
    sky: 'blank',
    spawn: { at: [-2.6, 1.6, F], face: 180 },
    levels: [{ z: F, label: '地板' }, { z: F + H, label: '天花板（样板里不盖）' }],
    prims: L.prims, portals: L.portals, arrives: L.arrives, regions: L.regions,
    views: [
      { name: 'bird', at: [9, -12, 13], look: [-0.6, -0.4, 0.5], fov: 50 },
      { name: 'bedroom', at: [-1.2, 1.0, 1.9], look: [-4.0, 3.8, 1.0], fov: 78 },
      { name: 'hall', at: [-4.2, 0, 1.9], look: [3.4, 0, 1.4], fov: 70 },
      { name: 'living', at: [0.6, -1.0, 1.9], look: [-4.2, -3.6, 0.8], fov: 78 },
    ],
    notes: [
      '比现在的家（室内 18×10m）小一半左右：卧室 4×3.6m，走廊宽 1.1m，客厅 4.8×4m。包裹感来自墙近、天花板低、灯暖、家具挤。',
      '走廊是脊：卧室、浴室、储物间、客厅都开在它上面；尽头那扇门平时不开，后面是家家家。',
      '六个通往浅梦世界的传送物仍在核心里，各在各的房间：床、衣柜、书在卧室，落地窗、花瓶在客厅，一杯水在餐桌。',
      '玄关的门通往室外：走出去回头，只有一扇门立在草地上。',
      '家不需要回家的灯。天花板在样板里不盖，只按 2.5m 砌墙。',
    ],
  };
}

// ── 室外 ──────────────────────────────────────────
// 不靠摆件，靠空地本身和屋里不一样：正午（屋里是夜）、格子更粗、换一组颜色、天压得很低。
// 地上几乎什么都没有；能看的都在头顶那层云上：垂下来的云、云上的一个洞、洞里落下来的一柱光。

function outside() {
  const L = new Layout();
  const G = 0;
  const CZ = 6;      // 云底的高度
  const IN = 34;     // 平的云底到这里为止，再往外一路压下来
  const OUT = 48;    // 云在这里贴到地上

  // 立着的门：门框 + 半开的门扇 + 一级门槛
  L.box('threshold', [0, 0, G], [1.4, 0.6, 0.12], 'stair');
  L.prims.push({ kind: 'frame', name: 'door_frame', w: 1.2, h: 2.25, t: 0.12, depth: 0.22, at: [0, 0, 0.12], rot: 0, style: 'frame', label: '一扇门' });
  L.box('door_leaf', [0.42, -0.42, 0.12], [0.05, 0.92, 2.05], 'frame', { rot: 0 });

  // 云底：一整块平的，在光柱那儿开一个洞（四块拼出洞口）
  const [hx, hy, hr] = [-10, -26, 2.6];
  const slab = (x0, y0, x1, y1, extra = {}) => {
    if (x1 - x0 < 0.05 || y1 - y0 < 0.05) return;
    L.box('cloud', [(x0 + x1) / 2, (y0 + y1) / 2, CZ], [x1 - x0, y1 - y0, 0.4], 'glass', { collide: false, shadow: false, plan: 'ghost', ...extra });
  };
  slab(-IN, -IN, IN, hy - hr);
  slab(-IN, hy + hr, IN, IN, { label: '云底 · 离地 6m' });
  slab(-IN, hy - hr, hx - hr, hy + hr);
  slab(hx + hr, hy - hr, IN, hy + hr);
  // 往外，云一路压下来，在 48m 贴到地上：天和地在远处合上（四面都铺满宽，角上自然交出斜脊）
  const run = OUT - IN, len = Math.hypot(run, CZ), a = (Math.atan2(CZ, run) * 180) / Math.PI;
  const skirt = { collide: false, shadow: false, plan: 'ghost' };
  L.box('cloud_edge', [0, (IN + OUT) / 2, CZ / 2], [OUT * 2, len, 0.4], 'glass', { ...skirt, rx: r2(-a) });
  L.box('cloud_edge', [0, -(IN + OUT) / 2, CZ / 2], [OUT * 2, len, 0.4], 'glass', { ...skirt, rx: r2(a) });
  L.box('cloud_edge', [(IN + OUT) / 2, 0, CZ / 2], [OUT * 2, len, 0.4], 'glass', { ...skirt, rot: 90, rx: r2(a) });
  L.box('cloud_edge', [-(IN + OUT) / 2, 0, CZ / 2], [OUT * 2, len, 0.4], 'glass', { ...skirt, rot: 90, rx: r2(-a) });

  // 洞里落下来的一柱光，地上一块被照亮的圆 → 晾场
  L.prims.push({ kind: 'cylinder', name: 'sunshaft', at: [hx, hy, G], r: 2.2, h: CZ, style: 'glass', collide: false, shadow: false, label: '云上一个洞，一柱光' });
  L.prims.push({ kind: 'cylinder', name: 'sunlit', at: [hx, hy, G], r: 2.5, h: 0.02, style: 'rail', collide: false });

  // 垂下来的云：一团挤在门后东北，一根孤零零在西边，一根一直垂到地上
  const drips = [
    [7, 11, 2.6, 0.7, 2.6], [10.5, 14, 3.8, 1.0, 2.8], [13, 10, 4.6, 0.6, 1.8], [9, 18, 1.4, 1.4, 3.6],
    [15, 16, 3.2, 0.9, 2.4], [5, 16, 4.4, 0.5, 1.6],
    [-27, 3, 2.2, 0.9, 2.6],
  ];
  drips.forEach(([x, y, z, r, rt], i) => {
    L.prims.push({ kind: 'cylinder', name: L.uid('drip'), at: [x, y, z], r, r2: rt, h: CZ - z, style: 'glass', collide: false, shadow: false, plan: 'ghost', ...(i === 1 ? { label: '一团垂下来的云' } : {}) });
  });
  L.prims.push({ kind: 'cylinder', name: 'drip_ground', at: [24, -6, G], r: 2.6, r2: 4.2, h: CZ, style: 'glass', collide: false, shadow: false, label: '垂到地上的云（走得进去）' });

  // 地面不平：几处很缓的隆起，空地不是一张纸
  for (const [x, y, r, rt, h] of [[-17, 9, 8, 5, 0.5], [15, -16, 10, 6.5, 0.8], [-5, 27, 5.5, 3.5, 0.35], [-31, -18, 7, 4, 0.6]]) {
    L.prims.push({ kind: 'cylinder', name: L.uid('swell'), at: [x, y, G], r, r2: rt, h, style: 'deck', segments: 32 });
  }

  L.portal({ name: 'p_door', kind: 'world', to: 'home-core', at_node: 'home-outside', mode: 'walk', at: [0, 0, 1.2], rot: 0, label: '→ 玄关', note: '走回门里' });
  L.portal({ name: 'p_shaft', kind: 'world', to: 'drying', mode: 'walk', at: [hx, hy, 1.2], radius: 1.6, pair: false, label: '→ 晾场', note: '站进光里' });
  L.arrive('home-core', [0, -1.4, G], 180);
  L.arrive('drying', [hx, hy + 3.4, G], 0);
  L.circle('悄悄带回来 · 云压到约 2.6m 处换回门前另一侧', [0, 0], 42, [0, -39]);
  L.circle('云贴到地上', [0, 0], OUT, [0, -46]);

  return {
    id: 'home-outside',
    title: '家 · 室外',
    en: 'Home · Outside',
    role: '推开夜里的家门，外面是正午。一大片空地，天压得很低，像一块无限大的天花板；回头只有一扇门立着，门里还是黑的。',
    extent: 110,
    ground: { a: 'white', b: 'green', pattern: 'grain' },
    sky: 'pale',
    sun: [0.03, -0.05, 1],
    shade: 'FLAT',
    // 管线参数（引擎还不认，先写在这里）：正午、格子比屋里粗、只用这几枚色板色
    look: { time: 'noon', grid: 8, palette: ['white', 'mist', 'blue_pale', 'blue', 'green'] },
    spawn: { at: [0, -1.4, G], face: 180 },
    prims: L.prims, portals: L.portals, arrives: L.arrives, regions: L.regions,
    views: [
      { name: 'eye', at: [0, -1.4, 1.6], look: [-10, -26, 2.2], fov: 74 },
      { name: 'back', at: [1.5, -7, 1.6], look: [4, 6, 2.2], fov: 70 },
      { name: 'wide', at: [26, -30, 1.6], look: [0, 0, 2.6], fov: 90 },
      { name: 'under', at: [-30, 30, 5.2], look: [2, -2, 0], fov: 80 },
    ],
    notes: [
      '和屋里不是一个地方，靠的是空地本身：屋里是夜，门外是正午；格子比屋里粗一级（屋里 4px，门外 8px）；只用白、雾、淡蓝、蓝、绿几枚色，屋里的暖色一个都不出现（look 字段；原型 house_out 里已接上）。',
      '天压得很低：云底离地 6m，平平地铺满头顶，像一块无限大的天花板。屋里低，外面也低，只是没有墙。',
      '地上几乎什么都没有，只有几处很缓的隆起。能看的东西都在头顶：门后东北一团垂下来的云、西边孤零零一根、东边一根一直垂到地上（走得进去）。',
      '出生点背对着门，正前方偏左约 28m，云上开着一个洞，一柱正午的光落下来——整片空地唯一有影子、有直射光的地方。站进光里 → 晾场。',
      '边界：往外云一路压下来，48m 处贴到地上。走到云压到约 2.6m 高的地方（约 42m），悄悄回到门前另一侧（要在引擎里加，样板里只画出那两圈）。',
    ],
  };
}

// ── 家家家 ────────────────────────────────────────

function rooms() {
  const L = new Layout();
  const rnd = rng(23);
  const pick = (a) => a[Math.floor(rnd() * a.length)];
  const lerp = (a, b, t) => a + (b - a) * t;

  // 过渡：一串门，一扇比一扇小、一扇比一扇歪
  L.floor('floor_pass', [-1.2, -0.8, 14.2, 0.8], '过渡 · 一串门');
  L.wallX(0.8, -1.2, 14.2, 2.5);
  L.wallX(-0.8, -1.2, 14.2, 2.5);
  L.wallY(-1.2, -0.8, 0.8, 2.5, [door(0)]);
  L.prims.push({ kind: 'procession', name: 'doors', from: [1, 0], to: [13.4, 0], n: 9, w0: 1.4, h0: 2.6, grow: 0.76, roll: 3.5, t: 0.1, depth: 0.16, at: [0, 0, F], style: 'frame' });

  // 房间网格：4 列 × 3 行，越往东越错乱
  const COLS = 4, ROWS = 3, W = 5.2, D = 4.6, X0 = 14.2, Y0 = -D * 1.5;
  const cell = (c, r) => [X0 + c * W, Y0 + r * D, X0 + (c + 1) * W, Y0 + (r + 1) * D];
  const wrong = (c, r) => Math.min(1, (c + Math.abs(r - 1) * 0.6) / 3.2);
  const height = (c, r) => r2(lerp(2.5, 4.6, wrong(c, r)));
  const HOME = [3, 2];   // 和卧室一模一样的那间（最深处、最安静）
  const NAMES = ['几乎一样', '多了一把椅子', '换了位置', '转了', '浮起来', '倒挂', '散开'];

  for (let c = 0; c < COLS; c++) for (let r = 0; r < ROWS; r++) {
    const [x0, y0, x1, y1] = cell(c, r), cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
    const w = wrong(c, r), H = height(c, r);
    const isHome = c === HOME[0] && r === HOME[1];
    L.floor('floor_room', [x0, y0, x1, y1], isHome ? '和卧室一样的那间' : null);
    if (isHome) {
      // 卧室原样：床靠北墙、床头柜、书桌靠西墙、衣柜靠东墙
      L.furn('bed', [cx - 0.9, y1 - 1.1, F], 180);
      L.furn('nightstand', [cx + 0.1, y1 - 0.35, F], 180);
      L.furn('desk', [x0 + 0.35, cy - 0.8, F], -90);
      L.furn('chair', [x0 + 0.9, cy - 0.8, F], 90);
      L.furn('wardrobe', [x1 - 0.4, cy + 0.4, F], 90);
      L.furn('shelf', [cx + 0.5, y0 + 0.3, F], 0);
      continue;
    }
    const kinds = ['bed', 'chair', 'chair', 'sofa', 'desk', 'wardrobe', 'table', 'lamp', 'shelf', 'tvstand', 'lowtable', 'nightstand'];
    const n = Math.round(lerp(3, 7, w));
    for (let i = 0; i < n; i++) {
      const k = (w > 0.2 && rnd() < 0.3) ? 'chair' : pick(kinds);   // 往里椅子越来越多
      const m = 1.1;
      let x = lerp(x0 + m, x1 - m, rnd()), y = lerp(y0 + m, y1 - m, rnd());
      let yaw = w < 0.15 ? pick([0, 90, 180, -90]) : rnd() * 360;
      let z = F, o = {};
      if (w < 0.15) {   // 几乎正常：靠墙
        // 门洞都在墙的中段，靠墙的东西只放在两头
        const end = (a0, a1, c) => (rnd() < 0.5 ? lerp(a0 + 0.8, c - 1.2, rnd()) : lerp(c + 1.2, a1 - 0.8, rnd()));
        if (rnd() < 0.5) { y = pick([y0 + 0.6, y1 - 0.6]); x = end(x0, x1, cx); }
        else { x = pick([x0 + 0.6, x1 - 0.6]); y = end(y0, y1, cy); }
      }
      if (w > 0.45 && rnd() < w) z = F + r2(lerp(0.3, H - 1.6, rnd()));                      // 浮起来
      if (w > 0.55 && rnd() < w) o = { rx: r2((rnd() - 0.5) * 80 * w), ry: r2((rnd() - 0.5) * 80 * w) }; // 斜着
      if (w > 0.7 && rnd() < 0.35) { z = F + H; o = { rx: 180, plan: 'ghost' }; }                         // 倒挂在天花板上
      L.furn(k, [x, y, z], yaw, o);
    }
    if (w > 0.6 && rnd() < 0.8) {   // 房间中间立着一扇没有墙的门，或一段通进天花板的楼梯
      if (rnd() < 0.5) L.prims.push({ kind: 'frame', name: L.uid('lone_door'), w: 1.0, h: 2.1, t: 0.1, depth: 0.16, at: [cx, cy, F], rot: r2(rnd() * 180), style: 'frame' });
      else L.prims.push({ kind: 'stairs', name: L.uid('ceil_stair'), w: 0.9, n: Math.ceil(H / 0.3), rise: 0.3, run: 0.3, at: [cx, y0 + 0.6, F], rot: 0, style: 'stair' });
    }
    L.regions.push({ label: NAMES[Math.min(NAMES.length - 1, Math.floor(w * (NAMES.length - 0.01)))], shape: 'rect', at: [cx, cy], size: [W - 0.4, D - 0.4] });
  }
  // 房间之间的墙：每段中间一扇门洞；高度取两边较高的
  for (let c = 0; c <= COLS; c++) for (let r = 0; r < ROWS; r++) {
    const x = X0 + c * W, ya = Y0 + r * D, yb = ya + D;
    const H = Math.max(c > 0 ? height(c - 1, r) : 0, c < COLS ? height(c, r) : 0);
    const open = c === 0 ? (r === 1 ? [door(ya + D / 2, 1.6, 2.5)] : [])   // 西：只有过渡那一口
      : [door(ya + D / 2 + (rnd() - 0.5) * 1.4 * (c / COLS))];             // 内墙与东墙（东墙的门是循环口）
    L.wallY(x, ya, yb, H, open);
  }
  for (let r = 0; r <= ROWS; r++) for (let c = 0; c < COLS; c++) {
    const y = Y0 + r * D, xa = X0 + c * W, xb = xa + W;
    const H = Math.max(r > 0 ? height(c, r - 1) : 0, r < ROWS ? height(c, r) : 0);
    const inner = r > 0 && r < ROWS;
    L.wallX(y, xa, xb, H, inner ? [door(xa + W / 2 + (rnd() - 0.5) * 1.6 * (c / COLS))] : []);
  }
  // 循环：走出最东那列的门，从最西那列进来
  const xE = X0 + COLS * W;
  for (let r = 0; r < ROWS; r++) {
    const y = Y0 + r * D + D / 2;
    if (r === 1) continue; // 中间那行的东门留给「门后还是门」，见下
    L.portal({ name: `p_loop_${r}`, kind: 'world', to: 'home-rooms', at_node: `west_${r}`, mode: 'walk', at: [xE + 0.3, y, 1.3], rot: -90, label: '↺ 最西那间', note: '循环' });
    L.arrive(`west_${r}`, [X0 + 1.0, y, F], -90);
  }
  // 东墙中间那扇门后面：又是一串门（缩小版过渡），走进去回到过渡的开头
  L.floor('floor_back', [xE, -0.8, xE + 6, 0.8]);
  L.prims.push({ kind: 'procession', name: 'doors_back', from: [xE + 0.6, 0], to: [xE + 5.4, 0], n: 5, w0: 1.1, h0: 2.2, grow: 0.88, roll: -6, t: 0.08, depth: 0.12, at: [0, 0, F], style: 'frame' });
  L.portal({ name: 'p_back', kind: 'world', to: 'home-rooms', at_node: 'pass_start', mode: 'walk', at: [xE + 5.6, 0, 1.0], rot: -90, label: '↺ 过渡的开头', note: '门后还是门' });
  L.arrive('pass_start', [0.2, 0, F], -90);
  // 出入口
  const [hx0, hy0, hx1] = cell(HOME[0], HOME[1]);
  L.portal({ name: 'p_home_bed', kind: 'world', to: 'home-core', at_node: 'home-rooms-bed', mode: 'walk', at: [(hx0 + hx1) / 2 - 0.9, hy0 + 2.2, 1.3], rot: 180, label: '→ 卧室', note: '走进这间就回到真正的卧室', radius: 1.4 });
  L.portal({ name: 'p_return', kind: 'world', to: 'home-core', at_node: 'home-rooms', mode: 'walk', at: [-1.2, 0, 1.3], rot: 90, label: '→ 走廊', note: '原路回去' });
  L.arrive('home-core', [0.2, 0, F], -90);

  return {
    id: 'home-rooms',
    title: '家 · 家家家',
    en: 'Home · Rooms, Rooms',
    role: '走廊尽头那扇门后面：先是一串越来越小、越来越歪的门，然后是一间间连着的家，全是家里的家具，越往里越错乱——浮起来、斜着、倒挂在天花板上。',
    extent: 52,
    slab: false,
    sky: 'pale',
    spawn: { at: [0.2, 0, F], face: -90 },
    prims: L.prims, portals: L.portals, arrives: L.arrives, regions: L.regions,
    views: [
      { name: 'bird', at: [52, -32, 30], look: [22, 0, 0], fov: 50 },
      { name: 'pass', at: [-0.6, 0, 1.9], look: [14, 0, 1.4], fov: 64 },
      { name: 'mid', at: [19.9, -1.7, 1.75], look: [24.2, 1.8, 1.3], fov: 80 },
      { name: 'deep', at: [30.3, -1.8, 1.75], look: [34.6, 1.9, 2.8], fov: 84 },
      { name: 'samebed', at: [34.4, 2.8, 1.75], look: [30.4, 6.4, 0.8], fov: 80 },
    ],
    notes: [
      '过渡：九扇门一扇比一扇小（2.6m 高收到最后一扇约 2.0m，刚好过得去）、一扇比一扇歪。',
      '房间 4×3 网格，每间 5.2×4.6m；离入口越远越错乱：靠墙摆好 → 多了椅子、换了位置 → 转了、浮起来 → 斜着、倒挂在天花板上。天花板也越来越高（2.5 → 4.6m）。',
      '最深处一角是「和卧室一样的那间」，安安静静；走进去回到真正的卧室。',
      '循环：最东那列的门通往同一行最西那间；中间那行的东门后面又是一串门，回到过渡的开头。要在引擎里加无缝的循环，样板里用传送物代替。',
      '和无墙之屋（同一间房复制三遍）很像，二选一：并进来当其中一间，或者让无墙之屋只剩框架与虚空。',
      '样板里不盖天花板；倒挂的家具按天花板高度放。家具摆放由种子生成，改种子换一套。',
    ],
  };
}

fs.mkdirSync(OUT, { recursive: true });
for (const d of [core(), outside(), rooms()]) {
  fs.writeFileSync(path.join(OUT, `${d.id}.json`), JSON.stringify(d, null, 1), 'utf8');
  console.log(`[gen] ${d.id} · ${d.prims.length} 项 · ${d.portals.length} 出入口`);
}
