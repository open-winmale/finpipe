# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2026-10-23

### Added

- **新数据域「经营分部」（`fund.segments`）**：主营构成多维分解——分产品
  （`cli.segments.products`）、分业务（`business`）、分区域境内外（`region`）、
  主营标签占比（`income`），外加四维合并快照（`snapshot`）、披露覆盖度
  （`coverage`）与可用报告期（`periods`）。数据来自定期报告分部披露的平台清洗
  归一（clean 口径，默认），可选披露明细（`source="raw"`）。
- 行结构统一 `{name, tr, tr_text, cost, margin, ratio}`：收入/成本=元、毛利率/占比/
  同比=小数（margin 服务端算好直出）；量级守护随 1.1.0 单位契约自动生效
  （tr/cost/margin/ratio/pct/yoy 均已声明范围，误口径会抛 `DataError`）。
- 核心接口 44 → 51（新增 segments 7 个）；底层函数 155 → 164（10 个数据域）；
  README「产品线/业务分部口径一期未纳入」欠账兑现。
- 提取器命名空间白名单 += segments（上游 `sys/segments`，18 个公开函数策展收录
  9 个；inventory 全量收录 15 个带合同注记的条目）。

## [Unreleased]

### Added

- README「与 Tushare 对比」章节：优势与劣势两面陈述（免费额度/单位口径/数据守护/
  衍生指标 vs 覆盖面/数据积累/生态/商用许可）。第三方名门禁为此开唯一例外：
  仅 README 允许点名 tushare（`check_leak.py` 的 `THIRDPARTY_ALLOWED_BY_FILE`），
  其余第三方名在全部文件仍然禁止；对比章节由测试守护必须保持两面陈述。

## [1.1.0] - 2026-10-23

### Changed（breaking：返回数值口径）

- **全库统一基础单位，SDK 单点自动换算**：比率/涨跌幅/占比=小数、金额/价格/市值=元
  （报表原币）、股数/成交量=股。上游脚本永远输出原生口径，`call()` 在返回前按随包
  目录的 YAML 声明做唯一一次换算。本次实际换算的字段：
  - `kline.query_bars / query_last / query_bars_adj / query_last_live` 的 `volume`：
    手 → 股（×100，A 股/港美/ETF 同口径）；
  - `rptdom.statement_compare` 的 `diffp`（差额占比）：百分数 → 小数；
  - `forecast.yjyg_*` 的 `np_amp_* / rev_amp_*` 与 `yjkb_*` 的 `np_yoy / rev_yoy / roe`：
    百分数 → 小数（含 `forecast.snapshot` 嵌套行）。
- **指标层金额口径文档修正**：实测全部为**元**（历史文档误标"亿元"；上游 cn 名中的
  "(%)"/"(亿)" 后缀是命名遗留，不代表数值口径），数值本身未变。

### Added

- **数据正确性保障（三层防线）**：① 目录声明式单位契约（函数级 `units`/`ranges`/`checks`
  与指标级 `unit`/`range`，schema 同步扩展，装载期即校验声明合法性）；② 返回前量级守护 +
  关系不变量（`diffp_ratio`、`volume_amount`），违例抛新异常 `DataError`（含字段/实际值/
  期望范围与逃生口指引），换算声明错误会被数据自动暴露；③ `tools/audit_units.py`
  样本宇宙审计（不同板块/行业/规模 + ETF，全部关系型断言）+ CI 每交易日夜间自动执行。
- **逃生口参数**（语义有测试守护）：`_units="native"` 保留脚本输出单位（字段名仍规范化）、
  `_raw=True` 返回 store 原始行、`Client(validate=False)` 保留换算关闭校验。
- 精选指标量级守护：精选组指标声明量级范围（分位 [0,1]、股息率 [0,1]、市值 (0,1e14) 元等），
  `indicator.get/metrics` 返回前校验。
- README 新增「指标体系：算好的增值数据」（速查表 + 可执行示例 + 预期输出注释）与
  「数据正确性保障」章节；README 示例注释值由离线罐头测试守护，不再腐烂。
- docs/API.md 新增「数据目录（离线）」章节（`finpipe.load()` + Catalog 方法表），
  函数附录新增「单位与守护」列，指标组表新增「量级守护」列。

### Fixed

- README 的 `cat.search()` 行内引用补充 `cat = finpipe.load()` 装载步骤；
  示例风格统一为 `finpipe.load()`。
- kline 复权 `query_bars_adj` 不套 `volume_amount` 不变量（复权价与成交额不可比）。
- `rptdom.statement_tree` 派生行口径文档化（pct 行=原生百分数、`fmt="x"` 行=倍数、
  科目行=元）；树视图适合展示核对，跨接口运算用 `compare()`。
- 目录 upstream rev 同步至上游 454585e5（函数/指标计数不变）。

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
