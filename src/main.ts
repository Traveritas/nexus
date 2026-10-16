import * as THREE from 'three';
import { Pipeline, MAX_FIELD, type Field, type FieldSource } from './pipeline';
import { SunShadow } from './shadow';
import { loadLevel, type Entrance, type Level, type Outlook, type Pose, type Portal } from './level';
import { PLAYER, Player } from './player';
import { SKY_NAMES, skyLabel } from './skybox';
import { shared } from './materials';
import { Ui, UI_SCALE, loadUiFont } from './ui';
import { PromptTag } from './prompt';
import { Diary, night, type Settings } from './diary';
import { ItemSystem, type Promptable } from './items/system';
import { MapView } from './mapview';
import { SiteCard } from './sitecard';
import { dreamt, edges, isReality, recordEdge, recordSite, sites } from './worlds';
import { RealName } from './realtext';
import { IntroPlayer, introSeen, stripIntro } from './intro';
import { Through, seamMatrix, seamSide, seamTube, seamTurn } from './seam';

/* 世界：?world=名字（public/scenes/<名字>.glb，默认 wake_fragment——现实的家，醒着的那一间）；?scene= 是旧写法，同义
   世界之间靠传送物（nx_type=portal）来往：走进去，或走近按 E。转场时格子一路变粗、蒙上雾色，新世界再一格格解析出来；
   现实与梦之间（入梦、醒来）不蒙色：粗到 32px 时两个世界按块交接，视野一路朝同一方向走（见 SLEEP）。
   缝（nx_type=seam，src/seam.ts）：门洞那边的世界一直留在内存里，透过门洞画出来，走过门槛就换过去，不转场（家的大门 ↔ 门外的原野）。
   循环的大地（atmosphere 的 nx_wrap）：走出方块从另一边回来。
   晶体（入口）通往真实的站点：走进去，整屏解析到底、化白。
   开场：第一次从根地址进来时停在标题的机位上，「点击醒来」以后木条掉进虚空、视角滑到床边（src/intro.ts）；?intro=1 强制再放一次，?intro=0 不放
   查询串：?pos=x,y,z（脚底）&yaw=度&pitch=度  ?freeze=1  ?hud=0  ?res=auto|full|half|quarter|eighth|sixteenth 世界的渲染分辨率  ?sky=主题（覆盖世界里的，见 docs/sky.md）  ?ramp=0..1 自动三色明暗的强度（默认 0.3）
   键：E 互动 · Q 按住捏手里的东西 · F 按住看看身上的 · Tab 日记（醒来、回到开场的 NEXUS 在日记里） · 1 原始世界 · 2 解析度场染色 · 3 色板 · 4 描边（关 / 格 / 细线） · 5 锁级 · 6 自动三色明暗强度 · G 飞行 · H 提示 · K 换天
   window.__nexus 供截图、测试脚本用 */

const q = new URLSearchParams(location.search);
if (q.has('ramp')) shared.uAutoRamp.value = THREE.MathUtils.clamp(Number(q.get('ramp')) || 0, 0, 1);
const canvas = document.getElementById('stage') as HTMLCanvasElement;
const hud = document.getElementById('hud')!;
const label = document.getElementById('label')!;
const siteName = new RealName(label);
const deg = Math.PI / 180;
const RETURN_KEY = 'nexus:return';
const DEV_KEY = 'nexus:dev';
const VISITED_KEY = 'nexus:visited';
/** 起点：现实的家（残片）。一开始在这里醒来，日记里「醒来」也回到这里，落在床边（到达点 home） */
const START = 'wake_fragment';
const START_AT = 'home';
/** 彩蛋：醒来时有 1% 醒错地方，落进另两个没选上的现实原型之一（各半），也落在床边 */
const ODD_WAKES = ['wake_white', 'wake_museum'];
const wakeWorld = () => (Math.random() < 0.01 ? ODD_WAKES[Math.floor(Math.random() * ODD_WAKES.length)] : START);

const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, powerPreference: 'high-performance' });
renderer.info.autoReset = false;
renderer.setPixelRatio(1);
/** 视野（竖直，度）；入梦、醒来时临时变（SLEEP.fovWide / fovNarrow） */
const FOV = 68;
const camera = new THREE.PerspectiveCamera(FOV, 16 / 9, 0.1, 400);
camera.rotation.order = 'YXZ';
const pipe = new Pipeline(renderer);
let shadow = new SunShadow();
/** 缝那边的世界自己的一张影子图：透过门洞看见的影子和走过去以后的一样（走过去时两张对调） */
let farShadow = new SunShadow();
const ui = new Ui(document.getElementById('ui') as HTMLCanvasElement);
const fontReady = loadUiFont();
const tag = new PromptTag(ui);
const items = new ItemSystem(ui, night);
/** 罗盘的地图：捏到底开、再捏到底收 */
const map = new MapView(ui, document.getElementById('maplabel')!, document.getElementById('glow') as HTMLCanvasElement);
items.onBloom = (id) => {
  if (id === 'compass') map.toggle(camera);
};
/** 日记本要等人和世界都有了才建（见「日记」一节）；resize 先于它跑 */
let diary: Diary | undefined;

/** 世界的渲染分辨率（日记 · 设置 · 画面）；?res=full|half|quarter|eighth|sixteenth 覆盖 */
let resMode: Settings['res'] = 'auto';
const RES_SHIFT = { full: 0, half: 1, quarter: 2, eighth: 3, sixteenth: 4 };
/** 自动：画布超过约 1920×1200 按半分辨率画世界，超过约 3200×1800（4K）按四分之一（像素化是填充率受限的，开销跟像素数成正比） */
const AUTO_HALF_PIXELS = 1920 * 1200;
const AUTO_QUARTER_PIXELS = 3200 * 1800;
function applyRes() {
  const { w, h } = pipe.size;
  const mode = (q.get('res') as typeof resMode | null) ?? resMode;
  const px = w * h;
  pipe.setShift(mode === 'auto' ? (px > AUTO_QUARTER_PIXELS ? 2 : px > AUTO_HALF_PIXELS ? 1 : 0) : RES_SHIFT[mode] ?? 0);
}

function resize() {
  const w = Math.max(8, Math.floor(innerWidth / 8) * 8);
  const h = Math.max(8, Math.floor(innerHeight / 8) * 8);
  renderer.setSize(w, h, false);
  canvas.style.width = `${w}px`;
  canvas.style.height = `${h}px`;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  pipe.setSize(w, h);
  applyRes();
  ui.setSize(w, h);
  diary?.setSize(ui.w, ui.h);
}
resize();
addEventListener('resize', resize);

