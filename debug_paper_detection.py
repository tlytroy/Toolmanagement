#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import cv2
import numpy as np
import matplotlib.pyplot as plt
from typing import List, Tuple

def debug_paper_detection(image_path: str):
    """
    调试图像纸张检测算法
    """
    # 读取图像
    image = cv2.imread(image_path)
    if image is None:
        print(f"无法读取图像: {image_path}")
        return
    
    print(f"原始图像尺寸: {image.shape}")
    
    # 转换为RGB用于显示
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    # 1. 转换为灰度图
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    print("1. 转换为灰度图完成")
    
    # 2. 高斯模糊
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    print("2. 高斯模糊完成")
    
    # 3. 边缘检测
    edges = cv2.Canny(blurred, 50, 150)
    print("3. 边缘检测完成")
    
    # 4. 形态学操作增强边缘
    kernel = np.ones((3,3), np.uint8)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    print("4. 形态学操作完成")
    
    # 5. 查找轮廓
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    print(f"5. 找到 {len(contours)} 个轮廓")
    
    # 6. 按面积排序，找到最大的轮廓
    contours_sorted = sorted(contours, key=cv2.contourArea, reverse=True)
    
    # 7. 寻找四边形轮廓
    paper_contour = None
    for contour in contours_sorted[:10]:  # 检查前10个最大轮廓
        area = cv2.contourArea(contour)
        if area < 1000:  # 忽略太小的轮廓
            continue
            
        # 近似轮廓
        epsilon = 0.02 * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)
        
        print(f"轮廓点数: {len(approx)}, 面积: {area}")
        
        # 如果是四边形
        if len(approx) == 4:
            paper_contour = approx
            print("找到四边形轮廓!")
            break
    
    # 创建调试图像
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    fig.suptitle('纸张检测调试过程', fontsize=16)
    
    # 原始图像
    axes[0, 0].imshow(image_rgb)
    axes[0, 0].set_title('原始图像')
    axes[0, 0].axis('off')
    
    # 灰度图
    axes[0, 1].imshow(gray, cmap='gray')
    axes[0, 1].set_title('灰度图')
    axes[0, 1].axis('off')
    
    # 边缘检测
    axes[0, 2].imshow(edges, cmap='gray')
    axes[0, 2].set_title('边缘检测')
    axes[0, 2].axis('off')
    
    # 所有轮廓
    contour_img = image_rgb.copy()
    cv2.drawContours(contour_img, contours, -1, (255, 0, 0), 2)
    axes[1, 0].imshow(contour_img)
    axes[1, 0].set_title('所有轮廓')
    axes[1, 0].axis('off')
    
    # 最大轮廓
    largest_contour_img = image_rgb.copy()
    if contours_sorted:
        cv2.drawContours(largest_contour_img, [contours_sorted[0]], -1, (0, 255, 0), 2)
        axes[1, 1].imshow(largest_contour_img)
        axes[1, 1].set_title('最大轮廓')
        axes[1, 1].axis('off')
    
    # 四边形检测结果
    result_img = image_rgb.copy()
    if paper_contour is not None:
        cv2.drawContours(result_img, [paper_contour], -1, (255, 0, 0), 3)
        # 标记角点
        for i, point in enumerate(paper_contour.reshape(4, 2)):
            x, y = int(point[0]), int(point[1])
            cv2.circle(result_img, (x, y), 8, (0, 0, 255), -1)
            cv2.putText(result_img, str(i+1), (x+10, y+10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        axes[1, 2].imshow(result_img)
        axes[1, 2].set_title('检测到的纸张四角')
        print(f"检测到的角点坐标:")
        for i, point in enumerate(paper_contour.reshape(4, 2)):
            print(f"  角点{i+1}: ({point[0]}, {point[1]})")
    else:
        axes[1, 2].imshow(image_rgb)
        axes[1, 2].set_title('未检测到四边形')
        print("未检测到四边形轮廓")
    
    axes[1, 2].axis('off')
    
    plt.tight_layout()
    plt.savefig('paper_detection_debug.png', dpi=150, bbox_inches='tight')
    print("调试图像已保存为: paper_detection_debug.png")
    plt.show()

def improved_paper_detection(image_path: str):
    """
    改进的纸张检测算法
    """
    # 读取图像
    image = cv2.imread(image_path)
    if image is None:
        print(f"无法读取图像: {image_path}")
        return None
    
    # 转换为灰度图
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # 多种方法尝试检测
    methods = [
        # 方法1: Canny边缘检测
        lambda img: cv2.Canny(cv2.GaussianBlur(img, (5, 5), 0), 50, 150),
        # 方法2: 自适应阈值
        lambda img: cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2),
        # 方法3: Otsu阈值
        lambda img: cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    ]
    
    best_contour = None
    best_area = 0
    
    for i, method in enumerate(methods):
        try:
            # 应用预处理方法
            processed = method(gray)
            
            # 形态学操作
            kernel = np.ones((3,3), np.uint8)
            processed = cv2.morphologyEx(processed, cv2.MORPH_CLOSE, kernel)
            
            # 查找轮廓
            contours, _ = cv2.findContours(processed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # 寻找最佳四边形
            for contour in contours:
                area = cv2.contourArea(contour)
                if area < 1000:  # 忽略太小的轮廓
                    continue
                
                # 多边形近似
                epsilon = 0.02 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                
                # 检查是否为四边形
                if len(approx) == 4:
                    # 检查是否为凸四边形
                    if cv2.isContourConvex(approx):
                        if area > best_area:
                            best_area = area
                            best_contour = approx
                            
        except Exception as e:
            print(f"方法 {i+1} 失败: {e}")
            continue
    
    return best_contour

if __name__ == "__main__":
    print("开始调试纸张检测算法...")
    
    # 运行详细调试
    debug_paper_detection('testpic.jpg')
    
    # 运行改进算法
    print("\n运行改进的纸张检测算法...")
    contour = improved_paper_detection('testpic.jpg')
    
    if contour is not None:
        print("改进算法检测到四边形!")
        print("角点坐标:")
        for i, point in enumerate(contour.reshape(4, 2)):
            print(f"  角点{i+1}: ({point[0]}, {point[1]})")
    else:
        print("改进算法未能检测到四边形")