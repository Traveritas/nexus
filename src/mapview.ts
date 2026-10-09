/* 罗盘的地图：捏到底，世界从手边那一点暗下去（pipeline 的 dim），星星一颗颗亮起来。
   - 星是连续的光：画在全分辨率的 #glow 画布上（叠加发亮），一颗亮核、一团光晕、细长的星芒；亮度慢慢呼吸，偶尔星芒一长。
     亮起时先闪一下再落定。星光落到暗下去的世界上是像素的：星的周围按格子撤回一两档暗（pipeline 的 glow）。
   - 本世界：每个出入口（传送物）与站点（晶体）一颗星，隔着墙也看得见；不标物品。
       站点：金，大，另有一对慢慢转的斜芒 · 去过的世界的出口：白，雾蓝的晕 · 没去过的：暗紫，一点微光，没有芒。
       远处的小一号；画面外的贴在屏幕边上。正看着的那颗挂一张纸签：「→ 浅滩 · 一杯水」，没去过的「→ ？」；
       站点的名字连着真实的站点，用全分辨率的平滑字（#maplabel）。
   - 抬头看天：去过的世界是天上的星座，走过的连接是星与星之间两头渐隐的细线，展开时一笔画出来；有站点的世界旁边一颗小金星。
   - 开着时照常走、转头；再捏到底一次收起来（暗色缩回手边）；换世界时直接收起。
   每帧先 layout（世界画之前，像素的星光要用），再 draw。 */
import * as THREE from 'three';
import type { Level } from './level';
import { MAX_GLOW } from './pipeline';
import { ease } from './stage';
import { UI_SCALE, paper, paperMask, paperShadow, text, C, type Ui } from './ui';
import { starAt, worldName } from './worlds';

const OPEN_TIME = 0.9;
const CLOSE_TIME = 0.5;

export interface MapCtx {
  level: Level;
  world: string;
  visited: string[];
  edges: [string, string][];
  sites: string[];
}

/** 一种星的样子：晕的颜色（r,g,b）、晕半径、星芒长（屏幕像素）、斜芒占几成、核的颜色、落到世界上的像素星光半径 */
interface Look {
  glow: string;
  r: number;
  arm: number;
  diag: number;
  core: string;
  lit: number;
}

const LOOK = {
  site: { glow: '234,215,160', r: 46, arm: 56, diag: 0.45, core: '#fffaf0', lit: 56 },
  seen: { glow: '195,209,230', r: 30, arm: 36, diag: 0, core: '#fbf9f7', lit: 38 },
  unseen: { glow: '168,161,191', r: 16, arm: 0, diag: 0, core: '#cdc8db', lit: 20 },
  sky: { glow: '205,200,219', r: 24, arm: 28, diag: 0, core: '#fbf9f7', lit: 32 },
  here: { glow: '243,214,214', r: 32, arm: 38, diag: 0, core: '#fff4f4', lit: 42 },
  gold: { glow: '234,215,160', r: 12, arm: 12, diag: 0, core: '#fff6dc', lit: 0 },
} satisfies Record<string, Look>;

interface Star {
  /** UI 像素（不取整：光是连续的） */
  x: number;
  y: number;
  look: Look;
  /** 小一号（远处的、贴边的） */
  small: boolean;
  edge: boolean;
  label: string;
  site: boolean;
  seed: number;
}

interface SkyStar {
  wld: string;
  x: number;
  y: number;
  here: boolean;
  site: boolean;
  seed: number;
}

const tmp = new THREE.Vector3();
const hash = (n: number) => {
  const s = Math.sin(n * 127.1) * 43758.5453;
  return s - Math.floor(s);
};
const clamp01 = (v: number) => Math.min(1, Math.max(0, v));

