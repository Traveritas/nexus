"""现实的家（原型）共用的构件：撕下来的地板、断掉的墙、一间卧室的残片。
三个原型（wake_fragment / wake_white / wake_museum）都从这里取。
床 E「睡」→ 梦里的家（home，落在床边的 wake）；从梦里回来落在床边（到达点 home）。
"""
import math
import random

import furniture as fu
import nx

WALL = dict(a="pink_pale", b="mist", pattern="bands")
SKIRT = dict(a="rose", b="rose_deep", pattern="plain")
BOARDS = dict(a="pink_pale", b="rose", pattern="bands")
UNDER = dict(a="lilac_pale", b="lilac", pattern="grain")
PLASTER = dict(a="white", b="mist", pattern="grain")


def prism(name, outline, z0, z1, parent=None, loc=(0, 0, 0), rot=(0, 0, 0), collide=True, shadow=True, **style):
    """按俯视轮廓（逆时针的 (x, y) 序列，可以凹）拉出一块板，z0 到 z1"""
    k = fu.Kit()
    n = len(outline)
    verts = [(x, y, z0) for x, y in outline] + [(x, y, z1) for x, y in outline]
    faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    k._add(verts, faces)
    return k.build(name, parent=parent, loc=loc, rot=rot, smooth=0, collide=collide, shadow=shadow, **style)


def torn_outline(x0, y0, x1, y1, torn, seed=0, bite=0.5, step=0.35):
    """矩形的轮廓，torn 里列出的边（'s' 'e' 'n' 'w'）撕成参差的：每 step 米一个点，往里咬 0..bite 米。
    逆时针：南边（y0）从西往东 → 东边 → 北边 → 西边"""
    r = random.Random(seed)
    sides = [("s", (x0, y0), (x1, y0), (0, 1)), ("e", (x1, y0), (x1, y1), (-1, 0)),
             ("n", (x1, y1), (x0, y1), (0, -1)), ("w", (x0, y1), (x0, y0), (1, 0))]
    pts = []
    for key, (ax, ay), (bx, by), (nx_, ny_) in sides:
        L = math.hypot(bx - ax, by - ay)
        m = max(1, int(L / step)) if key in torn else 1
        for i in range(m):
            t = i / m
            px, py = ax + (bx - ax) * t, ay + (by - ay) * t
            if key in torn:
                # 撕口：大多浅浅地咬一口，偶尔深深地缺一块
                d = r.uniform(0.0, bite) * (1.8 if r.random() < 0.15 else 1.0)
                if i == 0:  # 角上：与上一条边一起撕
                    d *= 0.6
                px += nx_ * d + (r.uniform(-0.08, 0.08) if 0 < i else 0) * (1 - abs(nx_))
                py += ny_ * d + (r.uniform(-0.08, 0.08) if 0 < i else 0) * (1 - abs(ny_))
            pts.append((px, py))
    return pts


def torn_floor(name, x0, y0, x1, y1, torn, seed=0, parent=None, boards=BOARDS, under=UNDER, deep=0.45):
    """一块撕下来的楼板：上面一层木地板（0 到 -0.12），下面一层结构层撕得更狠、更厚，底下再挂一层天花板的白灰。
    顶面在本地 z=0"""
    prism(f"{name}_boards", torn_outline(x0, y0, x1, y1, torn, seed, 0.45), -0.12, 0.0, parent=parent, **boards)
    prism(f"{name}_slab", torn_outline(x0 + 0.05, y0 + 0.05, x1 - 0.05, y1 - 0.05, torn, seed + 1, 0.8), -0.12 - deep, -0.12,
          parent=parent, **under)
    prism(f"{name}_plaster", torn_outline(x0 + 0.3, y0 + 0.3, x1 - 0.3, y1 - 0.3, torn, seed + 2, 1.0), -0.2 - deep, -0.12 - deep,
          parent=parent, collide=False, **PLASTER)


