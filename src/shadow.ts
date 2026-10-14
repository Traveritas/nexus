/* 太阳的影子：正交相机跟着玩家走，深度画进一张 2048² 的深度图。
   相机中心按影子图的纹素对齐，走动时影子边缘不游移；
   接收端（matte）再按世界纹素中心取样，影子的锯齿与像素格是同一套。

   绝大多数投影的东西是不动的，所以不必每帧重画：只在太阳变了、玩家离上次的中心超过 RECENTER 米、
   投影物增减了、或有投影物在动（最近 SETTLE 帧里世界矩阵变过：浮着的物品、会转的摆件）时才重画。
   不重画时影子矩阵也不动，深度图与矩阵始终对得上（覆盖半径 40 米，挪几米只是远处边缘差一点）。
   有东西在动时就整张重画：试过「拷一份静止的深度图再只画动的」，2048² 的深度拷贝比整场景重画还贵。 */
import * as THREE from 'three';
import { shared } from './materials';

const SIZE = 2048;
/** 覆盖范围大时的图边长 */
const BIG = 4096;
/** 大范围时竖向要盖住多高的东西（米） */
const BIG_H = 45;
/** 影子覆盖半径（米） */
const HALF = 40;
/** 玩家离上次的中心超过这么远（米）才挪中心重画 */
const RECENTER = 4;
/** 一个投影物停了这么多帧才算静止 */
const SETTLE = 30;

interface Track {
  m: Float64Array;
  moved: number;
}

export class SunShadow {
  rt: THREE.WebGLRenderTarget;
  private cam = new THREE.OrthographicCamera(-HALF, HALF, HALF, -HALF, 0.5, 260);
  /** 盖多远（米，atmosphere 的 nx_shadow_reach；0 ＝ 默认的 HALF）与此刻的图边长 */
  private reach = 0;
  private size = SIZE;
  private bias = new THREE.Matrix4().set(0.5, 0, 0, 0.5, 0, 0.5, 0, 0.5, 0, 0, 0.5, 0.5, 0, 0, 0, 1);
  private tmp = new THREE.Vector3();
  private basis = new THREE.Matrix4();
  private swapped: [THREE.Mesh, THREE.Material | THREE.Material[]][] = [];
  private track = new WeakMap<THREE.Mesh, Track>();
  private frame = 0;
  /** 上次重画时的太阳、中心、场景、投影物指纹 */
  private sun = new THREE.Vector3();
  private center = new THREE.Vector3(Infinity, 0, 0);
  private scene: THREE.Scene | null = null;
  private sig = NaN;
  /** 计数（测试脚本看）：一共几帧、重画了几次、上一帧有几个动着的投影物 */
  readonly stats = { frames: 0, draws: 0, live: 0 };

  constructor() {
    this.rt = SunShadow.target(SIZE);
    shared.uShadowOn.value = 1;
    this.bind();
  }

  private static target(size: number) {
    const rt = new THREE.WebGLRenderTarget(size, size, { depthBuffer: true });
    rt.depthTexture = new THREE.DepthTexture(size, size);
    rt.depthTexture.type = THREE.UnsignedIntType;
    return rt;
  }

  /** 换一个覆盖范围：大的（太阳低、影子上百米长的世界）换一张 4096² 的图。
      横向（垂直于太阳）盖 reach；竖向只要盖住「沿太阳方向 reach 米的地面」与 BIG_H 米高的东西，
      太阳低时竖向窄得多，沿太阳方向的影子边才不粗 */
  private setReach(reach: number, sun: THREE.Vector3) {
    const r = reach || HALF;
    const size = r > 60 ? BIG : SIZE;
    if (size !== this.size) {
      this.rt.dispose();
      this.rt = SunShadow.target(size);
      this.size = size;
    }
    this.reach = reach;
    const hy = reach ? Math.min(r, r * Math.abs(sun.y) + BIG_H) : r;
    const back = Math.max(120, r * 2.5);
    Object.assign(this.cam, { left: -r, right: r, top: hy, bottom: -hy, near: 0.5, far: back * 2 + 20 });
    this.cam.updateProjectionMatrix();
    return back;
  }

  /** 影子矩阵（世界 → 影子图） */
  private mat = new THREE.Matrix4();

