/* 程序化的纸片：树、云、星、草、灌木、花。
   名字写成  族[.变体][:种子]  ——  tree、tree:7、tree.pine:3、cloud.heap:12、star.cluster:5。
   不写变体时按种子挑一个；不写种子时是 1。同一个名字永远生成同一张图。

   画法是逐像素的，不用画布的抗锯齿：
   · 体积 ＝ 一组圆（或椭圆）的并集；每个像素按「离它最深的那个圆」求一个球面法线，左上来光，
     亮度按 4×4 Bayer 抖动落到一条 3~4 色的色阶上——像素画的明暗，而不是平涂。
   · 下沿、右沿压暗一档，读起来有厚度；轮廓交给管线的描边。 */
import * as THREE from 'three';

/* ── 随机数与色阶 ─────────────────────────── */

export type Rng = { (): number; range(a: number, b: number): number; int(a: number, b: number): number; pick<T>(xs: T[]): T };

export function rng(seed: number): Rng {
  let s = (seed * 2654435761) >>> 0 || 1;
  const f = (() => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }) as Rng;
  f.range = (a, b) => a + (b - a) * f();
  f.int = (a, b) => Math.floor(a + (b - a + 1) * f());
  f.pick = (xs) => xs[Math.floor(f() * xs.length)];
  return f;
}

const RAMP = {
  trunk: ['#3a3350', '#5c5378', '#82799e'],
  pink: ['#6e4f66', '#a8798c', '#d9aab5', '#f3d6d6'],
  lilac: ['#5c5378', '#82799e', '#a8a1bf', '#cdc8db'],
  sage: ['#4a6a66', '#5f8c80', '#86b5a5', '#c3d1e6'],
  blue: ['#5c5378', '#8fa3c7', '#c3d1e6', '#ece9f2'],
  mist: ['#a8a1bf', '#cdc8db', '#ece9f2', '#fbf9f7'],
  gold: ['#a8798c', '#ead7a0', '#fbf9f7'],
  rose: ['#6e4f66', '#a8798c', '#d9aab5'],
};
type Ramp = string[];
const BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5].map((v) => v / 16 - 0.47);
const bayer = (x: number, y: number) => BAYER[(y & 3) * 4 + (x & 3)];

/* ── 像素格 ───────────────────────────────── */

class Px {
  c: (string | null)[];
  constructor(public w: number, public h: number) {
    this.c = new Array(w * h).fill(null);
  }
  in(x: number, y: number) {
    return x >= 0 && y >= 0 && x < this.w && y < this.h;
  }
  get(x: number, y: number) {
    return this.in(x, y) ? this.c[y * this.w + x] : null;
  }
  set(x: number, y: number, col: string | null) {
    x = Math.round(x);
    y = Math.round(y);
    if (this.in(x, y)) this.c[y * this.w + x] = col;
  }
  /** 粗线：沿线盖圆点；色阶左亮右暗 */
  line(x0: number, y0: number, x1: number, y1: number, w: number, ramp: Ramp) {
    const n = Math.max(1, Math.ceil(Math.hypot(x1 - x0, y1 - y0) * 1.5));
    for (let i = 0; i <= n; i++) {
      const t = i / n;
      const x = x0 + (x1 - x0) * t;
      const y = y0 + (y1 - y0) * t;
      const r = Math.max(0.5, w / 2);
      for (let dy = -Math.ceil(r); dy <= Math.ceil(r); dy++)
        for (let dx = -Math.ceil(r); dx <= Math.ceil(r); dx++) {
          if (dx * dx + dy * dy > r * r + 0.25) continue;
          const side = w < 2.5 ? 1 : dx < -r * 0.3 ? 2 : dx > r * 0.3 ? 0 : 1;
          this.set(x + dx, y + dy, ramp[Math.min(ramp.length - 1, side)]);
        }
    }
  }
  /** 裁到内容：底边落在 baseY，左右以 cx 对称（纸片的锚点是底边中点） */
  crop(cx: number, baseY: number) {
    let x0 = Infinity, x1 = -Infinity, y0 = Infinity;
    for (let y = 0; y < this.h; y++)
      for (let x = 0; x < this.w; x++)
        if (this.c[y * this.w + x]) { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); }
    if (!isFinite(x0)) return this;
    const half = Math.ceil(Math.max(cx - x0, x1 + 1 - cx)) + 1;
    const out = new Px(half * 2, Math.round(baseY) - y0 + 1);
    for (let y = 0; y < out.h; y++)
      for (let x = 0; x < out.w; x++) out.c[y * out.w + x] = this.get(Math.round(cx) - half + x, y0 + y);
    return out;
  }
  texture() {
    const cv = document.createElement('canvas');
    cv.width = this.w;
    cv.height = this.h;
    const g = cv.getContext('2d')!;
    const im = g.createImageData(this.w, this.h);
    for (let i = 0; i < this.c.length; i++) {
      const col = this.c[i];
      if (!col) continue;
      const n = parseInt(col.slice(1), 16);
      im.data[i * 4] = n >> 16;
      im.data[i * 4 + 1] = (n >> 8) & 255;
      im.data[i * 4 + 2] = n & 255;
      im.data[i * 4 + 3] = 255;
    }
    g.putImageData(im, 0, 0);
    const tex = new THREE.CanvasTexture(cv);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.magFilter = THREE.NearestFilter;
    tex.minFilter = THREE.NearestFilter;
    tex.generateMipmaps = false;
    return tex;
  }
}

