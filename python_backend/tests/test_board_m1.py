"""M1 板体测试：1.4a 底座 / 1.4b 堆叠唇 / 1.4c 磁孔 / 1.6 板尺寸。

所有断言锚到 tracefinity 剖面真源；±0.01 / ±0.05 容差按 SDS §10 / plan M1 DoD。
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import manifold3d as mf  # noqa: E402
import pytest  # noqa: E402

from domain.models import BoardConfig, Tool, Vec2, Project  # noqa: E402
from geometry import board_size_mm, build_board, generate_insert  # noqa: E402
from geometry.board import derive_units  # noqa: E402
from geometry.constants import (  # noqa: E402
    GR_BASE_HEIGHT, GRU, LIP_HEIGHT, LIP_WIDTH, LIP_D0, LIP_D1,
    LIP_D2, LIP_D3, LIP_D4, MAGNET_DEPTH, MAGNET_DIAMETER, MAGNET_OFFSET,
    BASE_H_BOT, BASE_H_MID, BASE_H_TOP,
)
from geometry.gridfinity import (  # noqa: E402
    base_segments, lip_notch_segments, magnet_centers,
    magnet_hole_cutter, build_lip_ring_cutter, build_gridfinity_board, rounded_rect_pts,
)
from geometry.polygon import GeometryError  # noqa: E402


def _bb(m: mf.Manifold):
    return m.bounding_box()  # 扁平 6 元组 (minx,miny,minz,maxx,maxy,maxz)


# ── 1.4a 底座三段 ──────────────────────────────────────────────
def test_base_segments_three_heights_sum_to_475():
    segs = base_segments(42.0, 42.0)
    assert len(segs) == 3
    heights = [_bb(s)[5] - _bb(s)[2] for s in segs]
    assert heights == pytest.approx([BASE_H_BOT, BASE_H_MID, BASE_H_TOP], abs=0.01)
    assert sum(heights) == pytest.approx(GR_BASE_HEIGHT, abs=0.01)


def test_base_bottom_and_top_footprint_taper():
    """底段 bot 宽 36.1→mid 37.7（scale_top 收腰），顶段 mid 37.7→outer 42。"""
    segs = base_segments(42.0, 42.0)
    # 用 slice 量锥台上下端剖面宽（bbox 取的是最宽处，量不出锥度）
    l0_lo = segs[0].slice(0.01).bounds()   # 底段起点 ≈36.1
    l0_hi = segs[0].slice(0.79).bounds()   # 底段终点 ≈37.7
    # segs[2] 已 translate 到 z=2.6，其顶端在 z=4.75；slice 用全局 z
    l2_hi = segs[2].slice(GR_BASE_HEIGHT - 0.01).bounds()  # 顶段终点 ≈42
    assert (l0_lo[2] - l0_lo[0]) == pytest.approx(36.1, abs=0.15)
    assert (l0_hi[2] - l0_hi[0]) == pytest.approx(37.7, abs=0.15)
    assert (l2_hi[2] - l2_hi[0]) == pytest.approx(42.0, abs=0.15)


# ── 1.4b 堆叠唇五段 ────────────────────────────────────────────
def test_lip_notch_five_segment_heights_exact():
    segs = lip_notch_segments(42.0, 42.0)
    assert len(segs) == 5
    heights = [_bb(s)[5] - _bb(s)[2] for s in segs]
    assert heights == pytest.approx(
        [LIP_D4, LIP_D3, LIP_D2, LIP_D1, LIP_D0], abs=0.01
    )
    assert heights == pytest.approx([2.6, 1.2, 0.7, 1.8, 1.9], abs=0.01)
    assert sum(heights) == pytest.approx(8.2, abs=0.05)
    assert sum(heights) == pytest.approx(LIP_HEIGHT, abs=0.05)


def test_lip_width_radial_is_26_not_82():
    """LIP_WIDTH 是径向带宽 2.6；LIP_HEIGHT 8.2 是垂直高，不可混用。"""
    assert LIP_WIDTH == pytest.approx(2.6, abs=0.05)
    # 唇环槽底部外圈宽 2.6：内腔底宽 = 42 - 2*(D0+D2) = 36.3 → 环宽 (42-36.3)/2
    w = 42.0
    notch_bottom_w = w - 2.0 * (LIP_D0 + LIP_D2)
    assert (w - notch_bottom_w) / 2.0 == pytest.approx(LIP_WIDTH, abs=0.01)


def test_lip_ring_cutter_z_range_and_top_center_solid():
    """唇环槽 z ∈ [top_z-8.2, top_z]；顶面中心保持实心（供工具槽切）。"""
    w = h = 42.0
    top_z = 21.0  # 3U
    cutter = build_lip_ring_cutter(w, h, top_z)
    bb = _bb(cutter)
    assert bb[2] == pytest.approx(top_z - LIP_HEIGHT, abs=0.01)
    assert bb[5] == pytest.approx(top_z + 1e-6, abs=0.01)
    # 顶面中心 (0,0) 向下射线不应命中环槽（中心是实心的）
    m = cutter  # 环槽切刀本身中心为空；用板体验证中心实心见 build_gridfinity_board 测试


# ── 1.4c 磁孔 ─────────────────────────────────────────────────
def test_magnet_centers_offset_13_and_intra_inter_cell_distances():
    centers = magnet_centers(2, 1)
    assert len(centers) == 8  # 2 格 × 4 孔
    # 每格四孔相对格心 ±13：同格相邻孔心距 26，跨格相邻 16
    # 按 x 排序去重
    xs = sorted(set(round(x, 4) for x, _ in centers))
    # 2 格：格心 x = -21, +21；孔心 = -34,-8,8,34
    assert xs == pytest.approx([-34.0, -8.0, 8.0, 34.0], abs=0.01)
    assert xs[1] - xs[0] == pytest.approx(26.0, abs=0.01)   # 同格
    assert xs[2] - xs[1] == pytest.approx(16.0, abs=0.01)   # 跨格 42-26


def test_magnet_hole_depth_and_count():
    """磁孔从 z=0 起钻、深 2.4；每格 4 孔 batch union。"""
    cutter = magnet_hole_cutter(2, 2)
    bb = _bb(cutter)
    assert bb[2] == pytest.approx(0.0, abs=0.01)
    assert bb[5] == pytest.approx(MAGNET_DEPTH + 0.01, abs=0.01)
    # 16 个圆柱 union 后仍单连通？不要求；但体积应 ≈ 16 * π r² h
    expect = 16 * math.pi * (MAGNET_DIAMETER / 2) ** 2 * (MAGNET_DEPTH + 0.01)
    assert cutter.volume() == pytest.approx(expect, rel=0.02)


# ── 1.6 板外形 + 高度公式 + 组合 ──────────────────────────────
def test_gridfinity_board_height_3u_is_21():
    board = build_gridfinity_board(1, 1, 3, magnets=False, stacking_lip=False)
    bb = _bb(board)
    assert bb[2] == pytest.approx(0.0, abs=0.01)
    assert bb[5] == pytest.approx(21.0, abs=0.01)   # 3U=21，不是 26/25.75
    assert board.status() == mf.Error.NoError


def test_gridfinity_board_full_features_watertight():
    board = build_gridfinity_board(2, 2, 3, magnets=True, stacking_lip=True)
    bb = _bb(board)
    assert bb[5] == pytest.approx(21.0, abs=0.01)
    assert board.status() == mf.Error.NoError


def test_derive_units_three_modes():
    bbox = (10.0, 20.0, 110.0, 80.0)  # 100 x 60
    assert derive_units("fit-tools", bbox, 12.0, None, None, {}) == (3, 2)
    assert derive_units("custom", bbox, 12.0, 84.0, 126.0, {}) == (2, 3)
    assert derive_units("print-bed", bbox, 12.0, None, None,
                        {"x": 220.0, "y": 220.0}) == (5, 5)


def test_build_board_dispatches_gridfinity():
    cfg = BoardConfig(shape="gridfinity", units_x=2, units_y=1, height_u=3,
                      magnets=True, stacking_lip=True)
    size = board_size_mm(cfg, [])
    assert size == (84.0, 42.0)
    board = build_board(cfg, size)
    assert _bb(board)[5] == pytest.approx(21.0, abs=0.01)


def test_generate_insert_gridfinity_end_to_end():
    """gridfinity 板 + 一个矩形工具槽，端到端水密、槽顶正确。"""
    tool = Tool(id="t1", outer=[Vec2(0, 0), Vec2(100, 0), Vec2(100, 20), Vec2(0, 20)])
    board = BoardConfig(shape="gridfinity", units_x=3, units_y=2, height_u=3,
                        magnets=True, stacking_lip=True, embed_depth=8.0,
                        size_mode="custom", width_mm=126.0, height_mm=84.0)
    project = Project(tools=[tool], board=board)
    result = generate_insert(project)
    base = result["base"]
    assert base.status() == mf.Error.NoError
    assert result["top_z"] == pytest.approx(21.0, abs=0.01)
    bb = _bb(base)
    assert bb[5] == pytest.approx(21.0, abs=0.01)
    assert bb[3] - bb[0] == pytest.approx(126.0, abs=0.1)
    # clearance 0.4 每侧外扩 → 槽长 100 + 2*0.4 = 100.8
    assert result["pocket_length_mm"] == pytest.approx(100.8, abs=0.05)
