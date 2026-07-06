# Toolmanagement-web 开发指南

## 项目概述

Toolmanagement-web 是一个基于浏览器的工具轮廓扫描和 3D 收纳生成器。用户只需将工具平放在 A4/Letter 纸上俯拍上传，系统即可自动识别纸张、标定尺寸、AI 提取工具轮廓、配置嵌件参数，并一键导出 STL/STEP/DXF/SVG 等格式，用于 3D 打印或激光切割工具收纳嵌件。

## 当前实现状态

### 已完成的功能
1. ✅ 完整的6步向导UI界面
2. ✅ 图片上传功能
3. ✅ 步骤导航和状态管理
4. ✅ 基础的 Fabric.js SVG 编辑器
5. ✅ 参数配置面板
6. ✅ OpenCV.js 纸张检测功能（部分实现）

### 核心技术集成状态
1. ✅ OpenCV.js - 纸张检测与透视校正（正在进行）
2. ⬜ SAM (Segment Anything) - AI 工具轮廓提取
3. ⬜ Clipper.js - 轮廓偏移与布尔运算
4. ⬜ Three.js + OpenCASCADE - 3D 建模与渲染

## 测试图片

项目根目录下的 `testpic.jpg` 可用于测试所有功能。

## 如何测试当前功能

1. **启动开发服务器**
   ```bash
   npm run dev
   ```
   访问 http://localhost:5173

2. **测试基本流程**
   - 上传 `testpic.jpg`
   - 在纸张检测页面点击"自动检测纸张"
   - 导航到不同步骤查看界面

3. **测试 OpenCV.js 功能**
   - 访问 http://localhost:5173/opencv-test.html 测试基本图像处理
   - 访问 http://localhost:5173/paper-detection-test.html 测试纸张检测

## 已实现的 OpenCV.js 功能

### PaperDetector 类

位于 `src/utils/PaperDetector.ts`，提供了以下功能：

1. **自动加载 OpenCV.js**
2. **纸张四角检测**
   - 边缘检测
   - 轮廓查找
   - 四边形拟合
   - 角点排序
3. **透视校正**
   - 应用透视变换
   - 生成校正后图像
4. **尺寸标定**
   - 计算像素到毫米的比例

### 校准页面集成

校准页面 (`src/features/calibration/CalibrationPage.tsx`) 已集成真实的 OpenCV.js 功能：

1. 自动检测纸张四角
2. 应用透视校正
3. 显示检测到的角点标记
4. 计算并显示像素比例

## 下一步开发计划

### 第一阶段：完善 OpenCV.js 集成
1. 优化纸张检测算法准确性
2. 实现手动调整角点功能
3. 添加错误处理和用户提示
4. 优化性能和内存管理

### 第二阶段：SAM 分割集成
1. 集成 SAM ONNX 模型
2. 实现点击生成掩码功能
3. 轮廓提取和优化
4. 模型缓存机制

### 第三阶段：轮廓处理功能
1. 集成 Clipper.js
2. 实现轮廓偏移功能
3. 轮廓编辑和优化工具

### 第四阶段：3D 建模和导出
1. 集成 Three.js 和 OpenCASCADE
2. 实现 3D 预览功能
3. 多格式导出功能

## 项目结构

```
src/
├── app/           # 全局状态管理 (Zustand)
├── components/    # 公共组件
├── features/      # 功能模块
│   ├── upload/    # 上传功能
│   ├── calibration/ # 纸张检测与标定
│   ├── segmentation/ # AI 分割
│   ├── editor/    # 轮廓编辑
│   ├── params/    # 参数配置
│   └── export/    # 导出功能
├── utils/         # 工具函数
└── pages/         # 页面组件
```

## 开发资源

- OpenCV.js 文档: https://docs.opencv.org/
- SAM (Segment Anything): https://github.com/facebookresearch/segment-anything
- Fabric.js: http://fabricjs.com/
- Three.js: https://threejs.org/