// ── 世界 ──
const sceneUrl = (name: string) => `${import.meta.env.BASE_URL}scenes/${name}.glb`;
let world = q.get('world') ?? q.get('scene') ?? START;
let level: Level = await loadLevel(sceneUrl(world));
await fontReady;
const player = new Player(level.collider);
if (q.get('sky')) level.sky.set(q.get('sky')!);

function visited(): string[] {
  try {
    return JSON.parse(localStorage.getItem(VISITED_KEY) ?? '[]');
  } catch {
    return [];
  }
}
function markVisited(name: string) {
  try {
    const v = visited();
    if (!v.includes(name)) localStorage.setItem(VISITED_KEY, JSON.stringify([...v, name]));
  } catch {
    /* 存不了就算了 */
  }
}
markVisited(world);
/** 这个世界有站点（晶体）就记下来：罗盘的星座图在它旁边点一颗金星 */
function noteSites() {
  if (level.entrances.some((e) => e.url)) recordSite(world);
}
noteSites();

/** 预先取一下相邻世界的场景文件（只是暖一下浏览器缓存） */
function prefetchNeighbours(l: Level) {
  for (const to of new Set([...l.portals.map((p) => p.to), ...(l.fall ? [l.fall.to] : [])])) fetch(sceneUrl(to)).catch(() => {});
}
prefetchNeighbours(level);
items.attach(level, world);

// ── 缝（nx_type=seam）：门洞那边的世界和这个一起留在内存里，透过门洞画出来，走过门槛就换过去（不转场） ──
let beyond: { name: string; level: Level } | null = null;
const through = new Through();
/** 把这个世界的缝那边接上（换了世界就换；没有缝就放掉） */
async function link() {
  const to = level.seams[0]?.to ?? '';
  if (beyond?.name === to) return;
  if (beyond) disposeLevel(beyond.level);
  beyond = null;
  if (!to) return;
  const l = await loadLevel(sceneUrl(to)).catch((err) => {
    console.warn('[nexus] 缝那边接不上', to, err);
    return null;
  });
  if (!l) return;
  // 等它的时候已经去了别处：用不上了
  if ((level.seams[0]?.to ?? '') !== to || beyond) {
    disposeLevel(l);
    return;
  }
  beyond = { name: to, level: l };
  // 加载会改共享的天色与太阳，还给这个世界
  level.apply();
}
/** 这边的缝与那边对上的缝 */
function seamPair() {
  if (!beyond) return null;
  const name = beyond.name;
  const hs = level.seams.find((s) => s.to === name);
  const ts = beyond.level.seams.find((s) => s.to === world);
  return hs && ts ? { hs, ts, there: beyond.level } : null;
}
const UP = new THREE.Vector3(0, 1, 0);
/** 这一帧从 from 走到脚下：要是从缝的这一边、穿过门洞走到了那一边，就换到那个世界（位置、朝向、速度一起对过去） */
function crossSeam(from: THREE.Vector3) {
  const p = seamPair();
  if (!p || travel || !beyond) return;
  const a = seamSide(p.hs, from);
  const b = seamSide(p.hs, player.feet);
  if (!(a.along < 0 && b.along >= 0) || Math.abs(b.lateral) > p.hs.w / 2 || b.up < -0.6 || b.up > p.hs.h) return;
  const turn = seamTurn(p.hs, p.ts);
  player.shift(tmp.copy(player.feet).applyMatrix4(seamMatrix(p.hs, p.ts)).sub(player.feet));
  player.yaw += turn;
  player.vel.applyAxisAngle(UP, turn);
  const old = { name: world, level };
  [shadow, farShadow] = [farShadow, shadow];
  level = p.there;
  world = beyond.name;
  beyond = old;
  // 门（同名的 pose）在两边是同一扇
  for (const g of level.poses.values()) {
    const o = old.level.poses.get(g.name);
    if (o) {
      g.target = o.target;
      g.k = o.k;
    }
  }
  level.apply();
  player.setCollider(level.collider);
  lastArrival = '';
  markVisited(world);
  recordEdge(old.name, world);
  noteSites();
  items.attach(level, world);
  prefetchNeighbours(level);
  history.replaceState({ world, at: '' }, '', `?world=${encodeURIComponent(world)}`);
}
/** 循环的大地：走出方块就从另一边回来（四周画着复制，看不出挪过） */
function wrapAround() {
  const s = level.wrap;
  if (!s) return;
  const f = player.feet;
  const dx = f.x > s / 2 ? -s : f.x < -s / 2 ? s : 0;
  const dz = f.z > s / 2 ? -s : f.z < -s / 2 ? s : 0;
  if (dx || dz) player.shift(tmp.set(dx, 0, dz));
}

function disposeLevel(l: Level) {
  for (const s of [l.scene, l.crystalScene])
    s.traverse((o) => {
      const m = o as THREE.Mesh;
      if (!m.isMesh) return;
      m.geometry?.dispose();
      const mats = Array.isArray(m.material) ? m.material : [m.material];
      for (const mat of mats) mat?.dispose();
      (m.userData.shadowMat as THREE.Material | undefined)?.dispose();
    });
}

/** 刚到时若站在传送物里，不会又被带走：先走出它的范围才「上膛」（见 checkPortals） */
let armedFrom: THREE.Vector3 | null = null;
function arriveAt(at: string) {
  const a = (at && level.arrivals.get(at)) || level.spawn;
  player.feet.copy(a.pos);
  player.vel.set(0, 0, 0);
  player.yaw = a.yaw;
  player.pitch = -0.04;
  armedFrom = a.pos.clone();
}
let lastArrival = '';
function respawn() {
  arriveAt(lastArrival);
}
respawn();
await link();

interface Saved { x: number; y: number; z: number; yaw: number; pitch: number; world?: string }
function restore(key: string) {
  try {
    const raw = sessionStorage.getItem(key);
    if (!raw) return false;
    sessionStorage.removeItem(key);
    const s = JSON.parse(raw) as Saved;
    if (s.world && s.world !== world) return false;
    player.feet.set(s.x, s.y, s.z);
    player.vel.set(0, 0, 0);
    player.yaw = s.yaw;
    player.pitch = s.pitch;
    armedFrom = player.feet.clone();
    return true;
  } catch {
    return false;
  }
}
function save(key: string, s: Saved) {
  try {
    sessionStorage.setItem(key, JSON.stringify(s));
  } catch {
    /* 存不了就算了：回来时从出生点开始 */
  }
}

