"""预制件：可以在各个主题之间反复使用、拼接的构件族。每个族有几种变体，都带随机种子。
只管轮廓与标注（nx.matte）；家具、器物这类现实物在 furniture.py。

族一览（详见各函数）：
- 花之装置  bloom(kind=rosette|lotus|blade|halo|drift)：以花为隐喻的装置，花瓣是平的、尖头的板
- 框        frame(kind=door|window|square|arch)、procession（一串渐变的框）
- 阶        stair_straight、stair_spiral（顶上是开口的平台）、steps_between（悬空踏步）
- 环        halo、orrery（一组倾斜的、慢慢转的环）、arch_ring（立着的残环）
- 碑与塔    monolith、tower_broken（断开错位的塔）、plate_stack（一摞错开的薄板）
- 台        island（下面收尖的浮岛）、pad（缺口圆台）、plinth（低矮的方台）
- 器        vessel(lying=True|False)（杯，可以走进去）
- 纸片撒布  paper_scatter、paper_ring
- 世界之间  gate_home|book|bed|wardrobe|vase|glass|vessel|window：通往各个世界的东西 + 传送物 + 回来的到达点
"""
import math
import random

import bpy
from mathutils import Vector

import furniture as fu
import nx
import shapes as sh


def _rnd(seed):
    return random.Random(seed)


# ── 基本形：尖头的板 ─────────────────────────────

def plate(name, length, width, thick=0.18, waist=0.55, loc=(0, 0, 0), rot=(0, 0, 0), parent=None, **style):
    """一块两头尖的板：沿本地 +X 伸出，宽在 Y，厚在 Z；waist 是最宽处所在的位置（0~1）"""
    L, W = length, width / 2
    outline = [(0, 0), (L * 0.18, W * 0.62), (L * waist, W), (L * 0.86, W * 0.5), (L, 0),
               (L * 0.86, -W * 0.5), (L * waist, -W), (L * 0.18, -W * 0.62)]
    n = len(outline)
    verts = [(x, y, -thick / 2) for x, y in outline] + [(x, y, thick / 2) for x, y in outline]
    faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    return sh._mesh_obj(name, verts, faces, loc, rot, parent, **style)


# ── 花之装置 ─────────────────────────────────────

PETAL_STYLES = [
    dict(a="white", b="pink_pale"),
    dict(a="pink_pale", b="pink"),
    dict(a="mist", b="blue_pale"),
]


