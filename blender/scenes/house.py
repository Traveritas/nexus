"""梦里的家 · 原型（house）：docs/home.md 的「核心」与「家家家」（样板见 mockup/home-01）。

核心：大门进玄关，玄关通客厅；客厅一侧的宽口进走廊，走廊往里依次是卧室、储物间、浴室，
尽头那扇平时不开的门在最深处（北）。天花板 2.5m。永远是夜里：天是星纸（night），灯一直亮着（atmosphere lamps），
暖光一圈圈落在近处，远处的角落是暗的；月光从客厅西墙的落地窗斜进来。
每一扇门都能开关（走近按 E；prefabs.door），门扇开到底贴着旁边的墙，家具都让开门扇转过的那块地方。

通往浅梦各世界的东西（gates()；docs/home.md「出入口」）：
- 床 E「睡」→ 下沉；衣柜（打开柜门）走进去 → 长影；书桌上的书 E「翻开」→ 断梯；
- 落地窗推开、走出去 → 光斑；边几上的花瓶 E「凑近」→ 花房；茶几上的一杯水 E → 浅滩；
- 茶几上平放着罗盘（物品：地图）；从现实的床「睡」进来落在床边（到达点 wake）；
- 大门关着；推开门外面就是原野（house_out），门洞外一道缝（nx.seam），走过门槛就站在原野上，不转场。

家家家：走廊尽头那扇门后，往北一条过道，七扇门一扇比一扇小、一扇比一扇歪，一扇扇推开；
然后是 3 × 4 间和卧室一样大的房间（4.2 × 4.6m），全是家里的家具，越往北、越往两边越错乱——
多了一把椅子、换了位置、转了、浮起来、斜着、倒挂在天花板上；最深处西北角那间和卧室一模一样（门关着）。
东边一扇循环口（打得开，门外先挡着），最北那间的北门后面又是一串更小更歪的门，最后一扇过不去。

布局（俯视，x 向右、y 向上＝北）：核心 x 0…8.8、y −1.8…10；过道 y 10…24；房间网格 x −1.2…11.4、y 24…42.4。
运行：node scripts/blender.cjs build house，网页 ?world=house
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import furniture as fu  # noqa: E402
import nx  # noqa: E402
import prefabs as pf  # noqa: E402
import shapes as sh  # noqa: E402

EXTENT = 90
CENTER = (5, 20)

F = 0.15      # 地板面
H = 2.5       # 层高（地板面到天花板）
T = 0.16      # 墙厚
h = T / 2
CT = 0.12     # 天花板厚
LAP = 0.015   # 门扇关着时压住门套多少（两边、顶上）

WALL = dict(a="pink_pale", b="mist", pattern="grain")
WALL_MID = dict(a="lilac_pale", b="pink_pale", pattern="grain")
WALL_DEEP = dict(a="blue_pale", b="lilac_pale", pattern="stripes")
TILE = dict(a="white", b="blue_pale", pattern="tiles")
TRIM = dict(a="white", b="mist", pattern="plain")
CEIL = dict(a="white", b="mist", pattern="plain")
FLOOR_WOOD = dict(a="rose", b="rose_deep", pattern="bands")
FLOOR_WOOD2 = dict(a="pink", b="rose", pattern="bands")
FLOOR_TILE = dict(a="pink_pale", b="white", pattern="tiles")
FLOOR_STONE = dict(a="mist", b="lilac_pale", pattern="tiles")
WOOD = dict(a="rose", b="rose_deep", pattern="bands")
WOOD_DARK = dict(a="rose_deep", b="violet", pattern="bands")
DOOR = dict(a="blue_pale", b="mist", pattern="tiles")
SILL = dict(a="rose_deep", b="rose", pattern="plain")
WARM = "#ffd2a0"
COOL = "#dfe6ff"


# ── 墙、门、窗 ────────────────────────────────────

def wall(name, axis, at, s0, s1, gaps=(), top=H, style=WALL):
    """一段墙：axis="x" 沿 x（在 y=at），"y" 沿 y（在 x=at），从 s0 到 s1。
    gaps：[(中心, 宽, 洞底, 洞顶)]，洞底、洞顶是离地板面的高度；洞下砌窗台、洞上砌楣"""
    def put(a, b, z0, z1):
        if b - a < 0.005 or z1 - z0 < 0.005:
            return
        if axis == "x":
            nx.box(f"{name}_{a:.2f}_{z0:.2f}", (b - a, T, z1 - z0), ((a + b) / 2, at, F + z0), **style)
        else:
            nx.box(f"{name}_{a:.2f}_{z0:.2f}", (T, b - a, z1 - z0), (at, (a + b) / 2, F + z0), **style)
    cur = s0
    for c, w, g0, g1 in sorted(gaps):
        a, b = c - w / 2, c + w / 2
        put(cur, a, 0, top)
        put(a, b, 0, g0)
        put(a, b, g1, top)
        cur = b
    put(cur, s1, 0, top)


def doorway(name, axis, at, c, w=0.9, hgt=2.1):
    """门洞的门套（每边让 1cm，免得和墙的端面叠在一起）与门槛（盖住两块地板的接缝）"""
    loc = (c, at, F) if axis == "x" else (at, c, F)
    # 门套离地板 2mm：两块地板在墙下接缝，门套和墙的底面不能叠在同一平面上
    pf.frame(f"{name}_trim", (loc[0], loc[1], F + 0.002), 0 if axis == "x" else 90, w=w - 0.02, h=hgt - 0.012, depth=T + 0.06, t=0.07,
             kind="door", **TRIM)
    size = (w - 0.02, T + 0.04, 0.015) if axis == "x" else (T + 0.04, w - 0.02, 0.015)
    nx.box(f"{name}_sill", size, loc, collide=False, **SILL)


def door_in(name, axis, at, c, w=0.9, hgt=2.1, into=1, hinge=-1, start_open=False, swing_deg=90, style=DOOR, block=False):
    """墙上的门：门洞（门套、门槛）＋ 一扇能开关的门。axis / at / c 同 wall 的门洞（墙也要在 c 留出宽 w 的洞）。
    into：门往墙的哪一边开（+1 ＝ +y 或 +x 那边）；hinge：铰链在门洞的哪一头（−1 ＝ 坐标小的那头）。
    门扇关着时挡在开向那一侧的墙面外，开到底贴着旁边的墙（门开在房间角上时）。
    block：门洞里一块看不见的挡板（门外还什么都没有：大门、循环口）"""
    doorway(name, axis, at, c, w, hgt)
    # 门扇贴在门套外面（离 2mm，不和门套的面叠在一起），两边和顶上都压住门套 LAP，关着时看不见缝
    off = h + 0.03 + 0.0225 + 0.002
    half = w / 2 - 0.01 + LAP
    if axis == "x":
        hx, hy = c + hinge * half, at + into * off
        closed = 180 if hinge > 0 else 0
        target = 90 if into > 0 else -90
        mid = (c, at, F + 1.3)
    else:
        hx, hy = at + into * off, c + hinge * half
        closed = -90 if hinge > 0 else 90
        target = 0 if into > 0 else 180
        mid = (at, c, F + 1.3)
    swing = (((target - closed + 180) % 360) - 180) * swing_deg / 90
    # 底边离地 1cm（大门的门缝漏光）；顶上压住门套（门洞顶在 hgt − 1cm）
    pf.door(name, (hx, hy, F + 0.01), closed, swing, w=2 * half, h=hgt - 0.02 + LAP, start_open=start_open, at=mid, radius=1.3,
            style=style)
    if block:
        size = (w, 0.04, hgt) if axis == "x" else (0.04, w, hgt)
        nx.collider_only(nx.box(f"{name}_block", size, (mid[0], mid[1], F)))


FRONT_W, FRONT_H = 1.0, 2.1
FRONT_SEAM = h + 0.03 + 0.012   # 缝离墙中线多远：门套外面再让 1cm 多


def front_door(x, y, z):
    """大门：门洞中心在 (x, y)（墙的中线上）、地面在 z，往 +y 开。门外的原野（house_out）里立着同一扇，
    两边的缝把它们对齐，所以两边都用这一份"""
    global F
    keep, F = F, z
    try:
        door_in("d_front", "x", y, x, FRONT_W, FRONT_H, into=1, hinge=-1)
    finally:
        F = keep


def window(name, axis, at, c, w, z0, z1):
    """窗：窗套带窗台与十字棂；洞里一块看不见的挡板（不能从窗口出去）"""
    loc = (c, at, F + z0) if axis == "x" else (at, c, F + z0)
    pf.frame(f"{name}_trim", loc, 0 if axis == "x" else 90, w=w - 0.02, h=z1 - z0 - 0.01, depth=T + 0.08, t=0.06, kind="window", **TRIM)
    size = (w, 0.04, z1 - z0) if axis == "x" else (0.04, w, z1 - z0)
    nx.collider_only(nx.box(f"{name}_block", size, loc))


def picture(name, loc, yaw, w, hh, panel, border="rose_deep"):
    """墙上的画框：loc 是画面中心，yaw 是画面朝向"""
    g = nx.group(name, loc, (0, 0, yaw))
    nx.box(f"{name}_frame", (w + 0.1, 0.04, hh + 0.1), (0, 0, -(hh + 0.1) / 2), parent=g, collide=False, a=border, b="violet", pattern="plain")
    nx.box(f"{name}_panel", (w, 0.02, hh), (0, 0.025, -hh / 2), parent=g, collide=False, **panel)


def room(name, x0, y0, x1, y1, floor, hgt=H, inset=0.0):
    """一间房的地板与天花板（按墙的中线，两间房在墙下接上）。inset：天花板四边缩进墙里一点
    （隔壁天花板高低不一时，矮的那段墙的端面不和高的那块天花板的边叠在一起）"""
    nx.box(f"{name}_floor", (x1 - x0, y1 - y0, F), ((x0 + x1) / 2, (y0 + y1) / 2, 0), **floor)
    nx.box(f"{name}_ceil", (x1 - x0 - 2 * inset, y1 - y0 - 2 * inset, CT), ((x0 + x1) / 2, (y0 + y1) / 2, F + hgt), **CEIL)


def inner(x0, y0, x1, y1, hgt=H):
    """房间里面的盒子：灯只照这里。比墙面往外让 10cm——墙面的纹素中心落在墙面前后半格，
    让少了墙就照不亮；又不到墙的另一面（墙厚 16cm），隔壁照不到"""
    m = h - 0.1
    return (x0 + m, y0 + m, F - 0.1, x1 - m, y1 - m, F + hgt + 0.1)


def ceiling_light(name, x, y, box, hgt=H, power=1.8, radius=3.8, color=WARM):
    """吸顶灯：一只扁圆的灯，亮着"""
    zc = F + hgt
    nx.cylinder(f"{name}_base", 0.2, 0.2, 0.04, (x, y, zc - 0.04), segments=12, collide=False, shadow=False, **TRIM)
    nx.cylinder(f"{name}_dome", 0.12, 0.17, 0.06, (x, y, zc - 0.1), segments=12, collide=False, shadow=False, emit=1.0,
                a="white", b="mist", pattern="plain")
    nx.lamp(f"{name}_light", (x, y, zc - 0.2), color, radius, power, down=80, leak=0.45, box=box)


def lit_table_lamp(name, x, y, z, box, power=2.4, radius=3.8, shade="pink_pale", height=0.45):
    """小台灯（亮着）＋ 它的光：罩子上下开口，下口亮"""
    fu.table_lamp(name, (x, y, z), height=height, shade=shade, lit=True)
    nx.lamp(f"{name}_light", (x, y, z + height * 0.75), WARM, radius, power, down=62, up=40, leak=0.5, up_power=0.5, box=box)


def lit_floor_lamp(name, x, y, box, power=2.6, radius=4.4, z=F):
    fu.floor_lamp(name, (x, y, z), lit=True)
    nx.lamp(f"{name}_light", (x, y, z + 1.38), WARM, radius, power, down=58, up=45, leak=0.3, up_power=0.6, box=box)


def lit_pendant(name, x, y, zc, box, drop=0.6, power=2.6, radius=4.0):
    fu.pendant(name, (x, y, zc), drop=drop, shade="pink_pale", lit=True)
    nx.lamp(f"{name}_light", (x, y, zc - drop - 0.12), WARM, radius, power, down=50, leak=0.08, edge=8, box=box)


def curtain(name, x, y, yaw, n, height, side=1):
    """帘子：几条起伏的竖板，挂在窗的一边"""
    g = nx.group(name, (x, y, F), (0, 0, yaw))
    for k in range(n):
        nx.box(f"{name}_{k}", (0.2, 0.1, height - 0.04 * (k % 2)), (side * k * 0.16, 0.06 * (k % 2), 0), parent=g, collide=False,
               a="pink_pale" if k % 2 else "pink", b="rose", pattern="stripes")


def low_table(name, loc, size=(1.0, 0.55, 0.4), parent=None):
    """茶几 / 边几：一块厚板、四条腿"""
    x, y, z = loc
    sx, sy, sz = size
    nx.box(f"{name}_top", (sx, sy, 0.06), (x, y, z + sz - 0.06), parent=parent, **WOOD)
    for i, (dx, dy) in enumerate([(-1, -1), (1, -1), (-1, 1), (1, 1)]):
        nx.box(f"{name}_leg{i}", (0.06, 0.06, sz - 0.06), (x + dx * (sx / 2 - 0.06), y + dy * (sy / 2 - 0.06), z), parent=parent, **WOOD_DARK)


# ── 卧室里的东西（核心的卧室和家家家里那间一样的，用同一份） ──

BED_W, BED_D = 4.2, 4.6   # 卧室（墙的中线）


def bedroom_things(p, ox, oy):
    """卧室：ox, oy 是卧室西南角（墙的中线）；门在东墙南头（往里开，贴着南墙），窗在西墙。
    床头靠北墙，两边床头柜，左边一盏亮着的台灯、右边一只闹钟；窗下的书桌空着（书的位置），台灯照着那块空桌面；
    南墙西头一只衣柜（柜门能开关），东头一只书架；床头上方一幅画"""
    def at(u, v):
        return (ox + u, oy + v)
    box = inner(ox, oy, ox + BED_W, oy + BED_D)
    fu.bed(f"{p}bed", (*at(2.5, 3.31), F), 0)
    fu.nightstand(f"{p}nightstand_l", (*at(1.15, 4.28), F), 0)
    lit_table_lamp(f"{p}bed_lamp", *at(1.15, 4.3), F + 0.58, box, power=2.6, radius=4.2)
    fu.nightstand(f"{p}nightstand_r", (*at(3.84, 4.28), F), 0)
    fu.alarm_clock(f"{p}clock", (*at(3.84, 4.28), F + 0.58), 190)
    fu.desk(f"{p}desk", (*at(0.36, 2.5), F), -90)
    fu.desk_lamp(f"{p}desk_lamp", (*at(0.25, 2.95), F + 0.74), -167, lit=True)
    nx.lamp(f"{p}desk_lamp_light", (*at(0.4, 2.6), F + 1.12), WARM, 1.9, 1.5, down=45, leak=0.15, reach=0.38, box=box)
    fu.chair(f"{p}desk_chair", (*at(1.05, 2.5), F), 90, "dining", fabric="lilac")
    # 核心卧室的衣柜通往长影（打开柜门、拨开衣服走进去）；家家家里那间一样的只是衣柜
    pf.wardrobe(f"{p}wardrobe", (*at(1.15, 0.125), F), 0, None if p else "longshadow", None if p else "house",
                land=1.5, interactive=True)
    fu.bookshelf(f"{p}shelf", (*at(2.65, 0.27), F), 0, w=0.8, h=1.95, seed=2)
    nx.box(f"{p}rug", (0.55, 1.6, 0.02), (*at(3.8, 2.8), F), collide=False, a="blue_pale", b="white", pattern="stripes")
    picture(f"{p}pic", (*at(2.5, BED_D - h - 0.025), F + 1.75), 180, 0.8, 0.45, dict(a="blue_pale", b="pink_pale", pattern="bands"))


# ── 核心 ─────────────────────────────────────────

def core():
    nx.into("core")
    room("living", 0, 0, 6.0, 4.8, FLOOR_WOOD2)
    room("bed", 0, 4.8, 4.2, 9.4, FLOOR_WOOD)
    room("hall", 4.2, 4.8, 6.0, 10.0, FLOOR_WOOD)
    room("store", 6.0, 4.8, 8.4, 7.2, FLOOR_STONE)
    room("bath", 6.0, 7.2, 8.8, 10.0, dict(a="white", b="blue_pale", pattern="tiles"))
    room("entry", 3.4, -1.8, 5.4, 0, FLOOR_STONE)

    # 墙：转角处一边伸出半个墙厚盖住角，T 字口处停在另一面墙的墙面上（不叠出共面）
    nx.into("walls")
    wall("w_entry_s", "x", -1.8, 3.4 - h, 5.4 + h, gaps=[(4.1, 1.0, 0, 2.1)])
    wall("w_living_s", "x", 0, 0 - h, 6.0 + h, gaps=[(4.4, 1.2, 0, 2.3)])
    wall("w_living_n", "x", 4.8, 0 + h, 4.2 + h)
    wall("w_store_s", "x", 4.8, 6.0 + h, 8.4 + h)
    wall("w_store_n", "x", 7.2, 6.0 + h, 8.8 + h)
    wall("w_bed_n", "x", 9.4, 0 - h, 4.2 - h)
    wall("w_north", "x", 10.0, 4.2 - h, 8.8 + h, gaps=[(5.1, 0.9, 0, 2.1), (7.6, 0.6, 1.5, 2.1)])
    wall("w_west", "y", 0, 0 + h, 9.4 - h, gaps=[(2.4, 2.2, 0, 2.3), (7.3, 0.9, 0.95, 2.15)])
    wall("w_bed_e", "y", 4.2, 4.8 + h, 10.0 - h, gaps=[(5.41, 0.9, 0, 2.1)])
    wall("w_east", "y", 6.0, 0 + h, 10.0 - h, gaps=[(5.38, 0.8, 0, 2.1), (7.78, 0.8, 0, 2.1)])
    wall("w_store_e", "y", 8.4, 4.8 + h, 7.2 - h)
    wall("w_bath_e", "y", 8.8, 7.2 + h, 10.0 - h)
    wall("w_entry_w", "y", 3.4, -1.8 + h, 0 - h)
    wall("w_entry_e", "y", 5.4, -1.8 + h, 0 - h)

    # 门：卧室的开着（醒来能看见走廊），别的都关着；尽头那扇平时不开
    nx.into("doors")
    door_in("d_bed", "y", 4.2, 5.41, 0.9, into=-1, hinge=-1, start_open=True)
    door_in("d_store", "y", 6.0, 5.38, 0.8, into=1, hinge=-1)
    door_in("d_bath", "y", 6.0, 7.78, 0.8, into=1, hinge=-1)
    door_in("d_end", "x", 10.0, 5.1, 0.9, into=1, hinge=-1, swing_deg=100)
    # 大门：推开就是门外的原野（house_out），门洞外贴着一道缝，走过门槛就到了那边
    front_door(4.1, -1.8, F)
    # 从原野看进来只画到门里 14m（到尽头那扇门为止）：家家家的房间隔着墙，反正看不见
    nx.seam("seam_out", (4.1, -1.8 - FRONT_SEAM, F), 180, "house_out", FRONT_W - 0.02, FRONT_H - 0.01, reach=14)
    # 没有门扇的口：玄关 ↔ 客厅
    doorway("d_entry", "x", 0, 4.4, 1.2, 2.3)

    window("win_bed", "y", 0, 7.3, 0.9, 0.95, 2.15)
    window("win_bath", "x", 10.0, 7.6, 0.6, 1.5, 2.1)
    french_window()

    bedroom_things("", 0, 4.8)
    gates()
    hall()
    living()
    bath()
    store()
    entry()


def gates():
    """家里通往浅梦各世界的东西（落地窗、衣柜在 french_window / bedroom_things 里）。各自旁边是从那边回来的到达点"""
    nx.into("gates")
    # 床 → 下沉（E「睡」）；从现实睡进来、从下沉回来，都醒在床边
    nx.portal("portal_bed", (2.5, 8.11, F + 0.8), "descent", at="house", mode="key", title="睡", radius=1.3)
    nx.arrive("descent", (3.75, 7.5, F + 0.02), facing_deg=180)
    nx.arrive("wake", (3.1, 6.2, F + 0.02), facing_deg=50)
    # 书桌上摊开一本书 → 断梯（E「翻开」）：台灯照着的那块
    bx, by, bz = 0.38, 7.32, F + 0.74
    nx.box("book_cover", (0.26, 0.36, 0.012), (bx, by, bz + 0.002), collide=False, a="violet", b="violet_deep", pattern="plain")
    for s in (-1, 1):
        nx.box(f"book_page{s}", (0.115, 0.33, 0.014), (bx + s * 0.064, by, bz + 0.016), rot=(0, s * -6, 0), collide=False,
               a="white", b="mist", pattern="bands")
    nx.box("book_ribbon", (0.012, 0.012, 0.1), (bx + 0.02, by - 0.17, bz - 0.09), collide=False, a="pink", b="rose", pattern="plain")
    nx.portal("portal_book", (bx, by, bz + 0.2), "stair", at="house", mode="key", title="翻开", radius=0.9)
    nx.arrive("stair", (1.7, 6.55, F + 0.02), facing_deg=-60)
    # 边几上插着花的瓶 → 花房（E「凑近」）
    fu.vase("gate_vase", (0.4, 0.4, F + 0.6), 0.32, "round", flowers=5, seed=4, style=dict(a="pink_pale", b="white", pattern="plain"))
    nx.portal("portal_vase", (0.4, 0.4, F + 0.95), "glasshouse", at="house", mode="key", title="凑近", radius=0.9)
    nx.arrive("glasshouse", (1.1, 1.45, F + 0.02), facing_deg=-45)
    # 茶几上一杯水 → 浅滩（E「一杯水」）；旁边平放着罗盘
    gx, gy, gz = 2.62, 2.36, F + 0.42
    sh.tube("gate_glass", 0.075, 0.065, 0.2, (gx, gy, gz + 0.011), segments=16, collide=False, a="blue_pale", b="white", pattern="plain")
    nx.cylinder("gate_glass_base", 0.075, 0.075, 0.01, (gx, gy, gz + 0.001), segments=16, collide=False,
                a="white", b="blue_pale", pattern="plain")
    nx.cylinder("gate_glass_water", 0.064, 0.064, 0.14, (gx, gy, gz + 0.012), segments=16, collide=False,
                a="blue", b="blue_pale", pattern="bands")
    nx.portal("portal_glass", (gx, gy, gz + 0.35), "shoal", at="house", mode="key", title="一杯水", radius=0.9)
    nx.arrive("shoal", (2.6, 3.25, F + 0.02), facing_deg=180)
    nx.item("compass", (2.02, 2.2, gz + 0.02), "compass", get="pick")


def french_window():
    """客厅西墙的落地窗（去云阶的那扇，先不接）：两扇窗扇往屋里推开、关上；北边一挂帘子；月光从这里斜进来"""
    nx.into("living")
    c, w, hh = 2.4, 2.2, 2.3
    pf.frame("fw_trim", (0, c, F + 0.002), 90, w=w - 0.02, h=hh - 0.012, depth=T + 0.08, t=0.08, kind="door", **TRIM)
    # 窗扇贴在窗套外面、压住窗套（同 door_in）
    x = h + 0.04 + 0.025 + 0.002
    lw = w / 2 - 0.01 + LAP
    leaf = dict(a="white", b="mist", pattern="plain")
    for name, y0, closed, swing in (("fw_s", c - lw, 90, -90), ("fw_n", c + lw, -90, 90)):
        pf.door(name, (x, y0, F + 0.02), closed, swing, w=lw, h=hh - 0.03 + LAP, thick=0.05, kind="glass", at=(0.3, c, F + 1.3),
                radius=1.4, group="french", title=("推开窗", "关上窗"), style=leaf, knob_at=(lw - 0.08, 1.05))
    # 推开窗走出去 → 光斑：窗外一层膜（走近时铺满），站上窗台就走了
    nx.veil("fw_veil", w - 0.06, hh - 0.04, (-0.16, c, F + 0.01), 90, a="white", b="pink_pale")
    nx.portal("portal_sunpatch", (-0.42, c, F + 1.0), "sunpatch", at="house", mode="walk", radius=0.5)
    nx.arrive("sunpatch", (1.15, c, F + 0.02), facing_deg=-90)
    nx.box("fw_sill", (0.5, w + 0.2, 0.05), (-h - 0.25, c, F - 0.05), a="mist", b="white", pattern="plain")
    curtain("fw_curtain", 0.25, c + w / 2 + 0.24, -90, 2, hh + 0.1, side=-1)
    nx.box("fw_rod", (0.05, w + 0.5, 0.05), (0.2, c + 0.2, F + hh + 0.08), collide=False, a="rose_deep", b="violet", pattern="plain")


def hall():
    """走廊：1.8m 宽，从客厅的宽口一直到尽头那扇门"""
    nx.into("hall")
    box = inner(4.2, 4.8, 6.0, 10.0)
    ceiling_light("hall_light_s", 5.1, 6.0, box, power=1.6, radius=3.6)
    ceiling_light("hall_light_n", 5.1, 8.7, box, power=1.3, radius=3.2)
    nx.box("hall_runner", (0.9, 4.4, 0.02), (5.1, 7.45, F), collide=False, a="rose", b="pink", pattern="stripes")
    picture("pic_hall_w", (4.2 + h + 0.025, 7.6, F + 1.6), -90, 0.7, 0.5, dict(a="green", b="blue_pale", pattern="grain"))
    picture("pic_hall_e", (6.0 - h - 0.025, 6.58, F + 1.6), 90, 0.5, 0.65, dict(a="pink_pale", b="gold", pattern="grain"))


def living():
    """客厅：沙发靠南墙、电视靠北墙，中间茶几（一杯水的空位）；西南角边几（花瓶的空位）与落地灯；东墙一只矮柜、一盏台灯"""
    nx.into("living")
    box = inner(0, 0, 6.0, 4.8)
    fu.sofa("sofa", (2.3, 0.51, F), 0, fabric="pink")
    fu.tv_stand("tv", (2.3, 4.51, F), 180, lit=True)
    nx.box("rug_living", (2.4, 1.6, 0.02), (2.3, 2.3, F), collide=False, a="blue_pale", b="lilac_pale", pattern="stripes")
    low_table("coffee", (2.3, 2.3, F + 0.02))
    low_table("side_table", (0.4, 0.4, F), size=(0.45, 0.45, 0.6))
    lit_floor_lamp("floor_lamp", 0.98, 0.35, box)
    # 东墙的矮柜：柜身、顶板、两扇柜门；上面一盏台灯
    nx.box("sideboard", (0.44, 1.6, 0.72), (5.69, 2.2, F), **WOOD)
    nx.box("sideboard_top", (0.5, 1.7, 0.04), (5.67, 2.2, F + 0.72), **WOOD_DARK)
    for i, dy in enumerate((-0.4, 0.4)):
        nx.box(f"sideboard_door{i}", (0.02, 0.74, 0.56), (5.46, 2.2 + dy, F + 0.08), collide=False, a="pink_pale", b="rose", pattern="plain")
    lit_table_lamp("side_lamp", 5.69, 2.75, F + 0.76, box, power=2.0, radius=3.6)
    fu.plant("living_plant", (0.45, 4.3, F), 1.0, seed=3)
    picture("pic_sofa", (2.3, h + 0.025, F + 1.6), 0, 1.0, 0.55, dict(a="blue_pale", b="green", pattern="grain"))
    picture("pic_sideboard", (6.0 - h - 0.025, 2.2, F + 1.65), 90, 0.8, 0.5, dict(a="pink_pale", b="blue_pale", pattern="bands"))


def bath():
    nx.into("bath")
    box = inner(6.0, 7.2, 8.8, 10.0)
    # 墙裙：一圈白瓷砖（贴在墙面上，凸出 2cm），门口断开
    for name, size, loc in [
        ("tile_s", (2.64, 0.02, 1.4), (7.4, 7.29, F)),
        ("tile_n", (2.64, 0.02, 1.4), (7.4, 9.91, F)),
        ("tile_e", (0.02, 2.6, 1.4), (8.71, 8.6, F)),
        ("tile_w", (0.02, 1.62, 1.4), (6.09, 9.08, F)),
    ]:
        nx.box(name, size, loc, collide=False, **TILE)
    fu.tub("tub", (7.6, 9.5, F), 0)
    fu.toilet("toilet", (8.39, 8.3, F), 90)
    fu.sink("sink", (7.7, 7.55, F), 0)
    nx.box("mirror", (0.5, 0.03, 0.6), (7.7, 7.315, F + 1.45), collide=False, a="blue_pale", b="white", pattern="plain")
    nx.box("towel_rail", (0.04, 0.6, 0.04), (8.69, 9.0, F + 1.5), collide=False, a="pink_pale", b="white", pattern="plain")
    nx.box("towel", (0.04, 0.4, 0.5), (8.67, 9.0, F + 1.0), collide=False, a="pink", b="pink_pale", pattern="stripes")
    ceiling_light("bath_light", 7.4, 8.6, box, power=1.6, radius=3.4, color=COOL)


def store():
    """储物间：没开灯，开门以后只有走廊的光进来一点"""
    nx.into("store")
    fu.crate("crate1", (6.6, 6.85, F), 0)
    fu.crate("crate2", (6.62, 6.85, F + 0.42), 8, size=(0.5, 0.4, 0.36), style=dict(a="blue_pale", b="blue", pattern="grain"))
    fu.crate("crate3", (7.5, 6.88, F), 0, size=(0.45, 0.38, 0.9), style=dict(a="lilac_pale", b="lilac", pattern="grain"))
    # 铁架：四根立柱、三层板，板上几只盒子
    for i, (dx, dy) in enumerate([(-0.135, -0.425), (0.135, -0.425), (-0.135, 0.425), (0.135, 0.425)]):
        nx.box(f"rack_post{i}", (0.04, 0.04, 1.7), (8.16 + dx, 6.0 + dy, F), a="violet", b="violet_deep", pattern="plain")
    for k in range(3):
        nx.box(f"rack_shelf{k}", (0.29, 0.88, 0.03), (8.16, 6.0, F + 0.3 + k * 0.6), a="lilac", b="lilac_dark", pattern="plain")
        fu.crate(f"rack_box{k}", (8.16, 5.8 + 0.2 * (k % 2), F + 0.33 + k * 0.6), 90, size=(0.3, 0.24, 0.22))


def entry():
    nx.into("entry")
    box = inner(3.4, -1.8, 5.4, 0)
    fu.shoe_cabinet("shoes", (5.15, -1.0, F), 90, w=0.8)
    nx.box("coat_rail", (0.04, 0.6, 0.06), (5.29, -1.0, F + 1.75), collide=False, a="rose_deep", b="violet", pattern="plain")
    nx.box("coat", (0.1, 0.42, 0.7), (5.22, -0.95, F + 1.02), rot=(0, 0, 6), collide=False, a="blue", b="blue_pale", pattern="plain")
    nx.box("doormat", (0.9, 0.5, 0.02), (4.1, -1.3, F), collide=False, a="rose", b="rose_deep", pattern="stripes")
    ceiling_light("entry_light", 4.4, -0.9, box, power=1.3, radius=2.8)


# ── 过道：尽头那扇门后，七扇门 ────────────────────

PX0, PX1 = 4.3, 5.9     # 过道的两面墙（中线）
PY0, PY1 = 10.0, 24.0   # 从尽头那扇门到房间网格的南墙


def door_chain(prefix, ys, widths, heights, rolls, cols, last_blocked=False):
    """一串门：每道是一面歪过来的隔墙（比过道宽、比层高高，四角插进墙里、地板下、天花板上）、门套，
    和一扇关着的门（往北推开）。cols：每道隔墙的颜色"""
    for i, (y, w, hh, roll) in enumerate(zip(ys, widths, heights, rolls)):
        g = nx.group(f"{prefix}{i}", ((PX0 + PX1) / 2, y, F), (0, roll, 0))
        st = dict(a=cols[i % len(cols)], b="mist", pattern="bands")
        side = 1.25 - w / 2
        for s in (-1, 1):
            nx.box(f"{prefix}{i}_wall{s}", (side, 0.14, 3.4), (s * (w / 2 + side / 2), 0, -0.4), parent=g, **st)
        nx.box(f"{prefix}{i}_lintel", (w, 0.14, 3.0 - hh), (0, 0, hh), parent=g, **st)
        pf.frame(f"{prefix}{i}_trim", (0, 0, 0), 0, w=w - 0.02, h=hh - 0.01, depth=0.16, t=0.06, kind="door", parent=g, **TRIM)
        s = 1 if i % 2 else -1
        # 门扇贴在门套外面、压住门套（同 door_in）
        half = w / 2 - 0.01 + LAP
        pf.door(f"{prefix}{i}_door", (s * half, 0.08 + 0.0245, 0.01), 180 if s > 0 else 0, -95 * s, w=2 * half, h=hh - 0.02 + LAP,
                at=((PX0 + PX1) / 2, y, F + 1.2), radius=1.2, parent=g,
                style=dict(a=["blue_pale", "pink_pale", "lilac_pale"][i % 3], b="mist", pattern="tiles"))
        if last_blocked and i == len(ys) - 1:
            nx.collider_only(nx.box(f"{prefix}{i}_block", (1.4, 0.04, 2.4), ((PX0 + PX1) / 2, y + 0.3, F)))


def passage():
    nx.into("passage")
    room("pass", PX0, PY0, PX1, PY1, FLOOR_WOOD)
    wall("w_pass_w", "y", PX0, PY0 + h, PY1 - h)
    wall("w_pass_e", "y", PX1, PY0 + h, PY1 - h)
    n = 7
    ys = [11.6 + i * 1.8 for i in range(n)]
    # 一扇比一扇小、一扇比一扇歪；歪得有限度：门洞歪过来，头顶那一截往旁边挪 1.7·tan(歪)，人还过得去
    door_chain("pd", ys, [0.95 - i * 0.02 for i in range(n)], [2.25 - i * 0.04 for i in range(n)],
               [(1 if i % 2 else -1) * (1.0 + i * 0.65) for i in range(n)],
               ["white", "mist", "pink_pale", "lilac_pale", "pink_pale", "lilac_pale", "blue_pale"])
    # 两盏灯各只照自己那一段（两道门之间）
    ceiling_light("pass_light1", 5.1, 12.5, (4.28, 11.57, 0, 5.92, 13.43, 3), power=1.1, radius=2.8)
    ceiling_light("pass_light2", 5.1, 19.7, (4.28, 18.77, 0, 5.92, 20.63, 3), power=0.9, radius=2.6)


# ── 家家家：3 × 4 间 ──────────────────────────────

XS = [-1.2, 3.0, 7.2, 11.4]
YS = [24.0, 28.6, 33.2, 37.8, 42.4]
COLS, ROWS = 3, 4
HOME = (0, 3)       # 和卧室一样的那间：西北角（西墙、北墙在外面，和卧室一样）


def wrong(c, r):
    return min(1.0, (r + abs(c - 1) * 0.7) / 3.2)


def cell_h(c, r):
    if (c, r) == HOME:
        return H
    return round(H + 2.1 * wrong(c, r), 2)


def cell_style(w):
    return WALL if w < 0.3 else (WALL_MID if w < 0.6 else WALL_DEEP)


# 门：(沿哪条线, 第几条线, 第几段, 离这一段起点多远, 往哪边开, 铰链在哪头, 一开始开着)
# 沿 y 的线 x = XS[i]，段 j 是 YS[j]…YS[j+1]；沿 x 的线 y = YS[i]，段 j 是 XS[j]…XS[j+1]。
# 门都开在房间角上，开到底贴着旁边的墙
GRID_DOORS = [
    ("y", 1, 0, 3.95, -1, 1, True),   # 入口那间 → 西
    ("y", 2, 0, 3.95, 1, 1, True),    # 入口那间 → 东
    ("x", 1, 1, 3.55, 1, 1, True),    # 入口那间 → 北
    ("x", 1, 0, 0.65, 1, -1, True),
    ("x", 1, 2, 3.55, 1, 1, True),
    ("y", 1, 1, 2.3, -1, -1, True),   # 墙中间：东北角留给去北边那间的门
    ("y", 2, 1, 2.3, 1, -1, True),    # 墙中间：南墙角那扇门开着时贴着东墙，挡着这里
    ("x", 2, 1, 0.65, 1, -1, True),
    ("x", 2, 0, 3.55, 1, 1, False),
    ("x", 2, 2, 0.65, 1, -1, True),
    ("y", 1, 2, 3.95, -1, 1, True),
    ("y", 2, 2, 3.95, 1, 1, True),
    ("x", 3, 1, 3.55, 1, 1, True),
    ("x", 3, 2, 3.55, 1, 1, False),
    ("y", 1, 3, 0.61, -1, -1, False),  # 和卧室一样的那间：门的位置、开法都和卧室的一样；关着
    ("y", 2, 3, 2.3, 1, -1, True),
]
LOOP_DOOR = ("y", 3, 1, 1.5, 1, -1, False)   # 东墙的循环口：打得开，门外先挡着
BACK_DOOR = ("x", 4, 1, 2.1, 1, -1, False)   # 最北那间的北门：后面又是一串门
WINDOWS = {  # (沿哪条线, 第几条线, 第几段) → [(离起点多远, 宽, 洞底, 洞顶)]
    ("y", 0, 3): [(2.5, 0.9, 0.95, 2.15)],   # 和卧室一样的那间：窗在西墙，和卧室一样
    ("y", 0, 0): [(2.3, 1.0, 0.9, 2.1)],
    ("y", 3, 2): [(2.3, 0.8, 2.9, 3.7)],
    ("x", 4, 2): [(2.1, 0.9, 1.0, 2.1)],
}


def grid():
    nx.into("rooms")
    rnd = random.Random(23)
    for c in range(COLS):
        for r in range(ROWS):
            w = wrong(c, r)
            floor = FLOOR_WOOD if (c, r) == HOME or w < 0.3 else (FLOOR_TILE if w < 0.6 else FLOOR_STONE)
            room(f"r{c}{r}", XS[c], YS[r], XS[c + 1], YS[r + 1], floor, cell_h(c, r), inset=0.02)

    doors = {(d[0], d[1], d[2]): d for d in GRID_DOORS + [LOOP_DOOR, BACK_DOOR]}

    def gaps_of(axis, i, j, start):
        out = []
        d = doors.get((axis, i, j))
        if d:
            out.append((start + d[3], 0.9, 0, 2.1))
        if axis == "x" and i == 0 and j == 1:
            out.append((start + CW_MID, 1.3, 0, 2.3))  # 过道进来的口
        for g in WINDOWS.get((axis, i, j), []):
            out.append((start + g[0], *g[1:]))
        return out

    # 沿 y 的墙：一段段从节点到节点（最南、最北两头伸出半个墙厚盖住转角）；沿 x 的墙夹在中间
    for i in range(COLS + 1):
        for j in range(ROWS):
            cells = [k for k in ((i - 1, j), (i, j)) if 0 <= k[0] < COLS]
            top = max(cell_h(*k) for k in cells)
            st = WALL if HOME in cells else cell_style(sum(wrong(*k) for k in cells) / len(cells))
            s0 = YS[j] - (h if j == 0 else 0)
            s1 = YS[j + 1] + (h if j == ROWS - 1 else 0)
            wall(f"g_y{i}{j}", "y", XS[i], s0, s1, gaps=gaps_of("y", i, j, YS[j]), top=top, style=st)
    for i in range(ROWS + 1):
        for j in range(COLS):
            cells = [k for k in ((j, i - 1), (j, i)) if 0 <= k[1] < ROWS]
            top = max(cell_h(*k) for k in cells)
            st = WALL if HOME in cells else cell_style(sum(wrong(*k) for k in cells) / len(cells))
            wall(f"g_x{i}{j}", "x", YS[i], XS[j] + h, XS[j + 1] - h, gaps=gaps_of("x", i, j, XS[j]), top=top, style=st)

    nx.into("rooms_doors")
    for d in GRID_DOORS:
        axis, i, j, off, into, hinge, start_open = d
        line = XS[i] if axis == "y" else YS[i]
        c = (YS[j] if axis == "y" else XS[j]) + off
        door_in(f"gd_{axis}{i}{j}", axis, line, c, into=into, hinge=hinge, start_open=start_open)
    axis, i, j, off, into, hinge, _ = LOOP_DOOR
    door_in("gd_loop", "y", XS[i], YS[j] + off, into=into, hinge=hinge, block=True)
    axis, i, j, off, into, hinge, _ = BACK_DOOR
    door_in("gd_back", "x", YS[i], XS[j] + off, into=into, hinge=hinge)
    doorway("gd_in", "x", YS[0], XS[1] + CW_MID, 1.3, 2.3)
    for (axis, i, j), gs in WINDOWS.items():
        line = XS[i] if axis == "y" else YS[i]
        for k, g in enumerate(gs):
            window(f"gw_{axis}{i}{j}_{k}", axis, line, (YS[j] if axis == "y" else XS[j]) + g[0], g[1], g[2], g[3])

    rooms_things(rnd)
    back_chain()


CW_MID = (XS[2] - XS[1]) / 2   # 中间那一列的中线离西墙多远（过道正对着它）


def rooms_things(rnd):
    """各间的东西：u, v 是这一间里离西墙、南墙中线多远（一间 4.2 × 4.6）。门扇转过的那块地方都空着"""
    def P(c, r, u, v, z=F):
        return (XS[c] + u, YS[r] + v, z)

    def box_of(c, r):
        return inner(XS[c], YS[r], XS[c + 1], YS[r + 1], cell_h(c, r))

    def tilt(name, loc, rot):
        return nx.group(f"{name}_tilt", loc, rot)

    # (1,0) 几乎一样：客厅的那一套，摆得好好的（电视靠西墙、沙发靠东墙）
    c, r = 1, 0
    fu.tv_stand("a_tv", P(c, r, 0.29, 1.8), -90, lit=True)
    fu.sofa("a_sofa", P(c, r, 3.68, 1.8), 90, fabric="pink")
    low_table("a_coffee", P(c, r, 1.9, 1.8))
    low_table("a_side", P(c, r, 3.7, 3.05), size=(0.36, 0.36, 0.6))
    lit_floor_lamp("a_lamp", *P(c, r, 0.4, 3.0)[:2], box_of(c, r))

    # (0,0) 多了一把椅子：餐桌一角，椅子比座位多
    c, r = 0, 0
    fu.table("b_table", P(c, r, 2.0, 1.8), 0)
    for i, (u, v, yaw) in enumerate([(2.0, 1.05, 0), (2.0, 2.55, 180), (1.05, 1.8, -90), (2.95, 1.8, 90)]):
        fu.chair(f"b_chair{i}", P(c, r, u, v), yaw, "dining", fabric="blue")
    fu.chair("b_chair_x", P(c, r, 3.55, 0.5), 200, "dining", fabric="blue")
    lit_pendant("b_pendant", *P(c, r, 2.0, 1.8)[:2], F + cell_h(c, r), box_of(c, r), drop=1.0)

    # (2,0) 换了位置：床在屋子正中、横着，床头柜在床尾，衣柜面朝南墙
    c, r = 2, 0
    fu.bed("c_bed", P(c, r, 2.3, 2.15), 90)
    fu.nightstand("c_nightstand", P(c, r, 3.75, 2.15), -90)
    lit_table_lamp("c_lamp", *P(c, r, 3.75, 2.15)[:2], F + 0.58, box_of(c, r))
    pf.wardrobe("c_wardrobe", P(c, r, 2.3, 1.03), 180, None, None, open_deg=0)

    # (1,1) 转了：沙发对着北墙，电视对着沙发的背；一排餐椅对着西墙
    c, r = 1, 1
    fu.sofa("d_sofa", P(c, r, 2.1, 4.03), 0, fabric="lilac")
    fu.tv_stand("d_tv", P(c, r, 2.1, 2.6), 0, lit=True)
    for i, v in enumerate([0.6, 1.1, 1.6, 3.1, 3.6]):   # 中间让开西门
        fu.chair(f"d_chair{i}", P(c, r, 0.42, v), 90, "dining", fabric="pink")
    lit_floor_lamp("d_lamp", *P(c, r, 3.75, 3.3)[:2], box_of(c, r))

    # (0,1) 浴室搬进了客厅：浴缸在屋子中间、斜着，台灯立在浴缸里；一把扶手椅浮在半空
    c, r = 0, 1
    fu.tub("e_tub", P(c, r, 2.1, 2.2), 22)
    fu.sink("e_sink", P(c, r, 0.33, 2.6), -90)
    fu.toilet("e_toilet", P(c, r, 2.3, 0.5), 20)
    g = tilt("e_arm", P(c, r, 3.3, 0.9, F + 0.4), (0, 0, 210))
    fu.chair("e_arm", (0, 0, 0), 0, "arm", fabric="pink", parent=g)
    lit_table_lamp("e_lamp", *P(c, r, 2.1, 2.2)[:2], F + 0.38, box_of(c, r), height=0.6)

    # (2,1) 衣柜：一只靠东墙、一只靠南墙，东边那只歪着；书桌浮起来，椅子还在地上
    c, r = 2, 1
    g = tilt("f_wardrobe0", P(c, r, 4.075, 3.55), (0, 6, 90))
    pf.wardrobe("f_wardrobe0", (0, 0, 0), 0, None, None, open_deg=-35, parent=g)
    pf.wardrobe("f_wardrobe1", P(c, r, 2.0, 0.125), 0, None, None, open_deg=0)
    g = tilt("f_desk", P(c, r, 2.2, 2.7, F + 0.8), (8, -10, 15))
    fu.desk("f_desk", (0, 0, 0), 0, parent=g)
    fu.desk_lamp("f_desk_lamp", (0.3, 0.1, 0.74), 200, lit=True, parent=g)
    nx.lamp("f_desk_light", P(c, r, 2.4, 2.7, F + 1.95), WARM, 2.6, 1.6, down=70, leak=0.3, box=box_of(c, r))
    fu.chair("f_chair", P(c, r, 2.1, 2.0), 10, "dining", fabric="lilac")

    # (1,2) 浮起来：餐桌浮在半空，椅子绕着它、各歪各的（都在头顶上）；一盏吊灯从地上往上「吊」
    c, r = 1, 2
    hc = cell_h(c, r)
    g = tilt("g_table", P(c, r, 2.1, 2.3, F + 1.25), (0, 6, 20))
    fu.table("g_table", (0, 0, 0), 0, parent=g)
    for i in range(5):
        a = math.radians(i * 72 + 15)
        g = tilt(f"g_chair{i}", P(c, r, 2.1 + math.cos(a) * 1.3, 2.3 + math.sin(a) * 1.25, F + rnd.uniform(1.9, 2.8)),
                 (rnd.uniform(-30, 30), rnd.uniform(-30, 30), i * 72 + 105))
        fu.chair(f"g_chair{i}", (0, 0, 0), 0, "dining", fabric="blue", parent=g)
    lit_pendant("g_pendant", *P(c, r, 2.1, 2.3)[:2], F + hc, box_of(c, r), drop=0.9)
    g = tilt("g_floorpendant", P(c, r, 3.6, 0.6, F), (180, 0, 0))
    fu.pendant("g_floorpendant", (0, 0, 0), drop=0.5, lit=True, parent=g)
    nx.lamp("g_floorpendant_light", P(c, r, 3.6, 0.6, F + 0.7), WARM, 2.8, 1.6, up=60, leak=0.25, box=box_of(c, r))

    # (0,2) 斜着：一道楼梯沿西墙通进天花板，书架歪着靠在南墙上，椅子贴在东墙上，落地灯躺在地上
    c, r = 0, 2
    hc = cell_h(c, r)
    pf.stair_straight("i_stair", P(c, r, 0.6, 0.5), 0, 15, rise=round(hc / 15, 3), run=0.25, width=0.8, a="mist", b="lilac_pale", pattern="bands")
    for i, (u, rot) in enumerate([(1.6, (0, 14, 0)), (2.45, (0, -9, 0))]):
        g = tilt(f"i_shelf{i}", P(c, r, u, h + 0.3 + 0.16 * i), rot)
        fu.bookshelf(f"i_shelf{i}", (0, 0, 0), 0, w=0.8, seed=5 + i, parent=g)
    for i, (v, z) in enumerate([(1.4, 1.5), (2.2, 2.4), (2.9, 1.2)]):
        g = tilt(f"i_wallchair{i}", P(c, r, 4.2 - h - 0.01, v, F + z), (0, -90, 0))
        fu.chair(f"i_wallchair{i}", (0, 0, 0), 90 * i + 20, "dining", fabric="rose", parent=g)
    g = tilt("i_lamp", P(c, r, 2.6, 2.4, F + 0.12), (0, 90, 30))
    fu.floor_lamp("i_lamp", (0, 0, 0), lit=True, parent=g)
    nx.lamp("i_lamp_light", P(c, r, 2.4, 2.6, F + 0.4), WARM, 3.0, 1.6, leak=1.0, box=box_of(c, r))

    # (2,2) 倒挂：一间卧室整个贴在天花板上；地上只有一扇没有墙的门（也能开关）
    c, r = 2, 2
    hc = cell_h(c, r)
    g = tilt("h_ceiling", P(c, r, 0, 0, F + hc), (180, 0, 0))
    fu.bed("h_bed", (2.4, -2.3, 0), 0, parent=g)
    fu.nightstand("h_nightstand", (1.0, -3.8, 0), 0, parent=g)
    fu.table_lamp("h_lamp", (1.0, -3.82, 0.58), lit=True, parent=g)
    nx.box("h_rug", (1.3, 0.62, 0.02), (2.4, -0.8, 0), parent=g, collide=False, a="blue_pale", b="white", pattern="stripes")
    nx.lamp("h_lamp_light", P(c, r, 1.0, 3.82, F + hc - 0.9), WARM, 3.4, 1.8, up=70, leak=0.3, box=box_of(c, r))
    loc = P(c, r, 2.2, 2.3)
    g = tilt("h_lonedoor", loc, (0, 0, 32))
    pf.frame("h_lonedoor", (0, 0, 0), 0, w=0.86, h=2.06, depth=0.18, t=0.07, kind="door", parent=g, **TRIM)
    pf.door("h_lonedoor_door", (-0.43 - LAP, 0.09 + 0.0245, 0.01), 0, 95, w=0.86 + 2 * LAP, h=2.05 + LAP,
            at=(loc[0], loc[1], F + 1.2), parent=g)

    # (1,3) 散开：东西都浮在头顶上，各转各的
    c, r = 1, 3
    things = [(0.8, 1.2, 2.6), (3.3, 1.0, 3.4), (1.2, 3.4, 2.3), (3.4, 3.3, 2.9)]
    for i, (u, v, z) in enumerate(things):
        g = tilt(f"j_chair{i}", P(c, r, u, v, F + z), (rnd.uniform(-60, 60), rnd.uniform(-60, 60), rnd.uniform(0, 360)))
        fu.chair(f"j_chair{i}", (0, 0, 0), 0, "dining", fabric=["blue", "pink", "lilac", "white"][i], parent=g)
    g = tilt("j_sofa", P(c, r, 2.1, 2.9, F + 2.4), (14, -20, 160))
    fu.sofa("j_sofa", (0, 0, 0), 0, fabric="blue", parent=g)
    g = tilt("j_desk", P(c, r, 2.7, 1.6, F + 2.5), (35, 10, 70))
    fu.desk("j_desk", (0, 0, 0), 0, parent=g)
    g = tilt("j_nightstand", P(c, r, 1.0, 2.2, F + 3.2), (0, 75, 10))
    fu.nightstand("j_nightstand", (0, 0, 0), 0, parent=g)
    for i, (u, v, z) in enumerate([(1.5, 1.6, 2.2), (3.0, 2.7, 3.0)]):
        g = tilt(f"j_float_lamp{i}", P(c, r, u, v, F + z), (rnd.uniform(-40, 40), rnd.uniform(-40, 40), 0))
        fu.pendant(f"j_float_lamp{i}", (0, 0, 0.6), drop=0.2, lit=True, parent=g)
        nx.lamp(f"j_float_lamp{i}_light", P(c, r, u, v, F + z), WARM, 3.0, 1.4, leak=1.0, box=box_of(c, r))

    # (2,3) 一间客厅整个倒挂在天花板上；地上只剩一把椅子对着北墙，脚边一盏台灯
    c, r = 2, 3
    hc = cell_h(c, r)
    g = tilt("k_ceiling", P(c, r, 0, 0, F + hc), (180, 0, 0))
    fu.sofa("k_sofa", (2.1, -4.03, 0), 180, fabric="pink", parent=g)
    fu.tv_stand("k_tv", (2.1, -0.4, 0), 0, lit=True, parent=g)
    low_table("k_coffee", (2.1, -2.2, 0), parent=g)
    nx.box("k_rug", (2.2, 1.5, 0.02), (2.1, -2.2, 0), parent=g, collide=False, a="blue_pale", b="lilac_pale", pattern="stripes")
    fu.floor_lamp("k_floorlamp", (0.5, -3.9, 0), lit=True, parent=g)
    nx.lamp("k_floorlamp_light", P(c, r, 0.5, 3.9, F + hc - 1.4), WARM, 3.4, 1.6, down=0, up=60, leak=0.3, box=box_of(c, r))
    fu.chair("k_chair", P(c, r, 2.1, 2.6), 0, "dining", fabric="blue")
    lit_table_lamp("k_lamp", *P(c, r, 2.8, 1.8)[:2], F, box_of(c, r), power=1.6, radius=2.6)

    # 和卧室一模一样的那间：卧室的东西原样摆一遍
    c, r = HOME
    bedroom_things("m_", XS[c], YS[r])


def back_chain():
    """最北那间的北门后面：又是一串门，比过道里的还小、还歪，最后一扇小得过不去（推开了门后也挡着）"""
    nx.into("back")
    y0, y1 = YS[ROWS], YS[ROWS] + 6.0
    room("back", PX0, y0, PX1, y1, FLOOR_STONE)
    wall("w_back_w", "y", PX0, y0 + h, y1 + h)
    wall("w_back_e", "y", PX1, y0 + h, y1 + h)
    wall("w_back_n", "x", y1, PX0 + h, PX1 - h, style=WALL_DEEP)
    ceiling_light("back_light", (PX0 + PX1) / 2, y0 + 0.7, (4.28, y0 + 0.05, 0, 5.92, y0 + 1.25, 3), power=0.9, radius=2.4)
    n = 4
    door_chain("bd", [y0 + 1.2 + i * 1.15 for i in range(n)], [0.82 - i * 0.07 for i in range(n)], [2.0 - i * 0.17 for i in range(n)],
               [(1 if i % 2 else -1) * (3 + i * 3) for i in range(n)], ["lilac_pale", "blue_pale"], last_blocked=True)


def build(extent=EXTENT):
    nx.into("env")
    # 月光从西边斜着进来（落地窗、卧室的窗里落一块冷的光）
    nx.sun((-0.72, 0.12, 0.55))
    nx.atmosphere("night", lamps=True)
    # 醒来在床边：看着床、床头的灯、窗下的书桌
    nx.spawn((3.1, 6.2, F + 0.02), facing_deg=50)
    core()
    passage()
    grid()


if __name__ == "__main__":
    nx.reset()
    build()
    nx.save_blend("house")
    nx.export("house")