def broken_wall(name, a, b, h, torn_end=1, seed=0, t=0.2, gaps=(), parent=None, style=WALL, broken=1.8):
    """沿 a→b 砌一面墙（俯视的两点，底在 z=0），torn_end=1 时 b 端断掉（0 时 a 端，None 不断）：
    最后 broken 米切成竖条，越往断口越矮、参差。gaps：[(离 a 的距离, 宽, 洞底, 洞顶)] 开窗。
    断口附近掉下来的几块砖浮在旁边"""
    r = random.Random(seed)
    ax, ay = a
    bx, by = b
    L = math.hypot(bx - ax, by - ay)
    ux, uy = (bx - ax) / L, (by - ay) / L
    yaw = math.degrees(math.atan2(uy, ux))
    g = nx.group(name, (ax, ay, 0), (0, 0, yaw))
    if parent is not None:
        g.parent = parent

    # 每一列：(s0, s1, 顶高)
    cols = []
    s, k = 0.0, 0
    whole = L - broken if torn_end is not None else L
    if torn_end == 0:
        # a 端断：先把断的一截排在前面
        pieces = []
        x = 0.0
        while x < broken - 1e-6:
            w = min(r.uniform(0.25, 0.45), broken - x)
            pieces.append((x, x + w))
            x += w
        for i, (p0, p1) in enumerate(pieces):
            f = (i + 1) / len(pieces)
            cols.append((p0, p1, h * (0.25 + 0.7 * f) * r.uniform(0.85, 1.05)))
        cols.append((broken, L, h))
    else:
        cols.append((0.0, whole, h))
        if torn_end == 1:
            x = whole
            pieces = []
            while x < L - 1e-6:
                w = min(r.uniform(0.25, 0.45), L - x)
                pieces.append((x, x + w))
                x += w
            for i, (p0, p1) in enumerate(pieces):
                f = 1 - (i + 1) / (len(pieces) + 1)
                cols.append((p0, p1, h * (0.2 + 0.75 * f) * r.uniform(0.85, 1.05)))

    def put(s0, s1, z0, z1):
        if s1 - s0 < 0.01 or z1 - z0 < 0.01:
            return
        nx.box(f"{name}_{k}_{s0:.2f}_{z0:.2f}", (s1 - s0, t, z1 - z0), ((s0 + s1) / 2, 0, z0), parent=g, **style)

    for s0, s1, top in cols:
        # 这一列里遇到窗洞就让开
        cur = s0
        for c, w, z0, z1 in sorted(gaps):
            g0, g1 = c - w / 2, c + w / 2
            if g1 <= s0 or g0 >= s1:
                continue
            g0, g1 = max(g0, s0), min(g1, s1)
            put(cur, g0, 0, top)
            put(g0, g1, 0, min(z0, top))
            if z1 < top:
                put(g0, g1, z1, top)
            cur = g1
        put(cur, s1, 0, top)
        k += 1
    # 踢脚：只铺完整的那一截，两头各缩进 1cm
    s0, s1 = (broken, L) if torn_end == 0 else (0.0, whole)
    if s1 - s0 > 0.1:
        nx.box(f"{name}_skirt", (s1 - s0 - 0.02, t + 0.05, 0.12), ((s0 + s1) / 2, 0, 0), parent=g, collide=False, **SKIRT)
    # 掉出去的砖
    if torn_end is not None:
        end = L if torn_end == 1 else 0.0
        sgn = 1 if torn_end == 1 else -1
        for i in range(4):
            bz = r.uniform(0.6, h * 0.9)
            b_ = nx.box(f"{name}_crumb{i}", (r.uniform(0.18, 0.4), t * r.uniform(0.6, 1.0), r.uniform(0.15, 0.3)),
                        (end + sgn * r.uniform(0.5, 1.6), r.uniform(-0.3, 0.3), bz), rot=(r.uniform(-30, 30), r.uniform(-30, 30), r.uniform(0, 90)),
                        parent=g, collide=False, **style)
            nx.behave(b_, bob=r.uniform(0.04, 0.1))
    return g


def window_in_wall(name, x, y, yaw, w=1.2, sill=0.9, top=2.2, parent=None):
    """嵌在墙洞里的窗：窗框、窗台、十字棂（不挡人的薄条）"""
    fr = dict(a="white", b="mist", pattern="plain")
    g = nx.group(name, (x, y, 0), (0, 0, yaw))
    if parent is not None:
        g.parent = parent
    t = 0.07
    nx.box(f"{name}_sill", (w + 0.16, 0.3, 0.05), (0, 0.02, sill), parent=g, collide=False, **fr)
    nx.box(f"{name}_l", (t, 0.12, top - sill - 0.05), (-w / 2 + t / 2, 0, sill + 0.05), parent=g, collide=False, **fr)
    nx.box(f"{name}_r", (t, 0.12, top - sill - 0.05), (w / 2 - t / 2, 0, sill + 0.05), parent=g, collide=False, **fr)
    nx.box(f"{name}_top", (w - 2 * t, 0.12, t), (0, 0, top - t), parent=g, collide=False, **fr)
    nx.box(f"{name}_mid", (w - 2 * t, 0.05, 0.04), (0, 0, (sill + top) / 2), parent=g, collide=False, **fr)
    nx.box(f"{name}_vert", (0.04, 0.035, top - sill - 0.05 - t), (0, 0, sill + 0.05), parent=g, collide=False, **fr)
    return g


