/* 太阳的影子：正交相机跟着玩家走，深度画进一张 2048² 的深度图。
   相机中心按影子图的纹素对齐，走动时影子边缘不游移；
   接收端（matte）再按世界纹素中心取样，影子的锯齿与像素格是同一套。 */
import * as THREE from 'three';
import { shared } from './materials';

const SIZE = 2048;
/** 影子覆盖半径（米） */
const HALF = 40;

export class SunShadow {
  readonly rt: THREE.WebGLRenderTarget;
  private cam = new THREE.OrthographicCamera(-HALF, HALF, HALF, -HALF, 0.5, 260);
  private bias = new THREE.Matrix4().set(0.5, 0, 0, 0.5, 0, 0.5, 0, 0.5, 0, 0, 0.5, 0.5, 0, 0, 0, 1);
  private tmp = new THREE.Vector3();
  private basis = new THREE.Matrix4();
  private swapped: [THREE.Mesh, THREE.Material | THREE.Material[]][] = [];

  constructor() {
    this.rt = new THREE.WebGLRenderTarget(SIZE, SIZE, { depthBuffer: true });
    this.rt.depthTexture = new THREE.DepthTexture(SIZE, SIZE);
    this.rt.depthTexture.type = THREE.UnsignedIntType;
    shared.tShadow.value = this.rt.depthTexture;
    shared.uShadowOn.value = 1;
  }

  render(renderer: THREE.WebGLRenderer, scene: THREE.Scene, center: THREE.Vector3) {
    const sun = shared.uSun.value;
    // 光空间的基：沿太阳方向看
    const z = sun.clone().normalize();
    const x = new THREE.Vector3(0, 1, 0).cross(z).normalize();
    if (x.lengthSq() < 1e-6) x.set(1, 0, 0);
    const y = z.clone().cross(x);
    this.basis.makeBasis(x, y, z);
    // 中心投到光空间，按纹素对齐再放回世界
    const texel = (2 * HALF) / SIZE;
    const lx = Math.round(center.dot(x) / texel) * texel;
    const ly = Math.round(center.dot(y) / texel) * texel;
    const lz = center.dot(z);
    this.tmp.set(0, 0, 0).addScaledVector(x, lx).addScaledVector(y, ly).addScaledVector(z, lz + 120);
    this.cam.position.copy(this.tmp);
    this.cam.quaternion.setFromRotationMatrix(this.basis);
    this.cam.updateMatrixWorld();
    shared.uShadowMat.value.multiplyMatrices(this.bias, this.cam.projectionMatrix).multiply(this.cam.matrixWorldInverse);

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
