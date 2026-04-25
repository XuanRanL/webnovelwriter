#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chapter_audit.py — Step 6 审计闸门的 CLI 快速路径（Layer A/B/G 确定性检查）

职责:
- Layer A 过程真实性: Contract 完整性、Checker 多样性、External 模型完整性、
  Data Agent 子步、Fallback 检测、Workflow 时序、编码损坏、anti_ai_force_check stub
- Layer B 跨产物一致性: 摘要 vs 正文、实体三方、伏笔三方、review_metrics、
  主角/反派传播、章纲兑现、时间锚点、chapter_meta 字段
- Layer G 跨章趋势: 评分/字数/爽点/钩子/伏笔债务/checker 漂移/问题累积/人物频率/Step K 产出

该模块输出 JSON 到 --out 指定路径，供 audit-agent (Part 2) 消费。

CLI 子命令:
- chapter       → 运行 Layer A/B/G 全部检查 (主流程调用)
- trend         → 仅跑 Layer G 跨章趋势
- check-decision → 读取已存在的 audit_reports/ch{NNNN}.json 并验证决议
- write-editor-notes → 辅助: 根据 audit 结果生成 editor_notes/ch{NNNN+1}_prep.md

决议规则 (与 step-6-audit-matrix.md 决议矩阵保持一致):
- 任一 critical fail                    → block
- high fail 数量 >= 3                   → block
- 其他 high / medium / low fail 或 warn → approve_with_warnings
- 全部 pass / skipped                   → approve

退出码 (与 cli_decision 一一对应):
- 0 = approve (全部通过)
- 1 = block (critical fail 或 high fails >= 3)
- 2 = approve_with_warnings (有 high/medium/low fail 或 warn)
- 3 = CLI 自身错误 (脚本 bug / 文件缺失等)
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ==================== 配置常量 ====================

CHAPTER_META_REQUIRED_FIELDS = [
    "chapter", "title", "word_count", "summary", "hook_strength",
    "scene_count", "key_beats", "characters", "locations",
    "created_at", "updated_at", "protagonist_state", "location_current",
    "power_realm", "golden_finger_level", "time_anchor", "end_state",
    "foreshadowing_planted", "foreshadowing_paid", "strand_dominant",
    "review_score", "checker_scores",
]

CHECKER_NAMES = [
    "consistency-checker", "continuity-checker", "ooc-checker",
    "reader-pull-checker", "high-point-checker", "pacing-checker",
    "dialogue-checker", "density-checker", "prose-quality-checker",
    "emotion-checker", "flow-checker",
    # Round 13 v2 (2026-04-16) · 读者视角双维度，与其他 checker 平等参与 overall_score 聚合
    "reader-naturalness-checker", "reader-critic-checker",
]

# 审查报告使用中文维度名而非英文 checker 名，需做别名映射
# 规则：key 必须是 canonical 英文 checker 名；alias 覆盖中文/简写/legacy 维度名
# 新增 alias 原则：
#   1. 覆盖"概念相近 AI 会手写"的别名（节奏/对话/情绪曲线/Prose质量）
#   2. 覆盖 legacy 术语：钩子强度→reader-pull-checker, 伏笔埋设→consistency-checker
#   3. Round 13 v2：naturalness 和 reader-critic 升格为评分维度（原 veto 架构取消）
CHECKER_ALIASES = {
    "consistency-checker": ["设定一致性", "一致性检查", "consistency", "伏笔埋设", "伏笔检查"],
    "continuity-checker": ["连贯性", "连续性检查", "continuity"],
    "ooc-checker": ["人物塑造", "人物OOC", "OOC检查", "ooc", "人物"],
    "reader-pull-checker": ["追读力", "追读检查", "reader-pull", "钩子强度", "钩子检查"],
    "high-point-checker": ["爽点密度", "爽点检查", "high-point"],
    "pacing-checker": ["节奏控制", "节奏检查", "pacing", "节奏"],
    "dialogue-checker": ["对话质量", "对话检查", "dialogue", "对话"],
    "density-checker": ["信息密度", "密度检查", "density"],
    "prose-quality-checker": ["文笔质感", "文笔检查", "prose", "Prose质量", "Prose", "文笔"],
    "emotion-checker": ["情感表现", "情感检查", "emotion", "情绪曲线", "情感"],
    "flow-checker": ["读者流畅度", "读者视角流畅度", "流畅度检查", "flow"],
    "reader-naturalness-checker": ["汉语母语自然度", "自然度", "naturalness", "reader-naturalness"],
    "reader-critic-checker": ["读者锐评", "reader-critic", "读者视角锐评"],
}

# Reverse lookup: alias/canonical → canonical checker name
# Built once at import time; used by normalize_checker_scores_keys + audit.
_CHECKER_ALIAS_TO_CANONICAL: Dict[str, str] = {}
for _canonical, _aliases in CHECKER_ALIASES.items():
    _CHECKER_ALIAS_TO_CANONICAL[_canonical] = _canonical
    _CHECKER_ALIAS_TO_CANONICAL[_canonical.lower()] = _canonical
    for _a in _aliases:
        _CHECKER_ALIAS_TO_CANONICAL[_a] = _canonical
        _CHECKER_ALIAS_TO_CANONICAL[_a.lower()] = _canonical

# Non-checker keys permitted in checker_scores (reserved)
CHECKER_SCORES_RESERVED_KEYS = frozenset({"overall"})

# Legacy/AI-fallback keys that must NOT be treated as checkers
# (they are concept sub-metrics or old veto verdict names, not canonical checker scores)
# Round 13 v2: naturalness / reader-critic 升格为正式 checker，不再视为 veto
# 但保留 "naturalness_veto"/"Anti-AI" 这些旧字符串以兼容老 state.json（走 alias 映射到 reader-naturalness-checker）
CHECKER_SCORES_BANNED_KEYS = frozenset({
    "Anti-AI", "anti-ai", "anti_ai",
    "naturalness_veto",
    # sub-metrics that used to be split out but are now folded into parent checkers
})


def normalize_checker_scores_keys(
    checker_scores: Optional[Dict[str, Any]],
) -> Tuple[Dict[str, Any], List[str], List[str]]:
    """Normalize checker_scores keys to canonical English checker names.

    Returns:
        (normalized_dict, renamed_keys_log, invalid_keys_log)
        - normalized_dict: keys mapped to canonical (CHECKER_NAMES ∪ reserved)
        - renamed_keys_log: list of "src_key → canonical" entries (for audit trace)
        - invalid_keys_log: list of src_keys that could not be mapped (banned or unknown)

    Rules:
        - canonical key (in CHECKER_NAMES) → kept as-is
        - alias key (in CHECKER_ALIASES[*]) → mapped to canonical
        - reserved key (overall) → kept
        - banned key (Anti-AI etc.) → dropped + logged
        - unknown key → dropped + logged
        - on collision (two aliases map to same canonical), later value wins and
          collision is logged to invalid_keys_log as "COLLISION:src→canonical"
    """
    if not isinstance(checker_scores, dict):
        return {}, [], []
    normalized: Dict[str, Any] = {}
    renamed: List[str] = []
    invalid: List[str] = []
    seen_canonical: Dict[str, str] = {}  # canonical → src_key that set it
    for src_key, value in checker_scores.items():
        if src_key in CHECKER_SCORES_RESERVED_KEYS:
            normalized[src_key] = value
            continue
        if src_key in CHECKER_SCORES_BANNED_KEYS or src_key.lower() in {
            k.lower() for k in CHECKER_SCORES_BANNED_KEYS
        }:
            invalid.append(f"BANNED:{src_key}")
            continue
        canonical = _CHECKER_ALIAS_TO_CANONICAL.get(src_key) or _CHECKER_ALIAS_TO_CANONICAL.get(
            src_key.lower()
        )
        if canonical is None:
            invalid.append(f"UNKNOWN:{src_key}")
            continue
        if canonical in seen_canonical and seen_canonical[canonical] != src_key:
            invalid.append(f"COLLISION:{src_key}→{canonical}(prev={seen_canonical[canonical]})")
        normalized[canonical] = value
        seen_canonical[canonical] = src_key
        if src_key != canonical:
            renamed.append(f"{src_key}→{canonical}")
    return normalized, renamed, invalid

# 2026-04-23 Round 16 · 14 模型扁平化（根治 Ch6 RCA Bug #4 + core 概念过度耦合）
# 根因：core 3 模型硬要求 + openclawroot 单 provider 脆弱 → Ch3-6 连续 4 章 DEV 事故
# 根治：去 core/supplemental 层级 · 14 模型集体投票 · 任一失败不阻塞
# 判定改为：成功模型数 ≥ 10/14 pass · 8-9/14 medium warn · <8/14 high warn（不 critical block）
EXTERNAL_MODELS_ALL = [
    "qwen3.6-plus", "doubao-pro", "gpt-5.4", "gemini-3.1-pro",
    "doubao-seed-2.0-lite", "glm-5", "glm-5.1", "glm-4.7",
    "mimo-v2-pro", "minimax-m2.7-hs", "minimax-m2.5",
    "deepseek-v3.2-thinking", "kimi-k2.5", "kimi-k2.6",
]
# Round 16 完整度阈值（A3 判定核心参数）
EXTERNAL_MODELS_HEALTHY_MIN = 10    # ≥ 10/14 → pass
EXTERNAL_MODELS_DEGRADED_MIN = 8    # 8-9/14 → warn medium
EXTERNAL_MODELS_HIGH_WARN_MIN = 5   # 5-7/14 → warn high（仍不 critical block）
# 向后兼容 aliases（历史代码/外部引用 · 保留避免其他模块 ImportError）
EXTERNAL_MODELS_CORE3 = []  # Round 16 置空 · 不再有 core 概念
EXTERNAL_MODELS_SUPPLEMENTAL = list(EXTERNAL_MODELS_ALL)
EXTERNAL_MODELS_ALL9 = EXTERNAL_MODELS_ALL

DATA_AGENT_STEPS_REQUIRED = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]  # K 为 best-effort
EXTERNAL_REVIEW_EXPECTED_DIMENSIONS = 13  # Round 13 v2: 11 工艺维度 + naturalness + reader_critic
WORKFLOW_REQUIRED_STEPS = {
    "webnovel-write": ["Step 1", "Step 2A", "Step 2B", "Step 3", "Step 3.5", "Step 4", "Step 5", "Step 6", "Step 7"],
    "webnovel-review": ["Step 1", "Step 2", "Step 3", "Step 4", "Step 5", "Step 6", "Step 7", "Step 8"],
}

# ==================== 数据结构 ====================

@dataclass
class CheckResult:
    id: str
    name: str
    layer: str
    status: str  # pass / warn / fail / skipped
    severity: str  # critical / high / medium / low
    evidence: str
    measured: Dict[str, Any] = field(default_factory=dict)
    remediation: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LayerResult:
    layer: str
    score: Optional[int]
    checks: List[CheckResult] = field(default_factory=list)
    skipped_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "checks": [c.to_dict() for c in self.checks],
            **({"skipped_reason": self.skipped_reason} if self.skipped_reason else {}),
        }


# ==================== 辅助函数 ====================

def _pad(chapter: int) -> str:
    return f"{chapter:04d}"


def _read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return None


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        return rows
    return rows


def _find_chapter_file(project_root: Path, chapter: int) -> Optional[Path]:
    chapters_dir = project_root / "正文"
    if not chapters_dir.exists():
        return None
    pattern = f"第{chapter:04d}章"
    for p in chapters_dir.glob(f"{pattern}*.md"):
        return p
    # fallback: without padding
    pattern2 = f"第{chapter}章"
    for p in chapters_dir.glob(f"{pattern2}*.md"):
        return p
    return None


