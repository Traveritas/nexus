"""家具与器物：自己的低面数构件，替代现成模型（nx_mat=asset）。

造型语言：
- 倒角方块、车床回转体（8~10 边，留着棱）、两头尖的叶板；不贴图，颜色只走 nx_pal + nx_pattern。
- 比例略夸张、略粗壮：腿不细于 5~6cm，远看不闪；每件只保留一个认得出的特征（摇椅的弧脚、落地钟的长身）。
- 同一件东西里同色的零件合成一个物体（零件之间不勾线），不同色的分开（之间有轮廓线）。
- 面数预算：普通家具 ≤ 200 三角形，传送物 ≤ 500。

朝向约定：所有家具本地 +Y 是正面（人坐下时脸朝的方向、钟面朝的方向），loc 是落地的底面中心。
yaw 与 nx 的朝向一致：0 ＝ 正面朝 +Y，90 ＝ 朝 -X。
"""
import math
import random

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

import nx

WOOD = dict(a="rose", b="rose_deep", pattern="bands")
WOOD_DARK = dict(a="rose_deep", b="violet", pattern="bands")
WOOD_PALE = dict(a="pink_pale", b="rose", pattern="bands")
WHITE = dict(a="white", b="mist", pattern="plain")
INK = dict(a="violet_deep", b="ink", pattern="plain")
# 金色背光时会被量化成绿色，所以小零件的「金属」用浅粉，灯的亮面用白
BRASS = dict(a="pink_pale", b="white", pattern="plain")
GLOW = dict(a="white", b="mist", pattern="plain")
LEAF = dict(a="green", b="blue", pattern="plain")
FABRICS = {
    "blue": dict(a="blue_pale", b="white", pattern="grain"),
    "pink": dict(a="pink_pale", b="pink", pattern="grain"),
    "lilac": dict(a="lilac_pale", b="lilac", pattern="grain"),
    "rose": dict(a="pink", b="rose", pattern="grain"),
    "white": dict(a="white", b="mist", pattern="grain"),
}


def _m(loc, rot):
    return Matrix.Translation(Vector(loc)) @ Euler([math.radians(a) for a in rot], "XYZ").to_matrix().to_4x4()


# ── 零件拼装 ─────────────────────────────────────

