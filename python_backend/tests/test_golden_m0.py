"""M0 路 C：0.6 golden test（唯一端到端回归锚）。

★ 这个文件回答四个问题，每个问题都写成「会红」的形式：

  1. **毫米链有没有被缩放**（0.3 的验收，SDS §10.1 明写「0.6 的 DoD 正是 0.3 的验收」）
     —— 已知 mm 轮廓 → `generate_insert` → STL → 重新读回 → 截面量槽长宽，
        误差 ≤ **0.5mm**（SDS §10.3 容差总表）。
  2. **槽数对不对**（R7 静默失败：工具数对了、槽数不对，是最隐蔽的 bug）
     —— 3 个工具 → 截面里必须恰好 3 个槽孔。
  3. **有没有竖直镜像**（水密 / 体积 / 槽尺寸**全都测不出** y 翻转）
     —— L 形 fixture，左下伸 10×5 凸耳，断言凸耳落在 **y 的负侧**，
        且正侧**没有**凸耳（后者才能区分「没翻」与「翻了两次」）。
  4. **合成照片 → STL 的绝对误差是多少**
     —— 走完整链路（imaging 校正 → cv2 分割 → mm → 几何 → STL），
        把实测值钉在测试里，作为已知缺陷的回归锚（`xfail(strict=True)`）。

★ 为什么量 STL 截面而不是量 `pocket_length_mm`：
  `pocket_length_mm` 是 `CrossSection.bounds()` 的 x 跨度，它**不经过**倒角锥台、
  也不经过 STL 导出/重载。用它自证等于「拿返回值证明返回值」。
  这里一律 `export_stl` → `trimesh.load(BytesIO)` → `section(plane_normal=[0,0,1])`
  → `to_2D().polygons_full` 取内环，量的才是用户真正拿到的东西。

★ 为什么 `clearance = 0.0` 且 `slot_chamfer = 0.0`：
  槽尺寸的期望值必须唯一。clearance 默认 0.4 会让槽长变 `100.8`，倒角会让顶面
  再宽 `2*chamfer`，两者都会把「毫米链有没有错」这个信号淹没在公差里
  （SDS §10.1 的代码块同样显式置 `clearance = 0.0`）。间隙与倒角各有自己的用例，
  不在这里混测。

运行（项目根下）：
    .venv/bin/python -m pytest -q python_backend/tests/test_golden_m0.py
"""
from __future__ import annotations

import base64
import io
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
import trimesh

# ★ 两条导入根都要：`geometry/` 是裸导入（`from domain.models import ...`），
#   `imaging/` 是包导入（`from python_backend.imaging.api import ...`）。
#   两个包互不 import，所以不会出现「同一个模块加载两份」的问题；
#   但 `domain.models` 可能被 `python_backend.domain.models` 再加载一份，
#   因此本文件**只用裸路径的 `domain.models`**，不混用。
_ROOT = Path(__file__).resolve().parents[2]
_BACKEND = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT), str(_BACKEND)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from domain.models import BoardConfig, Project, Tool, Vec2  # noqa: E402
from geometry import board_center, generate_insert  # noqa: E402
from geometry.polygon import to_board_frame  # noqa: E402

# SDS §10.3：合成图 → STL 槽长宽容差。**唯一真源，不得就地放宽。**
SLOT_TOL_MM = 0.5

PAPER_W, PAPER_H = 210.0, 297.0
PX_PER_MM = 10.0          # imaging 固定常量（SDS §2.4）
PAPER_ORIGIN_PX = 150.0   # 校正画布左上角留白（SDS §4.2）


# ---------------------------------------------------------------- helpers
def _rect(cx: float, cy: float, w: float, h: float) -> list[Vec2]:
    """纸面 mm（y-down）里居中的 w×h 矩形。"""
    hw, hh = w / 2.0, h / 2.0
    return [
        Vec2(cx - hw, cy - hh),
        Vec2(cx + hw, cy - hh),
        Vec2(cx + hw, cy + hh),
        Vec2(cx - hw, cy + hh),
    ]


