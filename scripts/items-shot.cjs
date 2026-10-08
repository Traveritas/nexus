/* 物品截图：先 npm run build，再 node scripts/items-shot.cjs
   清空物品存档，走到家里茶几上的罗盘怀表跟前：纸签 → 按 E 拾起 → 得到的演出 → 按住 Q 举起、捏紧 → 按住 F 环绕展示 → 日记「拾得」页。输出 .shots/items-* */
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
  const url = `http://127.0.0.1:${srv.address().port}/?hud=0&world=home&pos=6.62,0.15,-6.25&yaw=0&pitch=-38`;
  await page.goto(url, { waitUntil: 'load' });
  await page.evaluate(() => localStorage.removeItem('nexus:items'));
  await page.goto(url, { waitUntil: 'load' });
  await page.waitForFunction(() => window.__nexus);
  await wait(600);
  const shot = (name) => page.screenshot({ path: path.join(OUT, `items-${name}.png`) });

  // 家里客厅的茶几上摆着罗盘怀表（blender/scenes/home.py）；站在茶几南边低头看它
  for (let i = 0; i < 3; i++) { await wait(500); await shot('world-' + i); }
  await page.evaluate(() => window.__nexus.keys('KeyE', true));
  for (let i = 0; i < 5; i++) { await wait(90); await shot(`get-${i}`); }
  await wait(1000);
  await shot('get-hold');
  await wait(900);
  await shot('get-out');
  await wait(800);

  await page.evaluate(() => window.__nexus.keys('KeyQ', true));
  for (let i = 0; i < 4; i++) { await wait(110); await shot(`use-${i}`); }
  await wait(500);
  await shot('use-bloom');
  await page.evaluate(() => window.__nexus.keys('KeyQ', false));
  await wait(600);

  // 按住 F：环绕展示（先抬头平视）
  await page.evaluate(() => { window.__nexus.player.pitch = -0.05; });
  await page.evaluate(() => window.__nexus.keys('KeyF', true));
  await wait(200);
  await shot('ring-open');
  await wait(500);
  await shot('ring');
  await page.evaluate(() => window.__nexus.keys('KeyF', false));
  await wait(500);

  await page.evaluate(() => window.__nexus.keys('Tab', true));
  await wait(1200);
  await page.evaluate(() => window.__nexus.diary.moveTo(214, 82 + 72));
  await wait(100);
  await page.evaluate(() => window.__nexus.diary.click());
  await wait(900);
  await page.evaluate(() => window.__nexus.diary.moveTo(214, 82 + 58));
  await wait(150);
  await shot('diary');
  console.log(JSON.stringify(await page.evaluate(() => ({ owned: window.__nexus.items.owned, held: window.__nexus.items.held }))));
  await browser.close();
  srv.close();
});
