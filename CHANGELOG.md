# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **AI 原生 skill（随 wheel 分发）**：Agent Skills 格式的 `SKILL.md`
  （`finpipe.skill_dir()` 定位，`skills/finpipe/*.md` 进 package-data），教 AI
  agent 正确使用 SDK——环境前置与 AppID 申请引导、单位铁律（小数/元/股 +
  混口径标注）、目录先行防臆造指标码、意图→接口决策树、工作流与返回解读、
  坑位清单、错误处理速查。装入方式：复制到 agent 的 skill 发现目录
  （`~/.agents/skills/` 等）。新增 `tests/test_skill.py`：frontmatter 合法性、
  **文中全部调用防臆造守护**（命名空间/方法/目录函数逐一校验 + 签名可绑定）、
  wheel 分发声明、关键措辞守护。
- **数据接口「选股与全景」**：新 `cli.screener` 门面，核心接口 52 → 64。
  单票一行布尔筛选：`screen_limit_up` / `screen_limit_down`（涨停/跌停，阈值
  ±0.10 小数）、`screen_above_ma20` / `screen_ma60_up` / `screen_breakout_ma20`
  （均线/趋势）、`screen_momentum_20d(min_chg=0.10)` / `screen_pullback_20d(min_chg=-0.10)`
  （动量/回撤，小数阈值；pullback 语义为涨幅**上限**）、
  `screen_volume_spike(min_ratio=1.5)`（5 日量比）；全市场宽度（服务端预计算
  索引直出，`idx` 不传 = 服务端解析 A 股最新查询索引）：`index_breadth_summary`
  （涨跌家数/占比/中位数）、`index_breadth_bins`（9 档分桶）、
  `index_breadth_bin_industries`（分桶×行业）、`index_top_movers`（涨跌榜，
  行含 symbol/name/percent）。kline 目录其余筛选函数经 `cli.screener.*` 属性直达。
- README 新增「选股与全景」独立小节（筛选阈值表 + 宽度返回口径表 + 可执行示例）；
  API.md 核心接口表改为按命名空间分节（生成器自动成节）；口径速查新增「筛选阈值」
  行（宽度返回的 `*_pct`/`pct_of_total` 为百分数数值、涨跌幅/中位数为小数）。
- 示例 `examples/screener.py`；`.internal/ROADMAP-1.3.md` 规划二期任意条件选股
  （上游 `kline.index_query`）与三期策略库候选。

### Fixed

- **选股门面对齐审查修复**：三个列表返回的宽度接口（`index_breadth_bins` /
  `index_breadth_bin_industries` / `index_top_movers`）补 `_df=True` 支持
  （对齐模块「返回列表的方法支持 _df」承诺）；`index_top_movers` 的 `limit` 在
  eval 拼脚本路径补 `Client(max_limit=...)` / 10000 行硬上限钳制（此前只走目录
  路径才受钳制）；门面模块 docstring 底层函数计数 155 → 164 并加测试守护；
  README 与示例中 `index_where_*` 的表述修正为「服务端筛选条件表达式」
  （原文案误写为可直接使用的股票池）。
- 宽度接口索引键：臆造字面量 `"index.cn.all"` 实测 500（索引键为动态 cache_key，
  无稳定字面量）；`cli.screener` 宽度四件套改为 `idx=None` 时由服务端
  `LatestIndexKey()` 解析。README/速查表中旧键示例已移除。
- 上游配套（7615b7ea，待部署）：`kline.index_top_movers` 原返回行仅含行号与
  `$` 原始字段、无标的代码——改 `INDEX_ROW_VALUES_MANY_SPEC` 投影并拍平为
  `{symbol, name, percent}`；SDK live 测试对部署前的旧形态 xfail。

### Docs

- README「与 Tushare 对比」章节：优势与劣势两面陈述（免费额度/单位口径/数据守护/
  衍生指标 vs 覆盖面/数据积累/生态/商用许可）。第三方名门禁为此开唯一例外：
  仅 README 允许点名 tushare（`check_leak.py` 的 `THIRDPARTY_ALLOWED_BY_FILE`），
  其余第三方名在全部文件仍然禁止；对比章节由测试守护必须保持两面陈述。
  「衍生计算」行升级为 `cli.screener` 选股门面口径；实时行情行明确免费提供
  盘中快照与当日 1 分钟分时（Tushare 实时分钟为 1000 元/月的独立权限）。

## [1.3.1] - 2026-10-24

### Changed

- `cli.valuation.hist_stats` 窗口白名单新增 **"6m"**（引擎支持 `<数字><单位>` 通用
  窗口，实测 6m 可用）：`("6m", "1y", "2y", "3y")`，上限仍为 3 年。

## [1.3.0] - 2026-10-24

### Added

- **数据接口「估值历史统计」**：`cli.valuation.hist_stats(symbol, metric="pe", window="3y")`
  ——与平台 web「估值通道」取数同源（宿主 HIST_STATS），返回窗口内每日 PE/PB/PS/市赚率
  序列与统计量（avg/current/median/min/max/pct）。窗口白名单 1y/2y/3y（上限 3 年）；
  亏损期 PE 无数据、净资产为负期间不参与。下游工具（big-winner 必赢佬）以此为数据源。
- 核心接口 51 → 52。

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
