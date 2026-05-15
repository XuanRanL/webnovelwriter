#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RCA Metadata Cleanup v2 · Round 28.29

Phase 2B: 更激进 sweep - 删除嵌入式 RCA 引用（不只是标题/标签）

策略：
- 圆括号内 "Round X.Y · ChN ..." → 整个括号删除
- 句中 "(Ch6 血教训)" / "(Round 18 新增)" → 整个括号删除
- 单独成段的 "**Round X · ChY deep research 三大新根因**：" 段落标题 → 替换为"硬规则"
- "Ch{N} 血教训" 不在括号里的 → 整句重写为 "曾发生过"
- "(Round XX · ChY RCA Task #N 根治)" → ""

保留：
- 检测 pattern + 阈值 + 命令模板 + 字段名

Usage:
  python cleanup_rca_metadata_v2.py [--dry-run]
"""
import re
import argparse
import sys
from pathlib import Path

# 整段删除 patterns（包括前后空行）
LINE_PATTERNS_TO_DELETE = [
    r"^\s*\*\*Round\s*\d+(?:\.\d+)*\s*[·\-—]?\s*Ch\d+\s+(?:deep\s+research\s+)?[^*]*?\*\*[：:]?\s*$",
]

# 更激进的内联替换
INLINE_PATTERNS = [
    # 圆括号内任何 Round/ChN/血教训/根治 标签
    (r"（\s*Round[^）]*?\s*\d+(?:\.\d+)?[^）]{0,150}?）", ""),
    (r"（\s*[一二三四五六七八九十]+\s*次\s*复发[^）]*?）", ""),
    (r"（\s*\d{4}-\d{2}-\d{2}[^）]{0,80}?）", ""),
    (r"（\s*\d{4}-\d{2}-\d{2}\s*）", ""),
    # 圆括号内含 "ChN 血教训"
    (r"（[^）]*?Ch\d+\s*血教训[^）]*?）", ""),
    (r"（[^）]*?血教训[^）]*?）", ""),
    (r"（[^）]*?Ch\d+\s+RCA[^）]*?）", ""),
    (r"（[^）]*?Ch\d+[^）]*?根治[^）]*?）", ""),
    (r"（[^）]*?根治[^）]*?Ch\d+[^）]*?）", ""),
    # 行尾的 RCA 标签：· Round 17.1 Ch7 RCA Task #10 根治
    (r"\s*[·\-—]\s*Round\s*\d+(?:\.\d+)?[^·\n]*?Ch\d+[^·\n]{0,100}", ""),
    (r"\s*[·\-—]\s*Ch\d+\s+RCA[^·\n]{0,100}", ""),
    # 标题中段：**Round X.Y · ChY deep research N 类新根因**：
    (r"\*\*Round\s*\d+(?:\.\d+)*\s*[·\-—]\s*Ch\d+[^*]{0,80}?\*\*[：:]?", "**深度根因**："),
    # 段中独立的 "Round 28.X" 短语（仅当后面接 RCA tag 时删除，避免破坏标题）
    (r"\bRound\s*\d+(?:\.\d+)*\s*[·\-—]\s*(?:Ch\d+|deep\s+research|RCA|血教训|根治|新增)", ""),
    # "Ch{N} 血教训" / "Ch{N} 血泪"
    (r"Ch\d+\s*血教训[^。\n]{0,30}[。]?", ""),
    (r"Ch\d+\s*血泪[^。\n]{0,30}[。]?", ""),
    (r"Ch\d+\s*RCA\s*[^。\n]{0,30}[。]?", ""),
    # 单独的"血教训"短语清理
    (r"血教训[：:]", ""),
    # "X 次复发"
    (r"\b\d+\s*次复发\b", ""),
    # "_comment_round[N]" JSON key
    (r'"_comment_round\d+"\s*:\s*"[^"]*",?\s*', ""),
    # 残留 "（）" 空中文圆括号（**不动 ASCII () 以保留函数调用**）
    (r"\s*（\s*）", ""),
    # 残留 "· ·" 双点
    (r"·\s*·", "·"),
    # 残留 ": "起始
    (r"^[：:]\s+", "", re.MULTILINE) if False else (r"^\s*[：:]\s+", ""),  # safer
    # 残留 "—— · ·" 多余分隔（**仅匹配中文破折号，不动 markdown ---**）
    (r"——\s*$(?!-)", ""),
]


def cleanup_text(text: str) -> tuple[str, dict]:
    stats = {
        "lines_deleted": 0,
        "inline_replacements": 0,
    }

    # Step 1: 删除整行
    lines = text.split("\n")
    out = []
    for line in lines:
        delete = False
        for pat in LINE_PATTERNS_TO_DELETE:
            if re.match(pat, line):
                delete = True
                stats["lines_deleted"] += 1
                break
        if not delete:
            out.append(line)
    text = "\n".join(out)

    # Step 2: 内联替换
    for pat_tuple in INLINE_PATTERNS:
        pat, repl = pat_tuple[0], pat_tuple[1]
        new_text, n = re.subn(pat, repl, text)
        if n > 0:
            stats["inline_replacements"] += n
            text = new_text

    # Step 3: 清理冗余空行 / 标点
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"·\s*·", "·", text)
    # **仅删除"·"（中文圆点），不动 - 和 — 以保护 markdown ---/-- 和函数名/破折号**
    text = re.sub(r"^\s*·\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s+·\s*$", "", text, flags=re.MULTILINE)
    # 双逗号
    text = re.sub(r"[，,]\s*[，,]", "，", text)
    # 残留 "（）" 中文圆括号（不动 ASCII () 保留函数调用）
    text = re.sub(r"（\s*）", "", text)

    return text, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--file", help="specific file")
    ap.add_argument("--root", default=".")
    args = ap.parse_args()

    fork = Path(args.root).resolve()
    targets = []
    if args.file:
        targets.append(Path(args.file))
    else:
        for pat in [
            "agents/*.md",
            "skills/webnovel-write/SKILL.md",
            "skills/webnovel-write/references/*.md",
            "skills/webnovel-write/references/writing/*.md",
            "skills/webnovel-write/references/shared/*.md",
            "skills/webnovel-init/SKILL.md",
            "skills/webnovel-init/references/*.md",
            "references/*.md",
        ]:
            for f in fork.glob(pat):
                if f.is_file():
                    targets.append(f)

    total_before = 0
    total_after = 0

    print(f"=== Phase 2B 激进 sweep ({'DRY' if args.dry_run else 'APPLY'}) ===\n")

    for path in sorted(targets):
        try:
            orig = path.read_text(encoding="utf-8")
        except Exception as e:
            continue
        cleaned, stats = cleanup_text(orig)
        bf, af = len(orig.encode("utf-8")), len(cleaned.encode("utf-8"))
        total_before += bf
        total_after += af
        if af < bf:
            if not args.dry_run:
                path.write_text(cleaned, encoding="utf-8")
            rel = path.relative_to(fork)
            print(f"  {rel}: -{bf-af}B (-{(bf-af)/bf*100:.1f}%) "
                  f"[lines:{stats['lines_deleted']} inline:{stats['inline_replacements']}]")

    print()
    saved = total_before - total_after
    print(f"=== Summary ===")
    print(f"  Total: {total_before} → {total_after} bytes")
    print(f"  Saved: {saved}B ({saved/total_before*100:.1f}%)")
    print(f"  Estimated tokens saved: ~{saved // 3}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
