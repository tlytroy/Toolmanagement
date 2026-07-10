#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
高级工具轮廓检测模块
集成参考包中的四策略并集算法：
1. Top-Hat + adaptive + Otsu
2. LAB暗区捕获
3. BlackHat去阴影
4. Canny桥接
"""

import cv2
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
import os
import sys

def tophat_deshedow(gray: np.ndarray, kernel_size: int = 31) -> Tuple[np.ndarray, np.ndarray]:
    """Top-Hat去阴影"""
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel)
    deshedow = cv2.subtract(gray, tophat)
    return deshedow, tophat

def mask_scheme_a(gray: np.ndarray, block: int = 31, C: int = 8) -> np.ndarray:
    """方案A: Top-Hat去阴影后自适应+Otsu组合"""
    # 自适应阈值
    binary1 = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                    cv2.THRESH_BINARY, block, C)
    binary1 = cv2.bitwise_not(binary1)
    
    # Otsu阈值
    _, binary2 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # 组合
    combined = cv2.bitwise_and(binary1, binary2)
    
    # 开运算去噪
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    combined = cv2.morphologyEx(combined, cv2.MORPH_OPEN, kernel)
    
    return combined

def strategy_lab_dark(bgr: np.ndarray, l_threshold_ratio: float = 0.55) -> Tuple[np.ndarray, float, float]:
    """LAB暗区捕获策略"""
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l_channel = lab[:,:,0]
    
    # Otsu阈值
    l_otsu, _ = cv2.threshold(l_channel, 0, 255, cv2.THRESH_OTSU)
    l_threshold = l_otsu * l_threshold_ratio
    
    # 二值化
    _, binary = cv2.threshold(l_channel, l_threshold, 255, cv2.THRESH_BINARY_INV)
    
    # 开运算去噪
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    
    return binary, l_otsu, l_threshold

def strategy_blackhat_corrected(gray: np.ndarray, kernel_size: int = 21) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """BlackHat去阴影策略"""
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel)
    
    # 灰度校正
    corrected = cv2.add(gray, blackhat)
    
    # 二值化
    _, binary = cv2.threshold(corrected, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # 开运算去噪
    kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_open)
    
    return binary, blackhat, corrected

def strategy_canny_bridge(gray: np.ndarray, low_thresh: int = 40, high_thresh: int = 120) -> np.ndarray:
    """Canny桥接策略"""
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blurred, low_thresh, high_thresh)
    
    # 膨胀连接断开的边缘
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edges = cv2.dilate(edges, kernel, iterations=1)
    
    # 闭运算形成区域
    kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    filled = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel_close)
    
    # 查找轮廓并填充
    contours, _ = cv2.findContours(filled, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mask = np.zeros_like(gray)
    for contour in contours:
        if cv2.contourArea(contour) >= 100:  # 过滤小噪声
            cv2.drawContours(mask, [contour], -1, 255, -1)
    
    return mask

def remove_shadow_adaptive(gray: np.ndarray, mask: np.ndarray, 
                          grad_factor: float = 0.55, min_grad: float = 15,
                          peel_ksize: int = 3, max_peel: int = 30,
                          close_ksize: int = 3) -> Tuple[np.ndarray, int]:
    """自适应阴影去除"""
    # 计算梯度
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    grad = np.sqrt(gx**2 + gy**2)
    
    n_mask = int(np.count_nonzero(mask))
    if n_mask == 0:
        return mask.copy(), 0
    
    result = mask.copy()
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (peel_ksize, peel_ksize))
    total_removed = 0
    
    for _ in range(max_peel):
        eroded = cv2.erode(result, kernel)
        boundary = cv2.bitwise_and(result, cv2.bitwise_not(eroded))
        n_bnd = int(np.count_nonzero(boundary))
        if n_bnd == 0:
            break
        
        bnd_grad = grad[boundary > 0]
        g_otsu, _ = cv2.threshold(np.clip(bnd_grad, 0, 255).astype(np.uint8), 0, 255, cv2.THRESH_OTSU)
        g_otsu = max(float(g_otsu), min_grad)
        thr = g_otsu * grad_factor
        
        low_bnd = (boundary > 0) & (grad < thr)
        shadow_mask = np.zeros_like(result)
        shadow_mask[low_bnd] = 255
        n_shadow = int(np.count_nonzero(shadow_mask))
        if n_shadow == 0:
            break
        
        result = cv2.bitwise_and(result, cv2.bitwise_not(shadow_mask))
        total_removed += n_shadow
    
    # 闭运算修复
    if close_ksize >= 3 and total_removed > 0:
        kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close_ksize, close_ksize))
        result = cv2.morphologyEx(result, cv2.MORPH_CLOSE, kernel_close)
    
    return result, total_removed

def fill_internal_holes(mask: np.ndarray) -> np.ndarray:
    """填充内部孔洞"""
    contours, _ = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    filled = mask.copy()
    for i in range(1, len(contours)):
        if len(contours[i]) > 40:
            cv2.drawContours(filled, [contours[i]], -1, 255, -1)
    
    # 轻量闭运算
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    filled = cv2.morphologyEx(filled, cv2.MORPH_CLOSE, kernel, iterations=1)
    
    # 开运算去噪
    kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    filled = cv2.morphologyEx(filled, cv2.MORPH_OPEN, kernel_open)
    
    return filled

def smooth_closed_spline(pts: np.ndarray, sigma: float = 4.0, debug: bool = False) -> np.ndarray:
    """平滑闭合样条"""
    if len(pts) < 3:
        return pts.reshape(-1, 1, 2)
    
    # 去除重复点
    unique_pts = [pts[0]]
    for i in range(1, len(pts)):
        if np.linalg.norm(pts[i] - pts[i-1]) > 1e-6:
            unique_pts.append(pts[i])
    if len(unique_pts) < 3:
        return pts.reshape(-1, 1, 2)
    pts = np.array(unique_pts)
    
    # 高斯平滑
    if len(pts) > 10 and sigma > 0:
        from scipy import ndimage
        x = pts[:, 0]
        y = pts[:, 1]
        x_smooth = ndimage.gaussian_filter1d(x, sigma=sigma, mode='wrap')
        y_smooth = ndimage.gaussian_filter1d(y, sigma=sigma, mode='wrap')
        pts = np.column_stack([x_smooth, y_smooth])
    
    return pts.reshape(-1, 1, 2).astype(np.int32)

def extract_advanced_tool_contour(warped_image: np.ndarray, 
                                 dilate_px: int = 7,
                                 use_lab: bool = True,
                                 use_blackhat: bool = True,
                                 use_canny: bool = True) -> Optional[np.ndarray]:
    """
    高级工具轮廓提取
    使用四策略并集算法提取工具的主要轮廓
    """
    if warped_image is None:
        return None
    
    # 转换为灰度图
    if len(warped_image.shape) == 3:
        bgr = warped_image
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    else:
        gray = warped_image
        bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    
    # 策略1: Top-Hat + adaptive + Otsu
    deshedow, _ = tophat_deshedow(gray, kernel_size=31)
    mask_a = mask_scheme_a(deshedow, block=31, C=8)
    
    # 策略2: LAB暗区捕获
    mask_lab = None
    if use_lab:
        try:
            mask_lab, _, _ = strategy_lab_dark(bgr, l_threshold_ratio=0.55)
        except Exception:
            mask_lab = None
    
    # 策略3: BlackHat去阴影
    mask_bh = None
    if use_blackhat:
        try:
            mask_bh, _, _ = strategy_blackhat_corrected(gray, kernel_size=21)
        except Exception:
            mask_bh = None
    
    # 策略4: Canny桥接
    mask_canny = None
    if use_canny:
        try:
            mask_canny = strategy_canny_bridge(gray, low_thresh=40, high_thresh=120)
        except Exception:
            mask_canny = None
    
    # 四策略并集
    union = mask_a.copy()
    if mask_lab is not None:
        union = cv2.bitwise_or(union, mask_lab)
    if mask_bh is not None:
        union = cv2.bitwise_or(union, mask_bh)
    if mask_canny is not None:
        union = cv2.bitwise_or(union, mask_canny)
    
    # 开运算去噪
    kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    union = cv2.morphologyEx(union, cv2.MORPH_OPEN, kernel_open)
    
    # 阴影去除
    union, _ = remove_shadow_adaptive(gray, union)
    
    # 填充孔洞
    union = fill_internal_holes(union)
    
    # 安全检查
    total_px = int(np.count_nonzero(union))
    if total_px > union.size * 0.85:
        union = mask_a
        union = fill_internal_holes(union)
    
    # 提取最大连通块
    contours, _ = cv2.findContours(union, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return None
    
    best_contour = max(contours, key=cv2.contourArea)
    
    # 膨胀余量
    tool_mask = np.zeros_like(union)
    cv2.drawContours(tool_mask, [best_contour], -1, 255, -1)
    
    if dilate_px > 0:
        kernel_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate_px*2+1, dilate_px*2+1))
        tool_mask = cv2.dilate(tool_mask, kernel_dilate, iterations=1)
    
    # 获取最终轮廓
    final_contours, _ = cv2.findContours(tool_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not final_contours:
        return None
    
    final_contour = max(final_contours, key=cv2.contourArea)
    
    # 平滑处理
    try:
        pts = final_contour.reshape(-1, 2).astype(np.float64)
        smooth_contour = smooth_closed_spline(pts, sigma=4.0)
        return smooth_contour
    except Exception:
        return final_contour.reshape(-1, 1, 2)

def test_advanced_contour_extraction():
    """测试高级轮廓提取"""
    print("测试高级工具轮廓提取...")
    
    # 读取校正后的图像
    warped_image = cv2.imread('test_results/paper_detection/optimized_warped_result.jpg')
    if warped_image is None:
        print("无法读取校正后的图像")
        return
    
    # 提取工具轮廓
    contour = extract_advanced_tool_contour(warped_image)
    
    if contour is not None:
        print(f"✓ 成功提取工具轮廓，点数: {len(contour)}")
        
        # 创建可视化结果
        result_img = warped_image.copy()
        cv2.drawContours(result_img, [contour], -1, (0, 0, 255), 2)
        
        # 保存结果
        cv2.imwrite('test_results/tool_contours/advanced_tool_contour.jpg', result_img)
        print("✓ 工具轮廓图像已保存到: test_results/tool_contours/advanced_tool_contour.jpg")
        
        return contour
    else:
        print("✗ 未能提取到工具轮廓")
        return None

if __name__ == "__main__":
    test_advanced_contour_extraction()