/** 一团体积：圆或椭圆（rx, ry）；bias 让各团亮度略有差别，读得出一簇一簇 */
interface Blob { x: number; y: number; rx: number; ry: number; bias?: number }

const LIGHT = (() => {
  const v = [-0.5, -0.75, 0.6];
  const l = Math.hypot(...v);
  return v.map((x) => x / l);
})();

/** 把一组团画成有体积的一块；clipY 以下不画（平底）；under 下沿压暗的行数 */
function shade(px: Px, blobs: Blob[], ramp: Ramp, o: { clipY?: number; under?: number; noise?: number; seed?: number } = {}) {
  const k = ramp.length;
  let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
  for (const b of blobs) {
    x0 = Math.min(x0, b.x - b.rx); x1 = Math.max(x1, b.x + b.rx);
    y0 = Math.min(y0, b.y - b.ry); y1 = Math.max(y1, b.y + b.ry);
  }
  const inside = (x: number, y: number) => {
    if (o.clipY !== undefined && y > o.clipY) return null;
    let best: Blob | null = null, depth = 0, nx = 0, ny = 0;
    for (const b of blobs) {
      const dx = (x - b.x) / b.rx, dy = (y - b.y) / b.ry;
      const d = 1 - Math.hypot(dx, dy);
      if (d > depth) { depth = d; best = b; nx = dx; ny = dy; }
    }
    return best ? { b: best, nx, ny } : null;
  };
  const r = rng(o.seed ?? 7);
  for (let y = Math.floor(y0); y <= Math.ceil(y1); y++)
    for (let x = Math.floor(x0); x <= Math.ceil(x1); x++) {
      const p = inside(x + 0.5, y + 0.5);
      if (!p) continue;
      const nz = Math.sqrt(Math.max(0, 1 - p.nx * p.nx - p.ny * p.ny));
      let v = (p.nx * LIGHT[0] + p.ny * LIGHT[1] + nz * LIGHT[2]) * 0.62 + 0.36 + (p.b.bias ?? 0) + (r() - 0.5) * (o.noise ?? 0.06);
      // 下沿、右沿：压一档
      if (!inside(x + 0.5, y + 1.5) || !inside(x + 1.5, y + 0.5)) v -= 0.22;
      if (o.under && o.clipY !== undefined && y > o.clipY - o.under) v -= 0.3;
      const lv = Math.max(0, Math.min(k - 1, Math.floor(v * k + bayer(x, y))));
      px.set(x, y, ramp[lv]);
    }
}

/* ── 树 ───────────────────────────────────── */

const TREE_KINDS = ['round', 'tall', 'weep', 'pine', 'bare', 'blossom', 'tuft'];

