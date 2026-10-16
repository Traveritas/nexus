"""浅梦 · 浅滩（shoal-var-3）：长条的田。mockup/shallows-04 的变体（第四轮），底本是第三轮的 shoal.py。

连形状一起换：不是一圈圈围着湾心的同心环，而是**一层层平行的长田**从东往西退下去，像剧场的看台。
田坎（东西向的等高线）笔直，但一层层错着位——有的地方两层挤在一起，有的地方一层宽成一大块。
最下面（西边）是水：先是一片齐踝、齐膝的浅水，再往西是深水，深水里一座孤洲。
南北两头收进崖里（往西退成两个岬角，把长田夹在中间），东边是岸与崖（高处），西边一条亮的海天线。

站在东岸（最高一层，7m 高）往西看：一层层长田往下退，每道坎的背面（朝西）都背着太阳、是一道暗线，
坎上一列列细桩；最下面是水，水里一座白洲。

- 水面停在 0m 不动，水只是看的：浅处直接走下去（齐踝、齐膝），深过 0.8m 的地方有一圈看不见的挡板。
- 每道田坎靠上（东）的一侧一条矮埂，埂上一列列细桩（这一版的记号，也是尺度）。
- 一条长埂从南岸斜穿到孤洲，是这一版的动线；半路一条岔路通到死胡同方台（伸在深水上）。
- 水尺（15m）立在最高一层（干田）；北边几处水洼；长田的水里躺着圆叶与几盏浮灯。
- 孤洲：西边水里的白洲，顶上一圈立石与一枚晶体，西边一座闸（往深水里去的台阶，最下一级 → 沁泫池 seeping）。

出入口：
- 回家：东岸地里嵌着的一只「杯口」——一圈白的杯沿围着一汪水，走进水里 → house（到达点 shoal）。
- 花房：北边岸上一只插花的大瓶，E「凑近」→ glasshouse。
- 沁泫池：闸里台阶的最下面一级（seeping，占位）。
- 晶体：孤洲顶上。

运行：node scripts/blender.cjs build shoal-var-3，网页 ?world=shoal-var-3
"""
import math
import os
import random
import sys

import bmesh

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import furniture as fu  # noqa: E402
import nx  # noqa: E402
import prefabs as pf  # noqa: E402
import shapes as sh  # noqa: E402

EXTENT = 200.0
CENTER = (0, 0)

SEA = 0.0             # 水面（不动）
DEEP = -0.8           # 地面低过它就是深水：一圈看不见的挡板拦着

# 从东往西一层层的高度（米）：干田最亮，越往西越湿、越暗
LAGOON = -2.3         # 深水底
T6 = -0.60            # 齐膝（水面下 0.60）
T5 = -0.20            # 齐踝（水面下 0.20）
T4 = 0.80             # 潮湿地：刚露出水面
T3 = 2.10             # 湿沙
T2 = 3.60             # 干田
T1 = 5.20             # 干田（最高一层田）
BANK = 7.00           # 东岸（看台顶）
ISLE = 1.80           # 孤洲

STEP = 1.0
X0, X1, Y0, Y1 = -80.0, 90.0, -50.0, 50.0
ISLE_C = (-24.0, 0.5)
BANK_U = 31.0         # 东岸坎（BANK 与 T1 之间）所在的 x（y = 0 处）
CLIFF_Y = 33.0        # 南北崖从 |y| 这里开始抬
CLIFF_EX = 45.0       # 东崖从 x 这里开始抬

# 一层一种颜色（分开的物体，田坎上有轮廓线）。三色是「暗（背光/影子）· 中（漂）· 亮（正对太阳）」，
# 平的地面几乎都吃「亮」那一档（太阳仰角 46°，朝上的面 ndl≈0.72），所以明度主要看第三色：
# 岸 → 干田最亮 → 湿沙 → 潮湿地 → 齐踝的水 → 深水 → 崖背光
GROUND = {
    "wet":   dict(ramp=("ink", "violet_deep", "violet_deep"), pattern="grain"),   # 水下的两层田（被水盖住）
    "damp":  dict(ramp=("violet_deep", "violet_deep", "violet"), pattern="drift"),
    "sand":  dict(ramp=("violet_deep", "violet", "lilac_dark"), pattern="drift"),
    "dry":   dict(ramp=("violet", "lilac_dark", "lilac"), pattern="drift"),
    "field": dict(ramp=("lilac", "lilac_pale", "pink_pale"), pattern="drift"),
    "bank":  dict(ramp=("violet", "lilac", "lilac_pale"), pattern="drift"),
    "isle":  dict(ramp=("lilac", "lilac_pale", "mist"), pattern="drift"),
    "cliff": dict(ramp=("ink", "violet_deep", "violet_deep"), pattern="bands"),
}
# 水：按底下多深分三种，都压在蓝的一列（不然受光后落到淡紫上，看不出是水）
WATER = {
    "shallow": dict(ramp=("violet", "blue", "blue"), pattern="flow"),
    "knee": dict(ramp=("violet_deep", "violet", "violet"), pattern="flow"),
    "deep": dict(ramp=("ink", "violet_deep", "violet_deep"), pattern="flow"),
}
BUND = dict(ramp=("lilac", "lilac_pale", "mist"), pattern="plain")
RIDGE_STYLE = dict(ramp=("lilac", "mist", "white"), pattern="tiles")
STAKE = dict(a="white", b="mist", pattern="plain")


