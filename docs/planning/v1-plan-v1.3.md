# Toolmanagement-web 开发计划 v1.3

> **v1.3 = v1.2 + 第四轮闭环审核（final-closure，双 lens）修订。**
> 两位审核员独立得出同一根因：判据换了新变量、几何仍按旧变量写。本版修 6 条硬问题 + 7 条表内算术/量纲：
> **① z 基准双值**（`thickness` vs `heightU*7`）→ 引入唯一量 `top_z`；
> **② scoop 没有几何** → SDS §7.4 首次给出完整构造；
> **③ scoop 连通性断言恒假**（2D `CrossSection` ∩ 3D `Manifold`）→ 改 3D 体积求交；
> **④ 手孔 z 断言互相夹死** → 按 `depthMode` 二分；
> **⑤ 槽长容差 ±1 vs ±0.1** → 统一 ±0.1；
> **⑥ `embedDepth` 滑块上界用 `thickness`** → 改 `top_z`（6U 板此前永远选不到竖直孔）；
> **⑥.5 第六轮 delta 审核（只审 ⑦⑧ 两条新反馈）双 lens 均判「需小修」，8 条 must-fix 已合并（修订表 #51–#58）**：板框锚点未定义、`print-bed` 必分块、gridfinity 三真源、scoop 的 `run` 仍用 `margin`、`TOOL_TOO_LONG` 用 `margin`、2.5 记 0 人日、`INVALID_SIZE_MODE` 判据、畸变因果。
> 另修：6U 算术（28.25 → **35.25**）、`LIP_WIDTH` 新增、磁孔跨格心距 16mm、D19' 请求体 `paperW/paperH`、D15' 板厚不参与手孔判定、修订表补 #31–#37。
> **第四轮 P1 亦已修完**：`slot_bounds`→`slotBounds`（camelCase）、1.1 倒角 DoD 改凸包边中点（bbox 宽差是恒真断言）、`depth` 唯一绑定式、`depth_fits` 给谓词、唇径向带改 `LIP_WIDTH=2.6`、阻塞边 `0.4→0.3→0.6` 串行。
>
> **第五轮终验（geo + contract 双 lens）两方均判「需小修、可开工」，must-fix 已全部合并**（修订表 #38–#48 共 11 条新行，含 3 条由前一轮修复引入的反向问题）：0.4 DoD 端点改 `/api/correct-image` + `warpedImage`（原写 `/detect-paper` + `warped_image` + 不存在的 `px_per_mm`）、3.2 的 `error_code`→`error.code`、D6' 形状字面量改 SDS 口径（`rect`/`filleted_rect`，原写 `rectangle`/`filleted_rectangle` 会被后端判非法）、D8' 的 clamp 改分外形（原 `height_mm − 2` 让 3U 切穿底座）、并行口径改为「仅 3.1/3.4 可提前」、1.5 六形态改两组参数（默认 embedDepth=8 下竖直孔被禁，单组跑不出）、1.4b 段容差 ±0.01 / 总和 ±0.05。
>
> **v1.3 增补（用户 m02193 两条反馈，2026-11-03）——均在定稿后追加，不改变里程碑与工期：**
> **⑦ 板尺寸是独立自由度，与工具数量解耦；板框锚点 = 未隐藏工具并集 bbox 中心**：`BoardConfig` 新增 `sizeMode: 'fit-tools' | 'custom' | 'print-bed'`（+ `widthMm`/`heightMm`）。A4 只承担「量尺」作用；板多大由用户决定——可以只放一把小件（60×60）、可以按最小 Gridfinity、可以铺满打印床、也可以自定义更大再分块。板大于工具并集时**允许留白，不自动居中、不自动排布**。Q5 关闭，**无待定项**。见 D15'、D2'、D3'、修订表 #49。
> **⑧ 镜头畸变：不标定、不告警，用留白吃掉**：`margin` 默认 **8 → 12mm**。手机广角边缘 1–2% 桶形畸变在 210mm 纸宽上约 2–4mm。**说清楚它吃什么**：`margin` 吃的是**板边余量**（工具贴在纸边被畸变推出画面时仍有材料兜住），**不是**修正工具轮廓——轮廓本身的 1–2% 局部误差仍在，所以 S0 ±1.5mm **只对「完整落在纸面内、离纸边 ≥ 20mm」的工具承诺**。**不做** `cv2.calibrateCamera`、不做 ArUco、不做去畸变、不做 `distortionWarningMm` 告警；工具贴板边时给 `BOARD_EDGE_TIGHT` warning 提示。见 D16'、§5、修订表 #50。
>
> **审核收敛记录（六轮）**：v0.3→v1.0 四路（exec/sds/risk/value）→ v1.1 双 lens（closure/cold-read）→ v1.2 逐条闭环 → v1.3 终验（geo/contract）。**每轮新引入的问题数：23 → 15 → 13 → 11，已进入收敛尾部**；最后一轮的 11 条里 6 条是「修 A 时把 B 写死」的同源模式（判据与几何用了不同变量）。因此本版额外加了一条**自检铁律**：
> **任何「判据/参数」与「用到它的几何」必须共用同一个局部量**（`top_z` / `depth` / `clearance` / `chamfer` 四个绑定式，见 SDS §7.3），审查时只需 grep 这四个名字有没有被绕过。
>
> **状态：计划与 SDS 均已达可开工状态。** §7 的 Q1–Q7 **全部已决**（Q5 由用户 m02193 关闭：板尺寸与工具数量无关），**无待定项**。
> **新会话实施交接见 §9**（启动口令、开工前清单、环境注意事项、遗留项）；SDS 侧对应 §12.4。
>
> **v1.2 = v1.1 + 第三轮独立审核（closure / cold-read）修订。**
> 第三轮：closure 判 15 CLOSED / 7 PARTIAL / 1 MISSING；cold-read 给出 7 条 P0 + 12 条 P1 + 11 条 P2。最严重的三条同源——**手孔形态按板厚分档**，Gridfinity 3U 的「等效厚度 16.25」落进 12–25 的空档、「等效厚度」实为可用腔深（量纲错）、scoop 坡底写成 `thickness − depth` 会把 12mm 板整片切穿。本版改成**单一连续判据 `embedDepth ≥ 20`**，坡底改 `thickness − embedDepth`，改动表见 §3.1 D6'（修订 2）。**⚠️ 这两处是 v1.2 的历史状态，v1.3 已进一步修正**：判据改用**生效 `depth`**（`depthOverride ?? embedDepth`）、坡底改 `top_z − depth`，见修订表 #24 与 D6'（修订 2 已在 v1.3 后被 D6' 现行版取代）。
>
> **v1.1 = v1.0 + 2026-11-03 第二轮独立审核（closure / cold-read）修订。**
> 第二轮发现 28 条一轮问题中 15 条已关闭、13 条部分关闭；另新引入 23 条矛盾，其中 6 条属「静默错且 DoD 抓不到」级别（z 原点两套并存、`to_board_frame` 符号错、契约三套字段名、板厚 20 落进手孔空档、移植清单保留取负、Gridfinity 总高两个值）。**本版逐条修完，改动表见 §0.1。**
>
> **v1.0 = v0.3 + 2026-11-03 四路独立审核（exec / sds / risk / value）修订。**
> 审核裁决：exec = 需大修，sds / risk / value = 需小修。本版逐条吸收，改动集中在三处：
> ① §2.3 的 y 轴约定**写反了**，已纠正并补齐为六条；② §4 由"里程碑串"改成**阻塞图 + 可离线复现的 DoD**，新增 M-1 冒烟与 0.3b / 0.7 / 0.8；③ 新增 §3.1（D1'/D6'/D8'/D14'/D15' 修订 + D18'–D21'）。
> 工期由 16 人日降到 **15.0 人日**（砍掉畸变标定、打印反馈回路、first-fit 自动排、亚像素精修；v1.3 板尺寸控件 +0.5 补回）。**v1.3 追加**（用户 m02193）：板尺寸改为独立参数（`sizeMode` 三选一）、`margin` 默认 8 → 12 吃掉镜头畸变。**畸变项是纯减法**（删掉标定、去畸变、告警三处）；**板尺寸控件是新增工作**（4 条独立可验收行为 + 一套与后端对齐的边界判据），计 **0.5 人日**，故 **M2 由 3.0 → 3.5**，总工期 **14.5 → 15.0 人日**。


> 状态：**推翻 v0.2 的主线**。v0.2 已归档，仅其"问题诊断"部分继续有效。
> 依据：三轮独立红队复审（产品/几何/交付）+ tracefinity 源码全量通读。
> 日期：2026-11-03
> 规模：**15.0 人日**，M-1–M4 六个里程碑（M-1 冒烟 0.5 / M0 2.5 / M1 3.5 / M2 3.5 / M3 3.5 / M4 1.5）


### 0.1 v1.1 / v1.2 修订表（第二、三轮审核，逐条可查）

> #1–#23 来自第二轮（cold-read 的 6 条静默错 + 其余）；#24–#30 来自第三轮（7 条 P0）。

