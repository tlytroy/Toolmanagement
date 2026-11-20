# RapidTool-ShadowBox 开源仓库审阅报告（对 toolmanagement-web 的参考价值）

- **审阅对象**：`FracktalWorks/RapidTool-ShadowBox`，固定 commit `f8372c1908db4ae9da367b1320af25a1f6d73bf0`（2026-11-05，Pavan，PGP 已验证，合并 PR #5：登录跳转到 Portal）
- **审阅方式**：GitHub MCP 列目录 + `raw.githubusercontent.com` 读取源码（README、package.json、appStore、geometry、cvWorkerManager、DesignWorkspace、ImageWorkspace、exportSTL、packages 结构、API commit 元数据）
- **重要前置说明**：仓库名仍叫 ShadowBox，但 **README 与 package.json 中的产品名为 ToolTrace**，README 自称 "RapidTool-ToolTrace"。README 的「Known Limitations / Roadmap」与实际代码存在明显漂移（详见 §4、§5），本报告以 **commit 实际代码为准**，并明确指出漂移点。

---

## 1. 定位与技术栈

**定位**：浏览器端 SaaS（口号 "From tool photo to ready-to-print insert — in under 10 minutes"），照片 → 工具轮廓 → 排版 → 3D 打印 / 激光切割嵌件，宣称无需 CAD、无需安装、无后端。属于 RapidTool 产品家族（与 SoftJaws / Fixture / Portal 共享设计系统与 SSO）。

**技术栈**（`package.json`）：

| 层 | 技术 | 版本 |
|---|---|---|
| 框架 | React + TS + Vite | React 18.3.1 / TS 5.9.3 / Vite 7.2.4 |
| 样式 | Tailwind CSS v4 + CSS 自定义属性（设计令牌） | 4.1.18 |
| 状态 | Zustand（单一 appStore） + 独立 authStore / progressStore | 5.0.10 |
| 3D | three + React Three Fiber + drei | three 0.182 / R3F 8.18 / drei 9.122 |
| 布尔运算 | three-bvh-csg（Brush / Evaluator / SUBTRACTION） | 0.0.17 |
| 2D offset | clipper-lib（Vatti 路径偏置） | 6.4.2 |
| CV | OpenCV.js（Web Worker）+ GrabCut | 静态 `public/opencv.js` |
| AI 分割 | @huggingface/transformers + onnxruntime-web（SlimSAM / SOD，另有 samWorker / sodWorker） | 4.2.0 / 1.22.0 |
| 动画 / 图标 | motion、lucide-react | 12.29 / 0.563 |
| Monorepo | npm workspaces：`packages/cad-core`、`packages/cad-ui`、`packages/storage` | — |
| 包身份 | `"name": "tooltrace", "private": true, "version": "0.0.0"` | — |

**与我方对比**：技术栈路线几乎相同（照片→轮廓→3D 嵌件），但其几何真相在浏览器（Clipper + three-bvh-csg + Three.js），我方几何真源在后端（Shapely + manifold3d + trimesh）。其 AI 分割链路（SlimSAM/SOD + GrabCut 多级回退）比我方目前的需求更重。

---

## 2. 目录与核心模块

### 2.1 根目录与 src 实测结构（以 commit 树为准，README 的结构图已过时）

