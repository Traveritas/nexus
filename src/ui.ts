/* UI 的地基：一张盖在画面上的低分辨率画布，一个 UI 像素 ＝ 2 个屏幕像素（等于解析度场的 1 级格子）。
   只许用色板里的颜色；字是 12px 像素字，画完按透明度一刀切，不留半透的边。
   面板都是「剪纸」：一张不太齐的纸、一圈墨线、底下压一格影子，翻过来是空白的纸。 */
import { PALETTE } from './palette';

/** 一个 UI 像素占几个屏幕像素 */
export const UI_SCALE = 2;

/** UI 用到的色板色（都在 PALETTE 里） */
export const C = {
  ink: PALETTE[1],
  inkDeep: PALETTE[0],
  thread: PALETTE[2],
  shadow: PALETTE[3],
  paper: PALETTE[7],
  back: PALETTE[6],
  fibre: PALETTE[5],
};

const FONT = 'NexusPixel';
const FONT_PX = 12;

export async function loadUiFont() {
  try {
    const f = new FontFace(FONT, `url(${import.meta.env.BASE_URL}fonts/fusion-pixel-12.woff2)`);
    document.fonts.add(await f.load());
  } catch (err) {
    console.warn('[nexus] 像素字没载入，退回等宽字', err);
  }
}

/** 由字符串得到的可复现随机数 */
export function rng(seed: string | number) {
  let h = typeof seed === 'number' ? seed | 0 : 2166136261;
  if (typeof seed === 'string') for (let i = 0; i < seed.length; i++) h = Math.imul(h ^ seed.charCodeAt(i), 16777619);
  return () => {
    h = Math.imul(h ^ (h >>> 15), 2246822507);
    h = Math.imul(h ^ (h >>> 13), 3266489909);
    h ^= h >>> 16;
    return (h >>> 0) / 4294967296;
  };
}

function canvas(w: number, h: number) {
  const c = document.createElement('canvas');
  c.width = Math.max(1, w);
  c.height = Math.max(1, h);
  const g = c.getContext('2d')!;
  g.imageSmoothingEnabled = false;
  return { c, g };
}

// ── 字 ──
const glyphCache = new Map<string, HTMLCanvasElement>();

/* 直接按 12px 画，字形的格子落不到整像素上，一刀切会切坏笔画。
   所以按 8 倍画大，再在每个字像素的中心取样；大图里格子的相位（ox, oy）开头量一次 */
const UP = 8;
let phase: [number, number] | null = null;

function big(s: string) {
  const probe = canvas(1, 1).g;
  probe.font = `${FONT_PX * UP}px ${FONT}, monospace`;
  const cols = Math.ceil(probe.measureText(s).width / UP) + 1;
  const { c, g } = canvas(cols * UP, (FONT_PX + 3) * UP);
  g.font = probe.font;
  g.textBaseline = 'alphabetic';
  g.fillStyle = '#000';
  g.fillText(s, 0, FONT_PX * UP);
  return { cols, a: g.getImageData(0, 0, c.width, c.height) };
}

/** 找格子的相位：取样点离字的边缘最远（覆盖率最接近 0 或 1）的那组偏移 */
function findPhase(): [number, number] {
  const { a } = big('永国翻杯Ag');
  const W = a.width;
  let best: [number, number] = [0, 0];
  let bestScore = -1;
  for (let oy = 0; oy < UP; oy++)
    for (let ox = 0; ox < UP; ox++) {
      let score = 0;
      for (let y = oy; y < a.height; y += UP)
        for (let x = ox; x < W; x += UP) {
          // 这一格的覆盖率
          let sum = 0;
          for (let j = 0; j < UP && y + j < a.height; j++)
            for (let i = 0; i < UP && x + i < W; i++) sum += a.data[((y + j) * W + x + i) * 4 + 3];
          const cov = sum / (UP * UP * 255);
          score += Math.abs(cov - 0.5);
        }
      if (score > bestScore) {
        bestScore = score;
        best = [ox, oy];
      }
    }
  return best;
}

/** 一行像素字：透明底、单色，没有半透的边。高 = 字号 + 2（留给下伸部） */
export function text(s: string, color = C.ink): HTMLCanvasElement {
  const key = `${color}|${s}`;
  const hit = glyphCache.get(key);
  if (hit) return hit;
  phase ??= findPhase();
  const [ox, oy] = phase;
  const { cols, a } = big(s);
  const rows = FONT_PX + 2;
  const { c, g } = canvas(cols, rows);
  const img = g.createImageData(cols, rows);
  const [r, gg, b] = hex(color);
  let right = 0;
  for (let j = 0; j < rows; j++)
    for (let i = 0; i < cols; i++) {
      const x = ox + i * UP + UP / 2;
      const y = oy + j * UP + UP / 2;
      if (x >= a.width || y >= a.height || a.data[(y * a.width + x) * 4 + 3] < 128) continue;
      const k = (j * cols + i) * 4;
      img.data.set([r, gg, b, 255], k);
      right = Math.max(right, i + 1);
    }
  // 去掉右边多留的空列
  const out = canvas(Math.max(1, right), rows);
  g.putImageData(img, 0, 0);
  out.g.drawImage(c, 0, 0);
  glyphCache.set(key, out.c);
  return out.c;
}

