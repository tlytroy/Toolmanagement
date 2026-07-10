#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v26 — 回归"简单稳健" · 只填不啃
===================================================
用户目视反馈(v25)的病根统一诊断:
  - T1 线画到工具里 = 开运算/收缩把轮廓往里啃
  - T3 下边该平的凹进去 / T5 / 测温枪头凹 / T6 顶凹 / T7 左边凹
      = mask 在直边/端头处没填满(金属反光或均匀区无梯度) → 取外轮廓塌进去
  - T4 圈了阴影
  - T2 越缩越怪 = 对错误形状做均匀侵蚀

v26 设计原则: 【只填不啃】
  1. 检测 = 强线索并集(LAB色勾配 C + 除法Otsu A + Canny桥),全跑原图,不白平衡
  2. 只在【纯纸面】减阴影(L低+ab中性),碰到工具(高饱和/强色勾配)就保护,绝不啃工具
  3. 取最大连通块(+近邻小块合并)
  4. 填实所有内部孔洞(治直边凹陷) + 适度闭运算桥接小缺口
  5. 取最大外轮廓, 【不做开运算/侵蚀】
  6. 轻度平滑

对比图只放三列: 原始图 / A4拉正图 / 最终结果(拉正图+红轮廓)
不再放"原版"、不再算 IoU。
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
#  Canny 桥接路 (补充直边/金属边)
# ============================================================
def path_canny_bridge(warped):
    h, w = warped.shape[:2]
    gray = cv2.GaussianBlur(cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY), (3, 3), 0)
    edges = cv2.Canny(gray, 30, 90)
    # 膨胀连断裂
    dk = max(3, int(min(h, w) * 0.006)) | 1
    edges = cv2.dilate(edges, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dk, dk)), 2)
    # 闭合成区域
    ck = max(5, int(min(h, w) * 0.02)) | 1
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE,
                              cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ck, ck)), 2)
    # 填充有效轮廓
    cnts, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    fil = np.zeros((h, w), np.uint8)
    ma = h * w * 0.008
    for c in cnts:
        if cv2.contourArea(c) >= ma:
            cv2.drawContours(fil, [c], -1, 255, cv2.FILLED)
    return fil


# ============================================================
#  纸张 Lab 统计
# ============================================================
def paper_lab_stats(warped):
    h, w = warped.shape[:2]
    m = max(15, int(min(h, w) * 0.04))
    lab = cv2.cvtColor(warped, cv2.COLOR_BGR2LAB)
    s = [lab[0:m, 0:m], lab[0:m, w-m:w], lab[h-m:h, 0:m], lab[h-m:h, w-m:w]]
    px = np.vstack([x.reshape(-1, 3) for x in s]).astype(np.float32)
    return float(np.median(px[:, 0])), float(np.median(px[:, 1])), float(np.median(px[:, 2]))


# ============================================================
#  阴影 mask (L低 + ab中性接近纸)
# ============================================================
def shadow_mask(warped, pL, pa, pb, l_ratio=0.80, ab_tol=13):
    lab = cv2.cvtColor(warped, cv2.COLOR_BGR2LAB)
    L, A, B = cv2.split(lab)
    Lf, Af, Bf = L.astype(np.float32), A.astype(np.float32), B.astype(np.float32)
    sh = (Lf < pL * l_ratio) & (np.abs(Af - pa) < ab_tol) & (np.abs(Bf - pb) < ab_tol)
    return sh.astype(np.uint8) * 255


# ============================================================
#  填实内部孔洞 (flood fill 反转法) — 治直边凹陷的关键
# ============================================================
def fill_holes(mask):
    h, w = mask.shape[:2]
    ff = mask.copy()
    m2 = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(ff, m2, (0, 0), 255)   # 从外部灌满背景
    holes = cv2.bitwise_not(ff)          # 反转 = 内部孔洞
    return cv2.bitwise_or(mask, holes)