def bloom(name, loc, kind="rosette", size=4.0, seed=0, yaw=None, petals=None, gap=None, open_deg=None,
          styles=None, hub_style=None, collide=True, parent=None, skip_az=None, axis=True):
    """以花为隐喻的装置。size ≈ 花瓣长度（米）。返回 (组, 信息 dict)
    rosette：一圈向上张开的板，围着一根细轴，板与轴之间留一道空隙；
             skip_az（组内角度）处空出一瓣，留给梯子；axis=False 不要中轴（中间放入口时）
    lotus  ：两三层板，内层直、外层平，坐在一只环形台上
    blade  ：几片竖直的长板绕轴扭转，像还没打开的花
    halo   ：板沿一个竖直的圆排开，中间是空的——一扇花形的门（入口放在圆心）
    drift  ：几片散开、慢慢浮动的板（落下的瓣）
    """
    r = _rnd(seed)
    styles = styles or PETAL_STYLES
    hub_style = hub_style or dict(a="lilac_pale", b="lilac", pattern="stripes")
    g = nx.group(name, loc, (0, 0, r.uniform(0, 360) if yaw is None else yaw))
    if parent is not None:
        g.parent = parent
    info = {"center_z": 0.0}

    def sty(i):
        s = dict(styles[i % len(styles)])
        s.setdefault("pattern", "grain")
        s["collide"] = collide
        return s

    if kind == "rosette":
        n = petals or 7
        gap_ = size * 0.18 if gap is None else gap
        op = 52 if open_deg is None else open_deg
        if axis:
            nx.cylinder(f"{name}_axis", size * 0.05 + 0.1, size * 0.04 + 0.08, size * 0.9, (0, 0, 0), segments=12,
                        parent=g, **hub_style)
        for i in range(n):
            az = 360 / n * i + r.uniform(-7, 7)
            if skip_az is not None and abs((az - skip_az + 180) % 360 - 180) < 360 / n * 0.75:
                continue
            a = math.radians(az)
            z = size * r.uniform(0.18, 0.32)
            L = size * r.uniform(0.85, 1.12)
            plate(f"{name}_p{i}", L, L * r.uniform(0.3, 0.38), thick=max(0.14, size * 0.03),
                  loc=(math.cos(a) * gap_, math.sin(a) * gap_, z), rot=(r.uniform(-6, 6), -(op + r.uniform(-8, 8)), az),
                  parent=g, **sty(i))
    elif kind == "lotus":
        tiers = [(petals or 8, 22, 0.75, size * 0.25), (petals or 8, 50, 0.95, size * 0.32), ((petals or 8) + 3, 74, 1.0, size * 0.42)]
        sh.tube(f"{name}_base", size * 0.5, size * 0.3, size * 0.12, (0, 0, 0), segments=40, parent=g, **hub_style)
        for t, (n, tilt, k, rr) in enumerate(tiers):
            off = r.uniform(0, 360)
            for i in range(n):
                az = off + 360 / n * i + r.uniform(-5, 5)
                a = math.radians(az)
                L = size * k * r.uniform(0.9, 1.08)
                plate(f"{name}_t{t}p{i}", L, L * 0.36, thick=max(0.14, size * 0.03),
                      loc=(math.cos(a) * rr, math.sin(a) * rr, size * (0.12 + 0.05 * (2 - t))),
                      rot=(0, -(90 - tilt) - r.uniform(-5, 5), az), parent=g, **sty(t + i))
        info["center_z"] = size * 0.12
    elif kind == "blade":
        n = petals or 5
        for i in range(n):
            az = 360 / n * i + r.uniform(-12, 12)
            a = math.radians(az)
            L = size * r.uniform(0.7, 1.15)
            lean = 90 - r.uniform(4, 14)
            plate(f"{name}_b{i}", L, L * 0.24, thick=max(0.14, size * 0.035), waist=0.4,
                  loc=(math.cos(a) * size * 0.06, math.sin(a) * size * 0.06, 0),
                  rot=(r.uniform(-8, 8), -lean, az + r.uniform(20, 40)), parent=g, **sty(i))
    elif kind == "halo":
        n = petals or 10
        R = size * 0.75 if gap is None else gap
        hub = nx.group(f"{name}_ring", (0, 0, R + size + 0.2), (0, 0, 0))
        hub.parent = g
        info["center_z"] = R + size + 0.2
        for i in range(n):
            az = 360 / n * i + r.uniform(-4, 4)
            a = math.radians(az)
            L = size * r.uniform(0.85, 1.1)
            # 竖直圆（XZ 平面）上，板从圆周向外伸
            plate(f"{name}_h{i}", L, L * 0.34, thick=max(0.14, size * 0.03),
                  loc=(math.cos(a) * R, 0, math.sin(a) * R), rot=(90 + r.uniform(-10, 10), -az, 0),
                  parent=hub, **sty(i))
        # 底下一根座
        nx.box(f"{name}_foot", (size * 0.5, size * 0.35, R * 0.3 + 0.2), (0, 0, 0), parent=g, **hub_style)
    elif kind == "drift":
        n = petals or 6
        for i in range(n):
            a = r.uniform(0, math.tau)
            d = r.uniform(0.5, 1.5) * size
            L = size * r.uniform(0.3, 0.55)
            p = plate(f"{name}_d{i}", L, L * 0.36, thick=0.14,
                      loc=(math.cos(a) * d, math.sin(a) * d, r.uniform(0.6, 2.2) * size),
                      rot=(r.uniform(-40, 40), r.uniform(-40, 40), r.uniform(0, 360)), parent=g,
                      **{**sty(i), "collide": False})
            nx.behave(p, spin=r.uniform(-10, 10), bob=r.uniform(0.2, 0.6))
    else:
        raise ValueError(kind)
    return g, info


# ── 框 ───────────────────────────────────────────

