"""槽切刀（SDS §7.3，M-1 核心）。

★ 局部量绑定式：`top_z` / `depth` / `clearance` / `chamfer` 四个局部量**只在函数开头
  按 `tool.xxx_override ?? board.xxx` 派生一次**，函数体其余地方一律复用，不许再散写
  `board.embed_depth` / `board.clearance` / `thickness`。

★ z 范围必须是 `[top_z - depth, top_z + 1]`：
  上界刺出顶面 1mm 是 F1（密闭空腔）的修复本体；写成 `top_z` 会让槽口只剩一个共面，
  布尔结果不稳定；写成 `thickness + ...` 在 gridfinity 上整体错位 9mm。

★ 调用方优先（M-1 审核缺陷 1 / 2）：`build_pocket_cutter` 的 `depth` / `shape` /
  `clearance` / `chamfer` 全部接受**已算好的值**。`generate_insert` 每个工具只派生一次
  并显式传入，切刀因此**不会**重复 `resolve_depth`（重复发 `DEPTH_EXCEEDS_THICKNESS`）、
  也**不会**重复 `pocket_shape`（重复追加 `SELF_INTERSECTION_REPAIRED` /
  `CLEARANCE_CLOSED_HOLE` / `POLYGON_SPLIT_ON_REPAIR`）。形参为 None 时才自行派生 ——
  这条兜底是给单测/脚本直接调用的，管线里不要依赖它。
"""
from __future__ import annotations

import warnings

import numpy as np
import manifold3d as mf

from domain.models import BoardConfig, Tool, Vec2
from geometry.constants import board_depth_limit, board_top_z
from geometry.polygon import (
    GeometryError,
    make_shape,
    normalize_winding,
    to_board_frame,
)

# 切刀刺出板顶面的高度（mm）。F1 修复本体，不要改小。
TOP_OVERHANG_MM = 1.0


def resolve_depth(
    tool: Tool,
    board: BoardConfig,
    depth: float | None = None,
    warnings_out: list | None = None,
) -> float:
    """生效深度：显式形参 > tool.depth_override > board.embed_depth，再按外形 clamp。

    ★ 超限时**两件事都做**（SDS §7.3 / §7.6 第 1 条）：
      1. `warnings_out.append({"code": "DEPTH_EXCEEDS_THICKNESS", ...})` —— 进响应信封，
         前端只按 `code` 出文案；
      2. 保留 `warnings.warn(...)` —— 开发期提示，且不破坏既有 `pytest.warns` 用法。
    只做 2 不做 1 就是 M-1 被打回的原因：Python 侧捕得到、`generate_insert()['warnings']`
    却是空列表，用户永远看不到。
    """
    if depth is None:
        depth = tool.depth_override if tool.depth_override is not None else board.embed_depth
    limit = board_depth_limit(board)          # rect: top_z - 2；gridfinity: top_z - 4.75 - 2
    if float(depth) > limit:
        requested = float(depth)
        warnings.warn(
            f"DEPTH_EXCEEDS_THICKNESS: depth {requested}mm 超过上界 {limit}mm，已 clamp",
            stacklevel=2,
        )
        if warnings_out is not None:
            warnings_out.append({
                "code": "DEPTH_EXCEEDS_THICKNESS",
                "message": f"槽深 {requested}mm 超过板厚允许的 {limit}mm，已 clamp",
                "detail": {"requested": requested, "clamped_to": float(limit),
                           "toolId": tool.id},
            })
        depth = limit
    return float(depth)


def resolve_clearance(tool: Tool, board: BoardConfig) -> float:
    return float(tool.clearance_override if tool.clearance_override is not None
                 else board.clearance)


def resolve_chamfer(tool: Tool, board: BoardConfig) -> float:
    return float(tool.chamfer_override if tool.chamfer_override is not None
                 else board.slot_chamfer)


def pocket_shape(
    tool: Tool,
    board: BoardConfig,
    board_center: Vec2,
    warnings_out: list | None = None,
    clearance: float | None = None,
):
    """槽在板局部 mm 下的 shapely 轮廓（已翻转、已归一化、已简化、已加间隙）。

    单独抽出是为了让冒烟脚本能直接量 `bounds` 得到槽长，而不必去猜 3D bbox。
    `clearance` 显式传入时沿用调用方已绑定的局部量，避免二次派生。

    ★ **每个工具每轮只调一次**（`generate_insert` 的唯一调用点）。第二次调用会把
      `SELF_INTERSECTION_REPAIRED` / `CLEARANCE_CLOSED_HOLE` 等同一条告警再追加一遍。
    """
    outer = to_board_frame(tool.outer, board_center)          # 1. 唯一 y 翻转
    holes = [to_board_frame(h, board_center) for h in tool.interior]
    outer, holes = normalize_winding(outer, holes)            # 2. 外 CCW / 孔 CW
    if clearance is None:
        clearance = resolve_clearance(tool, board)
    return make_shape(outer, holes, clearance, warnings_out=warnings_out)  # 3-5


