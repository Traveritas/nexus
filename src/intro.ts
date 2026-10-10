/* 开场：一进来停在机位上（场景里的 nx_type=intro），漂着的木条从这里看过去正好拼成 NEXUS。
   标题画面走梦里常驻的那套后处理（解析度场像素化、落色板）——这是一个关于 NEXUS 的梦；
   「点击醒来」（顺便锁定视角）以后，木条按次序一条条松手、掉进虚空；随后视角沿一道弧滑到床边（出生点），一路上画面一块块解析成干净的现实，交还给人。
   只在第一次从根地址进来时放（localStorage 记一笔）；?intro=1 强制再放一次，?intro=0 不放。不放时木条直接拿掉。 */
import * as THREE from 'three';
import type { Intro } from './level';

const SEEN_KEY = 'nexus:woke';
const EYE = 1.6;
/** 第一条松手前停一下；之后每隔多久松一条 */
const DROP_AT = 0.3;
const DROP_GAP = 0.11;
/** 往下的加速度（米/秒²）；松手时先往上轻轻一弹 */
const FALL_G = 7;
const HOP = 0.6;
/** 梦的后处理（像素化、落色板）在滑动的哪一段里退掉（滑动进度 0..1） */
const WAKE_FROM = 0.05;
const WAKE_TO = 0.8;
/** 松手前的浮动：每条沿自己的一个斜方向来回，幅度按离机位的距离给（看上去每条都浮得一样多，约 0.9°），周期几秒 */
const BOB = 0.015;
/** 掉了多久以后拿掉（早就没进雾里了） */
const FALL_LIFE = 4;
/** 视角什么时候开始滑、滑多久 */
const GLIDE_AT = 1.5;
const GLIDE = 3.8;

export function introSeen() {
  try {
    return localStorage.getItem(SEEN_KEY) === '1';
  } catch {
    return false;
  }
}

function markSeen() {
  try {
    localStorage.setItem(SEEN_KEY, '1');
  } catch {
    /* 存不了就算了：下回再放一次 */
  }
}

/** 不放开场：掉下去的东西直接拿掉 */
export function stripIntro(intro: Intro | null) {
  for (const p of intro?.pieces ?? []) p.removeFromParent();
}

const smoother = (k: number) => k * k * k * (k * (k * 6 - 15) + 10);

interface Falling {
  obj: THREE.Object3D;
  base: THREE.Vector3;
  /** 浮动的方向（单位向量，偏竖直） */
  dir: THREE.Vector3;
  amp: number;
  freq: number;
  phase: number;
  at: number;
  vel: THREE.Vector3;
  spin: THREE.Vector3;
}

export class IntroPlayer {
  /** title 停在机位等点击 · play 木条在掉、视角在滑 · done 交还给人 */
  phase: 'title' | 'play' | 'done' = 'title';
  private t = 0;
  /** 从标题起一直走的钟（浮动用） */
  private clock = 0;
  private readonly from: { pos: THREE.Vector3; yaw: number; pitch: number };
  private to: { pos: THREE.Vector3; yaw: number; pitch: number } | null = null;
  private readonly mid = new THREE.Vector3();
  private readonly falling: Falling[];
  private readonly hint: HTMLElement;

  constructor(intro: Intro, hint: HTMLElement) {
    this.from = { pos: intro.pos.clone().add(new THREE.Vector3(0, EYE, 0)), yaw: intro.yaw, pitch: intro.pitch };
    const r = (a: number, b: number) => a + Math.random() * (b - a);
    this.falling = intro.pieces.map((obj, i) => ({
      obj,
      base: obj.position.clone(),
      dir: new THREE.Vector3(r(-1, 1), r(0.6, 1.4) * (Math.random() < 0.5 ? -1 : 1), r(-1, 1)).normalize(),
      amp: obj.position.distanceTo(this.from.pos) * BOB,
      freq: r(0.7, 1.2),
      phase: r(0, Math.PI * 2),
      at: DROP_AT + i * DROP_GAP + r(-0.03, 0.03),
      vel: new THREE.Vector3(r(-0.3, 0.3), HOP * r(0.6, 1.2), r(-0.3, 0.3)),
      spin: new THREE.Vector3(r(-1.4, 1.4), r(-0.6, 0.6), r(-1.4, 1.4)),
    }));
    this.hint = hint;
    hint.textContent = '点击醒来';
    document.body.classList.add('intro');
    // 等第一帧画出来再浮出字
    requestAnimationFrame(() => hint.classList.add('on'));
  }

