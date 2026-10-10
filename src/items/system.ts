/* 物品系统：世界里摆着的物品、怎么得到、得到时的演出、存档、拿在手里与「捏」、环绕展示（F）。
   - 摆放来自场景（nx_type=item）；已经有了的不再摆出来。物品有 world() 就摆它自己的装置，没有就是一张浮着的纸片。
   - pick：走近、看着它，纸签「拾起」，按 E；reach：走进范围就得到；custom：物品自己的 check() 满足就得到。
   - 默认演出：东西变成一张卡片，翻过来飞到眼前，四周一下子解析清楚；停一会儿，缩小飞进右下角，日记那里闪一下。
   - 拿着的东西平时收着；按住 Q 从画面右下（手边）举起来、捏紧，松开放下。它是 3D 的，画在手边场景（hand）里，
     和世界一起像素化、落色板、描边（见 pipeline 的 overlay）。
   - 按住 F：身上的东西排成一道弧，围在眼前齐眼高的地方；世界犯困，正看着的那件清醒过来、挂上名字；松开 F 拿起它。 */
import * as THREE from 'three';
import type { FieldSource } from '../pipeline';
import type { ItemPlace, Level } from '../level';
import { paper as paperMat, shadowVariant, newId, TEXEL } from '../materials';
import { crisp } from '../sprites';
import { PALETTE } from '../palette';
import { clamp01, ease } from '../stage';
import { C, UI_SCALE, paper, paperMask, paperShadow, scratch, text, type Ui } from '../ui';
import { itemDef, type HeldModel, type ItemCtx, type ItemDef, type Shown } from './item';
import { isReality } from '../worlds';

const STORE_KEY = 'nexus:items';
const P = (i: number) => PALETTE[i];

export interface Owned {
  id: string;
  /** 在哪个世界得到的 */
  world: string;
  night: number;
}

/** 纸签能挂的东西（传送物与物品共用） */
export interface Promptable {
  pos: THREE.Vector3;
  title: string;
}

interface Placed {
  place: ItemPlace;
  def: ItemDef;
  holder: THREE.Group;
  /** 物品自己的样子（有就不浮不转，由它自己动） */
  shown: Shown | null;
  prompt: Promptable;
}

/** 得到时的演出（默认那套） */
interface Reveal {
  def: ItemDef;
  t: number;
  /** 起点：东西在 UI 画布上的位置 */
  from: THREE.Vector2;
  card: HTMLCanvasElement;
}
const R_IN = 0.45;
const R_HOLD = 1.9;
const R_OUT = 2.4;
const R_END = 3.4;

/** 手里的东西：离眼睛多远、往右往下偏多少（米），缩放 */
const HAND = { fwd: 0.5, right: 0.19, down: 0.11, scale: 0.75 };
/** 环绕：半径、相邻两件隔多少弧度、比眼睛低多少、缩放 */
const RING = { radius: 0.95, step: 0.7, drop: 0.3, scale: 0.85 };

interface RingShow {
  id: string;
  shown: Shown;
  angle: number;
}

const tmp = new THREE.Vector3();
const right = new THREE.Vector3();
const up = new THREE.Vector3();
const fwd = new THREE.Vector3();
const tilt = new THREE.Quaternion().setFromEuler(new THREE.Euler(0.2, -0.45, 0));

/** 一件物品摆出来的样子：它自己的装置，或者一张纸片 */
function showOf(def: ItemDef): Shown {
  if (def.world) {
    const s = def.world();
    s.object.traverse((o) => {
      const m = o as THREE.Mesh;
      if (m.isMesh) m.userData.shadowMat ??= shadowVariant(m.material as THREE.ShaderMaterial);
    });
    return s;
  }
  const ic = def.icon();
  const geo = new THREE.PlaneGeometry(ic.width / TEXEL, ic.height / TEXEL);
  geo.translate(0, ic.height / TEXEL / 2 + 0.1, 0);
  const m = paperMat(crisp(ic), { back: 6, id: newId() });
  // 纸片不投影
  return { object: new THREE.Mesh(geo, m) };
}

export class ItemSystem {
  owned: Owned[] = [];
  held: string | null = null;
  /** 手边场景：拿在手里的、环绕展示的。主循环把它作为 overlay 交给管线 */
  readonly hand = new THREE.Scene();
  private places: Placed[] = [];
  private level: Level | null = null;
  private world = '';
  private reveal: Reveal | null = null;
  private model: { id: string; m: HeldModel } | null = null;
  private want = false;
  private raise = 0;
  private press = 0;
  // 环绕
  private ringWant = false;
  private ringE = 0;
  private ringYaw = 0;
  private ring: RingShow[] = [];
  private focus: RingShow | null = null;
  private emptyT = 0;
  /** 在现实里：身上的东西拿不出来——不能举、不能环绕，拿着的那件也收着；按 F 只出一张纸签 */
  private sealed = false;
  private sealedT = 0;
  /** 捏到底时（主循环接上罗盘的地图） */
  onBloom?: (id: string) => void;

