# Toolmanagement-web 开发计划 v1.1

> **v1.1 = v1.0 + 2026-11-03 第二轮独立审核（closure / cold-read）修订。**
> 第二轮发现 28 条一轮问题中 15 条已关闭、13 条部分关闭；另新引入 23 条矛盾，其中 6 条属「静默错且 DoD 抓不到」级别（z 原点两套并存、`to_board_frame` 符号错、契约三套字段名、板厚 20 落进手孔空档、移植清单保留取负、Gridfinity 总高两个值）。**本版逐条修完，改动表见 §0.1。**
>
> **v1.0 = v0.3 + 2026-11-03 四路独立审核（exec / sds / risk / value）修订。**
> 审核裁决：exec = 需大修，sds / risk / value = 需小修。本版逐条吸收，改动集中在三处：
> ① §2.3 的 y 轴约定**写反了**，已纠正并补齐为六条；② §4 由"里程碑串"改成**阻塞图 + 可离线复现的 DoD**，新增 M-1 冒烟与 0.3b / 0.7 / 0.8；③ 新增 §3.1（D1'/D6'/D8'/D14'/D15' 修订 + D18'–D21'）。
> 工期由 16 人日降到 **14.5 人日**（砍掉畸变标定、打印反馈回路、first-fit 自动排、亚像素精修）。


> 状态：**推翻 v0.2 的主线**。v0.2 已归档，仅其"问题诊断"部分继续有效。
> 依据：三轮独立红队复审（产品/几何/交付）+ tracefinity 源码全量通读。
> 日期：2026-11-03
> 规模：**14.5 人日**，M-1–M4 六个里程碑（M-1 冒烟 0.5 / M0 2.5 / M1 3.5 / M2 3 / M3 3.5 / M4 1.5）


### 0.1 v1.1 修订表（第二轮审核，逐条可查）

| # | 问题 | 修法 | 落在 |
|---|---|---|---|
| 1 | z 原点两套并存（`H/2 + 0.9` 与 `thickness + 0.9`），H=20 时前一条**永远通过** | 全项目只剩 `z=0 在板底、板顶 = thickness`；删除 ±H/2 居中 | §1 F1、§2.3 第 2 条、D12'、M-1、0.2、1.1、1.5 |
| 2 | `to_board_frame` 的 `y=(origin.y+board_h)−p.y` 值域是 `[−h,0]`，不是 y-up | 改 `Vec2(p.x−center.x, center.y−p.y)`，板原点 = 板外接框中心 | §2.3 第 6 条 |
| 3 | 计划 D19' 与 SDS 各写一套字段名 | **以 SDS §3/§4 为唯一真源**，camelCase，未知字段 400 | D19' |
| 4 | 手孔板厚默认 20 落在 12 与 25 之间的空档 | 板厚枚举 6/12/25（默认 12）；`HoleShape` 加 `scoop`；sphere 改球缺 | D6'、1.5 |
| 5 | 移植清单把 `stl_generator_manifold.py:809-966`/`:969-1039` 标为"原样"，但 `:896`/`:984` 是 `-(p[1]+offset_y)` | 移植时删取负与 `offset_y` 形参；0.6 加非对称 fixture | §2.1 #4/#5/#6、0.6 |
| 6 | Gridfinity 总高 SDS 内部两个值（`7U+4.75` vs `7U`） | 统一 `7U`（3U = 21），加断言 | D8'、SDS §7.2 |
| 7 | 倒角三参数三套名（`fillet`/`corner_r`/`slot_chamfer`/`base_chamfer`） | 只留 `cornerR` / `baseEdgeRoundover` / `slotChamfer` | D15'、1.0b、2.3a/b |
| 8 | 1.6 依赖 2.3a，但 2.3a 排在 M2 | 新增 **1.0b** 把三参数提到 M1；2.3a 降级为联调验收 | M1 / M2 |
| 9 | 唇剖面抄 cq-gridfinity 的斜边写法折算 8.09，DoD 要 8.2 | 真源改 tracefinity `LIP_D0..D4`（2.6/1.2/0.7/1.8/1.9） | §2.4、1.4b |
| 10 | 1.1 锥台取样高差 `chamfer−0.1`，宽度差 2.8 而断言 3.0 必红 | 改取 `z = thickness − 1e−6` 与 `thickness − chamfer` | 1.1 |
| 11 | 容差三处三值（1.0 / 0.5 / ±0.05mm² 与 ±2×clearance 量纲互斥） | 新增 SDS §10.3 容差总表，全部指向它 | 0.3、0.6、1.2 |
| 12 | 缺"槽/手孔必须落在板轮廓内"校验 | 新增 `tools_in_board`（阻断，`TOOL_OUT_OF_BOARD`） | SDS §7.6 第 9 条 |
| 13 | 人日账 16−3.0+2.0=15.0 却报 14.5 | 基线改 15.5、加法含 1.0b 共 +2.5、再扣 1.6 返工 0.5 | §7 |
| 14 | D3' 保留 first-fit，但 §5 已砍 | D3' 同步删除 | D3'、§2.2 #7、§5 |
| 15 | 0.8 要改 `cad_engine.py` 的 17 处 `except`，但 SDS 宣布该文件冻结 | 范围收窄为"新代码 + main.py 信封层"，旧文件只许加计数行 | 0.8 |
| 16 | `NO_SPLIT_RIB` 被两种原因复用 | Gridfinity 分块改 `GRIDFINITY_SPLIT_UNSUPPORTED` | 3.2 |
| 17 | 3.4 DXF 未定义 y 翻转，面积类 DoD 对镜像不敏感 | 默认翻转，DoD 加非对称点断言 | 3.4 |
| 18 | `is_watertight` 单独用等于没查 | 已在 D12' 两级自检 + 首击射线断言 | D12'、M-1 |

---

## §0 这一版为什么推翻 v0.2

v0.2 的诊断是对的，处方是错的。三个红队独立得出了同一个结论：

| v0.2 的假设 | 实际情况 |
|---|---|
| 需要自研一套「逐顶点变宽度多层 2.5D loft」几何内核（D4.1/D4.2/D4.3） | tracefinity 用 `shapely.buffer(join_style=2)` + `CrossSection.offset(JoinType.Round)` + `extrude(scale_top=...)` 约 90 行就做完了，且没有层间顶点对应问题 |
| L2 矢量编辑器「已有」，只需加四件（D5） | **全项目不存在任何顶点级编辑代码**（`grep editVertex|selectedVertex|dragVertex` 为空），`EditorPanel.tsx:55` 自称矢量编辑器但内容只有画笔/橡皮 |
| 槽的坐标系问题只是「840×1188 硬编码」 | 更致命的是 **z 基准也错了**：槽是从 z=0 拉伸的，导致槽顶落在板顶之下，槽是**密闭空腔**（见 §1 F1） |
| 工期 26–37 人日 | 三个红队独立估 10–14 人日；加上用户后补的「模型分块 / 双板外形 / DXF / 畸变标定」后，v0.3 定为 **16 人日** |

**v0.3 的主线**：把几何内核整体移植（MIT 允许），把省下的 15 人日全部投到两块**真正没有开源替代品**的地方——**拍照端**（纸角确认、照片体检、镜头畸变、亚像素轮廓）和**交互端**（顶点编辑、手孔拖拽、倒角参数、撤销重做）。

**工具定位（已由用户确定）**：本工具**只管生成模型，不管材料与工艺**。输出物有两种形态，来自同一套几何数据：
- **STL**：实心板 + 凹槽，用于 FDM/SLA 打印（PLA/PETG/TPU 都行，用户自理）
- **DXF/SVG 1:1 轮廓图**：凹槽轮廓 + 深度标注，用于 CNC 铣削 / 激光切割 / 刀模切割泡沫

因此**"Foam"不再是"柔性材料打印件"**，而是"实心板 + 凹槽"这一形态的中性叫法。不做中空、不做肋、不做材料相关的夹持策略。

