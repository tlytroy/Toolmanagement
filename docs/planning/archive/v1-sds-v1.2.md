# Toolmanagement-web 软件详细设计说明（SDS）v1.2

> 状态：**第三轮审核已吸收（7 条 P0 全部修完），待用户定稿并开工**
> 上游计划：`docs/planning/v1-plan-v1.2.md`
> **v1.2 = v1.1 + 第三轮独立审核修订。** 7 条 P0 全部修完：手孔形态改单一连续判据 `embedDepth ≥ 20`（原按板厚分档有空档）、scoop 坡底改 `thickness − embedDepth`（原式切穿板底）、`sphere` 断言改绝对值（原 `≥ 0` 恒真）、`wantDxf`/`dxfFlipY` 进 `BoardConfig`、PY `FingerHole` 补 scoop 三字段、错误码补 4 个、磁孔改为「孔心距格心 ±13」。
>
> **v1.1 = v1.0 + 第二轮独立审核（closure / cold-read）修订，共 39 处。** 关键：`to_board_frame` 改签名与符号、板厚改 6/12/25 枚举、`HoleShape` 加 `scoop`、未知字段改 400、跳过 `bounds()`/`bounding_box()` 混用、DXF 默认翻转、新增 `tools_in_board` 校验与 §10.3 容差总表。全部改动处带 `▸ 第二轮审核` 或 `▸ 审核修订` 标记。
> 上游：`docs/planning/v1-plan-v1.2.md`（**14.5 人日**，M-1–M4）
> 修订摘要：本版吸收审核 B 的 7 条前置缺口、C 的 R1–R7、A 的任务编号与 D 的四条用户价值问题。改动处均带 `▸ 审核修订` 标记。
> 日期：2026-11-03
> 读者：实施阶段的主会话（调度）与子 agent（编码）

---

## §0 这份文档解决什么

计划（v0.3）回答「做什么、为什么、多少天」。**SDS 回答「每一行代码写在哪、接口长什么样、什么算做完」。**

阅读顺序：

1. **§2 坐标系** —— 不先读这一节，后面所有代码都会错。
2. **§3 数据模型** —— 前后端共用的唯一真相。
3. **§4 API 契约** —— 前后端的接缝。
4. **§7 几何流水线** —— 后端核心，M1 的全部内容。
5. 其余按需。

**实施铁律**：任何子 agent 在写代码前必须先读 §2 和 §3，并在 PR 描述里复述「我用的是哪个坐标系、哪个单位」。历史上这三处出错都是静默的（不报错、能出 STL、打印出来装不进）。

---

## §1 范围与非目标

### 1.1 本版要做（对应计划 M-1–M4，14.5 人日）

| 能力 | 里程碑 |
|---|---|
| 后端能在 WSL 里跑起来，`POST /api/generate` 返回可用 STL | M0 |
| 毫米链贯通：拍照 → 10px/mm 校正图 → 真实毫米尺寸 | M0 |
| 槽开口朝上（修密闭空腔）、倒角、间隙、内孔、手孔 | M1 |
| 板的两种外形：自定义矩形 / Gridfinity | M1 |
| 顶点编辑、手孔编辑、倒角参数、撤销重做 | M2 |
| 一张照片多把工具 → 一次生成多槽 | M2 |
| 模型分块（超打印床时切分 + 定位销） | M3 |
| DXF 1:1 导出 | M3 |
| 照片体检（EXIF 反算相机高度 / 纸出框 / 极端透视 三条告警）——**不做镜头标定**（计划 §5 已砍，只保留「畸变可能引入 X mm」的告警） | **M0**（任务 0.5；v1.1 误记为 M3） |

### 1.2 明确不做

- **不做切片**（不生成 G-code、不做层高/壁数/填充/支撑/温度）
- **不做材料与工艺相关的任何逻辑**（同一个模型给 PLA、PETG、TPU、泡沫、木板共用）
- **不做 STEP / B-Rep**（现有 `_mesh_to_step_base64` 是网格包壳，本版直接删除该端点）
- **不做云端、账号、多设备同步**
- **不做自动排版算法**（只有手动拖拽 + 旋转 90° + 重叠高亮；first-fit 已砍）
- **不做 ArUco 标记纸**
- **不支持超过 A4 的工具**
- **不支持单槽跨分块**（见 §8.4）

---

## §2 坐标系与单位（全项目唯一的铁律）

### 2.1 三套坐标，两次转换

```
 ① 源图像素 (px, y-down, 原点左上)
        │  透视变换 + 镜头去畸变
        ▼
 ② 纸面毫米 (mm, y-down, 原点 = A4 纸左上角)   ← 全系统的“存储坐标”
        │  板外接框平移 + 翻转 y
        ▼
 ③ 板局部毫米 (mm, y-up, 原点 = 板中心, z=0 在板底面)  ← 几何内核坐标
```

**规则：**

| 层 | 单位 | 轴向 | 原点 | 谁用 |
|---|---|---|---|---|
| ① 源图像素 | px | y 向下 | 图像左上 | 只在后端 warp 内部，不出现在任何 API 响应里 |
| ② 纸面毫米 | mm | y 向下（图像惯例） | A4 左上角 | **前端 store 的全部几何数据、API 请求体** |
| ③ 板局部毫米 | mm | **y 向上** | 板几何中心，z=0 在板底面 | 只在后端 `geometry/` 内部，不出现在 API 里 |

**为什么存储用 y-down**：轮廓来自图像，用 y-down 存可以避免前端画布、Canvas 编辑、SVG 叠加层三处反复翻转。翻转只在最后一刻（§2.3）做一次。

### 2.2 纸面毫米（②）的定义

- `mm_per_px` **恒为 0.1**（10 px/mm），由 warp 保证，**不作为参数在层间传递**。
- A4 竖向：纸面 **210.0 × 297.0 mm**，原点 (0,0) = 纸的左上（长边向上）。
- A4 横向：纸面 **297.0 × 210.0 mm**。
- 画布四周留 15mm 安全边（用于纸角误差容忍），但**坐标原点仍在纸角，不在画布角**。即允许坐标为负、允许超出 210×297 的工具轮廓被检测到（但会被 §7.6 的边界校验拒绝）。

**▸ 审核修订（B①）**：画布像素尺寸与纸面坐标的换算必须写死，不许两处各说一套。

```
画布 (A4 竖) = 2400 × 3270 px     = (210 + 2×15) × (297 + 2×15) 再 ×10 px/mm
纸面在画布中的像素范围 = x ∈ [150, 2250], y ∈ [150, 3120]
纸面毫米坐标 (0,0) 对应画布像素 (150, 150)
换算：  u_mm = px / 10 - 15.0      v_mm = py / 10 - 15.0
```

`/correct-image` 的响应必须回传 `canvasPx` 与 `paperOriginPx` 这两项，前端**只认纸面 mm**，不做像素换算。计划 v0.3 的 §3（2400×3270）与 M0.4 DoD（2100×2970）互相矛盾，已统一到 2400×3270（计划 v1.0 §3.1 已改）。
- 所有 `x, y` 都是 `float64`，**不做整数取整**。

### 2.3 板局部毫米（③）的转换

**这是全项目唯一允许翻转 y 的地方。** ▸ 第二轮审核修正：v1.0 草案写的 `y = (origin.y + board_h) − p.y` 是错的——纸面是 y-down，底边的 y 是**较大**值，`origin.y + board_h` 落在底边**之下**，值域变成 `[−h, 0]`，既不是 y-up 也没居中。正确写法只有一个平移、一个取负：

```python
def to_board_frame(polygon_mm: list[Vec2], center: Vec2) -> list[Vec2]:
    """纸面毫米(y-down) → 板局部毫米(y-up，原点=板心)。唯一翻转点。"""
    return [Vec2(x=p.x - center.x, y=center.y - p.y) for p in polygon_mm]
```

- `center` = **板外接框中心**在纸面 mm 中的点，`center = ((xmin+xmax)/2, (ymin+ymax)/2)`。
- 值域检查：纸面四角 → `(±w/2, ±h/2)`；纸面**顶**边（y 最小）中点 → `(0, +h/2)`。板心落在 (0,0)。
- **z 轴**：板底面 z = 0，板顶面 z = `thickness`。**不是 ±H/2 居中**（`cad_engine.py:96` 的居中必须删除）。
- **断言（写进 §10.1 单元测试，必须有）**：
  ```python
  bb = slot_cutter.bounding_box()
  assert abs(bb[1][2] - (thickness + 1.0)) < 1e-6    # 切刀顶 = thickness+1
  assert bb[0][2] < thickness                          # 切刀体在板内
  ```

