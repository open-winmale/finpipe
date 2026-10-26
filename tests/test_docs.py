"""文档-代码一致性门禁：README / API.md / quickstart 与目录、签名必须逐项对得上。

覆盖三类漂移：
  1. 计数与清单：文档里的域数/函数数/接口数/指标数、核心接口表、指标组表、附录函数表
  2. 参数与示例：表格参数 == 方法签名；每个示例真实可执行；README 代码块可运行
  3. 表述与口径：docstring 参数名存在、单位口径（小数/百分数）与目录一致

这些测试独立于生成器实现（直接解析文档文本 + inspect 签名），能抓住生成器本身的 bug。
"""
from __future__ import annotations

import ast
import inspect
import json
import re
from pathlib import Path

import pytest

from finpipe.api import FRIENDLY_INDEX, FRIENDLY_NAMESPACES, GENERATED_NAMESPACES
from finpipe.catalog import load

REPO = Path(__file__).resolve().parents[1]
API_MD = (REPO / "docs" / "API.md").read_text(encoding="utf-8")
README = (REPO / "README.md").read_text(encoding="utf-8")
CAT = load()

CORE_ROW = re.compile(
    r"^\| `cli\.(\w+)\.(\w+)\(\.\.\.\)` \| (.*?) \| `([^`]*)` \| (.*?) \| `(cli\.[^`]*)` \|$")
GROUP_HEAD = re.compile(r"^#### 指标组 (.+?)（([\w.]+)）$")
GROUP_ROW = re.compile(r"^\| `(\$[\w.]+)` \| (.*?) \| (.*?) \|$")
FN_ROW = re.compile(r"^\| `([a-z][\w]*\.[a-z][\w]*)` \| (.*?) \| (?:原始数据|指标) \|")


class FakeSession:
    """离线传输：token + eval 固定成功，返回列表（覆盖 last() 取首行的形态）。"""

    def post(self, url, json=None, data=None, headers=None, timeout=None):
        class R:
            status_code = 200
            text = "{}"
            headers = {}

            def raise_for_status(self):
                pass

            def json(self):
                if url.endswith("/v1/oauth/token"):
                    return {"data": {"access_token": "tok", "expires_in": 3600}}
                lines = (json or {}).get("xs_lines") or []
                # window_stats 的脚本显式返回 MAP（rows/dps/total）
                if any("bonus.query_list" in ln for ln in lines) and \
                        any('"rows"' in ln for ln in lines):
                    return {"success": True,
                            "data": {"result": {"rows": [], "dps": 0.0, "total": 0.0}}}
                return {"success": True, "data": {"result": [{"ok": True}]}}
        return R()


@pytest.fixture(scope="module")
def cli():
    from finpipe.client import Client
    return Client(base_url="https://t", client_id="i", client_secret="s",
                  catalog=CAT, session=FakeSession())


def core_rows() -> list[tuple[str, str, str, str, str]]:
    rows = []
    for line in API_MD.splitlines():
        m = CORE_ROW.match(line)
        if m:
            rows.append((m.group(1), m.group(2), m.group(4).replace("\\|", "|"),
                         m.group(5), m.group(6)))
    return rows


def parse_sig_cell(cell: str) -> list[tuple[str, str, str | None]]:
    """'symbol:str, n:int=120, adj:str | None=None' → [(name, annotation, default)]。"""
    out = []
    for part in [p.strip() for p in cell.split(",") if p.strip()]:
        if part == "—":
            continue
        name, _, ann = part.partition(":")
        ann = ann.strip()
        optional = ann.endswith("?")
        if optional:
            ann = ann[:-1]
        default = None
        if "=" in ann:
            ann, _, default = ann.partition("=")
        out.append((name.strip(), ann.strip(), default))
    return out


# ---------------------------------------------------------------- 计数与清单
def test_api_md_counts_match_catalog():
    groups = sum(len(d.get("metric_groups") or []) for d in CAT.domains.values())
    metrics = CAT.metrics["count"]
    assert f"共 **{len(CAT.domains)}** 个数据域" in API_MD
    assert f"**{len(FRIENDLY_INDEX)}** 个核心接口" in API_MD
    assert f"**{groups}** 个指标组" in API_MD
    assert f"{metrics} 个指标代码" in API_MD
    assert f"全量 {CAT.stats()['functions']} 个底层函数" in API_MD