**边界（用户 m00751 / m00755）**：
- **工具必须完整落在 A4 内**；超过 A4 的工具不做（那种尺寸直接挂墙）。
- **本项目不做切片**（切片 = 生成 G-code）。切片由打印机自带软件完成，且每台机器参数不同。本工具只输出几何模型（STL / DXF），不涉及层高、壁数、填充、支撑、打印机预设、材料预设。
- **但要做「模型分块」**（用户 m00776）：板超过打印机最大打印尺寸时，切成多片分别打印、打印完粘起来。这是几何问题，不是切片问题。

---

## §1 四个新确认的硬事实（已复核，带行号）

### F1. 槽是密闭空腔——最致命，且 v0.2 的六道守卫全部抓不到

```python
# python_backend/cad_engine.py:600-601
slot = trimesh.creation.extrude_polygon(poly, height=embed_depth + 1)
slot.apply_translation([0, 0, -embed_depth / 2])
```

- `extrude_polygon` 从 z=0 起拉伸 → 槽体 z ∈ `[-embed/2, +embed/2 + 1]`
- 底板 `_make_rounded_box` 在 `cad_engine.py:96` 做 `apply_translation([0,0,-size_z/2])` → 板体 z ∈ `[-H/2, +H/2]`
- 默认 `height_mm=20`、`embed_depth=15`：槽顶 = +8.5，板顶 = +10 → **槽上方留 1.5mm 实心顶盖，槽完全封闭**
- Gridfinity 更糟：`models.py:104-105` 的 `height_mm = height_u*7 + 5`，3U = 26mm，板顶 +13，槽顶 +8.5 → **盖 4.5mm**

这个 STL 水密、`volume_mm3` 正常、`/generate-cad` 返回 `success: true`。切片预览只看外形也正常。打印出来是一块实心板。

**v0.2 的 M1 六道守卫为什么全绿**：`tool_solid.difference(pocket_solid).volume≈0`（工具实体整个落在空腔内部，差集确实是 0）、单连通（外壁+内腔仍连通）、`min_wall≥1.2`（1.5mm 顶盖被算成合格壁厚）、`embed_depth ≤ H−0.2`（15≤19.8）、逐层面积对照（拿同一套错误几何做基准）、`is_watertight`（密闭空腔更"水密"）。

**修法**：槽切刀改为从板顶向下切，且顶面过切 1mm。

> **▸ 第二轮审核：z 原点全项目只允许一个定义 —— `z = 0` 在板**底**面，板顶面 = `thickness`（SDS §2.3）。**
> 不再用 ±H/2 居中（`cad_engine.py:96` 的居中做法就是 F1 的成因之一，必须删）。因此下文所有 z 公式里的 `H/2` 都已替换为 `thickness`；**旧代码里的 `[-H/2, +H/2]` 只出现在 §1 对现状的描述中**。

`z ∈ [thickness − embed_depth, thickness + 1]`。手指槽同理（`cad_engine.py:359`、`:368` 现在也是从 z=0 起）。

**必须新增的机检断言（M0 DoD，缺一不可）**：
1. `slot_cutter.bounding_box()[1][2] >= thickness + 0.9`（切刀必须刺出顶面）
2. 取 `base.section_plane(plane_origin=[0, 0, thickness − 0.01], plane_normal=[0, 0, 1])`，断言槽投影区域内**没有面**（等价于：顶面在该区域是空的）
3. 从板顶 `(x_slot, y_slot, thickness + 10)` 竖直向下 raycast，首击 `z ≈ thickness − embed_depth`（**不是** `thickness`）。这一条是密闭空腔的**唯一**可靠反证。

### F2. L2 矢量编辑器不存在，是从零写

- `src/features/editor/EditorPanel.tsx:55` 自称"矢量轮廓编辑器"，实际渲染的是 MaskEditor 的画笔/橡皮
- `src/features/workspace/Viewport.tsx:286` 收到 `primitives` 仅用于画红线（`:324-402`），无交互
- 全项目无 `editVertex` / `selectedVertex` / `movePoint` / `dragVertex`
- `src/features/mask/MaskEditor.tsx` 有 undo（`history` 数组 + `:720-745` `undo()` + `:818-825` Ctrl+Z），但**没有 redo**，且只在蒙版编辑内部生效

### F3. Gridfinity 磁吸孔位置是错的

```python
# python_backend/cad_engine.py:258-269  _gridfinity_hole_positions
cx = (ix + 0.5) * GRIDFINITY_PITCH - units_x * GRIDFINITY_PITCH / 2
```
孔放在**格子中心**。Gridfinity 规范是每个格子的**四角各一个**，且**孔心距 26mm**（`cq-gridfinity/constants.py` 的 `GR_HOLE_DIST = 26/2`，即 42mm 格内相对格心 ±13mm；tracefinity 的 `MAGNET_INSET = 4.8mm` 是从孔边缘量的同一组位置）。按现状打出来的盒子**摞不上任何标准底座**。同理 `_make_gridfinity_base`（`cad_engine.py:217-255`）是"实心块减裙边"，没有三段锥台底座、没有五段堆叠唇。

### F4. 内孔在全链路有 5 处断点

| 断点 | 位置 | 后果 |
|---|---|---|
| `fill_holes` 主动填洞 | `sam_tool_contour.py:46-53` 定义，`:211`、`:215`、`:232`、`:236` 调用 | 扳手环形头中心直接变成实心 |
| `RETR_EXTERNAL` 只取外轮廓 | `sam_tool_contour.py:115`、`:142`、`:191`、`:218`、`:240` | 内环从未被提取 |
| primitives 拍平成单环 | `cad_engine.py:503-521` `_primitives_to_2d_polygon` | 即使提到内环也被丢掉 |
| `Polygon` 拉伸不带 holes | `cad_engine.py:609` | 布尔减时孔被填 |
| 前端不渲染内环 | `MaskEditor.tsx` / `Viewport.tsx` | 用户看不见、改不了 |

tracefinity 的完整解法：`stl_generator_manifold.py:706-750`（`_shapely_to_cross_sections` 带 interior rings）+ `:809-868`（`FillRule.EvenOdd` + `area<=0` 反环重试）。

---

## §2 移植清单（MIT，直接搬，改 import）

路径前缀：`reference/oss/tracefinity/`

### 2.1 后端（必须移植）

| # | 模块 / 函数 | 位置 | 行数 | 要改什么 | 难度 |
|---|---|---|---|---|---|
| 1 | 标定 + 全视野 warp | `backend/app/services/image_processor.py:14`、`:19-110`、`:377-443` | ~110 | 输出改成固定 `PX_PER_MM=10`；`scale_factor` 恒为 0.1；保留"扩到整张源图可见范围"和 `pick_paper_orientation` | 易 |
| 2 | 照片体检 | `backend/app/services/photo_checks.py:36-145` | ~140 | 原样；`PAPER_SIZES` 换成我们的尺寸表 | 易 |
| 3 | 偏置 + 平滑/简化管线 | `backend/app/services/polygon_scaler.py:171-249` | ~95 | 原样。**顺序必须是先 smooth/simplify 后 clearance** | 易 |
| 4 | 槽切刀 + 倒角锥台 | `stl_generator_manifold.py:809-966` | ~160 | ① **删掉函数内的 `-(p[1] + offset_y)` 与 `offset_y` 形参**——入参已是板局部 y-up mm，再取负就是竖直镜像；② z 基准按本项目"板顶向下切"重写 | 中 |
| 5 | 手指孔 5 形态（+ scoop = 6） | `stl_generator_manifold.py:969-1039` | ~70 | ① 同上删 `:984` 的取负；② 坐标从像素转 mm；③ 按 §3.1 D6' 增加 scoop 形态 | 中 |
| 6 | 手指孔倒角 | `stl_generator_manifold.py:1042-1118` | ~75 | 同 #5：删取负，其余原样 | 易 |
| 7 | 内环 CrossSection | `stl_generator_manifold.py:706-786` | ~80 | 原样；`_clip_to_interior` 的矩形改成我们的板内壁 | 易 |
| 8 | 圆底角扫掠切刀 | `stl_generator_manifold.py:553-626` | ~70 | 原样（用于 filleted_rectangle 手孔） | 易 |
| 9 | Gridfinity 底座 + 堆叠唇 + 磁吸孔 | `stl_generator_manifold.py:90-162`、`:260-298`、`:629-703` | ~250 | 常量表照抄；`grid_x/grid_y` 参数化 | 中 |
| 10 | 床分割 | `stl_generator_manifold.py:1545-1669` | ~120 | 原样（v1 可推迟） | 易 |
| 11 | 参数模型 | `backend/app/models/schemas.py:63-157` | ~90 | Pydantic → 我们的 dataclass；补 `clearance/chamfer/interior_rings/depth_override` | 易 |
| 12 | 物理尺寸回归测试 | `backend/tests/test_physical_size_pipeline.py`（`SIZE_TOLERANCE_MM = 1.0`） | ~120 | 改造成本项目的 golden test | 易 |

