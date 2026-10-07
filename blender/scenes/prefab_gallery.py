"""预制件陈列：所有预制件与纸片各摆一份，挑选、比较用。
运行：node scripts/blender.cjs build prefab_gallery   网页：?scene=prefab_gallery
从出生点往前（+Y）：纸片一排 → 花之装置一排 → 框一排与一条渐变的框列 → 阶 / 环 / 塔 / 台 / 器
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import nx  # noqa: E402
import prefabs as pf  # noqa: E402

PAPER = ["lamp_street", "lamp_floor", "pendant", "chair", "window", "door", "cup", "phone",
         "lily", "puff", "cloud", "tree", "sparkle", "reed", "flower"]
EXTENT = 200


def build(extent=EXTENT):
    nx.into("env")
    nx.sun((0.4, -0.6, 0.55))
    nx.spawn((0, -14, 0), facing_deg=0)
    nx.box("ground", (extent, extent, 1.0), (0, 30, -1.0), a="mist", b="lilac_pale", pattern="tiles")

    # 纸片：一字排开，正面朝出生点
    nx.into("paper")
    x = -30.0
    for name in PAPER:
        w = {"cloud": 8, "tree": 3, "window": 2.5, "lily": 2, "lamp_street": 1.5, "lamp_floor": 1.4}.get(name, 1.4)
        nx.sprite(f"show_{name}", name, (x + w / 2, -2, 0), face=False, shadow=True, back="mist")
        x += w + 1.6
    # 吊灯要挂起来看
    nx.sprite("show_pendant_hung", "pendant", (x + 1, -2, 2.4), face=False, shadow=True)

    # 花之装置
    nx.into("bloom")
    for i, kind in enumerate(["rosette", "lotus", "blade", "halo", "drift"]):
        pf.bloom(f"bloom_{kind}", (-28 + i * 14, 14, 0), kind=kind, size=3.6, seed=10 + i)

    # 框
    nx.into("frame")
    for i, kind in enumerate(["door", "window", "square", "arch"]):
        pf.frame(f"frame_{kind}", (-24 + i * 7, 28, 0), 0, kind=kind)
    pf.procession("proc", (10, 26, 0), (30, 46, 0), 9, roll_step=6, seed=2)

    # 阶
    nx.into("stair")
    pf.stair_straight("stair_a", (-32, 40, 0), 0, 12)
    land = pf.stair_spiral("stair_b", (-20, 46), 0, 20)
    nx.entrance("gallery_spiral", (land[0], land[1], land[2] + 1.6), "", "螺旋梯顶")
    pf.steps_between("stair_c", (-12, 40, 0.3), (-4, 52, 3.0), seed=3)

    # 环
    nx.into("ring")
    pf.halo("ring_halo", (6, 62, 0.4), 4.0)
    pf.orrery("ring_orrery", (22, 66, 9), seed=4)
    pf.arch_ring("ring_arch", (-12, 66, 0), 0, 5.0)

    # 碑、塔、板
    nx.into("tower")
    pf.monolith("mono", (-30, 62, 0), 20)
    pf.tower_broken("tower", (-38, 70, 0), 16, seed=5)
    pf.plate_stack("stack", (-26, 72, 0), n=9, seed=6)

    # 台与器
    nx.into("platform")
    pf.island("isle", (34, 30, 4), 4.5, seed=7)
    pf.pad("pad", (40, 16, 0), 2.6, seed=8)
    pf.plinth("plinth", (40, 6, 0), 4, 3)
    _, inside = pf.vessel("cup_lying", (-8, 84, 0), 200)
    nx.entrance("gallery_cup", (inside[0], inside[1], inside[2] + 1.6), "", "杯里")
    pf.vessel("cup_standing", (6, 84, 0), lying=False, R=1.6, length=3.0)


if __name__ == "__main__":
    nx.reset()
    build()
    nx.save_blend("prefab_gallery")
    nx.export("prefab_gallery")