def test_readme_counts_match_catalog():
    stats = CAT.stats()
    groups = sum(len(d.get("metric_groups") or []) for d in CAT.domains.values())
    curated = sum(len(g.get("metrics") or []) for d in CAT.domains.values()
                  for g in d.get("metric_groups") or [])
    assert f"{stats['functions']} 个底层函数" in README
    assert f"{len(FRIENDLY_INDEX)} 个核心接口" in README
    assert f"{stats['metric_catalog_total']} 个指标代码" in README
    assert f"{len(CAT.domains)} 个数据域" in README
    assert f"{groups} 个指标组" in README
    assert f"{curated} 个精选常用指标代码" in README


def test_api_module_docstring_counts_match_catalog():
    """门面模块 docstring 的底层函数计数必须与目录一致（曾停留 155 而目录已 164）。"""
    src = (REPO / "src" / "finpipe" / "api" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r"(\d+) 个底层函数零遮蔽", src)
    assert m, "模块 docstring 缺少底层函数计数"
    assert int(m.group(1)) == CAT.stats()["functions"], \
        "api/__init__.py 模块 docstring 的函数计数与目录漂移"


def test_api_md_core_interfaces_exact():
    rows = core_rows()
    got = [(ns, m) for ns, m, _, _, _ in rows]
    want = [(ns, m) for _, ns, m, _, _ in FRIENDLY_INDEX]
    assert sorted(got) == sorted(want), "核心接口表与 FRIENDLY_INDEX 不一致"
    assert len(got) == len(set(got)), "核心接口表存在重复行"


def test_api_md_params_match_signatures():
    for ns, method, cell, _, _ in core_rows():
        sig = inspect.signature(getattr(FRIENDLY_NAMESPACES[ns], method))
        expected = []
        for name, p in sig.parameters.items():
            if name == "self" or name.startswith("_"):
                continue
            ann = p.annotation if isinstance(p.annotation, str) else str(p.annotation)
            default = None if p.default is inspect.Parameter.empty else repr(p.default)
            expected.append((name, ann, default))
        parsed = parse_sig_cell(cell)
        assert parsed == expected, f"{ns}.{method} 文档参数 {parsed} != 签名 {expected}"


def test_api_md_last_rows_are_map():
    """last() 包装返回单行/None，不能沿用底层数组的 ARR 描述。"""
    wanted = {("kline", "last"), ("moneyflow", "last"), ("dividend", "last")}
    seen = set()
    for ns, method, _cell, ret, _ in core_rows():
        if (ns, method) in wanted:
            seen.add((ns, method))
            assert "MAP" in ret and "ARR" not in ret, f"{ns}.{method}: {ret}"
    assert seen == wanted


def test_indicator_units_documented_as_decimal():
    assert "0.332 = 33.2%" in README
    assert "0.332 = 33.2%" in API_MD
    assert "15.0 = 15%" not in README
    assert "15.0 = 15%" not in API_MD
    assert "指标层比率统一为小数" in API_MD


def test_api_md_metric_groups_match_catalog():
    doc_groups: dict[str, list[tuple[str, str, str]]] = {}
    current = None
    for line in API_MD.splitlines():
        m = GROUP_HEAD.match(line)
        if m:
            current = m.group(2)
            doc_groups[current] = []
            continue
        if line.startswith("#"):
            current = None
            continue
        if current and (g := GROUP_ROW.match(line)):
            doc_groups[current].append((g.group(1), g.group(2), g.group(3).strip()))

    catalog_groups = {}
    for d in CAT.domains.values():
        for g in d.get("metric_groups") or []:
            catalog_groups[g["id"]] = [(m["code"], m["cn"]) for m in g["metrics"]]

    assert set(doc_groups) == set(catalog_groups), "指标组集合不一致"
    for gid, pairs in catalog_groups.items():
        got = [(c, cn) for c, cn, _ in doc_groups[gid]]
        assert got == pairs, f"指标组 {gid} 的指标代码/中文名与目录不一致"
        # 守护列：目录声明了 range/unit 的指标，文档必须带守护标注（反之不得空穴来风）
        by_code = {m["code"]: m for d in CAT.domains.values()
                   for g in d.get("metric_groups") or [] for m in g.get("metrics") or []}
        for code, _, guard in doc_groups[gid]:
            m = by_code[code]
            if m.get("range") or m.get("unit"):
                assert guard, f"{code} 目录声明了守护，文档守护列为空"
            else:
                assert not guard, f"{code} 目录无守护声明，文档却写了：{guard}"


