# M1 任务书：几何内核移植（3.5 天，3 路并行）

> 说明：为保护个人隐私，本文中的项目根已统一写作 `<PROJECT_ROOT>`，本机用户目录写作 `<STAGING_DIR>`。实施时请替换为你本机的实际路径。

## 通用约定（三路都适用）

**环境**
- 项目根（WSL）：`<PROJECT_ROOT>`
- 调用：`ops_bash` 里 `wsl -d Ubuntu bash -lc "cd <PROJECT_ROOT> && <cmd>"`
- 解释器：`.venv/bin/python`（3.14.4），已装 numpy/shapely/manifold3d/trimesh/rtree/cv2/skimage/ezdxf/pytest

**文件写入硬约束**
1. **不要**用 `write`/`edit` 直接写 `//wsl$/...`（报 `ENOTSUP: operation not supported on socket, link ...`）。
2. 做法：`write` 到 `<STAGING_DIR>\m1x\<name>.py`，再 `ops_bash` 用 `cp` 复制进 `//wsl$/Ubuntu/<PROJECT_ROOT>/<目标>`。
3. `bash -lc` 里**不要用 `$(...)`**（会被中转吃掉），写 .sh 文件再 `bash`。
4. python 源码注释里**不要用中文引号** `“”`（SyntaxError），用「」。

**已就绪（M-1 交付，直接用，不要重写）**
- `python_backend/domain/models.py`：`Vec2` / `Tool` / `BoardConfig` / `Project` / `FingerHole`（都是 frozen dataclass，snake_case）
- `python_backend/geometry/constants.py`：`board_top_z(board)` / `board_depth_limit(board)` / `GRHU=7.0` / `GRU=42.0` / `GR_BASE_HEIGHT=4.75` / `LIP_HEIGHT=8.2` / `LIP_WIDTH=2.6` / `EDGE_MM=5.0`
- `python_backend/geometry/polygon.py`：`GeometryError` / `signed_area` / `to_board_frame` / `normalize_winding` / `make_shape`（先简化后加间隙）/ `SIMPLIFY_TOL_MM=0.15`
- `python_backend/geometry/board.py`：`tools_bbox` / `board_center` / `board_size_mm` / `build_board`（rect only，z ∈ [0, thickness]）
- `python_backend/geometry/pockets.py`：`resolve_depth` / `resolve_clearance` / `resolve_chamfer` / `pocket_shape` / `build_pocket_cutter`（z ∈ [top_z−depth, top_z+1]，含倒角锥台）
- `python_backend/geometry/__init__.py`：`generate_insert(project)` 返回 `{base, base_uncut, slot_cutter, pocket_length_mm, board_mm, top_z, warnings, tools}`
- `scripts/smoke_geometry.py`：三条断言，**已跑通**（`bb[5]-top_z=1.0`、`first_hit=4.0`、`pocket_length=100.0`）

**★ 四个局部量铁律（审核只 grep 这四个名字）**
```python
top_z     = board_top_z(board)          # 唯一 z 基准，禁止 thickness / height_u*7
depth     = tool.depth_override    if tool.depth_override    is not None else board.embed_depth
clearance = tool.clearance_override if tool.clearance_override is not None else board.clearance
chamfer   = tool.chamfer_override  if tool.chamfer_override  is not None else board.slot_chamfer
```
判据与用到它的几何**必须共用同一个局部量**。凡在别处重新算 `thickness` / `height_u*7` / 裸 `board.embed_depth` 当判据，一律打回。

