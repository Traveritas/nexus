"""浅梦 · 长影（longshadow）：mockup/shallows-02 的新世界（第二版：围起来的盆地）。

一个直径约 180m 的盆地，四周缓坡和高地围住（走到坡上一段就过不去了）。太阳低低地压在西边的山脊上（仰角 ELEV），
不动；西边的山脊自己把盆地西边一块罩在影子里。盆地里一处挨一处都是影子的景象——投下影子的东西都看不见（nx.shade），
走到它们本该在的地方，什么也碰不到。

- 影子景象：一片影子树林（走进去光影斑驳）· 一架慢慢荡的秋千（会动的投影，nx_sway）· 一张长桌和一圈椅子 ·
  一段楼梯（影子斜铺到东边的坡上）· 一座格栅棚（地上一片格子光，正中浮着一枚晶体）· 一架竖琴（一排弦的影子）·
  一根挂着几片圆盘的转杆（影子绕着转）· 一只大花瓶 · 一扇悬空的窗框 · 一只衣柜。
- 传送点都在影子里，各自落在影子主人身上的一件东西上：
  · 花瓶影子的瓶颈里插着一丛真的花，只在影子里看得见（伸出瓶的轮廓就断掉），E「凑近」→ 花房（glasshouse）
  · 窗框影子里左下那格是暗的（关着一扇看不见的窗扇），E「推开窗」亮出来，走进去 → 光斑（sunpatch）
  · 衣柜的影子是整块的，E「打开柜门」，中间透出一线光，走进去 → 家（house）
- 出生点在东边，朝西：太阳压在山脊上，桌椅、秋千、花瓶、树林的影子都朝人伸过来。

运行：node scripts/blender.cjs build longshadow，网页 ?world=longshadow
"""
import math
import os
import random
import sys

import bmesh
import bpy

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import furniture as fu  # noqa: E402
import nx  # noqa: E402

EXTENT = 220.0
CENTER = (0, 0)
SIZE = 220.0          # 地形网格的边长
STEP = 3.0
FLOOR_R = 50.0        # 盆底的半径（往外开始起坡）
RIM_R = 80.0          # 坡顶
WALL_R = 68.0         # 看不见的墙：坡上走到这里就过不去了
SHADOW_REACH = 90

ELEV = 12.0           # 太阳仰角
AZ = 172.0            # 太阳在西边略偏北（从 +x 起逆时针）
TO_SUN = (math.cos(math.radians(ELEV)) * math.cos(math.radians(AZ)),
          math.cos(math.radians(ELEV)) * math.sin(math.radians(AZ)),
          math.sin(math.radians(ELEV)))
_h = math.hypot(TO_SUN[0], TO_SUN[1])
D = (-TO_SUN[0] / _h, -TO_SUN[1] / _h)     # 影子往哪伸（地上的单位向量）
P = (-D[1], D[0])                          # 与影子垂直
LONG = 1 / math.tan(math.radians(ELEV))    # 每米高投多长

GROUND = dict(ramp=("lilac", "lilac_pale", "pink_pale"), pattern="grain")
SLOPE = dict(ramp=("lilac", "pink", "pink_pale"), pattern="grain")


def facing(dx, dy):
    """朝 (dx, dy) 看的 facing_deg（同 spawn：0 ＝ +Y，90 ＝ −X）"""
    return math.degrees(math.atan2(-dx, dy))


def yaw_x_to(dx, dy):
    """让本地 +X 指向 (dx, dy) 的绕 Z 角度"""
    return math.degrees(math.atan2(dy, dx))


# 本地 +Y 朝太阳（正面对着太阳）的角度
SUNWARD = facing(-D[0], -D[1])


# ── 地形 ─────────────────────────────────────────

_rnd = random.Random(9)
BUMPS = [((_rnd.uniform(-45, 45), _rnd.uniform(-45, 45)), _rnd.uniform(10, 20), _rnd.uniform(-0.6, 0.6)) for _ in range(9)]


