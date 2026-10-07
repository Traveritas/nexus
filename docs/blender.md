# 用 Blender 搭 NEXUS 场景

场景在 Blender 里搭，导出 GLB，网页读进来后按物体上的自定义属性（`nx_*`）装配。
**风格由渲染管线统一产生**：Blender 里只管轮廓、尺度和摆放，不做材质、不贴图、不打光（太阳除外）。白模正合适。

## 工作流

| 做什么 | 命令 |
|---|---|
| 用脚本从零搭一个场景 | `node scripts/blender.cjs build <名字>` → 运行 `blender/scenes/<名字>.py`，存 `blender/<名字>.blend` 并导出 `public/scenes/<名字>.glb` |
| 手动改过 .blend 后导出 | `node scripts/blender.cjs export <名字>` |
| 查穿模 | `node scripts/blender.cjs clip <名字> [前缀 …]`：家具和墙、窗、别的家具有没有相交；场景里直接搭的东西用前缀算成一件（如 `bed_ wardrobe`） |
| 查共面（闪） | `node scripts/blender.cjs zfight <名字>`：不同物体的两个面贴在同一平面、朝向相同又有重叠，网页里材质和轮廓会来回闪；埋在别的物体里看不见的不算 |
| 在网页里看 | `npm run dev`，地址加 `?world=<名字>`（默认 `home`；`?scene=` 是旧写法，同义） |
| 截图 / 走一遍 | `npm run build` 后 `node scripts/shot.cjs`、`node scripts/walk.cjs`；`node scripts/travel.cjs` 把所有世界的所有传送物各走一遍 |

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
| `nx_mat` | `matte` / `asset` / `veil` / `collider` / `none` | `matte` | `asset`＝现成模型，用它自己的底色贴图（见下「现成模型」）；`veil`＝传送物洞口里的膜（一片竖着的面，`nx_size` 是「宽,高」，`nx_pal` 两色；远处不显，走近才铺满；不挡人、不投影，用 `nx.veil(...)`）；`collider`＝看不见只挡人；`none`＝不导入 |
| `nx_tint` | 0..1 | 0 | 只对 `asset`：把贴图的明暗映射到 `nx_pal` 两色（亮＝主色、暗＝副色）的程度 |
| `nx_smooth` | 0 / 1 | 0 | 只对 `asset`：1 ＝ 平滑受光，0 ＝ 与像素哑光一样的三档 |
| `nx_pal` | `"主,副"` 色板编号 | `"5,4"` | 副色用在纹样与颗粒上；只写一个数＝主副同色 |
| `nx_pattern` | 0 颗粒 · 1 一米方砖 · 2 横纹（每 0.5m） · 3 竖条 · 4 素面 | 0 | 除素面外都叠一层约 1.5m 的大色斑与成团颗粒；方砖、横纹、竖条每块/每条各有色偏，横纹在侧面按不等长断开成木板 |
| `nx_ramp` | `"暗,中,亮"` 色板编号 | 无 | 三色明暗：三档受光直接取这三色（可跨色相，暗偏冷、亮偏暖），纹样往暗处挪半档（棋盘抖动）或一档；给了就不用 `nx_pal`。没给时，网页的「自动三色」按主色从 `palette.ts` 的 `AUTO_RAMP` 配一组，与主色乘光照按总强度混（键 6：0.3 → 0.5 → 1 → 0，默认 0.3；或 `?ramp=0..1`） |
| `nx_top` | 色板编号 | 无 | 顶面色：朝上的面整片用它，并沿侧面上沿垂下 1–4 格参差的边（草皮、积雪、桌布） |
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
| `portal` | `nx_to` 目标世界、`nx_at` 到达点名（空＝出生点）、`nx_mode` `walk`/`key`、`nx_title` 提示、`nx_radius`（默认 0.9） | 传送物：去另一个世界。`walk` 走进半径内就走（衣柜、落地窗，洞口里要有膜），`key` 走近按 E（杯、床、灯、书、花），提示是「E · 标题」。一般不直接写，用 `prefabs.gate_*`（见「世界」） |
| `arrive` | `nx_name` 名字 | 到达点：别的世界传送过来落在这里，位置是脚底、朝向 +Y。别放在走进型传送物的范围里（站在里面也不会被立刻带走，但要先走出来）。`nx.arrive(...)` |
| `atmosphere` | `nx_sky` 主题名，可带种子 `名字:种子`（默认 `blank`） | 天空主题，连带雾色与天光一起换；位置无所谓，一个场景放一个。主题见 [sky.md](sky.md)，`nx.atmosphere("halo")`、`nx.atmosphere("dye", seed=7)` |