def frame(name, loc, yaw=0.0, w=2.2, h=3.4, depth=0.35, t=0.3, kind="door", roll=0.0, parent=None, **style):
    """立着的框；loc 是底边中点。kind：door 无底；window 有台、有十字棂；square 四边封闭；arch 半圆顶"""
    style = style or dict(a="mist", b="lilac_pale", pattern="plain")
    g = nx.group(name, loc, (roll, 0, yaw))
    if parent is not None:
        g.parent = parent
    if kind in ("door", "window", "square"):
        # 有底时两边立在底上（不和底并排落地），免得端面、底面叠在一起闪
        z0 = t if kind in ("window", "square") else 0
        nx.box(f"{name}_l", (t, depth, h - z0), (-w / 2 - t / 2, 0, z0), parent=g, **style)
        nx.box(f"{name}_r", (t, depth, h - z0), (w / 2 + t / 2, 0, z0), parent=g, **style)
        nx.box(f"{name}_top", (w + 2 * t, depth, t), (0, 0, h), parent=g, **style)
        if z0:
            nx.box(f"{name}_bot", (w + 2 * t, depth * 1.4, t), (0, 0, 0), parent=g, **style)
        if kind == "window":
            nx.box(f"{name}_mv", (0.14, 0.14, h - t), (0, 0, t), parent=g, **style)
            nx.box(f"{name}_mh", (w, 0.12, 0.14), (0, 0, h * 0.55), parent=g, **style)  # 比竖棂薄，交叉处不共面
    elif kind == "arch":
        R = w / 2 + t
        post = max(0.1, h - w / 2)
        nx.box(f"{name}_l", (t, depth, post), (-w / 2 - t / 2, 0, 0), parent=g, **style)
        nx.box(f"{name}_r", (t, depth, post), (w / 2 + t / 2, 0, 0), parent=g, **style)
        sh.tube(f"{name}_arc", R, w / 2, depth, (0, depth / 2, post), rot=(90, 0, 0), segments=48, arc=180,
                parent=g, **style)
    else:
        raise ValueError(kind)
    return g


def procession(name, start, end, n, kinds=("door", "window", "arch", "square"), w0=2.4, h0=3.6, grow=1.6,
               roll_step=0.0, palette=("lilac", "lilac_pale", "pink_pale", "white"), seed=0, depth=0.35):
    """从 start 到 end 立 n 个框，尺寸按 grow 渐变、颜色按 palette 渐变、可逐个侧倾 roll_step 度"""
    r = _rnd(seed)
    sx, sy, sz = start
    ex, ey, ez = end
    yaw = math.degrees(math.atan2(-(ex - sx), ey - sy))
    out = []
    for i in range(n):
        t = i / max(1, n - 1)
        k = 1 + (grow - 1) * t
        col = palette[min(len(palette) - 1, int(t * len(palette)))]
        kind = kinds[i % len(kinds)] if r.random() > 0.15 else r.choice(kinds)
        out.append(frame(f"{name}{i}", (sx + (ex - sx) * t, sy + (ey - sy) * t, sz + (ez - sz) * t), yaw,
                         w=w0 * k, h=h0 * k, depth=depth, t=0.3 * k ** 0.5, kind=kind, roll=roll_step * i,
                         a=col, b="mist", pattern="plain"))
    return out


# ── 阶 ───────────────────────────────────────────

def stair_straight(name, loc, yaw, steps, rise=0.3, run=0.75, width=2.4, solid=True, parent=None, **style):
    """直梯：从 loc 沿本地 +Y 上升。solid=False 时每级只是一块悬空的板。返回顶面世界坐标的局部描述"""
    style = style or dict(a="mist", b="lilac_pale", pattern="bands")
    g = nx.group(name, loc, (0, 0, yaw))
    if parent is not None:
        g.parent = parent
    for k in range(steps):
        top = rise * (k + 1)
        h = top if solid else 0.3
        nx.box(f"{name}{k}", (width, run, h), (0, k * run, top - h), parent=g, **style)
    return g, (0, steps * run, rise * steps)


def stair_spiral(name, center, z0, steps, r_in=0.9, r_out=2.7, rise=0.3, tread=19, start=0,
                 landing_arc=110, landing_r=None, **style):
    """螺旋梯，顶上是一段扇形平台（不封顶，走得上去）。返回平台中心的世界坐标（站立面）"""
    style = style or dict(a="pink_pale", b="pink", pattern="plain")
    top = sh.spiral_stair(f"{name}_s", center, r_in, r_out, rise, steps, start, tread, z0=z0, **style)
    a_end = start + tread * steps
    lr = landing_r or r_out + 0.6
    land_top = top + rise
    sh.tube(f"{name}_land", lr, 0, 0.3, (center[0], center[1], land_top - 0.3), segments=64, arc=landing_arc,
            start=a_end, **style)
    mid = math.radians(a_end + landing_arc / 2)
    rr = lr * 0.55
    return (center[0] + math.cos(mid) * rr, center[1] + math.sin(mid) * rr, land_top)


