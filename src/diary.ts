/* 日记本（Tab）：一本真的书，画在自己的舞台上（见 stage.ts）。
   书摊平、停稳时，页面一个纹素正好对一个 UI 像素，所以页上的像素字是锐利的；翻开、翻页时是真的 3D，带着像素的颗粒。
   着色只分三档明暗，然后落回色板。打开时世界「犯困」（见 pipeline 的 drowse），晶体照旧清醒。
   指针锁着时用一支像素小箭头操作；没锁时跟着真鼠标。Tab 打开、Tab 合上。
   书顶上伸出几张索引贴（记录 · 拾得 · 设置），点哪张翻到哪一节；没有目录页。 */
import * as THREE from 'three';
import { PALETTE } from './palette';
import { Stage, box, canvasTex, clamp01, ease, mat, plane, setMap, solid } from './stage';
import { itemDef } from './items/item';
import type { Owned } from './items/system';
import { dreamt, edges, isReality, sites, worldName } from './worlds';
import { C, UI_SCALE, inkRows, paper, paperMask, scratch, text, type Ui } from './ui';
import { andMore, gotOn, l, lang, night as nightTitle, setLang, t, type Key, type Lang } from './i18n';

/** 一页的尺寸（UI 像素 ＝ 书场景里的单位） */
const PW = 148;
const PH = 196;
const COVER_T = 3;
const STACK_T = 4;
/** 封面比书页多出来的一圈 */
const OVER = 5;
/** 书页比纸叠的顶面高一点点，免得两者打架（这点高度对像素对齐的影响远小于一格） */
const PAGE_LIFT = 0.05;
/** 横线：第一条的位置与行距 */
const ROW0 = 36;
const ROW = 14;
const OPEN_TIME = 0.8;
const CLOSE_TIME = 0.5;
const TURN_TIME = 0.55;
const SENS_STEPS = [0.5, 0.75, 1, 1.25, 1.5, 2];
const SETTINGS_KEY = 'nexus:settings';
const RES_STEPS: Settings['res'][] = ['auto', 'full', 'half', 'quarter', 'eighth', 'sixteenth'];
const RES_LABEL: Record<Settings['res'], Key> = { auto: 'resAuto', full: 'resFull', half: 'resHalf', quarter: 'resQuarter', eighth: 'resEighth', sixteenth: 'resSixteenth' };
/** 语言一栏写的是那种语言自己的名字 */
const LANG_LABEL: Record<Lang, string> = { zh: '中文', en: 'English' };
const NIGHTS_KEY = 'nexus:nights';
/** 索引贴露出书页上沿的高度（封面多出来的一圈 OVER 也算在里面） */
const TAB_H = 19;

const P = (i: number) => PALETTE[i];

export interface Settings {
  sens: number;
  hud: boolean;
  /** 世界的渲染分辨率：自动（按屏幕大小）· 精细（全分辨率）· 流畅（半）· 极速（四分之一）；
      再往下是玩笑：马赛克（八分之一）· 印象派（十六分之一） */
  res: 'auto' | 'full' | 'half' | 'quarter' | 'eighth' | 'sixteenth';
  /** 没存过时 i18n 按浏览器的语言挑 */
  lang: Lang;
}

export function loadSettings(): Settings {
  const s: Settings = { sens: 1, hud: true, res: 'auto', lang };
  try {
    Object.assign(s, JSON.parse(localStorage.getItem(SETTINGS_KEY) ?? '{}'));
  } catch {
    /* 用默认 */
  }
  return s;
}

function saveSettings(s: Settings) {
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(s));
  } catch {
    /* 存不了就算了 */
  }
}

/** 第几夜：每次新开一个标签页算一夜 */
export function night(): number {
  try {
    let n = Number(localStorage.getItem(NIGHTS_KEY) ?? 0);
    if (!sessionStorage.getItem(NIGHTS_KEY)) {
      n += 1;
      localStorage.setItem(NIGHTS_KEY, String(n));
      sessionStorage.setItem(NIGHTS_KEY, '1');
    }
    return Math.max(1, n);
  } catch {
    return 1;
  }
}