### 2.4 多边形绕向规范

- **外轮廓：逆时针（CCW）**，。**绕向只在「板局部 y-up 系」里有定义，全程只归一化一次**：`signed_area(outer) > 0`（CCW）、`signed_area(inner) < 0`（CW），归一化发生在 `to_board_frame` **之后**。存进 `Project`、经 API 传出的多边形是**纸面 y-down** 坐标，y 取负使符号整体翻转——此时外环有符号面积**必为负**，这是同一套规范的镜像结果，**不是第二套规范**；序列化层不许再做任何翻转。判定函数统一用：

```python
def signed_area(pts) -> float:
    # 在 y-up 坐标系下的有符号面积，> 0 为 CCW
    return 0.5 * sum(pts[i].x * pts[i+1].y - pts[i+1].x * pts[i].y for i in range(len(pts)))
```

- **入库**：`/extract-contours` 返回的是**纸面 y-down** 点环，绕向按上面的镜像规则（外环有符号面积 < 0、内环 > 0）。**入库时不再翻一次**。
- **送进 `manifold3d.CrossSection` 前**：`build_pocket_cutter` 入口先 `to_board_frame` 回到 y-up，外环符号恢复为正、内孔为负，正好满足 manifold3d 要求，**不需要二次反转**。这一步如果搞反，内孔会被 union 吃掉（实测体积 4000 vs 3000）。

### 2.5 三套坐标的其余四条铁律（▸ 审核修订，R3）

计划 §2.3 列了六条约定，其中 y 轴、z 原点、数据结构三条已分别落在 §2.3 / §2.4 / §3；剩下四条在这里，**每条都是"不报错但结果错"的类型**：

| # | 铁律 | 违反后的症状 | 落地位置 |
|---|---|---|---|
| 1 | **绕向**：板局部 y-up 系内 `signed_area(outer) > 0`、`signed_area(inner) < 0`；只在 `to_board_frame` 之后归一化一次，序列化层不翻 | 内孔被 union 吃掉，体积少 25%，但 `is_watertight` 仍为 true | §2.4 + `geometry/normalize.py` |
| 2 | **mask 极性**：`alpha > 0.5` = 工具（不是背景） | 整块板被掏空，或什么都没有 | §4.3 + 断言"mask 占画布 5%–60%" |
| 3 | **像素中心**：像素坐标取中心，统一 `+0.5 px` 再换算 | 整体偏 0.05mm（可忽略，但多个轮廓叠加会累积） | `imaging/warp.py` |
| 4 | **板原点 = 板外接框中心**（x/y），z 原点在板底面 | 若误取左下角，整板相对工具平移半个板宽，槽整体偏移而"看起来居中"；装不进 | §2.3 `to_board_frame` 的 `center` |

**禁止出现 `poly_mm -= center` 这种把工具挪到板心的写法**（现 `cad_engine.py:585` 就是这么做，F1 之外的第二致命点）。

### 2.6 单位出现在哪些字段名里

**规则：字段名里带 `Mm` 后缀（camelCase，如 `boardMm`）的一定是毫米；不带后缀的几何字段（`x`, `y`, `radius`, `width`）在同一对象内一律是毫米。**

唯一例外：字段名带 `_px` 或位于 `ImageSpace*` 类型内的，是像素。

---

## §3 数据模型

### 3.1 前端 TypeScript（`src/types/domain.ts`，新建）

```ts
export type Vec2 = { x: number; y: number };   // mm, 纸面坐标系, y-down

export type HoleShape =
  | 'scoop'          // 斜坡：与凹槽连通，embedDepth < FINGER_REACH_MM(20) 时唯一可用
  | 'sphere'         // 球缺竖直孔，仅 embedDepth >= 20 时可选
  | 'cylinder'
  | 'square'
  | 'rect'
  | 'filleted_rect';

export interface FingerHole {
  id: string;                 // 'fh_1' 递增
  x: number; y: number;       // 孔中心, 纸面 mm
  shape: HoleShape;
  radius: number;             // sphere/cylinder 用；其他形状忽略
  width: number;              // square/rect/filleted_rect 用
  height: number;
  rotation: number;           // 绕 Z, 度, 逆时针
  depthMode: 'blind' | 'through';
  depth: number;              // blind 时有效, 从板顶面向下, mm
  chamfer: number;            // 孔口倒角, mm, 0 = 无
  scoopWidth: number;         // 仅 scoop: 坡宽, 默认 12, 范围 10..15
  scoopAngleDeg: number;      // 仅 scoop: 坡角, 默认 45
  scoopDir: Vec2;             // 仅 scoop: 单位向量, 斜坡朝"最近工具质心"的方向
}

export interface Tool {
  id: string;                 // 'tool_1'
  name: string;               // 默认 '工具 1'
  outer: Vec2[];              // 外轮廓, 已归一化绕向
  interior: Vec2[][];         // 内孔环, 已归一化绕向; 空数组表示无孔
  fingerHoles: FingerHole[];  // 该工具自己的手孔(按质心归属)
  clearanceOverride: number | null;  // null → 用 board.clearance
  depthOverride: number | null;      // null → 用 board.embedDepth
  chamferOverride: number | null;
  source: 'auto' | 'manual';
  hidden: boolean;            // 暂时不参与生成
}

export type BoardShape = 'rect' | 'gridfinity';

export interface BoardConfig {
  shape: BoardShape;

  // —— rect 专用 ——
  margin: number;             // 板边到工具外接框的最小距离, 默认 8
  thickness: 6 | 12 | 25;     // 板厚, 三档枚举, 默认 12（自由值会让手孔形态无定义）
  cornerR: number;            // 板在 XY 平面的四角半径, 默认 5
  baseEdgeRoundover: number;  // 板顶面沿外框一周的圆角, 默认 0（关）

  // —— gridfinity 专用 ——
  unitsX: number;             // 42mm 格数, 1..40
  unitsY: number;
  heightU: number;            // 高度单位 U, 每 U = 7mm（含 4.75mm 底座）; 总高 = 7*U; 范围 2..10（1U=7 < 4.75 底座 + 8.2 唇）
  magnets: boolean;           // 是否打磁吸孔
  stackingLip: boolean;

  // —— 通用 ——
  embedDepth: number;         // 全局嵌入深度, 默认 8; 矩形板强制 <= thickness-2, Gridfinity 强制 <= heightU*7-4.75-2（见 §7.2）
  clearance: number;          // 全局侧向间隙, 默认 0.4
  slotChamfer: number;        // 槽口插入导向倒角, 默认 1.5
  fingerHoleChamfer: number;  // 手孔口倒角, 默认 0.5

  // —— 导出 ——
  wantDxf: boolean;           // 请求里带上则响应附 dxfBase64, 默认 false
  dxfFlipY: boolean;          // DXF 输出是否翻转 y, 默认 true（见 §9.2）

  // —— 分块 ——
  printBed: { x: number; y: number; z: number };  // 默认 220/220/220
  splitEnabled: boolean;
  pinDiameter: number;        // 定位销孔直径, 默认 4.0
}

export interface Project {
  schemaVersion: 1;
  paperW: number;             // 210 或 297（与 Python 的 paper_w 一一对应）
  paperH: number;
  tools: Tool[];
  board: BoardConfig;
}
```

**注意 `embedDepth` 的语义**：从**板顶面**往下算，单位 mm。前端滑块范围 `[2, thickness-2]`，后端再 clamp 一次（信任边界在后端）。

### 3.2 后端 Python（`python_backend/models/domain.py`，新建）

与 TS 一一对应，用 `@dataclass(frozen=True)` + `from_dict()` 显式解析（**不用 Pydantic 直接当领域模型**——Pydantic 只出现在 API 层，见 §4.0）。

```python
@dataclass(frozen=True)
class Vec2:
    x: float
    y: float

@dataclass(frozen=True)
class FingerHole:
    id: str
    x: float; y: float
    shape: str                  # 'scoop'|'sphere'|'cylinder'|'square'|'rect'|'filleted_rect'
    radius: float
    width: float; height: float
    rotation: float
    depth_mode: str             # 'blind'|'through'
    depth: float
    chamfer: float
    scoop_width: float          # 仅 scoop, 默认 12.0, 范围 10..15
    scoop_angle_deg: float      # 仅 scoop, 默认 45.0
    scoop_dir: Vec2             # 仅 scoop, 单位向量

@dataclass(frozen=True)
class Tool:
    id: str
    name: str
    outer: list[Vec2]
    interior: list[list[Vec2]]
    finger_holes: list[FingerHole]
    clearance_override: float | None
    depth_override: float | None
    chamfer_override: float | None
    source: str
    hidden: bool

@dataclass(frozen=True)
class BoardConfig: ...   # 字段同 TS

@dataclass(frozen=True)
class Project:
    schema_version: int
    paper_w: float
    paper_h: float
    tools: list[Tool]
    board: BoardConfig
```

