# M1-W 接线里程碑：决策记录 + 任务书骨架

> 说明：为保护个人隐私，本文中的项目根已统一写作 `<PROJECT_ROOT>`，本机用户目录写作 `<STAGING_DIR>`。实施时请替换为你本机的实际路径。

> 主会话 2026-11-06 建立。这是**实施层补的里程碑**，不回改六轮审核定稿文档。

## 1. 发现的定稿漏洞（必须记住）

SDS §4.1–4.7 定义了完整 `/api/*` 契约；SDS §1.1 验收表白纸黑字写：
> 「后端能在 WSL 里跑起来，`POST /api/generate` 返回可用 STL | **M0**」

但：
- plan M0 表格（`v1-plan-v1.3.md:364-372`）8 个任务全是库/旧引擎改造，0.1 的 DoD 只写「`uvicorn main:app` 能起」+「`pytest` 能收集到用例」，**没要求任何 `/api/*` 端点**。
- SDS §12.1 的 M1 分工是**3 路全纯几何库**（`1.0b+1.4a/b/c`｜`1.1+1.2`｜`1.0+1.3+1.5+1.6`），**没有任何一路负责建端点/接线**。
- SDS §11.4（`:1139`）与 §7.1（`:731`）都提到 `main.py` 加 `GEO_ENGINE=new|legacy` 开关、「M1 全绿后再删旧代码」，但**这个开关没进任何里程碑的 DoD**。
- M2 的 2.4b 直接要求 `POST /api/board/fit-check`、2.5 要求前端调 `/api/generate`，却没人先建它。

**后果**：不补的话 v1 交付 = 「一堆测试全绿的新库 + 一套仍然坏着的 legacy 端点」，M0 的 §1.1 验收不达标，M2 端到端连 `/api/generate` 都调不到。M0 独立审核 agent 报的「P0-1 新库未接线」正是这个漏洞的表征。

## 2. 裁决（实施期补，不回改定稿）

1. 承认 M0 未达 SDS §1.1「`/api/generate` 返回可用 STL」。这是定稿 §1.1 与 §12.1 分工之间的漏洞，六轮审核都漏了。
2. **不回改定稿文档**（保持 `ca765c1` 基线完整、不破坏六轮审核记录），改为在**实施层**补一个「M1-W 接线里程碑」，作为 **M2 的硬前置**。理由：端点要一次接全 M1 的几何能力（多轮廓/内孔/手孔/gridfinity 板），M0 接半成品反而返工。
3. 排期：①M0 修复 agent 完成 → 验收提交；②M1 路 A/B/C 并行（**禁止改 `geometry/__init__.py` 与 `main.py`**），各交纯函数 + 自己的测试；③**M1-W 接线 agent 最后进场**，负责「整合 `generate_insert` + 建 `/api/*` 端点 + `GEO_ENGINE`」；④独立审核；⑤M2/M3/M4。
4. **旧端点全部保留**（前端 `src/` 冻结，M2 才改）。M1-W **只新增** `/api/*`、不动任何旧端点；`GEO_ENGINE` 只影响新端点内部 fallback，不得改变旧端点行为；`cad_engine.py` 与旧端点的删除留到 M4（SDS §7.1 / §4.7）。

## 3. SDS §4 契约要点（接线时逐条对照）

### 3.0 信封
`{success, data, warnings, error:{code,message,detail}}`；`errors[]` 不是顶层字段；`warnings[]` 元素固定 `{code,message,detail}`。
`main.py` 现有 `_warn`(:40) / `_ok`(:45) / `_fail`(:55) / `_wrap_legacy`(:83) 已实现，`_ok` 把 `data` 键**同时铺在顶层**兼容冻结前端。接线**复用这四个函数**，不要另造信封。

