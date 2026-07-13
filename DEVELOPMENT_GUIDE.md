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
│                    ↓ API 调用                   │
├──────────────────────────────────────────────┤
│        Python Backend (FastAPI :8001)          │
│  /detect-paper  /extract-contours               │
│  /extract-tool-mask  /update-contour            │
│  /simplify-contours                             │
│                    ↓                            │
│         算法模块 (纯 OpenCV, 无 SAM)            │
│  latest_paper_detection.py                     │
│  sam_tool_contour.py (v26 轮廓)                │
│  contour_simplify.py (reference, 待接入)       │
└──────────────────────────────────────────────┘
```

### 1.2 前端技术栈

| 层 | 技术 |
|---|------|
| 框架 | React 19 + TypeScript 6 |
| 构建 | Vite 8 + TailwindCSS 3 |
| 状态 | Zustand 5 (`src/app/store.ts`) |
| 画布 | 原生 Canvas 3 层架构（display/preview/interaction），已移除 Fabric.js |
| 3D | Three.js 0.185（Viewport，待接入后端几何）|
| 已安装但暂未使用 | `@techstark/opencv-js`, `minisam`, `onnxruntime-web`（前端管线已移除，后续清理） |

### 1.3 后端技术栈

| 层 | 技术 |
|---|------|
| 框架 | FastAPI + uvicorn (:8001) |
| 图像处理 | OpenCV 4.9 (cv2) |
| 依赖 | numpy, pillow, python-multipart |
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
│   └── store.ts                      # Zustand 全局状态（step/imageUrl/primitives）
│
├── api/
│   └── toolProcessor.ts              # 所有后端 API 调用封装
│       detectPaper(file)             → POST /detect-paper
│       extractContours(file)         → POST /extract-contours
│       extractToolMask(file)         → POST /extract-tool-mask
│       updateContour(maskData)       → POST /update-contour
│       simplifyContours(maskData)    → POST /simplify-contours
│       generate3DModel(primitives)   → POST /generate-3d（桩）
│
├── utils/
│   └── types.ts                      # Primitive/Point/LinePrimitive 等类型定义
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
    │   ├── Viewport.tsx              # 中央画布：显示原图/校正图/蒙版叠加
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
    │   └── ParamsPanel.tsx           # 参数配置步骤（规划中占位）
    │
    └── export/
        └── ExportPanel.tsx           # 导出步骤（规划中占位）
```

### 2.2 后端 `python_backend/`

```
python_backend/
├── main.py                           # FastAPI 应用入口（4 个 API 端点）
├── requirements.txt                  # fastapi, uvicorn, opencv-python, numpy 等
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
  "mask_image": "data:image/jpeg;base64,..."  // 二值蒙版（工具区域=255，背景=0）
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
3. DP 抽稀（`cv2.approxPolyDP`, epsilon=0.004×周长） → 逐段 直线/圆弧/折线 拟合（最小二乘）

**实现来源**：`reference/contour_simplify/pkg_contour_simplify_primitives/contour_simplify.py` 的完整算法，已正确接入 `main.py`（2026-07-10）。

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

- `ParamsPanel.tsx`：规划中占位。未来支持底板厚度、嵌入深度、轮廓偏移、倒角。

#### Step 6: export — 导出文件

- `ExportPanel.tsx`：规划中占位。未来支持 STL/STEP/SVG/PDF 导出。

### 4.3 Viewport（中央画布）

- 无图片时：显示拖放上传区域
- editor 模式：显示 `warpedUrl`（校正图），叠加红色轮廓线（从 `currentPrimitives` 实时绘制 line/arc/polyline）
- 其他模式：显示 `warpedUrl`（校正图），可选叠加 `maskUrl`（蒙版，multiply 混合）
- 底部工具条：缩放、适应窗口、网格切换
- 左上角阶段指示器

### 4.4 全局状态 (Zustand store)

```typescript
// src/app/store.ts
step: Step          // 当前步骤
imageUrl: string    // 原始上传图片
calibratedImageUrl  // 校正后图片（较少使用，Workspace 本地管理 warpedUrl）
contours: any[]     // 原始轮廓（较少使用）
samMask: any        // SAM 掩膜（已废弃）
primitives: Primitive[] // 基元化结果
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

