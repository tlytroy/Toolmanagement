# 开源参考登记表（OSS Reference Registry）

> 记录每个参考仓库的版本、许可证、参考模块、借鉴的具体算法、是否复制源码。
> 区分「参考算法（自己重写）」与「直接复用代码（需许可合规）」。本项目的默认策略是**只参考算法，不复制源码**。

审查日期：2026-11-20。所有 commit 为审查时固定版本。

| # | 仓库 | commit / 版本 | 许可证 | 许可核查结论 | 借鉴分类 | 借鉴的具体内容 | 是否复制源码 |
|---|---|---|---|---|---|---|---|
| 1 | tracefinity/tracefinity | `fff65f0d6b6c9b648617c1228cf2365bb1ecc7f9` | MIT (Copyright (c) 2024 Tracefinity Contributors) | MIT，商用友好，保留版权声明即可 | 参考算法（重写） | 底座三层收腰剖面 0.8/1.8/2.15 + `scale_top`；五段堆叠唇槽 `LIP_D0..D4`；磁孔每格 4 孔 ±13mm batch union；`buffer(0)`+形态学开运算双级修复；cutter 先合并再一次布尔减；`STL_GEOMETRY_VERSION` 缓存失效 | 否。本地 `reference/oss/tracefinity/` 是历史 MIT 副本，仅作阅读；新代码自行重写且不照抄 y 取负/静默失败 |
| 2 | michaelgale/cq-gridfinity | `d317286ec15dc52587fadbd4f4c1e13f9cd8a8b2`（v0.5.7） | MIT | MIT，商用友好 | 数值交叉验证（第二信源） | 仅取一致项做校验：GRU=42、GR_BASE_HEIGHT=4.75、GR_HOLE_DIST=13、φ6.5×2.4、lip_width=2.6；新增可选常量 GR_BOT_H=7、GR_BASE_CLR=0.25、GR_HOLE_SLICE=0.25（注明来源） | 否。不引入 CadQuery/OCP/cqkit 依赖；不搬剖面分段与面边计数断言 |
| 3 | FracktalWorks/RapidTool-ShadowBox（ToolTrace） | `f8372c1908db4ae9da367b1320af25a1f6d73bf0`（v0.0.0） | README 声明 MIT（Copyright © 2025 RapidTool），**仓库无 LICENSE 文件** | ⚠️ 许可不完整：仅 README 声明，无 LICENSE 文件；复用前需作者书面确认 | 产品交互 / 架构参考 | 六步工作流壳层、光标中心缩放、可拖拽四角、SVG 覆盖层、「点内即精修」命中、Worker 超时协议、参数联动、显式 GPU 资源释放 | 否。只抄交互思路；几何真源、透视校正、STL 导出留后端 |
| 4 | pascalorg/editor | `cf37d32cdc195a2a179d1f9e7d02624f6d834c3e` | MIT (Copyright (c) 2026 Pascal Group Inc.)；docs/media/next-demo 视频为 CC BY 4.0 | MIT；视频资源单独许可，本项目不引用 | 交互逻辑参考（抄思路不抄代码） | 7 条编辑交互：initialPolygon 深拷贝快照、preview/commit 分离、插点即拖、沿外法线拖边、命中优先级、≤3 顶点拒绝、一次 gesture 一条 undo（zundo pause/resume 重写） | 否。bun/turbo/米制容差强绑定，全部按毫米坐标+Zustand 重写 |
| 5 | elalish/manifold（manifold3d） | 最新稳定 v3.5.5（2026-11-13） | Apache-2.0 | Apache-2.0，商用友好，保留版权/License 并标注修改 | 直接依赖（已是核心内核） | 核心 API：`+/-/^` 布尔（无 `.intersect()`）、`bounding_box()` 扁平 6 元组、`CrossSection.bounds()` 扁平 4 元组、`extrude(scale_top=)`、`batch_boolean(..., OpType.Subtract)`、`status()`、`genus()`、`min_gap()`、`offset(..., JoinType.Round)` | 以 pip 依赖形式使用（非复制源码）；保留依赖声明与许可 |
| 6 | facebookresearch/sam2 | `2b90b9f5ceec907a1c18123530e92e794ad901a4` | Apache 2.0；字体 Inter/Noto Emoji = OFL-1.1；cc_torch = BSD-3-Clause；权重文件不在仓库 | ⚠️ 代码 Apache-2.0，但权重需独立合规核查（模型卡/许可） | 未来 P2 交互分割参考（未引入） | `SAM2ImagePredictor`（set_image + 点/框/迭代 mask prompt）、`SAM2AutomaticMaskGenerator.generate()`；定位为「粗分割 + 点选精修」的交互层 | 否。仅作 API 研究；像素 mask 需经 10px/mm 换算，禁止与 golden test xfail 修复合并 |

## 附：参考但未列入六清单的库（本项目已是依赖或已选定）

| 库 | 状态 | 说明 |
|---|---|---|
| Shapely | 已用依赖 | 2D 偏移/合法性唯一内核；本项目先 simplify 后 clearance 顺序不可改 |
| trimesh | 已用依赖 | 网格检查/修复/组件/STL；`trimesh.load(process=True)` 才 watertight |
| OpenCV | 已用依赖 | 纸张检测/透视校正；本项目固定 10px/mm + A4 物理约束独立实现 |
| ezdxf | M3 计划依赖 | DXF 导出用 LWPOLYLINE/CUT/ANNO，y 翻转只在 DXF adapter 一次 |
| React-Konva / Fabric.js | 仅了解 | 编辑器骨架已选 pascalorg/editor 思路 + 自研渲染层，不引入 |
| rembg | P2 候选 | 代码 MIT 但权重许可各异（BRIA RMBG-2.0 商用受限），引入前逐一核查 |
| Clipper2 | 仅算法参考 | 作为 Shapely buffer 的独立对照，不引入第二套几何内核 |

## 合规说明

- 本项目对所有参考仓库一律**不复制源码**，只重写算法思路。现有 `reference/oss/tracefinity/` 是历史遗留的 MIT 副本，已在本项目 `docs` 中注明来源与许可。
- 所有「直接复用」仅限以 pip 依赖形式使用的 manifold3d（Apache-2.0），依赖声明保留。
- 许可不完整的仓库（ShadowBox 无 LICENSE、SAM2 权重）在实际引入代码前必须完成书面合规核查。
