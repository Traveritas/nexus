/* 缝：两个世界在一处门洞里接上（nx_type=seam）。不传送、不转场——透过门洞看见的就是那个世界，走过门槛就站在那边了。
   家的大门和门外的原野就是这样接的：从屋里推开门，外面是原野；从原野看，那扇门只是立在地上的一扇门，门洞里是亮着灯的玄关。
   · 每道缝是门洞底边中点上的一个空物体，朝向（Blender 的 +Y）是「从这边看过去」的方向，nx_size 是门洞的宽、高。
     两边各放一道，to 互相写着对方；两道缝贴在一起：这一边缝前面的东西，对上那一边缝后面的东西。
   · 只有一面：从缝的背后看过去什么也没有（原野里绕到门背后，门洞里还是原野）；从背后走过去也不会过去。
   · 画法（每帧，世界图里）：先照常画这个世界，缝那一处用模板记一笔（seamMesh，一只往缝外伸出去的开口小盒子，只画里面：
     眼睛贴着门槛、近裁面切进缝里时也记得上）；再把深度改写成「记过的地方最远、别处最近」，把那个世界套上它自己的天、光、雾，
     用对过去的镜头画一遍——只有记过的那一块画得进去。那个世界里，缝后面（对这一边来说是缝前面）的东西用切面切掉。
     像素化、落色板照常一起做：两边同一种格子。 */
import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { OUTS, shared } from './materials';
import type { Level, Seam } from './level';
import type { SunShadow } from './shadow';

/** 模板的记号（窗玻璃用 1） */
const REF = 2;
/** 记号的小盒子往缝外伸多深：比近裁面（0.1）再多一截 */
const DEPTH = 0.4;

/** 缝的模板，只画朝着这边看的那一面，不写颜色与深度：
    · 门洞那一片（就在缝上）：门背后这个世界自己的东西（原野上门后的地）挡不住它；
    · 往缝外伸出去的开口小盒子，四边往里让一点、底抬高一点（不和门套、门后的地贴在同一个面上）：
      眼睛贴着门槛、近裁面切掉了门洞那一片时，靠它接着记 */
