/* 看任意一个世界：先 npm run build，再
     node scripts/view.cjs <世界> 名字:x,y,z,朝向[,俯仰[,太阳秒]] …
   坐标是 Blender 的（脚底，Z 朝上），朝向同 spawn（度）；太阳秒＝会转的太阳拨到第几秒（atmosphere 的 sun_turn）。
   环境变量 Q 追加查询串（如 Q='&sky=pale'）。输出 .shots/<世界>-<名字>.png
   临时静态服务器 + 本机 Chrome + puppeteer-core（%TEMP%/node_modules），同 shot.cjs */
const path = require('path');
const fs = require('fs');
const http = require('http');
const os = require('os');
const puppeteer = require(path.join(os.tmpdir(), 'node_modules', 'puppeteer-core'));

// 环境变量 DIST 换成别的构建目录（几个人同时构建时各用各的：npx vite build --outDir dist-xxx）
const ROOT = path.resolve(__dirname, '..', process.env.DIST || 'dist');
const OUT = path.join(__dirname, '..', '.shots');
fs.mkdirSync(OUT, { recursive: true });
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css' };

const [world, ...specs] = process.argv.slice(2);
if (!world || !specs.length) {
  console.log('用法：node scripts/view.cjs <世界> 名字:x,y,z,朝向[,俯仰[,太阳秒]] …');
  process.exit(1);
}
const views = specs.map((s) => {
  const [name, nums] = s.split(':');
  const [x, y, z, yaw, pitch = 0, sun] = nums.split(',').map(Number);
  return { name, x, y, z, yaw, pitch, sun };
});

const srv = http.createServer((req, res) => {
  let f = path.join(ROOT, decodeURIComponent((req.url || '/').split('?')[0]));
  if (fs.existsSync(f) && fs.statSync(f).isDirectory()) f = path.join(f, 'index.html');
  if (!fs.existsSync(f)) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { 'content-type': TYPES[path.extname(f)] || 'application/octet-stream' });
  fs.createReadStream(f).pipe(res);
});
srv.listen(0, '127.0.0.1', async () => {
  const base = `http://127.0.0.1:${srv.address().port}/?world=${world}&freeze=1&hud=0&intro=0${process.env.Q || ''}`;
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
  await page.waitForFunction((w) => window.__nexus && window.__nexus.state().world === w && !window.__nexus.state().travelling, {}, world);
  await new Promise((r) => setTimeout(r, 800));
  for (const v of views) {
    await page.evaluate((v) => {
      const n = window.__nexus;
      Object.assign(n.flags, { raw: false, field: false, palette: true, outline: 0, lock: -1 });
      if (Number.isFinite(v.sun)) n.sunTime(v.sun);
      // Blender (x, y, z) → three (x, z, −y)
      n.set(v.x, v.z, -v.y, v.yaw, v.pitch);
    }, v);
    await new Promise((r) => setTimeout(r, 900));
    const file = path.join(OUT, `${world}-${v.name}.png`);
    await page.screenshot({ path: file });
    console.log('shot', file);
  }
  await browser.close();
  srv.close();
});
