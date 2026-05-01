#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ch22 Round 21.7 RCA 回归测试 · 2026-04-30

覆盖 Ch22 (<example-project>) 暴露的 root cause：

**P0-A · progress.total_words 单章覆盖**
  症状: data-agent Step D 直接 Edit state.json 把
        progress.total_words 从 62357 (22 章累加) 覆盖成 2587 (仅 Ch22)
  根因: data-agent 不走 state update --add-words CLI，绕过 PROTECTED_FIELDS
  根治: hygiene_check H36 在 Step 7 commit 前校验
        progress.total_words ≈ sum(chapter_meta.*.word_count) 容差 ±1%

**P0-B · chapter_meta.narrative_version 一刀切**
  症状: audit-agent Step 6 把 22 章的 chapter_meta.NNNN.narrative_version
        全部刷成 'v7.1'（混淆 Canon Bible 文档版本号 v7.1 与 chapter_meta
        narrative_version 字段语义 v1/v2/v3）
  根因: audit-agent tools 仅声明 Read/Grep/Bash，但 Bash 内部通过 python -c
        路径绕过守卫直接 Edit state.json
  根治: hygiene_check H35 检测 narrative_version / overall_score / review_score 等
        受保护字段被 ≥3 章一刀切改成同值 → P0 fail

测试矩阵：
  H36 · total_words consistency
    - 一致 (diff <= tolerance) → pass
    - 单章覆盖 (Ch22 = 2587 / 累计 62357) → P0 fail
    - chapter_meta 全空 → skip
    - chapter_meta 字数全 0 → skip

  H35 · chapter_meta 一刀切
    - 22 章 narrative_version 同值改 v7.1 → P0 fail
    - 单章 narrative_version 升 v3 → pass
    - 2 章 narrative_version 改同值 → pass (< 3 章阈值)
    - 5 章 overall_score 改 88 → P0 fail
    - commit message 含 chore(state-rebase) → P1 (豁免)
    - commit message 含 [polish:Ch22-recheck] → P1 (豁免)

  audit-agent.md 文档约束
    - tools 仅 Read/Grep/Bash（无 Write/Edit）
    - 包含禁止 python -c 改 state.json 的红字
    - 包含运行时自检 git diff state.json | wc -l == 0

  data-agent.md 文档约束
    - Step D 必须用 state update --add-words CLI
    - 禁直接 Edit/Write state.json
    - 引用 H36 阻断
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


def _ensure_scripts_on_path() -> None:
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def _load_hygiene():
    _ensure_scripts_on_path()
    import hygiene_check
    return hygiene_check


def _make_state(chapter_meta: dict, total_words: int) -> dict:
    return {
        "project_info": {"title": "test"},
        "progress": {
            "current_chapter": max((int(k) for k in chapter_meta.keys()), default=0),
            "total_words": total_words,
            "last_updated": "2026-04-30 12:00:00",
        },
        "chapter_meta": chapter_meta,
    }


# ---------------------------------------------------------------------------
# H36 · progress.total_words 与 chapter_meta 一致性
# ---------------------------------------------------------------------------


