"""梦里的家 · 门外（house_out）：docs/home.md 的「室外」。

推开夜里的家门，外面是一片原野。从原野上看，那扇门只是立在地上的一扇门：门洞里是亮着灯的玄关，
绕到门背后，门洞里还是原野（缝只有一面），从背后也穿不过去（门后一块看不见的挡板）。从正面走过门槛就回到了玄关，不转场（门洞外的缝，见 house.py 的 seam_out）。

原野（调子取自一张粉紫的原野：淡紫的天，起伏的地，一片片粉的草丛）：
- 地是一整片缓缓起伏的丘，按 TILE 首尾相接（atmosphere wrap）：一直往一个方向走，会从另一边回来，
  走上一阵又会碰到同一扇门。雾在 150m 内合上，比半个方块近，站在门边看不见别处的门。
- 地是淡紫与粉之间一块块、一道道的过渡（纹样「漂」），一片片偏粉的地上长着粉的草丛（低模的软垫，一簇簇的）。
- 门前一小块是平的。除了门，地上什么都没有。
- 天：原野（meadow），淡紫的渐变，太阳斜斜地在东南，背着太阳的一面有一点粉。

门和家里那扇是同一扇（house.front_door），两道缝对齐后，原野的坐标 ＝ 家的坐标 + (−4.1, 1.8, −0.15)。
运行：node scripts/blender.cjs build house_out，网页 ?world=house_out
"""
import math
import os
import random
import sys

import bmesh

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import furniture as fu  # noqa: E402
import house  # noqa: E402
import nx  # noqa: E402

TILE = 384.0     # 方块边长：首尾相接
STEP = 4.0       # 地形的格子（色区按格分，格子细一点，色区的边才不是一道道直的台阶）
CLEAR = 12.0     # 门前这么大一块是平的
EXTENT = TILE
CENTER = (0, 0)

# 地用「漂」的纹样（pattern=drift）：几米一块的主副色过渡，沿等高线拉成一道道——
# 只用颗粒时，大片同一档受光的坡落色板后是一整片纯色
# 主副两色要隔得开：受光以后还落在不同的色板色上，过渡才看得出来（同一色系的深浅两色常常落成同一色）
GROUND = dict(a="lilac_pale", b="pink", pattern="drift")
BLUSH = dict(a="pink_pale", b="lilac", pattern="drift")
TUFTS = [dict(ramp=("rose", "pink", "pink_pale"), pattern="grain"), dict(ramp=("pink", "pink_pale", "white"), pattern="grain"),
         dict(ramp=("rose_deep", "rose", "pink"), pattern="grain")]

# 地形与色区都只用整数波数：沿 x、y 各走一个方块正好转回来，接缝对得上
_rnd = random.Random(7)
WAVES = [((1, 0), 5.0), ((0, 1), 4.0), ((1, 1), 3.5), ((2, -1), 3.0), ((1, -2), 2.4), ((3, 1), 1.6), ((-2, 3), 1.4),
         ((4, -3), 0.9), ((5, 2), 0.8), ((-3, -5), 0.6), ((7, 4), 0.35), ((-6, 7), 0.3)]
WAVES = [(k, a, _rnd.uniform(0, math.tau)) for k, a in WAVES]
ZONES = [((2, 1), _rnd.uniform(0, math.tau)), ((-1, 3), _rnd.uniform(0, math.tau)), ((4, -2), _rnd.uniform(0, math.tau)),
         ((5, 5), _rnd.uniform(0, math.tau))]


def _wave(x, y, k, ph):
    return math.sin(math.tau * (k[0] * x + k[1] * y) / TILE + ph)


def _flat(x, y):
    """门前一块是平的（只在中间这一份方块的原点，复制的那几份也一样）"""
    d = math.hypot(x, y)
    t = min(1.0, max(0.0, (d - CLEAR) / 22.0))
    return t * t * (3 - 2 * t)


def height(x, y):
    raw = sum(a * _wave(x, y, k, ph) for k, a, ph in WAVES)
    # 整片往下压一点，门前平地落在 0，和四周的起伏接得上
    return raw * _flat(x, y)


def blush(x, y):
    """粉的那几片：低频的色区，-1..1"""
    return sum(_wave(x, y, k, ph) for k, ph in ZONES) / 2.2


def face_up(obj):
    """敞口的面（地形、底下不封的草丛）重算法线时会一块块各自定朝向，有的整块翻到朝下、背面朝人就被裁掉了。
    这里的面都该朝上（草丛的侧面也朝外偏上）：一个个面翻回来"""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return obj


