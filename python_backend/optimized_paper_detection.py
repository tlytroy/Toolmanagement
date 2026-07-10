#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
鲁棒的纸张检测模块
基于新的鲁棒纸张检测算法，解决了六角扳手等复杂场景下的检测问题
"""

import sys
import os
import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional

# 添加引用路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'reference', 'pkg_paper_detection'))

from robust_paper_detector import detect_paper_corners_robust, warp_paper

def detect_paper_corners_robust_wrapper(image_array: np.ndarray) -> List[Dict[str, float]]:
    """
    鲁棒检测A4纸四角的新算法
    解决了六角扳手等复杂场景下的检测问题，确保宽高比接近标准A4比例(1.414)
    """
    try:
        # 使用新算法检测纸张角点
        result = detect_paper_corners_robust(image_array)
        if result is None:
            return []
        
        corners, candidates = result
        
        # 转换为所需的格式
        return [{"x": float(x), "y": float(y)} for x, y in corners]
    except Exception as e:
        print(f"鲁棒纸张检测算法执行出错: {e}")
        return []

def warp_paper_wrapper(image_array: np.ndarray, corners: List[Dict[str, float]]) -> np.ndarray:
    """
    使用新算法进行透视校正
    """
    try:
        # 转换角点格式
        pts = np.array([[p["x"], p["y"]] for p in corners], dtype=np.float32)
        
        # 进行透视校正
        warped = warp_paper(image_array, pts)
        return warped
    except Exception as e:
        print(f"透视校正执行出错: {e}")
        # 如果新算法失败，回退到原来的实现
        return _fallback_perspective_warp(image_array, corners)

def _fallback_perspective_warp(image_array: np.ndarray, corners: List[Dict[str, float]]) -> np.ndarray:
    """
    回退的透视校正实现
    """
    # 提取角点坐标
    pts = np.array([[p["x"], p["y"]] for p in corners], dtype=np.float32)
    
    # 计算目标矩形的宽度和高度
    width = 210 * 4  # A4纸比例，假设4px/mm
    height = 297 * 4
    
    # 目标点（左上、右上、右下、左下）
    dst_pts = np.array([
        [0, 0],
        [width - 1, 0],
        [width - 1, height - 1],
        [0, height - 1]
    ], dtype=np.float32)
    
    # 计算透视变换矩阵
    matrix = cv2.getPerspectiveTransform(pts, dst_pts)
    
    # 应用透视变换
    warped = cv2.warpPerspective(image_array, matrix, (width, height))
    
    return warped

def test_robust_paper_detection():
    """测试鲁棒的纸张检测"""
    print("测试鲁棒的纸张检测算法...")
    
    # 读取测试图像
    image_path = "test_results/original/testpic.jpg"
    image = cv2.imread(image_path)
    
    if image is None:
        print("无法读取测试图像")
        return
    
    # 检测纸张角点
    corners = detect_paper_corners_robust_wrapper(image)
    
    if corners:
        print(f"✓ 成功检测到纸张角点: {corners}")
        
        # 进行透视校正
        warped = warp_paper_wrapper(image, corners)
        print(f"✓ 透视校正完成，尺寸: {warped.shape[1]}x{warped.shape[0]}")
        
        # 可视化结果
        result_img = image.copy()
        for i, corner in enumerate(corners):
            x, y = int(corner["x"]), int(corner["y"])
            cv2.circle(result_img, (x, y), 8, (0, 0, 255), -1)
            cv2.putText(result_img, f"{i+1}", (x+10, y+10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        
        # 保存结果
        cv2.imwrite('test_results/paper_detection/robust_paper_detection.jpg', result_img)
        cv2.imwrite('test_results/paper_detection/robust_warped_result.jpg', warped)
        print("✓ 鲁棒纸张检测结果已保存到: test_results/paper_detection/robust_paper_detection.jpg")
        print("✓ 透视校正结果已保存到: test_results/paper_detection/robust_warped_result.jpg")
        
        # 计算宽高比
        pts = np.array([[p["x"], p["y"]] for p in corners], dtype=float)
        d01 = np.linalg.norm(pts[0] - pts[1])
        d12 = np.linalg.norm(pts[1] - pts[2])
        d23 = np.linalg.norm(pts[2] - pts[3])
        d30 = np.linalg.norm(pts[3] - pts[0])
        ar = max((d01 + d23) / 2, (d12 + d30) / 2) / max(1, min((d01 + d23) / 2, (d12 + d30) / 2))
        print(f"✓ 检测宽高比: {ar:.3f} (A4 标准≈1.414)")
    else:
        print("✗ 未能检测到纸张角点")

if __name__ == "__main__":
    test_robust_paper_detection()