### 3.1 端点清单（7 新增 + 1 改名）
| 端点 | data | 关键约束 |
|---|---|---|
| `POST /api/detect-paper` | `{corners:[{x,y}×4], orientation, reprojectionError, imageSize:{w,h}}` | corners 是**纸面 mm 规范位置**，不是源图像素；warnings `CAMERA_TOO_CLOSE`/`PAPER_OUT_OF_FRAME`/`EXTREME_PERSPECTIVE`。**`imaging/api.py:77 detect_paper_response` 已装配好，直接调** |
| `POST /api/correct-image` | `{warpedImage, mmPerPx:0.1, paperMm, canvasPx, paperOriginPx}` | `warpedImage` 像素尺寸必须精确等于 `canvasPx`；`mmPerPx` 只作常量回显，**下游禁止读**。**`imaging/api.py:113 correct_image_response` 已装配好** |
| `POST /api/extract-tools` | `{tools:[{outer,interior,areaMm2,bbox}], quality, qualityParts}` | 入参必须是 `/correct-image` 输出；面积 <50mm² 丢弃；bbox 距纸边 <3mm → `TOOL_OUT_OF_PAPER`（不返回残缺轮廓） |
| `POST /api/simplify-contour` | `{polygons: Vec2[][]}` | **primitives 不出现在任何 v1 API**；旧 `/simplify-contours` 由它替代（但旧端点本轮保留） |
| `POST /api/generate` | 见下 | ★ 核心 |
| `POST /api/finger-holes/auto` | `{holes: FingerHole[]}` | 只给建议，前端可改可删 |
| `POST /api/board/fit-check` | `{boardMm:{w,h}, unitsX, unitsY, outOfBoardToolIds:[], minEdgeMm}` | plan 2.4b；`outOfBoardToolIds` 与 `/api/generate` 的 `TOOL_OUT_OF_BOARD` **必须完全一致** |
| `POST /api/tool-mask` | （旧 `/extract-tool-mask` 改名） | 用于画笔编辑初始蒙版回推 |

### 3.2 `/api/generate`（最复杂）
请求 = 完整 `Project`（**camelCase**）；响应 `data`：
```
pieces: [{index, name, stlBase64, bboxMm, volumeMm3}]   # 分块时 >1，命名 board_A1/A2/B1...
dxfBase64?                                              # 仅 wantDxf=true
summary: {
  toolCount, pieceCount, boardMm, totalVolumeMm3,
  paramsEcho: {sizeMode,widthMm,heightMm,margin,cornerR,baseEdgeRoundover,
               slotChamfer,embedDepth,clearance,unitsX,unitsY},
  slotBounds: [[x0,y0,z0],[x1,y1,z1]],   # 所有槽切刀并集 bbox
  baseBounds: [[x0,y0,z0],[x1,y1,z1]]
}
checks: [10 项]
```
- **blocking**（false → `success:false`，`GEOMETRY_INVALID` 或 `TOOL_OUT_OF_BOARD`，`detail.failedChecks`）：`shapely_valid`/`watertight`/`winding`/`manifold_status`/`tools_in_board`/`slot_open`
- **advisory**（false → `warnings[]`，仍出 STL）：`genus`/`volume_match`/`min_rib`/`depth_fits`
- `min_rib` 阈值 **2.0**（示例 `minMm:2.4` 是实测值）；`genus.expected = 内环数`；`volume_match.errorPct <= 2.0`
- `depth_fits` 判**请求值**：`max_embed = board_top_z-2`(rect) / `heightU*7-4.75-2`(gridfinity)，`ok = requested <= max_embed`；回传 `{ok,requested,clampedTo,maxEmbed}`；**先 clamp 再断言会恒真**
- `slot_open`：`ok = |firstHitZ - expectedZ| <= 0.05`
- 分块命名「先行后列，从左上起」

### 3.3 字段映射（关键工作量）
SDS §3.1/§3.2 用 **camelCase**（`sizeMode`/`widthMm`/`heightMm`/`cornerR`/`baseEdgeRoundover`/`slotChamfer`/`embedDepth`/`clearance`/`unitsX`/`unitsY`），
而 `python_backend/domain/models.py` 是 **snake_case frozen dataclass**。
→ 接线需建 `python_backend/api/schemas.py`（Pydantic）做一层 camelCase ↔ snake_case 转换：
- 未知字段 → 400 `SCHEMA_UNKNOWN_FIELD`
- `sizeMode='custom'` 缺 `widthMm`/`heightMm`，或非 custom 带宽高 → 400 `INVALID_SIZE_MODE`（判据必须 `is not None`）
- `schemaVersion` 不支持 → `SCHEMA_VERSION_UNSUPPORTED`

