"""浅梦 · 花房 · 变体二（glasshouse-var-2）：会开的花（修好）。

底本是第三轮的 blender/scenes/glasshouse.py。这一版保留「走近张开」，把第三轮的病根修掉：

- **穿模的根因与修法**（第三轮量过的数字见 mockup/shallows-04/README.md）：
  ① `blade` 的瓣根部半径只有 0.06·size，相邻瓣 72° 的弦长 0.07·size 小于两瓣半宽之和 → 原样就互穿；
  ② pose 的 `rot=(0,−38,0)` 与瓣本身的 `−lean` 同向，把瓣推过竖轴倒向另一侧，五片瓣的中轴全过花心（10/10 对全穿）。
  这一版：瓣本地重写成「两头尖的板」的简版（4 点轮廓 / 12 个三角），根部半径 0.22·size、半宽 0.13·size；
  pose 的 `rot` 符号改成**向外**（`(0, +open, 0)`），铰链就在瓣的根部——张开后瓣尖朝外上方，不越过花心。
- **花心露出亮色**：花心（金、自己发亮）在原样时缩到 0.31 倍藏在瓣里，张开时放大到 1 倍，
  「开」这一下就有了一个明确的落点。
- **挪开**：a_bud1 / a_bud2 拉开到 4.7m（触发半径 2.2m，站中间不会两株一起开）、b_tall1 离柱子与墙并缩到 3.1m、
  b_tall2 挪开回廊柱子。
- **玻璃重做**、**顶上那片只投影的顶收窄开洞**、**花床分层 / 落瓣**：同变体一（一格一块的玻璃、ghost (0.45,1.0,6.0)）。
- `a_drift` 的常转改慢到 2.5°/s 并关掉投影——影子图不再每帧重画。

保留：三间房与两条廊、下沉的池、玻璃外那 11 朵巨花与那株只有影子的 13m 花、四个出入口与到达点、头顶那片只投影的顶。

运行：node scripts/blender.cjs build glasshouse-var-2，网页 ?world=glasshouse-var-2
"""
import math
import os
import random
import sys

from mathutils import Vector

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import furniture as fu  # noqa: E402
import nx  # noqa: E402
import prefabs as pf  # noqa: E402
import shapes as sh  # noqa: E402

EXTENT = 90
CENTER = (0, 0)

GROUND_Z = -1.2       # 石台外面的地
ELEV = 50.0           # 太阳仰角
SUN_H = (0.55, -0.835)  # 太阳在东南偏南（水平方向，指向太阳）
CANOPY_Z = 28.0
CANOPY_EXT = 52

KICK_H = 0.45
FRAME = dict(a="white", b="mist", pattern="plain")
KICK = dict(ramp=("lilac", "lilac_pale", "mist"), pattern="plain")
FLOOR = dict(a="mist", b="pink_pale", pattern="tiles")
PODIUM = dict(ramp=("violet", "lilac_dark", "lilac"), pattern="bands")
# 玻璃：一格一块，远处 45% 的像素、1m 内散掉；色板压在蓝白一列（暗蓝 / 淡蓝 / 白）
GLASS = dict(ramp=("blue", "blue_pale", "white"), pattern="plain",
             collide=False, shadow=False, ghost=(0.45, 1.0, 6.0))
BED = dict(ramp=("lilac_dark", "lilac", "lilac_pale"), pattern="grain")
RAIL = dict(a="white", b="mist", pattern="plain")
HAND = dict(a="gold", b="pink_pale", pattern="plain")      # 回廊扶手：一点金
STEM = dict(a="green", b="lilac_pale", pattern="plain")    # 茎：一点绿
BASE = dict(a="lilac_pale", b="green", pattern="plain")
CORE = dict(a="gold", b="white", pattern="plain", emit=0.9)
# 外面的花：连茎、叶座一起暗下去（浅色在影子里压不住，直接用深一档的色）；花心也不亮
DARK_STEM = dict(a="lilac_dark", b="violet", pattern="plain")
DARK_BASE = dict(a="violet", b="lilac_dark", pattern="plain")

OPEN_R = 2.2          # 走近张开的触发半径（米）
OPEN_T = 2.2          # 张开用几秒


def sun_vec():
    e = math.radians(ELEV)
    h = Vector((SUN_H[0], SUN_H[1], 0)).normalized()
    return Vector((h.x * math.cos(e), h.y * math.cos(e), math.sin(e)))


SUN = sun_vec()


# ── 几何小件 ─────────────────────────────────────────

def beam(k, a, b, w, h):
    """a → b 的一根方梁，截面 w（横）× h（竖）"""
    a, b = Vector(a), Vector(b)
    d = (b - a)
    if d.length < 1e-4:
        return
    dn = d.normalized()
    up = Vector((0, 0, 1)) if abs(dn.z) < 0.95 else Vector((1, 0, 0))
    side = dn.cross(up).normalized() * (w / 2)
    up2 = side.normalized().cross(dn).normalized() * (h / 2)
    vs = []
    for p in (a, b):
        for s in (-1, 1):
            for u in (-1, 1):
                vs.append(tuple(p + side * s + up2 * u))
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    k._add(vs, faces)


def prism(k, pts, z0, z1):
    """凸多边形的柱（pts 逆时针）"""
    n = len(pts)
    vs = [(x, y, z0) for x, y in pts] + [(x, y, z1) for x, y in pts]
    faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    k._add(vs, faces)


def slab(k, poly, t=0.03):
    """三维的平面多边形，加一点厚（两面都看得见）"""
    P = [Vector(p) for p in poly]
    nrm = (P[1] - P[0]).cross(P[2] - P[0]).normalized() * (t / 2)
    n = len(P)
    vs = [tuple(p - nrm) for p in P] + [tuple(p + nrm) for p in P]
    faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    k._add(vs, faces)


def face_normal(pts):
    """一撮共面点的法线（取朝上的一侧）"""
    P = [Vector(p) for p in pts]
    n = (P[1] - P[0]).cross(P[2] - P[0])
    if n.length < 1e-9:
        return Vector((0, 0, 0))
    n.normalize()
    return n if n.z >= 0 else -n


def lerp(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(len(a)))


