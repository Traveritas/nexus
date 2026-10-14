/* 浅梦样板 · 俯视标注地图：resolved/*.json → plans/*.png
   用 Chrome 无界面把一张 SVG 平面图截成 PNG：体块按 style 上色、区域名、出入口记号、
   出生点、比例尺、指北、图例、尺度统计（含「是家的几倍」）。
   画布按内容长宽比自适应（北永远朝上），世界长就往长的方向铺。

   node mockup/shallows-01/tools/maps.cjs all
   node mockup/shallows-01/tools/maps.cjs arcade
*/
const fs = require('fs');
const path = require('path');
const os = require('os');
const puppeteer = require(path.join(os.tmpdir(), 'node_modules', 'puppeteer-core'));

const MOCK = process.env.MOCK_DIR || path.join(__dirname, '..');
const RESOLVED = path.join(MOCK, 'resolved');
const PLANS = path.join(MOCK, 'plans');

const C = {
  ground: '#f2eff7', groundEdge: '#cfc7dd', ink: '#241f38', dim: '#6b6480',
  deck: '#e6e2ee', stair: '#d2cbe1', wall: '#cdc8db', mass: '#a49cbc',
  frame: '#8b82a6', rail: '#ffffff', water: '#c3d1e6', glass: '#dce7f5',
  plant: '#93c0b0', prop: '#d9aab5', void: '#2a2740',
};
const LAYER = ['water', 'deck', 'stair', 'void', 'mass', 'wall', 'glass', 'rail', 'prop', 'frame', 'plant'];
const EDGE = { deck: '#cbc3da', stair: '#bfb6d2' };
const LEGEND = [['deck', '走人的面'], ['stair', '台阶'], ['wall', '墙'], ['mass', '体量'],
  ['frame', '框'], ['rail', '栏/道牙'], ['water', '水'], ['glass', '玻璃'],
  ['prop', '器物'], ['plant', '草木'], ['void', '洞']];
const PORTAL = {
  home: { color: '#d07f96', kind: '回家的灯' }, world: { color: '#7d7398', kind: '世界之间' },
  site: { color: '#5f9c8b', kind: '晶体→站点' }, realm: { color: '#c9a94e', kind: '跨主域' },
  dead: { color: '#6e4f66', kind: '死胡同' },
};

const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const f1 = (v) => (Math.round(v * 10) / 10).toString();
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

function primSvg(p, T) {
  const fill = C[p.style] || C.deck;
  const edge = EDGE[p.style];
  const at = p.at;
  // 描边不随缩放（矩形画在按米缩放的 transform 里，否则放大的图上边线会变成一条宽带）
  const stroke = edge ? ` stroke="${edge}" stroke-width="0.7" vector-effect="non-scaling-stroke"` : '';
  if (p.kind === 'box' || p.kind === 'plane') {
    const s = p.size || [1, 1, 0.3], sx = s[0], sy = s[1] || s[0];
    const [px, py] = T.pt(at[0], at[1]);
    // plan: "ghost" ＝ 头顶上的东西（门楣、天花板上的家具），地图上画得很淡，不挡住下面的门洞
    const op = p.plan === 'ghost' ? 0.22 : p.style === 'water' ? 0.9 : p.style === 'glass' ? 0.85 : 1;
    return `<rect x="${-sx / 2}" y="${-sy / 2}" width="${sx}" height="${sy}" fill="${fill}" fill-opacity="${op}"${stroke} transform="${T.mat(px, py, p.rot || 0)}"/>`;
  }
  if (p.kind === 'cylinder') {
    const [px, py] = T.pt(at[0], at[1]);
    return `<circle cx="${f1(px)}" cy="${f1(py)}" r="${f1((p.r || 1) * T.s)}" fill="${fill}"${stroke}/>`;
  }
  if (p.kind === 'torus') {
    const [px, py] = T.pt(at[0], at[1]);
    return `<circle cx="${f1(px)}" cy="${f1(py)}" r="${f1((p.major || 3) * T.s)}" fill="none" stroke="${fill}" stroke-width="${f1(Math.max(1.2, (p.minor || 0.2) * 2 * T.s))}"/>`;
  }
  if (p.kind === 'sprite') {
    const [px, py] = T.pt(at[0], at[1]);
    const r = clamp((p.style === 'plant' ? 0.62 : 0.4) * T.s, 2.6, 10);
    return `<circle cx="${f1(px)}" cy="${f1(py)}" r="${f1(r)}" fill="${C[p.style] || C.plant}" fill-opacity="0.85" stroke="#7d7594" stroke-width="0.6"/>`;
  }
  return '';
}