function tree(seed: number, kind?: string) {
  const r = rng(seed);
  kind = kind && TREE_KINDS.includes(kind) ? kind : r.pick(TREE_KINDS);
  const H = r.int(80, 128);
  const W = Math.round(H * (kind === 'tall' ? 0.42 : kind === 'pine' ? 0.55 : 0.85)) & ~1;
  // 工作格放宽，画完再裁到内容；树冠不会被画布顶切平
  const px = new Px(W * 3, Math.round(H * 1.8));
  const ox = W, oy = Math.round(H * 0.8);
  const crown: Ramp = kind === 'blossom' ? RAMP.pink : kind === 'pine' ? r.pick([RAMP.sage, RAMP.lilac, RAMP.blue])
    : r.pick([RAMP.pink, RAMP.lilac, RAMP.sage, RAMP.blue, RAMP.mist, RAMP.pink]);
  const cx = ox + W / 2, base = oy + H - 1;
  const tips: [number, number][] = [];
  const done = () => px.crop(cx, base).texture();

  const grow = (x: number, y: number, a: number, len: number, w: number, d: number, spread: number) => {
    const x2 = x + Math.sin(a) * len, y2 = y - Math.cos(a) * len;
    px.line(x, y, x2, y2, w, RAMP.trunk);
    if (d === 0) { tips.push([x2, y2]); return; }
    const n = r() < 0.35 ? 3 : 2;
    for (let i = 0; i < n; i++) {
      const t = i / (n - 1) - 0.5;
      grow(x2, y2, a + t * spread * 2 + r.range(-0.18, 0.18), len * r.range(0.62, 0.8), Math.max(1, w * 0.62), d - 1, spread);
    }
  };

  if (kind === 'pine') {
    px.line(cx, base, cx, oy + H * 0.08, 3, RAMP.trunk);
    const tiers = r.int(4, 6);
    for (let i = 0; i < tiers; i++) {
      const t = i / tiers;
      const top = oy + H * (0.04 + t * 0.62), bot = top + H * r.range(0.2, 0.28);
      const half = W * (0.16 + t * 0.32);
      for (let y = Math.floor(top); y < bot && y < base - 6; y++) {
        const s = (y - top) / (bot - top);
        const hw = half * s + (y % 3 === 0 ? 1 : 0);
        for (let x = Math.floor(cx - hw); x <= cx + hw; x++) {
          const v = 0.62 - ((x - cx) / (half + 1)) * 0.45 - s * 0.25 + (bot - y < 2 ? -0.3 : 0);
          px.set(x, y, crown[Math.max(0, Math.min(crown.length - 1, Math.floor(v * crown.length + bayer(x, y))))]);
        }
      }
    }
    return done();
  }

  if (kind === 'bare') {
    grow(cx, base, r.range(-0.1, 0.1), H * 0.3, 4, 5, 0.42);
    for (const [x, y] of tips) if (r() < 0.6) px.set(x, y, r.pick([RAMP.pink[3], RAMP.pink[2], '#fbf9f7']));
    return done();
  }

  if (kind === 'tall') {
    grow(cx, base, 0, H * 0.3, 3, 2, 0.16);
    const blobs: Blob[] = [];
    for (let y = oy + H * 0.7; y > oy + H * 0.06; y -= r.range(5, 9)) {
      const t = (oy + H * 0.7 - y) / (H * 0.64);
      const rr = W * 0.34 * Math.sin(Math.PI * (0.15 + t * 0.8)) + 2;
      blobs.push({ x: cx + r.range(-2, 2), y, rx: rr, ry: rr * 1.2, bias: r.range(-0.06, 0.06) });
    }
    shade(px, blobs, crown, { seed });
    return done();
  }

  grow(cx, base, r.range(-0.08, 0.08), H * (kind === 'tuft' ? 0.36 : 0.42), r.int(3, 5), 3, kind === 'tuft' ? 0.55 : 0.45);
  const blobs: Blob[] = [];
  const unit = H * (kind === 'tuft' ? 0.08 : 0.12);
  for (const [x, y] of tips) {
    const n = kind === 'tuft' ? 1 : r.int(2, 3);
    for (let i = 0; i < n; i++) {
      const rr = unit * r.range(0.8, 1.3);
      blobs.push({ x: x + r.range(-3, 3), y: y + r.range(-3, 2), rx: rr, ry: rr * 0.9, bias: r.range(-0.08, 0.08) });
    }
  }
  if (kind !== 'tuft') {
    const mx = tips.reduce((s, t) => s + t[0], 0) / tips.length, my = tips.reduce((s, t) => s + t[1], 0) / tips.length;
    blobs.push({ x: mx, y: my + unit * 0.6, rx: unit * 2.0, ry: unit * 1.5, bias: -0.08 });
    for (let i = 0; i < 4; i++) {
      const [tx, ty] = r.pick(tips);
      blobs.push({ x: (tx + mx) / 2 + r.range(-4, 4), y: (ty + my) / 2 + r.range(-4, 4), rx: unit * 1.3, ry: unit * 1.1, bias: r.range(-0.1, 0.02) });
    }
  }
  shade(px, blobs, crown, { seed });
  if (kind === 'weep') {
    const n = r.int(7, 12);
    for (let i = 0; i < n; i++) {
      const b = r.pick(blobs);
      let x = b.x + r.range(-b.rx, b.rx) * 0.8, y = b.y + b.ry * 0.6;
      const len = r.range(10, H * 0.4), drift = r.range(-0.25, 0.25);
      for (let j = 0; j < len && y < base - 4; j += 1.5) {
        x += drift * 0.5;
        y += 1.5;
        px.set(x, y, crown[j > len * 0.6 ? 1 : 2]);
        if (j % 4 < 1.5) px.set(x + 1, y, crown[1]);
      }
    }
  }
  if (kind === 'blossom') {
    for (let i = 0; i < blobs.length * 4; i++) {
      const b = r.pick(blobs);
      const a = r.range(0, Math.PI * 2), d = r.range(0, b.rx * 0.9);
      const x = b.x + Math.cos(a) * d, y = b.y + Math.sin(a) * d * 0.9;
      if (px.get(Math.round(x), Math.round(y))) px.set(x, y, r() < 0.5 ? '#fbf9f7' : RAMP.pink[3]);
    }
  }
  return done();
}

