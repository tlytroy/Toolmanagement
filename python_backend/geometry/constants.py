"""几何常量：全项目唯一真源（SDS §7.2 / §7.4）。

M-1 只用到 `board_top_z` 与 `GRU`；其余常量先占位，供 M1 的 gridfinity 底座/唇实现。

★ z 轴铁律：板底面 z = 0，板顶面 = `board_top_z(board)`。
  全项目一切「从板顶往下 X」都写 `top_z - X`，**禁止**写 `thickness - X`
  （gridfinity 的 thickness 只有 6/12/25，板顶却是 21/28/35，混用会让切刀整体下移 9mm）。
★ 也**禁止** `apply_translation([0, 0, -size_z / 2])` 把板在 z 上居中
  （旧 `cad_engine.py:96` 的 ±H/2 居中就是 F1 的成因）。
"""
from __future__ import annotations

# —— gridfinity 尺寸常量 ——
GRHU = 7.0            # 1 个高度单位 U 的毫米数（含底座）
GRU = 42.0            # 1 个平面格子的毫米数
GR_BASE_HEIGHT = 4.75  # 底座（下倒角 + 直壁 + 上倒角）总高
LIP_HEIGHT = 8.2      # 堆叠唇**垂直**总高（五段垂直高之和）
LIP_WIDTH = 2.6       # 堆叠唇在顶面外圈占的**径向**宽度（径向量，非垂直量）

# —— 打印床边缘留白 ——
EDGE_MM = 5.0         # 'print-bed' 尺寸模式下每边留白；两边共减 2*EDGE_MM


def board_top_z(board) -> float:
    """唯一 z 基准：rect = thickness；gridfinity = height_u * GRHU。

    参数 `board` 是 `domain.models.BoardConfig`（只读它的 shape / thickness / height_u）。
    """
    if board.shape == "gridfinity":
        return float(board.height_u) * GRHU
    return float(board.thickness)


def board_depth_limit(board) -> float:
    """embed_depth 的上界（SDS §3.1 / §7.2 第 3 条）。

    rect       : thickness - 2
    gridfinity : height_u*7 - GR_BASE_HEIGHT - 2   （3U 得 14.25，不是 19）
    """
    if board.shape == "gridfinity":
        return board_top_z(board) - GR_BASE_HEIGHT - 2.0
    return float(board.thickness) - 2.0
