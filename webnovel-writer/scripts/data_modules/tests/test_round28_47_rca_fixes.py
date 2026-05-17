"""Round 28.47 · Ch47 RCA · 17 项 bug + 7 类根因永久根治测试.

测试范围:
- Fix 1: PROTECTED_FIELDS 扩 5 字段 (hook_close / dialogue_ratio / signature_density / external_avg / reader_thrill_score)
- Fix 1 加强: incoming=None 但 existing 有值时保留 existing (防 R28.46 复发)
- Fix 2: chapter_audit CLI jsonl 加 decision + overall_decision + elapsed_ms 字段
- Fix 3: HOOK_ALIASES 加 行动钩→动作钩 / 发现钩→信息钩 映射

根因: Ch47 流程审计发现 R28.46 hook_close 副作用复发 + secondary_type=None 静默丢失 + jsonl schema 不一致
血教训: data-agent process-chapter merge 时不带 key → existing 真源被丢. R28.46 已修过但只对部分字段
"""
import json
import os
import sys
import inspect
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"


def _ensure_scripts_on_path():
    p = str(SCRIPTS_DIR)
    if p not in sys.path:
        sys.path.insert(0, p)


def _make_project_with_ch47_meta(tmp_path):
    """构造 .webnovel/state.json 含 Ch47 完整 chapter_meta."""
    pr = tmp_path / "book"
    (pr / ".webnovel").mkdir(parents=True)
    (pr / "正文").mkdir()
    state = {
        "project_info": {
            "name": "test",
            "word_count_policy": {"hard_min": 2200, "hard_max": 3800},
        },
        "chapter_meta": {
            "0047": {
                "chapter": 47,
                "word_count": 3044,
                "overall_score": 87,
                "narrative_version": "v1",
                "checker_scores": {"overall": 87, "consistency-checker": 88},
                "post_polish_recheck": {"reader-critic-checker": {"before": 72, "after": 86}},
                "thrill_score": {"overall": 71, "verdict": "neutral"},
                "hook_close": {
                    "primary_type": "决策钩",
                    "text_excerpt": "明早六点把那条线再过一遍",
                    "source_narrative_version": "v1",
                },
                "dialogue_ratio": 0.289,
                "signature_density": {"了一X": 5, "那一X": 1, "没X": 8},
                "external_avg": 85.68,
                "reader_thrill_score": 71,
            },
        },
        "progress": {"current_chapter": 47, "total_words": 0},
        "last_completed_chapter": 47,
        "current_chapter": 47,
        "entities_v3": {},
    }
    (pr / ".webnovel" / "state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return pr


def _make_manager(tmp_path):
    _ensure_scripts_on_path()
    from data_modules import state_manager as sm
    from data_modules.config import DataModulesConfig

    pr = _make_project_with_ch47_meta(tmp_path)
    config = DataModulesConfig.from_project_root(pr)
    manager = sm.StateManager(config)
    return pr, manager


# ---------- Fix 1: PROTECTED_FIELDS 扩 5 字段 ----------

def test_fix1_hook_close_preserved_when_incoming_missing(tmp_path):
    """R28.47 Fix 1: data-agent 不带 hook_close → existing 保留 (防 R28.46 复发)."""
    pr, manager = _make_manager(tmp_path)

    # 模拟 data-agent process-chapter, 不含 hook_close
    result = {
        "entities_appeared": [],
        "entities_new": [],
        "state_changes": [],
        "relationships_new": [],
        "uncertain": [],
        "chapter_meta": {"word_count": 3044, "scene_count": 6},  # hook_close 缺失
    }
    warnings = manager.process_chapter_result(47, result)

    actual = manager._state["chapter_meta"]["0047"]
    assert actual.get("hook_close") is not None, "FAIL: hook_close 被 R28.46 复发丢失"
    assert actual["hook_close"]["primary_type"] == "决策钩"
    # 必须有 hook_close 相关 warning (旧分支命中, 因为 incoming=None 时 chapter_meta.get 返回 None 已被旧分支处理)
    assert any("hook_close" in w for w in warnings), \
        f"FAIL: 未生成 hook_close 保护 warning, warnings={warnings}"


def test_fix1_dialogue_ratio_protected(tmp_path):
    """R28.47 Fix 1: LLM 自估错值 dialogue_ratio (0.476) 被真源 (0.289) 保留."""
    pr, manager = _make_manager(tmp_path)

    result = {
        "entities_appeared": [], "entities_new": [], "state_changes": [],
        "relationships_new": [], "uncertain": [],
        "chapter_meta": {"word_count": 3044, "dialogue_ratio": 0.476},
    }
    manager.process_chapter_result(47, result)

    actual = manager._state["chapter_meta"]["0047"]
    assert actual["dialogue_ratio"] == 0.289, \
        f"FAIL: dialogue_ratio 真源被 LLM 自估覆盖, 实际={actual['dialogue_ratio']}"


def test_fix1_signature_density_protected(tmp_path):
    """R28.47 Fix 1: signature_density 真源保护."""
    pr, manager = _make_manager(tmp_path)

    result = {
        "entities_appeared": [], "entities_new": [], "state_changes": [],
        "relationships_new": [], "uncertain": [],
        "chapter_meta": {"signature_density": {"了一X": 50}},  # 错估
    }
    manager.process_chapter_result(47, result)

    actual = manager._state["chapter_meta"]["0047"]
    assert actual["signature_density"]["了一X"] == 5, \
        "FAIL: signature_density 真源被覆盖"


def test_fix1_thrill_score_preserved_when_missing(tmp_path):
    """R28.47 Fix 1: thrill_score 真源保护 + incoming 缺失防御."""
    pr, manager = _make_manager(tmp_path)

    result = {
        "entities_appeared": [], "entities_new": [], "state_changes": [],
        "relationships_new": [], "uncertain": [],
        "chapter_meta": {"word_count": 3044},  # thrill_score 缺失
    }
    manager.process_chapter_result(47, result)

    actual = manager._state["chapter_meta"]["0047"]
    assert actual["thrill_score"]["overall"] == 71, "FAIL: thrill_score 被丢"


# ---------- Fix 3: HOOK_ALIASES 加 行动钩 ----------

def test_fix3_hook_alias_xingdongou_mapped_primary(tmp_path):
    """R28.47 Fix 3: 行动钩 (高频简称) → 动作钩 别名映射 (primary)."""
    _ensure_scripts_on_path()
    from data_modules import state_manager as sm
    pr = _make_project_with_ch47_meta(tmp_path)

    # 检查源码已含 别名 (核心断言)
    src = inspect.getsource(sm)
    # 找到 HOOK_ALIASES_PRIMARY 块
    start = src.find('HOOK_ALIASES_PRIMARY = {')
    assert start > 0, "HOOK_ALIASES_PRIMARY 定义未找到"
    end = src.find('}', start)
    block = src[start:end]
    assert '"行动钩": "动作钩"' in block, \
        "FAIL: R28.47 Fix 3 未应用 - HOOK_ALIASES_PRIMARY 缺 行动钩→动作钩"
    assert '"发现钩": "信息钩"' in block, \
        "FAIL: R28.47 Fix 3 未应用 - HOOK_ALIASES_PRIMARY 缺 发现钩→信息钩"


def test_fix3_hook_alias_xingdongou_mapped_secondary(tmp_path):
    """R28.47 Fix 3: secondary HOOK_ALIASES 也加 行动钩."""
    _ensure_scripts_on_path()
    from data_modules import state_manager as sm
    src = inspect.getsource(sm)
    # 找到 HOOK_ALIASES (secondary) 定义
    start = src.find('HOOK_ALIASES = {')
    assert start > 0, "HOOK_ALIASES (secondary) 定义未找到"
    end = src.find('}', start)
    block = src[start:end]
    assert '"行动钩": "动作钩"' in block, \
        "FAIL: R28.47 Fix 3 - secondary HOOK_ALIASES 缺 行动钩→动作钩"


# ---------- Fix 2: chapter_audit CLI jsonl schema ----------

def test_fix2_audit_cli_jsonl_decision_field():
    """R28.47 Fix 2: audit CLI jsonl 必须含 decision + overall_decision + elapsed_ms."""
    src = (SCRIPTS_DIR / "data_modules" / "chapter_audit.py").read_text(encoding="utf-8")
    # 找到 _cmd_chapter 函数体
    cmd_idx = src.find("def _cmd_chapter(args)")
    assert cmd_idx > 0
    # 取该函数到下一个 def 之间
    next_def = src.find("\ndef ", cmd_idx + 1)
    body = src[cmd_idx:next_def] if next_def > 0 else src[cmd_idx:]
    assert '"decision": report["cli_decision"]' in body, \
        "FAIL: Fix 2 未应用 - jsonl write 缺 decision 字段"
    assert '"overall_decision": report["cli_decision"]' in body, \
        "FAIL: Fix 2 未应用 - jsonl write 缺 overall_decision 字段"
    assert '"elapsed_ms": audit_elapsed_ms' in body, \
        "FAIL: Fix 2 未应用 - jsonl write 缺 elapsed_ms 字段"
    assert "audit_start_ts = time.time()" in body, \
        "FAIL: Fix 2 未应用 - timing 未启动"


# ---------- Meta tests · 防回归 ----------

def test_protected_fields_count_after_round28_47():
    """元测试: PROTECTED_FIELDS 在 R28.47 后必须含全部 16 个字段."""
    src = (SCRIPTS_DIR / "data_modules" / "state_manager.py").read_text(encoding="utf-8")
    # 找到 PROTECTED_FIELDS = ( 后的 ) 闭合 (允许 inline 注释存在)
    start = src.find('PROTECTED_FIELDS = (')
    assert start > 0
    # 真正的 closing ) 在 ',\n            )' 上 (考虑缩进)
    cursor = start
    paren_depth = 0
    end = -1
    while cursor < len(src):
        c = src[cursor]
        if c == '(':
            paren_depth += 1
        elif c == ')':
            paren_depth -= 1
            if paren_depth == 0:
                end = cursor
                break
        cursor += 1
    assert end > start
    block = src[start:end + 1]
    expected = ("checker_scores", "post_polish_recheck", "overall_score", "review_score",
                "naturalness_verdict", "naturalness_score", "reader_critic_verdict",
                "reader_critic_score", "thrill_score", "narrative_version", "polish_log",
                # R28.47 新增 5 个
                "hook_close", "dialogue_ratio", "signature_density", "external_avg",
                "reader_thrill_score")
    for f in expected:
        assert f'"{f}"' in block, f"FAIL: PROTECTED_FIELDS 缺字段 {f}"
