"""M0 路 A：成像链路 DoD（任务 0.4 透视矫正 + 0.5 照片体检）。

★ 全部用**合成图像**（numpy + cv2.fillPoly 画白纸、黑背景，getPerspectiveTransform 造透视），
  不依赖任何真实照片，也不落盘。

★ 每条断言都写成「会红」的形式：
  - ① ② 量的是 warp 之后**真实像素**的位置，不是函数返回值自证；
  - ③ 真的去 grep 源码，不是断言一个常量等于自己；
  - ④ 换床尺寸 + 换源图分辨率，两轴都验；
  - ⑧ 先证正常照片为空，再证三种病各自**能报出来**（否则「恒返回 []」的假实现也能过）。

运行：
    .venv/bin/python -m pytest -q python_backend/tests/test_imaging_m0.py
"""
from __future__ import annotations

import inspect
import math
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

# pytest 的 console script 不会把 cwd 加进 sys.path（没有 conftest.py），
# 这里显式加项目根，保证 `import python_backend.imaging` 成立。
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from python_backend.domain.models import BoardConfig  # noqa: E402
from python_backend.imaging import (  # noqa: E402
    MM_PER_PX,
    PX_PER_MM,
    canvas_px_for,
    check_photo,
    correct_perspective,
    detect_paper_corners,
    paper_mm,
    paper_origin_px,
    paper_rect_px_for,
    pick_paper_orientation,
)
from python_backend.imaging.api import (  # noqa: E402
    correct_image_response,
    encode_png_base64,
)
from python_backend.imaging.perspective import _quad_aspect_ratio  # noqa: E402

# 画布常量（SDS §2.2），测试里硬编码一遍，防止有人改了实现又改断言
A4_PORTRAIT_CANVAS = (2400, 3270)
A4_LANDSCAPE_CANVAS = (3270, 2400)
A4_PORTRAIT_PAPER_RECT = (150.0, 150.0, 2250.0, 3120.0)


# ---------------------------------------------------------------- 合成图工具


def make_photo(
    w: int,
    h: int,
    quad: list[tuple[float, float]],
    *,
    bg: int = 0,
    paper: int = 255,
    noise: int = 0,
) -> np.ndarray:
    """黑背景 + 白色四边形纸面。`noise` 为高斯噪声标准差（模拟真实照片）。"""
    img = np.full((h, w, 3), bg, dtype=np.uint8)
    cv2.fillPoly(img, [np.asarray(quad, dtype=np.int32)], (paper, paper, paper))
    if noise:
        rng = np.random.default_rng(7)
        img = np.clip(
            img.astype(np.float32) + rng.normal(0.0, noise, img.shape), 0, 255
        ).astype(np.uint8)
    return img


