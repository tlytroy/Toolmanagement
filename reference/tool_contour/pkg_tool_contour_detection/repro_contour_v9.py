"""
工具轮廓提取 v9 — 三绝招补全"最后缺口"

基于 v8 已验证的:
  ✓ 方案A mask (Top-Hat + adaptive + Otsu 并集)
  ✓ 内部孔洞填充
  ✓ 高斯低通平滑样条(无心电图抖动)

新增三绝招(解决 v8 最后的两个残局):
  绝招1: LAB L通道暗区捕获 — 解决纯黑物体(六角扳手)在灰背景上"隐形"
         核心修正: 不用 colorMask AND(对中性黑无效), 改用 OR 兜底
  绝招2: Bottom-Hat(底帽)去阴影 — 解决金属杆被阴影吞没(钳子底部)
  绝招3: Canny 边缘连接(轻量) — 桥接 1px 断裂, 不做主策略

流程:
  gray → [方案A | LAB暗区 | BlackHat校正 | Canny桥接] 四策略并集
       → 开运算去噪 → 填充内部孔洞 → 最大连通块 → 膨胀余量
       → 外轮廓(~2000pts) → median → 高斯低通平滑样条 → 最终

用法: python repro_contour_v9.py
"""
import cv2
import numpy as np
import os
import math
from math import acos, degrees, sqrt

OUT = "C:/Users/tlyth/WorkBuddy/2026-07-07-14-40-46"


# ============================================================
#  Part A: median 保边去噪 (来自 v8, 不变)
# ============================================================

def median_filter_points(pts, ksize=5):
    n = len(pts)
    if n < ksize or ksize < 3:
        return pts
    half = ksize // 2
    out = np.zeros_like(pts, dtype=np.float64)
    for i in range(n):
        window = np.array([pts[(i+j) % n] for j in range(-half, half+1)], dtype=np.float64)
        out[i, 0] = np.median(window[:, 0]); out[i, 1] = np.median(window[:, 1])
    return out


# ============================================================
#  Part B: 周期平滑样条 (来自 v8, 不变)
# ============================================================

def smooth_closed_spline(pts, sigma=4.0, n_samples=None, debug=False):
    """
    对闭合稠密轮廓做【平滑】而非【插值】的低通滤波。
    高斯权重的闭环滑动平均 → 像素抖动被平均, 直边保持直线。
    """
    pts = np.asarray(pts, dtype=np.float64)
    N = len(pts)
    if N < 8:
        return pts.reshape(-1, 1, 2).astype(np.int32)

    seg = np.hypot(np.roll(pts, -1, 0)[:, 0] - pts[:, 0],
                   np.roll(pts, -1, 0)[:, 1] - pts[:, 1])
    if np.allclose(seg, 0):
        return pts.reshape(-1, 1, 2).astype(np.int32)
    t = np.zeros(N)
    for i in range(1, N):
        t[i] = t[i-1] + seg[i-1]
    L = t[-1] + seg[-1]

    if n_samples is None:
        n_samples = max(N, 240)
    tt_new = np.linspace(0, L, n_samples, endpoint=False)
    xp = np.interp(tt_new, t, pts[:, 0], period=L)
    yp = np.interp(tt_new, t, pts[:, 1], period=L)

    half = max(int(round(3 * sigma)), 1)
    ksize = 2 * half + 1
    g = np.exp(-0.5 * (np.arange(-half, half + 1) / sigma) ** 2)
    g /= g.sum()
    xf = np.convolve(np.tile(xp, 3), g, mode='same')[n_samples:2*n_samples]
    yf = np.convolve(np.tile(yp, 3), g, mode='same')[n_samples:2*n_samples]

    out = np.column_stack([xf, yf])
    if debug:
        resid = np.hypot(xf - xp, yf - yp)
        print(f"       [smooth] N={N} sigma={sigma} ksize={ksize} "
              f"mean_shift={resid.mean():.2f}px max_shift={resid.max():.2f}px -> {n_samples}pts")
    return out.reshape(-1, 1, 2).astype(np.int32)


