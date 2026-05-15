#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RCA Metadata Cleanup · Round 28.29

目的：清理 plugin .md 文件中的历史 RCA 元数据标注，节省 token + 解决 PII 泄漏。

删除：
- 标题中 "Round X.Y · 日期 · ChN RCA · 描述" 前缀
- 圆括号内 "（YYYY-MM-DD Round X 新增/根治/...）" 标注
- 项目名（<example-project>/<example-project-A>/<example-project-B>/<example-project-C>/<example-project-D>/<example-project>）
- "ChN 血教训/血泪" 短语

保留：
- 规则正文 / 检测 pattern / 阈值 / 示例 / 命令模板

Usage:
  python cleanup_rca_metadata.py [--dry-run] [--file FILE]

退出码：0 = 干净, 1 = 检测到漂移
"""
import re
import argparse
import sys
from pathlib import Path

# 项目名 → 通用占位符
PROJECT_NAME_MAP = {
    "<example-project>": "<example-project>",
    "<example-project>": "<example-project>",
    "<example-project-A>": "<example-project-A>",
    "<example-project-B>": "<example-project-B>",
    "<example-project-C>": "<example-project-C>",
    "<example-project-D>": "<example-project-D>",
    "<example-project>": "<example-project>",  # 单独的"<example-project>"（不带后缀）
    "<example-project>": "<example-project>",
    "<example-project-A>": "<example-project-A>",
    "<example-project-B>": "<example-project-B>",
    "<example-project-C>": "<example-project-C>",
}

# 整行删除 patterns（包括前后空行）
LINE_PATTERNS_TO_DELETE = [
    # 完整 RCA 标题行（含粗体）
    r"^\s*\*\*Round\s*\d+(?:\.\d+)*\s*[·\-—]?\s*(?:\d{4}-\d{2}-\d{2}\s*[·\-—]?\s*)?Ch\d+\s+RCA[^*]*\*\*[：:]?\s*$",
]

# 内联替换 patterns（保留行，移除标注）
INLINE_PATTERNS = [
    # 括号内 RCA 标注：（2026-04-23 Round 17 新增）/（Round 22.x · 2026-05-01 · Ch8 触发全章扫）
    (r"（\s*\d{4}-\d{2}-\d{2}[^）]{0,80}?(?:Round\s*\d+(?:\.\d+)?|新增|根治|RCA|血教训)[^）]{0,80}?）", ""),
    (r"（\s*Round\s*\d+(?:\.\d+)?[^）]{0,80}?(?:Ch\d+|根治|RCA|血教训|新增)[^）]{0,80}?）", ""),
    # 标题/段首 "**Round 28.X · ChY RCA · 描述**：" → ""
    (r"\*\*Round\s*\d+(?:\.\d+)*\s*[·\-—]?\s*(?:\d{4}-\d{2}-\d{2}\s*[·\-—]?\s*)?Ch\d+\s+RCA\s*[·\-—][^*]*?\*\*[：:]?", ""),
    # 标题/段首 "**Round 28.X · 描述（ChY RCA · 根治）**：" → "**描述**："
    (r"\*\*Round\s*\d+(?:\.\d+)*\s*[·\-—]\s*", "**"),
    # "Ch{N} 血教训" 短语 → ""
    (r"Ch\d+\s*血教训", ""),
    (r"Ch\d+\s*血泪", ""),
    # "Ch{N} RCA" 中间出现 → ""
    (r"Ch\d+\s+RCA\s*[·\-—]?\s*", ""),
    # "2026-XX-XX" 时间戳（独立出现，不在 JSON value 里）→ ""
    (r"·?\s*\d{4}-\d{2}-\d{2}\s*[·\-—]?", ""),
    # 项目名列表"（<example-project> / <example-project-A> / <example-project-B> / <example-project-C> / 等等）"→ "（本插件所有项目）"
    (r"（<example-project>(?:[^）]*?(?:<example-project-A>|<example-project-B>|<example-project-C>|<example-project>))?[^）]*?等等?）", "（本插件所有项目）"),
    (r"（<example-project>(?:[^）]*?(?:<example-project-A>|<example-project-B>|<example-project-C>|<example-project>))[^）]*?）", "（本插件所有项目）"),
]


def cleanup_text(text: str) -> tuple[str, dict]:
    """返回 (cleaned_text, stats)"""
    stats = {
        "lines_deleted": 0,
        "inline_patterns_applied": 0,
        "project_names_replaced": 0,
    }

    # Step 1: 删除整行 patterns
    lines = text.split("\n")
    out_lines = []
    for line in lines:
        should_delete = False
        for pat in LINE_PATTERNS_TO_DELETE:
            if re.match(pat, line):
                should_delete = True
                stats["lines_deleted"] += 1
                break
        if not should_delete:
            out_lines.append(line)
    text = "\n".join(out_lines)

    # Step 2: 内联 pattern 替换
    for pat, replacement in INLINE_PATTERNS:
        new_text, n = re.subn(pat, replacement, text)
        if n > 0:
            stats["inline_patterns_applied"] += n
            text = new_text

    # Step 3: 项目名替换（按长度降序，避免子串误替换）
    for proj_name in sorted(PROJECT_NAME_MAP.keys(), key=len, reverse=True):
        placeholder = PROJECT_NAME_MAP[proj_name]
        if proj_name in text:
            count = text.count(proj_name)
            text = text.replace(proj_name, placeholder)
            stats["project_names_replaced"] += count

    # Step 4: 清理多余空行（连续 3+ 空行 → 2 空行）
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Step 5: 清理孤立的 "·" 或 "、" 标点（删除标注后残留）
    text = re.sub(r"·\s*[）)]", "）", text)
    text = re.sub(r"·\s*·", "·", text)
    text = re.sub(r"\s+·\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^·\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"（\s*[·\-—]?\s*）", "", text)
    text = re.sub(r"（\s*）", "", text)

    return text, stats


def process_file(path: Path, dry_run: bool = False) -> dict:
    """返回 stats dict"""
    original = path.read_text(encoding="utf-8")
    cleaned, stats = cleanup_text(original)

    bytes_before = len(original.encode("utf-8"))
    bytes_after = len(cleaned.encode("utf-8"))
    stats["bytes_before"] = bytes_before
    stats["bytes_after"] = bytes_after
    stats["bytes_saved"] = bytes_before - bytes_after
    stats["pct_saved"] = (stats["bytes_saved"] / bytes_before * 100) if bytes_before else 0

    # 只要有任何修改（删除行/inline 替换/项目名匿名化），就写文件
    has_changes = (
        stats["lines_deleted"] > 0
        or stats["inline_patterns_applied"] > 0
        or stats["project_names_replaced"] > 0
    )
    if not dry_run and has_changes:
        path.write_text(cleaned, encoding="utf-8")

    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="不写文件，只报告")
    ap.add_argument("--file", help="只处理指定文件")
    ap.add_argument("--root", default=".", help="fork root")
    args = ap.parse_args()

    fork_root = Path(args.root).resolve()

    targets = []
    if args.file:
        targets.append(Path(args.file))
    else:
        # 5 大 agent 文件 + SKILL.md + 关键 references
        for pat in [
            "agents/*.md",
            "skills/webnovel-write/SKILL.md",
            "skills/webnovel-write/references/*.md",
            "skills/webnovel-init/SKILL.md",
            "skills/webnovel-init/references/*.md",
            "skills/webnovel-write/references/writing/*.md",
            "skills/webnovel-write/references/shared/*.md",
            "references/*.md",
        ]:
            for f in fork_root.glob(pat):
                if f.is_file():
                    targets.append(f)

    total_before = 0
    total_after = 0
    total_lines_deleted = 0
    total_inline_applied = 0
    total_proj_replaced = 0
    affected_files = []

    print(f"=== RCA Metadata Cleanup ({'DRY RUN' if args.dry_run else 'APPLY'}) ===")
    print()

    for path in sorted(targets):
        try:
            stats = process_file(path, dry_run=args.dry_run)
        except Exception as e:
            print(f"  ERROR {path}: {e}")
            continue
        total_before += stats["bytes_before"]
        total_after += stats["bytes_after"]
        total_lines_deleted += stats["lines_deleted"]
        total_inline_applied += stats["inline_patterns_applied"]
        total_proj_replaced += stats["project_names_replaced"]

        if stats["bytes_saved"] > 0:
            affected_files.append((path, stats))
            rel = path.relative_to(fork_root)
            print(f"  {rel}: -{stats['bytes_saved']}B (-{stats['pct_saved']:.1f}%) "
                  f"[lines:{stats['lines_deleted']} inline:{stats['inline_patterns_applied']} "
                  f"proj:{stats['project_names_replaced']}]")

    print()
    print(f"=== Summary ===")
    print(f"  Files scanned: {len(targets)}")
    print(f"  Files modified: {len(affected_files)}")
    print(f"  Total bytes: {total_before} → {total_after} (saved {total_before - total_after}, {(total_before - total_after) / total_before * 100:.1f}%)")
    print(f"  Estimated tokens saved: ~{(total_before - total_after) // 3}")
    print(f"  Total lines deleted: {total_lines_deleted}")
    print(f"  Inline replacements: {total_inline_applied}")
    print(f"  Project names anonymized: {total_proj_replaced}")

    return 0 if not affected_files else (0 if not args.dry_run else 1)


if __name__ == "__main__":
    sys.exit(main())
