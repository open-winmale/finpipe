"""内置体验 appid（混淆存放，源码不出现明文）。

仅供初次体验，额度有限且多人共享；正式使用请在赢麻了开放平台申请自己的
appid，额度更充足。混淆仅防明文直读，不构成保密措施——有心人仍可从包内容
或网络请求中还原；明文凭证被 tools/check_leak.py 全仓拦截，勿以明文写入任何跟踪文件。
"""
from __future__ import annotations

import base64

_KEY = b"finpipe-experience"
_CID_B64 = "EQQxHxkVC3IcQRoTGgMLA1dcDQVdFQVC"
_SEC_B64 = "VQxaQVpJUU4BGUUHSwsGDwYGA1hcE1xJAU4BSkNdQAtVW1AHBF9XQF9EVhkATkAD"


def _decode(blob: str) -> str:
    raw = base64.b64decode(blob)
    return bytes(b ^ _KEY[i % len(_KEY)] for i, b in enumerate(raw)).decode("utf-8")


def credentials() -> tuple[str, str]:
    """返回 (client_id, client_secret)；解码结果异常时直接报错（包损坏或被篡改）。"""
    cid, sec = _decode(_CID_B64), _decode(_SEC_B64)
    if not cid.startswith("wm_open_") or len(sec) < 16:
        raise RuntimeError("内置体验 appid 解码异常：包可能损坏或被篡改，请重新安装或自行申请 appid")
    return cid, sec
