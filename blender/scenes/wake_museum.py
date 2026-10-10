"""现实 · 原型四：陈列。一间空无一人的白色展厅，天花板开着几道长天窗。
正中一块矮台，台上是那间卧室的残片（同原型一，没有浮着的天花板），四周拉着隔离绳，绳前立一块展签。
对面一条长凳。两侧还有几块空的展台，展签还在，东西不见了。
人可以跨过绳子（绳子不挡人），走进展品，躺上那张床：E「睡」→ 梦里的家。天空：pale（素）。
运行：node scripts/blender.cjs build wake_museum，网页 ?world=wake_museum
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import furniture as fu  # noqa: E402
import nx  # noqa: E402
import wake  # noqa: E402

CENTER = (0, 0)
WHITE = dict(a="white", b="mist", pattern="plain")
FLOOR = dict(a="mist", b="lilac_pale", pattern="tiles")
SHADE = dict(a="mist", b="lilac_pale", pattern="plain")
ROPE = dict(a="rose", b="rose_deep", pattern="plain")
BRASS = dict(a="pink_pale", b="white", pattern="plain")

L, W, H = 44.0, 26.0, 13.0   # 展厅：长（x）、宽（y）、高
T = 0.6


def stanchion(name, x, y):
    nx.cylinder(f"{name}_foot", 0.2, 0.2, 0.04, (x, y, 0), segments=12, collide=False, **BRASS)
    nx.cylinder(f"{name}_post", 0.04, 0.04, 0.92, (x, y, 0.04), segments=8, **BRASS)
    nx.cylinder(f"{name}_cap", 0.07, 0.05, 0.08, (x, y, 0.96), segments=8, collide=False, **BRASS)


def rope(name, a, b, z=1.18, sag=0.18, n=6):
    """两根柱子之间垂一道绳：几段短条接成弧，不挡人"""
    import math
    ax, ay = a
    bx, by = b
    yaw = math.degrees(math.atan2(by - ay, bx - ax))
    pts = []
    for i in range(n + 1):
        t = i / n
        pts.append((ax + (bx - ax) * t, ay + (by - ay) * t, z - sag * 4 * t * (1 - t)))
    k = fu.Kit()
    for i in range(n):
        (x0, y0, z0), (x1, y1, z1) = pts[i], pts[i + 1]
        seg = math.hypot(x1 - x0, y1 - y0)
        pitch = math.degrees(math.atan2(z1 - z0, seg))
        # 本地坐标：绳沿 +X；整道绳合成一个网格
        t = (i + 0.5) / n
        k.box((seg + 0.02, 0.045, 0.045), (math.hypot(bx - ax, by - ay) * t, 0, pts[i][2] / 2 + pts[i + 1][2] / 2 - z),
              rot=(0, -pitch, 0), base=False)
    k.build(name, loc=(ax, ay, z), rot=(0, 0, yaw), smooth=0, collide=False, shadow=False, **ROPE)


def label(name, x, y, yaw):
    """展签：一根斜面的小立牌"""
    g = nx.group(name, (x, y, 0), (0, 0, yaw))
    nx.box(f"{name}_post", (0.06, 0.06, 1.0), (0, 0, 0), parent=g, **SHADE)
    nx.box(f"{name}_card", (0.42, 0.3, 0.025), (0, 0.04, 1.0), rot=(-30, 0, 0), parent=g, collide=False, **WHITE)
    nx.box(f"{name}_text", (0.28, 0.012, 0.012), (0, 0.075, 1.07), rot=(-30, 0, 0), parent=g, collide=False,
           a="lilac", b="lilac_dark", pattern="plain")
    nx.box(f"{name}_text2", (0.2, 0.012, 0.012), (-0.04, 0.035, 1.02), rot=(-30, 0, 0), parent=g, collide=False,
           a="lilac", b="lilac_dark", pattern="plain")


def build(extent=None):
    nx.into("env")
    nx.sun((0.3, -0.25, 0.9))
    nx.atmosphere("pale")

    # ── 展厅：地面、四面墙、天花板（长天窗之间是梁） ──
    nx.into("hall")
    nx.box("floor", (L + 2 * T, W + 2 * T, 1.0), (0, 0, -1.0), **FLOOR)
    for s in (-1, 1):
        nx.box(f"wall_ns{s}", (L + 2 * T, T, H), (0, s * (W / 2 + T / 2), 0), **WHITE)
        nx.box(f"wall_ew{s}", (T, W, H), (s * (L / 2 + T / 2), 0, 0), **WHITE)
        # 墙脚一道浅色的线
        nx.box(f"base_ns{s}", (L - 0.02, 0.06, 0.2), (0, s * (W / 2 - 0.03), 0), collide=False, **SHADE)
    # 天花板：横梁之间留四道天窗
    gaps = [(-11.0, -9.5), (-5.0, -4.0), (4.0, 5.0), (9.5, 11.0)]
    edges = sorted({-W / 2 - T, W / 2 + T} | {g for p in gaps for g in p})
    for i in range(0, len(edges), 2):
        y0, y1 = edges[i], edges[i + 1]
        nx.box(f"ceil{i}", (L + 2 * T, y1 - y0, 0.8), (0, (y0 + y1) / 2, H), **WHITE)
    for k, (y0, y1) in enumerate(gaps):
        for j in range(-5, 6):  # 天窗里的细横档
            nx.box(f"mullion{k}_{j}", (0.12, y1 - y0, 0.3), (j * 4.0, (y0 + y1) / 2, H + 0.25), collide=False, **SHADE)

    # ── 展品：矮台上的卧室残片 ──
    nx.into("exhibit")
    PZ = 0.3
    nx.box("plinth", (9.2, 8.0, PZ), (0, 0.5, 0), **WHITE)
    _, land, facing = wake.bedroom("ex_", (0, 0.5, PZ + 0.66), 0, torn=("s", "e"), seed=11, size=(7.0, 6.0), ceiling=False)

    # 绳子围一圈（前面、两侧），柱子挡人，绳子不挡
    nx.into("ropes")
    posts = [(-5.0, -4.2), (-1.7, -4.2), (1.7, -4.2), (5.0, -4.2), (5.0, 0.5), (5.0, 4.9), (-5.0, 0.5), (-5.0, 4.9)]
    for i, (x, y) in enumerate(posts):
        stanchion(f"post{i}", x, y)
    for i, (a, b) in enumerate([(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (0, 6), (6, 7)]):
        rope(f"rope{i}", posts[a], posts[b], z=0.9)
    label("label_main", 2.6, -5.0, 180)

    # ── 对面一条长凳 ──
    nx.into("bench")
    fu.bench("bench", (0, -9.0, 0), 0, length=3.2, style=WHITE)

    # ── 空的展台：展签还在，东西不见了 ──
    nx.into("empty")
    for i, (x, y, w, d, h) in enumerate([(-15, 5, 1.6, 1.6, 1.1), (-15, -5, 2.4, 1.4, 0.6), (15, 5, 1.2, 1.2, 1.4),
                                         (15, -5, 3.0, 2.0, 0.4)]):
        nx.box(f"pedestal{i}", (w, d, h), (x, y, 0), **WHITE)
        label(f"label{i}", x + (w / 2 + 0.6) * (1 if x < 0 else -1), y - d / 2 - 0.3, 180)

    # 人从长凳那边来：出生点在长凳后，面朝展品；从梦里回来落在床边
    nx.spawn((0, -12.0, 0), facing_deg=0)


if __name__ == "__main__":
    nx.reset()
    build()
    nx.save_blend("wake_museum")
    nx.export("wake_museum")