def _l_shape_with_lug(cx: float, cy: float) -> list[Vec2]:
    """非对称 fixture：80×30 主体 + 左下伸出的 10×5 凸耳（纸面 y-down）。

    纸面坐标 y 向下增大，所以「向下伸」= y 更大。`to_board_frame` 会把它翻成
    **板局部 y 更小**（负侧）。整块板在 y 方向上因此**不对称**：
    若哪天 `to_board_frame` 的符号被改掉，凸耳会跑到正侧，这里必红。
    """
    hw, hh = 40.0, 15.0
    x0, x1 = cx - hw, cx + hw
    y0, y1 = cy - hh, cy + hh          # y0 上沿、y1 下沿（纸面 y-down）
    lug_x1 = x0 + 10.0                 # 凸耳宽 10
    lug_y1 = y1 + 5.0                  # 凸耳高 5（继续向下）
    # 顺序无关（后续 normalize_winding 会归一化），但保持简单闭合
    return [
        Vec2(x0, y0),
        Vec2(x1, y0),
        Vec2(x1, y1),
        Vec2(lug_x1, y1),
        Vec2(lug_x1, lug_y1),
        Vec2(x0, lug_y1),
    ]


def _board(**over) -> BoardConfig:
    """golden 用的基准板：rect、fit-tools、无间隙、无倒角（期望值唯一）。"""
    kw = dict(
        shape="rect",
        size_mode="fit-tools",
        margin=12.0,
        thickness=12,
        corner_r=5.0,
        embed_depth=8.0,
        clearance=0.0,
        slot_chamfer=0.0,
    )
    kw.update(over)
    return BoardConfig(**kw)


def _stl_roundtrip(manifold_obj) -> trimesh.Trimesh:
    """`Manifold` → STL bytes → `trimesh.Trimesh`（真走一遍导出/读回）。"""
    me = manifold_obj.to_mesh()
    mesh = trimesh.Trimesh(
        vertices=np.asarray(me.vert_properties)[:, :3].astype(float),
        faces=np.asarray(me.tri_verts),
        process=False,
    )
    stl = trimesh.exchange.stl.export_stl(mesh)
    return trimesh.load(io.BytesIO(stl), file_type="stl")


def _pocket_holes(mesh: trimesh.Trimesh, z: float) -> list:
    """在 z 处切一刀，返回**槽孔**（= 实体多边形里的内环）的 shapely 多边形列表。

    ★ 不能用 `p2d.bounds` 判开口：它恒为板外接框。必须逐个内环取几何。
    """
    sec = mesh.section(plane_normal=[0.0, 0.0, 1.0], plane_origin=[0.0, 0.0, float(z)])
    if sec is None:
        return []
    p2d, _T = sec.to_2D()
    from shapely.geometry import Polygon

    holes = []
    for poly in p2d.polygons_full:
        for ring in poly.interiors:
            hp = Polygon(ring)
            if hp.area > 1e-6:
                holes.append(hp)
    return holes


def _size_mm(poly) -> tuple[float, float]:
    minx, miny, maxx, maxy = poly.bounds
    return (float(maxx - minx), float(maxy - miny))


def _width_at(poly, y: float) -> float:
    """多边形在高度 y 处的水平跨度（mm）。用一条水平线去切，量交线长度。

    ★ 比 `bounds` 强的地方：`bounds` 只有四个数，一个「凸耳换到另一边」的形状
      可以拥有**完全相同**的 bbox（本 fixture 就是：body 30 + 凸耳 5 让上下沿
      恰好都是 ±17.5）。只有沿 y 采样才能区分「凸耳在下」和「凸耳在上」。
    """
    from shapely.geometry import LineString

    cut = poly.intersection(LineString([(-1e4, float(y)), (1e4, float(y))]))
    return float(cut.length)


