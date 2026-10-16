/* 断梯（stair-var-1 / stair-var-2）的断口自动测试：18 个断口逐个用真实按键跳一遍。
   先 npx vite build --outDir dist-stair-var，再
     DIST=dist-stair-var node scripts/walk-stair.cjs stair-var-1
     DIST=dist-stair-var node scripts/walk-stair.cjs stair-var-2
   （不给 DIST 就用 dist；世界不给默认 stair-var-1。两个变体的路线一样，断口表共用。）

   做法：构建场景时脚本会打印 [nx] jump x,y,z,yaw,距离,高差（Blender 坐标：起跳处脚底、朝向、断口
   有多远、对面高多少），表就抄在下面。每个断口：
     1. 站到起跳处往后 1.5m、高 1m（掉下来落在起跳那一级上）；
     2. 按住 KeyW（断口 > 2m 的加 Shift 快走），走到离边 0.15m 时按 Space 起跳（Space 一直按住，
        这个引擎里松开早会收短上升段）；
     3. 飞过断口、并且按住够久了才松 W（免得冲过头撞在对面的踏步上）；
     4. 落稳后读 window.__nexus.state()：脚底还在（grounded）、高度对上对面那一级、水平已经过了断口。
   一个断口最多试几种走法（慢走 / 快走 × 松手早晚），有一种落对了就算过。

   环境变量 DIST 换成别的构建目录（几个人同时构建时各用各的）。临时静态服务器 + 本机 Chrome +
   puppeteer-core（%TEMP%/node_modules），同 walk.cjs。 */
const path = require('path');
const fs = require('fs');
const http = require('http');
const os = require('os');
const puppeteer = require(path.join(os.tmpdir(), 'node_modules', 'puppeteer-core'));

const ROOT = path.resolve(__dirname, '..', process.env.DIST || 'dist');
const WORLD = process.argv[2] || 'stair-var-1';
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.glb': 'model/gltf-binary' };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* [nx] jump 打印出来的 18 个断口：x, y, z（起跳处脚底，Blender）、朝向、距离、高差 */
const JUMPS = [
  [-0.45, -7.00, 2.70, -90, 1.70, 0.00],   // 第一圈：纸上头一个平跳
  [8.15, 1.40, 4.50, 0, 1.00, 0.50],       // 第一圈：三块浮着的碎段
  [8.15, 3.90, 5.00, 0, 1.00, 0.50],
  [8.15, 6.40, 5.50, 0, 1.00, 0.50],
  [8.15, 8.90, 6.00, 0, 0.80, 0.40],
  [-0.45, 11.70, 8.80, 90, 1.50, 0.00],    // 第一圈：倒挂那一跑之后
  [-6.65, 7.45, 12.10, 180, 1.00, 0.45],   // 第二圈：四块浮着的碎段
  [-6.65, 4.85, 12.55, 180, 1.00, 0.45],
  [-6.65, 2.25, 13.00, 180, 1.00, 0.45],
  [-6.65, -0.35, 13.45, 180, 1.00, 0.45],
  [-6.65, -2.95, 13.90, 180, 0.80, 0.30],
  [0.05, -5.95, 17.20, 270, 1.90, 0.00],   // 第二圈：长的一跑之后
  [1.05, 10.30, 25.30, 450, 2.40, -0.30],  // 第三圈：中间那处 2.4m 的跳（要 Shift）
  [9.85, 2.40, 21.10, 270, 0.75, 0.25],    // 歇脚平台外侧伸出去那条
  [12.30, 2.40, 21.35, 270, 0.75, 0.25],
  [14.75, 2.40, 21.60, 270, 0.75, 0.25],
  [17.20, 2.40, 21.85, 270, 0.75, 0.25],
  [19.65, 2.40, 22.10, 270, 0.75, 0.10],   // 尽头那块斜板
];

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

  /** 在页面里用 rAF 盯着脚底，等到「过了 target 米」（或「落地了」）就返回——从外面轮询太粗，
      20~100ms 一次，走得快时能差 0.3m，起跳会错过断口边。 */
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

  /** 一个断口试一次：慢走 / 快走，起跳后 W 至少按住 holdMs 毫秒 */
  async function attempt(j, useRun, holdMs) {
    const [x, y, z, yaw, dist, dz] = j;
    const a = (yaw * Math.PI) / 180;
    const fx = -Math.sin(a), fy = Math.cos(a);      // Blender 里断口的方向
    // 断口起点在 three 里是 (x, z, −y)；朝向同 spawn，方向也是 (fx, 0, −fy)
    const prog = (s) => (s.feet[0] - x) * fx - (s.feet[2] + y) * fy;
    await set(x - fx * 1.5, z + 1.0, -(y - fy * 1.5), yaw);
    await sleep(700);
    let s = await state();
    if (!s.grounded) return { ok: false, why: '起跳处没站住', s, prog: NaN, top: z + dz };
    await key('KeyW', true);
    if (useRun) await key('ShiftLeft', true);
    await watch(j, -0.22, 0, false, 1500);          // 走到离边 0.22m 再起跳
    await key('Space', true);
    await watch(j, dist, Math.max(460, holdMs), false, 1300);   // 飞过断口（Space 至少按够这么久）
    await key('KeyW', false);
    if (useRun) await key('ShiftLeft', false);
    await watch(j, 0, 0, true, 1500);               // 等落稳
    await key('Space', false);
    await sleep(250);
    s = await state();
    const p = prog(s);
    const top = z + dz;
    const ok = s.grounded && s.feet[1] >= top - 0.35 && p >= dist * 0.8;
    const why = s.grounded
      ? (s.feet[1] < top - 0.35 ? `掉到 ${s.feet[1].toFixed(2)}（该 ${top.toFixed(2)}）` : `只走了 ${p.toFixed(2)}m`)
      : '没落地';
    return { ok, why, s, prog: p, top };
  }

  let fails = 0;
  for (let i = 0; i < JUMPS.length; i++) {
    const j = JUMPS[i];
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
  console.log(`\n${WORLD}：${JUMPS.length - fails}/${JUMPS.length} 个断口跳过去了`);
  await browser.close();
  srv.close();
  process.exit(fails ? 1 : 0);
});
