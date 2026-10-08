/* 交互提示：一张系在东西上的小纸签。
   走近、看着它：纸签从东西那里升起来，先是空白的背面，一翻，正面是「[E] 标题」。
   移开视线：压扁成一条边，收走。转头时纸签跟着线晃一下，慢半拍。按 E，键帽按下去。 */
import * as THREE from 'three';
import type { Promptable } from './items/system';
import { C, inkRows, line, paper, paperMask, paperShadow, scratch, text, type Ui } from './ui';

const PAD_X = 4;
const H = 18;
/** 纸签底边离系线的结（东西的位置）多高，UI 像素 */
const LIFT = 22;
/** 翻面速度，度/秒：出现从 270° 转到 0°（背面 → 侧边 → 正面），收走从 0° 转到 90° */
const IN_SPEED = 900;
const OUT_SPEED = 600;

interface Face {
  w: number;
  mask: Uint8Array;
  title: HTMLCanvasElement;
  key: HTMLCanvasElement;
  capW: number;
}

/** 竖直排版：汉字的墨迹在纸签里上下居中；键帽比汉字上下各多一格，底下再多一格厚度；E 在键帽里居中 */
let layout: { titleY: number; capY: number; capH: number; keyY: number } | null = null;
function vertical(key: HTMLCanvasElement) {
  const [t, b] = inkRows(text('国'));
  const titleY = Math.floor((H - (b - t + 1)) / 2) - t;
  const capY = titleY + t - 1;
  const capH = b - t + 4;
  const [kt, kb] = inkRows(key);
  const keyY = capY + Math.floor((capH - 1 - (kb - kt + 1)) / 2) - kt;
  return { titleY, capY, capH, keyY };
}

const v = new THREE.Vector3();

export class PromptTag {
  private ui: Ui;
  private cur: Promptable | null = null;
  private face: Face | null = null;
  private phase: 'hidden' | 'in' | 'shown' | 'out' = 'hidden';
  private ang = 90;
  /** 纸签中心底边（UI 像素，带弹簧） */
  private pos = new THREE.Vector2();
  private vel = new THREE.Vector2();
  private pressT = 0;
  private buf = scratch(1, 1);

  constructor(ui: Ui) {
    this.ui = ui;
  }

  press() {
    this.pressT = 0.2;
  }

  update(dt: number, want: Promptable | null, camera: THREE.Camera) {
    this.pressT = Math.max(0, this.pressT - dt);
    if (want !== this.cur) {
      if (this.cur && this.phase !== 'hidden') this.phase = 'out';
      else if (want) this.show(want, camera);
    } else if (want && this.phase === 'out') this.phase = 'in';

    if (this.phase === 'in') {
      this.ang = Math.max(0, this.ang - IN_SPEED * dt);
      if (this.ang === 0) this.phase = 'shown';
    } else if (this.phase === 'out') {
      this.ang = Math.min(90, this.ang + OUT_SPEED * dt);
      if (this.ang === 90) {
        this.phase = 'hidden';
        this.cur = null;
      }
    }
    if (!this.cur || !this.face) return;

    const a = this.anchor(camera);
    if (!a) return;
    const { w, h } = this.ui;
    const fw = this.face.w;
    const tx = THREE.MathUtils.clamp(a.x, fw / 2 + 4, w - fw / 2 - 4);
    const ty = THREE.MathUtils.clamp(a.y - LIFT, H + 4, h - 4);
    // 弹簧：慢半拍、略过头一点点
    const k = 140;
    const c = 17;
    this.vel.x += ((tx - this.pos.x) * k - this.vel.x * c) * dt;
    this.vel.y += ((ty - this.pos.y) * k - this.vel.y * c) * dt;
    this.pos.addScaledVector(this.vel, dt);
    this.draw(a.x, a.y);
  }

  private show(p: Promptable, camera: THREE.Camera) {
    this.cur = p;
    this.face = this.build(p.title || '……');
    this.phase = 'in';
    this.ang = 270;
    // 从结那里升起来
    const a = this.anchor(camera);
    if (a) this.pos.set(a.x, a.y - 2);
    this.vel.set(0, 0);
  }

  private build(title: string): Face {
    const t = text(title, C.ink);
    const key = text('E', C.paper);
    const capW = key.width + 5;
    const w = PAD_X + capW + 4 + t.width + PAD_X;
    return { w, mask: paperMask(w, H, title), title: t, key, capW };
  }

  /** 东西在 UI 画布上的位置；在身后就没有 */
  private anchor(camera: THREE.Camera) {
    v.copy(this.cur!.pos).project(camera);
    if (v.z > 1 || v.z < -1) return null;
    return { x: Math.round((v.x * 0.5 + 0.5) * this.ui.w), y: Math.round((0.5 - v.y * 0.5) * this.ui.h) };
  }

  private draw(ax: number, ay: number) {
    const f = this.face!;
    const W = f.w;
    const cos = Math.cos(this.ang * (Math.PI / 180));
    const dw = Math.round(W * Math.abs(cos));
    if (dw < 1) return;
    const back = cos < 0;

    // 先画整张纸签（含影子）到离屏，再按翻面压扁贴上去
    if (this.buf.c.width !== W + 1 || this.buf.c.height !== H + 1) this.buf = scratch(W + 1, H + 1);
    const g = this.buf.g;
    g.clearRect(0, 0, W + 1, H + 1);
    paperShadow(g, 1, 1, W, H, f.mask);
    paper(g, 0, 0, W, H, f.mask, { fill: back ? C.back : C.paper, fibre: true });
    if (!back) {
      // 键帽：墨色方块，底下一格深色当厚度；按下时整块沉一格、厚度没了
      const down = this.pressT > 0 ? 1 : 0;
      const cx = PAD_X;
      const L = (layout ??= vertical(f.key));
      const cy = L.capY + down;
      const ch = L.capH - down;
      g.fillStyle = C.ink;
      g.fillRect(cx, cy, f.capW, ch);
      g.fillStyle = C.inkDeep;
      if (!down) g.fillRect(cx, cy + ch - 1, f.capW, 1);
      // 键帽上两角剪圆
      g.fillStyle = C.paper;
      g.fillRect(cx, cy, 1, 1);
      g.fillRect(cx + f.capW - 1, cy, 1, 1);
      g.drawImage(f.key, cx + 3, L.keyY + down);
      g.drawImage(f.title, PAD_X + f.capW + 4, L.titleY);
    }

    const ui = this.ui.g;
    const px = Math.round(this.pos.x);
    const py = Math.round(this.pos.y);
    const left = px - Math.floor(dw / 2);
    // 系线：从纸签底边中点垂到东西上，末端一个结
    line(ui, px, py, ax, ay, C.thread);
    ui.fillStyle = C.ink;
    ui.fillRect(ax - 1, ay - 1, 2, 2);
    ui.drawImage(this.buf.c, 0, 0, W + 1, H + 1, left, py - H, dw + 1, H + 1);
  }
}