| # | 问题 | 修法 | 落在 |
|---|---|---|---|
| 1 | z 原点两套并存（`H/2 + 0.9` 与 `thickness + 0.9`），H=20 时前一条**永远通过** | 全项目只剩 `z=0 在板底、板顶 = top_z`（**#31 进一步明确 `top_z`，见下**）；删除 ±H/2 居中 | §1 F1、§2.3 第 2 条、D12'、M-1、0.2、1.1、1.5 |
| 2 | `to_board_frame` 的 `y=(origin.y+board_h)−p.y` 值域是 `[−h,0]`，不是 y-up | 改 `Vec2(p.x−center.x, center.y−p.y)`，板原点 = 板外接框中心 | §2.3 第 6 条 |
| 3 | 计划 D19' 与 SDS 各写一套字段名 | **以 SDS §3/§4 为唯一真源**，camelCase，未知字段 400 | D19' |
| 4 | 手孔板厚默认 20 落在 12 与 25 之间的空档 | 板厚枚举 6/12/25（默认 12）；`HoleShape` 加 `scoop`；sphere 改球缺 | D6'、1.5 |
| 5 | 移植清单把 `stl_generator_manifold.py:809-966`/`:969-1039` 标为"原样"，但 `:896`/`:984` 是 `-(p[1]+offset_y)` | 移植时删取负与 `offset_y` 形参；0.6 加非对称 fixture | §2.1 #4/#5/#6、0.6 |
| 6 | Gridfinity 总高 SDS 内部两个值（`7U+4.75` vs `7U`） | 统一 `7U`（3U = 21），加断言 | D8'、SDS §7.2 |
| 7 | 倒角三参数三套名（`fillet`/`corner_r`/`slot_chamfer`/`base_chamfer`） | 只留 `cornerR` / `baseEdgeRoundover` / `slotChamfer` | D15'、1.0b、2.3a/b |
| 8 | 1.6 依赖 2.3a，但 2.3a 排在 M2 | 新增 **1.0b** 把三参数提到 M1；2.3a 降级为联调验收 | M1 / M2 |
| 9 | 唇剖面抄 cq-gridfinity 的斜边写法折算 8.09，DoD 要 8.2 | 真源改 tracefinity `LIP_D0..D4`（2.6/1.2/0.7/1.8/1.9） | §2.4、1.4b |
| 10 | 1.1 锥台取样高差 `chamfer−0.1`，宽度差 2.8 而断言 3.0 必红 | 改取 `z = top_z − 1e−6` 与 `top_z − chamfer`（#31 后统一用 `top_z`） | 1.1 |
| 11 | 容差三处三值（1.0 / 0.5 / ±0.05mm² 与 ±2×clearance 量纲互斥） | 新增 SDS §10.3 容差总表，全部指向它 | 0.3、0.6、1.2 |
| 12 | 缺"槽/手孔必须落在板轮廓内"校验 | 新增 `tools_in_board`（阻断，`TOOL_OUT_OF_BOARD`） | SDS §7.6 第 9 条 |
| 13 | 人日账 16−3.0+2.0=15.0 却报 14.5 | 基线改 15.5、加法含 1.0b 共 +2.5、再扣 1.6 返工 0.5 | §7 |
| 14 | D3' 保留 first-fit，但 §5 已砍 | D3' 同步删除 | D3'、§2.2 #7、§5 |
| 15 | 0.8 要改 `cad_engine.py` 的 17 处 `except`，但 SDS 宣布该文件冻结 | 范围收窄为"新代码 + main.py 信封层"，旧文件只许加计数行 | 0.8 |
| 16 | `NO_SPLIT_RIB` 被两种原因复用 | Gridfinity 分块改 `GRIDFINITY_SPLIT_UNSUPPORTED` | 3.2 |
| 17 | 3.4 DXF 未定义 y 翻转，面积类 DoD 对镜像不敏感 | 默认翻转，DoD 加非对称点断言 | 3.4 |
| 18 | `is_watertight` 单独用等于没查 | 已在 D12' 两级自检 + 首击射线断言 | D12'、M-1 |
| 19 | M-1 冒烟射线原点 `[50,10,60]` 对 100×20 居中槽正好落在角顶点 | 改 `[0,0,thickness+10]`（落在槽内部） | M-1 |
| 20 | `git commit -am` 不纳入未跟踪的 `docs/planning/*.md` | 改 `git add -A && git commit` | SDS §11.4 |
| 21 | 照片体检在计划里是 M0 的 0.5，SDS §1.1 却记在 M3 | 里程碑改 M0 | SDS §1.1 |
| 22 | 0.3/0.4 被排进可并行组，但 0.4→0.3 是阻塞边 | M0 分工改三批次（见 SDS §12.1） | SDS §12.1 |
| 23 | `checks` 十项没写清 blocking / advisory | 六项 blocking、四项 advisory | SDS §4.5 |
| 24 | **手孔形态按板厚分档**：Gridfinity 用「等效厚度 `heightU*7−4.75`」套 ≤12/≥25 两档，3U=16.25 落进空档；且该值实为**可用腔深**、量纲不对 | 改用**单一连续判据** `depth ≥ FINGER_REACH_MM(20.0)`（`depth = depthOverride ?? embedDepth`）→ 竖直孔，否则 scoop；板厚只作 UI 快捷档、不参与判定 | §3.1 D6'（修订 2）、1.5、2.2、SDS §7.4 |
| 25 | **scoop 坡底写成 `z = thickness − depth`**：12mm 板 `depth=12` → 坡底 z=0，**整片切穿板底** | 坡底 = **槽底** = `top_z − embedDepth`（#31 后统一用 `top_z`，rect 时 `top_z = thickness`）；断言 `abs(bbox[2] − (top_z − embedDepth)) ≤ 0.01`（`bbox[2]` = minZ） | 1.5、SDS §7.4 |
| 26 | **手孔 z 三条断言互相夹死**：25mm 板 `depth=20` 时孔底 z=5，但另一条要 `bbox[0][2] ≤ 0.1`；改 through 后 `≥ 0` 又必红 | `depth` 的 clamp 只对 `blind` 生效；`through` 下界取 −1、断言 `≤ −0.5`；`≥ 0` 那条改成 `abs(bbox[2] − (top_z − depth)) ≤ 0.01`（`bbox[2]` = minZ；#31 后统一 `top_z`；原式**恒真**，等于没查） | 1.5、SDS §7.4 |
| 27 | **`wantDxf` / `dxfFlipY` 不是 schema 字段**：响应说「带 wantDxf 就附 DXF」、DXF 节说「`dxfFlipY` 默认 true」，但 `BoardConfig` 里都没有，而未知字段一律 400 → **DXF 交付不可达、翻转开关无处可关** | 两者写进 `BoardConfig`（`wantDxf: false` / `dxfFlipY: true`） | SDS §3.1、§9.2 |
| 28 | **Python `FingerHole` 缺 scoop 三字段**（TS 侧有 `scoopWidth` / `scoopAngleDeg` / `scoopDir`，PY 侧没有）→ 任何 scoop 请求 100% 400，而薄板**只允许** scoop → 薄板手孔整体不可用 | PY dataclass 补 `scoop_width` / `scoop_angle_deg` / `scoop_dir` | SDS §3.1、§7.4 |
| 29 | **错误码枚举缺 4 个（v1.3 后共 18 个）**：`TOOL_OUT_OF_BOARD`、`GRIDFINITY_SPLIT_UNSUPPORTED`、`SCHEMA_UNKNOWN_FIELD`、`SCHEMA_VERSION_UNSUPPORTED` 在正文用到、枚举里没有 | 枚举补齐到 **18** 个（v1.3 再增 `INVALID_SIZE_MODE`），并注明 `DEPTH_EXCEEDS_THICKNESS` **只作 warning** | SDS §4.0 |
| 30 | **磁孔「距格角 4.8」与「孔心距 26mm」算术互斥**：`42 − 2×4.8 = 32.4 ≠ 26` | 真值：孔心相对**格心 ±13.0**（距格角 8.0）；`MAGNET_INSET = 4.8` 是**孔边到格角**（`8.0 − 6.5/2 = 4.75`），**不参与定位** | 1.4c、SDS §7.2 |
| 31 | **z 基准双值 → Gridfinity 分支整体不可用**：`thickness` 只有 6/12/25，而 gridfinity 板顶是 `heightU*7`，切刀按 `thickness − depth` 埋进 9mm，槽成密闭内腔、`slot_open` 恒 false | 引入唯一量 `top_z`（rect = `thickness`；gridfinity = `heightU*7`），全文 `thickness − X` 改为 `top_z − X`（SDS §2.3/§7.2/§7.3/§7.4、本文 §1 修法第 1 条与 §4 的 `1.1`/`1.5`） | 第四轮审核 N1 |
| 32 | **scoop 没有几何**：默认 `embedDepth=8` + `thickness=12` 开箱即 scoop，而 SDS §7.4 表只有四种形状；且 45° 下「进深 = embedDepth」与 `scoopWidth` 10–15 过定，空间也装不下（进深 8 = `margin`） | 在 SDS §7.4 给出 scoop 的完整构造：落差 `embedDepth`、`run = embedDepth / tan(angle)`、`run ≤ d_edge − clearance`（`d_edge` = 槽壁到板轮廓的**实测**距离，**不是 `margin`**：custom/print-bed 下二者无关）否则 clamp 角度并 warning `SCOOP_CLAMPED`、`scoopWidth` 改为**沿槽壁的坡宽**（不参与进深） | 第四轮审核 P0-3/N2 |
| 33 | **scoop 连通性断言恒假**：原文要求 `CrossSection` 与槽切刀求交面积 > 0，但槽切刀是 `Manifold`（3D），2D∩3D 不可交；按 XY 投影解释则正确几何（坡道在槽外、只共边）恒为 0 | 改为 **3D 体积求交** `(scoop_cutter ^ pocket_cutter).volume() > 0.1` + 坡底 `abs(bbox[2] − (top_z − embedDepth)) ≤ 0.01`（`bbox[2]` = minZ） | 第四轮审核 P0-3 |
| 34 | **手孔 z 三条断言互相夹死**：`blind` 孔的 `bbox[0][2] ≤ 0.1`（「真贯穿」）与 `depthMode='blind'` 互斥，合法实现必红；且 `depth = min(embedDepth+8, thickness)` 无下界无上界，25 板 + embed 20 时正好打穿 | 断言按 `depthMode` 二分（`blind` 查 `top_z − depth`，`through` 查 `≤ −0.5`）；`depth = clamp(embedDepth+8, embedDepth, top_z−1)` | 第四轮审核 P0-2 |
| 35 | **槽长容差两个值**：SDS 冒烟代码 `< 1.0`，而 §10.3 容差表与本计划 M-1 都写 ±0.1——±1 会放过 0.9mm 的 scale 残留（正是 F1 类静默错），且这段代码会被整段抄进 `scripts/smoke_geometry.py` | SDS §10.1 冒烟代码改 `< 0.1` | 第四轮审核 N3 |
| 36 | **`embedDepth` 滑块上界用了 `thickness`**：6U 板（板顶 42）滑块被 `12−2=10` 封顶，用户永远选不到 ≥20，「6U 可选竖直孔」在 UI 上不可达 | 滑块上界改 `top_z`：rect `[2, thickness−2]`、gridfinity `[2, heightU*7−4.75−2]` | 第四轮审核 N4 |
| 37 | **唇「高 8.2」被当「外圈带宽」用**（SDS §7.2 第 3 条、§7.6 第 7 条）：8.2 是垂直唇高，径向宽度全文未定义 | 新增独立常量 `LIP_WIDTH`，由唇剖面**各段水平投影之和**算出（`sum(seg.h*\|sin a\| + seg.run)`），实算 2.6mm，并加断言 `abs(LIP_WIDTH − 2.6) ≤ 0.05` 卡住；凡「离顶面外沿 X mm 内禁切」一律用它。**注意**：`LIP_D0 + LIP_D2` 是两个**垂直**段高之和，不是径向宽度 | 第四轮审核 N7 + 第五轮 contract lens |
| 38 | **scoop 的 `run` 上界写成 `margin`**：`margin` 只在 `'fit-tools'` 下近似等于真实边距；`'custom'`/`'print-bed'` 下工具可能贴板边，此时 `margin` 与真实余量无关，坡道会从板侧切穿而 `tools_in_board` 只查「在板内」不查「距边 ≥ margin」，checks 全绿。默认 12 板 / `embedDepth=8` + 45° 时 `run = 8`，用 `margin` 判会误放行 | `run ≤ d_edge − clearance`（`d_edge` = 槽壁到板轮廓的**实测** `shapely.distance`），超出时 clamp `scoopAngleDeg` 使等号成立 + warning `SCOOP_CLAMPED`；`d_edge < clearance + 1.0` → 阻断 `GEOMETRY_INVALID` | 第五轮 geo lens + 第六轮 geo P0-2 |
| 39 | **scoop 连通性断言对正确实现恒假**：坡道竖直面正好贴槽壁起切，楔块与槽切刀只共一个面，交集体积 = 0 = 阈值边界 | 楔块沿 `scoopDir` 向槽内**侵入 ≥ 0.5mm**（起切点从槽壁面内移 0.5mm），再断言 `(scoop ^ pocket).volume() > 0.1` | 第五轮 geo lens |
| 40 | **scoop 与 `depthMode='through'` 互斥**：坡底恒为槽底 `top_z − depth`，`through` 要求下界 `−1`，两条断言不能同时满足 | 明确 `through` 只对 `cylinder`/`square`/`rect`/`filleted_rect` 生效；UI 在 `scoop`/`sphere` 下禁用该开关 | 第五轮 geo lens |
| 41 | **`sphere` 缺开口守卫**：`radius < depth/2` 时球顶落到板顶以下，生成**完全封闭的空腔**——水密、体积、`slot_open` 全绿而手伸不进去（F1 复发） | 加 `assert centerZ + r > top_z + 0.1`；`sphere` 只允许 `blind` | 第五轮 geo lens |
| 42 | **`embedDepth` 上界注释写成「即 `top_z−2`」**：3U 板得 19（真值 14.25），槽底切到 z=2、插进 4.75 高的锥台底座 2.75mm | `BoardConfig.embedDepth` 注释与 §7.6 第 1 条都改**分外形**：rect `thickness−2` / gridfinity `heightU*7 − 4.75 − 2` | 第五轮 contract lens |
| 43 | **倒角锥台用 `chamfer`、DoD 也按 `chamfer` 量**，而实现是 `eff = min(chamfer, max(0, depth−1))`：滑块拉到 `chamfer=1.5 / depth=2` 时 `eff=1`，DoD 必红 | 1.1 的锥台区间改 `[top_z − eff, top_z]`，取样两点改 `top_z − 1e−6` / `top_z − eff`，DoD 按 `eff` 量 | 第五轮 geo lens |
| 44 | **1.1 的 DoD 在矩形上恒真**：`scale_top` 按 bbox 仿射时，bbox 宽差**恒等于** `2×chamfer`；「四条边中点」在矩形上就是 bbox 边中点，同样恒真 | 改为在**外轮廓凸包**的各条边中点取样（L 形 fixture 才有区分度）；并明确 **v1 接受仿射实现**（manifold3d 无 loft），另加凹角告警 `CHAMFER_NARROW_AT_CONCAVE`（`offset(Miter)` 面积差 >15% 时 warning，不阻断） | 第五轮 geo lens |
| 45 | **判据用 `board.embedDepth`、几何用 `depthOverride ?? embedDepth`**：`depthOverride=5` 时判据说"竖直孔"但只挖 5mm，scoop 坡底也对不上槽底 | 判据与几何统一用**生效 `depth`**；`depthOverride` 加 clamp `min(depthOverride, top_z−2)` | 第五轮 geo lens |
| 46 | **`build_pocket_cutter` 函数体用了未绑定的 `top_z`/`clearance`/`chamfer`**，且 `clearanceOverride`/`chamferOverride` 的优先级全篇未给 | §7.3 给出四个局部量的唯一绑定式（`top_z = board_top_z(board)`、三者都是 `xxxOverride ?? board.xxx`），形参只留 `tool, board, board_center` | 第五轮 contract lens |
| 47 | **`checks` 三条无谓词**：`depth_fits` 先 clamp 再断言同一不等式（恒真）、`genus` 无 `expected`、`slot_open` 无容差；`warnings[]` 元素结构未定义、`SCOOP_CLAMPED` 不在任何枚举 | 全部补齐：`depth_fits` 判**请求值**并回传 `{requested, clampedTo, maxEmbed}`、`genus` 带 `expected`、`slot_open` 带 `expectedZ` + ±0.05 容差；`warnings[] = {code, message, detail}` 并单列 warning 码表 | 第五轮 contract lens |
| 48 | **`python_backend/models/` 与既有 `python_backend/models.py` 撞名**：`cad_engine.py:59` 是裸 `from models import`，新建同名包会让旧引擎在 M0 期间直接 ImportError；另冒烟未写 `clearance = 0`（默认 0.4 → 槽长 100.8、±0.1 断言必红），出顶量一处 `±1e−6` 一处 `≥ 0.9` 互斥 | 领域模型目录改 `python_backend/domain/models.py`；冒烟显式 `clearance = 0.0`；出顶量统一为区间 `[0.9, 1.0]` | 第五轮 contract lens |
| 49 | **板尺寸被当成「默认放几把工具」的问题**（Q5）：D15' 只写「工具并集 bbox + margin」，用户 m02193 指出 A4 只是量尺，板多大是独立自由度（可只放一把、可按最小 Gridfinity、可自定义、可铺满打印床、可更大再分块） | `BoardConfig` 加 `sizeMode`（`'fit-tools'` / `'custom'` / `'print-bed'`）+ `widthMm`/`heightMm`；**板框锚点 = 未隐藏工具并集 bbox 中心**；三种模式都要过 `tools_in_board` 板内校验；板大时**允许留白**（不重排、不平移工具）；Q5 关闭 | D15'、D2'、D3'、SDS §3.1 §7.2 §7.6 |
| 50 | **镜头畸变要标定+告警，成本高且用户认为没必要**：D16' 原方案是 `cv2.calibrateCamera` 棋盘格 + EXIF 焦距估「畸变可能引入 X mm」告警 | 用户 m02193 否决——改为 **`margin` 默认 8 → 12**，用留白吃掉 2–4mm 边界畸变；不做标定、不做去畸变、**也不告警**。S0 ±1.5mm 承诺的是槽尺寸不是板尺寸 | D16'、§5、SDS §1.1 §2.1 §4.2 §7.2 §11.1 |
| 51 | **板框锚点在纸面里的位置未定义**：`center` 写「板外接框中心」，但 `custom`/`print-bed` 只给宽高、不给位置；实现只能钉在工具并集中心（= 自动居中，被 §7.2 禁止）或钉在纸角（纸面中部工具必 `TOOL_OUT_OF_BOARD`）。`:135` 的「纸面四角 → (±w/2, ±h/2)」隐含「板 = 纸」 | 板原点 = **未隐藏工具并集 bbox 中心**；「不自动居中」的准确含义改为「不重排、不平移工具」（留白均分不算居中）；值域断言改成随板宽变化的表述 | 第六轮 geo P0-1 / contract P0-2 |
| 52 | **`print-bed` 取整张床 → 必然分块**：`board == printBed` 使 §8.1 的 `220 > 220 − 2*edge` **恒真**，用户点「铺满床」反而得到 4 片 110×110，而 gridfinity 同模式却是 210 | `print-bed` 一律取 `printBed − 2*edge`（`edge=5` → 220 床得 **210×210**），与 §8.1 判据同源 | 第六轮 geo P1-4 / contract P0-3 |
| 53 | **gridfinity 板尺寸三个真源**：`board_size_mm()` 返回 `widthMm`、实体是 `units*42`、分块又按前者判 → 切缝数与位置都会错；且 `ceil(400/42)=10` → 420mm 突破 400 上界 | `board_size_mm()` 为唯一真源：gridfinity 恒返回 `(units_x*42, units_y*42)`；`unitsX/unitsY` 改由后端 `derive_units()` 派生（X/Y 三条公式齐全）、clamp `1..40`；前端只回显并显示「实际 126×126（3 格）」 | 第六轮 geo P1-1/2/3、contract P1-2 |
| 54 | **scoop 的 `run` 上界仍用 `margin`**：`margin` 只在 `'fit-tools'` 下≈真实边距；`custom`/`print-bed` 下工具可贴板边，`tools_in_board` 只查「在板内」不查「距边 ≥ margin」→ 坡道从板侧切穿而 checks 全绿 | `run ≤ d_edge − clearance`（`d_edge` = 槽壁到板轮廓的**实测** `shapely.distance`）；`d_edge < clearance + 1.0` → 阻断 `GEOMETRY_INVALID` | 第六轮 geo P0-2 |
| 55 | **`TOOL_TOO_LONG` 用 `2*margin` 当打印余量**：`margin` 8→12 会把最大可做长度从 204 悄悄压到 196，200mm 扳手突然做不了 | 改用 `2*edge`（`edge=5` → 210），与 §8.1 同源；明确「这条与 `sizeMode` 无关」 | 第六轮 geo P1-6 |
| 56 | **2.5 板尺寸控件记 0 人日**：它有 4 条独立可验收行为 + 一套需与后端对齐的判据，「同文件即零成本」把评审当免费；且 §12.1 的 M2 三路里没有 2.5，会漏派 | 2.5 记 **0.5 人日**，M2 **3.0 → 3.5**，总工期 **14.5 → 15.0**；§12.1 改为 4 路并注明 2.5 与 2.3b 同一人 | 第六轮 contract P1-7 |
| 57 | **`INVALID_SIZE_MODE` 判据若按「字段出现」实现，每个默认请求都 400**：前端非 custom 时会发 `widthMm: null`；且 `ValueError → 400` 的映射未写，会落成 500 `INTERNAL`。另 §12.3 审核闸门「板级参数只有三个」会把本次改动自己打回 | 判据写死 `is not None`；`ValueError` 统一映射 400 `INVALID_SIZE_MODE`；§12.3 改为「与 §3.1 字段清单逐一对应（含 v1.3 三个新字段）」；前端离开 custom 时必须置 `null` | 第六轮 contract P0-1、P1-3、P1-5 |
| 58 | **「留白吃掉畸变」因果不成立**：`margin` 是板边到工具外接框的**材料厚度**，而畸变误差发生在**工具轮廓本身**（150mm 工具上 1–2% 就是 1.5–3mm），`margin` 大也修不了轮廓 | 表述改为「`margin` 吃板边余量与构图余量，**不修正轮廓**」；S0 ±1.5mm **只对「完整落在纸面内、离纸边 ≥ 20mm」的工具承诺**；工具贴板边给 `BOARD_EDGE_TIGHT` warning | 第六轮 geo P0-3 / contract P1-4 |

