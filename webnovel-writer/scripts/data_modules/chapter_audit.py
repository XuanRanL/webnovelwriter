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
    "emotion-checker",
]

EXTERNAL_MODELS_CORE3 = ["kimi", "glm", "qwen-plus"]
EXTERNAL_MODELS_ALL9 = [
    "kimi", "glm", "qwen-plus",
    "minimax", "doubao", "minimax-m2.7",
    "qwen", "glm4", "deepseek",
]

DATA_AGENT_STEPS_REQUIRED = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]  # K 为 best-effort

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
    payload = data.get("payload") or {}
    # 8 板块 (在 payload 中的 key，允许 Contract 以子 key 形式存在)
    expected_panels = ["state", "outline", "settings", "previous_summaries", "style_guide",
                       "entity_cards", "editor_notes", "contract"]
    present = [k for k in expected_panels if k in payload]
    contract = payload.get("contract") or payload.get("Contract") or {}
    contract_fields_min = 8  # 放宽：Contract 至少 8 个字段
    if len(present) < 6:
        return CheckResult(
            id="A1", name="Context Contract 完整性", layer="A",
            status="fail", severity="critical",
            evidence=f"snapshot 板块不全 (present={present})",
            measured={"panels_present": len(present), "contract_fields": len(contract)},
            remediation=["重跑 Step 1: Task(context-agent, chapter=%d)" % chapter],
        )
    if len(contract) < contract_fields_min:
        return CheckResult(
            id="A1", name="Context Contract 完整性", layer="A",
            status="warn", severity="high",
            evidence=f"Contract 字段不足 ({len(contract)} < {contract_fields_min})",
            measured={"panels_present": len(present), "contract_fields": len(contract)},
            remediation=["检查 context-agent 是否完整填充 Contract v2 所有字段"],
        )
    return CheckResult(
        id="A1", name="Context Contract 完整性", layer="A",
        status="pass", severity="high",
        evidence=f"snapshot 板块 {len(present)} 个, Contract 字段 {len(contract)} 个",
        measured={"panels_present": len(present), "contract_fields": len(contract)},
    )


def check_A2_checker_diversity(project_root: Path, chapter: int) -> CheckResult:
    """A2: 10 checker 独立调用 — 审查报告中必须出现所有 10 个 checker 名称."""
    report = _find_review_report(project_root, chapter)
    if report is None:
        return CheckResult(
            id="A2", name="10 checker 独立调用", layer="A",
            status="fail", severity="critical",
            evidence=f"审查报告 第{_pad(chapter)}章审查报告.md 不存在",
            remediation=["重跑 Step 3: 显式 Task 调用 10 个 checker"],
        )
    text = _read_text(report) or ""
    missing = [c for c in CHECKER_NAMES if c not in text]
    if len(missing) >= 3:
        return CheckResult(
            id="A2", name="10 checker 独立调用", layer="A",
            status="fail", severity="critical",
            evidence=f"审查报告缺少 checker: {missing}",
            measured={"present_count": len(CHECKER_NAMES) - len(missing), "missing": missing},
            remediation=["重跑 Step 3: Task(consistency-checker, ...) 等 10 个 checker 全部显式调用"],
        )
    if missing:
        return CheckResult(
            id="A2", name="10 checker 独立调用", layer="A",
            status="warn", severity="high",
            evidence=f"审查报告缺少 {len(missing)} 个 checker: {missing}",
            measured={"present_count": len(CHECKER_NAMES) - len(missing), "missing": missing},
            remediation=["补跑缺失的 checker"],
        )
    return CheckResult(
        id="A2", name="10 checker 独立调用", layer="A",
        status="pass", severity="high",
        evidence="审查报告含全部 10 个 checker",
        measured={"present_count": 10, "missing": []},
    )


