"""OpenAPI 客户端：OAuth(client_credentials) + /v1/analysis/xs/eval（mode=call）。

  POST {base}/v1/oauth/token        form: grant_type/client_id/client_secret[+scope]
  POST {base}/v1/analysis/xs/eval   JSON: {symbol, xs_lines, args, script_files, market?, mode}
                                    Bearer token；mode=call → 顶层 return 值在 data.result
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

from finpipe._experience import credentials as _experience_credentials
from finpipe.catalog import Catalog, load
from finpipe.errors import (
    ApiError, AuthError, CatalogError, FinPipeError, LimitError, ServerError,
    TransportError, UsageError,
)

DEFAULT_BASE_URL = "https://api.winmale.com"


_SYM_PREFIX = re.compile(r"^(?:cn|sh|sz|bj)\.", re.IGNORECASE)
_SYM_SUFFIX = re.compile(r"\.(?:SH|SZ|BJ)$", re.IGNORECASE)


def normalize_symbol(symbol: str) -> str:
    """标的代码归一：去 cn./sh./sz./bj. 前缀与 .SH/.SZ/.BJ 后缀，字母转大写。

    例：``sh.600519.SH`` → ``600519``；``cn.000001`` → ``000001``；``aapl`` → ``AAPL``。
    """
    s = str(symbol).strip()
    s = _SYM_PREFIX.sub("", s)
    s = _SYM_SUFFIX.sub("", s)
    return s.upper()


@dataclass
class BatchResult:
    """批量调用结果：成功项与逐标的错误（on_error="skip" 时）。"""

    results: dict[str, Any] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)


def _xs_literal(v: Any) -> str:
    """Python 值 → XS 字面量。

    XS 的空值是 ``nil``（不接受 JSON 的 ``null``），因此 None 必须单独映射；
    其余 string/number/bool/array/map 与 JSON 字面量一致。
    """
    if v is None:
        return "nil"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return json.dumps(v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_xs_literal(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ", ".join(f"{_xs_literal(str(k))}: {_xs_literal(x)}"
                               for k, x in v.items()) + "}"
    return json.dumps(v, ensure_ascii=False)


def _to_dataframe(result: Any) -> Any:
    try:
        import pandas as pd  # optional dependency
    except ImportError as e:  # pragma: no cover
        raise UsageError("_df=True 需要安装 pandas：pip install pandas", code="pandas") from e
    if isinstance(result, list):
        return pd.DataFrame(result)
    if isinstance(result, dict):
        return pd.DataFrame([result])
    raise UsageError(f"结果类型 {type(result).__name__} 无法转 DataFrame", code="dataframe")


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
        retries: int = 2,
        backoff: float = 0.5,
    ):
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.client_id = client_id or ""
        self.client_secret = client_secret or ""
        if bool(self.client_id) != bool(self.client_secret):
            raise AuthError(
                "client_id 与 client_secret 需成对提供；两者都不传则使用内置体验 appid"
                "（额度有限，正式使用请在赢麻了开放平台申请自己的 appid）", code="config")
        if not self.client_id:
            cid, sec = _experience_credentials()
            self.client_id = cid
            self.client_secret = sec
        self.market = market
        self.catalog = catalog or load()
        self.session = session or requests.Session()
        self.timeout = timeout
        self.max_limit = max_limit
        self.retries = max(0, int(retries))
        self.backoff = backoff
        self._sleep = time.sleep  # 测试注入点：不真实等待
        self._token: str = ""
        self._token_exp: float = 0.0

    # ---- 凭证 ----
    @classmethod
    def from_env(cls, env: dict[str, str] | None = None, **kw: Any) -> "Client":
        e = dict(os.environ if env is None else env)
        cred_file = Path(e.get("FINPIPE_CREDENTIALS", Path.home() / ".finpipe" / "credentials.env"))
        if cred_file.is_file():
            for line in cred_file.read_text(encoding="utf-8").splitlines():
                line = line.strip().removeprefix("export ").strip()
                if "=" in line and not line.startswith("#"):
                    k, _, v = line.partition("=")
                    e.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        base = e.get("FINPIPE_BASE_URL") or e.get("OPEN_PLATFORM_BASE_URL")
        cid = e.get("FINPIPE_CLIENT_ID") or e.get("OPEN_PLATFORM_CLIENT_ID")
        sec = e.get("FINPIPE_CLIENT_SECRET") or e.get("OPEN_PLATFORM_CLIENT_SECRET")
        # 环境变量只在显式参数缺省时注入；凭证成对性由 __init__ 校验（部分配置报错），
        # 全部缺省时 __init__ 兜底内置体验 appid
        if base:
            kw.setdefault("base_url", base)
        if cid:
            kw.setdefault("client_id", cid)
        if sec:
            kw.setdefault("client_secret", sec)
        return cls(**kw)

    # ---- 传输 ----
    RETRY_STATUS = frozenset({429, 500, 502, 503, 504})

    def _delay(self, attempt: int, resp: requests.Response | None) -> float:
        """退避秒数：优先 Retry-After，其次指数退避（封顶 10s）。"""
        if resp is not None:
            ra = resp.headers.get("Retry-After") if hasattr(resp, "headers") else None
            if ra:
                try:
                    return min(10.0, max(0.0, float(ra)))
                except (TypeError, ValueError):
                    pass
        return min(10.0, self.backoff * (2 ** attempt))

    def _request(self, url: str, **kw: Any) -> requests.Response:
        """POST + 429/5xx 指数退避重试；网络异常同样重试并在耗尽后转 FinPipeError。"""
        attempts = self.retries + 1
        last: requests.Response | None = None
        for i in range(attempts):
            try:
                resp = self.session.post(url, **kw)
            except requests.RequestException as e:
                if i == attempts - 1:
                    raise TransportError(
                        f"网络请求失败（已重试 {self.retries} 次）：{e}", code="network") from e
                self._sleep(self._delay(i, None))
                continue
            last = resp
            if resp.status_code in self.RETRY_STATUS and i < attempts - 1:
                self._sleep(self._delay(i, resp))
                continue
            return resp
        assert last is not None  # 循环必然 return 或 raise
        return last

    def _get_token(self) -> str:
        if self._token and time.time() < self._token_exp - 60:
            return self._token
        resp = self._request(
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
            raise AuthError(
                f"OAuth 未返回 access_token：{json.dumps(doc, ensure_ascii=False)[:300]}",
                code="oauth")
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
            "symbol": normalize_symbol(symbol),
            "xs_lines": lines,
            "args": {"print.plain": True, **(args or {})},
            "script_files": {},
            "mode": mode,
        }
        if market := (market or self.market):
            body["market"] = market
        url = f"{self.base_url}/v1/analysis/xs/eval"

        def call_once() -> requests.Response:
            return self._request(url, json=body, timeout=self.timeout,
                                 headers={"Authorization": f"Bearer {self._get_token()}"})

        resp = call_once()
        if resp.status_code == 401:
            # 令牌可能已失效：清缓存强制刷新后重试一次（仅一次，避免环路）
            self._token = ""
            self._token_exp = 0.0
            resp = call_once()
        if resp.status_code != 200:
            if resp.status_code in (401, 403):
                raise AuthError(f"eval HTTP {resp.status_code}: {resp.text[:300]}",
                                code="denied", status=resp.status_code)
            if resp.status_code >= 500:
                raise ServerError(f"eval HTTP {resp.status_code}: {resp.text[:300]}",
                                  code="server", status=resp.status_code)
            raise ApiError(f"eval HTTP {resp.status_code}: {resp.text[:300]}",
                           code="http", status=resp.status_code)
        doc = resp.json()
        if not doc.get("success", True):
            err = doc.get("error") or {}
            raise ApiError(
                f"eval 失败: {err.get('code', '')} {err.get('message', json.dumps(doc)[:200])}",
                code=str(err.get("code", "eval")))
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

    SYMBOL_PARAMS = ("sym", "symbol", "stk")

    def _build_call_line(self, name: str, params: list[dict], kwargs: dict[str, Any],
                         *, sym_override: str | None = None,
                         sym_param: str | None = None) -> str:
        """校验参数并生成单次调用字面量（含标的一体化归一）。"""
        known = {p["name"] for p in params}
        unknown = set(kwargs) - known
        if unknown:
            raise UsageError(f"{name}: 未知参数 {sorted(unknown)}；合法参数 {sorted(known)}",
                             code="params")
        for p in params:
            provided = p["name"] in kwargs or (sym_override is not None and p["name"] == sym_param)
            if not provided and "default" not in p and p.get("required"):
                raise UsageError(f"{name}: 缺少必填参数 {p['name']}", code="params")
        if self.max_limit is not None:
            for p in params:
                if p["name"] in ("limit", "lim") and p["type"] == "int":
                    v = kwargs.get(p["name"], p.get("default"))
                    if isinstance(v, int) and not isinstance(v, bool) and v > self.max_limit:
                        raise LimitError(
                            f"{name}: {p['name']}={v} 超过单次请求上限 {self.max_limit}"
                            "（防止单次拉取过大；可在 Client(max_limit=...) 调整，设 None 关闭）",
                            code="limit")
        args = []
        for p in params:
            if sym_override is not None and p["name"] == sym_param:
                args.append(_xs_literal(normalize_symbol(sym_override)))
            elif p["name"] in kwargs:
                v = kwargs[p["name"]]
                if p.get("type") == "string" and p["name"] in self.SYMBOL_PARAMS:
                    v = normalize_symbol(v)
                args.append(_xs_literal(v))
            elif "default" in p:
                args.append(_xs_literal(p["default"]))
        return f"{name}({', '.join(args)})"

    def call(self, name: str, /, _raw: bool = False, _df: bool = False, **kwargs: Any) -> Any:
        """按目录合同调用目录内函数：校验参数 → 生成 XS（自动 require + 规范化）→ eval(call)。

        选项以下划线开头，避免与 XS 参数名（如 etf_build 的 raw）冲突：
          _raw=True  跳过 normalize_with，返回 store 原始 Unit
          _df=True   结果为 list[dict] 时转 pandas.DataFrame（需安装 pandas）
        参数合同：优先用域目录精修 params；L1 精简条目回退到 inventory 的签名参数。
        标的参数（sym/symbol/stk）自动归一：去 cn./sh./sz./bj. 前缀与 .SH/.SZ/.BJ 后缀。
        """
        fn = self.catalog.function(name)
        params = fn.get("params") or self.catalog.inventory_params(name)
        call_line = self._build_call_line(name, params, kwargs)
        normalizer = fn.get("normalize_with")
        if normalizer and not _raw:
            lines = [f"__r := {call_line}", f"return {normalizer}(__r)"]
        else:
            lines = [f"return {call_line}"]
        xs = self._require_lines(name) + lines
        symbol = "600519"
        for p in params:
            if p["name"] in kwargs and p["type"] == "string" and p["name"] in self.SYMBOL_PARAMS:
                symbol = normalize_symbol(str(kwargs[p["name"]]))
                break
        result = self.eval_result(xs, symbol=symbol)
        return _to_dataframe(result) if _df else result

    def call_batch(self, name: str, symbols: list[str], /, on_error: str = "raise",
                   _raw: bool = False, _df: bool = False, **kwargs: Any) -> BatchResult:
        """同一目录函数在多个标的上的批量调用。

        on_error="raise"（默认）：把所有标的组装成**一次** eval（map 字面量），单次 HTTP；
        任一标的失败则整体抛出（服务端无 try/catch，无法在单次请求内隔离）。
        on_error="skip"：逐标的调用并捕获错误，成功项进 results、失败项进 errors（N 次 HTTP）。
        _df=True 时对每个成功结果转 DataFrame。
        """
        if on_error not in ("raise", "skip"):
            raise UsageError('on_error 只支持 "raise" 或 "skip"', code="params")
        fn = self.catalog.function(name)
        params = fn.get("params") or self.catalog.inventory_params(name)
        sym_param = next((p["name"] for p in params
                          if p.get("type") == "string" and p["name"] in self.SYMBOL_PARAMS), None)
        if sym_param is None:
            raise UsageError(f"{name}: 没有标的参数（sym/symbol/stk），不支持批量调用",
                             code="params")
        if sym_param in kwargs:
            raise UsageError(f"{name}: 批量调用请用 symbols 指定标的，不要在 kwargs 传 {sym_param}",
                             code="params")
        syms = list(dict.fromkeys(normalize_symbol(s) for s in symbols))
        if not syms:
            return BatchResult()
        if self.max_limit is not None and len(syms) > self.max_limit:
            raise LimitError(f"{name}: 批量标的数 {len(syms)} 超过上限 {self.max_limit}",
                             code="limit")
        if on_error == "skip":
            results: dict[str, Any] = {}
            errors: dict[str, str] = {}
            for s in syms:
                try:
                    results[s] = self.call(name, _raw=_raw, _df=_df, **kwargs, **{sym_param: s})
                except FinPipeError as e:
                    errors[s] = str(e)
            return BatchResult(results=results, errors=errors)

        normalizer = fn.get("normalize_with")
        pairs = []
        for s in syms:
            line = self._build_call_line(name, params, kwargs, sym_override=s, sym_param=sym_param)
            pairs.append(f'{_xs_literal(s)}: {normalizer}({line})' if normalizer and not _raw
                         else f"{_xs_literal(s)}: {line}")
        xs = self._require_lines(name) + [f"return {{{', '.join(pairs)}}}"]
        result = self.eval_result(xs, symbol=syms[0])
        if not isinstance(result, dict):
            raise ApiError(f"{name}: 批量返回不是 MAP（{type(result).__name__}）", code="batch")
        if _df:
            result = {k: _to_dataframe(v) for k, v in result.items()}
        return BatchResult(results=result)

    # ---- 生命周期 ----
    def close(self) -> None:
        """关闭底层 HTTP 会话（注入的 session 也由调用方决定是否关闭）。"""
        close = getattr(self.session, "close", None)
        if callable(close):
            close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def __getattr__(self, ns: str) -> Any:
        """client.bonus.query_list(...) —— 友好 API 优先，其次类型化门面，最后通用门面。"""
        if ns.startswith("_"):
            raise AttributeError(ns)
        from finpipe.api import FRIENDLY_NAMESPACES, GENERATED_NAMESPACES
        cls = FRIENDLY_NAMESPACES.get(ns)
        if cls is not None:
            return cls(self)
        gcls = GENERATED_NAMESPACES.get(ns)
        if gcls is not None:
            return gcls(self)
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
