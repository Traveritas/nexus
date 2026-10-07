"""新主题 · 花房：一座只剩骨架的温室。九道拱一字排开，拱顶由三根长梁串起；没有玻璃。
里面不种花，种的是「花之装置」：两侧的低台上，开的、未开的、落下的，各种形态都有一点。
- 中轴是一条长长的浅水，水心一片圆台，晶体在上面。
- 中殿尽头一扇花形的门。
- 侧门外横着一只水杯，晶体在杯里。
- 纸片：拱顶挂下来的纸吊灯、剪纸百合、香蒲、蒲公英。
运行：node scripts/blender.cjs build glasshouse
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import nx  # noqa: E402
import prefabs as pf  # noqa: E402

EXTENT = 400  # 地面边长；拼进总图（atlas.py）时按岛的大小传进来
CENTER = (0, 18)  # 内容的大致中心：地面以它为中心，总图也按它摆放


def build(extent=EXTENT):
    rnd = random.Random(53)
    F = 0.3
    W, H = 18.0, 15.0  # 拱的内宽、顶高
    Y0, Y1, N = -6.0, 42.0, 9

    nx.into("env")
    nx.sun((0.35, -0.5, 0.55))
    nx.spawn((0, -16, 0), facing_deg=0)
    nx.atmosphere("night")
    pf.return_door("glasshouse", (0, -19.5, 0), 0)
    nx.box("ground", (extent, extent, 1.0), (CENTER[0], CENTER[1], -1.0), a="mist", b="green", pattern="grain")
    nx.box("floor", (W + 4, Y1 - Y0 + 6, F), (0, (Y0 + Y1) / 2, 0), a="white", b="mist", pattern="tiles")
    # 门前的三级台阶
    for k in range(3):
        nx.box(f"front_step{k}", (8, 0.8, 0.1 * (k + 1)), (0, Y0 - 3.4 + k * 0.8, 0), a="white", b="mist", pattern="plain")

    # ── 骨架：九道拱 + 三根长梁 ──
    nx.into("skeleton")
    for i in range(N):
        y = Y0 + (Y1 - Y0) * i / (N - 1)
        pf.frame(f"arch{i}", (0, y, F), 0, w=W, h=H, depth=0.45, t=0.5, kind="arch",
                 a="white" if i % 2 else "mist", b="lilac_pale", pattern="plain")
    R = W / 2 + 0.25
    post = H - W / 2
    for k, ang in enumerate([90, 45, 135]):
        a = math.radians(ang)
        x, z = math.cos(a) * R, post + math.sin(a) * R
        nx.box(f"purlin{k}", (0.4, Y1 - Y0, 0.4), (x, (Y0 + Y1) / 2, F + z - 0.2), a="lilac_pale", b="lilac",
               pattern="plain", collide=False)
    # 拱顶挂下来的纸吊灯
    for i in range(N - 1):
        y = Y0 + (Y1 - Y0) * (i + 0.5) / (N - 1)
        nx.sprite(f"pendant{i}", "pendant", (0, y, F + post + R - 0.4 - 2.75 - rnd.uniform(0, 2.5)), face=False,
                  rot_deg=(0, 0, rnd.uniform(-20, 20)), shadow=False)

    # ── 中轴的浅水与水心圆台 ──
    nx.into("pool")
    nx.box("pool", (4.5, Y1 - Y0 - 4, 0.06), (0, (Y0 + Y1) / 2, F), a="blue_pale", b="blue", pattern="bands")
    M = (0, 18)
    pf.pad("pool_pad", (M[0], M[1], F), 3.4, h=0.3, notch=0, a="pink_pale", b="mist")
    pf.bloom("pool_drift", (M[0], M[1], F + 2), kind="drift", size=3, seed=1, petals=6)

    # ── 两侧的低台与花之装置 ──
    nx.into("beds")
    kinds = ["rosette", "lotus", "blade", "rosette", "blade", "lotus", "blade", "rosette"]
    for side in (-1, 1):
        for j in range(4):
            y = Y0 + 4 + j * 11
            bx = side * 6.2
            pf.plinth(f"bed{side}_{j}", (bx, y, F), 4.6, 7.5, h=0.3, a="lilac_pale", b="green")
            k = kinds[(j * 2 + (side > 0)) % len(kinds)]
            size = {"rosette": 2.8, "lotus": 2.2, "blade": 3.6}[k] * rnd.uniform(0.85, 1.15)
            pf.bloom(f"bloom{side}_{j}", (bx, y + rnd.uniform(-1.2, 1.2), F + 0.3), kind=k, size=size, seed=10 + j * 2 + (side > 0))
            nx.sprite(f"bed_lily{side}_{j}", f"flower:{j * 2 + (side > 0) + 11}", (bx + side * 1.4, y + 2.6, F + 0.3), face=True)
            nx.sprite(f"bed_reed{side}_{j}", f"grass.reed:{j + 1}", (bx - side * 1.6, y - 2.8, F + 0.3), face=True)

    # ── 尽头：花形的门 ──
    nx.into("gate")
    ent = pf.halo_gate("gate", (0, Y1 + 9, F), 0, size=4.2, seed=2)
    nx.box("gate_floor", (10, 10, F), (0, Y1 + 8, 0), a="white", b="mist", pattern="tiles")
    nx.portal("portal_gate", (ent[0], ent[1], ent[2] - 0.6), "procession", at="side", radius=0.9)
    nx.arrive("gate", (3.5, Y1 - 8, F), facing_deg=0)

    # ── 侧门外的水杯 ──
    nx.into("vessel")
    pf.frame("side_door", (W / 2 + 1.1, 21, F), 90, w=2.2, h=3.4, kind="door", a="violet", b="violet_deep", pattern="stripes")
    _, inside = pf.vessel("side_cup", (W / 2 + 9, 21, 0), yaw=90, R=2.5, length=5.5)
    nx.portal("portal_cup", (inside[0], inside[1], inside[2] + 1.0), "shoal", at="glass", mode="key", title="杯中", radius=1.0)
    nx.arrive("cup", (W / 2 + 5.5, 21, 0), facing_deg=90)

    # ── 温室外：草、蒲公英、几棵纸树 ──
    nx.into("paper")
    inside_house = lambda x, y: abs(x) < W / 2 + 3 and Y0 - 5 < y < Y1 + 14  # noqa: E731
    pf.paper_scatter("out_grass", ["grass:{}", "grass:{}", "bush:{}", "flower:{}"], (0, 18), 14, 45, 50, seed=3, avoid=inside_house)
    pf.paper_scatter("out_tree", ["tree:{}"], (0, 18), 22, 45, 9, seed=4, avoid=inside_house, shadow=True)


if __name__ == "__main__":
    nx.reset()
    build()
    nx.save_blend("glasshouse")
    nx.export("glasshouse")
