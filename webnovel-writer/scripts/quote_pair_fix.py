#!/usr/bin/env python3
"""段内独立中文弯引号配对修复器

应对场景：
- ASCII 双引号 `"..."` 批量替换为弯引号时，单次 flip-pair 会跨段翻转奇偶，
  在段内嵌套对话（对话中再启引用）时造成第二层开引号错写为右引号。
- 这个脚本按「段」独立配对，每段内奇数次出现=U+201C（开），偶数次=U+201D（闭）。
- 段分隔符：空行 (`\n\n+`)。
- 不会更改已经合法配对的段；只重写段内配对数量不匹配或方向错乱的段。

用法：
    python quote_pair_fix.py <chapter_file.md>                    # 原地修
    python quote_pair_fix.py <chapter_file.md> --dry-run          # 只报告
    python quote_pair_fix.py <chapter_file.md> --output fixed.md  # 另存

退出码：0=无需修或修成功 / 1=语法错误 / 2=IO
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

OPEN = "\u201c"
CLOSE = "\u201d"


def fix_paragraph(para: str) -> tuple[str, bool]:
    """段内独立配对。返回 (修后内容, 是否修改过)。"""
    opens = para.count(OPEN)
    closes = para.count(CLOSE)
    if opens == closes:
        # 配对数量匹配，但仍可能顺序错（右引号先于左引号）。检查状态机：
        flip = False
        ok = True
        for ch in para:
            if ch == OPEN:
                if flip:
                    ok = False
                    break
                flip = True
            elif ch == CLOSE:
                if not flip:
                    ok = False
                    break
                flip = False
        if ok:
            return para, False
    # 不匹配或顺序错：按段内独立奇偶配对重写
    buf = []
    flip = False
    for ch in para:
        if ch == OPEN or ch == CLOSE:
            buf.append(OPEN if not flip else CLOSE)
            flip = not flip
        else:
            buf.append(ch)
    return "".join(buf), True


def fix_text(text: str) -> tuple[str, int, int]:
    """返回 (修后文本, 总段数, 修复段数)。"""
    # 保留分隔符，使用 finditer
    segs = re.split(r"(\n{2,})", text)  # keep separators
    total = 0
    fixed = 0
    out = []
    for seg in segs:
        if seg.startswith("\n"):
            out.append(seg)
            continue
        if not seg.strip():
            out.append(seg)
            continue
        total += 1
        new, changed = fix_paragraph(seg)
        if changed:
            fixed += 1
        out.append(new)
    return "".join(out), total, fixed


def main():
    p = argparse.ArgumentParser()
    p.add_argument("path", type=str)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--output", type=str, default=None)
    args = p.parse_args()

    pth = Path(args.path)
    if not pth.exists():
        print(f"[FAIL] not found: {pth}", file=sys.stderr)
        sys.exit(2)
    text = pth.read_text(encoding="utf-8")
    new, total, fixed = fix_text(text)
    print(f"paragraphs total={total}, fixed={fixed}")
    if new == text:
        print("no change needed")
        sys.exit(0)
    if args.dry_run:
        print("--dry-run: not writing")
        sys.exit(0)
    out = Path(args.output) if args.output else pth
    out.write_text(new, encoding="utf-8", newline="\n")
    print(f"written: {out}")
    # post-check
    check = out.read_text(encoding="utf-8")
    bad = 0
    for para in re.split(r"\n{2,}", check):
        if para.count(OPEN) != para.count(CLOSE):
            bad += 1
    if bad:
        print(f"[FAIL] {bad} paragraphs still mismatched", file=sys.stderr)
        sys.exit(1)
    print("post-check: all paragraphs balanced")
    sys.exit(0)


if __name__ == "__main__":
    main()