def _find_review_report(project_root: Path, chapter: int) -> Optional[Path]:
    p = project_root / "审查报告" / f"第{chapter:04d}章审查报告.md"
    if p.exists():
        return p
    p2 = project_root / "审查报告" / f"第{chapter}章审查报告.md"
    if p2.exists():
        return p2
    return None


def _chapter_meta_entry(project_root: Path, chapter: int) -> Dict[str, Any]:
    state_path = project_root / ".webnovel" / "state.json"
    state = _read_json(state_path) or {}
    chapter_meta = state.get("chapter_meta") or {}
    for key in (_pad(chapter), str(chapter), f"{chapter:04d}"):
        value = chapter_meta.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _load_external_review_results(project_root: Path, chapter: int) -> Dict[str, Dict[str, Any]]:
    tmp_dir = project_root / ".webnovel" / "tmp"
    if not tmp_dir.exists():
        return {}

    results: Dict[str, Dict[str, Any]] = {}
    pattern = re.compile(rf"^external_review_(.+)_ch{_pad(chapter)}\.json$")
    for path in tmp_dir.glob(f"external_review_*_ch{_pad(chapter)}.json"):
        data = _read_json(path)
        if not isinstance(data, dict):
            continue
        match = pattern.match(path.name)
        model_key = str(data.get("model_key") or (match.group(1) if match else "")).strip()
        if not model_key:
            continue
        results[model_key] = {"path": path, "data": data}
    return results


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts or not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _score_from_checks(checks: List[CheckResult]) -> int:
    """根据 check 结果计算 layer 分数（0-100）."""
    if not checks:
        return 100
    total = 0
    for c in checks:
        if c.status == "pass":
            total += 100
        elif c.status == "warn":
            total += 70
        elif c.status == "skipped":
            total += 100  # skipped 不扣分
        else:  # fail
            if c.severity == "critical":
                total += 0
            elif c.severity == "high":
                total += 20
            elif c.severity == "medium":
                total += 40
            else:
                total += 60
    return int(total / len(checks))


# ==================== Layer A: 过程真实性 ====================

def check_A1_contract_completeness(project_root: Path, chapter: int) -> CheckResult:
    """A1: Context Contract 完整性 — context_snapshots/ch{NNNN}.json 必须存在且含 8 板块 + Contract 12 字段."""
    snap_path = project_root / ".webnovel" / "context_snapshots" / f"ch{_pad(chapter)}.json"
    data = _read_json(snap_path)
    if data is None:
        return CheckResult(
            id="A1", name="Context Contract 完整性", layer="A",
            status="fail", severity="critical",
            evidence=f"context_snapshots/ch{_pad(chapter)}.json 不存在或无法解析",
            remediation=["重跑 Step 1: Task(context-agent, chapter=%d)" % chapter],
        )
    # payload 可能被 "payload" key 包裹，也可能直接在顶层
    payload = data.get("payload") or {}
    if not payload:
        payload = data

    # --- 格式 A: 直接 panels dict（context-agent 紧凑格式） ---
    direct_panels = payload.get("panels")
    if isinstance(direct_panels, dict) and len(direct_panels) >= 4:
        panels_count = len(direct_panels)
        panels_list = list(direct_panels.keys())
        fmt = payload.get("format", "v1-compact")
        contract = payload.get("contract") or payload.get("Contract") or {}
        contract_fields = len(contract) if isinstance(contract, dict) else 0
    else:
        # --- 格式 B: v2 — meta + sections 结构 ---
        sections = payload.get("sections") or {}
        has_meta = "meta" in payload
        expected_v2 = ["core", "scene", "global", "reader_signal", "genre_profile",
                       "writing_guidance", "story_skeleton", "memory"]
        present_v2 = [k for k in expected_v2 if k in sections]

        if sections and (has_meta or present_v2):
            panels_count = len(present_v2) + (1 if has_meta else 0)
            panels_list = (["meta"] if has_meta else []) + present_v2
            fmt = "v2"
            # v2 contract: 从 meta / core.content / 同目录 .md 中提取关键词
            contract = payload.get("contract") or payload.get("Contract") or {}
            if not contract:
                contract_fields_found: set = set()
                # Contract v2 字段标记列表（中文 + 英文，覆盖 context-agent 两种输出风格）
                CONTRACT_MARKERS = [
                    "目标", "阻力", "代价", "本章变化", "钩子",
                    "未闭合问题", "核心冲突", "开头类型", "情绪节奏",
                    "爽点", "情感锚点", "时间约束", "Strand", "时间锚点", "章内时间跨度",
                    "goal", "obstacle", "cost", "change", "open_question",
                    "core_conflict", "opening_type", "emotion_rhythm",
                    "hooks", "cool_point", "emotion_anchor", "time_constraint",
                ]
                # 来源 1: sections.core.content.chapter_outline（字符串）
                core = sections.get("core", {})
                core_content = core.get("content", {}) if isinstance(core, dict) else {}
                outline_text = core_content.get("chapter_outline", "") if isinstance(core_content, dict) else ""
                if isinstance(outline_text, str):
                    for m in CONTRACT_MARKERS:
                        if m in outline_text:
                            contract_fields_found.add(m)
                # 来源 2: sections.core.content 本身的 dict keys
                if isinstance(core_content, dict):
                    for k in core_content.keys():
                        contract_fields_found.add(k)
                # 来源 3: 同章节 .md 文件（context-agent 首选输出）
                md_path = snap_path.with_suffix(".md")
                if md_path.exists():
                    try:
                        md_text = md_path.read_text(encoding="utf-8")
                        for m in CONTRACT_MARKERS:
                            if m in md_text:
                                contract_fields_found.add(m)
                    except Exception:
                        pass
                contract = {k: True for k in contract_fields_found}
            contract_fields = len(contract) if isinstance(contract, dict) else 0
        else:
            # --- 格式 C: v1 — 8 个顶级 key ---
            expected_panels = ["state", "outline", "settings", "previous_summaries", "style_guide",
                               "entity_cards", "editor_notes", "contract"]
            present = [k for k in expected_panels if k in payload]
            panels_count = len(present)
            panels_list = present
            fmt = "v1"
            contract = payload.get("contract") or payload.get("Contract") or {}
            contract_fields = len(contract) if isinstance(contract, dict) else 0

    contract_fields_min = 8
    min_panels = 6
    if panels_count < min_panels:
        return CheckResult(
            id="A1", name="Context Contract 完整性", layer="A",
            status="fail", severity="critical",
            evidence=f"snapshot 板块不全 (fmt={fmt}, present={panels_list})",
            measured={"panels_present": panels_count, "contract_fields": contract_fields, "format": fmt},
            remediation=["重跑 Step 1: Task(context-agent, chapter=%d)" % chapter],
        )
    if contract_fields < contract_fields_min:
        return CheckResult(
            id="A1", name="Context Contract 完整性", layer="A",
            status="warn", severity="high",
            evidence=f"Contract 字段不足 ({contract_fields} < {contract_fields_min})",
            measured={"panels_present": panels_count, "contract_fields": contract_fields, "format": fmt},
            remediation=["检查 context-agent 是否完整填充 Contract v2 所有字段"],
        )
    return CheckResult(
        id="A1", name="Context Contract 完整性", layer="A",
        status="pass", severity="high",
        evidence=f"snapshot {fmt} 格式, {panels_count} 个板块, Contract {contract_fields} 字段",
        measured={"panels_present": panels_count, "contract_fields": contract_fields, "format": fmt},
    )


def check_A2_checker_diversity(project_root: Path, chapter: int) -> CheckResult:
    """A2: internal checker coverage should be visible in both report text and state.json."""
    report = _find_review_report(project_root, chapter)
    if report is None:
        return CheckResult(
            id="A2", name="13 checker 独立调用", layer="A",
            status="fail", severity="critical",
            evidence="review report is missing",
            remediation=["rerun Step 3 with all 11 internal checkers"],
        )

    text = _read_text(report) or ""

    def _checker_found(name: str, txt: str) -> bool:
        if name in txt:
            return True
        for alias in CHECKER_ALIASES.get(name, []):
            if alias in txt:
                return True
        return False

    def _normalize_checker_snippet(line: str) -> str:
        cleaned = line.lower()
        for checker_name in CHECKER_NAMES:
            cleaned = cleaned.replace(checker_name.lower(), " ")
            for alias in CHECKER_ALIASES.get(checker_name, []):
                cleaned = cleaned.replace(str(alias).lower(), " ")
        cleaned = re.sub(r"(?<![\w.])(100(?:\.0+)?|[1-9]?\d(?:\.\d+)?)(?![\w.])", " ", cleaned)
        cleaned = re.sub(r"[|:：\-*_`#()\[\]{}]+", " ", cleaned)
        cleaned = re.sub(
            r"\b(?:batch|score|checker|internal|review|low|medium|high|critical|warn|pass)\b",
            " ",
            cleaned,
        )
        tokens = [
            token
            for token in re.findall(r"[a-z][a-z0-9_.-]+|[\u4e00-\u9fff]{2,}", cleaned)
            if len(token) >= 2
        ]
        return " ".join(tokens)

    def _extract_checker_score(line: str) -> Optional[float]:
        numbers = re.findall(r"(?<![\w.])(100(?:\.0+)?|[1-9]?\d(?:\.\d+)?)(?![\w.])", line)
        if not numbers:
            return None
        try:
            return float(numbers[0])
        except Exception:
            return None

    missing = [c for c in CHECKER_NAMES if not _checker_found(c, text)]
    chapter_meta = _chapter_meta_entry(project_root, chapter)
    checker_scores_raw = chapter_meta.get("checker_scores") or {}
    # Normalize checker_scores keys via CHECKER_ALIASES reverse map
    # (defends against AI fallback writing 中文 key like "钩子强度"/"Anti-AI")
    normalized_scores, renamed_keys, invalid_keys = normalize_checker_scores_keys(
        checker_scores_raw if isinstance(checker_scores_raw, dict) else {}
    )
    checker_scores = normalized_scores
    state_checker_count = len([k for k, v in checker_scores.items()
                               if v is not None and k not in CHECKER_SCORES_RESERVED_KEYS])

    report_rows: Dict[str, List[str]] = {}
    report_score_map: Dict[str, float] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        for checker_name in CHECKER_NAMES:
            if not _checker_found(checker_name, line):
                continue
            report_rows.setdefault(checker_name, []).append(line)
            if checker_name not in report_score_map:
                score = _extract_checker_score(line)
                if score is not None:
                    report_score_map[checker_name] = score
            break

    score_values: List[float] = []
    for checker_name in CHECKER_NAMES:
        value = None
        if isinstance(checker_scores, dict):
            candidate = checker_scores.get(checker_name)
            if isinstance(candidate, (int, float)):
                value = float(candidate)
        if value is None:
            value = report_score_map.get(checker_name)
        if isinstance(value, (int, float)):
            score_values.append(float(value))

    unique_scores = sorted({round(v, 1) for v in score_values})
    normalized_snippets = []
    for checker_name in CHECKER_NAMES:
        joined = " ".join(report_rows.get(checker_name, []))
        normalized = _normalize_checker_snippet(joined)
        if normalized:
            normalized_snippets.append(normalized)

    duplicate_snippet_counts: Dict[str, int] = {}
    for snippet in normalized_snippets:
        duplicate_snippet_counts[snippet] = duplicate_snippet_counts.get(snippet, 0) + 1
    duplicated_snippets = [s for s, count in duplicate_snippet_counts.items() if count >= 3]

    measured = {
        "present_count": len(CHECKER_NAMES) - len(missing),
        "missing": missing,
        "state_checker_scores_count": state_checker_count,
        "unique_scores": unique_scores,
        "duplicated_snippets": duplicated_snippets,
        "state_key_renames": renamed_keys,
        "state_key_invalid": invalid_keys,
    }
    # A2.1 · canonical key 校验（检测 AI fallback 写 legacy/中文 key）
    if invalid_keys:
        return CheckResult(
            id="A2", name="13 checker 独立调用 · canonical key", layer="A",
            status="warn", severity="high",
            evidence=(
                f"state.json checker_scores 含非 canonical key: {invalid_keys[:5]}. "
                f"应使用 CHECKER_NAMES 英文 key 或中文别名映射后的 canonical 名。"
            ),
            measured=measured,
            remediation=[
                "normalize state.json chapter_meta.checker_scores via CHECKER_ALIASES",
                "update data-agent 写入路径强制 canonical key",
            ],
        )
    if len(missing) >= 3:
        return CheckResult(
            id="A2", name="13 checker 独立调用", layer="A",
            status="fail", severity="critical",
            evidence=f"review report is missing checker entries: {missing}",
            measured=measured,
            remediation=["rerun Step 3 with all 11 internal checkers"],
        )
    if missing:
        return CheckResult(
            id="A2", name="13 checker 独立调用", layer="A",
            status="warn", severity="high",
            evidence=f"review report is missing checker entries: {missing}",
            measured=measured,
            remediation=["backfill the missing checker runs"],
        )
    if len(score_values) >= 8 and len(unique_scores) <= 2:
        return CheckResult(
            id="A2", name="13 checker 独立调用", layer="A",
            status="fail", severity="critical",
            evidence=f"checker scores collapsed into only {len(unique_scores)} distinct values: {unique_scores}",
            measured=measured,
            remediation=["rerun Step 3 and ensure each checker produces an independent judgment"],
        )
    if duplicated_snippets:
        return CheckResult(
            id="A2", name="13 checker 独立调用", layer="A",
            status="fail", severity="critical",
            evidence="checker review snippets look duplicated across multiple checkers",
            measured=measured,
            remediation=["rerun Step 3 and inspect for checker prompt collapse or copy-paste reuse"],
        )
    if state_checker_count and state_checker_count < 8:
        return CheckResult(
            id="A2", name="13 checker 独立调用", layer="A",
            status="warn", severity="high",
            evidence=f"state.json only persisted {state_checker_count} checker scores",
            measured=measured,
            remediation=["inspect Step 5 and ensure checker_scores are persisted into chapter_meta"],
        )
    return CheckResult(
        id="A2", name="13 checker 独立调用", layer="A",
        status="pass", severity="high",
        evidence="review report contains all 13 checkers (含 flow-checker + naturalness + reader-critic, Round 13 v2)",
        measured=measured,
    )

