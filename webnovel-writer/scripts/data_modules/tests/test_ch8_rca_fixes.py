#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ch8 RCA 回归测试 · 2026-04-16

覆盖 Ch1 (末世重生) 暴露的 root cause：

**RC · chapter_meta.checker_scores 中文 key vs canonical 英文 key 不一致**

症状：末世重生 Ch1 的 state.json checker_scores 写成：
    {"设定一致性": 93, "连贯性": 94, "节奏": 92, "对话": 91, "爽点密度": 93,
     "钩子强度": 93, "情绪曲线": 91, "伏笔埋设": 94, "Prose质量": 90, "Anti-AI": 91}
但 chapter_audit.py 只认 CHECKER_NAMES (consistency-checker 等英文 canonical)。
chapter_audit silent fallback 到报告文本匹配，audit 不报警，用户永远不知道 state 数据烂了。

根因：data-agent.md:557,623 官方示例教 AI 写中文 key `{"设定一致性": 82}`，
而代码侧只认英文 canonical。文档/代码 schema 割裂 → AI 照文档写 → audit 按代码读 → 永不匹配。

根治：
  1. CHECKER_ALIASES 扩充中文/legacy/简写别名
  2. normalize_checker_scores_keys() 反向映射 + 检测 banned/unknown
  3. chapter_audit A2 发 warning (severity=high) 当 state 含非 canonical key
  4. hygiene_check H18 P1 canonical 校验
  5. webnovel.py normalize-checker-scores CLI 一次性修复 legacy 数据
  6. data-agent.md 示例改英文 canonical

测试矩阵：
  - normalize canonical 原样保留
  - normalize 中文别名（设定一致性 → consistency-checker）
  - normalize legacy 别名（钩子强度 → reader-pull-checker, 伏笔埋设 → consistency-checker）
  - banned key 丢弃（Anti-AI → BANNED）
  - unknown key 丢弃（乱七八糟 → UNKNOWN）
  - collision 检测（两个 alias 指向同一 canonical）
  - reserved key 保留（overall 不动）
  - 空/非 dict 输入 graceful
