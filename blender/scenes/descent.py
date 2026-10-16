"""浅梦 · 下沉 · 井（descent）：一口一圈圈往下走的圆井（竖向）＋厚井壁里挖出来的洞。

秩序感＋说不清：台阶一丝不苟、一圈圈往下，却没人说得清它为谁而修。
井口在一处下沉的圆院里：院子从四周一圈圈台阶落到井沿，外面一圈高墙；墙外一片平地上立着一圈高低不一、中间断开的塔。
院子一角一道螺旋梯升进天里，顶上一枚晶体。头顶几只环慢慢地转；井里也浮着两只，从哪一层往上看都套着井口那一圈天。

井心是一口半径 7m 的空井，从井口一直看得到井底那一汪水。井心外一圈有顶的回廊（每层一圈），回廊外面是十几米厚的
实心井壁：每层只在里面挖出几条巷子、几间厅，挖法一层一个样——
- 第一层（−6）「梳」：一条折来折去的脊巷，两边伸出几条死胡同，尽头各放一只这口井的模型，一只比一只深；
  最长的那条死胡同尽头地上一个方口，掉下去落进第二层的大厅。院子地上几个天窗正对着脊巷。
- 第二层（−12）「厅」：三间大小不一的厅用宽巷串起来，最大那间是圆的，顶上就是第一层的方口，里面一座这口井的剖面模型
  （第二层那一道台上一点金：你在这里）；小圆厅后面一条巷子通到一段暗梯，下到第三层。
- 第三层（−18）「柱林」：一整片挖空的大洞，留下一根根没挖掉的石柱，在柱子之间绕着走；一口格栅盖着的小井。
- 第四层（−24）「回纹」：最暗的一层，一条窄巷来回折五次；尽头岔出去一间小室，第三层那口小井在这里是一根圆柱。
  回廊朝井心那面墙上一道道发亮的横缝；一座桥偏开井心横过空井。
- 井底（−30）：白的圆厅。台阶一级级落进一汪浅水，水里映着井口那一圈天光——走进那个圆就醒回床边（回家）。
- 上下层之间：明梯贴着回廊外沿（19 级，每级 0.3，最后一级再迈 0.3 就是下一层的地）；回廊被扶壁截断，
  从明梯下来的那段走不到下一段明梯，要穿过井壁里的洞。第二到第三层另有一段暗梯。
- 捷径：第二到第四层各有一块往井心伸出去的台，从上一层回廊边上对着它一迈，落在它上面；从井口往井心一跳，直接落进井底的水里。
- 从家里的床「睡」进来，落在井口的院子里。

运行：node scripts/blender.cjs build descent，网页 ?world=descent
环境变量 DESCENT_ROUTE=路径：只走明梯从井口走到井底的一条路（Blender 坐标的点列）写成 JSON，给自动行走测试用；
DESCENT_ROUTE_DARK=路径：同上，第二层走暗梯下到第三层。
"""
import json
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import furniture as fu  # noqa: E402
import nx  # noqa: E402
import prefabs as pf  # noqa: E402
import shapes as sh  # noqa: E402

EXTENT = 130
CENTER = (0, 0)

P = 7.0            # 空井（井心）半径：从井口一直看得到井底
SI, SO = 9.3, 11.47  # 明梯的带（回廊外沿，贴着井壁）
WALK_R = 8.15      # 回廊上走的那一圈（梯带里面，明梯旁边也走得过）
R_IN = 11.5        # 井壁（实心的岩）的内面
R_OUT = 23.86      # 每层楼板、井壁的外缘
LV = 6.0           # 层高
NL = 5             # 井底是第 5 层（−30m）
SLAB = 0.8         # 楼板厚
RISE = 0.3
STEPS = 19         # 19 级 × 0.3 = 5.7，最后一级再迈 0.3 就是下一层的地
SR = (SI + SO) / 2
TREAD = math.degrees(0.85 / SR)   # 每级占的角度（梯中线上 0.85m）
SPAN = TREAD * STEPS
COURT_R = 18.0     # 院子平地的外缘（往外是一圈圈台阶）
HALL_R = 14.0      # 井底圆厅的半径
POOL_R = 6.0

# 每段明梯的起点方位（度）：下一段在上一段落脚处再往前 140°
STAIR_A = [200.0]
for _ in range(NL - 1):
    STAIR_A.append((STAIR_A[-1] + SPAN + 140.0) % 360)

# 每层的颜色：越往下越深，井底是白的
WALLS = [
    dict(a="lilac_pale", b="mist", pattern="bands"),
    dict(a="lilac_pale", b="lilac", pattern="bands"),
    dict(a="lilac", b="lilac_dark", pattern="bands"),
    dict(a="lilac_dark", b="violet", pattern="bands"),
    dict(a="violet", b="violet_deep", pattern="bands"),
    dict(a="mist", b="white", pattern="bands"),
]
FLOORS = [
    dict(a="mist", b="lilac_pale", pattern="tiles"),
    dict(a="pink_pale", b="pink", pattern="tiles"),     # 台面偏暖，和冷的井壁分得开
    dict(a="lilac_pale", b="mist", pattern="tiles"),
    dict(a="pink", b="rose", pattern="grain"),
    dict(a="lilac", b="lilac_dark", pattern="tiles"),
    dict(a="white", b="mist", pattern="tiles"),
]
# 井壁的岩：三色明暗，朝向不同的面分得开；纹样一层一样
ROCK = [
    None,
    dict(ramp=("lilac", "lilac_pale", "mist"), pattern="plain"),
    dict(ramp=("rose", "pink", "pink_pale"), pattern="plain"),
    dict(ramp=("violet", "lilac_dark", "lilac"), pattern="plain"),
    dict(ramp=("violet_deep", "violet", "lilac_dark"), pattern="plain"),
]
GLOW = dict(a="gold", b="pink_pale", pattern="plain")
WHITE_GLOW = dict(a="white", b="mist", pattern="plain")
WARM = "#ffe6c8"  # 井里那几处自己亮着的东西漏出来的光


