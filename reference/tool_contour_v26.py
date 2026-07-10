#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具轮廓提取算法 v26 — 自包含版
================================
"只填不啃"管线：多路径并集 → 阴影保护减法 → 最大连通块 → 填洞 → 平滑

场景假设：白纸背景 + 单工具 + 俯拍

用法:
    from tool_contour_v26 import extract_tool_contour
    contour, warped_img = extract_tool_contour("photo.jpg")

    # 或者命令行
    python tool_contour_v26.py photo.jpg [output.png]

依赖: numpy, opencv-python (cv2)。无需 torch / GPU。

算法流程:
    1. detect_paper_corners_robust  → 找 A4 纸四角
    2. warp_paper                   → 透视校正为 A4 比例 (1.414:1)
    3. v26_extract                  → 多路径并集 + 阴影保护 + 填洞 + 平滑

v26 设计原则（"只填不啃"）:
    检测 = LAB色梯度(C) ∪ 除法Otsu(A) ∪ Canny桥, 全跑原图
    只在纯纸面减阴影(L低+ab中性), 碰到工具(高饱和/强色梯度)就保护
    取最大连通块(+近邻小块合并)
    填实所有内部孔洞 + 适度闭运算桥接小缺口
    取最大外轮廓, 不做开运算/侵蚀
    轻度环形高斯平滑
