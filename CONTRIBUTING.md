# 贡献指南与项目规范

感谢关注 finpipe。本文件同时是**内容规范**：违反任一条会被 CI 门禁拦截。

## 提交前门禁（全部必须通过）

```bash
python3 tools/check_leak.py         # 内容规范扫描（见下）
python3 tools/validate_catalog.py   # 域目录合同 + 防编造回溯
python3 tools/gen_api_docs.py       # 重生成 docs/API.md（改了目录必须重跑）
python3 tools/gen_typed_api.py      # 重生成类型化门面 docs 同源
python3 tools/gen_openapi.py        # 重生成 docs/openapi.json + swagger.html
pytest --cov=finpipe --cov-fail-under=85   # 全部测试（不联网）+ 覆盖率门禁
python3 -m mypy                     # 类型检查
```

真实取数冒烟（需要凭证）：`FINPIPE_LIVE=1 pytest tests/test_live.py`——覆盖全部 44 个
核心接口与多个标的，做数值合理性断言（日期有序、价格为正、率类口径等）。内置体验
AppID 是共享池，遇到 401/429 请按 README「免费额度与凭证」申请自己的 AppID。

文档一致性由 `tests/test_docs.py` 强制：API.md 的参数/示例/指标组/附录与目录逐项比对，
README 代码块真实执行，README 引用的指标代码与接口必须存在，docstring 单位口径必须与
目录一致。改了文档或接口后直接跑 pytest 即可发现不一致。

CI（`.github/workflows/ci.yml`）在每次 push/PR 上跑同样的门禁。

## 内容规范（check_leak 强制）

1. **禁止第三方产品/数据商引用**：不得出现任何第三方数据产品、数据商或竞品名称
   （包括对标措辞、数据来源点名、商标）。描述数据来源使用中性词（"交易所披露"、
   "平台数据源"等）。新增禁用词在 `tools/check_leak.py` 的 `THIRDPARTY_RE` 维护。
   **唯一例外**：README 的「与 主流数据服务 对比」章节允许点名 数据服务（经维护者批准的
   竞品对比例外，见 `THIRDPARTY_ALLOWED_BY_FILE`）；其余名称、其余位置一律禁止。
2. **禁止内部信息**：内网域名、基础设施路径、开发者机器路径、凭证字面量。
3. **文档白名单**：对外文档只允许 README / LICENSE / CONTRIBUTING / docs/API.md / examples。
   方案、计划、路线图、内部流程文档一律不入库。
4. **凭证纪律**：用户凭证只走环境变量或 `~/.finpipe/credentials.env`（gitignore 已覆盖
   `.env`），任何密钥字面量不得出现在代码、测试、文档中。唯一例外是随包内置的体验
   appid：以混淆 blob 形式存放于 `src/finpipe/_experience.py`，其**明文**在
   `check_leak.py` 的 `FORBIDDEN_SUBSTRINGS` 中列为禁用——任何跟踪文件出现明文即 FAIL。

## 数据域与接口规范

- **随包目录是维护者同步的发布物**：`generated/` 清单由维护者从上游数据平台
  同步冻结（`tools/extract_from_scripts.py`，含命名空间白名单、文本净化与指标
  策展过滤）。贡献者**无需也无法**自行重建目录；新增数据域或指标请提 issue，
  由维护者评估后同步。发布的是上游指标的**策展子集**，README 与文档表述保持一致。
- 新增/修改数据域：在 `src/finpipe/_catalog/domains/<域>.yaml` 操作，必须
  bump 域 `version`（semver），并通过 `validate_catalog.py`（函数/指标码必须可回溯到
  `generated/` 清单，防编造）。
- 生成物 `src/finpipe/_catalog/generated/*.json` **禁止手改**：由维护者用
  `tools/extract_from_scripts.py` 从上游同步（含命名空间白名单与文本净化策略）。
- 友好 API（`src/finpipe/api/` 包）改动必须同步 `FRIENDLY_INDEX` 注册表
  （`tests/test_api.py` 强制两者一致），方法首参统一 `symbol`。
- 命名空间映射：友好层的 `statements`/`dividend` 对应目录命名空间
  `rptdom`/`bonus`（见 `src/finpipe/api/__init__.py` 的 `_FRIENDLY_NS_TO_CATALOG`）；
  未显式包装的目录函数经 `_Api.__getattr__` 目录感知委托直达，
  目录之外的名字必须 AttributeError（`tests/test_api.py` 强制）。

## 运行示例

```bash
pip install -e ".[dev,dataframe]"
python examples/quickstart.py          # 需要凭证（或用内置体验 appid）
python examples/catalog_tour.py        # 离线可跑：无需凭证、不联网
python examples/error_handling.py      # 离线：错误分类体系演示
python examples/dividend_screener.py   # 高股息筛选（需凭证）
python examples/pandas_analysis.py     # DataFrame 分析（需凭证 + pandas）
```

## 许可政策

- 整项目采用 **MIT**（见 LICENSE）：贡献即同意以 MIT 发布。
- 不得引入与 MIT 不兼容的第三方代码。

## 提交信息

- 使用简明前缀：`feat(scope):` / `fix(scope):` / `docs:` / `test:` / `chore:`；
- 一次提交一个语义；改目录必须同提交重生成 API.md。