| 参数 | 值 | 说明 |
|------|-----|------|
| 闭运算核大小 | `max(5, int(min(h,w)*0.012))\|1` | 约 1.2% 最小边长 |
| 阴影 L 阈值 | `pL * 0.80` | 比纸暗 80% |
| 阴影 ab 容差 | `13` | ab 通道差值 |
| 轮廓平滑 sigma | `2.0` | 环形高斯 |
| 最小面积过滤 | `h*w*0.005` | 0.5% 图像面积 |
| 边框裁剪 | `max(3, int(min(h,w)*0.02))` | 2% 边距 |

### 5.4 已知局限

- **浅色/银色工具**在低对比度场景下，路径 A（Otsu）可能漏检工具中心区域
- **阴影区工具边缘**可能被 `shadow_mask` 误判切除，依赖 `protect` 区的膨胀保护
- **复杂形状（尖嘴钳、卡尺）**的薄边缘可能未完全捕获
- 算法无 SAM 语义补全，完全依赖传统 CV 手段

---

## 六、开发约定

### 6.1 前端

- **图标**：只使用 `src/components/ui/icons.tsx` 中定义的 27 个自绘 SVG 图标，不引入图标库。新增图标在该文件添加。
- **样式**：TailwindCSS 优先，不使用内联 style 除非动画/transform 等 CSS-in-JS 场景。颜色使用项目 design tokens（`brand-600`/`brand-50` 等，在 `tailwind.config.js` 定义）。
- **组件**：可复用 UI 放 `src/components/ui/`，业务功能组件放 `src/features/{功能名}/`。
- **状态**：跨组件共享状态用 Zustand store，局部状态用 React useState/useCallback。
- **API 调用**：全部通过 `src/api/toolProcessor.ts` 封装，不在组件中直接写 fetch。

### 6.2 后端

- **新增端点**：在 `main.py` 添加路由函数，算法逻辑放在独立 `.py` 文件中。
- **算法迭代**：保留旧版本文件（如 `advanced_tool_contour.py`），新版本放在单独的文件中（如 `sam_tool_contour.py`），通过 import 接入 main.py。不在原文件上覆盖。
- **参考 vs 主线**：`reference/` 目录下的代码是算法备份和纯净参考，不直接在主线 API 中 import（`main.py` 的纸张检测除外——`latest_paper_detection.py` 是 wrapper，它 import reference 的算法实现）。如需使用 reference 中的算法，写在 `python_backend/` 下的 wrapper 文件中。

### 6.3 通用

- **调试**：Python 算法的调试单独写测试脚本在 `python_backend/` 目录下，不污染 `main.py` 端点逻辑。前端调试在浏览器 DevTools 进行。
- **根目录散落文件**：`.py`/`.js`/`.html` 测试文件是历史遗留，不要在上面修改或新增。AI 不要引用或依赖这些文件。
- **npm 包**：`@techstark/opencv-js`、`minisam`、`onnxruntime-web` 已安装但前端管线已移除，后续可清理 package.json。

---

## 七、启动指南

### 7.1 后端

```bash
cd python_backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

验证：`curl http://localhost:8001/` → `{"message":"Tool Management Backend API"}`

### 7.2 前端

```bash
npm install
npm run dev
```

默认 `http://localhost:5173`，自动代理 API 到 `:8001`。

### 7.3 开发时的注意事项

- 后端必须先于前端启动，否则前端 API 调用会报网络错误
- 图片处理可能较慢（v26 轮廓提取涉及多次形态学操作），前端有 loading 状态处理
- 大图（>4000px）可能触发后端内存压力，建议前端先压缩

---

## 八、技术债务 & 待办

| 优先级 | 项 | 说明 |
|--------|-----|------|
| **P0** | MaskEditor 撤销/重做 | 用户手动画错无法回退 |
| P1 | MaskEditor 控制点拖拽 | 比画笔更精确的轮廓微调方式 |
| P1 | 清理无用 npm 包 | opencv-js / minisam / onnxruntime-web / fabric.js（已移除） |
| P1 | 清理 `src/types/opencv.d.ts` | OpenCV 类型声明已无用 |
| P2 | `optimized_paper_detection.py` 与 `latest_paper_detection.py` 功能重复 | 保留 latest，可删除 optimized |
| P2 | `optimized_contour_processing.py` 独立基元化 | 是否合并进 main.py 或 sam_tool_contour.py |
| P2 | ParamsPanel / ExportPanel | 规划中 → 实际实现 |
| P3 | 桌面化打包 | Tauri/Electron + Python 后端嵌入 |

---

## 附录：开发日志

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
