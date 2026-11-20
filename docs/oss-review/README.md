# 开源参考源码审查（OSS Review）

> 本文是对六个开源仓库做**源码级审查**后的结论索引，用于指导 toolmanagement-web 的 M1/M2/P2 实施。
> 审查于 2026-11-20 完成，固定 commit 见各详细报告与 [REFERENCE_REGISTRY.md](REFERENCE_REGISTRY.md)。
> 审查产物不含任何个人信息；详细报告在 `docs/oss-review/` 下。

## 0. 本次审查的基本原则（不可动摇）

开源项目是**算法与实现的参考**，不是本项目的规格来源。三条铁律：

1. **毫米链不能动。** 三套坐标（源图像素 y-down → 纸面毫米 y-down → 板局部毫米 y-up）、唯一 y 翻转点 `to_board_frame`、唯一 z 基准 `top_z = board_top_z(board)`，都是被 `840×1188` 缩放、`±H/2` 居中、tracefinity 二次取负这几个静默 bug 逼出来的。任何借鉴都不许改这些基准。
2. **库职责分离。** Shapely 管 2D 偏移/合法性，manifold3d 管 3D 布尔，trimesh 管网格检查与 STL。不要让同一几何操作在多个库里重复实现。
3. **几何真源唯一留在后端。** 毫米坐标是唯一事实源，Canvas 只负责绘制；前端不得计算最终打印轮廓，失败必须显式报错而非静默降级。

## 1. 六仓库一览

| 仓库 | 定位 | 许可证 | 价值 | 一句话结论 |
|---|---|---|---|---|
| tracefinity | 照片→AI 描边→Gridfinity 盒（FastAPI+manifold3d） | MIT | A | 核心几何算法可直接借鉴，但 y 取负/间隙/静默失败三处必须重写 |
| cq-gridfinity | CadQuery/OCP 的 Gridfinity B-Rep 库 | MIT | A（交叉校验） | 只取常量数值做第二信源；剖面分段与本项目口径冲突，禁止覆盖 |
| RapidTool-ShadowBox（ToolTrace） | React+Zustand+three 的同类产品 | README 声明 MIT（仓库无 LICENSE 文件，v0.0.0） | A（产品交互） | 抄工作流壳层与交互，几何/导出是半成品且真相分裂，不能抄 |
| pascalorg/editor | AECO 3D 建筑编辑器 + 多边形编辑核心 | MIT（视频 CC BY 4.0） | A（编辑交互） | 7 条编辑需求全有对应实现，但绑定 bun/turbo/米制容差，抄思路不抄代码 |
| manifold3d (elalish/manifold) | C++ 流形保证布尔内核 + Python binding | Apache-2.0 | 核心依赖 | 已是本项目布尔内核，深入 batch_boolean/status/genus/min_gap 即可 |
| SAM 2 | Meta FAIR 可提示分割基础模型 | Apache 2.0（字体 OFL-1.1 / cc_torch BSD-3 / 权重另核） | P2 交互精修 | 适合「点选一把工具→mask」，但输出在像素域，换它会动 golden test 基线，需单独排期 |

## 2. 关键发现：Gridfinity 常量交叉验证（一手取证）

读取 cq-gridfinity `constants.py`（commit `d317286`）与本项目 `docs/planning/` 基准逐项对照：

| 参数 | 本项目（tracefinity 剖面） | cq-gridfinity | 一致？ |
|---|---|---|---|
| 格距 GRU | 42 | 42 | ✅ |
| 高度单位 GRHU | 7（3U=21） | 7（外形高另计 3.8+7U） | ⚠️ 口径不同 |
| 底座总高 | 4.75 | 4.75 | ✅ |
| 底座分段 | 0.8 / 1.8 / 2.15 | 0.7 / 1.8 / 2.25 | ❌ |
| 堆叠唇垂直高 | 8.2（LIP_D0..D4=1.9/1.8/0.7/1.2/2.6 累计） | 6.6（1.6/1.2/0.7/1.8/1.3 累计） | ❌ 差 1.6mm |
| 磁孔孔心偏移 | 相对格心 ±13 | 13（=26/2） | ✅ |
| 磁孔直径/深度 | φ6.5 / 2.4（本项目常量；tracefinity 代码 φ6×2.4） | φ6.5 / 2.4 | ⚠️ tracefinity 代码与本项目常量本身有 φ6 vs φ6.5 差异，M1 需实测定案 |
| 外角 R | GF_CORNER_R=3.75 | GR_RAD=4 | ❌ |

**结论**：总量级（格距、底座总高、磁孔偏移）可交叉验证；**分段剖面与唇高必须以 tracefinity 为唯一真源**，两套来源混用会让摞叠失败。cq-gridfinity 的 Baseplate **没有磁孔**，磁孔只在 Box 类 `holes=True` 时才有——这是最容易误配的点。

## 3. 按里程碑的行动建议

