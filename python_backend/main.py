from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import cv2
import numpy as np
import io
from PIL import Image
import base64
from typing import List, Dict, Any, Tuple, Optional
import json
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

app = FastAPI(title="Tool Management Backend")

# CORS配置（开发时允许所有来源）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 统一响应信封（SDS §4.0 / 任务 0.8）─────────────────
# {success, data, warnings, error:{code,message,detail}}
# ★ 兼容说明：前端 `src/` 已冻结，`src/hooks/useWorkflow.ts` 读的是 `result.error`
#   的**字符串**形式，所以成功响应把 `data` 的字段**同时**铺在顶层（老前端照旧能读
#   `result.corners` / `result.stl_base64`），失败响应额外给一个 `error_message` 字符串。
#   结构化错误固定放 `error: {code, message, detail}`，前端将来改成 `error?.message` 即可。
import logging

logger = logging.getLogger("toolmanagement")


def _warn(code: str, message: str, detail: dict | None = None) -> dict:
    """SDS §4.0：warnings[] 元素与 error 同构 `{code, message, detail}`。"""
    return {"code": code, "message": message, "detail": detail or {}}


def _ok(data: dict, warnings: list | None = None) -> dict:
    """成功信封。`data` 的键同时铺在顶层，兼容冻结前端。"""
    out = dict(data)
    out["success"] = True
    out["data"] = dict(data)
    out["warnings"] = list(warnings or [])
    out["error"] = None
    return out


def _fail(
    code: str,
    message: str,
    detail: dict | None = None,
    warnings: list | None = None,
    *,
    legacy_error_string: bool = False,
) -> dict:
    """失败信封。`code` 必须是 SDS §4.0 的枚举值（前端据此出文案）。

    ★ `legacy_error_string` 只给 `/detect-paper` 用，理由见该端点的注释：
      冻结前端把它的 `error` 当 React child 直接渲染，给对象会整页崩。
    """
    err = {"code": code, "message": message, "detail": detail or {}}
    out = {
        "success": False,
        "data": None,
        "warnings": list(warnings or []),
        "error": message if legacy_error_string else err,
        "error_message": message,
    }
    if legacy_error_string:
        # 结构化错误不能因为兼容而丢掉，换个键继续下发
        out["error_info"] = err
    return out


def _wrap_legacy(result, *, stage: str) -> dict:
    """旧函数返回的裸 dict（自带 success / error 字符串）→ 信封。"""
    if not isinstance(result, dict):
        return _fail(
            "INTERNAL",
            f"{stage} 返回了非字典结果",
            {"stage": stage, "type": type(result).__name__},
        )
    if result.get("success"):
        return _ok({k: v for k, v in result.items() if k != "success"})
    return _fail(
        "INTERNAL",
        str(result.get("error") or f"{stage} 失败"),
        {"stage": stage},
    )

# 导入最新的纸张检测模块
from latest_paper_detection import detect_paper_corners_latest as detect_paper_corners_fast, warp_paper_latest as perspective_warp

# 保持原有的简单版本作为后备
def detect_paper_corners(image_array: np.ndarray) -> List[Dict[str, float]]:
    """
    检测A4纸四角（使用新的鲁棒检测算法）
    """
    return detect_paper_corners_fast(image_array)

# 导入SAM工具轮廓处理模块
from sam_tool_contour import extract_tool_contours_v26, convert_contour_to_primitives

# 导入轮廓抽稀模块
from curvature_simplify import simplify_contour_to_primitives, contour_to_polyline

def extract_tool_contours(warped_image: np.ndarray) -> List[Dict[str, Any]]:
    """
    从已校正的图像中提取工具轮廓并进行基元化处理（v26版本）
    使用"只填不啃"管线：多路径并集 → 阴影保护减法 → 最大连通块 → 填洞 → 平滑
    """
    # 提取工具轮廓
    contour = extract_tool_contours_v26(warped_image)
    
    if contour is None:
        return []
    
    # 转换为几何基元
    primitives = convert_contour_to_primitives(contour)
    
    return primitives


def extract_tool_contours_with_debug(warped_image: np.ndarray):
    """
    提取工具轮廓并返回 (contour, primitives) 元组，避免重复提取
    """
    contour = extract_tool_contours_v26(warped_image)
    
    if contour is None:
        return None, []
    
    primitives = convert_contour_to_primitives(contour)
    
    return contour, primitives

def image_to_base64(image_array: np.ndarray) -> str:
    """
    将OpenCV图像转换为base64编码
    """
    _, buffer = cv2.imencode('.jpg', image_array)
    return base64.b64encode(buffer).decode('utf-8')

@app.get("/")
async def root():
    return {"message": "Tool Management Backend API"}

