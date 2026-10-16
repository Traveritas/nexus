"""浅梦 · 光斑（sunpatch）第二版：光的迷宫（mockup/shallows-02）。

一座有边的迷宫（N × N 格、每格 CELL 米，路宽 5.6m，墙 2.8m、格点上一根高一点的柱），四周一圈高墙。
头顶 ROOF_Z 米一整片看不见的顶（nx.shade），开着好几扇形状不同的天窗；太阳在转（sun_turn），
好几块光斑同时在迷宫里绕着各自的天窗正下方画圈。暗处不全黑：看得见墙和路的轮廓，格子粗（8px）；光里清楚（2px）。

- 光里才显出来的（lit_only）：岔路口地上的箭头和记号（三种：窗形 → 回家、花形 → 花房、菱形 → 晶体，
  箭头指着该拐的方向）、墙上的纹样带、中间大厅地上一圈刻度（光斑沿着它走，像一只钟）、东南角一片软垫。
- 几处角落：中间的大厅（刻度圈 ＋ 一座矮台）；西北的观景台（台阶上去，眼睛高过墙，看得见整座迷宫和天窗）；
  东北浮着的几块板（光斑扫过时它们的影子在地上转）；东南的软垫园。
- 出口：东北角地上一块亮着的落地窗形（走进去回家，对着家里客厅的落地窗）；西南角一只插花的大瓶（E「凑近」→ 花房）；
  东南角一枚晶体（站点先空着）。
- 出生点：西边一条通向大厅的路上，站在光里，朝东看。

运行：node scripts/blender.cjs build sunpatch，网页 ?world=sunpatch（?suntime=秒 拨到某一刻）
"""
import math
import os
import random
import sys
from collections import deque

import bmesh

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import furniture as fu  # noqa: E402
import nx  # noqa: E402
import prefabs as pf  # noqa: E402

N = 12            # 迷宫 N × N 格
CELL = 6.0
HALF = N * CELL / 2   # 36
EXTENT = N * CELL + 20
CENTER = (0, 0)

WALL_H = 3.0
WALL_T = 0.9      # 厚墙：实心的，不是隔板
OUTER_H = 4.6
OUTER_T = 0.8

ROOF_Z = 34.0
ROOF_T = 0.4
ELEV = 72.0
AZ0 = 0.0         # 一开始太阳在东
TURN = 30.0       # 度每分：十二分钟一圈
R = ROOF_Z / math.tan(math.radians(ELEV))   # 光斑绕的圈的半径（约 11m）：中间那扇的光斑一直在大厅里

# 天窗：(中心 x, y, 宽, 长, 十字窗棂)。坐标取整，顶按 1m 的格子开洞
SKYLIGHTS = [
    (0, 0, 16, 16, True),      # 中间
    (-21, 18, 6, 34, False),   # 西北，一条长缝（南北向）
    (22, 22, 14, 14, True),    # 东北
    (-20, -20, 12, 16, True),  # 西南
    (14, -26, 34, 6, False),   # 东南，一条长缝（东西向）
    (-30, -4, 8, 10, False),   # 西
    (29, 0, 10, 16, True),     # 东
    (2, 29, 16, 8, False),     # 北
    (-8, -30, 6, 6, False),    # 南
]

FLOOR = dict(a="lilac_pale", b="pink", pattern="drift")
WALL = dict(ramp=("lilac_dark", "lilac", "pink_pale"), pattern="plain")
OUTER = dict(ramp=("violet", "lilac_dark", "lilac"), pattern="bands")
FRAME = dict(a="gold", b="pink_pale", pattern="plain")
PANE = dict(a="white", b="pink_pale", pattern="plain")
MARK = {"home": dict(a="gold", b="white", pattern="plain"),
        "glasshouse": dict(a="pink", b="pink_pale", pattern="plain"),
        "crystal": dict(a="blue_pale", b="white", pattern="plain")}