  /** 把这张影子图套到共享的 uniform 上（几张影子图轮流用：缝那边的世界有自己的一张，见 seam.ts） */
  bind() {
    shared.tShadow.value = this.rt.depthTexture;
    shared.uShadowMat.value.copy(this.mat);
    shared.uShadowSpan.value.set(this.cam.right - this.cam.left, this.cam.top - this.cam.bottom);
  }

  /** 画完（或不用重画）都会 bind */
  render(renderer: THREE.WebGLRenderer, scene: THREE.Scene, center: THREE.Vector3, reach = 0) {
    this.bind();
    this.frame++;
    this.stats.frames++;
    scene.updateMatrixWorld();

    // 投影物的指纹（个数与编号的和、平方和），顺便看谁动了
    let n = 0;
    let s1 = 0;
    let s2 = 0;
    let live = 0;
    scene.traverseVisible((o) => {
      const m = o as THREE.Mesh;
      if (!m.isMesh || !m.userData.shadowMat) return;
      n++;
      s1 += m.id;
      s2 += m.id * m.id;
      const e = m.matrixWorld.elements;
      const t = this.track.get(m);
      if (!t) {
        // 头一回见到：当它是静止的（指纹变了，反正要重画）
        this.track.set(m, { m: new Float64Array(e), moved: -Infinity });
        return;
      }
      let same = true;
      for (let i = 0; i < 16; i++) if (t.m[i] !== e[i]) same = false;
      if (!same) {
        t.m.set(e);
        t.moved = this.frame;
      }
      if (this.frame - t.moved < SETTLE) live++;
    });
    this.stats.live = live;
    const sig = n * 1e12 + s1 * 1e6 + s2;

    const sun = shared.uSun.value;
    const recenter = !this.sun.equals(sun) || this.scene !== scene || this.reach !== reach || this.center.distanceToSquared(center) > RECENTER * RECENTER;
    if (!recenter && !live && sig === this.sig) return;
    if (recenter) {
      this.place(sun, center, this.setReach(reach, sun));
      this.sun.copy(sun);
      this.center.copy(center);
      this.scene = scene;
    }
    this.sig = sig;
    this.stats.draws++;
    this.draw(renderer, scene);
    this.bind();
  }

  /** 把影子相机摆到 center 上方，沿太阳方向看；中心按纹素对齐 */
  private place(sun: THREE.Vector3, center: THREE.Vector3, back: number) {
    const z = sun.clone().normalize();
    const x = new THREE.Vector3(0, 1, 0).cross(z).normalize();
    if (x.lengthSq() < 1e-6) x.set(1, 0, 0);
    const y = z.clone().cross(x);
    this.basis.makeBasis(x, y, z);
    const tx = (this.cam.right - this.cam.left) / this.size;
    const ty = (this.cam.top - this.cam.bottom) / this.size;
    const lx = Math.round(center.dot(x) / tx) * tx;
    const ly = Math.round(center.dot(y) / ty) * ty;
    const lz = center.dot(z);
    this.tmp.set(0, 0, 0).addScaledVector(x, lx).addScaledVector(y, ly).addScaledVector(z, lz + back);
    this.cam.position.copy(this.tmp);
    this.cam.quaternion.setFromRotationMatrix(this.basis);
    this.cam.updateMatrixWorld();
    this.mat.multiplyMatrices(this.bias, this.cam.projectionMatrix).multiply(this.cam.matrixWorldInverse);
  }

  /** 投影物换成只写深度的影子材质，其余的先藏起来 */
  private draw(renderer: THREE.WebGLRenderer, scene: THREE.Scene) {
    this.swapped.length = 0;
    scene.traverseVisible((o) => {
      const m = o as THREE.Mesh;
      if (!m.isMesh) return;
      const sv = m.userData.shadowMat as THREE.Material | undefined;
      this.swapped.push([m, m.material]);
      if (sv) m.material = sv;
      else m.visible = false;
    });
    renderer.setRenderTarget(this.rt);
    renderer.clear(true, true, true);
    renderer.render(scene, this.cam);
    for (const [m, mat] of this.swapped) {
      m.material = mat;
      m.visible = true;
    }
  }
}