def zl(n):
    return -LV * n


def ceil_of(n):
    """第 n 层顶上那块板的底面"""
    return -1.0 if n == 1 else zl(n - 1) - SLAB


def polar(r, a_deg, z=0.0):
    a = math.radians(a_deg)
    return (math.cos(a) * r, math.sin(a) * r, z)


def norm(a):
    return a % 360.0


def within(a, a0, a1):
    """方位 a 在 a0 → a1（逆时针）之间"""
    return norm(a - a0) <= norm(a1 - a0)


def deg_at(m, r):
    """半径 r 处 m 米对应的角度"""
    return math.degrees(m / r)


# ── 网格：一块环形的板，按条件挖掉一些格 ────────────────

def slab(k, radii, z0, z1, present, extra_a=(), step=2.0):
    """在 Kit 里加一块环形的板：radii 是径向的分界，角向每 step 度一格（extra_a 里的方位也切一刀），
    present(r, a) 说这一格要不要；只出顶、底和露在外面的侧面，板里没有夹层"""
    radii = sorted(set(radii))
    angs = sorted({round(norm(a), 4) for a in [i * step for i in range(int(360 / step))] + list(extra_a)})
    nr, na = len(radii) - 1, len(angs)
    on = [[present((radii[i] + radii[i + 1]) / 2, norm(angs[j] + norm(angs[(j + 1) % na] - angs[j]) / 2))
           for j in range(na)] for i in range(nr)]
    verts, vid, faces = [], {}, []

    def v(i, j, top):
        key = (i, j % na, top)
        if key not in vid:
            a = math.radians(angs[j % na])
            vid[key] = len(verts)
            verts.append((math.cos(a) * radii[i], math.sin(a) * radii[i], z1 if top else z0))
        return vid[key]

    for i in range(nr):
        for j in range(na):
            if not on[i][j]:
                continue
            j1 = j + 1
            faces.append((v(i, j, 1), v(i + 1, j, 1), v(i + 1, j1, 1), v(i, j1, 1)))
            faces.append((v(i, j, 0), v(i, j1, 0), v(i + 1, j1, 0), v(i + 1, j, 0)))
            if i == 0 or not on[i - 1][j]:
                faces.append((v(i, j, 0), v(i, j, 1), v(i, j1, 1), v(i, j1, 0)))
            if i == nr - 1 or not on[i + 1][j]:
                faces.append((v(i + 1, j, 0), v(i + 1, j1, 0), v(i + 1, j1, 1), v(i + 1, j, 1)))
            if not on[i][(j - 1) % na]:
                faces.append((v(i, j, 0), v(i + 1, j, 0), v(i + 1, j, 1), v(i, j, 1)))
            if not on[i][(j + 1) % na]:
                faces.append((v(i, j1, 0), v(i, j1, 1), v(i + 1, j1, 1), v(i + 1, j1, 0)))
    if faces:
        k._add(verts, faces)


def sector(k, r0, r1, a0, a1, z0, z1, step=2.0):
    """一块扇形的实心块（a0 → a1 逆时针）"""
    span = norm(a1 - a0) or 360.0
    n = max(1, int(math.ceil(span / step)))
    verts, faces = [], []
    for i in range(n + 1):
        a = math.radians(a0 + span * i / n)
        c, s = math.cos(a), math.sin(a)
        verts += [(c * r0, s * r0, z0), (c * r1, s * r1, z0), (c * r0, s * r0, z1), (c * r1, s * r1, z1)]
    for i in range(n):
        o, p = i * 4, (i + 1) * 4
        faces += [(o + 2, o + 3, p + 3, p + 2), (o, p, p + 1, o + 1), (o + 1, p + 1, p + 3, o + 3), (o, o + 2, p + 2, p)]
    o = n * 4
    faces += [(0, 1, 3, 2), (o, o + 2, o + 3, o + 1)]
    k._add(verts, faces)


def radial_wall(k, a, r0, r1, z0, z1, th=0.5):
    x, y, _ = polar((r0 + r1) / 2, a)
    k.box((th, r1 - r0, z1 - z0), (x, y, z0), rot=(0, 0, a - 90))


def build_kit(k, name, **style):
    return k.build(name, smooth=0, **style)


def join(objs, name):
    objs = [o for o in objs if o is not None and o.type == "MESH"]
    if len(objs) < 2:
        return objs[0] if objs else None
    with bpy.context.temp_override(active_object=objs[0], object=objs[0], selected_objects=objs,
                                   selected_editable_objects=objs):
        bpy.ops.object.join()
    objs[0].name = name
    return objs[0]


# ── 井壁：一整圈实心的岩，按图挖出巷子和厅 ─────────────────

def xy(p):
    x, y, _ = polar(*p)
    return Vector((x, y))


def path(*parts):
    """拼一条折线（极坐标的点 (r, a)）：("arc", r, a1) ＝ 从上一点沿半径 r 转到方位 a1（a1 不折回 0–360，
    比上一点小就是顺时针转）；先径向挪到 r 再转"""
    pts = []
    for p in parts:
        if p[0] == "arc":
            _, r, a1 = p
            r0, a0 = pts[-1]
            if abs(r0 - r) > 1e-6:
                pts.append((r, a0))
            n = max(1, int(math.ceil(abs(a1 - a0) / 3.0)))
            pts += [(r, a0 + (a1 - a0) * i / n) for i in range(1, n + 1)]
        else:
            pts.append(tuple(p))
    return pts


