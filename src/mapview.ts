/* 罗盘的地图：捏到底，世界从手边那一点暗下去（pipeline 的 dim），星星一颗颗亮起来。
   - 本世界：每个出入口（传送物）与站点（晶体）一颗白色四芒星，隔着墙也看得见；不标物品。
       站点：大，金芯，四角各一颗金点 · 去过的世界的出口：白，雾蓝芯 · 没去过的：暗紫、小一号。
       远处的小一号；画面外的贴在屏幕边上。正看着的那颗挂一张纸签：「→ 浅滩 · 一杯水」，没去过的「→ ？」；
       站点的名字连着真实的站点，用全分辨率的平滑字（#maplabel）。
   - 抬头看天：去过的世界是天上的星座，走过的连接是星与星之间的细线；有站点的世界旁边一颗小金星。
   - 开着时照常走、转头；再捏到底一次收起来（暗色缩回手边）；换世界时直接收起。 */
import * as THREE from 'three';
import type { Level } from './level';
import { PALETTE } from './palette';
import { ease } from './stage';
import { C, UI_SCALE, line, paper, paperMask, paperShadow, text, type Ui } from './ui';
import { starAt, worldName } from './worlds';

const P = (i: number) => PALETTE[i];
const OPEN_TIME = 0.9;
const CLOSE_TIME = 0.5;

export interface MapCtx {
  level: Level;
  world: string;
  visited: string[];
  edges: [string, string][];
  sites: string[];
}

interface Star {
  x: number;
  y: number;
  /** 0 站点 · 1 去过的出口 · 2 没去过的出口 */
  kind: 0 | 1 | 2;
  far: boolean;
  label: string;
  site: boolean;
  seed: number;
}

const tmp = new THREE.Vector3();
const hash = (n: number) => {
  const s = Math.sin(n * 127.1) * 43758.5453;
  return s - Math.floor(s);
};