---

## §0 这一版为什么推翻 v0.2

v0.2 的诊断是对的，处方是错的。三个红队独立得出了同一个结论：

| v0.2 的假设 | 实际情况 |
|---|---|
| 需要自研一套「逐顶点变宽度多层 2.5D loft」几何内核（D4.1/D4.2/D4.3） | tracefinity 用 `shapely.buffer(join_style=2)` + `CrossSection.offset(JoinType.Round)` + `extrude(scale_top=...)` 约 90 行就做完了，且没有层间顶点对应问题 |
| L2 矢量编辑器「已有」，只需加四件（D5） | **全项目不存在任何顶点级编辑代码**（`grep 'editVertex\|selectedVertex\|dragVertex'` 为空），`EditorPanel.tsx:55` 自称矢量编辑器但内容只有画笔/橡皮 |
| 槽的坐标系问题只是「840×1188 硬编码」 | 更致命的是 **z 基准也错了**：槽是从 z=0 拉伸的，导致槽顶落在板顶之下，槽是**密闭空腔**（见 §1 F1） |
| 工期 26–37 人日 | 三个红队独立估 10–14 人日；加上用户后补的「模型分块 / 双板外形 / DXF / 畸变标定」后，v0.3 定为 **16 人日** |

**v0.3 的主线**：把几何内核整体移植（MIT 允许），把省下的 15 人日全部投到两块**真正没有开源替代品**的地方——**拍照端**（纸角确认、照片体检、镜头畸变、亚像素轮廓）和**交互端**（顶点编辑、手孔拖拽、倒角参数、撤销重做）。

**工具定位（已由用户确定）**：本工具**只管生成模型，不管材料与工艺**。输出物有两种形态，来自同一套几何数据：
- **STL**：实心板 + 凹槽，用于 FDM/SLA 打印（PLA/PETG/TPU 都行，用户自理）
- **DXF/SVG 1:1 轮廓图**：凹槽轮廓 + 深度标注，用于 CNC 铣削 / 激光切割 / 刀模切割泡沫

因此**"Foam"不再是"柔性材料打印件"**，而是"实心板 + 凹槽"这一形态的中性叫法。不做中空、不做肋、不做材料相关的夹持策略。

**边界（用户 m00751 / m00755）**：
- **工具必须完整落在 A4 内**；超过 A4 的工具不做（那种尺寸直接挂墙）。
- **本项目不做切片**（切片 = 生成 G-code）。切片由打印机自带软件完成，且每台机器参数不同。本工具只输出几何模型（STL / DXF），不涉及层高、壁数、填充、支撑、打印机预设、材料预设。
- **但要做「模型分块」**（用户 m00776）：板超过打印机最大打印尺寸时，切成多片分别打印、打印完粘起来。这是几何问题，不是切片问题。

---

## §1 四个新确认的硬事实（已复核，带行号）

### F1. 槽是密闭空腔——最致命，且 v0.2 的六道守卫全部抓不到

```python
# python_backend/cad_engine.py:600-601
slot = trimesh.creation.extrude_polygon(poly, height=embed_depth + 1)
slot.apply_translation([0, 0, -embed_depth / 2])
```

- `extrude_polygon` 从 z=0 起拉伸 → 槽体 z ∈ `[-embed/2, +embed/2 + 1]`
- 底板 `_make_rounded_box` 在 `cad_engine.py:96` 做 `apply_translation([0,0,-size_z/2])` → 板体 z ∈ `[-H/2, +H/2]`
- 默认 `height_mm=20`、`embed_depth=15`：槽顶 = +8.5，板顶 = +10 → **槽上方留 1.5mm 实心顶盖，槽完全封闭**
- Gridfinity 更糟：`models.py:104-105` 的 `height_mm = height_u*7 + 5`，3U = 26mm，板顶 +13，槽顶 +8.5 → **盖 4.5mm**

这个 STL 水密、`volume_mm3` 正常、`/generate-cad` 返回 `success: true`。切片预览只看外形也正常。打印出来是一块实心板。

**v0.2 的 M1 六道守卫为什么全绿**：`tool_solid.difference(pocket_solid).volume≈0`（工具实体整个落在空腔内部，差集确实是 0）、单连通（外壁+内腔仍连通）、`min_wall≥1.2`（1.5mm 顶盖被算成合格壁厚）、`embed_depth ≤ H−0.2`（15≤19.8）、逐层面积对照（拿同一套错误几何做基准）、`is_watertight`（密闭空腔更"水密"）。

**修法**：槽切刀改为从板顶向下切，且顶面过切 1mm。

> **▸ 第二轮审核：z 原点全项目只允许一个定义 —— `z = 0` 在板**底**面，板顶面 = `top_z`（SDS §2.3；rect = `thickness`、gridfinity = `heightU*7`，由 `board_top_z(board)` 唯一给出）。**
> 不再用 ±H/2 居中（`cad_engine.py:96` 的居中做法就是 F1 的成因之一，必须删）。因此下文所有 z 公式里的 `H/2` 都已替换为 `top_z`；**旧代码里的 `[-H/2, +H/2]` 只出现在 §1 对现状的描述中**。
>
> **⚠️ bbox API 事实（2026-11-05 实测，manifold3d 3.5.4）**：`Manifold.bounding_box()` 返回**扁平 6 元组** `(minx, miny, minz, maxx, maxy, maxz)`，故 **最大 z = `bb[5]`、最小 z = `bb[2]`**；`bb[1][2]` 会直接 `TypeError`（`bb[1]` 是 float）。`CrossSection.bounds()` 返回扁平 4 元组 `(minx, miny, maxx, maxy)`。本文及 SDS 早期版本写的 `bounding_box()[1][2]` / `bb[1][2]` 一律按上述含义理解（`[1][2]` → `bb[5]`、`[0][2]` → `bb[2]`），**写代码时不得照抄下标**。`trimesh` raycast 参数名是 `ray_origins` / `ray_directions`，且返回的 `loc` **不按距离排序**，首击高度必须取 `max(p[2] for p in loc)`。

`z ∈ [top_z − embed_depth, top_z + 1]`。手指槽同理（`cad_engine.py:359`、`:368` 现在也是从 z=0 起）。

**必须新增的机检断言（M0 DoD，缺一不可）**：
1. `slot_cutter.bounding_box()[5] >= top_z + 0.9`（切刀必须刺出顶面；`bounding_box()` 是扁平 6 元组，`[5]` = maxZ；`top_z` 见 §2.3，gridfinity 上不等于 `thickness`）
2. 取 `base.section(plane_normal=[0, 0, 1], plane_origin=[0, 0, top_z − 0.01])`（trimesh 5.2.0 **没有** `section_plane`，只有 `section`，返回 `Path3D`），断言槽投影区域内**没有面**（等价于：顶面在该区域是空的）
3. 从板顶 `(x_slot, y_slot, top_z + 10)` 竖直向下 raycast，首击 `z ≈ top_z − embed_depth`（**不是** `top_z`）。这一条是密闭空腔的**唯一**可靠反证。

### F2. L2 矢量编辑器不存在，是从零写

- `src/features/editor/EditorPanel.tsx:55` 自称"矢量轮廓编辑器"，实际渲染的是 MaskEditor 的画笔/橡皮
- `src/features/workspace/Viewport.tsx:286` 收到 `primitives` 仅用于画红线（`:324-402`），无交互
- 全项目无 `editVertex` / `selectedVertex` / `movePoint` / `dragVertex`
- `src/features/mask/MaskEditor.tsx` 有 undo（`history` 数组 + `:720-745` `undo()` + `:818-825` Ctrl+Z），但**没有 redo**，且只在蒙版编辑内部生效

### F3. Gridfinity 磁吸孔位置是错的

```python
# python_backend/cad_engine.py:258-269  _gridfinity_hole_positions
cx = (ix + 0.5) * GRIDFINITY_PITCH - units_x * GRIDFINITY_PITCH / 2
```
孔放在**格子中心**。Gridfinity 规范是每个格子的**四角各一个**，且**孔心距 26mm**（`cq-gridfinity/constants.py` 的 `GR_HOLE_DIST = 26/2`，即 42mm 格内相对格心 ±13mm；tracefinity 的 `MAGNET_INSET = 4.8mm` 是从孔边缘量的同一组位置）。按现状打出来的盒子**摞不上任何标准底座**。同理 `_make_gridfinity_base`（`cad_engine.py:217-255`）是"实心块减裙边"，没有三段锥台底座、没有五段堆叠唇。

### F4. 内孔在全链路有 5 处断点

| 断点 | 位置 | 后果 |
|---|---|---|
| `fill_holes` 主动填洞 | `sam_tool_contour.py:46-53` 定义，`:211`、`:215`、`:232`、`:236` 调用 | 扳手环形头中心直接变成实心 |
| `RETR_EXTERNAL` 只取外轮廓 | `sam_tool_contour.py:115`、`:142`、`:191`、`:218`、`:240` | 内环从未被提取 |
| primitives 拍平成单环 | `cad_engine.py:503-521` `_primitives_to_2d_polygon` | 即使提到内环也被丢掉 |
| `Polygon` 拉伸不带 holes | `cad_engine.py:609` | 布尔减时孔被填 |
| 前端不渲染内环 | `MaskEditor.tsx` / `Viewport.tsx` | 用户看不见、改不了 |

tracefinity 的完整解法：`stl_generator_manifold.py:706-750`（`_shapely_to_cross_sections` 带 interior rings）+ `:809-868`（`FillRule.EvenOdd` + `area<=0` 反环重试）。

---

## §2 移植清单（MIT，直接搬，改 import）

路径前缀：`reference/oss/tracefinity/`

### 2.1 后端（必须移植）