### 太阳

放一盏 **Sun** 灯，它照射的方向就是阳光方向。只认第一盏；强度、颜色都不用。

## 世界（world）

NEXUS 是一组世界，像《梦日记》：**家**（`home`）是起点，醒来在床边；世界之间靠**传送物**来往，有的世界里有**晶体**通往真实的站点。

**连接的规矩**

- **一个世界一样东西**：去哪个世界，碰的就是那个世界的东西，家里和别的世界里认得出是同一样（形态可以变，大小、立着躺着都行）：

  | 去 | 东西 | 怎么进 | 预制件 |
  |---|---|---|---|
  | 家 | 灯 | E「关灯」 | `gate_home`（路灯）；无墙之屋里是楼板上的纸吊灯 |
  | 回廊 | 摊开的书 | E「翻开」 | `gate_book`（书台） |
  | 下沉 | 床 | E「睡」 | `gate_bed`（`furniture.bed`） |
  | 无墙之屋 | 衣柜 | 走进去（拨开衣服） | `gate_wardrobe` / `wardrobe` |
  | 花房 | 插着花的瓶 | E「凑近」 | `gate_vase` |
  | 浅滩 | 一杯水 | E「一杯水」 | `gate_glass`（立着）/ `gate_vessel`（横躺的大杯，走进杯里） |
  | 云阶 | 落地窗 | 走出去 | `gate_window` |

- **少用门**：只有衣柜和落地窗是走进去的，其余都是走近按 E。走进去的洞口里有一层**膜**（`nx.veil`，`nx_mat=veil`）：远处没有，走近时从洞口中心长出来铺满，颜色是要去的世界的（`prefabs.VEIL`）。
- **来回成对**：A 里通往 B 的东西正前方，就是从 B 回来时落脚的地方（背对着它）。所以到达点按「从哪个世界来」命名，传送物的 `nx_at` 写自己世界的名字。`gate_*` 一次放好三样：东西、传送物（`to`，`at=here`）、到达点（名字 `to`）。
- **不在空地上传送**：每个传送物都落在一样看得见的东西上。
- **出入口宜少**（传送物 + 通往站点的晶体，家除外）：两个是常态（回家的灯 + 一处别的）；一个就是只能原路回去的死胡同，可以有；三个算多；四个是小枢纽，至多一两处。没用的门框、窗框可以当布景留着。
- 从家里来落在灯前：`gate_home` 默认把出生点也放在那里。

写一个世界：`blender/scenes/<名字>.py` 导出 `public/scenes/<名字>.glb`，写法同其他场景（`build(extent)` + `CENTER`），外加 `nx.atmosphere(...)`、一个 `pf.gate_home("<名字>", 位置, 朝向)`，和通往别处的 `pf.gate_*("<名字>", 位置, 朝向)`（东西的正面朝本地 +Y，人从正面来）。对面的世界里也要放一个通回来的。

- 转场：格子一路变粗到 32px、蒙上雾色，新世界加载好以后再一格格解析出来；转场时相邻世界会被预先取到浏览器缓存。
- 存档：去过哪些世界记在 localStorage（`nexus:visited`），将来做地图用。浏览器后退 / 前进在世界之间来回。
- 键：**E** 互动（按键型传送物）· **Q** 醒来（回家，落在床边）。
- 新世界接进网络后，跑 `npm run build && node scripts/travel.cjs`：它把每个世界的每个传送物都走一遍，检查到达的世界和到达点、落脚处跟前是不是回去的那个、出入口有没有超过四个。

当前的连接（★ 是晶体）。每条都是双向的；世界之间只有两对（回廊—云阶、花房—浅滩），其余都经过家：

