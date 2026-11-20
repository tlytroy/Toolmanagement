"""M1 任务 1.1 / 1.2：倒角锥台凸包采样 DoD + 间隙顺序断言（SDS §7.3）。

★ 防恒真：bbox 宽差对 `scale_top` 仿射实现恒等于 2×(clearance+chamfer)，
  不能作为倒角 DoD。必须在「外轮廓凸包各边中点」沿外法线量锥台顶/底径向宽。
fixture 用 L 形（矩形上凸包=bbox，无法区分仿射实现）。
"""
from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from shapely.geometry import LineString, Polygon  # noqa: E402

from domain.models import BoardConfig, Tool, Vec2  # noqa: E402
from geometry import build_pocket_cutter  # noqa: E402
from geometry.constants import board_top_z  # noqa: E402
from geometry.polygon import to_board_frame  # noqa: E402

CENTER = Vec2(105.0, 148.5)
CHAMFER = 1.5
DEPTH = 8.0
CLEARANCE = 0.4


def rect_board(**kw):
    base = dict(shape="rect", thickness=12, embed_depth=DEPTH,
                slot_chamfer=CHAMFER, clearance=CLEARANCE,
                size_mode="custom", width_mm=120, height_mm=120, corner_r=5.0)
    base.update(kw)
    return BoardConfig(**base)


def l_shape_tool():
    """板局部 L 形（bbox 40×40，凹角 25×25）→ 纸面 mm（y 翻转）。"""
    local = [(0, 0), (40, 0), (40, 15), (15, 15), (15, 40), (0, 40)]
    paper = [Vec2(x + CENTER.x, CENTER.y - y) for x, y in local]
    return Tool(id="L", outer=paper)


def rect_tool(x0=0, x1=100, y0=-10, y1=10):
    paper = [Vec2(x + CENTER.x, CENTER.y - y) for x, y in
             [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]]
    return Tool(id="R", outer=paper)


def _rings_at(cutter, z):
    """截面多边形（面积 > 1e-6），CrossSection.to_polygons() → shapely。"""
    out = []
    for r in cutter.slice(z).to_polygons():
        a = np.asarray(r, dtype=float)
        if len(a) >= 3:
            p = Polygon(a)
            if p.area > 1e-6:
                out.append(p)
    return out


def _radial_width(poly_top, poly_bot, m, n, reach=10.0):
    """沿外法线 n 从凸包边中点 m 作射线，量 top/bot 边界的有符号径向距离差。"""
    a = (m[0] - n[0] * 2, m[1] - n[1] * 2)
    b = (m[0] + n[0] * reach, m[1] + n[1] * reach)
    line = LineString([a, b])

    def far(inter):
        if inter.is_empty:
            return None
        geoms = inter.geoms if hasattr(inter, "geoms") else [inter]
        ds = []
        for g in geoms:
            for c in g.coords:
                ds.append((c[0] - m[0]) * n[0] + (c[1] - m[1]) * n[1])
        return max(ds) if ds else None

    ft, fb = far(line.intersection(poly_top.boundary)), far(line.intersection(poly_bot.boundary))
    return ft - fb if (ft is not None and fb is not None) else None


# ── 1.1 倒角锥台 ──────────────────────────────────────────────────
def test_chamfer_radial_width_on_convex_hull_edges():
    """★核心防恒真 DoD：锥台顶相对底的径向宽 = chamfer ±0.12（凸包边中点采样）。"""
    board = rect_board()
    top_z = board_top_z(board)
    eff = min(CHAMFER, max(0.0, DEPTH - 1.0))
    cutter = build_pocket_cutter(l_shape_tool(), board, CENTER,
                                 depth=DEPTH, chamfer=CHAMFER)

    pt = _rings_at(cutter, top_z - 1e-6)        # 锥台顶（几乎满外扩）
    pb = _rings_at(cutter, top_z - eff + 1e-4)  # 锥台底（几乎未外扩）
    assert pt and pb, "截面为空，锥台未生成"
    ptop, pbot = max(pt, key=lambda p: p.area), max(pb, key=lambda p: p.area)

    flipped = [(v.x, v.y) for v in to_board_frame(l_shape_tool().outer, CENTER)]
    hull = Polygon(flipped).convex_hull
    cx, cy = hull.centroid.x, hull.centroid.y
    coords = list(hull.exterior.coords)[:-1]
    widths = []
    for i in range(len(coords)):
        p1, p2 = coords[i], coords[(i + 1) % len(coords)]
        m = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        L = float(np.hypot(dx, dy))
        nx, ny = dy / L, -dx / L            # CCW 外环的外法线
        if (m[0] - cx) * nx + (m[1] - cy) * ny < 0:
            nx, ny = -nx, -ny
        w = _radial_width(ptop, pbot, m, (nx, ny))
        if w is not None:
            widths.append(w)

    assert len(widths) >= 3, f"凸包边中点采样不足（L 形应至少 3 条边能测到）: {widths}"
    for w in widths:
        assert abs(w - CHAMFER) <= 0.12, (
            f"凸包边中点径向宽 {w:.3f} 偏离 chamfer {CHAMFER} 超过 0.12（仿射 bbox 恒真不算）"
        )


