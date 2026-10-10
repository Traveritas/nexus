/* 关卡：读 Blender 导出的 GLB，按物体上的自定义属性（nx_*，导出为 glTF extras → userData）装配。
   约定的全文见 docs/blender.md；这里只认那份文档里写到的属性。
   · 网格默认是像素哑光、参与碰撞。
   · 空物体（Empty）靠 nx_type 区分：spawn 出生点 · entrance 入口 · sprite 纸片 · sky 天上的纸片 · atmosphere 天空主题（nx_sky）。
   · Blender 的日光（Sun）决定太阳方向。
   · 带 nx_spin / nx_bob / nx_face 的物体会动，不进静态碰撞。
   · 干净低模（nx_mat=clean，颜色 nx_color）与窗玻璃（nx_mat=pane）：现实的世界用；nx_window=view 的东西只画在窗玻璃里。
     atmosphere 上的 nx_style=clean 让管线在这个世界里不做像素化、落色板与描边。 */
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { MeshBVH } from 'three-mesh-bvh';
import { asset, clean, matte, pane, paper, throughPane, veil, shared, shadowVariant, newId, TEXEL } from './materials';
import { makeSky, makeWindowSky, type SkyBox, type WindowSky } from './skybox';
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

/** 传送物：从一个世界去另一个世界。walk ＝ 走进去就走；key ＝ 走近后按 E */
export interface Portal {
  to: string;
  /** 到达点的名字（目标世界里的 arrive）；空 ＝ 目标世界的出生点 */
  at: string;
  mode: 'walk' | 'key';
  title: string;
  radius: number;
  pos: THREE.Vector3;
}

/** 窗景：窗外是哪一个站点的天。走近窗按 E 推开窗，视角凑到窗口（view）往外看，站点卡片浮出来；
    同一扇窗可以有几处，在窗口左右换着看，选一处进去 */
export interface Outlook {
  name: string;
  url: string;
  title: string;
  /** 卡片上的一句话（站点自己的话） */
  desc: string;
  /** 推开窗以后眼睛在哪、朝哪（three 坐标；yaw、pitch 弧度）。几处窗景共用第一处的 */
  view: { pos: THREE.Vector3; yaw: number; pitch: number };
  /** 窗里的天：主题名（可带种子） */
  sky: string;
  /** 站在哪儿能推开窗（纸签系在这里） */
  pos: THREE.Vector3;
  radius: number;
  /** 只在这一处窗景里看得见的点缀（nx_window=view 且 nx_outlook=名字） */
  props: THREE.Object3D[];
}

/** 一组会动的东西：在「原样」与「另一个样子」之间来回。
    near 走近就变、走开变回（窗帘）；key 走近按 E 来回切换；cue 由别的东西叫它（推开窗时的窗扇） */
export interface Pose {
  name: string;
  on: 'near' | 'key' | 'cue';
  pos: THREE.Vector3;
  radius: number;
  title: string;
  /** 变到另一个样子要几秒 */
  time: number;
  target: number;
  /** 0 原样 … 1 另一个样子 */
  k: number;
  members: { obj: THREE.Object3D; p0: THREE.Vector3; q0: THREE.Quaternion; s0: THREE.Vector3; dp: THREE.Vector3; dq: THREE.Quaternion; ds: THREE.Vector3 }[];
}

/** 物品摆在哪、怎么得到（物品本身的定义在 src/items/） */
export interface ItemPlace {
  item: string;
  /** pick 走近按 E 拾起 · reach 走进 radius 内就得到 · custom 由物品自己判断条件，这里只标位置 */
  mode: 'pick' | 'reach' | 'custom';
  radius: number;
  pos: THREE.Vector3;
}

