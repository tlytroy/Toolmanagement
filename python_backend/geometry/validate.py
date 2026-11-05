"""几何自检库：SDS D12' 的两级校验（L0 2D shapely / L1 3D manifold3d + trimesh）。

★ 本模块**只判定、不修复**。L0 的 `buffer(0)` 修复在 `geometry.polygon.make_shape`
  里已经做过一次；这里再 `buffer(0)` 只会把「上游没修干净」这件事掩盖掉。
★ 每个 `CheckResult.name` 与 SDS §4.5 的 `checks[].id` **同名**，`to_dict()` 出来就能
  直接塞进响应信封，不需要再映射一次。
★ 阻断 / 建议的分工照 SDS §4.5 写死（见 `BLOCKING_CHECKS` / `ADVISORY_CHECKS`）。

★ 为什么需要 `components` + `self_intersection` 这两条（实测依据，别再删）：
  把两个**重叠**立方体的三角面**手工拼**成一张网格后，manifold3d / trimesh 的常规谓词
  **全部为绿**：

      status=Error.NoError  is_watertight=True  is_winding_consistent=True
      volume=2000.0（= 两块各 1000 直接相加，重叠区被算了两次）  parts=2

  也就是说，只查 `status` / `is_watertight` / `is_winding_consistent` / `volume`
  的自检对「实体重叠」是**恒真**的，没有任何价值。真正能抓到它的只有：
  1. `decompose()` 出 > 1 个**正体积**分量（重叠块之间拓扑不连通）；
  2. 分量两两求交 `(a ^ b).volume() > 0` —— 合法的内部空腔求交是**负值**
     （实测 `board - 内腔` 得 `[8000, -1000]`，交集 `-1000`），
     非法的实体重叠是**正值**（实测重叠 5mm 得 `+125`）。
  两者一起判，才能既不误杀合法空腔、又不放过重叠。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import manifold3d as mf
import numpy as np
import trimesh

# 体积容差（mm^3）：只吸收浮点误差，不承担几何偏差。
GEOMETRY_EPS_MM3 = 1e-6
# 体积与解析解的相对容差（SDS §10.3 容差总表：±2%）。
VOLUME_TOLERANCE = 0.02
# 最小筋厚阈值（mm，SDS §7.6 第 6 条 / §4.5 的 min_rib）。
MIN_RIB_MM = 2.0

# SDS §4.5：false 即 `success:false` 的检查项。
# ★ 相对 SDS §4.5 原文的**增补**（必须显式说明，不要以为 SDS 里本来就有）：
#   SDS 列的 6 项是 `shapely_valid` / `watertight` / `winding` / `manifold_status`
#   / `tools_in_board` / `slot_open`。其中 `tools_in_board` 与 `slot_open` 需要
#   板框 / 槽刀上下文，不在本模块判（由 `geometry.__init__` 与 golden test 负责）。
#   本模块另外把下面 3 项也定为**阻断**，理由都是「它们为 false 时几何确实坏了」：
#     - `area_positive`     : 面积 <= 0 的环根本不能当轮廓；
#     - `components`        : 一个嵌件必须是单实体（多实体 = 两块料/实体重叠）；
#     - `self_intersection` : 实体两两相交 > 0，打印出来是自穿模。
#   后两项是**唯一**能抓到「两块实体重叠」的谓词（见模块 docstring 的实测数据），
#   而 0.7 DoD ① 正是要求「重叠立方体必须被判失败」，所以它们必须阻断，
#   否则 `summarize()` 会说「失败但可放行」，等于没判。错误码统一映射
#   `GEOMETRY_INVALID`（SDS §4.5 对几何类阻断的统一出口）。
BLOCKING_CHECKS = frozenset({
    "shapely_valid",
    "area_positive",
    "manifold_status",
    "watertight",
    "winding",
    "components",
    "self_intersection",
})
# SDS §4.5：false 只进 `warnings[]`、仍出 STL 的检查项。
ADVISORY_CHECKS = frozenset({"genus", "volume_match", "min_rib"})


@dataclass(frozen=True)
class CheckResult:
    """一条检查结果。

    `name` 是 SDS §4.5 的 check id（`shapely_valid` / `watertight` / ...），
    `detail` 是该项自己的量化证据（面积、体积、相对误差、分量数……）。
    """

    name: str
    ok: bool
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转成 SDS §4.5 的 `checks[]` 元素：`{id, ok, ...detail}`。"""
        out = {"id": self.name, "ok": bool(self.ok)}
        out.update(self.detail)
        return out

    def __str__(self) -> str:  # 测试失败时直接可读
        return f"{'OK  ' if self.ok else 'FAIL'} {self.name} {self.detail}"