# ============================================================
#  Part C: 四策略 mask 并集 (核心增量: 三绝招)
# ============================================================

def tophat_deshedow(gray, kernel_size=31):
    """Top-Hat 去阴影 (来自 v8)"""
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, k)
    deshedow = cv2.subtract(gray, tophat)
    return deshedow, tophat


def mask_scheme_a(deshedow, block=31, C=8):
    """
    方案A: Top-Hat后 自适应INV + Otsu INV 并集 (v8验证通过的主体)
    对「亮工具 vs 白纸」效果最好。
    """
    m1 = cv2.adaptiveThreshold(deshedow, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY_INV, block, C)
    close_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    m1 = cv2.morphologyEx(m1, cv2.MORPH_CLOSE, close_k)

    _, m2 = cv2.threshold(deshedow, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    m2 = cv2.morphologyEx(m2, cv2.MORPH_CLOSE, close_k)

    return cv2.bitwise_or(m1, m2)


# ---------- 绝招1: LAB L通道暗区捕获 (修正版) ----------

def strategy_lab_dark(bgr, l_threshold_ratio=0.55):
    """
    绝招1修正版: 用 LAB L通道的「局部相对亮度」抓暗色物体。

    为什么不用用户原版的 colorMask AND?
      用户原码: finalMask = darkMask(L<120) AND colorMask(|A-128|>20)
      问题: 纯黑哑光物体(六角扳手)在LAB中 A≈128, B≈128(中性无色偏)
            → colorMask ≈ 空 → finalMask = 空 → 反而什么都抓不到!

    修正: 只用 L通道暗度, 不要求颜色偏移。
          对「黑vs灰」场景: 黑L~30-60, 灰背景L~130-180 → 直接用L区分即可。
          额外加 Otsu(L) 做"全局最优分界", 比 fixed threshold 更鲁棒。

    流程:
      BGR → LAB → 取L通道 → Otsu找分界点 → L < ratio*otsu_val 为"暗区"
      → 闭运算填缝 → 返回暗区mask
    """
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l_ch = lab[:, :, 0]  # L: 0=纯黑, 255=纯白

    # 用 Otsu 在 L 通道上自动找"暗/亮"分界点
    otsu_val, _ = cv2.threshold(l_ch, 0, 255, cv2.THRESH_OTSU)
    otsu_val = float(otsu_val)

    # 动态阈值: 比Otsu分界更"暗"的区域才算工具(避免误伤亮背景)
    thr = int(otsu_val * l_threshold_ratio)
    _, dark_mask = cv2.threshold(l_ch, thr, 255, cv2.THRESH_BINARY_INV)

    # 闭运算: 把断裂的暗区连起来(比如六角扳手的细长杆)
    close_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_CLOSE, close_k)

    return dark_mask, otsu_val, thr


# ---------- 绝招2: Bottom-Hat(底帽)去阴影 ----------

