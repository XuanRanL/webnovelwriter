#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import sys
from pathlib import Path
from types import SimpleNamespace


def _load_module():
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import workflow_manager

    return workflow_manager


def _run_full_write_workflow(module, chapter_num):
    module.start_task("webnovel-write", {"chapter_num": chapter_num})
    for step_id, step_name in [
        ("Step 1", "Context"),
        ("Step 2A", "Draft"),
        ("Step 2B", "Style"),
        ("Step 3", "Review"),
        ("Step 3.5", "External Review"),
        ("Step 4", "Polish"),
        ("Step 5", "Data"),
        ("Step 6", "Audit"),
        ("Step 7", "Backup"),
    ]:
        module.start_step(step_id, step_name)
        module.complete_step(step_id)


def test_workflow_lifecycle_and_trace(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "find_project_root", lambda: tmp_path)

    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)

    _run_full_write_workflow(module, 7)
    module.complete_task(json.dumps({"review_completed": True}, ensure_ascii=False))

    state = module.load_state()
    assert state["current_task"] is None
    assert state["history"][-1]["status"] == module.TASK_STATUS_COMPLETED
    assert state["last_stable_state"]["artifacts"]["review_completed"] is True
    assert state["history"][-1]["args"]["chapter_num"] == 7
    assert state["history"][-1]["completed_steps"][-1]["id"] == "Step 7"

    trace_path = module.get_call_trace_path()
    assert trace_path.exists()
    lines = trace_path.read_text(encoding="utf-8").strip().splitlines()
    events = [json.loads(line)["event"] for line in lines if line.strip()]
    assert "task_started" in events
    assert "step_started" in events
    assert "step_completed" in events
    assert "task_completed" in events


def test_start_task_reentry_increments_retry(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "find_project_root", lambda: tmp_path)

    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)

    module.start_task("webnovel-write", {"chapter_num": 8})
    module.start_task("webnovel-write", {"chapter_num": 8})

    state = module.load_state()
    task = state["current_task"]
    assert task is not None
    assert task["status"] == module.TASK_STATUS_RUNNING
    assert int(task.get("retry_count", 0)) >= 1


def test_complete_step_rejects_mismatch_step_id(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "find_project_root", lambda: tmp_path)

    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)

    module.start_task("webnovel-write", {"chapter_num": 9})
    module.start_step("Step 1", "Context")
    module.complete_step("Step 1")
    module.start_step("Step 2A", "Draft")
    module.complete_step("Step 2B")

    state = module.load_state()
    current_step = state["current_task"]["current_step"]
    assert current_step is not None
    assert current_step["id"] == "Step 2A"
    assert current_step["status"] == module.STEP_STATUS_RUNNING


def test_workflow_step_owner_and_order_violation_trace(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "find_project_root", lambda: tmp_path)

    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)

    assert module.expected_step_owner("webnovel-write", "Step 1") == "context-agent"
    assert module.expected_step_owner("webnovel-write", "Step 5") == "data-agent"

    module.start_task("webnovel-write", {"chapter_num": 12})
    module.start_step("Step 3", "Review")

    state = module.load_state()
    assert state["current_task"]["current_step"] is None

    trace_path = module.get_call_trace_path()
    lines = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    events = [row.get("event") for row in lines]
    assert "step_order_violation" in events
    assert "step_start_rejected" in events

    rejected = [row for row in lines if row.get("event") == "step_start_rejected"]
    assert rejected
    assert rejected[-1].get("payload", {}).get("reason") == "step_order_violation"


def test_start_step_rejects_when_another_step_running(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "find_project_root", lambda: tmp_path)

    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)

    module.start_task("webnovel-write", {"chapter_num": 13})
    module.start_step("Step 1", "Context")
    module.start_step("Step 2A", "Draft")

    state = module.load_state()
    assert state["current_task"]["current_step"]["id"] == "Step 1"

    trace_path = module.get_call_trace_path()
    lines = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rejected = [row for row in lines if row.get("event") == "step_start_rejected"]
    assert rejected
    assert rejected[-1]["payload"]["reason"] == "active_step_running"


def test_safe_append_call_trace_logs_failure(monkeypatch, caplog):
    module = _load_module()

    def _raise_trace_error(event, payload=None):
        raise RuntimeError("trace failure")

    monkeypatch.setattr(module, "append_call_trace", _raise_trace_error)

    with caplog.at_level(logging.WARNING):
        module.safe_append_call_trace("unit_test_event", {"ok": True})

    message_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "failed to append call trace" in message_text
    assert "unit_test_event" in message_text


