# Toolmanagement-web - 工具轮廓扫描 & 3D 收纳生成器

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![React](https://img.shields.io/badge/react-19+-blue.svg)
![TypeScript](https://img.shields.io/badge/typescript-6+-blue.svg)

## 项目简介

Toolmanagement-web 是一个基于浏览器的工具轮廓扫描和 3D 收纳生成器。用户只需将工具平放在 A4/Letter 纸上俯拍上传，系统即可自动识别纸张、标定尺寸、AI 提取工具轮廓、配置嵌件参数，并一键导出 STL 格式，用于 3D 打印工具收纳嵌件。

**架构**：Python FastAPI 后端负责所有图像处理（纸张检测、透视校正、轮廓提取、基元化）与 CAD 建模（trimesh + manifold3d），React 前端负责交互与可视化。

## 核心功能

1. **6 步工作流（单屏 Workspace 内完成）**
   - 上传照片
   - 纸张检测与标定
   - 工具轮廓提取（v26 传统 CV 四路径并集）
   - 轮廓编辑与参数配置（原生 Canvas 编辑器）
   - CAD 参数配置（Foam / Gridfinity 双模式）
   - **3D 预览与 STL 导出** 🎯

2. **CAD 模型生成（根据工具轮廓自动生成收纳嵌件）**
   - **Foam 模式**：自定义底座长宽高 + 圆角半径，工具轮廓自动布尔减形成工具槽
   - **Gridfinity 模式**：42mm 标准网格，自定义网格数/高度，可选磁吸孔
   - 工具轮廓偏移容差可调，嵌入深度可调
   - STL 格式导出，直接用于 3D 打印

3. **核心技术集成**
   - Python OpenCV：纸张检测与透视校正、工具轮廓提取、轮廓基元化（曲率分段 line/arc 拟合）
   - 原生 Canvas：蒙版编辑（画笔/橡皮/形状工具）
   - Three.js：3D 预览（STL 加载 + OrbitControls + 自动旋转）
   - trimesh + manifold3d + shapely：后端 CAD 建模引擎
   - Zustand：状态管理

4. **多格式导出**
   - STL：直接切片 3D 打印（已实现）
   - SVG/PDF：待实现

## 目标用户

- 3D 打印爱好者 / Maker
- 工厂车间工具管理（5S / Kaizen 泡沫嵌件）
- Gridfinity 收纳系统用户

## 技术栈

- **前端框架**：React 19 + TypeScript 6 + Vite 8
- **状态管理**：Zustand 5
- **画布编辑**：原生 Canvas 3 层架构（display/preview/interaction）
- **3D 渲染**：Three.js 0.185（STLLoader + OrbitControls）
- **样式框架**：Tailwind CSS 3
- **后端框架**：FastAPI + uvicorn (:8001)
- **图像处理**：OpenCV 4.9 (cv2)
- **CAD 建模**：trimesh + manifold3d + shapely
- **后端依赖**：numpy, pillow, python-multipart

## 快速开始

### 环境要求

- Node.js 18+
- npm 8+
- Python 3.9+

### 安装依赖

```bash
# 前端
npm install

# 后端
cd python_backend
pip install -r requirements.txt
cd ..
```

### 启动开发服务器

```bash
# 终端 1：启动后端（端口 8001）
cd python_backend && uvicorn main:app --host 0.0.0.0 --port 8001 --reload

# 终端 2：启动前端（端口 5173）
npm run dev
```

访问 http://localhost:5173 查看应用。

### 构建生产版本

```bash
npm run build
```

## 项目结构

```
src/
├── app/
│   └── store.ts              # Zustand 全局状态（step/imageUrl/primitives/CADParams/CADResult）
├── api/
│   └── toolProcessor.ts      # 后端 API 调用封装（6 个端点）
├── components/
│   └── ui/                   # 共享 UI 组件（Button/Card/Badge/icons 等）
├── features/
│   ├── workspace/            # 工作区外壳（Workspace/TopBar/LeftRail/Viewport/PlanningPanel）
│   ├── upload/               # 上传面板
│   ├── calibration/          # 纸张校准面板
│   ├── segmentation/         # 轮廓提取面板
│   ├── editor/               # 蒙版编辑器（MaskEditor）+ 编辑面板
│   ├── params/               # 参数配置面板（Foam/Gridfinity 双模式）
│   └── export/               # 导出面板（STL 下载 + 模型摘要 + 3D 预览）
├── pages/
│   └── Home.tsx              # 入口页面
├── utils/
│   └── types.ts              # 类型定义（Point/Primitive/CADParams/CADResult 等）
├── index.css                 # Tailwind 全局样式
└── main.tsx                  # ReactDOM 入口

python_backend/
├── main.py                   # FastAPI 服务（6 个端点，含 curvature-based 基元化算法）
├── cad_engine.py             # ★ CAD 引擎：Foam 嵌件 + Gridfinity 基座 3D 建模
├── latest_paper_detection.py # 纸张检测（代理 robust_paper_detector）
├── sam_tool_contour.py       # v26 工具轮廓提取
├── requirements.txt          # Python 依赖
└── __init__.py

reference/                    # 算法参考实现（纯净备份）
├── pkg_paper_detection/      # 纸张检测参考
├── tool_contour/             # 工具轮廓检测参考
└── contour_simplify/         # 轮廓基元化参考
```

## 开发路线图

### 已完成 ✅

- Web 项目骨架搭建
- 单屏 Workspace 布局（Linear 风顶栏 + 左侧工具栏 + 深色画布 + 右侧玻璃面板）
- 图片上传功能
- **Python 后端 FastAPI 服务**（6 个端点）
- **纸张检测**：三方法族多参数电池 + 加权共识判定 ✅
- **透视校正**：自动识别 A4 纸四角并校正 ✅
- **工具轮廓提取**：v26 传统 CV 四路径并集（LAB 暗区+BlackHat+Canny 桥接+方案 A）✅
- **轮廓基元化**：曲率分段法（compute_curvature → segment_by_curvature → fit_arc_robust / subdivide_polyline）✅
- **蒙版编辑器**：原生 Canvas 三层架构，画笔/橡皮/形状工具（直线/折线/矩形/椭圆），抖动修正 ✅
- **双按钮分离**：「更新轮廓」（快速预览）和「抽稀基元化」（慢速 line/arc 拟合）✅
- **检测失败处理**：失败时显示「手动绘制」/「重新上传」选项 ✅
- **设计系统重构**：brand 主色、canvas 深色面板、玻璃态浮层、自绘 SVG 图标 ✅
- **CAD 引擎**：trimesh + manifold3d + shapely，Foam/Gridfinity 双模式 ✅
- **3D 预览**：Three.js STLLoader + OrbitControls + 自动旋转 ✅
- **STL 导出**：后端生成 → base64 → 前端下载 ✅

### 近期计划 🚀

1. **撤销/重做**：MaskEditor 支持 Ctrl+Z/Y 撤销重做
2. **控制点拖拽**：在基元上显示可拖拽控制点，手动微调轮廓
3. **多工具排版**：MaxRects 自动排版 + 手动拖拽
4. **手指槽生成**：自动 + 手动微调
5. **多格式导出**：STEP/3MF/DXF/SVG/PDF
6. **画廊 / 历史记录**：本地保存设计历史
7. **清理无用 npm 包**：opencv-js / minisam / onnxruntime-web

## API 端点

| 端点                 | 方法 | 说明                                     |
| -------------------- | ---- | ---------------------------------------- |
| `/detect-paper`      | POST | 上传图片，检测 A4 纸四角并透视校正       |
| `/extract-contours`  | POST | 提取工具轮廓（v26 传统 CV）              |
| `/extract-tool-mask` | POST | 提取工具蒙版                             |
| `/update-contour`    | POST | 从蒙版提取原始轮廓（快速预览）           |
| `/simplify-contours` | POST | 轮廓抽稀基元化（曲率分段 line/arc 拟合） |
| `/generate-cad`      | POST | 生成 3D 模型（STL base64）               |

## 参考资源

- `PRODUCT_REQUIREMENTS.md` - 全量需求文档（功能清单 & 阶段规划）
- `DEVELOPMENT_GUIDE.md` - 开发指南（架构、文件结构、API 规范、开发约定）
- `OPENCV_INTEGRATION.md` - OpenCV 集成指南
- `reference/` - 算法参考实现（纯净备份）