def steps_between(name, p0, p1, rise_max=0.3, gap=0.25, size=1.2, seed=0, **style):
    """两点之间一串悬空的方踏步，高差均分且每级 ≤ rise_max。p0、p1 是站立面坐标"""
    style = style or dict(a="mist", b="lilac_pale", pattern="plain")
    r = _rnd(seed)
    dz = p1[2] - p0[2]
    dist = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    n = max(int(math.ceil(abs(dz) / rise_max)), int(dist / (size + gap)))
    for i in range(1, n):
        t = i / n
        x = p0[0] + (p1[0] - p0[0]) * t
        y = p0[1] + (p1[1] - p0[1]) * t
        z = p0[2] + dz * t
        # 顶面低 1cm：两头的踏步常压在岛面上，同高会闪
        nx.box(f"{name}{i}", (size, size, 0.3), (x, y, z - 0.31), rot=(0, 0, r.uniform(-10, 10)), **style)
    return n


# ── 环 ───────────────────────────────────────────

def halo(name, loc, R, minor=None, tilt=0.0, spin=0.0, **style):
    style = style or dict(a="white", b="lilac_pale")
    t = nx.torus(name, R, minor or (0.25 + R * 0.015), loc, rot=(tilt, 0, 0), major_seg=128, minor_seg=12,
                 collide=not spin, **style)
    if spin:
        nx.behave(t, spin=spin)
    return t


def orrery(name, loc, radii=(5, 8.5, 12.5), seed=0, colors=("blue_pale", "white", "mist", "pink_pale")):
    """一组不同倾角、不同转速的环，共一个圆心"""
    r = _rnd(seed)
    out = []
    for i, R in enumerate(radii):
        out.append(halo(f"{name}{i}", loc, R, tilt=r.uniform(10, 70) * (1 if i % 2 else -1),
                        spin=r.uniform(1.5, 6) * (1 if i % 2 else -1), a=colors[i % len(colors)], b="lilac_pale"))
        out[-1].rotation_euler.z = math.radians(r.uniform(0, 180))
    return out


def arch_ring(name, loc, yaw, R, thick=0.6, depth=0.8, arc=230, start=-25, **style):
    """立着的残环：一段圆弧，脚落在地上"""
    style = style or dict(a="mist", b="lilac_pale", pattern="plain")
    g = nx.group(name, loc, (0, 0, yaw))
    sh.tube(f"{name}_arc", R, R - thick, depth, (0, depth / 2, R), rot=(90, 0, 0), segments=96, arc=arc,
            start=start, parent=g, **style)
    return g


# ── 碑与塔 ───────────────────────────────────────

def monolith(name, loc, yaw, w=1.4, d=0.6, h=4.0, **style):
    style = style or dict(a="mist", b="lilac_pale", pattern="grain")
    return nx.box(name, (w, d, h), loc, rot=(0, 0, yaw), **style)


def tower_broken(name, loc, h, w=1.6, pieces=3, seed=0, **style):
    """一座分成几截、截与截之间悬空错位的塔"""
    r = _rnd(seed)
    style = style or dict(a="lilac_pale", b="lilac", pattern="bands")
    z = 0.0
    yaw = r.uniform(0, 90)
    for i in range(pieces):
        seg = h / pieces * r.uniform(0.7, 1.2)
        nx.box(f"{name}{i}", (w, w, seg), (loc[0] + r.uniform(-0.3, 0.3) * i, loc[1] + r.uniform(-0.3, 0.3) * i,
                                            loc[2] + z), rot=(0, 0, yaw + r.uniform(-12, 12) * i), **style)
        z += seg + (r.uniform(0.8, 2.4) if i < pieces - 1 else 0)


def plate_stack(name, loc, n=8, w=3.0, d=2.2, t=0.3, seed=0, colors=("white", "mist", "pink_pale", "lilac_pale")):
    """一摞错开的薄板（也可以当台阶走上去：每块 t 高）"""
    r = _rnd(seed)
    for i in range(n):
        nx.box(f"{name}{i}", (w * r.uniform(0.85, 1.1), d * r.uniform(0.85, 1.1), t),
               (loc[0] + r.uniform(-0.25, 0.25), loc[1] + r.uniform(-0.25, 0.25), loc[2] + i * t),
               rot=(0, 0, r.uniform(-14, 14)), a=colors[i % len(colors)], b="lilac_pale", pattern="bands")


# ── 台 ───────────────────────────────────────────

