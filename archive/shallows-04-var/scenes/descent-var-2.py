"""浅梦 · 下沉 · 方楼（descent-var-2）：圆井心里砌着一座方形的楼，一层层错着转 90°。

底本是第三轮的 descent.py（见 mockup/shallows-04/README.md 的「下沉 · 井」）。
这一版把井心填成一座方楼：边长约 12m，楼心偏开井心 2m，每层绕井心转 90°（方跟着挪位、长方那一边翻过去）。
楼与井壁之间剩下的那一弯月牙，就是从井口看得见的大坑——人沿井壁的台走，从月牙处的门进楼，
楼里是巷子与小房间，穿过楼到对面又回到月牙。从上往下看：圆井口里一个转着的方，一层层错开。
上两层楼里留着一口方天井（对着井心，上下对齐）；第三层往下楼占满，井底不再看得见；
直到第 4 层楼忽然收进去，只剩中间一小块，露出白的井底与池（对比）。

修掉的（第三轮的量过）：
- 楼梯每级顶面 = z − RISE·(k+1)，级数 20（20×0.3 = 6.0 正好一层）；上行下行都走得通。
- 梯带与台同宽（STAIR_IN = LEDGE_W），不再留那道 0.4m 的槽。
- 台面缺口、门、横缝的方位全部由 SPAN / STAIR_A 派生，没有手算常数。
- 井口那片平白（rim_flat）收窄，台阶从更近处开始。
- 井里那两只浮环挪到楼顶以上、井口以内的天井里，不穿楼不穿墙。

运行：node scripts/blender.cjs build descent-var-2，网页 ?world=descent-var-2
"""
import math
import os
import random
import sys

import bpy

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import furniture as fu  # noqa: E402
import nx  # noqa: E402
import prefabs as pf  # noqa: E402
import shapes as sh  # noqa: E402

EXTENT = 130
CENTER = (0, 0)

R = 13.0
WT = 1.2
LV = 6.0
NL = 5
LEDGE_W = 3.0
LEDGE_T = 0.8
SEG = 128

STAIR_IN = LEDGE_W
STEPS = 20
RISE = 0.3
TREAD = math.degrees(0.85 / (R - STAIR_IN / 2))
SPAN = TREAD * STEPS

STAIR_A = [200.0]
for _ in range(NL - 1):
    STAIR_A.append((STAIR_A[-1] + SPAN + 140.0) % 360)

# ── 方楼 ──────────────────────────────────────────
SX, SY = 12.6, 12.0     # 楼板的两边（本地 x / y）——角最远到 r 9.92，不碰井壁的台（r≥10）
OFF = 1.6               # 楼心偏开井心（再大角就伸进台里，挡住梯口了）
BT = 0.4                # 楼的墙厚
BLD_T = 0.5             # 楼板厚
COURT = 2.4             # 上两层楼板中间的方天井边长（天井对着井心，上下对齐）
DOOR_W = 1.4
# 每层楼心偏开的方位：逐层 +90°（楼跟着绕井心转）
BT_A = [240.0, 330.0, 60.0, 150.0]
BT_H = [3.5, LV - 0.5, LV - 0.5]    # 第 1 层顶上是天（矮墙），第 2、3 层顶上是上一层楼板

BAY_H = 3.0
BAND = 3.2

WALLS = [
    dict(a="lilac_pale", b="mist", pattern="bands"),
    dict(a="lilac_pale", b="lilac", pattern="bands"),
    dict(a="lilac", b="lilac_dark", pattern="bands"),
    dict(a="lilac_dark", b="violet", pattern="bands"),
    dict(a="violet", b="violet_deep", pattern="bands"),
    dict(a="mist", b="white", pattern="bands"),
]
FLOORS = [
    dict(a="mist", b="lilac_pale", pattern="tiles"),
    dict(a="pink_pale", b="pink", pattern="tiles"),
    dict(a="pink", b="pink_pale", pattern="tiles"),
    dict(a="rose", b="pink", pattern="tiles"),
    dict(a="rose_deep", b="rose", pattern="tiles"),
    dict(a="white", b="mist", pattern="tiles"),
]
BLD_FLOOR = dict(a="mist", b="lilac_pale", pattern="tiles")
BLD_WALL = dict(a="lilac_pale", b="lilac", pattern="tiles")
GLOW = dict(a="gold", b="pink_pale", pattern="plain")
WARM = "#ffe6c8"


