# wm-finpipe

[![CI](https://github.com/open-winmale/finpipe/actions/workflows/ci.yml/badge.svg)](https://github.com/open-winmale/finpipe/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](pyproject.toml)
[![License: PolyForm Noncommercial](https://img.shields.io/badge/License-PolyForm_NC_1.0-blue)](./LICENSE)
[![Types: py.typed](https://img.shields.io/badge/Types-py.typed-blue)](src/finpipe/py.typed)

> **English TL;DR** — `wm-finpipe` is a source-available Python SDK for A-share market data:
> k-line (3 adjustment modes), money flow, the three financial statements, 2,197 metric codes
> (historical & industry percentiles, TTM dividend analytics, technical screens), announcements,
> dividend history & high-dividend screeners. Ships a machine-readable offline catalog,
> unified base units with per-response data guards (ratios as decimals, money in CNY,
> volume in shares), a typed facade, and a zero-config trial AppID.
> **Install from source** (PyPI release is pending): `git clone` the repo, `pip install .`,
> then `finpipe.Client()`. Free for non-commercial use; commercial use requires a separate
> license. See the [English quick start](#english-quick-start).

> **⚠️ 许可声明（请先阅读）**：本项目采用
> [PolyForm Noncommercial 1.0.0](LICENSE) 许可，**属于 source-available（源码可见），
> 不是 OSI 定义的开源软件**。个人学习、研究等非商业使用完全免费；商业使用需另行授权。

A 股个股数据 Python SDK（**A股为主，港股/美股部分支持**——K 线与档案等部分接口已覆盖，
详见目录）。注册即得充足免费额度；源码安装后即可取数，无需任何配置
（代码中 `import finpipe`）。当前尚未发布到 PyPI，请使用「安装」一节的源码方式。

```python
import finpipe

cli = finpipe.Client()                  # 零配置：内置体验 appid 自动启用

cli.kline.bars("600519", n=30)                          # 日 K（不复权）
cli.kline.bars("600519", n=30, adj="qfq")               # 前复权 / "hfq"=后复权
cli.statements.income("600519", years=5)                # 利润表（合并口径，多期）
cli.dividend.history("600519", limit=10)                # 分红历史明细
cli.dividend.yield_ttm("600519")                        # TTM 股息率（小数）
cli.indicator.get("600519", "$PE_TTM_LAST")             # 平台指标（TTM 市盈率）
cli.notice.list("600519", window="3m")                  # 公告
cli.info.profile("600519")                              # 公司档案
```

## 为什么选择 finpipe

- **免费额度充足**——注册开放平台账号即得免费额度，个人学习、研究等非商业用途完全免费且
  足够使用（具体额度以开放平台为准）。
- **开箱即用**——SDK 内置体验 appid，`Client()` 零配置即可取数；正式使用换成自己的 appid。
- **目录随包、离线可查**——155 个底层函数、44 个核心接口、2197 个指标代码随 wheel 分发，
  断网也能查全部接口合同。类型支持说明：目录命名空间与生成层带类型签名（`py.typed`），
  44 个核心接口的方法有显式签名；其余底层函数经动态委托访问，IDE 补全以目录为准：

  ```python
  import finpipe

  cat = finpipe.load()              # 离线数据目录（纯本地读文件，零网络）
  hits = cat.search("股息")          # 跨 155 个函数 + 2197 个指标代码混合检索
  cat.function("bonus.snapshot_yield_ttm")["params"]   # 任意函数的参数/返回/示例
  ```

  目录对象的全部方法见 [docs/API.md](docs/API.md) 的「数据目录（离线）」一节。
- **单位统一、自动换算**——全库基础单位：比率/涨跌幅=小数（0.332 = 33.2%）、
  金额/价格/市值=元（报表原币）、股数/成交量=股。上游脚本的原生口径（百分数、手等）
  由 SDK 统一换算，你不需要再处理「这个接口是百分数、那个是小数」的问题；
  特殊需要时 `_units="native"` / `_raw=True` 可取脚本原值（见「数据正确性保障」）。
- **财报按最新会计准则归一**——新旧会计准则的科目差异在平台内部完成适配，输出口径一致，
  可直接做跨年、跨公司比较。
- **数据面完整**——K 线、资金流、三大报表、指标、公告、定期报告、业绩预告/快报、分红、
  公司档案，一个 SDK 覆盖个股研究常用数据。

## 数据能力详解

### 行情 K 线

- **三种复权**：不复权 `nr`（默认）、前复权 `qfq`、后复权 `hfq`；复权与不复权输出字段一致
  （date/open/high/low/close/volume/amount/percent），可直接穿插使用。
- **最新与盘中**：最新一根日 K；盘中快照（单票 `live` / 多标的 `batch_live`，单次请求）；
  当日 1 分钟分时（`min1`，有损合成采样，非逐笔，休市读上一交易日）。
- **ETF 与指数**：ETF 日线已入库；指数键自动桥接指数点位（指数无复权）。
- **筛选与全景**（底层目录能力，`cli.call`）：均线类（MA20/60/120、突破）、
  事件类（涨停/跌停/放量/回踩）筛选；全市场涨跌全景、涨跌榜、涨跌幅分桶。
- **回测口径**：财报季取数不因披露进度截断；日频回测口径按已披露数据截断。
- **日期区间**：`bars(..., begin="2026-01-01", end="2026-06-30")` 按自然日筛选
  （最多 5 年；单次取数受 `max_limit` 约束，覆盖不足会明确报错，不会静默截断）。
- 单位：价格=元，量=**股**（脚本原生为手，SDK 自动 ×100 换算，A 股/港美/ETF 同口径），
  额=元，涨跌幅=小数（0.01 = 1%）。
- 标的代码自动归一：`sh.600519.SH`、`cn.000001` 均可直接传入。

### 资金流向

- 日频主力/超大单/大单/中单/小单净流入；最新一行；盘中快照。
- **日期区间**：`bars(..., begin=..., end=...)`，规则与 K 线一致（最多 5 年）。
- 口径说明：单子分级聚合，**非 Level2 逐笔委托**。

### 财务报表

- **三大报表**（资产负债 / 利润 / 现金流）多期透视，默认 5 期年报降序，也可指定年份。
- **合并 vs 母公司**：分别取数（`scope=`）；`compare()` 直接返回合并值/母公司值/差额/
  差额占比（占比 = 差额 / 合并值，**小数**口径，0.078 = 7.8%；母公司未披露的科目差额为空）。
- **树视图**：`tree()` 按报表树序输出，含派生比率行（流动比率、资产负债率、毛利率等）；
  树视图派生行保留原生口径（pct 行为百分数、`fmt="x"` 行为倍数、科目行为元），
  适合展示核对，跨接口运算请用 `compare()`。
- **审计意见**：`audit()` 按年报返回 `{年份: 意见}`。
- **可用年份**：`years()` 返回该报表可用的年报年份（降序）。
- **新旧会计准则口径已归一**：跨年比较不需要自己调整科目。
- 金额=报表原币（A 股为元）。

### 指标层

- **11 个指标组、74 个精选常用指标代码**（全量 2197 个指标代码随包）：估值、盈利与杜邦、
  成长、营收与利润规模、现金流、资产负债与偿债、运营效率、分红、行情与风险、公司信息、
  收入构成。
- **常用指标开箱即用**：PE/PB/PS/PCF、ROE/ROIC/杜邦分解、TTM 同比与多年年化、
  周转天数与现金周期、费用率、市值与年化收益。
- **口径标注**：`_LAST` = 最新截面；指标层比率类为**小数**（0.332 = 33.2%）、
  金额/市值为**元**（与报表、资金流同口径，可直接混算）；业绩预告的同比/幅度字段
  也已由 SDK 统一换算为小数——全库不再有「有的接口是百分数」的问题。
- **经营与财务多口径**：合并/母公司、单期/多期/TTM、披露原值/派生指标；
  收入构成提供境内/境外收入占比与对应毛利率（产品线/业务分部口径一期未纳入）。

### 公告

- 检索：单票（`list`）、全市场近期（`recent`）、按类别（`by_category`）、
  指定日期全市场（`on_date`）、单票日期区间（`find`）。
- 信号：回购、减持、增持、股权激励的窗口判定，并返回**证据行**（原始公告可回溯）。
- 时间窗口：`7d` / `1m` / `3m` / `6m` / `1y` / `3y` / `5y` 或天数整数。

### 定期报告

- 年报 / 半年报 / 季报清单：报告期、标题、PDF 链接。
- 分工：结构化科目数字走财务报表，原文链接走本域。

### 业绩披露事件

- **业绩预告**：净利/扣非/营收区间 + 同比 + 修正轨迹。
- **业绩快报**：披露的近似单值。
- **预约披露日历**：`disclosure_history()` 历史与 `next_disclosure()` 下次披露日期。

### 分红

- **历史明细**：扁平规范化字段（公告日/除权日/派息日/每股分红/分红总额/方案摘要），
  支持按除权日的日期区间筛选（最多 5 年）；最近一次；指定报告期。
- **每股分红**：财报期 DPS（元/股）。
- **窗口统计**：`window_stats()` 单次返回任意窗口（7d/1m/3m/6m/1y/3y/5y 或天数）的
  每股股利合计、总分红金额与分红次数（按除权日统计）。
- **TTM 股息率 / 派息率**：小数口径（0.0396 = 3.96%，0.799 = 79.9%）。
- **质量筛选**：高股息、派息可持续性、股息稳定性/趋势/改善、低估+高股息。
- 列表与 DPS 为披露原值，率类与筛选为计算派生（逐函数标注）。

### 股本与公司档案

- 公司档案：名称、行业、组织类型、上市日期。
- 股本变动数据；F10 深度页（十大股东/质押/解禁等）一期未纳入。

## 指标体系：算好的增值数据

2197 个指标代码不只是"字段多"——大量派生口径是平台服务端算好直出的，
**你不用自己拉原始数据再做计算**。按用途分成 11 组（见 [docs/API.md](docs/API.md) 指标组表），
几个最有代表性的能力：

**我想做 X → 用哪一行**

| 我想做… | 一行接口 | 省掉的计算 |
|---|---|---|
| 看 TTM 股息率 | `cli.dividend.yield_ttm(sym)` | 拉全部分红史→截 TTM 窗→查市值→相除 |
| 判断估值贵不贵 | `cli.indicator.get(sym, "$PCT_PE_TTM_10Y_LAST")` | 拉十年估值史自己算百分位 |
| 看公司在行业里的位置 | `$CUR_IND_ROE_PCT_LAST`（行业内 ROE 分位） | 拉全行业成分→逐票取 ROE→排序 |
| 筛高股息且派息可持续 | `cli.dividend.screen_quality(sym)` | 自写股息/派息率质量模型 |
| 站上 20 日线了吗 | `cli.kline.screen_above_ma20(sym)` | 拉 K 线→算均线→比较 |
| 全市场今天涨跌如何 | `cli.kline.index_breadth_summary("index.cn.all")` | 全市场扫描→聚合统计 |
| 近半年有无回购/减持 | `cli.notice.has_buyback(sym, "6m")` | 拉公告列表→分类匹配→截窗 |
| 合并与母公司差多少 | `cli.statements.compare(sym)` | 双表对齐→逐科目相除 |

**示例（输出为预期量级，单位口径与全库一致）**：

```python
import finpipe

cli = finpipe.Client.from_env()

# TTM 股息率：小数口径，0.0396 = 3.96%
print(cli.dividend.yield_ttm("600519"))                      # 0.0396

# 估值温度计：PE(TTM) 处于近 10 年 42% 分位（小数）
print(cli.indicator.get("600519", "$PCT_PE_TTM_10Y_LAST"))   # 0.42

# 行业定位：ROE 位于同行业前 8% 分位（小数，越小越靠前）
print(cli.indicator.get("600519", "$CUR_IND_ROE_PCT_LAST"))  # 0.08

# 技术面一行布尔：是否站上 20 日均线
print(cli.kline.screen_above_ma20("600519"))                 # True

# 分红质量：高股息 + 派息可持续
print(cli.dividend.screen_quality("600519"))                 # True

# 公告信号：近 6 个月是否有回购公告
print(cli.notice.has_buyback("600519", "6m"))                # True
```

### 指标体系的四类特色能力

1. **专业的股息计算**——`yield_ttm` / `payout_ttm` 一键快照（TTM 分红总额÷最新市值、
   TTM 分红÷归母净利 TTM）；11 个单票质量筛选器（高股息、派息可持续、股息稳定/改善/下滑、
   低估+高股息…）；18 个全市场筛选积木（如 `bonus.index_where_high_yield_5()` = 连续 5 年
   高股息股票池）；背后还有 60 个分红衍生指标（近 3/5/10 年分红均值/最低/趋势）。
2. **分位计算**——历史分位：PE/PB/股息率的 3/5/10 年分位（`$PCT_PE_TTM_10Y_LAST` 等，
   估值温度计）；行业分位：192 个 CUR_IND 前缀的行业内相对指标
   （如 `$CUR_IND_ROE_PCT_LAST`：ROE/毛利率/营收/市值分位）。
   都是服务端一次取数直出，不用拉十年历史或全行业成分自算。
3. **窗口化衍生口径**——TTM 口径 586 个、同比 68 个、3/5/10 年年化/均值/最低/趋势 394 个；
   命名窗口（`7d`…`5y` 或天数）在分红/公告域通用，未知 token 显式报错。
4. **服务端算好的筛选与汇总**——14 个技术面筛选（均线/动量/量比/涨跌停，一行布尔）+
   6 个全市场宽度汇总（涨跌全景/分桶/行业分布/涨跌榜）；公告域的回购/减持/增持/股权激励
   窗口判定与证据行；财报域的合并 vs 母公司差额占比与杜邦分解。
   另有约 224 个宏观/行业横截面指标（CPI/PPI/M2/用电量/社零…）与 54 个指数加权指标
   （等权/市值/调和加权股息率、相对指数 Alpha/Beta），行业层面数据不必另找源。

以上能力全部在离线目录可查：`cat.search("分位")`、`cat.metrics_in_group("dividend")`。

## 数据正确性保障

单位问题曾让用户把 3.96% 读成 0.04%。finpipe 用三层机制保证你拿到的数据量级正确，
而不是靠"文档约定"：

1. **脚本原值 → SDK 单点换算**——上游脚本永远输出其原生口径（如差额占比百分数、
   A 股成交量手）；SDK 在 `call()` 里按目录声明做**唯一的**一次换算，转成基础单位
   （比率小数、金额元、股数股）。换算规则集中在随包目录的 YAML 声明里，可审计、可追溯。
2. **返回前校验**——换算后立即执行目录声明的量级范围守护与关系不变量（如
   `diffp ≈ 差额/合并值`、`volume×close ≈ amount`）。违例直接抛
   `DataError`（含字段/实际值/期望范围），**错误的量级到不了你的代码里**；
   换算声明写错也会被数据本身自动暴露。
3. **持续审计**——`tools/audit_units.py` 对一组覆盖不同板块/行业/规模的样本公司
   逐家跑全部守护与跨接口一致性（如 `dividend.yield_ttm` 与 `$BONUS_RATE_TTM_LAST`
   恒等、指标层市值与 K 线快照同量级）；CI 每个交易日夜间自动执行，口径漂移会在
   日志中显式报告。

校验默认开启。三种逃生口（有测试守护其语义）：

| 参数 | 语义 |
|---|---|
| `_units="native"` | 保留脚本输出的原生单位（字段名仍规范化），换算与校验都跳过 |
| `_raw=True` | 返回 store 原始行（连字段规范化也跳过） |
| `Client(validate=False)` | 保留换算、关闭量级/不变量校验 |

## 口径速查

| 维度 | 取值 | 说明 |
|---|---|---|
| 复权 | `nr` / `qfq` / `hfq` | 指数无复权 |
| 报表范围 | 合并 / 母公司 / 差额 | 差额与占比为派生值（占比已换算为小数） |
| 期间 | 单期 / 多期 / TTM | TTM = 最近四个季度滚动 |
| 数据性质 | 原始数据 / 指标 | 逐函数标注，可回溯目录 |
| 会计准则 | 新旧准则已归一 | 平台内部适配 |
| 价格 / 金额 / 市值 | 元 | 报表原币；指标层与报表同口径，可直接混算 |
| 成交量 | 股 | A 股/港美/ETF 同口径（脚本手原值由 SDK 自动 ×100） |
| 涨跌幅 / 比率 | 小数 | 0.01 = 1%；0.332 = 33.2%（ROE/毛利率/资产负债率等） |
| 业绩预告同比 | 小数 | 脚本原生百分数已由 SDK 自动换算（1.467 = 146.7%） |
| 分红率 | 小数 | 0.0396 = 3.96% |
| 数据守护 | 每次返回默认校验 | 违例抛 `DataError`；逃生口见「数据正确性保障」 |
| 时间窗口 | `7d`…`5y` 或天数 | 分红/公告；最大 5 年，未知 token 显式报错 |
| 日期区间 | `begin` / `end` | 含端点，最多 5 年；覆盖不足会报错 |

## 安装

当前尚未发布到 PyPI，请从源码安装：

```bash
git clone https://github.com/open-winmale/finpipe.git
cd finpipe
pip install .                          # 基础安装
pip install ".[dataframe]"             # 可选：pandas 支持（_df=True）
```

开发/贡献者安装：`pip install -e ".[dev,dataframe]"`。  
PyPI 发布后可直接 `pip install wm-finpipe`，届时会更新本节与 README 徽章。

## 免费额度与凭证

**个人学习、研究等非商业使用完全免费**。注册开放平台账号即可获得免费额度，个人研究足够使用；
具体额度以开放平台为准。商业使用需另行授权（见「使用限制」）。

SDK 内置体验 AppID，安装即用，但它是共享池、额度有限，仅供初次体验。正式使用建议申请
自己的 AppID（额度更充足）：

1. 打开 [赢麻了开放平台](https://open.winmale.com)，扫码微信登录注册；
2. 点击右上角「我的」，进入「开放平台」；
3. 左侧导航「我的应用」→「查看应用信息」，即可查看 `client_id` 与 api-key（即 `client_secret`）。

拿到自己的 AppID 后任选一种配置方式：

```bash
# 方式一：环境变量
export FINPIPE_CLIENT_ID=...
export FINPIPE_CLIENT_SECRET=...

# 方式二：凭证文件 ~/.finpipe/credentials.env（KEY=VALUE 每行一条）
```

也可以在代码中直接传入：`finpipe.Client(client_id=..., client_secret=...)`。
不配置时自动使用内置体验 AppID。

### 遇到 401 / 403 / 429 怎么办

内置体验 AppID 是多人共享池，可能失效、被撤销或被限流。收到这些错误时请申请自己的 AppID：

- **401 / 403** → SDK 抛 `AuthError`（带 `status` 与服务端 `code`，如 `POLICY_DENIED`）；
- **429** → SDK 抛 `LimitError(code="rate_limited")`，消息会带 `Retry-After` 建议；
- 错误消息本身已包含下面 3 步，程序里可直接 `except finpipe.AuthError` / `except finpipe.LimitError`。

申请步骤：打开 [open.winmale.com](https://open.winmale.com) 微信扫码登录 → 右上角「我的」→
「开放平台」→「我的应用」→「查看应用信息」→ 复制 `client_id` 与 api-key；然后按上面的
环境变量或 `~/.finpipe/credentials.env` 配置。内置 AppID 只适合初次体验，正式研究请使用
自己的 AppID。

## 数据范围（一期，9 个数据域）

| 分类 | 数据域 | 性质 |
|------|--------|------|
| 市场行情 | 行情K线（日K/复权/盘中快照）、资金流向 | 原始数据 |
| 财务基本面 | 三大报表（资产负债/利润/现金流）、指标层（2197 个指标代码：估值/盈利/成长/现金流/杜邦…） | 报表=原始数据，指标=派生指标 |
| 信息披露 | 公告、定期报告清单、业绩预告/快报/披露日历、分红 | 原始数据（率类为指标） |
| 参考数据 | 公司档案 / 股本 | 原始数据 |

**原始数据与指标显式分标**：每个接口在目录中标注 `raw`（披露/直采数据，含外部源算好的）
或 `computed`（平台公式计算的派生指标），全量见 [docs/API.md](docs/API.md)。

数据经云端 API 运行时获取（代码与目录开源，数据不随包分发）。

> **目录是如何来的？** 随包目录由维护者从上游数据平台同步并冻结进发布物
> （schema 版本治理，详见 [CONTRIBUTING.md](CONTRIBUTING.md)），发布的是上游指标的**策展子集**。
> 贡献者无需重建目录即可使用全部功能；如需新增数据域或指标，请提 issue。

## 使用限制（必读）

本项目采用 [PolyForm Noncommercial License 1.0.0](LICENSE)：

- ✅ **仅限非商业目的**：个人学习、研究、教学、学术、爱好者项目、公益组织等，完全免费；
- ❌ **严禁商业使用**：任何商业目的的使用、再分发或服务化均需另行获得商业授权；
- 本许可属于 source-available（源码可见）而非 OSI 定义的开源许可。

商业授权请联系项目维护方。数据仅供研究参考，不构成任何投资建议。

## English quick start

```python
import finpipe

cli = finpipe.Client()                     # zero config: built-in trial appid

bars = cli.kline.bars("600519", n=30)      # daily k-line (price in CNY, volume in shares)
yield_ttm = cli.dividend.yield_ttm("600519")   # TTM dividend yield (decimal: 0.0396 = 3.96%)
cat = finpipe.load()
hits = cat.search("股息")                   # offline search across 2,197 metric codes
                                            # + 155 functions (default limit = 20)
```

For non-commercial use the SDK is free (built-in trial AppID, register for your own quota).
Commercial use requires a license — see [License](#使用限制必读).
Units are unified to base units: prices/money in CNY, volume in shares, ratios and price
changes as decimals (0.332 = 33.2%); every response passes declared magnitude guards and
relational invariants (violations raise `DataError`).

## 更多

- [API 参考](docs/API.md)：四大类 44 个核心接口（参数 / 返回字段 / 单位口径 / 示例）+ 指标组
- **OpenAPI / Swagger**：[docs/openapi.json](docs/openapi.json)（OpenAPI 3.1，可导入
  Apifox / Postman 等工具）；[docs/swagger.html](docs/swagger.html)（已内联 spec，浏览器直接打开；
  Swagger UI 资源来自 CDN，若浏览器限制 `file://` 可在 docs 目录起 `python -m http.server`）
- 类型化门面：全部目录命名空间带类型签名与 docstring（`py.typed`），IDE 直接补全；
  单次拉取上限 `Client(max_limit=500)` 可调
- 批量调用：`cli.call_batch("kline.query_bars", ["600519", "000001"])` 单次 HTTP 返回
  `{symbol: 结果}`；`on_error="skip"` 时逐标的隔离错误
- 数据守护：单位换算、量级守护与关系不变量的声明全部在随包目录 YAML 中，
  维护者可用 `python tools/audit_units.py` 对样本宇宙做单位口径审计（CI 夜间自动执行）
- [贡献指南](CONTRIBUTING.md)：提交门禁、内容规范、许可政策
- 运行测试：`pytest`（不联网）；`FINPIPE_LIVE=1 pytest tests/test_live.py`（真实冒烟）