/** 一颗星：光晕、星芒（根上粗、往外收成尖、渐隐）、亮核。b 是亮度（0..~1.5），arm 乘在星芒长上 */
function shine(g: CanvasRenderingContext2D, x: number, y: number, k: Look, b: number, arm: number, rot: number) {
  if (b <= 0.01) return;
  const R = k.r * (0.6 + 0.4 * b);
  // 两层晕：贴着核的一小团亮的，外面一大圈很淡的
  for (const [r, a] of [
    [R, 0.2],
    [R * 0.3, 0.45],
  ]) {
    const halo = g.createRadialGradient(x, y, 0, x, y, r);
    halo.addColorStop(0, `rgba(${k.glow},${a * b})`);
    halo.addColorStop(0.35, `rgba(${k.glow},${a * 0.4 * b})`);
    halo.addColorStop(1, `rgba(${k.glow},0)`);
    g.fillStyle = halo;
    g.beginPath();
    g.arc(x, y, r, 0, Math.PI * 2);
    g.fill();
  }

  const spike = (ang: number, len: number, wid: number) => {
    if (len < 1) return;
    const c = Math.cos(ang);
    const s = Math.sin(ang);
    const grd = g.createLinearGradient(x, y, x + c * len, y + s * len);
    grd.addColorStop(0, `rgba(255,255,255,${0.6 * b})`);
    grd.addColorStop(0.35, `rgba(${k.glow},${0.3 * b})`);
    grd.addColorStop(1, `rgba(${k.glow},0)`);
    g.fillStyle = grd;
    g.beginPath();
    g.moveTo(x - s * wid, y + c * wid);
    g.lineTo(x + c * len, y + s * len);
    g.lineTo(x + s * wid, y - c * wid);
    g.closePath();
    g.fill();
  };
  const L = k.arm * arm;
  for (let i = 0; i < 4; i++) spike((i * Math.PI) / 2, L, 1.8);
  if (k.diag) for (let i = 0; i < 4; i++) spike(rot + Math.PI / 4 + (i * Math.PI) / 2, L * k.diag, 1.2);

  g.fillStyle = k.core;
  g.globalAlpha = Math.min(0.8, 0.8 * b);
  g.beginPath();
  g.arc(x, y, k.arm ? 2.6 : 1.8, 0, Math.PI * 2);
  g.fill();
  g.globalAlpha = 1;
}

function tag(g: CanvasRenderingContext2D, s: string, cx: number, top: number) {
  const t = text(s, C.ink);
  const W = t.width + 10;
  const H = 18;
  const m = paperMask(W, H, s);
  const x = cx - Math.floor(W / 2);
  paperShadow(g, x + 1, top + 1, W, H, m);
  paper(g, x, top, W, H, m, { fibre: true });
  g.drawImage(t, x + 5, top + 3);
}

export class MapView {
  private want = false;
  private e = 0;
  /** 打开那一刻人的朝向：天上的星座按它摆 */
  private yaw0 = 0;
  private t = 0;
  private g: CanvasRenderingContext2D;
  private stars: Star[] = [];
  private sky: SkyStar[] = [];
  private lines: [{ x: number; y: number }, { x: number; y: number }][] = [];
  private focus: Star | null = null;
  private skyFocus: SkyStar | null = null;
  private lookingUp = false;

  constructor(
    private ui: Ui,
    private label: HTMLElement,
    private glowEl: HTMLCanvasElement,
  ) {
    this.g = glowEl.getContext('2d')!;
  }

  get active() {
    return this.want || this.e > 0;
  }

  toggle(camera: THREE.Camera) {
    if (this.want) {
      this.want = false;
      return;
    }
    this.want = true;
    camera.getWorldDirection(tmp);
    this.yaw0 = Math.atan2(-tmp.x, -tmp.z);
  }

  /** 换世界：直接收起 */
  closeNow() {
    this.want = false;
    this.e = 0;
    this.label.style.opacity = '0';
  }

  update(dt: number) {
    this.t += dt;
    this.e = this.want ? Math.min(1, this.e + dt / OPEN_TIME) : Math.max(0, this.e - dt / CLOSE_TIME);
  }

  /** 暗下来的一圈：从手边那一点（屏幕像素，原点在左下）扩到盖住整个画面 */
  dim(from: { x: number; y: number }, w: number, h: number) {
    if (!this.e) return undefined;
    const far = Math.max(Math.hypot(from.x, from.y), Math.hypot(w - from.x, from.y), Math.hypot(from.x, h - from.y), Math.hypot(w - from.x, h - from.y));
    return { x: from.x, y: from.y, r: ease(this.e) * (far + 24) };
  }

  /** 这颗星亮了几成：按种子错开，一颗颗亮起，收起时倒着灭 */
  private appear(seed: number) {
    return clamp01((this.e - (0.45 + 0.4 * hash(seed))) / 0.14);
  }

  /** 亮度：慢慢呼吸；偶尔一闪（星芒一长） */
  private breath(seed: number) {
    const p = (this.t * 0.35 + hash(seed + 7)) % 1;
    const flash = p < 0.1 ? Math.sin((p / 0.1) * Math.PI) : 0;
    return { b: 0.85 + 0.15 * Math.sin(this.t * 1.9 + seed * 5.3), arm: 1 + 0.08 * Math.sin(this.t * 1.3 + seed) + 0.7 * flash };
  }