def zl(n):
    return -LV * n


def polar(r, a_deg, z=0.0):
    a = math.radians(a_deg)
    return (math.cos(a) * r, math.sin(a) * r, z)


def norm(a):
    return a % 360.0


def arcs(name, r_out, r_in, h, z, gaps, **style):
    if not gaps:
        sh.tube(name, r_out, r_in, h, (0, 0, z), segments=SEG, **style)
        return
    gaps = sorted(((a0 % 360), (a0 % 360) + (a1 - a0)) for a0, a1 in gaps)
    for i, (a0, a1) in enumerate(gaps):
        b0 = gaps[(i + 1) % len(gaps)][0] + (360 if i == len(gaps) - 1 else 0)
        if b0 - a1 > 0.5:
            sh.tube(f"{name}_{i}", r_out, r_in, h, (0, 0, z), segments=SEG, arc=b0 - a1, start=a1, **style)


def join(objs, name):
    objs = [o for o in objs if o is not None and o.type == "MESH"]
    if len(objs) < 2:
        return objs[0] if objs else None
    with bpy.context.temp_override(active_object=objs[0], object=objs[0], selected_objects=objs,
                                   selected_editable_objects=objs):
        bpy.ops.object.join()
    objs[0].name = name
    return objs[0]


def gap_of(a, w, r=R):
    half = math.degrees((w / 2 + 0.05) / r)
    return (a - half, a + half)


def arc_span(a, w, r):
    return math.degrees(w / r)


def stair_range(n):
    return (STAIR_A[n], STAIR_A[n] + SPAN)


def landing_range(n):
    a = STAIR_A[n - 1] + SPAN - TREAD
    return (a, a + TREAD)


def ledge_gaps(n):
    return [stair_range(n), landing_range(n)]


def in_arc(a, lo, hi):
    a, lo, hi = norm(a), norm(lo), norm(hi)
    if hi < lo:
        hi += 360
    if a < lo:
        a += 360
    return lo <= a <= hi


def free_at(n, deg, w=0.0):
    da = arc_span(deg, w / 2, R - LEDGE_W / 2) + 1.0
    for lo, hi in ledge_gaps(n):
        if in_arc(deg, lo - da, hi + da):
            return False
    return True


def solid_arcs(n):
    gaps = sorted((norm(lo), norm(lo) + (hi - lo)) for lo, hi in ledge_gaps(n))
    out = []
    for i, (_, a1) in enumerate(gaps):
        b0 = gaps[(i + 1) % len(gaps)][0] + (360 if i == len(gaps) - 1 else 0)
        if b0 - a1 > 2.0:
            out.append((a1, b0))
    return out


# ── 楼：本地坐标 → 世界 ─────────────────────────────

def bcenter(n):
    return polar(OFF, BT_A[n - 1])


def byaw(n):
    return BT_A[n - 1]


def bl(n, lx, ly, lz=0.0):
    """楼里（第 n 层）的本地坐标 → 世界：lx 沿半径朝外、ly 沿切向（逆时针）"""
    cx, cy = bcenter(n)[:2]
    a = math.radians(byaw(n))
    return (cx + math.cos(a) * lx - math.sin(a) * ly, cy + math.sin(a) * lx + math.cos(a) * ly, zl(n) + lz)


def bframe(n):
    cx, cy = bcenter(n)[:2]
    return nx.group(f"bld{n}", (cx, cy, zl(n) - 0.03), (0, 0, byaw(n)))