  constructor(
    private ui: Ui,
    private night: () => number,
  ) {
    this.load();
  }

  // ── 存档 ──
  private load() {
    try {
      const s = JSON.parse(localStorage.getItem(STORE_KEY) ?? '{}');
      this.owned = (s.owned ?? []).filter((o: Owned) => itemDef(o.id));
      this.held = s.held && this.has(s.held) ? s.held : null;
    } catch {
      /* 从空的开始 */
    }
  }

  private save() {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify({ owned: this.owned, held: this.held }));
    } catch {
      /* 存不了就算了 */
    }
  }

  has(id: string) {
    return this.owned.some((o) => o.id === id);
  }

  /** 拿起一件（null ＝ 收起来） */
  hold(id: string | null) {
    this.held = id && this.has(id) ? id : null;
    this.want = false;
    this.save();
  }

  /** 忘掉所有物品（测试用） */
  reset() {
    this.owned = [];
    this.held = null;
    this.save();
    if (this.level) this.attach(this.level, this.world);
  }

  // ── 世界里摆着的 ──
  /** 换了世界：把还没得到的物品摆出来 */
  attach(level: Level, world: string) {
    for (const p of this.places) p.holder.removeFromParent();
    this.places = [];
    this.level = level;
    this.world = world;
    this.sealed = isReality(world);
    if (this.sealed) {
      this.want = false;
      this.ringWant = false;
    }
    for (const place of level.items) this.place(place);
  }

  /** 摆一件（场景里读来的，或测试时临时放的） */
  place(place: ItemPlace) {
    const def = itemDef(place.item);
    if (!def || !this.level || this.has(def.id) || this.places.some((p) => p.def === def)) return;
    const holder = new THREE.Group();
    holder.position.copy(place.pos);
    let shown: Shown | null = null;
    if (def.world) {
      shown = showOf(def);
      holder.add(shown.object);
    } else if (place.mode !== 'custom') {
      // 纸片：以位置为中心浮着；正面朝人，左右轻轻摆
      const s = showOf(def);
      (s.object as THREE.Mesh).geometry.center();
      holder.add(s.object);
    }
    this.level.scene.add(holder);
    // 纸签系在东西上：装置系在它浮着的那一点
    const at = shown ? place.pos.clone().setY(place.pos.y + 0.32) : place.pos;
    this.places.push({ place, def, holder, shown, prompt: { pos: at, title: '拾起' } });
  }

  /** 眼前可以拾起的那一件，和它离眼睛多远 */
  promptAt(eye: THREE.Vector3, look: THREE.Vector3): { p: Promptable; d: number } | null {
    if (this.reveal || this.ringActive) return null;
    let best: { p: Promptable; d: number } | null = null;
    for (const pl of this.places) {
      if (pl.place.mode !== 'pick') continue;
      const d = eye.distanceTo(pl.prompt.pos);
      if (d > pl.place.radius + 1.2) continue;
      tmp.copy(pl.prompt.pos).sub(eye).normalize();
      if (tmp.dot(look) < 0.55 && d > pl.place.radius) continue;
      if (!best || d < best.d) best = { p: pl.prompt, d };
    }
    return best;
  }

  /** 按 E 拾起纸签挂着的那一件 */
  pick(p: Promptable, camera: THREE.Camera) {
    const pl = this.places.find((x) => x.prompt === p);
    if (pl) this.acquire(pl, camera);
  }

  private acquire(pl: Placed, camera: THREE.Camera) {
    this.places = this.places.filter((x) => x !== pl);
    pl.holder.removeFromParent();
    this.owned.push({ id: pl.def.id, world: this.world, night: this.night() });
    if (!this.held) this.held = pl.def.id;
    this.save();
    tmp.copy(pl.prompt.pos).project(camera);
    const from =
      tmp.z < 1 && Math.abs(tmp.x) < 1.2 && Math.abs(tmp.y) < 1.2
        ? new THREE.Vector2((tmp.x * 0.5 + 0.5) * this.ui.w, (0.5 - tmp.y * 0.5) * this.ui.h)
        : new THREE.Vector2(this.ui.w / 2, this.ui.h);
    this.reveal = { def: pl.def, t: 0, from, card: card(pl.def) };
  }

  /** 演出的前半段、环绕展示时：人不走（视角照转） */
  get locked() {
    return (!!this.reveal && this.reveal.t < R_HOLD) || this.ringActive;
  }

  /** 演出的前半段：别的界面都让开 */
  get busy() {
    return !!this.reveal && this.reveal.t < R_HOLD;
  }

  get ringActive() {
    return this.ringWant || this.ringE > 0;
  }

  /** 环绕时世界犯困的程度 */
  get drowse() {
    return ease(this.ringE);
  }

  /** 按住 Q：举起来捏；松开放下 */
  use(down: boolean) {
    this.want = down && !this.sealed && !!this.held && !this.reveal && !this.ringActive;
  }

  /** 按住 F：环绕展示；松开时拿起正看着的那一件 */
  showRing(down: boolean, camera: THREE.Camera) {
    if (down) {
      if (this.sealed) {
        this.sealedT = 1.6;
        return;
      }
      if (this.reveal || this.ringWant) return;
      if (!this.owned.length) {
        this.emptyT = 1.4;
        return;
      }
      this.want = false;
      this.ringWant = true;
      for (const r of this.ring) r.shown.object.removeFromParent();
      camera.getWorldDirection(fwd);
      this.ringYaw = Math.atan2(-fwd.x, -fwd.z);
      const n = this.owned.length;
      this.ring = this.owned.map((o, i) => {
        const shown = showOf(itemDef(o.id)!);
        shown.object.scale.setScalar(RING.scale);
        this.hand.add(shown.object);
        return { id: o.id, shown, angle: this.ringYaw + (i - (n - 1) / 2) * RING.step };
      });
    } else if (this.ringWant) {
      this.ringWant = false;
      if (this.focus) this.hold(this.focus.id);
    }
  }

  update(dt: number, ctx: ItemCtx, camera: THREE.Camera) {
    // 摆着的：纸片浮动、朝人；装置自己动；到达型与条件型在这里判断
    for (const pl of [...this.places]) {
      if (pl.shown) pl.shown.update?.(dt, ctx.t);
      else this.drift(pl, ctx.t, camera);
      if (this.reveal) continue;
      if (pl.place.mode === 'reach' && ctx.feet.distanceTo(pl.place.pos) < pl.place.radius + 0.9) this.acquire(pl, camera);
      else if (pl.place.mode === 'custom' && pl.def.check?.(ctx)) this.acquire(pl, camera);
    }

    if (this.reveal) {
      this.reveal.t += dt;
      if (this.reveal.t >= R_END) this.reveal = null;
    }
    this.emptyT = Math.max(0, this.emptyT - dt);
    this.sealedT = Math.max(0, this.sealedT - dt);

    right.set(1, 0, 0).applyQuaternion(camera.quaternion);
    up.set(0, 1, 0).applyQuaternion(camera.quaternion);
    fwd.set(0, 0, -1).applyQuaternion(camera.quaternion);
    this.updateHeld(dt, ctx, camera);
    this.updateRing(dt, ctx, camera);
  }

  private updateHeld(dt: number, ctx: ItemCtx, camera: THREE.Camera) {
    if (this.model && this.model.id !== this.held) {
      this.model.m.object.removeFromParent();
      this.model = null;
    }
    if (this.held && !this.model) {
      const def = itemDef(this.held)!;
      this.model = { id: def.id, m: def.held() };
      this.model.m.object.scale.setScalar(HAND.scale);
      this.hand.add(this.model.m.object);
    }
    this.raise = this.want ? Math.min(1, this.raise + dt / 0.3) : Math.max(0, this.raise - dt / 0.25);
    // 举到位了才开始捏
    const squeezing = this.want && this.raise > 0.8;
    this.press = squeezing ? Math.min(1, this.press + dt / 0.5) : Math.max(0, this.press - dt / 0.25);
    if (!this.model) return;
    const o = this.model.m.object;
    o.visible = this.raise > 0;
    if (!o.visible) return;
    // 手边：画面右下，从下面抬上来；略微转向画面中间
    const e = ease(this.raise);
    o.position
      .copy(camera.position)
      .addScaledVector(fwd, HAND.fwd)
      .addScaledVector(right, HAND.right)
      .addScaledVector(up, -HAND.down - (1 - e) * 0.3);
    o.quaternion.copy(camera.quaternion).multiply(tilt);
    if (this.model.m.update(dt, this.press, ctx.t)) {
      itemDef(this.model.id)?.bloom?.();
      this.onBloom?.(this.model.id);
    }
  }

  private updateRing(dt: number, ctx: ItemCtx, camera: THREE.Camera) {
    this.ringE = this.ringWant ? Math.min(1, this.ringE + dt / 0.35) : Math.max(0, this.ringE - dt / 0.25);
    this.focus = null;
    if (!this.ringE) {
      for (const r of this.ring) r.shown.object.removeFromParent();
      this.ring = [];
      return;
    }
    const e = ease(this.ringE);
    let best = 0.3;
    for (const r of this.ring) {
      const o = r.shown.object;
      o.position.set(-Math.sin(r.angle), 0, -Math.cos(r.angle)).multiplyScalar(RING.radius * e).add(camera.position);
      o.position.y += -RING.drop - 0.32 * RING.scale;
      o.rotation.set(0, r.angle, 0);
      r.shown.update?.(dt, ctx.t);
      if (this.ringWant) {
        tmp.copy(o.position).setY(o.position.y + 0.32 * RING.scale).sub(camera.position).normalize();
        const a = Math.acos(THREE.MathUtils.clamp(tmp.dot(fwd), -1, 1));
        if (a < best) {
          best = a;
          this.focus = r;
        }
      }
    }
    for (const r of this.ring) r.shown.object.scale.setScalar(RING.scale * (r === this.focus ? 1.15 : 1) * (0.3 + 0.7 * e));
  }

  /** 纸片：浮着，正面朝人、左右轻轻摆 */
  private drift(pl: Placed, t: number, camera: THREE.Camera) {
    pl.holder.position.y = pl.place.pos.y + Math.sin(t * 2 + pl.place.pos.y) * 0.06;
    const cp = camera.position;
    pl.holder.rotation.y = Math.atan2(cp.x - pl.place.pos.x, cp.z - pl.place.pos.z) + Math.sin(t * 1.1 + pl.place.pos.y) * 0.35;
  }

  /** 手边那一点（拿在手里的东西举起来时的中心）在屏幕上的位置：屏幕像素，原点在左下 */
  handScreen(camera: THREE.Camera, w: number, h: number) {
    tmp.copy(camera.position).addScaledVector(fwd, HAND.fwd).addScaledVector(right, HAND.right).addScaledVector(up, -HAND.down).project(camera);
    return { x: (tmp.x * 0.5 + 0.5) * w, y: (tmp.y * 0.5 + 0.5) * h };
  }

  /** 给解析度场加的源（屏幕像素，原点在左下）：得到时眼前一下子清楚；环绕时正看着的那件清醒 */
  sources(camera: THREE.Camera): FieldSource[] {
    const out: FieldSource[] = [];
    const r = this.reveal;
    if (r) {
      const k = r.t < R_IN ? ease(r.t / R_IN) : r.t < R_HOLD ? 1 : 1 - clamp01((r.t - R_HOLD) / 0.4);
      if (k > 0) {
        const c = this.center();
        out.push({ x: c.x * UI_SCALE, y: (this.ui.h - c.y) * UI_SCALE, r: 30 + 110 * k });
      }
    }
    const f = this.focusScreen(camera);
    if (f) out.push({ x: f.x * UI_SCALE, y: (this.ui.h - f.y) * UI_SCALE, r: 80 });
    return out;
  }

  /** 正看着的那件在 UI 画布上的位置（它的中心） */
  private focusScreen(camera: THREE.Camera) {
    if (!this.focus) return null;
    tmp.copy(this.focus.shown.object.position).setY(this.focus.shown.object.position.y + 0.32 * RING.scale).project(camera);
    if (tmp.z > 1) return null;
    return new THREE.Vector2((tmp.x * 0.5 + 0.5) * this.ui.w, (0.5 - tmp.y * 0.5) * this.ui.h);
  }

  private center() {
    return new THREE.Vector2(Math.round(this.ui.w / 2), Math.round(this.ui.h * 0.42));
  }

  /** UI 画布上：得到时的卡片、日记那里闪一下；环绕时的名字 */
  drawUi(camera: THREE.Camera) {
    const g = this.ui.g;
    const r = this.reveal;
    if (r) {
      const c = this.center();
      const corner = new THREE.Vector2(this.ui.w - 22, this.ui.h - 20);
      const W = r.card.width;
      const H = r.card.height;
      let x = c.x;
      let y = c.y;
      let sx = 1;
      let sy = 1;
      let back = false;
      if (r.t < R_IN) {
        // 从东西那里飞来，翻面：背面 → 侧边 → 正面
        const k = ease(r.t / R_IN);
        x = r.from.x + (c.x - r.from.x) * k;
        y = r.from.y + (c.y - r.from.y) * k;
        const cos = Math.cos(((1 - k) * 270 * Math.PI) / 180);
        sx = Math.abs(cos);
        back = cos < 0;
        sy = 0.4 + 0.6 * k;
      } else if (r.t >= R_HOLD && r.t < R_OUT) {
        // 缩小，飞进右下角
        const k = ease((r.t - R_HOLD) / (R_OUT - R_HOLD));
        x = c.x + (corner.x - c.x) * k;
        y = c.y + (corner.y - c.y) * k;
        sx = sy = 1 - 0.8 * k;
      }
      if (r.t < R_OUT) {
        const dw = Math.max(1, Math.round(W * sx));
        const dh = Math.max(1, Math.round(H * sy));
        g.drawImage(back ? cardBack(r.card) : r.card, Math.round(x - dw / 2), Math.round(y - dh / 2), dw, dh);
        if (r.t >= R_IN && r.t < R_HOLD) drawTag(g, [text('得到了', P(2)), text(r.def.name, C.ink)], Math.round(c.x), Math.round(c.y + H / 2 + 8));
      } else if (Math.floor((r.t - R_OUT) * 6) % 2 === 0) {
        // 日记那里闪三下
        drawBook(g, corner.x - 6, corner.y - 5);
      }
    }
    if (this.ringWant) {
      const f = this.focusScreen(camera);
      if (f && this.focus) {
        const def = itemDef(this.focus.id)!;
        const parts = [text(def.name, C.ink)];
        parts.push(text(this.focus.id === this.held ? '手里' : '松开 F 拿起', P(this.focus.id === this.held ? 9 : 3)));
        drawTag(g, parts, Math.round(f.x), Math.round(f.y + 34));
      }
    }
    if (this.emptyT > 0) drawTag(g, [text('身上还没有东西', P(2))], Math.round(this.ui.w / 2), Math.round(this.ui.h * 0.62));
    if (this.sealedT > 0) drawTag(g, [text('醒着，什么也没带出来', P(2))], Math.round(this.ui.w / 2), Math.round(this.ui.h * 0.62));
  }
}

