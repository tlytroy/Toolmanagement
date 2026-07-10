# Toolmanagement-web - 工具轮廓扫描 & 3D 收纳生成器

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![React](https://img.shields.io/badge/react-19+-blue.svg)
![TypeScript](https://img.shields.io/badge/typescript-6+-blue.svg)

## 项目简介

Toolmanagement-web 是一个基于浏览器的工具轮廓扫描和 3D 收纳生成器。用户只需将工具平放在 A4/Letter 纸上俯拍上传，系统即可自动识别纸张、标定尺寸、AI 提取工具轮廓、配置嵌件参数，并一键导出 STL/STEP/DXF/SVG 等格式，用于 3D 打印或激光切割工具收纳嵌件。

整个过程完全在浏览器中完成，无需安装任何软件，也无需上传图片到服务器，保护用户隐私。

## 核心功能

1. **6 步向导式操作界面**
   - 上传照片
   - 纸张检测与标定
   - AI 工具轮廓提取
   - 轮廓编辑与参数配置
   - 3D 预览
   - 多格式导出

2. **核心技术集成**
   - OpenCV.js：纸张检测与透视校正、工具轮廓基元化（直线/圆弧/折线提取）
   - SAM (Segment Anything)：AI 工具轮廓提取
   - Clipper.js：轮廓偏移与布尔运算
   - Three.js + OpenCASCADE：3D 建模与渲染

3. **多格式导出支持**
   - STL：直接切片 3D 打印
   - STEP：导入 CAD 软件二次编辑
   - 3MF：多色/多 Body 打印
   - DXF/SVG：激光切割

## 目标用户

- 3D 打印爱好者 / Maker
- 工厂车间工具管理（5S / Kaizen 泡沫嵌件）
- Gridfinity 收纳系统用户

## 技术栈

- **前端框架**：React 19 + TypeScript + Vite
- **状态管理**：Zustand
- **图形处理**：Fabric.js (SVG 编辑)
- **计算机视觉**：OpenCV.js (WASM) - 已集成
- **AI 分割**：SAM ONNX (浏览器端运行) - 模拟实现，待集成真实模型
- **矢量处理**：Clipper.js - 待集成
- **3D 渲染**：Three.js - 待集成
- **3D 建模**：OpenCASCADE WASM - 待集成
- **样式框架**：Tailwind CSS

## 快速开始

### 环境要求

- Node.js 18+
- npm 8+

### 安装依赖

```bash
npm install
```

### 启动开发服务器

```bash
npm run dev
```

访问 http://localhost:5173 查看应用。

> ⚠️ 如果你修改了 OpenCV 相关代码后出现卡死/白屏，请执行 `rm -rf node_modules/.vite` 后再启动。

### 构建生产版本

```bash
npm run build
```

## 项目结构

```
src/
├── app/           # 全局状态管理
├── components/    # 公共组件
├── features/      # 功能模块
├── pages/         # 页面组件
├── utils/         # 工具函数
├── hooks/         # React Hooks
├── lib/           # 核心工具库（opencvUtils, opencvLoader）
├── workers/       # Web Worker（待实现）
└── main.tsx       # 应用入口

public/
├── opencv.js      # OpenCV.js UMD（13MB，从 node_modules 复制，禁止 import 走 npm）
└── testpic.jpg    # 测试图片
```

## 开发路线图

### 已完成 ✅

- Web 项目骨架搭建 (toolmanagement-web)
- 6 步向导 UI 实现
- 图片上传功能
- Fabric.js SVG 编辑器
- 参数面板
- 状态管理
- **OpenCV.js 集成**：实现真实的纸张检测与透视校正 ✅
- **OpenCV.js 加载机制重构**（2026-07-07）：改用 `<script>` 标签 + `loadCv()`，解决 Vite dev 卡死 13MB CJS 文件问题 ✅
- **纸张检测功能完善**：多策略检测、调试信息、失败诊断 ✅
- **校准页面实现**：导入照片即自动识别 A4 纸四角、透视校正、尺寸标定 ✅
- **SAM 分割模拟**：实现基于假数据的分割页面与流程验证 ✅
- **工具轮廓基元化（曲率分段法）**：union(Fast∪SAM 接口) + 形态学 + Chaikin 平滑 + 曲率分段 line/arc 拟合（代数最小二乘圆拟合替代 minEnclosingCircle，避免 <180° 弧半径塌缩）；纯 JS 回归验证 10/10 通过 ✅

### 近期计划 🚀

1. **SAM 模型集成**：集成真实的 SAM ONNX 模型，实现 AI 工具轮廓提取（`abstractFromMask` 已预留 `samMask` 并集接口，当前走 Fast-only 路径）
2. **Clipper.js 轮廓偏移**：实现真实的轮廓偏移与布尔运算功能
3. **3D 建模与导出**：集成 OpenCASCADE 实现真实的 3D 模型生成
4. **Web Worker 优化**：将重计算任务（OpenCV、SAM、3D 建模）迁移到 Web Worker

## 纸张检测功能详情

### 核心算法

我们实现了先进的纸张检测算法，参考 CamScanner 等文档扫描应用：

1. **预处理**：灰度化 + 高斯模糊降噪
2. **多策略分割**：
   - Otsu 阈值分割
   - 自适应阈值分割（GAUSSIAN 和 MEAN）
   - Canny 边缘检测（多种阈值）
   - CLAHE 增强 + 自适应阈值
3. **轮廓查找** → 凸四边形拟合（不要求矩形，只要求凸+角度合理）
4. **选最佳候选**：面积大 + 形状规则
5. **角点排序** + 透视校正

### 检测算法

纸张检测已**全自动、无需手动调参**，统一实现在 `src/lib/opencvUtils.ts#detectPaperCorners`：

- 多策略自适应：Otsu 阈值、自适应阈值（GAUSSIAN / MEAN）、Canny 多阈值、CLAHE 增强
- 自动选取面积最大的合法凸四边形（接受透视变形，不要求严格矩形）
- 多 epsilon 逼近 + 内角约束（30°~150°）过滤不合理形状
- 用 `approx.data32S` 取点（**注意本构建 `approx.ptr(i,0)` 读 CV_32SC2 会错位**），四点按「左上→右上→右下→左下」排序后做透视校正
- 历史上散落的 `OptimizedPaperDetector` / `PaperDetector` 等重复实现已删除并合并进 `opencvUtils.ts`

### 功能特性

- **自动检测**：导入照片后自动识别 A4 纸，无需手动调参
- **多策略检测**：提高不同光照和背景条件下的检测成功率
- **失败诊断**：未识别时给出明确提示，可点击"重新检测"
- **尺寸标定**：自动计算像素到毫米的比例

## OpenCV.js 加载机制（重要）

> ⚠️ 详见 [OPENCV_INTEGRATION.md](OPENCV_INTEGRATION.md) 和 [DEVELOPMENT_GUIDE.md §二.6](DEVELOPMENT_GUIDE.md)。

**严禁**通过 npm 方式 `import('@techstark/opencv-js')` —— Vite dev 会因 13MB CJS 文件卡死。

**正确方式**：`public/opencv.js`（从 npm 包复制的 UMD）+ `<script>` 标签 + `src/lib/opencvLoader.ts#loadCv()`。

## 依赖版本管理

为了确保项目的稳定性和兼容性，我们定期更新依赖到最新的稳定版本。当前使用的版本：

- React & React DOM: 19.2.7
- Vite: 8.1.3
- TypeScript: 6.0.3
- Fabric: 7.4.0
- OpenCV.js (@techstark/opencv-js): 5.0.0-release.1（**仅在构建/复制时使用，运行时通过 public/opencv.js**）
- Three.js: 0.185.1
- Zustand: 5.0.14

我们会定期检查并更新依赖，确保使用最新的安全补丁和功能改进。详细信息请参阅 [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md) 中的依赖管理策略部分。

## 贡献指南

欢迎提交 Issue 和 Pull Request 来帮助改进项目。

### 开发原则

1. 前端优先：先用假数据把 UI/UX 跑通
2. 模块化：图像 / 矢量 / 3D 各自独立，后期替换实现
3. 渐进增强：每一步都能打开浏览器看到效果
4. 本地优先：所有重计算放 Web Worker，UI 不卡顿
5. 单一调试入口：OpenCV 相关调试只在 `src/features/calibration/CalibrationPage.tsx` 进行
6. 严禁 `import('@techstark/opencv-js')`：详见 OpenCV 加载机制

## 许可证

本项目采用 MIT 许可证。详情请见 [LICENSE](LICENSE) 文件。

## 八荣八耻

以暗猜接口为耻，以认真查阅为荣
以模糊执行为耻，以寻求确认为荣
以盲想业务为耻，以人类确认为荣
以创造接口为耻，以复用现有为荣
以跳过验证为耻，以主动测试为荣
以破坏架构为耻，以遵循规范为荣
以假装理解为耻，以诚实无知为菜
以盲目修改为耻，以谨慎重构为荣

## 致谢

- [OpenCV.js](https://docs.opencv.org/4.5.0/d5/d10/tutorial_js_root.html)
- [Segment Anything Model (SAM)](https://github.com/facebookresearch/segment-anything)
- [OpenCASCADE](https://www.opencascade.com/)
- [Fabric.js](http://fabricjs.com/)
- [Three.js](https://threejs.org/)

## UI 现代化更新日志

> ⚠️ **形态变更**：本站已于 2026-07-09 从「6 步向导（Stepper）」二次重构为 **Figma / Tooltrace 式单屏 workspace**（深色画布 + 浅色顶栏/侧栏 + 右侧浮动玻璃参数面板）。下文「设计系统重构·本次」及之后条目以 workspace 为准；更早的「全局设计系统升级 / Stepper 卡片式」等条目为向导形态历史，已被取代。

### 2026-07-09

#### 主要更新内容：

1. **全局设计系统升级**
   - 采用现代化渐变背景（从蓝色到靛蓝色的渐变）
   - 统一使用圆角设计（2xl 圆角）
   - 优化阴影层次，增强视觉深度
   - 全面响应式设计，适配各种屏幕尺寸

2. **Stepper 组件重设计**
   - 改为卡片式进度指示器，包含图标和状态
   - 实现步骤完成状态可视化（✅ 标记）
   - 添加平滑过渡动画
   - 禁用未完成步骤的点击
   - 优化移动端显示效果

3. **上传页面现代化**
   - 支持拖拽上传功能
   - 优化文件选择按钮样式
   - 重新设计拍摄指南，使用图标和卡片布局
   - 添加悬停效果和动画反馈

4. **校准页面 UI 升级**
   - 重新设计加载状态，添加进度条动画
   - 优化结果展示区域，使用彩色状态卡片
   - 重新布局操作按钮，使用图标和变体样式
   - 优化错误提示和警告信息的展示
   - 统一卡片式布局，增强视觉层次

5. **AI 分割页面重设计**
   - 优化图像展示区域，添加阴影和圆角
   - 重新设计进度条和处理状态
   - 美化选项面板，使用卡片和图标
   - 统一按钮样式和交互体验

6. **按钮组件系统升级**
   - 添加多种变体（primary, secondary, success, danger, outline）
   - 支持三种尺寸（sm, md, lg）
   - 优化悬停效果和阴影
   - 统一图标使用规范

#### 设计原则：

- **视觉层次清晰**：通过卡片、阴影、颜色区分不同层级
- **交互反馈明确**：所有操作都有即时视觉反馈
- **现代化美学**：采用当前流行的设计趋势，如渐变、圆角、卡片式布局
- **响应式适配**：确保在各种设备上都有良好的显示效果
- **无障碍设计**：合理的颜色对比度和状态提示

### 2026-07-09（设计系统重构 · 本次）

> 此前页面虽接了 Tailwind，但设计语言不统一（有的用 `brand`、有的用裸 `blue-*`、灰卡 `bg-gray-100`、emoji 堆砌）；未实现的分割/编辑/导出页还是早期 demo 风（裸 `<input>`、假矩形假坐标）。本次重做统一设计系统。

#### 设计令牌（tailwind.config.js）
- `brand` 蓝/靛色板（50–900）为全站唯一主色，**禁止再裸写 `blue-*`**。
- `shadow-card` / `shadow-card-hover` 柔和阴影；`rounded-2xl/3xl`；`animate-fade-in` 入场动画。
- `src/index.css` 新增 `.bg-app` 极淡斜向渐变背景（浅色 chrome 区用）；新增 `.canvas-grid`（深色画布点阵）、`.glass-panel`/`.glass-bar`（玻璃态浮层）、`.canvas-scroll`（深色细滚动条）。
- `tailwind.config.js` 的 `theme.extend.colors` 新增 `canvas`（950/900/850/800/700/600）作为深色画布与面板基调；`animate-slide-in-right`/`slide-down` 面板入场动画。

#### 共享组件库（src/components/ui/，零新依赖）
- `icons.tsx`：自绘 SVG 图标集（lucide 风格、`currentColor`），**当前不引入图标库**，避免你那边多装包。
  - 计划图标库为 **lucide-react**（用户指定栈：Shadcn/ui + Tailwind + Lucide）。本沙箱 WSL 文件系统 npm 安装存在 `ENOTEMPTY` 重命名冲突，无法在此装；你 WSL 内 `npm i lucide-react` 后，把 `icons.tsx` 的各处 `<Icon name=... />` 换为 lucide 组件即可，视觉等价。
- `Card`：统一卡片（可选标题/图标/副标题/操作区）。
- `Badge`：状态徽章（default/brand/success/warning/danger/info）。
- `Button`：统一按钮（primary/secondary/success/danger/outline/ghost + sm/md/lg），主色改 `brand`。
- `SectionHeading`：页头（eyebrow + 标题 + 描述）。
- `EmptyState`：空 / 规划中占位。

#### 应用外壳（单屏 workspace，取代 6 步向导）
- `pages/Home.tsx`：仅渲染 `<Workspace />`。
- `src/features/workspace/Workspace.tsx`（**唯一外壳**，新增）：浅色顶栏（Linear 风）+ 左侧工具栏（浅色、可收起 `w-16`↔`w-56`）+ 中央深色画布 viewport（`bg-canvas-950` + `.canvas-grid`）+ 右侧浮动玻璃参数面板（`glass-panel`，绝对定位浮于画布右上，不挤占画布）。`store.step` 驱动左侧激活态与右侧面板内容。
- 已删除 `components/Stepper.tsx`、`features/upload/UploadPage.tsx`、`features/calibration/CalibrationPage.tsx` 及分割/编辑/参数/导出页（逻辑并入 Workspace，未实现功能改为右侧「规划中」卡片）。

#### 页面状态（workspace 内）
- **已实现并打磨**：上传（画布内拖拽/点击）→ 自动识别纸张 → 透视校正 → 提取轮廓 → 基元化，全部在 `Workspace` 内完成，`opencvUtils` 调用逻辑零改动。
- **未实现 → 右侧面板「规划中」卡片**（避免假 demo 误导）：`AI 轮廓精修`（SAM 语义分割补全遮挡）、`矢量轮廓编辑器`、`参数配置`（底板/腔体厚度与偏移）、`导出`（STL/SVG/PDF/Gridfinity）。
- **3D 预览区**：中央画布左下角玻璃占位「3D 预览区·后端几何待接入」，待 §七 后端引擎接入后替换为真实 Three.js viewport。

#### 验证
- `tsc --noEmit` 退出码 0（strict + noUnusedLocals/Parameters）。
- `vite build` 通过（CSS 19KB = Tailwind 正常编译）。
- 顺带修复两处原有编译阻塞：`src/vite-env.d.ts` 缺失（CSS 导入报错）、`src/lib/samInference.ts` 错把 `RawSamMask` 写成 `@/utils/opencvUtils`（应为 `@/lib/opencvUtils`）。
- 注：本环境 `tailwindcss`/`autoprefixer` 此前未真正装进 node_modules，已补装，`npm run dev` 可直接起。
