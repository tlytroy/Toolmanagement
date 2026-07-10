"""
轮廓抽稀 + 基元化（改进版）
流程：
1. HSV 提取红色轮廓（带面积过滤去噪）
2. Douglas-Peucker 抽稀得到拐点顶点
3. 在相邻拐点之间的原始稠密点段上，逐段拟合「直线」或「圆弧」，
   取均方误差更小者作为该段的基元
4. 可视化：直线用绿线、圆弧用橙色真实椭圆弧绘制
"""

import cv2
import numpy as np
import os

# ── 路径 ───────────────────────────────────────────
WORKSPACE = r"C:\Users\tlyth\WorkBuddy\2026-07-08-18-46-14"
IMG_PATH = os.path.join(WORKSPACE, "demo.png")

img = cv2.imread(IMG_PATH)
if img is None:
    raise FileNotFoundError(f"无法读取图片: {IMG_PATH}")
h, w = img.shape[:2]
print(f"图像尺寸: {w}x{h}")

# ══════════════════════════════════════════════════
# 1. 提取红色轮廓
# ══════════════════════════════════════════════════
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
# 红色两段
lower1, upper1 = np.array([0, 70, 70]), np.array([12, 255, 255])
lower2, upper2 = np.array([160, 70, 70]), np.array([180, 255, 255])
red_mask = cv2.inRange(hsv, lower1, upper1) | cv2.inRange(hsv, lower2, upper2)

# 去噪：先高斯模糊抑制椒盐噪点，再闭运算连接断裂
red_mask = cv2.GaussianBlur(red_mask, (5, 5), 0)
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel, iterations=3)

contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
contours = [c for c in contours if cv2.contourArea(c) > 2000]   # 过滤小噪块
if not contours:
    raise ValueError("未找到红色轮廓")
contour = max(contours, key=cv2.contourArea)
print(f"原始轮廓点数: {len(contour)}  面积: {cv2.contourArea(contour):.0f}")

# ══════════════════════════════════════════════════
# 2. DP 抽稀（找拐点）
# ══════════════════════════════════════════════════
def dp_simplify(c, eps_ratio):
    peri = cv2.arcLength(c, closed=True)
    return cv2.approxPolyDP(c, eps_ratio * peri, closed=True)

# 多级展示用
levels = [0.001, 0.004, 0.015]
simplifs = {f"{e:.3f}": dp_simplify(contour, e) for e in levels}

# 用于基元化：选一个能保留弧段拐点的中等精度
EPS = 0.004
verts = dp_simplify(contour, EPS).reshape(-1, 2).astype(np.float64)
N = len(verts)
print(f"DP ε={EPS}: {N} 个拐点")

# ══════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════
def line_fit_error(pts):
    """点到最小二乘直线的最大垂直距离（均方根）"""
    if len(pts) < 2:
        return 1e9
    lp = cv2.fitLine(pts, cv2.DIST_L2, 0, 0.01, 0.01)
    vx, vy = float(lp[0][0]), float(lp[1][0])
    n = np.array([vx, vy]) / (np.hypot(vx, vy) + 1e-9)
    v0 = pts[0]
    d = np.abs((pts - v0) @ np.array([-n[1], n[0]]))   # 垂直距离
    return np.sqrt(np.mean(d**2))


def circle_fit(pts):
    """代数最小二乘圆拟合，返回 (cx,cy,r) 或 None"""
    if len(pts) < 3:
        return None
    xs, ys = pts[:, 0].astype(float), pts[:, 1].astype(float)
    A = np.column_stack([xs, ys, np.ones_like(xs)])
    b = -(xs**2 + ys**2)
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    a, bb, c = sol
    cx, cy = -a / 2.0, -bb / 2.0
    r = np.sqrt(max(cx**2 + cy**2 - c, 1e-6))
    return cx, cy, r


def circle_fit_error(pts, circle):
    cx, cy, r = circle
    d = np.hypot(pts[:, 0] - cx, pts[:, 1] - cy)
    return np.sqrt(np.mean((d - r) ** 2))


# 建立 原始稠密点 沿轮廓的顺序索引，用于取两拐点之间的点
# contour 是 CHAIN_APPROX_NONE，顺序即轮廓顺序
dense = contour.reshape(-1, 2).astype(np.float64)

# 把每个 DP 顶点映射回它在 dense 中的真实索引（DP 顶点是 dense 的子集点）
def nearest_dense_index(pt):
    d = np.sum((dense - pt) ** 2, axis=1)
    return int(np.argmin(d))

vert_idx = [nearest_dense_index(v) for v in verts]


def points_between(i, j):
    """取轮廓上从顶点 i 到顶点 j（顺时针）之间的稠密点"""
    a, b = vert_idx[i], vert_idx[j]
    if b >= a:
        return dense[a:b + 1]
    else:  # 跨越首尾
        return np.vstack([dense[a:], dense[:b + 1]])


# ══════════════════════════════════════════════════
# 3. 逐段基元化：直线 vs 圆弧
# ══════════════════════════════════════════════════
primitives = []   # {'type':'line'|'arc'|'polyline', ...}
LIN_TOL  = 4.0      # 直线均方误差容忍
ARC_TOL  = 4.0      # 圆弧径向误差容忍
MAX_ARC_RADIUS = 55   # 半径超过此值视为"缓弯"，退化为折线

