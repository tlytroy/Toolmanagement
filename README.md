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
   - OpenCV.js：纸张检测与透视校正
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
- **计算机视觉**：OpenCV.js (WASM)
- **AI 分割**：SAM ONNX (浏览器端运行)
- **矢量处理**：Clipper.js
- **3D 渲染**：Three.js
- **3D 建模**：OpenCASCADE WASM
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
├── workers/       # Web Worker（待实现）
└── main.tsx       # 应用入口
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
- **纸张检测功能完善**：多策略检测、调试信息、失败诊断 ✅
- **校准页面实现**：自动检测、手动调整、尺寸标定 ✅

### 近期计划 🚀

1. **SAM 分割集成**：替换假轮廓，实现 AI 工具轮廓提取
2. **Clipper.js 轮廓偏移**：实现真实的轮廓偏移功能
3. **3D 建模与导出**：集成 OpenCASCADE 实现真实的 3D 模型生成

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

### 功能特性

- **多策略检测**：提高不同光照和背景条件下的检测成功率
- **调试信息**：显示每种策略的中间结果图像
- **失败诊断**：提供具体的失败原因和改进建议
- **手动调整**：拖拽角点进行精确调整
- **尺寸标定**：自动计算像素到毫米的比例

### 算法改进

我们的 PaperDetector.ts 实现采用了重写后的健壮算法：

1. **多策略图像分割**：
   - Otsu阈值法：适用于高对比度图像
   - 自适应阈值法（GAUSSIAN和MEAN）：适用于光照不均匀场景
   - Canny边缘检测（低阈值和中阈值）：适用于复杂背景
   - CLAHE增强+自适应阈值：适用于低对比度图像

2. **鲁棒的四边形检测**：
   - 不再严格要求矩形，接受透视变形的凸四边形
   - 多epsilon逼近策略，提高检测成功率
   - 角度约束（40°-140°），过滤不合理形状

3. **智能评分机制**：
   - 面积得分：优先选择大面积轮廓
   - 形状规则性得分：角度接近90°、边长均匀的形状得分更高
   - 综合评分选出最优候选

4. **性能优化**：
   - 图像预处理优化：自适应缩放提升处理速度
   - 内存管理：及时释放OpenCV资源
   - 早期终止：找到高质量结果后提前结束后续策略

## 依赖版本管理

为了确保项目的稳定性和兼容性，我们定期更新依赖到最新的稳定版本。当前使用的版本：

- React & React DOM: 19.2.7
- Vite: 8.1.3
- TypeScript: 6.0.3
- Fabric: 7.4.0
- OpenCV.js (@techstark/opencv-js): 5.0.0-release.1
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

## 许可证

本项目采用 MIT 许可证。详情请见 [LICENSE](LICENSE) 文件。

## 致谢

- [OpenCV.js](https://docs.opencv.org/4.5.0/d5/d10/tutorial_js_root.html)
- [Segment Anything Model (SAM)](https://github.com/facebookresearch/segment-anything)
- [OpenCASCADE](https://www.opencascade.com/)
- [Fabric.js](http://fabricjs.com/)
- [Three.js](https://threejs.org/)