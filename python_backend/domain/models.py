"""M-1 最小领域模型（Python 侧）。

字段名与 SDS §3.1 一一对应（Python 侧 snake_case；camelCase 桥接由序列化层负责）。
本文件只落地 M-1 需要的字段，M0/M1 再扩。

注意：这里刻意**不**建成 `python_backend/models/` 包 —— `python_backend/models.py`
已存在且 `cad_engine.py:59` 是裸 `from models import`，同名包会让旧引擎 ImportError。

★ 校验约定（SDS §12.3）：`BoardConfig.__post_init__` 里任何非法值都抛 `DomainError`。
  它是 `ValueError` 的子类（保持 dataclass / 旧调用方 `except ValueError` 的兼容），
  额外带 `code` / `error_code` / `detail`，路由层据此映射 400 `error.code`（SDS §4.0）。
  判据一律用 `is not None` 与显式比较，**不用 truthiness**（SDS §3.2 修订 #57）。
"""
from __future__ import annotations

from dataclasses import dataclass, field


class DomainError(ValueError):
    """领域校验失败（带错误码）。

    `ValueError` 子类的理由：`@dataclass(frozen=True)` 的 `__post_init__` 约定抛
    `ValueError`，且 M0 的调用方已经在 `except ValueError` 上兜底；子类化后两者都能接住，
    同时 `error.code` 让路由层不必匹配中文串（SDS §4.0「禁止匹配中文串」）。
    """

    def __init__(self, code: str, message: str, detail: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.error_code = code          # 两种读法都支持，避免上游各自约定
        self.message = message
        self.detail = detail or {}


@dataclass(frozen=True)
class Vec2:
    """纸面毫米坐标（y-down）或板局部毫米坐标（y-up），由上下文决定。"""

    x: float
    y: float


@dataclass(frozen=True)
class FingerHole:
    """手孔。M-1 只占位，几何在 §7.4 / M1.5 实现。"""

    id: str
    x: float
    y: float
    shape: str = "scoop"          # 'scoop'|'sphere'|'cylinder'|'square'|'rect'|'filleted_rect'
    radius: float = 6.0
    width: float = 12.0
    height: float = 12.0
    rotation: float = 0.0         # 绕 Z，度，逆时针
    depth_mode: str = "blind"     # 'blind' | 'through'
    depth: float = 8.0
    chamfer: float = 0.0
    scoop_width: float = 12.0     # 仅 scoop，范围 10..15
    scoop_angle_deg: float = 45.0
    scoop_dir: Vec2 = field(default_factory=lambda: Vec2(1.0, 0.0))


@dataclass(frozen=True)
class Tool:
    id: str
    name: str = "工具 1"
    outer: list[Vec2] = field(default_factory=list)          # 纸面 mm
    interior: list[list[Vec2]] = field(default_factory=list)  # 纸面 mm
    finger_holes: list[FingerHole] = field(default_factory=list)
    clearance_override: float | None = None
    depth_override: float | None = None
    chamfer_override: float | None = None
    source: str = "auto"
    hidden: bool = False


# —— 板参数值域（SDS §3.1；改这里等于改契约，必须同步 SDS）——
ALLOWED_SHAPES = ("rect", "gridfinity")
ALLOWED_SIZE_MODES = ("fit-tools", "custom", "print-bed")
ALLOWED_THICKNESS = (6, 12, 25)      # SDS §3.1：只允许 6 / 12 / 25
HEIGHT_U_RANGE = (1, 20)             # 含端值
UNITS_RANGE = (1, 40)                # 含端值


def _as_int(value) -> int | None:
    """整数值（含 `3.0` 这种整值浮点）；非整数返回 None。bool 不算整数。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _depth_limit_mm(board: "BoardConfig") -> float:
    """`embed_depth` 的上界（唯一真源：`geometry/constants.py:board_depth_limit`）。

    ★ 用**函数内导入**而不是模块级：`geometry/__init__.py` 在导入时反向
      `from domain.models import ...`，模块级互导会成环（ImportError: Project）。
    ★ `except ModuleNotFoundError` 只吞「顶层 `geometry` 不可见」这一种情况：以
      `python_backend.domain.models` 旧路径导入、且 `python_backend` 不在 `sys.path` 时
      （M0 imaging 测试就是这样跑的）会走到这里，此时整个 geometry 包都不可见，只能用
      同一公式的本地副本 —— **改 `geometry/constants.py` 时必须同步改这里**。
      其它任何导入错误（含 geometry 内部自己 ImportError）都原样上抛。
    """
    try:
        from geometry.constants import board_depth_limit
    except ModuleNotFoundError as exc:
        if (exc.name or "").split(".")[0] != "geometry":
            raise
        if board.shape == "gridfinity":
            return float(board.height_u) * 7.0 - 4.75 - 2.0
        return float(board.thickness) - 2.0
    return float(board_depth_limit(board))


@dataclass(frozen=True)
class BoardConfig:
    shape: str = "rect"                  # 'rect' | 'gridfinity'
    size_mode: str = "fit-tools"         # 'fit-tools' | 'custom' | 'print-bed'
    width_mm: float | None = None        # 仅 'custom'
    height_mm: float | None = None       # 仅 'custom'
    margin: float = 12.0                 # 仅 size_mode='fit-tools' 生效
    thickness: int = 12                  # 6 | 12 | 25，仅 rect
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
    print_bed: dict = field(default_factory=lambda: {"x": 220.0, "y": 220.0, "z": 220.0})
    split_enabled: bool = True           # SDS §3.2 默认 True（§8.1 依赖它）
    pin_diameter: float = 4.0

    def __post_init__(self) -> None:
        # —— 1. 外形 ——（先校验，后面的 depth 上界要用它分支）
        if self.shape not in ALLOWED_SHAPES:
            raise DomainError(
                "INVALID_SHAPE",
                "shape 必须是 'rect' | 'gridfinity'",
                {"shape": self.shape},
            )

        # —— 2. sizeMode 与宽高同进同退 ——
        # 判据是 is not None（非 custom 模式下前端发 null 是合法的，不得 400）。
        if self.size_mode not in ALLOWED_SIZE_MODES:
            raise DomainError(
                "INVALID_SIZE_MODE",
                "sizeMode 必须是 'fit-tools' | 'custom' | 'print-bed'",
                {"sizeMode": self.size_mode},
            )
        if self.size_mode == "custom":
            if self.width_mm is None or self.height_mm is None:
                raise DomainError(
                    "INVALID_SIZE_MODE",
                    "sizeMode='custom' 必须同时给 widthMm 和 heightMm",
                    {"widthMm": self.width_mm, "heightMm": self.height_mm},
                )
            if not (60.0 <= float(self.width_mm) <= 400.0):
                raise DomainError("INVALID_SIZE_MODE", "widthMm 必须在 60..400 之间",
                                  {"widthMm": self.width_mm})
            if not (60.0 <= float(self.height_mm) <= 400.0):
                raise DomainError("INVALID_SIZE_MODE", "heightMm 必须在 60..400 之间",
                                  {"heightMm": self.height_mm})
        elif self.width_mm is not None or self.height_mm is not None:
            raise DomainError(
                "INVALID_SIZE_MODE",
                "widthMm/heightMm 仅在 sizeMode='custom' 时允许出现",
                {"sizeMode": self.size_mode, "widthMm": self.width_mm,
                 "heightMm": self.height_mm},
            )

        # —— 3. 板厚（SDS §3.1：只允许 6 / 12 / 25）——
        if self.thickness not in ALLOWED_THICKNESS:
            raise DomainError(
                "INVALID_THICKNESS",
                "thickness 必须是 6 | 12 | 25（SDS §3.1）",
                {"thickness": self.thickness},
            )

        # —— 4. gridfinity 格数与高度 ——
        h_u = _as_int(self.height_u)
        if h_u is None or not (HEIGHT_U_RANGE[0] <= h_u <= HEIGHT_U_RANGE[1]):
            raise DomainError(
                "INVALID_HEIGHT_U",
                f"heightU 必须是 {HEIGHT_U_RANGE[0]}..{HEIGHT_U_RANGE[1]} 的整数",
                {"heightU": self.height_u},
            )
        for name in ("units_x", "units_y"):
            value = _as_int(getattr(self, name))
            if value is None or not (UNITS_RANGE[0] <= value <= UNITS_RANGE[1]):
                raise DomainError(
                    "INVALID_UNITS",
                    f"{name} 必须是 {UNITS_RANGE[0]}..{UNITS_RANGE[1]} 的整数",
                    {name: getattr(self, name)},
                )

        # —— 5. 通用量 ——
        # 负间隙会被 polygon.py 的 `if clearance > 0` 静默跳过（用户以为缩了 1mm），必须拦。
        if not (self.clearance >= 0.0):
            raise DomainError("INVALID_CLEARANCE", "clearance 必须 >= 0",
                              {"clearance": self.clearance})

        # margin 必须大于 clearance，否则 §7.4 的 run 上界恒为负、scoop 无解。
        if not (self.margin >= self.clearance + 0.5):
            raise DomainError(
                "INVALID_MARGIN",
                "margin 必须 >= clearance + 0.5",
                {"margin": self.margin, "clearance": self.clearance},
            )

        # embedDepth：> 0 且 <= 板顶可用深度（rect 与 gridfinity 上界不同）。
        # 注意越界在**模型层**就阻断；运行期的 clamp + DEPTH_EXCEEDS_THICKNESS warning
        # 仍然保留给 `generate_insert(depth=...)` / `tool.depth_override` 这两条入口。
        if not (self.embed_depth > 0.0):
            raise DomainError("INVALID_EMBED_DEPTH", "embedDepth 必须 > 0",
                              {"embedDepth": self.embed_depth})
        limit = _depth_limit_mm(self)
        if float(self.embed_depth) > limit + 1e-9:
            raise DomainError(
                "INVALID_EMBED_DEPTH",
                f"embedDepth 不得超过 {limit}mm（shape={self.shape}）",
                {"embedDepth": self.embed_depth, "maxEmbed": limit, "shape": self.shape},
            )

        # cornerR：非负；custom 下还不得超过短边的一半（否则 offset(-r) 把矩形吃空）。
        if not (self.corner_r >= 0.0):
            raise DomainError("INVALID_CORNER_R", "cornerR 必须 >= 0",
                              {"cornerR": self.corner_r})
        if self.size_mode == "custom":
            half = min(float(self.width_mm), float(self.height_mm)) / 2.0
            if float(self.corner_r) > half:
                raise DomainError(
                    "INVALID_CORNER_R",
                    f"cornerR 不得超过短边的一半（{half}mm）",
                    {"cornerR": self.corner_r, "maxCornerR": half},
                )

        # 倒角量为负会让 scale_top/倒角锥台方向反掉，直接拦。
        if not (self.slot_chamfer >= 0.0):
            raise DomainError("INVALID_CHAMFER", "slotChamfer 必须 >= 0",
                              {"slotChamfer": self.slot_chamfer})
        if not (self.finger_hole_chamfer >= 0.0):
            raise DomainError("INVALID_CHAMFER", "fingerHoleChamfer 必须 >= 0",
                              {"fingerHoleChamfer": self.finger_hole_chamfer})


@dataclass(frozen=True)
class Project:
    """M-1 只做几何所需的四件套。"""

    schema_version: int = 1
    paper_w: float = 210.0
    paper_h: float = 297.0
    tools: list[Tool] = field(default_factory=list)
    board: BoardConfig = field(default_factory=BoardConfig)
