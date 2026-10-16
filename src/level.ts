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
import { ExtendedTriangle, MeshBVH } from 'three-mesh-bvh';
import { asset, clean, matte, pane, paper, throughPane, veil, shared, shadowVariant, newId, TEXEL, MAX_LAMPS } from './materials';
import { makeSky, makeWindowSky, type SkyBox, type WindowSky } from './skybox';
import { makeCrystal } from './crystal';
import { seamMesh } from './seam';
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
  /** 来回荡（nx_sway，度）：绕自己本地的 x 轴摆，原点放在挂点上（秋千） */
  sway: number;
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
  /** 门开着时才算数（nx_need：一扇能开关的门的组名）；空 ＝ 总是算数 */
  need: string;
}

/** 缝：这个世界在一处门洞里和另一个世界接上（nx_type=seam，见 seam.ts）。透过它看见的是那个世界，走过去就到了那边，不转场 */
export interface Seam {
  /** 接到哪个世界（那边也要有一道 to 写着这个世界的缝） */
  to: string;
  /** 门洞底边的中点（three 坐标） */
  pos: THREE.Vector3;
  /** 从这边看过去的方向（水平单位向量）与它的 yaw（同 spawn） */
  fwd: THREE.Vector3;
  yaw: number;
  w: number;
  h: number;
  /** 从那边透过这道缝看进来时，画到缝里面多深为止（米，nx_reach；0 ＝ 不限）：屋里看不见的房间不画 */
  reach: number;
  /** 模板里那只往缝外伸的小盒子：只在眼睛贴着门槛时放出来（seam.ts 的 seamTube） */
  tube: THREE.Object3D | null;
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
  /** 拨到另一个样子 ＝ 世界入夜（nx_pose_night，房间里的开关） */
  night: boolean;
  members: { obj: THREE.Object3D; p0: THREE.Vector3; q0: THREE.Quaternion; s0: THREE.Vector3; dp: THREE.Vector3; dq: THREE.Quaternion; ds: THREE.Vector3 }[];
  /** 挡人（能开关的门）：原样与另一个样子两头各一份世界坐标的三角形；变到一半时不挡 */
  block: [Blocker, Blocker];
  /** 纸签系在组里某个物体的这一点上（本地坐标），跟着它动：pos 每次动完都重算（nx_pose_anchor，门把手） */
  anchor: { obj: THREE.Object3D; at: THREE.Vector3 } | null;
}

/** 会动的东西在某一头挡人：三角形（世界坐标）与它们的包围盒 */
export interface Blocker {
  box: THREE.Box3;
  tris: ExtendedTriangle[];
}

/** 物品摆在哪、怎么得到（物品本身的定义在 src/items/） */
export interface ItemPlace {
  item: string;
  /** pick 走近按 E 拾起 · reach 走进 radius 内就得到 · custom 由物品自己判断条件，这里只标位置 */
  mode: 'pick' | 'reach' | 'custom';
  radius: number;
  pos: THREE.Vector3;
}

/** 开场（docs/blender.md「开场」）：一进来先停在机位上，「点击醒来」以后 pieces 按次序逐个掉进虚空，视角滑到出生点 */
export interface Intro {
  /** 机位：脚底（眼睛高 1.6m）、朝向（同 spawn）、俯仰（弧度） */
  pos: THREE.Vector3;
  yaw: number;
  pitch: number;
  /** 掉下去的东西，按 nx_intro 排好 */
  pieces: THREE.Object3D[];
}

