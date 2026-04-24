#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 2A/2B 后正文硬闸门（通用版，随 plugin 分发到所有项目）

目的：阻止起草期污染进入 Step 3 审查，避免浪费 13 个 checker + 9 个外部模型（Round 13 v2）
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
    """读 SSOT 字数区间 · 优先 word_count_policy.hard_min/max（Round 15.1）"""
    state_path = project_root / ".webnovel" / "state.json"
    try:
        d = json.loads(state_path.read_text(encoding="utf-8"))
        pi = d.get("project_info", {})
        wcp = pi.get("word_count_policy") or {}
        if wcp:
            return (
                int(wcp.get("hard_min", pi.get("average_words_per_chapter_min", 2200))),
                int(wcp.get("hard_max", pi.get("average_words_per_chapter_max", 3500))),
            )
        return (
            int(pi.get("average_words_per_chapter_min", 2200)),
            int(pi.get("average_words_per_chapter_max", 3500)),
        )
    except Exception:
        return (2200, 3500)


# ---------------------------------------------------------------------------
# Round 15.1 · 2026-04-22 · editor_notes 字数漂移检测
# ---------------------------------------------------------------------------
# 背景：2026-04-13 / 04-15 / 04-22 三次复现同一根因——audit-agent 在写
# editor_notes/ch{N+1}_prep.md 时凭印象写字数区间（如 2800-3500），下章
# context-agent 读 editor_notes 后直接把错误区间灌进执行包，writer
# 基于错误区间 over-draft。SSOT 应唯一来源于 state.project_info.word_count_policy。
#
# 本检查扫描以下三个产物中的 "X-Y" 字数模式，任一与 SSOT 不一致 → warn：
#   1. .webnovel/editor_notes/ch{NNNN}_prep.md
#   2. .webnovel/context/ch{NNNN}_context.json  (context_contract.word_count_target)
#   3. .webnovel/context/ch{NNNN}_context.md
# ---------------------------------------------------------------------------
WORD_COUNT_RANGE_RE = re.compile(
    r"(?P<lo>\b[23]\d{3})\s*[-—–]\s*(?P<hi>\b[23]\d{3})\b"
)


def load_word_policy_subranges(project_root: Path) -> list[tuple[int, int]]:
    """读 state.word_count_policy.chapter_type_guide 的合法子区间白名单"""
    state_path = project_root / ".webnovel" / "state.json"
    default = [(2200, 2800), (2600, 3200), (2800, 3400), (3000, 3500)]
    try:
        d = json.loads(state_path.read_text(encoding="utf-8"))
        wcp = d.get("project_info", {}).get("word_count_policy", {})
        guide = wcp.get("chapter_type_guide", {})
        ranges: list[tuple[int, int]] = []
        for v in guide.values():
            m = WORD_COUNT_RANGE_RE.search(str(v))
            if m:
                ranges.append((int(m.group("lo")), int(m.group("hi"))))
        return ranges or default
    except Exception:
        return default


