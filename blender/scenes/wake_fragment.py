"""现实 · 残片（干净低模）。一间卧室的一角被撕下来，浮在一片流动的、说不出是什么的东西里。

画风：现实的世界不走梦的管线——干净低模、不像素化、不落色板、不描边（nx.atmosphere(style="clean")），
模型全在这里与 blender/lowpoly.py 里重新做，不用梦里的家具库；颜色取 src/palette.ts 的色板，再整体降饱和（lowpoly.soft）。

这一角：
- 西墙、北墙还在，各自断在一头：砖芯一皮皮参差地断，内墙的灰皮断得更靠里，露出一圈砖。墙顶还留着一道顶角线（这里原来有天花板）。
- 撕下来的楼板：木地板、结构层、楼下天花板的白灰三层，南边、东边撕开，一层比一层撕得狠。
- 床（E「睡」→ 梦里的家）、床头柜与台灯、闹钟、一杯水。
- 北墙一扇窗，窗外有两处（窗景 outlook）：博客的那一夜（overnight）与 GitHub 的未完成的构造（scaffold）。两幅窗帘平时合着，走近就拉开；按 E 推开窗，两扇窗往外开，眼睛凑到窗口往外看，站点卡片浮出来，可以进博客或退回。窗下一张书桌（桌面右手空着一块）、一把椅子。
- 西墙一架书、一本挂历；床头上方一幅歪了一点的画；角落一把扶手椅、一张小圆几。
- 头顶浮着撕下来的一块天花板，吊灯还挂着、亮着。断墙口垂下一截电线，吊着一个开关。
- 四周漂着同一栋房子的别处：几块撕下来的楼板，上面各留着一样东西（椅子、一截门、书架、台灯），还有几条地板慢慢浮着。
运行：node scripts/blender.cjs build wake_fragment，网页 ?world=wake_fragment
"""
import math
import os
import random
import sys

from mathutils import Matrix, Vector

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import lowpoly as lp  # noqa: E402
import nx  # noqa: E402

CENTER = (0, 0)

# ── 颜色 ─────────────────────────────────────────
# 取 src/palette.ts 的 16 色（低饱和）；少数几枚是相邻两色之间的中间色，注明了是哪两色之间
P = dict(ink='#1d1a2b', violet_deep='#3a3350', violet='#5c5378', lilac_dark='#82799e', lilac='#a8a1bf',
         lilac_pale='#cdc8db', mist='#ece9f2', white='#fbf9f7', rose_deep='#6e4f66', rose='#a8798c', pink='#d9aab5',
         pink_pale='#f3d6d6', blue='#8fa3c7', blue_pale='#c3d1e6', gold='#ead7a0', green='#86b5a5')
C = dict(
    oak=(P['pink'], '#cfa0ad', '#e3bcc4'),          # 地板三色：粉，及粉往玫瑰 / 往浅粉各挪一点
    joist=P['rose'], plaster=P['mist'], copper=P['gold'], slab=P['lilac_pale'],
    brick='#8c6577',                                # 玫瑰与深玫瑰之间
    wall='#f0e0e4', render=P['lilac_pale'], trim=P['white'],   # 内墙：浅粉与雾白之间
    walnut=P['rose_deep'], sheet=P['white'], quilt=P['blue_pale'], throw=P['lilac'], pillow=P['mist'],
    pillow2=P['lilac_pale'], mustard=P['gold'], slate=P['blue'], slate2='#a9b9d6', brass=P['gold'],  # 雾蓝与浅雾蓝之间
    ceramic=P['mist'], shade=P['gold'],
    desk='#dcbcc3', sage=P['green'], curtain=P['lilac'], rug=P['mist'], rug2=P['blue'],   # 书桌：粉与浅粉之间
    shelf=P['white'], ink=P['violet_deep'],
    chair=P['rose'], chair2='#c08c9c', paper=P['white'], red=P['rose'], glass=P['blue_pale'],   # 坐垫：玫瑰与粉之间
    books=(P['rose'], P['blue'], P['gold'], P['green'], P['lilac_dark'], P['pink'], P['violet']),
)
# 整体再淡一点：所有颜色的饱和度乘 0.6（lowpoly.soft）
C = {k: tuple(lp.soft(c) for c in v) if isinstance(v, tuple) else lp.soft(v) for k, v in C.items()}
P = {k: lp.soft(v) for k, v in P.items()}

H = 2.7          # 墙高（原来的天花板）
COURSE = 0.15    # 一皮砖
# 墙的三层：内墙灰皮 0.03 · 砖芯 0.14 · 外墙抹灰 0.03
N_SKIN, N_CORE, N_REND = (2.80, 2.83), (2.83, 2.97), (2.97, 3.00)
W_SKIN, W_CORE, W_REND = (-3.23, -3.20), (-3.37, -3.23), (-3.40, -3.37)
WX0, WX1, WZ0, WZ1 = -2.35, -1.05, 0.85, 2.15   # 窗洞
SILL = 0.81      # 窗台板底（窗洞下的墙只砌到这里）


def courses(s_bottom, s_top, seed, jit=0.07, odd=0.11):
    """断口：每一皮砖的端头。下面的皮长、上面的短，单双皮错开半块"""
    r = random.Random(seed)
    out = []
    n = int(round(H / COURSE))
    for i in range(n):
        z0, z1 = i * COURSE, (i + 1) * COURSE
        t = ((z0 + z1) / 2) / H
        out.append((s_bottom + (s_top - s_bottom) * t ** 0.8 + r.uniform(-jit, jit) + (odd if i % 2 else 0), z0, z1))
    return out


def stair_outline(s0, cs):
    """砖芯的立面轮廓（台阶状的断口）"""
    pts = [(s0, 0.0)]
    for s, z0, z1 in cs:
        pts += [(s, z0), (s, z1)]
    pts.append((s0, H))
    return pts


def ragged_outline(s0, cs, back, seed, sign=1):
    """灰皮 / 抹灰的立面轮廓：比砖芯的断口往回缩一段（back 范围里随机），边是斜的、参差的，不按皮走"""
    r = random.Random(seed)
    pts = [(s0, 0.0)]
    zs = [0.0] + [z1 for _, _, z1 in cs]
    for k, z in enumerate(zs):
        i = min(k, len(cs) - 1)
        pts.append((cs[i][0] - sign * r.uniform(*back), z))
    pts.append((s0, H))
    return pts


