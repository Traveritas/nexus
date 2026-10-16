/* 一片夜（地图）：从一大块夜空上崩下来的一片——细长、两头尖，一边是贝壳状的弧形断口，一边是笔直的断边，很薄。
   · 面：里面是夜。星不贴在面上，而在它后面很远的地方：每颗星有一个世界里的方向，透过碎片这扇窗看过去，
     碎片在手里晃、换角度，星不跟着动；转身时星从一头滑进来、从另一头滑出去。这扇窗把四周一圈压进了碎片的宽度里
     （正前方在中间，身后的在两头），高低按碎片的高度压扁。星按管线的格子画（shared.uCellPx），和世界的格子对齐。
       出入口的星同地图：站点金（菱形）、去过的白（十字）、没去过的淡紫（一格）、通往别的主域的冷绿（十字），偶尔亮一下；
       底下一层背景星：一格、最暗的几色，世界里固定的方向，按世界名撒，每个世界的夜不一样，偶尔有一颗灭一会儿。
   · 断边：接住这个世界的光（器物材质，三档受光），一两格宽的一道亮棱，手一晃就沿着边滑过去。
   用（按住 Q，过了短按的时间窗）：碎片转正、对着人，开始发抖，越抖越厉害；面上一条条长出亮的裂纹（星光从缝里漏出来），
     每多一条，抖动停一下、碎片一胀。用到底：停一拍（裂纹发白），然后「啪」地沿裂纹错开，变成激活的样子——
     六片偏宽的三角乱叠在一起（一条边朝外、顶点朝里，前后错开一点），外轮廓是它们的并，摆在一片近乎圆的范围里，是一圈有错台的折线、没有尖往外戳；
     上面那片的侧边压在下面那片的面上，接光成一道道交错的亮线，像几层碎晶片叠着。
     摆开时像弹簧一样冲过头一点再回来；激活着时每片主要沿外边来回滑、朝外进出一点、稍微转、胀缩，轮廓一直在变。地图从手边暗下去（见 src/mapview.ts）。
   激活着时再按住 Q（先松开过）：几片往中间收、越抖越厉害；用到底时停一拍，很快合回一整片，一胀，地图收起。
     地图被别的原因收起（换世界）时也自己合上。用到底一次以后要先松开，按着也不长裂纹、不抖。
   id 仍是 compass（存档、场景里的 nx.item 都这么叫）。 */
import * as THREE from 'three';
import { PALETTE } from '../palette';
import { OUTS, charm, newId, pal, shared } from '../materials';
import { scratch } from '../ui';
import type { Exit } from '../mapview';
import type { HeldModel, ItemCtx, ItemDef, Shown } from './item';

const P = (i: number) => PALETTE[i];
type V2 = [number, number];

/** 轮廓（米，xy 平面，正面朝 +z）：上沿是弧形断口，下沿是笔直的断边，两头尖 */
const OUTLINE: V2[] = [
  [-0.15, -0.004],
  [-0.118, 0.016],
  [-0.072, 0.032],
  [-0.02, 0.041],
  [0.026, 0.04],
  [0.07, 0.03],
  [0.112, 0.014],
  [0.152, 0.002],
  [0.098, -0.012],
  [0.036, -0.02],
  [0.012, -0.027],
  [-0.03, -0.022],
  [-0.096, -0.016],
];
const HALF_LEN = 0.15;
const HALF_HT = 0.032;
const THICK = 0.006;
const DECOR = 14;
const MAX_STARS = 32;
/** 裂纹：几条，每条几段 */
const CRACKS = 7;
const SEGS = 3;

const STAR: Record<Exit['kind'], { col: number; r: number }> = {
  site: { col: 14, r: 2 },
  seen: { col: 7, r: 1 },
  cross: { col: 15, r: 1 },
  unseen: { col: 4, r: 0 },
};

function inside(p: V2, poly: V2[]) {
  let c = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    if (yi > p[1] !== yj > p[1] && p[0] < ((xj - xi) * (p[1] - yi)) / (yj - yi) + xi) c = !c;
  }
  return c;
}

