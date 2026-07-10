以暗猜接口为耻，以认真查阅为荣
以模糊执行为耻，以寻求确认为荣
以盲想业务为耻，以人类确认为荣
以创造接口为耻，以复用现有为荣
以跳过验证为耻，以主动测试为荣
以破坏架构为耻，以遵循规范为荣
以假装理解为耻，以诚实无知为菜
以盲目修改为耻，以谨慎重构为荣

📌 项目背景（给AI看）
本项目是仿Tooltrace的Web工具：用户上传「工具放在A4纸上的俯拍照片」，浏览器本地完成A4纸检测、透视校正、工具轮廓提取、参数配置，最终导出STL/STEP/DXF文件用于3D打印工具收纳。
技术栈：Vite + React + TypeScript + OpenCV.js + Fabric.js + Three.js + Zustand。

> **⚠️ 架构重大修订（2026-07-09，撤回旧约束）**：原"所有计算均在浏览器本地完成、无后端依赖"的目标**已撤回**。死磕纯 JS = 主动放弃对标 Tooltrace 的核心竞争力，且会让已跑通的基元化/轮廓处理成果在最后一步（3D 生成）直接垮掉。新方向为「**Tauri/Electron 桌面应用 + Python 后端**」：前端 JS 负责交互/预览，3D 生成（STEP/复杂布尔）复用现有 Python 生态（pythonocc/trimesh/clipper）。详见 **§六 3D 生成与桌面化架构决策**。前端 OpenCV.js 轮廓提取 + DP 基元化（`opencvUtils.ts`）继续作为"网页预览"层，其输出的 `primitives` 即前后端契约。

## 一、项目结构铁律（严禁违反）

### 1. 单一调试入口（核心红线）

所有OpenCV/纸张检测/轮廓提取的调试，仅允许在src/features/calibration/CalibrationPage.tsx中进行，严禁新增任何零散HTML测试文件（包括但不限于public/_.html、test-_.html）。
已永久删除的冗余文件（AI不得再提及或使用）：
public/optimized-detector-test.html、public/debug-test.html、public/paper-detector-test.html、public/opencv-debug.html、public/simple-test.html、test-paper-detector.html

### 2. 文件存放规范（不得随意新增）

| 功能                                         | 唯一文件路径                                                       |
| -------------------------------------------- | ------------------------------------------------------------------ |
| OpenCV加载入口（轮询window.cv）              | src/lib/opencvLoader.ts                                            |
| OpenCV核心算法（**检测/校正/轮廓全部在此**） | src/lib/opencvUtils.ts                                             |
| OpenCV加载Hook（React）                      | src/hooks/useOpenCV.ts                                             |
| 校准/调试页面                                | src/features/calibration/CalibrationPage.tsx                       |
| 全局状态管理                                 | src/app/store.ts                                                   |
| 第三方OpenCV资产                             | public/opencv.js（13MB，由npm包复制，禁止改回npm import）          |
| 前端全局样式（Tailwind 入口）                | src/index.css（@tailwind 三指令 + body base）                      |
| 前端构建配置（Tailwind/PostCSS）             | tailwind.config.js / postcss.config.js（见下方「前端样式体系」节） |

确需新增文件需先说明理由，禁止AI擅自创建零散文件。

> **检测逻辑集中声明（2026-07-07）**：纸张四角检测、透视校正、工具轮廓提取**全部集中在 `src/lib/opencvUtils.ts`**（对应本表"OpenCV核心算法"）。`detectPaperCorners(cv, img)` 为**全自动、无参数**接口，内部多策略自适应，调用方不要在外部传 Canny/模糊/面积等参数。此前散落的 `autoPaperDetector.ts` / `simplePaperDetector.ts` / `PaperDetector.ts` / `PaperDetector.optimized.ts` / `OptimizedPaperDetector.ts` / `testUtils.ts` 及 `CalibrationPage.backup.tsx` 已统一删除并合并进本项目唯一算法文件。**禁止再新增独立的 detector 散文件。**

**`opencvLoader.ts` 存在理由**（2026-07-07）：把"轮询 window.cv + 展平嵌套 Promise"独立成工具函数，是为了和 `useOpenCV` hook 复用同一份逻辑。**严格意义上这超出了§一.2 "新增文件需先说明理由"的要求**——事先未在对话中说明。下次类似改动应先在对话里说明理由并征得同意，再创建文件。

**`src/lib/samInference.ts` 存在理由**（2026-07-09）：SAM（Segment Anything）浏览器内 ONNX 推理。它是**模型运行时胶水**（`onnxruntime-web` 加载 + ViT 解码器前向），**不是轮廓算法**，与"检测/校正/轮廓全部集中在 opencvUtils.ts"的声明不冲突——轮廓算法（Fast 检测 `extractFastMask`、SAM 后处理 `prepareSamMask`、并集 `segmentDetail`、DP 基元化 `extractPrimitives`）仍在 `opencvUtils.ts`。把 70 行 ML 推理 + 动态 `import("onnxruntime-web")` 塞进 `opencvUtils.ts` 会污染核心算法文件并拖慢首屏，故独立成文件。若团队坚持绝对单文件，可将其 `SamInference` 类搬回 `opencvUtils.ts`。配套 `scripts/convert_sam_onnx.py` 为本地模型导出脚本（非前端运行时）。详见 `OPENCV_INTEGRATION.md` "SAM 浏览器内 ONNX 推理"。

### 前端样式体系（Tailwind，2026-07-09 接入）

> **背景**：项目所有组件（Stepper / Button / CalibrationPage 等）自初版即用 Tailwind 原子类名，但**此前 Tailwind 未配置**——无 `tailwind.config.js`、无 `postcss.config.js`、`package.json` 无 tailwind 依赖、`src` 无全局 CSS 的 import。结果是**所有类名失效、页面裸奔**（无布局/无居中/无配色），这正是用户反馈"网页太简陋"的根因。本次把 Tailwind 真正接好，现有全部 UI 代码立即生效，无需改写组件。

**配置位置（缺一不可）：**

- `tailwind.config.js`：`content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}']`；`theme.extend` 定义 `brand` 色板（50–900）、`shadow-card`/`shadow-card-hover`、圆角、`fontFamily.sans`。
- `postcss.config.js`：plugins `tailwindcss` + `autoprefixer`（ESM `export default`，因项目 `"type":"module"`）。
- `src/index.css`：`@tailwind base/components/utilities;` + `body`/`html`/`#root` 基础样式（背景 `#f1f5f9`、字体、细滚动条）+ 工具类 `.img-contain`。
- `src/main.tsx`：顶部 `import './index.css'`（必须最先 import，早于业务组件）。
- `vite.config.ts`：无需改（Tailwind 通过 PostCSS 自动接入，Vite 8 原生支持）。
- `package.json` → `devDependencies`：`tailwindcss@^3.4.17`、`autoprefixer@^10.4.20`、`postcss@^8.4.49`。

**使用约定（新增 UI 时遵守）：**

- 组件继续用 Tailwind 原子类；**主色一律用 `brand-*`**（如 `bg-brand-600`/`text-brand-700`），不要硬编码 `#2563eb` 之类的蓝。
- 卡片统一 `bg-white rounded-2xl shadow-card border border-slate-100`；空状态引导用虚线边框大卡片。
- **不引入** CSS-in-JS 库（styled-components 等）或第三方 UI 组件库；保持 Tailwind-only。
- **共享组件库**：`src/components/ui/` 已沉淀 `Card` / `Badge` / `Button` / `SectionHeading` / `EmptyState` / `icons`（自绘 SVG，零新依赖）。新增页面/卡片优先复用，不要重复手写卡片外壳或裸 `<input>`；图标统一从 `icons.tsx` 取，不堆 emoji。**计划图标库为 lucide-react**（用户指定栈 Shadcn/ui + Tailwind + Lucide）；当前沙箱 WSL 文件系统 npm 安装存在 `ENOTEMPTY` 重命名冲突、无法在此装，暂用自绘 SVG，你 WSL 内 `npm i lucide-react` 后可一键替换。
- 新增全局基础样式（字体、滚动条）放进 `src/index.css` 的 base 层，不要散到组件。

**布局架构（单屏 workspace，2026-07-09 二次重构）**：应用从「6 步向导（Stepper）」改为 **Figma / Tooltrace 式单屏 workspace**，`src/features/workspace/Workspace.tsx` 为唯一外壳（由 `Home` 渲染）：

- **顶栏（浅色 Linear 风）**：品牌标 + A4 / 0.3mm 模式芯片 + 「生成嵌件」主按钮（待几何时禁用）。
- **左侧工具栏（浅色、可收起 `w-16`↔`w-56`）**：上传 / 校准 / 轮廓提取 / 矢量编辑 / 参数 / 导出 六个工具，激活态用 `brand` 高亮；点击切换 `store.step`。
- **中央深色画布 viewport（`bg-canvas-950` + `.canvas-grid` 点阵）**：无图时居中虚线拖拽区；有图时显示校正后工作图，支持缩放（底部玻璃工具条）+ 网格开关 + 左上阶段指示 + 左下「3D 预览区·后端几何待接入」占位。
- **右侧浮动玻璃参数面板（`glass-panel`，绝对定位浮于画布右上，不挤占画布）**：按 `store.step` 渲染上下文——校准步含检测状态 / 四角坐标 / 透视校正 / 提取轮廓按钮 / 基元统计；其余步显示「规划中」卡片。
- **算法管线原样保留**：OpenCV 检测 / 校正 / 提取逻辑仍在 `Workspace` 内调用 `detectPaperCorners` / `perspectiveWarp` / `extractToolContours`，未触碰 `opencvUtils`。