def rim_height(theta):
    """坡顶有多高：西边（太阳那边）矮一点，太阳才压得在山脊上；别处高一些，起伏不齐"""
    west = max(0.0, -math.cos(theta))
    return 22.0 - 14.0 * west + 2.6 * math.sin(3 * theta + 0.7) + 1.6 * math.sin(5 * theta + 2.1)


def height(x, y):
    r = math.hypot(x, y)
    th = math.atan2(y, x)
    # 盆底是一只浅碗（越往外越高一点）：远处的地朝人抬起来，影子不全压成线
    floor = 0.0012 * r * r + sum(a * math.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * s * s)) for (cx, cy), s, a in BUMPS)
    if r <= FLOOR_R:
        return floor
    t = min(1.0, (r - FLOOR_R) / (RIM_R - FLOOR_R))
    t = t * t * (3 - 2 * t)
    top = rim_height(th)
    z = floor * (1 - t) + top * t
    if r > RIM_R:   # 坡顶往外是一圈平台，再缓缓落下一点
        z = top - 0.04 * (r - RIM_R)
    return z


def terrain():
    """一张高度网格；盆底与坡分两块上色（坡的颜色深一档、带漂的纹）"""
    n = int(round(SIZE / STEP))
    h0 = -SIZE / 2
    verts = [(h0 + i * STEP, h0 + j * STEP, height(h0 + i * STEP, h0 + j * STEP)) for j in range(n + 1) for i in range(n + 1)]
    parts = {k: ([], [], {}) for k in ("floor", "slope")}

    def vid(part, v):
        vs, _, idx = part
        if v not in idx:
            idx[v] = len(vs)
            vs.append(verts[v])
        return idx[v]

    for j in range(n):
        for i in range(n):
            q = [j * (n + 1) + i, j * (n + 1) + i + 1, (j + 1) * (n + 1) + i + 1, (j + 1) * (n + 1) + i]
            cx, cy = h0 + (i + 0.5) * STEP, h0 + (j + 0.5) * STEP
            part = parts["floor" if math.hypot(cx, cy) < FLOOR_R + 6 else "slope"]
            tris = [(q[0], q[1], q[2]), (q[0], q[2], q[3])] if (i + j) % 2 else [(q[0], q[1], q[3]), (q[1], q[2], q[3])]
            for t in tris:
                part[1].append(tuple(vid(part, v) for v in t))
    for name, style in (("floor", GROUND), ("slope", SLOPE)):
        k = fu.Kit()
        k._add(parts[name][0], parts[name][1])
        obj = k.build(f"ground_{name}", smooth=50, **style)
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.normal_update()
        for f in bm.faces:
            if f.normal.z < 0:
                f.normal_flip()
        bm.to_mesh(obj.data)
        bm.free()


def walls():
    """坡上一圈看不见的墙：走到这里就过不去了"""
    n = 48
    for i in range(n):
        a = math.tau * (i + 0.5) / n
        x, y = math.cos(a) * WALL_R, math.sin(a) * WALL_R
        w = math.tau * WALL_R / n + 0.6
        nx.collider_only(nx.box(f"wall_{i}", (w, 0.5, 40), (x, y, height(x, y) - 5), (0, 0, math.degrees(a) + 90)))


# ── 只投影的东西 ───────────────────────────────────

def ground_at(x, y):
    return height(x, y)


def sbox(name, size, loc, rot=(0, 0, 0), parent=None):
    return nx.shade(nx.box(name, size, loc, rot, parent=parent))


def shadow_point(x, y, z):
    """(x, y) 处高 z 的一点的影子落在地上哪（按盆底近似平地算）"""
    return (x + D[0] * z * LONG, y + D[1] * z * LONG)


def sball(name, r, loc):
    obj = nx._new_mesh_obj(name, bpy.ops.mesh.primitive_ico_sphere_add, subdivisions=2, radius=r)
    nx._place(obj, loc, (0, 0, 0), None)
    return nx.shade(nx.matte(obj))


