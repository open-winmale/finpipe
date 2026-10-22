# openwm

A 股个股数据 Python SDK。数据目录随包内置（离线可查全部接口合同），取数走云端 API，
**安装后唯一外部依赖是你的 appid（client_id + client_secret）**——不依赖任何仓库或内部工程。

```python
import openwm as wm

cli = wm.Client.from_env()          # 凭证：环境变量 OPENWM_CLIENT_ID / OPENWM_CLIENT_SECRET

cli.kline.bars("600519", n=30)                      # 日 K（自动规范化）
cli.statements.income("600519", years=5)            # 利润表（合并口径）
cli.indicator.get("600519", "$PE_TTM_LAST")         # 平台指标（TTM 市盈率）
cli.notice.list("600519", window="90d")             # 公告
cli.notice.find("600519", "2026-01-01", "2026-03-31")   # 按日期区间查公告
cli.dividend.yield_ttm("600519")                    # TTM 股息率
cli.info.profile("600519")                          # 公司档案
cli.bonus.query_list("600519", limit=10)            # 底层目录函数（类型化，IDE 补全）
```

## 安装

```bash
pip install openwm            # 或源码安装：pip install .
pip install "openwm[dataframe]"   # 可选：pandas 支持（_df=True）
```

配置凭证（二选一）：

```bash
export OPENWM_CLIENT_ID=...
export OPENWM_CLIENT_SECRET=...
# 或写入 ~/.openwm/credentials.env（KEY=VALUE 每行一条）
```

## 数据范围（一期，9 个数据域）

| 分类 | 数据域 | 性质 |
|------|--------|------|
| 市场行情 | 行情K线（日K/复权/盘中快照）、资金流向 | 原始数据 |
| 财务基本面 | 三大报表（资产负债/利润/现金流）、指标层（2197 个指标代码：估值/盈利/成长/现金流/杜邦…） | 报表=原始数据，指标=派生指标 |
| 信息披露 | 公告、定期报告清单、业绩预告/快报/披露日历、分红 | 原始数据（率类为指标） |
| 参考数据 | 公司档案 / 股本 | 原始数据 |

**原始数据与指标显式分标**：每个接口在目录中标注 `raw`（披露/直采数据，含外部源算好的）
或 `computed`（平台公式计算的派生指标），全量见 [docs/API.md](docs/API.md)。

数据经云端 API 运行时获取（代码与目录开源，数据不随包分发）。

## 使用限制（必读）

本项目采用 [PolyForm Noncommercial License 1.0.0](LICENSE)：

- ✅ **仅限非商业目的**：个人学习、研究、教学、学术、爱好者项目、公益组织等；
- ❌ **严禁商业使用**：任何商业目的的使用、再分发或服务化均需另行获得商业授权；
- 本许可属于 source-available（源码可见）而非 OSI 定义的开源许可。

商业授权请联系项目维护方。数据仅供研究参考，不构成任何投资建议。

## 更多

- [API 参考](docs/API.md)：四大类全量接口（参数 / 返回字段 / 单位口径 / 示例）
- 类型化门面：全部目录命名空间带类型签名与 docstring（`py.typed`），IDE 直接补全；
  单次拉取上限 `Client(max_limit=500)` 可调
- [贡献指南](CONTRIBUTING.md)：提交门禁、内容规范、许可政策
- 运行测试：`pytest`（不联网）；`OPENWM_LIVE=1 pytest tests/test_live.py`（真实冒烟）
