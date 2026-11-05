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
        return {
            "success": False,
            "error": "未检测到纸张"
        }
    
    # 透视校正
    warped_image = perspective_warp(image_array, corners)
    
    # 转换结果为可传输格式
    warped_base64 = image_to_base64(warped_image)
    
    return {
        "success": True,
        "corners": corners,
        "warped_image": f"data:image/jpeg;base64,{warped_base64}"
    }

@app.post("/extract-contours")
async def extract_contours(file: UploadFile = File(...)):
    """
    从已校正的图像中提取工具轮廓
    """
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
    
    return {
        "success": True,
        "primitives": primitives,
        "debug_image": f"data:image/jpeg;base64,{debug_base64}",
        "summary": {
            "lines": len([p for p in primitives if p["type"] == "line"]),
            "polylines": len([p for p in primitives if p["type"] == "polyline"]),
            "arcs": 0  # 简化版本暂不实现圆弧检测
        }
    }

@app.post("/extract-tool-mask")
async def extract_tool_mask(file: UploadFile = File(...)):
    """
    从已校正的图像中提取工具蒙版（用于手动调整）
    """
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
    
    return {
        "success": True,
        "mask_image": f"data:image/jpeg;base64,{mask_base64}"
    }

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
            return {
                "success": False,
                "error": "无法解码蒙版图像"
            }
        
        # 使用 curvature_simplify 模块进行抽稀基元化
        result = simplify_contour_to_primitives(mask_image)
        return result
    except Exception as e:
        print(f"抽稀基元化失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }

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
            return {"success": False, "error": "无法解码蒙版图像"}

        # 使用 curvature_simplify 模块提取轮廓
        result = contour_to_polyline(mask_image)
        return result
    except Exception as e:
        print(f"更新轮廓失败: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

# ── CAD 3D 生成端点 ──────────────────────────────────

from cad_engine import generate_stl, generate_step_from_dict, _auto_detect_finger_slots

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
    params = {
        "mode": req.mode,
        "foam": req.foam,
        "gridfinity": req.gridfinity,
        "primitives": req.primitives,
        "tool_offset": req.tool_offset,
        "embed_depth": req.embed_depth,
        "finger_slots": req.finger_slots,
    }
    result = generate_stl(params)
    return result


@app.post("/generate-step", response_model=Dict[str, Any])
async def generate_step(req: GenerateCADRequest):
    """
    生成工具嵌件 3D 模型（STEP 格式，base64 编码）。

    与 /generate-cad 相同的参数，但输出为 STEP AP242 格式，
    可在 Fusion 360、SolidWorks、FreeCAD 等主流 CAD 软件中直接编辑。

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
    params = {
        "mode": req.mode,
        "foam": req.foam,
        "gridfinity": req.gridfinity,
        "primitives": req.primitives,
        "tool_offset": req.tool_offset,
        "embed_depth": req.embed_depth,
        "finger_slots": req.finger_slots,
    }
    result = generate_step_from_dict(params)
    return result


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

        return {
            "success": True,
            "finger_slots": slots,
        }
    except Exception as e:
        print(f"自动手指槽检测失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
            "finger_slots": [],
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
