以暗猜接口为耻，以认真查阅为荣
以模糊执行为耻，以寻求确认为荣
以盲想业务为耻，以人类确认为荣
以创造接口为耻，以复用现有为荣
以跳过验证为耻，以主动测试为荣
以破坏架构为耻，以遵循规范为荣
以假装理解为耻，以诚实无知为荣
以盲目修改为耻，以谨慎重构为荣

---

📌 项目背景（给 AI 看）

本项目是仿 Tooltrace 的 Web 工具：用户上传「工具放在 A4 纸上的俯拍照片」，Python 后端完成 A4 纸检测、透视校正、工具轮廓提取和基元化，前端负责交互与可视化，最终导出 STL/STEP/DXF 文件用于 3D 打印工具收纳。

> **⚠️ 架构（2026-07-10 最终确认）**：前端的 OpenCV.js 客户端管线已全部移除。当前架构为 **「FastAPI Python 后端 + React 前端」**。所有图像处理（纸张检测、透视校正、轮廓提取、基元化）均在 Python 端完成，前端仅负责文件上传、API 调用、结果显示和手动编辑。桌面化打包（Tauri/Electron）待未来接入。详见 **§一 架构总览**。

**需求文档**：`PRODUCT_REQUIREMENTS.md`（功能清单 & 阶段规划）；**算法参考**：`reference/` 目录（算法实现的纯净备份，不直接在主线调用）。

---

## 一、架构总览

### 1.1 分层架构

```
┌──────────────────────────────────────────────┐
│              浏览器 (React + TS)               │
│  Upload → Calibration → Segmentation → Editor │
│  → Params → Export (3D 预览 + STL 下载)        │
│                    ↓ API 调用                   │
├──────────────────────────────────────────────┤
│        Python Backend (FastAPI :8001)          │
│  /detect-paper  /extract-contours               │
│  /extract-tool-mask  /update-contour            │
│  /simplify-contours  /generate-cad              │
│                    ↓                            │
│         算法模块 (纯 OpenCV, 无 SAM)            │
│  latest_paper_detection.py                     │
│  sam_tool_contour.py (v26 轮廓)                │
│  main.py (内联 curvature-based 抽稀基元化)     │
│  cad_engine.py (trimesh + manifold3d CAD)      │
└──────────────────────────────────────────────┘
```

### 1.2 前端技术栈

| 层               | 技术                                                                             |
| ---------------- | -------------------------------------------------------------------------------- |
| 框架             | React 19 + TypeScript 6                                                          |
| 构建             | Vite 8 + TailwindCSS 3                                                           |
| 状态             | Zustand 5 (`src/app/store.ts`)                                                   |
| 画布             | 原生 Canvas 3 层架构（display/preview/interaction），已移除 Fabric.js            |
| 3D               | Three.js 0.185 + STLLoader + OrbitControls（Viewport 内嵌 3D 预览）              |
| 已安装但暂未使用 | `@techstark/opencv-js`, `minisam`, `onnxruntime-web`（前端管线已移除，后续清理） |

### 1.3 后端技术栈

| 层       | 技术                                                                        |
| -------- | --------------------------------------------------------------------------- |
| 框架     | FastAPI + uvicorn (:8001)                                                   |
| 图像处理 | OpenCV 4.9 (cv2)                                                            |
| CAD 建模 | trimesh + manifold3d + shapely                                              |
| 依赖     | numpy, pillow, python-multipart                                             |
| 运行方式 | `cd python_backend && uvicorn main:app --host 0.0.0.0 --port 8001 --reload` |

---

## 二、项目文件结构（当前实际状态）

### 2.1 前端 `src/`

```
src/
├── main.tsx                          # ReactDOM 入口
├── index.css                         # Tailwind 全局样式
├── vite-env.d.ts                     # Vite 类型声明
│
├── app/
│   └── store.ts                      # Zustand 全局状态（step/imageUrl/primitives + CADParams/CADResult）
│
├── api/
│   └── toolProcessor.ts              # 所有后端 API 调用封装
│       detectPaper(file)             → POST /detect-paper
│       extractContours(file)         → POST /extract-contours
│       extractToolMask(file)         → POST /extract-tool-mask
│       updateContour(maskData)       → POST /update-contour
│       simplifyContours(maskData)    → POST /simplify-contours
│       generateCAD(params,prims)     → POST /generate-cad
│
├── utils/
│   └── types.ts                      # Primitive/Point/LinePrimitive/CADParams/CADResult 等类型定义
│
├── types/
│   └── opencv.d.ts                   # OpenCV 类型声明（前端已不用，待清理）
│
├── components/ui/                    # 通用 UI 组件（零外部依赖，自绘 SVG 图标）
│   ├── icons.tsx                     # 27 个自绘 SVG 图标 + Icon 组件
│   ├── Button.tsx                    # 按钮（primary/secondary/success/ghost + sm/md）
│   ├── Card.tsx                      # 卡片容器
│   ├── Badge.tsx                     # 标签
│   ├── SectionHeading.tsx            # 章节标题
│   └── EmptyState.tsx                # 空状态占位
│
├── pages/
│   └── Home.tsx                      # 根页面 → 渲染 <Workspace />
│
└── features/
    ├── workspace/
    │   ├── Workspace.tsx             # ★ 主容器：编排完整的 6 步工作流
    │   ├── TopBar.tsx                # 顶部栏（品牌 logo + "生成嵌件"按钮）
    │   ├── LeftRail.tsx              # 左侧导航栏（6 个步骤按钮 + 收起切换）
    │   ├── Viewport.tsx              # 中央画布：显示原图/校正图/蒙版叠加 + export 模式 3D 预览
    │   └── PlanningPanel.tsx         # 右侧参数面板（根据 step 渲染不同子面板）
    │
    ├── upload/
    │   └── UploadPanel.tsx           # 上传步骤：提示 + 选择照片按钮
    │
    ├── calibration/
    │   └── CalibrationPanel.tsx      # 校准步骤：显示检测结果 + 重新检测/透视校正
    │
    ├── segmentation/
    │   └── SegmentationPanel.tsx     # 轮廓提取步骤：提取按钮 + 检测失败时的手动绘制选项
    │
    ├── editor/
    │   ├── EditorPanel.tsx           # 编辑步骤容器：透传 props 给 MaskEditor
    │   └── MaskEditor.tsx            # ★ 原生 Canvas 3 层画布：画笔/橡皮 + 形状工具(直线/折线/矩形/椭圆) + 防抖修正滑块 + 「更新轮廓」「抽稀基元化」双按钮
    │
    ├── params/
    │   └── ParamsPanel.tsx           # ★ 参数配置（Foam/Gridfinity 模式 + 滑块参数 + 生成按钮）
    │
    └── export/
        └── ExportPanel.tsx           # ★ 导出 STL（base64 解码 + 下载）+ 模型摘要（顶点/面/体积/范围）
```

