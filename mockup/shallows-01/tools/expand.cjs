/* 浅梦样板 · 展开器：layouts/*.json → resolved/*.json
   把组合体（frame / arch / stairs / colonnade）摊成基本体块，校验字段，算出包围盒与统计。
   基本体块的展开只在这里实现一次：Blender 与地图工具都只读 resolved/，所以模型和地图永远一致。

   node mockup/shallows-01/tools/expand.cjs all
   node mockup/shallows-01/tools/expand.cjs arcade
*/
const fs = require('fs');
const path = require('path');

// 环境变量 MOCK_DIR 可指向别的样板文件夹（如 mockup/home-01），共用这套工具
const MOCK = process.env.MOCK_DIR || path.join(__dirname, '..');
const LAYOUTS = path.join(MOCK, 'layouts');
const RESOLVED = path.join(MOCK, 'resolved');

const STYLES = new Set(['deck', 'stair', 'wall', 'mass', 'frame', 'rail', 'water', 'glass', 'plant', 'prop', 'void']);
const KINDS = new Set(['box', 'cylinder', 'torus', 'plane', 'sprite', 'frame', 'arch', 'stairs', 'colonnade', 'procession', 'spriteRow']);
const PORTAL_KINDS = new Set(['home', 'world', 'site', 'realm', 'dead']);

const rad = (d) => (d * Math.PI) / 180;
// 把本地偏移 (lx, ly) 绕 at 转 rot 度
function spin(at, rot, lx, ly, z) {
  const a = rad(rot || 0), c = Math.cos(a), s = Math.sin(a);
  return [at[0] + c * lx - s * ly, at[1] + s * lx + c * ly, z];
}
const P = (name, kind, at, style, extra = {}) => ({ name, kind, at, style, ...extra });

function expand(p, warn) {
  const st = p.style || 'deck';
  const at = p.at || [0, 0];
  const z0 = at.length > 2 ? at[2] : 0;
  const rot = p.rot || 0;
  const out = [];
  switch (p.kind) {
    case 'box': case 'cylinder': case 'torus': case 'plane': case 'sprite':
      return [p];
    case 'frame': case 'arch': {
      const w = p.w || 2.4, h = p.h || 3.6, t = p.t || 0.28, d = p.depth || 0.4;
      const hx = w / 2 - t / 2;
      // 位置绕 at 转，方块本身也跟着转（否则 rot=±90 的框，横楣会横到错的方向）
      out.push(P(`${p.name}_L`, 'box', spin(at, rot, -hx, 0, z0), st, { size: [t, d, h], rot }));
      out.push(P(`${p.name}_R`, 'box', spin(at, rot, hx, 0, z0), st, { size: [t, d, h], rot }));
      out.push(P(`${p.name}_top`, 'box', spin(at, rot, 0, 0, z0 + h - t), st, { size: [w, d, t], rot }));
      if (p.kind === 'arch') {
        const b = p.corner || t * 1.7;
        out.push(P(`${p.name}_cL`, 'box', spin(at, rot, -(w / 2 - b / 2), 0, z0 + h - t - b), st, { size: [b, d, b], rot }));
        out.push(P(`${p.name}_cR`, 'box', spin(at, rot, w / 2 - b / 2, 0, z0 + h - t - b), st, { size: [b, d, b], rot }));
      }
      return out;
    }
    case 'stairs': {
      const w = p.w || 2.4, n = p.n || 8, rise = p.rise || 0.3, run = p.run || 0.75;
      for (let i = 0; i < n; i++) {
        out.push(P(`${p.name}_${i}`, 'box', spin(at, rot, 0, i * run + run / 2, z0), st,
          { size: [w, run, rise * (i + 1)], rot }));
      }
      return out;
    }
    case 'colonnade': {
      const n = p.n || 4, sp = p.spacing || 3, r = p.r || 0.3, h = p.h || 3;
      for (let i = 0; i < n; i++) {
        out.push(P(`${p.name}_${i}`, 'cylinder', spin(at, rot, 0, i * sp, z0), st, { r, h, segments: 16 }));
      }
      return out;
    }
    case 'procession': {
      // 一列越来越大的框，沿 from → to 排开；框面朝着走来的方向
      const [ax, ay] = p.from, [bx, by] = p.to, n = p.n || 8;
      const dx = bx - ax, dy = by - ay;
      const base = (Math.atan2(dy, dx) * 180) / Math.PI - 90; // 本地 +Y 指向前进方向
      for (let i = 0; i < n; i++) {
        const t = n === 1 ? 0 : i / (n - 1);
        const k = Math.pow(p.grow || 1.4, t);
        out.push(P(`${p.name}_${i}`, p.arch ? 'arch' : 'frame', [ax + dx * t, ay + dy * t, z0], st,
          { w: +((p.w0 || 3) * k).toFixed(3), h: +((p.h0 || 4) * k).toFixed(3),
            t: p.t || 0.28, depth: p.depth || 0.4, rot: base + (p.rot0 || 0) + (p.roll || 0) * i }));
      }
      return out;
    }
    case 'spriteRow': {
      const [ax, ay] = p.from, [bx, by] = p.to, n = p.n || 4;
      for (let i = 0; i < n; i++) {
        const t = n === 1 ? 0 : i / (n - 1);
        out.push(P(`${p.name}_${i}`, 'sprite', [ax + (bx - ax) * t, ay + (by - ay) * t, z0], st,
          { sprite: p.sprite, rot: p.rot || 0, face: p.face !== false, back: p.back }));
      }
      return out;
    }
    default:
      warn(`未知 kind「${p.kind}」：${p.name}`);
      return [];
  }
}

