"""浅梦 · 浅滩（shoal）：头顶的水。mockup/shallows-05 的重做（第三版；上一版的噪声地形作废）。

人走在一片**干的海底**上，**水面是头顶一整块平的天花板**（z=0，不动、不挡人）。
抬头看见的是**倒过来的海底**：脚下这片洞穴沿水面翻上去的倒影，隔着一层慢慢流动的蓝水面。
倒影里多出几样地上没有的东西（一座塔、一跑楼梯、一圈柱子、一扇门），走到那样东西的正下方，
地上有一圈沙纹，那里是出入口。正上方一处**圆窗**（水面在那里不反光），透出水面上的天；站进那圈光里就回家。

- **地**：几块平的海底（厅），用缓坡的沟连着，铺沙纹；只有平面和坡，没有噪声。
- **墙**：地升进水里的地方。墙是沿可走区域的边拉起来的几排大块面（脚下近乎直立，往上往外倾，
  顶边没进水面），整片因此是一个顶是水的洞穴：厅里水面高高在上（净空 7–13m），东南一团低矮的窄道（2.8m）。
- **倒影**：只翻上去核心那一片（地、墙、几块石头），颜色往水色挪一档，不投影、不挡人；
  水面是一层半透的「流」，倒影隔着它看。圆窗那里水面和倒影都开一个圆洞，透出天。
- **第二层**：东厅尽头一间圆室，一根石柱从地上穿过水面，楼梯绕着它盘上去，头钻出水面是一片潟湖：
  几座岛用石堤连着，去花房的花瓶在最远那座上。潟湖和核心之间隔着一道出水的岩脊（挡住倒影，也是远处的轮廓）；
  潟湖底下的水不反光，从下面看得见岛的底和天。

出入口（来回成对，落点名＝对方世界的 id）：
- 圆窗下那圈光 → house（at="shoal"）；从家来落在旁边（到达点 house，也是出生点）。
- 岛上的花瓶，E「凑近」→ glasshouse（pf.gate_vase）。
- 最深那条沟尽头的黑坑 → seeping（占位，世界还没有）。
- 倒影里那座塔的正下方：一圈沙纹，中间一枚晶体（站点先空着）。

运行：node scripts/blender.cjs build shoal，网页 ?world=shoal
"""
import math
import os
import random
import sys

import bmesh
import bpy

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import furniture as fu  # noqa: E402
import nx  # noqa: E402
import prefabs as pf  # noqa: E402

EXTENT = 220.0
CENTER = (10.0, 0.0)

SEA = 0.0
TOP = -0.06          # 墙顶（没在水面下）
MIRROR_X = 37.0      # 倒影只翻到这里为止（再往东是岩脊和潟湖）
X0, X1, Y0, Y1 = -60.0, 72.0, -66.0, 74.0    # 算可走区域的范围
CELL = 1.0

SUN = (0.42, -0.50, 0.76)
WIN_C = (3.0, 26.0)  # 圆窗
WIN_R = 4.4

FLOOR = dict(ramp=("lilac_dark", "lilac", "lilac_pale"), pattern="bands")
WALL = dict(ramp=("violet", "lilac_dark", "lilac"), pattern="plain")
STONE = dict(ramp=("violet", "lilac_dark", "lilac_pale"), pattern="plain")
M_FLOOR = dict(ramp=("blue", "blue", "blue_pale"), pattern="plain")
M_WALL = dict(ramp=("violet", "lilac_dark", "lilac"), pattern="plain")
WATER = dict(ramp=("blue", "blue_pale", "blue_pale"), pattern="flow")
GHOST_WATER = (0.45, 0.0, 0.1)

rnd = random.Random(7)


# ── 可走区域：厅（平的圆）＋ 沟（折线，地板高沿线插值）────────

HALLS = {
    "A": ((0.0, 30.0), 13.0, -9.0),     # 起厅：圆窗
    "C": ((0.0, -22.0), 12.0, -11.0),   # 塔厅
    "E": ((28.0, 4.0), 9.0, -7.0),      # 东厅
    "F": ((-32.0, 6.0), 10.0, -6.5),    # 西厅
    "G": ((-4.0, 57.0), 9.0, -7.0),     # 北厅（空的一片）
    "S": ((-5.0, -50.0), 5.5, -13.5),   # 最深那条沟的尽头
    "I": ((54.0, 8.0), 6.5, -7.0),      # 楼梯间（东）
}

PATHS = [
    # 起厅 → 塔厅：一条宽沟，第一眼顺着它看下去
    ([(0, 30), (1, 17), (2, 4), (0, -10), (0, -22)], [-9, -9, -9.8, -10.6, -11], 5.0),
    ([(0, -22), (-3, -34), (-5, -50)], [-11, -12.4, -13.5], 3.4),                  # 最深那条沟
    ([(0, 30), (12, 26), (22, 16), (28, 4)], [-9, -9, -8, -7], 3.4),               # 起厅 → 东厅
    ([(0, 30), (-13, 26), (-25, 16), (-32, 6)], [-9, -9, -7.8, -6.5], 3.4),        # 起厅 → 西厅
    ([(-32, 6), (-31, 26), (-20, 44), (-4, 57)], [-6.5, -6.6, -6.8, -7], 3.2),     # 西厅 → 北厅
    ([(0, 30), (-2, 44), (-4, 57)], [-9, -8, -7], 3.0),                            # 起厅 → 北厅
    ([(-32, 6), (-30, -12), (-18, -25), (0, -22)], [-6.5, -8, -10.2, -11], 3.4),   # 西厅 → 塔厅
    ([(28, 4), (40, 6), (54, 8)], [-7, -7, -7], 3.0),                              # 东厅 → 楼梯间（岩脊底下）
    # 东南密的一团：低矮的窄道（地板 −2.8，净空 2.8m）；从东厅一条坡上来，另一头坡下塔厅
    ([(28, 4), (29, -6), (30, -16)], [-7, -7, -2.8], 2.2),
    ([(30, -16), (22, -14)], [-2.8, -2.8], 1.9),
    ([(22, -14), (17, -21)], [-2.8, -2.8], 1.9),
    ([(17, -21), (23, -27)], [-2.8, -2.8], 1.9),
    ([(23, -27), (31, -27)], [-2.8, -2.8], 1.9),
    ([(31, -27), (30, -16)], [-2.8, -2.8], 1.9),
    ([(30, -16), (38, -20)], [-2.8, -2.8], 1.9),           # 死胡同
    ([(22, -14), (17, -6)], [-2.8, -2.8], 1.9),            # 死胡同
    ([(31, -27), (30, -36)], [-2.8, -2.8], 1.9),
    ([(30, -36), (18, -38), (10, -30), (0, -22)], [-2.8, -6.5, -11, -11], 2.4),
]