"""

import json
import sys
from pathlib import Path

import pytest


def _ensure_scripts_on_path() -> None:
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def _load_audit_module():
    _ensure_scripts_on_path()
    import data_modules.chapter_audit as module

    return module


# ---------------------------------------------------------------------------
# normalize_checker_scores_keys — core normalizer
# ---------------------------------------------------------------------------


def test_normalize_canonical_keys_untouched():
    audit = _load_audit_module()
    src = {
        "consistency-checker": 90,
        "continuity-checker": 91,
        "flow-checker": 88,
        "overall": 90,
    }
    out, renamed, invalid = audit.normalize_checker_scores_keys(src)
    assert out == src
    assert renamed == []
    assert invalid == []


def test_normalize_chinese_aliases_mapped():
    audit = _load_audit_module()
    src = {
        "设定一致性": 92,
        "连贯性": 91,
        "人物塑造": 88,
        "追读力": 94,
        "爽点密度": 89,
        "节奏控制": 90,
        "对话质量": 91,
        "信息密度": 97,
        "文笔质感": 92,
        "情感表现": 95,
        "读者流畅度": 88,
    }
    out, renamed, invalid = audit.normalize_checker_scores_keys(src)
    assert invalid == []
    expected_canonical = {
        "consistency-checker": 92,
        "continuity-checker": 91,
        "ooc-checker": 88,
        "reader-pull-checker": 94,
        "high-point-checker": 89,
        "pacing-checker": 90,
        "dialogue-checker": 91,
        "density-checker": 97,
        "prose-quality-checker": 92,
        "emotion-checker": 95,
        "flow-checker": 88,
    }
    assert out == expected_canonical
    assert len(renamed) == 11


def test_normalize_legacy_shorthand_mapped():
    audit = _load_audit_module()
    # Ch1 实际 state.json 的烂数据
    src = {
        "节奏": 92,
        "对话": 91,
        "情绪曲线": 91,
        "Prose质量": 90,
        "钩子强度": 93,
    }
    out, renamed, invalid = audit.normalize_checker_scores_keys(src)
    assert invalid == []
    assert out == {
        "pacing-checker": 92,
        "dialogue-checker": 91,
        "emotion-checker": 91,
        "prose-quality-checker": 90,
        "reader-pull-checker": 93,
    }
    assert len(renamed) == 5


def test_normalize_banned_anti_ai_dropped():
    audit = _load_audit_module()
    src = {"consistency-checker": 90, "Anti-AI": 88}
    out, renamed, invalid = audit.normalize_checker_scores_keys(src)
    assert out == {"consistency-checker": 90}
    assert "BANNED:Anti-AI" in invalid


def test_normalize_banned_case_insensitive():
    audit = _load_audit_module()
    for banned_variant in ("anti-ai", "anti_ai", "naturalness", "naturalness_veto"):
        _, _, invalid = audit.normalize_checker_scores_keys({banned_variant: 50})
        assert invalid, f"应该拒 {banned_variant}"
        assert any(banned_variant.lower() in i.lower() or banned_variant in i for i in invalid)


def test_normalize_unknown_key_dropped():
    audit = _load_audit_module()
    src = {"consistency-checker": 90, "乱七八糟": 70, "xyz": 80}
    out, _, invalid = audit.normalize_checker_scores_keys(src)
    assert out == {"consistency-checker": 90}
    assert "UNKNOWN:乱七八糟" in invalid
    assert "UNKNOWN:xyz" in invalid


def test_normalize_collision_detected():
    audit = _load_audit_module()
    # 设定一致性 和 伏笔埋设 都映射到 consistency-checker
    src = {"设定一致性": 93, "伏笔埋设": 94}
    out, renamed, invalid = audit.normalize_checker_scores_keys(src)
    assert out == {"consistency-checker": 94}  # 后者覆盖前者
    assert any("COLLISION" in i for i in invalid)


def test_normalize_reserved_overall_preserved():
    audit = _load_audit_module()
    src = {"consistency-checker": 90, "overall": 92}
    out, _, _ = audit.normalize_checker_scores_keys(src)
    assert out["overall"] == 92


def test_normalize_empty_input_graceful():
    audit = _load_audit_module()
    assert audit.normalize_checker_scores_keys({}) == ({}, [], [])
    assert audit.normalize_checker_scores_keys(None) == ({}, [], [])
    assert audit.normalize_checker_scores_keys("not a dict") == ({}, [], [])
    assert audit.normalize_checker_scores_keys([1, 2, 3]) == ({}, [], [])


def test_normalize_ch1_real_data_shape():
    """锁死末世重生 Ch1 原始烂数据的修复 shape。"""
    audit = _load_audit_module()
    ch1_raw = {
        "设定一致性": 93,
        "连贯性": 94,
        "节奏": 92,
        "对话": 91,
        "爽点密度": 93,
        "钩子强度": 93,
        "情绪曲线": 91,
        "伏笔埋设": 94,
        "Prose质量": 90,
        "Anti-AI": 91,
    }
    out, renamed, invalid = audit.normalize_checker_scores_keys(ch1_raw)
    # 9/10 能映射（伏笔埋设 collision 到 consistency-checker）
    assert len(renamed) == 9
    # 2 个异常：COLLISION + BANNED
    assert len(invalid) == 2
    assert any("BANNED:Anti-AI" in i for i in invalid)
    assert any("COLLISION" in i for i in invalid)
    # After: 8 个 canonical（伏笔埋设 94 覆盖 设定一致性 93）
    assert len(out) == 8
    assert out["consistency-checker"] == 94  # 后者胜
    assert "Anti-AI" not in out
    assert "ooc-checker" not in out  # 原本就没
    assert "density-checker" not in out  # 原本就没
    assert "flow-checker" not in out  # 原本就没


# ---------------------------------------------------------------------------
# CHECKER_ALIASES structural invariants
# ---------------------------------------------------------------------------


def test_checker_aliases_covers_all_canonical():
    audit = _load_audit_module()
    assert set(audit.CHECKER_ALIASES.keys()) == set(audit.CHECKER_NAMES)


def test_checker_aliases_no_duplicate_alias_across_canonicals():
    """同一 alias 不能同时属于两个 canonical checker（否则反查不唯一）。"""
    audit = _load_audit_module()
    alias_to_canonicals: dict = {}
    for canonical, aliases in audit.CHECKER_ALIASES.items():
        for a in aliases:
            alias_to_canonicals.setdefault(a, []).append(canonical)
    conflicts = {a: cs for a, cs in alias_to_canonicals.items() if len(cs) > 1}
    assert not conflicts, f"alias 不能指向多个 canonical: {conflicts}"


def test_checker_aliases_includes_key_legacy_terms():
    """锁死 Ch1 实际碰到的 legacy 别名都能被映射。"""
    audit = _load_audit_module()
    must_cover = {
        "设定一致性": "consistency-checker",
        "连贯性": "continuity-checker",
        "节奏": "pacing-checker",
        "对话": "dialogue-checker",
        "钩子强度": "reader-pull-checker",
        "情绪曲线": "emotion-checker",
        "伏笔埋设": "consistency-checker",  # legacy: 伏笔埋设是 consistency 的子项
        "Prose质量": "prose-quality-checker",
    }
    for alias, expected_canonical in must_cover.items():
        canonical = audit._CHECKER_ALIAS_TO_CANONICAL.get(alias)
        assert canonical == expected_canonical, f"{alias} 应映射到 {expected_canonical}, 实际 {canonical}"


def test_banned_keys_include_anti_ai():
    audit = _load_audit_module()
    assert "Anti-AI" in audit.CHECKER_SCORES_BANNED_KEYS


# ---------------------------------------------------------------------------
# hygiene_check H18 integration
# ---------------------------------------------------------------------------


def _write_minimal_state(root: Path, checker_scores: dict) -> None:
    (root / ".webnovel").mkdir(parents=True, exist_ok=True)
    state = {
        "chapter_meta": {
            "0001": {
                "chapter": 1,
                "title": "t",
                "word_count": 100,
                "summary": "s",
                "hook_strength": "strong",
                "scene_count": 1,
                "key_beats": ["b"],
                "characters": ["c"],
                "locations": ["l"],
                "created_at": "2026-01-01",
                "updated_at": "2026-01-01",
                "protagonist_state": "s",
                "location_current": "l",
                "power_realm": "r",
                "golden_finger_level": 0,
                "time_anchor": "t",
                "end_state": "e",
                "foreshadowing_planted": [],
                "foreshadowing_paid": [],
                "strand_dominant": "quest",
                "review_score": 90,
                "checker_scores": checker_scores,
                "allusions_used": [],
            }
        }
    }
    (root / ".webnovel" / "state.json").write_text(
        json.dumps(state, ensure_ascii=False), encoding="utf-8"
    )


def test_hygiene_H18_canonical_passes(tmp_path: Path):
    _ensure_scripts_on_path()
    import hygiene_check as hc

    _write_minimal_state(tmp_path, {"consistency-checker": 90, "overall": 90})
    rep = hc.HygieneReport()
    hc.check_checker_scores_canonical(tmp_path, 1, rep)
    # All clean — one pass recorded, no fails
    assert "H18" in rep.passes


def test_hygiene_H18_chinese_alias_passes_with_warning_noted(tmp_path: Path):
    _ensure_scripts_on_path()
    import hygiene_check as hc

    _write_minimal_state(tmp_path, {"设定一致性": 90, "overall": 90})
    rep = hc.HygieneReport()
    hc.check_checker_scores_canonical(tmp_path, 1, rep)
    # 中文别名是合法但不推荐 → record pass (audit 会 normalize)
    assert "H18" in rep.passes


def test_hygiene_H18_banned_key_fails(tmp_path: Path):
    _ensure_scripts_on_path()
    import hygiene_check as hc

    _write_minimal_state(tmp_path, {"Anti-AI": 88, "overall": 88})
    rep = hc.HygieneReport()
    hc.check_checker_scores_canonical(tmp_path, 1, rep)
    # Anti-AI 是 banned → P1 fail
    assert rep.p1_fails, "H18 应该 P1 fail"
    assert any("H18" in f for f in rep.p1_fails)


def test_hygiene_H18_unknown_key_fails(tmp_path: Path):
    _ensure_scripts_on_path()
    import hygiene_check as hc

    _write_minimal_state(tmp_path, {"乱七八糟": 80, "overall": 80})
    rep = hc.HygieneReport()
    hc.check_checker_scores_canonical(tmp_path, 1, rep)
    assert any("H18" in f for f in rep.p1_fails)


# ---------------------------------------------------------------------------
# chapter_audit A2 uses normalized scores
# ---------------------------------------------------------------------------


def test_chapter_audit_A2_uses_normalized_count(tmp_path: Path, monkeypatch):
    """验证 check_A2 读取 checker_scores 时用 normalize，不再 silent fail。"""
    audit = _load_audit_module()
    # 不直接跑 check_A2（依赖太多 Path/Report 文件），只验 normalize 返回正确
    # ——整合测试锁在 test_chapter_audit.py 已有 fixture，这里只回归 normalizer 本身
    raw = {"设定一致性": 90, "连贯性": 91}
    out, renamed, invalid = audit.normalize_checker_scores_keys(raw)
    state_count = len([k for k, v in out.items()
                       if v is not None and k not in audit.CHECKER_SCORES_RESERVED_KEYS])
    assert state_count == 2
    assert len(renamed) == 2