def visible_catalog_functions(cat) -> list[str]:
    """与 gen_api_docs.doc_hidden 同规则：排除内部/索引积木类函数。"""
    out = []
    for names in cat.functions_by_domain().values():
        for name in names:
            short = name.split(".", 1)[1]
            if cat.function(name).get("status") == "internal":
                continue
            if short.startswith(("index_where_", "index_field")) or short.endswith("_bin_expr"):
                continue
            out.append(name)
    return out


def test_api_md_appendix_functions_match_catalog():
    appendix = API_MD.split("附录：全量底层函数目录", 1)[1]
    doc_fns = [m.group(1) for m in map(FN_ROW.match, appendix.splitlines()) if m]
    assert sorted(doc_fns) == sorted(visible_catalog_functions(CAT)), \
        "附录函数表与目录（可见函数）不一致"


# ---------------------------------------------------------------- 示例可执行
def test_api_md_examples_execute(cli):
    for ns, method, _, _, example in core_rows():
        assert example.startswith(f"cli.{ns}.{method}("), f"{ns}.{method} 示例串不匹配"
        eval(example, {"cli": cli})  # noqa: S307 - 文档内生成的示例，受仓库控制


class ReadmeClient:
    """README 示例执行用的罐头客户端：返回值与示例注释里的预期输出同量级。

    与 test_units.py 的罐头数据同源（真实 probe 样本），保证注释值不腐烂。
    """

    INDICATORS = {"$PCT_PE_TTM_10Y_LAST": 0.42, "$CUR_IND_ROE_PCT_LAST": 1.0,
                  "$PE_TTM_LAST": 25.5}

    def __init__(self):
        import types
        self.kline = types.SimpleNamespace(
            bars=lambda *a, **k: [{"date": "2026-10-20", "close": 1331.88,
                                   "volume": 3413500.0, "amount": 4525398959.0,
                                   "percent": 0.005215}],
            screen_above_ma20=lambda *a, **k: True,
            index_breadth_summary=lambda *a, **k: {"up": 3200, "down": 2100},
        )
        self.screener = types.SimpleNamespace(
            screen_limit_up=lambda *a, **k: False,
            screen_above_ma20=lambda *a, **k: True,
            screen_momentum_20d=lambda *a, **k: False,
            screen_volume_spike=lambda *a, **k: True,
            # 数值取自 2026-10-24 真实 probe（A 股全市场截面）
            index_breadth_summary=lambda *a, **k: {"total": 5685, "up": 4567, "down": 934,
                                                   "flat": 184, "up_pct": 80.3,
                                                   "down_pct": 16.4, "flat_pct": 3.2,
                                                   "median_pct": 0.015363},
            index_breadth_bins=lambda *a, **k: [
                {"label": "i_涨停", "count": 109, "pct_of_total": 1.9},
                {"label": "h_+5%~10%", "count": 464, "pct_of_total": 8.2},
                {"label": "g_+3%~5%", "count": 829, "pct_of_total": 14.6},
            ],
            index_top_movers=lambda *a, **k: [
                {"symbol": "600519", "name": "贵州茅台", "percent": 0.0052},
            ],
        )
        self.dividend = types.SimpleNamespace(
            yield_ttm=lambda *a, **k: 0.0396,
            screen_quality=lambda *a, **k: True,
            history=lambda *a, **k: [],
        )
        self.indicator = types.SimpleNamespace(
            get=lambda sym, code: self.INDICATORS.get(code, 0.5),
        )
        self.notice = types.SimpleNamespace(
            list=lambda *a, **k: [],
            has_buyback=lambda *a, **k: True,
        )
        self.statements = types.SimpleNamespace(
            income=lambda *a, **k: [], compare=lambda *a, **k: [],
        )
        self.info = types.SimpleNamespace(profile=lambda *a, **k: {})

    @classmethod
    def from_env(cls, *a, **k):
        return cls()

    def call(self, name, **kw):
        return []


@pytest.fixture(scope="module")
def readme_cli():
    return ReadmeClient()


