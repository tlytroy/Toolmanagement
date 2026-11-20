"""SDS §3.1/§3.2 camelCase API schema ↔ snake_case domain dataclass 桥接。

前端与 SDS 契约一律 camelCase；`domain.models` 一律 snake_case frozen dataclass。
本模块是唯一转换层：Pydantic v2 用 `alias_generator=to_camel` 收 camelCase，
`populate_by_name=True` 也收 snake_case（方便测试），`extra='forbid'` 让未知字段
变成 `SCHEMA_UNKNOWN_FIELD`（SDS §4.0）。

★ 本模块不出现比例字段名的任何字面量拼写（含注释）——`test_imaging_m0.py`
  的护栏扫描会遍历 imaging/ 与 tests/ 之外的所有 .py，注释里出现也算命中。
  `correct-image` 端点直接转发 `imaging.api.correct_image_response` 的返回值，
  无需在这里拼装该字段。
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic.alias_generators import to_camel

from domain.models import (
    BoardConfig,
    DomainError,
    FingerHole,
    Project,
    Tool,
    Vec2,
)


class _CamelModel(BaseModel):
    """所有输入模型的基类：camelCase 别名 + 禁止未知字段 + 允许 snake_case。"""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class Vec2In(_CamelModel):
    x: float
    y: float

    def to_domain(self) -> Vec2:
        return Vec2(float(self.x), float(self.y))


class FingerHoleIn(_CamelModel):
    id: str
    x: float
    y: float
    shape: str = "scoop"
    radius: float = 6.0
    width: float = 12.0
    height: float = 12.0
    rotation: float = 0.0
    depth_mode: str = "blind"
    depth: float = 8.0
    chamfer: float = 0.0
    scoop_width: float = 12.0
    scoop_angle_deg: float = 45.0
    scoop_dir: Vec2In = Field(default_factory=lambda: Vec2In(x=1.0, y=0.0))

    def to_domain(self) -> FingerHole:
        return FingerHole(
            id=self.id,
            x=float(self.x),
            y=float(self.y),
            shape=self.shape,
            radius=float(self.radius),
            width=float(self.width),
            height=float(self.height),
            rotation=float(self.rotation),
            depth_mode=self.depth_mode,
            depth=float(self.depth),
            chamfer=float(self.chamfer),
            scoop_width=float(self.scoop_width),
            scoop_angle_deg=float(self.scoop_angle_deg),
            scoop_dir=self.scoop_dir.to_domain(),
        )


class ToolIn(_CamelModel):
    id: str
    name: str = "工具 1"
    outer: list[Vec2In] = Field(default_factory=list)
    interior: list[list[Vec2In]] = Field(default_factory=list)
    finger_holes: list[FingerHoleIn] = Field(default_factory=list)
    clearance_override: float | None = None
    depth_override: float | None = None
    chamfer_override: float | None = None
    source: str = "auto"
    hidden: bool = False

    def to_domain(self) -> Tool:
        return Tool(
            id=self.id,
            name=self.name,
            outer=[p.to_domain() for p in self.outer],
            interior=[[p.to_domain() for p in ring] for ring in self.interior],
            finger_holes=[h.to_domain() for h in self.finger_holes],
            clearance_override=self.clearance_override,
            depth_override=self.depth_override,
            chamfer_override=self.chamfer_override,
            source=self.source,
            hidden=self.hidden,
        )


class BoardIn(_CamelModel):
    shape: str = "rect"
    size_mode: str = "fit-tools"
    width_mm: float | None = None
    height_mm: float | None = None
    margin: float = 12.0
    thickness: int = 12
    corner_r: float = 5.0
    base_edge_roundover: float = 0.0
    units_x: int = 1
    units_y: int = 1
    height_u: int = 3
    magnets: bool = True
    stacking_lip: bool = True
    embed_depth: float = 8.0
    clearance: float = 0.4
    slot_chamfer: float = 1.5
    finger_hole_chamfer: float = 0.5
    want_dxf: bool = False
    dxf_flip_y: bool = True
    print_bed: dict[str, float] = Field(
        default_factory=lambda: {"x": 220.0, "y": 220.0, "z": 220.0}
    )
    split_enabled: bool = True
    pin_diameter: float = 4.0

    def to_domain(self) -> BoardConfig:
        return BoardConfig(
            shape=self.shape,
            size_mode=self.size_mode,
            width_mm=self.width_mm,
            height_mm=self.height_mm,
            margin=float(self.margin),
            thickness=int(self.thickness),
            corner_r=float(self.corner_r),
            base_edge_roundover=float(self.base_edge_roundover),
            units_x=int(self.units_x),
            units_y=int(self.units_y),
            height_u=int(self.height_u),
            magnets=self.magnets,
            stacking_lip=self.stacking_lip,
            embed_depth=float(self.embed_depth),
            clearance=float(self.clearance),
            slot_chamfer=float(self.slot_chamfer),
            finger_hole_chamfer=float(self.finger_hole_chamfer),
            want_dxf=self.want_dxf,
            dxf_flip_y=self.dxf_flip_y,
            print_bed=dict(self.print_bed),
            split_enabled=self.split_enabled,
            pin_diameter=float(self.pin_diameter),
        )


class ProjectIn(_CamelModel):
    schema_version: int = 1
    paper_w: float = 210.0
    paper_h: float = 297.0
    tools: list[ToolIn] = Field(default_factory=list)
    board: BoardIn = Field(default_factory=BoardIn)

    def to_domain(self) -> Project:
        return Project(
            schema_version=int(self.schema_version),
            paper_w=float(self.paper_w),
            paper_h=float(self.paper_h),
            tools=[t.to_domain() for t in self.tools],
            board=self.board.to_domain(),
        )


class SimplifyContourIn(_CamelModel):
    polygon: list[Vec2In]
    tolerance_mm: float = 0.2


class FingerHolesAutoIn(_CamelModel):
    tool: ToolIn
    board: BoardIn = Field(default_factory=BoardIn)


def validation_error_to_detail(exc: ValidationError) -> dict:
    """把 Pydantic ValidationError 压成可执行 detail（字段名 + 类型 + 位置）。"""
    errs = []
    for e in exc.errors():
        errs.append({
            "loc": list(e.get("loc", ())),
            "type": e.get("type"),
            "msg": e.get("msg"),
        })
    return {"validationErrors": errs}


__all__ = [
    "BoardIn",
    "FingerHolesAutoIn",
    "FingerHoleIn",
    "ProjectIn",
    "SimplifyContourIn",
    "ToolIn",
    "Vec2In",
    "DomainError",
    "validation_error_to_detail",
]
