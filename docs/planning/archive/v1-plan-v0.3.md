# Toolmanagement-web 开发计划 v0.3

> 状态：**推翻 v0.2 的主线**。v0.2 已归档，仅其"问题诊断"部分继续有效。
> 依据：三轮独立红队复审（产品/几何/交付）+ tracefinity 源码全量通读。
> 日期：2026-11-03
> 规模：**16 人日**，M0–M4 五个里程碑

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

**修法**：槽切刀改为从板顶向下切，且顶面过切 1mm，`z ∈ [H/2 − embed_depth, H/2 + 1]`。手指槽同理（`cad_engine.py:359`、`:368` 现在也是从 z=0 起）。

**必须新增的机检断言（M0 DoD，缺一不可）**：
1. `slot_cutter.bounds[1][2] >= base_top_z + 0.9`（切刀必须刺出顶面）
2. 取 `base.section_plane(origin=[0,0,H/2−0.01], normal=[0,0,1])`，断言槽区域内**没有面**（等价于：顶面在该区域是空的）

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
| 4 | 槽切刀 + 倒角锥台 | `stl_generator_manifold.py:809-966` | ~160 | **z 基准改成本项目的"板顶向下切"**（这是移植时唯一必须重写的部分） | 中 |
| 5 | 手指孔 5 形态 | `stl_generator_manifold.py:969-1039` | ~70 | 原样；坐标从像素转 mm | 易 |
| 6 | 手指孔倒角 | `stl_generator_manifold.py:1042-1118` | ~75 | 原样 | 易 |
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
| 7 | 排版（first-fit） | `frontend/src/lib/drawerLayout.ts:197-283`（含 `unfittedIds` 回传） | 只抄 UX 模式，不做 NFP | 易 |

### 2.3 移植时必须先统一的三个约定（不统一会静默出错）

1. **y 轴方向**：tracefinity 在 `stl_generator_manifold.py:896`、`:984` 写的是 `-(p[1] + offset_y)`（SVG y-down → CAD y-up）。本项目像素坐标系直接就是图像 y-down，若也取负会上下翻转。
2. **z 原点**：tracefinity 底面 z=0 向上（`wall_top_z`）；本项目居中 ±H/2。所有 `translate` 的 z 分量要重算——**这正是 F1 的来源，不要在移植时再犯一次**。
3. **数据结构**：tracefinity 用 Pydantic `GenerateRequest`；本项目是 `python_backend/models.py` 的 dataclass，缺 `clearance`、`interior_rings`、`depth_override`，必须先补齐再移植。

---

### 2.4 除 tracefinity 外，另外这 10 处该抄的（2026-11-03 四路开源调研结论）

> 许可证逐个核对（GitHub API / LICENSE 原文 / PyPI 元数据）。**只列能进 MIT 项目的。**

| 需求 | 抄哪个（star / 许可） | 抄什么（具体到文件/函数） |
|---|---|---|
| **Gridfinity 数值** | `michaelgale/cq-gridfinity` 205★ **MIT** | `cqgridfinity/constants.py` **整份拷进来当唯一真源**：`GRU=42`、`GRU_CUT=42.2`、`GRHU=7`、`GR_BASE_HEIGHT=4.75`、`GR_STR_H=1.8`、底座剖面 `((TOP_CHAMF*√2,45°),1.8,(CHAMF_H*√2,45°))`、唇剖面 `((1.6√2,45°),1.2,(0.7√2,-45°),1.8,(1.3√2,-45°))`、`GR_HOLE_D=6.5`、`GR_HOLE_H=2.4`、`GR_HOLE_DIST=13`、`GR_RAD=4`、`GR_FILLET=1.1`。**推导式也要抄**（`GR_BASE_TOP_CHAMF = 4.75 − CHAMF_H − 1.8`）——只抄结果数字，改一个尺寸就崩。 |
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

## §3 修订后的决策（D1'–D16'）