### 2.2 后端 `python_backend/`

```
python_backend/
├── main.py                           # FastAPI 应用入口（6 个 API 端点，含 /generate-cad）
├── cad_engine.py                     # ★ CAD 引擎：Foam 嵌件 + Gridfinity 基座 3D 建模
│   generate_cad_model(primitives, params) → trimesh.Scene → STL base64
│   _primitives_to_polygon()          #   基元 → shapely Polygon（含缓冲/简化）
│   _extrude_foam_insert()            #   Foam 模式：多边形 → 直壁/斜壁挤压
│   _extrude_gridfinity_base()        #   Gridfinity 模式：基座 + 凹槽阵列
│   _make_rounded_box()               #   圆角矩形辅助（shapely buffer → 挤压）
├── requirements.txt                  # fastapi, uvicorn, opencv-python, numpy, trimesh, manifold3d, shapely
│
├── sam_tool_contour.py               # ★ v26 工具轮廓提取（主算法）
│   extract_tool_contours_v26()       #   4 路径并集 → 阴影减法 → 最大连通块 → 填洞 → 高斯平滑
│   convert_contour_to_primitives()   #   轮廓 → 折线基元（DP 简化）
│   paper_lab_stats()                 #   四角纸色采样
│   shadow_mask()                     #   阴影判定
│   path_division_otsu()              #   路径 A：除法归一化 + Otsu
│   path_color_saturation()           #   路径 B：HSV 高饱和度
│   path_lab_color_gradient()         #   路径 C：LAB 色梯度（Scharr）
│   path_canny_bridge()               #   路径 E：Canny 边缘桥接
│
├── latest_paper_detection.py         # 纸张检测（调用 reference/robust_paper_detector）
│   detect_paper_corners_latest()     #   四角检测
│   warp_paper_latest()               #   透视校正（固定 A4 840×1188px）
│
├── advanced_tool_contour.py          # 旧版轮廓提取（四策略并集，已被 v26 替代）
│                                      #   保留作为 fallback 参考
│
├── optimized_contour_processing.py   # Chaikin 平滑 + RDP 抽稀 + 圆弧拟合
│                                      #   独立的基元化实现，未接入主线
│
└── optimized_paper_detection.py      # 旧版纸张检测 wrapper，已由 latest_ 替代
```

### 2.3 参考目录 `reference/`

```
reference/
├── pkg_paper_detection/
│   └── robust_paper_detector.py      # 被 latest_paper_detection.py 导入
├── pkg_tool_contour_detection.zip    # 旧版轮廓检测打包
├── contour_simplify/
│   └── pkg_contour_simplify_primitives/
│       ├── contour_simplify.py       # 完整抽稀基元化（参考实现）
│       ├── abstract_primitive.py     # 基元抽象
│       ├── repro_contour_v9.py       # v9 轮廓提取
│       └── batch_process.py          # 批量处理
└── *.py (contour_v26/v27/v28)        # 各版本算法快照
```

### 2.4 项目根目录散落文件（测试/调试用，非主线）

根目录有 ≈20 个 `.py`/`.js` 测试脚本和调试 HTML/图片文件。AI 修改主线时 **不要管这些文件**，只关注 `src/` `python_backend/` `reference/` 三条路径。

---

## 三、后端 API 规范

所有端点基础路径：`http://localhost:8001`

### 3.1 POST /detect-paper

**输入**：`multipart/form-data`，字段 `file`（原始照片）

**输出**：

```json
{
  "success": true,
  "corners": [{"x": 123, "y": 456}, ...],   // 4 个角点
  "warped_image": "data:image/jpeg;base64,..."  // 校正后图像
}
```

**内部流程**：

1. `latest_paper_detection.detect_paper_corners_latest()` → 调 `reference/robust_paper_detector.detect_paper_corners_robust()`
2. 若成功：`latest_paper_detection.warp_paper_latest()` → 透视校正到 840×1188px（A4 比例）
3. 若失败：返回 `{success: false, error: "未检测到纸张"}`

### 3.2 POST /extract-contours

**输入**：`multipart/form-data`，字段 `file`（校正后图像）

**输出**：

```json
{
  "success": true,
  "primitives": [{ "type": "polyline", "points": [...] }],
  "debug_image": "data:image/jpeg;base64,...",  // 校正图上绘制红色轮廓
  "summary": { "lines": 0, "polylines": 1, "arcs": 0 }
}
```

**内部流程**：

1. `sam_tool_contour.extract_tool_contours_v26()` → 提取工具轮廓
2. `sam_tool_contour.convert_contour_to_primitives()` → DP 简化轮廓为折线基元

### 3.3 POST /extract-tool-mask