/* ── 云 ───────────────────────────────────── */

const CLOUD_KINDS = ['heap', 'flat', 'wisp', 'puff'];

function cloud(seed: number, kind?: string) {
  const r = rng(seed);
  kind = kind && CLOUD_KINDS.includes(kind) ? kind : r.pick(CLOUD_KINDS);
  const ramp = r() < 0.7 ? RAMP.mist : r.pick([RAMP.blue, ['#a8798c', '#d9aab5', '#f3d6d6', '#fbf9f7']]);
  if (kind === 'wisp') {
    const W = r.int(96, 176), H = 18;
    const px = new Px(W, H);
    const n = r.int(3, 5);
    for (let i = 0; i < n; i++) {
      const y = r.int(2, H - 3), x0 = r.range(0, W * 0.4), len = r.range(W * 0.35, W * 0.9), th = r.int(1, 3);
      for (let x = Math.floor(x0); x < Math.min(W, x0 + len); x++) {
        const t = (x - x0) / len;
        const fade = Math.sin(Math.PI * t);
        for (let k = 0; k < th; k++) {
          if (fade + bayer(x, y + k) * 0.9 < 0.35) continue;
          px.set(x, y + k + Math.round(Math.sin(x * 0.07 + i) * 1.2), ramp[k === 0 ? 3 : 2]);
        }
      }
    }
    return px.texture();
  }
  if (kind === 'flat') {
    const W = r.int(128, 200), H = r.int(22, 30);
    const px = new Px(W, H);
    const blobs: Blob[] = [];
    const layers = r.int(2, 3);
    for (let l = 0; l < layers; l++) {
      const y = H - 4 - l * 6, x0 = r.range(W * 0.05, W * 0.25), x1 = r.range(W * 0.7, W * 0.95);
      for (let x = x0; x < x1; x += r.range(10, 18))
        blobs.push({ x, y: y - r.range(0, 2), rx: r.range(12, 22), ry: r.range(3, 5), bias: l * 0.06 });
    }
    shade(px, blobs, ramp, { clipY: H - 2, under: 2, seed });
    return px.texture();
  }
  const small = kind === 'puff';
  const W = small ? r.int(36, 56) : r.int(96, 160), H = small ? r.int(24, 36) : r.int(44, 64);
  const px = new Px(W, H);
  const blobs: Blob[] = [];
  const n = small ? r.int(3, 5) : r.int(6, 10);
  const baseY = small ? H * 0.68 : H - 3;
  for (let i = 0; i < n; i++) {
    const t = (i + 0.5) / n;
    const env = Math.pow(Math.sin(Math.PI * (0.08 + t * 0.84)), 0.7);
    const rr = (small ? H * 0.42 : H * 0.48) * env * r.range(0.7, 1.05) + 3;
    blobs.push({ x: W * (0.1 + t * 0.8) + r.range(-3, 3), y: baseY - rr * r.range(0.35, 0.6), rx: rr * 1.1, ry: rr, bias: r.range(-0.05, 0.05) });
  }
  for (let i = 0; i < (small ? 1 : r.int(2, 4)); i++) {
    const b = r.pick(blobs.slice(1, -1).length ? blobs.slice(1, -1) : blobs);
    blobs.push({ x: b.x + r.range(-6, 6), y: b.y - b.ry * 0.7, rx: b.rx * 0.7, ry: b.ry * 0.7, bias: 0.06 });
  }
  shade(px, blobs, ramp, { clipY: small ? undefined : baseY, under: small ? 0 : 3, seed });
  return px.texture();
}