/** 一串可复现的随机数 */
function rand(seed: string) {
  let s = 2166136261;
  for (const ch of seed) s = Math.imul(s ^ ch.charCodeAt(0), 16777619);
  return () => {
    s = Math.imul(s ^ (s >>> 15), 2246822507);
    s = Math.imul(s ^ (s >>> 13), 3266489909);
    return ((s ^= s >>> 16) >>> 0) / 4294967296;
  };
}

interface Decor {
  az: number;
  el: number;
  col: number;
  ph: number;
}
/** 背景星：世界里固定的方位、高低（-1..1）、颜色、闪的相位；按世界名撒 */
function decorOf(world: string): Decor[] {
  const r = rand(world);
  return Array.from({ length: DECOR }, () => ({
    az: r() * Math.PI * 2,
    el: r() * 2 - 1,
    col: r() < 0.7 ? 1 : r() < 0.8 ? 2 : 3,
    ph: r() * 100,
  }));
}

/** 裂纹：从偏中间的一点往四周走，每条三段、一路拐；返回线段（按长出来的先后排） */
function cracks(): THREE.Vector4[] {
  const r = rand('night-cracks');
  const from: V2 = [0.012, 0.006];
  const out: THREE.Vector4[] = [];
  for (let k = 0; k < CRACKS; k++) {
    let a = (k / CRACKS) * Math.PI * 2 + (r() - 0.5) * 0.6;
    let p: V2 = [...from];
    for (let s = 0; s < SEGS; s++) {
      a += (r() - 0.5) * 0.9;
      // 碎片细长：横着走得远、竖着走得近
      const len = 0.016 + r() * 0.022;
      let q: V2 = [p[0] + Math.cos(a) * len * 2.2, p[1] + Math.sin(a) * len * 0.55];
      if (!inside(q, OUTLINE)) q = [p[0] + (q[0] - p[0]) * 0.5, p[1] + (q[1] - p[1]) * 0.5];
      out.push(new THREE.Vector4(p[0], p[1], q[0], q[1]));
      p = q;
    }
  }
  return out;
}
const CRACK_SEGS = cracks();

function icon() {
  const { c, g } = scratch(16, 16);
  const put = (x: number, y: number, col: string) => {
    g.fillStyle = col;
    g.fillRect(x, y, 1, 1);
  };
  // 轮廓按 16 格量好、斜一点放；逐格填最暗的一色，上沿那一圈是亮棱
  const k = 15.4 / 0.302;
  const a = -0.35;
  const poly = OUTLINE.map(([x, y]): V2 => {
    const xr = x * Math.cos(a) - y * 1.7 * Math.sin(a);
    const yr = x * Math.sin(a) + y * 1.7 * Math.cos(a);
    return [8 + xr * k, 8 - yr * k];
  });
  const at = (x: number, y: number) => inside([x + 0.5, y + 0.5], poly);
  for (let y = 0; y < 16; y++)
    for (let x = 0; x < 16; x++) if (at(x, y)) put(x, y, !at(x, y - 1) || !at(x + 1, y - 1) ? P(4) : P(0));
  // 几颗星：金、雾蓝（白的落在纸上像个洞）、冷绿各一，两颗背景星
  for (const [x, y, col] of [
    [6, 9, 14],
    [9, 8, 13],
    [11, 6, 15],
    [4, 10, 2],
    [8, 7, 2],
  ]) if (at(x, y)) put(x, y, P(col));
  return c;
}

const VERT = /* glsl */ `
in vec3 bary;
out vec2 vLocal;
out vec3 vBary;
out vec3 vNormal;
out float vDepth;
void main() {
  vLocal = position.xy;
  vBary = bary;
  vNormal = normalize(mat3(modelMatrix) * normal);
  vec4 v = modelViewMatrix * vec4(position, 1.0);
  vDepth = -v.z;
  gl_Position = projectionMatrix * v;
}
`;