// ── 页面 ──
interface Region {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

interface PageCtx {
  hover: string | null;
  settings: Settings;
  world: string;
  visited: string[];
  night: number;
  owned: Owned[];
  held: string | null;
  /** 此刻在现实里（醒着）：身上的东西看不了，也没有「醒来」 */
  awake: boolean;
  /** 翻在哪一节（索引贴用） */
  spread: Spread;
  paths: number;
  sites: number;
}

type Draw = (g: CanvasRenderingContext2D, c: PageCtx) => Region[];

class Page {
  readonly canvas: HTMLCanvasElement;
  readonly g: CanvasRenderingContext2D;
  readonly tex: THREE.CanvasTexture;
  regions: Region[] = [];

  /** side：左页、右页，或 T ＝ 书顶上那一排索引贴（透明底，不画横线） */
  constructor(
    readonly side: 'L' | 'R' | 'T',
    readonly draw: Draw,
    w = PW,
    h = PH,
  ) {
    const s = scratch(w, h);
    this.canvas = s.c;
    this.g = s.g;
    this.tex = canvasTex(this.canvas);
  }

  redraw(c: PageCtx) {
    if (this.side === 'T') this.g.clearRect(0, 0, this.canvas.width, this.canvas.height);
    else pageBase(this.g, this.side);
    this.regions = this.draw(this.g, c);
    this.tex.needsUpdate = true;
  }
}

let cjk: [number, number] | null = null;
/** 第 k 条横线上写字时，字图的 y */
function rowY(k: number) {
  cjk ??= inkRows(text('国'));
  return ROW0 + k * ROW - 2 - cjk[1];
}

function pageBase(g: CanvasRenderingContext2D, side: 'L' | 'R') {
  g.fillStyle = C.paper;
  g.fillRect(0, 0, PW, PH);
  // 纸纤维
  g.fillStyle = C.fibre;
  let h = side === 'L' ? 7 : 13;
  for (let i = 0; i < 90; i++) {
    h = (h * 1103515245 + 12345) & 0x7fffffff;
    g.fillRect(h % PW, (h >> 8) % PH, 1, 1);
  }
  g.fillStyle = P(13);
  for (let y = ROW0; y < PH - 12; y += ROW) g.fillRect(8, y, PW - 16, 1);
  // 页边的竖线
  g.fillStyle = P(10);
  g.fillRect(side === 'L' ? 22 : 18, 10, 1, PH - 20);
  // 靠书脊的一侧：压出一道折
  const gx = side === 'L' ? PW - 3 : 0;
  g.fillStyle = C.back;
  g.fillRect(gx, 0, 3, PH);
  g.fillStyle = P(4);
  g.fillRect(side === 'L' ? PW - 1 : 0, 0, 1, PH);
}

function write(g: CanvasRenderingContext2D, s: string, x: number, k: number, color = C.ink) {
  const t = text(s, color);
  g.drawImage(t, x, rowY(k));
  return t.width;
}

/** 可以点的一行：悬停时字变成玫瑰色，左边一个小三角，下面一道波浪线 */
function item(g: CanvasRenderingContext2D, c: PageCtx, id: string, s: string, x: number, k: number): Region {
  const on = c.hover === id;
  const w = write(g, s, x, k, on ? P(8) : C.ink);
  if (on) {
    const y = ROW0 + k * ROW;
    g.fillStyle = P(8);
    // 朝右的小三角，5 格高
    const tx = x - 6;
    const ty = y - 8;
    for (let j = 0; j < 5; j++) g.fillRect(tx, ty + j, j <= 2 ? j + 1 : 5 - j, 1);
    g.fillStyle = P(9);
    for (let i = 0; i < w; i++) g.fillRect(x + i, y + ((i >> 1) & 1), 1, 1);
  }
  return { id, x: x - 8, y: ROW0 + (k - 1) * ROW + 1, w: w + 10, h: ROW };
}

function title(g: CanvasRenderingContext2D, s: string, x: number) {
  const w = write(g, s, x, 0);
  g.fillStyle = C.ink;
  g.fillRect(x, ROW0 + 1, w, 1);
}

/** 右对齐写在页边线以内 */
const RIGHT = PW - 14;
const rightX = (s: string) => RIGHT - text(s).width;

/** 页脚的小字（右下角，淡一档） */
function foot(g: CanvasRenderingContext2D, s: string) {
  const f = text(s, P(3));
  g.drawImage(f, PW - f.width - 10, PH - 14);
}

/** 一行数：左边名目，右边数目 */
function stat(g: CanvasRenderingContext2D, label: string, n: number, unit: string, k: number) {
  write(g, label, 30, k);
  const v = lang === 'zh' ? `${n} ${unit}` : String(n);
  write(g, v, rightX(v), k, P(2));
}

// ── 记录：这些夜里的一个总账 ──
const recordLeft: Draw = (g, c) => {
  title(g, nightTitle(c.night), 30);
  write(g, c.awake ? t('awakeNow') : `${t('now')} · ${worldName(c.world)}`, 30, 2);
  stat(g, t('visited'), c.visited.length, '处', 4);
  stat(g, t('paths'), c.paths, '条', 5);
  stat(g, t('sites'), c.sites, '处', 6);
  stat(g, t('found'), c.owned.length, '件', 7);
  // 醒着的时候已经醒了：淡下去，点不了
  if (c.awake) {
    write(g, t('wake'), 34, 9, P(3));
    return [];
  }
  return [item(g, c, 'wake', t('wake'), 34, 9)];
};

const recordRight: Draw = (g, c) => {
  title(g, t('visitedList'), 26);
  // 第 2 到第 10 行，放不下时最后一行写还有几处
  const max = c.visited.length > 9 ? 8 : 9;
  c.visited.slice(0, max).forEach((w, i) => {
    g.fillStyle = P(9);
    g.fillRect(30, ROW0 + (2 + i) * ROW - 6, 2, 2);
    write(g, worldName(w), 36, 2 + i, w === c.world ? P(8) : C.ink);
  });
  if (c.visited.length > max) write(g, andMore(c.visited.length - max), 36, 2 + max, P(3));
  foot(g, t('close'));
  return [];
};

// ── 设置：在书的最后，连着操作说明 ──
const settingsLeft: Draw = (g, c) => {
  title(g, t('settings'), 30);
  const r: Region[] = [];
  write(g, t('sens'), 30, 2);
  r.push(item(g, c, 'sens-', '-', 38, 3));
  const sens = `×${c.settings.sens.toFixed(2).replace(/0$/, '')}`;
  write(g, sens, Math.round((38 + RIGHT - text(sens).width) / 2), 3);
  r.push(item(g, c, 'sens+', '+', rightX('+'), 3));
  const opt = (id: string, label: string, value: string, k: number) => {
    write(g, label, 30, k);
    r.push(item(g, c, id, value, rightX(value), k));
  };
  opt('res', t('res'), t(RES_LABEL[c.settings.res] ?? RES_LABEL.auto), 4);
  opt('lang', t('language'), LANG_LABEL[c.settings.lang], 5);
  opt('hud', t('hud'), c.settings.hud ? t('on') : t('off'), 6);
  // 回到开场：木条重新拼成 NEXUS，再醒一次。用名字本身，不写「返回主界面」
  r.push(item(g, c, 'title', 'NEXUS', 34, 9));
  return r;
};

const controlsRight: Draw = (g) => {
  title(g, t('controls'), 26);
  const rows: [string, Key][] = [
    ['WASD', 'kWalk'],
    ['Space', 'kJump'],
    ['Shift', 'kHurry'],
    ['E', 'kUse'],
    ['Tab', 'kDiary'],
    ['Q', 'kSqueeze'],
    ['F', 'kCarried'],
    ['Esc', 'kFree'],
  ];
  rows.forEach(([k, v], i) => {
    write(g, k, 26, 2 + i, P(2));
    write(g, t(v), 70, 2 + i);
  });
  return [];
};

/** 按字宽折行：汉字一个字一断，拉丁字一个词一断 */
function wrap(s: string, maxW: number): string[] {
  const lines: string[] = [];
  let cur = '';
  for (const u of s.match(/[⺀-鿿　-〿＀-￯]|[^\s⺀-鿿　-〿＀-￯]+\s*|\s+/g) ?? []) {
    if (cur && text((cur + u).trimEnd()).width > maxW) {
      lines.push(cur.trimEnd());
      cur = u.trimStart();
    } else cur += u;
  }
  if (cur.trim()) lines.push(cur.trimEnd());
  return lines;
}

// ── 拾得 ──
const itemsLeft: Draw = (g, c) => {
  title(g, t('tabItems'), 30);
  const r: Region[] = [];
  if (!c.owned.length) write(g, t('none'), 34, 2, P(3));
  c.owned.slice(0, 8).forEach((o, i) => {
    const def = itemDef(o.id);
    if (!def) return;
    r.push(item(g, c, `hold:${o.id}`, l(def.name), 34, 2 + i));
    if (c.held === o.id) write(g, t('inHand'), rightX(t('inHand')), 2 + i, P(9));
  });
  return r;
};

const itemsRight: Draw = (g, c) => {
  const hov = c.hover?.startsWith('hold:') ? c.hover.slice(5) : null;
  const id = hov ?? c.held ?? c.owned[0]?.id;
  const o = c.owned.find((x) => x.id === id);
  const def = id ? itemDef(id) : undefined;
  if (!o || !def) {
    write(g, t('foundHere'), 26, 3, P(3));
    return [];
  }
  const ic = def.icon();
  g.imageSmoothingEnabled = false;
  g.drawImage(ic, Math.round((PW - ic.width * 3) / 2), 10, ic.width * 3, ic.height * 3);
  write(g, l(def.name), 26, 4, P(8));
  write(g, gotOn(o.night, worldName(o.world)), 26, 5, P(2));
  // 写不下的最后一行收成省略号
  const lines = wrap(l(def.desc), PW - 40);
  if (lines.length > 5) lines.splice(4, lines.length - 4, `${lines[4]}…`);
  lines.forEach((ln, i) => write(g, ln, 26, 6 + i));
  foot(g, c.held === id ? t('clickToStow') : t('clickToHold'));
  return [];
};

// ── 索引贴：一排彩色的小纸条，从书顶的纸叠里伸出来。翻在哪一节，那张就高一截 ──
const TABS: { id: Spread; key: Key; color: string }[] = [
  { id: 'record', key: 'tabRecord', color: P(11) },
  { id: 'items', key: 'tabItems', color: P(13) },
  { id: 'settings', key: 'tabSettings', color: P(14) },
];

const tabsDraw: Draw = (g, c) => {
  const r: Region[] = [];
  let x = 8;
  for (const tb of TABS) {
    const off = tb.id === 'items' && c.awake;
    const id = `tab:${tb.id}`;
    const on = c.spread === tb.id;
    const hov = !off && !on && c.hover === id;
    const label = text(t(tb.key), off ? P(3) : hov ? P(8) : C.ink);
    const w = label.width + 10;
    // 露出来的高度：翻到的那张最高，悬停的冒出一格
    const h = on ? TAB_H : hov ? TAB_H - 3 : TAB_H - 4;
    const y = TAB_H - h;
    g.fillStyle = C.ink;
    g.fillRect(x + 1, y, w - 2, 1);
    g.fillRect(x, y + 1, 1, h - 1);
    g.fillRect(x + w - 1, y + 1, 1, h - 1);
    g.fillStyle = tb.color;
    g.fillRect(x + 1, y + 1, w - 2, h - 1);
    // 字离贴的上沿 3 格：贴冒高、缩矮时字跟着贴走
    const [top] = inkRows(label);
    g.drawImage(label, x + 5, y + 3 - top);
    if (!off && !on) r.push({ id, x, y, w, h: TAB_H - y });
    x += w + 2;
  }
  return r;
};

function coverArt(): HTMLCanvasElement {
  const W = PW + OVER;
  const H = PH + OVER * 2;
  const { c, g } = scratch(W, H);
  g.fillStyle = P(8);
  g.fillRect(0, 0, W, H);
  // 布纹：稀疏的深一档的点
  g.fillStyle = P(1);
  for (let y = 1; y < H; y += 3) for (let x = (y * 7) % 5; x < W; x += 5) g.fillRect(x, y, 1, 1);
  // 压印的一圈细框
  g.fillStyle = P(9);
  g.fillRect(6, 6, W - 12, 1);
  g.fillRect(6, H - 7, W - 12, 1);
  g.fillRect(6, 6, 1, H - 12);
  g.fillRect(W - 7, 6, 1, H - 12);
  // 签条
  const lw = 64;
  const lh = 22;
  const lx = Math.round((W - lw) / 2) - 6;
  const ly = 48;
  const m = paperMask(lw, lh, 'cover');
  paper(g, lx, ly, lw, lh, m, { fibre: true });
  const t = text('NEXUS', C.ink);
  const [top, bot] = inkRows(t);
  g.drawImage(t, lx + Math.round((lw - t.width) / 2), ly + Math.floor((lh - (bot - top + 1)) / 2) - top);
  // 一枚小晶体
  const cx = lx + lw / 2;
  const cy = ly + lh + 36;
  for (let j = -6; j <= 6; j++) {
    const half = 6 - Math.abs(j);
    for (let i = -half; i <= half; i++) {
      g.fillStyle = Math.abs(i) === half || Math.abs(j) === 6 ? C.ink : j < 0 ? P(14) : i < 0 ? P(11) : P(13);
      g.fillRect(cx + i, cy + j, 1, 1);
    }
  }
  // 松紧带
  g.fillStyle = P(1);
  g.fillRect(W - 22, 0, 4, H);
  g.fillStyle = P(2);
  g.fillRect(W - 21, 0, 1, H);
  return c;
}

function ribbon(): HTMLCanvasElement {
  const { c, g } = scratch(5, 34);
  g.fillStyle = P(9);
  g.fillRect(0, 0, 5, 34);
  g.fillStyle = P(10);
  g.fillRect(1, 0, 1, 34);
  g.clearRect(2, 31, 1, 3);
  g.clearRect(1, 33, 3, 1);
  return c;
}

// ── 指针：一支像素小箭头，1 墨色 2 纸色 ──
const ARROW = ['1', '11', '121', '1221', '12221', '122221', '1222221', '12222221', '12211111', '1211', '11', '1'];

type Spread = 'record' | 'items' | 'settings';
const ORDER: Spread[] = ['record', 'items', 'settings'];

interface Turn {
  t: number;
  /** 1 往后翻（右页翻到左边），-1 往回翻 */
  dir: 1 | -1;
  to: Spread;
}

export interface DiaryHost {
  wake(): void;
  /** 回到开场的标题（NEXUS） */
  title(): void;
  apply(s: Settings): void;
  world(): string;
  visited(): string[];
  items(): { owned: Owned[]; held: string | null };
  /** 拿起一件（null ＝ 收起来） */
  hold(id: string | null): void;
}

export class Diary {
  /** 0 合上收走，1 摊开停稳 */
  private o = 0;
  private want = 0;
  private spread: Spread = 'record';
  private turn: Turn | null = null;
  private pages: Record<Spread, [Page, Page]>;
  private tabs = new Page('T', tabsDraw, PW, TAB_H);
  private leftPage: THREE.Mesh;
  private rightPage: THREE.Mesh;
  private sheetGeo: THREE.PlaneGeometry;
  private sheetFront: THREE.Mesh;
  private sheetBack: THREE.Mesh;
  private root = new THREE.Group();
  private hinge = new THREE.Group();
  /** 书页顶面是与 UI 像素一一对应的那个平面 */
  private stage = new Stage(STACK_T);
  private cursor = new THREE.Vector2();
  private hover: string | null = null;
  private night = night();
  settings: Settings;

