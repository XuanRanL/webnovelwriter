#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 13 v2 架构一致性回归 · 2026-04-16

问题背景：每次 checker/维度数量升级都会留一大堆"只改主路径没改引用路径"的漂移：

- Round 6 commit 说"10→11 同步（9 处）"，实测 >15 处未改，导致 Ch6 只跑 10 个
- Round 13 v2 commit 说"13 维度同步，grep 清零"，实测 external-review-agent.md / step-3.5 prompt / step-6 矩阵 / SKILL dimension_scores 示例等 >14 处仍是 11

根因是**真源多份 hardcode 副本**：CHECKER_NAMES 一份在 chapter_audit、一份在 external_review，
prompt 模板和 agent description 只是 naked 字符串，没有人机制强制一致。

本测试锁死几组跨文件一致性断言，改错任何一处立刻 fail。保证以后 Round 升级必须真正全量改完。

覆盖维度：
1. 内部 checker 数量 == 外部 dimensions 数量（都应是 13）
2. workflow_manager.REQUIRED_ARTIFACT_FIELDS["Step 3"] 含 8 个新架构字段
3. hygiene_check 实际共享 workflow_manager 的常量（import 不是副本）
4. 关键文档里的数字必须是 13 而非 11/12（prompt 模板 / agent description / audit 矩阵）
5. 9×dimensions 乘积表达必须数学正确（117 份评分而非 99）
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest


def _ensure_scripts_on_path() -> None:
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def _plugin_root() -> Path:
    return Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# 1. 代码常量一致性（真源）
# ---------------------------------------------------------------------------


def test_internal_checker_count_matches_external_dimensions():
    """内部 checker 数量必须等于外部维度数量；Round 13 v2 = 13。"""
    _ensure_scripts_on_path()
    from data_modules.chapter_audit import (
        CHECKER_NAMES,
        EXTERNAL_REVIEW_EXPECTED_DIMENSIONS,
    )
    import external_review

    internal = len(CHECKER_NAMES)
    external = EXTERNAL_REVIEW_EXPECTED_DIMENSIONS
    dimensions_dict = len(external_review.DIMENSIONS)

    assert internal == external == dimensions_dict, (
        f"三真源数字漂移: CHECKER_NAMES={internal} / "
        f"EXTERNAL_REVIEW_EXPECTED_DIMENSIONS={external} / "
        f"external_review.DIMENSIONS={dimensions_dict}"
    )
    assert internal == 13, f"Round 13 v2 架构应为 13 checker，实为 {internal}"


def test_canonical_checker_names_contains_round13_v2_pair():
    """Round 13 v2 新加的两个读者视角 checker 必须在 CHECKER_NAMES 里。"""
    _ensure_scripts_on_path()
    from data_modules.chapter_audit import CHECKER_NAMES

    assert "reader-naturalness-checker" in CHECKER_NAMES
    assert "reader-critic-checker" in CHECKER_NAMES


def test_external_dimensions_contains_reader_visual_pair():
    """外部维度必须含 naturalness + reader_critic + reader_flow。"""
    _ensure_scripts_on_path()
    import external_review

    names = set(external_review.DIMENSIONS.keys())
    for required in ("naturalness", "reader_critic", "reader_flow"):
        assert required in names, f"external_review.DIMENSIONS 缺 {required}: {names}"


# ---------------------------------------------------------------------------
# 2. hygiene_check 与 workflow_manager 共享常量（import 而非副本）
# ---------------------------------------------------------------------------


def test_hygiene_check_imports_from_workflow_manager():
    """hygiene_check.REQUIRED_ARTIFACT_FIELDS 必须是 workflow_manager 的同一对象。

    Ch7 RCA 发现 hygiene 本地副本漏更新导致两闸门不同步。Round 13 v2 RCA 改为
    import 共享，这里锁死防退化。
    """
    _ensure_scripts_on_path()
    import hygiene_check
    import workflow_manager

    assert hygiene_check.REQUIRED_ARTIFACT_FIELDS is workflow_manager.REQUIRED_ARTIFACT_FIELDS, (
        "hygiene_check.REQUIRED_ARTIFACT_FIELDS 必须 is workflow_manager 的对象，不得本地副本"
    )
    assert hygiene_check.PLACEHOLDER_ONLY_FIELDS is workflow_manager.PLACEHOLDER_ONLY_FIELDS
    assert hygiene_check._is_semantically_empty is workflow_manager._is_semantically_empty


def test_step3_whitelist_has_round13_v2_fields():
    """Step 3 artifact 白名单必须含 Round 13 v2 的 4 个读者视角字段。"""
    _ensure_scripts_on_path()
    import workflow_manager

    step3 = set(workflow_manager.REQUIRED_ARTIFACT_FIELDS["webnovel-write"]["Step 3"])
    required = {
        "naturalness_verdict",
        "naturalness_score",
        "reader_critic_verdict",
        "reader_critic_score",
    }
    missing = required - step3
    assert not missing, f"Step 3 白名单缺 Round 13 v2 字段: {missing}"