```
根目录: src/ packages/ server/ public/ docs/ deploy/ scripts/ test-photos/
        package.json / package-lock.json / vite.config.ts / nginx.conf /
        Dockerfile / docker-compose.yml / .env.{development,production,example} / README.md
        （根目录无 LICENSE 文件）

src/
  App.tsx  main.tsx  index.css        # index.css 10KB：CSS 设计令牌 + family 工具类
  components/                         # 15 个文件，app-specific UI
    WorkflowShell.tsx (30KB)  ControlPanel.tsx (77KB)  ImageWorkspace.tsx (38KB)
    LayoutWorkspace.tsx (34KB) DesignWorkspace.tsx (33KB) ExportWorkspace.tsx (42KB)
    DraggableCorners.tsx  TracingOverlay.tsx  PropertiesPanel.tsx  LabelsStepPanel.tsx
    ProgressBar.tsx  AuthGate.tsx  AccountSettings.tsx  ErrorBoundary.tsx  icons/
  features/labels/                    # 3D 浮雕文字标签工作流（README 未提及）
  hooks/  images/  services/api/  types/clipper-lib.d.ts  utils/prodLogger.ts
  lib/                                # 前端几何与导出核心
    geometry.ts (15KB)  contourRegularizer.ts (15KB)  gridfinityGeometry.ts
    gridfinitySpec.ts  packRects.ts  toolLibrary.ts  exportSTL.ts  exportSVG.ts
  stores/
    appStore.ts (25KB)  authStore.ts  progressStore.ts  index.ts
  workers/
    cvWorker.ts (98KB!)  cvWorkerManager.ts (9.7KB)
    samWorker.ts / samWorkerManager.ts  sodWorker.ts / sodWorkerManager.ts  index.ts

packages/
  cad-core/   src/{cad,compute,csg,export,mesh,offset,parsers,snapping,transform,utils,workers}/ + index.ts
              README.md + package.json + vitest.config.ts（纯 CAD 逻辑，无 React）
  cad-ui/     src/{branding,controls,layout,loading,panels,primitives,sidebar,stores,toolbar,transform,utils,viewport}/ + index.ts
              README.md (18KB) + package.json（共享 React UI 库）
  storage/    src/{FileAutoSave.ts,UndoRedoManager.ts,useFileSession.ts,types.ts,index.ts}
              （本地文件会话 / 自动保存 / 撤销重做，README 未提及）
```

README 声称的 `src/lib/meshBuilder.ts` 不存在（在 roadmap 里是待办）；`cad-core` 的目录比 README 多 `cad/`、`compute/`、`utils/`。

### 2.2 状态管理：`src/stores/appStore.ts`

单一 Zustand store，`create<AppState>((set, get) => ({ ...initialState, actions }))`，关键结构：

- **工作流**：`WorkflowStep = 'paper' | 'tools' | 'layout' | 'design' | 'labels' | 'export'`（比 README 的 5 步多 `labels`），`currentStep` / `setCurrentStep`。
- **图像与标定**：`imageFile/imageUrl/imageSize`；`isRectified`；`paperCorners`（4 点）；`paperDetected/paperConfidence`；**`pixelsPerMm: number | null` 单一标量**；`applyRectification(rectifiedUrl, size, pixelsPerMm)` 会替换工作图、把四角设为图像边框、清空轮廓/标签/历史。
- **轮廓**：`ToolOutline`（`points` 原始 → `smoothedPoints` → `regularizedPoints` 三级；`boundingBox`、`area`、`areaInMm2`、`confidence`、`samClicks`、`templateMatched/templateName`）。Actions：`addToolOutline`、`updateToolOutlineSmoothed`（重跑 `regularizeContour`）、`updateToolOutlineEdited`（**不重跑正则化**，避免拖拽锚点时全局弧拟合导致远端跳变——已记录的 bug 修复）、`updateToolOutlineRefined`、`snapToPill`。
- **撤销栈的双层设计**：全局 `undoStack/redoStack`（`ToolOutline[][]` 快照，cap 50）覆盖 add/remove/auto-detect/refine；另有 `refineHistory: Record<string, ToolOutline[]>`（每个工具 cap 25）+ `undoRefine(id)` 支持单次点击回退。
- **排版**：`LayoutState { grid:{rows,cols,cellWidthMm=42,cellHeightMm=42}, shapes:LayoutShape[], selectedShapeId, layoutTool }`；`LayoutShape` 用 **mm 坐标**（`x/y/width/height/rotation`）+ `toolOutlineId` 关联轮廓。`initializeLayoutFromTools()` 用 `packRects()` 做 2D skyline packing，`MARGIN = 8 + clearanceValue`、`GAP = 6 + clearanceValue*2`，按 42mm 整格向上取整并居中。
- **3D 设计参数**：`DesignSettings { baseHeight:5, wallThickness:2, cutoutDepth:15, chamferSize:2, gridfinityBase:true, materialPreset:'eva-foam' }`；`clearanceValue: 1.0`（Offset 预设 None 0 / Small 0.5 / Medium 1 / Large 2）。
- **其他**：`labels: LabelConfig[]`、`activeTool`、`refineBrush`、`exportFormat:'svg'|'stl'`、`isProcessing/processingMessage`；`MAX_FILE_SIZE=50MB`、允许 `jpeg/png/webp/bmp`；`setImage` 用 `URL.createObjectURL` 并在替换时 revoke。
- 旁支 store：`progressStore.ts`（`useProgress.start/done` 驱动假进度条）、`authStore.ts`（Cookie SSO，向 `portal.appliedadditive.com` 跳转，本 commit 已删除本地登录表单）。

