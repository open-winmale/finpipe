# examples：可运行示例（渐进式课程）

**编号即学习路径**：每个脚本独立可跑；输出里的数值都带单位注释——读输出就能学会
「率/分位=小数（0.0396 = 3.96%）、金额=元、量=股」的基础口径。
3 个离线示例在 CI 里以子进程真实执行，6 个凭证示例注入假客户端（`main(cli=None)`）
端到端跑过——可放心照抄。

## 运行

```bash
pip install wmshare                    # 仓库开发：pip install -e .
export WMSHARE_CLIENT_ID=... WMSHARE_CLIENT_SECRET=...   # 凭证获取见仓库 README「配置凭证」
python examples/01_quickstart.py
```

- **零凭证可跑**（不联网）：`02_catalog_tour`、`03_error_handling`、`09_ai_skill_setup`
- **可选依赖**：`pip install "wmshare[dataframe]"`（pandas，`08_pandas_analysis` 需要）

## 课程表

| # | 脚本 | 阶段 | 前提 | 学到什么 | 对应文档 |
|---|---|---|---|---|---|
| 01 | `01_quickstart.py` | 入门 | 凭证 | 行情/财务/披露/参考四类取数一次过；批量绕开 429 | GUIDE·单票菜谱、批量取数 |
| 02 | `02_catalog_tour.py` | 入门 | **离线** | 目录先行：`cat.search`、函数合同、指标组（防臆造） | GUIDE·核心概念 |
| 03 | `03_error_handling.py` | 入门 | **离线** | WmshareError 家族、按类型分支、code/status 程序化处理 | GUIDE·故障排查 |
| 04 | `04_screener.py` | 进阶 | 凭证 | 涨停/均线/放量单票筛选；全景/分桶/涨跌榜；`*_pct` 百分数例外 | GUIDE·单票菜谱 |
| 05 | `05_dividend_screener.py` | 进阶 | 凭证 | 分红质量筛选；call_batch 票级批量；底层函数属性直达 | GUIDE·单票菜谱 |
| 06 | `06_indicator_tour.py` | 进阶 | 凭证 | 指标码体系：`cat.search`→分位/TTM→`hist_stats`，小数读法 | GUIDE·核心概念 |
| 07 | `07_stocks_industry_batch.py` | 生产 | 凭证 | 全市场列表→行业成分→batch_all/batch_iter/call_batch 三入口分工 | GUIDE·批量取数 |
| 08 | `08_pandas_analysis.py` | 生产 | 凭证+pandas | `_df=True` 转 DataFrame：MA20/动量/资金流/分红表 | GUIDE·pandas |
| 09 | `09_ai_skill_setup.py` | AI | **离线** | skill 自检与装入 agent；AI 正确行为的验证标准 | AI.md（全文） |

## 约定（新增示例请遵守）

- 文件名 `NN_主题.py`（两位编号，接在现有最大编号后）；
- docstring 固定四行元信息：**前提 / 运行 / 学到 / 文档**；
- 骨架 `def main(cli=None)` + `__main__` 捕获 `WmshareError` 打印原文（消息自带修复步骤）；
- 打印值带单位注释；新增后同步本表，并在 `tests/test_examples.py` 加对应测试（CI 会拦截漏网的示例）。
