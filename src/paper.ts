/* 纸片图集：现实物的平面剪纸（ENA 式拼贴）。自然物（树、云、星、草、花）是程序化的，见 proc.ts。
   每米 16 像素直接画；颜色取色板；镂空处是真的透明，能透过去看到后面的世界。
   名字即 Blender 里 nx_sprite 的值，清单见 docs/blender.md「纸片的图」。 */
import * as THREE from 'three';
import { canvas, crisp } from './sprites';

const C = {
  ink: '#1d1a2b', violetDeep: '#3a3350', violet: '#5c5378', lilacDark: '#82799e', lilac: '#a8a1bf',
  lilacPale: '#cdc8db', mist: '#ece9f2', white: '#fbf9f7', roseDeep: '#6e4f66', rose: '#a8798c',
  pink: '#d9aab5', pinkPale: '#f3d6d6', blue: '#8fa3c7', bluePale: '#c3d1e6', gold: '#ead7a0',
  green: '#86b5a5', greenDeep: '#5f8c80',
};

type G = CanvasRenderingContext2D;
const rect = (g: G, x: number, y: number, w: number, h: number, c: string) => {
  g.fillStyle = c;
  g.fillRect(x, y, w, h);
};
const ell = (g: G, cx: number, cy: number, rx: number, ry: number, c: string, rot = 0) => {
  g.fillStyle = c;
  g.beginPath();
  g.ellipse(cx, cy, rx, ry, rot, 0, Math.PI * 2);
  g.fill();
};
const poly = (g: G, pts: number[], c: string) => {
  g.fillStyle = c;
  g.beginPath();
  g.moveTo(pts[0], pts[1]);
  for (let i = 2; i < pts.length; i += 2) g.lineTo(pts[i], pts[i + 1]);
  g.closePath();
  g.fill();
};
const line = (g: G, pts: number[], c: string, w = 1) => {
  g.strokeStyle = c;
  g.lineWidth = w;
  g.beginPath();
  g.moveTo(pts[0], pts[1]);
  for (let i = 2; i < pts.length; i += 2) g.lineTo(pts[i], pts[i + 1]);
  g.stroke();
};
const cut = (g: G, f: () => void) => {
  g.globalCompositeOperation = 'destination-out';
  f();
  g.globalCompositeOperation = 'source-over';
};

/* ── 现实物 ─────────────────────────────── */

/** 路灯：1.5 × 5.5m，灯罩里是淡金色的光 */
function lampStreet() {
  const { cv, g } = canvas(24, 88);
  poly(g, [7, 88, 17, 88, 15, 81, 9, 81], C.violet);
  rect(g, 11, 14, 2, 68, C.violetDeep);
  rect(g, 12, 20, 1, 60, C.violet);
  line(g, [12, 15, 13, 11, 17, 9, 19, 10], C.violetDeep, 2);
  poly(g, [15, 12, 23, 12, 21, 10, 17, 10], C.violetDeep);
  rect(g, 16, 12, 6, 7, C.gold);
  rect(g, 17, 13, 2, 4, C.white);
  poly(g, [16, 19, 22, 19, 20, 21, 18, 21], C.violetDeep);
  for (const [x, y] of [[13, 15], [23, 16], [19, 24], [14, 22], [22, 9]]) rect(g, x, y, 1, 1, C.white);
  return crisp(cv);
}

/** 落地灯：1.4 × 4m */
function lampFloor() {
  const { cv, g } = canvas(22, 64);
  poly(g, [0, 13, 22, 13, 17, 1, 5, 1], C.pink);
  for (let x = 3; x < 20; x += 4) poly(g, [x, 13, x + 2, 13, x + 1.4, 1, x + 0.6, 1], C.pinkPale);
  rect(g, 4, 13, 14, 1, C.rose);
  ell(g, 11, 15, 4, 1.5, C.gold);
  rect(g, 10, 14, 2, 46, C.violetDeep);
  ell(g, 11, 61.5, 7, 2.5, C.violet);
  return crisp(cv);
}

/** 吊灯：一根线、一只灯罩；放在高处，图的底边是灯罩下沿 */
function pendant() {
  const { cv, g } = canvas(18, 44);
  rect(g, 8, 0, 2, 30, C.violetDeep);
  ell(g, 9, 37, 9, 7, C.gold);
  rect(g, 0, 37, 18, 7, C.white);
  cut(g, () => rect(g, 0, 38, 18, 6, '#000'));
  ell(g, 9, 37, 9, 1.5, C.white);
  ell(g, 9, 36, 3, 2, C.white);
  return crisp(cv);
}

