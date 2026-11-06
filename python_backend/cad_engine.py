"""
工具嵌件 3D 模型生成引擎
==========================
基于 trimesh + manifold3d 生成两种模式的嵌件基底：
  - Foam 模式：可自定义长宽高 + 圆角的方盒（支持堆叠槽位）
  - Gridfinity 模式：42mm 标准网格基底（带磁吸孔）

每个模式的基底上会布尔减去工具轮廓的拉伸体，形成工具槽。
"""

import numpy as np
import trimesh
import base64
from typing import List, Dict, Any, Optional, Tuple

try:
    from manifold3d import Manifold, Mesh as ManifoldMesh
    HAS_MANIFOLD = True
except ImportError:
    HAS_MANIFOLD = False

# 静默失败计数（0.8）：每个 except 分支都会往这里追加一条人类可读的原因。
# ★ 冻结文件，只允许「追加一行」；**不**改逻辑、**不**改返回值。
# 由调用方（main.py 的信封层）在每次请求前 clear()，请求后读走塞进 warnings[]。
errors: List[str] = []

# ── 常量 ─────────────────────────────────────────────
GRIDFINITY_PITCH = 42.0          # Gridfinity 标准网格间距 (mm)
GRIDFINITY_HOLE_DIA = 6.5        # 磁吸孔直径 (mm)
GRIDFINITY_HOLE_DEPTH = 2.5      # 磁吸孔深度 (mm)
GRIDFINITY_CORNER_R = 3.0        # Gridfinity 底板圆角 (mm)
GRIDFINITY_BASE_THICKNESS = 5.0  # Gridfinity 底板基础厚度 (mm)
GRIDFINITY_SKIRT = 1.5           # Gridfinity 底部裙边高度 (mm)
GRIDFINITY_WALL = 1.2            # Gridfinity 隔板壁厚 (mm)

# 堆叠特征默认参数
STACK_LIP_WIDTH_DEFAULT = 3.0    # 堆叠唇边宽度 (mm)
STACK_LIP_HEIGHT_DEFAULT = 2.0   # 堆叠唇边高度 (mm)
STACK_GROOVE_DEPTH_DEFAULT = 2.0 # 堆叠槽深度 (mm)
STACK_CLEARANCE = 0.2            # 堆叠间隙 (mm)，防止过紧

# ── 毫米链（计划 v1.3 §0.3 / 缺陷 F1）──────────────────
# 10 px/mm 是**固定常量**，图像 → mm 只有一个方向：mm = px / PX_PER_MM。
# 禁止任何按纸边长度 / 底板尺寸 / 画布尺寸动态推导的比例 —— F1 的根因就是
# 按板尺寸把轮廓重新缩放去「铺满底板」的写法（见 git 历史里的 F1）。
# 与 `imaging/constants.py` 的 PX_PER_MM 同值；这里不 import 它，因为
# 全仓统一以 `python_backend/` 为导入根（`cd python_backend && uvicorn main:app`），
# 新模块用裸导入；本文件仍冻结，不 import 任何新包。
# ★ 只定义正向常量 PX_PER_MM。反向常量（0.1）由 `imaging/constants.py` 独占持有：
#   imaging 的 DoD ③ 禁止 imaging/ 之外的生产模块出现那个名字（纯文本扫描），
#   这里要用就现写 `1.0 / PX_PER_MM`，不要另立常量。
PX_PER_MM = 10.0                 # px / mm

# 基元接龙时判定「两个端点算同一个点」的容差（px）。0.2mm 量级：圆弧拟合的
# 首末采样点与相邻直线端点本来就不重合（拟合残差可达 1~2px）。
_RING_JOIN_TOL_PX = 2.0

# ── Manifold 转换辅助 ─────────────────────────────────

def _trimesh_to_manifold(mesh: trimesh.Trimesh) -> Manifold:
    """将 trimesh 转换为 Manifold 做布尔运算"""
    verts = np.asarray(mesh.vertices, dtype=np.float32, order='C')
    faces = np.asarray(mesh.faces, dtype=np.uint32, order='C')
    m = ManifoldMesh(vert_properties=verts, tri_verts=faces)
    return Manifold(m)


def _manifold_to_trimesh(man: Manifold) -> trimesh.Trimesh:
    """将 Manifold 转换回 trimesh"""
    mesh = man.to_mesh()
    verts = np.array(mesh.vert_properties, dtype=np.float64)
    faces = np.array(mesh.tri_verts, dtype=np.int64)
    return trimesh.Trimesh(vertices=verts, faces=faces)


# ── 参数模型（从 models.py 共享） ──────────────────────

from models import BoxParams, GridfinityParams, InsertParams


# ── 几何构建函数 ─────────────────────────────────────

