#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
比较不同纸张检测算法的性能和效果
"""

import cv2
import numpy as np
import time
import sys
import os

# 添加参考包路径
sys.path.insert(0, 'reference/tool_contour/pkg_tool_contour_detection')

# 导入不同算法
from repro_contour_v9 import detect_paper_battery
from improved_paper_detector import detect_paper_corners_precise

def test_algorithm_speed_and_accuracy(image_path):
    """测试不同算法的速度和准确性"""
    print("🔍 比较纸张检测算法性能")
    print("=" * 50)
    
    # 读取图像
    img = cv2.imread(image_path)
    if img is None:
        print(f"无法读取图像: {image_path}")
        return
    
    print(f"测试图像: {image_path}")
    print(f"图像尺寸: {img.shape[1]}x{img.shape[0]}")
    print()
    
    # 测试参考包算法 (detect_paper_battery)
    print("1. 测试参考包算法 (detect_paper_battery)...")
    start_time = time.time()
    corners_ref = detect_paper_battery(img)
    ref_time = time.time() - start_time
    
    if corners_ref is not None:
        print(f"   ✓ 检测成功! 耗时: {ref_time:.3f}秒")
        print(f"   角点坐标: {corners_ref.tolist()}")
    else:
        print("   ✗ 检测失败")
    print()
    
    # 测试改进算法 (detect_paper_corners_precise)
    print("2. 测试改进算法 (detect_paper_corners_precise)...")
    start_time = time.time()
    corners_improved = detect_paper_corners_precise(img)
    improved_time = time.time() - start_time
    
    if corners_improved is not None:
        print(f"   ✓ 检测成功! 耗时: {improved_time:.3f}秒")
        print(f"   角点坐标: {corners_improved}")
    else:
        print("   ✗ 检测失败")
    print()
    
    # 性能比较
    print("📊 性能比较:")
    if corners_ref is not None and corners_improved is not None:
        print(f"   参考包算法: {ref_time:.3f}秒")
        print(f"   改进算法:   {improved_time:.3f}秒")
        if ref_time < improved_time:
            print(f"   结论: 参考包算法快 {improved_time/ref_time:.1f}倍")
        else:
            print(f"   结论: 改进算法快 {ref_time/improved_time:.1f}倍")
    elif corners_ref is not None:
        print("   结论: 只有参考包算法成功")
    elif corners_improved is not None:
        print("   结论: 只有改进算法成功")
    else:
        print("   结论: 两种算法都失败")
    
    return corners_ref, corners_improved

def visualize_comparison(image_path, corners_ref, corners_improved):
    """可视化比较结果"""
    img = cv2.imread(image_path)
    if img is None:
        return
    
    h, w = img.shape[:2]
    
    # 创建比较图像
    comparison_img = img.copy()
    
    # 绘制参考包算法结果（蓝色）
    if corners_ref is not None:
        points_ref = np.array(corners_ref, dtype=np.int32)
        cv2.polylines(comparison_img, [points_ref], True, (255, 0, 0), 3)
        for i, (x, y) in enumerate(corners_ref):
            cv2.circle(comparison_img, (int(x), int(y)), 8, (255, 0, 0), -1)
            cv2.putText(comparison_img, f'R{i}', (int(x)+10, int(y)+10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
    
    # 绘制改进算法结果（绿色）
    if corners_improved is not None:
        points_improved = np.array([(int(x), int(y)) for x, y in corners_improved], dtype=np.int32)
        cv2.polylines(comparison_img, [points_improved], True, (0, 255, 0), 3)
        for i, (x, y) in enumerate(corners_improved):
            cv2.circle(comparison_img, (int(x), int(y)), 8, (0, 255, 0), -1)
            cv2.putText(comparison_img, f'I{i}', (int(x)+10, int(y)-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    
    # 保存比较结果
    output_path = "test_results/algorithm_comparison.jpg"
    cv2.imwrite(output_path, comparison_img)
    print(f"   比较结果已保存到: {output_path}")

def test_contour_extraction_with_both_papers(image_path, corners_ref, corners_improved):
    """使用两种纸张检测结果提取轮廓进行比较"""
    print("\n🔧 测试轮廓提取效果...")
    print("=" * 50)
    
    img = cv2.imread(image_path)
    if img is None:
        return
    
    # 添加参考包路径
    sys.path.insert(0, 'reference/tool_contour/pkg_tool_contour_detection')
    from repro_contour_v9 import extract_tool_contour_v9
    
    results = {}
    
    # 使用参考包纸张检测结果
    if corners_ref is not None:
        print("1. 使用参考包纸张检测结果提取轮廓...")
        try:
            img_w, img_h = img.shape[1], img.shape[0]
            pw, ph = (int(img_h*0.707), img_h) if img_h > img_w else (img_w, int(img_w*0.707))
            dst = np.array([[0,0],[pw,0],[pw,ph],[0,ph]], np.float32)
            M = cv2.getPerspectiveTransform(corners_ref.astype(np.float32), dst)
            warped_ref = cv2.warpPerspective(img, M, (pw, ph))
            
            # 保存校正图像
            cv2.imwrite("test_results/warped_ref.jpg", warped_ref)
            
            # 提取轮廓
            union, debug_info, raw_contour, smooth_contour = extract_tool_contour_v9(
                warped_ref, debug=True
            )
            
            if smooth_contour is not None:
                print(f"   ✓ 成功提取轮廓: {len(smooth_contour)} 个点")
                results['ref'] = {
                    'warped': warped_ref,
                    'contour': smooth_contour,
                    'points': len(smooth_contour)
                }
                
                # 保存轮廓图像
                contour_img = warped_ref.copy()
                cv2.drawContours(contour_img, [smooth_contour], -1, (0, 255, 0), 2)
                cv2.imwrite("test_results/contour_ref.jpg", contour_img)
            else:
                print("   ✗ 未能提取轮廓")
        except Exception as e:
            print(f"   ✗ 提取失败: {e}")
    
    # 使用改进纸张检测结果
    if corners_improved is not None:
        print("2. 使用改进纸张检测结果提取轮廓...")
        try:
            # 转换角点格式
            corners_np = np.array([(x, y) for x, y in corners_improved], dtype=np.float32)
            
            img_w, img_h = img.shape[1], img.shape[0]
            pw, ph = (int(img_h*0.707), img_h) if img_h > img_w else (img_w, int(img_w*0.707))
            dst = np.array([[0,0],[pw,0],[pw,ph],[0,ph]], np.float32)
            M = cv2.getPerspectiveTransform(corners_np, dst)
            warped_improved = cv2.warpPerspective(img, M, (pw, ph))
            
            # 保存校正图像
            cv2.imwrite("test_results/warped_improved.jpg", warped_improved)
            
            # 提取轮廓
            union, debug_info, raw_contour, smooth_contour = extract_tool_contour_v9(
                warped_improved, debug=True
            )
            
            if smooth_contour is not None:
                print(f"   ✓ 成功提取轮廓: {len(smooth_contour)} 个点")
                results['improved'] = {
                    'warped': warped_improved,
                    'contour': smooth_contour,
                    'points': len(smooth_contour)
                }
                
                # 保存轮廓图像
                contour_img = warped_improved.copy()
                cv2.drawContours(contour_img, [smooth_contour], -1, (0, 255, 0), 2)
                cv2.imwrite("test_results/contour_improved.jpg", contour_img)
            else:
                print("   ✗ 未能提取轮廓")
        except Exception as e:
            print(f"   ✗ 提取失败: {e}")
    
    # 比较结果
    print("\n📊 轮廓提取比较:")
    if 'ref' in results and 'improved' in results:
        ref_points = results['ref']['points']
        improved_points = results['improved']['points']
        print(f"   参考包方法: {ref_points} 个点")
        print(f"   改进方法:   {improved_points} 个点")
        if ref_points > improved_points:
            print(f"   结论: 参考包方法提取更多细节 ({ref_points/improved_points:.1f}倍)")
        else:
            print(f"   结论: 改进方法提取更多细节 ({improved_points/ref_points:.1f}倍)")
    elif 'ref' in results:
        print("   结论: 只有参考包方法成功提取轮廓")
    elif 'improved' in results:
        print("   结论: 只有改进方法成功提取轮廓")
    else:
        print("   结论: 两种方法都未能提取轮廓")

def main():
    """主函数"""
    image_path = "test_results/original/testpic.jpg"
    
    # 测试纸张检测算法
    corners_ref, corners_improved = test_algorithm_speed_and_accuracy(image_path)
    
    # 可视化比较
    visualize_comparison(image_path, corners_ref, corners_improved)
    
    # 测试轮廓提取
    test_contour_extraction_with_both_papers(image_path, corners_ref, corners_improved)
    
    print("\n✅ 比较完成!")

if __name__ == "__main__":
    main()