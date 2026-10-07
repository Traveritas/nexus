# 用 Blender 搭 NEXUS 场景

场景在 Blender 里搭，导出 GLB，网页读进来后按物体上的自定义属性（`nx_*`）装配。
**风格由渲染管线统一产生**：Blender 里只管轮廓、尺度和摆放，不做材质、不贴图、不打光（太阳除外）。白模正合适。

## 工作流

| 做什么 | 命令 |
|---|---|
| 用脚本从零搭一个场景 | `node scripts/blender.cjs build <名字>` → 运行 `blender/scenes/<名字>.py`，存 `blender/<名字>.blend` 并导出 `public/scenes/<名字>.glb` |
| 手动改过 .blend 后导出 | `node scripts/blender.cjs export <名字>` |
| 在网页里看 | `npm run dev`，地址加 `?scene=<名字>`（默认 `slice`） |
| 截图 / 走一遍 | `npm run build` 后 `node scripts/shot.cjs`、`node scripts/walk.cjs` |

- Blender：`D:/Steam/steamapps/common/Blender/blender.exe`（5.2 LTS），无界面运行；路径可用环境变量 `BLENDER` 覆盖。
- 开发服务器开着时，`public/scenes`、`public/sprites` 一变就整页刷新，人留在原地。
- 也可以通过 Blender MCP 在打开的 Blender 里直接搭，搭完照常 `save` 再 `export`。MCP 要求 Blender 里的插件在运行。
- 场景脚本统一用 `blender/nx.py` 的函数（`box` `cylinder` `torus` `plane` `group` `spawn` `entrance` `sprite` `sky_sprite` `sun`），它们会顺手写好属性。参考 `blender/scenes/slice.py`。
- **脚本是唯一来源**：用脚本搭的场景，改动写回脚本再 build。直接在 .blend 里手改的，以后就只 export，不再 build，否则手改的内容会被覆盖。

## 坐标与尺度

- Blender：Z 朝上，单位米。导出后 Blender (x, y, z) → three (x, z, −y)。绕竖轴的角度两边一致。
- 空物体的「朝向」是它本地的 **+Y**。
- 物体可以有缩放（包括非等比），不用 Apply。纹素格在世界空间里按每米 16 格铺，不随物体缩放。
- 颜色、纹样只看属性，Blender 里的材质会被忽略（导出时也不带）。

## 行走尺度（搭关卡时对照）

| 项 | 数值 |
|---|---|
| 人 | 胶囊半径 0.3m、高 1.7m，眼高 1.6m |
| 自动迈上 | ≤ 0.35m 的坎（楼梯每级 ≤ 0.3m 最稳） |
| 跳 | 最高约 1.18m；0.9m 的台子稳上，1.0m 以上要准，1.15m 以上基本上不去 |
| 跳远（平地起落） | 走着跳约 2m，快走（Shift）约 3.9m |
| 门洞 | 宽 ≥ 0.8m，高 ≥ 1.9m |
| 走动范围 | 以碰撞为准；掉到 −40m 以下回到出生点 |

入口不要放在需要跳的地方。

## 物体属性表

### 网格（默认：像素哑光、参与碰撞、投影）

| 属性 | 值 | 默认 | 说明 |
|---|---|---|---|
| `nx_mat` | `matte` / `asset` / `collider` / `none` | `matte` | `asset`＝现成模型，用它自己的底色贴图（见下「现成模型」）；`collider`＝看不见只挡人；`none`＝不导入 |
| `nx_tint` | 0..1 | 0 | 只对 `asset`：把贴图的明暗映射到 `nx_pal` 两色（亮＝主色、暗＝副色）的程度 |
| `nx_smooth` | 0 / 1 | 0 | 只对 `asset`：1 ＝ 平滑受光，0 ＝ 与像素哑光一样的三档 |
| `nx_pal` | `"主,副"` 色板编号 | `"5,4"` | 副色用在纹样与颗粒上；只写一个数＝主副同色 |
| `nx_pattern` | 0 颗粒 · 1 一米方砖 · 2 横纹（每 0.5m） · 3 竖条 · 4 素面 | 0 | |
| `nx_collide` | 0 / 1 | 1 | |
| `nx_shadow` | 0 / 1 | 1 | 是否投影（接收影子总是开的） |
| `nx_spin` | 度/秒 | 0 | 绕竖轴自转；会动的物体不参与碰撞 |
| `nx_bob` | 米 | 0 | 上下浮动幅度 |
| `nx_face` | 0 / 1 | 0 | 永远正面朝人（只绕竖轴转） |