| 编号 | 决策 | 相对 v0.2 的变化 |
|---|---|---|
| **D1'** | 透视校正后输出**固定 10px/mm** 的图。A4 竖向 → 纸面 2100×2970 px，四周各留 150px（15mm）安全边，画布 2400×3270 px，纸原点在 (150,150)。`mm_per_px` 恒为 0.1，**不向下游传递 `px_per_mm`**。源图长边 < 1800px 时拒绝并提示重拍。**不做**"工具超出纸张"的全视野扩展画布。 | 推翻 v0.2 的"自适应 ppmm 穿透 5 层"；简化 tracefinity 的全视野 warp |
| **D2'** | **一张照片拍 1..N 把工具，全部必须完整落在 A4 内**（用户 m00751：超过 A4 的工具没有收纳意义，直接挂墙）。一次提取多个轮廓、一次生成一块板。**校验**：任一轮廓的外接框触到纸边界（距边界 < 3mm）→ 直接报错"工具超出 A4，请更换工具或分次拍摄"，**不静默截断**。 | 推翻 v0.2 的"一照一工具、超 A4 手动建槽"；也推翻此前"支持纸外工具"的想法 |
| **D3'** | 排版只做：凸包重叠检测 + 手动拖拽/旋转 90° + first-fit 自动摆放（面积降序）+ 未放下高亮。**不做** STRtree/NFP/0.05mm 强制重叠。 | 砍掉 v0.2 的 D3 四件套 |
| **D4'** | 几何内核 = manifold3d。倒角 = `CrossSection.offset(JoinType.Round)` + 单层 `extrude(scale_top)` 锥台，与直筒切刀并集。**不做** miter 逐顶点偏置、medial axis、8~16 层曲线表、二分求 max d。**五个实测坑（照抄必踩）**：① `extrude(scale_top=)` 绕**原点**缩放、不是质心 → 拔模前必须 `cs.translate(-cx,-cy)`；② 孔的绕向必须与外轮廓相反（外 CCW / 孔 CW），否则孔被 union 吃掉（实测体积 4000 而非 3000）；③ `offset` 的 JoinType **只作用于凸角**，凹角永远 miter；④ 连续多次 offset 之间插 `cs.simplify(1e-3)`；⑤ 床分割用 `Manifold ∩ Box`，**不要用** `trimesh.slice_plane(cap=True)`（封口缺面，issue #2299）。 | 砍掉 v0.2 的 D4.1/D4.2/D4.3；补实测坑 |
| **D5'** | 轮廓编辑：顶点拖 / 边上插点 / 删点（下限 3，拒绝）/ 整体旋转 / 框选缩放 / 撤销重做。**圆弧基元 v1 只读**：一旦进入顶点编辑，arc 降级为折线并在 UI 明确提示。 | v0.2 未定义 arc 策略 |
| **D6'** | 手槽改用**竖直手孔**（sphere / cylinder / square / rectangle / filleted_rectangle），每孔独立 `depth_override`、`rotation`、口部倒角。**放弃 v0.2 的 scoop 同深度外凸模型**。 | 推翻 D6 |
| **D7'** | 数据结构 `Project → Board → Tool → FingerHole`（+ `interior_rings`）。M0 只做 localStorage 全量草稿 + `schemaVersion`，完整持久化等几何定型。 | v0.2 要求提前定完整 schema |
| **D8'** | 厚度三档（6 / 12 / 25mm 全高）+ **`embed_depth ≤ height_mm − 2` 强制 clamp**。板体**永远实心**（不中空、不加肋、不做薄壳）——v0.2 的 D10 薄壳与深槽算术互斥：2.4mm 顶板 + 任何 >2.4mm 的槽 = 打穿。材料无关：PLA / PETG / TPU / 泡沫 / 木板，同一份几何。 | 推翻 D10 的薄壳/肋/工时估算 |
| **D9'** | 间隙：滑杆（0.2–1.0mm，默认 0.4）+ **40×40×10 试切件**（打 0.2/0.4/0.6 三档）。浏览器本地记住上一次的值。**不做**材料数据库、不做按打印机预设、不做切片参数。 | 保留，删掉"公差非对称 +1.5/−0.3" |
| **D10'** | 只做**几何**校验：`is_watertight`、凹槽之间/凹槽与板边的**最小筋厚 ≥ 2.0mm**、`embed_depth ≤ height − 2`。**不做**层高/壁数/填充/支撑/床温/G-code——那是切片软件的事，本项目完全不管。不做用料与工时估算。 | 砍 |
| **D14'** | **新增：模型分块**（用户 m00776 明确要）。参数「最大打印尺寸」X/Y/Z（默认 220×220×220，用户可改）。板任意一边超出 → 自动裁成 nx×ny 片，每片独立 STL。**切缝只允许落在凹槽之间的实心筋上，绝不穿槽**（穿槽会把凹槽切成侧面开口，工具会滑出来）；该方向找不到任何 ≥2mm 的筋 → 拒绝并提示「请换更大打印机或缩小板」，不静默生成残缺件。片间用**圆柱定位销**（φ4×8 盲孔，两侧各一孔）而不是燕尾——销的容差好控制，燕尾要精确打印才能插。Gridfinity 板的分块线吸附到 42mm 网格。Z 超限只告警不切。 | 新增（v0.2 曾推迟） |
| **D15'** | **新增：板的两种外形，都做。** ① **自定义矩形**：工具并集外接框 + 用户填的边距（默认 8mm）+ 可选圆角；② **Gridfinity**：按 42mm 网格向上取整，带标准底座/堆叠唇/磁吸孔。切换时工具轮廓与手孔位置**原样保留**，只换外框与底座。 | 新增（用户 m00776：两个都要） |
| **D11'** | 精度只承诺 **S0（±1.5mm）**。拍照指引 + 照片体检（EXIF 反算相机高度、纸出框、极端透视三条告警）。**不做** 3×3×2 的 18 件 DoD 矩阵。 | 砍 S1/S2 |
| **D12'** | **新增：两级自检**。L0（2D，最便宜）：`shapely.is_valid` + `explain_validity` + `buffer(0)`——90% 的坏几何死在这一层。L1（3D）：`trimesh.is_watertight` + `is_winding_consistent` + `manifold.status()` + `genus()` + 体积与解析值 ±2% + bbox 对格位。**`is_watertight` 单独用等于没查**——实测两个重叠立方体拼起来仍然 watertight、`status()` 仍返回 `NoError`。壁厚用 `Manifold.min_gap(other, search_length)` 直接量（实测可用）。再加 F1 开口断言：切刀 `bounds[1][2] >= H/2 + 0.9`。 | 升级，替代 v0.2 六道守卫 |
| **D17'** | **新增：单把工具超过打印床时的策略**。硬约束：**单个凹槽必须完整落在一片内**，否则切缝会把槽劈成两个侧面开口，粘接后也无法使用。即 `工具最长边 ≤ min(打印尺寸X, 打印尺寸Y) − 2×边距`。v1 选 **A 方案：检测到超长 → 明确报错「该工具 280mm，超过你的打印尺寸 200mm，单槽无法分块」**，给出三个出路提示（缩小板/换大床/把该工具移出本板）。B 方案（穿槽 + 侧壁补条）与 C 方案（槽+两侧挡墙三段）留到 v2。 | 新增 |
| **D16'** | **新增：镜头畸变**（开源调研的核心发现）。手机广角在画面边缘 1–2% 桶形畸变，在 210mm 纸宽上就是 **2–4mm**——足以让所有 ±1.5mm 的努力归零。v1 做法：**可选的一次性棋盘格标定**（`cv2.calibrateCamera`，K/D 存后端配置），标定过就在 warp 前 `undistort`；没标定就按 EXIF 焦距近似，并在照片体检里按「畸变可能引入 X mm 误差」告警。**不做** ArUco 标记纸（要用户专门打纸，v1 不值）。 | 新增 |
| **D13'** | **新增：双输出**。同一份 `Board + Tool[] + pockets` 数据出两种文件：① STL（实心板 + 凹槽）；② DXF/SVG 1:1 平面图（凹槽轮廓 + 每槽深度标注 + 板外框）。DXF 用 `ezdxf` 写，增量约 80 行。**这是"不绑材料"的关键**——CNC/激光直接可用。 | 新增（用户 m00723：CNC 切割也行） |