def s_at(cs, z):
    return cs[min(int(z / COURSE), len(cs) - 1)][0]


# ── 墙 ───────────────────────────────────────────

def walls():
    nx.into("walls")
    g = {k: lp.Geo() for k in ("brick", "wall", "render", "trim")}
    # 北墙：沿 x，东头断。断口：底下到 x≈2.15，往上收到 x≈1.0
    nc = courses(2.15, 1.0, 3)
    for key, (y0, y1), back, x_start, seed in (("brick", N_CORE, None, -3.37, 0), ("wall", N_SKIN, (0.12, 0.38), -3.20, 41),
                                               ("render", N_REND, (0.05, 0.25), -3.40, 43)):
        geo = g[key]
        geo.cuboid(x_start, WX0, y0, y1, 0, H)
        geo.cuboid(WX0, WX1, y0, y1, 0, SILL)
        geo.cuboid(WX0, WX1, y0, y1, WZ1, H)
        geo.slab_xz(stair_outline(WX1, nc) if back is None else ragged_outline(WX1, nc, back, seed), y0, y1)
    # 西墙：沿 y 往南，南头断。断口：底下到 y≈-0.95，往上收到 y≈0.05
    wc = courses(-0.95, 0.05, 7, odd=-0.11)
    for key, (x0, x1), back, y_start, seed in (("brick", W_CORE, None, 2.83, 0), ("wall", W_SKIN, (0.12, 0.38), 2.80, 47),
                                               ("render", W_REND, (0.05, 0.25), 2.97, 53)):
        out = stair_outline(y_start, wc) if back is None else ragged_outline(y_start, wc, back, seed, sign=-1)
        g[key].slab_yz(out, x0, x1)

    # 踢脚、顶角线（这里原来有天花板）：只铺到灰皮还在的地方
    n_end = s_at(nc, 0.05) - 0.5
    w_end = s_at(wc, 0.05) + 0.5
    g["trim"].cuboid(-3.20, n_end, 2.785, 2.80, 0, 0.10)
    g["trim"].cuboid(-3.20, -3.185, w_end, 2.785, 0, 0.10)
    n_top = min(s for s, z0, _ in nc if z0 >= 2.4) - 0.5
    w_top = max(s for s, z0, _ in wc if z0 >= 2.4) + 0.5
    g["trim"].cuboid(-3.20, n_top, 2.74, 2.80, 2.58, H)
    g["trim"].cuboid(-3.20, -3.14, w_top, 2.74, 2.58, H)
    for key, geo in g.items():
        geo.build(f"wall_{key}", color=C[key])
    return nc, wc


