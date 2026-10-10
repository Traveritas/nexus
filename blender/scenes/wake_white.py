"""现实 · 原型二：白井。一口几乎纯白的竖井，地面只有十几米宽，井壁却一层层往上，没进雾里看不见顶。
井壁每 6 米一层拱廊（壁柱、拱、檐线），每隔几层伸出一圈回廊；一道螺旋梯贴着井壁爬到第一圈回廊，再往上就没有梯子了。
井顶收成一个圆口，天光直直落下来，在井底落成一个亮的圆，正好罩住床；地上嵌着一道细环，标出光的边。
墙上一扇门，关着，打不开。
床 E「睡」→ 梦里的家。天空：pale（素）。
运行：node scripts/blender.cjs build wake_white，网页 ?world=wake_white
"""
import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import furniture as fu  # noqa: E402
import nx  # noqa: E402
import shapes as sh  # noqa: E402
import wake  # noqa: E402

CENTER = (0, 0)
# 影子里也要是白的：三色明暗只在雾白、白之间走
STONE = dict(a="white", b="mist", pattern="plain", ramp=("mist", "white", "white"))
# 地面暗一档：光落下的圆才分得出来
STONE_T = dict(a="white", b="mist", pattern="tiles", ramp=("lilac_pale", "mist", "white"))
SHADE = dict(a="mist", b="lilac_pale", pattern="plain", ramp=("lilac_pale", "mist", "white"))

R = 8.0          # 井壁内面半径
TIER = 6.0       # 一层拱廊高
TOP = 110.0      # 井口高度（影子相机只看得到人头顶约 120 米以内）
EYE = 3.6        # 井口半径
BAYS = 24
BALCONIES = (12, 30, 48, 66, 84, 102)
STAIR_START = 200.0   # 螺旋梯起步的方位（度）
STAIR_TREAD = 19.0
STAIR_STEPS = 40      # 每级 0.3m，正好到第一圈回廊（12m）


def arcade(z0, z1, k):
    """一层拱廊：壁柱、两柱之间的半圆拱、顶上一道檐线；整层合成一个网格"""
    kit = fu.Kit()
    h = z1 - z0
    bay = 2 * math.pi / BAYS
    half = math.sin(bay / 2) * (R - 0.15)
    spring = z0 + h * 0.62
    for i in range(BAYS):
        a = bay * i
        # 壁柱：贴在井壁上
        kit.box((0.22, 0.42, h - 0.35), (math.cos(a) * (R - 0.1), math.sin(a) * (R - 0.1), z0), rot=(0, 0, math.degrees(a)))
        # 拱：两根壁柱之间
        c = a + bay / 2
        kit.band(half - 0.22, 0.14, 0.16, 0, 180,
                 loc=(math.cos(c) * (R - 0.22), math.sin(c) * (R - 0.22), spring), rot=(0, 0, math.degrees(c)), seg=10)
    kit.build(f"arcade{k}", smooth=0, collide=False, **SHADE)
    sh.tube(f"cornice{k}", R, R - 0.32, 0.35, (0, 0, z1 - 0.35), segments=96, collide=False, **STONE)


def balcony(z, k, gap=None):
    """回廊：一圈伸出来的板，顶面在 z + 0.32；栏杆一根横杆加一圈立柱。gap=(起, 止) 度留给楼梯"""
    start, arc = (0, 360) if gap is None else (gap[1], 360 - (gap[1] - gap[0]))
    # 板底比檐线顶高 2cm：檐线顶、壁柱底都在 z 上，贴着会闪
    sh.tube(f"balcony{k}", R - 0.01, R - 1.5, 0.3, (0, 0, z + 0.02), segments=96, start=start, arc=arc, **STONE)
    z += 0.32
    sh.tube(f"rail{k}", R - 1.38, R - 1.48, 0.07, (0, 0, z + 0.95), segments=96, start=start, arc=arc,
            collide=False, **SHADE)
    kit = fu.Kit()
    n = 48
    for i in range(n + 1 if gap else n):
        a = math.radians(start + arc * i / n)
        kit.box((0.06, 0.06, 0.95), (math.cos(a) * (R - 1.43), math.sin(a) * (R - 1.43), z))
    kit.build(f"rail_posts{k}", smooth=0, **SHADE)


