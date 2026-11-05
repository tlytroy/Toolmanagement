# Toolmanagement-web 软件详细设计说明（SDS）v1.3

> 状态：**v1.3 定稿 —— 已过六轮独立审核（第 5、6 轮 geo/contract 双 lens 均判「需小修」，must-fix 已全部合并）；环境已验证可用（WSL venv + 依赖装通）；可开工**
> 上游计划：`docs/planning/v1-plan-v1.3.md`
>
> **v1.3 = v1.2 + 第四轮审核修订（8 处）。** 两个 lens 独立得出同一根因：判据换了新变量、几何仍按旧变量写。本版做三组全局替换：
> **① `thickness` → `top_z`**（新增唯一量 `top_z`：rect = `thickness`、gridfinity = `heightU*7`）。原写法在 gridfinity 上让切刀整体下移 9mm、槽成密闭内腔、`slot_open` 恒 false。
> **② `scoop` 补真几何**（落差 = 生效 `depth`、`run = depth/tan(angle) ≤ margin − clearance`、坡宽 `scoopWidth` 不参与进深、楔块向槽内侵入 ≥0.5mm）；连通性断言从「2D∩3D」改为 3D 体积求交。它是开箱默认路径，此前无几何。
> **③ 手孔 z 断言按 `depthMode` 二分**、`depth` 加双端 clamp、`embedDepth` 滑块上界改 `top_z`、唇新增 `LIP_WIDTH = 2.6`、冒烟容差改 ±0.1。
>
> 第四轮 P1 亦已修完：`depth` 进 `build_pocket_cutter` 签名并给唯一绑定式（N6）、1.1 的倒角 DoD 改为凸包边中点（N9）、并行说明改为「仅 3.1/3.4 可提前，3.2/3.3 需实体」。
>
> **第六轮 delta 审核（只审 ⑦⑧ 两条反馈引入的新矛盾）** geo / contract 双 lens 均判「需小修」，8 条 must-fix 已合并：
> ① 板框锚点 = **未隐藏工具并集 bbox 中心**（原「板外接框中心」在 custom/print-bed 下无解）；
> ② `print-bed` 改取 `printBed − 2*edge`（原取整张床，`220 > 220−10` 恒真 → 必然分块得 4 片 110×110）；
> ③ `board_size_mm()` 为板尺寸唯一真源，gridfinity 恒返回 `(units*42, units*42)`；`unitsX/unitsY` 由后端 `derive_units()` 派生；
> ④ scoop 的 `run` 上界改 `d_edge − clearance`（实测距离，不是 `margin`）；
> ⑤ `TOOL_TOO_LONG` 改 `2*edge`（不是 `2*margin`，否则 margin 8→12 会让 200mm 扳手突然做不了）；
> ⑥ 2.5 板尺寸控件记 0.5 人日，M2 3.0 → 3.5、总 14.5 → 15.0；
> ⑦ `INVALID_SIZE_MODE` 判据写死 `is not None`（否则每个默认请求都 400），`ValueError` 统一映射 400；
> ⑧ 「留白吃掉畸变」改为吃**板边/构图余量**、不修正轮廓，S0 ±1.5mm 只对离纸边 ≥ 20mm 的工具承诺。
>
> **v1.3 增补（用户 m02193 两条反馈，2026-11-03）：**
> **⑦ 板尺寸独立**：`BoardConfig.sizeMode` 三选一（`'fit-tools'` / `'custom'` / `'print-bed'`）+ `widthMm`/`heightMm`；板大时允许留白、不自动居中不自动排布；三种模式一律过 `tools_in_board` 板内校验。见 §3.1、§7.2、§7.6 第 9 条。
> **⑧ 畸变不标定不告警**：`margin` 默认 12；删除 `distortionWarningMm` 字段与流程图里的「镜头去畸变」。见 §1.1、§2.1、§4.2、§7.2、§11.1。
>
> **第五轮终验（geo lens + contract lens 各独立跑一遍）两方均判「需小修、可开工」，must-fix 已在本次全部合并**（26 处）：
> ① scoop 三处过定——`run <= d_edge − clearance`（`d_edge` 为槽壁到板轮廓的实测距离；原 `<= margin` 在 custom/print-bed 下与真实余量无关）、楔块向槽内侵入 ≥0.5mm（否则连通性断言恒 0）、`scoop` 排除 `depthMode=through`；坡底与判据统一用**生效 `depth`**（`depthOverride ?? embedDepth`），不是 `board.embedDepth`；
> ② `sphere` 加开口守卫 `centerZ + r > top_z + 0.1`（`radius < depth/2` 时生成密闭内腔 = F1 复发）且只允许 `blind`；
> ③ `embedDepth` 上界改分外形（原写「即 `top_z−2`」让 3U 板得 19，槽底切进 4.75 高的锥台底座）；
> ④ `LIP_WIDTH` 改由剖面各段**水平投影**求和（原写 `LIP_D0+LIP_D2` 是把两个垂直段高相加当径向宽度）；
> ⑤ `checks` 补谓词（`depth_fits` 判**请求值**否则恒真、`genus` 给 `expected`、`slot_open` 给容差）；
> ⑥ `warnings[]` 定为 `{code, message, detail}` 并单列 warning 码表（`SCOOP_CLAMPED` 此前不在任何枚举里）；
> ⑦ 后端领域模型目录定为 `python_backend/domain/models.py`（**不要建 `python_backend/models/`**，与既有 `python_backend/models.py` 撞名会让 `cad_engine.py:59` 的裸 `from models import` 在 M0 期间直接 ImportError）；
> ⑧ 冒烟显式 `clearance = 0`（默认 0.4 会让槽长变 100.8、±0.1 断言必红）；出顶量统一为 `[0.9, 1.0]` 区间。
> **v1.2 = v1.1 + 第三轮独立审核修订。** 7 条 P0 全部修完：手孔形态改单一连续判据 `embedDepth ≥ 20`（原按板厚分档有空档；**v1.3 已再改为生效 `depth`**，见 §7.4）、scoop 坡底改 `top_z − embedDepth`（原式切穿板底；**v1.3 已再改为 `top_z − depth`**）、`sphere` 断言改绝对值（原 `≥ 0` 恒真）、`wantDxf`/`dxfFlipY` 进 `BoardConfig`、PY `FingerHole` 补 scoop 三字段、错误码补 4 个、磁孔改为「孔心距格心 ±13」。
>
> **v1.1 = v1.0 + 第二轮独立审核（closure / cold-read）修订，共 39 处。** 关键：`to_board_frame` 改签名与符号、板厚改 6/12/25 枚举、`HoleShape` 加 `scoop`、未知字段改 400、跳过 `bounds()`/`bounding_box()` 混用、DXF 默认翻转、新增 `tools_in_board` 校验与 §10.3 容差总表。全部改动处带 `▸ 第二轮审核` 或 `▸ 审核修订` 标记。
> 上游：`docs/planning/v1-plan-v1.3.md`（**15.0 人日**，M-1–M4）
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

### 1.1 本版要做（对应计划 M-1–M4，15.0 人日）

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
| 照片体检（EXIF 反算相机高度 / 纸出框 / 极端透视 三条告警）——**不做镜头标定、不做去畸变、也不做畸变告警**（用户 m02193：用 `margin` 留白吃掉 2–4mm 边界误差） | **M0**（任务 0.5；v1.1 误记为 M3） |

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
        │  透视变换（10px/mm 固定标定；不做去畸变）
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

- **板框锚点（唯一，三种 `sizeMode` 共用）**：`center = 未隐藏工具（`hidden == false`）并集 bbox 的中心` 在纸面 mm 中的点，`center = ((minx+maxx)/2, (miny+maxy)/2)`。
  **为什么不是"板外接框中心"**：`custom` / `print-bed` 下板的宽高由用户给，板在纸面里的**位置**不由尺寸决定；若取"板外接框中心"，实现只能二选一——把板心钉在工具并集中心（那正是 §7.2 禁止的"自动居中"）、或把板钉在纸角（纸面中部的工具必然 `TOOL_OUT_OF_BOARD`）。取工具并集中心则两种模式都自洽。
  **"不自动居中"的准确含义**：**不重排、不平移任何工具坐标**；板以工具并集中心为中心向四周**均分**扩张出来的留白，不算居中。