def window():
    """窗：窗台、窗套、两扇窗的框与横档、把手；窗玻璃（模板）；窗帘杆与两幅窗帘；窗台上一盆仙人掌"""
    nx.into("window")
    t = lp.Thing("window")
    tr = t["trim"]
    tr.cuboid(WX0 - 0.06, WX1 + 0.06, 2.62, 3.02, SILL, WZ0)            # 窗台板：伸进屋 18cm、伸出墙 2cm
    tr.cuboid(WX0, WX0 + 0.03, N_SKIN[0], N_REND[1], WZ0, WZ1)           # 窗套
    tr.cuboid(WX1 - 0.03, WX1, N_SKIN[0], N_REND[1], WZ0, WZ1)
    tr.cuboid(WX0 + 0.03, WX1 - 0.03, N_SKIN[0], N_REND[1], WZ1 - 0.03, WZ1)
    a, b = WX0 + 0.03, WX1 - 0.03
    mid = (a + b) / 2
    # 窗玻璃（模板）：贴在窗扇外侧（y 2.95，窗扇在 2.88..2.93），正面朝屋里。窗里只画窗景的天（outlook），
    # 窗扇往外开以后也还在原处，所以开着的窗洞里照样是那一处
    gp = lp.Geo()
    gp.quad([(a, 2.95, WZ0), (b, 2.95, WZ0), (b, 2.95, WZ1 - 0.03), (a, 2.95, WZ1 - 0.03)])
    nx.pane(gp.build("window_pane", recalc=False, color="#ffffff", collide=False, shadow=False))
    # 两扇窗：各自绕外侧的铰链往外开，翻到贴着外墙（推开窗时，pose 组 sash，on=cue）。
    # 原点就是铰链，在外墙面上（y 3.00），窗扇在它屋里那一侧 7–12cm：这样转过 90° 以后窗扇落在墙外，不切进窗套。
    # 开出去的窗扇在玻璃外面，窗里的天会盖住它，所以画在窗里的天之后（window="over"）
    for side, hinge, sx in (("l", a, 1), ("r", b, -1)):
        lf = lp.Thing(f"sash_{side}", (hinge, N_REND[1], 0))
        s = lf["sash"]
        w = mid - a
        y0, y1 = 2.88 - N_REND[1], 2.93 - N_REND[1]
        X = lambda u0, u1: (min(sx * u0, sx * u1), max(sx * u0, sx * u1))   # 铰链往窗中间的方向量 u
        s.cuboid(*X(0, 0.05), y0, y1, WZ0, WZ1 - 0.03)                      # 外侧的边梃
        s.cuboid(*X(w - 0.03, w), y0, y1, WZ0, WZ1 - 0.03)                  # 中间合缝的边梃（两扇各一半）
        s.cuboid(*X(0.05, w - 0.03), y0, y1, WZ0, WZ0 + 0.05)
        s.cuboid(*X(0.05, w - 0.03), y0, y1, WZ1 - 0.08, WZ1 - 0.03)
        s.cuboid(*X(0.05, w - 0.03), y0 + 0.005, y1 - 0.005, 1.74, 1.77)
        if side == "r":
            lf["brass"].cuboid(*X(w - 0.027, w - 0.003), y0 - 0.04, y0, 1.36, 1.46)
        lf.done({"sash": C["trim"], "brass": dict(color=C["brass"], collide=False)}, collide=False, window="over")
        for o in lf.g.children:
            nx.pose(o, "sash", on="cue", rot=(0, 0, 175 * sx), time=1.1)
    # 窗帘杆与托架
    t["brass"].rod((WX0 - 0.42, 2.66, 2.33), (WX1 + 0.42, 2.66, 2.33), 0.012, 8)
    for x in (WX0 - 0.36, WX1 + 0.36):
        t["brass"].cuboid(x - 0.015, x + 0.015, 2.67, 2.80, 2.31, 2.35)
    for x in (WX0 - 0.43, WX1 + 0.43):            # 杆头的球：球心压在杆端上，杆插进球里
        t["brass"].blob(0.025, (x, 2.66, 2.33), seg=8, rings=4, jitter=0)
    t.done({"trim": C["trim"], "brass": dict(color=C["brass"], collide=False)})
    # 窗帘：两幅折出褶子的布（一层面、双面渲染），平时合着；走近窗就往两头拉开、收拢（pose 组 curtain，on=near）。
    # 布的褶子以杆为中线左右折，上沿每隔一折（布穿过杆的地方）一只吊环套在杆上。
    # 原点在杆上、托架里侧：拉开 ＝ 沿杆缩到三成，布的褶子同时深一些；吊环只沿杆收拢，不跟着变形
    for side, end, x1, folds in (("l", WX0 - 0.33, mid - 0.005, 9), ("r", WX1 + 0.33, mid + 0.005, 9)):
        cu = lp.Thing(f"curtain_{side}", (end, 2.66, 0))
        n = folds * 2
        top, bot = 2.318, 1.0      # 上沿顶到吊环底；下摆让过床头的台灯与桌上的相框
        verts = []
        for i in range(n + 1):
            x = (x1 - end) * i / n
            y = 0.035 if i % 2 else -0.035
            verts += [(x, y, bot + (0.02 if i % 2 else 0)), (x, y, top)]
        cu["curtain"].add(verts, [(2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1) for i in range(n)])
        cu.done({"curtain": dict(color=C["curtain"], double=True, collide=False, one_sided=True)})
        rg = lp.Thing(f"curtain_rings_{side}", (end, 2.66, 0))
        for i in range(0, n, 2):
            x = (x1 - end) * (i + 0.5) / n
            rg["brass"].cyl(0.02, 0.012, 8, loc=(x - 0.006, 0, 2.33), rot=(0, 90, 0))
        rg.done({"brass": C["brass"]}, collide=False)
        for o in cu.g.children:
            nx.pose(o, "curtain", on="near", at=((WX0 + WX1) / 2, 2.6, 0), radius=2.6, scale=(0.28, 1.8, 1), time=1.1)
        for o in rg.g.children:
            nx.pose(o, "curtain", on="near", at=((WX0 + WX1) / 2, 2.6, 0), radius=2.6, scale=(0.28, 1, 1), time=1.1)
    # 窗景：窗外是博客的那一夜。纸签系在窗前；推开窗以后眼睛凑到窗口里（在开着的两扇窗之间），朝北往外看
    nx.outlook("blog", ((WX0 + WX1) / 2, 2.55, 1.45), "https://traveritas.github.io/", "AveritA的昼梦叙集", sky="overnight",
               radius=0.9, desc="在即将醒来的那一瞬，世界究竟是在成形，还是正在融化？",
               view=((WX0 + WX1) / 2, 2.42, 1.55), view_facing=0, view_pitch=2)
    # 第二处：GitHub。窗外是一张制图纸上没搭完的线框（scaffold）；一句话就是那边的简介。眼睛的位置跟第一处走
    nx.outlook("github", ((WX0 + WX1) / 2, 2.55, 1.45), "https://github.com/Traveritas", "GitHub · AveritA", sky="scaffold",
               radius=0.9, desc="Hello.")


def floor():
    """撕下来的楼板：上面一层木地板，下面一层结构，再下面挂着楼下天花板的白灰。南边、东边撕开；三层撕得一层比一层狠"""
    nx.into("floor")
    x0, y0, x1, y1 = -3.40, -2.85, 3.25, 3.00
    for name, inset, bite, z0, z1, col, seed in (("boards", 0.0, 0.45, -0.12, 0.0, C["oak"][0], 11),
                                                 ("slab", 0.05, 0.8, -0.57, -0.12, C["slab"], 12),
                                                 ("plaster", 0.3, 1.0, -0.65, -0.57, C["plaster"], 13)):
        g = lp.Geo()
        g.prism(lp.torn_outline(x0 + inset * 0, y0 + inset, x1 - inset, y1, "se", seed, bite), z0, z1)
        g.build(f"floor_{name}", color=col, collide=name != "plaster")


# ── 家具 ─────────────────────────────────────────

def bed():
    """床：床头靠北墙。胡桃木床架、拱顶床头板、床垫、软被、翻折的床单、两只枕头、床尾一条毯子"""
    t = lp.Thing("bed", (0.6, 1.685, 0))
    w = t["walnut"]
    for sx in (-1, 1):
        for sy in (-1, 1):
            w.cuboid(sx * 0.765 - 0.035, sx * 0.765 + 0.035, sy * 0.99 - 0.035, sy * 0.99 + 0.035, 0, 0.16)
        w.cuboid(sx * 0.77 - 0.03, sx * 0.77 + 0.03, -1.0, 0.99, 0.16, 0.36)
    w.slab_xz([(-0.82, 0.16), (0.82, 0.16), (0.82, 0.50), (-0.82, 0.50)], -1.065, -1.0)
    head = [(-0.82, 0.16), (0.82, 0.16), (0.82, 0.95), (0.62, 1.04), (0.32, 1.10), (0.0, 1.12),
            (-0.32, 1.10), (-0.62, 1.04), (-0.82, 0.95)]
    w.slab_xz(head, 0.99, 1.05)
    t["sheet"].cushion(-0.73, 0.73, -0.98, 0.97, 0.30, 0.52, 3, 5, puff=0.008, seed=1, edge=0.025)
    t["quilt"].cushion(-0.815, 0.815, -0.97, 0.35, 0.37, 0.585, 6, 6, puff=0.035, seed=2, edge=0.015)
    t["sheet"].cushion(-0.82, 0.82, 0.28, 0.50, 0.46, 0.60, 6, 2, puff=0.015, seed=3, edge=0.01)
    t["pillow"].cushion(-0.70, -0.08, 0.50, 0.92, 0.52, 0.66, 3, 3, puff=0.04, seed=4, edge=0.04)
    t["pillow2"].cushion(0.08, 0.70, 0.52, 0.93, 0.52, 0.65, 3, 3, puff=0.04, seed=5, edge=0.04)
    t["throw"].cushion(-0.84, 0.86, -0.86, -0.42, 0.45, 0.64, 6, 2, puff=0.02, seed=6, edge=0.01)
    t.done({"walnut": C["walnut"], "sheet": C["sheet"], "quilt": C["quilt"], "pillow": C["pillow"],
            "pillow2": C["pillow2"], "throw": C["throw"]})
    nx.portal("portal_bed", (0.6, 1.9, 0.8), "home", at="wake", mode="key", title="睡", radius=1.3)


