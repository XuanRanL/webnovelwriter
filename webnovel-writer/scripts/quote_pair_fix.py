#!/usr/bin/env python3
"""段内独立中文弯引号配对修复器 · Round 15.3 增强

应对场景：
- Claude Code Write/Edit 工具把 U+201C/U+201D 中文弯引号转成 ASCII " (U+0022)。
  → --ascii-to-curly 模式（默认）：先把 ASCII 双引号按段奇偶配对转成 U+201C/U+201D。
- ASCII 双引号 "..." 批量替换为弯引号时，单次 flip-pair 会跨段翻转奇偶，
  在段内嵌套对话（对话中再启引用）时造成第二层开引号错写为右引号。
  → 这个脚本按「段」独立配对，每段内奇数次出现=U+201C（开），偶数次=U+201D（闭）。
- 段分隔符：空行 (\\n\\n+)。
- 不会更改已经合法配对的段；只重写段内配对数量不匹配或方向错乱的段。

用法：
    python quote_pair_fix.py <chapter_file.md>                    # 原地修 · 含 ASCII→弯
    python quote_pair_fix.py <chapter_file.md> --strict-curly     # 仅修弯引号配对错乱
    python quote_pair_fix.py <chapter_file.md> --dry-run          # 只报告
    python quote_pair_fix.py <chapter_file.md> --output fixed.md  # 另存

退出码：0=无需修或修成功 / 1=语法错误（段仍不配对） / 2=IO
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

OPEN = "“"
CLOSE = "”"
ASCII_DQ = chr(34)


def fix_paragraph_curly(para: str) -> tuple[str, bool]:
    """段内独立配对（仅处理 U+201C/U+201D）。返回 (修后内容, 是否修改过)。"""
    opens = para.count(OPEN)
    closes = para.count(CLOSE)
    if opens == closes:
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
    buf = []
    flip = False
    for ch in para:
        if ch == OPEN or ch == CLOSE:
            buf.append(OPEN if not flip else CLOSE)
            flip = not flip
        else:
            buf.append(ch)
    return "".join(buf), True


def fix_paragraph_ascii_to_curly(para: str) -> tuple[str, bool]:
    """段内把 ASCII " 和已有弯引号统一重新配对。

    Round 15.3 · 2026-04-23 · Ch6 血教训：
    - Claude Code Write/Edit 工具把 U+201C/201D 规范化成 ASCII "
    - 统一 3 种引号（ASCII " / U+201C / U+201D）视为"引号"，按段内奇偶决定 open/close
    """
    if ASCII_DQ not in para and OPEN not in para and CLOSE not in para:
        return para, False
    unified = para.replace(OPEN, ASCII_DQ).replace(CLOSE, ASCII_DQ)
    buf = []
    flip = False
    for ch in unified:
        if ch == ASCII_DQ:
            buf.append(OPEN if not flip else CLOSE)
            flip = not flip
        else:
            buf.append(ch)
    out = "".join(buf)
    return out, out != para


def fix_paragraph(para: str, ascii_to_curly: bool = True) -> tuple[str, bool]:
    """段内独立配对（默认含 ASCII→弯引号转换）。"""
    if ascii_to_curly:
        return fix_paragraph_ascii_to_curly(para)
    return fix_paragraph_curly(para)


_FENCED_RE = re.compile(r"(```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`\n]+`)", re.MULTILINE)


def _mask_fenced(text: str) -> tuple[str, list[str]]:
    """Round 19 · 把 markdown ``` fenced block / inline ` code ` 替换成占位符。

    防御点：fenced 内可能含 bash heredoc / Python f-string / JSON 等带 ASCII " 的代码，
    若按段奇偶配对会把 `if [ -z "$X" ]` 等语法破坏。占位符不含引号且参与段切分但不被改写。
    """
    blocks: list[str] = []

    def _sub(m):
        blocks.append(m.group(0))
        return f"QPF_FENCED_{len(blocks) - 1}"

    return _FENCED_RE.sub(_sub, text), blocks


def _unmask_fenced(text: str, blocks: list[str]) -> str:
    for i, blk in enumerate(blocks):
        text = text.replace(f"QPF_FENCED_{i}", blk)
    return text


def fix_text(text: str, ascii_to_curly: bool = True) -> tuple[str, int, int]:
    """返回 (修后文本, 总段数, 修复段数)。

    Round 19 · 增加 fenced code 保护：先 mask ``` 块和 inline `code`，处理完再还原。
    """
    masked, blocks = _mask_fenced(text)
    segs = re.split(r"(\n{2,})", masked)
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
        new, changed = fix_paragraph(seg, ascii_to_curly=ascii_to_curly)
        if changed:
            fixed += 1
        out.append(new)
    result = _unmask_fenced("".join(out), blocks)
    return result, total, fixed


def main():
    p = argparse.ArgumentParser()
    p.add_argument("path", type=str)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--strict-curly",
        action="store_true",
        help="仅修弯引号配对错乱，不做 ASCII→弯 转换（Round 15.3 前的旧行为）",
    )
    p.add_argument("--output", type=str, default=None)
    p.add_argument(
        "--force",
        action="store_true",
        help="Round 19.1 P0-2：强制对非 .md 文件运行（默认对代码/数据文件跳过）",
    )
    args = p.parse_args()

    pth = Path(args.path)
    if not pth.exists():
        print(f"[FAIL] not found: {pth}", file=sys.stderr)
        sys.exit(2)

    # Round 19.1 P0-2 文件类型守卫：仅对 .md 默认运行
    # 历史教训：对 .py/.json/.yaml/.toml/.csv 跑会按段奇偶配对破坏 Python 字符串/JSON 引号/CSV 字段
    SKIP_EXTENSIONS = {".py", ".json", ".yaml", ".yml", ".toml", ".csv", ".tsv", ".xml", ".js", ".ts", ".sh", ".bat", ".ps1", ".sql"}
    suffix = pth.suffix.lower()
    if suffix in SKIP_EXTENSIONS and not args.force:
        print(f"[SKIP] {pth} suffix={suffix} 默认跳过（代码/数据文件）。需要强制跑请加 --force")
        sys.exit(0)
    if not suffix and not args.force:
        # 无扩展名也保险跳过
        print(f"[SKIP] {pth} 无扩展名，默认跳过。需要强制请加 --force")
        sys.exit(0)

    text = pth.read_text(encoding="utf-8")
    ascii_to_curly = not args.strict_curly
    new, total, fixed = fix_text(text, ascii_to_curly=ascii_to_curly)
    mode = "ascii-to-curly" if ascii_to_curly else "strict-curly"
    print(f"[mode={mode}] paragraphs total={total}, fixed={fixed}")
    if new == text:
        print("no change needed")
        # 仍做最终配对校验（因为可能完全 ASCII 但数量全偶的情况已经处理）
        sys.exit(0)
    if args.dry_run:
        print("--dry-run: not writing")
        sys.exit(0)
    out = Path(args.output) if args.output else pth
    out.write_text(new, encoding="utf-8", newline="\n")
    print(f"written: {out}")
    check = out.read_text(encoding="utf-8")
    bad = 0
    remaining_ascii = check.count(ASCII_DQ)
    for para in re.split(r"\n{2,}", check):
        if para.count(OPEN) != para.count(CLOSE):
            bad += 1
    if bad:
        print(f"[FAIL] {bad} paragraphs still mismatched", file=sys.stderr)
        sys.exit(1)
    if remaining_ascii and ascii_to_curly:
        print(f"[WARN] 仍有 {remaining_ascii} 个 ASCII 双引号（可能在代码块/属性标记里）", file=sys.stderr)
    print("post-check: all paragraphs balanced, ascii_dq={}".format(remaining_ascii))
    sys.exit(0)


if __name__ == "__main__":
    main()
