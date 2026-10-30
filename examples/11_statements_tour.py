"""财务报表：三大报表多期科目行 + 合并 vs 母公司对照 + 审计意见。

前提：凭证必填（export WMSHARE_CLIENT_ID=... WMSHARE_CLIENT_SECRET=...）；`--demo` 用随包演示数据零凭证试跑
运行：python examples/11_statements_tour.py
学到：报表行结构（k 科目键/cn 中文名/vals 各期值，金额=原币元）；compare 的 diffp 差额占比是小数；审计意见按年报
文档：docs/GUIDE.md（单票菜谱·三大报表）
"""
import sys
import wmshare

SYMBOL = "600519"


def main(cli=None, demo: bool = False) -> None:
    if cli is None:
        if demo:
            cli = wmshare.demo_client()
            print("(演示模式：随包罐头数据，非真实行情)")
            print()
        else:
            cli = wmshare.Client.from_env()

    # ---- 可用年报年份（降序）----
    years = cli.statements.years(SYMBOL, "income")
    print(f"利润表可用年报：{years}")

    # ---- 三大报表：科目行 {k 科目键, cn 中文名, vals:{年份: 值}}，金额=报表原币元 ----
    for kind, title in (("income", "利润表"), ("balance", "资产负债表"),
                        ("cashflow", "现金流量表")):
        rows = getattr(cli.statements, kind)(SYMBOL, years=1)
        first = next(r for r in rows if r.get("vals"))
        y, v = next(iter(first["vals"].items()))
        print(f"{title}：{len(rows)} 行科目；如「{first['cn']}」（{y}）= {v:,.0f} 元")

    # ---- 合并 vs 母公司：diffp 差额占比是小数（0.078 = 7.8%；母公司未披露的科目为空）----
    cmp_rows = cli.statements.compare(SYMBOL, "income", years=2)
    diff_rows = [r for r in cmp_rows if r.get("diff")]
    print(f"合并 vs 母公司（近 2 期）：{len(cmp_rows)} 行科目，{len(diff_rows)} 行可对出差额")
    for r in diff_rows[:3]:
        y = sorted(r["diff"])[0]
        print(f"  {r['cn']}（{y}）：合并 {r['c'][y]:,.0f} 元，母公司 {r['p'][y]:,.0f} 元，"
              f"差额占比 {r['diffp'][y]:.2%}")

    # ---- 审计意见（按年报）----
    audit = cli.statements.audit(SYMBOL)
    for y in sorted(audit, reverse=True)[:2]:
        print(f"{y} 年审计意见：{audit[y]}")


if __name__ == "__main__":
    try:
        main(demo="--demo" in sys.argv)
    except wmshare.WmshareError as e:
        print(f"取数失败：{e}")
        raise SystemExit(1)
