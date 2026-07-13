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

# ============================================================
# DP 抽稀 + 基元拟合（真实实现，对齐 reference/contour_simplify）
# ============================================================

def dp_simplify(contour, eps_ratio: float):
    """Douglas-Peucker 抽稀，返回简化后的轮廓点集"""
    peri = cv2.arcLength(contour, closed=True)
    eps = eps_ratio * peri
    return cv2.approxPolyDP(contour, eps, closed=True)


def line_fit_error(pts: np.ndarray) -> float:
    """点到最小二乘直线的 RMS 垂直距离"""
    if len(pts) < 2:
        return 1e9
    lp = cv2.fitLine(pts, cv2.DIST_L2, 0, 0.01, 0.01)
    vx, vy = float(lp[0][0]), float(lp[1][0])
    n = np.array([vx, vy]) / (np.hypot(vx, vy) + 1e-9)
    v0 = pts[0]
    d = np.abs((pts - v0) @ np.array([-n[1], n[0]]))  # 垂直距离
    return float(np.sqrt(np.mean(d ** 2)))


def circle_fit(pts: np.ndarray) -> Optional[Tuple[float, float, float]]:
    """代数最小二乘圆拟合，返回 (cx, cy, r) 或 None"""
    if len(pts) < 3:
        return None
    xs, ys = pts[:, 0].astype(float), pts[:, 1].astype(float)
    A = np.column_stack([xs, ys, np.ones_like(xs)])
    b = -(xs ** 2 + ys ** 2)
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    a, bb, c = sol
    cx, cy = -a / 2.0, -bb / 2.0
    r = np.sqrt(max(cx ** 2 + cy ** 2 - c, 1e-6))
    return (float(cx), float(cy), float(r))


def circle_fit_error(pts: np.ndarray, circle: Tuple[float, float, float]) -> float:
    """圆拟合的 RMS 径向误差"""
    cx, cy, r = circle
    d = np.hypot(pts[:, 0] - cx, pts[:, 1] - cy)
    return float(np.sqrt(np.mean((d - r) ** 2)))

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
        
        # 二值化保底
        _, mask_image = cv2.threshold(mask_image, 127, 255, cv2.THRESH_BINARY)

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
        dense = contour.reshape(-1, 2).astype(np.float64)

        # DP抽稀得到拐点顶点
        EPS = 0.004
        verts = dp_simplify(contour, EPS).reshape(-1, 2).astype(np.float64)
        N = len(verts)

        if N < 2:
            # 如果顶点太少，返回原始轮廓作为折线
            points_list = [{"x": float(p[0]), "y": float(p[1])} for p in dense]
            return {
                "success": True,
                "primitives": [{"type": "polyline", "points": points_list}],
                "summary": {"lines": 0, "polylines": 1, "arcs": 0}
            }

        # 建立顶点索引映射（闭包捕获 dense）
        def _nearest_dense_index(pt: np.ndarray) -> int:
            d = np.sum((dense - pt) ** 2, axis=1)
            return int(np.argmin(d))

        vert_idx = [_nearest_dense_index(v) for v in verts]

        def _points_between(i: int, j: int) -> np.ndarray:
            """取轮廓上从顶点 i 到顶点 j（顺时针）之间的稠密点"""
            a, b = vert_idx[i], vert_idx[j]
            if b >= a:
                return dense[a:b + 1]
            else:
                return np.vstack([dense[a:], dense[:b + 1]])

        # 逐段基元化：直线 vs 圆弧
        primitives = []
        LIN_TOL = 4.0
        ARC_TOL = 4.0
        MAX_ARC_RADIUS = 55

        for k in range(N):
            i, j = k, (k + 1) % N
            seg = _points_between(i, j)
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
                    # 计算起止角度
                    ang = np.unwrap(np.arctan2(seg[:, 1] - cy, seg[:, 0] - cx))
                    a0 = float(np.degrees(ang[0]))
                    a1 = a0 + float(np.degrees(ang[-1] - ang[0]))

                    # 重采样圆弧点列
                    n_sample = max(12, len(seg) // 3)
                    theta = np.linspace(np.radians(a0), np.radians(a1), n_sample)
                    arc_x = cx + r * np.cos(theta)
                    arc_y = cy + r * np.sin(theta)
                    points_list = [{"x": float(x), "y": float(y)} for x, y in zip(arc_x, arc_y)]

                    primitives.append({
                        'type': 'arc',
                        'p0': {'x': float(p0[0]), 'y': float(p0[1])},
                        'p1': {'x': float(p1[0]), 'y': float(p1[1])},
                        'center': {'x': float(cx), 'y': float(cy)},
                        'radius': float(r),
                        'startAngle': float(a0),
                        'endAngle': float(a1),
                        'points': points_list
                    })
                else:
                    # 大半径缓弯 → 退化为折线（对段内点做细粒度 DP）
                    sub_eps = 0.002 * cv2.arcLength(contour, closed=True)
                    poly_approx = cv2.approxPolyDP(
                        seg.reshape(-1, 1, 2).astype(np.int32), sub_eps, closed=False
                    ).reshape(-1, 2)
                    pts_list = [{"x": float(pt[0]), "y": float(pt[1])} for pt in poly_approx]
                    primitives.append({
                        'type': 'polyline', 'points': pts_list,
                    })
            else:
                primitives.append({
                    'type': 'line',
                    'p0': {'x': float(p0[0]), 'y': float(p0[1])},
                    'p1': {'x': float(p1[0]), 'y': float(p1[1])}
                })
        
        # 统计各类基元数量
        n_lines = len([p for p in primitives if p["type"] == "line"])
        n_polylines = len([p for p in primitives if p["type"] == "polyline"])
        n_arcs = len([p for p in primitives if p["type"] == "arc"])

        return {
            "success": True,
            "primitives": primitives,
            "summary": {
                "lines": n_lines,
                "polylines": n_polylines,
                "arcs": n_arcs
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

        # 二值化保底：防御 JPEG 压缩伪影（正常用 PNG 不会有此问题）
        _, mask_image = cv2.threshold(mask_image, 127, 255, cv2.THRESH_BINARY)

        contours, _ = cv2.findContours(mask_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if not contours:
            return {"success": False, "error": "蒙版中未找到轮廓"}

        contour = max(contours, key=cv2.contourArea)
        pts = contour.reshape(-1, 2).astype(np.float64)

        # 返回原始轮廓为一个 polyline primitive
        points_list = [{"x": float(p[0]), "y": float(p[1])} for p in pts]
        return {
            "success": True,
            "primitives": [{"type": "polyline", "points": points_list}],
            "summary": {"lines": 0, "polylines": 1, "arcs": 0}
        }
    except Exception as e:
        print(f"更新轮廓失败: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