// 从站点按后退回来：回到入口前几步；开发时改了场景自动刷新，也回到刚才的位置
const restored = restore(RETURN_KEY) || (import.meta.env.DEV && restore(DEV_KEY));
if (q.get('pos')) {
  const [x, y, z] = q.get('pos')!.split(',').map(Number);
  player.feet.set(x, y, z);
  armedFrom = player.feet.clone();
}
if (q.get('yaw')) player.yaw = Number(q.get('yaw')) * deg;
if (q.get('pitch')) player.pitch = Number(q.get('pitch')) * deg;
if (import.meta.env.DEV) {
  addEventListener('beforeunload', () => {
    if (!entering && !travel && !gaze) save(DEV_KEY, { ...player.feet, yaw: player.yaw, pitch: player.pitch, world });
  });
}
history.replaceState({ world, at: '' }, '');

let frozen = q.get('freeze') === '1';

// ── 开场 ──
// 第一次从根地址进来（不是深链接、不是从站点退回来）才放；?intro=1 强制。不放就把那些木条拿掉
const deepLink = q.has('world') || q.has('scene') || q.has('pos');
let intro: IntroPlayer | null =
  level.intro && q.get('intro') !== '0' && (q.get('intro') === '1' || (!deepLink && !restored && !introSeen()))
    ? new IntroPlayer(level.intro, document.getElementById('intro') as HTMLCanvasElement)
    : null;
if (!intro) stripIntro(level.intro);
const introView = { pos: new THREE.Vector3(), yaw: 0, pitch: 0 };
/** 点击醒来：终点每次都一样——人放回床边（到达点），眼睛平视，回头望着标题的机位（木条掉进去的那片虚空）。
    不取此刻人身上的状态：眼高的缓动、走路的起伏、朝向都会让终点每次差一点 */
function wakeIntro() {
  // 从日记里翻回来时，等转场解析完再认点击
  if (intro?.phase !== 'title' || travel || !level.intro) return;
  arriveAt(lastArrival);
  const back = level.intro.pos.clone().sub(player.feet);
  const end = { yaw: Math.atan2(-back.x, -back.z), pitch: 0 };
  player.yaw = end.yaw;
  player.pitch = end.pitch;
  const pos = player.feet.clone();
  pos.y += PLAYER.eye;
  intro.wake({ pos, ...end });
  introEnd = end;
}
let introEnd = { yaw: 0, pitch: 0 };
if (q.get('hud') === '0') hud.classList.add('off');

// ── 世界之间的转场 ──
interface Travel {
  /** out 旧世界变粗 · hand 马赛克交接（只有入梦、醒来） · in 新世界解析出来 */
  phase: 'out' | 'hand' | 'in';
  t: number;
  to: string;
  at: string;
  push: boolean;
  next: Promise<Level | null>;
  ready: Level | null | undefined;
  veilFrom: THREE.Color;
  veilTo: THREE.Color;
  /** 从哪个世界来；是不是穿过传送物来的（是的话记一条走过的连接，罗盘的星座图用） */
  from: string;
  via: boolean;
  /** 到了以后停在开场的标题上（日记里点 NEXUS） */
  dream: boolean;
  /** plain 同一边之间（变粗、蒙雾色）；sleep 现实 → 梦；wake 梦 → 现实 */
  kind: 'plain' | 'sleep' | 'wake';
  /** 掉进别处（atmosphere 的 nx_fall_to）：变粗时人照样往下掉，到了从半空落在到达点上 */
  fall: boolean;
}
let travel: Travel | null = null;
/** 掉进别处时，到了从到达点上方多高落下（米；家里天花板 2.5m，眼睛不能穿出去） */
const FALL_IN = 0.6;
let dissolve = 0;
const OUT = 0.75;
const IN = 1.0;
const veilCol = new THREE.Color();
/** 入梦与醒来：只靠分辨率。全屏均匀地一级级粗到 32px（现实那一侧粗到 4–16px 时一块块落进色板），
    两个世界在最粗的马赛克里交接（按块一块块换），再一级级解析出来；不蒙色、不黑场。醒来是入梦倒着放。
    秒数都在这里，window.__nexus.sleep 可以现调 */
const SLEEP = {
  /** 入睡：现实粗到底 · 交接 · 梦解析出来 */
  out: 2.2,
  hand: 0.35,
  in: 2.0,
  /** 醒来：梦粗到底 · 交接 · 现实解析出来 */
  wakeOut: 1.6,
  wakeHand: 0.35,
  wakeIn: 2.4,
  /** 曲线：整段是一个 V——变粗先慢后快（在细的几级流连，然后塌成色块），交接一闪而过，
      解析先快后慢（很快从色块里浮出来，最后几级慢慢落定）。数越大，两头越拖、谷底越快 */
  outPow: 1.5,
  inPow: 1.5,
  /** 视野（竖直，度）一路朝同一个方向走：从静止起步越来越快，交接那一刻最快，新世界带着这股速度出来、再慢慢停住
      （三次曲线：起止两头速度、加速度都是 0）。交接那段视野也不停，新世界的视野从交接一开始就在走。
      入梦：现实收窄（往里压），交接，梦从很宽收回正常——一直在往前沉。
      醒来反过来：梦拉宽（往后退），交接，现实从很窄拉回正常。
      格子是一级级跳的，视野是连续的，填满两级之间的空档 */
  fovWide: 120,
  fovNarrow: 30,
};
/** 视野的曲线：旧世界从静止加速冲向交接（三次），新世界从最快减速到静止 */
const accel3 = (x: number) => THREE.MathUtils.clamp(x, 0, 1) ** 3;
const decel3 = (x: number) => 1 - (1 - THREE.MathUtils.clamp(x, 0, 1)) ** 3;
/** 新世界的视野：从交接开始算，走完交接与解析两段 */
const fovIn = (tr: Travel, t: number) => {
  const handT = tr.kind === 'sleep' ? SLEEP.hand : SLEEP.wakeHand;
  const inT = tr.kind === 'sleep' ? SLEEP.in : SLEEP.wakeIn;
  return THREE.MathUtils.lerp(fovEnds(tr.kind).in, FOV, decel3(t / (handT + inT)));
};
/** 旧世界的视野走向哪头、新世界的视野从哪头来 */
const fovEnds = (kind: Travel['kind']) =>
  kind === 'sleep' ? { out: SLEEP.fovNarrow, in: SLEEP.fovWide } : { out: SLEEP.fovWide, in: SLEEP.fovNarrow };
/** 现实那一侧落进色板的程度（按粗细：4px 起、16px 落完）；交给管线的 uDream */
const paletteAt = (k: number) => THREE.MathUtils.smoothstep(k, 0.45, 0.85);
let travelDream = 0;
let hand = -1;
/** 这一帧的视野（竖直，度） */
let travelFov = FOV;
const fogSrgb = () => shared.uFogCol.value.clone().convertLinearToSRGB();

