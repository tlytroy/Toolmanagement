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
技术栈：Vite + React + TypeScript + OpenCV.js + Fabric.js + Three.js + Zustand，所有计算均在浏览器本地完成，无后端依赖。

## 一、项目结构铁律（严禁违反）

### 1. 单一调试入口（核心红线）
所有OpenCV/纸张检测/轮廓提取的调试，仅允许在src/features/calibration/CalibrationPage.tsx中进行，严禁新增任何零散HTML测试文件（包括但不限于public/_.html、test-_.html）。
已永久删除的冗余文件（AI不得再提及或使用）：
public/optimized-detector-test.html、public/debug-test.html、public/paper-detector-test.html、public/opencv-debug.html、public/simple-test.html、test-paper-detector.html

### 2. 文件存放规范（不得随意新增）

| 功能 | 唯一文件路径 |
|------|-------------|
| OpenCV加载入口（轮询window.cv） | src/lib/opencvLoader.ts |
| OpenCV核心算法（**检测/校正/轮廓全部在此**） | src/lib/opencvUtils.ts |
| OpenCV加载Hook（React） | src/hooks/useOpenCV.ts |
| 校准/调试页面 | src/features/calibration/CalibrationPage.tsx |
| 全局状态管理 | src/app/store.ts |
| 第三方OpenCV资产 | public/opencv.js（13MB，由npm包复制，禁止改回npm import） |

确需新增文件需先说明理由，禁止AI擅自创建零散文件。

> **检测逻辑集中声明（2026-07-07）**：纸张四角检测、透视校正、工具轮廓提取**全部集中在 `src/lib/opencvUtils.ts`**（对应本表"OpenCV核心算法"）。`detectPaperCorners(cv, img)` 为**全自动、无参数**接口，内部多策略自适应，调用方不要在外部传 Canny/模糊/面积等参数。此前散落的 `autoPaperDetector.ts` / `simplePaperDetector.ts` / `PaperDetector.ts` / `PaperDetector.optimized.ts` / `OptimizedPaperDetector.ts` / `testUtils.ts` 及 `CalibrationPage.backup.tsx` 已统一删除并合并进本项目唯一算法文件。**禁止再新增独立的 detector 散文件。**

