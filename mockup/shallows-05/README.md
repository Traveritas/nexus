# 浅梦 · 第三批（Shallows · batch 03）

从这里开始做第三批（2026-10-16）。第三轮的说明见 [`shallows-03/`](../shallows-03/README.md)；第四轮的变体没用上，归档在 `archive/shallows-04-var/`。

## 现状

| 世界 | id | 状态 |
|---|---|---|
| 家 · 屋里 / 家家家 | `house` | 可用 |
| 家 · 门外 | `house_out` | 可用 |
| 光斑 | `sunpatch` | 可用 |
| 长影 | `longshadow` | 可用 |
| 下沉 · 井 | `descent` | 可用：井壁是实心的岩，每层挖出一种结构（梳、厅、柱林、回纹） → [descent.md](descent.md) |
| 花房 | `glasshouse` | 调优过（花不穿模；为掉帧删了玻璃面、反光条和会动的花）；花的外形之后再改 → [glasshouse.md](glasshouse.md) |
| 断梯 | `stair` / `stair_b` | 可用（交接的智能体做的）：炸开的楼梯 ＋ 用缝穿过自己 ＋ 尺度错乱 → [stair.md](stair.md) |
| 浅滩 | `shoal` | 可用：头顶的水；沙纹是封闭的矮实体；水波光斑（引擎 `caustics`） → [shoal.md](shoal.md) |

## 接进网里（2026-10-16）

- 现实的床「睡」→ `house` 床边（到达点 `wake`）。旧的 `home`、`procession`、`room` 是 legacy：还在、`?world=` 进得去，但不在星图上（`src/worlds.ts` 的 `LEGACY`）。
- 家里的六样（`house.py` 的 `gates()`）：床 → 下沉，衣柜 → 长影，书 → 断梯，落地窗 → 光斑，花瓶 → 花房，一杯水 → 浅滩。罗盘在茶几上。
- 星图（`CONSTELLATION`）：家在正中；门外、下沉在一边，断梯 → 那边 → 云阶一串往外，花房在另一边，光斑、长影、浅滩围着它。
- `travel.cjs` 里家的落地窗、衣柜两项会报失败：它们要先按 E 打开才走得进去，脚本不会开。手动测过（打开再走）能到。
