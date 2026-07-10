#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
优化的工具轮廓处理模块
集成参考包中的先进算法：
1. 工具轮廓检测（四策略并集）
2. 轮廓抽稀（RDP + 曲率分析）
3. 基元化（直线 + 圆弧拟合）
"""

import cv2
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
import os

# ==================== 工具函数 ====================

def chaikin_smooth(contour: np.ndarray, passes: int = 2) -> np.ndarray:
    """
    Chaikin平滑算法 - 保角平滑，不磨尖角
    """
    if contour is None or len(contour) == 0:
        return contour
    
    pts = contour.reshape(-1, 2).astype(np.float64)
    for _ in range(passes):
        new_pts = []
        n = len(pts)
        for i in range(n):
            p1, p2 = pts[i], pts[(i+1)%n]
            new_pts.append(p1 * 0.75 + p2 * 0.25)
            new_pts.append(p1 * 0.25 + p2 * 0.75)
        pts = np.array(new_pts, dtype=np.float64)
    return pts  # (N, 2)

def rdp_decimate(pts: np.ndarray, epsilon_px: float = 2.0) -> np.ndarray:
    """
    RDP抽稀算法 - 直边只剩2端点
    """
    if len(pts) < 3:
        return pts
    
    eps = float(epsilon_px)
    marker = np.zeros(len(pts), dtype=bool)
    marker[0] = marker[-1] = True
    stack = [(0, len(pts)-1)]
    
    while stack:
        s, e = stack.pop()
        if e - s < 2: 
            continue
        p0, p1 = pts[s], pts[e]
        v = p1 - p0
        v2 = v @ v
        if v2 < 1e-10:
            mid = (s+e)//2
            stack.append((s, mid))
            stack.append((mid, e))
            continue
        max_d, max_i = 0.0, s
        for i in range(s+1, e):
            # 2D cross product = scalar (z-component only)
            diff = pts[i] - p0
            d = (diff[0]*v[1] - diff[1]*v[0])**2 / v2
            if d > max_d: 
                max_d, max_i = d, i
        if max_d > eps*eps:
            marker[max_i] = True
            stack.append((s, max_i))
            stack.append((max_i, e))
    return pts[marker]

def rdp_simplify_closed(pts: np.ndarray, epsilon: float = 2.0) -> np.ndarray:
    """
    闭合轮廓RDP抽稀（保留拓扑连续性）
    """
    pts = np.asarray(pts, dtype=np.float64)
    if len(pts) > 1 and np.linalg.norm(pts[-1] - pts[0]) < 1e-6:
        work = pts[:-1]
    else:
        work = pts
    if len(work) < 3:
        return pts
    simp = rdp_decimate(work, epsilon_px=epsilon)
    if len(simp) == 0:
        return pts
    closed = np.vstack([simp, simp[0:1]])  # 强制闭合
    return closed

def fit_arc_b(pts: np.ndarray, max_radius: float = 200) -> Optional[Tuple]:
    """
    圆弧拟合（方案B核心）：
    - 用cv2.fitEllipse做最小二乘圆拟合
    - 角度用解缠绕(unwrap)的连续角，避免%360边界问题
    """
    if len(pts) < 5:
        return None
    
    pts32 = pts.astype(np.float32)
    try:
        (cx, cy), (rax, ray), ang = cv2.fitEllipse(pts32)
    except Exception:
        return None
    
    cx, cy = float(cx), float(cy)
    rmin, rmaj = sorted([rax, ray])
    radius = (rax + ray) / 4.0   # fitEllipse返回的是直径(全轴长)，半径取轴长和/4
    
    # 圆度检查（轴长比）
    if rmaj > 1e-3 and (rmaj - rmin) / rmaj > 0.25:
        return None   # 不是圆（被直边污染/误判）
    
    if radius < 5.0 or radius > max_radius:
        return None
    
    # 端点角度：解缠绕的连续角度
    theta = np.arctan2(pts[:, 1]-cy, pts[:, 0]-cx)
    theta_u = np.unwrap(theta)
    a0 = float(np.degrees(theta_u[0]))
    a1 = float(np.degrees(theta_u[-1]))
    span = abs(a1 - a0)
    
    if span < 20 or span > 180:
        return None
    
    # 误差检查：采样点到拟合圆平均残差
    dists = np.abs(np.linalg.norm(pts - np.array([cx, cy]), axis=1) - radius)
    mean_err = np.mean(dists)
    max_error = 2.0 + (span - 20) / 30.0
    if mean_err > max_error:
        return None
    
    n = max(8, int(span / 5))  # 每5°一个点
    angles = np.linspace(a0, a1, n)
    arc_pts = np.stack([cx + radius*np.cos(np.radians(angles)),
                        cy + radius*np.sin(np.radians(angles))], axis=1)
    return ('ARC', (cx, cy, radius, a0, a1), arc_pts)

def adaptive_rdp(pts: np.ndarray, segment_flags: np.ndarray, min_arc_len: int = 5) -> List:
    """
    方案B抽稀：
    - 直线段（segment_flags=False）只留首尾2点（完全拍平）
    - 弧段（segment_flags=True）保留密度直接拟合圆，太短(<min_arc_len)退化成直线
    """
    n = len(pts)
    if n < 3:
        return [('LINE', pts)]
    
    segments = []
    i = 0
    while i < n:
        if segment_flags[i]:
            start_i = i
            while i < n and segment_flags[i]:
                i += 1
            arc_seg = pts[start_i:i]
            if len(arc_seg) >= min_arc_len:
                segments.append(('ARC_CAND', arc_seg))
            elif len(arc_seg) >= 2:
                segments.append(('LINE', np.array([arc_seg[0], arc_seg[-1]])))
        else:
            start_i = i
            while i < n and not segment_flags[i]:
                i += 1
            line_seg = pts[start_i:i]
            if len(line_seg) >= 2:
                segments.append(('LINE', np.array([line_seg[0], line_seg[-1]])))
    return segments

def classify_and_fit_fixed(pts_chaikin: np.ndarray, 
                          curv_thresh: float = 0.025, 
                          max_radius: float = 150, 
                          dil_k: int = 1) -> List:
    """
    方案B（自适应抽稀+安全拟合）：
      1) 一阶差分曲率sin(theta)标记弯曲点
      2) 开运算去噪：先腐蚀(3窗口≥2)去孤立噪声，可选轻度膨胀(dil_k)桥接断点
      3) adaptive_rdp：直线坍2点、弧保密度
      4) 组装：LINE段直接基元；ARC_CAND段fit_arc_b拟合（失败退化直线）
    """
    pts = np.asarray(pts_chaikin, dtype=np.float64)
    n = len(pts)
    if n < 4:
        return [('LINE', (pts[0], pts[-1]), pts)]
    
    # Step1: 一阶差分曲率
    curvature = np.zeros(n)
    for i in range(1, n - 1):
        v1 = pts[i] - pts[i-1]
        v2 = pts[i+1] - pts[i]
        L1 = np.linalg.norm(v1)
        L2 = np.linalg.norm(v2)
        if L1 > 1e-6 and L2 > 1e-6:
            cos_t = np.clip(np.dot(v1, v2) / (L1 * L2), -1.0, 1.0)
            curvature[i] = np.sin(np.arccos(cos_t))
    
    # Step2: 开运算去噪（腐蚀+可选膨胀）
    is_arc = (curvature > curv_thresh)
    is_arc = np.convolve(is_arc.astype(int), np.ones(3), mode='same') >= 2   # 腐蚀去孤立噪声
    if dil_k > 1:
        is_arc = np.convolve(is_arc.astype(int), np.ones(dil_k), mode='same') >= 1  # 轻度膨胀桥接断点
    is_arc = is_arc.astype(bool)
    
    # Step3: 自适应RDP -> 带类型的段
    segments = adaptive_rdp(pts, is_arc, min_arc_len=5)
    
    # Step4: 组装基元
    primitives = []
    for typ, seg in segments:
        if typ == 'LINE':
            primitives.append(('LINE', (seg[0], seg[-1]), seg))
        else:
            arc = fit_arc_b(seg, max_radius=max_radius)
            if arc is not None:
                primitives.append(arc)
            else:
                primitives.append(('LINE', (seg[0], seg[-1]), seg))
    return primitives

# ==================== 轮廓提取优化 ====================

def extract_optimized_contours(warped_image: np.ndarray) -> List[Dict[str, Any]]:
    """
    优化的工具轮廓提取和基元化处理
    结合四策略并集和先进的基元化算法
    """
    if warped_image is None:
        return []
    
    h, w = warped_image.shape[:2]
    
    # 1. 基础轮廓提取（使用现有算法）
    gray = cv2.cvtColor(warped_image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    binary = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    
    # 查找轮廓
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # 过滤小轮廓
    min_area = 300
    filtered_contours = [cnt for cnt in contours if cv2.contourArea(cnt) > min_area]
    
    if not filtered_contours:
        return []
    
    # 选择最大轮廓作为工具轮廓
    tool_contour = max(filtered_contours, key=cv2.contourArea)
    
    # 2. Chaikin平滑
    pts_chaikin = chaikin_smooth(tool_contour, passes=2)
    
    # 3. 基元化处理
    primitives = classify_and_fit_fixed(pts_chaikin, curv_thresh=0.025, max_radius=150)
    
    # 4. 转换为标准格式
    result_primitives = []
    
    for primitive in primitives:
        if primitive[0] == 'LINE':
            _, (p0, p1), _ = primitive
            result_primitives.append({
                "type": "line",
                "p0": {"x": float(p0[0]), "y": float(p0[1])},
                "p1": {"x": float(p1[0]), "y": float(p1[1])}
            })
        elif primitive[0] == 'ARC':
            _, (cx, cy, radius, a0, a1), _ = primitive
            result_primitives.append({
                "type": "arc",
                "center": {"x": float(cx), "y": float(cy)},
                "radius": float(radius),
                "angle_start": float(a0),
                "angle_end": float(a1)
            })
    
    return result_primitives

def extract_tool_contours_with_metrics(warped_image: np.ndarray) -> Dict[str, Any]:
    """
    带指标统计的工具轮廓提取
    """
    primitives = extract_optimized_contours(warped_image)
    
    # 统计信息
    line_count = len([p for p in primitives if p["type"] == "line"])
    arc_count = len([p for p in primitives if p["type"] == "arc"])
    polyline_count = len([p for p in primitives if p["type"] == "polyline"])
    
    return {
        "primitives": primitives,
        "summary": {
            "lines": line_count,
            "polylines": polyline_count,
            "arcs": arc_count,
            "total": len(primitives)
        }
    }

# ==================== 测试函数 ====================

def test_optimized_processing(image_path: str = "testpic.jpg"):
    """
    测试优化的轮廓处理算法
    """
    # 读取图像
    image = cv2.imread(image_path)
    if image is None:
        print(f"无法读取图像: {image_path}")
        return
    
    print(f"处理图像: {image_path}")
    print(f"图像尺寸: {image.shape}")
    
    # 执行优化的轮廓处理
    result = extract_tool_contours_with_metrics(image)
    
    print(f"检测到的基元数量: {result['summary']['total']}")
    print(f"基元统计: {result['summary']}")
    
    # 显示基元详情
    for i, primitive in enumerate(result['primitives']):
        if primitive['type'] == 'line':
            p0 = primitive['p0']
            p1 = primitive['p1']
            print(f"  直线 {i+1}: ({p0['x']:.1f}, {p0['y']:.1f}) → ({p1['x']:.1f}, {p1['y']:.1f})")
        elif primitive['type'] == 'arc':
            center = primitive['center']
            radius = primitive['radius']
            print(f"  圆弧 {i+1}: 中心({center['x']:.1f}, {center['y']:.1f}), 半径{radius:.1f}")
    
    return result

if __name__ == "__main__":
    test_optimized_processing()