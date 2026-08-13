"""
工具嵌件 3D 模型生成引擎
==========================
基于 trimesh + manifold3d 生成两种模式的嵌件基底：
  - Foam 模式：可自定义长宽高 + 圆角的方盒
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
    ):
        self.length_mm = length_mm
        self.width_mm = width_mm
        self.height_mm = height_mm
        self.fillet_radius = fillet_radius
        self.wall_thickness = wall_thickness

    def to_dict(self) -> dict:
        return {
            "length_mm": self.length_mm,
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "fillet_radius": self.fillet_radius,
            "wall_thickness": self.wall_thickness,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BoxParams":
        return cls(
            length_mm=d.get("length_mm", 200.0),
            width_mm=d.get("width_mm", 150.0),
            height_mm=d.get("height_mm", 20.0),
            fillet_radius=d.get("fillet_radius", 5.0),
            wall_thickness=d.get("wall_thickness", 2.0),
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
    ):
        self.mode = mode
        self.foam = foam or BoxParams()
        self.gridfinity = gridfinity or GridfinityParams()
        self.primitives = primitives or []
        self.tool_offset = tool_offset
        self.embed_depth = embed_depth

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "foam": self.foam.to_dict(),
            "gridfinity": self.gridfinity.to_dict(),
            "tool_offset": self.tool_offset,
            "embed_depth": self.embed_depth,
            "num_primitives": len(self.primitives),
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

        # 2. 工具槽布尔减
        if params.primitives:
            slot = _extrude_tool_slot(
                params.primitives, params.embed_depth,
                params.tool_offset, base_size_x, base_size_y,
            )
            if slot is not None:
                try:
                    if HAS_MANIFOLD:
                        m_base = _trimesh_to_manifold(base)
                        m_slot = _trimesh_to_manifold(slot)
                        base = _manifold_to_trimesh(m_base - m_slot)
                    else:
                        base = base.difference(slot)
                except Exception as e:
                    print(f"布尔运算失败（跳过工具槽）: {e}")

        # 3. 导出 STL
        stl_bytes = io.BytesIO()
        base.export(stl_bytes, file_type="stl")
        stl_base64 = base64.b64encode(stl_bytes.getvalue()).decode("utf-8")

        # 4. 统计
        summary: Dict[str, Any] = {
            "mode": params.mode,
            "vertices": len(base.vertices),
            "faces": len(base.faces),
            "bounds": {
                "x": [float(base.bounds[0][0]), float(base.bounds[1][0])],
                "y": [float(base.bounds[0][1]), float(base.bounds[1][1])],
                "z": [float(base.bounds[0][2]), float(base.bounds[1][2])],
            },
            "volume_mm3": float(base.volume),
        }
        if params.mode == "gridfinity":
            summary.update({
                "units_x": params.gridfinity.units_x,
                "units_y": params.gridfinity.units_y,
                "height_u": params.gridfinity.height_u,
            })
        else:
            summary.update({
                "length_mm": params.foam.length_mm,
                "width_mm": params.foam.width_mm,
                "height_mm": params.foam.height_mm,
                "fillet_radius": params.foam.fillet_radius,
            })

        return {"success": True, "stl_base64": stl_base64, "summary": summary}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def generate_stl(params_dict: dict) -> Dict[str, Any]:
    """从字典参数生成 STL（API 调用入口）"""
    params = InsertParams.from_dict(params_dict)
    return generate_insert(params)


# ── 命令行测试 ────────────────────────────────────────

if __name__ == "__main__":
    # Foam
    r = generate_insert(InsertParams(
        mode="foam",
        foam=BoxParams(200, 150, 20, 5),
        primitives=[{"type": "polyline", "points": [
            {"x": 200, "y": 200}, {"x": 600, "y": 200},
            {"x": 600, "y": 800}, {"x": 200, "y": 800},
            {"x": 200, "y": 200},
        ]}],
        embed_depth=10,
    ))
    print(f"Foam: success={r.get('success')}")
    if r.get("success"):
        s = r["summary"]
        print(f"  Verts={s['vertices']} Faces={s['faces']} Vol={s['volume_mm3']:.0f}mm³")

    # Gridfinity
    r = generate_insert(InsertParams(
        mode="gridfinity",
        gridfinity=GridfinityParams(3, 2, 3),
        embed_depth=10,
    ))
    print(f"Gridfinity: success={r.get('success')}")
    if r.get("success"):
        s = r["summary"]
        print(f"  Verts={s['vertices']} Faces={s['faces']} Vol={s['volume_mm3']:.0f}mm³")