def island(name, loc, r, depth=None, seed=0, top_style=None, under_style=None):
    """浮岛：顶面在 loc，下面收成尖"""
    rr = _rnd(seed)
    depth = depth or r * rr.uniform(0.9, 1.4)
    top_style = top_style or dict(a="mist", b="lilac_pale", pattern="grain")
    under_style = under_style or dict(a="lilac_pale", b="lilac", pattern="bands")
    x, y, z = loc
    nx.cylinder(f"{name}_top", r, r, 0.6, (x, y, z - 0.6), segments=40, **top_style)
    nx.cylinder(f"{name}_under", r * 0.12, r * 0.98, depth, (x, y, z - 0.6 - depth), segments=40, **under_style)


def pad(name, loc, r, h=0.2, notch=30, start=None, seed=0, **style):
    style = style or dict(a="pink_pale", b="mist", pattern="plain")
    rr = _rnd(seed)
    return sh.tube(name, r, 0, h, loc, arc=360 - notch, start=rr.uniform(0, 360) if start is None else start, **style)


def plinth(name, loc, w, d, h=0.3, yaw=0.0, **style):
    style = style or dict(a="lilac_pale", b="lilac", pattern="tiles")
    return nx.box(name, (w, d, h), loc, rot=(0, 0, yaw), **style)


# ── 器 ───────────────────────────────────────────

def vessel(name, loc, yaw=0.0, R=2.7, length=6.0, lying=True, **style):
    """杯：lying=True 横躺，杯口朝本地 +Y，可以走进去；返回杯里可站立处（世界坐标，用来放入口）"""
    style = style or dict(a="mist", b="blue_pale", pattern="bands")
    x, y, z = loc
    if lying:
        g = nx.group(name, (x, y, z + R), (0, 0, yaw))
        sh.tube(f"{name}_wall", R, R - 0.28, length, (0, 0, 0), rot=(90, 0, 0), segments=56, parent=g, **style)
        nx.cylinder(f"{name}_base", R, R, 0.4, (0, -length, 0), rot=(90, 0, 0), segments=56, parent=g,
                    a="blue_pale", b="mist", pattern="plain")
        bpy.context.view_layer.update()
        p = g.matrix_world @ Vector((0, -length * 0.45, -R + 0.28))
        return g, tuple(p)
    g = nx.group(name, loc, (0, 0, yaw))
    sh.tube(f"{name}_wall", R, R - 0.25, length - 0.25, (0, 0, 0.25), segments=48, parent=g, **style)  # 立在杯底上，不和杯底并排
    nx.cylinder(f"{name}_base", R, R, 0.25, (0, 0, 0), segments=48, parent=g, a="blue_pale", b="mist", pattern="plain")
    return g, (x, y, z + 0.25)


# ── 纸片撒布 ─────────────────────────────────────

def paper_scatter(name, sprites, center, r_min, r_max, n, seed=0, z=0.0, avoid=None, face=True, shadow=False,
                  back="lilac_pale"):
    """在环带里撒纸片；avoid(x, y) 返回 True 的位置跳过。
    名字里的 {} 换成每张不同的种子：["tree.round:{}", "grass:{}"] 撒出来棵棵不同（程序化纸片见 src/proc.ts）"""
    r = _rnd(seed)
    k = 0
    tries = 0
    while k < n and tries < n * 20:
        tries += 1
        a = r.uniform(0, math.tau)
        d = math.sqrt(r.uniform(r_min ** 2, r_max ** 2))
        x, y = center[0] + math.cos(a) * d, center[1] + math.sin(a) * d
        if avoid and avoid(x, y):
            continue
        nx.sprite(f"{name}{k}", sprites[k % len(sprites)].replace("{}", str(seed * 100 + k)), (x, y, z), rot_deg=(0, 0, r.uniform(0, 360)), face=face,
                  shadow=shadow, back=back)
        k += 1


def paper_ring(name, sprite, center, R, n, z=0.0, facing="in", start=0.0, back="mist", shadow=True):
    """纸片沿圆排开，固定朝向（不跟人转）：facing='in' 正面朝圆心，'out' 背朝圆心"""
    out = []
    for i in range(n):
        a = math.radians(start + 360 / n * i)
        x, y = center[0] + math.cos(a) * R, center[1] + math.sin(a) * R
        # 纸片的正面朝本地 -Y（空物体的「朝向」+Y 是它背面的方向）
        yaw = math.degrees(a) + (-90 if facing == "in" else 90)
        out.append(nx.sprite(f"{name}{i}", sprite, (x, y, z), rot_deg=(0, 0, yaw), face=False, shadow=shadow, back=back))
    return out


