#!/usr/bin/env python3
"""Leak gate before publishing to GitHub (ROADMAP M1.1).

Scans all git-tracked files for:
  - internal hostnames / NAS paths / developer machine paths
  - secret-looking assignments (CLIENT_SECRET=..., token literals)
  - tracked files outside the public whitelist (CONTRIBUTING.md 入库白名单),
    so internal planning/process docs can never slip back into the repo
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
    # 内置体验 appid 的明文：仅允许以混淆 blob 存在于 src/finpipe/_experience.py，
    # 任何跟踪文件出现明文（含 README/测试/示例）一律视为泄漏
    "wm_open_y9jvhjnm49kl3el2",
    "3e41394cda5b9bcaece12c59dcd2382b053bb6906434e60f",
]

# 第三方产品/数据商引用：项目规范禁止出现（含竞品对标与数据来源点名）
THIRDPARTY_RE = re.compile(
    r"tushare|akshare|eastmoney|东财|新浪|sina|腾讯|tencent|聚源|理杏仁|lixingren|"
    r"巨潮|雪球|xueqiu|同花顺|问财|iwencai|10jqka|通达信|tdx|bloomberg|万得|"
    r"fin-extract|rpttab|baostock|掘金|聚宽|joinquant|米筐|ricequant",
    re.IGNORECASE,
)

# 经维护者批准的例外：README「与 Tushare 对比」章节允许点名 tushare；CHANGELOG 记录、
# CONTRIBUTING 规范说明与守护测试同属这一决定的一部分。仅此一名、仅此四文件；
# 其余第三方名在全部文件仍然禁止。
THIRDPARTY_ALLOWED_BY_FILE = {
    rel: re.compile(r"tushare", re.IGNORECASE)
    for rel in ("README.md", "CHANGELOG.md", "CONTRIBUTING.md", "tests/test_docs.py")
}

# 开发者机器路径
FORBIDDEN_PATTERNS = [
    re.compile(r"/Users/[A-Za-z0-9_]+/"),
    re.compile(r"/home/[A-Za-z0-9_]+/winmale"),
]

# 携带第三方禁用词表本身的维护工具（策略定义文件），豁免第三方扫描；其余扫描照常
THIRDPARTY_SKIP = {"tools/check_leak.py", "tools/extract_from_scripts.py",
                   "tests/test_symbols.py"}

# 公司名录是标的数据：上市公司名本身（如港股 00700 腾讯控股）会与数据商/竞品禁词
# 撞名——这是「标的名」不是「第三方产品引用」，整个目录豁免第三方扫描
# （内部标识/凭证等其余扫描照常进行）。
THIRDPARTY_SKIP_PREFIXES = ("src/finpipe/_catalog/symbols/",)

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


# 允许进入公开仓库的路径白名单（CONTRIBUTING.md「入库白名单」的机器可执行版）。
# 白名单之外任何被 git 跟踪的文件一律视为泄漏——内部规划/流程/路线图文档
# 曾经因只扫关键词而漏网，这里从路径层面兜底。
ALLOWED_PATH_PREFIXES = (
    "src/",
    "tests/",
    "examples/",
    "docs/",
    "tools/",
    ".github/",
)
ALLOWED_PATHS = {
    "README.md",
    "README.en.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    "LICENSE",
    "NOTICE",
    "pyproject.toml",
    ".gitignore",
}


def disallowed_tracked_files() -> list[str]:
    out = subprocess.run(["git", "-C", str(REPO), "ls-files"],
                         capture_output=True, text=True, check=True)
    bad: list[str] = []
    for raw in out.stdout.splitlines():
        rel = raw.strip()
        if not rel:
            continue
        if rel.startswith(ALLOWED_PATH_PREFIXES) or rel in ALLOWED_PATHS:
            continue
        bad.append(rel)
    return bad


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
        allowed = THIRDPARTY_ALLOWED_BY_FILE.get(rel)
        if not (rel in THIRDPARTY_SKIP
                or rel.startswith(THIRDPARTY_SKIP_PREFIXES)):
            for m in THIRDPARTY_RE.finditer(text):
                if not (allowed and allowed.fullmatch(m.group(0))):
                    findings.append(f"{rel}: 含第三方引用 {m.group(0)!r}（项目规范禁止）")
                    break
        m = SECRET_RE.search(text)
        if m:
            findings.append(f"{rel}: 疑似凭证字面量 {m.group(0)[:40]!r}")
    return findings


def main() -> int:
    findings = scan()
    for rel in disallowed_tracked_files():
        findings.append(f"{rel}: 白名单外文件被 git 跟踪（见 CONTRIBUTING.md 入库白名单，"
                        f"内部规划/流程文档一律不入库）")
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