function go(to: string, at = '', push = true, via = false, dream = false, fall = false) {
  if (travel || entering || !to) return;
  const next = loadLevel(sceneUrl(to)).catch((err) => {
    console.warn('[nexus] 去不了', to, err);
    return null;
  });
  // 回到开场的标题（日记里点 NEXUS）落在梦的画面上，不算醒来
  const kind = dream || isReality(world) === isReality(to) ? 'plain' : isReality(world) ? 'sleep' : 'wake';
  const tr: Travel = { phase: 'out', t: 0, to, at, push, next, ready: undefined, veilFrom: fogSrgb(), veilTo: fogSrgb(), from: world, via, dream, kind, fall };
  map.closeNow();
  travel = tr;
  if (!fall) player.vel.set(0, 0, 0);
  next.then((l) => {
    tr.ready = l;
    // 加载新世界会改共享的天色与太阳；转场还没走完，先还给当前的世界
    level.apply();
  });
}

function stepTravel(dt: number) {
  if (!travel) return;
  travel.t += dt;
  const soft = travel.kind !== 'plain';
  if (travel.phase === 'out') {
    const T = travel.kind === 'sleep' ? SLEEP.out : travel.kind === 'wake' ? SLEEP.wakeOut : OUT;
    dissolve = soft ? Math.min(1, travel.t / T) ** SLEEP.outPow : Math.min(1, travel.t / T);
    if (travel.kind === 'sleep') travelDream = paletteAt(dissolve);
    // 视野一开始就动（格子还没开始跳的时候），越到最粗越慢
    if (soft) travelFov = THREE.MathUtils.lerp(FOV, fovEnds(travel.kind).out, accel3(travel.t / T));
    veilCol.copy(travel.veilFrom);
    // 入梦、醒来：粗到底以后再多停一帧，存下的那一帧才整屏都是 32px
    if (travel.t < T + (soft ? 0.05 : 0) || travel.ready === undefined) return;
    const l = travel.ready;
    if (!l) {
      // 没去成：原路解析回来
      travel.phase = 'in';
      travel.t = 0;
      return;
    }
    if (soft) pipe.holdFrame();
    disposeLevel(level);
    level = l;
    // 开场还没放完就走了（只有测试会这样）：收起来，别把人锁在新世界里
    intro?.cancel();
    intro = null;
    // 日记里点 NEXUS：回到现实的家，停在标题的机位上，木条重新拼成字，再点一下醒来
    if (travel.dream && level.intro) intro = new IntroPlayer(level.intro, document.getElementById('intro') as HTMLCanvasElement);
    else stripIntro(level.intro);
    level.apply();
    world = travel.to;
    player.setCollider(level.collider);
    lastArrival = travel.at;
    arriveAt(travel.at);
    // 掉进来的：从到达点上方 FALL_IN 米落下，带着一点往下的速度，落地那一下看得出来
    if (travel.fall) {
      player.feet.y += FALL_IN;
      player.vel.y = -3;
    }
    markVisited(world);
    if (travel.via) recordEdge(travel.from, world);
    noteSites();
    items.attach(level, world);
    prefetchNeighbours(level);
    link();
    if (travel.push) history.pushState({ world, at: travel.at }, '', `?world=${encodeURIComponent(world)}`);
    travel.veilTo = fogSrgb();
    travel.phase = soft ? 'hand' : 'in';
    travel.t = 0;
    if (soft) {
      hand = 0;
      travelFov = fovEnds(travel.kind).in;
      travelDream = isReality(world) ? 1 : 0;
    }
  } else if (travel.phase === 'hand') {
    // 马赛克交接：两边都是 32px 的色块，一块块从旧世界换成新世界
    hand = THREE.MathUtils.smoothstep(travel.t, 0, travel.kind === 'sleep' ? SLEEP.hand : SLEEP.wakeHand);
    travelFov = fovIn(travel, travel.t);
    if (hand < 1) return;
    hand = -1;
    travel.phase = 'in';
    travel.t = 0;
  } else if (soft) {
    // 一级级解析出来；落在现实的，色板先一块块松开，格子再变细到连续
    const k = Math.min(1, travel.t / (travel.kind === 'sleep' ? SLEEP.in : SLEEP.wakeIn));
    dissolve = (1 - k) ** SLEEP.inPow;
    travelFov = fovIn(travel, travel.t + (travel.kind === 'sleep' ? SLEEP.hand : SLEEP.wakeHand));
    travelDream = isReality(world) ? paletteAt(dissolve) : 0;
    if (k >= 1) {
      travel = null;
      dissolve = 0;
      travelDream = 0;
      travelFov = FOV;
    }
  } else {
    const k = Math.min(1, travel.t / IN);
    dissolve = 1 - k;
    veilCol.copy(travel.veilFrom).lerp(travel.veilTo, Math.min(1, k * 3));
    if (k >= 1) {
      travel = null;
      dissolve = 0;
    }
  }
}

// 浏览器后退 / 前进：在世界之间来回
addEventListener('popstate', (e) => {
  const s = e.state as { world?: string; at?: string } | null;
  if (s?.world && s.world !== world) go(s.world, s.at ?? '', false);
});

// ── 日记 ──
const book = new Diary(ui, {
  wake: () => go(wakeWorld(), START_AT),
  title: () => go(START, START_AT, true, false, true),
  apply: (s) => {
    player.sens = s.sens;
    resMode = s.res;
    applyRes();
    hud.classList.toggle('off', !s.hud || q.get('hud') === '0');
  },
  world: () => world,
  visited,
  items: () => ({ owned: items.owned, held: items.held }),
  hold: (id) => items.hold(id),
});
diary = book;
book.setSize(ui.w, ui.h);

