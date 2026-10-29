"""分批执行器契约测试（mock 传输，不联网）。

核心目标守护：批量接口的**存在理由是绕开 429 限流**——服务端按请求次数限流
（免费档 500 次/小时、5000 次/日），因此「N 个标的 = ⌈N/batch_size⌉ 次请求」
必须是可执行的断言，而不是文档里的口号。
"""
import pytest

from wmshare.catalog import load
from wmshare.client import BatchResult, Client
from wmshare.errors import LimitError, UsageError


class CountingSession:
    """记录 eval 请求次数的假传输；可按批次注入错误。"""

    def __init__(self, fail_at: int | None = None, fail_code: str = "rate_limited",
                 fail_status: int = 429):
        self.eval_calls = 0
        self.fail_at = fail_at          # 第 N 次 eval 调用抛错（1-based）
        self.fail_code = fail_code
        self.fail_status = fail_status

    def post(self, url, json=None, data=None, headers=None, timeout=None):
        cls = self

        class R:
            status_code = 200
            text = "{}"
            headers: dict = {}

            def raise_for_status(self):
                pass

            def json(self):
                if url.endswith("/v1/oauth/token"):
                    return {"data": {"access_token": "tok", "expires_in": 3600}}
                cls.eval_calls += 1
                if cls.fail_at is not None and cls.eval_calls == cls.fail_at:
                    return {"success": False,
                            "error": {"code": cls.fail_code,
                                      "message": f"injected failure #{cls.eval_calls}"}}
                # 按请求体里的代码回填结果，验证聚合正确性
                body = json or {}
                syms = []
                for ln in body.get("xs_lines") or []:
                    if ln.startswith("return {"):
                        syms = [p.split(":")[0].strip().strip('"')
                                for p in ln[len("return {"):-1].split(", ")]
                return {"success": True,
                        "data": {"result": {s: {"close": 10.0} for s in syms}}}

        return R()


def make_client(session=None, **kw):
    return Client(base_url="https://t", client_id="i", client_secret="s",
                  catalog=load(), session=session or CountingSession(), **kw)


def test_whole_market_needs_12_requests():
    """A 股全市场 5691 家 + 500/批 → 恰好 12 次请求（而非 5691 次）。"""
    s = CountingSession()
    c = make_client(s)
    codes = [f"{i:06d}" for i in range(5691)]
    res = c.batch_all("kline.snapshot", codes)
    assert s.eval_calls == 12, f"应 12 次请求，实际 {s.eval_calls}"
    assert res.requests == 12
    assert len(res.results) == 5691
    assert not res.errors


def test_batch_size_controls_request_count():
    s = CountingSession()
    c = make_client(s)
    codes = [f"{i:06d}" for i in range(1000)]
    c.batch_all("kline.snapshot", codes, batch_size=250)
    assert s.eval_calls == 4


def test_dedupe_before_chunking():
    """重复代码先去重再切片——避免把同一标的重复塞进多批、浪费额度。"""
    s = CountingSession()
    c = make_client(s)
    res = c.batch_all("kline.snapshot", ["600519"] * 600)
    assert res.requests == 1
    assert list(res.results) == ["600519"]


def test_symbol_normalization_before_chunking():
    c = make_client()
    res = c.batch_all("kline.snapshot", ["sh.600519.SH", "000001", "aapl"])
    assert list(res.results) == ["600519", "000001", "AAPL"]


def test_empty_symbols_yields_nothing():
    s = CountingSession()
    c = make_client(s)
    assert list(c.batch_iter("kline.snapshot", [])) == []
    res = c.batch_all("kline.snapshot", [])
    assert res.results == {} and res.requests == 0
    assert s.eval_calls == 0


def test_batch_iter_yields_per_batch():
    c = make_client()
    parts = list(c.batch_iter("kline.snapshot", [f"{i:06d}" for i in range(1200)],
                              batch_size=500))
    assert [len(p.results) for p in parts] == [500, 500, 200]
    assert all(p.requests == 1 for p in parts)


def test_batch_size_validation():
    c = make_client(max_limit=500)
    with pytest.raises(UsageError, match="batch_size=600 超过单批上限 500"):
        c.batch_all("kline.snapshot", ["600519"], batch_size=600)
    with pytest.raises(UsageError, match="batch_size 必须为正整数"):
        c.batch_all("kline.snapshot", ["600519"], batch_size=0)


def test_rate_limit_stops_with_resume_hint():
    """429 是按时间窗口的配额：必须停止并给出续跑位置，而不是继续连败。"""
    s = CountingSession(fail_at=3)
    c = make_client(s)
    codes = [f"{i:06d}" for i in range(3000)]      # 6 批，第 3 批失败
    with pytest.raises(LimitError) as ei:
        c.batch_all("kline.snapshot", codes)
    msg = str(ei.value)
    assert "第 3/6 批" in msg
    assert "已完成 1000 / 3000 个标的" in msg
    assert "codes[1000:]" in msg
    assert "500 次/小时" in msg
    assert s.eval_calls == 3                        # 第 3 批失败后不再发请求


def test_rate_limit_stops_even_in_skip_mode():
    """skip 是批级容错，但 429 例外——配额耗尽时跳过无用，必须停。"""
    s = CountingSession(fail_at=2)
    c = make_client(s)
    with pytest.raises(LimitError, match="触发限流"):
        c.batch_all("kline.snapshot", [f"{i:06d}" for i in range(2000)],
                    on_error="skip")
    assert s.eval_calls == 2


def test_skip_mode_drops_failed_batch_only():
    """非 429 的批失败可跳过，其余批照常返回，失败批记进 errors。"""
    s = CountingSession(fail_at=2, fail_code="XS_EVAL", fail_status=500)
    c = make_client(s)
    codes = [f"{i:06d}" for i in range(1500)]       # 3 批，第 2 批失败
    res = c.batch_all("kline.snapshot", codes, on_error="skip")
    assert len(res.results) == 1000                 # 第 1、3 批
    assert len(res.errors) == 1
    assert "batch#2[500:1000]" in res.errors
    assert res.requests == 3


def test_raise_mode_propagates_batch_failure():
    s = CountingSession(fail_at=2, fail_code="XS_EVAL", fail_status=500)
    c = make_client(s)
    with pytest.raises(Exception, match="injected failure"):
        c.batch_all("kline.snapshot", [f"{i:06d}" for i in range(1500)])


def test_ticket_level_skip_is_much_costlier():
    """防回潮：票级 skip（call_batch）请求数 = N，批级（batch_all）= 批数。

    这条断言就是「不要用 call_batch(on_error='skip') 做容错」的可执行证据。
    票级同样受 max_limit 约束（400 < 500），所以对比用 400 个代码。
    """
    codes = [f"{i:06d}" for i in range(400)]

    s1 = CountingSession()
    c1 = make_client(s1)
    c1.call_batch("kline.snapshot", codes, on_error="skip")
    ticket_level = s1.eval_calls

    s2 = CountingSession()
    c2 = make_client(s2)
    c2.batch_all("kline.snapshot", codes, on_error="skip")
    batch_level = s2.eval_calls

    assert ticket_level == 400, "票级 skip 应逐票发请求"
    assert batch_level == 1, "批级应 1 次请求"
    assert ticket_level >= 100 * batch_level


def test_batch_result_requests_default_zero():
    assert BatchResult().requests == 0


def test_call_batch_over_limit_mentions_batch_all():
    c = make_client(max_limit=500)
    with pytest.raises(LimitError, match="batch_all"):
        c.call_batch("kline.snapshot", [f"{i:06d}" for i in range(501)])