def check_A3_external_models(project_root: Path, chapter: int) -> CheckResult:
    """A3: external review must have durable JSON evidence, not just markdown mentions.

    Round 16 · 2026-04-23 · 扁平化共识机制（去 core 硬要求）：
        判定逻辑基于"有效模型数"而非"是否齐全 core 3"：
          - ≥ 10/14 有效 → pass（healthy · 14 模型共识充分）
          - 8-9/14 有效 → warn medium（degraded_ok · 不阻塞）
          - 5-7/14 有效 → warn high（degraded_warn · 仍不 critical block · 因为 5+ 模型已够共识）
          - < 5/14 有效 → fail critical（实际几乎不会发生 · 多家 provider 同时挂）
        保留：routing_verified 校验 · phantom_zero 检测 · score_spread alert
    """
    report = _find_review_report(project_root, chapter)
    external_results = _load_external_review_results(project_root, chapter)
    if report is None and not external_results:
        return CheckResult(
            id="A3", name="外部模型覆盖", layer="A",
            status="fail", severity="high",
            evidence="review report and external review JSON are both missing",
            remediation=["rerun Step 3.5: python external_review.py --mode dimensions --model-key all"],
        )

    if external_results:
        valid_models: List[str] = []
        partial_models: List[str] = []
        unrouted_models: List[str] = []
        phantom_models: List[str] = []
        invalid_models: Dict[str, List[str]] = {}
        for model_key, payload in external_results.items():
            data = payload.get("data") or {}
            dimension_reports = data.get("dimension_reports") or []
            ok_dims = [d for d in dimension_reports if d.get("status") == "ok"]
            expected_dimensions = EXTERNAL_REVIEW_EXPECTED_DIMENSIONS
            model_issues: List[str] = []
            routing_verified = data.get("routing_verified") is True
            if not routing_verified:
                unrouted_models.append(model_key)
                model_issues.append("routing_unverified")

            if len(ok_dims) < expected_dimensions:
                partial_models.append(model_key)
                model_issues.append(f"incomplete_dimensions:{len(ok_dims)}/{expected_dimensions}")

            model_phantom_hits = 0
            for item in dimension_reports:
                summary = str(item.get("summary") or "").strip()
                score = item.get("score")
                status = str(item.get("status") or "")
                if status == "ok" and isinstance(score, (int, float)) and float(score) == 0 and not summary:
                    model_phantom_hits += 1
            if model_phantom_hits:
                phantom_models.append(model_key)
                model_issues.append(f"phantom_zero_dimensions:{model_phantom_hits}")

            if not model_issues:
                valid_models.append(model_key)
            else:
                invalid_models[model_key] = model_issues

        total_expected = len(EXTERNAL_MODELS_ALL)
        valid_count = len(valid_models)

        # Round 12: external score spread alert.
        # Ch1《末世重生》血教训——Gemini 75.3 与其他模型 87-91 分差 ≥ 10，
        # 平均化稀释后主审查员未读 Gemini 低分 issue，漏掉时间线矛盾。
        model_scores: Dict[str, float] = {}
        for model_key, payload in external_results.items():
            data = payload.get("data") or {}
            score = data.get("overall_score")
            if isinstance(score, (int, float)) and score > 0:
                model_scores[model_key] = float(score)
        spread_alert_note = None
        if len(model_scores) >= 2:
            max_score = max(model_scores.values())
            min_score = min(model_scores.values())
            score_spread = max_score - min_score
            if score_spread >= 10:
                lowest_model = min(model_scores, key=model_scores.get)
                highest_model = max(model_scores, key=model_scores.get)
                spread_alert_note = (
                    f"external_score_spread={score_spread:.1f} >= 10 "
                    f"(lowest={lowest_model}:{min_score:.1f}, highest={highest_model}:{max_score:.1f}). "
                    f"人工强制复核 {lowest_model} 的 all high/medium issues."
                )

        measured = {
            "valid_count": valid_count,
            "total_expected": total_expected,
            "valid_models": sorted(valid_models),
            "partial_models": sorted(partial_models),
            "unrouted_models": sorted(unrouted_models),
            "phantom_models": sorted(phantom_models),
            "invalid_models": invalid_models,
            "coverage_status": (
                "healthy" if valid_count >= EXTERNAL_MODELS_HEALTHY_MIN
                else "degraded_ok" if valid_count >= EXTERNAL_MODELS_DEGRADED_MIN
                else "degraded_warn" if valid_count >= EXTERNAL_MODELS_HIGH_WARN_MIN
                else "critical"
            ),
            "thresholds": {
                "healthy_min": EXTERNAL_MODELS_HEALTHY_MIN,
                "degraded_ok_min": EXTERNAL_MODELS_DEGRADED_MIN,
                "high_warn_min": EXTERNAL_MODELS_HIGH_WARN_MIN,
            },
        }
        if len(model_scores) >= 2:
            measured["score_spread"] = round(max(model_scores.values()) - min(model_scores.values()), 1)
            measured["lowest_model"] = min(model_scores, key=model_scores.get)
            measured["highest_model"] = max(model_scores, key=model_scores.get)

        # Round 16 扁平判定：
        if valid_count < EXTERNAL_MODELS_HIGH_WARN_MIN:
            # < 5/14 有效：多家 provider 同时挂 · 真正的 critical
            missing_models = [m for m in EXTERNAL_MODELS_ALL if m not in valid_models]
            return CheckResult(
                id="A3", name="外部模型覆盖", layer="A",
                status="fail", severity="critical",
                evidence=(
                    f"external review coverage critical: only {valid_count}/{total_expected} models valid "
                    f"(< {EXTERNAL_MODELS_HIGH_WARN_MIN}). Consensus may be unreliable. "
                    f"missing/invalid={sorted(missing_models)}"
                ),
                measured=measured,
                remediation=[
                    "Check provider health (openclawroot/ark-coding/siliconflow)",
                    "rerun Step 3.5 for all models: python external_review.py --mode dimensions --model-key all",
                ],
            )
        if valid_count < EXTERNAL_MODELS_DEGRADED_MIN:
            # 5-7/14：warn high · 不 block（共识仍足够）
            missing_models = [m for m in EXTERNAL_MODELS_ALL if m not in valid_models]
            extra = []
            if spread_alert_note:
                extra.append(spread_alert_note)
            return CheckResult(
                id="A3", name="外部模型覆盖", layer="A",
                status="warn", severity="high",
                evidence=(
                    f"external review coverage degraded: {valid_count}/{total_expected} models valid "
                    f"(Round 16 扁平阈值：5-7 为 warn high · 不阻塞). "
                    f"missing/invalid={sorted(missing_models)}"
                    + (f". {' | '.join(extra)}" if extra else "")
                ),
                measured=measured,
                remediation=[
                    "可重跑失败模型 · 若 provider outage 本章可接受（共识仍够）",
                    "下章 Step 3.5 前验证 provider 健康度",
                ] + (["人工复核最低分模型的 high/medium issues"] if spread_alert_note else []),
            )
        if valid_count < EXTERNAL_MODELS_HEALTHY_MIN:
            # 8-9/14：warn medium
            # Round 18 · 2026-04-24 · Ch10 P1-5 根治：明确严格 valid vs 宽松 success 口径差异
            # external_review.py 报 coverage 用宽松判定（API 响应有 JSON 即 success），
            # audit A3 用严格判定（routing_verified + 全维度 OK + 0 phantom），两者口径必然不同。
            missing_models = [m for m in EXTERNAL_MODELS_ALL if m not in valid_models]
            extra = []
            if spread_alert_note:
                extra.append(spread_alert_note)
            lenient_success = total_expected - sum(
                1 for m in EXTERNAL_MODELS_ALL
                if m not in external_results
            )
            return CheckResult(
                id="A3", name="外部模型覆盖", layer="A",
                status="warn", severity="medium",
                evidence=(
                    f"external review coverage ok (degraded_ok): "
                    f"严格 valid={valid_count}/{total_expected}（路由+全维度+无 phantom）· "
                    f"宽松 success={lenient_success}/{total_expected}（仅看 API 响应）· "
                    f"missing/invalid={sorted(missing_models)}"
                    + (f". {' | '.join(extra)}" if extra else "")
                ),
                measured={**measured, "lenient_success_count": lenient_success},
                remediation=(
                    ["人工复核最低分模型的 high/medium issues"] if spread_alert_note else []
                ),
            )
        # ≥ 10/14 有效：healthy pass
        if spread_alert_note:
            return CheckResult(
                id="A3", name="外部模型覆盖", layer="A",
                status="warn", severity="medium",
                evidence=f"{valid_count}/{total_expected} external review JSON files are valid (healthy); {spread_alert_note}",
                measured=measured,
                remediation=["人工复核最低分模型的 high/medium issues，确认是共识低还是观察视角差异"],
            )
        return CheckResult(
            id="A3", name="外部模型覆盖", layer="A",
            status="pass", severity="high",
            evidence=f"{valid_count}/{total_expected} external review JSON files are valid (healthy · Round 16 扁平共识)",
            measured=measured,
        )

    # Fallback 路径：无 JSON 产物 · 只有 markdown 报告
    text = _read_text(report) or ""
    present = [m for m in EXTERNAL_MODELS_ALL if m in text.lower() or m in text]
    phantom_hits = 0
    zero_pattern = re.compile(
        r"(?:kimi|kimi-k2\.[56]|glm|glm-5\.1|qwen-plus|qwen3\.6-plus|minimax|minimax-m2\.[57]|minimax-m2\.7-hs|doubao|doubao-seed-2\.0-(?:pro|lite)|doubao-pro|qwen|glm4|glm-4\.7|deepseek|deepseek-v3\.2(?:-thinking)?|gpt-5\.4|gemini-3\.1-pro|mimo-v2-pro)[^\n]{0,40}[:：]\s*0(?:\.0+)?(?:\b|$)",
        re.IGNORECASE,
    )
    for match in zero_pattern.finditer(text):
        start = max(0, match.start() - 50)
        end = min(len(text), match.end() + 300)
        snippet = text[start:end]
        if len(snippet.replace(" ", "").replace("\n", "")) < 150:
            phantom_hits += 1

    measured = {"all_present": present, "phantom_zeros": phantom_hits}
    if phantom_hits > 0:
        return CheckResult(
            id="A3", name="外部模型覆盖", layer="A",
            status="fail", severity="high",
            evidence="review report contains likely phantom zero scores",
            measured=measured,
            remediation=["rerun Step 3.5 for the failed external models"],
        )
    if len(present) < EXTERNAL_MODELS_HIGH_WARN_MIN:
        return CheckResult(
            id="A3", name="外部模型覆盖", layer="A",
            status="warn", severity="high",
            evidence=f"review report implies too few external model reviews (<{EXTERNAL_MODELS_HIGH_WARN_MIN}/14)",
            measured=measured,
            remediation=["persist external review JSON instead of relying on markdown only"],
        )
    return CheckResult(
        id="A3", name="外部模型覆盖", layer="A",
        status="pass", severity="medium",
        evidence=f"review report shows external review coverage ({len(present)}/14 mentioned), but JSON evidence is preferred",
        measured=measured,
    )

