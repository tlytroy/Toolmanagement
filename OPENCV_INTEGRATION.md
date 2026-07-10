# OpenCV.js 集成开发指南

## 当前状态

OpenCV.js 已通过 `<script>` 标签集成（`public/opencv.js` 挂载到 `window.cv`），并实现了完整的纸张检测与工具轮廓基元化功能。纸张检测已全部集中在 `src/lib/opencvUtils.ts#detectPaperCorners`（全自动、无参数）；工具轮廓基元化集中在同文件的 `abstractFromMask` / `extractPrimitives`（union(Fast∪SAM接口) + 形态学 + Chaikin 平滑 + 曲率分段 line/arc 拟合）。功能完全集成到主应用的校准页面中：导入图片即自动识别纸张，提取轮廓后自动叠加直线/圆弧/折线基元。

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

### 3. 工具轮廓提取与基元化（DP 逐段法，2026-07-09 对齐）

> 并集算法对齐 `sam_union_final.py`；基元化对齐 `contour_simplify.py` / `batch_process.py`（DP 抽稀 + 逐段 line/arc 拟合）。用代数最小二乘圆拟合替代 `cv2.minEnclosingCircle`，避免 <180° 弧半径塌缩。纯 JS 端到端回归已 1:1 验证（4 张真实工具图与 Python 一致）。

**管线：**
- `extractFastMask(cv, src)`（对齐 `repro_contour_v9.extract_tool_contour_v9`）：四策略并集(LAB暗区+BlackHat+Canny桥接+方案A) → 开运算(3)去噪 → 梯度阴影剥离 → 孔洞填充 → 最大连通块填充 + dilate(7)。返回 Fast 掩膜（**已用 opencv.js 像素级回归验证 IoU=1.0000**）。**它取代了原先的 OTSU 玩具**——那正是"fast sam union 啥都没实现"的根因。
- `prepareSamMask(cv, rawMasks, fastMask)`（对齐 `sam_union_final.py` 的 `is_shadow_mask_simple`+过滤+合并）：逐候选做 面积≥100 / 与 Fast 重叠≥50% / 几何拒阴影 过滤，保留的按位累积。**返回的是累积并集（未做形态学）**，形态学交给下游 `segmentDetail`。
- `segmentDetail(cv, samMask, fastMask)`：`Red(SAM=prepareSamMask输出) → close(9) 桥接 → dilate(7) → ∪ Green(Fast) → erode(3 椭圆) → merged_contour(全量重绘+close9桥接+取最大) → Chaikin 平滑 2 次`。
- `abstractFromMask(cv, fastMask, samMask?, options?)` → `extractPrimitives`：DP 抽稀(ε=0.004·周长) → 相邻拐点稠密点段上逐段 line/arc 拟合。

- `extractToolContours(cv, imageUrl, minArea, samMask?)`：内部 `imread(RGBA)` → `extractFastMask`（内部 RGBA2BGR）得到 Fast 掩膜 → `abstractFromMask(fastMask, samMask)`。把 **`prepareSamMask` 处理过的 `samMask` Mat** 传进去即自动做 `Fast ∪ SAM` 融合（store 透传的即此 Mat）。
- ⚠️ 当前第 4 参是 `samMask`（Mat）；但 `prepareSamMask` 需要 `fastMask`，而 `fastMask` 在 `extractToolContours` 内部才算 → 推荐按 **§3 接法 A** 把 `SamInference` 实例传进来，由内部统一算 `fastMask` 再 union，避免重复计算与过滤失效。
- `samMask` 的 raw 来源是 **`src/lib/samInference.ts`（SAM ONNX 推理）**：`SamInference.create({modelUrl}).generate(cv, src)` 返回 `RawSamMask[]`，再经 `prepareSamMask` 过滤合并成 merged Mat。
- `findContours(RETR_EXTERNAL, CHAIN_APPROX_NONE)` 取面积最大轮廓后，`extractPrimitives` 内部为纯 JS 计算（主 DP 用 `cv.approxPolyDP`）。

**基元化步骤（对齐 `contour_simplify.py`，`dpEpsilon=0.004`、`linTol=4`、`arcTol=4`、`maxArcRadius=55`）：**
1. `cv.approxPolyDP(ε=0.004·arcLength)` 取拐点；相邻拐点间取原始稠密点段；
2. 每段：`err_l`=直线 RMS（等价 `cv2.fitLine`，以 `pts[0]` 为参考点），`err_c`=圆拟合 RMS（中心化 Kasa 代数最小二乘，等价 `np.linalg.lstsq`）；
3. `is_arc = err_c<err_l 且 err_c<4 且 err_l>4`；半径≤55 → `arc`（重采样点列，避 0/360 穿越），半径>55 → 退化为 `polyline`，否则 → `line`。

**类型（`src/utils/types.ts`）：** `Primitive = line | arc | polyline`；`AbstractOptions = { dpEpsilon?, linTol?, arcTol?, maxArcRadius? }`。`drawPrimitives` 配色：绿=直线、橙=圆弧、紫=折线。

