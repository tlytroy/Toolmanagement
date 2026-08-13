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

# ============================================================
# 轮廓抽稀 + 基元拟合（改进版）
# 流程：
#   1. 从蒙版提取外轮廓（CHAIN_APPROX_NONE 保留全密度）
#   2. 曲率分析标记弯曲段（一阶差分 sin(theta)）
#   3. 直线段坍缩为首尾 2 点；弯曲段用 fitEllipse 拟合圆弧
#   4. 大半径缓弯退化为子段 DP 折线
#   5. 参数自适应：基于轮廓周长/图像尺寸
# ============================================================

def _compute_curvature(pts: np.ndarray) -> np.ndarray:
    """
    一阶差分曲率：相邻边夹角的正弦值 sin(theta)
    直线段 → 0，弯曲段 → 非零
    """
    n = len(pts)
    curv = np.zeros(n)
    for i in range(1, n - 1):
        v1 = pts[i] - pts[i - 1]
        v2 = pts[i + 1] - pts[i]
        L1 = np.linalg.norm(v1)
        L2 = np.linalg.norm(v2)
        if L1 > 1e-6 and L2 > 1e-6:
            cos_t = np.clip(np.dot(v1, v2) / (L1 * L2), -1.0, 1.0)
            curv[i] = np.sin(np.arccos(cos_t))
    return curv


def _segment_by_curvature(pts: np.ndarray, curv_thresh: float = 0.03) -> List[Tuple[str, np.ndarray]]:
    """
    基于曲率将轮廓分段：
      - 直线段: curvature < thresh
      - 弧段候选: curvature >= thresh（经过形态学去噪+桥接）
    
    返回 [(type, segment_points), ...] 其中 type='LINE'|'ARC_CAND'
    """
    n = len(pts)
    if n < 4:
        return [('LINE', pts)]
    
    curv = _compute_curvature(pts)
    
    # 形态学去噪：腐蚀（3窗口≥2）去除孤立噪声点
    is_arc = (curv > curv_thresh).astype(int)
    is_arc = np.convolve(is_arc, np.ones(3), mode='same') >= 2
    
    # 轻度膨胀桥接断点（曲率连续区域的短间隙）
    is_arc = np.convolve(is_arc.astype(int), np.ones(3), mode='same') >= 1
    is_arc = is_arc.astype(bool)
    
    # 分段
    segments = []
    i = 0
    while i < n:
        if is_arc[i]:
            start = i
            while i < n and is_arc[i]:
                i += 1
            seg = pts[start:i]
            if len(seg) >= 5:  # 弧段至少需要 5 个点才能 fitEllipse
                segments.append(('ARC_CAND', seg))
            elif len(seg) >= 2:
                segments.append(('LINE', seg[[0, -1]]))
        else:
            start = i
            while i < n and not is_arc[i]:
                i += 1
            seg = pts[start:i]
            if len(seg) >= 2:
                segments.append(('LINE', np.array([seg[0], seg[-1]])))
    return segments


def _fit_arc_robust(pts: np.ndarray, max_radius: float, min_span_deg: float = 20.0) -> Optional[Dict]:
    """
    用 cv2.fitEllipse 做圆弧拟合（比代数最小二乘圆拟合更稳定）
    
    返回:
      {'type':'arc', 'center':(cx,cy), 'radius':r,
       'startAngle':a0, 'endAngle':a1, 'points':[...]} 或 None
    """
    if len(pts) < 5:
        return None
    
    pts32 = pts.astype(np.float32)
    try:
        (cx, cy), (rax, ray), angle = cv2.fitEllipse(pts32)
    except Exception:
        return None
    
    cx, cy = float(cx), float(cy)
    rmin, rmaj = sorted([rax, ray])
    
    # 圆度检查：长短轴比不能太椭圆（>25% 偏差则不是圆）
    if rmaj > 1e-3 and (rmaj - rmin) / rmaj > 0.25:
        return None
    
    # fitEllipse 返回的是轴全长，半径取平均
    radius = (rax + ray) / 4.0
    
    if radius < 3.0 or radius > max_radius:
        return None
    
    # 计算起止角度（解缠绕避免 ±π 跳变）
    theta = np.arctan2(pts[:, 1] - cy, pts[:, 0] - cx)
    theta_u = np.unwrap(theta)
    a0 = float(np.degrees(theta_u[0]))
    a1 = float(np.degrees(theta_u[-1]))
    span = abs(a1 - a0)
    
    if span < min_span_deg or span > 270:  # 跨度太小(<20°)或太大(>270°)不认为是有效弧
        return None
    
    # 误差检查：点到拟合圆的平均径向残差
    dists = np.abs(np.linalg.norm(pts - np.array([cx, cy]), axis=1) - radius)
    mean_err = np.mean(dists)
    # 自适应阈值：跨度越大允许误差越大
    max_err = 2.0 + (span - 20) / 30.0
    if mean_err > max_err:
        return None
    
    # 重采样弧上点（用于前端绘制）
    n_sample = max(12, int(span / 5))
    arc_angles = np.linspace(np.radians(a0), np.radians(a1), n_sample)
    arc_x = cx + radius * np.cos(arc_angles)
    arc_y = cy + radius * np.sin(arc_angles)
    points_list = [{"x": float(x), "y": float(y)} for x, y in zip(arc_x, arc_y)]
    
    return {
        'type': 'arc',
        'center': {'x': float(cx), 'y': float(cy)},
        'radius': float(radius),
        'startAngle': float(a0),
        'endAngle': float(a1),
        'points': points_list
    }