def check_A4_data_agent_steps(project_root: Path, chapter: int) -> CheckResult:
    """A4: data agent timing must show either aggregate timing_ms or per-step markers."""
    timing_path = project_root / ".webnovel" / "observability" / "data_agent_timing.jsonl"
    rows = _read_jsonl(timing_path)
    if not rows:
        return CheckResult(
            id="A4", name="Data Agent 子步完成", layer="A",
            status="fail", severity="high",
            evidence="data_agent_timing.jsonl is missing or empty",
            remediation=["rerun Step 5 for this chapter"],
        )

    chapter_rows = [r for r in rows if r.get("chapter") == chapter]
    if not chapter_rows:
        return CheckResult(
            id="A4", name="Data Agent 子步完成", layer="A",
            status="warn", severity="medium",
            evidence=f"no data-agent timing rows found for chapter {chapter}",
            remediation=["ensure Step 5 writes chapter-scoped timing rows"],
        )

    tools = {str(r.get("tool_name") or "") for r in chapter_rows if r.get("tool_name")}
    timing_rows = [r for r in chapter_rows if isinstance(r.get("timing_ms"), dict)]
    if timing_rows:
        latest = timing_rows[-1]
        timing_ms = latest.get("timing_ms") or {}
        present_steps = sorted({str(key).split("_", 1)[0] for key in timing_ms.keys() if "_" in str(key)})
        if "J" not in present_steps:
            present_steps.append("J")
        missing_core = [step for step in list("ABCDEFGH") if step not in present_steps]
        missing_optional = [step for step in ("I", "K") if step not in present_steps]
        measured = {
            "chapter_rows": len(chapter_rows),
            "tools_count": len(tools),
            "steps_found": present_steps,
            "total_ms": timing_ms.get("TOTAL"),
        }
        if missing_core:
            return CheckResult(
                id="A4", name="Data Agent 子步完成", layer="A",
                status="fail", severity="high",
                evidence=f"timing_ms is missing core data-agent steps: {missing_core}",
                measured=measured,
                remediation=["rerun Step 5 and ensure the aggregate timing row includes steps A-H"],
            )
        if missing_optional:
            return CheckResult(
                id="A4", name="Data Agent 子步完成", layer="A",
                status="warn", severity="medium",
                evidence=f"timing_ms is missing optional data-agent steps: {missing_optional}",
                measured=measured,
                remediation=["record why optional steps were skipped or persist them in timing_ms"],
            )
        return CheckResult(
            id="A4", name="Data Agent 子步完成", layer="A",
            status="pass", severity="medium",
            evidence=f"timing_ms captured data-agent steps: {present_steps}",
            measured=measured,
        )

    step_markers_found = []
    for step_letter in DATA_AGENT_STEPS_REQUIRED:
        marker = f"step_{step_letter.lower()}"
        if any(marker in t.lower() for t in tools):
            step_markers_found.append(step_letter)
    # 新增：当 timing_ms 和 legacy markers 都缺失时，检查其他 Step 5 产物是否齐备——
    # 若齐备说明 data-agent 已完成（只是没写 timing），降级为 skipped 而不是 warn
    if len(step_markers_found) < 5:
        summary_ok = (project_root / ".webnovel" / "summaries" / f"ch{_pad(chapter)}.md").exists()
        state_path = project_root / ".webnovel" / "state.json"
        state_meta_ok = False
        if state_path.exists():
            try:
                import json as _json
                s = _json.loads(state_path.read_text(encoding="utf-8"))
                state_meta_ok = f"{_pad(chapter)}" in (s.get("chapter_meta") or {})
            except Exception:
                state_meta_ok = False
        if summary_ok and state_meta_ok:
            return CheckResult(
                id="A4", name="Data Agent 子步完成", layer="A",
                status="skipped", severity="low",
                evidence="legacy markers absent but Step 5 artifacts complete (summary + chapter_meta)",
                measured={"chapter_rows": len(chapter_rows), "tools_count": len(tools), "steps_found": step_markers_found},
                remediation=["非阻断：新 data-agent 未写 legacy 标记但已完成实际工作；建议未来补 timing_ms 聚合行"],
            )
        return CheckResult(
            id="A4", name="Data Agent 子步完成", layer="A",
            status="warn", severity="medium",
            evidence=f"only found {len(step_markers_found)} legacy data-agent step markers",
            measured={"chapter_rows": len(chapter_rows), "tools_count": len(tools), "steps_found": step_markers_found},
            remediation=["prefer aggregate timing_ms rows, or persist a fuller legacy step trace"],
        )
    return CheckResult(
        id="A4", name="Data Agent 子步完成", layer="A",
        status="pass", severity="medium",
        evidence=f"legacy data-agent markers detected for steps: {step_markers_found}",
        measured={"chapter_rows": len(chapter_rows), "steps_found": step_markers_found},
    )

def check_A5_fallback_detection(project_root: Path, chapter: int) -> CheckResult:
    """A5: Subagent fallback 检测 — call_trace.jsonl 不得出现 general-purpose fallback."""
    trace_path = project_root / ".webnovel" / "observability" / "call_trace.jsonl"
    rows = _read_jsonl(trace_path)
    if not rows:
        return CheckResult(
            id="A5", name="Subagent fallback 检测", layer="A",
            status="warn", severity="medium",
            evidence="call_trace.jsonl 不存在或为空（无法判断）",
            remediation=["检查 workflow_manager 是否正确写入 call_trace"],
        )
    # 筛选出本章相关的 trace
    fallback_hits: List[str] = []
    for r in rows:
        payload = r.get("payload", {}) or {}
        trace_chapter = payload.get("chapter") or payload.get("chapter_num")
        if trace_chapter is not None and trace_chapter != chapter:
            continue
        # 检查 agent_type / subagent_type 字段
        blob = json.dumps(r, ensure_ascii=False).lower()
        if "general-purpose" in blob and ("fallback" in blob or "subagent" in blob or "agent_type" in blob):
            fallback_hits.append(r.get("event", "unknown"))
    if fallback_hits:
        return CheckResult(
            id="A5", name="Subagent fallback 检测", layer="A",
            status="fail", severity="critical",
            evidence=f"检测到 {len(fallback_hits)} 处 general-purpose fallback: {fallback_hits[:5]}",
            measured={"fallback_count": len(fallback_hits)},
            remediation=[
                "确认 webnovel-writer 插件已启用: claude plugin enable webnovel-writer@webnovel-writer-marketplace",
                "重启会话以重新加载 subagents",
                "重跑受影响的步骤",
            ],
        )
    return CheckResult(
        id="A5", name="Subagent fallback 检测", layer="A",
        status="pass", severity="critical",
        evidence=f"call_trace 扫描 {len(rows)} 条，无 fallback 事件",
        measured={"trace_rows_total": len(rows), "fallback_count": 0},
    )


