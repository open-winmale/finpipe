"""友好 API：按四大类组织的推荐入口（行情 / 财务 / 披露 / 参考）。

设计约定：
  - 参数统一 ``symbol``（6 位裸码；自动归一 cn./sh./sz./bj. 前缀与 .SH/.SZ/.BJ 后缀；
    港股 5 位、美股字母码）；
  - 方法名动宾化、可猜（bars/last/live/list/history/yield_ttm…）；
  - 返回 list[dict] / dict；返回列表的方法支持 ``_df=True`` 转 DataFrame，
    ``_raw=True`` 取未规范化原始行（仅部分方法）；
  - 本层只是目录合同的薄翻译，全量 155 个底层函数仍可经 ``client.call("ns.fn", ...)`` 调用。

使用：
    cli = finpipe.Client.from_env()
    cli.kline.bars("600519", n=30)
    cli.statements.income("600519", years=5)
    cli.notice.list("600519", window="3m")
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from finpipe.errors import CatalogError, UsageError

if TYPE_CHECKING:  # pragma: no cover
    from finpipe.client import Client


class _Api:
    def __init__(self, client: "Client"):
        self._c = client


# ---------------------------------------------------------------- 行情 market
class KlineApi(_Api):
    """行情与 K 线。单位：价格=元，量=手(A股)，额=本币，涨跌幅=小数（0.01=1%）。"""

    def bars(self, symbol: str, n: int = 120, adj: str | None = None,
             _raw: bool = False, _df: bool = False) -> Any:
        """日 K 序列（date/open/high/low/close/volume/amount/percent）。

        :param n: 根数，默认 120
        :param adj: None=不复权；"qfq"=前复权；"hfq"=后复权
        """
        if adj is None:
            return self._c.call("kline.query_bars", sym=symbol, limit=n,
                                _raw=_raw, _df=_df)
        return self._c.call("kline.query_bars_adj", sym=symbol, limit=n, adj=adj,
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

    def bars(self, symbol: str, n: int = 20, _raw: bool = False, _df: bool = False) -> Any:
        """资金流历史（date/net_mf/elg_net/lg_net/md_net/sm_net）。"""
        return self._c.call("moneyflow.query_bars", sym=symbol, limit=n,
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

        差额占比为**百分数**（差额 / 合并值 × 100）；母公司未披露的科目差额为空。
        """
        return self._c.call("rptdom.statement_compare", sym=symbol,
                            domain=self._domain(kind), opts={"n": years},
                            _raw=_raw, _df=_df)

    def tree(self, symbol: str, kind: str = "balance", years: int = 5,
             scope: str = "合并", _raw: bool = False, _df: bool = False) -> Any:
        """报表目录树视图：按树序输出科目行，含派生比率行（流动比率/资产负债率/毛利率等）。"""
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


class IndicatorApi(_Api):
    """平台指标（按指标代码寻址）。单位注意：比率类为百分数（15.0=15%），行情涨跌类为小数。"""

    def get(self, symbol: str, code: str) -> Any:
        """取单个指标当前值，如 cli.indicator.get("600519", "$PE_TTM_LAST")。"""
        if self._c.catalog.metric(code) is None:
            raise CatalogError(f"未知指标 {code!r}（防编造：code 必须在指标目录内）",
                               code="metric")
        return self._c.eval_result(f"return {code}", symbol=symbol)

    def metrics(self, symbol: str, codes: list[str]) -> dict:
        """批量取多个指标当前值，返回 {code: value}。"""
        missing = [c for c in codes if self._c.catalog.metric(c) is None]
        if missing:
            raise CatalogError(f"未知指标 {missing}（防编造：code 必须在指标目录内）",
                               code="metric")
        body = ", ".join(f'"{c}": {c}' for c in codes)
        return self._c.eval_result(f"return {{{body}}}", symbol=symbol) or {}