| # | 模块 / 函数 | 位置 | 行数 | 要改什么 | 难度 |
|---|---|---|---|---|---|
| 1 | 标定 + 全视野 warp | `backend/app/services/image_processor.py:14`、`:19-110`、`:377-443` | ~110 | 输出改成固定 `PX_PER_MM=10`；`scale_factor` 恒为 0.1；保留"扩到整张源图可见范围"和 `pick_paper_orientation` | 易 |
| 2 | 照片体检 | `backend/app/services/photo_checks.py:36-145` | ~140 | 原样；`PAPER_SIZES` 换成我们的尺寸表 | 易 |
| 3 | 偏置 + 平滑/简化管线 | `backend/app/services/polygon_scaler.py:171-249` | ~95 | 原样。**顺序必须是先 smooth/simplify 后 clearance** | 易 |
| 4 | 槽切刀 + 倒角锥台 | `stl_generator_manifold.py:809-966` | ~160 | ① **删掉函数内的 `-(p[1] + offset_y)` 与 `offset_y` 形参**——入参已是板局部 y-up mm，再取负就是竖直镜像；② z 基准按本项目"板顶向下切"重写 | 中 |
| 5 | 手指孔 5 形态（+ scoop = 6） | `stl_generator_manifold.py:969-1039` | ~70 | ① 同上删 `:984` 的取负；② 坐标从像素转 mm；③ 按 §3.1 D6' 增加 scoop 形态 | 中 |
| 6 | 手指孔倒角 | `stl_generator_manifold.py:1042-1118` | ~75 | 同 #5：删取负，其余原样 | 易 |
| 7 | 内环 CrossSection | `stl_generator_manifold.py:706-786` | ~80 | 原样；`_clip_to_interior` 的矩形改成我们的板内壁 | 易 |
| 8 | 圆底角扫掠切刀 | `stl_generator_manifold.py:553-626` | ~70 | 原样（用于 `filleted_rect` 手孔；**字面量按 SDS `HoleShape`**，不是 `filleted_rectangle`） | 易 |
| 9 | Gridfinity 底座 + 堆叠唇 + 磁吸孔 | `stl_generator_manifold.py:90-162`、`:260-298`、`:629-703` | ~250 | 常量表照抄；`grid_x/grid_y` 参数化 | 中 |
| 10 | 床分割 | `stl_generator_manifold.py:1545-1669` | ~120 | 原样（v1 可推迟） | 易 |
| 11 | 参数模型 | `backend/app/models/schemas.py:63-157` | ~90 | Pydantic → 我们的 dataclass；补 `clearance/chamfer/interior_rings/depth_override` | 易 |
| 12 | 物理尺寸回归测试 | `backend/tests/test_physical_size_pipeline.py`（`SIZE_TOLERANCE_MM = 1.0`） | ~120 | 改造成本项目的 golden test | 易 |

### 2.2 前端（必须移植）

| # | 模块 | 位置 | 说明 | 难度 |
|---|---|---|---|---|
| 1 | 顶点编辑器 | `frontend/src/components/PolygonEditor.tsx:214-263`（边上插点/删点/拖点） | 纯 SVG/React，逻辑可整段搬 | 中 |
| 2 | 编辑器工具条 + 模式集 | `ToolEditorToolbar.tsx:10`（9 种 edit mode）、`:282`（平滑视图切换） | 9 种模式的交互定义 | 中 |
| 3 | 手孔编辑 | `frontend/src/components/ToolEditor.tsx:470-503`（6 种孔型）、`:542-600`（拖/缩放/旋转）、`:316`（镜像） | 直接对应 PRD F3.5 | 中 |
| 4 | undo/redo | `frontend/src/hooks/useHistory.ts:1-60` | 60 行，Ctrl+Z / Ctrl+Shift+Z | 易 |
| 5 | 对称 | `frontend/src/lib/symmetry.ts:34-56`（`partnerIndex(i) = (n-i)%n`） | 对应 PRD F3.11 | 易 |
| 6 | 纸角手拖 | `frontend/src/components/PaperCornerEditor.tsx:115-200` | 对应 R2 的兜底 | 易 |
| 7 | 排版（仅重叠检测） | `frontend/src/lib/drawerLayout.ts:197-283` 里的 `unfittedIds` 回传与冲突高亮 | **只抄 UX 模式**；`fitAll` 之类的自动摆放**不移植**（D3' 已砍） | 易 |

### 2.3 移植时必须先统一的六个约定（不统一会静默出错）

> 前三条是 v0.3 原有的，其中**第 1 条写反了**——四路审核一致指出。后三条是本轮补的静默失败面。

1. **y 轴方向（v0.3 写反，已纠正）**：tracefinity 的输入是 SVG，天然 y-down；它在 `stl_generator_manifold.py:896`、`:984` 写 `-(p[1] + offset_y)`，**这正是 y-down → y-up 的那一次翻转**，不是"多余取负"。本项目**存储层保留纸面 y-down 毫米坐标**（原点 A4 左上、+y 向下），在唯一的 `to_board_frame()` 里翻转成板局部 y-up（原点板中心，z=0 板底）。**翻转只允许出现在这一处**；任何其它地方再取一次负就是竖直镜像——偏口扳手的槽口会朝反方向，旋转 180° 也补不回来，而且几何全绿。
2. **z 原点（与 tracefinity 相同，不必换算）**：两者都是 `z = 0` 在板**底**面、向上为正。**本项目不使用 ±H/2 居中**（`cad_engine.py:96` 的居中必须删除，它是 F1 的成因之一）。板顶面 `z = top_z`（rect = `thickness`，gridfinity = `heightU*7`）；`wall_top_z` 在这里就等于 `top_z`。倒角锥台的基面固定在 `z = top_z − eff_chamfer`、向上外扩，**不能**沿用 tracefinity 里多一层 `+ wall_top_z` 的写法——锥面一旦落到 `z = thickness + 1` 的空气里，槽口仍是直角，而"剖面能看到锥面"的 DoD 照样通过（F1 重演的路径）。
3. **数据结构**：tracefinity 用 Pydantic `GenerateRequest`；本项目是 `python_backend/models.py` 的 dataclass，缺 `clearance`、`holes`（内环）、`depth_override`，必须先补齐再移植。
4. **绕向**：外环 CCW、每个内环 CW，**导入即归一化**并断言 signed area 符号。`skimage.measure.find_contours` 返回 (row, col)，转 (x, y) 时 y 取反会把内环一起翻转——不报错，只是孔被 union 吃掉（实测体积差 25%）。
5. **mask 极性**：约定 `alpha > 0.5 = 工具`。断言 mask 面积占画布 5%–60%，否则说明极性反了或照片全黑。
6. **像素中心与板原点**：10px/mm 下坐标取像素中心，统一 `+0.5 px` 再换算 mm。**板原点 = 板几何中心**（x/y），z 原点在板底面——不是"左下角"（第二轮审核指出：`x = p.x − origin.x` 与 `y = (origin.y + board_h) − p.y` 这组式子的值域是 `[0,w] × [−h,0]`，既不居中也不是 y-up，必须改）。现在是 `poly_mm -= center`（`cad_engine.py:585`）把工具挪到板心，但**从未定义"板心"是哪个点**；必须断言"槽 bbox 到板边距 = 面板上填的边距"，否则整体偏 8mm 肉眼看不出来但装不进。手孔切刀同样从 z=0 起（`:368`），并入 0.2 的同一条开口断言。

---

### 2.4 除 tracefinity 外，另外这 10 处该抄的（2026-11-03 四路开源调研结论）

> 许可证逐个核对（GitHub API / LICENSE 原文 / PyPI 元数据）。**只列能进 MIT 项目的。**

| 需求 | 抄哪个（star / 许可） | 抄什么（具体到文件/函数） |
|---|---|---|
| **Gridfinity 数值** | `michaelgale/cq-gridfinity` 205★ **MIT** | `cqgridfinity/constants.py` **整份拷进来当唯一真源**：`GRU=42`、`GRU_CUT=42.2`、`GRHU=7`、`GR_BASE_HEIGHT=4.75`、`GR_STR_H=1.8`、底座剖面 `((TOP_CHAMF*√2,45°),1.8,(CHAMF_H*√2,45°))`、**唇剖面五段高度 = `2.6 / 1.2 / 0.7 / 1.8 / 1.9`，累计 8.2**（真源是 tracefinity `stl_generator_manifold.py:33-37` 的 `LIP_D0=1.9, LIP_D1=1.8, LIP_D2=0.7, LIP_D3=1.2, LIP_D4=LIP_D0+LIP_D2=2.6`，顺序为 `LIP_D4, LIP_D3, LIP_D2, LIP_D1, LIP_D0`）；**不要用 cq-gridfinity 文档里的 `(1.6√2, 45°)` 那套**——那是"斜边写法"，按 45° 折算出来的段高是 `2.263/1.2/0.990/1.8/1.839`（累计 8.09），与 8.2 差 0.11mm，混用会让唇高断言永久红、`GR_HOLE_D=6.5`、`GR_HOLE_H=2.4`、`GR_HOLE_DIST=13`、`GR_RAD=4`、`GR_FILLET=1.1`。**推导式也要抄**（`GR_BASE_TOP_CHAMF = 4.75 − CHAMF_H − 1.8`）——只抄结果数字，改一个尺寸就崩。 |
| 底座/唇的几何语义 | `kennetek/gridfinity-rebuilt-openscad` 2295★ **MIT**（LICENSE 正文确认；GitHub 显示 NOASSERTION 是文件头不规范） | `docs/constants.md` 参数语义表；`src/core/standard.scad`、`base.scad`、`wall.scad`、`tab.scad`；`tests/*.json` 当尺寸回归基线 |
| **纸角排序** | `imutils/perspective.py` 4580★ **MIT** | **只抄骨架，两处必须改**：① `dst` 直接写物理尺寸 `[[0,0],[210*10-1,0],[210*10-1,297*10-1],[0,297*10-1]]`，让 warp 输出天然是 0.1mm/px；② `order_points` 在旋转 >45° 时错序（它按 x 排序分左右），改用 `s=pts.sum(1); d=np.diff(pts,axis=1)` 取 min/max 四角。横竖不猜——用 210×297 与 297×210 两个 dst 都试，取 `findHomography` 的 `reprojErr` 小者。 |
| **亚像素轮廓** | `scikit-image` 6630★ **BSD-3** | `measure.find_contours(alpha, 0.5)`（marching squares，亚像素）；`restoration.rolling_ball()` 消纸面光照不均/阴影。**这两个函数顶掉 `sam_tool_contour.py` 里大半形态学**。 |
| 兜底分割模型 | `danielgatis/rembg` 25291★ **MIT** + `isnet-general-use.onnx`（170MB，上游 DIS **Apache-2.0**） | `remove(..., only_mask=True)` 拿 mask；`post_process()` 里**只抄 `opening(disk(1))`，别抄 `gaussian_filter(sigma=2)`**——那一步会把扳手的 90° 角削成 R2，直接吃掉 1mm 余量。ONNX 已现成挂在 rembg 的 `v0.0.0` release，不用自己 `torch.onnx.export`。 |
| **场外编辑器交互** | `pascalorg/editor` 25286★ **MIT** | `packages/editor/src/components/tools/shared/polygon-editor.tsx` **整文件**。7 条精华：① 拖拽状态存 `initialPolygon` **快照**，每次 move 从快照重算（不 `+= delta`，防丢帧漂移、Esc 可回滚）；② `onPolygonPreview`（每帧）与 `onPolygonChange`（仅 pointerup）分离 → **一次手势 = 一条 undo**；③ render 阶段比对 `polygon !== lastPolygonRef.current` 丢弃过期预览；④ 中点插点要「插入即进入拖拽」；⑤ 边拖拽沿外法线投影，法线用质心翻转 `if (nx*(mx-cx)+nz*(mz-cz) < 0) 翻转`（对混合绕向免疫）；⑥ 装饰性 mesh 一律 `raycast={NO_RAYCAST}`，否则边条抢走顶点点击；⑦ 吸附做成注入回调 `resolvePlanPoint`，不写死。 |
| **撤销/重做** | `charkour/zundo` 899★ **MIT** | zustand 中间件，peer `zustand ^4.3 \|\| ^5`，直接 `npm i`，不用自己写 history 栈。 |
| 前端矢量预览 | `jankovicsandras/imagetracerjs` 1548★ **Unlicense**（=公有领域） | `imagedataToSVG()` + `pathomit`（去灰尘碎轮廓）+ `rightangleenhance`（保直角）。单文件无依赖。**只做即时预览，定稿仍走后端。** |
| DXF 导出 | `mozman/ezdxf` 1516★ **MIT**（已实测） | `msp.add_lwpolyline(pts, close=True, dxfattribs={'layer':'CUT'})`；`doc.header['$INSUNITS']=6`（=mm）。注意 **SVG 后端要 Pillow**，只为网页预览不如自拼 SVG 字符串。 |
| 1:1 纸样校对 | `justinhardin/gridfinity-pic-to-bin` 2★ **MIT** | `trace_export.py` 的「打印一张 1:1 纸样比划一下」思路，约 20 行。 |

**明确不能碰（许可证）**：`Le0Michine/FusionGridfinityGenerator`（CC BY-NC-SA，非商用+传染）、`breandan81/shadow-board`（GPL-3.0）、`skotagiri/tooltrace`（**无许可证 = 默认保留所有权利**）、potrace 全家（GPL-2.0，含 `node-potrace` / `esm-potrace-wasm`）、pymeshlab / pymeshfix（GPL-3.0）、PrusaSlicer / OrcaSlicer（AGPL-3.0）。

**搜索到的反证**：GitHub 上「照片 → 收纳嵌件」做得成的项目不到 10 个，其中 6 个是 0–4★ 或玩具级。**想到的人不少、做成的不多**——抄 tracefinity + 上面这 10 处，已覆盖公开经验的 90%。

## §3 修订后的决策（D1'–D21'；D18'–D21' 与加粗条目的修订见 §3.1）

