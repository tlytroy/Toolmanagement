# elalish/manifold 开源库审查报告 —— 对 toolmanagement-web 后端的参考价值

> 审查对象：`elalish/manifold`（C++ 内核 + Python binding `manifold3d`），GitHub 默认分支 `master`。
> 证据基线 commit：`7fae9769195d1d4eccf373cbc0491f754eb6c193`。当前最新 release tag：**v3.5.5**（发布于 2026-11-13，非 prerelease/draft）。
> 本项目（`toolmanagement-web`）已将 `manifold3d` 作为 3D 布尔内核在用；本报告按 6 维度给出核对与补充，供 M1 几何增强参考。
> 取证方式：GitHub MCP `get_file_contents` + `web_fetch` 读取 `README.md`、`LICENSE`、`bindings/python/README.md`、`bindings/python/manifold3d.cpp`、`bindings/python/docstring_override.txt`、`bindings/python/examples/{all_apis,extrude}.py`，并用 `get_latest_release` 查版本。

---

## 1. 定位与技术栈

- **定位**（`README.md`）：专注"流形三角网格（manifold triangle mesh）"的几何库。首要目标 **reliability——保证输出恒为流形、无 caveat/边界情况**；次要目标性能（大量并行/流水线）。这是它作为 CAD 布尔内核的核心卖点，也是它被 OpenSCAD、Blender、trimesh、PyVista、Babylon.js、IFCjs 等大量项目采用的根本原因。
- **核心能力**：
  - 首个"保证流形输出"的 **mesh Boolean（网格布尔）** 算法——这是整个 CAD 内核的基石。
  - OpenSCAD 风格构造器（cube/cylinder/sphere/tetrahedron 等）+ SDF level-set（优于 Marching Cubes）。
  - 任意顶点属性（vertex properties）+ ID 机制（材质/面来源追踪）；`run_*` / `faceID` / `originalID` 字段。
  - 一组平滑/细化函数（refine、smooth_by_normals、calculate_normals 等）。
- **技术栈**：
  - 内核 C++；构建仅依赖 CMake + C++ 编译器 + Python。测试/并行/绑定均为可选依赖，无强制依赖。
  - 可选依赖 CMake flag（`README.md`）：`MANIFOLD_PAR=ON`（TBB 并行）、`MANIFOLD_PYBIND=ON`（Nanobind，Python 绑定）、`MANIFOLD_JSBIND=ON`（Emscripten/WASM）、`MANIFOLD_TEST=ON`（GTest）、`ASSIMP_ENABLE=ON`、`TRACY_ENABLE=ON`。
  - Python 绑定由 **Nanobind** 实现（`bindings/python/manifold3d.cpp`，单文件 ~44 KB），API 通过 **GIL 释放**（`nb::call_guard<nb::gil_scoped_release>`，`using release_gil`）支持并行；`Manifold`/`CrossSection` 对象不可变、可跨线程共享。文档字符串由 `gen_docs.py` 从 C++ 源码注释自动生成到 `autogen_docstrings.inl`（见 `bindings/python/README.md`）。
  - 其它绑定：C（内部）、TS/JS（npm `manifold-3d`）、Java/C#/Julia/Rust/Swift 等（多为外部维护，见 README 绑定表）。
- **重要工程约束**（`README.md` "3D Formats"）：**不要用 STL**——有损、丢失拓扑，重导入后不保证仍流形；推荐 **3MF**（专为实体网格设计）；带顶点属性（法线/UV）用 **glTF + `EXT_mesh_manifold`** 扩展；Python 侧文件 I/O 交给 **trimesh**。

---

## 2. Python binding 目录与核心 API 清单