export interface Level {
  scene: THREE.Scene;
  crystalScene: THREE.Scene;
  collider: MeshBVH | null;
  entrances: Entrance[];
  spawn: { pos: THREE.Vector3; yaw: number };
  portals: Portal[];
  /** 缝：和别的世界无缝接上的门洞 */
  seams: Seam[];
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
  /** 开场（有 nx_type=intro 的世界才有） */
  intro: Intro | null;
  /** 画风：'pixel'（默认，解析度场像素化）或 'clean'（干净低模，不做后处理） */
  style: string;
  /** 世界的样子（atmosphere 上写的）：grid 远处的格子是几级（2 ＝ 4px，3 ＝ 8px）、mask 只用哪几枚色板色（位）、
      lamps 灯一直亮着（不等入夜） */
  look: Look;
  /** 循环的大地：方块边长（米，0 ＝ 不循环），方块以原点为中心。四周八份复制只是画出来看的，碰撞只有中间这一份 */
  wrap: number;
  /** 昼夜：0 白天 … 1 夜里（跟着 night 的 pose 慢慢变） */
  readonly night: number;
  /** 把这个世界的太阳、天色、雾、灯重新套到共享的 uniform 上（几个世界同时在内存里时，后加载的会改掉它们） */
  apply(): void;
  /** 这一刻挡人的会动的东西（停在某一头的门） */
  blockers(): Blocker[];
  update(dt: number, t: number, camera: THREE.Camera, frozen: boolean): void;
  /** 影子图外面算暗（1）还是亮（0） */
  shadowOut: number;
  /** 影子图盖多远（米，0 ＝ 默认） */
  shadowReach: number;
  /** 太阳转到哪一刻（秒；atmosphere 写了 nx_sun_turn 才有用）。可以拨 */
  sunTime: number;
  /** 掉进别处（atmosphere 的 nx_fall_to）：脚底掉到 y 以下就去 to 世界的到达点 at，不回出生点 */
  fall: { to: string; at: string; y: number } | null;
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
  const seams: Seam[] = [];
  const items: ItemPlace[] = [];
  const arrivals = new Map<string, { pos: THREE.Vector3; yaw: number }>();
  let intro: Intro | null = null;
  /** 开场里掉下去的网格（nx_intro 写在网格或它的父级上） */
  const introMeshes: { m: THREE.Mesh; order: number }[] = [];
  const noteIntro = (m: THREE.Mesh, o: THREE.Object3D) => {
    const v = o.userData.nx_intro ?? o.parent?.userData.nx_intro;
    if (v !== undefined) introMeshes.push({ m, order: num(v, 0) });
  };
  const pending: Promise<void>[] = [];
  const outlooks: Outlook[] = [];
  const outlookProps: { name: string; obj: THREE.Object3D }[] = [];
  const poses = new Map<string, Pose>();
  let hasPane = false;
  /** 夜里亮的灯光：位置、照多远、颜色（已乘强度） */
  const lamps: {
    pos: THREE.Vector3;
    radius: number;
    color: THREE.Color;
    /** 灯罩：罩口朝下的方向、下口 / 上口半角的余弦（2 ＝ 封着）、别的方向透出多少 */
    axis: THREE.Vector3;
    cosDown: number;
    cosUp: number;
    leak: number;
    /** 往上那一束的倍数、光圈边上软的那一圈（弧度） */
    upPower: number;
    edge: number;
    /** 下口那一束照到多远为止（米，沿罩口方向） */
    reach: number;
    /** 只照这只盒子里的东西（three 坐标）；没写就不限 */
    lo: THREE.Vector3;
    hi: THREE.Vector3;
  }[] = [];

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
        night: bool(u.nx_pose_night, false),
        members: [],
        block: [{ box: new THREE.Box3(), tris: [] }, { box: new THREE.Box3(), tris: [] }],
        anchor: null,
      };
      poses.set(name, g);
    }
    if (u.nx_pose_anchor !== undefined && !g.anchor) g.anchor = { obj: m, at: vecOf(u.nx_pose_anchor, [0, 0, 0]) };
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
    // 能开关的门：nx_collide 没关掉的，两头各记一份三角形，停在哪头就挡在哪头（转到一半不挡）
    const mesh = m as THREE.Mesh;
    if (mesh.isMesh && bool(u.nx_collide, true)) {
      const mb = g.members[g.members.length - 1];
      const ends: [THREE.Matrix4, THREE.Matrix4] = [
        new THREE.Matrix4().compose(mb.p0, mb.q0, mb.s0),
        new THREE.Matrix4().compose(mb.p0.clone().add(mb.dp), mb.q0.clone().multiply(mb.dq), mb.s0.clone().multiply(mb.ds)),
      ];
      const pos = mesh.geometry.getAttribute('position');
      const idx = mesh.geometry.index;
      const n = idx ? idx.count : pos.count;
      ends.forEach((mat, e) => {
        const v = (i: number) => new THREE.Vector3().fromBufferAttribute(pos, idx ? idx.getX(i) : i).applyMatrix4(mat);
        for (let i = 0; i + 2 < n; i += 3) {
          const t = new ExtendedTriangle(v(i), v(i + 1), v(i + 2));
          g!.block[e].tris.push(t);
          g!.block[e].box.expandByPoint(t.a).expandByPoint(t.b).expandByPoint(t.c);
        }
      });
    }
  }

  // 天
  const sky = makeSky();
  scene.add(sky.mesh);
  let skyName = 'blank';
  let style = 'pixel';
  const look: Look = { grid: 2, mask: 0xffff, lamps: false, lit: -1 };
  let wrap = 0;
  /** 影子：图外面算不算暗、图盖多远（米）；太阳绕竖轴转多快（度每分） */
  let shadowOut = 0;
  let penumbra = 0;
  let shadowReach = 0;
  let sunTurn = 0;
  /** 水波光斑：强度、水面高、网纹大小、线变细的深度（见 materials.ts 的 uCaustic） */
  const caustic = new THREE.Vector4(0, 0, 3, 12);
  let fall: Level['fall'] = null;

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

    if (type === 'intro') {
      intro = { pos: wpos.clone(), yaw: Math.atan2(-fwd.x, -fwd.z), pitch: num(u.nx_pitch, 0) * (Math.PI / 180), pieces: [] };
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
        need: String(u.nx_need ?? ''),
      });
      continue;
    }

    if (type === 'seam') {
      const [w, h] = String(u.nx_size ?? '').split(/[,\s]+/).map(Number);
      const yaw = Math.atan2(-fwd.x, -fwd.z);
      const m = seamMesh(w || 1, h || 2.1);
      m.position.copy(wpos);
      m.rotation.set(0, yaw, 0);
      scene.add(m);
      seams.push({
        to: String(u.nx_to ?? ''), pos: wpos.clone(), fwd: new THREE.Vector3(-Math.sin(yaw), 0, -Math.cos(yaw)), yaw,
        w: w || 1, h: h || 2.1, reach: num(u.nx_reach, 0), tube: m.userData.tube as THREE.Object3D,
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

    if (type === 'lamp') {
      // 灯罩的半角（度）→ 余弦；0 ＝ 那一头封着（余弦给 2，锥里什么也进不去）
      const cosOf = (deg: number) => (deg > 0 ? Math.cos(deg * (Math.PI / 180)) : 2);
      // nx_box：Blender 坐标的 "x0,y0,z0,x1,y1,z1" → three（x, z, −y）
      const bx = u.nx_box === undefined ? null : String(u.nx_box).split(',').map(Number);
      const lo = bx ? new THREE.Vector3(Math.min(bx[0], bx[3]), Math.min(bx[2], bx[5]), -Math.max(bx[1], bx[4])) : new THREE.Vector3(-1e5, -1e5, -1e5);
      const hi = bx ? new THREE.Vector3(Math.max(bx[0], bx[3]), Math.max(bx[2], bx[5]), -Math.min(bx[1], bx[4])) : new THREE.Vector3(1e5, 1e5, 1e5);
      lamps.push({
          pos: wpos.clone(),
          radius: num(u.nx_radius, 4),
          color: new THREE.Color(String(u.nx_color ?? '#ffd2a0')).multiplyScalar(num(u.nx_power, 1)),
          // 罩口朝下：空物体本地的 −Z（Blender）＝ three 的 −Y，跟着父级歪
          axis: new THREE.Vector3(0, -1, 0).applyQuaternion(wquat).normalize(),
          cosDown: cosOf(num(u.nx_down, 180)),
          cosUp: cosOf(num(u.nx_up, 0)),
          leak: num(u.nx_leak, 1),
          upPower: num(u.nx_up_power, 1),
          edge: num(u.nx_edge, 4) * (Math.PI / 180),
          reach: num(u.nx_reach, 1e4),
          lo,
          hi,
        });
      continue;
    }

    if (type === 'atmosphere') {
      skyName = String(u.nx_sky ?? 'blank');
      style = String(u.nx_style ?? 'pixel');
      look.grid = THREE.MathUtils.clamp(Math.round(num(u.nx_grid, 2)), 0, 4);
      if (u.nx_palette !== undefined) look.mask = String(u.nx_palette).split(',').reduce((m, c) => m | (1 << (Number(c) & 15)), 0) || 0xffff;
      look.lamps = bool(u.nx_lamps, false);
      wrap = Math.max(0, num(u.nx_wrap, 0));
      look.lit = u.nx_grid_lit === undefined ? -1 : THREE.MathUtils.clamp(Math.round(num(u.nx_grid_lit, 1)), 0, 4);
      shadowOut = bool(u.nx_shadow_out, false) ? 1 : 0;
      penumbra = Math.max(0, num(u.nx_penumbra, 0));
      shadowReach = Math.max(0, num(u.nx_shadow_reach, 0));
      sunTurn = num(u.nx_sun_turn, 0);
      if (u.nx_caustics !== undefined)
        caustic.set(num(u.nx_caustics, 0), num(u.nx_caustics_y, 0), num(u.nx_caustics_size, 3), num(u.nx_caustics_depth, 12));
      if (u.nx_fall_to) fall = { to: String(u.nx_fall_to), at: String(u.nx_fall_at ?? ''), y: num(u.nx_fall_y, -12) };
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
    const collide = bool(u.nx_collide, kind !== 'none' && kind !== 'veil' && kind !== 'shade') && !b && u.nx_pose === undefined;
    if (collide) {
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', geo.getAttribute('position').clone());
      if (geo.index) g.setIndex(geo.index.clone());
      g.applyMatrix4(mesh.matrixWorld);
      colliderGeos.push(g.index ? g.toNonIndexed() : g);
    }
    if (kind === 'collider' || kind === 'none') continue;

    if (kind === 'shade') {
      // 只投影：看不见，只往太阳的影子图里画
      const m = new THREE.Mesh(geo, HIDDEN);
      m.position.copy(wpos);
      m.quaternion.copy(wquat);
      m.scale.copy(wscale);
      m.userData.shadowMat = SHADE_ONLY;
      scene.add(m);
      // 会动的投影（转、浮、荡）：影子跟着动（影子图看见投影物在动就整张重画）
      if (b) {
        b.obj = m;
        b.basePos.copy(m.position);
        b.baseRot.copy(m.rotation);
        behaviors.push(b);
      }
      // 能开关的投影（看不见的柜门、窗扇）：门转开，地上的影子跟着转开
      if (u.nx_pose !== undefined && !b) addPose(m, u);
      continue;
    }

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
              lit: bool(u.nx_lit, false),
              id: u.nx_id as number | undefined,
            });
      if (view) throughPane(cm);
      const m = new THREE.Mesh(geo, cm);
      m.position.copy(wpos);
      m.quaternion.copy(wquat);
      m.scale.copy(wscale);
      // nx_window=over：照常画，但在窗里的天之后，伸到玻璃外面也不被盖掉（往外开的窗扇）
      m.renderOrder = kind === 'pane' ? 1 : view || u.nx_window === 'over' ? 2 : 0;
      if (kind === 'clean' && !view && bool(u.nx_shadow, true)) m.userData.shadowMat = shadowVariant(cm);
      scene.add(m);
      noteIntro(m, o);
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
        emit: num(u.nx_emit, 0),
        litOnly: num(u.nx_lit_only, 0),
        ghost: ghostOf(u.nx_ghost),
        id: u.nx_id as number | undefined,
      });
    }
    const m = new THREE.Mesh(geo, mat);
    m.position.copy(wpos);
    m.quaternion.copy(wquat);
    m.scale.copy(wscale);
    if (bool(u.nx_shadow, true)) m.userData.shadowMat = shadowVariant(mat);
    scene.add(m);
    noteIntro(m, o);
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
  if (wrap > 0) tile(scene, wrap, new Set([sky.mesh, ...behaviors.map((b) => b.obj), ...skySprites.map((s) => s.obj)]));

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

  // 同一编号的网格收进一个以它们中心为原点的组：掉下去时绕自己翻
  if (intro) {
    const byOrder = new Map<number, THREE.Mesh[]>();
    for (const { m, order } of introMeshes) byOrder.set(order, [...(byOrder.get(order) ?? []), m]);
    (intro as Intro).pieces = [...byOrder.keys()].sort((p, q) => p - q).map((k) => {
      const ms = byOrder.get(k)!;
      const box = new THREE.Box3();
      for (const m of ms) box.expandByObject(m);
      const g = new THREE.Group();
      box.getCenter(g.position);
      scene.add(g);
      for (const m of ms) {
        m.position.sub(g.position);
        g.add(m);
      }
      return g;
    });
  }

  let collider: MeshBVH | null = null;
  if (colliderGeos.length) {
    const merged = mergeGeometries(colliderGeos, false);
    if (merged) collider = new MeshBVH(merged);
  }

  // 昼夜：跟着开关（night 的 pose）慢慢变，天光、天色、灯一起
  const nightPose = [...poses.values()].find((g) => g.night) ?? null;
  let nightK = 0;
  let night = 0;
  // 灯可以比槽多：每帧取离人最近的 MAX_LAMPS 盏写进 uniform（远处房间的灯反正隔着墙）
  let active = lamps.slice(0, MAX_LAMPS);
  const applyLamps = () => {
    shared.uLamps.value.forEach((v, i) => {
      const l = active[i];
      if (l) v.set(l.pos.x, l.pos.y, l.pos.z, l.radius);
      else v.set(0, 0, 0, 0);
    });
    shared.uLampCols.value.forEach((c, i) => c.copy(active[i]?.color ?? BLACK));
    shared.uLampAxis.value.forEach((v, i) => {
      const l = active[i];
      if (l) v.set(l.axis.x, l.axis.y, l.axis.z, l.cosDown);
    });
    shared.uLampShade.value.forEach((v, i) => {
      const l = active[i];
      if (l) v.set(l.cosUp, l.leak, l.upPower, Math.max(l.edge, 1e-3));
    });
    const reach = shared.uLampReach.value;
    for (let i = 0; i < reach.length; i++) reach[i] = active[i]?.reach ?? 1e4;
    shared.uLampLo.value.forEach((v, i) => v.copy(active[i]?.lo ?? FAR_LO));
    shared.uLampHi.value.forEach((v, i) => v.copy(active[i]?.hi ?? FAR_HI));
  };
  applyLamps();
  const pickLamps = (camera: THREE.Camera) => {
    if (lamps.length <= MAX_LAMPS) return;
    const c = camera.position;
    const next = [...lamps].sort((p, q) => p.pos.distanceToSquared(c) - q.pos.distanceToSquared(c)).slice(0, MAX_LAMPS);
    if (next.every((l) => active.includes(l))) return;
    active = next;
    applyLamps();
  };
  // 世界的样子（atmosphere 上写的）：格子多粗、只用哪几色、灯是不是一直亮着
  const lampOn = () => {
    shared.uLampOn.value = Math.max(look.lamps ? 1 : 0, night);
  };
  lampOn();

  function update(dt: number, t: number, camera: THREE.Camera, frozen: boolean) {
    if (sunTurn) {
      if (!frozen) sunTime += dt;
      turnSun();
    }
    const nt = nightPose?.target ?? 0;
    if (nightK !== nt) {
      nightK = nt > nightK ? Math.min(nt, nightK + dt / NIGHT_TIME) : Math.max(nt, nightK - dt / NIGHT_TIME);
      night = smooth(nightK);
      sky.night(night);
      lampOn();
    }
    pickLamps(camera);
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
      if (g.anchor) {
        g.anchor.obj.updateWorldMatrix(true, false);
        g.pos.copy(g.anchor.at).applyMatrix4(g.anchor.obj.matrixWorld);
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
      if (b.sway) b.obj.quaternion.multiply(tq.setFromAxisAngle(SWAY_AXIS, Math.sin(tt * 0.9 + b.phase) * b.sway));
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
  // 太阳转（nx_sun_turn，度每分）：绕竖轴，从 Blender 里摆的方向起。按 SUN_STEP 秒一步跳，
  // 影子图不用每帧重画（光斑一步挪不到一个纹素）
  const sunBase = sunDir.clone();
  let sunTime = Number(new URLSearchParams(location.search).get('suntime')) || 0;
  let sunStep = NaN;
  const turnSun = () => {
    const k = Math.floor(sunTime / SUN_STEP);
    if (k === sunStep) return;
    sunStep = k;
    sunDir.copy(sunBase).applyAxisAngle(UP, (k * SUN_STEP * sunTurn * Math.PI) / (60 * 180));
    shared.uSun.value.copy(sunDir);
  };
  if (sunTurn) turnSun();
  const apply = () => {
    shared.uSun.value.copy(sunDir);
    shared.uWrap.value = wrap;
    shared.uShadowOut.value = shadowOut;
    shared.uPenumbra.value = penumbra;
    shared.uCaustic.value.copy(caustic);
    sky.set(sky.spec);
    applyLamps();
    lampOn();
    // 窗里的天的底色与种子也是共用的一份
    showOutlook(outlook);
  };
  shared.uWrap.value = wrap;
  shared.uShadowOut.value = shadowOut;
  shared.uPenumbra.value = penumbra;
  shared.uCaustic.value.copy(caustic);
  return {
    shadowOut,
    shadowReach,
    fall,
    get sunTime() {
      return sunTime;
    },
    set sunTime(v: number) {
      sunTime = v;
      if (sunTurn) turnSun();
    },
    scene, crystalScene, collider, entrances, spawn, portals, seams, wrap, items, arrivals, sky, windowSky, outlooks,
    get outlook() {
      return outlook;
    },
    get night() {
      return night;
    },
    showOutlook, poses, intro, style, look, apply, update,
    blockers() {
      const out: Blocker[] = [];
      for (const g of poses.values()) {
        if (g.k <= 0.001 && g.block[0].tris.length) out.push(g.block[0]);
        else if (g.k >= 0.999 && g.block[1].tris.length) out.push(g.block[1]);
      }
      return out;
    },
  };
}

/** 循环的大地：把世界里不动的东西在四周各复制一份（共用网格与材质），站在方块边上往外看也是连着的。
    缝、天、会动的东西不复制；碰撞只有中间这一份（人一走出方块就被挪回另一边，见 main.ts） */
function tile(scene: THREE.Scene, size: number, skip: Set<THREE.Object3D>) {
  const things = scene.children.filter((o) => !skip.has(o) && !o.userData.seam);
  for (let i = -1; i <= 1; i++)
    for (let j = -1; j <= 1; j++) {
      if (!i && !j) continue;
      for (const o of things) {
        const c = copyOf(o);
        c.position.x += i * size;
        c.position.z += j * size;
        scene.add(c);
      }
    }
}

/** 复制一个物体（连同子物体）：网格、材质共用，影子材质也共用（Object3D.clone 会把 userData 过一遍 JSON，材质就坏了） */
function copyOf(o: THREE.Object3D): THREE.Object3D {
  const m = o as THREE.Mesh;
  const c = m.isMesh ? new THREE.Mesh(m.geometry, m.material) : new THREE.Group();
  c.position.copy(o.position);
  c.quaternion.copy(o.quaternion);
  c.scale.copy(o.scale);
  c.renderOrder = o.renderOrder;
  if (o.userData.shadowMat) c.userData.shadowMat = o.userData.shadowMat;
  for (const k of o.children) c.add(copyOf(k));
  return c;
}

const tq = new THREE.Quaternion();
const UP = new THREE.Vector3(0, 1, 0);
/** 虚像 "最浓,近,远"；不是三个数就当没有 */
function ghostOf(v: unknown): [number, number, number] | undefined {
  if (typeof v !== 'string') return undefined;
  const p = v.split(/[,\s]+/).map(Number);
  return p.length === 3 && p.every(Number.isFinite) ? [p[0], p[1], p[2]] : undefined;
}
const SWAY_AXIS = new THREE.Vector3(1, 0, 0);
/** 太阳转的时候隔多少秒跳一步 */
const SUN_STEP = 0.25;
/** 只投影的东西（nx_mat=shade）：主画面里不画，影子图里照常写深度 */
const HIDDEN = new THREE.MeshBasicMaterial({ visible: false });
const SHADE_ONLY = shadowVariant(new THREE.ShaderMaterial({ uniforms: {} }));
const BLACK = new THREE.Color(0, 0, 0);
const FAR_LO = new THREE.Vector3(-1e5, -1e5, -1e5);
const FAR_HI = new THREE.Vector3(1e5, 1e5, 1e5);

export interface Look {
  grid: number;
  mask: number;
  lamps: boolean;
  /** 亮处的格子是几级（atmosphere 的 nx_grid_lit）；-1 ＝ 不按亮度 */
  lit: number;
}
/** 昼夜换一次要几秒 */
const NIGHT_TIME = 1.6;

function behaviorOf(obj: THREE.Object3D, u: Record<string, unknown>, faceDefault: boolean): Behavior | null {
  const spin = num(u.nx_spin, 0) * (Math.PI / 180);
  const bob = num(u.nx_bob, 0);
  const face = bool(u.nx_face, faceDefault);
  const sway = num(u.nx_sway, 0) * (Math.PI / 180);
  if (!spin && !bob && !face && !sway) return null;
  return {
    obj,
    basePos: obj.position.clone(),
    baseRot: obj.rotation.clone(),
    spin,
    bob,
    face,
    sway,
    phase: Math.random() * Math.PI * 2,
  };
}