---

## §4 里程碑与 DoD

### M0 — 让后端能跑 + 打通毫米链（2 天）

| # | 任务 | DoD |
|---|---|---|
| 0.1 | 补 `python_backend/requirements.txt`（trimesh / manifold3d / shapely / scipy），`HAS_MANIFOLD=False` 改为启动即失败 | `uvicorn main:app` 能起；`/generate-cad` 用默认参数返回 `success:true` 且 `volume_mm3 > 0` |
| 0.2 | **修 z 基准**：槽切刀改为 `z ∈ [H/2 − embed, H/2 + 1]`；手指槽同理 | `slot.bounds[1][2] >= H/2 + 0.9`；`base.section_plane(z=H/2−0.01)` 在槽区域无面 |
| 0.3 | 删 `cad_engine.py:576` 的 `840.0/1188.0` 与 `:584` 的 `poly_mm -= center`，改用 D1' 的 mm 坐标 | 打印一把 100mm 的扳手，STL 里槽长 = 100 ± 1.5mm（卡尺） |
| 0.4 | 移植 D1'（固定 10px/mm + 全视野 warp） | `/detect-paper` 返回 `warped_image` 且尺寸 = `2100×2970`（A4 竖）或 `2970×2100`（横）；`/correct-image` 返回 `mm_per_px: 0.1` |
| 0.5 | 移植照片体检 | 低光照/近距离照片返回 `warnings[]`，含 `camera_too_close` 与估算高度 |
| 0.6 | 一个 golden test | `pytest` 能跑通，断言合成照片 → STL 的槽尺寸误差 ≤ 1.0mm |

### M1 — 几何内核移植（3.5 天）