### 2.3 Web Worker：`src/workers/cvWorkerManager.ts` + `cvWorker.ts`

- **管理器模式**：模块级单例 `worker: Worker | null`、`ready`、`reqId`、`pending: Map<id, {resolve,reject}>`。`init()` 懒加载 `new Worker(new URL('./cvWorker.ts', import.meta.url))`；`request<T>(type, payload, transfer)` 统一 `postMessage({id,type,payload}, transfer)`，带 **15s init 超时 / 60s 请求超时**。`getImageData(url)` 在主线程用 canvas 解码为 ImageData 再 postMessage。
- **公开 API**：`detectPaper`（两阶段 HSV 白 mask + Canny 回退，返回四角 + `pixelsPerMm`）、`traceTool`、`traceRegion`、`traceAllTools`、`grabCutInit/grabCutRefine/grabCutClear`（**会话留在 worker 内**，后续笔画不重传图像）、`contourFromMask`、`traceMask`、`proposeRegions`、`rectifyToA4`。
- **降级策略**：`detectPaper()` 失败时返回 10%/90% 的默认四角 + `pixelsPerMm = Math.min(w,h)/210` 的粗略猜测，confidence=0.1，提示用户拖角。
- `cvWorker.ts` 约 98KB，集中所有 OpenCV 管线（阴影去除：gray ÷ 51×51 高斯照明图；阈值 200 BINARY_INV；3×3 形态学；RETR_EXTERNAL；approxPolyDP ε=0.0005×周长；模板匹配 toolLibrary）。另有 samWorker/sodWorker 用 WebGPU/ONNX 做 AI 分割。

### 2.4 几何：`src/lib/geometry.ts`

- 类型：`Point2D`、`PaperCorners`、`BoundingBox`、`ToolOutline`；常量 `A4_WIDTH_MM=210 / A4_HEIGHT_MM=297`。
- 基本算子：`polygonArea`（鞋带公式）、`getBoundingBox`、`simplifyPath`（RDP）、`chaikinSmoothing`、`smoothContour(pts, epsilon=2, iterations=4)`、`createToolOutline`、`createPillShape` / `createOrientedPillShape`（PCA 主轴胶囊）、`pointInPolygon`、`contourToSVGPath`（刻意只用直线段，避免贝塞尔过冲）。
- **标定算子（关键缺陷点）**：`calculatePixelsPerMm(corners)` 取上下边平均宽、左右边平均高，再除以 A4 的 210/297（按长宽比择一）——**单一标量，不做透视投影校正**，斜拍照片上不同位置的比例尺不同。
- **`offsetPolygon(pts, offset)`**：Clipper `IntPoint`（`SCALE=1000`）→ `CleanPolygon(0.1*SCALE)` → `SimplifyPolygon(pftNonZero)` → `ClipperOffset(jtRound, etClosedPolygon)` → 取最大面积环 → 回到浮点。**存在 4 处静默降级**：`cleanPaths` 为空、`solution` 为空、异常 catch 均 `return [...pts]`（仅 `console.error`）；另有 `unionPolygons`（同样失败回退 `a`）。
- `createToolOutline` 先 `matchToolTemplate(processed, 0.82)` 匹配 CAD 模板库（`toolLibrary.ts`），失败再 `regularizeContour`（直线/圆弧拟合，`symmetryStrength: 0.0`——注释明确记录"强制镜像对称会扭曲非对称工具"的教训）；`smoothContour(points, 1.5, 0)` 只用 RDP 不用 Chaikin，以保留 L 尺内直角。
- 其他几何库：`contourRegularizer.ts`（直线/圆弧拟合）、`gridfinityGeometry.ts`（42mm 卡扣脚 + 堆叠唇边）、`packRects.ts`、`exportSVG.ts`、`exportSTL.ts`。

