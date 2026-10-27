"""快速上手：5 分钟看懂 wmshare 的四类数据。

凭证是可选的：不配置时自动使用内置体验 AppID（共享池、额度有限，仅供初次体验）。
正式使用建议配置自己的 AppID：
    export WMSHARE_CLIENT_ID=... WMSHARE_CLIENT_SECRET=...
    python examples/quickstart.py

遇到 401/403/429 时，错误消息会直接给出申请 AppID 的步骤。
"""
import wmshare


def main(cli=None) -> None:
    cli = cli or wmshare.Client.from_env()
    SYMBOL = "600519"

    # ---- 市场行情 ----
    bars = cli.kline.bars(SYMBOL, n=5)
    print("最近 5 根日 K：")
    for bar in bars:
        print(f"  {bar['date']}  收盘 {bar['close']}  涨跌 {bar['percent']:.2%}")

    snapshot = cli.kline.snapshot(SYMBOL)
    print(f"行情摘要：收盘 {snapshot['close']}，近20日 {snapshot['chg_20d']:.2%}")

    mf = cli.moneyflow.last(SYMBOL)
    if mf:
        print(f"最新主力净流入：{mf.get('net_mf'):,.0f} 元")

    # ---- 财务基本面 ----
    income = cli.statements.income(SYMBOL, years=3)
    print(f"利润表（近 3 期）：{len(income)} 行科目")

    pe = cli.indicator.get(SYMBOL, "$PE_TTM_LAST")
    roe = cli.indicator.get(SYMBOL, "$ROE_TTM_LAST")
    print(f"PE(TTM)={pe}  ROE(TTM)={roe:.2%}" if roe is not None else f"PE(TTM)={pe}  ROE(TTM)=—")

    # ---- 信息披露 ----
    notices = cli.notice.list(SYMBOL, window="3m", limit=3)
    print(f"近 3 个月公告（前 3 条）：")
    for n in notices or []:
        print(f"  {n.get('date', '')}  {str(n.get('title', ''))[:40]}")

    div = cli.dividend.last(SYMBOL)
    if div:
        print(f"最近一次分红：除权 {div.get('ex_div')}  DPS {div.get('dps')}  "
              f"总额 {div.get('total')}")

    # ---- 参考数据 ----
    profile = cli.info.profile(SYMBOL)
    print(f"{profile.get('name')} · {profile.get('industry')} · 上市 {profile.get('listing_date')}")

    # 进阶：DataFrame 见 examples/pandas_analysis.py；底层函数通用入口：
    cli.call("kline.query_bars", sym=SYMBOL, limit=5)


if __name__ == "__main__":
    try:
        main()
    except wmshare.WmshareError as e:
        # 401/403/429 等会在这里直接显示 AppID 申请步骤，而不是裸 traceback。
        print(f"取数失败：{e}")
        raise SystemExit(1)