  constructor(
    private ui: Ui,
    private host: DiaryHost,
  ) {
    this.settings = loadSettings();
    host.apply(this.settings);
    this.pages = {
      record: [new Page('L', recordLeft), new Page('R', recordRight)],
      items: [new Page('L', itemsLeft), new Page('R', itemsRight)],
      settings: [new Page('L', settingsLeft), new Page('R', controlsRight)],
    };

    const cover = solid(P(8));
    const coverEdge = solid(P(1));
    const edge = solid(C.back);
    const H = PH + OVER * 2;
    // 右半：封底、书页、书签带
    const right = new THREE.Group();
    right.add(box(0, PW + OVER, H, -COVER_T, 0, [coverEdge, coverEdge, coverEdge, coverEdge, cover, cover]));
    right.add(box(0, PW, PH, 0, STACK_T, [edge, edge, edge, edge, edge, edge]));
    this.rightPage = plane(PW, PH, mat(), PW / 2, STACK_T + PAGE_LIFT);
    right.add(this.rightPage);
    // 索引贴：和书页在同一个平面上（一个纹素对一个 UI 像素），从书页上沿伸出去，盖过封面多出来的那一圈
    const tabs = plane(PW, TAB_H, mat({ map: this.tabs.tex }), PW / 2, STACK_T + PAGE_LIFT);
    tabs.position.y = PH / 2 + TAB_H / 2;
    right.add(tabs);
    // 书签带夹在封底与纸叠之间：上端藏在纸叠里，只有垂出书页底边的那截看得见，永远在所有页后面
    const rb = plane(5, 34, mat({ map: canvasTex(ribbon()) }), 34.5, STACK_T / 2);
    rb.position.y = -PH / 2 - 9;
    right.add(rb);
    // 左半：封面连着第一页，绕书脊（z ＝ 书页顶面）转
    const left = new THREE.Group();
    left.position.z = -STACK_T;
    left.add(box(-(PW + OVER), 0, H, -COVER_T, 0, [coverEdge, coverEdge, coverEdge, coverEdge, cover, cover]));
    left.add(box(-PW, 0, PH, 0, STACK_T, [edge, edge, edge, edge, edge, edge]));
    this.leftPage = plane(PW, PH, mat(), -PW / 2, STACK_T + PAGE_LIFT);
    left.add(this.leftPage);
    const art = plane(PW + OVER, H, mat({ map: canvasTex(coverArt()) }), -(PW + OVER) / 2, -COVER_T - 0.05);
    art.rotation.y = Math.PI;
    left.add(art);
    this.hinge.position.z = STACK_T;
    this.hinge.add(left);
    this.root.add(right, this.hinge);

    // 正在翻的那一页：正面是旧的右页，背面是新的左页
    this.sheetGeo = new THREE.PlaneGeometry(PW, PH, 24, 1);
    this.sheetFront = new THREE.Mesh(this.sheetGeo, mat());
    this.sheetBack = new THREE.Mesh(this.sheetGeo, mat({ flipU: true, side: THREE.BackSide }));
    for (const m of [this.sheetFront, this.sheetBack]) {
      m.position.z = STACK_T + 0.3;
      m.visible = false;
      this.root.add(m);
    }
    this.stage.scene.add(this.root);
    this.showSpread('record');
  }

