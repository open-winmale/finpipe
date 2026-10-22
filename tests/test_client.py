"""客户端契约测试（mock 传输，不联网）。

FakeSession 复现 OpenAPI 合同：
  POST /v1/oauth/token      → {"data": {"access_token": ..., "expires_in": ...}}
  POST /v1/analysis/xs/eval → {"success": true, "data": {"result": ...}}
"""
import json

import pytest

from finpipe.catalog import load
from finpipe.client import Client, FinPipeError, _xs_literal


class FakeSession:
    def __init__(self):
        self.calls = []          # (url, json_body_or_none, form_or_none, headers)
        self.token_count = 0
        self.eval_result = {"ok": True}

    def post(self, url, json=None, data=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "data": data, "headers": headers})
        class R:
            status_code = 200
            text = "{}"
            def raise_for_status(self):
                pass
            def json(self):
                if url.endswith("/v1/oauth/token"):
                    self._cls.token_count += 1
                    return {"data": {"access_token": "tok-1", "expires_in": 3600}}
                return {"success": True, "data": {"result": self._cls.eval_result}}
        R._cls = self
        return R()


@pytest.fixture()
def client():
    s = FakeSession()
    return Client(base_url="https://test-api.winmale.com",
                  client_id="id", client_secret="sec",
                  catalog=load(), session=s, market="cn")


def last_eval(c: Client):
    return [x for x in c.session.calls if x["url"].endswith("/v1/analysis/xs/eval")][-1]


def test_xs_literal():
    assert _xs_literal("600519") == '"600519"'
    assert _xs_literal(30) == "30"
    assert _xs_literal(True) == "true"
    assert _xs_literal(["close"]) == '["close"]'
    assert _xs_literal({"scope": "合并"}) == '{"scope": "合并"}'


def test_call_builds_xs_and_body(client):
    out = client.call("kline.query_bars", sym="600519", limit=30)
    assert out == {"ok": True}
    ev = last_eval(client)
    assert ev["json"]["xs_lines"] == [
        '__r := kline.query_bars("600519", 30)',
        "return kline.fmt_maps(__r)",
    ]
    assert ev["json"]["mode"] == "call"
    assert ev["json"]["symbol"] == "600519"
    assert ev["json"]["market"] == "cn"
    assert ev["json"]["args"]["print.plain"] is True
    assert ev["json"]["script_files"] == {}
    assert ev["headers"]["Authorization"] == "Bearer tok-1"


def test_raw_bypasses_normalizer(client):
    client.call("kline.query_bars", sym="600519", _raw=True)
    assert last_eval(client)["json"]["xs_lines"] == ['return kline.query_bars("600519", 120)']


def test_default_fills_positional(client):
    client.call("kline.query_bars", sym="000807")
    assert last_eval(client)["json"]["xs_lines"] == [
        '__r := kline.query_bars("000807", 120)',
        "return kline.fmt_maps(__r)",
    ]


def test_auto_require_for_unpreloaded_ns(client):
    client.call("rptdom.statement_years", sym="600519", domain="fin.income_statement")
    lines = last_eval(client)["json"]["xs_lines"]
    assert lines[0] == 'xs.require("sys/rptdom/init.xs")'
    assert lines[-1] == ('return rptdom.statement_years("600519", "fin.income_statement")')
    # 预载域不补 require
    client.call("kline.query_last", sym="600519")
    lines = last_eval(client)["json"]["xs_lines"]
    assert not any(l.startswith("xs.require") for l in lines)


def test_param_validation(client):
    with pytest.raises(FinPipeError, match="未知参数"):
        client.call("kline.query_bars", sym="600519", n=10)
    with pytest.raises(FinPipeError, match="必填参数 sym"):
        client.call("moneyflow.query_bars", limit=5)
    with pytest.raises(KeyError, match="未知函数"):
        client.call("kline.no_such_fn", sym="600519")


def test_max_limit_caps_limit_params(client):
    with pytest.raises(FinPipeError, match="超过单次请求上限 500"):
        client.call("kline.query_bars", sym="600519", limit=501)
    client.call("kline.query_bars", sym="600519", limit=500)  # 上限值本身放行
    c2 = Client(base_url="https://t", client_id="i", client_secret="s",
                catalog=load(), session=FakeSession(), max_limit=None)
    c2.call("kline.query_bars", sym="600519", limit=5000)  # None 关闭上限


# ---- 凭证解析：内置体验 appid（混淆存放于 _experience.py，测试不写明文） ----