- 值域检查（随板宽变化，**不要写成"纸面四角 → (±w/2, ±h/2)"**，那是"板 = 纸"的特例）：未隐藏工具的并集 bbox 四角 → 恒为 `(±(bboxW/2), ±(bboxH/2))` 附近；`'fit-tools'` 时并集左上角 → `(−w/2 + margin, +h/2 − margin)`；`'custom'` 100×80 且并集 60×50 时 → `(−30, +25)`。板心恒为 `(0,0)`。
- **z 轴**：板底面 z = 0。板顶面记作 **`top_z`**，全项目只此一处定义——**rect：`top_z = thickness`；gridfinity：`top_z = heightU * 7`**（见 §7.2）。
  **下文一切「从板顶往下 X」的构造都写 `top_z − X`，禁止写 `thickness − X`**：gridfinity 的 `thickness` 只有 6/12/25，而板顶是 21/28/35，两者不等会让切刀整体下移 9mm、槽变成密闭内腔，`slot_open` 恒 false。
  **不是 ±H/2 居中**（`cad_engine.py:96` 的居中必须删除）。
- **断言（写进 §10.1 单元测试，必须有）**：
  ```python
  bb = slot_cutter.bounding_box()               # 扁平 6 元组 (minx,miny,minz,maxx,maxy,maxz)
  assert 0.9 <= bb[5] - top_z <= 1.0 + 1e-6      # maxZ；原写 `== top_z+1 ±1e-6` 与 M-1 的 `> top_z+0.9` 互斥
                                                 # （实现成 0.95 时一处红一处绿）；区间见 §10.3
  assert bb[2] >= 0.0                            # minZ；槽底不得穿板底（blind 时；原写 `< top_z` 恒真——depth>0 必然成立）
                                                 # through 时改断言 `bb[2] <= -0.5`
  ```

### 2.4 多边形绕向规范

- **外轮廓：逆时针（CCW）**。**绕向只在「板局部 y-up 系」里有定义，全程只归一化一次**：`signed_area(outer) > 0`（CCW）、`signed_area(inner) < 0`（CW），归一化发生在 `to_board_frame` **之后**。存进 `Project`、经 API 传出的多边形是**纸面 y-down** 坐标，y 取负使符号整体翻转——此时外环有符号面积**必为负**，这是同一套规范的镜像结果，**不是第二套规范**；序列化层不许再做任何翻转。判定函数统一用：

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
| 4 | **板原点 = 未隐藏工具并集 bbox 中心**（x/y），z 原点在板底面 | 若误取左下角，整板相对工具平移半个板宽，槽整体偏移而「看起来居中」；装不进。**不是「板外接框中心」**——`custom`/`print-bed` 下板尺寸与工具无关，取板框中心等于强制自动居中 | §2.3 `to_board_frame` 的 `center` |

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
  | 'scoop'          // 斜坡：与凹槽连通，depth < FINGER_REACH_MM(20) 时唯一可用（depth = depthOverride ?? embedDepth）
  | 'sphere'         // 球缺竖直孔，仅 depth >= 20 时可选（depth = depthOverride ?? embedDepth）
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

  // —— 板尺寸（与工具数量解耦，三种取法）——
  sizeMode: 'fit-tools' | 'custom' | 'print-bed';  // 默认 'fit-tools'
  widthMm: number | null;     // 仅 'custom' 用: 板宽, 60..400
  heightMm: number | null;    // 仅 'custom' 用: 板高, 60..400

  // —— rect 专用 ——
  margin: number;             // 仅 'fit-tools' 生效: 板边到工具并集外接框的距离, 默认 12, 范围 [2..30]
                              // （custom/print-bed 下板尺寸不依赖它; 依赖它的规则只有 scoop 的兜底提示）
  thickness: 6 | 12 | 25;     // 板厚, 三档枚举, 默认 12（仅对 rect 生效; 不参与手孔形态判定）
  cornerR: number;            // 板在 XY 平面的四角半径, 默认 5
  baseEdgeRoundover: number;  // 板顶面沿外框一周的圆角, 默认 0（关）

  // —— gridfinity 专用 ——
  unitsX: number;             // 42mm 格数, 1..40
  unitsY: number;
  heightU: number;            // 高度单位 U, 每 U = 7mm（含 4.75mm 底座）; 总高 = 7*U; 范围 2..10（1U=7 < 4.75 底座 + 8.2 唇）
  magnets: boolean;           // 是否打磁吸孔
  stackingLip: boolean;

  // —— 通用 ——
  embedDepth: number;         // 全局嵌入深度, 默认 8; 从板顶往下算。**上界分外形**（不是统一的 top_z-2）:
                              //   rect:       <= thickness - 2
                              //   gridfinity: <= heightU*7 - GR_BASE_HEIGHT(4.75) - 2   （3U 得 14.25，不是 19）
  clearance: number;          // 全局侧向间隙, 默认 0.4
  slotChamfer: number;        // 槽口插入导向倒角, 默认 1.5
  fingerHoleChamfer: number;  // 手孔口倒角, 默认 0.5 —— 绑定式: hole.chamfer ?? board.fingerHoleChamfer（§7.4）

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

**注意 `embedDepth` 的语义**：从**板顶面**往下算，单位 mm。
前端滑块上界必须用 **`top_z`**，不能用 `thickness`：rect → `[2, thickness-2]`；gridfinity → `[2, heightU*7-4.75-2]`（6U 得 **35.25**）。
**若写成 `thickness-2`，6U 板的滑块被 10 封顶，用户永远选不到 ≥20，「6U 可选竖直孔」在 UI 上不可达。**
后端再 clamp 一次（信任边界在后端）。

### 3.2 后端 Python（`python_backend/domain/models.py`，新建）

与 TS 一一对应，用 `@dataclass(frozen=True)` + `from_dict()` 显式解析（**不用 Pydantic 直接当领域模型**——Pydantic 只出现在 API 层，见 §4.0）。

> 代码块头需 `from dataclasses import dataclass, field`；`BoardConfig` 里 `print_bed` 用 `field(default_factory=...)` 正是因为 frozen dataclass 不接受可变默认值。

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
class BoardConfig:
    shape: str                       # 'rect' | 'gridfinity'
    # 板尺寸（与工具数量解耦，v1.3 / 用户 m02193）
    size_mode: str = "fit-tools"     # 'fit-tools' | 'custom' | 'print-bed'
    width_mm: float | None = None    # 仅 'custom'
    height_mm: float | None = None   # 仅 'custom'
    # rect
    margin: float = 12.0             # 仅 size_mode='fit-tools' 生效; custom/print-bed 下不参与板尺寸
    thickness: int = 12              # 6 | 12 | 25, 仅 rect
    corner_r: float = 5.0
    base_edge_roundover: float = 0.0
    # gridfinity
    units_x: int = 1
    units_y: int = 1
    height_u: float = 3.0
    magnets: bool = True
    stacking_lip: bool = True
    # 通用
    embed_depth: float = 8.0
    clearance: float = 0.4
    slot_chamfer: float = 1.5
    finger_hole_chamfer: float = 0.5
    want_dxf: bool = False
    dxf_flip_y: bool = True
    print_bed: dict = field(default_factory=lambda: {"x": 220.0, "y": 220.0, "z": 220.0})
    split_enabled: bool = True
    pin_diameter: float = 4.0

    def __post_init__(self):
        # sizeMode 与宽高必须同进同退。判据是 `is not None`（不是字段是否出现）：
        # 非 custom 模式下前端会把两字段发成 null，那是合法请求，不得 400。
        if self.size_mode not in ("fit-tools", "custom", "print-bed"):
            raise ValueError("sizeMode 必须是 'fit-tools' | 'custom' | 'print-bed'")
        if self.size_mode == "custom":
            if self.width_mm is None or self.height_mm is None:
                raise ValueError("sizeMode='custom' 必须同时给 widthMm 和 heightMm")
            if not (60.0 <= self.width_mm <= 400.0):
                raise ValueError("widthMm 必须在 60..400 之间")
            if not (60.0 <= self.height_mm <= 400.0):
                raise ValueError("heightMm 必须在 60..400 之间")
        elif self.width_mm is not None or self.height_mm is not None:
            raise ValueError("widthMm/heightMm 仅在 sizeMode='custom' 时允许出现")
        # margin 必须大于 clearance，否则 §7.4 的 run 上界恒为负、scoop 无解
        if self.margin < self.clearance + 0.5:
            raise ValueError("margin 必须 >= clearance + 0.5")

    def board_size_mm(self, tools_bbox: tuple) -> tuple:
        """返回最终实体 (w, h)。板尺寸的唯一真源，build_board 的 Rect 必须用它。

        gridfinity 恒为 (units_x*42, units_y*42)——widthMm / printBed 在那种外形下只是
        units 的种子（见 §7.2 gridfinity 第 1 条），不是尺寸本身。
        """
        if self.shape == "gridfinity":
            return (self.units_x * 42.0, self.units_y * 42.0)
        if self.size_mode == "custom":
            return (self.width_mm, self.height_mm)
        if self.size_mode == "print-bed":
            return (self.print_bed["x"] - 2 * EDGE_MM, self.print_bed["y"] - 2 * EDGE_MM)
        minx, miny, maxx, maxy = tools_bbox
        return (maxx - minx + 2 * self.margin, maxy - miny + 2 * self.margin)

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

