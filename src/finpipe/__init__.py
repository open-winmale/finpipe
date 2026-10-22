"""finpipe — WinMale 个股开放数据 SDK。

机器可读数据目录（catalog/）+ OpenAPI 取数客户端。

    import finpipe

    cat = finpipe.catalog.load()                     # 数据目录（域/函数/参数/返回 schema）
    fn = cat.function("kline.query_bars")

    cli = finpipe.Client.from_env()                  # 不配置凭证则自动使用内置体验 appid
    bars = cli.call("kline.query_bars", sym="600519", limit=30)
"""
from finpipe.catalog import Catalog, load
from finpipe.client import BatchResult, Client, normalize_symbol
from finpipe.errors import (
    ApiError, AuthError, CatalogError, FinPipeError, LimitError, ServerError,
    TransportError, UsageError,
)

__version__ = "0.1.0"

__all__ = [
    "Catalog", "load", "Client", "BatchResult", "normalize_symbol", "__version__",
    "FinPipeError", "AuthError", "UsageError", "LimitError", "TransportError",
    "ServerError", "ApiError", "CatalogError",
]
