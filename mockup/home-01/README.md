# 梦里的家 · 样板 01（Home · mockup 01）

家的白模样板，规划见 [`docs/home.md`](../../docs/home.md)。三个区域分成三份，只为地图看得清；将来是一个世界还是三个，待定。

| 区域 | id | 一句话 | 地图 | 渲染 |
|---|---|---|---|---|
| 核心 | `home-core` | 比记忆里更小、更窄的家：卧室、走廊、小客厅、餐桌一角、浴室、储物间、玄关；六个浅梦世界从这里出发 | [plans/home-core.png](plans/home-core.png) | `renders/home-core-*`（俯瞰、卧室、走廊、客厅） |
| 室外 | `home-outside` | 推开夜里的家门，外面是正午：一大片空地，云压在头顶 6m，像无限大的天花板；云上一个洞落下一柱光（→ 晾场），云在 48m 外贴到地上 | [plans/home-outside.png](plans/home-outside.png) | `renders/home-outside-*`（出生点、回头看门、远望、低处俯看） |
| 家家家 | `home-rooms` | 走廊尽头的门后：一串越来越小、越来越歪的门，然后一间间越来越错乱的家，首尾相接 | [plans/home-rooms.png](plans/home-rooms.png) | `renders/home-rooms-*`（俯瞰、过渡、中段、深处、和卧室一样的那间） |

```
node mockup/home-01/all.cjs              # 生成 JSON → 展开 → 白模 → 地图
node mockup/home-01/all.cjs home-core    # 单个（gen 总是全部重新生成）
```

- **`gen.cjs` 是唯一来源**：家具、墙、房间网格都在里面算，`layouts/*.json` 是它的产物，改布局改 `gen.cjs`。
- 展开、白模、地图借用 [`shallows-01/tools`](../shallows-01/tools)（环境变量 `MOCK_DIR` 指到这个文件夹），格式见 [`shallows-01/SCHEMA.md`](../shallows-01/SCHEMA.md)；为家另加了 `rx` / `ry`（倾斜）、`plan: "ghost"`（头顶上的东西在地图上画淡）、区域的 `label_at`。
- 天花板都不盖，只按高度砌墙；倒挂的家具按天花板高度放。
- 循环、「悄悄带回来」在引擎里还没有：家家家的循环用传送物代替，室外只画出那一圈。
- 室外地面是整块底板，「走人面」只算了门槛和几处隆起，不准。
- 室外的正午、粗格子、换色写在 layout 的 `look` 字段（白模不认；可以走的原型 `house_out` 里接上了）；白模用 `shade: FLAT` 渲，不然云底是黑的。
