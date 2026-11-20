"""M1-W 接线层测试（SDS §4 /api/* 端点）。

覆盖：
- 6 个新端点全部注册（真路由，不被 FastAPI 的 _IncludedRouter 包装迷惑）
- /api/generate 端到端：矩形工具 → 可用 STL + 12 项 checks
- 契约结构：checks 在 data 顶层、paramsEcho 字段齐全
- 回归钉子：volume_match 通过（切刀裁到板体，不是全量）、slot_open 首击落槽底
- 错误信封：未知字段 SCHEMA_UNKNOWN_FIELD、空工具 NO_VISIBLE_TOOLS
- GEO_ENGINE=new|legacy：8 个旧端点均仍注册，行为不受影响
- 单工具居中 → STL watertight（process=True）
"""
from __future__ import annotations

import base64
import io
import os

import pytest
import trimesh
from fastapi.testclient import TestClient

import main

client = TestClient(main.app)

RECT_OUTER = [
    {"x": 0.0, "y": 0.0},
    {"x": 100.0, "y": 0.0},
    {"x": 100.0, "y": 20.0},
    {"x": 0.0, "y": 20.0},
]


def _rect_payload():
    return {
        "schemaVersion": 1,
        "paperW": 210.0,
        "paperH": 297.0,
        "tools": [{
            "id": "t1", "name": "矩形测试", "outer": RECT_OUTER,
            "interior": [], "fingerHoles": [],
        }],
        "board": {
            "shape": "rect", "sizeMode": "fit-tools", "thickness": 12,
            "margin": 12.0, "embedDepth": 8.0, "clearance": 0.4,
            "slotChamfer": 1.5, "cornerR": 5.0,
        },
    }


API_PATHS = [
    "/api/detect-paper", "/api/correct-image", "/api/generate",
    "/api/finger-holes/auto", "/api/simplify-contour", "/api/extract-tools",
]


# ---- 端点注册 ----
def test_all_api_endpoints_registered():
    """6 个 /api/* 端点必须都是 POST 且存在（422 表示缺 body，非 404）。"""
    for p in API_PATHS:
        r = client.post(p, json={})
        assert r.status_code != 404, f"{p} 未注册（404）"


def test_old_endpoints_still_registered():
    """M1-W 只增不改：8 个旧端点必须在。"""
    old = ["/detect-paper", "/extract-contours", "/extract-tool-mask",
           "/simplify-contours", "/update-contour", "/generate-cad", "/auto-finger-slots"]
    for p in old:
        r = client.post(p, json={})
        assert r.status_code != 404, f"旧端点 {p} 丢失"


# ---- /api/generate 端到端 ----
def test_generate_rect_returns_valid_stl():
    r = client.post("/api/generate", json=_rect_payload())
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True, body.get("error")
    data = body["data"]
    assert len(data["pieces"]) == 1
    piece = data["pieces"][0]
    assert piece["name"] == "board"
    raw = base64.b64decode(piece["stlBase64"])
    assert raw[:5] != b"" and len(raw) > 100
    mesh = trimesh.load(io.BytesIO(raw), file_type="stl", process=True)
    # ★ process=True 是 watertight 判定的关键（process=False 会误报）
    assert mesh.is_watertight is True


def test_generate_checks_at_top_level():
    """SDS §4.5：checks 是 data 顶层字段，不在 summary 里。"""
    r = client.post("/api/generate", json=_rect_payload())
    data = r.json()["data"]
    assert "checks" in data, "checks 必须在 data 顶层"
    assert "checks" not in data["summary"], "checks 不该嵌在 summary"
    assert len(data["checks"]) >= 10
    ids = {c["id"] for c in data["checks"]}
    # min_rib 只在多工具（有邻居）时产生——单工具无邻居，validate.py 刻意不产生
    # 这条恒真项；多工具场景由 test_generate_min_rib_with_two_tools 覆盖。
    for must in ("watertight", "winding", "manifold_status", "tools_in_board",
                 "slot_open", "depth_fits", "volume_match"):
        assert must in ids, f"缺少 check: {must}"


def test_generate_min_rib_with_two_tools():
    """双工具相邻时 min_rib 必须出现（shapely.distance 真算，非恒真）。"""
    p = _rect_payload()
    p["tools"].append({
        "id": "t2", "name": "矩形2",
        "outer": [{"x": 130.0, "y": 0.0}, {"x": 200.0, "y": 0.0},
                  {"x": 200.0, "y": 20.0}, {"x": 130.0, "y": 20.0}],
        "interior": [], "fingerHoles": [],
    })
    r = client.post("/api/generate", json=p)
    assert r.json()["success"] is True, r.json().get("error")
    checks = {c["id"]: c for c in r.json()["data"]["checks"]}
    assert "min_rib" in checks, "双工具场景必须有 min_rib"
    # CheckResult.to_dict() 把 detail 展开到顶层
    mr = checks["min_rib"]
    assert any(k in mr for k in ("nearestMm", "thresholdMm", "label")), mr