def slab_with_holes(name, g, sx, sy, holes, t, **style):
    """一块矩形楼板，挖掉若干矩形洞（本地坐标 [(x0,y0,x1,y1)]）；按条带切"""
    ys = sorted(set([-sy / 2, sy / 2] + [h[1] for h in holes] + [h[3] for h in holes]))
    for i in range(len(ys) - 1):
        y0, y1 = ys[i], ys[i + 1]
        if y1 - y0 < 1e-4:
            continue
        ym = (y0 + y1) / 2
        hs = [h for h in holes if h[1] <= ym <= h[3]]
        xs = sorted(set([-sx / 2, sx / 2] + [h[0] for h in hs] + [h[2] for h in hs]))
        for j in range(len(xs) - 1):
            x0, x1 = xs[j], xs[j + 1]
            if x1 - x0 < 1e-4:
                continue
            nx.box(f"{name}_{i}_{j}", (x1 - x0, y1 - y0, t), ((x0 + x1) / 2, ym, -t), parent=g, **style)


def bwall(name, g, axis, fixed, length, h, doors, **style):
    """楼的一面墙：axis='y' 沿本地 y 走、位于本地 x=fixed；doors 时中间留一个门洞"""
    segs = [(-length / 2, -DOOR_W / 2), (DOOR_W / 2, length / 2)] if doors else [(-length / 2, length / 2)]
    for i, (a, b) in enumerate(segs):
        L = b - a
        if L < 0.05:
            continue
        mid = (a + b) / 2
        if axis == "y":
            nx.box(f"{name}_{i}", (BT, L, h), (fixed, mid, 0), parent=g, **style)
        else:
            nx.box(f"{name}_{i}", (L, BT, h), (mid, fixed, 0), parent=g, **style)


# ── 井 ────────────────────────────────────────────

BAYS = {1: [(160.0, 2.4), (190.0, 2.4), (220.0, 2.4), (250.0, 2.4), (310.0, 2.4)]}


def bay(name, a, z, w, d, back, style):
    k = fu.Kit()
    fw = w + 1.2
    k.box((fw, d, 0.4), (0, d / 2, z - 0.41))
    for sx in (-1, 1):
        k.box((0.5, d, BAY_H + 0.4), (sx * (w / 2 + 0.25), d / 2, z - 0.01))
    k.box((fw, d, 0.4), (0, d / 2, z + BAY_H))
    if back:
        k.box((fw, 0.6, BAY_H + 0.82), (0, d + 0.3, z - 0.41))
    x, y, _ = polar(R, a)
    return k.build(f"bay_{name}", loc=(x, y, 0), rot=(0, 0, a - 90), smooth=0, **style)


def well():
    for n in range(1, NL + 1):
        z = zl(n)
        st = WALLS[n]
        gaps = [gap_of(a, w) for a, w in BAYS.get(n, [])]
        arcs(f"wall{n}_band", R + WT, R, BAND + 0.41, z - 0.41, gaps, **st)
        top = zl(n - 1) - 0.41 if n > 1 else 0.0
        sh.tube(f"wall{n}_solid", R + WT, R, top - (z + BAND), (0, 0, z + BAND), segments=SEG, **st)
    sh.tube("wall_foot", R + WT, R, 1.0, (0, 0, zl(NL) - 1.41), segments=SEG, **WALLS[NL])
    for n in range(1, NL):
        arcs(f"ledge{n}", R, R - LEDGE_W, LEDGE_T, zl(n) - LEDGE_T, ledge_gaps(n), **FLOORS[n])
    stairs()


def stairs():
    for n in range(NL):
        a0, z = STAIR_A[n], zl(n)
        st = FLOORS[n + 1] if n + 1 < NL else FLOORS[NL - 1]
        steps = [sh.tube(f"stair{n}_{k:02d}", R, R - STAIR_IN, RISE, (0, 0, z - RISE * (k + 2)), segments=SEG,
                         arc=TREAD, start=a0 + TREAD * k, **st) for k in range(STEPS)]
        join(steps, f"stair{n}")


# ── 方楼本体 ──────────────────────────────────────

def court_hole():
    """方天井：本地坐标（天井对着井心，所以本地 x=−OFF）"""
    return (-OFF - COURT / 2, -COURT / 2, -OFF + COURT / 2, COURT / 2)


