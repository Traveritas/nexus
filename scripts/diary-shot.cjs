/* 日记本截图：先 npm run build，再 node scripts/diary-shot.cjs
   在家里按 Tab 打开日记，拍下打开过程、悬停、翻到设置页、翻回来、合上。输出 .shots/diary-* */
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
  await page.goto(`http://127.0.0.1:${srv.address().port}/?hud=0&world=home&pos=1.2,0.15,-1.8&yaw=200&pitch=-4`, { waitUntil: 'load' });
  await page.waitForFunction(() => window.__nexus);
  await wait(800);
  const shot = (name) => page.screenshot({ path: path.join(OUT, `diary-${name}.png`) });
  // 坐标是 UI 像素（屏幕 / 2）
  const at = (x, y) => page.evaluate((x, y) => window.__nexus.diary.moveTo(x, y), x, y);
  const click = () => page.evaluate(() => window.__nexus.diary.click());

  await page.evaluate(() => window.__nexus.keys('Tab', true));
  for (let i = 0; i < 6; i++) { await shot(`open-${i}`); await wait(60); }
  await wait(900);
  await shot('index');
  await at(214, 168);
  await wait(100);
  await shot('hover');
  await click();
  for (let i = 0; i < 4; i++) { await wait(70); await shot(`turn-${i}`); }
  await wait(700);
  await at(214, 82 + 36 + 2 * 14 + 8);
  await wait(100);
  await shot('settings');
  await at(214, 82 + 36 + 8 * 14 + 8);
  await wait(60);
  await click();
  for (let i = 0; i < 3; i++) { await wait(80); await shot(`back-${i}`); }
  await wait(700);
  await page.evaluate(() => window.__nexus.keys('Tab', true));
  for (let i = 0; i < 3; i++) { await wait(80); await shot(`close-${i}`); }
  console.log('done');
  await browser.close();
  srv.close();
});
