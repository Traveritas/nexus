/* 一片夜的地图：用到底，世界从手边那一点暗下去（pipeline 的 dim），星星一颗颗亮起来。
   - 星是连续的光：画在全分辨率的 #glow 画布上（叠加发亮），一颗亮核、一团光晕、细长的星芒；亮度慢慢呼吸，偶尔星芒一长。
     亮起时先闪一下再落定。星光落到暗下去的世界上是像素的：星的周围按格子撤回一两档暗（pipeline 的 glow）。
   - 本世界：每个出入口（传送物、缝）与站点（晶体）一颗星，隔着墙也看得见；不标物品。
       站点：金，大，另有一对慢慢转的斜芒 · 去过的世界的出口：白，雾蓝的晕 · 没去过的：暗紫，一点微光，没有芒。
       通往别的主域的：冷绿的晕，外面套一圈慢慢转、断成两截的环；纸签写「→ 旧梦 · 旧家」，没去过的「→ 旧梦 · ？」。
       远处的小一号；画面外的贴在屏幕边上。正看着的那颗挂一张纸签，只写通往哪里：「→ 浅滩」，没去过的「→ ？」；
       站点的名字连着真实的站点，是「现实的字」（#maplabel，src/realtext.ts），换到它时对一次焦。
   - 抬头看天：只画此刻所在的主域——去过的世界是天上的星座，走过的连接是星与星之间两头渐隐的细线，展开时一笔画出来；
     有站点的世界旁边一颗小金星。走过的、通往别的主域的连接：从那颗星往星座外面伸出一截冷绿的线，末端一颗带环的星。
   - 开着时照常走、转头；再用到底一次收起来（暗色缩回手边）；换世界时直接收起。
   每帧先 layout（世界画之前，像素的星光要用），再 draw。 */
import * as THREE from 'three';
import type { Level } from './level';
import { MAX_GLOW } from './pipeline';
import { ease } from './stage';
import { UI_SCALE, paper, paperMask, paperShadow, text, C, type Ui } from './ui';
import { PALETTE } from './palette';
import { RealName } from './realtext';
import { realmName, realmOf, starAt, worldName } from './worlds';
import { t } from './i18n';

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
  /** 通往别的主域：冷绿（色板里只有它没用在星上），另套一圈环（ring） */
  cross: { glow: '134,181,165', r: 34, arm: 30, diag: 0, core: '#fff4f4', lit: 42 },
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
  url?: string;
  /** 通往别的主域 */
  cross?: boolean;
}

interface SkyStar {
  wld: string;
  x: number;
  y: number;
  here: boolean;
  site: boolean;
  seed: number;
  /** 星座外面那颗：通往别的主域（wld 是那边的世界） */
  gate?: boolean;
}

/** 本世界的一个出入口：站点（晶体）· 去过的 · 没去过的 · 通往别的主域的 */
export interface Exit {
  pos: THREE.Vector3;
  kind: 'site' | 'seen' | 'unseen' | 'cross';
  /** 通往的世界（站点没有） */
  to: string;
  title?: string;
  url?: string;
}