  /** 打开着（包括正在打开、正在合上）：这时人不走、视角不转 */
  get active() {
    return this.o > 0 || this.want > 0;
  }

  /** 世界犯困的程度 */
  get drowse() {
    return ease(clamp01(this.o * 1.4));
  }

  toggle() {
    if (this.want > 0) this.close();
    else this.open();
  }

  open() {
    if (this.want > 0) return;
    this.want = 1;
    this.turn = null;
    this.spread = 'record';
    this.showSpread('record');
    this.cursor.set(this.ui.w / 2 + 60, this.ui.h / 2 - PH / 2 - 8);
  }

  close() {
    this.want = 0;
    this.hover = null;
  }

  setSize(wUi: number, hUi: number) {
    this.stage.setSize(wUi, hUi);
  }

  /** 锁着指针时：按位移挪箭头 */
  move(dx: number, dy: number) {
    this.cursor.x = THREE.MathUtils.clamp(this.cursor.x + dx / UI_SCALE, 0, this.ui.w - 1);
    this.cursor.y = THREE.MathUtils.clamp(this.cursor.y + dy / UI_SCALE, 0, this.ui.h - 1);
  }

  /** 没锁时：箭头就在真鼠标的位置（UI 像素） */
  moveTo(x: number, y: number) {
    this.cursor.set(x, y);
  }