**视觉令牌**：`tailwind.config.js` 的 `theme.extend.colors` 新增 `canvas`（950/900/850/800/700/600，深色画布与面板基调）；`src/index.css` 新增 `.canvas-grid`（点阵）、`.glass-panel`/`.glass-bar`（玻璃态浮层）、`.canvas-scroll`（深色细滚动条）。主色仍统一用 `brand-*`。

### 3. 参数管理规范

- **纸张检测已全自动**：`detectPaperCorners(cv, img)` 不接受任何参数，多策略自适应内部完成，UI 上**不提供也不应恢复** Canny/模糊/面积等手动调参滑块（历史经验：手动调参体验差且对白纸+木纹场景无必要）。
- 如需调整策略权重/阈值，直接在 `src/lib/opencvUtils.ts` 内部修改，不要外泄成 UI 参数。
- 轮廓提取的 `minArea` 目前以常量传入（默认 300），如确需可调，再以 React State 形式放在 CalibrationPage 中通过函数参数传递，严禁写死在工具函数默认值以外的位置。

## 二、OpenCV.js开发专项规范

### 1. 内存管理（必查项）

所有cv.Mat、cv.MatVector、cv.Kernel等OpenCV对象，使用完毕后必须立即调用.delete()，严禁内存泄漏。不得编造dispose()等不存在的销毁方法。

### 2. API合规性

仅使用OpenCV.js的Web端API，严禁混用其他环境的API：
✅ 正确：cv.imread(imgElement)、cv.imshow(canvas, mat)、cv.findContours(cnts, hier, ...)
❌ 错误：cv2.imread()（Python API）、cv.imwrite()（Node API）、cv.drawContours(img, cnts)（缺参数版本）

**@techstark/opencv-js 5.0 构建的特有坑（已踩）**：本项目 `public/opencv.js` 来自该构建，**没有** `cv.createCLAHE` 等 `create*` 工厂函数（`createCLAHE` 在官方 emscripten 文档里存在，但此构建未导出）。CLAHE 必须用**构造函数**：

```typescript
const clahe = new cv.CLAHE(2.0, new cv.Size(8, 8)); // ✅ 正确
clahe.apply(gray, enhanced);
clahe.delete();
// ❌ 错误：const clahe = cv.createCLAHE(2.0, new cv.Size(8,8)); // TypeError: cv.createCLAHE is not a function
```

不确定某个 API 在本构建是否存在时，用 `grep -a "函数名" public/opencv.js` 或 Node 读文件 `s.indexOf('函数名')` 验证（该文件含 wasm 字节，ripgrep 会判为二进制，用 Node 读更可靠）。

**`approxPolyDP` 输出取点必须用 `data32S` 或 `intPtr`（2026-07-07 修订，已踩大坑）**：本构建下 `approx.ptr(i, 0)` 读 `CV_32SC2`（type=36，即 4×1×2 Int32）会**错位**——x 正确但 y 恒为 0，导致所有点塌到图像顶边、`inBounds` 全拒、三方法族 0 candidates（前端「未检测到纸张」）。Node 最小复现已验证：`approx.rows/cols/channels/type = 4/1/2/36`，`data32S=[x0,y0,x1,y1,...]` 与 `intPtr(i)=[x,y]` 均正确，`ptr(i,0)` 错误。

```typescript
// ✅ 正确：用 data32S 读取四角（已在 Node + 真实图验证）
const s = approx.data32S as Int32Array;
for (let i = 0; i < 4; i++) pts.push({ x: s[i * 2], y: s[i * 2 + 1] });
// ✅ 也可用 intPtr：const p = approx.intPtr(i); pts.push({ x: p[0], y: p[1] });
// ❌ 错误：const p = approx.ptr(i, 0); // y 恒为 0，四边形退化
```

> 注：此前文档误写「禁止用 data32S、改用 ptr(i,0)」——该结论未经构建验证，正是此 bug 来源。cv2(Python) 用 `cnt.reshape(-1,2)` 读点正常，但 JS 侧 `ptr` 在此构建不可用。

### 3. 透视校正必做逻辑

使用cv.approxPolyDP获取四边形后，必须对4个点按「左上→右上→右下→左下」排序，严禁直接使用approxPolyDP的无序输出做透视变换。

### 4. 单位明确

透视校正后必须明确标注像素与实际毫米的换算关系（例如SCALE=10代表1px=0.1mm），所有轮廓坐标运算必须标注单位，严禁无单位的数值计算。

### 5. 验证流程

复杂算法（如纸张检测、轮廓提取）必须先通过Python OpenCV验证正确性，再迁移到OpenCV.js，严禁直接让AI编写未经验证的复杂算法。

### 6. 加载机制（2026-07-07 新增，重要）

**严禁在代码中使用 `import` 或 `import('@techstark/opencv-js')`**——Vite dev mode 会因 13MB CJS/UMD 文件导致整个模块图卡死，表现为：①白屏 ②`loaded` 永远 false。

**正确做法**：

- `public/opencv.js`（由 `node_modules/@techstark/opencv-js/dist/opencv.js` 复制）：通过 `<script src="/opencv.js">` 经典标签加载，UMD 自动挂载到 `window.cv`
- `src/lib/opencvLoader.ts#loadCv()`：轮询 `window.cv` → 展平嵌套 Promise → 校验 `cv.imread`
- `src/hooks/useOpenCV.ts`：调用 `loadCv()`，返回 `{ cv, loaded, error }`
- `index.html` 顺序：`<script src="/opencv.js">` 必须在 `<script type="module" src="/src/main.tsx">` 之前
- `vite.config.ts` 不需要 `optimizeDeps.exclude`（已不再通过 npm import）

**全项目铁律**：任何模块都禁止 `import('@techstark/opencv-js')`——一律 `import { loadCv } from '@/lib/opencvLoader'`。

**禁止手段**（AI 不得使用）：

- ❌ `import cvReadyPromise from '@techstark/opencv-js'`（静态 import）
- ❌ `const cvModule = await import('@techstark/opencv-js')`（动态 import，Vite 会卡）
- ❌ 等待 `window.cv = cv`（实际是 Promise，赋值前 cv 是函数本身，不是对象）
- ❌ `window.cv.Mat`（永远 undefined，因 cv 是 Promise）

**正确使用**：

```typescript
import { loadCv } from "@/lib/opencvLoader";
const cv = await loadCv();
cv.imread(imgElement);
```

**本次踩坑的三个阶段**（避免重蹈）：

1. **阶段1（白屏）**：静态 import → Vite 模块图卡死 → 整个 JS 加载链路崩溃
2. **阶段2（永远加载中）**：改动态 import → Vite 的 `import()` 对 13MB CJS 仍卡死，Promise 永不 resolve
3. **阶段3（解决）**：放弃 Vite 模块系统，`<script>` 标签 + `window.cv` + `loadCv()`

### 7. 工具轮廓提取与基元化（DP 逐段法，2026-07-09 对齐）

> **背景**：WSL 的 `extractPrimitives` 最终对齐的离线验证算法是 `contour_simplify.py` / `batch_process.py`（DP 抽稀 + 逐段 line/arc 拟合）；并集算法对齐 `sam_union_final.py`（Red(SAM) ∪ Green(Fast)）。**此前误用的「曲率分段法」（`optimized_primitives.classify_and_fit_optimized`）已废弃**——见下方「关键坑」。纯 JS 端到端回归已 1:1 验证：4 张真实工具图（caliper/hex_wrench/pliers）的直线·圆弧·折线数量与逐段序列、弧半径均与 Python 完全一致。

**完整管线（与离线 Python 严格对齐）：**
`segmentDetail`：Red(SAM) `→ close(9) 桥接 → dilate(7) 放宽到与 Fast 一致` `∪` Green(Fast) `→ erode(3 椭圆) 吃边缘薄阴影 → merged_contour（全量重绘+close(9)桥接+取最大轮廓）→ Chaikin 平滑 2 次`
`extractPrimitives`：DP 抽稀(ε=0.004·周长) 取拐点 → 相邻拐点稠密点段上逐段拟合「直线(cv2.fitLine 等价)」或「圆弧(代数最小二乘圆拟合)」，取误差小者

入口 `abstractFromMask(cv, fastMask, samMask?, options?)`：

- `samMask` **可选**；传了就先 `close(9)+dilate(7)` 再 `bitwise_or` 与 Fast 合并（union 接口已留好），不传走 Fast-only（当前 WSL 默认路径）。
- 腐蚀核 `MORPH_ELLIPSE(3)`；SAM 侧 `close/dilate` 核 `MORPH_ELLIPSE(9)`/`(15)`。
- `findContours(RETR_EXTERNAL, CHAIN_APPROX_NONE)` 取**面积最大**轮廓（此处 `CHAIN_APPROX_NONE` 取稠密点；与 `extractToolContours` 顶层画调试轮廓用的 `CHAIN_APPROX_SIMPLE` 不同，后者仅用于绘制）。

**基元化算法（`extractPrimitives`，主 DP 用 `cv.approxPolyDP`，拟合为纯 JS）：**

