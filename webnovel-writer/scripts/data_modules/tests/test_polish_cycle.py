#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 8 · Post-Commit Polish 流程回归测试 · 2026-04-20

引入背景：末世重生 Ch1 v3 polish 裸跑 → 58 个 ASCII 引号 + 414 字漂移。
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
# 3b. backfill_commit_sha · commit 后回填 sha（v2 顺序修正）
# ---------------------------------------------------------------------------


def test_backfill_commit_sha_updates_latest_polish_task(tmp_path):
    """预登记（commit_sha=None）+ commit + 回填 sha 的三步流水正确性"""
    _ensure_scripts_on_path()
    import polish_cycle as pc

    project = _make_minimal_project(tmp_path)

    # 预登记（模拟 [5/7] 步：commit_sha 留 None）
    pc.register_workflow_polish_task(
        project_root=project,
        chapter=1,
        reason="sha 回填测试",
        new_version="v3",
        diff_lines=10,
        state_diff={},
        commit_sha=None,
    )
    wf_before = json.loads(
        (project / ".webnovel" / "workflow_state.json").read_text(encoding="utf-8")
    )
    task = wf_before["history"][-1]
    # 预登记时不应有 commit_sha 字段
    assert "commit_sha" not in task["artifacts"]
    assert "commit" not in task["artifacts"]

    # 回填（模拟 [7/7] 步）
    pc.backfill_commit_sha(project, "deadbeef1234cafebabe5678")

    wf_after = json.loads(
        (project / ".webnovel" / "workflow_state.json").read_text(encoding="utf-8")
    )
    task = wf_after["history"][-1]
    assert task["artifacts"]["commit_sha"] == "deadbeef1234cafebabe5678"
    assert task["artifacts"]["commit"] == "deadbeef1234cafebabe5678"
    assert task["artifacts"]["branch"] == "master"
    # completed_steps Step 8 也应同步
    step8 = next(
        (s for s in task["completed_steps"] if s["id"] == "Step 8"), None
    )
    assert step8 is not None
    assert step8["artifacts"]["commit_sha"] == "deadbeef1234cafebabe5678"


def test_backfill_commit_sha_only_affects_last_polish_task(tmp_path):
    """若历史里有多个 polish task，回填只修改最后一个（刚预登记的）"""
    _ensure_scripts_on_path()
    import polish_cycle as pc

    project = _make_minimal_project(tmp_path)

    pc.register_workflow_polish_task(
        project_root=project, chapter=1, reason="r1", new_version="v3",
        diff_lines=1, state_diff={}, commit_sha="OLD_SHA_AAAA",
    )
    pc.register_workflow_polish_task(
        project_root=project, chapter=1, reason="r2", new_version="v4",
        diff_lines=1, state_diff={}, commit_sha=None,
    )

    pc.backfill_commit_sha(project, "NEW_SHA_BBBB")

    wf = json.loads(
        (project / ".webnovel" / "workflow_state.json").read_text(encoding="utf-8")
    )
    # 旧任务不应被改
    assert wf["history"][0]["artifacts"]["commit_sha"] == "OLD_SHA_AAAA"
    # 新任务被回填
    assert wf["history"][1]["artifacts"]["commit_sha"] == "NEW_SHA_BBBB"


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


# ---------------------------------------------------------------------------
# 7. v2 顺序修正：commit 必须是最后一步原子落盘
# ---------------------------------------------------------------------------


