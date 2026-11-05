# Ported from tracefinity/tracefinity (MIT License)
# Copyright (c) 2024 Tracefinity Contributors
# https://github.com/tracefinity/tracefinity
"""成像层常量：固定 10 px/mm（M0 任务 0.4）。

★ 毫米链铁律（SDS §2.2 / 计划 v1.3 §0.4）：
  `PX_PER_MM = 10.0` 是**固定常量**，图像 → mm 只有一个方向：

      mm = px / PX_PER_MM

  **禁止**任何按纸边长度 / 打印床尺寸 / 画布尺寸动态推导的比例
  （F1 的根因就是 `scale = min(base_size_x / 840.0, base_size_y / 1188.0)`）。
  `MM_PER_PX`（= 0.1）只作常量回显，**下游任何计算禁止读它**。

★ 画布尺寸同样写死（SDS §2.2）：

      画布 = (纸宽 + 2*15) × (纸高 + 2*15) 再 × 10 px/mm
      A4 竖 = 2400 × 3270 px，纸面占 x ∈ [150, 2250]、y ∈ [150, 3120]
      A4 横 = 3270 × 2400 px

  画布**不随打印床变化**。15mm 安全边是「纸角检测误差容忍」，
  不是「板/床尺寸推导」。
"""
from __future__ import annotations

# 10 px / mm —— 全项目唯一像素密度（SDS §2.2）
PX_PER_MM = 10.0

# 纸面四周安全边（mm）。画布 = 纸面 + 2*SAFE_MARGIN_MM
SAFE_MARGIN_MM = 15.0

# 常量回显值，= 0.1。★ 只许出现在 API 响应与断言里，下游计算禁止读。
MM_PER_PX = 1.0 / PX_PER_MM

# 纸尺寸（mm），长边在前（portrait 口径）
PAPER_SIZES: dict[str, tuple[float, float]] = {
    "a4": (210.0, 297.0),
    "letter": (215.9, 279.4),
    "a3": (297.0, 420.0),
    "tabloid": (279.4, 431.8),
}

DEFAULT_PAPER = "a4"


def paper_mm(paper_size: str = DEFAULT_PAPER, orientation: str | None = None) -> tuple[float, float]:
    """纸面毫米尺寸。`orientation=None` 时按纸型的 portrait 口径返回。

    `'landscape'` 返回 (长边, 短边)，`'portrait'` 返回 (短边, 长边)。
    这里只做**常量查表**，不读任何图像信息。
    """
    try:
        w, h = PAPER_SIZES[paper_size]
    except KeyError as exc:
        raise ValueError(f"未知纸型 {paper_size!r}，可选 {sorted(PAPER_SIZES)}") from exc
    short, long_ = min(w, h), max(w, h)
    if orientation == "landscape":
        return (long_, short)
    if orientation == "portrait":
        return (short, long_)
    return (w, h)


def canvas_px_for(paper_w_mm: float, paper_h_mm: float) -> tuple[int, int]:
    """画布像素尺寸 = (纸宽 + 2*15) × (纸高 + 2*15) × 10。

    A4 竖 → (2400, 3270)；A4 横 → (3270, 2400)。
    """
    w = int(round((paper_w_mm + 2.0 * SAFE_MARGIN_MM) * PX_PER_MM))
    h = int(round((paper_h_mm + 2.0 * SAFE_MARGIN_MM) * PX_PER_MM))
    return (w, h)


def paper_origin_px() -> tuple[float, float]:
    """纸左上角在画布里的像素位置，恒为 (150.0, 150.0)。"""
    return (SAFE_MARGIN_MM * PX_PER_MM, SAFE_MARGIN_MM * PX_PER_MM)


def paper_rect_px_for(paper_w_mm: float, paper_h_mm: float) -> tuple[float, float, float, float]:
    """纸面在画布里的像素矩形 (x0, y0, x1, y1)。

    A4 竖 → (150.0, 150.0, 2250.0, 3120.0)。
    """
    ox, oy = paper_origin_px()
    return (ox, oy, ox + paper_w_mm * PX_PER_MM, oy + paper_h_mm * PX_PER_MM)