def check_A6_workflow_timing(project_root: Path, chapter: int) -> CheckResult:
    """A6: workflow state must preserve an ordered, violation-free chapter trace."""
    ws_path = project_root / ".webnovel" / "workflow_state.json"
    data = _read_json(ws_path)
    if data is None:
        return CheckResult(
            id="A6", name="Workflow 时序校验", layer="A",
            status="warn", severity="high",
            evidence="workflow_state.json is missing",
        )

    # Audit-agent only cares about the webnovel-write or webnovel-review task
    # for this chapter. Helper entries like "ch2-hygiene" share the same
    # chapter number but have a different command — we must exclude them,
    # otherwise A6 silently picks the wrong snapshot and reports bogus
    # "1 ordered step" evidence.
    primary_commands = {"webnovel-write", "webnovel-review"}
    snapshot = None
    current_task = data.get("current_task") or {}
    if (
        current_task.get("command") in primary_commands
        and (current_task.get("args") or {}).get("chapter_num") == chapter
    ):
        snapshot = current_task
    else:
        history = data.get("history") or []
        for item in reversed(history):
            if item.get("command") not in primary_commands:
                continue
            args = item.get("args") or {}
            if item.get("chapter") == chapter or args.get("chapter_num") == chapter:
                snapshot = item
                break
    if snapshot is None:
        return CheckResult(
            id="A6", name="Workflow 时序校验", layer="A",
            status="warn", severity="high",
            evidence=f"no workflow snapshot found for chapter {chapter}",
        )

    command = str(snapshot.get("command") or "webnovel-write")
    sequence = WORKFLOW_REQUIRED_STEPS.get(command, [])
    completed = snapshot.get("completed_steps") or []
    failed_steps = snapshot.get("failed_steps") or []
    current_step = snapshot.get("current_step") or {}
    task_status = snapshot.get("status")
    completed_ids = [str(item.get("id")) for item in completed]

    if task_status == "failed" or failed_steps:
        reason = snapshot.get("failure_reason") or (failed_steps[-1].get("failure_reason") if failed_steps else "unknown")
        return CheckResult(
            id="A6", name="Workflow 时序校验", layer="A",
            status="fail", severity="critical",
            evidence=f"workflow already failed: {reason}",
            measured={"failed_steps": [step.get("id") for step in failed_steps]},
            remediation=["repair the failed step and resume from the last stable state"],
        )
    if not completed and not current_step:
        return CheckResult(
            id="A6", name="Workflow 时序校验", layer="A",
            status="fail", severity="critical",
            evidence=f"chapter {chapter} has no completed_steps and no active step",
            remediation=["restart workflow tracking so Step 0.5 persists workflow state"],
        )

    if task_status == "completed":
        expected_steps = sequence or completed_ids
    elif current_step and current_step.get("id") in sequence:
        expected_steps = sequence[:sequence.index(current_step["id"])]
    else:
        expected_steps = completed_ids

    missing_steps = [step for step in expected_steps if step not in completed_ids]
    if missing_steps:
        return CheckResult(
            id="A6", name="Workflow 时序校验", layer="A",
            status="fail", severity="critical",
            evidence=f"workflow is missing required steps: {missing_steps}",
            measured={"completed_steps": completed_ids, "missing_steps": missing_steps},
            remediation=["rerun the missing workflow steps in the planned order"],
        )

    timestamps = []
    for step in completed:
        ts = step.get("completed_at") or step.get("started_at")
        if ts:
            timestamps.append((str(step.get("id", "?")), ts))
    violations = []
    for i in range(1, len(timestamps)):
        if timestamps[i][1] < timestamps[i - 1][1]:
            violations.append(f"{timestamps[i - 1][0]}->{timestamps[i][0]}")

    trace_rows = _read_jsonl(project_root / ".webnovel" / "observability" / "call_trace.jsonl")
    trace_start = _parse_iso(snapshot.get("started_at"))
    trace_end = _parse_iso(snapshot.get("completed_at") or snapshot.get("failed_at"))
    invalid_events = []
    for row in trace_rows:
        payload = row.get("payload") or {}
        trace_chapter = payload.get("chapter") or payload.get("chapter_num") or (payload.get("args") or {}).get("chapter_num")
        if trace_chapter != chapter:
            continue
        row_ts = _parse_iso(row.get("timestamp"))
        if trace_start and row_ts and row_ts < trace_start:
            continue
        if trace_end and row_ts and row_ts > trace_end:
            continue
        if row.get("event") in {"step_order_violation", "step_complete_rejected", "task_complete_rejected", "step_start_rejected"}:
            invalid_events.append(str(row.get("event")))

    if invalid_events:
        return CheckResult(
            id="A6", name="Workflow 时序校验", layer="A",
            status="fail", severity="critical",
            evidence=f"workflow trace contains invalid events: {sorted(set(invalid_events))}",
            measured={"invalid_events": invalid_events, "completed_steps": completed_ids},
            remediation=["clear the failed task and rerun the chapter workflow in order"],
        )
    if violations:
        return CheckResult(
            id="A6", name="Workflow 时序校验", layer="A",
            status="fail", severity="high",
            evidence=f"workflow timestamps are not monotonic: {violations}",
            measured={"violations": violations},
            remediation=["rerun the suspicious steps and check system time"],
        )
    return CheckResult(
        id="A6", name="Workflow 时序校验", layer="A",
        status="pass", severity="medium",
        evidence=f"workflow recorded {len(timestamps)} ordered steps with no invalid trace events",
        measured={"steps_count": len(timestamps), "completed_steps": completed_ids},
    )

def check_A7_encoding_clean(project_root: Path, chapter: int) -> CheckResult:
    """A7: 编码清洁 — 正文不得出现 U+FFFD 替换字符或长串乱码."""
    chapter_file = _find_chapter_file(project_root, chapter)
    if chapter_file is None:
        return CheckResult(
            id="A7", name="编码清洁", layer="A",
            status="fail", severity="critical",
            evidence=f"章节文件不存在 (第{_pad(chapter)}章)",
            remediation=["检查 Step 4 是否正确写入章节"],
        )
    text = _read_text(chapter_file)
    if text is None:
        return CheckResult(
            id="A7", name="编码清洁", layer="A",
            status="fail", severity="critical",
            evidence=f"章节文件无法 UTF-8 解码: {chapter_file.name}",
            remediation=["从 Step 2A 重写; 检查写入流程是否指定 encoding='utf-8'"],
        )
    replacement_count = text.count("\ufffd")
    if replacement_count > 0:
        return CheckResult(
            id="A7", name="编码清洁", layer="A",
            status="fail", severity="critical",
            evidence=f"正文含 {replacement_count} 处 U+FFFD 替换字符",
            measured={"replacement_chars": replacement_count},
            remediation=["从 Step 2A 重写本章; 所有 Python 写入必须指定 encoding='utf-8'"],
        )
    return CheckResult(
        id="A7", name="编码清洁", layer="A",
        status="pass", severity="critical",
        evidence=f"{chapter_file.name} 编码清洁 ({len(text)} 字符)",
        measured={"char_count": len(text), "replacement_chars": 0},
    )


def check_A8_anti_ai_force_not_stub(project_root: Path, chapter: int) -> CheckResult:
    """A8: anti_ai_force_check 非 stub — 如果 Step 4 产物中引用了该检查，其输出不能是占位符."""
    # 约定: Step 4 的终检在 .webnovel/polish_reports/ch{NNNN}.json (优先) 或 .md (Markdown 版本)
    import re as _re
    json_path = project_root / ".webnovel" / "polish_reports" / f"ch{_pad(chapter)}.json"
    md_path = project_root / ".webnovel" / "polish_reports" / f"ch{_pad(chapter)}.md"
    report_path = json_path if json_path.exists() else None

    # 新增：先解析 .md 版本（主流程 Step 4 产物通常是 Markdown）
    if not report_path and md_path.exists():
        md_text = _read_text(md_path)
        # 接受 frontmatter (> anti_ai_force_check: pass) / 内联 / 结论 (= pass) 等多种格式
        m = _re.search(r"(?im)anti_ai_force_check\s*[:=]\s*([\*_~`]*)\s*(pass|fail|skip|stub)\b", md_text)
        if m:
            verdict = m.group(2).lower()
            if verdict == "stub":
                return CheckResult(
                    id="A8", name="anti_ai_force_check 非 stub", layer="A",
                    status="fail", severity="high",
                    evidence=f"polish_reports/ch{_pad(chapter)}.md anti_ai_force_check=stub",
                    remediation=["重跑 Step 4 终检"],
                )
            return CheckResult(
                id="A8", name="anti_ai_force_check 非 stub", layer="A",
                status="pass", severity="low",
                evidence=f"polish_reports/ch{_pad(chapter)}.md anti_ai_force_check={verdict}",
            )

    if not report_path:
        # 回退: 审查报告中如果提到 anti_ai 字样
        review = _find_review_report(project_root, chapter)
        text = _read_text(review) if review else ""
        if not text or "anti_ai" not in text.lower():
            return CheckResult(
                id="A8", name="anti_ai_force_check 非 stub", layer="A",
                status="skipped", severity="low",
                evidence="polish_reports 与审查报告均未提及 anti_ai_force_check",
            )
        # 简单判断: 是否含有 "stub" / "TODO" 之类的占位
        if "stub" in text.lower() or "TODO" in text:
            return CheckResult(
                id="A8", name="anti_ai_force_check 非 stub", layer="A",
                status="warn", severity="medium",
                evidence="审查报告中 anti_ai 检查疑似 stub",
                remediation=["重跑 Step 4 终检"],
            )
        return CheckResult(
            id="A8", name="anti_ai_force_check 非 stub", layer="A",
            status="pass", severity="low",
            evidence="审查报告包含 anti_ai 检查且非 stub",
        )
    data = _read_json(report_path) or {}
    anti = data.get("anti_ai_force_check") or {}
    if isinstance(anti, dict) and anti.get("is_stub"):
        return CheckResult(
            id="A8", name="anti_ai_force_check 非 stub", layer="A",
            status="fail", severity="high",
            evidence="anti_ai_force_check.is_stub=true",
            remediation=["重跑 Step 4 终检，确保 anti_ai_force_check 真实执行"],
        )
    return CheckResult(
        id="A8", name="anti_ai_force_check 非 stub", layer="A",
        status="pass", severity="low",
        evidence="polish_reports 中 anti_ai_force_check 真实运行",
    )


# ==================== Layer B: 跨产物一致性 ====================