- 错误码固定枚举（前端据此出文案，**禁止匹配中文串**）：`PAPER_NOT_FOUND`、`PAPER_OUT_OF_FRAME`、`CAMERA_TOO_CLOSE`、`EXTREME_PERSPECTIVE`、`IMAGE_TOO_SMALL`、`TOOL_OUT_OF_PAPER`（D2'）、`TOOL_TOO_LONG`（D17'）、`NO_SPLIT_RIB`（D14'，替代 v0.3 的 `SPLIT_IMPOSSIBLE`）、`EMPTY_TOOLSET`、`NO_CONTOUR`、`GEOMETRY_INVALID`、`DEPTH_EXCEEDS_THICKNESS`（**只作 warning**，见 §7.6 第 1 条）、`TOOL_OUT_OF_BOARD`（§7.6 第 9 条）、`GRIDFINITY_SPLIT_UNSUPPORTED`（§8，与 `NO_SPLIT_RIB` 分开）、`SCHEMA_UNKNOWN_FIELD`、`SCHEMA_VERSION_UNSUPPORTED`（§3.2）、**`INVALID_SIZE_MODE`**（v1.3：`sizeMode='custom'` 缺 `widthMm`/`heightMm`，或非 `custom` 模式带了宽高）、`INTERNAL`。
- **warning 码单独一张表**（永不置 `success:false`，前端据此出文案）：`DEPTH_EXCEEDS_THICKNESS`、`SCOOP_CLAMPED`（§7.4 的 run 被 clamp）、`CAMERA_TOO_CLOSE`、`PAPER_OUT_OF_FRAME`、`EXTREME_PERSPECTIVE`、`SLOT_OVERLAP`、`MIN_RIB_THIN`、**`BOARD_EDGE_TIGHT`**（工具距板边 < `margin`，见 §7.6 第 9 条）。**v1.3 删除 `DISTORTION_WARNING`**（用户 m02193：畸变用 `margin` 留白吃掉，不再做单列畸变告警；`BOARD_EDGE_TIGHT` 是板内几何提示，不是畸变告警）。
- **`warnings[]` 的元素结构固定为 `{code, message, detail}`**（与 `error` 同构）；前端**只按 `code` 分支**，`message` 仅作兜底展示。
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
    { "index": 0, "name": "board_A1", "stlBase64": "...", "bboxMm": {...}, "volumeMm3": 48231.2 }
  ],
  "dxfBase64": "...",              // 仅当请求带 wantDxf=true
  "summary": {
    "toolCount": 3, "pieceCount": 2, "boardMm": {...}, "totalVolumeMm3": 9612.4,
    "paramsEcho": { "sizeMode": "custom", "widthMm": 100, "heightMm": 80, "margin": 12,
                    "cornerR": 5, "baseEdgeRoundover": 0, "slotChamfer": 1.5,
                    "embedDepth": 8, "clearance": 0.4, "unitsX": 3, "unitsY": 2 },
                    // 非 'custom' 模式 widthMm/heightMm 回显为 null；gridfinity 的
                    // unitsX/unitsY 回显取整后的实际格数（见 §7.2）
    "slotBounds": [[x0,y0,z0],[x1,y1,z1]],   // 所有槽切刀的并集 bbox（计划 0.2 的断言靠它）
    "baseBounds": [[x0,y0,z0],[x1,y1,z1]]
  },
  "checks": [
    { "id": "shapely_valid",   "ok": true },              // L0
    { "id": "watertight",      "ok": true },              // L1
    { "id": "winding",         "ok": true },              // L1
    { "id": "manifold_status", "ok": true, "status": "NoError" },
    { "id": "genus",           "ok": true, "value": 2, "expected": 2 },   // expected = 内环数（每个通孔 +1）
    { "id": "volume_match",    "ok": true, "errorPct": 0.6 },
    { "id": "slot_open",       "ok": true, "firstHitZ": 5.0, "expectedZ": 5.0 },  // ok = |firstHitZ - expectedZ| <= 0.05
    { "id": "min_rib",         "ok": true, "minMm": 2.4 },       // 阈值 2.0，见 §7.6
    { "id": "tools_in_board",  "ok": true },                     // 见 §7.6 第 9 条
    { "id": "depth_fits",      "ok": true, "maxEmbed": 10.0 }   // 谓词见 §7.6 第 1 条
  ]
}
```

- **阻断 / 不阻断的分工写死**：`shapely_valid`、`watertight`、`winding`、`manifold_status`、`tools_in_board`、`slot_open` 为 **blocking**（false → `success:false`，`error.code=GEOMETRY_INVALID` 或 `TOOL_OUT_OF_BOARD`，`detail.failedChecks`）；`genus`、`volume_match`、`min_rib`、`depth_fits` 为 **advisory**（false → `warnings[]`，仍出 STL）。
- `min_rib` 的阈值是 **2.0mm**（不是 2.4），与 §7.6 第 6 条一致；示例里写的 `minMm: 2.4` 是**实测值**，`ok = minMm >= 2.0`。
- `genus` 的谓词：`ok = (value == expected)`，`expected = len(tools) * (孔数)` 由 `interior` 数组长度推出；`volume_match` 的谓词：`ok = errorPct <= 2.0`。
- `depth_fits` 的**谓词**（判**请求值**，不是 clamp 后的值——先 clamp 再断言同一不等式会让这条恒真）：
  ```python
  max_embed = board_top_z(board) - 2 if board.shape == 'rect' else board.heightU * GRHU - GR_BASE_HEIGHT - 2
  ok = (requested_embed <= max_embed + 1e-9)
  ```
  回传 `{ok, requested, clampedTo: min(requested, max_embed), maxEmbed}`，`maxEmbed` 供前端滑块直接用。advisory：`ok=false` 表示后端已 clamp。
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

- **6 种形状**：`scoop`（斜坡，`depth < 20` 时唯一可用；**几何必须先按 §7.4 落地再开放 UI**——它是开箱默认路径，缺实现等于默认路径不可用）、sphere（球缺）、cylinder（圆柱）、square、rect、filleted_rect。**形状选择器按生效 `depth` 过滤**（`depth < FINGER_REACH_MM(20)` 时**只给 `scoop`**——「scoop 系」只有 `scoop` 一个成员，不存在第二形态；判据见 §7.4，**不是按板厚**）。归属写死：`scoop` 只在 `< 20` 桶；`sphere`/`cylinder`/`square`/`rect`/`filleted_rect` 只在 `>= 20` 桶（其中 `sphere` 仅 `blind`，见 §7.4）。
- 拖拽平移、旋转手柄（仅非圆形）、宽高/半径数值框、深度模式切换（blind/through）。
- 默认值：`radius=15`、`width=30 height=20`、`depthMode='blind'`、**`depth = clamp(board.embedDepth + 8, board.embedDepth, top_z - 1)`**（下界 `embedDepth`、上界 `top_z − 1`，两头都得有；原式 `min(embedDepth+8, thickness)` 在 25 板 + embed 20 时得 25 = `top_z`，孔底正好落在板底、等价打穿）。**clamp 只对 `blind` 有效**；`through` 时 `depth` 被忽略、切刀下界取 −1。
- **自动放置**：调用 `/api/finger-holes/auto`，沿工具外轮廓的 PCA 主轴找**与槽壁距离最近的两端**，各放一个手孔；用户可删。**必须重写**现有 `_auto_detect_finger_slots`（`cad_engine.py:407`）——它现在只会生成水平胶囊、且直接吃像素坐标，换成竖直孔/scoop 后会静默失效。

### 6.5 板尺寸控件（`ParamsPanel.tsx`，v1.3 新增）

板尺寸是**独立自由度**——用户 m02193：「A4 纸只是用来作为参考来识别工具大小的……实际板子上能放几个，是根据我想打印多大的板子决定的」。

```
板尺寸  ( ) 刚好装下工具   ( ) 自定义尺寸   ( ) 铺满打印床
        ├─ margin:   [2..30] 默认 12（custom / print-bed 下置灰并注明"仅『刚好装下』生效"；下界 2 是为保证 > clearance+0.5，避免默认配置必被板内校验阻断）
        ├─ 自定义:   宽 [60..400] mm   高 [60..400] mm   ← 输入框，不是滑块
        └─ 铺满床:   只读显示 "{printBed.x−2·edge} × {printBed.y−2·edge}（可打印区域，edge=5；gridfinity 另显示取整后的 units×42）"