def _make_rounded_box(
    size_x: float, size_y: float, size_z: float,
    radius: float, segments: int = 16
) -> trimesh.Trimesh:
    """
    生成带圆角的方盒。
    
    策略：创建 2D 圆角矩形轮廓（使用 shapely buffer 方法），
    然后用 trimesh.extrude_polygon 拉伸成 3D。
    如果 shapely 不可用，回退到普通 box。
    """
    if radius < 0.01:
        return trimesh.creation.box(extents=[size_x, size_y, size_z])

    corner_r = min(radius, size_x / 2, size_y / 2)

    try:
        from shapely.geometry import box as sbox

        # 创建 2D 矩形 → 负 buffer 缩小 → 正 buffer 圆角
        rect = sbox(-size_x/2, -size_y/2, size_x/2, size_y/2)
        inner = rect.buffer(-corner_r, quad_segs=segments // 4)
        if inner is None or inner.area < 0.01:
            return trimesh.creation.box(extents=[size_x, size_y, size_z])
        rounded = inner.buffer(corner_r, quad_segs=segments // 4)
        if rounded is None or rounded.area < 0.01:
            return trimesh.creation.box(extents=[size_x, size_y, size_z])

        # 拉伸成 3D
        result = trimesh.creation.extrude_polygon(rounded, height=size_z)
        # extrude_polygon 从 z=0 开始，平移到居中
        result.apply_translation([0, 0, -size_z / 2])
        return result
    except Exception:
        errors.append("圆角拉伸失败，退回方块")
        return trimesh.creation.box(extents=[size_x, size_y, size_z])


def _make_rounded_rectangle_polygon(
    size_x: float, size_y: float,
    radius: float, segments: int = 16
):
    """
    生成 2D 圆角矩形多边形（shapely Polygon）。
    返回 shapely Polygon 或 None。
    """
    if radius < 0.01:
        from shapely.geometry import box as sbox
        return sbox(-size_x/2, -size_y/2, size_x/2, size_y/2)

    corner_r = min(radius, size_x / 2, size_y / 2)
    try:
        from shapely.geometry import box as sbox
        rect = sbox(-size_x/2, -size_y/2, size_x/2, size_y/2)
        inner = rect.buffer(-corner_r, quad_segs=segments // 4)
        if inner is None or inner.area < 0.01:
            return rect
        rounded = inner.buffer(corner_r, quad_segs=segments // 4)
        return rounded
    except Exception:
        errors.append("圆角轮廓失败，退回直角矩形")
        from shapely.geometry import box as sbox
        return sbox(-size_x/2, -size_y/2, size_x/2, size_y/2)


def _make_stackable_features(
    params: BoxParams,
) -> trimesh.Trimesh:
    """
    为 Foam 嵌件生成堆叠特征：
    - 顶面：沿内圈挖一条凹槽（groove）
    - 底面：沿内圈凸起一条唇边（lip）
    
    这样两个嵌件可以堆叠：下层嵌件的 lip 卡入上层嵌件的 groove。
    返回堆叠特征合并后的 mesh。
    """
    if not params.stackable:
        return None

    lw = min(params.stack_lip_width, min(params.length_mm, params.width_mm) * 0.15)
    lh = min(params.stack_lip_height, params.height_mm * 0.3)
    gd = lh  # groove depth = lip height (match for stacking)

    # 确保最小尺寸
    lw = max(lw, 1.0)
    lh = max(lh, 0.5)
    gd = max(gd, 0.5)

    try:
        from shapely.geometry import box as sbox

        # 底板外轮廓
        outer_poly = sbox(-params.length_mm/2, -params.width_mm/2,
                          params.length_mm/2, params.width_mm/2)

        # 内轮廓（lip/groove 的内边界）
        inner_poly = sbox(
            -params.length_mm/2 + lw,
            -params.width_mm/2 + lw,
            params.length_mm/2 - lw,
            params.width_mm/2 - lw,
        )

        # 环形区域 = 外 - 内
        ring = outer_poly.difference(inner_poly)

        if ring is None or ring.area < 1.0:
            return None

        # ── 底部 lip（向下凸起）──
        lip = trimesh.creation.extrude_polygon(ring, height=lh)
        lip.apply_translation([0, 0, -params.height_mm / 2 - lh / 2])

        # ── 顶部 groove 切除（从顶面向下挖槽）──
        # groove 比 lip 略宽（加 clearance），保证松配合
        groove_inner_off = lw + STACK_CLEARANCE
        groove_outer_off = -STACK_CLEARANCE  # 外边界略缩

        groove_inner_poly = sbox(
            -params.length_mm/2 + groove_inner_off,
            -params.width_mm/2 + groove_inner_off,
            params.length_mm/2 - groove_inner_off,
            params.width_mm/2 - groove_inner_off,
        )
        groove_outer_poly = sbox(
            -params.length_mm/2 - groove_outer_off,
            -params.width_mm/2 - groove_outer_off,
            params.length_mm/2 + groove_outer_off,
            params.width_mm/2 + groove_outer_off,
        )
        groove_ring = groove_outer_poly.difference(groove_inner_poly)

        if groove_ring is None or groove_ring.area < 1.0:
            return lip  # 只有 lip，没有 groove

        groove_cut = trimesh.creation.extrude_polygon(groove_ring, height=gd)
        groove_cut.apply_translation([0, 0, params.height_mm / 2 - gd / 2])

        # 合并：lip 加到基底，groove 作为减料
        if HAS_MANIFOLD:
            m_lip = _trimesh_to_manifold(lip)
            m_groove = _trimesh_to_manifold(groove_cut)
            # 返回两个特征，由调用方处理布尔运算
            return _manifold_to_trimesh(m_lip - m_groove)
        else:
            # 无 manifold：直接合并 mesh
            combined = trimesh.util.concatenate([lip, groove_cut])
            return combined

    except Exception as e:
        errors.append("堆叠特征生成失败")
        print(f"堆叠特征生成失败: {e}")
        return None


def _make_gridfinity_base(params: GridfinityParams) -> trimesh.Trimesh:
    """
    生成 Gridfinity 标准底板：
    - 外框尺寸 = units × 42mm
    - 底部有裙边
    - 可选磁吸孔
    """
    sx, sy, sz = params.size_x, params.size_y, params.height_mm
    base = _make_rounded_box(sx, sy, sz, GRIDFINITY_CORNER_R)
    if not HAS_MANIFOLD:
        return base

    try:
        m_base = _trimesh_to_manifold(base)

        # 底部裙边（内缩一圈）
        skirt_inner_x = sx - 2 * GRIDFINITY_SKIRT
        skirt_inner_y = sy - 2 * GRIDFINITY_SKIRT
        skirt_cut = trimesh.creation.box(
            extents=[skirt_inner_x, skirt_inner_y, GRIDFINITY_BASE_THICKNESS]
        )
        skirt_cut.apply_translation([0, 0, -GRIDFINITY_BASE_THICKNESS / 2])
        m_cut = _trimesh_to_manifold(skirt_cut)
        result = m_base - m_cut

        # 磁吸孔
        if params.has_magnet_holes:
            for hx, hy in _gridfinity_hole_positions(params.units_x, params.units_y):
                hole = trimesh.creation.cylinder(
                    radius=GRIDFINITY_HOLE_DIA / 2,
                    height=GRIDFINITY_HOLE_DEPTH + 1,
                    sections=16,
                )
                hole.apply_translation([hx, hy, -GRIDFINITY_BASE_THICKNESS / 2])
                result = result - _trimesh_to_manifold(hole)

        return _manifold_to_trimesh(result)
    except Exception:
        errors.append("gridfinity 磁吸孔布尔失败，退回无孔底板")
        return base


def _gridfinity_hole_positions(units_x: int, units_y: int) -> List[Tuple[float, float]]:
    """计算 Gridfinity 磁吸孔位置（每个网格中心）"""
    positions = []
    for ix in range(units_x):
        for iy in range(units_y):
            cx = (ix + 0.5) * GRIDFINITY_PITCH - units_x * GRIDFINITY_PITCH / 2
            cy = (iy + 0.5) * GRIDFINITY_PITCH - units_y * GRIDFINITY_PITCH / 2
            positions.append((cx, cy))
    return positions



# ── 手指槽生成 ─────────────────────────────────────

def _make_capsule_2d(
    cx: float, cy: float,
    length: float, width: float,
    rotation: float = 0.0,
    half: bool = False,
):
    """
    生成 2D 胶囊形（stadium shape）多边形。
    
    参数:
      cx, cy: 中心坐标 (mm)
      length: 胶囊总长度 (mm) — 矩形段长度 + 两端半圆直径
      width: 胶囊宽度/直径 (mm) — 半圆的直径
      rotation: 旋转角度（度，逆时针）
      half: 如果为 True，只生成上半部分（沿长轴切一半）
    
    返回 shapely Polygon。
    """
    from shapely.geometry import Point, Polygon, box as sbox
    from shapely import affinity
    import math
    
    r = width / 2.0
    rect_len = max(0, length - width)
    half_len = (rect_len + width) / 2.0
    
    c1 = Point(-rect_len / 2, 0)
    c2 = Point(rect_len / 2, 0)
    
    circle1 = c1.buffer(r, quad_segs=16)
    circle2 = c2.buffer(r, quad_segs=16)
    
    rect = sbox(-half_len, -r, half_len, r)
    
    capsule = rect.union(circle1).union(circle2)
    
    if half:
        clip_box = sbox(-half_len - r, 0, half_len + r, r + 1)
        capsule = capsule.intersection(clip_box)
    
    if abs(rotation) > 0.01:
        capsule = affinity.rotate(capsule, rotation, origin=(0, 0), use_radians=False)
    
    capsule = affinity.translate(capsule, cx, cy)
    
    return capsule


def _extrude_finger_slot(
    slot: Dict[str, Any],
    base_height: float,
) -> Optional[trimesh.Trimesh]:
    """
    生成单个手指槽的 3D 实体（用于从基底布尔减去）。
    
    手指槽是一个从侧面水平穿入的半胶囊形孔道，
    方便手指伸入拿取工具。
    
    参数:
      slot: {
        "x": 中心 X (mm),
        "y": 中心 Y (mm),
        "length": 胶囊长度 (mm),
        "width": 胶囊宽度 (mm),
        "depth": 深度 (mm) — 从侧面穿入的深度,
        "rotation": 旋转角度（度）
      }
      base_height: 基底高度 (mm)
    
    返回: trimesh.Trimesh 实体（用于布尔减）
    """
    cx = slot.get("x", 0)
    cy = slot.get("y", 0)
    length = slot.get("length", 25.0)
    width = slot.get("width", 12.0)
    depth = slot.get("depth", base_height * 0.8)
    rotation = slot.get("rotation", 0.0)
    
    depth = min(depth, base_height * 0.95)
    
    # 在 YZ 平面画半胶囊，沿 X 轴拉伸（水平穿入）
    cap_yz = _make_capsule_2d(0, 0, length, width, rotation=0, half=True)
    if cap_yz is None or cap_yz.area < 0.1:
        return None
    
    try:
        # 沿 X 轴拉伸
        slot_mesh = trimesh.creation.extrude_polygon(cap_yz, height=depth)
        
        # 旋转到指定角度（绕 Z 轴）
        import math
        rad = math.radians(rotation)
        rot_mat = trimesh.transformations.rotation_matrix(rad, [0, 0, 1])
        slot_mesh.apply_transform(rot_mat)
        
        # 平移到目标位置
        slot_mesh.apply_translation([cx, cy, 0])
        
        return slot_mesh
    except Exception as e:
        errors.append("手指槽拉伸失败")
        print(f"手指槽拉伸失败: {e}")
        return None


def _generate_finger_slots(
    finger_slots: List[Dict[str, Any]],
    base_height: float,
) -> Optional[trimesh.Trimesh]:
    """
    生成所有手指槽的合并实体（用于从基底布尔减去）。
    如果 slots 为空，返回 None。
    """
    if not finger_slots:
        return None
    
    meshes = []
    for slot in finger_slots:
        m = _extrude_finger_slot(slot, base_height)
        if m is not None:
            meshes.append(m)
    
    if not meshes:
        return None
    
    if len(meshes) == 1:
        return meshes[0]
    
    try:
        combined = trimesh.util.concatenate(meshes)
        return combined
    except Exception as e:
        errors.append("合并手指槽失败")
        print(f"合并手指槽失败: {e}")
        return meshes[0]


def _auto_detect_finger_slots(
    primitives: List[Dict],
    base_size_x: float,
    base_size_y: float,
    base_height: float,
    slot_width: float = 12.0,
    slot_depth: float = 10.0,
    slot_length: float = 25.0,
) -> List[Dict[str, Any]]:
    """
    自动检测工具轮廓，在合适位置生成手指槽。
    
    策略：
    1. 计算工具轮廓的包围盒和主方向（PCA）
    2. 在工具轮廓的长轴两端附近放置手指槽
    3. 手指槽从轮廓外侧向内侧穿入
    
    返回手指槽参数列表。
    """
    if not primitives:
        return []
    
    points = _primitives_to_2d_polygon(primitives)
    if points is None or len(points) < 3:
        return []
    
    # PCA 主方向
    mean = np.mean(points, axis=0)
    centered = points - mean
    cov = np.cov(centered.T)
    # numpy 2.x: eig 对实对称 cov 仍返回 complex128，会让下游 slot 坐标变复数
    # 并在 arctan2 抛 TypeError。eigh 专用于 Hermitian，返回实数 float64。
    # （M0 审核 P0-2 的冻结例外，主会话批准；仅此一行，不改任何逻辑）
    eig_vals, eig_vecs = np.linalg.eigh(cov)
    main_axis = eig_vecs[:, np.argmax(eig_vals)]
    
    # 投影到主轴，找两端
    proj = centered @ main_axis
    min_idx = np.argmin(proj)
    max_idx = np.argmax(proj)
    
    p_min = points[min_idx]
    p_max = points[max_idx]
    
    angle = np.degrees(np.arctan2(main_axis[1], main_axis[0]))
    margin = slot_length * 0.3
    
    slots = []
    
    # 端1（负方向）
    dir_vec = main_axis * margin
    pos1 = p_min - dir_vec
    rot1 = angle
    
    slots.append({
        "x": float(pos1[0]),
        "y": float(pos1[1]),
        "length": slot_length,
        "width": slot_width,
        "depth": slot_depth,
        "rotation": float(rot1 % 360),
    })
    
    # 端2（正方向）
    pos2 = p_max + dir_vec
    rot2 = (angle + 180) % 360
    
    slots.append({
        "x": float(pos2[0]),
        "y": float(pos2[1]),
        "length": slot_length,
        "width": slot_width,
        "depth": slot_depth,
        "rotation": float(rot2 % 360),
    })
    
    return slots



def _signed_area(pts: np.ndarray) -> float:
    """鞋带公式有符号面积（px²）。> 0 为 CCW。"""
    n = len(pts)
    if n < 3:
        return 0.0
    x = pts[:, 0]
    y = pts[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(np.roll(x, -1), y))


def _sample_arc(p: Dict) -> List[List[float]]:
    """圆弧基元 → 采样点列（px）。

    兼容两套键名：`angle_start/angle_end`（optimized_contour_processing.py）与
    `startAngle/endAngle`（curvature_simplify.py）。`a1 <= a0` 视为逆时针跨 0 度。
    缺 center/radius/角度时返回空列表，调用方据此跳过该基元。
    """
    center = p.get("center") or {}
    try:
        cx = float(center.get("x", 0.0))
        cy = float(center.get("y", 0.0))
        radius = float(p.get("radius", 0.0) or 0.0)
    except (TypeError, ValueError):
        return []
    if radius <= 0.0:
        return []

    a0 = p.get("angle_start", p.get("startAngle"))
    a1 = p.get("angle_end", p.get("endAngle"))
    if a0 is None or a1 is None:
        return []
    try:
        a0 = float(a0)
        a1 = float(a1)
    except (TypeError, ValueError):
        return []

    while a1 <= a0:          # 跨 0 度；a1 == a0 时补成整圆
        a1 += 360.0
    span = a1 - a0
    n = max(8, int(span / 5.0) + 1)
    angles = np.radians(np.linspace(a0, a1, n))
    return [
        [cx + radius * float(np.cos(t)), cy + radius * float(np.sin(t))]
        for t in angles
    ]


def _primitive_points(p: Dict) -> List[List[float]]:
    """单个基元 → 有序点列（px，不含闭合重复点）。"""
    t = p.get("type", "")
    if t == "line":
        p0 = p.get("p0") or {}
        p1 = p.get("p1") or {}
        return [
            [float(p0.get("x", 0.0)), float(p0.get("y", 0.0))],
            [float(p1.get("x", 0.0)), float(p1.get("y", 0.0))],
        ]
    if t == "polyline":
        return [
            [float(q.get("x", 0.0)), float(q.get("y", 0.0))]
            for q in (p.get("points") or [])
        ]
    if t == "arc":
        pts = [
            [float(q.get("x", 0.0)), float(q.get("y", 0.0))]
            for q in (p.get("points") or [])
        ]
        if len(pts) >= 2:
            return pts
        return _sample_arc(p)
    return []


def _chain_rings(
    primitives: List[Dict],
    tol: float = _RING_JOIN_TOL_PX,
) -> List[np.ndarray]:
    """把 line/arc/polyline 串成有序闭合环（px）。

    ★ 旧实现按**出现顺序**直接拼接点（历史 :503-521），既不保证闭合、也不保证方向，
      内环还会被拍平成外环的一段。这里改为端点接龙：每步从当前环末端出发，找端点
      距离 <= tol 的基元接上（必要时整段反向），直到接不上为止，然后开下一个环。

    环的顶点坐标**原样保留**（不插值、不吸附），因此 roundtrip 可以做到逐点相等；
    只有末尾那个与首点重合的闭合点会被去掉（shapely 的 Polygon 隐式闭合）。
    """
    pending: List[np.ndarray] = []
    for p in primitives:
        pts = _primitive_points(p)
        if len(pts) >= 2:
            pending.append(np.asarray(pts, dtype=np.float64))

    rings: List[np.ndarray] = []
    while pending:
        cur = [tuple(pt) for pt in pending.pop(0)]
        joined = True
        while joined:
            joined = False
            end = np.asarray(cur[-1], dtype=np.float64)
            for i, seg in enumerate(pending):
                if np.linalg.norm(seg[0] - end) <= tol:
                    cur.extend(tuple(pt) for pt in seg[1:])
                elif np.linalg.norm(seg[-1] - end) <= tol:
                    cur.extend(tuple(pt) for pt in seg[::-1][1:])
                else:
                    continue
                pending.pop(i)
                joined = True
                break
        ring = np.asarray(cur, dtype=np.float64)
        if len(ring) >= 2 and np.linalg.norm(ring[-1] - ring[0]) <= tol:
            ring = ring[:-1]        # 去掉重复的闭合点
        if len(ring) >= 3:
            rings.append(ring)
    return rings


def _primitives_to_rings(primitives: List[Dict]) -> List[np.ndarray]:
    """基元 → 环列表（px），按 |面积| 降序；`rings[0]` 是外环。"""
    rings = _chain_rings(primitives)
    rings.sort(key=lambda r: abs(_signed_area(r)), reverse=True)
    return rings


def _primitives_to_shape(primitives: List[Dict]):
    """基元 → shapely Polygon（px，含内环），失败返回 None。

    外环 = |面积| 最大的环；其余环若被外环包含则作为内孔。嵌在内孔里的岛
    （第三层嵌套）会被忽略 —— 旧引擎只需要「外轮廓 + 内孔」。
    """
    rings = _primitives_to_rings(primitives)
    if not rings:
        return None

    from shapely.geometry import Polygon

    outer = Polygon([tuple(pt) for pt in rings[0]])
    if outer.is_empty or not outer.is_valid:
        return None

    holes: List[list] = []
    for ring in rings[1:]:
        cand = Polygon([tuple(pt) for pt in ring])
        if cand.is_empty or not cand.is_valid:
            continue
        if outer.contains(cand):
            holes.append([tuple(pt) for pt in ring])

    poly = Polygon([tuple(pt) for pt in rings[0]], holes)
    if poly.is_empty or not poly.is_valid:
        return None
    return poly


def _primitives_to_2d_polygon(primitives: List[Dict]) -> Optional[np.ndarray]:
    """兼容旧调用方：只返回**外环**点列（px，N×2）。要内环请用 `_primitives_to_shape`。"""
    rings = _primitives_to_rings(primitives)
    if not rings:
        return None
    return rings[0]


def _paper_mm_shape(primitives: List[Dict]):
    """基元 → 纸面毫米 shapely Polygon（固定 10 px/mm，不读任何板/纸尺寸）。"""
    shape_px = _primitives_to_shape(primitives)
    if shape_px is None:
        return None

    from shapely import affinity

    # 缩放（含内环）交给 shapely，自己遍历 exterior/interiors 容易漏掉 LinearRing
    # 与闭合点的细节。
    _s = 1.0 / PX_PER_MM
    return affinity.scale(shape_px, xfact=_s, yfact=_s, origin=(0.0, 0.0))


def _to_board_frame_shape(shape, center: Tuple[float, float]):
    """纸面 mm(y-down) → 板局部 mm(y-up，原点 = 板心)。

    与 `geometry/polygon.py:44` 的 `to_board_frame` 同式：

        (x, y) -> (x - cx, cy - y)

    ★ y 取反（cy - y）是必须的：旧代码 `poly_mm -= center` 展开是 (x-cx, y-cy)，
      y 方向符号反了 —— 这是 F1 的第二个组成部分，不要再退回去。
    """
    from shapely import affinity

    cx, cy = center
    moved = affinity.translate(shape, xoff=-cx, yoff=-cy)
    return affinity.scale(moved, xfact=1.0, yfact=-1.0, origin=(0.0, 0.0))


def _extrude_tool_slot(
    primitives: List[Dict],
    embed_depth: float,
    tool_offset: float,
    base_size_x: Optional[float] = None,
    base_size_y: Optional[float] = None,
) -> Optional[trimesh.Trimesh]:
    """从工具轮廓拉伸生成工具槽（用于从基底布尔减去）。

    ★ 毫米链（计划 v1.3 §0.3 / 缺陷 F1）：px → mm **只用固定 `PX_PER_MM = 10.0`**。
      `base_size_x` / `base_size_y` **不参与任何换算**，保留形参仅为兼容既有调用方
      与回归测试（同一轮廓在不同板尺寸下必须得到同一把刀）。

      历史上这里把轮廓当作「校正图是固定像素尺寸」的像素坐标，再按
      `min(base_size_x / img_w, base_size_y / img_h)` 缩放去「铺满」底板 ——
      于是同一工具换个板就得到不同大小的槽。那套换算不要加回来。
    """
    shape_mm = _paper_mm_shape(primitives)
    if shape_mm is None or shape_mm.is_empty:
        return None

    # 纸面 mm(y-down) → 板局部 mm(y-up)，原点 = 轮廓 bbox 中心
    minx, miny, maxx, maxy = shape_mm.bounds
    center = ((minx + maxx) / 2.0, (miny + maxy) / 2.0)
    shape_board = _to_board_frame_shape(shape_mm, center)

    # 间隙：mm 域 miter 偏置（正值外扩）。替换原先手写的「平均法向 + 1/cos」偏移，
    # 后者无自交清理，而且把 mm 当成 px 用（差 10 倍）。
    if abs(tool_offset) > 1e-9:
        try:
            shape_board = shape_board.buffer(
                tool_offset, join_style=2, mitre_limit=2.0
            )
        except Exception as e:
            print(f"工具槽间隙偏置失败: {e}")
            return None
        if shape_board.is_empty:
            return None
        if shape_board.geom_type == "MultiPolygon":
            shape_board = max(shape_board.geoms, key=lambda g: g.area)

    try:
        from shapely.geometry.polygon import orient

        shape_board = orient(shape_board, sign=1.0)      # 外环 CCW、内孔 CW
        if shape_board.area < 0.1:                       # mm²
            return None
        slot = trimesh.creation.extrude_polygon(shape_board, height=embed_depth + 1)
        slot.apply_translation([0, 0, -embed_depth / 2])
        return slot
    except Exception as e:
        errors.append("工具槽拉伸失败")
        print(f"工具槽拉伸失败: {e}")
        return None


# ── 主生成函数 ───────────────────────────────────────

def generate_insert(params: InsertParams) -> Dict[str, Any]:
    """
    生成嵌件 3D 模型。

    返回:
        {
            "success": bool,
            "error": str (optional),
            "stl_base64": str (base64 encoded STL),
            "summary": { ... }
        }
    """
    try:
        # 1. 生成基底
        if params.mode == "gridfinity":
            base = _make_gridfinity_base(params.gridfinity)
            base_size_x = params.gridfinity.size_x
            base_size_y = params.gridfinity.size_y
        else:
            base = _make_rounded_box(
                params.foam.length_mm,
                params.foam.width_mm,
                params.foam.height_mm,
                params.foam.fillet_radius,
            )
            base_size_x = params.foam.length_mm
            base_size_y = params.foam.width_mm

        # 2. 堆叠特征（仅 Foam 模式）
        if params.mode == "foam" and params.foam.stackable:
            stack_feature = _make_stackable_features(params.foam)
            if stack_feature is not None:
                try:
                    if HAS_MANIFOLD:
                        m_base = _trimesh_to_manifold(base)
                        m_stack = _trimesh_to_manifold(stack_feature)
                        # stack_feature 已经包含了 lip 和 groove 的合并/减法
                        # 对于 lip（凸起），需要 union；对于 groove（凹槽），stack_feature 已经做了减法
                        # 我们简化处理：stack_feature 中的 lip 是凸起的正体，groove 已从 lip 减掉
                        # 所以这里 base + stack_feature 即可（stack_feature 包含 lip 正体和 groove 负体）
                        base = _manifold_to_trimesh(m_base + m_stack)
                    else:
                        # 无 manifold：直接在基底上挖 groove 并加 lip
                        # 提取 lip 和 groove
                        from shapely.geometry import box as sbox
                        lw = min(params.foam.stack_lip_width, min(params.foam.length_mm, params.foam.width_mm) * 0.15)
                        lh = min(params.foam.stack_lip_height, params.foam.height_mm * 0.3)
                        lw = max(lw, 1.0)
                        lh = max(lh, 0.5)

                        # 底部 lip（加到基底底部）
                        inner_poly = sbox(
                            -params.foam.length_mm/2 + lw,
                            -params.foam.width_mm/2 + lw,
                            params.foam.length_mm/2 - lw,
                            params.foam.width_mm/2 - lw,
                        )
                        outer_poly = sbox(
                            -params.foam.length_mm/2,
                            -params.foam.width_mm/2,
                            params.foam.length_mm/2,
                            params.foam.width_mm/2,
                        )
                        ring = outer_poly.difference(inner_poly)
                        if ring is not None and ring.area > 1.0:
                            lip = trimesh.creation.extrude_polygon(ring, height=lh)
                            lip.apply_translation([0, 0, -params.foam.height_mm / 2 - lh / 2])

                            # 顶部 groove（从基底顶面挖掉）
                            groove_inner = sbox(
                                -params.foam.length_mm/2 + lw + STACK_CLEARANCE,
                                -params.foam.width_mm/2 + lw + STACK_CLEARANCE,
                                params.foam.length_mm/2 - lw - STACK_CLEARANCE,
                                params.foam.width_mm/2 - lw - STACK_CLEARANCE,
                            )
                            groove_outer = sbox(
                                -params.foam.length_mm/2 - STACK_CLEARANCE,
                                -params.foam.width_mm/2 - STACK_CLEARANCE,
                                params.foam.length_mm/2 + STACK_CLEARANCE,
                                params.foam.width_mm/2 + STACK_CLEARANCE,
                            )
                            groove_ring = groove_outer.difference(groove_inner)
                            if groove_ring is not None and groove_ring.area > 1.0:
                                groove_cut = trimesh.creation.extrude_polygon(groove_ring, height=lh)
                                groove_cut.apply_translation([0, 0, params.foam.height_mm / 2 - lh / 2])

                                # 将 lip 加到基底底部
                                base = trimesh.util.concatenate([base, lip])
                                # groove 用减法
                                base = base.difference(groove_cut)
                            else:
                                # 只有 lip，没有 groove
                                base = trimesh.util.concatenate([base, lip])
                except Exception as e:
                    errors.append("堆叠特征布尔运算失败")
                    print(f"堆叠特征布尔运算失败 (no manifold): {e}")

        # 3. 工具槽（从基底减去工具轮廓的拉伸体）
        if params.primitives:
            tool_slot = _extrude_tool_slot(
                params.primitives,
                params.embed_depth,
                params.tool_offset,
                base_size_x,
                base_size_y,
            )
            if tool_slot is not None:
                try:
                    if HAS_MANIFOLD:
                        m_base = _trimesh_to_manifold(base)
                        m_slot = _trimesh_to_manifold(tool_slot)
                        base = _manifold_to_trimesh(m_base - m_slot)
                    else:
                        base = base.difference(tool_slot)
                except Exception as e:
                    errors.append("工具槽布尔运算失败")
                    print(f"工具槽布尔运算失败: {e}")


        # 3.5 手指槽（从基底减去手指槽实体）
        # 如果有自动生成标记且用户未自定义槽位，自动生成
        finger_slots = params.finger_slots
        if finger_slots and len(finger_slots) > 0:
            # 确定基底高度：Foam 模式用 foam.height_mm，Gridfinity 模式用 gridfinity height
            base_height = params.foam.height_mm if params.mode == "foam" else params.gridfinity.height_mm
            finger_mesh = _generate_finger_slots(finger_slots, base_height)
            if finger_mesh is not None:
                try:
                    if HAS_MANIFOLD:
                        m_base = _trimesh_to_manifold(base)
                        m_finger = _trimesh_to_manifold(finger_mesh)
                        base = _manifold_to_trimesh(m_base - m_finger)
                    else:
                        base = base.difference(finger_mesh)
                except Exception as e:
                    errors.append("手指槽布尔运算失败")
                    print(f"手指槽布尔运算失败: {e}")

        # 4. 导出 STL
        from trimesh.exchange.stl import export_stl as _export_stl
        stl_bytes = _export_stl(base)
        stl_base64 = base64.b64encode(stl_bytes).decode("utf-8")

        # 5. 统计信息
        volume = base.volume if hasattr(base, 'volume') else 0.0
        bounds = base.bounds if hasattr(base, 'bounds') else None
        summary = {
            "vertices": len(base.vertices) if hasattr(base, 'vertices') else 0,
            "faces": len(base.faces) if hasattr(base, 'faces') else 0,
            "volume_mm3": round(float(volume), 2),
            "bounds": {
                "x": [float(bounds[0][0]), float(bounds[1][0])] if bounds is not None else [0, 0],
                "y": [float(bounds[0][1]), float(bounds[1][1])] if bounds is not None else [0, 0],
                "z": [float(bounds[0][2]), float(bounds[1][2])] if bounds is not None else [0, 0],
            },
        }

        # 添加 Foam 参数到 summary（前端展示用）
        if params.mode == "foam":
            summary["length_mm"] = params.foam.length_mm
            summary["width_mm"] = params.foam.width_mm
            summary["height_mm"] = params.foam.height_mm
            summary["fillet_radius"] = params.foam.fillet_radius
            summary["stackable"] = params.foam.stackable
            summary["stack_lip_width"] = params.foam.stack_lip_width
            summary["stack_lip_height"] = params.foam.stack_lip_height
        else:
            summary["units_x"] = params.gridfinity.units_x
            summary["units_y"] = params.gridfinity.units_y
            summary["height_u"] = params.gridfinity.height_u

        return {
            "success": True,
            "stl_base64": stl_base64,
            "summary": summary,
        }
    except Exception as e:
        errors.append("CAD 生成失败")
        print(f"CAD 生成失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
        }


# ── 兼容性包装 ────────────────────────────────────────

def generate_stl(params: dict) -> dict:
    """
    兼容旧的 generate_stl API。
    接收原始 dict 参数，转换为 InsertParams 后调用 generate_insert。
    """
    mode = params.get("mode", "foam")
    foam_dict = params.get("foam", {})
    gridfinity_dict = params.get("gridfinity", {})

    # 从 foam dict 提取堆叠参数
    stackable = foam_dict.get("stackable", False)
    stack_lip_width = foam_dict.get("stack_lip_width", STACK_LIP_WIDTH_DEFAULT)
    stack_lip_height = foam_dict.get("stack_lip_height", STACK_LIP_HEIGHT_DEFAULT)

    foam = BoxParams(
        length_mm=foam_dict.get("length_mm", 200.0),
        width_mm=foam_dict.get("width_mm", 150.0),
        height_mm=foam_dict.get("height_mm", 20.0),
        fillet_radius=foam_dict.get("fillet_radius", 5.0),
        wall_thickness=foam_dict.get("wall_thickness", 2.0),
        stackable=stackable,
        stack_lip_width=stack_lip_width,
        stack_lip_height=stack_lip_height,
    )

    gridfinity = GridfinityParams(
        units_x=gridfinity_dict.get("units_x", 3),
        units_y=gridfinity_dict.get("units_y", 2),
        height_u=gridfinity_dict.get("height_u", 3.0),
        has_magnet_holes=gridfinity_dict.get("has_magnet_holes", True),
    )

    insert_params = InsertParams(
        mode=mode,
        foam=foam,
        gridfinity=gridfinity,
        primitives=params.get("primitives", []),
        tool_offset=params.get("tool_offset", 1.0),
        embed_depth=params.get("embed_depth", 15.0),
        finger_slots=params.get("finger_slots", []),
    )

    return generate_insert(insert_params)