class Kit:
    """把一件东西里同色的零件攒成一个网格。坐标都是这件东西的本地坐标（Z 朝上，底面中心是原点）"""

    def __init__(self):
        self.v = []
        self.f = []

    def _add(self, verts, faces, loc=(0, 0, 0), rot=(0, 0, 0)):
        m = _m(loc, rot)
        o = len(self.v)
        self.v += [tuple(m @ Vector(p)) for p in verts]
        self.f += [tuple(i + o for i in fc) for fc in faces]
        return self

    def box(self, size, loc=(0, 0, 0), rot=(0, 0, 0), bevel=0.0, base=True):
        """长方体；base=True 时 loc 是底面中心；bevel>0 时十二条棱倒一刀斜角（44 个三角形，不倒是 12 个）"""
        sx, sy, sz = size
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Diagonal((sx, sy, sz, 1)))
        if bevel > 0:
            b = min(bevel, sx / 2.2, sy / 2.2, sz / 2.2)
            try:
                bmesh.ops.bevel(bm, geom=list(bm.verts) + list(bm.edges), offset=b, segments=1, profile=0.5, affect="EDGES")
            except TypeError:
                bmesh.ops.bevel(bm, geom=list(bm.verts) + list(bm.edges), offset=b, segments=1, profile=0.5, vertex_only=False)
        bm.verts.index_update()
        dz = sz / 2 if base else 0
        verts = [(v.co.x, v.co.y, v.co.z + dz) for v in bm.verts]
        faces = [[v.index for v in fc.verts] for fc in bm.faces]
        bm.free()
        return self._add(verts, faces, loc, rot)

    def lathe(self, profile, loc=(0, 0, 0), rot=(0, 0, 0), seg=10, start=0.0):
        """回转体：profile 是自下而上的 (半径, 高) 序列；半径为 0 的点收成尖，两端半径不为 0 时封口"""
        verts, faces, rings = [], [], []
        a0 = math.radians(start)
        for r, z in profile:
            if r < 1e-6:
                rings.append([len(verts)])
                verts.append((0, 0, z))
            else:
                ring = []
                for i in range(seg):
                    a = a0 + 2 * math.pi * i / seg
                    ring.append(len(verts))
                    verts.append((math.cos(a) * r, math.sin(a) * r, z))
                rings.append(ring)
        for ra, rb in zip(rings, rings[1:]):
            if len(ra) == 1 and len(rb) == 1:
                continue
            for i in range(seg):
                j = (i + 1) % seg
                if len(ra) == 1:
                    faces.append((ra[0], rb[j], rb[i]))
                elif len(rb) == 1:
                    faces.append((ra[i], ra[j], rb[0]))
                else:
                    faces.append((ra[i], ra[j], rb[j], rb[i]))
        if len(rings[0]) > 1:
            faces.append(tuple(reversed(rings[0])))
        if len(rings[-1]) > 1:
            faces.append(tuple(rings[-1]))
        return self._add(verts, faces, loc, rot)

    def cyl(self, r, h, loc=(0, 0, 0), rot=(0, 0, 0), seg=10, r2=None):
        """圆柱 / 圆台，底面中心在 loc，沿本地 Z"""
        return self.lathe([(r, 0), (r if r2 is None else r2, h)], loc, rot, seg)

    def band(self, R, t, w, a0, a1, loc=(0, 0, 0), rot=(0, 0, 0), seg=8):
        """弧形的条：圆心在 loc，在本地 YZ 平面里从 a0 到 a1 度（0 度＝+Y，90 度＝+Z），厚 t（向圆心）、宽 w（沿 X）"""
        verts, faces = [], []
        for i in range(seg + 1):
            a = math.radians(a0 + (a1 - a0) * i / seg)
            c, s = math.cos(a), math.sin(a)
            for rr in (R, R - t):
                for x in (-w / 2, w / 2):
                    verts.append((x, c * rr, s * rr))
        for i in range(seg):
            o, p = i * 4, (i + 1) * 4
            faces += [(o, o + 1, p + 1, p), (o + 2, p + 2, p + 3, o + 3), (o, p, p + 2, o + 2), (o + 1, o + 3, p + 3, p + 1)]
        e = seg * 4
        faces += [(0, 2, 3, 1), (e, e + 1, e + 3, e + 2)]
        return self._add(verts, faces, loc, rot)

    def leaf(self, length, width, thick=0.02, loc=(0, 0, 0), rot=(0, 0, 0), waist=0.45):
        """两头尖的叶板：沿本地 +X 伸出，宽在 Y，厚在 Z（同 prefabs.plate，16 个顶点）"""
        L, W = length, width / 2
        outline = [(0, 0), (L * 0.18, W * 0.62), (L * waist, W), (L * 0.86, W * 0.5), (L, 0),
                   (L * 0.86, -W * 0.5), (L * waist, -W), (L * 0.18, -W * 0.62)]
        n = len(outline)
        verts = [(x, y, -thick / 2) for x, y in outline] + [(x, y, thick / 2) for x, y in outline]
        faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
        for i in range(n):
            j = (i + 1) % n
            faces.append((i, j, n + j, n + i))
        return self._add(verts, faces, loc, rot)

    def build(self, name, parent=None, loc=(0, 0, 0), rot=(0, 0, 0), smooth=40, collide=True, shadow=True, **style):
        if not self.f:
            return None
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        obj = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(obj)
        nx._place(obj, loc, rot, parent)
        if smooth:
            nx._smooth(obj, smooth)
        return nx.matte(obj, collide=collide, shadow=shadow, **style)


class Piece:
    """一件东西：一个空物体做父级，下面按颜色分几个 Kit"""

    def __init__(self, name, loc, yaw=0.0, parent=None, rot=None):
        self.name = name
        self.g = nx.group(name, loc, rot if rot is not None else (0, 0, yaw))
        self.g["nx_piece"] = 1  # 穿模检查（blender/clip.py）按它认「一件」
        if parent is not None:
            self.g.parent = parent
        self.kits = {}

    def __getitem__(self, key):
        return self.kits.setdefault(key, Kit())

    def done(self, styles, collide=True, shadow=True, **per_key):
        """styles：{kit 名: 样式}；per_key：{kit 名: dict(collide=…, shadow=…)} 单独覆盖"""
        for key, kit in self.kits.items():
            opts = dict(collide=collide, shadow=shadow)
            opts.update(per_key.get(key, {}))
            kit.build(f"{self.name}_{key}", parent=self.g, **opts, **styles[key])
        return self.g