def nightstand():
    t = lp.Thing("nightstand", (-0.575, 2.53, 0), yaw=180)
    for sx in (-1, 1):
        for sy in (-1, 1):
            t["slate"].cyl(0.022, 0.14, 6, loc=(sx * 0.2, sy * 0.16, 0), r2=0.016)
    t["slate"].box((0.5, 0.42, 0.41), (0, 0, 0.14))
    t["front"].cuboid(-0.21, 0.21, 0.21, 0.222, 0.36, 0.52)
    t["front"].cuboid(-0.21, 0.21, 0.21, 0.222, 0.17, 0.34)
    for z in (0.44, 0.255):
        t["brass"].blob(0.014, (0, 0.235, z), seg=6, rings=3, jitter=0)
    t.done({"slate": C["slate"], "front": C["slate2"], "brass": dict(color=C["brass"], collide=False)})
    top = 0.55
    # 台灯：陶瓷座、暖光的罩
    lamp = lp.Thing("bedlamp", (-0.70, 2.60, top))
    lamp["base"].lathe([(0.06, 0), (0.075, 0.04), (0.07, 0.12), (0.04, 0.2), (0.012, 0.24), (0.012, 0.3)], 8)
    lamp["shade"].lathe([(0.14, 0.25), (0.09, 0.43)], 10)
    lamp.done({"base": C["ceramic"], "shade": dict(color=C["shade"], emit=0.85)}, collide=False)
    # 闹钟：圆身子、两只铃，钟面朝屋里
    ck = lp.Thing("clock", (-0.43, 2.45, top), yaw=160)
    ck["body"].cyl(0.055, 0.045, 12, loc=(0, -0.0225, 0.065), rot=(-90, 0, 0))
    for sx in (-1, 1):
        ck["brass"].lathe([(0.026, 0), (0.024, 0.012), (0.0, 0.026)], 8, loc=(sx * 0.035, 0, 0.115), rot=(0, sx * 30, 0))
        ck["body"].cuboid(sx * 0.035 - 0.008, sx * 0.035 + 0.008, -0.01, 0.01, 0, 0.016)
    ck["face"].cyl(0.045, 0.004, 12, loc=(0, 0.0225, 0.065), rot=(-90, 0, 0))
    ck["ink"].cuboid(-0.002, 0.002, 0.0265, 0.029, 0.065, 0.1)
    ck["ink"].box((0.003, 0.0025, 0.03), (0.012, 0.0278, 0.06), rot=(0, -60, 0))
    ck.done({"body": C["red"], "brass": C["brass"], "face": C["paper"], "ink": C["ink"]}, collide=False)
    gl = lp.Thing("water", (-0.52, 2.66, top))
    gl["glass"].cyl(0.032, 0.11, 8, r2=0.036)
    gl.done({"glass": C["glass"]}, collide=False)


def desk():
    """书桌（窗下）：桌面、四条腿、牵条、左右两只抽屉；桌上摊开的本子、一支笔、笔筒、马克杯、小相框。桌面右手空着一块"""
    t = lp.Thing("desk", (-2.05, 2.48, 0), yaw=180)
    d = t["oak"]
    d.box((1.6, 0.56, 0.03), (0, 0, 0.72))
    for sx in (-1, 1):
        for sy in (-1, 1):
            d.cyl(0.024, 0.72, 6, loc=(sx * 0.75, sy * 0.23, 0), r2=0.02)
    d.cuboid(-0.72, 0.72, 0.195, 0.215, 0.63, 0.72)
    d.cuboid(-0.72, 0.72, -0.215, -0.195, 0.63, 0.72)
    for x in (-0.43, 0.43):                         # 左右两只抽屉
        t["drawer"].cuboid(x - 0.25, x + 0.25, 0.215, 0.228, 0.645, 0.71)
        t["brass"].blob(0.012, (x, 0.24, 0.678), seg=6, rings=3, jitter=0)
    t.done({"oak": C["desk"], "drawer": C["walnut"], "brass": dict(color=C["brass"], collide=False)})
    top = 0.75
    nb = lp.Thing("notebook", (-2.25, 2.40, top), yaw=8)
    nb["cover"].box((0.42, 0.29, 0.004))
    nb["pages"].box((0.195, 0.27, 0.012), (-0.103, 0, 0.004), rot=(0, -3, 0))
    nb["pages"].box((0.195, 0.27, 0.012), (0.103, 0, 0.004), rot=(0, 3, 0))
    for i in range(6):
        nb["ink"].box((0.13, 0.004, 0.001), (0.11, -0.08 + i * 0.03, 0.0175))
    nb["pen"].rod((0.02, -0.17, 0.006), (0.16, -0.21, 0.006), 0.005, 6)
    nb.done({"cover": C["red"], "pages": C["paper"], "ink": C["slate"], "pen": C["ink"]}, collide=False)
    pc = lp.Thing("pencils", (-2.72, 2.62, top))
    pc["cup"].cyl(0.04, 0.1, 8)
    for i, (dx, dy, col) in enumerate(((0.012, 0.0, "mustard"), (-0.01, 0.012, "slate"), (0.0, -0.014, "red"))):
        pc[col].rod((dx, dy, 0.02), (dx * 3, dy * 3, 0.2 - i * 0.015), 0.005, 6)
    pc.done({"cup": C["sage"], "mustard": C["mustard"], "slate": C["slate"], "red": C["red"]}, collide=False)
    mug = lp.Thing("mug", (-1.5, 2.5, top), yaw=-30)
    mug["mug"].cyl(0.042, 0.095, 10)
    for p0, p1 in (((0.04, 0, 0.075), (0.07, 0, 0.07)), ((0.07, 0, 0.07), (0.07, 0, 0.03)), ((0.07, 0, 0.03), (0.04, 0, 0.025))):
        mug["mug"].rod(p0, p1, 0.008, 5)
    mug["tea"].cyl(0.036, 0.004, 10, loc=(0, 0, 0.083))
    mug.done({"mug": P["pink"], "tea": P["rose_deep"]}, collide=False)
    # 相框：正面朝屋里（朝椅子），往后仰 12°，背后一条撑脚
    ph = lp.Thing("photo", (-2.5, 2.68, top), yaw=170)
    tilt = math.radians(12)
    lean = lambda y, z: (0, y * math.cos(tilt) - z * math.sin(tilt), y * math.sin(tilt) + z * math.cos(tilt))
    ph["frame"].box((0.14, 0.012, 0.18), (0, 0, 0), rot=(12, 0, 0))
    ph["pic"].box((0.1, 0.004, 0.13), lean(0.007, 0.025), rot=(12, 0, 0))
    ph["frame"].rod(lean(-0.006, 0.12), (0, -0.075, 0.0), 0.005, 5)
    ph.done({"frame": C["walnut"], "pic": P["blue_pale"]}, collide=False)
    # 椅子：漆成鼠尾草绿，椅背上搭着一件毛衣
    ch = lp.Thing("chair", (-2.0, 1.78, 0), yaw=12)
    s = ch["paint"]
    s.chamfer((0.44, 0.42, 0.035), 0.05, (0, 0, 0.44))
    for sx in (-1, 1):
        for sy in (-1, 1):
            s.rod((sx * 0.17, sy * 0.16, 0.44), (sx * 0.2, sy * 0.19, 0.0), 0.016, 6)
        s.rod((sx * 0.17, -0.17, 0.475), (sx * 0.18, -0.21, 0.92), 0.017, 6)
    s.box((0.42, 0.04, 0.09), (0, -0.205, 0.84), rot=(-8, 0, 0))
    for i in range(3):
        s.rod(((i - 1) * 0.08, -0.18, 0.475), ((i - 1) * 0.08, -0.2, 0.84), 0.009, 5)
    ch.done({"paint": C["sage"]})


