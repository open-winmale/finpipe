"""API 设计新增能力：标的归一、批量调用、错误分类、目录检索、会话生命周期。"""
from __future__ import annotations

import pytest

import finpipe
from finpipe.catalog import load
from finpipe.client import BatchResult, Client, normalize_symbol
from finpipe.errors import (
    ApiError, AuthError, CatalogError, FinPipeError, LimitError, TransportError,
    UsageError,
)


class FakeSession:
    def __init__(self, result=None):
        self.calls = []
        self.result = result if result is not None else [{"ok": True}]
        self.closed = False

    def post(self, url, json=None, data=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json})
        outer = self

        class R:
            status_code = 200
            text = "{}"
            headers = {}

            def raise_for_status(self):
                pass

            def json(self):
                if url.endswith("/v1/oauth/token"):
                    return {"data": {"access_token": "tok", "expires_in": 3600}}
                return {"success": True, "data": {"result": outer.result}}
        return R()

    def close(self):
        self.closed = True


@pytest.fixture()
def cli():
    return Client(base_url="https://t", client_id="i", client_secret="s",
                  catalog=load(), session=FakeSession())


def last_ev(cli) -> dict:
    return [x for x in cli.session.calls if x["url"].endswith("/xs/eval")][-1]["json"]


# ---------------------------------------------------------------- 标的归一
@pytest.mark.parametrize("raw,expected", [
    ("600519", "600519"),
    ("sh.600519", "600519"),
    ("cn.600519", "600519"),
    ("sz.000001", "000001"),
    ("bj.430047", "430047"),
    ("600519.SH", "600519"),
    ("000001.SZ", "000001"),
    ("830799.BJ", "830799"),
    ("sh.600519.SH", "600519"),
    (" 600519 ", "600519"),
    ("aapl", "AAPL"),
])
def test_normalize_symbol(raw, expected):
    assert normalize_symbol(raw) == expected


def test_call_normalizes_symbol_everywhere(cli):
    cli.call("kline.query_bars", sym="sh.600519.SH", limit=1)
    ev = last_ev(cli)
    assert ev["symbol"] == "600519"
    assert 'kline.query_bars("600519", 1)' in ev["xs_lines"][0]


def test_friendly_layer_normalizes_symbol(cli):
    cli.kline.bars("cn.600519", n=1)
    ev = last_ev(cli)
    assert ev["symbol"] == "600519"
    assert 'kline.query_bars("600519", 1)' in ev["xs_lines"][0]


# ---------------------------------------------------------------- 批量调用
def test_call_batch_single_http_map(cli):
    cli.session.result = {"600519": [{"close": 1}], "000001": [{"close": 2}]}
    out = cli.call_batch("kline.query_bars", ["sh.600519", "000001", "600519"], limit=5)
    assert isinstance(out, BatchResult) and not out.errors
    assert set(out.results) == {"600519", "000001"}
    evals = [x for x in cli.session.calls if x["url"].endswith("/xs/eval")]
    assert len(evals) == 1, "批量应合并为单次 HTTP"
    xs = evals[0]["json"]["xs_lines"][-1]
    assert '"600519": kline.fmt_maps(kline.query_bars("600519", 5))' in xs
    assert '"000001": kline.fmt_maps(kline.query_bars("000001", 5))' in xs
    assert xs.count("kline.query_bars") == 2  # 去重


def test_call_batch_applies_normalizer(cli):
    cli.session.result = {"600519": [{"close": 1}]}
    cli.call_batch("kline.query_bars", ["600519"])
    xs = last_ev(cli)["xs_lines"][-1]
    assert "kline.fmt_maps(kline.query_bars" in xs


def test_call_batch_skip_mode_isolates_errors(cli):
    calls = {"n": 0}

    class Flaky(FakeSession):
        def post(self, url, json=None, data=None, headers=None, timeout=None):
            if url.endswith("/xs/eval"):
                calls["n"] += 1
                if any('"000001"' in ln for ln in json["xs_lines"]):
                    class R:
                        status_code = 500
                        text = "boom"
                        headers = {}
                        def json(self):
                            return {}
                    return R()
            return super().post(url, json=json, data=data, headers=headers, timeout=timeout)

    c = Client(base_url="https://t", client_id="i", client_secret="s",
               catalog=load(), session=Flaky(), retries=0)
    out = c.call_batch("kline.query_bars", ["600519", "000001"], on_error="skip", limit=1)
    assert "600519" in out.results and "000001" in out.errors
    assert calls["n"] == 2


