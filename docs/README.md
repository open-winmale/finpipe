# 文档导航

wmshare 的文档按「教程 / 怎么做 / 参考 / 解释」四层组织（Diátaxis），各层不混写。
按你的目标选入口：

| 我想… | 去哪 | 说明 |
|---|---|---|
| 5 分钟装好并跑通第一行 | [README](../README.md) | 店面：特性、安装、凭证、三行上手 |
| 系统学一遍（可运行课程） | [examples/](../examples/README.md) | 9 个编号示例：离线优先、CI 全覆盖、输出带单位注释 |
| 完成某个具体任务 | [GUIDE.md](GUIDE.md) | 单票菜谱、全市场与行业、批量绕 429、多市场、pandas、公告订阅 |
| 查某个接口的参数与返回 | [API.md](API.md) | 116 个核心接口参考（生成物，随目录合同更新）；机器可读 [openapi.json](openapi.json) / [swagger.html](swagger.html) |
| 理解设计口径 | GUIDE · [核心概念](GUIDE.md#2-核心概念) | 双层 API、目录先行、单位铁律、限流模型 |
| 排查报错 | GUIDE · [故障排查](GUIDE.md#9-故障排查) | 错误家族表 + 按症状查 |
| 让 AI 正确使用本 SDK | [AI.md](AI.md) | 装 skill / 文档作上下文 / 报错驱动；提示词模板与安全红线 |
| 给 AI 投喂全文 | [llms.txt](../llms.txt) · [llms-full.txt](../llms-full.txt) | AI 友好索引与全文拼接（生成物） |

## 阅读路径建议

- **数据分析新手**：README 三行上手 → `examples/01→04→05` → GUIDE 单票菜谱 → GUIDE 故障排查
- **全市场/工程化用户**：GUIDE 第 5 章（批量）→ `examples/07、08` → GUIDE 配额实测
- **AI agent 开发者**：AI.md → `examples/09` → 把 skill 装进你的 agent → GUIDE 当参考

## 维护约定

- API.md / openapi.json / swagger.html / llms*.txt 是生成物：改 `tools/gen_*.py` 后重新生成，
  漂移由 CI 门禁拦截，不手改；
- 公开文档零竞品名、零导流话术（check_leak 与 test_docs 门禁强制）；
- 新示例必须带编号进课程表并在 tests 里端到端覆盖（约定见 [examples/README](../examples/README.md)）；
- 贡献流程见 [CONTRIBUTING](../CONTRIBUTING.md)，安全披露见 [SECURITY](../SECURITY.md)。