# ── 椅 ───────────────────────────────────────────

def chair(name, loc, yaw=0.0, kind="dining", fabric="blue", wood=WOOD, parent=None):
    """椅：dining 餐椅（靠背一条宽横档）· arm 扶手沙发椅（敦实的块）· lounge 低矮的躺椅 · rocking 摇椅（弧脚）"""
    p = Piece(name, loc, yaw, parent)
    fab = FABRICS[fabric] if isinstance(fabric, str) else fabric
    if kind == "dining":
        w, d, sh = 0.46, 0.44, 0.45
        p["wood"].box((w, d, 0.06), (0, 0, sh - 0.06), bevel=0.015)
        for sx in (-1, 1):
            for sy in (-1, 1):
                p["wood"].box((0.06, 0.06, sh - 0.06), (sx * (w / 2 - 0.04), sy * (d / 2 - 0.04), 0))
            p["wood"].box((0.06, 0.06, 0.5), (sx * (w / 2 - 0.04), -d / 2 + 0.04, sh), rot=(6, 0, 0))
        p["wood"].box((w + 0.02, 0.06, 0.2), (0, -d / 2 + 0.01, sh + 0.34), rot=(6, 0, 0), bevel=0.02)
        p["fabric"].box((w - 0.06, d - 0.06, 0.06), (0, 0.01, sh), bevel=0.025)
        return p.done({"wood": wood, "fabric": fab})
    if kind == "arm":
        w, d = 0.86, 0.8
        for sx in (-1, 1):
            for sy in (-1, 1):
                p["wood"].box((0.07, 0.07, 0.1), (sx * (w / 2 - 0.08), sy * (d / 2 - 0.08), 0))
        p["body"].box((w, d, 0.24), (0, 0, 0.1), bevel=0.04)
        for sx in (-1, 1):
            p["body"].box((0.16, d, 0.36), (sx * (w / 2 - 0.08), 0, 0.3), bevel=0.05)
        p["body"].box((w, 0.2, 0.62), (0, -d / 2 + 0.1, 0.3), rot=(8, 0, 0), bevel=0.05)
        p["cushion"].box((w - 0.34, d - 0.26, 0.14), (0, 0.08, 0.34), bevel=0.05)
        p["cushion"].box((w - 0.36, 0.14, 0.4), (0, -d / 2 + 0.26, 0.46), rot=(12, 0, 0), bevel=0.05)
        return p.done({"wood": WOOD_DARK, "body": fab, "cushion": FABRICS["white"] if fabric != "white" else FABRICS["pink"]})
    if kind == "lounge":
        w = 0.78
        for sx in (-1, 1):
            for sy, tilt in ((1, 12), (-1, -12)):
                p["wood"].box((0.06, 0.06, 0.33), (sx * (w / 2 - 0.08), sy * 0.24, 0.01), rot=(tilt, sx * -6, 0))
        p["wood"].box((w, 0.64, 0.07), (0, 0.04, 0.3), rot=(5, 0, 0), bevel=0.02)
        p["wood"].box((w, 0.07, 0.62), (0, -0.3, 0.32), rot=(18, 0, 0), bevel=0.02)
        p["cushion"].box((w - 0.08, 0.58, 0.11), (0, 0.06, 0.36), rot=(5, 0, 0), bevel=0.045)
        p["cushion"].box((w - 0.08, 0.12, 0.52), (0, -0.23, 0.42), rot=(18, 0, 0), bevel=0.045)
        return p.done({"wood": wood, "cushion": fab})
    if kind == "rocking":
        w, R = 0.52, 1.5
        for sx in (-1, 1):
            # 弧脚：一段大圆弧，最低点落在原点下方
            p["wood"].band(R, 0.05, 0.05, -112, -66, (sx * (w / 2 - 0.03), 0.02, R + 0.0), seg=8)
            for y in (0.2, -0.22):
                p["wood"].box((0.055, 0.055, 0.42), (sx * (w / 2 - 0.03), y, 0.02))
            p["wood"].box((0.055, 0.055, 0.72), (sx * (w / 2 - 0.03), -0.22, 0.42), rot=(14, 0, 0))
            p["wood"].box((0.07, 0.48, 0.05), (sx * (w / 2 - 0.0), -0.02, 0.66), bevel=0.015)
            p["wood"].box((0.05, 0.05, 0.22), (sx * (w / 2 - 0.0), 0.18, 0.44))
        p["wood"].box((w, 0.48, 0.05), (0, 0, 0.42), bevel=0.015)
        p["wood"].box((w + 0.04, 0.06, 0.12), (0, -0.39, 1.1), rot=(14, 0, 0), bevel=0.02)
        for k in range(3):
            p["wood"].box((0.07, 0.03, 0.56), ((k - 1) * 0.14, -0.27, 0.5), rot=(14, 0, 0))
        p["fabric"].box((w - 0.08, 0.42, 0.05), (0, 0.01, 0.47), bevel=0.02)
        return p.done({"wood": wood, "fabric": fab})
    raise ValueError(kind)


