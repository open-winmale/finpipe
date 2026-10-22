"""统一异常体系：全部继承 FinPipeError，并带 code/status 便于程序化分类。

CatalogError 同时继承 KeyError，兼容既有 `except KeyError` 用法。
"""
from __future__ import annotations


class FinPipeError(RuntimeError):
    """带修复建议的统一错误基类。"""

    def __init__(self, message: str, *, code: str = "", status: int | None = None):
        super().__init__(message)
        self.code = code
        self.status = status


class AuthError(FinPipeError):
    """凭证缺失/无效/被拒（OAuth 或 401/403）。"""


class UsageError(FinPipeError):
    """调用方式错误：未知/缺失参数、_df 依赖缺失等。"""


class LimitError(FinPipeError):
    """请求体积超过客户端上限（max_limit）。"""


class TransportError(FinPipeError):
    """网络层失败（连接/超时，重试耗尽）。"""


class ServerError(FinPipeError):
    """服务端 5xx。"""


class ApiError(FinPipeError):
    """服务端返回业务错误（success=false 或其他 4xx）。"""


class CatalogError(FinPipeError, KeyError):
    """目录中不存在该函数/域/指标/不兼容版本（同时兼容 KeyError 捕获）。"""
