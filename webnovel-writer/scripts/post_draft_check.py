#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 2A/2B 后正文硬闸门（通用版，随 plugin 分发到所有项目）

目的：阻止起草期污染进入 Step 3 审查，避免浪费 10 个 checker + 9 个外部模型
的算力在明显机械问题上（ASCII 引号、Markdown 格式、禁用词、破例预算、缺失
伏笔种子、字数越界）。

配置机制：
  项目侧可在 `.webnovel/post_draft_config.json` 覆盖章号敏感配置，如：
      {
        "forbidden_terms_by_chapter": {
          "1": {"守夜人": "Ch1 只能出现 #4732，守夜人三字延后"}
        },
        "break_budget_by_chapter": {
          "1": {"老子": 1, "他妈": 0}
        },
        "required_seeds_by_chapter": {
          "1": [
            ["你不是第一个", "A3 伏笔 · 系统首发必须含此短语"],
            ["#4732", "A2 伏笔 · 系统编号"]
          ]
        }
      }
  未提供配置时只跑 5 项通用检查（ASCII/FFFD/Markdown/字数/空文件）。

用法：
  python scripts/post_draft_check.py <chapter_num>
    [--project-root PATH]
    [--strict]

退出码：
  0 全通过
  1 hard fail（起草硬污染，禁止进入 Step 3）
  2 结构错误（正文文件缺失/state.json 损坏等）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# 默认通用配置（无 post_draft_config.json 时使用）
# ---------------------------------------------------------------------------
DEFAULT_FORBIDDEN_TERMS: dict[int, dict[str, str]] = {}
DEFAULT_BREAK_BUDGET: dict[int, dict[str, int]] = {}
DEFAULT_REQUIRED_SEEDS: dict[int, list[tuple[str, str]]] = {}

# ---------------------------------------------------------------------------
# 汉语首句语法红线（2026-04-16 新增 · 全项目通用硬约束）
# ---------------------------------------------------------------------------
# 引入背景：Ch1 v1 "陆沉在死。" 语病首句被 19 个审查器+7 层审计全部放行
# 用户一眼看出"很奇怪"。根因是规则同源污染（所有审查器读同一套设定集，
# 其中开篇策略含"4字激活杏仁核"伪神经科学规则）。
#
# 本红线独立于任何设定集/开篇策略，纯中文母语语法检查。
CHINESE_OPENING_REJECT_PATTERNS: list[tuple[str, str]] = [
    # "X + 在 + 瞬时动词/抽象动词"：违反现代汉语体貌
    # 中文的"在"只能接持续性动作（"在看书" "在走路"），不接瞬时动词
    (
        r"^[\u4e00-\u9fff]{1,5}在(死|亡|倒|碎|断|崩|醒|觉醒|死去|倒下)[。.]?\s*$",
        "首句语病：'X 在 + 瞬时动词' 违反汉语体貌。'在'只接持续性动作，不接瞬时动词。"
        "如'陆沉在死'应改为'陆沉快死了'/'陆沉濒死'/'陆沉正在死去'。",
    ),
]


def load_project_config(project_root: Path) -> dict:
    cfg_path = project_root / ".webnovel" / "post_draft_config.json"
    if not cfg_path.exists():
        return {}
    try:
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  ⚠️  post_draft_config.json 解析失败: {e}（使用默认配置）")
        return {}


def find_chapter_file(project_root: Path, chapter: int) -> Path | None:
    padded = f"{chapter:04d}"
    candidates = sorted((project_root / "正文").glob(f"第{padded}章*.md"))
    return candidates[0] if candidates else None


def load_word_bounds(project_root: Path) -> tuple[int, int]:
    state_path = project_root / ".webnovel" / "state.json"
    try:
        d = json.loads(state_path.read_text(encoding="utf-8"))
        pi = d.get("project_info", {})
        return (
            int(pi.get("average_words_per_chapter_min", 2200)),
            int(pi.get("average_words_per_chapter_max", 3500)),
        )
    except Exception:
        return (2200, 3500)


