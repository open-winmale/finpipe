"""首屏图与 README 同源的守护：图里的源码由生成器从 README 就地抽取。"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("PIL")  # 生成依赖不在 CI 的 dev extras 里；缺 Pillow 时跳过

REPO = Path(__file__).resolve().parents[1]


def _generator():
    spec = importlib.util.spec_from_file_location(
        "gen_quickstart_png", REPO / "tools" / "gen_quickstart_png.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_source_is_extracted_from_readme():
    """图里代码 = README「选股实战」块，避免两处各写一份。"""
    src = _generator().read_source()
    assert len(src) >= 10
    assert any('batch_all("bonus.snapshot_yield_ttm"' in line for line in src)
    assert any("rows[:8]" in line for line in src)


def test_result_table_shape_and_provenance():
    mod = _generator()
    assert len(mod.ROWS) == 8
    assert all(len(row) == 5 for row in mod.ROWS)
    assert "5,691" in mod.SUMMARY and "12 次请求" in mod.SUMMARY
    assert "2026-10-30" in mod.FOOT and "真实数据" in mod.FOOT