描边按「物体」区分：分开的物体之间有轮廓线；想让几块零件之间也勾线就分开建，不想要就 Join。

### 空物体（`nx_type`）

| `nx_type` | 其他属性 | 说明 |
|---|---|---|
| `spawn` | — | 出生点，位置是脚底，朝向是 +Y。只放一个 |
| `entrance` | `nx_url` 目标地址、`nx_title` 走近时显示的名字、`nx_size` 晶体尺寸（默认 0.32，外接半径 ≈ 2.236×） | 晶体中心放在**可站立的地面以上约 1.6m**，四周留出能走进去的空地。走近时周围一路解析到底，眼睛进入晶体约 0.9 倍半径即跳转（当前标签页）。`nx_url` 为空＝只是一枚晶体 |
| `sprite` | `nx_sprite` 图名、`nx_face`（默认 1）、`nx_shadow`（默认 1）、`nx_back` 背面色号（默认 6） | 纸片。位置是图的底边中点；尺寸＝图的像素 ÷ 16（米） |
| `sky` | `nx_sprite`、`nx_size` 宽度（米，默认 20） | 天上的纸片：只取「原点 → 空物体」的方向，永远在 180m 外、正面朝人 |
| `atmosphere` | `nx_sky` 主题名，可带种子 `名字:种子`（默认 `blank`） | 天空主题，连带雾色与天光一起换；位置无所谓，一个场景放一个。主题见 [sky.md](sky.md)，`nx.atmosphere("halo")`、`nx.atmosphere("dye", seed=7)` |

### 太阳

放一盏 **Sun** 灯，它照射的方向就是阳光方向。只认第一盏；强度、颜色都不用。

## 总图（atlas）：把各个场景放在一起看

`blender/scenes/atlas.py` 把各个场景当作浮岛摆成一圈，中间一块圆台，各有一座桥修到该场景原来的出生点。只为查看、对比，不是正式场景。

- 构建：先分别 build 各个场景（可选），再 `node scripts/blender.cjs build atlas`；网页 `?scene=atlas`，可加 `&sky=<主题>` 对比天空。
- 圆台上有一圈小晶体，名字就是岛名，走进去直接跳到那个岛的出生点（桥很长，这是捷径）。构建时也会打印每个岛的 `?pos=…&yaw=…`。
- 加一个场景：在 `ZONES` 里加一行（脚本名、显示名、方位角、离中心的距离、岛的边长）。构建时会检查岛与岛有没有叠在一起，叠了就报错。
- 被收进来的场景脚本要这样写（参考 `idea_shoal.py`）：内容放在 `build(extent)` 里；模块里写 `CENTER = (x, y)`（内容的大致中心），地面以 `CENTER` 为中心、边长用 `extent`；末尾 `if __name__ == "__main__":` 里 `reset → build → save_blend → export`，单独 build 时照旧。
- 收进总图时，场景里的 `spawn` 变成路标（`nx_type=waypoint`，网页不认），`sun`、`sky_sprite`、`atmosphere` 不生效，用总图自己的。
- 岛之间是空的，掉下去会回到中心台（出生点）。

## 预制件（`blender/prefabs.py`）

可以在各主题之间反复使用的构件族，每族几种变体、带随机种子；`?scene=prefab_gallery` 是全部预制件与纸片的陈列。
**现实物（灯、椅、窗帘、电话、杯……）不建模，用纸片**；立体的只做建筑尺度的抽象形。

