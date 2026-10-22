"""友好 API 层测试：注册表同步、命名统一、调用翻译（mock 传输，不联网）。"""
import inspect

import pytest

from finpipe.api import FRIENDLY_INDEX, FRIENDLY_NAMESPACES
from finpipe.catalog import load
from finpipe.client import Client, FinPipeError


class FakeSession:
    def __init__(self):
        self.calls = []
        self.token_count = 0
        self.eval_result = {"ok": True}

    def post(self, url, json=None, data=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json})
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
def cli():
    return Client(base_url="https://t.example", client_id="i", client_secret="s",
                  catalog=load(), session=FakeSession())


def last_xs(c: Client) -> list[str]:
    return [x for x in c.session.calls if x["url"].endswith("/xs/eval")][-1]["json"]["xs_lines"]


def test_registry_in_sync_with_classes():
    # 注册表每条都能解析到真实方法
    for _, ns, method, cn, _u in FRIENDLY_INDEX:
        assert ns in FRIENDLY_NAMESPACES, ns
        assert hasattr(FRIENDLY_NAMESPACES[ns], method), f"{ns}.{method}"
        assert cn
    # 每个公开方法都在注册表中（防漏文档）
    indexed = {(ns, m) for _, ns, m, _, _ in FRIENDLY_INDEX}
    for ns, cls in FRIENDLY_NAMESPACES.items():
        for name, member in inspect.getmembers(cls):
            if name.startswith("_") or not inspect.isfunction(member):
                continue
            assert (ns, name) in indexed, f"方法 {ns}.{name} 未登记 FRIENDLY_INDEX"


def test_symbol_param_uniform():
    """命名统一性：凡按标的查询的方法，首参必须是 symbol（全市场类方法可无 symbol）。"""
    for ns, cls in FRIENDLY_NAMESPACES.items():
        for name, member in inspect.getmembers(cls, inspect.isfunction):
            if name.startswith("_"):
                continue
            params = list(inspect.signature(member).parameters)
            if "symbol" in params:
                assert params[1] == "symbol", \
                    f"{ns}.{name} 含 symbol 但非首参：{params}"


def test_kline_bars_dispatch(cli):
    cli.kline.bars("600519", n=5)
    assert last_xs(cli) == ['__r := kline.query_bars("600519", 5)',
                            'return kline.fmt_maps(__r)']
    cli.kline.bars("600519", n=5, adj="qfq", _raw=True)
    assert last_xs(cli) == ['return kline.query_bars_adj("600519", 5, "qfq")']
    # 复权序列也走规范化（输出字段与不复权一致）
    cli.kline.bars("600519", n=5, adj="qfq")
    assert last_xs(cli) == ['__r := kline.query_bars_adj("600519", 5, "qfq")',
                            'return kline.fmt_maps(__r)']


def test_last_returns_normalized_latest_row(cli):
    cli.session.eval_result = [{"date": "2026-10-21", "close": 1309.69}]
    assert cli.kline.last("600519") == {"date": "2026-10-21", "close": 1309.69}
    assert last_xs(cli)[-1] == 'return kline.fmt_maps(__r)'
    cli.session.eval_result = [{"date": "2026-10-21", "net_mf": -161756700}]
    assert cli.moneyflow.last("600519") == {"date": "2026-10-21", "net_mf": -161756700}
    cli.session.eval_result = []
    assert cli.kline.last("600519") is None


def test_statements_translation(cli):
    cli.statements.income("600519", years=3)
    xs = last_xs(cli)
    assert xs[0] == 'xs.require("sys/rptdom/init.xs")'
    assert xs[-1] == ('return rptdom.statement("600519", "fin.income_statement", '
                      '{"scope": "合并", "n": 3})')


def test_notice_and_dividend(cli):
    cli.notice.list("600519", window="3m", keyword="回购", limit=5)
    assert last_xs(cli) == ['return notice.query_by_symbol("600519", "3m", "回购", 5)']
    cli.notice.find("600519", "2026-01-01", "2026-03-31", keyword="回购", limit=10)
    assert last_xs(cli) == ['return notice.query_find("2026-01-01", "2026-03-31", "回购", "600519", 10)']
    cli.dividend.yield_ttm("600519")
    assert last_xs(cli) == ['return bonus.snapshot_yield_ttm("600519")']


def test_indicator_anti_fabrication(cli):
    with pytest.raises(KeyError, match="未知指标"):
        cli.indicator.get("600519", "$NOT_EXIST")
    cli.indicator.get("600519", "$PE_TTM_LAST")
    assert last_xs(cli) == ["return $PE_TTM_LAST"]
    cli.indicator.metrics("600519", ["$PE_TTM_LAST", "$ROE_TTM_LAST"])
    assert last_xs(cli) == ["return {\"$PE_TTM_LAST\": $PE_TTM_LAST, \"$ROE_TTM_LAST\": $ROE_TTM_LAST}"]


def test_info_profile(cli):
    cli.info.profile("600519")
    assert last_xs(cli) == ['return {"name": $NAME, "industry": $INDUSTRY_CUR, '
                            '"style_industry": $STYLE_INDUSTRY, "org_type": $ORG_ORGTYPE, '
                            '"listing_date": $ORG_LISTINGDATE}']


def test_unknown_param_still_guards(cli):
    # 友好层为强类型签名：越权参数在 Python 层即被拒
    with pytest.raises(TypeError):
        cli.kline.bars("600519", bogus=1)
    # 通用 call() 层同守
    from finpipe.client import FinPipeError
    with pytest.raises(FinPipeError, match="未知参数"):
        cli.call("kline.query_bars", sym="600519", bogus=1)


def test_getattr_delegates_catalog_functions(cli):
    """__getattr__ 兜底：友好类未显式包装的目录函数经属性直达，零遮蔽。"""
    # kline 命名空间的筛选器（未显式包装）可直达
    cli.kline.screen_above_ma20(sym="600519")
    assert last_xs(cli) == ['return kline.screen_above_ma20("600519")']
    # dividend 命名空间映射到目录 bonus 命名空间，窗口函数同理
    cli.dividend.query_dps_window(sym="600519", window="3y")
    assert last_xs(cli) == ['return bonus.query_dps_window("600519", "3y")']
    # 委托函数带可读名（便于调试与 repr）
    fn = cli.kline.screen_above_ma20
    assert fn.__name__ == "screen_above_ma20"
    assert fn.__qualname__ == "KlineApi.screen_above_ma20"


def test_getattr_rejects_non_catalog_names(cli):
    """目录之外的名字显式 AttributeError，且提示可发现性入口。"""
    with pytest.raises(AttributeError, match="cat.search"):
        cli.kline.no_such_fn
    # 双下划线永不委托（不干扰 pickle/copy 等协议探测）
    with pytest.raises(AttributeError):
        cli.kline.__deepcopy__


def test_dividend_screeners_promoted(cli):
    """杀手锏筛选器提为显式方法，可经 cli.dividend.screen_* 调用。"""
    cli.dividend.screen_quality("600519", min_yield=0.03, payout_max=1.0)
    assert last_xs(cli) == ['return bonus.screen_quality("600519", 0.03, 1.0)']
    cli.dividend.screen_high_yield("600519")
    assert last_xs(cli) == ['return bonus.screen_high_yield("600519")']
    cli.dividend.screen_undervalued_yield("600519", min_yield=0.04)
    assert last_xs(cli) == ['return bonus.screen_undervalued_yield("600519", 0.04)']
