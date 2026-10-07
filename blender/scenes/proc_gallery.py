"""程序化纸片陈列：每一族、每种变体、几个种子并排（名字写法：族.变体:种子，见 src/proc.ts）。
运行：node scripts/blender.cjs build proc_gallery   网页：?scene=proc_gallery
从出生点往前：草与灌木 → 花 → 浮着的星 → 树 → 云
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import nx  # noqa: E402

EXTENT = 220
CENTER = (0, 30)
SEEDS = (1, 2, 3)


def row(prefix, names, y, gap, z=0.0, bob=0.0):
    n = len(names)
    for i, name in enumerate(names):
        x = (i - (n - 1) / 2) * gap
        s = nx.sprite(f"{prefix}{i}", name, (x, y, z), face=False, shadow=z == 0, back="mist")
        if bob:
            nx.behave(s, bob=bob)


def build(extent=EXTENT):
    nx.into("env")
    nx.sun((0.4, -0.6, 0.55))
    nx.spawn((0, -8, 0), facing_deg=0)
    nx.box("ground", (extent, extent, 1.0), (CENTER[0], CENTER[1], -1.0), a="mist", b="lilac_pale", pattern="tiles")

    nx.into("small")
    row("grass", [f"grass.{k}:{s}" for k in ("clump", "flowered", "reed") for s in SEEDS] + [f"bush:{s}" for s in (1, 2, 3, 4)],
        2, 2.6)
    row("flower", [f"flower.{k}:{s}" for k in ("cup", "star", "bell", "umbel", "puff") for s in SEEDS], 9, 3.0)
    row("star", [f"star.{k}:{s}" for k in ("dot", "glow", "diamond", "cluster", "ring") for s in SEEDS], 14, 1.6, z=2.6,
        bob=0.3)

    nx.into("trees")
    kinds = ("round", "tall", "weep", "pine", "bare", "blossom", "tuft")
    row("tree_a", [f"tree.{k}:1" for k in kinds], 26, 9.0)
    row("tree_b", [f"tree.{k}:2" for k in kinds], 36, 9.0)

    nx.into("clouds")
    row("cloud_a", [f"cloud.{k}:{s}" for k in ("heap", "flat") for s in (1, 2)], 54, 13.0)
    row("cloud_b", [f"cloud.{k}:{s}" for k in ("wisp", "puff") for s in (1, 2, 3)], 64, 11.0, z=3.0)


if __name__ == "__main__":
    nx.reset()
    build()
    nx.save_blend("proc_gallery")
    nx.export("proc_gallery")