| 族 | 函数 | 变体 |
|---|---|---|
| 花之装置 | `bloom(kind=…)` | `rosette` 一圈张开的瓣板 · `lotus` 三层瓣板坐在环台上 · `blade` 几片竖直扭转的长板 · `halo` 瓣板沿竖直的圆排开（花形的门）· `drift` 浮着转的散瓣 |
| 花形的门 | `halo_gate` | halo + 直梯 + 穿过圆心的平台，返回入口坐标 |
| 框 | `frame(kind=…)`、`procession` | `door` `window` `square` `arch`；一串尺寸、颜色、侧倾渐变的框 |
| 阶 | `stair_straight`、`stair_spiral`、`steps_between` | 直梯（实心/悬空）、螺旋梯（顶上是开口的扇形平台，走得上去）、两点间的悬空踏步 |
| 环 | `halo`、`orrery`、`arch_ring` | 平躺/倾斜的环（可转）、一组共心转动的环、立着的残环 |
| 碑与塔 | `monolith`、`tower_broken`、`plate_stack` | 方碑、断开错位的塔、一摞错开的薄板（可当台阶） |
| 台 | `island`、`pad`、`plinth` | 下面收尖的浮岛、缺口圆台、低矮方台 |
| 器 | `vessel(lying=…)` | 横躺（走得进去，返回杯里的站立点）/ 立着的杯 |
| 纸片撒布 | `paper_scatter`、`paper_ring` | 环带里随机撒（可避让）、沿圆固定朝向排开（朝里/朝外） |

基本形 `plate`（两头尖的板）和 `shapes.py` 里的 `tube`（管/扇/缺口环）、`spiral_stair` 也可以直接用。

## 色板（`nx_pal` 用编号；`nx.py` 里也可以用名字）

| 号 | 名字 | 色值 | | 号 | 名字 | 色值 |
|---|---|---|---|---|---|---|
| 0 | ink | `#1d1a2b` | | 8 | rose_deep | `#6e4f66` |
| 1 | violet_deep | `#3a3350` | | 9 | rose | `#a8798c` |
| 2 | violet | `#5c5378` | | 10 | pink | `#d9aab5` |
| 3 | lilac_dark | `#82799e` | | 11 | pink_pale | `#f3d6d6` |
| 4 | lilac | `#a8a1bf` | | 12 | blue | `#8fa3c7` |
| 5 | lilac_pale | `#cdc8db` | | 13 | blue_pale | `#c3d1e6` |
| 6 | mist | `#ece9f2` | | 14 | gold | `#ead7a0` |
| 7 | white | `#fbf9f7` | | 15 | green | `#86b5a5` |

受光会让颜色变暗，最终都量化回这 16 色。大面积的结构用冷紫一列，粉一列表达温度，金、绿、蓝只做点缀。

## 纸片的图

- **程序化的自然物**（`src/proc.ts`）：名字写成 `族[.变体][:种子]`，同一个名字永远是同一张图；不写变体按种子挑，不写种子是 1。
  - `tree`：`round` `tall` `weep` `pine` `bare` `blossom` `tuft`（5~8m）
  - `cloud`：`heap` 落地的积云 · `flat` 层云 · `wisp` 丝缕 · `puff` 小团（适合浮着）
  - `star`：`dot` `glow` `diamond` `cluster` `ring`（≤1m，适合 `nx_bob` 浮着）
  - `grass`：`clump` `flowered` `reed` · `bush`（灌木）
  - `flower`：`cup` `star` `bell` `umbel` `puff`（1.7~4m）
  - 例：`tree.pine:3`、`cloud:12`、`star.cluster:5`。撒一片时用 `prefabs.paper_scatter`，名字里写 `{}`（如 `"tree:{}"`）就每张一个种子。
  - 画法：一组圆的并集当体积，按球面法线左上受光，4×4 Bayer 抖动落到 3~4 色的色阶上；轮廓交给管线描边。改画法只改 `proc.ts`，所有场景跟着变。
  - 旧名字仍然可用，指向程序化的默认款：`flower` `grass1`~`grass3` `lily` `reed` `puff` `sparkle`。陈列：`?scene=proc_gallery`。