| 世界 | 出入口 |
|---|---|
| 家 | 床 → 下沉 · 落地窗 → 云阶 · 衣柜 → 无墙之屋 · 书房桌上的书 → 回廊 · 边几上的花瓶 → 花房 · 餐桌上一杯水 → 浅滩 |
| 回廊 | 出生点背后的路灯 → 家 · 小院里的落地窗 → 云阶 · ★ 尽头花形门 → 博客 |
| 云阶 | 出生岛的路灯 → 家 · 顶岛的书 → 回廊 |
| 花房 | 门前的路灯 → 家 · 东侧横躺的杯 → 浅滩 |
| 浅滩 | 圆叶上的路灯 → 家 · 洒出的水边的花瓶 → 花房 |
| 下沉 | 井口的路灯 → 家 · ★ 螺旋梯顶 → GitHub |
| 无墙之屋 | 楼板上的纸吊灯 → 家（死胡同：只从家里的衣柜进来） |

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
建筑尺度的抽象形在这里；家具、器物这类现实物见下一节「家具与器物」。

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
| 世界之间 | `gate_home` `gate_book` `gate_bed` `gate_wardrobe` `gate_vase` `gate_glass` `gate_vessel` `gate_window`、`wardrobe` | 通往各个世界的东西，连同传送物与回来的到达点（见「世界」） |
| 纸片撒布 | `paper_scatter`、`paper_ring` | 环带里随机撒（可避让）、沿圆固定朝向排开（朝里/朝外） |

基本形 `plate`（两头尖的板）和 `shapes.py` 里的 `tube`（管/扇/缺口环）、`spiral_stair` 也可以直接用。

## 家具与器物（`blender/furniture.py`）

现实物用自己的低面数构件，**不用现成模型、不贴图**，颜色只走 `nx_pal` + `nx_pattern`，和白模世界同一套语言。

- **造型语言**：倒角方块、8~10 边的车床回转体（留着棱）、两头尖的叶板；比例略粗壮，腿不细于 5~6cm；每件只留一个认得出的特征。
- **面数预算**：普通家具 ≤ 200 三角形，传送物 ≤ 500；一个世界的全部家具加起来以千计，不以万计。
- **分件**：同一件东西里同色的零件合成一个物体（不勾线），不同色的分开（有轮廓线）。写法见 `Kit` / `Piece`。
- **朝向**：本地 +Y 是正面（坐下时脸朝的方向、钟面朝的方向），`loc` 是底面中心；`yaw` 同 `spawn`。
- **颜色**：金色只做大面积受光的东西；小零件背光时会被量化成绿色，所以「金属」用浅粉（`BRASS`），灯的亮面用白（`GLOW`）。

| 族 | 函数 | 变体 |
|---|---|---|
| 椅 | `chair(kind=…, fabric=…)` | `dining` 餐椅 · `arm` 扶手沙发椅 · `lounge` 低躺椅 · `rocking` 摇椅；`fabric` 取 `blue` `pink` `lilac` `rose` `white` |
| 凳 | `bench` | 厚板 + 板腿 |
| 架与书 | `bookshelf(seed=…)`、`books_row`、`notebook` | 书随种子排：偶尔斜靠、偶尔平放一摞，相邻不同色 |
| 灯 | `pendant`、`desk_lamp`、`table_lamp`、`street_lamp` | 吊灯的 `loc` 是天花板挂点 |
| 钟 | `grandfather_clock`、`wall_clock`、`alarm_clock` | 挂钟的 `loc` 是钟心，背贴墙 |
| 器 | `vase(kind=…, flowers=n)` | `round` `tall` `bottle` `bowl`；`flowers` 插几枝杯形花（瓶子大于 0.4m 时花杆、花头跟着放大） |
| 床 | `bed` | 床头朝本地 +Y；家里的床和各世界去下沉的床都是它 |
| 草木 | `plant(kind=…)`、`planter` | `potted` 一蓬叶 · `tall` 直茎互生叶 · `tuft` 矮丛（槽里用） |

书桌、嵌在墙里的落地窗这些和场景绑得紧的，仍写在场景脚本里（见 `home.py`），用同样的规则；衣柜在 `prefabs.wardrobe`（它是传送物）。

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

> **只做参考，不进正式世界。** 正式场景里的现实物一律用上一节的「家具与器物」。这条管线留着用来比对比例、看一件东西在管线下的效果，以及 `asset_gallery` 陈列。上面「真实贴图的剪纸」同理。

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
- [ ] 跑一遍 `node scripts/blender.cjs zfight <名字>`，没有共面。常见的坑：门套 / 窗套和洞口一样宽（`home.py` 的 `trim` 每边让 1cm）、两块地板或楼板叠着、墙角两面墙都砌满、踢脚和墙一样长、踏步或平台的顶面和地面同高又压在上面。改法是让一边退开或伸出 ≥ 1cm，或者接上而不叠
- [ ] 跑一遍 `node scripts/blender.cjs clip <名字>`，家具不穿墙、不穿窗台（窗台会伸进屋里约 0.23m）
- [ ] 跑一遍 `node scripts/walk.cjs`（换场景时要改脚本里的坐标）和 `node scripts/travel.cjs`，再截几张图看