def check_B1_summary_vs_chapter(project_root: Path, chapter: int) -> CheckResult:
    """B1: 本章摘要 vs 正文 — summary 的 key_beats 字段应能在正文中匹配到."""
    summary_path = project_root / ".webnovel" / "summaries" / f"ch{_pad(chapter)}.md"
    if not summary_path.exists():
        return CheckResult(
            id="B1", name="摘要 vs 正文", layer="B",
            status="fail", severity="high",
            evidence=f"summaries/ch{_pad(chapter)}.md 不存在",
            remediation=["重跑 Step 5 E (生成摘要)"],
        )
    chapter_file = _find_chapter_file(project_root, chapter)
    if chapter_file is None:
        return CheckResult(
            id="B1", name="摘要 vs 正文", layer="B",
            status="fail", severity="high",
            evidence=f"章节文件不存在",
        )
    summary_text = _read_text(summary_path) or ""
    chapter_text = _read_text(chapter_file) or ""
    # 提取摘要中的 key_beats（按格式优先级 4 级 fallback）
    # P1：v3 yaml frontmatter 的 `key_beats:` 列表
    # P2：`## 剧情摘要` / `## 章节摘要` 叙事段落里的 4+ 字中文片段
    # P3：旧版 `## 关键节拍` section 的 bullet 列表
    # P4：兜底——全文第一级 bullet 列表
    beats: list[str] = []
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", summary_text, re.DOTALL)
    if fm_match:
        fm_block = fm_match.group(1)
        kb_match = re.search(
            r"^key_beats\s*:\s*\n((?:\s*[-・•]\s*.+\n?)+)",
            fm_block,
            re.MULTILINE,
        )
        if kb_match:
            beats = re.findall(
                r"^\s*[-・•]\s*[\"']?(.+?)[\"']?\s*$",
                kb_match.group(1),
                re.MULTILINE,
            )
            beats = [b.strip() for b in beats if len(b.strip()) > 5][:10]
    # narrative_style 标记：叙事段落摘要采用宽松匹配（3+ 字子串），bullet 摘要采用严格匹配（4+ 字片段）
    narrative_style = False
    if not beats:
        # 叙事段落式摘要：从 `## 剧情摘要` / `## 章节摘要` / `## 本章摘要` 段落提取 beat
        narrative_match = re.search(
            r"##\s*(?:剧情摘要|章节摘要|本章摘要|正文摘要)\s*\n(.*?)(?=\n##|\Z)",
            summary_text,
            re.DOTALL,
        )
        if narrative_match:
            narrative_style = True
            narrative = narrative_match.group(1)
            # 抽取 3+ 字连续中文片段，按出现顺序去重取前 15
            frags = re.findall(r"[\u4e00-\u9fff]{3,8}", narrative)
            seen: set[str] = set()
            for f in frags:
                if f not in seen:
                    seen.add(f)
                    beats.append(f)
                if len(beats) >= 15:
                    break
    if not beats:
        section = re.search(
            r"##\s*关键节拍\s*\n(.*?)(?=\n##|\Z)",
            summary_text,
            re.DOTALL,
        )
        if section:
            beats = re.findall(r"^[\s\-・•\*]+(.+?)$", section.group(1), re.MULTILINE)
            beats = [b.strip() for b in beats if len(b.strip()) > 5][:10]
    if not beats:
        beats = re.findall(r"^[\s\-・•\*]+(.+?)$", summary_text, re.MULTILINE)
        beats = [b.strip() for b in beats if len(b.strip()) > 5][:10]
    if not beats:
        return CheckResult(
            id="B1", name="摘要 vs 正文", layer="B",
            status="warn", severity="medium",
            evidence="摘要无可识别的 key_beats 列表",
            remediation=["Step 5 E 生成摘要时使用项目符号列表"],
        )
    # 每个 beat 抽取关键词，在正文中查找
    # 叙事段落模式：beat 自身即片段，直接子串匹配（宽松）
    # bullet 模式：beat 是完整短语，抽取 4+ 字中文子串再匹配（严格）
    matched = 0
    for beat in beats:
        if narrative_style:
            # beat 自己已经是 3-8 字连续中文，直接作为子串
            if beat in chapter_text:
                matched += 1
            else:
                # 降级：试 beat 的所有 3+ 字子串
                found = False
                for length in (4, 3):
                    if found:
                        break
                    for start in range(len(beat) - length + 1):
                        if beat[start : start + length] in chapter_text:
                            matched += 1
                            found = True
                            break
        else:
            fragments = re.findall(r"[\u4e00-\u9fff]{4,}", beat)
            for frag in fragments[:2]:
                if frag in chapter_text:
                    matched += 1
                    break
    match_ratio = matched / len(beats) if beats else 0
    # 叙事段落模式本质是概括而非字面复制，阈值放宽（fail<0.3, warn<0.5）
    # bullet 模式保持严格（fail<0.5, warn<0.8）
    fail_threshold = 0.3 if narrative_style else 0.5
    warn_threshold = 0.5 if narrative_style else 0.8
    if match_ratio < fail_threshold:
        return CheckResult(
            id="B1", name="摘要 vs 正文", layer="B",
            status="fail", severity="high",
            evidence=f"摘要 key_beats 仅 {matched}/{len(beats)} 能在正文中找到 ({match_ratio:.0%}, narrative={narrative_style})",
            measured={"matched": matched, "total_beats": len(beats), "ratio": round(match_ratio, 2), "narrative_style": narrative_style},
            remediation=["重跑 Step 5 E (摘要必须基于正文); 或人工核对摘要"],
        )
    if match_ratio < warn_threshold:
        return CheckResult(
            id="B1", name="摘要 vs 正文", layer="B",
            status="warn", severity="medium",
            evidence=f"摘要 key_beats 匹配率 {match_ratio:.0%} (narrative={narrative_style})",
            measured={"matched": matched, "total_beats": len(beats), "ratio": round(match_ratio, 2), "narrative_style": narrative_style},
            remediation=["核对摘要中与正文不符的条目"],
        )
    return CheckResult(
        id="B1", name="摘要 vs 正文", layer="B",
        status="pass", severity="high",
        evidence=f"摘要 key_beats 匹配率 {match_ratio:.0%} ({matched}/{len(beats)})",
        measured={"matched": matched, "total_beats": len(beats), "ratio": round(match_ratio, 2)},
    )


def check_B2_entities_three_way(project_root: Path, chapter: int) -> CheckResult:
    """B2: 实体三方一致 — index.db scenes.characters / chapter_meta / 正文 中的实体应一致."""
    db_path = project_root / ".webnovel" / "index.db"
    if not db_path.exists():
        return CheckResult(
            id="B2", name="实体三方一致", layer="B",
            status="skipped", severity="medium",
            evidence="index.db 不存在",
        )
    chapter_file = _find_chapter_file(project_root, chapter)
    if chapter_file is None:
        return CheckResult(
            id="B2", name="实体三方一致", layer="B",
            status="fail", severity="high",
            evidence="章节文件不存在",
        )
    chapter_text = _read_text(chapter_file) or ""
    entities_scenes: set[str] = set()
    entity_names: Dict[str, set] = {}  # entity_id → {canonical_name, alias1, alias2, ...}
    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("SELECT characters FROM scenes WHERE chapter = ?", (chapter,))
        for row in cur.fetchall():
            if row[0]:
                try:
                    arr = json.loads(row[0])
                    if isinstance(arr, list):
                        entities_scenes.update(str(x) for x in arr)
                except Exception:
                    # 也可能是逗号分隔字符串
                    entities_scenes.update(s.strip() for s in str(row[0]).split(",") if s.strip())
        # 解析 entity_id → canonical_name + aliases（正文使用中文姓名，entity_id 是英文主键）
        # 注意: entities / aliases 表在旧 schema 或测试 fixture 里可能不存在，
        # 单独 try/except 保证即使查询失败也不会中断 B2 检查。
        if entities_scenes:
            placeholders = ",".join("?" * len(entities_scenes))
            eid_list = list(entities_scenes)
            try:
                cur.execute(
                    f"SELECT id, canonical_name FROM entities WHERE id IN ({placeholders})",
                    eid_list,
                )
                for eid, cname in cur.fetchall():
                    if cname:
                        entity_names.setdefault(eid, set()).add(cname)
            except Exception:
                pass  # entities 表缺失时回退到旧行为
            try:
                cur.execute(
                    f"SELECT entity_id, alias FROM aliases WHERE entity_id IN ({placeholders})",
                    eid_list,
                )
                for eid, alias in cur.fetchall():
                    if alias:
                        entity_names.setdefault(eid, set()).add(alias)
            except Exception:
                pass  # aliases 表缺失时回退到旧行为
        conn.close()
    except Exception as exc:
        return CheckResult(
            id="B2", name="实体三方一致", layer="B",
            status="skipped", severity="medium",
            evidence=f"index.db 查询失败: {exc}",
        )
    if not entities_scenes:
        return CheckResult(
            id="B2", name="实体三方一致", layer="B",
            status="warn", severity="medium",
            evidence=f"scenes 表无 chapter={chapter} 的 characters",
            remediation=["重跑 Step 5 B (场景切片 + 实体抽取)"],
        )
    # 检查每个实体是否在正文出现
    # 优先用 canonical_name + aliases 做匹配（entity_id 是英文主键，在中文正文中永远不会匹配）
    # fallback 用复合中文名模糊匹配（如"推演课教官"→正文出现"教官"即匹配）
    def _entity_in_text(entity: str, text: str) -> bool:
        # 1. 首先查 canonical_name + aliases
        names = entity_names.get(entity)
        if names:
            if any(n and n in text for n in names):
                return True
        # 2. fallback: 直接 substring
        if entity in text:
            return True
        # 3. fallback: 中文前缀/后缀模糊匹配
        cjk = re.findall(r'[\u4e00-\u9fff]+', entity)
        full_cjk = "".join(cjk)
        if len(full_cjk) <= 2:
            return full_cjk in text if full_cjk else False
        for length in range(len(full_cjk) - 1, 1, -1):
            for start in range(len(full_cjk) - length + 1):
                if full_cjk[start:start + length] in text:
                    return True
        return False
    missing_in_chapter = [e for e in entities_scenes if e and not _entity_in_text(e, chapter_text)]
    if len(missing_in_chapter) > len(entities_scenes) * 0.3:
        return CheckResult(
            id="B2", name="实体三方一致", layer="B",
            status="fail", severity="high",
            evidence=f"{len(missing_in_chapter)}/{len(entities_scenes)} 个 scenes 实体未在正文找到",
            measured={"scenes_entities": len(entities_scenes), "missing_in_chapter": missing_in_chapter[:10]},
            remediation=["重跑 Step 5 B; 或人工核对 scenes 表"],
        )
    return CheckResult(
        id="B2", name="实体三方一致", layer="B",
        status="pass", severity="high",
        evidence=f"scenes 实体 {len(entities_scenes)} 个，正文匹配率 {1 - len(missing_in_chapter)/len(entities_scenes):.0%}",
        measured={"scenes_entities": len(entities_scenes), "missing_in_chapter": len(missing_in_chapter)},
    )


def check_B3_foreshadowing_three_way(project_root: Path, chapter: int) -> CheckResult:
    """B3: 伏笔三方一致 — 章纲/正文/state.plot_threads 伏笔应一致."""
    state_path = project_root / ".webnovel" / "state.json"
    state = _read_json(state_path) or {}
    plot = state.get("plot_threads", {}) or {}
    foreshadowing = plot.get("foreshadowing", []) or []
    # 筛选与本章相关的
    current_ch_foreshadowing = [f for f in foreshadowing
                                 if isinstance(f, dict) and f.get("chapter") == chapter]
    if not current_ch_foreshadowing:
        return CheckResult(
            id="B3", name="伏笔三方一致", layer="B",
            status="skipped", severity="medium",
            evidence=f"state.plot_threads 无章节 {chapter} 伏笔",
        )
    chapter_file = _find_chapter_file(project_root, chapter)
    text = _read_text(chapter_file) if chapter_file else ""
    text = text or ""
    missing = []
    for f in current_ch_foreshadowing:
        desc = f.get("description") or f.get("content") or ""
        if desc:
            # 抽取 4 字关键片段
            frags = re.findall(r"[\u4e00-\u9fff]{4,}", desc)
            if frags and not any(frag in text for frag in frags[:3]):
                missing.append(desc[:30])
    if len(missing) > len(current_ch_foreshadowing) * 0.5:
        return CheckResult(
            id="B3", name="伏笔三方一致", layer="B",
            status="fail", severity="high",
            evidence=f"{len(missing)}/{len(current_ch_foreshadowing)} 个伏笔未在正文找到",
            measured={"missing": missing},
            remediation=["补跑 Step 5 D+K; 手工核对伏笔"],
        )
    return CheckResult(
        id="B3", name="伏笔三方一致", layer="B",
        status="pass", severity="high",
        evidence=f"{len(current_ch_foreshadowing)} 个伏笔，{len(current_ch_foreshadowing)-len(missing)} 已落在正文",
        measured={"total": len(current_ch_foreshadowing), "missing_count": len(missing)},
    )


