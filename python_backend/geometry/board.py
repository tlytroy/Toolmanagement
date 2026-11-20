"""板体：尺寸决策（`board_size_mm`）与实体构造（`build_board`）。

★ `build_board` 的 z 范围恒为 `[0, board_top_z(board)]`（板底面 z=0），
  **绝不** `apply_translation([0, 0, -size_z/2])` 居中 —— 那是 F1 的成因。
  rect: top_z = thickness；gridfinity: top_z = height_u * 7。
"""
from __future__ import annotations

import math

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


def derive_units(size_mode: str, bbox: tuple[float, float, float, float],
                 margin: float, width_mm: float | None, height_mm: float | None,
                 print_bed: dict) -> tuple[int, int]:
    """由 sizeMode 派生 gridfinity 格数（SDS §7.2 表，后端唯一真源，前端只回显）。"""
    minx, miny, maxx, maxy = bbox
    if size_mode == "fit-tools":
        ux = int(math.ceil((maxx - minx + 2.0 * margin) / GRU))
        uy = int(math.ceil((maxy - miny + 2.0 * margin) / GRU))
    elif size_mode == "custom":
        ux = int(math.ceil(float(width_mm) / GRU)) if width_mm else 1
        uy = int(math.ceil(float(height_mm) / GRU)) if height_mm else 1
    elif size_mode == "print-bed":
        ux = int(math.floor((float(print_bed["x"]) - 2.0 * EDGE_MM) / GRU))
        uy = int(math.floor((float(print_bed["y"]) - 2.0 * EDGE_MM) / GRU))
    else:
        raise GeometryError("INVALID_SIZE_MODE", "未知 sizeMode", {"sizeMode": size_mode})
    return (max(1, ux), max(1, uy))


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
    """按外形构造板实体，z ∈ [0, board_top_z(board)]（不居中，F1 铁律）。

    rect       : 圆角矩形 CrossSection → extrude(thickness)
    gridfinity : 底座三段收腰 + 直壁 + 可选堆叠唇环槽 + 可选磁孔（geometry.gridfinity）
    `size` 必须来自 `board_size_mm`（唯一真源），不要在这里重算。
    """
    if board.shape == "gridfinity":
        from geometry.gridfinity import build_gridfinity_board
        ux = int(round(float(size[0]) / GRU))
        uy = int(round(float(size[1]) / GRU))
        return build_gridfinity_board(
            units_x=ux, units_y=uy, height_u=int(board.height_u),
            magnets=bool(board.magnets), stacking_lip=bool(board.stacking_lip),
        )

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