外形    ( ) 矩形    ( ) Gridfinity
        └─ Gridfinity 时: 格数 X/Y（起始值按 sizeMode 推出，可改）
```

规则：
- 切到 `'custom'` 时**用当前算出来的板尺寸预填**输入框（用户多半只想微调），不填 0。
- **离开 `'custom'` 时必须把 `widthMm`/`heightMm` 置 `null`**（不是清成 0）。否则用户切到 custom 再切回 fit-tools，两个字段留在 store 里，下一次 `/api/generate` 必然 400 `INVALID_SIZE_MODE`——"切了个单选框就再也生成不出来"。
- Gridfinity 外形下，自定义宽高输入框旁边**实时显示实际板尺寸**（"126 × 126（3 格）"），因为 `ceil(w/42)*42` 不等于用户填的值。
- 工具超出板框时，边界高亮 + 底部提示「有 N 个工具超出板框」，并把「生成」按钮置灰；**不自动放大板**。
- 板尺寸与工具位置**互不联动**：改板尺寸不挪工具，挪工具不改板尺寸（除 `'fit-tools'` 模式下板随并集变化）。
- 参数面板底部常驻一行只读摘要：`板 240 × 180 mm · 12 厚 · 3 把工具`。

---

## §7 几何流水线（后端）

### 7.1 模块划分

```
python_backend/
  main.py                     # 仅路由与信封；旧路由在 GEO_ENGINE=legacy 时保留，=new 时逐步切走
  api/schemas.py              # Pydantic 请求/响应模型
  api/errors.py               # 错误码枚举 + 异常类
  domain/models.py            # §3.2（**不要放 `models/`**：`python_backend/models.py` 已存在且 `cad_engine.py:59` 是裸 `from models import`，新建同名包会让旧引擎在 M0 期间直接 ImportError）
  imaging/warp.py             # 纸角检测 + 透视 + 10px/mm（不做去畸变）
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
1. **先按 `sizeMode` 定板尺寸，再决定工具哪些进这块板**（板尺寸是独立自由度，不由工具数量推导——用户 m02193）：

   | `sizeMode` | 板宽 × 板高 | 说明 |
   |---|---|---|
   | `'fit-tools'`（默认） | 所选工具的并集 bbox 各边 + `margin` | 全选时就是"刚好装下" |
   | `'custom'` | 用户填的 `widthMm` × `heightMm`（`60..400`） | 可小到 60×40 只放一把螺丝刀，也可大到 400×300 之后按 D14' 分块 |
   | `'print-bed'` | `printBed.x − 2*edge` × `printBed.y − 2*edge`（`edge = 5` → 220 床得 **210×210**） | 铺满**可打印区域**。**不要用整张床**：整张床会立刻触发 §8.1 的分块（`220 > 220−10` 恒真），用户点"铺满床"反而得到 4 片 110×110 |

   板大于工具并集时**一律允许留白**：**不重排、不平移任何工具坐标、不"拉伸填满"**。留白以**未隐藏工具的并集 bbox 中心**为中心向四周均分（见 §2.3 的板框锚点；这不叫"自动居中"）。工具坐标保持纸面毫米原样，板框只决定外形与底座。
   **`'fit-tools'` 的"并集"= `hidden == false` 的全部工具**（不含隐藏项）；`tools_in_board` 也只校验 `hidden == false` 的工具。隐藏一把工具后板会随之缩小，这是预期行为。
2. `_rounded_box(w, h, thickness, cornerR, edgeRoundover)`：`CrossSection` 矩形 → `offset(- cornerR)` → `offset(+ cornerR, JoinType.Round)` → `extrude(thickness)`。
   **▸ "倒角"拆三个独立参数，字段名以 §3.1 的 camelCase 为准**（v1.0 草案里 `fillet`/`corner_r`/`slot_chamfer` 三名混用，已删除旧名）：

   | 字段（代码内） | TS 字段 | 作用面 | 几何 | 默认 |
   |---|---|---|---|---|
   | `corner_r` | `cornerR` | 板在 XY 平面的四角 R | 上面的两次 offset | **5mm**（原写 6，统一为 5） |
   | `edge_roundover` | `baseEdgeRoundover` | 板**顶面**沿外框一周的圆角 | `board_solid ∩ (顶面外圈的倒圆扫掠)`,用一个沿外框路径扫掠的 `Manifold`；**v1 允许降级为 `board_solid ∩ 半圆柱沿四条边`** | 0（关） |
   | `slot_chamfer` | `slotChamfer` | 槽口插入导向 | §7.3 第 7 步的锥台 | **1.5mm** |
3. 返回的 `Rect` 用于 §7.6 的边界校验与 §8 的分块。

**gridfinity**：
1. `unitsX/unitsY` **起始值由后端派生**（`geometry/board.py` 的 `derive_units(size_mode, bbox, margin, width_mm, height_mm, print_bed)`，clamp 到 `1..40`；**前端只回显，不自己算**），三条 X、三条 Y **一一对应**：
   | `sizeMode` | `unitsX` | `unitsY` |
   |---|---|---|
   | `'fit-tools'` | `ceil((bboxW + 2*margin) / 42)` | `ceil((bboxH + 2*margin) / 42)` |
   | `'custom'` | `ceil(widthMm / 42)` | `ceil(heightMm / 42)` |
   | `'print-bed'` | `floor((printBed.x − 2·edge) / 42)` | `floor((printBed.y − 2·edge) / 42)` |
   **最小 1**，用户随时在参数面板手动改（改小到装不下工具时被 §7.6 第 9 条阻断并提示，不静默裁掉工具）。
   **▸ `'custom'` 在 gridfinity 下是"目标下限"不是"精确尺寸"**：`widthMm` 经 `ceil` 取整到 42 的倍数，填 100 得到 **126**（3 格）、填 400 会得到 **420**（10 格，**超过声明的 400 上界**）。因此参数面板必须**实时回显实际尺寸**（"126 × 126（3 格）"），且 `paramsEcho` 回传的 `boardMm` 取实际值。
   **▸ 板尺寸的真源只有一处**：`board_size_mm()` 在 gridfinity 下**必须**返回 `(units_x * 42, units_y * 42)`，**不得**返回 `widthMm`/`printBed`；`build_board` 返回的 `Rect` 恒为最终实体 bbox。否则 §8.1 用尺寸 A 判分块、实际实体是尺寸 B，切缝数与位置都会错。
2. **外形尺寸 = `unitsX * 42` × `unitsY * 42`**（顶面净尺寸）。`GRU_CUT = 42.2` 不改变外形，只用于底座切槽的内部尺寸——**不要自己推导，直接读 `constants/gridfinity.py` 的剖面元组**。
3. **▸ 高度 = `heightU * 7`**（`GRHU=7`，含底座）。3U 必须 = **21mm**。现有的 `height_u*7.0 + 5.0`（`models.py:105`）让 3U = 26mm，比标准高 5mm，**摞不上**；也不要写成 `heightU*7 + 4.75`（= 25.75，同样错）。
   深度 clamp 因此分外形（§3.1 里 `embedDepth` 的「强制 <= thickness-2」**只对矩形板生效**）：矩形 `embed ≤ thickness − 2`；Gridfinity `embed ≤ heightU*7 − 4.75 − 2`，且**槽不得进入堆叠唇区域**。**唇的两个尺寸不要混用**：`LIP_HEIGHT = 8.2mm` 是**垂直**高度；唇在顶面外圈占的**径向**宽度是独立常量 `LIP_WIDTH = 2.6mm`，**由唇剖面各段水平投影之和算出**（`sum(seg.h*|abs(sin a)| + seg.run)`，不是把两个垂直段高 `LIP_D0 + LIP_D2` 相加——那是量纲错），并加断言 `abs(LIP_WIDTH − 2.6) ≤ 0.05`。下文凡「离顶面外沿 X mm 内禁切」一律用 `LIP_WIDTH`，**不要拿 8.2 当带宽**（那是量纲错）。
   **断言**：`build_board(...).bounding_box()[5] == heightU * 7 ± 0.01`（`[5]` = maxZ；3U → 21mm）。
