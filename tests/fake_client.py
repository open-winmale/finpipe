"""共享假客户端：按 examples/ 用到的接口派发罐头数据，示例测试端到端跑 main(cli)。

罐头值一律基础单位口径（率/分位=小数、金额=元、量=股），与真实返回同构——
示例测试因此同时是「返回长这样」的可执行文档。签名校验由 test_docs 的
AST 门禁负责；本文件只负责让示例逻辑真的跑起来。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from wmshare.client import BatchResult

SYMBOLS = ("600519", "000001", "300750")
WATCHLIST = ("600519", "000858", "601088", "600900", "601318")


def _bars(n: int, start: float = 1300.0) -> list[dict]:
    return [{"date": f"2026-{3 + i // 28:02d}-{1 + i % 28:02d}", "close": start + i,
             "percent": 0.01, "volume": 3_000_000.0, "amount": 4.5e9}
            for i in range(n)]


def _maybe_df(rows: list[dict], _df: bool):
    if not _df:
        return rows
    pd = pytest.importorskip("pandas")
    return pd.DataFrame(rows)


def fake_client() -> SimpleNamespace:
    """覆盖 9 个示例全部 cli.* 调用面的最小假客户端。"""

    def batch_all(name, symbols, **kw):
        return BatchResult(results={s: {"close": 1.0} for s in symbols},
                           requests=-(-len(symbols) // 500))

    def batch_iter(name, symbols, **kw):
        yield batch_all(name, symbols, **kw)

    def call_batch(name, symbols, **kw):
        if name == "bonus.snapshot_yield_ttm":
            return BatchResult(results={s: 0.0379 for s in symbols}, requests=1)
        return BatchResult(results={s: {"close": 1.0} for s in symbols}, requests=1)

    indicator_values = {"$PE_TTM_LAST": 20.0, "$ROE_TTM_LAST": 0.3324,
                        "$PCT_PE_TTM_10Y_LAST": 0.2115149040424663,
                        "$CUR_IND_ROE_PCT_LAST": 1.0}

    return SimpleNamespace(
        kline=SimpleNamespace(
            bars=lambda *a, **k: _maybe_df(_bars(k.get("n") or 5), k.get("_df", False)),
            snapshot=lambda *a, **k: {"close": 1309.69, "chg_20d": 0.0123},
        ),
        moneyflow=SimpleNamespace(
            last=lambda *a, **k: {"net_mf": -100.0},
            bars=lambda *a, **k: _maybe_df([{"net_mf": 100.0} for _ in range(20)],
                                           k.get("_df", False)),
        ),
        statements=SimpleNamespace(
            income=lambda *a, **k: [{"k": "x", "cn": "收入", "vals": {}}] * 3,
        ),
        indicator=SimpleNamespace(
            get=lambda symbol, code: indicator_values.get(code),
        ),
        notice=SimpleNamespace(
            list=lambda *a, **k: [{"date": "2026-10-01", "title": "测试公告"}],
        ),
        dividend=SimpleNamespace(
            last=lambda *a, **k: {"ex_div": "2026-06-26", "dps": 28.02, "total": 3.5e10},
            yield_ttm=lambda *a, **k: 0.0379,
            screen_quality=lambda *a, **k: True,
            history=lambda *a, **k: _maybe_df(
                [{"ex_div": f"2026-0{i}-26", "dps": 28.0 + i, "payout_ratio": 0.8}
                 for i in range(1, 4)], k.get("_df", False)),
            index_where_high_yield_5=lambda *a, **k: "index_where: bonus_yield_5y > 0.03",
        ),
        info=SimpleNamespace(
            profile=lambda *a, **k: {"name": "贵州茅台", "industry": "白酒",
                                     "listing_date": "2001-08-27"},
        ),
        stocks=SimpleNamespace(
            list=lambda *a, **k: [{"symbol": c, "name": "公司", "exchange": "SSE",
                                   "industry_name": "白酒", "listed": "2001-08-27"}
                                  for c in SYMBOLS],
            industries=lambda level, *a, **k: [{"symbol": "S48", "name": "白酒"},
                                               {"symbol": "S49", "name": "银行"}],
            industry_members=lambda hint, *a, **k: [
                {"symbol": c, "name": "公司", "industry_name": "银行", "listed": "2001-08-27"}
                for c in WATCHLIST],
        ),
        screener=SimpleNamespace(
            screen_limit_up=lambda *a, **k: False,
            screen_above_ma20=lambda *a, **k: True,
            screen_volume_spike=lambda *a, **k: False,
            screen_up_today=lambda *a, **k: True,
            index_breadth_summary=lambda *a, **k: {
                "total": 5685, "up": 4567, "down": 934, "flat": 184,
                "up_pct": 80.3, "down_pct": 16.4, "flat_pct": 3.2,
                "median_pct": 0.015363},
            index_breadth_bins=lambda *a, **k: [
                {"label": "涨停", "count": 23, "pct_of_total": 0.4},
                {"label": "大涨", "count": 210, "pct_of_total": 3.7},
                {"label": "上涨", "count": 4334, "pct_of_total": 76.2}],
            index_top_movers=lambda *a, **k: [
                {"symbol": "600519", "name": "贵州茅台", "percent": 0.0521},
                {"symbol": "000858", "name": "五粮液", "percent": 0.0311}],
        ),
        valuation=SimpleNamespace(
            hist_stats=lambda *a, **k: {"avg": 21.43, "current": 21.42698311427773,
                                        "max": 28.724504202872666, "median": 20.621,
                                        "min": 17.661621153011183, "pct": 0.5374,
                                        "count": 749, "series": []},
        ),
        batch_all=batch_all,
        batch_iter=batch_iter,
        call_batch=call_batch,
        call=lambda *a, **k: [],
    )
