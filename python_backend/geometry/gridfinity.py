"""Gridfinity 板体几何（M1）：底座三段收腰 + 顶面堆叠唇环形槽 + 磁孔。

剖面语义来自 tracefinity（MIT，`stl_generator_manifold.py`）的
`_build_base_unit` / `_build_stacking_lip_notch` / `_make_magnet_holes`，但有三点本项目化：

1. 外轮廓恒为 `units * 42`（顶面净尺寸），**不做** tracefinity 的 0.5mm inset。
2. 堆叠唇做成**顶面外圈的环形槽**：中间保持实心，供工具槽从 `top_z` 往下切。
   tracefinity 的 bin 是「顶面全开口的内腔」（中间是空的），照搬会让工具槽切进空气。
   本模块的 `lip_notch_segments()` 返回的就是那个「内腔」实体；
   `build_lip_ring_cutter()` = 唇区外框 − 内腔 = 环形槽切刀。
3. 不做任何 y 取负：本项目坐标已在 `to_board_frame` 统一翻转一次（SDS §2）。

★ z 铁律：板底 z=0，板顶 z=`board_top_z(board)`=heightU*7。
  底座 [0, 4.75]；唇环形槽 [top_z - LIP_HEIGHT, top_z]。
"""
from __future__ import annotations

import math

import manifold3d as mf
import numpy as np

from geometry.constants import (
    BASE_H_BOT,
    BASE_H_MID,
    BASE_H_TOP,
    GF_CORNER_R,
    GR_BASE_HEIGHT,
    GRU,
    LIP_D0,
    LIP_D1,
    LIP_D2,
    LIP_D3,
    LIP_D4,
    LIP_HEIGHT,
    MAGNET_DEPTH,
    MAGNET_DIAMETER,
    MAGNET_OFFSET,
    CIRCLE_SEGS,
    ROUND_SEGS,
)
from geometry.polygon import GeometryError

# 唇五段自下而上的顺序（与 tracefinity `_build_stacking_lip_notch` 一致）：
#   LIP_D4(2.6) → LIP_D3(1.2) → LIP_D2(0.7) → LIP_D1(1.8) → LIP_D0(1.9)
LIP_SEGMENT_ORDER = (LIP_D4, LIP_D3, LIP_D2, LIP_D1, LIP_D0)


