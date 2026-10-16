"""浅梦 · 断梯（stair）：一座被炸开的螺旋楼梯——从一页摊开的纸上起来，绕着中心盘两圈往上。

这一版把「断梯」拆成两个世界：`stair`（下半，纸上那半）与 `stair_b`（上半，越往上踏步越大那半）。
中间靠一道**缝**（`nx.seam`，见 src/seam.ts）接上——缝只能接两个不同的世界；门洞两边的东西一模一样，
走过去不转场；回头能透过门洞看见自己刚爬过的那一跑，位置和角度都错开（「楼梯穿过自己」）。
上半那座继续往上，最后几级比人还高（要跳上去），旁边并排浮着一座只到脚踝的迷你楼梯，一直通到很远。

- 回家：从纸上或虚空里掉下去，脚底到 −14m（atmosphere 的 fall_to），落回家里书桌前（到达点 `stair`）。
- 顶上去「高处」：最后一级上方 `portal_heights`（暂指云阶 `isles`）。
- 晶体：一枚，在上半那座的一条岔路尽头（站点先空着）。
- 中心：原来是吊着的大锤，去掉；换成一摞错开、转开的圆板（炸开的柱心），从纸上立起来。

运行：node scripts/blender.cjs build stair（再 build stair_b），网页 ?world=stair / ?world=stair_b
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import furniture as fu  # noqa: E402
import nx  # noqa: E402
import prefabs as pf  # noqa: E402

EXTENT = 170
CENTER = (0, 0)

RISE = 0.30       # 普通踏步每级高（自动迈得上去 ≤ 0.35）
RUN = 0.80        # 普通踏步每级进深
W = 2.7           # 楼梯宽
TH = 0.34         # 踏步板厚（薄板浮着，底下另有一道梯梁）

# ── 门（缝）：两个世界共用这一份 ──
DOOR_W, DOOR_H = 1.34, 2.30
FRAME_DEPTH, FRAME_T = 0.30, 0.13
SEAM_OFF = FRAME_DEPTH / 2 + 0.012
BLOCK_OFF = 0.45
DOOR_AT = 2.0             # 门洞底边中点离平台近边 2m
LAND_ARC = 16.0           # 这道弦平台跨过多少度弧（短：门后立刻是刚爬过的那一跑）

PAGE = dict(a="white", b="mist", pattern="bands")
GUTTER = dict(a="lilac_pale", b="mist", pattern="plain")
STEP = [dict(ramp=("violet_deep", "violet", "lilac_dark"), top="lilac_pale", pattern="plain"),
        dict(ramp=("violet_deep", "violet", "lilac_dark"), top="pink_pale", pattern="plain"),
        dict(ramp=("violet", "lilac_dark", "lilac"), top="mist", pattern="plain")]
SLAB = dict(ramp=("lilac_dark", "lilac", "lilac_pale"), top="mist", pattern="tiles")
RAIL = dict(a="ink", b="violet_deep", pattern="plain")
STRINGER = dict(a="violet_deep", b="violet", pattern="bands")
POST = dict(a="rose_deep", b="rose", pattern="plain")
FAR = dict(ramp=("violet", "lilac_dark", "lilac"), pattern="plain")
CORE = dict(ramp=("violet", "lilac_dark", "lilac"), pattern="bands")
MINI = dict(ramp=("lilac_dark", "lilac", "lilac_pale"), pattern="plain")
GLOW = dict(a="white", b="gold", pattern="plain", emit=1.0)

# 下半：纸上那一圈
LO_ANG0 = -90.0
LO_R = 5.6
LO_SEGS = [(38, RISE, RUN)]          # 38 级 → 11.4m

CORE_TOP = 42.0


def fwd(yaw):
    a = math.radians(yaw)
    return (-math.sin(a), math.cos(a))


def dir_rot(d):
    """把本地 +Z 转到方向 d 的欧拉角（度，同 nx 的 XYZ）"""
    L = math.sqrt(d[0] * d[0] + d[1] * d[1] + d[2] * d[2]) or 1.0
    p = math.degrees(math.acos(max(-1.0, min(1.0, d[2] / L))))
    th = math.degrees(math.atan2(d[0], -d[1]))
    return (p, 0.0, th)


def beam_kit(k, p0, p1, t):
    """从 p0 到 p1 的一根方料（截面 t 见方）"""
    d = tuple(p1[i] - p0[i] for i in range(3))
    L = math.sqrt(sum(v * v for v in d)) or 0.001
    k.box((t, t, L), p0, dir_rot(d))


# ── 楼梯几何（斜跑、碎段） ───────────────────────

def flight_geo(n, rise=RISE, run=RUN, w=W, t=0.45, flat=False, dz=0.0):
    """一跑直梯：本地 +Y 往上走，原点在第一级前沿的底下。侧面是锯齿，底下是一道斜面"""
    prof = [(0.0, -t)]
    for i in range(n):
        prof += [(i * run, (i + 1) * rise), ((i + 1) * run, (i + 1) * rise)]
    prof += [(n * run, -t if flat else n * rise - t - rise)]
    prof = [(y, z + dz) for y, z in prof]
    m = len(prof)
    verts = [(-w / 2, y, z) for y, z in prof] + [(w / 2, y, z) for y, z in prof]
    faces = [tuple(range(m - 1, -1, -1)), tuple(range(m, 2 * m))]
    for i in range(m):
        j = (i + 1) % m
        faces.append((i, j, m + j, m + i))
    return verts, faces


def flight_kit(n, rise=RISE, run=RUN, w=W, t=0.45, kit=None, flat=False, dz=0.0):
    verts, faces = flight_geo(n, rise, run, w, t, flat, dz)
    k = kit or fu.Kit()
    return k._add(verts, faces)


def chunk_kit(n, span, w, t=0.34, step_rise=0.26, flip=False, kit=None):
    """一截「碎下来的踏步」：本地 +Y 往前，近端落脚边在 z=0。flip 时倒过来（平的底面翻上来当路）"""
    run = span / n
    verts, faces = flight_geo(n, step_rise, run, w, t, flat=flip)
    if flip:
        verts = [(x, -y, -z) for x, y, z in verts]
    k = kit or fu.Kit()
    return k._add(verts, faces)


# ── 螺旋 ─────────────────────────────────────────

def helix_chain(cx, cy, ang0, r0, z0, segs, dr=0.0, turn=1.0):
    """绕 (cx, cy) 从 ang0（度）、半径 r0、z0 起，按 segs=[(n, rise, run), …] 一级级往上。
    返回 (steps, runs, ang_end, r_end, z_end)；steps 是每级的 (x, y, z_top, yaw)"""
    steps, runs = [], []
    ang = math.radians(ang0)
    r, z = r0, z0
    for (n, rise, run) in segs:
        for _ in range(n):
            ang += turn * run / max(r, 0.4)
            r += dr
            z += rise
            x = cx + math.cos(ang) * r
            y = cy + math.sin(ang) * r
            yaw = math.degrees(ang) + (0.0 if turn > 0 else 180.0)
            steps.append((x, y, z, yaw))
            runs.append(run)
    return steps, runs, math.degrees(ang), r, z


def build_helix(name, steps, runs, w=W, widths=None, th=TH, skip=(), group=4, seed=0, rail=True, stringer=True, dry=False):
    """把螺旋的踏步搭出来：每 group 级合成一块、各自偏开一点（炸开的样子）；skip={起始级号: 不搭几级} 是断口。
    返回 jumps 列表 [(起跳 x, y, z, yaw, 距离, 高差)]"""
    jumps = []
    for i, cnt in sorted(skip.items()):
        if i - 1 < 0 or i + cnt >= len(steps):
            continue
        x0, y0, z0, yaw0 = steps[i - 1]
        x1, y1, z1, _ = steps[i + cnt]
        jumps.append((x0, y0, z0, yaw0, math.hypot(x1 - x0, y1 - y0), z1 - z0))
    if dry:
        return jumps
    gone = set()
    for i, cnt in skip.items():
        gone |= set(range(i, i + cnt))
    groups = {}
    for i in range(len(steps)):
        if i in gone:
            continue
        groups.setdefault(i // group, []).append(i)
    rnd = random.Random(seed)
    for gi, idxs in sorted(groups.items()):
        k = fu.Kit()
        for i in idxs:
            x, y, z, yaw = steps[i]
            wi = widths[i] if widths else w
            k.box((wi, runs[i] * 1.22, th), (x, y, z - th), (0, 0, yaw))
        ox, oy, oz = rnd.uniform(-0.22, 0.22), rnd.uniform(-0.22, 0.22), rnd.uniform(-0.04, 0.04)
        k.build(f"{name}_{gi:02d}", loc=(ox, oy, oz), rot=(0, 0, 0), smooth=0, **STEP[gi % 3])
    if rail:
        k = fu.Kit()
        rr = []
        for i in range(len(steps)):
            x, y, z, yaw = steps[i]
            L = math.hypot(x, y) or 1.0
            wi = widths[i] if widths else w
            rr.append((x + x / L * (wi / 2 + 0.20), y + y / L * (wi / 2 + 0.20), z + 1.02))
        for i in range(len(steps) - 1):
            if i in gone or i + 1 in gone or rnd.random() < 0.12:
                continue
            beam_kit(k, rr[i], rr[i + 1], 0.11)
        for i in range(0, len(steps), 3):
            if i in gone:
                continue
            x, y, z, yaw = steps[i]
            L = math.hypot(x, y) or 1.0
            wi = widths[i] if widths else w
            k.box((0.09, 0.09, 1.0), (x + x / L * (wi / 2 + 0.20), y + y / L * (wi / 2 + 0.20), z + 0.02))
        k.build(f"{name}_rail", loc=(rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5), rnd.uniform(-0.1, 0.35)),
                rot=(0, 0, 0), smooth=0, collide=False, **RAIL)
    if stringer:
        k = fu.Kit()
        rr = []
        for i in range(len(steps)):
            x, y, z, yaw = steps[i]
            L = math.hypot(x, y) or 1.0
            wi = widths[i] if widths else w
            rr.append((x + x / L * (wi / 2 + 0.34), y + y / L * (wi / 2 + 0.34), z - 0.30))
        for i in range(len(steps) - 1):
            if i in gone or i + 1 in gone:
                continue
            beam_kit(k, rr[i], rr[i + 1], 0.24)
        k.build(f"{name}_stringer", loc=(rnd.uniform(-0.4, 0.4), rnd.uniform(-0.4, 0.4), -0.1),
                rot=(0, 0, 0), smooth=0, collide=False, **STRINGER)
    return jumps


def chord_landing(name, a1, a2, r, z, w=5.2, style=SLAB, dry=False):
    """把螺旋上 a1→a2 这一段弧换成一块直的休息平台（弦），返回 (门 x, 门 y, 门 z, 门朝向)"""
    p1 = (r * math.cos(math.radians(a1)), r * math.sin(math.radians(a1)))
    p2 = (r * math.cos(math.radians(a2)), r * math.sin(math.radians(a2)))
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    L = math.hypot(dx, dy)
    yaw = math.degrees(math.atan2(-dx, dy))
    cx, cy = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
    if not dry:
        nx.into("door")
        nx.box(name, (w, L + 1.4, 0.7), (cx, cy, z - 0.705), (0, 0, yaw), **style)
    fx, fy = fwd(yaw)
    return (cx, cy, z - 0.005, yaw), (cx + fx * L / 2, cy + fy * L / 2, z, yaw)


# ── 纸、柱心、远处的断梯 ─────────────────────────

def page():
    """底下摊开的一页纸（两页，中间一道下凹的书沟）：头一圈的断口都在它上方"""
    nx.into("page")
    nx.box("page_left", (10.6, 20.4, 0.8), (-5.4, 0, -0.8), **PAGE)
    nx.box("page_right", (10.6, 20.4, 0.8), (5.4, 0, -0.8), **PAGE)
    nx.box("page_gutter", (0.6, 20.2, 0.8), (0, 0, -1.0), **GUTTER)
    for i, (dx, c) in enumerate(((0.3, "mist"), (0.6, "lilac_pale"), (0.9, "lilac"))):
        nx.box(f"page_under_{i}", (22.0 - dx * 4, 20.6 - dx * 2, 0.5), (0, 0, -1.3 - i * 0.5), a=c, b=c, pattern="bands")


def core():
    """中心那根被炸开的柱心：一摞错开、转开的薄圆板，从纸上立起来，升到雾里（替掉原来吊着的大锤）"""
    nx.into("core")
    rnd = random.Random(23)
    z = 0.0
    i = 0
    while z < CORE_TOP:
        th = rnd.uniform(0.35, 0.8)
        r = rnd.uniform(0.7, 1.9)
        n = rnd.choice((5, 6, 8))
        nx.cylinder(f"core_{i:02d}", r, r * rnd.uniform(0.6, 1.0), th, (rnd.uniform(-0.45, 0.45), rnd.uniform(-0.45, 0.45), z),
                    (rnd.uniform(-7, 7), rnd.uniform(-7, 7), rnd.uniform(0, 360)), segments=n, collide=False, **CORE)
        z += th + rnd.uniform(0.3, 1.1)
        i += 1


def far():
    """远处雾里的几截别的断梯：斜着、倒着、竖着，不挡人（远处也读得出是楼梯）"""
    nx.into("far")
    rnd = random.Random(9)
    for i in range(9):
        a = math.tau * i / 9 + rnd.uniform(-0.25, 0.25)
        r = rnd.uniform(55, 115)
        x, y = math.cos(a) * r, math.sin(a) * r
        z = rnd.uniform(-12, 30)
        n = rnd.randint(6, 13)
        s = rnd.uniform(0.9, 1.8)
        flight_kit(n, RISE * s, RUN * s, W * s, 0.45 * s).build(
            f"far_{i}", loc=(x, y, z), rot=(rnd.choice((0, 0, 180, 35, -60)), rnd.uniform(-25, 25), rnd.uniform(0, 360)),
            smooth=0, collide=False, **FAR)


# ── 下半那座（stair） ────────────────────────────

def lower_geom():
    """下半那圈螺旋的几何：steps、runs、终点角度、终点半径、终点高度"""
    return helix_chain(0, 0, LO_ANG0, LO_R, 0.0, LO_SEGS)


_DOOR = None


def door_pose():
    global _DOOR
    if _DOOR is None:
        _, _, a_end, _, z_end = lower_geom()
        _DOOR = chord_landing("door_land", a_end, a_end + LAND_ARC, LO_R, z_end, dry=True)[0]
    return _DOOR


def lower_route(dry=False):
    """纸上那一圈螺旋（门的弦平台由 door_common 搭，两个世界各一份）。返回 (steps, runs, jumps, marks)"""
    steps, runs, a_end, r_end, z_end = lower_geom()
    skip = {11: 1, 24: 1, 33: 1}         # 三处断口（每处空一级：2×0.8m，高差 0.6m；纸在下面接着）
    jumps = build_helix("step", steps, runs, skip=skip, group=4, seed=1, dry=dry)
    marks = dict(spawn=steps[0], door=door_pose())
    return steps, runs, jumps, marks, z_end


def door_common(to, facing):
    """门洞这一带两个世界共用：门前的弦平台、门框、缝、门后看不见的挡板（照 house_out 的 door_back_block）"""
    dx, dy, dz, yaw = door_pose()
    _, _, a_end, _, z_end = lower_geom()
    chord_landing("door_land", a_end, a_end + LAND_ARC, LO_R, z_end, dry=False)
    fx, fy = fwd(yaw)
    nx.into("door")
    pf.frame("door_frame", (dx, dy, dz), yaw, w=DOOR_W - 0.02, h=DOOR_H - 0.012, depth=FRAME_DEPTH, t=FRAME_T,
             kind="door", a="mist", b="lilac_pale", pattern="plain")
    sx, sy = dx + fx * SEAM_OFF, dy + fy * SEAM_OFF
    nx.seam("seam_out", (sx, sy, dz), facing, to, DOOR_W - 0.02, DOOR_H - 0.01)
    # 门后看不见的挡板：在这道缝的「里面」那一边（朝 facing 的方向），离缝 0.45m
    gx, gy = fwd(facing)
    nx.collider_only(nx.box("door_back", (DOOR_W + 0.2, 0.04, DOOR_H + 0.2), (sx + gx * BLOCK_OFF, sy + gy * BLOCK_OFF, dz), (0, 0, facing)))
    return (dx, dy, dz, yaw)


def fragments():
    """浮在楼梯旁边的碎块：一段段掉下来的踏步，各自歪着、转开（炸开的样子）"""
    nx.into("frag")
    rnd = random.Random(41)
    for i in range(22):
        a = rnd.uniform(0, math.tau)
        r = rnd.uniform(7.5, 15.0)
        z = rnd.uniform(1.0, 34.0)
        x, y = math.cos(a) * r, math.sin(a) * r
        n = rnd.choice((1, 2, 3))
        span = rnd.uniform(0.9, 2.0)
        chunk_kit(n, span, rnd.uniform(1.2, 2.0), flip=rnd.random() < 0.4).build(
            f"frag_{i:02d}", loc=(x, y, z), rot=(rnd.uniform(-45, 45), rnd.uniform(-45, 45), rnd.uniform(0, 360)),
            smooth=0, collide=False, **STEP[i % 3])


def build(extent=EXTENT):
    nx.into("env")
    nx.sun((0.45, -0.55, 0.7))
    # 掉下去：脚底到 −14m 就回家，从家里的书桌前落下来（家里还没有就落在出生点）
    nx.atmosphere("halo", fall_to="house", fall_at="stair", fall_y=-14.0)

    page()
    steps, runs, jumps, marks, z_end = lower_route()
    door_common("stair_b", marks["door"][3])
    core()
    fragments()
    far()

    nx.into("places")
    x, y, z, yaw = marks["spawn"]
    sx, sy = x - fwd(yaw)[0] * 5.0, y - fwd(yaw)[1] * 5.0
    nx.spawn((sx, sy, 0.0), facing_deg=yaw)
    nx.arrive("house", (sx, sy, 0.0), facing_deg=yaw)
    for j in jumps:
        print("[nx] jump " + ",".join(f"{v:.2f}" for v in j))
    for k, v in marks.items():
        print(f"[nx] mark {k}: {v[0]:.2f},{v[1]:.2f},{v[2]:.2f} yaw {v[3]:.0f}")
    print(f"[nx] lower top z {z_end:.2f}, steps {len(steps)}")


if __name__ == "__main__":
    nx.reset()
    build()
    nx.save_blend("stair")
    nx.export("stair")
