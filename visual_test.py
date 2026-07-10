#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import cv2
import numpy as np
import requests
import base64
import os

def save_base64_image(base64_data, filename):
    """保存base64编码的图像"""
    # 移除数据URL前缀
    if ',' in base64_data:
        header, base64_data = base64_data.split(',', 1)
    
    # 解码base64数据
    image_data = base64.b64decode(base64_data)
    
    # 保存到文件
    with open(filename, 'wb') as f:
        f.write(image_data)
    
    print(f"图像已保存到: {filename}")

def visualize_results():
    """可视化测试结果"""
    print("开始测试图像处理和可视化效果...")
    
    try:
        # 检查测试图片是否存在
        if not os.path.exists('testpic.jpg'):
            print("错误: 找不到测试图片 testpic.jpg")
            return
            
        # 读取原始图像
        original_img = cv2.imread('testpic.jpg')
        if original_img is None:
            print("错误: 无法读取测试图片")
            return
            
        print(f"原始图像尺寸: {original_img.shape}")
        
        # 发送到后端处理
        with open('testpic.jpg', 'rb') as f:
            files = {'file': ('testpic.jpg', f, 'image/jpeg')}
            response = requests.post('http://localhost:8000/process-image', files=files)
            
        if response.status_code != 200:
            print(f"错误: 后端处理失败 (状态码: {response.status_code})")
            return
            
        result = response.json()
        
        if not result.get('success'):
            print(f"错误: 处理失败 - {result.get('error', '未知错误')}")
            return
            
        print("✓ 后端处理成功!")
        print(f"检测到的基元数量: {len(result.get('primitives', []))}")
        print(f"基元统计: {result.get('summary', {})}")
        
        # 保存校正后的图像
        warped_image_data = result['calibration']['warped_image']
        save_base64_image(warped_image_data, 'warped_result.jpg')
        
        # 显示角点信息
        corners = result['calibration']['corners']
        print(f"检测到的角点: {corners}")
        
        # 在原始图像上绘制角点
        img_with_corners = original_img.copy()
        for i, corner in enumerate(corners):
            x, y = int(corner['x']), int(corner['y'])
            cv2.circle(img_with_corners, (x, y), 5, (0, 0, 255), -1)
            cv2.putText(img_with_corners, str(i+1), (x+10, y+10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # 保存带角点标记的图像
        cv2.imwrite('corners_detected.jpg', img_with_corners)
        print("✓ 角点检测图像已保存为: corners_detected.jpg")
        
        # 读取校正后的图像
        warped_img = cv2.imread('warped_result.jpg')
        if warped_img is not None:
            print(f"校正后图像尺寸: {warped_img.shape}")
            
            # 显示图像信息
            print("\n=== 处理结果 ===")
            print("1. 原始图像: testpic.jpg")
            print("2. 角点检测: corners_detected.jpg")
            print("3. 校正图像: warped_result.jpg")
            print("\n您可以使用任意图像查看器打开这些文件来查看效果!")
            
            # 如果有轮廓信息，也显示出来
            primitives = result.get('primitives', [])
            if primitives:
                print(f"\n=== 检测到的基元 ({len(primitives)} 个) ===")
                for i, primitive in enumerate(primitives[:5]):  # 只显示前5个
                    print(f"  {i+1}. 类型: {primitive['type']}, 点数: {len(primitive['points'])}")
                if len(primitives) > 5:
                    print(f"  ... 还有 {len(primitives)-5} 个基元")
        else:
            print("警告: 无法读取校正后的图像")
            
    except FileNotFoundError:
        print("错误: 找不到测试图片 testpic.jpg")
    except requests.exceptions.ConnectionError:
        print("错误: 无法连接到后端服务，请确保Python后端正在运行 (python_backend/main.py)")
    except Exception as e:
        print(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    visualize_results()