4. 底座剖面：按 `GR_BASE_PROFILE` 三段（第一段上倒角、中间 1.8mm 直壁、第三段下倒角），**每段单独 `extrude(scale_top=...)` 后 union**。段高之和必须等于 `GR_BASE_HEIGHT = 4.75`，跑一条断言卡住它。
5. 堆叠唇：按 `GR_LIP_PROFILE` 五段，做在顶面外圈。
6. 磁吸孔：每格四角，**孔心相对格心 ±13mm**，φ6.5 × 2.4 深，从底面往上打。

### 7.3 槽切刀（M1 核心）

```python
def build_pocket_cutter(
    tool: Tool, board: BoardConfig, board_center: Vec2,
    depth: float | None = None,        # None → 用 board.embedDepth
) -> Manifold:
```

**局部量的绑定规则（全篇唯一，不许在函数体里再散写）**：

```python
top_z     = board_top_z(board)                                        # 唯一 z 基准
depth     = tool.depthOverride    if tool.depthOverride    is not None else board.embedDepth
clearance = tool.clearanceOverride if tool.clearanceOverride is not None else board.clearance
chamfer   = tool.chamferOverride  if tool.chamferOverride  is not None else board.slotChamfer
```

下文第 7/8 步的 `depth` / `clearance` / `chamfer` / `top_z` 一律指这四个局部量（**它们不是函数形参以外的自由变量**：形参只留 `tool, board, board_center`，其余全部按上式从 `board`/`tool` 派生）。**同一参数只允许两个名字**：TS/PY 字段 `xxxOverride`、内部局部量 `xxx`；**禁止**再出现 `embedded_depth`。
**`depthOverride` 的 clamp（原来完全没有，手孔可穿透板底）**：`depthOverride = min(depthOverride, top_z - 2)`，越界写 warning `DEPTH_EXCEEDS_THICKNESS`。

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
   cutter_cyl = Manifold.extrude(cs0, depth + 1).translate((cx, cy, top_z - depth))
   - z 范围: [top_z - depth, top_z + 1]     ← 必须刺出顶面 1mm（F1 修正）
8. 倒角锥台（仅当 chamfer > 0）——顶面外扩，宽度比 > 1:
   eff   = min(chamfer, max(0, depth - 1))
   cs_o  = cs0.offset(eff, JoinType.Round)          # 外扩一个 eff
   bi, bo = cs0.bounds(), cs_o.bounds()
   sxy   = ((bo[1][0]-bo[0][0]) / (bi[1][0]-bi[0][0]),
            (bo[1][1]-bo[0][1]) / (bi[1][1]-bi[0][1]))   # 两者都 > 1
   cutter_chamfer = Manifold.extrude(cs0, eff + 0.01, scale_top=sxy) \
                          .translate((cx, cy, top_z - eff))
   # v1 限制：manifold3d 没有 loft，`scale_top` 只能按 bbox 比例仿射 → 凹角/内壁的倒角宽会衰减。
   # 这是已知的、可接受的 v1 取舍（真 offset 变截面要逐段 extrude，留 v2）。
   # 但必须写告警：cs_ref = cs0.offset(eff, mf.JoinType.Miter)
   #   if abs(cs_ref.area() - (cs0.area() * sxy[0] * sxy[1])) > 0.15 * cs_ref.area():
   #       warnings.append({'code': 'CHAMFER_NARROW_AT_CONCAVE', 'message': '凹角处倒角偏窄', 'detail': {...}})