def test_readme_python_blocks_execute(readme_cli):
    import textwrap

    import finpipe
    blocks = re.findall(r"```python\n(.*?)```", README, re.S)
    assert blocks, "README 缺少 python 示例"
    original = finpipe.Client
    finpipe.Client = type("PatchedClient", (ReadmeClient,), {})  # from_env/构造都不联网
    try:
        for block in blocks:
            exec(compile(textwrap.dedent(block), "README.md", "exec"),
                 {"__name__": "__readme__"})
    finally:
        finpipe.Client = original


def test_readme_example_outputs_documented():
    """示例注释里的预期输出必须与罐头数据同值——注释值从此有测试守护。"""
    pairs = [("yield_ttm", "0.0396"),
             ("$PCT_PE_TTM_10Y_LAST", "0.42"),
             ("$CUR_IND_ROE_PCT_LAST", "1.0")]
    for call, value in pairs:
        line = next((ln for ln in README.splitlines() if call in ln and value in ln), None)
        assert line is not None, f"README 示例缺少 {call} 与预期输出 {value} 的对应注释"


def test_readme_units_and_guards_documented():
    """单位与守护的最小行动块必须在 README 成文（2026-10-25 二次瘦身定版）。"""
    for kw in ("单位与数据守护", "DataError", '_units="native"', "validate=False",
               "算好的增值数据", "专业的股息计算", "能力一览"):
        assert kw in README, f"README 缺少关键内容：{kw}"
    assert "量=手" not in README and "volume in lots" not in README, \
        "成交量已统一为股，README 不得再写手"
    # API.md 同步：catalog 章节存在、旧口径文案绝迹
    assert "数据目录（离线）" in API_MD and "cat.search" in API_MD
    assert "差额 / 合并值 × 100" not in API_MD


def test_readme_no_competitor_names():
    """README 零竞品名（2026-10-24 用户定版）：差异化卖点一律自证式表述，防回潮。"""
    assert "数据服务" not in README.lower(), "README 不得出现竞品名（对比历史留在 CHANGELOG）"


def test_readme_is_lean():
    """店面纪律：README 保持精炼（2026-10-25 二次瘦身 206 行），超限先删内容再提限。"""
    assert len(README.splitlines()) <= 215, \
        f"README 膨胀到 {len(README.splitlines())} 行（上限 215）；长内容下沉 docs/ 或删除"


def test_readme_catalog_references_valid():
    """行内 `cat.xxx(...)` 引用必须是 Catalog 真实方法（防止文档凭空写方法名）。"""
    from finpipe.catalog import Catalog
    for meth in set(re.findall(r"cat\.(\w+)\(", README)):
        assert meth == "load" or callable(getattr(Catalog, meth, None)), \
            f"README 引用了不存在的目录方法 cat.{meth}()"


def test_quickstart_calls_are_valid():
    src = (REPO / "examples" / "quickstart.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    checked = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if not (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Attribute)
                and isinstance(f.value.value, ast.Name) and f.value.value.id == "cli"):
            continue
        if f.value.attr == "call":  # cli.call("ns.fn", ...) 走目录级校验
            assert node.args and isinstance(node.args[0], ast.Constant)
            CAT.function(node.args[0].value)
        else:
            cls = FRIENDLY_NAMESPACES.get(f.value.attr) or GENERATED_NAMESPACES.get(f.value.attr)
            assert cls is not None, f"quickstart 引用了不存在的命名空间 {f.value.attr}"
            assert hasattr(cls, f.attr), f"quickstart 引用了不存在的方法 {f.value.attr}.{f.attr}"
            sig = inspect.signature(getattr(cls, f.attr))
            kwargs = {kw.arg: None for kw in node.keywords if kw.arg}
            sig.bind(None, *[None] * len(node.args), **kwargs)
        checked += 1
    assert checked >= 8, f"quickstart 仅识别到 {checked} 个调用，解析可能失效"


# ---------------------------------------------------------------- 表述与口径
def test_docstring_params_exist_in_signature():
    for _, ns, method, _, _ in FRIENDLY_INDEX:
        fn = getattr(FRIENDLY_NAMESPACES[ns], method)
        doc = inspect.getdoc(fn) or ""
        params = set(re.findall(r"^:param (\w+):", doc, re.M))
        sig = set(inspect.signature(fn).parameters) - {"self", "_raw", "_df"}
        assert params <= sig, f"{ns}.{method} docstring 参数 {params - sig} 不在签名中"


