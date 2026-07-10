f#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
对比新旧纸张检测算法的性能
"""

import sys
import os
import numpy as np
import cv2
import time

# 添加引用路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'reference', 'pkg_paper_detection'))

# 导入新算法
from robust_paper_detector import detect_paper_corners_robust, warp_paper

# 导入旧算法
from improved_paper_detector import detect_paper_corners_precise

def calculate_aspect_ratio(corners):
    """计算四边形的宽高比"""
    pts = np.array(corners, float).reshape(-1, 2)
    d01 = np.linalg.norm(pts[0] - pts[1])
    d12 = np.linalg.norm(pts[1] - pts[2])
    d23 = np.linalg.norm(pts[2] - pts[3])
    d30 = np.linalg.norm(pts[3] - pts[0])
    ar = max((d01 + d23) / 2, (d12 + d30) / 2) / max(1, min((d01 + d23) / 2, (d12 + d30) / 2))
    return ar

def test_old_algorithm(img):
    """测试旧算法"""
    start_time = time.time()
    try:
        corners = detect_paper_corners_precise(img)
        elapsed_time = time.time() - start_time
        
        if corners:
            # 转换格式
            corner_list = [{"x": float(x), "y": float(y)} for x, y in corners]
            aspect_ratio = calculate_aspect_ratio(corners)
            return True, corner_list, aspect_ratio, elapsed_time
        else:
            return False, [], 0, elapsed_time
    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"旧算法执行出错: {e}")
        return False, [], 0, elapsed_time

def test_new_algorithm(img):
    """测试新算法"""
    start_time = time.time()
    try:
        result = detect_paper_corners_robust(img)
        elapsed_time = time.time() - start_time
        
        if result is not None:
            corners, candidates = result
            aspect_ratio = calculate_aspect_ratio(corners)
            # 转换格式
            corner_list = [{"x": float(x), "y": float(y)} for x, y in corners]
            return True, corner_list, aspect_ratio, elapsed_time, candidates[0][2] if candidates else "unknown"
        else:
            return False, [], 0, elapsed_time, ""
    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"新算法执行出错: {e}")
        return False, [], 0, elapsed_time, ""

def compare_algorithms():
    """对比两种算法"""
    print("🔍 对比新旧纸张检测算法...")
    
    # 读取测试图像
    image_path = "test_results/original/testpic.jpg"
    
    if not os.path.exists(image_path):
        print(f"❌ 找不到测试图像: {image_path}")
        return
    
    img = cv2.imread(image_path)
    if img is None:
        print(f"❌ 无法读取测试图像: {image_path}")
        return
    
    print(f"✅ 成功读取测试图像: {image_path} (尺寸: {img.shape})")
    print()
    
    # 测试旧算法
    print("🔄 测试旧算法...")
    old_success, old_corners, old_aspect, old_time = test_old_algorithm(img)
    
    # 测试新算法
    print("🔄 测试新算法...")
    new_success, new_corners, new_aspect, new_time, method = test_new_algorithm(img)
    
    # 输出结果对比
    print("\n" + "="*60)
    print("📊 算法对比结果")
    print("="*60)
    
    print(f"{'指标':<15} {'旧算法':<20} {'新算法':<20}")
    print("-"*60)
    print(f"{'检测成功率':<15} {'✅ 成功' if old_success else '❌ 失败':<20} {'✅ 成功' if new_success else '❌ 失败':<20}")
    print(f"{'处理时间':<15} {f'{old_time:.3f}s' if old_success else 'N/A':<20} {f'{new_time:.3f}s' if new_success else 'N/A':<20}")
    print(f"{'宽高比':<15} {f'{old_aspect:.3f}' if old_success else 'N/A':<20} {f'{new_aspect:.3f}' if new_success else 'N/A':<20}")
    print(f"{'与A4标准差值':<15} {f'{abs(old_aspect-1.414):.3f}' if old_success else 'N/A':<20} {f'{abs(new_aspect-1.414):.3f}' if new_success else 'N/A':<20}")
    print(f"{'采用方案':<15} {'N/A':<20} {method:<20}")
    
    # 评估结果
    print("\n" + "="*60)
    print("🏆 评估结论")
    print("="*60)
    
    if new_success and old_success:
        if abs(new_aspect - 1.414) < abs(old_aspect - 1.414):
            print("✅ 新算法在宽高比准确性方面更优")
        else:
            print("ℹ️  两种算法在宽高比准确性方面相当")
            
        if new_time < old_time:
            print("✅ 新算法在处理速度方面更优")
        else:
            print("ℹ️  两种算法在处理速度方面相当")
            
        print(f"✅ 新算法检测到的角点: {new_corners}")
        print(f"✅ 新算法宽高比: {new_aspect:.3f} (A4标准: 1.414)")
        
        # 保存新算法的结果
        warped = warp_paper(img, np.array([[p["x"], p["y"]] for p in new_corners]))
        cv2.imwrite('test_results/paper_detection/algorithm_comparison_new.jpg', warped)
        print("✅ 新算法透视校正结果已保存到: test_results/paper_detection/algorithm_comparison_new.jpg")
        
    elif new_success and not old_success:
        print("✅ 新算法成功检测到纸张，旧算法失败")
        print(f"✅ 新算法检测到的角点: {new_corners}")
        print(f"✅ 新算法宽高比: {new_aspect:.3f} (A4标准: 1.414)")
        
    elif old_success and not new_success:
        print("❌ 新算法失败，旧算法成功（这不应该发生）")
    else:
        print("❌ 两种算法都未能检测到纸张")

if __name__ == "__main__":
    compare_algorithms()