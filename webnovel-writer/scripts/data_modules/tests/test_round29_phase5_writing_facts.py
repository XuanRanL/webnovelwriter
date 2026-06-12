#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 29 Phase 5 · get-writing-facts：context-agent 机械事实由 CLI 产出。

背景：context-agent 伪造字数子区间 3+ 轮复发（Ch9/Ch13）、editor_notes 字数漂移、
time_anchor 承接错位——全是"检索清单太长导致编造"。机械事实（字数 SSOT/进度/
最近章承接/追读处方）改由本 CLI 一次产出，context-agent 只许原样引用。
"""

from data_modules.state_manager import compute_writing_facts


def _state():
    return {
        "project_info": {
            "word_count_policy": {"hard_min": 2200, "hard_max": 3800},
        },
        "progress": {"total_words": 163904},
        "last_completed_chapter": 53,
        "current_chapter": 53,
        "protagonist_state": {"power": "印记Lv2"},
        "chapter_meta": {
            "0052": {"time_anchor": "末世第29天", "end_state": "悬置",
                     "hook_close": {"primary_type": "信息钩"}, "narrative_version": "v3",
                     "thrill_score": {"verdict": "tepid"},
                     "checker_scores": {"reader-critic-checker": 82}},
            "0053": {"time_anchor": "末世第30天", "end_state": "推进",
                     "hook_close": {"primary_type": "情绪钩"}, "narrative_version": "v1",
                     "thrill_score": {"verdict": "tepid"},
                     "checker_scores": {"reader-critic-checker": 82}},
        },
    }


def test_word_policy_from_ssot():
    facts = compute_writing_facts(_state(), 54)
    assert facts["word_count_policy"]["hard_min"] == 2200
    assert facts["word_count_policy"]["hard_max"] == 3800
    assert facts["word_count_policy"]["source"] == "state.project_info.word_count_policy"


def test_word_policy_defaults_when_missing():
    facts = compute_writing_facts({}, 1)
    assert facts["word_count_policy"]["hard_min"] == 2200
    assert facts["word_count_policy"]["hard_max"] == 3800
    assert facts["word_count_policy"]["source"] == "default(Round 21.1)"


def test_recent_chapters_carryover():
    facts = compute_writing_facts(_state(), 54)
    recent = facts["recent_chapters"]
    assert [r["chapter"] for r in recent] == [52, 53]
    assert recent[-1]["time_anchor"] == "末世第30天"
    assert recent[-1]["hook_close_primary"] == "情绪钩"
    assert recent[-1]["narrative_version"] == "v1"


def test_includes_reading_trend_prescriptions():
    facts = compute_writing_facts(_state(), 54)
    assert "reading_trend" in facts
    assert isinstance(facts["reading_trend"]["prescriptions"], list)


def test_progress_and_protagonist_passthrough():
    facts = compute_writing_facts(_state(), 54)
    assert facts["progress"]["total_words"] == 163904
    assert facts["progress"]["last_completed_chapter"] == 53
    assert facts["protagonist_state"] == {"power": "印记Lv2"}
    assert facts["chapter"] == 54


def test_empty_state_safe():
    facts = compute_writing_facts({}, 1)
    assert facts["recent_chapters"] == []
    assert facts["reading_trend"]["prescriptions"] == []