def bench(name, loc, yaw=0.0, length=1.3, style=None, parent=None):
    """长凳：一块厚板，两片板腿，一根横撑"""
    p = Piece(name, loc, yaw, parent)
    p["wood"].box((length, 0.38, 0.07), (0, 0, 0.41), bevel=0.02)
    for sx in (-1, 1):
        p["wood"].box((0.07, 0.32, 0.41), (sx * (length / 2 - 0.16), 0, 0), bevel=0.012)
    p["wood"].box((length - 0.32, 0.05, 0.07), (0, 0, 0.12))
    return p.done({"wood": style or dict(a="blue_pale", b="blue", pattern="bands")})


# ── 架与书 ───────────────────────────────────────

BOOK_COLORS = [dict(a="violet", b="violet_deep", pattern="plain"), dict(a="rose", b="rose_deep", pattern="plain"),
               dict(a="blue", b="blue_pale", pattern="plain"), dict(a="pink_pale", b="pink", pattern="plain"),
               dict(a="lilac_dark", b="violet", pattern="plain"), dict(a="white", b="mist", pattern="plain")]


def books_row(piece, x0, x1, y, z, h_max, seed, fill=0.85):
    """在 [x0, x1] 上排一行书（书脊朝 +Y），偶尔斜靠、偶尔平放一摞；颜色相邻不重复"""
    r = random.Random(seed)
    x, last = x0, -1
    while x < x1 - 0.03:
        if r.random() > fill:
            x += r.uniform(0.05, 0.14)
            continue
        c = r.choice([i for i in range(len(BOOK_COLORS)) if i != last])
        last = c
        kit = piece[f"book{c}"]
        if r.random() < 0.08 and x1 - x > 0.3:
            # 平放的一摞
            hz = 0.0
            for k in range(r.randint(2, 4)):
                t = r.uniform(0.03, 0.05)
                kit.box((r.uniform(0.2, 0.26), 0.2, t), (x + 0.13, y, z + hz), rot=(0, 0, r.uniform(-6, 6)))
                hz += t
            x += 0.3
            continue
        t, hh = r.uniform(0.03, 0.06), h_max * r.uniform(0.7, 0.98)
        if r.random() < 0.1 and x > x0 + 0.1:
            kit.box((t, 0.2, hh), (x + 0.06, y, z), rot=(0, 18, 0))
            x += 0.12
            continue
        kit.box((t, r.uniform(0.16, 0.22), hh), (x + t / 2, y, z))
        x += t + 0.004


def bookshelf(name, loc, yaw=0.0, w=0.95, h=1.95, d=0.34, shelves=4, seed=0, wood=WOOD_DARK, parent=None):
    """书架：两侧板、顶盖、踢脚、背板，层板上排满书。正面 +Y"""
    p = Piece(name, loc, yaw, parent)
    t = 0.06
    for sx in (-1, 1):
        p["wood"].box((t, d, h), (sx * (w / 2 - t / 2), 0, 0), bevel=0.01)
    p["wood"].box((w + 0.06, d + 0.04, 0.06), (0, 0.01, h), bevel=0.02)
    p["wood"].box((w - 2 * t, d - 0.02, 0.1), (0, 0.01, 0))
    p["back"].box((w - 2 * t, 0.02, h - 0.1), (0, -d / 2 + 0.02, 0.1))
    gap = (h - 0.1) / shelves
    for k in range(shelves):
        z = 0.1 + k * gap
        if k:
            p["wood"].box((w - 2 * t + 0.02, d - 0.03, 0.035), (0, 0.0, z - 0.035))  # 两头插进侧板，端面不和背板共面
        books_row(p, -w / 2 + t + 0.01, w / 2 - t - 0.01, 0.0, z, gap - 0.08, seed * 31 + k)
    styles = {"wood": wood, "back": dict(a="violet_deep", b="violet", pattern="plain")}
    styles.update({f"book{i}": c for i, c in enumerate(BOOK_COLORS)})
    return p.done(styles, **{f"book{i}": dict(collide=False) for i in range(len(BOOK_COLORS))})