  /** 世界画之前：算好每颗星在哪；返回落到世界上的像素星光（屏幕像素，原点在左下，z 是半径） */
  layout(camera: THREE.PerspectiveCamera, c: MapCtx, hidden: boolean): THREE.Vector3[] {
    this.stars = [];
    this.sky = [];
    this.lines = [];
    this.focus = null;
    this.skyFocus = null;
    if (!this.e || hidden) return [];
    camera.updateMatrixWorld();
    const { w, h } = this.ui;
    this.lookingUp = camera.rotation.x > 0.55;

    // ── 本世界 ──
    let seed = 1;
    const all: Star[] = [];
    for (const e of c.level.entrances) {
      if (!e.url) continue;
      all.push(this.place(e.crystal.mesh.position, camera, LOOK.site, e.title || '站点', true, seed++));
    }
    for (const p of c.level.portals) {
      const seen = c.visited.includes(p.to);
      const what = p.title ? ` · ${p.title}` : '';
      all.push(this.place(p.pos, camera, seen ? LOOK.seen : LOOK.unseen, `→ ${seen ? worldName(p.to) : '？'}${what}`, false, seed++));
    }
    let best = 60;
    const margin = 10;
    for (const s of all) {
      if (!this.appear(s.seed)) continue;
      const inside = s.x >= margin && s.x <= w - margin && s.y >= margin && s.y <= h - margin;
      if (!inside) {
        // 画面外：贴在边上，小一号
        if (this.lookingUp) continue;
        const dx = s.x - w / 2;
        const dy = s.y - h / 2;
        const k = Math.min((w / 2 - margin) / Math.max(1e-3, Math.abs(dx)), (h / 2 - margin) / Math.max(1e-3, Math.abs(dy)));
        this.stars.push({ ...s, x: w / 2 + dx * k, y: h / 2 + dy * k, small: true, edge: true });
        continue;
      }
      this.stars.push(s);
      const d = Math.hypot(s.x - w / 2, s.y - h / 2);
      if (d < best) {
        best = d;
        this.focus = s;
      }
    }

    // ── 天上的星座：去过的世界、走过的连接 ──
    if (this.appear(99)) {
      const f0 = new THREE.Vector3(-Math.sin(this.yaw0), 0, -Math.cos(this.yaw0));
      const r0 = new THREE.Vector3(-f0.z, 0, f0.x);
      const at = new Map<string, { x: number; y: number }>();
      c.visited.forEach((wld, i) => {
        const [sx, sy] = starAt(wld, i);
        tmp.set(0, 1, 0).addScaledVector(r0, sx * 0.42).addScaledVector(f0, sy * 0.42).normalize().multiplyScalar(60).add(camera.position).project(camera);
        if (tmp.z >= 1) return;
        const p = { x: (tmp.x * 0.5 + 0.5) * w, y: (0.5 - tmp.y * 0.5) * h };
        at.set(wld, p);
        if (p.x < -8 || p.y < -8 || p.x > w + 8 || p.y > h + 8) return;
        this.sky.push({ wld, ...p, here: wld === c.world, site: c.sites.includes(wld), seed: 50 + i });
      });
      for (const [a, b] of c.edges) {
        const pa = at.get(a);
        const pb = at.get(b);
        if (pa && pb) this.lines.push([pa, pb]);
      }
      let skyBest = 60;
      for (const s of this.sky) {
        const d = Math.hypot(s.x - w / 2, s.y - h / 2);
        if (d < skyBest) {
          skyBest = d;
          this.skyFocus = s;
        }
      }
    }

    // 像素的星光：亮着的、在画面里的星，越亮半径越大
    const glow: THREE.Vector3[] = [];
    const H = h * UI_SCALE;
    const push = (x: number, y: number, look: Look, k: number) => {
      if (glow.length < MAX_GLOW && look.lit && k > 0) glow.push(new THREE.Vector3(x * UI_SCALE, H - y * UI_SCALE, look.lit * k));
    };
    for (const s of this.stars) if (!s.edge) push(s.x, s.y, s.look, this.appear(s.seed) * this.breath(s.seed).b * (s.small ? 0.7 : 1));
    for (const s of this.sky) push(s.x, s.y, s.here ? LOOK.here : LOOK.sky, this.appear(99) * this.breath(s.seed).b);
    return glow;
  }