### 2.5 2D→3D 数据流与导出

```
上传 JPG/PNG (appStore.setImage)
 → [paper] cvWorkerManager.detectPaper() → paperCorners + pixelsPerMm（标量）
   （可选：rectifyToA4() 透视校正，见 §4 的"未接线"问题）
 → [tools] 点选/框选/SAM → cvWorker traceTool/traceRegion/contourFromMask
   → geometry.createToolOutline() → points/smoothedPoints/regularizedPoints + areaInMm2
 → [layout] initializeLayoutFromTools()：轮廓 → mm 尺寸 → packRects → LayoutShape[]
 → [design] DesignWorkspace：LayoutShape + toolOutlines + pixelsPerMm
   → createSolidShape()：像素点 ÷ pixelsPerMm → mm，Y 翻转，CCW 排序，
      offsetPolygon(rotated, clearanceValue) → THREE.Shape → ExtrudeGeometry
   → createPocketFloorWithCutouts()：对每个 shape 用 three-bvh-csg 的
      Evaluator + Brush + SUBTRACTION 逐个挖洞（在 useMemo 中、主线程执行）
 → [labels] LabelsLayer 对 trayRef raycast，放置浮雕文字
 → [export] exportSVG.generateSVG() / exportSTL.generateExportMesh → STLExporter
```

**3D 视图细节（值得学习）**：`VIEWER_DPR = min(devicePixelRatio, 2)` 固定 DPR 避免交互时分辨率抖动；`useEffect(() => () => geometry.dispose(), [geometry])` 显式释放 GPU 资源（注释记录 R3F 不自动 dispose 导致 Context Lost 的坑）；`useLayoutEffect` 用 Box3 求最低点把 Gridfinity 脚放到网格面上；`OrbitControls.onChange → regress()` 降低交互时画质；`webglcontextlost` 事件 `preventDefault()` 允许浏览器恢复；通过 `window` 自定义事件 `viewer-orientation` / `viewer-reset` 解耦头部按钮、ViewCube 与相机。

---

## 3. 值得借鉴的产品交互 / 架构

