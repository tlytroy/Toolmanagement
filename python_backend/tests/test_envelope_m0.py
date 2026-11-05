"""0.8 静默失败收口：统一信封 + 端点级失败可观测。

★ 为什么这组测试存在（实证）：
  旧引擎对「自交轮廓」是**静默成功**的 —— 实测 bowtie 基元得到
  `success=True`、`volume_mm3=599530.73`，与**完全不给基元**的基线**一字不差**。
  也就是说用户点了「生成」，拿到一块没有槽的整板，界面显示成功。
  0.8 的全部意义就是把这类「成功但结果是废件」变成 `success:false` + `error.code`。

★ 为什么直调路由函数而不是 `TestClient`：
  本环境的 venv 里**没有 httpx**，`fastapi.testclient` 依赖它，装不了
  （M0 不允许动 requirements.txt）。路由函数是 `async def`，用 `asyncio.run` 直调
  覆盖的是同一段业务代码；HTTP 序列化层不在本里程碑的断言范围内。
"""
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import main  # noqa: E402


# ---------------------------------------------------------------- fixtures
def _rect(x0: float, y0: float, x1: float, y1: float) -> list[dict]:
    """闭合矩形轮廓（px，纸面 y-down）。"""
    return [
        {"type": "line", "p0": {"x": x0, "y": y0}, "p1": {"x": x1, "y": y0}},
        {"type": "line", "p0": {"x": x1, "y": y0}, "p1": {"x": x1, "y": y1}},
        {"type": "line", "p0": {"x": x1, "y": y1}, "p1": {"x": x0, "y": y1}},
        {"type": "line", "p0": {"x": x0, "y": y1}, "p1": {"x": x0, "y": y0}},
    ]


# 自交四边形：对角交叉，shoelace 面积恰好 0（正负抵消）
BOWTIE = [
    {"type": "line", "p0": {"x": 100, "y": 100}, "p1": {"x": 300, "y": 300}},
    {"type": "line", "p0": {"x": 300, "y": 300}, "p1": {"x": 300, "y": 100}},
    {"type": "line", "p0": {"x": 300, "y": 100}, "p1": {"x": 100, "y": 300}},
    {"type": "line", "p0": {"x": 100, "y": 300}, "p1": {"x": 100, "y": 100}},
]

# 共线三点：闭合但完全退化
COLLINEAR = [
    {"type": "line", "p0": {"x": 100, "y": 100}, "p1": {"x": 200, "y": 100}},
    {"type": "line", "p0": {"x": 200, "y": 100}, "p1": {"x": 300, "y": 100}},
    {"type": "line", "p0": {"x": 300, "y": 100}, "p1": {"x": 100, "y": 100}},
]

FOAM = {
    "mode": "foam",
    "foam": {
        "length_mm": 200.0,
        "width_mm": 150.0,
        "height_mm": 20.0,
        "fillet_radius": 5.0,
        "stackable": False,
    },
    "tool_offset": 1.0,
    "embed_depth": 15.0,
    "finger_slots": [],
}


def _cad(primitives: list[dict], **over) -> dict:
    req = main.GenerateCADRequest(primitives=primitives, **{**FOAM, **over})
    return asyncio.run(main.generate_cad(req))


# ---------------------------------------------------------------- 信封结构
def test_envelope_success_shape():
    """成功信封：success/data/warnings/error 四键齐全，error 必须是 None。"""
    out = _cad(_rect(100, 100, 1100, 700))

    assert out["success"] is True
    assert out["error"] is None
    assert out["warnings"] == []
    assert isinstance(out["data"], dict)
    # 冻结前端读的是顶层字段，所以 data 的键必须同时铺在顶层
    assert out["stl_base64"]
    assert out["data"]["stl_base64"] == out["stl_base64"]
    assert out["summary"]["volume_mm3"] > 0


def test_envelope_failure_shape():
    """失败信封：success=False、data=None、error 是 {code,message,detail} 对象。"""
    out = _cad(BOWTIE)

    assert out["success"] is False
    assert out["data"] is None
    assert isinstance(out["error"], dict)
    assert out["error"]["code"]
    assert out["error"]["message"]
    assert isinstance(out["error"]["detail"], dict)
    # 冻结前端（src/hooks/useWorkflow.ts）读的是字符串，这里给一份兜底副本
    assert isinstance(out["error_message"], str) and out["error_message"]


# ---------------------------------------------------------------- DoD ①
def test_self_intersecting_polygon_fails_the_request():
    """0.8 DoD ①：自交多边形 → success:false 且 error.code 非空。"""
    out = _cad(BOWTIE)

    assert out["success"] is False
    assert out["error"]["code"] == "GEOMETRY_INVALID"
    assert out["error"]["detail"]["stage"] == "validate_primitives"
    # 必须点名是自交，而不是笼统的「失败」
    assert "Self-intersection" in out["error"]["detail"]["reason"]


def test_degenerate_collinear_polygon_fails_the_request():
    """共线退化轮廓同样必须失败（旧引擎对它是静默成功）。"""
    out = _cad(COLLINEAR)

    assert out["success"] is False
    assert out["error"]["code"] == "GEOMETRY_INVALID"
    assert out["error"]["detail"]["reason"]


def test_bad_polygon_never_returns_a_slotless_board():
    """回归锚：失败响应里**不能**夹带 stl_base64。

    旧引擎的静默失败形态就是「success 为真 + 一块没槽的板」；一旦失败路径
    还带着 STL，前端会照样把废件存下来。
    """
    out = _cad(BOWTIE)
    assert "stl_base64" not in out
    assert "summary" not in out