/* ── 星 ───────────────────────────────────── */

const STAR_KINDS = ['dot', 'glow', 'diamond', 'cluster', 'ring'];

function star(seed: number, kind?: string) {
  const r = rng(seed);
  kind = kind && STAR_KINDS.includes(kind) ? kind : r.pick(STAR_KINDS);
  const core = r.pick(['#fbf9f7', '#ead7a0', '#f3d6d6', '#c3d1e6']);
  const halo = r.pick(['#f3d6d6', '#c3d1e6', '#ead7a0']);
  const px = new Px(15, 15);
  const c = 7;
  if (kind === 'dot') {
    const s = r.int(1, 2);
    for (let y = 0; y < s + 1; y++) for (let x = 0; x < s + 1; x++) px.set(c - 1 + x, c - 1 + y, core);
  } else if (kind === 'glow') {
    for (let y = -4; y <= 4; y++)
      for (let x = -4; x <= 4; x++) {
        const d = Math.hypot(x, y);
        if (d < 1.6) px.set(c + x, c + y, core);
        else if (d < 4.2 && 1 - d / 4.2 + bayer(x + 8, y + 8) * 0.8 > 0.35) px.set(c + x, c + y, halo);
      }
  } else if (kind === 'diamond') {
    const s = r.int(2, 4);
    for (let y = -s; y <= s; y++) for (let x = -s; x <= s; x++) if (Math.abs(x) + Math.abs(y) <= s) px.set(c + x, c + y, Math.abs(x) + Math.abs(y) < s - 1 ? core : halo);
  } else if (kind === 'ring') {
    const rr = r.range(3, 5.5);
    for (let a = 0; a < Math.PI * 2; a += 0.08) px.set(c + Math.cos(a) * rr, c + Math.sin(a) * rr, halo);
    px.set(c, c, core);
  } else {
    const n = r.int(3, 6);
    for (let i = 0; i < n; i++) {
      const x = r.int(1, 13), y = r.int(1, 13);
      px.set(x, y, core);
      if (r() < 0.35) px.set(x + 1, y, core), px.set(x, y + 1, core), px.set(x + 1, y + 1, core);
    }
  }
  return px.texture();
}

/* ── 草、灌木 ─────────────────────────────── */

const GRASS_KINDS = ['clump', 'reed', 'flowered'];

