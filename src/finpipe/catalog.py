"""数据目录装载与查询。

目录随包分发（wheel 内置，离线可用；运行时不依赖任何外部仓库，
唯一外部依赖是 OpenAPI 凭证 appid/client_secret）：
  _catalog/domains/*.yaml     域目录（合同见 _catalog/schema/domain.schema.json）
  _catalog/generated/*.json   机器清单（inventory=函数合同, metrics=$CODE 指标）

本模块只读目录，不做网络请求。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml

from finpipe.errors import CatalogError

_PACKAGE_CATALOG = Path(__file__).resolve().parent / "_catalog"
SUPPORTED_SCHEMA_VERSION = 2


def _check_schema(doc: dict, filename: str) -> None:
    version = doc.get("schema_version")
    if version != SUPPORTED_SCHEMA_VERSION:
        raise CatalogError(
            f"{filename}: schema_version={version} 与当前 SDK 支持的 "
            f"{SUPPORTED_SCHEMA_VERSION} 不兼容；请升级 wm-finpipe 或重新安装",
            code="schema")


def catalog_dir() -> Path:
    """定位随包分发的目录：FINPIPE_CATALOG_DIR 覆盖（开发期指向仓内），默认包内 _catalog/。"""
    env = os.environ.get("FINPIPE_CATALOG_DIR")
    if env:
        p = Path(env).expanduser().resolve()
        if (p / "domains").is_dir():
            return p
        raise FileNotFoundError(f"FINPIPE_CATALOG_DIR={env} 下没有 domains/")
    if (_PACKAGE_CATALOG / "domains").is_dir():
        return _PACKAGE_CATALOG
    raise FileNotFoundError(
        "包内 _catalog/ 缺失（安装损坏？）；或设置 FINPIPE_CATALOG_DIR 指向有效目录")


class Catalog:
    def __init__(self, root: Path):
        self.root = root
        self.domains: dict[str, dict] = {}
        self._functions: dict[str, dict] = {}      # qualified name -> merged entry
        self._fn_domain: dict[str, dict] = {}      # qualified name -> domain doc
        self.inventory: dict = json.loads(
            (root / "generated" / "inventory.json").read_text(encoding="utf-8"))
        self.metrics: dict = json.loads(
            (root / "generated" / "metrics.json").read_text(encoding="utf-8"))
        _check_schema(self.inventory, "generated/inventory.json")
        _check_schema(self.metrics, "generated/metrics.json")
        self._inv_functions = {f["name"]: f for f in self.inventory["functions"]}
        self._metric_by_code = {m["code"]: m for m in self.metrics["metrics"]}
        self._load_domains()

    # ---- 装载 ----
    def _load_domains(self) -> None:
        for path in sorted((self.root / "domains").glob("*.yaml")):
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.domains[doc["id"]] = doc
            for fn in doc.get("functions") or []:
                merged = self._merge_with_inventory(fn, doc["id"])
                self._functions[fn["name"]] = merged
                self._fn_domain[fn["name"]] = doc

    def _merge_with_inventory(self, fn: dict, domain_id: str) -> dict:
        """精修条目 + inventory 原始合同（示例/returns_shape/min_args）合并视图。"""
        inv = self._inv_functions.get(fn["name"], {})
        return {
            **fn,
            "domain": domain_id,
            "inventory_example": inv.get("example", ""),
            "returns_shape": inv.get("returns_shape"),
            "min_args": inv.get("min_args"),
            "sources": inv.get("sources", []),
        }

    def domain(self, domain_id: str) -> dict:
        try:
            return self.domains[domain_id]
        except KeyError:
            raise CatalogError(
                f"未知域 {domain_id!r}；已有：{sorted(self.domains)}", code="domain") from None

    def function(self, name: str) -> dict:
        try:
            return self._functions[name]
        except KeyError:
            raise CatalogError(
                f"未知函数 {name!r}；目录共 {len(self._functions)} 条", code="function") from None

    def metric(self, code: str) -> dict | None:
        """按代码取指标（O(1) 索引，2197 条不逐项扫描）。"""
        return self._metric_by_code.get(code)

    def metrics_in_group(self, group_id: str) -> list[dict]:
        """某指标组的全部指标（code/cn），如 metrics_in_group("valuation")。"""
        for d in self.domains.values():
            for g in d.get("metric_groups") or []:
                if g["id"] == group_id:
                    return list(g.get("metrics") or [])
        raise CatalogError(f"未知指标组 {group_id!r}", code="group")

    def metric_groups(self) -> list[dict]:
        """全部指标组摘要（id/cn/domain/count）。"""
        out = []
        for d in self.domains.values():
            for g in d.get("metric_groups") or []:
                out.append({"id": g["id"], "cn": g["cn"], "domain": d["id"],
                            "count": len(g.get("metrics") or [])})
        return out

    def search(self, query: str, *, kind: str = "all", limit: int = 20) -> list[dict]:
        """按关键字（英文名/中文名，大小写不敏感）搜索函数与指标代码。

        kind: "all" | "function" | "metric"；返回 [{kind,name/code,cn,domain?}]。
        """
        q = query.strip().lower()
        if not q:
            return []
        out: list[dict] = []
        if kind in ("all", "function"):
            for name, fn in self._functions.items():
                if q in f"{name} {fn.get('cn', '')}".lower():
                    out.append({"kind": "function", "name": name,
                                "cn": fn.get("cn", ""), "domain": fn["domain"]})
        if kind in ("all", "metric"):
            for m in self.metrics["metrics"]:
                if q in f"{m['code']} {m.get('cn', '')}".lower():
                    out.append({"kind": "metric", "code": m["code"], "cn": m.get("cn", "")})
        return out[:limit]

    def functions_by_domain(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for name, fn in self._functions.items():
            out.setdefault(fn["domain"], []).append(name)
        return {k: sorted(v) for k, v in out.items()}

    def namespaces(self) -> set[str]:
        """目录覆盖的 XS 命名空间（如 kline / notice / rptdom）。"""
        return {name.split(".", 1)[0] for name in self._functions}

    def inventory_params(self, name: str) -> list[dict]:
        """inventory 签名参数（L1 精简条目回退用）。

        xs:catalog 带 min_args 时前 min_args 个必填、其余可选；签名兜底条目全部必填。
        """
        inv = self._inv_functions.get(name) or {}
        params = inv.get("params") or []
        min_args = inv.get("min_args")
        out = []
        for i, p in enumerate(params):
            required = True if min_args is None else i < int(min_args)
            out.append({"name": p["name"], "type": p.get("type", "any"), "required": required})
        return out

    def stats(self) -> dict[str, Any]:
        kinds = {"raw": 0, "computed": 0}
        for fn in self._functions.values():
            k = fn.get("kind") or self.domains[fn["domain"]]["kind"]
            if k in kinds:
                kinds[k] += 1
        metric_total = sum(
            len(g.get("metrics") or []) for d in self.domains.values()
            for g in d.get("metric_groups") or [])
        return {
            "domains": len(self.domains),
            "functions": len(self._functions),
            "raw": kinds["raw"],
            "computed": kinds["computed"],
            "curated_metrics": metric_total,
            "metric_catalog_total": self.metrics.get("count", 0),
            "upstream_rev": self.inventory.get("upstream_rev"),
        }

    # ---- 装载辅助：_load_domains 时设置当前域 id ----
    def _set_loading(self, domain_id: str) -> None:
        self._loading_domain = domain_id


def load(path: str | os.PathLike | None = None) -> Catalog:
    """装载目录。默认自动定位；可传 catalog 目录或仓根。"""
    p = Path(path).expanduser().resolve() if path else catalog_dir()
    if (p / "domains").is_dir():
        return Catalog(p)
    if (p / "catalog" / "domains").is_dir():
        return Catalog(p / "catalog")
    raise FileNotFoundError(f"{p} 下未找到 domains/")
