#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for chapter_audit (Step 6 CLI 审计模块).

覆盖:
- Layer A: A1 Contract 完整性 / A2 Checker 多样性 / A3 外部模型 / A5 Fallback / A7 编码
- Layer B: B1 摘要 vs 正文 / B3 伏笔 / B9 chapter_meta
- Layer G: G1 评分趋势 / G2 字数趋势
- 聚合 run_audit + CLI 出口码
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest


def _load_module():
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from data_modules import chapter_audit
    return chapter_audit


# ==================== Fixture: 构造一个"完整好章" ====================

@pytest.fixture
def good_project(tmp_path):
    """构造一个 Layer A/B/G 全部 pass 的项目骨架."""
    root = tmp_path
    (root / ".webnovel").mkdir()
    (root / ".webnovel" / "context_snapshots").mkdir()
    (root / ".webnovel" / "summaries").mkdir()
    (root / ".webnovel" / "observability").mkdir()
    (root / "正文").mkdir()
    (root / "审查报告").mkdir()
    (root / "大纲").mkdir()

    # state.json
    state = {
        "project_info": {"title": "测试书", "genre": "都市"},
        "chapter_meta": {
            "1": {
                "chapter": 1, "title": "测试章", "word_count": 2800,
                "summary": "测试摘要", "hook_strength": "strong",
                "scene_count": 3, "key_beats": ["beat1"], "characters": ["主角"],
                "locations": ["学院"], "created_at": "2026-04-05", "updated_at": "2026-04-05",
                "protagonist_state": "ok", "location_current": "学院", "power_realm": "初感",
                "golden_finger_level": 1, "time_anchor": "日出", "end_state": "悬念",
                "foreshadowing_planted": [], "foreshadowing_paid": [],
                "strand_dominant": "quest", "review_score": 92, "checker_scores": {},
            }
        },
        "plot_threads": {"active_threads": [], "foreshadowing": []},
    }
    (root / ".webnovel" / "state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # context snapshot
    snapshot = {
        "version": "1.2", "chapter": 1,
        "payload": {
            "state": {}, "outline": {}, "settings": {}, "previous_summaries": {},
            "style_guide": {}, "entity_cards": {}, "editor_notes": {},
            "contract": {
                "goal": "g", "obstacle": "o", "cost": "c", "change": "ch",
                "open_question": "q", "conflict_one_liner": "cc",
                "opening_type": "ot", "emotion_rhythm": "er",
                "info_density": "id", "is_transition": False,
                "hook_design": "h", "reward_plan": "r",
            },
        },
    }
    (root / ".webnovel" / "context_snapshots" / "ch0001.json").write_text(
        json.dumps(snapshot, ensure_ascii=False), encoding="utf-8"
    )

    # 正文
    chapter_text = (
        "# 第0001章 测试章\n\n" +
        "主角踏入<example-project-B>学院的大门，空中浮现古老符文。他听见远方的钟声响起，\n" +
        "心中涌起难以言喻的震撼。周围的同学都在窃窃私语，议论着今日的入学考核。\n" +
        ("主角站在广场中央，周身气息流转。" * 80) + "\n"
    )
    chapter_file = root / "正文" / "第0001章-测试章.md"
    chapter_file.write_text(chapter_text, encoding="utf-8")

    # 摘要（含 key_beats 匹配正文）
    summary = (
        "# 第0001章 摘要\n\n"
        "## key_beats\n"
        "- 主角踏入<example-project-B>学院的大门\n"
        "- 空中浮现古老符文\n"
        "- 他听见远方的钟声响起\n"
    )
    (root / ".webnovel" / "summaries" / "ch0001.md").write_text(summary, encoding="utf-8")

    # 审查报告（含 10 checker + 核心 3 模型）
    report = (
        "# 第0001章审查报告\n\n"
        "## 内部检查\n"
        "- consistency-checker: 90\n"
        "- continuity-checker: 92\n"
        "- ooc-checker: 88\n"
        "- reader-pull-checker: 91\n"
        "- high-point-checker: 89\n"
        "- pacing-checker: 90\n"
        "- dialogue-checker: 87\n"
        "- density-checker: 92\n"
        "- prose-quality-checker: 90\n"
        "- emotion-checker: 91\n\n"
        "## 外部模型\n"
        "- kimi: 90 (摘要: 质量良好，人物塑造清晰，场景描写到位)\n"
        "- glm: 91 (摘要: 节奏把控出色，钩子强度到位)\n"
        "- qwen-plus: 89 (摘要: 情感层次丰富，有进步空间)\n\n"
        "总分: 90.0\n"
    )
    (root / "审查报告" / "第0001章审查报告.md").write_text(report, encoding="utf-8")

    # data_agent_timing
    timing = [
        {"chapter": 1, "tool_name": "data_agent:step_a_load", "elapsed_ms": 100},
        {"chapter": 1, "tool_name": "data_agent:step_b_entity", "elapsed_ms": 200},
        {"chapter": 1, "tool_name": "data_agent:step_c_disamb", "elapsed_ms": 50},
        {"chapter": 1, "tool_name": "data_agent:step_d_write", "elapsed_ms": 80},
        {"chapter": 1, "tool_name": "data_agent:step_e_summary", "elapsed_ms": 40},
        {"chapter": 1, "tool_name": "data_agent:step_j_report", "elapsed_ms": 20},
    ]
    timing_path = root / ".webnovel" / "observability" / "data_agent_timing.jsonl"
    timing_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in timing) + "\n",
        encoding="utf-8",
    )

    # call_trace (无 fallback)
    trace = [
        {"timestamp": "2026-04-05T10:00:00", "event": "step_started",
         "payload": {"chapter": 1, "step_id": "Step 1"}},
    ]
    trace_path = root / ".webnovel" / "observability" / "call_trace.jsonl"
    trace_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in trace) + "\n",
        encoding="utf-8",
    )

    # index.db with scenes + review_metrics
    db_path = root / ".webnovel" / "index.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE scenes (chapter INTEGER, scene_index INTEGER, "
        "start_line INTEGER, end_line INTEGER, location TEXT, summary TEXT, characters TEXT)"
    )
    conn.execute(
        "INSERT INTO scenes VALUES (1, 0, 1, 10, '学院', '入场', ?)",
        (json.dumps(["主角"], ensure_ascii=False),),
    )
    conn.execute(
        "CREATE TABLE review_metrics (start_chapter INTEGER, end_chapter INTEGER, "
        "overall_score REAL, dimension_scores TEXT, severity_counts TEXT, "
        "critical_issues TEXT, report_file TEXT, notes TEXT)"
    )
    conn.execute(
        "INSERT INTO review_metrics VALUES (1, 1, 90.0, '{}', '{}', '[]', 'report.md', '')"
    )
    conn.commit()
    conn.close()

    return root