def shelf():
    """书架（靠西墙，正面朝东）：白漆，四层书，书有斜靠的、平放一摞的；顶上一盆垂下来的绿萝、一只小陶瓷鸟"""
    t = lp.Thing("bookshelf", (-3.025, 0.75, 0), yaw=-90)
    w = t["shelf"]
    w.cuboid(-0.5, -0.475, -0.15, 0.15, 0, 1.85)
    w.cuboid(0.475, 0.5, -0.15, 0.15, 0, 1.85)
    w.cuboid(-0.5, 0.5, -0.15, 0.15, 1.85, 1.875)
    w.cuboid(-0.475, 0.475, -0.15, -0.135, 0.06, 1.85)
    w.cuboid(-0.475, 0.475, 0.125, 0.15, 0.0, 0.06)
    levels = [0.06, 0.48, 0.90, 1.32]
    for z in levels:
        w.cuboid(-0.475, 0.475, -0.135, 0.15, z, z + 0.022)
    r = random.Random(31)
    for li, z in enumerate(levels):
        base = z + 0.022
        room = (levels[li + 1] if li + 1 < len(levels) else 1.85) - base - 0.03
        x = -0.47
        while x < 0.42:
            if r.random() < 0.12 and x < 0.2:
                # 平放的一摞
                hz = base
                for _ in range(r.randint(2, 4)):
                    th = r.uniform(0.025, 0.045)
                    t[f"b{r.randrange(7)}"].box((r.uniform(0.18, 0.24), r.uniform(0.15, 0.2), th), (x + 0.13, 0.0, hz))
                    hz += th + 0.001
                x += 0.27
                continue
            th = r.uniform(0.022, 0.05)
            h = min(r.uniform(0.17, 0.31), room)
            t[f"b{r.randrange(7)}"].cuboid(x, x + th, -0.13, -0.13 + r.uniform(0.16, 0.21), base, base + h)
            x += th + 0.002
            if r.random() < 0.08:
                x += r.uniform(0.04, 0.1)
        # 每层最后一本斜靠着
        if x < 0.44:
            t[f"b{r.randrange(7)}"].box((0.03, 0.15, min(0.24, room)), (min(x + 0.07, 0.43), -0.05, base), rot=(0, -16, 0))
    specs = {f"b{i}": C["books"][i] for i in range(7)}
    specs["shelf"] = C["shelf"]
    t.done(specs)


def corner():
    """西南角：扶手椅（毯子搭在扶手上）、小圆几（茶杯、两本书）"""
    t = lp.Thing("armchair", (-2.25, -1.30, 0), yaw=137)    # 背对屋里，朝外面的虚空
    for sx in (-1, 1):
        for sy in (-1, 1):
            t["walnut"].cyl(0.022, 0.1, 6, loc=(sx * 0.33, sy * 0.3, 0), r2=0.016)
    t["body"].chamfer((0.82, 0.78, 0.28), 0.06, (0, 0, 0.1))
    t["body"].box((0.82, 0.18, 0.56), (0, -0.30, 0.38), rot=(10, 0, 0))
    for sx in (-1, 1):
        t["body"].chamfer((0.13, 0.72, 0.22), 0.04, (sx * 0.345, 0.02, 0.38))
    t["cushion"].cushion(-0.29, 0.29, -0.2, 0.36, 0.37, 0.47, 3, 3, puff=0.02, seed=13, edge=0.02)
    t["cushion"].box((0.56, 0.12, 0.40), (0, -0.17, 0.46), rot=(12, 0, 0))
    t.done({"walnut": C["walnut"], "body": C["chair"], "cushion": C["chair2"]})
    st = lp.Thing("sidetable", (-2.85, -0.55, 0))
    st["oak"].cyl(0.24, 0.025, 10, loc=(0, 0, 0.52))
    st["oak"].cyl(0.025, 0.5, 6, loc=(0, 0, 0.02))
    for k in range(3):
        a = 2 * math.pi * k / 3
        st["oak"].rod((0, 0, 0.06), (math.cos(a) * 0.2, math.sin(a) * 0.2, 0.0), 0.018, 5)
    st["cup"].lathe([(0.0, 0.545), (0.07, 0.545), (0.072, 0.552), (0.0, 0.552)], 10, loc=(0.08, 0.07, 0))
    st["cup"].lathe([(0.03, 0.552), (0.045, 0.6), (0.048, 0.605), (0.0, 0.605)], 10, loc=(0.08, 0.07, 0))
    st["b0"].box((0.2, 0.15, 0.03), (-0.09, -0.08, 0.545), rot=(0, 0, 18))
    st["b1"].box((0.19, 0.14, 0.025), (-0.09, -0.08, 0.576), rot=(0, 0, 4))
    st.done({"oak": C["desk"], "cup": C["paper"], "b0": C["books"][1], "b1": C["books"][2]})


