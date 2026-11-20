# pascalorg/editor 对 toolmanagement-web M2 多边形编辑器的参考价值报告

> 审查对象：`pascalorg/editor`，固定 commit `cf37d32cdc195a2a179d1f9e7d02624f6d834c3e`
> 报告目的：为 toolmanagement-web 项目 M2 多边形编辑器（SDS §6.3 已定 7 条需求）提供可借鉴/不可照搬的对照分析
> 取证方式：GitHub MCP `get_file_contents`（下载但正文不在此 harness 渲染）→ 改用 `web_fetch` 读取 `https://raw.githubusercontent.com/pascalorg/editor/<commit>/<path>` 原文；辅以 GitHub code search。所有结论均附具体文件/包路径。

---

## 1. 定位与技术栈（注意它现在是不是还是纯编辑器库）

**结论：它早已不是“纯 2D 多边形编辑器库”，而是一个完整的 AECO 3D 建筑编辑器产品 + 可拆分发布的库集合，且带 AI agent（MCP）能力。**

- `README.md` 自述："open-source 3D architecture software for AECO"，本地优先（local-first）、MIT 许可的**建筑编辑器**，基于 **React Three Fiber + WebGPU**；可建模 site/building/level/wall/slab/roof/opening/room/furniture，支持 3D 扫描参考层与 scan-to-BIM，并内置 **MCP server 供 AI agent 操作场景**。
- 发布物：`@pascal-app/core`、`@pascal-app/viewer`、`@pascal-app/cli`（npm）；可通过 `@pascal-app/editor` + `@pascal-app/nodes`（`loadPlugin(builtinPlugin)`）把整套编辑器嵌进宿主。CLI `npx @pascal-app/cli editor`；另有 Docker 自托管镜像 `ghcr.io/pascalorg/pascal-editor`。
- 技术栈（根 `package.json` + `docs/architecture.md`）：React 19.3.1 / Next.js 16.4.5、Three.js 0.187.0（WebGPU renderer）+ @react-three/fiber 9.8.2 + Drei、Zustand（场景/视图/编辑器三个 store）、Zod（node schema）、Zundo（undo/redo，50 步）、three-bvh-csg、Turborepo 2.11.10、Bun 1.4.4、TypeScript 6.0.2（`npm:@typescript/typescript6`）、Biome 2.6.5、Lingui 6.12.0、`ai` ^7.0.163 + `@ai-sdk/anthropic`（AI agent）。
- 运行约束：Node `^22.23.4 || ^24.22.1 || >=26.12.1`，`packageManager: bun@1.4.4`，workspaces `["apps/*","packages/*","tooling/*"]`；根脚本 `turbo run build` / `turbo run dev`（http://localhost:3002）。
- 因此它对我们只是“算法与交互模式的上游参考”，不是可直接 npm install 的 2D 多边形编辑组件。

---

## 2. 目录与真正的编辑器核心包位置

仓库已是 Turborepo monorepo（`docs/architecture.md` 有包职责表）：

- `packages/`：`cli`, `core`, `editor`, `eslint-config`, `geometry-script`, `ifc-converter`, `mcp`, `nodes`, `typescript-config`, `ui`, `viewer`
- `apps/`：`editor`（独立 Next.js 宿主）, `ifc-converter`
- `docs/`：`architecture.md`, `images/`, `media/`, `releasing.md`；另有 `wiki/`

**多边形编辑能力分散在三处，需组合阅读：**

1. **几何真源与数据模型** — `packages/core/src/`
   - `packages/core/src/lib/polygon-boolean.ts`：`export type Ring = [number, number][]`；`export type Polygon = {outer: Ring; holes: Ring[]}`；`MultiPolygon = Polygon[]`；`PolygonInput = Ring | Polygon | MultiPolygon`
   - 同目录还有 `polygon-union.ts`、`polygon-geometry.ts`（`dedupePolygonPoints` 容差 `1e-6`）、`polygon-relations.ts`、`polygon-label.ts`、`slab-polygon.ts`
   - `packages/core/src/schema/`（node schema）、`packages/core/src/store/use-scene.ts`（Zustand 场景 store）、`packages/core/src/store/history-control.ts`（历史事务/单步 undo）、`packages/core/src/hooks/scene-registry/`、`packages/core/src/systems/`、`packages/core/src/registry/types.ts`（affordance 描述符含 `priority?: number`）
