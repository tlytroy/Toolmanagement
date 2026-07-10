#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v27 — 多通道 Canny 补浅色直边 (在 v26"只填不啃"基础上)
========================================================
用户诊断(对 v26):
  单通道灰度 Canny 对"浅色边缘"(黄手柄/银卡尺/浅灰)是盲的——
  这些颜色在灰度下和白纸亮度接近, 梯度极小, Canny 漏掉,
  外边界缺失 → 填洞补不了(填洞只补内部黑洞) → 直边凹陷。

v27 唯一核心改动(先只改这一条, 验证效果):
  ★ path_canny_bridge 改成【多通道 Canny】:
     1. 灰度 Canny (常规边缘)
     2. RGB 分通道 Canny (黄色在 B/R 反差强, 银色在 G/B 反差)
     3. Lab a/b 通道 Canny (颜色边缘, 亮度接近纸也能抓到)
     并集后膨胀连断裂 + 闭合 + 填充
  ★ 闭运算核 0.012 → 0.018 (桥接更宽的浅色边缘缺口, 低风险)

其余"只填不啃"管线与 v26 完全一致。
对比图: 原图 / A4拉正 / v26结果 / v27结果  (放前一版对比, 看多通道补了啥)
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
# 复用 v26 的辅助函数(保持一致, 只改 canny 和 kernel)
from contour_v26 import (
    paper_lab_stats, shadow_mask, fill_holes, smooth_contour, draw_ov, mkcol,
    v26_extract,
)

TEST_IMAGES = [
    ("t1-钳子",      os.path.join(ROOT, "compare", "0.jpg")),
    ("t2-尖嘴钳",    os.path.join(ROOT, "compare", "PixPin.png")),
    ("t3-卡尺",      os.path.join(ROOT, "compare", "0_2.jpg")),
    ("t4-小卡尺",    os.path.join(ROOT, "compare", "0_3.jpg")),
    ("t5-六角扳手",  os.path.join(ROOT, "compare", "0_4.jpg")),
    ("t6-测温枪",    os.path.join(ROOT, "compare", "0_1.jpg")),
    ("t7-红钳",      os.path.join(ROOT, "compare", "0_5.jpg")),
]


# ============================================================
#  ★ 多通道 Canny 桥接路 (v27 核心改动)
#     灰度盲区(浅色) → RGB/Lab 分通道补
# ============================================================
def path_canny_bridge_mc(warped):
    h, w = warped.shape[:2]
    edges = np.zeros((h, w), np.uint8)

    # 1. 灰度 Canny (常规边缘)
    gray = cv2.GaussianBlur(cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY), (3, 3), 0)
    edges = cv2.bitwise_or(edges, cv2.Canny(gray, 30, 90))

    # 2. RGB 分通道 Canny (黄色在 B/R 有强反差, 银色在 G/B 有反差)
    for i in range(3):
        ch = cv2.GaussianBlur(warped[:, :, i], (3, 3), 0)
        edges = cv2.bitwise_or(edges, cv2.Canny(ch, 40, 100))

    # 3. Lab a/b 通道 Canny (颜色边缘, 亮度接近纸也能抓)
    lab = cv2.cvtColor(warped, cv2.COLOR_BGR2LAB)
    for i in (1, 2):
        ch = cv2.GaussianBlur(lab[:, :, i], (3, 3), 0)
        edges = cv2.bitwise_or(edges, cv2.Canny(ch, 25, 70))

    # 4. 膨胀连断裂 (核稍大, 专治浅色边缘碎片化)
    dk = max(5, int(min(h, w) * 0.008)) | 1
    edges = cv2.dilate(edges, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dk, dk)), 2)

    # 5. 闭合成区域
    ck = max(7, int(min(h, w) * 0.02)) | 1
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE,
                              cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ck, ck)), 2)

    # 6. 填充有效轮廓
    cnts, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    fil = np.zeros((h, w), np.uint8)
    ma = h * w * 0.008
    for c in cnts:
        if cv2.contourArea(c) >= ma:
            cv2.drawContours(fil, [c], -1, 255, cv2.FILLED)
    return fil


