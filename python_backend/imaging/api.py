# Ported from tracefinity/tracefinity (MIT License)
# Copyright (c) 2024 Tracefinity Contributors
# https://github.com/tracefinity/tracefinity
"""API 层适配：把成像结果装配成 SDS §4.1 / §4.2 的响应体。

★ 本模块只做**格式转换**，不含任何几何/比例计算。像素 → 毫米的唯一换算
  在 `perspective.correct_perspective` 里，且只用 `PX_PER_MM` 固定常量。

为什么单独一层：M0 任务书禁止改 `python_backend/main.py`（冻结文件），
所以路由挂载不在本路范围；这里给出可直接被 `main.py` 调用的纯函数，
装配逻辑与 HTTP 框架解耦，也方便单测。
"""
from __future__ import annotations

import base64
import binascii

import cv2
import numpy as np

from python_backend.imaging.constants import MM_PER_PX, paper_mm
from python_backend.imaging.paper import detect_paper_corners
from python_backend.imaging.perspective import (
    CorrectionResult,
    correct_perspective,
    pick_paper_orientation,
)
from python_backend.imaging.photo_checks import check_photo


class ImagingError(ValueError):
    """成像链路的可预期失败（纸没找到、图读不出等）。

    路由层捕获后转成 `{success: false, error: {code, message, detail}}`
    （SDS §3.2 信封）；本模块**不**自己吞异常。
    """

    def __init__(self, code: str, message: str, detail: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail or {}

    def to_dict(self) -> dict:
        out = {"code": self.code, "message": self.message}
        if self.detail:
            out["detail"] = self.detail
        return out


def decode_image(content: bytes) -> np.ndarray:
    """图片字节 → BGR ndarray。解不出就抛 `ImagingError('IMAGE_DECODE_FAILED')`。"""
    if not content:
        raise ImagingError("IMAGE_EMPTY", "上传内容为空")
    buf = np.frombuffer(content, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        raise ImagingError("IMAGE_DECODE_FAILED", "无法解码图片（支持 JPEG/PNG）")
    return img


def encode_png_base64(img: np.ndarray) -> str:
    """BGR ndarray → base64 PNG（不带 `data:` 前缀，SDS §3.2）。"""
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise ImagingError("IMAGE_ENCODE_FAILED", "PNG 编码失败")
    try:
        return base64.b64encode(buf.tobytes()).decode("ascii")
    except (binascii.Error, ValueError) as exc:  # pragma: no cover - 理论不可达
        raise ImagingError("IMAGE_ENCODE_FAILED", "PNG base64 编码失败") from exc


def _warnings_payload(warnings) -> list[dict]:
    return [w.to_api_dict() for w in warnings]


def detect_paper_response(content: bytes, paper_size: str = "a4") -> dict:
    """`POST /api/detect-paper` 的 `data`（SDS §4.1）。

    `corners` 返回**纸面毫米里的规范位置**（前端画引导框用），不是源图像素——
    源图坐标不下发，避免前端混用两套坐标（SDS §4.1 明文要求）。
    """
    img = decode_image(content)
    h, w = img.shape[:2]
    src_corners = detect_paper_corners(img)
    if not src_corners:
        raise ImagingError(
            "PAPER_NOT_FOUND",
            "没有在照片里找到纸的四个角，请让整张纸都在画面内、背景对比更强",
            {"imageSize": {"w": w, "h": h}},
        )

    pw, ph = paper_mm(paper_size, None)
    warnings = check_photo(src_corners, float(w), float(h), paper_size, None)

    # 朝向走闭式长宽比判断（`pick_paper_orientation`），不用像素边长猜测
    _, _, orientation = pick_paper_orientation(
        src_corners, pw, ph, principal_point=(w / 2.0, h / 2.0)
    )
    # 规范 corners 按**实际朝向**给，横放就是 297×210
    pw, ph = paper_mm(paper_size, orientation)
    canonical = [(0.0, 0.0), (pw, 0.0), (pw, ph), (0.0, ph)]

    return {
        "corners": [{"x": float(x), "y": float(y)} for x, y in canonical],
        "orientation": orientation,
        "reprojectionError": None,  # M0 不估计重投影误差，显式给 null 而不是假的 0.0
        "imageSize": {"w": int(w), "h": int(h)},
        "warnings": _warnings_payload(warnings),
    }


def correct_image_response(
    content: bytes,
    paper_size: str = "a4",
    orientation: str | None = None,
    corners: list[tuple[float, float]] | None = None,
) -> dict:
    """`POST /api/correct-image` 的 `data`（SDS §4.2）。

    返回键与 SDS 逐字一致：

        warpedImage / mmPerPx / paperMm / canvasPx / paperOriginPx

    `mmPerPx` **只作常量回显**（0.1）。★ 下游任何计算禁止读它——
    下游只认纸面 mm（SDS §4.2 审核修订 B④）。
    """
    img = decode_image(content)
    src_corners = corners or detect_paper_corners(img)
    if not src_corners:
        raise ImagingError(
            "PAPER_NOT_FOUND",
            "没有在照片里找到纸的四个角，无法做透视矫正",
            {"imageSize": {"w": int(img.shape[1]), "h": int(img.shape[0])}},
        )

    result: CorrectionResult = correct_perspective(
        img, src_corners, paper_size=paper_size, orientation=orientation
    )
    return {
        "warpedImage": encode_png_base64(result.warped),
        "mmPerPx": MM_PER_PX,  # 常量回显 0.1，禁止下游读取
        "paperMm": {"w": result.paper_mm[0], "h": result.paper_mm[1]},
        "canvasPx": {"w": result.canvas_px[0], "h": result.canvas_px[1]},
        "paperOriginPx": {"x": result.paper_origin_px[0], "y": result.paper_origin_px[1]},
    }
