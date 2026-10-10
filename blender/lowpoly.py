"""干净低模的建模工具：现实的世界（wake_*）用，不和梦里的家具库共用任何模型。

- Geo：一团几何，攒顶点与面（本地坐标，Z 朝上）；常用形都在这里：方块、按轮廓拉伸的板、圆柱/圆台、车床体、
  低面数的团块（树冠、猫）、顶面起伏的软垫（被子）、单面片。
- Thing：一件东西 ＝ 一个空物体做父级，下面按颜色分几团 Geo；done() 时每团建成一个网格，标成 nx_mat=clean。
  同色的零件合成一个网格；不同色的分开。

避免共面闪烁的规矩（zfight.py 会查）：
- 两个不同颜色的面，朝向相同又贴在同一平面上重叠，就会闪。放在别的东西上面没关系（底面朝下、顶面朝上，方向相反）；
  并排贴着、错开 1–2mm 的都要错开到不重叠，或者让其中一个高出几毫米。
- 镶嵌、贴面的东西（画框、开关、窗框）一律比墙面凸出至少几毫米。
"""
import math
import random

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

import nx


def soft(hexcol, sat=0.6):
    """降饱和：HLS 的饱和度乘 sat（现实的世界整体再淡一点）"""
    import colorsys
    r, g, b = (int(hexcol[i:i + 2], 16) / 255 for i in (1, 3, 5))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    r, g, b = colorsys.hls_to_rgb(h, l, s * sat)
    return "#%02x%02x%02x" % tuple(round(c * 255) for c in (r, g, b))


def torn_outline(x0, y0, x1, y1, torn, seed=0, bite=0.5, step=0.35):
    """矩形的俯视轮廓，torn 里列出的边（'s' 'e' 'n' 'w'）撕成参差的：每 step 米一个点，往里咬 0..bite 米。
    逆时针：南边（y0）从西往东 → 东边 → 北边 → 西边"""
    r = random.Random(seed)
    sides = [("s", (x0, y0), (x1, y0), (0, 1)), ("e", (x1, y0), (x1, y1), (-1, 0)),
             ("n", (x1, y1), (x0, y1), (0, -1)), ("w", (x0, y1), (x0, y0), (1, 0))]
    pts = []
    for key, (ax, ay), (bx, by), (nx_, ny_) in sides:
        L = math.hypot(bx - ax, by - ay)
        m = max(1, int(L / step)) if key in torn else 1
        for i in range(m):
            t = i / m
            px, py = ax + (bx - ax) * t, ay + (by - ay) * t
            if key in torn:
                # 撕口：大多浅浅地咬一口，偶尔深深地缺一块；角上与上一条边一起撕
                d = r.uniform(0.0, bite) * (1.8 if r.random() < 0.15 else 1.0) * (0.6 if i == 0 else 1.0)
                jit = r.uniform(-0.08, 0.08) if i > 0 else 0.0
                px += nx_ * d + jit * (1 - abs(nx_))
                py += ny_ * d + jit * (1 - abs(ny_))
            pts.append((px, py))
    return pts


def _m(loc, rot):
    return Matrix.Translation(Vector(loc)) @ Euler([math.radians(a) for a in rot], "XYZ").to_matrix().to_4x4()


