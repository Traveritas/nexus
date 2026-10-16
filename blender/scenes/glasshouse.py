"""浅梦 · 花房（glasshouse）正式版：三间歪着挨在一起的玻璃房，浅梦的小枢纽。

- 形状：一间（小连房）。三间玻璃房坐在一块抬起来的石台上，两条短廊连着：
  · 大间（A）：13 × 8.5m，屋脊偏北，出生在这里；花瓶回家。
  · 高间（B）：东边，斜着转了 12°、平面是歪的平行四边形，屋脊从南往北一路抬高（6.8 → 10m）；
    东墙一道楼梯上到 3.9m 的回廊，从上面看得见另外两间的屋顶；北墙一扇玻璃门 → 光斑。
  · 低间（C）：西边，六角、往下沉 0.9m，门里先是一块平台、三级台阶下去；当中一池浅水和一朵莲；
    一杯水 → 浅滩；地上一道从外面伸进来的长影（花的影子，花找不到）→ 长影。
- 玻璃：看不见的玻璃（只挡人）＋ 白的窗棂与横档，分成一格格；玻璃面是一层淡蓝的半透（0.5m 内才散），几格里有两道斜的白反光。
- 玻璃里外不一样：头顶 28m 一整片看不见的顶（nx.shade），只在三间房的正上方（顺着太阳）开了洞——
  阳光只落进玻璃房里。屋里亮、格子细（2px）；隔着玻璃看出去，外面整片在影子里，暗、粗（8px）。
  外面是够不着的：石台四周落下去 1.2m，再远是一圈很大的花之装置，暗着。
- 花：屋里塞得密，平的、尖头的花瓣板做的装置（花房自己的一份 cup / lotus / bud，瓣从够宽的根环上长出来，互不穿），开的、没开的、落下的都有；两株没开的走近会往外张开（只往外倒，越开离得越远）。
- 出入口（来回成对：从哪个世界来，就落在通往它的东西跟前）：
  · 花瓶（A，E「凑近」）→ 家（house，落点 glasshouse）；从家来落在花瓶前（arrive house，也是出生点）
  · 玻璃门（B 北墙，走出去）→ 光斑（sunpatch，落点 glasshouse）；从光斑来落在门前（arrive sunpatch）
  · 一杯水（C，E「一杯水」）→ 浅滩（shoal，落点 glasshouse）；从浅滩来落在杯前（arrive shoal）
  · 长影的花头（C 地上，走进去）→ 长影（longshadow，落点 glasshouse）；从长影来落在影子旁（arrive longshadow）

运行：node scripts/blender.cjs build glasshouse，网页 ?world=glasshouse
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
# 玻璃：一层淡蓝的半透（按 Bayer 格子筛掉一部分像素），近处也在——0.5m 内才散；一格格由窗棂、横档分开
GLASS = dict(a="blue_pale", b="white", pattern="plain", collide=False, shadow=False, ghost=(0.4, 0.5, 2.0))
# 玻璃上的反光：几格玻璃里两道斜的白条，自己发亮，也是半透的
GLINT = dict(a="white", b="white", pattern="plain", collide=False, shadow=False, emit=1.0, ghost=(0.45, 0.4, 1.6))
TRANSOM = 1.3         # 横档的间距（从矮墙顶往上）
BED = dict(ramp=("lilac_dark", "lilac", "lilac_pale"), pattern="grain")


def sun_vec():
    e = math.radians(ELEV)
    h = Vector((SUN_H[0], SUN_H[1], 0)).normalized()
    return Vector((h.x * math.cos(e), h.y * math.cos(e), math.sin(e)))


SUN = sun_vec()


def shadow_point(x, y, h):
    """离地 h 米的一点，影子落在地上的哪儿（地上 = 那点正下方的平面）"""
    k = h / SUN.z
    return x - SUN.x * k, y - SUN.y * k


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
    # 顶点：0 a-- 1 a-+ 2 a+- 3 a++ 4 b-- 5 b-+ 6 b+- 7 b++
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
    roof=("gable", f, hs, hn)：pts 是四边形，pts[0]→pts[1] 是南头、pts[2]→pts[3] 是北头，屋脊从南头 f 处到北头 f 处，两头高 hs、hn（相对地面）；
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
        fr, kick, glass, col, glint = kits["frame"], kits["kick"], kits["glass"], kits["collider"], kits["glint"]
        z0 = self.floor
        n = len(self.pts)
        for i in range(n):
            a, b = self.edge(i)
            L = math.dist(a, b)
            inward = (-(b[1] - a[1]) / L, (b[0] - a[0]) / L)   # 逆时针的多边形：边的左手是屋里
            if self.posts and not ({i, (i - 1) % n} & self.open):
                beam(fr, (*a, z0 + KICK_H - 0.01), (*a, z0 + self.roof_h(i, 0) + 0.06), 0.25, 0.25)
            if i in self.open:
                continue
            gaps = sorted((c - w / 2, c + w / 2, h) for c, w, h in self.doors.get(i, []))
            # 实段：门洞之间
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
                # 横档：每 TRANSOM 米一道，到这一段墙顶低的那头以下
                top_lo = min(self.roof_h(i, s0 / L), self.roof_h(i, s1 / L))
                zt = KICK_H + TRANSOM
                while zt < top_lo - 0.35:
                    beam(fr, (*lerp(a, b, s0 / L), z0 + zt), (*lerp(a, b, s1 / L), z0 + zt), 0.08, 0.1)
                    zt += TRANSOM
                # 反光：隔两格挑一格，两道斜的白条，贴在玻璃里侧 7cm（让开横档）
                pw = (s1 - s0) / m
                for j in range(m):
                    if (j + i + len(self.name)) % 3 != 1 or pw < 1.0:
                        continue
                    sa = s0 + pw * j
                    zb, zh = z0 + KICK_H + 0.35, min(top_lo - KICK_H - 0.5, 2.0)
                    if zh < 0.8:
                        continue
                    for off, wd, h0, h1 in ((0.2, 0.11, 0.15, 0.8), (0.48, 0.045, 0.3, 0.9)):
                        def P(s, z):
                            q = lerp(a, b, s / L)
                            return (q[0] + inward[0] * 0.07, q[1] + inward[1] * 0.07, z)
                        x0 = sa + pw * off
                        slab(glint, [P(x0, zb + zh * h0), P(x0 + wd, zb + zh * h0),
                                     P(x0 + wd + 0.35, zb + zh * h1), P(x0 + 0.35, zb + zh * h1)], 0.01)
                # 门洞边上的门框
                for s in (s0, s1):
                    if 0.2 < s < L - 0.2:
                        p = lerp(a, b, s / L)
                        beam(fr, (*p, z0 - 0.02), (*p, z0 + self.roof_h(i, s / L) + 0.02), 0.18, 0.16)
                # 玻璃面（虚像）：矮墙顶到墙顶
                q0, q1 = lerp(a, b, s0 / L), lerp(a, b, s1 / L)
                poly = [(*q0, z0 + KICK_H), (*q1, z0 + KICK_H), (*q1, z0 + self.roof_h(i, s1 / L)), (*q0, z0 + self.roof_h(i, s0 / L))]
                # 山墙在这一段里有屋脊的拐点
                if self.roof[0] == "gable" and i in (0, 2):
                    ff = self.roof[1] if i == 0 else 1 - self.roof[1]
                    if s0 / L < ff < s1 / L:
                        pk = lerp(a, b, ff)
                        poly.insert(3, (*pk, z0 + self.roof_h(i, ff)))
                slab(glass, poly, 0.02)
            # 门：门楣、门楣以上的玻璃
            for g0, g1, h in gaps:
                p0, p1 = lerp(a, b, g0 / L), lerp(a, b, g1 / L)
                beam(fr, (*p0, z0 + h + 0.09), (*p1, z0 + h + 0.09), 0.2, 0.18)
                top0, top1 = self.roof_h(i, g0 / L), self.roof_h(i, g1 / L)
                if min(top0, top1) > h + 0.3:
                    slab(glass, [(*p0, z0 + h + 0.18), (*p1, z0 + h + 0.18), (*p1, z0 + top1), (*p0, z0 + top0)], 0.02)
                    self._wall_box(col, p0, p1, z0 + h + 0.18, z0 + max(top0, top1, 3.0), 0.14)
            # 檐梁
            if not (self.roof[0] == "gable" and i in (0, 2)):
                beam(fr, (*a, z0 + self.eave + 0.06), (*b, z0 + self.eave + 0.06), 0.2, 0.2)
        self._roof(fr, glass)

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
            # 山墙的斜边
            for a, r in ((p0, r0), (p1, r0), (p3, r1), (p2, r1)):
                beam(fr, (*a, e + 0.06), r, 0.18, 0.18)
            for (a, b) in ((p1, p2), (p0, p3)):   # 两面坡：檐边 a→b，对着屋脊 r0→r1
                L = math.dist(a, b)
                m = max(2, math.ceil(L / 1.45))
                for j in range(1, m):
                    t = j / m
                    beam(fr, (*lerp(a, b, t), e + 0.06), lerp(r0, r1, t), 0.12, 0.12)
                slab(glass, [(*a, e + 0.12), (*b, e + 0.12), (r1[0], r1[1], r1[2] + 0.05), (r0[0], r0[1], r0[2] + 0.05)], 0.02)
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
                slab(glass, [(*a, e + 0.12), (*b, e + 0.12), (top[0], top[1], top[2] + 0.04)], 0.02)
            nx.cylinder(f"{self.name}_finial", 0.28, 0.05, 0.9, (top[0], top[1], top[2] - 0.1), segments=8, collide=False, **FRAME)


# ── 平面 ─────────────────────────────────────────────

def rot_pts(local, origin, yaw):
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    return [(origin[0] + x * c - y * s, origin[1] + x * s + y * c) for x, y in local]


def to_world(p, origin, yaw):
    return rot_pts([p], origin, yaw)[0]


# 大间 A
A = [(-6.5, -4.25), (6.5, -4.25), (6.5, 4.25), (-6.5, 4.25)]
# A 的「南头」要是 pts[0]→pts[1]：这里屋脊沿 x，换个起点让 0→1 是西头
A_G = [(-6.5, 4.25), (-6.5, -4.25), (6.5, -4.25), (6.5, 4.25)]   # 西头 0→1，东头 2→3
A_DOOR_E = (1.8, 2.4)    # 东墙上门的 y 中心、宽（东墙 = 边 2，从 (6.5,-4.25) 往北）
A_DOOR_W = (-2.6, 2.4)   # 西墙上门的 y 中心、宽（西墙 = 边 0，从 (-6.5,4.25) 往南）

# 高间 B：本地平行四边形（宽 6.5、长 11，北头往东错 1.2），转 12°
B_O, B_YAW = (9.6, -2.2), 12.0
B_LOCAL = [(0, 0), (6.5, 0), (7.7, 11), (1.2, 11)]
B = rot_pts(B_LOCAL, B_O, B_YAW)

# 低间 C：六角，一条边朝东
C_C, C_R = (-13.2, -2.6), 4.7
C = [(C_C[0] + C_R * math.cos(math.radians(-30 + 60 * k)), C_C[1] + C_R * math.sin(math.radians(-30 + 60 * k))) for k in range(6)]
C_FLOOR = -0.9


def door_on(pts, i, c, w):
    """边 i 上、以世界坐标的点 c 附近（投影）为中心的门：返回离边起点的米数"""
    a, b = pts[i], pts[(i + 1) % len(pts)]
    L = math.dist(a, b)
    t = ((c[0] - a[0]) * (b[0] - a[0]) + (c[1] - a[1]) * (b[1] - a[1])) / L
    return t


def plan():
    rooms = []
    # A：西墙边 0（从北往南）、南墙边 1、东墙边 2（从南往北）、北墙边 3
    a_e0 = A_DOOR_E[0] + 4.25          # 东墙从 y=-4.25 起
    a_w0 = 4.25 - A_DOOR_W[0]          # 西墙从 y=4.25 往南
    rooms.append(Room("A", A_G, 0.0, 3.4, ("gable", 0.36, 6.4, 6.4),
                      doors={2: [(a_e0, A_DOOR_E[1], 2.5)], 0: [(a_w0, A_DOOR_W[1], 2.5)]}))
    # B：边 3 是西墙（从 (1.2,11) 到 (0,0)），门对着 A 的东门
    bw_a, bw_b = B[3], B[0]
    t_mid = 0.78   # 西墙上门的位置（从北往南的比例）
    b_door_c = lerp(bw_a, bw_b, t_mid)
    b_door_s = math.dist(bw_a, bw_b) * t_mid
    # 北墙（边 2，从 (7.7,11) 往西到 (1.2,11)）上的玻璃门 → 光斑：离西头 2.4m
    bn_L = math.dist(B[2], B[3])
    rooms.append(Room("B", B, 0.0, 5.4, ("gable", 0.62, 6.8, 10.0),
                      doors={3: [(b_door_s, 2.4, 2.5)], 2: [(bn_L - 2.6, 1.6, 2.6)]}))
    # C：边 0 是东墙（从东南角往北）
    c_e = door_on(C, 0, (C[0][0], A_DOOR_W[0]), 0)
    rooms.append(Room("C", C, C_FLOOR, 3.9, ("apex", 6.6), doors={0: [(c_e, 2.4, 3.4)]}))

    # 廊 A–B：A 东门两边 → B 西门两边
    half = A_DOOR_E[1] / 2
    a0, a1 = (6.5, A_DOOR_E[0] - half), (6.5, A_DOOR_E[0] + half)
    d = Vector((bw_b[0] - bw_a[0], bw_b[1] - bw_a[1])).normalized()
    b0 = (b_door_c[0] + d.x * 1.2, b_door_c[1] + d.y * 1.2)   # 南边那头
    b1 = (b_door_c[0] - d.x * 1.2, b_door_c[1] - d.y * 1.2)
    # 逆时针：A 门南 → B 门南 → B 门北 → A 门北；南头（0→1）是靠 A 的那条？要 0→1、2→3 是两头敞开的边
    rooms.append(Room("AB", [a1, a0, b0, b1], 0.0, 2.95, ("gable", 0.5, 3.35, 3.35), open_edges=(0, 2), posts=False))
    # 廊 A–C：A 西门 → C 东门（C 的东墙 x = C[0][0]）
    cx_e = C[0][0]
    w0, w1 = (-6.5, A_DOOR_W[0] + half), (-6.5, A_DOOR_W[0] - half)
    c0, c1 = (cx_e, A_DOOR_W[0] - half), (cx_e, A_DOOR_W[0] + half)
    rooms.append(Room("AC", [w1, w0, c1, c0], 0.0, 2.95, ("gable", 0.5, 3.35, 3.35),
                      open_edges=(0, 2), posts=False))
    return rooms, b_door_c


# ── 光：看不见的顶，只在房间上方开洞 ─────────────────

def canopy(rooms):
    """CANOPY_Z 高的一整片看不见的顶（只投影），按 0.5m 的格：格心顺着太阳落到地面（与 1.5m 高处）若在某间房里，就开洞"""
    step = 0.5
    k = fu.Kit()
    lit = []
    for r in rooms:
        lit.append((r.pts, r.floor))
    ext = CANOPY_EXT
    nrow = int(2 * ext / step)

    def hole(x, y):
        for pts, f in lit:
            for zz in (f, f + 1.6):
                kk = (CANOPY_Z - zz) / SUN.z
                gx, gy = x - SUN.x * kk, y - SUN.y * kk
                if inside((gx, gy), pts, 0.35):
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


# ── 花：平的尖头板，按尺寸排开，瓣与瓣之间不穿 ─────────────
# 花房自己的一份（不用 prefabs.bloom：那边的莲几层瓣互相穿过去、没开的花根部挤在一起）。
# 每朵花的瓣都从一圈「根环」上长出来，根环的半径按瓣的宽、厚和倾角算够：相邻两瓣在最宽处也隔着几厘米。

PETALS = [dict(a="white", b="pink_pale"), dict(a="pink_pale", b="pink"), dict(a="mist", b="blue_pale"),
          dict(a="pink_pale", b="white")]
# 外面的花：暗着（浅色在影子里压不下去，直接用深一档的色）
OUT_PETALS = [dict(a="lilac", b="lilac_dark"), dict(a="rose", b="lilac"), dict(a="lilac_dark", b="violet")]
HUB = dict(a="lilac_pale", b="lilac", pattern="stripes")
OUT_HUB = dict(a="lilac_dark", b="violet", pattern="stripes")


def _sty(styles, i, collide=False):
    s = dict(styles[i % len(styles)])
    s.setdefault("pattern", "grain")
    s["collide"] = collide
    return s


def ring_r(n, L, W, t, lean):
    """n 片长 L、宽 W、厚 t、仰角 lean（度）的瓣围成一圈，根环至少要多大，瓣才不互相碰"""
    s = math.sin(math.pi / n)
    c = math.cos(math.radians(lean))
    return max(t * 1.7 / (2 * s),
               (0.62 * W + 0.08) / (2 * s) - 0.18 * L * c,
               (W + 0.08) / (2 * s) - 0.55 * L * c)


def petal_ring(g, name, n, L, W, t, lean, z, styles, seed, off=0.0, r0=None, waist=0.55, k0=0, jitter=True):
    """一圈瓣：根在半径 r0、高 z 的环上，沿径向往外仰 lean 度。返回 (r0, 瓣列表)"""
    r = random.Random(seed)
    r0 = ring_r(n, L, W, t, lean) if r0 is None else r0
    out = []
    for i in range(n):
        az = off + 360 / n * i
        a = math.radians(az)
        Li = L * (r.uniform(0.92, 1.0) if jitter else 1.0)
        p = pf.plate(f"{name}{i}", Li, W, thick=t, waist=waist,
                     loc=(math.cos(a) * r0, math.sin(a) * r0, z + t / 2 + 0.02),
                     rot=(r.uniform(-4, 4) if jitter else 0, -lean, az), parent=g, **_sty(styles, k0 + i))
        out.append(p)
    return r0, out


def cup(name, loc, size, seed, n=7, lean=52, styles=PETALS, hub=HUB, yaw=None, axis=True):
    """开着的花：一圈往外仰的瓣，围着一根细轴。size ≈ 瓣长。半径（伸多远）≈ 根环 + size·cos(lean)"""
    r = random.Random(seed)
    g = nx.group(name, loc, (0, 0, r.uniform(0, 360) if yaw is None else yaw))
    L, W, t = size, size * 0.34, max(0.1, size * 0.03)
    r0 = ring_r(n, L, W, t, lean)
    ax = max(0.05, min(size * 0.06, r0 - t - 0.06))
    if axis:
        nx.cylinder(f"{name}_axis", ax, ax * 0.7, size * 0.85, (0, 0, 0), segments=10, parent=g, collide=False, **hub)
    petal_ring(g, f"{name}_p", n, L, W, t, lean, size * 0.12, styles, seed, r0=r0)
    return g


def lotus(name, loc, size, seed, styles=PETALS, hub=HUB, yaw=None):
    """莲：三层，外层平、里层直；外层根环最大、最低，往里一层比一层小、高、陡——层与层错开半瓣，不穿"""
    r = random.Random(seed)
    g = nx.group(name, loc, (0, 0, r.uniform(0, 360) if yaw is None else yaw))
    t = max(0.08, size * 0.03)
    tiers = [(10, 18, 1.0), (8, 42, 0.78), (6, 68, 0.55)]   # (瓣数, 仰角, 长)
    rings = []
    for k, (n, lean, kk) in enumerate(tiers):
        L = size * kk
        rings.append(ring_r(n, L, L * 0.36, t, lean))
    # 往里一层，根环要更小（至少小一个瓣厚多点），但够自己那一圈用
    for k in range(1, 3):
        rings[k] = min(rings[k], rings[k - 1] - 2 * t - 0.04)
    for k in range(1, 3):
        n, lean, kk = tiers[k]
        need = ring_r(n, size * kk, size * kk * 0.36, t, lean)
        if rings[k] < need:   # 太挤：整体放大外圈
            d = need - rings[k]
            rings = [x + d for x in rings]
    base_h = max(0.08, size * 0.1)
    nx.cylinder(f"{name}_base", rings[0] + 0.06, rings[0] * 0.8, base_h, (0, 0, 0), segments=24, parent=g, collide=False, **hub)
    z = base_h
    for k, (n, lean, kk) in enumerate(tiers):
        L = size * kk
        petal_ring(g, f"{name}_t{k}p", n, L, L * 0.36, t, lean, z, styles, seed + k, off=(180 / n) * k, r0=rings[k], k0=k)
        z += 2 * t + 0.03
    return g


def bud(name, loc, size, seed, opens=0.0, styles=PETALS, hub=HUB, n=5):
    """没开的花：几片几乎直立的长瓣围成一圈，中间一根蕊。opens>0：走近时每瓣绕自己的根往外倒 opens 度（张开），走开合上。
    瓣不扭、不交叉：合着时根环够宽，张开只会让瓣离得更远"""
    r = random.Random(seed)
    g = nx.group(name, loc, (0, 0, r.uniform(0, 360)))
    L, W, t = size, size * 0.24, max(0.1, size * 0.035)
    lean = 80
    r0, ps = petal_ring(g, f"{name}_b", n, L, W, t, lean, 0.0, styles, seed, waist=0.4, jitter=False)
    ax = max(0.05, r0 - t - 0.08)
    nx.cylinder(f"{name}_pistil", ax, ax * 0.5, L * 0.55, (0, 0, 0), segments=8, parent=g, collide=False, **hub)
    if opens:
        for p in ps:
            nx.pose(p, f"{name}_open", on="near", at=(loc[0], loc[1], loc[2]), radius=2.8, rot=(0, opens, 0), time=2.4)
    return g


def fallen(name, pts, n, seed, z, avoid=(), Lr=(0.6, 1.2), styles=PETALS, thick=0.06, margin=0.3):
    """落下的瓣：平躺在地上的尖头板。pts：逆时针的凸多边形，瓣落在里面（离边 margin 以上）；
    avoid：[(x, y, r)] 这些圈里不落；瓣与瓣不叠"""
    r = random.Random(seed)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    placed = []
    tries = 0
    while len(placed) < n and tries < 2000:
        tries += 1
        L = r.uniform(*Lr)
        x, y = r.uniform(min(xs), max(xs)), r.uniform(min(ys), max(ys))
        if not inside((x, y), pts, -(margin + L / 2)):
            continue
        if any(math.hypot(x - ax_, y - ay) < ar + L / 2 for ax_, ay, ar in avoid):
            continue
        if any(math.hypot(x - px, y - py) < (L + pl) / 2 + 0.05 for px, py, pl in placed):
            continue
        placed.append((x, y, L))
        yaw = r.uniform(0, 360)
        # 板沿本地 +X 伸出：把中心放到 (x, y)
        ox, oy = -math.cos(math.radians(yaw)) * L / 2, -math.sin(math.radians(yaw)) * L / 2
        pf.plate(f"{name}{len(placed)}", L, L * 0.34, thick=thick, loc=(x + ox, y + oy, z + thick / 2 + 0.004),
                 rot=(0, 0, yaw), collide=False, pattern="plain", **styles[len(placed) % len(styles)])
    return placed


# ── 三间房 ───────────────────────────────────────────

def room_a():
    """大间：北边一条长花床（开的、没开的、莲）、中间偏西一张岛床（大莲）、
    东南一株比人高的花；东南角花瓶（回家）"""
    nx.into("a")
    pf.plinth("a_bed_n", (-2.5, 2.75, 0), 7.6, 1.7, h=0.4, **BED)
    pf.plinth("a_bed_i", (-2.9, -1.0, 0), 3.4, 2.4, h=0.4, yaw=-9, **BED)
    cup("a_cup1", (-5.3, 2.75, 0.4), 1.05, 3)
    bud("a_bud1", (-2.6, 2.75, 0.4), 1.25, 5)
    lotus("a_lotus1", (0.2, 2.75, 0.4), 0.85, 7)
    lotus("a_lotus2", (-2.9, -1.0, 0.4), 1.25, 11)
    # 东南一株比人高的（开到最大，瓣仰得陡，不挡东门进来的路）
    cup("a_cup_big", (4.6, -1.2, 0), 2.0, 21, n=7, lean=62)
    # 回家：方台上插花的瓶
    loc, yaw = (3.6, -3.1, 0.0), 20
    vase_home(loc, yaw)
    p = pf._ahead(loc, yaw, 2.1)
    nx.arrive("house", p, facing_deg=yaw + 25)
    nx.spawn(p, facing_deg=yaw + 25)
    fallen("a_fall", A, 9, 2, 0.0,
           avoid=[(-2.5, 2.75, 1.2), (-2.9, -1.0, 2.4), (4.6, -1.2, 1.4), (3.6, -3.1, 0.9), (p[0], p[1], 0.8),
                  (6.5, 1.8, 1.3), (-6.5, -2.6, 1.3)])


def vase_home(loc, yaw):
    """方台上一只瓶，插着几枝花（直杆、杯形的花头，同家具里的瓶花；杆各自从瓶口的一点插下去，花头彼此隔开）"""
    pf.plinth("vase_home_plinth", loc, 0.9, 0.9, h=0.5, yaw=yaw, a="white", b="mist", pattern="plain")
    H = 0.8
    fu.vase("vase_home", (loc[0], loc[1], 0.5), H, "round", flowers=0, seed=4, style=dict(a="pink_pale", b="white", pattern="plain"))
    top = 0.5 + H
    heads = [fu.Kit() for _ in range(3)]
    HEAD = [(0.0, -0.04), (0.07, 0.0), (0.15, 0.1), (0.12, 0.12), (0.0, 0.07)]
    for k, (az, lean, L) in enumerate(((20, 18, 0.6), (130, 28, 0.42), (250, 8, 0.72), (330, 32, 0.36))):
        a, tl = math.radians(az + yaw), math.radians(lean)
        d = (math.cos(a) * math.sin(tl), math.sin(a) * math.sin(tl), math.cos(tl))
        s0 = (loc[0] + math.cos(a) * 0.08, loc[1] + math.sin(a) * 0.08, top + 0.02)   # 各自从瓶口的一点插下去，杆底不挤
        s1 = (s0[0] + d[0] * L, s0[1] + d[1] * L, s0[2] + d[2] * L)
        k_ = fu.Kit()
        beam(k_, s0, s1, 0.025, 0.025)
        k_.build(f"vase_home_stem{k}", smooth=0, collide=False, a="lilac_pale", b="mist", pattern="plain")
        heads[k % 3].lathe(HEAD, s1, rot=(0, lean, az + yaw), seg=6, start=15 * k)
    for i, (k_, st) in enumerate(zip(heads, (dict(a="pink", b="pink_pale"), dict(a="white", b="pink_pale"), dict(a="blue_pale", b="white")))):
        k_.build(f"vase_home_head{i}", smooth=0, collide=False, pattern="plain", **st)
    nx.portal("portal_vase_home", (loc[0], loc[1], 1.4), "house", at="glasshouse", mode="key", title="凑近", radius=0.9)


def room_b(b_door_c):
    """高间：东墙一道楼梯上到回廊；当中一株很高的、没开的（走近张开一点）；一张矮台上一朵莲；北墙一扇玻璃门 → 光斑"""
    nx.into("b")
    W = lambda x, y: to_world((x, y), B_O, B_YAW)  # noqa: E731
    # 楼梯（沿东墙往北）与回廊
    steps = 13
    for s in range(steps):
        x, y = W(5.55, 0.9 + 0.42 * s + 0.21)
        nx.box(f"b_step{s}", (1.5, 0.42, 0.3 * (s + 1)), (x, y, 0), rot=(0, 0, B_YAW), **KICK)
    top = 0.3 * steps
    y0 = 0.9 + 0.42 * steps
    x, y = W(5.15, y0 + 2.15)
    nx.box("b_gallery", (2.3, 4.3, 0.3), (x, y, top - 0.3), rot=(0, 0, B_YAW), **KICK)
    for s in (0.6, 2.4, 4.0):
        x, y = W(4.25, y0 + s)
        nx.box(f"b_gpost{s}", (0.22, 0.22, top - 0.3), (x, y, 0), rot=(0, 0, B_YAW), collide=True, **FRAME)
    # 回廊上：一朵开着的
    x, y = W(5.4, y0 + 3.4)
    cup("b_cup_up", (x, y, top), 1.0, 31, lean=56)
    # 当中：一株很高的、没开的，走近张开一点
    x, y = W(2.8, 4.6)
    bud("b_tall", (x, y, 0), 3.1, 12)
    xb, yb = W(2.2, 7.1)
    pf.plinth("b_bed", (xb, yb, 0), 2.0, 2.6, h=0.4, yaw=B_YAW + 6, **BED)
    lotus("b_lotus", (xb, yb, 0.4), 0.9, 17)
    # 北墙的玻璃门：走出去 → 光斑
    bn_L = math.dist(B[2], B[3])
    c = lerp(B[2], B[3], (bn_L - 2.6) / bn_L)
    yaw_out = B_YAW  # 门朝北（本地 +Y）
    nx.veil("veil_sunpatch", 1.3, 2.4, (c[0], c[1], 0), yaw=yaw_out, a="gold", b="pink_pale")
    nx.portal("portal_sunpatch", (c[0], c[1], 1.0), "sunpatch", at="glasshouse", mode="walk", radius=0.6)
    # 门外一块看不见的挡板（门槛外 0.8m）：走不出石台
    fx, fy = pf._ahead((c[0], c[1], 0), yaw_out, 0.9)[:2]
    nx.collider_only(nx.box("b_door_stop", (2.4, 0.2, 3.0), (fx, fy, 0), rot=(0, 0, yaw_out)))
    p = pf._ahead((c[0], c[1], 0), yaw_out, -2.0)
    nx.arrive("sunpatch", p, facing_deg=yaw_out + 180)
    tx, ty = W(2.8, 4.6)
    fallen("b_fall", B, 6, 6, 0.0,
           avoid=[(tx, ty, 1.9), (xb, yb, 1.8), (*W(5.55, 1.6), 1.1), (*W(5.55, 3.6), 1.1), (*W(5.55, 5.6), 1.1), (*W(5.15, 8.7), 1.6), (p[0], p[1], 0.8),
                  (b_door_c[0], b_door_c[1], 1.4), (c[0], c[1], 1.0)])


def room_c():
    """低间：门里一块平台、三级台阶下去；当中一池浅水和一朵莲；西北一杯水 → 浅滩；地上一道长影 → 长影"""
    nx.into("c")
    ex = C[0][0]
    yc = A_DOOR_W[0]
    # 平台（门里 1.6m）与三级台阶（往西）；宽 2.2，让开门框
    nx.box("c_landing", (1.5, 2.2, -C_FLOOR), (ex - 0.85, yc, C_FLOOR), **KICK)
    for s in range(3):
        nx.box(f"c_step{s}", (0.5, 2.2, 0.3 * (s + 1) - 0.01), (ex - 1.6 - 0.25 - 0.5 * (2 - s), yc, C_FLOOR), **KICK)
    # 一池浅水：一圈矮沿，水面低于沿口
    cx, cy = C_C[0] - 0.7, C_C[1] + 1.6
    import shapes as sh
    sh.tube("c_pool_rim", 1.4, 1.18, 0.3, (cx, cy, C_FLOOR), segments=24, **KICK)
    nx.cylinder("c_pool_water", 1.17, 1.17, 0.18, (cx, cy, C_FLOOR), segments=24, collide=False, a="blue_pale", b="blue", pattern="bands")
    lotus("c_lotus", (cx, cy, C_FLOOR + 0.18), 0.62, 23)
    # 一杯水 → 浅滩（西北，面朝东南）
    gx, gy = C_C[0] - 2.6, C_C[1] + 2.3
    pf.gate_glass("glasshouse", (gx, gy, C_FLOOR), -125)
    return [(cx, cy, 1.5), (gx, gy, 0.8), (ex - 1.5, yc, 1.6)]


def long_shadow(c_avoid):
    """C 里地上的一道长影：外面东南一株很高的花（只投影、找不到），影子从玻璃外斜伸进来，花头落在 C 的西南。
    站进花头的影子 → 长影"""
    nx.into("shadow")
    # 花头的影子要落在这里（C 的地上）
    hx, hy = C_C[0] - 0.5, C_C[1] - 2.1
    head_h = 13.0   # 花头离 C 地面的高
    k = head_h / SUN.z
    sx, sy = hx + SUN.x * k, hy + SUN.y * k     # 花头在空中的水平位置
    base_z = GROUND_Z
    stem = fu.Kit()
    # 茎：从外面的地上斜斜地长到花头下面
    rx, ry = sx + 1.2, sy - 0.6
    beam(stem, (rx, ry, base_z), (sx, sy, C_FLOOR + head_h - 0.2), 0.3, 0.3)
    # 花头：一圈平的尖头瓣，微微翘起；影子是一颗七角的星（C 的窗棂不投影，地上只有这一道影子）
    z0, z1 = C_FLOOR + head_h - 0.2, C_FLOOR + head_h + 0.5
    for i in range(7):
        a = math.tau * i / 7
        ca, sa = math.cos(a), math.sin(a)
        L, w = 2.1, 0.55
        slab(stem, [(sx, sy, z0),
                    (sx + ca * L * 0.45 + sa * w, sy + sa * L * 0.45 - ca * w, (z0 + z1) / 2),
                    (sx + ca * L, sy + sa * L, z1),
                    (sx + ca * L * 0.45 - sa * w, sy + sa * L * 0.45 + ca * w, (z0 + z1) / 2)], 0.08)
    nx.shade(stem.build("far_flower", smooth=0, collide=False))
    # 花头的影子里落着一圈瓣（找得到传送点的记号；花本身找不到）
    for i, t in enumerate((0.3, 1.55, 2.8, 4.05, 5.3)):
        L = 0.7
        x, y = hx + math.cos(t) * 1.15, hy + math.sin(t) * 1.15
        yaw = math.degrees(t)
        pf.plate(f"c_head_fall{i}", L, L * 0.34, thick=0.06, loc=(x, y, C_FLOOR + 0.034), rot=(0, 0, yaw),
                 collide=False, pattern="plain", **PETALS[i % len(PETALS)])
    nx.portal("portal_longshadow", (hx, hy, C_FLOOR + 1.0), "longshadow", at="glasshouse", mode="walk", radius=0.8)
    # 落在影子旁，朝房间中心
    ax_, ay = hx + 1.6, hy + 0.4
    nx.arrive("longshadow", (ax_, ay, C_FLOOR), facing_deg=math.degrees(math.atan2(-(C_C[0] - ax_), C_C[1] - ay)))
    fallen("c_fall", C, 4, 9, C_FLOOR, avoid=[*c_avoid, (hx, hy, 2.4), (ax_, ay, 0.8)])
    return sx, sy


# ── 外面：暗着、够不着 ────────────────────────────────

def outside(rooms):
    nx.into("outside")
    nx.box("ground", (2 * EXTENT, 2 * EXTENT, 1.0), (0, 0, GROUND_Z - 1.0), a="lilac_dark", b="violet", pattern="drift")
    # 石台：三间房和廊底下一整块（每间各自的柱，拼起来）
    k = fu.Kit()
    for r in rooms:
        if r.name in ("A", "B", "AB", "AC"):
            prism(k, r.pts, GROUND_Z - 0.2, -0.21)
    k.build("podium", smooth=0, **PODIUM)
    kc = fu.Kit()
    prism(kc, C, GROUND_Z - 0.2, C_FLOOR - 0.21)
    kc.build("podium_c", smooth=0, **PODIUM)
    # 一圈很大的花之装置，暗着
    G = (0, 0, GROUND_Z)
    spots = [(-24, 13, "bud", 9), (-8, 24, "cup", 7), (13, 23, "lotus", 6), (28, 9, "bud", 11),
             (27, -17, "cup", 8), (6, -24, "bud", 7), (-15, -22, "lotus", 6), (-32, -6, "cup", 8),
             (-2, 36, "bud", 13), (-38, 24, "lotus", 7)]
    avoid = []
    for i, (x, y, kind, s) in enumerate(spots):
        loc = (x, y, GROUND_Z)
        if kind == "cup":
            cup(f"out_{i}", loc, s, 50 + i, styles=OUT_PETALS, hub=OUT_HUB)
            avoid.append((x, y, s * 0.75 + 1))
        elif kind == "lotus":
            lotus(f"out_{i}", loc, s, 50 + i, styles=OUT_PETALS, hub=OUT_HUB)
            avoid.append((x, y, s * 1.3 + 1))
        else:
            bud(f"out_{i}", loc, s, 50 + i, styles=OUT_PETALS, hub=OUT_HUB)
            avoid.append((x, y, s * 0.4 + 1))
    pf.bloom("out_halo", (38, -2, GROUND_Z), kind="halo", size=6, seed=58, styles=OUT_PETALS, collide=False)
    avoid.append((38, -2, 6))
    ring = [(math.cos(a) * 32, math.sin(a) * 32) for a in (math.tau * i / 12 for i in range(12))]
    # 落瓣：在石台外（离开石台 2m）、花之装置之间
    near = [(sum(p[0] for p in r.pts) / len(r.pts), sum(p[1] for p in r.pts) / len(r.pts), 9.5) for r in rooms if r.name in ("A", "B", "C")]
    fallen("out_fall", ring, 14, 41, GROUND_Z, avoid=[*avoid, *near], Lr=(2.0, 4.0), styles=OUT_PETALS, thick=0.16, margin=0.5)


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
    names = ("frame", "kick", "glass", "collider", "glint")   # glass、glint 照样收集但不再出模型（掉帧，2026-10-16 删）
    kits = {k: fu.Kit() for k in names}
    kits_c = {**kits, "frame": fu.Kit()}    # 低间的窗棂单独一份：不投影，地上只留长影的花头
    for r in rooms:
        r.build(kits_c if r.name == "C" else kits)
    kits["frame"].build("frames", smooth=0, collide=False, **FRAME)
    kits_c["frame"].build("frames_c", smooth=0, collide=False, shadow=False, **FRAME)
    kits["kick"].build("kick", smooth=0, **KICK)
    nx.collider_only(kits["collider"].build("glass_block", smooth=0))

    nx.into("light")
    canopy(rooms)

    room_a()
    room_b(b_door_c)
    c_avoid = room_c()
    long_shadow(c_avoid)
    outside(rooms)


if __name__ == "__main__":
    nx.reset()
    build()
    nx.save_blend("glasshouse")
    nx.export("glasshouse")