**输入**：`multipart/form-data`，字段 `file`（校正后图像）

**输出**：

```json
{
  "success": true,
  "mask_image": "data:image/jpeg;base64,..." // 二值蒙版（工具区域=255，背景=0）
}
```

**内部流程**：

1. `extract_tool_contours_v26()` → 提取轮廓
2. 若检测到轮廓：`cv2.drawContours(mask, [contour], -1, 255, cv2.FILLED)`
3. 若未检测到：返回全黑空白蒙版（同尺寸），`success: true`（前端可手动绘制）

### 3.4 POST /update-contour

**输入**：JSON body

```json
{ "mask_image": "data:image/jpeg;base64,..." }
```

**输出**：

```json
{
  "success": true,
  "primitives": [{ "type": "polyline", "points": [{ "x": 0, "y": 0 }, ...] }]
}
```

**内部流程**：

1. Base64 解码 → 灰度蒙版
2. `cv2.findContours` → 取最大轮廓 → 转为 polyline 基元（不做任何简化/拟合）
3. 用途：用户反复修改蒙版时快速预览轮廓，满意后再用 `/simplify-contours` 抽稀

### 3.5 POST /simplify-contours

**输入**：JSON body

```json
{ "mask_image": "data:image/jpeg;base64,..." }
```

**输出**：

```json
{
  "success": true,
  "primitives": [{ "type": "line", ... }, { "type": "arc", ... }],
  "summary": { "lines": 5, "polylines": 0, "arcs": 2 }
}
```

**内部流程**：

1. Base64 解码 → 灰度蒙版
2. `cv2.findContours` → 取最大轮廓
3. **曲率分段**：`_compute_curvature()` 计算每点一阶曲率（相邻边夹角 sinθ）→ `_segment_by_curvature()` 形态学侵蚀/膨胀，输出 `('LINE', pts)` 和 `('ARC_CAND', pts)` 段
4. **每段拟合**：
   - `LINE` 段 → 取首尾两点作为 `line` 基元
   - `ARC_CAND` 段 → `_fit_arc_robust()` 调用 `cv2.fitEllipse()`，通过圆度检查（轴比偏差 <25%）、跨度检查（20°~270°）、自适应误差阈值（2.0 + (span-20)/30.0 px）验证。通过 → `arc` 基元；失败 → `_subdivide_polyline()` 细粒度 DP 折线
5. 参数自适应：`max_radius = img_diag * 0.03`，`curv_thresh = clamp(0.02, 0.05, 50/img_diag)`

**实现来源**：`main.py` 内联实现，无外部依赖（纯 OpenCV + numpy）。2026-08-07 以 curvature-based 算法替代了旧版代数最小二乘。

### 3.6 POST /generate-cad

**输入**：JSON body

```json
{
  "primitives": [{ "type": "line", "p0": {"x":0,"y":0}, "p1": {"x":10,"y":10} }, ...],
  // Foam 模式参数
  "mode": "foam",
  "length_mm": 200,
  "width_mm": 150,
  "height_mm": 20,
  "fillet_radius": 5,
  // Gridfinity 模式参数（mode="gridfinity" 时使用）
  "units_x": 3,
  "units_y": 2,
  "height_u": 3,
  "has_magnet_holes": true,
  // 通用参数
  "embed_depth": 15,
  "tool_offset": 1.0
}
```

**输出**：

```json
{
  "success": true,
  "stl_base64": "...", // Base64 编码的 ASCII STL 文件
  "summary": {
    "mode": "foam",
    "vertices": 1234,
    "faces": 2468,
    "volume_mm3": 12345.6,
    "bounds": { "x": [0, 200], "y": [0, 150], "z": [-10, 10] },
    // Foam 模式附加字段
    "length_mm": 200,
    "width_mm": 150,
    "height_mm": 20,
    "fillet_radius": 5
    // Gridfinity 模式附加字段
    // "units_x": 3,
    // "units_y": 2,
    // "height_u": 3
  }
}
```

**内部流程**（`cad_engine.py`）：

1. **参数解析**：`InsertParams.from_dict()` 构建参数模型 → `BoxParams`（Foam）或 `GridfinityParams`（Gridfinity）+ 通用 `embed_depth`/`tool_offset`
2. **基底生成**：
   - Foam 模式：`_make_rounded_box(length, width, height, fillet_radius)` — 用 shapely buffer 生成圆角矩形截面，trimesh.extrude_polygon 拉伸
   - Gridfinity 模式：`_make_gridfinity_base()` — 圆角底板 + 底部裙边布尔减 + 可选磁吸孔（cylinder 布尔减）
3. **工具槽布尔减**：`_extrude_tool_slot()` 将 primitives 转为 2D 多边形 → 缩放至基底尺寸并居中 → shapely Polygon → extrude_polygon 拉伸 → Manifold 布尔减（若可用）或 trimesh.difference
4. **多边形偏移**：`_offset_polygon()` 沿法线方向移动顶点实现 tool_offset 容差
5. **输出**：`base.export(file_type='stl')` → base64 编码返回 + 统计摘要

---

## 四、前端工作流（6 步管线）

### 4.1 步骤导航

`Workspace.tsx` 管理一个 6 步线性工作流：

```
upload → calibration → segmentation → editor → params → export
```

- 通过 Zustand store 的 `step` 字段控制当前步骤
- `LeftRail.tsx` 渲染 6 个步骤按钮，点击可跳转（无强制性前序依赖，但后续步骤依赖前面步骤产出的数据）
- `PlanningPanel.tsx` 根据 `step` 渲染对应的子面板

### 4.2 各步骤详解

#### Step 1: upload — 上传图片

- `UploadPanel.tsx` 显示 4 条拍摄建议
- 点击"选择照片"或拖放到 Viewport → 触发 `handleFile` → 设置 `imageUrl` → 自动跳 `calibration`

