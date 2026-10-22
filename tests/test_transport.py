"""传输健壮性：429/5xx 指数退避、网络异常重试、401 单次令牌刷新、超时透传。

全部用可编排的 FakeSession，不联网、不真实等待（Client._sleep 注入）。
"""
import pytest
import requests

from finpipe.catalog import load
from finpipe.client import Client, FinPipeError


class Resp:
    def __init__(self, status_code=200, json_body=None, headers=None):
        self.status_code = status_code
        self._json = json_body or {}
        self.headers = headers or {}
        self.text = "{}"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        return self._json


class SeqSession:
    """按顺序回放 eval 响应：("status", code[, headers]) / ("exc", exception) / ("json", result)。"""

    def __init__(self, eval_responses):
        self.eval_responses = list(eval_responses)
        self.calls = []
        self.token_count = 0

    def post(self, url, json=None, data=None, headers=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "timeout": timeout})
        if url.endswith("/v1/oauth/token"):
            self.token_count += 1
            return Resp(json_body={"data": {"access_token": f"tok-{self.token_count}",
                                            "expires_in": 3600}})
        item = self.eval_responses.pop(0)
        if item[0] == "exc":
            raise item[1]
        if item[0] == "status":
            return Resp(status_code=item[1],
                        headers=item[2] if len(item) > 2 else {})
        return Resp(json_body={"success": True, "data": {"result": item[1]}})


def make(responses, **kw):
    s = SeqSession(responses)
    c = Client(base_url="https://t", client_id="i", client_secret="s",
               catalog=load(), session=s, backoff=0.5, **kw)
    sleeps: list[float] = []
    c._sleep = lambda seconds: sleeps.append(seconds)
    return c, s, sleeps


def eval_calls(s):
    return [x for x in s.calls if x["url"].endswith("/xs/eval")]


def test_retries_429_with_backoff():
    c, s, sleeps = make([("status", 429), ("json", {"ok": 1})])
    out = c.call("kline.query_last", sym="600519")
    assert out == {"ok": 1}
    assert len(eval_calls(s)) == 2
    assert sleeps == [0.5]  # 第一次退避 = backoff * 2^0


def test_retries_5xx_until_exhausted():
    c, s, sleeps = make([("status", 500), ("status", 503), ("status", 502)])
    with pytest.raises(FinPipeError, match="HTTP 502"):
        c.call("kline.query_last", sym="600519")
    assert len(eval_calls(s)) == 3  # retries=2 → 共 3 次
    assert sleeps == [0.5, 1.0]


def test_retry_after_header_honored():
    c, s, sleeps = make([("status", 429, {"Retry-After": "2"}), ("json", 1)])
    c.call("kline.query_last", sym="600519")
    assert sleeps == [2.0]


def test_network_error_retried_then_succeeds():
    c, s, sleeps = make([("exc", requests.ConnectionError("boom")), ("json", 7)])
    assert c.call("kline.query_last", sym="600519") == 7
    assert len(eval_calls(s)) == 2


def test_network_error_exhausted_becomes_finpipe_error():
    c, s, sleeps = make([("exc", requests.Timeout("t")), ("exc", requests.Timeout("t")),
                         ("exc", requests.Timeout("t"))])
    with pytest.raises(FinPipeError, match="网络请求失败（已重试 2 次）"):
        c.call("kline.query_last", sym="600519")


def test_retries_zero_fails_fast():
    c, s, sleeps = make([("status", 500)], retries=0)
    with pytest.raises(FinPipeError, match="HTTP 500"):
        c.call("kline.query_last", sym="600519")
    assert len(eval_calls(s)) == 1 and sleeps == []


def test_401_refreshes_token_once_and_retries():
    c, s, sleeps = make([("status", 401), ("json", {"ok": 2})])
    assert c.call("kline.query_last", sym="600519") == {"ok": 2}
    calls = eval_calls(s)
    assert len(calls) == 2
    assert calls[0]["headers"]["Authorization"] == "Bearer tok-1"
    assert calls[1]["headers"]["Authorization"] == "Bearer tok-2"  # 已刷新
    assert s.token_count == 2


def test_401_twice_surfaces_error():
    c, s, sleeps = make([("status", 401), ("status", 401)])
    with pytest.raises(FinPipeError, match="HTTP 401"):
        c.call("kline.query_last", sym="600519")
    assert s.token_count == 2  # 只刷新一次，不循环


def test_timeout_passed_through():
    c, s, sleeps = make([("json", 1)], timeout=7.5)
    c.call("kline.query_last", sym="600519")
    assert all(x["timeout"] == 7.5 for x in s.calls)


def test_token_endpoint_also_retried():
    class TokenThenEval(SeqSession):
        def post(self, url, json=None, data=None, headers=None, timeout=None):
            if url.endswith("/v1/oauth/token") and self.token_count == 0:
                self.calls.append({"url": url})
                self.token_count += 1
                return Resp(status_code=429, headers={"Retry-After": "1"})
            return super().post(url, json=json, data=data, headers=headers, timeout=timeout)

    s = TokenThenEval([("json", 5)])
    c = Client(base_url="https://t", client_id="i", client_secret="s",
               catalog=load(), session=s, backoff=0.5)
    c._sleep = lambda seconds: None
    assert c.call("kline.query_last", sym="600519") == 5
