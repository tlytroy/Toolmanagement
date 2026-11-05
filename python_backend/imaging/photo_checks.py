# Ported from tracefinity/tracefinity (MIT License)
# Copyright (c) 2024 Tracefinity Contributors
# https://github.com/tracefinity/tracefinity
"""照片体检：在用户开始描轮廓之前，先把「这张照片拍得行不行」说清楚。

移植自 tracefinity `app/services/photo_checks.py`。

三条检查（全部**建议性**，任何一条算不出来就静默跳过，绝不抛异常）：

| code | 触发条件 | 依据 |
|---|---|---|
| `camera_too_close`     | 估算的相机高度 < 450 mm | 针孔模型：纸的对角像素长 vs 35mm 等效焦距 |
| `paper_out_of_frame`   | 有角点距画面边缘 ≤ 2 px | 纸被裁掉了，四角定位会偏 |
| `extreme_perspective`  | 对边长度比 > 1.35 | 强梯形畸变，正投影假设失效 |

★ 防「恒真告警」：三条检查都要求**具体数值越界**才报警。正常照片（纸占画面
  约 1/3、四角离边 100+ px、对边比 ~1.0）必须一条都不报——这是 M0 DoD ⑧。

▸ 相对原版的差异（逐条说明，都是有意的）：
  1. **EXIF 缺失时回退到 26mm 等效焦距**（`DEFAULT_FOCAL_LENGTH_35MM`）。
     原版在 `focal_length_35mm is None` 时直接放弃检查；但手机导出、截图、微信
     转存几乎都会剥掉 EXIF，那样 `camera_too_close` 在本项目里等于永远不报。
     M0 DoD ⑤ 要求「近距离照片必须报出估算高度」，所以这里改成带标注的回退：
     `detail.focalSource` 为 `'exif'` 或 `'assumed'`，前端可以据此弱化措辞。
  2. `PhotoWarning` 用本项目的 dataclass（`python_backend.domain` 里没有对应模型），
     并提供 `to_api_dict()` 按 SDS §4.1 输出 camelCase / 大写 code。
  3. `check_photo` 额外接收 `image_w`/`image_h` 的缺省（从 ndarray 取），方便调用。
"""
from __future__ import annotations

import io
import logging
import math
from dataclasses import dataclass, field

from python_backend.imaging.constants import paper_mm

logger = logging.getLogger(__name__)

Corners = list[tuple[float, float]]

# 36×24mm 全画幅对角线；FocalLengthIn35mmFilm 就是按它定义的
FULL_FRAME_DIAG_MM = math.hypot(36.0, 24.0)

# 低于这个高度，15mm 厚的工具会描得偏大 ~3.5%（H/(H-t)）
MIN_CAMERA_HEIGHT_MM = 450.0
REFERENCE_TOOL_THICKNESS_MM = 15.0

# EXIF 缺失时的回退焦距（mm，35mm 等效）。26mm 是近五年手机主摄的常见值。
DEFAULT_FOCAL_LENGTH_35MM = 26.0

# 角点离画面边缘这么近（px）就认为纸被裁掉了
EDGE_MARGIN_PX = 2.0

# 对边长度比超过这个值就是强梯形畸变（上游 tracefinity 的取值）
MAX_OPPOSITE_SIDE_RATIO = 1.35

# code 与 SDS §4.1 的大写口径对应
SDS_CODE = {
    "camera_too_close": "CAMERA_TOO_CLOSE",
    "paper_out_of_frame": "PAPER_OUT_OF_FRAME",
    "extreme_perspective": "EXTREME_PERSPECTIVE",
}


@dataclass(frozen=True)
class PhotoWarning:
    """一条照片体检告警。

    `code` 用 snake_case（与 M0 DoD / 上游一致）；`to_api_dict()` 输出 SDS §4.1 的
    大写口径。`detail` 里的数值一律显式带单位后缀，避免前端猜。
    """

    code: str
    message: str
    detail: dict = field(default_factory=dict)

    def to_api_dict(self, *, sds: bool = True) -> dict:
        return {
            "code": SDS_CODE.get(self.code, self.code.upper()) if sds else self.code,
            "message": self.message,
            "detail": dict(self.detail),
        }


def extract_focal_length_35mm(content: bytes) -> float | None:
    """从图片字节里读 FocalLengthIn35mmFilm；没有就返回 None。

    异常一律吞掉：EXIF 是可选的，读失败不应该让整条链路失败。
    """
    try:
        from PIL import ExifTags, Image

        img = Image.open(io.BytesIO(content))
        exif = img.getexif()
        value = exif.get_ifd(ExifTags.IFD.Exif).get(ExifTags.Base.FocalLengthIn35mmFilm)
        if value is None:
            value = exif.get(ExifTags.Base.FocalLengthIn35mmFilm)
        if value is None:
            return None
        focal = float(value)
        # 伪造的 EXIF 可能给出 inf/nan
        return focal if math.isfinite(focal) and focal > 0 else None
    except Exception:  # noqa: BLE001 —— EXIF 缺失是常态，不是错误
        logger.debug("read focal length failed", exc_info=True)
        return None