### 2.2 前端（必须移植）

| # | 模块 | 位置 | 说明 | 难度 |
|---|---|---|---|---|
| 1 | 顶点编辑器 | `frontend/src/components/PolygonEditor.tsx:214-263`（边上插点/删点/拖点） | 纯 SVG/React，逻辑可整段搬 | 中 |
| 2 | 编辑器工具条 + 模式集 | `ToolEditorToolbar.tsx:10`（9 种 edit mode）、`:282`（平滑视图切换） | 9 种模式的交互定义 | 中 |
| 3 | 手孔编辑 | `frontend/src/components/ToolEditor.tsx:470-503`（6 种孔型）、`:542-600`（拖/缩放/旋转）、`:316`（镜像） | 直接对应 PRD F3.5 | 中 |
| 4 | undo/redo | `frontend/src/hooks/useHistory.ts:1-60` | 60 行，Ctrl+Z / Ctrl+Shift+Z | 易 |
| 5 | 对称 | `frontend/src/lib/symmetry.ts:34-56`（`partnerIndex(i) = (n-i)%n`） | 对应 PRD F3.11 | 易 |
| 6 | 纸角手拖 | `frontend/src/components/PaperCornerEditor.tsx:115-200` | 对应 R2 的兜底 | 易 |
| 7 | 排版（仅重叠检测） | `frontend/src/lib/drawerLayout.ts:197-283` 里的 `unfittedIds` 回传与冲突高亮 | **只抄 UX 模式**；`fitAll` 之类的自动摆放**不移植**（D3' 已砍） | 易 |

### 2.3 移植时必须先统一的六个约定（不统一会静默出错）

> 前三条是 v0.3 原有的，其中**第 1 条写反了**——四路审核一致指出。后三条是本轮补的静默失败面。

1. **y 轴方向（v0.3 写反，已纠正）**：tracefinity 的输入是 SVG，天然 y-down；它在 `stl_generator_manifold.py:896`、`:984` 写 `-(p[1] + offset_y)`，**这正是 y-down → y-up 的那一次翻转**，不是"多余取负"。本项目**存储层保留纸面 y-down 毫米坐标**（原点 A4 左上、+y 向下），在唯一的 `to_board_frame()` 里翻转成板局部 y-up（原点板中心，z=0 板底）。**翻转只允许出现在这一处**；任何其它地方再取一次负就是竖直镜像——偏口扳手的槽口会朝反方向，旋转 180° 也补不回来，而且几何全绿。
2. **z 原点（与 tracefinity 相同，不必换算）**：两者都是 `z = 0` 在板**底**面、向上为正。**本项目不使用 ±H/2 居中**（`cad_engine.py:96` 的居中必须删除，它是 F1 的成因之一）。板顶面 `z = thickness`；`wall_top_z` 在这里就等于 `thickness`。倒角锥台的基面固定在 `z = thickness − eff_chamfer`、向上外扩，**不能**沿用 tracefinity 里多一层 `+ wall_top_z` 的写法——锥面一旦落到 `z = thickness + 1` 的空气里，槽口仍是直角，而"剖面能看到锥面"的 DoD 照样通过（F1 重演的路径）。
3. **数据结构**：tracefinity 用 Pydantic `GenerateRequest`；本项目是 `python_backend/models.py` 的 dataclass，缺 `clearance`、`holes`（内环）、`depth_override`，必须先补齐再移植。
4. **绕向**：外环 CCW、每个内环 CW，**导入即归一化**并断言 signed area 符号。`skimage.measure.find_contours` 返回 (row, col)，转 (x, y) 时 y 取反会把内环一起翻转——不报错，只是孔被 union 吃掉（实测体积差 25%）。
5. **mask 极性**：约定 `alpha > 0.5 = 工具`。断言 mask 面积占画布 5%–60%，否则说明极性反了或照片全黑。
6. **像素中心与板原点**：10px/mm 下坐标取像素中心，统一 `+0.5 px` 再换算 mm。**板原点 = 板几何中心**（x/y），z 原点在板底面——不是"左下角"（第二轮审核指出：`x = p.x − origin.x` 与 `y = (origin.y + board_h) − p.y` 这组式子的值域是 `[0,w] × [−h,0]`，既不居中也不是 y-up，必须改）。现在是 `poly_mm -= center`（`cad_engine.py:585`）把工具挪到板心，但**从未定义"板心"是哪个点**；必须断言"槽 bbox 到板边距 = 面板上填的边距"，否则整体偏 8mm 肉眼看不出来但装不进。手孔切刀同样从 z=0 起（`:368`），并入 0.2 的同一条开口断言。

---

### 2.4 除 tracefinity 外，另外这 10 处该抄的（2026-11-03 四路开源调研结论）

> 许可证逐个核对（GitHub API / LICENSE 原文 / PyPI 元数据）。**只列能进 MIT 项目的。**

