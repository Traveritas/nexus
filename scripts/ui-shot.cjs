/* UI 截图：先 npm run build，再 node scripts/ui-shot.cjs [世界…]
   在每个世界里走到按键型传送物跟前、看着它，截下纸签（含出现中的一帧）。输出 .shots/ui-* */
const path = require('path');
const fs = require('fs');
const http = require('http');
const os = require('os');
const puppeteer = require(path.join(os.tmpdir(), 'node_modules', 'puppeteer-core'));

const ROOT = path.join(__dirname, '..', 'dist');
const OUT = path.join(__dirname, '..', '.shots');
fs.mkdirSync(OUT, { recursive: true });
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.woff2': 'font/woff2' };
const worlds = process.argv.slice(2).length ? process.argv.slice(2) : ['home'];
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
  await page.setViewport({ width: 1280, height: 720 });
  for (const w of worlds) {
    await page.goto(`http://127.0.0.1:${srv.address().port}/?hud=0&world=${w}`, { waitUntil: 'load' });
    await page.waitForFunction(() => window.__nexus);
    await wait(600);
    const portals = await page.evaluate(() => window.__nexus.state().portals.filter((p) => p.mode === 'key'));
    for (const [i, p] of portals.entries()) {
      // 从四个方向试着站到它跟前 2m，看着它；纸签出来了就截
      for (const a of [0, 90, 180, 270]) {
        const r = (a * Math.PI) / 180;
        const fx = p.pos[0] + Math.sin(r) * 2;
        const fz = p.pos[2] + Math.cos(r) * 2;
        await page.evaluate((fx, fy, fz, tx, ty, tz) => {
          const n = window.__nexus;
          const yaw = Math.atan2(-(tx - fx), -(tz - fz));
          const pitch = Math.atan2(ty - (fy + 1.6), Math.hypot(tx - fx, tz - fz));
          n.set(fx, fy, fz, (yaw * 180) / Math.PI, (pitch * 180) / Math.PI);
        }, fx, p.pos[1] - 1.2, fz, ...p.pos);
        await wait(110);
        const name = `ui-${w}-${i}-${a}`;
        await page.screenshot({ path: path.join(OUT, `${name}-in.png`) });
        await wait(700);
        await page.screenshot({ path: path.join(OUT, `${name}.png`) });
        console.log('shot', name, p.title, '→', p.to);
        break;
      }
    }
  }
  await browser.close();
  srv.close();
});