def inside(p, pts, buf=0.0):
    """点在凸多边形（逆时针）里，或离边不超过 buf"""
    n = len(pts)
    for i in range(n):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % n]
        ex, ey = bx - ax, by - ay
        L = math.hypot(ex, ey)
        cross = (ex * (p[1] - ay) - ey * (p[0] - ax)) / L
        if cross < -buf:
            return False
    return True


# ── 玻璃房 ───────────────────────────────────────────

class Room:
    """一间玻璃房：pts 逆时针的凸多边形，floor 地面高，eave 檐高（相对地面）。
    roof=("gable", f, hs, hn)：pts 是四边形，pts[0]→pts[1] 是南头、pts[2]→pts[3] 是北头，屋脊从南头 f 处到北头 f 处，两头高 hs、hn；
    roof=("apex", h)：攒尖，顶在中心。
    doors：{边号: [(离边起点的米数（门中心）, 宽, 高)]}；open：整条边敞开（廊的两头）"""

    def __init__(self, name, pts, floor, eave, roof, doors=None, open_edges=(), posts=True):
        self.name, self.pts, self.floor, self.eave, self.roof = name, pts, floor, eave, roof
        self.doors = doors or {}
        self.open = set(open_edges)
        self.posts = posts

    def edge(self, i):
        return self.pts[i], self.pts[(i + 1) % len(self.pts)]

    def roof_h(self, i, s):
        """边 i 上参数 s（0..1）处，墙顶（檐或山墙）的高（相对地面）"""
        if self.roof[0] == "gable" and i in (0, 2):
            _, f, hs, hn = self.roof
            top = hs if i == 0 else hn
            ff = f if i == 0 else 1 - f
            if s <= ff:
                return self.eave + (top - self.eave) * s / ff
            return self.eave + (top - self.eave) * (1 - s) / (1 - ff)
        return self.eave

    def ridge(self):
        _, f, hs, hn = self.roof
        p0, p1, p2, p3 = self.pts
        z = self.floor
        return (*lerp(p0, p1, f), z + hs), (*lerp(p3, p2, f), z + hn)

    def build(self, kits):
        fr, kick, glass, col = kits["frame"], kits["kick"], kits["glass"], kits["collider"]
        z0 = self.floor
        n = len(self.pts)
        for i in range(n):
            a, b = self.edge(i)
            L = math.dist(a, b)
            if self.posts and not ({i, (i - 1) % n} & self.open):
                beam(fr, (*a, z0 + KICK_H - 0.01), (*a, z0 + self.roof_h(i, 0) + 0.06), 0.25, 0.25)
            if i in self.open:
                continue
            gaps = sorted((c - w / 2, c + w / 2, h) for c, w, h in self.doors.get(i, []))
            segs, cur = [], 0.0
            for g0, g1, _ in gaps:
                segs.append((cur, g0))
                cur = g1
            segs.append((cur, L))
            ins = 0.12 if not self.posts else 0.0
            for s0, s1 in segs:
                s0, s1 = max(s0, ins), min(s1, L - ins)
                if s1 - s0 < 0.05:
                    continue
                p0, p1 = lerp(a, b, s0 / L), lerp(a, b, s1 / L)
                # 矮墙（实心）与只挡人的玻璃
                self._wall_box(kick, p0, p1, z0 + 0.005, z0 + KICK_H, 0.22)
                hmax = max(self.roof_h(i, s0 / L), self.roof_h(i, s1 / L))
                self._wall_box(col, p0, p1, z0, z0 + max(hmax, 3.0), 0.14)
                # 窗棂：等分，每格不宽于 1.45m
                m = max(1, math.ceil((s1 - s0) / 1.45))
                for j in range(1, m):
                    s = s0 + (s1 - s0) * j / m
                    p = lerp(a, b, s / L)
                    beam(fr, (*p, z0 + KICK_H - 0.01), (*p, z0 + self.roof_h(i, s / L) + 0.02), 0.12, 0.1)
                # 门洞边上的门框
                for s in (s0, s1):
                    if 0.2 < s < L - 0.2:
                        p = lerp(a, b, s / L)
                        beam(fr, (*p, z0 - 0.02), (*p, z0 + self.roof_h(i, s / L) + 0.02), 0.18, 0.16)
                # 玻璃面（虚像）：矮墙顶到墙顶，**一格一块**，每格沿墙法线错开 ±0.8cm
                for j in range(m):
                    u0 = s0 + (s1 - s0) * j / m + (0.0 if j == 0 else 0.05)      # 让开窗棂（0.1 宽）
                    u1 = s0 + (s1 - s0) * (j + 1) / m - (0.0 if j == m - 1 else 0.05)
                    if u1 - u0 < 0.05:
                        continue
                    self._wall_pane(glass, a, b, u0, u1, i, L, 1 if j % 2 == 0 else -1)
            # 门：门楣、门楣以上的玻璃（也分格）
            for g0, g1, h in gaps:
                p0, p1 = lerp(a, b, g0 / L), lerp(a, b, g1 / L)
                beam(fr, (*p0, z0 + h + 0.09), (*p1, z0 + h + 0.09), 0.2, 0.18)
                top0, top1 = self.roof_h(i, g0 / L), self.roof_h(i, g1 / L)
                if min(top0, top1) > h + 0.3:
                    mm = max(1, math.ceil((g1 - g0) / 1.45))
                    for j in range(mm):
                        u0 = g0 + (g1 - g0) * j / mm + (0.0 if j == 0 else 0.06)
                        u1 = g0 + (g1 - g0) * (j + 1) / mm - (0.0 if j == mm - 1 else 0.06)
                        if u1 - u0 < 0.05:
                            continue
                        self._door_pane(glass, a, b, u0, u1, i, L, h, 1 if j % 2 == 0 else -1)
                    self._wall_box(col, p0, p1, z0 + h + 0.18, z0 + max(top0, top1, 3.0), 0.14)
            # 檐梁
            if not (self.roof[0] == "gable" and i in (0, 2)):
                beam(fr, (*a, z0 + self.eave + 0.06), (*b, z0 + self.eave + 0.06), 0.2, 0.2)
        self._roof(fr, glass)

    # 一格玻璃：整块沿法线挪开 off·sign，与邻格错开，免得共面
    @staticmethod
    def _shift(poly, off, sign):
        o = face_normal(poly) * (off * sign)
        return [tuple(Vector(p) + o) for p in poly]

    def _wall_pane(self, k, a, b, u0, u1, i, L, sign, off=0.008):
        q0, q1 = lerp(a, b, u0 / L), lerp(a, b, u1 / L)
        z0 = self.floor
        h0, h1 = self.roof_h(i, u0 / L), self.roof_h(i, u1 / L)
        poly = [(*q0, z0 + KICK_H), (*q1, z0 + KICK_H), (*q1, z0 + h1), (*q0, z0 + h0)]
        if self.roof[0] == "gable" and i in (0, 2):
            ff = self.roof[1] if i == 0 else 1 - self.roof[1]
            if u0 / L < ff < u1 / L:
                pk = lerp(a, b, ff)
                poly.insert(3, (*pk, z0 + self.roof_h(i, ff)))
        slab(k, self._shift(poly, off, sign), 0.02)

    def _door_pane(self, k, a, b, u0, u1, i, L, h, sign, off=0.008):
        q0, q1 = lerp(a, b, u0 / L), lerp(a, b, u1 / L)
        z0 = self.floor
        poly = [(*q0, z0 + h + 0.18), (*q1, z0 + h + 0.18),
                (*q1, z0 + self.roof_h(i, u1 / L)), (*q0, z0 + self.roof_h(i, u0 / L))]
        slab(k, self._shift(poly, off, sign), 0.02)

    @staticmethod
    def _wall_box(k, p0, p1, z0, z1, t):
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        L = math.hypot(dx, dy)
        nxv, nyv = -dy / L * t / 2, dx / L * t / 2
        pts = [(p0[0] - nxv, p0[1] - nyv), (p1[0] - nxv, p1[1] - nyv), (p1[0] + nxv, p1[1] + nyv), (p0[0] + nxv, p0[1] + nyv)]
        prism(k, pts, z0, z1)

    def _roof(self, fr, glass):
        z0, e = self.floor, self.floor + self.eave
        if self.roof[0] == "gable":
            p0, p1, p2, p3 = self.pts
            r0, r1 = self.ridge()
            beam(fr, r0, r1, 0.24, 0.24)
            for a, r in ((p0, r0), (p1, r0), (p3, r1), (p2, r1)):   # 山墙的斜边
                beam(fr, (*a, e + 0.06), r, 0.18, 0.18)
            for (a, b, ra, rb) in ((p1, p2, r0, r1), (p0, p3, r0, r1)):   # 两面坡
                L = math.dist(a, b)
                m = max(2, math.ceil(L / 1.45))
                for j in range(1, m):
                    t = j / m
                    beam(fr, (*lerp(a, b, t), e + 0.06), lerp(ra, rb, t), 0.12, 0.12)
                # 玻璃：一格一块（椽条之间），每格错开
                for j in range(m):
                    t0 = j / m + (0.0 if j == 0 else 0.05 / L)
                    t1 = (j + 1) / m - (0.0 if j == m - 1 else 0.05 / L)
                    if (t1 - t0) * L < 0.05:
                        continue
                    ea, eb = lerp(a, b, t0), lerp(a, b, t1)
                    sa, sb = lerp(ra, rb, t0), lerp(ra, rb, t1)
                    poly = [(*ea, e + 0.12), (*eb, e + 0.12), (sb[0], sb[1], sb[2] + 0.05), (sa[0], sa[1], sa[2] + 0.05)]
                    slab(glass, self._shift(poly, 0.008, 1 if j % 2 == 0 else -1), 0.02)
        else:
            h = self.roof[1]
            cx = sum(p[0] for p in self.pts) / len(self.pts)
            cy = sum(p[1] for p in self.pts) / len(self.pts)
            top = (cx, cy, z0 + h)
            n = len(self.pts)
            for i in range(n):
                a, b = self.edge(i)
                beam(fr, (*a, e + 0.06), top, 0.18, 0.18)
                beam(fr, (*lerp(a, b, 0.5), e + 0.06), top, 0.12, 0.12)
                L = math.dist(a, b)
                for j, (t0, t1) in enumerate(((0.0, 0.5), (0.5, 1.0))):
                    u0 = t0 + (0.0 if t0 == 0 else 0.05 / L)
                    u1 = t1 - (0.0 if t1 == 1 else 0.05 / L)
                    q0, q1 = lerp(a, b, u0), lerp(a, b, u1)
                    poly = [(*q0, e + 0.12), (*q1, e + 0.12), (top[0], top[1], top[2] + 0.04)]
                    slab(glass, self._shift(poly, 0.008, 1 if j == 0 else -1), 0.02)
            nx.cylinder(f"{self.name}_finial", 0.28, 0.05, 0.9, (top[0], top[1], top[2] - 0.1), segments=8, collide=False, **FRAME)