def forest(cx, cy, n=22, R=17.0, seed=4):
    """一片影子树林：走进它的影子里，光一块块的"""
    rnd = random.Random(seed)
    for i in range(n):
        a, d = rnd.uniform(0, math.tau), R * math.sqrt(rnd.random())
        x, y = cx + math.cos(a) * d, cy + math.sin(a) * d
        z = ground_at(x, y)
        h = rnd.uniform(4.5, 7.5)
        r = rnd.uniform(1.8, 3.2)
        nx.shade(nx.cylinder(f"tree{i}_trunk", 0.35, 0.25, h + 1, (x, y, z - 0.5), segments=8))
        sball(f"tree{i}_crown", r, (x, y, z + h + r * 0.5))
        if rnd.random() < 0.7:
            sball(f"tree{i}_crown2", r * 0.65, (x + rnd.uniform(-1.6, 1.6), y + rnd.uniform(-1.6, 1.6), z + h + r * 1.25))


def swing(x, y):
    """一架秋千：架子不动，座板连两根绳绕横杆来回荡（原点在横杆上，nx_sway）。
    荡的方向与影子垂直，影子才看得出在动"""
    z = ground_at(x, y)
    H = 4.6
    yaw = yaw_x_to(*D)   # 本地 +X 顺着影子：横杆沿本地 X……要横杆垂直于影子，座板就沿影子方向荡——反过来：
    yaw = yaw_x_to(*P)   # 横杆沿 P（与影子垂直）；绕横杆摆，座板沿 D 荡；影子在地上拉长着来回伸缩
    g = nx.group("swing", (x, y, z), (0, 0, yaw))
    for s in (-1, 1):
        for t in (-1, 1):
            sbox(f"swing_leg{s}{t}", (0.22, 0.22, H + 0.4), (s * 1.6, t * 0.9, -0.2), (t * -11, 0, 0), parent=g)
    sbox("swing_bar", (3.6, 0.25, 0.25), (0, 0, H - 0.1), parent=g)
    k = fu.Kit()
    rope = 3.4
    for s in (-1, 1):
        k.box((0.1, 0.1, rope), (s * 0.6, 0, -rope))
    k.box((1.5, 0.5, 0.12), (0, 0, -rope - 0.06))
    obj = k.build("swing_seat", loc=(x, y, z + H), rot=(0, 0, yaw), smooth=0, collide=False)
    nx.shade(obj)
    nx.behave(obj, sway=28.0)


def banquet(x, y):
    """一张长桌和一圈椅子（桌顺着影子摆，影子是一条长桌带一排排椅背）"""
    z = ground_at(x, y)
    yaw = yaw_x_to(*P)
    g = nx.group("banquet", (x, y, z), (0, 0, yaw))
    L, W = 7.0, 1.4
    sbox("table_top", (L, W, 0.12), (0, 0, 0.78), parent=g)
    for s in (-1, 1):
        for t in (-1, 1):
            sbox(f"table_leg{s}{t}", (0.15, 0.15, 0.8), (s * (L / 2 - 0.3), t * (W / 2 - 0.2), -0.02), parent=g)
    seats = [(sx, -1, 0) for sx in (-2.6, -1.3, 0.0, 1.3, 2.6)] + [(sx, 1, 180) for sx in (-2.6, -1.3, 0.0, 1.3, 2.6)]
    seats += [(-L / 2 - 0.9, 0, -90), (L / 2 + 0.9, 0, 90)]
    for i, (cx, side, r) in enumerate(seats):
        cy = side * (W / 2 + 0.55) if side else 0
        c = nx.group(f"chair{i}", (cx, cy, 0), (0, 0, r))
        c.parent = g
        sbox(f"chair{i}_seat", (0.5, 0.5, 0.08), (0, 0, 0.45), parent=c)
        sbox(f"chair{i}_back", (0.5, 0.08, 0.6), (0, -0.25, 0.5), parent=c)
        for s in (-1, 1):
            for t in (-1, 1):
                sbox(f"chair{i}_leg{s}{t}", (0.06, 0.06, 0.46), (s * 0.2, t * 0.2, 0), parent=c)


