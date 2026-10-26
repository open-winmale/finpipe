# wm-finpipe

[![CI](https://github.com/open-winmale/finpipe/actions/workflows/ci.yml/badge.svg)](https://github.com/open-winmale/finpipe/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/wm-finpipe)](https://pypi.org/project/wm-finpipe/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](pyproject.toml)
[![License: PolyForm Noncommercial](https://img.shields.io/badge/License-PolyForm_NC_1.0-blue)](./LICENSE)
[![Types: py.typed](https://img.shields.io/badge/Types-py.typed-blue)](src/finpipe/py.typed)

> **English TL;DR** — `wm-finpipe` is a source-available (non-commercial) Python SDK for A-share market data:
> k-line (3 adjustment modes), intraday snapshots, money flow, the three financial statements,
> 2,197 metric codes (TTM, historical & industry percentiles, dividend analytics), a screener
> facade (single-stock screens & server-side market breadth), announcements and company profiles.
> Ships a machine-readable offline catalog, unified base units with per-response data guards
> (ratios as decimals, money in CNY, volume in shares), a typed facade, an AI-agent skill, and a
> zero-config trial AppID (shared pool; register for your own quota). **Install**: `pip install wm-finpipe`. Free for non-commercial use; commercial use requires a separate license.

> **⚠️ 许可声明（请先阅读）**：本项目采用
> [PolyForm Noncommercial 1.0.0](LICENSE) 许可，**属于 source-available（源码可见），
> 不是 OSI 定义的开源软件**。个人学习、研究等非商业使用完全免费；商业使用需另行授权。

A 股个股数据 Python SDK（**A股为主，港股/美股部分支持**——K 线与档案等部分接口已覆盖）。
`pip install wm-finpipe` 后即可取数，无需任何配置（代码中 `import finpipe`）。

## 目录

[特性](#特性) · [快速上手](#快速上手) · [能力一览](#能力一览) · [单位与数据守护](#单位与数据守护) ·
[我想做 X → 用哪一行](#我想做-x--用哪一行) · [免费额度与凭证](#免费额度与凭证) ·
[使用限制](#使用限制必读) · [更多](#更多)

## 特性

- **数据要全**——16 个数据域、113 个核心接口一站取全：K 线（三种复权、1 分钟分时、
  盘中快照、ETF/指数）、分红、三大报表、资金流、公告、业绩预告、股东治理（十大股东/
  质押五族/限售解禁/机构持仓/沪港通/国家队/高管增减持/股本结构）、回购（方案+执行）、
  并购重组、担保与诉讼、融资融券、可转债、盈利预测与研报、指数成分与估值、港美股披露。
- **数据要准**——财报按最新会计准则归一，跨年跨公司直接比较；全库基础单位
  （比率/涨跌幅=小数、金额=元、量=股）；每次返回做量级守护与关系不变量校验，
  错误的量级到不了你的代码（见下方「单位与数据守护」）。
- **特色数据**——非商业免费且含实时（盘中快照、当日 1 分钟分时不另收费）；
  `cli.screener` 涨停/均线筛选一行直出，全市场涨跌全景/分桶/行业分布/涨跌榜走
  服务端预计算索引，毫秒级响应，你不拉全市场数据、不算均线；2,197 个指标码
  （TTM、3/5/10 年历史分位、192 个行业内分位、TTM 股息率/派息率 + 11 个质量筛选器）
  服务端算好直出，不关心指标算法。
- **开箱即用**——SDK 内置体验 AppID，`Client()` 零配置即可取数；正式使用换成自己的 AppID。
- **目录随包 + AI 原生**——249 个底层函数、113 个核心接口、2,197 个指标码离线可查；
  附 Agent Skills 格式 skill（`finpipe.skill_dir()`），复制进 AI agent 即可正确使用。

## 快速上手

### 安装

```bash
pip install wm-finpipe                  # 基础安装
pip install "wm-finpipe[dataframe]"     # 可选：pandas 支持（_df=True）
```

国内镜像源（如阿里云）同步新版本可能滞后，装不到最新版时可临时指定官方源：
`pip install -i https://pypi.org/simple wm-finpipe`。开发/贡献者安装见
[CONTRIBUTING.md](CONTRIBUTING.md)。

### 三行上手

```python
import finpipe

cli = finpipe.Client()                            # 零配置：内置体验 appid 自动启用
print(cli.dividend.yield_ttm("600519"))           # 0.0396（TTM 股息率，小数）
print(cli.screener.index_breadth_summary())       # 全市场涨跌全景（服务端直出）
```

更多调用见下方「我想做 X → 用哪一行」。

## 能力一览

随包离线目录：**16 个数据域 · 249 个底层函数 · 2197 个指标代码**（11 个指标组、
75 个精选常用指标代码，`cat.search("中文")` 可编程检索）；友好层 **113 个核心接口**，
按使用视角组织为：

| 门面 | 核心能力 | 单位口径 |
|---|---|---|
| `cli.kline` | 日 K 三种复权（自上市首日起全覆盖，最早 1991 年）、最新/盘中快照、1 分钟分时、ETF/指数 | 价格=元、量=股、涨跌幅=小数 |
| `cli.screener` | 单票筛选器（涨停/均线/动量/回撤/放量）+ 全市场涨跌全景/分桶/行业分布/涨跌榜 | 阈值=小数；宽度 `*_pct`=百分数数值 |
| `cli.moneyflow` | 主力/超大单/大单/中单/小单净流入（日频+盘中） | 金额=元 |
| `cli.statements` | 三大报表多期、合并 vs 母公司、目录树、审计意见 | 报表原币元 |
| `cli.segments` | 经营分部：分产品/业务/区域收入构成 | 元；比率=小数 |
| `cli.indicator` | 按指标码取数：估值/盈利/成长/现金流/杜邦 | 比率=小数 |
| `cli.valuation` | PE/PB/PS/市赚率的历史统计与分位（窗口上限 3 年） | 分位=小数 |
| `cli.notice` | 公告检索、回购/减持信号 | — |
| `cli.filings` | 定期报告清单与最新 | — |
| `cli.forecast` | 业绩预告/快报、财报披露日历 | 同比=小数 |
| `cli.dividend` | 分红历史、TTM 股息率/派息率、质量筛选器 | 率=小数、DPS=元/股 |
| `cli.equity` | 股东治理：十大股东/股东户数/质押/解禁/机构持仓/沪港通/国家队/高管增减持/股本/回购/并购重组/关联交易/担保/诉讼 | 比例=小数、金额=元、量=股 |
| `cli.margin` | 个股融资融券（融资买入/偿还/余额、融券卖出/偿还/余量） | 金额=元、量=股 |
| `cli.estimates` | 机构盈利预测（逐年 EPS/PE）、预测明细、评级统计、个股研报 | EPS=元/股、PE=倍 |
| `cli.cbond` | 可转债合约快照、条款事件、正股关联、强赎计数、日 K 与盘中 1 分钟 | 价格=元（面值 100） |
| `cli.workout` | 契约套利条款（要约收购/换股/现金选择权）看板与单票查询 | 价格=元 |
| `cli.index` | 指数键列表、成分股（市值/估值中枢）、权重股、宽基估值时序 | 市值=元、比率=小数、权重=小数 |
| `cli.intl` | 港股 CCASS/主要股东/机构评级/盈利预测，港美沽空，美股发行信息 | 量=股、占比=小数、价格=披露币种 |
| `cli.info` | 公司档案（名称/行业/组织类型/上市日期） | — |

## 我想做 X → 用哪一行

| 我想做… | 一行接口 | 省掉的计算 |
|---|---|---|
| 看 TTM 股息率 | `cli.dividend.yield_ttm(sym)` | 拉全部分红史→截 TTM 窗→查市值→相除 |
| 判断估值贵不贵 | `cli.indicator.get(sym, "$PCT_PE_TTM_10Y_LAST")` | 拉十年估值史自己算百分位 |
| 看公司在行业里的位置 | `$CUR_IND_ROE_PCT_LAST`（行业内 ROE 分位，1=行业最高） | 拉全行业成分→逐票取 ROE→排序 |
| 筛高股息且派息可持续 | `cli.dividend.screen_quality(sym)` | 自写股息/派息率质量模型 |
| 站上 20 日线了吗 | `cli.screener.screen_above_ma20(sym)` | 拉 K 线→算均线→比较 |
| 全市场今天涨跌如何 | `cli.screener.index_breadth_summary()` | 全市场扫描→聚合统计 |
| 看最新十大股东 | `cli.equity.query_holder10(sym)` | 翻定期报告→抄股东名单 |
| 质押比例高不高 | `cli.equity.query_pledge_summary(sym)` | 翻质押公告→逐笔累加 |
| 下半年解禁压力大吗 | `cli.equity.query_release(sym)` | 翻解禁公告→手工排期 |
| 两融余额什么水平 | `cli.margin.query(sym)` | 翻交易所两融披露→对日期 |
| 券商怎么看这只票 | `cli.estimates.query_forecast(sym)` | 汇总各家研报预测→自己算均值 |
| 沪深300 都有谁 | `cli.index.members("index.hs300", "mv", 10)` | 找成分表→自己拉行情 |
| 这票正股有哪些转债 | `cli.cbond.of_stock(sym)` | 翻转债名录→逐只对正股 |
| 港股筹码在谁手里 | `cli.intl.query_ccass(sym)` | 上披露易→逐日查 CCASS |
| 今日涨幅榜前十 | `cli.screener.index_top_movers(limit=10)` | 全市场扫描→排序→取头部 |
| 近半年有无回购/减持 | `cli.notice.has_buyback(sym, "6m")` | 拉公告列表→分类匹配→截窗 |
| 合并与母公司差多少 | `cli.statements.compare(sym)` | 双表对齐→逐科目相除 |

**常用示例（输出为预期量级；`cli.kline.bars` / `statements.income` 等其余接口同风格）**：

```python
import finpipe

cli = finpipe.Client.from_env()

# TTM 股息率：小数口径，0.0396 = 3.96%
print(cli.dividend.yield_ttm("600519"))                      # 0.0396

# 估值温度计：PE(TTM) 处于近 10 年 42% 分位（小数）
print(cli.indicator.get("600519", "$PCT_PE_TTM_10Y_LAST"))   # 0.42

# 行业定位：ROE 在同行业内的分位（1.0 = 行业最高；茅台 ROE 为行业之最）
print(cli.indicator.get("600519", "$CUR_IND_ROE_PCT_LAST"))  # 1.0

# 技术面一行布尔：是否站上 20 日均线
print(cli.screener.screen_above_ma20("600519"))              # True

# 全市场涨跌全景：服务端索引直出，免本地扫描（*_pct 百分数、median_pct 小数）
print(cli.screener.index_breadth_summary())
# {'total': 5685, 'up': 4567, 'down': 934, 'flat': 184, 'up_pct': 80.3, ...}

# 分红质量：高股息 + 派息可持续（默认精品窗口=派息率 30%–70%，可显式放宽）
print(cli.dividend.screen_quality("600519", min_yield=0.02, payout_max=1.5))  # True

# 公告信号：近 6 个月是否有回购公告
print(cli.notice.has_buyback("600519", "6m"))                # True
```

以上能力全部在离线目录可查：`cat.search("分位")`、`cat.metrics_in_group("dividend")`。

## 单位与数据守护

全库统一基础单位：**比率 / 涨跌幅 = 小数**（0.01 = 1%，ROE 0.332 = 33.2%）、
**金额 / 价格 / 市值 = 元**（报表原币）、**成交量 = 股**；各接口单位口径见「能力一览」表。
返回前做量级与关系不变量校验，违例抛 `DataError`——错误的量级到不了你的代码。
需要脚本原始口径时：`_raw=True`（store 原始行）、`_units="native"`（脚本输出单位），
或 `Client(validate=False)` 关闭校验。

数据深度：个股/ETF 日 K 覆盖**自上市首日以来的全部交易日**（最早 1991 年）；
单次区间上限 5 年、默认单次 500 根（`Client(max_limit=...)` 可调）。全量深回溯
（1990 年代不复权老数据）可能触发不变量守护，需整段历史时 `validate=False` 取全。

## 免费额度与凭证

**个人学习、研究等非商业使用完全免费**，注册开放平台账号即得免费额度（商业使用需另行
授权，见「使用限制」）。SDK 内置体验 AppID 安装即用，但它是共享池、额度有限，仅供初次
体验；正式使用请申请自己的 AppID——非商业用途下它就是正式服务，注册即得、无需付费
（额度更充足）：

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

### 遇到 401 / 403 / 429

401/403（`AuthError`）与 429（`LimitError`，限流）的错误消息里都附有申请步骤；
体验 AppID 是共享池、限额较低，批量或连跑容易触发 429——按上面三步换成自己的 AppID 即可。
403「策略拒绝」（POLICY_DENIED）则是 AppID 接口权限范围、与额度无关，按错误消息指引处理。

## 使用限制（必读）

本项目采用 [PolyForm Noncommercial License 1.0.0](LICENSE)：

- ✅ **仅限非商业目的**：个人学习、研究、教学、学术、爱好者项目、公益组织等，完全免费；
- ❌ **严禁商业使用**：任何商业目的的使用、再分发或服务化均需另行获得商业授权；
- 本许可属于 source-available（源码可见）而非 OSI 定义的开源许可。

商业授权请联系项目维护方。数据仅供研究参考，不构成任何投资建议。

## 更多

- **AI agent skill（随包分发）**：把 skill 装进 agent 的发现目录，AI 即可正确使用
  SDK（目录先行防臆造指标码、单位铁律、错误引导都在 skill 里）：

  ```bash
  cp -r "$(python3 -c 'import finpipe; print(finpipe.skill_dir())')" ~/.agents/skills/finpipe
  # 项目级按工具放入 .zcode/skills/ 或 .claude/skills/
  ```
  skill 源文件：[src/finpipe/skills/finpipe/SKILL.md](src/finpipe/skills/finpipe/SKILL.md)
  （LLM 可直接读取的结构化用法）。

- **生态工具 [big-winner](https://github.com/open-winmale/big-winner)**（基于本 SDK 构建的开源工具）：
  **收息佬**——攒股收息驾驶舱（分红日历、A/H 持仓透视、派息稳定性看板）；
  **波段**——估值买卖点参考：区间设置支持**推荐区间**（四条约束自动搜点，含成交次数）
  与**自定义区间**两种来源，附安全边界（高位介入回撤统计）与「波段 vs 长持」历史回放。
- [API 参考](docs/API.md)：四大类 113 个核心接口（参数 / 返回字段 / 单位口径 / 示例）+ 指标组
- **OpenAPI / Swagger**：[docs/openapi.json](docs/openapi.json)（OpenAPI 3.1，可导入
  Apifox / Postman 等工具）；[docs/swagger.html](docs/swagger.html)（已内联 spec，浏览器直接打开；
  Swagger UI 资源来自 CDN，若浏览器限制 `file://` 可在 docs 目录起 `python -m http.server`）
- 类型化门面：全部目录命名空间带类型签名与 docstring（`py.typed`），IDE 直接补全；
  单次拉取上限 `Client(max_limit=500)` 可调
- 批量调用：`cli.call_batch("kline.query_bars", ["600519", "000001"])` 单次 HTTP 返回
  `{symbol: 结果}`；`on_error="skip"` 时逐标的隔离错误
- [贡献指南](CONTRIBUTING.md)：提交门禁、内容规范、许可政策
- 运行测试：`pytest`（不联网）；`FINPIPE_LIVE=1 pytest tests/test_live.py`（真实冒烟）