| 编号 | 决策 | 相对 v0.2 的变化 |
|---|---|---|
| **D1'** | 透视校正后输出**固定 10px/mm** 的图。A4 竖向 → 纸面 2100×2970 px，四周各留 150px（15mm）安全边，画布 2400×3270 px，纸原点在 (150,150)。`mm_per_px` 恒为 0.1，**不向下游传递 `px_per_mm`**。源图长边 < 1800px 时拒绝并提示重拍。**不做**"工具超出纸张"的全视野扩展画布。 | 推翻 v0.2 的"自适应 ppmm 穿透 5 层"；简化 tracefinity 的全视野 warp |
| **D2'** | **一张照片拍 1..N 把工具，全部必须完整落在 A4 内**（用户 m00751：超过 A4 的工具没有收纳意义，直接挂墙）。一次提取多个轮廓，再按 D15' 的 `sizeMode` 决定板尺寸（板可以只放其中一部分工具，其余移到下一块板）。**校验**：任一轮廓的外接框触到纸边界（距边界 < 3mm）→ 直接报错"工具超出 A4，请更换工具或分次拍摄"，**不静默截断**。 | 推翻 v0.2 的"一照一工具、超 A4 手动建槽"；也推翻此前"支持纸外工具"的想法 |
| **D3'** | 排版只做：重叠检测（高亮冲突）+ 手动拖拽 + 旋转 90° + 未放下提示。**不做** first-fit 自动摆放（v1.0 起砍，见 §5）、不做一个**自动排版算法**、不做 STRtree/NFP/0.05mm 强制重叠。**排版与板尺寸正交**：工具在纸面坐标里摆好后，板框按 D15' 的 `sizeMode` 单独决定，放宽 `margin` 或改 `custom` 尺寸就能多留白，不需要挪工具。 | 砍掉 v0.2 的 D3 四件套；first-fit 亦砍（第二轮审核：§5 已列为砍掉，§3 又保留，自相矛盾） |
| **D4'** | 几何内核 = manifold3d。倒角 = `CrossSection.offset(JoinType.Round)` + 单层 `extrude(scale_top)` 锥台，与直筒切刀并集。**不做** miter 逐顶点偏置、medial axis、8~16 层曲线表、二分求 max d。**五个实测坑（照抄必踩）**：① `extrude(scale_top=)` 绕**原点**缩放、不是质心 → 拔模前必须 `cs.translate(-cx,-cy)`；② 孔的绕向必须与外轮廓相反（外 CCW / 孔 CW），否则孔被 union 吃掉（实测体积 4000 而非 3000）；③ `offset` 的 JoinType **只作用于凸角**，凹角永远 miter；④ 连续多次 offset 之间插 `cs.simplify(1e-3)`；⑤ 床分割用 `Manifold ∩ Box`，**不要用** `trimesh.slice_plane(cap=True)`（封口缺面，issue #2299）。 | 砍掉 v0.2 的 D4.1/D4.2/D4.3；补实测坑 |
| **D5'** | 轮廓编辑：顶点拖 / 边上插点 / 删点（下限 3，拒绝）/ 整体旋转 / 框选缩放 / 撤销重做。**圆弧基元 v1 只读**：一旦进入顶点编辑，arc 降级为折线并在 UI 明确提示。 | v0.2 未定义 arc 策略 |
| **D6'** | 手槽改用**手孔**（`scoop` / `sphere` / `cylinder` / `square` / `rect` / `filleted_rect`——**字面量以 SDS §3 的 `HoleShape` 为准**，v1.0 草案写的 `rectangle`/`filleted_rectangle` 会让后端直接判非法值），每孔独立 `depthOverride`、`rotation`、口部倒角。放弃 v0.2 的「scoop 与凹槽同深度外凸」模型（scoop 仍保留，但改为**与槽连通的独立斜坡形态**，判据见 §3.1 D6'（修订 2）；**本节已被其取代**，勿按本节实现）。 | 推翻 D6 |
| **D7'** | 数据结构 `Project → Board → Tool → FingerHole`（+ `interior_rings`）。M0 只做 localStorage 全量草稿 + `schemaVersion`，完整持久化等几何定型。 | v0.2 要求提前定完整 schema |
| **D8'** | 厚度三档（6 / 12 / 25mm 全高）+ **分外形 clamp**：rect `embedDepth ≤ thickness − 2`；gridfinity `embedDepth ≤ heightU*7 − GR_BASE_HEIGHT − 2`（**本句为 v1.3 修订，原写 `≤ height_mm − 2` 会让 3U 板按 26−2=24 clamp、切穿 4.75 高的锥台底座**）。板体**永远实心**（不中空、不加肋、不做薄壳）——v0.2 的 D10 薄壳与深槽算术互斥：2.4mm 顶板 + 任何 >2.4mm 的槽 = 打穿。材料无关：PLA / PETG / TPU / 泡沫 / 木板，同一份几何。 | 推翻 D10 的薄壳/肋/工时估算 |
| **D9'** | 间隙：滑杆（0.2–1.0mm，默认 0.4）+ **40×40×10 试切件**（打 0.2/0.4/0.6 三档）。浏览器本地记住上一次的值。**不做**材料数据库、不做按打印机预设、不做切片参数。 | 保留，删掉"公差非对称 +1.5/−0.3" |
| **D10'** | 只做**几何**校验：`is_watertight`、凹槽之间/凹槽与板边的**最小筋厚 ≥ 2.0mm**、**深度 clamp 分外形**（rect `embed ≤ thickness − 2`；gridfinity `embed ≤ heightU*7 − GR_BASE_HEIGHT − 2`，与 D8' 一致——原写 `embed_depth ≤ height − 2` 是分外形之前的口径）。**不做**层高/壁数/填充/支撑/床温/G-code——那是切片软件的事，本项目完全不管。不做用料与工时估算。 | 砍 |
| **D14'** | **新增：模型分块**（用户 m00776 明确要）。参数「最大打印尺寸」X/Y/Z（默认 220×220×220，用户可改）。板任意一边超出 → 自动裁成 nx×ny 片，每片独立 STL。**切缝只允许落在凹槽之间的实心筋上，绝不穿槽**（穿槽会把凹槽切成侧面开口，工具会滑出来）；该方向找不到任何 ≥2mm 的筋 → 拒绝并提示「请换更大打印机或缩小板」，不静默生成残缺件。片间用**圆柱定位销**而不是燕尾——销的容差好控制，燕尾要精确打印才能插。~~φ4×8 盲孔~~ → **已被 §3.1 的 D14' 修订取代：销必须水平、从切缝面钻入**。~~Gridfinity 板的分块线吸附到 42mm 网格~~ → **已被取代：v1 禁用 Gridfinity 分块**。Z 超限只告警不切。 | 新增（v0.2 曾推迟） |
| **D15'** | **新增：板的两种外形，都做。** ① **自定义矩形**：`cornerR` + `baseEdgeRoundover` + 板厚；② **Gridfinity**：标准底座/堆叠唇/磁吸孔。切换外形时工具轮廓与手孔位置**原样保留**，只换外框与底座。<br>**板尺寸是独立自由度，不由工具数量推导**（用户 m02193：「理论上是想放几个放几个，A4 纸只是用来作为参考来识别工具大小的」）。`BoardConfig.sizeMode` 三选一：<br>• `'fit-tools'`（默认）——板 = 全部工具并集 bbox 各边 + `margin`；<br>• `'custom'`——用户直接填 `widthMm` / `heightMm`，可以是 60×40（只放一把螺丝刀）也可以是 400×300（放一整套，之后分块）；<br>• `'print-bed'`——板 = `printBed.x × printBed.y` 整张床。<br>三种模式下工具都必须完整落在板内（§7.6 第 9 条 `tools_in_board` 阻断校验）；板大于工具并集时**允许留白**，不做任何自动居中或自动排布。板超出打印床 → 走 D14' 分块（`sizeMode='custom'` 时是主路径而不是异常）。 | 新增（用户 m00776 两个外形；用户 m02193 修正板尺寸语义） |
| **D11'** | 精度只承诺 **S0（±1.5mm）**。拍照指引 + 照片体检（EXIF 反算相机高度、纸出框、极端透视三条告警）。**不做** 3×3×2 的 18 件 DoD 矩阵。 | 砍 S1/S2 |
| **D12'** | **新增：两级自检**。L0（2D，最便宜）：`shapely.is_valid` + `explain_validity` + `buffer(0)`——90% 的坏几何死在这一层。L1（3D）：`trimesh.is_watertight` + `is_winding_consistent` + `manifold.status()` + `genus()` + 体积与解析值 ±2% + bbox 对格位。**`is_watertight` 单独用等于没查**——实测两个重叠立方体拼起来仍然 watertight、`status()` 仍返回 `NoError`。壁厚用 `Manifold.min_gap(other, search_length)` 直接量（实测可用）。再加 F1 开口断言：切刀 `bounding_box()[5] >= top_z + 0.9`（`[5]` = maxZ），且 `min_gap` 之外的"首击射线"断言（见 §1 修法第 3 条）。 | 升级，替代 v0.2 六道守卫 |
| **D17'** | **新增：单把工具超过打印床时的策略**。硬约束：**单个凹槽必须完整落在一片内**，否则切缝会把槽劈成两个侧面开口，粘接后也无法使用。即 `工具最长边 ≤ min(打印尺寸X, 打印尺寸Y) − 2×边距`。v1 选 **A 方案：检测到超长 → 明确报错「该工具 280mm，超过你的打印尺寸 200mm，单槽无法分块」**，给出三个出路提示（缩小板/换大床/把该工具移出本板）。B 方案（穿槽 + 侧壁补条）与 C 方案（槽+两侧挡墙三段）留到 v2。 | 新增 |
| **D16'** | **镜头畸变：不标定，用留白吃掉**（用户 m02193：「没有那么重要，你边缘放大一些，比如预留多几毫米，就能吃掉这个误差了，没必要严丝合缝」）。手机广角在画面边缘 1–2% 桶形畸变，在 210mm 纸宽上约 **2–4mm**。v1 **不做** `cv2.calibrateCamera` 棋盘格标定、不做 ArUco 标记纸、不做去畸变、**也不告警**——而是把 `margin` 默认从 8mm 提到 **12mm**：**`margin` 不是精度手段**，它只保证板边与槽壁之间有 12mm 实体；畸变对**画幅边缘区域**的工具轮廓仍会带来 1–2% 的局部尺寸误差（150mm 工具上就是 1.5–3mm）。因此 S0 ±1.5mm **只对「完整落在纸面内且离纸边 ≥ 20mm」的工具承诺**；「留白吃掉畸变」的真实含义是**给构图留余量**，不是修正轮廓（槽是拿工具轮廓算的，与纸边无关；畸变主要影响**边缘附近**的轮廓采样）。需要的用户随时可以把 `margin` 调到 20mm。**这是精度策略的一部分：S0 ±1.5mm 承诺的是槽尺寸，不是板尺寸。** | 推翻本轮 v1.0 的标定方案（用户否决）；`margin` 默认 8 → 12 |
| **D13'** | **新增：双输出**。同一份 `Board + Tool[] + pockets` 数据出两种文件：① STL（实心板 + 凹槽）；② DXF/SVG 1:1 平面图（凹槽轮廓 + 每槽深度标注 + 板外框）。DXF 用 `ezdxf` 写，增量约 80 行。**这是"不绑材料"的关键**——CNC/激光直接可用。 | 新增（用户 m00723：CNC 切割也行） |


### 3.1 v1.0 对 D1'/D6'/D8'/D14'/D15' 的修订，以及新增 D18'–D21'

> 每条都来自四路审核的具体反驳，不是润色。

