"""真实贴图的剪纸陈列：public/sprites 里所有 <名字>@<每米像素>.png 排成两排，正面朝出生点。
做新的剪纸：node scripts/cutout.cjs <PolyHaven id> --name 名字 --height 米 [--yaw 度 --tilt 度 --part n --ppm 64]
运行：node scripts/blender.cjs build cutout_gallery   网页：?scene=cutout_gallery
"""
import glob
import os
import struct
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import nx  # noqa: E402

EXTENT = 200
CENTER = (0, 20)


def _png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    return struct.unpack(">II", head[16:24])


def build(extent=EXTENT):
    nx.into("env")
    nx.sun((0.45, -0.6, 0.5))
    nx.spawn((0, -10, 0), facing_deg=0)
    nx.box("ground", (extent, extent, 1.0), (CENTER[0], CENTER[1], -1.0), a="mist", b="lilac_pale", pattern="tiles")

    nx.into("cutouts")
    files = sorted(glob.glob(os.path.join(nx.ROOT, "public", "sprites", "*@*.png")))
    items = []
    for f in files:
        name = os.path.splitext(os.path.basename(f))[0]
        ppm = int(name.split("@")[1])
        w, h = _png_size(f)
        items.append((name, w / ppm, h / ppm))
    # 矮的一排在前，高的一排在后
    for row, (y, pick) in enumerate([(2, lambda h: h < 3.0), (16, lambda h: h >= 3.0)]):
        sel = [it for it in items if pick(it[2])]
        total = sum(w for _, w, _ in sel) + 1.5 * (len(sel) - 1)
        x = -total / 2
        for name, w, h in sel:
            nx.sprite(f"cut_{name}", name, (x + w / 2, y, 0), face=False, shadow=True, back="mist")
            x += w + 1.5


if __name__ == "__main__":
    nx.reset()
    build()
    nx.save_blend("cutout_gallery")
    nx.export("cutout_gallery")