def nightstand(name, loc, yaw=0.0, parent=None):
    p = fu.Piece(name, loc, yaw, parent)
    p["wood"].box((0.5, 0.42, 0.52), bevel=0.02)
    p["knob"].box((0.06, 0.03, 0.04), (0, 0.22, 0.36))
    p["knob"].box((0.2, 0.01, 0.01), (0, 0.211, 0.22))
    return p.done({"wood": fu.WOOD_PALE, "knob": fu.BRASS}, knob=dict(collide=False))


def bedroom(prefix, origin=(0, 0, 0), yaw=0.0, torn=("s", "e"), seed=0, size=(7.0, 6.0), ceiling=True, H=2.8):
    """一间卧室的残片。西墙、北墙还在（各断在一头），南边、东边撕开。床头靠北墙，E「睡」→ 梦里的家。
    返回 (组, 床边落脚点的世界坐标, 朝向)"""
    W, D = size
    x0, x1, y0, y1 = -W / 2, W / 2, -D / 2, D / 2
    root = nx.group(f"{prefix}room", origin, (0, 0, yaw))
    T = 0.2

    nx.into(f"{prefix}floor")
    torn_floor(f"{prefix}floor", x0, y0, x1, y1, torn, seed, parent=root)
    nx.box(f"{prefix}rug", (2.6, 1.8, 0.02), (0.4, 0.0, 0), parent=root, collide=False, a="blue_pale", b="blue", pattern="stripes")

    nx.into(f"{prefix}walls")
    # 北墙：从西往东，东头断；床左边开一扇窗
    broken_wall(f"{prefix}wall_n", (x0, y1 - T / 2), (x1 - 1.2, y1 - T / 2), H, torn_end=1, seed=seed + 3,
                gaps=[(1.4, 1.2, 0.9, 2.2)], parent=root)
    window_in_wall(f"{prefix}win", x0 + 1.4, y1 - T / 2, 0, parent=root)
    # 西墙：从北往南，南头断（和北墙在西北角相接：西墙让开北墙的厚度）
    broken_wall(f"{prefix}wall_w", (x0 + T / 2, y1 - T), (x0 + T / 2, y0 + 1.0), H, torn_end=1, seed=seed + 4, parent=root)

    nx.into(f"{prefix}furniture")
    bx, by = 0.75, y1 - T - 1.12
    fu.bed(f"{prefix}bed", (bx, by, 0), 0, parent=root)
    nightstand(f"{prefix}stand", (bx - 1.25, y1 - T - 0.25, 0), 0, parent=root)
    fu.table_lamp(f"{prefix}lamp", (bx - 1.32, y1 - T - 0.24, 0.52), 0, parent=root)
    fu.alarm_clock(f"{prefix}clock", (bx - 1.1, y1 - T - 0.33, 0.52), -20, parent=root)
    fu.bookshelf(f"{prefix}shelf", (x0 + T + 0.18, 0.3, 0), -90, seed=seed + 5, parent=root)
    fu.chair(f"{prefix}chair", (x0 + 1.4, y0 + 1.4, 0), -140, kind="arm", fabric="pink", parent=root)
    fu.plant(f"{prefix}plant", (x0 + 0.55, y1 - 0.6, 0), height=1.0, seed=seed + 6, parent=root)
    fu.notebook(f"{prefix}book", (bx - 1.0, by - 0.7, 0.58), 15, parent=root)

    if ceiling:
        # 天花板也撕下来一块，浮在上面，吊灯还挂着
        nx.into(f"{prefix}ceiling")
        cz = H + 1.6
        cg = nx.group(f"{prefix}ceil", (-0.8, 0.6, cz), (0, 0, 8))
        cg.parent = root
        prism(f"{prefix}ceil_plaster", torn_outline(-1.9, -1.6, 1.9, 1.6, "nesw", seed + 7, 0.6), 0, 0.12, parent=cg,
              collide=False, **PLASTER)
        prism(f"{prefix}ceil_slab", torn_outline(-1.7, -1.4, 1.7, 1.4, "nesw", seed + 8, 0.7), 0.12, 0.5, parent=cg,
              collide=False, **UNDER)
        fu.pendant(f"{prefix}pendant", (0, 0, 0), drop=0.9, shade="pink_pale", parent=cg)

    nx.into(f"{prefix}gate")
    a = math.radians(yaw)
    ca, sa = math.cos(a), math.sin(a)

    def world(px, py, pz):
        return (origin[0] + px * ca - py * sa, origin[1] + px * sa + py * ca, origin[2] + pz)
    nx.portal(f"{prefix}portal_bed", world(bx, by, 0.8), "home", at="wake", mode="key", title="睡", radius=1.3)
    land = world(bx + 1.9, by - 0.5, 0)
    nx.arrive("home", land, facing_deg=yaw + 90)
    return root, land, yaw + 90