# ---------------------------------------------------------------- L0：2D
def validate_2d(
    shape,
    *,
    label: str = "",
    min_rib_mm: float | None = None,
    others=(),
) -> list[CheckResult]:
    """L0 校验：shapely 轮廓是否合法、面积是否为正、（可选）最小筋厚。

    参数
    ----
    shape       : `shapely.geometry.Polygon`（`make_shape` 的返回值）。
    label       : 只用于报错定位，写进 detail。
    min_rib_mm  : 给阈值就做筋厚检查；给 `None`（默认）**不产生** `min_rib` 这条，
                  避免「没有邻居却报筋厚合格」的恒真项。
    others      : 与 `shape` 相邻的其它槽轮廓（用于槽-槽筋厚）。

    ★ `min_rib` 用 `shapely.distance` 真算，**不用 bbox 估算**（SDS §7.6 第 6 条）。
      `shape` 已是加过 clearance 的槽轮廓，所以量出来的就是**实际筋厚**。
    """
    results: list[CheckResult] = []
    base_detail: dict = {"label": label}
    if label:
        base_detail["label"] = label

    is_valid = bool(getattr(shape, "is_valid", False))
    detail = dict(base_detail)
    detail["type"] = type(shape).__name__
    if not is_valid:
        # explain_validity 是 shapely 自带的「为什么非法」，比 "Invalid" 有用得多
        try:
            from shapely.validation import explain_validity

            detail["reason"] = explain_validity(shape)
        except Exception:  # pragma: no cover - shapely 永远给得出理由
            detail["reason"] = "is_valid == False"
    results.append(CheckResult("shapely_valid", is_valid, detail))

    # 面积为正：独立的可读证据（`is_valid` 对「面积 0 的合法环」也可能为 True）
    area = float(getattr(shape, "area", 0.0) or 0.0)
    results.append(
        CheckResult("area_positive", area > GEOMETRY_EPS_MM3,
                    {**base_detail, "areaMm2": round(area, 6)})
    )

    if min_rib_mm is not None and others:
        nearest = float("inf")
        worst = None
        for i, other in enumerate(others):
            if other is shape:
                continue
            dist = float(shape.distance(other))
            if dist < nearest:
                nearest, worst = dist, i
        if worst is not None:
            results.append(
                CheckResult(
                    "min_rib",
                    nearest >= float(min_rib_mm),
                    {**base_detail,
                     "minMm": round(nearest, 6),
                     "thresholdMm": float(min_rib_mm),
                     "neighborIndex": worst},
                )
            )
    return results


# ---------------------------------------------------------------- L1：3D
def _to_trimesh(manifold_obj) -> trimesh.Trimesh:
    """`Manifold` → `trimesh.Trimesh`（`process=False`，否则 trimesh 会合并顶点、
    把「两个重叠但拓扑分离的壳」缝成一个，重叠就再也查不出来了）。"""
    if manifold_obj.is_empty():
        return trimesh.Trimesh()
    me = manifold_obj.to_mesh()
    verts = np.asarray(me.vert_properties)[:, :3].astype(float)
    faces = np.asarray(me.tri_verts)
    return trimesh.Trimesh(vertices=verts, faces=faces, process=False)


def _solid_parts(manifold_obj) -> list:
    """正体积分量。

    `decompose()` 会把**内部空腔**也列成一个分量，其 `volume()` 为**负**
    （实测：`board - 内腔` 得 `[8000, -1000]`）。空腔是合法几何，
    数「有几个实体」时必须把它排除，否则合法空腔会被判成多实体。
    """
    return [p for p in manifold_obj.decompose()
            if float(p.volume()) > GEOMETRY_EPS_MM3]


