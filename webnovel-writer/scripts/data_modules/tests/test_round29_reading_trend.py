#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 29 Phase 8 · get-reading-trend 追读力趋势 + 下一章节奏处方。

背景：52 章实测 thrill 分布 thrilling 仅 9/39，Ch51 frustrating / Ch52-53 tepid 连败，
reader-critic 首稿 77/72/68 三连低——但 overall 86-89 看不出来（1/13 稀释）。
趋势信号此前只是报告备注无人消费；本 CLI 把它变成下一章 prep 的结构化处方
（context-agent / arc-review-checker 必读）。
"""

from data_modules.state_manager import compute_reading_trend


def _meta(rows):
    """rows: list of (chapter, thrill_verdict, gf_release, reader_critic, hook_primary)"""
    out = {}
    for ch, verdict, gf, rc, hook in rows:
        m = {}
        if verdict is not None or gf is not None:
            m["thrill_score"] = {"verdict": verdict, "golden_finger_release": gf}
        if rc is not None:
            m["checker_scores"] = {"reader-critic-checker": rc}
        if hook is not None:
            m["hook_close"] = {"primary_type": hook}
        out[f"{ch:04d}"] = m
    return out


def _ids(trend):
    return {p["id"] for p in trend["prescriptions"]}


def test_thrill_release_due_after_3_non_thrilling():
    meta = _meta([
        (50, "thrilling", 88, 86, "决策钩"),
        (51, "frustrating", 35, 86, "动作钩"),
        (52, "tepid", 40, 86, "信息钩"),
        (53, "tepid", 45, 86, "情绪钩"),
    ])
    trend = compute_reading_trend(meta)
    assert trend["non_thrilling_streak"] == 3
    assert "THRILL_RELEASE_DUE" in _ids(trend)


def test_thrilling_tail_clears_release_prescription():
    meta = _meta([
        (51, "tepid", 40, 86, "动作钩"),
        (52, "tepid", 45, 86, "信息钩"),
        (53, "thrilling", 85, 86, "情绪钩"),
    ])
    trend = compute_reading_trend(meta)
    assert trend["non_thrilling_streak"] == 0
    assert "THRILL_RELEASE_DUE" not in _ids(trend)


def test_emotion_hook_drought_over_8_chapters():
    rows = [(40 + i, "neutral", None, 86, "决策钩" if i % 2 else "信息钩") for i in range(8)]
    trend = compute_reading_trend(_meta(rows))
    assert trend["no_emotion_hook_8"] is True
    assert "EMOTION_HOOK_DUE" in _ids(trend)


def test_hook_shape_vary_when_last_two_same():
    meta = _meta([
        (51, None, None, 86, "决策钩"),
        (52, None, None, 86, "动作钩"),
        (53, None, None, 86, "动作钩"),
    ])
    trend = compute_reading_trend(meta)
    assert "HOOK_SHAPE_VARY" in _ids(trend)


def test_reading_line_polish_priority_on_rc_streak():
    meta = _meta([
        (51, None, None, 84, "决策钩"),
        (52, None, None, 82, "信息钩"),
        (53, None, None, 80, "情绪钩"),
    ])
    trend = compute_reading_trend(meta)
    assert trend["rc_below_85_streak"] == 3
    assert "READING_LINE_POLISH_PRIORITY" in _ids(trend)
    # rc 85+ 打断连败
    meta2 = _meta([
        (52, None, None, 82, "信息钩"),
        (53, None, None, 90, "情绪钩"),
    ])
    assert "READING_LINE_POLISH_PRIORITY" not in _ids(compute_reading_trend(meta2))


def test_empty_meta_no_crash():
    trend = compute_reading_trend({})
    assert trend["prescriptions"] == []
    assert trend["non_thrilling_streak"] == 0