def strip(k, pts, w, z0, z1):
    """沿折线挖的一条巷子（宽 w）：一根横截面是矩形的条，拐角斜接"""
    q = []
    for p in pts:
        v = xy(p)
        if not q or (v - q[-1]).length > 0.05:
            q.append(v)
    n = len(q)
    left, right = [], []
    for i in range(n):
        if i == 0 or i == n - 1:
            d = (q[1] - q[0]) if i == 0 else (q[i] - q[i - 1])
            d.normalize()
            nm, s = Vector((-d.y, d.x)), 1.0
        else:
            d0 = (q[i] - q[i - 1]).normalized()
            d1 = (q[i + 1] - q[i]).normalized()
            n0, n1 = Vector((-d0.y, d0.x)), Vector((-d1.y, d1.x))
            nm = (n0 + n1)
            if nm.length < 1e-6:
                nm = n0
            nm.normalize()
            s = 1.0 / max(0.55, nm.dot(n0))
        left.append(q[i] + nm * (w / 2 * s))
        right.append(q[i] - nm * (w / 2 * s))
    verts, faces = [], []
    for i in range(n):
        for p in (left[i], right[i]):
            verts += [(p.x, p.y, z0), (p.x, p.y, z1)]
    for i in range(n - 1):
        o, p = i * 4, (i + 1) * 4
        # 0 左下 1 左上 2 右下 3 右上
        faces += [(o + 1, o + 3, p + 3, p + 1), (o, p, p + 2, o + 2), (o, o + 1, p + 1, p), (o + 2, p + 2, p + 3, o + 3)]
    o = (n - 1) * 4
    faces += [(0, 2, 3, 1), (o, o + 1, o + 3, o + 2)]
    k._add(verts, faces)