### 目录结构（`bindings/python/`）
| 文件/目录 | 作用 |
| --- | --- |
| `manifold3d.cpp` | Nanobind 绑定主源码，类/枚举/函数/类型转换全在此 |
| `CMakeLists.txt` | 构建绑定 |
| `gen_docs.py` | 从 C++ 注释/签名生成 `autogen_docstrings.inl`（白名单机制） |
| `docstring_override.txt` | 覆盖 `warp`/`warp_batch` 的 docstring（yaml 风格：`cross_section__warp__warp_func`、`manifold__warp_batch__warp_func` 等键） |
| `stub_pattern.txt` / `stub_postbuild.py` | nanobind stubgen 的 `.pyi` 生成辅助 |
| `README.md` | 绑定说明：`pip install .` 后 `help(manifold3d)`；或 `python -m nanobind.stubgen -m manifold3d -o manifold3d.pyi -i=. -p=bindings/python/stub_pattern.txt` |
| `examples/` | `all_apis.py`（全 API 覆盖测试）、`extrude.py`、`cube_with_dents.py`、`scallop.py`、`bricks.py`、`gyroid_module.py`、`minkowski.py`、`split_cube.py`、`sponge.py`、`maze.py` 等 |
| `tests/` | 单元测试 |

### 全局函数（`manifold3d.cpp`，`m.def` / 命名空间级）
- 精度/细分质量：`set_relative_precision(precision)`、`get_relative_precision()`、`set_min_circular_angle(angle)`、`set_min_circular_edge_length(length)`、`set_circular_segments(number)`、`get_circular_segments(radius)`。
- `triangulate(polygons, epsilon=-1, allow_convex=True)`。

### `Manifold` 类核心方法（签名摘自绑定源码，逐一核对）
- **布尔运算符**：`m1 + m2`（并/Add）、`m1 - m2`（差/Subtract）、`m1 ^ m2`（交/Intersect）——**没有 `.intersect()` 方法**，与本项目已知事实一致（交用 `^`）。
- **拓扑/查询**：`genus()`、`volume()`、`surface_area()`、`is_empty()`、`num_vert()/num_edge()/num_tri()/num_prop()/num_prop_vert()`、`original_id()`、`status()`、`bounding_box()`、`decompose()`、`split(cutter)`、`split_by_plane(normal, origin_offset)`、`trim_by_plane(normal, origin_offset)`、`slice(height) -> CrossSection`、`project() -> CrossSection`。
  - `bounding_box()` 返回**扁平 6 元组** `(xmin, ymin, zmin, xmax, ymax, zmax)`——已核对，与本项目事实一致（源码 lambda 里 `nb::make_tuple(b.min[0], b.min[1], b.min[2], b.max[0], b.max[1], b.max[2])`）。
- **变换（惰性组合）**：`transform(m)`、`translate(t)`、`scale(v)`（向量）与 `scale(s)`（标量重载）、`mirror(v)`、`rotate(v)`（[X,Y,Z] 角度，绑定里去掉了旧的 `rotate(x,y,z)`）、`warp(warp_func)`、`warp_batch(warp_func)`。
- **几何查询（补充）**：`min_gap(other, search_length) -> double`（0..searchLength）、`ray_cast(origin, endpoint)`、`winding_number(points)`、`calculate_curvature(gaussian_idx, mean_idx)`。
- **细化/法线/属性**：`refine(n)`、`refine_to_length(length)`、`refine_to_tolerance(tolerance)`、`simplify(tolerance=0)`、`calculate_normals(normal_idx=0, min_sharp_angle=52.5)`、`smooth_by_normals(normal_idx=0)`、`set_properties(new_num_prop, f)`。
- **凸包**：`hull()`、`batch_hull(manifolds)`（静态方法）、`hull_points(pts)`（静态方法）；`compose(manifolds)` 等价于 `BatchBoolean(manifolds, OpType::Add)`。
- **布尔/批处理**：`batch_boolean(manifolds, op)`（静态，`op` 为 `OpType`，见下）。
- **Minkowski**：`minkowski_sum(other)`、`minkowski_difference(other)`（均 `release_gil`）。
- **构造/工厂（静态）**：`cube(size=(1,1,1), center=False)`、`cylinder(height, radius_low, radius_high=-1, circular_segments=0, center=False)`、`sphere(radius, circular_segments=0)`、`tetrahedron()`、`extrude(crossSection, height, n_divisions=0, twist_degrees=0, scale_top=(1,1))`、`revolve(crossSection, circular_segments=0, revolve_degrees=360)`、`level_set(f, bounds, edgeLength, level=0, tolerance=-1)`（bounds 为 6 元素，同 `bounding_box` 格式）、`reserve_ids(n)`。
- **上下文/取消**：`with_context(ctx)`；`ExecutionContext` 类（`cancel()/cancelled()/progress()`，以及 ctx 版 `from_mesh()`/`level_set()`）。注意 docstring 警告：Python 3.13.8 之前，退出解释器前务必 join 运行这些调用的线程。
- **Mesh 容器**：`Mesh`（`MeshGL`：`vert_properties`/`tri_verts`/`merge_from_vert`/`merge_to_vert`/`run_*`/`face_id`/`halfedge_tangent`，方法 `merge(tolerance=0.0)`、`backside(run)`、`has_normals(run)`）；`Mesh64`（`MeshGL64`，双精度版，索引 `uint64_t`）。