/** 面：夜、星（屏幕上按格子画）、裂纹（面上按格子画） */
const FRAG = /* glsl */ `
precision highp float;
${OUTS}
uniform vec3 uPal[16];
uniform vec4 uStars[${MAX_STARS}];
uniform int uStarN;
uniform vec4 uCracks[${CRACK_SEGS.length}];
uniform float uCrack, uFlash, uId, uCellPx;
uniform vec2 uViewPx;
in vec2 vLocal; in vec3 vNormal; in float vDepth; in vec3 vBary;
vec2 octEncode(vec3 n) {
  n /= abs(n.x) + abs(n.y) + abs(n.z);
  return n.z >= 0.0 ? n.xy : (1.0 - abs(n.yx)) * vec2(n.x >= 0.0 ? 1.0 : -1.0, n.y >= 0.0 ? 1.0 : -1.0);
}
void main() {
  vec2 cell = floor(gl_FragCoord.xy / uCellPx);
  // 这一格中心落在面上的哪（面是平的，屏幕到面是线性的）
  vec2 dp = (cell + 0.5) * uCellPx - gl_FragCoord.xy;
  vec2 cl = vLocal + dFdx(vLocal) * dp.x + dFdy(vLocal) * dp.y;
  float perCell = max(length(dFdx(vLocal)), length(dFdy(vLocal))) * uCellPx;
  int col = 0;
  // 三角片自己的边（重心坐标离 0 不到一格）：一格宽的淡紫，上面那片的边压在下面那片的面上；碎片本体没有（全是 1）。
  // 只描朝着左上（画面上）的那几条边，像光从一边来：边的朝外方向 ＝ 那个重心分量在屏幕上减小的方向
  vec3 bc = vBary + dFdx(vBary) * dp.x + dFdy(vBary) * dp.y;
  vec3 bw = max(abs(dFdx(vBary)), abs(dFdy(vBary))) * uCellPx;
  vec3 br = bc / max(bw, vec3(1e-6));
  int k = br.x < br.y ? (br.x < br.z ? 0 : 2) : (br.y < br.z ? 1 : 2);
  vec2 grad = vec2(dFdx(vBary)[k], dFdy(vBary)[k]);
  if (br[k] < 1.0 && dot(-grad, vec2(-0.6, 0.8)) > 0.3 * length(grad)) col = 5;
  for (int i = 0; i < ${MAX_STARS}; i++) {
    if (i >= uStarN) break;
    vec4 s = uStars[i];
    vec2 sc = floor((s.xy * 0.5 + 0.5) * uViewPx / uCellPx);
    vec2 dd = abs(cell - sc);
    if (dd.x + dd.y <= s.z) col = int(s.w);
  }
  // 裂纹：长到第几段（小数＝最后一段长了几成）；一格宽、雾蓝，像星光从缝里漏出来
  for (int i = 0; i < ${CRACK_SEGS.length}; i++) {
    float f = clamp(uCrack - float(i), 0.0, 1.0);
    if (f <= 0.0) break;
    vec2 a = uCracks[i].xy, b = mix(a, uCracks[i].zw, f), e = b - a, w = cl - a;
    float d = length(w - e * clamp(dot(w, e) / max(dot(e, e), 1e-9), 0.0, 1.0));
    if (d < perCell * (0.5 + 0.5 * uFlash)) col = uFlash > 0.5 ? 7 : 13;
  }
  oColor = vec4(uPal[col], 1.0);
  oData = vec4(octEncode(normalize(vNormal)), vDepth, uId);
}
`;

const o = new THREE.Vector3();
const c = new THREE.Vector3();
const tmp = new THREE.Vector3();
const wrap = (a: number) => Math.atan2(Math.sin(a), Math.cos(a));

/** 夜的面：一份材质，碎片和飞出去的碎屑共用（星、裂纹都一样） */
function nightMat(id: number) {
  return new THREE.ShaderMaterial({
    glslVersion: THREE.GLSL3,
    side: THREE.DoubleSide,
    uniforms: {
      uPal: { value: PALETTE.map((_, i) => pal(i)) },
      uStars: { value: Array.from({ length: MAX_STARS }, () => new THREE.Vector4()) },
      uStarN: { value: 0 },
      uCracks: { value: CRACK_SEGS },
      uCrack: { value: 0 },
      /** 碎之前停的那一拍：裂纹发白、变粗 */
      uFlash: { value: 0 },
      uId: { value: id },
      uCellPx: shared.uCellPx,
      uViewPx: shared.uViewPx,
    },
    vertexShader: VERT,
    fragmentShader: FRAG,
  });
}