def building():
    for n in (1, 2, 3):
        g = bframe(n)
        holes = [court_hole()] if n <= 2 else []
        slab_with_holes(f"bld{n}_floor", g, SX, SY, holes, BLD_T, **BLD_FLOOR)
        h = BT_H[n - 1]
        bwall(f"bld{n}_wx", g, "y", -SX / 2 + BT / 2, SY, h, True, **BLD_WALL)
        bwall(f"bld{n}_ex", g, "y", SX / 2 - BT / 2, SY, h, True, **BLD_WALL)
        bwall(f"bld{n}_wy", g, "x", -SY / 2 + BT / 2, SX - 2 * BT, h, n != 2, **BLD_WALL)
        bwall(f"bld{n}_ey", g, "x", SY / 2 - BT / 2, SX - 2 * BT, h, n != 2, **BLD_WALL)
        thresholds(n)

    # 第 1 层：两道隔墙隔出南北两间小屋（中间留门）；楼板中间那口方天井四周是通的
    g = bframe(1)
    for s in (-1, 1):
        for i, (cx, L) in enumerate([(-3.7, 3.8), (2.6, 6.0)]):
            nx.box(f"l1_隔{s}_{i}", (L, 0.35, BT_H[0]), (cx, s * 3.4, 0), parent=g, **BLD_WALL)
    # 第 3 层：一道隔墙把楼里分成两间（中间留门，方形迷宫）
    g3 = bframe(3)
    for i, (cy, L) in enumerate([(-3.15, 4.5), (3.15, 4.5)]):
        nx.box(f"l3_隔墙{i}", (0.35, L, BT_H[2]), (1.2, cy, 0), parent=g3, **BLD_WALL)

    # 第 4 层：楼忽然收进去，只剩中间一小块（露出井底与池）
    g4 = bframe(4)
    nx.box("bld4_pad", (5.0, 5.0, BLD_T), (0, 0, 0), parent=g4, **BLD_FLOOR)


def thresholds(n):
    """门前的台：从楼的墙外沿跨过那弯月牙，接到井壁的台上（不然门离台还有一截，够不着）"""
    z = zl(n) - 0.05
    yaw = byaw(n)
    half = 9.0
    for lx in (SX / 2, -SX / 2):
        rr = OFF + lx
        a = yaw if rr > 0 else yaw + 180
        r_in = abs(rr)
        if r_in >= 9.6:
            continue
        sh.tube(f"thr{n}_{'e' if lx > 0 else 'w'}", 10.05, r_in, 0.5, (0, 0, z - 0.5), segments=360,
                arc=2 * half, start=a - half, **BLD_FLOOR)


def building_content():
    level1_building()
    level2_room()
    level3_well()


def level1_building():
    """第 1 层楼里：长巷两侧各放一只这口井的模型"""
    n = 1
    for i, (lx, ly) in enumerate([(-2.6, 3.6), (-2.6, -3.6)]):
        x, y, z = bl(n, lx, ly, 0)
        nx.box(f"l1_m{i}_plinth", (0.8, 0.8, 0.5), (x, y, z - 0.01), rot=(0, 0, byaw(n) - 90),
               a="mist", b="lilac_pale", pattern="plain")
        sh.tube(f"l1_m{i}", 0.3, 0.24, 1.1, (x, y, z + 0.49), segments=18, a="lilac_pale", b="lilac", pattern="bands")
        nx.cylinder(f"l1_m{i}_lit", 0.24, 0.24, 0.02, (x, y, z + 0.50), segments=18, emit=1.0, collide=False,
                    shadow=False, a="white", b="mist", pattern="plain")
        nx.lamp(f"l1_m{i}_lamp", (x, y, z + 1.7), color=WARM, radius=4.0, power=0.7)