# ── 花（本地重写：少瓣、有茎、瓣与瓣不相交；能走近张开） ──
# 一片瓣＝「两头尖的板」的简版：4 个轮廓点（根部一点、最宽处在 0.30L、尖端一点），12 个三角。
# 根部半径 0.22·size、半宽 0.13·size；五片瓣 72° 的角距下，最宽处离轴的角宽只有 26°，
# 留 10° 以上的缝。张开的转轴是瓣自己的本地 Y（绕根部），**正角度＝向外**，瓣尖朝外上方，不越过花心。

PETALS = [dict(a="white", b="pink_pale"), dict(a="pink_pale", b="pink"), dict(a="mist", b="blue_pale"),
          dict(a="pink_pale", b="white")]
OUT_PETALS = [dict(a="lilac", b="lilac_dark"), dict(a="rose", b="lilac"), dict(a="lilac_dark", b="violet")]

# kind -> [(瓣数, 根部半径/size, 离竖直的倾角, 瓣长/size, 瓣宽/size, 起点高/size)]
LAYERS = {
    "bud": [(5, 0.22, 8.0, 1.00, 0.30, 0.10)],                                    # 没开的：五片近乎竖直
    "cup": [(4, 0.30, 52.0, 1.00, 0.44, 0.14)],                                   # 开的：四片张开（少瓣、轮廓清楚）
    "lotus": [(4, 0.24, 16.0, 0.66, 0.36, 0.34),                                  # 三层：内直、中张、外平
              (5, 0.32, 42.0, 0.80, 0.42, 0.24),
              (6, 0.40, 62.0, 0.86, 0.48, 0.16)],
}


