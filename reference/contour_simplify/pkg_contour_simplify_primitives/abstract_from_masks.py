# -*- coding: utf-8 -*-
"""
用已保存的 Fast / SAM-box 掩膜重建并集（无需 torch），验证方案B基元化在真实工具轮廓上的效果。
掩膜: _fast_<name>.png + _sambox_<name>.png  (warped 对齐, 1200x848)
"""
import numpy as np
import cv2, os, sys, json

OUT = "C:/Users/tlyth/WorkBuddy/2026-07-07-14-40-46"
sys.path.insert(0, OUT)
from repro_contour_v9 import detect_paper_battery

# ---------- 工具函数（与 abstract_primitive.py 完全一致，方案B 验证版）----------
def largest_contour(mask):
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    return max(cnts, key=cv2.contourArea) if cnts else None

def chaikin_smooth(contour, passes=2):
    pts = contour.reshape(-1, 2).astype(np.float64)
    for _ in range(passes):
        new_pts, n = [], len(pts)
        for i in range(n):
            p1, p2 = pts[i], pts[(i+1) % n]
            new_pts.append(p1 * 0.75 + p2 * 0.25)
            new_pts.append(p1 * 0.25 + p2 * 0.75)
        pts = np.array(new_pts, dtype=np.float64)
    return pts

def fit_arc_b(pts, max_radius=200):
    if len(pts) < 5:
        return None
    pts32 = pts.astype(np.float32)
    try:
        (cx, cy), (rax, ray), ang = cv2.fitEllipse(pts32)
    except Exception:
        return None
    cx, cy = float(cx), float(cy)
    rmin, rmaj = sorted([rax, ray])
    radius = (rax + ray) / 4.0
    if rmaj > 1e-3 and (rmaj - rmin) / rmaj > 0.25:
        return None
    if radius < 5.0 or radius > max_radius:
        return None
    theta = np.arctan2(pts[:, 1]-cy, pts[:, 0]-cx)
    theta_u = np.unwrap(theta)
    a0 = float(np.degrees(theta_u[0]))
    a1 = float(np.degrees(theta_u[-1]))
    span = abs(a1 - a0)
    if span < 20 or span > 180:
        return None
    dists = np.abs(np.linalg.norm(pts - np.array([cx, cy]), axis=1) - radius)
    mean_err = np.mean(dists)
    max_error = 2.0 + (span - 20) / 30.0
    if mean_err > max_error:
        return None
    n = max(8, int(span / 5))
    angles = np.linspace(a0, a1, n)
    arc_pts = np.stack([cx + radius*np.cos(np.radians(angles)),
                        cy + radius*np.sin(np.radians(angles))], axis=1)
    return ('ARC', (cx, cy, radius, a0, a1), arc_pts)

def adaptive_rdp(pts, segment_flags, min_arc_len=5):
    n = len(pts)
    if n < 3:
        return [('LINE', pts)]
    segs = []; i = 0
    while i < n:
        if segment_flags[i]:
            s = i
            while i < n and segment_flags[i]:
                i += 1
            arc = pts[s:i]
            if len(arc) >= min_arc_len:
                segs.append(('ARC_CAND', arc))
            elif len(arc) >= 2:
                segs.append(('LINE', np.array([arc[0], arc[-1]])))
        else:
            s = i
            while i < n and not segment_flags[i]:
                i += 1
            line = pts[s:i]
            if len(line) >= 2:
                segs.append(('LINE', np.array([line[0], line[-1]])))
    return segs

def classify_and_fit_fixed(pts_chaikin, curv_thresh=0.025, max_radius=150, dil_k=1):
    pts = np.asarray(pts_chaikin, dtype=np.float64)
    n = len(pts)
    if n < 4:
        return [('LINE', (pts[0], pts[-1]), pts)]
    curvature = np.zeros(n)
    for i in range(1, n - 1):
        v1 = pts[i] - pts[i-1]; v2 = pts[i+1] - pts[i]
        L1 = np.linalg.norm(v1); L2 = np.linalg.norm(v2)
        if L1 > 1e-6 and L2 > 1e-6:
            cos_t = np.clip(np.dot(v1, v2) / (L1 * L2), -1.0, 1.0)
            curvature[i] = np.sin(np.arccos(cos_t))
    is_arc = (curvature > curv_thresh)
    is_arc = np.convolve(is_arc.astype(int), np.ones(3), mode='same') >= 2
    if dil_k > 1:
        is_arc = np.convolve(is_arc.astype(int), np.ones(dil_k), mode='same') >= 1
    is_arc = is_arc.astype(bool)
    segs = adaptive_rdp(pts, is_arc, min_arc_len=5)
    prims = []
    for typ, seg in segs:
        if typ == 'LINE':
            prims.append(('LINE', (seg[0], seg[-1]), seg))
        else:
            arc = fit_arc_b(seg, max_radius=max_radius)
            if arc is not None:
                prims.append(arc)
            else:
                prims.append(('LINE', (seg[0], seg[-1]), seg))
    return prims