def stair(x, y, n=16, rise=0.55, run=0.9, w=2.4):
    """一段横着往上的楼梯（每级一块实心的，沿与影子垂直的方向升高）：影子的边是一级级的锯齿，斜铺到东边的坡上"""
    z = ground_at(x, y)
    sx, sy = P
    for i in range(n):
        sbox(f"stair_{i}", (run, w, rise * (i + 1)), (x + sx * run * i, y + sy * run * i, z - 0.3), (0, 0, yaw_x_to(sx, sy)))


def pergola(x, y, size=9.0, h=3.4, n=7):
    """一座格栅棚：四根柱，顶上纵横的板条——地上一片格子光"""
    z = ground_at(x, y)
    g = nx.group("pergola", (x, y, z), (0, 0, yaw_x_to(*D) + 10))
    for s in (-1, 1):
        for t in (-1, 1):
            sbox(f"pergola_post{s}{t}", (0.3, 0.3, h), (s * size / 2, t * size / 2, -0.2), parent=g)
    for i in range(n):
        o = -size / 2 + size * i / (n - 1)
        sbox(f"pergola_a{i}", (size + 0.6, 0.22, 0.22), (0, o, h), parent=g)
        sbox(f"pergola_b{i}", (0.22, size + 0.6, 0.22), (o, 0, h + 0.22), parent=g)


def harp(x, y, h=8.0):
    """一架竖琴：弯的琴颈、斜的音箱、一排弦；琴面正对太阳，弦的影子一根根分开"""
    z = ground_at(x, y)
    g = nx.group("harp", (x, y, z), (0, 0, SUNWARD))
    sbox("harp_pillar", (0.45, 0.45, h), (-2.4, 0, 0), parent=g)
    sbox("harp_box", (0.9, 0.7, h * 0.95), (1.2, 0, 0.2), (0, -28, 0), parent=g)
    # 琴颈：一段弧，用几块拼
    for i in range(7):
        t = i / 6
        px = -2.4 + t * 4.9
        pz = h - 0.4 + math.sin(t * math.pi) * 0.9 - t * 0.6
        sbox(f"harp_neck{i}", (0.95, 0.4, 0.45), (px, 0, pz), (0, 12 - 24 * t, 0), parent=g)
    for i in range(11):
        t = (i + 0.7) / 12
        px = -2.4 + t * 4.4
        top = h - 0.4 + math.sin(t * math.pi) * 0.9 - t * 0.6
        bottom = 0.3 + t * 1.2 * h * 0.47
        sbox(f"harp_str{i}", (0.07, 0.07, max(0.5, top - bottom)), (px, 0, bottom), parent=g)


def mobile(x, y, h=9.0):
    """一根转杆，顶上挂着几片圆盘，慢慢转（nx_spin）：影子绕着转"""
    z = ground_at(x, y)
    sbox("mobile_pole", (0.3, 0.3, h + 0.5), (x, y, z - 0.5))
    k = fu.Kit()
    rnd = random.Random(2)
    for i in range(5):
        a = math.tau * i / 5
        r = rnd.uniform(2.2, 4.2)
        hz = rnd.uniform(-3.2, -0.6)
        k.box((r, 0.12, 0.12), (r / 2, 0, 0), rot=(0, 0, math.degrees(a)))
        cx, cy = math.cos(a) * r, math.sin(a) * r
        k.box((0.06, 0.06, -hz), (cx, cy, hz))
        k.lathe([(0.0, 0.0), (rnd.uniform(0.8, 1.4), 0.0), (rnd.uniform(0.8, 1.4), 0.12), (0.0, 0.12)], (cx, cy, hz - 0.12),
                rot=(90, 0, math.degrees(a)), seg=12)
    obj = k.build("mobile_arms", loc=(x, y, z + h), smooth=0, collide=False)
    nx.shade(obj)
    obj["nx_spin"] = 7.0


def land(px, py, dx, dy, name, d=2.6):
    """到达点：从传送点 (px, py) 顺着 (dx, dy) 再走 d 米，回头朝着传送点"""
    n = math.hypot(dx, dy) or 1.0
    ax, ay = px + dx / n * d, py + dy / n * d
    nx.arrive(name, (ax, ay, ground_at(ax, ay)), facing_deg=facing(-dx, -dy))