**解析规则**（▸ 第二轮审核修正，三条都是硬规则）：

1. `from_dict` 遇到**缺失**字段 → 用默认值。
2. 遇到**未知**字段 → **400 `SCHEMA_UNKNOWN_FIELD`，不忽略**。忽略未知字段会让前后端字段名不一致时"请求成功、参数全部退回默认值"（例如前端发 `slotChamfer`、后端读 `slot_chamfer`，倒角 1.5mm 凭空消失，两端测试全绿）。
3. **JSON 一律 camelCase**；Pydantic 用 `alias_generator=to_camel` + `populate_by_name=True` 桥接 snake_case 字段名。
4. `schema_version != 1` → 后端**只返回 400 `SCHEMA_VERSION_UNSUPPORTED`，不做迁移**；迁移只在前端做（§3.3）。**不允许两处都做。**

### 3.3 持久化（localStorage）

- key: `tm.project.v1`
- 存整份 `Project` + `updatedAt`。**不存图片**（照片体积大，单独 key `tm.photo.v1` 存 dataURL，超过 2MB 时丢弃并提示）。
- 自动保存：任何 store 变更后 debounce 800ms。
- 载入失败（JSON 坏）→ 丢弃并开新项目，不弹错。
- **▸ 审核修订（B⑦）`schemaVersion` 迁移**：维护一张 `migrations: Record<number, (p: any) => any>`。
  `stored.version < CURRENT` → 逐级套用迁移函数升到当前版本；`stored.version > CURRENT`（降级打开）或**缺迁移表** → 丢弃草稿 + 提示「旧草稿不兼容，已清空」，**不做静默兼容、不尝试猜字段**。
  M1–M3 每加一个几何字段（`chamfer` / `shape` / `depth_override` / `pieces`）就必须同时加一条迁移，漏了算 bug。

---

## §4 API 契约

### 4.0 通用约定

- 所有端点前缀 `/api`（`vite.config.ts` 加 proxy，见 §11.3）。
- 统一响应信封：

```jsonc
{ "success": true, "data": { ... }, "warnings": [], "error": null }
{ "success": false, "data": null, "warnings": [], "error": { "code": "TOOL_OUT_OF_PAPER", "message": "...", "detail": {...} } }
```

- 错误码固定枚举（前端据此出文案，**禁止匹配中文串**）：`PAPER_NOT_FOUND`、`PAPER_OUT_OF_FRAME`、`CAMERA_TOO_CLOSE`、`EXTREME_PERSPECTIVE`、`IMAGE_TOO_SMALL`、`TOOL_OUT_OF_PAPER`（D2'）、`TOOL_TOO_LONG`（D17'）、`NO_SPLIT_RIB`（D14'，替代 v0.3 的 `SPLIT_IMPOSSIBLE`）、`EMPTY_TOOLSET`、`NO_CONTOUR`、`GEOMETRY_INVALID`、`DEPTH_EXCEEDS_THICKNESS`（**只作 warning**，见 §7.6 第 1 条）、`TOOL_OUT_OF_BOARD`（§7.6 第 9 条）、`GRIDFINITY_SPLIT_UNSUPPORTED`（§8，与 `NO_SPLIT_RIB` 分开）、`SCHEMA_UNKNOWN_FIELD`、`SCHEMA_VERSION_UNSUPPORTED`（§3.2）、`INTERNAL`。
- `warnings[]` 与 `error` 分离：**能继续生成的**只进 `warnings`（如深度被 clamp、槽重叠），**不能生成的**才置 `success:false`。
- 所有几何响应**一律毫米、纸面坐标（y-down）**。
- 文件上传用 `multipart/form-data`，字段名 `file`；图像统一转 PNG 返回（base64，不带 `data:` 前缀）。
- **字段命名唯一来源是本文件 §3.1/§3.2**（camelCase）。计划 D19' 只是摘要，冲突时以 SDS 为准。
- `errors[]` **不是**顶层字段：一次请求只有一个错误，走 `error: {code, message, detail}`；可继续的提示走 `warnings[]`。

### 4.1 `POST /api/detect-paper`

**请求**：multipart，`file`（原图，JPEG/PNG）。

**响应 `data`**：

```jsonc
{
  "corners": [{ "x": 0.0, "y": 0.0 }, ...],   // 4 点，纸面 mm 里的理想位置（= (0,0),(210,0),(210,297),(0,297) 顺序：TL,TR,BR,BL）
  "orientation": "portrait",                   // portrait | landscape
  "reprojectionError": 0.83,                   // px，低于 2.0 视为可信
  "imageSize": { "w": 4032, "h": 3024 }
}
```

> `corners` 返回的是**纸面毫米里的规范位置**（用于前端画引导框），**不是**源图像素坐标。源图像素坐标不下发，避免前端混用两套坐标。

**warnings**：`CAMERA_TOO_CLOSE`（附 `estimatedHeightMm` 与 `thicknessErrorPercent`）、`PAPER_OUT_OF_FRAME`、`EXTREME_PERSPECTIVE`。

### 4.2 `POST /api/correct-image`

**请求**：multipart，`file` + 表单字段 `orientation`（`portrait`|`landscape`，可省略则由后端判）。

**响应 `data`**：

```jsonc
{
  "warpedImage": "iVBORw0KGgo...",   // base64 PNG
  "mmPerPx": 0.1,
  "paperMm": { "w": 210.0, "h": 297.0 },
  "canvasPx": { "w": 2400, "h": 3270 },    // = (210+30)*10 x (297+30)*10
  "paperOriginPx": { "x": 150, "y": 150 },  // 纸左上角在画布里的像素位置
  "distortionWarningMm": 2.1,      // 由 EXIF 焦距估的"畸变可能引入的误差", 无 EXIF 时为 null
}
```

**硬约束**：`warpedImage` 的像素尺寸必须精确等于 `canvasPx`；`mmPerPx == 0.1`。后端与前端各写一条断言。

> **▸ 审核修订（B④）**：`mmPerPx` **只是常量回显**，供断言与调试用。**任何下游计算禁止读它**——下游只认纸面 mm。计划 v1.0 的 M0.4 DoD 已同步改成这个口径（原 v0.3 一边要求「返回 mm_per_px」一边要求「不向下游传 ppmm」，自相矛盾）。

### 4.3 `POST /api/extract-tools`

**请求**：multipart，`file`（**必须是 `/correct-image` 的输出**，即已 10px/mm + 含 15mm 安全边）。

**响应 `data`**：

```jsonc
{
  "tools": [
    { "outer": [...], "interior": [[...]], "areaMm2": 2140.6, "bbox": {...} }
  ],
  "quality": 0.87,          // 0..1
  "qualityParts": { "coverage": 0.62, "circularity": 0.91, "edgeSharpness": 0.88 }
}
```

- 轮廓已是**纸面毫米、y-down、绕向归一化**（见 §2.4）。
- 面积 < 50mm² 的轮廓丢弃（灰尘）。
- 返回前做边界校验：任一 bbox 距纸边 < 3mm → 直接 `success:false, error.code=TOOL_OUT_OF_PAPER`，`detail` 里给出越界工具的下标与越界量。**不返回残缺轮廓。**

### 4.4 `POST /api/simplify-contour`

**请求**（JSON）：`{ "polygon": Vec2[], "toleranceMm": 0.2 }`

**响应**：`{ "polygons": Vec2[][] }`——保留投影变换后的简化多边形（用于编辑手柄）。

> **▸ 第二轮审核**：v1.0 草案这里与计划的 0.3b（primitives → 有序闭合环往返）冲突。定案：**`primitives` 不出现在任何 v1 API 里，也不进 `Project`**。0.3b 的往返测试只针对**旧引擎内部**的 `_primitives_to_2d_polygon`（因为 M0 仍在旧引擎上改 z 与 mm 链），属于过渡期测试，M1 换引擎后随之删除。`/simplify-contours` 旧端点（返回 line/arc）一并删除。

### 4.5 `POST /api/generate`

**请求**（JSON）：完整 `Project`。

**响应 `data`**：