### `CrossSection` 类核心方法
- 构造：`CrossSection(contours)`、`EvenOdd(contours)`、`NonZero(contours)`（静态）。
- 几何/查询：`area()`、`num_vert()`、`num_contour()`、`is_empty()`、`bounds()`、`to_polygons()`、`decompose()`。
  - `bounds()` 返回**扁平 4 元组** `(min_x, min_y, max_x, max_y)`——已核对，与本项目事实一致（源码 `nb::make_tuple(r.min[0], r.min[1], r.max[0], r.max[1])`）。
- 变换：`translate(v)`、`rotate(degrees)`、`scale(v)`/`scale(s)`、`mirror(ax)`、`transform(m)`（`2x3` 矩阵）、`warp(f)`、`warp_batch(f)`。
- **偏移/圆角（关键）**：`offset(delta, join_type=JoinType.Round, miter_limit=2.0, circular_segments=0)`。
  - `JoinType`：`Square`、`Round`、`Miter`、`Bevel`（语义见 `manifold3d.cpp` 枚举 docstring；Round 保持精确 offset 距离，Miter 超限时退化为 Square，Bevel 最快）。
- 布尔：`+`/`-`/`^`（同样无 `.intersect()`）、`batch_boolean(cross_sections, op)`（静态）、`hull()`、`batch_hull(cross_sections)`、`hull_points(pts)`。
- 其它：`simplify(tolerance=0)`、`extrude(height, n_divisions=0, twist_degrees=0, scale_top=(1,1))`、`revolve(circular_segments=0, revolve_degrees=360)`、`square(size, center=False)`、`circle(radius, circular_segments=0)`（静态）。

### 枚举
- `OpType`：`Add`、`Subtract`、`Intersect`（`batch_boolean` 用）。
- `Error`：`NoError`、`NonFiniteVertex`、`NotManifold`、`VertexOutOfBounds`、`PropertiesWrongLength`、`MissingPositionProperties`、`MergeVectorsDifferentLengths`、`MergeIndexOutOfBounds`、`TransformWrongLength`、`RunIndexWrongLength`、`FaceIDWrongLength`、`InvalidConstruction`、`ResultTooLarge`、`InvalidTangents`、`Cancelled`。
- `RayHit`：`face_id`、`distance`、`position`、`normal`、`crossing`（只读属性）。

> 参考：`bindings/python/examples/all_apis.py` 是一份"全 API 语法速查"，上面列出的绝大多数方法都有单行调用样例，可直接作为本项目写绑定封装时的模板。

---

## 3. 值得深入的机制

