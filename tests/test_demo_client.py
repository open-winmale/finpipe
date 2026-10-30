"""演示客户端门禁：README 首跑块承诺的调用面、单位口径与轮询语义不回退。

demo_client 是零凭证首跑的唯一入口，它的罐头值必须与 README 注释同值
（同一 probe 快照），单位必须与全库口径一致（率/分位=小数、金额=元、量=股）。
"""
from __future__ import annotations

import sys

import pandas as pd
import pytest

import wmshare
from wmshare.errors import UsageError
from wmshare.notice_stream import NoticeStreamEvent


@pytest.fixture(scope="module")
def cli():
    return wmshare.demo_client()


def test_repr_marks_demo_data():
    r = repr(wmshare.demo_client())
    assert "演示" in r and "非真实行情" in r


def test_readme_first_run_surface(cli):
    """README 首跑块的每一行调用都要真实可跑且输出与注释同值。"""
    assert cli.dividend.yield_ttm("600519") == 0.0396
    assert cli.indicator.get("600519", "$PCT_PE_TTM_10Y_LAST") == 0.42
    codes = [r["symbol"] for r in cli.stocks.list()]
    assert len(codes) == 3
    res = cli.batch_all("kline.snapshot", codes)
    assert len(res.results) == 3 and res.requests == 1


def test_units_are_base(cli):
    """全库单位铁律在演示数据上同样成立。"""
    assert cli.dividend.yield_ttm("600519") < 1          # 率=小数
    assert cli.dividend.last("600519")["dps"] > 1        # DPS=元/股
    assert cli.moneyflow.last("600519")["net_mf"] > 1e6  # 金额=元
    bar = cli.kline.bars("600519", n=3)[0]
    assert 100 < bar["close"] < 10000 and bar["volume"] > 1e4  # 价格=元、量=股
    breadth = cli.screener.index_breadth_summary()
    assert breadth["up_pct"] > 1 and 0 <= breadth["median_pct"] < 1  # pct 百分数、median 小数


def test_bars_are_date_descending(cli):
    dates = [b["date"] for b in cli.kline.bars("600519", n=5)]
    assert dates == sorted(dates, reverse=True)


def test_statements_shapes_match_real(cli):
    """报表行结构与 live 探针一致：科目行 k/cn/vals；compare 含 c/p/diff/diffp。"""
    for kind in ("income", "balance", "cashflow"):
        rows = getattr(cli.statements, kind)("600519", years=2)
        assert rows and all({"k", "cn", "vals"} <= set(r) for r in rows)
    assert cli.statements.years("600519", "income") == ["2025", "2024"]
    assert set(cli.statements.audit("600519")) == {"2024", "2023"}
    cmp_rows = cli.statements.compare("600519", "income", years=2)
    assert {"c", "p", "diff", "diffp", "k"} <= set(cmp_rows[0])
    diff_rows = [r for r in cmp_rows if r.get("diff")]
    assert diff_rows, "演示报表应有部分科目可比出差额"
    for r in diff_rows:  # 与 live 探针同款不变量：diffp = diff / 合并值（小数）
        for y in r["diff"]:
            assert abs(r["diffp"][y] - r["diff"][y] / r["c"][y]) < 1e-6


def test_notice_poller_ack_semantics(cli):
    """轮询桩复刻真实语义：首轮交付并回调，ack 后不重投。"""
    seen: list[list[NoticeStreamEvent]] = []
    poller = cli.notice_poller(group="demo", consumer="w1", on_events=seen.append)
    first = poller.poll_now()
    assert len(first) == 1 and isinstance(first[0], NoticeStreamEvent)
    assert first[0].title == "关于回购股份的公告"
    assert len(seen) == 1 and seen[0] == first  # on_events 回调被触发
    assert poller.poll_now() == []              # ack 后不重投


def test_df_needs_pandas(monkeypatch):
    """无 pandas 时 _df=True 报带安装指引的 UsageError（不是裸 ImportError）。"""
    monkeypatch.setitem(sys.modules, "pandas", None)
    cli = wmshare.demo_client()
    with pytest.raises(UsageError, match="wmshare\\[dataframe\\]"):
        cli.kline.bars("600519", n=3, _df=True)


def test_df_returns_dataframe(cli):
    df = cli.kline.bars("600519", n=3, _df=True)
    assert isinstance(df, pd.DataFrame) and len(df) == 3


def test_batch_entries_and_call(cli):
    batch = cli.call_batch("bonus.snapshot_yield_ttm", ["600519"], on_error="skip")
    assert batch.results["600519"] == 0.0396 and batch.requests == 1
    assert cli.batch_iter("kline.snapshot", ["600519", "000001"]).__next__().requests == 1
    assert len(cli.call("kline.query_bars", sym="600519", limit=5)) == 5
    assert cli.call("kline.snapshot", sym="600519") == []  # 未覆盖函数返回空表
