"""geometry 包：M-1 最小几何骨架。

对外只暴露 `generate_insert(project)`，其余是内部实现细节。
本包**不** import cv2 / trimesh，纯几何可离线测（SDS §10.1 架构约束）。

★ 导入根是 `python_backend/`（不是仓库根）：`main.py` 在 `cd python_backend` 下跑，
  `cad_engine.py:59` 是裸 `from models import`，所以 `python_backend` 必须是唯一的
  导入根，包内一律 `from domain.xxx` / `from geometry.xxx`（**不加** `python_backend.` 前缀）。
"""
from __future__ import annotations

import manifold3d as mf

from domain.models import Project
from geometry.board import board_center, board_size_mm, build_board
from geometry.constants import board_depth_limit, board_top_z
from geometry.finger_holes import build_finger_hole_cutter, scoop_edge_distance
from geometry.pockets import (
    build_pocket_cutter,
    pocket_shape,
    resolve_chamfer,
    resolve_clearance,
    resolve_depth,
)
from geometry.polygon import (
    GeometryError,
    make_shape,
    normalize_winding,
    signed_area,
    to_board_frame,
)

__all__ = [
    "GeometryError",
    "board_center",
    "board_depth_limit",
    "board_size_mm",
    "board_top_z",
    "build_board",
    "build_pocket_cutter",
    "generate_insert",
    "make_shape",
    "normalize_winding",
    "pocket_shape",
    "resolve_chamfer",
    "resolve_clearance",
    "resolve_depth",
    "signed_area",
    "to_board_frame",
]

# 板内判定容差（mm）：只吸收浮点误差，**不**用来"放过"越界。
_BOARD_EPS_MM = 1e-6


def _board_exits(size_mode: str) -> list[str]:
    """`TOOL_OUT_OF_BOARD` 的可执行出路（SDS §7.6 第 9 条：必须按模式给）。"""
    if size_mode == "custom":
        return [
            "调大 widthMm / heightMm",
            "把该工具移出本板（hidden=true 或删除）",
            "改用 sizeMode='fit-tools'",
        ]
    if size_mode == "print-bed":
        return [
            "把该工具移出本板（hidden=true 或删除）",
            "改用 sizeMode='custom' 并调大宽高",
            "开启分块（SDS §8，M1 范围）",
        ]
    # fit-tools：板是按工具并集算的，理论上到不了这里；真到了说明工具/板不自洽。
    return [
        "缩小 margin",
        "把该工具移出本板（hidden=true 或删除）",
        "改用 sizeMode='custom' 并调大宽高",
    ]


def _assert_tool_in_board(
    tool,
    shape,
    size: tuple[float, float],
    size_mode: str,
) -> None:
    """`tools_in_board`（SDS §7.6 第 9 条，**阻断**）：槽必须完全落在板框内。

    ★ 判定口径（保守）：板在板局部坐标里以原点为中心、占
      `[-w/2, w/2] × [-h/2, h/2]`，这里拿**已加 clearance 的槽轮廓外接框**
      与该矩形比 —— 按**矩形框**判、**不**扣 `corner_r` 的圆角。
      理由：扣圆角会让"刚好卡在角上"的工具被判通过，而圆角处实际是空的，
      宁严勿松。`fit-tools` 下 bbox + 2*margin 天然满足，这条在那里当回归锚。
    ★ 越界一律**阻断**，**不**自动放大板、**不** clamp（SDS §12.3 明列）。
    """
    half_w = float(size[0]) / 2.0
    half_h = float(size[1]) / 2.0
    minx, miny, maxx, maxy = (float(v) for v in shape.bounds)
    overflow = {
        "left": max(0.0, -half_w - minx),
        "right": max(0.0, maxx - half_w),
        "bottom": max(0.0, -half_h - miny),
        "top": max(0.0, maxy - half_h),
    }
    if all(v <= _BOARD_EPS_MM for v in overflow.values()):
        return
    raise GeometryError(
        "TOOL_OUT_OF_BOARD",
        f"工具 {tool.id} 的槽超出板框（板 {size[0]:.1f}×{size[1]:.1f}mm）",
        {
            "toolId": tool.id,
            "boardMm": (float(size[0]), float(size[1])),
            "toolBBox": (minx, miny, maxx, maxy),
            "sizeMode": size_mode,
            "overflowMm": overflow,
            "exits": _board_exits(size_mode),
        },
    )