def strategy_blackhat_corrected(gray, kernel_size=21, block=31, C=10):
    """
    绝招2: 底帽变换(Bottom-Hat / Black-Hat) 提取并抵消阴影。

    Black-hat = closing(src) - src  → 提取出比周围"暗"的结构(阴影坑)
    corrected = src + black_hat   → 把阴影坑"填平"(提亮阴影区)

    然后 adaptiveThreshold 在 corrected 图上做阈值:
      原本被阴影压暗到 120 的金属 → corrected 后可能恢复到 160+
      白纸仍保持 240+ → 阈值能正确切在中间

    注意: 只对「有阴影但主体仍在」的场景有效。
          如果物体完全隐形(如黑扳手在黑背景), 底帽也救不了。
    """
    bk = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))

    # Black-hat: closing - src = 暗结构(阴影)
    blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, bk)

    # 加回原图: 提亮阴影区
    corrected = cv2.add(gray, blackhat)

    # 在校正图上跑自适应阈值
    m1 = cv2.adaptiveThreshold(corrected, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY_INV, block, C)
    close_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    m1 = cv2.morphologyEx(m1, cv2.MORPH_CLOSE, close_k)

    _, m2 = cv2.threshold(corrected, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    m2 = cv2.morphologyEx(m2, cv2.MORPH_CLOSE, close_k)

    return cv2.bitwise_or(m1, m2), blackhat, corrected


# ---------- 绝招3: Canny 边缘连接 (轻量辅助) ----------

def strategy_canny_bridge(gray, low_thresh=40, high_thresh=120,
                          dilate_iters=1, min_area_px=500):
    """
    绝招3(轻量版): Canny 边缘检测 + 极轻膨胀桥接断裂。

    ⚠️ 不是替代阈值策略, 而是「辅助桥梁」:
      Canny 找到物理边缘(即使灰度接近也能检测梯度变化)
      膨胀 1px 连接断开的边缘线
      findContours 取外轮廓填充
      过滤极小噪声(面积 < min_area_px)

    为什么不能做主策略?
      Canny 输出是 1px 线条(非填充区域), 对纹理丰富的物体会产生大量杂线。
      只在 union 中作为 OR 补充, 贡献"桥接断裂边缘"的作用。
    """
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blurred, low_thresh, high_thresh)

    if dilate_iters > 0:
        dk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 3))  # 垂直优先
        edges = cv2.dilate(edges, dk, iterations=dilate_iters)
        dk2 = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 1))  # 水平补充
        edges = cv2.dilate(edges, dk2, iterations=dilate_iters)

    # 从Canny边缘提取填充区域(闭运算让线变成面)
    close_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    filled = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, close_k)

    # findContours + 面积过滤
    cnts, _ = cv2.findContours(filled, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    bridge_mask = np.zeros_like(gray)
    for cnt in cnts:
        if cv2.contourArea(cnt) >= min_area_px:
            cv2.drawContours(bridge_mask, [cnt], -1, 255, -1)

    # 轻量开运算去噪
    open_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    bridge_mask = cv2.morphologyEx(bridge_mask, cv2.MORPH_OPEN, open_k)

    return bridge_mask


# ---------- 绝招4: 自适应阴影剔除(暗工具用强度, 亮工具用梯度) ----------

def remove_shadow_adaptive(gray, mask,
                            grad_factor=0.55,
                            min_grad=15,
                            peel_ksize=3,
                            max_peel=30,
                            close_ksize=3,
                            debug=False):
    """
    保守阴影剥离: 只用梯度法逐层剥柔和边, 不做亮度判断。

    改版原因(教训总结):
      - 全局强度阈值(gray<otsu*0.55): 砍掉灰金属工具 ❌
      - 自适应DARK/BRIGHT分流: 强度法+close叠加导致轮廓变形 ❌
      - 凸包修补(repair_bright_notches): 过度填充成非工具形状 ❌
      - 大核close(k=31): 填掉正常内凹 ❌

    本版只做一件事: 梯度低=柔和边=可能阴影, 逐层轻剥(最多30层)。
    对所有工具类型都安全——不碰绝对亮度，只看边缘锐利度。
    """
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    grad = np.sqrt(gx**2 + gy**2)

    n_mask = int(np.count_nonzero(mask))
    if n_mask == 0:
        return mask.copy(), 0

    result = mask.copy()
    ek = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (peel_ksize, peel_ksize))
    total_removed = 0
    n_peel = 0

    for _ in range(max_peel):
        eroded = cv2.erode(result, ek)
        boundary = cv2.bitwise_and(result, cv2.bitwise_not(eroded))
        n_bnd = int(np.count_nonzero(boundary))
        if n_bnd == 0:
            break

        bnd_grad = grad[boundary > 0]
        g_otsu, _ = cv2.threshold(np.clip(bnd_grad, 0, 255).astype(np.uint8),
                                  0, 255, cv2.THRESH_OTSU)
        g_otsu = max(float(g_otsu), min_grad)
        thr = g_otsu * grad_factor

        low_bnd = (boundary > 0) & (grad < thr)
        shadow_mask = np.zeros_like(result)
        shadow_mask[low_bnd] = 255
        n_shadow = int(np.count_nonzero(shadow_mask))
        if n_shadow == 0:
            break

        result = cv2.bitwise_and(result, cv2.bitwise_not(shadow_mask))
        total_removed += n_shadow
        n_peel += 1

    # 极小核close修复薄边断裂
    if close_ksize >= 3 and total_removed > 0:
        ck = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close_ksize, close_ksize))
        result = cv2.morphologyEx(result, cv2.MORPH_CLOSE, ck)

    n_result = int(np.count_nonzero(result))
    if n_result < n_mask * 0.50:
        if debug:
            print(f"       [shadow] ⚠️ over-strip {n_result/n_mask:.1%}, fallback!")
        return mask.copy(), 0

    if debug:
        print(f"       [shadow] peeled {n_peel} layers "
              f"removed={total_removed}px ({total_removed/n_mask:.1%})")

    return result, total_removed


