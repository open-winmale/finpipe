"""Live 冒烟（默认跳过）：OPENWM_LIVE=1 且凭证可用时对 9 个数据域抽样真实调用。

凭证发现顺序同 Client.from_env。运行：
  OPENWM_LIVE=1 OPENWM_BASE_URL=... OPENWM_CLIENT_ID=... OPENWM_CLIENT_SECRET=... pytest tests/test_live.py
"""
import os

import pytest

from openwm.client import Client

pytestmark = pytest.mark.skipif(
    os.environ.get("OPENWM_LIVE") != "1", reason="OPENWM_LIVE!=1")


@pytest.fixture(scope="module")
def cli():
    return Client.from_env()


def test_market_kline(cli):
    bars = cli.kline.bars("600519", n=5)
    assert isinstance(bars, list) and len(bars) == 5
    assert {"date", "close"} <= set(bars[-1])


def test_market_moneyflow(cli):
    row = cli.moneyflow.last("600519")
    assert row is None or isinstance(row, dict)


def test_fund_statements(cli):
    rows = cli.call("rptdom.statement_years", sym="600519",
                    domain="fin.income_statement")
    assert isinstance(rows, list) and rows


def test_fund_indicator(cli):
    pe = cli.indicator.get("600519", "$PE_TTM_LAST")
    assert pe is None or isinstance(pe, (int, float))


def test_disc_notice(cli):
    rows = cli.notice.list("600519", window="1y", limit=5)
    assert isinstance(rows, list)


def test_disc_filings(cli):
    rows = cli.filings.list("600519", kind="annual", limit=3)
    assert isinstance(rows, list)


def test_disc_forecast(cli):
    row = cli.forecast.next_disclosure("600519")
    assert row is None or isinstance(row, dict)


def test_disc_bonus(cli):
    row = cli.dividend.last("600519")
    assert row is None or isinstance(row, dict)


def test_reference_info(cli):
    prof = cli.info.profile("600519")
    assert isinstance(prof, dict) and prof.get("name")