/** 本世界的出入口：地图上的星、一片夜里的小星都按它 */
export function exitsOf(level: Level, world: string, visited: string[]): Exit[] {
  const out: Exit[] = [];
  for (const e of level.entrances) if (e.url) out.push({ pos: e.crystal.mesh.position, kind: 'site', to: '', title: e.title, url: e.url });
  const realm = realmOf(world);
  const exit = (pos: THREE.Vector3, to: string) => {
    const other = realmOf(to);
    out.push({ pos, to, kind: realm && other && other !== realm ? 'cross' : visited.includes(to) ? 'seen' : 'unseen' });
  };
  for (const p of level.portals) exit(p.pos, p.to);
  // 缝（家的大门）也是出入口：星在门洞正中
  for (const s of level.seams) exit(s.pos.clone().setY(s.pos.y + s.h / 2), s.to);
  return out;
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

/** 通往别的主域的环：断成两截的一圈，慢慢转。r 是半径（屏幕像素），b 亮度 */
function ring(g: CanvasRenderingContext2D, x: number, y: number, r: number, glow: string, b: number, rot: number) {
  if (b <= 0.01) return;
  g.strokeStyle = `rgba(${glow},${0.55 * b})`;
  g.lineWidth = 1.5;
  for (let i = 0; i < 2; i++) {
    g.beginPath();
    g.arc(x, y, r, rot + i * Math.PI, rot + i * Math.PI + Math.PI * 0.72);
    g.stroke();
  }
}

/** 同一圈环在像素层上再画一遍（1 格、色板的冷绿）：星光那层是叠加发亮的，亮的地方细线会被吃掉 */
function pixelRing(g: CanvasRenderingContext2D, x: number, y: number, r: number, rot: number) {
  g.fillStyle = PALETTE[15];
  const n = Math.ceil(r * 8);
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2;
    // 两截，各占 0.72π
    const u = (((a - rot) % Math.PI) + Math.PI) % Math.PI;
    if (u > Math.PI * 0.72) continue;
    g.fillRect(Math.round(x + Math.cos(a) * r), Math.round(y + Math.sin(a) * r), 1, 1);
  }
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
  /** 第三个值：通往别的主域的那截（冷绿） */
  private lines: [{ x: number; y: number }, { x: number; y: number }, boolean][] = [];
  private focus: Star | null = null;
  private skyFocus: SkyStar | null = null;
  private lookingUp = false;
  private name: RealName;
  /** 站点名字的对焦：换到一颗站点星时从 0 起 */
  private nameF = 0;
  private nameOf: Star | null = null;

  constructor(
    private ui: Ui,
    private label: HTMLElement,
    private glowEl: HTMLCanvasElement,
  ) {
    this.g = glowEl.getContext('2d')!;
    this.name = new RealName(label);
  }

  /** 开着（或正要开）：收起的那一下已经不算 */
  get open() {
    return this.want;
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
    this.name.focus(0);
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
    const realm = realmOf(c.world);
    for (const x of exitsOf(c.level, c.world, c.visited)) {
      const name = x.kind === 'unseen' || !c.visited.includes(x.to) ? '？' : worldName(x.to);
      if (x.kind === 'site') all.push(this.place(x.pos, camera, LOOK.site, x.title || t('site'), true, seed++, x.url));
      else if (x.kind === 'cross') {
        const s = this.place(x.pos, camera, LOOK.cross, `→ ${realmName(realmOf(x.to)!)} · ${name}`, false, seed++);
        s.cross = true;
        all.push(s);
      } else all.push(this.place(x.pos, camera, LOOK[x.kind], `→ ${name}`, false, seed++));
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

    // ── 天上的星座：此刻所在的主域里去过的世界、走过的连接 ──
    if (this.appear(99)) {
      const f0 = new THREE.Vector3(-Math.sin(this.yaw0), 0, -Math.cos(this.yaw0));
      const r0 = new THREE.Vector3(-f0.z, 0, f0.x);
      /** 星座平面上的一点 → 画面（在身后就没有） */
      const sky = (sx: number, sy: number) => {
        tmp.set(0, 1, 0).addScaledVector(r0, sx * 0.42).addScaledVector(f0, sy * 0.42).normalize().multiplyScalar(60).add(camera.position).project(camera);
        return tmp.z >= 1 ? null : { x: (tmp.x * 0.5 + 0.5) * w, y: (0.5 - tmp.y * 0.5) * h };
      };
      const onScreen = (p: { x: number; y: number }) => p.x >= -8 && p.y >= -8 && p.x <= w + 8 && p.y <= h + 8;
      // 不在任何主域里（现实、样板）：只有自己这一颗
      const mine = (wld: string) => (realm ? realmOf(wld) === realm : wld === c.world);
      const at = new Map<string, { x: number; y: number }>();
      const pos = new Map<string, [number, number]>();
      c.visited.filter(mine).forEach((wld, i) => {
        const xy = starAt(wld, i);
        pos.set(wld, xy);
        const p = sky(...xy);
        if (!p) return;
        at.set(wld, p);
        if (onScreen(p)) this.sky.push({ wld, ...p, here: wld === c.world, site: c.sites.includes(wld), seed: 50 + i });
      });
      let gates = 0;
      /** 每颗星已经伸出去的方向 */
      const used = new Map<string, number[]>();
      for (const [a, b] of c.edges) {
        const pa = at.get(a);
        const pb = at.get(b);
        if (pa && pb) {
          this.lines.push([pa, pb, false]);
          continue;
        }
        // 一头在这个主域、另一头在别的主域：从这头往星座外面伸出一截，末端一颗带环的星
        const inn = pa ? a : pb ? b : null;
        const out = pa ? b : a;
        const other = realmOf(out);
        if (!inn || !realm || !other || other === realm) continue;
        const [sx, sy] = pos.get(inn)!;
        // 往四周最空的方向伸出去：离这颗星连出去的别的星、已经伸出去的那几截都尽量远，同样空时偏向背离星座中心
        const taken = [...pos].filter(([w]) => w !== inn).map(([, [x, y]]) => Math.atan2(y - sy, x - sx)).concat(used.get(inn) ?? []);
        let ang = 0;
        let bestGap = -1;
        for (let k = 0; k < 24; k++) {
          const t0 = (k / 24) * Math.PI * 2;
          const gap = Math.min(Math.PI, ...taken.map((t1) => Math.abs(((t0 - t1 + Math.PI * 3) % (Math.PI * 2)) - Math.PI)));
          const score = gap + 0.15 * Math.cos(t0 - Math.atan2(sy, sx));
          if (score > bestGap) {
            bestGap = score;
            ang = t0;
          }
        }
        used.set(inn, [...(used.get(inn) ?? []), ang]);
        gates++;
        const gp = sky(sx + Math.cos(ang) * 0.9, sy + Math.sin(ang) * 0.9);
        if (!gp) continue;
        this.lines.push([at.get(inn)!, gp, true]);
        if (onScreen(gp)) this.sky.push({ wld: out, ...gp, here: false, site: false, seed: 80 + gates, gate: true });
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
    for (const s of this.sky) push(s.x, s.y, s.gate ? LOOK.cross : s.here ? LOOK.here : LOOK.sky, this.appear(99) * this.breath(s.seed).b);
    return glow;
  }

  /** 世界画完之后：星画在 #glow 上，纸签画在 UI 画布上 */
  draw() {
    let named: Star | null = null;
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
    for (const [a, b, out] of this.lines) {
      const x0 = a.x * S;
      const y0 = a.y * S;
      const x1 = x0 + (b.x * S - x0) * grow;
      const y1 = y0 + (b.y * S - y0) * grow;
      const grd = g.createLinearGradient(x0, y0, x1, y1);
      // 通往别的主域的那截：冷绿，离开星座以后淡下去，快到环那里亮回来一点
      const col = out ? '134,181,165' : '205,200,219';
      grd.addColorStop(0, `rgba(${col},0)`);
      grd.addColorStop(0.15, `rgba(${col},0.45)`);
      grd.addColorStop(out ? 0.5 : 0.85, `rgba(${col},${out ? 0.15 : 0.45})`);
      grd.addColorStop(out ? 0.85 : 1, `rgba(${col},${out ? 0.4 : 0})`);
      if (out) grd.addColorStop(1, `rgba(${col},0)`);
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
      if (s.cross) ring(g, s.x * S, s.y * S, (s.small ? 16 : 24) * (0.9 + 0.1 * b), s.look.glow, a * b, rot * 2 + s.seed);
    }
    for (const s of this.sky) {
      const a = this.appear(99);
      const { b, arm } = this.breath(s.seed);
      shine(g, s.x * S, s.y * S, s.gate ? LOOK.cross : s.here ? LOOK.here : LOOK.sky, a * b, arm, rot);
      if (s.gate) ring(g, s.x * S, s.y * S, 20, LOOK.cross.glow, a * b, rot * 2 + s.seed);
      if (s.site) shine(g, s.x * S + 22, s.y * S - 18, LOOK.gold, a * b, arm, rot);
    }
    g.globalCompositeOperation = 'source-over';

    const ui = this.ui.g;
    for (const s of this.stars) if (s.cross && this.appear(s.seed) > 0.5) pixelRing(ui, s.x, s.y, s.small ? 7 : 10, rot * 2 + s.seed);
    if (this.appear(99) > 0.5) for (const s of this.sky) if (s.gate) pixelRing(ui, s.x, s.y, 9, rot * 2 + s.seed);
    const f = this.focus;
    if (f && !this.lookingUp) {
      if (f.site) {
        // 站点：现实的字，对着焦浮出来
        named = f;
        this.name.set(f.label, f.url);
        const r = this.ui.el.getBoundingClientRect();
        this.label.style.left = `${r.left + f.x * S}px`;
        this.label.style.top = `${r.top + (f.y + 16) * S}px`;
      } else tag(ui, f.label, Math.round(f.x), Math.round(f.y) + 16);
    }
    if (named?.label !== this.nameOf?.label) this.nameF = 0;
    this.nameOf = named;
    this.nameF = named ? Math.min(1, this.nameF + 1 / 30) : 0;
    this.name.focus(ease(this.nameF));
    const sf = this.skyFocus;
    if (sf && this.lookingUp) {
      const other = sf.gate ? realmOf(sf.wld) : null;
      const s = other ? `→ ${realmName(other)} · ${worldName(sf.wld)}` : sf.here ? `${t('here')} · ${worldName(sf.wld)}` : worldName(sf.wld);
      tag(ui, s, Math.round(sf.x), Math.round(sf.y) + 14);
    }
  }

  private place(pos: THREE.Vector3, camera: THREE.PerspectiveCamera, look: Look, label: string, site: boolean, seed: number, url?: string): Star {
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
    return { x, y, look, small, edge: false, label, site, seed, url };
  }
}
