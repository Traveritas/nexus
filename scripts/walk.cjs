/* 行走与入口的自动测试：先 npm run build，再 node scripts/walk.cjs
   用真实按键走：迈 0.3m 台阶上平台、跳上 0.9m 的台子、走进入口跳到测试页、后退回来。 */
const path = require('path');
const fs = require('fs');
const http = require('http');
const os = require('os');
const puppeteer = require(path.join(os.tmpdir(), 'node_modules', 'puppeteer-core'));

const ROOT = path.join(__dirname, '..', 'dist');
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.glb': 'model/gltf-binary' };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const srv = http.createServer((req, res) => {
  let f = path.join(ROOT, decodeURIComponent((req.url || '/').split('?')[0]));
  if (fs.existsSync(f) && fs.statSync(f).isDirectory()) f = path.join(f, 'index.html');
  if (!fs.existsSync(f)) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { 'content-type': TYPES[path.extname(f)] || 'application/octet-stream' });
  fs.createReadStream(f).pipe(res);
});

srv.listen(0, '127.0.0.1', async () => {
  const base = `http://127.0.0.1:${srv.address().port}/`;
  const browser = await puppeteer.launch({
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless: 'new',
    args: ['--use-angle=d3d11', '--enable-gpu', '--ignore-gpu-blocklist'],
  });
  const page = await browser.newPage();
  page.on('pageerror', (e) => console.log('[pageerror]', e.message));
  page.on('console', (m) => { if (m.type() === 'error') console.log('[page]', m.text()); });
  await page.setViewport({ width: 960, height: 540 });
  const ready = async () => { await page.waitForFunction(() => window.__nexus); await sleep(400); };
  const state = () => page.evaluate(() => window.__nexus.state());
  const set = (x, y, z, yaw) => page.evaluate((a) => window.__nexus.set(...a), [x, y, z, yaw, 0]);
  const hold = async (key, ms) => { await page.keyboard.down(key); await sleep(ms); await page.keyboard.up(key); };
  let fails = 0;
  const check = (name, ok, info) => { console.log(`${ok ? 'ok  ' : 'FAIL'} ${name}  ${info}`); if (!ok) fails++; };

  await page.goto(base, { waitUntil: 'load' });
  await ready();
  await sleep(800);
  let s = await state();
  check('出生点落地', s.grounded && Math.abs(s.feet[1]) < 0.05, JSON.stringify(s.feet.map((v) => +v.toFixed(2))));

  // 迈台阶：0.3m 一级，五级上到 1.5m 平台
  await set(-15.66, 0, -8.17, -12);
  await sleep(300);
  await hold('KeyW', 2300);
  await sleep(500);
  s = await state();
  check('走上 0.3m 台阶到平台', Math.abs(s.feet[1] - 1.5) < 0.08, `脚底 ${s.feet.map((v) => v.toFixed(2))}`);

  // 0.5m 的台阶不能直接迈上去
  await set(11.5 - 0.0, 0, -3.5, 20);
  await sleep(300);
  s = await state();
  const y0 = s.feet[1];
  await hold('KeyW', 1500);
  s = await state();
  check('0.5m 坎迈不上去', s.feet[1] - y0 < 0.4, `脚底 ${s.feet.map((v) => v.toFixed(2))}`);

  // 跳上 0.9m 的台子：记下这段时间里到过的最高处
  await set(11.6, 0, 4, -90);
  await sleep(300);
  const peak = page.evaluate(async () => {
    let m = 0;
    const t0 = performance.now();
    while (performance.now() - t0 < 1600) {
      m = Math.max(m, window.__nexus.state().grounded ? window.__nexus.state().feet[1] : 0);
      await new Promise((r) => requestAnimationFrame(r));
    }
    return m;
  });
  await page.keyboard.down('KeyW');
  await sleep(200);
  await page.keyboard.down('Space');
  await sleep(250);
  await page.keyboard.up('Space');
  await sleep(250);
  await page.keyboard.up('KeyW');
  const top = await peak;
  check('跳上 0.9m 台子并站住', top > 0.85, `站过的最高处 y=${top.toFixed(2)}`);

  // 走进入口 A → 测试页 → 后退回来
  await set(0, 0, -1.2, 0);
  await sleep(300);
  page.keyboard.down('KeyW');
  await page.waitForNavigation({ timeout: 8000 }).catch(() => null);
  const url1 = page.url();
  if (!url1.endsWith('/test-exit.html')) console.log('    状态', JSON.stringify(await state()));
  check('走进晶体跳到站点', url1.endsWith('/test-exit.html'), url1);
  await page.keyboard.up('KeyW').catch(() => {});
  await page.goBack({ waitUntil: 'load' });
  await ready();
  await sleep(500);
  s = await state();
  check('后退回到入口前', !s.entering && s.feet[2] > -4.5 && s.feet[2] < 0 && s.resolve < 0.5,
    `脚底 ${s.feet.map((v) => v.toFixed(2))} resolve=${s.resolve.toFixed(2)}`);

  await browser.close();
  srv.close();
  process.exit(fails ? 1 : 0);
});
