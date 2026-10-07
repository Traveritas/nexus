"""nx.py 之外的几种形：管、扇、花瓣、螺旋梯、百合。
草案场景（idea_*）用；同样只管轮廓，标注照旧走 nx.matte。
"""
import math
import random

import bmesh
import bpy

import nx


def _mesh_obj(name, verts, faces, loc, rot, parent, smooth_deg=None, **style):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    nx._place(obj, loc, rot, parent)
    if smooth_deg:
        nx._smooth(obj, smooth_deg)
    return nx.matte(obj, **style)


def tube(name, r_out, r_in, h, loc=(0, 0, 0), rot=(0, 0, 0), segments=48, arc=360, start=0,
         parent=None, **style):
    """管 / 环形台：底面在 loc，沿本地 Z 高 h。r_in=0 是实心扇；arc<360 是缺口的环"""
    full = arc >= 360
    n = segments if full else max(2, int(segments * arc / 360)) + 1
    a0 = math.radians(start)
    da = math.radians(arc) / (segments if full else n - 1)
    verts, faces = [], []
    solid = r_in <= 0
    for i in range(n):
        a = a0 + da * i
        c, s = math.cos(a), math.sin(a)
        verts += [(c * r_out, s * r_out, 0), (c * r_out, s * r_out, h)]
        if not solid:
            verts += [(c * r_in, s * r_in, 0), (c * r_in, s * r_in, h)]
    k = 2 if solid else 4
    if solid:
        verts += [(0, 0, 0), (0, 0, h)]
        cb, ct = len(verts) - 2, len(verts) - 1
    m = n if full else n - 1
    for i in range(m):
        j = (i + 1) % n
        o0, o1 = i * k, j * k
        faces.append((o0, o1, o1 + 1, o0 + 1))            # 外壁
        if solid:
            faces.append((cb, o1, o0))
            faces.append((ct, o0 + 1, o1 + 1))
        else:
            faces.append((o0 + 2, o0 + 3, o1 + 3, o1 + 2))  # 内壁
            faces.append((o0, o0 + 2, o1 + 2, o1))          # 底
            faces.append((o0 + 1, o1 + 1, o1 + 3, o0 + 3))  # 顶
    if not full:
        for i in (0, n - 1):
            o = i * k
            if solid:
                faces.append((o, o + 1, ct, cb))
            else:
                faces.append((o, o + 1, o + 3, o + 2))
    return _mesh_obj(name, verts, faces, loc, rot, parent, smooth_deg=30, **style)


def petal(name, length, width, thick=0.16, rise=70, curl=120, cup=0.22, loc=(0, 0, 0), rot=(0, 0, 0),
          parent=None, nu=16, nv=7, **style):
    """一片花瓣：根部在 loc，沿本地 +X 伸出；先以 rise 度扬起，再一路向外下卷 curl 度。
    cup：横截面的槽深（相对宽度）。百合的瓣是窄长、尖头、反卷。"""
    pts = []
    x = z = 0.0
    du = length / nu
    for i in range(nu + 1):
        u = i / nu
        a = math.radians(rise - curl * u ** 3.0)
        pts.append((x, z, a, u))
        x += math.cos(a) * du
        z += math.sin(a) * du
    verts = []
    for side in (1, -1):
        for (px, pz, a, u) in pts:
            nx_, nz_ = -math.sin(a), math.cos(a)
            w = width * max(0.1, math.sin(math.pi * u ** 0.8) ** 0.75) / 2
            for j in range(nv):
                v = j / (nv - 1) * 2 - 1
                off = cup * width * v * v + side * thick / 2
                verts.append((px + nx_ * off, v * w, pz + nz_ * off))
    rows = nu + 1
    half = rows * nv
    idx = lambda s, i, j: s * half + i * nv + j  # noqa: E731
    faces = []
    for i in range(nu):
        for j in range(nv - 1):
            faces.append((idx(0, i, j), idx(0, i + 1, j), idx(0, i + 1, j + 1), idx(0, i, j + 1)))
            faces.append((idx(1, i, j + 1), idx(1, i + 1, j + 1), idx(1, i + 1, j), idx(1, i, j)))
    for i in range(nu):
        for j in (0, nv - 1):
            faces.append((idx(0, i, j), idx(1, i, j), idx(1, i + 1, j), idx(0, i + 1, j)))
    for i in (0, nu):
        for j in range(nv - 1):
            faces.append((idx(0, i, j), idx(0, i, j + 1), idx(1, i, j + 1), idx(1, i, j)))
    return _mesh_obj(name, verts, faces, loc, rot, parent, smooth_deg=50, **style)