1. **六步工作流壳层**：`WorkflowShell.tsx` + 顶部面包屑 + 可折叠侧栏 + 右侧 `ControlPanel.tsx`（77KB，按步骤切换参数面板）+ 中央工作区（Image/Layout/Design/Export）。布局可直接借鉴为 M2 的"照片 → 轮廓 → 排版 → 参数 → 导出"结构。
2. **图像工作区交互**：`ImageWorkspace.tsx` 的自研 `useViewState`（zoom/pan，`MIN_ZOOM=0.1/MAX_ZOOM=10/ZOOM_STEP=1.15`）、**光标为中心缩放**、右键/Ctrl+左键平移、`F` 适配、`R` 重置、滚轮 `passive:false` 阻止页面滚动；`imageRendering:'pixelated'` 在 >2× 时显示像素边界（对轮廓检查有用）。SVG 覆盖层独立于 CSS scale，保证矢量线宽恒为 `2/zoom`。
3. **可拖拽四角标定**：`DraggableCorners.tsx` + 自动检测失败时的默认 10%~90% 四角——"先自动、后手动兜底"的交互模式很实用。
4. **轮廓编辑的教训**：`updateToolOutlineEdited` 明确不重跑全局正则化，避免锚点编辑时远端弧跳变；注释中记录了"3 次 Chaikin 会抹平 L 尺内直角、1 次仍倒角，故 RDP-only + 下游拟合圆弧"的决策。**这类"为什么"注释值得抄**。
5. **精修的命中判定**：点选时先 `pointInPolygon` 判断是否落在已有轮廓内（落在其中就 refine，不新建重复工具），再对未命中的点用 bbox 距离 + 收紧的 `reach = min(35, 0.08*对角线)` 决定是否吸附到邻近工具（找回 SOD 漏掉的卡尺爪）；正/负点击累积进 `samClicks` 后整体重分割，用 `unionPolygons` 合并，避免多次局部 mask 产生锯齿。
6. **撤销分层**：全局列表快照（cap 50）+ 单工具 refine 历史（cap 25）双栈，适合"多次点击精修"这类高频细粒度操作。
7. **Worker 通信协议**：单例懒加载 + Map 的 id→pending + 超时 + Transferable 数组（mask/rgba 用 transfer，复用 buffer 用 copy），管理器和 worker 分离，便于替换实现。
8. **共享 UI 包**：`packages/cad-ui` 把 DashboardLayout / ViewCube / ScalableGrid / NavigationHelp / LoadingOverlay / NumberInput / StepProgress 等做成无框架耦合的组件库，`packages/cad-core` 放纯 CAD 逻辑，`packages/storage` 放 FileAutoSave/UndoRedoManager/useFileSession——monorepo 的切分边界值得参考；CSS 用 `hsl(var(--token))` 而非硬编码色值（README 的硬性贡献规则）。
9. **参数化设计**：`DesignSettings` 把底板厚/壁厚/切深/倒角/Gridfinity/材质预设做成 store 字段，实时驱动 `useMemo` 重建几何；`clearanceValue` 与排版 MARGIN/GAP 联动，Offset 增大时自动扩大间距避免口袋重叠——**参数联动的产品思维可抄**。
10. **样本库**：`test-photos/` 和 `toolLibrary.ts` 的模板匹配（0.82 阈值）提供"识别到标准工具直接替换为完美 CAD 轮廓"的体验升级路径。

---

## 4. 不可照搬的坑

### 4.1 无真正的透视校正（本项目最需要避开的坑）

- **README 明列**："No perspective warp → Angled photos produce distorted tool shapes"，Roadmap Phase 1 仍为未勾选。
- **代码现状更微妙**：`appStore.applyRectification()` + `cvWorkerManager.rectifyToA4()`（OpenCV 透视变换）**存在**，但 `ImageWorkspace.tsx` 的 import 列表只有 `traceTool, grabCutInit, grabCutRefine, samSegmentPoint`——**UI 从未调用 `rectifyToA4` / `applyRectification`**，这段能力实际上是未接线的死代码。正常工作流仍然只用 `calculatePixelsPerMm(corners)` 的**单一标量比例**：四点被压成一个平均值，斜拍照片不同位置的尺度误差无法消除，工具轮廓因此变形。
- **对我方的意义**：我方的"固定 10px/mm 透视校正 + 真实毫米坐标存储"正是这里的解药。必须保证：(a) 透视变换在轮廓提取**之前**执行；(b) 轮廓点以毫米坐标（而非像素÷单一 ppm）进入排版与导出；(c) 标定失败时**显式报错/阻断**，不要像它那样给一个 `pixelsPerMm = min(w,h)/210` 的假数值然后继续出图。

### 4.2 Clipper 静默失败 → 返回原始点

- `offsetPolygon()` 在 `cleanPaths` 为空、`solution` 为空、以及 `catch` 三处都 `return [...pts]`，只有 `console.error`。README 的 Known Limitations 写着 "Clipper-lib not installed → `offsetPolygon()` silently returns original points"。**漂移点**：该 commit 的 `package.json` 实际已包含 `clipper-lib: ^6.4.2`，`geometry.ts` 已 import，README 的"未安装"说法已过时；但**静默降级结构仍在**——.library 缺失、Worker/浏览器环境异常、Clipper 产生空解，用户看到的都是"offset 没生效但流程继续"，最终 STL 口袋尺寸错误。
- 我方的 Shapely `buffer()` / manifold3d 必须在后端对失败**抛错并让前端显式展示**，禁止静默回退到未偏置轮廓；前后端都要有"offset 前后面积/包围盒"的可观测断言。

