#!/usr/bin/env python3
"""Validate domain catalog (src/wmshare/_catalog/domains/*.yaml) against schema + generated inventory.

Gates:
  1. domain YAML is valid against _catalog/schema/domain.schema.json
  2. every functions[].name exists in generated/inventory.json (anti-fabrication)
  3. returns.shape_ref=inventory requires the inventory entry to carry returns_shape
  4. metric_groups[].metrics[].code exists in metrics.json
  5. domain id matches filename stem

Usage: python3 tools/validate_catalog.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wmshare.catalog import catalog_dir  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
DOMAINS = catalog_dir() / "domains"
SCHEMA = json.loads((catalog_dir() / "schema" / "domain.schema.json").read_text(encoding="utf-8"))
INVENTORY = json.loads((catalog_dir() / "generated" / "inventory.json").read_text(encoding="utf-8"))
METRICS = json.loads((catalog_dir() / "generated" / "metrics.json").read_text(encoding="utf-8"))

INV_FUNCS = {f["name"]: f for f in INVENTORY["functions"]}
METRIC_CODES = {m["code"] for m in METRICS["metrics"]}


def main() -> int:
    errors: list[str] = []
    files = sorted(DOMAINS.glob("*.yaml"))
    if not files:
        print("no domain files found", file=sys.stderr)
        return 1

    total_fns = raw_fns = computed_fns = 0
    for path in files:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        where = str(path.relative_to(REPO))
        try:
            jsonschema.validate(doc, SCHEMA)
        except jsonschema.ValidationError as e:
            errors.append(f"{where}: schema: {'/'.join(str(p) for p in e.absolute_path)}: {e.message}")
            continue
        if doc["id"] != path.stem:
            errors.append(f"{where}: id {doc['id']!r} != filename stem {path.stem!r}")
        for fn in doc.get("functions") or []:
            total_fns += 1
            kind = fn.get("kind") or doc["kind"]
            if kind == "raw":
                raw_fns += 1
            elif kind == "computed":
                computed_fns += 1
            name = fn["name"]
            inv = INV_FUNCS.get(name)
            if inv is None:
                errors.append(f"{where}: function {name} not in inventory (fabricated or upstream-removed)")
                continue
            ret = fn.get("returns") or {}
            if ret.get("shape_ref") == "inventory" and not inv.get("returns_shape"):
                errors.append(f"{where}: {name} uses shape_ref=inventory but inventory has no returns_shape")
            # curated params must agree with inventory param names (order-insensitive)
            cur = [p["name"] for p in fn.get("params") or []]
            invp = [p["name"] for p in inv.get("params") or []]
            if cur and sorted(cur) != sorted(invp):
                errors.append(f"{where}: {name} params {cur} != inventory {invp}")
        for grp in doc.get("metric_groups") or []:
            for m in grp.get("metrics") or []:
                if m["code"] not in METRIC_CODES:
                    errors.append(f"{where}: metric {m['code']} not in metrics.json")
        print(f"ok   {where}: id={doc['id']} kind={doc['kind']} "
              f"functions={len(doc.get('functions') or [])} "
              f"metric_groups={len(doc.get('metric_groups') or [])}")

    if errors:
        print("\nFAIL:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"\ncatalog valid: {len(files)} domains, {total_fns} functions "
          f"(raw={raw_fns}, computed={computed_fns})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