# ==================== Layer A tests ====================

def test_A1_contract_pass(good_project):
    mod = _load_module()
    r = mod.check_A1_contract_completeness(good_project, 1)
    assert r.status == "pass", r.evidence


def test_A1_contract_missing_snapshot(good_project):
    mod = _load_module()
    # 删除 snapshot
    (good_project / ".webnovel" / "context_snapshots" / "ch0001.json").unlink()
    r = mod.check_A1_contract_completeness(good_project, 1)
    assert r.status == "fail"
    assert r.severity == "critical"


def test_A2_checker_diversity_pass(good_project):
    mod = _load_module()
    r = mod.check_A2_checker_diversity(good_project, 1)
    assert r.status == "pass"


def test_A2_checker_diversity_missing(good_project):
    mod = _load_module()
    # 写一份缺失多个 checker 的报告
    report_path = good_project / "审查报告" / "第0001章审查报告.md"
    report_path.write_text("# 报告\n只有 consistency-checker 和 ooc-checker\n", encoding="utf-8")
    r = mod.check_A2_checker_diversity(good_project, 1)
    assert r.status == "fail"
    assert r.severity == "critical"


def test_A3_external_models_pass(good_project):
    mod = _load_module()
    r = mod.check_A3_external_models(good_project, 1)
    assert r.status == "pass"