def vase(x, y, h=7.0):
    """一只大花瓶：圆肚、细颈、外翻的瓶口。瓶口的影子落在影子的最远处——站进瓶口的影子里去花房"""
    z = ground_at(x, y)
    k = fu.Kit()
    k.lathe([(0.0, 0.0), (1.2, 0.0), (2.2, 0.25 * h), (2.0, 0.5 * h), (0.75, 0.72 * h), (0.6, 0.86 * h), (1.7, h), (0.0, h)],
            seg=14)
    nx.shade(k.build("vase", loc=(x, y, z - 0.1), smooth=0, collide=False))
    return vase_flowers(x, y)


def vase_flowers(x, y, at_h=5.0):
    """瓶里的花：一丛真的花，插在瓶颈的影子里，只在影子里看得见（lit_only="shade"）。
    太阳的光是平行的：离地 z 高的一点，落在瓶身 at_h + z 高处的影子里——看得见的那一块正好是瓶颈往上、瓶口外翻的轮廓，
    花杆从窄处起、花头在瓶口那么宽的地方张开，伸出轮廓的瓣、高过瓶口的那一截齐齐断掉。像一只看不见的瓶里插着花。
    E「凑近」→ 花房；从花房回来落在影子旁的太阳里，朝着花"""
    fx, fy = shadow_point(x, y, at_h)
    fz = ground_at(fx, fy)
    rnd = random.Random(14)
    stems, heart = fu.Kit(), fu.Kit()
    heads = [fu.Kit() for _ in range(3)]
    n = 7
    for k in range(n):
        s = (k - (n - 1) / 2) / ((n - 1) / 2)       # 横着从一边排到另一边（-1..1，沿 P）
        b0 = rnd.uniform(-0.25, 0.25)
        base = (fx + P[0] * (s * 0.22 + rnd.uniform(-0.05, 0.05)) + D[0] * b0,
                fy + P[1] * (s * 0.22 + rnd.uniform(-0.05, 0.05)) + D[1] * b0, fz - 0.05)
        zt = rnd.uniform(1.4, 1.85)
        off = s * 1.0 + rnd.uniform(-0.15, 0.15)
        mid = (base[0] + P[0] * off * 0.3, base[1] + P[1] * off * 0.3, fz + zt * 0.6)
        top = (base[0] + P[0] * off, base[1] + P[1] * off, fz + zt)
        fu._rod(stems, base, mid, 0.05)
        fu._rod(stems, mid, top, 0.05)
        if k % 2:
            yaw = math.degrees(math.atan2(P[1], P[0])) + (0 if s >= 0 else 180)
            stems.leaf(0.42, 0.14, 0.03, (base[0], base[1], fz + zt * 0.32), rot=(0, -rnd.uniform(25, 40), yaw))
        axis = (P[0] * s * 0.6, P[1] * s * 0.6, 1.0)
        Lp = rnd.uniform(0.2, 0.26)
        fu._petals(heads[k % 3], top, axis, 6, Lp, Lp * 0.62, rnd.uniform(28, 45), Lp * 0.16, start=rnd.uniform(0, 60), thick=0.025)
        heart.lathe([(0.0, -0.01), (Lp * 0.24, 0.0), (Lp * 0.2, Lp * 0.14), (0.0, Lp * 0.2)], top, rot=fu._aim(axis), seg=6)
    only = dict(smooth=0, collide=False, shadow=False, lit_only="shade", pattern="plain")
    stems.build("vase_flower_stems", a="lilac_pale", b="mist", **only)
    heart.build("vase_flower_hearts", a="pink_pale", b="white", **only)
    for i, kt in enumerate(heads):
        kt.build(f"vase_flower_heads{i}", **{**only, **fu.FLOWER_HEADS[i]})
    nx.portal("portal_glasshouse", (fx, fy, fz + 1.0), "glasshouse", at="longshadow", mode="key", title="凑近", radius=1.5)
    # 从花房回来：落在影子旁边的太阳里，回头朝着花
    land(fx, fy, P[0], P[1], "glasshouse", d=3.0)
    return fx, fy