def halo_gate(name, loc, yaw, size=5.0, seed=0, styles=None, stair_style=None):
    """花形的门：一圈竖直的花瓣板，一道直梯走上去，平台穿过圆心；返回入口的世界坐标。
    梯子从本地 -Y 来（朝 +Y 走上去）"""
    R = size * 0.75
    g, info = bloom(f"{name}_halo", loc, kind="halo", size=size, seed=seed, yaw=yaw, styles=styles)
    cz = loc[2] + info["center_z"]
    top = cz - 1.6
    steps = int(math.ceil(top / 0.3))
    top = steps * 0.3 + loc[2]
    stair_style = stair_style or dict(a="white", b="mist", pattern="bands")
    run = 0.7
    a = math.radians(yaw)
    fwd = Vector((-math.sin(a), math.cos(a), 0))
    start = Vector(loc) - fwd * (steps * run + 1.6)
    stair_straight(f"{name}_stair", tuple(start), yaw, steps, run=run, width=2.4, **stair_style)
    plat = Vector(loc) - fwd * 1.6
    # 平台接在最上一级后面（不压在上面，否则同高的顶面会闪）
    nx.box(f"{name}_deck", (2.6, 3.6, 0.4), (plat.x + fwd.x * 1.8, plat.y + fwd.y * 1.8, top - 0.4), rot=(0, 0, yaw),
           **stair_style)
    return (loc[0], loc[1], top + 1.6)


# ── 世界之间 ─────────────────────────────────────

# 每个世界有一个认得出的意象，去哪个世界就碰那个世界的东西（在家里和在别的世界里是同一样东西）：
#   家 ← 灯（E「关灯」）          回廊 ← 摊开的书（E「翻开」）   下沉 ← 床（E「睡」）
#   无墙之屋 ← 衣柜（走进去）     花房 ← 插着花的瓶（E「凑近」）  浅滩 ← 一杯水（E）
#   云阶 ← 落地窗（走出去）
# 默认从 B 回来落在 A 里通往 B 的东西跟前，所以每个 gate_* 都同时放三样：
# 东西本身、传送物（去 to，落在 to 里名为 here 的到达点）、到达点（名字是 to，在东西正前方，背对它）。
# 东西的正面朝本地 +Y（yaw 同 nx.spawn），人从正面来、也从正面离开。
# 走进去的两样（衣柜、窗）洞口里有一层膜（nx.veil），走近时铺满，颜色是要去的世界的。
VEIL = {"room": ("pink", "pink_pale"), "isles": ("blue_pale", "white")}


def _ahead(loc, yaw, d, side=0.0):
    a = math.radians(yaw)
    return (loc[0] - math.sin(a) * d + math.cos(a) * side, loc[1] + math.cos(a) * d + math.sin(a) * side, loc[2])


def _pair(name, here, to, loc, yaw, portal_at, mode, title, radius, land=2.0, spawn=False):
    nx.portal(f"portal_{name}", portal_at, to, at=here, mode=mode, title=title, radius=radius)
    p = _ahead(loc, yaw, land)
    nx.arrive(to, p, facing_deg=yaw)
    if spawn:
        nx.spawn(p, facing_deg=yaw)


def gate_home(here, loc, yaw=0.0, height=3.4, spawn=True):
    """回家：一盏路灯，E「关灯」，醒在家里通往这个世界的那样东西旁边。默认这里也是出生点（从家里来的人落在这里）"""
    fu.street_lamp(f"lamp_home_{here}", loc, yaw, height)
    _pair(f"home_{here}", here, "home", loc, yaw, (loc[0], loc[1], loc[2] + 1.5), "key", "关灯", 0.8, spawn=spawn)


