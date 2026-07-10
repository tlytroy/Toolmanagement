#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
优化黄色工具（如钳子）的检测效果
专门针对参考包中的 repro_contour_v9.py 进行调整
"""

import cv2
import numpy as np
import sys
import os

# 添加参考包路径
sys.path.insert(0, 'reference/tool_contour/pkg_tool_contour_detection')

# 导入参考包模块
from repro_contour_v9 import (
    detect_paper_battery, 
    tophat_deshedow,
    mask_scheme_a,
    strategy_lab_dark,
    strategy_blackhat_corrected,
    strategy_canny_bridge,
    remove_shadow_adaptive,
    fill_internal_holes,
    median_filter_points,
    smooth_closed_spline
)

def extract_enhanced_tool_contour(warped_image):
    """
    增强版工具轮廓提取，特别优化黄色工具检测
    """
    print("🔧 增强版工具轮廓提取（优化黄色工具检测）")
    
    h, w = warped_image.shape[:2]
    bgr = warped_image if len(warped_image.shape) == 3 else cv2.cvtColor(warped_image, cv2.COLOR_GRAY2BGR)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY) if len(warped_image.shape) == 3 else warped_image.copy()
    
    print(f"图像尺寸: {w}x{h}")
    
    # ======== 策略1: 方案A (Top-Hat + adaptive + otsu) ========
    print("1. 应用方案A (Top-Hat + adaptive + otsu)...")
    deshedow, tophat = tophat_deshedow(gray, kernel_size=31)
    m_a = mask_scheme_a(deshedow, block=31, C=8)
    print(f"   方案A提取像素数: {int(np.count_nonzero(m_a))}")
    
    # ======== 策略2: LAB暗区捕获 (绝招1修正) ========
    print("2. 应用LAB暗区捕获...")
    m_lab, lab_otsu, lab_thr = strategy_lab_dark(bgr, l_threshold_ratio=0.55)
    print(f"   LAB暗区提取像素数: {int(np.count_nonzero(m_lab))}")
    
    # ======== 策略3: BlackHat去阴影 (绝招2) ========
    print("3. 应用BlackHat去阴影...")
    m_bh, blackhat_img, corrected_gray = strategy_blackhat_corrected(gray, kernel_size=21)
    print(f"   BlackHat提取像素数: {int(np.count_nonzero(m_bh))}")
    
    # ======== 策略4: Canny桥接 (绝招3轻量) ========
    print("4. 应用Canny桥接...")
    m_canny = strategy_canny_bridge(gray, low_thresh=40, high_thresh=120)
    print(f"   Canny桥接提取像素数: {int(np.count_nonzero(m_canny))}")
    
    # ======== 新增: HSV黄色检测 ========
    print("5. 应用HSV黄色检测...")
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    # 黄色范围 (可以根据需要调整)
    yellow_lower = np.array([15, 60, 60])
    yellow_upper = np.array([35, 255, 255])
    m_yellow = cv2.inRange(hsv, yellow_lower, yellow_upper)
    
    # 对黄色掩膜进行形态学操作
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    m_yellow = cv2.morphologyEx(m_yellow, cv2.MORPH_CLOSE, kernel)
    m_yellow = cv2.morphologyEx(m_yellow, cv2.MORPH_OPEN, kernel)
    print(f"   HSV黄色检测像素数: {int(np.count_nonzero(m_yellow))}")
    
    # ======== 五策略并集 ========
    print("6. 合并所有策略...")
    union = m_a.copy()
    union = cv2.bitwise_or(union, m_lab)
    union = cv2.bitwise_or(union, m_bh)
    union = cv2.bitwise_or(union, m_canny)
    union = cv2.bitwise_or(union, m_yellow)  # 添加黄色检测
    
    total_px = int(np.count_nonzero(union))
    print(f"   并集总像素数: {total_px} ({total_px/union.size:.2%})")
    
    # ======== 轻量开运算去噪 ========
    print("7. 去噪处理...")
    open_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    union = cv2.morphologyEx(union, cv2.MORPH_OPEN, open_k)
    
    # ======== 阴影去除 ========
    print("8. 阴影去除...")
    union, n_removed = remove_shadow_adaptive(gray, union, debug=True)
    
    # ======== 填充孔洞 ========
    print("9. 填充内部孔洞...")
    union = fill_internal_holes(union)
    
    # ======== 安全检查 ========
    total_px = int(np.count_nonzero(union))
    if total_px > union.size * 0.85:
        print("   ⚠️ 并集过大，回退到方案A")
        union = m_a
        union = fill_internal_holes(union)
    
    # ======== 提取最大连通块 ========
    print("10. 提取最大连通块...")
    cnts_all, _ = cv2.findContours(union, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts_all:
        print("   ✗ 未找到轮廓")
        return None, None, union
    
    best_cnt = max(cnts_all, key=cv2.contourArea)
    print(f"   最佳轮廓面积: {cv2.contourArea(best_cnt):.0f}")
    
    # ======== 膨胀余量 ========
    print("11. 应用膨胀余量...")
    tool_mask = np.zeros_like(union)
    cv2.drawContours(tool_mask, [best_cnt], -1, 255, -1)
    kd = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7*2+1, 7*2+1))
    tool_mask = cv2.dilate(tool_mask, kd, iterations=1)
    
    final_cnts, _ = cv2.findContours(tool_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not final_cnts:
        print("   ✗ 膨胀后未找到轮廓")
        return None, None, union
    
    raw_contour = max(final_cnts, key=cv2.contourArea)
    
    # ======== 平滑处理 ========
    print("12. 平滑轮廓...")
    pts = raw_contour.reshape(-1, 2).astype(np.float64)
    pts = median_filter_points(pts, ksize=5)
    smooth_cnt = smooth_closed_spline(pts, sigma=4.0, debug=True)
    
    print(f"   ✓ 最终轮廓点数: {len(smooth_cnt)}")
    return union, raw_contour, smooth_cnt

def visualize_enhanced_results(warped_image, union_mask, raw_contour, smooth_contour, output_dir="test_results/enhanced_test"):
    """可视化增强版检测结果"""
    print("13. 生成可视化结果...")
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. 原始校正图像
    cv2.imwrite(os.path.join(output_dir, "warped_image.jpg"), warped_image)
    
    # 2. 并集掩膜
    union_vis = np.zeros_like(warped_image)
    if len(warped_image.shape) == 2:
        union_vis = cv2.cvtColor(warped_image, cv2.COLOR_GRAY2BGR)
    else:
        union_vis = warped_image.copy()
    
    if union_mask is not None:
        overlay = union_vis.copy()
        overlay[union_mask > 0] = [0, 255, 0]  # 绿色掩膜
        union_vis = cv2.addWeighted(union_vis, 0.7, overlay, 0.3, 0)
    cv2.imwrite(os.path.join(output_dir, "union_mask.jpg"), union_vis)
    
    # 3. 轮廓对比
    contour_vis = warped_image.copy()
    if raw_contour is not None:
        cv2.drawContours(contour_vis, [raw_contour], -1, (0, 0, 255), 2)  # 红色原始轮廓
    if smooth_contour is not None:
        cv2.drawContours(contour_vis, [smooth_contour], -1, (0, 255, 0), 2)  # 绿色平滑轮廓
    cv2.imwrite(os.path.join(output_dir, "enhanced_contours.jpg"), contour_vis)
    
    print(f"   可视化结果已保存到: {output_dir}")

def main():
    """主函数"""
    print("🎨 优化黄色工具检测测试")
    print("=" * 50)
    
    # 输入图像路径
    image_path = "test_results/original/testpic.jpg"
    
    # 读取图像
    img = cv2.imread(image_path)
    if img is None:
        print(f"❌ 无法读取图像: {image_path}")
        return
    
    print(f"处理图像: {image_path}")
    
    # 纸张检测和透视校正
    print("1. 纸张检测和透视校正...")
    corners = detect_paper_battery(img)
    if corners is None:
        print("❌ 未检测到纸张")
        return
    
    print(f"检测到纸张角点: {corners.tolist()}")
    
    # 透视校正
    img_w, img_h = img.shape[1], img.shape[0]
    pw, ph = (int(img_h*0.707), img_h) if img_h > img_w else (img_w, int(img_w*0.707))
    dst = np.array([[0,0],[pw,0],[pw,ph],[0,ph]], np.float32)
    M = cv2.getPerspectiveTransform(corners.astype(np.float32), dst)
    warped = cv2.warpPerspective(img, M, (pw, ph))
    
    print(f"透视校正完成: {warped.shape[1]}x{warped.shape[0]}")
    
    # 增强版轮廓提取
    union_mask, raw_contour, smooth_contour = extract_enhanced_tool_contour(warped)
    
    # 可视化结果
    visualize_enhanced_results(warped, union_mask, raw_contour, smooth_contour)
    
    # 与原版对比
    print("\n📊 与原版对比:")
    sys.path.insert(0, 'reference/tool_contour/pkg_tool_contour_detection')
    from repro_contour_v9 import extract_tool_contour_v9
    
    print("原版算法:")
    _, _, _, original_smooth = extract_tool_contour_v9(warped, debug=True)
    original_points = len(original_smooth) if original_smooth is not None else 0
    print(f"   轮廓点数: {original_points}")
    
    enhanced_points = len(smooth_contour) if smooth_contour is not None else 0
    print(f"增强版算法:")
    print(f"   轮廓点数: {enhanced_points}")
    
    if enhanced_points > original_points:
        improvement = (enhanced_points - original_points) / original_points * 100
        print(f"   改进: 增加了 {improvement:.1f}% 的细节")
    elif enhanced_points < original_points:
        reduction = (original_points - enhanced_points) / original_points * 100
        print(f"   变化: 减少了 {reduction:.1f}% 的冗余点")
    else:
        print("   结果: 点数相同")
    
    print("\n✅ 增强版测试完成!")

if __name__ == "__main__":
    main()