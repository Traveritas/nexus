"""草案三 · 无墙之屋：一间只被记住了一部分的房间。
建筑的部分（地板、门框、窗框、几块天花板、一角墙、楼梯）是立体的；家具一律是纸片——
像舞台上的布景板，从侧面看只是一张纸。世界负责陌生，现实物负责熟悉。
纸片有两种并存：剪纸画的（灯、电话、杯）和真实贴图渲出来的（木椅、扶手椅、落地钟、盆栽、窗外的树，见 scripts/cutout.cjs）。
- 一扇自己站着的门，半开；晶体在门洞里。
- 一摞错开的板是楼梯，走上半空的一块楼板：纸的椅子、落地灯、电话，头顶天花板上挂着纸的吊灯，晶体在灯下。
- 一面落地的方框，像一面没有镜子的镜子，晶体在框里。
- 一排没有墙的窗；窗外是纸的树。墙上贴着一扇纸的门，打不开。
运行：node scripts/blender.cjs build room
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import nx  # noqa: E402
import prefabs as pf  # noqa: E402

EXTENT = 400  # 地面边长；拼进总图（atlas.py）时按岛的大小传进来
CENTER = (0, 6)  # 内容的大致中心：地面以它为中心，总图也按它摆放


def build(extent=EXTENT):
    rnd = random.Random(23)
    F = 0.3  # 地板高

    nx.into("env")
    nx.sun((0.45, -0.55, 0.5))
    nx.spawn((0, -22, 0), facing_deg=0)
    nx.atmosphere("dye", seed=7)
    pf.return_door("room", (0, -25.5, 0), 0)
    nx.box("ground", (extent, extent, 1.0), (CENTER[0], CENTER[1], -1.0), a="mist", b="lilac_pale", pattern="grain")
    nx.box("floor", (42, 36, F), (0, 6.5, 0), a="pink_pale", b="pink", pattern="bands")
    nx.box("rug", (12, 8, 0.1), (-1, 0, F), a="blue_pale", b="blue", pattern="stripes")

    # ── 门：自己站着，半开；晶体在门洞里 ──
    nx.into("door")
    pf.frame("door", (-0.5, 17, F), 0, w=2.2, h=4.0, depth=0.5, t=0.35, kind="door",
             a="violet", b="violet_deep", pattern="stripes")
    leaf = nx.group("door_hinge", (1.1, 0.25 + 17, F), (0, 0, -68))
    nx.box("door_leaf", (2.2, 0.18, 3.95), (-1.1, 0.09, 0), parent=leaf, a="mist", b="lilac_pale", pattern="tiles")
    nx.box("door_knob", (0.22, 0.4, 0.22), (-1.9, 0.09, 1.9), parent=leaf, a="gold", b="white", pattern="plain")
    nx.portal("portal_door", (-0.5, 17, F + 1.0), "glasshouse", radius=0.6)

    # ── 半空的楼板：板摞成的梯子走上去 ──
    nx.into("loft")
    LX, LY, LZ = -10, 9, 2.7  # 楼板顶面
    nx.box("loft_slab", (9, 7, 0.4), (LX, LY, F + LZ - 0.4), rot=(0, 0, -6), a="white", b="mist", pattern="tiles")
    for i, (x, y) in enumerate([(-13.8, 5.9), (-6.2, 5.9), (-13.8, 12.1), (-6.2, 12.1)]):
        nx.box(f"loft_post{i}", (0.4, 0.4, LZ - 0.4), (x, y, F), rot=(0, 0, -6), a="lilac_pale", b="lilac", pattern="plain")
    for k in range(9):  # 每块 0.3m，错开着往上
        nx.box(f"loft_step{k}", (2.4, 1.6, 0.3 - 0.01 * (k == 8)), (-4.2 - k * 0.15 + rnd.uniform(-0.15, 0.15), 0.6 + k * 0.95, F + k * 0.3),
               rot=(0, 0, rnd.uniform(-10, 10)), a=["white", "mist", "pink_pale", "lilac_pale"][k % 4], b="lilac_pale",
               pattern="bands")
    nx.box("ceiling_loft", (8, 6, 0.4), (LX, LY, F + LZ + 4.2), rot=(1.5, 0, 4), a="white", b="mist", pattern="tiles")
    nx.sprite("loft_pendant", "pendant", (LX, LY, F + LZ + 4.2 - 2.75), face=False, rot_deg=(0, 0, 10), shadow=True)
    nx.portal("portal_loft", (LX, LY, F + LZ + 1.7), "home", at="wake", mode="key", title="关灯", radius=1.0)
    # 楼板上的纸家具
    top = F + LZ
    nx.sprite("loft_chair", "chair_wood@64", (LX - 2.6, LY + 1.8, top), rot_deg=(0, 0, 20), face=False, back="pink_pale")
    nx.sprite("loft_lamp", "lamp_floor", (LX + 3.0, LY + 2.2, top), rot_deg=(0, 0, -15), face=False)
    nx.sprite("loft_phone", "phone", (LX - 3.2, LY - 2.2, top), face=True)
    nx.sprite("loft_cup", "cup", (LX + 2.8, LY - 2.0, top), face=True)

    # ── 落地的方框：晶体在框里 ──
    nx.into("mirror")
    pf.frame("mirror", (10, 6, F), -25, w=2.6, h=3.6, depth=0.4, t=0.4, kind="square", a="white", b="mist", pattern="plain")
    nx.portal("portal_mirror", (10, 6, F + 0.4 + 1.0), "descent", at="bottom", radius=0.7)
    nx.sprite("mirror_chair", "armchair_real@64", (12.5, 3.2, F), rot_deg=(0, 0, -58), face=False, back="pink_pale")

    # ── 没有墙的窗；窗外是纸的树 ──
    nx.into("windows")
    for i, (x, y, yaw, kind) in enumerate([(-12, 22, 0, "window"), (-3, 23.5, -6, "window"), (6, 22.5, 4, "square"),
                                           (15, 19.5, -28, "window")]):
        pf.frame(f"win{i}", (x, y, F + 1.4), yaw, w=4.0, h=5.0, depth=0.3, t=0.28, kind=kind,
                 a="white", b="mist", pattern="plain")
    for i, (x, y) in enumerate([(-15, 29), (-7, 32), (1, 30), (10, 31), (19, 27)]):
        nx.sprite(f"tree{i}", ["tree_island@32", "quiver@32", "tree_island_b@32", "quiver_b@32", "tree_island@32"][i], (x, y, 0), face=True)
    # 纸的帘子（窗贴纸）放在两扇窗前
    nx.sprite("curtain0", "window", (-12, 21.6, F), face=False, back="mist")
    nx.sprite("pot_lily", "plant_pot@40", (-6.5, 20.6, F), face=True)

    # ── 走到桌面那么高的楼梯，顶上一块天花板 ──
    nx.into("stair_up")
    g, (_, ly, lz) = pf.stair_straight("stair_up", (16.5, -3, F), 0, 16, solid=True)
    nx.box("stair_up_land", (3.4, 3.4, 0.3), (16.5, -3 + ly + 1.7, F + lz - 0.3), a="mist", b="lilac_pale", pattern="tiles")
    nx.box("ceiling_stair", (9, 7, 0.4), (16.5, -3 + ly + 1.7, F + lz + 4.2), rot=(0, 0, 9), a="white", b="mist", pattern="tiles")
    nx.sprite("stair_pendant", "pendant", (16.5, -3 + ly + 1.7, F + lz + 4.2 - 2.75), face=False, shadow=True)

    # ── 一角墙，墙上贴着一扇纸的门 ──
    nx.into("walls")
    nx.box("wall_a", (10, 0.6, 7.5), (-15, -7, F), a="lilac_pale", b="lilac", pattern="bands")
    # wall_b 接在 wall_a 后面、踢脚夹在两墙之间且不到 wall_a 的端头：面都不叠在一起（叠了会闪）
    nx.box("wall_b", (0.6, 6.4, 7.5), (-19.7, -3.5, F), a="lilac_pale", b="lilac", pattern="bands")
    nx.box("skirting", (9.39, 0.75, 0.5), (-14.705, -6.7, F), a="lilac", b="lilac_dark", pattern="plain")
    nx.sprite("wall_door", "door", (-14, -6.62, F), face=False, rot_deg=(0, 0, 180), back="lilac_pale")
    nx.sprite("wall_clock", "clock_real@64", (-18.2, -6.2, F), face=False, rot_deg=(0, 0, 180))
    nx.box("ceiling_far", (12, 8, 0.4), (-8, 6, 13.5), rot=(2, 0, -12), a="white", b="mist", pattern="tiles")

    # ── 浮着的板与纸的杯 ──
    nx.into("drift")
    for i in range(6):
        obj = nx.box(f"float_plate{i}", (rnd.uniform(1.6, 2.6), rnd.uniform(2.2, 3.0), 0.3),
                     (rnd.uniform(-6, 8), rnd.uniform(-2, 14), rnd.uniform(7.5, 11.5)),
                     rot=(rnd.uniform(-25, 25), rnd.uniform(-25, 25), rnd.uniform(0, 360)),
                     a=["rose", "lilac", "blue", "gold", "pink", "green"][i], b="mist", pattern="bands", collide=False)
        nx.behave(obj, spin=rnd.uniform(-8, 8), bob=rnd.uniform(0.2, 0.6))
    for i in range(3):
        s = nx.sprite(f"float_cup{i}", "cup", (rnd.uniform(-4, 6), rnd.uniform(0, 12), rnd.uniform(5, 8)), shadow=False)
        nx.behave(s, bob=rnd.uniform(0.3, 0.6))

    # ── 地板外的草 ──
    nx.into("paper")
    pf.paper_scatter("grass", ["grass:{}", "grass:{}", "bush:{}", "flower:{}"], (0, 6), 24, 40, 40, seed=7,
                     avoid=lambda x, y: -22 < x < 22 and -13 < y < 26)


if __name__ == "__main__":
    nx.reset()
    build()
    nx.save_blend("room")
    nx.export("room")
