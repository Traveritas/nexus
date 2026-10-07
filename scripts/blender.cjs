/* 无界面调用 Blender
   node scripts/blender.cjs build <名字>   运行 blender/scenes/<名字>.py：从零搭场景，存 .blend 并导出 GLB
   node scripts/blender.cjs export <名字>  打开 blender/<名字>.blend 导出 GLB（手动改过 .blend 之后用）
   Blender 路径：环境变量 BLENDER，默认 D:/Steam/steamapps/common/Blender/blender.exe */
const path = require('path');
const { spawnSync } = require('child_process');

const BLENDER = process.env.BLENDER || 'D:/Steam/steamapps/common/Blender/blender.exe';
const ROOT = path.join(__dirname, '..');
const [cmd, name] = process.argv.slice(2);
if (!cmd || !name) {
  console.log('用法：node scripts/blender.cjs build|export <名字>');
  process.exit(1);
}

const args =
  cmd === 'build'
    ? ['-b', '--factory-startup', '--python-exit-code', '1', '--python', path.join(ROOT, 'blender', 'scenes', `${name}.py`)]
    : ['-b', path.join(ROOT, 'blender', `${name}.blend`), '--python-exit-code', '1', '--python', path.join(ROOT, 'blender', 'export.py')];

const r = spawnSync(BLENDER, args, { encoding: 'utf8' });
const out = (r.stdout || '') + (r.stderr || '');
// 只留有用的几行
for (const line of out.split(/\r?\n/)) {
  if (/\[nx\]|Error|Traceback|File "|^\s+\w+Error|Warning/.test(line)) console.log(line);
}
process.exit(r.status ?? 1);
