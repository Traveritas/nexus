"""草案一 · 浅滩：一片没过脚踝的水，水上立着以花为隐喻的装置。
不再模仿真的花：花瓣是平的、尖头的板，围成圈、叠成层、浮在半空。
- 中央的花台：一根柱、一面圆台，螺旋梯绕柱而上；一圈花瓣板浮在台外，被一只细环托着。
- 一片花瓣板落在水上，成了一座桥。
- 横躺的水杯（浅滩自己的样子），洒出来的水边一瓶花（E「凑近」→ 花房）。
- 浮叶上一圈未开的「刃」。水里立着一扇斜着的门，门里什么也没有。
- 出生的圆叶上一盏路灯（E「关灯」→ 家）。出入口两个：灯和花瓶，从哪儿去的，回来就落在哪儿。
- 远处：立在水里的花形门（halo）、比塔还高的刃、断开的塔。
- 纸片：剪纸百合、香蒲、蒲公英、落在水上的云。
运行：node scripts/blender.cjs build shoal
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
CENTER = (0, 5)  # 内容的大致中心：地面以它为中心，总图也按它摆放


def build(extent=EXTENT):
    rnd = random.Random(11)

    # ── 环境：水面就是地面 ──
    nx.into("env")
    nx.sun((0.55, -0.6, 0.42))
    nx.atmosphere("silk", seed=4)
    nx.box("water", (extent, extent, 1.0), (CENTER[0], CENTER[1], -1.0), a="blue_pale", b="mist", pattern="bands")
    pf.pad("pad_spawn", (0, -16, 0), 3.2, notch=40, start=110, seed=1)
    pf.gate_home("shoal", (0, -18, 0.2), 0)  # 出生点在灯前

    # ── 中央的花台 ──
    nx.into("bloom_tower")
    C = (0, 6)
    TOP = 7.5
    nx.cylinder("tower_column", 1.25, 1.0, TOP - 0.4, (C[0], C[1], 0), segments=24, a="lilac_pale", b="lilac",
                pattern="stripes")
    nx.cylinder("tower_deck", 2.7, 2.7, 0.4, (C[0], C[1], TOP - 0.4), segments=40, a="white", b="pink_pale",
                pattern="tiles")
    steps = int(round(TOP / 0.3)) - 1
    tread = 14.5
    arrive = 250  # 梯子到达的方位
    sh.spiral_stair("tower_step", C, 2.85, 4.3, 0.3, steps, arrive - tread * steps, tread, a="mist", b="lilac_pale",
                    pattern="plain")
    pf.pad("tower_pad", (C[0], C[1], 0), 6.4, h=0.15, notch=30, start=arrive + 200, seed=2,
           a="lilac_pale", b="green")
    # 花瓣板浮在台外，一只细环托着
    pf.bloom("tower_bloom", (C[0], C[1], TOP - 1.3), kind="rosette", size=7.5, seed=3, yaw=0, petals=9, gap=5.2,
             open_deg=38, axis=False)
    pf.halo("tower_ring", (C[0], C[1], TOP - 0.2), 5.2, minor=0.22)
    pf.bloom("tower_drift", (C[0], C[1], 1.0), kind="drift", size=4.5, seed=4, petals=7)

    # 落在水上的一片，当桥
    nx.into("fallen_petal")
    pf.plate("fallen_petal", 8.5, 2.8, thick=0.25, loc=(-9.5, -3, 0.12), rot=(0, 0, 28), a="pink_pale", b="pink")

    # ── 横躺的水杯，入口在杯里 ──
    nx.into("glass")
    pf.vessel("glass", (12, 1, 0), yaw=148)
    sh.tube("glass_spill", 4.5, 0, 0.08, (9.5, -2.5, 0), segments=40, a="blue", b="blue_pale", pattern="plain")
    # 杯子是浅滩自己的；洒出来的水边一瓶花 → 花房
    pf.gate_vase("shoal", (8.6, -4.6, 0.08), 145)

    # ── 浮叶上的晶体，四周一圈未开的刃 ──
    nx.into("bud_ring")
    B = (-12, 14)
    pf.pad("bud_pad", (B[0], B[1], 0), 5.0, h=0.3, notch=25, start=-40, seed=5, a="green", b="lilac_pale")
    for i in range(7):
        a = math.radians(360 / 7 * i + 10)
        pf.bloom(f"bud{i}", (B[0] + math.cos(a) * 3.9, B[1] + math.sin(a) * 3.9, 0.3), kind="blade",
                 size=rnd.uniform(1.8, 3.0), seed=40 + i, petals=rnd.choice([3, 4, 5]),
                 styles=[dict(a="pink_pale", b="pink"), dict(a="pink", b="rose"), dict(a="white", b="pink_pale")])

    # ── 踏石 ──
    nx.into("stones")

    def stones(a, b, n, r=(0.7, 1.1), seed=0):
        rr = random.Random(seed)
        for i in range(1, n):
            t = i / n
            x = a[0] + (b[0] - a[0]) * t + rr.uniform(-0.6, 0.6)
            y = a[1] + (b[1] - a[1]) * t + rr.uniform(-0.6, 0.6)
            nx.cylinder(f"stone_{seed}_{i}", rr.uniform(*r), rr.uniform(*r), 0.18 + 0.02 * (i % 2), (x, y, 0), segments=18,
                        a="mist", b="lilac_pale", pattern="plain")

    stones((0, -13), (C[0], C[1] - 6.6), 7, seed=1)
    stones((2, -14), (9, -3), 7, seed=2)
    stones((-2, -13), (-8, -6), 4, seed=3)
    stones((-11, 1), (B[0] + 2, B[1] - 4.5), 4, seed=4)

    # ── 水里一扇斜着的门，门里什么也没有 ──
    nx.into("doors")
    pf.frame("door_b", (6.5, -9, 0), -24, kind="door", roll=9, a="violet", b="violet_deep", pattern="stripes")

    # ── 远处 ──
    nx.into("horizon")
    for i, (x, y, s) in enumerate([(-48, 52, 8), (40, 62, 10)]):
        yaw = math.degrees(math.atan2(-x, y)) + 180  # 正面朝中心
        pf.bloom(f"far_halo{i}", (x, y, 0), kind="halo", size=s, seed=60 + i, yaw=yaw, petals=11,
                 styles=[dict(a="mist", b="lilac_pale"), dict(a="pink_pale", b="mist")])
    for i, (x, y, s) in enumerate([(-30, 72, 15), (16, 78, 19), (58, 36, 12), (-64, 22, 10)]):
        pf.bloom(f"far_blade{i}", (x, y, 0), kind="blade", size=s, seed=70 + i, petals=4,
                 styles=[dict(a="lilac_pale", b="mist"), dict(a="mist", b="pink_pale")])
    pf.tower_broken("far_tower0", (-8, 82, 0), 26, w=2.4, pieces=3, seed=80)
    pf.tower_broken("far_tower1", (66, 66, 0), 18, w=2.0, pieces=2, seed=81)

    # ── 纸片 ──
    nx.into("paper")

    def near_things(x, y):
        return (math.hypot(x - C[0], y - C[1]) < 7.5 or math.hypot(x - 12, y - 1) < 7
                or math.hypot(x - B[0], y - B[1]) < 6 or math.hypot(x, y + 16) < 4.5)

    pf.paper_scatter("reed", ["grass.reed:{}"], (0, 0), 12, 30, 10, seed=90, avoid=near_things)
    pf.paper_scatter("lily", ["flower:{}"], (0, 0), 6, 22, 9, seed=91, avoid=near_things, shadow=True)
    pf.paper_scatter("puff", ["flower.puff:{}"], (0, -8), 3, 12, 8, seed=92, avoid=near_things)
    for i, (x, y, yaw) in enumerate([(-26, 30, 20), (24, 38, -30), (-34, -6, 70)]):
        nx.sprite(f"cloud{i}", f"cloud.heap:{i + 1}", (x, y, 0), rot_deg=(0, 0, yaw), face=False, shadow=False, back="mist")
    for i in range(5):
        a = rnd.uniform(0, math.tau)
        s = nx.sprite(f"spark{i}", f"star:{i + 1}", (C[0] + math.cos(a) * 4, C[1] + math.sin(a) * 4, TOP + rnd.uniform(1, 4)),
                      shadow=False)
        nx.behave(s, bob=rnd.uniform(0.3, 0.6))


if __name__ == "__main__":
    nx.reset()
    build()
    nx.save_blend("shoal")
    nx.export("shoal")
