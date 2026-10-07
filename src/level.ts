/* 关卡：读 Blender 导出的 GLB，按物体上的自定义属性（nx_*，导出为 glTF extras → userData）装配。
   约定的全文见 docs/blender.md；这里只认那份文档里写到的属性。
   · 网格默认是像素哑光、参与碰撞。
   · 空物体（Empty）靠 nx_type 区分：spawn 出生点 · entrance 入口 · sprite 纸片 · sky 天上的纸片 · atmosphere 天空主题（nx_sky）。
   · Blender 的日光（Sun）决定太阳方向。
   · 带 nx_spin / nx_bob / nx_face 的物体会动，不进静态碰撞。 */
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { MeshBVH } from 'three-mesh-bvh';
import { asset, matte, paper, shared, shadowVariant, newId, TEXEL } from './materials';
import { makeSky, type SkyBox } from './skybox';
import { makeCrystal } from './crystal';
import { loadSprite, spriteSize } from './sprites';

export interface Entrance {
  url: string;
  title: string;
  crystal: ReturnType<typeof makeCrystal>;
  /** 晶体的基准位置（浮动围绕它） */
  base: THREE.Vector3;
}

interface Behavior {
  obj: THREE.Object3D;
  basePos: THREE.Vector3;
  baseRot: THREE.Euler;
  spin: number;
  bob: number;
  face: boolean;
  phase: number;
}

export interface Level {
  scene: THREE.Scene;
  crystalScene: THREE.Scene;
  collider: MeshBVH | null;
  entrances: Entrance[];
  spawn: { pos: THREE.Vector3; yaw: number };
  sky: SkyBox;
  update(dt: number, t: number, camera: THREE.Camera, frozen: boolean): void;
}

const num = (v: unknown, d: number) => (v === undefined || v === null || v === '' ? d : Number(v));
const bool = (v: unknown, d: boolean) => (v === undefined || v === null || v === '' ? d : !!Number(v) || v === true || v === 'true');

/** "5,4" → [5, 4] */
function palPair(v: unknown, d: [number, number]): [number, number] {
  if (typeof v !== 'string' && typeof v !== 'number') return d;
  const parts = String(v).split(/[,\s]+/).filter(Boolean).map(Number);
  if (parts.length === 1) return [parts[0], parts[0]];
  return [parts[0] ?? d[0], parts[1] ?? d[1]];
}

