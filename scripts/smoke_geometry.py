#!/usr/bin/env python
"""M-1 冒烟：合成 100×20mm 矩形 → generate_insert → 三条断言。

用法（**项目根**下）：
    .venv/bin/python scripts/smoke_geometry.py

★ 导入根是 `python_backend/`（不是仓库根）：与 `cd python_backend && uvicorn main:app`
  的运行时一致，包内一律 `from geometry.xxx` / `from domain.xxx`，**没有** `python_backend.` 前缀。
  所以这里往 `sys.path` 塞的是 `_ROOT / "python_backend"`。

★ 三条断言证明三件事：环境能跑、F1（密闭空腔）的开口为真、DoD 可离线复现。
★ `clearance = 0.0` 与 `slot_chamfer = 0.0` **必须显式设**：默认 clearance 0.4 会让
  槽长变 100.8（第③条必红）；chamfer 1.5 会把切刀 bbox 撑宽 3mm。

★ 反向验证（改动后必须自己破坏一次，确认断言会红；三条都已实测）：
  ① 切刀刺出顶面：把 `pockets.py` 的 `TOP_OVERHANG_MM` 由 `1.0` 改 `0.0` → ① 红
     （`bb[5] - top_z = 0.0`），②③ 仍绿。
  ② 首击在槽底：**正确的破坏方式是「切刀整体下沉 1mm」**（把 `TOP_OVERHANG_MM` 保持 1.0，
     同时把切刀 translate 的 z 从 `top_z - depth` 改成 `top_z - depth - 1.0`）→
     ①② **同时**红（`hits=[0.0, 3.0]`，`first_hit=3.0 ≠ 4.0`）。
     ★ 更正：只把 `TOP_OVERHANG_MM` 改成 0（"去掉 +1"）**只会让 ① 红，② 仍绿** ——
       切刀顶面与板顶面共面时布尔仍能开出盲槽，射线照样打到槽底（实测 `hits=[0.0, 4.0]`）。
       所以"去掉 +1"不是 ② 的有效破坏项，任务书原来那句预期对盲槽几何不成立。
     ★ 另两种同样能点红 ② 的破坏：切刀整体下沉 3mm、槽底抬高 2mm（`depth` 实际少 2mm）。
  ③ 槽长 100 ± 0.1：把 `clearance` 改 `0.4` → ③ 红（`pocket_length_mm = 100.8`）。
"""
from __future__ import annotations

import sys
from pathlib import Path

# 允许从项目根直接 `python scripts/smoke_geometry.py`
# ★ 导入根是 python_backend/（与 `cd python_backend && uvicorn main:app` 一致）
_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _ROOT / "python_backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import numpy as np
import trimesh

from domain.models import BoardConfig, Project, Tool, Vec2
from geometry import generate_insert

# —— 合成件参数 ——
PAPER_W, PAPER_H = 210.0, 297.0
TOOL_W, TOOL_H = 100.0, 20.0
THICKNESS = 12
EMBED = 8.0
EXPECTED_POCKET_LEN = 100.0


def build_project() -> Project:
    """纸面坐标居中于纸心（210×297）的 100×20 矩形工具。"""
    cx, cy = PAPER_W / 2.0, PAPER_H / 2.0
    hw, hh = TOOL_W / 2.0, TOOL_H / 2.0
    outer = [
        Vec2(cx - hw, cy - hh),
        Vec2(cx + hw, cy - hh),
        Vec2(cx + hw, cy + hh),
        Vec2(cx - hw, cy + hh),
    ]
    tool = Tool(id="tool_1", name="合成 100x20", outer=outer)
    board = BoardConfig(
        shape="rect",
        size_mode="fit-tools",
        margin=12.0,
        thickness=THICKNESS,
        corner_r=5.0,
        embed_depth=EMBED,
        clearance=0.0,       # ★ 必须显式置 0（默认 0.4 → 槽长 100.8）
        slot_chamfer=0.0,    # ★ 必须显式置 0（默认 1.5 → bbox 撑宽 3mm）
    )
    return Project(schema_version=1, paper_w=PAPER_W, paper_h=PAPER_H,
                   tools=[tool], board=board)


