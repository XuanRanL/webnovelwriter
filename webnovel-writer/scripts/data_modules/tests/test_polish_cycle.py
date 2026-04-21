#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 8 · Post-Commit Polish 流程回归测试 · 2026-04-20

引入背景：<example-project> Ch1 v3 polish 裸跑 → 58 个 ASCII 引号 + 414 字漂移。
Round 14.5 引入 polish_cycle.py + hygiene_check H19 防御此类问题。

覆盖维度：
1. polish_cycle.parse_narrative_version 解析正确（v1, v2, v3.1, None）
2. polish_cycle.update_state_after_polish 正确写入 state.json
3. polish_cycle.register_workflow_polish_task 正确登记 workflow_state
4. polish_cycle CLI --no-commit 模式不调用 git
5. hygiene_check H19 在 polish drift 时报警
6. polish_cycle.py 与 hygiene_check.py 的 narrative_version 字段名一致
7. SKILL.md 与 references/post-commit-polish.md 提到的命令格式一致
"""

from __future__ import annotations

import json
import subprocess
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
# 1. parse_narrative_version 单元测试
# ---------------------------------------------------------------------------


def test_parse_narrative_version_basic():
    _ensure_scripts_on_path()
    import polish_cycle as pc

    assert pc.parse_narrative_version("v1") == ("v", 1)
    assert pc.parse_narrative_version("v2") == ("v", 2)
    assert pc.parse_narrative_version("v3") == ("v", 3)
    assert pc.parse_narrative_version("v10") == ("v", 10)


def test_parse_narrative_version_with_minor():
    _ensure_scripts_on_path()
    import polish_cycle as pc

    # bump only increments major; minor stays out
    assert pc.parse_narrative_version("v2.1") == ("v", 2)
    assert pc.parse_narrative_version("v3.5") == ("v", 3)


def test_parse_narrative_version_missing_or_invalid():
    _ensure_scripts_on_path()
    import polish_cycle as pc

    assert pc.parse_narrative_version(None) == ("v", 1)
    assert pc.parse_narrative_version("") == ("v", 1)
    assert pc.parse_narrative_version("invalid") == ("v", 1)


# ---------------------------------------------------------------------------
# 2. update_state_after_polish 写入正确性
# ---------------------------------------------------------------------------


def _make_minimal_project(tmp_path: Path, chapter_text: str = "正文" * 1500) -> Path:
    """Create a minimal .webnovel project with one chapter."""
    project = tmp_path / "test_project"
    (project / ".webnovel").mkdir(parents=True)
    (project / "正文").mkdir()
    chapter_file = project / "正文" / "第0001章-测试.md"
    chapter_file.write_text(chapter_text, encoding="utf-8")

    state = {
        "chapter_meta": {
            "0001": {
                "chapter": 1,
                "title": "测试",
                "word_count": 9999,
                "narrative_version": "v2",
                "checker_scores": {"overall": 90},
            }
        }
    }
    (project / ".webnovel" / "state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return project


def test_update_state_after_polish_word_count(tmp_path):
    _ensure_scripts_on_path()
    import polish_cycle as pc

    # "正文" 是 2 个中文字符 × 1500 = 3000 字
    project = _make_minimal_project(tmp_path, chapter_text="正文" * 1500)
    chapter_file = project / "正文" / "第0001章-测试.md"

    diff = pc.update_state_after_polish(
        project, 1, chapter_file, new_version="v3", notes="test polish"
    )

    s = json.loads((project / ".webnovel" / "state.json").read_text(encoding="utf-8"))
    meta = s["chapter_meta"]["0001"]
    assert meta["word_count"] == 3000
    assert meta["narrative_version"] == "v3"
    assert "updated_at" in meta
    assert meta["polish_log"][-1]["version"] == "v3"
    assert meta["polish_log"][-1]["notes"] == "test polish"
    assert "word_count" in diff
    assert diff["word_count"]["new"] == 3000
    assert diff["narrative_version"]["new"] == "v3"


def test_update_state_after_polish_checker_scores_merge(tmp_path):
    _ensure_scripts_on_path()
    import polish_cycle as pc

    project = _make_minimal_project(tmp_path)
    chapter_file = project / "正文" / "第0001章-测试.md"

    pc.update_state_after_polish(
        project,
        1,
        chapter_file,
        new_version="v3",
        checker_scores={
            "reader-naturalness-checker": 91,
            "reader-critic-checker": 88,
        },
        notes="checker polish",
    )

    s = json.loads((project / ".webnovel" / "state.json").read_text(encoding="utf-8"))
    cs = s["chapter_meta"]["0001"]["checker_scores"]
    # 不能覆盖原有 overall=90
    assert cs["overall"] == 90
    assert cs["reader-naturalness-checker"] == 91
    assert cs["reader-critic-checker"] == 88


def test_update_state_after_polish_polish_log_append(tmp_path):
    _ensure_scripts_on_path()
    import polish_cycle as pc

    project = _make_minimal_project(tmp_path)
    chapter_file = project / "正文" / "第0001章-测试.md"

    pc.update_state_after_polish(project, 1, chapter_file, "v3", notes="round 1")
    pc.update_state_after_polish(project, 1, chapter_file, "v4", notes="round 2")
    pc.update_state_after_polish(project, 1, chapter_file, "v5", notes="round 3")

    s = json.loads((project / ".webnovel" / "state.json").read_text(encoding="utf-8"))
    log = s["chapter_meta"]["0001"]["polish_log"]
    assert len(log) == 3
    assert [e["version"] for e in log] == ["v3", "v4", "v5"]
    assert [e["notes"] for e in log] == ["round 1", "round 2", "round 3"]


# ---------------------------------------------------------------------------
# 3. register_workflow_polish_task 登记正确性
# ---------------------------------------------------------------------------


def test_register_workflow_polish_task_creates_history(tmp_path):
    _ensure_scripts_on_path()
    import polish_cycle as pc

    project = _make_minimal_project(tmp_path)

    pc.register_workflow_polish_task(
        project_root=project,
        chapter=1,
        reason="naturalness 修复",
        new_version="v3",
        diff_lines=42,
        state_diff={"word_count": {"old": 9999, "new": 1500}},
        commit_sha="abc123def456",
        round_tag="round13v2",
    )

    wf = json.loads(
        (project / ".webnovel" / "workflow_state.json").read_text(encoding="utf-8")
    )
    assert "history" in wf
    assert len(wf["history"]) == 1
    task = wf["history"][0]
    assert task["task_id"] == "polish_001"
    assert task["command"] == "webnovel-polish"
    assert task["chapter"] == 1
    assert task["status"] == "completed"
    assert task["artifacts"]["polish_cycle"] is True
    assert task["artifacts"]["narrative_version"] == "v3"
    assert task["artifacts"]["reason"] == "naturalness 修复"
    assert task["artifacts"]["round_tag"] == "round13v2"
    assert task["artifacts"]["commit_sha"] == "abc123def456"
    assert task["completed_steps"][0]["id"] == "Step 8"

    # 第二次调用应追加 polish_002，不覆盖
    pc.register_workflow_polish_task(
        project_root=project,
        chapter=1,
        reason="round 2",
        new_version="v4",
        diff_lines=10,
        state_diff={},
    )
    wf2 = json.loads(
        (project / ".webnovel" / "workflow_state.json").read_text(encoding="utf-8")
    )
    assert len(wf2["history"]) == 2
    assert wf2["history"][1]["task_id"] == "polish_002"


# ---------------------------------------------------------------------------
# 4. CLI --no-commit / --allow-no-change smoke
# ---------------------------------------------------------------------------


def test_polish_cycle_rejects_no_change_by_default(tmp_path):
    """文件未改动且未给 --allow-no-change → 应返回 exit 2"""
    _ensure_scripts_on_path()
    import polish_cycle as pc

    project = _make_minimal_project(tmp_path)
    # 在临时项目里初始化 git 并 commit
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "add", "."],
        cwd=project, check=True,
    )
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t",
         "commit", "-q", "-m", "init"],
        cwd=project, check=True,
    )

    # 文件未改 → polish_cycle 应该 exit 2
    chapter_file = project / "正文" / "第0001章-测试.md"
    changed, _ = pc.detect_chapter_changed(project, chapter_file)
    assert not changed


def test_polish_cycle_detects_change(tmp_path):
    """文件改动后 detect_chapter_changed 应返回 True"""
    _ensure_scripts_on_path()
    import polish_cycle as pc

    project = _make_minimal_project(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "add", "."],
        cwd=project, check=True,
    )
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t",
         "commit", "-q", "-m", "init"],
        cwd=project, check=True,
    )

    chapter_file = project / "正文" / "第0001章-测试.md"
    chapter_file.write_text(
        chapter_file.read_text(encoding="utf-8") + "\n新增一句", encoding="utf-8"
    )
    changed, diff_lines = pc.detect_chapter_changed(project, chapter_file)
    assert changed is True
    assert diff_lines >= 1


# ---------------------------------------------------------------------------
# 5. hygiene_check H19 触发条件
# ---------------------------------------------------------------------------


def test_hygiene_check_h19_skips_when_clean(tmp_path):
    """正文与 HEAD 一致 → H19 应该 P2 通过"""
    _ensure_scripts_on_path()
    import hygiene_check as hc

    project = _make_minimal_project(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "add", "."],
        cwd=project, check=True,
    )
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t",
         "commit", "-q", "-m", "init"],
        cwd=project, check=True,
    )

    rep = hc.HygieneReport()
    hc.check_post_commit_polish_drift(project, 1, rep)
    # 干净状态下 H19 不应有任何 fail
    h19_fails = [
        f for f in rep.p0_fails + rep.p1_fails + rep.p2_fails
        if f.startswith("H19")
    ]
    assert not h19_fails, f"H19 should be clean but got fails: {h19_fails}"


def test_hygiene_check_h19a_blocks_when_v1_drift(tmp_path):
    """正文已改且 narrative_version=v1 → H19a P0 fail"""
    _ensure_scripts_on_path()
    import hygiene_check as hc

    project = _make_minimal_project(tmp_path)
    # 强制 narrative_version=v1
    state_p = project / ".webnovel" / "state.json"
    s = json.loads(state_p.read_text(encoding="utf-8"))
    s["chapter_meta"]["0001"]["narrative_version"] = "v1"
    state_p.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")

    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "add", "."],
        cwd=project, check=True,
    )
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t",
         "commit", "-q", "-m", "init"],
        cwd=project, check=True,
    )

    # 修改正文（模拟裸 polish）
    chapter_file = project / "正文" / "第0001章-测试.md"
    chapter_file.write_text(
        chapter_file.read_text(encoding="utf-8") + "\n裸 polish", encoding="utf-8"
    )

    rep = hc.HygieneReport()
    hc.check_post_commit_polish_drift(project, 1, rep)
    # H19a 应记录在 p0_fails 里
    h19a_fails = [f for f in rep.p0_fails if f.startswith("H19a")]
    assert len(h19a_fails) == 1, (
        f"Expected exactly one H19a P0 fail, got: p0={rep.p0_fails}, "
        f"p1={rep.p1_fails}, p2={rep.p2_fails}"
    )
    assert "narrative_version" in h19a_fails[0]


# ---------------------------------------------------------------------------
# 6. 文档与代码一致性
# ---------------------------------------------------------------------------


def test_skill_md_mentions_step_8():
    skill = _plugin_root() / "skills" / "webnovel-write" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    assert "Step 8" in text, "SKILL.md must mention Step 8"
    assert "polish_cycle.py" in text, "SKILL.md must mention polish_cycle.py"
    assert "Post-Commit Polish" in text, "SKILL.md must mention Post-Commit Polish"


def test_post_commit_polish_reference_exists():
    ref = _plugin_root() / "skills" / "webnovel-write" / "references" / "post-commit-polish.md"
    assert ref.exists(), "references/post-commit-polish.md must exist"
    text = ref.read_text(encoding="utf-8")
    assert "polish_cycle.py" in text
    assert "narrative_version" in text
    assert "polish_log" in text


def test_polish_cycle_imports_required_modules():
    """polish_cycle.py 必须能找到 post_draft_check / hygiene_check 在 SCRIPTS_DIR"""
    _ensure_scripts_on_path()
    import polish_cycle as pc

    assert (pc.SCRIPTS_DIR / "post_draft_check.py").exists()
    assert (pc.SCRIPTS_DIR / "hygiene_check.py").exists()


def test_hygiene_check_h19_registered_in_main():
    """hygiene_check.main() 必须调用 check_post_commit_polish_drift"""
    hc_path = _plugin_root() / "scripts" / "hygiene_check.py"
    text = hc_path.read_text(encoding="utf-8")
    assert "check_post_commit_polish_drift" in text
    assert "check_post_commit_polish_drift(root, args.chapter, rep)" in text, (
        "hygiene_check.main() must invoke check_post_commit_polish_drift"
    )