function buildHtml(d) {
  const W = 1780, PAD = 46, sideW = 430, headH = 140;
  const [x0, y0, x1, y1] = d._bbox;
  const mw = Math.max(1, x1 - x0), mh = Math.max(1, y1 - y0);
  const mapW = W - PAD * 2 - sideW;
  const mapH = Math.round(clamp((mapW * mh) / mw, 520, 1800));
  const H = Math.round(headH + PAD + mapH + PAD);
  const s = Math.min((mapW * 0.94) / mw, (mapH * 0.94) / mh);
  const vx = PAD, vy = headH;
  const px0 = vx + (mapW - mw * s) / 2, py0 = vy + (mapH - mh * s) / 2;
  const T = {
    s,
    pt: (x, y) => [px0 + (x - x0) * s, py0 + (y1 - y) * s],
    mat: (px, py, rot) => { const a = (rot * Math.PI) / 180, c = Math.cos(a), sn = Math.sin(a); return `matrix(${f1(c * s)},${f1(-sn * s)},${f1(-sn * s)},${f1(-c * s)},${f1(px)},${f1(py)})`; },
  };
  const ext = d.extent || 200;
  const [gx0, gy0] = T.pt(-ext / 2, ext / 2);
  const extRect = `<rect x="${f1(gx0)}" y="${f1(gy0)}" width="${f1(ext * s)}" height="${f1(ext * s)}" fill="none" stroke="${C.groundEdge}" stroke-width="1.3" stroke-dasharray="4 5"/>`;

  // 体块（按层从下往上）
  const body = [...d.prims].sort((a, b) => LAYER.indexOf(a.style) - LAYER.indexOf(b.style)).map((p) => primSvg(p, T)).join('\n');

  // 标签避让
  const boxes = [];
  const free = (b) => !boxes.some((o) => !(b[0] > o[2] || b[2] < o[0] || b[1] > o[3] || b[3] < o[1]));
  const put = (b) => { boxes.push(b); };
  const CAND = [[0, -18], [0, 20], [0, -34], [0, 36], [0, -50], [0, 52]];
  function place(txt, px, py, fs, color, weight, above) {
    const w = txt.length * fs * 0.98 + 10, h = fs + 4;
    const cands = above ? [...CAND].reverse() : CAND;
    for (const [dx, dy] of cands) {
      const b = [px + dx - w / 2, py + dy - h, px + dx + w / 2, py + dy];
      if (free(b)) { put(b); return `<text x="${f1(px + dx)}" y="${f1(py + dy - 3)}" text-anchor="middle" font-size="${fs}" font-weight="${weight}" fill="${color}" style="paint-order:stroke" stroke="#fff" stroke-width="${fs * 0.28}">${esc(txt)}</text>`; }
    }
    const b = [px - w / 2, py + 20 - h, px + w / 2, py + 20];
    put(b);
    return `<text x="${f1(px)}" y="${f1(py + 17)}" text-anchor="middle" font-size="${fs}" font-weight="${weight}" fill="${color}" style="paint-order:stroke" stroke="#fff" stroke-width="${fs * 0.28}">${esc(txt)}</text>`;
  }

  // 区域名
  let labels = '';
  for (const r of d.regions || []) {
    const [px, py] = T.pt(r.at[0], r.at[1]);
    if (r.shape === 'circle') {
      labels += `<circle cx="${f1(px)}" cy="${f1(py)}" r="${f1(r.r * s)}" fill="none" stroke="#9a91b2" stroke-width="1.4" stroke-dasharray="7 6"/>`;
    } else {
      const sz = r.size || [10, 10];
      labels += `<rect x="${f1(px - (sz[0] / 2) * s)}" y="${f1(py - (sz[1] / 2) * s)}" width="${f1(sz[0] * s)}" height="${f1(sz[1] * s)}" fill="none" stroke="#9a91b2" stroke-width="1.4" stroke-dasharray="7 6"/>`;
    }
  }
  for (const r of d.regions || []) {
    const la = r.label_at || r.at; // label_at：标签放别处（同心的几圈不叠在一起）
    const [px, py] = T.pt(la[0], la[1]);
    labels += place(r.label, px, py, 15.5, '#4b4363', 700);
  }
  for (const p of d.prims) {
    if (!p.label) continue;
    const [px, py] = T.pt(p.at[0], p.at[1]);
    labels += place(p.label, px, py, 13, '#3d3752', 400);
  }

  // 出入口
  let ports = '', plist = '';
  for (const po of d.portals || []) {
    const k = po.kind || 'world', col = (PORTAL[k] || PORTAL.world).color;
    const [px, py] = T.pt(po.at[0], po.at[1]);
    const sz = 10;
    if (k === 'home') ports += `<circle cx="${px}" cy="${py}" r="${sz}" fill="${col}" stroke="#fff" stroke-width="2.6"/><circle cx="${px}" cy="${py}" r="${sz * 0.34}" fill="#fff"/>`;
    else if (k === 'site') ports += `<path d="M${px} ${py - sz} L${px + sz} ${py} L${px} ${py + sz} L${px - sz} ${py} Z" fill="${col}" stroke="#fff" stroke-width="2.4"/>`;
    else if (k === 'realm') ports += `<rect x="${px - sz * 0.85}" y="${py - sz * 0.85}" width="${sz * 1.7}" height="${sz * 1.7}" fill="${col}" stroke="#fff" stroke-width="2.4"/>`;
    else if (k === 'dead') ports += `<circle cx="${px}" cy="${py}" r="${sz}" fill="#fff" stroke="${col}" stroke-width="2.8"/>`;
    else ports += `<path d="M${px} ${py - sz} L${px + sz} ${py + sz * 0.78} L${px - sz} ${py + sz * 0.78} Z" fill="${col}" stroke="#fff" stroke-width="2.4"/>`;
    put([px - sz - 2, py - sz - 2, px + sz + 2, py + sz + 2]);

    const label = po.label || (k === 'home' ? '→ 家' : k === 'site' ? '→ 站点' : `→ ${po.to || ''}`);
    const sub = po.note || (po.title ? `E · ${po.title}` : '');
    ports += place(label, px, py, 15, col, 700);
    if (sub) ports += place(sub, px, py + 20, 11.5, '#6b6480', 400, true);
    plist += `<div class="pl"><i style="background:${col}"></i><b>${esc(label)}</b><span>${esc((PORTAL[k] || PORTAL.world).kind)}${sub ? ' · ' + esc(sub) : ''}</span></div>`;
  }

  // 出生点
  const sp = d.spawn && d.spawn.at;
  let spawnSvg = '';
  if (sp) {
    const [px, py] = T.pt(sp[0], sp[1]);
    spawnSvg = `<path d="M${px} ${py - 11} L${px + 10} ${py + 8} L${px} ${py + 3.5} L${px - 10} ${py + 8} Z" fill="#fff" stroke="${C.ink}" stroke-width="2.2"/>`
      + place('出生', px, py, 13, C.ink, 700, true);
  }

  // 比例尺
  const barM = [1, 2, 5, 10, 20, 50, 100].find((v) => v * s > 110) || 100;
  const bp = barM * s, bx = vx + 24, by = vy + mapH - 22;
  const scaleBar = `<g><rect x="${f1(bx - 10)}" y="${f1(by - 30)}" width="${f1(bp + 20)}" height="42" fill="#fff" fill-opacity="0.82" rx="4"/>
    <line x1="${bx}" y1="${by}" x2="${f1(bx + bp)}" y2="${by}" stroke="${C.ink}" stroke-width="3"/>
    <line x1="${bx}" y1="${by - 7}" x2="${bx}" y2="${by + 7}" stroke="${C.ink}" stroke-width="3"/>
    <line x1="${f1(bx + bp)}" y1="${by - 7}" x2="${f1(bx + bp)}" y2="${by + 7}" stroke="${C.ink}" stroke-width="3"/>
    <text x="${f1(bx + bp / 2)}" y="${by - 10}" text-anchor="middle" font-size="14" fill="${C.ink}">${barM} m</text></g>`;

  const st = d._stats || {};
  const stat = (k, v) => `<div class="st"><span>${esc(k)}</span><b>${esc(v)}</b></div>`;
  const levels = (d.levels || []).map((l) => `${esc(l.label)} <i>z=${f1(l.z)}m</i>`).join('　');

  return `<!doctype html><html><head><meta charset="utf-8"><style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{width:${W}px;height:${H}px;background:#fbf9f7;font-family:"Microsoft YaHei","Noto Sans SC",system-ui,sans-serif;color:${C.ink};position:relative;overflow:hidden}
  .frame{position:absolute;inset:20px;border:1.6px solid #ded7e8;border-radius:10px}
  header{position:absolute;left:46px;top:34px;right:${sideW + 46}px;z-index:3}
  h1{font-size:38px;letter-spacing:2px;display:inline-block;margin-right:16px}
  .en{font-size:16px;color:${C.dim};letter-spacing:3px;text-transform:uppercase}
  .role{margin-top:9px;font-size:15px;color:#4b4363;line-height:1.5}
  aside{position:absolute;right:46px;top:${headH + 6}px;width:${sideW - 24}px;z-index:3;background:#fbf9f7;padding-left:16px;border-left:1px solid #ece6f3}
  h2{font-size:12.5px;letter-spacing:2px;color:${C.dim};margin:16px 0 7px;border-bottom:1px solid #e6dff0;padding-bottom:5px}
  h2:first-child{margin-top:0}
  .st{display:flex;justify-content:space-between;font-size:13.5px;padding:3px 0;color:#4b4363}
  .st b{font-weight:700}
  .pl{display:flex;gap:8px;align-items:flex-start;font-size:13px;padding:4px 0;line-height:1.35}
  .pl i{width:11px;height:11px;border-radius:3px;margin-top:3px;flex:none}
  .pl b{flex:none;min-width:60px}
  .pl span{color:${C.dim};font-size:12px}
  .lg{display:flex;flex-wrap:wrap;gap:4px 12px;font-size:12.5px;color:#4b4363}
  .lg div{display:flex;align-items:center;gap:5px}
  .lg i{width:13px;height:13px;border-radius:3px;border:1px solid #d9d2e6}
  .notes{font-size:12.5px;color:#5c5573;line-height:1.65;padding-left:15px}
  .notes li{margin-bottom:4px}
  .lv{font-size:12.5px;color:#4b4363;line-height:1.7}.lv i{color:${C.dim};font-style:normal}
  .north{position:absolute;left:46px;bottom:26px;font-size:13px;color:${C.dim};z-index:3}
  </style></head><body>
  <div class="frame"></div>
  <svg width="${W}" height="${H}" style="position:absolute;left:0;top:0;z-index:1">
    <defs><clipPath id="vp"><rect x="${vx}" y="${vy}" width="${mapW}" height="${mapH}"/></clipPath></defs>
    <rect x="${vx}" y="${vy}" width="${mapW}" height="${mapH}" fill="${C.ground}" stroke="${C.groundEdge}" stroke-width="1.4"/>
    <g clip-path="url(#vp)">${extRect}${body}${labels}${spawnSvg}${ports}${scaleBar}</g>
  </svg>
  <header><div><h1>${esc(d.title)}</h1><span class="en">${esc(d.en || d.id)}</span>
  <div class="role">${esc(d.role || '')}</div></div></header>
  <aside>
    <h2>尺度</h2>
    ${stat('地面底板', ext + ' × ' + ext + ' m')}
    ${stat('内容范围', f1(mw) + ' × ' + f1(mh) + ' m')}
    ${stat('走人面（估计）', (st.walkArea || 0) + ' ㎡')}
    ${stat('≈ 梦里的家', (st.homeRatio || 0) + ' 倍（家 180 ㎡）')}
    ${stat('最高处', f1(d._top || 0) + ' m')}
    ${(d._low || 0) < -0.5 ? stat('最深处', f1(d._low) + ' m') : ''}
    ${stat('体块数', (st.prims || d.prims.length) + '')}
    <h2>分层</h2><div class="lv">${levels || '单层'}</div>
    <h2>出入口（${(d.portals || []).length}）</h2>${plist}
    <h2>图例</h2><div class="lg">${LEGEND.map(([k, t]) => `<div><i style="background:${C[k]}"></i>${t}</div>`).join('')}</div>
    ${(d.notes || []).length ? `<h2>设计说明</h2><ul class="notes">${d.notes.map((n) => `<li>${esc(n)}</li>`).join('')}</ul>` : ''}
  </aside>
  <div class="north">▲ 北（+Y）　·　${esc(d.id)} · 浅梦 Shallows · 样板 ${esc(path.basename(MOCK))}</div>
  </body></html>`;
}

(async () => {
  const arg = process.argv[2] || 'all';
  fs.mkdirSync(PLANS, { recursive: true });
  const ids = fs.readdirSync(RESOLVED).filter((f) => f.endsWith('.json')).map((f) => f.slice(0, -5)).sort();
  const want = arg === 'all' ? ids : arg.split(',');
  const browser = await puppeteer.launch({
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: 'new',
  });
  const page = await browser.newPage();
  for (const id of want) {
    if (!ids.includes(id)) { console.log(`[maps] 没有这个布局：${id}`); continue; }
    const d = JSON.parse(fs.readFileSync(path.join(RESOLVED, `${id}.json`), 'utf8'));
    const html = buildHtml(d);
    const m = html.match(/body\{width:(\d+)px;height:(\d+)px/);
    await page.setViewport({ width: +m[1], height: +m[2], deviceScaleFactor: 2 });
    await page.setContent(html, { waitUntil: 'load' });
    await new Promise((r) => setTimeout(r, 260));
    await page.screenshot({ path: path.join(PLANS, `${id}.png`) });
    console.log(`[maps] ${id}.png  ${m[1]}×${m[2]}`);
  }
  await browser.close();
})().catch((e) => { console.error('[maps] FAIL', e.message); process.exit(1); });
