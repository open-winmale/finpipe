#!/usr/bin/env python3
"""Sync the packaged data catalog from the upstream source tree (maintainer-only).

This tool is NOT needed at runtime: the Python package ships a frozen copy under
src/openwm/_catalog/generated/. It is read-only against the upstream tree and
applies the project's publishing policy:

  - namespace whitelist  : only first-release in-scope data surfaces
  - text sanitization    : third-party vendor mentions -> neutral wording
  - metric filtering     : strategy-clone metric batches dropped, provenance
                           paths removed (see .internal/MAINTENANCE.md)

Outputs (deterministic; anchored to the upstream git rev):
  src/openwm/_catalog/generated/inventory.json
  src/openwm/_catalog/generated/metrics.json

Usage:
  python3 tools/extract_from_scripts.py [--scripts-root PATH] [--check]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "src" / "openwm" / "_catalog" / "generated"

CATALOG_RE = re.compile(r"^\s*#\s*xs:catalog\s+(\{.*\})\s*$")
SIG_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\s*=\s*func\s*\(([^)]*)\)")

TYPE_MAP = {
    "string": "string", "int": "int", "float64": "float", "float32": "float",
    "bool": "bool", "ARR": "array", "MAP": "object", "any": "any",
}

# ---- 发布政策 -------------------------------------------------------------
# 一期数据面白名单：只发布这些命名空间（.internal/MAINTENANCE.md §3）
INCLUDED_NS = frozenset({"kline", "moneyflow", "notice", "filings", "forecast", "bonus", "rptdom"})
# rptdom 只保留三表透视族（年报 PDF 提取类 rows/notes/note_index 不发布）
RPTDOM_KEEP = frozenset({"statement", "statement_years", "statement_compare", "statement_tree", "statement_audit"})

# 第三方数据商/竞品名 → 中性词（生成文本全字段适用；新增条目须同步 tools/check_leak.py）
SANITIZE_TEXT = {
    "东财": "数据源",
    "聚源混源": "多源混合",
    "理杏仁整理结构": "标准目录结构",
    "巨潮": "披露原文",
    "tencent|sina|sina_rt|eastmoney_quote|eastmoney_kline|eastmoney_ulist": "来源标识枚举",
}

# metrics 过滤：第三方策略对照批次不发布（其余批次为平台自产指标，仅不发布 source 溯源路径）
METRIC_SOURCE_EXCLUDE = ("xs/iwencai_strategy/",)


def sanitize(text: str) -> str:
    for bad, good in SANITIZE_TEXT.items():
        text = text.replace(bad, good)
    return text


def sanitize_tree(obj):
    """对生成结构的全部字符串字段递归净化（含 returns_shape 嵌套 cn）。"""
    if isinstance(obj, dict):
        return {k: sanitize_tree(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_tree(v) for v in obj]
    if isinstance(obj, str):
        return sanitize(obj)
    return obj


def find_scripts_root(cli: str | None) -> Path:
    import os
    if cli:
        p = Path(cli).expanduser().resolve()
        if p.is_dir():
            return p
        raise SystemExit(f"--scripts-root not a directory: {p}")
    env = None
    for var in ("WM_SCRIPTS_ROOT", "SCRIPTS_ROOT"):
        env = env or (Path(os.environ[var]).expanduser().resolve()
                      if os.environ.get(var) else None)
    if env and env.is_dir():
        return env
    for cand in (REPO.parent / "script", REPO.parent / "scripts"):
        if (cand / "sys" / "init.xs").is_file():
            return cand.resolve()
    raise SystemExit("upstream tree not found; set WM_SCRIPTS_ROOT or pass --scripts-root")


def git_rev(root: Path) -> str:
    try:
        out = subprocess.run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=10, check=True)
        return out.stdout.strip()
    except Exception:
        return "unknown"


def parse_signature(params_src: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for chunk in params_src.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = chunk.split()
        if len(parts) >= 2:
            out[parts[0]] = TYPE_MAP.get(parts[1], "any")
        elif parts:
            out[parts[0]] = "any"
    return out


def in_scope(qname: str) -> bool:
    ns, _, fname = qname.partition(".")
    if ns not in INCLUDED_NS:
        return False
    if ns == "rptdom" and fname not in RPTDOM_KEEP:
        return False
    return True


def extract_functions(sr: Path) -> list[dict]:
    entries: dict[str, dict] = {}
    for xs in sorted((sr / "sys").rglob("*.xs")):
        try:
            lines = xs.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for i, line in enumerate(lines):
            m = CATALOG_RE.match(line)
            if not m:
                continue
            try:
                ann = json.loads(m.group(1))
            except json.JSONDecodeError as e:
                print(f"WARN: bad xs:catalog JSON at {xs.name}:{i+1}: {e}", file=sys.stderr)
                continue
            qname = str(ann.get("name") or "").strip()
            if not qname or not in_scope(qname):
                continue
            sig_types: dict[str, str] = {}
            for j in range(i + 1, min(i + 6, len(lines))):
                sm = SIG_RE.match(lines[j])
                if sm and f"{sm.group(1)}.{sm.group(2)}" == qname:
                    sig_types = parse_signature(sm.group(3))
                    break
                if sm:
                    break
            entries[qname] = sanitize_tree({
                "name": qname,
                "cn": str(ann.get("cn") or ""),
                "example": str(ann.get("ex") or ""),
                "returns": str(ann.get("returns") or ""),
                "returns_shape": ann.get("returns_shape") or None,
                "min_args": ann.get("min_args"),
                "params": [{"name": p, "type": sig_types.get(p, "any")}
                           for p in (ann.get("params") or [])],
            })
    return [entries[k] for k in sorted(entries)]


def extract_domains(sr: Path) -> dict[str, dict]:
    domains: dict[str, dict] = {}
    for mf in sorted((sr / "sys").glob("*/manifest.json")):
        try:
            m = json.loads(mf.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        name = m.get("name")
        if name and name in INCLUDED_NS:
            domains[name] = {"entry": m.get("entry") or "",
                             "exports": sorted(m.get("exports") or [])}
    for init in sorted((sr / "sys").glob("*/init.xs")):
        ns = init.parent.name
        if ns in INCLUDED_NS and ns not in domains:
            domains[ns] = {"entry": init.relative_to(sr).as_posix(), "exports": []}
    return dict(sorted(domains.items()))


def extract_preloaded(sr: Path) -> list[str]:
    init = sr / "sys" / "init.xs"
    if not init.is_file():
        return []
    out = set()
    for m in re.finditer(r'xs\.require\("([^"]+)"\)', init.read_text(encoding="utf-8")):
        parts = m.group(1).split("/")
        if not parts[-1].endswith(".xs"):
            continue
        stem = parts[-1].rsplit(".", 1)[0]
        ns = parts[-2] if stem == "init" and len(parts) >= 2 else stem
        if ns in INCLUDED_NS:
            out.add(ns)
    return sorted(out)


def extract_metrics(sr: Path) -> dict:
    p = sr / "xs-lang-extension" / "catalogs" / "metric-memo-catalog.json"
    if not p.is_file():
        return {"count": 0, "metrics": []}
    d = json.loads(p.read_text(encoding="utf-8"))
    raw = d.get("metrics") or []
    items = raw.items() if isinstance(raw, dict) else \
        ((v.get("code") or v.get("name") or "", v) for v in raw)
    rows = []
    for code, v in items:
        if not code:
            continue
        src = (v or {}).get("source") or ""
        if src.startswith(METRIC_SOURCE_EXCLUDE):
            continue
        rows.append({"code": code, "cn": sanitize(str((v or {}).get("desc") or ""))})
    rows.sort(key=lambda r: r["code"])
    return {"count": len(rows), "metrics": rows}


def build(sr: Path) -> tuple[dict, dict]:
    rev = git_rev(sr)
    functions = extract_functions(sr)
    inventory = {
        "schema_version": 2,
        "upstream_rev": rev,
        "domains": extract_domains(sr),
        "preloaded_libs": extract_preloaded(sr),
        "function_count": len(functions),
        "functions": functions,
    }
    metrics = extract_metrics(sr)
    metrics_doc = {"schema_version": 2, "upstream_rev": rev,
                   "count": metrics["count"], "metrics": metrics["metrics"]}
    return inventory, metrics_doc


def render(doc: dict) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=False) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scripts-root", default=None)
    ap.add_argument("--check", action="store_true", help="verify on-disk files match regeneration")
    args = ap.parse_args()

    sr = find_scripts_root(args.scripts_root)
    inv, met = build(sr)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    files = {"inventory.json": render(inv), "metrics.json": render(met)}
    if args.check:
        drift = [n for n, b in files.items()
                 if not (OUT_DIR / n).is_file() or (OUT_DIR / n).read_text(encoding="utf-8") != b]
        if drift:
            print(f"extract drift: {drift}", file=sys.stderr)
            return 1
        print(f"extract ok: {inv['function_count']} functions, {met['count']} metrics "
              f"(upstream_rev={inv['upstream_rev']})")
        return 0
    for name, body in files.items():
        (OUT_DIR / name).write_text(body, encoding="utf-8")
    print(f"wrote {list(files)}: {inv['function_count']} functions, {met['count']} metrics")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