def gate_book(here, loc, yaw=0.0, **kw):
    """去回廊：一只斜面的书台，上面摊着一本比人肩还宽的书，E「翻开」"""
    p = fu.Piece(f"book_{here}", loc, yaw)
    p["stand"].box((0.7, 0.5, 0.08), bevel=0.02)
    p["stand"].box((0.26, 0.26, 0.9), (0, -0.05, 0.08), bevel=0.03)
    # 斜面朝人（本地 +Y 低）；封面、书页沿斜面的法线一层层叠上去，各让开 5mm，不共面
    tilt = math.radians(18)
    n = (0, math.sin(tilt), math.cos(tilt))

    def on(z0, d):
        return (0, n[1] * d, z0 + n[2] * d)
    p["stand"].box((1.3, 0.85, 0.06), (0, 0, 0.98), rot=(-18, 0, 0), bevel=0.02)
    p["cover"].box((1.24, 0.8, 0.03), on(0.98, 0.065), rot=(-18, 0, 0))
    # 两页从书脊往外翘起，摊成浅浅的 V；左右页分开建（之间勾一道线），一条丝带从书脊垂到台前
    for s in (-1, 1):
        x, y, z = on(0.98, 0.1)
        p[f"page{s}"].box((0.58, 0.74, 0.06), (s * 0.3, y, z + 0.03), rot=(-18, s * -9, 0))
    x, y, z = on(0.98, 0.1)
    p["ribbon"].box((0.08, 0.03, 0.42), (0, y + 0.42, z - 0.42), rot=(-8, 0, 0))
    page = dict(a="white", b="mist", pattern="bands")
    p.done({"stand": fu.WOOD_DARK, "cover": dict(a="violet", b="violet_deep", pattern="plain"),
            "page-1": page, "page1": page, "ribbon": dict(a="pink", b="rose", pattern="plain")},
           ribbon=dict(collide=False))
    _pair(f"book_{here}", here, "procession", loc, yaw, (loc[0], loc[1], loc[2] + 1.2), "key", "翻开", 0.9, **kw)


def gate_bed(here, loc, yaw=0.0, **kw):
    """去下沉：一张床（床头朝本地 +Y），E「睡」；到达点在床的右手边"""
    fu.bed(f"bed_{here}", loc, yaw)
    nx.portal(f"portal_bed_{here}", (loc[0], loc[1], loc[2] + 0.8), "descent", at=here, mode="key", title="睡", radius=1.3)
    p = _ahead(loc, yaw, -0.3, side=2.1)
    nx.arrive("descent", p, facing_deg=yaw - 90)
    if kw.get("spawn"):
        nx.spawn(p, facing_deg=yaw - 90)


def wardrobe(name, loc, yaw, to, here, land=2.2):
    """衣柜：开着的两扇门，里面挂着衣服，衣服后面一层膜；走进去就走了。loc 是柜背中点，柜门朝本地 +Y"""
    x, y, z = loc
    W, D, Ht = 1.8, 0.9, 2.35
    g = nx.group(name, loc, (0, 0, yaw))
    st = dict(a="lilac_pale", b="lilac", pattern="tiles")
    wood = dict(a="rose", b="rose_deep", pattern="bands")
    # 背板、侧板、顶板各接各的，不叠出共面
    nx.box(f"{name}_back", (W, 0.06, Ht - 0.08), (0, 0.03, 0), parent=g, **st)
    for s in (-1, 1):
        nx.box(f"{name}_side{s}", (0.06, D - 0.06, Ht - 0.08), (s * (W / 2 - 0.03), (D + 0.06) / 2, 0), parent=g, **st)
    nx.box(f"{name}_top", (W, D, 0.08), (0, D / 2, Ht - 0.08), parent=g, **st)
    nx.box(f"{name}_crown", (W + 0.12, D + 0.08, 0.1), (0, D / 2, Ht), parent=g, **wood)
    nx.box(f"{name}_inside", (W - 0.12, 0.02, Ht - 0.2), (0, 0.07, 0.05), parent=g, collide=False,
           a="violet_deep", b="violet", pattern="plain")
    a, b = VEIL[to]
    nx.veil(f"{name}_veil", W - 0.2, Ht - 0.3, (0, 0.13, 0.06), 0, a=a, b=b, parent=g)  # 在衣服后面、柜里衬板前面
    for s in (-1, 1):
        h = nx.group(f"{name}_hinge{s}", (s * W / 2, D, 0), (0, 0, s * 105))
        h.parent = g
        nx.box(f"{name}_door{s}", (W / 2 - 0.02, 0.05, Ht - 0.1), (-s * (W / 4), 0.025, 0.04), parent=h,
               a="lilac_pale", b="mist", pattern="tiles")
        nx.box(f"{name}_knob{s}", (0.05, 0.08, 0.14), (-s * (W / 2 - 0.12), 0.08, 1.05), parent=h, collide=False,
               a="gold", b="white", pattern="plain")
    # 衣杆与衣服：衣服不挡人，走进去就是拨开它们
    nx.box(f"{name}_rail", (W - 0.14, 0.05, 0.05), (0, D * 0.5, Ht - 0.35), parent=g, collide=False,
           a="rose_deep", b="violet", pattern="bands")
    r = random.Random(3)
    cols = ["pink", "blue_pale", "white", "lilac", "rose", "mist", "gold", "blue"]
    for k in range(9):
        L = r.uniform(0.75, 1.3)
        nx.box(f"{name}_cloth{k}", (0.12, r.uniform(0.42, 0.55), L), (-W / 2 + 0.2 + k * 0.175, D * 0.5, Ht - 0.4 - L),
               parent=g, collide=False, a=cols[k % len(cols)], b="mist", pattern="stripes" if k % 3 == 0 else "plain")
    _pair(name, here, to, loc, yaw, (*_ahead(loc, yaw, 0.45)[:2], z + 1.0), "walk", "", 0.5, land=land)
    return g