# 立在厅里、从地上一直穿进水面的石柱：(中心, 半径)
PILLARS = [((-6.5, -16.0), 1.7), ((4.0, -31.0), 1.4), ((7.5, -15.0), 1.2), ((25.5, -21.0), 1.5),
           ((-34.0, 1.0), 1.3), ((-3.0, 61.0), 1.0)]


def seg_proj(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 < 1e-9 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - ax - dx * t, py - ay - dy * t), t


def features(x, y):
    """这一点离各个厅、沟有多远：[(超出边多少米, 那里的地板高)]"""
    out = []
    for (cx, cy), r, f in HALLS.values():
        out.append((math.hypot(x - cx, y - cy) - r, f))
    for pts, fl, half in PATHS:
        best = (1e9, fl[0])
        for i in range(len(pts) - 1):
            d, t = seg_proj(x, y, *pts[i], *pts[i + 1])
            if d < best[0]:
                best = (d, fl[i] + (fl[i + 1] - fl[i]) * t)
        out.append((best[0] - half, best[1]))
    return out


def walkable(x, y):
    for (cx, cy), r in PILLARS:
        if math.hypot(x - cx, y - cy) < r:
            return False
    return min(features(x, y))[0] < 0.0


def floor_at(x, y):
    """地板高：取「最靠里」的那个——在里面的取最低的（厅压过穿过它的沟），都在外面取最近的"""
    fs = features(x, y)
    inside = [f for d, f in fs if d < 0.0]
    if inside:
        return min(inside)
    return min(fs)[1]


# ── 栅格：可走区域、距离场 ───────────────────────

NX = int((X1 - X0) / CELL)
NY = int((Y1 - Y0) / CELL)


def cell_c(i, j):
    return X0 + (i + 0.5) * CELL, Y0 + (j + 0.5) * CELL


MASK = None
DIST = None


def build_mask():
    global MASK, DIST
    MASK = [[walkable(*cell_c(i, j)) for i in range(NX)] for j in range(NY)]
    # 到最近的可走格多远（倒角距离）
    INF = 1e9
    D = [[0.0 if MASK[j][i] else INF for i in range(NX)] for j in range(NY)]
    a, b = 1.0, 1.4142
    for j in range(NY):
        for i in range(NX):
            v = D[j][i]
            if i > 0: v = min(v, D[j][i - 1] + a)
            if j > 0:
                v = min(v, D[j - 1][i] + a)
                if i > 0: v = min(v, D[j - 1][i - 1] + b)
                if i < NX - 1: v = min(v, D[j - 1][i + 1] + b)
            D[j][i] = v
    for j in range(NY - 1, -1, -1):
        for i in range(NX - 1, -1, -1):
            v = D[j][i]
            if i < NX - 1: v = min(v, D[j][i + 1] + a)
            if j < NY - 1:
                v = min(v, D[j + 1][i] + a)
                if i < NX - 1: v = min(v, D[j + 1][i + 1] + b)
                if i > 0: v = min(v, D[j + 1][i - 1] + b)
            D[j][i] = v
    DIST = D


