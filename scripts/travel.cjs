/* node scripts/travel.cjs —— 先 npm run build。走一遍所有传送物：每个世界的每个传送物，站到跟前走进去 / 按 E，看是不是到了该去的世界。
   另查：家以外每个世界出入口不超过四个；每个传送物的落脚处跟前就是回去的那个。另测：默认进家、日记里醒来、浏览器后退、转场中途截图。 */
const path = require('path');
const fs = require('fs');
const http = require('http');
const os = require('os');
const puppeteer = require(path.join(os.tmpdir(), 'node_modules', 'puppeteer-core'));

const NEXUS = path.join(__dirname, '..');
const ROOT = path.join(NEXUS, 'dist');
const OUT = path.join(NEXUS, '.shots', 'travel');
fs.mkdirSync(OUT, { recursive: true });
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css' };
// 世界清单：public/scenes 里除了陈列、总图、切片以外的都算
const WORLDS = fs.readdirSync(path.join(NEXUS, 'public', 'scenes')).map((f) => f.replace(/\.glb$/, ''))
  .filter((n) => !/gallery|atlas|slice/.test(n)).sort((a, b) => (a === 'home' ? -1 : b === 'home' ? 1 : a.localeCompare(b)));
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
  page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') console.log('[page]', m.text()); });
  await page.setViewport({ width: 960, height: 540 });
  await page.goto(base + '?hud=0', { waitUntil: 'load' });
  await page.waitForFunction(() => window.__nexus);
  await sleep(600);
  const st = () => page.evaluate(() => window.__nexus.state());
  const key = (code, down) => page.evaluate((c, d) => window.__nexus.keys(c, d), code, down);
  const press = async (code) => { await key(code, true); await sleep(60); await key(code, false); };
  const waitWorld = async (w, ms = 7000) => {
    const t0 = Date.now();
    while (Date.now() - t0 < ms) {
      const s = await st();
      if (s.world === w && !s.travelling) return true;
      await sleep(120);
    }
    return false;
  };
  const goWorld = async (w) => {
    const s = await st();
    if (s.world === w) return true;
    await page.evaluate((x) => window.__nexus.go(x), w);
    return waitWorld(w);
  };
  const results = [];
  const log = (ok, msg) => { results.push(ok); console.log(ok ? 'ok  ' : 'FAIL', msg); };

  // 1. 默认进家
  let s = await st();
  log(s.world === 'home', `默认世界 = ${s.world}`);
  await page.screenshot({ path: path.join(OUT, 't-01-home.png') });

  // 2. 每个世界的每个传送物
  for (const w of WORLDS) {
    if (!(await goWorld(w))) { log(false, `去不了 ${w}`); continue; }
    const s0 = await st();
    const portals = s0.portals;
    // 出入口（传送物 + 通往站点的晶体）：家以外的世界最多四个
    const gates = portals.length + s0.entrances.length;
    if (w !== 'home') log(gates <= 4, `${w} 出入口 ${gates} 个（传送物 ${portals.length} · 晶体 ${s0.entrances.length}）`);
    for (let i = 0; i < portals.length; i++) {
      if (!(await goWorld(w))) { log(false, `回不到 ${w}`); break; }
      await sleep(300);
      const p = (await st()).portals[i];
      const [px, py, pz] = p.pos;
      let ok = false;
      if (p.mode === 'key') {
        for (const a of [0, 90, 180, 270, 45, 135, 225, 315]) {
          const r = a * Math.PI / 180;
          const dx = Math.sin(r) * 1.4, dz = Math.cos(r) * 1.4;
          // 面朝传送物：从 (px+dx, pz+dz) 看向 (px, pz)
          const yaw = Math.atan2(dx, dz) * 180 / Math.PI;
          await page.evaluate((x, y, z, yw) => window.__nexus.set(x, y, z, yw, -10), px + dx, py - 1.0, pz + dz, yaw);
          await sleep(250);
          await press('KeyE');
          if (await waitWorld(p.to, 6000)) { ok = true; break; }
        }
      } else {
        for (const a of [0, 180, 90, 270, 45, 135, 225, 315]) {
          const r = a * Math.PI / 180;
          const dx = Math.sin(r) * 2.2, dz = Math.cos(r) * 2.2;
          const yaw = Math.atan2(dx, dz) * 180 / Math.PI;
          await page.evaluate((x, y, z, yw) => window.__nexus.set(x, y, z, yw, 0), px + dx, py - 0.9, pz + dz, yaw);
          await sleep(200);
          await key('KeyW', true);
          const hit = await waitWorld(p.to, 6000);
          await key('KeyW', false);
          if (hit) { ok = true; break; }
          if ((await st()).world !== w && !(await goWorld(w))) break;
          await sleep(200);
        }
      }
      log(ok, `${w} → ${p.to}${p.at ? '@' + p.at : ''}（${p.mode}${p.title ? ' ' + p.title : ''}）`);
      if (ok && p.at) {
        const s2 = await st();
        log(s2.arrivals.includes(p.at), `  到达点 ${p.at} 在 ${p.to} 里`);
        // 来回成对：落脚处最近的传送物就是回 w 的那个，而且就在跟前
        const f = s2.feet;
        const near = s2.portals.map((q) => ({ q, d: Math.hypot(q.pos[0] - f[0], q.pos[2] - f[2]) })).sort((a, b) => a.d - b.d)[0];
        log(!!near && near.q.to === w && near.d < 4, `  回程：落脚处最近的是 → ${near?.q.to}（${near?.d.toFixed(1)}m）`);
      }
    }
  }

  // 3. 转场中途截图、醒来（日记目录里的「醒来」）、后退
  await goWorld('procession');
  await sleep(500);
  await press('Tab');
  await sleep(1100);
  await page.evaluate(() => {
    // 目录左页第 5 行（醒来）：UI 像素 ＝ 屏幕 ÷ 2，书页 148×196 居中
    const w = (Math.floor(innerWidth / 8) * 8) / 2;
    const h = (Math.floor(innerHeight / 8) * 8) / 2;
    window.__nexus.diary.moveTo(w / 2 - 148 + 40, h / 2 - 98 + 100);
  });
  // 悬停下一帧才更新，等一下再点
  await sleep(120);
  await page.evaluate(() => window.__nexus.diary.click());
  await sleep(450);
  await page.screenshot({ path: path.join(OUT, 't-02-dissolve-out.png') });
  log(await waitWorld('home'), '日记 · 醒来 → home');
  await sleep(150);
  await page.screenshot({ path: path.join(OUT, 't-03-after-wake.png') });
  await page.goBack();
  log(await waitWorld('procession'), '浏览器后退 → procession');
  s = await st();
  log(WORLDS.every((w) => s.visited.includes(w)), `去过：${s.visited.join(' ')}`);
  const entr = await page.evaluate(() => document.title);
  console.log(`${results.filter(Boolean).length}/${results.length} 通过`);
  process.exitCode = results.every(Boolean) ? 0 : 1;
  await browser.close();
  srv.close();
});