// ── 键 ──
let interact = false;
addEventListener('keydown', (e) => {
  // 开场里不认键（Tab 也别让浏览器拿去换焦点）
  if (intro) {
    if (e.code === 'Tab' || e.code === 'Space') e.preventDefault();
    return;
  }
  // 凑在窗口往外看：只认窗前那几个键
  if (gaze) {
    if (e.code === 'Tab' || e.code === 'Space' || e.code === 'ArrowLeft' || e.code === 'ArrowRight' || e.code === 'ArrowDown') e.preventDefault();
    if (!e.repeat) gazeKey(e.code);
    return;
  }
  if (e.code === 'Tab') {
    e.preventDefault();
    if (!e.repeat && !travel && !entering && !items.busy && !items.ringActive) {
      items.use(false);
      book.toggle();
    }
    return;
  }
  if (e.code === 'Escape' && book.active && document.pointerLockElement !== canvas) book.close();
  // 日记摊开时，世界里的按键都不算
  if (book.active) return;
  const f = pipe.flags;
  if (e.code === 'Digit1') f.raw = !f.raw;
  if (e.code === 'Digit2') f.field = !f.field;
  if (e.code === 'Digit3') f.palette = !f.palette;
  if (e.code === 'Digit4') f.outline = (f.outline + 1) % 3;
  if (e.code === 'Digit5') f.lock = f.lock >= 2 ? -1 : f.lock + 1;
  // 三色强度：默认 → 一半 → 全 → 关 → 默认
  if (e.code === 'Digit6') { const r = [0.3, 0.5, 1, 0]; shared.uAutoRamp.value = r[(r.indexOf(shared.uAutoRamp.value) + 1) % r.length]; }
  if (e.code === 'KeyH') hud.classList.toggle('off');
  if (e.code === 'KeyK') level.sky.set(SKY_NAMES[(SKY_NAMES.indexOf(level.sky.name) + 1) % SKY_NAMES.length]);
  if (e.code === 'KeyR' && e.shiftKey) respawn();
  if (e.code === 'KeyE' && !e.repeat) interact = true;
  // 按住 Q：把手里的东西举到眼前、捏紧；松开放下（醒来在日记「记录」那页）
  if (e.code === 'KeyQ' && !e.repeat) items.use(true);
  // 按住 F：身上的东西排成一道弧围在眼前；松开拿起正看着的那件
  if (e.code === 'KeyF' && !e.repeat) items.showRing(true, camera);
  if (e.code === 'Space' && document.pointerLockElement === canvas) e.preventDefault();
});
addEventListener('keyup', (e) => {
  if (e.code === 'KeyQ') items.use(false);
  if (e.code === 'KeyF') items.showRing(false, camera);
});
addEventListener('blur', () => {
  items.use(false);
  items.showRing(false, camera);
});

let dragging = false;
const lockPointer = () => {
  // 刚按 Esc 放开后浏览器有一小段冷却，这时要不到锁，不要紧
  (canvas.requestPointerLock?.() as Promise<void> | undefined)?.catch?.(() => {});
};
canvas.addEventListener('mousedown', (e) => {
  if (intro) {
    if (e.button === 0) wakeIntro();
    lockPointer();
    return;
  }
  if (book.active) {
    if (e.button === 0) book.click();
    lockPointer();
    return;
  }
  dragging = true;
  lockPointer();
});
addEventListener('mouseup', () => (dragging = false));
addEventListener('mousemove', (e) => {
  const locked = document.pointerLockElement === canvas;
  if (intro) return;
  if (book.active) {
    if (locked) book.move(e.movementX, e.movementY);
    else {
      const r = canvas.getBoundingClientRect();
      book.moveTo((e.clientX - r.left) / UI_SCALE, (e.clientY - r.top) / UI_SCALE);
    }
    return;
  }
  if (gaze) {
    if (locked || dragging) gazeLook(e.movementX, e.movementY);
    return;
  }
  if (locked || dragging) player.look(e.movementX, e.movementY);
});
addEventListener('wheel', (e) => !book.active && player.nudge(-e.deltaY * 0.012), { passive: true });

// ── 入口（晶体 → 站点） ──
let entering: Entrance | null = null;
let resolve = 0;

addEventListener('pageshow', (e) => {
  // 从站点按后退、页面从缓存里恢复：退回入口前，重新开始
  if (e.persisted) {
    restore(RETURN_KEY);
    entering = null;
    gaze = null;
    card.hide();
    resolve = 0;
    for (const g of level.poses.values()) if (g.on === 'cue') g.target = g.k = 0;
  }
});

// ── 窗（窗景 → 站点）：走近窗按 E 推开窗——窗扇（cue 的 pose）往屋里开，视角凑到窗口往外看，站点卡片浮出来。
//    凑在窗口时：A / D（← / →）换一处窗景，E（Enter）进入，S（Esc、↓）退回屋里 ──
const card = new SiteCard();
const windowTags = new Map<Outlook | Pose, Promptable>();
function tagOf(key: Outlook | Pose, title: string): Promptable {
  let p = windowTags.get(key);
  if (!p) windowTags.set(key, (p = { pos: key.pos, title }));
  p.title = title;
  return p;
}

// ── 按 E 的东西：拾起的物品、窗景、门与开关（按键型的 pose）、按键型的传送物，一起挑出正对着的那一件 ──
//    纸签挂在它上面，按 E 用的也是它：挂着的和按下去的永远是同一件 ──

/** 一件够得着的：纸签、离眼睛多远、偏离视线多少（弧度）、按下去做什么 */
interface Option {
  p: Promptable;
  d: number;
  a: number;
  act: () => void;
}

/** 挂着纸签的那一件 */
let focus: Promptable | null = null;
/** 主要看偏离视线多少；远一米算多偏这么些弧度 */
const PER_METER = 0.08;
/** 已经挂着纸签的那件再让这么些弧度：两件挨着时纸签不来回跳 */
const KEEP = 0.1;

function pickFocus(): Option | null {
  if (intro || travel || entering || gaze || book.active || items.busy || items.ringActive) return (focus = null);
  camera.getWorldDirection(look);
  const opts: Option[] = [];
  /** reach：比 radius 再远多少还够得着；near：贴得这么近时不在眼前也算 */
  const consider = (pos: THREE.Vector3, radius: number, reach: number, near: number, p: () => Promptable, act: () => void) => {
    const d = eye.distanceTo(pos);
    if (d > radius + reach) return;
    tmp.copy(pos).sub(eye).normalize();
    const dot = tmp.dot(look);
    // 不在眼前的只在贴得很近时才算：几扇门挨着时，按 E 开的是看着的那扇，不是身后更近的那扇
    if (dot < 0.55 && d > near) return;
    opts.push({ p: p(), d, a: Math.acos(Math.min(1, dot)), act });
  };
  for (const { p, radius } of items.pickables()) consider(p.pos, radius, 1.2, radius, () => p, () => items.pick(p, camera));
  const ol = level.outlooks[level.outlook];
  if (ol) consider(ol.pos, ol.radius, 1.2, Math.min(ol.radius, 0.7), () => tagOf(ol, '推开窗'), openWindow);
  for (const g of level.poses.values()) {
    if (g.on !== 'key') continue;
    // 纸签可以写成「原样时|另一个样子时」（开关：开灯|关灯）
    const [t0, t1] = g.title.split('|');
    consider(g.pos, g.radius, 1.2, Math.min(g.radius, 0.7), () => tagOf(g, (g.target > 0.5 ? t1 : t0) ?? t0), () => (g.target = g.target > 0.5 ? 0 : 1));
  }
  for (const p of level.portals) {
    if (p.mode === 'key') consider(p.pos, p.radius, 1.8, p.radius, () => p, () => go(p.to, p.at, true, true));
  }
  let best: Option | null = null;
  let bs = Infinity;
  for (const o of opts) {
    const s = o.a + o.d * PER_METER - (o.p === focus ? KEEP : 0);
    if (s < bs) {
      bs = s;
      best = o;
    }
  }
  focus = best?.p ?? null;
  return best;
}

