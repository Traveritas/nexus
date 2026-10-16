/* 日记本截图：先 npm run build，再 node scripts/diary-shot.cjs
   中文、英文各一遍：预置存档，在家里按 Tab 打开日记，点索引贴翻到拾得、设置，再翻回记录，合上。输出 .shots/diary-<语言>-* */
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
  // 两种语言各拍一遍；预置一份存档，让记录页、拾得页有东西
  for (const lang of ['zh', 'en']) {
    const page = await browser.newPage();
    page.on('pageerror', (e) => console.log('[pageerror]', e.message));
    page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') console.log('[page]', m.text()); });
    await page.evaluateOnNewDocument((lang) => {
      localStorage.setItem('nexus:settings', JSON.stringify({ lang }));
      localStorage.setItem('nexus:visited', JSON.stringify(['house', 'house_out', 'descent', 'sunpatch', 'glasshouse', 'shoal']));
      localStorage.setItem('nexus:edges', JSON.stringify(['house|house_out', 'descent|house', 'house|sunpatch', 'glasshouse|house', 'glasshouse|shoal']));
      localStorage.setItem('nexus:sites', JSON.stringify(['descent']));
      localStorage.setItem('nexus:items', JSON.stringify({ owned: [{ id: 'compass', world: 'house', night: 1 }], held: 'compass' }));
    }, lang);
    await page.setViewport({ width: 1280, height: 720 });
    await page.goto(`http://127.0.0.1:${srv.address().port}/?hud=0&world=house`, { waitUntil: 'load' });
    await page.waitForFunction(() => window.__nexus);
    await wait(800);
    const shot = (name) => page.screenshot({ path: path.join(OUT, `diary-${lang}-${name}.png`) });
    // 坐标是 UI 像素（屏幕 / 2）
    const at = (x, y) => page.evaluate((x, y) => window.__nexus.diary.moveTo(x, y), x, y);
    const click = () => page.evaluate(() => window.__nexus.diary.click());
    /** 第 i 张索引贴的中心（书在 UI 画布正中：页宽 148、页高 196、贴高取画布） */
    const tab = (i) => page.evaluate((i) => {
      const d = window.__nexus.diary;
      const r = d.tabs.regions.find((r) => r.id === ['tab:record', 'tab:items', 'tab:settings'][i]);
      const x0 = d.ui.w / 2;
      const y0 = d.ui.h / 2 - 98 - d.tabs.canvas.height;
      return r ? [x0 + r.x + r.w / 2, y0 + r.y + r.h / 2] : null;
    }, i);
    const goTab = async (i, name) => {
      const p = await tab(i);
      if (!p) return;
      await at(p[0], p[1]);
      await wait(100);
      await shot(`hover-${name}`);
      await click();
      for (let k = 0; k < 3; k++) { await wait(80); await shot(`turn-${name}-${k}`); }
      await wait(700);
      await shot(name);
    };

    await page.evaluate(() => window.__nexus.keys('Tab', true));
    for (let i = 0; i < 4; i++) { await shot(`open-${i}`); await wait(90); }
    await wait(900);
    await shot('record');
    await goTab(1, 'items');
    await goTab(2, 'settings');
    await goTab(0, 'back');
    await page.evaluate(() => window.__nexus.keys('Tab', true));
    for (let i = 0; i < 3; i++) { await wait(80); await shot(`close-${i}`); }
    await page.close();
  }
  console.log('done');
  await browser.close();
  srv.close();
});
