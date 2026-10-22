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
    FALLBACK_RETURNS, method_example, method_params, underlying_fn,
)
from finpipe.api import FRIENDLY_INDEX, FRIENDLY_NAMESPACES  # noqa: E402
from finpipe.catalog import catalog_dir  # noqa: E402

DOMAINS = catalog_dir() / "domains"
INVENTORY = json.loads((catalog_dir() / "generated" / "inventory.json").read_text(encoding="utf-8"))
INV = {f["name"]: f for f in INVENTORY["functions"]}
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


def fmt_returns(fn: dict, inv: dict) -> str:
    ret = fn.get("returns") or {}
    desc = ret.get("desc") or inv.get("returns") or "—"
    shape = inv.get("returns_shape") if ret.get("shape_ref") == "inventory" else None
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


def core_table(cat: str, merged: dict[str, dict]) -> list[str]:
    """核心接口表：接口｜说明｜参数｜返回｜示例（自友好层签名与目录 shape 机械生成）。"""
    rows = [r for r in FRIENDLY_INDEX if r[0] == cat]
    if not rows:
        return []
    out = ["| 接口 | 说明 | 参数 | 返回 | 示例 |", "|---|---|---|---|---|"]
    for _, ns, method, cn, underlying in rows:
        cls = FRIENDLY_NAMESPACES[ns]
        params = method_params(cls, method)
        sig = ", ".join(
            f"{p.name}:{p.py_ann}" if p.required else f"{p.name}:{p.py_ann}={p.default}"
            for p in params) or "—"
        fn_key = underlying_fn(underlying)
        if fn_key:
            ret = fmt_returns(merged.get(fn_key, {}), INV.get(fn_key, {}))
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
        lines += ["| 指标代码 | 中文名 |", "|---|---|"]
        for m in g.get("metrics") or []:
            lines.append(f"| `{m['code']}` | {esc(m.get('cn', ''))} |")
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
        lines += ["| 函数 | 中文 | 性质 | 层 | 参数 | 返回 |", "|---|---|---|---|---|---|"]
        for fn in fns:
            inv = INV.get(fn["name"], {})
            k = fn.get("kind") or kind
            ex = sdk_example(fn, inv)
            status = f" ({fn['status']})" if fn.get("status") and fn["status"] != "stable" else ""
            lines.append(
                f"| `{fn['name']}` | {esc(fn['cn'])} | {KIND_CN.get(k, k)} | {fn['layer']}{status} | "
                f"{fmt_params(fn, inv)} | {fmt_returns(fn, inv)} |"
                + (f" 例：`{esc(ex)}`" if ex else ""))
        lines.append("")
        hidden_n = len(doc.get("functions") or []) - len(fns)
        if hidden_n:
            lines.append(f"> 另有 {hidden_n} 个索引/内部辅助函数未列入本文档，仍可经 `cli.call(...)` 调用。")
            lines.append("")
    return lines


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
        "性质标注：**原始数据** = 披露/直采数据（含外部源算好的）；**指标** = 平台公式计算的派生指标。",
        "",
        "**开箱即用**：`pip install wm-finpipe` 后 `finpipe.Client()` 无需配置即可调用核心接口"
        "（内置体验 appid，额度有限）；参数统一 `symbol`（6 位裸码）。"
        "机器可读合同：[openapi.json](openapi.json) · 交互浏览：[swagger.html](swagger.html)。",
        "",
        "| 分类 | 数据域 |", "|---|---|",
    ]
    for cat in CATEGORY_ORDER:
        cells = ", ".join(f"`{d['id']}`（{d['cn']}）" for d in by_cat[cat])
        out.append(f"| **{CATEGORY_CN[cat]}** | {cells} |")
    out.append("")

    for cat in CATEGORY_ORDER:
        out.append(f"## {CATEGORY_CN[cat]}")
        out.append("")
        out += core_table(cat, merged)
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
