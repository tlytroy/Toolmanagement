"""
优化 SAM(终极版): 合并"属于工具"的所有 SAM 子 mask -> 完整覆盖 + 干净边界。
根因: SAM 把多材质工具当多个独立物体, 单 prompt 只吐最大块(蓝塑料)。
解法: automatic 模式(points_per_side=16 提速)拿到全部候选 mask,
      保留与 Fast 工具区重叠的子 mask 并合并 -> 蓝+金属+黑 全盖, 边界干净。
"""
import cv2, numpy as np, os, sys, time

OUT = "C:/Users/tlyth/WorkBuddy/2026-07-07-14-40-46"
sys.path.insert(0, OUT)
from repro_contour_v9 import (
    detect_paper_battery, extract_tool_contour_v9,
    smooth_closed_spline,          # 复用 Fast 的高斯平滑样条
)
import torch
from segment_anything import sam_model_registry, SamAutomaticMaskGenerator, SamPredictor

CKPT = os.path.join(OUT, "sam_vit_b_01ec64.pth")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[SAM] loading vit_b on {DEVICE} ...")
sam = sam_model_registry["vit_b"](checkpoint=CKPT).to(DEVICE)
mask_gen = SamAutomaticMaskGenerator(
    sam,
    points_per_side=16,          # 密度降到16, 256点/张, 比32(1024点)快4倍
    pred_iou_thresh=0.80,
    stability_score_thresh=0.85,
    crop_n_layers=0,             # 关掉多尺度crop, 进一步提速
    min_mask_region_area=300,
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
    """取最大外轮廓 (单连通域场景)"""
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    return max(cnts, key=cv2.contourArea) if cnts else None


def merged_contour(mask):
    """取所有外部轮廓的并集再提外边界 (修复多连通域断裂问题)。
    SAM 合并后可能因局部缺口(如卡尺锁紧螺丝处)导致 mask 断成多个连通域,
    largest_contour 只会丢掉面积较小的组件(如尺身)。
    此函数把所有外部轮廓都画到 union_mask 再统一提取, 保证不丢组件。
    """
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return None
    # 所有外部轮廓填充 → 统一 mask
    union_mask = np.zeros_like(mask)
    cv2.drawContours(union_mask, cnts, -1, 255, -1)
    # 用稍大的 close 核桥接近邻组件 (处理 <=8px 的断裂)
    kbridge = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    union_mask = cv2.morphologyEx(union_mask, cv2.MORPH_CLOSE, kbridge)
    # 从桥接后的 mask 提最大轮廓
    final_cnts, _ = cv2.findContours(union_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    return max(final_cnts, key=cv2.contourArea) if final_cnts else None


# ===== 阴影拒识几何阈值(简化版, 不依赖灰度/饱和度) =====
SHADOW_DIST = 25        # 候选 mask 到工具距离 >25px → 拒(远处阴影/独立物体)
SHADOW_AREA = 200       # 候选 mask 面积 <200px → 拒(噪声/阴影碎片)


def is_shadow_mask_simple(seg, tool_cnt, tool_dist_map):
    """
    简化版阴影拒识: 仅用最鲁棒的「几何特征」, 不靠灰度/饱和度(不同光照不稳定)。
    返回 True=应拒绝(是阴影/噪声)。
      1) 质心在 Fast 工具轮廓内部 -> 一定是工具(黑柄/金属均保), 返回 False
      2) 到工具最小距离 > SHADOW_DIST -> 远处独立物体/阴影, 拒绝
      3) 面积 < SHADOW_AREA -> 噪声/阴影碎片, 拒绝
      兜底: 保留
    """
    seg_sum = int(np.count_nonzero(seg))
    if seg_sum == 0:
        return True
    m = cv2.moments(seg)
    if m['m00'] == 0:
        return True
    cx = int(m['m10'] / m['m00'])
    cy = int(m['m01'] / m['m00'])

    # 1) 质心在工具轮廓内 -> 黑色工具本身, 必保
    if tool_cnt is not None:
        if cv2.pointPolygonTest(tool_cnt, (cx, cy), False) > 0:
            return False

    # 2) 到工具距离过远 -> 独立物体/远处阴影
    vals = tool_dist_map[seg > 0]
    min_dist = float(vals.min()) if vals.size else 999.0
    if min_dist > SHADOW_DIST:
        return True

    # 3) 面积太小 -> 噪声/阴影碎片
    if seg_sum < SHADOW_AREA:
        return True

    return False  # 兜底保留


tests = [("test_cal.jpg", "calipers"), ("test_03.jpg", "hexkey_shadow"), ("test_05.jpg", "pliers")]
print(f"{'name':14} {'mode':12} {'SAM_px':>9} {'SAM_%':>7} {'IoU':>6} {'TOP':>5} {'MID':>5} {'BOT':>5} {'+add':>8} {'t':>5}")
print("---  post(simplified): merge → close(9,9) → merged_contour(union+bridge) → smooth(sigma=1.5) | shadow=geo")
print("-" * 72)

for fname, name in tests:
    img = cv2.imread(os.path.join(OUT, fname))
    warped = warp_image(img)
    if warped is None:
        print(f"{name:14} WARP_FAIL"); continue
    h, w = warped.shape[:2]
    union, dbg, raw_cnt, smooth_cnt = extract_tool_contour_v9(warped, debug=False)
    fast = np.zeros((h, w), np.uint8)
    if raw_cnt is not None:
        cv2.drawContours(fast, [raw_cnt], -1, 255, -1)
    fast_f = fast > 0
    fast_px = int(np.count_nonzero(fast))
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY) if len(warped.shape) == 3 else warped.copy()
    # Fast 锚框(v9 内部已剥阴影)是可靠的几何锚: 黑色工具/金属均被其覆盖
    fast_cnt = largest_contour(fast)
    # 到最近「工具像素」的距离图 (全图算一次, 合并循环内查询)
    tool_dist_map = cv2.distanceTransform((~fast).astype(np.uint8), cv2.DIST_L2, 5)

    t0 = time.time()
    masks = mask_gen.generate(warped)
    dt = time.time() - t0

    # 合并(几何门控): 候选 mask 必须"多数落在工具上"(overlap_ratio>0.5) 且"非阴影"才并入。
    #   overlap_ratio = 候选落在工具上的像素 / 候选总面积。
    #   这是鲁棒的几何判据, 不靠灰度/饱和度(不同光照不稳定):
    #     工具部件 ≈ 100% 在工具上 → 保留;  A4纸 / 阴影 << 50% → 自动剔除。
    #   不再调 IoU 阈值(易误杀), 不再用 hull-patch(引入的不确定比修的缝多)。
    AREA_MIN = 100           # 候选 mask 最小面积(噪声过滤)
    OVERLAP_MIN = 0.5        # 候选"落在工具上的比例">50% 才视为工具部件(几何, 鲁棒)
    CLOSE_K = 9              # 闭运算核(9×9椭圆): 桥接 SAM 子 mask 间 <=8px 的断裂缺口
                             # (卡尺头/尺身间距 ~5px, close(5)的椭圆有效半径~2px不够)
    EXPAND_PX = 7            # 外扩余量(对齐 Fast 档 dilate_px=7): 让 SAM 轮廓像 Fast 一样
                             # 向外扩 7px, 便于放工具(不紧贴), 而非"贴肉"轮廓

    merged = np.zeros((h, w), np.uint8)
    kept = 0
    rejected = []            # 诊断: 被拒的 mask 信息
    for mi, m in enumerate(masks):
        seg = m["segmentation"].astype(np.uint8) * 255
        seg_sum = int(np.count_nonzero(seg))
        if seg_sum < AREA_MIN:
            if name in ('hexkey_shadow', 'calipers'):
                rejected.append(f"[{mi}] area={seg_sum:<6} SKIP(area<{AREA_MIN})")
            continue
        inter = int(np.count_nonzero(cv2.bitwise_and(seg, fast)))
        if inter == 0:
            if name in ('hexkey_shadow', 'calipers'):
                rejected.append(f"[{mi}] area={seg_sum:<6} SKIP(no-overlap)")
            continue
        overlap_ratio = inter / seg_sum
        if overlap_ratio < OVERLAP_MIN:
            if name in ('hexkey_shadow', 'calipers'):
                rejected.append(f"[{mi}] area={seg_sum:<6} ovr={overlap_ratio:.2f} SKIP(<{OVERLAP_MIN})")
            continue
        # 阴影拒识(纯几何): 合并前拒绝"纯阴影"候选 mask, 保留黑色工具(质心在轮廓内)
        if is_shadow_mask_simple(seg, fast_cnt, tool_dist_map):
            if name in ('hexkey_shadow', 'calipers'):
                rejected.append(f"[{mi}] area={seg_sum:<6} SKIP(shadow-geo)")
            continue
        merged = cv2.bitwise_or(merged, seg)
        kept += 1

    # 诊断输出
    if name in ('hexkey_shadow', 'calipers') and rejected:
        print(f"  [DIAG] {name}: {len(rejected)} rejected of {len(masks)} total:")
        for r in rejected[:12]: print(f"          {r}")
        if len(rejected) > 12: print(f"          ... +{len(rejected)-12} more")
    # ===== 后处理流水线(简化: 合并 → 闭运算(5,5)一次 → 轮廓平滑) =====
    #   不做 hull-patch(引入的不确定比修的缝多); 不做 mask 高斯模糊(直接在轮廓点平滑);
    #   不做 dilate(放工具余量由 3D 打印 offset 承担, 0.3~0.5mm 吃掉 1~2px 边缘)
    kclose = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (CLOSE_K, CLOSE_K))
    merged_final = cv2.morphologyEx(merged, cv2.MORPH_CLOSE, kclose)
    # 外扩余量(对齐 Fast 档 dilate_px=7): 对合并+桥接后的 mask 做一次椭圆膨胀,
    # 让 SAM 轮廓向外扩 EXPAND_PX 像素, 与 Fast 的绿框余量一致, 便于放工具。
    if EXPAND_PX > 0:
        kexp = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (EXPAND_PX * 2 + 1, EXPAND_PX * 2 + 1))
        merged_final = cv2.dilate(merged_final, kexp, iterations=1)

    # ★ 无损诊断(仅测量, 不修改结果): 用「几何定义」找阴影区
    #   阴影 = 工具外侧的暗像素 (gray<160 且不在 fast 工具区内)
    #   若 final SAM 大量重叠该区域 → 阴影漏进 SAM; 若 fast 自身就重叠 → fast 含阴影
    dark_outside = (gray < 160) & (~fast_f)
    dark_outside_u8 = dark_outside.astype(np.uint8) * 255
    n_dark_outside = int(np.count_nonzero(dark_outside_u8))
    fast_self_shadow = int(np.count_nonzero(cv2.bitwise_and(fast, dark_outside_u8)))
    sam_leak = int(np.count_nonzero(cv2.bitwise_and(merged_final, dark_outside_u8)))
    if name in ('hexkey_shadow', 'calipers'):
        _sp = int(np.count_nonzero(merged_final))
        print(f"  [LEAK-CHECK] dark_outside={n_dark_outside}px  fast_self_shadow={fast_self_shadow}px  "
              f"SAM∩shadow={sam_leak}px ({sam_leak/_sp*100:.1f}% of SAM)")

    dt = time.time() - t0

    sp = int(np.count_nonzero(merged_final))
    inter2 = int(np.count_nonzero(cv2.bitwise_and(fast, merged_final)))
    uni2 = int(np.count_nonzero(cv2.bitwise_or(fast, merged_final)))
    iou = inter2 / uni2 * 100 if uni2 else 0
    added = int(np.count_nonzero(cv2.bitwise_and(merged_final, cv2.bitwise_not(fast))))  # SAM 比 Fast 多盖的像素
    bands = []
    for ya, yb in [(0, h//3), (h//3, 2*h//3), (2*h//3, h)]:
        fp = int(np.count_nonzero(fast[ya:yb])); spb = int(np.count_nonzero(merged_final[ya:yb]))
        bands.append(f"{spb/fp*100:4.0f}%" if fp else "  - ")
    print(f"{name:14} {'merge':12} {sp:>9} {sp/(h*w)*100:>6.1f}% {iou:>5.1f}%  " + " ".join(bands) + f" {added:>8} {dt:4.1f}s")

    # 可视化: 用 merged_contour (全组件并集+桥接) 代替 largest_contour (防断裂丢组件)
    raw_cnt = merged_contour(merged_final)
    # 轮廓点平滑 (sigma=1.5): 直线段保持直线, 只有真实拐角才圆润
    sam_smooth = None
    if raw_cnt is not None and len(raw_cnt) > 4:
        pts_flat = raw_cnt.reshape(-1, 2).astype(np.float64)
        sam_smooth = smooth_closed_spline(pts_flat, sigma=1.5)

    vis = warped.copy()
    ov = vis.copy(); ov[merged_final > 0] = (255, 120, 0)
    vis = cv2.addWeighted(ov, 0.40, vis, 0.60, 0)
    if smooth_cnt is not None:
        cv2.drawContours(vis, [smooth_cnt], -1, (0, 255, 0), 2)       # 绿 = Fast 平滑轮廓
    if raw_cnt is not None:
        cv2.drawContours(vis, [raw_cnt], -1, (100, 100, 255), 1)      # 淡蓝 = SAM 原始(有锯齿)
    if sam_smooth is not None:
        cv2.drawContours(vis, [sam_smooth], -1, (0, 80, 255), 2)        # 红/橙 = SAM 平滑后(已是对drawContours友好格式)
    cv2.putText(vis, f"MERGED-SAM | kept={kept}/{len(masks)} Fast={fast_px} SAM={sp} IoU={iou:.0f}%",
                (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
    cv2.imwrite(os.path.join(OUT, f"sam_{name}_merge.png"), vis)
    print(f"  -> sam_{name}_merge.png (kept {kept} of {len(masks)} masks)")

print("\n✅ merge done.")