### 4.3 前端算几何导致"前后端两套轮廓"（最严重的架构坑）

- **同一仓库内部就已经分裂**：`DesignWorkspace.tsx` 的实时 3D 用 `three-bvh-csg` 在主线程 `useMemo` 里逐 shape 做 SUBTRACTION（带 bevel、Gridfinity 脚/唇、chamfer、材质），而导出路径 `src/lib/exportSTL.ts` 的 `generateSTLMesh()` **是未实现的桩**：注释 `// For simplicity... // TODO: Implement CSG subtraction using cad-core`，`if (cutoutGeometries.length > 0) { return baseMesh; }`——**导出的 STL 只有底板，没有工具口袋**！README 却把 `generateExportMesh` 提取列为待办，说明作者也知道导出与预览不是同一套。
- 再叠加 `offsetPolygon` 的像素域偏置（先旋转再 offset，单位 px）与 CSS/SVG 显示域、`clearanceValue` 联动的排版尺寸，轮廓至少存在"显示轮廓 / 正则化轮廓 / CSG 预览轮廓 / 导出轮廓"多份真相。
- **我方必须**：几何真源唯一留在后端（Shapely + manifold3d + trimesh）；前端只做可视化与参数收集，预览用后端返回的规范几何或轻量代理网格，导出必须复用后端同一份实体；后端对轮廓做版本化（轮廓 ID + 参数哈希 → 几何结果），前端不得二次 offset/布尔/重采样。

### 4.4 其他工程坑（可选择性规避）

- `cvWorker.ts` 单文件 98KB、包里还引入 `@huggingface/transformers` + onnxruntime-web（模型首次下载、WebGPU/GPU 争用，代码里有 `webglcontextlost`/`failIfMajorPerformanceCaveat:false` 的兜底注释）——重型 AI 链路带来首次加载与 GPU 冲突复杂度。
- `setImage` / `applyRectification` 直接 `URL.revokeObjectURL` 管理资源，图片切换/撤销链路复杂时容易误 revoke。
- `ExportWorkspace.tsx` 42KB、`ControlPanel.tsx` 77KB 单文件过大，不利于维护。
- README 与代码漂移严重（产品名、目录、"无后端"、Clipper、已知问题），说明该仓库文档不能作为唯一事实来源——本次审查即按 commit 源码核对。
- 认证已接 Portal SSO（`AuthGate.tsx` 跳转 `portal.appliedadditive.com/auth/login?returnTo=...`），与 README "No backend / No authentication" 矛盾；我方 M2 若离线/本地优先，不要抄这套外部依赖。

---

## 5. 许可证与版本

- **许可证**：README 结尾声明 `MIT — © 2025 RapidTool`。但**仓库根目录（该 commit 树）没有 LICENSE / LICENSE.txt 文件**（MCP 目录列表与 raw 抓取均确认；raw 的 LICENSE/LICENSE.txt 请求失败/不存在）。→ 法律上仅有 README 的声明，无正式 LICENSE 文本；**不可直接复制其源码文件到我方仓库**，如需借用代码须先向作者确认授权，或仅借鉴交互/架构思路（本报告即按此原则撰写）。
- **版本**：`package.json` 为 `"version": "0.0.0", "private": true`，尚无公开发布版本；commit 处于早期开发（大量 TODO、Roadmap 大多未勾选、README 结构图过时）。
- **commit 元数据**：`f8372c19...`，作者 Pavan `<siddapurampavan9381@gmail.com>`，2026-11-05T11:18:37Z，PGP 验证通过（verified），message：`Merge pull request #5 from FracktalWorks/fix/auth-redirect-to-portal`。
- **依赖版本**（可复用性参考）：React 18.3.1 / Vite 7.2.4 / TS 5.9.3 / Zustand 5.0.10 / three 0.182 / R3F 8.18 / three-bvh-csg 0.0.17 / clipper-lib 6.4.2 / Tailwind 4.1.18；Node 18+、npm 9+。