- **真实贴图的剪纸**：纸片也可以是照片或渲染图。文件名写成 `<名字>@<每米像素>.png`（如 `chair_wood@64.png`），尺寸按这个密度算，用 mip 链采样；像素化、落色板、描边照旧由管线做。
  - 从现成模型渲：`node scripts/cutout.cjs <PolyHaven id> --name 名字 --height 米 [--yaw 度] [--tilt 俯角] [--ppm 64] [--part n]`。正交正面、透明底，自动补掉叶缝里的碎孔、透明度切成全有或全无（需要 ImageMagick）。花草模型常是一排并排的变体，用 `--part 0/1/2…` 取一个。大树原始模型可能几百 MB，但只在渲图时用，产物只是一张小 PNG。
  - 也可以直接放自己的照片抠图（透明底 PNG），按上面的名字规则写上每米像素。
  - 现有：`chair_wood@64` `armchair_real@64` `clock_real@64` `lamp_real@64` `desklamp_real@64` `vase_real@64` `plant_pot@40`；花草 `fern` `gazania` `heliophila` `ursinia` `nettle` `iceplant` `weed` `weed_b` `periwinkle`（都是 `@32`）；树 `quiver@32` `quiver_b@32` `tree_island@32` `tree_island_b@32`。陈列：`?scene=cutout_gallery`。
- **剪纸的现实物**（`src/paper.ts`）：`lamp_street` `lamp_floor` `pendant`（图的底边是灯罩下沿，挂在高处）`chair` `window`（玻璃镂空）`door` `cup` `phone`。想要真实的造型时，改用现成模型（下一节）。
- `moon`：天上的纸月（`sky_sprite` 用）。
- 纸片不跟人转（`face=False`）时，**正面朝空物体本地的 -Y**；背面是空白的纸（`nx_back` 色）——背过身的椅子就只剩一张白纸。
- 新图放 `public/sprites/<名字>.png`：**每米 16 像素**画，透明背景，透明度只有全有或全无，颜色尽量取色板里的。
- 一张图的底边就是地面。

## 现成模型（`nx_mat=asset`）

不一定要纯像素白模：现成的模型保留自己的造型与贴图，受光、影子、雾、晶体光与像素哑光同一套，**像素化、落色板、描边由管线统一做**——等于套了一层风格化滤镜。

1. 取模型（Poly Haven，CC0）：`node scripts/fetch-asset.cjs <id>`，存到 `assets/polyhaven/<id>/`（附 LICENSE.txt）；`--list 关键词` 查 id。
2. 场景脚本里：`import assets as at`，`at.asset("名字", "<id>", (x, y, z), rot=(0, 0, 度), height=米, tint=0..1, a="色", b="色", smooth=False)`。
   - 导入时只留底色贴图（和透明度），缩到 512；同一个模型只导入一次，之后共用网格与贴图（GLB 里只存一份）。
   - `height` 直接给高度（放大到建筑尺度就写大数）；`tint` 把贴图明暗拉向色板两色，让外来的东西融进来。
3. 注意体积：带复杂植被的模型可能很大（jacaranda_tree 原始 200MB），先看 `du -sh assets/polyhaven/<id>`。
陈列：`?scene=asset_gallery`（同一件东西：原色 · 染色 · 放大）。

## 搭场景时的检查清单

- [ ] 有且只有一个 `spawn`，脚底贴着能站的面
- [ ] 每个入口在地面以上约 1.6m，四周走得进去，不需要跳
- [ ] 楼梯每级 ≤ 0.3m；需要跳的高差 ≤ 0.9m
- [ ] 门洞、通道不窄于 0.8m
- [ ] 没有细于约 0.1m 的长物件（远处会闪）；细节交给纸片
- [ ] 跑一遍 `node scripts/walk.cjs`（换场景时要改脚本里的坐标），再截几张图看