  /** 世界画完之后：星画在 #glow 上，纸签画在 UI 画布上 */
  draw() {
    this.label.style.opacity = '0';
    const g = this.g;
    const W = this.ui.w * UI_SCALE;
    const H = this.ui.h * UI_SCALE;
    const dpr = Math.min(2, devicePixelRatio || 1);
    if (this.glowEl.width !== Math.round(W * dpr) || this.glowEl.height !== Math.round(H * dpr)) {
      this.glowEl.width = Math.round(W * dpr);
      this.glowEl.height = Math.round(H * dpr);
      this.glowEl.style.width = `${W}px`;
      this.glowEl.style.height = `${H}px`;
    }
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.clearRect(0, 0, this.glowEl.width, this.glowEl.height);
    if (!this.stars.length && !this.sky.length) return;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.globalCompositeOperation = 'lighter';
    const S = UI_SCALE;
    const rot = this.t * 0.25;

    // 连线：两头渐隐，展开时从一头画到另一头
    const grow = clamp01((this.appear(99) - 0.2) / 0.8);
    for (const [a, b] of this.lines) {
      const x0 = a.x * S;
      const y0 = a.y * S;
      const x1 = x0 + (b.x * S - x0) * grow;
      const y1 = y0 + (b.y * S - y0) * grow;
      const grd = g.createLinearGradient(x0, y0, x1, y1);
      grd.addColorStop(0, 'rgba(205,200,219,0)');
      grd.addColorStop(0.15, 'rgba(205,200,219,0.45)');
      grd.addColorStop(0.85, 'rgba(205,200,219,0.45)');
      grd.addColorStop(1, 'rgba(205,200,219,0)');
      g.strokeStyle = grd;
      g.lineWidth = 1;
      g.beginPath();
      g.moveTo(x0, y0);
      g.lineTo(x1, y1);
      g.stroke();
    }

    for (const s of this.stars) {
      const a = this.appear(s.seed);
      const { b, arm } = this.breath(s.seed);
      // 亮起时先闪一下：星芒冲出去再收回
      const pop = 1 + 1.2 * Math.sin(a * Math.PI) * (1 - a * 0.5);
      const k = s.small ? 0.6 : 1;
      shine(g, s.x * S, s.y * S, s.look, a * b * (s.edge ? 0.7 : 1), arm * pop * k, rot);
    }
    for (const s of this.sky) {
      const a = this.appear(99);
      const { b, arm } = this.breath(s.seed);
      shine(g, s.x * S, s.y * S, s.here ? LOOK.here : LOOK.sky, a * b, arm, rot);
      if (s.site) shine(g, s.x * S + 22, s.y * S - 18, LOOK.gold, a * b, arm, rot);
    }
    g.globalCompositeOperation = 'source-over';

    const ui = this.ui.g;
    const f = this.focus;
    if (f && !this.lookingUp) {
      if (f.site) {
        // 站点：全分辨率的平滑字
        this.label.textContent = f.label;
        const r = this.ui.el.getBoundingClientRect();
        this.label.style.left = `${r.left + f.x * S}px`;
        this.label.style.top = `${r.top + (f.y + 22) * S}px`;
        this.label.style.opacity = '1';
      } else tag(ui, f.label, Math.round(f.x), Math.round(f.y) + 16);
    }
    const sf = this.skyFocus;
    if (sf && this.lookingUp) tag(ui, sf.here ? `此刻 · ${worldName(sf.wld)}` : worldName(sf.wld), Math.round(sf.x), Math.round(sf.y) + 14);
  }

  private place(pos: THREE.Vector3, camera: THREE.PerspectiveCamera, look: Look, label: string, site: boolean, seed: number): Star {
    const small = camera.position.distanceTo(pos) > 10;
    tmp.copy(pos).applyMatrix4(camera.matrixWorldInverse);
    const behind = tmp.z > 0;
    tmp.copy(pos).project(camera);
    let x = (tmp.x * 0.5 + 0.5) * this.ui.w;
    let y = (0.5 - tmp.y * 0.5) * this.ui.h;
    if (behind) {
      // 身后的：投影是反的，翻过来并推到画面外
      x = this.ui.w / 2 - (x - this.ui.w / 2) * 1e3;
      y = this.ui.h / 2 - (y - this.ui.h / 2) * 1e3;
    }
    return { x, y, look, small, edge: false, label, site, seed };
  }
}
