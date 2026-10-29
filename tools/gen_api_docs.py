#!/usr/bin/env python3
"""Render docs/API.md from the packaged catalog + friendly API registry.

核心优先结构：主体 = 四大类核心接口表（友好层）+ 指标组；全量底层函数目录收进
文末折叠附录。Deterministic; `--check` verifies the on-disk doc matches (drift gate).

Usage:
  python3 tools/gen_api_docs.py          # write docs/API.md
  python3 tools/gen_api_docs.py --check  # exit 1 on drift
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _introspect import (  # noqa: E402
    FALLBACK_RETURNS, RETURNS_OVERRIDES, method_example, method_params,
    return_shape_for, underlying_fn,
)
from wmshare.api import FRIENDLY_INDEX, FRIENDLY_NAMESPACES  # noqa: E402
from wmshare.catalog import catalog_dir, load  # noqa: E402

DOMAINS = catalog_dir() / "domains"
INVENTORY = json.loads((catalog_dir() / "generated" / "inventory.json").read_text(encoding="utf-8"))
INV = {f["name"]: f for f in INVENTORY["functions"]}
CAT = load()
OUT = REPO / "docs" / "API.md"

KIND_CN = {"raw": "原始数据", "computed": "指标", "mixed": "混合"}
CATEGORY_CN = {"market": "市场行情", "fundamentals": "财务基本面",
               "disclosure": "信息披露", "reference": "参考数据"}
CATEGORY_ORDER = ["market", "fundamentals", "disclosure", "reference"]


def esc(s: object) -> str:
    return str(s if s is not None else "").replace("|", "\\|").replace("\n", " ")


def gh_slug(title: str) -> str:
    """GitHub 风格标题锚点：小写、去标点（保留连字符/空格/CJK）、空格转连字符。"""
    import re
    return re.sub(r"[^\w\- ]", "", title.lower()).replace(" ", "-")


TYPE_SHORT = {"float64": "float", "int64": "int"}
UNIT_CN = {"percent": "百分数→小数", "yi_yuan": "亿元→元", "lot": "手→股"}


def fmt_guards(fn: dict) -> str:
    """单位换算与守护声明的紧凑渲染（无声明时为 —）。"""
    parts = [f"`{f}`:{UNIT_CN[u]}" for f, u in (fn.get("units") or {}).items()]
    rng = fn.get("ranges") or {}
    if rng:
        parts.append("量级界 " + "、".join(f"`{f}`" for f in rng))
    checks = [f"`{c}`" for c in fn.get("checks") or []]
    if checks:
        parts.append("不变量 " + "、".join(checks))
    return "；".join(parts) if parts else "—"


def fmt_params(fn: dict, inv: dict) -> str:
    params = fn.get("params")
    if not params:
        sig = inv.get("params") or []
        if not sig:
            return "—"
        return " · ".join(f"`{p['name']}:{p.get('type', 'any')}`" for p in sig) + "（签名）"
    parts = []
    for p in params:
        s = f"{p['name']}:{p['type']}"
        if not p.get("required") and "default" not in p:
            s += "?"
        if "default" in p:
            s += f"={json.dumps(p['default'], ensure_ascii=False)}"
        part = f"`{s}`"
        if p.get("desc"):
            part += f" — {esc(p['desc'])}"
        parts.append(part)
    return " · ".join(parts)


def fmt_returns(fn: dict, inv: dict, shape: dict | None = None) -> str:
    ret = fn.get("returns") or {}
    desc = ret.get("desc") or inv.get("returns") or "—"
    if shape is None and ret.get("shape_ref") == "inventory":
        shape = inv.get("returns_shape")
    if shape and shape.get("kind") == "object":
        desc = "MAP · " + (shape.get("cn") or "结果")
    if shape:
        fields = (shape.get("items") or shape).get("fields") or []
        if fields:
            detail = " / ".join(
                f"{f['name']}:{TYPE_SHORT.get(f.get('type', 'any'), f.get('type', 'any'))}"
                + ("?" if f.get("optional") else "")
                + (f"（{f['cn']}）" if f.get("cn") else "")
                for f in fields)
            desc += "；字段 " + detail
    return esc(desc)


def doc_hidden(fn: dict) -> bool:
    """脚本专用/内部辅助函数不进公开文档（保留在目录中，cli.call 仍可调）。"""
    if fn.get("status") == "internal":
        return True
    short = fn["name"].split(".", 1)[-1]
    return short.startswith(("index_where_", "index_field")) or short.endswith("_bin_expr")


def _split_top_args(s: str) -> list[str] | None:
    """按顶层逗号切分参数串；引号/括号不平衡时返回 None。"""
    args: list[str] = []
    depth, cur, quote = 0, "", ""
    for ch in s:
        if quote:
            cur += ch
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            cur += ch
        elif ch in "([{":
            depth += 1
            cur += ch
        elif ch in ")]}":
            depth -= 1
            cur += ch
        elif ch == "," and depth == 0:
            args.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if depth != 0 or quote:
        return None
    if cur.strip():
        args.append(cur.strip())
    return args


def _py_literal(js: str) -> object | None:
    """目录示例里的 JS 风格字面量 → Python 值；含标识符/调用（如 LatestIndexKey()）时返回 None。"""
    import ast
    import re
    t = js.strip()
    if not t:
        return None
    relaxed = re.sub(r"\btrue\b", "True", re.sub(r"\bfalse\b", "False",
                     re.sub(r"\b(?:nil|null)\b", "None", t)))
    for candidate in (t, relaxed):
        try:
            return ast.literal_eval(candidate)
        except (ValueError, SyntaxError):
            continue
    return None


def sdk_example(fn: dict, inv: dict) -> str:
    """把目录示例机械转写为 cli.call kwargs 形式；参数含非字面量时宁缺毋编（返回空串）。"""
    ex = fn.get("example") or inv.get("example") or ""
    if not ex or "(" not in ex or not ex.endswith(")"):
        return ""
    name, _, argstr = ex[:-1].partition("(")
    if name.strip() != fn["name"]:
        return ""
    args = _split_top_args(argstr)
    if args is None:
        return ""
    sig = fn.get("params") or inv.get("params") or []
    names = [p["name"] for p in sig]
    if len(args) > len(names):
        return ""
    vals = [_py_literal(a) for a in args]
    if not all(v is not None for v in vals):
        return ""
    kw = ", ".join(f"{n}={v!r}" for n, v in zip(names, vals))
    return f'cli.call("{fn["name"]}"{", " + kw if kw else ""})'


def ns_title(ns: str) -> str:
    """命名空间标题：取类 docstring 首句（到句号/括号/冒号为止），防编造。"""
    import inspect
    import re as _re
    doc = inspect.getdoc(FRIENDLY_NAMESPACES[ns]) or ""
    head = _re.split(r"[。：（(:]", doc.strip(), 1)[0].strip()
    return head or ns


def core_table(cat: str, merged: dict[str, dict]) -> list[str]:
    """核心接口表：接口｜说明｜参数｜返回｜示例（自友好层签名与目录 shape 机械生成）。

    同一命名空间的接口归入一个 `###` 小节（保持 FRIENDLY_INDEX 顺序），文档
    组织随门面结构走：新命名空间自动成节。
    """
    rows = [r for r in FRIENDLY_INDEX if r[0] == cat]
    if not rows:
        return []
    groups: list[tuple[str, list[tuple[str, str, str, str, str]]]] = []
    for r in rows:
        if not groups or groups[-1][0] != r[1]:
            groups.append((r[1], []))
        groups[-1][1].append(r)
    out: list[str] = []
    for ns, grp in groups:
        out += [f"### {ns_title(ns)}（`cli.{ns}`）", ""]
        out += ["| 接口 | 说明 | 参数 | 返回 | 示例 |", "|---|---|---|---|---|"]
        for _, ns_, method, cn, underlying in grp:
            cls = FRIENDLY_NAMESPACES[ns]
            params = method_params(cls, method)
            sig = ", ".join(
                f"{p.name}:{p.py_ann}" if p.required else f"{p.name}:{p.py_ann}={p.default}"
                for p in params) or "—"
            fn_key = underlying_fn(underlying)
            if fn_key:
                shape = return_shape_for(CAT, ns, method, underlying)
                ret = fmt_returns(merged.get(fn_key, {}), INV.get(fn_key, {}), shape=shape)
                ret = RETURNS_OVERRIDES.get((ns, method), ret)
            else:
                ret = FALLBACK_RETURNS.get((ns, method), "—")
            ex = method_example(ns, method, params)
            out.append(f"| `cli.{ns}.{method}(...)` | {esc(cn)} | `{esc(sig)}` | {ret} | `{esc(ex)}` |")
        out.append("")
    return out


def metric_groups_lines(doc: dict) -> list[str]:
    lines: list[str] = []
    for g in doc.get("metric_groups") or []:
        lines.append(f"#### 指标组 {g['cn']}（{g['id']}）")
        lines.append(f"{esc(g['caliber'])}" + (f"（单位 {esc(g['unit'])}）" if g.get("unit") else ""))
        lines.append("")
        lines += ["| 指标代码 | 中文名 | 量级守护 |", "|---|---|---|"]
        for m in g.get("metrics") or []:
            guard = ""
            if m.get("unit") or m.get("range"):
                unit = UNIT_CN.get(m.get("unit", ""), "")
                rng = f"范围 {m['range'][0]}…{m['range'][1]}" if m.get("range") else ""
                guard = " · ".join(x for x in (unit, rng) if x)
            lines.append(f"| `{m['code']}` | {esc(m.get('cn', ''))} | {guard} |")
        lines.append("")
    return lines


def render_domain(doc: dict) -> list[str]:
    """附录域节：域合同（描述/单位/notes）+ 底层函数表（不含指标组，其在文档主体）。"""
    kind = doc["kind"]
    lines = [
        f"#### {doc['cn']}（`{doc['id']}`）",
        "",
        f"**性质**：{KIND_CN.get(kind, kind)} · **版本**：{doc['version']}  ",
        f"{esc(doc['description']).strip()}",
    ]
    if doc.get("data_origin"):
        lines.append(f"数据来源：{'、'.join(doc['data_origin'])}。")
    if doc.get("units"):
        lines.append("单位口径：" + "；".join(f"{k}={esc(v)}" for k, v in doc["units"].items()) + "。")
    for n in doc.get("notes") or []:
        lines.append(f"- {esc(n)}")
    lines.append("")

    fns = [f for f in (doc.get("functions") or []) if not doc_hidden(f)]
    if fns:
        lines += ["| 函数 | 中文 | 性质 | 层 | 参数 | 返回 | 单位与守护 |",
                  "|---|---|---|---|---|---|---|"]
        for fn in fns:
            inv = INV.get(fn["name"], {})
            k = fn.get("kind") or kind
            ex = sdk_example(fn, inv)
            shape = None
            # 附录只对规范化函数与显式 shape_ref 展开字段，避免无关大 shape 膨胀。
            if fn.get("normalize_with") or (fn.get("returns") or {}).get("shape_ref") == "inventory":
                try:
                    shape = CAT.function(fn["name"]).get("returns_shape")
                except Exception:
                    shape = None
            status = f" ({fn['status']})" if fn.get("status") and fn["status"] != "stable" else ""
            lines.append(
                f"| `{fn['name']}` | {esc(fn['cn'])} | {KIND_CN.get(k, k)} | {fn['layer']}{status} | "
                f"{fmt_params(fn, inv)} | {fmt_returns(fn, inv, shape=shape)} | {fmt_guards(fn)} |"
                + (f" 例：`{esc(ex)}`" if ex else ""))
        lines.append("")
        hidden_n = len(doc.get("functions") or []) - len(fns)
        if hidden_n:
            lines.append(f"> 另有 {hidden_n} 个索引/内部辅助函数未列入本文档，仍可经 `cli.call(...)` 调用。")
            lines.append("")
    return lines


def overview_table(docs: list[dict]) -> list[str]:
    """能力总览：数据域｜核心能力（L0 中文名）｜单位口径——全部取自目录，防编造。"""
    out = ["| 数据域 | 核心能力 | 单位口径 |", "|---|---|---|"]
    for d in sorted(docs, key=lambda x: (CATEGORY_ORDER.index(x["category"]), x["id"])):
        l0 = [f["cn"] for f in (d.get("functions") or []) if f.get("layer") == "L0"]
        if l0:
            capability = "、".join(l0[:5]) + ("…" if len(l0) > 5 else "")
        elif d.get("metric_groups"):
            capability = "指标组：" + "、".join(g["cn"] for g in d["metric_groups"][:5]) + "…"
        else:
            capability = "公司档案：名称/行业/组织类型/上市日期"
        units = "；".join(f"{k}={v}" for k, v in (d.get("units") or {}).items()) or "—"
        out.append(f"| `{d['id']}`（{d['cn']}） | {esc(capability)} | {esc(units)} |")
    out.append("")
    return out


def build() -> str:
    docs = [yaml.safe_load(p.read_text(encoding="utf-8")) for p in sorted(DOMAINS.glob("*.yaml"))]
    total_fn = sum(len(d.get("functions") or []) for d in docs)
    total_groups = sum(len(d.get("metric_groups") or []) for d in docs)
    metric_count = json.loads(
        (catalog_dir() / "generated" / "metrics.json").read_text(encoding="utf-8"))["count"]
    by_cat = {cat: sorted((x for x in docs if x["category"] == cat), key=lambda x: x["id"])
              for cat in CATEGORY_ORDER}
    merged = {fn["name"]: fn for d in docs for fn in (d.get("functions") or [])}
    out = [
        "# API 参考",
        "",
        "<!-- GENERATED by tools/gen_api_docs.py — do not hand-edit -->",
        "",
        f"共 **{len(docs)}** 个数据域 · **{len(FRIENDLY_INDEX)}** 个核心接口 · "
        f"**{total_groups}** 个指标组（指标目录全量 {metric_count} 个指标代码）；"
        f"全量 {total_fn} 个底层函数见文末折叠附录。",
        "",
        "## 能力总览",
        "",
        "- **额度**：开放平台账号自带免费档额度（500 次/小时、5,000 次/日），"
        "更高额度与条款以开放平台为准。",
        "- **凭证即用**：在开放平台获取 client_id/api-key，"
        "构造参数 / `WMSHARE_*` 环境变量 / `~/.wmshare/credentials.env` 任一配置即可调用核心接口。",
        "- **认证与限流**：401/403 抛 `AuthError`，429 抛 `LimitError(code=\"rate_limited\")`；"
        "错误消息即完整指引——附有申请自己的 AppID 的步骤与配置方法。",
        "- **目录随包、离线可查**：全部函数与指标代码随 wheel 分发；命名空间带类型签名"
        "（`py.typed`），IDE 直接补全。",
        "- **单位统一 + 数据守护**：返回值统一基础单位（比率/涨跌幅=小数、金额/市值=元、"
        "A 股成交量=股）；每次返回前按目录声明做量级守护与关系不变量校验，违例抛 "
        "`DataError` 而非交给你错误量级的数据。取原始口径：`_raw=True`（store 原始行）、"
        "`_units=\"native\"`（脚本输出单位）、`Client(validate=False)`（关校验留换算）。",
        "",
    ]
    out += overview_table(docs)
    out += [
        "性质标注：**原始数据** = 披露/直采数据（含外部源算好的）；**指标** = 平台公式计算的派生指标。",
        "",
        "参数统一 `symbol`（6 位裸码）。机器可读合同：[openapi.json](openapi.json) · "
        "交互浏览：[swagger.html](swagger.html) · 完整优势与口径说明见 "
        "[README](../README.md)。",
        "",
        "| 分类 | 数据域 |", "|---|---|",
    ]
    for cat in CATEGORY_ORDER:
        cells = ", ".join(f"`{d['id']}`（{d['cn']}）" for d in by_cat[cat])
        out.append(f"| **{CATEGORY_CN[cat]}** | {cells} |")
    out += [
        "",
        "## 数据目录（离线）",
        "",
        "目录随包分发、纯本地读取（零网络）：",
        "",
        "```python",
        "import wmshare",
        "",
        "cat = wmshare.load()          # 数据目录对象（离线，不产生任何请求）",
        "hits = cat.search(\"股息\")     # 跨函数 + 指标代码混合检索（默认返回 ≤20 条）",
        "cat.function(\"bonus.snapshot_yield_ttm\")[\"params\"]   # 函数合同：参数/返回/示例",
        "```",
        "",
        "| 方法 | 说明 |", "|---|---|",
        f"| `cat.function(name)` | 函数合同：params / returns_shape / 单位与守护声明 / 示例 |",
        "| `cat.domain(id)` | 域合同：描述 / 单位口径 / notes |",
        "| `cat.metric(code)` | 指标条目（精选组带单位与守护声明） |",
        "| `cat.metric_meta(code)` | 精选指标的单位换算 / 量级守护声明 |",
        "| `cat.metric_groups()` | 全部指标组摘要（id / cn / 数量） |",
        "| `cat.metrics_in_group(group)` | 组内全部精选指标 |",
        f"| `cat.search(query, kind=, limit=)` | 函数 + 指标混合检索（kind: all/function/metric） |",
        "| `cat.functions_by_domain()` | 域 → 函数名清单 |",
        "| `cat.namespaces()` | 全部 XS 命名空间 |",
        "| `cat.inventory_params(name)` | 底层签名参数（L1 精简条目兜底） |",
        "| `cat.stats()` | 域 / 函数 / 指标计数与 upstream rev |",
        "",
    ]

    for cat in CATEGORY_ORDER:
        out.append(f"## {CATEGORY_CN[cat]}")
        out.append("")
        out += core_table(cat, merged)
        if any(d.get("metric_groups") for d in by_cat[cat]):
            out += ["---", ""]
        for d in by_cat[cat]:
            out += metric_groups_lines(d)

    out += [
        "## 附录：全量底层函数目录（进阶）",
        "",
        "底层函数经 `cli.call(\"ns.fn\", ...)` 调用（友好层未覆盖的命名空间有类型化门面，"
        "如 `cli.bonus.query_list(...)`）；单位口径与域说明随域列出。",
        "",
        "<details>",
        "<summary><b>展开全量底层函数目录</b></summary>",
        "",
    ]
    for cat in CATEGORY_ORDER:
        out.append(f"### {CATEGORY_CN[cat]}")
        out.append("")
        for d in by_cat[cat]:
            out += render_domain(d)
    out += ["</details>", ""]
    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    body = build()
    if args.check:
        if not OUT.is_file() or OUT.read_text(encoding="utf-8") != body:
            print("gen_api_docs drift: docs/API.md", file=sys.stderr)
            return 1
        print("gen_api_docs ok")
        return 0
    OUT.write_text(body, encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)} ({len(body)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
