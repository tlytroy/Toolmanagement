# cq-gridfinity 开源仓库审查报告（对 toolmanagement-web 项目的参考价值）

- 审查对象：`michaelgale/cq-gridfinity`，固定 commit `d317286ec15dc52587fadbd4f4c1e13f9cd8a8b2`
- 审查方式：GitHub MCP `get_file_contents` 列目录 + `web_fetch` 读取对应 commit 的 raw 原文（MCP 的 embedded resource 在本环境不可展开，故用 raw 兜底）
- 阅读文件：`cqgridfinity/constants.py`、`gf_obj.py`、`gf_baseplate.py`、`gf_box.py`、`__init__.py`、`README.md`、`LICENSE`、`setup.py`、`CHANGELOG.md`、`requirements.txt`、`tests/test_box.py`、`tests/test_baseplate.py`、`tests/common_test.py`
- 结论定位：**可作为 Gridfinity 尺寸语义与数值的“第二信源”交叉验证，但不可作为几何实现模板**（B-Rep vs 网格的根本差异）。

---

## 1. 定位与技术栈（CadQuery）

- 仓库自述：`README.md` — “a python library to build Gridfinity boxes, baseplates, and other objects based on the CadQuery python library”。Gridfinity 由 Zach Freedman 发明（1U=42mm，高度 1U=7mm）。
- 构建/依赖链（`setup.py`、`requirements.txt`）：
  - `install_requires = ["cadquery", "cqkit>=0.5.6"]`；锁定版 `cadquery==2.4.0`、`cadquery-ocp==7.7.2`、`cqkit==0.5.8`、`numpy==2.1.3`。
  - Python `>=3.9`；开发容器 Python 3.12 + CadQuery 2.4；许可证字段 `license="MIT"`，分类 `Development Status :: 4 - Beta`。
  - 三个命令行脚本入口：`gridfinitybox=cqgridfinity.scripts.gridfinitybox:main`、`gridfinitybase=...gridfinitybase:main`、`ruggedbox=...ruggedbox:main`。
- 几何内核为 **CadQuery / OpenCascade（OCP）B-Rep**：`cq.Workplane`、`cq.Sketch`、`extrude(taper=…)`、`faces(">Z").workplane().pushPoints(...).cboreHole(...)`、`shell()`、`mirror()`、`edges(...).fillet(...)`、`intersect/union/cut`；导出 `save_step_file`（`cqkit.export_step_file`）、`save_stl_file`（`OCP.BRepMesh.BRepMesh_IncrementalMesh` + `OCP.StlAPI.StlAPI_Writer`，参数 `tol=1e-2, ang_tol=0.1`）、`save_svg_file`（`cadquery.exporters.export`）。
- **版本兼容 hack（重要参考）**：`cqgridfinity/gf_obj.py` 顶部有 `ZLEN_FIX` 机制——运行时用 `cq.Workplane("XY").rect(2,2).extrude(1, taper=45)` 探测 `BoundingBox().zlen`，CadQuery <2.4 需要把带锥度挤出长度按 `1/cos(taper)` 补偿；`extrude_profile()` 每段都依此分支。CHANGELOG v0.4.4/v0.4.5 为“IMPORTANT FIX”，说明**锥度挤出的垂直长度语义曾随 CQ 版本变化**，这是移植剖面公式时最容易踩的坑。
- 辅助库 `cqkit.cq_helpers` 提供 `rounded_rect_sketch()`、`composite_from_pts()`、`rotate_x()`、`recentre()`；选择器 `VerticalEdgeSelector`、`HasZCoordinateSelector`、`FlatEdgeSelector`、`FlatFaceSelector` 用于“按高度/方向挑边再倒角”，这是 B-Rep 拓扑操作，网格库无对应物。

## 2. 目录与核心类

```
cq-gridfinity/
├── cqgridfinity/
│   ├── __init__.py        # 版本 __version__='0.5.7'；星号导出各模块
│   ├── constants.py       # 所有 GR_* 尺寸常量（唯一尺寸真源）
│   ├── gf_obj.py          # 基类 GridfinityObject
│   ├── gf_baseplate.py    # GridfinityBaseplate
│   ├── gf_box.py          # GridfinityBox / GridfinitySolidBox
│   ├── gf_drawer.py       # GridfinityDrawerSpacer
│   ├── gf_ruggedbox.py    # GridfinityRuggedBox（最大，47KB）
│   ├── gf_helpers.py、scripts/、shims/
├── tests/                 # test_box / test_baseplate / test_rbox / test_spacer / common_test
├── README.md(32.8KB) / LICENSE / setup.py / CHANGELOG.md / requirements.txt / partcad.yaml
```

