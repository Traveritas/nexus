"""浅梦 · 下沉 · 年轮（descent-var-1）：井壁往里，一层层长出环形巷子——像树的年轮。

底本是第三轮的 descent.py（见 mockup/shallows-04/README.md 的「下沉 · 井」）。
这一版把「井心空洞」做成一年一圈：每往下走一层，台环就往井心多长出一圈，
井心的空洞一层比一层小（r 10 → 8.5 → 7 → 5.5，井底仍是 r 7 的池）。
从上往下看是几圈错着开口的环，套着一个越来越小的洞，洞里透出下一层的暖光。
人从井壁的梯下来，落在贴着井壁的那圈台上（外圈）；要进更里面的一圈（内圈），
得从圈墙上的一处门进去；再绕到另一处门才回到外圈、找到往下的梯——每层都要这么绕一次。

修掉的（第三轮的量过）：
- 楼梯每级顶面 = z − RISE·(k+1)，级数 20（20×0.3 = 6.0 正好一层）；上行下行都走得通。
- 梯带与台同宽（STAIR_IN = LEDGE_W），不再留那道 0.4m 的槽。
- 台面缺口、圈墙的门、隔墙、捷径、桥、横缝的剔除区全部由 SPAN / STAIR_A 派生，没有手算常数。
- 井口那片平白（rim_flat）收窄，台阶从更近处开始。
- 井里那两只浮环缩进天井里，不穿墙。

运行：node scripts/blender.cjs build descent-var-1，网页 ?world=descent-var-1
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

R = 13.0          # 井壁内半径
WT = 1.2          # 井壁厚
LV = 6.0          # 层高
NL = 5            # 井底是第 5 层（−30m）
LEDGE_W = 3.0     # 贴着井壁那一圈台的宽
LEDGE_T = 0.8     # 台厚
SEG = 128

STAIR_IN = LEDGE_W          # 梯带与台同宽
STEPS = 20                  # 20 × 0.3 = 6.0，正好一层
RISE = 0.3
TREAD = math.degrees(0.85 / (R - STAIR_IN / 2))   # 每级占的角度（中线上 0.85m）
SPAN = TREAD * STEPS        # 每段梯占的角度

# 每段梯的起点方位（度）：下一段在上一段落脚处再往前 140°，每层绕半圈
STAIR_A = [200.0]
for _ in range(NL - 1):
    STAIR_A.append((STAIR_A[-1] + SPAN + 140.0) % 360)

# 井心空洞的半径：逐层收小（井底是 r 7 的池）
VOID = [13.0, 10.0, 8.5, 7.0, 5.5, 7.0]

WALL_T = 0.4      # 圈墙 / 隔墙厚

BAY_H = 3.0       # 洞口高
BAND = 3.2        # 井壁开洞的那一圈带子高（洞的顶板压过它）

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
    """一圈环，在 gaps（[(起, 止) 度]）处断开"""
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
    """半径 r 上、角度 a 处、弧长 w 的一段，占多少度"""
    return math.degrees(w / r)


# ── 派生的角度：梯口、落脚口、隔墙、门 ───────────────────

def stair_range(n):
    """第 n 层往下的梯，占这一层台面的角度"""
    return (STAIR_A[n], STAIR_A[n] + SPAN)


def landing_range(n):
    """上一层的梯落在第 n 层台面上的那一段（末级），台面在这里也要让开"""
    a = STAIR_A[n - 1] + SPAN - TREAD
    return (a, a + TREAD)


def ledge_gaps(n):
    return [stair_range(n), landing_range(n)]


def radial_walls(n):
    """外圈台面上的隔墙（两段弧的中点）：把「落脚的一段」与「往下的梯那一段」隔开，
    逼人从圈墙的门进内圈、绕过去再回来。第 1 层没有内圈，不设隔墙。"""
    if n < 2:
        return []
    L = norm(STAIR_A[n - 1] + SPAN)     # 落脚方位
    S = norm(STAIR_A[n])                # 往下的梯口方位
    d1 = norm(S - L)
    return [norm(L + d1 / 2), norm(S + (360 - d1) / 2)]


def in_arc(a, lo, hi):
    a, lo, hi = norm(a), norm(lo), norm(hi)
    if hi < lo:
        hi += 360
    if a < lo:
        a += 360
    return lo <= a <= hi


def free_at(n, deg, w=0.0):
    """第 n 层台面上，方位 deg（±w 米）是不是空着（不在梯口、落脚口、隔墙上）"""
    da = arc_span(deg, w / 2, (R + VOID[n]) / 2) + 1.0
    for lo, hi in ledge_gaps(n):
        if in_arc(deg, lo - da, hi + da):
            return False
    for wa in radial_walls(n):
        if abs(((deg - wa + 180) % 360) - 180) < da + arc_span(deg, WALL_T, R) + 1.0:
            return False
    return True


def solid_arcs(n):
    """第 n 层外圈台面剩下的实心弧（梯口、落脚口、隔墙都算断口）"""
    gaps = list(ledge_gaps(n))
    for wa in radial_walls(n):
        gaps.append((wa - 0.8, wa + 0.8))
    gaps = sorted((norm(lo), norm(lo) + (hi - lo)) for lo, hi in gaps)
    out = []
    for i, (_, a1) in enumerate(gaps):
        b0 = gaps[(i + 1) % len(gaps)][0] + (360 if i == len(gaps) - 1 else 0)
        if b0 - a1 > 2.0:
            out.append((a1, b0))
    return out


def door_angles(n):
    """第 n 层圈墙上的门：开在每一段实心弧的中点"""
    return [norm((lo + hi) / 2) for lo, hi in solid_arcs(n)]


# ── 井壁上的洞：壁龛、长洞 ───────────────────────────

# 第 1 层的壁龛与长洞（方位按新的台面缺口挑，都在实心弧里）
NICHE_A = [160.0, 190.0, 220.0, 250.0, 300.0]
LONGHOLE_A = 30.0


def bay(name, a, z, w, d, back, style, floor_hole=None):
    """井壁上的一个洞：地、两侧、顶（和后墙）。本地 +Y 沿半径朝外，原点在井壁内面"""
    k = fu.Kit()
    fw = w + 1.2
    if floor_hole:
        y0, s = floor_hole
        k.box((fw, y0 - s / 2, 0.4), (0, (y0 - s / 2) / 2, z - 0.41))
        k.box((fw, d - y0 - s / 2, 0.4), (0, (d + y0 + s / 2) / 2, z - 0.41))
        side = (fw - s) / 2
        for sx in (-1, 1):
            k.box((side, s, 0.4), (sx * (s / 2 + side / 2), y0, z - 0.41))
    else:
        k.box((fw, d, 0.4), (0, d / 2, z - 0.41))
    for sx in (-1, 1):
        k.box((0.5, d, BAY_H + 0.4), (sx * (w / 2 + 0.25), d / 2, z - 0.01))
    k.box((fw, d, 0.4), (0, d / 2, z + BAY_H))
    if back:
        k.box((fw, 0.6, BAY_H + 0.82), (0, d + 0.3, z - 0.41))
    x, y, _ = polar(R, a)
    return k.build(f"bay_{name}", loc=(x, y, 0), rot=(0, 0, a - 90), smooth=0, **style)


def local(a, along, side=0.0, z=0.0):
    """洞里的本地坐标 → 世界：along 沿半径从井壁内面往外，side 沿切向"""
    r = math.radians(a)
    return (math.cos(r) * (R + along) - math.sin(r) * side, math.sin(r) * (R + along) + math.cos(r) * side, z)


def bay_gaps(n):
    """第 n 层井壁上开洞的角度（用于井壁带子的断开）"""
    out = []
    if n == 1:
        out = [gap_of(a, 2.4) for a in NICHE_A] + [gap_of(LONGHOLE_A, 2.4)]
    return out


# ── 井 ────────────────────────────────────────────

def well():
    """井壁 + 每层的台与内圈地 + 圈墙、隔墙 + 梯"""
    # 井壁：每层开洞的那一圈带子 + 上面一整圈
    for n in range(1, NL + 1):
        z = zl(n)
        st = WALLS[n]
        gaps = bay_gaps(n)
        arcs(f"wall{n}_band", R + WT, R, BAND + 0.41, z - 0.41, gaps, **st)
        top = zl(n - 1) - 0.41 if n > 1 else 0.0
        sh.tube(f"wall{n}_solid", R + WT, R, top - (z + BAND), (0, 0, z + BAND), segments=SEG, **st)
    sh.tube("wall_foot", R + WT, R, 1.0, (0, 0, zl(NL) - 1.41), segments=SEG, **WALLS[NL])

    for n in range(1, NL):
        level_floor(n)
        level_walls(n)
    # 井底那层的地在 bottom() 里

    stairs()


def level_floor(n):
    """第 n 层的台面：外圈（贴壁的 3m 台，梯口与落脚口断开）+ 内圈地（到井心空洞边）"""
    z = zl(n)
    st = FLOORS[n]
    arcs(f"ledge{n}", R, R - LEDGE_W, LEDGE_T, z - LEDGE_T, ledge_gaps(n), **st)
    ri = R - LEDGE_W
    if VOID[n] < ri - 0.001:
        sh.tube(f"floor{n}_in", ri, VOID[n], LEDGE_T, (0, 0, z - LEDGE_T), segments=SEG, **st)


def level_walls(n):
    """第 n 层：圈墙（在内圈与外圈之间，门开在实心弧的中点）+ 外圈上的两道隔墙"""
    z = zl(n)
    # 圈墙：半径 = 上一层台面的内沿（= VOID[n-1]），从这层的地顶到上一层的地底（第 1 层没有顶，不设）
    rw = VOID[n - 1]
    if n >= 2 and rw > VOID[n] + 0.5:
        doors = [gap_of(a, 1.4, rw) for a in door_angles(n)]
        arcs(f"ringwall{n}", rw + WALL_T / 2, rw - WALL_T / 2, LV - LEDGE_T, z, doors, **WALLS[n])
    # 隔墙：外圈台面上，从圈墙到井壁
    for i, wa in enumerate(radial_walls(n)):
        r_in = max(VOID[n - 1], VOID[n])
        x, y, _ = polar((r_in + R) / 2, wa)
        nx.box(f"spoke{n}_{i}", (R - r_in, WALL_T, LV - LEDGE_T), (x, y, z),
               rot=(0, 0, wa), **WALLS[n])


def stairs():
    """梯：一级级悬空的弧板，贴着井壁；每级顶面 = z − RISE·(k+1)（第 0 级比台面低 0.3，末级顶面 = 下一层台面）"""
    for n in range(NL):
        a0, z = STAIR_A[n], zl(n)
        st = FLOORS[n + 1] if n + 1 < NL else FLOORS[NL - 1]
        steps = [sh.tube(f"stair{n}_{k:02d}", R, R - STAIR_IN, RISE, (0, 0, z - RISE * (k + 2)), segments=SEG,
                         arc=TREAD, start=a0 + TREAD * k, **st) for k in range(STEPS)]
        join(steps, f"stair{n}")


# ── 井口的院子 ────────────────────────────────────

OUTER = 64.0
RIM_W = 1.0            # 井沿那一圈平地的宽（收窄）
RIM_OUT = R + WT + RIM_W   # 台阶从这里开始
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
    """头顶慢慢转的三只环；井里两只浮环缩进天井里（不穿墙不穿楼）"""
    for i, (rr, z, tilt, spin, col) in enumerate([(9.0, 13, 14, 4, "white"), (13.0, 17, -22, -2.5, "mist"),
                                                   (14.5, 27, 18, 1.6, "pink_pale"),
                                                   (6.0, -9.0, 6, 3, "white"), (4.0, -21.0, -8, -4.5, "pink_pale")]):
        t = nx.torus(f"ring{i}", rr, 0.3 + rr * 0.015, (0, 0, z), rot=(tilt, 0, 30 * i), major_seg=128,
                     minor_seg=10, a=col, b="lilac_pale", collide=False, shadow=False)
        nx.behave(t, spin=spin)


def sky_stair():
    """院子一角一道螺旋梯，一圈圈升进天里，顶上一枚晶体"""
    z0 = 1.85   # 梯脚压在最高的那圈台阶（terrace6 顶 1.8）上面一点
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


# ── 各层的内容 ────────────────────────────────────

def level1():
    """外圈（贴壁的台）：五个壁龛各放一只这口井的模型；一条长洞，尽头地上方口掉进第二层的圆屋。
    外圈的两段实心弧里各放一间小屋（一只井的模型 + 一盏灯）"""
    z = zl(1)
    models = [(0.3, 1.0), (0.55, 1.05), (0.8, 1.1), (1.05, 1.15), (1.3, 1.4)]
    for a, (h, rim) in zip(NICHE_A, models):
        name = f"niche{NICHE_A.index(a)}"
        bay(name, a, z, 2.4, 1.6, True, FLOORS[1])
        px, py, _ = local(a, 0.95)
        base = z - 0.01
        nx.box(f"{name}_plinth", (0.9, 0.9, rim - h), (px, py, base), rot=(0, 0, a - 90),
               a="mist", b="lilac_pale", pattern="plain")
        top = base + rim - h
        sh.tube(f"{name}_model", 0.36, 0.28, h, (px, py, top), segments=20, a="lilac_pale", b="lilac", pattern="bands")
        nx.cylinder(f"{name}_bottom", 0.28, 0.28, 0.02, (px, py, top + 0.005), segments=20, emit=1.0, collide=False,
                    shadow=False, a="white", b="mist", pattern="plain")
        nx.lamp(f"{name}_lamp", (px, py, base + rim + 0.3), color=WARM, radius=3.2, power=0.8)

    a = LONGHOLE_A
    bay("longhole", a, z, 2.4, 11.0, True, FLOORS[1], floor_hole=(9.0, 1.6))
    ex, ey, _ = local(a, 11.0 - 0.02)
    nx.box("longhole_glow", (0.5, 0.04, 0.5), (ex, ey, z + 1.4), rot=(0, 0, a - 90), emit=1.0, collide=False,
           shadow=False, **GLOW)
    gx, gy, _ = local(a, 11.0 - 0.8)
    nx.lamp("longhole_lamp", (gx, gy, z + 1.4), color=WARM, radius=5.0, power=0.7)

    # 两间小屋：外圈的两段实心弧里各放一只小井的模型（灯在模型上）
    arcs1 = solid_arcs(1)
    for i, (lo, hi) in enumerate(arcs1[:2]):
        a = norm((lo + hi) / 2)
        r = R - LEDGE_W - 1.1
        x, y, _ = polar(r, a)
        nx.box(f"l1_room{i}_plinth", (0.8, 0.8, 0.5), (x, y, z - 0.01), rot=(0, 0, a - 90),
               a="mist", b="lilac_pale", pattern="plain")
        sh.tube(f"l1_room{i}_model", 0.3, 0.24, 1.0, (x, y, z + 0.49), segments=18,
                a="lilac_pale", b="lilac", pattern="bands")
        nx.cylinder(f"l1_room{i}_lit", 0.24, 0.24, 0.02, (x, y, z + 0.50), segments=18, emit=1.0, collide=False,
                    shadow=False, a="white", b="mist", pattern="plain")
        nx.lamp(f"l1_room{i}_lamp", (x, y, z + 1.6), color=WARM, radius=4.0, power=0.7)


def room_ring(name, c, r_out, r_in, h, z, gaps, **style):
    gaps = sorted(((a0 % 360), (a0 % 360) + (a1 - a0)) for a0, a1 in gaps)
    if not gaps:
        sh.tube(name, r_out, r_in, h, (c[0], c[1], z), segments=48, **style)
        return
    for i, (a0, a1) in enumerate(gaps):
        b0 = gaps[(i + 1) % len(gaps)][0] + (360 if i == len(gaps) - 1 else 0)
        sh.tube(f"{name}_{i}", r_out, r_in, h, (c[0], c[1], z), segments=48, arc=b0 - a1, start=a1, **style)


def chamber(name, a, z, dist, r, h, w, floor_style, wall_style, hole=0.0):
    c = polar(dist, a)
    door = a + 180
    half = math.degrees((w / 2 + 0.05) / r)
    room_ring(f"{name}_band", c, r + 0.6, r, BAND + 0.45, z - 0.45, [(door - half, door + half)], **wall_style)
    room_ring(f"{name}_upper", c, r + 0.6, r, h - BAND, z + BAND, [], **wall_style)
    nx.cylinder(f"{name}_floor", r + 0.3, r + 0.3, 0.4, (c[0], c[1], z - 0.42), segments=48, **floor_style)
    if hole:
        sh.tube(f"{name}_ceiling", r + 0.6, hole, 0.4, (c[0], c[1], z + h), segments=48, **wall_style)
    else:
        nx.cylinder(f"{name}_ceiling", r + 0.6, r + 0.6, 0.4, (c[0], c[1], z + h), segments=48, **wall_style)
    return c


def level2():
    """长洞的方口掉进这间圆屋；屋里一座井的剖面模型，第二层那一道台上一点金（你在这里）"""
    z = zl(2)
    a = LONGHOLE_A
    # 井壁上的横洞（从井壁通到圆屋）
    bay("to_room", a, z, 2.6, 4.6, False, FLOORS[2])
    c = chamber("room2", a, z, 22.0, 5.0, 5.0, 2.6, FLOORS[2], WALLS[2], hole=1.0)
    r = math.radians(a)
    tx, ty = -math.sin(r), math.cos(r)
    mx, my = c[0] + tx * 2.6, c[1] + ty * 2.6
    base = z - 0.02
    nx.cylinder("model2_plinth", 1.7, 1.7, 0.5, (mx, my, base), segments=24, a="mist", b="lilac_pale", pattern="plain")
    top = base + 0.5
    scale = 0.1
    sh.tube("model2_wall", 1.45, 1.3, 3.0 + 0.1, (mx, my, top), segments=40, arc=180, start=a - 90,
            a="lilac_pale", b="lilac", pattern="bands")
    nx.cylinder("model2_bottom", 1.3, 1.3, 0.04, (mx, my, top), segments=40, emit=1.0, shadow=False,
                a="white", b="mist", pattern="plain")
    for n in range(1, NL):
        lz = top + 3.0 - LV * n * scale
        sh.tube(f"model2_ledge{n}", 1.3, 1.0, 0.05, (mx, my, lz - 0.05), segments=40, arc=180, start=a - 90,
                collide=False, a="lilac", b="lilac_pale", pattern="plain")
    gx, gy = mx + math.cos(r) * 1.15, my + math.sin(r) * 1.15
    nx.box("model2_here", (0.14, 0.14, 0.14), (gx, gy, top + 3.0 - LV * 2 * scale), emit=1.0, collide=False,
           shadow=False, **GLOW)
    nx.lamp("model2_lamp", (mx, my, top + 1.6), color=WARM, radius=7.0, power=0.9)


def level3():
    """外圈的一段弧里又是一口小井（盖着格栅，井圈矮矮地立在地上，底上一点白）；
    另外两段弧里各放一盏灯与一只落下的东西"""
    z = zl(3)
    arcs3 = solid_arcs(3)
    # 小井：外圈的一段实心弧里，一只矮井圈 + 格栅（井筒在井圈里面）
    a = norm((arcs3[0][0] + arcs3[0][1]) / 2)
    r = R - LEDGE_W / 2
    cx, cy = polar(r, a)[:2]
    hole = 0.62
    sh.tube("l3_well_rim", hole + 0.55, hole, 0.55, (cx, cy, z), segments=32, a="lilac_pale", b="lilac", pattern="bands")
    nx.cylinder("l3_well_bottom", hole, hole, 0.06, (cx, cy, z + 0.02), segments=32, a="violet_deep", b="ink", pattern="plain")
    nx.cylinder("l3_well_light", 0.18, 0.18, 0.04, (cx, cy, z + 0.1), segments=12, emit=1.0, collide=False,
                shadow=False, a="white", b="mist", pattern="plain")
    nx.lamp("l3_lamp", (cx, cy, z + 0.9), color=WARM, radius=5.0, power=0.9, down=0.0, up=75.0, leak=0.15)
    # 格栅：一排横条，缝比人窄
    k = fu.Kit()
    for i in range(-2, 3):
        k.box((0.12, 2 * hole + 0.35, 0.1), (i * 0.3, 0, 0.02))
    k.build("l3_grate", loc=(cx, cy, z + 0.55), rot=(0, 0, a), smooth=0, a="lilac_pale", b="lilac", pattern="plain")

    # 另外两段弧：一盏灯、一只落下的东西
    for i, (lo, hi) in enumerate(arcs3[1:3]):
        aa = norm((lo + hi) / 2)
        x, y, _ = polar(R - LEDGE_W - 1.1, aa)
        nx.box(f"l3_room{i}_crate", (0.7, 0.7, 0.55), (x, y, z - 0.01), rot=(0, 0, aa - 90),
               a="rose", b="rose_deep", pattern="bands")
        nx.lamp(f"l3_room{i}_lamp", (x, y, z + 2.0), color=WARM, radius=4.0, power=0.6)


def level4():
    """最暗的一层：圈墙与井壁上一道道发亮的横缝；一座偏开井心 3m 的桥横过空洞"""
    z = zl(4)
    # 横缝：贴在井壁内面与圈墙外面上，避开梯口与落脚口
    k = fu.Kit()
    i = 0
    for a in range(0, 360, 17):
        if not free_at(4, a, 0.6):
            continue
        hz = z + 1.2 + (i * 1.7) % 4.2
        ln = 1.0 + (i * 0.37) % 1.2
        x, y, _ = polar(R - 0.015, a)
        k.box((ln, 0.04, 0.14), (x, y, hz), rot=(0, 0, a - 90))
        i += 1
    k.build("slits", smooth=0, collide=False, shadow=False, emit=1.0, **GLOW)
    # 圈墙外面也来几道（内圈的墙）
    k2 = fu.Kit()
    rw = VOID[3]
    for j, a in enumerate(range(0, 360, 26)):
        hz = z + 1.4 + (j * 1.1) % 3.8
        x, y, _ = polar(rw - WALL_T / 2 - 0.015, a)
        k2.box((1.0, 0.04, 0.14), (x, y, hz), rot=(0, 0, a - 90))
    k2.build("slits_in", smooth=0, collide=False, shadow=False, emit=1.0, **GLOW)
    # 桥：偏开井心 3m 的一道弦，架在空洞上（两头搭在内圈地上）
    ba = norm((solid_arcs(4)[0][0] + solid_arcs(4)[0][1]) / 2)
    off = -3.0
    half = math.sqrt(max(0.1, VOID[4] ** 2 - off ** 2)) + 0.8
    L = 2 * half
    r = math.radians(ba)
    nx.box("bridge", (2.2, L, 0.5), (math.cos(r + math.pi / 2) * off, math.sin(r + math.pi / 2) * off, z - 0.35),
           rot=(0, 0, ba - 90), **FLOORS[4])
    for i, a in enumerate(door_angles(4)):
        nx.lamp(f"slit_lamp{i}", polar(VOID[4] + 0.8, a, z + 2.6), color=WARM, radius=3.5, power=0.5)


POOL_R = 7.0


def bottom():
    """井底：白的；三圈台阶落进一汪浅水，水里映着井口那一圈天光（走进去回家）"""
    z = zl(NL)
    # 地：外圈（贴壁，让开末级梯的落脚口）+ 内圈
    arcs("floor_out", R + 0.02, R - LEDGE_W, 1.0, z - 1.0, [landing_range(NL)], **FLOORS[NL])
    sh.tube("floor_in", R - LEDGE_W, POOL_R, 1.0, (0, 0, z - 1.0), segments=SEG, **FLOORS[NL])
    rings = [(POOL_R, 6.0), (6.0, 5.0)]
    for i, (ro, ri) in enumerate(rings):
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
    nx.into("sky_stair")
    sky_stair()
    nx.into("towers")
    towers()
    nx.into("level1")
    level1()
    nx.into("level2")
    level2()
    nx.into("level3")
    level3()
    nx.into("level4")
    level4()
    nx.into("bottom")
    bottom()

    sx, sy, _ = polar(RIM_OUT + 0.4, 270)
    nx.spawn((sx, sy, 0.3), facing_deg=0)
    nx.arrive("house", (sx, sy, 0.3), facing_deg=0)


if __name__ == "__main__":
    nx.reset()
    build()
    nx.save_blend("descent-var-1")
    nx.export("descent-var-1")
