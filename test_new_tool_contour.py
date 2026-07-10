#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试新的工具轮廓检测算法 v26
"""

import sys
import os
import numpy as np
import cv2

# 添加引用路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'reference'))

from tool_contour_v26 import extract_tool_contour

def test_new_tool_contour():
    """测试新的工具轮廓检测算法"""
    print("🔍 测试新的工具轮廓检测算法 v26...")
    
    # 读取测试图像
    image_path = "test_results/original/testpic.jpg"
    
    if not os.path.exists(image_path):
        print(f"❌ 找不到测试图像: {image_path}")
        return False
    
    try:
        # 使用新算法提取工具轮廓
        contour, warped = extract_tool_contour(image_path)
        
        if contour is None or warped is None:
            print("❌ 新算法未能检测到工具轮廓或纸张")
            return False
        
        print(f"✅ 新算法成功检测到工具轮廓!")
        print(f"   轮廓点数: {len(contour)}")
        
        # 计算轮廓面积
        area = cv2.contourArea(contour)
        area_ratio = area / (warped.shape[0] * warped.shape[1])
        print(f"   轮廓面积: {area:.0f} 像素")
        print(f"   面积占比: {area_ratio:.3f}")
        
        # 保存结果
        result_img = warped.copy()
        cv2.drawContours(result_img, [contour], -1, (0, 0, 255), 2)
        cv2.imwrite('test_results/tool_contours/new_tool_contour_v26.jpg', result_img)
        cv2.imwrite('test_results/tool_contours/new_warped_v26.jpg', warped)
        print("✅ 新算法检测结果已保存到: test_results/tool_contours/new_tool_contour_v26.jpg")
        print("✅ 透视校正结果已保存到: test_results/tool_contours/new_warped_v26.jpg")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试新算法时发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_new_tool_contour()
    if success:
        print("\n🎉 新的工具轮廓检测算法 v26 测试通过!")
    else:
        print("\n💥 新的工具轮廓检测算法 v26 测试失败!")