"""
robust_paper_detector.py — 鲁棒 A4 纸张四角检测（纯 OpenCV，无 PyTorch）

针对「A4 白纸 + 工具」场景设计。相比传统 Canny/边缘检测法，本模块以
「纸是画面里最亮的白色大区域」这一强先验为主，辅以边缘先验兜底，并用
三重打分（宽高比 ×0.4 + 直角偏离 ×0.3 + 亮度覆盖 ×0.3）从多方案候选中
选最优四边形，避免被桌面纹理 / 周边工具 / 金属反光边缘带跑。

解决了旧法（improved_paper_detector）在六角扳手等图上把纸张检测成正方形
（宽高比 1.00，透视校正全歪）的崩坏问题——新法在该类图上宽高比恢复到 1.41。

依赖: numpy, opencv-python (cv2)。无需 GPU / torch。

接口:
    corners, candidates = detect_paper_corners_robust(img)
        img        : BGR 图 (np.ndarray, shape H×W×3)
        corners    : np.float32 (4,2)，顺序 [TL, TR, BR, BL]，用于透视校正
        candidates : list[(corners, score, method)]，已按 score 降序，供调试

    warped = warp_paper(img, corners, ratio=1.414)
        把检测到的四角透视校正为 ratio(宽/高) 的矩形图，直接喂后续轮廓管线。
"""
import sys
import os
import numpy as np
import cv2


def _order_tl_tr_br_bl(pts):
    pts = np.array(pts, dtype=np.float64).reshape(-1, 2)
    s = pts.sum(1)
    d = np.diff(pts, axis=1).reshape(-1)
    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]
    tr = pts[np.argmin(d)]
    bl = pts[np.argmax(d)]
    return np.array([tl, tr, br, bl], dtype=np.float32)


def _quad_from_contour(cnt, eps_ratios=(0.02, 0.03, 0.04, 0.05)):
    for ep in eps_ratios:
        ap = cv2.approxPolyDP(cnt, ep * cv2.arcLength(cnt, True), True)
        if len(ap) == 4 and cv2.isContourConvex(ap):
            return _order_tl_tr_br_bl(ap.reshape(4, 2))
    return None


def _score_quad(corners, gray, img_shape):
    pts = np.array(corners, dtype=np.float64)
    d01 = np.linalg.norm(pts[0] - pts[1])
    d12 = np.linalg.norm(pts[1] - pts[2])
    d23 = np.linalg.norm(pts[2] - pts[3])
    d30 = np.linalg.norm(pts[3] - pts[0])
    wq = (d01 + d23) / 2
    hq = (d12 + d30) / 2
    aspect = max(wq, hq) / max(1, min(wq, hq))
    aspect_score = float(np.exp(-((aspect - 1.414) / 0.35) ** 2))
    angs = []
    p = pts
    for i in range(4):
        a = p[i]
        b = p[(i + 1) % 4]
        c = p[(i + 2) % 4]
        v1 = a - b
        v2 = c - b
        m1 = np.hypot(v1[0], v1[1])
        m2 = np.hypot(v2[0], v2[1])
        if m1 < 1 or m2 < 1:
            return 0.0, {}
        cos = np.clip((v1[0] * v2[0] + v1[1] * v2[1]) / (m1 * m2), -1, 1)
        angs.append(abs(np.degrees(np.arccos(cos)) - 90))
    ang_dev = max(angs)
    angle_score = 0.0 if ang_dev > 12 else (1 - ang_dev / 12)
    h, w = img_shape[:2]
    mask = np.zeros((h, w), np.uint8)
    cv2.fillPoly(mask, [pts.astype(np.int32)], 255)
    bright_cov = float(cv2.mean(gray, mask=mask)[0]) / 255.0 if mask.sum() > 0 else 0.0
    bscore = float(np.clip((bright_cov - 0.35) / 0.45, 0, 1))
    area = cv2.contourArea(pts.astype(np.int32))
    area_frac = area / (h * w)
    area_score = 1.0 if 0.15 <= area_frac <= 0.85 else 0.3
    total = aspect_score * 0.4 + angle_score * 0.3 + bscore * 0.3
    if aspect_score < 0.15 or angle_score == 0:
        total = 0.0
    return total, dict(
        aspect=round(aspect, 2),
        ang=round(ang_dev, 1),
        bright=round(bright_cov, 2),
        area=round(area_frac, 2),
    )


def _largest_quad(mask, gray, img_shape, min_frac=0.08, max_frac=0.95):
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return None
    best = None
    best_s = -1
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
            best_s = s
            best = q
    return best, best_s