def estimate_camera_height_mm(
    corners: Corners,
    image_w: float,
    image_h: float,
    paper_size: str = "a4",
    focal_length_35mm: float | None = None,
    *,
    assume_focal_if_missing: bool = True,
) -> float | None:
    """用纸的对角投影长度估算相机到纸的距离（mm）。

    针孔模型，把画面斜边映射到全画幅斜边：

        sensor_diag_mm = paper_diag_px / image_diag_px * 43.27
        D              = f35 * paper_diag_mm / sensor_diag_mm

    焦距缺失且 `assume_focal_if_missing` 为真时用 `DEFAULT_FOCAL_LENGTH_35MM`。
    """
    if len(corners) != 4 or image_w <= 0 or image_h <= 0:
        return None

    focal = focal_length_35mm
    if focal is None or not math.isfinite(focal) or focal <= 0:
        if not assume_focal_if_missing:
            return None
        focal = DEFAULT_FOCAL_LENGTH_35MM

    tl, tr, br, bl = [(float(c[0]), float(c[1])) for c in corners]
    paper_diag_px = (math.dist(tl, br) + math.dist(tr, bl)) / 2.0
    image_diag_px = math.hypot(image_w, image_h)
    if paper_diag_px < 1.0 or image_diag_px <= 0:
        return None

    w_mm, h_mm = paper_mm(paper_size, None)
    paper_diag_mm = math.hypot(w_mm, h_mm)
    sensor_diag_mm = paper_diag_px * FULL_FRAME_DIAG_MM / image_diag_px
    if sensor_diag_mm <= 0:
        return None
    return focal * paper_diag_mm / sensor_diag_mm


def _check_camera_height(
    corners: Corners,
    image_w: float,
    image_h: float,
    paper_size: str,
    focal_length_35mm: float | None,
) -> PhotoWarning | None:
    height = estimate_camera_height_mm(corners, image_w, image_h, paper_size, focal_length_35mm)
    if height is None or height >= MIN_CAMERA_HEIGHT_MM:
        return None

    focal_source = "exif"
    if focal_length_35mm is None or not math.isfinite(focal_length_35mm) or focal_length_35mm <= 0:
        focal_source = "assumed"

    if height > REFERENCE_TOOL_THICKNESS_MM * 2:
        oversize_pct = (height / (height - REFERENCE_TOOL_THICKNESS_MM) - 1.0) * 100.0
        detail_text = f"a 15 mm-thick tool would trace roughly {oversize_pct:.1f}% oversized"
    else:
        oversize_pct = None
        detail_text = "thick tools will trace well oversized"

    height_cm = round(height / 10.0)
    return PhotoWarning(
        code="camera_too_close",
        message=(
            f"Camera looks about {height_cm} cm from the paper; {detail_text}. "
            "Retake from 60 cm or higher for best accuracy."
        ),
        detail={
            "estimatedHeightMm": round(float(height), 1),
            "minHeightMm": MIN_CAMERA_HEIGHT_MM,
            "thicknessErrorPercent": None if oversize_pct is None else round(oversize_pct, 2),
            "focalSource": focal_source,
        },
    )


def _check_paper_in_frame(corners: Corners, image_w: float, image_h: float) -> PhotoWarning | None:
    for x, y in corners:
        if (
            x <= EDGE_MARGIN_PX
            or y <= EDGE_MARGIN_PX
            or x >= image_w - EDGE_MARGIN_PX
            or y >= image_h - EDGE_MARGIN_PX
        ):
            return PhotoWarning(
                code="paper_out_of_frame",
                message=(
                    "The paper looks cut off at the photo edge. Keep all four "
                    "corners inside the frame or scale accuracy may suffer."
                ),
                detail={"edgeMarginPx": EDGE_MARGIN_PX},
            )
    return None


def _opposite_side_ratio(corners: Corners) -> float | None:
    """四边形对边长度的最大比值 max(max/min of top-bottom, max/min of left-right)。"""
    if len(corners) != 4:
        return None
    tl, tr, br, bl = [(float(c[0]), float(c[1])) for c in corners]
    top = math.dist(tl, tr)
    bottom = math.dist(bl, br)
    left = math.dist(tl, bl)
    right = math.dist(tr, br)
    if min(top, bottom, left, right) < 1.0:
        return None
    return max(max(top, bottom) / min(top, bottom), max(left, right) / min(left, right))


def _check_perspective(corners: Corners) -> PhotoWarning | None:
    ratio = _opposite_side_ratio(corners)
    if ratio is None or ratio <= MAX_OPPOSITE_SIDE_RATIO:
        return None
    return PhotoWarning(
        code="extreme_perspective",
        message=(
            "Strong camera angle detected. Shoot from directly above the "
            "paper for the most accurate outlines."
        ),
        detail={"oppositeSideRatio": round(float(ratio), 3), "maxRatio": MAX_OPPOSITE_SIDE_RATIO},
    )


def check_photo(
    corners: Corners,
    image_w: float,
    image_h: float,
    paper_size: str = "a4",
    focal_length_35mm: float | None = None,
) -> list[PhotoWarning]:
    """跑完三条检查，返回告警列表（正常照片返回空列表）。

    每条检查各自兜异常：算不出来就跳过，不影响其它两条。
    """
    warnings: list[PhotoWarning] = []
    checks = (
        lambda: _check_camera_height(corners, image_w, image_h, paper_size, focal_length_35mm),
        lambda: _check_paper_in_frame(corners, image_w, image_h),
        lambda: _check_perspective(corners),
    )
    for check in checks:
        try:
            warning = check()
        except Exception:  # noqa: BLE001 —— 体检是建议性的，不能把主链路拖垮
            logger.exception("photo check failed")
            continue
        if warning:
            warnings.append(warning)
    return warnings


def check_photo_from_image(
    corners: Corners,
    img,
    paper_size: str = "a4",
    focal_length_35mm: float | None = None,
) -> list[PhotoWarning]:
    """用 ndarray 的尺寸做检查（`img.shape` 是 (h, w, c)）。"""
    h, w = img.shape[:2]
    return check_photo(corners, float(w), float(h), paper_size, focal_length_35mm)