```jsonc
{
  "pieces": [
    { "name": "board_A1", "stlBase64": "...", "bboxMm": {...}, "volumeMm3": 48231.2 }
  ],
  "dxfBase64": "...",              // 仅当请求带 wantDxf=true
  "summary": {
    "toolCount": 3, "pieceCount": 2, "boardMm": {...}, "totalVolumeMm3": 9612.4,
    "paramsEcho": { "cornerR": 5, "baseEdgeRoundover": 0, "slotChamfer": 1.5, "embedDepth": 8, "clearance": 0.4 },
    "slotBounds": [[x0,y0,z0],[x1,y1,z1]],   // 所有槽切刀的并集 bbox（计划 0.2 的断言靠它）
    "baseBounds": [[x0,y0,z0],[x1,y1,z1]]
  },
  "checks": [
    { "id": "shapely_valid",   "ok": true },              // L0
    { "id": "watertight",      "ok": true },              // L1
    { "id": "winding",         "ok": true },              // L1
    { "id": "manifold_status", "ok": true, "status": "NoError" },
    { "id": "genus",           "ok": true, "value": 2 },
    { "id": "volume_match",    "ok": true, "errorPct": 0.6 },
    { "id": "slot_open",       "ok": true, "firstHitZ": 5.0 },   // 首击射线，F1 反证
    { "id": "min_rib",         "ok": true, "minMm": 2.4 },       // 阈值 2.0，见 §7.6
    { "id": "tools_in_board",  "ok": true },                     // 见 §7.6 第 9 条
    { "id": "depth_fits",      "ok": true }
  ]
}
```

- **阻断 / 不阻断的分工写死**：`shapely_valid`、`watertight`、`winding`、`manifold_status`、`tools_in_board`、`slot_open` 为 **blocking**（false → `success:false`，`error.code=GEOMETRY_INVALID` 或 `TOOL_OUT_OF_BOARD`，`detail.failedChecks`）；`genus`、`volume_match`、`min_rib`、`depth_fits` 为 **advisory**（false → `warnings[]`，仍出 STL）。
- `min_rib` 的阈值是 **2.0mm**（不是 2.4），与 §7.6 第 6 条一致。
- 分块成功时 `pieces.length > 1`，命名 `board_A1/A2/B1...`（先行后列，从左上起）。

### 4.6 `POST /api/finger-holes/auto`

**请求**：`{ "tool": Tool, "board": BoardConfig }`

**响应**：`{ "holes": FingerHole[] }`——只给建议，前端可改可删。

### 4.7 已删除的端点

| 端点 | 处置 |
|---|---|
| `/generate-step` | **删除**。网格包壳的 STEP 是伪 B-Rep，留着会误导。 |
| `/extract-tool-mask` | 保留但改名 `/api/tool-mask`，用于画笔编辑时的初始蒙版回推。 |
| `/update-contour` | **删除**。▸ 审核修订（B③）：它返回的是"另一份轮廓数据"，与 D18'「稠密点环为唯一真源」冲突。编辑一律改 `Project.tools[i].outer` 后重渲染，不再有"服务端回算轮廓"这条路。 |
| `/simplify-contours`（旧） | 由 §4.4 替代，旧端点删除。 |

---

## §5 前端架构

### 5.1 目录

```
src/
  api/client.ts            # 唯一 fetch 封装, 统一信封解析 + 错误码 → 中文文案
  types/domain.ts          # §3.1
  store/project.ts         # zustand + zundo, Project 全量
  store/ui.ts              # 步骤、选中、面板开合（不进 undo 栈）
  geometry/frame.ts        # paper<->screen 转换, 唯一翻转点
  geometry/snap.ts         # 吸附策略（网格/邻边/角度）
  components/editor/PolygonEditor.tsx   # 顶点编辑（抄 pascal 的 7 条）
  components/editor/FingerHoleEditor.tsx
  components/editor/ToolList.tsx
  components/panels/ParamsPanel.tsx
  components/panels/ExportPanel.tsx
  components/viewport/Viewport.tsx      # three.js 预览
  components/viewport/Overlay2D.tsx     # Canvas 叠加层（独立于 three）
```

### 5.2 状态：一个 store，两层

```ts
// store/project.ts —— 进 undo 栈
interface ProjectState {
  project: Project;
  setTools, updateTool, addTool, removeTool,
  updateBoard, updateFingerHole, addFingerHole, removeFingerHole
}
export const useProject = create<ProjectState>()(
  temporal(immer((set) => ({...})), {
    limit: 50,
    partialize: (s) => ({ project: s.project }),   // 只把 project 存进历史
    equality: (a, b) => a.project === b.project,   // immer 保证引用稳定
  })
);

// store/ui.ts —— 不进 undo 栈
interface UIState {
  step: 'upload'|'calibration'|'segmentation'|'editor'|'params'|'export';
  selectedToolId: string | null;
  selectedHoleId: string | null;
  generating: boolean;
  lastError: AppError | null;
}
```

**undo 粒度（关键）**：
- 一次拖拽手势 = 一条历史（靠 `onPolygonPreview`/`onPolygonChange` 分离实现，见 §6.3）。
- 一次滑块拖动 = 一条（`pointerup` 才写 store，拖动中用本地 state 预览）。
- 切换板形状（rect ↔ gridfinity）**不是** undo 条目——它只改 `board.shape`，工具数据不动，但为了符合直觉**仍然记录**，因为 thickness/units 字段会变。

### 5.3 步骤流转

```
upload ──(有图)──> calibration ──(warp 成功)──> segmentation ──(有 tool[])──> editor ──> params ──> export
                                    ↑                                                        │
                                    └────────────── 重拍 ────────────────────────────────────┘
```

- 进入 `editor` 之后，**回到 calibration 不清空 tools**（只是让用户重拍，确认后才覆盖）。
- 每一步都是一个独立的 route-less 页面（`Workspace.tsx` 里 switch），不引入 router。

### 5.4 2D 叠加层与 3D 预览

- **编辑全部在 2D Canvas 上做**，不引入 r3f 手柄。理由：编辑对象是平面闭环，正交俯视下 world→screen 是纯仿射，同步成本极低。
- 3D 预览是独立区域：用户改参数 → 点「生成」→ 拿 STL → `STLLoader` 显示。**不做实时重算**（后端一次生成 1–5 秒，实时会卡死）。
- 叠加层绘制顺序：底板轮廓 → 工具轮廓（选中高亮）→ 手孔 → 顶点手柄。

---

## §6 前端关键实现

### 6.1 坐标转换（`geometry/frame.ts`）

```ts
// 纸面 mm → Canvas 像素
export const toScreen = (p: Vec2, view: { scale: number; offsetX: number; offsetY: number }) => ({
  x: p.x * view.scale + view.offsetX,
  y: p.y * view.scale + view.offsetY,      // y 仍向下, 与 Canvas 一致
});

// Canvas 像素 → 纸面 mm
export const toPaper = (p: Vec2, view) => ({
  x: (p.x - view.offsetX) / view.scale,
  y: (p.y - view.offsetY) / view.scale,
});
```

**没有翻转**。纸面 mm 与 Canvas 都是 y-down，`scale` 把 210mm 映射到比如 840px。**这也是为什么 §2.1 选 y-down 作为存储坐标**——前端一次翻转都不需要，唯一的翻转在后端 `to_board_frame()`。

### 6.2 吸附（`geometry/snap.ts`）

```ts
export type SnapContext = {
  point: Vec2;
  neighbors: Vec2[];        // 最近的若干顶点
  tools: Tool[];
  toleranceMm: number;      // = 8 / view.scale, 屏上 8px
};
export type SnapResult = { point: Vec2; kind: 'none'|'vertex'|'edge'|'grid'|'angle' };
```

优先级：`vertex` > `edge` > `angle(0/45/90)` > `grid(1mm)` > `none`。**吸附永远在 `toPaper` 之后、写 store 之前执行**。

### 6.3 多边形编辑器（抄 `pascalorg/editor` 的骨架）

必需实现的 7 条（缺一条都会在验收时被退）：

1. `DragState` 存 `initialPolygon` 快照；每次 `pointermove` 从快照重算，不累加。
2. `onPreview`（每帧，只改本地 state）与 `onCommit`（`pointerup` 一次，写 store）分离。
3. `useEffect` 里监听 `project.tools[i].outer` 的引用变化；变了且正在拖 → 丢弃预览、结束拖拽（防 undo 与拖动打架）。
4. 边中点手柄：点击后立即插入顶点并**进入拖拽状态**。
5. 拖边 = 沿该边外法线平移两个端点；外法线用「中点减质心」判向。
6. 顶点/边手柄的命中优先级：顶点 > 边中点 > 边；装饰性元素 `pointer-events: none`。
7. 删除顶点到 3 个时拒绝，并 toast「至少保留 3 个顶点」。

