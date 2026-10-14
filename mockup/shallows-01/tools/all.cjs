/* 浅梦样板：一条命令跑完三步 —— 展开、搭白模、画地图
   node mockup/shallows-01/tools/all.cjs all
   node mockup/shallows-01/tools/all.cjs arcade,isles */
const path = require('path');
const { spawnSync } = require('child_process');

const HERE = __dirname;
const which = process.argv[2] || 'all';
const steps = [
  ['expand', [path.join(HERE, 'expand.cjs'), which]],
  ['build', [path.join(HERE, 'build.cjs'), which]],
  ['maps', [path.join(HERE, 'maps.cjs'), which]],
];
for (const [name, args] of steps) {
  console.log(`\n=== ${name} ${which} ===`);
  const r = spawnSync(process.execPath, args, { stdio: 'inherit' });
  if (r.status !== 0) { console.log(`[all] ${name} 失败`); process.exit(r.status ?? 1); }
}
console.log('\n[all] 好了');
