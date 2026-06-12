#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 29 Phase 4 · audit finalize：决议矩阵代码化 + 最终报告落盘由 CLI 完成。

背景：Ch50/51/52 三章连续 audit-agent claim 落盘但未写；Ch52 "F2/A10/F7 三 high
按矩阵应 block 却写成 approve_with_warnings"——让 LLM 在 70 项检查末尾做矩阵运算
必然出错。R29：agent 只产出 findings（C/D/E/F 判断），决议与落盘由本 CLI 确定性完成，
audit-agent 自检 1/2/3/5 四道随之废除。

矩阵口径（step-6-audit-matrix.md 权威）：命中 = status ∈ {warn, fail}；
critical 任一命中 → block；high ≥3 命中 → block；high 1-2 → approve_with_warnings；
medium 任一命中 → approve_with_warnings；low 仅记录。
"""

import json

from data_modules.chapter_audit import aggregate_final_decision, merge_audit_layers, finalize_audit_report


def _layer(checks):
    return {"score": 90, "checks": checks}


def _chk(cid, status, severity):
    return {"id": cid, "name": cid, "layer": cid[0], "status": status, "severity": severity,
            "evidence": "test", "measured": {}, "remediation": []}


def test_critical_hit_blocks():
    layers = {
        "A_process_integrity": _layer([_chk("A1", "pass", "high")]),
        "C_reader_experience": _layer([_chk("C3", "fail", "critical")]),
    }
    out = aggregate_final_decision(layers)
    assert out["decision"] == "block"
    assert any(b["id"] == "C3" for b in out["blocking_issues"])


def test_three_high_hits_including_warn_status_block():
    """Ch52 实战回归：F2 fail-high + A10 warn-high + F7 warn-high = 3 命中 → 必须 block。"""
    layers = {
        "A_process_integrity": _layer([_chk("A10", "warn", "high")]),
        "F_genre_fitness": _layer([_chk("F2", "fail", "high"), _chk("F7", "warn", "high")]),
    }
    out = aggregate_final_decision(layers)
    assert out["high_hits"] == 3
    assert out["decision"] == "block"


def test_two_high_hits_approve_with_warnings():
    layers = {
        "C_reader_experience": _layer([_chk("C2", "warn", "high"), _chk("C5", "fail", "high")]),
    }
    out = aggregate_final_decision(layers)
    assert out["decision"] == "approve_with_warnings"


def test_single_medium_hit_approve_with_warnings():
    layers = {"E_craft_quality": _layer([_chk("E1", "warn", "medium")])}
    assert aggregate_final_decision(layers)["decision"] == "approve_with_warnings"


def test_all_pass_approves():
    layers = {
        "A_process_integrity": _layer([_chk("A1", "pass", "critical")]),
        "C_reader_experience": _layer([_chk("C1", "pass", "high"), _chk("C2", "skipped", "high")]),
    }
    out = aggregate_final_decision(layers)
    assert out["decision"] == "approve"
    assert out["blocking_issues"] == []


def test_merge_layers_agent_overrides_f_keeps_abg():
    part1 = {
        "layers": {
            "A_process_integrity": _layer([_chk("A1", "pass", "high")]),
            "B_cross_artifact_consistency": _layer([_chk("B4", "pass", "high")]),
            "F_genre_fitness": _layer([_chk("F2", "warn", "high")]),
            "G_cross_chapter_trend": _layer([_chk("G1", "pass", "low")]),
        }
    }
    agent = {
        "layers": {
            "C_reader_experience": _layer([_chk("C1", "pass", "high")]),
            "D_work_continuity": _layer([_chk("D1", "pass", "high")]),
            "E_craft_quality": _layer([_chk("E1", "pass", "medium")]),
            "F_genre_fitness": _layer([_chk("F2", "fail", "high"), _chk("F7", "warn", "high")]),
        }
    }
    merged = merge_audit_layers(part1, agent)
    assert set(merged.keys()) == {
        "A_process_integrity", "B_cross_artifact_consistency", "C_reader_experience",
        "D_work_continuity", "E_craft_quality", "F_genre_fitness", "G_cross_chapter_trend",
    }
    f_checks = {c["id"]: c for c in merged["F_genre_fitness"]["checks"]}
    assert f_checks["F2"]["status"] == "fail"  # agent 同 id 覆盖 CLI 子集
    assert "F7" in f_checks


def test_finalize_writes_report_and_jsonl(tmp_path):
    (tmp_path / ".webnovel").mkdir()
    part1 = {
        "layers": {
            "A_process_integrity": _layer([_chk("A1", "pass", "high")]),
            "B_cross_artifact_consistency": _layer([_chk("B4", "pass", "high")]),
            "F_genre_fitness": _layer([]),
            "G_cross_chapter_trend": _layer([_chk("G1", "pass", "low")]),
        }
    }
    agent = {
        "layers": {
            "C_reader_experience": _layer([_chk("C2", "warn", "high")]),
            "D_work_continuity": _layer([_chk("D1", "pass", "high")]),
            "E_craft_quality": _layer([_chk("E1", "pass", "medium")]),
            "F_genre_fitness": _layer([]),
        },
        "editor_notes_for_next_chapter": {"carry_forward_warnings": ["C2 钩子虚标"]},
    }
    report = finalize_audit_report(tmp_path, 7, part1, agent, mode="standard", time_elapsed_seconds=120)

    assert report["decision"] == "approve_with_warnings"
    assert report["decision"] == report["overall_decision"]
    assert set(report["layers"].keys()) == {
        "A_process_integrity", "B_cross_artifact_consistency", "C_reader_experience",
        "D_work_continuity", "E_craft_quality", "F_genre_fitness", "G_cross_chapter_trend",
    }

    disk = json.loads((tmp_path / ".webnovel" / "audit_reports" / "ch0007.json").read_text(encoding="utf-8"))
    assert disk["decision"] == "approve_with_warnings"
    assert disk["editor_notes_for_next_chapter"]["carry_forward_warnings"]

    jsonl = (tmp_path / ".webnovel" / "observability" / "chapter_audit.jsonl").read_text(encoding="utf-8").strip().splitlines()
    row = json.loads(jsonl[-1])
    assert row["chapter"] == 7
    assert row["decision"] == "approve_with_warnings"
    assert row["overall_decision"] == "approve_with_warnings"
    assert row["source"] == "audit_finalize_cli"


def test_finalize_rejects_missing_agent_layer(tmp_path):
    """agent findings 缺 C/D/E/F 任一层 → 拒绝（替代旧自检 2 schema 完整性）。"""
    (tmp_path / ".webnovel").mkdir()
    part1 = {"layers": {"A_process_integrity": _layer([]), "B_cross_artifact_consistency": _layer([]),
                        "F_genre_fitness": _layer([]), "G_cross_chapter_trend": _layer([])}}
    agent = {"layers": {"C_reader_experience": _layer([])}}  # 缺 D/E/F
    try:
        finalize_audit_report(tmp_path, 8, part1, agent, mode="standard", time_elapsed_seconds=10)
        assert False, "缺层应 raise"
    except ValueError as e:
        assert "D_work_continuity" in str(e)