def rug():
    t = lp.Thing("rug_main", (0.35, -0.45, 0), yaw=4)
    t["rug"].box((2.6, 1.8, 0.012))
    t["field"].box((2.3, 1.5, 0.004), (0, 0, 0.012))
    dia = [(-0.6, 0), (0, 0.42), (0.6, 0), (0, -0.42)]
    t["rug2"].prism(dia, 0.016, 0.019)
    for sx in (-1, 1):
        t["rug2"].prism([(x * 0.35 + sx * 0.85, y * 0.35) for x, y in dia], 0.016, 0.019)
        x0, x1 = (1.3, 1.34) if sx > 0 else (-1.34, -1.3)
        for i in range(11):
            t["rug"].cuboid(x0, x1, -0.8 + i * 0.16 - 0.012, -0.8 + i * 0.16 + 0.012, 0, 0.006)
    t.done({"rug": C["rug"], "field": C["rug2"], "rug2": C["rug"]}, collide=False, shadow=False)


def wall_things(nc):
    """墙上：床头上方一幅歪了一点的画（夜海与月亮）；书桌边西墙上一本挂历；断墙口垂下来的电线与开关"""
    t = lp.Thing("painting", (0.35, 0, 1.75), rot=(0, -4, 0))
    f = t["frame"]
    W, Hh = 0.5, 0.62
    for x0, x1, z0, z1 in ((-W / 2, W / 2, -Hh / 2, -Hh / 2 + 0.04), (-W / 2, W / 2, Hh / 2 - 0.04, Hh / 2),
                           (-W / 2, -W / 2 + 0.04, -Hh / 2 + 0.04, Hh / 2 - 0.04), (W / 2 - 0.04, W / 2, -Hh / 2 + 0.04, Hh / 2 - 0.04)):
        f.cuboid(x0, x1, 2.775, 2.80, z0, z1)
    a = W / 2 - 0.04
    b = Hh / 2 - 0.04
    t["sky"].cuboid(-a, a, 2.785, 2.80, -b, b)
    t["sea"].slab_xz([(-a, -b), (a, -b), (a, -0.06), (0.1, -0.04), (-a, -0.07)], 2.782, 2.785)
    t["moon"].slab_xz([(0.08 + math.cos(k * math.pi / 6) * 0.05, 0.12 + math.sin(k * math.pi / 6) * 0.05) for k in range(12)], 2.782, 2.785)
    t["moon"].slab_xz([(0.05, -0.09), (0.11, -0.09), (0.10, -0.075), (0.06, -0.075)], 2.7805, 2.782)
    t.done({"frame": C["walnut"], "sky": P["violet_deep"], "sea": P["violet"], "moon": P["gold"]}, collide=False)
    cal = lp.Thing("calendar", (0, 0, 0))
    cal["paper"].cuboid(-3.20, -3.192, 2.05, 2.37, 1.22, 1.66)
    cal["red"].cuboid(-3.192, -3.189, 2.05, 2.37, 1.56, 1.66)
    for i in range(5):
        for j in range(4):
            cal["ink"].cuboid(-3.192, -3.1905, 2.08 + i * 0.055, 2.115 + i * 0.055, 1.27 + j * 0.065, 1.30 + j * 0.065)
    cal["brass"].cyl(0.0035, 0.02, 8, loc=(-3.20, 2.21, 1.635), rot=(0, 90, 0))      # 平头钉：钉身从墙里钉出来
    cal["brass"].cyl(0.011, 0.004, 10, loc=(-3.18, 2.21, 1.635), rot=(0, 90, 0))     # 平的钉帽
    cal.done({"paper": C["paper"], "red": C["red"], "ink": C["pillow2"], "brass": C["brass"]}, collide=False)
    # 断墙口垂下来的电线：从砖芯的断面里伸出来，末端吊着一个开关盒（避开床头板）
    x0 = s_at(nc, 1.45) - 0.02
    xb = max(x0 + 0.2, 1.62)
    pts = [(x0, 2.86, 1.45), (x0 + (xb - x0) * 0.4, 2.8, 1.25), (x0 + (xb - x0) * 0.8, 2.76, 1.05), (xb, 2.75, 0.95)]
    wire = lp.Thing("wire", (0, 0, 0))
    for p0, p1 in zip(pts, pts[1:]):
        wire["ink"].rod(p0, p1, 0.006, 5)
    wire["trim"].box((0.08, 0.035, 0.11), (xb, 2.75, 0.84), rot=(0, 8, 0))
    wire["ink"].box((0.02, 0.01, 0.035), (xb, 2.729, 0.88), rot=(0, 8, 0))
    wire.done({"ink": C["ink"], "trim": C["trim"]}, collide=False, shadow=False)


