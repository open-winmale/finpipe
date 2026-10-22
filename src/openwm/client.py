"""OpenAPI 客户端：OAuth(client_credentials) + /v1/analysis/xs/eval（mode=call）。

  POST {base}/v1/oauth/token        form: grant_type/client_id/client_secret[+scope]
  POST {base}/v1/analysis/xs/eval   JSON: {symbol, xs_lines, args, script_files, market?, mode}
                                    Bearer token；mode=call → 顶层 return 值在 data.result
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import requests

from openwm.catalog import Catalog, load


class OpenWMError(RuntimeError):
    """带修复建议的统一错误。"""


def _xs_literal(v: Any) -> str:
    """Python 值 → XS 字面量（JSON 字面量与 XS 字面量在 string/number/bool/array/map 上一致）。"""
    return json.dumps(v, ensure_ascii=False)


def _to_dataframe(result: Any) -> Any:
    try:
        import pandas as pd  # optional dependency
    except ImportError as e:  # pragma: no cover
        raise OpenWMError("_df=True 需要安装 pandas：pip install pandas") from e
    if isinstance(result, list):
        return pd.DataFrame(result)
    if isinstance(result, dict):
        return pd.DataFrame([result])
    raise OpenWMError(f"结果类型 {type(result).__name__} 无法转 DataFrame")


class Client:
    def __init__(
        self,
        base_url: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        market: str = "cn",
        catalog: Catalog | None = None,
        session: requests.Session | None = None,
        timeout: float = 30.0,
        max_limit: int | None = 500,
    ):
        self.base_url = (base_url or "https://api.winmale.com").rstrip("/")
        self.client_id = client_id or ""
        self.client_secret = client_secret or ""
        self.market = market
        self.catalog = catalog or load()
        self.session = session or requests.Session()
        self.timeout = timeout
        self.max_limit = max_limit
        self._token: str = ""
        self._token_exp: float = 0.0

    # ---- 凭证 ----
    @classmethod
    def from_env(cls, env: dict[str, str] | None = None, **kw: Any) -> "Client":
        e = dict(os.environ if env is None else env)
        cred_file = Path(e.get("OPENWM_CREDENTIALS", Path.home() / ".openwm" / "credentials.env"))
        if cred_file.is_file():
            for line in cred_file.read_text(encoding="utf-8").splitlines():
                line = line.strip().removeprefix("export ").strip()
                if "=" in line and not line.startswith("#"):
                    k, _, v = line.partition("=")
                    e.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        base = e.get("OPENWM_BASE_URL") or e.get("OPEN_PLATFORM_BASE_URL")
        cid = e.get("OPENWM_CLIENT_ID") or e.get("OPEN_PLATFORM_CLIENT_ID")
        sec = e.get("OPENWM_CLIENT_SECRET") or e.get("OPEN_PLATFORM_CLIENT_SECRET")
        if not cid or not sec:
            raise OpenWMError(
                "缺少凭证：设置 OPENWM_CLIENT_ID/OPENWM_CLIENT_SECRET"
                "（或 OPEN_PLATFORM_*），或提供 ~/.openwm/credentials.env")
        return cls(base_url=base, client_id=cid, client_secret=sec, **kw)

    def _get_token(self) -> str:
        if self._token and time.time() < self._token_exp - 60:
            return self._token
        resp = self.session.post(
            f"{self.base_url}/v1/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        doc = resp.json()
        data = doc.get("data") or doc
        token = data.get("access_token")
        if not token:
            raise OpenWMError(f"OAuth 未返回 access_token：{json.dumps(doc, ensure_ascii=False)[:300]}")
        self._token = token
        self._token_exp = time.time() + float(data.get("expires_in", 3600))
        return token

    # ---- eval ----
    def eval(self, xs: str | list[str], *, symbol: str = "600519",
             args: dict | None = None, market: str | None = None,
             mode: str = "call") -> dict:
        """执行 XS，返回完整响应 doc（成功时 data.result 为顶层 return 值）。"""
        lines = xs if isinstance(xs, list) else [ln for ln in xs.splitlines() if ln.strip()]
        body: dict[str, Any] = {
            "symbol": symbol,
            "xs_lines": lines,
            "args": {"print.plain": True, **(args or {})},
            "script_files": {},
            "mode": mode,
        }
        if market := (market or self.market):
            body["market"] = market
        resp = self.session.post(
            f"{self.base_url}/v1/analysis/xs/eval",
            json=body,
            headers={"Authorization": f"Bearer {self._get_token()}"},
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            raise OpenWMError(f"eval HTTP {resp.status_code}: {resp.text[:300]}")
        doc = resp.json()
        if not doc.get("success", True):
            err = doc.get("error") or {}
            raise OpenWMError(
                f"eval 失败: {err.get('code', '')} {err.get('message', json.dumps(doc)[:200])}")
        return doc

    def eval_result(self, xs: str | list[str], **kw: Any) -> Any:
        doc = self.eval(xs, **kw)
        data = doc.get("data") or {}
        return data.get("result")

    # ---- 目录驱动的调用门面 ----
    def _require_lines(self, name: str) -> list[str]:
        """函数命名空间不在 sys/init 预载链时，自动补 xs.require（幂等）。"""
        ns = name.split(".", 1)[0]
        inv = self.catalog.inventory
        if ns in (inv.get("preloaded_libs") or []):
            return []
        entry = (inv.get("domains") or {}).get(ns, {}).get("entry")
        return [f'xs.require("{entry}")'] if entry else []

    def call(self, name: str, /, _raw: bool = False, _df: bool = False, **kwargs: Any) -> Any:
        """按目录合同调用目录内函数：校验参数 → 生成 XS（自动 require + 规范化）→ eval(call)。

        选项以下划线开头，避免与 XS 参数名（如 etf_build 的 raw）冲突：
          _raw=True  跳过 normalize_with，返回 store 原始 Unit
          _df=True   结果为 list[dict] 时转 pandas.DataFrame（需安装 pandas）
        参数合同：优先用域目录精修 params；L1 精简条目回退到 inventory 的签名参数。
        """
        fn = self.catalog.function(name)
        params = fn.get("params") or self.catalog.inventory_params(name)
        known = {p["name"] for p in params}
        unknown = set(kwargs) - known
        if unknown:
            raise OpenWMError(f"{name}: 未知参数 {sorted(unknown)}；合法参数 {sorted(known)}")
        for p in params:
            if p["name"] not in kwargs and "default" not in p and p.get("required"):
                raise OpenWMError(f"{name}: 缺少必填参数 {p['name']}")
        if self.max_limit is not None:
            for p in params:
                if p["name"] in ("limit", "lim") and p["type"] == "int":
                    v = kwargs.get(p["name"], p.get("default"))
                    if isinstance(v, int) and not isinstance(v, bool) and v > self.max_limit:
                        raise OpenWMError(
                            f"{name}: {p['name']}={v} 超过单次请求上限 {self.max_limit}"
                            "（防止单次拉取过大；可在 Client(max_limit=...) 调整，设 None 关闭）")
        args = []
        for p in params:
            if p["name"] in kwargs:
                args.append(_xs_literal(kwargs[p["name"]]))
            elif "default" in p:
                args.append(_xs_literal(p["default"]))
        call_line = f"{name}({', '.join(args)})"
        normalizer = fn.get("normalize_with")
        if normalizer and not _raw:
            lines = [f"__r := {call_line}", f"return {normalizer}(__r)"]
        else:
            lines = [f"return {call_line}"]
        xs = self._require_lines(name) + lines
        symbol = "600519"
        for p in params:
            if p["name"] in kwargs and p["type"] == "string" and p["name"] in ("sym", "symbol", "stk"):
                symbol = str(kwargs[p["name"]])
                break
        result = self.eval_result(xs, symbol=symbol)
        return _to_dataframe(result) if _df else result

    def __getattr__(self, ns: str) -> Any:
        """client.kline.bars(...) —— 友好 API 优先；其余命名空间回退通用门面。"""
        if ns.startswith("_"):
            raise AttributeError(ns)
        from openwm.api import FRIENDLY_NAMESPACES
        cls = FRIENDLY_NAMESPACES.get(ns)
        if cls is not None:
            return cls(self)
        if ns not in self.catalog.namespaces():
            raise AttributeError(
                f"命名空间 {ns!r} 不在目录中；可用友好入口 "
                f"{sorted(FRIENDLY_NAMESPACES)} 或底层命名空间 {sorted(self.catalog.namespaces())}")
        return _Namespace(self, ns)


class _Namespace:
    def __init__(self, client: Client, ns: str):
        self._client = client
        self._ns = ns

    def __getattr__(self, fname: str) -> Any:
        if fname.startswith("_"):
            raise AttributeError(fname)
        return lambda **kw: self._client.call(f"{self._ns}.{fname}", **kw)