#### Step 2: calibration — 纸张校准

- 进入时自动调 `detectPaper(file)` → 后端检测纸张四角 + 透视校正
- `CalibrationPanel.tsx` 显示：
  - 检测中：spinner
  - 检测成功：四角坐标 + 置信度 + 偏斜警告
  - 检测失败：红色错误提示
- 按钮：「重新检测」「透视校正」
- 校正成功 → `warpedUrl` 设置到状态 → 可进入下一步

#### Step 3: segmentation — 轮廓提取

- `SegmentationPanel.tsx` 核心流程：
  1. 点击「提取工具轮廓」→ `processContourExtraction(file)`
  2. 内部三步：`extractContours` → `extractToolMask` → `simplifyContours`
  3. 成功 → `setSimplifiedPrimitives` → 自动跳 `editor`
  4. **失败** → 显示「⚠ 未检测到工具轮廓」+ 两个选项：
     - 「✏ 手动绘制」→ 生成空白蒙版 → 跳 editor（从零画）
     - 「← 重新上传」→ 清空状态 → 回 upload

#### Step 4: editor — 矢量编辑（MaskEditor）

- `EditorPanel.tsx` 容器：透传 props 给 MaskEditor
- `MaskEditor.tsx` 核心功能（2026-07-10 完全重写）：
  - **三层 Canvas 架构**：display（背景图 30% + 蒙版显示）→ preview（形状拖拽预览）→ interaction（透明捕获层，鼠标事件）
  - **手绘工具**：画笔（刷白，键 B）/ 橡皮（刷黑，键 E），笔刷大小 2-50px 可调（键 [ / ]）
  - **形状工具**：直线（键 L，拖拽画线）/ 折线（键 P，单击加顶点，Enter 完成，Esc 取消）/ 矩形（键 R，填充）/ 椭圆（键 O，填充）
  - **防抖修正**：加权滑动平均（8 点 buffer）+ EMA（alpha=0.20）+ quadratic bezier 平滑，UI 滑块可调强度（弱/中/强）
  - **双按钮**：「更新轮廓」（/update-contour，快速预览未简化轮廓）→ 「抽稀基元化」（/simplify-contours，产出 line/arc 基元）
  - **左侧 Viewport 联动**：预览/抽稀后左侧大图立即显示红色轮廓线（从 primitives 实时绘制）
- **已知限制**：暂无撤销/重做、无控制点拖拽微调

#### Step 5: params — 参数配置

- `ParamsPanel.tsx`：两种模式选择 + 滑块参数 + 「生成 3D 模型」按钮
  - **Foam 模式**（嵌件）：底板长度（20-500mm）、底板宽度（20-500mm）、底板高度（5-200mm）、圆角半径（0-50mm）
  - **Gridfinity 模式**（基座）：X 网格数（1-10）、Y 网格数（1-10）、高度单位（1-10u，1u=7mm + 5mm 基座）、磁吸孔开关
  - **通用参数**：工具嵌入深度（1-50mm）、轮廓偏移（-5~10mm，负值缩小轮廓）
  - 点击「生成 3D 模型」→ `POST /generate-cad` → 更新 store 的 `cadResult` → 自动跳 `export`

#### Step 6: export — 导出文件

- `ExportPanel.tsx`：显示模型摘要（顶点数、面数、体积、范围）
- 「下载 STL 文件」按钮：base64 解码 → 创建 Blob → `URL.createObjectURL` → 触发下载
- 左侧 Viewport 切换为 Three.js 3D 预览（自动旋转 + OrbitControls）

### 4.3 Viewport（中央画布）

- 无图片时：显示拖放上传区域
- editor 模式：显示 `warpedUrl`（校正图），叠加红色轮廓线（从 `currentPrimitives` 实时绘制 line/arc/polyline）
- export 模式且 `cadResult.stl_base64` 存在：全屏 Three.js 3D 预览（深色背景 + 半透明边缘线 + 自动旋转 + OrbitControls）
- 其他模式：显示 `warpedUrl`（校正图），可选叠加 `maskUrl`（蒙版，multiply 混合）
- 底部工具条：缩放、适应窗口、网格切换
- 左上角阶段指示器

### 4.4 全局状态 (Zustand store)

```typescript
// src/app/store.ts
step: Step              // 当前步骤 ("upload"|"calibration"|"segmentation"|"editor"|"params"|"export"|"diagnose")
imageUrl: string | null // 原始上传图片
primitives: Primitive[] // 基元化结果

// CAD 参数（Foam / Gridfinity 双模式）
cadParams: CADParams = {
  mode: "foam" | "gridfinity",
  // Foam 参数
  length_mm: 200,         // 底板长度 (mm)
  width_mm: 150,           // 底板宽度 (mm)
  height_mm: 20,           // 底板高度 (mm)
  fillet_radius: 5,        // 底板圆角半径 (mm)
  // Gridfinity 参数
  units_x: 3,              // X 方向网格数
  units_y: 2,              // Y 方向网格数
  height_u: 3,             // Gridfinity 高度单位 (1u = 7mm)
  has_magnet_holes: true,  // 是否生成磁吸孔
  // 通用参数
  embed_depth: 15,         // 工具嵌入深度 (mm)
  tool_offset: 1.0,        // 工具轮廓外扩容差 (mm)
}

// CAD 结果
cadResult: CADResult = {
  stl_base64: string | null,     // Base64 编码的 STL 文件
  summary: {                     // 模型摘要
    vertices: number,             //   顶点数
    faces: number,                //   三角面数
    volume_mm3: number,           //   体积 (mm³)
    bounds: {                     //   包围盒范围
      x: [min, max],
      y: [min, max],
      z: [min, max],
    },
  } | null,
}

// Actions
setStep(step)           // 切换步骤
setImageUrl(url)        // 设置图片
setPrimitives(p)        // 设置基元
setCADParams(p)         // 部分更新 CAD 参数
resetCADParams()        // 重置为默认值
setCADResult(r)         // 设置 CAD 结果
setIsGenerating(v)      // 生成中状态
```