**★ manifold3d / trimesh 实测 API 事实（照此写，别改）**
| 事实 | 说明 |
|---|---|
| `Manifold.bounding_box()` | **扁平 6 元组** `(minx,miny,minz,maxx,maxy,maxz)`。`bb[5]`=maxZ、`bb[2]`=minZ。`bb[1][2]` 会 `TypeError` |
| `CrossSection.bounds()` | **扁平 4 元组** `(minx,miny,maxx,maxy)` |
| `intersects_location` | 参数名 `ray_origins` / `ray_directions`（不是 `origin`/`direction`） |
| 返回的 `loc` | **不按距离排序**，首击取 `max(p[2] for p in loc)` |
| 射线打盲槽 | 贯穿槽时 `loc = []` 空 |
| `trimesh` 5.2.0 | **没有** `section_plane`，只有 `section(plane_normal=, plane_origin=)` |
| 转 trimesh | `trimesh.Trimesh(vertices=np.asarray(m.vert_properties)[:, :3].astype(float), faces=np.asarray(m.tri_verts), process=False)` |

**许可合规（硬要求）**
移植 tracefinity 的代码，**文件头必须保留**：
```python
# Ported from tracefinity/tracefinity (MIT License)
# Copyright (c) 2024 Tracefinity Contributors
# https://github.com/tracefinity/tracefinity
```
参考源码在 `reference/oss/tracefinity/backend/app/services/stl_generator_manifold.py`（1669 行）。

---

## 路 A：板体与 Gridfinity（任务 1.0b / 1.4a / 1.4b / 1.4c / 1.6）

### 1.0b 板级参数进数据模型
`BoardConfig` 已经由 M-1 建好全部字段（含 `size_mode` / `width_mm` / `height_mm` / `corner_r` / `base_edge_roundover` / `slot_chamfer` / `margin=12.0`）。本任务只做**校验**：
- `size_mode='custom'` 缺 `widthMm`/`heightMm` → `INVALID_SIZE_MODE`
- 非 `custom` 模式带了宽高 → `INVALID_SIZE_MODE`
- 判据必须是 `is not None`（前端非 custom 时发 `null` 是合法的，不能用 truthiness）
- 未知字段 → `SCHEMA_UNKNOWN_FIELD`（M1 阶段可先只做 dataclass 层，Pydantic 层留给 M2）

`__post_init__` 里已有部分校验，**检查是否完备**，缺的补上。

### 1.6 自定义矩形外壳（三种 sizeMode）
`board_size_mm` 已实现三种模式。本任务补：
1. **`cornerR`**：`build_board` 已用 `offset(-r).offset(r, Round)`，验证 `r` 超过短边一半时被 clamp（已有）。
2. **`baseEdgeRoundover`**：板**顶面**沿外框一周的圆角。v1 允许降级为 `board_solid ∩ 半圆柱沿四条边`。
   - `baseEdgeRoundover = 0` 时必须**完全不改变**板体（不要留 0 面积的退化几何）
3. **`TOOL_OUT_OF_BOARD`**：`sizeMode='custom'` 且工具超出板框 → 抛 `GeometryError("TOOL_OUT_OF_BOARD", ...)`，**阻断，不自动放大板**。

**DoD**（必须写成 `python_backend/tests/test_board_m1.py`）
- ① `fit-tools` → 板外框 = 并集 bbox 各边 + `margin`(12)
- ② `custom` `widthMm=100, heightMm=80` → `bounding_box()` 得 100×80×thickness（**与工具并集大小无关**）
- ③ `print-bed` → 等于 `(printBed.x − 2*edge) × (printBed.y − 2*edge)`，`edge=5`，220 床 → **210×210**（**不是整张床 220**）
- ④ `custom` 且工具超出板框 → `TOOL_OUT_OF_BOARD`
- ⑤ `cornerR` / `baseEdgeRoundover` 与参数一致

### 1.4a Gridfinity 底座剖面
按 `GR_BASE_PROFILE` 三段，每段单独 `extrude(scale_top=...)` 后 union。
参考 `reference/oss/tracefinity/backend/app/services/stl_generator_manifold.py:90` `_build_base_unit`：
```python
GF_BASE_HEIGHT = 4.75
BASE_H_BOT = 0.8     # 下倒角段高
BASE_H_MID = 1.8     # 直壁段高
BASE_H_TOP = 2.15    # = 4.75 - 0.8 - 1.8，上倒角段高
GF_CORNER_R = 3.75   # 4.0 - 0.25 inset
```
**DoD**：底座高 4.75（±0.01）、顶面 chamfer 推导值与常量表一致（±0.01）、`BASE_H_BOT + BASE_H_MID + BASE_H_TOP == 4.75` 断言。

