#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import base64
from PIL import Image
import io

def test_improved_paper_detection():
    """
    测试改进后的纸张检测算法
    """
    print("开始测试改进后的纸张检测算法...")
    
    # 读取测试图像
    with open('testpic.jpg', 'rb') as f:
        image_data = f.read()
    
    # 发送到后端API
    files = {'file': ('testpic.jpg', image_data, 'image/jpeg')}
    
    try:
        response = requests.post('http://localhost:8000/process-image', files=files)
        
        if response.status_code == 200:
            result = response.json()
            
            if result['success']:
                print("✓ 后端处理成功!")
                print(f"检测到的基元数量: {len(result['primitives'])}")
                
                # 显示基元统计
                summary = result['summary']
                print(f"基元统计: {summary}")
                
                # 显示检测到的角点
                corners = result['calibration']['corners']
                print("检测到的纸张四角:")
                corner_names = ['左上', '右上', '右下', '左下']
                for i, corner in enumerate(corners):
                    print(f"  {corner_names[i]}: ({corner['x']:.1f}, {corner['y']:.1f})")
                
                # 保存校正后的图像
                if 'warped_image' in result['calibration']:
                    # 解码base64图像数据
                    header, encoded = result['calibration']['warped_image'].split(',', 1)
                    image_bytes = base64.b64decode(encoded)
                    
                    # 保存图像
                    with open('improved_warped_result.jpg', 'wb') as f:
                        f.write(image_bytes)
                    print("✓ 校正图像已保存为: improved_warped_result.jpg")
                
                # 创建带角点标记的图像
                create_corners_visualization(corners)
                
            else:
                print(f"✗ 后端处理失败: {result.get('error', '未知错误')}")
        else:
            print(f"✗ HTTP请求失败: {response.status_code}")
            print(response.text)
            
    except requests.exceptions.ConnectionError:
        print("✗ 无法连接到后端服务，请确保后端服务正在运行")
    except Exception as e:
        print(f"✗ 测试过程中发生错误: {e}")

def create_corners_visualization(corners):
    """
    创建带角点标记的原始图像
    """
    import cv2
    import numpy as np
    
    # 读取原始图像
    image = cv2.imread('testpic.jpg')
    if image is None:
        print("无法读取原始图像")
        return
    
    # 在图像上标记角点
    result_img = image.copy()
    
    # 绘制四边形轮廓
    if len(corners) == 4:
        points = np.array([(int(c['x']), int(c['y'])) for c in corners], dtype=np.int32)
        cv2.polylines(result_img, [points], True, (0, 255, 0), 3)
    
    # 标记角点
    corner_names = ['左上', '右上', '右下', '左下']
    for i, corner in enumerate(corners):
        x, y = int(corner['x']), int(corner['y'])
        # 绘制角点
        cv2.circle(result_img, (x, y), 8, (0, 0, 255), -1)
        # 添加标签
        cv2.putText(result_img, corner_names[i], 
                   (x + 10, y + 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    # 保存结果
    cv2.imwrite('improved_corners_detected.jpg', result_img)
    print("✓ 角点检测图像已保存为: improved_corners_detected.jpg")

if __name__ == "__main__":
    test_improved_paper_detection()