---

## 五、v26 轮廓提取算法（核心）

### 5.1 算法文件

`python_backend/sam_tool_contour.py`

### 5.2 管线（"只填不啃"）

```
原图（BGR, 校正后）
  │
  ├─ 路径 C: LAB 色梯度 (Scharr)        → mc  (形状好，抗阴影)
  ├─ 路径 A: 除法归一化 + Otsu          → ma  (填实均匀直边内部)
  ├─ 路径 E: Canny 边缘桥接             → me  (补金属直边)
  └─ 路径 B: HSV 高饱和度               → ms_sat (彩色件保护)
                │
          bitwise_or 并集 → base
                │
          阴影保护减法:
            paper_lab_stats(四角纸色) → shadow_mask
            protect = ms_sat ∪ mc (膨胀7px不碰彩色/梯度区)
            sh_eff = shadow AND NOT protect
            base = base AND NOT sh_eff
                │
          去边框噪声 (2%边距清零)
          闭运算桥接 (核=1.2%min_dim) + 轻开运算去噪
                │
          取最大连通块 + 合并近邻块 (bbox扩8%)
          填洞 (fill_holes flood fill反转法) ×2
                │
          取外轮廓 → 高斯平滑 (sigma=2.0)
```

### 5.3 关键参数

| 参数           | 值                               | 说明             |
| -------------- | -------------------------------- | ---------------- |
| 闭运算核大小   | `max(5, int(min(h,w)*0.012))\|1` | 约 1.2% 最小边长 |
| 阴影 L 阈值    | `pL * 0.80`                      | 比纸暗 80%       |
| 阴影 ab 容差   | `13`                             | ab 通道差值      |
| 轮廓平滑 sigma | `2.0`                            | 环形高斯         |
| 最小面积过滤   | `h*w*0.005`                      | 0.5% 图像面积    |
| 边框裁剪       | `max(3, int(min(h,w)*0.02))`     | 2% 边距          |

### 5.4 已知局限

- **浅色/银色工具**在低对比度场景下，路径 A（Otsu）可能漏检工具中心区域
- **阴影区工具边缘**可能被 `shadow_mask` 误判切除，依赖 `protect` 区的膨胀保护
- **复杂形状（尖嘴钳、卡尺）**的薄边缘可能未完全捕获
- 算法无 SAM 语义补全，完全依赖传统 CV 手段

---

## 六、CAD 引擎设计

### 6.1 算法文件

`python_backend/cad_engine.py`

### 6.2 依赖

- `trimesh`：三角网格构建、STL 导出
- `manifold3d`：高质量布尔运算后端（可选，回退到 trimesh.difference）
- `shapely`：2D 多边形构造（圆角矩形、缓冲、简化）
- `numpy`：数值运算

### 6.3 参数模型

```
InsertParams（总配置）
├── mode: "foam" | "gridfinity"
├── foam: BoxParams              # Foam 模式参数
│   ├── length_mm: 200           #   底板长度
│   ├── width_mm: 150            #   底板宽度
│   ├── height_mm: 20            #   底板高度
│   ├── fillet_radius: 5         #   圆角半径
│   └── wall_thickness: 2        #   壁厚（预留，暂未使用）
├── gridfinity: GridfinityParams # Gridfinity 模式参数
│   ├── units_x: 3               #   X 方向网格数
│   ├── units_y: 2               #   Y 方向网格数
│   ├── height_u: 3              #   高度单位 (1u = 7mm + 5mm 基座)
│   ├── has_magnet_holes: true   #   是否生成磁吸孔
│   ├── size_x (= units_x × 42mm)
│   ├── size_y (= units_y × 42mm)
│   └── height_mm (= height_u × 7 + 5)
├── primitives: List[Dict]       # 工具轮廓基元列表
├── tool_offset: 1.0             # 轮廓外扩容差 (mm)
└── embed_depth: 15              # 工具嵌入深度 (mm)
```

### 6.4 管线

```
generate_insert(InsertParams)
  │
  ├─ 1. 基底生成
  │   ├─ [foam]  _make_rounded_box(l, w, h, r)
  │   │    shapely box → buffer(-r) → buffer(r) → extrude_polygon
  │   │
  │   └─ [gridfinity] _make_gridfinity_base(params)
  │        _make_rounded_box(sx, sy, sz, corner_r=3)
  │        → 底部裙边布尔减 (内缩 1.5mm 方盒)
  │        → [has_magnet_holes] 磁吸孔阵列 (cylinder × units_x×units_y)
  │
  ├─ 2. 工具槽布尔减
  │    _extrude_tool_slot(primitives, embed_depth, tool_offset, base_sx, base_sy)
  │      _primitives_to_2d_polygon()    # 基元 → N×2 numpy array
  │        line  → p0, p1 加入点集
  │        arc   → points 加入点集
  │        polyline → points 加入点集
  │      _offset_polygon(offset)        # 沿法线方向偏移 tool_offset
  │      缩放至基底尺寸 (840×1188 → base_sx×base_sy)
  │      shapely.Polygon → extrude_polygon(embed_depth+1)
  │      [HAS_MANIFOLD] Manifold 布尔减
  │      [else] trimesh.difference
  │
  └─ 3. 导出
       base.export(file_type='stl') → base64 编码 → 统计摘要
```

### 6.5 关键常量