def _cs_from_shape(shape) -> mf.CrossSection:
    """shapely → CrossSection（内孔走 EvenOdd）。面积 <= 0 时整组反向重试一次。

    ★ 注：本实现用 `FillRule.EvenOdd`，按射线奇偶填充、与绕向无关，所以"整组反向重试"
      对 EvenOdd **不产生效果**（实测原样与全反向的 `area()` 相同）。这段是 SDS §7.3
      第 6 步明文要求的写法，保留作契约；真正兜底的是紧随其后的 `GeometryError`。
    """
    outer_ring = np.asarray(shape.exterior.coords, dtype=float)
    hole_rings = [np.asarray(h.coords, dtype=float) for h in shape.interiors]
    rings = [outer_ring] + hole_rings
    cs = mf.CrossSection(rings, mf.FillRule.EvenOdd)
    if cs.area() <= 0:
        # 整组反向重试一次（SDS §7.3 第 6 步；对 EvenOdd 无效，见上）
        cs = mf.CrossSection([r[::-1] for r in rings], mf.FillRule.EvenOdd)
        if cs.area() <= 0:
            raise GeometryError("GEOMETRY_INVALID", "CrossSection 面积为非正（两种绕向都试过）",
                                {"outer_points": len(outer_ring), "holes": len(hole_rings)})
    return cs


def build_pocket_cutter(
    tool: Tool,
    board: BoardConfig,
    board_center: Vec2,
    depth: float | None = None,
    warnings_out: list | None = None,
    shape=None,
    clearance: float | None = None,
    chamfer: float | None = None,
) -> mf.Manifold:
    """构造一把工具的槽切刀（直筒 + 可选倒角锥台），z ∈ [top_z - depth, top_z + 1]。

    形参 `shape` / `depth` / `clearance` / `chamfer` 是**调用方已算好的局部量**：
    传了就一律复用（`generate_insert` 就是这么调的），传 None 才自行派生。
    """
    # —— 局部量绑定（每个量最多派生一次；调用方给了就用调用方的）——
    top_z = board_top_z(board)
    depth = resolve_depth(tool, board, depth, warnings_out=warnings_out)
    if clearance is None:
        clearance = resolve_clearance(tool, board)
    if chamfer is None:
        chamfer = resolve_chamfer(tool, board)

    if depth <= 0:
        raise GeometryError("GEOMETRY_INVALID", "槽深非正", {"depth": depth})

    # 1-5. 翻转 / 归一化 / buffer(0) / simplify / buffer(clearance)
    # ★ 只在调用方没给 shape 时才算（否则告警会被追加两遍）
    if shape is None:
        shape = pocket_shape(tool, board, board_center, warnings_out, clearance=clearance)

    # 6. CrossSection（内孔 EvenOdd）
    cs_in = _cs_from_shape(shape)

    # 7. 平移到原点后拉伸，再平移回 z ∈ [top_z - depth, top_z + 1]
    bx0, by0, bx1, by1 = cs_in.bounds()          # 扁平 4 元组
    cx, cy = (bx0 + bx1) / 2.0, (by0 + by1) / 2.0
    cs0 = cs_in.translate((-cx, -cy))
    cutter_cyl = mf.Manifold.extrude(cs0, depth + TOP_OVERHANG_MM).translate(
        (cx, cy, top_z - depth)
    )

    # 8. 倒角锥台：z ∈ [top_z - eff, top_z]（顶面再 +0.01 保布尔稳定），顶面外扩
    if chamfer > 0:
        eff = min(chamfer, max(0.0, depth - 1.0))   # depth <= 1 时不倒角，避免切穿槽底
        if eff > 1e-6:
            cs_o = cs0.offset(eff, mf.JoinType.Round)
            bi, bo = cs0.bounds(), cs_o.bounds()
            wi, hi = bi[2] - bi[0], bi[3] - bi[1]
            wo, ho = bo[2] - bo[0], bo[3] - bo[1]
            if wi <= 1e-9 or hi <= 1e-9:
                raise GeometryError("GEOMETRY_INVALID", "槽截面退化（宽或高为 0）",
                                    {"bounds": list(bi)})
            sxy = (wo / wi, ho / hi)                # 两者都 > 1
            cutter_chamfer = mf.Manifold.extrude(cs0, eff + 0.01, scale_top=sxy).translate(
                (cx, cy, top_z - eff)
            )
            if warnings_out is not None:
                # v1 用 scale_top 仿射近似，凹角处倒角会偏窄（SDS §7.3 第 8 步）
                cs_ref = cs0.offset(eff, mf.JoinType.Miter)
                affine_area = cs0.area() * sxy[0] * sxy[1]
                if abs(cs_ref.area() - affine_area) > 0.15 * max(cs_ref.area(), 1e-9):
                    warnings_out.append({
                        "code": "CHAMFER_NARROW_AT_CONCAVE",
                        "message": "凹角处倒角偏窄（scale_top 仿射实现的已知 v1 取舍）",
                        "detail": {"ref_area": cs_ref.area(), "affine_area": affine_area},
                    })
            return cutter_cyl + cutter_chamfer

    return cutter_cyl