| # | 任务 | DoD |
|---|---|---|
| 1.1 | 移植槽切刀 + 倒角锥台（§2.1 #4） | 参数 `chamfer=1.5` 时，STL 剖面图能看到 45° 锥面；`chamfer=0` 时剖面是直筒 |
| 1.2 | 移植间隙 + 平滑管线（§2.1 #3） | 间隙 0.4mm 时，槽比工具轮廓外扩 0.4±0.05mm（用 `shapely.area` 差验证） |
| 1.3 | 移植内环链路（§2.1 #7 + F4 五处断点全改） | 一个带 6mm 中心孔的圆环工具，生成的槽中心有 6mm 的料柱，且 STL `is_watertight` |
| 1.4 | 移植 Gridfinity 底座 + 唇 + 磁吸孔（§2.1 #9） | 打出来的盒子能扣进标准 Gridfinity 底座、能被另一只盒子摞上；磁孔孔心距 = 26mm（相对格心 ±13mm） |
| 1.5 | 移植手孔 5 形态 + 倒角（§2.1 #5/#6） | 5 种形状各生成一次，都能布尔减成功且开口 |
| 1.6 | **自定义矩形外壳**（D15' ①）：工具并集 bbox + 边距 + 圆角 + 板厚 | 3 把工具生成的板外框 = 并集 bbox 各边 +8mm；圆角与参数一致 |

### M2 — 交互层（4 天）

| # | 任务 | DoD |
|---|---|---|
| 2.1 | 移植 `PolygonEditor` + `useHistory`（§2.2 #1/#2/#4） | 能拖点、边上插点、删点（到 3 个拒绝）、Ctrl+Z / Ctrl+Shift+Z |
| 2.2 | 移植 `ToolEditor` 手孔编辑（§2.2 #3） | 能加/删手孔、拖动、改宽度/深度/旋转、选 5 种形状 |
| 2.3 | **参数面板加倒角**（`ParamsPanel.tsx`） | 两个滑块：`slot_chamfer`（0–3mm）、`base_chamfer`（0–3mm），改动后点生成能看见效果 |
| 2.4 | 多工具：一张图 N 个轮廓 → 一次生成 | 一张 A4 放 3 把工具，点生成得到 3 个槽的板 |
| 2.5 | 排版：拖拽 + 旋转 90° + first-fit | 拖到重叠时高亮冲突；"自动排"能把 3 把工具放下 |
| 2.6 | **亚像素轮廓精修**（不推翻 v26，只加一层）：mask → `GaussianBlur(3)` → `skimage.measure.find_contours(alpha, 0.5)` → `approxPolyDP(eps=0.3mm)` | 同一张图连跑 3 次，轮廓面积抖动 < 0.2mm²；直边上的顶点落在理想直线 ±0.05mm 内 |

### M3 — 拍照端与产出（4.5 天）

| # | 任务 | DoD |
|---|---|---|
| 3.1 | 纸角四角手拖（§2.2 #6） | 自动检测失败时能手动拖，且 warp 用新手拖的角 |
| 3.2 | 打印反馈回路 | 记录每材质/机器的间隙值，下次自动带出 |
| 3.3 | **模型分块**（D14'）：输入最大打印尺寸，超出则切成 nx×ny 片，切缝优先落在实心筋上，每片带 φ4×8 定位销孔 | 300×200 的板 + 200×200 的限制 → 出 2 片，拼起来销孔对齐、缝宽 ≤0.2mm；把一片旋转 90° 后仍能对上 |
| 3.4 | 试切件生成按钮 | 一键出 40×40×10 的三档间隙试切件 STL |
| 3.5 | **DXF / SVG 1:1 导出**（D13'） | 导出的 DXF 在 CAD 里打开，量凹槽轮廓 = 设计尺寸 ±0.1mm；每个槽有深度标注；板外框闭合 |
| 3.6 | **可选棋盘格标定**（D16'） | 标定后，同一把 100mm 卡尺放在纸中心与纸角落，测出的长度差 < 0.5mm |

### M4 — 收尾（2 天）

持久化（localStorage 全量草稿）、错误边界、端到端冒烟、文档同步（README/PRD/DEVELOPMENT_GUIDE 纠正"STEP AP242 可二次编辑"等失真描述）。

**总计：约 16 天**（v0.2 是 26–37 天）。增量来自 D13' 的 DXF（+0.5）、D14' 的分块（+0.5）、D15' 的自定义外壳（+0.5）、D16' 的畸变标定（+0.5）。

---

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

1. 用户回答 §7 的 Q1–Q6（尤其 Q1，它可能推翻 M1）。
2. 计划冻结 → 写 **SDS**（结构：模块划分 / 数据模型 / API 契约 / 每个移植文件的适配说明 / 测试计划 / 迁移与回滚）。
3. SDS 过独立审核 → 新会话按 SDS 实施（主会话调度 + 子 agent 编码 + 独立审核）。
