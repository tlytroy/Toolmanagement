# Toolmanagement v1 计划（初稿 v0.1）

> 日期：2026-11-03 ｜ 作者：主会话 ｜ 状态：**待拷问（grill）**
> 项目：`Y:\home\atdoc\projects\playground\toolmanagement-web`（实为 WSL `\\wsl$\Ubuntu\home\atdoc\projects\playground\toolmanagement-web`）

---

## 0. 一句话目标

**拍一张 A4 纸上的工具照片 → 得到物理尺寸正确的凹槽 + 手槽 + 可调倒角 → 直接导出 STL 去打印。**

关键词是"**物理尺寸正确**"。当前实现离这个目标缺一整条链路。

---

## 1. 需求逐条拆解（来自 2026-11-03 面述）

| 编号 | 需求 | 验收含义 |
|---|---|---|
| R1 | 工具放在 A4 纸上拍照 | 输入就是一张手机照片，不要求额外器材 |
| R2 | 自动矫正视角 | 透视校正，用户不点四角 |
| R3 | **自动根据 A4 计算尺寸** | 像素→毫米必须由 A4（210×297mm）物理尺寸推导 |
| R4 | 识别工具轮廓 | CV 自动提取，允许失败后人工补救 |
| R5 | 形成凹槽 | 轮廓偏移后布尔减出槽 |
| R6 | 生成手槽便于拿取 | 手指槽，位置/尺寸可调 |
| R7 | 导出 STL 等格式直接打印 | 成品直接进切片软件 |
| R8 | 轮廓识别**可手动调整** | 修正自动识别错误，不只靠重拍 |
| R9 | 手槽**可手动调整** | 位置/角度/尺寸/增删 |
| R10 | 3D 模型可自定义**倒角**等 | 基底倒角、槽口倒角可调 |

---

## 2. 现状 vs 需求（差距矩阵，已逐条对代码核实）

| 需求 | 现状 | 证据 | 等级 |
|---|---|---|---|
| R1 | ✅ | `src/features/workspace/Workspace.tsx` | — |
| R2 | ✅ | `python_backend/latest_paper_detection.py:20` → `reference/pkg_paper_detection/robust_paper_detector.py:153` `warp_paper` | — |
| **R3** | ❌ **完全没有** | `python_backend/cad_engine.py:574-585` 硬编码 `840×1188` + 按底板缩放居中 | **P0 阻断** |
| R4 | ⚠️ 只取最大连通块 | `python_backend/sam_tool_contour.py:190-208` | 单工具够用 |
| R5 | ⚠️ 单槽/居中/尺寸错 | `python_backend/cad_engine.py:565` `_extrude_tool_slot` | **P0** |
| R6 | ❌ 坐标系错位 | `python_backend/cad_engine.py:407-478` `_auto_detect_finger_slots` 拿 px 当 mm | **P0** |
| R7 | ⚠️ STL ✅；STEP 是网格包壳 | `python_backend/cad_engine.py:795-847` `_mesh_to_step_base64`（STL→`StlAPI_Reader`→STEP） | P2 |
| **R8** | ⚠️ **只有位图蒙版，无矢量编辑** | `src/features/editor/MaskEditor.tsx:1125`（画笔/橡皮/直线/折线/矩形/椭圆） | **P0** |
| R9 | ⚠️ 能画但存错坐标系 | `src/features/workspace/Viewport.tsx:457-468` | **P0** |
| **R10** | ❌ **零倒角** | 全仓 `grep chamfer\|bevel` = 空；只有 `BoxParams.fillet_radius`（2D 圆角） | **P0** |

### 2.1 三处"看着有、其实错"

**A. `840×1188` 是 4px/mm 的 A4**：`840/210 = 4.0`，`1188/297 = 4.0`。写这段时脑子里是 A4 换算，但没落地——`warp_paper` 实际输出尺寸是**检测到的纸边长像素**，不是 840×1188；于是 `scale = min(base_x/840, base_y/1188)` 把轮廓**拉伸铺满底板**。一把 200mm 钳子和一把 100mm 扳手画在同一块 200×150 板上，得到**一样大的槽**。

