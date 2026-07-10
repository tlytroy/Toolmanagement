#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试修复后的功能
"""

import requests
import cv2
import numpy as np
import os

def test_paper_detection_and_contour_extraction():
    """测试纸张检测和工具轮廓提取"""
    print("开始测试修复后的功能...")
    
    # 测试图像路径
    test_image_path = "test_results/original/testpic.jpg"
    
    if not os.path.exists(test_image_path):
        print(f"❌ 找不到测试图像: {test_image_path}")
        return
    
    # 1. 测试纸张检测
    print("\n1. 测试纸张检测...")
    with open(test_image_path, 'rb') as f:
        files = {'file': f}
        response = requests.post('http://localhost:8001/detect-paper', files=files)
    
    if response.status_code != 200:
        print(f"❌ 纸张检测失败，状态码: {response.status_code}")
        return
    
    paper_result = response.json()
    if not paper_result.get('success'):
        print(f"❌ 纸张检测失败: {paper_result.get('error')}")
        return
    
    print("✅ 纸张检测成功")
    print(f"   检测到角点: {paper_result['corners']}")
    
    # 保存校正后的图像用于下一步测试
    import base64
    warped_data = paper_result['warped_image'].split(',')[1]
    warped_image = base64.b64decode(warped_data)
    with open('test_warped_image.jpg', 'wb') as f:
        f.write(warped_image)
    
    # 检查校正后图像的尺寸
    warped_img = cv2.imread('test_warped_image.jpg')
    if warped_img is not None:
        height, width = warped_img.shape[:2]
        aspect_ratio = width / height
        print(f"   校正后图像尺寸: {width}x{height}")
        print(f"   宽高比: {aspect_ratio:.3f} (A4标准≈0.707)")
        
        # 检查是否解决了图像被压扁的问题
        expected_width = 840  # 210 * 4
        expected_height = 1188  # 297 * 4
        if abs(width - expected_width) <= 10 and abs(height - expected_height) <= 10:
            print("✅ 图像尺寸符合预期，解决了压扁问题")
        else:
            print(f"⚠️  图像尺寸与预期略有差异，期望: {expected_width}x{expected_height}")
    
    # 2. 测试工具轮廓提取
    print("\n2. 测试工具轮廓提取...")
    with open('test_warped_image.jpg', 'rb') as f:
        files = {'file': f}
        response = requests.post('http://localhost:8001/extract-contours', files=files)
    
    if response.status_code != 200:
        print(f"❌ 工具轮廓提取失败，状态码: {response.status_code}")
        return
    
    contour_result = response.json()
    if not contour_result.get('success'):
        print(f"❌ 工具轮廓提取失败: {contour_result.get('error')}")
        return
    
    print("✅ 工具轮廓提取成功")
    print(f"   检测到基元数量: {len(contour_result['primitives'])}")
    if 'summary' in contour_result:
        print(f"   概要: {contour_result['summary']}")
    
    # 清理临时文件
    if os.path.exists('test_warped_image.jpg'):
        os.remove('test_warped_image.jpg')
    
    print("\n🎉 所有测试完成!")

if __name__ == "__main__":
    test_paper_detection_and_contour_extraction()