def test_client_defaults_to_experience_credentials():
    from finpipe._experience import credentials
    c = Client(base_url="https://t", catalog=load(), session=FakeSession())
    assert (c.client_id, c.client_secret) == credentials()


def test_partial_credentials_rejected():
    with pytest.raises(FinPipeError, match="成对"):
        Client(base_url="https://t", client_id="only-id",
               catalog=load(), session=FakeSession())
    with pytest.raises(FinPipeError, match="成对"):
        Client(base_url="https://t", client_secret="only-sec",
               catalog=load(), session=FakeSession())


def test_from_env_prefers_explicit_env():
    c = Client.from_env(env={"FINPIPE_CLIENT_ID": "id-1", "FINPIPE_CLIENT_SECRET": "sec-1"},
                        base_url="https://t", catalog=load(), session=FakeSession())
    assert (c.client_id, c.client_secret) == ("id-1", "sec-1")


def test_from_env_partial_raises():
    with pytest.raises(FinPipeError, match="成对"):
        Client.from_env(env={"FINPIPE_CLIENT_ID": "id-1"},
                        base_url="https://t", catalog=load(), session=FakeSession())


def test_from_env_open_platform_fallback():
    c = Client.from_env(env={"OPEN_PLATFORM_CLIENT_ID": "pid",
                             "OPEN_PLATFORM_CLIENT_SECRET": "psec"},
                        base_url="https://t", catalog=load(), session=FakeSession())
    assert c.client_id == "pid"


def test_from_env_empty_uses_experience():
    c = Client.from_env(env={}, base_url="https://t", catalog=load(), session=FakeSession())
    assert c.client_id.startswith("wm_open_")


def test_object_param_serialized(client):
    client.call("rptdom.statement", sym="600519", domain="fin.income_statement",
                opts={"scope": "合并", "n": 5})
    xs = last_eval(client)["json"]["xs_lines"][-1]
    assert xs == ('return rptdom.statement("600519", "fin.income_statement", '
                  '{"scope": "合并", "n": 5})')


def test_namespace_facade(client):
    # 通用门面（非友好命名空间）：rptdom 仍走底层函数直调
    out = client.rptdom.statement_years(sym="600519", domain="fin.income_statement")
    assert out == {"ok": True}
    xs = last_eval(client)["json"]["xs_lines"]
    assert xs[0] == 'xs.require("sys/rptdom/init.xs")'
    assert xs[-1] == 'return rptdom.statement_years("600519", "fin.income_statement")'
    with pytest.raises(AttributeError, match="不在目录中"):
        client.no_such_ns.query(sym="1")
    # L1 精简条目：回退 inventory 签名参数，可直接调用
    client.call("kline.fmt_snapshot_line", sym="600519")
    assert last_eval(client)["json"]["xs_lines"] == ['return kline.fmt_snapshot_line("600519")']
    with pytest.raises(FinPipeError, match="未知参数"):
        client.call("kline.fmt_snapshot_line", code="600519")


def test_inventory_min_args_optional(client):
    # kline.query_bars_adj(sym, limit, adj) xs:catalog min_args=2 → adj 可选
    client.call("kline.query_bars_adj", sym="600519", limit=10)
    assert last_eval(client)["json"]["xs_lines"] == [
        '__r := kline.query_bars_adj("600519", 10)',
        "return kline.fmt_maps(__r)"]  # 复权序列走规范化，字段与不复权一致
    with pytest.raises(FinPipeError, match="必填参数 limit"):
        client.call("kline.query_bars_adj", sym="600519")


def test_dataframe_option(client):
    pytest.importorskip("pandas")
    client.session.eval_result = [{"date": "2026-10-21", "close": 1309.69}]
    df = client.call("kline.query_bars", sym="600519", limit=1, _df=True)
    assert list(df.columns) == ["date", "close"] and len(df) == 1


def test_token_cached(client):
    client.call("kline.query_last", sym="600519")
    client.call("kline.query_last", sym="000807")
    assert client.session.token_count == 1


def test_eval_error_surfaced(client):
    class FailSession(FakeSession):
        def post(self, url, **kw):
            if url.endswith("/xs/eval"):
                class R:
                    status_code = 200
                    text = "{}"
                    def json(self):
                        return {"success": False,
                                "error": {"code": "XS_EVAL", "message": "undefined: foo"}}
                return R()
            return super().post(url, **kw)
    c2 = Client(base_url="https://t", client_id="i", client_secret="s",
                catalog=load(), session=FailSession())
    with pytest.raises(FinPipeError, match="undefined: foo"):
        c2.call("kline.query_bars", sym="600519")
