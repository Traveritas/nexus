import * as THREE from 'three';
import { Pipeline, MAX_FIELD, type Field, type FieldSource } from './pipeline';
import { SunShadow } from './shadow';
import { loadLevel, type Entrance, type Level, type Outlook, type Pose, type Portal } from './level';
import { Player } from './player';
import { SKY_NAMES, skyLabel } from './skybox';
import { shared } from './materials';
import { Ui, UI_SCALE, loadUiFont } from './ui';
import { PromptTag } from './prompt';
import { Diary, night, type Settings } from './diary';
import { ItemSystem, type Promptable } from './items/system';
import { MapView } from './mapview';
import { SiteCard } from './sitecard';
import { dreamt, edges, recordEdge, recordSite, sites } from './worlds';
import { IntroPlayer, introSeen, stripIntro } from './intro';

/* 世界：?world=名字（public/scenes/<名字>.glb，默认 wake_fragment——现实的家，醒着的那一间）；?scene= 是旧写法，同义
   世界之间靠传送物（nx_type=portal）来往：走进去，或走近按 E。转场时格子一路变粗、蒙上雾色，新世界再一格格解析出来。
   晶体（入口）通往真实的站点：走进去，整屏解析到底、化白。
   开场：第一次从根地址进来时停在标题的机位上，「点击醒来」以后木条掉进虚空、视角滑到床边（src/intro.ts）；?intro=1 强制再放一次，?intro=0 不放
   查询串：?pos=x,y,z（脚底）&yaw=度&pitch=度  ?freeze=1  ?hud=0  ?res=auto|full|half|quarter|eighth|sixteenth 世界的渲染分辨率  ?sky=主题（覆盖世界里的，见 docs/sky.md）  ?ramp=0..1 自动三色明暗的强度（默认 0.3）
   键：E 互动 · Q 按住捏手里的东西 · F 按住看看身上的 · Tab 日记（醒来在日记里） · 1 原始世界 · 2 解析度场染色 · 3 色板 · 4 描边（关 / 格 / 细线） · 5 锁级 · 6 自动三色明暗强度 · G 飞行 · H 提示 · K 换天
   window.__nexus 供截图、测试脚本用 */

const q = new URLSearchParams(location.search);
if (q.has('ramp')) shared.uAutoRamp.value = THREE.MathUtils.clamp(Number(q.get('ramp')) || 0, 0, 1);
const canvas = document.getElementById('stage') as HTMLCanvasElement;
const hud = document.getElementById('hud')!;
const label = document.getElementById('label')!;
const deg = Math.PI / 180;
const RETURN_KEY = 'nexus:return';
const DEV_KEY = 'nexus:dev';
const VISITED_KEY = 'nexus:visited';
/** 起点：现实的家（残片）。一开始在这里醒来，日记里「醒来」也回到这里，落在床边（到达点 home） */
const START = 'wake_fragment';
const START_AT = 'home';

const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, powerPreference: 'high-performance' });
renderer.setPixelRatio(1);
const camera = new THREE.PerspectiveCamera(68, 16 / 9, 0.1, 400);
camera.rotation.order = 'YXZ';
const pipe = new Pipeline(renderer);
const shadow = new SunShadow();
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
  for (const to of new Set(l.portals.map((p) => p.to))) fetch(sceneUrl(to)).catch(() => {});
}
prefetchNeighbours(level);
items.attach(level, world);

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
    ? new IntroPlayer(level.intro, document.getElementById('intro')!)
    : null;
if (!intro) stripIntro(level.intro);
const introView = { pos: new THREE.Vector3(), yaw: 0, pitch: 0 };
/** 点击醒来：终点是现在人站的地方（出生点）的眼睛 */
function wakeIntro() {
  if (intro?.phase !== 'title') return;
  const pos = new THREE.Vector3();
  player.eyePosition(pos);
  intro.wake({ pos, yaw: player.yaw, pitch: player.pitch });
  introEnd = { yaw: player.yaw, pitch: player.pitch };
}
let introEnd = { yaw: 0, pitch: 0 };
if (q.get('hud') === '0') hud.classList.add('off');

// ── 世界之间的转场 ──
interface Travel {
  phase: 'out' | 'in';
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
}
let travel: Travel | null = null;
let dissolve = 0;
const OUT = 0.75;
const IN = 1.0;
const veilCol = new THREE.Color();
const fogSrgb = () => shared.uFogCol.value.clone().convertLinearToSRGB();