def detect_paper_corners_robust(img):
    """鲁棒 A4 检测: 亮度先验为主 + 多方案候选 + 比例/直角/亮度三重打分。

    返回 (corners, candidates):
      corners    : np.float32 (4,2)，顺序 [TL, TR, BR, BL]，用于 warp
      candidates : list[(corners, score, method)]，已按 score 降序，供调试
    """
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g5 = cv2.GaussianBlur(gray, (5, 5), 0)
    cands = []
    # --- 亮度先验（纸是图里最亮的白色大区域）---
    otsu = cv2.threshold(g5, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    for m in [otsu, cv2.bitwise_not(otsu)]:
        r = _largest_quad(m, gray, (h, w))
        if r[0] is not None:
            cands.append((r[0], r[1], "bright-otsu"))
    for bs in [15, 31]:
        ad = cv2.adaptiveThreshold(
            g5, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, bs, 4
        )
        for m in [ad, cv2.bitwise_not(ad)]:
            r = _largest_quad(m, gray, (h, w))
            if r[0] is not None:
                cands.append((r[0], r[1], "bright-adapt"))
    # --- 边缘先验（兜底：杂物多 / 纸反光时）---
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


def warp_paper(img, corners, ratio=1.414):
    """用检测到的四角做透视校正为 ratio(宽/高) 的矩形图。

    ratio=1.414 即标准 A4。返回 warped BGR 图，可直接喂后续轮廓检测管线。
    """
    pts = np.array(corners, dtype=np.float32).reshape(4, 2)
    d01 = np.linalg.norm(pts[0] - pts[1])
    d12 = np.linalg.norm(pts[1] - pts[2])
    d23 = np.linalg.norm(pts[2] - pts[3])
    d30 = np.linalg.norm(pts[3] - pts[0])
    w_edge = (d01 + d23) / 2.0
    h_edge = (d12 + d30) / 2.0
    if w_edge / max(1, h_edge) > 1:
        pw = int(w_edge)
        ph = int(w_edge / ratio)
    else:
        ph = int(h_edge)
        pw = int(h_edge * ratio)
    dst = np.array([[0, 0], [pw, 0], [pw, ph], [0, ph]], np.float32)
    M = cv2.getPerspectiveTransform(pts, dst)
    return cv2.warpPerspective(img, M, (pw, ph))


if __name__ == "__main__":
    # 自包含 demo: 优先用 `--image 真实图`，否则合成一张 A4+工具示意图验证可运行
    img_path = sys.argv[1] if len(sys.argv) > 1 else None
    if img_path and os.path.exists(img_path):
        img = cv2.imread(img_path)
        print(f"[demo] 读取真实图: {img_path}  shape={img.shape}")
    else:
        W, H = 900, 640
        canvas = np.full((H, W, 3), 90, np.uint8)
        paper = np.array([[120, 60], [760, 90], [740, 560], [100, 540]], np.float32)
        cv2.fillPoly(canvas, [paper.astype(np.int32)], (235, 235, 235))
        cv2.fillPoly(
            canvas,
            [np.array([[300, 200], [520, 210], [510, 360], [310, 350]], np.int32)],
            (30, 30, 30),
        )
        img = canvas
        print("[demo] 未提供 --image，使用合成的 A4+工具示意图")

    res = detect_paper_corners_robust(img)
    if res is None:
        print("[demo] 检测失败: 未找到四边形")
        sys.exit(1)

    corners, cands = res
    pts = np.array(corners, float).reshape(-1, 2)
    d01 = np.linalg.norm(pts[0] - pts[1])
    d12 = np.linalg.norm(pts[1] - pts[2])
    d23 = np.linalg.norm(pts[2] - pts[3])
    d30 = np.linalg.norm(pts[3] - pts[0])
    ar = max((d01 + d23) / 2, (d12 + d30) / 2) / max(1, min((d01 + d23) / 2, (d12 + d30) / 2))
    print(f"[demo] 检测四角(TL,TR,BR,BL):\n{corners}")
    print(f"[demo] 宽高比={ar:.3f} (A4 标准≈1.414)")
    print(f"[demo] 采用方案={cands[0][2]}  分数={cands[0][1]:.3f}")
    print(f"[demo] 候选 Top3:")
    for c, s, m in cands[:3]:
        print(f"        {m:12s} score={s:.3f}")

    warped = warp_paper(img, corners)
    print(f"[demo] warp 后尺寸={warped.shape[1]}x{warped.shape[0]}")
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_detect.png")
    cv2.imwrite(out, warped)
    print(f"[demo] 已保存透视校正结果: {out}")