### 3.1 batch boolean（批量布尔）
- 签名：`Manifold.batch_boolean(manifolds, op)` / `CrossSection.batch_boolean(cross_sections, op)`，`op` ∈ `OpType.{Add, Subtract, Intersect}`；静态 `compose(manifolds)` = `BatchBoolean(..., Add)`。
- 价值：把 N 个输入的并/差/交一次性在 CSG 树里归并，比逐个 `+`/`-`/`^` 链式调用减少中间网格重建次数，对"手孔阵列""成组槽/孔切入主体"这类场景是关键性能优化。`all_apis.py` 中的样例：
  ```python
  m = Manifold.batch_boolean([
      Manifold.cylinder(4, 1),
      Manifold.cube((3, 2, 1)),
      Manifold.cylinder(5, 3).translate((1, 1, 1)),
  ], OpType.Add)
  ```
- **正确写法要点**：`Subtract` 时必须把"主体"放第一个、后续全是被减体（语义同 OpenSCAD difference）；`Intersect` 会取所有输入公共部分。相对链式 `a - b - c`，batch 版本能降低误差累积与临时对象数量。

### 3.2 拓扑有效性 `status()`
- `status() -> Error`（`nb::self.status`，`release_gil()`）。返回 `Error.NoError` 表示流形有效；非流形输入、越界/非有限顶点、属性长度错、构造非法、结果过大、被 `ExecutionContext` 取消等分别对应枚举值。
- 建议：本项目在每次布尔/offset 后对结果调用 `status()` 做**断言式校验**，并把非 `NoError` 当作几何失败上抛；不要只看 `volume()>0`。
- 与 `ExecutionContext` 配合：`with_context(ctx)` 可让 `status()` / `refine*()` / `minkowski*()` / `hull()` 上报进度、并被另一线程 `cancel()`；`all_apis.py` 验证了预取消 ctx 下 `tree.status() == Error.Cancelled`。适合后端对"大批量布尔/细化"Job 做超时取消。

### 3.3 `genus()`（亏格/欧拉拓扑指纹）
- `genus() -> int`（`Manifold::Genus`）。亏格 = 拓扑"手柄"数（球体 0，环面 1）。
- 价值：几何完整性/带孔性校验——例如"手孔是否真的贯穿（形成手柄/通孔）"、去内腔、检测布尔意外产生的碎裂/多余腔体。可与 `volume()`、`num_tri()`、`status()` 组合成几何体检指标。

### 3.4 `min_gap()`
- `min_gap(other, search_length) -> double`，返回 0..searchLength 的最小间距（`manifold3d.cpp` 注释："Returns the minimum gap between two manifolds. Returns a double between 0 and searchLength."）。
- 价值：装配/间隙校验——手孔与紧固件间隙、倒角后壁厚、两零件最小安全距离；`search_length` 是搜索上限，超过即返回该上限（可用作"至少间隔 X"的快速判定）。样例：`d = m.min_gap(m2, 2)`（`all_apis.py`）。

### 3.5 CrossSection `offset` / 圆角（本项目倒角方案的核心）
- `offset(delta, join_type=JoinType.Round, miter_limit=2.0, circular_segments=0)`：对 2D 轮廓做等距偏移；`delta<0` 内缩、`delta>0` 外扩。
- 圆角机制：用 `JoinType.Round` + 内缩 `delta = r`（圆角半径），把外凸角变成半径 r 的圆角；`circular_segments` 控制圆弧细分（默认 0 = 用 `get_circular_segments` 的质量设定）。内凹角则相应变为反向圆角。
- 重要：`docstring_override.txt` 明确 `warp`/`warp_batch` 后需要 union 来消除自交——`CrossSection.warp` 的 docstring："followed by a union operation (with a Positive fill rule) that ensures any introduced intersections are not included in the result"；而 `Manifold.warp` 的 docstring 警告"不检查重叠，由用户自行保证"（`This function does not change the topology ... it is up to the user to choose their function with discretion`）。做非等距变形时优先用 CrossSection.warp。