# ---------------------------------------------------------------- 披露 disclosure
class NoticeApi(_Api):
    """公告检索与信号。window 枚举 "7d"/"1m"/"3m"/"6m"/"1y"/"3y"/"5y" 或天数整数；keyword 为标题/类型正则（可空）。"""

    def list(self, symbol: str, window: str = "3m", keyword: str = "",
             limit: int = 20, _raw: bool = False, _df: bool = False) -> Any:
        """单票公告列表（日期/标题/类别/链接）。"""
        return self._c.call("notice.query_by_symbol", sym=symbol, window=window,
                            type_regex=keyword, limit=limit, _raw=_raw, _df=_df)

    def recent(self, window: str = "7d", keyword: str = "", limit: int = 50,
               _raw: bool = False, _df: bool = False) -> Any:
        """全市场近期公告（按披露时间倒序）。

        :param window: 时间窗口，如 "7d"/"1m" 或天数
        :param keyword: 标题/类型正则（可空）
        """
        return self._c.call("notice.query_recent", window=window, type_regex=keyword,
                            limit=limit, _raw=_raw, _df=_df)

    def by_category(self, category: str, window: str = "30d", limit: int = 20,
                    _df: bool = False) -> Any:
        """按类别查公告（如 "回购"）。"""
        return self._c.call("notice.query_by_category", category=category,
                            window=window, limit=limit, _df=_df)

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
                _df: bool = False) -> Any:
        """指定日期的全市场公告（date 格式 YYYY-MM-DD）。"""
        return self._c.call("notice.query_on_date", date=date, type_regex=keyword,
                            limit=limit, _df=_df)

    def has_buyback(self, symbol: str, window: str = "6m") -> bool:
        """窗口内是否有回购公告。"""
        return bool(self._c.call("notice.signal_has_buyback", sym=symbol, window=window))

    def has_reduction(self, symbol: str, window: str = "6m") -> bool:
        """窗口内是否有减持公告。"""
        return bool(self._c.call("notice.signal_has_reduction", sym=symbol, window=window))


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
    """分红。DPS 单位=元/股；股息率/派息率为小数（0.0396 = 3.96%）。"""

    def history(self, symbol: str, limit: int = 20, _raw: bool = False,
                _df: bool = False) -> Any:
        """分红历史明细（预案/除权除息日/每 10 股派息）。"""
        return self._c.call("bonus.query_list", sym=symbol, limit=limit,
                            _raw=_raw, _df=_df)

    def last(self, symbol: str) -> Any:
        """最近一次分红。"""
        return self._c.call("bonus.query_last", sym=symbol)

    def dps(self, symbol: str) -> Any:
        """财报期每股分红（元/股）。"""
        return self._c.call("bonus.dps_rpt", sym=symbol)

    def window_stats(self, symbol: str, window: str = "3y") -> dict:
        """窗口统计（单次请求）：{"dps": 每股股利合计(元/股), "total": 总分红(元)}。

        分红次数暂不返回：上游 count 聚合当前恒为 0（已记录，待上游修复）；
        需要次数时可用 ``history()`` 自行统计。

        :param window: 窗口字符串，如 "3y"/"5y"
        """
        s = json.dumps(symbol, ensure_ascii=False)
        w = json.dumps(window, ensure_ascii=False)
        body = (f'{{"dps": bonus.query_dps_window({s}, {w}), '
                f'"total": bonus.query_total_window({s}, {w})}}')
        return self._c.eval_result(f"return {body}", symbol=symbol) or {}

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
    "moneyflow": MoneyflowApi,
    "statements": StatementsApi,
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
    ("fundamentals", "statements", "balance", "资产负债表", "rptdom.statement"),
    ("fundamentals", "statements", "income", "利润表", "rptdom.statement"),
    ("fundamentals", "statements", "cashflow", "现金流量表", "rptdom.statement"),
    ("fundamentals", "statements", "compare", "合并 vs 母公司比较", "rptdom.statement_compare"),
    ("fundamentals", "statements", "tree", "报表目录树视图", "rptdom.statement_tree"),
    ("fundamentals", "statements", "years", "报表可用年份", "rptdom.statement_years"),
    ("fundamentals", "statements", "audit", "审计意见", "rptdom.statement_audit"),
    ("fundamentals", "indicator", "get", "取单个指标", "指标代码直查"),
    ("fundamentals", "indicator", "metrics", "批量取指标", "指标代码批量直查"),
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
    ("disclosure", "dividend", "last", "最近一次分红", "bonus.query_last"),
    ("disclosure", "dividend", "dps", "财报期每股分红", "bonus.dps_rpt"),
    ("disclosure", "dividend", "window_stats", "窗口分红统计", "bonus.query_*_window"),
    ("disclosure", "dividend", "yield_ttm", "TTM 股息率", "bonus.snapshot_yield_ttm"),
    ("disclosure", "dividend", "payout_ttm", "TTM 派息率", "bonus.snapshot_payout_ttm"),
    ("reference", "info", "profile", "公司档案摘要", "档案指标（$NAME 等）"),
]

# 类型化门面（生成层）：目录命名空间的完整类型签名；运行时仍走 client.call()。
from finpipe.api._generated import NAMESPACES as GENERATED_NAMESPACES  # noqa: E402