### 1.4b 堆叠唇五段剖面
参考 `stl_generator_manifold.py:115` `_build_stacking_lip_notch`：
```python
LIP_D0 = 1.9; LIP_D1 = 1.8; LIP_D2 = 0.7; LIP_D3 = 1.2
LIP_D4 = LIP_D0 + LIP_D2   # 2.6
```
顺序 **`D4, D3, D2, D1, D0`**，累计 **8.2**。

**DoD**：逐段 bbox 高度 **2.6 / 1.2 / 0.7 / 1.8 / 1.9**（各段 ±0.01、**总和 ±0.05**）。
**注意**：`LIP_HEIGHT=8.2` 是**垂直**高度；`LIP_WIDTH=2.6` 是**径向**宽度，两者量纲不同，不要混用。
另加断言 `abs(LIP_WIDTH − 2.6) ≤ 0.05`。

### 1.4c 磁吸孔 + 高度公式
参考 `stl_generator_manifold.py:629` `_make_magnet_holes`：
- 孔心**相对格心 ±13.0mm**（即距格角 8.0mm），φ6.0 × 2.4 深，**从底面往上打**（`translate((x, y, 0.0))`）
- `height_mm = height_u * GRHU`（3U 必须 = **21mm**，**不是 26**）

**DoD**
- 同一格内相邻两孔心距 **26mm**；跨格相邻两孔心距 **16mm**（42 − 26）
- 孔心到格角 **8.0 ± 0.1**
- `height_mm = height_u * 7`（3U → 21mm，±0.01）
- 磁孔深 2.4，角 R 4.0

**★ 关键警告**：`MAGNET_INSET = 4.8` 是**孔边到格角**（8.0 − 6.5/2 ≈ 4.75），**不参与定位**。「距格角 4.8」与「孔心距 26」算术互斥（42 − 2×4.8 = 32.4 ≠ 26）。**定位一律用 ±13.0 相对格心**。

---

## 路 B：切刀与间隙（任务 1.1 / 1.2）

### 1.1 倒角锥台（在 M-1 基础上加强 DoD）
`build_pocket_cutter` 已实现锥台。本任务补**可验证的 DoD**：

- `eff = min(chamfer, max(0, depth − 1))`（已实现）
- 锥台占 `z ∈ [top_z − eff, top_z]`，顶面 `+0.01` 溢出
- **DoD 不能只量 bbox 开口宽差**——`scale_top` 按 bbox 比例缩放时，bbox 宽差**恒等于** `2×chamfer`，那是恒真断言。
  **必须在「外轮廓凸包的各条边中点」取样**（不是 bbox 边中点——矩形上两者重合，所以 **L 形 fixture 必须用凸包采样才能区分**）：
  每点径向宽 = `chamfer ± 0.12mm`
- 在 `z = top_z − 1e-6` 与 `z = top_z − eff` 两处取 `section`，**高差必须恰好等于 `eff`**
  （原写「恰好等于 chamfer」在 `chamfer=1.5 / depth=2` 时必红；原写 `thickness−0.1` 会差 0.2mm 也必红）
- 凹角告警：`cs_o = cs0.offset(eff, JoinType.Miter)` 只作对照，若 `cs_o.area()` 与仿射锥台顶面面积相差 >15%，写 warning `CHAMFER_NARROW_AT_CONCAVE` 但**不阻断**（已实现）

### 1.2 间隙 + 平滑管线
- 间隙 0.4mm 时槽比轮廓外扩 **0.4 ± 0.05mm**
- **顺序断言**：`prepare_for_generation` 必须「先 simplify/smooth、后 clearance」。
  实现方式：造一个"简化会把顶点啃掉 0.15mm"的 fixture，断言最终外扩量仍是 0.4 而不是 0.25。