---

## 4. 已知坑 / 限制

1. **`scale_top` 只是顶点缩放，不是真 loft**（与本项目事实一致）：`extrude(..., scale_top=(sx, sy))` 和 `CrossSection.extrude(...)` 把顶层顶点按 (sx, sy) 仿射缩放 + `twist_degrees` 扭转、`n_divisions` 分段。它只对**单一轮廓**做线性插值，无法在两个**不同形状**的截面间做真正的放样（loft）；锥台靠"底面圆 + scale_top<1"近似可行，但任意异形截面过渡做不到。复杂过渡应改用 `hull`/逐层 `slice`+`revolve` 或外部 loft 后处理。
2. **容差/epsilon**：内部用 `Quality::SetRelativePrecision`、`Epsilon()`；`volume()/surface_area()` 文档注明"面在 Epsilon() 内则被 clamp 到零"（"This is clamped to zero for a given face if they are within the Epsilon()"）。`offset` 的 `miter_limit=2.0` 会在尖角超限处退化为 Square；`simplify(tolerance)`、`refine_to_tolerance`、`MeshGL.merge(tolerance)` 都涉及容差选择。相对精度过松会吞掉薄壁/小孔，过紧会放大浮点误差——需按本项目单位尺度标定。
3. **与 trimesh 的边界**（README 明确）：
   - Manifold 要求输入网格本身流形；`Merge()` 只能修轻微非流形，通常需要专门的 3D 打印修复工具。直接用 `trimesh` 导入的脏网格构造 `Manifold(mesh)` 会得到 `status() != NoError`。
   - 格式权衡：**避免 STL**（有损、丢拓扑）；实体用 3MF，带属性用 glTF + `EXT_mesh_manifold`；文件 I/O 交给 trimesh。边界在于"Manifold 只保证布尔/拓扑，不负责通用格式读写/修复"。
   - 数据接口：`MeshGL.vert_properties` 是 float32，NDArray 视图；导出到 trimesh 时注意 dtype/列数（至少 3 列）与属性语义（颜色/UV 需自行解释）。
4. **版本/API 兼容**：
   - 当前 release **v3.5.5**（2026-11-13）。近期变更含：Python 3.15 wheels（cibuildwheel 4.x）、Windows Arm64、多项 Python 入参校验修复（错误类型 vec/mat 导致 abort、越界参数崩溃修复、`set_properties` 负数现在返回 `InvalidConstruction` 而非 Python 抛错、不导出静态链接的 manifold/TBB 符号）。
   - `rotate(v)` 现为向量形式（内部 `self.Rotate(v.x, v.y, v.z)`），旧的 `rotate(x,y,z)` 已被替换/拼接 docstring——升级时注意调用签名。
   - `ExecutionContext` docstring：Python < 3.13.8 时，含 ctx 的长耗时调用线程必须在解释器退出前 join，否则有崩溃风险。
   - 精度/构造错误从"Python 抛异常"转向"返回 Error 枚举"的趋势（如 `set_properties` 负数）——校验策略应对齐 `status()`/`Error`，而非仅依赖 try/except。
5. **其它**：WASM 构建为 serial-only（且不建议在 Emscripten 下开 `MANIFOLD_PAR=ON`，有内存损坏风险）；内置 TBB（`MANIFOLD_USE_BUILTIN_TBB`）会与项目自带 TBB 冲突，Windows 构建建议 `-DBUILD_SHARED_LIBS=OFF`。这两点对本后端（本地 Python binding）影响有限，但 CI/部署需留意。

---

## 5. 许可证与版本

