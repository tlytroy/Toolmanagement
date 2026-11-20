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
GF_CORNER_R = 3.75    # gridfinity 外轮廓圆角半径（tracefinity GF_CORNER_R = 4.0 - 0.25 inset）

# 底座三段高度（自下而上）：0.8 + 1.8 + 2.15 = 4.75 = GR_BASE_HEIGHT
BASE_H_BOT = 0.8
BASE_H_MID = 1.8
BASE_H_TOP = 2.15

# 堆叠唇五段垂直高（tracefinity LIP_D0..D4；顺序自下而上 = D4,D3,D2,D1,D0）
LIP_D0 = 1.9
LIP_D1 = 1.8
LIP_D2 = 0.7
LIP_D3 = 1.2
LIP_D4 = LIP_D0 + LIP_D2  # 2.6
LIP_HEIGHT = 8.2      # 堆叠唇**垂直**总高（LIP_D0+D1+D2+D3+D4 = 8.2）
LIP_WIDTH = 2.6       # 堆叠唇在顶面外圈占的**径向**宽度（径向量，非垂直量）

# 磁孔（每格 4 孔，相对格心 ±13mm；φ6.5 × 2.4 深，从底面向上打）
MAGNET_OFFSET = 13.0   # 孔心相对格心的偏移（±13 → 同格相邻孔心距 26mm）
MAGNET_DIAMETER = 6.5
MAGNET_DEPTH = 2.4
# 注：tracefinity 注释 MAGNET_INSET=4.8 指「孔边到格角」（8 - 6.5/2 = 4.75≈4.8），
# **不参与定位**；「距格角 4.8」与「孔心距 26」算术互斥（42 - 2*4.8 = 32.4 ≠ 26）。

# 手孔形态判据（SDS §7.4 / §6.4）：生效 depth 的连续阈值，与板厚无关
FINGER_REACH_MM = 20.0   # 指腹可达深度：< 20 只能 scoop，>= 20 可用五种竖直孔

# 剖面/ cutter 采样精度
CIRCLE_SEGS = 48      # 2D 圆角矩形剖面每段点数
ROUND_SEGS = 128      # 3D 圆柱/球 circular_segments

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