def mask_at(x, y):
    i, j = int((x - X0) // CELL), int((y - Y0) // CELL)
    if 0 <= i < NX and 0 <= j < NY:
        return MASK[j][i]
    return False


def dist_at(x, y):
    i, j = int((x - X0) // CELL), int((y - Y0) // CELL)
    if 0 <= i < NX and 0 <= j < NY:
        return DIST[j][i] * CELL
    return 99.0


# ── 边界：可走区域的轮廓 → 化简成几米一段的折线 ─────────

def loops():
    """格子边界上的有向边（可走的在左手），串成闭合的圈"""
    nxt = {}
    for j in range(NY):
        for i in range(NX):
            if not MASK[j][i]:
                continue
            if i == 0 or not MASK[j][i - 1]:
                nxt.setdefault((i, j + 1), []).append((i, j))          # 西边，往下走
            if i == NX - 1 or not MASK[j][i + 1]:
                nxt.setdefault((i + 1, j), []).append((i + 1, j + 1))  # 东边，往上走
            if j == 0 or not MASK[j - 1][i]:
                nxt.setdefault((i, j), []).append((i + 1, j))          # 南边，往东走
            if j == NY - 1 or not MASK[j + 1][i]:
                nxt.setdefault((i + 1, j + 1), []).append((i, j + 1))  # 北边，往西走
    out = []
    while nxt:
        start = next(iter(nxt))
        loop = [start]
        cur = start
        prev_dir = None
        while True:
            cands = nxt.get(cur)
            if not cands:
                break
            if len(cands) > 1 and prev_dir is not None:
                # 鞍点：往左拐优先（可走的在左手，两块只在角上碰着时分开走）
                def turn(c):
                    d = (c[0] - cur[0], c[1] - cur[1])
                    return prev_dir[0] * d[1] - prev_dir[1] * d[0]
                cands.sort(key=turn, reverse=True)
            n = cands.pop(0)
            if not cands:
                del nxt[cur]
            prev_dir = (n[0] - cur[0], n[1] - cur[1])
            cur = n
            if cur == start:
                break
            loop.append(cur)
        if len(loop) >= 4:
            out.append([(X0 + i * CELL, Y0 + j * CELL) for i, j in loop])
    return out


def dp(pts, tol):
    if len(pts) < 3:
        return pts
    a, b = pts[0], pts[-1]
    best, idx = -1.0, 0
    for k in range(1, len(pts) - 1):
        d, _ = seg_proj(pts[k][0], pts[k][1], a[0], a[1], b[0], b[1])
        if d > best:
            best, idx = d, k
    if best <= tol:
        return [a, b]
    return dp(pts[:idx + 1], tol)[:-1] + dp(pts[idx:], tol)


def simplify(loop, tol=0.9, seg=4.5):
    # 从离第一点最远的那一点切开，两半各化简
    n = len(loop)
    far = max(range(n), key=lambda k: (loop[k][0] - loop[0][0]) ** 2 + (loop[k][1] - loop[0][1]) ** 2)
    a = dp(loop[:far + 1], tol)
    b = dp(loop[far:] + [loop[0]], tol)
    pts = a[:-1] + b[:-1]
    # 一段太长就切开（墙才有块面）
    out = []
    for k in range(len(pts)):
        p, q = pts[k], pts[(k + 1) % len(pts)]
        L = math.hypot(q[0] - p[0], q[1] - p[1])
        m = max(1, int(math.ceil(L / seg)))
        for s in range(m):
            out.append((p[0] + (q[0] - p[0]) * s / m, p[1] + (q[1] - p[1]) * s / m))
    return out


def area(pts):
    return 0.5 * sum(pts[k][0] * pts[(k + 1) % len(pts)][1] - pts[(k + 1) % len(pts)][0] * pts[k][1]
                     for k in range(len(pts)))


# ── 网格小工具 ──────────────────────────────────

def mesh(name, verts, faces, smooth=0, collide=True, shadow=True, **style):
    """按给定的绕向建网格（不重算法线）"""
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    nx._place(obj, (0, 0, 0), (0, 0, 0), None)
    if smooth:
        nx._smooth(obj, smooth)
    return nx.matte(obj, collide=collide, shadow=shadow, **style)


def face_n(vs, f):
    a, b, c = vs[f[0]], vs[f[1]], vs[f[2]]
    u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    v = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    return (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])


def mirrored(verts, faces):
    """沿水面翻上去：z 取反、绕向反过来"""
    return [(x, y, -z) for x, y, z in verts], [tuple(reversed(f)) for f in faces]


def mirror_obj(obj):
    """把一个物体沿水面（z=0）翻上去（倒影里多出来的东西：先在水面下照原样搭好，再整件翻上去）"""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    for v in bm.verts:
        v.co.z = -v.co.z
    for f in bm.faces:
        f.normal_flip()
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    obj.location.z = -obj.location.z
    r = obj.rotation_euler
    obj.rotation_euler = (-r.x, -r.y, r.z)
    return obj


# ── 地 ──────────────────────────────────────────

FLOOR_PARTS = {}


def ground():
    """可走的格子外加一圈 2m（压在墙底下），每个顶点取地板高"""
    vs, fs, idx = [], [], {}
    hcache = {}

    def vid(i, j):
        if (i, j) not in idx:
            x, y = X0 + i * CELL, Y0 + j * CELL
            if (i, j) not in hcache:
                hcache[(i, j)] = floor_at(x, y)
            idx[(i, j)] = len(vs)
            vs.append((x, y, hcache[(i, j)]))
        return idx[(i, j)]

    for j in range(NY):
        for i in range(NX):
            if DIST[j][i] > 2.5:
                continue
            q = [vid(i, j), vid(i + 1, j), vid(i + 1, j + 1), vid(i, j + 1)]
            if (i + j) % 2:
                fs += [(q[0], q[1], q[2]), (q[0], q[2], q[3])]
            else:
                fs += [(q[0], q[1], q[3]), (q[1], q[2], q[3])]
    mesh("ground", vs, fs, smooth=30, **FLOOR)
    # 倒影：只翻核心那一片；起厅圆窗上方挖一个圆
    HQ = 11.0    # 圆窗周围这一方块另做：方的一块、中间一个干净的圆洞
    mf = [f for f in fs if sum(vs[k][0] for k in f) / 3 < MIRROR_X
          and not (abs(sum(vs[k][0] for k in f) / 3 - WIN_C[0]) < HQ and abs(sum(vs[k][1] for k in f) / 3 - WIN_C[1]) < HQ)]
    mv, mf = mirrored(vs, mf)
    o = len(mv)
    hv, hf = ring_square(WIN_C[0], WIN_C[1], 10.0, HQ, -floor_at(*WIN_C), seg=44)
    mv += hv
    for f in hf:
        f = tuple(i + o for i in f)
        mf.append(f if face_n(mv, f)[2] < 0 else tuple(reversed(f)))
    mesh("m_ground", mv, mf, smooth=30, collide=False, shadow=False, **M_FLOOR)


# 沙纹：厅里一道道低矮的长棱（几何的，不是纹样），每个厅一个方向。
# 每一截是一个封闭的实体：截面是个矮三角（两侧斜面 ＋ 压在地下 2cm 的底），两头收成一个点；
# 只铺在厅里**完全平**的那片地上（地网格的四个角都是厅的地板高），离墙、石柱、石头、圆窗、出入口都留开
RIPPLES = [("A", 70, 1.7), ("C", 20, 1.5), ("E", 115, 1.6), ("F", 160, 1.8), ("G", 40, 2.0), ("S", 95, 1.3),
           ("I", 0, 0)]
RIP_W, RIP_STEP, RIP_CLEAR = 0.5, 0.5, 1.4


def _flat(x, y, f):
    """这一点所在的地网格那一格，四个角都是厅的地板高（地在这里是平的）"""
    i, j = math.floor((x - X0) / CELL), math.floor((y - Y0) / CELL)
    for di in (0, 1):
        for dj in (0, 1):
            if abs(floor_at(X0 + (i + di) * CELL, Y0 + (j + dj) * CELL) - f) > 1e-4:
                return False
    return True


def _rip_ok(x, y, f, p):
    if not walkable(x, y):
        return False
    for k in range(8):                          # 离墙、石柱留开
        a = k * math.pi / 4
        if not walkable(x + math.cos(a) * RIP_CLEAR, y + math.sin(a) * RIP_CLEAR):
            return False
    for sx in (-RIP_W, 0.0, RIP_W):             # 底下整片是平的
        if not _flat(x + p[0] * sx, y + p[1] * sx, f):
            return False
    if math.hypot(x - WIN_C[0], y - WIN_C[1]) < WIN_R + 1.0:
        return False
    for bx, by, br, *_ in BOULDERS:
        if math.hypot(x - bx, y - by) < br + 1.0:
            return False
    keep = [(TOWER[0], TOWER[1], 2.6 + 1.4 + 1.0), (HALLS["S"][0][0], HALLS["S"][0][1], 2.2 + 1.0),
            (SPAWN[0], SPAWN[1], 1.5)]
    return all(math.hypot(x - kx, y - ky) > kr for kx, ky, kr in keep)


def ripples():
    vs, fs = [], []
    pieces = 0
    for key, ang, gap in RIPPLES:
        if not gap:
            continue
        (cx, cy), r, f = HALLS[key]
        a = math.radians(ang)
        d = (math.cos(a), math.sin(a))          # 沙纹的走向
        p = (-d[1], d[0])                        # 一道道排开的方向
        k = -r + gap / 2
        i = 0
        while k < r:
            half = math.sqrt(max(0.0, r * r - k * k))
            h = 0.10 + 0.04 * (i % 2)
            run = []
            t = -half
            while t <= half + 1e-6:
                bend = 0.35 * math.sin(t * 0.35 + i)
                bx, by = cx + d[0] * t + p[0] * (k + bend), cy + d[1] * t + p[1] * (k + bend)
                if _rip_ok(bx, by, f, p):
                    run.append((bx, by))
                else:
                    if len(run) >= 5:
                        pieces += _rip_piece(vs, fs, run, p, f, h)
                    run = []
                t += RIP_STEP
            if len(run) >= 5:
                pieces += _rip_piece(vs, fs, run, p, f, h)
            k += gap
            i += 1
    obj = mesh("ripples", vs, fs, collide=False, shadow=False, **FLOOR)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    print(f"[nx] shoal ripples: {pieces} pieces")


def _rip_piece(vs, fs, run, p, f, h):
    """一截沙纹：两头收成点、中间一串矮三角截面，底压在地下 2cm；封闭（没有开口的边），法线朝外"""
    n = len(run)
    z0 = f - 0.02
    o = len(vs)
    vs.append((run[0][0], run[0][1], z0))                       # 头
    for s in range(1, n - 1):
        u = s / (n - 1)
        taper = min(1.0, min(u, 1.0 - u) / 0.22)                # 两头 22% 的长度里慢慢收
        w, hh = RIP_W * (0.35 + 0.65 * taper), h * taper
        x, y = run[s]
        vs += [(x - p[0] * w, y - p[1] * w, z0), (x, y, f + hh), (x + p[0] * w, y + p[1] * w, z0)]
    vs.append((run[-1][0], run[-1][1], z0))                     # 尾
    head, tail = o, len(vs) - 1
    L = lambda s: o + 1 + (s - 1) * 3                           # 第 s 个截面的左、顶、右 = L, L+1, L+2
    m = n - 2
    # 头尾两把扇
    fs += [(head, L(1), L(1) + 1), (head, L(1) + 1, L(1) + 2), (head, L(1) + 2, L(1))]
    for s in range(1, m):
        A, B = L(s), L(s + 1)
        fs += [(A, B, B + 1, A + 1), (A + 1, B + 1, B + 2, A + 2), (A + 2, B + 2, B, A)]
    fs += [(tail, L(m) + 1, L(m)), (tail, L(m) + 2, L(m) + 1), (tail, L(m), L(m) + 2)]
    return 1


# ── 墙 ──────────────────────────────────────────

def gap_out(p, n, limit=12.0):
    """从边上沿 n 往外走，多远又碰到可走的地方"""
    s = 0.8
    while s < limit:
        if mask_at(p[0] + n[0] * s, p[1] + n[1] * s):
            return s
        s += 0.5
    return limit


def walls():
    vs, fs, kinds = [], [], []
    for raw in loops():
        pts = simplify(raw)
        if len(pts) < 3:
            continue
        hole = area(pts) < 0          # 可走的在左手：外圈逆时针，石柱（洞）顺时针
        n_ = len(pts)
        rows = []
        for k in range(n_):
            p0, p1, p2 = pts[k - 1], pts[k], pts[(k + 1) % n_]
            # 外法线（指向不可走的一边 ＝ 走向的右手）
            nxs, nys = 0.0, 0.0
            for a, b in ((p0, p1), (p1, p2)):
                dx, dy = b[0] - a[0], b[1] - a[1]
                L = math.hypot(dx, dy) or 1.0
                nxs += dy / L
                nys += -dx / L
            L = math.hypot(nxs, nys) or 1.0
            n = (nxs / L, nys / L)
            fl = floor_at(p1[0] - n[0] * 1.2, p1[1] - n[1] * 1.2)
            depth = -fl
            gap = gap_out(p1, n)
            lean = min(rnd.uniform(2.0, 5.0) * min(1.0, depth / 8.0), 0.4 * gap)
            lip = min(lean + 3.0, 0.48 * gap)
            j1 = min(rnd.uniform(0.15, 0.6), 0.2 * gap)
            z1 = fl + min(1.5, 0.35 * depth)
            z2 = fl * 0.42 + rnd.uniform(-0.4, 0.4) * min(1.0, depth / 6)
            # 中间那一排进进出出，墙才有一块块的面
            mid = j1 + (lean - j1) * 0.55 + rnd.uniform(-1.0, 1.0) * min(1.0, depth / 6)
            mid = max(0.05, min(mid, 0.42 * gap))
            ring = [
                (p1[0] + n[0] * 0.1, p1[1] + n[1] * 0.1, fl - 0.7),
                (p1[0] + n[0] * j1, p1[1] + n[1] * j1, z1),
                (p1[0] + n[0] * mid, p1[1] + n[1] * mid, z2),
                (p1[0] + n[0] * lean, p1[1] + n[1] * lean, TOP),
                (p1[0] + n[0] * lip, p1[1] + n[1] * lip, TOP),
            ]
            rows.append(ring)
        base = len(vs)
        for ring in rows:
            vs.extend(ring)
        R = 5
        cx = sum(p[0] for p in pts) / n_
        for k in range(n_):
            a, b = base + k * R, base + ((k + 1) % n_) * R
            for r in range(R - 1):
                f = (a + r, b + r, b + r + 1, a + r + 1)
                # 朝可走的一边（左手）：法线和外法线反向
                fn = face_n(vs, f)
                ex, ey = pts[(k + 1) % n_][0] - pts[k][0], pts[(k + 1) % n_][1] - pts[k][1]
                outward = (ey, -ex)
                if r == R - 2:
                    want_up = True       # 墙顶外沿那一圈平的「礁」：朝上
                    if (fn[2] > 0) != want_up:
                        f = tuple(reversed(f))
                elif fn[0] * outward[0] + fn[1] * outward[1] > 0:
                    f = tuple(reversed(f))
                fs.append(f)
                kinds.append(sum(vs[i][0] for i in f) / 4)
    mesh("walls", vs, fs, **WALL)
    mf = [f for f, x in zip(fs, kinds) if x < MIRROR_X]
    mv, mf = mirrored(vs, mf)
    mesh("m_walls", mv, mf, collide=False, shadow=False, **M_WALL)


# ── 水面 ─────────────────────────────────────────

def ring_square(cx, cy, r, half, z, seg=48):
    """一块方的面，中间挖一个圆洞：返回 (顶点, 面)，面朝上"""
    vs, fs = [], []
    for k in range(seg):
        a = math.tau * k / seg
        c, s = math.cos(a), math.sin(a)
        m = half / max(abs(c), abs(s))
        vs.append((cx + c * r, cy + s * r, z))
        vs.append((cx + c * m, cy + s * m, z))
    for k in range(seg):
        a, b = 2 * k, 2 * ((k + 1) % seg)
        fs.append((a, a + 1, b + 1, b))
    # 方的四个角：每段外沿是方边上的点，所以角上要补三角
    corners = [(cx + half, cy + half), (cx - half, cy + half), (cx - half, cy - half), (cx + half, cy - half)]
    for (qx, qy) in corners:
        ang = math.atan2(qy - cy, qx - cx) % math.tau
        k = int(ang / (math.tau / seg))
        a, b = 2 * k + 1, 2 * ((k + 1) % seg) + 1
        vs.append((qx, qy, z))
        fs.append((a, len(vs) - 1, b))
    return vs, fs


def rect(x0, y0, x1, y1, z):
    return [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], [(0, 1, 2, 3)]


def water():
    """一层水：朝下一面（z=0）＋ 朝上一面（z=0.01），圆窗那里开洞"""
    H = 10.0
    cx, cy = WIN_C
    parts = [ring_square(cx, cy, WIN_R, H, 0.0, seg=44)]
    W0, W1, V0, V1 = -95.0, 125.0, -110.0, 115.0
    parts += [rect(W0, V0, W1, cy - H, 0.0), rect(W0, cy + H, W1, V1, 0.0),
              rect(W0, cy - H, cx - H, cy + H, 0.0), rect(cx + H, cy - H, W1, cy + H, 0.0)]
    vs, fs = [], []
    for pv, pf_ in parts:
        o = len(vs)
        vs += pv
        for f in pf_:
            fn = face_n(pv, f)
            fs.append(tuple(i + o for i in (f if fn[2] > 0 else tuple(reversed(f)))))
    up = [(x, y, 0.01) for x, y, _ in vs]
    down = [(x, y, 0.0) for x, y, _ in vs]
    # 朝下那一面（从洞里看）和朝上那一面（从潟湖看）分开：上面那面深一点、浓一点，看得出是水
    mesh("water", down, [tuple(reversed(f)) for f in fs], collide=False, shadow=False, ghost=GHOST_WATER, **WATER)
    mesh("water_top", up, fs, collide=False, shadow=False, ghost=(0.62, 0.0, 0.1),
         ramp=("lilac_dark", "blue", "blue"), pattern="flow")


def window():
    """圆窗：水面那一圈开洞，一道亮沿；洞里透下来一柱光，落在地上一圈亮的"""
    cx, cy = WIN_C
    nx.torus("win_ring", WIN_R + 0.05, 0.14, (cx, cy, SEA + 0.005), major_seg=64, minor_seg=8,
             collide=False, shadow=False, ramp=("mist", "white", "white"), pattern="plain", emit=1.0)
    fz = floor_at(cx, cy)
    # 光顺着太阳斜下来
    dx, dy = -SUN[0] / SUN[2] * (-fz), -SUN[1] / SUN[2] * (-fz)
    lx, ly = cx + dx * 0.0, cy + dy * 0.0
    global LIT
    LIT = (lx, ly, fz)
    nx.cylinder("win_spot", WIN_R - 0.2, WIN_R - 0.2, 0.03, (lx, ly, fz), segments=48, collide=False, shadow=False,
                ramp=("pink_pale", "white", "white"), pattern="plain", emit=1.0)
    # 光柱：一圈很淡的虚像，从水面落到地上
    for side, nm in ((1, "win_shaft"), (-1, "win_shaft_in")):
        seg = 40
        vs, fs = [], []
        for k in range(seg):
            a = math.tau * k / seg
            vs.append((cx + math.cos(a) * (WIN_R - 0.3), cy + math.sin(a) * (WIN_R - 0.3), -0.1))
            vs.append((lx + math.cos(a) * (WIN_R - 0.3), ly + math.sin(a) * (WIN_R - 0.3), fz + 0.05))
        for k in range(seg):
            a, b = 2 * k, 2 * ((k + 1) % seg)
            f = (a, b, b + 1, a + 1)
            fn = face_n(vs, f)
            mx = sum(vs[i][0] for i in f) / 4 - (cx + lx) / 2
            my = sum(vs[i][1] for i in f) / 4 - (cy + ly) / 2
            if (fn[0] * mx + fn[1] * my) * side < 0:
                f = tuple(reversed(f))
            fs.append(f)
        mesh(nm, vs, fs, collide=False, shadow=False, ghost=(0.12, 2.5, 9.0), emit=1.0,
             ramp=("mist", "white", "white"), pattern="plain")


LIT = (0, 0, 0)


# ── 石头 ─────────────────────────────────────────

def boulder_geo(r, h, seed, seg=7):
    """一块圆润的低矮石头：两三圈不规则的多边形，顶上收成一个平面"""
    rr = random.Random(seed)
    jit = [rr.uniform(0.82, 1.12) for _ in range(seg)]
    rings = [(1.0, -0.3), (1.0, 0.0), (0.92, h * 0.5), (0.62, h * 0.92), (0.0, h)]
    vs, fs = [], []
    for s, z in rings:
        if s == 0.0:
            vs.append((0, 0, z))
        else:
            for k in range(seg):
                a = math.tau * (k + 0.5 * (z > 0)) / seg
                vs.append((math.cos(a) * r * s * jit[k], math.sin(a) * r * s * jit[k], z))
    for ri in range(len(rings) - 2):
        a0, b0 = ri * seg, (ri + 1) * seg
        for k in range(seg):
            fs.append((a0 + k, a0 + (k + 1) % seg, b0 + (k + 1) % seg, b0 + k))
    top = len(vs) - 1
    b0 = (len(rings) - 2) * seg
    for k in range(seg):
        fs.append((b0 + k, b0 + (k + 1) % seg, top))
    return vs, fs


BOULDERS = [
    # (x, y, 半径, 高, 倒影里有没有)
    (-7.0, 24.0, 2.2, 1.6, True), (-9.5, 27.5, 1.2, 0.9, True), (9.5, 36.0, 1.8, 1.2, False),
    (3.5, -2.0, 1.6, 1.1, True), (-3.0, 10.0, 1.1, 0.7, True),
    (5.0, -19.0, 1.4, 1.0, True), (-8.5, -26.0, 2.4, 1.9, True),
    (30.0, 8.5, 2.0, 1.4, True), (24.5, -0.5, 1.2, 0.8, True),
    (-29.0, 10.5, 1.9, 1.3, True), (-36.0, 7.5, 1.0, 0.7, True),
    (-1.5, -52.0, 1.0, 0.7, True), (-27.0, 28.0, 1.5, 1.0, True), (17.0, 22.5, 1.3, 0.9, True),
]


def boulders():
    for i, (x, y, r, h, refl) in enumerate(BOULDERS):
        z = floor_at(x, y)
        vs, fs = boulder_geo(r, h, i + 3)
        vs = [(x + a, y + b, z + c) for a, b, c in vs]
        obj = mesh(f"boulder{i}", vs, fs, **STONE)
        _fix_normals(obj)
        if refl and x < MIRROR_X:
            mv, mf = mirrored(vs, fs)
            m = mesh(f"m_boulder{i}", mv, mf, collide=False, shadow=False, **M_WALL)
            _fix_normals(m, inward=False)


def _fix_normals(obj, inward=False):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if inward:
        for f in bm.faces:
            f.normal_flip()
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


# ── 倒影里多出来的东西 ───────────────────────────

def reflect_only():
    nx.into("mirror_things")
    tint = dict(collide=False, shadow=False)

    # 一座塔：立在塔厅的地板上（只在倒影里）；正下方一圈沙纹、中间一枚晶体
    k = fu.Kit()
    k.box((6.4, 6.4, 1.6), bevel=0.2)
    k.box((4.6, 4.6, 5.4), (0, 0, 1.6), bevel=0.15)
    k.box((3.2, 3.2, 1.6), (0, 0, 7.0), rot=(0, 0, 18), bevel=0.1)
    k.lathe([(2.0, 0.0), (1.5, 0.4), (0.0, 1.6)], loc=(0, 0, 8.6), seg=6)
    tz = floor_at(*TOWER)
    mirror_obj(k.build("m_tower", loc=(TOWER[0], TOWER[1], tz), rot=(0, 0, 17), smooth=0,
                       ramp=("rose_deep", "rose", "pink"), pattern="plain", **tint))

    # 一跑楼梯：从东厅的地板斜着上去，又断在半空
    s = fu.Kit()
    for i in range(14):
        s.box((2.2, 0.6, 0.35), (0, 0.6 * i, 0.35 * i + 0.6))
    s.box((0.4, 0.4, 0.95), (0, 0, 0))
    ex, ey = 26.0, 0.0
    mirror_obj(s.build("m_stair", loc=(ex, ey, floor_at(ex, ey)), rot=(0, 0, 300), smooth=0,
                       ramp=("rose_deep", "rose", "pink"), pattern="plain", **tint))

    # 一圈柱子：立在西厅
    p = fu.Kit()
    for i in range(7):
        a = math.tau * i / 7
        p.lathe([(0.55, 0.0), (0.42, 0.5), (0.42, 4.0), (0.62, 4.4), (0.62, 4.8)],
                loc=(math.cos(a) * 4.0, math.sin(a) * 4.0, 0), seg=7)
    mirror_obj(p.build("m_pillars", loc=(-30.0, 8.0, floor_at(-30, 8)), smooth=0,
                       ramp=("rose_deep", "rose", "pink"), pattern="plain", **tint))

    # 一扇门：立在北厅，门里什么也没有
    d = fu.Kit()
    d.box((0.45, 0.45, 3.3), (-1.05, 0, 0))
    d.box((0.45, 0.45, 3.3), (1.05, 0, 0))
    d.box((2.6, 0.5, 0.45), (0, 0, 3.3))
    mirror_obj(d.build("m_door", loc=(-6.0, 55.0, floor_at(-6, 55)), rot=(0, 0, 70), smooth=0,
                       ramp=("rose_deep", "rose", "pink"), pattern="plain", **tint))


TOWER = (-1.0, -21.0)


# ── 水面上的东西（够不着，只从下面看得见）─────────────

def floats():
    nx.into("floats")
    # 一只船的底，浮在塔厅上空
    k = fu.Kit()
    k.lathe([(0.0, 0.0), (1.2, 0.35), (1.6, 0.9), (1.6, 1.1)], seg=10)
    boat = k.build("boat", loc=(6.0, -12.0, 0.55), rot=(180, 0, 0), smooth=0,
                   ramp=("violet_deep", "violet", "lilac_dark"), pattern="bands", collide=False)
    boat.scale = (2.4, 1.0, 1.0)
    boat.rotation_euler[2] = math.radians(28)
    nx.behave(boat, bob=0.05)
    # 浮叶：贴着水面
    for i, (x, y, rr) in enumerate(((-8.0, 33.0, 1.6), (-5.0, 36.5, 1.1), (10.0, 31.0, 1.3), (12.0, 18.0, 1.5),
                                    (-4.0, -26.0, 1.8), (1.5, -30.0, 1.2), (30.0, 10.0, 1.4), (-30.0, 2.0, 1.7),
                                    (-2.0, 50.0, 1.4), (20.0, -20.0, 1.0), (-2.5, -40.0, 1.3))):
        nx.cylinder(f"leaf{i}", rr, rr * 0.96, 0.06, (x, y, SEA + 0.02), segments=12, collide=False,
                    ramp=("green", "lilac", "lilac_pale"), pattern="plain")
    # 垂下来的根：从一片大叶子底下垂进水里
    r = fu.Kit()
    for dx, dy, ln, rad in ((0.0, 0.0, 3.4, 0.14), (0.5, 0.3, 2.4, 0.12), (-0.4, 0.4, 2.9, 0.12),
                            (0.2, -0.5, 2.0, 0.1), (-0.6, -0.3, 2.3, 0.11)):
        r.box((2 * rad, 2 * rad, ln), (dx, dy, -ln))
    r.build("roots", loc=(-30.0, 2.0, SEA + 0.02), smooth=0, collide=False,
            ramp=("violet_deep", "violet", "lilac_dark"), pattern="plain")


# ── 岩脊：出水的一道岩，隔开核心和潟湖 ─────────────────

def crag(name, pts, z0, z1, shrink, seed, style):
    """一块出水的岩：底是多边形 pts，往上收（shrink 倍）、顶上平"""
    rr = random.Random(seed)
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    n = len(pts)
    levels = [(0.0, z0), (0.0, 0.25 * z1), (0.45, 0.7 * z1), (1.0, z1)]
    vs, fs = [], []
    for t, z in levels:
        s = 1.0 - (1.0 - shrink) * t
        for k, (x, y) in enumerate(pts):
            j = rr.uniform(-0.6, 0.6) * (0 < t < 1)
            vs.append((cx + (x - cx) * s + j, cy + (y - cy) * s + j, z))
    for li in range(len(levels) - 1):
        for k in range(n):
            a, b = li * n + k, li * n + (k + 1) % n
            fs.append((a, b, b + n, a + n))
    fs.append(tuple(range((len(levels) - 1) * n, len(levels) * n)))
    fs.append(tuple(reversed(range(n))))
    obj = mesh(name, vs, fs, **style)
    _fix_normals(obj)
    return obj


def ridge():
    nx.into("ridge")
    crag("ridge_a", [(41.5, -34), (45.5, -33), (47.0, -18), (46.0, -4), (44.5, -1), (41.0, -3), (41.0, -20)],
         -1.0, 7.5, 0.55, 1, WALL)
    crag("ridge_b", [(40.0, 12), (44.0, 11), (46.5, 22), (46.0, 40), (42.0, 52), (38.5, 46), (39.0, 26)],
         -1.0, 9.5, 0.5, 2, WALL)
    # 东厅 → 楼梯间那条沟上面：一块岩骑在沟上（沟里看是一道石顶），把两段岩脊接上，潟湖那边看不见倒影
    crag("ridge_arch", [(40.0, -4.0), (46.5, -5.0), (47.0, 5.0), (46.0, 14.0), (40.0, 14.0), (39.6, 5.0)],
         -1.2, 6.0, 0.6, 3, WALL)


# ── 第二层：楼梯间的石柱、绕柱的梯、潟湖里的岛 ──────────

STAIR_C = (54.0, 8.0)
PIL_R = 1.9
STEP_N, STEP_RISE = 28, 0.30
STEP_IN, STEP_OUT = PIL_R - 0.05, PIL_R + 2.5
STEP_ANG = 12.6          # 每级转多少度（中线上一级约 0.69m）
STEP_A0 = 17.0           # 第一级的方位角（度，从 +x 起逆时针）；最后一级落在东边

LAND = []       # ("disc", cx, cy, r) / ("rect", cx, cy, yaw, hx, hy)


def in_rect(px, py, cx, cy, yaw, hx, hy):
    a = math.radians(yaw)
    dx, dy = px - cx, py - cy
    return abs(dx * math.cos(a) + dy * math.sin(a)) <= hx and abs(-dx * math.sin(a) + dy * math.cos(a)) <= hy


def land_at(x, y):
    for s in LAND:
        if s[0] == "disc":
            if math.hypot(x - s[1], y - s[2]) <= s[3]:
                return True
        elif in_rect(x, y, *s[1:]):
            return True
    return False


def spiral():
    nx.into("second")
    cx, cy = STAIR_C
    f0 = floor_at(cx + 4, cy)
    # 石柱：从地上穿过水面，再往上立成一根尖
    k = fu.Kit()
    k.lathe([(PIL_R + 0.3, f0 - 0.5), (PIL_R, f0 + 1.0), (PIL_R, 2.0), (PIL_R * 0.8, 6.5), (PIL_R * 0.35, 9.5),
             (0.0, 10.5)], seg=9)
    k.build("stair_pillar", loc=(cx, cy, 0), smooth=0, **WALL)
    # 踏步：一圈扇形，各自一块（中间那一刀让它们有轮廓线）
    st = fu.Kit()
    for i in range(STEP_N):
        a0 = math.radians(STEP_A0 + STEP_ANG * i)
        a1 = math.radians(STEP_A0 + STEP_ANG * (i + 1) + 0.6)
        top = f0 + STEP_RISE * (i + 1)
        bot = top - 0.42
        vs = []
        for a in (a0, a1):
            for r in (STEP_IN, STEP_OUT):
                vs += [(cx + math.cos(a) * r, cy + math.sin(a) * r, bot), (cx + math.cos(a) * r, cy + math.sin(a) * r, top)]
        # 0,1 内下上；2,3 外下上（a0）；4,5 内（a1）；6,7 外（a1）
        faces = [(1, 3, 7, 5), (0, 4, 6, 2), (0, 1, 5, 4), (2, 6, 7, 3), (0, 2, 3, 1), (4, 5, 7, 6)]
        st._add(vs, faces)
    obj = st.build("spiral_steps", smooth=0, ramp=("lilac_dark", "lilac", "lilac_pale"), pattern="plain")
    # 楼梯出水那一截（z > -0.5）算陆地：挡板不拦它
    # 踏步都算「陆地」：潟湖的挡板只拦在楼梯的外沿（出水那一截当栏杆），不拦上下
    for i in range(STEP_N):
        am = math.radians(STEP_A0 + STEP_ANG * (i + 0.5))
        rm = (STEP_IN + STEP_OUT) / 2
        LAND.append(("rect", cx + math.cos(am) * rm, cy + math.sin(am) * rm,
                     math.degrees(am), (STEP_OUT - STEP_IN) / 2 + 0.05, 0.8))
    # 最后一级旁边一座岛（比最后一级高 0.2）
    aE = math.radians(STEP_A0 + STEP_ANG * STEP_N + 12.0)
    return (cx + math.cos(aE) * 6.4, cy + math.sin(aE) * 6.4), f0 + STEP_RISE * STEP_N + 0.2


def isle(name, cx, cy, r, top, seed):
    LAND.append(("disc", cx, cy, r - 0.15))
    rr = random.Random(seed)
    seg = 9
    jit = [rr.uniform(0.9, 1.08) for _ in range(seg)]
    vs, fs = [], []
    for s, z in ((1.12, -1.2), (1.05, 0.0), (1.0, top - 0.25)):
        for k in range(seg):
            a = math.tau * k / seg
            vs.append((cx + math.cos(a) * r * s * jit[k], cy + math.sin(a) * r * s * jit[k], z))
    for k in range(seg):
        a = math.tau * k / seg
        vs.append((cx + math.cos(a) * (r - 0.2) * jit[k], cy + math.sin(a) * (r - 0.2) * jit[k], top))
    for li in range(3):
        for k in range(seg):
            a, b = li * seg + k, li * seg + (k + 1) % seg
            fs.append((a, b, b + seg, a + seg))
    fs.append(tuple(range(3 * seg, 4 * seg)))
    obj = mesh(name, vs, fs, ramp=("lilac_dark", "lilac", "pink_pale"), pattern="grain", top="pink_pale")
    _fix_normals(obj)


def causeway(name, a, b, half, top):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy)
    yaw = math.degrees(math.atan2(-dx, dy))
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    LAND.append(("rect", mx, my, yaw, half - 0.1, L / 2))
    zb = -1.2 - 0.07 * int(name[-1])   # 各条堤的底错开（埋在岛里，免得共面）
    nx.box(name, (2 * half, L, top - zb), (mx, my, zb), (0, 0, yaw), ramp=("violet", "lilac_dark", "lilac"),
           pattern="tiles")