// 体块在俯视上的半宽半深（按 rot 算真实外接矩形，不是外接圆）
function extentOf(p) {
  const a = rad(p.rot || 0), c = Math.abs(Math.cos(a)), sn = Math.abs(Math.sin(a));
  if (p.kind === 'box' || p.kind === 'plane') {
    const s = p.size || [1, 1];
    const hx = s[0] / 2, hy = (s[1] || s[0]) / 2;
    return [hx * c + hy * sn, hx * sn + hy * c];
  }
  if (p.kind === 'cylinder') return [p.r || 1, p.r || 1];
  if (p.kind === 'torus') return [(p.major || 3) + (p.minor || 0.2), (p.major || 3) + (p.minor || 0.2)];
  return [1, 1];
}

function run(id) {
  const warn = (m) => console.log(`[expand] ${id}: ${m}`);
  const src = JSON.parse(fs.readFileSync(path.join(LAYOUTS, `${id}.json`), 'utf8'));
  const prims = [];
  const names = new Set();
  const queue = [];
  for (const p of src.prims || []) {
    if (!KINDS.has(p.kind)) { warn(`未知 kind：${p.kind}`); continue; }
    if (p.style && !STYLES.has(p.style)) warn(`未知 style「${p.style}」（${p.name}）`);
    queue.push(p);
  }
  // 组合体可以套组合体（如 procession 里是 frame），反复展开到只剩基本体块
  while (queue.length) {
    const p = queue.shift();
    const kids = expand(p, warn);
    for (const e of kids) {
      if (KINDS.has(e.kind) && !['box', 'cylinder', 'torus', 'plane', 'sprite'].includes(e.kind)) queue.push(e);
      else {
        if (names.has(e.name)) warn(`重名：${e.name}`);
        names.add(e.name);
        prims.push(e);
      }
    }
  }
  for (const po of src.portals || []) {
    const k = po.kind || 'world';
    if (!PORTAL_KINDS.has(k)) warn(`未知出入口 kind：${k}（${po.name}）`);
    if (k !== 'site' && k !== 'dead' && !po.to) warn(`出入口没有 to：${po.name}`);
  }
  if (!src.spawn && src.home) src.spawn = { at: src.home, face: src.home_yaw || 0 };

  // 包围盒与统计（纸片是装饰，撑得再远也不算进取景范围；地图照画，超出的裁掉）
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity, top = 0, low = 0;
  const solid = prims.filter((p) => p.kind !== 'sprite');
  for (const p of (solid.length ? solid : prims)) {
    const [rx, ry] = extentOf(p), at = p.at;
    x0 = Math.min(x0, at[0] - rx); x1 = Math.max(x1, at[0] + rx);
    y0 = Math.min(y0, at[1] - ry); y1 = Math.max(y1, at[1] + ry);
  }
  // 区域标注也撑开取景（走出某一圈会发生什么，圈本身要看得见）
  for (const r of src.regions || []) {
    const [rx, ry] = r.shape === 'circle' ? [r.r, r.r] : [(r.size || [10, 10])[0] / 2, (r.size || [10, 10])[1] / 2];
    x0 = Math.min(x0, r.at[0] - rx); x1 = Math.max(x1, r.at[0] + rx);
    y0 = Math.min(y0, r.at[1] - ry); y1 = Math.max(y1, r.at[1] + ry);
  }
  for (const p of prims) {
    if (p.kind === 'box' || p.kind === 'cylinder') {
      top = Math.max(top, (p.at[2] || 0) + (p.size ? p.size[2] || 0.3 : p.h || 1));
      low = Math.min(low, p.at[2] || 0);
    }
  }
  // 走人的面：deck / stair 的俯视面积（估计「可活动范围」）
  let walk = 0;
  for (const p of prims) {
    if (p.style !== 'deck' && p.style !== 'stair') continue;
    if (p.kind === 'box' || p.kind === 'plane') walk += (p.size[0] * (p.size[1] || p.size[0]));
    else if (p.kind === 'cylinder') walk += Math.PI * p.r * p.r;
  }
  const out = {
    ...src,
    prims,
    _bbox: [x0, y0, x1, y1],
    _top: top,
    _low: low,
    _stats: {
      span: [x1 - x0, y1 - y0],
      walkArea: Math.round(walk),
      homeRatio: +(walk / 180).toFixed(1),
      prims: prims.length,
    },
  };
  fs.writeFileSync(path.join(RESOLVED, `${id}.json`), JSON.stringify(out, null, 1), 'utf8');
  console.log(`[expand] ${id} · ${src.title || ''} · ${prims.length} 体块 · 走人面 ${Math.round(walk)}㎡（家的 ${(walk / 180).toFixed(1)} 倍）`);
}

const arg = process.argv[2] || 'all';
fs.mkdirSync(RESOLVED, { recursive: true });
const ids = fs.readdirSync(LAYOUTS).filter((f) => f.endsWith('.json')).map((f) => f.slice(0, -5)).sort();
for (const id of (arg === 'all' ? ids : arg.split(','))) {
  if (!ids.includes(id)) { console.log(`[expand] 没有这个布局：${id}`); continue; }
  run(id);
}
