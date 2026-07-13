#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
新版工具轮廓处理模块
基于tool_contour_v26.py的"只填不啃"管线，但作为独立实现
"""

import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional, Any
import sys
import os

def _order_tl_tr_br_bl(pts):
    """四点排序：左上、右上、右下、左下"""
    pts = np.array(pts, dtype=np.float64).reshape(-1, 2)
    s = pts.sum(1)
    d = np.diff(pts, axis=1).reshape(-1)
    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]
    tr = pts[np.argmin(d)]
    bl = pts[np.argmax(d)]
    return np.array([tl, tr, br, bl], dtype=np.float32)

def paper_lab_stats(warped):
    """采样四角区域的纸色统计（中位数，抗阴影/污渍异常）"""
    h, w = warped.shape[:2]
    m = max(15, int(min(h, w) * 0.04))
    lab = cv2.cvtColor(warped, cv2.COLOR_BGR2LAB)
    s = [lab[0:m, 0:m], lab[0:m, w - m:w],
         lab[h - m:h, 0:m], lab[h - m:h, w - m:w]]
    px = np.vstack([x.reshape(-1, 3) for x in s]).astype(np.float32)
    return (float(np.median(px[:, 0])),
            float(np.median(px[:, 1])),
            float(np.median(px[:, 2])))

def shadow_mask(warped, pL, pa, pb, l_ratio=0.80, ab_tol=13):
    """阴影判定：比纸暗(L < pL*l_ratio) + ab 近纸(|a-pa|<ab_tol) → 是阴影"""
    lab = cv2.cvtColor(warped, cv2.COLOR_BGR2LAB)
    L, A, B = cv2.split(lab)
    Lf, Af, Bf = L.astype(np.float32), A.astype(np.float32), B.astype(np.float32)
    sh = (Lf < pL * l_ratio) & (np.abs(Af - pa) < ab_tol) & (np.abs(Bf - pb) < ab_tol)
    return sh.astype(np.uint8) * 255

def fill_holes(mask):
    """flood fill 反转法填实内部孔洞 — 治直边凹陷的关键"""
    h, w = mask.shape[:2]
    ff = mask.copy()
    m2 = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(ff, m2, (0, 0), 255)   # 从外部灌满背景
    holes = cv2.bitwise_not(ff)           # 反转 = 内部孔洞
    return cv2.bitwise_or(mask, holes)

def smooth_contour(cnt, sigma=2.0):
    """环形高斯平滑：不改整体形状，只去锯齿"""
    pts = cnt.reshape(-1, 2).astype(np.float32)
    n = len(pts)
    if n < 7:
        return cnt
    k = max(3, int(sigma * 3) | 1)
    g = cv2.getGaussianKernel(k, sigma).flatten()
    xp = np.concatenate([pts[-(k // 2):, 0], pts[:, 0], pts[:k // 2, 0]])
    yp = np.concatenate([pts[-(k // 2):, 1], pts[:, 1], pts[:k // 2, 1]])
    xs = np.convolve(xp, g, mode='same')[k // 2:k // 2 + n]
    ys = np.convolve(yp, g, mode='same')[k // 2:k // 2 + n]
    out = np.stack([xs, ys], axis=1).astype(np.int32)
    return out.reshape(-1, 1, 2)

def path_division_otsu(warped):
    """路径 A — 除法归一化 + Otsu：抓均匀暗区/亮区（黑色/银色工具内部）"""
    h, w = warped.shape[:2]
    gray = cv2.GaussianBlur(cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY), (3, 3), 0)
    k = max(21, int(max(h, w) * 0.15) | 1)
    bg = cv2.morphologyEx(gray, cv2.MORPH_CLOSE,
                          cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    corr = cv2.divide(gray.astype(np.float32),
                      np.maximum(bg.astype(np.float32), 1.0), scale=255.0)
    corr = np.clip(corr, 0, 255).astype(np.uint8)
    _, m = cv2.threshold(corr, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return m

def path_color_saturation(warped):
    """路径 B — HSV 高饱和度：抓红/黄/蓝等彩色手柄"""
    hsv = cv2.cvtColor(warped, cv2.COLOR_BGR2HSV)
    m = cv2.bitwise_and(cv2.inRange(hsv[:, :, 1], 45, 255),
                        cv2.inRange(hsv[:, :, 2], 50, 255))
    return cv2.morphologyEx(m, cv2.MORPH_OPEN,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)), 1)

def path_lab_color_gradient(warped):
    """路径 C — LAB 颜色梯度(Scharr)：形状最完整，抗阴影

    公式：sqrt(grad_L² + 2*grad_a² + 2*grad_b²)
    a/b 通道加权 ×2 因为彩色边界是区分工具和纸的最强信号。
    """
    lab = cv2.cvtColor(warped, cv2.COLOR_BGR2LAB).astype(np.float32)

    def sm(ch):
        gx = cv2.Scharr(ch, cv2.CV_64F, 1, 0)
        gy = cv2.Scharr(ch, cv2.CV_64F, 0, 1)
        return np.sqrt(gx ** 2 + gy ** 2)

    g = np.sqrt(sm(lab[:, :, 0]) ** 2 + 2 * sm(lab[:, :, 1]) ** 2 + 2 * sm(lab[:, :, 2]) ** 2)
    gn = cv2.normalize(g, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    _, eb = cv2.threshold(gn, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    h, w = warped.shape[:2]
    ck = max(5, min(h, w) // 40) | 1
    ec = cv2.morphologyEx(eb, cv2.MORPH_CLOSE,
                          cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ck, ck)), 2)
    dk = max(3, ck // 2) | 1
    ed = cv2.dilate(ec, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dk, dk)), 2)

    cnts, _ = cv2.findContours(ed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    ma = h * w * 0.01
    fil = np.zeros_like(ed)
    vc = [c for c in cnts if cv2.contourArea(c) >= ma]
    if vc:
        if len(vc) <= 10:
            cv2.drawContours(fil, vc, -1, 255, cv2.FILLED)
        else:
            vc.sort(key=cv2.contourArea, reverse=True)
            ta = acc = h * w
            for c in vc:
                cv2.drawContours(fil, [c], -1, 255, cv2.FILLED)
                acc += cv2.contourArea(c)
                if acc > ta * 0.3: break
    return cv2.morphologyEx(fil, cv2.MORPH_OPEN,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)), 1)

def path_canny_bridge(warped):
    """路径 E — Canny 边缘桥接：补充金属直边"""
    h, w = warped.shape[:2]
    gray = cv2.GaussianBlur(cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY), (3, 3), 0)
    edges = cv2.Canny(gray, 30, 90)
    dk = max(3, int(min(h, w) * 0.006)) | 1
    edges = cv2.dilate(edges, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dk, dk)), 2)
    ck = max(5, int(min(h, w) * 0.02)) | 1
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE,
                              cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ck, ck)), 2)
    cnts, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    fil = np.zeros((h, w), np.uint8)
    ma = h * w * 0.008
    for c in cnts:
        if cv2.contourArea(c) >= ma:
            cv2.drawContours(fil, [c], -1, 255, cv2.FILLED)
    return fil

def extract_tool_contours_v26(warped_image: np.ndarray) -> Optional[np.ndarray]:
    """
    提取工具轮廓（新版v26实现）
    使用"只填不啃"管线：多路径并集 → 阴影保护减法 → 最大连通块 → 填洞 → 平滑
    """
    try:
        h, w = warped_image.shape[:2]
        ia = h * w

        # --- 1. 强线索并集 (全跑原图) ---
        mc = path_lab_color_gradient(warped_image)     # C: LAB 色梯度，形状好，抗阴影
        ma = path_division_otsu(warped_image)           # A: 除法 Otsu，填实均匀直边内部
        me = path_canny_bridge(warped_image)            # E: Canny 桥接，补金属直边
        ms_sat = path_color_saturation(warped_image)    # B: HSV 高饱和，彩色件保护用

        base = cv2.bitwise_or(cv2.bitwise_or(mc, ma), me)

        # --- 2. 只在纯纸面减阴影，保护工具 ---
        pL, pa, pb = paper_lab_stats(warped_image)
        sh = shadow_mask(warped_image, pL, pa, pb)
        # 保护区 = 高饱和(彩色工具) ∪ 强色梯度(C) → 这些绝不当阴影切
        protect = cv2.bitwise_or(ms_sat, mc)
        protect = cv2.dilate(protect,
                             cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)), 1)
        sh_eff = cv2.bitwise_and(sh, cv2.bitwise_not(protect))
        base = cv2.bitwise_and(base, cv2.bitwise_not(sh_eff))

        # --- 3. 去边框噪声 (纸边 2%) ---
        bm = max(3, int(min(h, w) * 0.02))
        base[:bm, :] = 0; base[-bm:, :] = 0
        base[:, :bm] = 0; base[:, -bm:] = 0

        # --- 4. 适度闭运算桥接缺口 (桥接小缺口，不吞真凹) ---
        ck = max(5, int(min(h, w) * 0.012)) | 1
        base = cv2.morphologyEx(base, cv2.MORPH_CLOSE,
                                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ck, ck)), 2)
        # 轻开运算只去掉孤立细噪(核很小，不啃主体)
        base = cv2.morphologyEx(base, cv2.MORPH_OPEN,
                                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)), 1)

        # --- 5. 取最大连通块 + 合并近邻块 ---
        cnts, _ = cv2.findContours(base, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if not cnts:
            return None
        cnts = [c for c in cnts if cv2.contourArea(c) >= ia * 0.005]
        if not cnts:
            return None
        biggest = max(cnts, key=cv2.contourArea)
        bx, by, bw, bh = cv2.boundingRect(biggest)
        # 主块 bounding box 扩 8% 内的其它块一并纳入(手柄断开等)
        ex = int(max(bw, bh) * 0.08)
        keep = np.zeros((h, w), np.uint8)
        for c in cnts:
            x, y, cw, ch = cv2.boundingRect(c)
            if (x >= bx - ex and y >= by - ex and
                    x + cw <= bx + bw + ex and y + ch <= by + bh + ex):
                cv2.drawContours(keep, [c], -1, 255, cv2.FILLED)
        if cv2.countNonZero(keep) == 0:
            cv2.drawContours(keep, [biggest], -1, 255, cv2.FILLED)

        # --- 6. 填实内部孔洞 (治直边凹陷) ---
        keep = fill_holes(keep)
        # 再闭一次把填洞后边缘缺口补平
        keep = cv2.morphologyEx(keep, cv2.MORPH_CLOSE,
                                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ck, ck)), 1)
        keep = fill_holes(keep)

        # --- 7. 取最终外轮廓 (不做侵蚀!) ---
        cnts2, _ = cv2.findContours(keep, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if not cnts2:
            return None
        final_cnt = max(cnts2, key=cv2.contourArea)

        # --- 8. 轻度平滑 (环形高斯，不改整体形状) ---
        final_cnt = smooth_contour(final_cnt, sigma=2.0)

        return final_cnt
    except Exception as e:
        print(f"v26工具轮廓提取失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def convert_contour_to_primitives(contour: np.ndarray) -> List[Dict[str, Any]]:
    """
    将轮廓转换为几何基元
    简化版本：将轮廓近似为折线
    """
    try:
        # 不在此处抽稀——初始检测保留全量轮廓点，抽稀由用户手动触发 /simplify-contours
        points = [{"x": float(x), "y": float(y)} for x, y in contour.reshape(-1, 2)]
        
        return [{
            "type": "polyline",
            "points": points
        }]
    except Exception as e:
        print(f"轮廓基元化失败: {e}")
        return []

def test_v26_contour_extraction():
    """测试v26轮廓提取"""
    print("测试v26工具轮廓提取...")
    
    # 读取测试图像
    image_path = "test_results/original/testpic.jpg"
    
    if not os.path.exists(image_path):
        print(f"❌ 找不到测试图像: {image_path}")
        return
    
    try:
        # 使用v26算法提取工具轮廓
        contour, warped = extract_tool_contour_v26(image_path)
        
        if contour is None or warped is None:
            print("❌ v26算法未能检测到工具轮廓或纸张")
            return
        
        print(f"✅ v26算法成功检测到工具轮廓!")
        print(f"   轮廓点数: {len(contour)}")
        
        # 计算轮廓面积
        area = cv2.contourArea(contour)
        area_ratio = area / (warped.shape[0] * warped.shape[1])
        print(f"   轮廓面积: {area:.0f} 像素")
        print(f"   面积占比: {area_ratio:.3f}")
        
        # 保存结果
        result_img = warped.copy()
        cv2.drawContours(result_img, [contour], -1, (0, 0, 255), 2)
        cv2.imwrite('test_results/tool_contours/v26_tool_contour.jpg', result_img)
        cv2.imwrite('test_results/tool_contours/v26_warped.jpg', warped)
        print("✅ v26算法检测结果已保存到: test_results/tool_contours/v26_tool_contour.jpg")
        print("✅ 透视校正结果已保存到: test_results/tool_contours/v26_warped.jpg")
        
        # 转换为基元
        primitives = convert_contour_to_primitives(contour)
        print(f"✅ 转换为 {len(primitives)} 个几何基元")
        
        return contour, primitives
        
    except Exception as e:
        print(f"❌ 测试v26算法时发生错误: {e}")
        import traceback
        traceback.print_exc()
        return None, []

if __name__ == "__main__":
    test_v26_contour_extraction()