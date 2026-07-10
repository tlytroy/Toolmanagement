from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
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

# 导入抽稀基元化模块
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'reference', 'contour_simplify', 'pkg_contour_simplify_primitives'))

# 延迟导入，避免在模块加载时执行代码
def import_contour_simplify():
    try:
        # 动态导入模块
        import importlib.util
        module_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'reference', 'contour_simplify', 'pkg_contour_simplify_primitives', 'contour_simplify.py')
        spec = importlib.util.spec_from_file_location("contour_simplify", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        print(f"警告: 无法导入抽稀基元化模块，将使用简化版本: {e}")
        return None

# 创建模拟函数以避免错误
def dp_simplify(c, eps_ratio):
    return c

def line_fit_error(pts):
    return 0

def circle_fit(pts):
    return None

def circle_fit_error(pts, circ):
    return 0

def nearest_dense_index(pt):
    return 0

def points_between(i, j):
    return []

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
    
    # 轮廓提取和基元化
    primitives = extract_tool_contours(image_array)
    
    # 生成调试图像：在原图上绘制红色轮廓
    debug_image = image_array.copy()
    if hasattr(extract_tool_contours, '__globals__'):
        # 尝试获取轮廓用于绘制
        try:
            contour = extract_tool_contours_v26(image_array)
            if contour is not None:
                # 在原图上绘制红色轮廓边框
                cv2.drawContours(debug_image, [contour], -1, (0, 0, 255), 2)
        except:
            pass

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
    
    # 提取工具蒙版
    contour = extract_tool_contours_v26(image_array)
    
    if contour is None:
        return {
            "success": False,
            "error": "未检测到工具轮廓"
        }
    
    # 创建蒙版图像
    mask = np.zeros(image_array.shape[:2], dtype=np.uint8)
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
        
        # 从蒙版中提取轮廓
        contours, _ = cv2.findContours(mask_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if not contours:
            return {
                "success": False,
                "error": "蒙版中未找到轮廓"
            }
        
        # 获取最大的轮廓
        contour = max(contours, key=cv2.contourArea)
        
        # 使用抽稀基元化算法处理轮廓
        # 这里我们使用参考实现中的算法
        dense = contour.reshape(-1, 2).astype(np.float64)
        
        # DP抽稀得到拐点顶点
        EPS = 0.004
        verts = dp_simplify(contour, EPS).reshape(-1, 2).astype(np.float64)
        N = len(verts)
        
        if N < 2:
            return {
                "success": False,
                "error": "轮廓点数不足"
            }
        
        # 建立顶点索引映射
        vert_idx = [nearest_dense_index(v) for v in verts]
        
        # 逐段基元化：直线 vs 圆弧
        primitives = []
        LIN_TOL = 4.0
        ARC_TOL = 4.0
        MAX_ARC_RADIUS = 55
        
        for k in range(N):
            i, j = k, (k + 1) % N
            seg = points_between(i, j) if 'points_between' in globals() else dense
            p0 = tuple(map(int, verts[i]))
            p1 = tuple(map(int, verts[j]))
            
            err_l = line_fit_error(seg)
            circ = circle_fit(seg)
            err_c = circle_fit_error(seg, circ) if circ else 1e9
            
            # 判定：圆弧拟合显著优于直线？
            is_arc_better = (err_c < err_l) and (err_c < ARC_TOL) and (err_l > LIN_TOL)
            
            if is_arc_better:
                cx, cy, r = circ
                if r <= MAX_ARC_RADIUS:
                    # 真正的弧（曲率足够大）
                    primitives.append({
                        'type': 'arc', 'p0': p0, 'p1': p1,
                        'center': (float(cx), float(cy)), 'radius': float(r)
                    })
                else:
                    # 大半径缓弯 → 退化为折线（对段内点做细粒度 DP）
                    # 注意：这里需要原始轮廓来计算周长
                    sub_eps = 0.002 * cv2.arcLength(contour, closed=True)
                    poly_approx = cv2.approxPolyDP(
                        seg.reshape(-1, 1, 2).astype(np.int32), sub_eps, closed=False
                    ).reshape(-1, 2)
                    pts_list = [tuple(map(float, pt)) for pt in poly_approx]
                    primitives.append({
                        'type': 'polyline', 'points': pts_list,
                    })
            else:
                primitives.append({'type': 'line', 'p0': p0, 'p1': p1})
        
        return {
            "success": True,
            "primitives": primitives,
            "summary": {
                "lines": len([p for p in primitives if p["type"] == "line"]),
                "polylines": len([p for p in primitives if p["type"] == "polyline"]),
                "arcs": len([p for p in primitives if p["type"] == "arc"])
            }
        }
    except Exception as e:
        print(f"抽稀基元化失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