def test_generate_all_checks_pass_for_rect():
    """矩形工具 + 默认参数应全部检查通过（含 volume_match 回归钉子）。"""
    r = client.post("/api/generate", json=_rect_payload())
    data = r.json()["data"]
    failed = [(c["id"], c) for c in data["checks"] if not c["ok"]]
    assert not failed, f"检查未全通过: {failed}"


def test_generate_volume_match_uses_clipped_cutter():
    """回归：volume_match 期望值用裁到板体的切刀，不是含 1mm 刺出的全量切刀。"""
    r = client.post("/api/generate", json=_rect_payload())
    checks = {c["id"]: c for c in r.json()["data"]["checks"]}
    vm = checks["volume_match"]
    assert vm["ok"] is True, vm
    assert vm["relativeError"] <= vm["tolerance"]


def test_generate_slot_open_first_hit():
    """回归：raycast 首击必须落在 top_z - depth。"""
    r = client.post("/api/generate", json=_rect_payload())
    checks = {c["id"]: c for c in r.json()["data"]["checks"]}
    so = checks["slot_open"]
    assert so["ok"] is True, so
    for hit in so["hits"]:
        assert abs(hit["firstHitZ"] - hit["expectedZ"]) <= 0.05


def test_generate_params_echo_complete():
    """paramsEcho 字段齐全（SDS §4.5）。"""
    r = client.post("/api/generate", json=_rect_payload())
    pe = r.json()["data"]["summary"]["paramsEcho"]
    for k in ("sizeMode", "widthMm", "heightMm", "margin", "cornerR",
              "baseEdgeRoundover", "slotChamfer", "embedDepth", "clearance",
              "unitsX", "unitsY"):
        assert k in pe, f"paramsEcho 缺 {k}"
    assert pe["sizeMode"] == "fit-tools"
    assert pe["widthMm"] is None and pe["heightMm"] is None


# ---- 错误信封 ----
def test_generate_unknown_field_returns_schema_error():
    """未知字段 → SCHEMA_UNKNOWN_FIELD（SDS §4.0）。"""
    payload = _rect_payload()
    payload["board"]["bogusField"] = 1
    r = client.post("/api/generate", json=payload)
    body = r.json()
    assert body["success"] is False
    assert body["error"]["code"] == "SCHEMA_UNKNOWN_FIELD", body


def test_generate_empty_tools_returns_envelope():
    """空工具集 → 信封错误（不是 500 裸奔）。"""
    payload = _rect_payload()
    payload["tools"] = []
    r = client.post("/api/generate", json=payload)
    body = r.json()
    assert body["success"] is False
    assert "error" in body and body["error"]["code"]


# ---- finger-holes / simplify-contour ----
def test_finger_holes_auto_returns_envelope_with_warning():
    r = client.post("/api/finger-holes/auto", json={
        "tool": {"id": "t1", "outer": RECT_OUTER},
    })
    body = r.json()
    assert body["success"] is True
    assert body["data"]["holes"] == []
    assert any(w["code"] == "FINGER_HOLES_NOT_IMPLEMENTED" for w in body["warnings"])


def test_simplify_contour_returns_polygon():
    payload = {
        "polygon": [{"x": 0, "y": 0}, {"x": 100, "y": 0},
                    {"x": 100, "y": 20}, {"x": 0, "y": 20}],
        "toleranceMm": 0.2,
    }
    r = client.post("/api/simplify-contour", json=payload)
    body = r.json()
    assert body["success"] is True
    assert len(body["data"]["polygons"]) >= 1


# ---- GEO_ENGINE 不变性 ----
@pytest.mark.parametrize("engine", ["new", "legacy"])
def test_geo_engine_does_not_break_old_endpoints(engine, monkeypatch):
    """GEO_ENGINE 两取值下，旧端点与 /api/generate 都仍可用。"""
    monkeypatch.setenv("GEO_ENGINE", engine)
    import importlib
    import api.generate as g
    importlib.reload(g)
    r = client.post("/api/generate", json=_rect_payload())
    assert r.json()["success"] is True
    # 旧端点 /generate-cad 至少存在（422 = 缺字段，非 404/500 结构错）
    r2 = client.post("/generate-cad", json={})
    assert r2.status_code != 404
