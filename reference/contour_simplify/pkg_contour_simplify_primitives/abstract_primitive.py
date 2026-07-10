"""
基元化（抽象化）脚本
输入：并集 + erode(3) + Chaikin(pass=2) 后的轮廓
输出：直线 + 圆弧 基元，可视化对比图
依赖：仅 numpy + cv2（你环境已有）
"""
import numpy as np
import cv2, os, sys

OUT = "C:/Users/tlyth/WorkBuddy/2026-07-07-14-40-46"
sys.path.insert(0, OUT)
from repro_contour_v9 import detect_paper_battery, extract_tool_contour_v9
import torch
from segment_anything import sam_model_registry, SamAutomaticMaskGenerator

CKPT = os.path.join(OUT, "sam_vit_b_01ec64.pth")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
sam = sam_model_registry["vit_b"](checkpoint=CKPT).to(DEVICE)
mask_gen = SamAutomaticMaskGenerator(sam, points_per_side=16, pred_iou_thresh=0.80,
                                    stability_score_thresh=0.85, crop_n_layers=0, min_mask_region_area=300)

# ==================== 工具函数 ====================
def warp_image(img):
    corners = detect_paper_battery(img)
    if corners is None: return None
    h, w = img.shape[:2]
    pw, ph = (int(h*0.707), h) if h > w else (w, int(w*0.707))
    dst = np.array([[0,0],[pw,0],[pw,ph],[0,ph]], np.float32)
    M = cv2.getPerspectiveTransform(corners.astype(np.float32), dst)
    return cv2.warpPerspective(img, M, (pw, ph))

def largest_contour(mask):
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    return max(cnts, key=cv2.contourArea) if cnts else None

def chaikin_smooth(contour, passes=2):
    pts = contour.reshape(-1, 2).astype(np.float64)
    for _ in range(passes):
        new_pts = []
        n = len(pts)
        for i in range(n):
            p1, p2 = pts[i], pts[(i+1)%n]
            new_pts.append(p1 * 0.75 + p2 * 0.25)
            new_pts.append(p1 * 0.25 + p2 * 0.75)
        pts = np.array(new_pts, dtype=np.float64)
    return pts  # (N, 2)

def rdp_decimate(pts, epsilon_px=2.0):
    """RDP 抽稀，直边只剩 2 端点"""
    eps = float(epsilon_px)
    marker = np.zeros(len(pts), dtype=bool)
    marker[0] = marker[-1] = True
    stack = [(0, len(pts)-1)]
    while stack:
        s, e = stack.pop()
        if e - s < 2: continue
        p0, p1 = pts[s], pts[e]
        v = p1 - p0
        v2 = v @ v
        if v2 < 1e-10:
            mid = (s+e)//2
            stack.append((s, mid)); stack.append((mid, e))
            continue
        max_d, max_i = 0.0, s
        for i in range(s+1, e):
            # 2D cross product = scalar (z-component only)
            diff = pts[i] - p0
            d = (diff[0]*v[1] - diff[1]*v[0])**2 / v2
            if d > max_d: max_d, max_i = d, i
        if max_d > eps*eps:
            marker[max_i] = True
            stack.append((s, max_i)); stack.append((max_i, e))
    return pts[marker]

def rdp_simplify_closed(pts, epsilon=2.0):
    """
    闭合轮廓 RDP 抽稀（保留拓扑连续性）：
    - 去掉尾部重合点（闭合环首尾同点）→ RDP 抽稀
    - 末尾强制 append 首点闭合，避免 classify 拿到破碎线段
    - 直边自然坍成 2 端点，曲线保留多点（RDP 误差阈值逻辑）
    """
    pts = np.asarray(pts, dtype=np.float64)
    if len(pts) > 1 and np.linalg.norm(pts[-1] - pts[0]) < 1e-6:
        work = pts[:-1]
    else:
        work = pts
    if len(work) < 3:
        return pts
    simp = rdp_decimate(work, epsilon_px=epsilon)
    if len(simp) == 0:
        return pts
    closed = np.vstack([simp, simp[0:1]])  # 强制闭合
    return closed

