"""友好 API：按四大类组织的推荐入口（行情 / 财务 / 披露 / 参考）。

设计约定：
  - 参数统一 ``symbol``（6 位裸码；自动归一 cn./sh./sz./bj. 前缀与 .SH/.SZ/.BJ 后缀；
    港股 5 位、美股字母码）；
  - 方法名动宾化、可猜（bars/last/live/list/history/yield_ttm…）；
  - 返回 list[dict] / dict；返回列表的方法支持 ``_df=True`` 转 DataFrame，
    ``_raw=True`` 取未规范化原始行（仅部分方法）；
  - 本层是目录合同的薄翻译：高频方法显式包装；目录内其余函数经 ``__getattr__``
    属性直达（如 ``cli.kline.screen_above_ma20``、``cli.dividend.screen_quality``），
    目录之外的名字显式 AttributeError——164 个底层函数零遮蔽。
  - 选股能力集中在 ``cli.screener``：单票筛选器（bool）与全市场宽度（服务端
    预计算索引直出）显式包装，kline 目录的其余筛选函数经属性直达。

使用：
    cli = finpipe.Client.from_env()
    cli.kline.bars("600519", n=30)
    cli.statements.income("600519", years=5)
    cli.notice.list("600519", window="3m")
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

from finpipe.errors import CatalogError, LimitError, UsageError
from finpipe.units import finish_metric

if TYPE_CHECKING:  # pragma: no cover
    from finpipe.client import Client

# 区间/窗口上限（与上游脚本仓对齐）：
#  - 上游 store 单次硬上限 10000 行（见 kernel vfunc_store_find.go）
#  - 分红命名窗口 token 最大 5y（sys/anchor.xs window_days）
#  - 上游未识别 token 会静默退化为 30 天，SDK 侧改为显式报错
MAX_RANGE_DAYS = 1825
WINDOW_DAYS = {"7d": 7, "1m": 30, "3m": 90, "6m": 180,
               "1y": 365, "3y": 1095, "5y": 1825}


def _range_bounds(begin: str, end: str) -> tuple[date, date]:
    try:
        b = date.fromisoformat(str(begin)[:10])
        e = date.fromisoformat(str(end)[:10])
    except ValueError:
        raise UsageError("begin/end 需为 YYYY-MM-DD 格式", code="range") from None
    if b > e:
        raise UsageError("begin 不能晚于 end", code="range")
    span = (e - b).days
    if span > MAX_RANGE_DAYS:
        raise LimitError(
            f"区间跨度 {span} 天超过上限 {MAX_RANGE_DAYS} 天（5 年）；"
            "更早数据请缩短区间或分批用 limit 获取", code="range")
    return b, e


def _filter_by_date(rows: Any, begin: str, end: str, key: str, limit: int) -> Any:
    """按日期列过滤（含端点）；行数已触顶且最早日期仍晚于 begin 时，说明区间未被覆盖。"""
    if not isinstance(rows, list):
        return rows
    b, e = _range_bounds(begin, end)
    out = []
    dates = []
    for r in rows:
        d = str(r.get(key) or "")[:10] if isinstance(r, dict) else ""
        if d:
            dates.append(d)
        if d and b.isoformat() <= d <= e.isoformat():
            out.append(r)
    if limit and len(rows) >= limit and dates and min(dates) > b.isoformat():
        raise LimitError(
            f"区间未被覆盖：单次返回 {len(rows)} 行（上限 {limit}），最早仅到 {min(dates)}；"
            "请缩小 begin/end 或调大 Client(max_limit=...)（上游单次硬上限 10000 行）",
            code="range")
    return out


def _window_days(window: str | int) -> int:
    if isinstance(window, int) or str(window).isdigit():
        days = int(window)
    elif window in WINDOW_DAYS:
        days = WINDOW_DAYS[window]
    else:
        raise UsageError(
            f"未知窗口 {window!r}；可选 {sorted(WINDOW_DAYS)} 或正整数天数"
            "（上游未知 token 会静默按 30 天处理，故此处显式报错）", code="window")
    if days <= 0 or days > MAX_RANGE_DAYS:
        raise LimitError(f"窗口 {days} 天超出支持范围 1~{MAX_RANGE_DAYS} 天（5 年）",
                         code="window")
    return days


def _to_df(result: Any) -> Any:
    from finpipe.client import _to_dataframe
    return _to_dataframe(result)


# 友好命名空间 → 目录（XS）命名空间。目录真实命名空间为
# bonus/filings/forecast/kline/moneyflow/notice/rptdom；statements/indicator/info
# 是聚合层（indicator/info 走指标 eval，无目录函数）。
_FRIENDLY_NS_TO_CATALOG: dict[str, str] = {
    "kline": "kline",
    "screener": "kline",
    "moneyflow": "moneyflow",
    "statements": "rptdom",
    "notice": "notice",
    "filings": "filings",
    "forecast": "forecast",
    "dividend": "bonus",
}


class _Api:
    def __init__(self, client: "Client"):
        self._c = client

    def __getattr__(self, name: str) -> Any:
        """目录感知兜底：友好类未显式定义的目录函数，委托 ``client.call(ns.name, ...)``。

        友好层只对高频方法做动宾化包装（bars/history/yield_ttm…）；目录内其余
        函数（筛选器 screen_*、全景 index_*、格式化 fmt_* 等）同样可经本属性
        直接调用，例如 ``cli.kline.screen_above_ma20("600519")``、
        ``cli.dividend.screen_quality("600519")``。非目录成员一律 AttributeError，
        且以双下划线开头的名称永不委托（避免干扰魔术方法解析）。
        """
        if name.startswith("__"):
            raise AttributeError(name)
        client = self._c
        ns = ""
        for cand, cls in FRIENDLY_NAMESPACES.items():
            if cls is type(self):
                ns = cand
                break
        catalog_ns = _FRIENDLY_NS_TO_CATALOG.get(ns, "")
        if not catalog_ns:
            raise AttributeError(name)  # indicator / info 等聚合层不提供目录委托
        qualified = f"{catalog_ns}.{name}"
        try:
            meta = client.catalog.function(qualified)
        except Exception:
            raise AttributeError(
                f"{type(self).__name__!s}.{name} 不存在；请查目录："
                f"cat.search({name!r}) 或 docs/API.md") from None
        params = meta.get("params") or client.catalog.inventory_params(qualified)
        param_names = [p["name"] for p in params]
        call = client.call

        def _delegate(*args: Any, **kwargs: Any) -> Any:
            if len(args) > len(param_names):
                raise UsageError(
                    f"{qualified}: 最多接受 {len(param_names)} 个位置参数，"
                    f"收到 {len(args)} 个；参数顺序 {param_names}", code="params")
            bound = dict(kwargs)
            for pname, value in zip(param_names, args):
                if pname in bound:
                    raise UsageError(
                        f"{qualified}: 参数 {pname!r} 同时以位置和关键字传入",
                        code="params")
                bound[pname] = value
            return call(qualified, **bound)

        _delegate.__name__ = name
        _delegate.__qualname__ = f"{type(self).__name__}.{name}"
        return _delegate


# ---------------------------------------------------------------- 行情 market
class KlineApi(_Api):
    """行情与 K 线。单位：价格=元，量=手(A股)，额=本币，涨跌幅=小数（0.01=1%）。"""

    def bars(self, symbol: str, n: int | None = None, adj: str | None = None,
             begin: str | None = None, end: str | None = None,
             _raw: bool = False, _df: bool = False) -> Any:
        """日 K 序列（date/open/high/low/close/volume/amount/percent）。

        覆盖自上市首日起的全部交易日（最早 1991 年）。

        :param n: 根数，默认 120；区间查询时默认取 max_limit（上限 10000）
        :param adj: None=不复权；"qfq"=前复权；"hfq"=后复权
        :param begin: 起始日期（含，YYYY-MM-DD），须与 end 同时提供；区间上限 5 年
        :param end: 结束日期（含）
        """
        if begin is not None or end is not None:
            if not (begin and end):
                raise UsageError("begin 与 end 需同时提供", code="range")
            if _raw:
                raise UsageError("_raw=True 时不支持 begin/end（原始行无扁平日期字段）",
                                 code="range")
            limit = min(int(n) if n is not None else (self._c.max_limit or 10000), 10000)
            fn = "kline.query_bars" if adj is None else "kline.query_bars_adj"
            kwargs: dict[str, Any] = {"sym": symbol, "limit": limit, "_raw": _raw}
            if adj is not None:
                kwargs["adj"] = adj
            rows = self._c.call(fn, **kwargs)
            out = _filter_by_date(rows, begin, end, "date", limit)
            return _to_df(out) if _df else out
        limit = 120 if n is None else n
        if adj is None:
            return self._c.call("kline.query_bars", sym=symbol, limit=limit,
                                _raw=_raw, _df=_df)
        return self._c.call("kline.query_bars_adj", sym=symbol, limit=limit, adj=adj,
                            _raw=_raw, _df=_df)

    def last(self, symbol: str, _raw: bool = False) -> Any:
        """最新一根日 K（date/open/high/low/close/volume/amount/percent），无数据返回 None。

        经规范化序列取最新一行，字段与 ``bars()`` 一致；``_raw=True`` 时跳过规范化，
        返回 store 原始行（字段名不同，含 CreatedAt/sampling 等）。
        """
        rows = self._c.call("kline.query_bars", sym=symbol, limit=1, _raw=_raw)
        return rows[0] if rows else None

    def live(self, symbol: str, _raw: bool = False) -> Any:
        """盘中最新快照（盘中 tip；休市返回最近收盘快照）。"""
        return self._c.call("kline.query_last_live", sym=symbol, _raw=_raw)

    def batch_live(self, symbols: list[str], _raw: bool = False) -> dict:
        """多标的盘中快照（单次请求，返回 {symbol: bar}）。

        :param symbols: 标的列表（自动去重与归一）
        """
        return self._c.call("kline.query_last_live_many", syms=symbols, _raw=_raw)

    def min1(self, symbol: str) -> Any:
        """当日 1 分钟分时（有损合成采样，非逐笔；休市返回上一交易日）。"""
        return self._c.call("kline.query_min1_live", sym=symbol)

    def snapshot(self, symbol: str) -> Any:
        """行情摘要（symbol/close/percent/chg_20d）。"""
        return self._c.call("kline.snapshot", sym=symbol)

    def is_etf(self, symbol: str) -> bool:
        """是否场内 ETF。"""
        return bool(self._c.call("kline.is_etf", sym=symbol))


class MoneyflowApi(_Api):
    """资金流向（日频：主力/超大单/大单/中单/小单净流入，单位=元；非逐笔 Level2）。"""

    def bars(self, symbol: str, n: int | None = None,
             begin: str | None = None, end: str | None = None,
             _raw: bool = False, _df: bool = False) -> Any:
        """资金流历史（date/net_mf/elg_net/lg_net/md_net/sm_net）。

        :param n: 条数，默认 20；区间查询时默认取 max_limit（上限 10000）
        :param begin: 起始日期（含，YYYY-MM-DD），须与 end 同时提供；区间上限 5 年
        :param end: 结束日期（含）
        """
        if begin is not None or end is not None:
            if not (begin and end):
                raise UsageError("begin 与 end 需同时提供", code="range")
            if _raw:
                raise UsageError("_raw=True 时不支持 begin/end（原始行无扁平日期字段）",
                                 code="range")
            limit = min(int(n) if n is not None else (self._c.max_limit or 10000), 10000)
            rows = self._c.call("moneyflow.query_bars", sym=symbol, limit=limit, _raw=_raw)
            out = _filter_by_date(rows, begin, end, "date", limit)
            return _to_df(out) if _df else out
        limit = 20 if n is None else n
        return self._c.call("moneyflow.query_bars", sym=symbol, limit=limit,
                            _raw=_raw, _df=_df)

    def last(self, symbol: str, _raw: bool = False) -> Any:
        """最新一行资金流（date/net_mf/elg_net/lg_net/md_net/sm_net），无数据返回 None。

        经规范化序列取最新一行，字段与 ``bars()`` 一致；``_raw=True`` 时返回 store
        原始行（净流入嵌在 props 下）。
        """
        rows = self._c.call("moneyflow.query_bars", sym=symbol, limit=1, _raw=_raw)
        return rows[0] if rows else None

    def live(self, symbol: str, _raw: bool = False) -> Any:
        """盘中资金流快照（短 TTL）；数据源暂无快照时返回 None。"""
        return self._c.call("moneyflow.query_last_live", sym=symbol, _raw=_raw)


# ---------------------------------------------------------------- 选股 market
class ScreenerApi(_Api):
    """选股与全景：单票筛选器（bool）+ 全市场涨跌宽度（服务端预计算索引直出）。

    筛选阈值统一**小数**（0.10 = 10%）；事件筛选以「当日有成交」为前置
    （停牌恒 False）。全市场四件套（全景/分桶/行业分布/涨跌榜）由服务端索引
    聚合直出、免本地计算；``idx`` 不传时由服务端解析 A 股最新查询索引。
    口径注记：宽度返回中 ``up_pct``/``down_pct``/``flat_pct`` 与分桶
    ``pct_of_total`` 为百分数数值（52.3 = 52.3%），``median_pct`` 与涨跌幅为
    小数（0.01 = 1%）。kline 目录的其余筛选函数经属性直达
    （如 ``cli.screener.screen_up_today("600519")``），``cat.search("screen")``
    可查全部；股息质量筛选器见 ``cli.dividend.screen_*``。
    """

    # ---- 单票事件筛选 ----
    def screen_limit_up(self, symbol: str) -> bool:
        """今日涨停（涨幅 > 0.10；停牌返回 False）。"""
        return bool(self._c.call("kline.screen_limit_up", sym=symbol))

    def screen_limit_down(self, symbol: str) -> bool:
        """今日跌停（涨幅 < -0.10；停牌返回 False）。"""
        return bool(self._c.call("kline.screen_limit_down", sym=symbol))

    # ---- 单票均线/量能/动量筛选 ----
    def screen_above_ma20(self, symbol: str) -> bool:
        """收盘价站上 MA20（60/120 日线变体经属性直达 screen_above_ma60/ma120）。"""
        return bool(self._c.call("kline.screen_above_ma20", sym=symbol))

    def screen_ma60_up(self, symbol: str) -> bool:
        """MA60 上行（中期趋势向上）。"""
        return bool(self._c.call("kline.screen_ma60_up", sym=symbol))

    def screen_breakout_ma20(self, symbol: str) -> bool:
        """突破 MA20（站上 MA20 且 MA60 上行的组合确认）。"""
        return bool(self._c.call("kline.screen_breakout_ma20", sym=symbol))

    def screen_momentum_20d(self, symbol: str, min_chg: float = 0.10) -> bool:
        """近 20 日涨幅达标（动量强）。

        :param min_chg: 20 日累计涨幅下限（小数，0.10 = 10%）
        """
        return bool(self._c.call("kline.screen_momentum_20d", sym=symbol, min_chg=min_chg))

    def screen_pullback_20d(self, symbol: str, min_chg: float = -0.10) -> bool:
        """近 20 日涨幅低于上限（回撤/未过热）。

        :param min_chg: 20 日累计涨幅的**上限**（小数）：默认 -0.10（近 20 日
            跌超 10%，深度回撤）；传 0.10 表示剔除已涨超 10% 的标的
        """
        return bool(self._c.call("kline.screen_pullback_20d", sym=symbol, min_chg=min_chg))

    def screen_volume_spike(self, symbol: str, min_ratio: float = 1.5) -> bool:
        """放量（5 日量比超阈值）。

        :param min_ratio: 量比下限，默认 1.5（5 日均量的 1.5 倍）
        """
        return bool(self._c.call("kline.screen_volume_spike", sym=symbol,
                                 min_ratio=min_ratio))

    # ---- 全市场宽度（服务端索引直出，免本地计算）----
    # idx 不传时由服务端解析最新 A 股查询索引（LatestIndexKey，动态 cache_key，
    # 无稳定字面量——不要臆造 "index.cn.all" 之类的键，实测 500）。
    def _breadth(self, fn: str, idx: str | None, _df: bool) -> Any:
        if idx is None:
            rows = self._c.eval_result(f"return {fn}(LatestIndexKey())")
        else:
            rows = self._c.call(fn, idx=idx)
        return _to_df(rows) if _df else rows

    def index_breadth_summary(self, idx: str | None = None) -> dict:
        """全市场涨跌全景（上涨/下跌/平盘家数、占比与涨跌幅中位数）。

        :param idx: 服务端索引键（高级；默认不传 = A 股最新查询索引）
        """
        return self._breadth("kline.index_breadth_summary", idx, _df=False)

    def index_breadth_bins(self, idx: str | None = None, _df: bool = False) -> Any:
        """涨跌幅 9 档分桶（涨停/±5%/±3%/平盘/…/跌停），行含 label/count/pct_of_total。

        :param idx: 服务端索引键（高级；默认不传 = A 股最新查询索引）
        """
        return self._breadth("kline.index_breadth_bins", idx, _df)

    def index_breadth_bin_industries(self, idx: str | None = None,
                                     _df: bool = False) -> Any:
        """涨跌幅分桶 × 一级行业分布（行含 bin/industry/count）。

        :param idx: 服务端索引键（高级；默认不传 = A 股最新查询索引）
        """
        return self._breadth("kline.index_breadth_bin_industries", idx, _df)

    def index_top_movers(self, limit: int = 20, desc: bool = True,
                         idx: str | None = None, _df: bool = False) -> Any:
        """涨跌榜（按当日涨跌幅排序，行含 symbol/name/percent；percent 为小数）。

        :param limit: 条数，默认 20；受 Client(max_limit=...) 与单次 10000 行硬上限钳制
        :param desc: true=涨幅榜（默认）；false=跌幅榜
        :param idx: 服务端索引键（高级；默认不传 = A 股最新查询索引）
        """
        cap = min(self._c.max_limit or 10000, 10000)
        if limit > cap:
            raise LimitError(
                f"index_top_movers: limit={limit} 超过单次上限 {cap}"
                "（防止单次拉取过大；可在 Client(max_limit=...) 调整，设 None 关闭）",
                code="limit")
        if idx is None:
            xs = (f"return kline.index_top_movers(LatestIndexKey(), {int(limit)}, "
                  f"{'true' if desc else 'false'})")
            rows = self._c.eval_result(xs)
        else:
            rows = self._c.call("kline.index_top_movers", idx=idx, limit=limit, desc=desc)
        return _to_df(rows) if _df else rows


# ---------------------------------------------------------------- 财务 fundamentals
class StatementsApi(_Api):
    """三大报表科目透视（披露原值；金额=报表原币）。

    各方法返回科目行列表（科目代码/中文名 × 期次列）；树视图另含派生比率行。
    ``kind`` 取值：``balance``（资产负债）/``income``（利润）/``cashflow``（现金流）。

    :param years: 期数（年报降序，默认 5）
    :param scope: "合并"（默认）或 "母公司"
    """

    _DOMAINS = {"balance": "fin.balance_sheet",
                "income": "fin.income_statement",
                "cashflow": "fin.cashflow_statement"}

    @classmethod
    def _domain(cls, kind: str) -> str:
        try:
            return cls._DOMAINS[kind]
        except KeyError:
            raise UsageError(f"未知报表 kind={kind!r}；可选 {sorted(cls._DOMAINS)}",
                             code="params") from None

    def balance(self, symbol: str, years: int = 5, scope: str = "合并",
                _raw: bool = False, _df: bool = False) -> Any:
        """资产负债表（fin.balance_sheet）。"""
        return self._c.call("rptdom.statement", sym=symbol, domain="fin.balance_sheet",
                            opts={"scope": scope, "n": years}, _raw=_raw, _df=_df)

    def income(self, symbol: str, years: int = 5, scope: str = "合并",
               _raw: bool = False, _df: bool = False) -> Any:
        """利润表（fin.income_statement，含费用四率原料行）。"""
        return self._c.call("rptdom.statement", sym=symbol, domain="fin.income_statement",
                            opts={"scope": scope, "n": years}, _raw=_raw, _df=_df)

    def cashflow(self, symbol: str, years: int = 5, scope: str = "合并",
                 _raw: bool = False, _df: bool = False) -> Any:
        """现金流量表（fin.cashflow_statement）。"""
        return self._c.call("rptdom.statement", sym=symbol, domain="fin.cashflow_statement",
                            opts={"scope": scope, "n": years}, _raw=_raw, _df=_df)

    def compare(self, symbol: str, kind: str = "income", years: int = 2,
                _raw: bool = False, _df: bool = False) -> Any:
        """合并 vs 母公司比较：科目行 + 合并值/母公司值/差额/差额占比。

        差额占比为**小数**（diffp = 差额 / 合并值，0.078 = 7.8%；SDK 自动由脚本
        的百分数口径换算，``_units="native"`` 可取原值）；母公司未披露的科目差额为空。
        """
        return self._c.call("rptdom.statement_compare", sym=symbol,
                            domain=self._domain(kind), opts={"n": years},
                            _raw=_raw, _df=_df)

    def tree(self, symbol: str, kind: str = "balance", years: int = 5,
             scope: str = "合并", _raw: bool = False, _df: bool = False) -> Any:
        """报表目录树视图：按树序输出科目行，含派生比率行（流动比率/资产负债率/毛利率等）。

        注意：派生行的数值口径按行内标记区分——``pct`` 行的 vals 为百分数（原生，
        未换算）、``fmt="x"`` 行为倍数、其余科目行为报表原币元；与 compare() 的统一
        小数口径不同，树视图适合展示/核对而非跨接口运算。
        """
        return self._c.call("rptdom.statement_tree", sym=symbol,
                            domain=self._domain(kind), opts={"scope": scope, "n": years},
                            _raw=_raw, _df=_df)

    def years(self, symbol: str, kind: str = "income", _df: bool = False) -> Any:
        """该报表可用的年报年份（降序）。"""
        return self._c.call("rptdom.statement_years", sym=symbol,
                            domain=self._domain(kind), _df=_df)

    def audit(self, symbol: str) -> Any:
        """审计意见（按年报，返回 {年份: 意见}）。"""
        return self._c.call("rptdom.statement_audit", sym=symbol)


class SegmentsApi(_Api):
    """经营分部：主营构成的多维分解（分产品 / 分业务 / 分区域 / 主营标签占比）。

    行结构统一 ``{name, tr, tr_text, cost, margin, ratio}``：收入/成本为**元**，
    毛利率与占比为**小数**（margin = (tr-cost)/tr，0.332 = 33.2%）；ratio 仅主营
    标签维填充、其余维为 0 占位。数据来自定期报告分部披露的平台清洗归一（clean
    口径，默认）；各维披露覆盖度先用 coverage() 探明。

    :param source: "clean"（默认，清洗归一）或 "raw"（披露明细）
    """

    def products(self, symbol: str, source: str = "clean", limit: int = 20,
                 _df: bool = False) -> Any:
        """分产品/商品收入构成（行按收入降序）。"""
        return self._c.call("segments.query_products", sym=symbol,
                            opts={"source": source, "limit": limit}, _df=_df)

    def business(self, symbol: str, source: str = "clean", limit: int = 20,
                 _df: bool = False) -> Any:
        """分业务线收入构成（行按收入降序）。"""
        return self._c.call("segments.query_business", sym=symbol,
                            opts={"source": source, "limit": limit}, _df=_df)

    def region(self, symbol: str, source: str = "clean", limit: int = 20,
               _df: bool = False) -> Any:
        """境内外分部。clean 口径返回 MAP（domestic/overseas 各含 tr/pct/margin/yoy），
        source="raw" 返回披露明细 ARR；无分部披露时为 None。"""
        return self._c.call("segments.query_region", sym=symbol,
                            opts={"source": source, "limit": limit}, _df=_df)

    def income(self, symbol: str, limit: int = 20, _df: bool = False) -> Any:
        """主营标签占比（name + ratio 小数；tr/cost 恒 0，margin 为 None）。"""
        return self._c.call("segments.query_income", sym=symbol,
                            opts={"limit": limit}, _df=_df)

    def snapshot(self, symbol: str, source: str = "clean", _df: bool = False) -> Any:
        """四维合并快照：{overview, income, region, product, business, coverage}。"""
        return self._c.call("segments.snapshot", sym=symbol,
                            opts={"source": source}, _df=_df)

    def coverage(self, symbol: str) -> Any:
        """各维是否有数据（has_income/has_region/has_products/has_business 布尔）。"""
        return self._c.call("segments.coverage", sym=symbol)

    def periods(self, symbol: str) -> Any:
        """清洗口径可用报告期（{clean_last, clean_last_q4}）。"""
        return self._c.call("segments.list_sas", sym=symbol)


class ValuationApi(_Api):
    """估值历史统计（与平台 web「估值通道」取数同源，宿主函数 HIST_STATS）。

    返回窗口内每日估值序列与统计量：``{avg, current, median, min, max, pct,
    count, series}``——pct 为当前值的历史分位（小数，0.42 = 42% 分位）；
    series 为 ``[[unix 秒, 值], ...]`` 升序；引擎不返回 stddev，需要通道带宽时
    由调用方按总体口径（÷N）自算。
    口径注记：亏损期 PE 无数据、净资产为负期间不参与统计（与平台免责一致）。
    """

    _METRICS = {"pe": "pe", "pb": "pb", "ps": "ps", "pr": "pr_base"}
    # 引擎支持 <数字><单位> 通用窗口（实测 6m 起可用）；上限 3 年
    _WINDOWS = ("6m", "1y", "2y", "3y")

    def hist_stats(self, symbol: str, metric: str = "pe", window: str = "3y") -> dict:
        """估值指标的历史统计与每日序列（PE=TTM 口径；pr=市赚率 pr_base）。

        :param metric: "pe" / "pb" / "ps" / "pr"
        :param window: "6m" / "1y" / "2y" / "3y"（上限 3 年）
        """
        if metric not in self._METRICS:
            raise UsageError(
                f"metric 只支持 {sorted(self._METRICS)}（pe=市盈率TTM、pb=市净率、"
                "ps=市销率、pr=市赚率；金融/亏损股建议用 pb）", code="params")
        if window not in self._WINDOWS:
            raise UsageError(
                f"window 只支持 {list(self._WINDOWS)}（上限 3 年）", code="params")
        return self._c.eval_result(
            f'return HIST_STATS("{window}", "{self._METRICS[metric]}")', symbol=symbol)


class IndicatorApi(_Api):
    """平台指标（按指标代码寻址）。

    单位统一为基础单位：比率类为小数（ROE 0.332 = 33.2%）、金额/市值为元、
    分位为小数（0.42 = 42% 分位）；精选组声明过 range 的指标在返回前做量级守护
    （违例抛 DataError）。非精选代码按脚本原值返回（目录未声明单位的代码不做换算）。
    """

    def get(self, symbol: str, code: str) -> Any:
        """取单个指标当前值，如 cli.indicator.get("600519", "$PE_TTM_LAST")。"""
        meta = self._c.catalog.metric_meta(code)
        if meta is None and self._c.catalog.metric(code) is None:
            raise CatalogError(f"未知指标 {code!r}（防编造：code 必须在指标目录内）",
                               code="metric")
        value = self._c.eval_result(f"return {code}", symbol=symbol)
        return finish_metric(value, meta, code=code, validate=self._c._validate)

    def metrics(self, symbol: str, codes: list[str]) -> dict:
        """批量取多个指标当前值，返回 {code: value}（精选代码带换算与量级守护）。"""
        missing = [c for c in codes if self._c.catalog.metric(c) is None]
        if missing:
            raise CatalogError(f"未知指标 {missing}（防编造：code 必须在指标目录内）",
                               code="metric")
        body = ", ".join(f'"{c}": {c}' for c in codes)
        values = self._c.eval_result(f"return {{{body}}}", symbol=symbol) or {}
        if not isinstance(values, dict):  # 上游恒返回 MAP；异常形态原样透传
            return values
        return {c: finish_metric(v, self._c.catalog.metric_meta(c), code=c,
                                 validate=self._c._validate)
                for c, v in values.items()}


# ---------------------------------------------------------------- 披露 disclosure
class NoticeApi(_Api):
    """公告检索与信号。window 枚举 "7d"/"1m"/"3m"/"6m"/"1y"/"3y"/"5y" 或天数整数；keyword 为标题/类型正则（可空）。"""

    def list(self, symbol: str, window: str = "3m", keyword: str = "",
             limit: int = 20, _raw: bool = False, _df: bool = False) -> Any:
        """单票公告列表（date/title/type/url/pdf_url）。"""
        days = _window_days(window)
        return self._c.call("notice.query_by_symbol", sym=symbol, window=str(days),
                            type_regex=keyword, limit=limit, _raw=_raw, _df=_df)

    def recent(self, window: str = "7d", keyword: str = "", limit: int = 50,
               _raw: bool = False, _df: bool = False) -> Any:
        """全市场近期公告（按披露时间倒序）。

        :param window: 时间窗口，如 "7d"/"1m" 或天数
        :param keyword: 标题/类型正则（可空）
        """
        days = _window_days(window)
        return self._c.call("notice.query_recent", window=str(days), type_regex=keyword,
                            limit=limit, _raw=_raw, _df=_df)

    def by_category(self, category: str, window: str = "1m", limit: int = 20,
                    _raw: bool = False, _df: bool = False) -> Any:
        """按类别查公告（如 "回购"）。"""
        days = _window_days(window)
        return self._c.call("notice.query_by_category", category=category,
                            window=str(days), limit=limit, _raw=_raw, _df=_df)

    def find(self, symbol: str, begin: str, end: str, keyword: str = "",
             limit: int = 50, _raw: bool = False, _df: bool = False) -> Any:
        """按日期区间查单票公告（begin/end 均含当日，格式 YYYY-MM-DD）。

        :param begin: 起始日期（含）
        :param end: 结束日期（含）
        :param keyword: 标题/类型正则（可空）
        """
        return self._c.call("notice.query_find", from_date=begin, to_date=end,
                            type_regex=keyword, stock_code=symbol, limit=limit,
                            _raw=_raw, _df=_df)

    def on_date(self, date: str, keyword: str = "", limit: int = 50,
                _raw: bool = False, _df: bool = False) -> Any:
        """指定日期的全市场公告（date 格式 YYYY-MM-DD）。"""
        return self._c.call("notice.query_on_date", date=date, type_regex=keyword,
                            limit=limit, _raw=_raw, _df=_df)

    def has_buyback(self, symbol: str, window: str = "6m") -> bool:
        """窗口内是否有回购公告。"""
        return bool(self._c.call("notice.signal_has_buyback", sym=symbol,
                                 window=str(_window_days(window))))

    def has_reduction(self, symbol: str, window: str = "6m") -> bool:
        """窗口内是否有减持公告。"""
        return bool(self._c.call("notice.signal_has_reduction", sym=symbol,
                                 window=str(_window_days(window))))


class FilingsApi(_Api):
    """定期报告清单。kind = all | annual | semi | quarter。"""

    def list(self, symbol: str, kind: str = "all", limit: int = 10,
             _df: bool = False) -> Any:
        """定期报告列表（报告期/标题/PDF 链接）。"""
        return self._c.call("filings.query", sym=symbol, type_key=kind, limit=limit, _df=_df)

    def latest(self, symbol: str, kind: str = "all") -> Any:
        """最新一条定期报告。"""
        return self._c.call("filings.latest", sym=symbol, type_key=kind)


class ForecastApi(_Api):
    """业绩预告 / 快报 / 披露日历（正式报表发布前的披露文件结构化）。"""

    def yjyg(self, symbol: str, limit: int = 8, _df: bool = False) -> Any:
        """业绩预告历史（净利/扣非/营收区间 + 同比 + 修正轨迹）。"""
        return self._c.call("forecast.yjyg_rows", sym=symbol, limit=limit, _df=_df)

    def yjyg_latest(self, symbol: str) -> Any:
        """最新业绩预告。"""
        return self._c.call("forecast.yjyg_latest", sym=symbol)

    def yjkb(self, symbol: str, limit: int = 8, _df: bool = False) -> Any:
        """业绩快报历史。"""
        return self._c.call("forecast.yjkb_rows", sym=symbol, limit=limit, _df=_df)

    def yjkb_latest(self, symbol: str) -> Any:
        """最新业绩快报。"""
        return self._c.call("forecast.yjkb_latest", sym=symbol)

    def disclosure_history(self, symbol: str, limit: int = 8, _df: bool = False) -> Any:
        """历史财报预约披露（报告期/计划披露日/实际日）。"""
        return self._c.call("forecast.disclosure_rows", sym=symbol, limit=limit, _df=_df)

    def next_disclosure(self, symbol: str) -> Any:
        """下次财报预约披露。"""
        return self._c.call("forecast.disclosure_next", sym=symbol)


class DividendApi(_Api):
    """分红。DPS 单位=元/股；股息率/派息率为小数（0.0396 = 3.96%）。

    除下方动宾化方法外，目录内全部 ``bonus.*`` 函数（含质量筛选器
    ``screen_quality`` / ``screen_high_yield`` / ``screen_undervalued_yield``…）
    经属性直达，如 ``cli.dividend.screen_quality("600519")``。
    """

    # 常用筛选器提为显式方法（docstring 在 IDE 可见；底层合同与目录一致）
    def screen_quality(self, symbol: str, min_yield: float | None = None,
                       payout_min: float | None = None,
                       payout_max: float | None = None, _raw: bool = False,
                       _df: bool = False) -> Any:
        """分红质量优（高股息 + 派息可持续，阈值可调）。

        :param min_yield: 最低股息率（小数，如 0.03 = 3%）
        :param payout_min: 派息率下限（小数）
        :param payout_max: 派息率上限（小数）
        """
        kw: dict[str, Any] = {"sym": symbol}
        if min_yield is not None:
            kw["min_yield"] = min_yield
        if payout_min is not None:
            kw["payout_min"] = payout_min
        if payout_max is not None:
            kw["payout_max"] = payout_max
        return self._c.call("bonus.screen_quality", **kw, _raw=_raw, _df=_df)

    def screen_high_yield(self, symbol: str, min_yield: float | None = None,
                          _raw: bool = False, _df: bool = False) -> Any:
        """高股息（min_yield 为小数，如 0.04 = 4%）。"""
        kw: dict[str, Any] = {"sym": symbol}
        if min_yield is not None:
            kw["min_yield"] = min_yield
        return self._c.call("bonus.screen_high_yield", **kw, _raw=_raw, _df=_df)

    def screen_undervalued_yield(self, symbol: str, min_yield: float | None = None,
                                 min_pct: float | None = None, _raw: bool = False,
                                 _df: bool = False) -> Any:
        """低估 + 高股息（min_yield 为小数；min_pct 为低估值百分位门槛）。"""
        kw: dict[str, Any] = {"sym": symbol}
        if min_yield is not None:
            kw["min_yield"] = min_yield
        if min_pct is not None:
            kw["min_pct"] = min_pct
        return self._c.call("bonus.screen_undervalued_yield", **kw, _raw=_raw, _df=_df)

    def history(self, symbol: str, limit: int | None = None,
                begin: str | None = None, end: str | None = None,
                _raw: bool = False, _df: bool = False) -> Any:
        """分红历史明细（announce/ex_date/pay/dps/total/content/sas/payout_ratio）。

        :param limit: 条数，默认 20；区间查询时默认取 max_limit（上限 10000）
        :param begin: 起始日期（含，YYYY-MM-DD，按除权日），须与 end 同时提供；上限 5 年
        :param end: 结束日期（含）
        """
        if begin is not None or end is not None:
            if not (begin and end):
                raise UsageError("begin 与 end 需同时提供", code="range")
            if _raw:
                raise UsageError("_raw=True 时不支持 begin/end（原始行无扁平日期字段）",
                                 code="range")
            fetch = min(int(limit) if limit is not None else (self._c.max_limit or 10000),
                        10000)
            rows = self._c.call("bonus.query_list", sym=symbol, limit=fetch)
            out = _filter_by_date(rows, begin, end, "ex_div", fetch)
            return _to_df(out) if _df else out
        limit = 20 if limit is None else limit
        return self._c.call("bonus.query_list", sym=symbol, limit=limit,
                            _raw=_raw, _df=_df)

    def last(self, symbol: str, _raw: bool = False) -> Any:
        """最近一次分红（announce/ex_date/pay/dps/total/content/sas/payout_ratio），无数据返回 None。

        复用规范化历史序列取最新一行，字段与 ``history(limit=1)[0]`` 一致；
        ``_raw=True`` 时返回 store 原始行。
        """
        rows = self._c.call("bonus.query_list", sym=symbol, limit=1, _raw=_raw)
        return rows[0] if rows else None

    def dps(self, symbol: str) -> Any:
        """财报期每股分红（元/股）。"""
        return self._c.call("bonus.dps_rpt", sym=symbol)

    def window_stats(self, symbol: str, window: str = "3y") -> dict:
        """窗口统计（单次请求）：{"dps": 每股股利合计(元/股), "total": 总分红(元), "count": 次数}。

        窗口按**除权日**计、截至今天；命名窗口仅支持 7d/1m/3m/6m/1y/3y/5y（最大 5 年）
        或正整数天数。count 由 SDK 从规范化历史行统计——上游 count 聚合存在缺陷
        （同窗口 sum 正常、count 恒 0），故不经上游 count。

        :param window: 窗口字符串，如 "3y"/"5y"
        """
        days = _window_days(window)
        limit = min(self._c.max_limit or 10000, 10000)
        s = json.dumps(symbol, ensure_ascii=False)
        w = json.dumps(str(window), ensure_ascii=False)
        xs = (f"__r := bonus.query_list({s}, {limit})\n"
              f"__rows := bonus.fmt_maps(__r)\n"
              f'return {{"rows": __rows, '
              f'"dps": bonus.query_dps_window({s}, {w}), '
              f'"total": bonus.query_total_window({s}, {w})}}')
        res = self._c.eval_result(xs, symbol=symbol) or {}
        if not isinstance(res, dict):
            raise CatalogError(
                f"window_stats: 返回不是 MAP（{type(res).__name__}）", code="shape")
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        rows = res.pop("rows", []) or []
        count = sum(1 for r in rows if isinstance(r, dict)
                    and str(r.get("ex_div") or r.get("ex_date") or "")[:10] >= cutoff)
        return {"dps": res.get("dps"), "total": res.get("total"), "count": count}

    def yield_ttm(self, symbol: str) -> Any:
        """TTM 股息率（小数，0.0396 = 3.96%；= TTM 分红总额 / 最新市值）。"""
        return self._c.call("bonus.snapshot_yield_ttm", sym=symbol)

    def payout_ttm(self, symbol: str) -> Any:
        """TTM 派息率（小数，0.799 = 79.9%；= TTM 分红 / 归母净利 TTM）。"""
        return self._c.call("bonus.snapshot_payout_ttm", sym=symbol)


# ---------------------------------------------------------------- 参考 reference
class InfoApi(_Api):
    """公司档案与参考信息。"""

    _PROFILE_CODES = ["$NAME", "$INDUSTRY_CUR", "$STYLE_INDUSTRY",
                      "$ORG_ORGTYPE", "$ORG_LISTINGDATE"]
    _PROFILE_KEYS = ["name", "industry", "style_industry", "org_type", "listing_date"]

    def profile(self, symbol: str) -> dict:
        """公司档案摘要（名称/行业/组织类型/上市日期）。"""
        body = ", ".join(f'"{k}": {c}' for k, c in
                         zip(self._PROFILE_KEYS, self._PROFILE_CODES))
        return self._c.eval_result(f"return {{{body}}}", symbol=symbol) or {}


FRIENDLY_NAMESPACES: dict[str, type[_Api]] = {
    "kline": KlineApi,
    "screener": ScreenerApi,
    "moneyflow": MoneyflowApi,
    "statements": StatementsApi,
    "segments": SegmentsApi,
    "valuation": ValuationApi,
    "indicator": IndicatorApi,
    "notice": NoticeApi,
    "filings": FilingsApi,
    "forecast": ForecastApi,
    "dividend": DividendApi,
    "info": InfoApi,
}

# 文档索引用注册表：(category, namespace, method, cn, 底层函数)
FRIENDLY_INDEX: list[tuple[str, str, str, str, str]] = [
    ("market", "kline", "bars", "日 K 序列", "kline.query_bars[_adj]"),
    ("market", "kline", "last", "最新一根日 K", "kline.query_bars"),
    ("market", "kline", "live", "盘中最新快照", "kline.query_last_live"),
    ("market", "kline", "batch_live", "多标的盘中快照", "kline.query_last_live_many"),
    ("market", "kline", "min1", "当日 1 分钟分时", "kline.query_min1_live"),
    ("market", "kline", "snapshot", "行情摘要", "kline.snapshot"),
    ("market", "kline", "is_etf", "是否场内 ETF", "kline.is_etf"),
    ("market", "moneyflow", "bars", "资金流历史", "moneyflow.query_bars"),
    ("market", "moneyflow", "last", "最新资金流", "moneyflow.query_bars"),
    ("market", "moneyflow", "live", "盘中资金流快照", "moneyflow.query_last_live"),
    ("market", "screener", "screen_limit_up", "今日涨停筛选", "kline.screen_limit_up"),
    ("market", "screener", "screen_limit_down", "今日跌停筛选", "kline.screen_limit_down"),
    ("market", "screener", "screen_above_ma20", "站上 MA20 筛选", "kline.screen_above_ma20"),
    ("market", "screener", "screen_ma60_up", "MA60 上行筛选", "kline.screen_ma60_up"),
    ("market", "screener", "screen_breakout_ma20", "突破 MA20 筛选", "kline.screen_breakout_ma20"),
    ("market", "screener", "screen_momentum_20d", "20 日动量筛选", "kline.screen_momentum_20d"),
    ("market", "screener", "screen_pullback_20d", "20 日回撤筛选", "kline.screen_pullback_20d"),
    ("market", "screener", "screen_volume_spike", "放量筛选", "kline.screen_volume_spike"),
    ("market", "screener", "index_breadth_summary", "全市场涨跌全景",
     "kline.index_breadth_summary"),
    ("market", "screener", "index_breadth_bins", "涨跌幅分桶", "kline.index_breadth_bins"),
    ("market", "screener", "index_breadth_bin_industries", "分桶行业分布",
     "kline.index_breadth_bin_industries"),
    ("market", "screener", "index_top_movers", "涨跌榜", "kline.index_top_movers"),
    ("fundamentals", "statements", "balance", "资产负债表", "rptdom.statement"),
    ("fundamentals", "statements", "income", "利润表", "rptdom.statement"),
    ("fundamentals", "statements", "cashflow", "现金流量表", "rptdom.statement"),
    ("fundamentals", "statements", "compare", "合并 vs 母公司比较", "rptdom.statement_compare"),
    ("fundamentals", "statements", "tree", "报表目录树视图", "rptdom.statement_tree"),
    ("fundamentals", "statements", "years", "报表可用年份", "rptdom.statement_years"),
    ("fundamentals", "statements", "audit", "审计意见", "rptdom.statement_audit"),
    ("fundamentals", "indicator", "get", "取单个指标", "指标代码直查"),
    ("fundamentals", "indicator", "metrics", "批量取指标", "指标代码批量直查"),
    ("fundamentals", "segments", "products", "分产品收入构成", "segments.query_products"),
    ("fundamentals", "segments", "business", "分业务收入构成", "segments.query_business"),
    ("fundamentals", "segments", "region", "境内外分部", "segments.query_region"),
    ("fundamentals", "segments", "income", "主营标签占比", "segments.query_income"),
    ("fundamentals", "segments", "snapshot", "分部截面快照", "segments.snapshot"),
    ("fundamentals", "segments", "coverage", "分部披露覆盖度", "segments.coverage"),
    ("fundamentals", "segments", "periods", "分部可用报告期", "segments.list_sas"),
    ("fundamentals", "valuation", "hist_stats", "估值历史统计", "组合接口（宿主 HIST_STATS）"),
    ("disclosure", "notice", "list", "单票公告列表", "notice.query_by_symbol"),
    ("disclosure", "notice", "recent", "全市场近期公告", "notice.query_recent"),
    ("disclosure", "notice", "by_category", "按类别查公告", "notice.query_by_category"),
    ("disclosure", "notice", "find", "按日期区间查公告", "notice.query_find"),
    ("disclosure", "notice", "on_date", "指定日期全市场公告", "notice.query_on_date"),
    ("disclosure", "notice", "has_buyback", "窗口内有回购", "notice.signal_has_buyback"),
    ("disclosure", "notice", "has_reduction", "窗口内有减持", "notice.signal_has_reduction"),
    ("disclosure", "filings", "list", "定期报告列表", "filings.query"),
    ("disclosure", "filings", "latest", "最新定期报告", "filings.latest"),
    ("disclosure", "forecast", "yjyg", "业绩预告历史", "forecast.yjyg_rows"),
    ("disclosure", "forecast", "yjyg_latest", "最新业绩预告", "forecast.yjyg_latest"),
    ("disclosure", "forecast", "yjkb", "业绩快报历史", "forecast.yjkb_rows"),
    ("disclosure", "forecast", "yjkb_latest", "最新业绩快报", "forecast.yjkb_latest"),
    ("disclosure", "forecast", "disclosure_history", "历史预约披露", "forecast.disclosure_rows"),
    ("disclosure", "forecast", "next_disclosure", "下次预约披露", "forecast.disclosure_next"),
    ("disclosure", "dividend", "history", "分红历史", "bonus.query_list"),
    ("disclosure", "dividend", "last", "最近一次分红", "bonus.query_list"),
    ("disclosure", "dividend", "dps", "财报期每股分红", "bonus.dps_rpt"),
    ("disclosure", "dividend", "window_stats", "窗口分红统计", "bonus.query_*_window"),
    ("disclosure", "dividend", "yield_ttm", "TTM 股息率", "bonus.snapshot_yield_ttm"),
    ("disclosure", "dividend", "payout_ttm", "TTM 派息率", "bonus.snapshot_payout_ttm"),
    ("disclosure", "dividend", "screen_quality", "分红质量优筛选", "bonus.screen_quality"),
    ("disclosure", "dividend", "screen_high_yield", "高股息筛选", "bonus.screen_high_yield"),
    ("disclosure", "dividend", "screen_undervalued_yield", "低估+高股息筛选",
     "bonus.screen_undervalued_yield"),
    ("reference", "info", "profile", "公司档案摘要", "档案指标（$NAME 等）"),
]

# 类型化门面（生成层）：目录命名空间的完整类型签名；运行时仍走 client.call()。
from finpipe.api._generated import NAMESPACES as GENERATED_NAMESPACES  # noqa: E402