export interface Level {
  scene: THREE.Scene;
  crystalScene: THREE.Scene;
  collider: MeshBVH | null;
  entrances: Entrance[];
  spawn: { pos: THREE.Vector3; yaw: number };
  portals: Portal[];
  items: ItemPlace[];
  /** 到达点：名字 → 脚底位置与朝向 */
  arrivals: Map<string, { pos: THREE.Vector3; yaw: number }>;
  sky: SkyBox;
  /** 窗里的天（有窗玻璃的世界才有） */
  windowSky: WindowSky | null;
  outlooks: Outlook[];
  /** 现在窗外是第几处 */
  outlook: number;
  showOutlook(i: number): void;
  poses: Map<string, Pose>;
  /** 画风：'pixel'（默认，解析度场像素化）或 'clean'（干净低模，不做后处理） */
  style: string;
  /** 把这个世界的太阳、天色、雾重新套到共享的 uniform 上（几个世界同时在内存里时，后加载的会改掉它们） */
  apply(): void;
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

/** Blender 坐标里的 "x,y,z" → three 坐标（x, z, −y）；没给就是 d */
function vecOf(v: unknown, d: [number, number, number]): THREE.Vector3 {
  const p = typeof v === 'string' ? v.split(/[,\s]+/).filter(Boolean).map(Number) : [];
  const [x, y, z] = p.length === 3 && p.every(Number.isFinite) ? p : d;
  return new THREE.Vector3(x, z, -y);
}

/** "暗,中,亮" 三个色板编号；不是三个就当没给 */
function rampOf(v: unknown): [number, number, number] | undefined {
  if (typeof v !== 'string') return undefined;
  const parts = v.split(/[,\s]+/).filter(Boolean).map(Number);
  return parts.length === 3 && parts.every(Number.isFinite) ? [parts[0], parts[1], parts[2]] : undefined;
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
  const portals: Portal[] = [];
  const items: ItemPlace[] = [];
  const arrivals = new Map<string, { pos: THREE.Vector3; yaw: number }>();
  const pending: Promise<void>[] = [];
  const outlooks: Outlook[] = [];
  const outlookProps: { name: string; obj: THREE.Object3D }[] = [];
  const poses = new Map<string, Pose>();
  let hasPane = false;

  /** 网格带 nx_pose：归进那一组。转、缩放都绕物体自己的原点（Blender 里物体的原点放在铰链 / 帘子收拢的那一头） */
  function addPose(m: THREE.Object3D, u: Record<string, unknown>) {
    const name = String(u.nx_pose);
    let g = poses.get(name);
    if (!g) {
      const on = String(u.nx_pose_on ?? 'near');
      g = {
        name,
        on: on === 'key' || on === 'cue' ? on : 'near',
        pos: u.nx_pose_at === undefined ? m.position.clone() : vecOf(u.nx_pose_at, [0, 0, 0]),
        radius: num(u.nx_pose_radius, 2),
        title: String(u.nx_pose_title ?? ''),
        time: Math.max(0.05, num(u.nx_pose_time, 0.8)),
        target: 0,
        k: 0,
        members: [],
      };
      poses.set(name, g);
    }
    // 转：Blender 本地轴的欧拉角（度，XYZ）→ three 本地轴（Blender 的 x、y、z 是 three 的 x、−z、y）
    const [rx, ry, rz] = String(u.nx_pose_rot ?? '0,0,0').split(/[,\s]+/).map((s) => Number(s) * (Math.PI / 180));
    const ax = (x: number, y: number, z: number, a: number) => new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(x, y, z), a || 0);
    const dq = ax(0, 1, 0, rz).multiply(ax(0, 0, -1, ry)).multiply(ax(1, 0, 0, rx));
    const [sx, sy, sz] = String(u.nx_pose_scale ?? '1,1,1').split(/[,\s]+/).map(Number);
    g.members.push({
      obj: m,
      p0: m.position.clone(),
      q0: m.quaternion.clone(),
      s0: m.scale.clone(),
      dp: vecOf(u.nx_pose_move, [0, 0, 0]),
      dq,
      ds: new THREE.Vector3(sx || 1, sz || 1, sy || 1),
    });
  }

  // 天
  const sky = makeSky();
  scene.add(sky.mesh);
  let skyName = 'blank';
  let style = 'pixel';

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

    if (type === 'arrive') {
      arrivals.set(String(u.nx_name ?? o.name), { pos: wpos.clone(), yaw: Math.atan2(-fwd.x, -fwd.z) });
      continue;
    }

    if (type === 'portal') {
      portals.push({
        to: String(u.nx_to ?? ''),
        at: String(u.nx_at ?? ''),
        mode: u.nx_mode === 'key' ? 'key' : 'walk',
        title: String(u.nx_title ?? ''),
        radius: num(u.nx_radius, 0.9),
        pos: wpos.clone(),
      });
      continue;
    }

