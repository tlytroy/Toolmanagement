"""
并集方案尝试: 在当前"红(SAM)∪绿(Fast)都挺好用"的基础上,
取 Final = Red ∪ Green, 然后做形态学收缩(erode 3x3) 吃掉边缘薄阴影/噪点, 再平滑。

不做复杂的几何判断去阴影(容易误伤钳子这类复杂工具);
阴影交给"Fast 本身不含阴影 + 并集后 erode 啃边缘"自然解决。

输出对比图: 绿=Fast参考  橙=SAM参考(淡)  紫=并集mask  红=并集平滑轮廓
指标: U_px(并集像素) / fast\\U(erode是否啃掉工具) / U∩shadow(阴影泄漏)
"""
import cv2, numpy as np, os, sys, time
OUT = "C:/Users/tlyth/WorkBuddy/2026-07-07-14-40-46"
sys.path.insert(0, OUT)
from repro_contour_v9 import (
    detect_paper_battery, extract_tool_contour_v9, smooth_closed_spline,
)
import torch
from segment_anything import sam_model_registry, SamAutomaticMaskGenerator

CKPT = os.path.join(OUT, "sam_vit_b_01ec64.pth")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[SAM] loading vit_b on {DEVICE} ...")
sam = sam_model_registry["vit_b"](checkpoint=CKPT).to(DEVICE)
mask_gen = SamAutomaticMaskGenerator(
    sam, points_per_side=16, pred_iou_thresh=0.80,
    stability_score_thresh=0.85, crop_n_layers=0, min_mask_region_area=300,
)


def warp_image(img):
    corners = detect_paper_battery(img)
    if corners is None:
        return None
    h, w = img.shape[:2]
    pw, ph = (int(h * 0.707), h) if h > w else (w, int(w * 0.707))
    dst = np.array([[0, 0], [pw, 0], [pw, ph], [0, ph]], np.float32)
    M = cv2.getPerspectiveTransform(corners.astype(np.float32), dst)
    return cv2.warpPerspective(img, M, (pw, ph))


def largest_contour(mask):
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    return max(cnts, key=cv2.contourArea) if cnts else None


def merged_contour(mask):
    """取所有外部轮廓并集 + close(9)桥接, 再提最大轮廓 (防多连通域断裂丢组件)"""
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return None
    union_mask = np.zeros_like(mask)
    cv2.drawContours(union_mask, cnts, -1, 255, -1)
    kbridge = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    union_mask = cv2.morphologyEx(union_mask, cv2.MORPH_CLOSE, kbridge)
    final_cnts, _ = cv2.findContours(union_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    return max(final_cnts, key=cv2.contourArea) if final_cnts else None


def chaikin_smooth(contour, passes=2):
    """Chaikin 曲线平滑: 每个线段取 1/4、3/4 处插值, 迭代 passes 次, 保角不磨尖。
    替代 smooth_closed_spline: 全局样条会把钳口尖角磨圆, Chaikin 几何保角。"""
    pts = contour.reshape(-1, 2).astype(np.float64)
    for _ in range(passes):
        new_points = []
        n = len(pts)
        for i in range(n):
            p1 = pts[i]
            p2 = pts[(i + 1) % n]
            q = p1 * 0.75 + p2 * 0.25
            r = p1 * 0.25 + p2 * 0.75
            new_points.append(q)
            new_points.append(r)
        pts = np.array(new_points, dtype=np.float64)
    return pts.reshape(-1, 1, 2).astype(np.int32)


# ===================== 工业级 XLD 风格管线 (Halcon→OpenCV) =====================
# 对标: edges_sub_pix → gen_contours_smooth_xld → split_contours_xld → fit_[line/circle]_contour_xld
# 比 Chaikin/全局样条对症: mask 级先治理(源头压锯齿) + 亚像素 refine(用灰度梯度) + 曲率分段拟合

def preprocess_mask_for_contour(merged, close_k=5, gauss_k=5, gauss_sigma=1.0):
    """SAM 合并后的 mask → 去锯齿 → 闭运算填缝。让轮廓点本身干净, 而非靠轮廓级平滑去救。"""
    m = cv2.medianBlur(merged, 3)                                  # 去椒盐 + 像素台阶(保边)
    m = cv2.GaussianBlur(m, (gauss_k, gauss_k), gauss_sigma)       # 轻高斯顺边缘(σ=1.0 防糊钳口)
    _, m = cv2.threshold(m, 127, 255, cv2.THRESH_BINARY)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close_k, close_k))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k)                     # 填 SAM 多块拼接缝
    return m