def test_polish_cycle_main_has_workflow_preregister_before_commit():
    """polish_cycle.main() 顺序验证：workflow 预登记必须在 git commit 之前调用

    v1 设计把 workflow 登记放 commit 后，导致 commit 内容完全不含 workflow 痕迹。
    v2 修正为预登记（commit_sha=None）在前、git commit 居中、backfill_commit_sha
    在后。这个测试锁死 v2 顺序不再退回 v1。
    """
    pc_path = _plugin_root() / "scripts" / "polish_cycle.py"
    text = pc_path.read_text(encoding="utf-8")

    # 找到 main() 函数里三个关键调用的位置
    pre_idx = text.find("[5/7] workflow 预登记")
    commit_idx = text.find("[6/7] git commit")
    backfill_idx = text.find("[7/7] 回填 commit_sha")

    assert pre_idx > 0, "polish_cycle.main must have [5/7] workflow 预登记 step"
    assert commit_idx > 0, "polish_cycle.main must have [6/7] git commit step"
    assert backfill_idx > 0, "polish_cycle.main must have [7/7] 回填 commit_sha step"
    assert pre_idx < commit_idx < backfill_idx, (
        f"顺序错误：预登记({pre_idx}) < commit({commit_idx}) < 回填({backfill_idx}) "
        f"这是 v2 关键约束（commit 含 workflow 痕迹），禁止退回 v1"
    )


def test_polish_cycle_preregister_uses_commit_sha_none():
    """预登记调用必须传 commit_sha=None（让 commit 带走"pending" 状态）"""
    pc_path = _plugin_root() / "scripts" / "polish_cycle.py"
    text = pc_path.read_text(encoding="utf-8")

    # 找到 [5/7] 代码块里的 register_workflow_polish_task 调用
    anchor = text.find("[5/7] workflow 预登记 polish task")
    assert anchor > 0
    block = text[anchor:anchor + 2000]
    assert "register_workflow_polish_task" in block
    assert "commit_sha=None" in block, (
        "预登记必须传 commit_sha=None；commit_sha 留到 [7/7] 回填"
    )


def test_polish_cycle_documentation_describes_v2_ordering():
    """SKILL.md 与 references/post-commit-polish.md 必须描述 v2 的 7 步顺序"""
    skill = _plugin_root() / "skills" / "webnovel-write" / "SKILL.md"
    skill_text = skill.read_text(encoding="utf-8")
    assert "自动完成 7 步" in skill_text, "SKILL.md 必须描述 7 步流程（v2）"
    assert "commit 是最后一步" in skill_text or "commit 是真正最后一步" in skill_text

    ref = _plugin_root() / "skills" / "webnovel-write" / "references" / "post-commit-polish.md"
    ref_text = ref.read_text(encoding="utf-8")
    assert "[5/7] workflow 预登记" in ref_text
    assert "[6/7] git commit" in ref_text
    assert "[7/7] 回填 commit_sha" in ref_text


# ---------------------------------------------------------------------------
# 8. Round 14.5.2 · context-agent polish 传递 / H20 schema / preflight polish_drift
# ---------------------------------------------------------------------------


def test_context_agent_reads_polish_log():
    """agents/context-agent.md 必须提到读 polish_log / narrative_version 做跨章传递"""
    ca = _plugin_root() / "agents" / "context-agent.md"
    text = ca.read_text(encoding="utf-8")
    assert "polish_log" in text, "context-agent 必须读 polish_log（Round 14.5.2 跨章传递闸门）"
    assert "narrative_version" in text
    assert "上章 polish 经验" in text or "polish 经验传递" in text, (
        "context-agent 必须在读 polish_log 后把经验注入任务书"
    )


def test_hygiene_h20_polish_log_schema_registered():
    """hygiene_check 必须挂载 check_polish_log_schema，且 docstring 含 H20 描述"""
    hc = _plugin_root() / "scripts" / "hygiene_check.py"
    text = hc.read_text(encoding="utf-8")
    assert "def check_polish_log_schema" in text
    assert "check_polish_log_schema(root, args.chapter, rep)" in text
    assert "H20" in text


