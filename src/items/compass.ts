/* 罗盘（地图）：不是一块表，是一件装置——中间浮着一根两头尖的表针，外面套着三道彼此倾斜、各自转动的环，
   左右各伸出一枚可以捏的小菱形。
   捏紧：环往里收、越转越快，表针转成一片，两枚菱形往里靠；捏到底：整个闪亮，世界从它这里暗下去，显现地图
   （见 src/mapview.ts）；地图开着时再捏到底一次，暗色缩回来。 */
import * as THREE from 'three';
import { PALETTE } from '../palette';
import { charm } from '../materials';
import { C, scratch } from '../ui';
import type { HeldModel, ItemDef, Shown } from './item';

const P = (i: number) => PALETTE[i];
type Ramp = [number, number, number];
const GOLD: Ramp = [9, 14, 14];
const BLUE: Ramp = [2, 12, 13];
const LILAC: Ramp = [2, 4, 5];
const ROSE: Ramp = [1, 8, 9];
const INK: Ramp = [0, 1, 2];

function icon() {
  const { c, g } = scratch(16, 16);
  const put = (x: number, y: number, col: string) => {
    g.fillStyle = col;
    g.fillRect(Math.round(x), Math.round(y), 1, 1);
  };
  // 三道环：一个圆、一个扁的横椭圆、一个瘦的竖椭圆
  for (let k = 0; k < 96; k++) {
    const a = (k / 96) * Math.PI * 2;
    put(7.5 + Math.cos(a) * 3.2, 7.5 + Math.sin(a) * 7, P(4));
    put(7.5 + Math.cos(a) * 7, 7.5 + Math.sin(a) * 2.6, P(12));
    put(7.5 + Math.cos(a) * 5.5, 7.5 + Math.sin(a) * 5.5, P(14));
  }
  // 表针：斜着，一头玫瑰一头墨
  for (let i = -5; i <= 5; i++) put(7.5 + i, 7.5 - i * 0.45, i > 0 ? P(8) : C.ink);
  for (const [x, y] of [[7, 7], [8, 8], [7, 8], [8, 7]]) put(x, y, P(14));
  // 左右两枚菱形
  for (const x of [0, 15]) for (const dy of [-1, 0, 1]) put(x, 7.5 + dy, dy === 0 ? P(8) : P(9));
  return c;
}

interface Device {
  root: THREE.Group;
  update(dt: number, press: number, glow: boolean): void;
}

/** 装置本体（米；原点在中心） */
function device(): Device {
  const root = new THREE.Group();
  const mats: THREE.ShaderMaterial[] = [];
  const mesh = (geo: THREE.BufferGeometry, ramp: Ramp) => {
    const m = charm(ramp);
    mats.push(m);
    return new THREE.Mesh(geo, m);
  };

  // 表针与金珠
  const core = new THREE.Group();
  const north = mesh(new THREE.ConeGeometry(0.024, 0.12, 8).rotateZ(-Math.PI / 2), ROSE);
  north.position.x = 0.06;
  const south = mesh(new THREE.ConeGeometry(0.024, 0.12, 8).rotateZ(Math.PI / 2), INK);
  south.position.x = -0.06;
  core.add(north, south, mesh(new THREE.SphereGeometry(0.028, 10, 8), GOLD));
  const tilt = new THREE.Group();
  tilt.rotation.z = 0.25;
  tilt.add(core);
  root.add(tilt);

  // 三道环：各自的初始倾角与转轴
  const specs = [
    { r: 0.1, tube: 0.014, ramp: GOLD, base: [0.4, 0, 0], spin: [0.7, 0, 0] },
    { r: 0.135, tube: 0.013, ramp: BLUE, base: [0, 0.5, 0.9], spin: [0, -0.5, 0] },
    { r: 0.17, tube: 0.012, ramp: LILAC, base: [1.3, 0.2, 0], spin: [0.15, 0, 0.3] },
  ];
  const rings = new THREE.Group();
  const ringMeshes = specs.map((s) => {
    const m = mesh(new THREE.TorusGeometry(s.r, s.tube, 6, 40), s.ramp);
    m.rotation.set(s.base[0], s.base[1], s.base[2]);
    rings.add(m);
    return m;
  });
  root.add(rings);

  // 左右两枚可以捏的菱形，各连一根细杆
  const grips = [-1, 1].map((s) => {
    const gr = new THREE.Group();
    const gem = mesh(new THREE.OctahedronGeometry(0.034), ROSE);
    gem.scale.set(0.7, 1.25, 0.7);
    const stem = mesh(new THREE.CylinderGeometry(0.007, 0.007, 0.04, 5).rotateZ(Math.PI / 2), INK);
    stem.position.x = -s * 0.03;
    gr.add(gem, stem);
    root.add(gr);
    return { gr, s };
  });

  return {
    root,
    update(dt, press, glow) {
      const k = 1 + 7 * press;
      ringMeshes.forEach((m, i) => {
        const sp = specs[i].spin;
        m.rotation.x += dt * sp[0] * k;
        m.rotation.y += dt * sp[1] * k;
        m.rotation.z += dt * sp[2] * k;
      });
      rings.scale.setScalar(1 - 0.22 * press);
      core.rotation.y += dt * (0.5 + 18 * press * press);
      for (const { gr, s } of grips) gr.position.x = s * (0.215 - 0.045 * press);
      for (const m of mats) m.uniforms.uGlow.value = glow ? 1 : 0;
    },
  };
}

/** 在世界里、环绕展示时：浮在原点上方一点，慢慢转着 */
function world(): Shown {
  const object = new THREE.Group();
  const d = device();
  // 世界里放大一号：4px 一格时环也有一两格粗
  d.root.scale.setScalar(1.3);
  d.root.position.y = 0.32;
  object.add(d.root);
  return {
    object,
    update(dt, t) {
      d.root.position.y = 0.32 + Math.sin(t * 1.6) * 0.02;
      d.update(dt, 0, false);
    },
  };
}

function held(): HeldModel {
  const object = new THREE.Group();
  const d = device();
  object.add(d.root);
  let fired = false;
  let glowT = 0;
  return {
    object,
    update(dt, press) {
      // 捏到底：整个闪亮一下；地图的开合由物品系统接着做（暗下来的一圈从这里扩出去）
      let hit = false;
      if (press >= 1 && !fired) {
        fired = true;
        hit = true;
        glowT = 0.5;
      }
      if (press < 0.5) fired = false;
      glowT = Math.max(0, glowT - dt);
      d.update(dt, press, glowT > 0 && Math.floor(glowT * 14) % 2 === 0);
      return hit;
    },
  };
}

export const compass: ItemDef = {
  id: 'compass',
  name: '罗盘',
  desc: '一根浮着的针，外面套着三道环，自己转着。左右各有一枚小菱形，可以捏紧。',
  kind: 'need',
  icon,
  world,
  held,
};
