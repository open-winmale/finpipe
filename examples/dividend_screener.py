"""高股息筛选器：finpipe 的杀手锏能力，跨自选股批量筛选。

需要凭证（内置体验 appid 也可跑）：共享池额度有限，建议用自己的 appid。
    export FINPIPE_CLIENT_ID=... FINPIPE_CLIENT_SECRET=...
    python examples/dividend_screener.py
"""
from finpipe import Client, FinPipeError

WATCHLIST = ["600519", "000858", "601088", "600900", "601318"]  # 自选股，换成你的


def main() -> None:
    cli = Client.from_env()

    # ---- 单票质量筛选：分红质量优（高股息 + 派息可持续）----
    print("--- 分红质量筛选（质量优 = 通过）---")
    for sym in WATCHLIST:
        try:
            ok = cli.dividend.screen_quality(sym, min_yield=0.02, payout_max=1.2)
            y = cli.dividend.yield_ttm(sym)
            print(f"  {sym}  TTM股息率={y if y is not None else '—':<8} 质量优={ok}")
        except FinPipeError as e:
            print(f"  {sym}  跳过：code={e.code} {e}")

    # ---- 批量调用：call_batch 单次 HTTP 返回 {symbol: 结果} ----
    print("\n--- call_batch：一次请求取全部自选股 TTM 股息率 ---")
    batch = cli.call_batch("bonus.snapshot_yield_ttm", WATCHLIST, on_error="skip")
    for sym, val in sorted(batch.results.items(), key=lambda kv: -(kv[1] or 0)):
        print(f"  {sym}  {val:.2%}" if val is not None else f"  {sym}  —")
    if batch.errors:
        print(f"  错误隔离：{len(batch.errors)} 个失败 → {dict(list(batch.errors.items())[:3])}")

    # ---- 底层选股函数经属性直达（__getattr__ 兜底，164 函数零遮蔽）----
    # 注意：index_where_* 返回的是服务端查询引擎的筛选表达式（非本地可执行的票池）
    print("\n--- 底层函数直达：cli.dividend.index_where_high_yield_5() ---")
    try:
        expr = cli.dividend.index_where_high_yield_5()  # 「连续 5 年高股息」筛选条件表达式
        print(f"  筛选表达式：{str(expr)[:80]}")
    except FinPipeError as e:
        print(f"  跳过：code={e.code} {e}")


if __name__ == "__main__":
    main()