## 4. 现有可复用接口（接线 agent 直接调，不要重写）
- `imaging/api.py`：`decode_image(content)->np.ndarray`(:51)、`encode_png_base64`(:62)、`_warnings_payload`(:73)、`detect_paper_response(content,paper_size)->dict`(:77)、`correct_image_response(content,paper_size,orientation,corners)->dict`(:113)、`ImagingError(ValueError)`(:31)
- `geometry/__init__.py:117 generate_insert(project,depth=None)->dict` 返回 `{base(Manifold), base_uncut, slot_cutter, pocket_length_mm, board_mm, top_z, warnings, tools}`；`:190 base = base_uncut - slot_cutter`。**`base` 是 Manifold，接线层需自己转 STL**
- **STL 导出**：`from trimesh.exchange.stl import export_stl` → `export_stl(trimesh_obj)` → `base64.b64encode(...).decode("utf-8")`（`cad_engine.py:899-901` 现成写法）。`validate.py:157 _to_trimesh(manifold_obj)` 已封装转换
- `geometry/validate.py`：`CheckResult`(:66，`to_dict()` → `{id,ok,...detail}`)、`validate_2d`(:88)、`validate_3d`(:179)、`summarize`(:265)、`assert_all_ok`(:288)；`ADVISORY_CHECKS = frozenset({"genus","volume_match","min_rib"})`(:61) —— **注意 SDS §4.5 还含 `depth_fits`，接线时要核是否一致并补**
- `main.py` 现有端点 8 个：`GET /`(:151)、`/detect-paper`(:155)、`/extract-contours`(:207)、`/extract-tool-mask`(:256)、`/simplify-contours`(:288)、`/update-contour`(:310)、`/generate-cad`(:405)、`/auto-finger-slots`(:486)。**全部保留不动**

## 5. M1-W 的 DoD（必须写成会红的测试）
1. `POST /api/generate` 用一个 100×20mm 矩形工具 → `success:true`、`pieces[0].stlBase64` 可被 `trimesh.load` 解析、槽开口朝上（raycast 首击 = `top_z - embed`）、槽长 100±0.1mm
2. `POST /api/generate` 传未知字段 → 400 `SCHEMA_UNKNOWN_FIELD`
3. `sizeMode='custom'` 缺宽高 → 400 `INVALID_SIZE_MODE`
4. `tools` 超出板 → `TOOL_OUT_OF_BOARD`（与 `/api/board/fit-check` 的 `outOfBoardToolIds` 一致）
5. `POST /api/detect-paper` / `correct-image` 的 `data` 键与 SDS §4.1/§4.2 逐字一致；`warpedImage` 解码后尺寸 == `canvasPx`
6. `/api/generate` 的 `checks` 恰含 SDS §4.5 的 10 个 id，且 blocking/advisory 分组与 §4.5 一致
7. `GEO_ENGINE=new` 与 `legacy` 两种取值下，**8 个旧端点行为不变**（回归）
8. 变异验证：把某个 blocking check 强行置 false → `success:false`；把 `paramsEcho` 换个字段 → `SCHEMA_UNKNOWN_FIELD`

## 6. 接线 agent 硬约束
- **只新增** `python_backend/api/`（新目录）、`python_backend/export/`（新目录）、`python_backend/main.py` 里的新端点；**不删/不改任何旧端点**
- 允许整合 `geometry/__init__.py` 的 `generate_insert`（这是 M1-W 专属权限，三路 A/B/C 被禁止改）
- 允许改 `domain/models.py` 加 schema 转换所需字段，但不许删已有字段
- **不许** import `cad_engine`（SDS §7.1 冻结）；`GEO_ENGINE=legacy` 的 fallback 只允许「调用已存在的旧端点函数」，不新加依赖
- 不许改 `docs/planning/`、前端 `src/`、`requirements.txt`
- 不许为了测试变绿放宽任何容差

## 7. 目录规划（SDS §7.1，尚不存在的目录）
`python_backend/api/schemas.py`、`api/errors.py`、`export/stl.py`、`export/dxf.py`、`constants/gridfinity.py` 都还没有。M1-W 至少建 `api/schemas.py` 与 `export/stl.py`（DXF 是 M3 任务，本轮可不建）。

Open objectives: M1-W 是 M2 的硬前置；接线完成 + 独立审核通过后才开 M2。