- **`GridfinityObject`（`gf_obj.py`）**：所有类的基类，规格 `__init__(self, **kwargs)`，属性 `length_u/width_u/height_u`（默认 1 1 1）、`_cq_obj`。关键签名：
  - `@property cq_obj / length / width / height / int_height / max_height / floor_h / lip_width / outer_l / outer_w / outer_dim / inner_l / inner_w / inner_dim / half_l / half_w / half_dim / half_in / outer_rad / inner_rad / under_h / safe_fillet_rad / grid_centres / hole_centres`
  - `extrude_profile(self, sketch, profile, workplane="XY", angle=None)` — 剖面核心：每项为 `长度` 或 `(斜边长度, taper角度)`，逐层 `faces(">Z").wires().toPending().extrude(...)`。
  - `filename(self, prefix=None, path=None)`、`save_step_file(self, filename=None, path=None, prefix=None)`、`save_stl_file(self, filename=None, path=None, prefix=None, tol=1e-2, ang_tol=0.1)`、`save_svg_file(...)`、`safe_fillet(self, obj, selector, rad)`。
  - `@classmethod to_step_file(cls, length_u, width_u, height_u=None, filename=None, prefix=None, path=None, **kwargs)`、`to_stl_file(...)`、`@staticmethod as_obj(cls, length_u=None, width_u=None, height_u=None, **kwargs)`。
- **`GridfinityBaseplate`（`gf_baseplate.py`）**：签名 `__init__(self, length_u, width_u, **kwargs)`；方法 `_corner_pts(self)`、`render(self)`。参数 `ext_depth=0, straight_bottom=False, corner_screws=False, corner_tab_size=21, csk_hole=5.0, csk_diam=10.0, csk_angle=82`。
- **`GridfinityBox`（`gf_box.py`）**：签名 `__init__(self, length_u, width_u, height_u, **kwargs)`；方法 `render(self)`、`render_shell(self, as_solid=False)`、`render_interior(self, force_solid=False)`、`render_dividers(self)`、`render_scoops(self)`、`render_labels(self)`、`render_holes(self, obj)`、`render_hole_fillers(self, obj)`、`base_interior(self)`、`solid_shell(self)`、`mask_with_obj(self, obj)`、`safe_label_height(self, backwall=False, from_bottom=False)`；属性 `top_ref_height / bin_height / has_dividers / interior_solid`。参数 `holes=False, no_lip=False, lite_style=False, solid=False, solid_ratio=1.0, unsupported_holes=False, scoop_rad=14, label_width=12, label_height=10, label_lip_height=0.8, wall_th=GR_WALL, hole_diam=GR_HOLE_D, length_div=0, width_div=0, fillet_interior=True`。
- **`GridfinitySolidBox(GridfinityBox)`**：`__init__(self, length_u, width_u, height_u, **kwargs)` 强制 `solid=True`。
- `GridfinityDrawerSpacer`、`GridfinityRuggedBox`：抽屉填充与“加固箱”，尺寸常量集中在 `constants.py` 的 `GR_RBOX_* / GR_HINGE_* / GR_LATCH_* / GR_RIB_*` 等，本项目 M1 不涉及，仅作背景。

## 3. 与本项目常量基准的 Cross-check

数据来源 `cqgridfinity/constants.py`（配合 `gf_obj.py` 的 property 公式与 `tests/test_*.py` 断言）。