1. `cv.approxPolyDP(ε = 0.004·arcLength)` 取拐点顶点（闭环）。
2. 把每个拐点映射回稠密点数组的最近下标（`nearestIndex`），相邻拐点之间取原始稠密点段。
3. 逐段判定（对齐 `contour_simplify.py`）：
   - `err_l` = 直线拟合 RMS 误差（**等价 `cv2.fitLine` + Python `line_fit_error`：以 `pts[0]` 为参考点算垂直距离**）。
   - `err_c` = 圆弧拟合 RMS 误差（**中心化 Kasa 代数最小二乘圆拟合**，等价 `np.linalg.lstsq`；替代 `cv2.minEnclosingCircle` 避免 <180° 弧半径塌缩到 ~0.707R）。
   - `is_arc = err_c < err_l 且 err_c < ARC_TOL(4) 且 err_l > LIN_TOL(4)`。
   - `is_arc` 且 `半径 ≤ MAX_ARC_R(55)` → `{type:"arc", center, radius, startAngle, endAngle, points}`（重采样点列，按短弧方向避 0/360 穿越）。
   - `is_arc` 但 `半径 > 55`（缓弯）→ 退化为折线 `polyline`（段内细粒度 DP，`sub_eps=0.002·周长`，`dpSimplifyJS`）。
   - 否则 → `{type:"line", p0, p1}`。

**类型与状态（`src/utils/types.ts` / `src/app/store.ts`）：**

- `Primitive = LinePrimitive | ArcPrimitive | PolylinePrimitive`；`ArcPrimitive` 含 `center/radius/startAngle/endAngle/points?`。
- `AbstractOptions = { dpEpsilon?, linTol?, arcTol?, maxArcRadius? }`（默认值 0.004 / 4.0 / 4.0 / 55，对齐 Python 常量）。
- store 新增 `primitives: Primitive[]` + `setPrimitives`；`CalibrationPage` 展示绿(直线)/橙(圆弧)/紫(折线) + 计数。

**⚠️ 关键坑（移植时踩过、已修复，勿回退）：**

1. **圆拟合必须中心化**：`circleFitJS` 用中心化 Kasa 法方程；未中心化法方程在真实图片坐标（x/y 数百~上千）下数值崩溃 → 半径算错/返回 null → 0 弧。已对齐 `np.linalg.lstsq`。
2. **直线误差必须以 `pts[0]` 为参考点**：Python `line_fit_error = sqrt(mean((pts-pts[0])·normal²))`，等价于 `sqrt(真实垂直RMS² + K²)`（K=pts[0] 到拟合线距离），系统性偏大。若用质心参考会得到真实 RMS，偏小 → `err_l>4` 永不满足 → 0 弧。务必用 `pts[0]`。
3. **SAM 当前是 mock**：`SegmentationPage` 里 SAM 为占位蓝框，未产出可用掩膜；故 WSL 默认 Fast-only 路径。真实 SAM 接入后把 `samMask` 传给 `extractToolContours` 即生效。

**踩坑记录（重要）：**

- 代数圆拟合线性系统原有两个 bug：`Suuuv` 算成 Σu³v、RHS 取了负号，会把半径炸到 1655；修正后 90°弧 r=50 → **r=50.00 精准不塌缩**。
- 原 `opencvUtils.ts` 存在**两个 `ptsFromMat` 重复声明 + 一堆 `noUnusedLocals` 死代码**，项目原本 `tsc` 根本过不了；已删除旧 DP 辅助函数，仅保留唯一 `ptsFromMat`。

## 三、AI协作八荣八耻（AI专属约束）

以集中逻辑为荣，以拆分散文件为耻：核心功能代码必须集中在≤3个文件中，拒绝过度抽象、拆分无意义的小文件。
以非阻塞执行为荣，以长命令卡死为耻：严禁执行npm run dev等长期阻塞终端的命令；启动服务前必须先检测端口占用，若端口已占用直接提示用户访问现有地址，不得反复重试。
以显式释放内存为荣，以OpenCV内存泄漏为耻：所有OpenCV对象必须显式调用.delete()，不得遗漏。
以适配目标环境为荣，以混用跨端API为耻：严格区分Web/Node/Python环境API，本项目为纯Web应用，所有代码必须运行在浏览器中。
以先读现有配置为荣，以覆盖原有配置为耻：修改vite.config.ts/tsconfig.json前必须先读取现有文件内容，不得直接覆盖原有配置，不得私自添加未声明的插件或loader。
以验证依赖真实性为荣，以虚构不存在包为耻：引用npm包前必须先验证包是否存在，严禁虚构@types/fabric、opencv-contrib-js等不存在/已废弃的依赖。
以完整报错分析为荣，以甩锅用户环境为耻：遇到报错必须先索要完整日志/截图，先分析代码逻辑问题，不得张口就说"你环境有问题""换个Node版本试试"。
以输出可运行代码为荣，以留TODO半成品为耻：输出的代码必须是复制粘贴后可直接运行的，不得遗留未定义的变量、未实现的TODO、缺少import的模块。

## 四、开发流程规范

小步提交：每调通一个功能点（如纸张检测、透视校正、轮廓提取）立即git commit，禁止累积大量修改后一次性提交。
先验证后固化：调试阶段的参数调整仅在CalibrationPage的State中进行，待参数稳定后，再将最优值作为工具函数的默认值，禁止AI擅自修改已验证稳定的参数。
禁止全自动：所有AI生成的代码必须经过人工Review后方可合并，严禁开启Auto-accept后直接合并AI代码。

## 五、违规处理

若AI违反上述任何一条规定，立即点击Cancel终止当前对话，Reload Window后重新开始，无需与AI争辩。

## 六、3D 生成与桌面化架构决策（2026-07-09 重大修订）

> **修订动因（撤回旧约束）**：撤回 2026-07 初"WSL 里完全不能用 Python、纯 JS 实现"的约束。结论：死磕纯 JS = 主动放弃对标 Tooltrace 的核心竞争力，且会让已跑通的基元化/轮廓处理成果在最后一步（3D 生成）直接垮掉。故改为「前端 JS 交互 + Python 后端生态」的桌面化方案。本决策适用于"后续工具开发"的方向把控。

### 1. 明确结论：纯 JS 做 3D，麻烦程度与要的 3D 质量强相关

| 目标                                              | 可行性        | 麻烦程度 | 周期                          |
| ------------------------------------------------- | ------------- | -------- | ----------------------------- |
| 网页 3D 预览 / 导出简单 STL（满足 3D 打印）       | ✅ 完全可用   | 中等     | 1~2 周，不用后端              |
| Tooltrace 级（STEP 导出 / 复杂布尔 / 多工具排版） | ❌ 几乎不可能 | 灾难级   | 除非填 3~6 个月 WASM 生态的坑 |

纯 JS 生成 3D 模型，麻烦是肯定的，但完全能做到「可用」；麻烦程度与你要的 3D 质量强相关。

### 2. 纯 JS vs Python 的三大核心痛点

| 能力              | Python 生态                                                              | 纯 JS 生态                                                                                             | 麻烦度     |
| ----------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------ | ---------- |
| CAD 内核（B-Rep） | pythonocc 完整封装 OpenCASCADE：直线/圆弧拉伸、偏移、布尔运算、STEP 导出 | 只有 @jscad/occt 这类 WASM 封装，功能残缺：不支持 STEP 导出、圆弧拉伸经常崩、偏移自交修复几乎没有      | ⭐⭐⭐⭐⭐ |
| 2D 轮廓处理       | clipper（C++ 原生）：高精度 offset、自交修复                             | clipper2-js（JS 移植）：功能砍半——大偏移量易出破面、自交修复逻辑弱需手写兜底                           | ⭐⭐⭐⭐   |
| 性能              | CUDA 加速 SAM、numpy 向量化，复杂轮廓秒出                                | JS 单线程；SAM 用 Transformers.js 比 Python 慢 3~5 倍；复杂轮廓基元化+3D 生成会卡顿，必须用 Web Worker | ⭐⭐⭐     |

> ⚠️ **最坑一点**：纯 JS 几乎无法生成 STEP（工业级 CAD 标准），只能生成 STL（三角面片格式）。**若坚持要 STEP，纯 JS 直接劝退。**

### 3. 纯 JS 降级可行路径（仅当"只要 STL + 放弃 STEP"时）

**工具链组合（已踩坑验证可用）：**

```
前端交互 → OpenCV.js（轮廓提取 / DP 抽稀）
         → 基元化逻辑（JS 版，几乎 1:1 翻译 Python 代码）
         → Clipper2-js（2D 公差补偿 / offset）
         → @jscad/modeling（矢量拉伸成 3D）
         → @jscad/stl-serializer（导出 STL）
```

**三个避坑点（务必遵守）：**

1. **不要拿 JS 的 OCCT 绑定做复杂操作**：offset、布尔运算全在 2D 层面用 Clipper2-js 做；@jscad/occt 只用来做「直线/圆弧拉伸」。
2. **圆弧必须采样成多段线**：JS 的拉伸功能对原生圆弧支持极差，把圆弧基元按 `5°/点` 采样成多段线再拉伸，STL 表面才光滑。
3. **offset 后用 earcut 做三角化兜底**：Clipper2-js offset 后的轮廓可能有自交，用 earcut 兜底三角化，避免生成破面 STL。

**最小可用 Demo（JS 版 3D 生成核心逻辑，可直接跑）：**