def reach(kind, size, opened=0.0):
    """一株花最远伸到离花心多远（米）——摆位置时用它算间距；opened 是张开的度数"""
    return max(rr + k * math.sin(math.radians(t + opened)) for _, rr, t, k, _, _ in LAYERS[kind]) * size


def petal_mesh(name, L, W, T, waist=0.42, loc=(0, 0, 0), rot=(0, 0, 0), parent=None, **style):
    """一片瓣：根部在 loc，沿本地 +X 伸出，宽在本地 Y，厚在本地 Z（12 个三角）"""
    W2 = W / 2
    outline = [(0.0, 0.0), (L * waist, W2), (L, 0.0), (L * waist, -W2)]
    n = 4
    verts = [(x, y, -T / 2) for x, y in outline] + [(x, y, T / 2) for x, y in outline]
    faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    return sh._mesh_obj(name, verts, faces, loc, rot, parent, **style)


def bloom(name, loc, size, seed, kind="bud", stem=0.0, styles=None, collide=False, yaw=None,
          open_deg=None, dark=False):
    """一株花：底下一圈小叶座 + 茎（可选）+ 花心 + 几片瓣。返回 (组, 瓣的列表)。
    loc 是花根（土面）；茎从 loc 长起，花头坐在茎顶。kind 见 LAYERS。
    open_deg：给了就是「走近张开」——每片瓣绕自己的根部向外转 open_deg 度，花心同时放大（原样时缩到 0.31 倍）。
    dark=True：整株用深一档的色、花心不亮（外面那些在影子里的）"""
    r = random.Random(seed)
    styles = styles or (OUT_PETALS if dark else PETALS)
    g = nx.group(name, loc, (0, 0, r.uniform(0, 360) if yaw is None else yaw))
    petals = []
    t = max(0.12, 0.045 * size)                       # 瓣厚（不细于 0.1m）
    nx.cylinder(f"{name}_base", 0.17 * size, 0.14 * size, 0.06 * size, (0, 0, 0), segments=6,
                parent=g, collide=collide, **(DARK_BASE if dark else BASE))
    if stem > 0:
        nx.cylinder(f"{name}_stem", 0.05 * size + 0.035, 0.04 * size + 0.03, stem + 0.05 * size,
                    (0, 0, 0), segments=6, parent=g, collide=collide, **(DARK_STEM if dark else STEM))
    head = nx.group(f"{name}_head", (0, 0, stem), (0, 0, 0))
    head.parent = g
    top = 0.0
    for li, (n, rr, tilt, k, w, z0) in enumerate(LAYERS[kind]):
        top = max(top, z0)
        off = r.uniform(0, 360) + (60.0 / n if li % 2 else 0.0)
        for i in range(n):
            az = off + 360.0 / n * i + r.uniform(-4, 4)
            a = math.radians(az)
            L = size * k * r.uniform(0.94, 1.06)
            p = petal_mesh(f"{name}_p{li}{i}", L, size * w, t, waist=0.42,
                           loc=(math.cos(a) * rr * size, math.sin(a) * rr * size, z0 * size),
                           rot=(0, -(90 - tilt), az), parent=head, **styles[i % len(styles)])
            petals.append(p)
            if open_deg is not None:
                # 铰链在瓣的根部；正角度＝向外（第三轮写成 −38 是反的，瓣会越过竖轴倒向另一侧）
                nx.pose(p, f"{name}_open", on="near", at=(loc[0], loc[1], loc[2]),
                        radius=OPEN_R, rot=(0, open_deg, 0), time=OPEN_T)
    # 花心：一点金（自己发亮）。会张开的花心原样时缩到 0.31 倍藏在瓣里，张开时放大到 1 倍
    if not dark:
        k0 = 0.31 if open_deg is not None else 1.0
        core = nx.cylinder(f"{name}_core", max(0.05, 0.06 * size * k0), max(0.04, 0.05 * size * k0), (0.24 * size + 0.06) * k0,
                           (0, 0, (top + 0.06) * size), segments=6, parent=head, collide=False, **CORE)
        if open_deg is not None:
            nx.pose(core, f"{name}_open", on="near", at=(loc[0], loc[1], loc[2]),
                    radius=OPEN_R, scale=(1.0 / k0, 1.0 / k0, 1.0 / k0), time=OPEN_T)
    return g, petals


def drift(name, loc, size, seed, n=5, spin=2.5):
    """浮着的落瓣：慢慢转的几片（关掉投影——不进影子图，影子图就不必每帧重画）"""
    r = random.Random(seed)
    g = nx.group(name, loc, (0, 0, 0))
    for i in range(n):
        a = r.uniform(0, math.tau)
        d = r.uniform(0.5, 1.4) * size
        L = size * r.uniform(0.32, 0.55)
        p = petal_mesh(f"{name}_d{i}", L, L * 0.42, 0.1, waist=0.42,
                       loc=(math.cos(a) * d, math.sin(a) * d, r.uniform(0.7, 2.2) * size),
                       rot=(r.uniform(-40, 40), r.uniform(-40, 40), r.uniform(0, 360)), parent=g,
                       collide=False, pattern="plain", **PETALS[i % len(PETALS)])
        p["nx_shadow"] = 0
        nx.behave(p, spin=spin, bob=r.uniform(0.08, 0.2))
    return g


# ── 落瓣：铺在地上当记号 ─────────────────────────────

def _d2seg(p, a, b):
    ex, ey = b[0] - a[0], b[1] - a[1]
    L2 = ex * ex + ey * ey
    t = 0.0 if L2 < 1e-9 else max(0.0, min(1.0, ((p[0] - a[0]) * ex + (p[1] - a[1]) * ey) / L2))
    return math.hypot(p[0] - (a[0] + ex * t), p[1] - (a[1] + ey * t))


def blk_poly(pts):
    return lambda p: min(_d2seg(p, pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts)))