def prism(k, poly, z0, z1):
    """多边形（极坐标点列，按逆时针）往上拉成的柱：厅"""
    q = [xy(p) for p in poly]
    n = len(q)
    verts = []
    for v in q:
        verts += [(v.x, v.y, z0), (v.x, v.y, z1)]
    faces = [tuple(i * 2 for i in range(n))[::-1], tuple(i * 2 + 1 for i in range(n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i * 2, j * 2, j * 2 + 1, i * 2 + 1))
    k._add(verts, faces)


def circle(c, rad, seg=20):
    """以极坐标点 c 为心、半径 rad 的圆（返回极坐标点列）"""
    o = xy(c)
    out = []
    for i in range(seg):
        t = 2 * math.pi * i / seg
        x, y = o.x + math.cos(t) * rad, o.y + math.sin(t) * rad
        out.append((math.hypot(x, y), math.degrees(math.atan2(y, x))))
    return out


def ring_sector(r0, r1, a0, a1):
    return path((r1, a0), ("arc", r1, a1)) + path((r0, a1), ("arc", r0, a0))


def carve_rock(name, z0, z1, cut, **style):
    """一整圈实心的井壁（R_IN → R_OUT，z0 → z1），减去 cut（Kit）里的巷子和厅"""
    rock = sh.tube(name, R_OUT + 0.3, R_IN, z1 - z0, (0, 0, z0), segments=180, **style)
    me = bpy.data.meshes.new(name + "_cut")
    me.from_pydata(cut.v, [], cut.f)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    co = bpy.data.objects.new(name + "_cut", me)
    bpy.context.scene.collection.objects.link(co)
    mod = rock.modifiers.new("carve", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.object = co
    mod.use_self = True
    mod.use_hole_tolerant = True
    dg = bpy.context.evaluated_depsgraph_get()
    new = bpy.data.meshes.new_from_object(rock.evaluated_get(dg))
    rock.modifiers.clear()
    old = rock.data
    rock.data = new
    new.name = name
    bpy.data.meshes.remove(old)
    bpy.data.objects.remove(co)
    bpy.data.meshes.remove(me)
    nx._smooth(rock, 30)
    return rock


# ── 每层挖什么 ─────────────────────────────────────────
# 一层的图：cuts 是挖掉的（("strip", 折线, 宽, 高) / ("room", 多边形, 高)，高 None ＝ 一直挖到顶）；
# route 是从明梯落脚处穿过井壁走到下一段明梯口的一条路（极坐标点）；lamps 是灯（极坐标点、离地多高）

def level_plan(n):
    lv = dict(n=n, z=zl(n), c=ceil_of(n), ap=STAIR_A[n - 1], an=STAIR_A[n] if n < NL else None)
    lv["ep"] = lv["ap"] + SPAN
    lv["en"] = lv["an"] + SPAN
    ep, an, en, ap = lv["ep"], lv["an"], lv["en"], lv["ap"]
    # 扶壁：把回廊截成三段——g0（明梯下来）、g1、g2（去下一段明梯）
    lv["butt"] = [ep + 40, an - 45, en + norm(ap - en) / 2]
    cuts, lamps, extra = [], [], {}
    W = {1: 2.4, 2: 3.0, 3: 2.8, 4: 2.4}[n]
    H = {1: 3.0, 2: 3.6, 3: 3.4, 4: 2.8}[n]

    def tun(pts, w=W, h=H):
        cuts.append(("strip", pts, w, h))
        return pts

    if n == 1:
        # 「梳」：一条折来折去的脊巷，两头各通一段回廊；几根齿伸出去是死胡同
        tun(path((10.3, 308), (14.5, 308), ("arc", 14.5, 342), (19.5, 342), ("arc", 19.5, 372),
                 (14.5, 372), ("arc", 14.5, 405), (10.3, 405)))
        tun([(10.3, 357), (19.5, 357)])                           # 中间那段回廊也通进来
        tun(path((14.5, 325), (18.5, 325), ("arc", 18.5, 250)))  # 最长的齿：尽头一个方口
        tun([(19.5, 342), (22.3, 342)])
        tun(path((14.5, 390), (18.5, 390), ("arc", 18.5, 424)))
        tun([(18.5, 285), (22.3, 285)])
        extra["models"] = [((21.3, 285), 285 + 180), ((21.3, 342), 342 + 180), ((18.5, 421.5), 421.5 + 90)]
        extra["hole"] = (18.5, 253.5)
        extra["sky"] = [(14.5, 318), (19.5, 357), (14.5, 396)]
        lv["route"] = [(WALK_R, ep + 9), (WALK_R, 308), (10.3, 308), (14.5, 308)] + \
            path((14.5, 308), ("arc", 14.5, 342))[1:] + [(19.5, 342)] + path((19.5, 342), ("arc", 19.5, 372))[1:] + \
            [(14.5, 372)] + path((14.5, 372), ("arc", 14.5, 405))[1:] + [(10.3, 405), (WALK_R, 405)]
        lamps += [((14.5, 308), H), ((14.5, 342), H), ((19.5, 357), H), ((14.5, 372), H),
                  ((18.5, 300), H), ((18.5, 265), H)]
    elif n == 2:
        # 「厅」：三间大小不一的厅用宽巷串起来
        hall = ((17.5, 250), 4.6)
        small = ((17.5, 306), 3.2)
        cuts.append(("room", ring_sector(14.0, 19.6, 176, 204), None))
        tun([(10.3, 186), (14.5, 186)])
        tun(path((16.5, 200), ("arc", 16.5, 242)))
        tun([(10.3, 226), (16.5, 226)])                          # 第二段回廊也通进来
        cuts.append(("room", circle(*hall, seg=28), None))
        tun(path((20.6, 256), ("arc", 20.6, 296), (19.0, 303)))
        cuts.append(("room", circle(*small, seg=20), None))
        tun(path((10.3, 284), (14.8, 284), ("arc", 14.8, 306)))
        tun(path((19.0, 190), (22.2, 190), ("arc", 22.2, 158)))  # 死胡同
        tun(path((19.4, 309), (21.5, 315), ("arc", 21.5, 363)), w=2.8, h=3.6)  # 去暗梯
        extra["hall"] = hall
        extra["small"] = small
        extra["dark"] = (320.0, 21.5)
        lv["route"] = [(WALK_R, ep + 9), (WALK_R, 186), (10.3, 186), (14.5, 186), (16.5, 192), (16.5, 200)] + \
            path((16.5, 200), ("arc", 16.5, 240))[1:] + [(17.5, 250), (20.6, 256)] + \
            path((20.6, 256), ("arc", 20.6, 296))[1:] + [(18.0, 304), (14.8, 300)] + \
            path((14.8, 300), ("arc", 14.8, 284))[1:] + [(10.3, 284), (WALK_R, 284)]
        lv["route_dark"] = [(WALK_R, ep + 9), (WALK_R, 186), (10.3, 186), (14.5, 186), (16.5, 192), (16.5, 200)] + \
            path((16.5, 200), ("arc", 16.5, 240))[1:] + [(17.5, 250), (20.6, 256)] + \
            path((20.6, 256), ("arc", 20.6, 296))[1:] + [(19.4, 309), (21.5, 315), (21.5, 319)]
        lamps += [((16.8, 190), None), ((17.5, 250), None), ((17.5, 306), None), ((20.6, 275), H),
                  ((22.2, 162), H), ((14.8, 292), H)]
    elif n == 3:
        # 「柱林」：挖空的一大片，留下一根根石柱
        cave = ring_sector(12.8, 20.6, 44, 150)
        cuts.append(("room", cave, None))
        tun([(10.3, 52), (13.5, 52)])
        tun([(10.3, 95), (13.5, 95)])
        tun([(10.3, 140), (13.5, 140)])
        tun(path((21.5, 363), ("arc", 21.5, 410), (19.4, 418)), w=2.8)   # 暗梯下来
        extra["well"] = (18.4, 68)
        lv["route"] = [(WALK_R, ep + 9), (WALK_R, 52), (10.3, 52), (14.0, 52), (16.5, 60), (17.6, 78),
                       (16.0, 95), (17.4, 112), (16.0, 128), (13.8, 139), (10.3, 140), (WALK_R, 140)]
        lv["route_dark_in"] = path((21.5, 363), ("arc", 21.5, 408))[:] + [(19.0, 418), (16.5, 60)]
        lamps += [((15.0, 70), None), ((18.5, 100), None), ((15.0, 122), None), ((21.5, 390), H)]
    else:
        # 「回纹」：一条窄巷来回折五次；尽头岔出去一间小室
        # 五折，每折的宽窄、进深都不一样
        loop = path((10.3, 282), (21.5, 282), ("arc", 21.5, 299), (14.8, 299), ("arc", 14.8, 320), (21.8, 320),
                    ("arc", 21.8, 334), (15.6, 334), ("arc", 15.6, 353), (21.5, 353), ("arc", 21.5, 372), (10.3, 372))
        tun(loop)
        tun(path((21.5, 372), ("arc", 21.5, 408), (18.8, 64)))
        extra["cell"] = ((18.4, 68), 3.0)
        cuts.append(("room", circle((18.4, 68), 3.0, seg=20), 3.6))
        lv["route"] = [(WALK_R, ep + 9), (WALK_R, 282)] + loop + [(WALK_R, 372)]
        lamps += [((21.5, 290), H), ((14.8, 310), H), ((21.8, 327), H), ((21.5, 362), H), ((18.4, 68), 3.6)]
    lv["cuts"], lv["lamps"], lv["extra"] = cuts, lamps, extra
    return lv


def build_level(lv, rest):
    n, z, c = lv["n"], lv["z"], lv["c"]
    nx.into(f"level{n}")
    box = (-25.0, -25.0, z - 0.1, 25.0, 25.0, c + 0.1)
    floor_k, cut_k, stair_k, glow_k = fu.Kit(), fu.Kit(), fu.Kit(), fu.Kit()
    ex = lv["extra"]

    # ─ 地：环形的板，挖掉明梯口、暗梯的梯井、方口、小井 ─
    holes = [(SI, SO, lv["an"], lv["en"])]
    if "dark" in ex:
        a0, r = ex["dark"]
        holes.append((r - 1.3, r + 1.3, a0, a0 + deg_at(0.85 * STEPS, r)))
    if "hole" in ex:
        hr, ha = ex["hole"]
        holes.append((hr - 0.8, hr + 0.8, ha - deg_at(0.8, hr), ha + deg_at(0.8, hr)))
    if "well" in ex:
        wr, wa = ex["well"]
        holes.append((wr - 1.0, wr + 1.0, wa - deg_at(1.0, wr), wa + deg_at(1.0, wr)))
    tongue = None
    if n >= 2:
        ta = lv["ep"] + (150 if n == 4 else 80)
        tongue = (ta - 12, ta + 12)

    def present(r, a):
        if r < P:
            return tongue is not None and r > P - 2.2 and within(a, *tongue)
        if r > R_OUT:
            return False
        return not any(h0 <= r <= h1 and within(a, b0, b1) for h0, h1, b0, b1 in holes)

    radii = [P - 2.2, P, SI, SO, R_IN, R_OUT] + [h[0] for h in holes] + [h[1] for h in holes]
    edges = [h[2] for h in holes] + [h[3] for h in holes] + (list(tongue) if tongue else [])
    slab(floor_k, radii, z - SLAB, z, present, edges)

    # ─ 井壁：挖巷子、厅；暗梯的梯井、天窗、方口、小井也挖穿 ─
    for cu in lv["cuts"]:
        if cu[0] == "strip":
            _, pts, w, h = cu
            strip(cut_k, pts, w, z - 0.3, z + h if h else c + 0.3)
        else:
            _, poly, h = cu
            prism(cut_k, poly, z - 0.3, z + h if h else c + 0.3)
    for r_, a_ in ex.get("sky", []):     # 天窗：一直挖到院子的地
        prism(cut_k, ring_sector(r_ - 0.86, r_ + 0.86, a_ - deg_at(0.86, r_), a_ + deg_at(0.86, r_)), z + 2.0, c + 0.3)
    for dk in rest.get("dark_below", []):  # 上一层的暗梯落到这一层：整段挖到顶
        a0, r = dk
        strip(cut_k, path((r, a0 - 2), ("arc", r, a0 + deg_at(0.85 * STEPS, r) + 1)), 2.8, z - 0.3, c + 0.3)
    carve_rock(f"rock{n}", z - 0.05, c if n == 1 else c + 0.05, cut_k, **ROCK[n])  # 第一层顶贴着院子的地，天窗的井壁不和院子的洞口共面

    # 扶壁：把回廊截成三段
    wall_k = fu.Kit()
    for b in lv["butt"]:
        radial_wall(wall_k, b, P, R_IN + 0.2, z - 0.05, c + 0.05, th=0.6)
    build_kit(wall_k, f"butt{n}", **WALLS[n])

    # ─ 明梯：从上一层下来的那段，在这一层的空间里 ─
    stair_steps(stair_k, lv["ap"], lv["ep"], SI + 0.05, SO, zl(n - 1), z)
    for dk in rest.get("dark_below", []):
        a0, r = dk
        stair_steps(stair_k, a0, a0 + deg_at(0.85 * STEPS, r), r - 1.25, r + 1.25, zl(n - 1), z)

    # ─ 捷径的桥 ─
    if n == 4:
        th = lv["ep"] - 9.3
        cx, cy, _ = polar(3.0, th)
        half = math.sqrt(8.5 ** 2 - 9.0)
        stair_k.box((2.2, 2 * half, 0.5), (cx, cy, z - 0.35), rot=(0, 0, th))

    # ─ 灯：洞里几处、回廊每段一盏 ─
    lamps = list(lv["lamps"])
    segs = [(lv["butt"][2], lv["butt"][0]), (lv["butt"][0], lv["butt"][1]), (lv["butt"][1], lv["butt"][2])]
    for a0, a1 in segs:
        lamps.append(((WALK_R + 0.4, a0 + norm(a1 - a0) / 2), None))
    for (r, a), h in lamps:
        x, y, _ = polar(r, a)
        top = c if h is None else z + h
        glow_k.box((0.6, 0.6, 0.08), (x, y, top - 0.065))
        nx.lamp(f"lamp{n}_{len(nx_lamps)}", (x, y, top - 0.3), color=WARM, radius=6.5, power=0.75, down=70,
                leak=0.25, box=box)
        nx_lamps.append(1)

    build_kit(floor_k, f"floor{n}", **FLOORS[n])
    build_kit(stair_k, f"stairs{n}", **FLOORS[n])
    build_kit(glow_k, f"lights{n}", emit=1.0, collide=False, shadow=False, a="pink_pale", b="white", pattern="plain")
    return box


nx_lamps = []


def court(sky):
    """井口：一处下沉的圆院，一圈圈台阶落到井沿；外面一圈高墙。地上的方口是第一层的天窗"""
    a0, a1 = STAIR_A[0], STAIR_A[0] + SPAN
    holes = [(SI, SO, a0, a1)] + [(r - 0.8, r + 0.8, a - deg_at(0.8, r), a + deg_at(0.8, r)) for r, a in sky]

    def present(r, a):
        if r < P or r > COURT_R:
            return False
        return not any(h0 <= r <= h1 and within(a, b0, b1) for h0, h1, b0, b1 in holes)

    k = fu.Kit()
    edges = [a0, a1] + [h[2] for h in holes] + [h[3] for h in holes]
    slab(k, [P, SI, SO, COURT_R] + [h[0] for h in holes] + [h[1] for h in holes], -1.0, 0.0, present, edges)
    build_kit(k, "court_floor", **FLOORS[0])
    # 井口一圈矮沿
    sh.tube("parapet", P + 0.7, P, 0.45, (0, 0, -0.02), segments=128, a="mist", b="lilac_pale", pattern="plain")
    # 一圈圈台阶往外升起
    r = COURT_R
    for i in range(1, 7):
        sh.tube(f"terrace{i}", r + 1.5, r, 1.05 + RISE * i, (0, 0, -1.05), segments=128,
                a="mist" if i % 2 else "lilac_pale", b="lilac_pale", pattern="tiles")
        r += 1.5
    sh.tube("court_wall", r + 1.5, r, 6.0, (0, 0, -1.0), segments=128, a="lilac_pale", b="lilac", pattern="bands")
    nx.collider_only(sh.tube("court_fence", r + 1.5, r, 40.0, (0, 0, 5.0), segments=48))
    sh.tube("plain", OUTER, r + 1.5, 1.0, (0, 0, 4.0), segments=128, a="mist", b="lilac_pale", pattern="grain")
    # 头顶慢慢转的环；空井里也浮着两只，从哪一层往上看都套着井口
    for i, (rr_, z, tilt, spin, col) in enumerate([(9.0, 13, 14, 4, "white"), (13.0, 17, -22, -2.5, "mist"),
                                                    (14.5, 27, 18, 1.6, "pink_pale"),
                                                    (3.2, zl(1) - 2.6, 5, 3, "white"), (2.6, zl(3) - 2.6, -8, -4.5, "pink_pale")]):
        t = nx.torus(f"ring{i}", rr_, 0.22 + rr_ * 0.015, (0, 0, z), rot=(tilt, 0, 30 * i), major_seg=128,
                     minor_seg=10, a=col, b="lilac_pale", collide=False, shadow=False)
        nx.behave(t, spin=spin)


OUTER = 64.0      # 墙外平地的外缘
SKY_C = polar(21.0, 55)[:2]   # 升进天里的螺旋梯（院子东北，从出生点隔着井看得见）


def sky_stair():
    """院子一角一道螺旋梯，一圈圈升进天里，顶上一枚晶体"""
    z0 = 1.52   # 梯脚压着的那几圈台阶最高 1.5
    land = pf.stair_spiral("sky_stair", SKY_C, z0, 64, r_in=0.9, r_out=2.7, tread=19, start=55 - 19,
                           landing_arc=120, a="mist", b="lilac_pale", pattern="plain")
    join([o for o in bpy.data.objects if o.name.startswith("sky_stair_s")], "sky_stair_steps")
    nx.cylinder("sky_axis", 0.5, 0.5, land[2] - 0.3 - 0.6, (SKY_C[0], SKY_C[1], 0.6), segments=16,
                a="lilac", b="lilac_dark", pattern="stripes")
    nx.entrance("crystal_descent", (land[0], land[1], land[2] + 1.6), "", "")


def towers():
    """墙外：一圈高低不一的塔，有的中间断开，上半截错开一点浮着"""
    rnd = random.Random(5)
    for i in range(14):
        a = 360 / 14 * i + rnd.uniform(-6, 6)
        x, y, _ = polar(rnd.uniform(34, 50), a)
        h = rnd.uniform(8, 30)
        w = rnd.uniform(1.4, 2.6)
        st = dict(a=rnd.choice(["lilac_pale", "mist", "lilac_pale", "pink_pale"]), b="lilac", pattern="bands")
        if i % 3 == 1:
            cut = h * rnd.uniform(0.45, 0.7)
            nx.box(f"tower{i}_lo", (w, w, cut), (x, y, 4.9), rot=(0, 0, a), **st)
            nx.box(f"tower{i}_hi", (w, w, h - cut), (x, y, 4.9 + cut + rnd.uniform(1.5, 3.5)), rot=(0, 0, a + 12), **st)
        else:
            nx.box(f"tower{i}", (w, w, h), (x, y, 4.9), rot=(0, 0, a), **st)


def stair_steps(k, a0, a1, r0, r1, z_top, z_floor):
    """一段往下的弧梯：从 a0 起 19 级，每级顶面比上一级低 0.3，实心落到下面那层的地里"""
    tr = (a1 - a0) / STEPS
    for i in range(STEPS):
        sector(k, r0, r1, a0 + tr * i, a0 + tr * (i + 1), z_floor - 0.1, z_top - RISE * (i + 1), step=1.0)


# ── 各层的东西 ─────────────────────────────────────────

def models1(lv, box):
    """第一层：齿尽头各一只这口井的模型，一只比一只深；最长那根齿尽头一个方口"""
    z = lv["z"]
    for j, ((r, a), face) in enumerate(lv["extra"]["models"]):
        h, rim = 0.3 + 0.35 * j, 1.0 + 0.1 * j
        px, py, _ = polar(r, a)
        name = f"niche{j}"
        nx.box(f"{name}_plinth", (0.9, 0.9, rim - h + 0.02), (px, py, z - 0.02), rot=(0, 0, face),
               a="mist", b="lilac_pale", pattern="plain")
        top = z + rim - h
        sh.tube(f"{name}_model", 0.36, 0.28, h, (px, py, top), segments=20, a="lilac_pale", b="lilac", pattern="bands")
        nx.cylinder(f"{name}_bottom", 0.28, 0.28, 0.02, (px, py, top + 0.005), segments=20, emit=1.0, collide=False,
                    shadow=False, **WHITE_GLOW)
        nx.lamp(f"{name}_lamp", (px, py, z + rim + 0.3), color=WARM, radius=3.6, power=0.8, box=box)
    r, a = lv["extra"]["hole"]
    nx.lamp("hole_lamp", polar(r, a, z + 2.4), color=WARM, radius=4.5, power=0.7, box=box)


def hall2(lv, box):
    """第二层：方口底下的圆厅，靠外墙立着一座这口井的剖面模型（不挡路）"""
    z = lv["z"]
    (hr, ha), rad = lv["extra"]["hall"]
    r, a = hr + 1.8, ha - 10
    mx, my, _ = polar(r, a)
    base = z - 0.02
    nx.cylinder("model2_plinth", 0.9, 0.9, 0.5, (mx, my, base), segments=24, a="mist", b="lilac_pale", pattern="plain")
    top = base + 0.5
    scale = 0.1
    face = a + 180   # 开口朝井心
    sh.tube("model2_wall", 0.8, 0.7, 3.0 + 0.1, (mx, my, top), segments=40, arc=180, start=face - 90,
            a="lilac_pale", b="lilac", pattern="bands")
    nx.cylinder("model2_bottom", 0.7, 0.7, 0.04, (mx, my, top), segments=40, emit=1.0, shadow=False, **WHITE_GLOW)
    for k in range(1, NL):
        lz = top + 3.0 - LV * k * scale
        sh.tube(f"model2_ledge{k}", 0.7, 0.5, 0.05, (mx, my, lz - 0.05), segments=40, arc=180, start=face - 90,
                collide=False, a="lilac", b="lilac_pale", pattern="plain")
    gx, gy, _ = polar(0.6, face)
    nx.box("model2_here", (0.1, 0.1, 0.1), (mx + gx, my + gy, top + 3.0 - LV * 2 * scale), emit=1.0, collide=False,
           shadow=False, **GLOW)
    nx.lamp("model2_lamp", (mx, my, top + 2.8), color=WARM, radius=6.0, power=0.9, box=box)


def pillars3(lv):
    """第三层：挖空的一大片里留下的石柱——躲开路、门口、小井和暗梯口"""
    z, c = lv["z"], lv["c"]
    rnd = random.Random(31)
    route = [xy(p) for p in lv["route"][2:-2]] + [xy(p) for p in lv["route_dark_in"][-3:]]
    keep = [xy(p) for p in [(14.0, 52), (14.0, 95), (14.0, 140), lv["extra"]["well"], (19.4, 52)]]

    def seg_d(p, a, b):
        ab = b - a
        t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-9)))
        return (p - (a + ab * t)).length

    placed = []
    k = fu.Kit()
    for r in (13.9, 15.5, 17.3, 19.2):
        a = 46.0
        while a < 150:
            rr = r + rnd.uniform(-0.6, 0.6)
            aa = a + rnd.uniform(-2.0, 2.0)
            rad = rnd.uniform(0.5, 1.2)
            p = xy((rr, aa))
            ok = rr - rad > 12.9 and rr + rad < 20.5 and 46.5 < aa - deg_at(rad, rr) and aa + deg_at(rad, rr) < 149.5
            ok = ok and all(seg_d(p, route[i], route[i + 1]) > rad + 0.8 for i in range(len(route) - 1))
            ok = ok and all((p - q).length > rad + 2.0 for q in keep)
            ok = ok and all((p - q).length > rad + qr + 1.0 for q, qr in placed)
            if ok:
                placed.append((p, rad))
                seg = rnd.choice([6, 7, 8])
                k.cyl(rad, c - z + 0.1, loc=(p.x, p.y, z - 0.05), rot=(0, 0, rnd.uniform(0, 60)), seg=seg)
            a += deg_at(rnd.uniform(2.9, 3.8), r)
    k.build("pillars3", smooth=0, **ROCK[3])
    print(f"[nx] descent pillars {len(placed)}")