/** 一张图上有墨的行：[最上, 最下]（含）；空图返回 [0, -1] */
export function inkRows(c: HTMLCanvasElement): [number, number] {
  const d = c.getContext('2d')!.getImageData(0, 0, c.width, c.height).data;
  let top = c.height;
  let bot = -1;
  for (let y = 0; y < c.height; y++)
    for (let x = 0; x < c.width; x++)
      if (d[(y * c.width + x) * 4 + 3]) {
        top = Math.min(top, y);
        bot = y;
        break;
      }
  return bot < 0 ? [0, -1] : [top, bot];
}

function hex(h: string): [number, number, number] {
  const n = parseInt(h.slice(1), 16);
  return [n >> 16, (n >> 8) & 255, n & 255];
}

// ── 剪纸 ──
/** 剪纸的形状：w×h 的掩码，四边按种子各有一两段缺口（缩进 1 格），四角剪掉一格 */
export function paperMask(w: number, h: number, seed: string | number): Uint8Array {
  const r = rng(seed);
  const m = new Uint8Array(w * h).fill(1);
  const nick = (len: number) => {
    // 一条边上每一格的缩进：大多为 0，偶尔一段 2–5 格缩进 1
    const off = new Uint8Array(len);
    for (let i = 2; i < len - 2; ) {
      if (r() < 0.07) {
        const run = 2 + Math.floor(r() * 4);
        for (let k = 0; k < run && i < len - 2; k++) off[i++] = 1;
        i += 3;
      } else i++;
    }
    return off;
  };
  const top = nick(w);
  const bot = nick(w);
  const lef = nick(h);
  const rig = nick(h);
  for (let x = 0; x < w; x++) {
    if (top[x]) m[x] = 0;
    if (bot[x]) m[(h - 1) * w + x] = 0;
  }
  for (let y = 0; y < h; y++) {
    if (lef[y]) m[y * w] = 0;
    if (rig[y]) m[y * w + w - 1] = 0;
  }
  m[0] = m[w - 1] = m[(h - 1) * w] = m[h * w - 1] = 0;
  return m;
}

export interface PaperStyle {
  fill?: string;
  line?: string;
  /** 纸纤维：底色上零星的浅点 */
  fibre?: boolean;
}

/** 在 g 上 (x, y) 处画一张剪纸（墨线在形状内侧一圈）。影子另画：paperShadow */
export function paper(g: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, mask: Uint8Array, st: PaperStyle = {}) {
  const fill = st.fill ?? C.paper;
  const line = st.line ?? C.ink;
  const inside = (i: number, j: number) => i >= 0 && j >= 0 && i < w && j < h && m(i, j);
  const m = (i: number, j: number) => mask[j * w + i] === 1;
  const r = rng(w * 131 + h);
  for (let j = 0; j < h; j++)
    for (let i = 0; i < w; i++) {
      if (!m(i, j)) continue;
      const edge = !inside(i - 1, j) || !inside(i + 1, j) || !inside(i, j - 1) || !inside(i, j + 1);
      g.fillStyle = edge ? line : st.fibre && r() < 0.035 ? C.fibre : fill;
      g.fillRect(x + i, y + j, 1, 1);
    }
}

export function paperShadow(g: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, mask: Uint8Array, color = C.shadow) {
  g.fillStyle = color;
  for (let j = 0; j < h; j++)
    for (let i = 0; i < w; i++) if (mask[j * w + i]) g.fillRect(x + i, y + j, 1, 1);
}

/** 一像素宽的线（Bresenham），两端都画 */
export function line(g: CanvasRenderingContext2D, x0: number, y0: number, x1: number, y1: number, color: string) {
  g.fillStyle = color;
  let dx = Math.abs(x1 - x0);
  let dy = -Math.abs(y1 - y0);
  const sx = x0 < x1 ? 1 : -1;
  const sy = y0 < y1 ? 1 : -1;
  let err = dx + dy;
  for (let n = 0; n < 4096; n++) {
    g.fillRect(x0, y0, 1, 1);
    if (x0 === x1 && y0 === y1) break;
    const e2 = 2 * err;
    if (e2 >= dy) {
      err += dy;
      x0 += sx;
    }
    if (e2 <= dx) {
      err += dx;
      y0 += sy;
    }
  }
}

/** 屏幕上那张 UI 画布。每帧 clear 之后各部件往 g 上画 */
export class Ui {
  readonly el: HTMLCanvasElement;
  readonly g: CanvasRenderingContext2D;
  w = 0;
  h = 0;

  constructor(el: HTMLCanvasElement) {
    this.el = el;
    this.g = el.getContext('2d')!;
  }

  /** 传入舞台画布的尺寸（屏幕像素，8 的倍数） */
  setSize(w: number, h: number) {
    this.w = w / UI_SCALE;
    this.h = h / UI_SCALE;
    this.el.width = this.w;
    this.el.height = this.h;
    this.el.style.width = `${w}px`;
    this.el.style.height = `${h}px`;
    this.g.imageSmoothingEnabled = false;
  }

  clear() {
    this.g.clearRect(0, 0, this.w, this.h);
  }
}

/** 离屏画一小块（部件先画在这里，再贴到 UI 上，可以压扁、翻面） */
export function scratch(w: number, h: number) {
  return canvas(w, h);
}
