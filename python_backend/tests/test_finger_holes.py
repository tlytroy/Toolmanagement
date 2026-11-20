"""M1.5 手孔 6 形态测试（SDS §7.4 / 任务书路 C DoD）。

所有 cutter 直接调 `build_finger_hole_cutter` 纯函数（按任务书约束，不接进 generate_insert）。
坐标：hole.x/y 是纸面 mm（y-down），board_center=(105,148.5)，故孔 y=138.5 → 板 y=+10。
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

from domain.models import BoardConfig, FingerHole, Tool, Project, Vec2  # noqa: E402
from geometry import generate_insert  # noqa: E402
from geometry.constants import board_top_z, FINGER_REACH_MM  # noqa: E402
from geometry.finger_holes import (  # noqa: E402
    ALL_KINDS,
    SHOULDER_KINDS,
    available_shapes,
    build_finger_hole_cutter,
    resolve_finger_depth,
)
from geometry.polygon import GeometryError  # noqa: E402

CENTER = Vec2(105.0, 148.5)
HOLE_PAPER_Y = 138.5          # → board y = +10.0（y 正侧）
BOARD_Y = 10.0


def board_a():
    return BoardConfig(shape="rect", thickness=12, embed_depth=8.0,
                       size_mode="custom", width_mm=200, height_mm=150, corner_r=5.0)


def board_b():
    return BoardConfig(shape="rect", thickness=25, embed_depth=22.0,
                       size_mode="custom", width_mm=200, height_mm=150, corner_r=5.0)


def hole(shape, depth, **kw):
    return FingerHole(id="h", x=105.0, y=HOLE_PAPER_Y, shape=shape,
                      depth=depth, **kw)


# ── 1. 形态判据（生效 depth，与板厚无关）──────────────────────────
def test_available_shapes_depth_threshold():
    # 阈值锚死 SDS §7.4 规格真值 20.0mm，不引用被测常量本身（防改常量恒真）
    assert FINGER_REACH_MM == 20.0
    assert available_shapes(19.99) == frozenset({"scoop"})
    assert available_shapes(20.0) == frozenset(SHOULDER_KINDS)
    assert available_shapes(22.0) == frozenset(SHOULDER_KINDS)


def test_effective_depth_uses_hole_depth_not_board_embed():
    # 25mm 板 embed_depth=8，但 hole.depth=22 → 生效深度取 hole.depth=22（在 limit=23 内）
    thick = BoardConfig(shape="rect", thickness=25, embed_depth=8.0,
                        size_mode="custom", width_mm=200, height_mm=150, corner_r=5.0)
    h = hole("cylinder", 22.0, radius=6.0)
    assert resolve_finger_depth(h, thick) == pytest.approx(22.0)
    cutter = build_finger_hole_cutter(h, thick, CENTER)
    assert cutter.status() == mf.Error.NoError
    assert abs(cutter.bounding_box()[2] - (board_top_z(thick) - 22.0)) <= 0.01


def test_depth_filter_rejects_vertical_below_20():
    # 生效深度 8 < 20 → 竖直孔被拒，只有 scoop 合法
    with pytest.raises(GeometryError) as ei:
        build_finger_hole_cutter(hole("cylinder", 8.0, radius=6.0), board_a(), CENTER)
    assert ei.value.code == "INVALID_FINGER_DEPTH"


# ── 2. A 组：thickness=12 / embedDepth=8 → scoop ──────────────────
def test_scoop_floor_is_top_z_minus_effective_depth():
    cutter = build_finger_hole_cutter(
        hole("scoop", 8.0, scoop_width=12.0, scoop_angle_deg=45.0,
             scoop_dir=Vec2(0.0, -1.0)),
        board_a(), CENTER, d_edge=30.0,
    )
    bb = cutter.bounding_box()
    assert abs(bb[2] - (board_top_z(board_a()) - 8.0)) <= 0.01   # 4.0
    assert cutter.status() == mf.Error.NoError


def test_scoop_is_on_positive_y_side():
    """防二次取负：若照抄 tracefinity `-(y+offset)` 会跑到 y 负侧。"""
    cutter = build_finger_hole_cutter(
        hole("scoop", 8.0, scoop_dir=Vec2(0.0, -1.0)),
        board_a(), CENTER, d_edge=30.0,
    )
    bb = cutter.bounding_box()
    assert bb[1] > 0.0, f"scoop minY={bb[1]} 应为正（板 y 正侧）"


def test_scoop_intersects_pocket_in_3d():
    scoop = build_finger_hole_cutter(
        hole("scoop", 8.0, scoop_dir=Vec2(0.0, -1.0)),
        board_a(), CENTER, d_edge=30.0,
    )
    tool = Tool(id="t1", outer=[
        Vec2(55, 138.5), Vec2(155, 138.5), Vec2(155, 158.5), Vec2(55, 158.5),
    ])
    pocket = generate_insert(Project(tools=[tool], board=board_a()))["slot_cutter"]
    assert (scoop ^ pocket).volume() > 0.1    # 3D 求交，不是 CrossSection


def test_scoop_run_clamped_by_measured_d_edge():
    # d_edge=5 → max_run=5-0.4=4.6 < 默认 run=8 → clamp
    cutter = build_finger_hole_cutter(
        hole("scoop", 8.0, scoop_dir=Vec2(0.0, -1.0)),
        board_a(), CENTER, d_edge=5.0,
    )
    bb = cutter.bounding_box()
    assert bb[4] <= BOARD_Y + 4.6 + 0.01      # maxY 不超 clamp 后的坡长
    assert bb[4] >= BOARD_Y + 4.5             # 确实被 clamp 到上界附近


def test_scoop_no_solution_raises_geometry_invalid():
    # d_edge < clearance + 1.0 → 无解
    with pytest.raises(GeometryError) as ei:
        build_finger_hole_cutter(
            hole("scoop", 8.0, scoop_dir=Vec2(0.0, -1.0)),
            board_a(), CENTER, d_edge=1.0,
        )
    assert ei.value.code == "GEOMETRY_INVALID"


# ── 3. B 组：thickness=25 / embedDepth=22 → 五种竖直孔 ────────────
VERTICAL_PARAMS = {
    "sphere": dict(radius=13.0),              # 必须 > depth/2=11 才开口
    "cylinder": dict(radius=6.0),
    "square": dict(radius=6.0),
    "rect": dict(width=14.0, height=10.0),
    "filleted_rect": dict(width=14.0, height=10.0),
}


@pytest.mark.parametrize("shape,kw", list(VERTICAL_PARAMS.items()))
def test_vertical_blind_floor_is_top_z_minus_depth(shape, kw):
    cutter = build_finger_hole_cutter(hole(shape, 22.0, **kw), board_b(), CENTER)
    bb = cutter.bounding_box()
    assert abs(bb[2] - (board_top_z(board_b()) - 22.0)) <= 0.01   # 3.0
    assert cutter.status() == mf.Error.NoError


@pytest.mark.parametrize("shape", ["cylinder", "square", "rect", "filleted_rect"])
def test_vertical_through_floor_below_minus_half(shape):
    kw = VERTICAL_PARAMS[shape]
    cutter = build_finger_hole_cutter(
        hole(shape, 22.0, depth_mode="through", **kw), board_b(), CENTER
    )
    assert cutter.bounding_box()[2] <= -0.5


def test_vertical_hole_on_positive_y_side():
    """防二次取负：cylinder r=6 孔心 board y=+10 → minY=+4>0。"""
    cutter = build_finger_hole_cutter(hole("cylinder", 22.0, radius=6.0), board_b(), CENTER)
    bb = cutter.bounding_box()
    assert bb[1] > 0.0, f"cylinder minY={bb[1]} 应为正"


def test_sphere_opening_guard_rejects_buried_ball():
    """radius < depth/2 → 珠顶低于板顶，封闭空腔 → 阻断。"""
    with pytest.raises(GeometryError) as ei:
        build_finger_hole_cutter(hole("sphere", 22.0, radius=8.0), board_b(), CENTER)
    assert ei.value.code == "GEOMETRY_INVALID"


def test_sphere_rejects_through():
    with pytest.raises(GeometryError) as ei:
        build_finger_hole_cutter(
            hole("sphere", 22.0, radius=13.0, depth_mode="through"), board_b(), CENTER
        )
    assert ei.value.code == "INVALID_FINGER_DEPTH"


def test_all_six_shapes_are_covered():
    assert ALL_KINDS == {"scoop"} | SHOULDER_KINDS
    assert len(ALL_KINDS) == 6


def test_rotation_is_negated_guard():
    """y 镜像使顺逆时针互换：源码必须 `rot = -hole.rotation`（防漏改回归）。"""
    src = (Path(__file__).resolve().parents[1] / "geometry" / "finger_holes.py").read_text(encoding="utf-8")
    assert "rot = -float(hole.rotation)" in src