function go(to: string, at = '', push = true, via = false) {
  if (travel || entering || !to) return;
  const next = loadLevel(sceneUrl(to)).catch((err) => {
    console.warn('[nexus] 去不了', to, err);
    return null;
  });
  const tr: Travel = { phase: 'out', t: 0, to, at, push, next, ready: undefined, veilFrom: fogSrgb(), veilTo: fogSrgb(), from: world, via };
  map.closeNow();
  travel = tr;
  player.vel.set(0, 0, 0);
  next.then((l) => {
    tr.ready = l;
    // 加载新世界会改共享的天色与太阳；转场还没走完，先还给当前的世界
    level.apply();
  });
}

function stepTravel(dt: number) {
  if (!travel) return;
  travel.t += dt;
  if (travel.phase === 'out') {
    dissolve = Math.min(1, travel.t / OUT);
    veilCol.copy(travel.veilFrom);
    if (dissolve < 1 || travel.ready === undefined) return;
    const l = travel.ready;
    if (!l) {
      // 没去成：原路解析回来
      travel.phase = 'in';
      travel.t = 0;
      return;
    }
    disposeLevel(level);
    level = l;
    stripIntro(level.intro);
    // 开场还没放完就走了（只有测试会这样）：收起来，别把人锁在新世界里
    intro?.cancel();
    intro = null;
    level.apply();
    world = travel.to;
    player.setCollider(level.collider);
    lastArrival = travel.at;
    arriveAt(travel.at);
    markVisited(world);
    if (travel.via) recordEdge(travel.from, world);
    noteSites();
    items.attach(level, world);
    prefetchNeighbours(level);
    if (travel.push) history.pushState({ world, at: travel.at }, '', `?world=${encodeURIComponent(world)}`);
    travel.veilTo = fogSrgb();
    travel.phase = 'in';
    travel.t = 0;
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
  wake: () => go(START, START_AT),
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
  // 按住 Q：把手里的东西举到眼前、捏紧；松开放下（醒来在日记的目录里）
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

/** 眼前的窗景或按键型的 pose（来回切换的东西）；按 E 就推开 / 切换 */
function checkWindow(limit: number): { p: Promptable; d: number } | null {
  if (travel || entering || gaze) return null;
  camera.getWorldDirection(look);
  let best: { p: Promptable; d: number; act: () => void } | null = null;
  const consider = (pos: THREE.Vector3, radius: number, p: () => Promptable, act: () => void) => {
    const d = eye.distanceTo(pos);
    if (d > radius + 1.2 || d >= (best?.d ?? limit)) return;
    tmp.copy(pos).sub(eye).normalize();
    if (tmp.dot(look) < 0.55 && d > radius) return;
    best = { p: p(), d, act };
  };
  const ol = level.outlooks[level.outlook];
  if (ol) consider(ol.pos, ol.radius, () => tagOf(ol, '推开窗'), openWindow);
  for (const g of level.poses.values()) {
    if (g.on !== 'key') continue;
    consider(g.pos, g.radius, () => tagOf(g, g.title), () => (g.target = g.target > 0.5 ? 0 : 1));
  }
  const b = best as { p: Promptable; d: number; act: () => void } | null;
  if (b && interact) {
    tag.press();
    b.act();
  }
  return b;
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

/** 走进型的直接走；按键型的返回眼前那一个（用来显示提示） */
function checkPortals(limit = Infinity): Portal | null {
  if (travel || entering) return null;
  body.copy(player.feet);
  body.y += 0.9;
  const inside = (p: Portal, margin = 0) =>
    Math.hypot(body.x - p.pos.x, body.z - p.pos.z) < p.radius + margin && Math.abs(body.y - p.pos.y) < 1.3;
  // 刚到 / 刚被放下时若正站在某个走进型的传送物里，要先走出来（留 0.3m 余量）才上膛
  if (armedFrom && !level.portals.some((p) => p.mode === 'walk' && inside(p, 0.3))) armedFrom = null;
  camera.getWorldDirection(look);
  let prompt: Portal | null = null;
  // limit：眼前有一件更近的物品可以拾起时，比它远的传送物不出纸签
  let best = limit;
  for (const p of level.portals) {
    if (p.mode === 'walk') {
      if (armedFrom) continue;
      if (inside(p)) {
        go(p.to, p.at, true, true);
        return null;
      }
    } else {
      const d = eye.distanceTo(p.pos);
      if (d > p.radius + 1.8) continue;
      tmp.copy(p.pos).sub(eye).normalize();
      if (tmp.dot(look) < 0.55 && d > p.radius) continue;
      if (d < best) {
        best = d;
        prompt = p;
      }
    }
  }
  if (prompt && interact) {
    tag.press();
    go(prompt.to, prompt.at, true, true);
    prompt = null;
  }
  return prompt;
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

  // 晶体的名字连着真实的站点，不走像素 UI，保持全分辨率；有纸签时让开
  label.textContent = nearest?.title ?? '';
  label.style.opacity = String(nearest && !prompt ? (1 - THREE.MathUtils.smoothstep(nearestD, 4, 9)) * (1 - resolve) * (1 - dissolve) : 0);

  return { sources: sources.slice(0, MAX_FIELD), prox, resolve, dissolve, veilCol };
}

// ── 主循环 ──
const clock = new THREE.Clock();
let t = 0;
let fps = 0;

function frame(dt: number) {
  if (!frozen) t += dt;
  stepTravel(dt);
  player.update(dt, !!entering || !!gaze || !!travel || book.active || items.locked || !!intro);
  if (player.feet.y < -40) respawn();
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
  camera.updateMatrixWorld();
  stepGaze(dt);

  items.update(dt, { world, feet: player.feet, t }, camera);
  // 纸签：眼前可以拾起的物品与按键型传送物，谁近挂谁
  camera.getWorldDirection(look);
  const itemP = travel || entering || book.active || intro ? null : items.promptAt(eye, look);
  // 窗先看：它按了 E 就把 E 用掉，后面的传送物、物品不再响应
  const winP = travel || entering || book.active || intro ? null : checkWindow(itemP?.d ?? Infinity);
  if (winP && interact) interact = false;
  let prompt: Promptable | null = checkPortals(winP?.d ?? itemP?.d ?? Infinity);
  if (!prompt && winP) prompt = winP.p;
  if (!prompt && itemP && !winP) {
    prompt = itemP.p;
    if (interact) {
      tag.press();
      items.pick(itemP.p, camera);
    }
  }
  interact = false;
  level.update(dt, t, camera, frozen);
  for (const e of level.entrances) e.crystal.update(camera, pipe.pixTexture);
  const field = fieldOf(prompt);
  // 窗景的站名：和晶体的名字一样是全分辨率的字，走近窗时浮出来，和纸签同时在
  const ol = level.outlooks[level.outlook];
  if (ol?.title && !level.entrances.length) {
    const d = eye.distanceTo(ol.pos);
    label.textContent = ol.title;
    label.style.opacity = String((1 - THREE.MathUtils.smoothstep(d, 2.2, 4.2)) * (1 - resolve) * (1 - dissolve) * (gaze ? 0 : 1));
  }
  field.sources = [...items.sources(camera), ...field.sources].slice(0, MAX_FIELD);
  shadow.render(renderer, level.scene, player.feet);
  book.update(dt);
  field.drowse = Math.max(book.drowse, items.drowse);
  map.update(dt);
  field.dim = map.dim(items.handScreen(camera, pipe.size.w, pipe.size.h), pipe.size.w, pipe.size.h);
  field.glow = map.layout(camera, { level, world, visited: dreamt(visited()), edges: edges(), sites: sites() }, book.active || items.ringActive || !!travel);
  // 现实的世界是干净低模，不做像素化（只有转场时变粗）
  pipe.setClean(level.style === 'clean');
  // 开场：标题是梦的画面，滑向床边时醒过来
  pipe.setDream(intro?.dream ?? 0);
  pipe.render(level.scene, level.crystalScene, camera, field, items.hand);
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
  /** 影子的计数：重画次数、动着的投影物 */
  shadow: shadow.stats,
  sky: (name: string) => level.sky.set(name),
  /** 窗里的天（测试用，如 overnight:3 错开时刻） */
  windowSky: (spec: string) => level.windowSky?.set(spec),
  poses: () => [...level.poses.values()].map((g) => ({ name: g.name, on: g.on, k: g.k })),
  /** 窗景（测试用：可以往里临时加一处，试换景） */
  outlooks: () => level.outlooks,
  gaze: () => gaze && { phase: gaze.phase, swap: !!gaze.swap, outlook: level.outlook },
  player,
  /** 开场：现在在哪一步（title / play / done）；wake() 等于点了一下 */
  intro: () => intro?.phase ?? 'done',
  wake: wakeIntro,
  freeze(b: boolean) {
    frozen = b;
  },
  /** 直接去一个世界（测试用） */
  go: (to: string, at = '') => go(to, at),
  state: () => ({
    feet: player.feet.toArray(),
    grounded: player.grounded,
    resolve,
    entering: !!entering,
    world,
    travelling: !!travel,
    dissolve,
    portals: level.portals.map((p) => ({ to: p.to, at: p.at, mode: p.mode, title: p.title, pos: p.pos.toArray() })),
    arrivals: [...level.arrivals.keys()],
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