class Geo:
    def __init__(self):
        self.v = []
        self.f = []

    def add(self, verts, faces, loc=(0, 0, 0), rot=(0, 0, 0)):
        m = _m(loc, rot)
        o = len(self.v)
        self.v += [tuple(m @ Vector(p)) for p in verts]
        self.f += [tuple(i + o for i in fc) for fc in faces]
        return self

    # ── 方块 ──
    def box(self, size, loc=(0, 0, 0), rot=(0, 0, 0), base=True):
        """长方体；base=True 时 loc 是底面中心，否则是体心"""
        sx, sy, sz = size
        z0 = 0 if base else -sz / 2
        x, y = sx / 2, sy / 2
        verts = [(-x, -y, z0), (x, -y, z0), (x, y, z0), (-x, y, z0),
                 (-x, -y, z0 + sz), (x, -y, z0 + sz), (x, y, z0 + sz), (-x, y, z0 + sz)]
        faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        return self.add(verts, faces, loc, rot)

    def cuboid(self, x0, x1, y0, y1, z0, z1):
        """按两角给的长方体（世界轴向）"""
        return self.box((x1 - x0, y1 - y0, z1 - z0), ((x0 + x1) / 2, (y0 + y1) / 2, z0))

    def chamfer(self, size, c, loc=(0, 0, 0), rot=(0, 0, 0)):
        """四条竖棱切角的方块（俯视是八边形），底面中心在 loc：软一点的家具块"""
        sx, sy, sz = size
        x, y = sx / 2, sy / 2
        c = min(c, x * 0.9, y * 0.9)
        out = [(-x + c, -y), (x - c, -y), (x, -y + c), (x, y - c), (x - c, y), (-x + c, y), (-x, y - c), (-x, -y + c)]
        return self.prism(out, 0, sz, loc, rot)

    # ── 板 ──
    def prism(self, outline, z0, z1, loc=(0, 0, 0), rot=(0, 0, 0)):
        """俯视轮廓 [(x, y)]（可以凹）沿本地 Z 从 z0 拉到 z1"""
        n = len(outline)
        verts = [(x, y, z0) for x, y in outline] + [(x, y, z1) for x, y in outline]
        faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
        for i in range(n):
            j = (i + 1) % n
            faces.append((i, j, n + j, n + i))
        return self.add(verts, faces, loc, rot)

    def slab_xz(self, outline, y0, y1):
        """立面轮廓 [(x, z)] 沿 Y 从 y0 拉到 y1（墙、画、门扇）"""
        n = len(outline)
        verts = [(x, y0, z) for x, z in outline] + [(x, y1, z) for x, z in outline]
        faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
        for i in range(n):
            j = (i + 1) % n
            faces.append((i, j, n + j, n + i))
        return self.add(verts, faces)

    def slab_yz(self, outline, x0, x1):
        """立面轮廓 [(y, z)] 沿 X 从 x0 拉到 x1"""
        n = len(outline)
        verts = [(x0, y, z) for y, z in outline] + [(x1, y, z) for y, z in outline]
        faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
        for i in range(n):
            j = (i + 1) % n
            faces.append((i, j, n + j, n + i))
        return self.add(verts, faces)

    # ── 回转体 ──
    def lathe(self, profile, seg=8, loc=(0, 0, 0), rot=(0, 0, 0), start=0.0):
        """车床体：profile 是自下而上的 (半径, 高)；半径 0 收尖，两端不为 0 时封口"""
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
            for i in range(seg):
                j = (i + 1) % seg
                if len(ra) == 1 and len(rb) == 1:
                    continue
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
        return self.add(verts, faces, loc, rot)

    def cyl(self, r, h, seg=8, loc=(0, 0, 0), rot=(0, 0, 0), r2=None, start=0.0):
        """圆柱 / 圆台，底面中心在 loc，沿本地 Z"""
        return self.lathe([(r, 0), (r if r2 is None else r2, h)], seg, loc, rot, start)

    def rod(self, p0, p1, r, seg=6):
        """两点之间一根细杆（电线、绳、腿）"""
        a, b = Vector(p0), Vector(p1)
        d = b - a
        L = d.length
        q = d.normalized().to_track_quat("Z", "Y")
        m = Matrix.Translation(a) @ q.to_matrix().to_4x4()
        o = len(self.v)
        g = Geo()
        g.cyl(r, L, seg)
        self.v += [tuple(m @ Vector(p)) for p in g.v]
        self.f += [tuple(i + o for i in fc) for fc in g.f]
        return self

    # ── 团块与软垫 ──
    def blob(self, r, loc=(0, 0, 0), scale=(1, 1, 1), rings=4, seg=7, jitter=0.12, seed=0, rot=(0, 0, 0)):
        """低面数的团：经纬球，顶点随机推拉一点（树冠、石头、猫的身子）"""
        rr = random.Random(seed)
        verts, faces = [(0, 0, -r)], []
        for i in range(1, rings):
            phi = math.pi * i / rings - math.pi / 2
            for j in range(seg):
                th = 2 * math.pi * (j + 0.5 * (i % 2)) / seg
                k = 1 + rr.uniform(-jitter, jitter)
                verts.append((math.cos(phi) * math.cos(th) * r * k, math.cos(phi) * math.sin(th) * r * k, math.sin(phi) * r * k))
        verts.append((0, 0, r * (1 + rr.uniform(-jitter, jitter) * 0.5)))
        top = len(verts) - 1
        for j in range(seg):
            faces.append((0, 1 + (j + 1) % seg, 1 + j))
        for i in range(rings - 2):
            a, b = 1 + i * seg, 1 + (i + 1) * seg
            for j in range(seg):
                jj = (j + 1) % seg
                faces.append((a + j, a + jj, b + jj, b + j))
        last = 1 + (rings - 2) * seg
        for j in range(seg):
            faces.append((last + j, last + (j + 1) % seg, top))
        sx, sy, sz = scale
        verts = [(x * sx, y * sy, z * sz) for x, y, z in verts]
        return self.add(verts, faces, loc, rot)

    def cushion(self, x0, x1, y0, y1, z0, z1, nx_=4, ny=4, puff=0.02, seed=0, edge=0.0):
        """顶面起伏的软垫（被子、床垫、坐垫）：顶面是 nx_×ny 的网格，内部的点随机抬高 0..puff；
        edge>0 时顶面四边往里收 edge、往下压，像鼓起来的垫子"""
        rr = random.Random(seed)
        W = nx_ + 1
        verts, grid = [], []
        for j in range(ny + 1):
            for i in range(W):
                x = x0 + (x1 - x0) * i / nx_
                y = y0 + (y1 - y0) * j / ny
                grid.append((x, y))
                inner = 0 < i < nx_ and 0 < j < ny
                if inner:
                    verts.append((x, y, z1 + rr.uniform(0.3, 1.0) * puff))
                else:
                    verts.append((min(max(x, x0 + edge), x1 - edge), min(max(y, y0 + edge), y1 - edge), z1 - edge * 0.6))
        faces = []
        for j in range(ny):
            for i in range(nx_):
                a = j * W + i
                faces.append((a, a + 1, a + W + 1, a + W))
        # 顶面的一圈边（逆时针），每个点往下接一个底面的点；四周是一圈竖面，底面一整块
        ring = [i for i in range(W)] + [j * W + nx_ for j in range(1, ny + 1)] + \
               [ny * W + i for i in range(nx_ - 1, -1, -1)] + [j * W for j in range(ny - 1, 0, -1)]
        bottom = []
        for p in ring:
            bottom.append(len(verts))
            verts.append((grid[p][0], grid[p][1], z0))
        n = len(ring)
        for k in range(n):
            p, q = ring[k], ring[(k + 1) % n]
            faces.append((p, bottom[k], bottom[(k + 1) % n], q))
        faces.append(tuple(reversed(bottom)))
        return self.add(verts, faces)

    def quad(self, pts):
        """单独一片（四个点，按逆时针看过去是正面）"""
        o = len(self.v)
        self.v += [tuple(p) for p in pts]
        self.f.append(tuple(range(o, o + len(pts))))
        return self

    def build(self, name, parent=None, recalc=True, **clean):
        if not self.f:
            return None
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        if recalc:
            bm = bmesh.new()
            bm.from_mesh(me)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            bm.to_mesh(me)
            bm.free()
        me.validate()
        obj = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(obj)
        nx._place(obj, (0, 0, 0), (0, 0, 0), parent)
        return nx.clean(obj, **clean)


class Thing:
    """一件东西：空物体做父级（位置 loc、绕 Z 转 yaw；rot 给了就用三轴），下面按颜色分几团 Geo"""

    def __init__(self, name, loc=(0, 0, 0), yaw=0.0, parent=None, rot=None):
        self.name = name
        self.g = nx.group(name, loc, rot if rot is not None else (0, 0, yaw))
        self.g["nx_piece"] = 1
        if parent is not None:
            self.g.parent = parent
        self.parts = {}

    def __getitem__(self, key):
        return self.parts.setdefault(key, Geo())

    def done(self, specs, collide=True, shadow=True, **common):
        """specs：{团名: '#rrggbb' 或 dict(color=…, emit=…, collide=…, shadow=…, recv=…, double=…, window=…, fog=…)}"""
        for key, geo in self.parts.items():
            s = specs[key]
            s = dict(color=s) if isinstance(s, str) else dict(s)
            opts = dict(collide=collide, shadow=shadow)
            opts.update(common)
            opts.update(s)
            recalc = not opts.pop("one_sided", False)
            geo.build(f"{self.name}_{key}", parent=self.g, recalc=recalc, **opts)
        return self.g