def _synthetic_photo(
    polys_mm: list[list[tuple[float, float]]],
    *,
    ppm: float = 4.0,
    paper: tuple[float, float] = (PAPER_W, PAPER_H),
    margin_px: int = 200,
    tool_gray: int = 60,
) -> tuple[bytes, list[tuple[float, float]]]:
    """合成一张「纸 + 若干深色工具」的照片，返回 (JPEG 字节, 纸四角像素)。

    ★ 纸面铺满整张画布（不留背景），并显式给 `corners`：这样校正的误差来源只剩
      透视变换本身，不会把「纸边检测」的误差算进 golden 的槽尺寸里。
    """
    pw, ph = paper
    w_px = int(round(pw * ppm)) + 2 * margin_px
    h_px = int(round(ph * ppm)) + 2 * margin_px
    img = np.full((h_px, w_px, 3), 235, np.uint8)

    def to_px(mx: float, my: float) -> tuple[int, int]:
        return (int(round(margin_px + mx * ppm)), int(round(margin_px + my * ppm)))

    for poly in polys_mm:
        cv2.fillPoly(img, [np.array([to_px(x, y) for x, y in poly], np.int32)],
                     (tool_gray, tool_gray, tool_gray))

    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    assert ok
    corners = [to_px(0.0, 0.0), to_px(pw, 0.0), to_px(pw, ph), to_px(0.0, ph)]
    return buf.tobytes(), [(float(x), float(y)) for x, y in corners]


def _contour_to_paper_mm(contour: np.ndarray) -> list[Vec2]:
    """校正画布像素 → 纸面 mm（`mm = (px - 150) / 10`，唯一换算方向）。"""
    pts = contour.reshape(-1, 2).astype(float)
    mm = (pts - np.array([PAPER_ORIGIN_PX, PAPER_ORIGIN_PX])) / PX_PER_MM
    return [Vec2(float(x), float(y)) for x, y in mm]


# ---------------------------------------------------------------- DoD ①
def test_golden_slot_size_mm_chain() -> None:
    """DoD ①：已知 100×60mm 轮廓 → STL，槽长宽误差 ≤ 0.5mm。

    ★ 这是 0.3「删掉缩放元凶」的验收：旧 `cad_engine.py` 里
      `scale = min(base_size_x/840, base_size_y/1188)` 会让同一个轮廓在不同尺寸
      的板上得到不同槽长。这里量的是 STL 里的真实尺寸。
    """
    tool_w, tool_h = 100.0, 60.0
    tool = Tool(id="t1", outer=_rect(PAPER_W / 2, PAPER_H / 2, tool_w, tool_h))
    board = _board()
    result = generate_insert(Project(tools=[tool], board=board))

    mesh = _stl_roundtrip(result["base"])
    # 切在槽深的中间：既在槽内（不是顶面），又避开倒角/底面
    z_mid = result["top_z"] - board.embed_depth / 2.0
    holes = _pocket_holes(mesh, z_mid)
    assert len(holes) == 1, f"应该恰好 1 个槽孔，实际 {len(holes)}"

    w_mm, h_mm = _size_mm(holes[0])
    assert abs(w_mm - tool_w) <= SLOT_TOL_MM, f"槽长 {w_mm:.3f} vs {tool_w} 超差"
    assert abs(h_mm - tool_h) <= SLOT_TOL_MM, f"槽宽 {h_mm:.3f} vs {tool_h} 超差"


def test_golden_slot_size_is_scale_invariant() -> None:
    """0.3 DoD ②：同一轮廓在 200mm 板与 300mm 板上槽长必须一致。

    这是 F1（`scale = min(base/840, base/1188)`）的直接回归锚。
    """
    tool_w, tool_h = 100.0, 60.0
    tool = Tool(id="t1", outer=_rect(PAPER_W / 2, PAPER_H / 2, tool_w, tool_h))

    sizes = {}
    for label, w_board, h_board in (("200", 200.0, 150.0), ("300", 300.0, 200.0)):
        board = _board(size_mode="custom", width_mm=w_board, height_mm=h_board)
        result = generate_insert(Project(tools=[tool], board=board))
        mesh = _stl_roundtrip(result["base"])
        holes = _pocket_holes(mesh, result["top_z"] - board.embed_depth / 2.0)
        assert len(holes) == 1, f"{label}mm 板：槽孔数 {len(holes)}"
        sizes[label] = _size_mm(holes[0])

    assert abs(sizes["200"][0] - sizes["300"][0]) < 1e-6, (
        f"槽长随板尺寸变化：200mm 板 {sizes['200'][0]:.6f} vs "
        f"300mm 板 {sizes['300'][0]:.6f}（scale 残留）"
    )
    assert abs(sizes["200"][0] - tool_w) <= SLOT_TOL_MM