def blk_rect(c, w, d, yaw=0.0):
    def f(p):
        ca, sa = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        dx, dy = p[0] - c[0], p[1] - c[1]
        x, y = dx * ca + dy * sa, -dx * sa + dy * ca
        return math.hypot(max(abs(x) - w / 2, 0.0), max(abs(y) - d / 2, 0.0))
    return f


def blk_circ(c, r):
    return lambda p: math.hypot(p[0] - c[0], p[1] - c[1]) - r


def fallen(name, pts, seed, z, blockers=(), lmax=0.85, lmin=0.35):
    """落下的瓣：平躺在地上的尖头板，一片片的（逐片抬高 0.012m 防共面）"""
    r = random.Random(seed)
    pts = list(pts)
    for i, (x, y) in enumerate(pts):
        room = min([b((x, y)) for b in blockers], default=lmax + 0.12)
        near = min([math.dist((x, y), q) for j, q in enumerate(pts) if j != i], default=9.9)
        L = max(lmin, min(lmax, room - 0.12, (near - 0.10) * 0.5))
        petal_mesh(f"{name}{i}", L, L * 0.42, 0.1, waist=0.42,
                   loc=(x, y, z + 0.06 + 0.012 * i), rot=(0, 0, r.uniform(0, 360)),
                   collide=False, pattern="plain", **PETALS[i % len(PETALS)])


# ── 平面 ─────────────────────────────────────────────

def rot_pts(local, origin, yaw):
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    return [(origin[0] + x * c - y * s, origin[1] + x * s + y * c) for x, y in local]


def to_world(p, origin, yaw):
    return rot_pts([p], origin, yaw)[0]


A = [(-6.5, -4.25), (6.5, -4.25), (6.5, 4.25), (-6.5, 4.25)]
A_G = [(-6.5, 4.25), (-6.5, -4.25), (6.5, -4.25), (6.5, 4.25)]
A_DOOR_E = (1.8, 2.4)    # 东墙上门的 y 中心、宽
A_DOOR_W = (-2.6, 2.4)   # 西墙上门的 y 中心、宽

B_O, B_YAW = (9.6, -2.2), 12.0
B_LOCAL = [(0, 0), (6.5, 0), (7.7, 11), (1.2, 11)]
B = rot_pts(B_LOCAL, B_O, B_YAW)

C_C, C_R = (-13.2, -2.6), 4.7
C = [(C_C[0] + C_R * math.cos(math.radians(-30 + 60 * k)), C_C[1] + C_R * math.sin(math.radians(-30 + 60 * k))) for k in range(6)]
C_FLOOR = -0.9


def door_on(pts, i, c, w):
    a, b = pts[i], pts[(i + 1) % len(pts)]
    L = math.dist(a, b)
    return ((c[0] - a[0]) * (b[0] - a[0]) + (c[1] - a[1]) * (b[1] - a[1])) / L


def plan():
    rooms = []
    a_e0 = A_DOOR_E[0] + 4.25
    a_w0 = 4.25 - A_DOOR_W[0]
    rooms.append(Room("A", A_G, 0.0, 3.4, ("gable", 0.36, 6.4, 6.4),
                      doors={2: [(a_e0, A_DOOR_E[1], 2.5)], 0: [(a_w0, A_DOOR_W[1], 2.5)]}))
    bw_a, bw_b = B[3], B[0]
    t_mid = 0.78
    b_door_c = lerp(bw_a, bw_b, t_mid)
    b_door_s = math.dist(bw_a, bw_b) * t_mid
    bn_L = math.dist(B[2], B[3])
    rooms.append(Room("B", B, 0.0, 5.4, ("gable", 0.62, 6.8, 10.0),
                      doors={3: [(b_door_s, 2.4, 2.5)], 2: [(bn_L - 2.6, 1.6, 2.6)]}))
    c_e = door_on(C, 0, (C[0][0], A_DOOR_W[0]), 0)
    rooms.append(Room("C", C, C_FLOOR, 3.9, ("apex", 6.6), doors={0: [(c_e, 2.4, 3.4)]}))

    half = A_DOOR_E[1] / 2
    a0, a1 = (6.5, A_DOOR_E[0] - half), (6.5, A_DOOR_E[0] + half)
    d = Vector((bw_b[0] - bw_a[0], bw_b[1] - bw_a[1])).normalized()
    b0 = (b_door_c[0] + d.x * 1.2, b_door_c[1] + d.y * 1.2)
    b1 = (b_door_c[0] - d.x * 1.2, b_door_c[1] - d.y * 1.2)
    rooms.append(Room("AB", [a1, a0, b0, b1], 0.0, 2.95, ("gable", 0.5, 3.35, 3.35), open_edges=(0, 2), posts=False))
    cx_e = C[0][0]
    w0, w1 = (-6.5, A_DOOR_W[0] + half), (-6.5, A_DOOR_W[0] - half)
    c0, c1 = (cx_e, A_DOOR_W[0] - half), (cx_e, A_DOOR_W[0] + half)
    rooms.append(Room("AC", [w1, w0, c1, c0], 0.0, 2.95, ("gable", 0.5, 3.35, 3.35),
                      open_edges=(0, 2), posts=False))
    return rooms, b_door_c


# ── 光：看不见的顶，只在房间正上方开洞 ───────────────

def canopy(rooms):
    """CANOPY_Z 高的一整片看不见的顶（只投影），按 0.5m 的格：格心顺着太阳落到**房间地面**若在某间房里，就开洞。
    第三轮多测了一层 f+1.6，把洞往背光一侧多扩了约 2.1m，石台外露出一圈晒得到太阳的地；这里只按地面算。"""
    step = 0.5
    k = fu.Kit()
    lit = [(r.pts, r.floor) for r in rooms]
    ext = CANOPY_EXT
    nrow = int(2 * ext / step)

    def hole(x, y):
        for pts, f in lit:
            kk = (CANOPY_Z - f) / SUN.z
            if inside((x - SUN.x * kk, y - SUN.y * kk), pts, 0.0):
                return True
        return False

    for j in range(nrow):
        y = -ext + step * (j + 0.5)
        run = None
        for i in range(nrow + 1):
            x = -ext + step * (i + 0.5)
            solid = i < nrow and not hole(x, y)
            if solid and run is None:
                run = i
            elif not solid and run is not None:
                x0, x1 = -ext + step * run, -ext + step * i
                k.box((x1 - x0, step, 0.4), ((x0 + x1) / 2, y, CANOPY_Z))
                run = None
    nx.shade(k.build("canopy", smooth=0, collide=False))


