#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
直接使用参考包中的成熟方案进行测试
这样就不需要每次都写前端网页了，直接用Python测试
"""

import cv2
import numpy as np
import sys
import os

# 添加参考包路径
sys.path.insert(0, 'reference/tool_contour/pkg_tool_contour_detection')
sys.path.insert(0, 'reference/contour_simplify/pkg_contour_simplify_primitives')

# 导入参考包中的模块
from repro_contour_v9 import extract_tool_contour_v9, detect_paper_battery

def paper_detect_and_warp(image_path):
    """纸张检测和透视校正"""
    print("开始纸张检测和透视校正...")
    
    # 读取图像
    img = cv2.imread(image_path)
    if img is None:
        print(f"无法读取图像: {image_path}")
        return None
    
    # 检测纸张角点
    corners = detect_paper_battery(img)
    if corners is None:
        print("未检测到纸张")
        return None
    
    print(f"检测到纸张角点: {corners.tolist()}")
    
    # 透视校正
    img_w, img_h = img.shape[1], img.shape[0]
    pw, ph = (int(img_h*0.707), img_h) if img_h > img_w else (img_w, int(img_w*0.707))
    dst = np.array([[0,0],[pw,0],[pw,ph],[0,ph]], np.float32)
    M = cv2.getPerspectiveTransform(corners.astype(np.float32), dst)
    warped = cv2.warpPerspective(img, M, (pw, ph))
    
    print(f"透视校正完成: {warped.shape[1]}x{warped.shape[0]}")
    return warped

def extract_tool_contour_reference(warped_image):
    """使用参考包方案提取工具轮廓"""
    print("使用参考包方案提取工具轮廓...")
    
    # 使用参考包的v9方案提取轮廓
    union, debug_info, raw_contour, smooth_contour = extract_tool_contour_v9(
        warped_image, 
        dilate_px=7, 
        smooth=True,
        sigma=4.0, 
        median_ksize=5,
        use_lab=True, 
        use_blackhat=True, 
        use_canny=True,
        debug=True
    )
    
    if smooth_contour is None:
        print("未能提取到工具轮廓")
        return None, None
    
    print(f"成功提取轮廓: {len(smooth_contour)} 个点")
    return smooth_contour, union

def simplify_contour_to_primitives(contour):
    """
    简化的轮廓基元化函数（基于参考包的思路）
    """
    print("将轮廓转换为几何基元...")
    
    if contour is None or len(contour) < 3:
        return []
    
    # 重塑点
    pts = contour.reshape(-1, 2).astype(np.float64)
    
    # 使用Douglas-Peucker算法简化轮廓
    peri = cv2.arcLength(contour, closed=True)
    epsilon = 0.004 * peri
    simplified = cv2.approxPolyDP(contour, epsilon, closed=True)
    vertices = simplified.reshape(-1, 2).astype(np.float64)
    
    print(f"简化后顶点数: {len(vertices)}")
    
    # 转换为点列表
    points = [{"x": float(pt[0]), "y": float(pt[1])} for pt in pts]
    
    # 返回作为一条折线
    return [{
        "type": "polyline",
        "points": points
    }]

def visualize_results(warped_image, contour, primitives, output_dir="test_results/reference_test"):
    """可视化结果"""
    print("生成可视化结果...")
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. 原始校正图像
    cv2.imwrite(os.path.join(output_dir, "warped_image.jpg"), warped_image)
    
    # 2. 轮廓图像
    contour_img = warped_image.copy()
    if contour is not None:
        cv2.drawContours(contour_img, [contour], -1, (0, 255, 0), 2)
    cv2.imwrite(os.path.join(output_dir, "tool_contour.jpg"), contour_img)
    
    # 3. 基元图像
    primitives_img = warped_image.copy()
    for primitive in primitives:
        if primitive["type"] == "line":
            p0 = (int(primitive["p0"]["x"]), int(primitive["p0"]["y"]))
            p1 = (int(primitive["p1"]["x"]), int(primitive["p1"]["y"]))
            cv2.line(primitives_img, p0, p1, (0, 0, 255), 2)
        elif primitive["type"] == "arc":
            center = (int(primitive["center"]["x"]), int(primitive["center"]["y"]))
            radius = int(primitive["radius"])
            cv2.circle(primitives_img, center, radius, (255, 0, 0), 2)
        elif primitive["type"] == "polyline":
            points = [(int(p["x"]), int(p["y"])) for p in primitive["points"]]
            for i in range(len(points) - 1):
                cv2.line(primitives_img, points[i], points[i+1], (0, 255, 255), 1)
    
    cv2.imwrite(os.path.join(output_dir, "primitives.jpg"), primitives_img)
    
    print(f"可视化结果已保存到: {output_dir}")

def print_primitives_info(primitives):
    """打印基元信息"""
    print("\n=== 基元详细信息 ===")
    line_count = 0
    arc_count = 0
    polyline_count = 0
    
    for i, primitive in enumerate(primitives):
        if primitive["type"] == "line":
            line_count += 1
            p0 = primitive["p0"]
            p1 = primitive["p1"]
            length = ((p1["x"] - p0["x"])**2 + (p1["y"] - p0["y"])**2)**0.5
            print(f"直线 {line_count}: ({p0['x']:.1f}, {p0['y']:.1f}) → ({p1['x']:.1f}, {p1['y']:.1f}) 长度: {length:.1f}")
        elif primitive["type"] == "arc":
            arc_count += 1
            center = primitive["center"]
            radius = primitive["radius"]
            print(f"圆弧 {arc_count}: 中心({center['x']:.1f}, {center['y']:.1f}) 半径: {radius:.1f}")
        elif primitive["type"] == "polyline":
            polyline_count += 1
            points = primitive["points"]
            print(f"折线 {polyline_count}: {len(points)} 个点")
    
    print(f"\n总计: 直线{line_count}个, 圆弧{arc_count}个, 折线{polyline_count}个")

def main():
    """主函数"""
    print("🔧 使用参考包成熟方案进行工具轮廓检测测试")
    print("=" * 50)
    
    # 输入图像路径
    image_path = "test_results/original/testpic.jpg"
    
    # 1. 纸张检测和透视校正
    warped_image = paper_detect_and_warp(image_path)
    if warped_image is None:
        return
    
    # 2. 工具轮廓提取
    contour, union_mask = extract_tool_contour_reference(warped_image)
    if contour is None:
        return
    
    # 3. 轮廓基元化
    primitives = simplify_contour_to_primitives(contour)
    
    # 4. 可视化结果
    visualize_results(warped_image, contour, primitives)
    
    # 5. 打印详细信息
    print_primitives_info(primitives)
    
    print("\n✅ 测试完成！所有结果已保存到 test_results/reference_test/")

if __name__ == "__main__":
    main()