// ── 卡片与小件 ──
/** 卡片：剪纸上贴着放大三倍的像素画 */
function card(def: ItemDef): HTMLCanvasElement {
  const ic = def.icon();
  const k = 3;
  const W = ic.width * k + 14;
  const H = ic.height * k + 14;
  const { c, g } = scratch(W + 1, H + 1);
  const m = paperMask(W, H, def.id);
  paperShadow(g, 1, 1, W, H, m);
  paper(g, 0, 0, W, H, m, { fibre: true });
  g.imageSmoothingEnabled = false;
  g.drawImage(ic, 7, 7, ic.width * k, ic.height * k);
  return c;
}

const backs = new WeakMap<HTMLCanvasElement, HTMLCanvasElement>();
function cardBack(front: HTMLCanvasElement) {
  let b = backs.get(front);
  if (!b) {
    const W = front.width - 1;
    const H = front.height - 1;
    const s = scratch(W + 1, H + 1);
    const m = paperMask(W, H, 'back');
    paperShadow(s.g, 1, 1, W, H, m);
    paper(s.g, 0, 0, W, H, m, { fill: C.back });
    b = s.c;
    backs.set(front, b);
  }
  return b;
}

/** 一张小纸签，几段字横排，(cx, top) 是上边的中点 */
function drawTag(g: CanvasRenderingContext2D, parts: HTMLCanvasElement[], cx: number, top: number) {
  const gap = 4;
  const tw = parts.reduce((s, p) => s + p.width, 0) + gap * (parts.length - 1);
  const W = tw + 10;
  const H = 18;
  const m = paperMask(W, H, tw);
  const x = cx - Math.floor(W / 2);
  paperShadow(g, x + 1, top + 1, W, H, m);
  paper(g, x, top, W, H, m, { fibre: true });
  let px = x + 5;
  for (const p of parts) {
    g.drawImage(p, px, top + 3);
    px += p.width + gap;
  }
}

/** 右下角的小日记本：12×10 */
function drawBook(g: CanvasRenderingContext2D, x: number, y: number) {
  g.fillStyle = C.ink;
  g.fillRect(x, y, 12, 10);
  g.fillStyle = P(8);
  g.fillRect(x + 1, y + 1, 10, 8);
  g.fillStyle = C.paper;
  g.fillRect(x + 4, y + 3, 5, 3);
  g.fillStyle = P(14);
  g.fillRect(x + 9, y + 1, 1, 8);
}