| 编号 | 修订后的内容 | 为什么改 |
|---|---|---|
| **D1'（修订）** | 画布口径统一为 **2400×3270**（A4 竖，纸面占 `[150,2250]×[150,3120]`），横版 3270×2400。v0.3 的 §3 写 2400×3270、而 M0.4 的 DoD 写 2100×2970，二者矛盾；以 2400×3270 为准。**不向下游传 `px_per_mm`**，`mm_per_px` 恒 0.1。 | 审核 B①：口径不一致，下游是否 +150 偏移无法判断 |
| **D6'（修订 2）** | 手孔形态由**单一连续判据**决定，不再按板厚分档：**`depth ≥ FINGER_REACH_MM`（常量 20.0）→ 竖直孔（`cylinder`/`sphere`/`square`/`rect`/`filleted_rect`）；否则 → `scoop` 斜坡**。其中 `depth = depthOverride ?? embedDepth` 是**生效槽深**（**与几何共用同一个局部量**，否则 `depthOverride=5` 时判据说「竖直孔」、几何只挖 5mm）。理由：手指必须够到工具**底面**（在板顶下方 `depth` 处）才能捏住工具侧壁向上提，起作用的量是「板顶到槽底的距离」即 `depth`，**不是板厚**。该判据对两种外形都成立且无空档：矩形 6/12 板 `embedDepth ≤ 4/10` 必为 scoop，25 板由用户选的 `embedDepth` 决定；Gridfinity 3U 的 `depth` 上限 14.25 < 20 → 只能 scoop；4U 的 21.25 ≥ 20、6U 的 35.25 同理 → **可以**选竖直孔（用户实际选的值决定形态，不是「必须 6U」）（**不是 28.25，那是 5U；42 − 4.75 − 2 = 35.25**）。板厚枚举 6/12/25（默认 12）保留，但**只作 UI 快捷档，不参与形态判定**。scoop 坡底 = **槽底** = `z = top_z − depth`（不是 `thickness − depth`，后者在 12mm 板上会把整片切穿；也不是裸的 `thickness`，gridfinity 上会整体错位 9mm）。**scoop 的几何（落差 = `depth`、水平进深 `run = depth / tan(angle) ≤ margin − clearance`、坡宽 `scoopWidth`、向槽内侵入 ≥0.5mm 否则连通性断言恒 0）首次在 SDS §7.4 给出；没有这段几何就不能开放 scoop UI。**同时 `_auto_detect_finger_slots`（`cad_engine.py:407`）的 PCA 两端胶囊逻辑换孔型后会静默失效，M1.5 必须重写。 | 第三轮审核 P0-1/P0-3：分档有空档、量纲错（「等效板厚」实为腔深）、scoop 坡底写错会切穿板底 |
| **D8'（修订）** | 三档厚度（6/12/25）只约束**自定义矩形**。Gridfinity 的高度由规范决定：`height_mm = height_u * GRHU`（**不是现在的 `7u+5`**，3U 必须 = 21mm）。深度 clamp 分外形：矩形 `embed ≤ H−2`；Gridfinity `embed ≤ height_mm − GR_BASE_HEIGHT(4.75) − 2`，且**槽不得进入堆叠唇区域**。 | 审核 B⑥/D4：现有公式 3U=26 比标准高 5mm，摞不上；且按 H−2 会切穿锥台底座 |
| **D14'（修订）** | 分块保留，但：① **v1 直接禁用 Gridfinity 分块**（锥台底座/唇/磁孔按整板成型，切开后中间片的底座与唇全断，粘起来摞不上）；② 切缝所在筋厚阈值从 2mm 提到 **≥4mm**（2mm 筋切完每侧只剩 1mm，粘接面太薄）；③ 定位销**水平**从切缝面钻入，`销长 = 2×孔深 − 1mm`，可落缝筋厚 ≥5mm（φ4）或改 φ3×6——φ4×8 的**竖直**盲孔在 6mm 板上物理上不可能，在 2mm 筋上会破进槽。 | 审核 D5/R5：D14' 与 D15'/D8' 互斥 |
| **D15'（修订）** | 板外形仍是两种，但"倒角"拆成**三个独立参数**，字段名一律 camelCase（与 SDS §3.1 对齐，旧名 `slot_chamfer`/`base_edge_roundover`/`corner_r` 全部作废）：**`slotChamfer`**（槽口插入导向，默认 1.5，D4' 已有）、**`baseEdgeRoundover`**（板顶沿外框一周的圆角，默认 0 = 关，此前无定义）、**`cornerR`**（板在 XY 平面的四角半径，默认 5，M1.6 已有）。三者独立 UI、独立几何。**板厚 `thickness` 只有 6 / 12 / 25 三档（默认 12）**，仅作 UI 快捷档；**手孔形态由生效 `depth` 决定，与板厚无关**（`depth = depthOverride ?? embedDepth`，见 D6' 修订 2）。 | 审核 D2：v0.3 的"倒角"混指三件事，`base_chamfer` 在 §3 无任何定义，UI 无法落地 |
| **D18'（新增）** | **几何真源唯一 = 稠密点环**（纸面 mm、y-down、外环 CCW / 内环 CW）。`primitives`（line/arc）只是**渲染视图**，`/simplify-contours` 从"数据源"降级为"显示优化建议"。任何写回真源的操作都必须回到点环。 | 审核 B③：折线 / line-arc / find_contours 三份并存，SDS 无法决定存哪一份 |
| **D19'（新增）** | **API 契约以 SDS §3/§4 为唯一真源**（第二轮审核：计划与 SDS 各写了一套字段名，必须只留一套）。要点：**JSON 一律 camelCase**；请求 = 完整 `Project`（`{schemaVersion, paperW, paperH, tools[], board}`；`paperW`/`paperH` 而非 `paper: {w,h}`，见 SDS §3），`Tool` 字段为 `outer: Vec2[]` / `interior: Vec2[][]` / `fingerHoles: FingerHole[]` / `depthOverride` / `chamferOverride`；响应 = `data.pieces[{index, name, stlBase64, bboxMm, volumeMm3}]` + `data.summary` + `data.checks[]`，拒绝走统一信封 `error.code`（不是顶层 `errors[]`）；`error.code` 枚举见 SDS §4.0。**`from_dict` 遇未知字段必须 400 `SCHEMA_UNKNOWN_FIELD`，不许静默忽略**。 | 审核 A②/B④ + 第二轮审核：两套字段名 + "未知字段忽略"会让参数静默消失 |
| **D20'（新增）** | **undo 作用域**：zundo 的 `partialize` 只含 `board/tools/cadParams`；`step`、`cadResult`、`uiState` 不进栈；`MaskEditor` 保留自己的私有 history（`MaskEditor.tsx:720-745`）；一次手势 = 一条记录（preview/commit 分离）。 | 审核 B⑤：`src/app/store.ts:114-136` 里 `step` 与几何同处一 store，不加限定 Ctrl+Z 会连步骤一起回滚 |
| **D21'（新增）** | **`schemaVersion` 迁移策略**：版本不等则按迁移表逐级升；缺迁移表则丢弃草稿并提示"旧草稿不兼容，已清空"，**不做静默兼容**。 | 审核 B⑦：M1–M3 会陆续加 `chamfer/shape/depth_override/pieces`，字段一改草稿就报错 |

---

## §4 里程碑与 DoD

> **§4 是阻塞图，不是串行甘特图。** 关键阻塞边：`0.4 → 0.3`（没有 10px/mm 就没有 mm 坐标，v0.3 把顺序排反了）、`0.3 → 0.6`（golden 的 0.5mm 精度正是 0.3 的验收）、`0.2 → 全部 3D 任务`、`1.0（后端多轮廓）→ 1.6 / 2.4`、`1.0b（三参数进 schema）→ 2.3a`（2.3a 只剩端到端联调，字段已在 1.0b 建好）、`0.7 → 0.6`（校验库就是 golden test 的断言库）。
> **可并行**：只有 `3.1`（纸角手拖）与 `3.4`（DXF）只依赖数据模型（D7'），M1 一开工即可并行；`3.2`（分块）需要 `Manifold` 实体、`3.3`（试切件）需要真实 STL，**必须等 M1 的切刀能出实体之后**。
> **DoD 一律可离线复现**：不出现"打印出来用卡尺量""在 CAD 里量 DXF""实物扣底座"。实物验证集中到 M5「用户验收清单」（不占工期）。

### M-1 — 环境冒烟（0.5 天，排在一切之前）

> **✅ 环境已就绪（2026-11-03 实测通过，原先记录的"建不了 venv"已作废）**
> 早先观测到 `python3 -m venv` 失败，是因为 `python3.14-venv` / `python3-pip` **没装**，不是系统残缺。装上后 WSL 侧完全可用：
>
> ```
> $ echo <sudo-pw> | sudo -S apt-get install -y python3.14-venv python3-pip
> Setting up python3.14-venv (3.14.4-1ubuntu0.2) ...
> Setting up python3-pip (25.1.1+dfsg-1ubuntu2) ...
> $ python3 -m venv /tmp/tv2 && /tmp/tv2/bin/python -V
> Python 3.14.4
> $ /tmp/tv2/bin/pip install numpy
> $ /tmp/tv2/bin/python -c "import numpy; print(numpy.__version__)"
> 2.5.4
> ```
>
> **结论：走 WSL venv，不用换到 Windows conda。** 落地步骤：
> 1. `python3 -m venv .venv`（**不要**用 `sudo` 建，否则 venv 归 root，后面 pip 装包要 sudo）；
> 2. `. .venv/bin/activate && pip install -r python_backend/requirements.txt`；
> 3. `python -c "import numpy,shapely,manifold3d,trimesh,cv2,skimage,ezdxf"` 全绿后再开 -1.1。
>
> **两个已踩过的坑，实施时别重犯**：
> - `curl https://pypi.org/simple/` **会超时**（ICMP/HTTP 探测受限、IPv6 优先），但 **`pip` 本身能正常下载**——不要拿 curl 通不通当出网判据，直接用 `pip install` 试。
> - 从 Windows 侧 `wsl -d Ubuntu <cmd>` 调用时，若当前目录是 `/mnt/d/...` 会报 `CreateProcessCommon: chdir(...) failed 5`（无害，命令仍执行）；先 `cd ~` 再跑可消除该噪音。


| # | 任务 | DoD |
|---|---|---|
| -1.1 | `scripts/smoke_geometry.py`：**环境就绪后**（见上框，WSL venv 已验证可用）用合成 100×20mm 矩形跑一次 `generate_insert` | (a) `slot_cutter.bounding_box()[5] > top_z + 0.9`（`[5]` = maxZ）；(b) **从 `(0, 0, top_z + 10)` 竖直向下 raycast（`ray_origins`/`ray_directions`，首击取 `max(p[2] for p in loc)`），首击 z ≈ `top_z − embed`，而不是 `top_z`**（射线原点必须落在槽**内部**，不能落在槽角顶点上，否则边界命中不稳定）；(c) 槽长 100 ± 0.1mm（与 SDS §10.3 同一量只允许一个容差；±1 会放过 0.9mm 的 scale 残留，正是 F1 类静默错） |

> 这一条同时证明三件事：环境能跑、F1 的开口为真、DoD 可离线复现。**没有它，后面每条 DoD 都可能被"静默失败"骗过。**

> **⚠️ 两条探针实测事实（2026-11-05 在 WSL 上跑通，写代码时照此实现）**
>
> **1) raycast 探针必须打「盲槽」，不能打「贯穿槽」。** 实测（板 `160×80×12`、槽 `100×20`）：
> - 盲槽切刀 `z ∈ [6, 13]` → `intersects_location` 返回 **2 个命中 `[0.0, 6.0]`**，`max(z) = 6.0 = top_z − embed` ✅
> - 贯穿切刀 `z ∈ [-4, 12]` → 返回 **`[]` 空**（射线从孔里穿过去，一个面都打不到），而且此时 `bb[5] − top_z = 0.0`，连 (a) 都不满足
> - 所以：**射线打空 = 槽被打穿了或板没实体**，不是"库有问题"；排查顺序是「先看 `bb[5] − top_z` 是否 > 0.9，再看槽是否被切成通孔」
> - 返回的 `loc` **不按距离排序**（实测是 `[0.0, 6.0]`，板底在前），**必须取 `max(p[2] for p in loc)`**，不能取 `loc[0]`
>
> **2) 「顶面在该区域是空的」用截面环数判，不用射线。** 在 `z = top_z − 0.01` 处 `mesh.section(plane_normal=[0,0,1], plane_origin=[0,0,z])`，`to_2D()` 后数**中心落在槽投影多边形内部**的闭环数：
> - 盲槽 → **1 个内环**（槽口轮廓）✅
> - 不切 → **0 个内环**（只有外轮廓）✅
> - 注意 `p2d.bounds` 始终是板的外接框（`[-80,-40]..[80,40]`），**不能用 bounds 判断开口**，必须逐环 `Polygon(pts).centroid` 判定
> - `trimesh` 5.2.0 **没有** `section_plane` 方法（`hasattr(mesh,'section_plane') == False`），只有 `section(plane_normal=, plane_origin=)`

### M0 — 让后端能跑 + 打通毫米链（2.5 天）

| # | 任务 | DoD |
|---|---|---|
| 0.1 | **重写 `python_backend/requirements.txt` 的 pin**（不是"补四个包"）：`numpy>=2.1`、`shapely>=2.2`、`manifold3d>=3.5.4`、`trimesh>=4.4`、`opencv-python-headless>=4.11`、`scikit-image>=0.25`、`ezdxf>=1.3`、fastapi、uvicorn、pillow、python-multipart、`pytest>=8.3`。**删除** `cadquery==2.8.0`（只被 `cad_engine.py:803` 懒加载，服务已砍的 STEP）与 `scipy`（无调用点）；同一任务删 `/generate-step` 端点 | `uvicorn main:app` 能起（**必须先 `cd python_backend`**，`cad_engine.py:59` 是裸 `from models import`）；`pytest` 能收集到用例；`import cv2` 不报 `libGL.so.1`。**不验证 success/volume**——那正是密闭空腔的特征 |
| 0.2 | **修 z 基准**：新增 `geometry/constants.py` 的 `board_top_z(board)`（rect = `thickness`，gridfinity = `heightU*7`），槽切刀改为 `z ∈ [top_z − embed, top_z + 1]`；手孔切刀用同一条断言覆盖 | summary 输出 `slotBounds` / `baseBounds`（camelCase，与 SDS §4.5 一致；计划旧稿写的 `slot_bounds` 是 snake_case 笔误）；pytest 断言 `slotBounds[5] >= top_z + 0.9`（扁平 6 元组，`[5]`=maxZ），且 `base.section(plane_normal=[0,0,1], plane_origin=[0,0,top_z−0.01])` 在槽投影区域内无面（trimesh 5.2.0 只有 `section(plane_normal=, plane_origin=)`，没有 `section_plane`） |
| 0.3 | **先删错的那行**：`cad_engine.py:582` 的 `scale = min(base_size_x/840, base_size_y/1188)`（真正的缩放元凶），连同 `:575` 的 `840.0/1188.0`、`:585` 的 `poly_mm -= center` 一起处理，改成 `mm = px * 0.1`，原点取纸面坐标 | 100mm 长的合成轮廓 → **切刀长 = 100.0 ± 0.1mm**（M0 阶段尚无 clearance 环节，必须精确等于 100，不许出现 100.8）；**同一轮廓在 200mm 板与 300mm 板上结果完全一致**（防 scale 残留）；截面积相对误差 ≤ 0.1%（不是"±0.05mm² 且 ±2×clearance"那种量纲互斥的写法；容差总表见 SDS §10.3） |
| 0.3b | **新增：primitives → 有序闭合环**。`_primitives_to_2d_polygon`（`cad_engine.py:503-521`）把 line/arc/polyline 的点**按出现顺序拼接**，不保证闭合、不保证方向、不带内环 | 随机简单多边形往返（polygon → primitives → polygon）后 `shapely.equals_exact(tol=1e-6)`；带 1 个内环的多边形往返后 `holes` 数量与面积不变 |
| 0.4 | 移植 D1'（固定 10px/mm） | `/api/correct-image` 返回 `warpedImage` + `canvasPx` + `paperOriginPx`，尺寸 = **2400×3270**（A4 竖）/ **3270×2400**（横），纸面占 `[150,2250]×[150,3120]`；`mmPerPx` **只作常量回显**（0.1），**下游任何计算禁止读它**（SDS §4.1/§4.2） |
| 0.5 | 移植照片体检（`photo_checks.py`） | 合成近距离照片返回 `warnings[]`，含 `camera_too_close` 与估算高度；`paper_out_of_frame`、`extreme_perspective` 各一条用例 |
| 0.6 | golden test（唯一回归锚） | 合成照片 → STL，槽尺寸误差 **≤ 0.5mm**（原写 1.0 与 SDS §10 的 0.5 冲突，统一取 0.5）；同时断言 `len(slots) == len(tools)`（防 R7 的静默失败）；**再加一条非对称 fixture**（L 形，左下伸 10×5 凸耳）断言凸耳落在 y 的负侧——只用水密/体积测不出竖直镜像 |
| 0.7 | **新增：`geometry/validate.py`** 落地 D12' 两级自检 | L0：`shapely.is_valid` + `explain_validity` + `buffer(0)`；L1：`is_watertight` + `is_winding_consistent` + `manifold.status()` + `genus()` + 体积 ±2% + `min_gap()` 量壁厚。**两个重叠立方体的反例必须被判失败**。作为 0.6 的断言库 |
| 0.8 | **新增：静默失败收口**。范围**只限新代码 + `main.py` 信封层**：新模块禁止 `except: print(...)`，异常一路抛到路由层转成 `error.code`。**旧 `cad_engine.py` 已冻结（SDS §7.1），只允许在它的 `except` 分支里加一行 `errors.append(...)` 计数（不改逻辑、不改返回值）**，M1 换引擎后整体作废 | 用例：故意让 1 个槽失败 → 接口返回 `success:false` 且 `error.code` 非空。**不再承诺"改掉 17 处"**（第二轮审核：SDS 宣布冻结的文件不能派任务去改） |

