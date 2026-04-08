#!/usr/bin/env python3
"""
Workflow state manager
- Track write/review task execution status
- Detect interruption points
- Provide recovery options
- Emit call traces for observability
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from chapter_paths import default_chapter_draft_path, find_chapter_file
from project_locator import resolve_project_root
from runtime_compat import enable_windows_utf8_stdio, normalize_windows_path
from security_utils import atomic_write_json, create_secure_directory


logger = logging.getLogger(__name__)


# UTF-8 output for Windows console (CLI run only, avoid pytest capture issues)
if sys.platform == "win32" and __name__ == "__main__" and not os.environ.get("PYTEST_CURRENT_TEST"):
    enable_windows_utf8_stdio(skip_in_pytest=True)


TASK_STATUS_RUNNING = "running"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_FAILED = "failed"

STEP_STATUS_STARTED = "started"
STEP_STATUS_RUNNING = "running"
STEP_STATUS_COMPLETED = "completed"
STEP_STATUS_FAILED = "failed"


def now_iso() -> str:
    return datetime.now().isoformat()


def find_project_root(override: Optional[Path] = None) -> Path:
    """Resolve project root (containing .webnovel/state.json).

    Args:
        override: If provided, use this path directly instead of auto-detecting.
    """
    if override is not None:
        # 允许传入“工作区根目录”，统一解析到真正的 book project_root（必须包含 .webnovel/state.json）
        return resolve_project_root(str(override))
    return resolve_project_root()


# Global variable to hold CLI-provided project root
_cli_project_root: Optional[Path] = None


def _get_active_project_root() -> Path:
    """Resolve workflow paths while兼容测试中无参 monkeypatch。"""
    if _cli_project_root is not None:
        return find_project_root(_cli_project_root)
    return find_project_root()


def get_workflow_state_path() -> Path:
    """Absolute path to workflow_state.json."""
    project_root = _get_active_project_root()
    return project_root / ".webnovel" / "workflow_state.json"


def get_call_trace_path() -> Path:
    project_root = _get_active_project_root()
    return project_root / ".webnovel" / "observability" / "call_trace.jsonl"


def append_call_trace(event: str, payload: Optional[Dict[str, Any]] = None):
    """Append workflow call trace event (best effort)."""
    payload = payload or {}
    trace_path = get_call_trace_path()
    create_secure_directory(str(trace_path.parent))
    row = {
        "timestamp": now_iso(),
        "event": event,
        "payload": payload,
    }
    with open(trace_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def safe_append_call_trace(event: str, payload: Optional[Dict[str, Any]] = None):
    try:
        append_call_trace(event, payload)
    except Exception as exc:
        logger.warning("failed to append call trace for event '%s': %s", event, exc)


def expected_step_owner(command: str, step_id: str) -> str:
    """Resolve expected caller owner by command + step id.

    Returns concise owner tags to align with
    `.claude/references/claude-code-call-matrix.md`.

    Note: these owner strings are logging tags used in `call_trace.jsonl`'s
    `expected_owner` field for observability. Some map to real subagent files
    under `agents/` (context-agent, external-review-agent, data-agent,
    audit-agent), while others are conceptual tags for main-skill phases that
    have no corresponding subagent file (writer-draft, style-adapter,
    review-agents, polish-agent, backup-agent). Do not treat the absence of a
    matching agent file as a bug.
    """
    if command == "webnovel-write":
        mapping = {
            "Step 1": "context-agent",
            "Step 2A": "writer-draft",
            "Step 2B": "style-adapter",
            "Step 3": "review-agents",
            "Step 3.5": "external-review-agent",
            "Step 4": "polish-agent",
            "Step 5": "data-agent",
            "Step 6": "audit-agent",
            "Step 7": "backup-agent",
        }
        return mapping.get(step_id, "webnovel-write-skill")

    if command == "webnovel-review":
        return "webnovel-review-skill"

    return "unknown"



# Steps that can run in parallel — neither requires the other to complete first.
PARALLEL_GROUPS = {
    "webnovel-write": [{"Step 3", "Step 3.5"}],
}


def step_allowed_before(command: str, step_id: str, completed_steps: list[Dict[str, Any]]) -> bool:
    """Check simple ordering constraints by pending sequence.

    Parallel groups: steps in the same group do not require each other.
    E.g. Step 3 and Step 3.5 can start independently after Step 2B.
    """
    sequence = get_pending_steps(command)
    if step_id not in sequence:
        return True

    expected_index = sequence.index(step_id)
    completed_ids = [str(item.get("id")) for item in completed_steps]
    required_before = sequence[:expected_index]

    # Remove parallel siblings from required_before
    parallel_groups = PARALLEL_GROUPS.get(command, [])
    for group in parallel_groups:
        if step_id in group:
            required_before = [s for s in required_before if s not in group]
            break

    return all(prev in completed_ids for prev in required_before)


def missing_required_before(command: str, step_id: str, completed_steps: list[Dict[str, Any]]) -> list[str]:
    """Return the missing prerequisite steps before `step_id`."""
    sequence = get_pending_steps(command)
    if step_id not in sequence:
        return []

    expected_index = sequence.index(step_id)
    completed_ids = {str(item.get("id")) for item in completed_steps}
    required_before = sequence[:expected_index]

    parallel_groups = PARALLEL_GROUPS.get(command, [])
    for group in parallel_groups:
        if step_id in group:
            required_before = [s for s in required_before if s not in group]
            break

    return [step for step in required_before if step not in completed_ids]


def _new_task(command: str, args: Dict[str, Any]) -> Dict[str, Any]:
    started_at = now_iso()
    return {
        "command": command,
        "args": args,
        "started_at": started_at,
        "last_heartbeat": started_at,
        "status": TASK_STATUS_RUNNING,
        "current_step": None,
        "completed_steps": [],
        "failed_steps": [],
        "pending_steps": get_pending_steps(command),
        "retry_count": 0,
        "artifacts": {
            "chapter_file": {},
            "git_status": {},
            "state_json_modified": False,
            "entities_appeared": False,
            "review_completed": False,
        },
    }


def _finalize_current_step_as_failed(task: Dict[str, Any], reason: str):
    current_step = task.get("current_step")
    if not current_step:
        return
    if current_step.get("status") in {STEP_STATUS_COMPLETED, STEP_STATUS_FAILED}:
        return

    current_step = dict(current_step)
    current_step["status"] = STEP_STATUS_FAILED
    current_step["failed_at"] = now_iso()
    current_step["failure_reason"] = reason
    task.setdefault("failed_steps", []).append(current_step)
    task["current_step"] = None


def _mark_task_failed(state: Dict[str, Any], reason: str):
    task = state.get("current_task")
    if not task:
        return

    _finalize_current_step_as_failed(task, reason=reason)
    task["status"] = TASK_STATUS_FAILED
    task["failed_at"] = now_iso()
    task["failure_reason"] = reason


def _task_history_entry(state: Dict[str, Any], task: Dict[str, Any], *, status: Optional[str] = None) -> Dict[str, Any]:
    history = state.setdefault("history", [])
    return {
        "task_id": f"task_{len(history) + 1:03d}",
        "command": task.get("command"),
        "chapter": (task.get("args") or {}).get("chapter_num"),
        "status": status or task.get("status"),
        "started_at": task.get("started_at"),
        "completed_at": task.get("completed_at"),
        "failed_at": task.get("failed_at"),
        "failure_reason": task.get("failure_reason"),
        "args": deepcopy(task.get("args") or {}),
        "artifacts": deepcopy(task.get("artifacts") or {}),
        "completed_steps": deepcopy(task.get("completed_steps") or []),
        "failed_steps": deepcopy(task.get("failed_steps") or []),
    }


def _pending_required_steps(task: Dict[str, Any]) -> list[str]:
    sequence = get_pending_steps(str(task.get("command") or ""))
    completed_ids = {str(item.get("id")) for item in task.get("completed_steps", [])}
    return [step_id for step_id in sequence if step_id not in completed_ids]


def start_task(command, args):
    """Start a new task."""
    state = load_state()
    current = state.get("current_task")

    if current and current.get("status") == TASK_STATUS_RUNNING:
        current["retry_count"] = int(current.get("retry_count", 0)) + 1
        current["last_heartbeat"] = now_iso()
        state["current_task"] = current
        save_state(state)
        safe_append_call_trace(
            "task_reentered",
            {
                "command": current.get("command"),
                "chapter": current.get("args", {}).get("chapter_num"),
                "retry_count": current["retry_count"],
            },
        )
        print(f"ℹ️ 任务已在运行，执行重入标记: {current.get('command')}")
        return

    state["current_task"] = _new_task(command, args)
    save_state(state)
    safe_append_call_trace("task_started", {"command": command, "args": args})
    print(f"✅ 任务已启动: {command} {json.dumps(args, ensure_ascii=False)}")


def start_step(step_id, step_name, progress_note=None):
    """Mark step started."""
    state = load_state()
    task = state.get("current_task")
    if not task:
        print("⚠️ 无活动任务，请先使用 start-task")
        return

    command = str(task.get("command") or "")
    current_step = task.get("current_step")
    if current_step and current_step.get("id") == step_id and current_step.get("status") in {
        STEP_STATUS_STARTED,
        STEP_STATUS_RUNNING,
    }:
        current_step["running_at"] = now_iso()
        if progress_note:
            current_step["progress_note"] = progress_note
        task["last_heartbeat"] = now_iso()
        save_state(state)
        safe_append_call_trace(
            "step_reentered",
            {
                "step_id": step_id,
                "command": command,
                "chapter": task.get("args", {}).get("chapter_num"),
                "progress_note": progress_note,
            },
        )
        print(f"↻ {step_id} 继续运行")
        return

    if current_step and current_step.get("status") in {STEP_STATUS_STARTED, STEP_STATUS_RUNNING}:
        safe_append_call_trace(
            "step_start_rejected",
            {
                "step_id": step_id,
                "command": command,
                "chapter": task.get("args", {}).get("chapter_num"),
                "reason": "active_step_running",
                "active_step_id": current_step.get("id"),
            },
        )
        print(f"⚠️ 当前仍在执行 {current_step.get('id')}，拒绝启动 {step_id}")
        return

    if not step_allowed_before(command, step_id, task.get("completed_steps", [])):
        missing_steps = missing_required_before(command, step_id, task.get("completed_steps", []))
        safe_append_call_trace(
            "step_order_violation",
            {
                "step_id": step_id,
                "command": command,
                "chapter": task.get("args", {}).get("chapter_num"),
                "completed_steps": [row.get("id") for row in task.get("completed_steps", [])],
                "missing_steps": missing_steps,
            },
        )
        safe_append_call_trace(
            "step_start_rejected",
            {
                "step_id": step_id,
                "command": command,
                "chapter": task.get("args", {}).get("chapter_num"),
                "reason": "step_order_violation",
                "missing_steps": missing_steps,
            },
        )
        print(f"⚠️ Step 顺序不合法，缺少前置步骤: {missing_steps}")
        return

    owner = expected_step_owner(command, step_id)

    started_at = now_iso()
    task["current_step"] = {
        "id": step_id,
        "name": step_name,
        "status": STEP_STATUS_STARTED,
        "started_at": started_at,
        "running_at": started_at,
        "attempt": int(task.get("retry_count", 0)) + 1,
        "progress_note": progress_note,
    }
    task["current_step"]["status"] = STEP_STATUS_RUNNING
    task["status"] = TASK_STATUS_RUNNING
    task["last_heartbeat"] = now_iso()

    save_state(state)
    safe_append_call_trace(
        "step_started",
        {
            "step_id": step_id,
            "step_name": step_name,
            "command": task.get("command"),
            "chapter": task.get("args", {}).get("chapter_num"),
            "progress_note": progress_note,
            "expected_owner": owner,
        },
    )
    print(f"▶️ {step_id} 开始: {step_name}")


def complete_step(step_id, artifacts_json=None):
    """Mark step completed."""
    state = load_state()
    task = state.get("current_task")
    if not task or not task.get("current_step"):
        print("⚠️ 无活动 Step")
        return

    current_step = task["current_step"]
    if current_step.get("id") != step_id:
        print(f"⚠️ 当前 Step 为 {current_step.get('id')}，与 {step_id} 不一致，拒绝完成")
        safe_append_call_trace(
            "step_complete_rejected",
            {
                "requested_step_id": step_id,
                "active_step_id": current_step.get("id"),
                "command": task.get("command"),
            },
        )
        return

    current_step["status"] = STEP_STATUS_COMPLETED
    current_step["completed_at"] = now_iso()

    if artifacts_json:
        try:
            artifacts = json.loads(artifacts_json)
            current_step["artifacts"] = artifacts
            task["artifacts"].update(artifacts)
        except json.JSONDecodeError as exc:
            print(f"⚠️ Artifacts JSON 解析失败: {exc}")

    task["completed_steps"].append(current_step)
    task["current_step"] = None
    task["last_heartbeat"] = now_iso()

    save_state(state)
    safe_append_call_trace(
        "step_completed",
        {
            "step_id": step_id,
            "command": task.get("command"),
            "chapter": task.get("args", {}).get("chapter_num"),
        },
    )
    print(f"✅ {step_id} 完成")


def fail_step(step_id, reason="step_marked_failed", artifacts_json=None):
    """Mark the active step as failed and fail the task for diagnostics/recovery."""
    state = load_state()
    task = state.get("current_task")
    if not task or not task.get("current_step"):
        print("⚠️ 无活动 Step")
        return

    current_step = task["current_step"]
    if current_step.get("id") != step_id:
        print(f"⚠️ 当前 Step 为 {current_step.get('id')}，与 {step_id} 不一致，拒绝标记失败")
        safe_append_call_trace(
            "step_fail_rejected",
            {
                "requested_step_id": step_id,
                "active_step_id": current_step.get("id"),
                "command": task.get("command"),
            },
        )
        return

    if artifacts_json:
        try:
            artifacts = json.loads(artifacts_json)
            current_step["artifacts"] = artifacts
            task["artifacts"].update(artifacts)
        except json.JSONDecodeError as exc:
            print(f"⚠️ Artifacts JSON 解析失败: {exc}")

    current_step = dict(current_step)
    current_step["status"] = STEP_STATUS_FAILED
    current_step["failed_at"] = now_iso()
    current_step["failure_reason"] = reason
    task.setdefault("failed_steps", []).append(current_step)
    task["current_step"] = None
    task["status"] = TASK_STATUS_FAILED
    task["failed_at"] = current_step["failed_at"]
    task["failure_reason"] = reason
    task["last_heartbeat"] = now_iso()

    save_state(state)
    safe_append_call_trace(
        "step_failed",
        {
            "step_id": step_id,
            "command": task.get("command"),
            "chapter": task.get("args", {}).get("chapter_num"),
            "reason": reason,
        },
    )
    print(f"⚠️ {step_id} 已标记失败: {reason}")


def complete_task(final_artifacts_json=None):
    """Mark task completed."""
    state = load_state()
    task = state.get("current_task")
    if not task:
        print("⚠️ 无活动任务")
        return

    if task.get("status") == TASK_STATUS_FAILED:
        safe_append_call_trace(
            "task_complete_rejected",
            {
                "command": task.get("command"),
                "chapter": task.get("args", {}).get("chapter_num"),
                "reason": "task_already_failed",
            },
        )
        print("⚠️ 任务已处于失败状态，拒绝标记完成")
        return

    current_step = task.get("current_step")
    if current_step and current_step.get("status") in {STEP_STATUS_STARTED, STEP_STATUS_RUNNING}:
        reason = "task_complete_rejected_active_step"
        _mark_task_failed(state, reason=reason)
        save_state(state)
        safe_append_call_trace(
            "task_complete_rejected",
            {
                "command": task.get("command"),
                "chapter": task.get("args", {}).get("chapter_num"),
                "reason": "active_step_running",
                "active_step_id": current_step.get("id"),
            },
        )
        print(f"⚠️ 当前仍有活动 Step {current_step.get('id')}，任务已标记失败")
        return

    missing_steps = _pending_required_steps(task)
    if missing_steps:
        reason = "task_complete_rejected_missing_steps:" + ",".join(missing_steps)
        _mark_task_failed(state, reason=reason)
        save_state(state)
        safe_append_call_trace(
            "task_complete_rejected",
            {
                "command": task.get("command"),
                "chapter": task.get("args", {}).get("chapter_num"),
                "reason": "missing_required_steps",
                "missing_steps": missing_steps,
            },
        )
        print(f"⚠️ 任务缺少必需步骤，已标记失败: {missing_steps}")
        return

    task["status"] = TASK_STATUS_COMPLETED
    task["completed_at"] = now_iso()

    if final_artifacts_json:
        try:
            final_artifacts = json.loads(final_artifacts_json)
            task["artifacts"].update(final_artifacts)
        except json.JSONDecodeError as exc:
            print(f"⚠️ Final artifacts JSON 解析失败: {exc}")

    state["last_stable_state"] = extract_stable_state(task)
    state.setdefault("history", [])
    state["history"].append(_task_history_entry(state, task, status=TASK_STATUS_COMPLETED))

    state["current_task"] = None
    save_state(state)
    safe_append_call_trace(
        "task_completed",
        {
            "command": task.get("command"),
            "chapter": task.get("args", {}).get("chapter_num"),
            "completed_steps": [step.get("id") for step in task.get("completed_steps", [])],
            "failed_steps": [step.get("id") for step in task.get("failed_steps", [])],
        },
    )
    print("🎀 任务完成")


def detect_interruption():
    """Detect interruption state."""
    state = load_state()
    if not state or "current_task" not in state or state["current_task"] is None:
        return None

    task = state["current_task"]
    if task.get("status") == TASK_STATUS_COMPLETED:
        return None

    last_heartbeat = datetime.fromisoformat(task["last_heartbeat"])
    elapsed = (datetime.now() - last_heartbeat).total_seconds()

    interrupt_info = {
        "command": task["command"],
        "args": task["args"],
        "task_status": task.get("status"),
        "current_step": task.get("current_step"),
        "completed_steps": task.get("completed_steps", []),
        "failed_steps": task.get("failed_steps", []),
        "elapsed_seconds": elapsed,
        "artifacts": task.get("artifacts", {}),
        "started_at": task.get("started_at"),
        "retry_count": int(task.get("retry_count", 0)),
    }

    safe_append_call_trace(
        "interruption_detected",
        {
            "command": task.get("command"),
            "chapter": task.get("args", {}).get("chapter_num"),
            "task_status": task.get("status"),
            "current_step": (task.get("current_step") or {}).get("id"),
            "elapsed_seconds": elapsed,
        },
    )
    return interrupt_info


def analyze_recovery_options(interrupt_info):
    """Analyze recovery options based on interruption point."""
    current_step = interrupt_info["current_step"]
    command = interrupt_info["command"]
    chapter_num = interrupt_info["args"].get("chapter_num", "?")

    if not current_step:
        return [
            {
                "option": "A",
                "label": "从头开始",
                "risk": "low",
                "description": "重新执行完整流程",
                "actions": [
                    "删除 workflow_state.json 当前任务",
                    f"执行 /{command} {chapter_num}",
                ],
            }
        ]

    step_id = current_step["id"]

    # 注：Step 1.5 已在 v5.6.0 前内置到 Step 1（Context Agent 生成执行包时产出 Context Contract）。
    # 保留 "Step 1.5" 作为历史兼容分支，避免读取旧 workflow_state.json 时断裂；新流程不会再写入该 id。
    if step_id in {"Step 1", "Step 1.5"}:
        return [
            {
                "option": "A",
                "label": "从 Step 1 重新开始",
                "risk": "low",
                "description": "重新加载上下文",
                "actions": [
                    "清理中断状态",
                    f"执行 /{command} {chapter_num}",
                ],
            }
        ]

    if step_id in {"Step 2", "Step 2A", "Step 2B"}:
        project_root = find_project_root()
        existing_chapter = find_chapter_file(project_root, chapter_num)
        draft_path = None
        if existing_chapter:
            chapter_path = str(existing_chapter.relative_to(project_root))
        else:
            draft_path = default_chapter_draft_path(project_root, chapter_num)
            chapter_path = str(draft_path.relative_to(project_root))

        options = [
            {
                "option": "A",
                "label": "删除半成品，从 Step 1 重启",
                "risk": "low",
                "description": f"清理 {chapter_path}，重新生成章节",
                "actions": [
                    f"删除 {chapter_path}（如存在）",
                    "清理 Git 暂存区",
                    "清理中断状态",
                    f"执行 /{command} {chapter_num}",
                ],
            }
        ]

        candidate = existing_chapter or draft_path
        if candidate and candidate.exists():
            options.append(
                {
                    "option": "B",
                    "label": "回滚到上一章",
                    "risk": "medium",
                    "description": "丢弃当前章节进度",
                    "actions": [
                        f"git reset --hard ch{(chapter_num - 1):04d}",
                        "清理中断状态",
                        f"重新决定是否继续 Ch{chapter_num}",
                    ],
                }
            )
        return options

    if step_id == "Step 3":
        return [
            {
                "option": "A",
                "label": "重新执行审查",
                "risk": "medium",
                "description": "重新调用审查员并生成报告",
                "actions": ["重新执行审查", "生成审查报告", "继续 Step 4 润色"],
            },
            {
                "option": "B",
                "label": "跳过审查直接润色",
                "risk": "low",
                "description": "后续可用 /webnovel-review 补审",
                "actions": ["标记审查已跳过", "继续 Step 4 润色"],
            },
        ]

    if step_id == "Step 3.5":
        return [
            {
                "option": "A",
                "label": "重新执行外部审查",
                "risk": "medium",
                "description": "重新调用 9 模型外部审查（核心模型按 fallback 链重试）",
                "actions": ["重新执行外部模型审查", "合并内外部分数", "继续 Step 4 润色"],
            },
            {
                "option": "B",
                "label": "跳过外部审查，使用纯内部分数",
                "risk": "low",
                "description": "退化为纯内部分数，后续可补跑外部审查",
                "actions": ["标记外部审查已跳过", "overall_score 退化为纯内部分数", "继续 Step 4 润色"],
            },
        ]

    if step_id == "Step 4":
        project_root = find_project_root()
        existing_chapter = find_chapter_file(project_root, chapter_num)
        draft_path = None
        if existing_chapter:
            chapter_path = str(existing_chapter.relative_to(project_root))
        else:
            draft_path = default_chapter_draft_path(project_root, chapter_num)
            chapter_path = str(draft_path.relative_to(project_root))

        return [
            {
                "option": "A",
                "label": "继续润色",
                "risk": "low",
                "description": f"继续润色 {chapter_path}，完成后进入 Step 5",
                "actions": [f"打开并继续润色 {chapter_path}", "保存文件", "继续 Step 5（Data Agent）"],
            },
            {
                "option": "B",
                "label": "删除润色稿，从 Step 2A 重写",
                "risk": "medium",
                "description": f"删除 {chapter_path} 并重新生成章节内容",
                "actions": [f"删除 {chapter_path}", "清理 Git 暂存区", "清理中断状态", f"执行 /{command} {chapter_num}"],
            },
        ]

    if step_id == "Step 5":
        return [
            {
                "option": "A",
                "label": "从 Step 5 重新开始",
                "risk": "low",
                "description": "重新运行 Data Agent（幂等）",
                "actions": ["重新调用 Data Agent", "继续 Step 6（Audit Gate）"],
            }
        ]

    if step_id == "Step 6":
        return [
            {
                "option": "A",
                "label": "按 blocking_issues 修复后重跑 audit",
                "risk": "low",
                "description": "读取 audit_reports/ch{NNNN}.json，按 remediation 清单逐项修复",
                "actions": [
                    f"查看 .webnovel/audit_reports/ch{chapter_num:04d}.json 的 blocking_issues",
                    "按 remediation 字段指引修复 (通常回到 Step 1/3/4/5)",
                    "重跑 Step 6: CLI + audit-agent",
                ],
            },
            {
                "option": "B",
                "label": "仅重跑 audit-agent (怀疑 agent 本身出错)",
                "risk": "low",
                "description": "不动任何产物，只重跑 Step 6 审计",
                "actions": [
                    "webnovel.py audit chapter --chapter %d --mode standard" % chapter_num,
                    "Task(audit-agent, chapter=%d)" % chapter_num,
                ],
            },
            {
                "option": "C",
                "label": "强制跳过审计 (高风险)",
                "risk": "high",
                "description": "绕过 Step 6 直接进入 Step 7 Git 提交 — 仅在 audit-agent 本身严重故障时使用",
                "actions": [
                    "用户显式确认跳过",
                    "workflow complete-step --step-id 'Step 6' --artifacts '{\"forced_skip\": true}'",
                    "进入 Step 7",
                ],
            },
        ]

    if step_id == "Step 7":
        return [
            {
                "option": "A",
                "label": "继续 Git 提交",
                "risk": "low",
                "description": "完成未完成的 Git commit + tag",
                "actions": ["检查 Git 暂存区", "重新执行 backup_manager.py", "继续 complete-task"],
            },
            {
                "option": "B",
                "label": "回滚 Git 改动",
                "risk": "medium",
                "description": "丢弃暂存区所有改动",
                "actions": ["git reset HEAD .", f"删除第{chapter_num}章文件", "清理中断状态"],
            },
        ]

    return [
        {
            "option": "A",
            "label": "从头开始",
            "risk": "low",
            "description": "重新执行完整流程",
            "actions": ["清理所有中断 artifacts", f"执行 /{command} {chapter_num}"],
        }
    ]


def _backup_chapter_for_cleanup(project_root: Path, chapter_num: int, chapter_path: Path) -> Path:
    """Backup chapter file before destructive cleanup."""
    backup_dir = project_root / ".webnovel" / "recovery_backups"
    create_secure_directory(str(backup_dir))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"ch{chapter_num:04d}-{chapter_path.name}.{timestamp}.bak"
    backup_path = backup_dir / backup_name
    shutil.copy2(chapter_path, backup_path)
    return backup_path


def cleanup_artifacts(chapter_num, *, confirm: bool = False):
    """Cleanup partial artifacts."""
    artifacts_cleaned = []
    planned_actions = []

    project_root = find_project_root()

    chapter_path = find_chapter_file(project_root, chapter_num)
    if chapter_path is None:
        draft_path = default_chapter_draft_path(project_root, chapter_num)
        if draft_path.exists():
            chapter_path = draft_path

    if chapter_path and chapter_path.exists():
        planned_actions.append(f"删除章节文件: {chapter_path.relative_to(project_root)}")

    planned_actions.append("重置 Git 暂存区: git reset HEAD .")

    if not confirm:
        preview_items = [f"[预览] {action}" for action in planned_actions]
        safe_append_call_trace(
            "artifacts_cleanup_preview",
            {
                "chapter": chapter_num,
                "planned_actions": planned_actions,
                "confirmed": False,
            },
        )
        print("⚠️ 检测到高风险清理操作，当前仅预览。若确认执行，请追加 --confirm。")
        return preview_items or ["[预览] 无可清理项"]

    if chapter_path and chapter_path.exists():
        try:
            backup_path = _backup_chapter_for_cleanup(project_root, chapter_num, chapter_path)
        except OSError as exc:
            error_msg = f"❌ 章节备份失败，已取消删除: {exc}"
            safe_append_call_trace(
                "artifacts_cleanup_backup_failed",
                {
                    "chapter": chapter_num,
                    "chapter_file": str(chapter_path),
                    "error": str(exc),
                },
            )
            return [error_msg]

        chapter_path.unlink()
        artifacts_cleaned.append(str(chapter_path.relative_to(project_root)))
        artifacts_cleaned.append(f"章节备份已保存: {backup_path.relative_to(project_root)}")

    result = subprocess.run(["git", "reset", "HEAD", "."], cwd=project_root, capture_output=True, text=True)
    if result.returncode == 0:
        artifacts_cleaned.append("Git 暂存区已清理（project）")
    else:
        git_error = (result.stderr or "").strip() or "unknown error"
        artifacts_cleaned.append(f"⚠️ Git 暂存区清理失败: {git_error}")

    safe_append_call_trace(
        "artifacts_cleaned",
        {
            "chapter": chapter_num,
            "items": artifacts_cleaned,
            "planned_actions": planned_actions,
            "confirmed": True,
            "git_reset_ok": result.returncode == 0,
        },
    )
    return artifacts_cleaned or ["无可清理项"]


def clear_current_task():
    """Clear interrupted current task."""
    state = load_state()
    task = state.get("current_task")
    if task:
        safe_append_call_trace(
            "task_cleared",
            {
                "command": task.get("command"),
                "chapter": task.get("args", {}).get("chapter_num"),
                "status": task.get("status"),
            },
        )
        state["current_task"] = None
        save_state(state)
        print("✅ 中断任务已清除")
    else:
        print("⚠️ 无中断任务")


def fail_current_task(reason: str = "manual_fail"):
    """Mark current task as failed and keep state for diagnostics."""
    state = load_state()
    task = state.get("current_task")
    if not task:
        print("⚠️ 无活动任务")
        return

    _mark_task_failed(state, reason=reason)
    save_state(state)
    safe_append_call_trace(
        "task_failed",
        {
            "command": task.get("command"),
            "chapter": task.get("args", {}).get("chapter_num"),
            "reason": reason,
        },
    )
    print(f"⚠️ 任务已标记失败: {reason}")


def load_state():
    """Load workflow state."""
    state_file = get_workflow_state_path()
    if not state_file.exists():
        return {"current_task": None, "last_stable_state": None, "history": []}
    with open(state_file, "r", encoding="utf-8") as f:
        state = json.load(f)

    state.setdefault("current_task", None)
    state.setdefault("last_stable_state", None)
    state.setdefault("history", [])
    if state.get("current_task"):
        state["current_task"].setdefault("failed_steps", [])
        state["current_task"].setdefault("retry_count", 0)
    for item in state.get("history", []):
        item.setdefault("args", {})
        item.setdefault("artifacts", {})
        item.setdefault("completed_steps", [])
        item.setdefault("failed_steps", [])
    return state


def save_state(state):
    """Save workflow state atomically."""
    state_file = get_workflow_state_path()
    create_secure_directory(str(state_file.parent))
    atomic_write_json(state_file, state, use_lock=True, backup=False)


def get_pending_steps(command):
    """Get command pending step list."""
    if command == "webnovel-write":
        # v2: Step 1 内置 Contract v2，不再单独记录 Step 1.5，避免产生 step_order_violation 噪声。
        # Step 3.5 与 Step 3 并行执行，但需独立记录进度以支持 /webnovel-resume 恢复。
        # v3: Step 6 = Audit Gate (audit-agent), Step 7 = Git Commit (backup-agent)
        return ["Step 1", "Step 2A", "Step 2B", "Step 3", "Step 3.5", "Step 4", "Step 5", "Step 6", "Step 7"]
    if command == "webnovel-review":
        return ["Step 1", "Step 2", "Step 3", "Step 4", "Step 5", "Step 6", "Step 7", "Step 8"]
    return []


def extract_stable_state(task):
    """Extract stable state snapshot."""
    return {
        "command": task["command"],
        "chapter_num": task["args"].get("chapter_num"),
        "completed_at": task.get("completed_at"),
        "artifacts": task.get("artifacts", {}),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="工作流状态管理")
    parser.add_argument(
        "--project-root",
        dest="global_project_root",
        help="项目根目录（可选，默认自动检测）",
    )
    subparsers = parser.add_subparsers(dest="action", help="操作类型")

    def add_project_root_arg(subparser):
        """Allow --project-root after subcommand for compatibility."""
        subparser.add_argument("--project-root", help="项目根目录（可选，默认自动检测）")

    p_start_task = subparsers.add_parser("start-task", help="开始新任务")
    add_project_root_arg(p_start_task)
    p_start_task.add_argument("--command", required=True, help="命令名称")
    p_start_task.add_argument("--chapter", type=int, help="章节号")

    p_start_step = subparsers.add_parser("start-step", help="开始 Step")
    add_project_root_arg(p_start_step)
    p_start_step.add_argument("--step-id", required=True, help="Step ID")
    p_start_step.add_argument("--step-name", required=True, help="Step 名称")
    p_start_step.add_argument("--note", help="进度备注")

    p_complete_step = subparsers.add_parser("complete-step", help="完成 Step")
    add_project_root_arg(p_complete_step)
    p_complete_step.add_argument("--step-id", required=True, help="Step ID")
    p_complete_step.add_argument(
        "--status",
        choices=["completed", "failed"],
        default="completed",
        help="完成状态（默认 completed）",
    )
    p_complete_step.add_argument("--artifacts", help="Artifacts JSON")
    p_complete_step.add_argument("--reason", default="step_marked_failed", help="失败原因（仅 failed 时使用）")

    p_complete_task = subparsers.add_parser("complete-task", help="完成任务")
    add_project_root_arg(p_complete_task)
    p_complete_task.add_argument("--artifacts", help="Final artifacts JSON")

    p_fail_task = subparsers.add_parser("fail-task", help="标记任务失败")
    add_project_root_arg(p_fail_task)
    p_fail_task.add_argument("--reason", default="manual_fail", help="失败原因")

    p_detect = subparsers.add_parser("detect", help="检测中断")
    add_project_root_arg(p_detect)

    p_cleanup = subparsers.add_parser("cleanup", help="清理 artifacts")
    add_project_root_arg(p_cleanup)
    p_cleanup.add_argument("--chapter", type=int, required=True, help="章节号")
    p_cleanup.add_argument("--confirm", action="store_true", help="确认执行删除与 Git 重置（高风险）")

    p_clear = subparsers.add_parser("clear", help="清除中断任务")
    add_project_root_arg(p_clear)

    args = parser.parse_args()

    # Set global project root if provided (support both before/after subcommand).
    project_root_arg = getattr(args, "project_root", None) or getattr(args, "global_project_root", None)
    if project_root_arg:
        _cli_project_root = normalize_windows_path(project_root_arg)

    if args.action == "start-task":
        start_task(args.command, {"chapter_num": args.chapter})
    elif args.action == "start-step":
        start_step(args.step_id, args.step_name, args.note)
    elif args.action == "complete-step":
        if args.status == "failed":
            fail_step(args.step_id, args.reason, args.artifacts)
        else:
            complete_step(args.step_id, args.artifacts)
    elif args.action == "complete-task":
        complete_task(args.artifacts)
    elif args.action == "fail-task":
        fail_current_task(args.reason)
    elif args.action == "detect":
        interrupt = detect_interruption()
        if interrupt:
            print("\n🔶 检测到中断任务:")
            print(json.dumps(interrupt, ensure_ascii=False, indent=2))
            print("\n📕 恢复选项:")
            options = analyze_recovery_options(interrupt)
            print(json.dumps(options, ensure_ascii=False, indent=2))
        else:
            print("✅ 无中断任务")
    elif args.action == "cleanup":
        cleaned = cleanup_artifacts(args.chapter, confirm=args.confirm)
        if args.confirm:
            print(f"✅ 已清理: {', '.join(cleaned)}")
        else:
            for item in cleaned:
                print(item)
            print("⚠️ 以上为预览，未执行实际清理。")
    elif args.action == "clear":
        clear_current_task()
    else:
        parser.print_help()