def notebook(name, loc, yaw=0.0, cover="blue", parent=None):
    p = Piece(name, loc, yaw, parent)
    p["cover"].box((0.22, 0.29, 0.012), (0, 0, 0), bevel=0.004)
    p["cover"].box((0.22, 0.29, 0.008), (0, 0, 0.032))
    p["pages"].box((0.205, 0.28, 0.022), (0.004, 0, 0.011))
    return p.done({"cover": dict(a=cover, b="violet", pattern="plain"), "pages": WHITE}, collide=False)


# ── 灯 ───────────────────────────────────────────

def pendant(name, loc, drop=0.5, shade="white", parent=None):
    """吊灯：loc 是天花板上的挂点；一根吊线、一只钟形罩、罩口一圈亮面"""
    p = Piece(name, loc, 0, parent)
    p["cord"].box((0.03, 0.03, drop), (0, 0, -drop))
    p["shade"].lathe([(0.0, -drop + 0.02), (0.05, -drop + 0.02), (0.07, -drop - 0.04), (0.16, -drop - 0.15),
                      (0.22, -drop - 0.24)], seg=10)
    p["glow"].cyl(0.19, 0.01, (0, 0, -drop - 0.235), seg=10)
    return p.done({"cord": INK, "shade": dict(a=shade, b="mist", pattern="plain"), "glow": GLOW}, collide=False, shadow=False)


def desk_lamp(name, loc, yaw=0.0, parent=None):
    """台灯：圆座、两节折臂、斜着朝前下方的灯罩"""
    p = Piece(name, loc, yaw, parent)
    p["metal"].cyl(0.09, 0.03, seg=10)
    # 下臂向前斜上，上臂接在下臂顶端、几乎水平地伸出去，灯罩挂在上臂末端、口朝前下方
    p["metal"].box((0.03, 0.03, 0.3), (0, 0, 0.03), rot=(-20, 0, 0))
    p["metal"].box((0.03, 0.03, 0.25), (0, 0.103, 0.312), rot=(-70, 0, 0))
    p["shade"].lathe([(0.0, 0.0), (0.04, 0.0), (0.05, -0.05), (0.1, -0.14)], (0, 0.33, 0.4), rot=(30, 0, 0), seg=8)
    return p.done({"metal": dict(a="violet", b="violet_deep", pattern="plain"), "shade": dict(a="pink", b="pink_pale", pattern="plain")}, collide=False)


def table_lamp(name, loc, yaw=0.0, height=0.45, shade="pink_pale", parent=None):
    """小台灯：鼓肚的座、圆台形的罩"""
    p = Piece(name, loc, yaw, parent)
    s = height / 0.45
    p["base"].lathe([(0.06 * s, 0), (0.09 * s, 0.06 * s), (0.08 * s, 0.14 * s), (0.03 * s, 0.22 * s), (0.015 * s, 0.26 * s)], seg=8)
    p["shade"].lathe([(0.15 * s, 0.22 * s), (0.09 * s, 0.45 * s)], seg=8)
    return p.done({"base": dict(a="blue_pale", b="blue", pattern="plain"), "shade": dict(a=shade, b="white", pattern="plain")},
                  collide=False)


def street_lamp(name, loc, yaw=0.0, height=3.4, parent=None):
    """路灯：八棱的柱、座、一盏方灯笼（亮面是金色）、四坡的顶"""
    p = Piece(name, loc, yaw, parent)
    p["iron"].lathe([(0.16, 0), (0.16, 0.12), (0.1, 0.22), (0.065, 0.3), (0.06, height - 0.45), (0.1, height - 0.4)], seg=8, start=22.5)
    top = height - 0.4
    for sx in (-1, 1):
        for sy in (-1, 1):
            p["iron"].box((0.04, 0.04, 0.36), (sx * 0.12, sy * 0.12, top))
    p["iron"].lathe([(0.24, top + 0.36), (0.0, top + 0.56)], seg=4, start=45)
    p["glow"].box((0.2, 0.2, 0.3), (0, 0, top + 0.03))
    return p.done({"iron": INK, "glow": GLOW}, glow=dict(collide=False, shadow=False))