def check_editor_notes_word_drift(
    project_root: Path, chapter: int, ssot_lo: int, ssot_hi: int
) -> list[str]:
    """扫描 editor_notes 和 context JSON/MD，检测字数区间漂移

    判定规则（Round 15.1）：
      a. 完整 SSOT 区间（2200-3500）：OK
      b. chapter_type_guide 白名单子区间（过渡/推进/情感/战斗四档）：OK
      c. 外溢 SSOT（如 2100-3500 / 2200-3600）：DRIFT · 外溢
      d. 任意其他收紧（如 2800-3500 / 2400-3200 / 2700-3200）：DRIFT · 伪窄
    """
    warnings: list[str] = []
    padded = f"{chapter:04d}"

    candidates = [
        project_root / ".webnovel" / "editor_notes" / f"ch{padded}_prep.md",
        project_root / ".webnovel" / "context" / f"ch{padded}_context.json",
        project_root / ".webnovel" / "context" / f"ch{padded}_context.md",
    ]

    whitelist = set(load_word_policy_subranges(project_root))
    full_ssot = {(ssot_lo, ssot_hi)}
    allowed = whitelist | full_ssot

    for cand in candidates:
        if not cand.exists():
            continue
        try:
            text = cand.read_text(encoding="utf-8")
        except Exception:
            continue

        for m in WORD_COUNT_RANGE_RE.finditer(text):
            lo, hi = int(m.group("lo")), int(m.group("hi"))
            ctx_start = max(0, m.start() - 30)
            ctx_end = min(len(text), m.end() + 10)
            ctx = text[ctx_start:ctx_end]
            if not any(
                k in ctx for k in ("字数", "word_count", "字符")
            ):
                continue
            # 负样本豁免（Round 15.2 · 2026-04-23 修复）：
            # 若区间出现在 forbidden / 禁止 / 不得 / 不能 / 不得自造 / forbidden_items
            # / word_count_narrowing / disallowed / 负样本 等上下文内（前后 120 字节内），
            # 说明是声明"禁区"而非"实际采用"——必须豁免，否则 context-agent 无法在
            # forbidden 列表里反讽式列举伪窄区间（Ch5 ch0005_context.json L40/L655 案例）
            neg_start = max(0, m.start() - 120)
            neg_end = min(len(text), m.end() + 120)
            neg_ctx = text[neg_start:neg_end]
            _neg_markers = (
                "forbidden", "禁止", "不得", "不能", "不得自造",
                "word_count_narrowing", "disallowed", "负样本",
                "自造字数区间", "伪窄", "forbidden_items",
            )
            if any(k in neg_ctx for k in _neg_markers):
                continue
            # a/b: 完整 SSOT 或白名单子区间
            if (lo, hi) in allowed:
                continue
            # c: 外溢
            if lo < ssot_lo or hi > ssot_hi:
                warnings.append(
                    f"[EDITOR_NOTES_WORD_DRIFT] {cand.name} 字数区间 "
                    f"{lo}-{hi} 外溢 SSOT {ssot_lo}-{ssot_hi}（state.word_count_policy）"
                )
            # d: 伪收紧（在 SSOT 内但不在白名单）
            else:
                warnings.append(
                    f"[EDITOR_NOTES_WORD_DRIFT] {cand.name} 字数区间 "
                    f"{lo}-{hi} 是伪窄区间（SSOT={ssot_lo}-{ssot_hi}，合法子区间="
                    f"{sorted(allowed)}）· context-agent 应以 SSOT 或正确 "
                    f"chapter_type_guide 子区间覆盖"
                )
    return warnings


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

    # 7. 字数区间（从 state.json 读 · Round 15.1 优先 word_count_policy.hard_min/max）
    lo, hi = load_word_bounds(project_root)
    wc = count_chinese_chars(text)
    if wc < lo:
        errors.append(f"[WORD_COUNT] {wc} < {lo}（state.json 设置 {lo}-{hi}）")
    elif wc > hi:
        errors.append(f"[WORD_COUNT] {wc} > {hi}（state.json 设置 {lo}-{hi}）")
    else:
        warnings.append(f"[INFO] 字数 {wc} ∈ [{lo}, {hi}]")

    # 8. Round 15.1 · editor_notes / context JSON 字数漂移检测（非阻断 · warn）
    warnings.extend(check_editor_notes_word_drift(project_root, chapter, lo, hi))

    # 9. Round 17.1 · 对话占比下限（2026-04-24 · Ch7 RCA F2 根治）
    # 引入背景：Round 16 约束 VII 要求对话占比 ≥ 0.20（连 3 章 < 0.2 触发 H21 fail），
    # 但 post_draft_check 不检查，polish 阶段才挣扎。本闸门在起草后即提示。
    # 配置可在 post_draft_config.json 自定义 dialogue_ratio_min（默认 0.20）。
    # 豁免：chapter_type_guide 允许"空间视觉化章/高密度纯动作章"声明 override。
    dr_min = cfg.get("dialogue_ratio_min", 0.20)
    dr_override_chapters = set(cfg.get("dialogue_ratio_override_chapters", []))
    if chapter not in dr_override_chapters:
        dialogue_parts = re.findall(r"[“]([^”]*)[”]", text)
        total_cc = len(re.findall(r"[一-鿿]", text))
        dialogue_cc = sum(
            len(re.findall(r"[一-鿿]", d)) for d in dialogue_parts
        )
        if total_cc > 0:
            ratio = dialogue_cc / total_cc
            if ratio < dr_min - 0.005:  # 2.5% 浮点容差
                errors.append(
                    f"[DIALOGUE_RATIO] 对话占比 {ratio:.3f} < {dr_min:.2f}"
                    f"（约束 VII · 连 3 章 < 0.2 触发 H21 fail）"
                )
            elif ratio < dr_min:
                warnings.append(
                    f"[DIALOGUE_RATIO_BORDER] 对话占比 {ratio:.3f}"
                    f"（贴近下限 {dr_min:.2f}，建议 Step 4 扩对话）"
                )

    # 10. Round 17.1 · 元标识符扫描（2026-04-24 · Ch7 RCA F6 根治）
    # 引入背景：Ch7 首稿 L183 "一次是 Ch1 那个清晨，一次是 Ch4 守夜人系统的第一次登录"
    # 元标识符 Ch{N} 不应出现在正文（小说人物不知道章号）。
    # 根因：context-agent 的 immutable_facts 用"Ch1/Ch4"简写，主 agent 照搬入正文。
    metaref_patterns = [
        (r"\bCh\d+\b", "Ch{N} 元标识符"),
        (r"\[Ch\d+\]", "[Ch{N}] 章号标注"),
        (r"第\s*\d+\s*章", "第N章元标识符"),
    ]
    for pat, name in metaref_patterns:
        hits = re.findall(pat, text)
        if hits:
            errors.append(
                f"[METAREF] 正文含 {len(hits)} 处 {name}（样本：{hits[:3]}）· "
                f"人物不知道章号 · 必须自然化表述"
            )

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
    ap.add_argument(
        "--no-auto-fix",
        action="store_true",
        help="禁用 ASCII 引号自动修复（默认启用 · Round 15.3 · 根治 Claude Code Write/Edit 转 ASCII 的 Bug #3）",
    )
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

    # Round 15.3 · 2026-04-23 · Ch6 RCA Bug #3 根治：
    # Claude Code Write/Edit 工具把 U+201C/201D 转 ASCII，导致每章起草后都有 ASCII 引号。
    # 这里在第一次 check 前自动跑 quote_pair_fix.py --ascii-to-curly，自动根治。
    # 用户可用 --no-auto-fix 禁用。
    if not args.no_auto_fix:
        try:
            import glob as _glob

            chapter_padded = f"{args.chapter:04d}"
            candidates = _glob.glob(str(project_root / "正文" / f"第{chapter_padded}章*.md"))
            if candidates:
                chapter_file = candidates[0]
                text_before = Path(chapter_file).read_text(encoding="utf-8")
                if chr(34) in text_before:
                    # 调 quote_pair_fix 模块（内联 import）
                    import importlib.util as _iu

                    qp_path = Path(__file__).parent / "quote_pair_fix.py"
                    if qp_path.exists():
                        _spec = _iu.spec_from_file_location("quote_pair_fix", qp_path)
                        _mod = _iu.module_from_spec(_spec)
                        _spec.loader.exec_module(_mod)
                        new_text, total, fixed = _mod.fix_text(text_before, ascii_to_curly=True)
                        if new_text != text_before:
                            Path(chapter_file).write_text(new_text, encoding="utf-8", newline="\n")
                            print(
                                f"  🔧 [auto-fix] ASCII 引号 → 弯引号："
                                f"段 {total}, 修 {fixed}（写回 {Path(chapter_file).name}）"
                            )
        except Exception as _ex:
            print(f"  ⚠️ auto-fix 内部异常（继续跑硬闸门）: {_ex}")

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