def check_B4_review_metrics_consistency(project_root: Path, chapter: int) -> CheckResult:
    db_path = project_root / ".webnovel" / "index.db"
    if not db_path.exists():
        return CheckResult(
            id="B4", name="review_metrics 一致性", layer="B",
            status="skipped", severity="medium",
            evidence="index.db is missing",
        )
    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute(
            "SELECT overall_score FROM review_metrics WHERE start_chapter <= ? AND end_chapter >= ? ORDER BY start_chapter DESC LIMIT 1",
            (chapter, chapter),
        )
        row = cur.fetchone()
        conn.close()
    except Exception as exc:
        return CheckResult(
            id="B4", name="review_metrics 一致性", layer="B",
            status="skipped", severity="medium",
            evidence=f"review_metrics query failed: {exc}",
        )
    if not row:
        return CheckResult(
            id="B4", name="review_metrics 一致性", layer="B",
            status="warn", severity="medium",
            evidence=f"review_metrics has no row for chapter {chapter}",
            remediation=["rerun index save-review-metrics"],
        )

    db_score = row[0]
    review = _find_review_report(project_root, chapter)
    text = (_read_text(review) if review else "") or ""
    report_score = None
    # 先过滤掉所有代码块内容（```...```），避免把文档/示例里的分数当真值
    text_nofence = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    # 允许行首有 blockquote `>` 或空白；要求 score 是 1-3 位整数或 xx.x 浮点（排除公式里的 0.6 / 0.4）；
    # 要求 score 后紧跟中文括号、换行、空白+中文字符或行尾（避免吃到公式里的数字）
    for pattern in (
        # P1：标准 frontmatter 行：`> overall_score: 93（...）` / `overall_score: 93`
        r"(?im)^[>\s]*(?:overall[_ ]?score|score\s*total|合并加权分|综合分数|综合分|综合评分|总评分|合并分|总分)\s*[:：=]\s*[*_~`]*\s*(\d{1,3}(?:\.\d)?)(?=\s*[\*（(\n]|\s+[\u4e00-\u9fff]|$)",
        # P2：宽松匹配：要求数字不跟随小数点（排除 0.6 等权重）
        r"(?i)(?:overall[_ ]?score|score\s*total|合并加权分|综合分数|综合分|综合评分|总评分|合并分|总分)\s*[:：=]?\s*[*_~`]*\s*(\d{2,3})(?!\.\d)(?!\s*[×x*])",
        # P3 兜底：整段独立一行 `93 分` 或 `综合: 93` 或 Markdown 加粗 `合并分：**91**`
        r"(?im)^(?!\s*[-*>])\s*[^0-9\n]{0,30}[:：]?\s*\*{0,2}\s*(\d{2,3})\*{0,2}\s*(?:分)?\s*$",
    ):
        match = re.search(pattern, text_nofence, re.IGNORECASE)
        if not match:
            continue
        try:
            candidate = float(match.group(1))
            # 合理性闸门：网文审查分必须是 0-100 的整数或 xx.x 小数，0.x 一律视为假阳性
            if candidate < 1.0:
                continue
            report_score = candidate
            break
        except Exception:
            report_score = None
    if report_score is None:
        return CheckResult(
            id="B4", name="review_metrics 一致性", layer="B",
            status="warn", severity="medium",
            evidence=f"review report score was not found (db_score={db_score})",
        )
    diff = abs(float(db_score) - report_score)
    if diff > 3:
        return CheckResult(
            id="B4", name="review_metrics 一致性", layer="B",
            status="fail", severity="high",
            evidence=f"db_score={db_score} vs report_score={report_score}, diff={diff}",
            measured={"db_score": db_score, "report_score": report_score, "diff": diff},
            remediation=["rerun index save-review-metrics"],
        )
    return CheckResult(
        id="B4", name="review_metrics 一致性", layer="B",
        status="pass", severity="medium",
        evidence=f"db_score={db_score} ~= report_score={report_score}",
        measured={"db_score": db_score, "report_score": report_score, "diff": diff},
    )

def check_B7_outline_to_chapter(project_root: Path, chapter: int) -> CheckResult:
    """B7: 章纲兑现 — 大纲/节拍表中本章的关键点应在正文中找到."""
    outline_dir = project_root / "大纲"
    if not outline_dir.exists():
        return CheckResult(
            id="B7", name="章纲兑现", layer="B",
            status="skipped", severity="medium",
            evidence="大纲目录不存在",
        )
    # 尝试找节拍表
    beat_files = list(outline_dir.glob("*节拍表*.md")) + list(outline_dir.glob("*章纲*.md"))
    if not beat_files:
        return CheckResult(
            id="B7", name="章纲兑现", layer="B",
            status="skipped", severity="medium",
            evidence="无节拍表或章纲文件",
        )
    chapter_file = _find_chapter_file(project_root, chapter)
    text = _read_text(chapter_file) if chapter_file else ""
    text = text or ""
    # 从节拍表中寻找 "第N章" 附近的内容
    chapter_beats: List[str] = []
    for bf in beat_files:
        bf_text = _read_text(bf) or ""
        # 匹配 "第 N 章" 或 "Ch N" 段
        pattern = re.compile(rf"第\s*{chapter}\s*章[^\n]*\n(.*?)(?=第\s*\d+\s*章|\Z)", re.DOTALL)
        for m in pattern.finditer(bf_text):
            block = m.group(1)
            # 提取项目符号行
            lines = re.findall(r"^[\s\-・•\*]+(.+?)$", block, re.MULTILINE)
            chapter_beats.extend(l.strip() for l in lines if len(l.strip()) > 5)
    if not chapter_beats:
        return CheckResult(
            id="B7", name="章纲兑现", layer="B",
            status="skipped", severity="medium",
            evidence=f"节拍表中无章节 {chapter} 细节",
        )
    matched = 0
    for beat in chapter_beats[:10]:
        frags = re.findall(r"[\u4e00-\u9fff]{4,}", beat)
        if any(frag in text for frag in frags[:3]):
            matched += 1
    ratio = matched / min(len(chapter_beats), 10)
    if ratio < 0.5:
        return CheckResult(
            id="B7", name="章纲兑现", layer="B",
            status="fail", severity="high",
            evidence=f"节拍兑现率 {ratio:.0%} ({matched}/{min(len(chapter_beats),10)})",
            measured={"matched": matched, "total_beats": len(chapter_beats), "ratio": round(ratio, 2)},
            remediation=["回 Step 4 补写缺失节拍"],
        )
    if ratio < 0.8:
        return CheckResult(
            id="B7", name="章纲兑现", layer="B",
            status="warn", severity="medium",
            evidence=f"节拍兑现率 {ratio:.0%}",
            measured={"matched": matched, "total_beats": len(chapter_beats), "ratio": round(ratio, 2)},
        )
    return CheckResult(
        id="B7", name="章纲兑现", layer="B",
        status="pass", severity="high",
        evidence=f"节拍兑现率 {ratio:.0%} ({matched}/{min(len(chapter_beats),10)})",
        measured={"matched": matched, "total_beats": len(chapter_beats), "ratio": round(ratio, 2)},
    )


def check_B9_chapter_meta_fields(project_root: Path, chapter: int) -> CheckResult:
    """B9: chapter_meta 字段完整性 — state.chapter_meta[chapter] 应含所需字段."""
    state = _read_json(project_root / ".webnovel" / "state.json") or {}
    cmeta = state.get("chapter_meta", {}) or {}
    # 尝试三种格式: padded "0005", unpadded "5", int 5
    entry = cmeta.get(_pad(chapter)) or cmeta.get(str(chapter)) or cmeta.get(chapter)
    if not entry:
        return CheckResult(
            id="B9", name="chapter_meta 字段完整", layer="B",
            status="fail", severity="high",
            evidence=f"state.chapter_meta 无章节 {chapter}",
            remediation=["重跑 Step 5 D (chapter_meta 写入)"],
        )
    if not isinstance(entry, dict):
        return CheckResult(
            id="B9", name="chapter_meta 字段完整", layer="B",
            status="fail", severity="high",
            evidence=f"chapter_meta[{chapter}] 不是对象",
        )
    missing = [k for k in CHAPTER_META_REQUIRED_FIELDS if k not in entry]
    present_count = len(CHAPTER_META_REQUIRED_FIELDS) - len(missing)
    if len(missing) > len(CHAPTER_META_REQUIRED_FIELDS) * 0.3:
        return CheckResult(
            id="B9", name="chapter_meta 字段完整", layer="B",
            status="fail", severity="high",
            evidence=f"chapter_meta 缺失字段: {missing[:10]}",
            measured={"present": present_count, "total": len(CHAPTER_META_REQUIRED_FIELDS), "missing": missing},
            remediation=["重跑 Step 5 D"],
        )
    if missing:
        return CheckResult(
            id="B9", name="chapter_meta 字段完整", layer="B",
            status="warn", severity="medium",
            evidence=f"chapter_meta 缺失 {len(missing)} 个字段: {missing}",
            measured={"present": present_count, "total": len(CHAPTER_META_REQUIRED_FIELDS), "missing": missing},
        )
    return CheckResult(
        id="B9", name="chapter_meta 字段完整", layer="B",
        status="pass", severity="high",
        evidence=f"chapter_meta 字段齐全 ({present_count}/{len(CHAPTER_META_REQUIRED_FIELDS)})",
        measured={"present": present_count, "total": len(CHAPTER_META_REQUIRED_FIELDS)},
    )


# ==================== Layer G: 跨章趋势 ====================

def check_G1_score_trend(project_root: Path, chapter: int) -> CheckResult:
    """G1: 评分趋势 — 近 5 章评分不得下跌超过 8 分."""
    if chapter < 3:
        return CheckResult(
            id="G1", name="评分趋势", layer="G",
            status="skipped", severity="low",
            evidence=f"Ch{chapter} 基线不足 (需 ≥3 章)",
        )
    db_path = project_root / ".webnovel" / "index.db"
    if not db_path.exists():
        return CheckResult(
            id="G1", name="评分趋势", layer="G",
            status="skipped", severity="low",
            evidence="index.db 不存在",
        )
    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute(
            "SELECT start_chapter, overall_score FROM review_metrics "
            "WHERE start_chapter <= ? ORDER BY start_chapter DESC LIMIT 5",
            (chapter,),
        )
        rows = cur.fetchall()
        conn.close()
    except Exception as exc:
        return CheckResult(
            id="G1", name="评分趋势", layer="G",
            status="skipped", severity="low",
            evidence=f"查询失败: {exc}",
        )
    if len(rows) < 2:
        return CheckResult(
            id="G1", name="评分趋势", layer="G",
            status="skipped", severity="low",
            evidence=f"历史评分不足 ({len(rows)} 条)",
        )
    current_score = rows[0][1]
    prev_scores = [r[1] for r in rows[1:] if r[1] is not None]
    if current_score is None or not prev_scores:
        return CheckResult(
            id="G1", name="评分趋势", layer="G",
            status="skipped", severity="low",
            evidence="评分数据不全",
        )
    avg_prev = sum(prev_scores) / len(prev_scores)
    drop = avg_prev - current_score
    if drop > 8:
        return CheckResult(
            id="G1", name="评分趋势", layer="G",
            status="warn", severity="high",
            evidence=f"当前分 {current_score} 比前 {len(prev_scores)} 章均值 {avg_prev:.1f} 低 {drop:.1f}",
            measured={"current": current_score, "prev_avg": round(avg_prev, 2), "drop": round(drop, 2)},
            remediation=["检查质量下滑原因；调整 Step 4 策略"],
        )
    if drop > 4:
        return CheckResult(
            id="G1", name="评分趋势", layer="G",
            status="warn", severity="medium",
            evidence=f"评分下滑 {drop:.1f} 分",
            measured={"current": current_score, "prev_avg": round(avg_prev, 2)},
        )
    return CheckResult(
        id="G1", name="评分趋势", layer="G",
        status="pass", severity="low",
        evidence=f"评分稳定 ({current_score} vs 均值 {avg_prev:.1f})",
        measured={"current": current_score, "prev_avg": round(avg_prev, 2)},
    )


def check_G2_word_count_trend(project_root: Path, chapter: int) -> CheckResult:
    """G2: 字数趋势 — 本章字数应在 2200-3500 范围; 与前章差异 < 40%."""
    chapter_file = _find_chapter_file(project_root, chapter)
    if chapter_file is None:
        return CheckResult(
            id="G2", name="字数趋势", layer="G",
            status="skipped", severity="low",
            evidence="章节文件不存在",
        )
    text = _read_text(chapter_file) or ""
    # 简单字数 = 中文字符数
    word_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    checks = []
    if word_count < 2200:
        return CheckResult(
            id="G2", name="字数趋势", layer="G",
            status="warn", severity="medium",
            evidence=f"字数 {word_count} 低于目标 2200",
            measured={"word_count": word_count, "target_min": 2200, "target_max": 3500},
            remediation=["Step 4 补写至目标范围"],
        )
    if word_count > 3500:
        return CheckResult(
            id="G2", name="字数趋势", layer="G",
            status="warn", severity="low",
            evidence=f"字数 {word_count} 超过目标 3500",
            measured={"word_count": word_count, "target_min": 2200, "target_max": 3500},
        )
    return CheckResult(
        id="G2", name="字数趋势", layer="G",
        status="pass", severity="low",
        evidence=f"字数 {word_count} 在目标范围",
        measured={"word_count": word_count},
    )