def window_frame(x, y, w=6.0, h=6.0, z0=3.0, t=0.45):
    """一扇悬空的窗框，田字格，正对太阳；影子里三块亮格、一块暗的：左下那格（离窗最近的那一排、左手边）关着一扇看不见的窗扇。
    站在那块暗格里按 E「推开窗」，窗扇绕竖着的那条边转开，地上那块影子跟着转成一条细线，亮出第四格；走进这格 → 光斑"""
    z = ground_at(x, y) + z0
    g = nx.group("frame", (x, y, z), (0, 0, SUNWARD))
    bars = [(w, t, 0, 0), (w, t, 0, h - t), (t, h, -w / 2 + t / 2, 0), (t, h, w / 2 - t / 2, 0), (w, t, 0, h / 2 - t / 2),
            (t, h, 0, 0)]
    for i, (sx, sz, lx, lz) in enumerate(bars):
        sbox(f"frame_{i}", (sx, t, sz), (lx, 0, lz), parent=g)
    # 下排一格的中心：本地 x = ±w/4，高 z0 + h/4
    a = math.radians(SUNWARD)
    lx = -w / 4
    cx, cy = x + lx * math.cos(a), y + lx * math.sin(a)
    px, py = shadow_point(cx, cy, z0 + h / 4)
    pz = ground_at(px, py)
    # 窗扇：铰链在这格靠外的竖边上（本地 x = -w/2 + t），四边各伸进窗框 3cm（关着不漏光）；比窗框薄，虚像那份不和窗框共面
    cw, ch = w / 2 - 1.5 * t + 0.06, h / 2 - 1.5 * t + 0.06
    sash = fu.Kit()
    sash.box((cw, 0.12, ch), (cw / 2, 0, 0))
    leaf = nx.shade(sash.build("frame_sash", parent=g, loc=(-w / 2 + t - 0.03, 0, t - 0.03), smooth=0, collide=False))
    nx.pose(leaf, "frame_sash", on="key", at=(px, py, pz + 1.0), radius=1.8, rot=(0, 0, 100), time=1.2, title="推开窗|关上窗")
    nx.portal("portal_sunpatch", (px, py, pz + 1.0), "sunpatch", mode="walk", radius=0.9, need="frame_sash")


