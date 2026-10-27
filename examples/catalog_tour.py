"""目录巡礼：离线可跑，无需凭证、不联网。

随包目录是 SDK 的核心卖点之一——249 个底层函数、2197 个指标代码
随 wheel 分发，断网也能查全部接口合同。

    python examples/catalog_tour.py
"""
from wmshare import load


def main() -> None:
    cat = load()  # 装载随包目录（纯本地读文件，零网络请求）

    # ---- 全局概览 ----
    stats = cat.stats()
    print(f"数据域：{stats['domains']}  底层函数：{stats['functions']}"
          f"（原始 {stats['raw']} / 派生 {stats['computed']}）")
    print(f"指标代码：精选 {stats['curated_metrics']} / 目录全量 {stats['metric_catalog_total']}")

    # ---- 关键字搜索：函数 + 指标一次出 ----
    print("\n--- cat.search('股息') ---")
    for hit in cat.search("股息"):
        where = hit.get("name") or hit.get("code")
        print(f"  [{hit['kind']}] {where}  {hit.get('cn', '')}")

    # ---- 按指标组浏览 ----
    print("\n--- 指标组 ---")
    for g in cat.metric_groups():
        print(f"  {g['id']:<18} {g['cn']}（{g['count']} 个）")

    print("\n--- dividend 组前 5 个指标 ---")
    for m in cat.metrics_in_group("dividend")[:5]:
        print(f"  {m['code']:<22} {m.get('cn', '')}")

    # ---- 函数合同：参数 / 返回 / 示例 ----
    fn = cat.function("bonus.screen_quality")
    params = fn.get("params") or cat.inventory_params("bonus.screen_quality")
    print(f"\n--- 合同：bonus.screen_quality（{fn.get('cn')}）---")
    for p in params:
        req = "必填" if p.get("required") else "可选"
        print(f"  :param {p['name']} ({p.get('type', 'any')}, {req}) {p.get('desc', '')}")
    print(f"  :returns {fn.get('returns', {}).get('desc', '')}")
    print(f"  示例：{fn.get('example', '')}")

    # ---- 按域列出全部函数 ----
    by_domain = cat.functions_by_domain()
    domain = "market.kline"
    print(f"\n--- {domain} 域的 {len(by_domain[domain])} 个函数（前 10）---")
    for name in by_domain[domain][:10]:
        print(f"  {name}")


if __name__ == "__main__":
    main()