### 6.4 手孔编辑器

- **6 种形状**：`scoop`（斜坡，`embedDepth < 20` 时唯一可用）、sphere（球缺）、cylinder（圆柱）、square、rect、filleted_rect。**形状选择器按 `embedDepth` 过滤**（`embedDepth < FINGER_REACH_MM(20)` 只给 `scoop` 系；判据见 §7.4，**不是按板厚**）。
- 拖拽平移、旋转手柄（仅非圆形）、宽高/半径数值框、深度模式切换（blind/through）。
- 默认值：`radius=15`、`width=30 height=20`、`depthMode='blind'`、`depth = min(board.embedDepth + 8, board.thickness)`。**clamp 只对 `blind` 有效**；`through` 时 `depth` 被忽略、切刀下界取 −1。
- **自动放置**：调用 `/api/finger-holes/auto`，沿工具外轮廓的 PCA 主轴找**与槽壁距离最近的两端**，各放一个手孔；用户可删。**必须重写**现有 `_auto_detect_finger_slots`（`cad_engine.py:407`）——它现在只会生成水平胶囊、且直接吃像素坐标，换成竖直孔/scoop 后会静默失效。

---

## §7 几何流水线（后端）

### 7.1 模块划分

```
python_backend/
  main.py                     # 仅路由与信封；旧路由在 GEO_ENGINE=legacy 时保留，=new 时逐步切走
  api/schemas.py              # Pydantic 请求/响应模型
  api/errors.py               # 错误码枚举 + 异常类
  models/domain.py            # §3.2
  imaging/warp.py             # 纸角检测 + 透视 + 去畸变 + 10px/mm
  imaging/quality.py          # 照片体检
  imaging/contour.py          # 轮廓提取 + 亚像素 + 质量分
  geometry/polygon.py         # shapely 工具: 归一化/间隙/简化/校验
  geometry/board.py           # 板外形（rect / gridfinity）
  geometry/pockets.py         # 切刀生成（直筒 + 倒角锥台 + 内孔）
  geometry/finger_holes.py    # 6 种手孔
  geometry/split.py           # 分块 + 定位销
  geometry/checks.py          # L0/L1 校验
  export/stl.py
  export/dxf.py
  constants/gridfinity.py     # 抄 cq-gridfinity constants.py
```

**`cad_engine.py` 保留但冻结**：新代码不 import 它；M4 时删除（先 git tag 一份）。

### 7.2 板外形

```python
def build_board(board: BoardConfig, tools: list[Tool]) -> tuple[Manifold, Rect]:
    """返回 (实体, 板在纸面坐标里的外接矩形)。所有输入输出为板局部 mm。"""
```

**rect**：
1. 所有工具外轮廓的并集 bbox，各边 + `margin`。
2. `_rounded_box(w, h, thickness, cornerR, edgeRoundover)`：`CrossSection` 矩形 → `offset(- cornerR)` → `offset(+ cornerR, JoinType.Round)` → `extrude(thickness)`。
   **▸ "倒角"拆三个独立参数，字段名以 §3.1 的 camelCase 为准**（v1.0 草案里 `fillet`/`corner_r`/`slot_chamfer` 三名混用，已删除旧名）：

   | 字段（代码内） | TS 字段 | 作用面 | 几何 | 默认 |
   |---|---|---|---|---|
   | `corner_r` | `cornerR` | 板在 XY 平面的四角 R | 上面的两次 offset | **5mm**（原写 6，统一为 5） |
   | `edge_roundover` | `baseEdgeRoundover` | 板**顶面**沿外框一周的圆角 | `board_solid ∩ (顶面外圈的倒圆扫掠)`,用一个沿外框路径扫掠的 `Manifold`；**v1 允许降级为 `board_solid ∩ 半圆柱沿四条边`** | 0（关） |
   | `slot_chamfer` | `slotChamfer` | 槽口插入导向 | §7.3 第 7 步的锥台 | **1.5mm** |
3. 返回的 `Rect` 用于 §7.6 的边界校验与 §8 的分块。

**gridfinity**：
1. `unitsX/unitsY` 由工具 bbox 向上取整：`unitsX = ceil((bboxW + 2*margin) / 42)`，最小 1。用户可在参数面板手动改大。
2. **外形尺寸 = `unitsX * 42` × `unitsY * 42`**（顶面净尺寸）。`GRU_CUT = 42.2` 不改变外形，只用于底座切槽的内部尺寸——**不要自己推导，直接读 `constants/gridfinity.py` 的剖面元组**。
3. **▸ 高度 = `heightU * 7`**（`GRHU=7`，含底座）。3U 必须 = **21mm**。现有的 `height_u*7.0 + 5.0`（`models.py:105`）让 3U = 26mm，比标准高 5mm，**摞不上**；也不要写成 `heightU*7 + 4.75`（= 25.75，同样错）。
   深度 clamp 因此分外形（§3.1 里 `embedDepth` 的「强制 <= thickness-2」**只对矩形板生效**）：矩形 `embed ≤ thickness − 2`；Gridfinity `embed ≤ heightU*7 − 4.75 − 2`，且**槽不得进入堆叠唇区域**（唇高 8.2mm，占顶面外圈）。
   **断言**：`build_board(...).bounding_box()[1][2] == heightU * 7 ± 0.01`（3U → 21mm）。
4. 底座剖面：按 `GR_BASE_PROFILE` 三段（第一段上倒角、中间 1.8mm 直壁、第三段下倒角），**每段单独 `extrude(scale_top=...)` 后 union**。段高之和必须等于 `GR_BASE_HEIGHT = 4.75`，跑一条断言卡住它。
5. 堆叠唇：按 `GR_LIP_PROFILE` 五段，做在顶面外圈。
6. 磁吸孔：每格四角，**孔心相对格心 ±13mm**，φ6.5 × 2.4 深，从底面往上打。

### 7.3 槽切刀（M1 核心）

```python
def build_pocket_cutter(
    tool: Tool, board: BoardConfig, board_center: Vec2
) -> Manifold:
```

步骤（**顺序不能变**）：

```
1. 纸面 mm → 板局部 mm：`to_board_frame(tool.outer, board_center)`（§2.3，唯一翻转）
2. 绕向归一化：外 CCW / 孔 CW（§2.4）
3. 修自交: shape = Polygon(outer, interior).buffer(0)
4. 简化: shape = shape.simplify(0.15, preserve_topology=True)
   ★ 必须先简化、后加间隙。简化会把轮廓向内啃掉最多一个 tolerance，
     放在 buffer 之前啃的是"工具轮廓"（无害）；放在之后啃的就是"间隙"（把 0.4mm 间隙啃成 0.25mm）。
     这是 tracefinity polygon_scaler.py:237-249 注释里写死的教训，v0.3 的 §7.3 顺序反了。
5. 间隙: shape = shape.buffer(clearance, join_style=2, mitre_limit=2.0)
   - buffer 结果为空 → 抛 GEOMETRY_INVALID
   - 视觉上能看出"薄颈是否被撑爆"：比较 buffer 前后的 `len(exterior.coords)` 与面积差；颈宽 < 2×clearance 时 warn「该处间隙会连通两侧槽"
6. 建 CrossSection（内孔走 EvenOdd）:
   cs_in = CrossSection(outer_ring, hole_rings, FillRule.EvenOdd)
   if cs_in.area() <= 0: 整组反向重试一次; 仍 <=0 → GEOMETRY_INVALID
   （`shell_of` / `cs_centered_at_origin` 是 v1.0 草案里的伪代码占位，正文没有定义——此处给出可直接落地的写法）
7. 拉伸直筒（先平移到原点，`scale_top` 绕原点缩放）:
   b = cs_in.bounds(); cx, cy = (b[0][0]+b[1][0])/2, (b[0][1]+b[1][1])/2
   cs0 = cs_in.translate((-cx, -cy))
   cutter_cyl = Manifold.extrude(cs0, depth + 1).translate((cx, cy, thickness - depth))
   - z 范围: [thickness - depth, thickness + 1]     ← 必须刺出顶面 1mm（F1 修正）
8. 倒角锥台（仅当 chamfer > 0）——顶面外扩，宽度比 > 1:
   eff   = min(chamfer, max(0, depth - 1))
   cs_o  = cs0.offset(eff, JoinType.Round)          # 外扩一个 eff
   bi, bo = cs0.bounds(), cs_o.bounds()
   sxy   = ((bo[1][0]-bo[0][0]) / (bi[1][0]-bi[0][0]),
            (bo[1][1]-bo[0][1]) / (bi[1][1]-bi[0][1]))   # 两者都 > 1
   cutter_chamfer = Manifold.extrude(cs0, eff + 0.01, scale_top=sxy) \
                          .translate((cx, cy, thickness - eff))
9. return cutter_cyl + cutter_chamfer
```