### M1 — 几何内核移植（3.5 天）

| # | 任务 | DoD |
|---|---|---|
| 1.0 | **新增：后端多轮廓**（原 2.4 的后端部分）。`extract_tool_contours_v26` 只返回**单个最大连通轮廓**（`sam_tool_contour.py:150`、`:226`），改为返回 `List[Contour]`，每个带自己的 `holes` | 一张放了 3 把工具的照片 → 返回 3 个外环 + 正确内环数 |
| 1.1 | 移植槽切刀 + 倒角锥台（§2.1 #4） | 锥台占 `z ∈ [top_z − eff, top_z]`、顶面外扩，其中 **`eff = min(chamfer, max(0, depth − 1))`**（SDS §7.3 的 clamp：`depth ≤ 2` 时 `eff < chamfer`，不 clamp 会把锥台切到槽底以下）；在 `z = top_z − 1e−6` 与 `z = top_z − eff` 两处取 section（**高差必须恰好等于 `eff`**——原写「恰好等于 chamfer」在滑块拉到 `chamfer=1.5 / depth=2` 时必红；原写 `thickness−0.1` 会让期望值差 0.2mm 也必红）。**DoD 不能只量 bbox 开口宽差**——`scale_top` 按 bbox 比例缩放时，bbox 宽差**恒等于** `2×chamfer`，那是恒真断言。必须在**外轮廓凸包的各条边中点**取样（**不是 bbox 边中点**——矩形上两者重合，所以 L 形 fixture 必须用凸包采样才能区分；bbox 中点量到的宽差对 `scale_top` 仿射实现**恒等于** `2×chamfer`，是恒真断言）：每点径向宽 = `chamfer ± 0.12mm`。**v1 明确接受 `scale_top` 仿射实现**（manifold3d 没有 loft，真 offset 变截面要逐段 extrude，留 v2）；因此另加一条**凹角告警**：`cs_o = cs0.offset(eff, JoinType.Miter)` 只作对照，若 `cs_o.area()` 与仿射锥台顶面面积相差 >15%，写 warning「凹角处倒角偏窄」但不阻断 |
| 1.2 | 移植间隙 + 平滑管线（§2.1 #3） | 间隙 0.4mm 时槽比轮廓外扩 0.4±0.05mm；**顺序断言**：`prepare_for_generation` 必须"先 simplify/smooth、后 clearance" |
| 1.3 | 移植内环链路（§2.1 #7 + F4 五处断点全改） | **用一张真实开口扳手照片端到端跑出中心孔**——"圆环基元能过"不算通过（否则 `fill_holes` 与 `RETR_EXTERNAL` 一行不改也能过） |
| 1.4a | Gridfinity 底座剖面 | 底座高 4.75、顶面 chamfer 推导值与 `cq-gridfinity` 常量表一致（±0.01） |
| 1.4b | 堆叠唇五段剖面 | 逐段 bbox 高度 **2.6 / 1.2 / 0.7 / 1.8 / 1.9**（顺序 = `LIP_D4, LIP_D3, LIP_D2, LIP_D1, LIP_D0`），累计 **8.2**（各段 ±0.01、总和 ±0.05——**总和容差必须 ≥ 5×段容差**，否则五段各偏 0.05 可累到 ±0.25，无 bug 也会红）。真源是 tracefinity 常量，**不是** cq-gridfinity 的斜边写法（那套算出 8.09，会永久红） |
| 1.4c | 磁吸孔 + 高度公式 | 孔心**相对格心 ±13.0mm**（即距格角 8.0mm）：同一格内相邻两孔心距 **26mm**，跨格相邻两孔（本格的 +13 与邻格的 −13）心距 **16mm**（42 − 26）；`MAGNET_INSET = 4.8` 是**孔边到格角**（8.0 − 6.5/2 = 4.75 ≈ 4.8），**不参与定位**——「距格角 4.8」与「孔心距 26」算术互斥（42 − 2×4.8 = 32.4 ≠ 26）。断言：孔心到格角 8.0 ± 0.1；`height_mm = height_u * GRHU`（3U 必须 = 21mm，±0.01）；磁孔深 2.4，角 R 4.0 |
| 1.5 | 移植手孔 6 形态 + 倒角（§2.1 #5/#6）+ **重写 `_auto_detect_finger_slots`** | **分两组参数各跑一遍**（默认 `embedDepth=8` 下竖直孔被禁，单组跑不出六形态）：A 组 `thickness=12, embedDepth=8` 只生成 `scoop` 并断言开口；B 组 `thickness=25, embedDepth=22` 生成 `sphere`/`cylinder`/`square`/`rect`/`filleted_rect` 五种并各自断言开口。**形态由生效 `depth`（= `depthOverride ?? embedDepth`）≥ 20 决定**（见 D6'）：`depth < 20` 时**禁止**生成竖直孔（UI 只给 scoop 系），scoop 必须与凹槽**连通**——用 **3D 求交体积** `(scoop_cutter ^ pocket_cutter).volume() > 0.1`（**不能写 `CrossSection` 求交：2D 与 3D 不可交；按 XY 投影解释则正确几何恒为 0，断言恒假**）且坡底 = `top_z − depth`（±0.01，**不是 `thickness − depth`**）；`depth ≥ 20` 时竖直孔按 `depthMode` 断言：`blind` → `abs(bbox[2] − (top_z − depth)) ≤ 0.01`；`through` → `bbox[2] ≤ −0.5`（**原式「≤ 0.1 = 真贯穿」把合法盲孔判红**）；sphere 断言 `abs(cutter.bounding_box()[2] − (top_z − depth)) ≤ 0.01`（**原来的 `≥ 0` 恒真、等于没查**）；`depthMode='through'` 时断言 `bounding_box()[2] ≤ −0.5` |
| 1.0b | **新增：板级参数进数据模型**（从原 2.3a 提前）。`BoardConfig` 增加 `cornerR`（默认 5）、`baseEdgeRoundover`（默认 0）、`slotChamfer`（默认 1.5）；**v1.3 再增板尺寸三字段** `sizeMode`（默认 `'fit-tools'`）/ `widthMm` / `heightMm`，并把 `margin` 默认 8 改 **12**；全部进 Pydantic API schema 与 `summary.paramsEcho` | 字段在 `/api/generate` 请求里可传、在 `summary.paramsEcho` 里原样回显；`sizeMode='custom'` 缺 `widthMm`/`heightMm`，或非 `custom` 模式带了宽高 → 400 `INVALID_SIZE_MODE`；未知字段 → 400 `SCHEMA_UNKNOWN_FIELD` |
| 1.6 | **自定义矩形外壳**（D15' ①）：按 `sizeMode` 定板尺寸 + `cornerR` + `baseEdgeRoundover` + 板厚 | 给定 **3 个 polygon 输入**（不依赖 M2 的交互），三种 `sizeMode` 各断言一次：① `'fit-tools'` → 板外框 = 并集 bbox 各边 + `margin`(12)；② `'custom'` `widthMm=100, heightMm=80` → `bounding_box()` 得 100×80×thickness（**与工具并集大小无关**）；③ `'print-bed'` → 等于 `(printBed.x − 2*edge) × (printBed.y − 2*edge)`（`edge=5`，220 床 → **210×210**；写成整张床会立刻触发分块）。另断言：`'custom'` 且工具超出板框 → `TOOL_OUT_OF_BOARD`（阻断，不自动放大板）；`cornerR`、`baseEdgeRoundover` 与参数一致 |

### M2 — 交互层（3.5 天；含 2.5 板尺寸控件 0.5，与 2.3b 同文件、须同一人）

| # | 任务 | DoD |
|---|---|---|
| 2.1 | 移植 `PolygonEditor` + `useHistory`（§2.2 #1/#2/#4），接入 D18' 点环真源 | 能拖点、边上插点（插入即拖）、删点（到 3 个拒绝）；Ctrl+Z / Ctrl+Shift+Z；**压住鼠标拖 3 秒只产生 1 条 undo** |
| 2.2 | 移植 `ToolEditor` 手孔编辑（§2.2 #3） | 能加/删手孔、拖动、改宽度/深度/旋转、选 6 种形状；**形状选择器按生效 `depth` 过滤**（`depth < 20` 只给 `scoop`，见 D6'），**不是按 `thickness`、也不是按原始 `embedDepth`** |
| 2.3a | **端到端验收**（字段本身已由 1.0b 建好，此处只做联调）：每个参数单独改大 1mm，观察 `summary.paramsEcho` 与网格 bbox 的相应变化 | 三个参数各有一条用例；改 `cornerR` → 板 bbox 不变而圆角处顶点数变化；改 `baseEdgeRoundover` → 只在顶面外圈出现新面 | 
| 2.3b | **前端**：`ParamsPanel.tsx` 三个滑块绑定 `cornerR` / `baseEdgeRoundover` / `slotChamfer`（`foam` 目前在 `src/api/toolProcessor.ts:288` 是 `Record<string, any>`，需补类型） | 三个滑块各有独立可辨效果；`slotChamfer` 用**网格法向统计**：45° 面面积占比与 `2×chamfer×周长` 相符（±10%） |
| 2.4b | **`POST /api/board/fit-check`**（只读）：请求 `{board, tools}`，响应 `{boardMm:{w,h}, unitsX, unitsY, outOfBoardToolIds:[], minEdgeMm}` | 前端不再自己复刻 clearance/cornerR/units*42 判据；同一请求下该端点的 `outOfBoardToolIds` 与 `/api/generate` 的 `TOOL_OUT_OF_BOARD` **必须完全一致** |
| 2.4 | **前端多工具**：一张图 N 个轮廓 → 列表 → 一次生成 | 一张 A4 放 3 把工具，点生成得到 3 个槽的板；删除其中一把后重生成只剩 2 个槽 |
| 2.5 | **前端板尺寸控件**（SDS §6.5）：单选框切 `sizeMode` + 自定义宽高输入框 + margin 滑块，绑 `BoardConfig`。**计 0.5 人日**，与 2.3b 同一文件 `ParamsPanel.tsx`、必须同一人做 | ① 三种模式都能切，且**切走 custom 后请求体里 `widthMm`/`heightMm` 为 `null`**（往返 cut→custom→fit-tools 后仍能生成）；② 切到 `'custom'` 时输入框**预填当前算出的尺寸**（不是 0）；③ 工具超出板框时**由后端 `/api/board/fit-check` 返回 `outOfBoardToolIds`**，按钮置灰并提示「有 N 个工具超出板框」，**不自动放大板**（前端只用矩形近似做提示，最终以后端为准，不复刻 clearance/cornerR 判据）；④ 改板尺寸**不挪动任何工具坐标** |

### M3 — 拍照端与产出（3.5 天）

| # | 任务 | DoD |
|---|---|---|
| 3.1 | 纸角四角手拖（§2.2 #6） | 自动检测失败时能手动拖，且 warp 用新手拖的角（`CalibrationPanel.tsx:66-79` 现在是只读） |
| 3.2 | **模型分块**（D14' 修订版） | 300×200 板 + 200×200 限制 → 出 2 片；两片各自的 `bounds` 相加 = 原板 bbox（±0.01）；切缝筋厚 ≥4mm；Gridfinity 板请求分块直接返回 `success:false` + `error.code = GRIDFINITY_SPLIT_UNSUPPORTED`（信封只有 `error:{code,message,detail}`，**没有顶层 `error_code`**，见 SDS §4.0）（与"找不到 ≥4mm 筋"的 `NO_SPLIT_RIB` 分开） |
| 3.3 | 试切件生成按钮 | 一键出 40×40×10 三档间隙（0.2/0.4/0.6）试切件 STL，三件同一次请求 |
| 3.4 | **DXF / SVG 1:1 导出**（D13'）。**默认 y 翻转（与照片同向）**，翻转开关默认 `true` | 重新读回 DXF（`ezdxf.readfile`）后：每个凹槽 LWPOLYLINE 面积 = 设计值 ±0.1mm²；`$INSUNITS == 6`；板外框闭合；每个槽有 depth 标注；**非对称点断言**：输入顶点 `(12.3, 45.6)` → 读回必须是 `(12.3, 251.4)`（= 297 − 45.6，±0.01）——面积对镜像完全不敏感，只有这条能抓住翻转做反 |

