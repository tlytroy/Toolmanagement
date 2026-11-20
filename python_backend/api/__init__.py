"""M1-W 接线层：SDS §4 的 /api/* 端点支撑模块。

- `schemas.py`：camelCase ↔ snake_case 桥接（Pydantic v2）
- `errors.py`  ：异常 → SDS 错误码映射
- `generate.py`：/api/generate 逻辑核心（含 checks / STL 导出）
"""
