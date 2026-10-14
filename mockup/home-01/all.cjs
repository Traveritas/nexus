/* 梦里的家 · 样板 01：生成 JSON，再借浅梦样板的工具展开、搭白模、画地图
   node mockup/home-01/all.cjs            全部
   node mockup/home-01/all.cjs home-core  单个（也可以逗号分隔） */
const path = require('path');
const { spawnSync } = require('child_process');

const HERE = __dirname;
const TOOLS = path.join(HERE, '..', 'shallows-01', 'tools');
const which = process.argv[2] || 'all';
const env = { ...process.env, MOCK_DIR: HERE };
const steps = [
  ['gen', [path.join(HERE, 'gen.cjs')]],
  ['expand', [path.join(TOOLS, 'expand.cjs'), which]],
  ['build', [path.join(TOOLS, 'build.cjs'), which]],
  ['maps', [path.join(TOOLS, 'maps.cjs'), which]],
];
for (const [name, args] of steps) {
  console.log(`\n=== ${name} ${which} ===`);
  const r = spawnSync(process.execPath, args, { stdio: 'inherit', env });
  if (r.status !== 0) { console.log(`[all] ${name} 失败`); process.exit(r.status ?? 1); }
}
console.log('\n[all] 好了');