def subpixel_refine_contour(contour, gray, win=(7, 7)):
    """把轮廓点 refine 到亚像素(±0.1px)。必须用原灰度图(有梯度信息), 不能只用 mask。"""
    pts = contour.reshape(-1, 1, 2).astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.01)
    cv2.cornerSubPix(gray, pts, win, (-1, -1), criteria)
    return pts.reshape(-1, 2)

def classify_segments(pts, angle_thresh=20, curv_thresh=0.05):
    """曲率分段: 返回 [(type, start, end), ...]  type: 'line'|'arc'。闭合环首尾相接。"""
    N = len(pts)
    segs = []
    cur_type = None
    cur_start = 0
    for i in range(N):
        p_prev = pts[(i - 1) % N]
        p_curr = pts[i]
        p_next = pts[(i + 1) % N]
        v1 = p_curr - p_prev
        v2 = p_next - p_curr
        cross_val = v1[0] * v2[1] - v1[1] * v2[0]   # 2D 叉积(标量)
        ang = abs(np.arctan2(cross_val, np.dot(v1, v2)) * 180 / np.pi)
        a = np.linalg.norm(p_prev - p_curr)
        b = np.linalg.norm(p_curr - p_next)
        c = np.linalg.norm(p_prev - p_next)
        s = (a + b + c) / 2
        area = np.sqrt(max(s * (s - a) * (s - b) * (s - c), 1e-10))
        curv = (2 * area) / (a * b + 1e-10)
        is_arc = (ang > angle_thresh) or (curv > curv_thresh)
        if cur_type is None:
            cur_type = 'arc' if is_arc else 'line'
        elif (is_arc and cur_type == 'line') or (not is_arc and cur_type == 'arc'):
            segs.append((cur_type, cur_start, i - 1))
            cur_type = 'arc' if is_arc else 'line'
            cur_start = i
    segs.append((cur_type, cur_start, N - 1))
    return segs

def project_to_line(pts, vx, vy, x0, y0):
    """把点投影到拟合直线, 保持首尾端点(避免线段缩短)。"""
    d = np.array([vx, vy], dtype=np.float64)
    d = d / (np.linalg.norm(d) + 1e-9)
    p = pts.astype(np.float64)
    rel = p - np.array([x0, y0])
    t = rel @ d
    proj = np.array([x0, y0]) + np.outer(t, d)
    proj[0] = p[0]
    proj[-1] = p[-1]
    return proj

def fit_segment(seg_pts, seg_type='line'):
    """分段拟合: 直边→fitLine投影(绝对直); 弧边→椭圆拟合+角度裁剪(防溢出)。"""
    seg_pts = np.asarray(seg_pts, dtype=np.float64)
    if len(seg_pts) < 3:
        return seg_pts
    if seg_type == 'line':
        vx, vy, x0, y0 = cv2.fitLine(seg_pts, cv2.DIST_L2, 0, 0.01, 0.01).flatten()
        return project_to_line(seg_pts, vx, vy, x0, y0)
    else:  # arc 分支：椭圆拟合 + 角度裁剪（只画该短弧对应角度，绝不溢出）
        if len(seg_pts) >= 5:
            try:
                (cx, cy), (MA, ma), angle = cv2.fitEllipse(seg_pts)
                cx, cy = float(cx), float(cy)
                r = (MA + ma) / 4.0  # 长短轴均值作半径
                start_pt = seg_pts[0]
                end_pt = seg_pts[-1]
                v1 = start_pt - np.array([cx, cy])
                v2 = end_pt - np.array([cx, cy])
                a1 = (np.arctan2(v1[1], v1[0]) + 2 * np.pi) % (2 * np.pi)
                a2 = (np.arctan2(v2[1], v2[0]) + 2 * np.pi) % (2 * np.pi)
                span = abs(a2 - a1)
                if span > np.pi:
                    span = 2 * np.pi - span
                n = max(5, int(span / (np.pi / 180) * 0.8))
                if abs(a2 - a1) > np.pi:
                    angles = np.linspace(a1, a2 + 2 * np.pi, n) % (2 * np.pi)
                else:
                    angles = np.linspace(a1, a2, n)
                return np.stack([cx + r * np.cos(angles), cy + r * np.sin(angles)], axis=1)
            except Exception:
                pass  # 椭圆拟合失败(退化)
        # 退化：minEnclosingCircle + 端点角度裁剪（需 float32 输入）
        (cx, cy), r = cv2.minEnclosingCircle(seg_pts.astype(np.float32))
        cx, cy, r = float(cx), float(cy), float(r)
        p0 = seg_pts[0]
        pn = seg_pts[-1]
        a0 = np.arctan2(p0[1] - cy, p0[0] - cx)
        an = np.arctan2(pn[1] - cy, pn[0] - cx)
        diff = an - a0
        if abs(diff) > np.pi:
            if diff > 0:
                diff -= 2 * np.pi
            else:
                diff += 2 * np.pi
        step = np.sign(diff) * 0.05
        angles = np.arange(a0, a0 + diff, step)
        return np.stack([cx + r * np.cos(angles), cy + r * np.sin(angles)], axis=1)