/** 凑在窗口往外看：in 凑过去 · look 看着（卡片在） · out 退回屋里 · go 进站（化白）。
    from 是推开窗那一刻的眼睛，退回时回到那里；nudge 是看着时鼠标带一点的偏转 */
interface Gaze {
  phase: 'in' | 'look' | 'out' | 'go';
  t: number;
  from: { pos: THREE.Vector3; yaw: number; pitch: number };
  nudge: THREE.Vector2;
  /** 换窗景：往哪边换、换了几秒（中间那一下窗外一亮，换掉天与卡片） */
  swap: { dir: number; t: number; done: boolean } | null;
  gone: boolean;
}
let gaze: Gaze | null = null;
const GAZE_IN = 1.3;
const GAZE_OUT = 0.9;
const SWAP = 0.5;
const NUDGE = 0.12;

function openWindow() {
  for (const g of level.poses.values()) if (g.on === 'cue') g.target = 1;
  gaze = {
    phase: 'in',
    t: 0,
    from: { pos: eye.clone(), yaw: player.yaw, pitch: player.pitch },
    nudge: new THREE.Vector2(),
    swap: null,
    gone: false,
  };
  map.closeNow();
}

function leaveWindow() {
  if (!gaze || gaze.phase !== 'look') return;
  gaze.phase = 'out';
  gaze.t = 0;
  card.hide();
  for (const g of level.poses.values()) if (g.on === 'cue') g.target = 0;
}

function enterWindow() {
  if (!gaze || gaze.phase !== 'look' || gaze.swap || !level.outlooks[level.outlook]?.url) return;
  gaze.phase = 'go';
  gaze.t = 0;
  card.hide();
}

function switchWindow(dir: number) {
  if (!gaze || gaze.phase !== 'look' || gaze.swap || level.outlooks.length < 2) return;
  gaze.swap = { dir, t: 0, done: false };
  card.swapOut(dir);
}

/** 窗前那一套的按键；凑在窗口时别的键都不算 */
function gazeKey(code: string) {
  if (code === 'KeyA' || code === 'ArrowLeft') switchWindow(-1);
  else if (code === 'KeyD' || code === 'ArrowRight') switchWindow(1);
  else if (code === 'KeyE' || code === 'Enter') enterWindow();
  else if (code === 'KeyS' || code === 'Escape' || code === 'ArrowDown' || code === 'Backspace') leaveWindow();
}

const lerpAngle = (a: number, b: number, k: number) => a + Math.atan2(Math.sin(b - a), Math.cos(b - a)) * k;
const ease = (k: number) => k * k * (3 - 2 * k);

/** 每帧：推着状态走，把眼睛摆到该在的地方（camera），并推着化白（resolve） */
function stepGaze(dt: number) {
  if (!gaze) return;
  const g = gaze;
  g.t += dt;
  const view = level.outlooks[0]?.view;
  if (!view) {
    gaze = null;
    return;
  }
  const yaw = view.yaw + g.nudge.x;
  const pitch = view.pitch + g.nudge.y;
  let k = 1;
  if (g.phase === 'in') {
    k = ease(Math.min(1, g.t / GAZE_IN));
    if (g.t >= GAZE_IN) {
      g.phase = 'look';
      card.show(level.outlooks[level.outlook], level.outlook, level.outlooks.length);
    }
  } else if (g.phase === 'out') {
    k = 1 - ease(Math.min(1, g.t / GAZE_OUT));
    if (g.t >= GAZE_OUT) {
      gaze = null;
      player.yaw = g.from.yaw;
      player.pitch = g.from.pitch;
      return;
    }
  }
  camera.position.lerpVectors(g.from.pos, view.pos, k);
  camera.rotation.set(THREE.MathUtils.lerp(g.from.pitch, pitch, k), lerpAngle(g.from.yaw, yaw, k), 0);
  camera.updateMatrixWorld();

  resolve = 0;
  if (g.swap) {
    const s = g.swap;
    s.t += dt;
    resolve = 0.8 * Math.sin(Math.PI * Math.min(1, s.t / SWAP));
    if (!s.done && s.t >= SWAP / 2) {
      s.done = true;
      level.showOutlook(level.outlook + s.dir);
      card.swapIn(level.outlooks[level.outlook], level.outlook, level.outlooks.length);
    }
    if (s.t >= SWAP) g.swap = null;
  }
  if (g.phase === 'go') {
    resolve = Math.min(1, g.t * 1.3);
    if (resolve >= 1 && !g.gone) {
      g.gone = true;
      // 回来时站在推开窗前的地方，窗关着
      save(RETURN_KEY, { x: player.feet.x, y: player.feet.y + 0.05, z: player.feet.z, yaw: g.from.yaw, pitch: 0, world });
      const url = level.outlooks[level.outlook].url;
      setTimeout(() => location.assign(url), 120);
    }
  }
  if (card.shown || g.phase === 'go') card.tone(level.windowSky?.tone(frozen ? 0 : t) ?? { bg: '#edf0f4', ink: '#232830', dark: false });
}

// 指针锁着时按 Esc，浏览器先把锁放了、不一定把键传进来：看着窗外时丢了锁也算退回
document.addEventListener('pointerlockchange', () => {
  if (!document.pointerLockElement && gaze?.phase === 'look') leaveWindow();
});

/** 看着时，鼠标只带一点偏转，松开不回弹（人还在窗口，只是头偏了一点） */
function gazeLook(dx: number, dy: number) {
  if (!gaze || gaze.phase !== 'look') return;
  const s = 0.0016 * player.sens;
  gaze.nudge.x = THREE.MathUtils.clamp(gaze.nudge.x - dx * s, -NUDGE, NUDGE);
  gaze.nudge.y = THREE.MathUtils.clamp(gaze.nudge.y - dy * s, -NUDGE * 0.7, NUDGE * 0.7);
}

function enter(e: Entrance) {
  entering = e;
  const back = player.forward().multiplyScalar(-2.6);
  save(RETURN_KEY, {
    x: player.feet.x + back.x,
    y: player.feet.y + 0.05,
    z: player.feet.z + back.z,
    yaw: player.yaw,
    pitch: 0,
    world,
  });
  setTimeout(() => location.assign(e.url), 160);
}

// ── 解析度场与传送物共用的临时量 ──
const tmp = new THREE.Vector3();
const edge = new THREE.Vector3();
const right = new THREE.Vector3();
const eye = new THREE.Vector3();
const body = new THREE.Vector3();
const look = new THREE.Vector3();

