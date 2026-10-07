/* 纸片的图：在小画布上按每米 TEXEL 像素直接画，再把半透明边一刀切成全有或全无。 */
import * as THREE from 'three';

function crisp(cv: HTMLCanvasElement) {
  const g = cv.getContext('2d')!;
  const im = g.getImageData(0, 0, cv.width, cv.height);
  const d = im.data;
  for (let i = 0; i < d.length; i += 4) {
    if (d[i + 3] >= 110) {
      const a = d[i + 3] / 255;
      d[i] = Math.round(d[i] / a);
      d[i + 1] = Math.round(d[i + 1] / a);
      d[i + 2] = Math.round(d[i + 2] / a);
      d[i + 3] = 255;
    } else d[i + 3] = 0;
  }
  g.putImageData(im, 0, 0);
  const tex = new THREE.CanvasTexture(cv);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.magFilter = THREE.NearestFilter;
  tex.minFilter = THREE.NearestFilter;
  tex.generateMipmaps = false;
  return tex;
}

function canvas(w: number, h: number) {
  const cv = document.createElement('canvas');
  cv.width = w;
  cv.height = h;
  const g = cv.getContext('2d')!;
  g.imageSmoothingEnabled = false;
  return { cv, g };
}

/** 一株平面的花：40×72 纹素，即 2.5m × 4.5m。原点在画布底边中点 */
export function flowerTexture() {
  const { cv, g } = canvas(40, 72);
  // 茎：不是直的，带一点犹豫
  g.strokeStyle = '#86b5a5';
  g.lineWidth = 2;
  g.beginPath();
  g.moveTo(20, 72);
  g.bezierCurveTo(19, 58, 23, 46, 20, 28);
  g.stroke();
  // 两片叶子
  g.fillStyle = '#86b5a5';
  g.beginPath();
  g.ellipse(13, 52, 7, 2.6, -0.5, 0, Math.PI * 2);
  g.fill();
  g.beginPath();
  g.ellipse(27, 44, 6, 2.4, 0.45, 0, Math.PI * 2);
  g.fill();
  g.fillStyle = '#5f8c80';
  g.fillRect(12, 52, 4, 1);
  g.fillRect(25, 44, 4, 1);
  // 六瓣
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * Math.PI * 2 + 0.2;
    g.fillStyle = i % 2 ? '#d9aab5' : '#f3d6d6';
    g.beginPath();
    g.ellipse(20 + Math.cos(a) * 8, 18 + Math.sin(a) * 8, 7.5, 4.2, a, 0, Math.PI * 2);
    g.fill();
  }
  g.strokeStyle = '#a8798c';
  g.lineWidth = 1;
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * Math.PI * 2 + 0.2;
    g.beginPath();
    g.moveTo(20 + Math.cos(a) * 4, 18 + Math.sin(a) * 4);
    g.lineTo(20 + Math.cos(a) * 12, 18 + Math.sin(a) * 12);
    g.stroke();
  }
  g.fillStyle = '#ead7a0';
  g.beginPath();
  g.arc(20, 18, 4, 0, Math.PI * 2);
  g.fill();
  g.fillStyle = '#fbf9f7';
  g.fillRect(18, 16, 2, 2);
  return crisp(cv);
}

/** 一簇草：16×10 纹素 */
export function grassTexture(seed: number) {
  const { cv, g } = canvas(16, 10);
  let s = seed;
  const rnd = () => ((s = (s * 16807) % 2147483647) / 2147483647);
  for (let i = 0; i < 5; i++) {
    const x = 2 + rnd() * 12;
    const h = 4 + rnd() * 6;
    g.fillStyle = rnd() > 0.5 ? '#86b5a5' : '#a8a1bf';
    g.fillRect(Math.round(x), 10 - Math.round(h), 1, Math.round(h));
    g.fillRect(Math.round(x + (rnd() > 0.5 ? 1 : -1)), 10 - Math.round(h * 0.5), 1, Math.round(h * 0.5));
  }
  return crisp(cv);
}

/** 天上的纸月：一枚平的圆片，缺一角 */
export function moonTexture() {
  const { cv, g } = canvas(32, 32);
  g.fillStyle = '#ead7a0';
  g.beginPath();
  g.arc(16, 16, 15, 0, Math.PI * 2);
  g.fill();
  g.globalCompositeOperation = 'destination-out';
  g.beginPath();
  g.arc(25, 9, 7, 0, Math.PI * 2);
  g.fill();
  g.globalCompositeOperation = 'source-over';
  g.fillStyle = '#fbf9f7';
  g.fillRect(8, 14, 3, 3);
  g.fillRect(12, 22, 2, 2);
  return crisp(cv);
}

/* ── 按名字取纸片的图：先找内置的，再找 public/sprites/<名字>.png ── */
const BUILTIN: Record<string, () => THREE.Texture> = {
  flower: flowerTexture,
  grass1: () => grassTexture(3),
  grass2: () => grassTexture(11),
  grass3: () => grassTexture(29),
  moon: moonTexture,
};
const cache = new Map<string, Promise<THREE.Texture>>();
const loader = new THREE.TextureLoader();

export function loadSprite(name: string): Promise<THREE.Texture> {
  let p = cache.get(name);
  if (!p) {
    p = BUILTIN[name]
      ? Promise.resolve(BUILTIN[name]())
      : loader.loadAsync(`${import.meta.env.BASE_URL}sprites/${name}.png`).then((tex) => {
          tex.colorSpace = THREE.SRGBColorSpace;
          tex.magFilter = THREE.NearestFilter;
          tex.minFilter = THREE.NearestFilter;
          tex.generateMipmaps = false;
          return tex;
        });
    cache.set(name, p);
  }
  return p;
}

/** 图的像素尺寸 */
export function spriteSize(tex: THREE.Texture) {
  const im = tex.image as { width: number; height: number };
  return { w: im.width, h: im.height };
}
