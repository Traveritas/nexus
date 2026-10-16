"""浅梦 · 浅滩变体一（shoal-var-1）：浅水田。

把「水」当内容：一圈圈浅水田从东岸往湾心退下去，**每层田有自己的水位**，
水从高的一层溢到低的一层（每道田坎一个溢流口，挂一道细白的水线）。
人在田埂上走、在浅水里蹚。

- 地形还是解析函数 height(x, y)：湾心深水 LAGOON，东/北/南三面崖，西边敞开是深水（边）。
  田坎 EDGES 一层层往湾心退，每层田约 6.5m 宽。
- **水位** water_level(x, y)：每层田一个水位（田面 + 0.22m），台阶落在每道田埂上——
  水被田埂拢住，只在溢流口溢到下一层。水面用纹样「流」，五档明暗从高到低一路压深。
- 明度：干岸最亮最暖、崖中暗、深水底最暗；水从亮蓝一路到近黑紫。一层占一档，不再糊在一起。
- 内容：15m 水尺（最高一层）、22 块潮石（6.2m 那道横纹连成空中一条水平线）、
  孤洲（顶上晶体，一圈立石有分量）、闸（孤洲西边往深水里去的台阶）、圆叶（躺在水面上）、
  几盏浮灯（浮在水面轻轻上下）、宽埂与一条到死水里方台的岔路、北边水洼。

出入口（照旧）：
- 回家：东岸地里嵌着的一只「杯口」（白杯沿围着一汪水），走进水里 → house（at="shoal"）。
- 花房：北边一只插花的大瓶，E「凑近」→ glasshouse（落在那边的到达点 shoal-var-1）。
- 沁泫池：闸里台阶的最下面一级（seeping，占位）。
- 晶体：孤洲顶上（站点待定）。
出生点＝到达点 house，在东岸，朝西。

运行：node scripts/blender.cjs build shoal-var-1，网页 ?world=shoal-var-1
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

EXTENT = 180.0
CENTER = (0, 0)

# ── 高与水的尺 ──────────────────────────────────────
LAGOON = -2.8         # 湾心的深水底
T4 = -1.1             # 最低一层田（离湾心最近）
T3 = -0.2
T2 = 0.7
T1 = 1.6              # 最高一层田（离岸最近）
BANK = 3.2            # 东岸（干）
ISLE = 1.0            # 孤洲顶

WD = 0.22             # 每层田的水深
W1, W2, W3, W4 = T1 + WD, T2 + WD, T3 + WD, T4 + WD     # 1.82 / 0.92 / 0.02 / -0.88
SEA = -1.7            # 湾心与西边深水的水面
DEEP = -1.95          # 地面低过它就是深水：一圈看不见的挡板拦着
MARK = 6.2            # 潮石上那道横纹的高度：这片湾记得的一次水位

BUND_H = 0.30         # 田埂高出上层田面
STEP = 1.0
X0, X1, Y0, Y1 = -58.0, 58.0, -54.0, 54.0
ISLE_C = (-4.0, 5.0)

# 田坎：(离深水外沿多远的基准, 下面那层, 上面那层, 坎的半宽)
EDGES = [(0.0, LAGOON, T4, 0.80), (6.5, T4, T3, 0.65), (13.0, T3, T2, 0.65),
         (19.5, T2, T1, 0.65), (26.0, T1, BANK, 0.90)]

# 每层的水位（湾心＝SEA；岸上没有水，取最高一层的水位，反正岸比它高）
WLEV = {LAGOON: SEA, T4: W4, T3: W3, T2: W2, T1: W1, BANK: W1}

# 溢流口的方位（度）：一道田埂一个，都放在出生点正西那一片，一层层看得见
SPILL = {0: -7.0, 1: 2.5, 2: -3.0, 3: 9.5}

# 地面：一层一种明度，越低越暗越湿（分开的物体，田坎上有轮廓线）；干的一列偏暖、水偏冷
GROUND = {
    "floor": dict(ramp=("ink", "ink", "violet_deep"), pattern="grain"),             # 湾心深水底：最暗
    "t4": dict(ramp=("ink", "violet_deep", "violet"), pattern="grain"),
    "t3": dict(ramp=("violet_deep", "violet", "rose_deep"), pattern="grain"),
    "t2": dict(ramp=("violet", "rose_deep", "rose"), pattern="drift"),
    "t1": dict(ramp=("rose_deep", "rose", "pink"), pattern="drift"),
    "bank": dict(ramp=("lilac", "pink", "pink_pale"), pattern="drift"),             # 干岸：最亮最暖
    "cliff": dict(ramp=("violet", "lilac_dark", "lilac"), pattern="bands"),
    "isle": dict(ramp=("rose_deep", "rose", "pink"), pattern="grain", top="green"),
}
# 水：一层一种明暗，从最高一层（亮蓝）一路压到湾心（暗紫）；都用纹样「流」
WATER = {
    "w1": dict(ramp=("lilac", "blue", "blue_pale"), pattern="flow"),
    "w2": dict(ramp=("violet", "lilac", "blue"), pattern="flow"),
    "w3": dict(ramp=("violet_deep", "violet", "lilac_dark"), pattern="flow"),
    "w4": dict(ramp=("ink", "violet_deep", "violet"), pattern="flow"),
    "deep": dict(ramp=("ink", "ink", "violet_deep"), pattern="flow"),
}
STONE = dict(ramp=("lilac_dark", "lilac_pale", "mist"), pattern="grain")
MARK_STYLE = dict(a="violet_deep", b="violet", pattern="plain")
BUND_STYLE = dict(ramp=("violet", "rose_deep", "rose"), pattern="plain")
SPILL_STYLE = dict(a="white", b="blue_pale", pattern="stripes")


# ── 基本工具 ────────────────────────────────────────

def ss(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def facing(dx, dy):
    """朝 (dx, dy) 看的 facing_deg（同 spawn：0 ＝ +Y，90 ＝ −X）"""
    return math.degrees(math.atan2(-dx, dy))


# ── 地形与水 ────────────────────────────────────────

def lagoon_r(th):
    """湾心深水的外沿半径；西边敞开，一直是深水"""
    r = 9.0 + 1.7 * math.sin(2 * th + 0.5) + 1.2 * math.sin(3 * th + 1.7) + 0.7 * math.sin(5 * th + 0.3)
    opening = ss(-0.5, -0.85, math.cos(th))
    return r + opening * 120.0


def warp(x, y):
    return (2.3 * math.sin(x / 13.0 + 0.7) * math.cos(y / 11.0 - 0.4) + 1.2 * math.sin((x + y) / 7.0 + 1.1)
            + 0.6 * math.sin(x / 3.6 - y / 5.0))


def bay_s(x, y):
    """离深水外沿有多远（米，往岸上为正）"""
    r = math.hypot(x, y)
    th = math.atan2(y, x)
    return r - lagoon_r(th) + warp(x, y)


def step_(s, at, w=0.7):
    return ss(at - w, at + w, s)


def wide_at(th):
    """每层田的宽窄：东边宽、南北窄（崖逼得近）"""
    return 1.0 + 0.15 * math.cos(th)


def edge_at(i, th):
    """第 i 道田坎在 th 方向上的位置（s）；每道各有自己的弯，不是一圈圈平行的环"""
    base = EDGES[i][0]
    if i == 0:
        return 0.0
    return (base * wide_at(th) + 1.6 * math.sin((2 + i) * th + 1.3 * i)
            + 1.0 * math.sin((5 + 2 * i) * th + 0.7 * i))


def bund_s(i, th):
    """第 i 道田埂在 th 方向上的位置（在坎的上侧田面上）"""
    return edge_at(i, th) + EDGES[i][3] + 0.35


def isle_ri(a):
    return 5.8 + 0.9 * math.sin(3 * a + 0.9) + 0.45 * math.sin(5 * a + 2.0)


def height(x, y):
    s = bay_s(x, y)
    th = math.atan2(y, x)
    wide = wide_at(th)
    z = LAGOON
    for i, (_, lo, hi, w) in enumerate(EDGES):
        z += (hi - lo) * step_(s, edge_at(i, th), w)
    cliff_at = 31.0 * wide
    top = 8.5 + 2.5 * math.sin(3 * th + 0.4) + 1.6 * math.sin(7 * th)
    z += top * ss(cliff_at, cliff_at + 3.5, s)
    # 孤洲：一块不圆的台地，顶是绿的
    dx, dy = x - ISLE_C[0], y - ISLE_C[1]
    d = math.hypot(dx, dy)
    a = math.atan2(dy, dx)
    ri = isle_ri(a)
    isle = LAGOON + (ISLE - LAGOON) * ss(ri + 5.0, ri - 1.0, d) + 0.25 * ss(ri - 0.5, 1.0, d)
    return max(z, isle)


def water_level(x, y):
    """这一点上的水面高：每层田一个水位，台阶落在田埂上（水被田埂拢住）"""
    s = bay_s(x, y)
    th = math.atan2(y, x)
    w = SEA
    for i in range(4):
        if s >= bund_s(i, th):
            w = WLEV[EDGES[i][2]]
    return w


def ridge_level(x, y):
    """宽埂用的水位：台阶落在田埂的**西侧**、用 2m 坡下来（人走得上去、下得去），埂面永远在水面之上"""
    s = bay_s(x, y)
    th = math.atan2(y, x)
    w = SEA
    for i in range(4):
        w += (WLEV[EDGES[i][2]] - WLEV[EDGES[i][1]]) * step_(s, bund_s(i, th) - 1.0, 1.0)
    return w


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
    """把整片网格按格子分类，各类拼成一份网格：classify(四角的高, 中心 x, y) → 类名或 None，
    zfun(x, y, 顶点的高) → 这个顶点的高"""
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
                    x, y = X0 + vi * STEP, Y0 + vj * STEP
                    vs.append((x, y, zfun(x, y, hs[v])))
                ids.append(idx[v])
            if (i + j) % 2:
                fs += [(ids[0], ids[1], ids[2]), (ids[0], ids[2], ids[3])]
            else:
                fs += [(ids[0], ids[1], ids[3]), (ids[1], ids[2], ids[3])]
    return parts


def terrain():
    def classify(zs, cx, cy):
        zmax = max(zs)
        if math.hypot(cx - ISLE_C[0], cy - ISLE_C[1]) < 9.0 and zmax > SEA + 0.3:
            return "isle"
        if zmax < LAGOON + 0.05 and math.hypot(cx, cy) > 42:
            return None     # 远处的深水底：水不透明，看不见，也走不到
        if zmax < (LAGOON + T4) / 2:
            return "floor"
        if zmax < (T4 + T3) / 2:
            return "t4"
        if zmax < (T3 + T2) / 2:
            return "t3"
        if zmax < (T2 + T1) / 2:
            return "t2"
        if zmax < T1 + 0.9:
            return "t1"
        if zmax < BANK + 0.7:
            return "bank"
        return "cliff"

    for name, (vs, fs, _) in grid_parts(classify, lambda x, y, h: h).items():
        k = fu.Kit()
        k._add(vs, fs)
        obj = k.build(f"ground_{name}", smooth=179 if name == "cliff" else 50, **GROUND[name])
        flip_up(obj)


def wband(w):
    """按水位分档，给水面上色"""
    if w >= (W1 + W2) / 2:
        return "w1"
    if w >= (W2 + W3) / 2:
        return "w2"
    if w >= (W3 + W4) / 2:
        return "w3"
    if w >= (W4 + SEA) / 2:
        return "w4"
    return "deep"


def sea():
    """水面：每层田一块，台阶落在田埂上；网格外四块大片接到天边（湾心的深水）"""
    def classify(zs, cx, cy):
        w = water_level(cx, cy)
        if min(zs) >= w - 0.03:
            return None
        return wband(w)

    for name, (vs, fs, _) in grid_parts(classify, lambda x, y, h: water_level(x, y)).items():
        k = fu.Kit()
        k._add(vs, fs)
        obj = k.build(f"water_{name}", smooth=0, collide=False, shadow=False, **WATER[name])
        flip_up(obj)
    # 网格外：四块大片，比网格里的深水略低 5cm，不共面
    R = 420.0
    for name, (cx, cy, sx, sy) in {
        "w": ((X0 - R) / 2, 0, R + X0, 2 * R), "e": ((X1 + R) / 2, 0, R - X1, 2 * R),
        "s": ((X0 + X1) / 2, (Y0 - R) / 2, X1 - X0, R + Y0), "n": ((X0 + X1) / 2, (Y1 + R) / 2, X1 - X0, R - Y1),
    }.items():
        nx.plane(f"water_far_{name}", abs(sx), abs(sy), (cx, cy, SEA - 0.05), collide=False, shadow=False,
                 **WATER["deep"])


# ── 田埂与溢流口 ────────────────────────────────────

def bunds():
    """田埂：每层田靠下那一边一道矮埂（高出田面 BUND_H），沿着田坎弯过去；每道埂上一个溢流口"""
    n = 480
    for i in range(4):
        _, lo, hi, w = EDGES[i]
        top = WLEV[hi] + 0.08      # 埂顶比上层田的水面高 8cm，水被拢在埂后面
        runs, cur = [], []
        for j in range(n + 1):
            th = math.tau * j / n - math.pi
            if math.cos(th) < -0.35:        # 西边敞开处没有田
                if len(cur) > 1:
                    runs.append(cur)
                cur = []
                continue
            x, y = at_s(th, bund_s(i, th))
            if abs(height(x, y) - hi) > 0.06:   # 两道坎挤在一起、或被孤洲盖住的地方断开
                if len(cur) > 1:
                    runs.append(cur)
                cur = []
                continue
            sx, sy = at_s(math.radians(SPILL[i]), bund_s(i, math.radians(SPILL[i])))
            if math.hypot(x - sx, y - sy) < 0.58:   # 溢流口：这一小段断开
                if len(cur) > 1:
                    runs.append(cur)
                cur = []
                continue
            cur.append((x, y))
        if len(cur) > 1:
            runs.append(cur)
        for k, pts in enumerate(runs):
            kit = fu.Kit()
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                L = math.hypot(bx - ax, by - ay)
                if L > 3.0:
                    continue
                ang = math.degrees(math.atan2(by - ay, bx - ax))
                kit.box((L + 0.42, 1.0, top - (hi - 0.35)), ((ax + bx) / 2, (ay + by) / 2, hi - 0.35), rot=(0, 0, ang))
            kit.build(f"bund{i}_{k}", smooth=0, **BUND_STYLE)


def spillways():
    """溢流口：田埂断开处挂一道细白的水线，从上层田的水面落到下层田的水面；底下一点白沫"""
    for i in range(4):
        _, lo, hi, _ = EDGES[i]
        th = math.radians(SPILL[i])
        x, y = at_s(th, bund_s(i, th))
        zt, zb = WLEV[hi], WLEV[lo]
        yaw = math.degrees(th) + 90.0
        h = zt - zb
        nx.box(f"spill{i}", (0.72, 0.44, h + 0.10), (x, y, zb - 0.06), (0, 0, yaw), collide=False, **SPILL_STYLE)
        nx.cylinder(f"spill{i}_foam", 0.62, 0.62, 0.05, (x, y, zb + 0.01), segments=18, collide=False, shadow=False,
                    **SPILL_STYLE)


def at_s(th, target):
    """th 方向上 s ＝ target 的那一点"""
    a, b = 1.0, 150.0
    ca, sa = math.cos(th), math.sin(th)
    for _ in range(40):
        m = (a + b) / 2
        if bay_s(ca * m, sa * m) < target:
            a = m
        else:
            b = m
    return ca * a, sa * a


def walls():
    """崖顶一圈看不见的墙（西边敞开处是深水，深水的挡板就是边）"""
    n = 64
    for i in range(n):
        th = math.tau * (i + 0.5) / n
        if math.cos(th) < -0.45:
            continue
        r = lagoon_r(th) + 31.0 * wide_at(th) + 4.0
        x, y = math.cos(th) * r, math.sin(th) * r
        w = math.tau * r / n + 1.0
        nx.collider_only(nx.box(f"wall_{i}", (w, 0.6, 40), (x, y, -5), (0, 0, math.degrees(th) + 90)))


# ── 走得到的地方 ────────────────────────────────────

RIDGE_W = 2.0
SOLID = []      # (判断函数)：点在这些东西的脚下 → 不是深水
RIDGE_AVOID = []    # 宽埂与岔路走过的地方，别的东西让开


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
    z0, z1 = -3.5, 2.5

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


# ── 内容 ────────────────────────────────────────────

def settle(x, y, r, at_least=-99.0):
    """把 (x, y) 沿径向挪到一块平地上（半径 r 内高差不到 4cm），东西不压在田坎上"""
    d = math.hypot(x, y)
    ux, uy = x / d, y / d
    for k in range(60):
        o = (k // 2 + 1) * 0.5 * (1 if k % 2 == 0 else -1) if k else 0.0
        px, py = x + ux * o, y + uy * o
        zs = [height(px + math.cos(a) * r, py + math.sin(a) * r) for a in [i * math.tau / 10 for i in range(10)]]
        zs.append(height(px, py))
        if max(zs) - min(zs) < 0.04 and zs[-1] >= at_least:
            return px, py
    return x, y


def causeway(pts, name, style, base=None):
    """一条埂：沿折线密排方块，埂面比「水与地中高的那个」高 0.12m（一路跟着水位起伏，走得上去）"""
    base = LAGOON - 0.3 if base is None else base
    dense = []
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        L = math.hypot(bx - ax, by - ay)
        n = max(1, int(L / 0.3))
        for k in range(n):
            t = k / n
            dense.append((ax + (bx - ax) * t, ay + (by - ay) * t))
    dense.append(pts[-1])
    k = fu.Kit()
    for (ax, ay), (bx, by) in zip(dense, dense[1:]):
        mx, my = (ax + bx) / 2, (ay + by) / 2
        top = max(ridge_level(mx, my), height(mx, my)) + 0.10
        L = math.hypot(bx - ax, by - ay)
        ang = math.degrees(math.atan2(by - ay, bx - ax))
        k.box((L + 0.34, RIDGE_W, top - base), (mx, my, base), rot=(0, 0, ang))
    k.build(name, smooth=0, **style)
    # 两边一路细桩（读作尺度）
    st = fu.Kit()
    acc = 0.0
    for (ax, ay), (bx, by) in zip(dense, dense[1:]):
        L = math.hypot(bx - ax, by - ay)
        if L < 1e-6:
            continue
        nx_, ny_ = -(by - ay) / L, (bx - ax) / L
        t = 0.0
        while t < L:
            px, py = ax + (bx - ax) * t / L, ay + (by - ay) * t / L
            side = 1 if int(acc / 2.6) % 2 else -1
            top = max(ridge_level(px, py), height(px, py)) + 0.10
            st.box((0.14, 0.14, 0.9), (px + nx_ * side * (RIDGE_W / 2 - 0.12), py + ny_ * side * (RIDGE_W / 2 - 0.12),
                                       top - 0.05))
            t += 2.6
            acc += 2.6
    st.build(name + "_stakes", smooth=0, collide=False, a="white", b="mist", pattern="plain")


def ridge():
    """宽埂：从东岸（th≈22°）弯到孤洲，一路跟着各层的水位起伏；半路一条岔路到深水里的方台"""
    th0 = math.radians(22.0)
    sx, sy = at_s(th0, edge_at(4, th0) + 2.8)
    main = [(sx, sy), (30.0, 13.0), (24.0, 10.8), (18.0, 9.2), (12.0, 7.8), (6.0, 7.0), (1.0, 6.2), ISLE_C]
    branch = [(12.0, 7.8), (11.0, 3.4), (10.5, 0.2)]
    end = (10.4, -1.4, 20.0)
    causeway(main, "ridge", dict(ramp=("violet", "rose_deep", "rose"), pattern="grain"))
    causeway(branch, "ridge_branch", dict(ramp=("violet", "rose_deep", "rose"), pattern="grain"), base=LAGOON - 0.36)
    # 方台：比埂面高 0.22，迈得上去；立在深水里
    zt = max(ridge_level(end[0], end[1]), height(end[0], end[1])) + 0.34
    nx.box("ridge_end", (3.6, 3.6, zt - (LAGOON - 0.42)), (end[0], end[1], LAGOON - 0.42), (0, 0, end[2]),
           a="rose", b="rose_deep", pattern="tiles")
    SOLID.append(lambda px, py: any(seg_dist(px, py, ax, ay, bx, by) < RIDGE_W / 2 - 0.05
                                    for (ax, ay), (bx, by) in zip(main, main[1:])))
    SOLID.append(lambda px, py: any(seg_dist(px, py, ax, ay, bx, by) < RIDGE_W / 2 - 0.05
                                    for (ax, ay), (bx, by) in zip(branch, branch[1:])))
    SOLID.append(lambda px, py: in_rect(px, py, end[0], end[1], end[2], 1.85, 1.85))
    # 埂与岔路走过的地方：潮石、水洼、别的东西让开
    for pts in (main, branch):
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            L = math.hypot(bx - ax, by - ay)
            n = max(1, int(L / 2.0))
            for k in range(n + 1):
                RIDGE_AVOID.append((ax + (bx - ax) * k / n, ay + (by - ay) * k / n, 2.6))
    RIDGE_AVOID.append((end[0], end[1], 3.4))
    return end


def gauge(x, y, h=15.0):
    """水尺：一道道刻度（白与深紫相间，每 0.3m 一格，每 1.5m 一道长的），顶上一点金。立在最高一层田里"""
    z0 = T1 + 0.05
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
    # 底座：一块方台，立在田里
    nx.box("gauge_base", (1.5, 1.5, 0.5), (x, y, T1 - 0.35), (0, 0, 18), a="lilac_pale", b="lilac", pattern="tiles")
    SOLID.append(lambda px, py: in_rect(px, py, x, y, 18, 1.0, 1.0))


def tide_stone(name, x, y, w, h, yaw, t=0.5):
    """潮石：一块竖着的石板，在 MARK 那个高度有一道深色的横纹（比石板宽一圈，不共面）"""
    z = height(x, y)
    nx.box(name, (w, t, h + 0.3), (x, y, z - 0.3), (0, 0, yaw), **STONE)
    nx.box(name + "_mark", (w + 0.06, t + 0.06, 0.22), (x, y, MARK - 0.11), (0, 0, yaw), collide=False, **MARK_STYLE)


def tide_stones(avoid):
    """岸上、田里、孤洲上一块块潮石，高矮不一（每块都高过 MARK）；横纹连起来是空中一条水平线"""
    rnd = random.Random(23)
    stones = []
    tries = 0
    while len(stones) < 22 and tries < 1400:
        tries += 1
        if len(stones) < 5:                 # 孤洲上放几块，横纹线横过洲顶
            a = rnd.uniform(0, math.tau)
            d = rnd.uniform(2.2, 4.6)
            x, y = ISLE_C[0] + math.cos(a) * d, ISLE_C[1] + math.sin(a) * d
        else:
            th = rnd.uniform(-1.7, 1.7)     # 东半边（西边敞开）
            s = rnd.uniform(-0.5, 28.0)
            x, y = at_s(th, s)
        z = height(x, y)
        if z < T4 - 0.05 or z > BANK + 0.3:
            continue
        # 离田坎远一点（脚下要平）
        zs = [height(x + 1.2 * math.cos(a), y + 1.2 * math.sin(a)) for a in (0, 1.6, 3.1, 4.7)]
        if max(zs) - min(zs) > 0.05:
            continue
        if any(math.hypot(x - ax, y - ay) < ar for ax, ay, ar in avoid):
            continue
        if any(math.hypot(x - qx, y - qy) < 6.0 for qx, qy in stones):
            continue
        stones.append((x, y))
        top = MARK + rnd.uniform(0.6, 3.0)
        w = rnd.uniform(0.7, 1.5)
        tide_stone(f"stone{len(stones)}", x, y, w, top - z, math.degrees(math.atan2(y, x)) + 90 + rnd.uniform(-25, 25),
                   t=rnd.uniform(0.28, 0.42))
    return stones


def isle_top():
    """孤洲上的分量：一圈立石围在边上（正对宽埂上来的那一段留出缺口） + 顶上一块方台，晶体立在台上"""
    rnd = random.Random(7)
    n = 9
    k = fu.Kit()
    for i in range(n):
        a = math.tau * i / n + 0.35
        # 宽埂从 a≈13.5° 上来，那一段空出来
        if abs(((math.degrees(a) - 13.5 + 540) % 360) - 180) > 150:
            continue
        ri = isle_ri(a)
        d = ri - 0.7
        x, y = ISLE_C[0] + math.cos(a) * d, ISLE_C[1] + math.sin(a) * d
        z = height(x, y)
        h = rnd.uniform(1.0, 1.9)
        w = rnd.uniform(0.5, 0.85)
        k.box((w, 0.4, h), (x, y, z - 0.15), (0, 0, math.degrees(a) + 90 + rnd.uniform(-15, 15)))
    k.build("isle_ring", smooth=0, **STONE)
    # 洲顶一块方台（晶体立在上面），只高 0.28，迈得上去
    cx, cy = ISLE_C[0] + 0.3, ISLE_C[1] + 0.4
    zt = height(cx, cy)
    nx.box("isle_plinth", (2.2, 2.2, 0.4), (cx, cy, zt - 0.12), (0, 0, 14), a="lilac_pale", b="lilac", pattern="tiles")
    return cx, cy, zt + 0.28


LOCK_STEPS = [0.5, 0.2, -0.1, -0.4, -0.7, -1.0, -1.3, -1.6]


def lock(x, y, yaw):
    """孤洲西边的闸：三面矮墙围着一段往深水里去的台阶（本地 +Y 朝外、往下）。最下一级 → 沁泫池"""
    g = nx.group("lock", (x, y, 0), (0, 0, yaw))
    w = 3.0
    k = fu.Kit()
    for i, zt in enumerate(LOCK_STEPS):
        k.box((w, 1.0, zt - (LAGOON - 0.3)), (0, 1.0 + i * 1.0, LAGOON - 0.3))
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


def cup(x, y):
    """杯口：东岸地里嵌着一圈白的杯沿，里面一汪水。走进水里回家"""
    z = height(x, y)
    R = 2.2
    nx.torus("cup_rim", R + 0.15, 0.17, (x, y, z + 0.1), major_seg=40, minor_seg=8, a="white", b="mist", pattern="plain")
    nx.cylinder("cup_bed", R, R, 0.3, (x, y, z - 0.34), segments=32, a="blue", b="blue_pale", pattern="plain")
    nx.cylinder("cup_water", R + 0.02, R + 0.02, 0.02, (x, y, z + 0.04), segments=32, collide=False, shadow=False,
                **WATER["w1"])
    nx.portal("portal_home", (x, y, z + 1.0), "house", at="shoal", mode="walk", radius=1.3)


def pools():
    """北边最高一层田上的水洼：一圈矮沿（高出田面 0.3m，迈得上去）围着一汪水"""
    rnd = random.Random(5)
    spots = [(d + rnd.uniform(-2, 2), rnd.uniform(1.1, 2.7), rnd.random()) for d in range(55, 108, 4)]
    placed = []
    for i, (deg, r, f) in enumerate(spots):
        th = math.radians(deg)
        lo, hi = edge_at(3, th) + 0.7 + 1.3 + r, edge_at(4, th) - 0.9 - 0.3 - r
        if hi < lo:
            continue
        x, y = at_s(th, lo + (hi - lo) * f)
        z = height(x, y)
        if abs(z - T1) > 0.02 or any(math.hypot(x - qx, y - qy) < r + qr + 1.2 for qx, qy, qr in placed):
            continue
        placed.append((x, y, r))
        sh.tube(f"pool{i}_rim", r + 0.3, r, 0.5, (x, y, z - 0.12), segments=24, a="white", b="mist", pattern="plain")
        nx.cylinder(f"pool{i}_bed", r + 0.05, r + 0.05, 0.12, (x, y, z - 0.12), segments=24,
                    a="lilac", b="lilac_dark", pattern="grain")
        nx.cylinder(f"pool{i}_water", r - 0.02, r - 0.02, 0.02, (x, y, z + 0.16), segments=24,
                    collide=False, shadow=False, **WATER["w1"])
    return placed


def leaves(avoid):
    """圆叶：躺在水面上（贴着各层的水面，不挡人）"""
    rnd = random.Random(11)
    n = 0
    got = []
    for i in range(240):
        th = rnd.uniform(-2.2, 2.2)
        s = rnd.uniform(-1.0, 26.0)
        px, py = at_s(th, s)
        wl = water_level(px, py)
        if height(px, py) > wl - 0.06:
            continue
        if any(math.hypot(px - ax, py - ay) < ar + 2.0 for ax, ay, ar in avoid):
            continue
        r = rnd.uniform(0.35, 0.75)
        if any(math.hypot(px - qx, py - qy) < r + qr + 0.25 for qx, qy, qr in got):
            continue
        got.append((px, py, r))
        nx.cylinder(f"leaf{n}", r, r, 0.08, (px, py, wl - 0.02 + rnd.uniform(-0.012, 0.012)), segments=14, collide=False,
                    a="rose" if n % 3 else "pink", b="rose_deep", pattern="plain")
        n += 1
        if n >= 22:
            break


def lamps(avoid):
    """浮灯：浮在水面上，轻轻上下、慢慢转"""
    rnd = random.Random(31)
    n = 0
    for i in range(120):
        th = rnd.uniform(-2.0, 2.0)
        s = rnd.uniform(-1.5, 24.0)
        px, py = at_s(th, s)
        wl = water_level(px, py)
        if height(px, py) > wl - 0.25:
            continue
        if any(math.hypot(px - ax, py - ay) < ar + 3.0 for ax, ay, ar in avoid):
            continue
        # 浮盘 + 灯罩（自己发亮）
        nx.cylinder(f"lamp{n}_float", 0.42, 0.38, 0.1, (px, py, wl - 0.05), segments=16, collide=False,
                    a="lilac_pale", b="lilac", pattern="plain")
        body = nx.cylinder(f"lamp{n}_body", 0.22, 0.26, 0.3, (px, py, wl + 0.05), segments=12, collide=False,
                           a="pink_pale", b="rose", pattern="plain")
        glow = nx.cylinder(f"lamp{n}_glow", 0.2, 0.0, 0.18, (px, py, wl + 0.35), segments=12,
                           collide=False, shadow=False, emit=1.0, a="gold", b="white", pattern="plain")
        nx.behave(body, spin=rnd.uniform(-9, 9), bob=0.05)
        nx.behave(glow, spin=rnd.uniform(-9, 9), bob=0.05)
        n += 1
        if n >= 5:
            break


def foreground(sx, sy):
    """出生点脚前的几片圆叶与一盏浮灯（第一眼里就有东西，别是一片空水面）"""
    rnd = random.Random(97)
    for i, (ox, oy) in enumerate([(-5.5, -3.0), (-7.5, 1.6), (-6.5, -1.2), (-9.2, -4.0), (-4.6, 3.4), (-8.0, -1.0)]):
        px, py = sx + ox, sy + oy
        wl = water_level(px, py)
        if height(px, py) > wl - 0.05:
            continue
        r = rnd.uniform(0.4, 0.7)
        nx.cylinder(f"leafF{i}", r, r, 0.08, (px, py, wl - 0.01), segments=14, collide=False,
                    a="rose" if i % 2 else "pink", b="rose_deep", pattern="plain")
    px, py = sx - 6.2, sy - 0.6
    wl = water_level(px, py)
    if height(px, py) < wl - 0.25:
        nx.cylinder("lampF_float", 0.55, 0.5, 0.14, (px, py, wl - 0.06), segments=16, collide=False,
                    a="lilac_pale", b="lilac", pattern="plain")
        body = nx.cylinder("lampF_body", 0.3, 0.34, 0.34, (px, py, wl + 0.08), segments=12, collide=False,
                           a="pink_pale", b="rose", pattern="plain")
        glow = nx.cylinder("lampF_glow", 0.26, 0.0, 0.22, (px, py, wl + 0.42), segments=12,
                           collide=False, shadow=False, emit=1.0, a="gold", b="white", pattern="plain")
        nx.behave(body, spin=4, bob=0.05)
        nx.behave(glow, spin=4, bob=0.05)


def build(extent=EXTENT):
    nx.into("env")
    nx.sun((0.42, -0.55, 0.72))
    nx.atmosphere("ebb")

    nx.into("things")
    ridge()
    # 水尺：立在最高一层田（出生点西边一点）
    gth = math.radians(-24.0)
    gx, gy = at_s(gth, bund_s(3, gth) + 2.6)
    gauge(gx, gy)

    # 孤洲：一圈立石 + 方台 + 晶体
    cx, cy, cz = isle_top()
    nx.entrance("crystal", (cx, cy, cz + 1.6), "", "", size=0.45)

    # 闸：从洲心往西走到地面落到 0.6 的地方，第一级台阶从那里接出去
    ld = (-math.sin(math.radians(168)), math.cos(math.radians(168)))
    t = 0.0
    while height(ISLE_C[0] + ld[0] * t, ISLE_C[1] + ld[1] * t) > 0.6:
        t += 0.1
    lock(ISLE_C[0] + ld[0] * (t - 0.8), ISLE_C[1] + ld[1] * (t - 0.8), 168)

    # 东岸：杯口（回家）与出生点
    ux, uy = at_s(math.radians(-16.0), edge_at(4, math.radians(-16.0)) + 3.6)
    cup(ux, uy)
    th0 = math.radians(3.0)
    sx, sy = at_s(th0, edge_at(4, th0) + 0.8)
    yaw = facing(-1, -0.05)
    nx.spawn((sx, sy, height(sx, sy)), facing_deg=yaw)
    nx.arrive("house", (sx, sy, height(sx, sy)), facing_deg=yaw)

    nx.into("pools")
    placed = pools()
    # 花房：北边水洼旁的花瓶
    vx, vy = settle(16.0, 30.0, 1.6)
    pf.gate_vase("shoal-var-1", (vx, vy, height(vx, vy)), facing(-1, -1))

    nx.into("stones")
    avoid = [(ux, uy, 5.0), (sx, sy, 3.0), (vx, vy, 5.0), (gx, gy, 4.5), (ISLE_C[0], ISLE_C[1], 4.0)]
    avoid += [(x, y, r + 2.0) for x, y, r in placed]
    avoid += RIDGE_AVOID
    tide_stones(avoid)

    nx.into("ground")
    terrain()
    bunds()
    walls()
    deep_fence()

    nx.into("water")
    sea()
    spillways()
    leaves(avoid)
    lamps(avoid)
    foreground(sx, sy)


if __name__ == "__main__":
    nx.reset()
    build()
    nx.save_blend("shoal-var-1")
    nx.export("shoal-var-1")