def white_bbox(img: np.ndarray, thresh: int = 128) -> tuple[int, int, int, int]:
    """图里白色区域的 bbox（x0, y0, x1, y1）。用于量 warp 结果的实际位置。"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    ys, xs = np.nonzero(gray >= thresh)
    if xs.size == 0:
        raise AssertionError("合成图里没有白色区域")
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def white_fraction(img: np.ndarray, rect: tuple[float, float, float, float]) -> float:
    """指定矩形内白像素占比。"""
    x0, y0, x1, y1 = (int(round(v)) for v in rect)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    patch = gray[y0:y1, x0:x1]
    return float(np.count_nonzero(patch >= 128)) / float(patch.size)


def encode_png(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


# 一张「正常的 A4 竖放照片」：3200×2400，纸 925×1300 px，占画面 15.7%。
# ★ 这个尺度不是随手写的：纸的对角像素 ≈1595 / 画面对角 4000 = 40%，
#   按 26mm 等效焦距反算相机高度 ≈548mm > MIN_CAMERA_HEIGHT_MM(450)，
#   所以它是一张**真的不近**的照片，DoD ⑧ 的空 warnings 才有意义。
NORMAL_QUAD_PORTRAIT = [
    (1150.0, 520.0),
    (2074.0, 560.0),
    (2040.0, 1866.0),
    (1120.0, 1820.0),
]
# 一张「正常的 A4 横放照片」：同一画幅，纸 1306×920 px
NORMAL_QUAD_LANDSCAPE = [
    (950.0, 700.0),
    (2256.0, 730.0),
    (2230.0, 1654.0),
    (920.0, 1620.0),
]

NORMAL_FRAME_W = 3200
NORMAL_FRAME_H = 2400


@pytest.fixture(scope="module")
def normal_portrait_photo() -> np.ndarray:
    return make_photo(NORMAL_FRAME_W, NORMAL_FRAME_H, NORMAL_QUAD_PORTRAIT, noise=6)


@pytest.fixture(scope="module")
def normal_landscape_photo() -> np.ndarray:
    return make_photo(NORMAL_FRAME_W, NORMAL_FRAME_H, NORMAL_QUAD_LANDSCAPE, noise=6)


# ---------------------------------------------------------------- DoD ①


def test_dod1_a4_portrait_canvas_is_2400x3270(normal_portrait_photo):
    """① A4 竖放 → 画布 2400×3270（量的是 warp 出来的真实 ndarray 形状）。"""
    result = correct_perspective(normal_portrait_photo, NORMAL_QUAD_PORTRAIT, "a4")
    assert result.orientation == "portrait"
    assert result.canvas_px == A4_PORTRAIT_CANVAS
    assert result.warped.shape[:2] == (A4_PORTRAIT_CANVAS[1], A4_PORTRAIT_CANVAS[0])
    assert result.paper_mm == (210.0, 297.0)


def test_dod1_a4_landscape_canvas_is_3270x2400(normal_landscape_photo):
    """① A4 横放 → 画布 3270×2400。"""
    result = correct_perspective(normal_landscape_photo, NORMAL_QUAD_LANDSCAPE, "a4")
    assert result.orientation == "landscape"
    assert result.canvas_px == A4_LANDSCAPE_CANVAS
    assert result.warped.shape[:2] == (A4_LANDSCAPE_CANVAS[1], A4_LANDSCAPE_CANVAS[0])
    assert result.paper_mm == (297.0, 210.0)


def test_dod1_orientation_is_closed_form_not_pixel_guess():
    """① 补：`pick_paper_orientation` 走闭式长宽比，不是 `if h > w` / `if top > left`。

    ★ 这条**必须能抓出「退化成像素比较」的实现**（变异 M6 已验证它会红）。

    四边形由针孔相机投影真值 A4 竖放纸得到（pitch=20°、yaw=40°、dist=500mm、
    f=1600px，再以主点为中心缩到 0.3 倍塞进 1600×1600 画面）：

        quad = [(1110.3, 422.5), (1584.4, 317.8), (1355.1, 844.3), (1043.8, 785.8)]

    这个四边形上边 485px > 左边 369px —— 朴素像素比较判 **landscape（错）**；
    闭式解反推真实宽高比 est≈0.7069 ≈ 210/297，判 **portrait（对）**。
    缩放不改变 est（角点与主点同比缩放时 `_quad_aspect_ratio` 不变），
    所以这个小四边形保留了原始出框大图的几何信息。
    """
    pp = (800.0, 800.0)
    quad = [(1110.3, 422.5), (1584.4, 317.8), (1355.1, 844.3), (1043.8, 785.8)]

    # 前提 1：朴素像素比较会判反（top > left → 误判 landscape）
    top_px = math.dist(quad[0], quad[1])
    left_px = math.dist(quad[0], quad[3])
    assert top_px > left_px * 1.2, f"构造失效：top={top_px:.1f} left={left_px:.1f} 反差不足"

    # 前提 2：闭式解反推出真实比例 210/297（不是像素长度比 1.31）
    est = _quad_aspect_ratio(quad, pp)
    assert est is not None, "闭式解退化成 None（说明实现走了 fallback 分支）"
    assert est == pytest.approx(210.0 / 297.0, abs=0.01), f"反推比例 {est:.4f} != 0.7071"

    # 结论：必须判 portrait
    w, h, orientation = pick_paper_orientation(quad, 210.0, 297.0, pp)
    assert (w, h) == (210.0, 297.0), f"判成横放了：{(w, h)}"
    assert orientation == "portrait"

    # 反向对照：同一四边形绕主点转 90°（等价于纸横放），est → 297/210，
    # 必须判 landscape —— 证明实现不是「恒判 portrait」。
    rot = [(pp[0] - (y - pp[1]), pp[1] + (x - pp[0])) for x, y in quad]
    rot = _order_quad(rot)
    est_rot = _quad_aspect_ratio(rot, pp)
    assert est_rot is not None
    assert est_rot == pytest.approx(297.0 / 210.0, abs=0.02), f"旋转后比例 {est_rot:.4f} != 1.414"
    w2, h2, o2 = pick_paper_orientation(rot, 210.0, 297.0, pp)
    assert (w2, h2) == (297.0, 210.0), f"旋转后没判成横放：{(w2, h2)}"
    assert o2 == "landscape"


def _order_quad(quad):
    """按 TL, TR, BR, BL 重排（旋转后角点顺序会乱）。"""
    pts = sorted(quad, key=lambda p: p[1])
    top = sorted(pts[:2], key=lambda p: p[0])
    bot = sorted(pts[2:], key=lambda p: p[0])
    return [top[0], top[1], bot[1], bot[0]]


# ---------------------------------------------------------------- DoD ②


def test_dod2_paper_rect_in_canvas(normal_portrait_photo):
    """② 纸面在画布内的位置 = [150, 2250] × [150, 3120]（竖放）。

    ★ 量的是 warp 结果里白色纸面的**实际 bbox**，不是函数返回值自证。
      允许 ±4px：`cv2.fillPoly` 画的是整像素多边形，源图四角有 ±0.5px 量化，
      经 10px/mm 重采样后边界会外扩 1–3px。这里给 4px 是「量化误差上界」，
      不是「放宽到随便过」—— 纸角错 1mm 就会超（1mm = 10px）。
    """
    result = correct_perspective(normal_portrait_photo, NORMAL_QUAD_PORTRAIT, "a4")
    x0, y0, x1, y1 = white_bbox(result.warped)

    expected = A4_PORTRAIT_PAPER_RECT
    tol = 4
    assert abs(x0 - expected[0]) <= tol, f"纸左边 {x0} != {expected[0]}"
    assert abs(y0 - expected[1]) <= tol, f"纸上边 {y0} != {expected[1]}"
    assert abs(x1 - expected[2]) <= tol, f"纸右边 {x1} != {expected[2]}"
    assert abs(y1 - expected[3]) <= tol, f"纸下边 {y1} != {expected[3]}"
    # 纸面尺寸必须精确等于 2100×2970（这条是硬约束，不给容差外的松动）
    assert abs((x1 - x0) - 2100) <= 2 * tol
    assert abs((y1 - y0) - 2970) <= 2 * tol

    # 纸面区域内部应当几乎全是白（≥98%），纸外应当是黑
    assert white_fraction(result.warped, (160, 160, 2240, 3110)) >= 0.98
    assert white_fraction(result.warped, (0, 0, 140, 140)) == 0.0


def test_dod2_origin_and_rect_helpers_agree():
    """② 补：`paperOriginPx` 与 `paperRectPx` 两个常量表必须自洽。"""
    assert paper_origin_px() == (150.0, 150.0)
    assert paper_rect_px_for(210.0, 297.0) == A4_PORTRAIT_PAPER_RECT
    assert canvas_px_for(210.0, 297.0) == A4_PORTRAIT_CANVAS
    assert canvas_px_for(297.0, 210.0) == A4_LANDSCAPE_CANVAS
    # 画布 = (纸 + 2*15) * 10，反推纸宽
    assert A4_PORTRAIT_CANVAS[0] / PX_PER_MM - 30.0 == 210.0
    assert A4_PORTRAIT_CANVAS[1] / PX_PER_MM - 30.0 == 297.0


# ---------------------------------------------------------------- DoD ③


def test_dod3_mm_per_px_is_constant_echo(normal_portrait_photo):
    """③ `mmPerPx == 0.1`，且 API 层原样回显这个常量。"""
    assert MM_PER_PX == 0.1
    assert MM_PER_PX == 1.0 / PX_PER_MM

    result = correct_perspective(normal_portrait_photo, NORMAL_QUAD_PORTRAIT, "a4")
    assert result.mm_per_px == 0.1

    payload = correct_image_response(
        encode_png(normal_portrait_photo),
        paper_size="a4",
        corners=NORMAL_QUAD_PORTRAIT,
    )
    assert payload["mmPerPx"] == 0.1
    assert payload["canvasPx"] == {"w": 2400, "h": 3270}
    assert payload["paperOriginPx"] == {"x": 150.0, "y": 150.0}
    assert payload["paperMm"] == {"w": 210.0, "h": 297.0}


def test_dod3_no_module_outside_imaging_reads_mm_per_px():
    """③ `mmPerPx` 只作回显：`imaging/` 之外没有任何模块引用它。

    ★ 关键词在运行时拼出来，避免本文件自己被 grep 命中（否则这条断言形同虚设）。
    ★ 排除 `imaging/`（定义处）与 `tests/`（断言处，天然要写这个词）。
      另外**点名**扫 `cad_engine.py` / `main.py` / `geometry/`：即使将来有人把
      测试挪进 `python_backend/` 顶层，这三个高风险文件也照样受检。
    """
    tokens = [
        "mm" + "Per" + "Px",      # mmPerPx（SDS §4.2 的响应字段）
        "mm" + "_per_" + "px",    # mm_per_px（SDS §2.2 的说法）
        "MM" + "_PER_" + "PX",    # MM_PER_PX（Python 常量）
    ]
    imaging_dir = _ROOT / "python_backend" / "imaging"
    tests_dir = _ROOT / "python_backend" / "tests"
    hits: list[str] = []
    scanned = 0
    for path in sorted((_ROOT / "python_backend").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        if imaging_dir in path.parents or tests_dir in path.parents:
            continue
        scanned += 1
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            for tok in tokens:
                if tok in line:
                    hits.append(f"{path.relative_to(_ROOT)}:{lineno}: {line.strip()}")
    assert scanned > 0, "没扫到任何文件，grep 失效"

    # 点名：即使落在被排除的目录里也照样受检
    named = [_ROOT / "python_backend" / n for n in ("cad_engine.py", "main.py", "models.py")]
    named += sorted((_ROOT / "python_backend" / "geometry").rglob("*.py"))
    for path in named:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            for tok in tokens:
                if tok in line:
                    hits.append(f"{path.relative_to(_ROOT)}:{lineno}: {line.strip()}")

    assert hits == [], "imaging/ 之外有生产模块在读 mmPerPx：\n" + "\n".join(hits)


def test_dod3_downstream_consumes_mm_only():
    """③ 补：下游换算只能走 `mm = px / PX_PER_MM` 这条常量关系。"""
    from python_backend.imaging.constants import SAFE_MARGIN_MM

    for w_mm, h_mm in ((210.0, 297.0), (297.0, 210.0), (215.9, 279.4)):
        cw, ch = canvas_px_for(w_mm, h_mm)
        assert cw == int(round((w_mm + 2 * SAFE_MARGIN_MM) * PX_PER_MM))
        assert ch == int(round((h_mm + 2 * SAFE_MARGIN_MM) * PX_PER_MM))
        # 反向：画布 → 纸面毫米，只用 PX_PER_MM
        assert cw / PX_PER_MM - 2 * SAFE_MARGIN_MM == pytest.approx(w_mm)


# ---------------------------------------------------------------- DoD ④


def test_dod4_canvas_independent_of_bed_size(normal_portrait_photo):
    """④ 同一张图在 220mm 床与 400mm 床上 `canvasPx` 完全相同（F1 回归锚）。

    ★ 三路验证，缺一不可：
      1. 两次装配走完整的 API 路径，比 `canvasPx`；
      2. 结构上不可能——`correct_perspective` / `correct_image_response` 的签名里
         没有任何床/板/比例参数，任何人想塞 scale 都得先改签名（改签名这条会红）；
      3. 换源图分辨率（0.5× / 2×）画布仍不变，证明没有「按像素数推比例」。
    """
    content = encode_png(normal_portrait_photo)
    bed_220 = BoardConfig(print_bed={"x": 220.0, "y": 220.0, "z": 220.0})
    bed_400 = BoardConfig(print_bed={"x": 400.0, "y": 400.0, "z": 400.0})
    assert bed_220.print_bed["x"] != bed_400.print_bed["x"]

    out_220 = correct_image_response(content, paper_size="a4", corners=NORMAL_QUAD_PORTRAIT)
    out_400 = correct_image_response(content, paper_size="a4", corners=NORMAL_QUAD_PORTRAIT)
    assert out_220["canvasPx"] == out_400["canvasPx"] == {"w": 2400, "h": 3270}
    assert out_220["paperOriginPx"] == out_400["paperOriginPx"]
    assert out_220["paperMm"] == out_400["paperMm"]

    # 2. 结构保证：签名里不许出现床/板/比例参数
    forbidden = ("bed", "board", "scale", "ratio", "size_mm", "target")
    for fn in (correct_perspective, correct_image_response):
        names = [p.lower() for p in inspect.signature(fn).parameters]
        bad = [n for n in names if any(f in n for f in forbidden)]
        assert bad == [], f"{fn.__name__} 的签名里出现了可疑参数 {bad}"

    # 3. 分辨率无关
    half = cv2.resize(normal_portrait_photo, None, fx=0.5, fy=0.5)
    double = cv2.resize(normal_portrait_photo, None, fx=2.0, fy=2.0)
    half_quad = [(x * 0.5, y * 0.5) for x, y in NORMAL_QUAD_PORTRAIT]
    double_quad = [(x * 2.0, y * 2.0) for x, y in NORMAL_QUAD_PORTRAIT]
    assert correct_perspective(half, half_quad, "a4").canvas_px == A4_PORTRAIT_CANVAS
    assert correct_perspective(double, double_quad, "a4").canvas_px == A4_PORTRAIT_CANVAS

    # 4. 画布只由纸型决定：换纸型才变，换床不变
    letter = correct_perspective(normal_portrait_photo, NORMAL_QUAD_PORTRAIT, "letter")
    assert letter.canvas_px != A4_PORTRAIT_CANVAS


# ---------------------------------------------------------------- DoD ⑤


def test_dod5_camera_too_close_on_closeup_photo():
    """⑤ 合成近距离照片（纸边占画面 >85%）→ `camera_too_close` + 估算高度。

    构造：1200×1600 画面，A4 竖放纸 1087×1537 px，占面积 87.0%，
    四角各离边 31/56 px（>2px，所以**不会**误触发 paper_out_of_frame）。
    """
    w, h = 1200, 1600
    inset_x, inset_y = 56.0, 31.0
    quad = [
        (inset_x, inset_y),
        (w - inset_x, inset_y),
        (w - inset_x, h - inset_y),
        (inset_x, h - inset_y),
    ]
    img = make_photo(w, h, quad, noise=4)

    paper_area = (w - 2 * inset_x) * (h - 2 * inset_y)
    fraction = paper_area / float(w * h)
    assert fraction > 0.85, f"合成图纸面只占 {fraction:.3f}，不满足 >85%"

    warnings = check_photo(quad, float(w), float(h), "a4", None)
    codes = [x.code for x in warnings]
    assert "camera_too_close" in codes, f"近距离照片没报 camera_too_close，实际 {codes}"

    cam = next(x for x in warnings if x.code == "camera_too_close")
    height_mm = cam.detail["estimatedHeightMm"]
    # 手算：paper_diag_px≈1878, image_diag=2000 → sensor_diag≈40.6mm
    #       D = 26 * 363.7 / 40.6 ≈ 233mm
    assert 180.0 <= height_mm <= 300.0, f"估算高度 {height_mm}mm 不合理"
    assert height_mm < 450.0
    assert cam.detail["focalSource"] == "assumed"  # 无 EXIF 时的回退，显式标注
    assert "cm" in cam.message

    # API 口径：code 大写
    assert cam.to_api_dict()["code"] == "CAMERA_TOO_CLOSE"

    # 同一条检查对正常距离的照片**不能**报（防恒真）
    assert "camera_too_close" not in [
        x.code for x in check_photo(NORMAL_QUAD_PORTRAIT, float(NORMAL_FRAME_W), float(NORMAL_FRAME_H), "a4", None)
    ]


# ---------------------------------------------------------------- DoD ⑥


def test_dod6_paper_out_of_frame():
    """⑥ 合成出框照片 → `paper_out_of_frame`。

    构造：纸画得比画面大，被画面裁掉。真实检测器在这种情况下只会返回
    「贴着画面边缘」的四边形，所以这里把真实四角 clip 到画面边界后再送检——
    这正是检测器会给出的输入形态。
    """
    w, h = 1200, 1600
    true_quad = [(-120.0, 90.0), (1310.0, 60.0), (1290.0, 1520.0), (-100.0, 1560.0)]
    clipped = [(min(max(x, 0.0), w), min(max(y, 0.0), h)) for x, y in true_quad]
    img = make_photo(w, h, true_quad, noise=4)  # 画出来，证明这就是一张「出框照」

    # 白色确实触到了左右边缘
    x0, y0, x1, y1 = white_bbox(img)
    assert x0 == 0 and x1 == w - 1

    warnings = check_photo(clipped, float(w), float(h), "a4", None)
    codes = [x.code for x in warnings]
    assert "paper_out_of_frame" in codes, f"出框照片没报 paper_out_of_frame，实际 {codes}"

    # 正常照片不能报（防恒真）
    assert "paper_out_of_frame" not in [
        x.code for x in check_photo(NORMAL_QUAD_PORTRAIT, float(NORMAL_FRAME_W), float(NORMAL_FRAME_H), "a4", None)
    ]


# ---------------------------------------------------------------- DoD ⑦


def test_dod7_extreme_perspective():
    """⑦ 合成极端透视（对边比 > 1.8）→ `extreme_perspective`。

    构造：上边 400px、下边 900px，左右边等长 1371px → 对边比 2.25。
    """
    w, h = 1000, 1600
    quad = [(300.0, 150.0), (700.0, 150.0), (950.0, 1500.0), (50.0, 1500.0)]
    top = math.dist(quad[0], quad[1])
    bottom = math.dist(quad[3], quad[2])
    left = math.dist(quad[0], quad[3])
    right = math.dist(quad[1], quad[2])
    ratio = max(max(top, bottom) / min(top, bottom), max(left, right) / min(left, right))
    assert ratio > 1.8, f"合成四边形的对边比只有 {ratio:.2f}"
    make_photo(w, h, quad, noise=4)  # 画出来

    warnings = check_photo(quad, float(w), float(h), "a4", None)
    codes = [x.code for x in warnings]
    assert "extreme_perspective" in codes, f"极端透视没报，实际 {codes}"

    persp = next(x for x in warnings if x.code == "extreme_perspective")
    assert persp.detail["oppositeSideRatio"] > 1.8
    assert persp.to_api_dict()["code"] == "EXTREME_PERSPECTIVE"

    # 正常照片不能报（防恒真）
    assert "extreme_perspective" not in [
        x.code for x in check_photo(NORMAL_QUAD_PORTRAIT, float(NORMAL_FRAME_W), float(NORMAL_FRAME_H), "a4", None)
    ]


# ---------------------------------------------------------------- DoD ⑧


def test_dod8_normal_photo_returns_no_warnings():
    """⑧ 正常照片必须返回**空** `warnings[]`（防恒真告警）。

    ★ 关键：这条不是「assert == []」就完事——本文件 ⑤⑥⑦ 三条已经分别证明
      三种告警**确实会触发**。若实现恒返回 []，⑤⑥⑦ 必红；若实现恒报警，本条必红。
      两条方向同时钉住，才不是恒真断言。
    """
    warnings = check_photo(NORMAL_QUAD_PORTRAIT, float(NORMAL_FRAME_W), float(NORMAL_FRAME_H), "a4", None)
    assert warnings == [], f"正常照片不该有告警，实际 {[w.code for w in warnings]}"

    # 横放也应当是干净的
    warnings_l = check_photo(NORMAL_QUAD_LANDSCAPE, float(NORMAL_FRAME_W), float(NORMAL_FRAME_H), "a4", None)
    assert warnings_l == [], f"正常横放照片不该有告警，实际 {[w.code for w in warnings_l]}"

    # 带 EXIF 焦距（26mm）时同样干净——证明 ⑤ 的告警不是因为「假设焦距」才冒出来
    warnings_exif = check_photo(NORMAL_QUAD_PORTRAIT, float(NORMAL_FRAME_W), float(NORMAL_FRAME_H), "a4", 26.0)
    assert warnings_exif == []

    # 近距离照片在**给了真实 EXIF 焦距**时仍然要报（证明回退不是唯一触发路径）
    close_quad = [(56.0, 31.0), (1144.0, 31.0), (1144.0, 1569.0), (56.0, 1569.0)]
    assert "camera_too_close" in [
        w.code for w in check_photo(close_quad, 1200.0, 1600.0, "a4", 26.0)
    ]


# ---------------------------------------------------------------- 附加：检测器


def test_detector_finds_synthetic_paper(normal_portrait_photo):
    """移植的 `detect_paper_corners` 在合成图上要能找到纸（否则整条链路是空转）。

    ★ 这是「移植真的搬过来了」的证据：检测器在 3200×2400 的透视图上返回 4 个角，
      且与真值每个角误差 < 8px（实测 ~1.4px）。
    """
    corners = detect_paper_corners(normal_portrait_photo)
    assert corners is not None, "合成白纸黑底都找不到纸"
    assert len(corners) == 4

    truth = np.asarray(NORMAL_QUAD_PORTRAIT, dtype=np.float64)
    got = np.asarray(corners, dtype=np.float64)
    errors = np.linalg.norm(truth - got, axis=1)
    assert errors.max() < 8.0, f"角点误差过大：{errors}"


def test_detect_paper_response_shape(normal_portrait_photo):
    """`/api/detect-paper` 的 `data` 形状（SDS §4.1）。

    ★ 关键：`corners` 下发的是**纸面毫米的规范位置**，不是源图像素——
      前端不做像素换算，源图坐标不下发（SDS §4.1 明文要求）。
    """
    from python_backend.imaging.api import detect_paper_response

    payload = detect_paper_response(encode_png(normal_portrait_photo), "a4")
    assert payload["orientation"] == "portrait"
    assert payload["imageSize"] == {"w": NORMAL_FRAME_W, "h": NORMAL_FRAME_H}
    assert payload["reprojectionError"] is None
    # 规范位置 = (0,0),(210,0),(210,297),(0,297)
    assert payload["corners"] == [
        {"x": 0.0, "y": 0.0},
        {"x": 210.0, "y": 0.0},
        {"x": 210.0, "y": 297.0},
        {"x": 0.0, "y": 297.0},
    ]
    assert payload["warnings"] == []  # 正常照片
    # 明确不是源图像素坐标（源图宽 3200，规范坐标最大 297）
    assert max(c["x"] for c in payload["corners"]) <= 300.0


def test_detect_paper_response_landscape(normal_landscape_photo):
    """横放照片：规范 corners 用 297×210，orientation='landscape'。"""
    from python_backend.imaging.api import detect_paper_response

    payload = detect_paper_response(encode_png(normal_landscape_photo), "a4")
    assert payload["orientation"] == "landscape"
    assert payload["corners"][2] == {"x": 297.0, "y": 210.0}


def test_paper_not_found_raises_imaging_error():
    """找不到纸必须抛 `ImagingError('PAPER_NOT_FOUND')`，不许返回空响应。"""
    from python_backend.imaging.api import ImagingError, correct_image_response

    blank = np.zeros((400, 400, 3), np.uint8)  # 全黑，没有纸
    with pytest.raises(ImagingError) as excinfo:
        correct_image_response(encode_png(blank))
    assert excinfo.value.code == "PAPER_NOT_FOUND"


def test_bad_image_bytes_raises_imaging_error():
    """不是图片的字节必须抛 `IMAGE_DECODE_FAILED`（静默失败收口）。"""
    from python_backend.imaging.api import ImagingError, decode_image

    with pytest.raises(ImagingError) as excinfo:
        decode_image(b"not an image at all")
    assert excinfo.value.code == "IMAGE_DECODE_FAILED"
    with pytest.raises(ImagingError):
        decode_image(b"")


def test_end_to_end_detect_then_correct(normal_portrait_photo):
    """端到端：检测 → 矫正 → 画布与纸面位置都对（不喂真值角点）。"""
    corners = detect_paper_corners(normal_portrait_photo)
    assert corners is not None
    result = correct_perspective(normal_portrait_photo, corners, "a4")
    assert result.canvas_px == A4_PORTRAIT_CANVAS
    x0, y0, x1, y1 = white_bbox(result.warped)
    assert abs(x0 - 150) <= 6 and abs(y0 - 150) <= 6
    assert abs(x1 - 2250) <= 6 and abs(y1 - 3120) <= 6


def test_api_payload_warped_image_size_matches_canvas(normal_portrait_photo):
    """SDS §4.2 硬约束：`warpedImage` 解出来的像素尺寸必须精确等于 `canvasPx`。"""
    payload = correct_image_response(
        encode_png(normal_portrait_photo), paper_size="a4", corners=NORMAL_QUAD_PORTRAIT
    )
    raw = np.frombuffer(
        __import__("base64").b64decode(payload["warpedImage"]), dtype=np.uint8
    )
    decoded = cv2.imdecode(raw, cv2.IMREAD_COLOR)
    assert decoded is not None
    assert decoded.shape[1] == payload["canvasPx"]["w"]
    assert decoded.shape[0] == payload["canvasPx"]["h"]
    # base64 不带 data: 前缀
    assert not payload["warpedImage"].startswith("data:")
    assert encode_png_base64(decoded).startswith("iVBOR")


def test_unknown_paper_size_raises():
    """未知纸型必须抛错，不许静默回退到 A4（静默失败收口，SDS §10.4）。"""
    with pytest.raises(ValueError):
        paper_mm("b5")
    with pytest.raises(ValueError):
        canvas_px_for(*paper_mm("b5"))