9. return cutter_cyl + cutter_chamfer
```

**关键数值**：
- 切刀 z 上界 = `top_z + 1.0`（保证开口）；下界 = `top_z - depth`。
- **▸ 锥台的 z 区间是 `[top_z − eff, top_z]`**（第 8 步的 `translate(..., top_z - eff)` + 高度 `eff + 0.01` 正好如此）：**底面与槽底方向一致、顶面与板顶面齐平再向上溢出 0.01 保布尔稳定**；宽度从下往上变大（`scale_top > 1`），形成喇叭口导向。
  两个反例都会**静默失败**：(a) 把锥台放在 `z ∈ [thickness, thickness + eff]` → 整个锥面悬在板顶上方 1mm 的空气里，槽口仍是直角，而"剖面能看到锥面"的 DoD 照样通过；(b) 沿用 tracefinity 的 `wall_top_z − eff_chamfer` 却把板改成 ±H/2 居中 → 同 (a)；(c) 用 `thickness` 代替 `top_z` → 整个切刀连槽带锥一起下移（gridfinity 上必现）。**因此 z 基准必须只有一处定义（§2.3 的 `top_z`），且此处断言 `cutter_chamfer.bounding_box()[5] ≈ top_z + 0.01`（`[5]` = maxZ）。**
- 切刀的 `CrossSection` **必须平移到原点再 extrude**（`scale_top` 绕原点缩放）。
- 内孔：见上第 6 步（`FillRule.EvenOdd`，面积 <= 0 时整组反向重试一次）。

### 7.4 手孔切刀

```python
def build_finger_hole_cutter(hole: FingerHole, board: BoardConfig, board_center: Vec2) -> Manifold
```

**常量（`geometry/constants.py`，全项目唯一真源）**：`FINGER_REACH_MM = 20.0`（指腹可达深度）、`GRHU = 7.0`、`GR_BASE_HEIGHT = 4.75`、`LIP_D0 = 1.9`、`LIP_D1 = 1.8`、`LIP_D2 = 0.7`、`LIP_D3 = 1.2`、`LIP_D4 = LIP_D0 + LIP_D2`、`LIP_HEIGHT = 8.2`（五段之和，**垂直**量）。**`LIP_WIDTH` 是径向量、不能由垂直段高相加得出**：它 = 唇剖面**各段水平投影之和**，按 `GR_LIP_PROFILE` 元组逐段算：`LIP_WIDTH = sum(seg.height * abs(sin(seg.angle)) + seg.run for seg in GR_LIP_PROFILE)`，实算 **2.6mm**，并加一条断言 `abs(LIP_WIDTH - 2.6) <= 0.05` 卡住它（剖面改了就报警）。凡「离顶面外沿 X mm 内禁切」一律用 `LIP_WIDTH`，**不要拿 8.2 当带宽**。`top_z` 只由 `board_top_z(board)` 一处给出。

| shape | 几何 | z 范围 |
|---|---|---|
| `scoop` | **斜坡楔块**：在槽壁开口处切一块三棱柱，坡顶在 `top_z`、坡底 = 槽底 `top_z − depth`，竖直落差 = 生效 `depth`，水平进深 `run = depth / tan(scoopAngleDeg)`，`scoopWidth` 是**沿槽壁方向的坡宽**（不参与进深），`scoopDir` 由编辑器的旋转手柄给出。**三条边界见本节末** | 底面 `top_z − depth`（= 槽底），顶面 `top_z + 0.01` |
| `sphere` | **球缺**：`r = min(radius, depth, top_z - 1)`，`centerZ = top_z - depth + r`，球体与 `z >= 0` 求交。**开口守卫（原缺，会重演 F1 的密闭内腔）**：`assert centerZ + r > top_z + 0.1`——`radius < depth/2` 时珠顶会掉到板顶以下，生成完全封闭的空腔，水密+体积+`slot_open` 全绿而手根本伸不进去。**`sphere` 只允许 `blind`**（`through` 时球底恒 ≥ 1、满足不了 `≤ −0.5`，会必红） | 从顶面下探到 `top_z - depth`，**不得穿透板底**：断言 `abs(bounding_box()[2] − (top_z − depth)) <= 0.01`（**原来的 `>= 0` 恒真**：球底 = `centerZ − r = top_z − depth`，而 `depth ≤ top_z` 必然成立，等于没查） |
| `cylinder` | `Manifold.cylinder(r, h)` | `[top_z - depth, top_z + 1]` |
| `square`/`rect` | `Manifold.cube([w, h, depth+1])` 绕 Z 旋转 | 同上 |
| `filleted_rect` | X/Z 剖面扫掠（圆底角半径 = `min(w/3, depth/2)`） | 同上（`blind`；`through` 时下界 −1） |

- **`scoop` 的三条边界条件**（缺一条就有一半默认请求被拒、或断言恒假）：
  1. **`run <= d_edge − clearance`**，其中 `d_edge` = 坡道方向上**槽壁到板轮廓的实测距离**（`shapely.distance(pocket_ring, board_section.boundary)`），**不是 `margin`**。`margin` 只在 `'fit-tools'` 下近似等于 `d_edge`；`'custom'` / `'print-bed'` 下工具可能贴板边，此时 `margin` 与真实余量无关，用它会算出错误上界、坡道直接从板侧切穿（而 `tools_in_board` 只查"在板内"、不查"距边 ≥ margin"，会放过这种情况）。
   超出时 clamp 角度使等号成立，写 warning `SCOOP_CLAMPED`。**`d_edge < clearance + 1.0` 时无解** → 阻断 `GEOMETRY_INVALID`，`error.detail` 提示"增大板尺寸或把该工具离板边远一些"。
  2. **楔块必须向槽内侵入 ≥ 0.5mm**：坡道沿 `scoopDir` 的起切点从槽壁面**向内**移 0.5mm。否则楔块与槽切刀只共一个面、交集体积恒为 0，下面的连通性断言对**正确实现恒假**。
  3. **`scoop` 不参与 `depthMode`**：坡底恒为槽底 `top_z − depth`；`through` 只对 `cylinder`/`square`/`rect`/`filleted_rect` 生效。
  4. 坡底用的是**生效 `depth`**（`depthOverride ?? embedDepth`），**不是 `board.embedDepth`**——否则 `depthOverride` 非空时「坡底 = 槽底」不成立。
- `depthMode == 'through'` → 切刀下界取 `-1`（贯穿）。**只对 `cylinder` / `square` / `rect` / `filleted_rect` 生效**；`scoop` 与 `sphere` 不支持 `through`（前者坡底恒为槽底，后者球底恒 ≥ 1），UI 在选这两个形态时禁用该开关。
- `chamfer > 0` → 与槽倒角同样的 `offset + scale_top` 锥台，加在顶面。`chamfer` 的绑定式：`chamfer = hole.chamfer if hole.chamfer is not None else board.fingerHoleChamfer`（`fingerHoleChamfer` 默认 0.5，见 §3）。
- **手孔坐标同样要用 `to_board_frame`**（这是现有代码最严重的错位 bug）。**`rotation` 必须取负**：`to_board_frame` 的 y 取负是镜像，镜像下「逆时针」变「顺时针」；`filleted_rect` 的圆角位置与 `scoopDir` 的朝向都会反，而 0.6 的 L 形 fixture 抓不到（它只查外轮廓）。

**▸ 审核修订（D①/D②，v1.3）：判据是生效 `depth`（= `depthOverride ?? embedDepth`），与板厚无关；scoop 的几何在此定义；三条断言的量纲已修正：**

| 判据（连续，两种外形共用） | 手孔形态 | 理由 | 机检断言 |
|---|---|---|---|
| **`depth < FINGER_REACH_MM(20)`**（矩形 6/12 板 `≤ 4/10`；gridfinity **3U 只有 14.25**——4U 的 21.25 已 ≥ 20，落在下一行） | `scoop` 斜坡（几何见上表 `scoop` 行）：落差 = **生效 `depth`**，坡底 = **槽底** `z = top_z − depth` | 手指要够到工具**底面**才能捏住侧壁；生效 `depth`（= `depthOverride ?? embedDepth`）就是板顶到槽底的距离，不够 20mm 时竖直孔伸到底也够不到 | ① `abs(scoop.bounding_box()[2] − (top_z − depth)) ≤ 0.01`（**用生效 `depth`，不是 `embedDepth`**——`depthOverride` 非空时两者不同，坡底会对不上槽底）；② **连通性用 3D 求交**：`(scoop_cutter ^ pocket_cutter).volume() > 0.1`（两者都是 `Manifold`；**不能写 `CrossSection` 求交——2D/3D 不可交，若按 XY 投影解释则正确几何恒为 0，断言恒假**） |
| **`depth ≥ FINGER_REACH_MM(20)`**（矩形 25 板可选；gridfinity **4U 21.25 / 6U 35.25** 都 ≥ 20——不是「必须 6U」） | `cylinder` / `sphere` 竖直孔 | 板够厚，指尖能下探到工具底面以下 | **按 `depthMode` 分两条**：`blind` → `abs(hole.bounding_box()[2] − (top_z − depth)) ≤ 0.01`；`through` → `hole.bounding_box()[2] ≤ −0.5`。**原式「≤ 0.1 = 真的贯穿」是自毁的**：合法 blind 孔孔底在 `top_z − depth > 0`，按原式必红、只有打穿才绿 |
| **Gridfinity** | **不单独判档**：`depth` 的 clamp 上界是 `heightU*7 − 4.75 − 2`（3U 14.25 / 4U 21.25 / 6U 35.25），直接用这个 `depth` 套同一判据 | 判据与外形无关；3U 得 **14.25** < 20 → scoop；4U 得 21.25 ≥ 20 → 可选竖直孔；6U 得 **35.25** ≥ 20 → 可选竖直孔 | 同上两条 |

- **禁止**在 `depth < FINGER_REACH_MM` 时提供竖直孔选项；UI 的形状选择器按 **`depth`（= `depthOverride ?? embedDepth`）** 过滤（**不是按板厚，也不是按原始 `embedDepth`**——`depthOverride` 可以把 8mm 的板挖成 22mm 深，那时判据必须跟着 `depthOverride` 走）。判据是连续的、矩形与 Gridfinity 共用同一套，因此**不存在任何空档**——v1.1 按板厚分档时 Gridfinity 3U 的「等效厚度 16.25」落进 12–25 之间，是真实存在的 bug（第三轮审核 P0-1）；v1.2 虽已改判据，但几何仍按 `thickness − depth` 写、gridfinity 上整体错位 9mm（第四轮审核 N1/P0）。**v1.3 起判据与几何统一用 `embedDepth` + `top_z`。**
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

1. **分外形判上界**（统一用 `top_z - 2` 是错的：3U 板会得 19，槽底切到 z=2、插进 4.75 高的锥台底座，削穿台阶）：rect `embedDepth > thickness - 2`、gridfinity `embedDepth > heightU*7 - GR_BASE_HEIGHT - 2` → `DEPTH_EXCEEDS_THICKNESS`（自动 clamp 到该上界并 warning，**不阻断**）。`depthOverride` 走同一 clamp。该码虽然出现在 §4.0 的错误枚举里，但**只用于 warning、永不置 `success:false`**——枚举与严重度是两个维度。
2. 任一工具 bbox 超出纸面 3mm → `TOOL_OUT_OF_PAPER`（阻断）。
3. 工具之间槽重叠（间隙后仍相交）→ warning「工具 A 与 B 的槽重叠，生成后会连成一片」，不阻断。
4. 单工具最长边 > `min(printBed.x, printBed.y) - 2*edge`（`edge = 5`，即 220 床 → **210**）→ `TOOL_TOO_LONG`（阻断，见 §8.4）。**余量用 `edge`，不是 `margin`**——这条判的是「能不能打印」，与「板边到工具留多少」是两个量；用 `margin` 会让 `margin` 从 8 调到 12 时最大可做长度从 204 悄悄降到 196（一把 200mm 扳手突然做不了，用户却只改了个边距滑块）。**这条与 `sizeMode` 无关。**
5. 板 bbox 超过 `printBed` 且 `splitEnabled == false` → warning「板超出打印尺寸，请开分块」。
6. **▸ 审核修订（D10'）最小筋厚**：相邻两个槽（含间隙后）、槽与板边、槽与手孔之间的最近距离 < 2.0mm → warning「此处筋厚 X mm，打印后易断」。这个值用真实几何量：`min(shapely.distance)` 或 `Manifold.min_gap(other, search_length=5.0)`，**不要用 bbox 估算**。
7. **▸ 审核修订（D8'/B⑥）Gridfinity 专属 clamp**：板为 gridfinity 时，`embed > heightU*7 − 4.75 − 2` → 直接 clamp 到该值并 warning；若某槽的 bbox 进入堆叠唇区域（顶面外圈**径向** `LIP_WIDTH = 2.6mm` 带；**不是 8.2**——那是垂直唇高）→ 阻断 `GEOMETRY_INVALID`。
8. **▸ 静默失败收口**：`precheck` 之外，生成阶段的每个 `except` 都必须把异常写进 `issues[]` 并把 `success` 置 false。**禁止 `except: print(...)`**。旧 `cad_engine.py` 已冻结，只允许在其 `except` 分支追加一行计数。
9. **▸ 第二轮审核新增：`tools_in_board`（阻断）**。取板顶下方 0.01mm 的截面多边形，断言每个槽（已加 clearance）与每个手孔轮廓**完全落在**截面多边形内；否则 `TOOL_OUT_OF_BOARD`。**没有这一条，gridfinity 格数改小或手孔拖到板外时，切刀切的是空气——水密、体积、checks 全绿，用户拿到一块没有任何槽的实心板。**
   同时 `tools_in_board` 不只查纸面，还查板内：`sizeMode='custom'` 或用户手动改小格数后，工具超出板框 → `TOOL_OUT_OF_BOARD`（阻断）。**不自动 clamp 格数**——自动变大等于用户自定义的尺寸被悄悄推翻。
   **出路必须按模式给（`error.detail`）**，否则给了用户照做也没用：
   - `'fit-tools'` → "缩小 `margin` / 把该工具移出本板 / 改用 `'custom'` 并调大宽高"
   - `'custom'` → "调大 `widthMm`/`heightMm` / 把该工具移出本板 / 改用 `'fit-tools'`"（**不要给"缩小 margin"**——该模式下 `margin` 不参与板尺寸，用户照做仍然失败）
   - `'print-bed'` → "把该工具移出本板 / 改用 `'custom'` 并调大宽高 / 开启分块（§8）"
   另加一条 **warning（不阻断）** `BOARD_EDGE_TIGHT`：工具外接框距板边 < `margin` 时提示「边缘畸变可能使本工具顶出板框，建议至少留 12mm 或改用『刚好装下』」——`'custom'` 下用户可以把工具贴到板边，这条是"留白吃掉畸变"策略的兜底提示。
10. **▸ 出错出路**：上述任一阻断触发时，`error.detail` 必须带可执行的三个出路（例：`TOOL_OUT_OF_BOARD` → "调大板宽/格数 / 缩小 margin / 把该工具移出本板"），不准只给一个错误码。

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
top_z     = THICKNESS_TEST                                        # 合成件：rect 板 → top_z = thickness
clearance = 0.0                                                   # **必须显式置 0**：§3.1 默认 0.4，槽长会变 100.8、下面第③条必红
# bounding_box() 返回扁平 6 元组 (minx,miny,minz,maxx,maxy,maxz)；[5] = maxZ
assert cutter.bounding_box()[5] > top_z + 0.9                       # ① 切刀确实刺出顶面
# trimesh raycast 参数名是 ray_origins / ray_directions（不是 origin/direction）
# 返回的 loc 不按距离排序，首击高度取 z 最大者（= 槽底，不是板底）
loc, _, _ = mesh.ray.intersects_location(
    ray_origins=[[0.0, 0.0, top_z + 10.0]],
    ray_directions=[[0.0, 0.0, -1.0]])
assert len(loc) > 0
first_hit = max(float(p[2]) for p in loc)
assert abs(first_hit - (top_z - depth)) < 0.05                     # ② 首击在槽底，不在顶面（射线要落在槽内部，不能落在角顶点）
assert abs(pocket_length_mm - 100.0) < 0.1                          # ③ 尺寸对（§10.3：±0.1，不是 ±1）
```