def level2_room():
    """第 2 层楼里一角：一间圆屋，屋里一座这口井的剖面模型，第二层那一道台上一点金（你在这里）"""
    n = 2
    cx, cy = bl(n, -3.8, 3.2, 0)[:2]
    rr, yaw = 1.8, byaw(n)
    door = yaw - 90                    # 门朝走廊（本地 −y）
    half = math.degrees((DOOR_W / 2 + 0.05) / rr)
    arcs("room2_wall", rr + 0.3, rr, BT_H[1], zl(n) - 0.03, [(door - half, door + half)], **WALLS[2])
    base = zl(n) - 0.02
    nx.cylinder("model2_plinth", 1.25, 1.25, 0.5, (cx, cy, base), segments=24, a="mist", b="lilac_pale", pattern="plain")
    top = base + 0.5
    scale = 0.1
    sh.tube("model2_wall", 1.1, 0.98, 3.1, (cx, cy, top), segments=40, arc=180, start=yaw - 90,
            a="lilac_pale", b="lilac", pattern="bands")
    nx.cylinder("model2_bottom", 0.98, 0.98, 0.04, (cx, cy, top), segments=40, emit=1.0, shadow=False,
                a="white", b="mist", pattern="plain")
    for k in range(1, NL):
        lz = top + 3.0 - LV * k * scale
        sh.tube(f"model2_ledge{k}", 0.98, 0.72, 0.05, (cx, cy, lz - 0.05), segments=40, arc=180, start=yaw - 90,
                collide=False, a="lilac", b="lilac_pale", pattern="plain")
    hx = cx + math.cos(math.radians(yaw)) * 0.85
    hy = cy + math.sin(math.radians(yaw)) * 0.85
    nx.box("model2_here", (0.12, 0.12, 0.12), (hx, hy, top + 3.0 - LV * 2 * scale), emit=1.0, collide=False,
           shadow=False, **GLOW)
    nx.lamp("model2_lamp", (cx, cy, top + 1.5), color=WARM, radius=6.0, power=0.9)


def level3_well():
    """第 3 层楼里：地上又一口小井（盖着格栅），底上一点白"""
    n = 3
    cx, cy, z = bl(n, -2.6, 2.6, 0)
    hole = 0.62
    sh.tube("l3_well_rim", hole + 0.55, hole, 0.55, (cx, cy, z), segments=32, a="lilac_pale", b="lilac", pattern="bands")
    nx.cylinder("l3_well_bottom", hole, hole, 0.06, (cx, cy, z + 0.02), segments=32, a="violet_deep", b="ink", pattern="plain")
    nx.cylinder("l3_well_light", 0.18, 0.18, 0.04, (cx, cy, z + 0.1), segments=12, emit=1.0, collide=False,
                shadow=False, a="white", b="mist", pattern="plain")
    nx.lamp("l3_lamp", (cx, cy, z + 0.9), color=WARM, radius=5.0, power=0.9, down=0.0, up=75.0, leak=0.15)
    k = fu.Kit()
    for i in range(-2, 3):
        k.box((0.12, 2 * hole + 0.35, 0.1), (i * 0.3, 0, 0.02))
    k.build("l3_grate", loc=(cx, cy, z + 0.55), rot=(0, 0, byaw(n)), smooth=0, a="lilac_pale", b="lilac", pattern="plain")


def slits():
    """第 2、3 层楼的墙上几扇亮着的窗（发光横缝）；第 4 层井壁上一圈横缝"""
    for n in (2, 3):
        for i, ly in enumerate((-3.8, -1.6, 1.6, 3.8)):
            for sgn, lx in ((-1, -SX / 2 - 0.01), (1, SX / 2 + 0.01)):
                x, y, z = bl(n, lx, ly, BT_H[n - 1] * 0.6)
                nx.box(f"win{n}_{i}_{sgn}", (0.05, 0.7, 0.16), (x, y, z), rot=(0, 0, byaw(n)), emit=1.0,
                       collide=False, shadow=False, **GLOW)
    k = fu.Kit()
    j = 0
    for a in range(0, 360, 17):
        if not free_at(4, a, 0.6):
            continue
        hz = zl(4) + 1.2 + (j * 1.7) % 4.2
        ln = 1.0 + (j * 0.37) % 1.2
        x, y, _ = polar(R - 0.015, a)
        k.box((ln, 0.04, 0.14), (x, y, hz), rot=(0, 0, a - 90))
        j += 1
    k.build("slits4", smooth=0, collide=False, shadow=False, emit=1.0, **GLOW)
    for i, a in enumerate((20, 120, 250, 320)):
        nx.lamp(f"slit_lamp{i}", polar(R - 0.6, a, zl(4) + 2.6), color=WARM, radius=3.5, power=0.5)


