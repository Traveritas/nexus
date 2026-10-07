"""NEXUS 的 Blender 工具库：场景脚本用它来搭建、标注、导出。

约定全文见 docs/blender.md。这里所有坐标都是 Blender 坐标（Z 朝上，单位米）；
导出后变成 three 的 Y 朝上：Blender (x, y, z) → three (x, z, -y)。
"""
import math
import os

import bpy
from mathutils import Euler, Matrix, Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# 色板编号（与 src/palette.ts 同序）
P = {
    "ink": 0, "violet_deep": 1, "violet": 2, "lilac_dark": 3, "lilac": 4, "lilac_pale": 5,
    "mist": 6, "white": 7,
    "rose_deep": 8, "rose": 9, "pink": 10, "pink_pale": 11,
    "blue": 12, "blue_pale": 13,
    "gold": 14,
    "green": 15,
}

PATTERN = {"grain": 0, "tiles": 1, "bands": 2, "stripes": 3, "plain": 4}

# 拼总图（blender/scenes/atlas.py）时由总图设置：
# ATLAS=True 时，各场景的 spawn 变成路标（nx_type=waypoint，网页不认），sun / sky_sprite 不生效，只用总图自己的；
# PREFIX 加在集合名前，Blender 里按场景分得开。
ATLAS = False
PREFIX = ""


# ── 场景 ──────────────────────────────────────────────

def reset():
    """清空当前文件（包括孤立数据）"""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.objects):
        for d in list(coll):
            coll.remove(d)


def collection(name):
    """新建并返回一个集合，后续 add 的物体放进去（只是 Blender 里的分组，不影响导出）"""
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if c.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(c)
    return c


_current = None


def into(coll_name):
    global _current
    _current = collection(PREFIX + coll_name)


def _link(obj):
    target = _current or bpy.context.scene.collection
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    target.objects.link(obj)
    return obj


def _place(obj, loc, rot_deg, parent):
    obj.location = Vector(loc)
    obj.rotation_euler = Euler([math.radians(a) for a in rot_deg], "XYZ")
    if parent is not None:
        obj.parent = parent
    return _link(obj)


# ── 标注 ──────────────────────────────────────────────

def _pal(v):
    return P[v] if isinstance(v, str) else int(v)


def matte(obj, a="mist", b="lilac_pale", pattern="grain", collide=True, shadow=True, top=None, ramp=None):
    """像素哑光：主色 a、副色 b（色板名或编号），纹样见 PATTERN；
    top：顶面色，朝上的面整片换成它，并沿侧面上沿垂下参差的几格（草皮、积雪、桌布之类）；
    ramp：(暗, 中, 亮) 三色明暗，受光档直接取这三色，可以跨色相（暗偏冷紫、亮偏暖粉/淡金）；给了就不用 a、b"""
    if ramp is not None:
        obj["nx_ramp"] = ",".join(str(_pal(c)) for c in ramp)
    obj["nx_mat"] = "matte"
    obj["nx_pal"] = f"{_pal(a)},{_pal(b)}"
    obj["nx_pattern"] = PATTERN[pattern] if isinstance(pattern, str) else int(pattern)
    if top is not None:
        obj["nx_top"] = _pal(top)
    obj["nx_collide"] = 1 if collide else 0
    obj["nx_shadow"] = 1 if shadow else 0
    return obj


def collider_only(obj):
    """看不见、只挡人"""
    obj["nx_mat"] = "collider"
    obj["nx_collide"] = 1
    obj.display_type = "WIRE"
    return obj


def behave(obj, spin=0.0, bob=0.0, face=None):
    """spin：绕竖轴 度/秒；bob：上下浮动幅度（米）；face：永远正面朝人"""
    if spin:
        obj["nx_spin"] = float(spin)
    if bob:
        obj["nx_bob"] = float(bob)
    if face is not None:
        obj["nx_face"] = 1 if face else 0
    return obj


# ── 几何 ──────────────────────────────────────────────

def _new_mesh_obj(name, op, **kw):
    op(**kw)
    obj = bpy.context.active_object
    obj.name = name
    obj.data.name = name
    return obj