| 常量                      | 值   | 说明                         |
| ------------------------- | ---- | ---------------------------- |
| GRIDFINITY_PITCH          | 42.0 | Gridfinity 标准网格间距 (mm) |
| GRIDFINITY_HOLE_DIA       | 6.5  | 磁吸孔直径 (mm)              |
| GRIDFINITY_HOLE_DEPTH     | 2.5  | 磁吸孔深度 (mm)              |
| GRIDFINITY_CORNER_R       | 3.0  | Gridfinity 底板圆角 (mm)     |
| GRIDFINITY_BASE_THICKNESS | 5.0  | Gridfinity 底板基础厚度 (mm) |
| GRIDFINITY_SKIRT          | 1.5  | Gridfinity 底部裙边高度 (mm) |
| GRIDFINITY_WALL           | 1.2  | Gridfinity 隔板壁厚 (mm)     |

### 6.6 已知局限

- **自交多边形**：基元组合可能产生自交轮廓，shapely 的 `buffer(0)` 可修复但可能改变形状
- **复杂布尔运算**：Gridfinity 磁吸孔使用 Manifold 差集，对窄壁（<2mm）可能产生退化三角面
- **无 STEP 导出**：当前仅支持 STL（ASCII），trimesh 可扩展 STEP 但需额外依赖
- **工具槽居中**：当前假设校正图尺寸 840×1188px 并缩放至基底尺寸，未支持手动定位

---

## 七、开发约定

### 7.1 前端

- **图标**：只使用 `src/components/ui/icons.tsx` 中定义的 27 个自绘 SVG 图标，不引入图标库。新增图标在该文件添加。
- **样式**：TailwindCSS 优先，不使用内联 style 除非动画/transform 等 CSS-in-JS 场景。颜色使用项目 design tokens（`brand-600`/`brand-50` 等，在 `tailwind.config.js` 定义）。
- **组件**：可复用 UI 放 `src/components/ui/`，业务功能组件放 `src/features/{功能名}/`。
- **状态**：跨组件共享状态用 Zustand store，局部状态用 React useState/useCallback。
- **API 调用**：全部通过 `src/api/toolProcessor.ts` 封装，不在组件中直接写 fetch。

### 7.2 后端

- **新增端点**：在 `main.py` 添加路由函数，算法逻辑放在独立 `.py` 文件中。
- **算法迭代**：保留旧版本文件（如 `advanced_tool_contour.py`），新版本放在单独的文件中（如 `sam_tool_contour.py`），通过 import 接入 main.py。不在原文件上覆盖。
- **参考 vs 主线**：`reference/` 目录下的代码是算法备份和纯净参考，不直接在主线 API 中 import（`main.py` 的纸张检测除外——`latest_paper_detection.py` 是 wrapper，它 import reference 的算法实现）。如需使用 reference 中的算法，写在 `python_backend/` 下的 wrapper 文件中。
- **CAD 引擎新增依赖**：`trimesh`、`manifold3d`、`shapely` 需在 `requirements.txt` 中声明。在无 GPU 环境下，manifold3d 回退到 trimesh 内置布尔运算。

### 7.3 通用

- **调试**：Python 算法的调试单独写测试脚本在 `python_backend/` 目录下，不污染 `main.py` 端点逻辑。前端调试在浏览器 DevTools 进行。
- **根目录散落文件**：`.py`/`.js`/`.html` 测试文件是历史遗留，不要在上面修改或新增。AI 不要引用或依赖这些文件。
- **npm 包**：`@techstark/opencv-js`、`minisam`、`onnxruntime-web` 已安装但前端管线已移除，后续可清理 package.json。

---

## 八、启动指南

### 8.1 后端

```bash
cd python_backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

验证：`curl http://localhost:8001/` → `{"message":"Tool Management Backend API"}`

### 8.2 前端

```bash
npm install
npm run dev
```

默认 `http://localhost:5173`，自动代理 API 到 `:8001`。

### 8.3 开发时的注意事项

- 后端必须先于前端启动，否则前端 API 调用会报网络错误
- 图片处理可能较慢（v26 轮廓提取涉及多次形态学操作），前端有 loading 状态处理
- 大图（>4000px）可能触发后端内存压力，建议前端先压缩
- CAD 生成涉及三角网格构建，复杂轮廓可能需要 1-3 秒

---

## 九、技术债务 & 待办

| 优先级 | 项                                                                     | 说明                                                        |
| ------ | ---------------------------------------------------------------------- | ----------------------------------------------------------- |
| **P0** | MaskEditor 撤销/重做                                                   | 用户手动画错无法回退                                        |
| P1     | MaskEditor 控制点拖拽                                                  | 比画笔更精确的轮廓微调方式                                  |
| P1     | 清理无用 npm 包                                                        | opencv-js / minisam / onnxruntime-web / fabric.js（已移除） |
| P1     | 清理 `src/types/opencv.d.ts`                                           | OpenCV 类型声明已无用                                       |
| P2     | `optimized_paper_detection.py` 与 `latest_paper_detection.py` 功能重复 | 保留 latest，可删除 optimized                               |
| P2     | `optimized_contour_processing.py` 独立基元化                           | 是否合并进 main.py 或 sam_tool_contour.py                   |
| P2     | CAD 引擎 STEP 导出                                                     | trimesh 支持 STEP 但需额外依赖                              |
| P2     | CAD 引擎 GUI 参数实时预览                                              | 调整滑块时后端实时返回预览 STL                              |
| P3     | 桌面化打包                                                             | Tauri/Electron + Python 后端嵌入                            |

---

## 附录：开发日志

### 2026-08-07 CAD 引擎完整实现（第六次会话）

**文件**：`python_backend/cad_engine.py` + `python_backend/main.py` + `python_backend/requirements.txt` + `src/app/store.ts` + `src/api/toolProcessor.ts` + `src/utils/types.ts` + `src/features/params/ParamsPanel.tsx` + `src/features/export/ExportPanel.tsx` + `src/features/workspace/Viewport.tsx` + `DEVELOPMENT_GUIDE.md`