def well3(lv3, lv4, box3, box4):
    """第三层：柱林里一口小井，格栅盖着；井穿下去，在第四层那间小室里是一根柱子，底上一点白"""
    r, a = lv3["extra"]["well"]
    z = lv3["z"]
    cx, cy, _ = polar(r, a)
    sh.tube("well3_head", 1.5, 0.95, 0.6, (cx, cy, z - 0.02), segments=32, **WALLS[2])
    sh.tube("well3_shaft", 1.2, 0.9, z - zl(4) + 0.05, (cx, cy, zl(4) - 0.05), segments=32, **WALLS[4])
    nx.cylinder("well3_bottom", 0.9, 0.9, 0.04, (cx, cy, zl(4) + 0.02), segments=24, emit=1.0, collide=False,
                shadow=False, **WHITE_GLOW)
    k = fu.Kit()
    for i in range(-2, 3):
        k.box((0.1, 2.0, 0.1), (i * 0.36, 0, 0.58))
    k.build("well3_grate", loc=(cx, cy, z), rot=(0, 0, a), smooth=0, a="lilac_pale", b="lilac", pattern="plain")
    nx.lamp("well3_lamp", (cx, cy, z - 1.0), color=WARM, radius=4.5, power=1.0, down=0.0, up=60.0, leak=0.1, box=box3)
    nx.lamp("well3_lamp_up", (cx, cy, z + 1.4), color=WARM, radius=3.0, power=0.5, box=box3)


