"""pandas 分析：`_df=True` 直接拿 DataFrame 做研究。

需要凭证 + 可选依赖（在仓库根目录安装）：pip install ".[dataframe]"
    export WMSHARE_CLIENT_ID=... WMSHARE_CLIENT_SECRET=...
    python examples/pandas_analysis.py
"""
from wmshare import Client


def main() -> None:
    cli = Client.from_env()
    SYMBOL = "600519"

    # ---- 日 K → DataFrame：算 20 日均线与动量 ----
    df = cli.kline.bars(SYMBOL, n=120, _df=True)
    df["ma20"] = df["close"].rolling(20).mean()
    df["mom_20d"] = df["close"].pct_change(20)
    last = df.iloc[-1]
    print(f"{SYMBOL}  收盘={last['close']:.2f}  MA20={last['ma20']:.2f}  "
          f"20日动量={last['mom_20d']:.2%}")
    above = bool(last["close"] > last["ma20"])
    print(f"站上 MA20：{above}")

    # ---- 资金流 → DataFrame：近 20 日主力净流入合计 ----
    mf = cli.moneyflow.bars(SYMBOL, n=20, _df=True)
    print(f"近 20 日主力净流入合计：{mf['net_mf'].sum():,.0f} 元")

    # ---- 分红历史 → DataFrame：股息可持续性速览 ----
    div = cli.dividend.history(SYMBOL, limit=10, _df=True)
    cols = [c for c in ("ex_div", "dps", "payout_ratio") if c in div.columns]
    print("\n近 10 次分红：")
    print(div[cols].to_string(index=False))


if __name__ == "__main__":
    main()