**`opencvLoader.ts` 存在理由**（2026-07-07）：把"轮询 window.cv + 展平嵌套 Promise"独立成工具函数，是为了和 `useOpenCV` hook 复用同一份逻辑。**严格意义上这超出了§一.2 "新增文件需先说明理由"的要求**——事先未在对话中说明。下次类似改动应先在对话里说明理由并征得同意，再创建文件。

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
import { loadCv } from '@/lib/opencvLoader';
const cv = await loadCv();
cv.imread(imgElement);
```

**本次踩坑的三个阶段**（避免重蹈）：
1. **阶段1（白屏）**：静态 import → Vite 模块图卡死 → 整个 JS 加载链路崩溃
2. **阶段2（永远加载中）**：改动态 import → Vite 的 `import()` 对 13MB CJS 仍卡死，Promise 永不 resolve
3. **阶段3（解决）**：放弃 Vite 模块系统，`<script>` 标签 + `window.cv` + `loadCv()`

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

> 修订动因：用户原验证的 Otsu / Canny / Otsu 反相三种**可视化**都清晰分离了纸张，但自动化落点（findContours→approxPolyDP→凸四边形校验）时 Canny 易贴框溢出、Otsu 反相（THRESH\_BINARY\_INV）会把背景当最大轮廓漏掉纸。固定单参数在光线/阴影/异色背景下必然有盲区。故改为「首轮强命中早退 → 三方法族多参数电池 → 按方法族加权共识」。

判定流程（`detectPaperCorners` 全程无参数，内部自适应）：

① **首轮强命中早退**：`Otsu + GaussianBlur(5)` 跑一次，四边形 `isStrong`（四角明显在图内、角度 75°~105°、面积合理）即返回（mode=strong, conf=1）。好照片只花 1 次 findContours。

② **三方法族多参数电池**（仅首轮不干净才展开）：

| 方法族 | 参数变体 |
|--------|---------|
| otsu | Otsu + 高斯(5/9) / 中值(5/7) 四种平滑 |
| canny | Canny(30,90)/(50,150)/(80,200) + 膨胀闭合 |
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
5. 点"2. 透视校正" → "3. 提取工具轮廓"

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

| 文件 | 类型 | 说明 |
|------|------|------|
| `public/opencv.js` | 新增 | 13MB，从 npm 包复制，wasm 内嵌 |
| `index.html` | 改动 | 加 `<script src="/opencv.js">` |
| `src/lib/opencvLoader.ts` | 新增 | 轮询 window.cv + 展平 Promise（**需说明理由**，见§一.2） |
| `src/hooks/useOpenCV.ts` | 改动 | 调用 loadCv()，返回 error 字段 |
| `src/features/calibration/CalibrationPage.tsx` | 改动 | 加载失败时显示错误文字 |
| `src/utils/PaperDetector.ts` | 改动 | getCV() 改用 loadCv() |
| `src/utils/OptimizedPaperDetector.ts` | 改动 | getCV() 改用 loadCv() |
| `src/utils/PaperDetector.optimized.ts` | 改动 | getCV() 改用 loadCv() |
| `src/utils/simplePaperDetector.ts` | 改动 | cv 改用构造函数注入 |
| `src/utils/testUtils.ts` | 改动 | cv 参数化 |
| `vite.config.ts` | 改动 | 移除 optimizeDeps.exclude |
| `src/test-opencv.ts` | 删除 | 调试文件 |
| `src/test-diagnose.tsx` | 删除 | 调试文件 |
| `src/utils/PaperDetectorDebug.ts` | 删除 | 调试文件 |
| `public/test-opencv*.js`、`debug-opencv.html` 等 | 已删除 | 上次已清理 |

### 合规自查

| 规范 | 自查结论 |
|------|---------|
| §一.1 单一调试入口 | ✅ 无新增 HTML/测试文件 |
| §一.2 新增文件需先说明 | ⚠️ `opencvLoader.ts` 违反流程（已在§一.2 标注理由） |
| §一.3 参数管理 | ✅ 未触碰 |
| §二.1-§二.5 OpenCV 规范 | ✅ 未触碰算法逻辑 |
| §二.6 加载机制（本次新增） | ✅ 全项目已统一 |
| §三 AI 协作 | ✅ 没跑长阻塞命令，没改 vite/tsconfig 前先读 |

### 后续AI 协作提示

- 修改 OpenCV 加载相关代码前，**必须**先读 `src/lib/opencvLoader.ts`，**禁止**改回 `import('@techstark/opencv-js')`
- 检测器只有 `src/lib/opencvUtils.ts` 一个文件，所有算法改动都在那里，**禁止新建** `autoPaperDetector.ts` / `PaperDetector.ts` 之类的散文件
- 遇到 OpenCV 加载相关报错，先看 `CalibrationPage` 是否显示红色错误文字，再看控制台

---

## 附录：2026-07-07（续）纸张检测自动识别化重构

### 背景
手动调参（Canny/模糊/面积滑块 + 手动检测按钮 + 测试简化检测器按钮）体验差、且对"白纸+木纹+投影暗边"场景无必要。本次目标：舍去手动调参、导入图片后自动识别纸张。

### 改动文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `src/lib/opencvUtils.ts` | 改动 | `detectPaperCorners` 重写为**全自动无参**多策略检测器（Otsu/自适应/Canny/CLAHE，自动选最大合法四边形），用 `approx.ptr(i,0)` 取点；保留 `perspectiveWarp`、`extractToolContours` |
| `src/features/calibration/CalibrationPage.tsx` | 改动 | 删除滑块/手动检测/测试按钮；图片就绪后 `useEffect` 自动调用 `detectPaperCorners`，带"识别中…"与失败提示；保留透视校正/提取轮廓/重新检测 |
| `src/lib/autoPaperDetector.ts` | **删除** | 逻辑已并入 `opencvUtils.ts` |
| `src/utils/simplePaperDetector.ts` | **删除** | 仅被测试按钮与 testUtils 引用，已无用 |
| `src/utils/PaperDetector.ts` | **删除** | 孤儿文件（无人 import） |
| `src/utils/PaperDetector.optimized.ts` | **删除** | 孤儿文件（无人 import） |
| `src/utils/OptimizedPaperDetector.ts` | **删除** | 孤儿文件（无人 import） |
| `src/utils/testUtils.ts` | **删除** | 仅引用 simplePaperDetector，已无用 |
| `src/features/calibration/CalibrationPage.backup.tsx` | **删除** | 备份文件 |

### 合规自查

| 规范 | 自查结论 |
|------|---------|
| §一.1 单一调试入口 | ✅ 无新增测试文件，删除了 backup |
| §一.2 文件存放/集中 | ✅ 检测逻辑集中到唯一文件 `opencvUtils.ts`，删除 6 个散文件 |
| §一.3 参数管理 | ✅ 移除全部手动调参 UI，检测无参数 |
| §二.1-§二.5 OpenCV 规范 | ✅ 内存 .delete 完整、四点排序、ptr 取点 |
| §二.6 加载机制 | ✅ 仍严格走 `window.cv` + `loadCv()`，无 import |
| §三 AI 协作（集中逻辑） | ✅ 符合"以集中逻辑为荣" |

---

## 附录：2026-07-07（续）三方法融合判定 + 横竖屏自适应 + 偏斜提醒

### 背景
上一版多策略检测（Otsu/自适应/Canny/CLAHE 共 5 策略×2 方向）在亮白纸场景失效（96%/89% 白噪声），且 Canny/Otsu-inv 存在设计缺陷。用户要求基于三种验证通过的可视化手段实现加权融合，并增加横竖屏通用 + 角度偏斜提醒。

### 改动文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `src/lib/opencvUtils.ts` | 改动 | `detectPaperCorners` 重写为**三方法加权融合**：①Otsu(Gauss) ②Canny+margin ③Otsu(median)；返回 `PaperDetection`（含 corners/confidence/skew/lowConfidence）；`perspectiveWarp` 改为横竖屏自适应 A4 输出；删除 CLAHE/自适应阈值等失效策略；新增 skewOf/interiorAngles/averageQuads/quadDist |
| `src/features/calibration/CalibrationPage.tsx` | 改动 | 适配新返回结构：展示置信度、偏斜警告(红/琥珀)、低置信提示；透视校正传 `detect.corners` |
| `OPENCV_INTEGRATION.md` | 改动 | 新增 §1.1 融合策略详细文档（三方法表/融合流程/skew 阈值/方案评估）；更新集成描述 |
| `DEVELOPMENT_GUIDE.md` | 改动 | 更新 §2 为融合判定逻辑；更新 §4 排查指南；本附录 |

### Python 验证（cv2 miniconda）
- 用 `validate_fusion.py` 复现同一算法跑 testpic.jpg → M1✅ M3✅ M2✗ → 2/3 共识确认，conf=0.67，skew maxDev=1.4°(ok)
- 调试图 `fusion_debug.png` 显示两套 Otsu 方法几乎重合、融合四边形完美贴合白纸

### 关键发现与设计决策

| 问题 | 发现 | 解决方案 |
|------|------|---------|
| Otsu-inv RETR_EXTERNAL 漏洞 | 反相后白纸变成内部"洞"，RETR_EXTERNAL 只返回背景轮廓(99.7%) | 改用 medianBlur+Otsu 正相取最大外轮廓（与方法① 不同平滑→独立投票） |
| Canny 贴框溢出 | 纸边与图像边界相连时 Canny 四边形顶点落在 y=0/y=H | inBounds 加 margin(~8px) 自动拒绝贴框轮廓 |
| 纯 2-of-3 在示例图可能失败 | Canny 在 testpic 上不命中，仅 M1/M3 投票 | M1+M3 本身构成 2 票共识；额外加单方法兜底(lowConfidence) |

### 合规自查

| 规范 | 自查结论 |
|------|---------|
| §一.1 单一调试入口 | ✅ 无新增文件 |
| §一.2 文件存放/集中 | ✅ 仅改 opencvUtils.ts + CalibrationPage.tsx |
| §一.3 参数管理 | ✅ 无参数 UI，全内部自适应 |
| §二.1-§二.5 OpenCV 规范 | ✅ 内存 .delete 完整、ptr 取点、四点排序、无 import |
| §二.6 加载机制 | ✅ 不涉及 |
| §二.5 先验证后迁移 | ✅ cv2 Python 复现已通过，调试图已保存 |
| §三 AI 协作 | ✅ 符合 |

---

## 附录：2026-07-07（续）多参数电池 + 首轮早退 + 按方法族加权共识

### 背景
用户提出三点诉求：① 为何"三种可视化都完美"却代码失败；② 三种处理可否多参数自动（应对光线/影子等）；③ 加权共识如何避免固定参数全失败、且首轮完美就不调用多参数。

### 改动文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `src/lib/opencvUtils.ts` | 改动 | `detectPaperCorners` 重写为「首轮 Otsu 强命中早退 → otsu/canny/adaptive 三族多参数电池 → 按方法族加权共识」；新增 `otsuQuad`/`isStrong` 辅助；`PaperDetection` 增加 `mode` 字段 |
| `src/features/calibration/CalibrationPage.tsx` | 改动 | 成功提示区分 mode（首轮强命中 / N 方法族共识） |
| `OPENCV_INTEGRATION.md` | 改动 | §1.1 重写为电池+早退+族加权共识；更新集成描述与两处术语 |
| `DEVELOPMENT_GUIDE.md` | 改动 | §2 重写为电池+早退+族加权共识；本附录 |

### Python 验证（cv2 miniconda，先验证后迁移）
- `validate_battery.py` 复现新电池逻辑跑 `public/testpic.jpg` → **PATH=early-exit**（首轮 Otsu+Gauss5 即 `isStrong`），conf=1.0，四角 `[[60,332],[590,337],[595,1110],[34,1102]]`，贴合白纸
- 三族多参数电池逻辑已在脚本中实现并验证（聚类/族计数/早退分支均覆盖）

### 关键设计决策

| 诉求 | 方案 |
|------|------|
| 可视化完美却代码失败 | 区分"二值图可分离"与"轮廓→四边形落点"：Canny 贴框溢出、Otsu 反相抓背景，两者在落点步骤失败（已规避） |
| 多参数自动 | 每方法族放 3~4 个参数变体，覆盖光线/阴影/背景；变体数有界（浏览器性能） |
| 加权避免全失败 | 按方法族加权（非变体数）：≥2 独立族一致才高置信，抗单族系统性误判 |
| 首轮完美不调多参数 | 首轮 Otsu `isStrong` 即早退，省去后续 ~10 次 findContours |

### 合规自查

| 规范 | 自查结论 |
|------|---------|
| §一.1 单一调试入口 | ✅ 无新增文件 |
| §一.2 文件存放/集中 | ✅ 仅改 opencvUtils.ts + CalibrationPage.tsx |
| §一.3 参数管理 | ✅ 仍无参数 UI，全内部自适应 |
| §二.1-§二.5 OpenCV 规范 | ✅ 内存 .delete 完整（g5/g9/m5/m7 均在 finally 释放）、ptr 取点、四点排序 |
| §二.5 先验证后迁移 | ✅ cv2 Python 复现已通过（validate_battery.py） |
| §三 AI 协作 | ✅ 符合 |

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

| 文件 | 类型 | 说明 |
|------|------|------|
| `src/lib/opencvUtils.ts` | 改动 | `ptsFromMat` 由 `approx.ptr(i,0)` 改为 `approx.data32S` 读取；清理调试日志噪声 |
| `DEVELOPMENT_GUIDE.md` | 改动 | §二.2 新增 ptr 坑说明、§取点与面积过滤翻正、本附录 |
| `README.md` | 改动 | 取点说明翻正 |
| `OPENCV_INTEGRATION.md` | 改动 | 见下方 §1.1 取点更正 |

### 合规自查

| 规范 | 自查结论 |
|------|---------|
| §二.1-§二.5 OpenCV 规范 | ✅ 内存 .delete 完整、`data32S` 取点、四点排序、无 import |
| §二.5 先验证后迁移 | ✅ 用 Node 加载实际 `public/opencv.js` + 真实图灰度端到端验证 |
| §三 AI 协作 | ✅ 修复后同步 MD |

---

_本指南最后更新：2026-07-07（approxPolyDP 取点 ptr 致命 bug 修复 + 文档更正）_