# ---------------------------------------------------------------------------
# 3. 活规则文档不得含过时数字（11/12 checker/维度 · 限定于当前硬规则文件）
# ---------------------------------------------------------------------------


# 活规则文件：这些文件描述"现在"的架构，不得出现过时数字。
# 排除 CUSTOMIZATIONS.md（历史记录）和 tests/（测试数据）。
LIVE_RULE_FILES = [
    "agents/external-review-agent.md",
    "skills/webnovel-write/references/step-3.5-external-review.md",
    "skills/webnovel-write/references/step-6-audit-matrix.md",
    "skills/webnovel-write/references/step-6-audit-gate.md",
    "skills/webnovel-resume/references/workflow-resume.md",
]

# 过时表达 → 在活规则文件中出现即为 bug。
# Round 13 v2 应是 13 checker / 13 维度。
OBSOLETE_PATTERNS = [
    r"\b11\s*(个)?\s*维度",
    r"\b11\s*(个)?\s*dimension",
    r"\b11\s*(个)?\s*checker\b",
    r"\b12\s*(个)?\s*checker\b",
    r"9\s*模型\s*[×x]\s*11\s*维度",
    r"9\s*模型\s*[×x]\s*12\s*维度",
    r"9\s*[×x]\s*11",
    r"9\s*[×x]\s*12",
]


@pytest.mark.parametrize("rel_path", LIVE_RULE_FILES)
def test_live_rule_docs_no_obsolete_counter(rel_path: str):
    """活规则文档不得含过时的 11/12 checker|维度 表达。

    历史背景见 CUSTOMIZATIONS.md Round 6 / Round 13 v2 的 counter 漂移事故。
    """
    path = _plugin_root() / rel_path
    if not path.exists():
        pytest.skip(f"{rel_path} 不存在，跳过")
    text = path.read_text(encoding="utf-8")
    hits = []
    for pattern in OBSOLETE_PATTERNS:
        for match in re.finditer(pattern, text):
            line_no = text[: match.start()].count("\n") + 1
            hits.append(f"L{line_no}: `{match.group(0)}` (pattern={pattern})")
    assert not hits, (
        f"{rel_path} 含 Round 13 v2 过时数字（应为 13 checker / 13 维度）:\n  "
        + "\n  ".join(hits)
    )


def test_external_review_prompt_uses_13_dimensions():
    """step-3.5-external-review.md 的 system prompt 必须让外部模型打 13 个维度。"""
    path = (
        _plugin_root()
        / "skills"
        / "webnovel-write"
        / "references"
        / "step-3.5-external-review.md"
    )
    text = path.read_text(encoding="utf-8")
    # Must contain "13个维度" or "13 个维度"
    assert re.search(r"13\s*个?\s*维度", text), (
        "step-3.5-external-review.md 的 prompt 模板必须明确说 13 个维度"
    )
    # Must list all three reader-perspective dims
    for dim in ("reader_flow", "naturalness", "reader_critic"):
        assert dim in text, f"prompt 模板缺维度 {dim}"


def test_external_review_agent_desc_uses_13_dimensions():
    """external-review-agent.md description 必须说 13 维度。"""
    path = _plugin_root() / "agents" / "external-review-agent.md"
    text = path.read_text(encoding="utf-8")
    # Description line should say 13
    desc_match = re.search(r"description:\s*外部模型审查Agent.*", text)
    assert desc_match, "external-review-agent.md 没有 description 行"
    assert "13" in desc_match.group(0), (
        f"description 行必须含 13: {desc_match.group(0)}"
    )


# ---------------------------------------------------------------------------
# 4. 9×dimensions 乘积数学正确（避免算错 99 vs 117）
# ---------------------------------------------------------------------------


def test_nine_times_dimensions_product_correctness():
    """所有"9 模型 × N 维度 = M 份"的表述，M 必须等于 9 × 13 = 117。"""
    files_to_check = [
        "agents/external-review-agent.md",
        "skills/webnovel-write/references/step-3.5-external-review.md",
        "scripts/external_review.py",
    ]
    pattern = re.compile(
        r"9\s*(?:模型)?\s*[×xX]\s*(\d+)\s*(?:维度)?\s*[=＝]\s*(\d+)\s*份"
    )
    violations = []
    for rel in files_to_check:
        path = _plugin_root() / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for m in pattern.finditer(text):
            dims, product = int(m.group(1)), int(m.group(2))
            if 9 * dims != product:
                line_no = text[: m.start()].count("\n") + 1
                violations.append(
                    f"{rel}:L{line_no} 算错: 9 × {dims} ≠ {product}（应 {9*dims}）"
                )
    assert not violations, "9×N 份乘积表达式数学错误:\n  " + "\n  ".join(violations)
