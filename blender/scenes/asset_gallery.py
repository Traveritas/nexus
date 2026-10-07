"""现成模型陈列：同一件东西三种处理并排——原色 · 色板染色（tint）· 放大到建筑尺度。
先取模型：node scripts/fetch-asset.cjs <id>（见下面 ITEMS）
运行：node scripts/blender.cjs build asset_gallery   网页：?scene=asset_gallery
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import assets as at  # noqa: E402
import nx  # noqa: E402

# (Poly Haven id, 正常高度 m, 放大后的高度 m, 染色用的两色)
ITEMS = [
    ("WoodenChair_01", 0.95, 4.2, ("pink_pale", "rose_deep")),
    ("potted_plant_02", 1.3, 5.0, ("mist", "violet")),
    ("street_lamp_01", 4.5, 9.0, ("lilac_pale", "violet_deep")),
    ("vintage_grandfather_clock_01", 2.1, 8.0, ("pink_pale", "violet")),
    ("GothicBed_01", 1.6, 5.0, ("white", "lilac_dark")),
    ("antique_ceramic_vase_01", 0.6, 5.5, ("blue_pale", "violet")),
    ("moon_rock_03", 1.2, 4.0, ("mist", "lilac_dark")),
]
EXTENT = 200
CENTER = (0, 20)


def build(extent=EXTENT):
    nx.into("env")
    nx.sun((0.45, -0.6, 0.5))
    nx.spawn((0, -6, 0), facing_deg=0)
    nx.box("ground", (extent, extent, 1.0), (CENTER[0], CENTER[1], -1.0), a="mist", b="lilac_pale", pattern="tiles")

    nx.into("assets")
    n = len(ITEMS)
    for i, (aid, h, big, (ca, cb)) in enumerate(ITEMS):
        x = (i - (n - 1) / 2) * 6.5
        at.asset(f"{aid}_raw", aid, (x, 4, 0), height=h, rot=(0, 0, 200))
        at.asset(f"{aid}_tint", aid, (x, 10, 0), height=h, rot=(0, 0, 200), tint=0.65, a=ca, b=cb)
        at.asset(f"{aid}_big", aid, (x, 26, 0), height=big, rot=(0, 0, 200), tint=0.35, a=ca, b=cb, smooth=(i % 2 == 1))


if __name__ == "__main__":
    nx.reset()
    build()
    nx.save_blend("asset_gallery")
    nx.export("asset_gallery")
