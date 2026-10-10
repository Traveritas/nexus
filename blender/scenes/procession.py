"""新主题 · 回廊：一条笔直的堤，从低处一路穿过二十多道框。
框一道比一道大、一道比一道斜、颜色一道比一道浅；走着走着，像是被一层层「显影」出来。
- 堤两侧是浅水，纸的路灯一对一对站在堤边。
- 半路一方小院：四面拱框朝里，头顶一组慢慢转的环；院里立着一扇落地窗（走出去 → 云阶）。
- 堤的尽头是一扇花形的门：梯子走上去，穿过花心就是晶体（→ 博客）。
- 堤外一处侧园：立着的残环，环边一朵莲。
- 出生点背后一盏路灯（E「关灯」→ 家）。出入口三个：灯、窗、晶体；从哪儿去的，回来就落在哪儿。
运行：node scripts/blender.cjs build procession
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import nx  # noqa: E402
import prefabs as pf  # noqa: E402

EXTENT = 400  # 地面边长；拼进总图（atlas.py）时按岛的大小传进来
CENTER = (0, 33)  # 内容的大致中心：地面以它为中心，总图也按它摆放


def build(extent=EXTENT):
    rnd = random.Random(31)
    F = 0.3

    nx.into("env")
    nx.sun((-0.5, -0.45, 0.45))
    nx.atmosphere("halo")
    pf.gate_home("procession", (0, -26.6, F), 0)  # 出生点在灯前
    nx.box("ground", (extent, extent, 1.0), (CENTER[0], CENTER[1], -1.0), a="lilac_pale", b="lilac", pattern="grain")

    # ── 堤与两侧的水 ──
    nx.into("causeway")
    nx.box("causeway", (5, 104, F), (0, 24, 0), a="mist", b="lilac_pale", pattern="tiles")
    for sx in (-1, 1):
        nx.box(f"pool{sx}", (14, 96, 0.06), (sx * 9.6, 26, 0), a="blue_pale", b="blue", pattern="bands")
        nx.box(f"curb{sx}", (0.6, 104, F + 0.25), (sx * 2.8, 24, 0), a="white", b="mist", pattern="plain")

    # ── 二十多道框：越走越大、越斜、越浅 ──
    nx.into("frames")
    pf.procession("pf_a", (0, -14, F), (0, 18, F), 10, kinds=("door", "window", "square", "arch"),
                  w0=3.0, h0=4.0, grow=1.6, roll_step=2.5, palette=("lilac", "lilac_pale", "pink_pale"), seed=1)
    pf.procession("pf_b", (0, 36, F), (0, 66, F), 12, kinds=("arch", "square", "door"),
                  w0=4.6, h0=6.2, grow=1.7, roll_step=-3.5, palette=("pink_pale", "mist", "white"), seed=2)

    # 纸的路灯，一对一对
    nx.into("lamps")
    for i, y in enumerate(range(-18, 72, 9)):
        for sx in (-1, 1):
            nx.sprite(f"lamp{i}_{'l' if sx < 0 else 'r'}", "lamp_street", (sx * 2.2, y, F + 0.25),
                      rot_deg=(0, 0, 90 * -sx), face=False, back="lilac_pale")

    # ── 半路的小院 ──
    nx.into("cloister")
    Q = (0, 27)
    nx.box("cloister_floor", (16, 16, F + 0.01), (Q[0], Q[1], 0), a="white", b="pink_pale", pattern="tiles")
    for k in range(4):
        yaw = 90 * k
        a = math.radians(yaw + 90)
        pf.frame(f"cloister_arch{k}", (Q[0] + math.cos(a) * 6.5, Q[1] + math.sin(a) * 6.5, F), yaw,
                 w=4.2, h=5.2, depth=0.6, t=0.45, kind="arch", a="mist", b="lilac_pale", pattern="plain")
    for k, (dx, dy) in enumerate([(-6.5, -6.5), (6.5, -6.5), (-6.5, 6.5), (6.5, 6.5)]):
        pf.monolith(f"cloister_corner{k}", (Q[0] + dx, Q[1] + dy, F), 45, w=1.0, d=1.0, h=3.2,
                    a="lilac_pale", b="lilac", pattern="bands")
    pf.orrery("cloister_rings", (Q[0], Q[1], 11), radii=(3.5, 5.5, 7.5), seed=3)
    pf.gate_window("procession", (Q[0] + 4.5, Q[1], F), 180)  # 院里一扇落地窗，朝着来路，头顶转着环 → 云阶
    for i in range(4):
        a = math.radians(45 + 90 * i)
        nx.sprite(f"cloister_lily{i}", f"flower.cup:{i + 1}", (Q[0] + math.cos(a) * 4.2, Q[1] + math.sin(a) * 4.2, F), face=True)

    # ── 尽头：花形的门 ──
    nx.into("gate")
    ent = pf.halo_gate("gate", (0, 82, F), 0, size=5.2, seed=4,
                       styles=[dict(a="white", b="pink_pale"), dict(a="pink_pale", b="pink"), dict(a="mist", b="white")])
    nx.box("gate_floor", (12, 12, F + 0.01), (0, 80, 0), a="white", b="mist", pattern="tiles")
    nx.entrance("entrance_gate", ent, "https://traveritas.github.io/", "AveritA的昼梦叙集")
    pf.bloom("gate_drift", (0, 80, 2), kind="drift", size=4, seed=5, petals=8)

    # ── 侧园：立着的残环 ──
    nx.into("side_garden")
    S = (-20, 44)
    pf.pad("side_pad", (S[0], S[1], 0), 7, h=F, notch=0, seed=6, a="mist", b="pink_pale")
    pf.arch_ring("side_ring", (S[0], S[1], F), 70, 5.5, thick=0.7, depth=1.0)
    pf.steps_between("side_steps", (-2.5, 44, F), (S[0] + 6.8, S[1], F), seed=7)
    pf.bloom("side_lotus", (S[0] - 4, S[1] + 4.5, F), kind="lotus", size=2.2, seed=8)

    # ── 远处两排碑，透视收向尽头 ──
    nx.into("monoliths")
    for i in range(10):
        y = -6 + i * 10
        for sx in (-1, 1):
            h = rnd.uniform(5, 14) * (1 + i * 0.08)
            pf.monolith(f"far{i}_{sx}", (sx * (24 + i * 1.5 + rnd.uniform(-2, 2)), y, 0), rnd.uniform(-10, 10),
                        w=1.6, d=1.0, h=h, a=rnd.choice(["mist", "lilac_pale", "pink_pale"]), b="lilac", pattern="bands")

    # ── 纸片 ──
    nx.into("paper")
    for i in range(8):
        s = nx.sprite(f"spark{i}", f"star:{i + 1}", (rnd.uniform(-2, 2), rnd.uniform(-10, 70), rnd.uniform(3, 7)), shadow=False)
        nx.behave(s, bob=rnd.uniform(0.3, 0.7))
    pf.paper_scatter("reed", ["grass.reed:{}", "flower:{}"], (0, 26), 4, 40, 18, seed=9,
                     avoid=lambda x, y: abs(x) < 4 or math.hypot(x - S[0], y - S[1]) < 8 or (abs(x) < 9 and abs(y - 27) < 9))


if __name__ == "__main__":
    nx.reset()
    build()
    nx.save_blend("procession")
    nx.export("procession")