"""

import sys
import numpy as np
import cv2


# ============================================================
#  第一部分：纸张检测 + 透视校正
#  (来源: robust_paper_detector.py, 纯 OpenCV)
# ============================================================

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


def _quad_from_contour(cnt, eps_ratios=(0.02, 0.03, 0.04, 0.05)):
    """从轮廓近似四边形（尝试多级精度）"""
    for ep in eps_ratios:
        ap = cv2.approxPolyDP(cnt, ep * cv2.arcLength(cnt, True), True)
        if len(ap) == 4 and cv2.isContourConvex(ap):
            return _order_tl_tr_br_bl(ap.reshape(4, 2))
    return None


def _score_quad(corners, gray, img_shape):
    """四边形打分：宽高比(A4≈1.414) ×0.4 + 直角偏离 ×0.3 + 亮度覆盖 ×0.3"""
    pts = np.array(corners, dtype=np.float64)
    d01 = np.linalg.norm(pts[0] - pts[1])
    d12 = np.linalg.norm(pts[1] - pts[2])
    d23 = np.linalg.norm(pts[2] - pts[3])
    d30 = np.linalg.norm(pts[3] - pts[0])
    wq = (d01 + d23) / 2
    hq = (d12 + d30) / 2
    aspect = max(wq, hq) / max(1, min(wq, hq))
    aspect_score = float(np.exp(-((aspect - 1.414) / 0.35) ** 2))

    # 直角偏离
    angs = []
    p = pts
    for i in range(4):
        a = p[i]; b = p[(i + 1) % 4]; c = p[(i + 2) % 4]
        v1 = a - b; v2 = c - b
        m1 = np.hypot(v1[0], v1[1]); m2 = np.hypot(v2[0], v2[1])
        if m1 < 1 or m2 < 1:
            return 0.0, {}
        cos = np.clip((v1[0] * v2[0] + v1[1] * v2[1]) / (m1 * m2), -1, 1)
        angs.append(abs(np.degrees(np.arccos(cos)) - 90))
    ang_dev = max(angs)
    angle_score = 0.0 if ang_dev > 12 else (1 - ang_dev / 12)

    # 亮度覆盖
    h, w = img_shape[:2]
    mask = np.zeros((h, w), np.uint8)
    cv2.fillPoly(mask, [pts.astype(np.int32)], 255)
    bright_cov = float(cv2.mean(gray, mask=mask)[0]) / 255.0 if mask.sum() > 0 else 0.0
    bscore = float(np.clip((bright_cov - 0.35) / 0.45, 0, 1))

    total = aspect_score * 0.4 + angle_score * 0.3 + bscore * 0.3
    if aspect_score < 0.15 or angle_score == 0:
        total = 0.0
    return total, {}


def _largest_quad(mask, gray, img_shape, min_frac=0.08, max_frac=0.95):
    """在二值 mask 中找最大有效四边形"""
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return None
    best = None; best_s = -1
    for cnt in sorted(cnts, key=cv2.contourArea, reverse=True)[:6]:
        a = cv2.contourArea(cnt)
        af = a / (img_shape[0] * img_shape[1])
        if af < min_frac or af > max_frac:
            continue
        q = _quad_from_contour(cnt)
        if q is None:
            continue
        s, _ = _score_quad(q, gray, img_shape)
        if s > best_s:
            best_s = s; best = q
    return best, best_s


def detect_paper_corners_robust(img):
    """鲁棒 A4 纸张四角检测：亮度先验 + 边缘兜底 + 三重打分

    Returns:
        corners: np.float32 (4,2), 顺序 [TL, TR, BR, BL], 用于透视校正
        candidates: list[(corners, score, method)], 已按 score 降序
    """
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g5 = cv2.GaussianBlur(gray, (5, 5), 0)
    cands = []

    # 亮度先验（纸是图里最亮的白色大区域）
    otsu = cv2.threshold(g5, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    for m in [otsu, cv2.bitwise_not(otsu)]:
        r = _largest_quad(m, gray, (h, w))
        if r[0] is not None:
            cands.append((r[0], r[1], "bright-otsu"))

    for bs in [15, 31]:
        ad = cv2.adaptiveThreshold(
            g5, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, bs, 4)
        for m in [ad, cv2.bitwise_not(ad)]:
            r = _largest_quad(m, gray, (h, w))
            if r[0] is not None:
                cands.append((r[0], r[1], "bright-adapt"))

    # 边缘先验（兜底：杂物多 / 纸反光时）
    for lo, hi, ks in [(30, 110, 3), (60, 160, 5)]:
        ed = cv2.Canny(g5, lo, hi)
        ed = cv2.dilate(ed, cv2.getStructuringElement(cv2.MORPH_RECT, (ks, ks)))
        r = _largest_quad(ed, gray, (h, w))
        if r[0] is not None:
            cands.append((r[0], r[1], "edge-canny"))

    if not cands:
        return None
    cands.sort(key=lambda x: x[1], reverse=True)
    best = cands[0]
    return best[0], cands


def warp_paper(img, corners):
    pts = np.array(corners, dtype=np.float32).reshape(4, 2)
    d01 = np.linalg.norm(pts[0] - pts[1]); d12 = np.linalg.norm(pts[1] - pts[2])
    d23 = np.linalg.norm(pts[2] - pts[3]); d30 = np.linalg.norm(pts[3] - pts[0])
    we = (d01 + d23) / 2; he = (d12 + d30) / 2; r = 2 ** 0.5
    if we >= he:
        pw, ph = max(100, int(we)), max(100, int(we / r))
    else:
        ph, pw = max(100, int(he)), max(100, int(he / r))
    dst = np.array([[0, 0], [pw, 0], [pw, ph], [0, ph]], np.float32)
    return cv2.warpPerspective(img, cv2.getPerspectiveTransform(pts, dst), (pw, ph))


# ============================================================
#  第二部分：工具检测路径
#  (来源: contour_v19 + contour_v26, 纯 OpenCV)
# ============================================================

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


# ============================================================
#  第三部分：阴影检测与去除
# ============================================================

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


# ============================================================
#  第四部分：后处理（填洞 + 平滑）
# ============================================================

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


# ============================================================
#  第五部分：v26 主提取管线
# ============================================================

def v26_extract(warped):
    """
    v26 "只填不啃" 主管线。

    输入: warped — 经 warp_paper 透视校正的 BGR 图
    返回: contour — (N,1,2) int32 轮廓点集，或 None
    """
    h, w = warped.shape[:2]
    ia = h * w

    # --- 1. 强线索并集 (全跑原图) ---
    mc = path_lab_color_gradient(warped)     # C: LAB 色梯度，形状好，抗阴影
    ma = path_division_otsu(warped)           # A: 除法 Otsu，填实均匀直边内部
    me = path_canny_bridge(warped)            # E: Canny 桥接，补金属直边
    ms_sat = path_color_saturation(warped)    # B: HSV 高饱和，彩色件保护用

    base = cv2.bitwise_or(cv2.bitwise_or(mc, ma), me)

    # --- 2. 只在纯纸面减阴影，保护工具 ---
    pL, pa, pb = paper_lab_stats(warped)
    sh = shadow_mask(warped, pL, pa, pb)
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


# ============================================================
#  第六部分：顶层 API
# ============================================================

def extract_tool_contour(image):
    """
    完整管线：原始照片 → 工具轮廓

    参数:
        image : str (文件路径) 或 np.ndarray (BGR 图, H×W×3)

    返回:
        contour : np.ndarray (N,1,2) int32 — 工具轮廓点集，失败返回 None
        warped  : np.ndarray — 透视校正后的 BGR 图，失败返回 None
    """
    if isinstance(image, str):
        img = cv2.imread(image)
        if img is None:
            raise FileNotFoundError(f"无法读取图片: {image}")
    else:
        img = image

    # 1. 检测纸张
    result = detect_paper_corners_robust(img)
    if result is None:
        return None, None
    corners, _ = result

    # 2. 透视校正
    warped = warp_paper(img, corners)

    # 3. 提取轮廓
    contour = v26_extract(warped)

    return contour, warped


# ============================================================
#  CLI
# ============================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python tool_contour_v26.py <图片路径> [输出路径]")
        print("示例: python tool_contour_v26.py photo.jpg result.png")
        sys.exit(1)

    img_path = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else "contour_result.png"

    print(f"[v26] 处理: {img_path}")
    contour, warped = extract_tool_contour(img_path)

    if contour is None:
        print("[v26] 失败：未检测到纸张或工具")
        sys.exit(1)

    npts = len(contour)
    area = cv2.contourArea(contour)
    ar = area / (warped.shape[0] * warped.shape[1])
    print(f"[v26] 成功: {npts} 个轮廓点, 面积比={ar:.3f}")

    # 画结果图
    result = warped.copy()
    cv2.drawContours(result, [contour], -1, (0, 0, 255), 2)
    cv2.imwrite(out_path, result)
    print(f"[v26] 已保存: {out_path}")
