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
import io
from typing import List, Dict, Any, Optional, Tuple

try:
    from manifold3d import Manifold, Mesh as ManifoldMesh
    HAS_MANIFOLD = True
except ImportError:
    HAS_MANIFOLD = False

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


# ── 参数模型 ──────────────────────────────────────────

class BoxParams:
    """方盒参数（Foam 模式用）"""
    def __init__(
        self,
        length_mm: float = 200.0,
        width_mm: float = 150.0,
        height_mm: float = 20.0,
        fillet_radius: float = 5.0,
        wall_thickness: float = 2.0,
        stackable: bool = False,
        stack_lip_width: float = STACK_LIP_WIDTH_DEFAULT,
        stack_lip_height: float = STACK_LIP_HEIGHT_DEFAULT,
    ):
        self.length_mm = length_mm
        self.width_mm = width_mm
        self.height_mm = height_mm
        self.fillet_radius = fillet_radius
        self.wall_thickness = wall_thickness
        self.stackable = stackable
        self.stack_lip_width = stack_lip_width
        self.stack_lip_height = stack_lip_height

    def to_dict(self) -> dict:
        return {
            "length_mm": self.length_mm,
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "fillet_radius": self.fillet_radius,
            "wall_thickness": self.wall_thickness,
            "stackable": self.stackable,
            "stack_lip_width": self.stack_lip_width,
            "stack_lip_height": self.stack_lip_height,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BoxParams":
        return cls(
            length_mm=d.get("length_mm", 200.0),
            width_mm=d.get("width_mm", 150.0),
            height_mm=d.get("height_mm", 20.0),
            fillet_radius=d.get("fillet_radius", 5.0),
            wall_thickness=d.get("wall_thickness", 2.0),
            stackable=d.get("stackable", False),
            stack_lip_width=d.get("stack_lip_width", STACK_LIP_WIDTH_DEFAULT),
            stack_lip_height=d.get("stack_lip_height", STACK_LIP_HEIGHT_DEFAULT),
        )


class GridfinityParams:
    """Gridfinity 模式参数"""
    def __init__(
        self,
        units_x: int = 3,
        units_y: int = 2,
        height_u: float = 3.0,
        has_magnet_holes: bool = True,
    ):
        self.units_x = units_x
        self.units_y = units_y
        self.height_u = height_u
        self.has_magnet_holes = has_magnet_holes

    @property
    def size_x(self) -> float:
        return self.units_x * GRIDFINITY_PITCH

    @property
    def size_y(self) -> float:
        return self.units_y * GRIDFINITY_PITCH

    @property
    def height_mm(self) -> float:
        return self.height_u * 7.0 + GRIDFINITY_BASE_THICKNESS

    def to_dict(self) -> dict:
        return {
            "units_x": self.units_x,
            "units_y": self.units_y,
            "height_u": self.height_u,
            "has_magnet_holes": self.has_magnet_holes,
            "size_x": self.size_x,
            "size_y": self.size_y,
            "height_mm": self.height_mm,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GridfinityParams":
        return cls(
            units_x=d.get("units_x", 3),
            units_y=d.get("units_y", 2),
            height_u=d.get("height_u", 3.0),
            has_magnet_holes=d.get("has_magnet_holes", True),
        )


class InsertParams:
    """嵌件参数（总配置）"""
    def __init__(
        self,
        mode: str = "foam",
        foam: Optional[BoxParams] = None,
        gridfinity: Optional[GridfinityParams] = None,
        primitives: Optional[List[Dict]] = None,
        tool_offset: float = 1.0,
        embed_depth: float = 15.0,
        finger_slots: Optional[List[Dict]] = None,
    ):
        self.mode = mode
        self.foam = foam or BoxParams()
        self.gridfinity = gridfinity or GridfinityParams()
        self.primitives = primitives or []
        self.tool_offset = tool_offset
        self.embed_depth = embed_depth
        self.finger_slots = finger_slots or []

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "foam": self.foam.to_dict(),
            "gridfinity": self.gridfinity.to_dict(),
            "tool_offset": self.tool_offset,
            "embed_depth": self.embed_depth,
            "num_primitives": len(self.primitives),
            "num_finger_slots": len(self.finger_slots),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "InsertParams":
        return cls(
            mode=d.get("mode", "foam"),
            foam=BoxParams.from_dict(d.get("foam", {})),
            gridfinity=GridfinityParams.from_dict(d.get("gridfinity", {})),
            primitives=d.get("primitives", []),
            tool_offset=d.get("tool_offset", 1.0),
            embed_depth=d.get("embed_depth", 15.0),
            finger_slots=d.get("finger_slots", []),
        )


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

    # 内缩尺寸（lip/groove 的内外边界）
    inner_off = lw
    outer_off = 0.0  # lip/groove 的外边界就是底板边缘

    try:
        from shapely.geometry import box as sbox

        # 底板外轮廓
        outer_poly = sbox(-params.length_mm/2, -params.width_mm/2,
                          params.length_mm/2, params.width_mm/2)

        # 内轮廓（lip/groove 的内边界）
        inner_poly = sbox(
            -params.length_mm/2 + inner_off,
            -params.width_mm/2 + inner_off,
            params.length_mm/2 - inner_off,
            params.width_mm/2 - inner_off,
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
        groove_inner_off = inner_off + STACK_CLEARANCE
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
    
    points = _primitives_to_2d_polygon(primitives, offset_mm=0)
    if points is None or len(points) < 3:
        return []
    
    # PCA 主方向
    mean = np.mean(points, axis=0)
    centered = points - mean
    cov = np.cov(centered.T)
    eig_vals, eig_vecs = np.linalg.eig(cov)
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



def _primitives_to_2d_polygon(
    primitives: List[Dict],
    offset_mm: float = 0.0,
) -> Optional[np.ndarray]:
    """
    将基元列表转换为 2D 多边形点列。
    返回 N×2 numpy array，或 None。
    """
    if not primitives:
        return None

    points = []
    for p in primitives:
        t = p.get("type", "")
        if t == "line":
            p0 = p.get("p0", {})
            p1 = p.get("p1", {})
            points.append([p0.get("x", 0), p0.get("y", 0)])
            points.append([p1.get("x", 0), p1.get("y", 0)])
        elif t == "arc":
            for pt in p.get("points", []):
                points.append([pt.get("x", 0), pt.get("y", 0)])
        elif t == "polyline":
            for pt in p.get("points", []):
                points.append([pt.get("x", 0), pt.get("y", 0)])

    if len(points) < 3:
        return None

    pts = np.array(points, dtype=np.float64)

    if abs(offset_mm) > 0.01:
        try:
            pts = _offset_polygon(pts, offset_mm)
        except Exception:
            pass

    return pts


def _offset_polygon(pts: np.ndarray, offset: float) -> np.ndarray:
    """简单多边形偏移（沿法线方向移动顶点）"""
    n = len(pts)
    if n < 3:
        return pts

    result = np.zeros_like(pts)
    for i in range(n):
        prev = pts[(i - 1) % n]
        curr = pts[i]
        next_ = pts[(i + 1) % n]

        d1 = curr - prev
        d2 = next_ - curr
        len1 = np.linalg.norm(d1)
        len2 = np.linalg.norm(d2)

        if len1 < 1e-6 or len2 < 1e-6:
            result[i] = curr
            continue

        n1 = np.array([-d1[1] / len1, d1[0] / len1])
        n2 = np.array([-d2[1] / len2, d2[0] / len2])

        avg_n = (n1 + n2) / 2
        norm = np.linalg.norm(avg_n)
        if norm < 1e-6:
            avg_n = n1
            norm = 1.0

        cos_half = np.dot(n1, avg_n / norm)
        if abs(cos_half) < 0.01:
            cos_half = 0.01
        compensation = 1.0 / cos_half

        result[i] = curr + avg_n / norm * offset * compensation

    return result


def _extrude_tool_slot(
    primitives: List[Dict],
    embed_depth: float,
    tool_offset: float,
    base_size_x: float,
    base_size_y: float,
) -> Optional[trimesh.Trimesh]:
    """
    从工具轮廓拉伸生成工具槽（用于从基底布尔减去）。
    """
    # 假设校正图尺寸 840×1188 px
    img_width, img_height = 840.0, 1188.0

    polygon_2d = _primitives_to_2d_polygon(primitives, offset_mm=tool_offset)
    if polygon_2d is None or len(polygon_2d) < 3:
        return None

    # 缩放至基底尺寸并居中
    scale = min(base_size_x / img_width, base_size_y / img_height)
    poly_mm = polygon_2d * scale
    center = poly_mm.mean(axis=0)
    poly_mm -= center

    # 确保逆时针
    area = 0.5 * np.sum(
        poly_mm[:-1, 0] * poly_mm[1:, 1] - poly_mm[1:, 0] * poly_mm[:-1, 1]
    )
    if area < 0:
        poly_mm = poly_mm[::-1]

    try:
        from shapely.geometry import Polygon
        poly = Polygon(poly_mm)
        if not poly.is_valid or poly.area < 0.1:
            return None

        slot = trimesh.creation.extrude_polygon(poly, height=embed_depth + 1)
        slot.apply_translation([0, 0, -embed_depth / 2])
        return slot
    except Exception as e:
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
                except Exception as e:
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