# ── 井口的院子 ────────────────────────────────────

OUTER = 64.0
RIM_W = 1.0
RIM_OUT = R + WT + RIM_W
SKY_C = polar(21.0, 55)[:2]


def court():
    a0 = STAIR_A[0]
    sh.tube("rim_flat", RIM_OUT, R + WT, 1.0, (0, 0, -1.0), segments=SEG, **FLOORS[0])
    sh.tube("rim_landing", R, R - STAIR_IN, 1.0, (0, 0, -1.0), segments=SEG, arc=10, start=a0 - 10, **FLOORS[0])
    arcs("parapet", R + 0.7, R, 0.45, 0.0, [(a0 - 11, a0 + 1)], a="mist", b="lilac_pale", pattern="plain")
    r = RIM_OUT
    for i in range(1, 7):
        sh.tube(f"terrace{i}", r + 1.5, r, 1.0 + RISE * i, (0, 0, -1.0), segments=SEG,
                a="mist" if i % 2 else "lilac_pale", b="lilac_pale", pattern="tiles")
        r += 1.5
    sh.tube("court_wall", r + 1.5, r, 6.0, (0, 0, -1.0), segments=SEG, a="lilac_pale", b="lilac", pattern="bands")
    nx.collider_only(sh.tube("court_fence", r + 1.5, r, 40.0, (0, 0, 5.0), segments=48))
    sh.tube("plain", OUTER, r + 1.5, 1.0, (0, 0, 4.0), segments=SEG, a="mist", b="lilac_pale", pattern="grain")


def rings():
    """头顶三只环；井里两只浮环挪到楼顶以上、井口以内的天井里（不穿楼）"""
    for i, (rr, z, tilt, spin, col) in enumerate([(9.0, 13, 14, 4, "white"), (13.0, 17, -22, -2.5, "mist"),
                                                   (14.5, 27, 18, 1.6, "pink_pale"),
                                                   (5.6, -1.5, 5, 3, "white"), (4.4, -0.6, -7, -4.5, "pink_pale")]):
        t = nx.torus(f"ring{i}", rr, 0.3 + rr * 0.015, (0, 0, z), rot=(tilt, 0, 30 * i), major_seg=128,
                     minor_seg=10, a=col, b="lilac_pale", collide=False, shadow=False)
        nx.behave(t, spin=spin)


def sky_stair():
    z0 = 1.85
    land = pf.stair_spiral("sky_stair", SKY_C, z0, 64, r_in=0.9, r_out=2.7, tread=19, start=55 - 19,
                           landing_arc=120, a="mist", b="lilac_pale", pattern="plain")
    join([o for o in bpy.data.objects if o.name.startswith("sky_stair_s")], "sky_stair_steps")
    nx.cylinder("sky_axis", 0.5, 0.5, land[2] - 0.3 - 0.6, (SKY_C[0], SKY_C[1], 0.6), segments=16,
                a="lilac", b="lilac_dark", pattern="stripes")
    nx.entrance("crystal_descent", (land[0], land[1], land[2] + 1.6), "", "")


def towers():
    rnd = random.Random(5)
    for i in range(14):
        a = 360 / 14 * i + rnd.uniform(-6, 6)
        x, y, _ = polar(rnd.uniform(34, 50), a)
        h = rnd.uniform(8, 30)
        w = rnd.uniform(1.4, 2.6)
        st = dict(a=rnd.choice(["lilac_pale", "mist", "lilac_pale", "pink_pale"]), b="lilac", pattern="bands")
        if i % 3 == 1:
            cut = h * rnd.uniform(0.45, 0.7)
            nx.box(f"tower{i}_lo", (w, w, cut), (x, y, 4.9), rot=(0, 0, a), **st)
            nx.box(f"tower{i}_hi", (w, w, h - cut), (x, y, 4.9 + cut + rnd.uniform(1.5, 3.5)), rot=(0, 0, a + 12), **st)
        else:
            nx.box(f"tower{i}", (w, w, h), (x, y, 4.9), rot=(0, 0, a), **st)


