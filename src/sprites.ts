/* 纸片的图：在小画布上按每米 TEXEL 像素直接画，再把半透明边一刀切成全有或全无。 */
import * as THREE from 'three';
import { PAPER } from './paper';
import { TEXEL } from './materials';
import { procSprite } from './proc';

export function crisp(cv: HTMLCanvasElement) {
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

export function canvas(w: number, h: number) {
  const cv = document.createElement('canvas');
  cv.width = w;
  cv.height = h;
  const g = cv.getContext('2d')!;
  g.imageSmoothingEnabled = false;
  return { cv, g };
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
  moon: moonTexture,
  ...PAPER,
};
/** 旧名字 → 程序化的默认款（以前手绘的那几张已经换掉） */
const ALIAS: Record<string, string> = {
  flower: 'flower.star:1',
  grass1: 'grass.clump:1',
  grass2: 'grass.clump:2',
  grass3: 'grass.flowered:3',
  sparkle: 'star.glow:1',
  lily: 'flower.cup:1',
  reed: 'grass.reed:1',
  puff: 'flower.puff:1',
};
const cache = new Map<string, Promise<THREE.Texture>>();
const loader = new THREE.TextureLoader();

export function loadSprite(name: string): Promise<THREE.Texture> {
  let p = cache.get(name);
  if (!p) {
    const proc = BUILTIN[name] ? null : procSprite(ALIAS[name] ?? name);
    p = BUILTIN[name]
      ? Promise.resolve(BUILTIN[name]())
      : proc
      ? Promise.resolve(proc)
      : loader.loadAsync(`${import.meta.env.BASE_URL}sprites/${name}.png`).then((tex) => {
          tex.colorSpace = THREE.SRGBColorSpace;
          // 名字以 @<每米像素> 结尾的是真实贴图的剪纸（照片、渲染图）：比像素画细，按自己的密度定尺寸，
          // 用 mip 链采样，远处不闪；像素化与落色板照旧交给管线
          const ppm = Number(/@(d+)$/.exec(name)?.[1] ?? TEXEL);
          tex.userData.ppm = ppm;
          if (ppm > TEXEL) {
            tex.magFilter = THREE.LinearFilter;
            tex.minFilter = THREE.LinearMipmapLinearFilter;
            tex.generateMipmaps = true;
          } else {
            tex.magFilter = THREE.NearestFilter;
            tex.minFilter = THREE.NearestFilter;
            tex.generateMipmaps = false;
          }
          return tex;
        });
    cache.set(name, p);
  }
  return p;
}

/** 图的尺寸（米）：像素 ÷ 每米像素（像素画是 TEXEL，真实贴图的剪纸看文件名里的 @数字） */
export function spriteSize(tex: THREE.Texture) {
  const im = tex.image as { width: number; height: number };
  const ppm = (tex.userData.ppm as number | undefined) ?? TEXEL;
  return { w: im.width / ppm, h: im.height / ppm };
}