def wardrobe(x, y, w=3.0, d=0.9, h=3.0, gap=0.5):
    """一只衣柜（进来时是从衣柜）：柜身中间一道缝，顺着太阳穿过整个柜子；朝太阳那面两扇柜门关着，影子是整块的。
    柜子看不见，柜里挂的一排衣服看得见——只在影子里画（lit_only="shade"），柜里本来就在柜子自己的影子里，
    走近看见一排衣服悬在半空、围出一只柜子。柜门上两只把手是实的。
    走到柜前按 E「打开柜门」，两扇门往太阳那边转开：地上门的影子张开、柜影中间透出一线光，缝前那一截横杆跟着不见。
    从两扇门中间走进柜里回家（同家里那只：开柜门、走进去）"""
    z = ground_at(x, y)
    g = nx.group("wardrobe", (x, y, z), (0, 0, SUNWARD))   # 本地 +Y 朝太阳，x 是柜宽
    a = math.radians(SUNWARD)

    def world(lx, ly, lz):
        return (x + lx * math.cos(a) - ly * math.sin(a), y + lx * math.sin(a) + ly * math.cos(a), z + lz)

    half = (w - gap) / 2
    for s in (-1, 1):
        sbox(f"wardrobe_half{s}", (half, d, h), (s * (gap / 2 + half / 2), 0, -0.2), parent=g)
    sbox("wardrobe_top", (w + 0.2, d + 0.1, 0.25), (0, 0, h - 0.2 + 0.0), parent=g)
    # 顶板盖住了缝的上头：缝的光只在柜顶以下，影子里是一条从柜脚伸出去、到柜顶影子为止的细光
    clothes(g, w, d, h, gap)
    # 柜门：贴在朝太阳那面外 1cm，铰链在两头，各宽半个柜子；门开着光才进得了缝。把手是实的，跟着门转，纸签系在把手上
    front = world(0, d / 2 + 0.6, 1.2)
    for s in (-1, 1):
        k = fu.Kit()
        k.box((w / 2, 0.06, h), (-s * w / 4, 0, 0))
        door = nx.shade(k.build(f"wardrobe_door{s}", parent=g, loc=(s * w / 2, d / 2 + 0.04, -0.2), smooth=0, collide=False))
        kx = -s * (w / 2 - 0.12)
        kn = fu.Kit()
        kn.box((0.05, 0.05, 0.32), (kx, 0.07, 1.25))
        for zz in (1.29, 1.53):
            kn.box((0.03, 0.06, 0.03), (kx, 0.035, zz))
        knob = kn.build(f"wardrobe_knob{s}", parent=g, loc=(s * w / 2, d / 2 + 0.04, -0.2), smooth=0, collide=False,
                        a="pink_pale", b="white", pattern="plain")
        for o in (door, knob):
            nx.pose(o, "wardrobe_doors", on="key", at=front, radius=2.0, rot=(0, 0, -100 * s), time=1.0,
                    title="打开柜门|关上柜门", anchor=(kx, 0.1, 1.4) if o is knob and s < 0 else None)
    cx, cy, cz = world(0, 0, 1.0)
    nx.portal("portal_home", (cx, cy, cz), "house", at="longshadow", mode="walk", radius=0.45, need="wardrobe_doors")
    return cx, cy


def clothes(g, w, d, h, gap):
    """柜里挂的一排衣服：一根横杆、一只只衣架、长短不一的衣裳（面朝柜门，薄的那面顺着横杆）。
    都只在影子里画——伸出柜子的影子就没了；柜门开着时，中间那道缝进了光，缝前那一截横杆就不见了"""
    rnd = random.Random(23)
    only = dict(smooth=0, collide=False, shadow=False, lit_only="shade")
    rail_z = h - 0.75
    rail = fu.Kit()
    rail.box((w - 0.3, 0.04, 0.04), (0, 0, rail_z))
    cloth = [fu.Kit() for _ in range(4)]
    looks = [dict(a="blue_pale", b="white", pattern="plain"), dict(a="pink", b="pink_pale", pattern="plain"),
             dict(a="lilac", b="lilac_pale", pattern="plain"), dict(a="white", b="mist", pattern="plain")]
    # 缝两边各空出 0.45m（低太阳的影子边是软的，缝里透进来的光会往两边晕开这么宽），缝里不挂
    xs = []
    for s in (-1, 1):
        xc = gap / 2 + 0.45
        while xc < w / 2 - 0.22:
            xs.append(s * xc)
            xc += rnd.uniform(0.17, 0.24)
    for i, cx in enumerate(xs):
        k = cloth[rnd.randrange(4)]
        L = rnd.choice((0.75, 0.95, 1.25, 1.5))
        t = rnd.uniform(0.05, 0.08)
        lean = rnd.uniform(-4, 4)
        top = rail_z - 0.12
        # 衣架：一只钩、两条斜肩
        rail.box((0.012, 0.012, 0.1), (cx, 0, top + 0.02))
        for sd in (-1, 1):
            rail.box((0.012, 0.24, 0.012), (cx, sd * 0.11, top - 0.04), rot=(sd * 18, 0, 0))
        # 衣裳：肩一块、身子往下略收（两块叠着，宽在本地 Y）
        k.box((t, 0.46, 0.22), (cx, 0, top - 0.24), rot=(0, lean, 0))
        k.box((t * 0.9, 0.4, L - 0.2), (cx, 0, top - L), rot=(0, lean, 0))
    rail.build("wardrobe_rail", parent=g, a="mist", b="white", pattern="plain", **only)
    for i, k in enumerate(cloth):
        if k.f:
            k.build(f"wardrobe_clothes{i}", parent=g, **only, **looks[i])