### M4 — 收尾（1.5 天）

| # | 任务 | DoD |
|---|---|---|
| 4.1 | 持久化：localStorage 全量草稿 + `schemaVersion`（D21'） | 刷新页面后 board/tools/params 全在；手改 `schemaVersion` 为 999 后不崩、按规则走降级 |
| 4.2 | 错误边界 | 任一 API 抛错时 UI 有可读提示 + 重试按钮，不出现白屏；守卫触发（`TOOL_OUT_OF_PAPER` 等）有明确出路提示 |
| 4.3 | 端到端冒烟 | 一条命令跑完 A4 照片 → STL + DXF，两份产物都落盘；失败时非零退出 |
| 4.4 | 文档纠偏（附行号） | 修 `README.md:165`（撤销/重做真实状态）、`PRODUCT_REQUIREMENTS.md:139-201`（STEP AP242 "可二次编辑"是假的、`F2.5` 标注矛盾）、`DEVELOPMENT_GUIDE.md` 的 `useWorkflow` 与实际不符 |

**总计：约 15.0 人日**（v0.3 是 16，v0.2 是 26–37）。
**v0.3 → v1.0 的减法**（v0.3 基线实为 15.5：原表 16 里含 1.4 拆分后重复计数的 0.5）：砍畸变标定 −0.5、打印反馈回路 −0.5、first-fit 自动排 −0.5、亚像素精修 −1.0、M4 文档减半 −0.5，**合计 −3.0**；**加法**：M-1 冒烟 +0.5、0.3b 闭合环 +0.5、0.7 校验库 +0.5、1.0 后端多轮廓 +0.5、1.0b 三参数进 schema +0.5，**合计 +2.5**。15.5 − 3.0 + 2.5 = **15.0**；再扣掉"1.6 因参数提前而不再返工"的 0.5 → **14.5**；**v1.3 板尺寸控件 2.5 再 +0.5 → 15.0**。里程碑相加 `0.5+2.5+3.5+3.5+3.5+1.5 = 15.0`，两套账一致。

## §5 明确砍掉（v2 再谈）

| 条目 | 理由 |
|---|---|
| 自研 2.5D loft 内核（D4.1/D4.2/D4.3） | tracefinity 已解决；自研会在 V 形内凹口产生层间折叠且守卫抓不到 |
| STEP / 真 B-Rep / OCCT golden reference | 用户只打印；现在的 STEP 是网格包壳，PRD 的"可二次编辑"是假的 |
| 完整自动排版（STRtree/NFP/增量锁定） | 工具在纸面坐标里本来就是「拍在哪就在哪」，只需要重叠检测；板框另由 D15' 的 `sizeMode` 决定，不需要为了塞进某块板而重排 |
| 18 件 × 3 厚度 DoD 矩阵 | 打印成本 > 开发成本 |
| Foam 板中空 + 网格肋 + 用料工时估算 | 与深槽算术互斥（§3 D8'） |
| 3MF 多色 / 文字标签 / SVG 出图（DXF 已够） | 个人自用无意义 |
| IndexedDB 项目画廊 | localStorage 够 |
| 燕尾拼缝 | 改用圆柱定位销（D14'），精度要求低得多 |
| 畸变棋盘格标定（原 M3.6）+ 畸变告警 | 用户 m02193 明确否决：「没有那么重要，你边缘放大一些，比如预留多几毫米，就能吃掉这个误差了」。改为 `margin` 默认 **12mm**，用留白吃掉 2–4mm 的边界畸变；连告警也不做（告警会让人以为要处理） |
| 打印反馈回路（原 M3.2） | 与 D9'「浏览器本地记住上次间隙」重复 |
| first-fit 自动排（原 M2.5） | 工具在纸面坐标里拍在哪就在哪，手拖 + 旋转 90° 调重叠更快；板框尺寸另由 D15' 的 `sizeMode` 决定，不需要为塞进某块板而重排。只保留重叠高亮。**D3' 与本表已同步删除，M2 不再有该项** |
| 亚像素精修（原 M2.6，降级为 v1.1） | 其 DoD 测的是**重复性**不是**精度**；v1 保留现有 DP 抽稀（`eps=0.3mm`） |
| Gridfinity 板的分块（D14' 修订） | 锥台底座/唇/磁孔按整板成型，切开后中间片全断，粘起来摞不上 |

---

## §6 许可证与合规（v0.2 零字提及，必须补）

- tracefinity 是 **MIT**（`Copyright (c) 2024 Tracefinity Contributors`）。
- 移植代码必须在文件头保留原始版权与许可声明，并在仓库根加 `NOTICE`（或 `THIRD_PARTY_LICENSES.md`）说明"几何内核部分移植自 tracefinity/tracefinity，MIT"。
- 本项目自身许可证需先确认（`Y:/.../toolmanagement-web/LICENSE` 存在，内容待核）。

---

## §7 仍未决、需要用户拍板的问题

| # | 问题 | 为什么必须问 |
|---|---|---|
| ~~Q1~~ | ~~"Foam 模式"到底是什么？~~ **已决（用户 m00723）**：只管生成模型，不管材料与工艺。实心板 + 凹槽；打印（PLA/PETG/TPU）与 CNC 切割共用同一份几何，STL 与 DXF 双输出。**不做中空、不做材料相关策略。** | 已决，见 §3 D8'/D13' |
| ~~Q2~~ | ~~每把单独拍还是一次拍多把？~~ **已决（用户 m00751）**：一张 A4 放 1..N 把，全部必须在纸内；超过 A4 的工具不做。 | 已决，见 §3 D2' |
| ~~Q3~~ | ~~圆弧基元能不能只读~~ **已决（m00776「按你的推荐」）**：v1 圆弧只读，进入顶点编辑时降级为折线并提示。 | 已决 |
| ~~Q4~~ | ~~间隙默认值~~ **已决**：默认 0.4mm + 试切件校正。 | 已决 |
| ~~Q5~~ | ~~一块板默认按 3–5 把工具设计~~ **已决（用户 m02193）**：板尺寸与工具数量无关。`sizeMode` 三选一（`fit-tools` / `custom` / `print-bed`），想放几把放几把；A4 只承担量尺作用，超过打印床按 D14' 分块。 | 已决，见 D15' |
| ~~Q7~~ | ~~单把工具比打印床长怎么办~~ **暂按 A 方案（D17'，直接报错）实现**；如用户后续要 B/C，作为增量。 | 已定 v1 默认 |
| ~~Q6~~ | ~~导出范围~~ **部分已决（m00723）**：STL + DXF/SVG 都要（D13'）。3MF 仍推迟。 | 已决 |

---

## §8 下一步

**状态：计划与 SDS 均已定稿（v1.3），六轮独立审核收敛，环境已验证可用（WSL venv），可开工。**

1. ~~用户拍板 Q5~~ **已决（用户 m02193）**：板尺寸与工具数量无关，`sizeMode` 三选一（`fit-tools` / `custom` / `print-bed`）。Q1–Q7 全部已决，**无待定项**。
2. ~~开工第一件事 —— 建可回滚基线~~ **已完成（2026-11-05）**：`git rm -r --cached node_modules && git add -A && git commit && git tag pre-m0`。基线提交 `68f950b`、tag `pre-m0` 指向当前 HEAD、工作区干净；`node_modules` 10367 文件与 20 个 `.pyc` 已停止跟踪（仍在磁盘），`.gitignore` 补了 `.venv/` / `__pycache__/` / `*.pyc` / `.claude/`。**新会话不必再做这一步**，直接从 M-1 开始。
3. **按 `docs/planning/v1-sds-v1.3.md` 实施**：主会话调度 + 子 agent 编码 + 独立审核。
   - 先跑 M-1（0.5d，`scripts/smoke_geometry.py` 三条断言）—— 它同时证明环境能跑、F1 的开口为真、DoD 可离线复现。没有它，后面每条 DoD 都可能被"静默失败"骗过。
   - M0 内部**不是全并行**：批 1 = `0.1` ∣ `0.2`+`0.7`+`0.8`；批 2 = `0.4` → `0.3`+`0.3b` → `0.5` → `0.6`（严格串行）。
4. **审核节律**：每个里程碑结束开 1 个独立审核 agent（不复用实施 agent 的上下文），按 SDS §12.3 的固定检查项逐条核。**铁律：任何判据与用到它的几何必须共用同一个局部量**（`top_z` / `depth` / `clearance` / `chamfer`），复审只需 grep 这四个名字有没有被绕过。
5. **六轮审核收敛记录**（供参考，不必重跑）：一轮 28 条 → 二轮 23 条 → 三轮 13 条 → 四轮 11 条 → 五轮 6 条 must-fix → 六轮（只审 m02193 两条反馈）8 条 must-fix；每轮新引入问题数 23 → 15 → 13 → 11，已收敛。历史版本在 `docs/planning/archive/`。


---

## §9 新会话实施交接（SDS 定稿后执行）

> 本节是「v1.3 定稿 → 新会话开工」的交接物。SDS 已在 §12 给出分工、交付格式与审核闸门；本节只补**启动新会话所需的上下文与口令**，不重复 SDS 内容。

### 9.1 开工前已完成（本会话）

| 项 | 状态 |
|---|---|
| 《v1 开发计划》`v1-plan-v1.3.md` | 定稿，六轮独立审核收敛，Q1–Q7 全决 |
| 《软件设计说明书》`v1-sds-v1.3.md` | 定稿，§12 实施协议 + §12.3 固定审核项 |
| 历史版本归档 | `docs/planning/archive/`（11 份） |
| 许可证 | 项目根 `LICENSE` = **MIT**（`Copyright (c) 2026 Toolmanagement-web`），与 tracefinity MIT 兼容；移植需按计划 §6 加 `NOTICE` |
| `python_backend/requirements.txt` | **已按 SDS §11.2 重写**（去掉 `cadquery==2.8.0` / `numpy==1.24.3` / `opencv-python==4.9.0.80` 三个在 Python 3.14 上无 wheel 的硬 pin，改 `>=` 下限 + `opencv-python-headless`） |
| Git 可回滚基线 | **已建**：基线提交 `68f950b`（`chore: untrack node_modules and bytecode, checkpoint before v1`），后接文档记录提交；**tag `pre-m0` 指向当前 HEAD**（含「基线已完成」的最终文档状态）；`node_modules` 10367 文件与 20 个 `.pyc` 已停止跟踪（文件仍在磁盘），工作区干净 |
| WSL 环境 | **已验通**：`python3 -m venv .venv`（Python 3.14.4）→ `pip install -r python_backend/requirements.txt` → `.venv/bin/python -c "import numpy,shapely,manifold3d,trimesh,cv2,skimage,ezdxf,fastapi,uvicorn,pytest"` **全绿**（numpy 2.5.4 / shapely 2.2.0 / manifold3d 3.5.4 / trimesh 5.2.0 / cv2 5.0.0 / skimage 0.26.0 / ezdxf 1.4.5）。`python3.14-venv` / `python3-pip` 已 apt 装通 |

### 9.2 新会话启动口令（可直接复制）

```
新会话，目标：按 docs/planning/v1-sds-v1.3.md 实施 toolmanagement-web 的 v1。
你（主会话）只做三件事：调度、验收关键问题、开独立审核 agent；不自己写实现代码。
先读：docs/planning/v1-plan-v1.3.md（§8 下一步 + §9 交接）与 v1-sds-v1.3.md（§2 坐标系、§3 数据模型、§7 几何、§12 实施协议）。
实施顺序：M-1（冒烟脚本三条断言）→ M0 → M1 → M2 → M3 → M4，严格按 §12.1 的阻塞边分组，不要全并行。
每完成一个里程碑：开 1 个独立审核 agent（不复用实施 agent 上下文），按 §12.3 固定检查项逐条核；任一项不过即打回，不合并。
子 agent 交付格式按 §12.2（改动文件绝对路径 + 关键行号 + 跑过的命令与输出 + 未完成项）。
铁律：任何判据与用到它的几何必须共用同一个局部量（top_z / depth / clearance / chamfer，见 §7.3）。
基线已建（基线提交 68f950b / tag pre-m0 指向当前 HEAD，工作区干净），直接从 M-1 开始；不要重复清理 git
```

### 9.3 环境注意事项（交接给新会话）

- 项目实际在 WSL：`//wsl$/Ubuntu/home/atdoc/projects/playground/toolmanagement-web`（Windows 侧 `Y:` 是它的映射）。
- 从 Windows 侧调 WSL 用 `wsl -d Ubuntu bash -lc "cd ~ && <cmd>"`；若 cwd 在 `/mnt/d/...` 会打印 `chdir(...) failed 5`，无害。
- `curl https://pypi.org/simple/` 会超时但 **`pip` 能正常下载**，不要拿 curl 当出网判据；opencv 的 wheel 约 61MB，慢网下用 `pip install --retries 10 --timeout 180 --resume-retries 30 -r python_backend/requirements.txt`。
- 验收环境的命令：`.venv/bin/python -c "import numpy,shapely,manifold3d,trimesh,cv2,skimage,ezdxf"` 必须全绿才开 M-1（§11.2）。**本会话已实测全绿**，新会话只需复核一次即可。
- `main.py:4` 顶层 `import cv2`，必须用 `opencv-python-headless`，否则无 X 的 WSL 撞 `libGL.so.1`。

### 9.4 遗留（不阻塞开工）

- 计划 §7 的 Q1–Q7 全部已决；**无待定项**。
- `scripts/smoke_geometry.py` 三条断言（M-1）尚未编写——由新会话的 M-1 子 agent 交付。
- 仓库 git 基线已建（基线提交 `68f950b`，tag `pre-m0` → 当前 HEAD），工作区干净；`node_modules` / `.venv` / `__pycache__` / `.claude/` 已在 `.gitignore` 中。**无需再清理**。