/** 走进型的传送物：走进去就走（按键型的和别的按 E 的东西一起挑，见 pickFocus） */
function checkPortals() {
  if (travel || entering) return;
  body.copy(player.feet);
  body.y += 0.9;
  const inside = (p: Portal, margin = 0) =>
    Math.hypot(body.x - p.pos.x, body.z - p.pos.z) < p.radius + margin && Math.abs(body.y - p.pos.y) < 1.3;
  // 刚到 / 刚被放下时若正站在某个走进型的传送物里，要先走出来（留 0.3m 余量）才上膛
  if (armedFrom && !level.portals.some((p) => p.mode === 'walk' && inside(p, 0.3))) armedFrom = null;
  if (armedFrom) return;
  // 要门开着的：门没开到底（还关着、正在开）就不算
  const open = (p: Portal) => !p.need || (level.poses.get(p.need)?.k ?? 0) > 0.85;
  for (const p of level.portals) {
    if (p.mode === 'walk' && open(p) && inside(p)) {
      go(p.to, p.at, true, true);
      return;
    }
  }
}

function fieldOf(prompt: Promptable | null): Field {
  const { w, h } = pipe.size;
  const sources: (FieldSource & { d: number })[] = [];
  let prox = 0;
  let nearest: Entrance | null = null;
  let nearestD = Infinity;
  right.setFromMatrixColumn(camera.matrixWorld, 0);
  for (const e of level.entrances) {
    const c = e.crystal.mesh.position;
    const d = camera.position.distanceTo(c);
    prox = Math.max(prox, 1 - THREE.MathUtils.smoothstep(d, 2.2, 18));
    if (d < nearestD) {
      nearestD = d;
      nearest = e;
    }
    tmp.copy(c).applyMatrix4(camera.matrixWorldInverse);
    if (tmp.z > -0.1) continue;
    const p = c.clone().project(camera);
    edge.copy(right).multiplyScalar(e.crystal.radius).add(c).project(camera);
    sources.push({
      x: (p.x * 0.5 + 0.5) * w,
      y: (p.y * 0.5 + 0.5) * h,
      r: Math.abs(edge.x - p.x) * 0.5 * w,
      d,
    });
  }
  sources.sort((a, b) => a.d - b.d);

  // 走近一个入口：周围一路解析到底；穿进晶体就进站。后退可以撤回
  let target = 0;
  if (nearest && nearest.url && !travel) {
    const r = nearest.crystal.radius;
    target = 1 - THREE.MathUtils.smoothstep(nearestD, r * 0.9, r * 7);
    if (!entering && nearestD < r * 0.9) enter(nearest);
  }
  // 凑在窗口时的化白（换景的一亮、进站）由 stepGaze 推
  if (!gaze) resolve = entering ? Math.min(1, resolve + 0.12) : target;

  // 晶体的名字连着真实的站点，是「现实的字」（src/realtext.ts）：走近时对上焦；有纸签时让开
  if (nearest) siteName.set(nearest.title, nearest.url);
  const near = nearest && !prompt ? 1 - THREE.MathUtils.smoothstep(nearestD, 4, 9) : 0;
  siteName.focus(near, near * (1 - resolve) * (1 - dissolve));

  return { sources: sources.slice(0, MAX_FIELD), prox, resolve, dissolve, veilCol, bare: !!travel && travel.kind !== 'plain', hand: hand >= 0 ? hand : undefined };
}

// ── 主循环 ──
const clock = new THREE.Clock();
let t = 0;
/** 这一帧走之前脚在哪（看有没有穿过缝） */
const stepFrom = new THREE.Vector3();
let fps = 0;

function frame(dt: number) {
  // 渲染计数按整帧累计（__nexus.info）
  renderer.info.reset();
  if (!frozen) t += dt;
  stepTravel(dt);
  // 停住的门（开着或关着）挡人；转到一半时不挡
  player.dynamic = level.blockers();
  stepFrom.copy(player.feet);
  player.update(dt, !!entering || !!gaze || !!travel || book.active || items.locked || !!intro);
  crossSeam(stepFrom);
  wrapAround();
  // 掉进别处：这个世界指定了掉下去的去处，就不回出生点
  const fall = level.fall;
  if (!travel && fall && player.feet.y < fall.y) go(fall.to, fall.at, true, true, false, true);
  else if (!travel && player.feet.y < -40) respawn();
  player.eyePosition(eye);
  camera.position.copy(eye);
  camera.rotation.set(player.pitch, player.yaw, 0);
  if (intro) {
    if (intro.update(dt, introView)) {
      // 放完了：交还给人，朝向就是滑到的那个
      player.yaw = introEnd.yaw;
      player.pitch = introEnd.pitch;
      intro = null;
    }
    eye.copy(introView.pos);
    camera.position.copy(eye);
    camera.rotation.set(introView.pitch, introView.yaw, 0);
  }
  const fov = travelFov;
  if (camera.fov !== fov) {
    camera.fov = fov;
    camera.updateProjectionMatrix();
  }
  camera.updateMatrixWorld();
  stepGaze(dt);

  items.update(dt, { world, feet: player.feet, t }, camera);
  checkPortals();
  // 纸签挂在正对着的那一件上；按 E 用的就是它
  const opt = pickFocus();
  if (opt && interact) {
    tag.press(opt.p);
    opt.act();
  }
  interact = false;
  const prompt: Promptable | null = opt?.p ?? null;
  level.update(dt, t, camera, frozen);
  for (const e of level.entrances) e.crystal.update(camera, pipe.pixTexture);
  const field = fieldOf(prompt);
  // 窗景不挂站名：走近窗有纸签，推开窗有站点卡片，名字在卡片上
  field.sources = [...items.sources(camera), ...field.sources].slice(0, MAX_FIELD);
  shadow.render(renderer, level.scene, player.feet, level.shadowReach);
  book.update(dt);
  field.drowse = Math.max(book.drowse, items.drowse);
  map.update(dt);
  field.dim = map.dim(items.handScreen(camera, pipe.size.w, pipe.size.h), pipe.size.w, pipe.size.h);
  field.glow = map.layout(camera, { level, world, visited: dreamt(visited()), edges: edges(), sites: sites() }, book.active || items.ringActive || !!travel);
  // 现实的世界是干净低模，不做像素化（只有转场时变粗）
  pipe.setClean(level.style === 'clean');
  // 世界自己的格子粗细与色板子集（家的室外：8px、只用几枚冷色）
  pipe.setLook(level.look.grid, level.look.mask, level.look.lit);
  // 开场：标题是梦的画面，滑向床边时醒过来
  pipe.setDream(Math.max(intro?.dream ?? 0, travelDream));
  // 缝在眼前：世界画完以后，透过门洞把那边也画进同一张世界图
  for (const s of level.seams) seamTube(s, camera.position);
  const pair = travel ? null : seamPair();
  const thru = pair && through.visible(pair.hs, camera)
    ? (r: THREE.WebGLRenderer) => through.draw(r, camera, level, pair.hs, pair.there, pair.ts, { here: shadow, there: farShadow }, dt, t, frozen)
    : undefined;
  if (pair && thru) {
    // 那边的影子图：用那边的太阳，跟着人对过去的位置
    pair.there.apply();
    farShadow.render(renderer, pair.there.scene, tmp.copy(player.feet).applyMatrix4(seamMatrix(pair.hs, pair.ts)), pair.there.shadowReach);
    level.apply();
    shadow.bind();
  }
  pipe.render(level.scene, level.crystalScene, camera, field, items.hand, thru);
  book.render(renderer);
  ui.clear();
  tag.update(dt, intro || travel || entering || gaze || book.active || items.busy || items.ringActive ? null : prompt, camera);
  items.drawUi(camera);
  map.draw();
  book.drawCursor();
  canvas.style.cursor = book.active ? 'none' : '';
}

