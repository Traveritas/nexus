# NEXUS

所有网站的枢纽：一片可以走动的第一人称空间，每个站点是一枚晶体，走进去就到了。

- 审美方向：[docs/direction.md](docs/direction.md)
- 用 Blender 搭场景（约定、属性表、尺度、色板）：[docs/blender.md](docs/blender.md)

```
npm install
npm run dev                            # 本地预览，?scene=<名字> 切场景
npm run build                          # 类型检查 + 打包
node scripts/blender.cjs build slice   # 跑 blender/scenes/slice.py，生成 .blend 与 GLB
node scripts/blender.cjs export slice  # 手改 .blend 后只导出
node scripts/shot.cjs                  # 打包后截图到 .shots/
node scripts/walk.cjs                  # 打包后用真实按键走一遍：台阶、跳、入口、后退
```

截图与行走测试需要 `%TEMP%/node_modules/puppeteer-core` 与本机 Chrome。

操作：点击画面锁定视角 · WASD / 滚轮行走 · Space 跳 · Shift 快走 · Esc 释放 · Shift+R 回出生点
调试键：1 原始世界 · 2 解析度场染色 · 3 色板 · 4 描边 · 5 锁级 · G 穿墙飞行（Space 升 / C 降） · H 隐藏提示
查询串：`?scene=` · `?pos=x,y,z`（脚底）`&yaw=度&pitch=度` · `?freeze=1` · `?hud=0`

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
| `blender/nx.py` | Blender 侧的搭建、标注、导出函数 |
| `blender/prefabs.py` | 预制件族（花之装置、框、阶、环、塔、台、器、纸片撒布） |
| `blender/assets.py` | 现成模型（Poly Haven）的导入与标注；取模型用 `scripts/fetch-asset.cjs` |
