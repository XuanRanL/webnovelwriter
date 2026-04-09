#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审查 schema 测试"""
import pytest
from data_modules.review_schema import ReviewIssue, ReviewResult, parse_review_output


def test_review_issue_blocking_defaults():
    """critical severity 默认 blocking=True"""
    issue = ReviewIssue(
        severity="critical",
        category="continuity",
        location="第3段",
        description="主角使用了已失去的能力",
    )
    assert issue.blocking is True


def test_review_issue_non_critical_not_blocking():
    """非 critical 默认 blocking=False"""
    issue = ReviewIssue(
        severity="high",
        category="setting",
        location="第7段",
        description="时间线矛盾",
    )
    assert issue.blocking is False


def test_review_result_counts():
    """blocking_count 自动计算"""
    result = ReviewResult(
        chapter=10,
        issues=[
            ReviewIssue(severity="critical", category="continuity", location="p1", description="d1"),
            ReviewIssue(severity="high", category="setting", location="p2", description="d2"),
            ReviewIssue(severity="high", category="timeline", location="p3", description="d3", blocking=True),
        ],
        summary="测试",
    )
    assert result.blocking_count == 2
    assert result.issues_count == 3
    assert result.has_blocking is True


def test_review_result_no_issues():
    result = ReviewResult(chapter=10, issues=[], summary="无问题")
    assert result.blocking_count == 0
    assert result.has_blocking is False


def test_review_result_to_dict_roundtrip():
    result = ReviewResult(
        chapter=10,
        issues=[
            ReviewIssue(severity="medium", category="ai_flavor", location="p5", description="AI味重",
                        evidence="'稳住心神'出现3次", fix_hint="替换为具体动作描写"),
        ],
        summary="1个AI味问题",
    )
    d = result.to_dict()
    assert d["chapter"] == 10
    assert d["blocking_count"] == 0
    assert len(d["issues"]) == 1
    assert d["issues"][0]["category"] == "ai_flavor"
    assert d["issues"][0]["fix_hint"] == "替换为具体动作描写"


def test_parse_review_output_from_dict():
    raw = {
        "issues": [
            {"severity": "critical", "category": "continuity", "location": "p1",
             "description": "矛盾", "evidence": "证据", "fix_hint": "修复"},
        ],
        "summary": "1个严重问题",
    }
    result = parse_review_output(chapter=5, raw=raw)
    assert result.chapter == 5
    assert result.blocking_count == 1


def test_parse_review_output_tolerates_missing_fields():
    raw = {
        "issues": [
            {"severity": "low", "description": "小问题"},
        ],
        "summary": "轻微",
    }
    result = parse_review_output(chapter=1, raw=raw)
    assert result.issues[0].category == "other"
    assert result.issues[0].location == ""


def test_review_result_to_metrics_dict():
    result = ReviewResult(
        chapter=10,
        issues=[
            ReviewIssue(severity="critical", category="continuity", location="p1", description="d1"),
            ReviewIssue(severity="high", category="ai_flavor", location="p2", description="d2"),
        ],
        summary="测试",
    )
    metrics = result.to_metrics_dict()
    assert metrics["chapter"] == 10
    assert metrics["start_chapter"] == 10
    assert metrics["end_chapter"] == 10
    assert metrics["issues_count"] == 2
    assert metrics["blocking_count"] == 1
    assert "continuity" in metrics["categories"]
    assert "ai_flavor" in metrics["categories"]
    assert metrics["severity_counts"]["critical"] == 1
    assert metrics["severity_counts"]["high"] == 1
    assert metrics["critical_issues"] == ["d1"]
    assert metrics["report_file"] == ""
    assert metrics["overall_score"] < 100
    assert metrics["dimension_scores"]["continuity"] < 100
    assert metrics["dimension_scores"]["ai_flavor"] < 100