def smooth_contour_xld_style(merged_mask, gray, close_k=5):
    """对标 Halcon XLD 四步法。输入: 并集+erode 后的 mask, 原灰度图。返回分段拟合闭合轮廓。"""
    m = preprocess_mask_for_contour(merged_mask, close_k)
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return None
    # 全组件并集(防 max 丢组件, 如卡尺尺身), 再取最大轮廓
    union_all = np.zeros_like(m)
    cv2.drawContours(union_all, cnts, -1, 255, cv2.FILLED)
    fc, _ = cv2.findContours(union_all, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not fc:
        return None
    cnt = max(fc, key=cv2.contourArea).reshape(-1, 2)
    cnt_sp = subpixel_refine_contour(cnt, gray)
    segs = classify_segments(cnt_sp, angle_thresh=20, curv_thresh=0.05)
    result = []
    for typ, s, e in segs:
        sp = np.concatenate([cnt_sp[s:e + 1], [cnt_sp[s]]]) if e < s else cnt_sp[s:e + 1]
        result.append(fit_segment(sp, typ))
    final = np.concatenate(result, axis=0)
    return final.reshape(-1, 1, 2).astype(np.int32)


# ===== 参数(对齐现有 Red/Green) =====
AREA_MIN = 100
OVERLAP_MIN = 0.5       # 几何门控: 候选多数在工具上才并入(防A4纸爆掉, 非阴影几何判断)
CLOSE_K = 9
EXPAND_PX = 7           # 同 Fast dilate_px=7
ERODE_K = 3             # 并集后轻微腐蚀, 吃边缘薄阴影/噪点
CHAIKIN_PASSES = 2      # Chaikin 平滑迭代次数: 2 次已收敛(与3无差异, 点数少一半)

tests = [("test_cal.jpg", "calipers"), ("test_03.jpg", "hexkey_shadow"), ("test_05.jpg", "pliers")]
print(f"{'name':14} {'mode':14} {'U_px':>9} {'U%':>6} {'fast\\U':>7} {'U∩shdw':>7} {'t':>5}")
print("-" * 64)

for fname, name in tests:
    img = cv2.imread(os.path.join(OUT, fname))
    warped = warp_image(img)
    if warped is None:
        print(f"{name:14} WARP_FAIL"); continue
    h, w = warped.shape[:2]
    _, _, raw_cnt, smooth_cnt = extract_tool_contour_v9(warped, debug=False)
    fast = np.zeros((h, w), np.uint8)
    if raw_cnt is not None:
        cv2.drawContours(fast, [raw_cnt], -1, 255, -1)
    fast_f = fast > 0
    fast_px = int(np.count_nonzero(fast))
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY) if len(warped.shape) == 3 else warped.copy()

    t0 = time.time()
    masks = mask_gen.generate(warped)
    dt = time.time() - t0

    # ---- Red: SAM 合并(含 isShadowMaskSimple 几何拒阴影, 因"当前已挺好用"保留) ----
    fast_cnt = largest_contour(fast)
    tool_dist_map = cv2.distanceTransform((~fast).astype(np.uint8), cv2.DIST_L2, 5)

    def is_shadow_mask_simple(seg, tool_cnt, tdm):
        s = int(np.count_nonzero(seg))
        if s == 0: return True
        m = cv2.moments(seg)
        if m['m00'] == 0: return True
        cx, cy = int(m['m10']/m['m00']), int(m['m01']/m['m00'])
        if tool_cnt is not None and cv2.pointPolygonTest(tool_cnt, (cx, cy), False) > 0:
            return False
        vals = tdm[seg > 0]; md = float(vals.min()) if vals.size else 999.0
        if md > 25: return True
        if s < 200: return True
        return False

    merged = np.zeros((h, w), np.uint8)
    kept = 0
    for mi, m in enumerate(masks):
        seg = m["segmentation"].astype(np.uint8) * 255
        seg_sum = int(np.count_nonzero(seg))
        if seg_sum < AREA_MIN: continue
        inter = int(np.count_nonzero(cv2.bitwise_and(seg, fast)))
        if inter == 0: continue
        if inter / seg_sum < OVERLAP_MIN: continue
        if is_shadow_mask_simple(seg, fast_cnt, tool_dist_map): continue
        merged = cv2.bitwise_or(merged, seg)
        kept += 1

    kclose = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (CLOSE_K, CLOSE_K))
    merged_final = cv2.morphologyEx(merged, cv2.MORPH_CLOSE, kclose)
    if EXPAND_PX > 0:
        kexp = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (EXPAND_PX*2+1, EXPAND_PX*2+1))
        merged_final = cv2.dilate(merged_final, kexp, iterations=1)

    # ============ 并集: Final = Red(SAM) ∪ Green(Fast) ============
    union = cv2.bitwise_or(merged_final, fast)
    # 形态学收缩: 轻微腐蚀吃边缘薄阴影/噪点
    ke = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ERODE_K, ERODE_K))
    union_e = cv2.erode(union, ke, iterations=1)

    # 取轮廓 + Chaikin 平滑(保角, 不磨尖角, 2次已收敛)
    union_cnt = merged_contour(union_e)
    union_smooth = None
    if union_cnt is not None and len(union_cnt) > 4:
        union_smooth = chaikin_smooth(union_cnt, passes=CHAIKIN_PASSES)

    # ---- 指标 ----
    U_px = int(np.count_nonzero(union_e))
    # erode 是否啃掉工具(fast 的工具像素不在 union_e 内 → 说明 erode 太狠)
    fast_not_in_U = int(np.count_nonzero(cv2.bitwise_and(fast, cv2.bitwise_not(union_e))))
    # 阴影泄漏: union_e 与 "工具外侧暗区" 的重叠
    dark_outside = (gray < 160) & (~fast_f)
    dark_u8 = dark_outside.astype(np.uint8) * 255
    u_leak = int(np.count_nonzero(cv2.bitwise_and(union_e, dark_u8)))
    print(f"{name:14} {'union+erode':14} {U_px:>9} {U_px/(h*w)*100:>5.1f}% {fast_not_in_U:>7} {u_leak:>7} {dt:>4.1f}s")

    # ---- 可视化 ----
    vis = warped.copy()
    ov = vis.copy(); ov[union_e > 0] = (180, 80, 200)   # 紫 = 并集 mask
    vis = cv2.addWeighted(ov, 0.35, vis, 0.65, 0)
    if smooth_cnt is not None:
        cv2.drawContours(vis, [smooth_cnt], -1, (0, 255, 0), 2)       # 绿 = Fast 参考
    sam_ref = largest_contour(merged_final)
    if sam_ref is not None:
        cv2.drawContours(vis, [sam_ref], -1, (255, 120, 0), 1)        # 橙 = SAM 参考(淡)
    if union_smooth is not None:
        cv2.drawContours(vis, [union_smooth], -1, (0, 0, 255), 2)     # 红 = 并集平滑轮廓
    cv2.putText(vis, f"UNION(SAM\u222aFast)+erode{ERODE_K} | kept={kept} U={U_px} fast\\U={fast_not_in_U} leak={u_leak}",
                (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
    cv2.imwrite(os.path.join(OUT, f"union_{name}.png"), vis)
    print(f"  -> union_{name}.png (kept {kept} of {len(masks)} masks)")

print("\n✅ union done.")
