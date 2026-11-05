"""多边形准备管线：坐标帧、绕向归一化、自交修复 / 简化 / 加间隙。

★ 顺序铁律（SDS §7.3 第 4-5 步）：**先简化、后加间隙**。
  简化会把轮廓向内啃掉最多一个 tolerance：放在 buffer(clearance) 之前，啃的是
  「工具轮廓」（无害）；放在之后，啃的就是「间隙」本身（0.4mm 被啃成 0.25mm）。
  这是 tracefinity polygon_scaler.py:237-249 注释里写死的教训。
"""
from __future__ import annotations

from shapely.geometry import MultiPolygon, Polygon

from domain.models import Vec2

# 简化容差（mm）。SDS §7.3 第 4 步写死的值，不要就地改。
SIMPLIFY_TOL_MM = 0.15


class GeometryError(Exception):
    """几何构造失败。路由层据此转成 error.code（SDS §4.5）。"""

    def __init__(self, code: str, message: str, detail: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail or {}


def signed_area(pts: list[Vec2]) -> float:
    """y-up 系下的有符号面积，> 0 为 CCW（SDS §2.4）。

    ★ 原式 `sum(... pts[i+1] ...)` 少了取模，会在最后一条边上 IndexError。
    """
    n = len(pts)
    if n < 3:
        return 0.0
    total = 0.0
    for i in range(n):
        a = pts[i]
        b = pts[(i + 1) % n]
        total += a.x * b.y - b.x * a.y
    return 0.5 * total


def to_board_frame(points: list[Vec2], center: Vec2) -> list[Vec2]:
    """纸面 mm(y-down) → 板局部 mm(y-up，原点 = 板心)。全项目唯一的 y 翻转点。

    板原点 = 未隐藏工具并集 bbox 的中心（纸面 mm），**不是板外接框中心**。
    """
    return [Vec2(p.x - center.x, center.y - p.y) for p in points]


def normalize_winding(
    outer: list[Vec2], holes: list[list[Vec2]]
) -> tuple[list[Vec2], list[list[Vec2]]]:
    """绕向归一化：外环 CCW（signed_area > 0）、内孔 CW（signed_area < 0）。

    只在 `to_board_frame` 之后调用一次（SDS §2.4）。序列化层不得再翻。
    """
    out = list(outer)
    if signed_area(out) < 0:
        out.reverse()
    fixed_holes: list[list[Vec2]] = []
    for h in holes:
        ring = list(h)
        if len(ring) >= 3 and signed_area(ring) > 0:
            ring.reverse()
        fixed_holes.append(ring)
    return out, fixed_holes


def _largest(geom, warnings_out: list | None, code: str, message: str):
    """buffer 把轮廓炸成多块时，取面积最大的那块并告警。"""
    if isinstance(geom, MultiPolygon):
        parts = sorted(geom.geoms, key=lambda g: g.area, reverse=True)
        if warnings_out is not None:
            warnings_out.append(
                {"code": code, "message": message,
                 "detail": {"pieces": len(parts), "dropped_area_mm2": sum(p.area for p in parts[1:])}}
            )
        return parts[0]
    return geom


def make_shape(
    outer: list[Vec2],
    holes: list[list[Vec2]],
    clearance: float,
    simplify_tol: float = SIMPLIFY_TOL_MM,
    warnings_out: list | None = None,
) -> Polygon:
    """shapely：`buffer(0)` 修自交 → `simplify` → 再 `buffer(clearance)`。

    `clearance <= 0` 时跳过第二步 buffer（不是跳过 simplify）。
    任何一步得到空几何 → 抛 `GEOMETRY_INVALID`。
    """
    if len(outer) < 3:
        raise GeometryError("GEOMETRY_INVALID", "外轮廓少于 3 个点",
                            {"points": len(outer)})

    shell = [(p.x, p.y) for p in outer]
    ring_holes = [[(p.x, p.y) for p in h] for h in holes if len(h) >= 3]
    poly = Polygon(shell, ring_holes)
    if not poly.is_valid:
        if warnings_out is not None:
            warnings_out.append({"code": "SELF_INTERSECTION_REPAIRED",
                                 "message": "轮廓自交，已用 buffer(0) 修复", "detail": {}})

    # 1) 修自交
    shape = poly.buffer(0)
    if shape.is_empty:
        raise GeometryError("GEOMETRY_INVALID", "buffer(0) 后几何为空",
                            {"outer_points": len(shell), "holes": len(ring_holes)})
    shape = _largest(shape, warnings_out, "POLYGON_SPLIT_ON_REPAIR",
                     "轮廓自交修复后裂成多块，只保留面积最大的一块")

    # 2) 简化（必须早于间隙）
    shape = shape.simplify(simplify_tol, preserve_topology=True)
    if shape.is_empty:
        raise GeometryError("GEOMETRY_INVALID", "simplify 后几何为空",
                            {"simplify_tol": simplify_tol})

    # 3) 加间隙（clearance <= 0 跳过）
    if clearance > 0:
        holes_before = len(shape.interiors)
        shape = shape.buffer(clearance, join_style=2, mitre_limit=2.0)
        if shape.is_empty:
            raise GeometryError("GEOMETRY_INVALID", "加间隙后几何为空（间隙吃掉了整个轮廓）",
                                {"clearance": clearance})
        shape = _largest(shape, warnings_out, "CLEARANCE_SPLIT_POCKET",
                         "间隙把槽撑成多块（薄颈处连通），只保留面积最大的一块")
        if warnings_out is not None and len(shape.interiors) < holes_before:
            warnings_out.append({"code": "CLEARANCE_CLOSED_HOLE",
                                 "message": "间隙过大，内孔被填实",
                                 "detail": {"before": holes_before, "after": len(shape.interiors)}})
    return shape
