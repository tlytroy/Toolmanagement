"""
批量轮廓抽稀 + 基元化 v3
对多张图片统一处理：HSV红色提取 → DP抽稀 → 直线/圆弧/折线基元化
"""

import cv2
import numpy as np
import os

WORKSPACE = r"C:\Users\tlyth\WorkBuddy\2026-07-08-18-46-14"
IMAGES = [
    ("demo.png",              "caliper_v1"),
    ("back_chaikin_hex.png",  "hex_wrench"),
    ("back_chaikin_cal.png",  "caliper_v2"),
    ("back_chaikin_pli.png",  "pliers"),
]

# ══════════════════════════════════════════════════
# 工具函数（同 v3）
# ══════════════════════════════════════════════════
def dp_simplify(c, eps_ratio):
    return cv2.approxPolyDP(c, eps_ratio * cv2.arcLength(c, closed=True), closed=True)

def line_fit_error(pts):
    if len(pts) < 2: return 1e9
    lp = cv2.fitLine(pts, cv2.DIST_L2, 0, 0.01, 0.01)
    vx, vy = float(lp[0][0]), float(lp[1][0])
    n = np.array([vx, vy]) / (np.hypot(vx, vy) + 1e-9)
    d = np.abs((pts - pts[0]) @ np.array([-n[1], n[0]]))
    return np.sqrt(np.mean(d**2))

def circle_fit(pts):
    if len(pts) < 3: return None
    xs, ys = pts[:, 0].astype(float), pts[:, 1].astype(float)
    A = np.column_stack([xs, ys, np.ones_like(xs)])
    b = -(xs**2 + ys**2)
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    cx, cy = -sol[0]/2.0, -sol[1]/2.0
    r = np.sqrt(max(cx**2 + cy**2 - sol[2], 1e-6))
    return cx, cy, r

def circle_fit_error(pts, circ):
    cx, cy, r = circ
    return np.sqrt(np.mean((np.hypot(pts[:, 0]-cx, pts[:, 1]-cy) - r)**2))

def draw_arc(img, center, r, seg_pts, color, thick):
    cx, cy = center
    ang = np.unwrap(np.arctan2(seg_pts[:, 1] - cy, seg_pts[:, 0] - cx))
    a0 = float(np.degrees(ang[0]))
    a1 = a0 + float(np.degrees(ang[-1] - ang[0]))
    cv2.ellipse(img, (int(round(cx)), int(round(cy))),
                (int(round(r)), int(round(r))), 0, a0, a1, color, thick)


# 参数
EPS_DP      = 0.004
LIN_TOL     = 4.0
ARC_TOL     = 4.0
MAX_ARC_R   = 55
RED_THRESH  = 2000


