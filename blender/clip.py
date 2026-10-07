"""穿模检查：每件家具（furniture.py 搭的，父级带 nx_piece）和场景里其他物体有没有三角形相交。

用法：node scripts/blender.cjs clip <名字> [名字前缀 …]
- 额外的前缀把场景脚本里直接搭的东西也当成「一件」来查，如 `bed_ wardrobe`（同一前缀的零件之间不互查）。
- 只是贴着面不算：查之前把家具往里缩 3mm。地面、地板、地毯、门垫不算（家具本来就立在上面）。
- 有穿模时打印每一对并以非零退出。
"""
import sys

import bmesh
import bpy
from mathutils.bvhtree import BVHTree

SKIP = ("ground", "floor_", "rug_", "doormat")
prefixes = tuple(sys.argv[sys.argv.index("--") + 1:]) if "--" in sys.argv else ()


def root(o):
    while o.parent:
        o = o.parent
    return o


def piece_of(o):
    r = root(o)
    if r.get("nx_piece"):
        return r.name
    for p in prefixes:
        if o.name.startswith(p):
            return p
    return None


dg = bpy.context.evaluated_depsgraph_get()


def tree(o, shrink=0.0):
    bm = bmesh.new()
    bm.from_object(o, dg)
    bm.transform(o.matrix_world)
    if shrink:
        bm.normal_update()
        for v in bm.verts:
            v.co -= v.normal * shrink
    t = BVHTree.FromBMesh(bm)
    bm.free()
    return t


meshes = [o for o in bpy.data.objects if o.type == "MESH" and o.get("nx_mat") != "none" and not o.name.startswith(SKIP)]
trees = {o.name: tree(o) for o in meshes}
found = set()
checked = 0
for f in meshes:
    pf = piece_of(f)
    if pf is None:
        continue
    checked += 1
    tf = tree(f, 0.003)
    for o in meshes:
        po = piece_of(o) or o.name
        if po == pf:
            continue
        key = tuple(sorted((pf, po)))
        if key not in found and tf.overlap(trees[o.name]):
            found.add(key)
            print(f"[nx] 穿模 {pf} <-> {o.name}")
print(f"[nx] 查了 {checked} 个家具网格，{len(found)} 处穿模")
if found:
    raise RuntimeError("有穿模")