def ceiling():
    """头顶浮着撕下来的一块天花板：底面白灰、龙骨、楼上的地板；吊灯还挂着、亮着；楼上的地板上掉着一本书"""
    t = lp.Thing("ceiling", (0.45, 1.3, 3.55), rot=(3, -2, 6))
    r = random.Random(17)
    out = []
    for k in range(18):
        a = 2 * math.pi * k / 18
        rad = 1.0 + r.uniform(-0.25, 0.25)
        out.append((math.cos(a) * rad * 1.75, math.sin(a) * rad * 1.35))
    t["plaster"].prism(out, 0.0, 0.03)
    for i in range(6):
        x = -1.5 + i * 0.6
        lim = 1.0 - abs(x) / 2.2
        t["joist"].cuboid(x - 0.035, x + 0.035, -1.2 * lim, 1.2 * lim, 0.03, 0.21)
    for k in range(14):
        y0 = -1.12 + k * 0.16
        span = 1.55 * math.sqrt(max(0.05, 1 - (y0 / 1.3) ** 2))
        t["oak"].prism([(-span + r.uniform(-0.1, 0.15), y0), (span + r.uniform(-0.15, 0.1), y0),
                        (span + r.uniform(-0.15, 0.1), y0 + 0.155), (-span + r.uniform(-0.1, 0.15), y0 + 0.155)], 0.21, 0.245)
    t["book"].box((0.16, 0.22, 0.03), (0.4, -0.2, 0.245), rot=(0, 0, 25))
    # 吊灯：顶盘、电线、灯罩（亮着）、灯泡
    px, py = 0.2, 0.35
    t["trim"].cyl(0.07, 0.03, 10, loc=(px, py, -0.03))
    t["ink"].rod((px, py, -0.03), (px, py, -0.72), 0.005, 4)
    t["shade"].lathe([(0.03, -0.74), (0.2, -0.95), (0.19, -0.96), (0.025, -0.75)], 12, loc=(px, py, 0))
    t["bulb"].blob(0.04, (px, py, -0.8), scale=(1, 1, 1.2), seg=8, rings=4, jitter=0)
    t.done({"plaster": C["plaster"], "joist": C["joist"], "oak": C["oak"][1], "book": C["books"][4], "trim": C["trim"],
            "ink": C["ink"], "shade": dict(color=C["shade"], emit=0.7), "bulb": dict(color=P["white"], emit=1.0)},
           collide=False)


# ── 漂着的：同一栋房子的别处 ──────────────────────

def chunk(name, loc, w, d, yaw, seed, r):
    """一块撕下来的楼板（四边都撕开），稍稍歪着；返回它的父级，上面的东西挂在它下面"""
    g = nx.group(name, loc, (r.uniform(-6, 6), r.uniform(-6, 6), yaw))
    for part, inset, bite, z0, z1, col in (("boards", 0.0, 0.4, -0.1, 0.0, C["oak"][r.randrange(3)]),
                                          ("slab", 0.05, 0.6, -0.4, -0.1, C["slab"]),
                                          ("plaster", 0.2, 0.7, -0.45, -0.4, C["plaster"])):
        geo = lp.Geo()
        geo.prism(lp.torn_outline(-w / 2 + inset, -d / 2 + inset, w / 2 - inset, d / 2 - inset, "nesw", seed + len(part), bite), z0, z1)
        geo.build(f"{name}_{part}", parent=g, color=col, collide=False)
    return g


def drift():
    """四周漂着同一栋房子的别处：几块撕下来的楼板，上面各留着一样东西（椅子、一截门、书架、台灯），还有几条地板慢慢浮着"""
    nx.into("drift")
    r = random.Random(5)
    bits = [(-11, 6, -3, 3.0, 2.4, 20, "chair"), (12, 9, 2.5, 2.4, 2.0, -35, "door"), (8, -12, -6, 3.6, 2.6, 60, "shelf"),
            (-14, -9, 5, 1.8, 1.4, 10, None), (-4, 18, 9, 2.2, 1.6, -15, "lamp"), (20, -2, -12, 4.0, 3.0, 5, None),
            (-22, 14, -15, 3.0, 2.0, 40, None), (3, -24, 12, 1.4, 1.2, 70, None)]
    for i, (x, y, z, w, d, yaw, what) in enumerate(bits):
        g = chunk(f"bit{i}", (x, y, z), w, d, yaw, 40 + i * 5, r)
        if what == "chair":
            t = lp.Thing(f"bit{i}_chair", (0.2, 0, 0), yaw=30, parent=g)
            s = t["paint"]
            s.chamfer((0.44, 0.42, 0.035), 0.05, (0, 0, 0.44))
            for sx in (-1, 1):
                for sy in (-1, 1):
                    s.rod((sx * 0.17, sy * 0.16, 0.44), (sx * 0.2, sy * 0.19, 0.0), 0.016, 6)
                s.rod((sx * 0.17, -0.17, 0.475), (sx * 0.18, -0.21, 0.92), 0.017, 6)
            s.box((0.42, 0.04, 0.09), (0, -0.205, 0.84), rot=(-8, 0, 0))
            t.done({"paint": C["chair"]}, collide=False)
        elif what == "door":
            t = lp.Thing(f"bit{i}_door", (0, 0.2, 0), parent=g)
            t["wall"].slab_xz([(-1.2, 0), (-0.5, 0), (-0.5, 2.15), (0.5, 2.15), (0.5, 0), (0.9, 0), (0.85, 1.9), (0.3, 2.6), (-1.1, 2.45)],
                              -0.08, 0.08)
            t["trim"].cuboid(-0.5, -0.45, -0.1, 0.1, 0.0, 2.1)
            t["trim"].cuboid(0.45, 0.5, -0.1, 0.1, 0.0, 2.1)
            t["trim"].cuboid(-0.5, 0.5, -0.1, 0.1, 2.1, 2.15)
            t.done({"wall": C["wall"], "trim": C["trim"]}, collide=False)
        elif what == "shelf":
            t = lp.Thing(f"bit{i}_shelf", (0, 0.8, 0), parent=g)
            w_ = t["shelf"]
            for xx in (-0.5, 0.475):
                w_.cuboid(xx, xx + 0.025, -0.15, 0.15, 0, 1.6)
            for zz in (0.0, 0.5, 1.0, 1.575):
                w_.cuboid(-0.475, 0.475, -0.15, 0.15, zz, zz + 0.025)
            rb = random.Random(70 + i)
            for zz in (0.025, 0.525, 1.025):
                xx = -0.47
                while xx < 0.4:
                    th = rb.uniform(0.03, 0.06)
                    t[f"b{rb.randrange(7)}"].cuboid(xx, xx + th, -0.12, -0.12 + rb.uniform(0.17, 0.22), zz, zz + rb.uniform(0.2, 0.42))
                    xx += th + 0.003
            specs = {f"b{k}": C["books"][k] for k in range(7)}
            specs["shelf"] = C["shelf"]
            t.done(specs, collide=False)
        elif what == "lamp":
            t = lp.Thing(f"bit{i}_lamp", (0, 0, 0), parent=g)
            t["base"].lathe([(0.12, 0), (0.15, 0.08), (0.14, 0.24), (0.08, 0.4), (0.024, 0.48), (0.024, 0.6)], 8)
            t["shade"].lathe([(0.28, 0.5), (0.18, 0.86)], 10)
            t.done({"base": C["ceramic"], "shade": dict(color=C["shade"], emit=0.6)}, collide=False)
    # 几条地板，慢慢浮着（不投影）
    for i in range(14):
        a = r.uniform(0, 2 * math.pi)
        dist = r.uniform(6, 16)
        t = lp.Thing(f"plank{i}", (math.cos(a) * dist, math.sin(a) * dist, r.uniform(-4, 6)),
                     rot=(r.uniform(-40, 40), r.uniform(-40, 40), r.uniform(0, 180)))
        t["x"].box((r.uniform(0.6, 1.4), 0.14, 0.04), base=False)
        t.done({"x": C["oak"][i % 3] if i % 3 else C["quilt"]}, collide=False, shadow=False)
        for o in t.g.children:
            nx.behave(o, bob=r.uniform(0.1, 0.3))