| 需求 | 抄哪个（star / 许可） | 抄什么（具体到文件/函数） |
|---|---|---|
| **Gridfinity 数值** | `michaelgale/cq-gridfinity` 205★ **MIT** | `cqgridfinity/constants.py` **整份拷进来当唯一真源**：`GRU=42`、`GRU_CUT=42.2`、`GRHU=7`、`GR_BASE_HEIGHT=4.75`、`GR_STR_H=1.8`、底座剖面 `((TOP_CHAMF*√2,45°),1.8,(CHAMF_H*√2,45°))`、**唇剖面五段高度 = `2.6 / 1.2 / 0.7 / 1.8 / 1.9`，累计 8.2**（真源是 tracefinity `stl_generator_manifold.py:33-37` 的 `LIP_D0=1.9, LIP_D1=1.8, LIP_D2=0.7, LIP_D3=1.2, LIP_D4=LIP_D0+LIP_D2=2.6`，顺序为 `LIP_D4, LIP_D3, LIP_D2, LIP_D1, LIP_D0`）；**不要用 cq-gridfinity 文档里的 `(1.6√2, 45°)` 那套**——那是"斜边写法"，按 45° 折算出来的段高是 `2.263/1.2/0.990/1.8/1.839`（累计 8.09），与 8.2 差 0.11mm，混用会让唇高断言永久红、`GR_HOLE_D=6.5`、`GR_HOLE_H=2.4`、`GR_HOLE_DIST=13`、`GR_RAD=4`、`GR_FILLET=1.1`。**推导式也要抄**（`GR_BASE_TOP_CHAMF = 4.75 − CHAMF_H − 1.8`）——只抄结果数字，改一个尺寸就崩。 |
| 底座/唇的几何语义 | `kennetek/gridfinity-rebuilt-openscad` 2295★ **MIT**（LICENSE 正文确认；GitHub 显示 NOASSERTION 是文件头不规范） | `docs/constants.md` 参数语义表；`src/core/standard.scad`、`base.scad`、`wall.scad`、`tab.scad`；`tests/*.json` 当尺寸回归基线 |
| **纸角排序** | `imutils/perspective.py` 4580★ **MIT** | **只抄骨架，两处必须改**：① `dst` 直接写物理尺寸 `[[0,0],[210*10-1,0],[210*10-1,297*10-1],[0,297*10-1]]`，让 warp 输出天然是 0.1mm/px；② `order_points` 在旋转 >45° 时错序（它按 x 排序分左右），改用 `s=pts.sum(1); d=np.diff(pts,axis=1)` 取 min/max 四角。横竖不猜——用 210×297 与 297×210 两个 dst 都试，取 `findHomography` 的 `reprojErr` 小者。 |
| **亚像素轮廓** | `scikit-image` 6630★ **BSD-3** | `measure.find_contours(alpha, 0.5)`（marching squares，亚像素）；`restoration.rolling_ball()` 消纸面光照不均/阴影。**这两个函数顶掉 `sam_tool_contour.py` 里大半形态学**。 |
| 兜底分割模型 | `danielgatis/rembg` 25291★ **MIT** + `isnet-general-use.onnx`（170MB，上游 DIS **Apache-2.0**） | `remove(..., only_mask=True)` 拿 mask；`post_process()` 里**只抄 `opening(disk(1))`，别抄 `gaussian_filter(sigma=2)`**——那一步会把扳手的 90° 角削成 R2，直接吃掉 1mm 余量。ONNX 已现成挂在 rembg 的 `v0.0.0` release，不用自己 `torch.onnx.export`。 |
| **场外编辑器交互** | `pascalorg/editor` 25286★ **MIT** | `packages/editor/src/components/tools/shared/polygon-editor.tsx` **整文件**。7 条精华：① 拖拽状态存 `initialPolygon` **快照**，每次 move 从快照重算（不 `+= delta`，防丢帧漂移、Esc 可回滚）；② `onPolygonPreview`（每帧）与 `onPolygonChange`（仅 pointerup）分离 → **一次手势 = 一条 undo**；③ render 阶段比对 `polygon !== lastPolygonRef.current` 丢弃过期预览；④ 中点插点要「插入即进入拖拽」；⑤ 边拖拽沿外法线投影，法线用质心翻转 `if (nx*(mx-cx)+nz*(mz-cz) < 0) 翻转`（对混合绕向免疫）；⑥ 装饰性 mesh 一律 `raycast={NO_RAYCAST}`，否则边条抢走顶点点击；⑦ 吸附做成注入回调 `resolvePlanPoint`，不写死。 |
| **撤销/重做** | `charkour/zundo` 899★ **MIT** | zustand 中间件，peer `zustand ^4.3 \|\| ^5`，直接 `npm i`，不用自己写 history 栈。 |
| 前端矢量预览 | `jankovicsandras/imagetracerjs` 1548★ **Unlicense**（=公有领域） | `imagedataToSVG()` + `pathomit`（去灰尘碎轮廓）+ `rightangleenhance`（保直角）。单文件无依赖。**只做即时预览，定稿仍走后端。** |
| DXF 导出 | `mozman/ezdxf` 1516★ **MIT**（已实测） | `msp.add_lwpolyline(pts, close=True, dxfattribs={'layer':'CUT'})`；`doc.header['$INSUNITS']=6`（=mm）。注意 **SVG 后端要 Pillow**，只为网页预览不如自拼 SVG 字符串。 |
| 1:1 纸样校对 | `justinhardin/gridfinity-pic-to-bin` 2★ **MIT** | `trace_export.py` 的「打印一张 1:1 纸样比划一下」思路，约 20 行。 |

**明确不能碰（许可证）**：`Le0Michine/FusionGridfinityGenerator`（CC BY-NC-SA，非商用+传染）、`breandan81/shadow-board`（GPL-3.0）、`skotagiri/tooltrace`（**无许可证 = 默认保留所有权利**）、potrace 全家（GPL-2.0，含 `node-potrace` / `esm-potrace-wasm`）、pymeshlab / pymeshfix（GPL-3.0）、PrusaSlicer / OrcaSlicer（AGPL-3.0）。

**搜索到的反证**：GitHub 上「照片 → 收纳嵌件」做得成的项目不到 10 个，其中 6 个是 0–4★ 或玩具级。**想到的人不少、做成的不多**——抄 tracefinity + 上面这 10 处，已覆盖公开经验的 90%。

## §3 修订后的决策（D1'–D21'；D18'–D21' 与加粗条目的修订见 §3.1）