## SAM 浏览器内 ONNX 推理（2026-07-09 新增，2026-07-09 深夜降级为备选）

> ⚠️ **架构修订（2026-07-09 深夜）**：本节原目标"Fast+SAM+union 全在浏览器本地、不再依赖 Python"**已被撤回**。新主路径为「Tauri/Electron 桌面应用 + Python 后端」（详见 `DEVELOPMENT_GUIDE.md` §六）：SAM 由 Python 后端跑，前端只做 union+基元化。本节的浏览器 ONNX 推理路径**降级为纯前端备选**——仅当"绝对不要后端、只做轻量网页预览"时才用。前端 `opencvUtils.ts` 的 `prepareSamMask`/`segmentDetail` 仍作为"Python 后端算好 SAM 掩膜 → 前端 union"的契约层，不废。

### 1. 安装依赖

`onnxruntime-web` 已在 `package.json` 声明，装好即可：

```bash
npm install        # 已含 onnxruntime-web ^1.27.0
```

### 2. 准备 ONNX 模型（纯前端备选路径，主路径请用 Python 后端）

> 仅当走"纯浏览器、无后端"备选时执行本节。若采用 Tauri/Electron + Python 后端方案，SAM 由后端跑，跳过本节。
模型文件只需一次性准备好，二选一：

**方案 A（推荐，零 Python）**：直接下载社区已导出的 SAM ViT-B「合并 ONNX」（单 session）。
- 搜索 `sam_vit_b.onnx` 合并模型（HuggingFace / 模型社区均可），确认输入含
  `image` / `point_coords` / `point_labels` / `mask_input` / `has_mask_input`，
  输出含 `masks` / `iou_predictions`。
- 放到 `public/models/sam_vit_b.onnx` 即可。

**方案 B（自己导出）**：在能跑 torch 的机器上用脚本导出（需 `torch` + `segment_anything`）：

```bash
cd toolmanagement-web
python scripts/convert_sam_onnx.py \
    --checkpoint /path/to/sam_vit_b_01ec64.pth \
    --model-type vit_b \
    --output public/models/sam_vit_b.onnx
```

导出的是「合并 ONNX」单 session（官方 `export_onnx_model.py` 格式）：输入 `image[1,3,1024,1024]|point_coords|point_labels|mask_input|has_mask_input`，输出 `masks[1,3,256,256]|iou_predictions|low_res_masks`。`samInference.ts` 用 16×16 网格点逐点喂，复刻 `SamAutomaticMaskGenerator`。

> 验证模型格式：用 netron 打开，确认张量名与上面一致；若命名不同，`samInference.ts` 的 `findName()` 会容错匹配含子串的名字。

### 3. 接线（React 侧）—— 先解决 "prepareSamMask 需要 fastMask" 的依赖

**依赖关系（踩坑点）：**
- `segmentDetail` 真正要的是 **已 `prepareSamMask` 处理过的 SAM merged Mat**（不是 rawMasks）。
- `prepareSamMask(cv, rawMasks, fastMask)` 内部要用 `fastMask` 计算「与 Fast 重叠率 ≥50%」来过滤 SAM 候选。
- 而 `fastMask` 是在 `extractToolContours` 内部由 `extractFastMask` 算的。

→ 所以 **SAM 推理 + prepareSamMask 必须能拿到同一个 `fastMask`**，否则过滤失效（SAM 候选全被误杀，union 等于没接）。两种接法：

#### 接法 A（推荐）：把 `SamInference` 实例直接传进 `extractToolContours`

改 `extractToolContours` 第 4 参：从"已处理好的 samMask Mat"改成"可选的 sam 实例"，内部完成 union：

```ts
// opencvUtils.ts
import { SamInference } from "./samInference";

export const extractToolContours = async (
  cv: OpenCV,
  imageUrl: string,
  minArea: number,
  sam?: SamInference,            // ← 改这里：传实例而非 Mat
) => {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      const c: any = cv;
      const src = c.imread(img);
      const fastMask = extractFastMask(cv, src);       // 内部先算 Fast
      let samMaskMat: any = null;
      if (sam) {
        const rawMasks = await sam.generate(cv, src);  // 浏览器 ONNX 推理
        samMaskMat = prepareSamMask(cv, rawMasks, fastMask);  // 用同一 fastMask 过滤
      }
      // 后续 findContours / drawContours / abstractFromMask(fastMask, samMaskMat) 不变
      const abstracted = abstractFromMask(cv, fastMask, samMaskMat);
      // ... 组装 resolve({ debugUrl, primitives, primitiveDebugUrl }) 后别忘了 fastMask.delete()
    };
    img.src = imageUrl;
  });
};
```

页面侧只需初始化时建一次 `sam`，点"提取工具轮廓"传进去：