**DoD 文件**：`python_backend/tests/test_pocket_m1.py`

---

## 路 C：多轮廓 / 内孔 / 手孔 / 矩形外壳（任务 1.0 / 1.3 / 1.5）

### 1.0 后端多轮廓
`extract_tool_contours_v26` 现在只返回**单个最大连通轮廓**（`sam_tool_contour.py:150`、`:226`）。
改成返回 `List[Contour]`，每个带自己的 `holes`。

**DoD**：一张放了 3 把工具的照片 → 返回 3 个外环 + 正确内环数。
（没有真实照片就用合成 mask 图，用 `cv2.fillPoly` 画 3 个矩形 + 1 个圆环）

### 1.3 内环链路（F4 五处断点）
用**真实开口扳手照片**端到端跑出中心孔 —— 「圆环基元能过」**不算通过**（否则 `fill_holes` 与 `RETR_EXTERNAL` 一行不改也能过）。

**DoD**：开口扳手的中心孔在最终 STL 里存在（用 `section` 数内环数，或用 genus 数）。

### 1.5 手孔 6 形态 + 倒角（**最大的一块**）
按 SDS §7.4 实现 `geometry/finger_holes.py`。

**★ 形态判据是「生效 depth」（= `depthOverride ?? embedDepth`），不是板厚、不是裸 `embedDepth`**
- `depth < FINGER_REACH_MM(20)` → **禁止**生成竖直孔（只给 scoop 系）
- `depth >= 20` → `sphere` / `cylinder` / `square` / `rect` / `filleted_rect` 可选

**★ scoop 必须有真几何**（不是只有枚举值）
- 坡底 = `top_z − depth`（**±0.01，不是 `thickness − depth`**）
- `run = depth / tan(angle)`
- **`run ≤ d_edge − clearance`**，`d_edge` = 坡道方向上槽壁到板轮廓的**实测** `shapely.distance`（**不是 `margin`**）
- `d_edge < clearance + 1.0` → 阻断 `GEOMETRY_INVALID`
- 楔块向槽内侵入 ≥ 0.5mm
- **与槽切刀 3D 求交体积 > 0.1**：`(scoop_cutter ^ pocket_cutter).volume() > 0.1`
  **不能写 `CrossSection` 求交**——2D 与 3D 不可交；按 XY 投影解释则正确几何（坡道在槽外、只共边）恒为 0，断言恒假

**DoD 必须分两组参数各跑一遍**（默认 `embedDepth=8` 下竖直孔被禁，单组跑不出六形态）：
- **A 组** `thickness=12, embedDepth=8`：只生成 `scoop` 并断言开口
- **B 组** `thickness=25, embedDepth=22`：生成 `sphere`/`cylinder`/`square`/`rect`/`filleted_rect` 五种并各自断言开口

**竖直孔的 z 断言（按 `depthMode` 二分，别写反）**
- `blind` → `abs(bbox[2] − (top_z − depth)) ≤ 0.01`（`bbox[2]` = minZ）
- `through` → `bbox[2] ≤ −0.5`
- **`≥ 0` 恒真，等于没查**，禁止出现
- `sphere` 同样断言 `abs(bbox[2] − (top_z − depth)) ≤ 0.01`

**★ 重写 `_auto_detect_finger_slots`**：现在它吃**像素坐标**、CAD 里按 **mm** 布局（F3 坐标系错位）。改成全程 mm。

**★★ 移植 y 翻转的陷阱（必读，SDS §12.3 有专项检查项）**

tracefinity 的 `_make_finger_holes`（`stl_generator_manifold.py:986-987`）里写的是：
```python
fh_x = fh.x_mm + offset_x
fh_y = -(fh.y_mm + offset_y)      # ← 这个取负
```
**不要照抄这个 `-`**。原因：
- tracefinity 的入参 `fh.y_mm` 是 **y-down（纸面/图像系）**，所以它需要取负翻成 y-up；
- 但本项目 `to_board_frame(p, center)` **已经做了** `center.y - p.y`（SDS §2.3，全项目唯一 y 翻转点）；
- 如果手孔再走一遍 `-(y + offset_y)`，就是**二次取负 = 竖直镜像**，手孔会跑到槽的另一侧（镜像），而板、槽、轮廓全都对——**这是最难发现的一类 bug**。

