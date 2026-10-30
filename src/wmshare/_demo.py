"""离线演示客户端：随包罐头数据（真实 probe 样本的固定快照），零凭证、不联网。

定位：先看输出再配凭证的首跑路径、示例离线试跑、教学演示。数据与真实返回
同构同单位（率/分位=小数、金额=元、量=股、K 线按日期降序），但**不是实时
行情**——接真实数据用 ``wmshare.Client.from_env()``。
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable

from wmshare.client import BatchResult
from wmshare.errors import UsageError
from wmshare.notice_stream import NoticeStreamEvent

SYMBOLS: tuple[str, ...] = ("600519", "000001", "300750")
WATCHLIST: tuple[str, ...] = ("600519", "000858", "601088", "600900", "601318")

# 公告变更事件罐头（字段与 notice_stream.NoticeStreamEvent 对齐）
_NOTICE_EVENTS: list[dict[str, Any]] = [
    {"seq": 42, "eid": "demo-ev-1", "market": "cn", "code": "600519",
     "name": "贵州茅台", "type": "回购", "title": "关于回购股份的公告",
     "date": "2026-10-28", "announce_date": "2026-10-28",
     "available_at": "2026-10-28 18:05:00",
     "url": "https://example.com/demo-notice.pdf", "pdf_url": ""},
]

_INCOME_ROWS: list[dict[str, Any]] = [
    {"k": "revenue", "cn": "营业收入",
     "vals": {"2025": 1.741e11, "2024": 1.709e11}},
    {"k": "operating_cost", "cn": "营业成本",
     "vals": {"2025": 2.91e10, "2024": 2.87e10}},
    {"k": "operating_profit", "cn": "营业利润",
     "vals": {"2025": 1.172e11, "2024": 1.148e11}},
    {"k": "net_profit", "cn": "净利润",
     "vals": {"2025": 8.72e10, "2024": 8.59e10}},
    {"k": "np_parent_company", "cn": "归属于母公司股东的净利润",
     "vals": {"2025": 8.65e10, "2024": 8.52e10}},
]
_BALANCE_ROWS: list[dict[str, Any]] = [
    {"k": "total_assets", "cn": "资产总计",
     "vals": {"2025": 2.976e11, "2024": 2.789e11}},
    {"k": "total_liabilities", "cn": "负债合计",
     "vals": {"2025": 4.24e10, "2024": 3.94e10}},
    {"k": "total_equity", "cn": "股东权益合计",
     "vals": {"2025": 2.552e11, "2024": 2.395e11}},
]
_CASHFLOW_ROWS: list[dict[str, Any]] = [
    {"k": "operating_cash_flow", "cn": "经营活动产生的现金流量净额",
     "vals": {"2025": 9.12e10, "2024": 9.24e10}},
    {"k": "investing_cash_flow", "cn": "投资活动产生的现金流量净额",
     "vals": {"2025": -2.31e9, "2024": -1.87e9}},
]
_STATEMENT_ROWS = {"income": _INCOME_ROWS, "balance": _BALANCE_ROWS,
                   "cashflow": _CASHFLOW_ROWS}


def _slice_years(rows: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
    # 与真实行为一致：years=N → vals 至多 N 期（test_live 同款不变量）
    return [{**r, "vals": dict(list(r["vals"].items())[:n])} for r in rows]


def _compare_rows(rows: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, r in enumerate(_slice_years(rows, n)):
        c = r["vals"]
        if i == 0:  # 首个科目母公司未披露：p 仅参考、差额为空
            out.append({"k": r["k"], "cn": r["cn"], "c": c,
                        "p": {y: round(v * 0.97, 2) for y, v in c.items()},
                        "diff": None, "diffp": None})
        else:
            p = {y: round(v * 0.98, 2) for y, v in c.items()}
            diff = {y: c[y] - p[y] for y in c}
            out.append({"k": r["k"], "cn": r["cn"], "c": c, "p": p,
                        "diff": diff, "diffp": {y: diff[y] / c[y] for y in c}})
    return out


def _bars(n: int, start: float = 1300.0) -> list[dict[str, Any]]:
    # 与真实 API 同构：按日期降序（最新在前）——消费方须自己升序后再算指标
    rows = [{"date": f"2026-{3 + i // 28:02d}-{1 + i % 28:02d}", "close": start + i,
             "percent": 0.01, "volume": 3_000_000.0, "amount": 4.5e9}
            for i in range(n)]
    return rows[::-1]


def _maybe_df(rows: list[dict[str, Any]], _df: bool) -> Any:
    if not _df:
        return rows
    try:
        import pandas as pd
    except ImportError as e:
        raise UsageError("_df=True 需要 pandas：pip install \"wmshare[dataframe]\"") from e
    return pd.DataFrame(rows)


class DemoClient:
    """``wmshare.Client`` 的离线演示替身：同调用面、罐头数据、零网络零凭证。

    repr 与文档均明示「演示数据、固定快照」；量级守护与单位换算不在此复现
    （罐头数据本身就是基础单位口径）。未覆盖的底层函数返回空表。
    """

    def __init__(self) -> None:
        def batch_all(name: str, symbols: list[str], **kw: Any) -> BatchResult:
            return BatchResult(results={s: {"close": 1.0} for s in symbols},
                               requests=-(-len(symbols) // 500))

        def batch_iter(name: str, symbols: list[str], **kw: Any) -> Any:
            yield batch_all(name, symbols, **kw)

        def call_batch(name: str, symbols: list[str], **kw: Any) -> BatchResult:
            if name == "bonus.snapshot_yield_ttm":
                return BatchResult(results={s: 0.0396 for s in symbols}, requests=1)
            return BatchResult(results={s: {"close": 1.0} for s in symbols}, requests=1)

        indicator_values = {"$PE_TTM_LAST": 20.0, "$ROE_TTM_LAST": 0.3324,
                            "$PCT_PE_TTM_10Y_LAST": 0.42,
                            "$CUR_IND_ROE_PCT_LAST": 1.0}

        def notice_poller(*, group: str, consumer: str,
                          on_events: Callable | None = None, **kw: Any) -> SimpleNamespace:
            acked = False

            def poll_now() -> list[NoticeStreamEvent]:
                nonlocal acked
                if acked:  # 进度已确认：与真实轮询器一致，ack 后不重投
                    return []
                acked = True
                evs = [NoticeStreamEvent.from_dict(r, market="cn")
                       for r in _NOTICE_EVENTS]
                if on_events is not None:
                    on_events(evs)
                return evs

            return SimpleNamespace(
                poll_now=poll_now,
                start=lambda: None,
                stop=lambda timeout: None,
                seek_oldest=lambda market: 0,
                running=lambda: False,
            )

        self.kline = SimpleNamespace(
            bars=lambda *a, **k: _maybe_df(_bars(k.get("n") or 5), k.get("_df", False)),
            snapshot=lambda *a, **k: {"close": 1309.69, "chg_20d": 0.0123},
        )
        self.moneyflow = SimpleNamespace(
            last=lambda *a, **k: {"net_mf": 821186700.0},
            bars=lambda *a, **k: _maybe_df([{"net_mf": 100.0} for _ in range(20)],
                                           k.get("_df", False)),
        )
        self.statements = SimpleNamespace(
            income=lambda *a, **k: _slice_years(_INCOME_ROWS, k.get("years") or 5),
            balance=lambda *a, **k: _slice_years(_BALANCE_ROWS, k.get("years") or 5),
            cashflow=lambda *a, **k: _slice_years(_CASHFLOW_ROWS, k.get("years") or 5),
            years=lambda symbol, kind="income", _df=False: ["2025", "2024"],
            compare=lambda symbol, kind="income", years=2, _df=False:
                _compare_rows(_STATEMENT_ROWS.get(kind, _INCOME_ROWS), years or 2),
            audit=lambda symbol: {"2024": "标准无保留意见", "2023": "标准无保留意见"},
        )
        self.indicator = SimpleNamespace(
            get=lambda symbol, code: indicator_values.get(code),
            metrics=lambda symbol, codes: {c: indicator_values.get(c) for c in codes},
        )
        self.notice = SimpleNamespace(
            list=lambda *a, **k: [{"date": "2026-10-28", "title": "关于回购股份的公告"}],
            has_buyback=lambda *a, **k: True,
        )
        self.dividend = SimpleNamespace(
            last=lambda *a, **k: {"ex_div": "2026-06-26", "dps": 28.02, "total": 3.5e10},
            yield_ttm=lambda *a, **k: 0.0396,
            screen_quality=lambda *a, **k: True,
            history=lambda *a, **k: _maybe_df(
                [{"ex_div": f"2026-0{i}-26", "dps": 28.0 + i, "payout_ratio": 0.8}
                 for i in range(1, 4)], k.get("_df", False)),
            index_where_high_yield_5=lambda *a, **k: "index_where: bonus_yield_5y > 0.03",
        )
        self.info = SimpleNamespace(
            profile=lambda *a, **k: {"name": "贵州茅台", "industry": "白酒",
                                     "listing_date": "2001-08-27"},
        )
        self.stocks = SimpleNamespace(
            list=lambda *a, **k: [
                {"symbol": "600519", "name": "贵州茅台", "exchange": "SSE",
                 "industry_name": "白酒", "is_st": False, "listed": "2001-08-27"},
                {"symbol": "000001", "name": "平安银行", "exchange": "SZSE",
                 "industry_name": "银行", "is_st": False, "listed": "1991-04-03"},
                {"symbol": "300750", "name": "宁德时代", "exchange": "SZSE",
                 "industry_name": "电池", "is_st": False, "listed": "2018-06-11"},
            ],
            industries=lambda level, *a, **k: [{"symbol": "S48", "name": "白酒"},
                                               {"symbol": "S49", "name": "银行"}],
            industry_members=lambda hint, *a, **k: [
                {"symbol": s, "name": n, "industry_name": "银行", "is_st": False,
                 "listed": "2001-08-27"}
                for s, n in zip(WATCHLIST, ("贵州茅台", "五粮液", "中国神华",
                                            "长江电力", "中国平安"))],
        )
        self.screener = SimpleNamespace(
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
        )
        self.valuation = SimpleNamespace(
            hist_stats=lambda *a, **k: {"avg": 21.43, "current": 21.42698311427773,
                                        "max": 28.724504202872666, "median": 20.621,
                                        "min": 17.661621153011183, "pct": 0.5374,
                                        "count": 749, "series": []},
        )
        self.batch_all = batch_all
        self.batch_iter = batch_iter
        self.call_batch = call_batch
        self.notice_poller = notice_poller
        self.call = lambda name, **kw: (
            _bars(kw.get("limit") or 5) if name == "kline.query_bars" else [])

    def __repr__(self) -> str:
        return ("wmshare.demo_client()  # 离线演示数据（固定快照，非真实行情）；"
                "接真实数据请 wmshare.Client.from_env()")


def demo_client() -> DemoClient:
    """创建离线演示客户端：零凭证、不联网，数据为随包固定快照（非真实行情）。

    与 ``Client`` 同调用面（门面命名空间 + 批量入口 + 公告轮询器桩），
    覆盖 README 首跑块与 examples/ 全部演示路径::

        import wmshare

        cli = wmshare.demo_client()
        print(cli.dividend.yield_ttm("600519"))   # 0.0396（演示快照，小数）
        print(cli.indicator.get("600519", "$PCT_PE_TTM_10Y_LAST"))   # 0.42
    """
    return DemoClient()