# ── 钟 ───────────────────────────────────────────

def _dial(p, r, loc, rot, hour, minute):
    """钟面：一个白盘、金边、两根针；盘面在本地 +Y 一侧"""
    x, y, z = loc
    p["face"].cyl(r, 0.02, (x, y, z), rot=(-90, 0, 0), seg=12)
    p["brass"].lathe([(r + 0.02, 0), (r + 0.02, 0.012), (r - 0.005, 0.012), (r - 0.005, 0)], (x, y - 0.002, z), rot=(-90, 0, 0), seg=12)
    for ang, L, wdt in ((hour, r * 0.55, 0.025), (minute, r * 0.85, 0.018)):
        p["ink"].box((wdt, 0.008, L), (x, y + 0.024, z), rot=(0, ang, 0))


def grandfather_clock(name, loc, yaw=0.0, height=2.2, parent=None):
    """落地钟：座、细长的身子（摆窗里一只金摆）、钟头、钟面、顶上的冠"""
    p = Piece(name, loc, yaw, parent)
    s = height / 2.2
    p["wood"].box((0.56, 0.36, 0.18 * s), (0, 0, 0), bevel=0.02)
    p["wood"].box((0.44, 0.28, 1.32 * s), (0, -0.02, 0.18 * s), bevel=0.015)
    hz = 1.5 * s
    p["wood"].box((0.56, 0.36, 0.5 * s), (0, 0, hz), bevel=0.025)
    p["wood"].box((0.62, 0.4, 0.06), (0, 0, hz + 0.5 * s), bevel=0.02)
    p["wood"].box((0.3, 0.34, 0.14 * s), (0, 0, hz + 0.5 * s + 0.06), bevel=0.03)
    p["ink"].box((0.24, 0.02, 0.86 * s), (0, 0.12, 0.38 * s))
    p["brass"].cyl(0.07, 0.02, (0, 0.135, 0.62 * s), rot=(-90, 0, 0), seg=10)
    p["brass"].box((0.02, 0.01, 0.42 * s), (0, 0.135, 0.66 * s))
    _dial(p, 0.17, (0, 0.18, hz + 0.25 * s), (0, 0, 0), hour=-60, minute=30)
    return p.done({"wood": WOOD_DARK, "ink": INK, "brass": BRASS, "face": WHITE},
                  ink=dict(collide=False), brass=dict(collide=False), face=dict(collide=False))


def wall_clock(name, loc, yaw=0.0, r=0.2, parent=None):
    """挂钟：loc 是钟心，钟背贴墙，正面 +Y"""
    p = Piece(name, loc, yaw, parent)
    p["rim"].lathe([(r + 0.04, 0), (r + 0.04, 0.05), (r, 0.06), (r, 0.0)], rot=(-90, 0, 0), seg=12)
    _dial(p, r, (0, 0.005, 0), (0, 0, 0), hour=100, minute=-20)  # 钟面离开钟背 5mm，不和边框的底共面
    return p.done({"rim": WOOD, "ink": INK, "brass": BRASS, "face": WHITE}, collide=False)


def alarm_clock(name, loc, yaw=0.0, parent=None):
    """闹钟：圆鼓的身子、顶上两只铃、两只短脚"""
    p = Piece(name, loc, yaw, parent)
    r = 0.065
    p["body"].cyl(r, 0.05, (0, -0.025, r + 0.02), rot=(-90, 0, 0), seg=12)
    for sx in (-1, 1):
        p["body"].box((0.02, 0.03, 0.03), (sx * 0.04, 0, 0))
        p["brass"].lathe([(0.03, 0), (0.028, 0.014), (0.0, 0.03)], (sx * 0.04, 0, 2 * r + 0.01), rot=(0, sx * 30, 0), seg=8)
    _dial(p, r - 0.012, (0, 0.025, r + 0.02), (0, 0, 0), hour=-45, minute=70)
    return p.done({"body": dict(a="pink", b="rose", pattern="plain"), "brass": BRASS, "ink": INK, "face": WHITE}, collide=False)


