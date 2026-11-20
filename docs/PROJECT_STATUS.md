# Toolmanagement-web 项目状态（实施期持久状态）

> 说明：为保护个人隐私，本文中的项目根已统一写作 `<PROJECT_ROOT>`，本机用户目录写作 `<STAGING_DIR>`。实施时请替换为你本机的实际路径。

> 本文件是**实施阶段的唯一权威状态来源**。规格以 `docs/planning/v1-plan-v1.3.md` 与 `docs/planning/v1-sds-v1.3.md` 为准；本文件记录规格之外、但新会话必须知道的实时状态、欠债与带条件裁决。
> 最后更新：2026-11-20。对应 HEAD：`b99e84e`。

## 1. 一句话状态

规划 + 规格已定稿（6 轮审核收敛），M-1 与 M0 已实现并验证（117 测试全绿）；**但新引擎尚未接线到线上 API，端到端仍不可用**。相当于"发动机造好了，还没装到车上"。

## 2. 里程碑台账

| 阶段 | 内容 | 状态 | 证据 |
|---|---|---|---|
| 规划 | v1 计划 + SDS v1.3（15.0 人日） | ✅ 定稿 | `docs/planning/v1-plan-v1.3.md`、`v1-sds-v1.3.md`，6 轮审核 |
| M-1 | 冒烟骨架：槽开口 / 首击在槽底 | ✅ 完成 | `scripts/smoke_geometry.py`、`test_geometry_m1.py`，41 用例 |
| M0 | 后端跑通 + 毫米链 + 成像 + 自检库 + 统一信封 | ✅ 完成 | 132 passed（含 M1-W 15 个）；`/api/generate` 已由 M1-W 交付，见 §4 |
| M1 | 几何内核增强（Gridfinity 底座/唇/磁孔、倒角间隙、手孔 6 形态、多轮廓） | ❌ 未开始 | 三个并行 agent 空转/崩溃后已停，零产出 |
| M1-W | 新建 `/api/*` 端点、把新引擎接上线 | ✅ 完成 | `python_backend/api/` + `export/`，6 端点全注册；`/api/generate` 端到端出真实 STL + 12 checks；15 wire 测试 + 4 组变异全红；commit `6682e06` |
| M2 | 前端多工具 / 顶点编辑 / 手孔拖拽 / 参数面板 | ❌ 未开始 | 前端 `src/` 冻结至今 |
| M3 | 纸角手拖、分块、试切件、DXF 导出 | ❌ 未开始 | |
| M4 | localStorage、错误边界、删旧引擎、文档纠偏 | ❌ 未开始 | |

粗略完成度：规划 + M0 + M-1 + M1-W ≈ 45%，剩余 55% 主要是 M1 几何增强与 M2 前端。端到端最小闭环（rect 模式）已打通：POST /api/generate 返回可用 STL。

## 3. 已拿到的硬成果（有证据）

- **F1 毫米链断裂已修**：固定 `PX_PER_MM = 10.0`，删掉 `cad_engine.py` 的 `840/1188` 与 `scale = min(...)`；100mm 轮廓 → 槽长 100.0±0.1mm，同一轮廓在 200/300mm 板上结果逐位一致。
- **静默产出废板已堵住**：工具超框抛 `TOOL_OUT_OF_BOARD`，detail 按 sizeMode 给三条可执行出路。
- **所有关键断言做过变异验证**：去掉 `_assert_tool_in_board` → 1 failed；`eigh↔eig`、`PX_PER_MM 10→12`、SAFE_MARGIN 改动等均能点红对应测试；修过"护栏只测库自身恒真"的问题。
- **M0 整体独立审核**：5 组变异全红（0 恒真），审核发现的两条 P0 已修（统一裸导入根、numpy2 `eigh`、root 信封）。

## 4. ⚠️ 欠债与带条件裁决（新会话必读）

