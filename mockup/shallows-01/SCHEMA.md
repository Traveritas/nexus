# 浅梦样板 · 布局格式（layout JSON）

一个世界 = `layouts/<id>.json`。**这是唯一的数据源**：白模（Blender）和俯视标注地图（PNG）
都从它生成，所以地图画出来的和模型搭出来的永远一致。

```
node mockup/shallows-01/tools/expand.cjs all     # layouts/*.json → resolved/*.json（摊平组合体、校验、算统计）
node mockup/shallows-01/tools/build.cjs all      # resolved/*.json → scenes/*.blend + glb/*.glb + renders/*.png
node mockup/shallows-01/tools/maps.cjs all       # resolved/*.json → plans/*.png（带标注的俯视地图）
node mockup/shallows-01/tools/all.cjs all        # 上面三步连跑
```
（`all` 可换成单个 id，或逗号分隔的几个，如 `arcade,isles`。）

坐标沿用仓库约定（见 `docs/blender.md`）：**Blender 坐标，Z 朝上，单位米**；
`at` 里的 `[x, y]` 是俯视图上的位置（x 向右、y 向上＝北），`z` 是高度。
`rot` 一律是绕竖轴的度数（逆时针为正，0 ＝ 物体正面朝 +Y／北）。

## 顶层字段

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | ✓ | 与文件名同名，英文小写 |
| `title` / `en` | ✓ | 中文名 / 英文名 |
| `role` | ✓ | 一句话：这个世界在浅梦里干什么 |
| `extent` | ✓ | 地面底板边长（米）。取内容范围 ×1.2 左右，地图上以它画一圈虚线 |
| `ground` | | 底板色板 `{a,b,pattern}`，默认 `mist/lilac_pale/grain` |
| `slab` | | 默认 `true`：在原点铺一整块 `extent×extent`、z∈[-1,0] 的底板。`false` ＝ 不铺，地面完全由 `prims` 自己搭（**下挖的井、悬空的岛要用它**，否则底板会把下挖盖住） |
| `sky` | | 天空主题名（见 `docs/sky.md`），可带种子 `"dye:7"` |
| `spawn` | | `{at:[x,y,z], face:度}`；不给时若写了 `home` 就落在灯那儿 |
| `home` | | `[x,y,z]`：省事写法，等于把出生点放在这里（回家那盏灯自己用 prims 搭） |
| `levels` | | `[{z, label}]` 分层（地面 / 二楼 / 水下），地图图例里列出 |
| `prims` | ✓ | 体块列表，见下 |
| `regions` | | 区域标注：`[{label, shape:"rect"|"circle", at, size|r, label_at?}]`；也撑开地图的取景 |
| `portals` | ✓ | 出入口/传送点，见下 |
| `arrives` | | 手放的到达点：`[{name, at, face}]`（多数不用写，见 `portals` 的 `pair`） |
| `shade` | | 白模渲染的受光：默认 `STUDIO`；头顶盖着大片东西（低云、天花）时写 `FLAT`，否则底面渲成全黑 |
| `views` | | 白模渲染机位 `[{name, at:[x,y,z], look:[x,y,z], fov, res?}]`；不给就自动给「俯瞰＋出生点」 |
| `notes` | | 设计说明若干行，写进地图与 README |

**可活动范围**：`expand.cjs` 会自动统计（所有 `deck`/`stair` 体块的俯视面积之和），
并在 map 与 README 里给出「是梦里的家（180 ㎡）的几倍」。目标 ≈ **4~5 倍（720~900 ㎡）**，
主干道/枢纽类可以到 6 倍上下；世界可以大可以小，但整体要比现在大。

## `prims[]` 体块

### 基本体块

| 字段 | 说明 |
|---|---|
| `kind` | `box` · `cylinder` · `torus` · `plane` · `sprite` |
| `name` | 唯一名字（Blender 物体名） |
| `style` | 见下表，决定白模观感与地图颜色 |
| `at` | `[x,y]` 或 `[x,y,z]`（缺 z 记 0）；box/cylinder 的 `at` 是**底面中心** |
| `size` | box/plane：`[x,y]` 或 `[x,y,z]`（box 缺 z 时按 `h`，默认 0.3） |
| `r` / `r2` | cylinder：底半径 / 顶半径（缺 r2 ＝ 直筒）；`segments` 默认 24 |
| `major` / `minor` | torus：主半径 / 管半径 |
| `h` | 高度（box 的 z、cylinder 的高都可用） |
| `rot` | 绕竖轴度数，默认 0 |
| `tilt` | torus 用：`"stand"` ＝ 立着的环（默认平躺） |
| `sprite` | sprite 用：图名（见 `docs/blender.md`「纸片的图」），如 `tree.round:3`、`lamp_street` |
| `face` | sprite 用：默认 `true`（永远正面朝人）；`false` ＝ 固定朝向，背面是白纸 |
| `label` | 可选：在地图上给这个体块标字（放不下时自动让位） |
| `collide` / `shadow` | 默认 `true`；纯装饰的板、水膜、纸片关掉 |
| `spin` / `bob` | 可选：绕竖轴自转（度/秒）／上下浮动（米），只在 GLB 里生效 |
| `rx` / `ry` | 可选：box 绕 X / Y 轴倾斜（度，Euler XYZ）；地图仍只按 `rot` 画俯视轮廓 |
| `plan` | 可选：`"ghost"` ＝ 头顶上的东西（门楣、倒挂的家具），地图上画得很淡，不挡住下面 |

