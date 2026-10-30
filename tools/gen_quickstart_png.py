#!/usr/bin/env python3
"""生成 README 首屏静态图：docs/img/quickstart.png（生成物不手改，重跑本脚本再生成）。

画面是「高股息 + 低估值」选股脚本的真实实跑结果（2026-10-30，PROD 数据，
全市场 5,691 家 → 12 次批量请求 → 60 只候选 → 命中 20，按 PE 十年分位取前 8）。
纯 Pillow 渲染终端画面，无外部录制工具依赖：ASCII 用等宽字体，中文回落系统黑体。

数值来自一次真实运行；行情变化后重跑脚本再替换下面 ROWS 与 SUMMARY，保持图与
README 代码块同源。重新生成：

    python tools/gen_quickstart_png.py
"""
from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs" / "img" / "quickstart.png"

W, H = 1640, 960
BG = (13, 17, 23)          # GitHub Dark
BAR = (32, 38, 46)
FG = (201, 209, 217)
DIM = (139, 148, 158)
PROMPT = (63, 185, 80)     # 绿：提示符
VALUE = (227, 181, 90)     # 暖黄：结果值
COMMENT = (110, 122, 136)  # 灰：说明
RULE = (48, 54, 61)

TITLE = "wmshare · 选股实战"
CMD = "python3 screen.py"
CONDITION = "筛选：全市场股息率 3%–10% 且非 ST ｜ PE 0–40 ｜ PE 十年分位 ≤ 50%"
HEADER = ("代码", "名称", "股息率", "PE", "十年分位")
ROWS = [
    ("920022", "世昌股份", "7.57%", "14.2", "0.0%"),
    ("300910", "瑞丰新材", "7.18%", "12.0", "0.3%"),
    ("002616", "长青集团", "8.57%", "12.2", "0.4%"),
    ("000703", "恒逸石化", "7.49%", "6.5", "2.2%"),
    ("002345", "潮宏基", "7.01%", "9.7", "3.0%"),
    ("600983", "惠而浦", "8.78%", "12.2", "4.9%"),
    ("002170", "芭田股份", "8.12%", "10.9", "5.6%"),
    ("600351", "亚宝药业", "7.68%", "13.7", "11.9%"),
]
SUMMARY = "全市场 5,691 家 → 12 次请求 → 60 只候选 → 命中 20，按分位取前 8"
FOOT = "实测 2026-10-30 · 真实数据（Client.from_env()）· 代码见 README「选股实战」· 数值随行情变动"

# 列左边界（代码/名称为左对齐，其余右对齐到 COL_RIGHT）
COL_X = (60, 300, 800, 1060, 1290)
COL_RIGHT = (None, None, 990, 1210, 1480)

MONO_CANDIDATES = [
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/Monaco.dfont",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
]
CJK_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
]
_SEG = re.compile(r"[\x00-\x7f]+|[^ \x00-\x7f]+")  # ASCII 段 / 非 ASCII 段


def _font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise SystemExit(f"未找到候选字体：{candidates}，请补充系统字体路径")


def _draw_mixed(d: ImageDraw.ImageDraw, pos: tuple[int, int], text: str,
                mono: ImageFont.FreeTypeFont, cjk: ImageFont.FreeTypeFont,
                fill) -> None:
    """按段选择字体绘制（ASCII→等宽，CJK→黑体）。"""
    x, y = pos
    for seg in _SEG.findall(text):
        f = mono if seg[0] < "\x80" else cjk
        d.text((x, y), seg, font=f, fill=fill)
        x += d.textlength(seg, font=f)


def _mixed_len(d: ImageDraw.ImageDraw, text: str, mono, cjk) -> float:
    x = 0.0
    for seg in _SEG.findall(text):
        f = mono if seg[0] < "\x80" else cjk
        x += d.textlength(seg, font=f)
    return x


def _render() -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    mono, cjk = _font(MONO_CANDIDATES, 32), _font(CJK_CANDIDATES, 30)
    title_f, foot_f = _font(CJK_CANDIDATES, 24), _font(CJK_CANDIDATES, 23)
    small = _font(MONO_CANDIDATES, 24)

    # 终端标题栏
    d.rectangle([0, 0, W, 58], fill=BAR)
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([24 + i * 32, 21, 42 + i * 32, 39], fill=c)
    tw = d.textlength(TITLE, font=title_f)
    d.text(((W - tw) / 2, 16), TITLE, font=title_f, fill=DIM)

    y = 104
    # 命令行
    d.text((60, y), "$ ", font=mono, fill=PROMPT)
    d.text((60 + d.textlength("$ ", font=mono), y), CMD, font=mono, fill=FG)
    y += 74
    # 筛选条件（脚本第一行输出，作说明色）
    _draw_mixed(d, (60, y), CONDITION, mono, cjk, COMMENT)
    y += 66
    # 表头 + 分隔线
    for i, cell in enumerate(HEADER):
        color = DIM
        if COL_RIGHT[i] is None:
            _draw_mixed(d, (COL_X[i], y), cell, mono, cjk, color)
        else:
            _draw_mixed(d, (int(COL_RIGHT[i] - _mixed_len(d, cell, mono, cjk)), y),
                        cell, mono, cjk, color)
    y += 52
    d.line([(60, y), (W - 60, y)], fill=RULE, width=2)
    y += 18
    # 数据行
    for row in ROWS:
        for i, cell in enumerate(row):
            color = VALUE if i >= 2 else FG
            if COL_RIGHT[i] is None:
                _draw_mixed(d, (COL_X[i], y), cell, mono, cjk, color)
            else:
                _draw_mixed(d, (int(COL_RIGHT[i] - _mixed_len(d, cell, mono, cjk)), y),
                            cell, mono, cjk, color)
        y += 56
    # 汇总
    y += 18
    d.line([(60, y), (W - 60, y)], fill=RULE, width=2)
    y += 24
    _draw_mixed(d, (60, y), SUMMARY, mono, cjk, FG)
    # 页脚：来源与复跑口径
    d.text((60, H - 62), FOOT, font=foot_f, fill=DIM)
    return img


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    _render().save(OUT, optimize=True)
    print(f"已生成 {OUT}（{OUT.stat().st_size / 1024:.0f} KB）")


if __name__ == "__main__":
    main()