/** 椅子：正面，2m 高（比人还高一点） */
function chair() {
  const { cv, g } = canvas(20, 32);
  rect(g, 3, 0, 14, 15, C.rose);
  cut(g, () => {
    for (let x = 5; x < 15; x += 3) rect(g, x, 3, 2, 9, '#000');
  });
  rect(g, 3, 0, 14, 2, C.roseDeep);
  rect(g, 1, 15, 18, 3, C.pink);
  rect(g, 1, 18, 18, 1, C.roseDeep);
  rect(g, 5, 19, 2, 9, C.roseDeep);
  rect(g, 13, 19, 2, 9, C.roseDeep);
  rect(g, 2, 19, 2, 13, C.rose);
  rect(g, 16, 19, 2, 13, C.rose);
  return crisp(cv);
}

/** 窗：2.5 × 3.4m，四格玻璃是镂空的；两边的帘子垂到地上 */
function windowCut() {
  const { cv, g } = canvas(40, 54);
  rect(g, 6, 8, 28, 30, C.white);
  cut(g, () => {
    rect(g, 9, 11, 10, 12, '#000');
    rect(g, 21, 11, 10, 12, '#000');
    rect(g, 9, 25, 10, 10, '#000');
    rect(g, 21, 25, 10, 10, '#000');
  });
  rect(g, 4, 38, 32, 2, C.lilacPale);
  rect(g, 2, 4, 36, 2, C.lilacDark);
  for (const [x0, dir] of [[0, 1], [33, -1]] as const) {
    for (let i = 0; i < 7; i++) {
      const x = x0 + i;
      const sway = Math.round(Math.sin(i * 1.3) * 0.6);
      rect(g, x + (dir > 0 ? 0 : 0), 6, 1, 48 + sway, i % 2 ? C.pinkPale : C.pink);
    }
  }
  rect(g, 5, 30, 3, 2, C.rose);
  rect(g, 32, 30, 3, 2, C.rose);
  return crisp(cv);
}

/** 门：1.4 × 2.6m，关着，门缝里漏出一线光 */
function door() {
  const { cv, g } = canvas(22, 42);
  rect(g, 0, 0, 22, 42, C.violet);
  rect(g, 2, 2, 18, 40, C.mist);
  rect(g, 4, 5, 14, 13, C.lilacPale);
  rect(g, 4, 21, 14, 17, C.lilacPale);
  rect(g, 5, 6, 12, 11, C.mist);
  rect(g, 5, 22, 12, 15, C.mist);
  rect(g, 16, 22, 2, 2, C.gold);
  rect(g, 20, 2, 1, 40, C.gold);
  rect(g, 21, 6, 1, 30, C.white);
  return crisp(cv);
}

/** 水杯：0.75 × 0.9m，下半是水 */
function cup() {
  const { cv, g } = canvas(12, 14);
  poly(g, [0, 0, 12, 0, 11, 14, 1, 14], C.lilacPale);
  cut(g, () => poly(g, [1, 1, 11, 1, 10, 7, 2, 7], '#000'));
  poly(g, [1.4, 7, 10.6, 7, 10, 13, 2, 13], C.bluePale);
  rect(g, 2, 7, 8, 1, C.white);
  rect(g, 2, 8, 1, 4, C.white);
  return crisp(cv);
}

/** 电话：拨盘式，1.1 × 0.8m */
function phone() {
  const { cv, g } = canvas(18, 13);
  poly(g, [2, 13, 16, 13, 14, 5, 4, 5], C.roseDeep);
  rect(g, 0, 1, 18, 3, C.rose);
  rect(g, 0, 0, 4, 5, C.rose);
  rect(g, 14, 0, 4, 5, C.rose);
  ell(g, 9, 9.5, 3.5, 3.5, C.mist);
  ell(g, 9, 9.5, 1.2, 1.2, C.roseDeep);
  for (let i = 0; i < 8; i++) {
    const a = (i / 8) * Math.PI * 1.6 + 0.6;
    rect(g, Math.round(9 + Math.cos(a) * 2.6), Math.round(9.5 + Math.sin(a) * 2.6), 1, 1, C.lilacDark);
  }
  return crisp(cv);
}

export const PAPER: Record<string, () => THREE.Texture> = {
  lamp_street: lampStreet,
  lamp_floor: lampFloor,
  pendant,
  chair,
  window: windowCut,
  door,
  cup,
  phone,
};