# ---------------------------------------------------------------- DoD ②
def test_golden_slot_count_matches_tool_count() -> None:
    """DoD ②：`len(slots) == len(tools)`，防 R7 静默失败。

    ★ 断言的是 **STL 截面里真实存在的槽孔数**，不是 `len(result["tools"])` ——
      后者是函数自己数的，工具被静默丢掉时它也照样对。
    """
    tools = [
        Tool(id="a", outer=_rect(60.0, 60.0, 100.0, 60.0)),
        Tool(id="b", outer=_rect(60.0, 150.0, 80.0, 40.0)),
        Tool(id="c", outer=_rect(60.0, 230.0, 60.0, 30.0)),
    ]
    board = _board()
    result = generate_insert(Project(tools=tools, board=board))

    mesh = _stl_roundtrip(result["base"])
    holes = _pocket_holes(mesh, result["top_z"] - board.embed_depth / 2.0)
    assert len(holes) == len(tools), (
        f"工具 {len(tools)} 个、槽孔 {len(holes)} 个 —— 有槽被静默吞掉了"
    )

    # 再加一条：三个槽的面积必须各不相同（否则可能是同一个槽被数了三遍）
    areas = sorted(h.area for h in holes)
    assert areas[0] < areas[1] < areas[2], f"槽面积不互异：{areas}"


def test_golden_slot_count_with_hidden_tool() -> None:
    """隐藏的工具不参与生成，槽数 = 可见工具数（`hidden` 不得被当成「生成失败」）。"""
    tools = [
        Tool(id="vis", outer=_rect(60.0, 60.0, 100.0, 60.0)),
        Tool(id="hid", outer=_rect(60.0, 200.0, 80.0, 40.0), hidden=True),
    ]
    board = _board()
    result = generate_insert(Project(tools=tools, board=board))
    mesh = _stl_roundtrip(result["base"])
    holes = _pocket_holes(mesh, result["top_z"] - board.embed_depth / 2.0)
    assert len(holes) == 1, f"隐藏工具不该出槽，实际槽孔 {len(holes)} 个"


