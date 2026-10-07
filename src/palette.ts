/* 色板：像素层的所有颜色最终都落在这 16 色上（晶体与解析度 0 级除外）。
   冷紫一列管结构，粉一列管温度，另有雾蓝、淡金、冷绿各一两枚作记忆点。 */
import * as THREE from 'three';

export const PALETTE = [
  '#1d1a2b', '#3a3350', '#5c5378', '#82799e', '#a8a1bf', '#cdc8db', '#ece9f2', '#fbf9f7',
  '#6e4f66', '#a8798c', '#d9aab5', '#f3d6d6',
  '#8fa3c7', '#c3d1e6',
  '#ead7a0',
  '#86b5a5',
];

/** 按主色自动配的三色明暗（暗, 中＝主色, 亮）：暗一档往冷紫/雾蓝偏，亮一档往粉/淡金/白偏。
    没写 nx_ramp 的哑光在「自动三色」开着时用它 */
export const AUTO_RAMP: [number, number, number][] = [
  [0, 0, 1], //  0 ink
  [0, 1, 8], //  1 violet_deep → rose_deep
  [1, 2, 9], //  2 violet → rose
  [2, 3, 9], //  3 lilac_dark → rose
  [3, 4, 10], //  4 lilac → pink
  [4, 5, 11], //  5 lilac_pale → pink_pale
  [5, 6, 7], //  6 mist → white
  [13, 7, 7], //  7 white：暗处落雾蓝
  [1, 8, 9], //  8 rose_deep
  [3, 9, 10], //  9 rose
  [4, 10, 11], // 10 pink
  [10, 11, 7], // 11 pink_pale
  [3, 12, 13], // 12 blue
  [12, 13, 7], // 13 blue_pale
  [9, 14, 7], // 14 gold
  [12, 15, 14], // 15 green → 亮处淡金
];

/** 描边色：不用最深那枚，线要软一点 */
export const INK = '#3a3350';
/** 凸棱亮边色：最亮那枚，半透地压上去 */
export const HI = '#fbf9f7';

function lin(c: number) {
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

function oklab(r: number, g: number, b: number) {
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  return new THREE.Vector3(
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  );
}

function rgb(hex: string) {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

/** 显示空间（sRGB）的色值，着色器直接输出 */
export const paletteRgb = PALETTE.map((h) => new THREE.Vector3(...rgb(h)));
/** OKLab，用来找最近色 */
export const paletteLab = PALETTE.map((h) => {
  const [r, g, b] = rgb(h).map(lin);
  return oklab(r, g, b);
});
export const inkRgb = new THREE.Vector3(...rgb(INK));
export const hiRgb = new THREE.Vector3(...rgb(HI));
