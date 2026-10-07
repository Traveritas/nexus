"""现成的模型（Poly Haven，CC0）：导入、清理、标注为 nx_mat=asset。
先取模型：node scripts/fetch-asset.cjs <id>（存到 assets/polyhaven/<id>/）。
网页里它保留自己的底色贴图与颜色，受光、影子、雾与像素哑光一致；像素化、落色板、描边交给管线。
"""
import glob
import math
import os

import bpy
from mathutils import Matrix, Vector

import nx

ASSETS = os.path.join(nx.ROOT, "assets", "polyhaven")


def _base_image(mat):
    """找连到 Principled 底色上的那张图"""
    if not mat or not mat.use_nodes:
        return None, None
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if not bsdf:
        return None, None
    link = next((l for l in mat.node_tree.links if l.to_socket == bsdf.inputs["Base Color"]), None)
    node = link.from_node if link else None
    # 有时中间隔着一个混色 / 色相节点，往上找一层
    while node is not None and node.type != "TEX_IMAGE":
        up = next((l.from_node for l in mat.node_tree.links if l.to_node == node), None)
        node = up
    alpha = next((l for l in mat.node_tree.links if l.to_socket == bsdf.inputs["Alpha"]), None)
    return (node.image if node else None), alpha is not None


def _simplify(mat, res):
    """只留底色贴图（和透明度），其余贴图拆掉；图缩到 res"""
    img, has_alpha = _base_image(mat)
    color = None
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None) if mat.use_nodes else None
    if bsdf and not img:
        color = tuple(bsdf.inputs["Base Color"].default_value)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    for n in list(nodes):
        nodes.remove(n)
    out = nodes.new("ShaderNodeOutputMaterial")
    p = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(p.outputs["BSDF"], out.inputs["Surface"])
    if img:
        if max(img.size) > res:
            k = res / max(img.size)
            img.scale(max(1, int(img.size[0] * k)), max(1, int(img.size[1] * k)))
            # 缩过的图要重新打包，否则导出时用的还是磁盘上 / 包里的原图
            img.pack()
        t = nodes.new("ShaderNodeTexImage")
        t.image = img
        links.new(t.outputs["Color"], p.inputs["Base Color"])
        if has_alpha:
            links.new(t.outputs["Alpha"], p.inputs["Alpha"])
            try:
                mat.blend_method = "CLIP"
            except Exception:
                pass
    elif color:
        p.inputs["Base Color"].default_value = color


_cache = {}  # (asset_id, part, 面数上限) → (网格数据, 原始高度)
MAX_FACES = 3000        # 家具：导入时减到的面数上限（None ＝ 不减；渲剪纸时用 None 保留细节）
MAX_FACES_SMALL = 1200  # 小摆件（高度不到 0.6m）


def asset(name, asset_id, loc, rot=(0, 0, 0), height=None, scale=1.0, tint=0.0, a="mist", b="lilac", smooth=False,
          collide=True, shadow=True, parent=None, res=512, part=None, max_faces=None):
    """放一个 Poly Haven 模型，原点在底面中心。同一个模型只导入一次，之后的都共用网格与贴图（GLB 里也只存一份）。
    height：把整体缩放到这个高度（米），否则用 scale；tint 0..1 把贴图明暗映射到色板 a（亮）/ b（暗）。
    res：贴图缩到的边长（小摆件用 256 省体积）；part：一排并排的变体里只取第几个（见 _keep_part）。"""
    if max_faces is None:
        max_faces = MAX_FACES_SMALL if height is not None and height < 0.6 else MAX_FACES
    key = (asset_id, part, max_faces)
    if key not in _cache or _cache[key][0].name not in bpy.data.meshes:
        _cache[key] = _import(asset_id, res, part, max_faces)
    data, h0 = _cache[key]
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    k = height / max(1e-6, h0) if height else scale
    obj.scale = (k, k, k)
    nx._place(obj, loc, rot, parent)
    obj["nx_mat"] = "asset"
    obj["nx_pal"] = f"{nx._pal(a)},{nx._pal(b)}"
    obj["nx_tint"] = float(tint)
    obj["nx_smooth"] = 1 if smooth else 0
    obj["nx_collide"] = 1 if collide else 0
    obj["nx_shadow"] = 1 if shadow else 0
    return obj


def _keep_part(obj, part, gap=0.1, bin_=0.02):
    """有的模型（花草尤其）是一排几个变体并排放的：按 X 方向的空隙分组，只留第 part 组（从左数，0 起）"""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    xs = sorted(v.co.x for v in bm.verts)
    groups, start, prev = [], xs[0], xs[0]
    for x in xs[1:]:
        if x - prev > gap:
            groups.append((start, prev))
            start = x
        prev = x
    groups.append((start, prev))
    lo, hi = groups[min(part, len(groups) - 1)]
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not (lo - bin_ <= v.co.x <= hi + bin_)], context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()
    print(f"[nx] {obj.name}: {len(groups)} 组，留第 {min(part, len(groups) - 1)} 组")


def _import(asset_id, res, part=None, max_faces=MAX_FACES):
    """导入、合成一块网格、原点放到底面中心；返回 (网格数据, 高度)，导入用的临时物体删掉。
    part：只留并排变体里的第几个（见 _keep_part）"""
    files = glob.glob(os.path.join(ASSETS, asset_id, "*.gltf"))
    if not files:
        raise FileNotFoundError(f"[nx] 没有 {asset_id}，先运行 node scripts/fetch-asset.cjs {asset_id}")
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=files[0])
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    # 烘进世界变换、去掉层级
    bpy.context.view_layer.update()
    for o in meshes:
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
    for o in new:
        if o.type != "MESH":
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if part is not None:
        _keep_part(obj, part)
    # 减面：像素化之后看不出几万个面的细节，场景文件却会大很多
    faces = len(obj.data.polygons)
    if max_faces and faces > max_faces:
        mod = obj.modifiers.new("decimate", "DECIMATE")
        mod.ratio = max_faces / faces
        bpy.ops.object.modifier_apply(modifier=mod.name)
        print(f"[nx] {asset_id}: {faces} → {len(obj.data.polygons)} 面")
    data = obj.data
    data.name = f"asset_{asset_id}"

    for slot in obj.material_slots:
        if slot.material:
            _simplify(slot.material, res)

    # 原点：底面中心
    vs = [v.co for v in data.vertices]
    lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
    hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
    data.transform(Matrix.Translation((-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z)))
    # 材质挂在网格数据上，临时物体删掉后共用的网格照样带着材质
    for i, slot in enumerate(obj.material_slots):
        if slot.link == "OBJECT":
            data.materials[i] = slot.material
    bpy.data.objects.remove(obj, do_unlink=True)
    return data, hi.z - lo.z
