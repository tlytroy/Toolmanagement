"""SDS §4 的 /api/* 端点（M1-W 接线层）。

只用 FastAPI `APIRouter`，由 `main.py` 在信封函数定义之后 `include_router`。
信封函数通过 **延迟导入** `main._ok/_fail` 取得（在请求时 main 已完全初始化），
避免 `main → api.routes → main` 的循环导入。**不动任何旧端点**。
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, File, Form, UploadFile

from api.errors import error_payload
from api.generate import generate_response
from api.schemas import FingerHolesAutoIn, ProjectIn, SimplifyContourIn
from imaging.api import detect_paper_response, correct_image_response

logger = logging.getLogger("toolmanagement.api")

router = APIRouter(prefix="/api")


def _envelope():
    """请求时取 main 的信封函数（此时 main 已初始化，无循环导入）。"""
    from main import _fail, _ok  # noqa: PLC0415 - 故意延迟
    return _ok, _fail


def _fail_only():
    from main import _fail  # noqa: PLC0415
    return _fail


# ---- §4.1 /api/detect-paper ----
@router.post("/detect-paper")
async def api_detect_paper(file: UploadFile = File(...), paperSize: str = Form("a4")):
    _ok, _fail = _envelope()
    try:
        content = await file.read()
        data = detect_paper_response(content, paper_size=paperSize)
        warns = data.pop("warnings", [])
        return _ok(data, warns)
    except Exception as exc:  # noqa: BLE001
        code, message, detail = error_payload(exc)
        return _fail(code, message, detail)


# ---- §4.2 /api/correct-image ----
@router.post("/correct-image")
async def api_correct_image(
    file: UploadFile = File(...),
    paperSize: str = Form("a4"),
    orientation: str | None = Form(None),
):
    _ok, _fail = _envelope()
    try:
        content = await file.read()
        data = correct_image_response(content, paper_size=paperSize, orientation=orientation)
        return _ok(data)
    except Exception as exc:  # noqa: BLE001
        code, message, detail = error_payload(exc)
        return _fail(code, message, detail)


# ---- §4.5 /api/generate ----
@router.post("/generate")
async def api_generate(payload: dict):
    _ok, _fail = _envelope()
    from api.schemas import validation_error_to_detail
    from pydantic import ValidationError

    try:
        pin = ProjectIn(**payload)
    except ValidationError as exc:
        detail = validation_error_to_detail(exc)
        if any(e.get("type") == "extra_forbidden" for e in detail.get("validationErrors", [])):
            return _fail("SCHEMA_UNKNOWN_FIELD", "请求含未知字段", detail)
        return _fail("GEOMETRY_INVALID", "请求字段校验失败", detail)
    except Exception as exc:  # noqa: BLE001
        return _fail("INVALID_SIZE_MODE", str(exc))

    ok, data, code, message, detail, warnings = generate_response(pin)
    if ok:
        return _ok(data, warnings)
    return _fail(code or "INTERNAL", message or "生成失败", detail, warnings)


# ---- §4.6 /api/finger-holes/auto ----
@router.post("/finger-holes/auto")
async def api_finger_holes_auto(payload: dict):
    """手孔自动放置。M1.5 的手孔几何尚未实现，这里返回空建议 + 明确 warning。"""
    _ok, _fail = _envelope()
    from api.schemas import validation_error_to_detail
    from pydantic import ValidationError

    try:
        FingerHolesAutoIn(**payload)
    except ValidationError as exc:
        return _fail("SCHEMA_UNKNOWN_FIELD", "请求字段错误", validation_error_to_detail(exc))
    return _ok(
        {"holes": []},
        [{"code": "FINGER_HOLES_NOT_IMPLEMENTED",
          "message": "手孔自动放置待 M1.5 实现，当前返回空建议", "detail": {}}],
    )


# ---- §4.4 /api/simplify-contour ----
@router.post("/simplify-contour")
async def api_simplify_contour(payload: dict):
    """轮廓简化。用 shapely，输入 polygon → 输出简化后的闭合环。"""
    _ok, _fail = _envelope()
    from api.schemas import validation_error_to_detail
    from pydantic import ValidationError

    try:
        pin = SimplifyContourIn(**payload)
    except ValidationError as exc:
        return _fail("SCHEMA_UNKNOWN_FIELD", "请求字段错误", validation_error_to_detail(exc))
    from shapely.geometry import Polygon

    pts = [(p.x, p.y) for p in pin.polygon]
    if len(pts) < 3:
        return _fail("GEOMETRY_INVALID", "轮廓至少需要 3 个点", {"count": len(pts)})
    try:
        poly = Polygon(pts).buffer(0).simplify(float(pin.tolerance_mm), preserve_topology=True)
        ring = [[float(x), float(y)] for x, y in poly.exterior.coords]
        return _ok({"polygons": [ring]})
    except Exception as exc:  # noqa: BLE001
        return _fail("GEOMETRY_INVALID", f"轮廓简化失败：{exc}")


# ---- §4.3 /api/extract-tools ----
@router.post("/extract-tools")
async def api_extract_tools(file: UploadFile = File(...)):
    """从透视矫正图提取工具轮廓（纸面 mm）。复用遗留分割器。"""
    _ok, _fail = _envelope()
    try:
        import cv2
        import numpy as np
        from sam_tool_contour import extract_tool_contours_v26
        from imaging.constants import PX_PER_MM

        content = await file.read()
        arr = np.frombuffer(content, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return _fail("IMAGE_DECODE_FAILED", "无法解码图片")
        contour = extract_tool_contours_v26(img)
        if contour is None:
            return _fail("NO_CONTOUR", "未找到工具轮廓")
        pts = contour.reshape(-1, 2).astype(float) / float(PX_PER_MM)
        outer = [{"x": float(x), "y": float(y)} for x, y in pts]
        from shapely.geometry import Polygon

        poly = Polygon([(p["x"], p["y"]) for p in outer])
        data = {
            "tools": [{
                "outer": outer, "interior": [],
                "areaMm2": float(poly.area),
                "bbox": [float(v) for v in poly.bounds],
            }],
            "quality": 1.0,
            "qualityParts": {"coverage": 1.0, "circularity": 1.0, "edgeSharpness": 1.0},
        }
        return _ok(data)
    except Exception as exc:  # noqa: BLE001
        code, message, detail = error_payload(exc)
        return _fail(code, message, detail)


__all__ = ["router"]