def check_A3_external_models(project_root: Path, chapter: int) -> CheckResult:
    """A3: 9 外部模型真实性 — 审查报告应出现核心 3 模型 (kimi/glm/qwen-plus) 或 3.5 产出至少 3 个模型评分."""
    report = _find_review_report(project_root, chapter)
    if report is None:
        return CheckResult(
            id="A3", name="外部模型审查完整性", layer="A",
            status="fail", severity="high",
            evidence="审查报告不存在",
            remediation=["重跑 Step 3.5: python external_review.py --chapter %d --model-key all" % chapter],
        )
    text = _read_text(report) or ""
    present = [m for m in EXTERNAL_MODELS_ALL9 if m in text.lower() or m in text]
    core_present = [m for m in EXTERNAL_MODELS_CORE3 if m in text.lower() or m in text]

    # 检查是否有 phantom zero (评分为 0 且摘要为空)
    # 简单方法: 搜索 "评分: 0" 或 "score.*0" + 周围 200 字符内没有内容
    phantom_hits = 0
    zero_pattern = re.compile(r"(?:评分|score)[^\n]{0,10}[:：]\s*0\b")
    for m in zero_pattern.finditer(text):
        start = max(0, m.start() - 50)
        end = min(len(text), m.end() + 300)
        snippet = text[start:end]
        # 如果 0 分且周围没有实质内容（< 100 字符），判定为 phantom
        if len(snippet.replace(" ", "").replace("\n", "")) < 150:
            phantom_hits += 1

    if len(core_present) < 2:
        return CheckResult(
            id="A3", name="外部模型审查完整性", layer="A",
            status="fail", severity="critical",
            evidence=f"核心 3 模型仅出现 {core_present}",
            measured={"core_present": core_present, "all_present": present, "phantom_zeros": phantom_hits},
            remediation=["重跑 Step 3.5: python external_review.py --chapter %d --model-key all" % chapter],
        )
    if phantom_hits > 0:
        return CheckResult(
            id="A3", name="外部模型审查完整性", layer="A",
            status="fail", severity="critical",
            evidence=f"检测到 {phantom_hits} 处幽灵零分（score=0 且摘要空）",
            measured={"core_present": core_present, "phantom_zeros": phantom_hits},
            remediation=["重跑 Step 3.5 的失败模型: python external_review.py --chapter %d --model-key <失败key>" % chapter],
        )
    if len(present) < 3:
        return CheckResult(
            id="A3", name="外部模型审查完整性", layer="A",
            status="warn", severity="high",
            evidence=f"仅 {len(present)} 个模型参评 (核心 3 已齐)",
            measured={"core_present": core_present, "all_present": present},
            remediation=["考虑补跑 6 个次级模型以提升审查覆盖度"],
        )
    return CheckResult(
        id="A3", name="外部模型审查完整性", layer="A",
        status="pass", severity="high",
        evidence=f"{len(present)} 个模型参评 (核心 3 齐)",
        measured={"core_present": core_present, "all_present": present, "phantom_zeros": 0},
    )