- **License：Apache License 2.0**（`LICENSE`，标准全文）。要点：
  - 第 2 条授予永久、全球、非独占、免费、不可撤销的**版权许可**（复制、衍生、展示、再许可、分发）。
  - 第 3 条授予**专利许可**，但若你对本项目提起专利诉讼（含反诉）主张该 Work/Contribution 侵权，则专利许可自动终止。
  - 第 4 条再分发条件：随附 License 副本；修改文件加显著变更说明；保留源文件中的版权/专利/商标/归属声明；若有 NOTICE 文件则衍生作品需包含其归属声明。
  - 第 7/8 条：**"AS IS" 无担保**、免责声明；责任限制。
  - **对本项目结论**：Apache-2.0 属宽松许可，商用/闭源衍生允许，只要保留版权与 License 副本、标注修改即可；专利授权对工程落地友好。建议在 `toolmanagement-web` 的依赖清单/版权页标注 manifold3d 的 Apache-2.0 归属，并保留其 LICENSE/NOTICE。
- **版本**：最新稳定 release tag **v3.5.5**（`get_latest_release`，`published_at 2026-11-13T02:30:47Z`，author zmerlynn；`prerelease=false`、`draft=false`）。README 徽章指向 PyPI `manifold3d` / npm `manifold-3d`。默认分支 `master` 当前 HEAD `7fae976…`。建议后端 `requirements` 固定到与 v3.5.5 对应的 `manifold3d` 版本并锁 minor，避免上述 API 变更漂移。

---

## 6. 对本项目 M1 几何增强的具体建议

> 目标：在 `toolmanagement-web` 后端用现有 `manifold3d` 能力实现"倒角锥台、手孔、batch boolean"三类 M1 几何增强。以下均基于本节核对过的真实签名。

### 6.1 倒角（chamfer）/ 圆角锥台
- **两种语义，别混淆**：
  - **圆角（fillet/round）**：对 2D 轮廓 `CrossSection.offset(-r, JoinType.Round)` 内缩 r 得到圆角轮廓，再 `extrude(height)`；或先用 `Manifold.minkowski_difference(sphere(r))` 做整体圆角（见 `minkowski.py` 示例，`release_gil` 长任务）。
  - **倒角（chamfer，斜切）**：用 `Extrude` 的 `scale_top` + `n_divisions=1` 做锥台；真正的 45° 倒角应对**截面**做 `offset(delta)` 分层或用 `JoinType.Bevel`/`Square` 生成斜边轮廓。
- **锥台（frustum）推荐写法**（已核对签名）：
  ```python
  from manifold3d import CrossSection, Manifold
  base = CrossSection.circle(radius_low)              # 或 square/polygon
  frustum = Manifold.extrude(
      base, height=h, n_divisions=1,
      scale_top=(radius_high / radius_low, radius_high / radius_low),
  )
  ```
  或 `m = base.extrude(h, scale_top=(s, s))`（实例方法，签名相同）。**注意**：`scale_top` 是"顶层顶点按 (sx,sy) 仿射缩放"，仅对底面轮廓等比缩放有效；若底/顶形状不同，须用 `hull`/`revolve`/`min_gap` 等组合，不要指望 loft。
- **本项目既有"offset(eff, JoinType.Round) + scale_top 仿射"的倒角方案是正确方向**：先用 `offset(-eff, Round)` 处理 2D 轮廓的凸角圆滑，再用 `scale_top` 做锥度；记得按 4 节所述设定 `circular_segments` 与相对精度，避免圆角被 epsilon 吞掉。
- 校验：倒角后 `status()==NoError`、`genus()` 与预期一致、`volume()` 在合理区间、`bounding_box()` 符合尺寸。

### 6.2 手孔（through hole / 带沉孔）
- **通孔**：`main - cutter`，cutter 高度为 `h + 2*margin`、沿法线两端各外伸 margin，保证完全贯穿：
  ```python
  cutter = Manifold.cylinder(h + 2*margin, r).translate((x, y, -margin))
  part = body - cutter
  ```