def _subdivide_polyline(seg: np.ndarray, contour_arc_length: float) -> List[Dict]:
    """
    对缓弯段做细粒度 DP 抽稀，返回 polyline 基元
    """
    sub_eps = 0.002 * contour_arc_length
    poly = cv2.approxPolyDP(
        seg.reshape(-1, 1, 2).astype(np.int32), sub_eps, closed=False
    ).reshape(-1, 2)
    pts_list = [{"x": float(pt[0]), "y": float(pt[1])} for pt in poly]
    return [{'type': 'polyline', 'points': pts_list}]

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
        
        # ========== 改进的抽稀基元化算法 ==========
        # 1. 获取全密度轮廓点
        dense = contour.reshape(-1, 2).astype(np.float64)
        arc_length = cv2.arcLength(contour, closed=True)
        h, w = mask_image.shape[:2]
        img_diag = np.sqrt(h * h + w * w)
        
        # 2. 自适应参数：基于轮廓周长和图像尺寸
        #    MAX_ARC_RADIUS = 图像对角线的 3%，对于 2000px 图像约 60px
        adaptive_max_radius = img_diag * 0.03
        adaptive_max_radius = max(adaptive_max_radius, 30.0)  # 至少 30px
        adaptive_max_radius = min(adaptive_max_radius, 300.0)  # 最多 300px
        
        # 曲率阈值：小图像用稍大阈值（更少的弧检测），大图像用稍小阈值
        adaptive_curv_thresh = max(0.02, min(0.05, 50.0 / img_diag))
        
        # 3. 曲率分段
        segments = _segment_by_curvature(dense, curv_thresh=adaptive_curv_thresh)
        
        # 4. 逐段基元化
        primitives = []
        for seg_type, seg_pts in segments:
            if seg_type == 'LINE':
                # 直线段：只保留首尾 2 点
                p0, p1 = seg_pts[0], seg_pts[-1]
                primitives.append({
                    'type': 'line',
                    'p0': {'x': float(p0[0]), 'y': float(p0[1])},
                    'p1': {'x': float(p1[0]), 'y': float(p1[1])}
                })
            else:  # ARC_CAND
                # 尝试圆弧拟合
                arc = _fit_arc_robust(seg_pts, max_radius=adaptive_max_radius)
                if arc is not None:
                    primitives.append(arc)
                else:
                    # 圆弧拟合失败 → 尝试小半径弧（更宽松）或退化为折线
                    # 先试一个更宽松的阈值
                    arc = _fit_arc_robust(seg_pts, max_radius=adaptive_max_radius * 2, min_span_deg=10.0)
                    if arc is not None:
                        primitives.append(arc)
                    else:
                        # 完全退化为折线
                        primitives.extend(_subdivide_polyline(seg_pts, arc_length))
        
        # 5. 统计
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

# ── CAD 3D 生成端点 ──────────────────────────────────

from cad_engine import generate_stl

class GenerateCADRequest(BaseModel):
    """CAD 生成请求"""
    mode: str = "foam"
    foam: Dict[str, Any] = {}
    gridfinity: Dict[str, Any] = {}
    primitives: List[Dict[str, Any]] = []
    tool_offset: float = 1.0
    embed_depth: float = 15.0


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
    }
    result = generate_stl(params)
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