def slits4(lv):
    """第四层：回廊朝井心的那面墙上一道道发亮的横缝（明梯挡着的那段不放）"""
    z = lv["z"]
    k = fu.Kit()
    i = 0
    for a in range(0, 360, 9):
        if within(a, lv["ap"] - 3, lv["ep"] + 3) or any(abs(norm(a - b + 180) - 180) < 4 for b in lv["butt"]):
            continue
        if any(abs(norm(a - d + 180) - 180) < 5 for d in (282, 12)):     # 门洞
            continue
        hz = z + 1.0 + (i * 1.7) % 3.6
        ln = 0.8 + (i * 0.37) % 1.2
        x, y, _ = polar(R_IN - 0.01, a)
        k.box((ln, 0.05, 0.12), (x, y, hz), rot=(0, 0, a - 90))
        i += 1
    k.build("slits", smooth=0, collide=False, shadow=False, emit=1.0, **GLOW)


def bottom():
    """井底：白的圆厅；台阶落进一汪浅水，水里映着井口那一圈天光（走进去回家）"""
    z = zl(NL)
    c = zl(NL - 1) - SLAB
    box = (-16.0, -16.0, z - 0.1, 16.0, 16.0, c + 0.1)
    nx.into("bottom")
    k = fu.Kit()

    def present(r, a):
        return POOL_R <= r <= HALL_R + 0.8

    slab(k, [POOL_R, HALL_R + 0.8], z - 1.0, z, present)
    build_kit(k, "floor5", **FLOORS[NL])
    sh.tube("hall_wall", HALL_R + 0.8, HALL_R, c - z + 0.15, (0, 0, z - 0.1), segments=128, **WALLS[NL])
    # 明梯：第四层下来的那段
    k = fu.Kit()
    stair_steps(k, STAIR_A[NL - 1], STAIR_A[NL - 1] + SPAN, SI + 0.05, SO, zl(NL - 1), z)
    build_kit(k, "stairs5", **FLOORS[NL - 1])
    rings = [(POOL_R, 5.0), (5.0, 4.0)]
    for i, (ro, ri) in enumerate(rings):
        sh.tube(f"pool_step{i}", ro, ri, 1.0, (0, 0, z - 1.0 - RISE * (i + 1)), segments=128, **FLOORS[NL])
    deep = z - RISE * 3
    nx.cylinder("pool_floor", 4.0, 4.0, 1.0, (0, 0, deep - 1.0), segments=128, a="mist", b="blue_pale", pattern="tiles")
    wz = z - 0.45
    nx.cylinder("pool", POOL_R - 0.02, POOL_R - 0.02, 0.04, (0, 0, wz - 0.04), segments=96, collide=False,
                shadow=False, ramp=("blue", "blue_pale", "white"), pattern="bands")
    sh.tube("mirror_rim", 2.0, 1.6, 0.03, (0, 0, wz + 0.005), segments=48, collide=False, shadow=False,
            a="lilac", b="lilac_dark", pattern="plain")
    nx.cylinder("mirror_sky", 1.6, 1.6, 0.04, (0, 0, wz + 0.005), segments=48, collide=False, shadow=False, emit=1.0,
                a="blue_pale", b="white", pattern="plain")
    nx.portal("portal_home", (0, 0, deep + 0.9), "house", at="descent", mode="walk", radius=1.1)
    for i, a in enumerate((30, 150, 270)):
        nx.lamp(f"hall_lamp{i}", polar(HALL_R - 1.5, a, z + 3.5), color=WARM, radius=6.0, power=0.5, box=box)


