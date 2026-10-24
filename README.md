# wm-finpipe

[![CI](https://github.com/open-winmale/finpipe/actions/workflows/ci.yml/badge.svg)](https://github.com/open-winmale/finpipe/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/wm-finpipe)](https://pypi.org/project/wm-finpipe/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](pyproject.toml)
[![License: PolyForm Noncommercial](https://img.shields.io/badge/License-PolyForm_NC_1.0-blue)](./LICENSE)
[![Types: py.typed](https://img.shields.io/badge/Types-py.typed-blue)](src/finpipe/py.typed)

> **English TL;DR** — `wm-finpipe` is a source-available Python SDK for A-share market data:
> k-line (3 adjustment modes), intraday snapshots, money flow, the three financial statements,
> 2,197 metric codes (TTM, historical & industry percentiles, dividend analytics), a screener
> facade (single-stock screens & server-side market breadth), announcements and company profiles.
> Ships a machine-readable offline catalog, unified base units with per-response data guards
> (ratios as decimals, money in CNY, volume in shares), a typed facade, an AI-agent skill, and a
> zero-config trial AppID. **Install**: `pip install wm-finpipe`. Free for non-commercial use.

> **⚠️ 许可声明（请先阅读）**：本项目采用
> [PolyForm Noncommercial 1.0.0](LICENSE) 许可，**属于 source-available（源码可见），
> 不是 OSI 定义的开源软件**。个人学习、研究等非商业使用完全免费；商业使用需另行授权。

A 股个股数据 Python SDK（**A股为主，港股/美股部分支持**——K 线与档案等部分接口已覆盖）。
`pip install wm-finpipe` 后即可取数，无需任何配置（代码中 `import finpipe`）。

## 目录

[特性](#特性) · [快速上手](#快速上手) · [能力一览](#能力一览) · [我想做 X → 用哪一行](#我想做-x--用哪一行) ·
[数据正确性保障](#数据正确性保障) · [口径速查](#口径速查) · [免费额度与凭证](#免费额度与凭证) ·
[使用限制](#使用限制必读) · [English quick start](#english-quick-start) · [更多](#更多)

## 特性

- **免费且含实时**——个人学习、研究等非商业用途完全免费且足够使用；盘中快照、当日
  1 分钟分时等实时数据包含在内，不单独收费。
- **开箱即用**——SDK 内置体验 AppID，`Client()` 零配置即可取数；正式使用换成自己的 AppID。
- **选股免计算**——`cli.screener` 单票一行布尔筛选（涨停/均线/动量/放量）+ 全市场
  涨跌全景/分桶/行业分布/涨跌榜，服务端预计算索引直出，你不拉全市场数据、不算均线。
- **单位统一 + 数据守护**——全库基础单位（比率/涨跌幅=小数、金额=元、量=股）；
  每次返回做量级守护与关系不变量校验，错误的量级到不了你的代码（见「数据正确性保障」）。
- **算好的增值数据**——2,197 个指标码：TTM、3/5/10 年历史分位、192 个行业内分位、
  专业的股息计算（TTM 股息率/派息率 + 11 个质量筛选器），服务端一次取数直出。
- **财报按最新会计准则归一**——新旧准则科目差异平台内部适配，跨年、跨公司直接比较。
- **目录随包 + AI 原生**——164 个底层函数、64 个核心接口、2,197 个指标码离线可查；
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

### 十行上手

```python
import finpipe

cli = finpipe.Client()                  # 零配置：内置体验 appid 自动启用

cli.kline.bars("600519", n=30)                          # 日 K（不复权）
cli.kline.bars("600519", n=30, adj="qfq")               # 前复权 / "hfq"=后复权
cli.screener.screen_limit_up("600519")                  # 今日涨停了吗（bool）
cli.screener.index_breadth_summary()                    # 全市场涨跌全景（服务端直出）
cli.statements.income("600519", years=5)                # 利润表（合并口径，多期）
cli.dividend.yield_ttm("600519")                        # TTM 股息率（小数）
cli.indicator.get("600519", "$PE_TTM_LAST")             # 平台指标（TTM 市盈率）
cli.notice.list("600519", window="3m")                  # 公告
cli.info.profile("600519")                              # 公司档案
```

## 能力一览

随包离线目录：**10 个数据域 · 164 个底层函数 · 2197 个指标代码**（11 个指标组、
74 个精选常用指标代码，`cat.search("中文")` 可编程检索）；友好层 **64 个核心接口**，
按使用视角组织为：

| 门面 | 核心能力 | 单位口径 |
|---|---|---|
| `cli.kline` | 日 K 三种复权、最新/盘中快照、1 分钟分时、ETF/指数 | 价格=元、量=股、涨跌幅=小数 |
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
| `cli.info` | 公司档案（名称/行业/组织类型/上市日期） | — |

## 我想做 X → 用哪一行

| 我想做… | 一行接口 | 省掉的计算 |
|---|---|---|
| 看 TTM 股息率 | `cli.dividend.yield_ttm(sym)` | 拉全部分红史→截 TTM 窗→查市值→相除 |
| 判断估值贵不贵 | `cli.indicator.get(sym, "$PCT_PE_TTM_10Y_LAST")` | 拉十年估值史自己算百分位 |
| 看公司在行业里的位置 | `$CUR_IND_ROE_PCT_LAST`（行业内 ROE 分位） | 拉全行业成分→逐票取 ROE→排序 |
| 筛高股息且派息可持续 | `cli.dividend.screen_quality(sym)` | 自写股息/派息率质量模型 |
| 站上 20 日线了吗 | `cli.screener.screen_above_ma20(sym)` | 拉 K 线→算均线→比较 |
| 全市场今天涨跌如何 | `cli.screener.index_breadth_summary()` | 全市场扫描→聚合统计 |
| 今日涨幅榜前十 | `cli.screener.index_top_movers(limit=10)` | 全市场扫描→排序→取头部 |
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
print(cli.screener.screen_above_ma20("600519"))              # True

# 全市场涨跌全景：服务端索引直出，免本地扫描（*_pct 百分数、median_pct 小数）
print(cli.screener.index_breadth_summary())
# {'total': 5685, 'up': 4567, 'down': 934, 'flat': 184, 'up_pct': 80.3, ...}

# 分红质量：高股息 + 派息可持续
print(cli.dividend.screen_quality("600519"))                 # True

# 公告信号：近 6 个月是否有回购公告
print(cli.notice.has_buyback("600519", "6m"))                # True
```

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
| 筛选阈值 | 小数 | `screen_momentum_20d(min_chg=0.10)` = 10%；宽度返回的 `*_pct`/`pct_of_total` 为百分数数值（80.3 = 80.3%） |
| 业绩预告同比 | 小数 | 脚本原生百分数已由 SDK 自动换算（1.467 = 146.7%） |
| 分红率 | 小数 | 0.0396 = 3.96% |
| 数据守护 | 每次返回默认校验 | 违例抛 `DataError`；逃生口见「数据正确性保障」 |
| 时间窗口 | `7d`…`5y` 或天数 | 分红/公告；最大 5 年，未知 token 显式报错 |
| 日期区间 | `begin` / `end` | 含端点，最多 5 年；覆盖不足会报错 |

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

- **401 / 403**（`AuthError`，凭证无效或权限不足）与 **429**（`LimitError`，限流）
  的错误消息里都附有申请自己 AppID 的步骤；
- 体验 AppID 是共享池、限额较低（批量或连跑容易触发 429），正式使用请按上面三步
  换成自己的 AppID 并配置 `FINPIPE_CLIENT_ID` / `FINPIPE_CLIENT_SECRET`。

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
                                            # + 164 functions (default limit = 20)
```

For non-commercial use the SDK is free (built-in trial AppID, register for your own quota).
Commercial use requires a license — see [License](#使用限制必读).
Units are unified to base units: prices/money in CNY, volume in shares, ratios and price
changes as decimals (0.332 = 33.2%); every response passes declared magnitude guards and
relational invariants (violations raise `DataError`).

## 更多

- **AI agent skill（随包分发）**：把 skill 装进 agent 的发现目录，AI 即可正确使用
  SDK（目录先行防臆造指标码、单位铁律、错误引导都在 skill 里）：

  ```bash
  cp -r "$(python3 -c 'import finpipe; print(finpipe.skill_dir())')" ~/.agents/skills/finpipe
  # 项目级按工具放入 .zcode/skills/ 或 .claude/skills/
  ```

- **生态工具 [big-winner](https://github.com/open-winmale/big-winner)**（基于本 SDK 构建的开源工具）：
  **收息佬**——攒股收息驾驶舱（分红日历、A/H 持仓透视、派息稳定性看板）；
  **波段**——估值买卖点参考：区间设置支持**推荐区间**（四条约束自动搜点，含成交次数）
  与**自定义区间**两种来源，附安全边界（高位介入回撤统计）与「波段 vs 长持」历史回放。
- [API 参考](docs/API.md)：四大类 64 个核心接口（参数 / 返回字段 / 单位口径 / 示例）+ 指标组
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
