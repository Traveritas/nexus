"""把一个现成模型渲染成一张真实贴图的剪纸：正面、正交、透明底。
由 scripts/cutout.cjs 调用：
  blender -b --factory-startup --python blender/cutout.py -- <id> <名字> <高度m> <转角°> <每米像素> [<俯仰°> [<第几个变体>]]
输出 public/sprites/<名字>@<每米像素>.png；场景里 nx.sprite(..., "<名字>@<每米像素>", ...)。
"""
import math
import os
import sys

import bpy
from mathutils import Euler, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assets  # noqa: E402
import nx  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
asset_id, name = argv[0], argv[1]
height = float(argv[2])
yaw = float(argv[3]) if len(argv) > 3 else 0.0
ppm = int(argv[4]) if len(argv) > 4 else 64
tilt = float(argv[5]) if len(argv) > 5 else 0.0
part = int(argv[6]) if len(argv) > 6 and argv[6] != "-" else None

nx.reset()
data, h0 = assets._import(asset_id, 2048, part)
obj = bpy.data.objects.new(name, data)
bpy.context.scene.collection.objects.link(obj)
k = height / max(1e-6, h0)
obj.scale = (k, k, k)
obj.rotation_euler = Euler((0, 0, math.radians(yaw)))
bpy.context.view_layer.update()

# 相机沿 +Y 看，向下俯 tilt 度；在相机平面（右 = X、上 = up）上量外框
t = math.radians(tilt)
view = Vector((0, math.cos(t), -math.sin(t)))
up = Vector((0, math.sin(t), math.cos(t)))
corners = [obj.matrix_world @ v.co for v in data.vertices]
x0, x1 = min(c.x for c in corners), max(c.x for c in corners)
u0, u1 = min(c.dot(up) for c in corners), max(c.dot(up) for c in corners)
cx = (x0 + x1) / 2
# 左右对称地留边：纸片的锚点是底边中点
half = max(cx - x0, x1 - cx) + 0.02
w, h = 2 * half, (u1 - u0) + 0.02
# 画面中心：x = cx，up 方向上取外框中点；再沿视线往后退
mid_u = (u0 + u1) / 2 - 0.01
center = Vector((cx, 0, 0)) + up * mid_u

cam_data = bpy.data.cameras.new("cut_cam")
cam_data.type = "ORTHO"
cam_data.ortho_scale = max(w, h)
cam = bpy.data.objects.new("cut_cam", cam_data)
bpy.context.scene.collection.objects.link(cam)
cam.location = center - view * 60
cam.rotation_euler = Euler((math.radians(90 - tilt), 0, 0))
bpy.context.scene.camera = cam
cam_data.clip_end = 200

# 光：左上前方的日光 + 柔和的天光（与网页里的太阳方向大致一致）
sun = bpy.data.lights.new("cut_sun", type="SUN")
sun.energy = 3.2
sun_obj = bpy.data.objects.new("cut_sun", sun)
bpy.context.scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler = Euler((math.radians(50), 0, math.radians(-35)))
world = bpy.data.worlds.new("cut_world")
world.use_nodes = True
bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
bg.inputs["Color"].default_value = (0.82, 0.8, 0.88, 1)
bg.inputs["Strength"].default_value = 0.9
bpy.context.scene.world = world

sc = bpy.context.scene
for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"):
    try:
        sc.render.engine = eng
        break
    except TypeError:
        continue
if sc.render.engine == "CYCLES":
    sc.cycles.samples = 32
sc.render.film_transparent = True
sc.render.resolution_x = max(4, round(w * ppm))
sc.render.resolution_y = max(4, round(h * ppm))
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGBA"
try:
    sc.view_settings.view_transform = "Standard"
except TypeError:
    pass
out = os.path.join(nx.ROOT, "public", "sprites", f"{name}@{ppm}.png")
os.makedirs(os.path.dirname(out), exist_ok=True)
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
print(f"[nx] cutout {out}  {sc.render.resolution_x}x{sc.render.resolution_y}  ({w:.2f}m x {h:.2f}m, {sc.render.engine})")