  click() {
    if (!this.idle || !this.hover) return;
    const s = this.settings;
    switch (this.hover) {
      case 'wake':
        this.close();
        this.host.wake();
        break;
      case 'title':
        this.close();
        this.host.title();
        break;
      case 'lang':
        s.lang = s.lang === 'zh' ? 'en' : 'zh';
        setLang(s.lang);
        break;
      case 'sens-':
      case 'sens+': {
        const i = SENS_STEPS.indexOf(s.sens);
        const j = THREE.MathUtils.clamp((i < 0 ? 2 : i) + (this.hover === 'sens+' ? 1 : -1), 0, SENS_STEPS.length - 1);
        s.sens = SENS_STEPS[j];
        break;
      }
      case 'hud':
        s.hud = !s.hud;
        break;
      case 'res':
        s.res = RES_STEPS[(RES_STEPS.indexOf(s.res) + 1) % RES_STEPS.length];
        break;
      default:
        if (this.hover.startsWith('tab:')) this.turnTo(this.hover.slice(4) as Spread);
        else if (this.hover.startsWith('hold:')) {
          const id = this.hover.slice(5);
          this.host.hold(this.host.items().held === id ? null : id);
        }
    }
    saveSettings(s);
    this.host.apply(s);
    this.redraw(this.spread);
  }