/** 把星摆进这扇窗：每颗星给一个世界里的方向，按透过碎片看过去的样子换成画面上的点（NDC） */
function layStars(mat: THREE.ShaderMaterial, center: THREE.Vector3, scale: number, ctx: ItemCtx, decor: Decor[], bright: number, tall = 1) {
  const cam = ctx.camera;
  c.copy(center).sub(ctx.eye);
  const dist = Math.max(0.05, c.length());
  const azC = Math.atan2(c.x, -c.z);
  const elC = Math.asin(THREE.MathUtils.clamp(c.y / dist, -1, 1));
  // 四周一圈压进碎片的宽度：K 倍；高低压进碎片的高度
  const halfW = (HALF_LEN * scale) / dist;
  const halfH = (HALF_HT * scale * tall) / dist;
  const K = Math.PI / (halfW * 0.92);
  const stars = mat.uniforms.uStars.value as THREE.Vector4[];
  let n = 0;
  const put = (az: number, el: number, r: number, col: number) => {
    if (n >= MAX_STARS) return;
    const a = azC + wrap(az - azC) / K;
    const e = elC + el * halfH * 0.5;
    tmp.set(Math.sin(a) * Math.cos(e), Math.sin(e), -Math.cos(a) * Math.cos(e)).multiplyScalar(10).add(ctx.eye).project(cam);
    if (tmp.z < 1) stars[n++].set(tmp.x, tmp.y, r, col);
  };
  // 背景星先放，出入口的星后放（重叠时盖在上面）
  for (const s of decor) if (Math.sin(ctx.t * 0.45 + s.ph) < 0.93) put(s.az, s.el, 0, s.col);
  ctx.exits.forEach((x, i) => {
    tmp.copy(x.pos).sub(ctx.eye);
    const el = Math.atan2(tmp.y, Math.hypot(tmp.x, tmp.z)) / (Math.PI / 2);
    const s = STAR[x.kind];
    const tw = Math.sin(ctx.t * 1.7 + i * 2.9) > 0.97 ? 1 : 0;
    put(Math.atan2(tmp.x, -tmp.z), THREE.MathUtils.clamp(el * 2.5, -1, 1), s.r + tw + bright, s.col);
  });
  mat.uniforms.uStarN.value = n;
}

/** 给面加上重心坐标（bary）：三角片的正反两面按三个角给 (1,0,0)/(0,1,0)/(0,0,1)，着色器据此描自己的边；
    别的（碎片本体、侧边）全给 1，不描 */
function withEdges(geo: THREE.BufferGeometry, tri?: number[][]) {
  const pos = geo.getAttribute('position');
  const bary = new Float32Array(pos.count * 3).fill(1);
  if (tri) {
    const caps = geo.groups.find((g) => g.materialIndex === 0);
    for (let i = caps?.start ?? 0; caps && i < caps.start + caps.count; i++) {
      const j = tri.findIndex(([x, y]) => Math.abs(pos.getX(i) - x) < 1e-5 && Math.abs(pos.getY(i) - y) < 1e-5);
      if (j < 0) continue;
      bary.fill(0, i * 3, i * 3 + 3);
      bary[i * 3 + j] = 1;
    }
  }
  geo.setAttribute('bary', new THREE.BufferAttribute(bary, 3));
  return geo;
}

/** 碎片本体（米；原点在中心）：夜的面 + 接光的断边 */
function shard(id: number) {
  const face = nightMat(id);
  const rim = charm([2, 4, 6], id);
  const shape = new THREE.Shape(OUTLINE.map(([x, y]) => new THREE.Vector2(x, y)));
  const geo = withEdges(new THREE.ExtrudeGeometry(shape, { depth: THICK, bevelEnabled: false }).translate(0, 0, -THICK / 2));
  // ExtrudeGeometry 的第 0 组是正反两面，第 1 组是侧边
  const mesh = new THREE.Mesh(geo, [face, rim]);
  mesh.userData.noShadow = true;
  return { mesh, face, rim };
}

