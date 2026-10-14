/* 浅梦样板 · 白模：用 Blender 无界面跑 tools/build_scenes.py
   node mockup/shallows-01/tools/build.cjs all
   node mockup/shallows-01/tools/build.cjs arcade
   Blender 路径：环境变量 BLENDER，默认 D:/Steam/steamapps/common/Blender/blender.exe */
const path = require('path');
const { spawnSync } = require('child_process');

const BLENDER = process.env.BLENDER || 'D:/Steam/steamapps/common/Blender/blender.exe';
const HERE = __dirname;
const which = process.argv[2] || 'all';
const args = ['-b', '--factory-startup', '--python-exit-code', '1',
  '--python', path.join(HERE, 'build_scenes.py'), '--', which];
const r = spawnSync(BLENDER, args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
const out = (r.stdout || '') + (r.stderr || '');
for (const line of out.split(/\r?\n/)) {
  if (/\[mock\]|Error|Traceback|File "|^\s+\w+Error|Warning/.test(line)) console.log(line);
}
process.exit(r.status ?? 1);
