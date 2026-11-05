# Ported from tracefinity/tracefinity (MIT License)
# Copyright (c) 2024 Tracefinity Contributors
# https://github.com/tracefinity/tracefinity
"""纸面检测：从一张照片里找出 A4 纸的四个角（源图像素坐标）。

移植自 tracefinity `app/services/image_processor.py` 的 `detect_paper_corners` /
`_detect_paper` / `_find_paper_contour` / `_try_brightness_threshold` 等。

▸ 相对原版的差异（M0 有意为之，逐条说明）：
  1. **去掉 U2-Net / rembg 工具掩膜**。原版用 ONNX 分割把纸上的工具涂黑再找纸边；
     本项目的 `requirements.txt` 只有 `opencv-python-headless`，不引入 onnxruntime /
     rembg（那是 100MB+ 的模型依赖，M0 不值得）。所以只保留 OpenCV-only 路径，
     也就是原版在「无 ONNX 时」走的那条路径，行为等价。
  2. 入参从「文件路径」改成「BGR ndarray」，方便合成图测试与后续把图像留在内存里。
     需要路径版本时用 `detect_paper_corners_from_path`。

★ 本模块只输出**源图像素**四角；纸面 mm 的换算在 `perspective.py` 里，且只能用
  `PX_PER_MM` 这个固定常量（见 `constants.py` 顶部注释）。
"""
from __future__ import annotations

import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)

Corners = list[tuple[float, float]]

# 纸面候选的面积下限 / 上限（占整幅画面的比例）
MIN_AREA_FRACTION = 0.05
MAX_AREA_FRACTION = 0.85

# 候选矩形必须离画面边缘至少这么多（占 min(h,w) 的比例）
EDGE_MARGIN_FRACTION = 0.02

# 纸型长宽比的合理区间（A4 0.707 / Letter 0.773 / A3 0.707 / Tabloid 0.647）
MIN_ASPECT = 0.55
MAX_ASPECT = 0.85

# 四边形内「亮像素」占比低于此值就认为不是纸
MIN_FILL_RATIO = 0.35


def order_corners(pts: np.ndarray) -> np.ndarray:
    """把 4 个点排成 TL, TR, BR, BL。

    原版用 `argmin(sum)` / `argmax(sum)` / `argmin(diff)` / `argmax(diff)`，
    在图像坐标系（y 向下）下对凸四边形成立，直接沿用。
    """
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def _is_roughly_rectangular(approx: np.ndarray) -> bool:
    """4 点轮廓是否大致是矩形（每个内角偏离 90° 不超过 ~30°）。"""
    pts = approx.reshape(4, 2).astype(np.float64)
    for i in range(4):
        p1 = pts[i]
        p2 = pts[(i + 1) % 4]
        p3 = pts[(i + 2) % 4]
        v1 = p1 - p2
        v2 = p3 - p2
        denom = np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6
        cos_angle = float(np.dot(v1, v2) / denom)
        if abs(cos_angle) > 0.5:
            return False
    return True


def _detect_canny(gray: np.ndarray, low: int, high: int) -> np.ndarray:
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    return cv2.Canny(blur, low, high)


def _detect_adaptive_threshold(gray: np.ndarray) -> np.ndarray:
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    return cv2.Canny(thresh, 50, 150)


def _detect_saturation(img: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]
    _, thresh = cv2.threshold(sat, 30, 255, cv2.THRESH_BINARY_INV)
    return cv2.Canny(thresh, 50, 150)


def _find_paper_contour(
    edges: np.ndarray, min_area: float, max_area: float, margin: int, h: int, w: int
) -> Corners | None:
    """在边缘图里找近似矩形、不贴边的四点多边形。"""
    kernel = np.ones((3, 3), np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=2)
    edges = cv2.erode(edges, kernel, iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:10]:
        area = cv2.contourArea(contour)
        if area < min_area or area > max_area:
            continue
        x, y, cw, ch = cv2.boundingRect(contour)
        if x < margin or y < margin or x + cw > w - margin or y + ch > h - margin:
            continue
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
        if len(approx) == 4 and _is_roughly_rectangular(approx):
            corners = order_corners(approx.reshape(4, 2))
            return [(float(c[0]), float(c[1])) for c in corners]
    return None


def _has_paper_fill(gray: np.ndarray, corners: Corners) -> bool:
    """强工具轮廓不能顶掉淡纸边：四边形内部亮像素占比要够。"""
    region = np.zeros(gray.shape, dtype=np.uint8)
    cv2.fillPoly(region, [np.asarray(corners, dtype=np.int32)], 255)
    area = cv2.countNonZero(region)
    if not area:
        return False
    bright = cv2.inRange(gray, 180, 255)
    return cv2.countNonZero(cv2.bitwise_and(bright, region)) / area >= MIN_FILL_RATIO