| 编号 | 决策 | 相对 v0.2 的变化 |
|---|---|---|
| **D1'** | 透视校正后输出**固定 10px/mm** 的图。A4 竖向 → 纸面 2100×2970 px，四周各留 150px（15mm）安全边，画布 2400×3270 px，纸原点在 (150,150)。`mm_per_px` 恒为 0.1，**不向下游传递 `px_per_mm`**。源图长边 < 1800px 时拒绝并提示重拍。**不做**"工具超出纸张"的全视野扩展画布。 | 推翻 v0.2 的"自适应 ppmm 穿透 5 层"；简化 tracefinity 的全视野 warp |
| **D2'** | **一张照片拍 1..N 把工具，全部必须完整落在 A4 内**（用户 m00751：超过 A4 的工具没有收纳意义，直接挂墙）。一次提取多个轮廓、一次生成一块板。**校验**：任一轮廓的外接框触到纸边界（距边界 < 3mm）→ 直接报错"工具超出 A4，请更换工具或分次拍摄"，**不静默截断**。 | 推翻 v0.2 的"一照一工具、超 A4 手动建槽"；也推翻此前"支持纸外工具"的想法 |
| **D3'** | 排版只做：重叠检测（高亮冲突）+ 手动拖拽 + 旋转 90° + 未放下提示。**不做** first-fit 自动摆放（v1.0 起砍，见 §5）、不做一个**自动排版算法**、不做 STRtree/NFP/0.05mm 强制重叠。 | 砍掉 v0.2 的 D3 四件套；first-fit 亦砍（第二轮审核：§5 已列为砍掉，§3 又保留，自相矛盾） |
| **D4'** | 几何内核 = manifold3d。倒角 = `CrossSection.offset(JoinType.Round)` + 单层 `extrude(scale_top)` 锥台，与直筒切刀并集。**不做** miter 逐顶点偏置、medial axis、8~16 层曲线表、二分求 max d。**五个实测坑（照抄必踩）**：① `extrude(scale_top=)` 绕**原点**缩放、不是质心 → 拔模前必须 `cs.translate(-cx,-cy)`；② 孔的绕向必须与外轮廓相反（外 CCW / 孔 CW），否则孔被 union 吃掉（实测体积 4000 而非 3000）；③ `offset` 的 JoinType **只作用于凸角**，凹角永远 miter；④ 连续多次 offset 之间插 `cs.simplify(1e-3)`；⑤ 床分割用 `Manifold ∩ Box`，**不要用** `trimesh.slice_plane(cap=True)`（封口缺面，issue #2299）。 | 砍掉 v0.2 的 D4.1/D4.2/D4.3；补实测坑 |
| **D5'** | 轮廓编辑：顶点拖 / 边上插点 / 删点（下限 3，拒绝）/ 整体旋转 / 框选缩放 / 撤销重做。**圆弧基元 v1 只读**：一旦进入顶点编辑，arc 降级为折线并在 UI 明确提示。 | v0.2 未定义 arc 策略 |
| **D6'** | 手槽改用**竖直手孔**（sphere / cylinder / square / rectangle / filleted_rectangle），每孔独立 `depth_override`、`rotation`、口部倒角。**放弃 v0.2 的 scoop 同深度外凸模型**。 | 推翻 D6 |
| **D7'** | 数据结构 `Project → Board → Tool → FingerHole`（+ `interior_rings`）。M0 只做 localStorage 全量草稿 + `schemaVersion`，完整持久化等几何定型。 | v0.2 要求提前定完整 schema |
| **D8'** | 厚度三档（6 / 12 / 25mm 全高）+ **`embed_depth ≤ height_mm − 2` 强制 clamp**。板体**永远实心**（不中空、不加肋、不做薄壳）——v0.2 的 D10 薄壳与深槽算术互斥：2.4mm 顶板 + 任何 >2.4mm 的槽 = 打穿。材料无关：PLA / PETG / TPU / 泡沫 / 木板，同一份几何。 | 推翻 D10 的薄壳/肋/工时估算 |
| **D9'** | 间隙：滑杆（0.2–1.0mm，默认 0.4）+ **40×40×10 试切件**（打 0.2/0.4/0.6 三档）。浏览器本地记住上一次的值。**不做**材料数据库、不做按打印机预设、不做切片参数。 | 保留，删掉"公差非对称 +1.5/−0.3" |
| **D10'** | 只做**几何**校验：`is_watertight`、凹槽之间/凹槽与板边的**最小筋厚 ≥ 2.0mm**、`embed_depth ≤ height − 2`。**不做**层高/壁数/填充/支撑/床温/G-code——那是切片软件的事，本项目完全不管。不做用料与工时估算。 | 砍 |
| **D14'** | **新增：模型分块**（用户 m00776 明确要）。参数「最大打印尺寸」X/Y/Z（默认 220×220×220，用户可改）。板任意一边超出 → 自动裁成 nx×ny 片，每片独立 STL。**切缝只允许落在凹槽之间的实心筋上，绝不穿槽**（穿槽会把凹槽切成侧面开口，工具会滑出来）；该方向找不到任何 ≥2mm 的筋 → 拒绝并提示「请换更大打印机或缩小板」，不静默生成残缺件。片间用**圆柱定位销**而不是燕尾——销的容差好控制，燕尾要精确打印才能插。~~φ4×8 盲孔~~ → **已被 §3.1 的 D14' 修订取代：销必须水平、从切缝面钻入**。~~Gridfinity 板的分块线吸附到 42mm 网格~~ → **已被取代：v1 禁用 Gridfinity 分块**。Z 超限只告警不切。 | 新增（v0.2 曾推迟） |
| **D15'** | **新增：板的两种外形，都做。** ① **自定义矩形**：工具并集外接框 + 用户填的边距（默认 8mm）+ 可选圆角；② **Gridfinity**：按 42mm 网格向上取整，带标准底座/堆叠唇/磁吸孔。切换时工具轮廓与手孔位置**原样保留**，只换外框与底座。 | 新增（用户 m00776：两个都要） |
| **D11'** | 精度只承诺 **S0（±1.5mm）**。拍照指引 + 照片体检（EXIF 反算相机高度、纸出框、极端透视三条告警）。**不做** 3×3×2 的 18 件 DoD 矩阵。 | 砍 S1/S2 |
| **D12'** | **新增：两级自检**。L0（2D，最便宜）：`shapely.is_valid` + `explain_validity` + `buffer(0)`——90% 的坏几何死在这一层。L1（3D）：`trimesh.is_watertight` + `is_winding_consistent` + `manifold.status()` + `genus()` + 体积与解析值 ±2% + bbox 对格位。**`is_watertight` 单独用等于没查**——实测两个重叠立方体拼起来仍然 watertight、`status()` 仍返回 `NoError`。壁厚用 `Manifold.min_gap(other, search_length)` 直接量（实测可用）。再加 F1 开口断言：切刀 `bounding_box()[1][2] >= thickness + 0.9`，且 `min_gap` 之外的"首击射线"断言（见 §1 修法第 3 条）。 | 升级，替代 v0.2 六道守卫 |
| **D17'** | **新增：单把工具超过打印床时的策略**。硬约束：**单个凹槽必须完整落在一片内**，否则切缝会把槽劈成两个侧面开口，粘接后也无法使用。即 `工具最长边 ≤ min(打印尺寸X, 打印尺寸Y) − 2×边距`。v1 选 **A 方案：检测到超长 → 明确报错「该工具 280mm，超过你的打印尺寸 200mm，单槽无法分块」**，给出三个出路提示（缩小板/换大床/把该工具移出本板）。B 方案（穿槽 + 侧壁补条）与 C 方案（槽+两侧挡墙三段）留到 v2。 | 新增 |
| **D16'** | **新增：镜头畸变**（开源调研的核心发现）。手机广角在画面边缘 1–2% 桶形畸变，在 210mm 纸宽上就是 **2–4mm**——足以让所有 ±1.5mm 的努力归零。v1 做法：**可选的一次性棋盘格标定**（`cv2.calibrateCamera`，K/D 存后端配置），标定过就在 warp 前 `undistort`；没标定就按 EXIF 焦距近似，并在照片体检里按「畸变可能引入 X mm 误差」告警。**不做** ArUco 标记纸（要用户专门打纸，v1 不值）。 | 新增 |
| **D13'** | **新增：双输出**。同一份 `Board + Tool[] + pockets` 数据出两种文件：① STL（实心板 + 凹槽）；② DXF/SVG 1:1 平面图（凹槽轮廓 + 每槽深度标注 + 板外框）。DXF 用 `ezdxf` 写，增量约 80 行。**这是"不绑材料"的关键**——CNC/激光直接可用。 | 新增（用户 m00723：CNC 切割也行） |


### 3.1 v1.0 对 D1'/D6'/D8'/D14'/D15' 的修订，以及新增 D18'–D21'

> 每条都来自四路审核的具体反驳，不是润色。