  private get idle() {
    return this.o === 1 && this.want === 1 && !this.turn;
  }

  private ctx(): PageCtx {
    const world = this.host.world();
    return {
      hover: this.hover,
      settings: this.settings,
      world,
      visited: dreamt(this.host.visited()),
      night: this.night,
      awake: isReality(world),
      spread: this.turn?.to ?? this.spread,
      paths: edges().length,
      sites: sites().length,
      ...this.host.items(),
    };
  }

  private redraw(s: Spread) {
    const c = this.ctx();
    for (const p of this.pages[s]) p.redraw(c);
    this.tabs.redraw(c);
  }

  private showSpread(s: Spread) {
    this.redraw(s);
    setMap(this.leftPage, this.pages[s][0].tex);
    setMap(this.rightPage, this.pages[s][1].tex);
  }

  private turnTo(to: Spread) {
    if (to === this.spread || this.turn) return;
    const dir = ORDER.indexOf(to) > ORDER.indexOf(this.spread) ? 1 : -1;
    this.hover = null;
    this.redraw(this.spread);
    this.redraw(to);
    const [oldL, oldR] = this.pages[this.spread];
    const [newL, newR] = this.pages[to];
    if (dir === 1) {
      // 往后翻：右页立起来翻到左边；底下先露出新的右页，左页等它落下来再换
      setMap(this.sheetFront, oldR.tex);
      setMap(this.sheetBack, newL.tex);
      setMap(this.rightPage, newR.tex);
    } else {
      // 往回翻：左页翻回右边；底下先露出新的左页
      setMap(this.sheetFront, newR.tex);
      setMap(this.sheetBack, oldL.tex);
      setMap(this.leftPage, newL.tex);
    }
    this.turn = { t: 0, dir, to };
    this.tabs.redraw(this.ctx());
    this.sheetFront.visible = this.sheetBack.visible = true;
  }