def ground():
    """地形：一张周期的高度网格，按色区分成两块（大片的淡紫与粉、长草的那几片）"""
    n = int(round(TILE / STEP))
    h0 = -TILE / 2
    verts = [(h0 + i * STEP, h0 + j * STEP, height(h0 + i * STEP, h0 + j * STEP)) for j in range(n + 1) for i in range(n + 1)]
    # 每块各自一份顶点表（同一块里相邻的面共用顶点，才平滑得起来）
    parts = {k: ([], [], {}) for k in ("ground", "blush")}

    def vid(part, v):
        vs, _, idx = part
        if v not in idx:
            idx[v] = len(vs)
            vs.append(verts[v])
        return idx[v]

    for j in range(n):
        for i in range(n):
            q = [j * (n + 1) + i, j * (n + 1) + i + 1, (j + 1) * (n + 1) + i + 1, (j + 1) * (n + 1) + i]
            cx, cy = h0 + (i + 0.5) * STEP, h0 + (j + 0.5) * STEP
            cz = sum(verts[v][2] for v in q) / 4
            # 门前那一块（连同四周一圈）不分色区：色区的边是沿格子的台阶，离门近了看得出一道直线
            part = parts["blush" if blush(cx, cy) > 0.35 and cz > -5.5 and math.hypot(cx, cy) > CLEAR + 20 else "ground"]
            # 对角线交错：低模的三角面不排成一个方向
            tris = [(q[0], q[1], q[2]), (q[0], q[2], q[3])] if (i + j) % 2 else [(q[0], q[1], q[3]), (q[1], q[2], q[3])]
            for t in tris:
                part[1].append(tuple(vid(part, v) for v in t))
    for name, style in (("ground", GROUND), ("blush", BLUSH)):
        k = fu.Kit()
        k._add(parts[name][0], parts[name][1])
        face_up(k.build(name, smooth=50, **style))


def tuft(k, x, y, r, hh, rnd):
    """一簇草：贴着地的低模软垫，底圈压进地里，中圈收一点，顶上一个尖略偏开"""
    seg = rnd.choice((6, 7))
    a0 = rnd.uniform(0, math.tau)
    base, mid = [], []
    for s in range(seg):
        a = a0 + math.tau * s / seg
        rr = r * rnd.uniform(0.8, 1.15)
        bx, by = x + math.cos(a) * rr, y + math.sin(a) * rr
        base.append((bx, by, height(bx, by) - 0.25))
        mx, my = x + math.cos(a) * rr * 0.62, y + math.sin(a) * rr * 0.62
        mid.append((mx, my, height(mx, my) + hh * rnd.uniform(0.55, 0.75)))
    tx, ty = x + rnd.uniform(-0.2, 0.2) * r, y + rnd.uniform(-0.2, 0.2) * r
    verts = base + mid + [(tx, ty, height(x, y) + hh)]
    top = 2 * seg
    faces = []
    for s in range(seg):
        t = (s + 1) % seg
        faces.append((s, t, seg + t, seg + s))
        faces.append((seg + s, seg + t, top))
    k._add(verts, faces)


def tufts():
    """草丛：只长在淡粉的那几片上，一团团地聚着；按 4 × 4 块、三种颜色合成几个物体（远处整块裁掉）"""
    rnd = random.Random(11)
    parts = {}
    lim = TILE / 2 - 6
    placed = 0
    tries = 0
    while placed < 2400 and tries < 120000:
        tries += 1
        x, y = rnd.uniform(-lim, lim), rnd.uniform(-lim, lim)
        b = blush(x, y)
        if b < 0.05 or math.hypot(x, y) < CLEAR + 4 or height(x, y) < -5.5:
            continue
        # 聚团：色区越浓越密
        if rnd.random() > (b - 0.05) * 1.4:
            continue
        # 一团里几簇挨着
        for _ in range(rnd.randint(3, 7)):
            px, py = x + rnd.uniform(-3, 3), y + rnd.uniform(-3, 3)
            if abs(px) > lim or abs(py) > lim or math.hypot(px, py) < CLEAR + 2:
                continue
            r = rnd.uniform(0.9, 2.8)
            key = (int((px + TILE / 2) // (TILE / 4)), int((py + TILE / 2) // (TILE / 4)), rnd.choices((0, 1, 2), (5, 4, 1))[0])
            tuft(parts.setdefault(key, fu.Kit()), px, py, r, r * rnd.uniform(0.35, 0.55), rnd)
            placed += 1
    for (cx, cy, c), k in sorted(parts.items()):
        face_up(k.build(f"tufts_{cx}{cy}_{c}", smooth=0, collide=False, **TUFTS[c]))


def build(extent=EXTENT):
    nx.into("env")
    nx.sun((0.55, -0.62, 0.42))  # 东南，斜斜的
    nx.atmosphere("meadow", wrap=TILE)
    nx.spawn((0, -3.0, 0), facing_deg=180)

    nx.into("door")
    # 家里那扇大门：门洞中心在原点，门往 +y（门背后）开；缝贴在门套外面，从南边看过去是玄关
    house.front_door(0.0, 0.0, 0.0)
    nx.seam("seam_home", (0.0, -house.FRONT_SEAM, 0.0), 0, "house", house.FRONT_W - 0.02, house.FRONT_H - 0.01)
    # 门背后一块看不见的挡板：从背后穿不过门洞（穿过去以后回头，门洞里的屋子会一下子出现）。
    # 离门 0.45m：从正面走进去时，人的中心先过了缝、换到屋里，身子还碰不到它
    nx.collider_only(nx.box("door_back_block", (house.FRONT_W + 0.2, 0.04, house.FRONT_H + 0.2), (0.0, 0.45, 0.0)))

    nx.into("ground")
    ground()
    tufts()


if __name__ == "__main__":
    nx.reset()
    build()
    nx.save_blend("house_out")
    nx.export("house_out")