def test_get_workflow_paths_support_zero_arg_find_project_root(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "_cli_project_root", None)
    monkeypatch.setattr(module, "find_project_root", lambda: tmp_path)

    assert module.get_workflow_state_path() == tmp_path / ".webnovel" / "workflow_state.json"
    assert module.get_call_trace_path() == tmp_path / ".webnovel" / "observability" / "call_trace.jsonl"


def test_workflow_reentry_does_not_duplicate_history(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "find_project_root", lambda: tmp_path)

    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)

    module.start_task("webnovel-write", {"chapter_num": 20})
    module.start_task("webnovel-write", {"chapter_num": 20})
    module.start_task("webnovel-write", {"chapter_num": 20})

    state = module.load_state()
    assert isinstance(state.get("history"), list)
    assert len(state.get("history")) == 0

    task = state.get("current_task") or {}
    assert int(task.get("retry_count", 0)) >= 2


def test_complete_task_rejects_missing_required_steps(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "find_project_root", lambda: tmp_path)

    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)

    module.start_task("webnovel-write", {"chapter_num": 21})
    module.start_step("Step 1", "Context")
    module.complete_step("Step 1")
    module.complete_task()

    state = module.load_state()
    task = state["current_task"]
    assert task is not None
    assert task["status"] == module.TASK_STATUS_FAILED
    assert "Step 7" in task["failure_reason"]

    trace_path = module.get_call_trace_path()
    lines = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rejected = [row for row in lines if row.get("event") == "task_complete_rejected"]
    assert rejected
    assert rejected[-1]["payload"]["reason"] == "missing_required_steps"


def test_complete_task_rejects_active_step(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "find_project_root", lambda: tmp_path)

    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)

    module.start_task("webnovel-write", {"chapter_num": 22})
    module.start_step("Step 1", "Context")
    module.complete_task()

    state = module.load_state()
    task = state["current_task"]
    assert task is not None
    assert task["status"] == module.TASK_STATUS_FAILED
    assert task["current_step"] is None


def test_fail_step_marks_task_failed_and_records_trace(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "find_project_root", lambda: tmp_path)

    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)

    module.start_task("webnovel-write", {"chapter_num": 23})
    module.start_step("Step 1", "Context")
    module.fail_step("Step 1", "context_failed", json.dumps({"warnings_count": 3}, ensure_ascii=False))

    state = module.load_state()
    task = state["current_task"]
    assert task is not None
    assert task["status"] == module.TASK_STATUS_FAILED
    assert task["current_step"] is None
    assert task["failed_steps"][-1]["id"] == "Step 1"
    assert task["failed_steps"][-1]["artifacts"]["warnings_count"] == 3

    trace_path = module.get_call_trace_path()
    lines = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(row.get("event") == "step_failed" for row in lines)


def test_cleanup_artifacts_requires_confirm(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "find_project_root", lambda: tmp_path)

    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)

    draft_path = module.default_chapter_draft_path(tmp_path, 7)
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text("draft", encoding="utf-8")

    git_called = {"count": 0}

    def _fake_run(*args, **kwargs):
        git_called["count"] += 1
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    preview = module.cleanup_artifacts(7, confirm=False)

    assert draft_path.exists()
    assert git_called["count"] == 0
    assert any(item.startswith("[预览]") for item in preview)


def test_cleanup_artifacts_confirm_deletes_with_backup(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "find_project_root", lambda: tmp_path)

    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)

    draft_path = module.default_chapter_draft_path(tmp_path, 8)
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text("draft", encoding="utf-8")

    git_called = {"count": 0, "cmd": None}

    def _fake_run(cmd, **kwargs):
        git_called["count"] += 1
        git_called["cmd"] = cmd
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    cleaned = module.cleanup_artifacts(8, confirm=True)

    assert not draft_path.exists()
    assert git_called["count"] == 1
    assert git_called["cmd"] == ["git", "reset", "HEAD", "."]
    assert any("Git 暂存区已清理" in item for item in cleaned)

    backup_dir = tmp_path / ".webnovel" / "recovery_backups"
    backups = list(backup_dir.glob("ch0008-*"))
    assert backups