**B. 手指槽吃像素、工具槽是毫米**：`_auto_detect_finger_slots`（`cad_engine.py:452-478`）对原始 px 点做 PCA，输出 `{x,y}` 直接当 mm；而工具槽在此前已被 `scale` 缩放过并 `-= center`。两者永远对不上。

**C. 前端手绘手槽的反算与后端不一致**：`Viewport.tsx:457` 用 `foamW/naturalWidth`，而渲染 `FingerSlotOverlay` 用 `imageWidth/foamWidth`（`:214`），且都没考虑透视校正图 ≠ 原图。

### 2.2 你没写但会咬人的两处

- **"取出通道"**：有内凹的工具（卡尺爪、扳手开口、活动钳口）若槽只能从正上方放入，是**拿不出来**的。泡沫可挤，Gridfinity 硬塑料不行。当前零处理。
- **打印缩放**：A4 若按"适合页面"打印，纸就不是 210×297，物理尺寸偏 3~5%，200mm 工具偏 6~10mm。

---

## 3. 待决策设计（grill 靶子）

### D1 像素→毫米标定

**方案 A1（推荐）**：`warp_paper` 输出**固定物理分辨率**，`px_per_mm = clamp(纸长边像素 / 297, 6, 12)`，随 `/detect-paper` 响应返回，全链路使用。
**理由**：① 轮廓算法里的像素常数（如 `sam_tool_contour.py:183` `ck = max(5, int(min(h,w)*0.012))|1`）现在会随拍照分辨率漂移，同一工具用广角和长焦拍结果不同——这是"有时好用有时不好用"的隐藏原因。改为 `k_mm × px_per_mm` 后行为恒定。② API 契约简单。
**备选**：A2 输出随边长走、动态算 `px_per_mm`；A3 要求拍尺子标定（v1 太重）。

### D2 多工具路径

**方案 B1（推荐）**：**一张照片一把工具**，前端维护工具列表累积，像购物车。
**理由**：两把工具贴在一起时 `RETR_EXTERNAL` 只有一个连通块，自动拆分在重叠/贴边/阴影下无解；强行做等于上实例分割，代价远超收益。当前"最大连通块 + bbox 外扩 8% 合并"（`sam_tool_contour.py:198-208`）恰恰对多工具是反作用的。
**代价**：用户要拍 N 次。可接受，这也是 Tooltrace 类产品的实际做法。
**隐含后果**：多工具 ⇒ **排版从可选变核心**（见 D3）。

### D3 排版

**推荐：手动优先 + 自动兜底**
- 手动：拖拽/旋转、1mm 吸附、实时碰撞（shapely `distance()`）
- 自动：对每个工具 **offset 后的 AABB** 跑 MaxRects，只保证"放得下"
- 底板尺寸三来源：手填 / "自动装满"=包围盒+边距 / Gridfinity 向上取整到 42mm
**理由**：对任意凹轮廓做精确 nest 是 NP-hard 且实现成本高；AABB + 手动微调是 80% 收益 20% 成本。自动结果必须能一键回退。

### D4 3D 后端（最关键架构分叉）

| | C1 trimesh+manifold | C2 全转 cadquery/OCCT | C3 混合 |
|---|---|---|---|
| 倒角实现 | 中（自己写 2.5D loft） | 低（`chamfer()`） | 低 |
| 任意凹轮廓鲁棒性 | **高**（shapely buffer 稳） | 低（OCCT 对上千点凹轮廓 fillet 常崩） | 中 |
| STEP | 假（网格包壳） | **真 B-Rep** | 真 |
| 性能 | 秒级 | 十秒级且不确定 | 中 |
| 部署 | 低 | 高（OCP 体积大、Python 版本敏感） | 高 |

**推荐 C1**，理由：① 用户真实出口是 **STL**（原话"直接供给 3D 打印机"），STEP 只是"想再改改"的 nice-to-have；② OCCT 对任意凹多边形的 fillet/chamfer 是著名脆弱点，为一个 nice-to-have 引入全流水线稳定性风险不划算；③ 2.5D loft 能覆盖全部要的倒角场景且天然不自交。