# ---------------------------------------------------------------- DoD ③
def test_golden_asymmetric_lug_is_on_negative_y() -> None:
    """DoD ③：非对称 L 形，凸耳必须在板局部 **y 的负侧**。

    ★ 只测水密 / 体积 / 槽长宽**全都测不出竖直镜像**：镜像后的实体水密、体积、
      槽尺寸完全一样。唯一能抓到它的是「凸耳相对主体的位置」。
    ★ 连 `bounds` 也测不出：body 30 + 凸耳 5 恰好让 bbox 上下沿对称（±17.5），
      镜像前后 bbox 一模一样。**必须沿 y 采样量宽度**（`_width_at`）：
      上沿处宽 80（主体），下沿处宽 10（凸耳）。这才是判别式。
    """
    body_w, body_h, lug_w, lug_h = 80.0, 30.0, 10.0, 5.0
    cx, cy = PAPER_W / 2, PAPER_H / 2
    outer = _l_shape_with_lug(cx, cy)
    board = _board()
    result = generate_insert(Project(tools=[Tool(id="L", outer=outer)], board=board))

    # —— 先确认坐标翻转本身（纯 2D，不依赖 3D）——
    center = board_center([Tool(id="L", outer=outer)])
    local = to_board_frame(outer, center)
    # 纸面 y-down：凸耳「向下伸」= 纸面 y 最大。翻转后在板局部 y 最小（负侧）。
    lowest = min(p.y for p in local)
    highest = max(p.y for p in local)
    lug_pts = [p for p in local if p.y < lowest + 1e-9]
    assert lug_pts, "找不到凸耳（fixture 坏了）"
    assert len(lug_pts) == 2, f"凸耳应贡献 2 个最低点，实际 {len(lug_pts)}"
    assert all(abs(p.y - lowest) < 1e-9 for p in lug_pts)
    # 凸耳的两个最低点 x 跨度 = lug_w，且落在 x 负侧（左下，不是右下）
    assert abs(np.ptp([p.x for p in lug_pts]) - lug_w) < 1e-9
    assert max(p.x for p in lug_pts) < 0.0, "凸耳跑到 x 正侧了"

    # —— 再从 STL 截面里验一遍 ——
    mesh = _stl_roundtrip(result["base"])
    holes = _pocket_holes(mesh, result["top_z"] - board.embed_depth / 2.0)
    assert len(holes) == 1
    hole = holes[0]
    minx, miny, maxx, maxy = hole.bounds
    assert abs((maxx - minx) - body_w) <= SLOT_TOL_MM
    assert abs((maxy - miny) - (body_h + lug_h)) <= SLOT_TOL_MM

    # ★ 判别式：靠近上沿处是主体宽度，靠近下沿处只剩凸耳宽度
    w_top = _width_at(hole, highest - 1.0)
    w_bottom = _width_at(hole, lowest + 1.0)
    assert abs(w_top - body_w) <= SLOT_TOL_MM, (
        f"y 上沿处宽度 {w_top:.3f}，应为主体 {body_w}（凸耳不该在上侧）"
    )
    assert abs(w_bottom - lug_w) <= SLOT_TOL_MM, (
        f"y 下沿处宽度 {w_bottom:.3f}，应为凸耳 {lug_w}（凸耳该在负 y 侧）"
    )

    # 主体/凸耳的分界线位置：从下沿往上 lug_h 处宽度应跳回 body_w
    w_above_lug = _width_at(hole, lowest + lug_h + 1.0)
    assert abs(w_above_lug - body_w) <= SLOT_TOL_MM, (
        f"凸耳上方 1mm 处宽度 {w_above_lug:.3f}，应为主体 {body_w}"
    )

    # 凸耳在 x 负侧（同时排掉 x 镜像）
    from shapely.geometry import box as _box

    lug_band = hole.intersection(_box(-1e4, -1e4, 1e4, lowest + lug_h - 0.5))
    lminx, _, lmaxx, _ = lug_band.bounds
    assert lmaxx < 0.0, f"凸耳在 x 正侧：max x = {lmaxx:.3f}"
    assert abs((lmaxx - lminx) - lug_w) <= SLOT_TOL_MM


def test_golden_fixture_is_truly_asymmetric() -> None:
    """fixture 自检：L 形**不得**关于 y 对称，否则上面那条镜像断言形同虚设。

    ★ 这条测的是 fixture 本身，不是实现。它先红一次，才能证明判别式有效。
    """
    outer = _l_shape_with_lug(PAPER_W / 2, PAPER_H / 2)
    board = _board()
    result = generate_insert(Project(tools=[Tool(id="L", outer=outer)], board=board))
    mesh = _stl_roundtrip(result["base"])
    holes = _pocket_holes(mesh, result["top_z"] - board.embed_depth / 2.0)
    hole = holes[0]
    minx, miny, maxx, maxy = hole.bounds

    # bbox 本身是对称的（30 主体 + 5 凸耳），所以对称性必须靠采样判定
    w_top = _width_at(hole, maxy - 1.0)
    w_bottom = _width_at(hole, miny + 1.0)
    assert abs(w_top - w_bottom) > 10.0, (
        f"上下宽度差只有 {abs(w_top - w_bottom):.3f}mm，fixture 退化成了对称件"
    )
    # 把这条镜像件的宽度曲线也钉死：若实现改成 y 镜像，w_top/w_bottom 会互换
    assert w_top > w_bottom