def level1():
    """井壁上的五个壁龛，各放一只这口井的模型，一只比一只深"""
    z = zl(1)
    models = [(0.3, 1.0), (0.55, 1.05), (0.8, 1.1), (1.05, 1.15), (1.3, 1.4)]
    for i, (a, w) in enumerate(BAYS[1]):
        h, rim = models[i]
        name = f"niche{i}"
        bay(name, a, z, w, 1.6, True, FLOORS[1])
        r = math.radians(a)
        px, py = math.cos(r) * (R + 0.95), math.sin(r) * (R + 0.95)
        base = z - 0.01
        nx.box(f"{name}_plinth", (0.9, 0.9, rim - h), (px, py, base), rot=(0, 0, a - 90),
               a="mist", b="lilac_pale", pattern="plain")
        top = base + rim - h
        sh.tube(f"{name}_model", 0.36, 0.28, h, (px, py, top), segments=20, a="lilac_pale", b="lilac", pattern="bands")
        nx.cylinder(f"{name}_bottom", 0.28, 0.28, 0.02, (px, py, top + 0.005), segments=20, emit=1.0, collide=False,
                    shadow=False, a="white", b="mist", pattern="plain")
        nx.lamp(f"{name}_lamp", (px, py, base + rim + 0.3), color=WARM, radius=3.2, power=0.8)


POOL_R = 7.0


def bottom():
    z = zl(NL)
    arcs("floor_out", R + 0.02, R - LEDGE_W, 1.0, z - 1.0, [landing_range(NL)], **FLOORS[NL])
    sh.tube("floor_in", R - LEDGE_W, POOL_R, 1.0, (0, 0, z - 1.0), segments=SEG, **FLOORS[NL])
    for i, (ro, ri) in enumerate([(POOL_R, 6.0), (6.0, 5.0)]):
        sh.tube(f"pool_step{i}", ro, ri, 1.0, (0, 0, z - 1.0 - RISE * (i + 1)), segments=SEG, **FLOORS[NL])
    deep = z - RISE * 3
    nx.cylinder("pool_floor", 5.0, 5.0, 1.0, (0, 0, deep - 1.0), segments=SEG, a="mist", b="blue_pale", pattern="tiles")
    wz = z - 0.45
    nx.cylinder("pool", POOL_R - 0.02, POOL_R - 0.02, 0.04, (0, 0, wz - 0.04), segments=96, collide=False,
                shadow=False, ramp=("blue", "blue_pale", "white"), pattern="bands")
    sh.tube("mirror_rim", 2.0, 1.6, 0.03, (0, 0, wz + 0.005), segments=48, collide=False, shadow=False,
            a="lilac", b="lilac_dark", pattern="plain")
    nx.cylinder("mirror_sky", 1.6, 1.6, 0.04, (0, 0, wz + 0.005), segments=48, collide=False, shadow=False, emit=1.0,
                a="blue_pale", b="white", pattern="plain")
    nx.portal("portal_home", (0, 0, deep + 0.9), "house", at="descent", mode="walk", radius=1.1)


def build(extent=EXTENT):
    nx.into("env")
    e, az = math.radians(80), math.radians(225)
    nx.sun((math.cos(e) * math.cos(az), math.cos(e) * math.sin(az), math.sin(e)))
    nx.atmosphere("lattice", grid=3, grid_lit=1, lamps=True)

    nx.into("court")
    court()
    nx.into("rings")
    rings()
    nx.into("well")
    well()
    nx.into("building")
    building()
    nx.into("content")
    level1()
    building_content()
    slits()
    nx.into("sky_stair")
    sky_stair()
    nx.into("towers")
    towers()
    nx.into("bottom")
    bottom()

    sx, sy, _ = polar(RIM_OUT + 0.4, 270)
    nx.spawn((sx, sy, 0.3), facing_deg=0)
    nx.arrive("house", (sx, sy, 0.3), facing_deg=0)


if __name__ == "__main__":
    nx.reset()
    build()
    nx.save_blend("descent-var-2")
    nx.export("descent-var-2")
