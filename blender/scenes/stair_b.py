"""浅梦 · 断梯 · 那边（stair_b）：断梯的上半座——穿过缝以后继续往上。

和 `stair`（下半）共用 `blender/scenes/stair.py` 里的几何与那道门（`door_common`）：
- 门洞两边一模一样，透过缝看见的是下半那座自己（走过去不转场）；回头能看见自己刚爬过的那一跑。
- 这一半越往上踏步越大（0.30 → 0.42 → 0.55 → 0.70），最后几级是**巨踏步**（每级高 0.85、比人还高），
  要跳上去；旁边并排浮着一座只到脚踝的迷你楼梯，一直通到很远。
- 回家：掉下去脚底到 −14m 就去家里书桌前（到达点 `stair`），和下半那座一样。
- 顶上去「高处」：最后一级上方 `portal_heights`（暂指云阶 `isles`）。晶体在这半的一条岔路尽头。

运行：node scripts/blender.cjs build stair_b，网页 ?world=stair_b
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import furniture as fu  # noqa: E402
import nx  # noqa: E402
import stair  # noqa: E402
from stair import helix_chain, build_helix, chunk_kit, fwd  # noqa: E402
from stair import SLAB, GLOW  # noqa: E402

EXTENT = 170
CENTER = (0, 0)

GIANT = dict(ramp=("violet_deep", "violet", "lilac_dark"), top="mist", pattern="tiles")
SPUR = dict(ramp=("lilac_dark", "lilac", "lilac_pale"), top="pink_pale", pattern="plain")
MINI = dict(ramp=("lilac_dark", "lilac", "lilac_pale"), pattern="plain")
REST = dict(ramp=("lilac_dark", "lilac", "lilac_pale"), top="mist", pattern="tiles")

UP_SEGS = [(16, 0.30, 0.80), (10, 0.42, 0.85), (8, 0.55, 0.90), (6, 0.70, 0.92)]
UP_W = [2.7, 3.2, 3.8, 4.6]          # 每段踏步多宽（越往上越大）
UP_DR = 0.035


def upper_route(dry=False):
    """门 → 休息平台。返回 (steps, runs, jumps, marks)"""
    _, _, a_end, _, z_end = stair.lower_geom()
    a2 = a_end + stair.LAND_ARC
    steps, runs, a3, r3, z3 = helix_chain(0, 0, a2, stair.LO_R, z_end, UP_SEGS, dr=UP_DR)
    widths = [UP_W[0]] * UP_SEGS[0][0] + [UP_W[1]] * UP_SEGS[1][0] + [UP_W[2]] * UP_SEGS[2][0] + [UP_W[3]] * UP_SEGS[3][0]
    skip = {8: 1, 20: 1}                 # 两处断口（再往上踏步太高，不再断）
    jumps = build_helix("up", steps, runs, widths=widths, skip=skip, group=4, seed=7, dry=dry)
    marks = dict(end=steps[-1])
    return steps, runs, jumps, marks


def rest_platform(x, y, z, yaw, dry=False):
    """螺旋尽头一块宽的休息平台：晶体的岔路从这里出去，巨踏步也从这里起"""
    fx, fy = fwd(yaw)
    cx, cy = x + fx * 2.4, y + fy * 2.4
    if not dry:
        nx.into("rest")
        nx.box("rest_land", (7.2, 4.6, 0.7), (cx, cy, z - 0.702), (0, 0, yaw), **REST)
        for s in (-1, 1):
            k = fu.Kit()
            k.box((0.22, 0.22, 1.6), (s * 3.4, -1.8, 0))
            k.build(f"rest_post_{s + 1}", loc=(cx, cy, z + 0.1), rot=(0, 0, yaw + s * 6), smooth=0, collide=False,
                    a="rose_deep", b="rose", pattern="plain")
    return (cx, cy, z, yaw), (x + fx * 4.7, y + fy * 4.7, z, yaw)


def giant_flight(x, y, z, yaw, n, rise=0.82, run=2.2, w=6.4, gap=0.5, th=2.5, dry=False):
    """巨踏步：一块比人还高的厚板，顶面比前一块高 rise，中间留 gap（要跳上去）"""
    jumps = []
    fx, fy = fwd(yaw)
    rnd = random.Random(int(x * 5 + y * 7) & 0xffff)
    for i in range(n):
        jumps.append((x, y, z, yaw, gap, rise))
        x, y, z = x + fx * gap, y + fy * gap, z + rise
        cx, cy = x + fx * run / 2, y + fy * run / 2
        if not dry:
            nx.box(f"giant_{i}", (w, run, th), (cx, cy, z - th), (0, 0, yaw + rnd.uniform(-3, 3)), **GIANT)
        x, y = x + fx * run, y + fy * run
    return jumps, (x, y, z, yaw)


def crystal_spur(x, y, z, yaw, dry=False):
    """休息平台一侧伸出去的一条岔路（一级级的碎踏步，一级比一级高一点、转一点），尽头一块斜板上浮着晶体"""
    nx.into("spur")
    fx, fy = fwd(yaw)
    sx, sy = fy, -fx                     # 右手边（远离中心）
    side_yaw = yaw - 90
    span, gap, rise = 1.9, 0.8, 0.30
    edge = 3.6
    jumps = []
    for i in range(4):
        top = z + rise * (i + 1)
        jumps.append((x + sx * edge, y + sy * edge, top, side_yaw, gap, rise))
        c = edge + span / 2
        if not dry:
            # 一块碎下来的踏步（单级，锯齿侧面、斜底），顶面正好在 top
            chunk_kit(1, span, span, t=0.4, step_rise=rise).build(
                f"spur_{i}", loc=(x + sx * c, y + sy * c, top - rise), rot=(0, 0 if i % 2 else 2, side_yaw + 3 * i),
                smooth=0, **SPUR)
        edge += span + gap
    jumps.append((x + sx * edge, y + sy * edge, z + rise * 4, side_yaw, gap, 0.1))
    c = edge + gap + 1.8
    ex, ey = x + sx * c, y + sy * c
    if not dry:
        nx.box("spur_end", (3.6, 3.6, 0.5), (ex, ey, z + rise * 4 + 0.1 - 0.5), (6, -5, yaw + 34), **SLAB)
        nx.entrance("crystal_stair", (ex, ey, z + rise * 4 + 0.1 + 1.6), "", "")
    return jumps


def mini():
    """旁边并排浮着的一座迷你楼梯：只到脚踝，绕着主楼梯外面再盘一圈、慢慢往外飘远"""
    nx.into("mini")
    steps, runs, _, _, _ = helix_chain(0, 0, -50.0, 9.2, 4.0, [(132, 0.15, 0.50)], dr=0.055)
    for g in range(6):
        k = fu.Kit()
        for i in range(g * 22, min(len(steps), (g + 1) * 22)):
            x, y, z, yaw = steps[i]
            k.box((1.0, 0.64, 0.12), (x, y, z - 0.12), (0, 0, yaw))
        k.build(f"mini_stair_{g}", loc=(0, 0, 0), rot=(0, 0, 0), smooth=0, collide=False, **MINI)


def build(extent=EXTENT):
    nx.into("env")
    nx.sun((0.45, -0.55, 0.7))
    nx.atmosphere("halo", fall_to="house", fall_at="stair", fall_y=-14.0)

    ax, ay, az, ayaw = stair.door_pose()
    stair.door_common("stair", ayaw + 180.0)

    steps, runs, jumps, marks = upper_route()
    ex, ey, ez, eyaw = marks["end"]
    center, far = rest_platform(ex, ey, ez, eyaw)
    jumps += crystal_spur(center[0], center[1], center[2], eyaw)
    gj, top = giant_flight(far[0], far[1], far[2] + 0.3, eyaw, 6)
    jumps += gj

    nx.into("top")
    tx, ty, tz, tyaw = top
    fx, fy = fwd(tyaw)
    lx, ly = tx + fx * 1.6, ty + fy * 1.6
    nx.box("last_step", (3.2, 3.2, 0.14), (lx, ly, tz - 0.14), (0, 0, tyaw), collide=True, shadow=False, **GLOW)
    nx.portal("portal_heights", (lx, ly, tz + 0.9), "isles", mode="walk", radius=0.9)
    nx.into("echo")
    nx.box("echo_page_l", (7.0, 13.6, 0.5), (-3.7, 2.0, 42.0), (16, 0, 24), **stair.PAGE)
    nx.box("echo_page_r", (7.0, 13.6, 0.5), (3.7, 2.0, 42.0), (16, 0, 24), **stair.PAGE)
    nx.box("echo_gutter", (0.4, 13.6, 0.5), (0, 2.0, 41.8), (16, 0, 24), **stair.GUTTER)
    mini()

    nx.into("places")
    nx.spawn((ax, ay, az), facing_deg=ayaw + 180.0)   # 直接进 stair_b 时，面朝上行的那一跑
    for j in jumps:
        print("[nx] jump " + ",".join(f"{v:.2f}" for v in j))
    for k, v in marks.items():
        print(f"[nx] mark {k}: {v[0]:.2f},{v[1]:.2f},{v[2]:.2f} yaw {v[3]:.0f}")
    print(f"[nx] rest {center[0]:.2f},{center[1]:.2f},{center[2]:.2f}  giant top {tx:.2f},{ty:.2f},{tz:.2f} yaw {tyaw:.0f}")


if __name__ == "__main__":
    nx.reset()
    build()
    nx.save_blend("stair_b")
    nx.export("stair_b")