### 4.1 M0 欠账：新库没接线
`python_backend/geometry/` 与 `imaging/` 测试全绿，但 `main.py` / `cad_engine.py` **都不 import 它们**。线上 `/detect-paper` 仍用 `latest_paper_detection.py`、`/generate-cad` 仍用 `cad_engine.py`。
**这是定稿漏洞**：SDS §1.1 写「后端能在 WSL 里跑起来，`POST /api/generate` 返回可用 STL | M0」，但 plan M0 表格与 SDS §12.1 的 M1 三路分工都没有"建端点"这一任务。
**裁决**：不回改六轮审核定稿（保持基线完整），实施期补 **M1-W** 作为 M2 硬前置；旧 8 个端点全部保留、M1-W 只新增 `/api/*`、`GEO_ENGINE=new|legacy` 只影响新端点内部；`cad_engine.py` 与旧端点删除留到 M4。旧端点不因 new 开关改变行为。
**M0 曾按 §10 记为 partially complete；M1-W 已交付 `/api/generate`（commit `6682e06`），M0 随之升为完成。**

### 4.2 带条件豁免：sam_tool_contour +3.4mm
`test_golden_m0.py::test_golden_synthetic_photo_absolute_size_known_defect` 是 `xfail(strict=True)`。遗留分割器 `sam_tool_contour.py` 的固定像素膨胀（`dk=31px`/`dk=15px`，10px/mm 下约 +3.4mm）无腐蚀补偿，实测 100×60mm 真值 → 槽 103.4×63.3mm，超 SDS §10.3 的 ±0.5mm。
**豁免三条件**：① 不许删/放宽 `xfail(strict=True)`；② 任何「端到端 ±0.5mm」或 S0「±1.5mm」承诺生效前必须排期修/换分割器（M2 前）；③ M1 不许靠放宽容差绕过。修好分割器会让 xfail XPASS 变红，逼着去标记。

### 4.3 已登记但不阻塞的遗留
- `cad_engine.py` 的 `_extrude_tool_slot` 仍 `±H/2` 居中（F1 的 z 半边）——并入 M1 换引擎整体作废，不单独修。
- `/auto-finger-slots` 的 numpy2 `eig` 复数问题主线程已用 `eigh` 修（书面冻结例外，1 行 + 注释）；旧引擎其它路径不保证。
- 前端 `src/api/toolProcessor.ts` 仍 fetch `/generate-step`（已删端点 → 404，靠 `useWorkflow.ts` 静默失败兜住）；前端冻结到 M2 才改。
- `cad_engine.py.bak` 是远古提交留下的 git 追踪文件，建议 M4 清理。

## 5. 下一步（按依赖顺序）

1. ~~**M1-W 接线**~~ ✅ 已完成（6 个 `/api/*` 端点已上线，见里程碑台账）。
2. **M1 几何增强**：Gridfinity 板体（`board.py` 当前 `build_board` 对 gridfinity 抛 `NOT_IMPLEMENTED_M1`）、倒角凸包采样验证、手孔 6 形态、多轮廓。建议拆成"每 10 分钟必须落盘一个最小文件"的小任务派发（大 agent 多次空转）。
3. M1 整体独立审核 → M2 / M3 / M4。

## 6. 待办：把临时目录里的决策文档搬进仓库

以下文件目前只在 Windows `.staging\toolmanagement\`（临时目录），新会话看不到：
- `M1_WIRE_DECISION.md`（接线决策 + 端点清单 + 8 条 DoD）
- `M1_TASKS_3WAY.md`（M1 三路任务书）

计划把它们复制为 `docs/M1_WIRE_DECISION.md` 与 `docs/M1_TASKS_3WAY.md` 并做脱敏（去掉个人路径）。

## 7. 环境与验证命令

- 项目根（WSL 原生路径）：`<PROJECT_ROOT>`
- 导入根：`python_backend/`（`cd python_backend && ../.venv/bin/python ...`）
- 测试：`.venv/bin/python -m pytest -q python_backend/tests`（**不要裸 `pytest`**，会因 `reference/oss/tracefinity` 下 42 个收集错误中断；已用 `pytest.ini` 的 `testpaths` 修正，见本次治理改动）
- 当前基线：117 passed, 1 xfailed, 1 warning
