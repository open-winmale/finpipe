"""选股与全景：cli.screener 单票筛选器 + 全市场涨跌宽度（服务端索引直出）。

需要凭证：注册开放平台获取（免费、注册即得），见错误消息指引。
    export WMSHARE_CLIENT_ID=... WMSHARE_CLIENT_SECRET=...
    python examples/screener.py
"""
from wmshare import Client, WmshareError

WATCHLIST = ["600519", "000858", "601088", "600900", "601318"]  # 自选股，换成你的


def main() -> None:
    cli = Client.from_env()

    # ---- 单票一行布尔：涨停 / 站上 MA20 / 放量（停牌恒 False）----
    print("--- 单票筛选器（阈值均为小数：0.10 = 10%）---")
    for sym in WATCHLIST:
        try:
            print(f"  {sym}  涨停={cli.screener.screen_limit_up(sym)}"
                  f"  站上MA20={cli.screener.screen_above_ma20(sym)}"
                  f"  放量={cli.screener.screen_volume_spike(sym)}")
        except WmshareError as e:
            print(f"  {sym}  跳过：code={e.code} {e}")

    # ---- 全市场涨跌全景：服务端预计算索引直出，免本地扫描 ----
    print("\n--- 涨跌全景（*_pct 百分数数值，median_pct 小数）---")
    try:
        s = cli.screener.index_breadth_summary()
        print(f"  总数={s.get('total')}  涨={s.get('up')}({s.get('up_pct')}%)"
              f"  跌={s.get('down')}({s.get('down_pct')}%)  平={s.get('flat')}"
              f"  涨跌幅中位数={s.get('median_pct')}")
    except WmshareError as e:
        print(f"  跳过：code={e.code} {e}")

    # ---- 涨跌幅 9 档分桶：涨停档 / 大涨档家数一目了然 ----
    print("\n--- 涨跌幅分桶（前 3 档）---")
    try:
        for b in cli.screener.index_breadth_bins()[:3]:
            print(f"  {b['label']:<12} {b['count']:>5} 家（{b['pct_of_total']}%）")
    except WmshareError as e:
        print(f"  跳过：code={e.code} {e}")

    # ---- 涨跌榜：行含 symbol/name/percent（percent 为小数）----
    print("\n--- 涨幅榜 Top5 / 跌幅榜 Top3 ---")
    try:
        for r in cli.screener.index_top_movers(limit=5):
            print(f"  {r['symbol']}  {r['name']:<6} {r['percent']:+.2%}")
        print("  ---")
        for r in cli.screener.index_top_movers(limit=3, desc=False):
            print(f"  {r['symbol']}  {r['name']:<6} {r['percent']:+.2%}")
    except WmshareError as e:
        print(f"  跳过：code={e.code} {e}")

    # ---- 其余目录筛选函数经属性直达（零遮蔽）----
    print("\n--- 底层函数直达：cli.screener.screen_up_today(sym) ---")
    for sym in WATCHLIST[:2]:
        try:
            print(f"  {sym}  今日上涨={cli.screener.screen_up_today(sym)}")
        except WmshareError as e:
            print(f"  {sym}  跳过：code={e.code} {e}")


if __name__ == "__main__":
    main()