def lagoon(landing, top):
    """潟湖：楼梯顶上一块岩，几座岛用石堤连着，去花房的花瓶在最远那座上"""
    lx, ly = landing
    isle("isle_land", lx, ly, 3.2, top, 11)
    I1, I2, I3, I4 = (67.5, 17.0), (75.0, 9.5), (84.0, 15.0), (73.0, -3.0)
    isle("isle1", *I1, 3.4, 1.65, 12)
    isle("isle2", *I2, 3.6, 1.80, 13)
    isle("isle3", *I3, 4.0, 1.95, 14)
    isle("isle4", *I4, 3.0, 1.80, 15)
    causeway("cw0", (lx, ly), I1, 1.3, 1.45)
    causeway("cw1", I1, I2, 1.3, 1.60)
    causeway("cw2", I2, I3, 1.3, 1.75)
    causeway("cw3", I2, I4, 1.2, 1.60)
    # 潟湖里几块露出水的礁
    for i, (x, y, r, h) in enumerate(((62, -6, 1.6, 0.6), (77, 23, 2.0, 0.9), (88, 4, 1.4, 0.5), (59, 26, 1.8, 0.7))):
        vs, fs = boulder_geo(r, h, 40 + i)
        o = mesh(f"reef{i}", [(x + a, y + b, c) for a, b, c in vs], fs, **STONE)
        _fix_normals(o)
    return I3