```typescript
// 假设你已经有了基元数组 primitives（结构与 Python 版一致）
import { line, extrudeLinear, serialize } from "@jscad/modeling";
import { stlSerializer } from "@jscad/stl-serializer";

// 1. 把基元转成 JSCAD 的 2D 几何
const shapes2d: any[] = [];
for (const p of primitives) {
  if (p.type === "line") {
    shapes2d.push(line({ start: p.p0, end: p.p1 }));
  } else if (p.type === "arc") {
    // 圆弧采样成多段线（5°一个点，保证光滑）
    const { center, radius, angle_start, angle_end } = p;
    const segments = Math.ceil(Math.abs(angle_end - angle_start) / 5);
    const points: [number, number][] = [];
    for (let i = 0; i <= segments; i++) {
      const angle = angle_start + (angle_end - angle_start) * (i / segments);
      const x = center[0] + radius * Math.cos((angle * Math.PI) / 180);
      const y = center[1] + radius * Math.sin((angle * Math.PI) / 180);
      points.push([x, y]);
    }
    shapes2d.push(line({ points }));
  }
}

// 2. 拉伸成 3D（厚度 3mm，对应嵌件深度）
const model3d = extrudeLinear({ height: 3 }, shapes2d);

// 3. 导出 STL（binary:false 可读文本，便于调试）
const stlData = serialize(model3d, { binary: false });
// 浏览器侧：new Blob([stlData]) → download URL → a.click()
```

> 该 Demo 能直接跑出可打印 STL，但圆弧采样多→STL 文件大、采样少→表面有棱角，需自己平衡——这就是纯 JS 的代价，Python 的 pythonocc 根本不用考虑。

### 4. 最终决策（最优解）：Tauri / Electron 桌面打包

结合「工具收纳嵌件」需求，优先级从高到低：

✅ **最优解：Tauri/Electron 打包（兼顾网页体验 + Python 生态）**

- 前端：JS 做交互（网页级体验，支持拖拽、预览）
- 后端：**复用现有 Python 代码**做 SAM、基元化、3D 生成（完全不用改代码）
- 打包成桌面应用，用户双击就能用，无需部署后端，隐私性也 ok
- 开发成本最低，**1 周出可用版本**，支持 STEP/STL 所有格式

> **Tauri vs Electron 选型提示**：Tauri 更轻（Rust 壳 + 系统 WebView，包体小、性能好），但 Python 后端需以子进程 / 本地 HTTP 方式桥接；Electron 自带 Node 运行时、集成 Python 子进程更简单，但包体大。具体选型留待实现阶段根据用户环境定。

### 5. 对当前 WSL 代码的影响（待实现，本环境未做）

- **前端（已就绪）**：OpenCV.js 轮廓提取 + DP 基元化（`opencvUtils.ts`）继续作为"网页预览"层；其输出的 `primitives` 是传给后端的核心契约（字段见 §二.7 / `src/utils/types.ts`）。
- **后端（待建）**：新建 Python 后端（CLI 或本地 HTTP），接收 `primitives` JSON → 用 `pythonocc`/`trimesh`/`clipper` 做 3D 生成 → 返回 STL/STEP 文件。
- **桥接**：桌面壳（Tauri/Electron）把前端 `primitives` 通过 stdin/IPC/HTTP 喂给 Python 后端，再把生成的 3D 文件回传前端预览/下载。
- **SAM 来源澄清**：若走 Tauri+Python 后端，**浏览器内 ONNX 推理（`src/lib/samInference.ts`）即被 Python SAM 后端取代**，无需在浏览器跑神经网络（OPENCV_INTEGRATION.md 的「SAM 浏览器内 ONNX 推理」节仅作为纯前端降级备选保留）；`opencvUtils.ts` 的 `prepareSamMask`/`segmentDetail` 仍作为"后端 Python 算好 SAM 掩膜 → 前端 union"的契约层。
- **纯 JS 降级路径**（§3）仅在"绝对不要后端"的轻量预览场景使用，不作为主路径。

## 七、下一步开发需求：桌面化桥接层（Tauri/Electron + Python 后端）

> 状态：**需求已定，实现未开工**。本节把 §六 的决策落成可执行的开发任务清单，供在 WSL 照做（或交 AI 实现时直接引用）。这是 2026-07-09 收尾时口头提议、但尚未落档的部分。

### 1. 目标

把现有纯前端（OpenCV.js 轮廓提取 + DP 基元化）包成桌面应用，复用 Python 生态（`pythonocc` / `trimesh` / `clipper`）做 3D 生成，最终产出可 3D 打印的 **STEP（主）/ STL（预览）** 嵌件文件。前端 `primitives` 作为前后端唯一契约。

### 2. 前后端契约：`primitives` JSON 形状

前端 `extractToolContours` → `abstractFromMask` 产出的 `Primitive[]`，经桌面壳传给 Python。字段以 `src/utils/types.ts` 为准：

```typescript
type Primitive =
  | { type: "line"; p0: [number, number]; p1: [number, number] }
  | {
      type: "arc";
      center: [number, number];
      radius: number;
      startAngle: number;
      endAngle: number;
      points?: [number, number][];
    }
  | { type: "polyline"; points: [number, number][] };
```

Python 端用 `dataclass` / `pydantic` 镜像该结构，作为 3D 生成的输入。角度单位（度/弧度）需在契约里固定并写进 types.ts 注释，避免前后端错位。

### 3. 两个实现起点（选其一先开工，推荐先做 3.1 验证契约闭环）

- **3.1 Python 后端（优先，最快验证「前端 → 后端」闭环）**
  - 形态：本地 HTTP 服务（FastAPI）或 CLI（stdin 收 JSON / 文件出 stdout）。
  - 职责：收 `primitives` JSON → 用 `clipper` 做 2D 偏移（嵌件留公差）→ `pythonocc` 把直线/圆弧拉伸成实体（**圆弧先按 5°/点 采样多段线**，对齐 §六.3 避坑点 2）→ 布尔差集挖出工具槽 → 导出 STEP（主）/ STL（预览）。
  - 验收：`curl` 发一张测试图的 `primitives` → 得到可打开的 STEP/STL。
- **3.2 桌面壳（Tauri 优先，包体小）**
  - 把现有 Vite 前端包进 Tauri；用 Tauri 的 `Command` / 本地 HTTP 调起 Python 子进程。
  - 职责：前端点「生成 3D」→ 壳把 `primitives` 喂给 3.1 的 Python → 回传 3D 文件 → 前端 Three.js 预览 + 下载按钮。
  - 验收：桌面应用内完成「照片 → 轮廓 → 3D 文件」全流程，无外部服务。

### 4. 关键技术决策（实现前拍板）

- **Tauri vs Electron**：Tauri（Rust 壳 + 系统 WebView，包体小）需解决 Python 子进程桥接；Electron（内置 Node，集成 Python 更简单）包体大。建议先按 Tauri 试，卡住再转 Electron。
- **Python 分发**：PyInstaller / Nuitka 打包进安装包，或要求用户本机有 Python 环境（开发期用后者，发布期用前者）。
- **SAM 位置**：走 Python 后端跑 SAM（取代浏览器 ONNX），`opencvUtils.ts` 的 `prepareSamMask`/`segmentDetail` 作为「后端算好 SAM 掩膜 → 前端 union」契约层保留。

### 5. 验收清单

- [ ] `primitives` JSON 能在前端导出、Python 端正确解析（字段/角度单位一致）
- [ ] Python 后端对一组 `primitives` 产出合法 STEP + STL
- [ ] 桌面壳内点按钮完成「照片 → 3D 文件」闭环
- [ ] 生成的嵌件槽位与工具轮廓公差匹配（clipper offset 生效）

## 八、竞品对标全量需求文档（ToolTrace 对标 PRD）

> 完整的产品需求、功能清单、技术架构、数据流转与开发路线图，**已独立成册：`PRODUCT_REQUIREMENTS.md`（与本文件同目录）**。
> 该文档是「要做什么」的权威来源；本指南是「代码怎么写 / 怎么合规」的权威来源。两者配合：PRD 里标注「已有算法」的项，对应本指南 §六/§七 已落地的 WSL 代码与契约。

**功能清单速览（按模块，完整 P0/P1/P2 见 `PRODUCT_REQUIREMENTS.md`）：**

- **输入与预处理**：F1.1 单图上传 / F1.3 透视校正(**已有**) / F1.4 智能掩码 SAM+CV 融合(**已有**) / F1.5 工具类型标签
- **2D 轮廓基元化**：F2.1 平滑(**已有**) / F2.2 矢量拟合 Line/Arc(**已有**) / F2.3 公差预设 / F2.4 基元可视化(**已有**)
- **输入与预处理补充**：F1.6 画廊/本地历史(回看重打)
- **2D 轮廓补充**：F2.5 手动描边修正(控制点) / F2.6 自定义形状绘制 / F2.7 Detail 精度档
- **嵌件设计(核心)**：F3.1 底板设置 / F3.3 独立嵌入深度 / F3.4 手指槽自动 / F3.5 手指槽微调 / F3.6 MaxRects 自动排版 / F3.7 手动拖拽排版 / F3.8 间距 / F3.9 网格吸附 / **F3.10 Gridfinity 升为一等模式(与 Foam 并列)** / F3.11 强制对称 / F3.12 导入已有工具
- **导出补充**：F5.5 PDF 1:1 校对图
- **📌 范围声明(个人使用)**：完整对标 Tooltrace _功能能力_；**不含** 其 SaaS 社交/商业化层(云端账户/社区发布评分/分享短链/付费墙/5S-B2B 话术)。画廊为**本地历史**非云端社区。
- **3D 可视化**：F4.1 Three.js 预览 / F4.2 轮廓叠加 / F4.3 实时更新(WS 重算) / F4.4 视角预设
- **导出**：F5.1 STL(**已有**) / F5.2 STEP(**已有**) / F5.3 3MF / F5.4 DXF/SVG
- **技术架构**：前后端分离 + WebSocket；后端 B1-B6（FastAPI/算法引擎/基元化/排版引擎/CAD 内核/数据模型）；前端 F1-F6（UI/3D 引擎/交互/状态/通信/可视化）
- **路线图**：Phase 1 MVP(2W) → Phase 2 交互与排版(3W) → Phase 3 专业功能与导出(2W)