def _smooth(obj, angle_deg=40):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    try:
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(angle_deg))
    except Exception:
        bpy.ops.object.shade_smooth()


def box(name, size, loc=(0, 0, 0), rot=(0, 0, 0), parent=None, base=True, **style):
    """长方体。size=(x 宽, y 深, z 高)；base=True 时 loc 是底面中心"""
    sx, sy, sz = size
    obj = _new_mesh_obj(name, bpy.ops.mesh.primitive_cube_add, size=1)
    obj.data.transform(Matrix.Diagonal((sx, sy, sz, 1)))
    if base:
        obj.data.transform(Matrix.Translation((0, 0, sz / 2)))
    _place(obj, loc, rot, parent)
    return matte(obj, **style)


def cylinder(name, r1, r2, h, loc=(0, 0, 0), rot=(0, 0, 0), segments=28, parent=None, **style):
    """圆台，底面中心在 loc"""
    obj = _new_mesh_obj(name, bpy.ops.mesh.primitive_cone_add, vertices=segments, radius1=r1, radius2=r2, depth=h)
    obj.data.transform(Matrix.Translation((0, 0, h / 2)))
    _place(obj, loc, rot, parent)
    _smooth(obj)
    return matte(obj, **style)


def torus(name, major, minor, loc=(0, 0, 0), rot=(0, 0, 0), major_seg=96, minor_seg=16, parent=None, **style):
    """圆环；默认平躺（环面在 XY 上），立起来用 rot=(90, 0, 0)"""
    obj = _new_mesh_obj(name, bpy.ops.mesh.primitive_torus_add,
                        major_radius=major, minor_radius=minor,
                        major_segments=major_seg, minor_segments=minor_seg)
    _place(obj, loc, rot, parent)
    _smooth(obj, 60)
    return matte(obj, **style)


def plane(name, sx, sy, loc=(0, 0, 0), rot=(0, 0, 0), parent=None, **style):
    obj = _new_mesh_obj(name, bpy.ops.mesh.primitive_plane_add, size=1)
    obj.data.transform(Matrix.Diagonal((sx, sy, 1, 1)))
    _place(obj, loc, rot, parent)
    return matte(obj, **style)


def group(name, loc=(0, 0, 0), rot=(0, 0, 0)):
    """空物体做父级：一组零件一起摆放、旋转"""
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = "PLAIN_AXES"
    return _place(obj, loc, rot, None)


# ── 空物体 ────────────────────────────────────────────

def _empty(name, loc, rot_deg, display="ARROWS", size=0.5):
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = display
    obj.empty_display_size = size
    return _place(obj, loc, rot_deg, None)


def spawn(loc, facing_deg=0):
    """出生点：loc 是脚底；facing_deg 是从 +Y 起绕 Z 逆时针的角度（0 ＝ 朝 +Y）"""
    if ATLAS:
        obj = _empty("waypoint", loc, (0, 0, facing_deg), "SINGLE_ARROW", 1.0)
        obj["nx_type"] = "waypoint"
        return obj
    obj = _empty("spawn", loc, (0, 0, facing_deg), "SINGLE_ARROW", 1.0)
    obj["nx_type"] = "spawn"
    return obj


def entrance(name, loc, url, title="", size=0.32):
    """入口：晶体中心放在 loc，应在可站立地面以上约 1.6m（眼高），且周围能走进去"""
    obj = _empty(name, loc, (0, 0, 0), "SPHERE", size * 2.236)
    obj["nx_type"] = "entrance"
    obj["nx_url"] = url
    obj["nx_title"] = title
    obj["nx_size"] = float(size)
    return obj


def sprite(name, sprite_name, loc, rot_deg=(0, 0, 0), face=True, shadow=True, back="mist"):
    """纸片：loc 是图底边中点；尺寸由图决定（每米 16 像素）"""
    obj = _empty(name, loc, rot_deg, "SINGLE_ARROW", 0.6)
    obj["nx_type"] = "sprite"
    obj["nx_sprite"] = sprite_name
    obj["nx_face"] = 1 if face else 0
    obj["nx_shadow"] = 1 if shadow else 0
    obj["nx_back"] = _pal(back)
    return obj


