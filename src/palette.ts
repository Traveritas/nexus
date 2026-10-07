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

/** 描边色：不用最深那枚，线要软一点 */
export const INK = '#3a3350';

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
