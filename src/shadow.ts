/* 太阳的影子：正交相机跟着玩家走，深度画进一张 2048² 的深度图。
   相机中心按影子图的纹素对齐，走动时影子边缘不游移；
   接收端（matte）再按世界纹素中心取样，影子的锯齿与像素格是同一套。

   绝大多数投影的东西是不动的，所以不必每帧重画：
   - 静止的投影物画进一张「静图」，只在太阳变了、玩家离上次的中心超过 RECENTER 米、或静止的那一批变了时重画；
     不重画时影子矩阵也不动，静图与矩阵始终对得上（覆盖半径 40 米，挪几米只是远处边缘差一点）。
   - 动着的（这几帧里世界矩阵变过的：浮着的物品、会转的摆件）每帧先拷一份静图、再单独画上去。
     不用打标记：哪个投影物动了就自动归到动的那一批，停够 SETTLE 帧再并回静图。 */
import * as THREE from 'three';
import { shared } from './materials';

const SIZE = 2048;
/** 影子覆盖半径（米） */
const HALF = 40;
/** 玩家离静图中心超过这么远（米）才挪中心重画 */
const RECENTER = 4;
/** 一个投影物停了这么多帧才算回到静止的那一批 */
const SETTLE = 30;

interface Track {
  m: Float64Array;
  moved: number;
}

function makeTarget() {
  const rt = new THREE.WebGLRenderTarget(SIZE, SIZE, { depthBuffer: true });
  rt.depthTexture = new THREE.DepthTexture(SIZE, SIZE);
  rt.depthTexture.type = THREE.UnsignedIntType;
  return rt;
}

export class SunShadow {
  /** 静止的投影物 */
  private rtStatic = makeTarget();
  /** 静图 + 动着的投影物 */
  private rtLive = makeTarget();
  private cam = new THREE.OrthographicCamera(-HALF, HALF, HALF, -HALF, 0.5, 260);
  private bias = new THREE.Matrix4().set(0.5, 0, 0, 0.5, 0, 0.5, 0, 0.5, 0, 0, 0.5, 0.5, 0, 0, 0, 1);
  private tmp = new THREE.Vector3();
  private basis = new THREE.Matrix4();
  private swapped: [THREE.Mesh, THREE.Material | THREE.Material[]][] = [];
  private track = new WeakMap<THREE.Mesh, Track>();
  private casters: THREE.Mesh[] = [];
  private live = new Set<THREE.Mesh>();
  private frame = 0;
  /** 静图是在什么情况下画的：太阳、中心、场景、静止那一批的指纹 */
  private sun = new THREE.Vector3();
  private center = new THREE.Vector3(Infinity, 0, 0);
  private scene: THREE.Scene | null = null;
  private sig = NaN;
  private liveReady = false;
  /** 计数（测试脚本看）：静图重画了几次、上一帧有几个动着的投影物 */
  readonly stats = { frames: 0, statics: 0, live: 0 };

  constructor() {
    shared.tShadow.value = this.rtStatic.depthTexture;
    shared.uShadowOn.value = 1;
  }

  render(renderer: THREE.WebGLRenderer, scene: THREE.Scene, center: THREE.Vector3) {
    this.frame++;
    scene.updateMatrixWorld();

    // 找出这一帧的投影物，看谁动了
    const casters = this.casters;
    const live = this.live;
    casters.length = 0;
    live.clear();
    // 静止那一批的指纹：个数与编号的和、平方和
    let n = 0;
    let s1 = 0;
    let s2 = 0;
    scene.traverseVisible((o) => {
      const m = o as THREE.Mesh;
      if (!m.isMesh || !m.userData.shadowMat) return;
      casters.push(m);
      const e = m.matrixWorld.elements;
      let t = this.track.get(m);
      if (!t) {
        // 头一回见到：当它是静止的
        t = { m: new Float64Array(e), moved: -Infinity };
        this.track.set(m, t);
      } else {
        let same = true;
        for (let i = 0; i < 16; i++) if (t.m[i] !== e[i]) same = false;
        if (!same) {
          t.m.set(e);
          t.moved = this.frame;
        }
      }
      if (this.frame - t.moved < SETTLE) live.add(m);
      else {
        n++;
        s1 += m.id;
        s2 += m.id * m.id;
      }
    });
    const sig = n * 1e12 + s1 * 1e6 + s2;

    const sun = shared.uSun.value;
    const recenter = !this.sun.equals(sun) || this.scene !== scene || this.center.distanceToSquared(center) > RECENTER * RECENTER;
    if (recenter) {
      this.place(sun, center);
      this.sun.copy(sun);
      this.center.copy(center);
      this.scene = scene;
    }
    if (recenter || sig !== this.sig) {
      this.sig = sig;
      this.stats.statics++;
      this.draw(renderer, scene, this.rtStatic, (m) => !live.has(m));
    }

    this.stats.frames++;
    this.stats.live = live.size;
    if (live.size) {
      if (!this.liveReady) {
        renderer.initRenderTarget(this.rtLive);
        this.liveReady = true;
      }
      renderer.copyTextureToTexture(this.rtStatic.depthTexture!, this.rtLive.depthTexture!);
      this.draw(renderer, scene, this.rtLive, (m) => live.has(m), false);
      shared.tShadow.value = this.rtLive.depthTexture;
    } else {
      shared.tShadow.value = this.rtStatic.depthTexture;
    }
  }

  /** 把影子相机摆到 center 上方，沿太阳方向看；中心按纹素对齐 */
  private place(sun: THREE.Vector3, center: THREE.Vector3) {
    const z = sun.clone().normalize();
    const x = new THREE.Vector3(0, 1, 0).cross(z).normalize();
    if (x.lengthSq() < 1e-6) x.set(1, 0, 0);
    const y = z.clone().cross(x);
    this.basis.makeBasis(x, y, z);
    const texel = (2 * HALF) / SIZE;
    const lx = Math.round(center.dot(x) / texel) * texel;
    const ly = Math.round(center.dot(y) / texel) * texel;
    const lz = center.dot(z);
    this.tmp.set(0, 0, 0).addScaledVector(x, lx).addScaledVector(y, ly).addScaledVector(z, lz + 120);
    this.cam.position.copy(this.tmp);
    this.cam.quaternion.setFromRotationMatrix(this.basis);
    this.cam.updateMatrixWorld();
    shared.uShadowMat.value.multiplyMatrices(this.bias, this.cam.projectionMatrix).multiply(this.cam.matrixWorldInverse);
  }

  /** 只画 pick 选中的投影物（换成只写深度的影子材质），其余的先藏起来 */
  private draw(renderer: THREE.WebGLRenderer, scene: THREE.Scene, rt: THREE.WebGLRenderTarget, pick: (m: THREE.Mesh) => boolean, clear = true) {
    this.swapped.length = 0;
    scene.traverseVisible((o) => {
      const m = o as THREE.Mesh;
      if (!m.isMesh) return;
      const sv = m.userData.shadowMat as THREE.Material | undefined;
      this.swapped.push([m, m.material]);
      if (sv && pick(m)) m.material = sv;
      else m.visible = false;
    });
    const autoClear = renderer.autoClear;
    renderer.autoClear = false;
    renderer.setRenderTarget(rt);
    if (clear) renderer.clear(true, true, true);
    renderer.render(scene, this.cam);
    renderer.autoClear = autoClear;
    for (const [m, mat] of this.swapped) {
      m.material = mat;
      m.visible = true;
    }
  }
}
