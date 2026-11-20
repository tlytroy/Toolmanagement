"""把领域/几何/成像异常映射成 SDS §4.0 的 `{code,message,detail}`。

新端点统一在路由里 `except` 这些异常，转成 `main._fail(...)`。
这样错误码来自异常自带的 `.code`，不靠匹配中文串（SDS 明令禁止）。
"""
from __future__ import annotations

from domain.models import DomainError


def error_payload(exc: Exception) -> tuple[str, str, dict]:
    """返回 `(code, message, detail)`，code 属 SDS §4.0 枚举。

    - `DomainError`（models）与 `GeometryError`（geometry.polygon）都带 `.code`；
    - `ImagingError`（imaging.api）带 `.code/.message/.detail`；
    - 未知异常 → `INTERNAL`，detail 带异常类型（可诊断，但不泄露栈）。
    """
    code = getattr(exc, "code", None)
    message = getattr(exc, "message", None) or str(exc)
    detail = getattr(exc, "detail", None)
    if not isinstance(detail, dict):
        detail = {}
    if not code:
        return ("INTERNAL", message, {"type": type(exc).__name__})
    # 兜底：任何非 SDS 枚举的 code 也归 INTERNAL，但保留原码便于诊断
    return (str(code), message, dict(detail))


__all__ = ["error_payload", "DomainError"]