**关键数值**：
- 切刀 z 上界 = `thickness + 1.0`（保证开口）；下界 = `thickness - depth`。
- **▸ 锥台的 z 区间是 `[thickness − eff, thickness]`**（第 8 步的 `translate(..., thickness - eff)` + 高度 `eff + 0.01` 正好如此）：**底面与槽底方向一致、顶面与板顶面齐平再向上溢出 0.01 保布尔稳定**；宽度从下往上变大（`scale_top > 1`），形成喇叭口导向。
  两个反例都会**静默失败**：(a) 把锥台放在 `z ∈ [thickness, thickness + eff]` → 整个锥面悬在板顶上方 1mm 的空气里，槽口仍是直角，而"剖面能看到锥面"的 DoD 照样通过；(b) 沿用 tracefinity 的 `wall_top_z − eff_chamfer` 却把板改成 ±H/2 居中 → 同 (a)。**因此 z 原点必须只有一处定义（§2.3），且此处断言 `cutter_chamfer.bounding_box()[1][2] ≈ thickness + 0.01`。**
- 切刀的 `CrossSection` **必须平移到原点再 extrude**（`scale_top` 绕原点缩放）。
- 内孔：见上第 6 步（`FillRule.EvenOdd`，面积 <= 0 时整组反向重试一次）。

### 7.4 手孔切刀

```python
def build_finger_hole_cutter(hole: FingerHole, board: BoardConfig, board_center: Vec2) -> Manifold
```

| shape | 几何 | z 范围 |
|---|---|---|
| `sphere` | **球缺**：`r = min(radius, depth, thickness - 1)`，`centerZ = thickness - depth + r`，球体与 `z >= 0` 求交 | 从顶面下探到 `thickness - depth`，**不得穿透板底**：断言 `abs(bounding_box()[0][2] − (thickness − depth)) <= 0.01`（**原来的 `>= 0` 恒真**：球底 = `centerZ − r = thickness − depth`，而 `depth ≤ thickness` 必然成立，等于没查） |
| `cylinder` | `Manifold.cylinder(r, h)` | `[thickness - depth, thickness + 1]` |
| `square`/`rect` | `Manifold.cube([w, h, depth+1])` 绕 Z 旋转 | 同上 |
| `filleted_rect` | X/Z 剖面扫掠（圆底角半径 = `min(w/3, depth/2)`） | 同上 |

- `depthMode == 'through'` → 切刀下界取 `-1`（贯穿）。
- `chamfer > 0` → 与槽倒角同样的 `offset + scale_top` 锥台，加在顶面。
- **手孔坐标同样要用 `to_board_frame`**（这是现有代码最严重的错位 bug）。**`rotation` 必须取负**：`to_board_frame` 的 y 取负是镜像，镜像下「逆时针」变「顺时针」；`filleted_rect` 的圆角位置与 `scoopDir` 的朝向都会反，而 0.6 的 L 形 fixture 抓不到（它只查外轮廓）。

**▸ 审核修订（D①）按板厚选形态——竖直孔在薄板上物理上不成立：**

| 板厚 `thickness` | 手孔形态 | 理由 | 机检断言 |
|---|---|---|---|
| **`embedDepth < 20`**（薄板必然落在这档：矩形 6/12 板 `≤ 4/10`，Gridfinity 3U `≤ 14.25`） | `scoop` 斜坡：从板顶面向凹槽方向做一段斜坡，**与槽连通**（`scoopWidth` 10–15mm 默认 12，`scoopAngleDeg` 默认 45，坡底 = **槽底** `z = thickness − embedDepth`） | 手指要够到工具**底面**才能捏住侧壁；`embedDepth` 就是板顶到工具底面的距离，不够 20mm 时竖直孔伸到底也够不到 | `scoop` 的 `CrossSection` 与槽切刀相交面积 > 0（真的连通）；`abs(scoop.bounding_box()[0][2] − (thickness − embedDepth)) ≤ 0.01` |
| **`embedDepth ≥ 20`**（矩形 25 板可选；Gridfinity 需 6U 以上） | `cylinder` / `sphere` 竖直通孔 | 板够厚，指尖能下探到工具底面以下 | `hole.bounding_box()[0][2] <= 0.1`（真的贯穿到板底，不是盲孔） |
| **Gridfinity** | **不单独判档**：`embedDepth` 的 clamp 上界是 `heightU*7 − 4.75 − 2`，直接用这个 `embedDepth` 套同一判据 | 判据与外形无关；3U 得 14.25 < 20 → scoop，6U 得 28.25 ≥ 20 → 可选竖直孔 | 同上两条 |

- **禁止**在 `embedDepth < FINGER_REACH_MM` 时提供竖直孔选项；UI 的形状选择器按 **`embedDepth`** 过滤（**不是按板厚**）。判据是连续的、矩形与 Gridfinity 共用同一套，因此**不存在任何空档**——v1.1 按板厚分档时 Gridfinity 3U 的「等效厚度 16.25」落进 12–25 之间，是真实存在的 bug（第三轮审核 P0-1）。
- **`_auto_detect_finger_slots`（`cad_engine.py:407`）必须重写**：它现在用 PCA 主轴取两端、各放一个水平胶囊，换成竖直孔/scoop 后这段逻辑会**静默失效**（不报错，只是孔出现在与工具无关的位置）。重写要点见 §6.4。

### 7.5 布尔与导出

```python
solid = board_solid
for cutter in all_cutters:      # 槽 + 手孔
    solid = solid - cutter
```

- 用 `manifold3d` 的 `batch_boolean` 一次性减去所有切刀（比逐个减快 3–5 倍，且中间结果不落地）。
- 失败（`status() != NoError`）→ `GEOMETRY_INVALID`，`detail` 带 `status()` 字符串。
- STL：`manifold.to_mesh()` → `trimesh.Trimesh(vertices, faces)` → `export(file_type='stl')`。**binary STL**。
- 单位：STL 无单位，**文件名与 `summary` 里必须标 mm**。

### 7.6 边界与深度校验（生成前，不是生成后）

```python
def precheck(project: Project) -> list[Issue]:
```

1. `embedDepth > thickness - 2` → `DEPTH_EXCEEDS_THICKNESS`（自动 clamp 并 warning，**不阻断**）。该码虽然出现在 §4.0 的错误枚举里，但**只用于 warning、永不置 `success:false`**——枚举与严重度是两个维度。
2. 任一工具 bbox 超出纸面 3mm → `TOOL_OUT_OF_PAPER`（阻断）。
3. 工具之间槽重叠（间隙后仍相交）→ warning「工具 A 与 B 的槽重叠，生成后会连成一片」，不阻断。
4. 单工具最长边 > `min(printBed.x, printBed.y) - 2*margin` → `TOOL_TOO_LONG`（阻断，见 §8.4）。
5. 板 bbox 超过 `printBed` 且 `splitEnabled == false` → warning「板超出打印尺寸，请开分块」。
6. **▸ 审核修订（D10'）最小筋厚**：相邻两个槽（含间隙后）、槽与板边、槽与手孔之间的最近距离 < 2.0mm → warning「此处筋厚 X mm，打印后易断」。这个值用真实几何量：`min(shapely.distance)` 或 `Manifold.min_gap(other, search_length=5.0)`，**不要用 bbox 估算**。
7. **▸ 审核修订（D8'/B⑥）Gridfinity 专属 clamp**：板为 gridfinity 时，`embed > heightU*7 − 4.75 − 2` → 直接 clamp 到该值并 warning；若某槽的 bbox 进入堆叠唇区域（顶面外圈 8.2mm 带）→ 阻断 `GEOMETRY_INVALID`。
8. **▸ 静默失败收口**：`precheck` 之外，生成阶段的每个 `except` 都必须把异常写进 `issues[]` 并把 `success` 置 false。**禁止 `except: print(...)`**。旧 `cad_engine.py` 已冻结，只允许在其 `except` 分支追加一行计数。
9. **▸ 第二轮审核新增：`tools_in_board`（阻断）**。取板顶下方 0.01mm 的截面多边形，断言每个槽（已加 clearance）与每个手孔轮廓**完全落在**截面多边形内；否则 `TOOL_OUT_OF_BOARD`。**没有这一条，gridfinity 格数改小或手孔拖到板外时，切刀切的是空气——水密、体积、checks 全绿，用户拿到一块没有任何槽的实心板。**
   同时 `unitsX*42 < bboxW + 2*margin` 时自动 clamp 并 warning（用户只能改大、不能改小到装不下）。
