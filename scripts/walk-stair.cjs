/* 断梯（stair / stair_b）的断口自动测试：每个断口逐个用真实按键跳一遍，再走一遍缝、掉一次家。
   先 npx vite build --outDir dist-stair，再
     DIST=dist-stair node scripts/walk-stair.cjs stair
     DIST=dist-stair node scripts/walk-stair.cjs stair_b

   断口表抄的是场景脚本 build 时打印的 [nx] jump x,y,z,yaw,距离,高差（Blender 坐标：起跳处脚底、朝向、
   断口多远、对面高多少）。世界换路线时把表重抄一遍。

   环境变量 DIST 换成别的构建目录。临时静态服务器 + 本机 Chrome + puppeteer-core（%TEMP%/node_modules）。 */
const path = require('path');
const fs = require('fs');
const http = require('http');
const os = require('os');
const puppeteer = require(path.join(os.tmpdir(), 'node_modules', 'puppeteer-core'));

const ROOT = path.resolve(__dirname, '..', process.env.DIST || 'dist');
const WORLD = process.argv[2] || 'stair';
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.glb': 'model/gltf-binary' };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* [nx] jump 打印出来的断口：x, y, z（起跳处脚底，Blender）、朝向、距离、高差 */
const JUMPS = {
  stair: [
    [5.60, 0.00, 3.30, 0.04, 1.59, 0.60],
    [-1.59, 5.37, 7.20, 106.44, 1.59, 0.60],
    [-5.60, -0.01, 9.90, 180.11, 1.59, 0.60],
  ],
  stair_b: [
    [3.04, -5.03, 13.80, 301.13, 1.60, 0.60],
    [5.25, 3.49, 17.88, 393.59, 1.70, 0.84],
    [-10.19, -3.77, 29.30, 457.53, 0.80, 0.30],
    [-12.87, -4.12, 29.60, 457.53, 0.80, 0.30],
    [-15.55, -4.48, 29.90, 457.53, 0.80, 0.30],
    [-18.22, -4.83, 30.20, 457.53, 0.80, 0.30],
    [-20.90, -5.18, 30.20, 457.53, 0.80, 0.10],
    [-6.32, -5.58, 29.30, 547.53, 0.50, 0.82],
    [-5.97, -8.25, 30.12, 547.53, 0.50, 0.82],
    [-5.62, -10.93, 30.94, 547.53, 0.50, 0.82],
    [-5.26, -13.61, 31.76, 547.53, 0.50, 0.82],
    [-4.91, -16.28, 32.58, 547.53, 0.50, 0.82],
    [-4.55, -18.96, 33.40, 547.53, 0.50, 0.82],
  ],
};
/* 门的底边中点与朝向（build 打印的 mark door） */
const DOOR = { stair: [-3.64, -4.19, 11.40, -131], stair_b: [-3.64, -4.19, 11.40, 49] };

const srv = http.createServer((req, res) => {
  let f = path.join(ROOT, decodeURIComponent((req.url || '/').split('?')[0]));
  if (fs.existsSync(f) && fs.statSync(f).isDirectory()) f = path.join(f, 'index.html');
  if (!fs.existsSync(f)) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { 'content-type': TYPES[path.extname(f)] || 'application/octet-stream' });
  fs.createReadStream(f).pipe(res);
});

