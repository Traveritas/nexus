"""新主题 · 云阶：没有地面，只有高低错落的浮岛，一串悬空的踏步把它们连起来；纸的云垫在岛下。
越往上岛越小、颜色越浅，最高处一只平躺的环和一组转着的环。
- 出生的岛最大；第二座岛上一朵「莲」；一座岛上一摞错开的板和一棵纸的树。
- 三枚晶体：半腰的小岛、莲的花心、最高的岛。
掉下去会回到出生点。
运行：node scripts/blender.cjs build idea_isles
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import nx  # noqa: E402
import prefabs as pf  # noqa: E402

EXTENT = 400  # 地面边长；拼进总图（atlas.py）时按岛的大小传进来
CENTER = (0, 25)  # 内容的大致中心：地面以它为中心，总图也按它摆放

# (名字, x, y, 顶面高, 半径, 顶面色, 侧面色)
ISLES = [
    ("home", 0, 0, 0.0, 9.0, "mist", "lilac"),
    ("lotus", 17, 12, 3.0, 6.5, "pink_pale", "rose"),
    ("stack", 4, 28, 6.0, 6.0, "white", "lilac_pale"),
    ("small", -14, 19, 4.5, 4.2, "blue_pale", "lilac"),
    ("tree", -20, 38, 8.7, 5.5, "mist", "lilac_pale"),
    ("top", 2, 50, 12.0, 7.0, "white", "pink_pale"),
]
LINKS = [("home", "lotus"), ("home", "small"), ("lotus", "stack"), ("small", "tree"), ("stack", "top"), ("tree", "top")]


def build(extent=EXTENT):
    rnd = random.Random(41)
    isles = {n: (x, y, z, r) for n, x, y, z, r, *_ in ISLES}

    nx.into("env")
    nx.sun((0.3, -0.6, 0.5))
    nx.spawn((0, -5, 0), facing_deg=10)

    nx.into("isles")
    for i, (n, x, y, z, r, top, side) in enumerate(ISLES):
        pf.island(f"isle_{n}", (x, y, z), r, seed=i, top_style=dict(a=top, b="lilac_pale", pattern="grain"),
                  under_style=dict(a=side, b="lilac_pale", pattern="bands"))

    # 悬空的踏步：从一座岛的边到另一座岛的边
    nx.into("steps")
    for k, (a, b) in enumerate(LINKS):
        ax, ay, az, ar = isles[a]
        bx, by, bz, br = isles[b]
        d = math.hypot(bx - ax, by - ay)
        ux, uy = (bx - ax) / d, (by - ay) / d
        pa = (ax + ux * (ar - 0.6), ay + uy * (ar - 0.6), az)
        pb = (bx - ux * (br - 0.6), by - uy * (br - 0.6), bz)
        pf.steps_between(f"link{k}_", pa, pb, size=1.3, seed=k, a="white", b="mist", pattern="plain")

    # ── 各岛上的东西 ──
    nx.into("things")
    x, y, z, r = isles["lotus"]
    pf.bloom("lotus", (x, y, z), kind="lotus", size=3.2, seed=5, collide=False)  # 走得进花心
    nx.entrance("entrance_lotus", (x, y, z + 1.6), "https://traveritas.github.io/", "随笔 · 醒梦")

    x, y, z, r = isles["stack"]
    pf.plate_stack("stack", (x - 2, y + 1, z), n=7, seed=6)
    nx.sprite("stack_lamp", "lamp_street", (x + 2.5, y - 2, z), face=True)

    x, y, z, r = isles["small"]
    nx.entrance("entrance_small", (x, y, z + 1.6), "", "未命名")
    pf.bloom("small_blades", (x + 2.2, y + 1.5, z), kind="blade", size=2.4, seed=7, petals=4)

    x, y, z, r = isles["tree"]
    for i in range(3):
        nx.sprite(f"tree{i}", f"tree:{40 + i}", (x + rnd.uniform(-2.5, 2.5), y + rnd.uniform(-2, 2.5), z), face=True)
    pf.frame("tree_door", (x + 2.6, y - 2.2, z), 30, kind="door", a="violet", b="violet_deep", pattern="stripes")

    x, y, z, r = isles["top"]
    pf.halo("top_ring", (x, y, z + 3.2), r + 1.2, minor=0.3, tilt=8, spin=1.5, a="pink_pale", b="white")
    pf.orrery("top_orrery", (x, y, z + 10), radii=(4, 6.5, 9), seed=8)
    nx.entrance("entrance_top", (x, y, z + 1.6), "https://github.com/Traveritas", "GITHUB")
    pf.bloom("top_drift", (x, y, z), kind="drift", size=3.5, seed=9, petals=6)

    x, y, z, r = isles["home"]
    pf.frame("home_window", (x - 4, y + 3, z), -20, kind="window", w=2.4, h=3.0, a="white", b="mist", pattern="plain")
    nx.sprite("home_chair", "chair", (x + 3.5, y + 2, z), rot_deg=(0, 0, 200), face=False, back="pink_pale")
    pf.paper_scatter("home_grass", ["grass:{}", "grass:{}", "flower:{}", "bush:{}"], (x, y), 2.5, r - 1, 12, seed=10, z=z,
                     avoid=lambda px, py: math.hypot(px, py + 5) < 2)

    # ── 岛下的纸云，远处更多小岛 ──
    nx.into("clouds")
    for i, (n, x, y, z, r, *_) in enumerate(ISLES):
        nx.sprite(f"cloud_{n}", f"cloud:{i + 1}", (x + rnd.uniform(-3, 3), y + rnd.uniform(-3, 3), z - r * 1.3 - 2), face=True,
                  shadow=False)
    for i in range(10):
        a = rnd.uniform(0, math.tau)
        d = rnd.uniform(38, 58)
        x, y = math.cos(a) * d, math.sin(a) * d + 25
        z = rnd.uniform(-10, 22)
        pf.island(f"far_isle{i}", (x, y, z), rnd.uniform(2, 6), seed=20 + i,
                  top_style=dict(a=rnd.choice(["mist", "pink_pale", "white"]), b="lilac_pale", pattern="plain"))
        if i % 3 == 0:
            pf.tower_broken(f"far_tower{i}", (x, y, z), rnd.uniform(6, 14), w=1.2, pieces=2, seed=30 + i)


if __name__ == "__main__":
    nx.reset()
    build()
    nx.save_blend("idea_isles")
    nx.export("idea_isles")
