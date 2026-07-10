#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v28 — 投票融合 + 边缘引导局部反差补全
======================================
在 v28 管线基础上，将 base 的 bitwise_or 替换为 4路径投票融合：
  - >=2票 = 高置信度，直接保留
  - 1票 = 只在主块附近补充
  - 0票 = 丢弃

管线: 投票融合 → edge_guided_fill → 阴影减 → 闭运算 → 主块过滤 → 填洞 → 平滑

对比图: 原图 / v26(原始bitwise_or) / v28(投票融合)
"""
import os, sys, time
import numpy as np
import cv2

ROOT = r"C:\Users\tlyth\WorkBuddy\2026-07-07-14-40-46"
METHOD_NEW = os.path.join(ROOT, "compare", "method_new")
sys.path.insert(0, ROOT)
sys.path.insert(0, METHOD_NEW)

from robust_paper_detector import detect_paper_corners_robust
from contour_v19 import (
    warp_paper, path_division_otsu, path_color_saturation, path_lab_color_gradient,
)
from contour_v26 import (
    paper_lab_stats, shadow_mask, fill_holes, smooth_contour, draw_ov, mkcol,
    v26_extract,
)
from contour_v27 import path_canny_bridge_mc

TEST_IMAGES = [
    ("t1-钳子",      os.path.join(ROOT, "compare", "0.jpg")),
    # t2 像素太差，排除
    ("t3-卡尺",      os.path.join(ROOT, "compare", "0_2.jpg")),
    ("t4-小卡尺",    os.path.join(ROOT, "compare", "0_3.jpg")),
    ("t5-六角扳手",  os.path.join(ROOT, "compare", "0_4.jpg")),
    ("t6-测温枪",    os.path.join(ROOT, "compare", "0_1.jpg")),
    ("t7-红钳",      os.path.join(ROOT, "compare", "0_5.jpg")),
]


# ============================================================
#  边缘引导的局部反差补全 (替代 Hough + 全局膨胀)
# ============================================================
def edge_guided_fill(warped, base_mask):
    """
    只补 base_mask 内部：局部反差 + Canny 引导，只允许在已有 mask 内部生长。
    外侧一概要不到，防止阴影边缘/纸纹被当成物体边缘补进来。
    """
    h, w = warped.shape[:2]
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)

    # 1. 局部背景估计 (大核高斯 = 纸张局部均值)
    local_bg = cv2.GaussianBlur(gray, (51, 51), 0)

    # 2. 和局部背景的差异
    diff = cv2.absdiff(gray, local_bg)
    diff = cv2.normalize(diff, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

    # 3. Canny 边缘带做引导
    edges = cv2.Canny(gray, 30, 90)
    edges = cv2.dilate(edges, np.ones((5, 5), np.uint8), 1)

    # 4. 差异 + 边缘带
    _, diff_bin = cv2.threshold(diff, 12, 255, cv2.THRESH_BINARY)
    guided = cv2.bitwise_and(diff_bin, edges)

    # 5. ★ 只保留 base_mask 内部的 — 外侧一概不补
    guided = cv2.bitwise_and(guided, base_mask)

    # 6. 连通性过滤 (去噪声碎片)
    cnts, _ = cv2.findContours(guided, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    guided_clean = np.zeros_like(guided)
    for c in cnts:
        if cv2.contourArea(c) >= 50:
            cv2.drawContours(guided_clean, [c], -1, 255, cv2.FILLED)
    guided = guided_clean

    # 7. 小膨胀连碎片
    guided = cv2.dilate(guided, np.ones((3, 3), np.uint8), 1)

    return guided


# ============================================================
#  v28 主提取
# ============================================================
def v28_extract(warped, dbg=False):
    h, w = warped.shape[:2]; ia = h * w

    # --- 1. 基础并集 (恢复原始 v28 的 bitwise_or) ---
    mc, _ = path_lab_color_gradient(warped)
    ma = path_division_otsu(warped)
    me = path_canny_bridge_mc(warped)
    ms_sat = path_color_saturation(warped)

    base = cv2.bitwise_or(cv2.bitwise_or(mc, ma), me)

    # --- 2. 边缘引导的局部反差补全 ---

    # --- 2. 边缘引导的局部反差补全 ---
    guided = edge_guided_fill(warped, base)
    base = cv2.bitwise_or(base, guided)

    # --- 3. 减阴影 (protect 包含 me) ---
    pL, pa, pb = paper_lab_stats(warped)
    sh = shadow_mask(warped, pL, pa, pb, l_ratio=0.75, ab_tol=18)
    protect = cv2.bitwise_or(cv2.bitwise_or(ms_sat, mc), me)
    protect = cv2.dilate(protect, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)), 1)
    sh_eff = cv2.bitwise_and(sh, cv2.bitwise_not(protect))
    base = cv2.bitwise_and(base, cv2.bitwise_not(sh_eff))

    # --- 4. 去边框噪声 ---
    bm = max(3, int(min(h, w) * 0.02))
    base[:bm, :] = 0; base[-bm:, :] = 0; base[:, :bm] = 0; base[:, -bm:] = 0

    # --- 5. 闭运算 (核 0.018，不需 0.025) ---
    ck = max(7, int(min(h, w) * 0.018)) | 1
    base = cv2.morphologyEx(base, cv2.MORPH_CLOSE,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ck, ck)), 2)
    base = cv2.morphologyEx(base, cv2.MORPH_OPEN,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)), 1)

    # --- 6. 最大连通块 + 近邻合并 (0.08) ---
    cnts, _ = cv2.findContours(base, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return None, {}
    cnts = [c for c in cnts if cv2.contourArea(c) >= ia * 0.005]
    if not cnts:
        return None, {}
    biggest = max(cnts, key=cv2.contourArea)
    bx, by, bw, bh = cv2.boundingRect(biggest)
    ex = int(max(bw, bh) * 0.08)
    keep = np.zeros((h, w), np.uint8)
    for c in cnts:
        x, y, cw, ch = cv2.boundingRect(c)
        if (x >= bx-ex and y >= by-ex and x+cw <= bx+bw+ex and y+ch <= by+bh+ex):
            cv2.drawContours(keep, [c], -1, 255, cv2.FILLED)
    if cv2.countNonZero(keep) == 0:
        cv2.drawContours(keep, [biggest], -1, 255, cv2.FILLED)

    # --- 7. 填洞 + 再闭 ---
    keep = fill_holes(keep)
    keep = cv2.morphologyEx(keep, cv2.MORPH_CLOSE,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ck, ck)), 1)
    keep = fill_holes(keep)

    # --- 8. GrabCut 精修边界 ---
    keep_gc = keep.copy()  # 保存粗mask用于调试
    try:
        gc_mask = np.where(keep == 255, cv2.GC_PR_FGD, cv2.GC_PR_BGD).astype('uint8')
        # 外扩一圈做可能背景，给GrabCut学习纸的颜色
        dilated_keep = cv2.dilate(keep, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)), 1)
        gc_mask[(dilated_keep > 0) & (keep == 0)] = cv2.GC_PR_BGD
        bgdModel, fgdModel = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
        cv2.grabCut(warped, gc_mask, None, bgdModel, fgdModel, 3, cv2.GC_INIT_WITH_MASK)
        keep = np.where((gc_mask == cv2.GC_FGD) | (gc_mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    except cv2.error:
        pass  # GrabCut 失败就保持原样

    # --- 9. 最终轮廓 ---
    cnts2, _ = cv2.findContours(keep, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts2:
        return None, {}
    final_cnt = max(cnts2, key=cv2.contourArea)

    # --- 9. 凸包修直边 (条件放宽: >0.85 + >2.5) ---
    used_hull = False
    hull = cv2.convexHull(final_cnt)
    a_cnt = cv2.contourArea(final_cnt)
    a_hull = cv2.contourArea(hull)
    area_ratio = a_cnt / a_hull if a_hull > 0 else 0
    rect = cv2.boundingRect(final_cnt)
    aspect = max(rect[2], rect[3]) / (min(rect[2], rect[3]) + 1e-5)
    if area_ratio > 0.85 and aspect > 2.5:
        final_cnt = hull
        used_hull = True

    # --- 11. 平滑 ---
    final_cnt = smooth_contour(final_cnt, sigma=2.0)

    if dbg:
        print(f"    [凸包] area_ratio={area_ratio:.3f} aspect={aspect:.2f} "
              f"used_hull={used_hull}")
    info = {
        'base': base, 'keep': keep, 'shadow_eff': sh_eff,
        'me': me, 'guided': guided, 'keep_gc': keep_gc,
    } if dbg else {}
    return final_cnt, info


def main():
    print("=" * 60)
    print("v28 — 原始并集 + edge_guided_fill + GrabCut精修")
    print("=" * 60)
    CW = 300; rows = []; drows = []; tA = time.time()

    for idx, (name, path) in enumerate(TEST_IMAGES):
        img = cv2.imread(path)
        if img is None:
            print(f"[{idx+1}] {name}: 读图失败"); continue
        t0 = time.time()
        corners, _ = detect_paper_corners_robust(img)
        warped = warp_paper(img, corners)

        c26, _ = v26_extract(warped, dbg=False)
        print(f"[{idx+1}/6] {name}")
        c28, dbg = v28_extract(warped, dbg=True)
        p26 = len(c26) if c26 is not None else 0
        p28 = len(c28) if c28 is not None else 0
        ar28 = (cv2.contourArea(c28) / (warped.shape[0]*warped.shape[1])) if c28 is not None else 0
        print(f"    v26={p26}pts | v28={p28}pts ar={ar28:.3f} | {time.time()-t0:.2f}s")

        r26 = draw_ov(warped, c26, (255, 140, 0), 2)
        r28 = draw_ov(warped, c28, (0, 0, 255), 2)

        def ch(i): return int(i.shape[0] * (CW / max(i.shape[1], 1))) + 30
        mh_row = max(ch(img), ch(warped), ch(r26), ch(r28))
        rows.append(np.hstack([
            mkcol(img, CW, f"{name}", mh_row),
            mkcol(r26, CW, f"v26({p26})", mh_row),
            mkcol(r28, CW, f"v28({p28})", mh_row),
        ]))

        # 调试用的 vote_viz 不再需要
        DW = 195
        def dh(i): return int(i.shape[0] * (DW / max(i.shape[1], 1))) + 25
        dbs = [(warped, "拉正"), (dbg.get('me', warped), "多通道Canny"),
               (dbg.get('guided', warped), "局部反差补全"),
               (dbg.get('shadow_eff', warped), "切掉的阴影"),
               (dbg.get('base', warped), "并集-减阴影"),
               (dbg.get('keep_gc', warped), "GrabCut前"),
               (dbg.get('keep', warped), "GrabCut后"),
               (r28, "v28结果")]
        mdh = max(dh(im) for im, _ in dbs)
        drows.append(np.hstack([mkcol(im, DW, t, mdh) for im, t in dbs]))

    if rows:
        op = os.path.join(ROOT, "compare", "contour_v28.png")
        cv2.imwrite(op, np.vstack(rows)); print(f"\n主图: {op}")
    if drows:
        dp = os.path.join(ROOT, "compare", "contour_v28_debug.png")
        cv2.imwrite(dp, np.vstack(drows)); print(f"调试: {dp}")
    print(f"总耗时 {time.time()-tA:.1f}s")


if __name__ == "__main__":
    main()