/** 激活时的样子：六片偏宽的三角乱叠在一起，外轮廓是它们的并——每片一条边朝外（大致贴着一个近乎圆的外圈，各自斜一点、远近不一），
    第三个顶点指向中心或越过中心，所以外轮廓是一圈有错台、小凹口的折线，没有尖往外戳。
    几片前后错开一点（同一个编号），上面那片的侧边压在下面那片的面上，接光成一道道交错的亮线，像几层碎晶片叠着 */
const TRIS: { pts: [V2, V2, V2]; ph: number; a: number; z: number }[] = (
  // 每片：外边朝哪（弧度）、外边离中心多远、外边多长、顶点越过中心多远、顶点往一侧偏多少、外边斜多少（弧度）、动的相位
  [
    [0.2, 0.14, 0.2, 0.03, 0.02, 0.15, 0.3],
    [1.25, 0.128, 0.18, 0.05, -0.03, -0.2, 1.9],
    [2.15, 0.145, 0.21, 0.02, 0.01, 0.1, 3.4],
    [3.2, 0.134, 0.19, 0.04, 0.03, -0.12, 4.8],
    [4.2, 0.14, 0.2, 0.035, -0.02, 0.18, 0.9],
    [5.25, 0.124, 0.17, 0.05, 0, -0.1, 2.6],
  ] as const
).map(([a, R, chord, deep, shift, skew, ph], i) => {
  const out: V2 = [Math.cos(a), Math.sin(a)];
  // 外边的方向：切线再斜一点
  const ta = a + Math.PI / 2 + skew;
  const tan: V2 = [Math.cos(ta), Math.sin(ta)];
  const m: V2 = [out[0] * R, out[1] * R];
  const pts: [V2, V2, V2] = [
    [m[0] + (tan[0] * chord) / 2, m[1] + (tan[1] * chord) / 2],
    [m[0] - (tan[0] * chord) / 2, m[1] - (tan[1] * chord) / 2],
    [-out[0] * deep - out[1] * shift, -out[1] * deep + out[0] * shift],
  ];
  // 前后错开：按一个打乱的次序，每层 2.5mm
  return { pts, ph, a, z: ([2, 5, 0, 3, 1, 4][i] - 2.5) * 0.0025 };
});
/** 激活时星的窗口：比碎片宽几倍、高几倍 */
const ACTIVE_WIDE = 1.0;
const ACTIVE_TALL = 3.4;
/** 激活时整簇缩放（三角表按这个尺寸的 1/0.82 写的） */
const CLUSTER = 0.82;

interface Tri {
  g: THREE.Group;
  ph: number;
  /** 三角形自己的中心（摆出来、收回去都朝着它走） */
  c: THREE.Vector2;
  /** 外边朝外的方向、沿外边的方向：动的时候主要沿外边滑，朝外只挪一点 */
  out: THREE.Vector2;
  tan: THREE.Vector2;
  z: number;
}

function tris(face: THREE.ShaderMaterial, rim: THREE.ShaderMaterial): Tri[] {
  return TRIS.map(({ pts, ph, a, z }) => {
    const c = new THREE.Vector2((pts[0][0] + pts[1][0] + pts[2][0]) / 3, (pts[0][1] + pts[1][1] + pts[2][1]) / 3);
    // 顶点相对自己的中心：绕中心转、缩
    const shape = new THREE.Shape(pts.map(([x, y]) => new THREE.Vector2(x - c.x, y - c.y)));
    const geo = withEdges(new THREE.ExtrudeGeometry(shape, { depth: THICK, bevelEnabled: false }).translate(0, 0, -THICK / 2), pts.map(([x, y]) => [x - c.x, y - c.y]));
    const m = new THREE.Mesh(geo, [face, rim]);
    m.frustumCulled = false;
    const g = new THREE.Group();
    g.add(m);
    g.visible = false;
    const out = new THREE.Vector2(Math.cos(a), Math.sin(a));
    return { g, ph, c, out, tan: new THREE.Vector2(-out.y, out.x), z };
  });
}

