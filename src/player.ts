/* 第一人称行走：胶囊体对静态碰撞网格（three-mesh-bvh）
   · 胶囊半径 0.3m、高 1.7m，眼高 1.6m。
   · 跳：起跳速度 7.2m/s、重力 22m/s² → 约 1.15m；松开早一点就跳得低一点。
     带「土狼时间」（离开边缘 0.1s 内还能起跳）与预输入（落地前 0.12s 按下也算）。
   · 台阶：贴地走时遇到 ≤ 0.35m 的坎自动迈上去；更高的要跳。
   · G 切到穿墙飞行（搭场景时用）：Space 上升、C 下降。 */
import * as THREE from 'three';
import { MeshBVH } from 'three-mesh-bvh';

export const PLAYER = {
  radius: 0.3,
  height: 1.7,
  eye: 1.6,
  walk: 3.2,
  run: 6,
  jump: 7.2,
  gravity: 22,
  step: 0.35,
  coyote: 0.1,
  buffer: 0.12,
};

export class Player {
  /** 脚底位置 */
  readonly feet = new THREE.Vector3();
  readonly vel = new THREE.Vector3();
  yaw = 0;
  pitch = 0;
  grounded = false;
  fly = false;
  walked = 0;
  /** 视线高度的平滑：迈台阶时镜头不瞬间抬高 */
  private eyeY = 0;

  private keys = new Set<string>();
  /** 这一帧想走的水平方向（单位向量或零） */
  private wantDir = new THREE.Vector3();
  private sinceGround = 99;
  private sinceJumpPress = 99;
  private jumpHeld = false;
  private seg = new THREE.Line3();
  private box = new THREE.Box3();
  private triPt = new THREE.Vector3();
  private capPt = new THREE.Vector3();
  private ray = new THREE.Ray(new THREE.Vector3(), new THREE.Vector3(0, -1, 0));

  constructor(private bvh: MeshBVH | null) {
    addEventListener('keydown', (e) => {
      if (e.repeat) return;
      this.keys.add(e.code);
      if (e.code === 'Space') {
        this.sinceJumpPress = 0;
        this.jumpHeld = true;
      }
      if (e.code === 'KeyG') {
        this.fly = !this.fly;
        this.vel.set(0, 0, 0);
      }
    });
    addEventListener('keyup', (e) => {
      this.keys.delete(e.code);
      if (e.code === 'Space') this.jumpHeld = false;
    });
    // 失焦、离开页面（包括走进入口跳走）都清掉按键：松开事件可能落在别的页面上
    const clear = () => {
      this.keys.clear();
      this.jumpHeld = false;
    };
    addEventListener('blur', clear);
    addEventListener('pagehide', clear);
    addEventListener('pageshow', clear);
  }

  setCollider(bvh: MeshBVH | null) {
    this.bvh = bvh;
  }

  /** 滚轮行走：沿视线水平方向推一下 */
  nudge(amount: number) {
    this.vel.addScaledVector(this.forward(), amount);
  }

  look(dx: number, dy: number) {
    this.yaw -= dx * 0.0022;
    this.pitch = THREE.MathUtils.clamp(this.pitch - dy * 0.0022, -1.4, 1.4);
  }

  forward() {
    return new THREE.Vector3(-Math.sin(this.yaw), 0, -Math.cos(this.yaw));
  }

  eyePosition(target: THREE.Vector3) {
    const bob = this.grounded && !this.fly ? Math.sin(this.walked * 2.2) * 0.025 : 0;
    return target.copy(this.feet).setY(this.eyeY + PLAYER.eye + bob);
  }

  /** 输入被冻结（比如正在进入一个入口）时传 locked */
  update(dt: number, locked = false) {
    const k = this.keys;
    const f = this.forward();
    const r = new THREE.Vector3(Math.cos(this.yaw), 0, -Math.sin(this.yaw));
    const want = new THREE.Vector3();
    if (!locked) {
      if (k.has('KeyW') || k.has('ArrowUp')) want.add(f);
      if (k.has('KeyS') || k.has('ArrowDown')) want.sub(f);
      if (k.has('KeyD') || k.has('ArrowRight')) want.add(r);
      if (k.has('KeyA') || k.has('ArrowLeft')) want.sub(r);
    }
    const speed = k.has('ShiftLeft') || k.has('ShiftRight') ? PLAYER.run : PLAYER.walk;
    this.wantDir.copy(want).setY(0);
    if (this.wantDir.lengthSq() > 0) this.wantDir.normalize();
    if (want.lengthSq() > 0) want.normalize().multiplyScalar(speed);

    if (this.fly) {
      if (!locked && k.has('Space')) want.y += speed;
      if (!locked && k.has('KeyC')) want.y -= speed;
      this.vel.lerp(want, 1 - Math.exp(-dt * 8));
      this.feet.addScaledVector(this.vel, dt);
      this.eyeY = this.feet.y;
      this.grounded = false;
      return;
    }

    // 水平：起步与停下都有一点惯性；空中控制弱一半
    const accel = this.grounded ? (want.lengthSq() > 0 ? 6 : 4) : 2.5;
    const h = new THREE.Vector3(this.vel.x, 0, this.vel.z).lerp(want, 1 - Math.exp(-dt * accel));
    this.vel.x = h.x;
    this.vel.z = h.z;

    // 跳
    this.sinceGround += dt;
    this.sinceJumpPress += dt;
    if (!locked && this.sinceJumpPress < PLAYER.buffer && this.sinceGround < PLAYER.coyote) {
      this.vel.y = PLAYER.jump;
      this.sinceGround = 99;
      this.sinceJumpPress = 99;
      this.grounded = false;
    }
    // 松开早：上升段收短
    const g = this.vel.y > 0 && !this.jumpHeld ? PLAYER.gravity * 2.2 : PLAYER.gravity;
    this.vel.y = Math.max(this.vel.y - g * dt, -40);

    // 分小步走，快速移动也不会穿过薄墙
    const steps = 4;
    const sdt = dt / steps;
    let grounded = false;
    for (let i = 0; i < steps; i++) grounded = this.substep(sdt) || grounded;
    if (grounded) {
      this.sinceGround = 0;
      if (this.vel.y < 0) this.vel.y = 0;
    }
    this.grounded = grounded;
    // 地面上往上的高差慢慢跟，跳起、落下、飞行都直接跟
    if (grounded && this.feet.y > this.eyeY && this.feet.y - this.eyeY < PLAYER.step + 0.05) {
      this.eyeY += (this.feet.y - this.eyeY) * (1 - Math.exp(-dt * 22));
    } else this.eyeY = this.feet.y;
    this.walked += grounded ? Math.hypot(this.vel.x, this.vel.z) * dt : 0;
  }