**2.5D loft 方案**（M1 的技术核心）：
```
输入：2D 轮廓 P（shapely Polygon）、总高 H、顶倒角 c_top、底倒角 c_bot
z 分段：
  z∈[0, c_bot]        → P_i = P.buffer(-(c_bot - t))
  z∈[c_bot, H-c_top]  → P_i = P
  z∈[H-c_top, H]      → P_i = P.buffer(-t)
相邻层同索引顶点连四边形 → 三角化
```
**唯一技术难点**：`buffer()` 会改变顶点数与顺序，**不能按索引连线**。必须先把每层多边形沿周长均匀重采样到相同点数再 loft。这是方案能否成立的关键，必须有单测兜住。

### D5 「手动调整轮廓」的层级

- **L1 位图层**（已有，保留）：画笔/橡皮修蒙版 → 重算轮廓。解决"多识别了一块阴影"。
- **L2 矢量层**（新增）：`primitives` 上拖顶点、整段平移、删段。解决"机器把圆角拟合成折线"。
**v1 只做 L2 的"顶点拖拽 + 段删除"**，不做贝塞尔插入（那是 CAD 软件的活）。
**必须定义的语义**：矢量编辑后蒙版失效 → `contour_source = 'editable_vector'`，蒙版层转为只读快照，再编辑蒙版要提示"将丢弃矢量修改"。

### D6 手槽数据模型

现状是"像素线段 → 半胶囊"，坐标系错。**推荐挂在 tool 上而非底板上**（mm 单位）：
```python
FingerSlot {
  id: str
  anchor_mm: {x, y}      # 槽中心，底板坐标系，mm
  normal_deg: float      # 进刀方向（朝工具外侧）
  length_mm, width_mm, depth_mm: float
  kind: "outer" | "inner" # 从边缘内切 / 工具中间开孔
}
```
**自动策略**（替代当前 PCA）：沿轮廓长轴两端各放一个，距外缘 `depth×0.5`，方向沿外法线；约束槽的 2D 投影与工具本体重叠 ≤ 30%（否则拿工具会顶手）。

### D7 状态与持久化

**现状**：`Workspace.tsx` 本地 `useState` 与 zustand store 双份真相，`setPrimitives` 只在 `Workspace.tsx:153` 调过一次；`useWorkflow.ts:488` 零引用（死代码）。
**推荐**：单一真相 = zustand，按 `Project / Tool[] / BoardConfig` 组织；持久化到 **IndexedDB**（dataURL 存 localStorage 5MB 会爆）；`useWorkflow.ts` 先删，重构时再建。

---

## 4. 里程碑

### M0 打通毫米链（阻断级，先做）
1. `warp_paper` 固定物理分辨率 + 返回 `px_per_mm`；`/detect-paper` 响应加该字段
2. `sam_tool_contour.py` 像素常数改 `px_per_mm × k_mm`
3. `_extrude_tool_slot` 删 `840×1188`、删 `scale`、删 `-= center`；改 `poly_mm = poly_px / px_per_mm` 并保留绝对位置
4. `InsertParams` 加 `px_per_mm`、`board_origin_mm`
5. 前端 `toolProcessor.ts` 类型补 `px_per_mm`

**DoD**：拿已知尺寸测试件拍一张，STL 在切片软件里量槽长误差 ≤1mm；`/generate-cad` 在开发机真正跑通一次（`backend.log` 显示从未调用）；新增 `python_backend/tests/test_geometry.py::test_slot_dimensions_match_mm`。

### M1 单工具完整可用（倒角 + 手槽修正 + 矢量编辑）
1. 倒角体系（C1/2.5D loft）：`top_chamfer_mm`、`bottom_chamfer_mm`、`corner_fillet_mm`、`slot_chamfer_mm`（槽口外扩，默认 0.5，改善滑入与打印）、`slot_floor_fillet_mm`
2. 手槽按 D6 mm 模型重写，前后端同源
3. 手槽手动调：拖拽 + 旋转 + 数字输入 + 增删
4. 矢量轮廓编辑 L2（顶点拖拽 / 段删除）

