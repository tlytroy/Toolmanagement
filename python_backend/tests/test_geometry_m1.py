"""M-1 正式 pytest：`geometry/` 的 DoD（替代只靠 `sys.exit` 报信的冒烟脚本）。

运行（**项目根**下，与 `scripts/smoke_geometry.py` 同口径）：
    .venv/bin/python -m pytest -q python_backend/tests/test_geometry_m1.py

★ 导入根是 `python_backend/`（`cd python_backend && uvicorn main:app` 的运行时口径），
  所以这里只往 `sys.path` 塞 `python_backend`，导入写 `from geometry import ...` /
  `from domain.models import ...`。**不要**再塞仓库根：那会让 `geometry` 同时以
  `geometry` 和 `python_backend.geometry` 两个名字各加载一份，`GeometryError` 变成两个
  不同的类，`pytest.raises` 会莫名其妙抓不到。

★ 每条断言都写成「会红」的形式，且**量的都是真实几何**（体积 / 射线 / bbox / 槽长），
  不是拿函数返回值自证：
  1. `test_pocket_overhang_and_raycast`        —— 冒烟 ①②（F1 开口为真、首击在槽底）
  2. `test_pocket_length_zero_clearance`       —— 冒烟 ③（槽长 100 ± 0.1）
  3. `test_clearance_changes_pocket_length`    —— 新增：间隙真的进槽长（100.8 ± 0.05）
  4. `test_tool_out_of_board_raises`           —— 新增：custom 60×60 + 200×100 → 阻断
  5. `test_no_duplicate_warnings_*`            —— 审核缺陷 1：同一告警只能出现一次
  6. `test_depth_exceeds_thickness_in_envelope`—— 审核缺陷 2：clamp 必须进 `warnings[]`
  7. `test_board_config_rejects_*`             —— 审核缺陷 6/7：非法板参数带码拒绝
  8. `test_split_enabled_default_is_true`      —— 审核缺陷 4：SDS §3.2 默认值
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pytest
import trimesh

# ★ 只塞 python_backend（见模块 docstring）
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from domain.models import (  # noqa: E402
    ALLOWED_THICKNESS,
    BoardConfig,
    DomainError,
    Project,
    Tool,
    Vec2,
)
from geometry import GeometryError, generate_insert  # noqa: E402

PAPER_W, PAPER_H = 210.0, 297.0
TOOL_W, TOOL_H = 100.0, 20.0
THICKNESS = 12
EMBED = 8.0
EXPECTED_POCKET_LEN = 100.0


# ---------------------------------------------------------------- fixtures
def _rect_outer(w: float = TOOL_W, h: float = TOOL_H) -> list[Vec2]:
    """纸面坐标、居中于纸心的 w×h 矩形（CCW，y-down 下看是顺时针，无所谓）。"""
    cx, cy = PAPER_W / 2.0, PAPER_H / 2.0
    hw, hh = w / 2.0, h / 2.0
    return [
        Vec2(cx - hw, cy - hh),
        Vec2(cx + hw, cy - hh),
        Vec2(cx + hw, cy + hh),
        Vec2(cx - hw, cy + hh),
    ]


def build_project(
    clearance: float = 0.0,
    slot_chamfer: float = 0.0,
    board: BoardConfig | None = None,
    tools: list[Tool] | None = None,
) -> Project:
    """合成件：100×20 矩形 + fit-tools 12mm 板。

    ★ `clearance=0.0` / `slot_chamfer=0.0` 必须显式给：默认 0.4 / 1.5 会让槽长变 100.8、
      切刀 bbox 撑宽 3mm（第③条与 bbox 断言都会假红）。
    """
    if board is None:
        board = BoardConfig(
            shape="rect", size_mode="fit-tools", margin=12.0,
            thickness=THICKNESS, corner_r=5.0, embed_depth=EMBED,
            clearance=clearance, slot_chamfer=slot_chamfer,
        )
    if tools is None:
        tools = [Tool(id="tool_1", name="合成 100x20", outer=_rect_outer())]
    return Project(schema_version=1, paper_w=PAPER_W, paper_h=PAPER_H,
                   tools=tools, board=board)


def to_trimesh(m) -> trimesh.Trimesh:
    """manifold3d.Manifold → trimesh.Trimesh（SDS §10.1 实测写法）。"""
    mesh = m.to_mesh()
    verts = np.asarray(mesh.vert_properties)[:, :3].astype(float)
    faces = np.asarray(mesh.tri_verts)
    return trimesh.Trimesh(vertices=verts, faces=faces, process=False)


def _codes(result: dict) -> list[str]:
    return [w["code"] for w in result["warnings"]]


# ---------------------------------------------------------------- 冒烟 ①②③
def test_pocket_overhang_and_raycast() -> None:
    """① 切刀刺出顶面 1mm（F1 修复本体）；② 竖直射线的首击落在槽底。"""
    result = generate_insert(build_project())
    top_z = result["top_z"]
    depth = result["tools"][0]["depth"]
    bb = result["slot_cutter"].bounding_box()      # 扁平 6 元组

    # ① 出顶量 ∈ [0.9, 1.0+1e-6]（SDS §2.3 / §10.3 区间，两处口径同时满足）
    assert 0.9 <= bb[5] - top_z <= 1.0 + 1e-6, (
        f"① 切刀未按 1mm 刺出顶面：bb[5]-top_z={bb[5] - top_z}"
    )
    # 槽底不得穿板底
    assert bb[2] >= 0.0, f"槽底穿板底：bb[2]={bb[2]}"

    # ② 从槽心正上方向下打射线，首击必须在槽底而不是板顶
    mesh = to_trimesh(result["base"])
    loc, _, _ = mesh.ray.intersects_location(
        ray_origins=[[0.0, 0.0, top_z + 10.0]],
        ray_directions=[[0.0, 0.0, -1.0]],
    )
    assert len(loc) > 0, "② 射线打空（槽被切成通孔或切刀没切到板）"
    first_hit = max(float(p[2]) for p in loc)      # loc 不按距离排序
    assert abs(first_hit - (top_z - depth)) < 0.05, (
        f"② 首击不在槽底：first_hit={first_hit}，期望 {top_z - depth}"
    )

    # 顺带量真实体积：100×20×8 = 16000（±1，容差表 SDS §10.3）
    removed = result["base_uncut"].volume() - result["base"].volume()
    assert abs(removed - TOOL_W * TOOL_H * EMBED) < 1.0, f"切除体积不对：{removed}"


def test_pocket_length_zero_clearance() -> None:
    """③ 槽长 = 工具 x 跨度 = 100.0（容差 0.1，SDS §10.3）。"""
    result = generate_insert(build_project(clearance=0.0))
    assert abs(result["pocket_length_mm"] - EXPECTED_POCKET_LEN) < 0.1, (
        f"③ 槽长不对：{result['pocket_length_mm']}"
    )


def test_clearance_changes_pocket_length() -> None:
    """间隙必须真的进槽长：clearance=0.4 → 100.8（±0.05）。

    ★ 这条同时守住"先 simplify 后 buffer"的顺序（SDS §7.3 第 4-5 步）：顺序反了会被
      简化啃掉一部分间隙，实测变成 100.65 左右，直接红。
    """
    result = generate_insert(build_project(clearance=0.4))
    got = result["pocket_length_mm"]
    assert abs(got - 100.8) < 0.05, f"clearance=0.4 时槽长应为 100.8，实得 {got}"
    assert result["tools"][0]["clearance"] == pytest.approx(0.4)


# ---------------------------------------------------------------- tools_in_board
def test_tool_out_of_board_raises() -> None:
    """`tools_in_board`（SDS §7.6 第 9 条，**阻断**）：custom 60×60 + 200×100 工具 → 抛。

    ★ 修复前实测：不报错，`removed=28624.29`（板总体积仅 43200），静默产出废板。
    """
    board = BoardConfig(
        shape="rect", size_mode="custom", width_mm=60.0, height_mm=60.0,
        margin=12.0, thickness=THICKNESS, corner_r=5.0, embed_depth=EMBED,
        clearance=0.0, slot_chamfer=0.0,
    )
    project = build_project(board=board, tools=[Tool(id="big", outer=_rect_outer(200.0, 100.0))])

    with pytest.raises(GeometryError) as excinfo:
        generate_insert(project)
    err = excinfo.value
    assert err.code == "TOOL_OUT_OF_BOARD", f"错误码不对：{err.code}"
    # detail 必须可执行（SDS §7.6 第 10 条：不准只给一个错误码）
    for key in ("toolId", "boardMm", "toolBBox", "exits"):
        assert key in err.detail, f"detail 缺 {key}：{err.detail}"
    assert err.detail["toolId"] == "big"
    assert err.detail["boardMm"] == (60.0, 60.0)
    assert len(err.detail["exits"]) == 3


def test_fit_tools_never_out_of_board() -> None:
    """`fit-tools` 是回归锚：板按工具并集算，永远不该触发 `TOOL_OUT_OF_BOARD`。"""
    result = generate_insert(build_project())      # 不抛即通过
    w, h = result["board_mm"]
    assert (w, h) == pytest.approx((TOOL_W + 2 * 12.0, TOOL_H + 2 * 12.0))


# ---------------------------------------------------------------- 缺陷 1：warnings 重复
def _bowtie_outer() -> list[Vec2]:
    """自交的"蝴蝶结"轮廓（buffer(0) 会修复它并告警）。"""
    cx, cy = PAPER_W / 2.0, PAPER_H / 2.0
    return [
        Vec2(cx - 50.0, cy - 10.0),
        Vec2(cx + 50.0, cy + 10.0),
        Vec2(cx + 50.0, cy - 10.0),
        Vec2(cx - 50.0, cy + 10.0),
    ]


def test_no_duplicate_self_intersection_warning() -> None:
    """自交轮廓只准产生 **1 条** `SELF_INTERSECTION_REPAIRED`（修复前是 2 条）。"""
    project = build_project(tools=[Tool(id="bow", outer=_bowtie_outer())])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")            # 只关心信封，不关心 Python warnings
        result = generate_insert(project)
    codes = _codes(result)
    assert codes.count("SELF_INTERSECTION_REPAIRED") == 1, f"告警重复：{codes}"


def test_no_duplicate_clearance_closed_hole_warning() -> None:
    """小孔被间隙填实只准告警 **1 次** `CLEARANCE_CLOSED_HOLE`（修复前是 2 次）。"""
    cx, cy = PAPER_W / 2.0, PAPER_H / 2.0
    outer = _rect_outer()
    # r=0.3 的方孔：clearance 0.4 会把它填实
    hole = [
        Vec2(cx - 0.3, cy - 0.3), Vec2(cx + 0.3, cy - 0.3),
        Vec2(cx + 0.3, cy + 0.3), Vec2(cx - 0.3, cy + 0.3),
    ]
    project = build_project(
        clearance=0.4,
        tools=[Tool(id="tiny_hole", outer=outer, interior=[hole])],
    )
    result = generate_insert(project)
    codes = _codes(result)
    assert codes.count("CLEARANCE_CLOSED_HOLE") == 1, f"告警重复：{codes}"


# ---------------------------------------------------------------- 缺陷 2：深度 clamp 进信封
def test_depth_exceeds_thickness_in_envelope() -> None:
    """`embed_depth` 超上界 → clamp，且 `DEPTH_EXCEEDS_THICKNESS` **必须进 `warnings[]`**。

    修复前：Python 侧 `warnings.warn` 能捕到，但 `generate_insert(...)['warnings'] == []`。
    这里同时验两条入口（显式 `depth=` 形参 / `tool.depth_override`），并验**只发一次**。
    """
    # 入口 A：显式 depth=20（rect 12mm 的上界 = 10）
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = generate_insert(build_project(), depth=20.0)
    assert result["tools"][0]["depth"] == pytest.approx(10.0)
    codes = _codes(result)
    assert codes.count("DEPTH_EXCEEDS_THICKNESS") == 1, f"信封告警不对：{codes}"
    warn = next(w for w in result["warnings"] if w["code"] == "DEPTH_EXCEEDS_THICKNESS")
    assert warn["detail"]["requested"] == pytest.approx(20.0)
    assert warn["detail"]["clamped_to"] == pytest.approx(10.0)
    assert any("DEPTH_EXCEEDS_THICKNESS" in str(c.message) for c in caught), \
        "Python 侧 warnings.warn 被删掉了（不破坏既有行为）"

    # 入口 B：tool.depth_override=20（同样只告警一次）
    project = build_project(
        tools=[Tool(id="tool_1", outer=_rect_outer(), depth_override=20.0)]
    )
    result_b = generate_insert(project)
    assert result_b["tools"][0]["depth"] == pytest.approx(10.0)
    assert _codes(result_b).count("DEPTH_EXCEEDS_THICKNESS") == 1


# ---------------------------------------------------------------- 缺陷 4：默认值
def test_split_enabled_default_is_true() -> None:
    """SDS §3.2 写 `split_enabled: bool = True`（§8.1 的"板超打印床"分支依赖它）。"""
    assert BoardConfig().split_enabled is True


# ---------------------------------------------------------------- 缺陷 6/7：板参数校验
def _expect(code: str, **kwargs) -> None:
    with pytest.raises(DomainError) as excinfo:
        BoardConfig(**kwargs)
    err = excinfo.value
    assert err.code == code, f"错误码应为 {code}，实得 {err.code}（{err}）"
    # dataclass 约定仍要能按 ValueError 接住（旧调用方兼容）
    assert isinstance(err, ValueError)
    assert err.error_code == code


def test_board_config_rejects_bad_shape() -> None:
    _expect("INVALID_SHAPE", shape="banana")


@pytest.mark.parametrize("thickness", [10, 100, 7, 0])
def test_board_config_rejects_bad_thickness(thickness) -> None:
    _expect("INVALID_THICKNESS", thickness=thickness)


@pytest.mark.parametrize("thickness", list(ALLOWED_THICKNESS))
def test_board_config_accepts_allowed_thickness(thickness) -> None:
    """三个合法板厚都可用。

    ★ 必须显式给 `embed_depth`：6mm 板的上界只有 `6 - 2 = 4`，而 `embed_depth` 默认 8，
      直接用默认值会（正确地）被 `INVALID_EMBED_DEPTH` 拒掉 —— 这不是 bug，是 SDS §3.1
      「rect 的 embedDepth 范围是 [2, thickness-2]」与「thickness 默认 12」共同决定的：
      调用方把 thickness 改成 6 时必须同时下调 embedDepth（前端滑块上界同理）。
    """
    embed = 2.0 if thickness == 6 else 8.0
    board = BoardConfig(thickness=thickness, embed_depth=embed)
    assert board.thickness == thickness
    assert board.embed_depth == embed


def test_thickness6_default_embed_depth_is_rejected() -> None:
    """显式钉住上面那条交互：6mm 板 + 默认 embedDepth=8 必须被拒（否则切穿板底）。"""
    _expect("INVALID_EMBED_DEPTH", thickness=6)


@pytest.mark.parametrize("height_u", [99, 0, -1, 2.5])
def test_board_config_rejects_bad_height_u(height_u) -> None:
    _expect("INVALID_HEIGHT_U", height_u=height_u)


@pytest.mark.parametrize("field_name", ["units_x", "units_y"])
@pytest.mark.parametrize("value", [999, 0, -3])
def test_board_config_rejects_bad_units(field_name, value) -> None:
    _expect("INVALID_UNITS", **{field_name: value})


def test_board_config_rejects_negative_clearance() -> None:
    """负间隙会被 `polygon.py` 的 `if clearance > 0` 静默跳过（用户以为缩了 1mm）。"""
    _expect("INVALID_CLEARANCE", clearance=-1.0)


@pytest.mark.parametrize("embed_depth", [-5.0, 0.0, 20.0])
def test_board_config_rejects_bad_embed_depth(embed_depth) -> None:
    """`embed_depth` 非法必须在模型层就报 `INVALID_EMBED_DEPTH`，不能拖到 pockets.py。"""
    _expect("INVALID_EMBED_DEPTH", embed_depth=embed_depth)


def test_board_config_gridfinity_embed_limit() -> None:
    """gridfinity 的上界是 `heightU*7 - 4.75 - 2`（3U → 14.25），不是 thickness-2。"""
    assert BoardConfig(shape="gridfinity", height_u=3, embed_depth=14.0).embed_depth == 14.0
    _expect("INVALID_EMBED_DEPTH", shape="gridfinity", height_u=3, embed_depth=15.0)


def test_board_config_rejects_bad_corner_r() -> None:
    _expect("INVALID_CORNER_R", corner_r=-1.0)
    _expect("INVALID_CORNER_R", size_mode="custom", width_mm=60.0, height_mm=60.0,
            corner_r=40.0)


def test_board_config_rejects_negative_chamfer() -> None:
    _expect("INVALID_CHAMFER", slot_chamfer=-0.5)
    _expect("INVALID_CHAMFER", finger_hole_chamfer=-0.5)


@pytest.mark.parametrize("kwargs", [
    {"size_mode": "banana"},
    {"size_mode": "custom"},                                  # 缺宽高
    {"size_mode": "custom", "width_mm": 100.0},               # 缺 height
    {"size_mode": "custom", "width_mm": 10.0, "height_mm": 100.0},   # 太小
    {"size_mode": "fit-tools", "width_mm": 100.0},            # 非 custom 带宽高
])
def test_board_config_size_mode_errors_carry_code(kwargs) -> None:
    """§12.3：`sizeMode` 与宽高不同进同退 → 必须带 `INVALID_SIZE_MODE`（不是裸 ValueError）。"""
    _expect("INVALID_SIZE_MODE", **kwargs)


def test_board_config_default_is_valid() -> None:
    """默认参数本身必须过校验（防止新校验把默认值自己判非法）。"""
    board = BoardConfig()
    assert (board.shape, board.thickness, board.embed_depth) == ("rect", 12, 8.0)