  private substep(dt: number): boolean {
    const start = this.feet.clone();
    const target = start.clone().addScaledVector(this.vel, dt);
    let res = this.collide(target);
    let stepped = false;
    const wantH = Math.hypot(target.x - start.x, target.z - start.z);
    const gotH = Math.hypot(res.pos.x - start.x, res.pos.z - start.z);

    // 迈台阶：贴地、想往前走却被挡住时，在胶囊前沿再往前一点、从 step 高处往下量地面；
    // 高差在 step 以内，就先把人抬到那一级的高度，再照常往前走
    const blocked = (res.pos.x - target.x) * this.wantDir.x + (res.pos.z - target.z) * this.wantDir.z < -1e-5;
    if (this.bvh && this.grounded && this.wantDir.lengthSq() > 0 && (blocked || gotH < wantH * 0.6)) {
      this.ray.origin.copy(start).addScaledVector(this.wantDir, PLAYER.radius + 0.08);
      this.ray.origin.y = start.y + PLAYER.step + 0.05;
      const hit = this.bvh.raycastFirst(this.ray, THREE.DoubleSide, 0, PLAYER.step + 0.1);
      const rise = hit ? hit.point.y - start.y : 0;
      if (rise > 0.01 && rise <= PLAYER.step + 1e-3) {
        const lifted = this.collide(target.clone().setY(start.y + rise + 0.01));
        // 头顶要有空：抬起来没被压回去才算
        if (lifted.pos.y >= start.y + rise - 0.005) {
          res = lifted;
          res.grounded = true;
          stepped = true;
          // 前几个分步贴墙时速度已被削掉，这里补回想走的方向
          const sp = Math.max(Math.hypot(this.vel.x, this.vel.z), PLAYER.walk * 0.6);
          this.vel.x = this.wantDir.x * sp;
          this.vel.z = this.wantDir.z * sp;
        }
      }
    }

    // 撞到的方向上把速度削掉，贴墙滑动；正在迈台阶时不削，人才能越过台阶边
    const push = res.pos.clone().sub(target);
    if (!stepped && push.lengthSq() > 1e-10) {
      const n = push.normalize();
      const vn = this.vel.dot(n);
      if (vn < 0) this.vel.addScaledVector(n, -vn);
    }
    this.feet.copy(res.pos);
    return res.grounded;
  }

  /** 把脚底在 p 的胶囊推出所有三角形；grounded ＝ 有一次推是朝上的 */
  private collide(p: THREE.Vector3) {
    const R = PLAYER.radius;
    const pos = p.clone();
    let grounded = false;
    if (!this.bvh) {
      if (pos.y < 0) {
        pos.y = 0;
        grounded = true;
      }
      return { pos, grounded };
    }
    for (let iter = 0; iter < 3; iter++) {
      this.seg.start.set(pos.x, pos.y + R, pos.z);
      this.seg.end.set(pos.x, pos.y + PLAYER.height - R, pos.z);
      this.box.makeEmpty().expandByPoint(this.seg.start).expandByPoint(this.seg.end);
      this.box.min.addScalar(-R);
      this.box.max.addScalar(R);
      let moved = false;
      this.bvh.shapecast({
        intersectsBounds: (b) => b.intersectsBox(this.box),
        intersectsTriangle: (tri) => {
          const d = tri.closestPointToSegment(this.seg, this.triPt, this.capPt);
          if (d < R) {
            const dir = this.capPt.sub(this.triPt);
            if (dir.lengthSq() < 1e-12) dir.copy(tri.getNormal(new THREE.Vector3()));
            dir.normalize();
            const depth = R - d;
            this.seg.start.addScaledVector(dir, depth);
            this.seg.end.addScaledVector(dir, depth);
            if (dir.y > 0.55) grounded = true;
            moved = true;
          }
        },
      });
      pos.set(this.seg.start.x, this.seg.start.y - R, this.seg.start.z);
      if (!moved) break;
    }
    return { pos, grounded };
  }
}
