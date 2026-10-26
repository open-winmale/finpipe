"""finpipe — WinMale 个股开放数据 SDK。

机器可读数据目录（catalog/）+ OpenAPI 取数客户端。返回值统一基础单位：
比率/涨跌幅=小数（0.332=33.2%）、金额/价格/市值=元（报表原币）、股数/成交量=股；
每次返回都经过目录声明的量级守护与关系不变量校验（违例抛 DataError）。

    import finpipe

    cat = finpipe.load()                             # 数据目录（域/函数/参数/返回 schema）
    fn = cat.function("kline.query_bars")

    cli = finpipe.Client.from_env()                  # 不配置凭证则自动使用内置体验 appid
    bars = cli.call("kline.query_bars", sym="600519", limit=30)
    # _units="native" 保留脚本输出单位；_raw=True 返回 store 原始行；
    # Client(validate=False) 关闭校验（换算仍执行）
"""
from finpipe.catalog import Catalog, load
from finpipe.client import BatchResult, Client, normalize_symbol
from finpipe.errors import (
    ApiError, AuthError, CatalogError, DataError, FinPipeError, LimitError,
    ServerError, TransportError, UsageError,
)

__version__ = "1.4.2"

__all__ = [
    "Catalog", "load", "Client", "BatchResult", "normalize_symbol", "__version__",
    "skill_dir",
    "FinPipeError", "AuthError", "UsageError", "LimitError", "TransportError",
    "ServerError", "ApiError", "DataError", "CatalogError",
]


def skill_dir():
    """随包分发的 AI agent skill 目录（Agent Skills 格式，含 SKILL.md）。

    装入 agent（复制到其发现路径之一）::

        cp -r "$(python3 -c 'import finpipe; print(finpipe.skill_dir())')" \\
            ~/.agents/skills/finpipe
    """
    from pathlib import Path

    return Path(__file__).resolve().parent / "skills" / "finpipe"
