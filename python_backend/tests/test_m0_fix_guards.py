"""M0 审核 P0 修复的护栏测试（主会话 2026-11-06 接手补写）。

覆盖：
- P0-1 统一导入根：生产代码零 `from python_backend` 残留；`cd python_backend` 下
  `import geometry, domain, imaging` 必须成功（防止再分裂成两套导入根）。
- P0-2 numpy 2.x 下 `/auto-finger-slots` 不再抛 complex128 的 TypeError，
  且返回的 slot 坐标全为有限实数（不能是复数，否则 JSON 序列化直接崩）。
- P1 `GET /` 走统一信封。
- P2 `PX_PER_MM` 双份常量保持一致（cad_engine 冻结，不 import 新包）。
"""
from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
_PROJECT = _BACKEND.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import main  # noqa: E402
from imaging import PX_PER_MM as IMAGING_PX_PER_MM  # noqa: E402


# ---------------------------------------------------------------- P0-1 导入根
def test_import_root_is_uniform() -> None:
    """生产运行口径 `cd python_backend && uvicorn main:app` 下，三包必须都能 import。"""
    py = _PROJECT / ".venv" / "bin" / "python"
    proc = subprocess.run(
        [str(py), "-c", "import geometry, domain, imaging, main; print('OK')"],
        cwd=str(_BACKEND),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, (
        f"统一导入根失败（rc={proc.returncode}）\n"
        f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
    )
    assert "OK" in proc.stdout


def test_no_python_backend_prefix_in_production() -> None:
    """生产模块里不许再有 `from python_backend...`（会与裸导入互斥）。"""
    hits: list[str] = []
    for path in sorted(_BACKEND.rglob("*.py")):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        if path.suffix == ".bak":
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if "from python_backend" in line or "import python_backend" in line:
                hits.append(f"{path.relative_to(_PROJECT)}:{lineno}: {line.strip()}")
    assert hits == [], "生产代码仍存在包绝对导入：\n" + "\n".join(hits)


# ---------------------------------------------------------------- P0-2 eigh
def test_auto_finger_slots_succeeds_on_valid_primitives() -> None:
    """正常输入下 `_auto_detect_finger_slots` 不再因 complex128 崩，且坐标是有限实数。"""
    import cad_engine as ce

    prim = [
        {"type": "line", "p0": {"x": 0, "y": 0}, "p1": {"x": 1000, "y": 0}},
        {"type": "line", "p0": {"x": 1000, "y": 0}, "p1": {"x": 1000, "y": 200}},
        {"type": "line", "p0": {"x": 1000, "y": 200}, "p1": {"x": 0, "y": 200}},
        {"type": "line", "p0": {"x": 0, "y": 200}, "p1": {"x": 0, "y": 0}},
    ]
    slots = ce._auto_detect_finger_slots(prim, 200.0, 150.0, 20.0)
    assert len(slots) > 0, "水平矩形应当产出 2 个手槽建议"
    for s in slots:
        for k, v in s.items():
            if isinstance(v, (int, float, complex)) and not isinstance(v, bool):
                # complex 会在 json.dumps 直接崩；明确禁止
                assert not isinstance(v, complex), f"{k} 是复数 {v}"
                assert math.isfinite(float(v)), f"{k} 不是有限数 {v}"


def test_eigh_returns_real_main_axis() -> None:
    """根因回归：`np.linalg.eigh(实对称 cov)` 返回 float64，不是 complex128。

    ★ 含一条源码断言：冻结的 `cad_engine.py` 必须真的用 `eigh`，不许被改回
      `eig`。只测 numpy 自身行为是恒真的（改坏 cad_engine 照样绿），必须锚到实现。
    """
    import numpy as np

    src = (_BACKEND / "cad_engine.py").read_text(encoding="utf-8")
    assert "np.linalg.eigh(cov)" in src, "cad_engine.py 没用 eigh（P0-2 修法被撤）"
    assert "np.linalg.eig(cov)" not in src, "cad_engine.py 又退回 eig"

    pts = np.array([[0.0, 0.0], [1000.0, 0.0], [1000.0, 200.0], [0.0, 200.0]])
    centered = pts - pts.mean(axis=0)
    vals, vecs = np.linalg.eigh(np.cov(centered.T))
    axis = vecs[:, int(np.argmax(vals))]
    assert np.isrealobj(axis), f"主轴仍是复数 dtype={axis.dtype}"
    # 水平矩形的主轴必须沿 x（不能换到短轴）
    assert abs(float(axis[0])) > abs(float(axis[1])), f"主轴方向错了: {axis}"


# ---------------------------------------------------------------- P1 信封
def test_root_uses_unified_envelope() -> None:
    """`GET /` 也必须返回 `{success,data,warnings,error}`。"""
    import asyncio

    resp = asyncio.run(main.root())
    for key in ("success", "data", "warnings", "error"):
        assert key in resp, f"根路由缺 {key}"
    assert resp["success"] is True
    assert resp["error"] is None
    assert resp["data"]["message"] == "Tool Management Backend API"


# ---------------------------------------------------------------- P2 常量一致
def test_px_per_mm_constants_agree() -> None:
    """`cad_engine.py` 与 `imaging/constants.py` 的 10 px/mm 必须一致。

    cad_engine 冻结不 import 新包，双份常量靠本测试守住。
    """
    import cad_engine as ce

    assert float(ce.PX_PER_MM) == pytest.approx(float(IMAGING_PX_PER_MM))
    assert float(IMAGING_PX_PER_MM) == pytest.approx(10.0)