- **沉孔/阶梯孔（counterbore）**：用两个不同半径/深度的圆柱并集做 cutter：
  ```python
  cutter = Manifold.cylinder(shank_h, r_small).translate((x,y,-m)) \
         + Manifold.cylinder(counter_h, r_big).translate((x,y,shank_h))
  part = body - cutter
  ```
  或用 `CrossSection` 画阶梯轮廓后 `revolve`/`extrude`。**务必**在操作后 `status()`——若 cutter 与 body 恰好相切/共面，可能触发非流形或精度问题，margin 消除共面。
- **贯穿验证**：`genus()` 每贯穿一个孔 +1；配合 `min_gap()` 检查孔壁与零件边缘/相邻孔的最小壁厚是否满足工艺要求。
- **圆角孔口**：对孔内缩做 `offset(delta, JoinType.Round)` 或用 `minkowski_difference` 对孔口倒圆（成本较高，注意 GIL 释放与取消）。

### 6.3 batch boolean 的正确用法（性能与精度）
- **成组孔/槽一次性切**：把所有 cutter 收进列表，一次 `Manifold.batch_boolean([body, *cutters], OpType.Subtract)`，而不是 `for c in cutters: body = body - c`。减少中间 CSG 节点与网格重建，误差累积更小：
  ```python
  ops = [body] + [Manifold.cylinder(...).translate(pos) for pos in holes]
  part = Manifold.batch_boolean(ops, OpType.Subtract)
  assert part.status() == Error.NoError
  ```
- **Add/Intersect 同理**：`OpType.Add` 可用 `compose([...])` 简写；`OpType.Intersect` 取公共区（本项目无 `.intersect()`，batch 版也不提供该方法名，走 `OpType.Intersect` 或 `^`）。
- **2D 端同样适用**：`CrossSection.batch_boolean([...], OpType.Add/Subtract/Intersect)` 在拉伸前合并轮廓，能减少 `extrude` 次数。
- **长任务取消**：把批量布尔包进 `ExecutionContext`，`part = Manifold.batch_boolean(...).with_context(ctx)`，后台线程可 `ctx.cancel()`；后端据此实现 Job 超时/取消（注意 Python <3.13.8 退出前 join 线程）。
- **精度与顺序**：`batch_boolean` 对输入同质性敏感——所有输入都应流形、单位一致、避免共面重叠；若发现失败，先用 `status()` 定位，再考虑微调尺寸/容差（`set_relative_precision`）或拆分为多次布尔。

### 6.4 落地优先级建议
1. P0：封装统一几何工厂，所有几何产出强制 `status()==NoError` 校验 + `bounding_box()`/`genus()`/`volume()` 记录，接入日志。
2. P0：用 `batch_boolean` 重构现有成组孔/槽切除，量化提速与失败率。
3. P1：倒角锥台/圆角方案固化为"CrossSection.offset + Extrude.scale_top"工具函数，参数化半径/锥度/分段，并写单测覆盖 `genus()`/尺寸。
4. P1：锁 `manifold3d==<v3.5.5对应版本>`，把 API 变更（`rotate(v)`、错误以 `Error` 返回、ctx 线程 join 规则）纳入升级 checklist。
5. P2：许可合规——依赖页/版权页标注 Apache-2.0 归属，保留 LICENSE/NOTICE，修改处加变更说明。

---

## 证据索引（URL）
- README：https://github.com/elalish/manifold/blob/master/README.md
- LICENSE：https://github.com/elalish/manifold/blob/master/LICENSE
- Python 绑定主源码：https://github.com/elalish/manifold/blob/master/bindings/python/manifold3d.cpp
- Python 绑定说明：https://github.com/elalish/manifold/blob/master/bindings/python/README.md
- docstring 覆盖：https://github.com/elalish/manifold/blob/master/bindings/python/docstring_override.txt
- 全 API 示例：https://github.com/elalish/manifold/blob/master/bindings/python/examples/all_apis.py
- extrude 示例：https://github.com/elalish/manifold/blob/master/bindings/python/examples/extrude.py
- 最新版本 release：https://github.com/elalish/manifold/releases/tag/v3.5.5