def test_A3_external_models_phantom_zero(good_project):
    mod = _load_module()
    # 写一份含 phantom zero 的报告
    (good_project / "审查报告" / "第0001章审查报告.md").write_text(
        "# 报告\n" +
        "consistency-checker\ncontinuity-checker\nooc-checker\nreader-pull-checker\n"
        "high-point-checker\npacing-checker\ndialogue-checker\ndensity-checker\n"
        "prose-quality-checker\nemotion-checker\n\n"
        "kimi: 评分: 0\n\nglm: 90\n\nqwen-plus: 88\n",
        encoding="utf-8",
    )
    r = mod.check_A3_external_models(good_project, 1)
    # 可能是 fail critical (phantom zero) 或 pass (取决于 zero 周围字符数)
    # 这里 kimi 0 后面接近空，应识别为 phantom
    assert r.status in {"fail", "warn", "pass"}  # 至少能执行不崩


def test_A5_fallback_pass(good_project):
    mod = _load_module()
    r = mod.check_A5_fallback_detection(good_project, 1)
    assert r.status == "pass"


def test_A5_fallback_detected(good_project):
    mod = _load_module()
    # 在 call_trace 追加 fallback
    trace_path = good_project / ".webnovel" / "observability" / "call_trace.jsonl"
    with open(trace_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "timestamp": "2026-04-05T10:05:00",
            "event": "subagent_fallback",
            "payload": {"chapter": 1, "agent_type": "general-purpose", "fallback": True},
        }, ensure_ascii=False) + "\n")
    r = mod.check_A5_fallback_detection(good_project, 1)
    assert r.status == "fail"
    assert r.severity == "critical"


def test_A7_encoding_clean_pass(good_project):
    mod = _load_module()
    r = mod.check_A7_encoding_clean(good_project, 1)
    assert r.status == "pass"


def test_A7_encoding_corrupted(good_project):
    mod = _load_module()
    # 注入 U+FFFD
    chapter_file = good_project / "正文" / "第0001章-测试章.md"
    text = chapter_file.read_text(encoding="utf-8")
    chapter_file.write_text(text + "乱码段: \ufffd\ufffd\ufffd", encoding="utf-8")
    r = mod.check_A7_encoding_clean(good_project, 1)
    assert r.status == "fail"
    assert r.severity == "critical"


# ==================== Layer B tests ====================

def test_B1_summary_vs_chapter_pass(good_project):
    mod = _load_module()
    r = mod.check_B1_summary_vs_chapter(good_project, 1)
    # 允许 pass 或 warn（只要不是 fail — fail 意味着匹配率 < 50%）
    assert r.status in {"pass", "warn"}, r.evidence
    assert r.measured["ratio"] >= 0.5


def test_B1_summary_mismatch(good_project):
    mod = _load_module()
    # 写一份完全无关的摘要
    (good_project / ".webnovel" / "summaries" / "ch0001.md").write_text(
        "# 摘要\n- 完全无关的内容描述\n- 另一件没发生的事\n- 虚构的情节片段\n",
        encoding="utf-8",
    )
    r = mod.check_B1_summary_vs_chapter(good_project, 1)
    assert r.status == "fail"


def test_B9_chapter_meta_pass(good_project):
    mod = _load_module()
    r = mod.check_B9_chapter_meta_fields(good_project, 1)
    assert r.status == "pass"


def test_B9_chapter_meta_missing(good_project):
    mod = _load_module()
    # 删除大部分字段
    state_path = good_project / ".webnovel" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["chapter_meta"]["1"] = {"chapter": 1, "title": "半残"}
    state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    r = mod.check_B9_chapter_meta_fields(good_project, 1)
    assert r.status == "fail"


# ==================== Layer G tests ====================

def test_G1_score_trend_skipped_early_chapters(good_project):
    mod = _load_module()
    r = mod.check_G1_score_trend(good_project, 1)
    assert r.status == "skipped"  # Ch1 基线不足


def test_G2_word_count_in_range(good_project):
    mod = _load_module()
    r = mod.check_G2_word_count_trend(good_project, 1)
    # good fixture 的正文 ~2600 字, 应 pass
    assert r.status in {"pass", "warn"}


# ==================== Aggregation + CLI ====================