### 组合体（写一行，展开成一堆）

| `kind` | 字段 | 展开成 |
|---|---|---|
| `frame` | `w` `h` `t`(0.28) `depth`(0.4) | 两根立柱 + 一根横楣（一个立着的框） |
| `arch` | 同上 + `corner`(t×1.7) | 框 + 顶上两个收进来的角块（近似拱） |
| `stairs` | `w` `n` `rise`(0.3) `run`(0.75) | n 级实心踏步，沿本地 +Y 一级级升 |
| `colonnade` | `n` `spacing` `r`(0.3) `h`(3) | 一列柱子，沿本地 +Y 排开 |
| `procession` | `from` `to` `n` `w0` `h0` `grow`(1.4) `roll` `t` `depth` | 一列越走越大的框，从 `from` 到 `to`；框面朝着走来的方向，`roll` 是每道多转几度 |
| `spriteRow` | `sprite` `from` `to` `n` `rot` `face` `z` | 一列纸片，沿 `from`→`to` 均匀排开 |

组合体的 `style` 会传给展开出来的每一块。组合体可以套组合体（`procession` 里就是 `frame`）。

### style 对照

| style | 是什么 | 白模色 | 地图色 |
|---|---|---|---|
| `deck` | 走人的地板、平台、堤 | 近白 | `#e6e2ee` |
| `stair` | 台阶、踏步 | 近白 | `#d2cbe1` |
| `wall` | 竖直的墙、隔断、栏板 | 浅灰紫 | `#cdc8db` |
| `mass` | 大块实体：楼体、碑、塔 | 中灰紫 | `#a49cbc` |
| `frame` | 立着的框（门框、拱、窗框） | 深灰紫 | `#8b82a6` |
| `rail` | 细栏、踢脚、道牙 | 白 | `#ffffff` |
| `water` | 水面、浅滩、池 | 淡蓝 | `#c3d1e6` |
| `glass` | 玻璃、窗扇 | 极淡蓝 | `#dce7f5` |
| `plant` | 纸片草木（sprite） | 淡绿 | `#93c0b0` |
| `prop` | 家具尺度的东西、灯 | 淡粉 | `#d9aab5` |
| `void` | 洞、井、缺口（画成暗块） | 深 | `#2a2740` |

## `portals[]` 出入口

| 字段 | 说明 |
|---|---|
| `name` | 唯一名字（Blender 空物体名） |
| `kind` | `home` 回家的灯 · `world` 世界之间 · `site` 晶体→真实站点 · `realm` 跨主域 · `dead` 只进不出的死胡同口 |
| `at` | `[x,y,z]`，z 是传送物中心高度（按键型放齐腰高 ≈ 地面 +1.5，走进型放洞口中心） |
| `to` | 目标世界 id（`site` 留空） |
| `at_node` | 到达点名（留空＝对方的出生点；去家写 `"home"`） |
| `mode` | `key`（走近按 E）／`walk`（走进去）；`site` 恒为 `walk` |
| `title` | 提示文字，如 `关灯` / `一杯水` / `翻开` |
| `url` | `site` 用：站点地址 |
| `rot` | 走进型的洞口朝向（`veil` 与到达点跟着它） |
| `veil_w` / `veil_h` | 走进型的膜尺寸，默认 1.8×2.6 |
| `label` | 地图上的标签，如 `→ 家`；不写则按 kind 生成 |
| `note` | 地图标签下面的一行小字，如 `出生点背后` |
| `radius` | 触发半径，默认 `0.9` |
| `pair` | 默认 `true`（`world` 类）：自动在传送物正面 2m 处放一个到达点，名字＝目标世界；「来回成对」 |

**出入口宜少**（家除外）：两个是常态，三个算多，四个是小枢纽。每个世界至少一个
`home`（回家的灯）＋一到两个别的。死胡同可以只有一个 `home`。

## 地图上的记号

`home` 圆点 · `world` 三角 · `site` 菱形（晶体）· `realm` 方框（跨主域）· `dead` 空心点。
地图另画：出生点（星）、比例尺、指北、区域名、`可活动范围` 与「是家的几倍」。

## 搭一个世界的次序（照着做）

1. 想清楚这个世界的**一句话**与**一条动线**（从出生点到最远处经过什么）。
2. 先铺 `deck`（走人的面）与 `water`/`mass`，跑 `expand.cjs <id>` 看走人面是不是 700~1000 ㎡。
3. 再放出入口（`home` 的灯 + 一到两个别的），`arrives`/`pair` 会自动配好。
4. 然后加 `frame`/`arch`/`stairs`/`colonnade` 做体量与竖向，加 `sprite` 做草木。
5. `build.cjs <id>` 看白模渲染，`maps.cjs <id>` 看地图，来回改 `views` 找好看的角度。
6. 写 `notes` 与 `levels`，收尾。
