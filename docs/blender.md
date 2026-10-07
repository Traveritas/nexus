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
| `nx_mat` | `matte` / `collider` / `none` | `matte` | `collider`＝看不见只挡人；`none`＝不导入 |
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

### 太阳

放一盏 **Sun** 灯，它照射的方向就是阳光方向。只认第一盏；强度、颜色都不用。

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

- 内置：`flower`、`grass1`～`grass3`、`moon`（在 `src/sprites.ts` 里用代码画）。
- 新图放 `public/sprites/<名字>.png`：**每米 16 像素**画，透明背景，透明度只有全有或全无，颜色尽量取色板里的。
- 一张图的底边就是地面。

## 搭场景时的检查清单

- [ ] 有且只有一个 `spawn`，脚底贴着能站的面
- [ ] 每个入口在地面以上约 1.6m，四周走得进去，不需要跳
- [ ] 楼梯每级 ≤ 0.3m；需要跳的高差 ≤ 0.9m
- [ ] 门洞、通道不窄于 0.8m
- [ ] 没有细于约 0.1m 的长物件（远处会闪）；细节交给纸片
- [ ] 跑一遍 `node scripts/walk.cjs`（换场景时要改脚本里的坐标），再截几张图看