# ---------- 内部孔洞填充 (来自 v8, 不变) ----------

def fill_internal_holes(mask):
    """填充 mask 内部所有孔洞(RETR_CCOMP)。
    仅用极小核 close(k=7) 桥接 1~3px 的细断裂，不改变轮廓几何形状。
    """
    contours, _ = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    filled = mask.copy()
    for i in range(1, len(contours)):
        if len(contours[i]) > 40:
            cv2.drawContours(filled, [contours[i]], -1, 255, -1)
    # 极小核: 只修 1~3px 断裂/毛刺, 不影响轮廓几何
    ck = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    filled = cv2.morphologyEx(filled, cv2.MORPH_CLOSE, ck, iterations=1)
    open_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    filled = cv2.morphologyEx(filled, cv2.MORPH_OPEN, open_k)
    return filled


def repair_bright_notches(mask, gray, bright_thresh=170, min_notch_area=200,
                          max_notch_ratio=0.03):
    """智能修补「高反光亮金属被四策略遗漏」导致的外轮廓窄凹陷。

    原理: 取最大外轮廓→凸包→减mask=缺口, 逐个检查灰度中位数:
      亮(>bright_thresh) → 高反光金属漏检 → 补 ✅ (钳子咬合区~195)
      暗(≤bright_thresh) → 正常几何缝隙   → 不补 ✅ (六角扳手间隙~140)

    安全阀: max_notch_ratio — 单个缺口面积超过 mask 总面积此比例时跳过。
             卡尺的"正常内凹"(白纸区)面积几万px > 3% → 不补 ✅
             钳子的真正缺口(~715px) 远 < 3% → 正常补 ✅
    """
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return mask, 0
    best = max(cnts, key=cv2.contourArea)
    hull = cv2.convexHull(best)
    hull_mask = np.zeros_like(mask)
    cv2.fillPoly(hull_mask, [hull], 255)
    notches = cv2.bitwise_and(hull_mask, cv2.bitwise_not(mask))
    notch_cnts, _ = cv2.findContours(notches, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    repaired = mask.copy()
    total_repaired = 0
    max_area = mask.size * max_notch_ratio  # 单缺口面积上限
    for nc in notch_cnts:
        area = cv2.contourArea(nc)
        if area < min_notch_area:
            continue
        if area > max_area:
            # 缺口太大 → 是工具正常内凹(如卡尺头部比尾部窄), 不是漏检
            continue
        nm = np.zeros_like(mask)
        cv2.drawContours(nm, [nc], -1, 255, -1)
        notch_gray = gray[nm > 0]
        if len(notch_gray) == 0:
            continue
        if float(np.median(notch_gray)) > bright_thresh:
            repaired = cv2.bitwise_or(repaired, nm)
            total_repaired += int(np.count_nonzero(nm))
    return repaired, total_repaired


# ============================================================
#  Part D: 主提取流程 (四策略并集)
# ============================================================

def extract_tool_contour_v9(warped, dilate_px=7, smooth=True,
                            sigma=4.0, median_ksize=5,
                            use_lab=True, use_blackhat=True, use_canny=True,
                            debug=False):
    """
    v9 主流程: 四策略 mask 并集 + 孔洞填充 + 平滑样条。

    返回: (union, debug_info_dict, raw_cnt, smooth_cnt)
      debug_info 包含各策略的贡献数据, 供可视化使用。
    """
    h, w = warped.shape[:2]
    bgr = warped if len(warped.shape) == 3 else cv2.cvtColor(warped, cv2.COLOR_GRAY2BGR)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY) if len(warped.shape) == 3 else warped.copy()

    debug_info = {}

    # ======== 策略1: 方案A (Top-Hat + adaptive + otsu) ========
    deshedow, tophat = tophat_deshedow(gray, kernel_size=31)
    m_a = mask_scheme_a(deshedow, block=31, C=8)
    if debug:
        debug_info['a_px'] = int(np.count_nonzero(m_a))
        print(f"       [scheme-A] px={debug_info['a_px']} ratio={debug_info['a_px']/m_a.size:.2%}")

    # ======== 策略2: LAB暗区捕获 (绝招1修正) ========
    m_lab = None
    if use_lab:
        m_lab, lab_otsu, lab_thr = strategy_lab_dark(bgr, l_threshold_ratio=0.55)
        if debug:
            debug_info['lab_px'] = int(np.count_nonzero(m_lab))
            print(f"       [LAB-dark] L-otsu={lab_otsu:.0f} thr={lab_thr} "
                  f"px={debug_info['lab_px']} ratio={debug_info['lab_px']/m_lab.size:.2%}")

    # ======== 策略3: BlackHat去阴影 (绝招2) ========
    m_bh = None
    if use_blackhat:
        m_bh, blackhat_img, corrected_gray = strategy_blackhat_corrected(gray, kernel_size=21)
        if debug:
            debug_info['bh_px'] = int(np.count_nonzero(m_bh))
            print(f"       [BlackHat] px={debug_info['bh_px']} ratio={debug_info['bh_px']/m_bh.size:.2%}")

    # ======== 策略4: Canny桥接 (绝招3轻量) ========
    m_canny = None
    if use_canny:
        m_canny = strategy_canny_bridge(gray, low_thresh=40, high_thresh=120)
        if debug:
            debug_info['canny_px'] = int(np.count_nonzero(m_canny))
            print(f"       [Canny-br] px={debug_info['canny_px']} ratio={debug_info['canny_px']/m_canny.size:.2%}")

    # ======== 四策略并集 ========
    union = m_a.copy()
    if m_lab is not None:
        union = cv2.bitwise_or(union, m_lab)
    if m_bh is not None:
        union = cv2.bitwise_or(union, m_bh)
    if m_canny is not None:
        union = cv2.bitwise_or(union, m_canny)

    if debug:
        total_px = int(np.count_nonzero(union))
        print(f"       [UNION-all] px={total_px} ratio={total_px/union.size:.2%}")

    # ======== 轻量开运算去噪(四策略并集后统一清理) ========
    open_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    union = cv2.morphologyEx(union, cv2.MORPH_OPEN, open_k)

    # ======== 先剔阴影(绝招4) — 必须在填补缺口之前! ========
    # 原因: bridge(k=31) 用凸包补缺口时, 补的是凸包内部区域(原始图上是
    #       白纸/背景), 该填充区与真背景边界梯度极低 → 若先补后剥, 会被
    #       阴影剥离当成"柔和阴影"又剥回去, 缺口重现。
    #       正确顺序: 先剥掉真阴影, 再补高反光金属的缺口(补完即终态)。
    if debug:
        pre_shadow_px = int(np.count_nonzero(union))
    union, n_removed = remove_shadow_adaptive(gray, union,
                                               debug=debug)
    if debug:
        post_shadow_px = int(np.count_nonzero(union))
        print(f"       [-shadow]  removed={n_removed}px -> {post_shadow_px}px "
              f"({post_shadow_px/union.size:.2%})")

    # ======== 填充内部孔洞(RETR_CCOMP) ========
    union = fill_internal_holes(union)
    if debug:
        after_holes = int(np.count_nonzero(union))
        print(f"       [+holes]   px={after_holes} ratio={after_holes/union.size:.2%}")

    # ======== 智能修补高反光缺口(已禁用 — 凸包修补过度填充) ========
    # union, n_repaired = repair_bright_notches(union, gray, bright_thresh=170, min_notch_area=500)
    # if debug and n_repaired > 0:
    #     print(f"       [+notch]   repaired={n_repaired}px")
    n_repaired = 0

    # 安全检查: 如果并集占比过高(>85%), 可能某个策略炸了, 回退到方案A
    total_px = int(np.count_nonzero(union))
    if total_px > union.size * 0.85:
        print(f"       ⚠️ UNION too large ({total_px/union.size:.1%}), falling back to scheme-A!")
        union = m_a
        union = fill_internal_holes(union)

    # ======== 最大连通块 ========
    cnts_all, _ = cv2.findContours(union, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts_all:
        return (union, debug_info, None, None)
    best_cnt = max(cnts_all, key=cv2.contourArea)

    # ======== 膨胀余量 ========
    tool_mask = np.zeros_like(union)
    cv2.drawContours(tool_mask, [best_cnt], -1, 255, -1)
    if dilate_px > 0:
        kd = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate_px*2+1, dilate_px*2+1))
        tool_mask = cv2.dilate(tool_mask, kd, iterations=1)

    final_cnts, _ = cv2.findContours(tool_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not final_cnts:
        return (union, debug_info, None, None)
    raw_contour = max(final_cnts, key=cv2.contourArea)

    if not smooth:
        return (union, debug_info, raw_contour, raw_contour)

    # ======== 平滑样条 ========
    pts = raw_contour.reshape(-1, 2).astype(np.float64)
    if median_ksize >= 3:
        pts = median_filter_points(pts, ksize=median_ksize)
    smooth_cnt = smooth_closed_spline(pts, sigma=sigma, debug=debug)

    return (union, debug_info, raw_contour, smooth_cnt)


# ============================================================
#  Part E: 可视化 (增强: 展示每个策略的贡献)
# ============================================================

def draw_v9(name, warped, debug=False):
    res = extract_tool_contour_v9(warped, dilate_px=7, smooth=True,
                                  sigma=4.0, median_ksize=5,
                                  use_lab=True, use_blackhat=True, use_canny=True,
                                  debug=debug)
    union, dbg, raw_cnt, smooth_cnt = res

    h, w = warped.shape[:2]
    def bgr(im):
        return cv2.cvtColor(im, cv2.COLOR_GRAY2BGR) if len(im.shape) == 2 else im.copy()
    gap = np.ones((h, 6, 3), dtype=np.uint8) * 200
    cols = []

    # 1) 原始灰度
    col = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY) if len(warped.shape)==3 else warped.copy()
    col = bgr(col); cv2.putText(col, "GRAY", (10,25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)
    cols.append(col)

    # 2) 方案A mask
    col = bgr(res[0])
    cv2.putText(col, f"scheme-A ({dbg.get('a_px','?')}px)", (10,25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200,200,200), 1)
    cols.append(col)

    # 3) LAB暗区
    lab_col = np.zeros((h,w,3), np.uint8)
    lab_m, lo, lt = strategy_lab_dark(warped if len(warped.shape)==3 else cv2.cvtColor(warped,cv2.COLOR_GRAY2BGR))
    lab_col = bgr(lab_m)
    cv2.putText(lab_col, f"LAB-dark (otsu={lo:.0f})", (10,25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255,100,100), 1)
    cols.append(lab_col)

    # 4) BlackHat校正
    bh_m, bh_img, corr = strategy_blackhat_corrected(
        cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY) if len(warped.shape)==3 else warped)
    bh_col = bgr(bh_m)
    cv2.putText(bh_col, f"BlackHat ({dbg.get('bh_px','?')}px)", (10,25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100,255,100), 1)
    cols.append(bh_col)

    # 5) 去除阴影后(绝招4)
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY) if len(warped.shape)==3 else warped
    shadow_removed, n_rm = remove_shadow_adaptive(gray, union, debug=False)
    sh_col = bgr(shadow_removed)
    cv2.putText(sh_col, f"-SHADOW (-{n_rm}px)", (10,25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255,200,0), 1)
    cols.append(sh_col)

    # 6) RAW轮廓
    col = bgr(warped)
    if raw_cnt is not None:
        cv2.drawContours(col, [raw_cnt], -1, (180,180,180), 1)
    cv2.putText(col, f"RAW ({len(raw_cnt) if raw_cnt is not None else 0}pts)",
                (10,25), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150,150,150), 1)
    cols.append(col)

    # 7) 平滑最终
    col = bgr(warped)
    if smooth_cnt is not None:
        cv2.drawContours(col, [smooth_cnt], -1, (0,220,80), 2)
        ov = col.copy(); cv2.fillPoly(ov, [smooth_cnt], [0,200,60])
        col = cv2.addWeighted(ov, 0.08, col, 0.92, 0)
    ar = cv2.contourArea(smooth_cnt) if smooth_cnt is not None else 0
    cv2.putText(col, f"SMOOTH ({len(smooth_cnt) if smooth_cnt is not None else 0}pts) area={ar:.0f}",
                (10,25), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0,220,80), 1)
    cols.append(col)

    row = np.hstack([c for i,c in enumerate(cols) for c in ([c,gap] if i<len(cols)-1 else [c])])
    p = os.path.join(OUT, f"v9_{name}_compare.png")
    cv2.imwrite(p, row)
    print(f"  -> compare: {p}  ({row.shape[1]}x{row.shape[0]})")

    # 单独最终贴合图
    solo = bgr(warped)
    if smooth_cnt is not None:
        cv2.drawContours(solo, [smooth_cnt], -1, (0,255,0), 2)
        ov = solo.copy(); cv2.fillPoly(ov, [smooth_cnt], [0,200,50])
        solo = cv2.addWeighted(ov, 0.08, solo, 0.92, 0)
    sp = os.path.join(OUT, f"v9_{name}_final.png")
    cv2.imwrite(sp, solo)
    print(f"  -> final:   {sp}")
    print(f"     RAW={len(raw_cnt) if raw_cnt is not None else 0}pts  "
          f"SMOOTH={len(smooth_cnt) if smooth_cnt is not None else 0}pts")