```ts
// CalibrationPage.tsx
import { SamInference } from "@/lib/samInference";
const samRef = useRef<SamInference | null>(null);

useEffect(() => {
  if (cv && !samRef.current) {
    SamInference.create({ modelUrl: "/models/sam_vit_b.onnx", backend: "webgl" })
      .then((s) => (samRef.current = s))
      .catch((e) => console.error("[SAM] 加载失败:", e));
  }
}, [cv]);

const handleExtract = useCallback(async () => {
  if (!cv || !warpedUrl) return;
  try {                                    // ← 务必 try/catch，否则异常被静默吞掉
    const result = await extractToolContours(cv, warpedUrl, 300, samRef.current ?? undefined);
    setDebugUrl(result.debugUrl);
    setPrimitives(result.primitives ?? []);
    setPrimitiveDebugUrl(result.primitiveDebugUrl);
  } catch (e) {
    console.error("[handleExtract] 失败:", e);
  }
}, [cv, warpedUrl]);
```

> 接法 A 下 union 自动生效：Fast 漏掉的暗区（如尖嘴钳刀刃缺口）会被 SAM 的 Red 掩膜补上。

#### 接法 B（不改 extractToolContours 签名）：页面分步算 samMask 存 store

若不想动 `opencvUtils.ts`，页面在"生成 SAM"按钮里算好 samMask 存 store，再透传给 `extractToolContours`：

```ts
const handleGenerateSam = useCallback(async () => {
  if (!cv || !warpedUrl || !samRef.current) return;
  const img = new Image(); img.src = warpedUrl;
  await new Promise((r) => (img.onload = r));
  const c: any = cv;
  const src = c.imread(img);
  const fastMask = extractFastMask(cv, src);
  const rawMasks = await samRef.current.generate(cv, src);
  const samMaskMat = prepareSamMask(cv, rawMasks, fastMask);  // 累积并集 Mat
  src.delete(); fastMask.delete();
  setSamMask(samMaskMat);   // store 字段 samMask: any | null
}, [cv, warpedUrl]);

// 之后点"提取工具轮廓"仍走原签名：extractToolContours(cv, warpedUrl, 300, samMask)
// ⚠️ 代价：fastMask 会算两次（handleGenerateSam 一次 + extractToolContours 内部一次），重复但正确
```

> 接法 B 的 `samMask` 必须是 **`prepareSamMask` 返回的 merged Mat**（不是 rawMasks）。

### 4. 已知坑 / 可调项

- **`SAM_SIGMOID_OUTPUT`**：官方导出输出的是 logits，本模块默认 `true`（sigmoid 后按 0.5 二值化）。若你的导出已含 sigmoid，置 `false`，否则 mask 全黑/全白。
- **推理后端**：默认 `webgl`；低端机/无 WebGL 时设 `backend: "wasm"`。
- **本地托管 onnxruntime-web wasm**：`npm install` 后把 `node_modules/onnxruntime-web/dist/*.wasm` 复制到 `public/ort-wasm/`，并在 `SamInference.create` 前设 `ort.env.wasm.wasmPaths = "/ort-wasm/"`（或动态 import 后设），否则依赖 CDN 联网首次加载。
- **`handleExtract` 必须 try/catch**：否则浏览器任何一步抛异常会被 Promise 静默 reject，表现为"按钮按了没反应"（本次排查踩过的坑）。
- **性能**：16×16=256 次解码器前向，ViT-B 在浏览器约数秒~十几秒/张，适合"点一下生成"而非实时。
- **`prepareSamMask` 过滤参数**（在 opencvUtils.ts）：`SAM_AREA_MIN=100`、`SAM_OVERLAP_MIN=0.5`。若 union 后仍见缺口，可能该 SAM 候选被重叠率阈值误杀 → 临时调到 `0.3` 验证。

### 5. 浏览器端验证 union 生效（对照本次目标）

目标：Fast 掩膜（红）在**尖嘴钳刀刃上方有缺口**，接 SAM 后该缺口应被补上。

1. **不传 SAM**：`extractToolContours(cv, warpedUrl, 300)` —— 基元化结果钳口上方应有空洞。
2. **接上 SAM** 重跑：`union(Red(SAM) ∪ Green(Fast))` 后空洞应被补满，轮廓闭合。
3. **临时可视化**：在 `extractToolContours` 的 `debugImg` 上多画一层 SAM 掩膜（青色 `Scalar(255,255,0)`），确认 SAM 真的覆盖缺口区域。
4. **缺口没补上？** 按 F12 看 console 报错；或检查 `prepareSamMask` 是否把该候选过滤了（`SAM_OVERLAP_MIN` / `isShadowMaskSimple` 误杀 → 调参或临时打 log 看 `kept` 计数）。

## 新增文件说明（偏离单文件铁律，需知会）

- **`src/lib/samInference.ts`**：SAM ONNX 推理（模型运行时胶水），非轮廓算法，故独立于 `opencvUtils.ts`。若团队坚持绝对单文件，可把 `SamInference` 类搬进 `opencvUtils.ts` 并 `import("onnxruntime-web")` 动态加载。
- **`scripts/convert_sam_onnx.py`**：本地导出脚本，不属于前端运行时。

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
- **工具轮廓基元化**（segmentDetail 并集(Fast∪SAM接口，对齐 sam_union_final.py) + Chaikin 平滑 + DP 逐段 line/arc 拟合，绿=直线/橙=圆弧/紫=折线叠加显示）
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
