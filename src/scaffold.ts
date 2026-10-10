/* 窗景 · 构造（scaffold）的几座线框：在这里按米搭好，算成「从眼睛看过去的方向」，写进着色器当常量。
   天是跟着人走的球，所以这些东西实际上在无穷远——只有方向，没有视差；尺寸只用来定它们在天上占多大。
   每座是一串按顺序画的边：着色器按时间决定画到第几笔（见 skybox.ts 的 scaffold）。 */
import * as THREE from 'three';

interface Edge {
  a: THREE.Vector3;
  b: THREE.Vector3;
  /** 属于第几座 */
  s: number;
  /** 这一座里的第几笔 */
  k: number;
}

/** 地面在眼睛下面几米（同一个尺度下的远近才排得开） */
const GROUND = 3;
const deg = Math.PI / 180;

class Build {
  edges: Edge[] = [];
  private n = 0;
  constructor(
    private s: number,
    private az: number,
    private dist: number,
    private yaw = 0,
  ) {}

  /** 本地坐标（x 朝右、y 朝上、z 朝远，米；原点在地面上）→ 世界 */
  private w([x, y, z]: number[]) {
    const c = Math.cos(this.yaw * deg);
    const s = Math.sin(this.yaw * deg);
    const lx = x * c - z * s;
    const lz = x * s + z * c;
    const a = this.az * deg;
    // 正前方是 −Z；方位角往右为正
    const cx = Math.sin(a) * this.dist;
    const cz = -Math.cos(a) * this.dist;
    // 本地的 x 轴：与视线垂直、朝右；z 轴：沿视线往远
    return new THREE.Vector3(cx + lx * Math.cos(a) + lz * Math.sin(a), y - GROUND, cz + lx * Math.sin(a) - lz * Math.cos(a));
  }

  line(p: number[], q: number[]) {
    this.edges.push({ a: this.w(p), b: this.w(q), s: this.s, k: this.n++ });
  }
}

/** 塔架：一层层往上搭——四根立柱、一圈横梁、一根斜撑 */
function tower(b: Build, levels: number, side: number, h: number) {
  const r = side / 2;
  const sq = (y: number) => [[-r, y, -r], [r, y, -r], [r, y, r], [-r, y, r]];
  for (let i = 0; i < levels; i++) {
    const lo = sq(i * h);
    const hi = sq((i + 1) * h);
    for (let j = 0; j < 4; j++) b.line(lo[j], hi[j]);
    for (let j = 0; j < 4; j++) b.line(hi[j], hi[(j + 1) % 4]);
    const f = i % 4;
    b.line(lo[f], hi[(f + 1) % 4]);
  }
}

/** 门形框：两道拱框一前一后，先立腿、再起拱，最后用几根横档连起来 */
function gate(b: Build, w: number, leg: number, depth: number, seg: number) {
  const r = w / 2;
  const arc = (z: number) => {
    const pts: number[][] = [[-r, 0, z], [-r, leg, z]];
    for (let i = 1; i <= seg; i++) {
      const t = Math.PI - (Math.PI * i) / seg;
      pts.push([Math.cos(t) * r, leg + Math.sin(t) * r, z]);
    }
    pts.push([r, 0, z]);
    return pts;
  };
  const front = arc(0);
  const back = arc(depth);
  for (const pts of [front, back]) for (let i = 0; i + 1 < pts.length; i++) b.line(pts[i], pts[i + 1]);
  for (let i = 1; i < front.length - 1; i += 2) b.line(front[i], back[i]);
}

/** 立方格架：w×h×d 格，一格 size 米，从下往上、从近往远一根根加 */
function lattice(b: Build, nx: number, ny: number, nz: number, size: number) {
  const p = (i: number, j: number, k: number) => [(i - nx / 2) * size, j * size, k * size];
  for (let j = 0; j <= ny; j++)
    for (let k = 0; k <= nz; k++)
      for (let i = 0; i <= nx; i++) {
        if (i < nx) b.line(p(i, j, k), p(i + 1, j, k));
        if (k < nz) b.line(p(i, j, k), p(i, j, k + 1));
        if (j < ny) b.line(p(i, j, k), p(i, j + 1, k));
      }
}

/** 桁架桥：上下两根弦、一格格三角，往一头伸出去，到半空就停了 */
function truss(b: Build, bays: number, len: number, h: number, y0: number) {
  for (let i = 0; i < bays; i++) {
    const x0 = i * len;
    const x1 = (i + 1) * len;
    b.line([x0, y0, 0], [x1, y0, 0]);
    b.line([x0, y0 + h, 0], [x1, y0 + h, 0]);
    b.line([x0, y0, 0], [x0, y0 + h, 0]);
    b.line(i % 2 ? [x0, y0, 0] : [x0, y0 + h, 0], i % 2 ? [x1, y0 + h, 0] : [x1, y0, 0]);
  }
  // 桥墩：只有起头的一根
  b.line([0, 0, 0], [0, y0, 0]);
}

// 摆法：站点卡片在画面左上，所以高的东西都在正前方和右边；左边只有一段低低的桥从左往中间伸
const builds = [new Build(0, 24, 90, 20), new Build(1, 0, 130), new Build(2, 38, 82, -25), new Build(3, -44, 150, 18)];
tower(builds[0], 6, 9, 8);
gate(builds[1], 44, 32, 8, 10);
lattice(builds[2], 2, 2, 1, 8);
truss(builds[3], 8, 11, 6, 8);

const edges = builds.flatMap((b) => b.edges);
/** 每一座有几笔 */
export const SCAFFOLD_COUNTS = builds.map((b) => b.edges.length);

const v3 = (v: THREE.Vector3) => `vec3(${v.x.toFixed(5)}, ${v.y.toFixed(5)}, ${v.z.toFixed(5)})`;

/** 着色器里的常量：每一笔的起点方向 EA、法向 EN（起点 × 终点）、[弧长, 第几笔, 第几座] EK */
export function scaffoldGlsl() {
  const ea: string[] = [];
  const en: string[] = [];
  const ek: string[] = [];
  for (const e of edges) {
    const a = e.a.clone().normalize();
    const b = e.b.clone().normalize();
    ea.push(v3(a));
    en.push(v3(a.clone().cross(b).normalize()));
    ek.push(`vec3(${a.angleTo(b).toFixed(6)}, ${e.k}.0, ${e.s}.0)`);
  }
  return `const int NE = ${edges.length};
const vec3 EA[${edges.length}] = vec3[](${ea.join(', ')});
const vec3 EN[${edges.length}] = vec3[](${en.join(', ')});
const vec3 EK[${edges.length}] = vec3[](${ek.join(', ')});
const float NS[4] = float[](${SCAFFOLD_COUNTS.map((n) => `${n}.0`).join(', ')});`;
}