def fit_arc_b(pts, max_radius=200):
    """
    圆弧拟合（方案B核心）：
    - 用 cv2.fitEllipse 做最小二乘圆拟合（返回直径，半径=轴长和/4）
    - 关键坑：cv2.minEnclosingCircle 对 <180° 的弧会退化为“弦直径圆”，半径严重偏小
      （90°圆角会被压成 ~弦长/2，比真实半径小约30%）→ 真实圆角必须用最小二乘拟合
    - 角度用解缠绕(unwrap)的连续角，避免 %360 在 0/360 边界把方向判反
      （否则会把 0→88° 的弧画成 360→88° 的 272° 长弧）
    - 半径上限 max_radius / 下限 5px；圆度(轴长比)超限拒识；平均拟合误差过大拒识
    """
    if len(pts) < 5:
        return None
    pts32 = pts.astype(np.float32)
    try:
        (cx, cy), (rax, ray), ang = cv2.fitEllipse(pts32)
    except Exception:
        return None
    cx, cy = float(cx), float(cy)
    rmin, rmaj = sorted([rax, ray])
    radius = (rax + ray) / 4.0   # fitEllipse 返回的是直径(全轴长)，半径取轴长和/4
    if rmaj > 1e-3 and (rmaj - rmin) / rmaj > 0.25:
        return None   # 不是圆（被直边污染 / 误判）
    if radius < 5.0 or radius > max_radius:
        return None
    # 端点角度：解缠绕的连续角度，正确表达方向与跨度
    theta = np.arctan2(pts[:, 1]-cy, pts[:, 0]-cx)
    theta_u = np.unwrap(theta)
    a0 = float(np.degrees(theta_u[0]))
    a1 = float(np.degrees(theta_u[-1]))
    span = abs(a1 - a0)
    if span < 20 or span > 180:
        return None
    # 误差检查：采样点到拟合圆平均残差
    dists = np.abs(np.linalg.norm(pts - np.array([cx, cy]), axis=1) - radius)
    mean_err = np.mean(dists)
    max_error = 2.0 + (span - 20) / 30.0
    if mean_err > max_error:
        return None
    n = max(8, int(span / 5))  # 每 5° 一个点
    angles = np.linspace(a0, a1, n)
    arc_pts = np.stack([cx + radius*np.cos(np.radians(angles)),
                        cy + radius*np.sin(np.radians(angles))], axis=1)
    return ('ARC', (cx, cy, radius, a0, a1), arc_pts)

def adaptive_rdp(pts, segment_flags, min_arc_len=5):
    """
    方案B抽稀：
    - 直线段（segment_flags=False）只留首尾 2 点（完全拍平）
    - 弧段（segment_flags=True）保留密度直接拟合圆，太短(<min_arc_len)退化成直线
    返回 [(type, points), ...] —— 顺序即轮廓顺序，下游直接按标签组装基元
    """
    n = len(pts)
    if n < 3:
        return [('LINE', pts)]
    segments = []
    i = 0
    while i < n:
        if segment_flags[i]:
            start_i = i
            while i < n and segment_flags[i]:
                i += 1
            arc_seg = pts[start_i:i]
            if len(arc_seg) >= min_arc_len:
                segments.append(('ARC_CAND', arc_seg))
            elif len(arc_seg) >= 2:
                segments.append(('LINE', np.array([arc_seg[0], arc_seg[-1]])))
        else:
            start_i = i
            while i < n and not segment_flags[i]:
                i += 1
            line_seg = pts[start_i:i]
            if len(line_seg) >= 2:
                segments.append(('LINE', np.array([line_seg[0], line_seg[-1]])))
    return segments

def classify_and_fit_fixed(pts_chaikin, curv_thresh=0.025, max_radius=150, dil_k=1):
    """
    方案B（自适应抽稀 + 安全拟合）：
      1) 一阶差分曲率 sin(theta) 标记弯曲点
      2) 开运算去噪：先腐蚀(3窗口≥2)去孤立噪声，可选轻度膨胀(dil_k)桥接断点
         —— 注意：膨胀核过大会把直边点吞进弧段，导致 fitEllipse 半径偏大，
            故默认 dil_k=1（不膨胀），只在确有断点时才调大
      3) adaptive_rdp：直线坍2点、弧保密度
      4) 组装：LINE 段直接基元；ARC_CAND 段 fit_arc_b 拟合（失败退化直线）
    """
    pts = np.asarray(pts_chaikin, dtype=np.float64)
    n = len(pts)
    if n < 4:
        return [('LINE', (pts[0], pts[-1]), pts)]
    # Step1: 一阶差分曲率
    curvature = np.zeros(n)
    for i in range(1, n - 1):
        v1 = pts[i] - pts[i-1]
        v2 = pts[i+1] - pts[i]
        L1 = np.linalg.norm(v1); L2 = np.linalg.norm(v2)
        if L1 > 1e-6 and L2 > 1e-6:
            cos_t = np.clip(np.dot(v1, v2) / (L1 * L2), -1.0, 1.0)
            curvature[i] = np.sin(np.arccos(cos_t))
    # Step2: 开运算去噪（腐蚀 + 可选膨胀）
    is_arc = (curvature > curv_thresh)
    is_arc = np.convolve(is_arc.astype(int), np.ones(3), mode='same') >= 2   # 腐蚀去孤立噪声
    if dil_k > 1:
        is_arc = np.convolve(is_arc.astype(int), np.ones(dil_k), mode='same') >= 1  # 轻度膨胀桥接断点
    is_arc = is_arc.astype(bool)
    # Step3: 自适应 RDP -> 带类型的段
    segments = adaptive_rdp(pts, is_arc, min_arc_len=5)
    # Step4: 组装基元（直接用段标签，不贪心扫描）
    primitives = []
    for typ, seg in segments:
        if typ == 'LINE':
            primitives.append(('LINE', (seg[0], seg[-1]), seg))
        else:
            arc = fit_arc_b(seg, max_radius=max_radius)
            if arc is not None:
                primitives.append(arc)
            else:
                primitives.append(('LINE', (seg[0], seg[-1]), seg))
    return primitives