export async function loadLevel(url: string): Promise<Level> {
  const gltf = await new GLTFLoader().loadAsync(url);
  const root = gltf.scene;
  root.updateMatrixWorld(true);

  const scene = new THREE.Scene();
  const crystalScene = new THREE.Scene();
  const entrances: Entrance[] = [];
  const behaviors: Behavior[] = [];
  const skySprites: { obj: THREE.Object3D; dir: THREE.Vector3; dist: number }[] = [];
  const colliderGeos: THREE.BufferGeometry[] = [];
  const spawn = { pos: new THREE.Vector3(0, 0, 0), yaw: 0 };
  const pending: Promise<void>[] = [];

  // 天
  const sky = makeSky();
  scene.add(sky.mesh);
  let skyName = 'blank';

  const nodes: THREE.Object3D[] = [];
  root.traverse((o) => nodes.push(o));

  const wpos = new THREE.Vector3();
  const wquat = new THREE.Quaternion();
  const wscale = new THREE.Vector3();

  for (const o of nodes) {
    const u = o.userData as Record<string, unknown>;
    o.matrixWorld.decompose(wpos, wquat, wscale);

    // 太阳：Blender 的 Sun 灯
    if ((o as THREE.DirectionalLight).isDirectionalLight) {
      const L = o as THREE.DirectionalLight;
      L.target.updateMatrixWorld();
      const tp = new THREE.Vector3().setFromMatrixPosition(L.target.matrixWorld);
      shared.uSun.value.copy(wpos).sub(tp).normalize();
      continue;
    }

    const type = u.nx_type as string | undefined;
    // 空物体朝向：Blender 里的 +Y（导出后是 three 的 -Z）
    const fwd = new THREE.Vector3(0, 0, -1).applyQuaternion(wquat);

    if (type === 'spawn') {
      spawn.pos.copy(wpos);
      spawn.yaw = Math.atan2(-fwd.x, -fwd.z);
      continue;
    }

    if (type === 'atmosphere') {
      skyName = String(u.nx_sky ?? 'blank');
      continue;
    }

    if (type === 'entrance') {
      const crystal = makeCrystal(num(u.nx_size, 0.32));
      crystal.mesh.position.copy(wpos);
      crystalScene.add(crystal.mesh);
      entrances.push({
        url: String(u.nx_url ?? ''),
        title: String(u.nx_title ?? ''),
        crystal,
        base: wpos.clone(),
      });
      continue;
    }

    if (type === 'sprite' || type === 'sky') {
      const name = String(u.nx_sprite ?? '');
      const holder = new THREE.Group();
      holder.position.copy(wpos);
      holder.quaternion.copy(wquat);
      scene.add(holder);
      const isSky = type === 'sky';
      pending.push(
        loadSprite(name).then((tex) => {
          const { w, h } = spriteSize(tex);
          // 纸片：尺寸 ＝ 像素 ÷ 每米像素，底边中点落在空物体上；天上的：按 nx_size 米宽、居中
          const size = num(u.nx_size, 0);
          const sw = isSky ? size || 20 : w;
          const sh = isSky ? (sw * h) / w : h;
          const geo = new THREE.PlaneGeometry(sw, sh);
          if (!isSky) geo.translate(0, sh / 2, 0);
          const mat = paper(tex, { back: num(u.nx_back, 6), fog: !isSky, id: newId() });
          const mesh = new THREE.Mesh(geo, mat);
          if (!isSky && bool(u.nx_shadow, true)) mesh.userData.shadowMat = shadowVariant(mat);
          holder.add(mesh);
        }),
      );
      if (isSky) {
        skySprites.push({ obj: holder, dir: wpos.clone().normalize(), dist: 180 });
      } else {
        const b = behaviorOf(holder, u, true);
        if (b) behaviors.push(b);
      }
      continue;
    }

    const mesh = o as THREE.Mesh;
    if (!mesh.isMesh) continue;
    // 多材质的物体导出后拆成几块子网格，属性留在父节点上：子网格继承父节点的 nx_*，共用一个描边编号
    if (u.nx_mat === undefined && o.parent && !(o.parent as THREE.Mesh).isMesh && o.parent.userData.nx_mat !== undefined) {
      Object.assign(u, { ...o.parent.userData, ...u });
      o.parent.userData.nx_id ??= newId();
      u.nx_id = o.parent.userData.nx_id;
    }

    const kind = (u.nx_mat as string | undefined) ?? 'matte';
    const geo = mesh.geometry;
    const b = behaviorOf(mesh, u, false);
    const collide = bool(u.nx_collide, kind !== 'none') && !b;
    if (collide) {
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', geo.getAttribute('position').clone());
      if (geo.index) g.setIndex(geo.index.clone());
      g.applyMatrix4(mesh.matrixWorld);
      colliderGeos.push(g.index ? g.toNonIndexed() : g);
    }
    if (kind === 'collider' || kind === 'none') continue;

    const [a, bb] = palPair(u.nx_pal, [5, 4]);
    let mat: THREE.ShaderMaterial;
    if (kind === 'asset') {
      // 现成的模型：用它自己的底色贴图与颜色
      const src = mesh.material as THREE.MeshStandardMaterial;
      mat = asset({
        map: src?.map ?? null,
        color: src?.color?.clone() ?? new THREE.Color(1, 1, 1),
        cutout: (src?.alphaTest ?? 0) > 0 || !!src?.transparent,
        tint: num(u.nx_tint, 0),
        a,
        b: bb,
        smooth: num(u.nx_smooth, 0),
        id: u.nx_id as number | undefined,
      });
    } else {
      mat = matte({ a, b: bb, pattern: num(u.nx_pattern, 0), id: u.nx_id as number | undefined });
    }
    const m = new THREE.Mesh(geo, mat);
    m.position.copy(wpos);
    m.quaternion.copy(wquat);
    m.scale.copy(wscale);
    if (bool(u.nx_shadow, true)) m.userData.shadowMat = shadowVariant(mat);
    scene.add(m);
    if (b) {
      b.obj = m;
      b.basePos.copy(m.position);
      b.baseRot.copy(m.rotation);
      behaviors.push(b);
    }
  }

  await Promise.all(pending);
  sky.set(skyName);

  let collider: MeshBVH | null = null;
  if (colliderGeos.length) {
    const merged = mergeGeometries(colliderGeos, false);
    if (merged) collider = new MeshBVH(merged);
  }

  function update(_dt: number, t: number, camera: THREE.Camera, frozen: boolean) {
    sky.update(frozen ? 0 : t, camera);
    for (const s of skySprites) {
      s.obj.position.copy(camera.position).addScaledVector(s.dir, s.dist);
      s.obj.lookAt(camera.position);
    }
    for (const b of behaviors) {
      const tt = frozen ? 0 : t;
      b.obj.position.copy(b.basePos);
      b.obj.rotation.copy(b.baseRot);
      if (b.bob) b.obj.position.y += Math.sin(tt * 1.5 + b.phase) * b.bob;
      if (b.spin) b.obj.rotation.y += tt * b.spin;
      if (b.face) b.obj.rotation.set(0, Math.atan2(camera.position.x - b.obj.position.x, camera.position.z - b.obj.position.z), 0);
    }
    entrances.forEach((e, i) => {
      const m = e.crystal.mesh;
      const tt = frozen ? 0 : t + i * 1.7;
      m.rotation.set(0.42 + Math.sin(tt * 0.13) * 0.2, tt * 0.21, 0.18);
      m.position.copy(e.base);
      m.position.y += Math.sin(tt * 0.7) * 0.06;
    });
    // 最近的几枚晶体照亮周围
    const glows = shared.uGlows.value;
    const near = entrances
      .map((e) => ({ e, d: e.crystal.mesh.position.distanceToSquared(camera.position) }))
      .sort((p, q) => p.d - q.d);
    for (let i = 0; i < glows.length; i++) {
      const e = near[i]?.e;
      if (e) glows[i].set(e.crystal.mesh.position.x, e.crystal.mesh.position.y, e.crystal.mesh.position.z, 1);
      else glows[i].set(0, 0, 0, 0);
    }
  }

  return { scene, crystalScene, collider, entrances, spawn, sky, update };
}

function behaviorOf(obj: THREE.Object3D, u: Record<string, unknown>, faceDefault: boolean): Behavior | null {
  const spin = num(u.nx_spin, 0) * (Math.PI / 180);
  const bob = num(u.nx_bob, 0);
  const face = bool(u.nx_face, faceDefault);
  if (!spin && !bob && !face) return null;
  return {
    obj,
    basePos: obj.position.clone(),
    baseRot: obj.rotation.clone(),
    spin,
    bob,
    face,
    phase: Math.random() * Math.PI * 2,
  };
}
