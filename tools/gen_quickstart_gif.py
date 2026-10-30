#!/usr/bin/env python3
"""生成 README 首屏演示 GIF：docs/img/quickstart.gif（生成物不手改，重跑本脚本再生成）。

录的是 wmshare.demo_client() 的真实调用与真实输出（罐头快照，与 README 首跑块同值），
因此数值永不漂移、不违反可验证事实链。纯 Pillow 渲染终端画面，无 brew/外部录制工具依赖：
ASCII 用等宽字体，中文回落系统黑体（Menlo 无 CJK 字形）。

    python tools/gen_quickstart_gif.py
"""
from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs" / "img" / "quickstart.gif"

W, H = 1040, 700
BG = (13, 17, 23)          # GitHub Dark
BAR = (32, 38, 46)
FG = (201, 209, 217)
PROMPT = (63, 185, 80)     # 绿：提示符
VALUE = (227, 181, 90)     # 暖黄：输出值
COMMENT = (110, 122, 136)  # 灰：注释
FOOT = (139, 148, 158)
CURSOR = (63, 185, 80)
LINE_H = 46

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

# 与 README「不配凭证，先看输出」演示块同值（demo_client 罐头快照）
SCRIPT: list[tuple[str, str]] = [
    ("cmd", "python3 -q"),
    ("repl", "import wmshare"),
    ("repl", "cli = wmshare.demo_client()   # 离线演示：零凭证、不联网"),
    ("repl", 'cli.dividend.yield_ttm("600519")'),
    ("out", "0.0396"),
    ("repl", 'cli.indicator.get("600519", "$PCT_PE_TTM_10Y_LAST")'),
    ("out", "0.42"),
    ("repl", "res = cli.batch_all(\"kline.snapshot\","),
    ("cont", "        [r['symbol'] for r in cli.stocks.list()])"),
    ("repl", "len(res.results), res.requests"),
    ("out", "(3, 1)"),
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
    """按段选择字体绘制（ASCII→等宽，CJK→黑体），返回横向推进由调用方用 textlength 实现。"""
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


def _frame(lines: list[tuple[str, str]], foot: bool) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    mono, cjk = _font(MONO_CANDIDATES, 30), _font(CJK_CANDIDATES, 28)
    title_f, foot_f = _font(CJK_CANDIDATES, 22), _font(CJK_CANDIDATES, 24)
    # 终端标题栏
    d.rectangle([0, 0, W, 52], fill=BAR)
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([22 + i * 30, 19, 40 + i * 30, 37], fill=c)
    tw = d.textlength("wmshare 零凭证首跑", font=title_f)
    d.text(((W - tw) / 2, 14), "wmshare 零凭证首跑", font=title_f, fill=FOOT)
    # 正文行
    y = 86
    for kind, text in lines:
        x = 34
        color = FG
        prompt = ""
        if kind == "cmd":
            prompt = "$ "
        elif kind == "repl":
            prompt = ">>> "
        elif kind == "cont":
            prompt = "... "
        elif kind == "out":
            color = VALUE
        if prompt:
            d.text((x, y), prompt, font=mono, fill=PROMPT)
            x += d.textlength(prompt, font=mono)
        code, _, note = text.partition("#")
        if kind in ("cmd", "repl", "cont"):
            _draw_mixed(d, (x, y), code, mono, cjk, color)
            if note:
                nx = x + _mixed_len(d, code, mono, cjk)
                _draw_mixed(d, (int(nx), y), "#" + note, mono, cjk, COMMENT)
        else:
            d.text((x, y), text, font=mono, fill=color)
        y += LINE_H
    if foot:
        d.text((34, H - 58), "演示数据 = 随包固定快照（非真实行情）· 接真实数据："
               "wmshare.Client.from_env()", font=foot_f, fill=FOOT)
    return img


def main() -> None:
    frames: list[Image.Image] = []
    lines: list[tuple[str, str]] = []
    for kind, text in SCRIPT:
        for n in range(0, len(text) + 1, 4):       # 打字动画：每帧 4 字符
            frames.append(_frame(lines + [(kind, text[:n])], foot=False))
        lines.append((kind, text))
        frames.append(_frame(lines, foot=False))
    frames.append(_frame(lines, foot=True))        # 尾帧：完整脚本 + 页脚，长停顿
    durations = [45] * len(frames)
    durations[-1] = 2600
    OUT.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(OUT, save_all=True, append_images=frames[1:], duration=durations,
                   loop=0, optimize=True)
    print(f"已生成 {OUT}（{OUT.stat().st_size / 1024:.0f} KB，{len(frames)} 帧）")


if __name__ == "__main__":
    main()
