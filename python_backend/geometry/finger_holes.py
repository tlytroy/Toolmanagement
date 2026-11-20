"""手孔切刀（M1 / SDS §7.4）：6 形态的 3D cutter + 生效深度判定。

坐标铁律（SDS §2 / §12.3，本模块最容易出错的地方）：
- `hole.x/y` 是**纸面毫米**（y-down），必须先过 `to_board_frame` 翻成板局部 mm（y-up），
  **之后不再取负**。tracefinity 的 `fh_y = -(y+offset_y)` 是它自己一次性的 y 翻转，
  本项目照抄会二次取负 = 竖直镜像，手孔跑到槽另一侧而其它几何全对，极难发现。
- `rotation` 必须取负（`rot = -hole.rotation`）：y 取负是镜像，镜像下顺逆时针互换。
- 生效 `depth` = `hole.depth`（已在 schema 层由 depthOverride??embedDepth 解析并 clamp），
  再按 `board_depth_limit(board)` 兜底 clamp。形态判据与板厚**无关**。

z 铁律：板底 z=0，板顶 z=`board_top_z(board)`；一切「从顶往下」写 `top_z - depth`。
"""
from __future__ import annotations

import math

import manifold3d as mf
import numpy as np

from domain.models import BoardConfig, FingerHole, Vec2
from geometry.constants import (
    CIRCLE_SEGS,
    FINGER_REACH_MM,
    ROUND_SEGS,
    board_depth_limit,
    board_top_z,
)
from geometry.polygon import GeometryError, to_board_frame

# 6 形态；scoop 只在 depth < FINGER_REACH_MM 时合法，其余只在 >= 时合法
SHOULDER_KINDS = frozenset({"sphere", "cylinder", "square", "rect", "filleted_rect"})
ALL_KINDS = frozenset({"scoop"}) | SHOULDER_KINDS

SCOOP_INTRUSION_MM = 0.5      # 楔块向槽内侵入量（保证与槽切刀 3D 求交 > 0.1）


def resolve_finger_depth(hole: FingerHole, board: BoardConfig) -> float:
    """生效深度：hole.depth 经 board_depth_limit 兜底 clamp（形态判据与板厚无关）。"""
    depth = float(hole.depth)
    limit = board_depth_limit(board)
    return max(0.0, min(depth, limit))


def available_shapes(depth: float) -> frozenset[str]:
    """按生效 depth 过滤可用形态（SDS §6.4 / §7.4）。"""
    if depth < FINGER_REACH_MM:
        return frozenset({"scoop"})
    return frozenset(SHOULDER_KINDS)


def _hole_center(hole: FingerHole, board_center: Vec2) -> Vec2:
    """纸面 mm → 板局部 mm（唯一 y 翻转点），直接用、不再取负。"""
    return to_board_frame([Vec2(hole.x, hole.y)], board_center)[0]