def test_chamfer_z_extent_and_top_overflow():
    """锥台占 z ∈ [top_z-eff, top_z]，顶面 +0.01 溢出；eff 以下截面恒定、以上逐渐外扩。"""
    board = rect_board()
    top_z = board_top_z(board)
    eff = min(CHAMFER, max(0.0, DEPTH - 1.0))
    cutter = build_pocket_cutter(l_shape_tool(), board, CENTER,
                                 depth=DEPTH, chamfer=CHAMFER)

    # 整体 cutter maxZ = top_z + TOP_OVERHANG_MM（直筒刺出主导，锥台只到 top_z+0.01）
    from geometry.pockets import TOP_OVERHANG_MM
    assert cutter.bounding_box()[5] == pytest.approx(top_z + TOP_OVERHANG_MM, abs=0.02)

    area = lambda z: sum(p.area for p in _rings_at(cutter, z))
    a_below1 = area(top_z - eff - 0.3)   # 直筒段
    a_below2 = area(top_z - eff - 0.1)   # 直筒段
    a_above = area(top_z - eff + 0.3)    # 锥面开始外扩
    a_top = area(top_z - 0.1)            # 接近满外扩
    assert abs(a_below1 - a_below2) < 2.0, "eff 以下截面应恒定（直筒）"
    assert a_above > a_below2 + 10, "eff 以上截面应开始外扩（锥面）"
    assert a_top > a_above + 10, "越接近顶面外扩越大"


def test_eff_formula_no_chamfer_for_shallow_depth():
    """eff = min(chamfer, depth-1)：depth=2 时 eff=1；depth<=1 时不倒角。"""
    board = rect_board()
    top_z = board_top_z(board)
    # depth=2 → eff=1，锥台 z ∈ [11, 13.01]
    c2 = build_pocket_cutter(l_shape_tool(), board, CENTER, depth=2.0, chamfer=CHAMFER)
    from geometry.pockets import TOP_OVERHANG_MM
    assert c2.bounding_box()[5] == pytest.approx(top_z + TOP_OVERHANG_MM, abs=0.02)
    area = lambda z: sum(p.area for p in _rings_at(c2, z))
    assert abs(area(top_z - 1.3) - area(top_z - 1.1)) < 2.0   # eff=1 以下直筒
    assert area(top_z - 0.5) > area(top_z - 1.1) + 10          # eff 以上外扩

    # depth=1 → eff=0，无锥台（顶面截面 == 直筒截面）
    c1 = build_pocket_cutter(l_shape_tool(), board, CENTER, depth=1.0, chamfer=CHAMFER)
    assert sum(p.area for p in _rings_at(c1, top_z - 1e-6)) == pytest.approx(
        sum(p.area for p in _rings_at(c1, top_z - 0.5)), rel=0.01
    )


# ── 1.2 间隙 + 顺序 ───────────────────────────────────────────────
def test_clearance_04_expands_rect_pocket():
    """间隙 0.4 → 矩形槽每边外扩 0.4：100×20 → 100.8×20.8。"""
    board = rect_board()
    cutter = build_pocket_cutter(rect_tool(), board, CENTER, depth=DEPTH, chamfer=0.0)
    top_poly = max(_rings_at(cutter, board_top_z(board) - 1e-6), key=lambda p: p.area)
    x0, y0, x1, y1 = top_poly.bounds
    assert (x1 - x0) == pytest.approx(100.8, abs=0.05)  # 100 + 2×0.4
    assert (y1 - y0) == pytest.approx(20.8, abs=0.05)   # 20 + 2×0.4


def test_simplify_before_clearance_source_order():
    """★顺序铁律：make_shape 必须 buffer(0)→simplify(0.15)→buffer(clearance)。

    源码级断言 + 几何断言双保险：若先加间隙后简化，简化会啃掉 0.15mm 间隙
    （0.4→0.25），几何断言必红。
    """
    import inspect
    from geometry import polygon as poly_mod

    src = inspect.getsource(poly_mod.make_shape)
    # 锚到代码行（跳过 docstring）：找形如 `shape = shape.simplify(...)` 与
    # `shape = shape.buffer(clearance` 的真实赋值语句，避免命中 docstring 中的说明文字。
    i_simp = src.find("shape = shape.simplify(")
    i_clr = src.find("shape = shape.buffer(clearance")
    assert 0 <= i_simp < i_clr, "必须『先 simplify 后 clearance』，源码顺序错误"

    # 几何断言：clearance 生效值不被简化啃掉
    board = rect_board()
    cutter = build_pocket_cutter(rect_tool(), board, CENTER, depth=DEPTH, chamfer=0.0)
    top_poly = max(_rings_at(cutter, board_top_z(board) - 1e-6), key=lambda p: p.area)
    assert (top_poly.bounds[2] - top_poly.bounds[0]) == pytest.approx(100.8, abs=0.05)