def to_trimesh(m) -> trimesh.Trimesh:
    """manifold3d.Manifold → trimesh.Trimesh（SDS §10.1 实测写法）。"""
    mesh = m.to_mesh()
    verts = np.asarray(mesh.vert_properties)[:, :3].astype(float)
    faces = np.asarray(mesh.tri_verts)
    return trimesh.Trimesh(vertices=verts, faces=faces, process=False)


def main() -> int:
    project = build_project()
    result = generate_insert(project)

    board_solid = result["base_uncut"]
    board_cut = result["base"]
    cutter = result["slot_cutter"]
    pocket_length_mm = result["pocket_length_mm"]
    top_z = result["top_z"]
    depth = result["tools"][0]["depth"]

    bb = cutter.bounding_box()          # 扁平 6 元组 (minx,miny,minz,maxx,maxy,maxz)
    print("=" * 66)
    print("M-1 冒烟：合成 100×20mm 矩形")
    print("=" * 66)
    print(f"paper            : {project.paper_w} × {project.paper_h} mm")
    print(f"board_mm         : {result['board_mm'][0]} × {result['board_mm'][1]} mm")
    print(f"top_z            : {top_z} mm   (= thickness {THICKNESS})")
    print(f"depth            : {depth} mm   (= embed_depth {EMBED})")
    print(f"pocket_length_mm : {pocket_length_mm} mm")
    print(f"cutter bbox      : {bb}")
    print(f"  bb[5] (maxZ)   : {bb[5]}   → bb[5] - top_z = {bb[5] - top_z}")
    print(f"  bb[2] (minZ)   : {bb[2]}   → 期望 top_z - depth = {top_z - depth}")
    print(f"base volume      : {board_cut.volume():.3f} mm^3")
    print(f"uncut volume     : {board_solid.volume():.3f} mm^3")
    print(f"removed volume   : {board_solid.volume() - board_cut.volume():.3f} mm^3 "
          f"(期望 ≈ 100 × 20 × 8 = 16000)")
    print(f"base is_empty    : {board_cut.is_empty()}")
    print(f"base status      : {board_cut.status()}")
    print(f"warnings         : {result['warnings']}")
    print("-" * 66)

    # ① 切刀确实刺出顶面（F1 修复本体）
    assert bb[5] > top_z + 0.9, (
        f"① 红：切刀未刺出顶面 —— bb[5]={bb[5]}，top_z={top_z}，"
        f"bb[5]-top_z={bb[5] - top_z}（要求 > 0.9）"
    )
    print(f"① OK  切刀刺出顶面：bb[5] - top_z = {bb[5] - top_z:.4f} > 0.9")

    # ② 首击在槽底，不在顶面
    mesh = to_trimesh(board_cut)
    loc, _, _ = mesh.ray.intersects_location(
        ray_origins=[[0.0, 0.0, top_z + 10.0]],
        ray_directions=[[0.0, 0.0, -1.0]],
    )
    assert len(loc) > 0, (
        "② 红：射线打空 —— 先查槽是否被切成通孔，再看 bb[5]-top_z 是否 > 0.9。"
        f"（bb[5]-top_z={bb[5] - top_z:.4f}，hits={len(loc)}）"
    )
    first_hit = max(float(p[2]) for p in loc)   # loc 不按距离排序，必须取 z 最大者
    print(f"② raycast hits  : {[round(float(p[2]), 4) for p in loc]}  → first_hit(z_max) = {first_hit:.4f}")
    assert abs(first_hit - (top_z - depth)) < 0.05, (
        f"② 红：首击不在槽底 —— first_hit={first_hit:.4f}，"
        f"期望 top_z - depth = {top_z - depth}（容差 0.05）"
    )
    print(f"② OK  首击在槽底：first_hit = {first_hit:.4f} ≈ top_z - depth = {top_z - depth}")

    # ③ 槽长 100 ± 0.1（容差表 SDS §10.3，不是 ±1）
    assert abs(pocket_length_mm - EXPECTED_POCKET_LEN) < 0.1, (
        f"③ 红：槽长不对 —— pocket_length_mm={pocket_length_mm}，"
        f"期望 {EXPECTED_POCKET_LEN}（容差 0.1）"
    )
    print(f"③ OK  槽长：{pocket_length_mm} ≈ {EXPECTED_POCKET_LEN}（容差 0.1）")

    print("=" * 66)
    print("SMOKE PASS —— 三条断言全过")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    sys.exit(main())