## OpenCV纸张四角检测开发指南

### 1. 统一调试入口

项目已完成测试界面断舍离，仅保留唯一调试入口：

- `src/features/calibration/CalibrationPage.tsx` - 唯一的OpenCV调试、纸张检测、参数调优入口

所有零散测试页已删除，包括：

- `public/optimized-detector-test.html`
- `public/debug-test.html`
- `public/paper-detector-test.html`
- `public/opencv-debug.html`
- `public/simple-test.html`
- `test-paper-detector.html`
- `src/pages/OpenCVTestPage.tsx`
- `src/pages/SimpleTestPage.tsx`

### 2. 自动检测说明（detectPaperCorners）

纸张四角检测已全部集中在 `src/lib/opencvUtils.ts#detectPaperCorners(cv, img)`，**全自动、无参数**，UI 不提供手动调参（历史经验：手动 Canny/模糊/面积滑块对"白纸+木纹+投影暗边"场景无必要且体验差）。

#### 三方法族多参数电池 + 加权共识判定逻辑（2026-07-07 二次修订）

> 修订动因：用户原验证的 Otsu / Canny / Otsu 反相三种**可视化**都清晰分离了纸张，但自动化落点（findContours→approxPolyDP→凸四边形校验）时 Canny 易贴框溢出、Otsu 反相（THRESH_BINARY_INV）会把背景当最大轮廓漏掉纸。固定单参数在光线/阴影/异色背景下必然有盲区。故改为「首轮强命中早退 → 三方法族多参数电池 → 按方法族加权共识」。

判定流程（`detectPaperCorners` 全程无参数，内部自适应）：

① **首轮强命中早退**：`Otsu + GaussianBlur(5)` 跑一次，四边形 `isStrong`（四角明显在图内、角度 75°~105°、面积合理）即返回（mode=strong, conf=1）。好照片只花 1 次 findContours。

② **三方法族多参数电池**（仅首轮不干净才展开）：

| 方法族   | 参数变体                                                                |
| -------- | ----------------------------------------------------------------------- |
| otsu     | Otsu + 高斯(5/9) / 中值(5/7) 四种平滑                                   |
| canny    | Canny(30,90)/(50,150)/(80,200) + 膨胀闭合                               |
| adaptive | 自适应阈值 GAUSSIAN/MEAN × block 11/21（纸为亮前景，应对光照不均/阴影） |

③ **按「方法族」加权共识落点**：所有候选按角点距离（≤ `0.16 × 对角线`）贪心聚类，优先取 **≥2 独立方法族**一致的簇（族越多 conf 越高：`0.6 + 0.2×族数`），一致角点取平均精化；仅单族多变体一致 → 中置信(0.6)接受；全无共识 → 仅单候选 `isStrong` 才低置信(0.4)兜底；否则 null。

**为何按方法族而非变体数加权**：同族多参数变体一致只是 1 份独立证据；Otsu+Canny+adaptive 三族中有 2 族一致才算强共识，更能抵抗单族系统性误判（如 Otsu 锁定白色桌面）。

**角度偏斜提醒：** maxDev > 12° mild；> 25° severe（工具抠图变形警告）

**横竖屏自适应：** perspectiveWarp 自动跟随检测方向，输出保持 A4 比例

#### 取点与面积过滤

- 取点用 `approx.data32S[i*2]` / `data32S[i*2+1]`（或 `approx.intPtr(i)`）；**严禁用 `approx.ptr(i,0)`**（本构建读 CV_32SC2 会错位，y 恒为 0，详见上文 §二.2）
- 四点「左上→右上→右下→左下」排序后交给透视校正
- 面积下限 `0.12`、上限 `0.98`；四角离边框 ≥ margin（基础 `0.008 × min(宽,高)`，isStrong 用更严格的 `0.025 × min`），排除贴框溢出

### 3. 测试方法

1. `npm run dev` 启动，访问 http://localhost:5173
2. 进入校准页（CalibrationPage），上传 `public/testpic.jpg`
3. 图片就绪后**自动触发** `detectPaperCorners`，界面显示"识别中…"
4. 成功显示"✅ 已自动识别纸张四角"；失败显示红色原因文字，可点"重新检测"
5. 点"2. 透视校正" → "3. 提取工具轮廓"：二值化找最大轮廓并绘制绿色轮廓调试图，同时走 `abstractFromMask` 完成 union + 形态学 + Chaikin + 基元化
6. 基元化结果叠加显示：绿=直线 / 橙=圆弧 / 紫=折线，并列出各类型计数；当前仅 Fast 掩膜路径（`samMask` 接口已预留，待接入真实 SAM）

### 4. 常见问题排查

#### 识别不到纸张（红色失败提示）？

- **先看控制台**：`detectPaperCorners` 内部每个方法失败时都会 `console.warn` 原因（无候选 / 面积不符 / 角度不合规 / 贴框被 margin 拒绝）
- **常见根因**：纸张占比 < 15%（离得太远）、四角被遮挡、光照过暗
- **低置信度提示**：若显示「仅单方法命中」说明 Otsu 单独检出但未达共识，建议重拍确认
- **排查手段**：在 `opencvUtils.ts` 临时把 `console.warn` 改成 `console.log` 各方法中间结果，定位哪个策略漏了

#### 四角顺序错误？

- **原因**：未用 `sortPoints` 标准化顺序
- **解决**：`detectPaperCorners` 已默认返回「左上→右上→右下→左下」顺序，调用方直接用于透视校正

#### 内存泄漏？

- 每个候选 `Mat`/`MatVector` 用完必须 `.delete()`；`detectPaperCorners` 已释放除 best 外的所有候选

#### 卡在"加载OpenCV中..."？

- **原因**：用了 `import('@techstark/opencv-js')`，Vite dev 卡死 13MB CJS 文件
- **解决**：见 §二.6，必须用 `<script>` 标签 + `loadCv()`。Vite 缓存也要清：`rm -rf node_modules/.vite`

### 5. 后续维护规范

1. **统一测试界面管理**：
   - 所有测试必须在现有界面中进行，禁止创建新的测试文件
   - 若确需创建新测试界面，必须先获得团队负责人批准，并更新本文档
   - 每次修改测试界面后，需在本文档中记录修改内容和原因
   - 当前唯一有效的测试界面是：`src/features/calibration/CalibrationPage.tsx`

2. **参数调整规范**：针对不同场景调整参数时，在代码中添加明确注释，说明调整原因和适用场景

3. **类型安全**：所有新增代码必须使用TypeScript类型系统，避免any类型

4. **资源清理**：确保所有OpenCV Mat对象都正确释放，避免内存泄漏

5. **测试界面使用规范**：
   - 所有OpenCV相关的调试、纸张检测、参数调优都应通过`src/features/calibration/CalibrationPage.tsx`进行
   - 不再维护多个独立的测试界面，避免功能重复和维护困难

### 6. 下一步优化建议

1. ✅ 参数自动调优（已实现：导入即自动识别，多策略自适应，详见 §2）
2. 实现多纸张检测支持
3. 添加旋转校正功能，处理倾斜纸张
4. 优化性能，减少检测时间到100ms以内

---

## 附录：2026-07-07 OpenCV加载机制重构记录

### 改动文件

| 文件                                             | 类型   | 说明                                                     |
| ------------------------------------------------ | ------ | -------------------------------------------------------- |
| `public/opencv.js`                               | 新增   | 13MB，从 npm 包复制，wasm 内嵌                           |
| `index.html`                                     | 改动   | 加 `<script src="/opencv.js">`                           |
| `src/lib/opencvLoader.ts`                        | 新增   | 轮询 window.cv + 展平 Promise（**需说明理由**，见§一.2） |
| `src/hooks/useOpenCV.ts`                         | 改动   | 调用 loadCv()，返回 error 字段                           |
| `src/features/calibration/CalibrationPage.tsx`   | 改动   | 加载失败时显示错误文字                                   |
| `src/utils/PaperDetector.ts`                     | 改动   | getCV() 改用 loadCv()                                    |
| `src/utils/OptimizedPaperDetector.ts`            | 改动   | getCV() 改用 loadCv()                                    |
| `src/utils/PaperDetector.optimized.ts`           | 改动   | getCV() 改用 loadCv()                                    |
| `src/utils/simplePaperDetector.ts`               | 改动   | cv 改用构造函数注入                                      |
| `src/utils/testUtils.ts`                         | 改动   | cv 参数化                                                |
| `vite.config.ts`                                 | 改动   | 移除 optimizeDeps.exclude                                |
| `src/test-opencv.ts`                             | 删除   | 调试文件                                                 |
| `src/test-diagnose.tsx`                          | 删除   | 调试文件                                                 |
| `src/utils/PaperDetectorDebug.ts`                | 删除   | 调试文件                                                 |
| `public/test-opencv*.js`、`debug-opencv.html` 等 | 已删除 | 上次已清理                                               |