  /** 梦的程度：标题时 1（整屏走梦的管线），滑向床边时一块块、一级级解析成干净的现实，到 0 */
  dream = 1;

  get active() {
    return this.phase !== 'done';
  }

  /** 点击醒来。终点（床边的眼睛、朝向）由调用方给 */
  wake(to: { pos: THREE.Vector3; yaw: number; pitch: number }) {
    if (this.phase !== 'title') return;
    this.phase = 'play';
    this.t = 0;
    this.to = { pos: to.pos.clone(), yaw: to.yaw, pitch: to.pitch };
    // 弧的控制点：两头的中点往上抬一些
    this.mid.copy(this.from.pos).lerp(to.pos, 0.5);
    this.mid.y += 2.2;
    this.hint.classList.remove('on');
    markSeen();
  }

  /** 不放了（开场还没完就去了别的世界）：木条拿掉、字收起 */
  cancel() {
    this.dream = 0;
    for (const f of this.falling) f.obj.removeFromParent();
    this.hint.classList.remove('on');
    document.body.classList.remove('intro');
    this.phase = 'done';
  }

  /** 推一帧；把这一帧眼睛的位置与朝向写进 out。返回 true 表示刚刚放完 */
  update(dt: number, out: { pos: THREE.Vector3; yaw: number; pitch: number }): boolean {
    if (this.phase === 'done') return false;
    this.clock += dt;
    // 还没松手的轻轻浮着；松手时从浮到的地方掉下去
    for (const f of this.falling) {
      if (this.phase === 'play' && this.t + dt > f.at) continue;
      f.obj.position.copy(f.base).addScaledVector(f.dir, Math.sin(this.clock * f.freq + f.phase) * f.amp);
    }
    if (this.phase === 'title') {
      out.pos.copy(this.from.pos);
      out.yaw = this.from.yaw;
      out.pitch = this.from.pitch;
      return false;
    }
    this.t += dt;
    for (const f of this.falling) {
      const age = this.t - f.at;
      if (age <= 0 || !f.obj.parent) continue;
      if (age > FALL_LIFE) {
        f.obj.removeFromParent();
        continue;
      }
      f.vel.y -= FALL_G * dt;
      f.obj.position.addScaledVector(f.vel, dt);
      f.obj.rotation.x += f.spin.x * dt;
      f.obj.rotation.y += f.spin.y * dt;
      f.obj.rotation.z += f.spin.z * dt;
    }
    const to = this.to!;
    const k = smoother(THREE.MathUtils.clamp((this.t - GLIDE_AT) / GLIDE, 0, 1));
    // 二次贝塞尔：机位 → 抬高的中点 → 床边
    const a = (1 - k) * (1 - k);
    const b = 2 * (1 - k) * k;
    const c = k * k;
    out.pos.set(0, 0, 0).addScaledVector(this.from.pos, a).addScaledVector(this.mid, b).addScaledVector(to.pos, c);
    let dy = (to.yaw - this.from.yaw) % (Math.PI * 2);
    if (dy > Math.PI) dy -= Math.PI * 2;
    if (dy < -Math.PI) dy += Math.PI * 2;
    out.yaw = this.from.yaw + dy * k;
    out.pitch = THREE.MathUtils.lerp(this.from.pitch, to.pitch, k);
    const g = THREE.MathUtils.clamp((this.t - GLIDE_AT) / GLIDE, 0, 1);
    this.dream = 1 - THREE.MathUtils.smoothstep(g, WAKE_FROM, WAKE_TO);
    const last = this.falling.reduce((m, f) => Math.max(m, f.at), 0);
    if (k >= 1 && this.t > last + 0.5) {
      for (const f of this.falling) f.obj.removeFromParent();
      this.phase = 'done';
      this.dream = 0;
      document.body.classList.remove('intro');
      return true;
    }
    return false;
  }
}