# ── 器与草木 ─────────────────────────────────────

VASES = {
    # (半径, 高) 归一到高 1
    "round": [(0.2, 0), (0.32, 0.08), (0.42, 0.35), (0.36, 0.62), (0.16, 0.8), (0.14, 0.92), (0.2, 1.0)],
    "tall": [(0.16, 0), (0.24, 0.1), (0.26, 0.55), (0.14, 0.82), (0.11, 0.9), (0.16, 1.0)],
    "bottle": [(0.2, 0), (0.3, 0.06), (0.3, 0.45), (0.1, 0.62), (0.07, 0.92), (0.1, 1.0)],
    "bowl": [(0.3, 0), (0.55, 0.3), (0.7, 0.75), (0.72, 1.0)],
}


def vase(name, loc, height=0.4, kind="round", style=None, flowers=0, seed=0, parent=None):
    """花瓶 / 罐 / 钵（kind 见 VASES）。flowers>0 时插几枝花：直杆、杯形的花头"""
    p = Piece(name, loc, 0, parent)
    p["vase"].lathe([(r * height, z * height) for r, z in VASES[kind]], seg=10)
    r = random.Random(seed)
    heads = [dict(a="pink", b="pink_pale", pattern="plain"), dict(a="white", b="pink_pale", pattern="plain"),
             dict(a="blue_pale", b="white", pattern="plain")]
    s = max(1.0, height / 0.4)  # 大瓶子的花杆、花头跟着放大（细杆远看会闪）
    for k in range(flowers):
        az = 360 * k / flowers + r.uniform(-25, 25)
        lean = r.uniform(8, 22)
        L = height * r.uniform(0.7, 1.15)
        a = math.radians(az)
        tilt = math.radians(lean)
        top = (math.cos(a) * math.sin(tilt) * L, math.sin(a) * math.sin(tilt) * L, height * 0.85 + math.cos(tilt) * L)
        # 杆：从瓶口向外斜（rot 的 Y 轴先倾、Z 轴再转到方位上）
        p["stem"].box((0.018 * s, 0.018 * s, L), (0, 0, height * 0.85), rot=(0, lean, az))
        p[f"head{k % 3}"].lathe([(0.0, -0.02 * s), (0.035 * s, 0.0), (0.075 * s, 0.05 * s), (0.06 * s, 0.06 * s), (0.0, 0.035 * s)], top,
                                rot=(0, lean, az), seg=6, start=r.uniform(0, 60))
    styles = {"vase": style or dict(a="blue_pale", b="white", pattern="plain"), "stem": LEAF}
    styles.update({f"head{i}": heads[i] for i in range(3)})
    return p.done(styles, collide=False)


def plant(name, loc, height=1.1, kind="potted", pot=None, seed=0, parent=None):
    """盆栽：kind=potted 一蓬向外张的叶 · tall 一根直茎、叶沿茎互生 · tuft 矮的一丛（种在槽里，不带盆）"""
    p = Piece(name, loc, 0, parent)
    r = random.Random(seed)
    base = 0.0
    if kind != "tuft":
        ph = min(0.32, height * 0.3)
        pr = ph * 0.62
        p["pot"].lathe([(pr * 0.72, 0), (pr, ph * 0.9), (pr * 1.1, ph * 0.92), (pr * 1.1, ph), (pr * 0.9, ph)], seg=10)
        p["soil"].cyl(pr * 0.92, 0.02, (0, 0, ph - 0.03), seg=10)
        base = ph
    if kind in ("potted", "tuft"):
        n = 9 if kind == "potted" else 6
        L0 = (height - base) * 0.8
        for k in range(n):
            az = 360 * k / n + r.uniform(-15, 15)
            el = r.uniform(30, 75)
            L = L0 * r.uniform(0.65, 1.05)
            p["leaf"].leaf(L, L * 0.32, 0.02, (0, 0, base), rot=(0, -el, az))
    elif kind == "tall":
        stem = height - base
        p["stem"].box((0.04, 0.04, stem * 0.9), (0, 0, base))
        for k in range(8):
            z = base + stem * (0.2 + 0.75 * k / 8)
            L = 0.32 * (1.15 - k / 10)
            p["leaf"].leaf(L, L * 0.45, 0.02, (0, 0, z), rot=(0, -r.uniform(10, 40), k * 137.5))
    else:
        raise ValueError(kind)
    return p.done({"pot": pot or dict(a="rose", b="rose_deep", pattern="plain"), "soil": INK, "leaf": LEAF, "stem": LEAF},
                  leaf=dict(collide=False), stem=dict(collide=False), soil=dict(collide=False))