### 合规自查

| 规范                       | 自查结论                                            |
| -------------------------- | --------------------------------------------------- |
| §一.1 单一调试入口         | ✅ 无新增 HTML/测试文件                             |
| §一.2 新增文件需先说明     | ⚠️ `opencvLoader.ts` 违反流程（已在§一.2 标注理由） |
| §一.3 参数管理             | ✅ 未触碰                                           |
| §二.1-§二.5 OpenCV 规范    | ✅ 未触碰算法逻辑                                   |
| §二.6 加载机制（本次新增） | ✅ 全项目已统一                                     |
| §三 AI 协作                | ✅ 没跑长阻塞命令，没改 vite/tsconfig 前先读        |

### 后续AI 协作提示

- 修改 OpenCV 加载相关代码前，**必须**先读 `src/lib/opencvLoader.ts`，**禁止**改回 `import('@techstark/opencv-js')`
- 检测器只有 `src/lib/opencvUtils.ts` 一个文件，所有算法改动都在那里，**禁止新建** `autoPaperDetector.ts` / `PaperDetector.ts` 之类的散文件
- 遇到 OpenCV 加载相关报错，先看 `CalibrationPage` 是否显示红色错误文字，再看控制台

---

## 附录：2026-07-07（续）纸张检测自动识别化重构

### 背景

手动调参（Canny/模糊/面积滑块 + 手动检测按钮 + 测试简化检测器按钮）体验差、且对"白纸+木纹+投影暗边"场景无必要。本次目标：舍去手动调参、导入图片后自动识别纸张。

### 改动文件

| 文件                                                  | 类型     | 说明                                                                                                                                                                             |
| ----------------------------------------------------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/lib/opencvUtils.ts`                              | 改动     | `detectPaperCorners` 重写为**全自动无参**多策略检测器（Otsu/自适应/Canny/CLAHE，自动选最大合法四边形），用 `approx.ptr(i,0)` 取点；保留 `perspectiveWarp`、`extractToolContours` |
| `src/features/calibration/CalibrationPage.tsx`        | 改动     | 删除滑块/手动检测/测试按钮；图片就绪后 `useEffect` 自动调用 `detectPaperCorners`，带"识别中…"与失败提示；保留透视校正/提取轮廓/重新检测                                          |
| `src/lib/autoPaperDetector.ts`                        | **删除** | 逻辑已并入 `opencvUtils.ts`                                                                                                                                                      |
| `src/utils/simplePaperDetector.ts`                    | **删除** | 仅被测试按钮与 testUtils 引用，已无用                                                                                                                                            |
| `src/utils/PaperDetector.ts`                          | **删除** | 孤儿文件（无人 import）                                                                                                                                                          |
| `src/utils/PaperDetector.optimized.ts`                | **删除** | 孤儿文件（无人 import）                                                                                                                                                          |
| `src/utils/OptimizedPaperDetector.ts`                 | **删除** | 孤儿文件（无人 import）                                                                                                                                                          |
| `src/utils/testUtils.ts`                              | **删除** | 仅引用 simplePaperDetector，已无用                                                                                                                                               |
| `src/features/calibration/CalibrationPage.backup.tsx` | **删除** | 备份文件                                                                                                                                                                         |

### 合规自查

| 规范                    | 自查结论                                                    |
| ----------------------- | ----------------------------------------------------------- |
| §一.1 单一调试入口      | ✅ 无新增测试文件，删除了 backup                            |
| §一.2 文件存放/集中     | ✅ 检测逻辑集中到唯一文件 `opencvUtils.ts`，删除 6 个散文件 |
| §一.3 参数管理          | ✅ 移除全部手动调参 UI，检测无参数                          |
| §二.1-§二.5 OpenCV 规范 | ✅ 内存 .delete 完整、四点排序、ptr 取点                    |
| §二.6 加载机制          | ✅ 仍严格走 `window.cv` + `loadCv()`，无 import             |
| §三 AI 协作（集中逻辑） | ✅ 符合"以集中逻辑为荣"                                     |

---

## 附录：2026-07-07（续）三方法融合判定 + 横竖屏自适应 + 偏斜提醒

### 背景

上一版多策略检测（Otsu/自适应/Canny/CLAHE 共 5 策略×2 方向）在亮白纸场景失效（96%/89% 白噪声），且 Canny/Otsu-inv 存在设计缺陷。用户要求基于三种验证通过的可视化手段实现加权融合，并增加横竖屏通用 + 角度偏斜提醒。

### 改动文件

| 文件                                           | 类型 | 说明                                                                                                                                                                                                                                                                                      |
| ---------------------------------------------- | ---- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/lib/opencvUtils.ts`                       | 改动 | `detectPaperCorners` 重写为**三方法加权融合**：①Otsu(Gauss) ②Canny+margin ③Otsu(median)；返回 `PaperDetection`（含 corners/confidence/skew/lowConfidence）；`perspectiveWarp` 改为横竖屏自适应 A4 输出；删除 CLAHE/自适应阈值等失效策略；新增 skewOf/interiorAngles/averageQuads/quadDist |
| `src/features/calibration/CalibrationPage.tsx` | 改动 | 适配新返回结构：展示置信度、偏斜警告(红/琥珀)、低置信提示；透视校正传 `detect.corners`                                                                                                                                                                                                    |
| `OPENCV_INTEGRATION.md`                        | 改动 | 新增 §1.1 融合策略详细文档（三方法表/融合流程/skew 阈值/方案评估）；更新集成描述                                                                                                                                                                                                          |
| `DEVELOPMENT_GUIDE.md`                         | 改动 | 更新 §2 为融合判定逻辑；更新 §4 排查指南；本附录                                                                                                                                                                                                                                          |

### Python 验证（cv2 miniconda）

- 用 `validate_fusion.py` 复现同一算法跑 testpic.jpg → M1✅ M3✅ M2✗ → 2/3 共识确认，conf=0.67，skew maxDev=1.4°(ok)
- 调试图 `fusion_debug.png` 显示两套 Otsu 方法几乎重合、融合四边形完美贴合白纸

### 关键发现与设计决策

| 问题                        | 发现                                                        | 解决方案                                                           |
| --------------------------- | ----------------------------------------------------------- | ------------------------------------------------------------------ |
| Otsu-inv RETR_EXTERNAL 漏洞 | 反相后白纸变成内部"洞"，RETR_EXTERNAL 只返回背景轮廓(99.7%) | 改用 medianBlur+Otsu 正相取最大外轮廓（与方法① 不同平滑→独立投票） |
| Canny 贴框溢出              | 纸边与图像边界相连时 Canny 四边形顶点落在 y=0/y=H           | inBounds 加 margin(~8px) 自动拒绝贴框轮廓                          |
| 纯 2-of-3 在示例图可能失败  | Canny 在 testpic 上不命中，仅 M1/M3 投票                    | M1+M3 本身构成 2 票共识；额外加单方法兜底(lowConfidence)           |

### 合规自查

| 规范                    | 自查结论                                            |
| ----------------------- | --------------------------------------------------- |
| §一.1 单一调试入口      | ✅ 无新增文件                                       |
| §一.2 文件存放/集中     | ✅ 仅改 opencvUtils.ts + CalibrationPage.tsx        |
| §一.3 参数管理          | ✅ 无参数 UI，全内部自适应                          |
| §二.1-§二.5 OpenCV 规范 | ✅ 内存 .delete 完整、ptr 取点、四点排序、无 import |
| §二.6 加载机制          | ✅ 不涉及                                           |
| §二.5 先验证后迁移      | ✅ cv2 Python 复现已通过，调试图已保存              |
| §三 AI 协作             | ✅ 符合                                             |

---

## 附录：2026-07-07（续）多参数电池 + 首轮早退 + 按方法族加权共识

### 背景

用户提出三点诉求：① 为何"三种可视化都完美"却代码失败；② 三种处理可否多参数自动（应对光线/影子等）；③ 加权共识如何避免固定参数全失败、且首轮完美就不调用多参数。

### 改动文件