  /** 翻页的弯：根部先走，页尖慢半拍 */
  private bendSheet(theta: number, dir: 1 | -1) {
    const pos = this.sheetGeo.attributes.position as THREE.BufferAttribute;
    const N = 24;
    const ds = PW / N;
    let x = 0;
    let z = 0;
    const xs = [0];
    const zs = [0];
    for (let i = 0; i < N; i++) {
      const s = (i + 0.5) / N;
      const a = theta - dir * 0.9 * Math.sin(theta) * s;
      x += ds * Math.cos(a);
      z += ds * Math.sin(a);
      xs.push(x);
      zs.push(z);
    }
    for (let row = 0; row < 2; row++)
      for (let i = 0; i <= N; i++) {
        const k = row * (N + 1) + i;
        pos.setX(k, xs[i]);
        pos.setZ(k, zs[i]);
      }
    pos.needsUpdate = true;
    this.sheetGeo.computeVertexNormals();
  }

  update(dt: number) {
    // 开合
    if (this.want > this.o) this.o = Math.min(1, this.o + dt / OPEN_TIME);
    else if (this.want < this.o) this.o = Math.max(0, this.o - dt / CLOSE_TIME);
    if (!this.active) return;

    const rise = ease(clamp01(this.o / 0.45));
    const unfold = ease(clamp01((this.o - 0.35) / 0.65));
    const { h } = this.ui;
    this.root.position.set((-(PW + OVER) / 2) * (1 - unfold), -(h / 2 + PH) * (1 - rise), 0);
    this.root.rotation.set(-1.0 * (1 - ease(this.o)), 0, 0.12 * (1 - rise));
    this.hinge.rotation.y = Math.PI * (1 - unfold);

    // 翻页
    if (this.turn) {
      const tr = this.turn;
      tr.t = Math.min(1, tr.t + dt / TURN_TIME);
      const e = ease(tr.t);
      this.bendSheet(tr.dir === 1 ? Math.PI * e : Math.PI * (1 - e), tr.dir);
      if (tr.t >= 1) {
        const [newL, newR] = this.pages[tr.to];
        setMap(this.leftPage, newL.tex);
        setMap(this.rightPage, newR.tex);
        this.sheetFront.visible = this.sheetBack.visible = false;
        this.spread = tr.to;
        this.turn = null;
      }
    }

    // 悬停：只在摊平停稳时（这时页面与 UI 像素一一对应）
    let hov: string | null = null;
    if (this.idle) {
      const [L, R] = this.pages[this.spread];
      const x0 = this.ui.w / 2 - PW;
      const y0 = this.ui.h / 2 - PH / 2;
      const cx = Math.floor(this.cursor.x);
      const cy = Math.floor(this.cursor.y);
      for (const [p, ox, oy] of [[L, x0, y0], [R, x0 + PW, y0], [this.tabs, x0 + PW, y0 - TAB_H]] as [Page, number, number][])
        for (const r of p.regions) if (cx >= ox + r.x && cx < ox + r.x + r.w && cy >= oy + r.y && cy < oy + r.y + r.h) hov = r.id;
    }
    if (hov !== this.hover) {
      this.hover = hov;
      this.redraw(this.spread);
    }
  }

  render(r: THREE.WebGLRenderer) {
    if (this.active) this.stage.render(r);
  }

  /** 箭头画在 UI 画布上（在纸签之上） */
  drawCursor() {
    if (!this.active || this.o < 0.6) return;
    const g = this.ui.g;
    const x = Math.floor(this.cursor.x);
    const y = Math.floor(this.cursor.y);
    ARROW.forEach((row, j) => {
      for (let i = 0; i < row.length; i++) {
        if (row[i] === '.') continue;
        g.fillStyle = row[i] === '1' ? C.ink : C.paper;
        g.fillRect(x + i, y + j, 1, 1);
      }
    });
  }
}