# ---------------------------------------------------------------- 端到端
def test_golden_synthetic_photo_to_stl_mm_chain() -> None:
    """合成照片 → 校正 → 分割 → mm → STL：**相对检测轮廓**的尺寸误差 ≤ 0.5mm。

    这条测的是「毫米链 + 几何」这一段（0.3 的验收）：不论 cv2 分割给出什么轮廓，
    进几何引擎之后 STL 里的槽必须还是那个尺寸，不许被缩放。
    """
    from python_backend.imaging import correct_image_response
    from sam_tool_contour import extract_tool_contours_v26

    truth = [(30.0, 40.0), (130.0, 40.0), (130.0, 100.0), (30.0, 100.0)]  # 100×60
    photo, corners = _synthetic_photo([truth])
    corrected = correct_image_response(photo, corners=corners)
    warped = cv2.imdecode(
        np.frombuffer(base64.b64decode(corrected["warpedImage"]), np.uint8),
        cv2.IMREAD_COLOR,
    )
    assert warped.shape[1] == int((PAPER_W + 2 * 15.0) * PX_PER_MM)

    contour = extract_tool_contours_v26(warped)
    assert contour is not None, "合成图上没找到轮廓"

    outer = _contour_to_paper_mm(contour)
    in_w = float(np.ptp(np.array([p.x for p in outer])))
    in_h = float(np.ptp(np.array([p.y for p in outer])))

    board = _board()
    result = generate_insert(Project(tools=[Tool(id="t1", outer=outer)], board=board))
    mesh = _stl_roundtrip(result["base"])
    holes = _pocket_holes(mesh, result["top_z"] - board.embed_depth / 2.0)
    assert len(holes) == 1
    out_w, out_h = _size_mm(holes[0])

    # 毫米链只允许「轮廓 → STL」这一段有误差
    assert abs(out_w - in_w) <= SLOT_TOL_MM, f"毫米链把槽长从 {in_w:.3f} 变成 {out_w:.3f}"
    assert abs(out_h - in_h) <= SLOT_TOL_MM, f"毫米链把槽宽从 {in_h:.3f} 变成 {out_h:.3f}"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "已知缺陷（不在路 C 范围）：遗留分割器 sam_tool_contour.py 对掩膜做了"
        "固定像素膨胀（path_lab_color_gradient 的 dk=31px、path_canny_bridge 的 "
        "dk=15px，10px/mm 下约 +3.4mm），且没有任何腐蚀补偿。实测 100x60mm 真值 -> "
        "STL 槽 103.4x63.3mm，绝对误差 +3.4mm，超过 SDS §10.3 的 ±0.5mm。"
        "修复要动 sam_tool_contour.py（路由 A/B/C 之外的遗留文件），本路不改。"
        "★ strict=True：一旦有人修好分割器，这条会 XPASS 变红，逼着把标记去掉。"
    ),
)
def test_golden_synthetic_photo_absolute_size_known_defect() -> None:
    """合成照片 → STL 的**绝对**槽尺寸误差（对真值 100×60mm）。

    这条目前**必然红**（xfail）。保留它的价值：
      - 把实测的 3.4mm 偏差钉在代码里，任何改动让它变大都会 XPASS 失败；
      - 让「端到端 ±0.5mm」这条 DoD 的缺口在 CI 里可见，而不是躺在文档里。
    """
    from python_backend.imaging import correct_image_response
    from sam_tool_contour import extract_tool_contours_v26

    truth_w, truth_h = 100.0, 60.0
    truth = [(30.0, 40.0), (130.0, 40.0), (130.0, 100.0), (30.0, 100.0)]
    photo, corners = _synthetic_photo([truth])
    corrected = correct_image_response(photo, corners=corners)
    warped = cv2.imdecode(
        np.frombuffer(base64.b64decode(corrected["warpedImage"]), np.uint8),
        cv2.IMREAD_COLOR,
    )
    contour = extract_tool_contours_v26(warped)
    assert contour is not None

    outer = _contour_to_paper_mm(contour)
    board = _board()
    result = generate_insert(Project(tools=[Tool(id="t1", outer=outer)], board=board))
    mesh = _stl_roundtrip(result["base"])
    holes = _pocket_holes(mesh, result["top_z"] - board.embed_depth / 2.0)
    assert len(holes) == 1
    out_w, out_h = _size_mm(holes[0])

    assert abs(out_w - truth_w) <= SLOT_TOL_MM, (
        f"绝对槽长 {out_w:.3f} vs 真值 {truth_w}（误差 {out_w - truth_w:+.3f}）"
    )
    assert abs(out_h - truth_h) <= SLOT_TOL_MM, (
        f"绝对槽宽 {out_h:.3f} vs 真值 {truth_h}（误差 {out_h - truth_h:+.3f}）"
    )