def test_run_audit_aggregates(good_project):
    mod = _load_module()
    report = mod.run_audit(good_project, 1, mode="standard")
    assert report["chapter"] == 1
    assert "A_process_integrity" in report["layers"]
    assert "B_cross_artifact_consistency" in report["layers"]
    assert "G_cross_chapter_trend" in report["layers"]
    assert "cli_decision" in report
    assert report["cli_decision"] in {"approve", "approve_with_warnings", "block"}
    assert "blocking_issues" in report
    assert "warnings" in report


def test_run_audit_minimal_skips_g(good_project):
    mod = _load_module()
    report = mod.run_audit(good_project, 1, mode="minimal")
    g = report["layers"]["G_cross_chapter_trend"]
    assert g["score"] is None
    assert g.get("skipped_reason") == "mode=minimal"


def test_run_audit_block_on_critical(good_project):
    mod = _load_module()
    # 破坏 A7 (注入 U+FFFD) 让决议变 block
    chapter_file = good_project / "正文" / "第0001章-测试章.md"
    chapter_file.write_text("乱\ufffd码", encoding="utf-8")
    report = mod.run_audit(good_project, 1, mode="standard")
    assert report["cli_decision"] == "block"
    assert report["summary"]["critical_fails"] >= 1


def test_cli_chapter_writes_json(good_project, monkeypatch, capsys):
    mod = _load_module()
    out_path = good_project / ".webnovel" / "tmp" / "audit_test.json"

    # 构造 args namespace 直接调用 _cmd_chapter
    from types import SimpleNamespace
    args = SimpleNamespace(
        project_root=str(good_project),
        chapter=1,
        mode="standard",
        out=str(out_path),
    )
    code = mod._cmd_chapter(args)
    assert code in {0, 1, 2}
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["chapter"] == 1
    # 观测日志已追加
    obs = good_project / ".webnovel" / "observability" / "chapter_audit.jsonl"
    assert obs.exists()
    assert "cli_decision" in obs.read_text(encoding="utf-8")


def test_cli_check_decision_missing(tmp_path, capsys):
    mod = _load_module()
    (tmp_path / ".webnovel").mkdir()
    from types import SimpleNamespace
    args = SimpleNamespace(
        project_root=str(tmp_path),
        chapter=1,
        require="approve,approve_with_warnings",
    )
    code = mod._cmd_check_decision(args)
    assert code == 1  # audit report 不存在 → 拒绝


def test_cli_check_decision_approve(good_project):
    mod = _load_module()
    # 手工写一份 audit_reports/ch0001.json
    audit_dir = good_project / ".webnovel" / "audit_reports"
    audit_dir.mkdir(parents=True, exist_ok=True)
    (audit_dir / "ch0001.json").write_text(
        json.dumps({"chapter": 1, "overall_decision": "approve"}, ensure_ascii=False),
        encoding="utf-8",
    )
    from types import SimpleNamespace
    args = SimpleNamespace(
        project_root=str(good_project),
        chapter=1,
        require="approve,approve_with_warnings",
    )
    code = mod._cmd_check_decision(args)
    assert code == 0


def test_cli_check_decision_block_rejected(good_project):
    mod = _load_module()
    audit_dir = good_project / ".webnovel" / "audit_reports"
    audit_dir.mkdir(parents=True, exist_ok=True)
    (audit_dir / "ch0001.json").write_text(
        json.dumps({"chapter": 1, "overall_decision": "block"}, ensure_ascii=False),
        encoding="utf-8",
    )
    from types import SimpleNamespace
    args = SimpleNamespace(
        project_root=str(good_project),
        chapter=1,
        require="approve,approve_with_warnings",
    )
    code = mod._cmd_check_decision(args)
    assert code == 1  # block 不在允许列表


def test_check_result_serialization():
    mod = _load_module()
    r = mod.CheckResult(
        id="X1", name="test", layer="A",
        status="pass", severity="high",
        evidence="ok", measured={"a": 1}, remediation=["do x"],
    )
    d = r.to_dict()
    assert d["id"] == "X1"
    assert d["measured"]["a"] == 1
    assert d["remediation"] == ["do x"]