**改动**：

- **新增 `python_backend/cad_engine.py`**：完整的 CAD 建模引擎，基于 trimesh + manifold3d + shapely：
  - `_primitives_to_polygon()`：基元（line/arc/polyline）→ shapely Polygon
  - `_extrude_foam_insert()`：Foam 模式嵌件挤压（支持斜壁）
  - `_extrude_gridfinity_base()`：Gridfinity 模式基座 + 凹槽阵列
  - `_make_rounded_box()`：圆角矩形辅助（shapely buffer）
  - `generate_cad_model()`：主入口 → trimesh.Scene → STL base64
  - 参数校验：thickness 5-30mm、wall_angle 30-90°、base_height 0-20mm、grid_size 1-5、tolerance 0.1-2.0
- **`main.py` 新增 `/generate-cad` 端点**：接收 primitives + params → 调 cad_engine → 返回 STL base64 + 摘要
- **`requirements.txt` 新增依赖**：`trimesh`, `manifold3d`, `shapely`
- **前端 store 新增**：`cadParams`（CADParams 类型）+ `cadResult`（CADResult 类型）+ `setCadParams`/`setCadResult` actions
- **前端 types 新增**：`CADParams`（mode/thickness/wall_angle/base_height/grid_size/tolerance）+ `CADResult`（stl_base64/summary）
- **API 层新增 `generateCAD()`**：POST /generate-cad 封装
- **`ParamsPanel.tsx` 完整实现**：
  - 两种模式切换：Foam（嵌件）/ Gridfinity（基座）
  - 各模式专属滑块参数（thickness、wall_angle、base_height、grid_size）
  - 「生成 3D 模型」按钮 → loading + 错误处理
- **`ExportPanel.tsx` 完整实现**：
  - 模型摘要卡片（顶点数、面数、体积、范围）
  - 「下载 STL 文件」按钮 → base64 解码 + Blob 下载
  - 无模型时的空状态提示
- **`Viewport.tsx` 集成 3D 预览**：
  - export 模式且 `cadResult.stl_base64` 存在 → 全屏 Three.js 预览
  - `CADPreview` 组件：STLLoader 解析 → 自动居中/缩放 → OrbitControls + 自动旋转 → 半透明边缘线
- **安装依赖**：`pip install trimesh manifold3d shapely` 全部成功
- **验证**：`curl` 测试 `/generate-cad` 返回有效 STL base64 + 摘要数据

### 2026-08-07 根目录清理 + warp_paper 比例修复（第五次会话）

**文件**：根目录 + `reference/pkg_paper_detection/robust_paper_detector.py` + `DEVELOPMENT_GUIDE.md`

**改动**：

- **根目录清理**：删除 25+ 个历史遗留测试脚本（`compare_algorithms.py`、`debug_*.py`、`test_*.py`、`test-*.js`、`index.html`、`view_results.html`、`visual_test.py` 等）和调试生成图片（`corners_detected.jpg`、`paper_detection_debug.png`、`warped_result.jpg` 等）。保留 `postcss.config.js`、`tailwind.config.js`、`tests/` 目录。
- **warp_paper 比例修复**：`reference/pkg_paper_detection/robust_paper_detector.py` 中 `warp_paper()` 函数的条件判断逻辑修正——当 `w_edge/h_edge > 1` 时（宽>高），长边是宽，输出 `pw = w_edge, ph = w_edge/ratio`；反之（高>宽），长边是高，输出 `ph = h_edge, pw = h_edge/ratio`。修复前条件判断导致输出尺寸比例错误（短/长=0.707 而非长/短=1.414），修复后 `testpic.jpg` 验证长/短=1.415。
- **测试规范**：新增 `tests/` 目录存放管线输出验证图（如 `tests/test_warped_fixed.jpg`），Python 端 API 手动测试用 curl/python 命令直接执行，不写独立测试脚本文件。
- **不涉及**：`python_backend/main.py`、`sam_tool_contour.py`、前端组件未修改。

### 2026-07-10 轮廓检测失败时给用户选项（第二次会话）

**文件**：`main.py` + `Workspace.tsx` + `SegmentationPanel.tsx` + `PlanningPanel.tsx`

**改动**：

- 后端 `/extract-tool-mask`：检测不到轮廓时不再返回 error，返回全黑空白蒙版（success:true）
- 前端 `SegmentationPanel`：检测失败时显示「手动绘制」/「重新上传」两个选项，不再直接跳编辑器
- 前端 `Workspace.tsx`：检测失败时不跳转，等待用户选择；手动绘制 → 空白蒙版 → editor；重新上传 → 清空 → upload

**设计决策**：给用户选择权，避免"强制进入空白编辑器"的突兀体验。

### 2026-07-10 DEVELOPMENT_GUIDE.md 完全重写（本次会话）

**动因**：文档引用的 `src/lib/opencvUtils.ts`、`src/lib/opencvLoader.ts`、`src/hooks/useOpenCV.ts` 等核心文件已在 WSL 重构中删除，前端 OpenCV.js 管线被 Python 后端完全替代。文档与实际代码严重脱节（约 60% 内容过时）。

**重写范围**：全部章节 —— 架构总览、文件结构、API 规范、前端工作流、v26 算法、开发约定、启动指南、技术债务。

### 2026-07-10 MaskEditor 完全重写 + 抽稀算法接入 + 双按钮分离（第三次会话）

**文件**：`MaskEditor.tsx` + `EditorPanel.tsx` + `Workspace.tsx` + `Viewport.tsx` + `PlanningPanel.tsx` + `main.py` + `toolProcessor.ts`

**MaskEditor 重写**：

