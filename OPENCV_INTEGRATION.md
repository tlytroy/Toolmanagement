# OpenCV.js 集成开发指南

## 当前状态

OpenCV.js 已经成功集成并实现了完整的纸张检测功能。我们创建了专门的测试页面来验证基本功能，并且功能已经完全集成到主应用的校准页面中。

## 核心功能实现

### 1. 纸张检测功能

已实现以下核心功能：
- 多策略图像分割（Otsu阈值、自适应阈值、Canny边缘检测等）
- 凸四边形检测（不要求严格矩形，适应透视变形）
- 形状规则性评分（角度和边长方差评估）
- 角点排序（左上→右上→右下→左下）
- 透视校正
- 纸张尺寸标定

### 2. 调试和错误处理

- 详细的调试信息输出（每种策略的中间结果图像）
- 具体的失败原因诊断和用户提示
- 内存管理和资源释放

## 测试方法

1. 访问 http://localhost:5173/opencv-test.html 或通过主应用中的"OpenCV Test"按钮进入测试页面
2. 上传测试图片或加载默认测试图片
3. 使用按钮测试不同的图像处理功能
4. 查看检测结果和校正后的图像

## 集成到主应用

OpenCV.js 功能已完全集成到校准页面中：
- 自动检测纸张四角（多策略并行处理）
- 手动调整功能（拖拽角点）
- 透视校正处理
- 尺寸标定计算
- 用户友好的界面和错误提示
- 详细的调试信息显示
- 失败原因诊断和改进建议

## 性能优化

1. 图像预处理（缩放）以提高处理速度
2. 及时释放 OpenCV 资源避免内存泄漏
3. 更高效的算法实现

## OpenCV.js 使用注意事项

1. OpenCV.js 是一个大型库，加载时间较长
2. 需要注意内存管理，及时释放 Mat 对象
3. 某些功能可能需要 wasm 支持
4. 在复杂计算时考虑使用 Web Worker 避免阻塞 UI

## 依赖版本管理

当前使用的是最新稳定版本的 @techstark/opencv-js (^5.0.0-release.1)，确保了功能完整性和性能。

## OpenCV.js 加载机制（重要）

> ⚠️ 本节是 2026-07-07 修订后的**唯一正确**加载方式，旧的 `import('@techstark/opencv-js')` / `window.cv = cv` 模式已被废弃，详见 [DEVELOPMENT_GUIDE.md §二.6](DEVELOPMENT_GUIDE.md)。

### 加载链路

```
index.html
  └─ <script src="/opencv.js">           ← 经典脚本，UMD 挂 window.cv
        └─ window.cv = cv(Module)         ← cv 是 async 函数 → window.cv 是 Promise

src/lib/opencvLoader.ts#loadCv()
  └─ 轮询 window.cv
  └─ 展平嵌套 Promise（UMD 包装会套 1~2 层）
  └─ 校验 cv.imread 存在

src/hooks/useOpenCV.ts
  └─ 调用 loadCv()，返回 { cv, loaded, error }

业务组件（如 CalibrationPage）
  └─ import { useOpenCV } from '@/hooks/useOpenCV'
  └─ 拿到 cv 实例，调用 cv.imread() / cv.Mat 等
```

### 关键文件

| 文件 | 角色 |
|------|------|
| `public/opencv.js` | 13MB UMD，wasm 内嵌，从 `node_modules/@techstark/opencv-js/dist/opencv.js` 复制 |
| `src/lib/opencvLoader.ts` | 共享的 `loadCv()` 函数（轮询 + 展平） |
| `src/hooks/useOpenCV.ts` | React hook，调用 `loadCv()` |
| `index.html` | 在 module 脚本**之前**加 `<script src="/opencv.js">` |
| `vite.config.ts` | **不要**加 `optimizeDeps.exclude`（已不再 import 该包） |

### 严禁事项

- ❌ `import cvReadyPromise from '@techstark/opencv-js'`（静态 import）
- ❌ `await import('@techstark/opencv-js')`（动态 import，Vite dev 卡死）
- ❌ 在组件里直接 `import "@techstark/opencv-js"`（同样卡死）
- ❌ 假设 `window.cv` 是同步对象（实际是 Promise，必须 await）
- ❌ 假设 `window.cv` resolve 一次就是 Module（可能嵌套 Promise，需展平）

### 故障排查

| 现象 | 原因 | 解决 |
|------|------|------|
| 白屏 | 静态 import 卡死 Vite | 改用 `<script>` 标签 |
| 永远"加载OpenCV中..." | 动态 import 卡死 Vite | 同上，**先** `rm -rf node_modules/.vite` |
| `window.cv is undefined` | `<script>` 加载顺序错 | 把 `<script src="/opencv.js">` 放在 `<script type="module">` 之前 |
| `cv.imread is not a function` | Promise 没展平 | 用 `loadCv()`，不要手写 await |

### 复用模式

新增 detector（如 `MyNewDetector.ts`）时：

```typescript
import type { Point } from "./types";
import { loadCv } from "@/lib/opencvLoader";

let cv: any = null;
async function getCV() {
  if (!cv) cv = await loadCv();
  return cv;
}

export class MyNewDetector {
  async detect(image: HTMLImageElement): Promise<Point[] | null> {
    const cv = await getCV();
    // ... 使用 cv.imread / cv.Mat 等
  }
}
```

不要在多个文件里复制粘贴"轮询 window.cv + 展平 Promise"的代码——一律走 `loadCv()`。

## 参考资源

- OpenCV.js 官方文档
- @techstark/opencv-js npm 包文档
- 相关教程和示例代码
