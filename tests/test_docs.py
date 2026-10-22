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
GROUP_ROW = re.compile(r"^\| `(\$[\w.]+)` \| (.*?) \|$")
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
                return {"success": True, "data": {"result": [{"ok": True}]}}
        return R()


@pytest.fixture(scope="module")
def cli():
    from finpipe.client import Client
    return Client(base_url="https://t", client_id="i", client_secret="s",
                  catalog=CAT, session=FakeSession())


def core_rows() -> list[tuple[str, str, str, str]]:
    rows = []
    for line in API_MD.splitlines():
        m = CORE_ROW.match(line)
        if m:
            rows.append((m.group(1), m.group(2), m.group(4).replace("\\|", "|"), m.group(6)))
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


def test_api_md_core_interfaces_exact():
    rows = core_rows()
    got = [(ns, m) for ns, m, _, _ in rows]
    want = [(ns, m) for _, ns, m, _, _ in FRIENDLY_INDEX]
    assert sorted(got) == sorted(want), "核心接口表与 FRIENDLY_INDEX 不一致"
    assert len(got) == len(set(got)), "核心接口表存在重复行"


def test_api_md_params_match_signatures():
    for ns, method, cell, _ in core_rows():
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


def test_api_md_metric_groups_match_catalog():
    doc_groups: dict[str, list[tuple[str, str]]] = {}
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
            doc_groups[current].append((g.group(1), g.group(2)))

    catalog_groups = {}
    for d in CAT.domains.values():
        for g in d.get("metric_groups") or []:
            catalog_groups[g["id"]] = [(m["code"], m["cn"]) for m in g["metrics"]]

    assert set(doc_groups) == set(catalog_groups), "指标组集合不一致"
    for gid, pairs in catalog_groups.items():
        assert doc_groups[gid] == pairs, f"指标组 {gid} 的指标代码/中文名与目录不一致"


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
    for ns, method, _, example in core_rows():
        assert example.startswith(f"cli.{ns}.{method}("), f"{ns}.{method} 示例串不匹配"
        eval(example, {"cli": cli})  # noqa: S307 - 文档内生成的示例，受仓库控制


def test_readme_python_blocks_execute(cli):
    import finpipe
    blocks = re.findall(r"```python\n(.*?)```", README, re.S)
    assert blocks, "README 缺少 python 示例"
    original = finpipe.Client
    finpipe.Client = lambda *a, **k: cli  # 示例里的构造不访问网络
    try:
        for block in blocks:
            exec(compile(block, "README.md", "exec"), {"__name__": "__readme__"})
    finally:
        finpipe.Client = original


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


def test_readme_references_are_valid():
    # 指标代码必须存在于指标目录
    codes = set(re.findall(r"\$[A-Za-z_][A-Za-z0-9_]*", README))
    metrics = {m["code"] for m in CAT.metrics["metrics"]}
    assert codes <= metrics, f"README 引用了不存在的指标代码：{codes - metrics}"
    # cli.ns.method 必须真实存在
    for ns, method in set(re.findall(r"cli\.(\w+)\.(\w+)\(", README)):
        cls = FRIENDLY_NAMESPACES.get(ns) or GENERATED_NAMESPACES.get(ns)
        assert cls is not None and hasattr(cls, method), f"README 引用了不存在的接口 {ns}.{method}"
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
        container = resp.get("items", resp) if resp.get("type") == "array" else resp
        assert set(container.get("properties") or {}) == {f["name"] for f in fields}, \
            f"{ns}.{method} 响应字段与目录 returns_shape 不一致"
