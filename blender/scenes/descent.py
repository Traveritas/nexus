"""草案二 · 下沉：一口一圈圈往下走的圆井，越往下颜色越深；头顶悬着几只慢慢转的环。
秩序感 + 不可理解：台阶一丝不苟，却没人说得清它为谁而修。越往下越亮，井底是白的。
路灯与椅子是纸片：有一把椅子背过身去，看过去只是一张空白的纸。
- 四层平台，每层四级 0.3m 的台阶，层与层之间颜色加深一档。
- 第一层：一圈路灯。第二层：一排朝向井心的椅子，其中一把背过身去。
- 井底一汪水，水里立着一扇门，门里什么也没有。
- 井口外一圈高低不一、中间断开的塔；一道螺旋梯从井口升进天里，顶上是晶体（→ GitHub）。
- 出生点背后一盏路灯（E「关灯」→ 家）。
  出入口两个：灯和晶体。
运行：node scripts/blender.cjs build descent
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import nx  # noqa: E402
import prefabs as pf  # noqa: E402
import shapes as sh  # noqa: E402

EXTENT = 400  # 地面边长；拼进总图（atlas.py）时按岛的大小传进来
CENTER = (0, 0)  # 内容的大致中心：地面以它为中心，总图也按它摆放


def build(extent=EXTENT):
    rnd = random.Random(5)

    RIM = 30.0
    STEP_W, LAND_W, DROP = 0.8, 2.6, 0.3
    BASE = -8.0  # 所有环台的底，埋在下面

    nx.into("env")
    nx.sun((-0.35, -0.5, 0.33))
    nx.atmosphere("lattice")
    pf.gate_home("descent", (0, -38, 0), 0)  # 出生点在灯前
    sh.tube("ground", extent / 2, RIM, 1.0, (0, 0, -1.0), segments=96, a="mist", b="lilac_pale", pattern="tiles")

    # ── 环台 ──
    nx.into("terraces")
    STAGES = [("lilac", "lilac_dark"), ("lilac_pale", "lilac"), ("blue_pale", "lilac_pale"), ("mist", "blue_pale")]
    r, top = RIM, 0.0
    landings = []  # (外半径, 内半径, 顶面高)
    for s, (a, b) in enumerate(STAGES):
        for k in range(4):
            top -= DROP
            sh.tube(f"t{s}_step{k}", r, r - STEP_W, top - BASE, (0, 0, BASE), segments=128,
                    a=a, b=b, pattern="bands")
            r -= STEP_W
        sh.tube(f"t{s}_landing", r, r - LAND_W, top - BASE, (0, 0, BASE), segments=128,
                a=a, b=b, pattern="tiles")
        landings.append((r, r - LAND_W, top))
        r -= LAND_W
    FLOOR = top - DROP
    # 环与环正好接上、不重叠（重叠的顶面同高会闪）；井底圆盘边数不同，还是伸进去一点，底面就往下错开 1cm
    nx.cylinder("floor", r + 0.05, r + 0.05, FLOOR - BASE + 0.01, (0, 0, BASE - 0.01), segments=96, a="white", b="mist", pattern="tiles")
    POOL_R = r - 1.6
    nx.cylinder("pool", POOL_R, POOL_R, 0.1, (0, 0, FLOOR - 0.04), segments=96, a="blue", b="blue_pale", pattern="bands")

    # 井底水里立着一扇门，门里什么也没有
    nx.into("pool_door")
    pf.frame("pool_door", (0, -2.6, FLOOR), 0, w=1.7, h=3.0, kind="door", a="mist", b="lilac_pale", pattern="stripes")

    # ── 第一层：一圈纸的路灯，正面朝井心 ──
    nx.into("lamps")
    ro, ri, z1 = landings[0]
    pf.paper_ring("lamp", "lamp_street", (0, 0), (ro + ri) / 2, 9, z=z1, facing="in", start=7)

    # ── 第二层：纸的椅子，正面朝井心；有一把背过身去，只看得见纸的背面 ──
    nx.into("chairs")
    ro, ri, z2 = landings[1]
    rm = (ro + ri) / 2
    for i, deg in enumerate([200, 214, 231, 243, 258, 276, 289, 305, 322]):
        a = math.radians(deg)
        yaw = deg + (90 if i == 5 else -90) + rnd.uniform(-5, 5)
        nx.sprite(f"chair{i}", "chair", (math.cos(a) * rm, math.sin(a) * rm, z2), rot_deg=(0, 0, yaw), face=False,
                  back="pink_pale")

    # ── 第三层：几块低矮的方碑，一块浮着 ──
    nx.into("slabs")
    ro, ri, z3 = landings[2]
    rm = (ro + ri) / 2
    for i, deg in enumerate([30, 74, 150, 190, 260, 335]):
        a = math.radians(deg)
        h = rnd.uniform(1.0, 2.4)
        obj = nx.box(f"slab{i}", (1.2, 0.5, h), (math.cos(a) * rm, math.sin(a) * rm, z3 + (1.4 if i == 3 else 0)),
                     rot=(0, 0, deg + 90), a="mist", b="lilac_pale", pattern="grain")
        if i == 3:
            nx.behave(obj, bob=0.25)
            obj["nx_collide"] = 0

    # ── 头顶的环：不同倾角，绕竖轴慢慢转 ──
    nx.into("rings")
    for i, (R, z, tilt, spin, col) in enumerate([(8.5, 11, 14, 4, "white"), (12.5, 15, -22, -2.5, "mist"),
                                                  (17.0, 21, 35, 1.6, "pink_pale"), (5.0, 8.2, 62, -7, "blue_pale")]):
        t = nx.torus(f"ring{i}", R, 0.32 + R * 0.015, (0, 0, z), rot=(tilt, 0, rnd.uniform(0, 90)), major_seg=128,
                     minor_seg=12, a=col, b="lilac_pale", collide=False)
        nx.behave(t, spin=spin)

    # ── 井口外：高低不一、中间断开的塔 ──
    nx.into("towers")
    for i in range(14):
        a = math.radians(360 / 14 * i + rnd.uniform(-6, 6))
        rr = rnd.uniform(36, 48)
        x, y = math.cos(a) * rr, math.sin(a) * rr
        h = rnd.uniform(8, 30)
        w = rnd.uniform(1.2, 2.2)
        st = dict(a=rnd.choice(["lilac_pale", "mist", "lilac_pale", "pink_pale"]), b="lilac", pattern="bands")
        if i % 3 == 1:
            cut = h * rnd.uniform(0.45, 0.7)
            nx.box(f"tower{i}_lo", (w, w, cut), (x, y, 0), rot=(0, 0, math.degrees(a)), **st)
            nx.box(f"tower{i}_hi", (w, w, h - cut), (x, y, cut + rnd.uniform(1.5, 3.5)), rot=(0, 0, math.degrees(a) + 12), **st)
        else:
            nx.box(f"tower{i}", (w, w, h), (x, y, 0), rot=(0, 0, math.degrees(a)), **st)

    # ── 升进天里的螺旋梯 ──
    nx.into("sky_stair")
    sa = math.radians(130)
    SC = (math.cos(sa) * 34, math.sin(sa) * 34)
    n = 36
    land = pf.stair_spiral("sky_stair", SC, 0, n, r_in=0.9, r_out=2.7, tread=19, start=-90, landing_arc=120)
    nx.entrance("entrance_sky", (land[0], land[1], land[2] + 1.6), "https://github.com/Traveritas", "GITHUB")
    nx.cylinder("sky_axis", 0.5, 0.5, land[2] - 0.3, (SC[0], SC[1], 0), segments=16, a="lilac", b="lilac_dark",
                pattern="stripes")

    # ── 纸片：井口与层间的草，井底的花 ──
    nx.into("paper")
    for i in range(36):
        a = rnd.uniform(0, math.tau)
        rr = rnd.uniform(RIM + 1, RIM + 12)
        nx.sprite(f"grass{i}", [f"grass:{i}", f"grass:{i}", f"flower:{i}", f"bush:{i}"][i % 4], (math.cos(a) * rr, math.sin(a) * rr, 0), shadow=False, back="lilac_pale")
    for i in range(2):
        a = math.radians(40 + 70 * i)
        nx.sprite(f"floor_lily{i}", f"flower:{i + 5}", (math.cos(a) * (POOL_R + 0.8), math.sin(a) * (POOL_R + 0.8), FLOOR))


if __name__ == "__main__":
    nx.reset()
    build()
    nx.save_blend("descent")
    nx.export("descent")