2. **2D floor-plan 编辑 affordance（主力实现，2D 版）** — `packages/nodes/src/`
   - `packages/nodes/src/shared/polygon-vertex-affordance.ts`：四个共享 affordance 工厂（move-vertex / add-vertex / delete-vertex / move-edge）
   - `packages/nodes/src/slab/floorplan.ts`、`packages/nodes/src/ceiling/floorplan-affordances.ts`、`packages/nodes/src/zone/floorplan-affordances.ts`、`packages/nodes/src/floor-opening/floorplan-affordances.ts`：各 kind 接入上述工厂
   - `packages/nodes/src/polygon-centroid-move.ts`、`polygon-measurement.ts`
3. **拖拽调度/命中与 3D 交互层** — `packages/editor/src/`
   - `packages/editor/src/components/editor-2d/renderers/floorplan-registry-layer.tsx`：2D SVG 拖拽 dispatcher、命中优先级、手柄层级、单步 undo 调度（约 106KB 大文件）
   - `packages/editor/src/components/tools/shared/polygon-editor.tsx`：3D（R3F）通用多边形编辑器组件，zone / site boundary 编辑器在用
   - `packages/editor/src/lib/wall-polygon-draft.ts`：墙体多边形草绘（预览/提交分离的另一范例）、`packages/editor/src/lib/units.ts`
   - `packages/editor/src/store/`（useEditor 等）
   - 状态结构：`useScene` = {nodes: Record<id,AnyNode>, rootNodeIds: string[], dirtyNodes: Set<string>, createNode/updateNode/deleteNode, ...}（Zustand + Zundo，IndexedDB 持久化，50 步历史）；`useViewer` = {selection: {buildingId/levelId/zoneId}, levelDisplayMode, cameraMode, unit, metricNotation, ...}；`useEditor` = {active tool/mode, layer visibility, panel states, prefs}

---

## 3. 可直接借鉴的交互逻辑（对照 M2 的 7 条逐条）

先明确该仓库有**两套并存的多边形编辑实现**：
- **2D floor-plan 线**（新，主力）：`polygon-vertex-affordance.ts` + `floorplan-registry-layer.tsx` + 各 kind 的 `*.floorplan-affordances.ts`；
- **3D R3F 线**（旧/局部）：`components/tools/shared/polygon-editor.tsx`，用于 zone / site boundary。