@app.post("/detect-paper")
async def detect_paper(file: UploadFile = File(...)):
    """
    检测上传图片中的A4纸四角
    """
    try:
        # 读取上传的图片
        contents = await file.read()
        image_array = np.array(Image.open(io.BytesIO(contents)))

        # 确保是BGR格式
        if len(image_array.shape) == 3 and image_array.shape[2] == 3:
            # PIL读取的是RGB，需要转换为BGR
            image_array = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)

        # 纸张检测
        corners = detect_paper_corners(image_array)

        if not corners:
            # ★ 这个端点**单独**保留 `error` 为字符串：冻结前端
            #   `src/features/workspace/Workspace.tsx:88` 把 `result.error` 直接塞进
            #   `processError`，而 `src/features/calibration/CalibrationPanel.tsx:61`
            #   用 `{detectError}` 当 React child 渲染 —— 给对象会整页抛
            #   「Objects are not valid as a React child」。结构化错误改放 `error_info`，
            #   前端解冻后把这两处改成 `result.error?.message` 即可切回统一形态。
            return _fail(
                "PAPER_NOT_FOUND",
                "未检测到纸张",
                {"stage": "detect_paper"},
                legacy_error_string=True,
            )

        # 透视校正
        warped_image = perspective_warp(image_array, corners)

        # 转换结果为可传输格式
        warped_base64 = image_to_base64(warped_image)

        return _ok({
            "corners": corners,
            "warped_image": f"data:image/jpeg;base64,{warped_base64}",
        })
    except Exception as e:  # 路由层兜底：异常在这里转成 error.code，不再 print 后继续
        logger.exception("纸张检测失败")
        return _fail(
            "INTERNAL",
            f"纸张检测失败: {e}",
            {"stage": "detect_paper"},
            legacy_error_string=True,
        )


@app.post("/extract-contours")
async def extract_contours(file: UploadFile = File(...)):
    """
    从已校正的图像中提取工具轮廓
    """
    try:
        # 读取上传的图片
        contents = await file.read()
        image_array = np.array(Image.open(io.BytesIO(contents)))

        # 确保是BGR格式
        if len(image_array.shape) == 3 and image_array.shape[2] == 3:
            # PIL读取的是RGB，需要转换为BGR
            image_array = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)

        # 轮廓提取和基元化（一次性提取轮廓和基元，避免重复提取）
        contour, primitives = extract_tool_contours_with_debug(image_array)

        # 生成调试图像：在原图上绘制红色轮廓
        debug_image = image_array.copy()
        if contour is not None:
            cv2.drawContours(debug_image, [contour], -1, (0, 0, 255), 2)

        # 转换调试图像为base64
        debug_base64 = image_to_base64(debug_image)

        if not primitives:
            # 没轮廓不是错误（用户可以手绘），但必须让前端知道「没东西」，
            # 否则会拿着空基元一路走到 CAD 生成，得到一块没有槽的板。
            return _ok({
                "primitives": [],
                "debug_image": f"data:image/jpeg;base64,{debug_base64}",
                "summary": {"lines": 0, "polylines": 0, "arcs": 0},
            }, [_warn("NO_CONTOUR", "未检测到工具轮廓", {"stage": "extract_contours"})])

        return _ok({
            "primitives": primitives,
            "debug_image": f"data:image/jpeg;base64,{debug_base64}",
            "summary": {
                "lines": len([p for p in primitives if p["type"] == "line"]),
                "polylines": len([p for p in primitives if p["type"] == "polyline"]),
                "arcs": 0  # 简化版本暂不实现圆弧检测
            }
        })
    except Exception as e:
        logger.exception("轮廓提取失败")
        return _fail("INTERNAL", f"轮廓提取失败: {e}", {"stage": "extract_contours"})


@app.post("/extract-tool-mask")
async def extract_tool_mask(file: UploadFile = File(...)):
    """
    从已校正的图像中提取工具蒙版（用于手动调整）
    """
    try:
        # 读取上传的图片
        contents = await file.read()
        image_array = np.array(Image.open(io.BytesIO(contents)))

        # 确保是BGR格式
        if len(image_array.shape) == 3 and image_array.shape[2] == 3:
            # PIL读取的是RGB，需要转换为BGR
            image_array = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)

        # 提取工具轮廓
        contour = extract_tool_contours_v26(image_array)

        # 创建蒙版图像。如果未检测到工具，则返回全黑空白蒙版（用户可以手动绘制）
        mask = np.zeros(image_array.shape[:2], dtype=np.uint8)
        if contour is not None:
            cv2.drawContours(mask, [contour], -1, 255, cv2.FILLED)

        # 转换结果为可传输格式
        mask_base64 = image_to_base64(mask)

        return _ok({"mask_image": f"data:image/jpeg;base64,{mask_base64}"})
    except Exception as e:
        logger.exception("蒙版提取失败")
        return _fail("INTERNAL", f"蒙版提取失败: {e}", {"stage": "extract_tool_mask"})


