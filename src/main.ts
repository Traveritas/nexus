import * as THREE from 'three';
import { Pipeline, MAX_FIELD, type Field, type FieldSource } from './pipeline';
import { SunShadow } from './shadow';
import { loadLevel, type Entrance, type Level, type Portal } from './level';
import { Player } from './player';
import { SKY_NAMES, skyLabel } from './skybox';
import { shared } from './materials';
import { Ui, UI_SCALE, loadUiFont } from './ui';
import { PromptTag } from './prompt';
import { Diary, night } from './diary';
import { ItemSystem, type Promptable } from './items/system';
import { MapView } from './mapview';
import { edges, recordEdge, recordSite, sites } from './worlds';

/* 世界：?world=名字（public/scenes/<名字>.glb，默认 home——家）；?scene= 是旧写法，同义
   世界之间靠传送物（nx_type=portal）来往：走进去，或走近按 E。转场时格子一路变粗、蒙上雾色，新世界再一格格解析出来。
   晶体（入口）通往真实的站点：走进去，整屏解析到底、化白。
   查询串：?pos=x,y,z（脚底）&yaw=度&pitch=度  ?freeze=1  ?hud=0  ?sky=主题（覆盖世界里的，见 docs/sky.md）  ?ramp=0..1 自动三色明暗的强度（默认 0.3）
   键：E 互动 · Q 按住捏手里的东西 · F 按住看看身上的 · Tab 日记（醒来在日记里） · 1 原始世界 · 2 解析度场染色 · 3 色板 · 4 描边 · 5 锁级 · 6 自动三色明暗强度 · G 飞行 · H 提示 · K 换天
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
const HOME = 'home';

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
const map = new MapView(ui, document.getElementById('maplabel')!);
items.onBloom = (id) => {
  if (id === 'compass') map.toggle(camera);
};
/** 日记本要等人和世界都有了才建（见「日记」一节）；resize 先于它跑 */
let diary: Diary | undefined;

function resize() {
  const w = Math.max(8, Math.floor(innerWidth / 8) * 8);
  const h = Math.max(8, Math.floor(innerHeight / 8) * 8);
  renderer.setSize(w, h, false);
  canvas.style.width = `${w}px`;
  canvas.style.height = `${h}px`;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  pipe.setSize(w, h);
  ui.setSize(w, h);
  diary?.setSize(ui.w, ui.h);
}
resize();
addEventListener('resize', resize);

// ── 世界 ──
const sceneUrl = (name: string) => `${import.meta.env.BASE_URL}scenes/${name}.glb`;
let world = q.get('world') ?? q.get('scene') ?? HOME;
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
restore(RETURN_KEY) || (import.meta.env.DEV && restore(DEV_KEY));
if (q.get('pos')) {
  const [x, y, z] = q.get('pos')!.split(',').map(Number);
  player.feet.set(x, y, z);
  armedFrom = player.feet.clone();
}
if (q.get('yaw')) player.yaw = Number(q.get('yaw')) * deg;
if (q.get('pitch')) player.pitch = Number(q.get('pitch')) * deg;
if (import.meta.env.DEV) {
  addEventListener('beforeunload', () => {
    if (!entering && !travel) save(DEV_KEY, { ...player.feet, yaw: player.yaw, pitch: player.pitch, world });
  });
}
history.replaceState({ world, at: '' }, '');

let frozen = q.get('freeze') === '1';
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
  wake: () => go(HOME, 'wake'),
  apply: (s) => {
    player.sens = s.sens;
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
  if (e.code === 'Digit4') f.outline = !f.outline;
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
  if (book.active) {
    if (locked) book.move(e.movementX, e.movementY);
    else {
      const r = canvas.getBoundingClientRect();
      book.moveTo((e.clientX - r.left) / UI_SCALE, (e.clientY - r.top) / UI_SCALE);
    }
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
    resolve = 0;
  }
});

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
  resolve = entering ? Math.min(1, resolve + 0.12) : target;

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
  player.update(dt, !!entering || !!travel || book.active || items.locked);
  if (player.feet.y < -40) respawn();
  player.eyePosition(eye);
  camera.position.copy(eye);
  camera.rotation.set(player.pitch, player.yaw, 0);
  camera.updateMatrixWorld();

  items.update(dt, { world, feet: player.feet, t }, camera);
  // 纸签：眼前可以拾起的物品与按键型传送物，谁近挂谁
  camera.getWorldDirection(look);
  const itemP = travel || entering || book.active ? null : items.promptAt(eye, look);
  let prompt: Promptable | null = checkPortals(itemP?.d ?? Infinity);
  if (!prompt && itemP) {
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
  field.sources = [...items.sources(camera), ...field.sources].slice(0, MAX_FIELD);
  shadow.render(renderer, level.scene, player.feet);
  book.update(dt);
  field.drowse = Math.max(book.drowse, items.drowse);
  map.update(dt);
  field.dim = map.dim(items.handScreen(camera, pipe.size.w, pipe.size.h), pipe.size.w, pipe.size.h);
  pipe.render(level.scene, level.crystalScene, camera, field, items.hand);
  book.render(renderer);
  ui.clear();
  tag.update(dt, travel || entering || book.active || items.busy || items.ringActive ? null : prompt, camera);
  items.drawUi(camera);
  map.draw(camera, { level, world, visited: visited(), edges: edges(), sites: sites() }, book.active || items.ringActive || !!travel);
  book.drawCursor();
  canvas.style.cursor = book.active ? 'none' : '';
}

function updateHud() {
  const f = pipe.flags;
  const on = (b: boolean) => (b ? '开' : '关');
  const p = player.feet;
  hud.textContent =
    `NEXUS · ${world}   ${fps.toFixed(0)} fps   ${pipe.size.w}×${pipe.size.h}   ` +
    `脚底 ${p.x.toFixed(2)}, ${p.y.toFixed(2)}, ${p.z.toFixed(2)}  朝向 ${((player.yaw / deg) % 360).toFixed(0)}°${player.fly ? '  飞行' : ''}\n` +
    `点击画面锁定视角 · WASD / 滚轮 行走 · Space 跳 · Shift 快走 · E 互动 · Q 按住捏手里的 · F 按住看看身上的 · Tab 日记 · Esc 释放 · Shift+R 回到到达处\n` +
    `1 原始 ${on(f.raw)} · 2 场 ${on(f.field)} · 3 色板 ${on(f.palette)} · 4 描边 ${on(f.outline)} · 5 锁级 ${f.lock < 0 ? '自动' : f.lock} · 6 三色 ${shared.uAutoRamp.value} · G 飞行 · H 隐藏 · K 天：${skyLabel(level.sky.name)}`;
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
  sky: (name: string) => level.sky.set(name),
  player,
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