| # | M2 需求 | 它有没有 | 实现要点（文件 + 函数/状态） |
|---|---|---|---|
| 1 | 顶点拖拽快照重算 | **有（两条线都有）** | 3D `polygon-editor.tsx` 的 `startDrag` 用 `initialPolygon: polygon.map(([px,pz])=>[px,pz])` 存快照，`handleVertexDrag` 从 `previewPolygonRef.current ?? polygon` 派生新数组（只改 `newPolygon[vertexIndex]`，不可变更新），拖拽全程基于 `initialPolygon` 重算而非累加增量。2D `polygon-vertex-affordance.ts` 的 `createPolygonVertexAffordance` 在 `start()` 捕获 `originalRing`，`apply()` 每 tick 都从原始 ring 重建。 |
| 2 | preview/commit 分离 | **有（非常完整）** | 3D：`onPolygonPreview(polygon|null)` 每 tick 发 in-flight polygon，commit 发 `null`；注释明确"Hosts wire this to `useLiveNodeOverrides` so the underlying mesh rebuilds at pointer rate while `onPolygonChange` stays a single store commit on release"；`previewPolygonRef` 是同步真源，`updatePreviewPolygon` 同时更新 ref+state+回调；`commitPolygonChange()` 才调 `onPolygonChange(previewPolygonRef.current)`。2D：dispatcher 的 `ActiveDrag.session.apply()` 借 `pauseSceneHistory` 实时写 store 但暂停历史，`SessionWrites` 记录本次写入以便取消时精确回滚；另有 `useFloorplanDraftPreview.wallPolygonDraftPoints`（`wall-polygon-draft.ts`）草稿只在本地 store，完成时才批量提交。 |
| 3 | 边中点插点并进入拖拽 | **有** | 3D：`handleAddVertex(afterIndex,position)` 插入后 `updatePreviewPolygon(newPolygon)` 并返回 `{polygon, vertexIndex: afterIndex+1}`，midpoint 的 pointerDown 里先 `onBeforeVertexDrag(index+1,point)` → `handleAddVertex` → `startDrag({mode:'vertex', vertexIndex: insertedVertex.vertexIndex, initialPolygon: insertedVertex.polygon, ...})`，即"插入即拖拽，不松手"。2D：`createPolygonAddVertexAffordance` 以 `(a+b)/2` 生成中点，`newVertexIndex=edgeIndex+1`，`start()` 立即 `commitRingPatch` 插入初始 ring，`apply()` 移动新顶点；"点而不拖"时 dispatcher 已拍的快照会回滚到插入前，成为 no-op。 |
| 4 | 拖边沿外法线 | **有（且处理了绕向）** | 3D：`getEdgeNormal(start,end)` 返回 `[-dz/length, dx/length]`（长度 <1e-6 返回 null），`grid:move` 的 edge 分支 `normalDistance = pointerDeltaX*normalX + pointerDeltaZ*normalZ`，仅 `initialPolygon[edgeStartIndex/edgeEndIndex] += normal*normalDistance`，其余顶点不动；外法线用质心判定翻转：`if (nx*(midpoint[0]-cx)+nz*(midpoint[1]-cz)<0)` 取反，兼容混合绕向；并根据法线投影到屏幕的 NDC 角切换 `ew-resize/nesw-resize/ns-resize/nwse-resize` 光标。2D：`createPolygonMoveEdgeAffordance` 同样 `normal=(-dy/len, dx/len)`，`projection = snapScalarToGrid(deltaX*normalX+deltaY*normalY, getSegmentGridStep())`，`fallbackPoint=start+normal*projection`；可选 `snapEdge` 让最终法向距离从**原始边**量取（"grab offset and pointer position drop out entirely"）；可选 `keepNeighbourAngles` 用 `movedEdgeKeepingNeighbours`（`IN_LINE_SINE=0.05`）。 |
| 5 | 命中优先级 顶点 > 边中点 > 边 | **有（多处显式实现）** | `slab/floorplan.ts` 的 `appendRingEditor` 发射顺序固定：先所有 `edge-handle`（命中区最大、z 最低）→ 再 `midpoint-handle` → 最后 `endpoint-handle`（顶点在最上），注释即"Emits in this order so the hit-test priority is sensible"。`floorplan-registry-layer.tsx` 的 `splitFloorplanHandles` 把 handle 放在所有节点 overlay 之后的独立 pass 渲染，避免邻墙轮廓盖住选中墙角点抢走按压（"the 2D twin of the 3D handle hit priority"）；`wiki/architecture/measurements.md` 记载 2D 层"gives vertices priority over edges, acquires registered corners within 16 screen pixels"；`packages/core/src/registry/types.ts` 的 affordance 描述符有 `priority?: number`（Higher values win）。3D `polygon-editor.tsx` 用 `NO_RAYCAST = () => null` 让纯视觉 mesh（edge bar/border line）不参与拾取，边拖拽手柄放在多边形**外侧**的 chevron 箭头，从结构上避开与顶点/中点重叠。 |
| 6 | 删到 3 顶点拒绝 | **有** | 2D：`polygon-vertex-affordance.ts` 的 `canDeleteCurrentVertex` 要求 `ring.length > 3`（<=3 直接拒绝）且 vertexIndex 为合法整数；`floorplan-registry-layer.tsx` 的 `floorplanHandleDoubleClickAffordance(geometry)` 仅当 `geometry.kind==='endpoint-handle' && geometry.affordance==='move-vertex'` 才映射为 `delete-vertex`（双击删除）。3D：`handleDeleteVertex(index)` 直接 `if (basePolygon.length <= minVertices) return`（默认 `minVertices=3`）。 |
| 7 | 一次拖拽 = 一条 undo | **有（核心机制值得抄）** | `packages/core/src/store/history-control.ts` 的 `runAsSingleSceneHistoryStep(sceneStore, run)`：进入时 `commitTransactionDepth += 1`，`run` 内多次写入产生多个 zundo past state，退出时用 `retainedPastStateCount(before, after)` 算出新增数 `addedCount`；若 `addedCount > 1` 则 `pastStates` 只保留 `firstAddedState`（`[...afterPastStates.slice(0,retainedCount), firstAddedState]`）；若事务内提交是 no-op 则把 pastStates 截回 `retainedCount`。另有 `beginSceneHistoryPauseSession(sceneStore,{gesture})` 返回 `{commitStep(write), end()}`，支持"gesture co-owners"（同一节点的 3D mover 与 2D overlay 共用一个 key），"whichever view drops records the one step"。2D dispatcher 的 `ActiveDrag.historyPaused` + `session.commitStep` 正是"暂停历史实时写、释放时记一步"；`wall-polygon-draft.ts` 的 `commitWallPolygonDraft()` 把整批 `scene.applyNodeChanges({create,update,delete})` 包进 `runAsSingleSceneHistoryStep(useScene, ...)`。 |

