#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import cv2
import numpy as np
from typing import List, Tuple, Optional

def detect_paper_corners_precise(image: np.ndarray) -> Optional[List[Tuple[float, float]]]:
    """
    精确检测A4纸四角的改进算法
    """
    # 转换为灰度图
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # 尝试多种预处理方法
    methods = [
        # 方法1: Canny边缘检测 + 形态学操作
        lambda img: _preprocess_canny(img),
        # 方法2: 自适应阈值
        lambda img: _preprocess_adaptive_threshold(img),
        # 方法3: Otsu阈值 + 形态学
        lambda img: _preprocess_otsu_morphology(img)
    ]
    
    best_corners = None
    best_score = 0
    
    for method in methods:
        try:
            processed = method(gray)
            corners = _find_paper_corners_from_processed(processed, image.shape)
            if corners:
                # 计算角点质量分数（基于角点分布的合理性）
                score = _calculate_corner_quality_score(corners, image.shape)
                if score > best_score:
                    best_score = score
                    best_corners = corners
        except Exception as e:
            print(f"处理方法失败: {e}")
            continue
    
    return best_corners

def _preprocess_canny(gray: np.ndarray) -> np.ndarray:
    """Canny边缘检测预处理"""
    # 高斯模糊减少噪声
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    # Canny边缘检测
    edges = cv2.Canny(blurred, 50, 150)
    # 形态学闭运算连接边缘
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    return edges

def _preprocess_adaptive_threshold(gray: np.ndarray) -> np.ndarray:
    """自适应阈值预处理"""
    # 高斯模糊
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    # 自适应阈值
    binary = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY, 11, 2)
    # 取反（纸张通常是亮的）
    binary = cv2.bitwise_not(binary)
    # 形态学操作
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    return binary

def _preprocess_otsu_morphology(gray: np.ndarray) -> np.ndarray:
    """Otsu阈值 + 形态学预处理"""
    # 高斯模糊
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    # Otsu阈值
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # 形态学操作
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    return binary

def _find_paper_corners_from_processed(processed: np.ndarray, image_shape: Tuple[int, int]) -> Optional[List[Tuple[float, float]]]:
    """从预处理图像中查找纸张角点"""
    # 查找轮廓
    contours, _ = cv2.findContours(processed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return None
    
    # 按面积排序
    contours_sorted = sorted(contours, key=cv2.contourArea, reverse=True)
    
    # 寻找最佳四边形
    for contour in contours_sorted[:10]:  # 检查前10个最大轮廓
        area = cv2.contourArea(contour)
        # 忽略太小或太大的轮廓
        image_area = image_shape[0] * image_shape[1]
        if area < image_area * 0.1 or area > image_area * 0.9:
            continue
        
        # 多边形近似
        epsilon = 0.02 * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)
        
        # 检查是否为四边形
        if len(approx) == 4:
            # 检查是否为凸四边形
            if cv2.isContourConvex(approx):
                # 提取角点坐标
                corners = [(float(point[0][0]), float(point[0][1])) for point in approx]
                return _order_points(corners)
    
    return None

def _order_points(pts: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """
    对四个点进行排序：左上、右上、右下、左下
    """
    # 计算质心
    centroid_x = sum(p[0] for p in pts) / 4
    centroid_y = sum(p[1] for p in pts) / 4
    
    # 根据相对于质心的位置分类
    top_left = min(pts, key=lambda p: p[0] + p[1])      # x+y最小
    top_right = max(pts, key=lambda p: p[0] - p[1])     # x-y最大
    bottom_right = max(pts, key=lambda p: p[0] + p[1])  # x+y最大
    bottom_left = min(pts, key=lambda p: p[0] - p[1])   # x-y最小
    
    return [top_left, top_right, bottom_right, bottom_left]

def _calculate_corner_quality_score(corners: List[Tuple[float, float]], image_shape: Tuple[int, int]) -> float:
    """
    计算角点质量分数
    """
    if len(corners) != 4:
        return 0.0
    
    h, w = image_shape[:2]
    
    # 检查角点是否过于靠近图像边界（避免选择整幅图像的边界）
    margin = min(w, h) * 0.1  # 10%边距
    valid_corners = 0
    for x, y in corners:
        if margin <= x <= w - margin and margin <= y <= h - margin:
            valid_corners += 1
    
    # 如果所有角点都在边界附近，则分数较低
    if valid_corners == 4:
        return 1.0
    elif valid_corners >= 2:
        return 0.5
    else:
        return 0.1

def visualize_corners(image: np.ndarray, corners: List[Tuple[float, float]], output_path: str = "precise_corners.jpg"):
    """
    可视化检测到的角点
    """
    if not corners or len(corners) != 4:
        print("无效的角点数据")
        return
    
    # 复制图像用于绘制
    result_img = image.copy()
    
    # 绘制四边形轮廓
    points = np.array([(int(x), int(y)) for x, y in corners], dtype=np.int32)
    cv2.polylines(result_img, [points], True, (0, 255, 0), 3)
    
    # 标记角点
    corner_names = ['左上', '右上', '右下', '左下']
    for i, (x, y) in enumerate(corners):
        # 绘制角点
        cv2.circle(result_img, (int(x), int(y)), 8, (0, 0, 255), -1)
        # 添加标签
        cv2.putText(result_img, f'{corner_names[i]}({int(x)},{int(y)})', 
                   (int(x) + 10, int(y) + 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    # 保存结果
    cv2.imwrite(output_path, result_img)
    print(f"角点检测结果已保存到: {output_path}")
    
    # 打印角点坐标
    print("检测到的纸张四角坐标:")
    for i, (x, y) in enumerate(corners):
        print(f"  {corner_names[i]}: ({x:.1f}, {y:.1f})")

# 测试函数
def test_paper_detection(image_path: str):
    """
    测试纸张检测功能
    """
    # 读取图像
    image = cv2.imread(image_path)
    if image is None:
        print(f"无法读取图像: {image_path}")
        return
    
    print(f"处理图像: {image_path}")
    print(f"图像尺寸: {image.shape}")
    
    # 检测角点
    corners = detect_paper_corners_precise(image)
    
    if corners:
        print("✓ 成功检测到纸张四角!")
        visualize_corners(image, corners, "precise_paper_detection.jpg")
    else:
        print("✗ 未能检测到纸张四角")

if __name__ == "__main__":
    test_paper_detection("testpic.jpg")