def validate_3d(
    manifold_obj,
    *,
    expected_volume: float | None = None,
    expected_genus: int | None = None,
    label: str = "",
    volume_tol: float = VOLUME_TOLERANCE,
) -> list[CheckResult]:
    """L1 校验：流形状态、水密、绕向、实体分量、实体重叠、亏格、体积。

    参数
    ----
    manifold_obj   : `manifold3d.Manifold`。
    expected_volume: 解析解体积（mm^3）。给了才产生 `volume_match` 这条。
    expected_genus : 期望亏格。给了就精确比对；不给则只要求「单实体且 genus >= 0」。
    volume_tol     : 相对容差，默认 SDS §10.3 的 ±2%。
    """
    results: list[CheckResult] = []
    base: dict = {"label": label} if label else {}

    status = manifold_obj.status()
    results.append(
        CheckResult("manifold_status", status == mf.Error.NoError,
                    {**base, "status": str(status)})
    )

    mesh = _to_trimesh(manifold_obj)
    results.append(
        CheckResult("watertight", bool(mesh.is_watertight),
                    {**base, "faces": int(len(mesh.faces)),
                     "vertices": int(len(mesh.vertices))})
    )
    results.append(
        CheckResult("winding", bool(mesh.is_winding_consistent), dict(base))
    )

    all_parts = [] if manifold_obj.is_empty() else manifold_obj.decompose()
    solid_parts = [p for p in all_parts if float(p.volume()) > GEOMETRY_EPS_MM3]
    results.append(
        CheckResult("components", len(solid_parts) == 1,
                    {**base, "count": len(solid_parts),
                     "volumesMm3": [round(float(p.volume()), 6) for p in all_parts]})
    )

    # —— 实体重叠：这是唯一能抓到「两块实体叠在一起」的谓词（见模块 docstring）——
    overlaps: list[dict] = []
    for i in range(len(all_parts)):
        for j in range(i + 1, len(all_parts)):
            inter = float((all_parts[i] ^ all_parts[j]).volume())
            if inter > GEOMETRY_EPS_MM3:
                overlaps.append({"i": i, "j": j,
                                 "intersectionMm3": round(inter, 6)})
    results.append(
        CheckResult("self_intersection", not overlaps,
                    {**base, "overlaps": overlaps})
    )

    genus = int(manifold_obj.genus()) if not manifold_obj.is_empty() else 0
    if expected_genus is None:
        genus_ok = genus >= 0
    else:
        genus_ok = genus == int(expected_genus)
    results.append(
        CheckResult("genus", genus_ok,
                    {**base, "genus": genus, "expected": expected_genus,
                     "components": len(solid_parts)})
    )

    if expected_volume is not None:
        actual = float(manifold_obj.volume())
        expected = float(expected_volume)
        if abs(expected) <= GEOMETRY_EPS_MM3:
            rel = float("inf")
        else:
            rel = abs(actual - expected) / abs(expected)
        results.append(
            CheckResult("volume_match", rel <= float(volume_tol),
                        {**base, "expectedMm3": round(expected, 6),
                         "actualMm3": round(actual, 6),
                         "relativeError": round(rel, 9),
                         "tolerance": float(volume_tol)})
        )
    return results


# ---------------------------------------------------------------- 汇总
def summarize(results, *, label: str = "") -> dict:
    """把一组 `CheckResult` 汇成一份可直接判定的摘要。

    `blocking` 为 True 表示**必须** `success:false`；`ok` 为 False 但 `blocking`
    为 False 时，按 SDS §4.5 只进 `warnings[]`、仍出 STL。
    """
    failed = [r for r in results if not r.ok]
    blocking = [r for r in failed if r.name in BLOCKING_CHECKS]
    advisory = [r for r in failed if r.name in ADVISORY_CHECKS]
    unknown = [r for r in failed
               if r.name not in BLOCKING_CHECKS and r.name not in ADVISORY_CHECKS]
    return {
        "label": label,
        "ok": not failed,
        "blocking": bool(blocking),
        "failed": [r.name for r in failed],
        "blockingFailed": [r.name for r in blocking],
        "advisoryFailed": [r.name for r in advisory],
        "unknownFailed": [r.name for r in unknown],
        "checks": [r.to_dict() for r in results],
    }


def assert_all_ok(results, *, label: str = "") -> None:
    """测试/冒烟用：有任何一条红就抛 AssertionError，并带上每条 detail。"""
    bad = [r for r in results if not r.ok]
    if bad:
        lines = "\n".join(f"  {r}" for r in bad)
        raise AssertionError(f"{label or 'validate'} 未通过 {len(bad)} 项：\n{lines}")


__all__ = [
    "ADVISORY_CHECKS",
    "BLOCKING_CHECKS",
    "CheckResult",
    "GEOMETRY_EPS_MM3",
    "MIN_RIB_MM",
    "VOLUME_TOLERANCE",
    "assert_all_ok",
    "summarize",
    "validate_2d",
    "validate_3d",
]
