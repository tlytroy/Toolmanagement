# Ported from tracefinity/tracefinity (MIT License)
# Copyright (c) 2024 Tracefinity Contributors
# https://github.com/tracefinity/tracefinity
"""透视矫正：把任意角度的纸面照片 warp 成固定 10 px/mm 的俯视图。

移植自 tracefinity `app/services/image_processor.py` 的
`pick_paper_orientation` / `_quad_aspect_ratio` / `apply_perspective_correction`。

★ 毫米链铁律（SDS §2.2）：本模块**只有一处**像素→毫米的换算，且只用
  `PX_PER_MM` 固定常量。**没有**任何「按纸边像素长度 / 打印床尺寸推比例」的代码。
  同一张图，无论板/床是 220mm 还是 400mm，输出画布都**完全相同**（M0 DoD ④）。

★ 输出画布 = 纸面 + 四周各 15mm 安全边，尺寸写死为
  `(纸宽 + 30) * 10 × (纸高 + 30) * 10`；A4 竖 = 2400×3270。

▸ 相对原版的差异：
  1. 原版输出画布是「纸 + 全视野扩展」（`max_extent` 裁剪），尺寸随照片变化；
     本版**固定画布**，纸外超出 15mm 的部分会被裁掉（SDS §2.2 要求画布写死）。
  2. 原版返回 `(path, scale_factor)` 并落盘；本版返回 dataclass，图像留在内存，
     由调用方（API 层）决定是否编码 PNG。
  3. 入参是 BGR ndarray 而不是文件路径。
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

import cv2
import numpy as np

from imaging.constants import (
    MM_PER_PX,
    PX_PER_MM,
    canvas_px_for,
    paper_mm,
    paper_origin_px,
    paper_rect_px_for,
)

logger = logging.getLogger(__name__)

Corners = list[tuple[float, float]]


@dataclass
class CorrectionResult:
    """`correct_perspective` 的返回值。

    字段名对应 SDS §4.2 的响应（API 层只做 camelCase 改名）：

    - `warped`            : BGR ndarray，尺寸 == `canvas_px`
    - `canvas_px`         : `(w, h)` 像素
    - `paper_origin_px`   : 纸左上角在画布里的像素位置
    - `paper_mm`          : `(w_mm, h_mm)` 纸面毫米
    - `mm_per_px`         : 常量回显 0.1，**下游禁止读**
    - `orientation`       : 'portrait' | 'landscape'
    - `transform`         : 3×3 源图 → 画布的透视矩阵（调试用）
    """

    warped: np.ndarray
    canvas_px: tuple[int, int]
    paper_origin_px: tuple[float, float]
    paper_mm: tuple[float, float]
    mm_per_px: float = MM_PER_PX
    orientation: str = "portrait"
    transform: np.ndarray | None = None
    meta: dict = field(default_factory=dict)


def _quad_aspect_ratio(
    corners: Corners, principal_point: tuple[float, float]
) -> float | None:
    """从投影四边形反推「背后矩形」的宽高比。

    Zhang & He, "Whiteboard scanning and image enhancement"：主点取图像中心时，
    焦距与矩形宽高比有闭式解。四边形没有透视（灭点在无穷远）时退化，返回 None。

    corners 顺序 TL, TR, BR, BL。
    """
    u0, v0 = principal_point
    tl, tr, br, bl = corners
    m1 = np.array([tl[0], tl[1], 1.0])
    m2 = np.array([tr[0], tr[1], 1.0])
    m3 = np.array([bl[0], bl[1], 1.0])
    m4 = np.array([br[0], br[1], 1.0])

    denom2 = np.cross(m2, m4) @ m3
    denom3 = np.cross(m3, m4) @ m2
    if abs(denom2) < 1e-9 or abs(denom3) < 1e-9:
        return None
    k2 = (np.cross(m1, m4) @ m3) / denom2
    k3 = (np.cross(m1, m4) @ m2) / denom3

    n2 = k2 * m2 - m1
    n3 = k3 * m3 - m1

    flat2 = abs(n2[2]) < 1e-4
    flat3 = abs(n3[2]) < 1e-4

    if flat2 and flat3:
        # 纸面平行于像平面：比例就是像素长度比
        len2 = math.hypot(n2[0], n2[1])
        len3 = math.hypot(n3[0], n3[1])
        if len3 < 1e-9:
            return None
        return float(len2 / len3)

    if flat2 or flat3:
        # 一组对边平行于像平面：焦距（进而比例）从四边形本身不可解
        return None

    f_sq = -(
        (n2[0] * n3[0] - (n2[0] * n3[2] + n2[2] * n3[0]) * u0 + n2[2] * n3[2] * u0 * u0)
        + (n2[1] * n3[1] - (n2[1] * n3[2] + n2[2] * n3[1]) * v0 + n2[2] * n3[2] * v0 * v0)
    ) / (n2[2] * n3[2])
    if not np.isfinite(f_sq) or f_sq <= 1.0:
        return None
    f = math.sqrt(float(f_sq))

    a = np.array([[f, 0.0, u0], [0.0, f, v0], [0.0, 0.0, 1.0]])
    ata_inv = np.linalg.inv(a @ a.T)
    num = float(n2 @ ata_inv @ n2)
    den = float(n3 @ ata_inv @ n3)
    if den <= 0 or num <= 0:
        return None
    return math.sqrt(num / den)


def pick_paper_orientation(
    corners: Corners,
    width_mm: float,
    height_mm: float,
    principal_point: tuple[float, float] | None = None,
) -> tuple[float, float, str]:
    """决定纸在照片里是竖放还是横放，返回 (w_mm, h_mm, 'portrait'|'landscape')。

    ★ **闭式长宽比判断**：先用 `_quad_aspect_ratio` 反推矩形真实宽高比 `r`，
      再把 `r` 与纸的两种朝向比较——取对数距离更小的那个：

          |log(r / (w/h))|  <=  |log(r / (h/w))|   → 竖放

      不用 `if h > w` / `if top_px > left_px` 这类像素长度猜测：透视下长边会被
      压缩得比短边还短，朴素比较会翻错。
    """
    src = np.array(corners, dtype=np.float64)
    if src.shape != (4, 2):
        raise ValueError(f"corners 必须是 4×2，收到 {src.shape}")
    if principal_point is None:
        principal_point = (float(src[:, 0].mean()), float(src[:, 1].mean()))

    portrait = (min(width_mm, height_mm), max(width_mm, height_mm))
    landscape = (portrait[1], portrait[0])
    portrait_ratio = portrait[0] / portrait[1]

    estimated = _quad_aspect_ratio(corners, principal_point)
    if estimated is not None and estimated > 0 and math.isfinite(estimated):
        # 距离取对数：宽高比是比例量，1/2 与 2 应当对称地「远」
        if abs(math.log(estimated / portrait_ratio)) <= abs(math.log(estimated * portrait_ratio)):
            return portrait[0], portrait[1], "portrait"
        return landscape[0], landscape[1], "landscape"

    # 退化四边形（无透视 / 主点解不出焦距）：退回像素边长比较
    top = float(np.linalg.norm(src[1] - src[0]))
    left = float(np.linalg.norm(src[3] - src[0]))
    if top > left:
        return landscape[0], landscape[1], "landscape"
    return portrait[0], portrait[1], "portrait"


def correct_perspective(
    img: np.ndarray,
    corners: Corners,
    paper_size: str = "a4",
    orientation: str | None = None,
    principal_point: tuple[float, float] | None = None,
) -> CorrectionResult:
    """把纸面 warp 成固定 10 px/mm 的俯视图，画布写死为 2400×3270（A4 竖）。

    参数
    ----
    img          : BGR 源图
    corners      : 源图像素四角，顺序 TL, TR, BR, BL
    paper_size   : `constants.PAPER_SIZES` 的键，默认 'a4'
    orientation  : 'portrait' | 'landscape' | None（None 时用闭式长宽比判断）
    principal_point : 主点，默认图像中心

    返回 `CorrectionResult`。

    ★ 这里**没有**任何来自打印床 / 板尺寸的参数——签名里根本没有它们。
      DoD ④（220mm 床与 400mm 床 canvasPx 相同）在结构上就成立。
    """
    if img is None or img.ndim != 3:
        raise ValueError("img 必须是 BGR 三通道图像")

    src = np.asarray(corners, dtype=np.float32)
    if src.shape != (4, 2):
        raise ValueError(f"corners 必须是 4×2，收到 {src.shape}")

    h_img, w_img = img.shape[:2]
    if principal_point is None:
        principal_point = (w_img / 2.0, h_img / 2.0)

    base_w, base_h = paper_mm(paper_size, None)
    if orientation in ("portrait", "landscape"):
        w_mm, h_mm = paper_mm(paper_size, orientation)
        chosen = orientation
    else:
        w_mm, h_mm, chosen = pick_paper_orientation(src, base_w, base_h, principal_point)

    # 纸面在**画布**里的目标矩形（像素）—— 固定常量，不读任何外部尺寸
    ox, oy = paper_origin_px()
    paper_w_px = w_mm * PX_PER_MM
    paper_h_px = h_mm * PX_PER_MM
    dst = np.array(
        [
            [ox, oy],
            [ox + paper_w_px, oy],
            [ox + paper_w_px, oy + paper_h_px],
            [ox, oy + paper_h_px],
        ],
        dtype=np.float32,
    )

    M = cv2.getPerspectiveTransform(src, dst)

    canvas_w, canvas_h = canvas_px_for(w_mm, h_mm)
    # 源图 → 画布。纸面之外的区域由 warpPerspective 的边界填充处理，
    # 不做「全视野扩展」——画布尺寸必须写死（SDS §2.2）。
    warped = cv2.warpPerspective(
        img, M, (canvas_w, canvas_h), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0)
    )

    return CorrectionResult(
        warped=warped,
        canvas_px=(canvas_w, canvas_h),
        paper_origin_px=(ox, oy),
        paper_mm=(float(w_mm), float(h_mm)),
        mm_per_px=MM_PER_PX,
        orientation=chosen,
        transform=M,
        meta={"paper_rect_px": paper_rect_px_for(w_mm, h_mm)},
    )
