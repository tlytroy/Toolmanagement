#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试新的鲁棒纸张检测算法
"""

import sys
import os
import numpy as np
import cv2

# 添加引用路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'reference', 'pkg_paper_detection'))

from robust_paper_detector import detect_paper_corners_robust, warp_paper

def test_new_algorithm():
    """测试新算法"""
    print("🔍 测试新的鲁棒纸张检测算法...")
    
    # 读取测试图像
    image_path = "test_results/original/testpic.jpg"
    
    if not os.path.exists(image_path):
        print(f"❌ 找不到测试图像: {image_path}")
        return False
    
    img = cv2.imread(image_path)
    if img is None:
        print(f"❌ 无法读取测试图像: {image_path}")
        return False
    
    print(f"✅ 成功读取测试图像: {image_path} (尺寸: {img.shape})")
    
    # 使用新算法检测纸张角点
    try:
        result = detect_paper_corners_robust(img)
        if result is None:
            print("❌ 新算法未能检测到纸张")
            return False
        
        corners, candidates = result
        print(f"✅ 新算法成功检测到纸张角点!")
        print(f"   角点坐标: {corners}")
        
        # 计算宽高比
        pts = np.array(corners, float).reshape(-1, 2)
        d01 = np.linalg.norm(pts[0] - pts[1])
        d12 = np.linalg.norm(pts[1] - pts[2])
        d23 = np.linalg.norm(pts[2] - pts[3])
        d30 = np.linalg.norm(pts[3] - pts[0])
        ar = max((d01 + d23) / 2, (d12 + d30) / 2) / max(1, min((d01 + d23) / 2, (d12 + d30) / 2))
        print(f"   检测宽高比: {ar:.3f} (A4 标准≈1.414)")
        print(f"   采用方案: {candidates[0][2]}  分数: {candidates[0][1]:.3f}")
        
        # 显示前3个候选方案
        print(f"   候选方案 Top3:")
        for i, (c, s, m) in enumerate(candidates[:3]):
            print(f"     {i+1}. {m:12s} score={s:.3f}")
        
        # 进行透视校正
        warped = warp_paper(img, corners)
        print(f"   透视校正后尺寸: {warped.shape[1]}x{warped.shape[0]}")
        
        # 保存结果
        cv2.imwrite('test_results/paper_detection/new_robust_paper_detection.jpg', warped)
        print("✅ 新算法检测结果已保存到: test_results/paper_detection/new_robust_paper_detection.jpg")
        
        # 可视化角点
        vis_img = img.copy()
        for i, (x, y) in enumerate(corners):
            cv2.circle(vis_img, (int(x), int(y)), 8, (0, 0, 255), -1)
            cv2.putText(vis_img, f"{i+1}", (int(x)+10, int(y)+10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        
        cv2.imwrite('test_results/paper_detection/new_corners_detected.jpg', vis_img)
        print("✅ 角点可视化结果已保存到: test_results/paper_detection/new_corners_detected.jpg")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试新算法时发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_new_algorithm()
    if success:
        print("\n🎉 新的鲁棒纸张检测算法测试通过!")
    else:
        print("\n💥 新的鲁棒纸张检测算法测试失败!")