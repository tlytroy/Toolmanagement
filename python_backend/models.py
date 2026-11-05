"""
参数模型定义
============
所有 CAD 生成相关的参数模型集中在此模块，供 cad_engine.py 和 main.py 共享。

包含：
  - BoxParams: 方盒参数（Foam 模式）
  - GridfinityParams: Gridfinity 模式参数
  - InsertParams: 嵌件总配置参数

常量：
  - GRIDFINITY_PITCH, GRIDFINITY_HOLE_DIA, ... 等 CAD 相关常量
"""

from typing import List, Dict, Any, Optional

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