@app.post("/simplify-contours")
async def simplify_contours(mask_data: dict):
    """
    对给定的蒙版进行抽稀基元化处理
    """
    try:
        # 从base64数据重建蒙版
        mask_base64 = mask_data.get("mask_image", "").split(",")[1]
        mask_bytes = base64.b64decode(mask_base64)
        mask_array = np.frombuffer(mask_bytes, np.uint8)
        mask_image = cv2.imdecode(mask_array, cv2.IMREAD_GRAYSCALE)

        if mask_image is None:
            return _fail("NO_CONTOUR", "无法解码蒙版图像", {"stage": "simplify_contours"})

        # 使用 curvature_simplify 模块进行抽稀基元化
        return _wrap_legacy(simplify_contour_to_primitives(mask_image), stage="simplify_contours")
    except Exception as e:
        logger.exception("抽稀基元化失败")
        return _fail("INTERNAL", f"抽稀基元化失败: {e}", {"stage": "simplify_contours"})


@app.post("/update-contour")
async def update_contour(mask_data: dict):
    """
    仅从蒙版中提取原始轮廓（不抽稀、不基元化），返回 polyline 供前端预览。
    用于用户反复编辑蒙版时快速预览边界变化。
    """
    try:
        mask_base64 = mask_data.get("mask_image", "").split(",")[1]
        mask_bytes = base64.b64decode(mask_base64)
        mask_array = np.frombuffer(mask_bytes, np.uint8)
        mask_image = cv2.imdecode(mask_array, cv2.IMREAD_GRAYSCALE)

        if mask_image is None:
            return _fail("NO_CONTOUR", "无法解码蒙版图像", {"stage": "update_contour"})

        # 使用 curvature_simplify 模块提取轮廓
        return _wrap_legacy(contour_to_polyline(mask_image), stage="update_contour")
    except Exception as e:
        logger.exception("更新轮廓失败")
        return _fail("INTERNAL", f"更新轮廓失败: {e}", {"stage": "update_contour"})


# ── CAD 3D 生成端点 ──────────────────────────────────

from cad_engine import (
    generate_stl,
    _auto_detect_finger_slots,
    _chain_rings,
    _primitives_to_shape,
)
import cad_engine


def _validate_primitives(primitives: list) -> dict | None:
    """CAD 生成前的轮廓前置校验，返回信封或 None。

    ★ 为什么必须有这一步（0.8 静默失败收口的实证）：
      旧引擎 `_extrude_tool_slot` 在轮廓串不成合法多边形时**静默 return None**，
      于是「传一个自交轮廓」得到的是**一块没有槽的整板**，而且 `success=True`。
      实测（bowtie 基元）：vol 599530.73，与完全不给基元的基线**完全相同**。
      这是本里程碑最隐蔽的一类静默失败：用户看到成功，拿到的是废件。
    """
    if not primitives:
        return None

    from shapely.geometry import Polygon
    from shapely.validation import explain_validity

    rings = _chain_rings(primitives)
    if not rings:
        return _fail(
            "GEOMETRY_INVALID",
            "工具轮廓未能串成闭合环",
            {"stage": "validate_primitives", "reason": "no_closed_ring",
             "primitiveCount": len(primitives)},
        )

    outer = Polygon([tuple(pt) for pt in rings[0]])
    # ★ 先判 is_valid、再判面积：自交多边形（bowtie）的 shoelace 面积恰好是 0
    #   （两块三角形正负抵消），先判面积会把「自交」误报成「面积为零」，
    #   排查时会往错的方向找。实测：bowtie 环 area=0.0 但 is_valid=False。
    if not outer.is_empty and not outer.is_valid:
        return _fail(
            "GEOMETRY_INVALID",
            "工具轮廓自交或退化",
            {"stage": "validate_primitives", "reason": explain_validity(outer),
             "ringCount": len(rings)},
        )
    if outer.is_empty or outer.area <= 0.0:
        return _fail(
            "GEOMETRY_INVALID",
            "工具轮廓面积为零",
            {"stage": "validate_primitives", "reason": "zero_area",
             "areaPx2": float(outer.area)},
        )
    if _primitives_to_shape(primitives) is None:
        return _fail(
            "GEOMETRY_INVALID",
            "工具轮廓无法构成合法多边形",
            {"stage": "validate_primitives", "reason": "shape_build_failed"},
        )
    return None


class GenerateCADRequest(BaseModel):
    """CAD 生成请求"""
    mode: str = "foam"
    foam: Dict[str, Any] = {}
    gridfinity: Dict[str, Any] = {}
    primitives: List[Dict[str, Any]] = []
    tool_offset: float = 1.0
    embed_depth: float = 15.0
    finger_slots: List[Dict[str, Any]] = []


