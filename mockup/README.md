# mockup

正式世界动工之前的样板。**一个主域一个文件夹**，里面放白模场景、俯视地图与说明。

| 文件夹 | 是什么 |
|---|---|
| [`shallows-01/`](shallows-01/README.md) | **浅梦（Shallows）** 样板 01：家以外的七个世界的地图设计（白模），每个世界 2~3 个备选方案 |
| [`shallows-02/`](shallows-02/README.md) | **浅梦** 样板 02：重排阵容（删、留、挪、新加），两个新世界光斑、长影直接做成能走的原型（`?world=sunpatch`、`?world=longshadow`），不是白模 |
| [`home-01/`](home-01/README.md) | **梦里的家** 样板 01：核心（卧室与小客厅）、室外、家家家三个区域（白模）；规划见 `docs/home.md` |

先看 [`shallows-01/plans/_index.png`](shallows-01/plans/_index.png)（七张地图拼在一起）。

仓库里只有源文件（`layouts/*.json`、`gen.cjs`、`tools/`、说明）；地图、白模、渲染图（`plans/` `scenes/` `glb/` `resolved/` `renders/`）都是生成的，不入库——
上面和各文件夹 README 里的图片链接要先生成才有：`node mockup/shallows-01/tools/all.cjs all`、`node mockup/home-01/all.cjs`。

约定：样板用仓库自带的 `blender/nx.py` 搭场景（属性 `nx_*` 照写，GLB 将来能直接进游戏），
**布局是一份 JSON**（`layouts/<id>.json`），白模与地图都从它生成，所以两者永远一致。
格式见 [`shallows-01/SCHEMA.md`](shallows-01/SCHEMA.md)。
