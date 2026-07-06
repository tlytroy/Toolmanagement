# Toolmanagement-web 开发指南

## 项目概述

Toolmanagement-web 是一个基于浏览器的工具轮廓扫描和 3D 收纳生成器。用户只需将工具平放在 A4/Letter 纸上俯拍上传，系统即可自动识别纸张、标定尺寸、AI 提取工具轮廓、配置嵌件参数，并一键导出 STL/STEP/DXF/SVG 等格式，用于 3D 打印或激光切割工具收纳嵌件。

## 依赖管理策略

### 当前依赖版本
项目目前已升级到兼容的最新版本组合，以确保使用最新的特性和安全修复。

### Fabric.js 依赖问题
- Fabric.js v5.x 自带 TypeScript 类型声明，不需要单独安装 `@types/fabric`
- 如果之前误装了 `@types/fabric`，请卸载：`npm uninstall @types/fabric`
- 确保 `tsconfig.json` 里没有强制要求该类型包

### OpenCV.js 集成说明
OpenCV 官方没有原生发布 npm 包，浏览器端通常用两种方式：
✅ 推荐做法：npm 包 `@techstark/opencv-js`（本项目采用）
- 基于官方 OpenCV 4.10~4.12 编译的 opencv.js + wasm，社区维护最活跃
- 带 TypeScript 类型声明，Vite / React 可直接用
- Vite 需排除预构建（避免把 wasm 打进 bundle），已在 `vite.config.ts` 中配置

### 最近的依赖升级
项目依赖已于 2026年7月6日 升级到以下版本：
- React & React DOM: 18.3.1 (从 18.2.0 升级)
- Vite: 5.4.21 (从 5.2.0 升级)
- TypeScript: 5.9.3 (从 5.2.2 升级)
- Fabric: 5.5.2 (从 5.3.0 升级)
- OpenCV.js (@techstark/opencv-js): 5.0.0-release.1 (从 4.12.0-release.1 升级)
- Three.js: 0.185.1 (从 0.154.0 升级)
- Zustand: 4.5.7 (从 4.5.2 升级)
- @vitejs/plugin-react: 4.7.0 (从 4.2.1 升级)
- @types/react: 18.3.31 (从 18.2.66 升级)
- @types/react-dom: 18.3.7 (从 18.2.22 升级)
- @types/three: 0.185.0 (从 0.154.0 升级)

### 依赖升级策略
1. **全面兼容性升级**：我们选择了一组经过验证可以良好协作的最新版本
2. **定期评估**：每季度评估一次是否有重要的安全更新或功能改进
3. **全面测试**：每次升级后都需要进行全面的测试，确保所有功能正常工作
4. **文档更新**：升级依赖后及时更新相关文档和配置文件

要检查当前有哪些依赖可以升级，可以运行：
```bash
npm outdated
```

要升级特定依赖，可以运行：
```bash
npm install package@latest
```

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

## 已实现的 OpenCV.js 功能

### PaperDetector 类

位于 `src/utils/PaperDetector.ts`，提供了以下功能：

1. **初始化 OpenCV.js**
   - 使用 `@techstark/opencv-js` npm 包
   - 自动异步加载 OpenCV 模块
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

### 校准页面改进

校准页面 (`src/features/calibration/CalibrationPage.tsx`) 已经过重大改进：

1. **现代化UI设计** - 使用网格布局和卡片设计
2. **自动纸张检测** - 一键自动检测纸张四角
3. **图像自适应缩放** - 图片自动缩放以适应显示区域
4. **纸张类型选择** - 支持A4、Letter、A5等标准纸张类型
5. **手动调整备用方案** - 自动检测失败时的手动调整选项
6. **实时角点显示** - 检测到的角点实时可视化显示
7. **尺寸标定信息** - 显示像素到毫米的转换比例

## 下一步开发计划

### 第一阶段：完善 OpenCV.js 集成
1. 优化纸张检测算法准确性
2. 实现真正可交互的手动调整功能
3. 添加更多错误处理和用户提示
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