/** 在世界里、环绕展示时：浮在原点上方一点，慢慢转着 */
function world(): Shown {
  const object = new THREE.Group();
  const { mesh, face } = shard(newId());
  const root = new THREE.Group();
  root.add(mesh);
  // 世界里放大：远了碎片只剩几格高
  root.scale.setScalar(1.6);
  root.position.y = 0.32;
  root.rotation.set(0, 0, 0.12);
  object.add(root);
  let decor: Decor[] = [];
  let decorFor = '';
  return {
    object,
    update(dt, ctx) {
      root.position.y = 0.32 + Math.sin(ctx.t * 1.6) * 0.02;
      // 绕竖轴慢慢晃，不整圈转（侧对着时只剩一道亮边）
      root.rotation.y = Math.sin(ctx.t * 0.5) * 0.7;
      if (decorFor !== ctx.world) decor = decorOf((decorFor = ctx.world));
      root.getWorldPosition(o);
      layStars(face, o, root.getWorldScale(tmp).x, ctx, decor, 0);
    },
  };
}

/** 停一拍（秒）：变之前、每长出一条裂纹 */
const HITCH_BREAK = 0.07;
const HITCH_CRACK = 0.05;
/** 散开：弹簧的劲与阻尼（会冲过头一点再回来）；合上要多久 */
const SPRING = 220;
const DAMP = 15;
const CLOSE_TIME = 0.16;

