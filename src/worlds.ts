/* 世界：名字（中英）、星座图上的位置，以及「走过的连接」「有站点的世界」的存档（罗盘的地图用）。 */
import { l, type L } from './i18n';

/** 世界的名字；没写的显示原名 */
export const WORLD_NAMES: Record<string, L> = {
  // 浅梦（mockup/shallows-05）：家是中枢
  house: { zh: '家', en: 'Home' },
  house_out: { zh: '家 · 门外', en: 'Home · Outside' },
  sunpatch: { zh: '光斑', en: 'Sunpatch' },
  longshadow: { zh: '长影', en: 'Longshadow' },
  descent: { zh: '下沉', en: 'Descent' },
  glasshouse: { zh: '花房', en: 'Glasshouse' },
  shoal: { zh: '浅滩', en: 'Shoal' },
  stair: { zh: '断梯', en: 'Broken Stair' },
  stair_b: { zh: '断梯 · 那边', en: 'Broken Stair · Beyond' },
  isles: { zh: '云阶', en: 'Cloud Steps' },
  // 现实
  wake_fragment: { zh: '残片', en: 'Fragment' },
  wake_white: { zh: '白井', en: 'White Well' },
  wake_museum: { zh: '陈列', en: 'Exhibit' },
  // 旧的（legacy）：不接进网里，不在星图上占位置；留着，也许以后作为彩蛋出现
  home: { zh: '旧家', en: 'Old Home' },
  procession: { zh: '回廊', en: 'Cloister' },
  room: { zh: '无墙之屋', en: 'Wallless Room' },
};

export const worldName = (w: string) => (WORLD_NAMES[w] ? l(WORLD_NAMES[w]) : w);

/** 现实：醒着的那几间（干净低模的世界）。它们自成一处，不在梦的网里——
    不进罗盘的星座、不记连接、不列进日记的「去过」；在这里身上的东西拿不出来（看不了、拿不起、用不了） */
export const REALITY = new Set(['wake_fragment', 'wake_white', 'wake_museum']);
export const isReality = (w: string) => REALITY.has(w);
/** 梦里去过的（日记、星座用） */
export const dreamt = (visited: string[]) => visited.filter((w) => !isReality(w));

/** 旧的世界（legacy）：还在、还能进（?world=），但不在星图上；以后也许作为彩蛋出现 */
export const LEGACY = new Set(['home', 'procession', 'room']);

/** 星座图上的位置（x 向右、y 向前；家在正中）。按连接排：
    家 → 门外、下沉（往下）、断梯 → 那边 → 云阶（往上）；花房在家的右手边，光斑、长影、浅滩围着它（它们彼此相通）。
    没写的世界排在外圈 */
export const CONSTELLATION: Record<string, [number, number]> = {
  house: [0, 0],
  house_out: [-0.55, -0.45],
  descent: [0.05, -1.15],
  stair: [-0.4, 0.8],
  stair_b: [-0.6, 1.3],
  isles: [-0.35, 1.8],
  glasshouse: [0.95, 0.25],
  sunpatch: [0.75, 0.95],
  longshadow: [0.6, -0.9],
  shoal: [1.55, -0.15],
};

export function starAt(w: string, i: number): [number, number] {
  const p = CONSTELLATION[w];
  if (p) return p;
  const a = i * 2.4;
  return [Math.cos(a) * 1.6, Math.sin(a) * 1.6];
}

const EDGES_KEY = 'nexus:edges';
const SITES_KEY = 'nexus:sites';

function readList(key: string): string[] {
  try {
    const v = JSON.parse(localStorage.getItem(key) ?? '[]');
    return Array.isArray(v) ? v : [];
  } catch {
    return [];
  }
}

function writeList(key: string, v: string[]) {
  try {
    localStorage.setItem(key, JSON.stringify(v));
  } catch {
    /* 存不了就算了 */
  }
}

/** 走过的连接（无向）：[a, b] */
export function edges(): [string, string][] {
  return readList(EDGES_KEY)
    .map((s) => s.split('|') as [string, string])
    .filter(([a, b]) => !isReality(a) && !isReality(b));
}

/** 穿过一个传送物，从 a 到了 b（入睡、醒来不算：现实不在梦的网里） */
export function recordEdge(a: string, b: string) {
  if (!a || !b || a === b || isReality(a) || isReality(b)) return;
  const k = [a, b].sort().join('|');
  const all = readList(EDGES_KEY);
  if (!all.includes(k)) writeList(EDGES_KEY, [...all, k]);
}

/** 有站点（晶体）的世界 */
export function sites(): string[] {
  return readList(SITES_KEY);
}

export function recordSite(w: string) {
  const all = readList(SITES_KEY);
  if (!all.includes(w)) writeList(SITES_KEY, [...all, w]);
}