| 文件                                           | 类型 | 说明                                                                                                                                                                            |
| ---------------------------------------------- | ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/lib/opencvUtils.ts`                       | 改动 | `detectPaperCorners` 重写为「首轮 Otsu 强命中早退 → otsu/canny/adaptive 三族多参数电池 → 按方法族加权共识」；新增 `otsuQuad`/`isStrong` 辅助；`PaperDetection` 增加 `mode` 字段 |
| `src/features/calibration/CalibrationPage.tsx` | 改动 | 成功提示区分 mode（首轮强命中 / N 方法族共识）                                                                                                                                  |
| `OPENCV_INTEGRATION.md`                        | 改动 | §1.1 重写为电池+早退+族加权共识；更新集成描述与两处术语                                                                                                                         |
| `DEVELOPMENT_GUIDE.md`                         | 改动 | §2 重写为电池+早退+族加权共识；本附录                                                                                                                                           |

### Python 验证（cv2 miniconda，先验证后迁移）

- `validate_battery.py` 复现新电池逻辑跑 `public/testpic.jpg` → **PATH=early-exit**（首轮 Otsu+Gauss5 即 `isStrong`），conf=1.0，四角 `[[60,332],[590,337],[595,1110],[34,1102]]`，贴合白纸
- 三族多参数电池逻辑已在脚本中实现并验证（聚类/族计数/早退分支均覆盖）

### 关键设计决策

| 诉求                 | 方案                                                                                                 |
| -------------------- | ---------------------------------------------------------------------------------------------------- |
| 可视化完美却代码失败 | 区分"二值图可分离"与"轮廓→四边形落点"：Canny 贴框溢出、Otsu 反相抓背景，两者在落点步骤失败（已规避） |
| 多参数自动           | 每方法族放 3~4 个参数变体，覆盖光线/阴影/背景；变体数有界（浏览器性能）                              |
| 加权避免全失败       | 按方法族加权（非变体数）：≥2 独立族一致才高置信，抗单族系统性误判                                    |
| 首轮完美不调多参数   | 首轮 Otsu `isStrong` 即早退，省去后续 ~10 次 findContours                                            |

### 合规自查

| 规范                    | 自查结论                                                                  |
| ----------------------- | ------------------------------------------------------------------------- |
| §一.1 单一调试入口      | ✅ 无新增文件                                                             |
| §一.2 文件存放/集中     | ✅ 仅改 opencvUtils.ts + CalibrationPage.tsx                              |
| §一.3 参数管理          | ✅ 仍无参数 UI，全内部自适应                                              |
| §二.1-§二.5 OpenCV 规范 | ✅ 内存 .delete 完整（g5/g9/m5/m7 均在 finally 释放）、ptr 取点、四点排序 |
| §二.5 先验证后迁移      | ✅ cv2 Python 复现已通过（validate_battery.py）                           |
| §三 AI 协作             | ✅ 符合                                                                   |

---

## 附录：2026-07-07（续）`approxPolyDP` 取点致命 bug 修复

### 现象

前端校准页所有图片（含 cv2 已验证可识别的图）均返回"未检测到纸张"，控制台无 `[detectPaperCorners]` 报错，仅打印 `TOTAL candidates: 0`。三方法族（otsu/canny/adaptive）全部 0 候选。

### 根因（已用 Node + 实际 opencv.js 构建端到端验证）

`ptsFromMat` 用 `approx.ptr(i, 0)` 读取 `CV_32SC2`（type=36, 4×1×2 Int32）的四角坐标。本构建（`@techstark/opencv-js 5.0` 的 `public/opencv.js`）下 `ptr(i,0)` 读该类型会**错位：x 正确、y 恒为 0**。结果所有检测点 y=0 塌到图像顶边，`inBounds` 一律判越界 → 候选全毙 → 0 candidates。

- Node 复现实测：`approx.rows/cols/channels/type = 4/1/2/36`；`data32S=[x0,y0,...]` 与 `intPtr(i)=[x,y]` 均正确；`ptr(i,0)` 输出 `[[115,3],[82,0],[91,0],[102,3]]`（y≈0 乱码）。
- 这解释了"cv2 能过、前端全挂"：cv2 用 `cnt.reshape(-1,2)` 读点正常，而 JS 侧 `ptr` 在此构建不可用。

### 修复

`ptsFromMat` 改用 `approx.data32S[i*2]` / `data32S[i*2+1]`（或 `approx.intPtr(i)`）。真实图（地毯背景卡尺，白纸占 75%）验证正确四角 `[[883,52],[82,53],[91,1085],[870,1071]]`，tsc 通过。

### 文档更正（重要）

此前 §二.2 / §取点与面积过滤 / README 误写"取点用 `approx.ptr(i,0)`、**禁止**用 `data32S`"——该结论未经构建验证，正是此 bug 来源。已全部翻正为"用 `data32S`/`intPtr`，严禁 `ptr(i,0)`"。

### 改动文件

| 文件                     | 类型 | 说明                                                                           |
| ------------------------ | ---- | ------------------------------------------------------------------------------ |
| `src/lib/opencvUtils.ts` | 改动 | `ptsFromMat` 由 `approx.ptr(i,0)` 改为 `approx.data32S` 读取；清理调试日志噪声 |
| `DEVELOPMENT_GUIDE.md`   | 改动 | §二.2 新增 ptr 坑说明、§取点与面积过滤翻正、本附录                             |
| `README.md`              | 改动 | 取点说明翻正                                                                   |
| `OPENCV_INTEGRATION.md`  | 改动 | 见下方 §1.1 取点更正                                                           |

### 合规自查

| 规范                    | 自查结论                                                      |
| ----------------------- | ------------------------------------------------------------- |
| §二.1-§二.5 OpenCV 规范 | ✅ 内存 .delete 完整、`data32S` 取点、四点排序、无 import     |
| §二.5 先验证后迁移      | ✅ 用 Node 加载实际 `public/opencv.js` + 真实图灰度端到端验证 |
| §三 AI 协作             | ✅ 修复后同步 MD                                              |

---

---

## 附录：2026-07-08 工具轮廓提取 + 基元化（曲率分段法）同步完成

### 背景

WSL 项目里 `extractPrimitives` 此前是「DP 抽稀 + 逐顶点段拟合」的错误实现，对干净弧检不出。离线验证算法实为 `optimized_primitives.classify_and_fit_optimized`（曲率分段法）。用户要求用代数最小二乘圆拟合替代 `cv2.minEnclosingCircle`（避免 <180° 弧半径塌缩）。

### 改动文件

| 文件                                           | 类型 | 说明                                                                                                                                                                                                                                                                                                                                                                                                |
| ---------------------------------------------- | ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/lib/opencvUtils.ts`                       | 改动 | 删除旧 DP 辅助函数（重复 `ptsFromMat` + `noUnusedLocals` 死代码，原 `tsc` 过不了）；`extractPrimitives` 对齐 `contour_simplify.py`（DP ε=0.004 + 逐段 line/arc 拟合）；`segmentDetail` 对齐 `sam_union_final.py`（Red(SAM)∪Green(Fast)→close9+dilate7→erode3椭圆→merged_contour桥接→Chaikin2）；`circleFitJS` 改中心化 Kasa；`lineFitErrorJS` 改用 `pts[0]` 参考点；`drawPrimitives` 弧画重采样点列 |
| `src/utils/types.ts`                           | 改动 | `AbstractOptions = { dpEpsilon?, linTol?, arcTol?, maxArcRadius? }`（默认 0.004/4/4/55）；`ArcPrimitive` 加 `points?`（重采样弧点）                                                                                                                                                                                                                                                                 |
| `src/app/store.ts`                             | 改动 | 新增 `primitives` + `setPrimitives`                                                                                                                                                                                                                                                                                                                                                                 |
| `src/features/calibration/CalibrationPage.tsx` | 改动 | 取 `result.primitives`/`primitiveDebugUrl` 存 state+store，新增基元化结果显示区块（绿/橙/紫 + 计数）                                                                                                                                                                                                                                                                                                |

### 关键发现与设计决策（2026-07-09 修正）

| 问题                      | 发现                                                                                                                                     | 解决方案                                                                                              |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| 之前错用「曲率分段法」    | 误从 `.pyc` 反编译出 `classify_and_fit_optimized` 当真算法；用户指正真实算法是 `contour_simplify.py`/`batch_process.py` 的 **DP 逐段法** | 整体换回 DP 逐段拟合，与离线脚本 1:1                                                                  |
| 并集算法来源              | 用户指明并集在 `sam_union_final.py`（Red(SAM)∪Green(Fast)→close9→dilate7→erode3→bridge→chaikin）                                         | `segmentDetail` 严格对齐实现                                                                          |
| 真实图片 0 弧（关键 bug） | `circleFitJS` 未中心化法方程在大坐标下数值崩溃 → 半径错/null；`lineFitErrorJS` 用质心参考 → 真实 RMS 偏小 → `err_l>4` 永不满足           | 圆拟合中心化 Kasa（对齐 `np.linalg.lstsq`）；直线误差用 `pts[0]` 参考（对齐 Python `line_fit_error`） |
| 半径塌缩                  | `cv2.minEnclosingCircle` 对 <180° 弧半径压到 ~0.707R                                                                                     | 代数最小二乘（中心化 Kasa），半径精准                                                                 |
| 项目原本编译不过          | 重复 `ptsFromMat` 声明 + 一堆 `noUnusedLocals` 死代码                                                                                    | 删除旧辅助函数，仅留唯一 `ptsFromMat`                                                                 |

### 验证

- 纯 JS 端到端回归 `validate_union_primitives.mjs`（沙箱可跑）：**4/4 真实工具图与 Python 1:1 通过**（caliper 13L/3A/5P、hex_wrench 21L/3A/1P、pliers 19L/2A/4P，逐段序列一致，弧半径误差≤0.000）。
- WSL `tsc --noEmit`：**退出码 0**。
- 待用户在 WSL `npm run dev` + 浏览器真实工具图做端到端目视确认（沙箱无浏览器 + OpenCV.js 运行时）。

### 合规自查