/** 四芒星：中心一个菱形，四条臂各长 s 格（大的靠中心那段加粗）；先描一圈墨，再填色 */
function star(g: CanvasRenderingContext2D, x: number, y: number, s: number, fill: string, core: string, outline = C.ink) {
  const pts = new Set<string>();
  const add = (i: number, j: number) => pts.add(`${i},${j}`);
  // 中心一个菱形；四条臂靠中心那段三格宽，往外收成一格的尖
  const rad = s >= 4 ? 2 : 1;
  for (let i = -rad; i <= rad; i++) for (let j = -rad; j <= rad; j++) if (Math.abs(i) + Math.abs(j) <= rad) add(i, j);
  for (let k = 1; k <= s; k++) {
    const hw = k <= Math.ceil(s * 0.45) && s >= 4 ? 1 : 0;
    for (let q = -hw; q <= hw; q++) {
      add(k, q);
      add(-k, q);
      add(q, k);
      add(q, -k);
    }
  }
  g.fillStyle = outline;
  for (const p of pts) {
    const [i, j] = p.split(',').map(Number);
    for (const [di, dj] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) if (!pts.has(`${i + di},${j + dj}`)) g.fillRect(x + i + di, y + j + dj, 1, 1);
  }
  g.fillStyle = fill;
  for (const p of pts) {
    const [i, j] = p.split(',').map(Number);
    g.fillRect(x + i, y + j, 1, 1);
  }
  g.fillStyle = core;
  g.fillRect(x, y, 1, 1);
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

  constructor(
    private ui: Ui,
    private label: HTMLElement,
  ) {}

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

  /** 星星画在 UI 画布上；hidden（日记、环绕展示开着）时不画 */
  draw(camera: THREE.PerspectiveCamera, c: MapCtx, hidden: boolean) {
    this.label.style.opacity = '0';
    if (!this.e || hidden) return;
    const g = this.ui.g;
    const { w, h } = this.ui;
    const shown = (seed: number) => this.e > 0.45 + 0.4 * hash(seed);
    const twinkle = (seed: number) => (this.t * 0.6 + hash(seed + 7)) % 1 < 0.06;
    const lookingUp = camera.rotation.x > 0.55;

    // ── 本世界 ──
    const stars: Star[] = [];
    let seed = 1;
    for (const e of c.level.entrances) {
      if (!e.url) continue;
      stars.push(this.place(e.crystal.mesh.position, camera, 0, e.title || '站点', true, seed++));
    }
    for (const p of c.level.portals) {
      const seen = c.visited.includes(p.to);
      const what = p.title ? ` · ${p.title}` : '';
      stars.push(this.place(p.pos, camera, seen ? 1 : 2, `→ ${seen ? worldName(p.to) : '？'}${what}`, false, seed++));
    }
    let focus: Star | null = null;
    let best = 60;
    const margin = 10;
    for (const s of stars) {
      if (!shown(s.seed)) continue;
      const inside = s.x >= margin && s.x <= w - margin && s.y >= margin && s.y <= h - margin;
      if (!inside) {
        // 画面外：贴在边上，小一号
        if (lookingUp) continue;
        const dx = s.x - w / 2;
        const dy = s.y - h / 2;
        const k = Math.min((w / 2 - margin) / Math.max(1e-3, Math.abs(dx)), (h / 2 - margin) / Math.max(1e-3, Math.abs(dy)));
        star(g, Math.round(w / 2 + dx * k), Math.round(h / 2 + dy * k), 1, s.kind === 2 ? P(4) : C.paper, s.kind === 0 ? P(14) : C.paper);
        continue;
      }
      const x = Math.round(s.x);
      const y = Math.round(s.y);
      let size = s.kind === 0 ? 7 : s.kind === 1 ? 5 : 4;
      if (s.far) size -= 1;
      if (twinkle(s.seed)) size -= 1;
      if (s.kind === 0) {
        star(g, x, y, size, C.paper, P(14));
        g.fillStyle = P(14);
        g.fillRect(x - 1, y, 3, 1);
        g.fillRect(x, y - 1, 1, 3);
        for (const [i, j] of [[4, 4], [4, -4], [-4, 4], [-4, -4]]) g.fillRect(x + i, y + j, 1, 1);
      } else if (s.kind === 1) star(g, x, y, size, C.paper, P(13));
      else star(g, x, y, size, P(4), P(1));
      const d = Math.hypot(s.x - w / 2, s.y - h / 2);
      if (d < best) {
        best = d;
        focus = s;
      }
    }
    if (focus && !lookingUp) {
      if (focus.site) {
        // 站点：全分辨率的平滑字
        this.label.textContent = focus.label;
        const r = this.ui.el.getBoundingClientRect();
        this.label.style.left = `${r.left + focus.x * UI_SCALE}px`;
        this.label.style.top = `${r.top + (focus.y + 12) * UI_SCALE}px`;
        this.label.style.opacity = '1';
      } else tag(g, focus.label, Math.round(focus.x), Math.round(focus.y) + 10);
    }

    // ── 天上的星座：去过的世界、走过的连接 ──
    const f0 = new THREE.Vector3(-Math.sin(this.yaw0), 0, -Math.cos(this.yaw0));
    const r0 = new THREE.Vector3(-f0.z, 0, f0.x);
    const sky = new Map<string, { x: number; y: number } | null>();
    c.visited.forEach((wld, i) => {
      const [sx, sy] = starAt(wld, i);
      tmp.set(0, 1, 0).addScaledVector(r0, sx * 0.42).addScaledVector(f0, sy * 0.42).normalize().multiplyScalar(60).add(camera.position).project(camera);
      sky.set(wld, tmp.z < 1 ? { x: (tmp.x * 0.5 + 0.5) * w, y: (0.5 - tmp.y * 0.5) * h } : null);
    });
    if (!shown(99)) return;
    for (const [a, b] of c.edges) {
      const pa = sky.get(a);
      const pb = sky.get(b);
      if (!pa || !pb) continue;
      line(g, Math.round(pa.x), Math.round(pa.y), Math.round(pb.x), Math.round(pb.y), P(5));
    }
    let skyFocus: string | null = null;
    let skyBest = 60;
    c.visited.forEach((wld, i) => {
      const p = sky.get(wld);
      if (!p || p.x < -8 || p.y < -8 || p.x > w + 8 || p.y > h + 8) return;
      const x = Math.round(p.x);
      const y = Math.round(p.y);
      const here = wld === c.world;
      star(g, x, y, (here ? 5 : 4) - (twinkle(50 + i) ? 1 : 0), C.paper, here ? P(10) : C.paper);
      if (c.sites.includes(wld)) star(g, x + 6, y - 5, 1, P(14), P(14));
      const d = Math.hypot(p.x - w / 2, p.y - h / 2);
      if (d < skyBest) {
        skyBest = d;
        skyFocus = wld;
      }
    });
    if (skyFocus && lookingUp) {
      const p = sky.get(skyFocus)!;
      tag(g, skyFocus === c.world ? `此刻 · ${worldName(skyFocus)}` : worldName(skyFocus), Math.round(p.x), Math.round(p.y) + 9);
    }
  }

  private place(pos: THREE.Vector3, camera: THREE.PerspectiveCamera, kind: 0 | 1 | 2, label: string, site: boolean, seed: number): Star {
    const far = camera.position.distanceTo(pos) > 10;
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
    return { x, y, kind, far, label, site, seed };
  }
}