# ── 虚像 ──────────────────────────────────────────
# 投影的东西远远地看得见一点：淡淡的、半透的一层（nx_ghost），走近就散掉，只剩影子。
# 山脊上另有几样只有虚像、没有影子的东西——和盆里「只有影子」的反过来
GHOST = dict(a="white", b="lilac_pale", pattern="plain", collide=False, shadow=False)
GHOST_NEAR = (0.42, 14.0, 34.0)   # 盆里的：14m 内看不见，34m 外最浓
GHOST_FAR = (0.5, 26.0, 60.0)     # 山脊上的：走到坡上就散了


def ghosts_of_shadows():
    """每一件只投影的东西复制一份虚像（共用网格，会动的跟着一起动）"""
    for o in [o for o in bpy.data.objects if o.type == "MESH" and o.get("nx_mat") == "shade"]:
        g = o.copy()
        g.name = o.name + "_ghost"
        for c in o.users_collection:
            c.objects.link(g)
        nx.matte(g, ghost=GHOST_NEAR, **GHOST)


def mirages():
    """山脊上的虚像：一扇很高的门框（北）、一段伸进天里的楼梯（南）、一座细塔（东北）。都没有影子"""
    def at(theta_deg, r):
        t = math.radians(theta_deg)
        x, y = math.cos(t) * r, math.sin(t) * r
        return x, y, height(x, y)

    def ghost_box(name, size, loc, rot=(0, 0, 0), parent=None):
        return nx.box(name, size, loc, rot, parent=parent, ghost=GHOST_FAR, **GHOST)

    # 北：门框，正对盆心
    x, y, z = at(95, 84)
    g = nx.group("mirage_door", (x, y, z - 1), (0, 0, facing(-x, -y)))
    w, h, t = 9.0, 22.0, 1.4
    for s in (-1, 1):
        ghost_box(f"mirage_door_post{s}", (t, t, h), (s * (w / 2 + t / 2), 0, 0), parent=g)
    ghost_box("mirage_door_lintel", (w + 2 * t, t, t), (0, 0, h), parent=g)
    # 南：一段楼梯往天上去，越往上越淡（一级比一级小）
    x, y, z = at(-80, 82)
    g = nx.group("mirage_stair", (x, y, z - 0.5), (0, 0, facing(x, y)))
    for i in range(22):
        ghost_box(f"mirage_stair_{i}", (6.0 - i * 0.18, 1.6, 0.6), (0, i * 1.7, i * 1.25), parent=g)
    # 东北：一座细塔
    x, y, z = at(40, 88)
    ghost_box("mirage_tower", (2.2, 2.2, 34.0), (x, y, z - 1), (0, 0, 20))


def build(extent=EXTENT):
    nx.into("env")
    nx.sun(TO_SUN)
    nx.atmosphere("lowsun", shadow_reach=SHADOW_REACH)

    nx.into("ground")
    terrain()
    walls()

    nx.into("shadows")
    # 出生点在东边朝西（太阳压在西边山脊上），景象都在它前后左右二三十米内，影子朝人伸过来
    banquet(14, 4)
    vase(-8, 22)
    swing(2, -18)
    mobile(-24, -2)
    pergola(-10, -34)
    window_frame(-30, 14)
    wardrobe(18, -34)
    forest(4, 36, n=12, R=13.0)
    harp(-30, -22)
    stair(36, -12)

    # 晶体：格栅棚的格子光正中（url 先空）
    cx, cy = shadow_point(-10, -34, 3.4)
    nx.entrance("crystal", (cx, cy, ground_at(cx, cy) + 1.6), "", "")

    sx, sy = 24.0, 3.0
    nx.spawn((sx, sy, ground_at(sx, sy)), facing_deg=facing(-1, -0.02))

    nx.into("ghosts")
    ghosts_of_shadows()
    mirages()

if __name__ == "__main__":
    nx.reset()
    build()
    nx.save_blend("longshadow")
    nx.export("longshadow")