    if (type === 'item') {
      const mode = String(u.nx_get ?? 'pick');
      items.push({
        item: String(u.nx_item ?? ''),
        mode: mode === 'reach' || mode === 'custom' ? mode : 'pick',
        radius: num(u.nx_radius, 1.2),
        pos: wpos.clone(),
      });
      continue;
    }

    if (type === 'outlook') {
      outlooks.push({
        name: o.name,
        url: String(u.nx_url ?? ''),
        title: String(u.nx_title ?? ''),
        desc: String(u.nx_desc ?? ''),
        view: {
          pos: u.nx_view === undefined ? wpos.clone().add(new THREE.Vector3(0, 0.15, 0)) : vecOf(u.nx_view, [0, 0, 0]),
          // 朝向同 spawn：从 Blender 的 +Y 起绕 Z 逆时针的角度，正好就是 three 里的 yaw
          yaw: num(u.nx_view_yaw, 0) * (Math.PI / 180),
          pitch: num(u.nx_view_pitch, 0) * (Math.PI / 180),
        },
        sky: String(u.nx_sky ?? 'blank'),
        pos: wpos.clone(),
        radius: num(u.nx_radius, 1.2),
        props: [],
      });
      continue;
    }

    if (type === 'atmosphere') {
      skyName = String(u.nx_sky ?? 'blank');
      style = String(u.nx_style ?? 'pixel');
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
    let whole: THREE.Object3D = mesh;
    if (u.nx_mat === undefined && o.parent && !(o.parent as THREE.Mesh).isMesh && o.parent.userData.nx_mat !== undefined) {
      whole = o.parent;
      Object.assign(u, { ...o.parent.userData, ...u });
      o.parent.userData.nx_id ??= newId();
      u.nx_id = o.parent.userData.nx_id;
    }

    const kind = (u.nx_mat as string | undefined) ?? 'matte';
    const geo = mesh.geometry;
    const b = behaviorOf(mesh, u, false);
    // 会动的（nx_spin / nx_bob / nx_pose）不进静态碰撞
    const collide = bool(u.nx_collide, kind !== 'none' && kind !== 'veil') && !b && u.nx_pose === undefined;
    if (collide) {
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', geo.getAttribute('position').clone());
      if (geo.index) g.setIndex(geo.index.clone());
      g.applyMatrix4(mesh.matrixWorld);
      colliderGeos.push(g.index ? g.toNonIndexed() : g);
    }
    if (kind === 'collider' || kind === 'none') continue;

    if (kind === 'pane' || kind === 'clean') {
      // 干净低模；窗玻璃先于窗里的景画（renderOrder），窗里的景只画在玻璃记过的模板里
      const view = u.nx_window === 'view';
      const cm =
        kind === 'pane'
          ? pane()
          : clean({
              color: new THREE.Color(String(u.nx_color ?? '#cccccc')),
              emit: num(u.nx_emit, 0),
              recv: bool(u.nx_recv, true),
              fog: bool(u.nx_fog, true),
              double: bool(u.nx_double, false),
              view,
              id: u.nx_id as number | undefined,
            });
      if (view) throughPane(cm);
      const m = new THREE.Mesh(geo, cm);
      m.position.copy(wpos);
      m.quaternion.copy(wquat);
      m.scale.copy(wscale);
      m.renderOrder = kind === 'pane' ? 1 : view ? 2 : 0;
      if (kind === 'clean' && !view && bool(u.nx_shadow, true)) m.userData.shadowMat = shadowVariant(cm);
      scene.add(m);
      if (kind === 'pane') hasPane = true;
      if (view && u.nx_outlook !== undefined) outlookProps.push({ name: String(u.nx_outlook), obj: m });
      if (u.nx_pose !== undefined && !b) addPose(m, u);
      if (b) {
        b.obj = m;
        b.basePos.copy(m.position);
        b.baseRot.copy(m.rotation);
        behaviors.push(b);
      }
      continue;
    }

    const [a, bb] = palPair(u.nx_pal, [5, 4]);
    let mat: THREE.ShaderMaterial;
    if (kind === 'veil') {
      // 传送物的膜：nx_size 是洞口的宽、高（米）；不投影
      const [w, h] = String(u.nx_size ?? '').split(/[,\s]+/).map(Number);
      const m = new THREE.Mesh(geo, veil({ a, b: bb, size: [w || 2, h || 2.5] }));
      m.position.copy(wpos);
      m.quaternion.copy(wquat);
      m.scale.copy(wscale);
      scene.add(m);
      continue;
    }
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
      // 高度范围按整个物体算（拆开的子网格也一样），渐变与顶面垂边才连得上
      const box = new THREE.Box3().setFromObject(whole);
      mat = matte({
        a,
        b: bb,
        pattern: num(u.nx_pattern, 0),
        top: u.nx_top === undefined ? undefined : num(u.nx_top, 0),
        yRange: [box.min.y, box.max.y],
        ramp: rampOf(u.nx_ramp),
        id: u.nx_id as number | undefined,
      });
    }
    const m = new THREE.Mesh(geo, mat);
    m.position.copy(wpos);
    m.quaternion.copy(wquat);
    m.scale.copy(wscale);
    if (bool(u.nx_shadow, true)) m.userData.shadowMat = shadowVariant(mat);
    scene.add(m);
    if (u.nx_pose !== undefined && !b) addPose(m, u);
    if (b) {
      b.obj = m;
      b.basePos.copy(m.position);
      b.baseRot.copy(m.rotation);
      behaviors.push(b);
    }
  }

  await Promise.all(pending);
  sky.set(skyName);

  // 窗：有窗玻璃就有窗里的天。没写窗景的，窗外就是这个世界自己的天
  outlooks.sort((p, q) => p.name.localeCompare(q.name));
  for (const { name, obj } of outlookProps) outlooks.find((ol) => ol.name === name)?.props.push(obj);
  const windowSky = hasPane ? makeWindowSky() : null;
  if (windowSky) scene.add(windowSky.mesh);
  let outlook = 0;
  const showOutlook = (i: number) => {
    outlook = outlooks.length ? ((i % outlooks.length) + outlooks.length) % outlooks.length : 0;
    windowSky?.set(outlooks[outlook]?.sky ?? sky.spec);
    outlooks.forEach((ol, j) => ol.props.forEach((p) => (p.visible = j === outlook)));
  };
  showOutlook(0);
  const smooth = (k: number) => k * k * (3 - 2 * k);

  let collider: MeshBVH | null = null;
  if (colliderGeos.length) {
    const merged = mergeGeometries(colliderGeos, false);
    if (merged) collider = new MeshBVH(merged);
  }

  function update(dt: number, t: number, camera: THREE.Camera, frozen: boolean) {
    sky.update(frozen ? 0 : t, camera);
    windowSky?.update(camera);
    for (const g of poses.values()) {
      if (g.on === 'near') g.target = Math.hypot(camera.position.x - g.pos.x, camera.position.z - g.pos.z) < g.radius ? 1 : 0;
      const k0 = g.k;
      g.k = g.target > g.k ? Math.min(g.target, g.k + dt / g.time) : Math.max(g.target, g.k - dt / g.time);
      if (g.k === k0 && g.members[0]?.obj.userData.posed === g.k) continue;
      const e = smooth(g.k);
      for (const mb of g.members) {
        mb.obj.position.copy(mb.p0).addScaledVector(mb.dp, e);
        mb.obj.quaternion.copy(mb.q0).multiply(tq.identity().slerp(mb.dq, e));
        mb.obj.scale.set(mb.s0.x * (1 + (mb.ds.x - 1) * e), mb.s0.y * (1 + (mb.ds.y - 1) * e), mb.s0.z * (1 + (mb.ds.z - 1) * e));
        mb.obj.userData.posed = g.k;
      }
    }
    shared.uTime.value = frozen ? 0 : t;
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

  const sunDir = shared.uSun.value.clone();
  const apply = () => {
    shared.uSun.value.copy(sunDir);
    sky.set(sky.spec);
    // 窗里的天的底色与种子也是共用的一份
    showOutlook(outlook);
  };
  return {
    scene, crystalScene, collider, entrances, spawn, portals, items, arrivals, sky, windowSky, outlooks,
    get outlook() {
      return outlook;
    },
    showOutlook, poses, style, apply, update,
  };
}

const tq = new THREE.Quaternion();

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
