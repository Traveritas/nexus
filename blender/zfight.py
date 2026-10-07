"""共面检查：不同物体的两个面贴在同一平面上、朝向相同、又有重叠——网页里这里的材质和轮廓会闪（z-fighting）。

用法：node scripts/blender.cjs zfight <名字>
- 只查看得见的网格（nx_mat 为 collider / none 的不算）；像素哑光只画正面，背靠背的两个面不会闪，不算。
- 两面相距 < 1mm 算共面，重叠面积 > 1cm² 才报；重叠处埋在第三个物体里面（墙底压在地板上之类）看不见，不算。
- 改法：让一边退开或伸出 ≥ 1cm（门套比洞口窄一点、地板别叠在一起……）。
- 有共面时打印每一对（重叠面积、大致位置）并以非零退出。
"""
from collections import defaultdict

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

TOL = 0.001      # 平面距离容差（米）
ANG = 0.9999     # 法线同向（cos）
MIN_AREA = 1e-4  # 重叠面积下限（m²）

dg = bpy.context.evaluated_depsgraph_get()


def faces_of(o):
    bm = bmesh.new()
    bm.from_object(o, dg)
    bm.transform(o.matrix_world)
    bm.normal_update()
    out = []
    for f in bm.faces:
        if f.calc_area() < MIN_AREA:
            continue
        n = f.normal.copy()
        pts = [v.co.copy() for v in f.verts]
        out.append((n, n.dot(pts[0]), pts))
    bm.free()
    return out


def basis(n):
    a = Vector((1, 0, 0)) if abs(n.x) < 0.9 else Vector((0, 1, 0))
    u = n.cross(a).normalized()
    return u, n.cross(u)


def area2(poly):
    return 0.5 * sum(poly[i - 1][0] * poly[i][1] - poly[i][0] * poly[i - 1][1] for i in range(len(poly)))


def ccw(poly):
    return poly if area2(poly) >= 0 else poly[::-1]


def clip(subject, clipper):
    """凸多边形相交（Sutherland–Hodgman），两者都是逆时针"""
    out = subject
    for i in range(len(clipper)):
        if not out:
            break
        ax, ay = clipper[i - 1]
        bx, by = clipper[i]
        side = lambda p: (bx - ax) * (p[1] - ay) - (by - ay) * (p[0] - ax)  # noqa: E731
        inp, out = out, []
        for j in range(len(inp)):
            p, q = inp[j - 1], inp[j]
            sp, sq = side(p), side(q)
            if sq >= 0:
                if sp < 0:
                    t = sp / (sp - sq)
                    out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
                out.append(q)
            elif sp >= 0:
                t = sp / (sp - sq)
                out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
    return out


meshes = [o for o in bpy.data.objects if o.type == "MESH" and o.get("nx_mat", "matte") not in ("collider", "none")]


def solid(o):
    """物体的 BVH 与世界包围盒，用来判断一个点在不在它里面"""
    bm = bmesh.new()
    bm.from_object(o, dg)
    bm.transform(o.matrix_world)
    bm.normal_update()
    lo = Vector([min(v.co[k] for v in bm.verts) for k in range(3)])
    hi = Vector([max(v.co[k] for v in bm.verts) for k in range(3)])
    t = BVHTree.FromBMesh(bm)
    bm.free()
    return t, lo, hi


solids = {o.name: solid(o) for o in meshes}


def buried(p):
    """点在不在某个物体里面（包括这两个物体自己：合并的网格里，别的零件也能把它埋住）"""
    for t, lo, hi in solids.values():
        if not all(lo[k] <= p[k] <= hi[k] for k in range(3)):
            continue
        loc, n, _, _ = t.find_nearest(p)
        if loc is not None and (p - loc).dot(n) < 0:
            return True
    return False


# 按平面分桶：法线与距离取整；距离落在桶边上的，邻桶也查
buckets = defaultdict(list)
for o in meshes:
    for n, d, pts in faces_of(o):
        key = (round(n.x, 2), round(n.y, 2), round(n.z, 2))
        buckets[key + (round(d / TOL),)].append((o.name, n, d, pts))

hits = defaultdict(lambda: [0.0, Vector()])
seen = set()
for key, fs in buckets.items():
    near = fs + buckets.get(key[:3] + (key[3] + 1,), [])
    for i, (oa, na, da, pa) in enumerate(fs):
        u, v = basis(na)
        A = ccw([(p.dot(u), p.dot(v)) for p in pa])
        for j, (ob, nb, db, pb) in enumerate(near):
            if ob == oa or (j < len(fs) and j <= i) or na.dot(nb) < ANG or abs(da - db) > TOL:
                continue
            fid = (id(pa), id(pb))
            if fid in seen:
                continue
            seen.add(fid)
            inter = clip(A, ccw([(p.dot(u), p.dot(v)) for p in pb]))
            if len(inter) < 3:
                continue
            ar = abs(area2(inter))
            per = sum(((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5 for p, q in zip(inter, inter[1:] + inter[:1]))
            if ar < MIN_AREA or 2 * ar / per < 0.002:  # 只是沿边挨着、旋转的浮点误差叠出的细条，不算
                continue
            c2 = (sum(p[0] for p in inter) / len(inter), sum(p[1] for p in inter) / len(inter))
            # 在重叠处取几个点、往外挪 3mm：都埋在别的物体里就看不见
            samples = [c2] + [((c2[0] + p[0] + q[0]) / 3, (c2[1] + p[1] + q[1]) / 3) for p, q in zip(inter, inter[1:] + inter[:1])]
            shown = sum(not buried(u * x + v * y + na * (da + 0.003)) for x, y in samples) / len(samples)
            if shown == 0:
                continue
            ar *= shown
            k = tuple(sorted((oa, ob)))
            h = hits[k]
            h[1] = (h[1] * h[0] + (u * c2[0] + v * c2[1] + na * da) * ar) / (h[0] + ar)
            h[0] += ar

for (a, b), (ar, c) in sorted(hits.items(), key=lambda kv: -kv[1][0]):
    print(f"[nx] 共面 {a} <-> {b}  {ar * 1e4:.0f}cm²  @({c.x:.2f}, {c.y:.2f}, {c.z:.2f})")
print(f"[nx] 查了 {len(meshes)} 个网格，{len(hits)} 对共面")
if hits:
    raise RuntimeError("有共面")
