#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
生成测试结果图片以可视化修复效果
"""

import requests
import cv2
import numpy as np
import os
import base64

def generate_visual_test_results():
    """生成可视化的测试结果"""
    print("开始生成测试结果图片...")
    
    # 确保测试结果目录存在
    os.makedirs('test_results/paper_detection', exist_ok=True)
    os.makedirs('test_results/tool_contours', exist_ok=True)
    
    # 测试图像路径
    test_image_path = "public/testpic.jpg"
    
    if not os.path.exists(test_image_path):
        print(f"❌ 找不到测试图像: {test_image_path}")
        return
    
    print(f"使用测试图像: {test_image_path}")
    
    # 1. 纸张检测测试
    print("\n1. 执行纸张检测...")
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
    
    # 保存检测结果图片（带角点标记）
    original_img = cv2.imread(test_image_path)
    result_img = original_img.copy()
    
    # 在原图上标记检测到的角点
    for i, corner in enumerate(paper_result['corners']):
        x, y = int(corner['x']), int(corner['y'])
        cv2.circle(result_img, (x, y), 8, (0, 0, 255), -1)
        cv2.putText(result_img, f"{i+1}", (x+10, y+10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
    
    # 保存角点检测结果
    cv2.imwrite('test_results/paper_detection/corners_detected.jpg', result_img)
    print("✅ 角点检测结果已保存到: test_results/paper_detection/corners_detected.jpg")
    
    # 保存校正后的图像
    warped_data = paper_result['warped_image'].split(',')[1]
    warped_image = base64.b64decode(warped_data)
    with open('test_results/paper_detection/warped_result.jpg', 'wb') as f:
        f.write(warped_image)
    
    warped_img = cv2.imread('test_results/paper_detection/warped_result.jpg')
    if warped_img is not None:
        height, width = warped_img.shape[:2]
        print(f"✅ 透视校正完成，尺寸: {width}x{height}")
    
    # 2. 工具轮廓提取测试
    print("\n2. 执行工具轮廓提取...")
    with open('test_results/paper_detection/warped_result.jpg', 'rb') as f:
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
    
    # 在校正后的图像上绘制轮廓
    if warped_img is not None and len(contour_result['primitives']) > 0:
        contour_img = warped_img.copy()
        
        # 绘制检测到的轮廓
        for primitive in contour_result['primitives']:
            if primitive['type'] == 'polyline':
                points = [(int(p['x']), int(p['y'])) for p in primitive['points']]
                points = np.array(points, np.int32)
                cv2.polylines(contour_img, [points], True, (0, 0, 255), 2)
        
        # 保存轮廓检测结果
        cv2.imwrite('test_results/tool_contours/tool_contour_result.jpg', contour_img)
        print("✅ 工具轮廓检测结果已保存到: test_results/tool_contours/tool_contour_result.jpg")
    
    print("\n🎉 所有测试结果图片已生成!")

if __name__ == "__main__":
    generate_visual_test_results()