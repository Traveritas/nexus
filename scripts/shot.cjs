/* 截图：先 npm run build，再 node scripts/shot.cjs
   临时静态服务器 + 本机 Chrome + puppeteer-core（%TEMP%/node_modules）。输出 .shots/ */
const path = require('path');
const fs = require('fs');
const http = require('http');
const os = require('os');
const puppeteer = require(path.join(os.tmpdir(), 'node_modules', 'puppeteer-core'));

const ROOT = path.join(__dirname, '..', 'dist');
const OUT = path.join(__dirname, '..', '.shots');
fs.mkdirSync(OUT, { recursive: true });
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css' };

// [名字, 脚底 x, y, z, yaw°, pitch°, flags]
const VIEWS = [
  ['01-entry', 0, 0, 13, 0, -2, {}],
  ['02-near', 1.2, 0, -1.2, 12, 0, {}],
  ['03-chair', 2, 0, 6, 38, 8, {}],
  ['04-flower', 1, 0, 8, -35, 6, {}],
  ['05-stairs', 4, 0, 2, -48, 10, {}],
  ['06-terrace', -8, 0, -4, 27, 4, {}],
  ['07-jumps', 8, 0, 9, -61, 6, {}],
  ['01-entry-field', 0, 0, 13, 0, -2, { field: true }],
  ['02-near-field', 1.2, 0, -1.2, 12, 0, { field: true }],
  ['01-entry-raw', 0, 0, 13, 0, -2, { raw: true }],
];
const only = process.argv[2];

const srv = http.createServer((req, res) => {
  let f = path.join(ROOT, decodeURIComponent((req.url || '/').split('?')[0]));
  if (fs.existsSync(f) && fs.statSync(f).isDirectory()) f = path.join(f, 'index.html');
  if (!fs.existsSync(f)) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { 'content-type': TYPES[path.extname(f)] || 'application/octet-stream' });
  fs.createReadStream(f).pipe(res);
});
srv.listen(0, '127.0.0.1', async () => {
  const base = `http://127.0.0.1:${srv.address().port}/?world=slice&freeze=1&hud=0`;  // 机位是切片（slice）的
  const browser = await puppeteer.launch({
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless: 'new',
    args: ['--use-angle=d3d11', '--enable-gpu', '--ignore-gpu-blocklist'],
  });
  const page = await browser.newPage();
  page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') console.log('[page]', m.text()); });
  page.on('pageerror', (e) => console.log('[pageerror]', e.message));
  await page.setViewport({ width: 1280, height: 720 });
  await page.goto(base, { waitUntil: 'load' });
  await page.waitForFunction(() => window.__nexus);
  await new Promise((r) => setTimeout(r, 500));
  for (const [name, x, y, z, yaw, pitch, flags] of VIEWS) {
    if (only && !name.includes(only)) continue;
    await page.evaluate((x, y, z, yaw, pitch, flags) => {
      const n = window.__nexus;
      Object.assign(n.flags, { raw: false, field: false, palette: true, outline: 0, lock: -1 }, flags);
      n.set(x, y, z, yaw, pitch);
    }, x, y, z, yaw, pitch, flags);
    await new Promise((r) => setTimeout(r, 700));
    await page.screenshot({ path: path.join(OUT, `${name}.png`) });
    console.log('shot', name);
  }
  const fps = await page.evaluate(() => document.getElementById('hud').textContent.split('\n')[0]);
  console.log(fps);
  await browser.close();
  srv.close();
});
