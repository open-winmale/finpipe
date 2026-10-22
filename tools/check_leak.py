#!/usr/bin/env python3
"""Leak gate before publishing to GitHub (ROADMAP M1.1).

Scans all git-tracked files for:
  - internal hostnames / NAS paths / developer machine paths
  - secret-looking assignments (CLIENT_SECRET=..., token literals)
Exits 1 on any hit. Wired into CI (gates job) and pre-push habit.

Usage: python3 tools/check_leak.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# 内部域名 / 基础设施路径（对外不可见的信息）
FORBIDDEN_SUBSTRINGS = [
    "code.yepless.cn",
    "datanas",
    "less.server",
    "skillhub-releases",
    "winmale/.skillhub",
]

# 第三方产品/数据商引用：项目规范禁止出现（含竞品对标与数据来源点名）
THIRDPARTY_RE = re.compile(
    r"数据服务|开源数据库|quote_source|数据源|数据源|quote_source|数据服务商|quote_source|数据商|数据服务商|vendor_events|"
    r"披露平台|社区|社区|行情软件|问财|vendor_source|行情软件|行情软件|行情软件|海外数据商|数据商|"
    r"提取工具|报表工具|开源数据库|量化平台|量化平台|量化平台|量化平台|量化平台",
    re.IGNORECASE,
)

# 开发者机器路径
FORBIDDEN_PATTERNS = [
    re.compile(r"/Users/[A-Za-z0-9_]+/"),
    re.compile(r"/home/[A-Za-z0-9_]+/winmale"),
]

# 携带第三方禁用词表本身的维护工具（策略定义文件），豁免第三方扫描；其余扫描照常
THIRDPARTY_SKIP = {"tools/check_leak.py", "tools/extract_from_scripts.py"}

# 凭证赋值（带字面量）
SECRET_RE = re.compile(
    r"(CLIENT_SECRET|client_secret|ACCESS_TOKEN|access_token|api[_-]?key)\s*[=:]\s*['\"]?[A-Za-z0-9_\-]{16,}",
    re.IGNORECASE,
)

# 允许出现的公开端点（SDK 的合法目标），不在此列的内网域名会被上面的规则拦下
ALLOWED_MARKERS = ("api.winmale.com", "test-api.winmale.com")


def tracked_files() -> list[Path]:
    out = subprocess.run(["git", "-C", str(REPO), "ls-files"],
                         capture_output=True, text=True, check=True)
    return [REPO / p for p in out.stdout.splitlines() if p.strip()]


def scan() -> list[str]:
    findings: list[str] = []
    self_rel = Path(__file__).resolve().relative_to(REPO).as_posix()
    for path in tracked_files():
        if not path.is_file() or path.relative_to(REPO).as_posix() == self_rel:
            continue  # 规则定义文件本身含被扫描字面量，排除
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = path.relative_to(REPO).as_posix()
        for needle in FORBIDDEN_SUBSTRINGS:
            if needle in text:
                findings.append(f"{rel}: 含内部标识 {needle!r}")
        for pat in FORBIDDEN_PATTERNS:
            m = pat.search(text)
            if m:
                findings.append(f"{rel}: 含机器路径 {m.group(0)!r}")
        m = THIRDPARTY_RE.search(text) if rel not in THIRDPARTY_SKIP else None
        if m:
            findings.append(f"{rel}: 含第三方引用 {m.group(0)!r}（项目规范禁止）")
        m = SECRET_RE.search(text)
        if m:
            findings.append(f"{rel}: 疑似凭证字面量 {m.group(0)[:40]!r}")
    return findings


def main() -> int:
    findings = scan()
    if findings:
        print("FAIL: 泄漏扫描发现以下问题：", file=sys.stderr)
        for f in findings:
            print(f"  - {f}", file=sys.stderr)
        return 1
    n = len(tracked_files())
    print(f"leak gate ok ({n} tracked files clean)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
