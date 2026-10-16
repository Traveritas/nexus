/* 世界：名字（中英）、所在的主域、星座图上的位置，以及「走过的连接」「有站点的世界」的存档（罗盘的地图用）。 */
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
  // 现实
  wake_fragment: { zh: '残片', en: 'Fragment' },
  wake_white: { zh: '白井', en: 'White Well' },
  wake_museum: { zh: '陈列', en: 'Exhibit' },
  // 旧梦：以前的家和它连着的几处
  home: { zh: '旧家', en: 'Old Home' },
  procession: { zh: '回廊', en: 'Cloister' },
  room: { zh: '无墙之屋', en: 'Wallless Room' },
  isles: { zh: '云阶', en: 'Cloud Steps' },
  descent_old: { zh: '旧下沉', en: 'Old Descent' },
};

export const worldName = (w: string) => (WORLD_NAMES[w] ? l(WORLD_NAMES[w]) : w);

/** 现实：醒着的那几间（干净低模的世界）。它们自成一处，不在梦的网里——
    不进罗盘的星座、不记连接、不列进日记的「去过」；在这里身上的东西拿不出来（看不了、拿不起、用不了） */
export const REALITY = new Set(['wake_fragment', 'wake_white', 'wake_museum']);
export const isReality = (w: string) => REALITY.has(w);
/** 梦里去过的（日记、星座用） */
export const dreamt = (visited: string[]) => visited.filter((w) => !isReality(w));

/** 主域：风格差别大的一大片梦，里面有多个世界（docs/realms.md）。罗盘头顶的星图只画此刻所在的主域；
    通往别的主域的出入口另有一种星。现实不在任何主域里；没写进来的世界（样板、测试）也不在 */
export const REALMS: Record<string, { name: L; worlds: string[] }> = {
  shallows: {
    name: { zh: '浅梦', en: 'Shallows' },
    worlds: ['house', 'house_out', 'sunpatch', 'longshadow', 'descent', 'glasshouse', 'shoal', 'stair', 'stair_b'],
  },
  // 旧梦：以前的家和它连着的几处。从家家家里那扇转了 32° 的孤门进来；没有回去的路，只能醒来
  olddream: {
    name: { zh: '旧梦', en: 'Old Dreams' },
    worlds: ['home', 'procession', 'room', 'isles', 'descent_old'],
  },
};

export const realmOf = (w: string) => Object.keys(REALMS).find((r) => REALMS[r].worlds.includes(w)) ?? null;
export const realmName = (r: string) => l(REALMS[r].name);

/** 星座图上的位置（x 向右、y 向前；每个主域的中心在正中）。按连接排，没写的世界排在外圈。
    浅梦：家 → 门外、下沉（往下）、断梯 → 那边（往上）；花房在家的右手边，光斑、长影、浅滩围着它（它们彼此相通）。
    旧梦：旧家在正中，书 → 回廊、衣柜 → 无墙之屋、落地窗 → 云阶（回廊也通云阶）、床 → 旧下沉 */
export const CONSTELLATION: Record<string, [number, number]> = {
  house: [0, 0],
  house_out: [-0.55, -0.45],
  descent: [0.05, -1.15],
  stair: [-0.4, 0.8],
  stair_b: [-0.6, 1.3],
  glasshouse: [0.95, 0.25],
  sunpatch: [0.75, 0.95],
  longshadow: [0.6, -0.9],
  shoal: [1.55, -0.15],

  home: [0, 0],
  procession: [-0.85, 0.55],
  room: [-0.7, -0.6],
  isles: [-0.15, 1.2],
  descent_old: [0.45, -1.05],
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
