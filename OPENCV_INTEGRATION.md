# OpenCV.js 集成开发指南

## 当前状态

OpenCV.js 已通过 `<script>` 标签集成（`public/opencv.js` 挂载到 `window.cv`），并实现了完整的纸张检测功能。纸张检测已全部集中在 `src/lib/opencvUtils.ts#detectPaperCorners`（全自动、无参数），功能完全集成到主应用的校准页面中：导入图片即自动识别，无需手动调参。

## 核心功能实现

### 1. 纸张检测功能

已实现以下核心功能：
- **三方法族多参数电池 + 加权共识判定**（详见下文 §1.1）
- 凸四边形检测（不要求严格矩形，适应透视变形，横竖屏通用）
- 角度偏斜评估与提醒（视角过偏时警告用户重拍，避免工具抠图变形）
- 角点排序（左上→右上→右下→左下）
- 透视校正（输出自动跟随检测方向：横拍→横 A4，竖拍→竖 A4）
- 纸张尺寸标定（A4 长边 = 297mm → scaleMmPerPx）

### 1.1 三方法族多参数电池 + 加权共识判定策略（2026-07-07 二次修订）

`detectPaperCorners` 返回 `PaperDetection | null`（含 corners + confidence + methodCount + skew + mode）。

> 本次修订动因：用户原验证的三种可视化（Otsu / Canny / Otsu 反相最大轮廓）在**二值图层面**都清晰分离了纸张，但自动化落点（findContours→approxPolyDP→凸四边形校验）时，**Canny 易因纸边贴画框而溢出**、**Otsu 反相（THRESH\_BINARY\_INV）把背景当最大轮廓漏掉纸**。故改为：固定单参数 → 多参数电池 + 按「方法族」加权共识，并对首轮强命中早退。

> ⚠️ **`approxPolyDP` 取点致命坑（2026-07-07 修复）**：本构建（`public/opencv.js`，`@techstark/opencv-js 5.0`）下 `approx.ptr(i, 0)` 读 `CV_32SC2` 会错位（x 正确、y 恒为 0），导致所有点塌到图像顶边、`inBounds` 全拒、三族 0 candidates（前端"未检测到纸张"）。必须用 `approx.data32S[i*2]/[i*2+1]` 或 `approx.intPtr(i)` 读四角。详见 `DEVELOPMENT_GUIDE.md` §二.2。

**判定流程：**

① **首轮强命中早退**：先用 `Otsu + GaussianBlur(5)` 跑一次，若四边形「干净」（`isStrong`：四角明显在图内、角度 75°~105°、面积不过界）即直接返回（mode=strong, confidence=1）。好照片（绝大多数情况）只花 1 次 findContours。

② **三方法族多参数电池**（仅在首轮不干净时展开，覆盖光线/阴影/背景差异，避免固定一组参数全失败）：

| 方法族 | 参数变体 | 应对场景 |
|---|--------|---------|
| otsu | Otsu + 高斯(5/9) / 中值(5/7) 四种平滑 | 高对比、不同纹理背景 |
| canny | Canny(30,90)/(50,150)/(80,200) + 膨胀闭合 | 边缘完整但易贴框溢出 |
| adaptive | 自适应阈值 GAUSSIAN/MEAN × block 11/21（THRESH\_BINARY，纸为亮前景） | 光照不均 / 阴影 |

③ **按「方法族」加权共识落点**：所有候选按角点距离（`≤0.16×对角线`）贪心聚类，优先取 **≥2 个独立方法族**一致的簇（族越多 confidence 越高：`0.6+0.2×族数`），对一致角点取平均精化。仅单族多变体一致 → 中置信（0.6）接受；全无共识 → 仅单候选且 `isStrong` 才低置信（0.4）兜底；否则返回 null 提示重拍。

**为什么按「方法族」而非「变体数」加权：** 同一族的多个参数变体一致只是 1 份独立证据；Otsu + Canny + adaptive 三族中有 2 族一致才算强共识，更能抵抗单族系统性误判（如 Otsu 锁定白色桌面）。

**角度偏斜评估：**

- maxDev ≤ 12° → ok（无提示）
- 12° < maxDev ≤ 25° → mild（琥珀色提醒）
- maxDev > 25° → severe（红色警告：视角过偏导致工具抠图变形）

### 2. 调试和错误处理

- 详细的调试信息输出（每种策略的中间结果图像）
- 具体的失败原因诊断和用户提示
- 内存管理和资源释放

## 测试方法

1. `npm run dev` 启动，访问 http://localhost:5173
2. 进入校准页（CalibrationPage），上传 `public/testpic.jpg`
3. 图片就绪后**自动触发** `detectPaperCorners`，界面显示"识别中…"
4. 成功显示"✅ 已自动识别纸张四角"；失败显示红色原因文字，可点"重新检测"
5. 点"2. 透视校正" → "3. 提取工具轮廓"

> 唯一有效的调试入口是 `src/features/calibration/CalibrationPage.tsx`，没有独立的 opencv-test.html 测试页（历史测试页已删除，详见 DEVELOPMENT_GUIDE.md §一.1）。

## 集成到主应用

OpenCV.js 功能已完全集成到校准页面中：
- **三方法族多参数电池 + 加权共识自动检测**（图片导入即触发：首轮强命中早退，否则展开 otsu/canny/adaptive 三族多参数电池并按方法族加权共识，无需手动调参）
- **角度偏斜提醒**（视角过偏时琥珀/红色警告，防止工具抠图变形）
- **横竖屏自适应**（检测方向跟随照片方向，输出保持 A4 比例）
- 透视校正处理
- 尺寸标定计算
- 用户友好的界面和错误提示（"识别中…" / 失败原因文字）
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

- **所有 OpenCV 算法（检测/校正/轮廓）统一放在 `src/lib/opencvUtils.ts`**，**禁止新建** `autoPaperDetector.ts` / `PaperDetector.ts` 之类的 detector 散文件（历史上这些重复实现已删除并合并）。
- 纸张检测入口就是无参的 `detectPaperCorners(cv, img)`，调用方不要传 Canny/模糊/面积等参数，所有策略在内部自适应完成。
- 不要在多个文件里复制粘贴"轮询 window.cv + 展平 Promise"的代码——一律走 `loadCv()`。

## 参考资源

- OpenCV.js 官方文档
- @techstark/opencv-js npm 包文档
- 相关教程和示例代码