# ── 走一遍（给自动测试） ─────────────────────────────

def route(levels, dark=False):
    """从井口走到井底的一条路：[x, y, 种类, 层]（Blender 坐标的脚底，只用水平位置）"""
    pts = []

    def at(r, a, tag, n):
        x, y, _ = polar(r, a)
        pts.append([round(x, 3), round(y, 3), tag, n])

    def arc(r, a0, a1, tag, n, step=7.0):
        span = a1 - a0
        m = max(1, int(abs(span) // step))
        for i in range(1, m + 1):
            at(r, a0 + span * i / m, tag, n)

    def gal(n, a0, a1):
        """沿回廊从 a0 走到 a1（走不跨扶壁的那一边）"""
        lv = levels[n - 1]
        ccw = norm(a1 - a0)
        cw = norm(a0 - a1)
        span = ccw if not any(within(b, a0, a1) for b in lv["butt"]) else -cw
        arc(WALK_R, a0, a0 + span, "gal", n)

    for r, a in ((15.2, 270), (13.5, 250), (12.0, 205), (11.6, STAIR_A[0] - 7)):
        at(r, a, "court", 0)
    a0 = STAIR_A[0]
    at(SR, a0 - 5, "court", 0)
    arc(SR, a0 - 5, a0 + SPAN + 4, "stair0", 0)
    n = 1
    while n < NL:
        lv = levels[n - 1]
        if dark and n == 2:
            rt = lv["route_dark"]
        elif dark and n == 3:
            rt = levels[2]["route_dark_in"] + levels[2]["route"][5:]
        else:
            rt = lv["route"]
        if dark and n == 3:
            for r, a in rt:
                at(r, a, "cave", n)
        else:
            start = lv["ep"] + 9
            at(WALK_R, start, "gal", n)
            gal(n, start, rt[1][1])
            for r, a in rt[1:]:
                at(r, a, "cave", n)
        if dark and n == 2:
            # 暗梯：沿着梯走下去
            a0, r = lv["extra"]["dark"]
            arc(r, a0 - 1, a0 + deg_at(0.85 * STEPS, r) + 1, "dark2", n, step=5.0)
            n += 1
            continue
        an = lv["an"]
        gal(n, rt[-1][1], an - 9)
        at(SR, an - 5, "gal", n)
        arc(SR, an - 5, an + SPAN + 4, f"stair{n}", n)
        n += 1
    at(WALK_R, STAIR_A[NL - 1] + SPAN + 9, "gal", NL)
    return pts


def build(extent=EXTENT):
    nx.into("env")
    e, az = math.radians(80), math.radians(225)
    nx.sun((math.cos(e) * math.cos(az), math.cos(e) * math.sin(az), math.sin(e)))
    nx.atmosphere("lattice", grid=3, grid_lit=1, lamps=True)

    levels = [level_plan(n) for n in range(1, NL)]

    nx.into("court")
    court(levels[0]["extra"]["sky"])
    nx.into("sky_stair")
    sky_stair()
    nx.into("towers")
    towers()
    boxes = {}
    for lv in levels:
        rest = {}
        if lv["n"] == 3:
            rest["dark_below"] = [levels[1]["extra"]["dark"]]
        boxes[lv["n"]] = build_level(lv, rest)
    nx.into("level1")
    models1(levels[0], boxes[1])
    nx.into("level2")
    hall2(levels[1], boxes[2])
    nx.into("level3")
    pillars3(levels[2])
    well3(levels[2], levels[3], boxes[3], boxes[4])
    nx.into("level4")
    slits4(levels[3])
    bottom()

    # 从家里的床来：落在井口的院子里，朝着井
    sx, sy, _ = polar(15.2, 270)
    nx.spawn((sx, sy, 0), facing_deg=0)
    nx.arrive("house", (sx, sy, 0), facing_deg=0)

    for env, dark in (("DESCENT_ROUTE", False), ("DESCENT_ROUTE_DARK", True)):
        out = os.environ.get(env)
        if out:
            with open(out, "w", encoding="utf-8") as f:
                json.dump(dict(pts=route(levels, dark)), f)


if __name__ == "__main__":
    nx.reset()
    build()
    nx.save_blend("descent")
    nx.export("descent")
