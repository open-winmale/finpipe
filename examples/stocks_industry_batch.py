"""全市场代码池 → 行业过滤 → 批量取数：一表流的完整链路。

凭证必填：注册开放平台获取 client_id/api-key（免费、注册即得）：
    export WMSHARE_CLIENT_ID=... WMSHARE_CLIENT_SECRET=...
    python examples/stocks_industry_batch.py

可选环境变量：
    WMSHARE_MARKET=cn|hk|us   # 缺省 cn（港/美同样出全表；美股行业目录树暂缺）
    BANK_HINT=银行            # 行业名或行业代码（如 S48 / industry.S48）

说明：
  - cli.stocks.list() 一次拿全市场（A≈5.7k / 港≈2.8k / 美≈5.6k 行）；
  - cli.stocks.industry_members() 支持中文名（"银行"）、行业代码（"S48"）、行业键；
  - 批量绕开 429：服务端按请求次数限流（免费档 500 次/小时），逐票取全市场必撞；
    batch_all 自动按 500 分批 —— A 股 5691 家只发 12 次请求；
  - 少量标的单批用 call_batch（≤500），to_df() 出带 symbol 列的长表；
  - 港/美市场用 Client.from_env(market="hk"/"us")，跨市场代码会被服务端拒绝。
"""
import os

import wmshare


def main(cli=None) -> None:
    cli = cli or wmshare.Client.from_env()

    # ---- 1) 全市场证券列表（代码池底座） ----
    rows = cli.stocks.list()
    print(f"全市场共 {len(rows)} 家（字段：{sorted(rows[0].keys())}）")

    # ---- 2) 行业目录 + 行业成分（中文名/代码皆可） ----
    hint = os.environ.get("BANK_HINT", "银行")
    l1 = cli.stocks.industries(1)
    print(f"一级行业 {len(l1)} 个，如："
          + "、".join(f"{r['symbol']} {r['name']}" for r in l1[:5]) + " …")
    try:
        members = cli.stocks.industry_members(hint)
        print(f"「{hint}」成分 {len(members)} 家，前 5 家：")
        for r in members[:5]:
            print(f"  {r['symbol']}  {r['name']}  {r.get('industry_name', '')}"
                  f"  上市 {r.get('listed') or '—'}")
    except wmshare.WmshareError as e:
        # 未命中/多候选时错误消息会列出候选行业；改用候选里的代码重试即可
        print(f"行业解析失败：{e}")
        return

    # ---- 3) 批量取数：全市场分批（A 股 12 次请求，逐票要 5691 次会撞 429） ----
    all_codes = [r["symbol"] for r in rows]
    res = cli.batch_all("kline.snapshot", all_codes)
    naive = len(all_codes)
    print(f"全市场 {len(res.results)} 家：批量 {res.requests} 次请求"
          f"（逐票需 {naive} 次，免费档 500 次/小时 → 省 {naive // max(res.requests, 1)} 倍配额）")
    if res.errors:
        print(f"失败批 {len(res.errors)}：{list(res.errors)[:3]}")

    # ---- 4) 逐批：长任务边取边处理（此处只打印批大小，实际可 to_df().to_parquet） ----
    for i, part in enumerate(cli.batch_iter("kline.snapshot", all_codes), 1):
        print(f"  第 {i} 批 {len(part.results)} 家", end="\r" if i % 3 else "\n")
    print()

    # ---- 5) 行业维度聚合（单批 ≤500 也可直接用 call_batch） ----
    codes = [r["symbol"] for r in members[: min(500, len(members))]]
    one = cli.call_batch("kline.snapshot", codes)
    df = one.to_df()  # 需要 pandas（pip install "wmshare[dataframe]"）
    print(f"「{hint}」{len(df)} 行快照（symbol 列在前）：")
    print(df.head().to_string(index=False))


if __name__ == "__main__":
    main()
