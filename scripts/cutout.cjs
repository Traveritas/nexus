/* 把现成模型渲染成真实贴图的剪纸（public/sprites/<名字>@<每米像素>.png）
   node scripts/cutout.cjs <PolyHaven id> [--name 名字] [--height 米] [--yaw 度] [--ppm 64] [--tilt 度] [--part 第几个变体]
   （有的模型是一排并排的变体，--part 0/1/2… 只取其中一个）
   例：node scripts/cutout.cjs WoodenChair_01 --name chair_wood --height 2 --yaw 180
   模型不在本地时先自动取（scripts/fetch-asset.cjs）。 */
const path = require('path');
const fs = require('fs');
const { spawnSync } = require('child_process');

const BLENDER = process.env.BLENDER || 'D:/Steam/steamapps/common/Blender/blender.exe';
const ROOT = path.join(__dirname, '..');
const [id, ...rest] = process.argv.slice(2);
if (!id) {
  console.log('用法：node scripts/cutout.cjs <id> [--name 名字] [--height 米] [--yaw 度] [--ppm 64] [--tilt 度]');
  process.exit(1);
}
const opt = { name: id.toLowerCase(), height: '2', yaw: '0', ppm: '64', tilt: '0', part: '-' };
for (let i = 0; i < rest.length; i += 2) opt[rest[i].replace(/^--/, '')] = rest[i + 1];

if (!fs.existsSync(path.join(ROOT, 'assets', 'polyhaven', id))) {
  const f = spawnSync('node', [path.join(__dirname, 'fetch-asset.cjs'), id], { stdio: 'inherit' });
  if (f.status) process.exit(f.status);
}
const r = spawnSync(BLENDER, ['-b', '--factory-startup', '--python-exit-code', '1', '--python', path.join(ROOT, 'blender', 'cutout.py'),
  '--', id, opt.name, opt.height, opt.yaw, opt.ppm, opt.tilt, opt.part], { encoding: 'utf8' });
for (const line of ((r.stdout || '') + (r.stderr || '')).split(/\r?\n/)) {
  if (/\[nx\]|Error|Traceback|File "/.test(line)) console.log(line);
}
if (r.status) process.exit(r.status);

// 收拾轮廓：把叶缝里的碎小透明孔补上、透明度一刀切成全有或全无（管线会沿透明边描边，碎孔会变成满屏的线）
const out = path.join(ROOT, 'public', 'sprites', `${opt.name}@${opt.ppm}.png`);
const m = spawnSync('magick', [out, '-channel', 'A', '-morphology', 'Close', `Disk:${opt.close || '1.5'}`, '-threshold', '50%', '+channel', out],
  { encoding: 'utf8' });
if (m.status) console.log('[nx] magick 收拾轮廓失败（没装 ImageMagick？），图照样能用：', m.stderr.trim());
process.exit(0);