# ── 大间 A ───────────────────────────────────────────

def room_a():
    """大间：北边一条长花床、中间偏西一张岛床、东北与南边各一张矮床；
    北床与岛床上各一株走近会张开的（拉开 4.7m）；东南一株开得特别大的（静态）；东南角花瓶（回家）。"""
    nx.into("a")
    pf.plinth("a_bed_n", (-2.6, 3.0, 0), 7.0, 1.7, h=0.4, **BED)
    pf.plinth("a_bed_i", (-2.9, -1.0, 0), 4.0, 2.6, h=0.4, yaw=-9, **BED)
    pf.plinth("a_bed_ne", (4.4, 3.3, 0), 3.6, 1.2, h=0.4, **BED)
    pf.plinth("a_bed_s", (0.4, -3.5, 0), 3.6, 1.4, h=0.4, **BED)
    pf.plinth("a_mound", (4.4, -0.4, 0), 1.5, 1.5, h=0.5, a="mist", b="lilac_pale", pattern="tiles")
    # 北床：开的 / **走近会张开的** / 三层莲，高低错开
    bloom("a_rose1", (-5.2, 3.0, 0.4), 0.95, 3, kind="cup", stem=0.5)
    bloom("a_bud1", (-3.0, 2.7, 0.4), 1.6, 5, kind="bud", stem=0.6, open_deg=24)
    bloom("a_lotus1", (0.1, 2.75, 0.4), 1.2, 7, kind="lotus", stem=0.3)
    # 岛床：一朵三层莲 + 一株走近会张开的
    bloom("a_lotus2", (-3.7, -0.9, 0.4), 1.3, 11, kind="lotus", stem=0.3)
    bloom("a_bud2", (-1.1, -1.6, 0.4), 1.2, 8, kind="bud", stem=0.4, open_deg=30)
    # 东北床：一朵开着的
    bloom("a_rose_ne", (5.2, 3.0, 0.4), 0.95, 21, kind="cup", stem=0.5)
    # 南床：一朵没开的（不张开——留几朵不开的做对照）+ 一朵开着的
    bloom("a_bud3", (-0.6, -3.5, 0.4), 1.5, 27, kind="bud", stem=0.5)
    bloom("a_rose2", (1.4, -3.0, 0.4), 0.9, 29, kind="cup", stem=0.4)
    # 看点：开得特别大的静态花——2.2m 的茎，四片瓣张开，顶到 3.8m
    bloom("a_big", (4.4, -0.4, 0.5), 1.6, 41, kind="cup", stem=2.2)
    # 岛床上方浮着的落瓣（慢慢转，不投影）
    drift("a_drift", (-3.9, -0.7, 3.0), 1.0, 4, n=5)
    # 落瓣：空地上铺开当记号（自动避开墙、花床、别的花）
    blk = [blk_poly(A),
           blk_rect((-2.6, 3.0), 7.0, 1.7), blk_rect((-2.9, -1.0), 4.0, 2.6, -9),
           blk_rect((4.4, 3.3), 3.6, 1.2), blk_rect((0.4, -3.5), 3.6, 1.4),
           blk_rect((4.4, -0.4), 1.5, 1.5), blk_rect((3.6, -3.1), 0.9, 0.9, 20),
           blk_circ((-5.2, 3.0), reach("cup", 0.95)), blk_circ((-3.0, 2.7), reach("bud", 1.6, 24)),
           blk_circ((0.1, 2.75), reach("lotus", 1.2)), blk_circ((-3.7, -0.9), reach("lotus", 1.3)),
           blk_circ((-1.1, -1.6), reach("bud", 1.2, 30)), blk_circ((5.2, 3.0), reach("cup", 0.95)),
           blk_circ((-0.6, -3.5), reach("bud", 1.5)), blk_circ((1.4, -3.0), reach("cup", 0.9)),
           blk_circ((4.4, -0.4), reach("cup", 1.6))]
    fallen("a_fall", [(0.9, -1.7), (2.7, -2.3), (5.7, -1.7), (6.1, 1.5), (2.1, 1.5),
                      (0.0, 1.6), (3.9, 1.0), (1.3, 0.2), (-1.9, -3.6), (5.0, -3.3)], 2, 0.0, blk)
    # 回家：方台上插花的瓶
    loc, yaw = (3.6, -3.1, 0.0), 20
    pf.plinth("vase_home_plinth", loc, 0.9, 0.9, h=0.5, yaw=yaw, a="white", b="mist", pattern="plain")
    fu.vase("vase_home", (loc[0], loc[1], 0.5), 0.8, "round", flowers=9, seed=4, style=dict(a="pink_pale", b="white", pattern="plain"))
    nx.portal("portal_vase_home", (loc[0], loc[1], 1.4), "house", at="glasshouse", mode="key", title="凑近", radius=0.9)
    p = pf._ahead(loc, yaw, 2.1)
    nx.arrive("house", p, facing_deg=yaw + 25)
    nx.spawn(p, facing_deg=yaw + 25)


# ── 高间 B ───────────────────────────────────────────