# ── 开场：漂着的地板条，从一处看过去拼成 NEXUS ──────────
# 每一笔是一条地板，沿「机位 → 字面上那一点」的视线推远或拉近、按距离等比放大缩小——
# 从机位看过去五个字整整齐齐；走开一步就散成四处漂着的木条。
# 开场停在机位上（nx.intro），「点击醒来」以后木条逐个掉进虚空、视角滑到床边；不放开场时网页直接拿掉它们（src/intro.ts）。
TITLE_EYE = Vector((12.5, -14.5, 4.6))      # 机位（眼睛）
TITLE_LOOK = Vector((-0.6, 0.6, 0.9))      # 机位看向哪里（屋子的中间）
TITLE_D = 9.0                              # 字面离机位多远（深浅倍数 1 的地方）
TITLE_H = 2.3                             # 字高（在字面上）
TITLE_LIFT = 2.8                          # 字面中心比视线中心高多少（让出下面的屋子）
# 字的笔画：字高为 1 的格子里的线段
GLYPHS = {
    "N": [((0, 0), (0, 1)), ((0, 1), (0.68, 0)), ((0.68, 0), (0.68, 1))],
    "E": [((0, 0), (0, 1)), ((0, 1), (0.58, 1)), ((0, 0.5), (0.46, 0.5)), ((0, 0), (0.58, 0))],
    "X": [((0, 0), (0.7, 1)), ((0, 1), (0.7, 0))],
    "U": [((0, 1), (0, 0)), ((0, 0), (0.6, 0)), ((0.6, 0), (0.6, 1))],
    "S": [((0.62, 1), (0.1, 1)), ((0, 0.9), (0, 0.6)), ((0.1, 0.5), (0.52, 0.5)), ((0.62, 0.4), (0.62, 0.1)), ((0.52, 0), (0, 0))],
}


def title_view():
    """机位：脚底（Blender 坐标）、yaw、pitch（度，同 spawn / ?yaw ?pitch）"""
    f = (TITLE_LOOK - TITLE_EYE).normalized()
    yaw = math.degrees(math.atan2(-f.x, f.y))
    pitch = math.degrees(math.asin(f.z))
    return TITLE_EYE - Vector((0, 0, 1.6)), yaw, pitch


def title():
    nx.into("title")
    r = random.Random(11)
    eye = TITLE_EYE
    f = (TITLE_LOOK - eye).normalized()
    right = f.cross(Vector((0, 0, 1))).normalized()
    up = right.cross(f)
    gap, stroke = 0.3, 0.15          # 字距、笔画宽（字高为 1）
    word = "NEXUS"
    widths = [max(max(a[0], b[0]) for a, b in GLYPHS[ch]) for ch in word]
    total = sum(widths) + gap * (len(word) - 1)
    mid = eye + f * TITLE_D + up * TITLE_LIFT
    x0 = -total / 2
    i = 0
    for ch, w in zip(word, widths):
        for (ax, ay), (bx, by) in GLYPHS[ch]:
            pa = mid + (right * (x0 + ax) + up * (ay - 0.5)) * TITLE_H
            pb = mid + (right * (x0 + bx) + up * (by - 0.5)) * TITLE_H
            s = (pb - pa).normalized()
            ext = stroke * TITLE_H / 2          # 两头各伸出半个笔宽，转角接得上
            pa, pb = pa - s * ext, pb + s * ext
            n = (-f).cross(s).normalized() * (stroke * TITLE_H / 2)
            depth = (-f) * 0.035
            # 沿视线推远 / 拉近：以眼睛为中心整条等比缩放，从机位看过去投影不变
            k = r.uniform(0.6, 1.25)
            corners = [pa - n, pb - n, pb + n, pa + n]
            verts = [eye + (c - depth - eye) * k for c in corners] + [eye + (c + depth - eye) * k for c in corners]
            t = lp.Thing(f"title{i}")
            t["x"].add(verts, [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)])
            t.done({"x": r.choice((C["joist"], C["brick"], C["oak"][1]))}, collide=False, shadow=False)
            t.g["nx_intro"] = i          # 「点击醒来」以后按这个次序逐个掉进虚空
            i += 1
        x0 += w + gap


def build(extent=None):
    nx.into("env")
    nx.sun((0.35, -0.5, 0.75))
    nx.atmosphere("flux", style="clean")
    nc, wc = walls()
    window()
    floor()
    nx.into("furniture")
    bed()
    nightstand()
    desk()
    shelf()
    corner()
    rug()
    wall_things(nc)
    ceiling()
    drift()
    title()
    nx.intro(*title_view())
    # 醒来在床的东边，面朝屋里（看得见床、窗和窗外的街）
    land = (2.0, 1.45, 0)
    nx.arrive("home", land, facing_deg=95)
    nx.spawn(land, facing_deg=95)


if __name__ == "__main__":
    nx.reset()
    build()
    nx.save_blend("wake_fragment")
    nx.export("wake_fragment")
