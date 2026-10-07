import * as THREE from 'three';
import { Pipeline, MAX_FIELD, type Field, type FieldSource } from './pipeline';
import { SunShadow } from './shadow';
import { loadLevel, type Entrance } from './level';
import { Player } from './player';
import { SKY_NAMES, skyLabel } from './skybox';

/* 查询串：?scene=名字（public/scenes/<名字>.glb，默认 slice）
          ?pos=x,y,z（脚底）&yaw=度&pitch=度  ?freeze=1  ?hud=0  ?sky=主题（覆盖场景里的，见 docs/sky.md）
   键：1 原始世界 · 2 解析度场染色 · 3 色板 · 4 描边 · 5 锁级 · G 飞行 · H 提示 · K 换天
   window.__nexus 供截图脚本用 */

const q = new URLSearchParams(location.search);
const canvas = document.getElementById('stage') as HTMLCanvasElement;
const hud = document.getElementById('hud')!;
const label = document.getElementById('label')!;
const deg = Math.PI / 180;
const RETURN_KEY = 'nexus:return';
const DEV_KEY = 'nexus:dev';

const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, powerPreference: 'high-performance' });
renderer.setPixelRatio(1);
const camera = new THREE.PerspectiveCamera(68, 16 / 9, 0.1, 400);
camera.rotation.order = 'YXZ';
const pipe = new Pipeline(renderer);
const shadow = new SunShadow();

function resize() {
  const w = Math.max(8, Math.floor(innerWidth / 8) * 8);
  const h = Math.max(8, Math.floor(innerHeight / 8) * 8);
  renderer.setSize(w, h, false);
  canvas.style.width = `${w}px`;
  canvas.style.height = `${h}px`;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  pipe.setSize(w, h);
}
resize();
addEventListener('resize', resize);

const level = await loadLevel(`${import.meta.env.BASE_URL}scenes/${q.get('scene') ?? 'slice'}.glb`);
const player = new Player(level.collider);
if (q.get('sky')) level.sky.set(q.get('sky')!);

function respawn() {
  player.feet.copy(level.spawn.pos);
  player.vel.set(0, 0, 0);
  player.yaw = level.spawn.yaw;
  player.pitch = -0.04;
}
respawn();

interface Saved { x: number; y: number; z: number; yaw: number; pitch: number }
function restore(key: string) {
  try {
    const raw = sessionStorage.getItem(key);
    if (!raw) return false;
    sessionStorage.removeItem(key);
    const s = JSON.parse(raw) as Saved;
    player.feet.set(s.x, s.y, s.z);
    player.vel.set(0, 0, 0);
    player.yaw = s.yaw;
    player.pitch = s.pitch;
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
}
if (q.get('yaw')) player.yaw = Number(q.get('yaw')) * deg;
if (q.get('pitch')) player.pitch = Number(q.get('pitch')) * deg;
if (import.meta.env.DEV) {
  addEventListener('beforeunload', () => {
    if (!entering) save(DEV_KEY, { ...player.feet, yaw: player.yaw, pitch: player.pitch });
  });
}

let frozen = q.get('freeze') === '1';
if (q.get('hud') === '0') hud.classList.add('off');

addEventListener('keydown', (e) => {
  const f = pipe.flags;
  if (e.code === 'Digit1') f.raw = !f.raw;
  if (e.code === 'Digit2') f.field = !f.field;
  if (e.code === 'Digit3') f.palette = !f.palette;
  if (e.code === 'Digit4') f.outline = !f.outline;
  if (e.code === 'Digit5') f.lock = f.lock >= 2 ? -1 : f.lock + 1;
  if (e.code === 'KeyH') hud.classList.toggle('off');
  if (e.code === 'KeyK') level.sky.set(SKY_NAMES[(SKY_NAMES.indexOf(level.sky.name) + 1) % SKY_NAMES.length]);
  if (e.code === 'KeyR' && e.shiftKey) respawn();
  if (e.code === 'Space' && document.pointerLockElement === canvas) e.preventDefault();
});

let dragging = false;
canvas.addEventListener('mousedown', () => {
  dragging = true;
  canvas.requestPointerLock?.();
});
addEventListener('mouseup', () => (dragging = false));
addEventListener('mousemove', (e) => {
  if (document.pointerLockElement === canvas || dragging) player.look(e.movementX, e.movementY);
});
addEventListener('wheel', (e) => player.nudge(-e.deltaY * 0.012), { passive: true });

// ── 入口 ──
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
  });
  setTimeout(() => location.assign(e.url), 160);
}

// ── 解析度场 ──
const tmp = new THREE.Vector3();
const edge = new THREE.Vector3();
const right = new THREE.Vector3();
const eye = new THREE.Vector3();

function fieldOf(): Field {
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
  if (nearest && nearest.url) {
    const r = nearest.crystal.radius;
    target = 1 - THREE.MathUtils.smoothstep(nearestD, r * 0.9, r * 7);
    if (!entering && nearestD < r * 0.9) enter(nearest);
  }
  resolve = entering ? Math.min(1, resolve + 0.12) : target;

  label.textContent = nearest?.title ?? '';
  label.style.opacity = String(nearest ? (1 - THREE.MathUtils.smoothstep(nearestD, 4, 9)) * (1 - resolve) : 0);

  return { sources: sources.slice(0, MAX_FIELD), prox, resolve };
}

// ── 主循环 ──
const clock = new THREE.Clock();
let t = 0;
let fps = 0;

function frame(dt: number) {
  if (!frozen) t += dt;
  player.update(dt, !!entering);
  if (player.feet.y < -40) respawn();
  player.eyePosition(eye);
  camera.position.copy(eye);
  camera.rotation.set(player.pitch, player.yaw, 0);
  camera.updateMatrixWorld();

  level.update(dt, t, camera, frozen);
  for (const e of level.entrances) e.crystal.update(camera, pipe.pixTexture);
  const field = fieldOf();
  shadow.render(renderer, level.scene, player.feet);
  pipe.render(level.scene, level.crystalScene, camera, field);
}

function updateHud() {
  const f = pipe.flags;
  const on = (b: boolean) => (b ? '开' : '关');
  const p = player.feet;
  hud.textContent =
    `NEXUS   ${fps.toFixed(0)} fps   ${pipe.size.w}×${pipe.size.h}   ` +
    `脚底 ${p.x.toFixed(2)}, ${p.y.toFixed(2)}, ${p.z.toFixed(2)}  朝向 ${((player.yaw / deg) % 360).toFixed(0)}°${player.fly ? '  飞行' : ''}\n` +
    `点击画面锁定视角 · WASD / 滚轮 行走 · Space 跳 · Shift 快走 · Esc 释放 · Shift+R 回出生点\n` +
    `1 原始 ${on(f.raw)} · 2 场 ${on(f.field)} · 3 色板 ${on(f.palette)} · 4 描边 ${on(f.outline)} · 5 锁级 ${f.lock < 0 ? '自动' : f.lock} · G 飞行 · H 隐藏 · K 天：${skyLabel(level.sky.name)}`;
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
  },
  flags: pipe.flags,
  sky: (name: string) => level.sky.set(name),
  player,
  freeze(b: boolean) {
    frozen = b;
  },
  state: () => ({ feet: player.feet.toArray(), grounded: player.grounded, resolve, entering: !!entering }),
  keys: (code: string, down: boolean) => dispatchEvent(new KeyboardEvent(down ? 'keydown' : 'keyup', { code })),
};