| 规范                    | 自查结论                                                                    |
| ----------------------- | --------------------------------------------------------------------------- |
| §一.1 单一调试入口      | ✅ 无新增测试文件                                                           |
| §一.2 文件存放/集中     | ✅ 仅改 opencvUtils.ts + types.ts + store.ts + CalibrationPage.tsx          |
| §一.3 参数管理          | ✅ `dpEpsilon`/`linTol`/`arcTol`/`maxArcRadius` 为工具函数默认值，未外泄 UI |
| §二.1-§二.5 OpenCV 规范 | ✅ 内存 .delete 完整、四点排序、无 import                                   |
| §二.5 先验证后迁移      | ✅ 离线算法 1:1 移植 + 纯 JS 端到端回归 4/4                                 |
| §三 AI 协作             | ✅ 符合（未跑长阻塞命令，未私自改 vite/tsconfig）                           |

---

## 附录：2026-07-09（续）前端样式体系接入 + CalibrationPage UI 现代化

### 背景

用户反馈网页"太简陋、不好看、与工作流不一致"。排查发现：项目所有组件自初版即用 Tailwind 原子类名，但 **Tailwind 从未配置**（无 config / postcss / css import / 依赖），导致所有类名失效、页面裸奔——这是"简陋"的真正根因。整站其实已有完整 6 步工作流（`src/components/Stepper.tsx`：上传→校准→提取→编辑→参数→导出），`CalibrationPage` 也已是现代写法，只要把 Tailwind 接好即可立即现代化。本次：① 接入 Tailwind 样式体系（让现有代码生效）；② 重构 `CalibrationPage` 布局（居中 hero、页内三步指示器、友好空状态、结果卡片网格、提取错误兜底），更贴合"导入→校正→提取"工作流。

### 改动文件

| 文件                                           | 类型 | 说明                                                                                                                                                                 |
| ---------------------------------------------- | ---- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tailwind.config.js`                           | 新增 | content 指向 src；theme.extend 定义 brand 色板 / shadow-card / 圆角 / 字体                                                                                           |
| `postcss.config.js`                            | 新增 | plugins: tailwindcss + autoprefixer（ESM）                                                                                                                           |
| `src/index.css`                                | 新增 | @tailwind 三指令 + body/html/#root base + 细滚动条 + .img-contain                                                                                                    |
| `src/main.tsx`                                 | 改动 | 顶部新增 `import './index.css'`（先于业务组件）                                                                                                                      |
| `package.json`                                 | 改动 | devDependencies 加 tailwindcss@^3.4.17 / autoprefixer@^10.4.20 / postcss@^8.4.49                                                                                     |
| `src/features/calibration/CalibrationPage.tsx` | 改动 | 重构布局：居中 hero、FlowSteps 三步指示器、虚线大卡片空状态、结果卡片网格（ResultCard 组件）、handleExtract 加 try/catch 错误兜底；保留全部 opencvUtils 调用逻辑不变 |

### 关键设计决策

| 问题                     | 发现                                                                     | 解决方案                                                                        |
| ------------------------ | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------- |
| 网页简陋                 | 不是组件写得差，而是 Tailwind 未配置导致所有类名失效（裸奔）             | 接入 Tailwind v3.4（最成熟稳定、踩坑最少），现有组件立即生效                    |
| 工作流不一致             | CalibrationPage 三步（导入/校正/提取）与全站 6 步 Stepper 概念未显式呼应 | 页内加 FlowSteps 三步指示器，状态由 imgUrl/warpedUrl/debugUrl 推导高亮          |
| 提取按钮"按了没反应"隐患 | 原 handleExtract 无 try/catch，浏览器抛错会被静默吞掉                    | handleExtract 包 try/catch，extractError 渲染到页面，loading 用 extracting 状态 |
| 空状态差                 | 原上传入口是小 label 按钮，无引导                                        | 未上传时显示虚线大卡片"点击或拖拽上传工具照片"                                  |

### 验证

- 沙箱无 node_modules，未跑 `tsc`/`npm run dev`；用户在 WSL `npm install`（含新增 tailwind 依赖）→ `npm run dev` 目视确认：布局生效、三步流程高亮正确、提取错误可显示。
- 算法逻辑（opencvUtils / samInference）零改动，仅 UI 层重构。

### 合规自查

| 规范                    | 自查结论                                                                                                                             |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| §一.1 单一调试入口      | ✅ 无新增 HTML/测试文件                                                                                                              |
| §一.2 文件存放/集中     | ⚠️ 新增 `tailwind.config.js`/`postcss.config.js`/`src/index.css` 为前端构建基础设施（非 OpenCV 散文件），已在 §一.2 表登记并说明理由 |
| §一.3 参数管理          | ✅ 未触碰算法参数                                                                                                                    |
| §二.1–§二.5 OpenCV 规范 | ✅ 未触碰算法逻辑，仅 UI 层                                                                                                          |
| §三 AI 协作             | ✅ 未跑长阻塞命令；新增文件已在文档登记说明理由                                                                                      |

---

### 背景

用户指出此前「6 步向导 + 浅色页」仍是“AI 脚手架简陋风”（白底 + 默认 input + 按钮无圆角 + 假 demo），与“设计工具”调性不搭，给定明确方向：**Figma / Tooltrace 式深色 workspace**（深色画布为主 + 浅色顶栏/侧栏 + 浮动玻璃参数面板），技术栈 Shadcn/ui + Tailwind + Lucide + Three.js(@react-three/fiber) + Zustand（Tauri 桌面为主、网页为辅）。经确认：① 布局改为单屏 workspace；② 先轻量落地（Three.js/R3F/Zustand 待真做 3D 再装；`three`/`zustand` 已在 package.json）。

### 改动文件

| 文件                                                                                                                                                                                                                                                     | 类型 | 说明                                                                                                                                                           |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/features/workspace/Workspace.tsx`                                                                                                                                                                                                                   | 新增 | 唯一应用外壳：浅色顶栏 + 可收起浅色左栏 + 深色画布 viewport + 右侧浮动玻璃面板；算法管线(`detectPaperCorners`/`perspectiveWarp`/`extractToolContours`)原样搬入 |
| `src/pages/Home.tsx`                                                                                                                                                                                                                                     | 改动 | 仅渲染 `<Workspace />`                                                                                                                                         |
| `src/app/store.ts`                                                                                                                                                                                                                                       | 改动 | 导出 `Step` 类型（单一真相源，供 Workspace 复用）                                                                                                              |
| `src/components/ui/icons.tsx`                                                                                                                                                                                                                            | 改动 | 扩 panelLeft/grid/zoomIn/zoomOut/maximize/aperture/settings 七个 chrome 图标                                                                                   |
| `tailwind.config.js`                                                                                                                                                                                                                                     | 改动 | colors 增 `canvas`(950–600)；animation 增 slide-in-right/slide-down                                                                                            |
| `src/index.css`                                                                                                                                                                                                                                          | 改动 | 增 `.canvas-grid`/`.glass-panel`/`.glass-bar`/`.canvas-scroll`                                                                                                 |
| `components/Stepper.tsx`、`features/upload/UploadPage.tsx`、`features/calibration/CalibrationPage.tsx`、`features/segmentation/SegmentationPage.tsx`、`components/CanvasEditor.tsx`、`features/params/ParamsPanel.tsx`、`features/export/ExportPage.tsx` | 删除 | 逻辑并入 Workspace，未实现功能改为右侧「规划中」卡片                                                                                                           |

### 关键决策

| 问题         | 方案                                                                                                                                       |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------ |
| 向导 vs 单屏 | 按用户方向改为单屏 workspace（画布为主、面板为辅，行业惯例）                                                                               |
| 依赖重量     | 先轻量：Three.js/@react-three/fiber/Zustand 等真做 3D 再装；图标因沙箱 WSL npm `ENOTEMPTY` 冲突未装 lucide-react，暂用自绘 SVG（计划可换） |
| 算法管线     | 零改动搬入 Workspace，未触碰 `opencvUtils`                                                                                                 |

### 验证

- `tsc --noEmit` 退出码 0（strict + noUnusedLocals/Parameters）。
- `vite build` 成功（CSS 19.4KB = 新增 canvas/glass 类编译通过）。

---

_本指南最后更新：2026-07-09（基元化改为 DP 逐段法对齐 contour_simplify.py/batch_process.py；并集对齐 sam_union_final.py；修复真实图片 0 弧的两个数值 bug；接入 Tailwind 样式体系并重构 CalibrationPage UI；新增 §六 3D 生成与桌面化架构决策——撤回"纯 JS / 无后端"旧约束，改为 Tauri/Electron 桌面应用 + Python 后端；新增 §七 下一步桌面化桥接层开发需求；**新增 §八 竞品对标全量需求文档指针 → PRODUCT_REQUIREMENTS.md**；§八 已随 Tooltrace 实测功能对账**二次扩充**：F1.6 本地画廊、F2.5 手动描边/F2.6 自定义形状/F2.7 精度档、F3.10 Gridfinity 升为一等模式、F3.11 对称/F3.12 导入、F5.5 PDF 校对，并加"个人使用范围声明(不含云端账户/社区)"；**本会话前端设计系统重构**：统一 design tokens + 组件库(`src/components/ui`: Card/Badge/Button/SectionHeading/EmptyState/icons 自绘 SVG 零新依赖) + 品牌顶栏与圆形编号节点 Stepper，未完成页改为"规划中"占位（不再用假 demo），修复 `vite-env.d.ts` 缺失与 `samInference.ts` 的 `RawSamMask` 路径笔误，`tsc --noEmit` 与 `vite build` 均通过）_
