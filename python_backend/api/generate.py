"""`/api/generate` 的实现核心（SDS §4.5）。

输入是 camelCase `ProjectIn`，输出是 `(ok, data, error_code, error_message,
error_detail, warnings)` 六元组；`main.py` 的路由只负责把它转成 `_ok`/`_fail`
信封。这样逻辑可独立测试，信封保持单一实现。

★ 全部 checks 用真实几何量，不用函数返回值自证：
  - 3D 项走 `geometry.validate.validate_3d`（manifold status / watertight /
    winding / components / self_intersection / genus / volume_match）；
  - 2D 项走 `validate_2d`（shapely_valid / area_positive / min_rib），
    相邻槽轮廓用 `pocket_shape` 重算（纯函数，幂等）；
  - `tools_in_board` 独立重算槽轮廓并量 bbox（不靠 generate_insert 内部已断言）；
  - `slot_open` 对每把工具中心做一次向下 raycast，首击 z 必须落在槽底 ±0.05；
  - `depth_fits` 判**请求值**（先 clamp 再断言会恒真），回传 maxEmbed。
"""
from __future__ import annotations

import os

import manifold3d as mf
import trimesh

from domain.models import DomainError, Project
from geometry import (
    GeometryError,
    board_center,
    board_depth_limit,
    board_top_z,
    generate_insert,
    pocket_shape,
    resolve_clearance,
    resolve_depth,
)
from geometry.validate import (
    ADVISORY_CHECKS,
    BLOCKING_CHECKS,
    CheckResult,
    _to_trimesh,
    summarize,
    validate_2d,
    validate_3d,
)
from api.errors import error_payload
from api.schemas import ProjectIn, validation_error_to_detail
from export.stl import manifold_to_stl_base64

from pydantic import ValidationError

# SDS §4.5 的 blocking/advisory 分组（validate.py 自带集合不含后三项，这里补齐）
_BLOCKING = set(BLOCKING_CHECKS) | {"tools_in_board", "slot_open"}
_ADVISORY = set(ADVISORY_CHECKS) | {"depth_fits"}


def engine_name() -> str:
    """`GEO_ENGINE` 只读作配置记录；新端点恒用新引擎（见 PROJECT_STATUS §4.1）。

    旧 8 个端点不读这个变量，因此其行为不受影响。返回归一化后的取值。
    """
    return (os.environ.get("GEO_ENGINE") or "new").strip().lower()


def _bounds(m) -> list[list[float]]:
    """扁平 6 元组 → SDS §4.5 的 `[[x0,y0,z0],[x1,y1,z1]]`。"""
    b = list(m.bounding_box())
    return [[float(v) for v in b[:3]], [float(v) for v in b[3:6]]]


def _check_tools_in_board(project: Project, center) -> CheckResult:
    """独立重算每个槽轮廓并查板框（不复用 generate_insert 内部的断言结果）。"""
    board = project.board
    from geometry.board import board_size_mm

    size = board_size_mm(board, [t for t in project.tools if not t.hidden])
    half_w, half_h = size[0] / 2.0, size[1] / 2.0
    bad = []
    for t in project.tools:
        if t.hidden or len(t.outer) < 3:
            continue
        shape = pocket_shape(t, board, center, None, clearance=resolve_clearance(t, board))
        x0, y0, x1, y1 = shape.bounds
        if x0 < -half_w - 1e-6 or x1 > half_w + 1e-6 or y0 < -half_h - 1e-6 or y1 > half_h + 1e-6:
            bad.append({"toolId": t.id, "bbox": [x0, y0, x1, y1]})
    return CheckResult("tools_in_board", not bad, {"boardMm": [size[0], size[1]], "violations": bad})


def _check_slot_open(result: dict, project: Project, center) -> CheckResult:
    """每把工具中心向下 raycast，首击必须落在 `top_z - depth` ±0.05。"""
    mesh = _to_trimesh(result["base"])
    top_z = float(result["top_z"])
    hits_detail = []
    all_ok = True
    reports = {r["id"]: r for r in result["tools"]}
    for t in project.tools:
        if t.hidden or len(t.outer) < 3:
            continue
        board = project.board
        shape = pocket_shape(t, board, center, None, clearance=resolve_clearance(t, board))
        cx, cy = shape.centroid.coords[0]
        # trimesh 5.x 返回 (points, ray_indices, triangle_indices) 三元组
        locs, _, _ = mesh.ray.intersects_location(
            ray_origins=[[cx, cy, top_z + 10.0]],
            ray_directions=[[0.0, 0.0, -1.0]],
        )
        first = max((float(p[2]) for p in locs), default=None)
        depth = float(reports[t.id]["depth"])
        expected = top_z - depth
        ok = first is not None and abs(first - expected) <= 0.05
        all_ok = all_ok and ok
        hits_detail.append({
            "toolId": t.id, "firstHitZ": first, "expectedZ": expected,
        })
    return CheckResult("slot_open", all_ok, {"hits": hits_detail, "toleranceMm": 0.05})


def _check_depth_fits(project: Project) -> CheckResult:
    """判请求值，不判 clamp 后的值（否则恒真）。"""
    board = project.board
    max_embed = board_depth_limit(board)
    requested = float(board.embed_depth)
    clamped = min(requested, max_embed)
    ok = requested <= max_embed + 1e-9
    return CheckResult("depth_fits", ok, {
        "requested": requested, "clampedTo": clamped, "maxEmbed": max_embed,
    })