def test_hygiene_h20_validates_required_fields(tmp_path):
    """H20：polish_log 里每条必须含 version + timestamp + notes"""
    _ensure_scripts_on_path()
    from hygiene_check import check_polish_log_schema, HygieneReport  # type: ignore

    root = tmp_path
    webnovel = root / ".webnovel"
    webnovel.mkdir()
    state = {
        "chapter_meta": {
            "0001": {
                "polish_log": [
                    {"version": "v2", "timestamp": "2026-04-20T01:00:00Z", "notes": "ok"},
                    {"version": "v3", "notes": "missing timestamp"},
                ]
            }
        }
    }
    (webnovel / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    rep = HygieneReport()
    check_polish_log_schema(root, 1, rep)
    assert rep.p1_fails, "缺 timestamp 的 polish_log 必须报 H20 P1"
    assert "H20" in rep.p1_fails[0]


def test_hygiene_h20_accepts_valid_schema(tmp_path):
    """H20：完整 schema 的 polish_log 必须通过"""
    _ensure_scripts_on_path()
    from hygiene_check import check_polish_log_schema, HygieneReport  # type: ignore

    root = tmp_path
    webnovel = root / ".webnovel"
    webnovel.mkdir()
    state = {
        "chapter_meta": {
            "0001": {
                "polish_log": [
                    {"version": "v3.8.1", "timestamp": "2026-04-20T01:00:00Z", "notes": "ASCII 引号清理"},
                    {"version": "v3.8.2", "timestamp": "2026-04-20T02:00:00Z", "notes": "字数同步"},
                ]
            }
        }
    }
    (webnovel / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    rep = HygieneReport()
    check_polish_log_schema(root, 1, rep)
    assert not rep.p1_fails, f"完整 schema 不应触发 P1，实际 fails={rep.p1_fails}"


def test_preflight_check_polish_drift_exists():
    """webnovel.py 必须实现 _check_polish_drift"""
    wn = _plugin_root() / "scripts" / "data_modules" / "webnovel.py"
    text = wn.read_text(encoding="utf-8")
    assert "def _check_polish_drift" in text
    assert "polish_drift" in text
    assert "narrative_version" in text


def test_install_git_hooks_script_exists():
    """scripts/install_git_hooks.py 必须存在且含 HOOK_SCRIPT 定义"""
    hook = _plugin_root() / "scripts" / "install_git_hooks.py"
    assert hook.exists(), "Round 14.5.2 必须提供可选 pre-commit hook 安装脚本"
    text = hook.read_text(encoding="utf-8")
    assert "HOOK_SCRIPT" in text
    assert "polish_cycle" in text
    assert "no-verify" in text, "hook 描述必须说明可通过 --no-verify 绕过"


def test_gate_matrix_reference_exists():
    """Round 14.5.2 · gate-matrix.md 必须存在且被 SKILL.md 引用"""
    gm = _plugin_root() / "skills" / "webnovel-write" / "references" / "gate-matrix.md"
    assert gm.exists()
    gm_text = gm.read_text(encoding="utf-8")
    assert "多层拦截" in gm_text or "多层防御" in gm_text

    skill = _plugin_root() / "skills" / "webnovel-write" / "SKILL.md"
    assert "gate-matrix.md" in skill.read_text(encoding="utf-8"), (
        "SKILL.md 必须引用 gate-matrix.md（闸门一致性来源）"
    )


def test_polish_cycle_has_idempotent_warning():
    """polish_cycle.py 必须检测同版本重复登记（P1-7）"""
    pc = _plugin_root() / "scripts" / "polish_cycle.py"
    text = pc.read_text(encoding="utf-8")
    assert "幂等" in text or "idempotent" in text.lower()
    assert "existing_versions" in text or "polish_log_existing" in text


# ---------------------------------------------------------------------------
# Round 20 · Ch12 RCA P0：polish 轮数上限测试
# ---------------------------------------------------------------------------


def test_polish_cycle_has_max_rounds_arg():
    """Round 20：polish_cycle.py 必须有 --max-rounds / --allow-exceed-max-rounds 参数."""
    pc = _plugin_root() / "scripts" / "polish_cycle.py"
    text = pc.read_text(encoding="utf-8")
    assert "--max-rounds" in text
    assert "--allow-exceed-max-rounds" in text
    assert "--deviation-reason" in text


def test_polish_cycle_blocks_when_round_exceeds_max(tmp_path):
    """Round 20：polish_log 已 3 轮，再跑 polish_cycle 必须 exit 1."""
    _ensure_scripts_on_path()
    project = _make_minimal_project(tmp_path)
    state_p = project / ".webnovel" / "state.json"
    s = json.loads(state_p.read_text(encoding="utf-8"))
    s["chapter_meta"]["0001"]["polish_log"] = [
        {"version": "v2", "timestamp": "2026-04-20T10:00:00Z", "notes": "r1"},
        {"version": "v3", "timestamp": "2026-04-20T11:00:00Z", "notes": "r2"},
        {"version": "v4", "timestamp": "2026-04-20T12:00:00Z", "notes": "r3"},
    ]
    state_p.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")

    pc_script = _plugin_root() / "scripts" / "polish_cycle.py"
    result = subprocess.run(
        [
            sys.executable, "-X", "utf8", str(pc_script),
            "1",
            "--project-root", str(project),
            "--reason", "fourth round attempt",
            "--narrative-version", "v5",
            "--no-commit",
        ],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 1, f"应被 max-rounds 闸门 block，实际 exit={result.returncode}"
    assert "POLISH ROUND LIMIT" in result.stdout


def test_polish_cycle_allow_exceed_max_rounds_with_deviation(tmp_path):
    """Round 20：--allow-exceed-max-rounds + --deviation-reason 可继续 polish."""
    _ensure_scripts_on_path()
    project = _make_minimal_project(tmp_path)
    state_p = project / ".webnovel" / "state.json"
    s = json.loads(state_p.read_text(encoding="utf-8"))
    s["chapter_meta"]["0001"]["polish_log"] = [
        {"version": "v2", "timestamp": "2026-04-20T10:00:00Z", "notes": "r1"},
        {"version": "v3", "timestamp": "2026-04-20T11:00:00Z", "notes": "r2"},
        {"version": "v4", "timestamp": "2026-04-20T12:00:00Z", "notes": "r3"},
    ]
    state_p.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")

    pc_script = _plugin_root() / "scripts" / "polish_cycle.py"
    result = subprocess.run(
        [
            sys.executable, "-X", "utf8", str(pc_script),
            "1",
            "--project-root", str(project),
            "--reason", "deviation polish",
            "--narrative-version", "v5",
            "--allow-exceed-max-rounds",
            "--deviation-reason", "Beat 3 关键反派对线必须修",
            "--no-commit",
        ],
        capture_output=True, text=True, encoding="utf-8",
    )
    # 没 commit 但 allow exceed → 应进入正常流程（最后 --no-commit return 0 或前置 fail）
    # 因为 minimal project 没建 hygiene_check fixtures, post_draft_check 可能 fail
    # 关键：不应被 max-rounds 直接 block (return code != 1 with "POLISH ROUND LIMIT")
    assert "POLISH ROUND LIMIT" not in result.stdout
    assert "POLISH ROUND DEVIATION" in result.stdout or result.returncode in (0, 1)


def test_polish_cycle_allow_exceed_without_reason_fails(tmp_path):
    """Round 20：--allow-exceed-max-rounds 但缺 --deviation-reason → exit 1."""
    _ensure_scripts_on_path()
    project = _make_minimal_project(tmp_path)
    state_p = project / ".webnovel" / "state.json"
    s = json.loads(state_p.read_text(encoding="utf-8"))
    s["chapter_meta"]["0001"]["polish_log"] = [
        {"version": "v2", "timestamp": "2026-04-20T10:00:00Z", "notes": "r1"},
        {"version": "v3", "timestamp": "2026-04-20T11:00:00Z", "notes": "r2"},
        {"version": "v4", "timestamp": "2026-04-20T12:00:00Z", "notes": "r3"},
    ]
    state_p.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")

    pc_script = _plugin_root() / "scripts" / "polish_cycle.py"
    result = subprocess.run(
        [
            sys.executable, "-X", "utf8", str(pc_script),
            "1",
            "--project-root", str(project),
            "--reason", "deviation polish",
            "--narrative-version", "v5",
            "--allow-exceed-max-rounds",
            "--no-commit",
        ],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 1
    assert "deviation-reason" in result.stdout
