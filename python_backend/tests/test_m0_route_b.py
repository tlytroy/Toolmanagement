"""M0 路 B 测试：轮廓原语 + 毫米链收口（计划 v1.3 §0.3 / §0.3b）。

运行（项目根下）：

    .venv/bin/python -m pytest -q python_backend/tests/test_m0_route_b.py

★ 只把 `python_backend` 塞进 sys.path（与 test_geometry_m1.py 一致），**不要**塞仓库根：
  否则 `geometry` 会被加载两份，`GeometryError` 变成两个不同的类。

本文件覆盖的缺陷：
  F1 毫米链断裂 —— `_extrude_tool_slot` 曾用 `img_width, img_height = 840.0, 1188.0`
     再 `scale = min(base_size_x / img_width, base_size_y / img_height)` 按板尺寸
     重新缩放轮廓，于是同一工具换个板就得到不同大小的槽。
  0.3b 基元拍平 —— `_primitives_to_2d_polygon` 曾按出现顺序直接拼接点，不闭合、
     不保方向、内环被拍平成外环的一段。
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import Polygon

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import cad_engine as ce  # noqa: E402


# ── 工具函数 ──────────────────────────────────────────

def _ring_to_primitives(ring, start: int = 0):
    """闭合环（px，不含重复闭合点）→ 一串 line 基元，按环的顺序接龙。"""
    prims = []
    n = len(ring)
    for k in range(n):
        p0 = ring[(start + k) % n]
        p1 = ring[(start + k + 1) % n]
        prims.append({
            "type": "line",
            "p0": {"x": float(p0[0]), "y": float(p0[1])},
            "p1": {"x": float(p1[0]), "y": float(p1[1])},
        })
    return prims


def _normalize_coords(coords):
    """起点对齐 + 绕向归一化，再拿去 equals_exact 比较。

    shapely 的 `equals_exact` 是**逐点有序**比较：起点旋转或绕向相反都会判不等，
    但几何上它们是同一个多边形。所以比较前先统一这两件事。
    """
    pts = [(round(float(x), 9), round(float(y), 9)) for x, y in coords]
    if pts and pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) < 3:
        return pts
    # 绕向归一：统一成 CCW（shoelace > 0）
    area = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        area += x1 * y2 - x2 * y1
    if area < 0:
        pts = pts[::-1]
    # 起点归一：字典序最小点打头
    k = min(range(len(pts)), key=lambda i: pts[i])
    return pts[k:] + pts[:k]


def _assert_same_polygon(actual: Polygon, expected: Polygon, tol: float = 1e-6) -> None:
    a = Polygon(_normalize_coords(actual.exterior.coords),
                [_normalize_coords(r.coords) for r in actual.interiors])
    e = Polygon(_normalize_coords(expected.exterior.coords),
                [_normalize_coords(r.coords) for r in expected.interiors])
    assert a.equals_exact(e, tol), f"往返后多边形不等：\nactual  ={a.wkt}\nexpected={e.wkt}"


def _rect_ring_px(x0: float, y0: float, w_px: float, h_px: float):
    return np.array([
        [x0, y0], [x0 + w_px, y0], [x0 + w_px, y0 + h_px], [x0, y0 + h_px],
    ], dtype=float)


def _slot_x_span(slot) -> float:
    b = slot.bounds
    return float(b[1][0] - b[0][0])


def _slot_y_span(slot) -> float:
    b = slot.bounds
    return float(b[1][1] - b[0][1])


# ── 任务 B：毫米链 ────────────────────────────────────

def test_pocket_length_is_100mm_regardless_of_board_size():
    """100mm 长的合成轮廓 → 切刀长 100.0mm，且与板尺寸完全无关。

    这是 F1 的核心断言。旧实现下 840/1188 + scale 会让长度变成
    `100 * min(board_x/840, board_y/1188) * 10`，随板尺寸漂移。
    """
    # 100mm × 40mm 的矩形，10 px/mm → 1000 × 400 px，放在纸面任意位置
    ring = _rect_ring_px(700.0, 1000.0, 1000.0, 400.0)
    prims = _ring_to_primitives(ring)

    slot_200 = ce._extrude_tool_slot(
        prims, embed_depth=15.0, tool_offset=0.0,
        base_size_x=200.0, base_size_y=150.0,
    )
    slot_300 = ce._extrude_tool_slot(
        prims, embed_depth=15.0, tool_offset=0.0,
        base_size_x=300.0, base_size_y=300.0,
    )
    assert slot_200 is not None, "200mm 板上切刀生成失败"
    assert slot_300 is not None, "300mm 板上切刀生成失败"

    # DoD 1：100.0 ± 0.1mm（M0 无 clearance，必须精确等于 100，不许 100.8）
    assert _slot_x_span(slot_200) == pytest.approx(100.0, abs=0.1)
    assert _slot_y_span(slot_200) == pytest.approx(40.0, abs=0.1)

    # DoD 2：同一轮廓在 200mm 板与 300mm 板上结果完全一致
    assert slot_200.bounds.tolist() == slot_300.bounds.tolist(), (
        f"板尺寸影响了切刀：200mm 板 {slot_200.bounds.tolist()} vs "
        f"300mm 板 {slot_300.bounds.tolist()}"
    )
    assert slot_200.volume == pytest.approx(slot_300.volume, rel=1e-9)

    # DoD 3：截面积相对误差 ≤ 0.1%（拉伸体体积 / 高度 = 截面积）
    height = 15.0 + 1.0                      # embed_depth + 1
    area_mm2 = slot_200.volume / height
    assert area_mm2 == pytest.approx(100.0 * 40.0, rel=1e-3), (
        f"截面积 {area_mm2} mm² 与 4000 mm² 相对误差超过 0.1%"
    )


def test_generate_stl_cuts_same_volume_on_different_boards():
    """端到端：`generate_stl`（/generate-cad 的实现）在 200 与 300 板上挖掉同体积。

    上一条测的是 `_extrude_tool_slot` 单元；这条走完整链路
    `generate_stl → generate_insert → _extrude_tool_slot → 布尔减法`，
    确保没有人从别处又把板尺寸塞回轮廓换算。
    """
    ring = _rect_ring_px(700.0, 1000.0, 1000.0, 400.0)
    prims = _ring_to_primitives(ring)

    def cut_volume(board_mm: float) -> float:
        res = ce.generate_stl({
            "mode": "foam",
            "foam": {"length_mm": board_mm, "width_mm": board_mm,
                     "height_mm": 20.0, "fillet_radius": 0.0},
            "primitives": prims,
            "tool_offset": 1.0,
            "embed_depth": 15.0,
            "finger_slots": [],
        })
        assert res["success"], res.get("error")
        blank = board_mm * board_mm * 20.0
        return blank - res["summary"]["volume_mm3"]

    v200 = cut_volume(200.0)
    v300 = cut_volume(300.0)
    # 100×40 轮廓 + 1mm miter 外扩 → (102 × 42) × 16mm 深 = 68544 mm³
    assert v200 == pytest.approx(102.0 * 42.0 * 16.0, rel=1e-3)
    assert v200 == pytest.approx(v300, rel=1e-6), (
        f"板尺寸影响了挖掉的体积：200mm 板 {v200} vs 300mm 板 {v300}"
    )


def test_no_board_size_rescaling_left_in_engine():
    """源码级护栏：`840` / `1188` 这两个「假 A4 像素尺寸」不得再出现。

    DoD 2 的行为断言由上一个测试守；这里额外守住「有人又把常量加回来」。
    """
    src = (_BACKEND / "cad_engine.py").read_text(encoding="utf-8")
    assert "840" not in src, "cad_engine.py 里仍有 840（F1 的假 A4 宽度）"
    assert "1188" not in src, "cad_engine.py 里仍有 1188（F1 的假 A4 高度）"
    assert "PX_PER_MM = 10.0" in src, "固定 10 px/mm 常量不见了"


def test_board_frame_y_flip_matches_geometry_package():
    """板坐标系必须与 `geometry/polygon.py:44` 的 `to_board_frame` 同式（y 取反）。

    旧代码 `poly_mm -= center` 展开是 (x-cx, y-cy)，y 方向没翻转 —— F1 的第二半。
    这里用 y 方向不对称的三角形，符号错了就一定红。
    """
    from domain.models import Vec2
    from geometry.polygon import to_board_frame

    ring = np.array([[200.0, 200.0], [1400.0, 300.0], [500.0, 1300.0]])
    prims = _ring_to_primitives(ring)

    shape_mm = ce._paper_mm_shape(prims)
    assert shape_mm is not None
    minx, miny, maxx, maxy = shape_mm.bounds
    center = ((minx + maxx) / 2.0, (miny + maxy) / 2.0)

    expected_pts = to_board_frame(
        [Vec2(x, y) for x, y in list(shape_mm.exterior.coords)[:-1]],
        Vec2(center[0], center[1]),
    )
    expected = Polygon([(p.x, p.y) for p in expected_pts])

    actual = ce._to_board_frame_shape(shape_mm, center)
    assert actual is not None
    _assert_same_polygon(actual, expected, tol=1e-9)

    # 直接钉住符号：纸面 y 大 → 板 y 小
    ys_paper = [y for _, y in shape_mm.exterior.coords]
    ys_board = [y for _, y in actual.exterior.coords]
    assert min(ys_board) == pytest.approx(-(max(ys_paper) - center[1]), abs=1e-9)


# ── 任务 C：primitives → 有序闭合环 ───────────────────

def test_primitives_roundtrip_simple_polygon():
    """随机简单多边形 polygon → primitives → polygon，equals_exact(tol=1e-6)。"""
    rng = np.random.default_rng(20251105)

    # 生成随机简单多边形：极角排序的星形（一定简单、无自交）
    n = 12
    angles = np.sort(rng.uniform(0.0, 2.0 * math.pi, size=n))
    radii = rng.uniform(600.0, 1200.0, size=n)
    ring = np.column_stack([
        1500.0 + radii * np.cos(angles),
        1500.0 + radii * np.sin(angles),
    ])
    expected = Polygon([tuple(p) for p in ring])
    assert expected.is_valid, "测试自身的多边形必须有效"

    prims = _ring_to_primitives(ring)
    actual = ce._primitives_to_shape(prims)
    assert actual is not None, "往返后拿不到多边形"
    assert actual.is_valid
    assert len(actual.interiors) == 0

    _assert_same_polygon(actual, expected, tol=1e-6)


def test_primitives_roundtrip_orders_shuffled_primitives():
    """基元被打乱、部分反向时仍应拼回同一个环（证明是「接龙」不是「按出现顺序拼」）。"""
    ring = np.array([
        [100.0, 100.0], [900.0, 120.0], [1100.0, 700.0],
        [600.0, 1000.0], [150.0, 800.0],
    ], dtype=float)
    expected = Polygon([tuple(p) for p in ring])

    prims = _ring_to_primitives(ring)
    # 逐段翻转一半，再整体打乱
    flipped = []
    for i, seg in enumerate(prims):
        if i % 2 == 0:
            flipped.append({"type": "line", "p0": seg["p1"], "p1": seg["p0"]})
        else:
            flipped.append(seg)
    shuffled = [flipped[i] for i in (2, 0, 4, 1, 3)]

    actual = ce._primitives_to_shape(shuffled)
    assert actual is not None
    _assert_same_polygon(actual, expected, tol=1e-6)


def test_primitives_roundtrip_with_hole():
    """带 1 个内环的多边形往返后 holes 数量与面积不变。"""
    outer = _rect_ring_px(0.0, 0.0, 3000.0, 2000.0)          # 300 × 200 mm
    hole = _rect_ring_px(1000.0, 500.0, 1000.0, 1000.0)      # 100 × 100 mm
    expected = Polygon([tuple(p) for p in outer], [[tuple(p) for p in hole]])
    assert expected.is_valid and len(expected.interiors) == 1

    prims = _ring_to_primitives(outer) + _ring_to_primitives(hole)
    actual = ce._primitives_to_shape(prims)
    assert actual is not None, "带内环的往返拿不到多边形"

    # holes 数量不变
    assert len(actual.interiors) == 1, (
        f"内环丢了：往返后 holes = {len(actual.interiors)}"
    )
    # 面积不变（px²）
    assert actual.area == pytest.approx(expected.area, rel=1e-9)
    # 孔面积不变
    hole_area_expected = Polygon([tuple(p) for p in hole]).area
    hole_area_actual = Polygon(actual.interiors[0]).area
    assert hole_area_actual == pytest.approx(hole_area_expected, rel=1e-9)

    # 拉伸时孔必须真的被挖掉：体积 = (外 - 孔) × 高度
    slot = ce._extrude_tool_slot(prims, embed_depth=15.0, tool_offset=0.0,
                                 base_size_x=200.0, base_size_y=150.0)
    assert slot is not None
    expected_volume = (expected.area / 100.0) * (15.0 + 1.0)   # px² → mm²
    assert slot.volume == pytest.approx(expected_volume, rel=1e-6)


# ── 任务 A：/generate-step 已删除 ─────────────────────

def test_generate_step_endpoint_removed():
    """`/generate-step` 路由必须不存在（cadquery 已从 requirements 删除）。"""
    import main as backend_main

    paths = {getattr(r, "path", "") for r in backend_main.app.routes}
    assert "/generate-step" not in paths, (
        f"/generate-step 仍在路由表里：{sorted(p for p in paths if p)}"
    )
    # 其余端点不许被误删
    for keep in ("/generate-cad", "/auto-finger-slots"):
        assert keep in paths, f"{keep} 被误删了：{sorted(p for p in paths if p)}"

    src = (_BACKEND / "main.py").read_text(encoding="utf-8")
    assert "generate-step" not in src
    assert "generate_step" not in src