function updateHud() {
  const f = pipe.flags;
  const on = (b: boolean) => (b ? '开' : '关');
  const p = player.feet;
  hud.textContent =
    `NEXUS · ${world}   ${fps.toFixed(0)} fps   ${pipe.size.w}×${pipe.size.h}${pipe.worldShift ? ` · 世界 1/${1 << pipe.worldShift}` : ''}   ` +
    `脚底 ${p.x.toFixed(2)}, ${p.y.toFixed(2)}, ${p.z.toFixed(2)}  朝向 ${((player.yaw / deg) % 360).toFixed(0)}°${player.fly ? '  飞行' : ''}\n` +
    `点击画面锁定视角 · WASD / 滚轮 行走 · Space 跳 · Shift 快走 · E 互动 · Q 按住捏手里的 · F 按住看看身上的 · Tab 日记 · Esc 释放 · Shift+R 回到到达处\n` +
    `1 原始 ${on(f.raw)} · 2 场 ${on(f.field)} · 3 色板 ${on(f.palette)} · 4 描边 ${['关', '格', '细线'][f.outline]} · 5 锁级 ${f.lock < 0 ? '自动' : f.lock} · 6 三色 ${shared.uAutoRamp.value} · G 飞行 · H 隐藏 · K 天：${skyLabel(level.sky.name)}`;
}

let acc = 0;
let n = 0;
renderer.setAnimationLoop(() => {
  const dt = Math.min(clock.getDelta(), 0.05);
  frame(dt);
  acc += dt;
  n++;
  if (acc > 0.25) {
    fps = n / acc;
    acc = 0;
    n = 0;
    updateHud();
  }
});
updateHud();

(window as unknown as { __nexus: unknown }).__nexus = {
  /** 脚底坐标 */
  set(x: number, y: number, z: number, yawDeg: number, pitchDeg = 0) {
    player.feet.set(x, y, z);
    player.vel.set(0, 0, 0);
    player.yaw = yawDeg * deg;
    player.pitch = pitchDeg * deg;
    armedFrom = player.feet.clone();
  },
  flags: pipe.flags,
  /** 渲染计数：上一帧一共画了几次、多少三角形（影子、像素化、窗都算在内） */
  info: () => ({ ...renderer.info.render }),
  /** 影子的计数：重画次数、动着的投影物 */
  shadow: shadow.stats,
  sky: (name: string) => level.sky.set(name),
  /** 窗里的天（测试用，如 overnight:3 错开时刻） */
  windowSky: (spec: string) => level.windowSky?.set(spec),
  poses: () => [...level.poses.values()].map((g) => ({ name: g.name, on: g.on, k: g.k })),
  /** 拨一个能开关的东西（测试用：开门、关门） */
  pose(name: string, on: boolean) {
    const g = level.poses.get(name);
    if (g) g.target = on ? 1 : 0;
    return !!g;
  },
  /** 昼夜：不给参数就读（0 白天 … 1 夜里）；给 true / false 就像拨了开关（测试用） */
  night(on?: boolean) {
    const g = [...level.poses.values()].find((p) => p.night);
    if (g && on !== undefined) g.target = on ? 1 : 0;
    return level.night;
  },
  /** 窗景（测试用：可以往里临时加一处，试换景） */
  outlooks: () => level.outlooks,
  gaze: () => gaze && { phase: gaze.phase, swap: !!gaze.swap, outlook: level.outlook },
  player,
  /** 开场：现在在哪一步（title / play / done）；wake() 等于点了一下 */
  intro: () => intro?.phase ?? 'done',
  wake: wakeIntro,
  /** 入梦、醒来各段的秒数，可以现调 */
  sleep: SLEEP,
  freeze(b: boolean) {
    frozen = b;
  },
  /** 会转的太阳（atmosphere 的 nx_sun_turn）：拨到第几秒；不给参数就读 */
  sunTime(sec?: number) {
    if (sec !== undefined) level.sunTime = sec;
    return level.sunTime;
  },
  /** 直接去一个世界（测试用） */
  go: (to: string, at = '') => go(to, at),
  state: () => ({
    feet: player.feet.toArray(),
    grounded: player.grounded,
    resolve,
    entering: !!entering,
    world,
    /** 缝那边接着的世界 */
    beyond: beyond?.name ?? '',
    travelling: !!travel,
    travelKind: travel?.kind,
    travelPhase: travel?.phase,
    dissolve,
    portals: level.portals.map((p) => ({ to: p.to, at: p.at, mode: p.mode, title: p.title, pos: p.pos.toArray() })),
    arrivals: [...level.arrivals.keys()],
    fall: level.fall,
    /** 到达点：名字 → [x, y, z, 朝向°] */
    arrivalAt: Object.fromEntries([...level.arrivals].map(([k, v]) => [k, [...v.pos.toArray(), v.yaw / deg]])),
    entrances: level.entrances.map((e) => e.url).filter(Boolean),
    /** 晶体（有站点的）：网址与中心位置 */
    sitesHere: level.entrances.filter((e) => e.url).map((e) => ({ url: e.url, title: e.title, pos: e.crystal.mesh.position.toArray() })),
    visited: visited(),
  }),
  /** 日记本（测试用） */
  diary: book,
  /** 物品系统；placeItem 在当前世界临时摆一件（脚底坐标系，位置是物品浮着的地方） */
  items,
  placeItem: (id: string, x: number, y: number, z: number, mode: 'pick' | 'reach' | 'custom' = 'pick', radius = 1.2) =>
    items.place({ item: id, mode, radius, pos: new THREE.Vector3(x, y, z) }),
  keys: (code: string, down: boolean) => dispatchEvent(new KeyboardEvent(down ? 'keydown' : 'keyup', { code })),
};