### M1 几何增强（当前主线）
- **gridfinity 板体/唇/磁孔**：以 tracefinity `stl_generator_manifold.py` 为实现蓝本——`_build_base_unit`（三层 `scale_top` 收腰）、`_build_stacking_lip_notch`（五段唇槽，`LIP_D4=2.6` 径向宽）、`_make_magnet_holes`（每格 4 孔 ±13mm，batch union）。常量集中到 `geometry/constants.py`，唇分段不得参考 cq-gridfinity。
- **手孔 6 形态**：tracefinity `_make_finger_holes` 支持 circle/cylinder/square/rectangle/filleted_rectangle（5 种），本项目第 6 种 scoop 需自建。★ 头号坑：`fh_y = -(fh.y_mm + offset_y)` 是 tracefinity 像素 y-down→manifold y-up 的一次性翻转，本项目 `to_board_frame` 已翻过，照抄即**竖直镜像**；`rotation` 也必须取负。DoD 必加「手孔落在父口袋内、y 正侧放手孔、`bbox[1] > 0`」。
- **倒角锥台**：manifold `CrossSection.offset(eff, Round)` + `extrude(..., scale_top=(sx,sy))`；`scale_top` 仅仿射非真 loft。有效倒角 `eff = min(chamfer, max(0, depth-1))`。
- **多轮廓/内孔**：tracefinity `_shapely_to_cross_sections` 的 `buffer(0)` + 形态学开运算双级修复 + EvenOdd 内环值得借鉴，但本项目先 simplify 后 clearance 的顺序断言必须保留。
- **静默失败**：tracefinity 大量 `try/except + logger.warning + continue` 会让用户拿到缺手孔/缺倒角的 STL；本项目必须显式报错进错误信封。

### M2 前端
- **工作流壳层与交互**（抄）：ShadowBox 的六步流程、光标中心缩放、可拖拽四角、SVG 覆盖层、「点内即精修」命中、Worker 超时协议、参数联动（Offset↔MARGIN/GAP）、显式 GPU 资源释放。
- **多边形编辑器**（抄思路）：pascalorg/editor 的 7 条交互逐条有实现——快照深拷贝、preview/commit 分离、插点即拖、沿外法线拖边、命中优先级、≤3 顶点拒绝、一次拖拽一条 undo。用 `zundo` 的 `temporal.pause()/resume()` 重写为「一次 gesture 一条 undo」。
- **绝不照抄**：ShadowBox 的 `rectifyToA4` 存在但 UI 从未调用、单标量 `pixelsPerMm` 斜拍变形、`offsetPolygon` 静默回退、`exportSTL.ts` 是 TODO 桩——它是前后两套轮廓真相的反面教材。

### P2 识别增强（需单独排期）
- 采用「rembg/传统 CV 自动粗分割 + SAM 2 点选迭代修正 + 像素转毫米多边形」组合，SAM 2 作可选低耦合服务。
- ★ SAM 2 输出是像素 mask，必须经 10px/mm 纸面标定换算；现有 `sam_tool_contour.py` 的 `dk=31/15px≈+3.4mm` 膨胀与 `test_golden_m0.py` 的 `xfail(strict=True)` 不会因换分割器自动修复。**禁止与 xfail 修复合并提交**，用影子测试保护回归基线。

## 4. 不可照搬的坑（汇总）

1. **坐标系双重翻转**：tracefinity 手孔 y 取负、rotation 未取负 → 本项目会竖直镜像。
2. **尺寸口径冲突**：cq-gridfinity 唇高 6.6 vs 本项目 8.2；底座分段、外角 R 均不同；Baseplate 无磁孔。
3. **像素域输出**：SAM 2 mask 必须换算到纸面毫米；ShadowBox 单标量 ppm 斜拍变形。
4. **静默降级**：ShadowBox `offsetPolygon` 缺库时返回原始点、tracefinity `try/except+continue` → 本项目失败必须显式报错。
5. **许可不完整**：ShadowBox 无 LICENSE 文件仅 README 声明 MIT；SAM 2 字体 OFL-1.1、cc_torch BSD-3、权重许可需独立核查；pascalorg/editor demo 视频 CC BY 4.0。
6. **工具链绑定**：pascalorg/editor 是 bun/turbo monorepo、React 19/Next 16、米制容差 1e-6/1e-3/0.015 → 只能移植交互思路，不能复制代码与常量。

## 5. 详细报告索引

- [tracefinity.md](tracefinity.md) — Gridfinity 几何算法蓝本与三处必改坑
- [cq-gridfinity.md](cq-gridfinity.md) — 常量交叉验证与 B-Rep→网格映射禁区
- [shadowbox.md](shadowbox.md) — 同类产品架构、交互与「两套轮廓真相」反例
- [pascal-editor.md](pascal-editor.md) — 多边形编辑器 7 条交互实现对照
- [manifold.md](manifold.md) — 布尔内核 API、batch_boolean、拓扑校验与版本坑
- [sam2.md](sam2.md) — 可提示分割 API、毫米链冲突与 xfail 基线保护
- [CROSSCHECK.md](CROSSCHECK.md) — Gridfinity 常量一手交叉验证笔记
- [REFERENCE_REGISTRY.md](REFERENCE_REGISTRY.md) — 参考登记表（版本/许可/借鉴范围/是否复制源码）