**⚠️ API 事实（manifold3d 3.5.4 / trimesh 5.2.0 实测）**：`Manifold.bounding_box()` 是**扁平 6 元组**，`[1][2]` 会 `TypeError`；`CrossSection.bounds()` 是扁平 4 元组；`intersects_location` 用 `ray_origins`/`ray_directions` 关键字，且 `loc` **不按距离排序**（实测 `loc[0]` 可能是板底 `z=0`、`loc[1]` 才是槽底 `z=top_z−depth`），故必须 `max(p[2])`。`rtree` 是 `trimesh.ray` 的隐式依赖（见 §11.2），缺了报 `ModuleNotFoundError: No module named 'rtree'`。

② 是 F1 的**唯一**可靠证据：密闭空腔的首击会落在 `z = top_z`（rect 时 = `thickness`）。没有这条断言，`success + volume>0` 会把错误固定下来。

**⚠️ 实测补充（2026-11-05，板 `160×80×12` / 槽 `100×20`）**：

- **射线必须打盲槽，不能打贯穿槽**。盲槽切刀 `z ∈ [6,13]` → `loc` 有 2 个命中 `[0.0, 6.0]`，`max = 6.0 = top_z − embed` ✅；贯穿切刀 `z ∈ [-4,12]` → `loc = []` 空（射线从孔里穿过去）。**射线打空的第一排查项不是库，而是「槽是不是被切成通孔了」**，同时看 `bb[5] − top_z` 是否 > 0.9。
- `loc` **不按距离排序**（实测板底 `0.0` 排在槽底 `6.0` 前面），必须 `max(p[2] for p in loc)`，不能 `loc[0][2]`。
- **「顶面在槽投影区域是空的」用截面环数判，不用射线**：在 `z = top_z − 0.01` 处 `mesh.section(plane_normal=[0,0,1], plane_origin=[0,0,z])` → `to_2D()` → 数**中心落在槽投影多边形内部**的闭环数。盲槽 = **1 个内环** ✅；不切 = **0 个内环** ✅。注意 `p2d.bounds` 恒为板外接框（`[-80,-40]..[80,40]`），**不能用 bounds 判开口**，必须逐环取 `Polygon(pts).centroid`。
- `trimesh` 5.2.0 **没有** `section_plane`（`hasattr == False`），只有 `section(plane_normal=, plane_origin=)`。

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
| 唇各段高度 / 总和 | ±0.01 / ±0.05（**总和容差 ≥ 5×段容差**，否则五段各偏 0.05 累到 ±0.25，无 bug 也会红） | 计划 1.4b |
| 分块两片 bounds 之和 vs 原板 | ±0.01mm | 计划 3.2 |
| DXF 读回面积 / 非对称点 | ±0.1mm² / ±0.01mm | 计划 3.4 |

**规则：新增 DoD 前先查这张表；同一个量只允许一个容差。**（v1.0 草案里 0.5 与 1.0、±0.05mm² 与 ±2×clearance 互斥，已在此收敛。）

## §11 目录与构建

### 11.1 新增目录

```
python_backend/
  api/ domain/ imaging/ geometry/ export/ constants/ tests/
src/
  types/ store/ geometry/ components/editor/
docs/planning/
  v1-plan-v1.3.md   v1-sds-v1.3.md
```

### 11.2 `requirements.txt`（必须写全）

**▸ 审核修订（R1）先写清目标环境**：WSL Ubuntu 26.04 自带 **Python 3.14.4**，没有 `pip`、没有 `gcc/make`。因此：

