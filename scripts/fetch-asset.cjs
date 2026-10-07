/* 从 Poly Haven（CC0）取模型：glTF + 贴图，存到 assets/polyhaven/<id>/。
   node scripts/fetch-asset.cjs <id> [分辨率 1k|2k]     例：node scripts/fetch-asset.cjs WoodenChair_01
   node scripts/fetch-asset.cjs --list [关键词]           列出可用的模型 id
   场景里用 blender/nx.py 的 asset() 导入（会只留底色贴图、缩小到 512，导出时嵌进场景的 GLB）。 */
const fs = require('fs');
const path = require('path');

const API = 'https://api.polyhaven.com';
const ROOT = path.join(__dirname, '..', 'assets', 'polyhaven');

async function json(url) {
  const r = await fetch(url, { headers: { 'User-Agent': 'nexus-fetch-asset' } });
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json();
}

async function download(url, out) {
  if (fs.existsSync(out)) return;
  const r = await fetch(url, { headers: { 'User-Agent': 'nexus-fetch-asset' } });
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  fs.mkdirSync(path.dirname(out), { recursive: true });
  fs.writeFileSync(out, Buffer.from(await r.arrayBuffer()));
}

(async () => {
  const [id, res = '1k'] = process.argv.slice(2);
  if (!id) {
    console.log('用法：node scripts/fetch-asset.cjs <id> [1k|2k]  ·  --list [关键词]');
    process.exit(1);
  }
  if (id === '--list') {
    const all = await json(`${API}/assets?t=models`);
    const kw = (res === '1k' ? '' : res).toLowerCase();
    console.log(Object.keys(all).filter((k) => k.toLowerCase().includes(kw)).join('\n'));
    return;
  }
  const files = await json(`${API}/files/${id}`);
  const g = files.gltf?.[res]?.gltf;
  if (!g) throw new Error(`${id} 没有 ${res} 的 glTF`);
  const dir = path.join(ROOT, id);
  await download(g.url, path.join(dir, path.basename(new URL(g.url).pathname)));
  for (const [rel, f] of Object.entries(g.include || {})) await download(f.url, path.join(dir, rel));
  const info = await json(`${API}/info/${id}`);
  fs.writeFileSync(path.join(dir, 'LICENSE.txt'),
    `${info.name}\nPoly Haven · CC0\nhttps://polyhaven.com/a/${id}\n作者：${Object.keys(info.authors || {}).join(', ')}\n`);
  console.log('[asset]', id, '→', dir);
})().catch((e) => {
  console.error(e.message);
  process.exit(1);
});