function held(): HeldModel {
  const object = new THREE.Group();
  const id = newId();
  const { mesh, face, rim } = shard(id);
  const body = new THREE.Group();
  body.add(mesh);
  object.add(body);
  const cluster = new THREE.Group();
  // 激活时的几片侧边亮一档：地图暗下来以后，叠着的那几道亮线还看得见
  const parts = tris(face, charm([3, 5, 7], id));
  for (const p of parts) cluster.add(p.g);
  object.add(cluster);

  let decor: Decor[] = [];
  let decorFor = '';
  /** whole 一整片 · active 激活（几片三角叠着，地图开着）· closing 正合回去 */
  let state: 'whole' | 'active' | 'closing' = 'whole';
  let sawOpen = false;
  let hitch = 0;
  let pending = false;
  let lastCrack = 0;
  let pop = 0;
  let flash = 0;
  let face0 = 0;
  /** 散开的程度（弹簧）：0 收在中间 · 1 摆开 */
  let sp = 0;
  let spV = 0;
  let closeT = 0;
  /** 用到底一次以后，要先松开（press 落回去）才能再触发下一次 */
  let armed = true;

  const activate = () => {
    state = 'active';
    sawOpen = false;
    body.visible = false;
    for (const p of parts) p.g.visible = true;
    face.uniforms.uCrack.value = 0;
    sp = 0;
    // 一踢：猛地摆开、冲过头再回来
    spV = 9;
  };
  const close = () => {
    state = 'closing';
    closeT = 0;
  };
  const shake = (amp: number) => new THREE.Vector3((Math.random() - 0.5) * amp, (Math.random() - 0.5) * amp, 0);

  return {
    object,
    update(dt, press, ctx) {
      let hit = false;
      if (decorFor !== ctx.world) decor = decorOf((decorFor = ctx.world));
      if (ctx.mapOpen) sawOpen = true;
      if (press < 0.3) armed = true;
      // 用到底一次以后、松开以前：按着也不算（不长裂纹、不抖）
      const e = armed ? press * press * (3 - 2 * press) : 0;
      const t = ctx.t;

      // 停一拍：不抖、不长，到点了再变
      if (hitch > 0) {
        hitch -= dt;
        if (hitch <= 0 && pending) {
          pending = false;
          hit = true;
          if (state === 'whole') activate();
          else close();
        }
      }
      // 平时斜一点（断边好接光）；用的时候转正、对着人（手边整体是斜着举的，往上仰一点就正了）
      face0 += ((press > 0 && armed ? 1 : 0) - face0) * Math.min(1, dt * 10);
      const rest = (g: THREE.Object3D, sway: number) =>
        g.rotation.set(-0.1 - 0.3 * face0 + sway * 0.4, (0.35 + sway) * (1 - face0), 0.1 * (1 - face0));
      pop = Math.max(0, pop - dt * 8);
      const trigger = () => {
        if (press >= 1 && armed && !pending && hitch <= 0) {
          armed = false;
          pending = true;
          hitch = HITCH_BREAK;
          flash = 1;
        }
      };

      if (state === 'whole') {
        rest(body, 0);
        // 裂纹一条条长出来；每多一条停一下、一胀
        const cr = e * CRACK_SEGS.length;
        const crackNo = Math.floor(cr / SEGS);
        if (crackNo > lastCrack && hitch <= 0) {
          hitch = HITCH_CRACK;
          pop = 1;
        }
        lastCrack = press === 0 ? 0 : crackNo;
        if (hitch <= 0) face.uniforms.uCrack.value = cr;
        body.scale.setScalar(1 + 0.04 * pop + 0.03 * e);
        // 抖：越用越厉害；停一拍时不抖
        body.position.copy(shake(hitch > 0 ? 0 : 0.0006 + 0.004 * e * e));
        trigger();
      } else {
        // 弹簧：激活时往 1 走（冲过头一点）；合上时很快收回 0
        if (state === 'closing') {
          closeT += dt;
          const k = Math.min(1, closeT / CLOSE_TIME);
          sp = (1 - k * k) * Math.min(sp, 1);
          spV = 0;
          if (k >= 1) {
            // 合回一整片：裂纹没了，一胀
            state = 'whole';
            body.visible = true;
            for (const p of parts) p.g.visible = false;
            lastCrack = 0;
            pop = 1;
          }
        } else {
          spV += ((1 - sp) * SPRING - spV * DAMP) * dt;
          sp += spV * dt;
          // 地图被别的原因收起（换世界）：自己合上
          if (sawOpen && !ctx.mapOpen) close();
          else trigger();
        }
        // 按住要合上时：往中间收、越抖越厉害（松开过才算）
        const g = state === 'active' ? e : 1;
        rest(cluster, Math.sin(t * 0.6) * 0.12);
        cluster.position.copy(shake(hitch > 0 ? 0 : 0.003 * g * g));
        cluster.scale.setScalar(CLUSTER * (1 + 0.05 * pop));
        for (const p of parts) {
          // 摆开：从中间往各自的位置走；平时各自沿外边来回滑、朝外进出一点、稍微转、胀缩——像几层碎晶片在彼此身上蹭
          const s = Math.max(0, sp) * (1 - 0.35 * g);
          const slide = Math.sin(t * 0.8 + p.ph) * 0.011 + Math.sin(t * 1.9 + p.ph * 2.1) * 0.003;
          const bob = Math.sin(t * 1.1 + p.ph * 1.7) * 0.004;
          p.g.position.set(
            p.c.x * (0.5 + 0.5 * s) + p.tan.x * slide + p.out.x * bob,
            p.c.y * (0.5 + 0.5 * s) + p.tan.y * slide + p.out.y * bob,
            p.z,
          );
          p.g.rotation.z = (1 - s) * 0.3 * Math.sin(p.ph * 2.3) + Math.sin(t * 0.7 + p.ph) * 0.045;
          p.g.scale.setScalar((0.7 + 0.3 * s) * (1 + 0.04 * Math.sin(t * 1.5 + p.ph)));
        }
      }

      flash = Math.max(0, flash - dt * 2);
      face.uniforms.uFlash.value = pending && state === 'whole' ? 1 : 0;
      object.getWorldPosition(o);
      // 激活时窗口跟着变：宽差不多，高得多（三角摆成了近乎圆的一片）
      const k = state === 'whole' ? 0 : Math.min(1, Math.max(0, sp));
      layStars(face, o, object.getWorldScale(tmp).x * (1 + (ACTIVE_WIDE - 1) * k), ctx, decor, flash > 0.5 ? 1 : 0, 1 + (ACTIVE_TALL - 1) * k);
      return hit;
    },
  };
}


export const nightPiece: ItemDef = {
  id: 'compass',
  name: { zh: '一片夜', en: 'A Piece of Night' },
  desc: {
    zh: '一片奇特的晶体，你透过它看到的是什么呢？',
    en: 'A strange crystal. What is it you see through it?',
  },
  kind: 'need',
  icon,
  world,
  held,
};
