"""变体的平面图：打开 blender/<名字>.blend，用 Workbench 渲俯视平面图（按色板给每块上色）。

  blender -b --factory-startup --python mockup/shallows-04/tools/plan.py -- <名字> [层高 z …] [box=x0,y0,x1,y1]
  # 例：blender -b --factory-startup --python mockup/shallows-04/tools/plan.py -- descent-var-1 0 -6 -12

- 不给 z：一张整体俯视图（`plans/<名字>-plan.png`）。
- 给了 z（米，Blender 坐标）：按 [z−1.5, z+3.0] 切一刀，只画这一层（相机的近/远裁剪面当剖切面），
  像一张建筑平面图（`plans/<名字>-z<z>.png`）。
- `box=` 手动指定取景（不给就按所有网格的包围盒，跳过边长超过 400m 的大地面）。

颜色：`nx_color`（干净低模）＞ `nx_ramp` 的中间一档 ＞ `nx_pal` 的主色 ＞ 灰。看不见的
（`nx_mat=shade` / `collider` / `veil` / `none`）不画；传送物、出生点、到达点、晶体另用小方块标出来
（橙＝传送物、青＝出生点、绿＝到达点、洋红＝晶体），坐标同时打在 stdout 上，方便在地图上标注。
"""
import os
import sys

import bpy
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
OUT = os.path.join(ROOT, "mockup", "shallows-04", "plans")

# 色板（见 docs/blender.md）
PAL = ["#1d1a2b", "#3a3350", "#5c5378", "#82799e", "#a8a1bf", "#cdc8db", "#ece9f2", "#fbf9f7",
       "#6e4f66", "#a8798c", "#d9aab5", "#f3d6d6", "#8fa3c7", "#c3d1e6", "#ead7a0", "#86b5a5"]

HIDDEN = {"shade", "collider", "veil", "none"}
MARKS = {"portal": (1.0, 0.62, 0.25), "spawn": (0.25, 0.85, 1.0),
         "arrive": (0.35, 0.9, 0.45), "entrance": (0.95, 0.35, 0.85)}


def srgb(hexstr):
    h = hexstr.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4) for v in c)


PAL_RGB = [srgb(h) for h in PAL]
GREY = (0.75, 0.74, 0.80)


def color_of(obj):
    u = obj
    while u is not None:
        if u.get("nx_color"):
            try:
                return srgb(str(u["nx_color"]))
            except Exception:
                pass
        if u.get("nx_ramp"):
            try:
                return PAL_RGB[int(str(u["nx_ramp"]).split(",")[1])]
            except Exception:
                pass
        if u.get("nx_pal"):
            try:
                return PAL_RGB[int(str(u["nx_pal"]).split(",")[0])]
            except Exception:
                pass
        u = u.parent
    return GREY


def mat_of(obj):
    u = obj
    while u is not None:
        if u.get("nx_mat"):
            return str(u["nx_mat"])
        u = u.parent
    return "matte"


def visible():
    out = []
    for o in bpy.context.scene.objects:
        if o.type != "MESH" or o.name.startswith("px_") or o.hide_render:
            continue
        if mat_of(o) in HIDDEN:
            continue
        if max(o.dimensions) > 400:  # 接到天边的大地面不参与取景
            continue
        out.append(o)
    return out


def bounds(objs):
    x0 = y0 = 1e9
    x1 = y1 = -1e9
    for o in objs:
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            x0, y0, x1, y1 = min(x0, w.x), min(y0, w.y), max(x1, w.x), max(y1, w.y)
    if x0 > x1:
        return (-20, -20, 20, 20)
    return (x0, y0, x1, y1)


def marks():
    """传送物 / 出生点 / 到达点 / 晶体：在图上放一个小方块"""
    got = {}
    for o in bpy.context.scene.objects:
        t = str(o.get("nx_type") or "")
        if t not in MARKS:
            continue
        got.setdefault(t, []).append(o)
        m = bpy.data.meshes.new(f"mk_{o.name}")
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(o.location.x, o.location.y, o.location.z))
        cube = bpy.context.active_object
        cube.name = f"mk_{o.name}"
        cube.data = m
        cube.color = (*MARKS[t], 1.0)
        cube.display_type = "SOLID"
    return got


def setup(res=(1500, 1500)):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.image_settings.file_format = "PNG"
    sc.render.resolution_percentage = 100
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.film_transparent = False
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "OBJECT"
    sh.show_object_outline = True
    sh.object_outline_color = (0.24, 0.22, 0.34)
    sh.show_shadows = True
    sh.shadow_intensity = 0.2
    sh.show_cavity = True
    sh.cavity_type = "BOTH"
    sh.curvature_ridge_factor = 0.5
    sh.curvature_valley_factor = 0.8
    sh.background_type = "VIEWPORT"
    sh.background_color = (0.94, 0.935, 0.965)
    try:
        sc.display.render_aa = "16"
    except Exception:
        pass
    cam_d = bpy.data.cameras.new("plan_cam")
    cam_d.type = "ORTHO"
    cam = bpy.data.objects.new("plan_cam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    return cam, cam_d


def shoot(cam, cam_d, box, z_top, path, clip=None):
    sc = bpy.context.scene
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    cam_z = z_top + 60.0
    cam.location = (cx, cy, cam_z)
    cam.rotation_euler = (0, 0, 0)  # 朝下（-Z），上方是 +Y（北）
    cam_d.ortho_scale = max(x1 - x0, y1 - y0) * 1.06
    if clip:
        lo, hi = clip  # 只画 z ∈ [lo, hi]
        cam_d.clip_start = cam_z - hi
        cam_d.clip_end = cam_z - lo
    else:
        cam_d.clip_start = 0.1
        cam_d.clip_end = cam_z + 400
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("[plan] render", os.path.basename(path))


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if not argv:
        print("用法：… -- <名字> [层高 z …] [box=x0,y0,x1,y1]")
        return
    name = argv[0]
    zs = []
    box = None
    for a in argv[1:]:
        if a.startswith("box="):
            box = tuple(float(v) for v in a[4:].split(","))
        else:
            zs.append(float(a))
    os.makedirs(OUT, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, "blender", f"{name}.blend"))

    objs = visible()
    for o in objs:
        o.color = (*color_of(o), 1.0)
    got = marks()
    for t, lst in got.items():
        for o in lst:
            print(f"[plan] {t} {o.name}: {o.location.x:.2f},{o.location.y:.2f},{o.location.z:.2f}")

    if box is None:
        box = bounds(objs)
    top = max([(o.matrix_world @ Vector(c)).z for o in objs for c in o.bound_box] or [3])
    cam, cam_d = setup()
    shoot(cam, cam_d, box, top, os.path.join(OUT, f"{name}-plan.png"))
    for z in zs:
        tag = f"{z:g}".replace("-", "m")
        shoot(cam, cam_d, box, top, os.path.join(OUT, f"{name}-z{tag}.png"), clip=(z - 1.5, z + 3.0))
    print(f"[plan] done: {len(objs)} 个网格")


if __name__ == "__main__":
    main()
