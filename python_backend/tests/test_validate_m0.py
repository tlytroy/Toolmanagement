"""M0 路 C：0.7 `geometry/validate.py` 的 DoD。

★ 这个文件的存在理由只有一条：**证明自检不是恒真**。
  一个「永远返回全绿」的校验器也能让 ②（正常板体全绿）通过，
  所以每条断言都必须配一个**必须判红**的反例：

  ① 两个重叠立方体的手工拼接 union → 必须判失败（`components` + `self_intersection`）
  ② 正常板体 + 正常槽 → 全绿
  ③ 板体缩放 1.1 倍 → `volume_match` 必须红（且只是 advisory，不阻断）
  ④ genus：盲槽 = 0，贯穿孔 = 1（且给错期望值时必须红）
  ⑤ 合法内部空腔**不得**被误判成「实体重叠」（负交集 ≠ 正交集）
  ⑥ 非流形（删面）→ `manifold_status` 必须红
  ⑦ L0：自交多边形 → `shapely_valid` 红；退化零面积 → `area_positive` 红

★ 每条「必须红」的断言都同时断言了 **是哪一条 check 红**，而不是只断言「有红的」。
  否则 `volume_match` 红了也会让重叠立方体用例通过，判据就串味了。

运行（项目根下）：
    .venv/bin/python -m pytest -q python_backend/tests/test_validate_m0.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import manifold3d as mf
import numpy as np
import pytest
import trimesh
from shapely.geometry import Polygon

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from domain.models import BoardConfig, Project, Tool, Vec2  # noqa: E402
from geometry import generate_insert  # noqa: E402
from geometry.validate import (  # noqa: E402
    ADVISORY_CHECKS,
    BLOCKING_CHECKS,
    CheckResult,
    MIN_RIB_MM,
    VOLUME_TOLERANCE,
    assert_all_ok,
    summarize,
    validate_2d,
    validate_3d,
)

PAPER_W, PAPER_H = 210.0, 297.0


# ---------------------------------------------------------------- helpers
def _mesh_of(m) -> tuple[np.ndarray, np.ndarray]:
    me = m.to_mesh()
    return (np.asarray(me.vert_properties)[:, :3].astype(float),
            np.asarray(me.tri_verts))


def _stitch(*parts) -> mf.Manifold:
    """把若干 `Manifold` 的三角面**手工拼**成一张网格（不求并！）。

    ★ 这是 0.7 DoD ① 的关键：`a.compose([b])` / `a + b` 会**真的求并**，
      重叠区被消掉、`decompose()` 只剩 1 个分量，重叠就再也查不出来。
      必须走 `mf.Mesh(vert_properties=vstack, tri_verts=vstack)` 才能造出
      「两张壳在空间上叠在一起、但拓扑上互不相连」的病态实体。
    """
    vs, fs, offset = [], [], 0
    for p in parts:
        v, f = _mesh_of(p)
        vs.append(v)
        fs.append(f + offset)
        offset += len(v)
    return mf.Manifold(mf.Mesh(
        vert_properties=np.vstack(vs).astype(np.float32),
        tri_verts=np.vstack(fs).astype(np.uint32),
    ))


def _by_name(results, name: str):
    for r in results:
        if r.name == name:
            return r
    raise AssertionError(f"缺少 check {name}，实际有 {[r.name for r in results]}")


def _board_manifold(w: float = 100.0, h: float = 100.0, t: float = 12.0) -> mf.Manifold:
    ring = np.array([(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)])
    return mf.Manifold.extrude(mf.CrossSection([ring]), t)


def _slot_cutter(w: float = 20.0, h: float = 10.0, depth: float = 9.0,
                 z0: float = 4.0) -> mf.Manifold:
    ring = np.array([(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)])
    return mf.Manifold.extrude(mf.CrossSection([ring]), depth).translate((0.0, 0.0, z0))


def _rect(cx: float, cy: float, w: float, h: float) -> list[Vec2]:
    hw, hh = w / 2.0, h / 2.0
    return [Vec2(cx - hw, cy - hh), Vec2(cx + hw, cy - hh),
            Vec2(cx + hw, cy + hh), Vec2(cx - hw, cy + hh)]


def _golden_board() -> BoardConfig:
    return BoardConfig(size_mode="fit-tools", margin=12.0, thickness=12,
                       corner_r=5.0, embed_depth=8.0, clearance=0.0, slot_chamfer=0.0)


# ---------------------------------------------------------------- ① 重叠立方体
def test_overlap_union_is_rejected() -> None:
    """DoD ①：两个重叠立方体的 union 必须被判**失败**。

    ★ 先证「常规谓词抓不到」，再证「本模块抓得到」—— 前者是后者的存在理由。
    """
    a = mf.Manifold.cube((10.0, 10.0, 10.0))
    b = mf.Manifold.cube((10.0, 10.0, 10.0)).translate((5.0, 5.0, 5.0))  # 重叠 5mm
    bad = _stitch(a, b)

    # —— 第一步：常规谓词全是绿的（这就是为什么需要 components / self_intersection）——
    mesh = trimesh.Trimesh(
        vertices=np.asarray(bad.to_mesh().vert_properties)[:, :3].astype(float),
        faces=np.asarray(bad.to_mesh().tri_verts), process=False)
    assert bad.status() == mf.Error.NoError, "前提变了：status 不再是 NoError"
    assert mesh.is_watertight, "前提变了：拼接网格不再水密"
    assert mesh.is_winding_consistent, "前提变了：绕向不再一致"

    # —— 第二步：本模块必须判红 ——
    results = validate_3d(bad, label="overlap")
    summary = summarize(results)
    assert not summary["ok"], "重叠立方体被判为全绿 —— 校验器是恒真的"
    assert summary["blocking"], "重叠立方体没有产生阻断项"

    comp = _by_name(results, "components")
    assert not comp.ok, "components 没抓到重叠"
    assert comp.detail["count"] == 2

    inter = _by_name(results, "self_intersection")
    assert not inter.ok, "self_intersection 没抓到重叠"
    assert inter.detail["overlaps"], "overlaps 列表为空"
    # 5mm 重叠的两块 10³ 立方体，交集是 5×5×5 = 125
    assert abs(inter.detail["overlaps"][0]["intersectionMm3"] - 125.0) < 1e-6


def test_touching_faces_are_not_reported_as_overlap() -> None:
    """面贴面（交集体积 = 0）不是重叠 —— 但仍是两个实体，`components` 该红。

    ★ 这条防「把贴合误报成重叠」：`min_gap` 对贴合返回 0.0、对重叠也返回 0.0，
      分不开；只有**交集体积**分得开。
    """
    a = mf.Manifold.cube((10.0, 10.0, 10.0))
    b = mf.Manifold.cube((10.0, 10.0, 10.0)).translate((10.0, 0.0, 0.0))
    touching = _stitch(a, b)
    results = validate_3d(touching, label="touching")
    assert _by_name(results, "self_intersection").ok, "面贴合被误报成实体重叠"
    assert not _by_name(results, "components").ok, "两块贴合实体应算 2 个分量"


def test_disjoint_solids_are_rejected_as_multiple_components() -> None:
    """两个**分离**实体也必须是失败（一个嵌件不能是两块料）。"""
    a = mf.Manifold.cube((10.0, 10.0, 10.0))
    b = mf.Manifold.cube((10.0, 10.0, 10.0)).translate((50.0, 0.0, 0.0))
    results = validate_3d(_stitch(a, b), label="disjoint")
    assert not _by_name(results, "components").ok
    assert _by_name(results, "self_intersection").ok
    assert summarize(results)["blocking"]


def test_internal_cavity_is_legal_not_overlap() -> None:
    """合法内部空腔**不得**被判成重叠 —— 这是「宁可漏判也别误杀」的反向锚。

    ★ 实测：`board - 内腔` 的 `decompose()` 给出 `[8000, -1000]`，
      **空腔体积为负**，两者交集也是 **-1000**。
      若把 `> 0` 写成 `!= 0`，合法空腔会被判死。
    """
    outer = mf.Manifold.cube((20.0, 20.0, 20.0))
    inner = mf.Manifold.cube((10.0, 10.0, 10.0)).translate((5.0, 5.0, 5.0))
    cavity = outer - inner

    parts = cavity.decompose()
    assert len(parts) == 2, "前提变了：空腔不再产生 2 个 decompose 分量"
    volumes = sorted(float(p.volume()) for p in parts)
    assert volumes[0] < 0.0, f"前提变了：空腔不再是负体积 {volumes}"

    results = validate_3d(cavity, label="cavity")
    assert _by_name(results, "self_intersection").ok, "合法空腔被误判成实体重叠"
    assert _by_name(results, "components").ok, "合法空腔被数成 2 个实体"


# ---------------------------------------------------------------- ② 正常板体
def test_normal_board_and_slot_all_green() -> None:
    """DoD ②：正常板体 + 正常槽 → 全绿（且 checks 一个都不少）。"""
    board = _board_manifold(100.0, 100.0, 12.0)
    # 盲槽：切刀 z ∈ [4, 13]，板 z ∈ [0, 12] → **实际切除深度只有 8**（4..12）。
    # ★ 解析解必须按「切刀 ∩ 板」算，不能拿切刀自己的 depth=9 去算，
    #   否则 1mm 的系统偏差会被误当成浮点误差（实测 relerr 0.169%）。
    result = board - _slot_cutter(20.0, 10.0, depth=9.0, z0=4.0)

    expected = 100.0 * 100.0 * 12.0 - 20.0 * 10.0 * 8.0
    results = validate_3d(result, expected_volume=expected, expected_genus=0,
                          label="board+slot")
    summary = summarize(results)
    assert summary["ok"], f"正常件被判失败：{summary['failed']}\n{results}"
    assert summary["blocking"] is False

    # 六条必需的 check 一条都不能少（少了等于静默跳过）
    names = {r.name for r in results}
    assert {"manifold_status", "watertight", "winding",
            "components", "self_intersection", "genus", "volume_match"} <= names

    # volume_match 的相对误差应该很小（这条防「expected 被当成 actual」）
    vm = _by_name(results, "volume_match")
    assert vm.detail["relativeError"] < 1e-6
    assert abs(vm.detail["actualMm3"] - expected) < 1e-6


def test_normal_generate_insert_output_all_green() -> None:
    """真实 `generate_insert` 的产出必须全绿（不是只对手搓的立方体成立）。"""
    tools = [Tool(id="t1", outer=_rect(PAPER_W / 2, PAPER_H / 2, 100.0, 60.0))]
    board = _golden_board()
    result = generate_insert(Project(tools=tools, board=board))

    board_vol = result["base_uncut"].volume()
    slot_vol = board_vol - result["base"].volume()
    results = validate_3d(
        result["base"],
        expected_volume=board_vol - slot_vol,
        expected_genus=0,
        label="generate_insert",
    )
    assert summarize(results)["ok"], f"{[r for r in results if not r.ok]}"
    # 顺带证明 base_uncut 自己也干净
    assert summarize(validate_3d(result["base_uncut"], label="uncut"))["ok"]


def test_checkresult_to_dict_matches_sds_shape() -> None:
    """`CheckResult.to_dict()` 必须给出 SDS §4.5 的 `{id, ok, ...}` 形状。"""
    d = CheckResult("min_rib", False, {"minMm": 1.2}).to_dict()
    assert d["id"] == "min_rib"
    assert d["ok"] is False
    assert d["minMm"] == 1.2
    # 用 summarize 汇出来的 checks 也必须是同一形状
    payload = summarize([CheckResult("watertight", True, {})])
    assert payload["checks"] == [{"id": "watertight", "ok": True}]


def test_blocking_and_advisory_sets_match_sds() -> None:
    """阻断/建议的分类必须与 SDS §4.5 一致（且不重叠）。"""
    assert BLOCKING_CHECKS & ADVISORY_CHECKS == frozenset()
    for name in ("shapely_valid", "watertight", "winding", "manifold_status"):
        assert name in BLOCKING_CHECKS
    for name in ("genus", "volume_match", "min_rib"):
        assert name in ADVISORY_CHECKS
    assert MIN_RIB_MM == 2.0
    assert VOLUME_TOLERANCE == 0.02


# ---------------------------------------------------------------- ③ 缩放 1.1
def test_scaled_board_fails_volume_match() -> None:
    """DoD ③：板体缩放 1.1 倍 → `volume_match` 必须红，且只是 advisory。"""
    board = _board_manifold(100.0, 100.0, 12.0)
    truth = float(board.volume())

    # 先证原样是绿的
    assert _by_name(validate_3d(board, expected_volume=truth), "volume_match").ok

    scaled = board.scale((1.1, 1.1, 1.1))
    results = validate_3d(scaled, expected_volume=truth, label="scaled1.1")
    vm = _by_name(results, "volume_match")
    assert not vm.ok, "缩放 1.1 倍后 volume_match 仍然是绿的"
    # 1.1^3 = 1.331，相对误差应约 33.1%
    assert abs(vm.detail["relativeError"] - 0.331) < 0.01
    assert abs(vm.detail["actualMm3"] / truth - 1.331) < 1e-6

    # volume_match 是 advisory：不进阻断集合
    summary = summarize(results)
    assert not summary["ok"]
    assert "volume_match" in summary["advisoryFailed"]
    assert not summary["blocking"], "volume_match 不该阻断"


def test_volume_tolerance_is_two_percent_not_looser() -> None:
    """±2% 的边界要**卡死**：1.9% 绿、2.1% 红（防有人偷偷放宽容差）。"""
    cube = mf.Manifold.cube((10.0, 10.0, 10.0))
    truth = 1000.0

    ok_case = validate_3d(cube, expected_volume=truth / 1.019)
    assert _by_name(ok_case, "volume_match").ok, "1.9% 误差不该红"

    bad_case = validate_3d(cube, expected_volume=truth / 1.021)
    assert not _by_name(bad_case, "volume_match").ok, "2.1% 误差必须红"


# ---------------------------------------------------------------- ④ genus
def test_genus_blind_slot_is_zero() -> None:
    """DoD ④：开 1 个盲槽的板 = genus 0（盲槽不增加亏格）。"""
    board = _board_manifold(100.0, 100.0, 12.0)
    blind = board - _slot_cutter(20.0, 10.0, depth=9.0, z0=4.0)  # 槽底 z=4 > 0，不通
    g = _by_name(validate_3d(blind, expected_genus=0), "genus")
    assert g.ok and g.detail["genus"] == 0

    # 给错期望值时必须红（证明不是恒真）
    wrong = _by_name(validate_3d(blind, expected_genus=1), "genus")
    assert not wrong.ok


def test_genus_through_hole_is_one() -> None:
    """DoD ④：开 1 个贯穿孔的板 = genus 1。"""
    board = _board_manifold(100.0, 100.0, 12.0)
    through = board - _slot_cutter(20.0, 10.0, depth=20.0, z0=-4.0)  # z 从 -4 到 16，穿
    g = _by_name(validate_3d(through, expected_genus=1), "genus")
    assert g.ok and g.detail["genus"] == 1

    assert not _by_name(validate_3d(through, expected_genus=0), "genus").ok
    assert not _by_name(validate_3d(through, expected_genus=2), "genus").ok


def test_genus_two_through_holes_is_two() -> None:
    """两个贯穿孔 → genus 2（防「genus 只认 0/1 两档」的假实现）。

    ★ 第二个孔必须**完全落在板内**：若它碰到板边（x 跨到 ±50），
      孔就变成「缺口」而不是「通孔」，genus 仍是 1 —— 实测踩过这个坑。
    """
    board = _board_manifold(100.0, 100.0, 12.0)   # x ∈ [-50, 50]
    two = (board
           - _slot_cutter(20.0, 10.0, depth=20.0, z0=-4.0)            # x ∈ [-10, 10]
           - _slot_cutter(20.0, 10.0, depth=20.0, z0=-4.0).translate((30.0, 0.0, 0.0)))
    #                                                              # x ∈ [ 20, 40]
    g = _by_name(validate_3d(two, expected_genus=2), "genus")
    assert g.ok and g.detail["genus"] == 2


def test_hole_touching_board_edge_is_not_a_through_hole() -> None:
    """孔碰到板边 → 是缺口不是通孔，genus 仍为 1（上一条的前提自检）。"""
    board = _board_manifold(100.0, 100.0, 12.0)
    notch = (board
             - _slot_cutter(20.0, 10.0, depth=20.0, z0=-4.0)
             - _slot_cutter(20.0, 10.0, depth=20.0, z0=-4.0).translate((40.0, 0.0, 0.0)))
    #                                                    x ∈ [30, 50] → 恰好切到板边
    g = _by_name(validate_3d(notch, expected_genus=1), "genus")
    assert g.ok and g.detail["genus"] == 1


# ---------------------------------------------------------------- ⑤ 非流形
def test_non_manifold_mesh_fails_status() -> None:
    """删掉两个面造开口盒 → `manifold_status` 必须红。"""
    box = trimesh.creation.box(extents=[10.0, 10.0, 10.0])
    box.faces = box.faces[:-2]
    broken = mf.Manifold(mf.Mesh(
        vert_properties=np.asarray(box.vertices, dtype=np.float32),
        tri_verts=np.asarray(box.faces, dtype=np.uint32),
    ))
    assert broken.status() != mf.Error.NoError, "前提变了：删面后 status 仍是 NoError"
    results = validate_3d(broken, label="open_box")
    assert not _by_name(results, "manifold_status").ok
    assert summarize(results)["blocking"]


# ---------------------------------------------------------------- ⑥ L0：2D
def test_l0_valid_polygon_is_green() -> None:
    """正常矩形 → `shapely_valid` + `area_positive` 全绿。"""
    poly = Polygon([(0, 0), (100, 0), (100, 60), (0, 60)])
    results = validate_2d(poly, label="rect")
    assert_all_ok(results, label="rect")
    assert _by_name(results, "area_positive").detail["areaMm2"] == 6000.0


def test_l0_self_intersecting_polygon_is_red() -> None:
    """自交（bowtie）→ `shapely_valid` 必须红，且 detail 里带 explain_validity。"""
    bowtie = Polygon([(0, 0), (60, 60), (60, 0), (0, 60)])
    assert not bowtie.is_valid, "前提变了：bowtie 变成合法多边形"
    results = validate_2d(bowtie, label="bowtie")
    valid = _by_name(results, "shapely_valid")
    assert not valid.ok, "自交多边形被判合法"
    assert "Self-intersection" in valid.detail["reason"], valid.detail
    assert summarize(results)["blocking"]


def test_l0_degenerate_polygon_fails_area() -> None:
    """退化（所有点共线）→ `area_positive` 必须红。

    ★ `is_valid` 对退化环不一定为 False（shapely 会认为它「合法但空」），
      所以面积必须单独判一条。
    """
    degenerate = Polygon([(0, 0), (20, 0), (40, 0), (60, 0)])
    results = validate_2d(degenerate, label="degenerate")
    area = _by_name(results, "area_positive")
    assert not area.ok, f"退化多边形面积被判为正：{area.detail}"
    assert area.detail["areaMm2"] == 0.0


def test_l0_min_rib_is_measured_not_estimated() -> None:
    """`min_rib` 用 `shapely.distance` 真算：两槽相距 1.0mm → 必须红。

    ★ 不给 `others` 时**不产生** `min_rib` 这条（避免恒真项）。
    """
    a = Polygon([(0, 0), (20, 0), (20, 10), (0, 10)])
    b = Polygon([(21, 0), (41, 0), (41, 10), (21, 10)])   # 与 a 相距 1.0mm

    # 不给邻居 → 没有 min_rib
    alone = validate_2d(a, label="a")
    assert "min_rib" not in {r.name for r in alone}

    both = validate_2d(a, label="a", min_rib_mm=MIN_RIB_MM, others=[b])
    rib = _by_name(both, "min_rib")
    assert not rib.ok, "1.0mm 筋厚没被判红（阈值 2.0）"
    assert abs(rib.detail["minMm"] - 1.0) < 1e-9

    # 拉开到 3mm → 绿
    b2 = Polygon([(23, 0), (43, 0), (43, 10), (23, 10)])
    ok_rib = _by_name(validate_2d(a, min_rib_mm=MIN_RIB_MM, others=[b2]), "min_rib")
    assert ok_rib.ok
    assert abs(ok_rib.detail["minMm"] - 3.0) < 1e-9


def test_l0_real_pocket_shapes_are_valid() -> None:
    """真实槽轮廓（`generate_insert` 的中间产物）必须合法。"""
    from geometry import pocket_shape, board_center

    tool = Tool(id="t1", outer=_rect(PAPER_W / 2, PAPER_H / 2, 100.0, 60.0))
    board = _golden_board()
    shape = pocket_shape(tool, board, board_center([tool]))
    assert_all_ok(validate_2d(shape, label="pocket"), label="pocket")


# ---------------------------------------------------------------- 汇总语义
def test_assert_all_ok_raises_with_details() -> None:
    """`assert_all_ok` 必须把失败的 detail 带出来（否则排查全靠猜）。"""
    with pytest.raises(AssertionError) as exc:
        assert_all_ok([CheckResult("watertight", False, {"faces": 3})], label="x")
    assert "watertight" in str(exc.value)
    assert "faces" in str(exc.value)


def test_summarize_unknown_check_does_not_block() -> None:
    """未分类的 check 失败**不阻断**（避免新增检查项时意外拦死全部请求）。"""
    s = summarize([CheckResult("some_new_check", False, {})])
    assert not s["ok"]
    assert not s["blocking"]
    assert s["unknownFailed"] == ["some_new_check"]
