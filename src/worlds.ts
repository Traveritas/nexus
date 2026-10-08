/* 世界：中文名、星座图上的位置，以及「走过的连接」「有站点的世界」的存档（罗盘的地图用）。 */

/** 世界的中文名；没写的显示原名 */
export const WORLD_NAMES: Record<string, string> = {
  home: '家',
  procession: '回廊',
  isles: '云阶',
  glasshouse: '花房',
  shoal: '浅滩',
  descent: '下沉',
  room: '无墙之屋',
};

export const worldName = (w: string) => WORLD_NAMES[w] ?? w;

/** 星座图上的位置（x 向右、y 向前；家在正中）。没写的世界排在外圈 */
export const CONSTELLATION: Record<string, [number, number]> = {
  home: [0, 0],
  descent: [0.1, -1],
  room: [-1.05, -0.55],
  procession: [-0.85, 0.75],
  isles: [0.25, 1.15],
  glasshouse: [1.1, -0.35],
  shoal: [1.25, 0.55],
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
  return readList(EDGES_KEY).map((s) => s.split('|') as [string, string]);
}

/** 穿过一个传送物，从 a 到了 b */
export function recordEdge(a: string, b: string) {
  if (!a || !b || a === b) return;
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
