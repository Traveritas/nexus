/* 旧梦的入口与主域星图：先 npm run build，再 node scripts/olddream-shot.cjs
   1. 家家家里那扇转了 32° 的孤门：关着时穿过门框不算；推开以后穿过去 → 旧家
   2. 旧家里捏罗盘：本世界的星、头顶只剩旧梦的星座
   3. 回到家里捏罗盘：通往旧梦的那颗星带环；头顶浅梦的星座外伸出一截通往旧梦的线
   输出 .shots/olddream-* */
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
    localStorage.clear();
    localStorage.setItem('nexus:visited', JSON.stringify(['house', 'house_out', 'descent', 'sunpatch', 'glasshouse', 'shoal', 'stair']));
    localStorage.setItem('nexus:edges', JSON.stringify(['house|house_out', 'descent|house', 'house|sunpatch', 'glasshouse|house', 'house|shoal', 'house|stair', 'glasshouse|shoal']));
    localStorage.setItem('nexus:items', JSON.stringify({ owned: [{ id: 'compass', world: 'house', night: 1 }], held: 'compass' }));
  });
  await page.goto(base + '?world=house&hud=0&intro=0', { waitUntil: 'load' });
  await page.waitForFunction(() => window.__nexus);
  await wait(800);
  const shot = (name) => page.screenshot({ path: path.join(OUT, `olddream-${name}.png`) });
  const key = (c, d) => page.evaluate((c, d) => window.__nexus.keys(c, d), c, d);
  const state = () => page.evaluate(() => window.__nexus.state());
  const world = async () => (await state()).world;

  // 孤门：传送物在门框正中；门框的法线（three 坐标）＝ Blender 本地 +y 转 32°
  const door = (await state()).portals.find((p) => p.to === 'home');
  if (!door) throw new Error('家里没有通往旧家的传送物');
  const a = (32 * Math.PI) / 180;
  const n = [-Math.sin(a), 0, -Math.cos(a)];
  const [px, py, pz] = door.pos;
  const feetY = py - 1.0 + 0.02;
  /** 从门框前 d0 米走到门框后 d1 米（直接挪脚，每帧一小步） */
  const cross = async (d0, d1, name) => {
    const yaw = Math.atan2(-n[0], -n[2]);
    for (let k = 0; k <= 24; k++) {
      const d = d0 + ((d1 - d0) * k) / 24;
      await page.evaluate((x, y, z, yaw) => {
        const p = window.__nexus.player;
        p.feet.set(x, y, z);
        p.yaw = yaw;
        p.pitch = 0;
      }, px + n[0] * d, feetY, pz + n[2] * d, yaw);
      await wait(40);
      if (k === 6 && name) await shot(name);
      if ((await world()) !== 'house' || (await state()).travelling) return true;
    }
    return false;
  };

  console.log('door closed, crossing →', (await cross(-1.4, 1.4, 'door-closed')) ? 'WENT (wrong)' : 'stayed (ok)');
  await page.evaluate(() => window.__nexus.pose('h_lonedoor_door', true));
  await wait(1200);
  const went = await cross(-1.4, 1.4, 'door-open');
  console.log('door open, crossing →', went ? 'went' : 'STAYED (wrong)');
  for (let i = 0; i < 40 && (await world()) !== 'home'; i++) await wait(150);
  await wait(1500);
  console.log('now in', await world());
  await shot('home');

  // 旧家里捏罗盘
  await page.evaluate(() => { window.__nexus.player.pitch = -0.2; });
  await key('KeyQ', true);
  await wait(850);
  await key('KeyQ', false);
  await wait(1200);
  await shot('home-local');
  await page.evaluate(() => { window.__nexus.player.yaw += 2.2; });
  await wait(300);
  await shot('home-local-turn');
  await page.evaluate(() => { window.__nexus.player.pitch = 1.5; });
  await wait(500);
  await shot('home-sky');

  // 回到家里：通往旧梦的星、星座外的那截
  await page.evaluate(() => window.__nexus.go('house'));
  for (let i = 0; i < 40 && (await world()) !== 'house'; i++) await wait(150);
  await wait(1500);
  await page.evaluate(({ x, y, z, n }) => {
    const p = window.__nexus.player;
    p.feet.set(x - n[0] * 3, y, z - n[2] * 3);
    p.yaw = Math.atan2(-n[0], -n[2]);
    p.pitch = -0.1;
  }, { x: px, y: feetY, z: pz, n });
  await wait(600);
  await key('KeyQ', true);
  await wait(850);
  await key('KeyQ', false);
  await wait(1200);
  await shot('house-local');
  await page.evaluate(() => { window.__nexus.player.pitch = 1.5; });
  await wait(500);
  await shot('house-sky');
  for (let i = 0; i < 8; i++) {
    await page.evaluate(() => { window.__nexus.player.yaw += 0.4; });
    await wait(150);
    await shot(`house-sky-${i}`);
  }
  console.log('done');
  await browser.close();
  srv.close();
});