function grass(seed: number, kind?: string) {
  const r = rng(seed);
  kind = kind && GRASS_KINDS.includes(kind) ? kind : r.pick(GRASS_KINDS);
  const tall = kind === 'reed';
  const W = tall ? r.int(10, 18) : r.int(12, 24), H = tall ? r.int(36, 60) : r.int(8, 20);
  const px = new Px(W, H);
  const ramp = r() < 0.6 ? RAMP.sage : RAMP.lilac;
  const n = tall ? r.int(3, 5) : r.int(5, 11);
  for (let i = 0; i < n; i++) {
    let x = r.range(2, W - 3);
    const h = r.range(H * 0.45, H - 1), bend = r.range(-0.35, 0.35), tone = ramp[r.int(1, ramp.length - 1)];
    for (let y = H - 1, j = 0; y > H - 1 - h; y--, j++) {
      x += bend * (j / h) * 1.2;
      px.set(x, y, j < 2 ? ramp[1] : tone);
    }
    if (tall && r() < 0.8) {
      const top = H - 1 - h;
      for (let k = 2; k < 9; k++) px.set(x, top + k, k < 4 ? RAMP.rose[2] : RAMP.rose[1]), px.set(x + 1, top + k, RAMP.rose[0]);
    }
    if (kind === 'flowered' && r() < 0.5) px.set(x, H - 1 - h, r.pick(['#fbf9f7', '#f3d6d6', '#ead7a0']));
  }
  return px.texture();
}

function bush(seed: number) {
  const r = rng(seed);
  const W = r.int(28, 56), H = r.int(16, 30);
  const px = new Px(W, H);
  const ramp = r.pick([RAMP.sage, RAMP.lilac, RAMP.pink, RAMP.blue]);
  const blobs: Blob[] = [];
  const n = r.int(3, 6);
  for (let i = 0; i < n; i++) {
    const t = (i + 0.5) / n;
    const rr = H * 0.55 * Math.pow(Math.sin(Math.PI * (0.1 + t * 0.8)), 0.6) + 2;
    blobs.push({ x: W * (0.12 + t * 0.76), y: H - rr * 0.6, rx: rr, ry: rr * 0.9, bias: r.range(-0.07, 0.07) });
  }
  shade(px, blobs, ramp, { clipY: H - 1, under: 1, seed });
  if (r() < 0.5) {
    const dot = r.pick(['#fbf9f7', '#f3d6d6', '#ead7a0']);
    for (let i = 0; i < W / 3; i++) {
      const x = r.int(2, W - 3), y = r.int(2, H - 4);
      if (px.get(x, y)) px.set(x, y, dot);
    }
  }
  return px.texture();
}

/* ── 花 ───────────────────────────────────── */

const FLOWER_KINDS = ['cup', 'star', 'bell', 'umbel', 'puff'];

