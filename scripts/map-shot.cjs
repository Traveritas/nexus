/* 罗盘地图截图：先 npm run build，再 node scripts/map-shot.cjs
   预置存档（去过的世界、走过的连接、手里拿着罗盘），在家里捏到底：暗圈扩散 → 本世界的星 → 抬头看星座 → 去回廊看站点。输出 .shots/map-* */
const path = require('path');
const fs = require('fs');
const http = require('http');
const os = require('os');
const puppeteer = require(path.join(os.tmpdir(), 'node_modules', 'puppeteer-core'));

const ROOT = path.join(__dirname, '..', 'dist');
const OUT = path.join(__dirname, '..', '.shots');
fs.mkdirSync(OUT, { recursive: true });
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.woff2': 'font/woff2' };
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

const srv = http.createServer((req, res) => {
  let f = path.join(ROOT, decodeURIComponent((req.url || '/').split('?')[0]));
  if (fs.existsSync(f) && fs.statSync(f).isDirectory()) f = path.join(f, 'index.html');
  if (!fs.existsSync(f)) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { 'content-type': TYPES[path.extname(f)] || 'application/octet-stream' });
  fs.createReadStream(f).pipe(res);
});
srv.listen(0, '127.0.0.1', async () => {
  const browser = await puppeteer.launch({
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless: 'new',
    args: ['--use-angle=d3d11', '--enable-gpu', '--ignore-gpu-blocklist'],
  });
  const page = await browser.newPage();
  page.on('pageerror', (e) => console.log('[pageerror]', e.message));
  page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') console.log('[page]', m.text()); });
  await page.setViewport({ width: 1280, height: 720 });
  const base = `http://127.0.0.1:${srv.address().port}/`;
  await page.goto(base + '?hud=0&intro=0', { waitUntil: 'load' });
  await page.evaluate(() => {
    localStorage.setItem('nexus:visited', JSON.stringify(['house', 'house_out', 'descent', 'sunpatch', 'longshadow', 'glasshouse', 'shoal', 'stair', 'stair_b', 'isles', 'home']));
    localStorage.setItem('nexus:edges', JSON.stringify(['house|house_out', 'descent|house', 'house|sunpatch', 'house|longshadow', 'glasshouse|house', 'house|shoal', 'house|stair', 'stair|stair_b', 'isles|stair_b', 'glasshouse|shoal', 'glasshouse|sunpatch', 'glasshouse|longshadow', 'longshadow|sunpatch', 'home|house']));
    localStorage.setItem('nexus:sites', JSON.stringify(['descent']));
    localStorage.setItem('nexus:items', JSON.stringify({ owned: [{ id: 'compass', world: 'house', night: 1 }], held: 'compass' }));
  });
  // 家的客厅，茶几北边，面向那杯水（→ 浅滩）
  await page.goto(base + '?world=house&hud=0&intro=0&pos=2.3,0.15,-3.4&yaw=0&pitch=-16', { waitUntil: 'load' });
  await page.waitForFunction(() => window.__nexus);
  await wait(800);
  const shot = (name) => page.screenshot({ path: path.join(OUT, `map-${name}.png`) });
  const key = (c, d) => page.evaluate((c, d) => window.__nexus.keys(c, d), c, d);

  await key('KeyQ', true);
  await wait(850);
  for (let i = 0; i < 5; i++) { await shot(`open-${i}`); await wait(150); }
  await key('KeyQ', false);
  await wait(900);
  await shot('local');
  // 转身看看别的出口
  await page.evaluate(() => { window.__nexus.player.yaw += 1.4; });
  await wait(300);
  await shot('local-turn');
  // 抬头看天
  await page.evaluate(() => { window.__nexus.player.yaw -= 1.4; window.__nexus.player.pitch = 1.5; });
  await wait(400);
  await shot('sky');
  await page.evaluate(() => { window.__nexus.player.pitch = -0.1; });
  // 去下沉：站点
  await page.evaluate(() => window.__nexus.go('descent'));
  await page.waitForFunction(() => window.__nexus.state().world === 'descent' && !window.__nexus.state().travelling, { timeout: 15000 });
  await wait(600);
  await key('KeyQ', true);
  await wait(1100);
  await key('KeyQ', false);
  await wait(1000);
  for (const [i, a] of [0, 1.57, 3.14, 4.71].entries()) {
    await page.evaluate((a) => { window.__nexus.player.yaw = a; }, a);
    await wait(300);
    await shot(`site-${i}`);
  }
  // 正对着晶体：站点的名字是全分辨率的平滑字（梦里的晶体都还没接站点时跳过）
  const hasSite = await page.evaluate(() => window.__nexus.state().sitesHere.length > 0);
  if (!hasSite) console.log('这里没有接了站点的晶体，跳过 site-focus');
  else await page.evaluate(() => {
    const n = window.__nexus;
    const site = n.state().sitesHere[0];
    const f = n.state().feet;
    const dx = site.pos[0] - f[0], dz = site.pos[2] - f[2], dy = site.pos[1] - (f[1] + 1.6);
    n.player.yaw = Math.atan2(-dx, -dz);
    n.player.pitch = Math.atan2(dy, Math.hypot(dx, dz));
  });
  await wait(300);
  if (hasSite) await shot('site-focus');
  console.log('done');
  await browser.close();
  srv.close();
});