| 编号 | 修订后的内容 | 为什么改 |
|---|---|---|
| **D1'（修订）** | 画布口径统一为 **2400×3270**（A4 竖，纸面占 `[150,2250]×[150,3120]`），横版 3270×2400。v0.3 的 §3 写 2400×3270、而 M0.4 的 DoD 写 2100×2970，二者矛盾；以 2400×3270 为准。**不向下游传 `px_per_mm`**，`mm_per_px` 恒 0.1。 | 审核 B①：口径不一致，下游是否 +150 偏移无法判断 |
| **D6'（修订）** | 手孔**按板厚选形态**，且**矩形板厚只允许 6 / 12 / 25 三档（默认 12）**——否则 `12 < thickness < 25` 落进无定义区间（v1.0 草案的默认 20 正好落进去）。**thickness ≤ 12 → `scoop` 斜坡**（与凹槽连通，坡宽 10–15mm、默认 12，坡角默认 45°，坡底 = 槽底，不受最小筋厚约束）；**thickness ≥ 25 → 竖直通孔**（断言 `hole.bounding_box()[0][2] ≤ 0.1`，即真的穿到板底）。理由：12mm 板凹槽深上限 10mm，2mm 筋隔开工具侧壁，指腹 15mm 伸到孔底也够不到工具——**竖直孔在 12mm 板上物理上不成立**。Gridfinity 板不适用三档（高度由 `heightU*7` 定），其"等效板厚"= `heightU*7 − 4.75`，判定用这个值。同时 `_auto_detect_finger_slots`（`cad_engine.py:407`）的 PCA 两端胶囊逻辑换孔型后会静默失效，M1.5 必须重写。 | 审核 D1 + 第二轮审核：默认 20 / Gridfinity 3U=21 都会落进空档 |
| **D8'（修订）** | 三档厚度（6/12/25）只约束**自定义矩形**。Gridfinity 的高度由规范决定：`height_mm = height_u * GRHU`（**不是现在的 `7u+5`**，3U 必须 = 21mm）。深度 clamp 分外形：矩形 `embed ≤ H−2`；Gridfinity `embed ≤ height_mm − GR_BASE_HEIGHT(4.75) − 2`，且**槽不得进入堆叠唇区域**。 | 审核 B⑥/D4：现有公式 3U=26 比标准高 5mm，摞不上；且按 H−2 会切穿锥台底座 |
| **D14'（修订）** | 分块保留，但：① **v1 直接禁用 Gridfinity 分块**（锥台底座/唇/磁孔按整板成型，切开后中间片的底座与唇全断，粘起来摞不上）；② 切缝所在筋厚阈值从 2mm 提到 **≥4mm**（2mm 筋切完每侧只剩 1mm，粘接面太薄）；③ 定位销**水平**从切缝面钻入，`销长 = 2×孔深 − 1mm`，可落缝筋厚 ≥5mm（φ4）或改 φ3×6——φ4×8 的**竖直**盲孔在 6mm 板上物理上不可能，在 2mm 筋上会破进槽。 | 审核 D5/R5：D14' 与 D15'/D8' 互斥 |
| **D15'（修订）** | 板外形仍是两种，但"倒角"拆成**三个独立参数**，字段名一律 camelCase（与 SDS §3.1 对齐，旧名 `slot_chamfer`/`base_edge_roundover`/`corner_r` 全部作废）：**`slotChamfer`**（槽口插入导向，默认 1.5，D4' 已有）、**`baseEdgeRoundover`**（板顶沿外框一周的圆角，默认 0 = 关，此前无定义）、**`cornerR`**（板在 XY 平面的四角半径，默认 5，M1.6 已有）。三者独立 UI、独立几何。**板厚 `thickness` 只有 6 / 12 / 25 三档（默认 12）**，因为它决定手孔形态。 | 审核 D2：v0.3 的"倒角"混指三件事，`base_chamfer` 在 §3 无任何定义，UI 无法落地 |
| **D18'（新增）** | **几何真源唯一 = 稠密点环**（纸面 mm、y-down、外环 CCW / 内环 CW）。`primitives`（line/arc）只是**渲染视图**，`/simplify-contours` 从"数据源"降级为"显示优化建议"。任何写回真源的操作都必须回到点环。 | 审核 B③：折线 / line-arc / find_contours 三份并存，SDS 无法决定存哪一份 |
| **D19'（新增）** | **API 契约以 SDS §3/§4 为唯一真源**（第二轮审核：计划与 SDS 各写了一套字段名，必须只留一套）。要点：**JSON 一律 camelCase**；请求 = 完整 `Project`（`{schemaVersion, paper, tools[], board}`），`Tool` 字段为 `outer: Vec2[]` / `interior: Vec2[][]` / `fingerHoles: FingerHole[]` / `depthOverride` / `chamferOverride`；响应 = `data.pieces[{index, name, stlBase64, bboxMm, volumeMm3}]` + `data.summary` + `data.checks[]`，拒绝走统一信封 `error.code`（不是顶层 `errors[]`）；`error.code` 枚举见 SDS §4.0。**`from_dict` 遇未知字段必须 400 `SCHEMA_UNKNOWN_FIELD`，不许静默忽略**。 | 审核 A②/B④ + 第二轮审核：两套字段名 + "未知字段忽略"会让参数静默消失 |
| **D20'（新增）** | **undo 作用域**：zundo 的 `partialize` 只含 `board/tools/cadParams`；`step`、`cadResult`、`uiState` 不进栈；`MaskEditor` 保留自己的私有 history（`MaskEditor.tsx:720-745`）；一次手势 = 一条记录（preview/commit 分离）。 | 审核 B⑤：`src/app/store.ts:114-136` 里 `step` 与几何同处一 store，不加限定 Ctrl+Z 会连步骤一起回滚 |
| **D21'（新增）** | **`schemaVersion` 迁移策略**：版本不等则按迁移表逐级升；缺迁移表则丢弃草稿并提示"旧草稿不兼容，已清空"，**不做静默兼容**。 | 审核 B⑦：M1–M3 会陆续加 `chamfer/shape/depth_override/pieces`，字段一改草稿就报错 |

---

## §4 里程碑与 DoD

> **§4 是阻塞图，不是串行甘特图。** 关键阻塞边：`0.4 → 0.3`（没有 10px/mm 就没有 mm 坐标，v0.3 把顺序排反了）、`0.2 → 全部 3D 任务`、`1.0（后端多轮廓）→ 1.6 / 2.4`、`1.1 → 2.3 的后端部分`、`0.7 → 0.6`（校验库就是 golden test 的断言库）。
> **可并行**：3.4 DXF、3.2 分块、3.3 试切件只依赖数据模型（D7'），M1 一开工即可并行。
> **DoD 一律可离线复现**：不出现"打印出来用卡尺量""在 CAD 里量 DXF""实物扣底座"。实物验证集中到 M5「用户验收清单」（不占工期）。

### M-1 — 环境冒烟（0.5 天，排在一切之前）

| # | 任务 | DoD |
|---|---|---|
| -1.1 | `scripts/smoke_geometry.py`：venv 建好后用合成 100×20mm 矩形跑一次 `generate_insert` | (a) `slot_cutter.bounding_box()[1][2] > thickness + 0.9`；(b) **从 `(0, 0, thickness + 10)` 竖直向下 raycast，首击 z ≈ `thickness − embed`，而不是 `thickness`**（射线原点必须落在槽**内部**，不能落在槽角顶点上，否则边界命中不稳定）；(c) 槽长 100 ± 1mm |

> 这一条同时证明三件事：环境能跑、F1 的开口为真、DoD 可离线复现。**没有它，后面每条 DoD 都可能被"静默失败"骗过。**

### M0 — 让后端能跑 + 打通毫米链（2.5 天）

| # | 任务 | DoD |
|---|---|---|
| 0.1 | **重写 `python_backend/requirements.txt` 的 pin**（不是"补四个包"）：`numpy>=2.1`、`shapely>=2.2`、`manifold3d>=3.5.4`、`trimesh>=4.4`、`opencv-python-headless>=4.11`、fastapi、uvicorn、pillow、python-multipart。**删除** `cadquery==2.8.0`（只被 `cad_engine.py:803` 懒加载，服务已砍的 STEP）与 `scipy`（无调用点）；同一任务删 `/generate-step` 端点 | `uvicorn main:app` 能起（**必须先 `cd python_backend`**，`cad_engine.py:59` 是裸 `from models import`）；`pytest` 能收集到用例；`import cv2` 不报 `libGL.so.1`。**不验证 success/volume**——那正是密闭空腔的特征 |
| 0.2 | **修 z 基准**：槽切刀改为 `z ∈ [thickness − embed, thickness + 1]`；手孔切刀用同一条断言覆盖 | summary 输出 `slot_bounds` / `base_bounds`；pytest 断言 `slot_bounds[1][2] >= thickness + 0.9`，且 `base.section_plane(plane_origin=[0,0,thickness−0.01], plane_normal=[0,0,1])` 在槽投影区域内无面（trimesh 的参数名是 `plane_origin`/`plane_normal`，不是 `z=`） |
| 0.3 | **先删错的那行**：`cad_engine.py:582` 的 `scale = min(base_size_x/840, base_size_y/1188)`（真正的缩放元凶），连同 `:575` 的 `840.0/1188.0`、`:585` 的 `poly_mm -= center` 一起处理，改成 `mm = px * 0.1`，原点取纸面坐标 | 100mm 长的合成轮廓 → **切刀长 = 100.0 ± 0.1mm**（M0 阶段尚无 clearance 环节，必须精确等于 100，不许出现 100.8）；**同一轮廓在 200mm 板与 300mm 板上结果完全一致**（防 scale 残留）；截面积相对误差 ≤ 0.1%（不是"±0.05mm² 且 ±2×clearance"那种量纲互斥的写法；容差总表见 SDS §10.3） |
| 0.3b | **新增：primitives → 有序闭合环**。`_primitives_to_2d_polygon`（`cad_engine.py:503-521`）把 line/arc/polyline 的点**按出现顺序拼接**，不保证闭合、不保证方向、不带内环 | 随机简单多边形往返（polygon → primitives → polygon）后 `shapely.equals_exact(tol=1e-6)`；带 1 个内环的多边形往返后 `holes` 数量与面积不变 |
| 0.4 | 移植 D1'（固定 10px/mm） | `/detect-paper` 返回 `warped_image`，尺寸 = **2400×3270**（A4 竖）/ **3270×2400**（横），纸面占 `[150,2250]×[150,3120]`；响应**不含** `px_per_mm` |
| 0.5 | 移植照片体检（`photo_checks.py`） | 合成近距离照片返回 `warnings[]`，含 `camera_too_close` 与估算高度；`paper_out_of_frame`、`extreme_perspective` 各一条用例 |
| 0.6 | golden test（唯一回归锚） | 合成照片 → STL，槽尺寸误差 **≤ 0.5mm**（原写 1.0 与 SDS §10 的 0.5 冲突，统一取 0.5）；同时断言 `len(slots) == len(tools)`（防 R7 的静默失败）；**再加一条非对称 fixture**（L 形，左下伸 10×5 凸耳）断言凸耳落在 y 的负侧——只用水密/体积测不出竖直镜像 |
| 0.7 | **新增：`geometry/validate.py`** 落地 D12' 两级自检 | L0：`shapely.is_valid` + `explain_validity` + `buffer(0)`；L1：`is_watertight` + `is_winding_consistent` + `manifold.status()` + `genus()` + 体积 ±2% + `min_gap()` 量壁厚。**两个重叠立方体的反例必须被判失败**。作为 0.6 的断言库 |
| 0.8 | **新增：静默失败收口**。范围**只限新代码 + `main.py` 信封层**：新模块禁止 `except: print(...)`，异常一路抛到路由层转成 `error.code`。**旧 `cad_engine.py` 已冻结（SDS §7.1），只允许在它的 `except` 分支里加一行 `errors.append(...)` 计数（不改逻辑、不改返回值）**，M1 换引擎后整体作废 | 用例：故意让 1 个槽失败 → 接口返回 `success:false` 且 `error.code` 非空。**不再承诺"改掉 17 处"**（第二轮审核：SDS 宣布冻结的文件不能派任务去改） |

