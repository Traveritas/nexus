"""浅梦 · 断梯变体一（stair-var-1）：吊着的断梯。

整座断梯是从头顶那块 34m 见方的底面（z=44）上**吊下来**的——像一只巨大的风铃。
- 浮空的每一块不再是一块光板，而是一截「碎下来的踏步」：1–3 级真踏步，锯齿侧面、斜面底。
  有的正着（近端落脚、往前一级级升高，越往前越高），有的倒着（平的底面翻上来当路，齿挂在下面）。
  落脚的那一级顶面仍在原来的高度（断口的高差、间距一个没动）。
- 每一块都用一两根细线吊在头顶那块底面上：线的规格同正中吊大锤那根（0.15 见方、lilac_dark/lilac、
  不挡人、不投影），从底面垂下来、插进踏步里一点点。挂点出了底面就斜着拉回来，落进中间那个方洞就推到洞外。
- 有几处（第 3、第 6 块）的线断了：只剩一截垂线吊在踏步上方两三米处慢慢晃，那一块就那样悬着——读作「掉下来过」。
- 大锤、垂线、垂下的踏步串都照旧；远处雾里那 9 截断梯也吊起来 6 截（线往上没进雾里），留 3 截浮着做对比。
- 路线与第三轮一模一样（同样的 18 个断口、同样的落点、同样的第一圈安全网），只是浮空的东西换了样子、有了来处。

顺带记下第三轮文档与代码的出入（这一版按代码来）：第二圈是 **4 块**方石（不是 5 块）；
总高 **32.2m**（不是 33m）；第二圈那几块方石掉下去其实**仍落在纸上**（x −6.65、y −2.95…7.45 都在纸的 23.5×22m 里），
不是虚空。

运行：node scripts/blender.cjs build stair-var-1，网页 ?world=stair-var-1
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import furniture as fu  # noqa: E402
import nx  # noqa: E402

EXTENT = 120
CENTER = (0, 0)

RISE = 0.3
RUN = 0.45
W = 2.6           # 楼梯宽
T = 0.45          # 楼梯底下斜面的厚

STEP_RISE = 0.28  # 碎段自己每级多高（≤0.3，人能自动迈上去；断口的高差仍是原来那 0.5/0.45/0.25）
CHUNK_T = 0.35    # 碎段底下那道斜面的厚
WIRE_T = 0.15     # 吊线见方（同正中吊大锤那根 0.16；不细于 0.1，远了不闪）
SIDE_K = 0.35     # 每块侧偏收小（原来 ±0.7m，落点会被让到方砖边上）
YAW_K = 8.0       # 自转收小（原来是 ±12°）

PAGE = dict(a="white", b="mist", pattern="bands")
GUTTER = dict(a="lilac_pale", b="mist", pattern="plain")
STEP = [dict(ramp=("lilac_dark", "lilac", "lilac_pale"), top="white", pattern="plain"),
        dict(ramp=("lilac_dark", "lilac", "lilac_pale"), top="pink_pale", pattern="plain"),
        dict(ramp=("rose_deep", "rose", "pink"), top="white", pattern="plain")]
SLAB = dict(ramp=("lilac_dark", "lilac", "lilac_pale"), top="mist", pattern="tiles")
FAR = dict(ramp=("lilac_dark", "lilac", "lilac_pale"), pattern="plain")
BOB = dict(ramp=("rose", "gold", "white"), pattern="plain")
LINE = dict(a="lilac_dark", b="lilac", pattern="plain")
WIRE = LINE
ABOVE = dict(ramp=("violet", "lilac_dark", "lilac"), pattern="bands")
GLOW = dict(a="white", b="gold", pattern="plain", emit=1.0)

BOB_AT = (0.0, 0.0)
BOB_Z = 15.0      # 锤的下尖
TOP_Z = 44.0      # 头顶那块底面（底面在这，往上厚 3m）
CEIL_HALF = 17.0  # 头顶那块底面 34m 见方
HOLE_HALF = 3.0   # 中间那个方洞 6m 见方（挂在洞里的线没有东西可挂，要推开）
CUT = (2, 5)      # 这两块（0 起数）的线断了：只剩一截垂线吊在上面慢慢晃


def fwd(yaw):
    a = math.radians(yaw)
    return (-math.sin(a), math.cos(a))


def dir_rot(d):
    """把本地 +Z 转到方向 d 的欧拉角（度，同 nx 的 XYZ）——给斜着拉的吊线用"""
    L = math.sqrt(d[0] * d[0] + d[1] * d[1] + d[2] * d[2]) or 1.0
    p = math.degrees(math.acos(max(-1.0, min(1.0, d[2] / L))))
    th = math.degrees(math.atan2(d[0], -d[1]))
    return (p, 0.0, th)


# ── 楼梯与碎段 ───────────────────────────────────

def flight_geo(n, rise=RISE, run=RUN, w=W, t=T, flat=False, dz=0.0):
    """一跑楼梯的几何：本地 +Y 往上走，原点在第一级前沿的底下（z=0 是出发的地面）。
    侧面是锯齿，底下是一道斜面（flat=True 时底下是平的、厚 t）。dz：整个往本地 z 挪"""
    prof = [(0.0, -t)]
    for i in range(n):
        prof += [(i * run, (i + 1) * rise), ((i + 1) * run, (i + 1) * rise)]
    prof += [(n * run, -t if flat else n * rise - t - rise)]
    prof = [(y, z + dz) for y, z in prof]
    m = len(prof)
    verts = [(-w / 2, y, z) for y, z in prof] + [(w / 2, y, z) for y, z in prof]
    faces = [tuple(range(m - 1, -1, -1)), tuple(range(m, 2 * m))]
    for i in range(m):
        j = (i + 1) % m
        faces.append((i, j, m + j, m + i))
    return verts, faces


def flight_kit(n, rise=RISE, run=RUN, w=W, t=T, kit=None, flat=False, dz=0.0):
    """一跑楼梯（同第三轮）：本地 +Y 往上走，原点在第一级前沿的底下"""
    verts, faces = flight_geo(n, rise, run, w, t, flat, dz)
    k = kit or fu.Kit()
    return k._add(verts, faces)


def chunk_kit(n, span, w, t=CHUNK_T, step_rise=STEP_RISE, flip=False, kit=None):
    """一截「碎下来的踏步」：本地 +Y 是往前（往上）的方向，原点在近端的落脚边。
    不 flip：近端第一级的顶面在 z=0，往前一级级升高 step_rise；底下是一道斜面。
    flip：倒过来——平的底面翻到上面当路（齿挂在下面），整块顶面都在 z=0。
    span 是这一截在前进方向上的总长（取原来方砖的边长，落点与断口才对得上），每级进深 span/n。"""
    run = span / n
    verts, faces = flight_geo(n, step_rise, run, w, t, flat=flip)
    if flip:
        # 绕 X 翻 180°（旋转，不是镜像）：本地 y → −y、z → −z，平的底面（z=−t）翻到 z=+t
        verts = [(x, -y, -z) for x, y, z in verts]
    k = kit or fu.Kit()
    return k._add(verts, faces)


def chunk(name, x, y, z, yaw, span, w, n, t=CHUNK_T, step_rise=STEP_RISE, flip=False,
          tilt=(0.0, 0.0), dyaw=0.0, style=None):
    """在 (x, y) 放一截碎下来的踏步：近端的落脚顶面正好在 z（断口的高差因此一个没动）。
    tilt＝(前后倾, 左右倾) 度，绕近端那一点转，落点几乎不动。返回这一截的几个点：
      top  最高一级顶面的中心（吊线挂这）、near/far 最高一级顶面的近边、远边中点、yaw 朝向。"""
    run = span / n
    k = chunk_kit(n, span, w, t, step_rise, flip)
    if flip:
        loc, rot = (x, y, z - t), (tilt[0], tilt[1], yaw + 180 + dyaw)
    else:
        loc, rot = (x, y, z - step_rise), (tilt[0], tilt[1], yaw + dyaw)
    k.build(name, loc=loc, rot=rot, smooth=0, **(style or STEP[0]))
    fx, fy = fwd(yaw)
    if flip:
        n0, n1, tz = 0.0, span, z
    else:
        n0, n1, tz = (n - 1) * run, span, z + (n - 1) * step_rise
    mid = (n0 + n1) / 2
    return {"top": (x + fx * mid, y + fy * mid, tz),
            "near": (x + fx * n0, y + fy * n0, tz),
            "far": (x + fx * n1, y + fy * n1, tz),
            "yaw": yaw, "span": span, "n": n, "flip": flip}


class Path:
    """一条往上绕的路：游标（x, y, z, 朝向）一段段往前走，顺手把东西搭在走过的地方"""

    def __init__(self, x, y, z, yaw):
        self.x, self.y, self.z, self.yaw = x, y, z, yaw
        self.n = 0
        self.marks = {}
        self.jumps = []   # 断口：起跳处 (x, y, z, 朝向, 距离, 高差)，测试用
        self.chunks = []  # 浮着的碎段：吊线挂在这些上面

    def _name(self, kind):
        self.n += 1
        return f"{kind}_{self.n:02d}"

    def ahead(self, d, side=0.0):
        fx, fy = fwd(self.yaw)
        return (self.x + fx * d + fy * side, self.y + fy * d - fx * side)

    def go(self, d, dz=0.0):
        self.x, self.y = self.ahead(d)
        self.z += dz

    def flight(self, n, rise=RISE, run=RUN, w=W, style=None, thin=None):
        """一跑楼梯；thin＝(起, 止) 踏步厚度从起渐变到止（最后一跑，越往上越薄、越稀）"""
        name = self._name("flight")
        st = style or STEP[self.n % len(STEP)]
        if thin is None:
            flight_kit(n, rise, run, w).build(name, loc=(self.x, self.y, self.z), rot=(0, 0, self.yaw), smooth=0, **st)
            self.go(n * run, n * rise)
            return
        # 一级级分开的薄板，间隔也越来越大
        for i in range(n):
            f = i / max(1, n - 1)
            th = thin[0] + (thin[1] - thin[0]) * f
            gap = 0.0 if f < 0.3 else 0.25 * (f - 0.3) / 0.7
            self.go(gap, 0)
            cx, cy = self.ahead(run / 2)
            nx.box(f"{name}_{i}", (w * (1 - 0.25 * f), run, th), (cx, cy, self.z + rise - th), (0, 0, self.yaw), **st)
            self.go(run, rise)

    def slab(self, d, w=None, turn=0.0, th=0.6, style=SLAB, mark=None):
        """平台：往前 d 米；turn 不为 0 时是方的转角平台，走到中心转过去再出去"""
        w = w or W
        name = self._name("slab")
        size = (d, d) if turn else (w, d)
        cx, cy = self.ahead(d / 2)
        nx.box(name, (size[0], size[1], th), (cx, cy, self.z - th), (0, 0, self.yaw), **style)
        if mark:
            self.marks[mark] = (cx, cy, self.z, self.yaw)
        if turn:
            self.x, self.y = cx, cy
            self.yaw += turn
            self.go(d / 2)
        else:
            self.go(d)
        return name

    def gap(self, d, dz=0.0):
        self.jumps.append((self.x, self.y, self.z, self.yaw, d, dz))
        self.go(d, dz)

    def stones(self, n, size=1.5, gap=0.8, rise=0.5, th=0.5, jitter=0.5, seed=0, step_rise=STEP_RISE):
        """单独浮着的几级：不再是一块光板，而是一截截「碎下来的踏步」（1–3 级，锯齿侧面、斜面底）。
        落脚的那一级顶面仍在原来的高度（self.z），所以断口的距离与高差一个没动；
        侧偏与自转都收小（原来的 ±0.7m / ±12° 会把落点让到方砖边上）。每块都吊一根线（见 hang_all）。"""
        rnd = random.Random(seed)
        for i in range(n):
            self.jumps.append((self.x, self.y, self.z, self.yaw, gap, rise))
            self.go(gap, rise)
            x, y = self.ahead(0.0, rnd.uniform(-jitter, jitter) * SIDE_K)
            m = rnd.choice((1, 2, 3)) if size > 1.4 else rnd.choice((1, 2))
            c = chunk(self._name("chunk"), x, y, self.z, self.yaw + rnd.uniform(-YAW_K, YAW_K), size, size, m,
                      step_rise=step_rise, flip=rnd.random() < 0.3,
                      tilt=(rnd.uniform(-3, 3), rnd.uniform(-3, 3)),
                      style=STEP[(i + seed) % len(STEP)])
            self.chunks.append(c)
            self.go(size)

    def sideways(self, length, h=3.4):
        """侧躺的一跑：一整跑楼梯翻倒在一边，人踩着它的侧面（平的）走过去；锯齿的那一边朝外"""
        name = self._name("side")
        n = int(h / RISE)
        run = length / n
        # 底下是平的、厚 1.6：翻过来以后路面最窄处也有 1.9m（锯齿那一边越往前越宽），人走在离平的那一边约 0.95m 处
        k = flight_kit(n, RISE, run, w=0.8, t=1.6, flat=True, dz=0.65)
        cx, cy = self.x, self.y
        obj = k.build(name, loc=(cx, cy, self.z - 0.4), rot=(0, 90, self.yaw), smooth=0, **STEP[2])
        self.go(length)
        return obj


def page():
    """底下摊开的一页纸（两页，中间一道下凹的书沟）：头一圈的断口都在它上方"""
    nx.into("page")
    nx.box("page_left", (11.5, 22, 0.8), (-6.0, 0, -0.8), **PAGE)
    nx.box("page_right", (11.5, 22, 0.8), (6.0, 0, -0.8), (0, 0, 0), **PAGE)
    nx.box("page_gutter", (0.5, 22, 0.8), (0, 0, -1.0), **GUTTER)
    # 纸边：几页叠着、比上面一页小一圈，往下渐暗
    for i, (dx, c) in enumerate(((0.3, "mist"), (0.6, "lilac_pale"), (0.9, "lilac"))):
        nx.box(f"page_under_{i}", (24 - dx * 4, 22 - dx * 2, 0.5), (0, 0, -1.3 - i * 0.5),
               a=c, b=c, pattern="bands")


def route():
    nx.into("route")
    # 第一圈（纸上）：出生在纸的西南，朝东
    p = Path(-8.5, -7.0, 0.0, -90)
    p.marks["spawn"] = (p.x, p.y, p.z, p.yaw)   # 出生在纸上，不另垫一块
    p.go(2.4)
    p.flight(9)                       # 0 → 2.7
    p.slab(1.6)
    p.gap(1.7)                        # 头一个断口：平跳
    p.slab(2.2)
    p.flight(6)                       # → 4.5
    p.slab(4.0, turn=90, mark="c1")   # 东南角，转向北
    p.sideways(6.4)                   # 侧躺的一跑：走在它侧面
    p.stones(3, rise=0.5, gap=1.0, seed=1)   # → 6.0
    p.gap(0.8, 0.4)
    p.slab(4.0, turn=90, mark="c2")   # 东北角，转向西
    p.flight(8)                       # → 9.3
    over = p.ahead(-1.8)
    p.slab(3.0, mark="under")         # 头顶倒挂着一跑
    p.gap(1.5)
    p.flight(6)                       # → 11.1
    p.slab(4.0, turn=90, mark="c3")   # 西北角，转向南
    # 第二圈：往外放一点；跳得不难（这几块的底下其实还是纸，不是虚空）
    p.flight(5)                       # → 12.6
    p.stones(4, size=1.6, rise=0.45, gap=1.0, jitter=0.7, seed=4)   # → 14.4
    p.gap(0.8, 0.3)
    p.slab(4.4, turn=90, mark="c4")   # 西南角，转向东
    p.flight(10)                      # → 18.0
    p.gap(1.9)
    p.flight(6)                       # → 19.8
    p.slab(4.4, turn=90, mark="c5")   # 东南，转向北
    p.flight(7)                       # → 21.9
    p.slab(6.0, w=6.0, mark="rest")   # 宽平台：歇脚，晶体的岔路从这里出去
    p.flight(6)                       # → 23.7
    p.slab(4.4, turn=90, mark="c6")   # 东北，转向西
    # 第三圈：长的一跑，中间断掉三分之一（要快走着跳）
    p.flight(8)                       # → 26.1
    p.gap(2.4, -0.3)
    p.flight(8)                       # → 28.2
    p.slab(4.4, turn=90, mark="c7")   # 西北，转向南
    p.flight(6)                       # → 30.0
    p.slab(2.0, mark="last")
    # 最后一跑：越往上越薄、越稀，最后一级是亮的
    p.flight(10, thin=(0.4, 0.06))    # → 33.0
    gx, gy = p.ahead(0.8)
    nx.box("last_step", (1.6, 1.6, 0.08), (gx, gy, p.z - 0.08), (0, 0, p.yaw), collide=True, shadow=False, **GLOW)
    p.marks["top"] = (gx, gy, p.z, p.yaw)
    return p, over


def under(p, over):
    """头顶倒挂的一跑：从它底下钻过去"""
    x, y, z, yaw = p.marks["under"]
    k = flight_kit(9)
    # 倒过来以后最低的一级在 z + 6.2 − 2.7 ＝ 头顶 3.5m 处
    k.build("flight_hung", loc=(x - fwd(yaw)[0] * 1.5, y - fwd(yaw)[1] * 1.5, z + 6.2), rot=(180, 0, yaw + 180), smooth=0,
            collide=False, **STEP[0])


def dangling(p):
    """从头顶那块底面垂下来、慢慢荡着的一串踏步（够不着，只是看）：原点在挂点上"""
    x, y, z, yaw = p.marks["c5"]
    fx, fy = fwd(yaw)
    hx, hy = x + fy * 5.5, y - fx * 5.5
    # 会动的只认网格自己（空物体父级上的 nx_sway 不起作用）：线和踏步攒成一个网格。最低一级在平台上方约 1.5m
    drop = TOP_Z - (z + 12.0)
    k = fu.Kit()
    k.box((0.14, 0.14, drop + 11), (0, 0, -(drop + 11)))
    for i in range(12):
        k.box((1.6, 0.5, 0.22), (0, (i % 2) * 0.12, -drop - i * 0.95), (0, 0, i * 7))
    obj = k.build("dangle", loc=(hx, hy, TOP_Z), rot=(0, 0, yaw), smooth=0, collide=False, **STEP[1])
    nx.behave(obj, sway=3)
    return obj


def plumb():
    """正中垂下的一根线、一枚大锤：远远就看得见，绕着它往上走"""
    nx.into("plumb")
    x, y = BOB_AT
    k = fu.Kit()
    k.lathe([(0, 0), (1.3, 1.8), (1.05, 2.6), (0, 4.4)], seg=8)
    bob = k.build("bob", loc=(x, y, BOB_Z), smooth=0, collide=False, **BOB)
    nx.behave(bob, bob=0.5, spin=4)
    # 线从头顶那块底面垂下来；锤上下浮 0.5m，线的下端插进锤顶里一截，浮起落下都接得上
    nx.box("bob_line", (0.16, 0.16, TOP_Z - BOB_Z - 3.6), (x, y, BOB_Z + 3.6), collide=False, shadow=False, **LINE)


def crystal_spur(p):
    """宽平台一侧伸出去的几级：不再是一块块方砖，而是一截截碎下来的踏步（2–3 级），
    一级比一级高一点、转一点；尽头一块斜板上浮着晶体（照旧）。
    断口照主路线那样记：记在**这一块的远边**上（下一块的近边在 gap 之外）——
    所以每块碎段放在 `edge + gap`，`edge` 走完变成它的远边。"""
    nx.into("spur")
    x, y, z, yaw = p.marks["rest"]
    fx, fy = fwd(yaw)
    # 往右手边（远离中心）伸出去
    sx, sy = fy, -fx
    side_yaw = yaw - 90
    size, gap, rise = 1.7, 0.75, 0.25
    edge, top = 3.0, z           # 平台边上
    for i in range(4):
        p.jumps.append((x + sx * edge, y + sy * edge, top, side_yaw, gap, rise))
        top += rise
        c = edge + gap                      # 这一块的近边
        cc = chunk(f"spur_{i}", x + sx * c, y + sy * c, top, side_yaw, size, size,
                   3 if i % 2 == 0 else 2, t=0.42, step_rise=rise, flip=(i == 1),
                   tilt=(0, 0) if i % 2 == 0 else (0, 3), dyaw=3 * i, style=STEP[i % 3])
        p.chunks.append(cc)
        edge = c + size
    p.jumps.append((x + sx * edge, y + sy * edge, top, side_yaw, gap, 0.1))
    c = edge + gap + 1.6
    ex, ey = x + sx * c, y + sy * c
    nx.box("spur_end", (3.2, 3.2, 0.4), (ex, ey, top + 0.1 - 0.4), (5, -4, yaw + 30), **SLAB)
    nx.entrance("crystal_stair", (ex, ey, top + 0.1 + 1.6), "", "")
    # 尽头这块斜板也吊着（两根线，往外斜着拉到头顶那块底面的东边上）
    p.chunks.append({"top": (ex, ey, top + 0.1), "near": (ex, ey, top + 0.1), "far": (ex, ey, top + 0.1),
                     "yaw": side_yaw, "span": 3.2})
    return ex, ey, top + 0.1


def above(p):
    """头顶压着的那一整块底面：正对最后一级开着方洞，洞里是更亮的天"""
    nx.into("above")
    gx, gy, gz, yaw = p.marks["top"]
    hole = 6.0
    big = 34.0
    th = 3.0
    # 四块拼成一块中间有洞的大板
    half = big / 2
    for i, (cx, cy, sx, sy) in enumerate((
            (gx, gy + (hole / 2 + half) / 2 + 0, big, half - hole / 2),
            (gx, gy - (hole / 2 + half) / 2, big, half - hole / 2),
            (gx + (hole / 2 + half) / 2, gy, half - hole / 2, hole),
            (gx - (hole / 2 + half) / 2, gy, half - hole / 2, hole))):
        nx.box(f"above_{i}", (sx, sy, th), (cx, cy, TOP_Z), collide=False, **ABOVE)
    # 洞口一圈框
    nx.torus("above_ring", hole * 0.62, 0.25, (gx, gy, TOP_Z - 0.2), major_seg=4, minor_seg=4,
             rot=(0, 0, 45), collide=False, shadow=False, a="white", b="gold", pattern="plain")
    # 去「高处」：最后一级上方，走上去就到
    nx.portal("portal_heights", (gx, gy, gz + 0.9), "isles", mode="walk", radius=0.8)


# ── 吊线 ─────────────────────────────────────────

def anchor(px, py, gx, gy):
    """吊线在头顶那块底面上的挂点：出了边就拉回来；落进中间那个方洞里没有东西可挂，推到洞外"""
    ax = min(max(px, gx - CEIL_HALF + 0.6), gx + CEIL_HALF - 0.6)
    ay = min(max(py, gy - CEIL_HALF + 0.6), gy + CEIL_HALF - 0.6)
    if abs(ax - gx) < HOLE_HALF + 0.5 and abs(ay - gy) < HOLE_HALF + 0.5:
        if abs(ax - gx) > abs(ay - gy):
            ax = gx + math.copysign(HOLE_HALF + 0.5, ax - gx or 1.0)
        else:
            ay = gy + math.copysign(HOLE_HALF + 0.5, ay - gy or 1.0)
        ax = min(max(ax, gx - CEIL_HALF + 0.6), gx + CEIL_HALF - 0.6)
        ay = min(max(ay, gy - CEIL_HALF + 0.6), gy + CEIL_HALF - 0.6)
    return ax, ay


def hang_all(p):
    """给每一块浮着的碎段吊线：从头顶那块底面垂下来，下端插进踏步里一点点。
    有几处（CUT）的线断了：只剩一截垂线吊在踏步上方慢慢晃（会动的得自己一个网格，原点在挂点上）。
    绷着的线合成一个网格（省画次数，也不会互相算穿模）。"""
    nx.into("hang")
    gx, gy = p.marks["top"][0], p.marks["top"][1]
    taut = fu.Kit()
    rnd = random.Random(5)
    for i, c in enumerate(p.chunks):
        cx, cy, cz = c["top"]
        fx, fy = fwd(c["yaw"])
        offs = (-0.35, 0.35) if c["span"] > 1.4 else (0.0,)
        for k, o in enumerate(offs):
            px, py = cx + fy * o, cy - fx * o
            ax, ay = anchor(px, py, gx, gy)
            # 挂点被从底面外头拉回来的（伸出去那条）：几根线顺着边扇开，别挤成一束
            if math.hypot(ax - px, ay - py) > 1.2:
                ay += (cx - gx - CEIL_HALF - 3.0) * 0.6
            # 断了的那两块：线从底面垂到踏步上方两三米就没了，那一截慢慢晃
            if i in CUT:
                drop = TOP_Z - cz - rnd.uniform(2.4, 3.6)
                stub = fu.Kit()
                stub.box((WIRE_T, WIRE_T, drop), (0, 0, -drop))
                obj = stub.build(f"wire_cut_{i}_{k}", loc=(px, py, TOP_Z), smooth=0,
                                 collide=False, shadow=False, **WIRE)
                nx.behave(obj, sway=rnd.uniform(2.0, 3.0))
                continue
            b = (px, py, cz - 0.1)                       # 下端插进踏步里 10cm
            t = (ax, ay, TOP_Z + 0.25)                   # 上端插进头顶那块底面里
            d = (t[0] - b[0], t[1] - b[1], t[2] - b[2])
            taut.box((WIRE_T, WIRE_T, math.sqrt(sum(v * v for v in d))), b, dir_rot(d))
    taut.build("wires", smooth=0, collide=False, shadow=False, **WIRE)


def far():
    """远处雾里的几截别的断梯：斜着、倒着、竖着，不挡人；吊起来 6 截，留 3 截浮着做对比"""
    nx.into("far")
    rnd = random.Random(9)
    extra = []
    for i in range(9):
        a = math.tau * i / 9 + rnd.uniform(-0.2, 0.2)
        r = rnd.uniform(45, 85)
        x, y = BOB_AT[0] + math.cos(a) * r, BOB_AT[1] + math.sin(a) * r
        z = rnd.uniform(-6, 38)
        n = rnd.randint(8, 20)
        s = rnd.uniform(1.4, 3.2)
        rot = (rnd.choice((0, 0, 180, 35, -60)), rnd.uniform(-25, 25), rnd.uniform(0, 360))
        flight_kit(n, RISE * s, RUN * s, W * s, T * s).build(
            f"far_{i}", loc=(x, y, z), rot=rot, smooth=0, collide=False, **FAR)
        if i % 3 != 2:   # 每三截吊两截，剩一截浮着
            extra.append(((x, y, z + n * RISE * s * 0.9), (x, y)))
    hang_all_extra(extra)


def hang_all_extra(extra):
    nx.into("hang")
    k = fu.Kit()
    for (bx, by, bz), (tx, ty) in extra:
        t = (tx, ty, TOP_Z + 16.0)
        d = (t[0] - bx, t[1] - by, t[2] - bz)
        k.box((WIRE_T, WIRE_T, math.sqrt(sum(v * v for v in d))), (bx, by, bz), dir_rot(d))
    k.build("wires_far", smooth=0, collide=False, shadow=False, **WIRE)


def build(extent=EXTENT):
    nx.into("env")
    nx.sun((0.45, -0.55, 0.7))
    # 掉下去：脚底到 −14m 就回家，从家里的书桌前落下来
    nx.atmosphere("plumb", seed=3, fall_to="house", fall_at="stair", fall_y=-14.0)

    page()
    p, over = route()
    under(p, over)
    nx.into("dangle")
    dangling(p)
    plumb()
    crystal_spur(p)
    above(p)
    hang_all(p)
    far()

    nx.into("places")
    x, y, z, yaw = p.marks["spawn"]
    sx, sy = x - fwd(yaw)[0] * 0.4, y - fwd(yaw)[1] * 0.4
    nx.spawn((sx, sy, z), facing_deg=yaw)
    # 从家里的书来，落在出生点（家里 gate_book 的 at 写的是 house）
    nx.arrive("house", (sx, sy, z), facing_deg=yaw)
    for j in p.jumps:
        print("[nx] jump " + ",".join(f"{v:.2f}" for v in j))
    for c in p.chunks:
        print("[nx] chunk " + f"{c['near'][0]:.2f},{c['near'][1]:.2f},{c['near'][2]:.2f} "
              f"span {c['span']:.2f} n {c.get('n', 0)}{' 倒着' if c.get('flip') else ''}")
    for k, v in p.marks.items():
        print(f"[nx] mark {k}: {v[0]:.2f},{v[1]:.2f},{v[2]:.2f} yaw {v[3]:.0f}")


if __name__ == "__main__":
    nx.reset()
    build()
    nx.save_blend("stair-var-1")
    nx.export("stair-var-1")
