"""总图：把各个场景当作浮岛摆成一圈，中间一块圆台。只为查看和对比，不是正式场景。
运行：node scripts/blender.cjs build atlas    网页：?scene=atlas（天空可以加 &sky=<主题> 对比）

- 每个岛有一座桥从圆台修到它原来的出生点；路远，圆台上另有一圈小晶体，走进去直接跳到对应的岛。
- 从岛的边上掉下去，会回到圆台。
- 加一个场景：在 ZONES 里加一行。被收进来的场景脚本要满足：
  内容写在 build(extent) 里，地面用 extent、以 CENTER 为中心（见 idea_shoal.py）；单独运行时照旧。
- 构建时会检查岛与岛有没有叠在一起，叠了就报错，改 ZONES 里的距离。
"""
import importlib.util
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import nx  # noqa: E402

# (脚本名, 名字, 方位角°（从中心看，0＝+X，90＝+Y）, 岛心离中心的距离, 岛的边长)
ZONES = [
    ("idea_shoal", "浅滩", 90, 197, 150),
    ("idea_descent", "下沉", 150, 177, 110),
    ("idea_room", "无墙之屋", 210, 172, 100),
    ("idea_procession", "回廊", 270, 192, 140),
    ("idea_isles", "云阶", 330, 182, 120),
    ("idea_glasshouse", "花房", 30, 172, 100),
]
HUB_R = 14.0
DECK = 0.15  # 中心台与桥的顶面高


def _corners(cx, cy, yaw, half):
    a = math.radians(yaw)
    c, s = math.cos(a), math.sin(a)
    return [(cx + c * x - s * y, cy + s * x + c * y) for x, y in ((-half, -half), (half, -half), (half, half), (-half, half))]


def _overlap(p, q):
    """两个凸四边形是否相交（分离轴）"""
    for poly in (p, q):
        for i in range(4):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % 4]
            nx_, ny_ = y2 - y1, x1 - x2
            pa = [nx_ * x + ny_ * y for x, y in p]
            pb = [nx_ * x + ny_ * y for x, y in q]
            if max(pa) < min(pb) or max(pb) < min(pa):
                return False
    return True


nx.reset()
nx.into("atlas")
nx.sun((-0.4, -0.6, 0.5))
nx.spawn((0, 0, DECK), facing_deg=0)
nx.cylinder("hub", HUB_R, HUB_R, 1.0, (0, 0, DECK - 1.0), segments=72, a="mist", b="lilac_pale", pattern="tiles")
nx.torus("hub_ring", HUB_R - 1.2, 0.18, (0, 0, DECK + 0.02), major_seg=96, minor_seg=6, a="lilac", b="lilac_dark",
         collide=False, shadow=False)

placed = []  # (名字, 四角)
nx.ATLAS = True
for script, label, az, dist, extent in ZONES:
    spec = importlib.util.spec_from_file_location(f"zone_{script}", os.path.join(HERE, f"{script}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cx, cy = getattr(mod, "CENTER", (0, 0))

    a = math.radians(az)
    yaw = az - 90  # 岛的本地 +Y 朝外：从中心走过去，正好对着场景原来的出生朝向
    # 让场景的 CENTER 落在 (cos a, sin a) * dist 上
    rot = Matrix.Rotation(math.radians(yaw), 3, "Z")
    target = Vector((math.cos(a) * dist, math.sin(a) * dist, 0))
    origin = target - rot @ Vector((cx, cy, 0))

    quad = _corners(target.x, target.y, yaw, extent / 2)
    for other, oq in placed:
        if _overlap(quad, oq):
            raise RuntimeError(f"[nx] 岛 {script} 与 {other} 叠在一起了，调大 ZONES 里的距离")
    placed.append((script, quad))

    nx.PREFIX = ""
    nx.into(script)
    zone = nx.group(script, tuple(origin), (0, 0, yaw))
    before = set(bpy.data.objects)
    nx.PREFIX = f"{script}/"
    mod.build(extent)
    nx.PREFIX = ""
    for obj in set(bpy.data.objects) - before:
        if obj.parent is None:
            obj.parent = zone
    bpy.context.view_layer.update()

    # 桥：中心台边缘 → 这个场景的出生点（路标）
    wp = next((o for o in set(bpy.data.objects) - before if o.get("nx_type") == "waypoint"), None)
    goal = wp.matrix_world.translation.copy() if wp else target
    start = Vector((math.cos(a) * (HUB_R - 0.5), math.sin(a) * (HUB_R - 0.5), 0))
    d = Vector((goal.x - start.x, goal.y - start.y, 0))
    mid = start + d / 2
    nx.into(script)
    nx.box(f"bridge_{script}", (3.0, d.length, 0.3), (mid.x, mid.y, DECK - 0.3),
           rot=(0, 0, math.degrees(math.atan2(-d.x, d.y))), a="lilac_pale", b="mist", pattern="tiles")

    # 圆台上的小晶体：走进去就跳到这个岛的出生点
    face = math.degrees(wp.matrix_world.to_euler().z) if wp else yaw
    gz = max(goal.z, DECK)
    url = f"?scene=atlas&pos={goal.x:.1f},{gz:.2f},{-goal.y:.1f}&yaw={face:.0f}"
    b = math.radians(az + 30)
    nx.into("atlas")
    nx.entrance(f"jump_{script}", (math.cos(b) * 8.5, math.sin(b) * 8.5, DECK + 1.6), url, label, size=0.2)
    print(f"[nx] {label} {script}: {url}")

nx.ATLAS = False
nx.save_blend("atlas")
nx.export("atlas")
