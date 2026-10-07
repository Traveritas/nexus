/* 天空测速与截图：先 npm run build，再 node scripts/skybench.cjs [主题,主题…] [--shots]
   不锁帧，抬头看天测 3 秒的帧率；--shots 时每个主题隔几秒拍三张，看动起来的样子。输出 .shots/sky-* */
const path = require('path');
const fs = require('fs');
const http = require('http');
const os = require('os');
const puppeteer = require(path.join(os.tmpdir(), 'node_modules', 'puppeteer-core'));

const ROOT = path.join(__dirname, '..', 'dist');
const OUT = path.join(__dirname, '..', '.shots');
fs.mkdirSync(OUT, { recursive: true });
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css' };
const names = (process.argv[2] && !process.argv[2].startsWith('--') ? process.argv[2] : 'blank,dye,silk').split(',');
const shots = process.argv.includes('--shots');

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
    args: ['--use-angle=d3d11', '--enable-gpu', '--ignore-gpu-blocklist', '--disable-gpu-vsync', '--disable-frame-rate-limit'],
  });
  const page = await browser.newPage();
  page.on('pageerror', (e) => console.log('[pageerror]', e.message));
  page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') console.log('[page]', m.text()); });
  await page.setViewport({ width: 1920, height: 1080 });
  for (const name of names) {
    await page.goto(`http://127.0.0.1:${srv.address().port}/?hud=0&world=${process.env.WORLD || "isles"}&sky=${name}`, { waitUntil: 'load' });
    await page.waitForFunction(() => window.__nexus);
    await page.evaluate((pitch) => { const n = window.__nexus; const p = n.state().feet; n.set(p[0], p[1], p[2], 20, pitch); }, Number(process.env.PITCH || 32));
    await new Promise((r) => setTimeout(r, 800));
    const fps = await page.evaluate(() => new Promise((res) => {
      let n = 0; const t0 = performance.now();
      const f = () => { n++; if (performance.now() - t0 < 3000) requestAnimationFrame(f); else res(n / ((performance.now() - t0) / 1000)); };
      requestAnimationFrame(f);
    }));
    console.log(name.padEnd(10), fps.toFixed(1), 'fps');
    if (shots) {
      for (let i = 0; i < 3; i++) {
        await page.screenshot({ path: path.join(OUT, `sky-${name.replace(':', '_')}-p${process.env.PITCH || 32}-${i}.png`) });
        await new Promise((r) => setTimeout(r, 4000));
      }
    }
  }
  await browser.close();
  srv.close();
});