| 项目 | 本项目基准 | cq-gridfinity 实际值 / 公式 | 结论 |
|---|---|---|---|
| 格距 | 42 mm | `GRU=42`, `GRU2=21`, `GRHU=7`, `GRU_CUT=42.2`(单格外切宽), `GR_TOL=0.5`(外形扣减) | **一致** |
| 底座高 | 4.75 = 0.8+1.8+2.15 | `GR_BASE_HEIGHT=4.75`；但剖面 `GR_BASE_PROFILE=( (GR_BASE_TOP_CHAMF*√2,45), GR_STR_H, (GR_BASE_CHAMF_H*√2,45) )`，其中 `GR_BASE_CHAMF_H=0.98994949/√2≈0.7`、`GR_STR_H=1.8`、`GR_BASE_TOP_CHAMF=4.75-0.7-1.8=2.25`。即 **4.75 = 0.7 + 1.8 + 2.25** | 总高一致；**分段不同**：底倒角 0.7 vs 0.8，顶段 2.25 vs 2.15 |
| 箱体底剖面 | （同上基准） | `GR_BOX_CHAMF_H=1.1313708/√2≈0.8`、`GR_BOX_TOP_CHAMF=4.75-0.8-1.8+GR_BASE_CLR=2.4`、`GR_BOX_PROFILE=((2.4*√2,45),1.8,(0.8*√2,45))` | **另一套分段**：box 用 0.8 倒角、2.4 顶段，且含 `GR_BASE_CLR=0.25` 余隙；baseplate 用 0.7/2.25 |
| 堆叠唇 5 段 | 1.9/1.8/0.7/1.2/1.9，垂直高 8.2 | `GR_LIP_PROFILE=((GR_UNDER_H*√2,45),GR_TOPSIDE_H,(0.7*√2,-45),1.8,(1.3*√2,-45))`，`GR_UNDER_H=1.6`、`GR_TOPSIDE_H=1.2` → 5 段垂直贡献 **1.6/1.2/0.7/1.8/1.3**，`GR_LIP_H=6.6` | **不一致**：顺序与数值都不同；cq 的 `GR_LIP_H=6.6` 用于 `int_height` 计算，本项目 8.2 不对应 |
| 唇径向宽 | 2.6 | `lip_width = GR_UNDER_H + self.wall_th = 1.6+1.0 = 2.6`（`no_lip` 时退化为 `wall_th`） | **一致（默认值下）**，但 cq 是随 `wall_th` 变动的 property，非固定常量 |
| 磁孔孔心 | ±13 mm | `GR_HOLE_DIST=26/2=13`；`hole_centres = [(x*GRU - 13*i, -(y*GRU - 13*j)) for x in range(length_u) for y in range(width_u) for i,j in (-1,1)]` | **一致**：每格 4 孔，相对格心 ±13 |
| 磁孔尺寸 | φ6.5 × 2.4 深 | `GR_HOLE_D=6.5`(=默认 `hole_diam`)、`GR_HOLE_H=2.4`、`GR_BOLT_D=3.0`、`GR_BOLT_H=3.6+GR_HOLE_H=6.0`、`GR_HOLE_SLICE=0.25`；`render_holes()` 用 `.cboreHole(GR_BOLT_D, self.hole_diam, h, depth=GR_BOLT_H)`，即 φ3 通孔 + φ6.5 沉孔深 2.4（无支撑模式 +0.25） | **一致**；孔径可经 `hole_diam` 覆盖（v0.5.6 新增） |
| MAGNET_INSET | 4.8（孔边到格角，不参与定位） | 代码中**无此常量**；定位完全由 `GR_HOLE_DIST=13` 决定 | **本项目特有**，cq 无对应；勿强行映射 |
| 板高 | U×7 mm（3U=21） | `height = 3.8 + GRHU*height_u`（3U 外形 = 24.8 mm，见 `test_solid_box`）；`GR_BOT_H=7`；`top_ref_height=3U → 21`（实心/参考面） | **需澄清**：21 对应本项目基准的“参考高度”，cq 的**外形高度多 3.8 mm 基数** |
| 底板高（测试） | — | `test_baseplate.py`: `GridfinityBaseplate(4,3)` → `size_3d == (168,126,4.75)`；`test_box.py`: `GridfinityBox(2,3,5,no_lip=True)` → `(83.5,125.5,38.8)`；`(1,1,1)` → `(41.5,41.5,10.8)` | 外廓 = `U*42 - 0.5`，高 = `3.8+7U`，可作回归基准 |