# ============================================================
#  Part F: 纸张检测 (同 v8, 不变)
# ============================================================

def detect_paper_battery(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g5 = cv2.GaussianBlur(gray, (5,5), 0); g9 = cv2.GaussianBlur(gray, (9,9), 0)
    m5 = cv2.medianBlur(gray, 5); m7 = cv2.medianBlur(gray, 7)
    h, w = img.shape[:2]; area = h*w
    minA = area*0.12; maxA = area*0.98; margin = max(4, round(0.008*min(h,w)))

    def find_quad(thresh):
        cands=[]
        cnts,_ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        for cnt in cnts:
            a = cv2.contourArea(cnt)
            if a<minA or a>maxA: continue
            p = cv2.arcLength(cnt, True)
            for ep in [0.02,0.025,0.03,0.04]:
                ap = cv2.approxPolyDP(cnt, ep*p, True)
                if len(ap)==4 and cv2.isContourConvex(ap):
                    pts = ap.reshape(4,2)
                    if any(pt[0]<margin or pt[0]>w-margin or pt[1]<margin or pt[1]>h-margin for pt in pts): continue
                    rect=np.zeros((4,2),np.float32)
                    s=pts.sum(axis=1); d=np.diff(pts,axis=1)
                    rect[0]=pts[np.argmin(s)]; rect[2]=pts[np.argmax(s)]
                    rect[1]=pts[np.argmin(d)]; rect[3]=pts[np.argmax(d)]
                    cands.append((rect,a)); break
        return max(cands,key=lambda x:x[1])[0] if cands else None

    def is_strong(q):
        pts=q.astype(int).tolist(); angs=[]
        for i in range(4):
            p1,p2,p3 = pts[i], pts[(i+1)%4], pts[(i+2)%4]
            v1=((p1[0]-p2[0]),(p1[1]-p2[1])); v3=((p3[0]-p2[0]),(p3[1]-p2[1]))
            m1=np.hypot(*v1); m2=np.hypot(*v3)
            cos=(v1[0]*v3[0]+v1[1]*v3[1])/(m1*m2) if m1>0 and m2>0 else 1
            angs.append(abs(degrees(acos(np.clip(cos,-1,1)))-90))
        return max(angs)<15

    primary = find_quad(cv2.threshold(g5,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)[1])
    if primary is not None and is_strong(primary): return primary

    all_cands=[]
    for sm in [g5,g9,m5,m7]:
        q=find_quad(cv2.threshold(sm,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)[1])
        if q is not None: all_cands.append((q,'otsu'))
    for lo,hi,ks in [(30,90,3),(50,150,5),(80,200,7)]:
        ed=cv2.Canny(g5,lo,hi); ed=cv2.dilate(ed,cv2.getStructuringElement(cv2.MORPH_RECT,(ks,ks)))
        q=find_quad(ed)
        if q is not None: all_cands.append((q,'canny'))
    for method in [cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.ADAPTIVE_THRESH_MEAN_C]:
        for bs in [11,21]:
            ad=cv2.adaptiveThreshold(g5,255,method,cv2.THRESH_BINARY,bs,4)
            q=find_quad(ad)
            if q is not None: all_cands.append((q,'adaptive'))
    if len(all_cands)==0: return None
    diag=np.hypot(h,w); tol=0.16*diag; used=[False]*len(all_cands); clusters=[]
    for i in range(len(all_cands)):
        if used[i]: continue
        grp=[all_cands[i]]; used[i]=True
        for j in range(i+1,len(all_cands)):
            if used[j]: continue
            d=np.mean([np.hypot(all_cands[i][0][k][0]-all_cands[j][0][k][0],
                                 all_cands[i][0][k][1]-all_cands[j][0][k][1]) for k in range(4)])
            if d<tol: grp.append(all_cands[j]); used[j]=True
        clusters.append(grp)
    clusters.sort(key=len, reverse=True)
    return np.round(np.mean([q[0] for q in clusters[0]], axis=0)).astype(np.int32)


tests = [
    ("test_cal.jpg",  "calipers"),
    ("test_03.jpg",  "hexkey_shadow"),
    ("test_05.jpg",  "pliers"),
]

for fname, name in tests:
    path = os.path.join(OUT, fname)
    if not os.path.exists(path):
        print(f"SKIP {fname}"); continue
    print(f"\n{'='*50}\n  {name} ({fname})\n{'='*50}")
    img = cv2.imread(path)
    if img is None:
        print(f"  FAIL read"); continue
    corners = detect_paper_battery(img)
    if corners is None:
        print(f"  FAIL no paper"); continue
    img_w, img_h = img.shape[1], img.shape[0]
    pw, ph = (int(img_h*0.707), img_h) if img_h > img_w else (img_w, int(img_w*0.707))
    dst = np.array([[0,0],[pw,0],[pw,ph],[0,ph]], np.float32)
    M = cv2.getPerspectiveTransform(corners.astype(np.float32), dst)
    warped = cv2.warpPerspective(img, M, (pw, ph))
    wp = os.path.join(OUT, f"v9_{name}_warped.png")
    cv2.imwrite(wp, warped)
    print(f"  corners={corners.tolist()} -> warped({pw}x{ph})")
    draw_v9(name, warped, debug=True)

print("\n✅ v9 Done! 四策略并集(LAB暗区+BlackHat+Canny+方案A) + 平滑样条")
