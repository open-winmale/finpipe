"""openwm — WinMale 个股开放数据 SDK。

机器可读数据目录（catalog/）+ OpenAPI 取数客户端。

    import openwm as wm

    cat = wm.catalog.load()                     # 数据目录（域/函数/参数/返回 schema）
    fn = cat.function("kline.query_bars")

    cli = wm.Client.from_env()                  # 凭证：环境变量或 ~/.winmale/credentials.env
    bars = cli.call("kline.query_bars", sym="600519", limit=30)
"""
from openwm.catalog import Catalog, load
from openwm.client import Client

__version__ = "0.1.0"

__all__ = ["Catalog", "load", "Client", "__version__"]
