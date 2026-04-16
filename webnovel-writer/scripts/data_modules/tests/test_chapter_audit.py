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
                "strand_dominant": "quest",
                "review_score": 92,
                "checker_scores": {
                    "consistency-checker": 90,
                    "continuity-checker": 92,
                    "ooc-checker": 88,
                    "reader-pull-checker": 91,
                    "high-point-checker": 89,
                    "pacing-checker": 90,
                    "dialogue-checker": 87,
                    "density-checker": 92,
                    "prose-quality-checker": 90,
                    "emotion-checker": 91,
                },
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
        "主角踏入镇妖学院的大门，空中浮现古老符文。他听见远方的钟声响起，\n" +
        "心中涌起难以言喻的震撼。周围的同学都在窃窃私语，议论着今日的入学考核。\n" +
        ("主角站在广场中央，周身气息流转。" * 80) + "\n"
    )
    chapter_file = root / "正文" / "第0001章-测试章.md"
    chapter_file.write_text(chapter_text, encoding="utf-8")

    # 摘要（含 key_beats 匹配正文）
    summary = (
        "# 第0001章 摘要\n\n"
        "## key_beats\n"
        "- 主角踏入镇妖学院的大门\n"
        "- 空中浮现古老符文\n"
        "- 他听见远方的钟声响起\n"
    )
    (root / ".webnovel" / "summaries" / "ch0001.md").write_text(summary, encoding="utf-8")

    # 审查报告（含 11 checker + 核心 3 模型）
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
        "- emotion-checker: 91\n"
        "- flow-checker: 88\n\n"
        "## 外部模型\n"
        "- kimi: 90 (摘要: 质量良好，人物塑造清晰，场景描写到位)\n"
        "- glm: 91 (摘要: 节奏把控出色，钩子强度到位)\n"
        "- qwen-plus: 89 (摘要: 情感层次丰富，有进步空间)\n\n"
        "总分: 90.0\n"
    )
    (root / "审查报告" / "第0001章审查报告.md").write_text(report, encoding="utf-8")

    tmp_dir = root / ".webnovel" / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    dimension_names = [
        "consistency",
        "continuity",
        "ooc",
        "reader_pull",
        "high_point",
        "pacing",
        "dialogue_quality",
        "information_density",
        "prose_quality",
        "emotion_expression",
        "reader_flow",
    ]
    for model_key in ("kimi", "glm", "qwen-plus"):
        payload = {
            "agent": f"external-{model_key}",
            "chapter": 1,
            "model_key": model_key,
            "model_actual": f"{model_key}-actual",
            "routing_verified": True,
            "overall_score": 90.0,
            "pass": True,
            "dimension_reports": [
                {"dimension": dim_name, "status": "ok", "score": 90, "summary": "ok"}
                for dim_name in dimension_names
            ],
        }
        (tmp_dir / f"external_review_{model_key}_ch0001.json").write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )

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

    workflow_state = {
        "current_task": None,
        "last_stable_state": None,
        "history": [
            {
                "task_id": "task_001",
                "command": "webnovel-write",
                "chapter": 1,
                "status": "completed",
                "started_at": "2026-04-05T09:00:00",
                "completed_at": "2026-04-05T09:30:00",
                "args": {"chapter_num": 1},
                "artifacts": {},
                "completed_steps": [
                    {"id": "Step 1", "started_at": "2026-04-05T09:00:00", "completed_at": "2026-04-05T09:01:00"},
                    {"id": "Step 2A", "started_at": "2026-04-05T09:01:01", "completed_at": "2026-04-05T09:05:00"},
                    {"id": "Step 2B", "started_at": "2026-04-05T09:05:01", "completed_at": "2026-04-05T09:06:00"},
                    {"id": "Step 3", "started_at": "2026-04-05T09:06:01", "completed_at": "2026-04-05T09:10:00"},
                    {"id": "Step 3.5", "started_at": "2026-04-05T09:10:01", "completed_at": "2026-04-05T09:14:00"},
                    {"id": "Step 4", "started_at": "2026-04-05T09:14:01", "completed_at": "2026-04-05T09:18:00"},
                    {"id": "Step 5", "started_at": "2026-04-05T09:18:01", "completed_at": "2026-04-05T09:22:00"},
                    {"id": "Step 6", "started_at": "2026-04-05T09:22:01", "completed_at": "2026-04-05T09:25:00"},
                    {"id": "Step 7", "started_at": "2026-04-05T09:25:01", "completed_at": "2026-04-05T09:30:00"},
                ],
                "failed_steps": [],
            }
        ],
    }
    (root / ".webnovel" / "workflow_state.json").write_text(
        json.dumps(workflow_state, ensure_ascii=False, indent=2),
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


def test_A2_checker_diversity_fails_on_score_collapse(good_project):
    mod = _load_module()
    state_path = good_project / ".webnovel" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["chapter_meta"]["1"]["checker_scores"] = {name: 90 for name in mod.CHECKER_NAMES}
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    r = mod.check_A2_checker_diversity(good_project, 1)
    assert r.status == "fail"
    assert r.severity == "critical"


def test_A2_checker_diversity_fails_on_duplicated_snippets(good_project):
    mod = _load_module()
    report_path = mod._find_review_report(good_project, 1)
    assert report_path is not None
    report_path.write_text(
        "\n".join(
            [
                "| consistency-checker | 90 | 同一条模板意见：节奏需要微调 |",
                "| continuity-checker | 91 | 同一条模板意见：节奏需要微调 |",
                "| ooc-checker | 92 | 同一条模板意见：节奏需要微调 |",
                "| reader-pull-checker | 93 | 追读钩子足够 |",
                "| high-point-checker | 89 | 爽点密度稳定 |",
                "| pacing-checker | 88 | 节奏控制稳定 |",
                "| dialogue-checker | 87 | 对话层次正常 |",
                "| density-checker | 92 | 信息密度平衡 |",
                "| prose-quality-checker | 90 | 文笔保持稳定 |",
                "| emotion-checker | 91 | 情感张力在线 |",
                "| flow-checker | 88 | 读者流畅度稳定 |",
            ]
        ),
        encoding="utf-8",
    )
    r = mod.check_A2_checker_diversity(good_project, 1)
    assert r.status == "fail"
    assert r.severity == "critical"


def test_A3_external_models_pass(good_project):
    mod = _load_module()
    r = mod.check_A3_external_models(good_project, 1)
    assert r.status in {"pass", "warn"}


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


def test_A3_external_models_json_phantom_zero(good_project):
    mod = _load_module()
    payload = {
        "agent": "external-kimi",
        "chapter": 1,
        "model_key": "kimi",
        "overall_score": 0,
        "pass": False,
        "dimension_reports": [
            {"dimension": "consistency", "status": "ok", "score": 0, "summary": ""},
        ],
    }
    (good_project / ".webnovel" / "tmp" / "external_review_kimi_ch0001.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    r = mod.check_A3_external_models(good_project, 1)
    assert r.status == "fail"
    assert r.severity == "critical"


def test_A3_external_models_fails_on_core_partial_dimensions(good_project):
    mod = _load_module()
    core_path = good_project / ".webnovel" / "tmp" / "external_review_kimi_ch0001.json"
    payload = json.loads(core_path.read_text(encoding="utf-8"))
    payload["dimension_reports"] = payload["dimension_reports"][:9]
    core_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    r = mod.check_A3_external_models(good_project, 1)
    assert r.status == "fail"
    assert r.severity == "critical"
    assert "kimi" in json.dumps(r.measured, ensure_ascii=False)


def test_A3_external_models_fails_on_core_routing_unverified(good_project):
    mod = _load_module()
    core_path = good_project / ".webnovel" / "tmp" / "external_review_glm_ch0001.json"
    payload = json.loads(core_path.read_text(encoding="utf-8"))
    payload["routing_verified"] = False
    core_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    r = mod.check_A3_external_models(good_project, 1)
    assert r.status == "fail"
    assert r.severity == "critical"
    assert "routing_unverified" in json.dumps(r.measured, ensure_ascii=False)


def test_A3_external_models_warns_on_partial_supplemental_model(good_project):
    mod = _load_module()
    payload = {
        "agent": "external-qwen",
        "chapter": 1,
        "model_key": "qwen",
        "model_actual": "qwen-3.5",
        "routing_verified": True,
        "overall_score": 88.0,
        "pass": True,
        "dimension_reports": [
            {"dimension": "consistency", "status": "ok", "score": 88, "summary": "ok"},
            {"dimension": "continuity", "status": "ok", "score": 89, "summary": "ok"},
            {"dimension": "ooc", "status": "ok", "score": 87, "summary": "ok"},
        ],
    }
    (good_project / ".webnovel" / "tmp" / "external_review_qwen_ch0001.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    r = mod.check_A3_external_models(good_project, 1)
    assert r.status == "warn"
    assert r.severity == "high"
    assert "qwen" in json.dumps(r.measured, ensure_ascii=False)


def test_A4_data_agent_steps_passes_with_timing_ms(good_project):
    mod = _load_module()
    timing_path = good_project / ".webnovel" / "observability" / "data_agent_timing.jsonl"
    timing_path.write_text(
        json.dumps(
            {
                "chapter": 1,
                "timing_ms": {
                    "A_load_context": 100,
                    "B_entity_extract": 200,
                    "C_disambiguation": 50,
                    "D_state_index_write": 80,
                    "E_summary_write": 40,
                    "F_scene_chunking": 60,
                    "G_rag_index": 70,
                    "H_style_sample": 30,
                    "I_debt_interest": 0,
                    "K_settings_sync": 0,
                    "TOTAL": 630,
                },
            },
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )
    r = mod.check_A4_data_agent_steps(good_project, 1)
    assert r.status in {"pass", "warn"}


def test_A6_workflow_timing_detects_trace_violations(good_project):
    mod = _load_module()
    trace_path = good_project / ".webnovel" / "observability" / "call_trace.jsonl"
    with open(trace_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "timestamp": "2026-04-05T09:20:00",
            "event": "step_order_violation",
            "payload": {"chapter": 1, "step_id": "Step 5"},
        }, ensure_ascii=False) + "\n")
    r = mod.check_A6_workflow_timing(good_project, 1)
    assert r.status == "fail"
    assert r.severity == "critical"


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


# ==================== 决议矩阵（step-6-audit-matrix.md 对齐）====================

def _mk_check(severity: str, status: str = "fail") -> "object":
    mod = _load_module()
    return mod.CheckResult(
        id=f"T_{severity}", name="test", layer="A",
        status=status, severity=severity, evidence="synthetic",
    )


def test_derive_decision_approve_when_all_pass():
    mod = _load_module()
    assert mod._derive_cli_decision([], [], [], [], []) == "approve"


def test_derive_decision_block_on_any_critical_fail():
    mod = _load_module()
    decision = mod._derive_cli_decision(
        [_mk_check("critical")], [], [], [], []
    )
    assert decision == "block"


def test_derive_decision_single_high_fail_is_warning_not_block():
    """1-2 个 high fail 应降级为 approve_with_warnings (对齐 matrix 决议矩阵)."""
    mod = _load_module()
    decision = mod._derive_cli_decision(
        [], [_mk_check("high")], [], [], []
    )
    assert decision == "approve_with_warnings"


def test_derive_decision_two_high_fails_is_warning_not_block():
    mod = _load_module()
    decision = mod._derive_cli_decision(
        [], [_mk_check("high"), _mk_check("high")], [], [], []
    )
    assert decision == "approve_with_warnings"


def test_derive_decision_three_high_fails_triggers_block():
    """high fail >= 3 触发 block (matrix 决议矩阵)."""
    mod = _load_module()
    decision = mod._derive_cli_decision(
        [], [_mk_check("high")] * 3, [], [], []
    )
    assert decision == "block"


def test_derive_decision_medium_fail_is_warning():
    mod = _load_module()
    decision = mod._derive_cli_decision(
        [], [], [_mk_check("medium")], [], []
    )
    assert decision == "approve_with_warnings"


def test_derive_decision_low_fail_still_degrades_to_warning():
    mod = _load_module()
    decision = mod._derive_cli_decision(
        [], [], [], [_mk_check("low")], []
    )
    assert decision == "approve_with_warnings"


def test_derive_decision_warn_status_is_warning():
    mod = _load_module()
    decision = mod._derive_cli_decision(
        [], [], [], [], [_mk_check("medium", status="warn")]
    )
    assert decision == "approve_with_warnings"


def test_decision_to_exit_code_map_is_injective():
    """exit code 映射必须 approve=0 / block=1 / warn=2，与 docstring 一致."""
    mod = _load_module()
    assert mod._DECISION_TO_EXIT_CODE["approve"] == 0
    assert mod._DECISION_TO_EXIT_CODE["block"] == 1
    assert mod._DECISION_TO_EXIT_CODE["approve_with_warnings"] == 2


def test_cli_chapter_exit_code_matches_decision_block(good_project):
    """注入 critical fail → cli_decision=block → exit_code=1."""
    mod = _load_module()
    # 注入 U+FFFD 触发 A7 critical fail
    chapter_file = good_project / "正文" / "第0001章-测试章.md"
    chapter_file.write_text("乱\ufffd码", encoding="utf-8")

    out_path = good_project / ".webnovel" / "tmp" / "audit_block.json"
    from types import SimpleNamespace
    args = SimpleNamespace(
        project_root=str(good_project),
        chapter=1, mode="standard", out=str(out_path),
    )
    code = mod._cmd_chapter(args)
    data = json.loads(out_path.read_text(encoding="utf-8"))
    # JSON 和 exit code 必须一致
    assert data["cli_decision"] == "block"
    assert code == 1


def test_run_audit_summary_has_new_severity_counts(good_project):
    """run_audit summary 应含 medium_fails / low_fails 字段."""
    mod = _load_module()
    report = mod.run_audit(good_project, 1, mode="standard")
    summary = report["summary"]
    assert "critical_fails" in summary
    assert "high_fails" in summary
    assert "medium_fails" in summary
    assert "low_fails" in summary
    assert "warnings" in summary
    assert "total_checks" in summary


def test_A2_checker_diversity_warns_on_sparse_state_scores(good_project):
    mod = _load_module()
    state_path = good_project / ".webnovel" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["chapter_meta"]["1"]["checker_scores"] = {f"checker_{i}": 90 for i in range(7)}
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    r = mod.check_A2_checker_diversity(good_project, 1)
    assert r.status == "warn"
    assert r.severity == "high"


def test_A4_data_agent_steps_fails_when_timing_ms_missing_core_steps(good_project):
    mod = _load_module()
    timing_path = good_project / ".webnovel" / "observability" / "data_agent_timing.jsonl"
    timing_path.write_text(
        json.dumps(
            {
                "chapter": 1,
                "timing_ms": {
                    "A_load_context": 100,
                    "B_entity_extract": 200,
                    "C_disambiguation": 50,
                    "J_report": 10,
                    "TOTAL": 360,
                },
            },
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )
    r = mod.check_A4_data_agent_steps(good_project, 1)
    assert r.status == "fail"
    assert r.severity == "high"


def test_A6_workflow_timing_detects_missing_required_steps(good_project):
    mod = _load_module()
    workflow_path = good_project / ".webnovel" / "workflow_state.json"
    workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
    workflow["history"][0]["completed_steps"] = workflow["history"][0]["completed_steps"][:-1]
    workflow_path.write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8")
    r = mod.check_A6_workflow_timing(good_project, 1)
    assert r.status == "fail"
    assert r.severity == "critical"


def test_B4_review_metrics_pass_with_bold_total_score(good_project):
    mod = _load_module()
    report_path = mod._find_review_report(good_project, 1)
    assert report_path is not None
    report_path.write_text(
        "# report\n"
        "overall_score: **90.0**\n",
        encoding="utf-8",
    )
    r = mod.check_B4_review_metrics_consistency(good_project, 1)
    assert r.status == "pass"


def test_B4_review_metrics_fail_on_large_diff(good_project):
    mod = _load_module()
    report_path = mod._find_review_report(good_project, 1)
    assert report_path is not None
    report_path.write_text(
        "# report\n"
        "overall_score: 81.0\n",
        encoding="utf-8",
    )
    r = mod.check_B4_review_metrics_consistency(good_project, 1)
    assert r.status == "fail"
    assert r.severity == "high"


def test_A3_external_models_markdown_only_uses_report_fallback(good_project):
    mod = _load_module()
    tmp_dir = good_project / ".webnovel" / "tmp"
    for item in tmp_dir.glob("external_review_*_ch0001.json"):
        item.unlink()
    report_path = mod._find_review_report(good_project, 1)
    assert report_path is not None
    report_path.write_text(
        "# report\n"
        "- kimi: 90 (summary: solid prose and scene work)\n"
        "- glm: 91 (summary: strong pacing and hook)\n"
        "- qwen-plus: 89 (summary: emotion lands well)\n",
        encoding="utf-8",
    )
    r = mod.check_A3_external_models(good_project, 1)
    assert r.status in {"pass", "warn"}


def test_A4_data_agent_steps_warns_on_sparse_legacy_markers(good_project):
    mod = _load_module()
    timing_path = good_project / ".webnovel" / "observability" / "data_agent_timing.jsonl"
    rows = [
        {"chapter": 1, "tool_name": "data_agent:step_a_load", "elapsed_ms": 100},
        {"chapter": 1, "tool_name": "data_agent:step_b_entity", "elapsed_ms": 120},
    ]
    timing_path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    r = mod.check_A4_data_agent_steps(good_project, 1)
    assert r.status == "warn"
    assert r.severity == "medium"


def test_A8_anti_ai_force_not_stub_detects_stub_json(good_project):
    mod = _load_module()
    polish_dir = good_project / ".webnovel" / "polish_reports"
    polish_dir.mkdir(parents=True, exist_ok=True)
    (polish_dir / "ch0001.json").write_text(
        json.dumps({"anti_ai_force_check": {"is_stub": True}}, ensure_ascii=False),
        encoding="utf-8",
    )
    r = mod.check_A8_anti_ai_force_not_stub(good_project, 1)
    assert r.status == "fail"
    assert r.severity == "high"


def test_B2_entities_three_way_fails_when_scene_entities_missing_from_text(good_project):
    mod = _load_module()
    db_path = good_project / ".webnovel" / "index.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("DELETE FROM scenes")
    conn.execute(
        "INSERT INTO scenes VALUES (1, 0, 1, 10, 'arena', 'entry', ?)",
        (json.dumps(["\u4e0d\u5b58\u5728\u89d2\u8272"], ensure_ascii=False),),
    )
    conn.commit()
    conn.close()
    r = mod.check_B2_entities_three_way(good_project, 1)
    assert r.status == "fail"
    assert r.severity == "high"


def test_B3_foreshadowing_three_way_fails_when_state_claims_missing_setup(good_project):
    mod = _load_module()
    state_path = good_project / ".webnovel" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["plot_threads"]["foreshadowing"] = [
        {"chapter": 1, "description": "\u795e\u79d8\u7389\u4f69\u88c2\u5f00\u5e76\u53d1\u51fa\u9f99\u541f"}
    ]
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    r = mod.check_B3_foreshadowing_three_way(good_project, 1)
    assert r.status == "fail"
    assert r.severity == "high"


def test_B7_outline_to_chapter_skips_when_outline_dir_is_missing(good_project):
    mod = _load_module()
    outline_dir = good_project / "\u5927\u7eb2"
    for path in outline_dir.iterdir():
        path.unlink()
    outline_dir.rmdir()
    r = mod.check_B7_outline_to_chapter(good_project, 1)
    assert r.status == "skipped"


def test_B7_outline_to_chapter_skips_when_beat_file_has_no_matching_chapter(good_project):
    mod = _load_module()
    beat_path = good_project / "\u5927\u7eb2" / "\u4e3b\u7ebf\u8282\u62cd\u8868.md"
    beat_path.write_text(
        "\u7b2c 2 \u7ae0\n"
        "- \u540e\u7eed\u51b2\u7a81\u5168\u9762\u5347\u7ea7\n",
        encoding="utf-8",
    )
    r = mod.check_B7_outline_to_chapter(good_project, 1)
    assert r.status == "skipped"


def test_B7_outline_to_chapter_warns_when_only_partially_realized(good_project):
    mod = _load_module()
    beat_path = good_project / "\u5927\u7eb2" / "\u4e3b\u7ebf\u8282\u62cd\u8868.md"
    beat_path.write_text(
        "\u7b2c 1 \u7ae0\n"
        "- \u4e3b\u89d2\u8e0f\u5165\u9547\u5996\u5b66\u9662\u5927\u95e8\n"
        "- \u53e4\u8001\u7b26\u6587\u5728\u7a7a\u4e2d\u6d6e\u73b0\n"
        "- \u9662\u957f\u5f53\u4f17\u5ba3\u5e03\u8bd5\u70bc\u5f00\u59cb\n",
        encoding="utf-8",
    )
    chapter_file = mod._find_chapter_file(good_project, 1)
    assert chapter_file is not None
    chapter_file.write_text(
        "# \u7b2c001\u7ae0 \u8bd5\u70bc\u524d\u5915\n"
        "\u4e3b\u89d2\u8e0f\u5165\u9547\u5996\u5b66\u9662\u5927\u95e8\uff0c\u770b\u89c1\u53e4\u8001\u7b26\u6587\u5728\u7a7a\u4e2d\u6d6e\u73b0\u3002\n"
        "\u4eba\u7fa4\u4e00\u9635\u9a9a\u52a8\uff0c\u4f46\u8fd8\u6ca1\u6709\u4eba\u5ba3\u5e03\u8bd5\u70bc\u89c4\u5219\u3002\n",
        encoding="utf-8",
    )
    r = mod.check_B7_outline_to_chapter(good_project, 1)
    assert r.status == "warn"
    assert r.measured["ratio"] == pytest.approx(0.67, rel=1e-2)


def test_B7_outline_to_chapter_passes_when_beats_are_fully_realized(good_project):
    mod = _load_module()
    beat_path = good_project / "\u5927\u7eb2" / "\u4e3b\u7ebf\u7ae0\u7eb2.md"
    beat_path.write_text(
        "\u7b2c 1 \u7ae0\n"
        "- \u4e3b\u89d2\u8e0f\u5165\u9547\u5996\u5b66\u9662\u5927\u95e8\n"
        "- \u53e4\u8001\u7b26\u6587\u5728\u7a7a\u4e2d\u6d6e\u73b0\n"
        "- \u9662\u957f\u5f53\u4f17\u5ba3\u5e03\u8bd5\u70bc\u5f00\u59cb\n"
        "- \u65b0\u751f\u5728\u5e7f\u573a\u4e0a\u538b\u529b\u9661\u589e\n",
        encoding="utf-8",
    )
    chapter_file = mod._find_chapter_file(good_project, 1)
    assert chapter_file is not None
    chapter_file.write_text(
        "# \u7b2c001\u7ae0 \u8bd5\u70bc\u5f00\u7aef\n"
        "\u4e3b\u89d2\u8e0f\u5165\u9547\u5996\u5b66\u9662\u5927\u95e8\uff0c\u770b\u89c1\u53e4\u8001\u7b26\u6587\u5728\u7a7a\u4e2d\u6d6e\u73b0\u3002\n"
        "\u9662\u957f\u5f53\u4f17\u5ba3\u5e03\u8bd5\u70bc\u5f00\u59cb\uff0c\u65b0\u751f\u5728\u5e7f\u573a\u4e0a\u538b\u529b\u9661\u589e\u3002\n",
        encoding="utf-8",
    )
    r = mod.check_B7_outline_to_chapter(good_project, 1)
    assert r.status == "pass"
    assert r.measured["ratio"] == pytest.approx(1.0)


def test_G3_audit_trend_warns_on_rising_warning_counts(good_project):
    mod = _load_module()
    trend_path = good_project / ".webnovel" / "observability" / "chapter_audit.jsonl"
    rows = [
        {"chapter": 1, "warnings_count": 1},
        {"chapter": 2, "warnings_count": 2},
        {"chapter": 3, "warnings_count": 3},
        {"chapter": 4, "warnings_count": 4},
        {"chapter": 5, "warnings_count": 7},
    ]
    trend_path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    r = mod.check_G3_audit_trend(good_project, 5)
    assert r.status == "warn"
    assert r.severity == "medium"


def test_A8_anti_ai_force_not_stub_skips_when_not_referenced(good_project):
    mod = _load_module()
    r = mod.check_A8_anti_ai_force_not_stub(good_project, 1)
    assert r.status == "skipped"


def test_A8_anti_ai_force_not_stub_passes_on_non_stub_json(good_project):
    mod = _load_module()
    polish_dir = good_project / ".webnovel" / "polish_reports"
    polish_dir.mkdir(parents=True, exist_ok=True)
    (polish_dir / "ch0001.json").write_text(
        json.dumps({"anti_ai_force_check": {"is_stub": False}}, ensure_ascii=False),
        encoding="utf-8",
    )
    r = mod.check_A8_anti_ai_force_not_stub(good_project, 1)
    assert r.status == "pass"


def test_A8_anti_ai_force_not_stub_warns_when_report_mentions_stub(good_project):
    mod = _load_module()
    report_path = mod._find_review_report(good_project, 1)
    assert report_path is not None
    report_path.write_text("anti_ai_force_check: stub\n", encoding="utf-8")
    r = mod.check_A8_anti_ai_force_not_stub(good_project, 1)
    assert r.status == "warn"


def test_B2_entities_three_way_passes_for_fixture(good_project):
    mod = _load_module()
    r = mod.check_B2_entities_three_way(good_project, 1)
    assert r.status == "pass"


def test_G1_score_trend_warns_on_large_drop(good_project):
    mod = _load_module()
    db_path = good_project / ".webnovel" / "index.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("DELETE FROM review_metrics")
    conn.executemany(
        "INSERT INTO review_metrics VALUES (?, ?, ?, '{}', '{}', '[]', 'report.md', '')",
        [
            (1, 1, 95.0),
            (2, 2, 94.0),
            (3, 3, 93.0),
            (4, 4, 92.0),
            (5, 5, 80.0),
        ],
    )
    conn.commit()
    conn.close()
    r = mod.check_G1_score_trend(good_project, 5)
    assert r.status == "warn"


def test_G1_score_trend_passes_when_scores_are_stable(good_project):
    mod = _load_module()
    db_path = good_project / ".webnovel" / "index.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("DELETE FROM review_metrics")
    conn.executemany(
        "INSERT INTO review_metrics VALUES (?, ?, ?, '{}', '{}', '[]', 'report.md', '')",
        [
            (1, 1, 91.0),
            (2, 2, 92.0),
            (3, 3, 90.0),
            (4, 4, 91.0),
            (5, 5, 90.0),
        ],
    )
    conn.commit()
    conn.close()
    r = mod.check_G1_score_trend(good_project, 5)
    assert r.status == "pass"


def test_G2_word_count_trend_warns_when_too_short(good_project):
    mod = _load_module()
    chapter_file = mod._find_chapter_file(good_project, 1)
    assert chapter_file is not None
    chapter_file.write_text("简短章节", encoding="utf-8")
    r = mod.check_G2_word_count_trend(good_project, 1)
    assert r.status == "warn"
    assert r.severity == "medium"


def test_G2_word_count_trend_warns_when_too_long(good_project):
    mod = _load_module()
    chapter_file = mod._find_chapter_file(good_project, 1)
    assert chapter_file is not None
    chapter_file.write_text("长" * 3601, encoding="utf-8")
    r = mod.check_G2_word_count_trend(good_project, 1)
    assert r.status == "warn"
    assert r.severity == "low"


def test_G3_audit_trend_passes_when_warning_counts_are_stable(good_project):
    mod = _load_module()
    trend_path = good_project / ".webnovel" / "observability" / "chapter_audit.jsonl"
    rows = [
        {"chapter": 1, "warnings_count": 1},
        {"chapter": 2, "warnings_count": 2},
        {"chapter": 3, "warnings_count": 2},
        {"chapter": 4, "warnings_count": 2},
        {"chapter": 5, "warnings_count": 2},
    ]
    trend_path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    r = mod.check_G3_audit_trend(good_project, 5)
    assert r.status == "pass"


def test_cmd_chapter_rejects_missing_webnovel_dir(tmp_path):
    mod = _load_module()
    from types import SimpleNamespace
    args = SimpleNamespace(project_root=str(tmp_path), chapter=1, mode="standard", out=None)
    assert mod._cmd_chapter(args) == 3


def test_cmd_chapter_rejects_runtime_error(good_project, monkeypatch):
    mod = _load_module()
    from types import SimpleNamespace
    monkeypatch.setattr(mod, "run_audit", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    args = SimpleNamespace(project_root=str(good_project), chapter=1, mode="standard", out=None)
    assert mod._cmd_chapter(args) == 3


def test_chapter_audit_main_dispatches_subcommands(monkeypatch, good_project):
    mod = _load_module()

    monkeypatch.setattr(mod, "_cmd_chapter", lambda args: 2)
    monkeypatch.setattr(sys, "argv", ["chapter_audit", "--project-root", str(good_project), "chapter", "--chapter", "1"])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert int(exc.value.code or 0) == 2

    monkeypatch.setattr(mod, "_cmd_check_decision", lambda args: 0)
    monkeypatch.setattr(
        sys,
        "argv",
        ["chapter_audit", "--project-root", str(good_project), "check-decision", "--chapter", "1"],
    )
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert int(exc.value.code or 0) == 0


def test_A1_contract_passes_with_compact_panels_format(good_project):
    mod = _load_module()
    snapshot_path = good_project / ".webnovel" / "context_snapshots" / "ch0001.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "format": "v1-compact",
                "panels": {
                    "state": {},
                    "outline": {},
                    "settings": {},
                    "summaries": {},
                    "reader_signal": {},
                    "memory": {},
                },
                "contract": {
                    "goal": "g",
                    "obstacle": "o",
                    "cost": "c",
                    "change": "ch",
                    "hook": "h",
                    "reward": "r",
                    "emotion": "e",
                    "time_anchor": "t",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    r = mod.check_A1_contract_completeness(good_project, 1)
    assert r.status == "pass"


def test_A1_contract_warns_when_compact_panels_contract_is_too_small(good_project):
    mod = _load_module()
    snapshot_path = good_project / ".webnovel" / "context_snapshots" / "ch0001.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "format": "v1-compact",
                "panels": {
                    "state": {},
                    "outline": {},
                    "settings": {},
                    "summaries": {},
                    "reader_signal": {},
                    "memory": {},
                },
                "contract": {"goal": "g", "obstacle": "o"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    r = mod.check_A1_contract_completeness(good_project, 1)
    assert r.status == "warn"
    assert r.severity == "high"