### M1 — 几何内核移植（3.5 天）

| # | 任务 | DoD |
|---|---|---|
| 1.0 | **新增：后端多轮廓**（原 2.4 的后端部分）。`extract_tool_contours_v26` 只返回**单个最大连通轮廓**（`sam_tool_contour.py:150`、`:226`），改为返回 `List[Contour]`，每个带自己的 `holes` | 一张放了 3 把工具的照片 → 返回 3 个外环 + 正确内环数 |
| 1.1 | 移植槽切刀 + 倒角锥台（§2.1 #4） | 锥台占 `z ∈ [thickness − chamfer, thickness]`、顶面外扩；在 `z = thickness − 1e−6` 与 `z = thickness − chamfer` 两处取 section（**高差必须恰好等于 chamfer**，原写 `thickness−0.1` 会让期望值差 0.2mm 而必红），开口宽差 = `2×chamfer` ±0.1mm |
| 1.2 | 移植间隙 + 平滑管线（§2.1 #3） | 间隙 0.4mm 时槽比轮廓外扩 0.4±0.05mm；**顺序断言**：`prepare_for_generation` 必须"先 simplify/smooth、后 clearance" |
| 1.3 | 移植内环链路（§2.1 #7 + F4 五处断点全改） | **用一张真实开口扳手照片端到端跑出中心孔**——"圆环基元能过"不算通过（否则 `fill_holes` 与 `RETR_EXTERNAL` 一行不改也能过） |
| 1.4a | Gridfinity 底座剖面 | 底座高 4.75、顶面 chamfer 推导值与 `cq-gridfinity` 常量表一致（±0.01） |
| 1.4b | 堆叠唇五段剖面 | 逐段 bbox 高度 **2.6 / 1.2 / 0.7 / 1.8 / 1.9**（顺序 = `LIP_D4, LIP_D3, LIP_D2, LIP_D1, LIP_D0`），累计 **8.2**（各段 ±0.05、总和 ±0.05）。真源是 tracefinity 常量，**不是** cq-gridfinity 的斜边写法（那套算出 8.09，会永久红） |
| 1.4c | 磁吸孔 + 高度公式 | 孔心距**格角** `MAGNET_INSET=4.8`（不是格心），相邻格孔心距 26mm；`height_mm = height_u * GRHU`（3U 必须 = 21mm），磁孔深 2.4，角 R 4.0 |
| 1.5 | 移植手孔 5 形态 + 倒角（§2.1 #5/#6）+ **重写 `_auto_detect_finger_slots`** | 6 种形状（含新增 `scoop`）各生成一次且开口；**按厚度选形态**：rect 板 `thickness ≤ 12` → scoop 且与凹槽**连通**（`CrossSection` 相交面积 > 0），`thickness ≥ 25` → 竖直孔且 `hole.bounding_box()[0][2] ≤ 0.1`；Gridfinity 板用等效厚度 `heightU*7 − 4.75` 判定；sphere 形态断言 `cutter.bounding_box()[0][2] ≥ 0`（不许穿透板底） |
| 1.0b | **新增：三个板级参数进数据模型**（从原 2.3a 提前）。`BoardConfig` 增加 `cornerR`（默认 5）、`baseEdgeRoundover`（默认 0）、`slotChamfer`（默认 1.5），进 Pydantic API schema 与 `summary.paramsEcho` | 三个字段在 `/api/generate` 请求里可传、在响应 `summary.paramsEcho` 里原样回显；未知字段返回 400 `SCHEMA_UNKNOWN_FIELD` |
| 1.6 | **自定义矩形外壳**（D15' ①）：并集 bbox + 边距 + `cornerR` + `baseEdgeRoundover` + 板厚 | 给定 **3 个 polygon 输入**（不依赖 M2 的交互）→ 板外框 = 并集 bbox 各边 +8mm；`cornerR`、`baseEdgeRoundover` 与参数一致 |

### M2 — 交互层（3 天）

| # | 任务 | DoD |
|---|---|---|
| 2.1 | 移植 `PolygonEditor` + `useHistory`（§2.2 #1/#2/#4），接入 D18' 点环真源 | 能拖点、边上插点（插入即拖）、删点（到 3 个拒绝）；Ctrl+Z / Ctrl+Shift+Z；**压住鼠标拖 3 秒只产生 1 条 undo** |
| 2.2 | 移植 `ToolEditor` 手孔编辑（§2.2 #3） | 能加/删手孔、拖动、改宽度/深度/旋转、选 6 种形状；`thickness ≤ 12` 时形状选择器只给 `scoop` 系 |
| 2.3a | **端到端验收**（字段本身已由 1.0b 建好，此处只做联调）：每个参数单独改大 1mm，观察 `summary.paramsEcho` 与网格 bbox 的相应变化 | 三个参数各有一条用例；改 `cornerR` → 板 bbox 不变而圆角处顶点数变化；改 `baseEdgeRoundover` → 只在顶面外圈出现新面 | 
| 2.3b | **前端**：`ParamsPanel.tsx` 三个滑块绑定 `cornerR` / `baseEdgeRoundover` / `slotChamfer`（`foam` 目前在 `src/api/toolProcessor.ts:288` 是 `Record<string, any>`，需补类型） | 三个滑块各有独立可辨效果；`slotChamfer` 用**网格法向统计**：45° 面面积占比与 `2×chamfer×周长` 相符（±10%） |
| 2.4 | **前端多工具**：一张图 N 个轮廓 → 列表 → 一次生成 | 一张 A4 放 3 把工具，点生成得到 3 个槽的板；删除其中一把后重生成只剩 2 个槽 |

### M3 — 拍照端与产出（3.5 天）