**正确做法**：手孔坐标也必须先过 `to_board_frame`，然后**直接用**，不再取负：
```python
fh_pt = to_board_frame([Vec2(fh.x, fh.y)], board_center)[0]
# 之后一律用 fh_pt.x / fh_pt.y，不要写 -(fh_pt.y + anything)
```
**DoD 必加一条**：造一个**只在 y 正侧**有手孔的工具（例如槽中心偏上 30mm 处放一个手孔），断言手孔 cutter 的 `bbox[1] > 0`（minY 为正）。若写成二次取负，手孔会跑到 `bbox[3] < 0`，这条立刻红。**只查"有没有手孔"抓不住这个 bug。**

**★★ `rotation` 必须取负（SDS §7.4 末条，容易漏）**

`to_board_frame` 的 y 取负是一次**镜像**；镜像下「逆时针」变「顺时针」。所以：
```python
rot = -hole.rotation      # 度，绕 Z
```
不取负的话，`filleted_rect` 的圆角位置与 `scoopDir` 的朝向都会**反向**，而外轮廓相关的断言全部照过（抓不到）。

**DoD 文件**：`python_backend/tests/test_finger_holes.py`

---

## 交付格式（每路都要）
1. **改动文件清单**：绝对路径 + 行数
2. **关键行号 + 作用**（每文件 1–3 处）
3. **跑过的命令 + 原样输出**（必须含 `pytest -q python_backend/tests -k <你的模块>` 完整结果）
4. **未完成项 / 已知限制**（诚实列）

## ★★ 并行冲突硬约束（主会话 2026-11-06 追加，三路都必须遵守）

本轮三路**并行**跑，且之后还有一个「M1-W 接线 agent」最后进场整合。为避免互相覆盖，以下是硬约束：

1. **禁止修改 `python_backend/geometry/__init__.py`**。三路谁都不许动 `generate_insert`。
   路 A 的 gridfinity 板体、路 C 的手孔切刀，**都不要试图接进 `generate_insert`**；
   各交**纯函数**（例如 `build_gridfinity_base(...)` / `build_finger_hole_cutter(...)`）+ 独立测试。
   `generate_insert` 的整合统一由最后进场的 M1-W 接线 agent 完成（它届时能看到三路成品）。
2. **禁止修改 `python_backend/main.py`**（`/api/*` 端点由 M1-W 建，本轮不碰）。
3. **路 A 的 1.0b「补 `__post_init__` 校验」要改 `python_backend/domain/models.py`**：
   本轮**允许改**，但只允许在 `__post_init__` 内追加校验分支，不许重排/删除已有字段与逻辑
   （`domain/models.py` 刚由 M0 修复 agent 改过注释，改动面必须最小）。
4. **三路各建自己的测试文件**（`test_board_m1.py` / `test_pocket_m1.py` / `test_finger_holes.py`），
   不许改别人的测试文件，也不许改 `test_geometry_m1.py` 等 M-1/M0 既有测试。
5. 新建模块放进 `python_backend/geometry/`（如 `gridfinity.py`、`finger_holes.py`），
   **不要**新建 `python_backend/models/` 包（会撞 `cad_engine.py:59` 裸 `from models import`）。
6. 若某路发现必须先改 `__init__.py` 才能验证，**停下来在报告里说明**，交 M1-W 处理，
   不要自己改。

## 禁止事项
- 不要改 `cad_engine.py` / `main.py` / `geometry/__init__.py` / `python_backend/models.py` / 前端 `src/` / `docs/planning/`
- 不要 import `cad_engine`
- `geometry/` 里**不要** import cv2（`imaging/` 才可以用）
- 不要为了让测试变绿而放宽断言容差