def gate_wardrobe(here, loc, yaw=0.0):
    """去无墙之屋：一只自己站着的衣柜，走进去"""
    return wardrobe(f"wardrobe_{here}", loc, yaw, "room", here)


def gate_window(here, loc, yaw=0.0, w=1.8, h=2.6, land=2.4):
    """去云阶：一扇自己站着的落地窗，两扇窗扇往后推开，洞口里一层天色的膜；走出去"""
    name = f"window_{here}"
    st = dict(a="white", b="mist", pattern="plain")
    g = frame(name, loc, yaw, w=w, h=h, depth=0.3, t=0.14, kind="door", **st)
    nx.box(f"{name}_transom", (w, 0.1, 0.1), (0, 0, h * 0.78), parent=g, collide=False, **st)
    nx.box(f"{name}_sill", (w + 0.5, 0.6, 0.09), (0, 0, 0.01), parent=g, **st)  # 离地 1cm，底面不贴着地面
    for s in (-1, 1):
        hinge = nx.group(f"{name}_hinge{s}", (s * w / 2, -0.15, 0.1), (0, 0, s * 70))
        hinge.parent = g
        nx.box(f"{name}_leaf{s}", (w / 2 - 0.04, 0.06, h - 0.15), (-s * (w / 4), -0.03, 0.02), parent=hinge,
               collide=False, a="mist", b="blue_pale", pattern="tiles")
    a, b = VEIL["isles"]
    nx.veil(f"{name}_veil", w - 0.02, h - 0.11, (0, 0.04, 0.1), 0, a=a, b=b, parent=g)
    _pair(name, here, "isles", loc, yaw, (loc[0], loc[1], loc[2] + 1.0), "walk", "", 0.5, land=land)
    return g


def gate_vase(here, loc, yaw=0.0, **kw):
    """去花房：方台上一只插满花的大瓶，E「凑近」"""
    plinth(f"vase_{here}_plinth", loc, 0.9, 0.9, h=0.5, yaw=yaw, a="white", b="mist", pattern="plain")
    fu.vase(f"vase_{here}", (loc[0], loc[1], loc[2] + 0.5), 0.8, "round", flowers=9, seed=len(here),
            style=dict(a="pink_pale", b="white", pattern="plain"))
    _pair(f"vase_{here}", here, "glasshouse", loc, yaw, (loc[0], loc[1], loc[2] + 1.4), "key", "凑近", 0.9, **kw)


def gate_glass(here, loc, yaw=0.0, **kw):
    """去浅滩：一只齐腰高的玻璃杯立在地上，盛着水，E「一杯水」"""
    x, y, z = loc
    sh.tube(f"glass_{here}", 0.5, 0.44, 1.05, (x, y, z + 0.08), segments=20, a="blue_pale", b="white", pattern="plain")
    nx.cylinder(f"glass_{here}_base", 0.52, 0.52, 0.08, (x, y, z), segments=20, a="white", b="blue_pale", pattern="plain")
    nx.cylinder(f"glass_{here}_water", 0.43, 0.43, 0.7, (x, y, z + 0.08), segments=20, collide=False,
                a="blue", b="blue_pale", pattern="bands")
    _pair(f"glass_{here}", here, "shoal", loc, yaw, (x, y, z + 1.3), "key", "一杯水", 0.9, **kw)


def gate_vessel(here, loc, yaw=0.0, R=2.5, length=5.5):
    """去浅滩（大的）：横躺的杯，走进杯里，E「一杯水」"""
    _, inside = vessel(f"vessel_{here}", loc, yaw=yaw, R=R, length=length)
    _pair(f"vessel_{here}", here, "shoal", loc, yaw, (inside[0], inside[1], inside[2] + 1.0), "key", "一杯水", 1.0,
          land=1.0)  # 杯口前一步；传送物在杯里深处