1. **不能用现有 pin**：`numpy==1.24.3` 没有 cp314 wheel（必源码编译）、`cadquery==2.8.0` 没有 cp314 wheel、`scipy` 在本项目**无调用点**。
2. **删 `cadquery`**：它只被 `cad_engine.py:803` 懒加载，服务的是已砍掉的 `/generate-step`。
3. **必须 venv**（Ubuntu 走 PEP 668）。**✅ 2026-11-03 已验证可用**：先 `sudo apt install -y python3.14-venv python3-pip`（原先失败只因这两个包没装），然后
   ```bash
   python3 -m venv .venv          # 不要用 sudo 建，否则 venv 归 root
   . .venv/bin/activate
   pip install -r python_backend/requirements.txt
   python -c "import numpy,shapely,manifold3d,trimesh,cv2,skimage,ezdxf,rtree"   # 必须全绿再开 M-1
   ```
   实测已通过：`python3 -m venv /tmp/tv2` OK（Python 3.14.4）、`pip install numpy` OK（2.5.4）。依赖齐全后先跑 `python -c "import numpy,shapely,manifold3d,trimesh,cv2,skimage,ezdxf,rtree"`（**`rtree` 已实测为必需**：`trimesh.ray.intersects_location` 依赖它，缺了直接 `ModuleNotFoundError`；已装 1.4.1），**任何 ImportError 都必须在 M-1 之前解决**（3.14 的 wheel 覆盖度是主要风险；`opencv-python-headless` 必须用 headless 版，否则 `main.py:4` 的顶层 `import cv2` 会因缺 `libGL.so.1` 直接崩）。
   **两个坑**：① `curl https://pypi.org/simple/` 会超时（IPv6 优先/探测受限），但 **`pip` 能正常下载**——别拿 curl 当出网判据；② 从 Windows 侧 `wsl -d Ubuntu <cmd>` 调用时若 cwd 在 `/mnt/d/...` 会打印 `chdir(...) failed 5`，无害，先 `cd ~` 可消除。
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
rtree>=1.2                    # trimesh.ray 的隐式依赖；缺了 intersects_location 报 ModuleNotFoundError
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
| **M-1a**（0.5d，前置） | 建环境并验通（`python3 -m venv .venv` + `pip install -r` + `import numpy,shapely,manifold3d,trimesh,cv2,skimage,ezdxf` 全绿） | 0 个（主会话自己做） |
| **M-1**（0.5d） | 定冒烟脚本的三条断言 | 1 个：`scripts/smoke_geometry.py`（**不含建环境**） |
| **M0**（2.5d） | 写 §2 的断言、跑通环境、验收 | **分三批，不是全并行（有阻塞边）**：**批 1（无依赖，先开）** `0.1` 环境与 requirements ｜ `0.2`+`0.7`+`0.8` z 基准与校验库；**批 2（依赖批 1，内部串行）** `0.4`（warp 固定 10px/mm）→ `0.3`+`0.3b`（删 scale、毫米链）→ `0.5`（照片体检）→ `0.6`（golden）。**`0.3` 既不能与 `0.4` 并行**（没有 10px/mm 校正图就没有毫米坐标可删），**也不能排在 `0.6` 之后**——0.6 的 DoD「槽尺寸误差 ≤0.5mm」正是 0.3 的验收，排在批 2 末尾即按此序执行。 |
| **M1**（3.5d） | 定切刀参数、验收 STL | **3 个并行**：`1.0b`+`1.4a/b/c` 参数与底座唇磁孔 ｜ `1.1`+`1.2` 槽切刀与间隙 ｜ `1.0`+`1.3`+`1.5`+`1.6` 多轮廓、内孔、手孔、矩形外壳 |
| **M2**（3.5d） | 定交互契约、验收 | **4 路，其中 2.5 与 2.3b 必须同一人（同文件 `ParamsPanel.tsx`）**：`2.1` PolygonEditor ｜ `2.2` ToolEditor ｜ `2.3a/b`+`2.4` 三参数联调与多工具前端 ｜ **`2.5` 板尺寸控件（0.5d，独立 4 条 DoD，不是"同文件即零成本"）** |
| **M3**（3.5d） | 定分块算法、验收 | **3 个并行**：`3.2` 分块 ｜ `3.4` DXF ｜ `3.1`+`3.3` 纸角手拖与试切件 |
| — | — | **并行说明**：`3.1`（纸角手拖）与 `3.4`（DXF）**只依赖数据模型**（§3），M1 一开工即可并行；`3.2`（分块）需要 `Manifold` 实体、`3.3`（试切件）需要真实 STL，**必须等 M1 的切刀能出实体之后**（第二轮审核指出 v1.0 把可并行的项全排在 M3，第四轮审核指出 v1.3 又把它俩误列为纯数据依赖）。 |
| **M4**（1.5d） | 全量回归、文档同步 | 1 个：`4.1`–`4.4` |

### 12.2 每个子 agent 的交付格式

1. 改动文件清单（绝对路径）
2. 每个文件的**关键行号 + 该行做什么**
3. 跑过的命令与输出（不许写"应该能跑"）
4. 未完成项与原因

### 12.3 审核 agent 的固定检查项

- 有没有出现 `840`、`1188`、`±H/2`、`H/2`、`localhost:8001`、**`bounding_box()[1][2]` / `bb[1][2]` 这类错误下标**（`Manifold.bounding_box()` 是扁平 6 元组，`[5]`=maxZ / `[2]`=minZ；`CrossSection.bounds()` 是扁平 4 元组）
- 有没有在 `geometry/` 里 import `cv2`
- 切刀出顶量 `bb[5] - top_z` 是否落在 `[0.9, 1.0]`（rect 时 `top_z = thickness`；**gridfinity 上写 `thickness` 就是错的**）
- 内孔是否走了 `FillRule.EvenOdd`
- 有没有 `except: print(...)`（禁止吞异常）
- 有没有未归一化的绕向直接送进 `CrossSection`
- 有没有在 `simplify` 之后才 `buffer(clearance)`（顺序反了会静默吃掉间隙）
- 有没有在 `depth < FINGER_REACH_MM` 时生成竖直手孔（判据是生效 `depth`，不是板厚、也不是原始 `embedDepth`）
- **`scoop` 是否有真几何**（不是只有枚举值）：坡底 = `top_z − depth`、`run = depth / tan(angle) ≤ margin − clearance`、楔块向槽内侵入 ≥ 0.5mm、与槽切刀 3D 求交体积 > 0.1
- 有没有竖直定位销孔（必须是水平、从切缝面钻入）
- 有没有对 gridfinity 板分块（v1 必须拒绝）
- `heightU*7` 还是 `heightU*7+5`（后者 3U=26，摞不上）
- 有没有把 `mmPerPx` 读进下游计算（只许回显）
- 有没有在移植代码里保留 `-(p[1] + offset_y)` 取负（入参已是 y-up，再取负 = 竖直镜像）
- `BoardConfig` 是否与 §3.1 的字段清单**逐一对应**（含 v1.3 新增的 `sizeMode` / `widthMm` / `heightMm`）；**残留旧名** `fillet` / `corner_r` / `base_chamfer` / `size_mode`（TS 侧）/ `distortionWarningMm` 任一出现即打回
- 手孔形态的判据**必须是生效 `depth`**（`depthOverride ?? embedDepth`）；凡出现 `thickness >=` / `thickness <` 作为形态判据一律打回（**手孔与板厚无关**），凡直接用裸 `embedDepth` 判据也对 `depthOverride` 不成立
- `sphere` 手孔是否断言 `abs(bbox[0][2] − (top_z − depth)) ≤ 0.01`（**`≥ 0` 恒真，等于没查**）
- `from_dict` 是否静默忽略未知字段（必须 400 `SCHEMA_UNKNOWN_FIELD`）
- 是否校验了"槽/手孔完全落在板轮廓内"（`tools_in_board`）
- **板尺寸是否被当成工具数量的函数**：`sizeMode='custom'` / `'print-bed'` 时板尺寸**必须**只由 `widthMm/heightMm` 或 `printBed` 决定，出现"按工具并集自动放大"一律打回（用户 m02193：板尺寸是独立自由度）
- **`sizeMode` 与宽高是否同进同退**：`'custom'` 缺 `widthMm`/`heightMm`、或非 `custom` 模式带了宽高 → 必须 400 `INVALID_SIZE_MODE`；静默忽略即打回
- **工具超框时是否自动改板**：必须阻断报 `TOOL_OUT_OF_BOARD` + 给三个出路提示，**不自动放大板、不自动 clamp 格数**
- **`margin` 默认是否为 12**（v1.3 由 8 提到 12，用来吃掉 2–4mm 边缘畸变）；出现默认 8 一律打回
- **有没有残留镜头畸变代码或告警**：`cv2.calibrateCamera`、ArUco、`distortionWarningMm`、`DISTORTION_WARNING` 全部已砍，出现即打回。（**注意**：`标定` 一词仅允许指 §2.1 的「固定 10px/mm 换算」，指相机/棋盘格标定一律打回。）
- **`board_size_mm()` 是否为板尺寸的唯一真源**：gridfinity 下必须返回 `(units*42, units*42)`，`build_board` 的 `Rect` 必须取自它；出现"用 `widthMm` 建实体但用 `units*42` 判分块"即打回
- **`print-bed` 是否按 `printBed − 2*edge`**：用整张床会立刻触发 §8.1 分块，出现即打回

**任一项不过 → 打回，不合并。**

---

### 12.4 新会话交接（SDS 定稿后）

> 计划 `v1-plan-v1.3.md` §9 是「定稿 → 新会话开工」的交接物，含：开工前已完成清单、可直接复制的**新会话启动口令**、WSL 环境注意事项、遗留项。主会话开工前先读它，再按 §12.1 分工派活。
> 环境已在本会话实测验通：`.venv`（Python 3.14.4）+ `pip install -r python_backend/requirements.txt` 全绿（numpy 2.5.4 / shapely 2.2.0 / manifold3d 3.5.4 / trimesh 5.2.0 / cv2 5.0.0 / skimage 0.26.0 / ezdxf 1.4.5）。

