# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- Untracked internal planning documents (`.zcode/`) from the public repository;
  `tools/check_leak.py` now fails on any tracked file outside the public whitelist
  (see CONTRIBUTING.md).
- Added PolyForm-required `Required Notice` line to LICENSE.

### Added

- PyPI metadata: classifiers, keywords, author (improves PyPI discoverability).
- Repository hygiene files: `CHANGELOG.md`, `SECURITY.md`, GitHub issue/PR templates.
- CI matrix extended to Python 3.10 / 3.11 / 3.12 / 3.13.
- Friendly facade: unknown methods on namespace classes now delegate to the
  underlying `call()` — all 155 catalog functions are reachable via the typed
  facade (e.g. `cli.kline.screen_above_ma20(...)`), no more AttributeError.
- Dividend screeners promoted to the facade: `cli.dividend.screen_quality(...)` etc.
- New examples: `catalog_tour.py`, `dividend_screener.py`, `pandas_analysis.py`,
  `error_handling.py`.

## [0.1.0] - 2026-09

### Added

- Initial public release: 9 data domains (k-line, money flow, statements,
  indicators, notices, periodic reports, earnings events, dividends, reference),
  41 typed facade methods, 155 catalog functions, 2,197 metric codes,
  offline machine-readable catalog, zero-config trial appid,
  batch calls (`call_batch`), optional pandas support (`_df=True`).