---

## 6. 对本项目 M2 前端的具体建议

### 可以抄（交互 / 架构层，不涉及几何真相）

1. **六步 WorkflowShell + 面包屑 + 可折叠侧栏 + 右侧参数面板 + 中央工作区**的整体布局（`WorkflowShell.tsx` / `ControlPanel.tsx`）；M2 可先搭壳再把后端结果填进去。
2. **`useViewState` 的图像查看交互**：光标中心缩放、右键/Ctrl 平移、F 适配、R 复位、滚轮阻止冒泡、>2× 像素化；`ImageWorkspace.tsx` 的实现可直接移植为独立 hook。
3. **SVG 覆盖层与光栅分离**：轮廓/四角用 SVG `viewBox=原图尺寸` + 外层按 zoom 缩放，线宽用 `n/zoom` 保持恒定（`PaperOverlay` / `ToolOutlinesOverlay`）。
4. **可拖拽四角 + 自动检测失败回退到默认角点**的标定交互（但默认角点在我方只能作为"待用户确认"的中间态，不能据此直接出毫米结果）。
5. **轮廓点命中判定与"点内即精修、点外才新建"逻辑**、邻近吸附的收紧 reach、`samClicks` 累积式精修——若 M2 需要多轮修形可直接抄交互模型。
6. **双层撤销栈**（全局列表快照 + 单对象 refine 历史）与"编辑锚点时不重跑全局正则化"的教训。
7. **Worker 管理器协议**：单例懒加载 + id/pending Map + 超时 + Transferable；我方可用于"图像预处理 / 轮廓后处理（若必须放前端）"，但**不得承载最终几何**。
8. **参数联动**：Offset/间隙变化时排版 MARGIN/GAP 同步增大（`initializeLayoutFromTools` 的 `8+clearance` / `6+2*clearance`），避免相邻口袋 merged；材质/底板/壁厚参数化面板。
9. **3D 视图工程细节**：固定 DPR≤2、geometry/material 显式 dispose、`useLayoutEffect` 底面对齐、交互时 `regress()` 降质、`webglcontextlost` 恢复。
10. **monorepo 切分**：共享 UI（无业务几何）独立成包；CSS 令牌用 `hsl(var(--token))`。

### 必须留在后端（几何真相）

1. **透视校正与标定**：10px/mm 的固定比例变换 + 四角单应性在后端完成；前端只上传原图与角点，接收校正结果（或其稳定 URL）与标定元数据。禁止把 `calculatePixelsPerMm` 式单标量比例用于任何最终尺寸。
2. **轮廓规范化**：RDP/圆弧拟合/偏置（`buffer`）由 Shapely 完成并版本化；前端的平滑/显示点仅作预览，标记 `displayOnly`，不参与导出。
3. **实体布尔与网格**：cutout / 底板 / 壁厚 / Gridfinity 脚一律由 manifold3d 生成、trimesh 校验（水密、法线、最小壁厚、体积）；前端 R3F 只渲染后端下发的预览网格。
4. **导出**：STL/SVG 直接由后端同一实体导出；前端不得存在第二个 `generateSTLMesh` —— ShadowBox 的"预览有口袋、导出只有底板"就是前车之鉴。
5. **失败可见性**：后端几何操作失败返回结构化错误（哪个轮廓、哪一步、参数哈希），前端明确展示并阻断导出；禁止 `catch → return original points` 的静默降级。
6. **契约**：前后端以 `{ outlineId, revision, paramsHash, geometryUrl }` 对齐，任何参数变化触发后端重算并升级 revision，前端缓存按 revision 失效。

**一句话结论**：抄它的工作流壳层、查看器交互、Worker 管理器和"为什么这么写"的注释文化；它的几何链路（单标量标定、未接线的 rectifyToA4、静默 offset 回退、预览/导出两套轮廓且导出是空壳）正是我方用后端几何内核要消灭的反模式。
