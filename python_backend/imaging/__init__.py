# Ported from tracefinity/tracefinity (MIT License)
# Copyright (c) 2024 Tracefinity Contributors
# https://github.com/tracefinity/tracefinity
"""imaging 包：唯一允许 import cv2 / skimage 的地方（SDS §10.1）。

对外只暴露三类东西：

- `constants`   : `PX_PER_MM` 固定常量 + 画布换算（纯算术，不 import cv2）
- `paper`       : 找纸四角（源图像素）
- `perspective` : 透视矫正到固定 10 px/mm 画布
- `photo_checks`: 照片体检（三条建议性告警）
- `api`         : SDS §4.1 / §4.2 响应装配

★ 毫米链：`mm = px / PX_PER_MM`，全项目唯一换算方向。
  `MM_PER_PX`（0.1）只作 API 回显，**下游禁止读**。
"""
from __future__ import annotations

from python_backend.imaging.api import (
    ImagingError,
    correct_image_response,
    decode_image,
    detect_paper_response,
    encode_png_base64,
)
from python_backend.imaging.constants import (
    MM_PER_PX,
    PX_PER_MM,
    SAFE_MARGIN_MM,
    canvas_px_for,
    paper_mm,
    paper_origin_px,
    paper_rect_px_for,
)
from python_backend.imaging.paper import detect_paper_corners, order_corners
from python_backend.imaging.perspective import (
    CorrectionResult,
    correct_perspective,
    pick_paper_orientation,
)
from python_backend.imaging.photo_checks import (
    PhotoWarning,
    check_photo,
    check_photo_from_image,
    estimate_camera_height_mm,
    extract_focal_length_35mm,
)

__all__ = [
    "CorrectionResult",
    "ImagingError",
    "MM_PER_PX",
    "PX_PER_MM",
    "PhotoWarning",
    "SAFE_MARGIN_MM",
    "canvas_px_for",
    "check_photo",
    "check_photo_from_image",
    "correct_image_response",
    "correct_perspective",
    "decode_image",
    "detect_paper_corners",
    "detect_paper_response",
    "encode_png_base64",
    "estimate_camera_height_mm",
    "extract_focal_length_35mm",
    "order_corners",
    "paper_mm",
    "paper_origin_px",
    "paper_rect_px_for",
    "pick_paper_orientation",
]