---

## 4. 不可照搬的坑

1. **React / 构建工具强绑定**：根 `package.json` 把 `react 19.3.1`、`react-dom 19.3.1`、`next 16.4.5`、`@react-three/fiber 9.8.2`、`three 0.187.0` 全部写进 `overrides`，工具链是 **Bun 1.4.4 + Turborepo 2.11.10 + Biome 2 + TypeScript 6.0.2**，并有 `patchedDependencies`（`three@0.187.0`、`three-bvh-csg@0.0.18`、`iwer@2.3.0`）。任何源码级复制都会把这些版本约束带进来；M2 不应引入 R3F/WebGPU/Bun 依赖，只抄算法与状态机思路。
2. **不是 Canvas 像素当几何真源，但手柄尺寸是屏幕像素**：几何真源是 `node.polygon`（`[number,number][]` 世界米制坐标，2D 用 `[x,z]` 平面）+ holes，绝不用画布像素存几何——`slab/floorplan.ts` 明确"handles live on the RAW `node.polygon`"；渲染用的 `getRenderableSlabPolygon` 与原始 polygon 不一致时用虚线 skeleton（`strokeDasharray '0.08 0.06'`）提示手柄实际抓取位置。但**手柄命中/视觉尺寸按屏幕像素定义**：`floorplan-registry-layer.tsx` 中 `ENDPOINT_HANDLE_SELECTED_RADIUS_PX=8`、`HIT_STROKE_WIDTH_PX=18`、`DIRECT_DRAG_THRESHOLD_PX=4`、`MAX_HANDLE_UNITS_PER_PIXEL=0.015`，靠 `unitsPerPixel` 换算（"stay screen-sized until world-space ceiling takes over"）。抄这个"世界坐标存真值 + 屏幕像素定手柄"的分层，别抄它的 SVG/R3F 渲染细节。
3. **坐标单位不是毫米**：2D 平面坐标是米（浮点），容差 `1e-6`（polygon 去重）、`1e-3`（`wall-polygon-draft.ts` 的 1mm 吸附判定、`endpointKey` 用 `Math.round(x*1000)` 做 1mm 折叠）。M2 若内部用毫米整数，这些魔法数必须整体重算，不能照抄。
4. **3D 与 2D 两套实现并存且有行为差异**：3D `polygon-editor.tsx` 的 midpoint 只在 `!dragState` 时显示、edge 从外侧箭头起拖；2D `floorplan-registry-layer.tsx` 走 affordance dispatcher + `SceneWrites` 回滚。别把两套混着抄。
5. **大量领域耦合**：affordance 提交时 boundary 走 `scene.detachDerivedNode(id, patch)`（把 reconciler 派生的 slab/ceiling 转成用户 authored 表面），hole 走 `scene.updateNodes`；还有 `SceneSnapshot` 包含 `nodes/rootNodeIds/collections/materials/installedPlugins`、`noteDerivedNodeWrites`、`subscribeSceneCommits`、协同远程写入判断（`isApplyingRemoteSceneChange`）等 AECO 专有概念，M2 用不上。
6. **3D 线的外法线基于 `[x,z]` 平面 + Y_OFFSET**；M2 若是屏幕平面坐标，法线公式形式要相应调整。
7. **AI/MCP 与发布形态差异**：仓库内 `packages/mcp`、`packages/nodes/src/agent-tools`、AI SDK 依赖属于 agent 工具链，与多边形编辑交互无关，勿引入。