def reef_cap():
    """潟湖底下不是洞的地方：贴着水面下的一层礁（从上往下透过水看得见）"""
    vs, fs = [], []
    step = 2.0
    x = 38.0
    while x < 100.0:
        y = -40.0
        while y < 50.0:
            cx, cy = x + step / 2, y + step / 2
            if dist_at(cx, cy) > 4.5 and not (40 <= cx <= 47 and -36 <= cy <= 54):
                o = len(vs)
                vs += [(x, y, -0.03), (x + step, y, -0.03), (x + step, y + step, -0.03), (x, y + step, -0.03)]
                fs.append((o, o + 1, o + 2, o + 3))
            y += step
        x += step
    mesh("reef_cap", vs, fs, collide=False, shadow=False, ramp=("violet", "lilac_dark", "lilac"), pattern="grain")


def fences():
    """看不见的挡板：潟湖的岸（站在岛上走不进水里）"""
    x0, x1, y0, y1, step = 46.0, 92.0, -10.0, 24.0, 0.5
    nx_ = int(round((x1 - x0) / step))
    ny_ = int(round((y1 - y0) / step))
    ok = [[land_at(x0 + (i + 0.5) * step, y0 + (j + 0.5) * step) for i in range(nx_)] for j in range(ny_)]
    vs, fs = [], []
    z0, z1 = -0.3, 4.5

    def quad(ax, ay, bx, by):
        n = len(vs)
        vs.extend([(ax, ay, z0), (bx, by, z0), (bx, by, z1), (ax, ay, z1)])
        fs.extend([(n, n + 1, n + 2, n + 3)])

    for j in range(ny_):
        for i in range(nx_):
            if i + 1 < nx_ and ok[j][i] != ok[j][i + 1]:
                quad(x0 + (i + 1) * step, y0 + j * step, x0 + (i + 1) * step, y0 + (j + 1) * step)
            if j + 1 < ny_ and ok[j][i] != ok[j + 1][i]:
                quad(x0 + i * step, y0 + (j + 1) * step, x0 + (i + 1) * step, y0 + (j + 1) * step)
    obj = mesh("land_fence", vs, fs, shadow=False)
    nx.collider_only(obj)