# ============================================================
#  v26 主提取 — 只填不啃
# ============================================================
def v26_extract(warped, dbg=False):
    h, w = warped.shape[:2]; ia = h * w

    # --- 1. 强线索并集 (全跑原图) ---
    mc, _ = path_lab_color_gradient(warped)   # 形状好, 抗阴影
    ma = path_division_otsu(warped)           # 填实均匀/直边内部
    me = path_canny_bridge(warped)            # 补金属直边
    ms_sat = path_color_saturation(warped)    # 彩色件保护用

    base = cv2.bitwise_or(cv2.bitwise_or(mc, ma), me)

    # --- 2. 只在纯纸面减阴影, 保护工具 ---
    pL, pa, pb = paper_lab_stats(warped)
    sh = shadow_mask(warped, pL, pa, pb)
    # 保护区 = 高饱和(彩色工具) ∪ 强色勾配(C) → 这些绝不当阴影切
    protect = cv2.bitwise_or(ms_sat, mc)
    protect = cv2.dilate(protect, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)), 1)
    sh_eff = cv2.bitwise_and(sh, cv2.bitwise_not(protect))
    base = cv2.bitwise_and(base, cv2.bitwise_not(sh_eff))

    # --- 3. 去边框噪声 (纸边 2%) ---
    bm = max(3, int(min(h, w) * 0.02))
    base[:bm, :] = 0; base[-bm:, :] = 0; base[:, :bm] = 0; base[:, -bm:] = 0

    # --- 4. 适度闭运算桥接缺口 (桥接小缺口, 不吞真凹) ---
    ck = max(5, int(min(h, w) * 0.012)) | 1
    base = cv2.morphologyEx(base, cv2.MORPH_CLOSE,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ck, ck)), 2)
    # 轻开运算只去掉孤立细噪(核很小,不啃主体)
    base = cv2.morphologyEx(base, cv2.MORPH_OPEN,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)), 1)

    # --- 5. 取最大连通块 + 合并近邻块 ---
    cnts, _ = cv2.findContours(base, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return None, {}
    cnts = [c for c in cnts if cv2.contourArea(c) >= ia * 0.005]
    if not cnts:
        return None, {}
    biggest = max(cnts, key=cv2.contourArea)
    bx, by, bw, bh = cv2.boundingRect(biggest)
    # 主块 bounding box 扩 8% 内的其它块一并纳入(手柄断开等)
    ex = int(max(bw, bh) * 0.08)
    keep = np.zeros((h, w), np.uint8)
    for c in cnts:
        x, y, cw, ch = cv2.boundingRect(c)
        if (x >= bx-ex and y >= by-ex and x+cw <= bx+bw+ex and y+ch <= by+bh+ex):
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
        return None, {}
    final_cnt = max(cnts2, key=cv2.contourArea)

    # --- 8. 轻度平滑 (高斯环形平滑, 不改整体形状) ---
    final_cnt = smooth_contour(final_cnt, sigma=2.0)

    info = {'base': base, 'keep': keep, 'shadow_eff': sh_eff} if dbg else {}
    return final_cnt, info


# ============================================================
#  环形高斯平滑
# ============================================================
def smooth_contour(cnt, sigma=2.0):
    pts = cnt.reshape(-1, 2).astype(np.float32)
    n = len(pts)
    if n < 7:
        return cnt
    k = max(3, int(sigma * 3) | 1)
    g = cv2.getGaussianKernel(k, sigma).flatten()
    xp = np.concatenate([pts[-(k//2):, 0], pts[:, 0], pts[:k//2, 0]])
    yp = np.concatenate([pts[-(k//2):, 1], pts[:, 1], pts[:k//2, 1]])
    xs = np.convolve(xp, g, mode='same')[k//2:k//2+n]
    ys = np.convolve(yp, g, mode='same')[k//2:k//2+n]
    out = np.stack([xs, ys], axis=1).astype(np.int32)
    return out.reshape(-1, 1, 2)


# ============================================================
#  绘制工具
# ============================================================
def draw_ov(img, cnt, col=(0, 0, 255), th=2):
    r = img.copy()
    if cnt is not None and len(cnt) > 0:
        cv2.drawContours(r, [cnt.reshape(-1, 1, 2) if cnt.ndim == 2 else cnt], -1, col, th)
    return r


def mkcol(img, cw, title="", th=None):
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    ih, iw = img.shape[:2]; sc = cw / max(iw, 1)
    rz = cv2.resize(img, (cw, int(ih * sc)), interpolation=cv2.INTER_AREA)
    bar = np.zeros((30, cw, 3), np.uint8)
    cv2.putText(bar, title, (5, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (210, 210, 210), 1)
    col = np.vstack([bar, rz])
    if th and col.shape[0] < th:
        col = np.vstack([col, np.zeros((th - col.shape[0], cw, 3), np.uint8)])
    return col


def main():
    print("=" * 60)
    print("v26 — 只填不啃 · 三列输出(原图/拉正/结果)")
    print("=" * 60)
    CW = 360; rows = []; drows = []; tA = time.time()

    for idx, (name, path) in enumerate(TEST_IMAGES):
        img = cv2.imread(path)
        if img is None:
            print(f"[{idx+1}] {name}: 读图失败 {path}"); continue
        t0 = time.time()
        corners, _ = detect_paper_corners_robust(img)
        warped = warp_paper(img, corners)
        cnt, dbg = v26_extract(warped, dbg=True)
        npts = len(cnt) if cnt is not None else 0
        ar = (cv2.contourArea(cnt) / (warped.shape[0]*warped.shape[1])) if cnt is not None else 0
        print(f"[{idx+1}/7] {name}: pts={npts} ar={ar:.3f} | {time.time()-t0:.2f}s")

        res = draw_ov(warped, cnt, (0, 0, 255), 2)

        def ch(i): return int(i.shape[0] * (CW / max(i.shape[1], 1))) + 30
        mh = max(ch(img), ch(warped), ch(res))
        rows.append(np.hstack([
            mkcol(img, CW, f"{name} 原图", mh),
            mkcol(warped, CW, "A4 拉正", mh),
            mkcol(res, CW, f"结果 ({npts}pts)", mh),
        ]))

        # 调试列(内部看,不给用户看原版): base / keep
        DW = 240
        def dh(i): return int(i.shape[0] * (DW / max(i.shape[1], 1))) + 25
        dbs = [(warped, "拉正"), (dbg.get('base', warped), "并集-减阴影"),
               (dbg.get('shadow_eff', warped), "切掉的阴影"),
               (dbg.get('keep', warped), "填洞后"), (res, "结果")]
        mdh = max(dh(im) for im, _ in dbs)
        drows.append(np.hstack([mkcol(im, DW, t, mdh) for im, t in dbs]))

    if rows:
        op = os.path.join(ROOT, "compare", "contour_v26.png")
        cv2.imwrite(op, np.vstack(rows)); print(f"\n主图: {op}")
    if drows:
        dp = os.path.join(ROOT, "compare", "contour_v26_debug.png")
        cv2.imwrite(dp, np.vstack(drows)); print(f"调试: {dp}")
    print(f"总耗时 {time.time()-tA:.1f}s")


if __name__ == "__main__":
    main()
