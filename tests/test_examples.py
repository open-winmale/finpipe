"""示例冒烟：离线示例真实执行；quickstart 用 FakeClient 防止可选依赖/403 回归。"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
EXAMPLES = REPO / "examples"


def _run_example(name: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    return subprocess.run([sys.executable, str(EXAMPLES / name)],
                          capture_output=True, text=True, env=env, timeout=60)


def test_catalog_tour_runs_offline():
    result = _run_example("catalog_tour.py")
    assert result.returncode == 0, result.stderr
    assert "数据域：16" in result.stdout


def test_error_handling_runs_offline_and_shows_appid_guidance():
    result = _run_example("error_handling.py")
    assert result.returncode == 0, result.stderr
    assert "[auth]" in result.stdout and "[limit]" in result.stdout
    assert "open.winmale.com" in result.stdout
    assert "FINPIPE_CLIENT_ID" in result.stdout


def test_quickstart_base_install_path(capsys):
    """quickstart 不依赖 pandas、不调用已知 403 接口，normalized 字段可直接读取。"""
    import importlib.util

    spec = importlib.util.spec_from_file_location("finpipe_quickstart_example",
                                                  EXAMPLES / "quickstart.py")
    assert spec and spec.loader
    quickstart = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(quickstart)

    bars = [{"date": f"2026-10-{d:02d}", "close": 1300.0 + d, "percent": 0.01}
            for d in range(1, 6)]
    notice = [{"date": "2026-10-01", "title": "测试公告"}]

    class Kline:
        def bars(self, *a, **k):
            return bars

        def snapshot(self, *a, **k):
            return {"close": 1309.69, "chg_20d": 0.0123}

    class Moneyflow:
        def last(self, *a, **k):
            return {"net_mf": -100.0}

    class Statements:
        def income(self, *a, **k):
            return [{"k": "x", "cn": "收入", "vals": {}}] * 3

    class Indicator:
        def get(self, symbol, code):
            return 20.0 if code == "$PE_TTM_LAST" else 0.3324

    class Notice:
        def list(self, *a, **k):
            return notice

    class Dividend:
        def last(self, *a, **k):
            return {"ex_div": "2026-06-26", "dps": 28.02, "total": 3.5e10}

    class Info:
        def profile(self, *a, **k):
            return {"name": "贵州茅台", "industry": "白酒", "listing_date": "2001-08-27"}

    cli = SimpleNamespace(kline=Kline(), moneyflow=Moneyflow(), statements=Statements(),
                          indicator=Indicator(), notice=Notice(), dividend=Dividend(),
                          info=Info(), call=lambda *a, **k: [])
    quickstart.main(cli)
    out = capsys.readouterr().out
    assert "ROE(TTM)=33.24%" in out
    assert "DPS 28.02" in out
    assert "测试公告" in out
    assert "DataFrame" not in out