@app.post("/generate-cad", response_model=Dict[str, Any])
async def generate_cad(req: GenerateCADRequest):
    """
    生成工具嵌件 3D 模型（STL 格式，base64 编码）。

    请求体示例 (Foam):
    ```json
    {
      "mode": "foam",
      "foam": {"length_mm": 200, "width_mm": 150, "height_mm": 20, "fillet_radius": 5},
      "primitives": [...],
      "embed_depth": 15,
      "tool_offset": 1.0
    }
    ```

    请求体示例 (Gridfinity):
    ```json
    {
      "mode": "gridfinity",
      "gridfinity": {"units_x": 3, "units_y": 2, "height_u": 3, "has_magnet_holes": true},
      "primitives": [...],
      "embed_depth": 15,
      "tool_offset": 1.0
    }
    ```
    """
    prim_err = _validate_primitives(req.primitives)
    if prim_err is not None:
        return prim_err

    params = {
        "mode": req.mode,
        "foam": req.foam,
        "gridfinity": req.gridfinity,
        "primitives": req.primitives,
        "tool_offset": req.tool_offset,
        "embed_depth": req.embed_depth,
        "finger_slots": req.finger_slots,
    }
    try:
        # 0.8：旧引擎（冻结文件）只在 except 分支里 append 一行计数，
        # 这里清空/读取，把「静默降级」升级成可下发的 warnings[]。
        # ★ 前后各清一次：清前是防止上个请求的残留，清后是防止本请求的计数
        #   泄漏到下个请求（`generate_stl` 是模块级单例状态，没有自动重置）。
        cad_engine.errors.clear()
        try:
            result = generate_stl(params)
            engine_errors = list(cad_engine.errors)
        finally:
            cad_engine.errors.clear()
        warnings = [
            _warn("ENGINE_DEGRADED", f"旧引擎降级：{msg}", {"stage": "generate_insert"})
            for msg in engine_errors
        ]
        if not result.get("success"):
            return _fail(
                "GEOMETRY_INVALID",
                str(result.get("error") or "CAD 生成失败"),
                {"stage": "generate_insert"},
                warnings,
            )
        payload = {k: v for k, v in result.items() if k != "success"}
        return _ok(payload, warnings)
    except Exception as e:
        logger.exception("CAD 生成失败")
        return _fail("INTERNAL", f"CAD 生成失败: {e}", {"stage": "generate_cad"})


class AutoFingerSlotsRequest(BaseModel):
    """自动手指槽检测请求"""
    mode: str = "foam"
    foam: Dict[str, Any] = {}
    gridfinity: Dict[str, Any] = {}
    primitives: List[Dict[str, Any]] = []
    tool_offset: float = 1.0
    slot_width: float = 12.0
    slot_depth: float = 10.0
    slot_length: float = 25.0


@app.post("/auto-finger-slots", response_model=Dict[str, Any])
async def auto_finger_slots(req: AutoFingerSlotsRequest):
    """
    根据工具轮廓自动检测并生成手指槽位置。

    使用 PCA 分析工具轮廓的主方向，在长轴两端自动放置半胶囊形手指槽，
    使手指槽始终位于工具轮廓的合适位置（轮廓外侧向内侧穿入）。

    请求体示例:
    ```json
    {
      "mode": "foam",
      "foam": {"length_mm": 200, "width_mm": 150},
      "primitives": [...],
      "tool_offset": 1.0,
      "slot_width": 12,
      "slot_depth": 10,
      "slot_length": 25
    }
    ```
    """
    try:
        # 确定基底尺寸
        if req.mode == "gridfinity":
            from models import GridfinityParams
            gf = GridfinityParams(
                units_x=req.gridfinity.get("units_x", 3),
                units_y=req.gridfinity.get("units_y", 2),
            )
            base_size_x = gf.size_x
            base_size_y = gf.size_y
            base_height = gf.height_mm
        else:
            base_size_x = req.foam.get("length_mm", 200.0)
            base_size_y = req.foam.get("width_mm", 150.0)
            base_height = req.foam.get("height_mm", 20.0)

        # 调用 cad_engine 中的自动检测函数
        slots = _auto_detect_finger_slots(
            req.primitives,
            base_size_x,
            base_size_y,
            base_height,
            slot_width=req.slot_width,
            slot_depth=req.slot_depth,
            slot_length=req.slot_length,
        )

        return _ok({"finger_slots": slots})
    except Exception as e:
        logger.exception("自动手指槽检测失败")
        return _fail(
            "INTERNAL",
            f"自动手指槽检测失败: {e}",
            {"stage": "auto_finger_slots"},
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