def test_call_batch_guards(cli):
    with pytest.raises(UsageError, match="没有标的参数"):
        cli.call_batch("notice.query_recent", ["600519"])
    with pytest.raises(UsageError, match="不要在 kwargs 传"):
        cli.call_batch("kline.query_bars", ["600519"], sym="600519")
    with pytest.raises(UsageError, match="on_error"):
        cli.call_batch("kline.query_bars", ["600519"], on_error="bogus")
    with pytest.raises(LimitError, match="超过上限"):
        c = Client(base_url="https://t", client_id="i", client_secret="s",
                   catalog=load(), session=FakeSession(), max_limit=1)
        c.call_batch("kline.query_bars", ["600519", "000001"])
    assert cli.call_batch("kline.query_bars", []) == BatchResult()


# ---------------------------------------------------------------- 错误体系
def test_error_hierarchy_and_exports():
    for cls in (AuthError, UsageError, LimitError, TransportError, ApiError, CatalogError):
        assert issubclass(cls, FinPipeError)
        assert getattr(finpipe, cls.__name__) is cls
    assert issubclass(CatalogError, KeyError)   # 兼容既有 except KeyError
    assert issubclass(LimitError, FinPipeError)


def test_error_codes(cli):
    with pytest.raises(LimitError) as ei:
        cli.call("kline.query_bars", sym="600519", limit=10_000)
    assert ei.value.code == "limit"
    with pytest.raises(UsageError) as ei:
        cli.call("kline.query_bars", sym="600519", bogus=1)
    assert ei.value.code == "params"
    with pytest.raises(CatalogError) as ei:
        cli.call("no.such_fn")
    assert ei.value.code == "function"
    with pytest.raises(CatalogError):
        cli.indicator.get("600519", "$NOT_REAL")


def test_auth_error_for_partial_credentials():
    with pytest.raises(AuthError) as ei:
        Client(client_id="only")
    assert ei.value.code == "config"


def test_catalog_error_on_unknown_domain():
    cat = load()
    with pytest.raises(CatalogError):
        cat.domain("no.such.domain")


# ---------------------------------------------------------------- 目录检索
def test_catalog_search_and_groups():
    cat = load()
    fns = cat.search("query_bars", kind="function")
    assert any(x["name"] == "kline.query_bars" for x in fns)
    metrics = cat.search("市盈率", kind="metric", limit=5)
    assert metrics and all("code" in m for m in metrics)
    assert cat.search("   ") == []
    val = cat.metrics_in_group("valuation")
    assert val and cat.metric(val[0]["code"]) == val[0]
    groups = cat.metric_groups()
    assert {g["id"] for g in groups} >= {"valuation", "dividend", "revenue_mix"}
    assert all(g["count"] > 0 for g in groups)
    with pytest.raises(CatalogError):
        cat.metrics_in_group("no_such_group")


def test_metric_lookup_is_indexed():
    cat = load()
    assert cat._metric_by_code["$PE_TTM_LAST"]["cn"] == "PE(TTM)"
    assert cat.metric("$PE_TTM_LAST") is cat._metric_by_code["$PE_TTM_LAST"]


# ---------------------------------------------------------------- 生命周期与 DataFrame
def test_context_manager_closes_session():
    s = FakeSession()
    with Client(base_url="https://t", client_id="i", client_secret="s",
                catalog=load(), session=s) as c:
        assert c is not None
    assert s.closed is True


def test_df_on_list_interfaces(cli):
    pd = pytest.importorskip("pandas")
    cli.session.result = [{"date": "2026-10-21", "close": 1.0}]
    df = cli.notice.list("600519", _df=True)
    assert isinstance(df, pd.DataFrame) and list(df.columns) == ["date", "close"]
    df2 = cli.statements.income("600519", _df=True)
    assert isinstance(df2, pd.DataFrame)
