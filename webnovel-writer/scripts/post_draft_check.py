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
          "1": {"<power-faction>": "Ch1 只能出现 #4732，<power-faction>三字延后"}
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
# 引入背景：Ch1 v1 "<protagonist>在死。" 语病首句被 19 个审查器+7 层审计全部放行
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
        "如'<protagonist>在死'应改为'<protagonist>快死了'/'<protagonist>濒死'/'<protagonist>正在死去'。",
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
                int(wcp.get("hard_max", pi.get("average_words_per_chapter_max", 3800))),
            )
        return (
            int(pi.get("average_words_per_chapter_min", 2200)),
            int(pi.get("average_words_per_chapter_max", 3800)),
        )
    except Exception:
        return (2200, 3800)


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
    default = [(2200, 2900), (2700, 3300), (2900, 3500), (3200, 3800)]
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
      a. 完整 SSOT 区间（2200-3800 · Round 21.1）：OK
      b. chapter_type_guide 白名单子区间（过渡/推进/情感/战斗四档）：OK
      c. 外溢 SSOT（如 2100-3800 / 2200-3900）：DRIFT · 外溢
      d. 任意其他收紧（如 2900-3800 / 2400-3300 / 2700-3300）：DRIFT · 伪窄
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
            # 负样本豁免（Round 15.2 · 2026-04-23 修复 + Round 18 · 2026-04-24 · Ch10 P0-2 扩充）：
            # 若区间出现在 forbidden / 禁止 / 不得 / 不能 / 不得自造 / forbidden_items
            # / word_count_narrowing / disallowed / 负样本 等上下文内（前后 200 字节内），
            # 说明是声明"禁区"而非"实际采用"——必须豁免，否则 context-agent 无法在
            # forbidden 列表里反讽式列举伪窄区间（Ch5 ch0005_context.json L40/L655 案例）
            #
            # Round 18 · Ch10 P0-2 根因：context-agent forbidden_items 描述里写
            # "字数自造区间（如 2800-3200 / 2700-3200 / 2400-3200·非 SSOT 派生白名单）"
            # 这种反例列举被误判。扩展窗口到 200 字节 + 加 "字数自造" / "如 N-N" / "白名单外" /
            # "非 SSOT" / "派生白名单" / "示例" / "反例" 等 markers。
            neg_start = max(0, m.start() - 200)
            neg_end = min(len(text), m.end() + 200)
            neg_ctx = text[neg_start:neg_end]
            _neg_markers = (
                "forbidden", "禁止", "不得", "不能", "不得自造",
                "word_count_narrowing", "disallowed", "负样本",
                "自造字数区间", "伪窄", "forbidden_items",
                # Round 18 新增：
                "字数自造", "字数自造区间", "白名单外", "非 SSOT",
                "派生白名单", "示例", "反例", "反讽", "如 ", "rationale",
                "alternative_suggestions", "alternative",
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


def _count_recent_word_drift_chapters(project_root: Path, current_chapter: int, lookback: int = 3) -> int:
    """Round 18.2 · Ch11 RCA #1 根治：检测近 N 章 EDITOR_NOTES_WORD_DRIFT 连续命中。

    扫描 .webnovel/editor_notes/chXXXX_prep.md 里的字数区间，对每个章号判断是否含
    白名单外区间。返回连续命中（包含当前章）的章数；当 ≥3 时上层把 warning 升 ERROR。
    """
    if current_chapter < 2:
        return 0
    notes_dir = project_root / ".webnovel" / "editor_notes"
    if not notes_dir.exists():
        return 0
    try:
        ssot_lo, ssot_hi = _read_word_policy_ssot(project_root)
    except Exception:
        return 0
    whitelist = set(load_word_policy_subranges(project_root)) | {(ssot_lo, ssot_hi)}
    consecutive = 0
    for ch in range(current_chapter, max(0, current_chapter - lookback), -1):
        fp = notes_dir / f"ch{ch:04d}_prep.md"
        if not fp.exists():
            break
        try:
            t = fp.read_text(encoding="utf-8")
        except Exception:
            break
        hit = False
        for m in WORD_COUNT_RANGE_RE.finditer(t):
            lo, hi = int(m.group("lo")), int(m.group("hi"))
            ctx_start = max(0, m.start() - 30)
            ctx_end = min(len(t), m.end() + 10)
            ctx = t[ctx_start:ctx_end]
            if not any(k in ctx for k in ("字数", "word_count", "字符")):
                continue
            neg_start = max(0, m.start() - 200)
            neg_end = min(len(t), m.end() + 200)
            neg_ctx = t[neg_start:neg_end]
            if any(k in neg_ctx for k in (
                "forbidden", "禁止", "不得", "不能", "negative", "反例", "禁区",
                "白名单外", "非 SSOT", "派生白名单", "alternative",
            )):
                continue
            if (lo, hi) in whitelist:
                continue
            hit = True
            break
        if hit:
            consecutive += 1
        else:
            break
    return consecutive


def _read_word_policy_ssot(project_root: Path) -> tuple[int, int]:
    state_file = project_root / ".webnovel" / "state.json"
    if not state_file.exists():
        return (2200, 3800)
    s = json.loads(state_file.read_text(encoding="utf-8"))
    pol = s.get("project_info", {}).get("word_count_policy", {})
    return int(pol.get("hard_min", 2200)), int(pol.get("hard_max", 3800))


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

    # Round 18.2 · 连续 ≥3 章 EDITOR_NOTES_WORD_DRIFT 升级为 ERROR（阻断起草）
    drift_streak = _count_recent_word_drift_chapters(project_root, chapter, lookback=3)
    if drift_streak >= 3:
        errors.append(
            f"[EDITOR_NOTES_WORD_DRIFT_STREAK] 近 {drift_streak} 章 editor_notes 连续含伪窄/外溢区间 · "
            f"audit-agent SSOT self-check 未根治 · 必须先修 audit-agent 输出再继续"
        )

    fp = find_chapter_file(project_root, chapter)
    if not fp:
        errors.append(f"[ERROR] 章节文件缺失: 正文/第{chapter:04d}章*.md")
        return errors, warnings

    text = fp.read_text(encoding="utf-8")

    if not text.strip():
        errors.append("[ERROR] 章节文件为空")
        return errors, warnings

    # 0. 首句汉语自然度（2026-04-16 新增 · Ch1 v1 "<protagonist>在死"语病根治）
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
    # Round 17.5 · 2026-04-24 · Ch9 RCA P1-1 根治：读 context_contract.structural_exemptions
    dr_min = cfg.get("dialogue_ratio_min", 0.20)
    dr_override_chapters = set(cfg.get("dialogue_ratio_override_chapters", []))

    # Round 17.5 · 读取 context_contract.structural_exemptions.dialogue_ratio_override
    # 情感章/视觉章/纯动作章可声明 override 区间（如 "0.20-0.28"），但底线仍为绝对 0.20
    contract_path = (
        project_root / ".webnovel" / "context" / f"ch{chapter:04d}_context.json"
    )
    if contract_path.exists():
        try:
            ctx_data = json.loads(contract_path.read_text(encoding="utf-8"))
            structural_ex = (
                ctx_data.get("context_contract", {})
                .get("structural_exemptions", {})
            )
            override_str = structural_ex.get("dialogue_ratio_override")
            # override 格式如 "0.20-0.28" 或 {"min": 0.20, "max": 0.28}
            # Round 28.31 (Ch43 v2 deep research): 旧逻辑 dr_min=max(0.20, override_min)
            # 让 0.18 exemption 永远等于 0.20，context.exemption 设计完全废 → writer 仍被反复
            # 加对话耗时（Ch43 实测加了 5 轮 polish 才到 0.198）。
            # 修复：允许 override 真正生效（绝对底线放宽到 0.15），但 0.15-0.20 段需 prep 笔记
            # 声明 reason；hygiene H21 streak 仍以 0.20 计避免长期低对话章累积。
            if isinstance(override_str, str):
                m = re.match(r"\s*(\d*\.?\d+)\s*-\s*(\d*\.?\d+)\s*", override_str)
                if m:
                    override_min = float(m.group(1))
                    if 0.15 <= override_min <= 0.30:
                        dr_min = override_min  # 真正生效
            elif isinstance(override_str, dict) and "min" in override_str:
                override_min = float(override_str["min"])
                if 0.15 <= override_min <= 0.30:
                    dr_min = override_min
        except Exception:
            pass

    if chapter not in dr_override_chapters:
        dialogue_parts = re.findall(r"[“]([^”]*)[”]", text)
        total_cc = len(re.findall(r"[一-鿿]", text))
        dialogue_cc = sum(
            len(re.findall(r"[一-鿿]", d)) for d in dialogue_parts
        )
        if total_cc > 0:
            ratio = dialogue_cc / total_cc
            # Round 17.5 · Ch9 RCA P1-3 根治：actionable diff
            target_dialogue_cc = int(total_cc * dr_min)
            short_by = target_dialogue_cc - dialogue_cc
            if ratio < dr_min - 0.005:  # 2.5% 浮点容差
                errors.append(
                    f"[DIALOGUE_RATIO] 对话占比 {ratio:.3f} < {dr_min:.2f}"
                    f"（约束 VII · 连 3 章 < 0.2 触发 H21 fail · "
                    f"差额：缺 ~{short_by} 字对话 或 减 ~{int(short_by/dr_min)} 字叙述）"
                )
            elif ratio < dr_min:
                warnings.append(
                    f"[DIALOGUE_RATIO_BORDER] 对话占比 {ratio:.3f}"
                    f"（贴近下限 {dr_min:.2f}，建议 Step 4 扩 ~{short_by+5} 字对话）"
                )

    # 11. Round 17.2 · 签名句式密度扫描（2026-04-24 · Ch8 RCA P0-R5 根治）
    # 引入背景：Ch8 polish 后"没X" 34 次（editor_notes ≤15·hygiene H21 ≥30 fail），
    # polish-guide 只管 anti-AI 禁语，不管密度签名；Step 4 漏抓导致上线后用户手动 12 处改写。
    # 根治：post_draft_check 直接 block 明显过密的签名模式。
    #
    # 配置：`.webnovel/signature_density_config.json`（项目级 · 可覆盖默认阈值）
    # 默认 block 阈值：
    #   没X ≥ 20  · 未X ≥ 3  · 扶眼镜 ≥ 6  · 笑了一下 ≥ 8  · 停了半秒 ≥ 8
    signature_patterns_default = {
        "没X": {"pattern": r"没[一-鿿]", "warn": 15, "block": 20},
        "未X": {"pattern": r"未[一-鿿]", "warn": 3, "block": 5},
        "扶眼镜": {"pattern": r"扶眼镜", "warn": 4, "block": 6},
        "笑了一下": {"pattern": r"笑了一下", "warn": 5, "block": 8},
        "停了半秒": {"pattern": r"停了半秒", "warn": 5, "block": 8},
        # Round 18.2 · 2026-04-25 · Ch11 RCA #2 根治
        # Ch10 polish 把"没X"压下来后，Ch11 起草时签名迁移到"那一X"18 次（reader-naturalness +
        # prose-quality 双独立 grep 证实）。post_draft 没有相应扫描，导致 Step 3 才被发现。
        # Round 28 · Ch24 RCA 收紧：block 18→12（Ch24 实测 14 次仍只 warn 不 block，
        # 导致整章 polish 回避了这个签名，commit 后 deep research 才暴露）。
        "那一X": {"pattern": r"那一[一-鿿]", "warn": 10, "block": 12},
        # 同期发现：精确秒级时间词外溢（叙事声音约束 ≤3）。Ch11 polish 前 5 次。
        "半秒|一秒|三秒": {"pattern": r"(?:半秒|一秒|三秒)", "warn": 3, "block": 6},
        # Round 28.6 · Ch28 RCA · B7 根治：reader-naturalness 持续标"了一下" 5+/千字 (N2 红线)
        # 但 post_draft 一直未拦，polish 容易漏。Ch28 实测 20 次/3689 字 = 5.4/千字 触发 N2。
        # 与"了一X"近似 r"了一[一-鿿]"（覆盖了一下/了一会/了一眼/了一拍 等）。
        # 阈值参考 06-叙事声音约束.md ≤3 次/千字 → 警 12 / block 18（按 3500 字典型推进章计）。
        "了一X": {"pattern": r"了一[一-鿿]", "warn": 12, "block": 18},
        # Round 28.6 · 同源 N4 红线："不是X是Y" 排比，reader-naturalness 持续标外溢
        # 单章 ≤1 次（执行包硬规则）但 polish 经常 5+ 次。block 4 拦最严重案例。
        "不是X是Y": {"pattern": r"不是[^，。；！？\n]{1,15}是[^，。；！？\n]{1,15}", "warn": 2, "block": 4},
        # Round 28.32 · Ch43 v2 deep research RCA：post_draft 完全漏检 "嗯" 应答词和 "他不X"
        # 否定式两个 prep 笔记 W3 明文限的签名，导致 v2 commit 后 reader-naturalness 复测仍报
        # "嗯 18次/章 ≥12 prep 限超载"、"他不X 7次/章 ≥5 prep 限超载"。
        # 单独配置 prep 笔记常用阈值 + 千字归一化（按 3500 字典型推进章计）。
        # 段落首"他"开头连续（叙事声音约束 0 容忍）。Ch11 polish 前 2 处。
        # 这里用近似：单文档"他+空白"模式过密时 warn（精确版要分段处理，留 prose-quality 兜底）
        "嗯应答": {"pattern": r"[“]嗯[。.！？]", "warn": 12, "block": 16},
        "他不X": {"pattern": r"他不[一-鿿]", "warn": 5, "block": 8},
        # Round 28.35 · Ch44 v3 deep research RCA：half-X 高密度
        # 根因：reader-naturalness AV-091 标"半 X"成新代偿签名 · Ch44 实测 13 次（半截/半张/
        #       半指/半道/半碗/半口/半档/半拍/半步/半截 ...）
        # 阈值 warn 15 / block 22（Ch44 13 留 margin · 排除"半夜/半小时/半个"等正常用语
        # 用 [一-鿿] 但实际 grep 也会抓"半夜半小时"，建议 Step 4 polish-guide 处理"半 X" 误伤）
        "半X": {"pattern": r"半[一-鿿]", "warn": 15, "block": 22},
    }
    # 项目级 override
    sig_cfg_path = project_root / ".webnovel" / "signature_density_config.json"
    if sig_cfg_path.exists():
        try:
            sig_cfg = json.loads(sig_cfg_path.read_text(encoding="utf-8"))
            for k, v in (sig_cfg or {}).items():
                if k in signature_patterns_default and isinstance(v, dict):
                    signature_patterns_default[k].update(
                        {kk: vv for kk, vv in v.items() if kk in ("warn", "block")}
                    )
        except Exception:
            pass
    # Round 29 Phase 6.1 · 签名族闸门默认 warn-only（家族级开关）
    # 实证副作用：没X→未X 替换污染三复发（Ch16/Ch23）/ 过+量词替代效应（R28.33）——
    # block 驱动的是"换一个更不自然的词"而非"写得更好"（详见 docs/RCA-CHANGELOG.md R29）。
    # 自然度真源 = reader-naturalness checker。覆盖：SIGNATURE_DENSITY / SIGNATURE_AGGREGATE /
    # DASH_DENSITY / H78。项目恢复硬闸：signature_density_config.json 设 {"_enforcement": "block"}。
    sig_enforcement = "warn"
    if sig_cfg_path.exists():
        try:
            _enf = json.loads(sig_cfg_path.read_text(encoding="utf-8")).get("_enforcement")
            if _enf in ("warn", "block"):
                sig_enforcement = _enf
        except Exception:
            pass
    sig_breach_sink = errors if sig_enforcement == "block" else warnings
    sig_breach_note = (
        ""
        if sig_enforcement == "block"
        else ' · R29 默认警示不阻断（恢复硬闸：signature_density_config.json 设 "_enforcement": "block"）'
    )
    # Round 28.22 Ch37 RCA · 累积 signature_summary（即使未触发也显示）
    # 防御场景：polish 第一次只 fix 触发的（没X），不知道临界的（未X 4/5 warn 1/3 block）
    # 替换"没X→未X"后反向触发 未X 17/3 block，造成第二轮 polish。
    # 现：每次 post_draft_check 输出"全部 6 类签名当前计数"INFO（不阻断），让 AI 看见所有临界点。
    signature_summary_lines = []
    for sig_name, sig_cfg in signature_patterns_default.items():
        count = len(re.findall(sig_cfg["pattern"], text))
        margin = sig_cfg["warn"] - count
        status = "OK" if margin > 2 else ("NEAR" if margin > 0 else "BREACH")
        signature_summary_lines.append(
            f"  · {sig_name}: {count} 次 (warn {sig_cfg['warn']} / block {sig_cfg['block']}) [{status}]"
        )
        if count >= sig_cfg["block"]:
            sig_breach_sink.append(
                f"[SIGNATURE_DENSITY] 签名句式'{sig_name}' {count} 次 ≥ block {sig_cfg['block']} · "
                f"AI 签名外溢（Round 17.2 Ch8 P0-R5）· "
                f"polish 优先重写句式而非同义替换{sig_breach_note}"
            )
        elif count >= sig_cfg["warn"]:
            warnings.append(
                f"[SIGNATURE_DENSITY_WARN] 签名句式'{sig_name}' {count} 次 ≥ warn {sig_cfg['warn']} · "
                f"建议 polish 降到 < {sig_cfg['warn']}"
            )
    # INFO 行：全部签名计数（永远显示，让 AI 看见所有临界）· Round 28.22 Ch37 RCA
    # 用 warnings 的 [INFO] 前缀，被 strict_warnings filter 过滤掉，不计入 exit_code
    warnings.append("[INFO] [SIGNATURE_SUMMARY] 全部签名密度（让 polish 看见所有临界）:")
    for line in signature_summary_lines:
        warnings.append(f"[INFO] {line}")

    # 11b. Round 27.1 · 否定签名累计上限（2026-05-02 · Ch23 RCA R4 根治）
    # 引入背景：Ch16/17/23 三次复发"没X→未X"替换循环：
    #   - 用户 polish 把"没X"压下来 → 替换池退到"未X" → 触发 未X block
    #   - 再压"未X" → 替换池退到"不曾" → 累计仍超
    # 单类阈值各自独立判断，无法防御"分散到多个否定式各自不超阈，但累计仍是 AI signature"的
    # 跨类外溢。根治：no_xx_aggregate ≤ 25 / 千字 (warn 20 / 千字)，捕获 polish 替换循环。
    # 配置：`.webnovel/signature_density_config.json` 可在 "_aggregate" 键覆盖默认阈值。
    aggr_patterns = [r"没[一-鿿]", r"未[一-鿿]", r"不曾[一-鿿]?", r"无[回信法]"]
    aggr_count = sum(len(re.findall(p, text)) for p in aggr_patterns)
    chinese_count = max(1, len(re.findall(r"[一-鿿]", text)))
    aggr_per_kchar = aggr_count / (chinese_count / 1000.0)
    aggr_cfg = {"warn": 20.0, "block": 25.0}
    if sig_cfg_path.exists():
        try:
            sig_cfg_all = json.loads(sig_cfg_path.read_text(encoding="utf-8"))
            if isinstance(sig_cfg_all.get("_aggregate"), dict):
                aggr_cfg.update(
                    {kk: vv for kk, vv in sig_cfg_all["_aggregate"].items() if kk in ("warn", "block")}
                )
        except Exception:
            pass
    if aggr_per_kchar >= aggr_cfg["block"]:
        sig_breach_sink.append(
            f"[SIGNATURE_AGGREGATE] 否定签名累计 {aggr_count} 次 ({aggr_per_kchar:.1f}/千字) "
            f">= block {aggr_cfg['block']}/千字 · 没/未/不曾/无回信 累计外溢 (Round 27.1 · Ch23 RCA R4) · "
            f"polish 不得只在 没X/未X/不曾 之间互换，必须用 不/重写句式{sig_breach_note}"
        )
    elif aggr_per_kchar >= aggr_cfg["warn"]:
        warnings.append(
            f"[SIGNATURE_AGGREGATE_WARN] 否定签名累计 {aggr_count} 次 ({aggr_per_kchar:.1f}/千字) "
            f">= warn {aggr_cfg['warn']}/千字 · 建议改用动作/感官实写避免单调否定"
        )

    # 10. Round 17.1 · 元标识符扫描（2026-04-24 · Ch7 RCA F6 根治）
    # 引入背景：Ch7 首稿 L183 "一次是 Ch1 那个清晨，一次是 Ch4 <power-faction>系统的第一次登录"
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

    # 13. Round 18.3 · AI 套话副词密度扫描（2026-04-25 · Ch12 RCA P0 根治）
    # 引入背景：跨 Ch1-12 数据：Ch5 "轻轻" 7 次（章 3406 字 → 2.06/千字），Ch9 "轻轻" 5 次，
    # Ch10 "轻轻" 1 次，Ch12 polish 引入"轻轻"+"仿佛" 各 1 次。累计 12 章 ≥36 处 AI 套话副词。
    # 根因：context-agent 的 forbidden_items 列入 ai_cliche（轻轻/仿佛/微微等 10 词）作为 writer
    # 起草软提示，但 polish 阶段没有"复扫禁词"机制，反向引入；post_draft_check 不扫这些词。
    # 影响：网文读者高度敏感这类 AI 副词（tavily search 2026-04-25 · "弃文风险"），累积削弱质感。
    # 根治：post_draft_check 强制扫描 10 类 AI cliche 副词，warn ≥3 / block ≥6（按千字计算更合理：
    # warn 1.0/千字，block 2.0/千字，单词上限按章字数动态算）。
    # 项目级 override：`.webnovel/ai_cliche_config.json`
    ai_cliche_default = {
        "微微": {"per_kchar_warn": 0.8, "per_kchar_block": 1.5, "abs_min_warn": 2, "abs_min_block": 4},
        "缓缓": {"per_kchar_warn": 0.6, "per_kchar_block": 1.2, "abs_min_warn": 2, "abs_min_block": 3},
        "淡淡": {"per_kchar_warn": 0.6, "per_kchar_block": 1.2, "abs_min_warn": 2, "abs_min_block": 3},
        "轻轻": {"per_kchar_warn": 0.8, "per_kchar_block": 1.5, "abs_min_warn": 3, "abs_min_block": 5},
        "仿佛": {"per_kchar_warn": 0.5, "per_kchar_block": 1.0, "abs_min_warn": 2, "abs_min_block": 3},
        "终究": {"per_kchar_warn": 0.5, "per_kchar_block": 1.0, "abs_min_warn": 2, "abs_min_block": 3},
        "本能地": {"per_kchar_warn": 0.3, "per_kchar_block": 0.6, "abs_min_warn": 1, "abs_min_block": 2},
        "猛地": {"per_kchar_warn": 0.5, "per_kchar_block": 1.0, "abs_min_warn": 2, "abs_min_block": 3},
        "陡然": {"per_kchar_warn": 0.3, "per_kchar_block": 0.6, "abs_min_warn": 1, "abs_min_block": 2},
        "缓缓地": {"per_kchar_warn": 0.3, "per_kchar_block": 0.6, "abs_min_warn": 1, "abs_min_block": 2},
    }
    ai_cliche_cfg_path = project_root / ".webnovel" / "ai_cliche_config.json"
    if ai_cliche_cfg_path.exists():
        try:
            cfg = json.loads(ai_cliche_cfg_path.read_text(encoding="utf-8"))
            for k, v in (cfg or {}).items():
                if k in ai_cliche_default and isinstance(v, dict):
                    ai_cliche_default[k].update(v)
        except Exception:
            pass
    chinese_chars = len(re.findall(r"[一-鿿]", text))
    kchar = max(1, chinese_chars / 1000.0)
    ai_cliche_total = 0
    ai_cliche_hits_summary = {}
    for word, cfg in ai_cliche_default.items():
        count = text.count(word)
        if count == 0:
            continue
        ai_cliche_total += count
        ai_cliche_hits_summary[word] = count
        per_k = count / kchar
        # 单词级扫描
        if count >= cfg["abs_min_block"] or per_k >= cfg["per_kchar_block"]:
            errors.append(
                f"[AI_CLICHE] '{word}' {count} 次（{per_k:.2f}/千字）"
                f" ≥ block 阈值 · 必须 polish 删/换具象动词"
            )
        elif count >= cfg["abs_min_warn"] or per_k >= cfg["per_kchar_warn"]:
            warnings.append(
                f"[AI_CLICHE_WARN] '{word}' {count} 次（{per_k:.2f}/千字）"
                f" ≥ warn 阈值 · 建议 polish 删/换具象动词"
            )
    # 总量级扫描（避免 10 词每词都低于阈值但累积爆表）
    total_per_k = ai_cliche_total / kchar
    if total_per_k >= 3.0:
        errors.append(
            f"[AI_CLICHE_TOTAL] 10 类 AI 套话副词累计 {ai_cliche_total} 次"
            f"（{total_per_k:.2f}/千字）≥ block 3.0/千字 · "
            f"明显 AI 文风（命中：{ai_cliche_hits_summary}）· 必须 polish 大幅删除"
        )
    elif total_per_k >= 1.8:
        warnings.append(
            f"[AI_CLICHE_TOTAL_WARN] 10 类 AI 套话副词累计 {ai_cliche_total} 次"
            f"（{total_per_k:.2f}/千字）≥ warn 1.8/千字 · "
            f"建议 polish 替换具象动词（命中：{ai_cliche_hits_summary}）"
        )

    # 14. Round 18.3 · 破折号密度扫描（2026-04-25 · Ch10 RCA 47 个破折号 P0 根治）
    # 引入背景：06-叙事声音约束.md 写"破折号 ≤3/单章"，但跨 Ch1-12 实测：
    # Ch1 21 / Ch2 29 / Ch5 31 / Ch10 47 / Ch12 6 — 平均 ~21，远超约束 ≤3。
    # Ch10 47 个 = 13.4/千字，节奏严重失控但 prose-quality 给 91 高分（因为视觉锚等加分项盖过节奏扣分）。
    # 根因：约束在文档层面但缺乏工具检测；只有人工注意能控（Ch11 4 个证明能控）。
    # 影响：破折号过密 = 节奏断裂 = 读者阅读疲劳（中文小说破折号比英文敏感）。
    # 根治：post_draft_check 强制硬扫，warn ≥6 / block ≥10（比 06 约束更宽松，因为 ≤3 太严苛但 ≥10 必爆）。
    # 项目级 override：`.webnovel/dash_density_config.json`
    dash_count = text.count("——")
    dash_per_k = dash_count / kchar
    dash_warn_abs = 6
    dash_block_abs = 10
    dash_per_k_warn = 2.5
    dash_per_k_block = 4.0
    dash_cfg_path = project_root / ".webnovel" / "dash_density_config.json"
    if dash_cfg_path.exists():
        try:
            dcfg = json.loads(dash_cfg_path.read_text(encoding="utf-8"))
            dash_warn_abs = dcfg.get("warn_abs", dash_warn_abs)
            dash_block_abs = dcfg.get("block_abs", dash_block_abs)
            dash_per_k_warn = dcfg.get("per_kchar_warn", dash_per_k_warn)
            dash_per_k_block = dcfg.get("per_kchar_block", dash_per_k_block)
        except Exception:
            pass
    if dash_count >= dash_block_abs or dash_per_k >= dash_per_k_block:
        sig_breach_sink.append(
            f"[DASH_DENSITY] 破折号 '——' {dash_count} 次（{dash_per_k:.2f}/千字）"
            f" ≥ block 阈值 · 节奏断裂信号 · polish 建议改为句号/逗号/省略号{sig_breach_note}"
        )
    elif dash_count >= dash_warn_abs or dash_per_k >= dash_per_k_warn:
        warnings.append(
            f"[DASH_DENSITY_WARN] 破折号 '——' {dash_count} 次（{dash_per_k:.2f}/千字）"
            f" ≥ warn 阈值 · 06-叙事声音约束 ≤3/单章 · 建议 polish 收敛"
        )

    # 15. Round 28.30 · AI 排比/诗化金句检测（2026-05-15 · Ch43 RCA · reader-critic 79 三连金句 critical）
    # 引入背景：Ch43 起草触发 reader-critic / ooc / dialogue / flow / density / prose 6 checker 共识 critical/high：
    # L207 "一棵一棵种。一户一户教。一年一年做。" 四联排比 + L221 "到头来不是我自己的脚" 诗化隐喻金句
    # = "作者代言外露" + "口号化" + "网络爽文金句模板"。reader-critic 79 / flow 72 / dialogue 70。
    # 根因：context-agent prep 笔记说"宣告朴素落字一次"，但起草无硬约束；post_draft 只看签名密度不看排比/金句结构。
    # 根治：扫描两类模板：
    #   (a) ABAB 四连排比 "一X一X、一X一X、一X一X" 或 "X一X、X一X、X一X" 或 "X的Y、X的Y、X的Y" 等
    #   (b) 诗化金句模式 "X，是Y" / "不是X，是Y" / "X不是Y、是Z" 单章 ≥ 3 处
    # 项目级 override：`.webnovel/ai_slogan_config.json`
    slogan_warn = 1  # warn 阈值：排比组数
    slogan_block = 2  # block 阈值：排比组数
    slogan_cfg_path = project_root / ".webnovel" / "ai_slogan_config.json"
    if slogan_cfg_path.exists():
        try:
            scfg = json.loads(slogan_cfg_path.read_text(encoding="utf-8"))
            slogan_warn = scfg.get("warn_abs", slogan_warn)
            slogan_block = scfg.get("block_abs", slogan_block)
        except Exception:
            pass
    # 排比检测：单句内重复"一X一X、一X一X、一X一X" 三连及以上（用 \1 反向引用）
    # 例：一棵一棵种。一户一户教。一年一年做。 / 一字一字地说。一笔一笔地写。一句一句地交代。
    triple_parallel_pattern = re.compile(
        r"一([一-鿿])一\1[^。]{0,4}[。，；]\s*一[一-鿿]一[一-鿿][^。]{0,4}[。，；]\s*一[一-鿿]一[一-鿿]"
    )
    slogan_hits_a = triple_parallel_pattern.findall(text)
    # 诗化金句 (b): "不是X，到头来不是Y" / "到头来不是X" / "走快了，路就不是X" 等强对偶金句
    # 模式：以"不是X是Y"、"不是X，是Y"、"到头来不是"、"X到头来Y" 单章累计
    slogan_pattern_b = re.compile(r"(?:不是.{1,8}[是就]|到头来不是|说到底.{0,3}不是|本质.{0,3}不是)")
    slogan_hits_b = slogan_pattern_b.findall(text)
    slogan_total = len(slogan_hits_a) + max(0, len(slogan_hits_b) - 2)  # 诗化金句 ≤2 容忍
    if slogan_total >= slogan_block:
        errors.append(
            f"[AI_SLOGAN] AI 排比/诗化金句模板 {slogan_total} 处（排比 {len(slogan_hits_a)} 组 / "
            f"诗化对偶 {len(slogan_hits_b)} 处）≥ block 阈值 · "
            f"reader-critic 易判'口号化/作者代言外露' · 必须 polish 拆解或白话化"
        )
    elif slogan_total >= slogan_warn:
        warnings.append(
            f"[AI_SLOGAN_WARN] AI 排比/诗化金句 {slogan_total} 处（排比 {len(slogan_hits_a)} / "
            f"诗化 {len(slogan_hits_b)}）≥ warn 阈值 · 建议 polish 拆短或减一组"
        )

    # 12. Round 17.5 · 中文章数元叙事扫描（2026-04-24 · Ch9 RCA P0-3 根治）
    # 引入背景：Ch9 L233 主角心里"二十章之前，不问这种事"——
    # 主角不应该用"章"做时间单位（这是元叙事破壁）。
    # reader-critic critical + ooc low + flow high 三层 checker 同时发现。
    # 现有 Ch[0-9]+/第N章 regex 漏掉中文数词章号。
    # 根治：扫描"X 章之前/之后/内/前/后" 模式（X = 中文数词或阿拉伯数字）。
    # Round 28.28 · Ch42 RCA · 多位中文数词补丁（2026-05-15）
    # 引入背景：Ch42 L9 "<antagonist>二十二章前在日料店包厢" 漏过原 pattern。
    # 根因：原 pattern 用枚举 alternatives (二十/三十/四十/五十)，
    #       无法匹配"二十二/三十二/四十五"等多位中文数词；
    #       \d+ 只匹配阿拉伯数字。
    # 5 个 checker 同时命中本应在 post_draft_check 拦截的 H40 P0 critical。
    # 根治：用字符类 [零一二两三四五六七八九十百千]+ 直接吃整段中文数词。
    cn_chapter_meta_pattern = (
        r"(几|[零一二两三四五六七八九十百千]+|"
        r"\d+)\s*章\s*(之前|之后|内|后|前|以前|以后)"
    )
    cn_chapter_hits = re.findall(cn_chapter_meta_pattern, text)
    if cn_chapter_hits:
        errors.append(
            f"[METAREF_CN_CHAPTER] 正文含 {len(cn_chapter_hits)} 处中文章数元叙事（样本：{cn_chapter_hits[:3]}）· "
            f"小说人物不能用「章」做时间单位 · 改为「等几天/几个月/到时候」等自然时间表述"
        )

    # H78. Round 28.35 · 跨章首段 N-gram 比对（2026-05-16 · Ch44 v3 deep research RCA · P0 根治）
    # 引入背景：Ch43→Ch44 首段 4 处意象 1:1 复用（东墙根青砖/膝盖印/送水车压低引擎/引擎声拖出去半截）
    # 13 个内部 checker + 15 个外部模型全部漏检（单章独立视角盲区）· 只有读者会感到"昨天已读过"
    # 根因：所有 checker 都看本章 in-text，无跨章 N-gram 比对工具
    # 根治：扫上一章文本，取章末最后 600 字 + 当章前 600 字，对比 6-gram 重合度
    #       命中 ≥ 3 个 6-gram 重合即 warn，≥ 6 个 block
    # 配置：`.webnovel/cross_chapter_ngram_config.json`（可调阈值或禁用）
    cross_cfg = {
        "enabled": True,
        "ngram_size": 6,
        "lookback_chars": 600,
        "warn_threshold": 3,
        "block_threshold": 6,
        # 跳过过于通用的 6-gram（如"末世第N天"时间锚 / "蓝铁门那头" 等场景常量）
        "exclude_patterns": [r"\d+章$", r"末世第", r"失情绪第"],
    }
    cross_cfg_path = project_root / ".webnovel" / "cross_chapter_ngram_config.json"
    if cross_cfg_path.exists():
        try:
            cross_cfg.update(json.loads(cross_cfg_path.read_text(encoding="utf-8")))
        except Exception:
            pass

    if cross_cfg.get("enabled", True) and chapter >= 2:
        try:
            # 找上一章正文
            prev_padded = f"{chapter - 1:04d}"
            prev_files = list((project_root / "正文").glob(f"第{prev_padded}章*.md"))
            if prev_files:
                prev_text = prev_files[0].read_text(encoding="utf-8")
                # 清洗：去除 frontmatter / 标题
                prev_text_clean = re.sub(r"^---.*?^---", "", prev_text, flags=re.DOTALL | re.MULTILINE).strip()
                prev_text_clean = re.sub(r"^#.*$", "", prev_text_clean, flags=re.MULTILINE).strip()
                cur_text_clean = re.sub(r"^---.*?^---", "", text, flags=re.DOTALL | re.MULTILINE).strip()
                cur_text_clean = re.sub(r"^#.*$", "", cur_text_clean, flags=re.MULTILINE).strip()

                # 取上一章末尾 + 当章开头
                prev_tail = prev_text_clean[-cross_cfg["lookback_chars"]:]
                cur_head = cur_text_clean[:cross_cfg["lookback_chars"]]

                # 提取 N-gram (仅中文字符)
                ngram_size = cross_cfg["ngram_size"]
                def _extract_ngrams(s, n):
                    # 只取连续 N 个中文字符
                    cleaned = re.sub(r"[^一-鿿]", "", s)
                    return set(cleaned[i:i + n] for i in range(len(cleaned) - n + 1))

                prev_ngrams = _extract_ngrams(prev_tail, ngram_size)
                cur_ngrams = _extract_ngrams(cur_head, ngram_size)
                overlap = prev_ngrams & cur_ngrams

                # 排除通用 patterns
                exclude_pats = [re.compile(p) for p in cross_cfg.get("exclude_patterns", [])]
                overlap_filtered = [
                    g for g in overlap if not any(p.search(g) for p in exclude_pats)
                ]
                overlap_count = len(overlap_filtered)

                if overlap_count >= cross_cfg["block_threshold"]:
                    sig_breach_sink.append(
                        f"[H78_CROSS_CHAPTER_REUSE] 与上一章首尾 {ngram_size}-gram 重合 {overlap_count} 处 ≥ block {cross_cfg['block_threshold']} · "
                        f"跨章意象 1:1 复用（样本：{overlap_filtered[:5]}）· "
                        f"读者会感到 deja vu · 强烈建议改写开篇或末段{sig_breach_note}"
                    )
                elif overlap_count >= cross_cfg["warn_threshold"]:
                    warnings.append(
                        f"[H78_CROSS_CHAPTER_REUSE_WARN] 与上一章首尾 {ngram_size}-gram 重合 {overlap_count} 处 "
                        f"（样本：{overlap_filtered[:5]}）· 建议替换 1-2 处具体意象避免单调"
                    )
        except Exception as e:
            warnings.append(f"[H78_SKIP] 跨章 N-gram 检查失败（不阻断）：{e}")

    # H79. Round 28.35 · 正文 ASCII 英文动词残留扫描（2026-05-16 · Ch44 v3 RCA · P0 根治）
    # 引入背景：Ch44 v1 含 "release 不开"（AI draft 残留），naturalness checker P0 high
    # 但 13 checker 漏检（prose_quality 也漏）· 只有 5 个外部模型 critical
    # 根因：post_draft_check 无 ASCII 英文动词扫描（ASCII 引号 H1 已查 · 英文 token 未查）
    # 根治：扫常见 AI 残留英文动词，warn ≥1 / block ≥3（容忍极少英文档案引用，不可滥用）
    # 配置：`.webnovel/ascii_verb_config.json`
    ascii_verbs = ["release", "active", "passive", "trigger", "deactive", "enable", "disable",
                   "buff", "debuff", "cooldown", "execute", "abort", "resume", "suspend"]
    ascii_verb_cfg_path = project_root / ".webnovel" / "ascii_verb_config.json"
    if ascii_verb_cfg_path.exists():
        try:
            cfg = json.loads(ascii_verb_cfg_path.read_text(encoding="utf-8"))
            ascii_verbs = cfg.get("verbs", ascii_verbs)
        except Exception:
            pass
    # 用 word boundary 扫描，避免 "released"/"trigger_" 等被误匹配的同时排除人名/ID 单词上下文
    ascii_verb_hits = {}
    for verb in ascii_verbs:
        # 严格 word boundary：前后必须是非字母数字（含中文）
        pattern = r"(?<![A-Za-z0-9_])" + re.escape(verb) + r"(?![A-Za-z0-9_])"
        count = len(re.findall(pattern, text, re.IGNORECASE))
        if count:
            ascii_verb_hits[verb] = count
    total_ascii_verbs = sum(ascii_verb_hits.values())
    if total_ascii_verbs >= 3:
        errors.append(
            f"[H79_ASCII_VERB] 正文含 {total_ascii_verbs} 处 ASCII 英文动词（{ascii_verb_hits}）· "
            f"AI draft 残留 · 必须改写为中文表达（如 release→松开/释放/打开）"
        )
    elif total_ascii_verbs >= 1:
        warnings.append(
            f"[H79_ASCII_VERB_WARN] 正文含 {total_ascii_verbs} 处 ASCII 英文动词（{ascii_verb_hits}）· "
            f"建议改为中文表达"
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
    ap.add_argument(
        "--editor-notes-only",
        action="store_true",
        help="Round 17.2 · Ch8 P0-R4 根治：只跑 editor_notes 字数漂移扫描（audit-agent 写完 editor_notes 后 self-check 用）",
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

    # Round 17.2 · Ch8 P0-R4 根治：editor-notes-only 模式（audit-agent self-check）
    if args.editor_notes_only:
        print("=" * 60)
        print(f" editor_notes 字数漂移扫描 · Ch{args.chapter}")
        print(f" 项目：{project_root.name}")
        print("=" * 60)
        state_path = project_root / ".webnovel" / "state.json"
        try:
            policy = (
                json.loads(state_path.read_text(encoding="utf-8"))
                .get("project_info", {})
                .get("word_count_policy", {})
            )
            ssot_lo = int(policy.get("hard_min", 2200))
            ssot_hi = int(policy.get("hard_max", 3800))
        except Exception:
            ssot_lo, ssot_hi = 2200, 3800
        drifts = check_editor_notes_word_drift(project_root, args.chapter, ssot_lo, ssot_hi)
        if drifts:
            print(f"\n ❌ 发现 {len(drifts)} 项字数漂移：")
            for d in drifts:
                print(f"  ⚠️  {d}")
            print(
                "\n  修复方式：把 editor_notes 里伪窄区间替换为合法子区间（Round 21.1）：\n"
                "    过渡/铺垫：2200-2900  推进/日常：2700-3300\n"
                "    情感/揭秘：2900-3500  战斗/高潮：3200-3800\n"
                "    hard 兜底：2200-3800"
            )
            return 1
        print("\n ✅ editor_notes 无字数漂移")
        return 0

    print("=" * 60)
    print(f" 起草后硬闸门 · post_draft_check · Ch{args.chapter}")
    print(f" 项目：{project_root.name}")
    print("=" * 60)

    # Round 15.3 · 2026-04-23 · Ch6 RCA Bug #3 根治：
    # Claude Code Write/Edit 工具把 U+201C/201D 转 ASCII，导致每章起草后都有 ASCII 引号。
    # 这里在第一次 check 前自动跑 quote_pair_fix.py --ascii-to-curly，自动根治。
    # 用户可用 --no-auto-fix 禁用。
    #
    # Round 18 · 2026-04-24 · Ch10 RCA P0-1 根治：
    # 旧逻辑只在 `chr(34) in text_before` 时触发（即文件里有 ASCII 引号才跑 fix）。
    # 但 Edit 工具在替换跨弯引号段时，可能把 new_string 内的 ASCII " 写成 U+201D（右），
    # 导致 "全 ASCII 已变全弯引号但段内方向错配" 的状态——那时段内 0 个 ASCII，
    # auto-fix 就不会跑，错配段一直留到下一阶段。
    # 根治：触发条件改为"任一段引号方向不平衡 OR 仍含 ASCII 双引号"。
    # quote_pair_fix.fix_paragraph_ascii_to_curly 是 idempotent 的——已正确配对的段
    # 不会被改写（out == para），所以总跑一遍是安全的。
    if not args.no_auto_fix:
        try:
            import glob as _glob

            chapter_padded = f"{args.chapter:04d}"
            candidates = _glob.glob(str(project_root / "正文" / f"第{chapter_padded}章*.md"))
            if candidates:
                chapter_file = candidates[0]
                text_before = Path(chapter_file).read_text(encoding="utf-8")
                # 判定是否需要 fix：(1) 有 ASCII 引号 OR (2) 有任一段弯引号方向不平衡
                needs_fix = chr(34) in text_before or any(
                    seg.count("“") != seg.count("”")
                    for seg in re.split(r"\n{2,}", text_before)
                )
                if needs_fix:
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
                                f"  🔧 [auto-fix] 引号配对 → 弯引号 OCOC："
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

    # Round 20.8 · 2026-04-28 · Ch15 RCA:
    # 字数命中硬区间时会记录一条 "[INFO] 字数..." 供日志留痕。它不是 warning，
    # strict 模式不应因此返回 1；否则会出现"打印全部通过但退出码失败"的幽灵阻断。
    strict_warnings = [w for w in warnings if not w.startswith("[INFO]")]
    return 0 if not (args.strict and strict_warnings) else 1


if __name__ == "__main__":
    sys.exit(main())
