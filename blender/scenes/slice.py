"""切片场景：验证地基用。
运行：node scripts/blender.cjs build slice
产出：blender/slice.blend（可在 Blender 里打开继续改）与 public/scenes/slice.glb
"""
import os
import random
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import nx  # noqa: E402

nx.reset()

# ── 环境 ──
nx.into("env")
nx.sun((-0.5, -0.67, 0.55))
nx.spawn((0, -13, 0), facing_deg=0)
nx.sky_sprite("moon", "moon", (-0.35, 1, 0.3), width=22)
nx.plane("ground", 400, 400, a="mist", b="lilac_pale", pattern="tiles")

# ── 入口 A：低台上的晶体（低台 0.15m，直接迈上去） ──
nx.into("entrance_a")
nx.cylinder("dais_a", 1.6, 1.5, 0.15, (0, 6, 0), a="lilac", b="lilac_dark")
nx.torus("halo_a", 3.1, 0.06, (0, 6, 0.03), major_seg=96, minor_seg=6, a="violet", b="violet_deep", collide=False, shadow=False)
nx.entrance("entrance_a", (0, 6, 0.15 + 1.6), "/test-exit.html", "测试出口")

# ── 巨环 ──
nx.into("ring")
nx.torus("ring", 7.5, 0.42, (0, 17, 5.4), rot=(90, 0, 0), major_seg=120, minor_seg=18, a="mist", b="lilac_pale")

# ── 椅子：座高 4.2m ──
nx.into("chair")
chair = nx.group("chair", (-10, 4, 0), (0, 0, 31.5))
H, S, T = 4.2, 3.8, 0.5
c = S / 2 - T / 2
style = dict(a="lilac_dark", b="violet", pattern="bands")
for i, (sx, sy) in enumerate([(-1, -1), (-1, 1), (1, -1), (1, 1)]):
    nx.box(f"chair_leg{i}", (T, T, H), (sx * c, sy * c, 0), parent=chair, **style)
nx.box("chair_seat", (S + 0.3, S + 0.3, 0.45), (0, 0, H), parent=chair, **style)
for i, sx in enumerate([-1, 1]):
    nx.box(f"chair_post{i}", (T, T, 5.2), (sx * c, c, H + 0.45), parent=chair, **style)
for i in range(3):
    nx.box(f"chair_slat{i}", (S, 0.36, 0.42), (0, c, H + 1.6 + i * 1.35 - 0.21), parent=chair, **style)

# ── 通向半空的台阶：每级 0.5m（要跳），最后两级悬着 ──
nx.into("stairs")
st = nx.group("stairs", (11.5, 6, 0), (0, 0, -20))
style = dict(a="pink", b="rose")
n = 8
for i in range(n):
    nx.box(f"stair{i}", (2.4, 0.8, 0.5 * (i + 1)), (0, i * 0.8, 0), parent=st, **style)
nx.box("stair_float0", (2.4, 0.8, 0.5), (0, (n + 1.2) * 0.8, 0.5 * (n + 2) - 0.5), parent=st, **style)
nx.box("stair_float1", (2.4, 0.8, 0.5), (0, (n + 2.9) * 0.8, 0.5 * (n + 4.2) - 0.5), parent=st, **style)

# ── 一扇门框，前后都没有墙 ──
nx.into("door")
door = nx.group("door", (-3.6, -5, 0), (0, 0, 17))
style = dict(a="violet", b="violet_deep", pattern="stripes")
nx.box("door_post0", (0.22, 0.22, 2.3), (-0.55, 0, 0), parent=door, **style)
nx.box("door_post1", (0.22, 0.22, 2.3), (0.55, 0, 0), parent=door, **style)
nx.box("door_lintel", (1.32, 0.22, 0.22), (0, 0, 2.3), parent=door, **style)

# ── 远处的细柱 ──
nx.into("pillars")
for i, (x, y, h) in enumerate([(-26, 38, 14), (-18, 52, 22), (-7, 60, 9), (9, 48, 17), (22, 40, 11), (30, 58, 26), (-34, 24, 7)]):
    nx.box(f"pillar{i}", (0.8, 0.8, h), (x, y, 0), a="lilac_pale", b="lilac", pattern="bands")

# ── 入口 B：0.3m 一级的台阶走上平台（测试自动迈台阶） ──
nx.into("terrace")
ter = nx.group("terrace", (-14, 16, 0), (0, 0, -12))
style = dict(a="blue_pale", b="mist", pattern="tiles")
for i in range(5):
    nx.box(f"terrace_step{i}", (3.0, 0.6, 0.3 * (i + 1)), (0, -6.0 + i * 0.6, 0), parent=ter, **style)
nx.box("terrace_top", (6, 6, 1.5), (0, 0, 0), parent=ter, **style)
nx.entrance("entrance_b", (-14, 16, 1.5 + 1.6), "https://github.com/Traveritas", "GITHUB")

# ── 跳台：每块高 0.9m（要跳），顶上一株花 ──
nx.into("jumps")
for i in range(4):
    h = 0.9 * (i + 1)
    nx.box(f"jump{i}", (1.5, 1.5, h), (14 + i * 2.2, -4, 0), a="lilac", b="lilac_dark")
nx.sprite("flower_top", "flower", (14 + 3 * 2.2, -4, 3.6))

# ── 纸片 ──
nx.into("paper")
nx.sprite("flower", "flower", (5.5, -1.5, 0))
rnd = random.Random(7)
for i in range(46):
    import math
    a = rnd.random() * math.tau
    r = 3 + rnd.random() * 22
    nx.sprite(f"grass{i}", f"grass{i % 3 + 1}", (math.cos(a) * r + 2, -(math.sin(a) * r - 4), 0), shadow=False, back="lilac_pale")

nx.save_blend("slice")
nx.export("slice")
