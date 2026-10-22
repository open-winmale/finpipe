# 贡献指南与项目规范

感谢关注 openwm。本文件同时是**内容规范**：违反任一条会被 CI 门禁拦截。

## 提交前门禁（全部必须通过）

```bash
python3 tools/check_leak.py        # 内容规范扫描（见下）
python3 tools/validate_catalog.py  # 域目录合同 + 防编造回溯
python3 tools/gen_api_docs.py      # 重生成 docs/API.md（改了目录必须重跑）
pytest                             # 全部测试（不联网）
```

CI（`.github/workflows/ci.yml`）在每次 push/PR 上跑同样的门禁。

## 内容规范（check_leak 强制）

1. **禁止第三方产品/数据商引用**：不得出现任何第三方数据产品、数据商或竞品名称
   （包括对标措辞、数据来源点名、商标）。描述数据来源使用中性词（"交易所披露"、
   "平台数据源"等）。新增禁用词在 `tools/check_leak.py` 的 `THIRDPARTY_RE` 维护。
2. **禁止内部信息**：内网域名、基础设施路径、开发者机器路径、凭证字面量。
3. **文档白名单**：对外文档只允许 README / LICENSE / CONTRIBUTING / docs/API.md / examples。
   方案、计划、路线图、内部流程文档一律不入库。
4. **凭证纪律**：凭证只走环境变量或 `~/.openwm/credentials.env`（gitignore 已覆盖 `.env`），
   任何密钥字面量不得出现在代码、测试、文档中。

## 数据域与接口规范

- 新增/修改数据域：在 `src/openwm/_catalog/domains/<域>.yaml` 操作，必须
  bump 域 `version`（semver），并通过 `validate_catalog.py`（函数/指标码必须可回溯到
  `generated/` 清单，防编造）。
- 生成物 `src/openwm/_catalog/generated/*.json` **禁止手改**：由维护者用
  `tools/extract_from_scripts.py` 从上游同步（含命名空间白名单与文本净化策略）。
- 友好 API（`src/openwm/api.py`）改动必须同步 `FRIENDLY_INDEX` 注册表
  （`tests/test_api.py` 强制两者一致），方法首参统一 `symbol`。

## 许可政策

- 整项目采用 **PolyForm Noncommercial 1.0.0**（见 LICENSE）：贡献即同意以该许可发布。
- 任何商业使用需项目维护方另行授权；不得引入与该许可不兼容的第三方代码。

## 提交信息

- 使用简明前缀：`feat(scope):` / `fix(scope):` / `docs:` / `test:` / `chore:`；
- 一次提交一个语义；改目录必须同提交重生成 API.md。