def test_empty_primitives_still_succeeds_but_is_not_a_failure():
    """空基元不是错误：用户可以不选工具，直接要一块底板。"""
    out = _cad([])
    assert out["success"] is True
    assert out["summary"]["volume_mm3"] > 0


# ---------------------------------------------------------------- 引擎降级可观测
def test_engine_errors_become_warnings(monkeypatch):
    """旧引擎 except 里 append 的计数，必须升级成响应里的 warnings[]。

    这是 0.8「只允许在冻结文件的 except 加一行计数」这条约束的兑现方式：
    计数本身不说话，是 main.py 的信封层把它翻成 warning。
    """
    real = main.generate_stl

    def fake(params):
        result = real(params)
        import cad_engine

        cad_engine.errors.append("模拟：工具槽布尔运算失败")
        return result

    monkeypatch.setattr(main, "generate_stl", fake)
    out = _cad(_rect(100, 100, 1100, 700))

    assert out["success"] is True
    codes = [w["code"] for w in out["warnings"]]
    assert codes == ["ENGINE_DEGRADED"]
    assert "工具槽布尔运算失败" in out["warnings"][0]["message"]
    # 计数必须被清空，否则第二个请求会带着上一个请求的 warning
    import cad_engine

    assert cad_engine.errors == []


def test_engine_errors_do_not_leak_between_requests(monkeypatch):
    """上一请求的降级计数不能污染下一请求。"""
    import cad_engine

    real = main.generate_stl

    def fake(params):
        cad_engine.errors.append("模拟：一次性失败")
        return real(params)

    monkeypatch.setattr(main, "generate_stl", fake)
    first = _cad(_rect(100, 100, 1100, 700))
    monkeypatch.setattr(main, "generate_stl", real)
    second = _cad(_rect(100, 100, 1100, 700))

    assert first["warnings"], "第一个请求应该带 warning"
    assert second["warnings"] == []


# ---------------------------------------------------------------- 其它端点
def test_detect_paper_failure_keeps_string_error(monkeypatch):
    """`/detect-paper` 的失败响应里 `error` 必须是**字符串**。

    ★ 这条断言看起来和「统一信封」相反，但它保护的是一个真实的崩溃点：
      冻结前端 `src/features/workspace/Workspace.tsx:88` 把 `result.error` 直接塞进
      `processError`，而 `src/features/calibration/CalibrationPanel.tsx:61` 用
      `{detectError}` 当 React child 渲染 —— 一旦 `error` 变成对象，React 会抛
      「Objects are not valid as a React child」，整页白屏。
      结构化错误放在 `error_info`，前端解冻后改读 `error_info.code` 即可。
    """
    import io

    from starlette.datastructures import UploadFile

    monkeypatch.setattr(main, "detect_paper_corners", lambda _img: [])
    upload = UploadFile(filename="x.png", file=io.BytesIO(_tiny_png()))
    out = asyncio.run(main.detect_paper(upload))

    assert out["success"] is False
    assert isinstance(out["error"], str), "冻结前端会把 error 当 React child 渲染"
    assert out["error"] == "未检测到纸张"
    # 结构化错误不能丢
    assert out["error_info"]["code"] == "PAPER_NOT_FOUND"


def _tiny_png() -> bytes:
    import io

    import numpy as np
    from PIL import Image

    buf = io.BytesIO()
    Image.fromarray(np.full((16, 16, 3), 255, dtype=np.uint8)).save(buf, format="PNG")
    return buf.getvalue()


def test_auto_finger_slots_failure_uses_envelope(monkeypatch):
    """/auto-finger-slots 的 except 也必须走信封（不能 print 后返回裸 dict）。"""

    def boom(*_a, **_kw):
        raise RuntimeError("模拟检测失败")

    monkeypatch.setattr(main, "_auto_detect_finger_slots", boom)
    req = main.AutoFingerSlotsRequest(primitives=_rect(100, 100, 1100, 700), **{
        k: v for k, v in FOAM.items() if k != "finger_slots"
    })
    out = asyncio.run(main.auto_finger_slots(req))

    assert out["success"] is False
    assert out["error"]["code"] == "INTERNAL"
    assert "模拟检测失败" in out["error"]["message"]


# ---------------------------------------------------------------- DoD ②
def test_new_modules_have_no_except_print():
    """0.8 DoD ②：新模块禁止 `except ...:` 后紧跟 `print(`。"""
    roots = [_BACKEND / name for name in ("geometry", "imaging", "domain")]
    offenders: list[str] = []

    for root in roots:
        for path in sorted(root.rglob("*.py")):
            lines = path.read_text(encoding="utf-8").splitlines()
            for i, line in enumerate(lines):
                if not re.match(r"\s*except\b.*:\s*$", line):
                    continue
                # 往下看三行，跳过空行与注释
                for nxt in lines[i + 1: i + 4]:
                    stripped = nxt.strip()
                    if not stripped or stripped.startswith("#"):
                        continue
                    if stripped.startswith("print("):
                        offenders.append(f"{path.relative_to(_BACKEND)}:{i + 1}")
                    break

    assert offenders == [], f"新模块里仍有 except -> print：{offenders}"


def test_no_bare_except_in_new_modules():
    """新模块禁止裸 `except:`（会吞掉 KeyboardInterrupt / SystemExit）。"""
    offenders = []
    for name in ("geometry", "imaging", "domain"):
        for path in sorted((_BACKEND / name).rglob("*.py")):
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
                if re.match(r"\s*except\s*:\s*$", line):
                    offenders.append(f"{path.relative_to(_BACKEND)}:{i + 1}")
    assert offenders == [], f"存在裸 except：{offenders}"


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
