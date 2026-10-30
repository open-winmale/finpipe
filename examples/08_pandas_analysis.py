"""pandas 分析：`_df=True` 直接拿 DataFrame 做研究计算。

前提：凭证必填 + 可选依赖 pandas（pip install "wmshare[dataframe]"）；`--demo` 用随包演示数据零凭证试跑
运行：python examples/08_pandas_analysis.py
学到：_df=True 转 DataFrame；MA20/动量/资金流合计/分红历史表
文档：docs/GUIDE.md（pandas）
"""
import sys
import wmshare
from wmshare import Client


def main(cli=None, demo: bool = False) -> None:
    if cli is None:
        if demo:
            cli = wmshare.demo_client()
            print("(演示模式：随包罐头数据，非真实行情)")
            print()
        else:
            cli = wmshare.Client.from_env()
    SYMBOL = "600519"

    # ---- 日 K → DataFrame：先升序再算指标 ----
    # bars 按日期降序返回（最新在前），直接 iloc[-1] 拿到的是最老一根——
    # pandas 惯例是升序，先排序是必做的一步（实测踩过的坑，勿删）。
    df = cli.kline.bars(SYMBOL, n=120, _df=True).sort_values("date", ignore_index=True)
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
    main(demo="--demo" in sys.argv)