10. **▸ 出错出路**：上述任一阻断触发时，`error.detail` 必须带可执行的三个出路（例：`TOOL_OUT_OF_BOARD` → "调大格数 / 缩小 margin / 把该工具移出本板"），不准只给一个错误码。

---

## §8 分块

### 8.1 触发

`board_w > printBed.x - 2*edge` 或 `board_h > printBed.y - 2*edge`，其中 `edge = 5mm`（给 brim 留空间）。

### 8.2 切缝位置

沿 X 方向求 `n = ceil(board_w / (printBed.x - 2*edge))` 段。对每个候选切缝 `x_i = i * board_w / n`：

1. 计算所有工具槽（**已加间隙**）在 X 轴的投影区间集合 `intervals`。
2. 在 `x_i ± searchWindow (= 20mm)` 内寻找「不落在任何 interval 内」的位置，取离 `x_i` 最近的。
3. 找到 → 用该位置；找不到 → 尝试把 `n` 加 1 重试（最多 +3）；仍找不到 → `NO_SPLIT_RIB`。
4. **▸ v1 直接禁用 Gridfinity 板的分块**——锥台底座、堆叠唇、磁吸孔都是按整板一次成型的，切开后中间片的底座与唇全部断裂，粘起来也摞不上标准底座。请求对 gridfinity 板分块 → 返回 **`GRIDFINITY_SPLIT_UNSUPPORTED`**（与"找不到筋"的 `NO_SPLIT_RIB` 分开，客户端才能给不同文案），文案「Gridfinity 板暂不支持分块，请调大打印尺寸或改用自定义矩形板」。
   （v2 的解法是每片各自重建完整底座、边界外扩一格，不在本版范围。）
5. 切缝所在位置的**实心筋厚必须 ≥ 4mm**（不是 2mm）：2mm 筋切开后每侧只剩 1mm，粘接面太薄。找不到 ≥4mm 的筋 → `NO_SPLIT_RIB`。

### 8.3 切分与定位销

- 切分用 `solid ∩ box`（不是 `split_by_plane`）：对每片构造一个大包围盒求交，天然封口。
- 定位销：在**每条切缝**上均匀放 2 个（板高 < 150mm）或 3 个（≥150mm）销孔，距板边 ≥ 12mm。
  - 孔 1：在片 A 的切面上，深 8mm，φ`pinDiameter`。
  - 孔 2：在片 B 的切面上，同位置，深 8mm。
  - 实现：两个 `cylinder` 分别从切缝面向内打，**向片内方向各退 0.05mm** 保证布尔稳定。
- **▸ 审核修订（R5）销必须是水平孔，禁止竖直盲孔**：
  - 销轴方向 = **垂直于切缝、从切缝面水平钻入**（`cylinder` 的轴沿切缝法线）。φ4×8 的**竖直**盲孔在 6mm 板上根本不可能（孔深 8 > 板厚 6），在 2mm 筋上打 φ4 会直接破进槽。
  - 可落销的筋厚阈值提到 **≥5mm**（比切缝筋的 4mm 更严）；不够就改 φ3×6，仍不够就少放一个销。
  - `销长 = 2 × 孔深 − 1mm`（留 1mm 让两片不留缝）。`summary` 里输出销位与销长，供用户买现成销或打印。
- 销孔**避让槽**：若销位落进任何槽的投影 → 沿切缝平移找最近空位。
- 粘接提示：`summary` 里输出 `glueOrder`（建议粘接顺序）+ 每片的外形尺寸。

### 8.4 单槽跨缝（明确不支持）

若某个工具的外接框在切缝方向上跨越切缝 → 该槽会被劈开。**v1 直接拒绝**（§7.6 第 4 条）。错误文案要给出具体数字：

> 「工具『活动扳手 250』长 248mm，超过你的打印尺寸 200mm（单槽无法分块）。请换成更大打印床，或把该工具移出本板。」

---

## §9 导出

### 9.1 STL

- binary STL，每片一个文件，命名 `board_A1.stl`。
- 前端打包下载（多片时用 `JSZip`，仅多片才引入，动态 `import()`）。

### 9.2 DXF（`export/dxf.py`）

```python
doc = ezdxf.new("R2010", setup=True)
doc.header["$INSUNITS"] = 6          # 毫米
msp = doc.modelspace()
msp.add_lwpolyline(outer_pts, close=True, dxfattribs={"layer": "CUT"})
for hole in interior_rings:
    msp.add_lwpolyline(hole, close=True, dxfattribs={"layer": "CUT"})
msp.add_text(f"{tool.name} 深 {depth}mm", dxfattribs={"height": 3.0}).set_placement((cx, cy))
```

- 图层：`CUT`（只放切割线：板外框 + 每个槽/内环 + 每个手孔）；`ANNO`（**只放文字标注**：工具名与深度）。板外框属于切割线，**不放 ANNO**。
- **坐标（▸ 第二轮审核修正）**：纸面 mm 是 y-down，DXF 是 y-up，因此**默认翻转 `y' = paperH − y`**，开关 `dxfFlipY` 默认 `true`。
  v1.0 草案写"不做翻转、对 1:1 切割无影响，因为板是对称外框"——**这个理由只对板框成立，对槽位不成立**：镜像会把左手工具的槽切成右手槽，切出来的嵌件装不进工具。而面积类 DoD 对镜像完全不敏感，必须用**非对称点**断言（计划 3.4）。
- 分块时 DXF 也按片输出（每片一个 `LWPOLYLINE` 集合，放在 `PIECE_A1` 图层）。

---

## §10 测试

### 10.1 后端（pytest，`python_backend/tests/`）

**▸ 审核修订（R1/R2）：M-1 的 `scripts/smoke_geometry.py` 必须最先写、且不属于 pytest 用例集。** 它只做三件事：

```python
# 合成 100×20mm 矩形 → generate → 三条断言
assert cutter.bounding_box()[1][2] > thickness + 0.9                 # ① 切刀确实刺出顶面（manifold3d 的接口是 bounding_box()）
first_hit = mesh.ray.intersects_location(
    origin=[0.0, 0.0, thickness + 10.0], direction=[0.0, 0.0, -1.0])[0][0][2]
assert abs(first_hit - (thickness - embedded_depth)) < 0.05          # ② 首击在槽底，不在顶面（射线要落在槽内部，不能落在角顶点）
assert abs(pocket_length_mm - 100.0) < 1.0                           # ③ 尺寸对
```

② 是 F1 的**唯一**可靠证据：密闭空腔的首击会落在 `z = thickness`。没有这条断言，`success + volume>0` 会把错误固定下来。

| 类型 | 数量 | 内容 |
|---|---|---|
| golden | 3 | 合成图 → 已知 100×60mm 矩形 → 断言 STL 槽长宽误差 ≤ 0.5mm |
| 单元 | ~15 | `to_board_frame` 四角映射、绕向归一化、buffer 空、切刀 z 边界、分块位置选择 |
| 契约 | 5 | 每个端点用 `TestClient` 打一次，断言信封结构与错误码 |
| 回归 | 3 | 内孔（圆环工具）不被填实；倒角 chamfer=0 与 1.5 的剖面差异；**故意让 1 个槽失败 → 接口必须 `success:false`** |

**没有 Python 环境时的降级**：`geometry/` 与 `imaging/` 的纯函数部分**不 import cv2/trimesh**，可用 `pytest` 在只有 numpy 的环境跑（CI 与本地都不至于全瘫）。这条是架构约束，不是建议。

### 10.2 前端（jest）

| 文件 | 内容 |
|---|---|
| `frame.test.ts` | `toScreen`/`toPaper` 往返 |
| `snap.test.ts` | 吸附优先级 |
| `project.test.ts` | undo/redo 粒度：一次拖拽只产生一条历史 |

---

### 10.3 容差总表（唯一真源，计划里的 DoD 一律引用这里）

