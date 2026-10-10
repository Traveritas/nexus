# NEXUS - INDEV

所有网站的枢纽，也是一个像《梦日记》那样的小游戏：从家里醒来，穿过门、杯、床这些现实物去往一个个世界；有的世界里有晶体，走进去就到了一个真实的站点。

- 审美方向：[docs/direction.md](docs/direction.md)
- 用 Blender 搭场景（约定、属性表、尺度、色板、世界与传送物）：[docs/blender.md](docs/blender.md)
- 天空主题：[docs/sky.md](docs/sky.md)
- UI（纸签提示、日记本、物品的方向）：[docs/ui.md](docs/ui.md)

```
npm install
npm run dev                            # 本地预览（从家开始），?world=<名字> 直接去某个世界
npm run build                          # 类型检查 + 打包
node scripts/blender.cjs build slice   # 跑 blender/scenes/slice.py，生成 .blend 与 GLB
node scripts/blender.cjs export slice  # 手改 .blend 后只导出
node scripts/shot.cjs                  # 打包后截图到 .shots/
node scripts/walk.cjs                  # 打包后用真实按键走一遍：台阶、跳、入口、后退
node scripts/travel.cjs                # 打包后把所有世界的所有传送物各走一遍
node scripts/ui-shot.cjs [世界…]        # 打包后截各个按键型传送物前的纸签提示
node scripts/diary-shot.cjs            # 打包后截日记本：打开、悬停、翻页、合上
node scripts/items-shot.cjs            # 打包后截物品：拾起、演出、捏、环绕、日记拾得页
node scripts/map-shot.cjs              # 打包后截罗盘的地图：暗圈、本世界的星、星座、站点
```

截图与行走测试需要 `%TEMP%/node_modules/puppeteer-core` 与本机 Chrome。

操作：点击画面锁定视角 · WASD / 滚轮行走 · Space 跳 · Shift 快走 · E 互动 · Q 按住捏手里的东西 · F 按住看看身上的 · Tab 日记（醒来在日记的目录里）· Esc 释放 · Shift+R 回到到达处
调试键：1 原始世界 · 2 解析度场染色 · 3 色板 · 4 描边（关 / 格 / 细线） · 5 锁级 · G 穿墙飞行（Space 升 / C 降） · H 隐藏提示
查询串：`?world=`（默认 `wake_fragment`，现实的家；梦里的家是 `home`；`?scene=` 同义）· `?pos=x,y,z`（脚底）`&yaw=度&pitch=度` · `?freeze=1` · `?hud=0` · `?sky=`

## 代码地图

| 文件 | 做什么 |
|---|---|
| `src/main.ts` | 启动、主循环、入口的进出与后退复原、解析度场的输入 |
| `src/pipeline.ts` | 世界 → 解析度场像素化 → 合成 → 晶体 → 泛白 |
| `src/materials.ts` | 像素哑光 / 纸片 / 天空三种材质与影子版本；共享的光、雾、晶体光 |
| `src/shadow.ts` | 跟着人走、按纹素对齐的太阳影子 |
| `src/crystal.ts` | 晶体：解析求交、体内反射、色散 |
| `src/level.ts` | 读 GLB，按 `nx_*` 属性装配；碰撞网格；行为 |
| `src/player.ts` | 胶囊行走、迈台阶、跳、飞行 |
| `src/sprites.ts` | 纸片的图：按名字取（内置、程序化、`public/sprites/*.png`） |
| `src/proc.ts` | 程序化的纸片：树、云、星、草、灌木、花（`族.变体:种子`） |
| `src/paper.ts` | 剪纸的现实物：灯、椅、窗、门、杯、电话 |
| `src/skybox.ts` | 天空主题（见 docs/sky.md） |
| `src/palette.ts` | 16 色色板 |
| `src/ui.ts` | UI 地基：低分辨率 UI 画布、像素字、剪纸 |
| `src/prompt.ts` | 交互提示：系在东西上的纸签 |
| `src/diary.ts` | 日记本（Tab）：3D 的书、翻页、拾得、设置 |
| `src/stage.ts` | 舞台：UI 里的 3D 实物（日记本）画在 UI 分辨率上，三档明暗落回色板 |
| `src/mapview.ts` | 罗盘的地图：暗下来的一圈、本世界的星、天上的星座 |
| `src/worlds.ts` | 世界的中文名、星座的形状、走过的连接与有站点的世界的存档 |
| `src/items/` | 物品：定义与登记（`item.ts`）、摆放/拾取/演出/存档/手里/环绕（`system.ts`）、各件物品 |
| `blender/nx.py` | Blender 侧的搭建、标注、导出函数 |
| `blender/prefabs.py` | 预制件族（花之装置、框、阶、环、塔、台、器、纸片撒布） |
| `blender/furniture.py` | 家具与器物：自己的低面数构件（椅、架、灯、钟、瓶、草木），正式世界里的现实物都用它 |
| `blender/assets.py` | 现成模型（Poly Haven）的导入与标注，只做参考与陈列；取模型用 `scripts/fetch-asset.cjs` |