function flower(seed: number, kind?: string) {
  const r = rng(seed);
  kind = kind && FLOWER_KINDS.includes(kind) ? kind : r.pick(FLOWER_KINDS);
  const H = r.int(28, 64), W = Math.max(20, Math.round(H * 0.55)) & ~1;
  const px = new Px(W * 3, H * 2);
  const oy = H, base = oy + H - 1;
  const head = r.pick([RAMP.pink, RAMP.mist, RAMP.blue, RAMP.lilac, ['#a8798c', '#ead7a0', '#fbf9f7']]);
  const cx = W * 1.5;
  // 茎：一条带点犹豫的曲线
  const top = oy + (kind === 'bell' ? H * 0.3 : H * 0.36);
  const sway = r.range(-W * 0.15, W * 0.15);
  let hx = cx, hy = top;
  const steps = Math.ceil(base - top);
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const x = cx + sway * Math.sin(Math.PI * t * 0.9) * (1 - t);
    const y = base - t * (base - top);
    px.set(x, y, RAMP.sage[1]);
    if (H > 50) px.set(x + 1, y, RAMP.sage[0]);
    hx = x; hy = y;
  }
  // 叶
  for (let i = 0; i < r.int(1, 2); i++) {
    const y = oy + H * r.range(0.62, 0.86), dir = i % 2 ? 1 : -1, L = r.range(5, W * 0.4);
    shade(px, [
      { x: cx + dir * L * 0.35, y: y + 1, rx: L * 0.4, ry: 2.4 },
      { x: cx + dir * L * 0.8, y: y - L * 0.25, rx: L * 0.32, ry: 2.0, bias: 0.06 },
    ], RAMP.sage, { seed: seed + i });
  }
  if (kind === 'cup') {
    const s = r.range(H * 0.11, H * 0.16);
    shade(px, [
      { x: hx, y: hy - s * 0.6, rx: s * 0.5, ry: s * 1.1, bias: 0.08 },
      { x: hx - s * 0.55, y: hy - s * 0.4, rx: s * 0.42, ry: s * 0.95, bias: -0.04 },
      { x: hx + s * 0.55, y: hy - s * 0.4, rx: s * 0.42, ry: s * 0.95, bias: -0.1 },
    ], head, { seed });
  } else if (kind === 'star') {
    const k = r.int(5, 8), s = r.range(H * 0.1, H * 0.15);
    const blobs: Blob[] = [];
    for (let i = 0; i < k; i++) {
      const a = (i / k) * Math.PI * 2 + r.range(-0.1, 0.1);
      blobs.push({ x: hx + Math.cos(a) * s * 0.7, y: hy - s * 0.3 + Math.sin(a) * s * 0.55, rx: s * 0.42, ry: s * 0.42, bias: r.range(-0.06, 0.06) });
    }
    shade(px, blobs, head, { seed });
    shade(px, [{ x: hx, y: hy - s * 0.3, rx: s * 0.28, ry: s * 0.28 }], RAMP.gold, { seed: seed + 3 });
  } else if (kind === 'bell') {
    // 茎在顶上弯过去，花垂下来
    const dir = r() < 0.5 ? -1 : 1, s = r.range(H * 0.07, H * 0.11);
    let x = hx, y = hy;
    for (let i = 0; i < s * 2.5; i++) { x += dir * 0.7; y += i > s * 1.2 ? 0.7 : -0.25; px.set(x, y, RAMP.sage[1]); }
    shade(px, [{ x, y: y + s * 0.9, rx: s * 0.75, ry: s, bias: 0.04 }], head, { seed });
    for (let i = -1; i <= 1; i++) px.set(x + i * s * 0.55, y + s * 1.85, head[1]);
  } else if (kind === 'umbel') {
    const s = r.range(H * 0.1, H * 0.15);
    for (let i = 0; i < s * 6; i++) {
      const a = r.range(Math.PI, Math.PI * 2), d = r.range(0, s);
      const x = hx + Math.cos(a) * d * 1.1, y = hy - s * 0.2 + Math.sin(a) * d;
      px.line(hx, hy, x, y, 1, [RAMP.sage[2], RAMP.sage[2], RAMP.sage[2]]);
      px.set(x, y, head[r.int(2, head.length - 1)]);
    }
  } else {
    const s = r.range(H * 0.1, H * 0.15);
    for (let i = 0; i < 26; i++) {
      const a = (i / 26) * Math.PI * 2, d = s * r.range(0.85, 1.05);
      px.line(hx, hy - s, hx + Math.cos(a) * d, hy - s + Math.sin(a) * d, 1, [RAMP.mist[2], RAMP.mist[2], RAMP.mist[2]]);
      px.set(hx + Math.cos(a) * d, hy - s + Math.sin(a) * d, '#fbf9f7');
    }
  }
  return px.crop(cx, base).texture();
}

/* ── 名字 → 图 ─────────────────────────────── */

const FAMILIES: Record<string, (seed: number, kind?: string) => THREE.Texture> = {
  tree,
  cloud,
  star,
  grass,
  bush: (s) => bush(s),
  flower,
};

/** 族[.变体][:种子] → 图；不是程序化的名字返回 null */
export function procSprite(name: string): THREE.Texture | null {
  const m = /^([a-z]+)(?:\.([a-z]+))?(?::(\d+))?$/.exec(name);
  if (!m || !FAMILIES[m[1]]) return null;
  return FAMILIES[m[1]](Number(m[3] ?? 1), m[2]);
}

/** 各族的变体名（陈列与文档用） */
export const PROC_KINDS = { tree: TREE_KINDS, cloud: CLOUD_KINDS, star: STAR_KINDS, grass: GRASS_KINDS, bush: [], flower: FLOWER_KINDS };
