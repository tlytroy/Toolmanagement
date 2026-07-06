# Toolmanagement-web - 工具轮廓扫描 & 3D 收纳生成器

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![React](https://img.shields.io/badge/react-18+-blue.svg)
![TypeScript](https://img.shields.io/badge/typescript-5+-blue.svg)

## 项目简介

Tooltrace-web 是一个基于浏览器的工具轮廓扫描和 3D 收纳生成器。用户只需将工具平放在 A4/Letter 纸上俯拍上传，系统即可自动识别纸张、标定尺寸、AI 提取工具轮廓、配置嵌件参数，并一键导出 STL/STEP/DXF/SVG 等格式，用于 3D 打印或激光切割工具收纳嵌件。

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

- **前端框架**：React 18 + TypeScript + Vite
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

- Node.js 16+
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
├── workers/       # Web Worker（待实现）
└── main.tsx       # 应用入口
```

## 开发路线图

### 已完成 ✅

- Web 项目骨架搭建
- 6 步向导 UI 实现
- 图片上传功能
- Fabric.js SVG 编辑器
- 参数面板
- 状态管理

### 近期计划 🚀

1. **OpenCV.js 集成**：实现真实的纸张检测与透视校正
2. **SAM 分割集成**：替换假轮廓，实现 AI 工具轮廓提取
3. **Clipper.js 轮廓偏移**：实现真实的轮廓偏移功能
4. **3D 建模与导出**：集成 OpenCASCADE 实现真实的 3D 模型生成

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