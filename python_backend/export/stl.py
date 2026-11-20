"""Manifold → STL base64 导出（接线层，SDS §4.5）。

`geometry.generate_insert` 返回的 `base` 是 `manifold3d.Manifold`；这里转成
STL 字节再 base64。参考旧 `cad_engine.py` 的写法：`trimesh.exchange.stl.export_stl`。

★ 往返验证时若要把 base64 再 load 回来做 checks，必须 `trimesh.load(..., process=True)`，
  否则 `is_watertight` 会误报 False（STL 是三角汤，process 会合并顶点重建拓扑）。
  本模块导出用 manifold 直接转 mesh，不做 roundtrip，所以不受影响。
"""
from __future__ import annotations

import base64

from trimesh.exchange.stl import export_stl as _export_stl
from geometry.validate import _to_trimesh


def manifold_to_stl_base64(manifold_obj) -> tuple[str, int]:
    """返回 `(base64_str, byte_len)`。空实体抛 ValueError。"""
    if manifold_obj.is_empty():
        raise ValueError("cannot export empty manifold")
    mesh = _to_trimesh(manifold_obj)
    blob: bytes = _export_stl(mesh)
    return base64.b64encode(blob).decode("ascii"), len(blob)


__all__ = ["manifold_to_stl_base64"]