def _try_brightness_threshold(
    gray: np.ndarray, thresh_val: int, min_area: float, max_area: float, margin: int, h: int, w: int
) -> tuple[Corners | None, float]:
    """在某个亮度阈值上找纸。返回 (corners, 面积)。"""
    _, thresh = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY)

    small_kernel = np.ones((3, 3), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, small_kernel, iterations=1)
    large_k = max(5, int(max(h, w) * 0.02) | 1)  # 约画面 2%，必须是奇数
    large_kernel = np.ones((large_k, large_k), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, large_kernel, iterations=1)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 候选 = 单个轮廓 + 合并凸包（工具把纸劈成几块时用凸包接回来）
    candidates = list(sorted(contours, key=cv2.contourArea, reverse=True)[:10])
    min_fragment = (h * w) * 0.005
    fragments = [c for c in contours if cv2.contourArea(c) >= min_fragment]
    if len(fragments) >= 2:
        hull = cv2.convexHull(np.vstack(fragments))
        candidates.insert(0, hull)

    best = None
    best_area = 0.0
    for contour in candidates:
        area = cv2.contourArea(contour)
        if area < min_area or area > max_area:
            continue
        rect = cv2.minAreaRect(contour)
        box = np.int32(cv2.boxPoints(rect))

        box_margin = margin * 2
        if np.any(box[:, 0] < box_margin) or np.any(box[:, 0] > w - box_margin):
            continue
        if np.any(box[:, 1] < box_margin) or np.any(box[:, 1] > h - box_margin):
            continue

        rect_mask = np.zeros(gray.shape, dtype=np.uint8)
        cv2.fillPoly(rect_mask, [box], 255)
        bright_pixels = cv2.countNonZero(cv2.bitwise_and(thresh, rect_mask))
        total_pixels = cv2.countNonZero(rect_mask)
        fill_ratio = bright_pixels / total_pixels if total_pixels > 0 else 0.0
        if fill_ratio < MIN_FILL_RATIO:
            continue

        rect_w, rect_h = rect[1]
        if rect_w == 0 or rect_h == 0:
            continue
        aspect = min(rect_w, rect_h) / max(rect_w, rect_h)
        if aspect < MIN_ASPECT or aspect > MAX_ASPECT:
            continue

        if area > best_area:
            best = box
            best_area = float(area)

    if best is None:
        return None, 0.0
    corners = order_corners(best.astype(np.float32))
    return [(float(c[0]), float(c[1])) for c in corners], best_area


def _detect_bright_region(
    gray: np.ndarray, min_area: float, max_area: float, margin: int, h: int, w: int
) -> Corners | None:
    """按亮度阈值找白纸，取面积最大的合法候选。"""
    best_result: Corners | None = None
    best_area = 0.0
    for thresh_val in (200, 190, 180):
        result, area = _try_brightness_threshold(gray, thresh_val, min_area, max_area, margin, h, w)
        if result and area > best_area:
            best_result, best_area = result, area
    return best_result


def detect_paper_corners(img: np.ndarray) -> Corners | None:
    """从 BGR 图里找纸四角，顺序 TL, TR, BR, BL（源图像素）。找不到返回 None。

    策略顺序与原版一致：两组 Canny 边 → 亮度区域 → 兜底策略表。
    """
    if img is None or img.ndim != 3:
        return None

    h, w = img.shape[:2]
    min_area = (h * w) * MIN_AREA_FRACTION
    max_area = (h * w) * MAX_AREA_FRACTION
    edge_margin = int(min(h, w) * EDGE_MARGIN_FRACTION)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    edge_candidates = [_detect_canny(gray, 50, 150), _detect_canny(gray, 75, 200)]
    for edges in edge_candidates:
        result = _find_paper_contour(edges, min_area, max_area, edge_margin, h, w)
        if result and _has_paper_fill(gray, result):
            return result

    bright_result = _detect_bright_region(gray, min_area, max_area, edge_margin, h, w)
    if bright_result:
        return bright_result

    strategies = [
        edge_candidates[0],
        _detect_canny(gray, 30, 100),
        edge_candidates[1],
        _detect_adaptive_threshold(gray),
        _detect_saturation(img),
    ]
    for edges in strategies:
        if edges is None:
            continue
        result = _find_paper_contour(edges, min_area, max_area, edge_margin, h, w)
        if result:
            return result

    return None


def detect_paper_corners_from_path(image_path: str) -> Corners | None:
    """路径版本。读不到图返回 None（不吞异常之外的错误）。"""
    img = cv2.imread(image_path)
    if img is None:
        return None
    return detect_paper_corners(img)