BAND = [dict(a="pink_pale", b="gold", pattern="plain"), dict(a="blue_pale", b="white", pattern="plain"),
        dict(a="gold", b="pink_pale", pattern="plain")]
TUFTS = [dict(ramp=("rose", "pink_pale", "white"), pattern="grain"),
         dict(ramp=("pink", "pink_pale", "gold"), pattern="grain"),
         dict(ramp=("lilac", "blue_pale", "white"), pattern="grain")]


def sun_dir(az_deg):
    e, a = math.radians(ELEV), math.radians(az_deg)
    return (math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e))


def cx(i):
    return -HALF + CELL * (i + 0.5)


# ── 迷宫 ──────────────────────────────────────────

# 打通成一间的几处（格的范围 i0..i1, j0..j1，含）
ROOMS = {
    "hall": (4, 7, 4, 7),       # 中间大厅（24 × 24m）
    "lookout": (1, 2, 8, 9),    # 西北观景台
    "slabs": (9, 10, 9, 10),    # 东北浮板
    "garden": (9, 10, 1, 2),    # 东南软垫园
}
HOME_CELL = (11, 11)
VASE_CELL = (0, 0)
CRYSTAL_CELL = (11, 0)
SPAWN_CELL = (3, 5)


def gen_maze(seed=4):
    """深度优先生成，再打掉一些墙绕出环路（少死胡同）、把几处房间打通。返回开着的边：{((i,j),(i2,j2))}"""
    rnd = random.Random(seed)
    opened = set()

    def key(a, b):
        return (a, b) if a < b else (b, a)

    seen = {(0, 0)}
    stack = [(0, 0)]
    while stack:
        c = stack[-1]
        nb = [(c[0] + dx, c[1] + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        nb = [n for n in nb if 0 <= n[0] < N and 0 <= n[1] < N and n not in seen]
        if not nb:
            stack.pop()
            continue
        n = rnd.choice(nb)
        opened.add(key(c, n))
        seen.add(n)
        stack.append(n)
    # 环路：打掉一成多的墙
    for i in range(N):
        for j in range(N):
            for n in ((i + 1, j), (i, j + 1)):
                if n[0] < N and n[1] < N and rnd.random() < 0.14:
                    opened.add(key((i, j), n))
    # 房间里面打通
    for i0, i1, j0, j1 in ROOMS.values():
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                if i < i1:
                    opened.add(key((i, j), (i + 1, j)))
                if j < j1:
                    opened.add(key((i, j), (i, j + 1)))
    # 出生点那条路直通大厅
    for i in range(SPAWN_CELL[0], 4):
        opened.add(key((i, 5), (i + 1, 5)))
    return opened, key


def build_walls(opened, key):
    """厚墙：每段从格点到格点、两头各伸出半个墙厚，转角处自然接上；合成一个网格。返回墙段列表（给墙上的纹样用）"""
    walls = fu.Kit()
    segs = []
    for i in range(N - 1):
        for j in range(N):
            if key((i, j), (i + 1, j)) not in opened:
                segs.append(("y", -HALF + CELL * (i + 1), -HALF + CELL * j, -HALF + CELL * (j + 1)))
    for i in range(N):
        for j in range(N - 1):
            if key((i, j), (i, j + 1)) not in opened:
                segs.append(("x", -HALF + CELL * (j + 1), -HALF + CELL * i, -HALF + CELL * (i + 1)))
    for axis, at, a, b in segs:
        mid, ln = (a + b) / 2, b - a + WALL_T
        if axis == "y":
            walls.box((WALL_T, ln, WALL_H), (at, mid, 0))
        else:
            walls.box((ln, WALL_T, WALL_H), (mid, at, 0))
    walls.build("maze_walls", smooth=0, top="lilac_pale", **WALL)
    return segs


def outer_wall():
    L = 2 * HALF + 2 * OUTER_T
    o = HALF + OUTER_T / 2
    nx.box("outer_s", (L, OUTER_T, OUTER_H), (0, -o, 0), **OUTER)
    nx.box("outer_n", (L, OUTER_T, OUTER_H), (0, o, 0), **OUTER)
    nx.box("outer_w", (OUTER_T, 2 * HALF, OUTER_H), (-o, 0, 0), **OUTER)
    nx.box("outer_e", (OUTER_T, 2 * HALF, OUTER_H), (o, 0, 0), **OUTER)


# ── 顶与天窗 ───────────────────────────────────────

def roof():
    """看不见的顶：按 1m 的格子盖满（迷宫外再让出 R 多），天窗处留洞；每行连成一段合成一个网格。十字窗棂另放"""
    ext = int(HALF + R + 8)
    holes = []
    for x, y, w, l, _ in SKYLIGHTS:
        holes.append((x - w / 2, y - l / 2, x + w / 2, y + l / 2))
    k = fu.Kit()
    for j in range(-ext, ext):
        y0, y1 = j, j + 1
        cuts = sorted((h[0], h[2]) for h in holes if h[1] <= y0 and y1 <= h[3])
        cur = -ext
        for a, b in cuts:
            if a > cur:
                k.box((a - cur, 1.0, ROOF_T), ((a + cur) / 2, y0 + 0.5, ROOF_Z))
            cur = max(cur, b)
        if cur < ext:
            k.box((ext - cur, 1.0, ROOF_T), ((ext + cur) / 2, y0 + 0.5, ROOF_Z))
    for n, (x, y, w, l, cross) in enumerate(SKYLIGHTS):
        if cross:
            k.box((w, 0.7, ROOF_T), (x, y, ROOF_Z))
            k.box((0.7, l, ROOF_T), (x, y, ROOF_Z))
    nx.shade(k.build("roof", smooth=0))


def skylights():
    """看得见的天窗：一圈淡金的框、窗棂、发白的窗格（自己发亮、不投影），悬在半空"""
    z = ROOF_Z
    fw = 0.6
    st = dict(collide=False, shadow=False, **FRAME)
    for n, (x, y, w, l, cross) in enumerate(SKYLIGHTS):
        hw, hl = w / 2, l / 2
        nx.box(f"sky{n}_s", (w + 2 * fw, fw, ROOF_T + 0.1), (x, y - hl - fw / 2, z - 0.05), **st)
        nx.box(f"sky{n}_n", (w + 2 * fw, fw, ROOF_T + 0.1), (x, y + hl + fw / 2, z - 0.05), **st)
        nx.box(f"sky{n}_w", (fw, l, ROOF_T + 0.12), (x - hw - fw / 2, y, z - 0.06), **st)
        nx.box(f"sky{n}_e", (fw, l, ROOF_T + 0.12), (x + hw + fw / 2, y, z - 0.06), **st)
        if cross:
            nx.box(f"sky{n}_bx", (w, 0.7, ROOF_T + 0.06), (x, y, z - 0.03), **st)
            nx.box(f"sky{n}_by", (0.7, l, ROOF_T + 0.14), (x, y, z - 0.07), **st)
            for sx in (-1, 1):
                for sy in (-1, 1):
                    nx.box(f"sky{n}_p{sx}{sy}", (hw - 0.35, hl - 0.35, 0.05), (x + sx * (hw + 0.35) / 2, y + sy * (hl + 0.35) / 2, z + ROOF_T / 2 + 0.02),
                           collide=False, shadow=False, emit=1.0, **PANE)
        else:
            nx.box(f"sky{n}_p", (w, l, 0.05), (x, y, z + ROOF_T / 2 + 0.02), collide=False, shadow=False, emit=1.0, **PANE)


# ── 只在光里的东西 ─────────────────────────────────

def lit(k, name, style):
    if k.f:
        k.build(name, smooth=0, collide=False, shadow=False, lit_only=True, **style)


def glyph(k, kind, x, y, s=1.0):
    """地上的记号：窗形（回家）、花形（花房）、菱形（晶体）。贴地薄板"""
    z, t = 0.006, 0.02
    if kind == "home":
        w, h, b = 0.9 * s, 1.3 * s, 0.14 * s
        for dx, dy, sx, sy in ((0, h / 2, w, b), (0, -h / 2, w, b), (-w / 2, 0, b, h), (w / 2, 0, b, h), (0, 0, w, b), (0, 0, b, h)):
            k.box((sx, sy, t + (0.002 if (sx, sy) == (b, h) and dx == 0 else 0)), (x + dx, y + dy, z))
    elif kind == "glasshouse":
        for p in range(5):
            a = math.tau * p / 5
            k.box((0.32 * s, 0.32 * s, t), (x + math.cos(a) * 0.38 * s, y + math.sin(a) * 0.38 * s, z), rot=(0, 0, math.degrees(a) + 45))
        k.box((0.26 * s, 0.26 * s, t + 0.003), (x, y, z))
    else:
        k.box((0.75 * s, 0.75 * s, t), (x, y, z), rot=(0, 0, 45))


def arrow(k, x, y, dx, dy, s=1.0):
    """箭头：两条斜杠拼成的 V，尖朝 (dx, dy)"""
    a = math.degrees(math.atan2(dy, dx))
    z, t = 0.006, 0.02
    for sgn in (-1, 1):
        ang = math.radians(a + 180 + sgn * 35)
        ln = 0.9 * s
        k.box((ln, 0.18 * s, t + (0.002 if sgn > 0 else 0)), (x + math.cos(ang) * ln / 2 * 0.95, y + math.sin(ang) * ln / 2 * 0.95, z),
              rot=(0, 0, math.degrees(ang)))


def signs(opened, key):
    """岔路口的提示：从出口往回广度优先，每个岔路口（通着三条以上的格）摆一个该出口的记号和一只指路的箭头"""
    def nbrs(c):
        for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (c[0] + d[0], c[1] + d[1])
            if 0 <= n[0] < N and 0 <= n[1] < N and key(c, n) in opened:
                yield n
    room_cells = {(i, j) for i0, i1, j0, j1 in ROOMS.values() for i in range(i0, i1 + 1) for j in range(j0, j1 + 1)}
    kits = {k: fu.Kit() for k in MARK}
    slot = {"home": (-1.4, 1.4), "glasshouse": (1.4, 1.4), "crystal": (0.0, -1.6)}
    for kind, goal in (("home", HOME_CELL), ("glasshouse", VASE_CELL), ("crystal", CRYSTAL_CELL)):
        nxt = {goal: None}
        q = deque([goal])
        while q:
            c = q.popleft()
            for n in nbrs(c):
                if n not in nxt:
                    nxt[n] = c
                    q.append(n)
        for c, to in nxt.items():
            if to is None or c in room_cells:
                continue
            if sum(1 for _ in nbrs(c)) < 3 and c != SPAWN_CELL:
                continue
            ox, oy = slot[kind]
            x, y = cx(c[0]) + ox, cx(c[1]) + oy
            glyph(kits[kind], kind, x, y, 0.8)
            dx, dy = to[0] - c[0], to[1] - c[1]
            arrow(kits[kind], x + dx * 0.9, y + dy * 0.9, dx, dy, 0.7)
    for kind, k in kits.items():
        lit(k, f"signs_{kind}", MARK[kind])


def wall_bands(segs, rnd):
    """墙上的纹样带：一排小方块，贴在墙面外 1cm（两面都有），只在光扫过时显出来"""
    kits = [fu.Kit() for _ in BAND]
    for axis, at, a, b in segs:
        if rnd.random() > 0.55:
            continue
        c = rnd.randrange(len(BAND))
        z = rnd.choice((0.9, 1.4, 1.9))
        n = 7
        step = (b - a - 1.6) / n
        for side in (-1, 1):
            off = at + side * (WALL_T / 2 + 0.012)
            for t in range(n):
                v = a + 0.8 + step * (t + 0.5)
                sz = 0.32 if t % 2 else 0.22
                if axis == "y":
                    kits[c].box((0.02, sz, sz), (off, v, z - sz / 2), rot=(0, 0, 0))
                else:
                    kits[c].box((sz, 0.02, sz), (v, off, z - sz / 2))
    for n, k in enumerate(kits):
        lit(k, f"bands_{n}", BAND[n])


def hall():
    """中间大厅：一座矮圆台；地上一圈刻度（光斑沿着它走，照到哪格亮哪格）"""
    nx.cylinder("hall_dais", 2.4, 2.2, 0.3, (0, 0, 0), segments=12, ramp=("lilac", "lilac_pale", "white"), pattern="plain")
    k = fu.Kit()
    # 中间那扇天窗的光斑中心绕 (0,0) 画半径 R 的圈：刻度落在这圈上（落在墙里的跳过，不要紧——墙里看不见）
    for n in range(48):
        a = math.tau * n / 48
        big = n % 4 == 0
        ln = 1.0 if big else 0.5
        k.box((ln, 0.16, 0.02 + (0.002 if n % 2 else 0)), (math.cos(a) * R, math.sin(a) * R, 0.006), rot=(0, 0, math.degrees(a)))
    lit(k, "hall_ticks", dict(a="gold", b="white", pattern="plain"))


def lookout():
    """西北观景台：一段宽台阶上到 4.5m 的平台，眼睛高出墙三米多，看得进巷子里"""
    i0, i1, j0, j1 = ROOMS["lookout"]
    x0, y0 = -HALF + CELL * i0, -HALF + CELL * j0
    st = dict(ramp=("lilac_dark", "lilac_pale", "white"), pattern="plain")
    steps = 15
    for s in range(steps):
        nx.box(f"look_step{s}", (2.4, 0.5, 0.3 * (s + 1)), (x0 + 3.0, y0 + 1.0 + 0.5 * s, 0), **st)
    top = 0.3 * steps
    nx.box("look_deck", (5.0, 3.0, top), (x0 + 3.0 + 1.3, y0 + 1.0 + 0.5 * steps + 1.25, 0), **st)


def slabs():
    """东北：几块板浮在半空，光斑扫过时它们的影子在地上转"""
    i0, i1, j0, j1 = ROOMS["slabs"]
    xm, ym = -HALF + CELL * (i0 + 1), -HALF + CELL * (j0 + 1)
    rnd = random.Random(9)
    for n in range(6):
        w, d = rnd.uniform(1.4, 3.0), rnd.uniform(0.8, 1.8)
        nx.box(f"slab{n}", (w, d, 0.18), (xm + rnd.uniform(-3.5, 3.5), ym + rnd.uniform(-3.5, 3.5), rnd.uniform(3.4, 7.5)),
               rot=(rnd.uniform(-12, 12), rnd.uniform(-12, 12), rnd.uniform(0, 180)), collide=False,
               ramp=("violet", "lilac", "pink_pale"), pattern="plain")


def tuft(k, x, y, r, hh, rnd):
    seg = rnd.choice((5, 6, 7))
    a0 = rnd.uniform(0, math.tau)
    base, mid = [], []
    for s in range(seg):
        a = a0 + math.tau * s / seg
        rr = r * rnd.uniform(0.8, 1.15)
        base.append((x + math.cos(a) * rr, y + math.sin(a) * rr, -0.2))
        mid.append((x + math.cos(a) * rr * 0.6, y + math.sin(a) * rr * 0.6, hh * rnd.uniform(0.55, 0.75)))
    verts = base + mid + [(x + rnd.uniform(-0.2, 0.2) * r, y + rnd.uniform(-0.2, 0.2) * r, hh)]
    top = 2 * seg
    faces = []
    for s in range(seg):
        t = (s + 1) % seg
        faces.append((s, t, seg + t, seg + s))
        faces.append((seg + s, seg + t, top))
    k._add(verts, faces)


def face_up(obj):
    if obj is None:
        return
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def garden():
    """东南软垫园：一片低矮的软垫，只在光里"""
    i0, i1, j0, j1 = ROOMS["garden"]
    rnd = random.Random(5)
    kits = [fu.Kit() for _ in TUFTS]
    x0, y0 = -HALF + CELL * i0 + 0.8, -HALF + CELL * j0 + 0.8
    for _ in range(70):
        x, y = rnd.uniform(x0, x0 + 2 * CELL - 1.6), rnd.uniform(y0, y0 + 2 * CELL - 1.6)
        r = rnd.uniform(0.3, 1.0)
        tuft(kits[rnd.choices((0, 1, 2), (5, 3, 2))[0]], x, y, r, r * rnd.uniform(0.5, 0.9), rnd)
    for n, k in enumerate(kits):
        if k.f:
            face_up(k.build(f"garden_{n}", smooth=0, collide=False, shadow=False, lit_only=True, **TUFTS[n]))


# ── 出口 ──────────────────────────────────────────

HOME_W, HOME_H, HOME_B = 1.8, 2.6, 0.12      # 地上那扇窗：外框 1.8 × 2.6，框宽 0.12
PIT_Z = -3.6                                 # 窗底下的井底


def home_hole():
    """地上那扇窗的洞口（窗框里面那一块）：(x0, y0, x1, y1)"""
    x, y = cx(HOME_CELL[0]), cx(HOME_CELL[1])
    hw, hh = HOME_W / 2 - HOME_B, HOME_H / 2 - HOME_B
    return x - hw, y - hh, x + hw, y + hh


def floor():
    """地板：一整块，只在地上那扇窗底下开一个洞（四块拼起来，彼此只贴边、不叠）"""
    S = HALF + OUTER_T + 0.2
    x0, y0, x1, y1 = home_hole()
    for name, (a, b, c, d) in (("w", (-S, -S, x0, S)), ("e", (x1, -S, S, S)), ("s", (x0, -S, x1, y0)), ("n", (x0, y1, x1, S))):
        nx.box(f"floor_{name}", (c - a, d - b, 1.0), ((a + c) / 2, (b + d) / 2, -1.0), **FLOOR)


def home_window(x, y):
    """回家：地上一扇亮着的落地窗（1.8 × 2.6，十字棂），对着家里客厅的落地窗。两扇窗扇是光做的，平躺着盖住地上一个洞；
    走近按 E「推开窗」，两扇往下翻开、垂进洞里——底下是家里的夜。走上去就掉下去，落回客厅的落地窗前"""
    w, h, b = HOME_W, HOME_H, HOME_B
    pane = dict(shadow=False, emit=1.0, a="pink_pale", b="gold", pattern="plain")
    frame = dict(collide=False, shadow=False, a="gold", b="pink_pale", pattern="plain")
    # 外框：贴在洞口外的地上，不动
    nx.box("home_frame_s", (w + 2 * b, b * 2, 0.03), (x, y - h / 2, 0.008), **frame)
    nx.box("home_frame_n", (w + 2 * b, b * 2, 0.03), (x, y + h / 2, 0.008), **frame)
    nx.box("home_frame_w", (b * 2, h - 2 * b, 0.03), (x - w / 2, y, 0.008), **frame)
    nx.box("home_frame_e", (b * 2, h - 2 * b, 0.03), (x + w / 2, y, 0.008), **frame)
    # 两扇窗扇：铰链在洞口的东西两条长边上（原点在铰链，地面高），各伸到正中；
    # 光的窗格挡人（关着能站上去），横棂和中间那条竖棂（两扇各半条）压在上面
    hw, L = w / 2 - b, h - 2 * b
    for s in (-1, 1):
        lw = hw - 0.004
        glass, bars = fu.Kit(), fu.Kit()
        glass.box((lw, L - 0.008, 0.02), (-s * lw / 2, 0, 0))
        bars.box((lw - 0.006, b * 1.4, 0.032), (-s * lw / 2, 0, 0.002))
        bars.box((b * 0.7, L - 0.014, 0.034), (-s * (lw - b * 0.35 - 0.003), 0, 0.002))
        objs = [glass.build(f"home_leaf{s}", loc=(x + s * hw, y, 0.0), smooth=0, **pane),
                bars.build(f"home_leaf{s}_bars", loc=(x + s * hw, y, 0.0), smooth=0, **frame)]
        for o in objs:
            nx.pose(o, "home_window", on="key", at=(x, y, 0.9), radius=2.0, rot=(0, -90 * s, 0), time=0.9,
                    title="推开窗|关上窗")
    # 洞底下：一口井（井壁接在地板底下），井底是夜里的颜色，落着一块斜斜的月光
    x0, y0, x1, y1 = home_hole()
    t, top = 0.2, -1.0
    wall = dict(ramp=("ink", "violet_deep", "violet"), pattern="plain")
    for name, size, loc in (("w", (t, y1 - y0 + 2 * t, top - PIT_Z), (x0 - t / 2, y, PIT_Z)),
                            ("e", (t, y1 - y0 + 2 * t, top - PIT_Z), (x1 + t / 2, y, PIT_Z)),
                            ("s", (x1 - x0, t, top - PIT_Z), (x, y0 - t / 2, PIT_Z)),
                            ("n", (x1 - x0, t, top - PIT_Z), (x, y1 + t / 2, PIT_Z))):
        nx.box(f"home_pit_{name}", size, loc, **wall)
    nx.box("home_pit_floor", (x1 - x0 + 2 * t, y1 - y0 + 2 * t, 0.3), (x, y, PIT_Z - 0.3), a="ink", b="violet_deep", pattern="plain")
    nx.box("home_pit_moon", (0.7, 1.3, 0.01), (x + 0.2, y - 0.3, PIT_Z + 0.002), rot=(0, 0, 18), collide=False, shadow=False,
           emit=0.6, a="blue_pale", b="mist", pattern="plain")
    # 掉进井里一截（脚低过 -0.9m）就回家；窗扇没推开到底不算
    nx.portal("portal_home", (x, y, -1.3), "house", at="sunpatch", mode="walk", radius=min(hw, L / 2) - 0.02, need="home_window")


def build(extent=EXTENT):
    nx.into("env")
    nx.sun(sun_dir(AZ0))
    nx.atmosphere("umbra", grid=3, grid_lit=1, shadow_out=True, shadow_reach=70, sun_turn=TURN)

    nx.into("maze")
    floor()
    opened, key = gen_maze()
    segs = build_walls(opened, key)
    outer_wall()

    nx.into("roof")
    roof()
    skylights()

    nx.into("light")
    signs(opened, key)
    wall_bands(segs, random.Random(12))
    hall()
    garden()

    nx.into("places")
    lookout()
    slabs()
    home_window(cx(HOME_CELL[0]), cx(HOME_CELL[1]))
    pf.gate_vase("sunpatch", (cx(VASE_CELL[0]), cx(VASE_CELL[1]), 0), 45)
    nx.entrance("crystal_sunpatch", (cx(CRYSTAL_CELL[0]), cx(CRYSTAL_CELL[1]), 1.6), "", "")

    # 出生点：西边通向大厅的路上，朝东
    nx.spawn((cx(SPAWN_CELL[0]) - 1.0, cx(SPAWN_CELL[1]), 0), facing_deg=-90)


if __name__ == "__main__":
    nx.reset()
    build()
    nx.save_blend("sunpatch")
    nx.export("sunpatch")
