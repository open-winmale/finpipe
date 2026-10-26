---
name: finpipe
description: 用 wm-finpipe Python SDK 取 A 股数据：K 线（三种复权）、盘中快照、1 分钟分时、资金流、三大报表、2197 个指标码、选股筛选与全市场涨跌全景、分红、公告、公司档案。零配置 Client() 即可取数；随包离线目录可编程查询，指标码/函数名先查目录、禁止臆造。用户要 A 股行情/财务/指标/选股/分红/公告数据时用本 skill，即使用户没点名 finpipe。
when_to_use: 用户需要 A 股个股或全市场数据（价格、财务、指标、筛选、分红、公告）来回答问题、做分析或写代码时。
---

# finpipe：A 股个股数据 SDK

wm-finpipe 是 A 股个股数据 Python SDK（**MIT 开源**，云端数据服务需账号与配额）。本 skill 教你怎么把它
用对：先装好、先查目录、按单位铁律读数、按决策树选接口。

**它不是**：回测框架（没有撮合/仓位管理）；数据库（数据经云端 API 运行时获取，
不随包分发）；全品类数据超市（一期 10 个数据域，覆盖 A 股个股常用研究数据，
基金净值/期货/期权/债券未覆盖）。

## 1. 环境前置

```bash
python3 -c "import finpipe; print(finpipe.__version__)"   # 探测
# 缺失则安装（本机 pip 若走镜像可能同步滞后，加 -i 指官方源）：
pip install wm-finpipe -i https://pypi.org/simple
```

凭证：`finpipe.Client()` **零配置**即可取数（内置体验 AppID，共享池、额度有限）。
遇到 401/403/429 再申请自己的 AppID（额度更充足）：

1. 打开 open.winmale.com，扫码微信登录注册；
2. 右上角「我的」→「开放平台」→ 左侧「我的应用」→「查看应用信息」，
   取 `client_id` 与 api-key（即 `client_secret`）；
3. 配置其一：`export FINPIPE_CLIENT_ID=... FINPIPE_CLIENT_SECRET=...`，
   或凭证文件 `~/.finpipe/credentials.env`（KEY=VALUE 每行一条）。

## 2. 单位铁律（读数前必读）

返回值统一**基础单位**，不要自己再换算：

| 维度 | 单位 | 示例 |
|---|---|---|
| 比率 / 涨跌幅 / 分位 | 小数 | 0.0396 = 3.96%；0.01 = 1%；0.42 = 42% 分位 |
| 金额 / 价格 / 市值 | 元（报表原币） | — |
| 股数 / 成交量 | 股 | — |

例外要在读数时留意：`cli.screener` 宽度接口（全景/分桶）的 `up_pct`/`down_pct`/
`pct_of_total` 是**百分数数值**（80.3 = 80.3%），同返回里的 `median_pct` 与
涨跌幅仍是小数——字段级口径以各方法 docstring 为准。

每次返回前 SDK 做量级守护与关系不变量校验，违例抛 `DataError`（含字段/实际值/
期望范围）——**这是数据在报警，不要 try/except 吞掉**。逃生口：`_raw=True`
（store 原始行）、`_units="native"`（脚本输出单位）、`Client(validate=False)`
（关校验留换算）。

## 3. 目录先行（防臆造，AI 最重要的纪律）

**指标码、函数名、参数必须先查离线目录，禁止编造 `$XXX` 码或猜函数名**。
目录随包分发、纯本地读文件、零网络：

```python
import finpipe

cat = finpipe.load()                                    # 数据目录对象
hits = cat.search("股息")                                # 函数 + 指标码混合检索（中文口语可查）
cat.function("bonus.snapshot_yield_ttm")["params"]       # 任意函数的参数/返回/示例合同
cat.metric("$PE_TTM_LAST")                               # 指标条目（精选码带单位与守护声明）
cat.metrics_in_group("dividend")                         # 指标组内全部精选指标
```

检索返回的函数一律可用两种方式调用：`cli.call("<域>.<函数名>", ...)`（按目录参数名
传参）或友好层方法（见下节决策树）。

## 4. 意图 → 接口决策树

| 用户意图 | 一行调用 |
|---|---|
| 某股最近 N 根日 K | `cli.kline.bars("600519", n=30)`（`adj="qfq"/"hfq"` 复权） |
| 某股日期区间 K 线 | `cli.kline.bars("600519", begin="2026-01-01", end="2026-06-30")` |
| 最新价 / 盘中快照 | `cli.kline.last("600519")` / `cli.kline.live("600519")` |
| 当日 1 分钟分时 | `cli.kline.min1("600519")` |
| 今日涨停了吗 / 全市场涨停梯队 | `cli.screener.screen_limit_up("600519")` |
| 全市场今天涨跌如何 | `cli.screener.index_breadth_summary()` |
| 涨幅榜 / 跌幅榜 | `cli.screener.index_top_movers(limit=20)`（`desc=False` 跌幅） |
| 站上 20 日线了吗 / 放量了吗 | `cli.screener.screen_above_ma20(sym)` / `screen_volume_spike(sym)` |
| 资金流 | `cli.moneyflow.last(sym)` / `cli.moneyflow.bars(sym, n=20)` |
| 利润表 / 资产负债表 / 现金流 | `cli.statements.income(sym, years=5)` / `balance` / `cashflow` |
| 合并 vs 母公司 | `cli.statements.compare(sym)` |
| 估值指标当前值 | `cli.indicator.get(sym, "$PE_TTM_LAST")`（码先查目录） |
| 估值历史分位 | `cli.valuation.hist_stats(sym, metric="pe", window="3y")` |
| TTM 股息率 / 分红历史 | `cli.dividend.yield_ttm(sym)` / `cli.dividend.history(sym)` |
| 分红质量筛选 | `cli.dividend.screen_quality(sym)` |
| 公告 / 有无回购 | `cli.notice.list(sym, window="3m")` / `cli.notice.has_buyback(sym, "6m")` |
| 业绩预告 | `cli.forecast.yjyg_latest(sym)` |
| 公司档案 | `cli.info.profile(sym)` |
| 批量（单次 HTTP） | `cli.call_batch("bonus.snapshot_yield_ttm", syms, on_error="skip")` |

