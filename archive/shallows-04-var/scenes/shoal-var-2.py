"""浅梦 · 浅滩变体 2（shoal-var-2）：退到底的海湾。

潮已经退到了尽头。第三轮的浅滩水面停在 0m，这一版把水面压到 −1.6m：整片滩涂露出来，
一层层往下（干裂的东岸 → 湿沙的田 → 湾心那片最暗的干滩），水只在很远的西边剩一条，
再往外是深水与海天线。**「干」是这一版的主角**——跟浅滩的另两个变体（水多）正好相反。

- 水面 SEA = −1.6m；地面低过 DEEP = −2.05m 的地方走不进去（一圈看不见的挡板）。
  湾心的深水底（LAGOON = −1.2m）如今在水面之上：从东岸一路走下去，脚下全是干的。
- `height` 里加了一项 SEA_DROP：出了湾心往西，海底一路深下去——湾里的深水退到画面外，
  只剩西边远处一条海；孤洲脚下留了一圈下凹（MOAT），水退到底后还剩洲根一圈水。
- 22 块潮石上那道 6.2m 的横纹（MARK）连成空中一条水平线：这一版的记号，从哪儿都看得见。
- 东岸与田里立着 15m 的水尺（脚下是干的）；孤洲顶上晶体；孤洲东边一座闸，
  六级的台阶一路下到水里，最下一级 → 沁泫池（占位 seeping）。
- 圆叶搁浅在滩上，干瘪地平躺着；北边几处水洼干了、裂着纹（留两处还有一点水）；
  干滩上一列列细桩与一串脚印（纸片，给尺度）。

出入口：
- 回家：东岸地里嵌着的一只「杯口」——一圈白的杯沿围着一汪水，走进水里 → house，at="shoal"。
- 花房：北边岸上一只插花的瓶，E「凑近」→ glasshouse（从那边回来落在瓶前，到达点 glasshouse）。
- 沁泫池：闸里最下面一级（seeping，占位）。
- 晶体：孤洲顶上（站点待定）。
出生点＝到达点 house，在东岸高处，朝西。

运行：node scripts/blender.cjs build shoal-var-2，网页 ?world=shoal-var-2
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

SEA = -1.6            # 水面：潮退到了尽头
DEEP = -2.05          # 地面低过它就是深水：一圈看不见的挡板拦着（水面上蹚到 0.45m 就到底）
MARK = 6.2            # 潮石上那道横纹的高度：这片湾记得的一次水位

# 各层的地面高（米）。田一层层照旧，只是水面退到了它们下面
LAGOON = -1.2         # 湾心的深水底：如今是一片露出来的干滩（最低、最湿、最暗）
T4 = -0.45            # 潮痕那层
T3 = -0.15            # 湿沙
T2 = 0.35             # 干沙
T1 = 1.4              # 干田
BANK = 3.2            # 东岸
ISLE = 2.6            # 孤洲

STEP = 1.0
X0, X1, Y0, Y1 = -95.0, 95.0, -90.0, 90.0
ISLE_C = (-4.0, 3.0)
ISLE_R = 7.5
SEA_DROP = 5.2        # 出了湾心往西，海底深多少（湾里的深水退到画面外）
MOAT = 0.8            # 孤洲脚下那一圈水有多深（水面上蹚得过去）

# 一层一种颜色（分开的物体，田坎上有轮廓线）：明度一层层拉开——越往下越湿、越暗
TERRACE_STYLE = {
    "floor": dict(ramp=("ink", "violet_deep", "violet_deep"), pattern="tiles"),      # 湾心那片干滩：最低最暗，裂着纹
    "low": dict(ramp=("violet_deep", "violet", "violet"), pattern="bands"),           # T4：一道道潮痕
    "mid": dict(ramp=("violet", "lilac_dark", "lilac_dark"), pattern="grain"),        # T3：湿沙斑驳
    "up": dict(ramp=("lilac_dark", "lilac", "lilac"), pattern="grain"),               # T2：干沙
    "bank": dict(ramp=("lilac", "lilac_pale", "lilac_pale"), pattern="grain"),        # T1：干田
    "shore": dict(ramp=("lilac_dark", "pink", "pink_pale"), pattern="grain"),         # 东岸：最亮，干裂
    "cliff": dict(ramp=("violet", "lilac_dark", "lilac"), pattern="bands"),           # 崖：背光的一档
}
# 水：都压在蓝紫一列（不然受光后落到淡紫上，看不出是水）。齐踝的水是这一版唯一饱和的一块
WATER = {
    "shallow": dict(ramp=("violet", "blue", "blue"), pattern="flow"),                # 齐踝：饱和的蓝
    "deep": dict(ramp=("ink", "ink", "ink"), pattern="flow"),                        # 深水：最深
}
STONE = dict(ramp=("lilac_dark", "lilac_pale", "mist"), pattern="grain")
MARK_STYLE = dict(a="violet_deep", b="violet", pattern="plain")
STAKE = dict(a="white", b="mist", pattern="plain")
PRINT = dict(a="violet_deep", b="ink", pattern="plain")


def ss(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def facing(dx, dy):
    """朝 (dx, dy) 看的 facing_deg（同 spawn：0 ＝ +Y，90 ＝ −X）"""
    return math.degrees(math.atan2(-dx, dy))


# ── 地形 ─────────────────────────────────────────

def lagoon_r(th):
    """湾心深水的外沿半径（各方向不一样）；西边敞开，一直是深水"""
    r = 21.0 + 3.0 * math.sin(2 * th + 0.5) + 2.0 * math.sin(3 * th + 1.7) + 1.2 * math.sin(5 * th + 0.3)
    opening = ss(-0.5, -0.85, math.cos(th))
    return r + opening * 170.0


def warp(x, y):
    return (3.5 * math.sin(x / 17.0 + 0.7) * math.cos(y / 14.0 - 0.4) + 1.6 * math.sin((x + y) / 8.5 + 1.1)
            + 0.8 * math.sin(x / 4.3 - y / 6.1))


def bay_s(x, y):
    """离深水外沿有多远（米，往岸上为正）"""
    r = math.hypot(x, y)
    th = math.atan2(y, x)
    return r - lagoon_r(th) + warp(x, y)


def step_(s, at, w=0.7):
    return ss(at - w, at + w, s)


# 田坎：(离深水外沿多远的基准, 下面那层, 上面那层, 坎的半宽)
# 坎放得宽（每 1m 网格抬不到 0.3m）：上下都能走，不是一道翻不过去的墙；埂照旧压在每道坎的上边
EDGES = [(0.0, LAGOON, T4, 1.5), (8.0, T4, T3, 0.7), (16.0, T3, T2, 1.1), (24.5, T2, T1, 2.0), (33.0, T1, BANK, 3.2)]


def wide_at(th):
    """每层田的宽窄：东边宽、南北窄（崖逼得近）"""
    return 1.0 + 0.2 * math.cos(th)


def edge_at(i, th):
    """第 i 道田坎在 th 方向上的位置（s）。每道各有自己的弯"""
    base = EDGES[i][0]
    if i == 0:
        return 0.0
    return base * wide_at(th) + 3.2 * math.sin((2 + i) * th + 1.3 * i) + 2.0 * math.sin((5 + 2 * i) * th + 0.7 * i)


def isle_ri(a):
    return ISLE_R + 1.6 * math.sin(3 * a + 0.9) + 0.8 * math.sin(5 * a + 2.0)


def height(x, y):
    s = bay_s(x, y)
    r = math.hypot(x, y)
    th = math.atan2(y, x)
    wide = wide_at(th)
    z = LAGOON
    for i, (_, lo, hi, w) in enumerate(EDGES):
        z += (hi - lo) * step_(s, edge_at(i, th), w)
    cliff_at = 40.0 * wide
    top = 9.0 + 3.0 * math.sin(3 * th + 0.4) + 2.0 * math.sin(7 * th)
    z += top * ss(cliff_at, cliff_at + 3.5, s)
    # 潮退到底：出了湾心往西，海底一路深下去——湾里的深水退到画面外，只剩西边远处一条海
    z -= SEA_DROP * ss(-0.12, -0.78, math.cos(th)) * ss(2.0, 46.0, r)
    # 孤洲：一块不圆的台地，顶上微微隆起；洲根一圈下凹，水退到底后还剩这一圈水
    dx, dy = x - ISLE_C[0], y - ISLE_C[1]
    d = math.hypot(dx, dy)
    ri = isle_ri(math.atan2(dy, dx))
    z -= MOAT * ss(ri + 12.0, ri + 3.0, d)
    return z + (ISLE - z) * ss(ri + 4.0, ri - 0.6, d) + 0.3 * ss(ri - 1.0, 1.0, d)


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
    """把整片网格按格子分类，各类拼成一份网格：classify(四角的高) → 类名或 None，zfun(顶点) → 这个点的高"""
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
        if zmax < LAGOON - 0.05 and math.hypot(cx, cy) > 60:
            return None     # 远处的海底：水不透明，看不见，也走不到
        if zmax < LAGOON + 0.05:
            return "floor"
        if zmax < T3 + 0.05:
            return "low"
        if zmax < T2 + 0.05:
            return "mid"
        if zmax < T1 + 0.05:
            return "up"
        if zmax < BANK - 0.6:
            return "bank"
        if zmax < BANK + 0.6:
            return "shore"
        return "cliff"

    for name, (vs, fs, _) in grid_parts(classify, lambda z: z).items():
        k = fu.Kit()
        k._add(vs, fs)
        obj = k.build(f"ground_{name}", smooth=179 if name == "cliff" else 50, **TERRACE_STYLE[name])
        flip_up(obj)


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


def flat(x, y, r):
    """半径 r 内高差不到 5cm（东西不压在田坎上）"""
    zs = [height(x + math.cos(a) * r, y + math.sin(a) * r) for a in [i * math.tau / 10 for i in range(10)]]
    zs.append(height(x, y))
    return max(zs) - min(zs) < 0.05


def bunds():
    """田埂：每层田靠下那一边一道矮埂（高出田面 0.16m，迈得过去），沿着田坎弯过去"""
    n = 720
    for i in range(1, len(EDGES)):
        _, lo, hi, w = EDGES[i]
        runs, cur = [], []
        for j in range(n + 1):
            th = math.tau * j / n - math.pi
            if math.cos(th) < -0.4:     # 西边敞开处没有田
                if len(cur) > 1:
                    runs.append(cur)
                cur = []
                continue
            x, y = at_s(th, edge_at(i, th) + w + 0.6)
            if abs(height(x, y) - hi) > 0.05:   # 两道坎挤在一起、或被孤洲盖住的地方断开
                if len(cur) > 1:
                    runs.append(cur)
                cur = []
                continue
            cur.append((x, y))
        if len(cur) > 1:
            runs.append(cur)
        top = hi + 0.16
        for k, pts in enumerate(runs):
            kit = fu.Kit()
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                L = math.hypot(bx - ax, by - ay)
                if L > 3.0:
                    continue
                ang = math.degrees(math.atan2(by - ay, bx - ax))
                kit.box((L + 0.42, 0.42, top - (hi - 0.3)), ((ax + bx) / 2, (ay + by) / 2, hi - 0.3), rot=(0, 0, ang))
            kit.build(f"bund{i}_{k}", smooth=0, ramp=("lilac_dark", "lilac", "lilac_pale"), pattern="plain")


def walls():
    """崖顶一圈看不见的墙（西边敞开处是深水，深水的挡板就是边）"""
    n = 64
    for i in range(n):
        th = math.tau * (i + 0.5) / n
        if math.cos(th) < -0.45:
            continue
        r = lagoon_r(th) + 45.0 * (1.0 + 0.2 * math.cos(th))
        x, y = math.cos(th) * r, math.sin(th) * r
        w = math.tau * r / n + 1.0
        nx.collider_only(nx.box(f"wall_{i}", (w, 0.6, 40), (x, y, -5), (0, 0, math.degrees(th) + 90)))


# ── 走得到的地方 ─────────────────────────────────
# 埂、闸、水尺的方台这些「滩上的实地」，挡板要让开它们

RIDGE_W = 2.2
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
    """水面停在 SEA：网格范围里按底下多深分两种颜色，范围外一圈深水接到天边"""
    def classify(zs, cx, cy):
        if min(zs) >= SEA - 0.02:
            return None
        z = height(cx, cy)
        if z > SEA - 1.2:
            return "shallow"
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


def pools(avoid):
    """滩上的水洼：一圈矮沿围着一片干裂的泥底，只留几处还有一点点水。
    东边（出生点看出去的那一片）与北边都有，近处那几处大一点，一眼就看见"""
    rnd = random.Random(5)
    spots = [(d + rnd.uniform(-2, 2), rnd.uniform(1.1, 2.8), rnd.random()) for d in range(-64, 118, 4)]
    placed = []
    for i, (deg, r, f) in enumerate(spots):
        th = math.radians(deg)
        lo, hi = edge_at(3, th) + 0.7 + 1.3 + r, edge_at(4, th) - 0.9 - 0.3 - r
        if hi < lo:
            continue
        x, y = at_s(th, lo + (hi - lo) * f)
        z = height(x, y)
        if abs(z - T1) > 0.6 or any(math.hypot(x - qx, y - qy) < r + qr + 1.2 for qx, qy, qr in placed):
            continue
        if any(math.hypot(x - ax, y - ay) < ar + r for ax, ay, ar in avoid):
            continue
        placed.append((x, y, r))
        sh.tube(f"pool{i}_rim", r + 0.24, r, 0.3, (x, y, z - 0.1), segments=24, a="white", b="mist", pattern="plain")
        # 泥底：干裂（方砖纹），只有第 1、4 处还剩一点水
        nx.cylinder(f"pool{i}_bed", r + 0.05, r + 0.05, 0.14, (x, y, z - 0.12), segments=24,
                    ramp=("violet_deep", "violet", "lilac_dark"), pattern="tiles")
        if i % 3 == 1:
            nx.cylinder(f"pool{i}_water", r - 0.35, r - 0.35, 0.02, (x, y, z + 0.09), segments=24,
                        collide=False, shadow=False, **WATER["shallow"])
    print("[shoal-var-2] 水洼", [(round(a, 1), round(b, 1), round(c, 1)) for a, b, c in placed])
    return placed


def tide_stone(name, x, y, w, h, yaw, t=0.5):
    """潮石：一块竖着的石板，在 MARK 那个高度有一道深色的横纹（比石板宽一圈，不共面）。
    石板要够高：顶比横纹高；底埋进地里一点"""
    z = height(x, y)
    nx.box(name, (w, t, h + 0.3), (x, y, z - 0.3), (0, 0, yaw), **STONE)
    nx.box(name + "_mark", (w + 0.06, t + 0.06, 0.22), (x, y, MARK - 0.11), (0, 0, yaw), collide=False, **MARK_STYLE)


def tide_stones(avoid):
    """岸上、田里、露出来的滩涂上一块块潮石，高矮不一（每块都高过 MARK）；
    横纹连起来是空中一条水平线——这一版的记号"""
    rnd = random.Random(23)
    stones = []
    tries = 0
    while len(stones) < 22 and tries < 1400:
        tries += 1
        th = rnd.uniform(-1.9, 1.9)     # 东半边（西边敞开）
        s = rnd.uniform(-9.0, 38.0)     # 现在滩涂也露出来了，潮石一直立到湾心那片干滩上
        x, y = at_s(th, s)
        z = height(x, y)
        if z < SEA + 0.1 or z > BANK + 0.3:
            continue
        if not flat(x, y, 1.2):
            continue
        if any(math.hypot(x - ax, y - ay) < ar for ax, ay, ar in avoid):
            continue
        if any(math.hypot(x - qx, y - qy) < 6.5 for qx, qy in stones):
            continue
        stones.append((x, y))
        top = MARK + rnd.uniform(0.6, 3.0)
        w = rnd.uniform(0.7, 1.5)
        tide_stone(f"stone{len(stones)}", x, y, w, top - z, math.degrees(th) + 90 + rnd.uniform(-25, 25),
                   t=rnd.uniform(0.28, 0.42))
    print("[shoal-var-2] 潮石", [(round(a, 1), round(b, 1)) for a, b in stones])
    return stones


def gauge(x, y, base):
    """水尺：一道道刻度（白与深紫相间，每 0.3m 一格，每 1.5m 一道长的），顶上一点金。立在干滩的方台上"""
    z0 = base + 0.3
    h = 15.0
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


def leaf(name, x, y, r, curl):
    """一片搁浅的圆叶：干瘪地平躺在滩上（curl>0 时边卷起来，只剩一圈）"""
    z = height(x, y)
    if curl:
        sh.tube(name, r, r * 0.45, 0.06, (x, y, z + 0.02), segments=14, collide=False, shadow=False,
                a="rose", b="rose_deep", pattern="plain")
    else:
        nx.cylinder(name, r, r * 0.94, 0.05, (x, y, z + 0.015), segments=14, collide=False, shadow=False,
                    a="pink" if r > 0.8 else "rose", b="rose_deep", pattern="grain")


def leaves(avoid):
    """圆叶搁浅在滩上：不跟水走，干瘪地平躺着，多在北边与东边那几片露出来的田上"""
    rnd = random.Random(11)
    n = 0
    tries = 0
    while n < 22 and tries < 400:
        tries += 1
        th = rnd.uniform(-2.0, 2.0)
        s = rnd.uniform(-6.0, 43.0)
        px, py = at_s(th, s)
        z = height(px, py)
        if z < SEA + 0.12 or z > T1 + 0.05:
            continue
        if math.hypot(px - ISLE_C[0], py - ISLE_C[1]) < 11:
            continue
        if any(math.hypot(px - ax, py - ay) < ar + 2.0 for ax, ay, ar in avoid):
            continue
        if not flat(px, py, rnd.uniform(0.5, 1.0)):
            continue
        leaf(f"leaf{n}", px, py, rnd.uniform(0.55, 1.5), rnd.random() < 0.3)
        n += 1


def ridge():
    """宽埂：从东边的干田下一路弯到孤洲；半路分出一条，尽头一块方台，立着水尺。
    潮退到底，埂现在是一条低矮的土埂，贴着露出来的滩涂走——每 1m 一小段、埂面就在脚下 0.22 上面，
    所以哪儿都迈得上去，也不会在地势低的地方立成一道墙"""
    main = [(32.0, 7.5), (28.0, 6.0), (24.0, 5.0), (20.0, 5.0), (16.0, 5.5), (12.0, 5.5), (9.5, 5.2), (7.5, 4.8)]
    branch = [(24.0, 5.0), (25.0, -1.0), (26.0, -5.5)]
    end = (26.5, -7.0, 0.0)
    # 沿路每 1m 采一个点，埂面取这一带地面的「包络」再抹平：一段段接得上，也没有一处立成墙
    path = []
    for pts in (main, branch):
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            n = max(1, int(round(math.hypot(bx - ax, by - ay) / 1.0)))
            for i in range(n):
                path.append((ax + (bx - ax) * i / n, ay + (by - ay) * i / n))
    g = [height(px, py) for px, py in path]
    n = len(path)
    env = [max(g[max(0, i - 2):i + 3]) + 0.18 for i in range(n)]
    top = [max(SEA + 0.12, sum(env[max(0, i - 2):i + 3]) / len(env[max(0, i - 2):i + 3])) for i in range(n)]
    top = [max(t, g[i] + 0.12) for i, t in enumerate(top)]
    segs = [(path[i], path[i + 1]) for i in range(n - 1)]
    seg_top = [max(top[i], top[i + 1]) for i in range(n - 1)]

    k = fu.Kit()
    for ((ax, ay), (bx, by)), t in zip(segs, seg_top):
        L = math.hypot(bx - ax, by - ay)
        ang = math.degrees(math.atan2(by - ay, bx - ax))
        k.box((L + 0.6, RIDGE_W, t + 2.6), ((ax + bx) / 2, (ay + by) / 2, -2.6), rot=(0, 0, ang))
    k.build("ridge", smooth=0, a="lilac_pale", b="lilac", pattern="grain")
    # 一路细桩：一根根插在埂的两边，标着这条路的边
    st = fu.Kit()
    acc, side = 0.0, 1
    for ((ax, ay), (bx, by)), t in zip(segs, seg_top):
        L = math.hypot(bx - ax, by - ay)
        nx_, ny_ = -(by - ay) / L, (bx - ax) / L
        px, py = ax + nx_ * side * (RIDGE_W / 2 - 0.12), ay + ny_ * side * (RIDGE_W / 2 - 0.12)
        st.box((0.14, 0.14, 0.9), (px, py, t - 0.05))
        acc += L
        side = 1 if int(acc / 2.6) % 2 else -1
    st.build("ridge_stakes", smooth=0, collide=False, **STAKE)
    # 方台：比埂面高 0.08（迈得上去；也避开田埂的顶面，不共面）
    ez = max(height(end[0], end[1]) + 0.18, SEA + 0.12)
    nx.box("ridge_end", (3.6, 3.6, ez + 0.08 + 2.6), (end[0], end[1], -2.6), (0, 0, end[2]),
           a="lilac_pale", b="lilac", pattern="tiles")

    SOLID.append(lambda px, py: any(seg_dist(px, py, ax, ay, bx, by) < RIDGE_W / 2 - 0.05 for (ax, ay), (bx, by) in segs))
    SOLID.append(lambda px, py: in_rect(px, py, end[0], end[1], end[2], 1.75, 1.75))
    return end[0], end[1], ez + 0.08


LOCK_STEPS = [-1.00, -1.14, -1.28, -1.42, -1.56, -1.70]
LOCK_TREAD = 1.2


def lock(x, y, yaw):
    """孤洲东边干滩上的闸：三面矮墙围着六级的台阶，一路下到水里（本地 +Y 朝西、往下）。
    上面几级还是干的，最下一级已经在水里（→ 沁泫池）"""
    g = nx.group("lock", (x, y, 0), (0, 0, yaw))
    w = 3.0
    k = fu.Kit()
    for i, zt in enumerate(LOCK_STEPS):
        k.box((w, LOCK_TREAD, zt + 2.9), (0, i * LOCK_TREAD, -2.9))
    k.build("lock_steps", parent=g, smooth=0, a="mist", b="lilac_pale", pattern="tiles")
    L = len(LOCK_STEPS) * LOCK_TREAD
    for s in (-1, 1):
        nx.box(f"lock_wall{s}", (0.6, L + 1.2, 2.35), (s * (w / 2 + 0.3), L / 2 - 0.6, -2.9), parent=g,
               ramp=("violet", "lilac_dark", "lilac"), pattern="bands")
    nx.box("lock_end", (w + 1.2, 0.6, 2.35), (0, L + 0.3, -2.9), parent=g,
           ramp=("violet", "lilac_dark", "lilac"), pattern="bands")
    i = len(LOCK_STEPS) - 1
    a = math.radians(yaw)
    ly = (i + 0.5) * LOCK_TREAD
    px, py = x - math.sin(a) * ly, y + math.cos(a) * ly
    nx.portal("portal_seeping", (px, py, LOCK_STEPS[i] + 1.0), "seeping", mode="walk", radius=0.8)
    # 闸里（台阶加两边的墙）都算实地
    SOLID.append(lambda qx, qy: in_rect(qx, qy, x, y, yaw, w / 2 + 0.6, L / 2 + 1.2, oy=L / 2 - 0.6))
    return px, py


def cup(x, y):
    """杯口：东岸地里嵌着一圈白的杯沿，里面一汪水。走进水里回家"""
    z = height(x, y)
    R = 2.2
    nx.torus("cup_rim", R + 0.15, 0.17, (x, y, z + 0.16), major_seg=40, minor_seg=8, a="white", b="mist", pattern="plain")
    nx.cylinder("cup_bed", R, R, 0.36, (x, y, z - 0.38), segments=32, a="blue", b="blue_pale", pattern="plain")
    nx.cylinder("cup_water", R + 0.02, R + 0.02, 0.02, (x, y, z + 0.12), segments=32, collide=False, shadow=False,
                **WATER["shallow"])
    nx.portal("portal_home", (x, y, z + 1.0), "house", at="shoal", mode="walk", radius=1.3)


def stakes(avoid):
    """干滩上一列列细桩（给尺度）：一根根插在露出来的滩涂上，不成行，只是标着人走过的地方"""
    rnd = random.Random(41)
    k = fu.Kit()
    placed = []
    n = 0
    tries = 0
    while n < 30 and tries < 900:
        tries += 1
        th = rnd.uniform(-1.7, 1.7)
        s = rnd.uniform(-8.0, 44.0)
        x, y = at_s(th, s)
        z = height(x, y)
        if z < SEA + 0.15 or z > T2 + 0.05:
            continue
        if not flat(x, y, 0.9):
            continue
        if any(math.hypot(x - ax, y - ay) < ar + 1.5 for ax, ay, ar in avoid):
            continue
        if any(math.hypot(x - qx, y - qy) < 2.6 for qx, qy in placed):
            continue
        placed.append((x, y))
        k.box((0.13, 0.13, rnd.uniform(0.8, 1.6)), (x, y, z - 0.12))
        n += 1
    k.build("stakes", smooth=0, collide=False, **STAKE)


def footprints(avoid):
    """一串似脚印的东西（纸片）：从出生点前一路走向湾心，平贴在湿泥上，给滩涂一点尺度"""
    rnd = random.Random(53)
    k = fu.Kit()
    x, y = 67.0, 5.5
    n = 0
    while n < 70:
        dx, dy = -1.0, rnd.uniform(-0.4, 0.4)
        L = math.hypot(dx, dy)
        x += dx / L * 0.9
        y += dy / L * 0.9
        if math.hypot(x, y) < 13:
            break
        z = height(x, y)
        if z < SEA + 0.1:
            continue
        if any(math.hypot(x - ax, y - ay) < ar for ax, ay, ar in avoid):
            n += 1
            continue
        side = 1 if n % 2 else -1
        yaw = math.degrees(math.atan2(-dx, dy)) + side * 12
        k.box((0.34, 0.2, 0.03), (x + side * 0.16 * math.cos(math.radians(yaw)), y - side * 0.16 * math.sin(math.radians(yaw)),
                                  z + 0.012), rot=(0, 0, yaw))
        n += 1
    k.build("footprints", smooth=0, collide=False, **PRINT)


def scraps(avoid):
    """几片薄薄的纸片（碎屑）：干滩上被风落下的东西，给尺度"""
    rnd = random.Random(67)
    k = fu.Kit()
    placed = []
    n = 0
    tries = 0
    while n < 12 and tries < 300:
        tries += 1
        th = rnd.uniform(-1.8, 1.8)
        s = rnd.uniform(-6.0, 44.0)
        x, y = at_s(th, s)
        z = height(x, y)
        if z < SEA + 0.15:
            continue
        if any(math.hypot(x - ax, y - ay) < ar + 1.0 for ax, ay, ar in avoid):
            continue
        if any(math.hypot(x - qx, y - qy) < 3.0 for qx, qy in placed):
            continue
        placed.append((x, y))
        k.box((rnd.uniform(0.24, 0.42), rnd.uniform(0.3, 0.5), 0.015),
              (x, y, z + 0.01), rot=(rnd.uniform(-4, 4), rnd.uniform(-4, 4), rnd.uniform(0, 180)))
        n += 1
    k.build("scraps", smooth=0, collide=False, shadow=False, a="pink_pale", b="lilac_pale", pattern="plain")


def build(extent=EXTENT):
    nx.into("env")
    nx.sun((0.40, -0.54, 0.86))
    nx.atmosphere("ebb")

    nx.into("things")
    gx, gy, gz = ridge()
    gauge(gx, gy, gz)
    print("[shoal-var-2] 水尺", round(gx, 2), round(gy, 2), "台面", round(gz, 2))

    # 闸：孤洲东边找一处滩涂开始入水的地方，最下一级放在那儿，六级台阶往回（东）退
    ly = -2.0
    lx = ISLE_C[0] + 30.0
    while lx > ISLE_C[0] + 6.0 and height(lx, ly) > SEA - 0.2:
        lx -= 0.2
    lock(lx + (len(LOCK_STEPS) - 1) * LOCK_TREAD, ly, 90)
    print("[shoal-var-2] 闸最下一级", round(lx, 2), "地面", round(height(lx, ly), 2))

    # 孤洲顶上的晶体：一圈石堆托着它（比默认大一圈，远远就要有分量）
    cx, cy = ISLE_C[0] + 0.5, ISLE_C[1] + 0.5
    base = height(cx, cy)
    for i, (rr, hh) in enumerate(((1.45, 0.28), (1.05, 0.56), (0.72, 0.82))):
        nx.cylinder(f"isle_cairn{i}", rr, rr * 0.8, 0.28, (cx, cy, base + hh - 0.28), segments=6, **STONE)
    nx.entrance("crystal", (cx, cy, base + 1.6), "", "", size=0.46)

    # 东岸：杯口（回家）与出生点。出生点站在岸沿上，一眼看见一层层往下的滩涂
    th0 = math.radians(2.0)
    ux, uy = at_s(math.radians(-7.0), edge_at(4, math.radians(-7.0)) + 5.5)
    cup(ux, uy)
    sx, sy = at_s(th0, edge_at(4, th0) + 3.0)
    yaw = facing(-1, -0.05)
    nx.spawn((sx, sy, height(sx, sy)), facing_deg=yaw)
    nx.arrive("house", (sx, sy, height(sx, sy)), facing_deg=yaw)
    print("[shoal-var-2] 出生点", round(sx, 2), round(sy, 2), "地面", round(height(sx, sy), 2))

    nx.into("pools")
    # 花房：北边岸上一只插花的大瓶
    vx, vy = settle(27.0, 37.0, 1.6)
    pf.gate_vase("shoal-var-2", (vx, vy, height(vx, vy)), facing(-1, -1))
    placed = pools([(sx, sy, 7.0), (ux, uy, 5.0), (vx, vy, 4.0), (gx, gy, 3.0)])

    nx.into("stones")
    avoid = [(ux, uy, 5.0), (sx, sy, 5.0), (vx, vy, 5.0), (gx, gy, 4.0), (ISLE_C[0], ISLE_C[1], 12.0)]
    avoid += [(x, y, r + 2.0) for x, y, r in placed]
    # 埂两边让开
    for px in range(0, 36, 3):
        avoid.append((px, 5.0, 4.0))
    tide_stones(avoid)
    # 出生点跟前一块潮石：那道 6.2m 的横纹就在头顶，一眼就是这一版的记号
    for dx, dy in ((6.0, 1.6), (7.5, 1.6), (9.5, 2.0), (5.0, 1.0)):
        px, py = sx - dx, sy + dy
        if flat(px, py, 1.2):
            tide_stone("stone_near", px, py, 1.25, MARK + 2.4 - height(px, py), 8.0, t=0.36)
            print("[shoal-var-2] 出生点旁的潮石", round(px, 1), round(py, 1), "地面", round(height(px, py), 2))
            break
    # 岸上再补两块，让这道横纹线从出生点起就横在眼前
    for dx, dy in ((12.0, -3.5), (18.0, 4.5), (14.0, 7.0)):
        px, py = sx - dx, sy + dy
        if flat(px, py, 1.2) and height(px, py) > SEA + 0.2:
            tide_stone(f"stone_near2", px, py, 1.0, MARK + 1.2 - height(px, py), -14.0, t=0.32)
            break

    nx.into("ground")
    terrain()
    bunds()
    walls()
    deep_fence()

    nx.into("water")
    sea()

    nx.into("litter")
    leaves(avoid)
    stakes(avoid)
    footprints(avoid)
    scraps(avoid)


if __name__ == "__main__":
    nx.reset()
    build()
    nx.save_blend("shoal-var-2")
    nx.export("shoal-var-2")