| # | 任务 | DoD |
|---|---|---|
| 3.1 | 纸角四角手拖（§2.2 #6） | 自动检测失败时能手动拖，且 warp 用新手拖的角（`CalibrationPanel.tsx:66-79` 现在是只读） |
| 3.2 | **模型分块**（D14' 修订版） | 300×200 板 + 200×200 限制 → 出 2 片；两片各自的 `bounds` 相加 = 原板 bbox（±0.01）；切缝筋厚 ≥4mm；Gridfinity 板请求分块直接返回 `error_code = GRIDFINITY_SPLIT_UNSUPPORTED`（与"找不到 ≥4mm 筋"的 `NO_SPLIT_RIB` 分开） |
| 3.3 | 试切件生成按钮 | 一键出 40×40×10 三档间隙（0.2/0.4/0.6）试切件 STL，三件同一次请求 |
| 3.4 | **DXF / SVG 1:1 导出**（D13'）。**默认 y 翻转（与照片同向）**，翻转开关默认 `true` | 重新读回 DXF（`ezdxf.readfile`）后：每个凹槽 LWPOLYLINE 面积 = 设计值 ±0.1mm²；`$INSUNITS == 6`；板外框闭合；每个槽有 depth 标注；**非对称点断言**：输入顶点 `(12.3, 45.6)` → 读回必须是 `(12.3, 251.4)`（= 297 − 45.6，±0.01）——面积对镜像完全不敏感，只有这条能抓住翻转做反 |

### M4 — 收尾（1.5 天）

| # | 任务 | DoD |
|---|---|---|
| 4.1 | 持久化：localStorage 全量草稿 + `schemaVersion`（D21'） | 刷新页面后 board/tools/params 全在；手改 `schemaVersion` 为 999 后不崩、按规则走降级 |
| 4.2 | 错误边界 | 任一 API 抛错时 UI 有可读提示 + 重试按钮，不出现白屏；守卫触发（`TOOL_OUT_OF_PAPER` 等）有明确出路提示 |
| 4.3 | 端到端冒烟 | 一条命令跑完 A4 照片 → STL + DXF，两份产物都落盘；失败时非零退出 |
| 4.4 | 文档纠偏（附行号） | 修 `README.md:165`（撤销/重做真实状态）、`PRODUCT_REQUIREMENTS.md:139-201`（STEP AP242 "可二次编辑"是假的、`F2.5` 标注矛盾）、`DEVELOPMENT_GUIDE.md` 的 `useWorkflow` 与实际不符 |

**总计：约 14.5 人日**（v0.3 是 16，v0.2 是 26–37）。
**v0.3 → v1.0 的减法**（v0.3 基线实为 15.5：原表 16 里含 1.4 拆分后重复计数的 0.5）：砍畸变标定 −0.5、打印反馈回路 −0.5、first-fit 自动排 −0.5、亚像素精修 −1.0、M4 文档减半 −0.5，**合计 −3.0**；**加法**：M-1 冒烟 +0.5、0.3b 闭合环 +0.5、0.7 校验库 +0.5、1.0 后端多轮廓 +0.5、1.0b 三参数进 schema +0.5，**合计 +2.5**。15.5 − 3.0 + 2.5 = **15.0**；再扣掉"1.6 因参数提前而不再返工"的 0.5 → **14.5**。里程碑相加 `0.5+2.5+3.5+3+3.5+1.5 = 14.5`，两套账一致。

## §5 明确砍掉（v2 再谈）

| 条目 | 理由 |
|---|---|
| 自研 2.5D loft 内核（D4.1/D4.2/D4.3） | tracefinity 已解决；自研会在 V 形内凹口产生层间折叠且守卫抓不到 |
| STEP / 真 B-Rep / OCCT golden reference | 用户只打印；现在的 STEP 是网格包壳，PRD 的"可二次编辑"是假的 |
| 完整自动排版（STRtree/NFP/增量锁定） | 3–5 把工具手拖更快 |
| 18 件 × 3 厚度 DoD 矩阵 | 打印成本 > 开发成本 |
| Foam 板中空 + 网格肋 + 用料工时估算 | 与深槽算术互斥（§3 D8'） |
| 3MF 多色 / 文字标签 / SVG 出图（DXF 已够） | 个人自用无意义 |
| IndexedDB 项目画廊 | localStorage 够 |
| 燕尾拼缝 | 改用圆柱定位销（D14'），精度要求低得多 |

| 畸变棋盘格标定（原 M3.6） | 一次性标定对个人自用失败率高，S0 只承诺 ±1.5mm；改为照片体检里按 EXIF 焦距**告警**"畸变可能引入 X mm" |
| 打印反馈回路（原 M3.2） | 与 D9'「浏览器本地记住上次间隙」重复 |
| first-fit 自动排（原 M2.5） | 一张 A4 放 3–5 把，手拖 + 旋转 90° 更快；只保留重叠高亮。**D3' 与本表已同步删除，M2 不再有该项** |
| 亚像素精修（原 M2.6，降级为 v1.1） | 其 DoD 测的是**重复性**不是**精度**；v1 保留现有 DP 抽稀（`eps=0.3mm`） |
| Gridfinity 板的分块（D14' 修订） | 锥台底座/唇/磁孔按整板成型，切开后中间片全断，粘起来摞不上 |

---

## §6 许可证与合规（v0.2 零字提及，必须补）

- tracefinity 是 **MIT**（`Copyright (c) 2024 Tracefinity Contributors`）。
- 移植代码必须在文件头保留原始版权与许可声明，并在仓库根加 `NOTICE`（或 `THIRD_PARTY_LICENSES.md`）说明"几何内核部分移植自 tracefinity/tracefinity，MIT"。
- 本项目自身许可证需先确认（`Y:/.../toolmanagement-web/LICENSE` 存在，内容待核）。

---

## §7 仍未决、需要用户拍板的问题

| # | 问题 | 为什么必须问 |
|---|---|---|
| ~~Q1~~ | ~~"Foam 模式"到底是什么？~~ **已决（用户 m00723）**：只管生成模型，不管材料与工艺。实心板 + 凹槽；打印（PLA/PETG/TPU）与 CNC 切割共用同一份几何，STL 与 DXF 双输出。**不做中空、不做材料相关策略。** | 已决，见 §3 D8'/D13' |
| ~~Q2~~ | ~~每把单独拍还是一次拍多把？~~ **已决（用户 m00751）**：一张 A4 放 1..N 把，全部必须在纸内；超过 A4 的工具不做。 | 已决，见 §3 D2' |
| ~~Q3~~ | ~~圆弧基元能不能只读~~ **已决（m00776「按你的推荐」）**：v1 圆弧只读，进入顶点编辑时降级为折线并提示。 | 已决 |
| ~~Q4~~ | ~~间隙默认值~~ **已决**：默认 0.4mm + 试切件校正。 | 已决 |
| Q5 | 一块板默认按 3–5 把工具设计（超过手拖），可以吗？ | 决定 D3' 要不要扩 |
| ~~Q7~~ | ~~单把工具比打印床长怎么办~~ **暂按 A 方案（D17'，直接报错）实现**；如用户后续要 B/C，作为增量。 | 已定 v1 默认 |
| ~~Q6~~ | ~~导出范围~~ **部分已决（m00723）**：STL + DXF/SVG 都要（D13'）。3MF 仍推迟。 | 已决 |

---

## §8 下一步

1. **计划 v1.0 定稿**（本文件）→ 用户过一遍 §7 只剩 Q5 未决，不阻塞开工。
2. **SDS 按 v1.0 修订**：吸收 §3.1 的 D18'–D21'、§2.3 的六条约定、§4 的任务编号（0.3b / 0.7 / 0.8 / 1.0 / 1.4a-c / 2.3a-b），补 `/generate-cad` 的 `{pieces, errors}` 与 `error_code` 枚举。
3. **第二轮审核已完成**（closure + cold-read 双视角，2026-11-03）：计划 v1.0 与 SDS v1.0 的 28 条一轮问题中 15 条 CLOSED、13 条 PARTIAL，另发现 23 条新问题（z 原点两套、`to_board_frame` 符号、契约三套字段名等）。**均已在本版（计划 v1.1 / SDS v1.1）逐条修完**，见两文件头部的"第二轮修订"清单。
4. 新会话按 SDS 实施：主会话调度 + 子 agent 编码 + 独立审核；**开工第一件事是 `git rm -r --cached node_modules && git commit && git tag pre-m0`**（当前工作区 79 项未提交、`node_modules` 被跟踪 10369 个文件，没有可回滚基线）。