def sky_sprite(name, sprite_name, direction, width=20):
    """天上的纸片：沿 direction 方向、永远在远处，宽 width 米"""
    if ATLAS:
        return None
    d =Vector(direction).normalized() * 50
    obj = _empty(name, tuple(d), (0, 0, 0), "CIRCLE", 3)
    obj["nx_type"] = "sky"
    obj["nx_sprite"] = sprite_name
    obj["nx_size"] = float(width)
    return obj


def sun(to_sun):
    """太阳：to_sun 是指向太阳的方向"""
    if ATLAS:
        return None
    d =Vector(to_sun).normalized()
    light = bpy.data.lights.new("sun", type="SUN")
    obj = bpy.data.objects.new("sun", light)
    obj.location = d * 30
    obj.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    return _link(obj)


# ── 存档与导出 ─────────────────────────────────────────

def save_blend(name):
    path = os.path.join(ROOT, "blender", f"{name}.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    print("[nx] saved", path)
    return path


def export(name):
    """导出 public/scenes/<name>.glb"""
    out = os.path.join(ROOT, "public", "scenes", f"{name}.glb")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    opts = dict(
        filepath=out,
        export_format="GLB",
        export_extras=True,
        export_apply=True,
        export_yup=True,
        export_lights=True,
        export_cameras=False,
        # 只有现成模型（nx_mat=asset，见 blender/assets.py）带材质；搭出来的白模没有材质，导出时也就没有
        export_materials="EXPORT",
        # 贴图一律存成 WebP：保留透明度（叶子），体积比打包后的 PNG 小得多；three 的 GLTFLoader 直接认
        export_image_format="WEBP",
        export_image_quality=82,
        use_selection=False,
    )
    try:
        bpy.ops.export_scene.gltf(**opts)
    except TypeError as e:
        # 选项名随 Blender 版本变化时，退回最少的选项再试
        print("[nx] export option fallback:", e)
        bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", export_extras=True, export_apply=True)
    print("[nx] exported", out)
    return out


# ── 天空主题 ───────────────────────────────────────────

def atmosphere(sky="blank", seed=None):
    """天空主题：blank 空白 · halo 天环 · plumb 悬锤 · horizon 远碑 · lattice 天格 ·
    dye 洇 · silk 绸 · dawn 溶金 · night 星纸（意图见 docs/sky.md）。一个场景放一个；总图里不生效。
    seed：程序化主题（dye、silk、plumb）按它生成，不给时为 1"""
    if ATLAS:
        return None
    obj = _empty("atmosphere", (0, 0, 8), (0, 0, 0), "CUBE", 1.0)
    obj["nx_type"] = "atmosphere"
    obj["nx_sky"] = sky if seed is None else f"{sky}:{int(seed)}"
    return obj


# ── 世界之间 ───────────────────────────────────────────

def portal(name, loc, to, at="", mode="walk", title="", radius=0.9):
    """传送物：去另一个世界。loc 放在物件的「门洞」中心（大约齐腰高）。
    mode="walk" 走进 radius 米内就走（门、框、窗）；mode="key" 走近按 E（杯、床、灯……），title 是提示文字。
    to 是目标世界（public/scenes/<to>.glb），at 是那边的到达点名字（空 ＝ 那边的出生点）"""
    obj = _empty(name, loc, (0, 0, 0), "SPHERE", radius)
    obj["nx_type"] = "portal"
    obj["nx_to"] = to
    obj["nx_at"] = at
    obj["nx_mode"] = mode
    obj["nx_title"] = title
    obj["nx_radius"] = float(radius)
    return obj


def arrive(name, loc, facing_deg=0):
    """到达点：别的世界传送过来时落在这里。loc 是脚底，facing_deg 同 spawn。别放在传送物的 radius 里"""
    obj = _empty(f"arrive_{name}", loc, (0, 0, facing_deg), "SINGLE_ARROW", 0.8)
    obj["nx_type"] = "arrive"
    obj["nx_name"] = name
    return obj