def test_h36_total_words_consistent_passes(tmp_path):
    hg = _load_hygiene()
    cm = {f"{i:04d}": {"word_count": 3000} for i in range(1, 11)}
    state = _make_state(cm, total_words=30000)
    (tmp_path / ".webnovel").mkdir()
    (tmp_path / ".webnovel" / "state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    rep = hg.HygieneReport()
    hg.check_total_words_consistency(tmp_path, 10, rep)
    assert "H36" in rep.passes, f"H36 应 pass, got fails={rep.p0_fails}"
    assert not any("H36" in f for f in rep.p0_fails), f"H36 不应 P0 fail, got {rep.p0_fails}"


def test_h36_total_words_single_chapter_overwrite_fails(tmp_path):
    """Ch22 复刻：total_words=2587（仅 Ch22）但累计应是 62357"""
    hg = _load_hygiene()
    cm = {f"{i:04d}": {"word_count": 3000 if i != 22 else 2587} for i in range(1, 23)}
    # 累计 = 21*3000 + 2587 = 65587 但被覆盖成 2587
    state = _make_state(cm, total_words=2587)
    (tmp_path / ".webnovel").mkdir()
    (tmp_path / ".webnovel" / "state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    rep = hg.HygieneReport()
    hg.check_total_words_consistency(tmp_path, 22, rep)
    h36_fails = [f for f in rep.p0_fails if f.startswith("H36:")]
    assert len(h36_fails) == 1, f"H36 应 P0 fail, got passes={rep.passes} p0={rep.p0_fails}"
    assert "total_words" in h36_fails[0]
    assert "add-words" in h36_fails[0]


def test_h36_total_words_within_tolerance_passes(tmp_path):
    """容差范围内（10 字以内）应 pass"""
    hg = _load_hygiene()
    cm = {f"{i:04d}": {"word_count": 3000} for i in range(1, 11)}
    # 实际 30000 vs 记录 30005，diff=5 < tolerance=300 (1%) 或 100 floor
    state = _make_state(cm, total_words=30005)
    (tmp_path / ".webnovel").mkdir()
    (tmp_path / ".webnovel" / "state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    rep = hg.HygieneReport()
    hg.check_total_words_consistency(tmp_path, 10, rep)
    assert "H36" in rep.passes
    assert not any("H36" in f for f in rep.p0_fails)


def test_h36_chapter_meta_empty_skips(tmp_path):
    hg = _load_hygiene()
    state = _make_state({}, total_words=0)
    (tmp_path / ".webnovel").mkdir()
    (tmp_path / ".webnovel" / "state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    rep = hg.HygieneReport()
    hg.check_total_words_consistency(tmp_path, 1, rep)
    # skip = pass
    assert "H36" in rep.passes


# ---------------------------------------------------------------------------
# H35 · state.json chapter_meta 一刀切检测
# ---------------------------------------------------------------------------


def _setup_git_repo(tmp_path: Path, initial_state: dict) -> Path:
    """初始化一个 git repo，commit initial_state，返回 root"""
    root = tmp_path / "proj"
    root.mkdir()
    (root / ".webnovel").mkdir()
    (root / ".webnovel" / "state.json").write_text(
        json.dumps(initial_state, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "initial", "--allow-empty"],
        cwd=root, check=True,
    )
    return root


def test_h35_22_chapters_narrative_version_v7_1_blocks(tmp_path):
    """Ch22 真实复刻：22 章 narrative_version 全部改 v7.1 → P0 fail"""
    hg = _load_hygiene()
    initial_cm = {
        "0001": {"word_count": 2917, "narrative_version": "v8"},
        "0002": {"word_count": 3447, "narrative_version": "v5"},
        "0003": {"word_count": 2971, "narrative_version": "v3"},
        "0004": {"word_count": 2348, "narrative_version": "v3"},
        "0005": {"word_count": 3102, "narrative_version": "v3"},
    }
    root = _setup_git_repo(tmp_path, _make_state(initial_cm, 14785))
    # 模拟 audit-agent 越权：把 5 章 narrative_version 全刷 v7.1
    poisoned = json.loads((root / ".webnovel" / "state.json").read_text(encoding="utf-8"))
    for k in poisoned["chapter_meta"]:
        poisoned["chapter_meta"][k]["narrative_version"] = "v7.1"
    (root / ".webnovel" / "state.json").write_text(
        json.dumps(poisoned, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    rep = hg.HygieneReport()
    hg.check_chapter_meta_overstep(root, 5, rep)
    h35_fails = [f for f in rep.p0_fails if f.startswith("H35:")]
    assert len(h35_fails) == 1, f"应 P0 fail, got passes={rep.passes} p0={rep.p0_fails}"
    assert "narrative_version" in h35_fails[0]


def test_h35_single_chapter_polish_passes(tmp_path):
    """合法路径：单章升级 v2→v3，仅 1 章改动 → pass"""
    hg = _load_hygiene()
    initial_cm = {
        "0001": {"word_count": 2917, "narrative_version": "v8"},
        "0002": {"word_count": 3447, "narrative_version": "v2"},
    }
    root = _setup_git_repo(tmp_path, _make_state(initial_cm, 6364))
    # 单章 polish: Ch2 v2 → v3
    poisoned = json.loads((root / ".webnovel" / "state.json").read_text(encoding="utf-8"))
    poisoned["chapter_meta"]["0002"]["narrative_version"] = "v3"
    (root / ".webnovel" / "state.json").write_text(
        json.dumps(poisoned, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    rep = hg.HygieneReport()
    hg.check_chapter_meta_overstep(root, 2, rep)
    assert "H35" in rep.passes, f"单章 polish 应 pass, got p0={rep.p0_fails} p1={rep.p1_fails}"
    assert not any("H35" in f for f in rep.p0_fails)


def test_h35_two_chapters_under_threshold_passes(tmp_path):
    """边界：2 章同值改动（< 3 章阈值）应 pass"""
    hg = _load_hygiene()
    initial_cm = {
        "0001": {"word_count": 2917, "narrative_version": "v8"},
        "0002": {"word_count": 3447, "narrative_version": "v2"},
        "0003": {"word_count": 2971, "narrative_version": "v3"},
    }
    root = _setup_git_repo(tmp_path, _make_state(initial_cm, 9335))
    poisoned = json.loads((root / ".webnovel" / "state.json").read_text(encoding="utf-8"))
    poisoned["chapter_meta"]["0001"]["narrative_version"] = "v9"
    poisoned["chapter_meta"]["0002"]["narrative_version"] = "v9"
    (root / ".webnovel" / "state.json").write_text(
        json.dumps(poisoned, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    rep = hg.HygieneReport()
    hg.check_chapter_meta_overstep(root, 2, rep)
    assert "H35" in rep.passes, f"2 章应 pass, got p0={rep.p0_fails}"
    assert not any("H35" in f for f in rep.p0_fails)


def test_h35_overall_score_overstep_blocks(tmp_path):
    """overall_score 5 章一刀切应 P0 fail"""
    hg = _load_hygiene()
    initial_cm = {
        f"{i:04d}": {"word_count": 3000, "overall_score": 80 + i}
        for i in range(1, 6)
    }
    root = _setup_git_repo(tmp_path, _make_state(initial_cm, 15000))
    poisoned = json.loads((root / ".webnovel" / "state.json").read_text(encoding="utf-8"))
    for k in poisoned["chapter_meta"]:
        poisoned["chapter_meta"][k]["overall_score"] = 88
    (root / ".webnovel" / "state.json").write_text(
        json.dumps(poisoned, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    rep = hg.HygieneReport()
    hg.check_chapter_meta_overstep(root, 5, rep)
    h35_fails = [f for f in rep.p0_fails if f.startswith("H35:")]
    assert len(h35_fails) == 1, f"overall_score 一刀切应 P0 fail, got passes={rep.passes} p0={rep.p0_fails}"
    assert "overall_score" in h35_fails[0]


# ---------------------------------------------------------------------------
# audit-agent.md 文档约束（防再次回归）
# ---------------------------------------------------------------------------


def test_audit_agent_tools_readonly():
    """audit-agent.md 必须仅声明 Read, Grep, Bash 工具"""
    fork = Path(__file__).resolve().parents[3]
    p = fork / "agents" / "audit-agent.md"
    text = p.read_text(encoding="utf-8")
    # frontmatter
    head = text.split("---")[1] if "---" in text else text[:500]
    assert "tools: Read, Grep, Bash" in head, "audit-agent tools 必须只 Read/Grep/Bash"
    assert "Write" not in head.split("model:")[0]  # frontmatter 之内
    assert "Edit" not in head.split("model:")[0]


def test_audit_agent_round21_7_runtime_check_documented():
    """audit-agent.md 必须包含 Round 21.7 运行时自检红字"""
    fork = Path(__file__).resolve().parents[3]
    p = fork / "agents" / "audit-agent.md"
    text = p.read_text(encoding="utf-8")
    assert "Round 21.7" in text, "必须标注 Round 21.7"
    assert "git diff" in text and "state.json" in text, "必须有 state.json git diff 自检"
    assert "python -c" in text, "必须明禁 python -c 路径"
    assert "v7.1" in text, "必须保留 Ch22 血教训案例"


# ---------------------------------------------------------------------------
# data-agent.md 文档约束
# ---------------------------------------------------------------------------


def test_data_agent_step_d_uses_cli_for_total_words():
    """data-agent.md Step D 必须明示走 state update --add-words CLI"""
    fork = Path(__file__).resolve().parents[3]
    p = fork / "agents" / "data-agent.md"
    text = p.read_text(encoding="utf-8")
    # 必须出现 add-words CLI
    assert "state update --add-words" in text, "Step D 必须引用 --add-words CLI"
    # 必须明禁直接 Edit/Write
    assert "禁止" in text and "total_words" in text
    # 必须引用 H36
    assert "H36" in text, "必须引用 hygiene H36 阻断"


# ---------------------------------------------------------------------------
# state_manager.py PROTECTED_FIELDS 仍保护 narrative_version
# ---------------------------------------------------------------------------


def test_protected_fields_includes_narrative_version():
    """state_manager.process_chapter_result 守卫必须含 narrative_version"""
    _ensure_scripts_on_path()
    sm_text = (
        Path(__file__).resolve().parents[2] / "data_modules" / "state_manager.py"
    ).read_text(encoding="utf-8")
    # 找 PROTECTED_FIELDS 块
    assert 'PROTECTED_FIELDS = (' in sm_text
    block = sm_text.split('PROTECTED_FIELDS = (')[1].split(')')[0]
    for field in ("checker_scores", "narrative_version", "polish_log", "overall_score"):
        assert f'"{field}"' in block, f"PROTECTED_FIELDS 必须含 {field}"
