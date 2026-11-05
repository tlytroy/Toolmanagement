"""板体：尺寸决策（`board_size_mm`）与实体构造（`build_board`）。

★ `build_board` 的 z 范围恒为 `[0, thickness]`（板底面 z=0），
  **绝不** `apply_translation([0, 0, -size_z/2])` 居中 —— 那是 F1 的成因。
"""
from __future__ import annotations

import numpy as np
import manifold3d as mf

from domain.models import BoardConfig, Tool, Vec2
from geometry.constants import EDGE_MM, GRU
from geometry.polygon import GeometryError

# 圆角矩形在内缩/外扩时的最小可用半径（避免 offset(-r) 把矩形吃空）
_EPS = 1e-6


def tools_bbox(tools: list[Tool]) -> tuple[float, float, float, float]:
    """未隐藏工具在**纸面 mm** 下的并集外接框 `(minx, miny, maxx, maxy)`。

    只用 `hidden == false` 的工具（隐藏一把后板会随之缩小，是预期行为）。
    """
    visible = [t for t in tools if not t.hidden and t.outer]
    if not visible:
        raise GeometryError("NO_VISIBLE_TOOLS", "没有可参与生成的工具（全部隐藏或为空）")
    xs = [p.x for t in visible for p in t.outer]
    ys = [p.y for t in visible for p in t.outer]
    return (min(xs), min(ys), max(xs), max(ys))


def board_center(tools: list[Tool]) -> Vec2:
    """板框锚点：未隐藏工具并集 bbox 的中心（纸面 mm）。三种 sizeMode 共用。"""
    minx, miny, maxx, maxy = tools_bbox(tools)
    return Vec2((minx + maxx) / 2.0, (miny + maxy) / 2.0)


def _as_bbox(tools) -> tuple[float, float, float, float]:
    """接受 `list[Tool]` 或已算好的 `(minx, miny, maxx, maxy)`。"""
    if isinstance(tools, tuple) and len(tools) == 4 and all(
        isinstance(v, (int, float)) for v in tools
    ):
        return (float(tools[0]), float(tools[1]), float(tools[2]), float(tools[3]))
    return tools_bbox(tools)


def board_size_mm(board: BoardConfig, tools) -> tuple[float, float]:
    """板尺寸的唯一真源（SDS §3.2 / §7.2）。

    rect 三种 sizeMode：
      fit-tools → 未隐藏工具并集 bbox + 2*margin（各边）
      custom    → (width_mm, height_mm)
      print-bed → (print_bed.x - 2*EDGE_MM, print_bed.y - 2*EDGE_MM)   # 220 床 → 210
    gridfinity → (units_x*42, units_y*42)，恒用格数，**不用 width_mm / print_bed**
    """
    if board.shape == "gridfinity":
        return (float(board.units_x) * GRU, float(board.units_y) * GRU)

    if board.size_mode == "custom":
        if board.width_mm is None or board.height_mm is None:
            raise GeometryError("INVALID_SIZE_MODE",
                                "sizeMode='custom' 但缺少 width_mm / height_mm")
        return (float(board.width_mm), float(board.height_mm))

    if board.size_mode == "print-bed":
        return (float(board.print_bed["x"]) - 2.0 * EDGE_MM,
                float(board.print_bed["y"]) - 2.0 * EDGE_MM)

    # fit-tools
    minx, miny, maxx, maxy = _as_bbox(tools)
    return (maxx - minx + 2.0 * board.margin, maxy - miny + 2.0 * board.margin)


def build_board(board: BoardConfig, size: tuple[float, float]) -> mf.Manifold:
    """rect：圆角矩形 CrossSection → extrude(thickness)，z ∈ [0, thickness]。

    `size` 必须来自 `board_size_mm`（唯一真源），不要在这里重算。
    gridfinity 的底座/唇剖面属于 M1，M-1 明确不支持。
    """
    if board.shape == "gridfinity":
        raise GeometryError("NOT_IMPLEMENTED_M1",
                            "gridfinity 板体属 M1 范围，M-1 只实现 rect",
                            {"shape": board.shape})

    w, h = float(size[0]), float(size[1])
    if w <= 0 or h <= 0:
        raise GeometryError("GEOMETRY_INVALID", "板尺寸非正", {"size": [w, h]})

    thickness = float(board.thickness)
    # corner_r 不能超过短边的一半，否则 offset(-r) 会把矩形吃成空集。
    r = min(float(board.corner_r), w / 2.0 - _EPS, h / 2.0 - _EPS)
    r = max(r, 0.0)

    ring = np.asarray(
        [(-w / 2.0, -h / 2.0), (w / 2.0, -h / 2.0), (w / 2.0, h / 2.0), (-w / 2.0, h / 2.0)],
        dtype=float,
    )
    cs = mf.CrossSection([ring])
    if r > 0:
        # 内缩再外扩 = 圆角矩形（JoinType.Round 外扩把尖角变圆角）。
        cs = cs.offset(-r).offset(r, mf.JoinType.Round)
    if cs.area() <= 0:
        raise GeometryError("GEOMETRY_INVALID", "板截面面积为非正",
                            {"size": [w, h], "corner_r": r})

    solid = mf.Manifold.extrude(cs, thickness)
    # z ∈ [0, thickness]；**不**做 ±H/2 居中（F1 成因）。
    return solid