def process_one(img_path, name):
    print(f"\n{'='*50}")
    print(f"处理: {name}  ({os.path.basename(img_path)})")
    print('='*50)

    img = cv2.imread(img_path)
    if img is None:
        print(f"❌ 无法读取 {img_path}")
        return

    h, w = img.shape[:2]
    print(f"尺寸: {w}x{h}")

    # ── 1. 提取红色轮廓 ──
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    m1 = cv2.inRange(hsv, np.array([0,70,70]), np.array([12,255,255]))
    m2 = cv2.inRange(hsv, np.array([160,70,70]), np.array([180,255,255]))
    red_mask = m1 | m2
    red_mask = cv2.GaussianBlur(red_mask, (5,5), 0)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5,5))
    red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, k, iterations=3)

    contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    contours = [c for c in contours if cv2.contourArea(c) > RED_THRESH]

    if not contours:
        print("⚠️ 未找到红色轮廓！尝试放宽阈值...")
        # fallback: 降低面积阈值
        contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        contours = [c for c in contours if cv2.contourArea(c) > 500]
        if not contours:
            print("❌ 仍然没有找到轮廓，跳过")
            return

    contour = max(contours, key=cv2.contourArea)
    print(f"原始轮廓点数: {len(contour)}  面积: {cv2.contourArea(contour):.0f}")

    # ── 2. DP 抽稀 ──
    verts = dp_simplify(contour, EPS_DP).reshape(-1, 2).astype(np.float64)
    N = len(verts)
    print(f"DP拐点: {N}")

    dense = contour.reshape(-1, 2).astype(np.float64)

    def nearest_dense_index(pt):
        return int(np.argmin(np.sum((dense - pt)**2, axis=1)))
    vert_idx = [nearest_dense_index(v) for v in verts]

    def points_between(i, j):
        a, b = vert_idx[i], vert_idx[j]
        return dense[a:b+1] if b >= a else np.vstack([dense[a:], dense[:b+1]])

    # ── 3. 基元化 ──
    primitives = []
    for k in range(N):
        i, j = k, (k+1) % N
        seg = points_between(i, j)
        p0 = tuple(map(int, verts[i])); p1 = tuple(map(int, verts[j]))

        err_l = line_fit_error(seg)
        circ = circle_fit(seg)
        err_c = circle_fit_error(seg, circ) if circ else 1e9

        is_arc_better = (err_c < err_l) and (err_c < ARC_TOL) and (err_l > LIN_TOL)

        if is_arc_better:
            cx, cy, r = circ
            if r <= MAX_ARC_R:
                primitives.append({'type':'arc', 'p0':p0, 'p1':p1,
                    'center':(cx,cy), 'radius':r, 'seg_pts':seg})
            else:
                sub_eps = 0.002 * cv2.arcLength(contour, closed=True)
                poly_approx = cv2.approxPolyDP(
                    seg.reshape(-1,1,2).astype(np.int32), sub_eps, closed=False).reshape(-1,2)
                primitives.append({'type':'polyline',
                    'points':[tuple(map(int,p)) for p in poly_approx]})
        else:
            primitives.append({'type':'line', 'p0':p0, 'p1':p1})

    n_line = sum(p['type']=='line' for p in primitives)
    n_arc  = sum(p['type']=='arc' for p in primitives)
    n_poly = sum(p['type']=='polyline' for p in primitives)
    print(f"基元: {n_line}L / {n_arc}A / {n_poly}P")

    # ── 4. 可视化 ──
    vis_a = img.copy()
    cv2.drawContours(vis_a, [contour], -1, (0,0,255), 2)

    # DP 多级叠加
    vis_b = img.copy()
    for e, col in zip([0.001, 0.004, 0.015],
                      [(0,255,0),(255,165,0),(0,165,255)]):
        cv2.drawContours(vis_b, [dp_simplify(contour,e)], -1, col, 2)

    # 纯净基元图
    vis_c = np.ones_like(img) * 250
    cv2.drawContours(vis_c, [contour], -1, (210,210,210), 1)
    for p in primitives:
        if p['type'] == 'line':
            cv2.line(vis_c, p['p0'], p['p1'], (0,150,0), 3)
        elif p['type'] == 'arc':
            draw_arc(vis_c, p['center'], p['radius'], p['seg_pts'], (0,140,255), 3)
        elif p['type'] == 'polyline':
            cv2.polylines(vis_c, [np.array(p['points'],np.int32)], False, (100,60,200), 2)
    for v in verts:
        cv2.circle(vis_c, tuple(map(int,v)), 4, (20,20,20), -1)

    # 叠加图（细线）
    vis_d = img.copy()
    for p in primitives:
        if p['type'] == 'line':
            cv2.line(vis_d, p['p0'], p['p1'], (0,255,0), 1)
        elif p['type'] == 'arc':
            draw_arc(vis_d, p['center'], p['radius'], p['seg_pts'], (0,165,255), 1)
        elif p['type'] == 'polyline':
            cv2.polylines(vis_d, [np.array(p['points'],np.int32)], False, (180,80,220), 1)

    # 拼接
    pad = 24; ch, cw = h+pad, w+pad
    canvas = np.ones((ch*2, cw*2, 3), np.uint8) * 245
    panels = [(vis_a,0,0,f"Red Contour ({len(contour)}pts)"),
              (vis_b,0,1,"DP Simplification"),
              (vis_c,1,0,f"Primitives: {n_line}L/{n_arc}A/{n_poly}P"),
              (vis_d,1,1,"Overlay (thin lines)")]
    for panel, r, c, title in panels:
        y0,x0 = r*ch+pad//2, c*cw+pad//2
        canvas[y0:y0+h, x0:x0+w] = panel
        cv2.putText(canvas, title, (x0, y0-6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (30,30,30), 2)

    out = os.path.join(WORKSPACE, f"result_{name}.png")
    clean = os.path.join(WORKSPACE, f"clean_{name}.png")
    cv2.imwrite(out, canvas)
    cv2.imwrite(clean, vis_c)
    print(f"✅ 已保存: {out}")


# ── 批量执行 ────────────────────────────────
for fname, name in IMAGES:
    path = os.path.join(WORKSPACE, fname)
    if os.path.exists(path):
        process_one(path, name)
    else:
        print(f"⚠️ 文件不存在: {path}")

print("\n全部完成 ✅")