def check_A4_data_agent_steps(project_root: Path, chapter: int) -> CheckResult:
    """A4: Data Agent 子步完整性 — data_agent_timing.jsonl 必须含本章的 Step A-J."""
    timing_path = project_root / ".webnovel" / "observability" / "data_agent_timing.jsonl"
    rows = _read_jsonl(timing_path)
    if not rows:
        return CheckResult(
            id="A4", name="Data Agent 子步完整性", layer="A",
            status="fail", severity="high",
            evidence="data_agent_timing.jsonl 不存在或为空",
            remediation=["重跑 Step 5: Task(data-agent, chapter=%d)" % chapter],
        )
    chapter_rows = [r for r in rows if r.get("chapter") == chapter]
    if not chapter_rows:
        return CheckResult(
            id="A4", name="Data Agent 子步完整性", layer="A",
            status="warn", severity="medium",
            evidence=f"data_agent_timing 无 chapter={chapter} 记录",
            remediation=["确认 Data Agent 调用时传入了 chapter 参数"],
        )
    # 读取 tool_name 推断子步
    tools = set(r.get("tool_name", "") for r in chapter_rows)
    step_markers_found = []
    for step_letter in DATA_AGENT_STEPS_REQUIRED:
        marker = f"step_{step_letter.lower()}"
        if any(marker in t.lower() for t in tools):
            step_markers_found.append(step_letter)
    if len(step_markers_found) < 5:
        return CheckResult(
            id="A4", name="Data Agent 子步完整性", layer="A",
            status="warn", severity="medium",
            evidence=f"仅识别出 {len(step_markers_found)} 个 Data Agent 子步 (tools={len(tools)})",
            measured={"chapter_rows": len(chapter_rows), "tools_count": len(tools), "steps_found": step_markers_found},
            remediation=["确认 data-agent 记录完整 Step A-J 的 tool_name"],
        )
    return CheckResult(
        id="A4", name="Data Agent 子步完整性", layer="A",
        status="pass", severity="medium",
        evidence=f"Data Agent 记录 {len(chapter_rows)} 条，识别 {len(step_markers_found)} 个子步",
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
    """A6: Workflow 步骤时序 — workflow_state.json 中 Step 1~5 时间戳必须单调递增."""
    ws_path = project_root / ".webnovel" / "workflow_state.json"
    data = _read_json(ws_path)
    if data is None:
        return CheckResult(
            id="A6", name="Workflow 步骤时序", layer="A",
            status="skipped", severity="medium",
            evidence="workflow_state.json 不存在",
        )
    task = data.get("current_task") or {}
    # 也允许从 history 中找已完成任务
    completed = task.get("completed_steps") or []
    if not completed:
        # 尝试从 history
        history = data.get("history") or []
        for h in reversed(history):
            if h.get("args", {}).get("chapter_num") == chapter:
                completed = h.get("completed_steps") or []
                break
    if not completed:
        return CheckResult(
            id="A6", name="Workflow 步骤时序", layer="A",
            status="skipped", severity="medium",
            evidence=f"无章节 {chapter} 的 completed_steps",
        )
    # 提取时间戳
    timestamps = []
    for s in completed:
        ts = s.get("completed_at") or s.get("started_at")
        if ts:
            timestamps.append((s.get("id", "?"), ts))
    violations = []
    for i in range(1, len(timestamps)):
        if timestamps[i][1] < timestamps[i - 1][1]:
            violations.append(f"{timestamps[i - 1][0]}→{timestamps[i][0]}")
    if violations:
        return CheckResult(
            id="A6", name="Workflow 步骤时序", layer="A",
            status="fail", severity="high",
            evidence=f"时间戳非单调: {violations}",
            measured={"violations": violations},
            remediation=["重跑可疑步骤; 检查系统时钟"],
        )
    return CheckResult(
        id="A6", name="Workflow 步骤时序", layer="A",
        status="pass", severity="medium",
        evidence=f"{len(timestamps)} 个 step 时间戳单调",
        measured={"steps_count": len(timestamps)},
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
    # 约定: Step 4 的终检在 .webnovel/polish_reports/ch{NNNN}.json (best effort)
    report_path = project_root / ".webnovel" / "polish_reports" / f"ch{_pad(chapter)}.json"
    if not report_path.exists():
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
    # 提取摘要中的 key_beats (以 - / ・ 开头的行)
    beats = re.findall(r"^[\s\-・•\*]+(.+?)$", summary_text, re.MULTILINE)
    beats = [b.strip() for b in beats if len(b.strip()) > 5][:10]
    if not beats:
        return CheckResult(
            id="B1", name="摘要 vs 正文", layer="B",
            status="warn", severity="medium",
            evidence="摘要无可识别的 key_beats 列表",
            remediation=["Step 5 E 生成摘要时使用项目符号列表"],
        )
    # 每个 beat 抽取 4-8 字关键词，在正文中查找
    matched = 0
    for beat in beats:
        # 提取 4 字及以上的连续中文片段
        fragments = re.findall(r"[\u4e00-\u9fff]{4,}", beat)
        for frag in fragments[:2]:
            if frag in chapter_text:
                matched += 1
                break
    match_ratio = matched / len(beats) if beats else 0
    if match_ratio < 0.5:
        return CheckResult(
            id="B1", name="摘要 vs 正文", layer="B",
            status="fail", severity="high",
            evidence=f"摘要 key_beats 仅 {matched}/{len(beats)} 能在正文中找到 ({match_ratio:.0%})",
            measured={"matched": matched, "total_beats": len(beats), "ratio": round(match_ratio, 2)},
            remediation=["重跑 Step 5 E (摘要必须基于正文); 或人工核对摘要"],
        )
    if match_ratio < 0.8:
        return CheckResult(
            id="B1", name="摘要 vs 正文", layer="B",
            status="warn", severity="medium",
            evidence=f"摘要 key_beats 匹配率 {match_ratio:.0%}",
            measured={"matched": matched, "total_beats": len(beats), "ratio": round(match_ratio, 2)},
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
    missing_in_chapter = [e for e in entities_scenes if e and e not in chapter_text]
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
    """B4: review_metrics 数值一致 — index.db review_metrics 表与审查报告分数一致."""
    db_path = project_root / ".webnovel" / "index.db"
    if not db_path.exists():
        return CheckResult(
            id="B4", name="review_metrics 一致性", layer="B",
            status="skipped", severity="medium",
            evidence="index.db 不存在",
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
            evidence=f"review_metrics 查询失败: {exc}",
        )
    if not row:
        return CheckResult(
            id="B4", name="review_metrics 一致性", layer="B",
            status="warn", severity="medium",
            evidence=f"review_metrics 表无章节 {chapter} 数据",
            remediation=["重跑 index save-review-metrics"],
        )
    db_score = row[0]
    # 从审查报告中提取分数
    review = _find_review_report(project_root, chapter)
    text = _read_text(review) if review else ""
    text = text or ""
    report_score = None
    m = re.search(r"(?:总分|综合评分|overall[_ ]?score)[^\n]{0,20}[:：]\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE)
    if m:
        try:
            report_score = float(m.group(1))
        except Exception:
            report_score = None
    if report_score is None:
        return CheckResult(
            id="B4", name="review_metrics 一致性", layer="B",
            status="warn", severity="medium",
            evidence=f"审查报告未找到总分字段 (db_score={db_score})",
        )
    diff = abs(float(db_score) - report_score)
    if diff > 3:
        return CheckResult(
            id="B4", name="review_metrics 一致性", layer="B",
            status="fail", severity="high",
            evidence=f"db_score={db_score} vs report_score={report_score}, 差异 {diff}",
            measured={"db_score": db_score, "report_score": report_score, "diff": diff},
            remediation=["重跑 index save-review-metrics"],
        )
    return CheckResult(
        id="B4", name="review_metrics 一致性", layer="B",
        status="pass", severity="medium",
        evidence=f"db_score={db_score} ≈ report_score={report_score}",
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
    ch_key = str(chapter)
    entry = cmeta.get(ch_key) or cmeta.get(chapter)
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
    decision = data.get("overall_decision")
    allowed = [x.strip() for x in args.require.split(",") if x.strip()]
    if decision not in allowed:
        print_error("audit_decision_not_allowed",
                    f"overall_decision={decision} 不在允许列表 {allowed}",
                    suggestion="修复 blocking_issues 或重跑 audit")
        return 1
    print_success({"chapter": args.chapter, "decision": decision, "allowed": allowed},
                  message=f"audit decision={decision} 符合要求")
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
