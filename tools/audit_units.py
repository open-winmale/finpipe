"""单位口径审计：对样本宇宙逐公司跑目录声明的量级守护与关系不变量 + 跨接口一致性。

维护者命令（联网）：
    python tools/audit_units.py                       # 默认样本宇宙
    python tools/audit_units.py --etf 510300          # 自选 ETF 验证成交量口径

SDK 默认调用路径（call() / indicator.get）已内置换算 + 量级守护 + 行内不变量，
本工具在其之上补**跨接口**一致性核验（数据是否对所有公司同口径，而非单一样本）：
  - $AMOUNT_LAST（指标层）与 kline bars amount 同量级（同为元，容时间戳差异）
  - dividend.yield_ttm == $BONUS_RATE_TTM_LAST（跨接口恒等，分红公司）
  - $MV_FREE_LAST <= $MV_LAST
样本宇宙覆盖不同板块/行业/规模（大市值消费/金融/创业板制造/科创板/高杠杆周期），
任何一家违例即 FAIL；报告逐项输出，存在 FAIL 时退出码 1（供 CI 夜间审计）。
"""
from __future__ import annotations

import argparse
import sys

import finpipe
from finpipe import DataError

DEFAULT_UNIVERSE = ["600519", "601318", "300750", "688981", "601857"]
DEFAULT_ETF = "510300"
METRIC_CODES = [
    "$CLOSE_LAST", "$MV_LAST", "$MV_FREE_LAST", "$AMOUNT_LAST",
    "$BONUS_TTM", "$BONUS_RATE_TTM_LAST", "$ROE_TTM_LAST", "$TL_RATE_LAST",
    "$TR_TTM_LAST", "$NP_TTM_LAST",
]

# AMOUNT_LAST（live 截面）与 EOD bars amount 的时间戳不同，只校验同量级（同为中心元）
AMOUNT_SCALE_RATIO = (0.02, 50.0)


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[bool, str, str]] = []

    def add(self, ok: bool, check: str, detail: str) -> None:
        self.rows.append((ok, check, detail))
        print(f"{'PASS' if ok else 'FAIL'}  {check:<28} {detail}")

    def ok(self) -> bool:
        return all(r[0] for r in self.rows)


def audit_symbol(rep: Report, cli: finpipe.Client, sym: str, with_fundamentals: bool = True) -> None:
    # 1) K 线：volume(股)×close≈amount(元)——SDK 运行时已守护，这里复核并记录
    bars = cli.call("kline.query_bars", sym=sym, limit=3)
    bar = bars[-1] if bars else {}
    v, c, a = bar.get("volume"), bar.get("close"), bar.get("amount")
    if v and c and a:
        ratio = v * c / a
        rep.add(0.4 <= ratio <= 2.5, "kline.volume_amount",
                f"{sym}: volume={v:.0f}股 ratio={ratio:.3f}")
    else:
        rep.add(False, "kline.volume_amount", f"{sym}: bars 缺 volume/close/amount")

    if not with_fundamentals:
        return

    # 2) 指标层：runtime 已做 range 守护（违例抛 DataError）；补跨接口一致性
    try:
        m = cli.indicator.metrics(sym, METRIC_CODES)
    except DataError as e:
        rep.add(False, "indicator.range", f"{sym}: {e}")
        return
    mv, mv_free = m.get("$MV_LAST"), m.get("$MV_FREE_LAST")
    if mv and mv_free:
        rep.add(mv_free <= mv * 1.01, "indicator.mv_free_le_mv",
                f"{sym}: MV_FREE/MV={mv_free / mv:.3f}")
    amount_last = m.get("$AMOUNT_LAST")
    if amount_last and v and a:
        scale = amount_last / a
        lo, hi = AMOUNT_SCALE_RATIO
        rep.add(lo <= scale <= hi, "indicator.amount_scale_yuan",
                f"{sym}: $AMOUNT_LAST/bars.amount={scale:.3g}（同为中心元则接近 1）")
    # 3) 跨接口恒等：yield_ttm == $BONUS_RATE_TTM_LAST
    rate = m.get("$BONUS_RATE_TTM_LAST")
    if rate:
        y = cli.dividend.yield_ttm(sym)
        rep.add(y is not None and abs(y - rate) <= 1e-9, "cross.yield_identity",
                f"{sym}: yield_ttm={y} vs $BONUS_RATE_TTM_LAST={rate}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="单位口径审计（样本宇宙 + 跨接口一致性）")
    ap.add_argument("--universe", default=",".join(DEFAULT_UNIVERSE),
                    help="逗号分隔的样本宇宙（默认覆盖不同板块/行业/规模）")
    ap.add_argument("--etf", default=DEFAULT_ETF, help="ETF 代码（验证成交量口径跨品种一致）")
    ap.add_argument("--compare-syms", default=2, type=int,
                    help="对前 N 家跑 statement_compare（配额友好；0 关闭）")
    args = ap.parse_args(argv)

    cli = finpipe.Client.from_env()
    rep = Report()
    print(f"# 单位口径审计 | 样本宇宙 {args.universe} | ETF {args.etf}")
    print(f"# finpipe {finpipe.__version__} | catalog upstream_rev "
          f"{cli.catalog.stats().get('upstream_rev')}")

    universe = [s.strip() for s in args.universe.split(",") if s.strip()]
    for i, sym in enumerate(universe):
        try:
            audit_symbol(rep, cli, sym)
        except finpipe.FinPipeError as e:
            rep.add(False, "call", f"{sym}: {type(e).__name__}: {e}")
    if args.etf:
        try:
            audit_symbol(rep, cli, args.etf, with_fundamentals=False)
        except finpipe.FinPipeError as e:
            rep.add(False, "call", f"ETF {args.etf}: {type(e).__name__}: {e}")
    for sym in universe[:max(0, args.compare_syms)]:
        try:
            cli.statements.compare(sym, kind="income", years=1)
            rep.add(True, "statements.diffp_ratio", f"{sym}: SDK 不变量通过（diffp 小数口径）")
        except DataError as e:
            rep.add(False, "statements.diffp_ratio", f"{sym}: {e}")

    fails = sum(1 for r in rep.rows if not r[0])
    print(f"\n# 结果：{len(rep.rows) - fails}/{len(rep.rows)} 通过"
          + ("" if not fails else f"；{fails} 项 FAIL（单位口径可能已漂移，请核查目录声明）"))
    return 0 if rep.ok() else 1


if __name__ == "__main__":
    sys.exit(main())
