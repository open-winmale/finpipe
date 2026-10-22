# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-22

First stable release. Install from source until the PyPI publication is enabled.

### Fixed

- Source-install instructions are now the documented path until the PyPI
  release; removed the not-yet-published `pip install wm-finpipe` requirement.
- OAuth 401/403 and eval 401/403/429 now always raise `FinPipeError` subclasses
  (`AuthError` / `LimitError`) with actionable AppID registration steps, instead
  of leaking `requests.HTTPError` or misclassifying 429 as `ApiError`.
- Notice query methods now return normalized flat rows (`date/title/url/...`)
  via `notice.fmt_maps`; `dividend.last()` now matches `history()` with flat
  fields instead of raw store rows.
- `last()` documentation/OpenAPI responses now describe a single object (or
  `None`), not the underlying array.
- Indicator ratio units corrected: metric-layer ratios are decimals
  (`0.332 = 33.2%`), not percentages (`15.0 = 15%`). Forecast yoy fields remain
  percentages.
- Dynamic facade now binds positional arguments to catalog parameter names.
- `_raw=True` with date ranges raises a clear `UsageError` for kline/moneyflow;
  notice windows reject unknown tokens instead of silently using 30 days.
- `notice.find()` normalizes `stock_code`; injected HTTP sessions are no longer
  closed by `Client.close()`.
- Swagger page fixed (`window.SwaggerUIBundle`) and now inlines the OpenAPI spec
  so it opens directly from disk.
- Untracked internal planning documents (`.zcode/`) from the public repository;
  `tools/check_leak.py` now fails on any tracked file outside the public whitelist
  (see CONTRIBUTING.md).
- Added PolyForm-required `Required Notice` line to LICENSE.

### Added

- PyPI metadata: classifiers, keywords, author (improves PyPI discoverability).
- Repository hygiene files: `CHANGELOG.md`, `SECURITY.md`, GitHub issue/PR templates.
- CI matrix extended to Python 3.10 / 3.11 / 3.12 / 3.13, plus wheel clean-install
  and Swagger syntax smoke checks.
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