def generate_insert(project: Project, depth: float | None = None) -> dict:
    """最小可用生成链路（M-1 版本）。

    返回 dict：
      `base`              : 板实体减去所有槽切刀后的 `Manifold`
      `base_uncut`        : 未开槽的板实体
      `slot_cutter`       : 所有槽切刀的 union（单槽时就是那把切刀）
      `pocket_length_mm`  : 第一个**可见**工具的槽在板局部 x 方向的长度
      `board_mm`          : `(w, h)`
      `top_z`             : 板顶面 z
      `warnings`          : 告警列表（dict，含 code / message / detail）
      `tools`             : 每个工具一条 `{id, depth, clearance, chamfer, pocket_length_mm}`

    ★ 单次派生铁律（M-1 审核缺陷 1 / 2 的修复本体）：
      每个工具在**本函数里**只调一次 `resolve_depth`、只调一次 `pocket_shape`，
      然后把结果（`depth` / `shape` / `clearance` / `chamfer`）**显式**传给
      `build_pocket_cutter`。切刀构造函数只在形参为 None 时才自己派生 —— 否则
      `warnings_out` 会被同一条告警追加两次（信封里出现重复 `SELF_INTERSECTION_REPAIRED`
      / `CLEARANCE_CLOSED_HOLE`），`DEPTH_EXCEEDS_THICKNESS` 也会发两遍。

    ★ `pocket_length_mm` 的取法（SDS §10.1 要求注释写明）：
      直接取**槽切刀 CrossSection 的 x 方向宽度** = `shape.bounds[2] - shape.bounds[0]`，
      而不是去量 3D 实体或 trimesh 的 bbox。`clearance = 0` 时它正好等于工具轮廓的
      x 跨度（合成件 100mm → 100.0）。选这条是因为它**只受简化/间隙影响**，不受
      `scale_top` 倒角锥台把 3D bbox 撑宽的影响（倒角会让 `Manifold.bounding_box()`
      的 x 跨度变成 100 + 2*chamfer，用它量槽长会假红）。
    """
    warnings_out: list[dict] = []
    board = project.board

    visible = [t for t in project.tools if not t.hidden and len(t.outer) >= 3]
    if not visible:
        raise GeometryError("NO_VISIBLE_TOOLS", "没有可参与生成的工具（全部隐藏或为空）")

    center = board_center(visible)
    size = board_size_mm(board, visible)
    top_z = board_top_z(board)

    base_uncut = build_board(board, size)

    cutters: list[mf.Manifold] = []
    tool_reports: list[dict] = []
    for tool in visible:
        # —— 每个局部量只派生一次（告警因此也只发一次）——
        eff_depth = resolve_depth(tool, board, depth, warnings_out=warnings_out)
        clr = resolve_clearance(tool, board)
        chamfer = resolve_chamfer(tool, board)
        shape = pocket_shape(tool, board, center, warnings_out, clearance=clr)

        # tools_in_board：板框校验必须在布尔之前（阻断，不自动放大板）
        _assert_tool_in_board(tool, shape, size, board.size_mode)

        sb = shape.bounds                      # 扁平 4 元组 (minx, miny, maxx, maxy)
        pocket_len = float(sb[2] - sb[0])

        # 已算好的 shape / 各局部量直接复用 —— 切刀内部不再重算，也不再追加告警
        cutter = build_pocket_cutter(
            tool, board, center,
            depth=eff_depth, shape=shape, clearance=clr, chamfer=chamfer,
            warnings_out=warnings_out,
        )
        cutters.append(cutter)

        # —— 手孔切刀（SDS §7.4/§7.5）：每个手孔一个 cutter，并入同一次布尔 ——
        hole_reports: list[dict] = []
        for fh in tool.finger_holes:
            d_edge = None
            if fh.shape == "scoop":
                # scoop 的 d_edge 必须是实测「槽壁到板轮廓」距离，不是 margin
                d_edge = scoop_edge_distance(shape, base_uncut, top_z)
            fh_cutter = build_finger_hole_cutter(
                fh, board, center,
                d_edge=d_edge, clearance=clr, warnings_out=warnings_out,
            )
            cutters.append(fh_cutter)
            hole_reports.append({"id": fh.id, "shape": fh.shape})

        tool_reports.append({
            "id": tool.id,
            "depth": eff_depth,
            "clearance": clr,
            "chamfer": chamfer,
            "pocket_length_mm": pocket_len,
            "finger_holes": hole_reports,
        })

    slot_cutter = cutters[0]
    for c in cutters[1:]:
        slot_cutter = slot_cutter + c

    base = base_uncut - slot_cutter
    if base.is_empty():
        raise GeometryError("GEOMETRY_INVALID", "板体被切刀完全切除",
                            {"cutters": len(cutters)})

    return {
        "base": base,
        "base_uncut": base_uncut,
        "slot_cutter": slot_cutter,
        "pocket_length_mm": tool_reports[0]["pocket_length_mm"],
        "board_mm": (float(size[0]), float(size[1])),
        "top_z": top_z,
        "warnings": warnings_out,
        "tools": tool_reports,
    }