**DoD**：STL 层视图能看到 45° 斜面；构造 100×30mm 矩形参考件，断言手槽中心到轮廓边缘距离 = 设定值 ±0.2mm；矢量编辑后槽形跟随。

### M2 多工具与排版
`Tool[]` 模型 + 工具列表（缩略图/重命名/删除/重拍）→ 画布排版（拖拽/旋转/吸附/碰撞）→ MaxRects 自动排版 → 底板三来源 → 每工具独立 `embed_depth`/`offset`
**DoD**：3 把工具自动排版不重叠；每把槽的 STL 尺寸都等于各自真实毫米。

### M3 持久化与导出
zustand 单一真相 + IndexedDB + 项目画廊；导出 STL / 3MF / DXF(1:1) / PDF 校对页；STEP 降级为实验性并明示"网格包壳"（或砍掉，见 Q4）
**DoD**：刷新不丢；DXF 量出来 = 标称 1:1。

### M4 打磨
参数防抖自动重算 + 生成进度；redo + 快捷键面板；死代码清理（`useWorkflow.ts`、`advanced_tool_contour.py`、`optimized_*.py`、`cad_engine.py.bak`）；vite `/api` 代理 + `VITE_API_BASE`；错误边界 + 后端统一错误码。

---

## 5. 风险

| 编号 | 风险 | 影响 | 缓解 |
|---|---|---|---|
| R-1 | A4 打印缩放导致物理偏差 3~5% | 200mm 件偏 6~10mm，嵌件松/紧 | UI 提示"按 100% 打印"；M4 加校准尺 |
| R-2 | `px_per_mm` 改动后所有阈值需重调 | 识别质量回退 | 用 `tests/` 5 张 jpg 做改前/改后回归对比 |
| R-3 | loft 顶点参数化做错 → 自交/扭曲 | STL 不可打印 | 单测：矩形/圆/凹多边形各断言 `is_watertight` + 体积 |
| R-4 | 多工具后 CAD 时间线性增长，前端阻塞 | 体验崩 | M2 起异步任务 + 进度轮询；预览低精度 |
| R-5 | 浅色/银色工具识别失败 | 无法生成 | 已有蒙版兜底；M1 起显式失败提示 + 一键重拍 |
| R-6 | 内凹工具无取出通道 | **物理不可用** | M1 检测"内凹且无开口方向"，建议旋转或改通孔 |

---

## 6. 不在 v1 范围
云端/账号/分享（定位个人自用）；学习型分割（SAM）；真 B-Rep 参数化 STEP（除非 Q3 转 C2）；工具型号/尺寸数据库；多色/多材质；移动端适配。

---

## 7. 工期

| 里程碑 | 人日 | 说明 |
|---|---|---|
| M0 | 2–3 | 改动面小但涉及全链路验证 + 搭测试 |
| M1 | 6–8 | loft 是新几何代码，手槽重写跨前后端 |
| M2 | 6–8 | 排版交互 + 碰撞 + 装箱 |
| M3 | 4–5 | 持久化 + 3MF + DXF |
| M4 | 3–4 | 可穿插 |
| **合计** | **21–28**（建议按 30 排） | 不含 debug 与返工 |

---

## 8. 待你拍板（grill 的核心）

- **Q1（阻断）** D1 选 A1（固定物理分辨率 + 返回 `px_per_mm`）？
- **Q2（阻断）** D2 走 B1（一次一把 + 列表累积）？
- **Q3（阻断）** D4 选 C1（trimesh + 2.5D loft，承认 STEP 是假的）？
- **Q4** STEP 还要不要？砍掉换 3MF + DXF 对 3D 打印更实用。
- **Q5** R-6「取出通道」v1 要不要至少给警告？
- **Q6** 纯自用还是要给别人用？决定要不要投入产品化成本。

---

## 9. 下一步
1. grill 逐条拷问 §3 / §8
2. 独立 subagent 红队评审（只读本文件 + 给出的代码证据）
3. 合并成 `v1-plan-v0.2.md`，循环直到通过
4. 通过后写 `v1-sds.md`，再一轮审核
5. SDS 定稿 → 新会话实施（主会话调度 + 子 agent 编码 + 独立审核）