| 量 | 容差 | 用在哪 |
|---|---|---|
| 合成图 → STL 槽长宽 | **±0.5mm** | 计划 0.6 golden |
| 切刀截面积（相对设计值） | **±0.1%** | 计划 0.3 |
| M-1 冒烟 / M0 阶段切刀长度（尚无 clearance） | **±0.1mm**（**不是 ±1**） | 计划 M-1、0.3 |
| 间隙后外扩量 | **±0.05mm** | 计划 1.2 |
| 真实照片端到端（S0 承诺） | **±1.5mm** | 计划 D11'，**只由 1.3 的扳手照片用例锚定** |
| 唇各段高度 / 总和 | ±0.05 / ±0.05 | 计划 1.4b |
| 分块两片 bounds 之和 vs 原板 | ±0.01mm | 计划 3.2 |
| DXF 读回面积 / 非对称点 | ±0.1mm² / ±0.01mm | 计划 3.4 |

**规则：新增 DoD 前先查这张表；同一个量只允许一个容差。**（v1.0 草案里 0.5 与 1.0、±0.05mm² 与 ±2×clearance 互斥，已在此收敛。）

## §11 目录与构建

### 11.1 新增目录

```
python_backend/
  api/ models/ imaging/ geometry/ export/ constants/ tests/
src/
  types/ store/ geometry/ components/editor/
docs/planning/
  v1-plan-v1.2.md   v1-sds-v1.2.md
```

### 11.2 `requirements.txt`（必须写全）

**▸ 审核修订（R1）先写清目标环境**：WSL Ubuntu 26.04 自带 **Python 3.14.4**，没有 `pip`、没有 `gcc/make`。因此：

1. **不能用现有 pin**：`numpy==1.24.3` 没有 cp314 wheel（必源码编译）、`cadquery==2.8.0` 没有 cp314 wheel、`scipy` 在本项目**无调用点**。
2. **删 `cadquery`**：它只被 `cad_engine.py:803` 懒加载，服务的是已砍掉的 `/generate-step`。
3. **必须 venv**（Ubuntu 走 PEP 668）：`sudo apt install python3-venv && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`。
4. **必须 headless 版 opencv**：`main.py:4` 顶层 `import cv2`，非 headless 版在无 X 的 WSL 里会撞 `libGL.so.1`。

```
# python_backend/requirements.txt  —— 下限 pin，不用 ==（避免 cp314 无 wheel）
fastapi>=0.115
uvicorn>=0.34
python-multipart>=0.0.20
numpy>=2.1
opencv-python-headless>=4.11
shapely>=2.2
manifold3d>=3.5.4
trimesh>=4.4
scikit-image>=0.25
ezdxf>=1.3
pillow>=11
pytest>=8.3
```

> `trimesh` 导出 3MF 才需要 `networkx`/`lxml`，而 3MF 已砍（计划 §5），**不要装**。

### 11.3 `vite.config.ts` 加代理

```ts
server: { proxy: { '/api': { target: 'http://127.0.0.1:8001', changeOrigin: true } } }
```

前端 `api/client.ts` 里所有 URL 用相对路径 `/api/...`，**禁止硬编码 localhost:8001**。

### 11.4 Git

- 开工前先 `git checkout -b feat/v1 && git add -A && git commit -m "chore: snapshot before v1"`（**必须 `git add -A`，不能用 `-am`**——`-a` 不纳入未跟踪文件，而工作区里正好有未跟踪的 `docs/planning/*.md`，漏掉它们基线就不完整）。当前工作区有大量未提交改动，**必须先提交一份快照**，否则 M0 改坏后无法回滚。
- **▸ 审核修订（R6）仓库里有个必须先处理的坑**：`node_modules` 被 git 跟踪了 **10369 个文件**（`.gitignore` 只对未跟踪文件生效），`.git` 已达 187MB；`cad_engine.py.bak` 是 8/13 的旧版，不能当回滚点。开工第一步：

```bash
git rm -r --cached node_modules
git commit -m "chore: untrack node_modules"
git tag pre-m0
```

- **M0 起写新模块**（`python_backend/geometry/`），`main.py` 加环境变量开关 `GEO_ENGINE=new|legacy` 保留旧路径；M1 全绿后再删旧代码。**不要在原 `cad_engine.py` 上就地改**——没有测试网，改坏了无从对比。

---

## §12 实施协议（给主会话与子 agent）

### 12.1 分工

> **▸ 审核修订（A）：任务编号与计划 v1.0 §4 严格对齐**——`0.3b` / `0.7` / `0.8` / `1.0` / `1.4a-c` / `2.3a-b` 都是计划里的一等任务，子 agent 的交付清单必须按这个编号报。

| 阶段 | 主会话 | 子 agent |
|---|---|---|
| **M-1**（0.5d） | 定冒烟脚本的三条断言 | 1 个：`scripts/smoke_geometry.py` + venv |
| **M0**（2.5d） | 写 §2 的断言、跑通环境、验收 | **分三批，不是全并行（有阻塞边）**：**批 1（无依赖，先开）** `0.1` 环境与 requirements ｜ `0.2`+`0.7`+`0.8` z 基准与校验库；**批 2（依赖批 1）** `0.4`→`0.5`→`0.6`（warp → 照片体检 → golden）；**批 3（依赖 `0.4` 的毫米坐标，最后开）** `0.3`+`0.3b`。**`0.3` 不能与 `0.4` 并行**——没有 10px/mm 校正图就没有毫米坐标可删。 |
| **M1**（3.5d） | 定切刀参数、验收 STL | **3 个并行**：`1.0b`+`1.4a/b/c` 参数与底座唇磁孔 ｜ `1.1`+`1.2` 槽切刀与间隙 ｜ `1.0`+`1.3`+`1.5`+`1.6` 多轮廓、内孔、手孔、矩形外壳 |
| **M2**（3d） | 定交互契约、验收 | **3 个并行**：`2.1` PolygonEditor ｜ `2.2` ToolEditor ｜ `2.3a/b`+**`2.4`** 三参数联调与多工具前端 |
| **M3**（3.5d） | 定分块算法、验收 | **3 个并行**：`3.2` 分块 ｜ `3.4` DXF ｜ `3.1`+`3.3` 纸角手拖与试切件 |
| — | — | **并行说明**：`3.1`/`3.2`/`3.3`/`3.4` 只依赖数据模型（§3），**M1 一开工即可与 M1 并行**，不必等 M3（第二轮审核指出 v1.0 把可并行的项全排在 M3）。 |
| **M4**（1.5d） | 全量回归、文档同步 | 1 个：`4.1`–`4.4` |

### 12.2 每个子 agent 的交付格式

1. 改动文件清单（绝对路径）
2. 每个文件的**关键行号 + 该行做什么**
3. 跑过的命令与输出（不许写"应该能跑"）
4. 未完成项与原因

### 12.3 审核 agent 的固定检查项

- 有没有出现 `840`、`1188`、`±H/2`、`H/2`、`localhost:8001`、`bounding_box` 之外的 bbox 写法（`bounds()[1][2]` 对 `Manifold` 不成立，`CrossSection` 才有 `bounds()`）
- 有没有在 `geometry/` 里 import `cv2`
- 切刀 z 上界是否 ≥ `thickness + 0.9`
- 内孔是否走了 `FillRule.EvenOdd`
- 有没有 `except: print(...)`（禁止吞异常）
- 有没有未归一化的绕向直接送进 `CrossSection`
- 有没有在 `simplify` 之后才 `buffer(clearance)`（顺序反了会静默吃掉间隙）
- 有没有在 `embedDepth < 20` 时生成竖直手孔（判据是 embedDepth，不是板厚）
- 有没有竖直定位销孔（必须是水平、从切缝面钻入）
- 有没有对 gridfinity 板分块（v1 必须拒绝）
- `heightU*7` 还是 `heightU*7+5`（后者 3U=26，摞不上）
- 有没有把 `mmPerPx` 读进下游计算（只许回显）
- 有没有在移植代码里保留 `-(p[1] + offset_y)` 取负（入参已是 y-up，再取负 = 竖直镜像）
- `BoardConfig` 的板级参数是否只有 `cornerR` / `baseEdgeRoundover` / `slotChamfer` 三个（出现 `fillet` / `corner_r` / `base_chamfer` 一律打回）
- 手孔形态是否用了 `12 < thickness < 25` 的中间档（板厚只有 6/12/25）
- `sphere` 手孔的 `bounding_box()[0][2]` 是否 ≥ 0（不得穿到板底以下）
- `from_dict` 是否静默忽略未知字段（必须 400 `SCHEMA_UNKNOWN_FIELD`）
- 是否校验了"槽/手孔完全落在板轮廓内"（`tools_in_board`）

**任一项不过 → 打回，不合并。**