srv.listen(0, '127.0.0.1', async () => {
  const base = `http://127.0.0.1:${srv.address().port}/?world=${WORLD}&intro=0&hud=0`;
  const browser = await puppeteer.launch({
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless: 'new',
    args: ['--use-angle=d3d11', '--enable-gpu', '--ignore-gpu-blocklist'],
  });
  const page = await browser.newPage();
  page.on('pageerror', (e) => console.log('[pageerror]', e.message));
  await page.setViewport({ width: 960, height: 540 });
  await page.goto(base, { waitUntil: 'load' });
  await page.waitForFunction((w) => window.__nexus && window.__nexus.state().world === w, {}, WORLD);
  await sleep(800);

  const state = () => page.evaluate(() => window.__nexus.state());
  const set = (x, y, z, yaw) => page.evaluate((a) => window.__nexus.set(...a), [x, y, z, yaw, 0]);
  const key = (k, down) => (down ? page.keyboard.down(k) : page.keyboard.up(k));

  const watch = (j, target, minMs, grounded, timeout) => page.evaluate(async ([x, y, yaw, target, minMs, grounded, timeout]) => {
    const N = window.__nexus;
    const a = (yaw * Math.PI) / 180;
    const fx = -Math.sin(a), fy = Math.cos(a);
    const prog = () => (N.player.feet.x - x) * fx - (N.player.feet.z + y) * fy;
    const t0 = performance.now();
    for (;;) {
      await new Promise((r) => requestAnimationFrame(r));
      const el = performance.now() - t0;
      if (el > minMs && (grounded ? N.state().grounded : prog() >= target)) return { prog: prog(), el };
      if (el > timeout) return { prog: prog(), el, timeout: true };
    }
  }, [j[0], j[1], j[3], target, minMs, grounded, timeout]);

  async function attempt(j, useRun, holdMs) {
    const [x, y, z, yaw, dist, dz] = j;
    const a = (yaw * Math.PI) / 180;
    const fx = -Math.sin(a), fy = Math.cos(a);
    const prog = (s) => (s.feet[0] - x) * fx - (s.feet[2] + y) * fy;
    await set(x - fx * 1.5, z + 1.0, -(y - fy * 1.5), yaw);
    await sleep(700);
    let s = await state();
    if (!s.grounded) return { ok: false, why: '起跳处没站住', s, prog: NaN };
    await key('KeyW', true);
    if (useRun) await key('ShiftLeft', true);
    await watch(j, -0.22, 0, false, 1500);
    await key('Space', true);
    await watch(j, dist, Math.max(460, holdMs), false, 1300);
    await key('KeyW', false);
    if (useRun) await key('ShiftLeft', false);
    await watch(j, 0, 0, true, 1500);
    await key('Space', false);
    await sleep(250);
    s = await state();
    const p = prog(s);
    const top = z + dz;
    const ok = s.grounded && s.feet[1] >= top - 0.35 && p >= dist * 0.8;
    const why = s.grounded
      ? (s.feet[1] < top - 0.35 ? `掉到 ${s.feet[1].toFixed(2)}（该 ${top.toFixed(2)}）` : `只走了 ${p.toFixed(2)}m`)
      : '没落地';
    return { ok, why, s, prog: p };
  }

  let fails = 0;
  const list = JUMPS[WORLD] || [];
  for (let i = 0; i < list.length; i++) {
    const j = list[i];
    if (process.env.ONLY && !process.env.ONLY.split(',').map(Number).includes(i + 1)) continue;
    const tries = [[false, 0], [true, 0], [false, 400], [true, 500]];
    let best = null;
    for (const [useRun, hold] of tries) {
      const r = await attempt(j, useRun, hold);
      if (!best || (!best.ok && r.ok)) best = { ...r, useRun, hold };
      if (r.ok) break;
    }
    const info = `脚底 ${best.s.feet.map((v) => v.toFixed(2)).join(',')}`
      + `  过了 ${Number.isFinite(best.prog) ? best.prog.toFixed(2) : '—'}m（该 ${j[4]}）`
      + `  ${best.useRun ? '快走' : '慢走'}/W 按住 ${best.hold}ms`;
    console.log(`${best.ok ? 'ok  ' : 'FAIL'} 断口 ${String(i + 1).padStart(2)}  @(${j[0]},${j[1]},${j[2]})  ${info}`
      + (best.ok ? '' : `  ← ${best.why}`));
    if (!best.ok) fails++;
  }
  console.log(`\n${WORLD}：${list.length - fails}/${list.length} 个断口跳过去了`);

  // 走缝：从这一边走到门里，看世界有没有换过去
  if (process.env.SEAM) {
    const [dx, dy, dz, dyaw] = DOOR[WORLD];
    const a = (dyaw * Math.PI) / 180;
    const fx = -Math.sin(a), fy = Math.cos(a);
    await set(dx - fx * 1.6, dz, -(dy - fy * 1.6), dyaw);
    await sleep(700);
    const before = (await state()).world;
    await key('KeyW', true);
    let now = before;
    for (let k = 0; k < 40; k++) {
      await sleep(80);
      now = (await state()).world;
      if (now !== before) break;
    }
    await key('KeyW', false);
    await sleep(300);
    const ok = now !== before;
    console.log(`${ok ? 'ok  ' : 'FAIL'} 走缝：${before} → ${now}（该换到另一边）`);
    if (!ok) fails++;
  }

  // 走上最后一级：从最后一块巨踏步往前走，看是不是到了「高处」（isles）
  if (process.env.TOP) {
    await page.goto(base, { waitUntil: 'load' });   // 前面的项可能把世界换走了，重新进来
    await page.waitForFunction((w) => window.__nexus && window.__nexus.state().world === w, {}, WORLD);
    await sleep(700);
    await set(-4.34, 34.22, 20.65, 548);
    await sleep(700);
    let s = await state();
    console.log(`     最后一级站住：${s.grounded} 脚底 ${s.feet.map((v) => v.toFixed(2)).join(',')}`);
    await key('KeyW', true);
    let now = s.world;
    for (let k = 0; k < 60; k++) {
      await sleep(100);
      now = (await state()).world;
      if (now !== 'stair_b') break;
    }
    await key('KeyW', false);
    const ok = now === 'isles';
    console.log(`${ok ? 'ok  ' : 'FAIL'} 走上最后一级 → ${now}（该 isles）`);
    if (!ok) fails++;
  }

  // 掉下去回家：把脚底放到 −16m，看是不是落到 house
  if (process.env.FALL) {
    await page.goto(base, { waitUntil: 'load' });
    await page.waitForFunction((w) => window.__nexus && window.__nexus.state().world === w, {}, WORLD);
    await sleep(700);
    await page.evaluate(() => { window.__nexus.set(0, -16, 0, 0, 0); });
    await sleep(400);
    let now = (await state()).world;
    for (let k = 0; k < 60; k++) {
      await sleep(100);
      now = (await state()).world;
      if (now === 'house') break;
    }
    const ok = now === 'house';
    console.log(`${ok ? 'ok  ' : 'FAIL'} 掉下去回家：落到 ${now}`);
    if (!ok) fails++;
  }

  await browser.close();
  srv.close();
  process.exit(fails ? 1 : 0);
});