def build_generate_data(project_in: ProjectIn) -> dict:
    """成功时返回 SDS §4.5 的 `data`；抛 DomainError/GeometryError/ValidationError。

    blocking 检查失败时抛 `GeometryError("GEOMETRY_INVALID", detail.failedChecks=...)`；
    advisory 检查失败不抛，转成 `warnings[]`（由调用方追加）。
    """
    project = project_in.to_domain()   # ValidationError / DomainError 向上抛
    board = project.board
    center = board_center([t for t in project.tools if not t.hidden])
    result = generate_insert(project)

    base = result["base"]
    base_uncut = result["base_uncut"]
    slot_cutter = result["slot_cutter"]
    top_z = float(result["top_z"])

    # volume_match 期望值：切刀要裁到板体 z∈[0, top_z]，不能用切刀全量。
    # 切刀在顶面上方有 TOP_OVERHANG_MM=1mm 刺出 + 倒角锥台，全量会虚高 ~4.5%。
    board_size = result["board_mm"]
    board_box = mf.Manifold.cube(
        [float(board_size[0]), float(board_size[1]), top_z], center=False
    ).translate([-float(board_size[0]) / 2.0, -float(board_size[1]) / 2.0, 0.0])
    cut_inside = slot_cutter ^ board_box

    # —— checks ——
    checks: list[CheckResult] = []
    checks += validate_3d(
        base,
        expected_volume=float(base_uncut.volume()) - float(cut_inside.volume()),
        expected_genus=sum(len(t.interior) for t in project.tools if not t.hidden),
        label="board",
    )
    shapes = []
    for t in project.tools:
        if t.hidden or len(t.outer) < 3:
            continue
        shape = pocket_shape(t, board, center, None, clearance=resolve_clearance(t, board))
        shapes.append(shape)
    for i, shape in enumerate(shapes):
        checks += validate_2d(
            shape,
            label=f"tool[{i}]",
            min_rib_mm=2.0,
            others=[s for j, s in enumerate(shapes) if j != i],
        )
    checks.append(_check_tools_in_board(project, center))
    checks.append(_check_slot_open(result, project, center))
    checks.append(_check_depth_fits(project))

    # —— blocking 判定 ——
    failed_blocking = [c.name for c in checks if not c.ok and c.name in _BLOCKING]
    if failed_blocking:
        raise GeometryError(
            "GEOMETRY_INVALID",
            "几何自检未通过：" + "、".join(failed_blocking),
            {"failedChecks": failed_blocking},
        )

    # —— STL ——
    stl_b64, _ = manifold_to_stl_base64(base)

    # —— paramsEcho ——
    params_echo = {
        "sizeMode": board.size_mode,
        "widthMm": board.width_mm,
        "heightMm": board.height_mm,
        "margin": board.margin,
        "cornerR": board.corner_r,
        "baseEdgeRoundover": board.base_edge_roundover,
        "slotChamfer": board.slot_chamfer,
        "embedDepth": board.embed_depth,
        "clearance": board.clearance,
        "unitsX": board.units_x,
        "unitsY": board.units_y,
    }

    data = {
        "pieces": [{
            "index": 0,
            "name": "board",
            "stlBase64": stl_b64,
            "bboxMm": _bounds(base),
            "volumeMm3": float(base.volume()),
        }],
        "summary": {
            "toolCount": len(result["tools"]),
            "pieceCount": 1,
            "boardMm": list(result["board_mm"]),
            "totalVolumeMm3": float(base.volume()),
            "paramsEcho": params_echo,
            "slotBounds": _bounds(slot_cutter),
            "baseBounds": _bounds(base_uncut),
        },
        # SDS §4.5：checks 是 data 顶层字段（10 项），不在 summary 内
        "checks": [c.to_dict() for c in checks],
    }
    return data


def generate_response(project_in: ProjectIn) -> tuple[bool, dict | None, str | None, str | None, dict | None, list[dict]]:
    """六元组：`ok, data, code, message, detail, advisory_warnings`。

    路由层据 `ok` 调 `_ok` 或 `_fail`。advisory 失败在这里转成 `warnings[]`，
    成功与失败都要带（失败时也要告诉用户哪些非阻断项没过）。
    """
    warnings: list[dict] = []
    try:
        data = build_generate_data(project_in)
    except ValidationError as exc:
        detail = validation_error_to_detail(exc)
        errs = detail.get("validationErrors", [])
        # 未知字段 → SCHEMA_UNKNOWN_FIELD；其余归 GEOMETRY_INVALID 的字段错误
        if any(e.get("type") == "extra_forbidden" for e in errs):
            return False, None, "SCHEMA_UNKNOWN_FIELD", "请求含未知字段", detail, warnings
        return False, None, "GEOMETRY_INVALID", "请求字段校验失败", detail, warnings
    except (DomainError, GeometryError) as exc:
        code, message, detail = error_payload(exc)
        return False, None, code, message, detail, warnings
    except Exception as exc:  # noqa: BLE001 - 路由层必须给信封，不能让 500 裸奔
        code, message, detail = error_payload(exc)
        return False, None, code, message, detail, warnings

    # advisory 失败 → warnings[]（仍出 STL）
    for c in data["checks"]:
        if not c["ok"] and c["id"] in _ADVISORY:
            warnings.append({
                "code": "ADVISORY_CHECK_FAILED",
                "message": f"非阻断检查未通过：{c['id']}",
                "detail": {"check": c},
            })
    # generate_insert 自身的告警（如 DEPTH_EXCEEDS_THICKNESS / 自交修复）也带出
    return True, data, None, None, None, warnings


__all__ = ["build_generate_data", "engine_name", "generate_response"]