def rounded_rect_pts(w: float, h: float, r: float, segs: int = CIRCLE_SEGS) -> np.ndarray:
    """CCW 圆角矩形点列（中心在原点），每段 segs//4 个点。"""
    r = max(0.0, min(float(r), w / 2.0 - 1e-9, h / 2.0 - 1e-9))
    n = max(3, int(segs) // 4)
    cx, cy = w / 2.0 - r, h / 2.0 - r
    pts: list[tuple[float, float]] = []
    for i, (ox, oy) in enumerate([(-cx, -cy), (cx, -cy), (cx, cy), (-cx, cy)]):
        base = i * math.pi / 2.0 + math.pi
        for j in range(n):
            a = base + j * (math.pi / 2.0) / n
            pts.append((ox + r * math.cos(a), oy + r * math.sin(a)))
    return np.asarray(pts, dtype=np.float64)


def _cs(pts: np.ndarray) -> mf.CrossSection:
    return mf.CrossSection([np.asarray(pts, dtype=np.float64)])


def _union(parts: list[mf.Manifold]) -> mf.Manifold:
    if not parts:
        return mf.Manifold()
    if len(parts) == 1:
        return parts[0]
    return mf.Manifold.batch_boolean(parts, mf.OpType.Add)


def base_segments(w: float, h: float) -> list[mf.Manifold]:
    """底座三段收腰实体（z 局部从 0 起），每段单独 extrude + scale_top。

    段高 BASE_H_BOT(0.8) + BASE_H_MID(1.8) + BASE_H_TOP(2.15) = GR_BASE_HEIGHT(4.75)。
    自下而上：bot→mid 锥台、mid 直壁、mid→outer 锥台。
    """
    mid_w = w - 2.0 * BASE_H_TOP
    mid_h = h - 2.0 * BASE_H_TOP
    bot_w = mid_w - 2.0 * BASE_H_BOT
    bot_h = mid_h - 2.0 * BASE_H_BOT
    if min(bot_w, bot_h, mid_w, mid_h) <= 0:
        raise GeometryError("GEOMETRY_INVALID", "gridfinity 底座剖面宽度非正",
                            {"size": [w, h]})

    cs_bot = _cs(rounded_rect_pts(bot_w, bot_h, GF_CORNER_R))
    cs_mid = _cs(rounded_rect_pts(mid_w, mid_h, GF_CORNER_R))

    l0 = mf.Manifold.extrude(cs_bot, BASE_H_BOT,
                             scale_top=(mid_w / bot_w, mid_h / bot_h))
    l1 = mf.Manifold.extrude(cs_mid, BASE_H_MID).translate((0.0, 0.0, BASE_H_BOT))
    l2 = mf.Manifold.extrude(cs_mid, BASE_H_TOP,
                             scale_top=(w / mid_w, h / mid_h)).translate(
                                 (0.0, 0.0, BASE_H_BOT + BASE_H_MID))
    return [l0, l1, l2]


def lip_notch_segments(w: float, h: float) -> list[mf.Manifold]:
    """堆叠唇「内腔」五段实体（z 局部从 0 起，总高 LIP_HEIGHT=8.2）。

    从下往上：outer→inner (D4) / inner 直壁 (D3) / inner→mid (D2)
    / mid 直壁 (D1) / mid→outer (D0)。每段 bbox 高度即其段高，
    供 M1 DoD 逐段断言 2.6 / 1.2 / 0.7 / 1.8 / 1.9。
    """
    nw_inner = w - 2.0 * (LIP_D0 + LIP_D2)
    nh_inner = h - 2.0 * (LIP_D0 + LIP_D2)
    nw_mid = w - 2.0 * LIP_D0
    nh_mid = h - 2.0 * LIP_D0
    if min(nw_inner, nh_inner, nw_mid, nh_mid) <= 0:
        raise GeometryError("GEOMETRY_INVALID", "gridfinity 唇剖面宽度非正",
                            {"size": [w, h]})

    cs_outer = _cs(rounded_rect_pts(w, h, GF_CORNER_R))
    cs_inner = _cs(rounded_rect_pts(nw_inner, nh_inner, GF_CORNER_R))
    cs_mid = _cs(rounded_rect_pts(nw_mid, nh_mid, GF_CORNER_R))

    l0 = mf.Manifold.extrude(cs_outer, LIP_D4,
                             scale_top=(nw_inner / w, nh_inner / h))
    z = LIP_D4
    l1 = mf.Manifold.extrude(cs_inner, LIP_D3).translate((0.0, 0.0, z))
    z += LIP_D3
    l2 = mf.Manifold.extrude(cs_inner, LIP_D2,
                             scale_top=(nw_mid / nw_inner, nh_mid / nh_inner)).translate(
                                 (0.0, 0.0, z))
    z += LIP_D2
    l3 = mf.Manifold.extrude(cs_mid, LIP_D1).translate((0.0, 0.0, z))
    z += LIP_D1
    l4 = mf.Manifold.extrude(cs_mid, LIP_D0,
                             scale_top=(w / nw_mid, h / nh_mid)).translate((0.0, 0.0, z))
    return [l0, l1, l2, l3, l4]


def build_lip_ring_cutter(w: float, h: float, top_z: float) -> mf.Manifold:
    """顶面外圈的环形槽切刀，z ∈ [top_z - LIP_HEIGHT, top_z]。

    = (外框实心) − (五段内腔 union)。内腔顶部宽=外框 → 顶面环宽=0（顶面实心）；
    内腔底部宽=outer−2*(D0+D2) → 底部环宽=LIP_WIDTH(2.6)。
    """
    z0 = top_z - LIP_HEIGHT
    cs_outer = _cs(rounded_rect_pts(w, h, GF_CORNER_R))
    outer_solid = mf.Manifold.extrude(cs_outer, LIP_HEIGHT).translate((0.0, 0.0, z0))
    notch = _union(lip_notch_segments(w, h)).translate((0.0, 0.0, z0))
    return outer_solid - notch


def magnet_centers(units_x: int, units_y: int) -> list[tuple[float, float]]:
    """磁孔孔心（板局部坐标，原点板心）。每格四孔、相对格心 ±13mm。"""
    w, h = units_x * GRU, units_y * GRU
    centers: list[tuple[float, float]] = []
    for ix in range(units_x):
        for iy in range(units_y):
            cx = -w / 2.0 + (ix + 0.5) * GRU
            cy = -h / 2.0 + (iy + 0.5) * GRU
            for dx, dy in [(-MAGNET_OFFSET, -MAGNET_OFFSET),
                           (MAGNET_OFFSET, -MAGNET_OFFSET),
                           (MAGNET_OFFSET, MAGNET_OFFSET),
                           (-MAGNET_OFFSET, MAGNET_OFFSET)]:
                centers.append((cx + dx, cy + dy))
    return centers


def magnet_hole_cutter(units_x: int, units_y: int) -> mf.Manifold:
    """磁孔切刀（从 z=0 底面向上打，深 MAGNET_DEPTH），batch union 成一把刀。"""
    centers = magnet_centers(units_x, units_y)
    if not centers:
        return mf.Manifold()
    cyl = mf.Manifold.cylinder(MAGNET_DEPTH + 0.01,
                               MAGNET_DIAMETER / 2.0,
                               circular_segments=ROUND_SEGS)
    holes = [cyl.translate((x, y, 0.0)) for x, y in centers]
    return _union(holes)


def build_gridfinity_board(units_x: int, units_y: int, height_u: int,
                           magnets: bool, stacking_lip: bool) -> mf.Manifold:
    """组合 gridfinity 板体：底座收腰 + 直壁到 top_z + 可选唇环槽 + 可选磁孔。

    z ∈ [0, height_u * GRHU]，底面 z=0，**不做 ±H/2 居中**。
    """
    if units_x < 1 or units_y < 1 or height_u < 1:
        raise GeometryError("GEOMETRY_INVALID", "gridfinity 格数/高度必须为正",
                            {"units": [units_x, units_y], "height_u": height_u})
    w, h = units_x * GRU, units_y * GRU
    top_z = height_u * 7.0

    base = _union(base_segments(w, h))
    wall_h = top_z - GR_BASE_HEIGHT
    if wall_h <= 0:
        raise GeometryError("GEOMETRY_INVALID", "gridfinity 高度不足以容纳底座",
                            {"top_z": top_z, "base_h": GR_BASE_HEIGHT})
    cs_outer = _cs(rounded_rect_pts(w, h, GF_CORNER_R))
    walls = mf.Manifold.extrude(cs_outer, wall_h).translate((0.0, 0.0, GR_BASE_HEIGHT))
    solid = base + walls

    if stacking_lip:
        solid = solid - build_lip_ring_cutter(w, h, top_z)
    if magnets:
        solid = solid - magnet_hole_cutter(units_x, units_y)
    return solid