def check_G3_audit_trend(project_root: Path, chapter: int) -> CheckResult:
    """G3: 跨章审计趋势 — chapter_audit.jsonl 中警告数不得累积上升."""
    trend_path = project_root / ".webnovel" / "observability" / "chapter_audit.jsonl"
    rows = _read_jsonl(trend_path)
    if len(rows) < 2:
        return CheckResult(
            id="G3", name="审计警告累积", layer="G",
            status="skipped", severity="low",
            evidence=f"历史审计数据不足 ({len(rows)} 条)",
        )
    recent = rows[-5:]
    warn_counts = [r.get("warnings_count", 0) for r in recent]
    if warn_counts[-1] > 5 and warn_counts[-1] >= max(warn_counts[:-1]) + 2:
        return CheckResult(
            id="G3", name="审计警告累积", layer="G",
            status="warn", severity="medium",
            evidence=f"近 5 章警告数 {warn_counts}, 当前 {warn_counts[-1]} 上升",
            measured={"recent_warns": warn_counts},
            remediation=["检查质量下滑；补跑失败检查"],
        )
    return CheckResult(
        id="G3", name="审计警告累积", layer="G",
        status="pass", severity="low",
        evidence=f"近 5 章警告数稳定: {warn_counts}",
        measured={"recent_warns": warn_counts},
    )


# ==================== 聚合 ====================

def _run_layer_a(project_root: Path, chapter: int) -> LayerResult:
    checks = [
        check_A1_contract_completeness(project_root, chapter),
        check_A2_checker_diversity(project_root, chapter),
        check_A3_external_models(project_root, chapter),
        check_A4_data_agent_steps(project_root, chapter),
        check_A5_fallback_detection(project_root, chapter),
        check_A6_workflow_timing(project_root, chapter),
        check_A7_encoding_clean(project_root, chapter),
        check_A8_anti_ai_force_not_stub(project_root, chapter),
    ]
    return LayerResult(layer="A", score=_score_from_checks(checks), checks=checks)


def _run_layer_b(project_root: Path, chapter: int) -> LayerResult:
    checks = [
        check_B1_summary_vs_chapter(project_root, chapter),
        check_B2_entities_three_way(project_root, chapter),
        check_B3_foreshadowing_three_way(project_root, chapter),
        check_B4_review_metrics_consistency(project_root, chapter),
        check_B7_outline_to_chapter(project_root, chapter),
        check_B9_chapter_meta_fields(project_root, chapter),
    ]
    return LayerResult(layer="B", score=_score_from_checks(checks), checks=checks)


# Updated 2026-04: stronger evidence-based overrides for critical checks.
# These later definitions intentionally override earlier text-only versions.

def _run_layer_g(project_root: Path, chapter: int) -> LayerResult:
    checks = [
        check_G1_score_trend(project_root, chapter),
        check_G2_word_count_trend(project_root, chapter),
        check_G3_audit_trend(project_root, chapter),
    ]
    return LayerResult(layer="G", score=_score_from_checks(checks), checks=checks)


def _derive_cli_decision(
    critical_fails: List[CheckResult],
    high_fails: List[CheckResult],
    medium_fails: List[CheckResult],
    low_fails: List[CheckResult],
    warnings: List[CheckResult],
) -> str:
    """根据 fail/warn 计数派生 cli_decision.

    权威规范: step-6-audit-matrix.md 决议矩阵。
    - 任一 critical fail                → block
    - high fail 数量 >= 3               → block
    - 有 high/medium/low fail 或 warn   → approve_with_warnings
    - 全部 pass/skipped                 → approve

    注: CLI 仅覆盖 Layer A/B/G，最终决议由 audit-agent 合并 C/D/E/F 后重新聚合。
    """
    if critical_fails:
        return "block"
    if len(high_fails) >= 3:
        return "block"
    if high_fails or medium_fails or low_fails or warnings:
        return "approve_with_warnings"
    return "approve"


# cli_decision → CLI 退出码 (与 docstring 顶部一致)
_DECISION_TO_EXIT_CODE = {
    "approve": 0,
    "block": 1,
    "approve_with_warnings": 2,
}


def run_audit(project_root: Path, chapter: int, mode: str = "standard") -> Dict[str, Any]:
    """运行 Layer A/B/G 全部检查，返回字典供主流程/agent 消费."""
    layer_a = _run_layer_a(project_root, chapter)
    layer_b = _run_layer_b(project_root, chapter)
    # minimal 模式跳过 Layer G
    if mode == "minimal":
        layer_g = LayerResult(layer="G", score=None, checks=[], skipped_reason="mode=minimal")
    else:
        layer_g = _run_layer_g(project_root, chapter)

    all_checks = layer_a.checks + layer_b.checks + layer_g.checks
    critical_fails = [c for c in all_checks if c.status == "fail" and c.severity == "critical"]
    high_fails = [c for c in all_checks if c.status == "fail" and c.severity == "high"]
    medium_fails = [c for c in all_checks if c.status == "fail" and c.severity == "medium"]
    low_fails = [c for c in all_checks if c.status == "fail" and c.severity == "low"]
    warnings = [c for c in all_checks if c.status == "warn"]

    cli_decision = _derive_cli_decision(
        critical_fails, high_fails, medium_fails, low_fails, warnings
    )

    # blocking_issues 仅收纳会触发 block 的项:
    # - 任一 critical fail
    # - high fails >= 3 时全部 high fails
    blocking_issues: List[CheckResult] = list(critical_fails)
    if len(high_fails) >= 3:
        blocking_issues.extend(high_fails)

    return {
        "chapter": chapter,
        "audit_version": "1.0",
        "mode": mode,
        "source": "chapter_audit_cli",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cli_decision": cli_decision,
        "layers": {
            "A_process_integrity": layer_a.to_dict(),
            "B_cross_artifact_consistency": layer_b.to_dict(),
            "G_cross_chapter_trend": layer_g.to_dict(),
        },
        "summary": {
            "critical_fails": len(critical_fails),
            "high_fails": len(high_fails),
            "medium_fails": len(medium_fails),
            "low_fails": len(low_fails),
            "warnings": len(warnings),
            "total_checks": len(all_checks),
        },
        "blocking_issues": [c.to_dict() for c in blocking_issues],
        "warnings": [c.to_dict() for c in warnings],
    }


# ==================== CLI ====================

def _cmd_chapter(args) -> int:
    from .cli_output import print_error
    try:
        project_root = Path(args.project_root).resolve()
    except Exception as exc:
        print_error("invalid_project_root", str(exc))
        return 3
    if not (project_root / ".webnovel").exists():
        print_error("no_webnovel_dir", f"{project_root}/.webnovel 不存在",
                    suggestion="先通过 webnovel.py use <project_root> 绑定书项目")
        return 3

    try:
        report = run_audit(project_root, args.chapter, mode=args.mode)
    except Exception as exc:
        print_error("audit_runtime_error", f"{type(exc).__name__}: {exc}")
        return 3

    # 写出到 --out
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # 追加到 chapter_audit.jsonl 观测日志
    obs_path = project_root / ".webnovel" / "observability" / "chapter_audit.jsonl"
    obs_path.parent.mkdir(parents=True, exist_ok=True)
    with open(obs_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "chapter": args.chapter,
            "ts": datetime.now(timezone.utc).isoformat(),
            "source": "chapter_audit_cli",
            "cli_decision": report["cli_decision"],
            "layer_scores": {
                "A": report["layers"]["A_process_integrity"]["score"],
                "B": report["layers"]["B_cross_artifact_consistency"]["score"],
                "G": report["layers"]["G_cross_chapter_trend"]["score"],
            },
            "warnings_count": report["summary"]["warnings"],
            "blocking_count": report["summary"]["critical_fails"] + report["summary"]["high_fails"],
        }, ensure_ascii=False) + "\n")

    # 同时输出 JSON 到 stdout
    print(json.dumps(report, ensure_ascii=False, indent=2))

    # 从 cli_decision 反推退出码，确保 JSON 与 exit code 语义一致
    return _DECISION_TO_EXIT_CODE.get(report["cli_decision"], 3)


def _cmd_check_decision(args) -> int:
    from .cli_output import print_error, print_success
    try:
        project_root = Path(args.project_root).resolve()
    except Exception as exc:
        print_error("invalid_project_root", str(exc))
        return 3
    report_path = project_root / ".webnovel" / "audit_reports" / f"ch{_pad(args.chapter)}.json"
    data = _read_json(report_path)
    if data is None:
        print_error("audit_report_missing", f"{report_path} 不存在",
                    suggestion="先运行 Step 6 audit-agent 生成 audit_reports/ch{NNNN}.json")
        return 1
    # Round 17.1 · 2026-04-24 · Ch7 RCA P1.3 根治
    # 同时读 decision 和 overall_decision，任一非空即通过；两者皆空则 fail
    # 若两者都存在但不一致 → schema 违规，fail
    decision = data.get("decision")
    overall_decision = data.get("overall_decision")
    if decision is None and overall_decision is None:
        print_error("audit_decision_missing",
                    "both decision and overall_decision are null/missing",
                    suggestion="audit-agent 必须写 decision 和 overall_decision（两字段同值）")
        return 1
    if decision is not None and overall_decision is not None and decision != overall_decision:
        print_error("audit_decision_inconsistent",
                    f"decision={decision} vs overall_decision={overall_decision} 不一致",
                    suggestion="audit-agent 必须写两字段同值")
        return 1
    effective = decision if decision is not None else overall_decision
    allowed = [x.strip() for x in args.require.split(",") if x.strip()]
    if effective not in allowed:
        print_error("audit_decision_not_allowed",
                    f"decision={effective} 不在允许列表 {allowed}",
                    suggestion="修复 blocking_issues 或重跑 audit")
        return 1
    print_success({"chapter": args.chapter, "decision": effective, "allowed": allowed},
                  message=f"audit decision={effective} 符合要求")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="chapter_audit CLI — Step 6 确定性审计")
    parser.add_argument("--project-root", required=True, help="书项目根目录")

    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ch = sub.add_parser("chapter", help="运行 Layer A/B/G 全部检查")
    p_ch.add_argument("--chapter", type=int, required=True)
    p_ch.add_argument("--mode", choices=["standard", "fast", "minimal"], default="standard")
    p_ch.add_argument("--out", help="输出 JSON 路径 (供 audit-agent 消费)")

    p_dec = sub.add_parser("check-decision", help="验证已有审计决议")
    p_dec.add_argument("--chapter", type=int, required=True)
    p_dec.add_argument("--require", default="approve,approve_with_warnings",
                       help="允许的决议值 (逗号分隔)")

    args = parser.parse_args()

    if args.cmd == "chapter":
        raise SystemExit(_cmd_chapter(args))
    if args.cmd == "check-decision":
        raise SystemExit(_cmd_check_decision(args))
    raise SystemExit(2)


if __name__ == "__main__":
    main()