---

## 5. 许可证与版本

- **LICENSE（原文确认）**：`MIT License`，`Copyright (c) 2026 Pascal Group Inc.`，标准 MIT 授权/免责条款。
- README 说明：editor、packages、CLI、MCP server 为 MIT；`docs/media/next-demo` 下的演示视频为 **CC BY 4.0**（独立许可，不属于代码）。我们只借鉴思路与自写代码，MIT 完全兼容；若直接复制代码须保留 MIT 版权声明。
- 版本锚点：commit `cf37d32cdc195a2a179d1f9e7d02624f6d834c3e`；根包 `name: "editor", private: true`；Node 要求 `^22.23.4 || ^24.22.1 || >=26.12.1`；`packageManager: bun@1.4.4`。文件级 blob sha（取证用）：`polygon-editor.tsx` = `df66ff3847ee2a6425699289fdd088f55f6bf459`，`polygon-vertex-affordance.ts` = `406f086c35f7924a112c8ab4b3142748ca55910c`，`history-control.ts` = `1417252d3dfc237653c5d816cd9503bb06494244`，`slab/floorplan.ts` = `590cb8eb0ec484b0264a4400aad781511fba07ea`，`wall-polygon-draft.ts` = `704a9443f80fc3f1572a237f139ef812a7899665`。

---

## 6. 对本项目 M2 的具体建议（适配毫米坐标 + Zustand + zundo）

**建议直接抄的交互模式（算法级，与框架无关）：**

1. **拖拽状态机 + 快照重算**（抄 `polygon-editor.tsx` 的 `DragState`）：`{mode:'vertex'|'edge'|'midpoint-insert', initialPolygon: 深拷贝, pointerId}`，每次 pointermove 从 `initialPolygon` 重算新 polygon，禁止基于上一帧增量累加。
2. **preview/commit 分离**（抄 `onPolygonPreview` 契约）：preview 写入独立的 `previewPolygon` ref/selector（供渲染层实时重绘），只有当次 pointerup 才写 Zustand 正式 store 一次；`previewPolygon` 用 ref 做同步真源以避免 React 批处理丢帧。
3. **中点插入即拖拽**（抄 `handleAddVertex` + midpoint pointerDown 顺序）：pointerdown 时把中点插入 preview、把 `vertexIndex` 设为插入位置，直接进入 vertex drag；"点而不拖"时 pointerup 还原 preview 为 null，实现无副作用的 no-op。
4. **沿边外法线拖边**（抄法线公式与质心翻转）：`n=(-dy/len, dx/len)`，用质心判定翻转保证朝外，`normalDistance=dot(pointerDelta, n)`，只移动该边两端点；按法线屏幕方向切换 resize 光标。
5. **命中优先级**（抄 `appendRingEditor` 的发射顺序思想）：命中检测按 vertex → midpoint → edge 顺序，顶点优先；手柄视觉层独立于多边形主体层渲染，避免被后续图形盖住抢事件；可视元素的 raycast/命中应关闭（`NO_RAYCAST` 思路）。
6. **双击顶点删除且少于 3 顶点拒绝**（抄 `canDeleteCurrentVertex`：`ring.length > 3`）。
7. **一次拖拽一条 undo**（抄 `runAsSingleSceneHistoryStep` 的收缩思路，但用 zundo API 重写）：pointerdown 时 `zundo.temporal.pause()`，拖拽期间所有预览写不走历史；pointerup 时先提交最终 polygon 到 Zustand，再 `zundo.temporal.resume()` 让这一笔进入 pastStates。若采用"每 tick 写 store + 暂停历史"方案，则需在结束时按 Pascal 的 `retainedPastStateCount` 思路裁剪 `pastStates` 只保留首个快照——**优先用 pause/resume 方案，更简单**。若一次拖拽混用 2D 编辑器与 3D 视图两处写同一节点，借鉴 `beginSceneHistoryPauseSession({gesture})` 的 co-owner key 保证只看最终一致态。

