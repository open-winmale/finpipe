# AGENTS.md

给 AI 编码代理（Claude Code、ZCode、Codex…）的仓库工作约定。人类贡献者的唯一事实源是
[CONTRIBUTING.md](CONTRIBUTING.md)，本文件只是代理视角的摘要；两者冲突时以 CONTRIBUTING 为准。

## 门禁（提交前全部跑一遍，CI 同款）

```bash
python tools/check_leak.py            # 泄漏 / 竞品名 / 凭证字面量
python tools/validate_catalog.py      # 目录合同 + 防编造
python tools/gen_api_docs.py --check  # 以下四个是生成物漂移门禁
python tools/gen_typed_api.py --check
python tools/gen_openapi.py --check
python tools/gen_llms.py --check
python -m mypy
pytest -q                             # 离线全量（覆盖率 ≥85%）
```

## 硬规则

- **先查目录再写代码**：指标码/函数名/参数一律 `wmshare.load()` 后
  `cat.search / cat.function` 确认，禁止凭记忆编造；
- **公开文档零竞品名、零导流话术**（CTA 禁词表见 `tests/test_docs.py::test_docs_no_ad_diversion_cta`，
  Gitee 内容风控会拦截导流类措辞，故全库执行）；
- **生成物不手改**：docs/API.md、docs/openapi.json、docs/swagger.html、llms.txt、
  llms-full.txt 由 `tools/gen_*.py` 生成——改源头后重新生成，漂移门禁会拦截手改；
- **README ≤291 行**（`test_readme_is_lean`）：长内容下沉 docs/，先删后提限；
- **新增示例**：`NN_主题.py` 编号进 examples/ 课程表，docstring 四行元信息
  （前提/运行/学到/文档），`main(cli=None)` 可注入，tests 端到端覆盖，并加进 examples/README.md 索引；
- **文档引用全部受门禁校验**：README/GUIDE/AI 里的 `cli.*` 调用、`$指标码`、`cat.*` 方法、
  域 id 必须真实存在；
- **凭证纪律**：密钥只走环境变量或 `~/.wmshare/credentials.env`，任何密钥字面量不得入库；
- 提交信息用 conventional 前缀（`feat:`/`fix:`/`docs:`/`chore:`）。