for k in range(N):
    i, j = k, (k + 1) % N
    seg = points_between(i, j)
    p0 = tuple(map(int, verts[i]))
    p1 = tuple(map(int, verts[j]))

    err_l = line_fit_error(seg)
    circ = circle_fit(seg)
    err_c = circle_fit_error(seg, circ) if circ else 1e9

    # 判定：圆弧拟合显著优于直线？
    is_arc_better = (err_c < err_l) and (err_c < ARC_TOL) and (err_l > LIN_TOL)

    if is_arc_better:
        cx, cy, r = circ
        if r <= MAX_ARC_RADIUS:
            # 真正的弧（曲率足够大）
            primitives.append({
                'type': 'arc', 'p0': p0, 'p1': p1,
                'center': (cx, cy), 'radius': r, 'seg_pts': seg,
            })
        else:
            # 大半径缓弯 → 退化为折线（对段内点做细粒度 DP）
            sub_eps = 0.002 * cv2.arcLength(contour, closed=True)
            poly_approx = cv2.approxPolyDP(
                seg.reshape(-1, 1, 2).astype(np.int32), sub_eps, closed=False
            ).reshape(-1, 2)
            pts_list = [tuple(map(int, pt)) for pt in poly_approx]
            primitives.append({
                'type': 'polyline', 'points': pts_list,
            })
    else:
        primitives.append({'type': 'line', 'p0': p0, 'p1': p1})

n_line = sum(p['type'] == 'line' for p in primitives)
n_arc  = sum(p['type'] == 'arc' for p in primitives)
n_poly = sum(p['type'] == 'polyline' for p in primitives)
print(f"基元化结果: {len(primitives)} 段  (直线 {n_line} / 圆弧 {n_arc} / 折线 {n_poly})")


# ══════════════════════════════════════════════════
# 4. 可视化
# ══════════════════════════════════════════════════
def draw_arc(img, center, r, seg_pts, color, thick):
    cx, cy = center
    # 用实际点角度展开得到扫掠方向，避免画成优弧
    ang = np.unwrap(np.arctan2(seg_pts[:, 1] - cy, seg_pts[:, 0] - cx))
    a0 = float(np.degrees(ang[0]))
    a1 = a0 + float(np.degrees(ang[-1] - ang[0]))
    cv2.ellipse(img, (int(round(cx)), int(round(cy))),
                (int(round(r)), int(round(r))), 0, a0, a1, color, thick)

# (A) 原始 + 红轮廓
vis_a = img.copy()
cv2.drawContours(vis_a, [contour], -1, (0, 0, 255), 2)

# (B) DP 拐点多边形（三种精度叠加）
vis_b = img.copy()
for e, col in zip(levels, [(0, 255, 0), (255, 165, 0), (0, 165, 255)]):
    cv2.drawContours(vis_b, [simplifs[f"{e:.3f}"]], -1, col, 2)

# (C) 基元纯净图（白底）
vis_c = np.ones_like(img) * 250
cv2.drawContours(vis_c, [contour], -1, (210, 210, 210), 1)  # 参考灰轮廓
for p in primitives:
    if p['type'] == 'line':
        cv2.line(vis_c, p['p0'], p['p1'], (0, 150, 0), 3)
    elif p['type'] == 'arc':
        draw_arc(vis_c, p['center'], p['radius'], p['seg_pts'], (0, 140, 255), 3)
    elif p['type'] == 'polyline':
        pts = np.array(p['points'], dtype=np.int32)
        cv2.polylines(vis_c, [pts], False, (100, 60, 200), 2)
# 拐点
for v in verts:
    cv2.circle(vis_c, tuple(map(int, v)), 4, (20, 20, 20), -1)

# (D) 基元叠加原图（线条细化，不遮挡原始轮廓）
vis_d = img.copy()
for p in primitives:
    if p['type'] == 'line':
        cv2.line(vis_d, p['p0'], p['p1'], (0, 255, 0), 1)
    elif p['type'] == 'arc':
        draw_arc(vis_d, p['center'], p['radius'], p['seg_pts'], (0, 165, 255), 1)
    elif p['type'] == 'polyline':
        pts = np.array(p['points'], dtype=np.int32)
        cv2.polylines(vis_d, [pts], False, (180, 80, 220), 1)

# 拼接 2x2
pad = 24
ch, cw = h + pad, w + pad
canvas = np.ones((ch * 2, cw * 2, 3), np.uint8) * 245
panels = [(vis_a, 0, 0, f"Red Contour ({len(contour)} pts)"),
          (vis_b, 0, 1, "DP simplification (3 eps)"),
          (vis_c, 1, 0, f"Primitives: {n_line}L / {n_arc}A / {n_poly}P"),
          (vis_d, 1, 1, "Primitives overlaid")]
for panel, r, c, title in panels:
    y0, x0 = r * ch + pad // 2, c * cw + pad // 2
    canvas[y0:y0 + h, x0:x0 + w] = panel
    cv2.putText(canvas, title, (x0, y0 - 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (30, 30, 30), 2)

out = os.path.join(WORKSPACE, "contour_primitives_v2.png")
cv2.imwrite(out, canvas)
cv2.imwrite(os.path.join(WORKSPACE, "primitives_clean.png"), vis_c)
print(f"✅ 已保存: {out}")