**必须自己写以适配 M2 环境与约束的部分：**

1. **坐标与单位**：M2 状态以毫米（整数或高精度小数）为真源；所有容差、吸附半径、1mm 折叠键（`endpointKey` 思路可借鉴但要按我们的量级重定）、`1e-6/1e-3/0.015` 等常量全部重算；网格吸附按毫米步长。
2. **Zustand + zundo 落地**：在 M2 的 polygon store 中显式定义 `polygon`（committed）与 `previewPolygon`（不进历史）两个字段；用 `temporal.pause()`/`resume()` 包住整个 gesture，或对 zundo 的 `partialize` 配置确保只追踪 committed polygon；取消（Esc / pointercancel）时回滚到 pointerdown 快照且不产生 undo。
3. **无 R3F / 无 SVG 三件套**：用我们自己的渲染层（Canvas/SVG/浏览器事件）实现手柄与命中，仅搬状态机与数学；不引入 React 19 / Next 16 / Bun / Turbo / three 依赖。
4. **数据模型对齐**：我们的多边形节点结构（id / points / holes / parent）需自建 `getRing/buildRingPatch` 等价函数；不需要 `detachDerivedNode`、`SceneSnapshot`、`noteDerivedNodeWrites`、协同 remote 判断等 AECO 概念。
5. **测试**：按 7 条需求逐条写交互测试（快照重算、preview 不落库、中点插入 no-op、法线方向、命中优先级、3 顶点拒绝、一次拖拽一条 undo），Pascal 的测试在 `packages/nodes/src/__tests__` 与各 `*.test.*`，但其 fixture 依赖完整场景树，不能直接复用。

**优先级建议**：先移植 1/2/3/7（快照 + 预览提交 + 插点即拖 + 单步 undo），这四条是 M2 体验与正确性的核心；4/5/6 作为第二梯队。整体"抄思路不抄代码"，MIT 兼容但无需搬运其源码。

---

## 证据索引（路径速查）

- 定位/技术栈：`README.md`、根 `package.json`、`docs/architecture.md`
- 许可证：`LICENSE`
- 几何类型：`packages/core/src/lib/polygon-boolean.ts`
- 历史单步：`packages/core/src/store/history-control.ts`（`runAsSingleSceneHistoryStep`、`beginSceneHistoryPauseSession`）
- 2D affordance：`packages/nodes/src/shared/polygon-vertex-affordance.ts`（四个 `createPolygon*Affordance`）
- 手牌发射顺序：`packages/nodes/src/slab/floorplan.ts`（`appendRingEditor`）
- 2D 调度/命中/像素手柄：`packages/editor/src/components/editor-2d/renderers/floorplan-registry-layer.tsx`（`ActiveDrag`、`splitFloorplanHandles`、`floorplanHandleDoubleClickAffordance`、`endpointKey`）
- 3D 编辑器：`packages/editor/src/components/tools/shared/polygon-editor.tsx`（`DragState`、`onPolygonPreview`、`getEdgeNormal`、`handleAddVertex`、`handleDeleteVertex`）
- 草稿预览提交：`packages/editor/src/lib/wall-polygon-draft.ts`（`commitWallPolygonDraft`）
- 命中优先级文档：`wiki/architecture/measurements.md`、`packages/core/src/registry/types.ts`（`priority?: number`）