def _rounded_bottom_rect_profile(width: float, depth: float, fillet_r: float) -> np.ndarray:
    """CCW x/z 剖面：仅底部两个角倒圆（tracefinity `_rounded_bottom_rect_profile_pts`）。"""
    w, d = max(width, 0.01), max(depth, 0.01)
    hw = w / 2.0
    r = min(max(fillet_r, 0.0), hw, d)
    if r <= 1e-6:
        return np.array([(hw, 0.0), (hw, d), (-hw, d), (-hw, 0.0)], dtype=np.float64)
    n = max(4, CIRCLE_SEGS // 8)
    pts: list[tuple[float, float]] = [(hw - r, 0.0)]
    for j in range(1, n + 1):
        a = -math.pi / 2.0 + j * (math.pi / 2.0) / n
        pts.append((hw - r + r * math.cos(a), r + r * math.sin(a)))
    pts.append((hw, d))
    pts.append((-hw, d))
    for j in range(0, n + 1):
        a = math.pi + j * (math.pi / 2.0) / n
        pts.append((-hw + r + r * math.cos(a), r + r * math.sin(a)))
    return np.asarray(pts, dtype=np.float64)


def _filleted_rect_cutter(
    width: float, height: float, depth: float, top_z: float,
    rot: float, cx: float, cy: float, *, through: bool,
) -> mf.Manifold:
    """X/Z 剖面（底角倒圆）沿 Y 扫掠，再绕 Z 旋转、平移到孔心。"""
    w = max(width, 0.01)
    length = max(height, 0.01)
    r = min(w / 3.0, depth / 2.0)
    bottom = -1.0 if through else top_z - depth
    prof_depth = (top_z + 1.0) - bottom
    prof = _rounded_bottom_rect_profile(w, prof_depth, r)
    cs = mf.CrossSection([prof], mf.FillRule.EvenOdd)
    return (
        mf.Manifold.extrude(cs, length)
        .rotate((90.0, 0.0, 0.0))
        .translate((0.0, length / 2.0, bottom))
        .rotate((0.0, 0.0, rot))
        .translate((cx, cy, 0.0))
    )


def _scoop_cutter(
    hole: FingerHole, cx: float, cy: float, top_z: float, depth: float,
    *, d_edge: float | None, clearance: float,
    warnings_out: list[dict] | None = None,
) -> mf.Manifold:
    """斜坡楔块：三棱柱，坡顶 top_z+0.01，坡底 top_z-depth，向槽内侵入 0.5mm。"""
    angle = float(hole.scoop_angle_deg)
    if not (0.0 < angle < 90.0):
        raise GeometryError("INVALID_SCOOP_ANGLE", "scoop 坡角必须在 (0,90) 度",
                            {"angleDeg": angle})
    run = depth / math.tan(math.radians(angle))
    if d_edge is not None:
        max_run = float(d_edge) - float(clearance)
        if max_run < SCOOP_INTRUSION_MM + 0.5:
            raise GeometryError(
                "GEOMETRY_INVALID",
                "scoop 无解：坡道方向槽壁到板边距离不足，请增大板尺寸或把工具移离板边",
                {"dEdge": float(d_edge), "clearance": float(clearance), "requiredRun": run},
            )
        if run > max_run:
            # SDS §7.4：超出 d_edge − clearance 时 clamp 坡长并写 SCOOP_CLAMPED
            if warnings_out is not None:
                warnings_out.append({
                    "code": "SCOOP_CLAMPED",
                    "message": "scoop 坡长超出槽壁到板边的实测距离，已 clamp",
                    "detail": {"requiredRun": run, "clampedTo": max_run,
                               "dEdge": float(d_edge), "clearance": float(clearance)},
                })
            run = max_run

    # scoop_dir 是纸面(y-down)单位向量 → 板局部(y-up)需翻 y 再归一化
    dx = float(hole.scoop_dir.x)
    dy = -float(hole.scoop_dir.y)
    norm = math.hypot(dx, dy)
    if norm < 1e-9:
        dx, dy, norm = 1.0, 0.0, 1.0
    dx, dy = dx / norm, dy / norm
    px, py = -dy, dx                              # 垂直于坡向
    halfw = max(float(hole.scoop_width), 10.0) / 2.0
    z_top = top_z + 0.01
    z_bot = top_z - depth

    # 三棱柱顶点（局部 s 沿坡向，起切点从槽壁向内移 SCOOP_INTRUSION_MM）
    s0 = -SCOOP_INTRUSION_MM
    s1 = run
    tri = [(s0, z_top), (s0, z_bot), (s1, z_top)]
    pts: list[tuple[float, float, float]] = []
    for side in (-halfw, halfw):
        for s, z in tri:
            pts.append((cx + dx * s + px * side, cy + dy * s + py * side, z))
    return mf.Manifold.hull_points(pts)


def build_finger_hole_cutter(
    hole: FingerHole,
    board: BoardConfig,
    board_center: Vec2,
    *,
    d_edge: float | None = None,
    clearance: float = 0.4,
    warnings_out: list[dict] | None = None,
) -> mf.Manifold:
    """按形态构造单个手孔切刀（板局部 mm，z∈[底, top_z+1]）。

    `d_edge` 仅 scoop 使用：坡道方向槽壁到板轮廓的实测距离；None 时不 clamp 坡长。
    `warnings_out` 接收 SCOOP_CLAMPED 等告警（SDS §7.4）。
    """
    shape = hole.shape
    if shape not in ALL_KINDS:
        raise GeometryError("SCHEMA_UNKNOWN_FIELD", f"未知手孔形态: {shape}",
                            {"shape": shape, "allowed": sorted(ALL_KINDS)})

    top_z = board_top_z(board)
    depth = resolve_finger_depth(hole, board)
    if shape not in available_shapes(depth):
        raise GeometryError(
            "INVALID_FINGER_DEPTH",
            f"形态 {shape} 在生效深度 {depth:.2f}mm 下不可用",
            {"shape": shape, "depth": depth, "reach": FINGER_REACH_MM},
        )

    center = _hole_center(hole, board_center)
    cx, cy = center.x, center.y
    rot = -float(hole.rotation)                   # y 镜像 → 旋转角取负
    through = (hole.depth_mode == "through")

    if shape == "scoop":
        return _scoop_cutter(
            hole, cx, cy, top_z, depth,
            d_edge=d_edge, clearance=clearance, warnings_out=warnings_out,
        )

    if shape == "sphere":
        if through:
            raise GeometryError("INVALID_FINGER_DEPTH", "sphere 不支持 through",
                                {"shape": shape})
        r = min(float(hole.radius), depth, top_z - 1.0)
        center_z = top_z - depth + r
        if center_z + r <= top_z + 0.1:
            raise GeometryError(
                "GEOMETRY_INVALID", "sphere 珠顶低于板顶，会生成封闭空腔",
                {"radius": r, "depth": depth, "centerZ": center_z},
            )
        sphere = mf.Manifold.sphere(r, circular_segments=ROUND_SEGS).translate((cx, cy, center_z))
        clip = mf.Manifold.cube(
            (2 * r + 4, 2 * r + 4, top_z + 2), center=False
        ).translate((cx - r - 2, cy - r - 2, 0.0))
        return sphere ^ clip                      # 与 z>=0 求交，球底 = top_z-depth

    if shape == "cylinder":
        z0 = -1.0 if through else top_z - depth
        h = (top_z + 1.0) - z0
        return mf.Manifold.cylinder(
            h, float(hole.radius), circular_segments=ROUND_SEGS
        ).translate((cx, cy, z0))

    if shape == "square":
        z0 = -1.0 if through else top_z - depth
        size = max(float(hole.radius) * 2.0, 0.01)
        h = (top_z + 1.0) - z0
        return (
            mf.Manifold.cube((size, size, h), center=False)
            .rotate((0.0, 0.0, rot))
            .translate((cx - size / 2.0, cy - size / 2.0, z0))
        )

    if shape == "rect":
        z0 = -1.0 if through else top_z - depth
        w = max(float(hole.width), 0.01)
        h = max(float(hole.height), 0.01)
        hz = (top_z + 1.0) - z0
        return (
            mf.Manifold.cube((w, h, hz), center=False)
            .rotate((0.0, 0.0, rot))
            .translate((cx - w / 2.0, cy - h / 2.0, z0))
        )

    # filleted_rect
    return _filleted_rect_cutter(
        float(hole.width), float(hole.height), depth, top_z, rot, cx, cy, through=through
    )


def scoop_edge_distance(pocket_shape, board_solid, top_z: float) -> float:
    """d_edge：槽壁到板轮廓的实测距离（SDS §7.4）。

    `pocket_shape` 是板局部 mm 的 shapely Polygon（已加间隙），`board_solid` 是
    未开槽板 Manifold。取板顶下方 0.01mm 截面外环，量 `pocket.distance(outline.boundary)`。
    ★ 不是 `margin`——custom/print-bed 下工具可贴板边，margin 与真实余量无关。
    """
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    cs = board_solid.slice(top_z - 0.01)
    rings = cs.to_polygons()
    if not rings:
        return 0.0
    try:
        polys = [Polygon(r) for r in rings if len(r) >= 3]
        if not polys:
            return 0.0
        boundary = unary_union(polys).boundary
        return float(pocket_shape.distance(boundary))
    except Exception:
        return 0.0


__all__ = [
    "FINGER_REACH_MM", "SHOULDER_KINDS", "ALL_KINDS",
    "resolve_finger_depth", "available_shapes", "build_finger_hole_cutter",
    "scoop_edge_distance",
]