export function seamMesh(w: number, h: number) {
  const face = new THREE.PlaneGeometry(w, h);
  face.rotateY(Math.PI);
  face.translate(0, h / 2, 0);
  const box = new THREE.BoxGeometry(w - 0.02, h - 0.03, DEPTH);
  box.translate(0, 0.02 + (h - 0.03) / 2, -DEPTH / 2);
  // 面依次是 +x −x +y −y +z −z；+z 那一面朝着这边，拿掉
  const idx = box.index!;
  const keep: number[] = [];
  for (const gr of box.groups) if (gr.materialIndex !== 4) for (let i = gr.start; i < gr.start + gr.count; i++) keep.push(idx.getX(i));
  box.setIndex(keep);
  box.clearGroups();
  const m = new THREE.Mesh(
    mergeGeometries([face, box])!,
    new THREE.ShaderMaterial({
      glslVersion: THREE.GLSL3,
      side: THREE.BackSide,
      colorWrite: false,
      depthWrite: false,
      stencilWrite: true,
      stencilRef: REF,
      stencilFunc: THREE.AlwaysStencilFunc,
      stencilZPass: THREE.ReplaceStencilOp,
      vertexShader: /* glsl */ `void main() { gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: /* glsl */ `
precision highp float;
${OUTS}
void main() { oColor = vec4(0.0); oData = vec4(0.0); }`,
    }),
  );
  // 世界里别的东西都画完了才记：被挡住的地方记不上
  m.renderOrder = 1e5;
  m.userData.seam = true;
  return m;
}

/** 这一边的位置 → 那一边：贴着这道缝转半圈，对上那道缝 */
export function seamMatrix(from: Seam, to: Seam, out = new THREE.Matrix4()) {
  const a = new THREE.Matrix4().makeTranslation(-from.pos.x, -from.pos.y, -from.pos.z);
  const r = new THREE.Matrix4().makeRotationY(to.yaw + Math.PI - from.yaw);
  return out.makeTranslation(to.pos.x, to.pos.y, to.pos.z).multiply(r).multiply(a);
}

/** 走过去时朝向要转多少（弧度） */
export const seamTurn = (from: Seam, to: Seam) => to.yaw + Math.PI - from.yaw;

/** 人在缝的哪一边：负 ＝ 这边（看得见那边），正 ＝ 已经过了门槛；lateral、up 是在门洞里的哪里 */
export function seamSide(s: Seam, p: THREE.Vector3) {
  const dx = p.x - s.pos.x;
  const dz = p.z - s.pos.z;
  return { along: dx * s.fwd.x + dz * s.fwd.z, lateral: dx * -s.fwd.z + dz * s.fwd.x, up: p.y - s.pos.y };
}

const QUAD_VERT = /* glsl */ `void main() { gl_Position = vec4(position.xy, 0.0, 1.0); }`;
const depthMat = (func: THREE.StencilFunc, z: number) =>
  new THREE.ShaderMaterial({
    glslVersion: THREE.GLSL3,
    colorWrite: false,
    depthWrite: true,
    depthTest: true,
    depthFunc: THREE.AlwaysDepth,
    stencilWrite: true,
    stencilRef: REF,
    stencilFunc: func,
    stencilFail: THREE.KeepStencilOp,
    stencilZFail: THREE.KeepStencilOp,
    stencilZPass: THREE.KeepStencilOp,
    vertexShader: QUAD_VERT,
    fragmentShader: /* glsl */ `
precision highp float;
${OUTS}
void main() { oColor = vec4(0.0); oData = vec4(0.0); gl_FragDepth = ${z.toFixed(1)}; }`,
  });

/** 透过缝画另一个世界 */
export class Through {
  private cam = new THREE.PerspectiveCamera();
  private m = new THREE.Matrix4();
  private quadScene = new THREE.Scene();
  private quadCam = new THREE.Camera();
  private quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2));
  private near = depthMat(THREE.NotEqualStencilFunc, 0);
  private far = depthMat(THREE.EqualStencilFunc, 1);
  private frustum = new THREE.Frustum();
  private pm = new THREE.Matrix4();
  private box = new THREE.Box3();
  private tmp = new THREE.Vector3();

  constructor() {
    this.quad.frustumCulled = false;
    this.quadScene.add(this.quad);
  }

  /** 这一帧看不看得见那边：眼睛在缝的这一边、缝在视野里、不太远 */
  visible(here: Seam, camera: THREE.PerspectiveCamera) {
    const s = seamSide(here, camera.position);
    if (s.along > 0.05 || s.along < -140) return false;
    camera.updateMatrixWorld();
    this.pm.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse);
    this.frustum.setFromProjectionMatrix(this.pm);
    const r = Math.max(here.w, here.h);
    this.tmp.copy(here.pos).setY(here.pos.y + here.h / 2);
    this.box.setFromCenterAndSize(this.tmp, new THREE.Vector3(r, r, r));
    return this.frustum.intersectsBox(this.box);
  }

  /** 门洞（连同往外伸的小盒子）在屏幕上的外接框，按世界图的像素；有角跑到镜头后面就是整屏 */
  private rect(s: Seam, camera: THREE.PerspectiveCamera, w: number, h: number) {
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    const rx = -s.fwd.z, rz = s.fwd.x;
    for (const a of [-1, 1])
      for (const up of [0, s.h])
        for (const d of [0, DEPTH]) {
          const p = this.tmp.set(s.pos.x + rx * a * s.w * 0.5 + s.fwd.x * d, s.pos.y + up, s.pos.z + rz * a * s.w * 0.5 + s.fwd.z * d);
          p.applyMatrix4(camera.matrixWorldInverse);
          if (p.z > -camera.near) return new THREE.Vector4(0, 0, w, h);
          p.applyMatrix4(camera.projectionMatrix);
          x0 = Math.min(x0, p.x);
          x1 = Math.max(x1, p.x);
          y0 = Math.min(y0, p.y);
          y1 = Math.max(y1, p.y);
        }
    const px = (v: number, n: number) => THREE.MathUtils.clamp((v * 0.5 + 0.5) * n, 0, n);
    const ax = Math.floor(px(x0, w)) - 2, ay = Math.floor(px(y0, h)) - 2;
    return new THREE.Vector4(Math.max(0, ax), Math.max(0, ay), Math.min(w, Math.ceil(px(x1, w)) + 2) - Math.max(0, ax), Math.min(h, Math.ceil(px(y1, h)) + 2) - Math.max(0, ay));
  }

  /** 世界画完以后、还在世界图上时调用：here 是人在的世界，there 是缝那边的世界 */
  /** shade：两个世界各自的影子图（那边的由 main.ts 先画好）——透过门洞看见的和走过去以后看见的一样，影子不会一下子出现 */
  draw(r: THREE.WebGLRenderer, camera: THREE.PerspectiveCamera, here: Level, hs: Seam, there: Level, ts: Seam, shade: { here: SunShadow; there: SunShadow }, dt: number, t: number, frozen: boolean) {
    // 对过去的镜头：只取门洞在屏幕上的外接框那一块（偏轴的视锥）。那边的东西按这块视锥裁，
    // 门洞里看不见的房间不画；那个世界的材质带着切面的 discard，提前的深度剔除不起作用，也只在这一块里着色
    const cam = this.cam;
    cam.fov = camera.fov;
    cam.aspect = camera.aspect;
    cam.near = camera.near;
    // 那边写了 reach：只画到门洞里面这么深（眼睛到门洞的距离再加上它）
    cam.far = ts.reach > 0 ? Math.min(camera.far, camera.position.distanceTo(hs.pos) + ts.reach) : camera.far;
    const target = r.getRenderTarget();
    const W = target?.width ?? 1;
    const H = target?.height ?? 1;
    const R = target ? this.rect(hs, camera, W, H) : null;
    if (target && R && R.z > 0 && R.w > 0) {
      cam.setViewOffset(W, H, R.x, H - R.y - R.w, R.z, R.w);
      target.viewport.copy(R);
      target.scissor.copy(R);
      target.scissorTest = true;
      r.setRenderTarget(target);
    } else cam.clearViewOffset();
    seamMatrix(hs, ts, this.m).multiply(camera.matrixWorld);
    this.m.decompose(cam.position, cam.quaternion, cam.scale);
    cam.updateMatrixWorld();

    // 深度：记过的地方推到最远，别处拉到最近——那个世界只画得进门洞
    this.quad.material = this.near;
    r.render(this.quadScene, this.quadCam);
    this.quad.material = this.far;
    r.render(this.quadScene, this.quadCam);

    // 门（同名的 pose）跟着这边一起开关
    for (const g of there.poses.values()) {
      const mine = here.poses.get(g.name);
      if (mine) {
        g.target = mine.target;
        g.k = mine.k;
      }
    }
    there.apply();
    there.update(dt, t, cam, frozen);
    shade.there.bind();
    // 那边缝后面的东西（对这边来说在缝前面、挡在镜头和门洞之间）切掉
    shared.uCut.value.set(ts.fwd.x, 0, ts.fwd.z, ts.fwd.x * ts.pos.x + ts.fwd.z * ts.pos.z + 0.002);
    // 那边的天球（半径 370）缩进远裁面里：天只看方向，大小无所谓
    there.sky.mesh.scale.setScalar(Math.min(1, (cam.far * 0.95) / 370));
    r.render(there.scene, cam);
    there.sky.mesh.scale.setScalar(1);
    shared.uCut.value.set(0, 0, 0, 1e9);
    shade.here.bind();
    here.apply();
    if (target) {
      target.viewport.set(0, 0, W, H);
      target.scissorTest = false;
      r.setRenderTarget(target);
    }
  }
}