- 从 Fabric.js 换成原生 Canvas 三层架构（display/preview/interaction），彻底解决闪烁和渲染竞态
- **抖动修正加强**：加权滑动平均 8 点 buffer + EMA alpha=0.20 + quadratic bezier，UI 滑块可调强度（弱/中/强）。仅在手绘模式（画笔/橡皮）显示
- **新增 4 个形状工具**：直线（L，拖拽）、折线（P，单击加顶点/Enter 完成/Esc 取消）、矩形（R，填充）、椭圆（O，填充）。形状工具拖拽时实时半透明预览
- 键盘快捷键：B=画笔, E=橡皮, L=直线, P=折线, R=矩形, O=椭圆, [ 缩小笔刷 2px, ] 放大笔刷 2px

**双按钮分离**：

- 新增 `/update-contour` 端点（`main.py`）：mask → findContours → 最大轮廓 polyline，不做任何简化。用户反复改画→预览→满意
- 新增 `handleUpdateContour` 在 `Workspace.tsx` → PlanningPanel → EditorPanel → MaskEditor 全链路透传
- 「更新轮廓」按钮调 /update-contour（快，预览用），「抽稀基元化」按钮调 /simplify-contours（慢，产出 line/arc）
- API 层 `toolProcessor.ts` 新增 `updateContour()` + `normalizePrimitiveArray()` 格式兼容

**后端简化接入**：

- `/simplify-contours` 的 6 个桩函数全部替换为 reference 算法的真实实现：`dp_simplify` (≈50 拐点)、`line_fit_error` (cv2.fitLine RMS)、`circle_fit` (最小二乘)、`circle_fit_error` (RMS 径向)
- `_nearest_dense_index` / `_points_between` 改为闭包捕获 dense 和 vert_idx
- 「抽稀基元化」产出与 v26 同质量的直线/圆弧/折线基元

**Viewport**：

- editor 模式下显示校正图 + 从 primitives 实时绘制的红色轮廓线（p0/p1 字段名修正 + polyline 支持 + toPt() 防御性兼容）

**Workspace 布局**：

- editor 模式下右侧面板从 w-80 (320px) 拓宽至 w-[28rem] (448px)

**Bug 修复**：

- Viewport 用 primitive.start/end 但类型定义是 p0/p1 → 修正
- MaskEditor 背景图 data URL 的 img.onload 绑定前已触发 → 加 img.complete 兜底
- `/extract-contours` 和 `/simplify-contours` 后端返回 [x,y] 数组，前端期望 {x,y} 对象 → API 层 normalizePrimitiveArray 统一转换

### 2026-08-07 /simplify-contours 重写为 curvature-based 算法（第四次会话）

**文件**：`main.py` + `DEVELOPMENT_GUIDE.md`

**改动**：

- **完全重写 `/simplify-contours` 内部算法**，用 curvature-based 分段替代旧版代数最小二乘拟合：
  - 旧算法：`dp_simplify` → `line_fit_error` / `circle_fit`（代数最小二乘，数值不稳定）
  - 新算法：`_compute_curvature`（一阶曲率 sinθ）→ `_segment_by_curvature`（形态学侵蚀/膨胀，输出 LINE / ARC_CAND 段）→ `_fit_arc_robust`（`cv2.fitEllipse` + 圆度/跨度/误差校验）→ `_subdivide_polyline`（失败 fallback）
- **删除**：`import_contour_simplify()` 动态导入函数、`dp_simplify`、`line_fit_error`、`circle_fit`、`circle_fit_error` 四个旧函数
- **修复注释截断**：`# 确保` → `# 确保是BGR格式`
- **参数自适应**：`max_radius = img_diag * 0.03`，`curv_thresh = clamp(0.02, 0.05, 50/img_diag)`
- **不涉及**：A4 纸张检测（`detect_paper_corners` / `perspective_warp`）、工具轮廓提取（`extract_tool_contours_v26` / `convert_contour_to_primitives`）未修改

### 2026-08-13 文档更新 + ParamsPanel 参数范围修正

**文件**：`README.md` + `DEVELOPMENT_GUIDE.md`

**改动**：

- **README.md 更新**：新增「CAD 模型生成」核心功能说明，清晰描述 Foam 模式（自定义长宽高 + 圆角）和 Gridfinity 模式（42mm 标准网格 + 磁吸孔）的能力
- **DEVELOPMENT_GUIDE.md 参数范围修正**：§4.2 Step 5 params 中的参数范围更新为与实际代码一致：
  - Foam 模式：长度 20-500mm、宽度 20-500mm、高度 5-200mm、圆角 0-50mm
  - Gridfinity 模式：网格数 1-10、高度 1-10u
  - 通用参数：嵌入深度 1-50mm、轮廓偏移 -5~10mm
- **验证**：`cd python_backend && python3 -c "from cad_engine import *; r = generate_insert(InsertParams(mode='foam', foam=BoxParams(200,150,20,5), primitives=[{'type':'polyline','points':[{'x':200,'y':200},{'x':600,'y':200},{'x':600,'y':800},{'x':200,'y':800},{'x':200,'y':200}]}], embed_depth=10)); print(f'Foam test: success={r.get(\"success\")}')"` → `Foam test: success=True`

### 2026-08-07 handleUpdateContour 语义修复

**文件**：`src/features/workspace/Workspace.tsx`

**改动**：

- **修复 `handleUpdateContour` 语义错误**：之前同时更新 `simplifiedPrimitives` 和 `currentPrimitives`，导致「更新轮廓」按钮错误地修改了简化基元计数（EditorPanel 显示的基元数量）。
- **修正后**：`handleUpdateContour` 仅更新 `currentPrimitives`（用于 Viewport 红色轮廓预览），不触碰 `simplifiedPrimitives`（仅由「抽稀基元化」按钮设置）。