**Baseplate vs Box 的磁孔差异（用户特别提示点，已确认）**：
- `README.md` 原文：“The baseplate style ... does not have magnet or mounting holes.”；`gf_baseplate.py` 类 docstring：“it does not include features such as mounting holes, magnet holes, weight slots, etc.”。`GridfinityBaseplate.render()` 只做底座凹槽轮廓 + 可选角部沉头螺钉（`cskHole`），**不调用 `render_holes`，没有磁孔**。
- `GridfinityBox.render()` 中 `if self.holes: r = self.render_holes(r)`，磁孔只属于 Box 系（含 `GridfinitySolidBox`）。抽屉 spacer/rugged box 另有各自逻辑。
- 因此本项目的“底板”若指纯 baseplate，则不应期待磁孔常量参与；磁孔常量属于 bin/box 语义。**这是对照时最易误配的一点**。

**差异原因归纳**：
1. 底座分段 0.7/2.25 与 0.8/2.15 之和相同，属同一 4.75 总高的不同倒角分配（CHANGELOG v0.5.1 “Increased the resolution of the extruded base profile”、v0.5.4 “Optimized the baseplate top height” 表明作者微调过剖面）。
2. Box 与 Baseplate 采用两套剖面，是为给箱体配合留 `GR_BASE_CLR=0.25` 余隙并适配可变壁厚；不是笔误。
3. 唇剖面数值不同：cq 采用 `GR_UNDER_H=1.6 / GR_TOPSIDE_H=1.2` 为骨架的 5 段轮廓（合计 6.6），而本项目基准是另一组（8.2）。两者均是“可配合”的工程近似，不能混用。
4. 高度 3.8 基数来自 cq 把底高/参考面统一到 `GR_BOT_H=7` 的约定，与本项目“U×7=21”的参考面口径不同（21 在 cq 中对应 `top_ref_height`/实心填充高度）。

## 4. 不可照搬的坑

1. **B-Rep ≠ 网格**：CadQuery 的 `Sketch`/`Workplane`/`extrude(taper)`/`shell`/`mirror`/`edges().fillet()`/`cboreHole()` 全部是解析曲面拓扑操作；本项目 manifold3d 是离散三角网格 CSG。倒角/圆角必须显式离散（多边形近似或自己生成截面），`fillet` 无直接等价；`cboreHole` 需自造两级圆柱差集。
2. **锥度挤出长度语义随版本变**：`ZLEN_FIX` 探测表明带 `taper` 的 `extrude` 垂直高度在不同 CadQuery 版本有 `1/cos(taper)` 差异。照抄剖面元组 `(斜边长, 角度)` 而不重新推导垂直/径向分量，会导致底座/唇高度错位。本项目应直接存**垂直高度 + 径向宽度**的显式数值，而非斜边长度+角度。
3. **尺寸配置跨类不统一**：`GR_BASE_PROFILE`(0.7/1.8/2.25) ≠ `GR_BOX_PROFILE`(0.8/1.8/2.4+0.25 余隙)；`lip_width`/`inner_dim`/`safe_fillet_rad`/`under_h` 随 `wall_th`（0.5–2.5，lite≤1.5）动态变化；`hole_diam` 可覆盖 `GR_HOLE_D`。不存在一个“全局唯一剖面”，移植时要按场景分别取值。
4. **高度口径不统一**：`height=3.8+7U`、`top_ref_height`、`int_height = height - GR_LIP_H - GR_BOT_H`、`floor_h = GR_FLOOR - wall_th(lite)` 多套口径并存；测试同时断言外形 38.8 与参考 21。混用会把 3.8 的基数重复计入或漏计。
5. **Baseplate 无磁孔**：见第 3 节；不能把 `render_holes` 逻辑套到底板。
6. **拓扑选择器不可移植**：`VerticalEdgeSelector`/`HasZCoordinateSelector`/`FlatEdgeSelector` 依赖 B-Rep 面边枚举与容差（`tolerance=0.5` / `0.05`），网格上需改按顶点坐标范围筛选，容差语义不同。
7. **测试断言是拓扑计数而非尺寸**：`_faces_match`/`_edges_match`（`tests/common_test.py`，`_almost_same` tol=1e-3）统计面/边数量（如 `>Z` 1 面、`<Z` 6 面、边 16/48/72），这些数字只对 B-Rep 有效，网格模型不能直接搬。
8. **README 与代码个别不一致**：README 参数表写 `scoop_rad=11`，`gf_box.py` 实际默认 `self.scoop_rad=14`（测试里还手动设 20）。提示 README 数值不可尽信，以 `constants.py`/源码为准。