def room_b(b_door_c):
    """高间：东墙一道楼梯上到回廊（加了栏板与金扶手）；当中两株走近会张开的高花（离柱子与墙远）；
    西边一张矮台上一朵莲；北墙一扇玻璃门 → 光斑"""
    nx.into("b")
    W = lambda x, y: to_world((x, y), B_O, B_YAW)  # noqa: E731
    steps = 13
    for s in range(steps):
        x, y = W(5.55, 0.9 + 0.42 * s + 0.21)
        nx.box(f"b_step{s}", (1.5, 0.42, 0.3 * (s + 1)), (x, y, 0), rot=(0, 0, B_YAW), **KICK)
    top = 0.3 * steps
    y0 = 0.9 + 0.42 * steps
    x, y = W(5.2, y0 + 2.3)
    nx.box("b_gallery", (2.6, 4.6, 0.3), (x, y, top - 0.3), rot=(0, 0, B_YAW), **KICK)
    for s in (0.6, 2.4, 4.0):
        x, y = W(4.25, y0 + s)
        nx.box(f"b_gpost{s}", (0.22, 0.22, top - 0.3), (x, y, 0), rot=(0, 0, B_YAW), collide=True, **FRAME)
    # 回廊的栏板与金扶手：西边（敞开的长边）、北头、东边；南头留出楼梯口。
    # 四块首尾相接（只共一条边，不叠在一起——叠了共面会闪）
    for nm, x0, x1, y0b, y1b in (("b_rail_w", 3.84, 3.96, 6.48, 10.84), ("b_rail_s", 3.96, 4.80, 6.36, 6.48),
                                 ("b_rail_n", 3.96, 6.38, 10.84, 10.96), ("b_rail_e", 6.38, 6.50, 6.48, 10.84)):
        x, y = W((x0 + x1) / 2, (y0b + y1b) / 2)
        nx.box(nm, (x1 - x0, y1b - y0b, 0.74), (x, y, top), rot=(0, 0, B_YAW), collide=True, **RAIL)
        nx.box(nm + "_hand", (x1 - x0, y1b - y0b, 0.14), (x, y, top + 0.74),
               rot=(0, 0, B_YAW), collide=False, **HAND)
    # 回廊上：一朵开着的
    x, y = W(5.2, 9.4)
    bloom("b_rose_up", (x, y, top), 0.95, 31, kind="cup", stem=0.3)
    # 当中：两株很高的、走近会张开的（离柱子与墙远；张开的角度收小，免得撞墙）
    bx1, by1 = W(2.7, 2.4)
    bloom("b_tall1", (bx1, by1, 0), 3.1, 12, kind="bud", stem=0.9, open_deg=14)
    bx2, by2 = W(2.3, 6.9)
    bloom("b_tall2", (bx2, by2, 0), 2.4, 14, kind="bud", stem=0.7, open_deg=14)
    # 西边一张矮台上一朵莲
    blx, bly = W(2.6, 9.6)
    pf.plinth("b_bed", (blx, bly, 0), 1.8, 1.6, h=0.4, yaw=B_YAW, **BED)
    bloom("b_lotus", (blx, bly, 0.4), 1.05, 17, kind="lotus", stem=0.3)
    blk = [blk_poly(B), blk_rect(W(5.55, 3.65), 1.5, 5.5, B_YAW),
           blk_rect((blx, bly), 1.8, 1.6, B_YAW),
           blk_circ((bx1, by1), reach("bud", 3.1, 14)), blk_circ((bx2, by2), reach("bud", 2.4, 14)),
           blk_circ((blx, bly), reach("lotus", 1.05))]
    fallen("b_fall", [W(3.8, 1.8), W(1.4, 9.2), W(3.0, 5.2), W(1.0, 3.6), W(4.0, 9.9), W(3.6, 7.2)], 6, 0.0, blk)
    # 北墙的玻璃门：走出去 → 光斑
    bn_L = math.dist(B[2], B[3])
    c = lerp(B[2], B[3], (bn_L - 2.6) / bn_L)
    yaw_out = B_YAW
    nx.veil("veil_sunpatch", 1.6, 2.6, (c[0], c[1], 0), yaw=yaw_out, a="gold", b="pink_pale")
    nx.portal("portal_sunpatch", (c[0], c[1], 1.0), "sunpatch", at="glasshouse", mode="walk", radius=0.6)
    fx, fy = pf._ahead((c[0], c[1], 0), yaw_out, 0.9)[:2]
    nx.collider_only(nx.box("b_door_stop", (2.4, 0.2, 3.0), (fx, fy, 0), rot=(0, 0, yaw_out)))
    p = pf._ahead((c[0], c[1], 0), yaw_out, -2.0)
    nx.arrive("sunpatch", p, facing_deg=yaw_out + 180)


# ── 低间 C ───────────────────────────────────────────

def room_c():
    """低间：门里一块平台、三级台阶下去；当中一池浅水和一朵重做的莲；西南一张矮床两株花（一株会张开）；
    西北一杯水 → 浅滩；地上一道长影 → 长影"""
    nx.into("c")
    ex = C[0][0]
    yc = A_DOOR_W[0]
    nx.box("c_landing", (1.6, 2.8, -C_FLOOR), (ex - 0.8, yc, C_FLOOR), **KICK)
    for s in range(3):
        nx.box(f"c_step{s}", (0.5, 2.8, 0.3 * (s + 1) - 0.01), (ex - 1.6 - 0.25 - 0.5 * (2 - s), yc, C_FLOOR), **KICK)
    cx, cy = C_C[0] - 0.3, C_C[1] + 1.3
    sh.tube("c_pool_rim", 1.55, 1.3, 0.3, (cx, cy, C_FLOOR), segments=24, **KICK)
    nx.cylinder("c_pool_water", 1.32, 1.32, 0.18, (cx, cy, C_FLOOR), segments=24, collide=False, a="blue_pale", b="blue", pattern="bands")
    bloom("c_lotus", (cx, cy, C_FLOOR + 0.18), 1.0, 23, kind="lotus", stem=0.15)
    # 西南一张矮床：一株走近会张开的 + 一朵开着的
    pf.plinth("c_bed", (-15.6, -3.6, C_FLOOR), 2.6, 1.4, h=0.4, yaw=25, **BED)
    bloom("c_bud", (-16.2, -3.7, C_FLOOR + 0.4), 1.2, 33, kind="bud", stem=0.4, open_deg=30)
    bloom("c_cup", (-14.4, -3.2, C_FLOOR + 0.4), 0.6, 35, kind="cup", stem=0.35)
    # 一杯水 → 浅滩（西北，面朝东南）
    gx, gy = C_C[0] - 2.6, C_C[1] + 2.3
    pf.gate_glass("glasshouse", (gx, gy, C_FLOOR), -125)
    blk = [blk_poly(C), blk_rect((ex - 0.8, yc), 1.6, 2.8), blk_rect((ex - 2.35, yc), 1.5, 2.8),
           blk_rect((cx, cy), 3.1, 2.6), blk_rect((-15.6, -3.6), 2.6, 1.4, 25),
           blk_circ((cx, cy), reach("lotus", 1.0)), blk_circ((-16.2, -3.7), reach("bud", 1.2, 30)),
           blk_circ((-14.4, -3.2), reach("cup", 0.6)), blk_circ((gx, gy), 0.7)]
    fallen("c_fall", [(C_C[0], C_C[1] + 4.1), (C_C[0] + 1.4, C_C[1] + 3.3), (C_C[0] + 1.2, C_C[1] - 2.8),
                      (C_C[0] - 1.2, C_C[1] - 3.4), (C_C[0] + 2.6, C_C[1] - 2.6), (C_C[0] - 2.8, C_C[1] + 1.0)],
           9, C_FLOOR, blk)