def merged_contour(mask):
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return None
    umask = np.zeros_like(mask)
    cv2.drawContours(umask, cnts, -1, 255, -1)
    kb = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    umask = cv2.morphologyEx(umask, cv2.MORPH_CLOSE, kb)
    fcs, _ = cv2.findContours(umask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    return max(fcs, key=cv2.contourArea) if fcs else None

# ---------- 参数（与 sam_union_final.py 一致）----------
CLOSE_K, EXPAND_PX, ERODE_K = 9, 7, 3

tests = [("test_cal.jpg", "calipers"),
         ("test_03.jpg", "hexkey_shadow"),
         ("test_05.jpg", "pliers")]

for fname, name in tests:
    fast = cv2.imread(os.path.join(OUT, f"_fast_{name}.png"), cv2.IMREAD_GRAYSCALE)
    sambox = cv2.imread(os.path.join(OUT, f"_sambox_{name}.png"), cv2.IMREAD_GRAYSCALE)
    if fast is None or sambox is None:
        print(f"[skip] {name}: 缺掩膜"); continue
    fast = (fast > 127).astype(np.uint8) * 255
    merged = (sambox > 127).astype(np.uint8) * 255
    h, w = merged.shape

    # 并集管线（同 abstract_primitive.py）
    kclose = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (CLOSE_K, CLOSE_K))
    merged_final = cv2.morphologyEx(merged, cv2.MORPH_CLOSE, kclose)
    if EXPAND_PX > 0:
        kexp = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (EXPAND_PX*2+1, EXPAND_PX*2+1))
        merged_final = cv2.dilate(merged_final, kexp, iterations=1)
    union = cv2.bitwise_or(merged_final, fast)
    ke = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ERODE_K, ERODE_K))
    union_e = cv2.erode(union, ke, iterations=1)

    union_cnt = merged_contour(union_e)
    if union_cnt is None:
        print(f"[skip] {name}: 无轮廓"); continue
    pts_chaikin = chaikin_smooth(union_cnt, passes=2)

    primitives = classify_and_fit_fixed(pts_chaikin, curv_thresh=0.025, max_radius=150)
    n_pts = len(pts_chaikin)
    n_pr = len(primitives)
    n_line = sum(1 for p in primitives if p[0] == 'LINE')
    n_arc = sum(1 for p in primitives if p[0] == 'ARC')
    # ---- 曲率诊断 ----
    curv = np.zeros(n_pts)
    for i in range(1, n_pts-1):
        v1 = pts_chaikin[i]-pts_chaikin[i-1]; v2 = pts_chaikin[i+1]-pts_chaikin[i]
        L1 = np.linalg.norm(v1); L2 = np.linalg.norm(v2)
        if L1>1e-6 and L2>1e-6:
            curv[i] = np.sin(np.arccos(np.clip(np.dot(v1,v2)/(L1*L2),-1,1)))
    is_arc = (curv > 0.025).astype(int)
    is_arc_e = np.convolve(is_arc, np.ones(3), mode='same') >= 2
    n_raw = int(is_arc.sum()); n_ero = int(is_arc_e.sum())
    print(f"{name:14} | Chaikin: {n_pts:>5} | 基元: {n_pr:>3} (直线 {n_line}, 圆弧 {n_arc})")
    print(f"           曲率: max={curv.max():.4f} >0.025点={n_raw} 腐蚀后={n_ero}")
    # 逐段尝试拟合，看为何被拒
    if n_ero > 0:
        segs = adaptive_rdp(pts_chaikin, is_arc_e.astype(bool), min_arc_len=5)
        for t, s in segs:
            if t == 'ARC_CAND':
                r = fit_arc_b(s, max_radius=150)
                if r is None:
                    # 诊断
                    try:
                        (cx,cy),(rax,ray),_ = cv2.fitEllipse(s.astype(np.float32))
                        rad=(rax+ray)/4; rr=abs(max(rax,ray)-min(rax,ray))/max(rax,ray)
                        th=np.arctan2(s[:,1]-cy,s[:,0]-cx); tu=np.unwrap(th)
                        sp=abs(np.degrees(tu[-1])-np.degrees(tu[0]))
                        print(f"             ARC_CAND n={len(s)} -> 拒: r={rad:.1f} 圆度={rr:.2f} span={sp:.1f}")
                    except Exception as e:
                        print(f"             ARC_CAND n={len(s)} -> fitEllipse err {e!r}")
                else:
                    print(f"             ARC_CAND n={len(s)} -> OK r={r[1][2]:.1f}")

    # 弧半径统计
    arcs = [(p[1][2], p[1][3], p[1][4]) for p in primitives if p[0] == 'ARC']
    if arcs:
        rs = [a[0] for a in arcs]
        print(f"           弧半径: min={min(rs):.1f} max={max(rs):.1f} mean={np.mean(rs):.1f}  (n={len(rs)})")

    # 重建 + IoU
    recon = []
    for typ, data, _ in primitives:
        if typ == 'LINE':
            p0, p1 = data
            if not recon: recon.append(p0)
            recon.append(p1)
        else:
            cx, cy, r, a0, a1 = data
            na = max(40, int(abs(a1-a0)/2))
            ang = np.linspace(a0, a1, na)
            av = np.stack([cx+r*np.cos(np.radians(ang)), cy+r*np.sin(np.radians(ang))], axis=1)
            if recon and np.linalg.norm(np.array(recon[-1])-av[0]) < 10:
                recon.extend(av[1:].tolist())
            else:
                recon.extend(av.tolist())
    recon_arr = np.array(recon, np.int32).reshape(-1, 1, 2)
    chaikin_arr = pts_chaikin.astype(np.int32).reshape(-1, 1, 2)
    m_ch = np.zeros((h, w), np.uint8); m_rc = np.zeros((h, w), np.uint8)
    cv2.fillPoly(m_ch, [chaikin_arr], 255); cv2.fillPoly(m_rc, [recon_arr], 255)
    inter = int((cv2.bitwise_and(m_ch, m_rc)).sum()/255)
    uni = int((cv2.bitwise_or(m_ch, m_rc)).sum()/255)
    print(f"           重绘 vs Chaikin IoU: {inter/max(uni,1):.4f}")

    # JSON
    pj = []
    for typ, data, _ in primitives:
        if typ == 'LINE':
            p0, p1 = data
            pj.append({"type": "line", "p0": p0.tolist(), "p1": p1.tolist()})
        else:
            cx, cy, r, a0, a1 = data
            pj.append({"type": "arc", "center": [cx, cy], "radius": r,
                       "angle_start": a0, "angle_end": a1})
    with open(os.path.join(OUT, f"primitives_{name}.json"), 'w') as f:
        json.dump(pj, f, indent=2)

    # 可视化
    img = cv2.imread(os.path.join(OUT, fname))
    warped = detect_paper_battery(img)
    base = warped if warped is not None else np.zeros((h, w, 3), np.uint8)
    vis = np.ascontiguousarray(base, dtype=np.uint8).copy()
    cv2.drawContours(vis, [pts_chaikin.astype(np.int32).reshape(-1, 1, 2)], -1, (255, 200, 200), 1)
    for typ, data, seg in primitives:
        if typ == 'LINE':
            p0, p1 = data
            cv2.line(vis, tuple(p0.astype(int)), tuple(p1.astype(int)), (0, 0, 255), 2)
        else:
            cx, cy, r, a0, a1 = data
            sa = a0 if a0 <= a1 else a0 - 360
            cv2.ellipse(vis, (int(cx), int(cy)), (int(r), int(r)), 0, sa, a1, (0, 120, 255), 2)
    cv2.putText(vis, f"Chaikin:{n_pts} -> 基元:{n_pr}(L{n_line}/A{n_arc})",
                (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
    cv2.imwrite(os.path.join(OUT, f"abstract_{name}.png"), vis)
    print(f"  -> abstract_{name}.png  primitives_{name}.json")

print("\n✅ 基元化完成（基于已保存掩膜重建并集，无 torch）。")