def planter(name, loc, yaw=0.0, length=1.2, seed=0, parent=None):
    """花槽：木槽一只，里面一排矮丛"""
    p = Piece(name, loc, yaw, parent)
    p["box"].box((length, 0.36, 0.4), bevel=0.02)
    p["soil"].box((length - 0.1, 0.26, 0.02), (0, 0, 0.37))
    p.done({"box": dict(a="white", b="mist", pattern="bands"), "soil": INK}, soil=dict(collide=False))
    for k in range(3):
        plant(f"{name}_tuft{k}", ((k - 1) * length / 3, 0, 0.38), height=0.5, kind="tuft", seed=seed * 7 + k, parent=p.g)
    return p.g


# ── 床 ───────────────────────────────────────────

def bed(name, loc, yaw=0.0, parent=None):
    """床：床头朝本地 +Y，loc 是床的底面中心。床架、床头板、床尾板、床垫、被子（两侧与床尾垂下）、翻折的被头、
    两只枕头、床尾搭着一条毯子。零件各是一个物体（之间有轮廓线）"""
    L, W = 2.2, 1.85
    g = nx.group(name, loc, (0, 0, yaw))
    if parent is not None:
        g.parent = parent
    g["nx_piece"] = 1  # 穿模检查按它认「一件」
    y0, y1 = -L / 2, L / 2

    def b(part, size, at, rot=(0, 0, 0), collide=True, **style):
        nx.box(f"{name}_{part}", size, at, rot=rot, parent=g, collide=collide, **style)
    b("frame", (W + 0.08, L, 0.32), (0, 0, 0), **WOOD)
    b("head", (W + 0.12, 0.1, 1.15), (0, y1 + 0.02, 0), **WOOD)
    b("head_cap", (W + 0.22, 0.16, 0.08), (0, y1 + 0.02, 1.15), **WOOD_DARK)
    for i in range(5):
        b(f"head_slat{i}", (0.1, 0.03, 0.55), (-0.7 + i * 0.35, y1 - 0.04, 0.45), collide=False, a="rose_deep", b="rose", pattern="plain")
    b("foot", (W + 0.12, 0.1, 0.62), (0, y0 - 0.02, 0), **WOOD)
    top = 0.32
    b("mattress", (W - 0.05, L - 0.12, 0.24), (0, 0, top), **WHITE)
    m = top + 0.24
    quilt = dict(a="blue_pale", b="white", pattern="tiles")
    ql = 1.45
    qc = y0 + 0.08 + ql / 2
    b("quilt", (W + 0.06, ql, 0.1), (0, qc, m), **quilt)
    for sx in (-1, 1):
        b(f"quilt_side{sx}", (0.06, ql - 0.02, 0.41), (sx * (W / 2 + 0.03), qc, m - 0.32), collide=False, **quilt)
    b("quilt_fold", (W + 0.06, 0.26, 0.15), (0, qc + ql / 2 - 0.05, m), collide=False, a="white", b="blue_pale", pattern="plain")
    for i, (dx, r) in enumerate([(-0.45, 4), (0.42, -6)]):
        b(f"pillow{i}", (0.72, 0.42, 0.17), (dx, y1 - 0.32, m), rot=(0, 0, r), collide=False,
          a="white" if i == 0 else "pink_pale", b="mist", pattern="plain")
    b("cushion", (0.36, 0.14, 0.32), (0.05, y1 - 0.55, m + 0.02), rot=(-18, 0, 10), collide=False, a="pink", b="rose", pattern="stripes")
    blanket = dict(a="pink", b="pink_pale", pattern="stripes")
    b("throw", (W + 0.1, 0.55, 0.05), (0, y0 + 0.4, m + 0.1), collide=False, **blanket)
    b("throw_drop", (W + 0.1, 0.05, 0.28), (0, y0 + 0.1, m - 0.2), collide=False, **blanket)
    return g
