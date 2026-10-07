"""家：NEXUS 的起点。醒来在床边。去别的世界的不是门，而是家里的东西：
- 床（E「睡」）→ 下沉            · 卧室的落地窗（走出去）→ 云阶
- 衣柜（走进去，拨开衣服）→ 无墙之屋  · 书房桌上摊开的书（E「翻开」）→ 回廊（博客在那里）
- 客厅边几上的花瓶（E「凑近」）→ 花房  · 餐桌上一杯水（E）→ 浅滩
唯一一扇真正的门是前门：开向院子，院子就是院子。

布局（俯视，x 向右、y 向上）：西北卧室、西南书房、东边一整间客厅兼餐厅（头顶天窗）；南墙前门 → 门廊 → 小径 → 院门。
到达点：wake（床边，也是出生点）、window（落地窗内）、door_descent（床边）、door_room（衣柜前）、
       door_procession（书桌旁）、door_glasshouse（花瓶旁）、cup（餐桌旁）。
各世界回家的门用 door_<世界> 这些名字，见 prefabs.return_door。
运行：node scripts/blender.cjs build home
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import assets as at  # noqa: E402
import nx  # noqa: E402
import prefabs as pf  # noqa: E402

EXTENT = 160
CENTER = (0, 3)

F = 0.15   # 地板顶面
H = 3.0    # 层高
T = 0.25   # 墙厚
WALL_IN = dict(a="pink_pale", b="mist", pattern="bands")
SKIRT = dict(a="rose", b="rose_deep", pattern="plain")
WOOD = dict(a="rose", b="rose_deep", pattern="bands")
WOOD_DARK = dict(a="rose_deep", b="violet", pattern="bands")
WHITE = dict(a="white", b="mist", pattern="plain")
COZY = dict(tint=0.45, a="pink_pale", b="rose")  # 真实家具偏黑的，拉向暖色


# ── 墙 ───────────────────────────────────────────

def _wall(name, s0, s1, gaps, put):
    """沿一条线砌墙；gaps：[(中心, 宽, 洞底高, 洞顶高)]，洞下砌窗台、洞上砌楣"""
    cur = s0
    for c, w, z0, z1 in sorted(gaps):
        a, b = c - w / 2, c + w / 2
        if a > cur:
            put(cur, a, F, H, True)
        if z0 > F + 0.01:
            put(a, b, F, z0, True)
        if z1 < H:
            put(a, b, z1, H, False)
        cur = b
    if cur < s1:
        put(cur, s1, F, H, True)


def wall_x(name, y, x0, x1, gaps=()):
    def put(a, b, z0, z1, floor):
        nx.box(f"{name}_{a:.2f}_{z0:.2f}", (b - a, T, z1 - z0), ((a + b) / 2, y, z0), **WALL_IN)
        if floor:
            nx.box(f"{name}_sk_{a:.2f}", (b - a, T + 0.05, 0.14), ((a + b) / 2, y, F), collide=False, **SKIRT)
    _wall(name, x0, x1, gaps, put)


def wall_y(name, x, y0, y1, gaps=()):
    def put(a, b, z0, z1, floor):
        nx.box(f"{name}_{a:.2f}_{z0:.2f}", (T, b - a, z1 - z0), (x, (a + b) / 2, z0), **WALL_IN)
        if floor:
            nx.box(f"{name}_sk_{a:.2f}", (T + 0.05, b - a, 0.14), (x, (a + b) / 2, F), collide=False, **SKIRT)
    _wall(name, y0, y1, gaps, put)


# ── 细部 ─────────────────────────────────────────

def picture(name, loc, yaw, w, h, panel, border="rose_deep"):
    """墙上的画框：loc 是画面中心，yaw 是画面朝向（画挂在墙上、正面朝屋里）"""
    g = nx.group(name, loc, (0, 0, yaw))
    nx.box(f"{name}_frame", (w + 0.12, 0.05, h + 0.12), (0, 0, -(h + 0.12) / 2), parent=g, collide=False,
           a=border, b="violet", pattern="plain")
    nx.box(f"{name}_panel", (w, 0.03, h), (0, 0.03, -h / 2), parent=g, collide=False, **panel)


def curtains(name, x, y, yaw, width, height):
    """落地窗两边的帘子：几条起伏的竖板"""
    g = nx.group(name, (x, y, F), (0, 0, yaw))
    for side in (-1, 1):
        for k in range(4):
            nx.box(f"{name}_{side}_{k}", (0.22, 0.12, height), (side * (width / 2 + 0.15 + k * 0.17), 0.12 + 0.06 * (k % 2), 0),
                   parent=g, collide=False, a="pink_pale" if k % 2 else "pink", b="rose", pattern="stripes")
    nx.box(f"{name}_rod", (width + 1.8, 0.08, 0.08), (0, 0.15, height + 0.05), parent=g, collide=False, **WOOD_DARK)


def wardrobe(name, cx, cy, yaw, to, at_name):
    """衣柜：开着的两扇门，里面挂着衣服；走进去就走了。cy 是柜背贴墙处，yaw=0 时柜门朝 +Y"""
    a = math.radians(yaw)
    fx, fy = -math.sin(a), math.cos(a)
    W, D, Ht = 1.8, 0.9, 2.35
    g = nx.group(name, (cx, cy, F), (0, 0, yaw))
    st = dict(a="lilac_pale", b="lilac", pattern="tiles")
    nx.box(f"{name}_back", (W, 0.06, Ht), (0, 0.03, 0), parent=g, **st)
    for s in (-1, 1):
        nx.box(f"{name}_side{s}", (0.06, D, Ht), (s * (W / 2 - 0.03), D / 2, 0), parent=g, **st)
    nx.box(f"{name}_top", (W, D, 0.08), (0, D / 2, Ht - 0.08), parent=g, **st)
    nx.box(f"{name}_crown", (W + 0.12, D + 0.08, 0.1), (0, D / 2, Ht), parent=g, **WOOD)
    nx.box(f"{name}_inside", (W - 0.12, 0.02, Ht - 0.2), (0, 0.07, 0.05), parent=g, collide=False,
           a="violet_deep", b="violet", pattern="plain")
    # 两扇门开着，贴向两侧
    for s in (-1, 1):
        h = nx.group(f"{name}_hinge{s}", (s * W / 2, D, 0), (0, 0, s * 105))
        h.parent = g
        nx.box(f"{name}_door{s}", (W / 2 - 0.02, 0.05, Ht - 0.1), (-s * (W / 4), 0.025, 0.04), parent=h,
               a="lilac_pale", b="mist", pattern="tiles")
        nx.box(f"{name}_knob{s}", (0.05, 0.08, 0.14), (-s * (W / 2 - 0.12), 0.08, 1.05), parent=h, collide=False,
               a="gold", b="white", pattern="plain")
    # 衣杆与衣服：衣服不挡人，走进去就是拨开它们
    nx.box(f"{name}_rail", (W - 0.14, 0.05, 0.05), (0, D * 0.5, Ht - 0.35), parent=g, collide=False, **WOOD_DARK)
    r = random.Random(3)
    cols = ["pink", "blue_pale", "white", "lilac", "rose", "mist", "gold", "blue"]
    for k in range(9):
        L = r.uniform(0.75, 1.3)
        nx.box(f"{name}_cloth{k}", (0.12, r.uniform(0.42, 0.55), L), (-W / 2 + 0.2 + k * 0.175, D * 0.5, Ht - 0.4 - L),
               parent=g, collide=False, a=cols[k % len(cols)], b="mist", pattern="stripes" if k % 3 == 0 else "plain")
    nx.portal(f"portal_{name}", (cx + fx * 0.45, cy + fy * 0.45, F + 1.0), to, mode="walk", radius=0.5)
    nx.arrive(at_name, (cx + fx * 2.2, cy + fy * 2.2, F), facing_deg=yaw)


def french_window(name, x, y0, y1, to, at_name):
    """西墙上的落地窗（x 处，朝 -X 开出去）：两扇窗扇推开在屋里，帘子，窗外一小片露台；走出去就走了"""
    w = y1 - y0
    yc = (y0 + y1) / 2
    hgt = 2.55
    st = dict(a="white", b="mist", pattern="plain")
    nx.box(f"{name}_head", (T + 0.08, w + 0.2, 0.12), (x, yc, F + hgt), **st)
    for s in (-1, 1):
        nx.box(f"{name}_jamb{s}", (T + 0.08, 0.1, hgt), (x, yc + s * (w / 2 + 0.05), F), **st)
        hinge = nx.group(f"{name}_hinge{s}", (x + T / 2, yc + s * w / 2, F), (0, 0, -90 + s * 75))
        leaf = dict(a="mist", b="blue_pale", pattern="tiles")
        nx.box(f"{name}_leaf{s}", (w / 2 - 0.04, 0.06, hgt - 0.05), (-s * (w / 4), 0, 0.02), parent=hinge, collide=False, **leaf)
    nx.box(f"{name}_sill", (0.8, w + 0.4, 0.12), (x - T / 2 - 0.4, yc, F - 0.04), **st)
    curtains(f"{name}_curtain", x + T / 2 + 0.05, yc, -90, w, hgt)
    nx.portal(f"portal_{name}", (x - 0.35, yc, F + 1.0), to, mode="walk", radius=1.05)
    nx.arrive(at_name, (x + 2.4, yc, F), facing_deg=-90)


def bed(cx, cy):
    """床：床头朝北（+Y）。床架、床头板、床尾板、床垫、被子（两侧与床尾垂下）、翻折的被头、两只枕头、床尾搭着一条毯子"""
    L, W = 2.2, 1.85
    y0, y1 = cy - L / 2, cy + L / 2
    nx.box("bed_frame", (W + 0.08, L, 0.32), (cx, cy, F), **WOOD)
    nx.box("bed_head", (W + 0.12, 0.1, 1.15), (cx, y1 + 0.02, F), **WOOD)
    nx.box("bed_head_cap", (W + 0.22, 0.16, 0.08), (cx, y1 + 0.02, F + 1.15), **WOOD_DARK)
    for i in range(5):
        nx.box(f"bed_head_slat{i}", (0.1, 0.03, 0.55), (cx - 0.7 + i * 0.35, y1 - 0.04, F + 0.45), collide=False,
               a="rose_deep", b="rose", pattern="plain")
    nx.box("bed_foot", (W + 0.12, 0.1, 0.62), (cx, y0 - 0.02, F), **WOOD)
    top = F + 0.32
    nx.box("bed_mattress", (W - 0.05, L - 0.12, 0.24), (cx, cy, top), **WHITE)
    m = top + 0.24
    quilt = dict(a="blue_pale", b="white", pattern="tiles")
    ql = 1.45
    qc = y0 + 0.08 + ql / 2
    nx.box("bed_quilt", (W + 0.06, ql, 0.1), (cx, qc, m), **quilt)
    for sx in (-1, 1):
        nx.box(f"bed_quilt_side{sx}", (0.06, ql, 0.42), (cx + sx * (W / 2 + 0.03), qc, m - 0.32), collide=False, **quilt)
    nx.box("bed_quilt_fold", (W + 0.06, 0.26, 0.15), (cx, qc + ql / 2 - 0.05, m), collide=False, a="white", b="blue_pale", pattern="plain")
    for i, (dx, r) in enumerate([(-0.45, 4), (0.42, -6)]):
        nx.box(f"bed_pillow{i}", (0.72, 0.42, 0.17), (cx + dx, y1 - 0.32, m), rot=(0, 0, r), collide=False,
               a="white" if i == 0 else "pink_pale", b="mist", pattern="plain")
    nx.box("bed_cushion", (0.36, 0.14, 0.32), (cx + 0.05, y1 - 0.55, m + 0.02), rot=(-18, 0, 10), collide=False,
           a="pink", b="rose", pattern="stripes")
    blanket = dict(a="pink", b="pink_pale", pattern="stripes")
    nx.box("bed_throw", (W + 0.1, 0.55, 0.05), (cx, y0 + 0.4, m + 0.1), collide=False, **blanket)
    nx.box("bed_throw_drop", (W + 0.1, 0.05, 0.3), (cx, y0 + 0.1, m - 0.2), collide=False, **blanket)


def ceiling_lamp(name, x, y):
    at.asset(name, "modern_ceiling_lamp_01", (x, y, H - 0.45), height=0.45, collide=False, shadow=False, res=256)


# ── 世界 ─────────────────────────────────────────

def build(extent=EXTENT):
    rnd = random.Random(17)
    nx.into("env")
    nx.sun((0.3, -0.45, 0.85))
    nx.atmosphere("blank")
    nx.spawn((-3.4, 6.3, F), facing_deg=70)
    nx.arrive("wake", (-3.4, 6.3, F), facing_deg=70)
    nx.box("ground", (extent, extent, 1.0), (CENTER[0], CENTER[1], -1.0), a="mist", b="green", pattern="grain")
    nx.box("floor_west", (8.25, 10.25, F), (-5.0, 5.0, 0), a="rose", b="pink", pattern="bands")
    nx.box("floor_east", (10.1, 10.25, F), (4.0, 5.0, 0), a="pink", b="rose", pattern="tiles")

    # ── 墙 ──
    nx.into("walls")
    wall_x("wall_s", 0.0, -9.125, 9.125, gaps=[(-5.5, 1.4, F + 0.9, F + 2.2), (4.0, 1.3, F, F + 2.3),
                                              (1.5, 1.6, F + 0.9, F + 2.2), (7.0, 1.6, F + 0.9, F + 2.2)])
    wall_x("wall_n", 10.0, -9.125, 9.125, gaps=[(-4.0, 1.4, F + 1.0, F + 2.2), (4.0, 2.4, F + 0.9, F + 2.3)])
    wall_y("wall_e", 9.0, 0, 10.0, gaps=[(5.0, 2.6, F + 0.8, F + 2.4)])
    wall_y("wall_w", -9.0, 0, 10.0, gaps=[(2.2, 1.4, F + 0.9, F + 2.2), (7.6, 2.0, F, F + 2.55)])
    wall_y("wall_mid", -1.0, 0, 10.0, gaps=[(2.2, 1.3, F, F + 2.3), (7.6, 1.3, F, F + 2.3)])
    wall_x("wall_bs", 4.5, -9.0, -1.0, gaps=[(-2.6, 1.2, F, F + 2.3)])
    # 室内门洞的门套
    for name, loc, yaw in [("jamb_bed", (-1.0, 7.6, F), 90), ("jamb_study", (-1.0, 2.2, F), 90), ("jamb_bs", (-2.6, 4.5, F), 0)]:
        pf.frame(name, loc, yaw, w=1.3 if name != "jamb_bs" else 1.2, h=2.3, depth=T + 0.06, t=0.08, kind="door", **WHITE)
    # 装饰窗（不能走）
    for name, loc, yaw, w, hh in [("win_study", (-9.0, 2.2, F + 0.9), 90, 1.4, 1.3), ("win_bed_n", (-4.0, 10.0, F + 1.0), 0, 1.4, 1.2),
                                  ("win_liv_n", (4.0, 10.0, F + 0.9), 0, 2.4, 1.4), ("win_liv_e", (9.0, 5.0, F + 0.8), 90, 2.6, 1.6),
                                  ("win_s1", (-5.5, 0.0, F + 0.9), 0, 1.4, 1.3), ("win_s2", (1.5, 0.0, F + 0.9), 0, 1.6, 1.3),
                                  ("win_s3", (7.0, 0.0, F + 0.9), 0, 1.6, 1.3)]:
        pf.frame(name, loc, yaw, w=w, h=hh, depth=T + 0.08, t=0.07, kind="window", **WHITE)

    # ── 天花板：客厅中间开天窗；客厅下有几根梁 ──
    nx.into("ceiling")
    C = dict(a="white", b="mist", pattern="tiles")
    nx.box("ceil_west", (8.25, 10.25, 0.22), (-5.0, 5.0, H), **C)
    nx.box("ceil_e_s", (10.1, 3.6, 0.22), (4.0, 1.8, H), **C)
    nx.box("ceil_e_n", (10.1, 3.0, 0.22), (4.0, 8.5, H), **C)
    nx.box("ceil_e_w", (3.0, 3.4, 0.22), (0.5, 5.3, H), **C)
    nx.box("ceil_e_e", (3.1, 3.4, 0.22), (7.45, 5.3, H), **C)
    for i, x in enumerate([0.3, 2.3, 5.7, 7.7]):
        nx.box(f"beam{i}", (0.22, 10.0, 0.26), (x, 5.0, H - 0.26), collide=False, **WOOD)
    nx.box("skylight_frame_w", (0.18, 3.4, 0.3), (2.05, 5.3, H - 0.05), collide=False, **WOOD_DARK)
    nx.box("skylight_frame_e", (0.18, 3.4, 0.3), (5.95, 5.3, H - 0.05), collide=False, **WOOD_DARK)

    # ── 卧室（西北）：床、床头柜、衣柜、落地窗 ──
    nx.into("bedroom")
    bed(-5.6, 8.75)
    nx.portal("portal_bed", (-5.6, 8.4, F + 0.8), "descent", mode="key", title="睡", radius=1.3)
    nx.arrive("door_descent", (-4.0, 6.9, F), facing_deg=-120)
    for i, x in enumerate([-7.4, -3.8]):
        nx.box(f"nightstand{i}", (0.55, 0.45, 0.55), (x, 9.45, F), **WOOD)
        nx.box(f"nightstand{i}_drawer", (0.45, 0.02, 0.16), (x, 9.21, F + 0.3), collide=False, a="rose_deep", b="rose", pattern="plain")
    at.asset("alarm_clock", "alarm_clock_01", (-3.8, 9.45, F + 0.55), rot=(0, 0, 200), height=0.13, collide=False, res=256)
    at.asset("oil_lamp", "vintage_oil_lamp", (-7.4, 9.45, F + 0.55), height=0.38, collide=False, res=256)
    nx.box("rug_bed", (3.4, 2.4, 0.03), (-5.6, 6.6, F), collide=False, a="blue_pale", b="white", pattern="stripes")
    wardrobe("wardrobe", -7.4, 4.63, 0, "room", "door_room")
    french_window("french", -9.0, 6.6, 8.6, "isles", "window")
    picture("pic_bed1", (-1.14, 9.0, F + 2.0), -90, 0.7, 0.9, dict(a="blue_pale", b="pink_pale", pattern="bands"))
    picture("pic_bed2", (-1.14, 5.8, F + 1.9), -90, 0.5, 0.5, dict(a="pink_pale", b="gold", pattern="grain"))
    at.asset("bed_plant", "potted_plant_04", (-1.6, 9.4, F), height=1.1, res=256)
    ceiling_lamp("lamp_bed", -5.6, 6.8)

    # ── 书房（西南）：书桌上摊开的书、书架、摇椅 ──
    nx.into("study")
    nx.box("desk_top", (0.8, 1.6, 0.05), (-8.45, 2.2, F + 0.72), **WOOD)
    for i, (dx, dy) in enumerate([(-0.33, -0.72), (-0.33, 0.72), (0.33, -0.72), (0.33, 0.72)]):
        nx.box(f"desk_leg{i}", (0.07, 0.07, 0.72), (-8.45 + dx, 2.2 + dy, F), **WOOD_DARK)
    top = F + 0.77
    # 摊开的书：两页微微拱起
    nx.box("book_cover", (0.36, 0.52, 0.02), (-8.4, 2.25, top), rot=(0, 0, 8), collide=False, a="violet", b="violet_deep", pattern="plain")
    for s in (-1, 1):
        nx.box(f"book_page{s}", (0.17, 0.48, 0.03), (-8.4 + s * 0.085, 2.25, top + 0.02), rot=(0, s * -6, 8), collide=False,
               a="white", b="mist", pattern="bands")
    nx.portal("portal_book", (-8.4, 2.25, top + 0.3), "procession", mode="key", title="翻开", radius=0.9)
    nx.arrive("door_procession", (-6.4, 2.2, F), facing_deg=90)
    at.asset("desk_lamp", "desk_lamp_arm_01", (-8.55, 1.6, top), rot=(0, 0, 70), height=0.5, collide=False, res=256)
    at.asset("notebook", "binder_notebook", (-8.35, 2.85, top), rot=(0, 0, -20), height=0.05, collide=False, res=256)
    at.asset("desk_chair", "dining_chair_02", (-7.6, 2.2, F), rot=(0, 0, 90), height=0.9, res=256, **COZY)
    at.asset("shelf", "wooden_bookshelf_worn", (-4.6, 0.38, F), rot=(0, 0, 0), height=1.9, res=512, **COZY)
    for i, z in enumerate([0.42, 0.85, 1.3]):
        at.asset(f"books{i}", "book_encyclopedia_set_01", (-4.6 + rnd.uniform(-0.25, 0.25), 0.4, F + z), height=0.27,
                 collide=False, res=256)
    at.asset("rocking", "Rockingchair_01", (-2.6, 1.5, F), rot=(0, 0, 150), height=1.0, res=256, **COZY)
    nx.box("rug_study", (2.2, 1.6, 0.03), (-3.2, 2.2, F), collide=False, a="lilac_pale", b="pink", pattern="tiles")
    picture("pic_study", (-5.3, 4.36, F + 1.8), 180, 1.0, 0.7, dict(a="green", b="blue_pale", pattern="grain"))
    ceiling_lamp("lamp_study", -5.0, 2.3)

    # ── 客厅兼餐厅（东） ──
    nx.into("living")
    # 餐桌在天窗下，桌上一杯水
    nx.cylinder("table_leg", 0.1, 0.18, 0.7, (4.0, 5.3, F), segments=14, **WOOD_DARK)
    nx.cylinder("table_top", 0.85, 0.85, 0.06, (4.0, 5.3, F + 0.7), segments=36, **WOOD)
    nx.cylinder("glass", 0.075, 0.085, 0.2, (4.2, 5.15, F + 0.76), segments=14, collide=False, shadow=False,
                a="blue_pale", b="white", pattern="plain")
    nx.cylinder("plate", 0.18, 0.18, 0.02, (3.75, 5.5, F + 0.76), segments=20, collide=False, a="white", b="mist", pattern="plain")
    nx.portal("portal_cup", (4.2, 5.15, F + 0.9), "shoal", mode="key", title="一杯水", radius=0.9)
    nx.arrive("cup", (4.0, 3.3, F), facing_deg=0)
    for i, ang in enumerate([200, 320, 80]):
        a = math.radians(ang)
        at.asset(f"dining_chair{i}", "dining_chair_02", (4.0 + math.cos(a) * 1.25, 5.3 + math.sin(a) * 1.25, F),
                 rot=(0, 0, ang + 90), height=0.9, res=256, **COZY)
    # 沙发角（东北）
    nx.box("rug_living", (3.8, 2.8, 0.03), (6.6, 8.0, F), collide=False, a="blue_pale", b="lilac_pale", pattern="stripes")
    at.asset("lounge", "mid_century_lounge_chair", (5.4, 8.9, F), rot=(0, 0, 200), height=0.85, res=256)
    at.asset("armchair", "modern_arm_chair_01", (8.1, 7.6, F), rot=(0, 0, 250), height=1.0, res=256, **COZY)
    nx.box("coffee_table", (1.1, 0.6, 0.38), (6.6, 7.8, F), **WOOD)
    at.asset("coffee_vase", "ceramic_vase_03", (6.4, 7.8, F + 0.38), height=0.3, collide=False, res=256)
    # 边几上的花瓶：凑近去闻 → 花房
    nx.box("side_table", (0.55, 0.55, 0.65), (8.45, 9.4, F), **WOOD)
    at.asset("vase", "antique_ceramic_vase_01", (8.45, 9.4, F + 0.65), height=0.42, collide=False, res=256)
    at.asset("vase_flowers", "flower_heliophila", (8.45, 9.4, F + 0.9), height=0.55, collide=False, shadow=False, res=256, part=0)
    nx.portal("portal_vase", (8.45, 9.4, F + 1.05), "glasshouse", mode="key", title="凑近", radius=0.9)
    nx.arrive("door_glasshouse", (7.2, 7.2, F), facing_deg=225)
    # 进门处：长凳、衣帽架、落地钟、盆栽
    at.asset("bench", "painted_wooden_bench", (1.6, 0.55, F), height=0.48, res=256)
    nx.cylinder("coat_pole", 0.04, 0.05, 1.8, (6.0, 0.5, F), segments=8, **WOOD_DARK)
    nx.cylinder("coat_base", 0.25, 0.25, 0.05, (6.0, 0.5, F), segments=16, **WOOD_DARK)
    for i, a in enumerate([30, 150, 270]):
        r = math.radians(a)
        nx.box(f"coat_hook{i}", (0.18, 0.04, 0.04), (6.0 + math.cos(r) * 0.08, 0.5 + math.sin(r) * 0.08, F + 1.72), rot=(0, 0, a),
               collide=False, **WOOD_DARK)
    nx.box("coat", (0.12, 0.38, 0.8), (6.12, 0.5, F + 0.9), rot=(0, 0, 20), collide=False, a="blue", b="blue_pale", pattern="plain")
    at.asset("clock", "vintage_grandfather_clock_01", (-0.6, 9.55, F), rot=(0, 0, 200), height=2.2, tint=0.4,
             a="pink_pale", b="rose_deep", res=512)
    at.asset("wall_clock", "wall_clock", (8.86, 2.5, F + 2.1), rot=(0, 0, -90), height=0.38, collide=False, res=256)
    at.asset("plant", "potted_plant_02", (8.4, 0.6, F), height=1.3, res=256)
    at.asset("plant2", "potted_plant_04", (-0.5, 0.5, F), height=1.0, res=256)
    picture("pic_liv1", (2.0, 9.86, F + 1.9), 180, 1.2, 0.8, dict(a="pink_pale", b="blue_pale", pattern="bands"))
    picture("pic_liv2", (-0.86, 5.0, F + 1.8), 90, 0.6, 0.8, dict(a="gold", b="white", pattern="grain"))
    picture("pic_liv3", (-0.86, 4.0, F + 2.0), 90, 0.4, 0.4, dict(a="blue", b="blue_pale", pattern="plain"))
    ceiling_lamp("lamp_liv1", 6.6, 8.0)
    ceiling_lamp("lamp_liv2", 4.0, 1.6)
    # 天窗下浮着几颗小星
    for i in range(4):
        s = nx.sprite(f"mote{i}", f"star.dot:{i + 3}", (rnd.uniform(2.6, 5.4), rnd.uniform(4.2, 6.4), rnd.uniform(1.8, 2.7)),
                      shadow=False)
        nx.behave(s, bob=0.15)

    # ── 前门、门廊、院子 ──
    nx.into("porch")
    hinge = nx.group("front_hinge", (4.65, 0.0 - T / 2, F), (0, 0, -70))
    nx.box("front_door", (1.3, 0.07, 2.28), (-0.65, -0.035, 0), parent=hinge, a="blue_pale", b="mist", pattern="tiles")
    nx.box("front_knob", (0.06, 0.12, 0.06), (-1.15, -0.1, 1.0), parent=hinge, collide=False, a="gold", b="white", pattern="plain")
    pf.frame("front_frame", (4.0, 0.0, F), 0, w=1.3, h=2.3, depth=T + 0.1, t=0.1, kind="door", **WHITE)
    nx.box("porch", (3.6, 2.4, F), (4.0, -1.2, 0), a="white", b="mist", pattern="tiles")
    nx.box("porch_step", (2.0, 0.5, 0.08), (4.0, -2.65, 0), a="mist", b="white", pattern="plain")
    nx.box("doormat", (1.0, 0.6, 0.03), (4.0, -0.7, F), collide=False, a="rose", b="rose_deep", pattern="stripes")
    for i in range(7):
        nx.cylinder(f"path{i}", 0.42, 0.42, 0.06, (4.0 + math.sin(i * 1.3) * 0.3, -3.6 - i * 1.15, 0), segments=14,
                    a="mist", b="lilac_pale", pattern="plain")
    # 篱笆：低低一圈，院门开在小径尽头
    fence = dict(a="white", b="mist", pattern="plain")
    for (x0, y0, x1, y1) in [(-13, -12, 3.0, -12), (5.0, -12, 13, -12), (13, -12, 13, 15), (13, 15, -13, 15), (-13, 15, -13, -12)]:
        L = math.hypot(x1 - x0, y1 - y0)
        yaw = math.degrees(math.atan2(y1 - y0, x1 - x0))
        n = int(L / 1.2)
        for k in range(n + 1):
            t = k / max(1, n)
            nx.box(f"fence_post_{x0}_{y0}_{k}", (0.12, 0.12, 0.9), (x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, 0), rot=(0, 0, yaw), **fence)
        for z in (0.35, 0.72):
            nx.box(f"fence_rail_{x0}_{y0}_{z}", (L, 0.07, 0.1), ((x0 + x1) / 2, (y0 + y1) / 2, z), rot=(0, 0, yaw), **fence)
    nx.box("mailbox_post", (0.1, 0.1, 1.05), (2.4, -11.6, 0), **WOOD_DARK)
    nx.box("mailbox", (0.32, 0.5, 0.26), (2.4, -11.6, 1.05), a="blue", b="blue_pale", pattern="plain")
    at.asset("street_lamp", "street_lamp_01", (5.6, -11.5, 0), rot=(0, 0, 90), height=3.6, res=256)
    at.asset("planter", "planter_box_01", (7.0, -0.55, 0), height=0.45, res=256)
    at.asset("planter2", "planter_box_01", (-5.5, -0.55, 0), height=0.45, res=256)

    # ── 院子里的树与花 ──
    nx.into("garden")
    for i, (x, y, name) in enumerate([(-11, 3, "tree_island@32"), (-11.5, 11.5, "quiver@32"), (10.8, 12.5, "tree_island_b@32"),
                                      (11, -6, "quiver_b@32"), (-9, -8.5, "tree_island@32"), (2, 13, "quiver@32")]):
        nx.sprite(f"tree{i}", name, (x, y, 0), face=True)
    for i, (x, y, name) in enumerate([(-11.5, 6.5, "fern@32"), (-10.6, 0.4, "nettle@32"), (7.8, -3.5, "weed_b@32"),
                                      (-3.0, -3.4, "periwinkle@32"), (11.5, 3, "fern@32"), (-6.5, 12.3, "weed@32"),
                                      (0.5, -3.6, "nettle@32"), (11.0, 9.0, "periwinkle@32")]):
        nx.sprite(f"flowerbed{i}", name, (x, y, 0), face=True)
    pf.paper_scatter("grass", ["grass.clump:{}", "grass.clump:{}", "flower:{}", "grass.flowered:{}"], CENTER, 6, 13, 40, seed=5,
                     avoid=lambda x, y: (-9.6 < x < 9.6 and -3.2 < y < 10.6) or (2.8 < x < 5.2 and y < -3))
    pf.paper_scatter("far", ["tree:{}", "tree:{}", "bush:{}"], CENTER, 30, 65, 26, seed=6, shadow=True)


if __name__ == "__main__":
    nx.reset()
    build()
    nx.save_blend("home")
    nx.export("home")
