"""浅梦样板 · 白模：layouts/*.json → scenes/*.blend、glb/*.glb、renders/*.png

在仓库根用 Blender 无界面跑（一般经 tools/build.cjs）：
  blender -b --factory-startup --python mockup/shallows-01/tools/build_scenes.py -- arcade
  blender -b --factory-startup --python mockup/shallows-01/tools/build_scenes.py -- all

做法：JSON 里的体块用仓库自己的 blender/nx.py 搭（属性 nx_* 照写，GLB 将来能直接丢进游戏），
再用 Workbench 渲白模——按 style 给每块一个很淡的视口色，加对象轮廓、腔隙、软影，
所以平面和体量分得开，仍然是白模。渲染用的纸片替身板在导出 GLB 之后才加，不进 GLB。
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
MOCK = os.environ.get("MOCK_DIR") or os.path.dirname(HERE)  # 可指向别的样板文件夹（如 mockup/home-01）
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "blender"))
import nx  # noqa: E402
import prefabs as pf  # noqa: E402

LAYOUTS = os.path.join(MOCK, "resolved")  # 由 tools/expand.cjs 从 layouts/ 展开而来
SCENES = os.path.join(MOCK, "scenes")
GLB = os.path.join(MOCK, "glb")
RENDERS = os.path.join(MOCK, "renders")

# style → (色板 a,b,pattern) 进 GLB；白模视口色 只给渲染
STYLE = {
    "deck": (("mist", "lilac_pale", "tiles"), (0.930, 0.918, 0.958)),
    "stair": (("mist", "lilac_pale", "tiles"), (0.885, 0.868, 0.922)),
    "wall": (("white", "mist", "bands"), (0.845, 0.828, 0.890)),
    "mass": (("lilac_pale", "lilac", "bands"), (0.700, 0.672, 0.782)),
    "frame": (("lilac", "lilac_dark", "plain"), (0.545, 0.510, 0.640)),
    "rail": (("white", "mist", "plain"), (0.980, 0.976, 0.982)),
    "water": (("blue_pale", "blue", "bands"), (0.800, 0.848, 0.920)),
    "glass": (("blue_pale", "white", "plain"), (0.888, 0.915, 0.950)),
    "plant": (("green", "mist", "grain"), (0.640, 0.792, 0.718)),
    "prop": (("pink", "rose", "plain"), (0.878, 0.722, 0.760)),
    "void": (("ink", "violet_deep", "plain"), (0.150, 0.140, 0.250)),
}
DEFAULT_STYLE = "deck"

# 纸片家族 → 渲染替身板的（宽, 高），只为白模里看得见
PROXY = {"tree": (2.4, 6.0), "cloud": (5.0, 4.0), "star": (0.8, 0.8),
         "grass": (1.2, 1.2), "bush": (1.8, 1.8), "flower": (1.6, 2.6)}
DEFAULT_PROXY = (1.2, 1.6)


def v3(at, z=0.0):
    a = list(at or (0, 0))
    return (float(a[0]), float(a[1]), float(a[2]) if len(a) > 2 else float(z))


def style_of(p):
    return STYLE.get(p.get("style", DEFAULT_STYLE), STYLE[DEFAULT_STYLE])


# ── 搭 ────────────────────────────────────────────────

def mk_prim(p):
    kind = p["kind"]
    st, _ = style_of(p)
    a, b, pattern = st
    kw = dict(a=a, b=b, pattern=pattern,
              collide=bool(p.get("collide", True)),
              shadow=bool(p.get("shadow", True)))
    loc = v3(p.get("at"))
    # rx / ry：box 绕 X / Y 轴倾斜（度，Euler XYZ）；地图仍只按 rot 画俯视轮廓
    rot = (float(p.get("rx", 0.0)), float(p.get("ry", 0.0)), float(p.get("rot", 0.0)))
    name = p["name"]
    if kind == "box":
        size = list(p.get("size", [1, 1]))
        sx, sy = float(size[0]), float(size[1])
        sz = float(size[2]) if len(size) > 2 else float(p.get("h", 0.3))
        obj = nx.box(name, (sx, sy, sz), loc, rot=rot, **kw)
    elif kind == "cylinder":
        obj = nx.cylinder(name, float(p.get("r", 1)), float(p.get("r2", p.get("r", 1))),
                          float(p.get("h", 1)), loc, rot=rot, segments=int(p.get("segments", 24)), **kw)
    elif kind == "torus":
        rot = (90.0, 0.0, float(p.get("rot", 0.0))) if p.get("tilt") == "stand" else rot
        obj = nx.torus(name, float(p.get("major", 3)), float(p.get("minor", 0.2)), loc, rot=rot,
                       major_seg=int(p.get("segments", 64)), minor_seg=10, **kw)
    elif kind == "plane":
        size = list(p.get("size", [2, 2]))
        obj = nx.plane(name, float(size[0]), float(size[1]), loc, rot=rot, **kw)
    elif kind == "sprite":
        obj = nx.sprite(name, p["sprite"], loc, rot_deg=rot,
                        face=bool(p.get("face", True)), shadow=bool(p.get("shadow", False)),
                        back=p.get("back", "mist"))
    else:
        raise ValueError(f"未知 kind：{kind}（{name}）")
    if p.get("spin") or p.get("bob"):
        nx.behave(obj, spin=float(p.get("spin", 0)), bob=float(p.get("bob", 0)))
    return obj


def mk_portal(po):
    kind = po.get("kind", "world")
    loc = v3(po.get("at"))
    if kind == "site":
        return nx.entrance(po["name"], loc, po.get("url", ""), po.get("title", ""),
                           size=float(po.get("size", 0.32)))
    if kind == "dead":
        return None  # 只进不出的死胡同口：只是地图上的记号，Blender 里不生成东西
    to = po.get("to", "")
    mode = po.get("mode", "key")
    nx.portal(po["name"], loc, to, at=po.get("at_node", ""), mode=mode,
              title=po.get("title", ""), radius=float(po.get("radius", 0.9)))
    # 走进去的洞口里铺一层膜（颜色是要去的世界那一套；表里没有就跳过）
    if mode == "walk" and to in pf.VEIL:
        a, b = pf.VEIL[to]
        nx.veil(f"{po['name']}_veil", float(po.get("veil_w", 1.8)), float(po.get("veil_h", 2.6)),
                (loc[0], loc[1], loc[2]), float(po.get("rot", 0)), a=a, b=b)
    # 来回成对：去 B 的东西跟前，就是从 B 回来落脚的地方（背对着它）
    if po.get("pair", kind == "world") and to:
        yaw = math.radians(float(po.get("rot", 0)))
        d = float(po.get("land", 2.0))
        nx.arrive(to, (loc[0] - math.sin(yaw) * d, loc[1] + math.cos(yaw) * d, loc[2] - 1.6),
                  facing_deg=float(po.get("rot", 0)))


def build_world(data):
    nx.reset()
    nx.into("env")
    nx.sun(tuple(data.get("sun", (0.35, -0.5, 0.72))))
    nx.atmosphere(data.get("sky", "blank"))

    g = data.get("ground", {})
    ext = float(data.get("extent", 200))
    if data.get("slab", True):
        ground = nx.box("ground", (ext, ext, 1.0), (0, 0, -1.0),
                        a=g.get("a", "mist"), b=g.get("b", "lilac_pale"), pattern=g.get("pattern", "grain"))
        ground.color = (0.945, 0.938, 0.968, 1.0)
    # slab=false：不铺整块底板，地面完全由 prims 自己搭（下挖的井、悬空的岛用它）

    nx.into("world")
    objs = []
    for p in data.get("prims", []):
        objs.append((p, mk_prim(p)))
    for po in data.get("portals", []):
        mk_portal(po)

    if data.get("spawn"):
        s = data["spawn"]
        nx.spawn(v3(s["at"]), facing_deg=float(s.get("face", 0.0)))
    for ar in data.get("arrives", []):
        nx.arrive(ar["name"], v3(ar["at"]), facing_deg=float(ar.get("face", 0.0)))

    # 白模视口色
    for p, obj in objs:
        _, col = style_of(p)
        obj.color = (col[0], col[1], col[2], 1.0)
    return data, objs


# ── 渲白模 ────────────────────────────────────────────

def add_sprite_proxies(data):
    """纸片在 Workbench 里画不出来，渲之前给每张立一块薄板（不进 GLB）"""
    nx.into("proxy")
    for p in data.get("prims", []):
        if p["kind"] != "sprite":
            continue
        fam = p["sprite"].split("@")[0].split(":")[0].split(".")[0]
        w, h = PROXY.get(fam, DEFAULT_PROXY)
        obj = nx.box(f"px_{p['name']}", (w, 0.12, h), v3(p.get("at")), rot=(0, 0, float(p.get("rot", 0))),
                     a="green", b="mist", pattern="grain", collide=False, shadow=False)
        col = STYLE["plant"][1]
        obj.color = (col[0], col[1], col[2], 1.0)


def setup_render(light="STUDIO"):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.image_settings.file_format = "PNG"
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sh = sc.display.shading
    sh.light = light
    sh.color_type = "OBJECT"
    sh.show_object_outline = True
    sh.object_outline_color = (0.27, 0.25, 0.37)
    sh.show_shadows = True
    sh.shadow_intensity = 0.28
    sh.show_cavity = True
    sh.cavity_type = "BOTH"
    sh.curvature_ridge_factor = 0.55
    sh.curvature_valley_factor = 0.9
    sh.background_type = "VIEWPORT"
    sh.background_color = (0.947, 0.941, 0.968)
    try:
        sc.display.render_aa = "16"
    except Exception:
        pass
    cam_d = bpy.data.cameras.new("cam")
    cam = bpy.data.objects.new("cam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    return cam, cam_d


def shoot(cam, cam_d, at, look, path, res=(1600, 900), fov=55.0, ortho=None):
    sc = bpy.context.scene
    cam.location = Vector(at)
    d = (Vector(look) - Vector(at))
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    if ortho:
        cam_d.type = "ORTHO"
        cam_d.ortho_scale = float(ortho)
    else:
        cam_d.type = "PERSP"
        cam_d.angle = math.radians(float(fov))
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("[mock] render", os.path.basename(path))


def bbox_of(data):
    xs, ys = [], []
    for p in data.get("prims", []):
        if p["kind"] == "sprite":
            continue
        at = v3(p.get("at"))
        r = 1.0
        if p["kind"] == "box":
            s = list(p.get("size", [1, 1]))
            r = 0.5 * math.hypot(float(s[0]), float(s[1]))
        elif p["kind"] == "cylinder":
            r = float(p.get("r", 1))
        elif p["kind"] == "torus":
            r = float(p.get("major", 3)) + float(p.get("minor", 0.2))
        elif p["kind"] == "plane":
            s = list(p.get("size", [2, 2]))
            r = 0.5 * math.hypot(float(s[0]), float(s[1]))
        xs += [at[0] - r, at[0] + r]
        ys += [at[1] - r, at[1] + r]
    if not xs:
        return (-10, -10, 10, 10)
    return (min(xs), min(ys), max(xs), max(ys))


def render_world(data):
    # shade: 白模的受光，默认 STUDIO；头顶有大片东西（云底、天花）时用 FLAT，不然底面全黑
    cam, cam_d = setup_render(data.get("shade", "STUDIO"))
    x0, y0, x1, y1 = bbox_of(data)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    span = max(x1 - x0, y1 - y0)
    top = max([v3(p.get("at"))[2] + float(p.get("h", 3)) for p in data.get("prims", [])
               if p["kind"] in ("box", "cylinder")] or [3])
    # 平面（正俯视，白模蓝图）
    shoot(cam, cam_d, (cx, cy, top + span + 20), (cx, cy, 0),
          os.path.join(RENDERS, f"{data['id']}-plan.png"), res=(1500, 1500), ortho=span * 1.12)
    # 透视机位：JSON 里给的，没有就给一个俯瞰 + 一个出生点视角
    views = data.get("views") or []
    if not views:
        sp = data.get("spawn", {}).get("at", [cx, cy - span / 2, 0])
        views = [
            {"name": "bird", "at": [cx + span * 0.55, cy - span * 0.75, span * 0.62],
             "look": [cx, cy, 2.0], "fov": 52},
            {"name": "eye", "at": [sp[0], sp[1], sp[2] + 1.75], "look": [cx, cy, 2.0], "fov": 66},
        ]
    for v in views:
        shoot(cam, cam_d, v["at"], v["look"], os.path.join(RENDERS, f"{data['id']}-{v['name']}.png"),
              res=tuple(v.get("res", (1600, 900))), fov=v.get("fov", 55.0))


# ── 入口 ──────────────────────────────────────────────

def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    which = argv[0] if argv else "all"
    os.makedirs(SCENES, exist_ok=True)
    os.makedirs(GLB, exist_ok=True)
    os.makedirs(RENDERS, exist_ok=True)
    ids = sorted(f[:-5] for f in os.listdir(LAYOUTS) if f.endswith(".json"))
    if which != "all":
        ids = [w for w in which.split(",") if w in ids]
    for wid in ids:
        with open(os.path.join(LAYOUTS, f"{wid}.json"), encoding="utf-8") as f:
            data = json.load(f)
        data["id"] = wid  # 以文件名为准
        print(f"[mock] build {wid} · {data.get('title', '')}")
        data, _ = build_world(data)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(SCENES, f"{wid}.blend"))
        print("[mock] saved", os.path.join(SCENES, f"{wid}.blend"))
        bpy.ops.export_scene.gltf(filepath=os.path.join(GLB, f"{wid}.glb"), export_format="GLB",
                                  export_extras=True, export_apply=True, export_yup=True,
                                  export_lights=True, export_cameras=False, export_materials="EXPORT")
        print("[mock] exported", os.path.join(GLB, f"{wid}.glb"))
        add_sprite_proxies(data)
        render_world(data)
    print(f"[mock] done: {len(ids)} world(s)")


if __name__ == "__main__":
    main()