# ============================================================
#  v27 主提取 — 与 v26 同管线, 仅换多通道 Canny + 闭运算核 0.018
# ============================================================
def v27_extract(warped, dbg=False):
    h, w = warped.shape[:2]; ia = h * w

    # --- 1. 强线索并集 (全跑原图) — Canny 换成多通道 ---
    mc, _ = path_lab_color_gradient(warped)
    ma = path_division_otsu(warped)
    me = path_canny_bridge_mc(warped)          # ★ 多通道
    ms_sat = path_color_saturation(warped)

    base = cv2.bitwise_or(cv2.bitwise_or(mc, ma), me)

    # --- 2. 只在纯纸面减阴影, 保护工具 (与 v26 一致) ---
    pL, pa, pb = paper_lab_stats(warped)
    sh = shadow_mask(warped, pL, pa, pb)
    protect = cv2.bitwise_or(ms_sat, mc)
    protect = cv2.dilate(protect, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)), 1)
    sh_eff = cv2.bitwise_and(sh, cv2.bitwise_not(protect))
    base = cv2.bitwise_and(base, cv2.bitwise_not(sh_eff))

    # --- 3. 去边框噪声 ---
    bm = max(3, int(min(h, w) * 0.02))
    base[:bm, :] = 0; base[-bm:, :] = 0; base[:, :bm] = 0; base[:, -bm:] = 0

    # --- 4. 闭运算 (核 0.012 → 0.018, 桥接更宽缺口) ---
    ck = max(7, int(min(h, w) * 0.018)) | 1     # ★ 加大
    base = cv2.morphologyEx(base, cv2.MORPH_CLOSE,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ck, ck)), 2)
    base = cv2.morphologyEx(base, cv2.MORPH_OPEN,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)), 1)

    # --- 5. 最大连通块 + 近邻块合并 ---
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

    # --- 6. 填洞 + 再闭 ---
    keep = fill_holes(keep)
    keep = cv2.morphologyEx(keep, cv2.MORPH_CLOSE,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ck, ck)), 1)
    keep = fill_holes(keep)

    # --- 7. 最终外轮廓 (不侵蚀) ---
    cnts2, _ = cv2.findContours(keep, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts2:
        return None, {}
    final_cnt = max(cnts2, key=cv2.contourArea)

    # --- 8. 轻度平滑 ---
    final_cnt = smooth_contour(final_cnt, sigma=2.0)

    info = {'base': base, 'keep': keep, 'shadow_eff': sh_eff, 'me': me} if dbg else {}
    return final_cnt, info


def main():
    print("=" * 60)
    print("v27 — 多通道 Canny 补浅色直边 (对比 v26)")
    print("=" * 60)
    CW = 300; rows = []; drows = []; tA = time.time()

    for idx, (name, path) in enumerate(TEST_IMAGES):
        img = cv2.imread(path)
        if img is None:
            print(f"[{idx+1}] {name}: 读图失败 {path}"); continue
        t0 = time.time()
        corners, _ = detect_paper_corners_robust(img)
        warped = warp_paper(img, corners)

        c26, _ = v26_extract(warped, dbg=False)
        c27, dbg = v27_extract(warped, dbg=True)
        p26 = len(c26) if c26 is not None else 0
        p27 = len(c27) if c27 is not None else 0
        ar27 = (cv2.contourArea(c27) / (warped.shape[0]*warped.shape[1])) if c27 is not None else 0
        print(f"[{idx+1}/7] {name}: v26={p26}pts | v27={p27}pts ar={ar27:.3f} | {time.time()-t0:.2f}s")

        r26 = draw_ov(warped, c26, (255, 140, 0), 2)   # v26 橙
        r27 = draw_ov(warped, c27, (0, 0, 255), 2)     # v27 红

        def ch(i): return int(i.shape[0] * (CW / max(i.shape[1], 1))) + 30
        mh = max(ch(img), ch(warped), ch(r26), ch(r27))
        rows.append(np.hstack([
            mkcol(img, CW, f"{name} 原图", mh),
            mkcol(warped, CW, "A4 拉正", mh),
            mkcol(r26, CW, f"v26 ({p26})", mh),
            mkcol(r27, CW, f"v27 ({p27})", mh),
        ]))

        DW = 220
        def dh(i): return int(i.shape[0] * (DW / max(i.shape[1], 1))) + 25
        dbs = [(warped, "拉正"), (dbg.get('me', warped), "多通道Canny填充"),
               (dbg.get('base', warped), "并集-减阴影"),
               (dbg.get('keep', warped), "填洞后"), (r27, "v27结果")]
        mdh = max(dh(im) for im, _ in dbs)
        drows.append(np.hstack([mkcol(im, DW, t, mdh) for im, t in dbs]))

    if rows:
        op = os.path.join(ROOT, "compare", "contour_v27.png")
        cv2.imwrite(op, np.vstack(rows)); print(f"\n主图: {op}")
    if drows:
        dp = os.path.join(ROOT, "compare", "contour_v27_debug.png")
        cv2.imwrite(dp, np.vstack(drows)); print(f"调试: {dp}")
    print(f"总耗时 {time.time()-tA:.1f}s")


if __name__ == "__main__":
    main()
