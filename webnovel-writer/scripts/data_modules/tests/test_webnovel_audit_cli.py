#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integration tests for `webnovel.py audit chapter` + `audit check-decision`
via subprocess, covering the full dispatch from the unified CLI.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[2]


def _run_audit_cli(project_root: Path, *args: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = [
        sys.executable, "-X", "utf8",
        str(SCRIPTS_DIR / "webnovel.py"),
        "--project-root", str(project_root),
        "audit", *args,
    ]
    return subprocess.run(
        cmd, cwd=str(SCRIPTS_DIR), env=env,
        capture_output=True, text=True, encoding="utf-8",
    )


@pytest.fixture
def minimal_project(tmp_path):
    """构造一个最小可审计的项目 (足以让 CLI 运行但会有 fail)."""
    root = tmp_path / "book"
    root.mkdir()
    (root / ".webnovel").mkdir()
    # state.json — project_locator 需要
    (root / ".webnovel" / "state.json").write_text(
        json.dumps({
            "project_info": {"title": "t", "genre": "g"},
            "plot_threads": {"foreshadowing": []},
            "chapter_meta": {},
        }, ensure_ascii=False), encoding="utf-8",
    )
    return root


def test_cli_audit_chapter_missing_artifacts(minimal_project):
    """CLI 在缺失产物时应正常运行并输出 JSON（决议 block）."""
    out_file = minimal_project / ".webnovel" / "tmp" / "audit.json"
    result = _run_audit_cli(
        minimal_project,
        "chapter", "--chapter", "1", "--mode", "standard", "--out", str(out_file),
    )
    # 退出码应为 1 (critical fail) 或 2 (warnings)
    assert result.returncode in {1, 2}, f"stderr={result.stderr}\nstdout={result.stdout[:500]}"
    # stdout 含 JSON
    assert "cli_decision" in result.stdout
    # out 文件写出
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["chapter"] == 1
    assert "layers" in data
    assert "A_process_integrity" in data["layers"]
    # 观测日志追加
    obs_path = minimal_project / ".webnovel" / "observability" / "chapter_audit.jsonl"
    assert obs_path.exists()


def test_cli_audit_check_decision_missing_report(minimal_project):
    """check-decision 在 audit_reports 缺失时应退出 1."""
    result = _run_audit_cli(
        minimal_project,
        "check-decision", "--chapter", "1",
        "--require", "approve,approve_with_warnings",
    )
    assert result.returncode == 1
    # 输出含错误 JSON
    assert "audit_report_missing" in result.stdout or "audit_report_missing" in result.stderr


def test_cli_audit_check_decision_approve(minimal_project):
    """check-decision 读取 approve 报告应退出 0."""
    audit_dir = minimal_project / ".webnovel" / "audit_reports"
    audit_dir.mkdir(parents=True, exist_ok=True)
    (audit_dir / "ch0001.json").write_text(
        json.dumps({"chapter": 1, "overall_decision": "approve"}, ensure_ascii=False),
        encoding="utf-8",
    )
    result = _run_audit_cli(
        minimal_project,
        "check-decision", "--chapter", "1",
        "--require", "approve,approve_with_warnings",
    )
    assert result.returncode == 0, f"stderr={result.stderr}"
    assert "success" in result.stdout or "approve" in result.stdout


def test_cli_audit_check_decision_block_rejected(minimal_project):
    """check-decision 读取 block 报告应退出 1."""
    audit_dir = minimal_project / ".webnovel" / "audit_reports"
    audit_dir.mkdir(parents=True, exist_ok=True)
    (audit_dir / "ch0001.json").write_text(
        json.dumps({"chapter": 1, "overall_decision": "block"}, ensure_ascii=False),
        encoding="utf-8",
    )
    result = _run_audit_cli(
        minimal_project,
        "check-decision", "--chapter", "1",
        "--require", "approve,approve_with_warnings",
    )
    assert result.returncode == 1
    assert "audit_decision_not_allowed" in result.stdout or "audit_decision_not_allowed" in result.stderr


def test_cli_audit_mode_minimal_skips_g(minimal_project):
    """mode=minimal 时 Layer G 应被 skip."""
    out_file = minimal_project / ".webnovel" / "tmp" / "audit_minimal.json"
    result = _run_audit_cli(
        minimal_project,
        "chapter", "--chapter", "1", "--mode", "minimal", "--out", str(out_file),
    )
    assert result.returncode in {0, 1, 2}
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    g = data["layers"]["G_cross_chapter_trend"]
    assert g["score"] is None
    assert "minimal" in g.get("skipped_reason", "")