def test_unit_wording_matches_catalog():
    """目录说小数，文档就不能说百分数（反之亦然）——曾出现过分红率口径事故。"""
    problems = []
    for _, ns, method, _, underlying in FRIENDLY_INDEX:
        fn_key = underlying.split("[")[0].strip()
        if not re.fullmatch(r"[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*", fn_key):
            continue
        try:
            ret = (CAT.function(fn_key).get("returns") or {}).get("desc") or ""
        except KeyError:
            continue
        cls = FRIENDLY_NAMESPACES[ns]
        doc = (inspect.getdoc(getattr(cls, method)) or "") + (inspect.getdoc(cls) or "")
        if "小数" in ret and "百分数" in doc:
            problems.append(f"{ns}.{method}: 目录=小数，文档出现百分数")
        if "百分数" in ret and "小数" in doc:
            problems.append(f"{ns}.{method}: 目录=百分数，文档出现小数")
    assert not problems, problems


def test_readme_references_are_valid(cli):
    # 指标代码必须存在于指标目录
    codes = set(re.findall(r"\$[A-Za-z_][A-Za-z0-9_]*", README))
    metrics = {m["code"] for m in CAT.metrics["metrics"]}
    assert codes <= metrics, f"README 引用了不存在的指标代码：{codes - metrics}"
    # cli.ns.method 必须运行时可触达：显式方法或目录动态委托（与真实语义一致）
    for ns, method in set(re.findall(r"cli\.(\w+)\.(\w+)\(", README)):
        try:
            getattr(getattr(cli, ns), method)
        except AttributeError:
            raise AssertionError(f"README 引用了不存在的接口 {ns}.{method}") from None
    # 反引号里的域 id 必须存在
    for dom in re.findall(r"`([a-z]+\.[a-z_]+)`", README):
        if dom.split(".")[0] in {d.split(".")[0] for d in CAT.domains}:
            assert dom in CAT.domains, f"README 引用了不存在的域 {dom}"


def test_openapi_matches_signatures_and_returns():
    spec = json.loads((REPO / "docs" / "openapi.json").read_text(encoding="utf-8"))
    ops = {op["operationId"]: op for item in spec["paths"].values() for op in item.values()}
    type_map = {"str": "string", "int": "integer", "float": "number",
                "bool": "boolean", "list[str]": "array", "dict": "object"}
    for _, ns, method, _, underlying in FRIENDLY_INDEX:
        op = ops[f"{ns}_{method}"]
        fn = getattr(FRIENDLY_NAMESPACES[ns], method)
        params = [p for name, p in inspect.signature(fn).parameters.items()
                  if name != "self" and not name.startswith("_")]
        schema = op["requestBody"]["content"]["application/json"]["schema"]
        assert set(schema["properties"]) == {p.name for p in params}
        assert set(schema.get("required") or []) == {
            p.name for p in params if p.default is inspect.Parameter.empty}
        for p in params:
            ann = p.annotation if isinstance(p.annotation, str) else str(p.annotation)
            expected = type_map.get(ann.split("|")[0].strip(), "object")
            assert schema["properties"][p.name]["type"] == expected, f"{ns}.{method}.{p.name}"

        fn_key = underlying.split("[")[0].strip()
        if not re.fullmatch(r"[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*", fn_key):
            continue
        shape = CAT.function(fn_key).get("returns_shape")
        if not shape:
            continue
        fields = (shape.get("items") or shape).get("fields") or []
        if not fields:
            continue
        resp = op["responses"]["200"]["content"]["application/json"]["schema"]
        expected_container = {
            ("kline", "last"): "object",
            ("moneyflow", "last"): "object",
            ("dividend", "last"): "object",
            ("kline", "bars"): "array",
        }
        if (ns, method) in expected_container:
            assert resp.get("type") == expected_container[(ns, method)], \
                f"{ns}.{method} OpenAPI 容器类型错误：{resp.get('type')}"
        if ns == "notice" and method in ("list", "recent", "by_category", "find", "on_date"):
            assert {"date", "title", "url"} <= set(resp.get("items", {}).get("properties") or {}), \
                f"notice.{method} 未记录规范化字段"
        container = resp.get("items", resp) if resp.get("type") == "array" else resp
        assert set(container.get("properties") or {}) == {f["name"] for f in fields}, \
            f"{ns}.{method} 响应字段与目录 returns_shape 不一致"