def long_shadow():
    """C 里地上的一道长影：外面东南一株很高的花（只投影、找不到）。站进花头的影子 → 长影"""
    nx.into("shadow")
    hx, hy = C_C[0] - 0.5, C_C[1] - 2.1
    head_h = 13.0
    k = head_h / SUN.z
    sx, sy = hx + SUN.x * k, hy + SUN.y * k
    base_z = GROUND_Z
    stem = fu.Kit()
    rx, ry = sx + 1.2, sy - 0.6
    beam(stem, (rx, ry, base_z), (sx, sy, C_FLOOR + head_h - 0.2), 0.3, 0.3)
    z0, z1 = C_FLOOR + head_h - 0.2, C_FLOOR + head_h + 0.4
    for i in range(7):
        a = math.tau * i / 7
        ca, sa = math.cos(a), math.sin(a)
        L, w = 1.7, 0.5
        slab(stem, [(sx, sy, z0),
                    (sx + ca * L * 0.45 + sa * w, sy + sa * L * 0.45 - ca * w, (z0 + z1) / 2),
                    (sx + ca * L, sy + sa * L, z1),
                    (sx + ca * L * 0.45 - sa * w, sy + sa * L * 0.45 + ca * w, (z0 + z1) / 2)], 0.08)
    nx.shade(stem.build("far_flower", smooth=0, collide=False))
    fallen("c_head_fall", [(hx + math.cos(t) * 0.9, hy + math.sin(t) * 0.9) for t in (0.3, 1.6, 2.9, 4.1, 5.3)],
           13, C_FLOOR, lmax=0.55, lmin=0.35)
    nx.portal("portal_longshadow", (hx, hy, C_FLOOR + 1.0), "longshadow", at="glasshouse", mode="walk", radius=0.8)
    nx.arrive("longshadow", (hx + 1.9, hy + 1.4, C_FLOOR), facing_deg=-60)
    return sx, sy


# ── 外面：暗着、够不着 ────────────────────────────────

def outside(rooms):
    nx.into("outside")
    nx.box("ground", (2 * EXTENT, 2 * EXTENT, 1.0), (0, 0, GROUND_Z - 1.0), a="lilac_dark", b="violet", pattern="drift")
    k = fu.Kit()
    for r in rooms:
        if r.name in ("A", "B", "AB", "AC"):
            prism(k, r.pts, GROUND_Z - 0.2, -0.21)
    k.build("podium", smooth=0, **PODIUM)
    kc = fu.Kit()
    prism(kc, C, GROUND_Z - 0.2, C_FLOOR - 0.21)
    kc.build("podium_c", smooth=0, **PODIUM)
    r = random.Random(41)
    spots = [(-24, 12, "bud", 9), (-8, 22, "cup", 7), (12, 20, "lotus", 6), (27, 9, "bud", 11),
             (26, -16, "cup", 8), (6, -22, "bud", 7), (-14, -20, "lotus", 7), (-30, -6, "cup", 9),
             (38, -2, "lotus", 6), (-2, 34, "bud", 13), (-38, 22, "lotus", 9)]
    for i, (x, y, kind, s) in enumerate(spots):
        bloom(f"out_{i}", (x, y, GROUND_Z), s, 50 + i, kind=kind, styles=OUT_PETALS, stem=0.35 * s, dark=True)
    blk = [blk_poly(A), blk_poly(B), blk_poly(C)] + [blk_circ((x, y), reach(kind, s) + 0.3) for x, y, kind, s in spots]
    for i in range(14):
        p, room = (0.0, 0.0), 0.0
        for _ in range(40):
            a = r.uniform(0, math.tau)
            d = r.uniform(15, 30)
            p = (math.cos(a) * d, math.sin(a) * d)
            room = min(b(p) for b in blk)
            if room > 1.5:
                break
        L = max(0.8, min(4.0, room - 0.25))
        petal_mesh(f"out_fall{i}", L, L * 0.42, 0.2, waist=0.42,
                   loc=(p[0], p[1], GROUND_Z + 0.11 + 0.025 * i),
                   rot=(0, 0, r.uniform(0, 360)), collide=False, pattern="plain", **OUT_PETALS[i % 3])


def build(extent=EXTENT):
    nx.into("env")
    nx.sun(tuple(SUN))
    nx.atmosphere("blank", grid=3, grid_lit=1, shadow_out=True, shadow_reach=50)

    rooms, b_door_c = plan()
    nx.into("glass")
    floor = fu.Kit()
    for r in rooms:
        prism(floor, r.pts, r.floor - 0.2, r.floor)
    floor.build("floors", smooth=0, **FLOOR)
    kits = {k: fu.Kit() for k in ("frame", "kick", "glass", "collider")}
    for r in rooms:
        r.build(kits)
    kits["frame"].build("frames", smooth=0, collide=False, **FRAME)
    kits["kick"].build("kick", smooth=0, **KICK)
    kits["glass"].build("glass", smooth=0, **GLASS)
    nx.collider_only(kits["collider"].build("glass_block", smooth=0))

    nx.into("light")
    canopy(rooms)

    room_a()
    room_b(b_door_c)
    room_c()
    long_shadow()
    outside(rooms)


if __name__ == "__main__":
    nx.reset()
    build()
    nx.save_blend("glasshouse-var-2")
    nx.export("glasshouse-var-2")