## 5. 许可证与版本

- `LICENSE`：标准 **MIT License**，Copyright (c) 2023 Michael Gale；正文含完整“AS IS”免责声明。`setup.py` 亦声明 `license="MIT"` 与 `License :: OSI Approved :: MIT License`，README badge 为 MIT。
- 版本：`cqgridfinity/__init__.py` 中 `__project__='cqgridfinity'`、`__version__='0.5.7'`（`VERSION = "cqgridfinity-0.5.7"`）；`CHANGELOG.md` 最新条目 v0.5.7（增加 lite scoop、rib-style rugged box、lid window）。
- 各源文件头部有逐文件的 MIT 许可证注释（含 `constants.py`、`gf_*.py`），因此**摘录常量到本项目时建议保留“源自 cq-gridfinity (MIT, Michael Gale, v0.5.7, commit d317286)”的署名注释**以符合 MIT 的署名要求；MIT 允许商用/修改/再分发，无 copyleft 风险。
- 发布渠道：PyPI `cqgridfinity`；仓库 `https://github.com/michaelgale/cq-gridfinity`；作者 michael@fxbricks.com。

## 6. 对本项目 M1 的具体建议

原则：**只取数值与语义，不取代码与依赖**。不引入 CadQuery / OCP / cqkit（会带入数十 MB 原生依赖与 Python 运行时，与 web 项目技术栈冲突）。

建议采纳/交叉验证的常量（在 `cqgridfinity/constants.py`，建议在本项目常量表旁加注释注明第二信源）：
- **可直接确认一致**：`GRU=42`、`GRU2=21`、`GRHU=7`（格距/高度步进）；`GR_BASE_HEIGHT=4.75`；`GR_HOLE_D=6.5`、`GR_HOLE_H=2.4`、`GR_BOLT_D=3.0`、`GR_HOLE_DIST=13`（孔心 ±13）；`lip_width=1.6+wall_th=2.6`（默认壁厚下）；外形公差 `GR_TOL=0.5`、圆角 `GR_RAD=4`、壁厚 `GR_WALL=1.0`。这些数值本项目基准已具备，cq 可作独立交叉验证，无需改动。
- **值得新增到本项目常量表（标注来源）**：`GR_BOT_H=7`（bin 名义底高）、`GR_FLOOR=2.25`（=7−4.75 的底板偏移）、`GR_UNDER_H=1.6`、`GR_TOPSIDE_H=1.2`（唇骨架，正好凑出本项目 LIP_WIDTH=2.6 的推导）、`GR_BASE_CLR=0.25`（配合余隙）、`GR_BOLT_H=6.0`（沉孔总深）、`GR_HOLE_SLICE=0.25`（无支撑孔填充条）、`GR_DIV_WALL=1.2`（分隔壁厚）、`GR_FILLET=1.1`（内圆角）。
- **需要标记为“口径不同、勿直接覆盖”**：底座分段（cq 0.7/1.8/2.25 vs 本项目 0.8/1.8/2.15）、唇 5 段与 `GR_LIP_H=6.6` vs 本项目 8.2、`height=3.8+7U` vs 本项目 U×7。建议在代码中写成两份带名字的 profile（如 `CQ_BASE_PROFILE` 仅作注记），主实现仍用本项目基准，避免误替换。
- **不采纳**：`MAGNET_INSET=4.8` 本项目特有，cq 无对应；不要为了“对齐”而删除或重定义。
- **测试借鉴**：把 `size_3d` 断言改写为本项目网格模型的包围盒断言（baseplate 4×3 → 168×126×4.75；box 2×3×5 → 83.5×125.5×38.8；1×1×1 → 41.5×41.5×10.8），用 tol≈1e-3；面/边计数断言不要照搬。
- **署名合规**：若把上述常量逐条抄入本项目文件，在常量块加一行 `// Derived/cross-checked against cq-gridfinity v0.5.7 (MIT, © 2023 Michael Gale, commit d317286ec15dc52587fadbd4f4c1e13f9cd8a8b2)`；或仅以“数值核对记录”形式保存在文档/测试注释中，不复制代码，风险更低。
- **交付边界**：本审查不改 toolmanagement-web 源码、不做 git 操作；报告落盘于 `.staging/oss/cq-gridfinity.md`，供 M1 常量定值评审引用。