def spiral_stair(name, center, r_in, r_out, rise, steps, start_deg, tread_deg, z0=0.0, slab=0.3,
                 grounded=False, parent=None, **style):
    """绕 center 逆时针上升的螺旋梯；每级顶面比上一级高 rise。返回最后一级顶面高度"""
    cx, cy = center
    for k in range(steps):
        top = z0 + rise * (k + 1)
        h = top if grounded else slab
        tube(f"{name}{k}", r_out, r_in, h, (cx, cy, top - h), segments=72, arc=tread_deg * 1.04,
             start=start_deg + tread_deg * k, parent=parent, **style)
    return z0 + rise * steps


def lily(name, loc, stem_h, petal_len, petals=6, stem_r=0.6, open_=1.0, seed=0, skip=(), lean=(0, 0),
         stem_style=None, petal_style=None, stamen=True, disc_r=None, nod=0.0, base_r=0.6):
    """一株百合：茎 + 花托 + 若干瓣。瓣的下半段收成喇叭，到尖上才反卷；open_=0 是花苞，1 全开。
    瓣长、开角、方位都带抖动。nod：花头侧垂的角度。skip：缺掉的瓣（编号）。返回 (组, 花托顶面高度)"""
    rnd = random.Random(seed)
    g = nx.group(name, loc, (lean[0], lean[1], rnd.uniform(0, 360)))
    stem_style = stem_style or dict(a="lilac_pale", b="green", pattern="stripes")
    petal_style = petal_style or dict(a="white", b="pink_pale")
    nx.cylinder(f"{name}_stem", stem_r * 1.25, stem_r, stem_h, (0, 0, 0), segments=20, parent=g, **stem_style)
    head, z0 = g, stem_h
    if nod:
        head = nx.group(f"{name}_head", (0, 0, stem_h), (nod, 0, 0))
        head.parent = g
        z0 = 0.0
    dr = disc_r or stem_r * 2.4
    nx.cylinder(f"{name}_disc", stem_r, dr, dr * 0.55, (0, 0, z0), segments=24, parent=head,
                a="pink_pale", b="gold")
    top = z0 + dr * 0.55
    for i in range(petals):
        if i in skip:
            continue
        az = 360 / petals * i + rnd.uniform(-9, 9)
        L = petal_len * rnd.uniform(0.86, 1.1)
        rise = 84 - 14 * open_ + rnd.uniform(-4, 4)
        curl = 10 + 140 * open_ ** 1.2 + rnd.uniform(-12, 12)
        sty = petal_style if i % 2 == 0 else {**petal_style, "a": petal_style.get("a2", petal_style["a"])}
        sty = {k: v for k, v in sty.items() if k != "a2"}
        r0 = dr * base_r
        a = math.radians(az)
        petal(f"{name}_petal{i}", L, petal_len * rnd.uniform(0.4, 0.46), thick=max(0.14, petal_len * 0.025),
              rise=rise, curl=curl, cup=0.16, loc=(math.cos(a) * r0, math.sin(a) * r0, top - dr * 0.15),
              rot=(0, 0, az), parent=head, **sty)
    if stamen:
        for i in range(5):
            a = math.radians(72 * i + rnd.uniform(-10, 10))
            h = petal_len * rnd.uniform(0.32, 0.42)
            r = dr * 0.45
            tilt = (math.degrees(-math.sin(a)) * 0.2, math.degrees(math.cos(a)) * 0.2, 0)
            s = nx.cylinder(f"{name}_stamen{i}", max(0.08, 0.12 * petal_len / 4), max(0.07, 0.1 * petal_len / 4), h,
                            (math.cos(a) * r, math.sin(a) * r, top), rot=tilt, segments=8, parent=head,
                            a="lilac_pale", b="green", collide=False)
            s["nx_shadow"] = 0
    return g, stem_h + dr * 0.55