# ── 出入口 ──────────────────────────────────────

def sand_ring(name, x, y, z, r, rings=3):
    for i in range(rings):
        nx.torus(f"{name}{i}", r + i * 0.7, 0.09, (x, y, z + 0.03), major_seg=48, minor_seg=6,
                 collide=False, shadow=False, ramp=("lilac", "lilac_pale", "mist"), pattern="plain")


SPAWN = (-4.0, 38.5, 196.0)


def exits():
    nx.into("places")
    lx, ly, lz = LIT
    nx.portal("portal_home", (lx, ly, lz + 1.0), "house", at="shoal", mode="walk", radius=1.6)
    sx, sy, yaw = SPAWN
    nx.spawn((sx, sy, floor_at(sx, sy)), facing_deg=yaw)
    nx.arrive("house", (sx, sy, floor_at(sx, sy)), facing_deg=yaw)

    tx, ty = TOWER
    tz = floor_at(tx, ty)
    sand_ring("ring_tower", tx, ty, tz, 2.6)
    nx.entrance("crystal_shoal", (tx, ty, tz + 1.6), "", "")

    gx, gy = HALLS["S"][0]
    gz = floor_at(gx, gy)
    nx.cylinder("seep_hole", 2.0, 2.0, 0.6, (gx, gy, gz - 0.58), segments=32,
                ramp=("ink", "ink", "violet_deep"), pattern="plain")
    nx.torus("seep_rim", 2.15, 0.16, (gx, gy, gz + 0.04), major_seg=32, minor_seg=6,
             collide=False, shadow=False, ramp=("violet_deep", "violet", "lilac_dark"), pattern="plain")
    nx.portal("portal_seeping", (gx, gy, gz + 1.0), "seeping", at="shoal", mode="walk", radius=1.2)


def build(extent=EXTENT):
    nx.into("env")
    nx.sun(SUN)
    nx.atmosphere("ebb", shadow_reach=60, caustics=dict(strength=0.55, y=SEA, size=3.2, depth=10.0))
    nx.sky_sprite("cloud_up", "cloud.heap:4", (0.05, -0.1, 1.0), width=34)

    build_mask()
    nx.into("ground")
    ground()
    walls()
    ripples()
    boulders()
    nx.into("sky")
    water()
    window()
    reflect_only()
    floats()
    ridge()
    landing, top = spiral()
    vase_isle = lagoon(landing, top)
    reef_cap()
    fences()
    nx.into("second")
    pf.gate_vase("shoal", (vase_isle[0] + 0.5, vase_isle[1] + 0.8, 1.95), 120.0)
    exits()


if __name__ == "__main__":
    nx.reset()
    build()
    nx.save_blend("shoal")
    nx.export("shoal")