def build(extent=None):
    nx.into("env")
    # 太阳正在头顶：光从井口落到井底正中
    nx.sun((0.003, -0.004, 1.0))
    nx.atmosphere("pale")

    # ── 井底 ──
    nx.into("floor")
    nx.cylinder("floor", R + 1.0, R + 1.0, 1.0, (0, 0, -1.0), segments=96, **STONE_T)
    # 嵌在地上的两道细环：外一道贴着墙脚，里一道标出光落下的圆
    sh.tube("inlay_eye", EYE + 0.06, EYE - 0.06, 0.012, (0, 0, 0), segments=96, collide=False, a="lilac_pale", b="lilac",
            pattern="plain")
    sh.tube("inlay_mid", 5.9, 5.75, 0.012, (0, 0, 0), segments=96, collide=False, a="lilac_pale", b="lilac", pattern="plain")

    # ── 井壁：一整圈，往上 TOP 米；每 6 米一层拱廊 ──
    nx.into("shaft")
    sh.tube("wall", R + 1.0, R, TOP, (0, 0, 0), segments=96, **STONE)
    sh.tube("plinth", R, R - 0.3, 0.5, (0, 0, 0), segments=96, collide=False, **SHADE)
    for k in range(int(TOP // TIER)):
        z0 = 0.5 if k == 0 else k * TIER
        arcade(z0, (k + 1) * TIER, k)
    # 井口：一圈厚檐收成圆口
    sh.tube("crown", R + 1.0, EYE, 1.6, (0, 0, TOP), segments=96, **STONE)
    sh.tube("crown_lip", EYE + 0.5, EYE, 0.6, (0, 0, TOP - 0.6), segments=96, collide=False, **SHADE)

    # ── 回廊与螺旋梯：梯子只到第一圈 ──
    nx.into("balconies")
    a_end = STAIR_START + STAIR_TREAD * STAIR_STEPS
    # 缺口要让开最后一圈梯子：头顶离回廊不到 2m 的那几级都在缺口里
    gap = ((a_end - 140) % 360, (a_end + 2) % 360)
    if gap[1] < gap[0]:
        gap = (gap[0] - 360, gap[1])
    for k, z in enumerate(BALCONIES):
        balcony(z, k, gap if k == 0 else None)
    nx.into("stair")
    sh.spiral_stair("stair", (0, 0), R - 1.45, R - 0.02, 0.3, STAIR_STEPS, STAIR_START, STAIR_TREAD, z0=0.02, **STONE)

    # ── 门：开在井壁上，关着 ──
    nx.into("door")
    da = math.radians(STAIR_START - 40)
    dyaw = math.degrees(da) + 90
    g = nx.group("door", (math.cos(da) * (R - 0.05), math.sin(da) * (R - 0.05), 0), (0, 0, dyaw))
    for s in (-1, 1):
        nx.box(f"door_jamb{s}", (0.16, 0.24, 2.3), (s * 0.58, 0, 0), parent=g, **STONE)
    nx.box("door_head", (1.32, 0.24, 0.16), (0, 0, 2.3), parent=g, **STONE)
    nx.box("door_leaf", (1.0, 0.1, 2.28), (0, -0.04, 0.01), parent=g, a="mist", b="lilac_pale", pattern="tiles")
    nx.box("door_knob", (0.06, 0.1, 0.06), (0.36, 0.08, 1.0), parent=g, collide=False, a="pink_pale", b="white", pattern="plain")

    # ── 床与床边几样：在光里 ──
    nx.into("bed")
    fu.bed("bed", (0, 0.2, 0), 0)
    wake.nightstand("stand", (-1.35, 0.95, 0), 0)
    fu.table_lamp("lamp", (-1.42, 0.96, 0.52), 0)
    fu.alarm_clock("clock", (-1.2, 0.86, 0.52), -20)
    fu.chair("chair", (1.9, -1.4, 0), 150, kind="dining", fabric="white")
    fu.notebook("book", (1.55, 0.95, 0), 30)
    nx.portal("portal_bed", (0, 0.2, 0.8), "home", at="wake", mode="key", title="睡", radius=1.3)
    land = (1.6, 0.0, 0)
    nx.arrive("home", land, facing_deg=-120)
    nx.spawn(land, facing_deg=-120)


if __name__ == "__main__":
    nx.reset()
    build()
    nx.save_blend("wake_white")
    nx.export("wake_white")
