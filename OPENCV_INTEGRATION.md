# OpenCV 集成开发指南

## 当前状态

OpenCV.js 前端管线已全部移除。当前架构为 **Python FastAPI 后端 + React 前端**。

所有图像处理（纸张检测、透视校正、轮廓提取、基元化）均在 Python 端完成，前端仅负责文件上传、API 调用、结果显示和手动编辑。CAD 建模（trimesh + manifold3d）也在 Python 后端完成。

## 架构

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

## 核心功能实现

### 1. 纸张检测（Python 后端）

- **文件**：`python_backend/latest_paper_detection.py`（代理 `reference/pkg_paper_detection/robust_paper_detector.py`）
- **端点**：`POST /detect-paper`
- **算法**：三方法族多参数电池 + 加权共识判定
  - **亮度先验为主**：A4 白纸在深色桌面上是最亮的连通区域
  - **三重打分择优**：`比例(1.414)×0.4 + 直角(90°)×0.3 + 亮度覆盖×0.3`
  - **正反都试 + 边缘兜底**：Otsu / 自适应阈值各取正反两个 mask，再加 Canny 边缘兜底
- **返回**：四角坐标 + 透视校正后的 warped 图像（base64）

### 2. 工具轮廓提取（Python 后端）

- **文件**：`python_backend/sam_tool_contour.py`（v26 传统 CV 四路径并集）
- **端点**：`POST /extract-contours`
- **算法管线**：
  1. 四策略并集（LAB 暗区 + BlackHat + Canny 桥接 + 方案 A）
  2. 开运算(3)去噪
  3. 梯度阴影剥离
  4. 孔洞填充
  5. 最大连通块填充 + dilate(7)
  6. 环形高斯平滑 (sigma=2.0)
- **特点**：不依赖 SAM / torch，CPU 单图毫秒级
- **返回**：轮廓点 + 调试图像

### 3. 轮廓基元化（Python 后端）

- **文件**：`python_backend/main.py`（内联 curvature-based 算法）
- **端点**：`POST /simplify-contours`
- **算法管线**：
  1. `_compute_curvature`：一阶差分曲率 sin(θ)
  2. `_segment_by_curvature`：形态学侵蚀/膨胀分段
  3. `_fit_arc_robust`：cv2.fitEllipse + 圆度/跨度/误差校验
  4. `_subdivide_polyline`：大半径缓弯退化为 DP 折线
- **参数自适应**：max_radius = img_diag × 0.03，curv_thresh = clamp(0.02, 0.05, 50/img_diag)
- **返回**：line/arc/polyline 基元列表

### 4. 蒙版更新（快速预览）

- **端点**：`POST /update-contour`
- **功能**：从蒙版中提取原始轮廓（不抽稀、不基元化），返回 polyline 供前端快速预览
- **用途**：用户反复编辑蒙版时实时查看边界变化

### 5. CAD 建模引擎（Python 后端）

- **文件**：`python_backend/cad_engine.py`
- **端点**：`POST /generate-cad`
- **依赖**：trimesh + manifold3d + shapely
- **功能**：
  - 基元（line/arc/polyline）→ 2D 多边形 → 3D 拉伸
  - Foam 模式：自定义长宽高 + 圆角的方盒嵌件
  - Gridfinity 模式：42mm 标准网格基底（带磁吸孔）
  - 工具槽布尔减：轮廓偏移 → 拉伸 → 从基底减去
- **返回**：STL base64 + 模型摘要（顶点/面/体积/范围）

## 启动方式

```bash
# 后端（端口 8001）
cd python_backend && uvicorn main:app --host 0.0.0.0 --port 8001 --reload

# 前端（端口 5173）
npm run dev
```

## API 端点一览

| 端点                 | 方法 | 输入                       | 输出                                               |
| -------------------- | ---- | -------------------------- | -------------------------------------------------- |
| `/detect-paper`      | POST | 图片文件 (multipart)       | corners, warped_image, confidence, skew            |
| `/extract-contours`  | POST | 图片文件 (multipart)       | primitives, debug_image, summary                   |
| `/extract-tool-mask` | POST | 图片文件 (multipart)       | mask_image                                         |
| `/update-contour`    | POST | mask_image (base64 JSON)   | primitives (原始 polyline)                         |
| `/simplify-contours` | POST | mask_image (base64 JSON)   | primitives (line/arc/polyline), summary            |
| `/generate-cad`      | POST | primitives + params (JSON) | stl_base64, summary (vertices/faces/volume/bounds) |

## 参考资源

- `python_backend/main.py` — FastAPI 服务主入口
- `python_backend/cad_engine.py` — CAD 建模引擎
- `python_backend/latest_paper_detection.py` — 纸张检测代理模块
- `python_backend/sam_tool_contour.py` — v26 工具轮廓提取
- `reference/pkg_paper_detection/robust_paper_detector.py` — 纸张检测算法参考
- `reference/tool_contour/pkg_tool_contour_detection/repro_contour_v9.py` — v9 Fast 检测器参考
- `reference/contour_simplify/pkg_contour_simplify_primitives/` — 基元化算法参考
