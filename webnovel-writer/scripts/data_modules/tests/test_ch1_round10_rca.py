#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ch1 末世重生 Round 10 RCA 回归测试 · 2026-04-16

覆盖 Ch1 质量深度审查发现的 5 个 root cause：

RC-1 · consistency-checker 缺金手指激活时序 rubric
    → agents/consistency-checker.md 第三层时间线新增"金手指激活时序交叉校验"

RC-2 · reader-pull-checker 缺大纲爽点兑现 rubric
    → agents/reader-pull-checker.md 新增 SOFT_OUTLINE_PAYOFF + SOFT_SECRET_LEAK
    + Step 5.5 大纲爽点兑现 + 首章核心悬念泄露检查

RC-3 · density-checker 缺首章认知载入量子项
    → agents/density-checker.md 第九步半 Ch1 专用认知载入量

RC-4 · external_review.py 缺 quote 幻觉验证
    → scripts/external_review.py 新增 _verify_quote_exists + _downgrade_severity
    + call_dimension 里对每个 issue 的 quote 做存在性校验

RC-5 · SKILL.md 缺首章专属 rubric 段
    → skills/webnovel-write/SKILL.md 开篇黄金协议加"首章专属审查 rubric"表

本测试锁死代码层修改（RC-4 的 _verify/_downgrade），agent/skill 层改动由
Step 3 重跑时的实际 checker 行为覆盖。
"""

import sys
from pathlib import Path

import pytest


def _ensure_scripts_on_path() -> None:
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def _load_external_review():
    _ensure_scripts_on_path()
    import external_review as module

    return module


# ---------------------------------------------------------------------------
# RC-4.1 · _verify_quote_exists
# ---------------------------------------------------------------------------


def test_verify_quote_exact_match():
    er = _load_external_review()
    text = "陆沉第七次拨通苏灵号码的时候，正跪在合肥地铁二号线大东门站的月台边上。"
    assert er._verify_quote_exists("陆沉第七次拨通苏灵号码的时候", text) is True


def test_verify_quote_ascii_vs_chinese_quotes_normalized():
    er = _load_external_review()
    text = '他说："这次不能再死。"然后放下手。'
    # 外部模型可能返回 ASCII " 的 quote
    assert er._verify_quote_exists('"这次不能再死。"', text) is True


def test_verify_quote_whitespace_normalized():
    er = _load_external_review()
    text = "陆沉   第七次拨通苏灵号码"
    assert er._verify_quote_exists("陆沉第七次拨通苏灵号码", text) is True


def test_verify_quote_punctuation_normalized():
    er = _load_external_review()
    text = "他想笑，笑不出。喉咙里堵着血。"  # 中文逗号
    # 模型返回半角，normalize 后仍应匹配
    assert er._verify_quote_exists("他想笑,笑不出.", text) is True


def test_verify_quote_long_quote_core_substring_fallback():
    er = _load_external_review()
    text = "陆沉第七次拨通苏灵号码的时候，正跪在合肥地铁二号线大东门站的月台边上"
    # long_quote 前 10 字 = "陆沉第七次拨通苏灵号" 吻合 text → 核心 10 字子串回退匹配
    long_quote = "陆沉第七次拨通苏灵号 还带了点尾巴与原文略微不同"
    assert er._verify_quote_exists(long_quote, text) is True


def test_verify_quote_hallucination_detected():
    er = _load_external_review()
    # qwen 实测瞎引 "妹妹那时候在外地读书，他在合肥加班" 不在正文里
    text = "前世这段时间，妹妹打过两个电话。他都在加班，挂了没回。"
    halluc = "妹妹那时候在外地读书，他在合肥加班。"
    assert er._verify_quote_exists(halluc, text) is False


def test_verify_quote_empty_inputs():
    er = _load_external_review()
    assert er._verify_quote_exists("", "some text") is False
    assert er._verify_quote_exists("some quote", "") is False
    assert er._verify_quote_exists(None, "some text") is False


# ---------------------------------------------------------------------------
# RC-4.2 · _downgrade_severity
# ---------------------------------------------------------------------------


def test_downgrade_critical_to_high():
    er = _load_external_review()
    assert er._downgrade_severity("critical") == "high"


def test_downgrade_high_to_medium():
    er = _load_external_review()
    assert er._downgrade_severity("high") == "medium"


def test_downgrade_medium_to_low():
    er = _load_external_review()
    assert er._downgrade_severity("medium") == "low"


def test_downgrade_low_to_info():
    er = _load_external_review()
    assert er._downgrade_severity("low") == "info"


def test_downgrade_info_stays_info():
    er = _load_external_review()
    assert er._downgrade_severity("info") == "info"


def test_downgrade_case_insensitive():
    er = _load_external_review()
    assert er._downgrade_severity("CRITICAL") == "high"
    assert er._downgrade_severity("High") == "medium"


def test_downgrade_unknown_severity_to_info():
    er = _load_external_review()
    assert er._downgrade_severity("xxx") == "info"
    assert er._downgrade_severity("") == "info"
    assert er._downgrade_severity(None) == "info"


# ---------------------------------------------------------------------------
# RC-4.3 · 集成：幻觉 quote → severity 自动降级
# ---------------------------------------------------------------------------


def test_hallucinated_quote_flow_end_to_end():
    """模拟 call_dimension 里那段 issue 增强逻辑。"""
    er = _load_external_review()
    chapter_text = "陆沉第七次拨通苏灵号码的时候，正跪在合肥地铁二号线大东门站的月台边上。"
    # 两个 issue：一个真实 quote，一个幻觉 quote
    real_issue = {
        "id": "C1",
        "severity": "high",
        "quote": "陆沉第七次拨通苏灵号码",
    }
    halluc_issue = {
        "id": "H1",
        "severity": "critical",
        "quote": "妹妹那时候在外地读书，他在合肥加班",
    }
    # 跑 verify + downgrade 逻辑
    for issue in (real_issue, halluc_issue):
        quote = issue.get("quote")
        verified = er._verify_quote_exists(quote, chapter_text)
        issue["quote_verified"] = verified
        if not verified:
            orig = issue["severity"]
            issue["original_severity"] = orig
            issue["severity"] = er._downgrade_severity(orig)
    assert real_issue["quote_verified"] is True
    assert real_issue["severity"] == "high"  # 未改
    assert halluc_issue["quote_verified"] is False
    assert halluc_issue["severity"] == "high"  # critical → high 降级
    assert halluc_issue["original_severity"] == "critical"
