"""audit_units 离线冒烟：罐头客户端（数值取自真实 probe 样本）驱动审计全流程。

不联网；分别验证全通过（退出码 0）与违例（退出码 1，报告含 FAIL 行）。
"""
import types

import pytest

import wmshare
from tools import audit_units


def audit_client(mv_free=None, bonus_rate=0.0396):
    """构造通过全部检查的罐头客户端；可用参数注入违例。"""
    bar = {"date": "2026-10-20", "close": 1331.88, "volume": 3413500.0,
           "amount": 4525398959.0, "percent": 0.005215}
    metrics = {"$CLOSE_LAST": 1337.0, "$MV_LAST": 1.67e12,
               "$MV_FREE_LAST": mv_free if mv_free is not None else 1.6e12,
               "$AMOUNT_LAST": 4.5e9, "$BONUS_TTM": 6.5e10,
               "$BONUS_RATE_TTM_LAST": bonus_rate, "$ROE_TTM_LAST": 0.332,
               "$TL_RATE_LAST": 0.152, "$TR_TTM_LAST": 1.73e11,
               "$NP_TTM_LAST": 8.4e10}

    class Client:
        def __init__(self):
            self.kline = types.SimpleNamespace(bars=lambda *a, **k: [dict(bar)])
            self.dividend = types.SimpleNamespace(
                yield_ttm=lambda *a, **k: bonus_rate)
            self.indicator = types.SimpleNamespace(metrics=lambda s, codes: dict(metrics))
            self.statements = types.SimpleNamespace(compare=lambda *a, **k: [])
            self.catalog = wmshare.load()

        @classmethod
        def from_env(cls, *a, **k):
            return cls()

        def call(self, name, **kw):
            return [dict(bar)]

    return Client


def test_audit_passes_on_canned_data(monkeypatch, capsys):
    monkeypatch.setattr(audit_units.wmshare, "Client", audit_client())
    rc = audit_units.main(["--universe", "600519,000001", "--etf", "510300",
                           "--compare-syms", "0"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "FAIL" not in out
    assert "kline.volume_amount" in out and "cross.yield_identity" in out
    assert "510300" in out  # ETF 也在审计范围


def test_audit_fails_on_violation(monkeypatch, capsys):
    monkeypatch.setattr(audit_units.wmshare, "Client", audit_client(mv_free=9.9e12))
    rc = audit_units.main(["--universe", "600519", "--etf", "", "--compare-syms", "0"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "FAIL" in out and "indicator.mv_free_le_mv" in out


def test_audit_reports_sdk_data_error(monkeypatch, capsys):
    from wmshare import DataError

    class Boom(audit_client()):
        def call(self, name, **kw):
            raise DataError("kline.query_bars: 字段 volume 超出声明范围 [0, 1e12]"
                            "（量级守护）。如需原始口径：_raw=True 或 _units=\"native\"",
                            code="range")

    monkeypatch.setattr(audit_units.wmshare, "Client", Boom)
    rc = audit_units.main(["--universe", "600519", "--etf", "", "--compare-syms", "0"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "DataError" in out


@pytest.mark.parametrize("empty", ["", " "])
def test_audit_empty_universe_ok(monkeypatch, empty):
    monkeypatch.setattr(audit_units.wmshare, "Client", audit_client())
    assert audit_units.main(["--universe", empty, "--etf", "",
                             "--compare-syms", "0"]) == 0
