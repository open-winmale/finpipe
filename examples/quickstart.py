"""快速上手：5 分钟看懂 finpipe 的四类数据。

运行前设置凭证：
    export FINPIPE_CLIENT_ID=... FINPIPE_CLIENT_SECRET=...
    python examples/quickstart.py
"""
import finpipe

cli = finpipe.Client.from_env()
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
print(f"PE(TTM)={pe}  ROE(TTM)={roe}%")

# ---- 信息披露 ----
notices = cli.notice.list(SYMBOL, window="3m", limit=3)
print(f"近 3 个月公告（前 3 条）：")
for n in notices or []:
    print(f"  {n.get('date', '')}  {str(n.get('title', ''))[:40]}")

div = cli.dividend.last(SYMBOL)
if div:
    print(f"最近一次分红：{div}")

# ---- 参考数据 ----
profile = cli.info.profile(SYMBOL)
print(f"{profile.get('name')} · {profile.get('industry')} · 上市 {profile.get('listing_date')}")

# 进阶：DataFrame 与全量底层函数
df = cli.kline.bars(SYMBOL, n=30, _df=True)     # 需 pip install "finpipe[dataframe]"
print(f"DataFrame 形状：{df.shape}")
row = cli.call("kline.query_last_live", sym=SYMBOL)   # 155 个底层函数通用入口