def count_chinese_chars(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def check(project_root: Path, chapter: int) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    cfg = load_project_config(project_root)
    forbidden_terms = cfg.get("forbidden_terms_by_chapter", {}).get(
        str(chapter), DEFAULT_FORBIDDEN_TERMS.get(chapter, {})
    )
    break_budget = cfg.get("break_budget_by_chapter", {}).get(
        str(chapter), DEFAULT_BREAK_BUDGET.get(chapter, {})
    )
    required_seeds = cfg.get("required_seeds_by_chapter", {}).get(
        str(chapter), DEFAULT_REQUIRED_SEEDS.get(chapter, [])
    )

    fp = find_chapter_file(project_root, chapter)
    if not fp:
        errors.append(f"[ERROR] 章节文件缺失: 正文/第{chapter:04d}章*.md")
        return errors, warnings

    text = fp.read_text(encoding="utf-8")

    if not text.strip():
        errors.append("[ERROR] 章节文件为空")
        return errors, warnings

    # 0. 首句汉语自然度（2026-04-16 新增 · Ch1 v1 "陆沉在死"语病根治）
    first_line = ""
    for line in text.split("\n"):
        line = line.strip()
        if line and not line.startswith("#"):
            first_line = line
            break
    for pattern, reason in CHINESE_OPENING_REJECT_PATTERNS:
        if re.match(pattern, first_line):
            errors.append(
                f"[CHINESE_OPENING_REJECT] 首句 '{first_line[:40]}' — {reason}"
            )

    # 1. ASCII 双引号（硬约束 · 正文禁止）
    n_ascii_d = text.count(chr(34))
    if n_ascii_d > 0:
        errors.append(
            f"[ASCII_QUOTE] {n_ascii_d} 个 ASCII 双引号（必须 U+201C/U+201D）"
        )

    # 2. U+FFFD Unicode 替换字符（上下文压缩损坏征兆）
    n_fffd = text.count("\ufffd")
    if n_fffd > 0:
        errors.append(
            f"[FFFD] {n_fffd} 个 Unicode 替换字符（上下文压缩损坏）"
        )

    # 3. Markdown 标题 / 分隔线 / 粗体（正文禁止）
    md_titles = sum(
        1
        for line in text.split("\n")
        if line.startswith("# ") or line.startswith("## ")
    )
    md_hr = len(re.findall(r"^---+$", text, flags=re.MULTILINE))
    md_bold = text.count("**")
    if md_titles > 0:
        errors.append(f"[MARKDOWN] {md_titles} 个 # 标题（正文禁止）")
    if md_hr > 0:
        errors.append(f"[MARKDOWN] {md_hr} 处 --- 分隔线（正文禁止）")
    if md_bold > 0:
        errors.append(f"[MARKDOWN] {md_bold // 2} 处 ** 粗体（正文禁止）")

    # 4. 章号敏感禁用词（项目配置）
    for term, reason in forbidden_terms.items():
        n = text.count(term)
        if n > 0:
            errors.append(f"[FORBIDDEN] '{term}' × {n} — {reason}")

    # 5. 破例预算（项目配置 · 如主角粗口）
    for term, limit in break_budget.items():
        n = text.count(term)
        if n > limit:
            errors.append(
                f"[BREAK_BUDGET] '{term}' × {n} 超过预算 {limit}"
            )

    # 6. 必须伏笔种子（项目配置 · 正则）
    for pattern, note in required_seeds:
        if not re.search(pattern, text):
            errors.append(f"[REQUIRED_SEED] 缺失 /{pattern}/ — {note}")

    # 7. 字数区间（从 state.json 读）
    lo, hi = load_word_bounds(project_root)
    wc = count_chinese_chars(text)
    if wc < lo:
        errors.append(f"[WORD_COUNT] {wc} < {lo}（state.json 设置 {lo}-{hi}）")
    elif wc > hi:
        errors.append(f"[WORD_COUNT] {wc} > {hi}（state.json 设置 {lo}-{hi}）")
    else:
        warnings.append(f"[INFO] 字数 {wc} ∈ [{lo}, {hi}]")

    return errors, warnings


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Step 2A/2B 后正文硬闸门（通用版 · 随 plugin 分发）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("chapter", type=int, help="章节号（整数）")
    ap.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="项目根目录（默认从脚本位置推导，或当前目录）",
    )
    ap.add_argument("--strict", action="store_true", help="任何 warning 也 fail")
    args = ap.parse_args()

    # 项目根推导
    if args.project_root:
        project_root = args.project_root.resolve()
    else:
        # 尝试从 CWD 找 .webnovel
        cwd = Path.cwd()
        if (cwd / ".webnovel").exists():
            project_root = cwd
        else:
            # 脚本在 plugin cache 内，必须指定 --project-root
            print(
                "  ❌ 无法自动定位项目根。请用 --project-root 指定，"
                "或在项目根下运行。"
            )
            return 2

    print("=" * 60)
    print(f" 起草后硬闸门 · post_draft_check · Ch{args.chapter}")
    print(f" 项目：{project_root.name}")
    print("=" * 60)

    errors, warnings = check(project_root, args.chapter)

    if warnings:
        for w in warnings:
            print(f"  ⚠️  {w}")

    if errors:
        print(f"\n ❌ 发现 {len(errors)} 项硬问题：")
        for e in errors:
            print(f"  {e}")
        print(
            "\n  修复方式：\n"
            "    - ASCII_QUOTE：scripts/quote_pair_fix.py 批量替换\n"
            "    - FFFD：Grep 定位后 Edit 补\n"
            "    - MARKDOWN：移除 # / --- / ** 字符\n"
            "    - FORBIDDEN：改写避开禁用词（项目 .webnovel/post_draft_config.json 配置）\n"
            "    - BREAK_BUDGET：改写主角台词\n"
            "    - REQUIRED_SEED：Edit 补入伏笔句\n"
            "    - WORD_COUNT：扩写或压缩到 state.json 的 min-max 区间内"
        )
        return 1

    print("\n ✅ 全部通过，可进入 Step 3 审查")
    return 0 if not (args.strict and warnings) else 1


if __name__ == "__main__":
    sys.exit(main())
