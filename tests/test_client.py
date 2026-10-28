"""客户端契约测试（mock 传输，不联网）。

FakeSession 复现 OpenAPI 合同：
  POST /v1/oauth/token      → {"data": {"access_token": ..., "expires_in": ...}}
  POST /v1/analysis/xs/eval → {"success": true, "data": {"result": ...}}
"""
import json

import pytest

from wmshare.catalog import load
from wmshare.client import Client, WmshareError, _xs_literal


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
    # XS 空值是 nil，不是 JSON 的 null（否则服务端报 undefined variable "null"）
    assert _xs_literal(None) == "nil"
    assert _xs_literal({"a": None, "b": [1, None]}) == '{"a": nil, "b": [1, nil]}'


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


def test_missing_middle_param_fills_nil(client):
    """中段可选参数未传时必须补 nil 保位：调用字面量按位置绑定，跳洞会把后值错绑到前槽
    （实证：screen_quality(sym, payout_max=1.5) 曾生成 (sym, 1.5)，1.5 错进 payout_min）。"""
    client.call("bonus.screen_quality", sym="600519", min_yield=0.02, payout_max=1.5)
    lines = last_eval(client)["json"]["xs_lines"]
    assert 'return bonus.screen_quality("600519", 0.02, nil, 1.5)' in lines
    # 尾部未传仍按省略处理，不补尾 nil
    client.call("bonus.screen_quality", sym="600519", min_yield=0.02)
    lines = last_eval(client)["json"]["xs_lines"]
    assert 'return bonus.screen_quality("600519", 0.02)' in lines


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
    with pytest.raises(WmshareError, match="未知参数"):
        client.call("kline.query_bars", sym="600519", n=10)
    with pytest.raises(WmshareError, match="必填参数 sym"):
        client.call("moneyflow.query_bars", limit=5)
    with pytest.raises(KeyError, match="未知函数"):
        client.call("kline.no_such_fn", sym="600519")


def test_max_limit_caps_limit_params(client):
    with pytest.raises(WmshareError, match="超过单次请求上限 500"):
        client.call("kline.query_bars", sym="600519", limit=501)
    client.call("kline.query_bars", sym="600519", limit=500)  # 上限值本身放行
    c2 = Client(base_url="https://t", client_id="i", client_secret="s",
                catalog=load(), session=FakeSession(), max_limit=None)
    c2.call("kline.query_bars", sym="600519", limit=5000)  # None 关闭上限


# ---- 凭证解析：SDK 不再内置体验 AppID，缺凭证必须在构造期报错并给指引 ----

def test_client_without_credentials_rejected():
    with pytest.raises(WmshareError, match="缺少凭证") as ei:
        Client(base_url="https://t", catalog=load(), session=FakeSession())
    assert ei.value.code == "config"
    assert "open.winmale.com" in str(ei.value)


def test_missing_credentials_mention_legacy_finpipe(monkeypatch, tmp_path):
    """更名迁移指引：检测到旧 finpipe 配置残留时，缺凭证报错附迁移提示（只指路不映射）。"""
    monkeypatch.setenv("FINPIPE_CLIENT_ID", "old-id")
    monkeypatch.delenv("FINPIPE_CLIENT_SECRET", raising=False)
    with pytest.raises(WmshareError, match="缺少凭证") as ei:
        Client(base_url="https://t", catalog=load(), session=FakeSession())
    assert "FINPIPE_CLIENT_ID" in str(ei.value) and "迁移" in str(ei.value)

    monkeypatch.delenv("FINPIPE_CLIENT_ID", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))      # 无 ~/.finpipe/ 残留
    with pytest.raises(WmshareError, match="缺少凭证") as ei2:
        Client(base_url="https://t", catalog=load(), session=FakeSession())
    assert "迁移" not in str(ei2.value)


def test_dir_exposes_all_namespaces():
    """dir(cli) 必须可见友好门面与底层目录命名空间（IDE 补全可达）。"""
    cli = Client(base_url="https://t", client_id="cid", client_secret="sec",
                 catalog=load(), session=FakeSession())
    names = set(dir(cli))
    assert {"dividend", "kline", "screener", "call", "call_batch"} <= names
    assert {"bonus", "rptdom"} <= names            # 底层目录命名空间


def test_partial_credentials_rejected():
    with pytest.raises(WmshareError, match="成对"):
        Client(base_url="https://t", client_id="only-id",
               catalog=load(), session=FakeSession())
    with pytest.raises(WmshareError, match="成对"):
        Client(base_url="https://t", client_secret="only-sec",
               catalog=load(), session=FakeSession())


def test_from_env_prefers_explicit_env():
    c = Client.from_env(env={"WMSHARE_CLIENT_ID": "id-1", "WMSHARE_CLIENT_SECRET": "sec-1"},
                        base_url="https://t", catalog=load(), session=FakeSession())
    assert (c.client_id, c.client_secret) == ("id-1", "sec-1")


def test_from_env_partial_raises(tmp_path):
    # WMSHARE_CREDENTIALS 指向不存在文件：隔离本机 ~/.wmshare/credentials.env
    with pytest.raises(WmshareError, match="成对"):
        Client.from_env(env={"WMSHARE_CLIENT_ID": "id-1",
                             "WMSHARE_CREDENTIALS": str(tmp_path / "absent.env")},
                        base_url="https://t", catalog=load(), session=FakeSession())


def test_from_env_open_platform_fallback(tmp_path):
    c = Client.from_env(env={"OPEN_PLATFORM_CLIENT_ID": "pid",
                             "OPEN_PLATFORM_CLIENT_SECRET": "psec",
                             "WMSHARE_CREDENTIALS": str(tmp_path / "absent.env")},
                        base_url="https://t", catalog=load(), session=FakeSession())
    assert c.client_id == "pid"


def test_from_env_empty_raises_with_guidance(tmp_path):
    # 隔离本机凭证文件（维护者/用户可能已配置 ~/.wmshare/credentials.env），
    # 确保测的是「无任何配置 → 构造期报错并附申请指引」这条路径
    with pytest.raises(WmshareError, match="缺少凭证"):
        Client.from_env(env={"WMSHARE_CREDENTIALS": str(tmp_path / "absent.env")},
                        base_url="https://t", catalog=load(), session=FakeSession())


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
    with pytest.raises(WmshareError, match="未知参数"):
        client.call("kline.fmt_snapshot_line", code="600519")


def test_inventory_min_args_optional(client):
    # kline.query_bars_adj(sym, limit, adj) xs:catalog min_args=2 → adj 可选
    client.call("kline.query_bars_adj", sym="600519", limit=10)
    assert last_eval(client)["json"]["xs_lines"] == [
        '__r := kline.query_bars_adj("600519", 10)',
        "return kline.fmt_maps(__r)"]  # 复权序列走规范化，字段与不复权一致
    with pytest.raises(WmshareError, match="必填参数 limit"):
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
    with pytest.raises(WmshareError, match="undefined: foo"):
        c2.call("kline.query_bars", sym="600519")