完整 64 个核心接口与全部底层函数：仓库用户看 docs/API.md；pip 用户用
`cat.search(...)` / `cat.function(...)` 查（同一份合同）。

## 5. 工作流示例（返回长这样，从这些字段读）

```python
import finpipe

cli = finpipe.Client.from_env()

# 日 K：按日期降序；percent 为小数（0.005215 = 0.52%）、volume 为股
bars = cli.kline.bars("600519", n=5)
print(bars[0])
# {'date': '2026-10-20', 'close': 1331.88, 'volume': 3413500.0,
#  'amount': 4525398959.0, 'percent': 0.005215, 'open': ..., 'high': ..., 'low': ...}

# 全市场涨跌全景：服务端预计算索引直出；*_pct 是百分数数值、median_pct 是小数
s = cli.screener.index_breadth_summary()
print(s)
# {'total': 5685, 'up': 4567, 'down': 934, 'flat': 184,
#  'up_pct': 80.3, 'down_pct': 16.4, 'flat_pct': 3.2, 'median_pct': 0.015363}

# TTM 股息率：小数，0.0396 = 3.96%
print(cli.dividend.yield_ttm("600519"))        # 0.0396

# 估值温度计：PE(TTM) 近 10 年分位，0.42 = 42% 分位
print(cli.indicator.get("600519", "$PCT_PE_TTM_10Y_LAST"))   # 0.42

# 窗口分红统计：dps 元/股、total 元、count 次（按除权日计）
print(cli.dividend.window_stats("600519", "3y"))   # {'dps': ..., 'total': ..., 'count': 6}
```

## 6. 坑位清单

- **率与涨跌幅都是小数**（0.04 = 4%）；业绩预告的同比才是百分数口径换算后的小数。
  唯一例外是 `cli.screener` 宽度接口的 `*_pct`/`pct_of_total`（百分数数值）。
- **window 白名单**：`"7d"/"1m"/"3m"/"6m"/"1y"/"3y"/"5y"` 或天数整数；未知 token
  显式报错（不会静默按 30 天处理）。
- **日期区间上限 5 年**（`begin/end` 含端点）；数据覆盖不足抛 `LimitError`，
  不会静默截断。
- **单次拉取上限**：`Client(max_limit=500)` 可调；超限显式报错。
- **盘中语义**：休市时 `live`/`min1` 返回最近收盘快照 / 上一交易日；事件筛选
  （涨停等）以「当日有成交」为前置，停牌恒 `False`。
- **宽度接口的 `idx` 不要传臆造键**：不传 = 服务端自动解析 A 股最新查询索引。
- **空结果 ≠ 市场为空**：先核对 symbol 与窗口再下结论。
- `_df=True` 转 DataFrame 需要安装 pandas（可选依赖）。
- ETF 用 6 位码直接查（如 `510300`）；`cli.kline.is_etf(sym)` 可判断。

## 7. 错误处理速查（都是 `FinPipeError` 子类）

| 异常 | 含义 | 怎么做 |
|---|---|---|
| `AuthError` | 401/403 凭证或权限 | 按第 1 节申请自己的 AppID 并配置环境变量 |
| `LimitError` | 429 限流 / 超上限 | 体验 AppID 共享池限额：稍等重试或换自己的 AppID；区间类缩小 begin/end |
| `UsageError` | 参数不合法 | 按消息修正；参数合同查 `cat.function(name)["params"]` |
| `DataError` | 单位/守护校验违例 | 数据在报警：换指标或核实口径，勿静默吞掉 |
| `CatalogError` | 目录查无此函数/指标 | `cat.search(...)` 找正确名字，禁止臆造 |
| `TransportError` / `ServerError` | 网络 / 服务端 | 可重试；持续失败再排查凭证与网络 |

## 8. 装入 AI agent

skill 随包分发，复制到 agent 的 skill 目录即可被自动发现：

```bash
cp -r "$(python3 -c 'import finpipe; print(finpipe.skill_dir())')" ~/.agents/skills/finpipe
# 项目级：放进仓库的 .zcode/skills/ 或 .claude/skills/（各工具发现路径不同）
```

许可：MIT——代码自由使用；云端数据服务需账号与配额（内置体验 Key 为共享池，额度有限）。