def ss(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def facing(dx, dy):
    """朝 (dx, dy) 看的 facing_deg（同 spawn：0 ＝ +Y，90 ＝ −X）"""
    return math.degrees(math.atan2(-dx, dy))


# ── 地形：一层层平行的长田，从东往西退下去 ──────────────

def bend(y):
    """整片长田从东往西的坐标上的一点弯：田坎不是死直的，南北两头微微往里收"""
    return 2.6 * math.sin(y / 27.0 + 0.45) + 1.1 * math.sin(y / 10.5 - 0.8)


def u_of(x, y):
    """从东往西的坐标：东岸坎（BANK 与 T1 之间）为 0，往西变大"""
    return (BANK_U - x) + bend(y)


def at_u(y, u):
    """在 y 这一行上、从东往西坐标为 u 的那一点"""
    return BANK_U + bend(y) - u, y


# 田坎：(从东往西的坐标, 下面那层, 上面那层, 坎的半宽)。半宽大一点，高差就有 40° 上下的坡，上下都走得过
EDGES = [
    (0.0, T1, BANK, 1.5),          # 东岸坎（最高一道）
    (6.0, T2, T1, 1.4),
    (12.0, T3, T2, 1.4),
    (18.0, T4, T3, 1.4),
    (24.0, T5, T4, 1.3),
    (30.0, T6, T5, 1.2),
    (36.0, LAGOON, T6, 1.4),       # 深水的沿：水下的挡板就立在这条线上
]
# 每道坎各自歪一点（错位）：有的地方两层挤在一起，有的地方一层宽成一大块
WIGGLE = [(0.0, 1.0, 0.0), (2.4, 18.0, 0.4), (2.0, 13.5, 2.3), (2.3, 20.0, 4.1), (1.8, 11.5, 1.2), (2.2, 16.0, 3.3), (1.9, 14.0, 5.0)]


def edge_at(i, y):
    """第 i 道坎在 y 这一行上的位置（u）。岸坎不歪，其余各自歪一点"""
    base = EDGES[i][0]
    if i == 0:
        return 0.0
    a, l, p = WIGGLE[i]
    return base + a * math.sin(y / l + p) + 0.55 * math.sin(y / 5.4 + 1.9 * i)


def cliff_h(x, y):
    """南北两头与东边的崖：往西退成两个岬角，把长田夹在中间（西边是水与海天线）"""
    head = ss(-40.0, -26.0, x)
    t = max(ss(CLIFF_Y, CLIFF_Y + 3.5, abs(y)) * head, ss(CLIFF_EX, CLIFF_EX + 3.5, x))
    if t <= 0.0:
        return 0.0
    top = 10.5 + 2.5 * math.sin(x / 8.5 + 0.7) * math.cos(y / 12.0) + 1.5 * math.sin((x - y) / 6.0 + 0.5)
    return t * top


def isle_ri(a):
    """孤洲的轮廓半径（各方向不一样）"""
    return 8.6 + 1.8 * math.sin(3 * a + 0.9) + 0.9 * math.sin(5 * a + 2.0)


def isle_h(x, y):
    """孤洲：从深水里抬起来的一块台地，顶心微微隆起"""
    dx, dy = x - ISLE_C[0], y - ISLE_C[1]
    d = math.hypot(dx, dy)
    ri = isle_ri(math.atan2(dy, dx))
    h = LAGOON + (ISLE - LAGOON) * ss(ri + 3.6, ri - 0.8, d)
    h += 0.30 * ss(ri - 1.0, 0.0, d)
    return h


def height(x, y):
    u = u_of(x, y)
    z = LAGOON
    for i, (_, lo, hi, w) in enumerate(EDGES):
        z += (hi - lo) * ss(edge_at(i, y) + w, edge_at(i, y) - w, u)
    z += cliff_h(x, y)
    return max(z, isle_h(x, y))


def flip_up(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    bm.to_mesh(obj.data)
    bm.free()


def grid_parts(classify, zfun):
    """把整片网格按格子分类，各类拼成一份网格：classify(四角的高, 格心) → 类名或 None，zfun(顶点的高) → 这个点的高"""
    nxs = int(round((X1 - X0) / STEP))
    nys = int(round((Y1 - Y0) / STEP))
    hs = [height(X0 + i * STEP, Y0 + j * STEP) for j in range(nys + 1) for i in range(nxs + 1)]
    parts = {}
    for j in range(nys):
        for i in range(nxs):
            q = [j * (nxs + 1) + i, j * (nxs + 1) + i + 1, (j + 1) * (nxs + 1) + i + 1, (j + 1) * (nxs + 1) + i]
            key = classify([hs[v] for v in q], X0 + (i + 0.5) * STEP, Y0 + (j + 0.5) * STEP)
            if key is None:
                continue
            vs, fs, idx = parts.setdefault(key, ([], [], {}))
            ids = []
            for v in q:
                if v not in idx:
                    idx[v] = len(vs)
                    vi, vj = v % (nxs + 1), v // (nxs + 1)
                    vs.append((X0 + vi * STEP, Y0 + vj * STEP, zfun(hs[v])))
                ids.append(idx[v])
            if (i + j) % 2:
                fs += [(ids[0], ids[1], ids[2]), (ids[0], ids[2], ids[3])]
            else:
                fs += [(ids[0], ids[1], ids[3]), (ids[1], ids[2], ids[3])]
    return parts


def terrain():
    def classify(zs, cx, cy):
        zmax = max(zs)
        if zmax < LAGOON + 0.05:
            return None     # 深水底：水不透明，看不见，也走不到
        if abs(cy) > CLIFF_Y + 5.0 or cx > CLIFF_EX + 5.0:
            return None     # 崖顶那道看不见的墙外面：站不上去，也看不出去（省一大片平顶）
        if math.hypot(cx - ISLE_C[0], cy - ISLE_C[1]) < 15.0 and zmax > -1.0:
            return "isle"
        if zmax < 0.05:
            return "wet"
        if zmax < 1.45:
            return "damp"
        if zmax < 2.85:
            return "sand"
        if zmax < 4.40:
            return "dry"
        if zmax < 6.10:
            return "field"
        if zmax < 8.2:
            return "bank"
        return "cliff"

    for name, (vs, fs, _) in grid_parts(classify, lambda z: z).items():
        k = fu.Kit()
        k._add(vs, fs)
        obj = k.build(f"ground_{name}", smooth=179 if name == "cliff" else 50, **GROUND[name])
        flip_up(obj)


def walls():
    """崖顶一圈看不见的墙（保险；西边是深水，深水的挡板就是边）"""
    for x in range(-36, 58, 6):
        for sy in (-1, 1):
            nx.collider_only(nx.box(f"wall_ns{sy}_{x}", (6.5, 0.6, 48), (x, sy * 38.0, -6)))
    for y in range(-38, 39, 6):
        nx.collider_only(nx.box(f"wall_e_{y}", (0.6, 6.5, 48), (50.0, y, -6)))


# ── 走得到的地方 ─────────────────────────────────
# 长埂、岔路、方台、闸这些「深水里的实地」，挡板要让开它们

RIDGE_W = 2.6
RIDGE_TOP = SEA + 0.30
BRANCH_TOP = SEA + 0.26     # 岔路比长埂低 4cm：接得上、迈得过，两块也不共面
SOLID = []      # (判断函数)：点在这些东西的脚下 → 不是深水


def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - dx * t, py - ay - dy * t)


def in_rect(px, py, cx, cy, yaw, hx, hy, oy=0.0):
    """点是否在一块转了 yaw 度的矩形里（本地 x ∈ ±hx，y ∈ oy ± hy）"""
    a = math.radians(yaw)
    dx, dy = px - cx, py - cy
    lx = dx * math.cos(a) + dy * math.sin(a)
    ly = -dx * math.sin(a) + dy * math.cos(a)
    return abs(lx) <= hx and abs(ly - oy) <= hy


def deep_at(x, y):
    if height(x, y) >= DEEP:
        return False
    return not any(f(x, y) for f in SOLID)


def deep_fence():
    """深水的挡板：0.5m 一格，深水格与非深水格之间立一片看不见的墙（−3 到 +2.5m）"""
    h = 0.5
    xs = [X0 + i * h for i in range(int((X1 - X0) / h) + 1)]
    ys = [Y0 + j * h for j in range(int((Y1 - Y0) / h) + 1)]
    deep = [[deep_at(x + h / 2, y + h / 2) for x in xs[:-1]] for y in ys[:-1]]
    vs, fs = [], []
    z0, z1 = -3.0, 2.5

    def quad(ax, ay, bx, by):
        n = len(vs)
        vs.extend([(ax, ay, z0), (bx, by, z0), (bx, by, z1), (ax, ay, z1)])
        fs.extend([(n, n + 1, n + 2), (n, n + 2, n + 3)])

    nyc, nxc = len(deep), len(deep[0])
    for j in range(nyc):
        for i in range(nxc):
            if i + 1 < nxc and deep[j][i] != deep[j][i + 1]:
                x = xs[i + 1]
                quad(x, ys[j], x, ys[j + 1])
            if j + 1 < nyc and deep[j][i] != deep[j + 1][i]:
                y = ys[j + 1]
                quad(xs[i], y, xs[i + 1], y)
    k = fu.Kit()
    k._add(vs, fs)
    obj = k.build("deep_fence", smooth=0, shadow=False)
    nx.collider_only(obj)


# ── 水 ──────────────────────────────────────────

def sea():
    """水面停在 SEA：网格范围里按底下多深分三种颜色，范围外一圈深水接到天边"""
    def classify(zs, cx, cy):
        if min(zs) >= SEA - 0.02:
            return None
        z = height(cx, cy)
        if z > -0.35:
            return "shallow"
        if z > DEEP - 0.15:
            return "knee"
        return "deep"

    for name, (vs, fs, _) in grid_parts(classify, lambda z: SEA).items():
        k = fu.Kit()
        k._add(vs, fs)
        obj = k.build(f"water_{name}", smooth=0, collide=False, shadow=False, **WATER[name])
        flip_up(obj)
    # 网格外：四块大片
    R = 420.0
    for name, (cx, cy, sx, sy) in {
        "w": ((X0 - R) / 2, 0, R + X0, 2 * R), "e": ((X1 + R) / 2, 0, R - X1, 2 * R),
        "s": ((X0 + X1) / 2, (Y0 - R) / 2, X1 - X0, R + Y0), "n": ((X0 + X1) / 2, (Y1 + R) / 2, X1 - X0, R - Y1),
    }.items():
        nx.plane(f"water_far_{name}", abs(sx), abs(sy), (cx, cy, SEA), collide=False, shadow=False, **WATER["deep"])


# ── 田埂与细桩 ───────────────────────────────────

def bund_run(idx, pts, hi):
    """沿一串点砌一条矮埂（高出田面 0.18m，迈得过去）"""
    top = hi + 0.18
    k = fu.Kit()
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        L = math.hypot(bx - ax, by - ay)
        if L > 3.0:
            continue
        ang = math.degrees(math.atan2(by - ay, bx - ax))
        k.box((L + 0.40, 0.40, top - (hi - 0.30)), ((ax + bx) / 2, (ay + by) / 2, hi - 0.30), rot=(0, 0, ang))
    k.build(f"bund{idx}", smooth=0, **BUND)


def bund_paths():
    """每道坎靠上（东）的一侧一条埂的中心线：[(坎号, 上层高度, [点…])]；被崖、孤洲、挤在一起的地方断开"""
    out = []
    for i in range(len(EDGES)):
        _, _, hi, w = EDGES[i]
        if hi < 0.05:
            continue                    # 水下的那两道不砌埂
        pts = []
        y = -CLIFF_Y + 1.2
        while y <= CLIFF_Y - 1.2:
            px, py = at_u(y, edge_at(i, y) - (w + 0.4))
            if abs(height(px, py) - hi) < 0.07:
                pts.append((px, py))
            else:
                if len(pts) > 1:
                    out.append((i, hi, pts))
                pts = []
            y += 0.7
        if len(pts) > 1:
            out.append((i, hi, pts))
    return out


def bunds():
    """田坎上的矮埂，返回所有埂上的点（后面撒东西时让开）"""
    paths = bund_paths()
    for n, (_, hi, pts) in enumerate(paths):
        bund_run(n, pts, hi)
    return paths


def stakes(paths, ridge_pts):
    """细桩：田埂上一列一列，长埂两侧一路（读作尺度，也是这一版的记号）"""
    k = fu.Kit()
    for _, hi, pts in paths:
        acc = 0.0
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            L = math.hypot(bx - ax, by - ay)
            acc += L
            if acc < 2.4:
                continue
            acc = 0.0
            h = 0.85 + 0.35 * math.sin((ax + ay) / 3.1)
            k.box((0.14, 0.14, h + 0.06), (ax, ay, hi + 0.13))
    # 长埂两侧：隔 2.6m 一根，左右交替
    acc = 0.0
    for (ax, ay, az), (bx, by, _) in zip(ridge_pts, ridge_pts[1:]):
        L = math.hypot(bx - ax, by - ay)
        if L < 1e-6:
            continue
        nx_, ny_ = -(by - ay) / L, (bx - ax) / L
        t = 0.0
        while t < L:
            px, py = ax + (bx - ax) * t / L, ay + (by - ay) * t / L
            side = 1 if int((acc + t) / 2.6) % 2 else -1
            k.box((0.14, 0.14, 1.0), (px + nx_ * side * (RIDGE_W / 2 - 0.14), py + ny_ * side * (RIDGE_W / 2 - 0.14), az - 0.02))
            t += 2.6
        acc += L
    k.build("stakes", smooth=0, collide=False, **STAKE)


# ── 长埂：从南岸斜穿到孤洲 ────────────────────────

RIDGE_PTS = [(37.0, -26.0), (18.0, -19.5), (0.0, -12.5), (-9.5, -6.0), (-17.5, -0.5)]
BRANCH_FROM = (5.8, -14.7)
PLATFORM = (-9.0, -28.0)


def ribbon(kit, pts, tops, width, zbot):
    """把一串点拉成一条长埂：顶面是斜的（走上去是一段缓坡），下面一直埋到水底"""
    verts, faces = [], []
    n = len(pts)
    for i, (px, py) in enumerate(pts):
        j, k = min(i + 1, n - 1), max(i - 1, 0)
        dx, dy = pts[j][0] - pts[k][0], pts[j][1] - pts[k][1]
        L = math.hypot(dx, dy) or 1.0
        nx_, ny_ = -dy / L, dx / L
        verts += [(px - nx_ * width / 2, py - ny_ * width / 2, tops[i]),
                  (px + nx_ * width / 2, py + ny_ * width / 2, tops[i]),
                  (px - nx_ * width / 2, py - ny_ * width / 2, zbot),
                  (px + nx_ * width / 2, py + ny_ * width / 2, zbot)]
    for i in range(n - 1):
        a, b = i * 4, (i + 1) * 4
        faces += [(a, a + 1, b + 1, b), (a + 2, b + 2, b + 3, a + 3),
                  (a, b, b + 2, a + 2), (a + 1, a + 3, b + 3, b + 1)]
    faces += [(0, 1, 3, 2), ((n - 1) * 4, (n - 1) * 4 + 2, (n - 1) * 4 + 3, (n - 1) * 4 + 1)]
    kit._add(verts, faces)


def polyline(pts, spacing=0.8):
    out = []
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        L = math.hypot(bx - ax, by - ay)
        m = max(1, int(L / spacing))
        for i in range(m):
            t = i / m
            out.append((ax + (bx - ax) * t, ay + (by - ay) * t))
    out.append(pts[-1])
    return out


def ridge():
    """长埂：从南岸斜穿到孤洲，是这一版的动线。埂面高出脚下的地 0.28m（迈得上去），
    深水上露出水面 0.30m——一路走得过去；半路一条岔路通到死胡同方台"""
    pts = polyline(RIDGE_PTS)
    tops = [max(RIDGE_TOP, height(px, py) + 0.28) for px, py in pts]
    k = fu.Kit()
    ribbon(k, pts, tops, RIDGE_W, LAGOON - 0.40)
    k.build("ridge", smooth=0, **RIDGE_STYLE)

    # 岔路：从长埂半路往南，通到深水上的方台（比长埂低一点，两块不共面）
    bpts = polyline([BRANCH_FROM, PLATFORM])
    btops = [max(BRANCH_TOP, height(px, py) + 0.24) for px, py in bpts]
    bk = fu.Kit()
    ribbon(bk, bpts, btops, RIDGE_W * 0.85, LAGOON - 0.62)
    bk.build("ridge_branch", smooth=0, **RIDGE_STYLE)
    # 方台：比埂面高 0.29（迈得上去），死胡同
    nx.box("ridge_end", (3.8, 3.8, BRANCH_TOP + 0.29 - LAGOON + 0.82), (PLATFORM[0], PLATFORM[1], LAGOON - 0.82),
           (0, 0, 24), **RIDGE_STYLE)

    # 挡板要让开整条埂（埂面上走人，脚下不是深水）
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        SOLID.append(lambda px, py, ax=ax, ay=ay, bx=bx, by=by: seg_dist(px, py, ax, ay, bx, by) < RIDGE_W / 2 - 0.05)
    for (ax, ay), (bx, by) in zip(bpts, bpts[1:]):
        SOLID.append(lambda px, py, ax=ax, ay=ay, bx=bx, by=by: seg_dist(px, py, ax, ay, bx, by) < RIDGE_W * 0.42 - 0.05)
    SOLID.append(lambda px, py: in_rect(px, py, PLATFORM[0], PLATFORM[1], 24, 1.85, 1.85))
    return list(zip([p[0] for p in pts], [p[1] for p in pts], tops))


# ── 孤洲上 ──────────────────────────────────────

def isle_marks():
    """孤洲顶上的一圈立石：给这座白洲一点分量，也把晶体围在中间"""
    rnd = random.Random(31)
    k = fu.Kit()
    n = 7
    for i in range(n):
        a = math.tau * i / n + 0.35
        d = 4.6 + rnd.uniform(-0.4, 0.4)
        px = ISLE_C[0] + math.cos(a) * d
        py = ISLE_C[1] + math.sin(a) * d
        z = height(px, py)
        h = rnd.uniform(1.5, 2.6)
        w = rnd.uniform(0.55, 0.85)
        k.box((w, w * 0.62, h + 0.3), (px, py, z - 0.3), rot=(0, 0, math.degrees(a) + 90))
    k.build("isle_stones", smooth=0, ramp=("violet", "lilac_dark", "lilac_pale"), pattern="bands")


LOCK_STEPS = [0.6, 0.28, -0.03, -0.32, -0.62, -0.92]


def lock(x, y, yaw):
    """孤洲西边的闸：三面矮墙围着一段往深水里去的台阶（本地 +Y 朝外、往下）。走到最下面一级 → 沁泫池"""
    g = nx.group("lock", (x, y, 0), (0, 0, yaw))
    w = 3.0
    k = fu.Kit()
    for i, zt in enumerate(LOCK_STEPS):
        k.box((w, 1.0, zt - LAGOON + 0.3), (0, 1.0 + i * 1.0, LAGOON - 0.3))
    k.build("lock_steps", parent=g, smooth=0, a="mist", b="lilac_pale", pattern="tiles")
    L = len(LOCK_STEPS) * 1.0 + 1.0
    for s in (-1, 1):
        nx.box(f"lock_wall{s}", (0.6, L, 1.05 - LAGOON), (s * (w / 2 + 0.3), 0.5 + L / 2, LAGOON), parent=g,
               ramp=("violet", "lilac_dark", "lilac"), pattern="bands")
    nx.box("lock_end", (w + 1.2, 0.6, 1.05 - LAGOON), (0, 0.8 + L, LAGOON), parent=g,
           ramp=("violet", "lilac_dark", "lilac"), pattern="bands")
    i = len(LOCK_STEPS) - 1
    a = math.radians(yaw)
    ly = 1.0 + i * 1.0
    px, py = x - math.sin(a) * ly, y + math.cos(a) * ly
    nx.portal("portal_seeping", (px, py, LOCK_STEPS[i] + 1.0), "seeping", mode="walk", radius=0.8)
    # 闸里（台阶加两边的墙）都算实地
    SOLID.append(lambda qx, qy: in_rect(qx, qy, x, y, yaw, w / 2 + 0.6, (L + 1.4) / 2, oy=0.5 + L / 2))


# ── 内容 ────────────────────────────────────────

def flat_spot(u_lo, u_hi, y_lo, y_hi, r, rnd, avoid):
    """找一块平地（半径 r 内高差不到 4cm），东西不压在田坎上"""
    for _ in range(300):
        y = rnd.uniform(y_lo, y_hi)
        px, py = at_u(y, rnd.uniform(u_lo, u_hi))
        zs = [height(px + math.cos(a) * r, py + math.sin(a) * r) for a in (i * math.tau / 10 for i in range(10))]
        zs.append(height(px, py))
        if max(zs) - min(zs) > 0.04:
            continue
        if any(math.hypot(px - ax, py - ay) < ar + r for ax, ay, ar in avoid):
            continue
        return px, py
    return None


def pools():
    """北边几处水洼：一圈矮沿（高出地面 0.3m，迈得上去）围着一汪水"""
    rnd = random.Random(5)
    placed = []
    for i in range(14):
        r = rnd.uniform(1.2, 2.6)
        spot = flat_spot(1.5, 11.0, 13.0, 28.0, r + 0.4, rnd, [(x, y, rr + 2.0) for x, y, rr in placed])
        if spot is None:
            continue
        px, py = spot
        placed.append((px, py, r))
        z = height(px, py)
        sh.tube(f"pool{i}_rim", r + 0.3, r, 0.4, (px, py, z - 0.1), segments=24, a="white", b="mist", pattern="plain")
        nx.cylinder(f"pool{i}_bed", r + 0.05, r + 0.05, 0.12, (px, py, z - 0.1), segments=24,
                    a="lilac", b="lilac_dark", pattern="grain")
        nx.cylinder(f"pool{i}_water", r - 0.02, r - 0.02, 0.02, (px, py, z + 0.14), segments=24,
                    collide=False, shadow=False, **WATER["shallow"])
        if len(placed) >= 3:
            break
    return placed


def gauge(x, y, h=15.0):
    """水尺：一道道刻度（白与深紫相间，每 0.3m 一格，每 1.5m 一道长的），顶上一点金。立在最高一层（干田）"""
    z0 = height(x, y) + 0.22
    nx.box("gauge_base", (1.7, 1.7, 0.26), (x, y, z0 - 0.26), (0, 0, 18), a="lilac_pale", b="lilac", pattern="tiles")
    light, dark = fu.Kit(), fu.Kit()
    n = int(h / 0.3)
    for i in range(n):
        k = dark if i % 2 else light
        wide = 0.62 if i % 5 == 0 else 0.42
        k.box((wide, 0.42, 0.3), (0, 0, i * 0.3))
    # 刻度一格格凸出来，挡人的话会被当成台阶爬上去：刻度本身不挡人，另立一根看不见的方柱
    light.build("gauge_light", loc=(x, y, z0), rot=(0, 0, 18), smooth=0, collide=False, a="white", b="mist", pattern="plain")
    dark.build("gauge_dark", loc=(x, y, z0), rot=(0, 0, 18), smooth=0, collide=False, a="violet", b="violet_deep", pattern="plain")
    nx.collider_only(nx.box("gauge_col", (0.7, 0.7, h + 1.2), (x, y, z0), (0, 0, 18)))
    top = fu.Kit()
    top.lathe([(0.0, 0.0), (0.45, 0.5), (0.0, 1.1)], seg=4)
    top.build("gauge_top", loc=(x, y, z0 + n * 0.3), rot=(0, 0, 18), smooth=0, collide=False, a="gold", b="white", pattern="plain")


def cup(x, y):
    """杯口：东岸地里嵌着一圈白的杯沿，里面一汪水。走进水里回家"""
    z = height(x, y)
    R = 2.2
    nx.torus("cup_rim", R + 0.15, 0.17, (x, y, z + 0.1), major_seg=40, minor_seg=8, a="white", b="mist", pattern="plain")
    nx.cylinder("cup_bed", R, R, 0.3, (x, y, z - 0.32), segments=32, a="blue", b="blue_pale", pattern="plain")
    nx.cylinder("cup_water", R + 0.02, R + 0.02, 0.02, (x, y, z + 0.04), segments=32, collide=False, shadow=False,
                **WATER["shallow"])
    nx.portal("portal_home", (x, y, z + 1.0), "house", at="shoal", mode="walk", radius=1.3)


def leaves(avoid):
    """长田的水里躺着几片圆叶（贴着水，不挡人）；彼此不叠，微微高低错开（不然共面会闪）"""
    rnd = random.Random(11)
    placed = []
    for i in range(400):
        y = rnd.uniform(-CLIFF_Y + 1.5, CLIFF_Y - 1.5)
        px, py = at_u(y, rnd.uniform(23.5, 33.0))
        if height(px, py) > -0.12:
            continue
        if math.hypot(px - ISLE_C[0], py - ISLE_C[1]) < 12.5:
            continue
        if any(math.hypot(px - ax, py - ay) < ar + 2.5 for ax, ay, ar in avoid):
            continue
        r = rnd.uniform(0.7, 1.5)
        if any(math.hypot(px - ax, py - ay) < r + ar + 0.5 for ax, ay, ar in placed):
            continue
        placed.append((px, py, r))
        n = len(placed) - 1
        nx.cylinder(f"leaf{n}", r, r, 0.08, (px, py, SEA - 0.02 + rnd.uniform(-0.05, 0.05)), segments=14, collide=False,
                    a="pink_pale" if n % 3 else "pink", b="rose", pattern="plain")
        if len(placed) >= 22:
            break
    return placed


def lamps(avoid, leaves_at):
    """几盏浮灯：水上一只小筏子托着一盏亮的（自己发光，慢慢上下浮）"""
    rnd = random.Random(7)
    n = 0
    for i in range(400):
        y = rnd.uniform(-CLIFF_Y + 2.0, CLIFF_Y - 2.0)
        px, py = at_u(y, rnd.uniform(26.0, 40.0))
        if height(px, py) > -0.30:
            continue
        if math.hypot(px - ISLE_C[0], py - ISLE_C[1]) < 12.0:
            continue
        if any(math.hypot(px - ax, py - ay) < ar + 4.0 for ax, ay, ar in avoid):
            continue
        if any(math.hypot(px - ax, py - ay) < ar + 2.0 for ax, ay, ar in leaves_at):
            continue
        nx.cylinder(f"float{n}_raft", 0.62, 0.56, 0.14, (px, py, SEA - 0.05), segments=12, collide=False,
                    a="violet", b="violet_deep", pattern="plain")
        lamp = nx.cylinder(f"float{n}_lamp", 0.42, 0.30, 0.52, (px, py, SEA + 0.09), segments=10, collide=False,
                           emit=1, a="gold", b="white", pattern="plain")
        nx.behave(lamp, bob=0.06)
        n += 1
        if n >= 4:
            break


def build(extent=EXTENT):
    nx.into("env")
    nx.sun((0.42, -0.55, 0.72))
    nx.atmosphere("ebb")

    nx.into("things")
    ridge_pts = ridge()
    gx, gy = at_u(8.0, 5.5)
    gauge(gx, gy)
    # 闸：从洲心往西走到地面落到 0.75 的地方，第一级台阶（0.6）就从那里接出去
    ld = (-math.sin(math.radians(100)), math.cos(math.radians(100)))
    t = 0.0
    while height(ISLE_C[0] + ld[0] * t, ISLE_C[1] + ld[1] * t) > 0.75:
        t += 0.1
    lock(ISLE_C[0] + ld[0] * (t - 1.0), ISLE_C[1] + ld[1] * (t - 1.0), 100)
    isle_marks()

    # 孤洲顶上的晶体
    cx, cy = ISLE_C[0] + 0.5, ISLE_C[1] + 0.3
    nx.entrance("crystal", (cx, cy, height(cx, cy) + 1.6), "", "", size=0.42)

    # 东岸：杯口（回家）与出生点。出生点退到岸沿上（前面就是第一道坎），一眼看见一层层往西退下去
    ux, uy = at_u(-10.0, -5.0)
    cup(ux, uy)
    sx, sy = at_u(3.0, -4.2)
    yaw = facing(-1, -0.05)
    nx.spawn((sx, sy, height(sx, sy)), facing_deg=yaw)
    nx.arrive("house", (sx, sy, height(sx, sy)), facing_deg=yaw)

    nx.into("pools")
    placed = pools()
    # 花房：北边岸上的花瓶
    vx, vy = at_u(20.0, -4.0)
    pf.gate_vase("shoal-var-3", (vx, vy, height(vx, vy)), 150.0)

    nx.into("ground")
    terrain()
    avoid = [(ux, uy, 5.0), (sx, sy, 5.0), (vx, vy, 5.0), (gx, gy, 4.5), (cx, cy, 12.0)]
    avoid += [(x, y, r + 2.0) for x, y, r in placed]
    avoid += [(p[0], p[1], 3.2) for p in ridge_pts[::6]]
    paths = bunds()
    stakes(paths, ridge_pts)
    walls()
    deep_fence()

    nx.into("water")
    sea()
    leaves_at = leaves(avoid)
    lamps(avoid, leaves_at)


if __name__ == "__main__":
    nx.reset()
    build()
    nx.save_blend("shoal-var-3")
    nx.export("shoal-var-3")