# ===== 参数（与 sam_union_final.py 完全一致）=====
CLOSE_K = 9
EXPAND_PX = 7
ERODE_K = 3

# ==================== 主流程 ====================
tests = [("test_cal.jpg","calipers"), ("test_03.jpg","hexkey_shadow"), ("test_05.jpg","pliers")]

for fname, name in tests:
    img = cv2.imread(os.path.join(OUT, fname))
    warped = warp_image(img)
    if warped is None: continue
    h, w = warped.shape[:2]

    # Fast 轮廓
    _, _, raw_cnt, smooth_cnt = extract_tool_contour_v9(warped, debug=False)
    fast = np.zeros((h, w), np.uint8)
    if raw_cnt is not None:
        cv2.drawContours(fast, [raw_cnt], -1, 255, -1)

    # SAM 合并（简化版，你已有）
    # NO_SAM=1 时跳过 SAM（本沙箱 torch CPU 推理会段错误），退化为 Fast-only 并集，
    # 仅用于验证基元化管线；完整并集请在能跑 SAM 的环境运行。
    use_sam = os.environ.get("NO_SAM") is None
    merged = np.zeros((h, w), np.uint8)
    if use_sam:
        masks = mask_gen.generate(warped)
        fast_cnt = largest_contour(fast)
        tool_dist = cv2.distanceTransform((~fast).astype(np.uint8), cv2.DIST_L2, 5)
        for m in masks:
            seg = m["segmentation"].astype(np.uint8)*255
            if np.count_nonzero(seg) < 100: continue
            inter = int(np.count_nonzero(cv2.bitwise_and(seg, fast)))
            if inter == 0: continue
            if inter / np.count_nonzero(seg) < 0.5: continue
            # 简易阴影拒识
            mmt = cv2.moments(seg)
            if mmt['m00'] > 0:
                cx = int(mmt['m10']/mmt['m00'])
                cy = int(mmt['m01']/mmt['m00'])
                if fast_cnt is not None and cv2.pointPolygonTest(fast_cnt, (cx,cy), False) <= 0:
                    min_d = float(tool_dist[seg>0].min()) if np.any(seg>0) else 999
                    if min_d > 25 or np.count_nonzero(seg) < 200: continue
            merged = cv2.bitwise_or(merged, seg)
    else:
        print("           [NO_SAM] 跳过 SAM，使用 Fast-only 并集（仅验证基元化管线）")

    # ===== 并集管线（与 sam_union_final.py 完全一致）=====
    # SAM 合并后先 close(9) 填缝 + dilate(7) 外扩（与 Fast 对齐）
    kclose = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (CLOSE_K, CLOSE_K))
    merged_final = cv2.morphologyEx(merged, cv2.MORPH_CLOSE, kclose)
    if EXPAND_PX > 0:
        kexp = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (EXPAND_PX*2+1, EXPAND_PX*2+1))
        merged_final = cv2.dilate(merged_final, kexp, iterations=1)

    # Final = Red(SAM) ∪ Green(Fast)
    union = cv2.bitwise_or(merged_final, fast)
    # 轻微 erode 吃边缘薄阴影
    ke = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ERODE_K, ERODE_K))
    union_e = cv2.erode(union, ke, iterations=1)

    # 用 merged_contour 取轮廓（全组件并集+close9桥接，防多连通域断裂）
    def merged_contour(mask):
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if not cnts: return None
        umask = np.zeros_like(mask)
        cv2.drawContours(umask, cnts, -1, 255, -1)
        kb = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        umask = cv2.morphologyEx(umask, cv2.MORPH_CLOSE, kb)
        fcs, _ = cv2.findContours(umask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        return max(fcs, key=cv2.contourArea) if fcs else None

    union_cnt = merged_contour(union_e)
    if union_cnt is None: continue
    pts_chaikin = chaikin_smooth(union_cnt, passes=2)

    # ✅ 方案B：自适应抽稀 + 基元化（直接吃 Chaikin 稠密点，直线坍2点 / 弧保密度）
    primitives = classify_and_fit_fixed(pts_chaikin, curv_thresh=0.025, max_radius=150)
    print(f"           原始: {len(union_cnt)} | Chaikin: {len(pts_chaikin)} | "
          f"基元数: {len(primitives)}")

    # 统计
    n_pts_chaikin = len(pts_chaikin)
    n_primitives = len(primitives)
    n_line = sum(1 for p in primitives if p[0]=='LINE')
    n_arc = sum(1 for p in primitives if p[0]=='ARC')

    print(f"{name:14} | Chaikin 点: {n_pts_chaikin:>5} | 基元数: {n_primitives:>3} "
          f"(直线 {n_line}, 圆弧 {n_arc})")

    # ============ 量化校验：重建轮廓 vs 原始 Chaikin ============
    recon_verts = []
    for typ, data, _ in primitives:
        if typ == 'LINE':
            p0, p1 = data
            if not recon_verts:
                recon_verts.append(p0)
            recon_verts.append(p1)
        else:  # ARC
            cx, cy, r, a0, a1 = data
            n_arc = max(12, int(abs(a1 - a0) / 3))
            angles = np.linspace(a0, a1, n_arc)
            arc_v = np.stack([cx + r*np.cos(np.radians(angles)),
                              cy + r*np.sin(np.radians(angles))], axis=1)
            if recon_verts and np.linalg.norm(np.array(recon_verts[-1]) - arc_v[0]) < 8:
                recon_verts.extend(arc_v[1:].tolist())
            else:
                recon_verts.extend(arc_v.tolist())

    recon_arr = np.array(recon_verts, dtype=np.int32).reshape(-1, 1, 2)
    chaikin_arr = pts_chaikin.astype(np.int32).reshape(-1, 1, 2)

    mask_ch = np.zeros((h, w), np.uint8)
    mask_rc = np.zeros((h, w), np.uint8)
    cv2.fillPoly(mask_ch, [chaikin_arr], 255)
    cv2.fillPoly(mask_rc, [recon_arr], 255)

    inter_mask = cv2.bitwise_and(mask_ch, mask_rc)
    union_mask = cv2.bitwise_or(mask_ch, mask_rc)
    inter_px = int(inter_mask.sum() / 255)
    union_px = int(union_mask.sum() / 255)
    iou = inter_px / max(union_px, 1)
    print(f"           重绘 vs Chaikin IoU: {iou:.4f}  (inter={inter_px} union={union_px})")

    # 导出基元 JSON（下游 STL/STEP 直接用）
    prims_json = []
    for typ, data, _ in primitives:
        if typ == 'LINE':
            p0, p1 = data
            prims_json.append({"type": "line", "p0": p0.tolist(), "p1": p1.tolist()})
        else:
            cx, cy, r, a0, a1 = data
            prims_json.append({"type": "arc", "center": [cx, cy], "radius": r,
                               "angle_start": a0, "angle_end": a1})
    import json
    with open(os.path.join(OUT, f"primitives_{name}.json"), 'w') as f:
        json.dump(prims_json, f, indent=2)
    print(f"           -> primitives_{name}.json ({len(prims_json)}基元)")

    # ============ 可视化 ============
    vis = warped.copy()

    # 1. Chaikin 原轮廓（淡蓝）
    cv2.drawContours(vis, [pts_chaikin.astype(np.int32).reshape(-1,1,2)], -1, (255,200,200), 1)

    # 2. 基元重绘（红=直线，橙=圆弧）
    for typ, data, seg_pts in primitives:
        if typ == 'LINE':
            p0, p1 = data
            cv2.line(vis, tuple(p0.astype(int)), tuple(p1.astype(int)), (0,0,255), 2)
        else:
            cx, cy, r, a0, a1 = data
            start_angle = a0 if a0 <= a1 else a0 - 360
            end_angle = a1
            cv2.ellipse(vis, (int(cx),int(cy)), (int(r),int(r)), 0,
                        start_angle, end_angle, (0,120,255), 2)

    cv2.putText(vis,
                f"Chaikin: {n_pts_chaikin}pts → 基元: {n_primitives}(L{n_line}/A{n_arc})",
                (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 2)
    cv2.imwrite(os.path.join(OUT, f"abstract_{name}.png"), vis)
    print(f"  -> abstract_{name}.png")

print("\n✅ 基元化完成。")
