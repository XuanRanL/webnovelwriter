#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 8 · 提交后再润色循环 (Post-Commit Polish Loop)

引入背景（2026-04-20 · <example-project> Ch1 血教训）：
  Round 13 v2 / Round 14 升级了内部 13 checker + 外部 13 维度后，作者/AI 经常根据
  reader-critic-checker / reader-naturalness-checker 反馈手动改正文，然后裸跑
  `git commit -m "v3 polish"`。结果：
  - post_draft_check.py 不再跑 → 58 个 ASCII 引号漏过去（H5 P0 fail）
  - hygiene_check.py 不再跑 → word_count 漂移（state=3498 vs actual=3084）
  - workflow_state.json 不再登记 → polish 任务在工作流系统里"不存在"
  - chapter_meta.narrative_version 不变 → 下章 context-agent 看到旧版本

Step 7 commit 之后任何对正文的修改都必须走本脚本，**不得裸跑 git commit**。

职责：
1. 检测变化（hash diff against last committed version）
2. 重跑 post_draft_check（必须 exit 0）
3. 重跑 hygiene_check（必须 exit 0 或 仅 P1 警告）
4. 同步 state.json:
   - chapter_meta.{NNNN}.word_count = actual chapter word count
   - chapter_meta.{NNNN}.narrative_version 自增（v2 → v3）
   - chapter_meta.{NNNN}.updated_at = now
5. 登记 workflow_state（polish-only task，含 reason + diff_lines）
6. 可选：补录 reader-perspective checker（naturalness/reader-critic/flow）的新分数
7. Git commit `第N章 v{X}: {reason} [polish:roundN]`

用法：
  python polish_cycle.py <chapter> --reason "读者视角 6 medium 修复"
    [--project-root PATH]
    [--round-tag round13v2]
    [--narrative-version-bump]              # 自动 v2→v3
    [--narrative-version v3]                # 手动指定
    [--checker-rerun naturalness,reader-critic,flow]
    [--checker-scores '{"reader-naturalness-checker": 91}']
    [--no-commit]                           # 只跑检查不 commit

退出码：
  0 全部通过 + commit 完成
  1 hygiene/post_draft 检查失败（必须修到通过）
  2 结构错误（无变化、文件缺失、state 损坏等）
  3 git 操作失败
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional


SCRIPTS_DIR = Path(__file__).resolve().parent


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def find_chapter_file(project_root: Path, chapter: int) -> Optional[Path]:
    padded = f"{chapter:04d}"
    matches = sorted((project_root / "正文").glob(f"第{padded}章*.md"))
    return matches[0] if matches else None


def count_chinese_chars(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def git_show_head_blob(project_root: Path, rel_path: str) -> Optional[str]:
    """Read the file content from HEAD (last commit). Returns None if untracked."""
    try:
        out = subprocess.run(
            ["git", "show", f"HEAD:{rel_path}"],
            cwd=project_root,
            capture_output=True,
            timeout=10,
        )
        if out.returncode != 0:
            return None
        return out.stdout.decode("utf-8", errors="replace")
    except Exception:
        return None


def detect_chapter_changed(project_root: Path, chapter_file: Path) -> tuple[bool, int]:
    """Return (changed, diff_lines). diff_lines == -1 if HEAD blob unavailable."""
    rel = str(chapter_file.relative_to(project_root)).replace("\\", "/")
    head_text = git_show_head_blob(project_root, rel)
    current_text = chapter_file.read_text(encoding="utf-8")
    if head_text is None:
        return True, -1
    if head_text == current_text:
        return False, 0
    head_lines = set(head_text.split("\n"))
    cur_lines = set(current_text.split("\n"))
    diff_lines = len(head_lines.symmetric_difference(cur_lines))
    return True, diff_lines


def run_subprocess(cmd: list[str], cwd: Path) -> tuple[int, str]:
    try:
        out = subprocess.run(
            cmd, cwd=cwd, capture_output=True, timeout=120
        )
        text = out.stdout.decode("utf-8", errors="replace") + out.stderr.decode(
            "utf-8", errors="replace"
        )
        return out.returncode, text
    except subprocess.TimeoutExpired:
        return 124, "[TIMEOUT 120s]"
    except Exception as exc:
        return 1, f"[EXC] {exc}"


def run_post_draft_check(project_root: Path, chapter: int) -> tuple[int, str]:
    return run_subprocess(
        [
            sys.executable,
            "-X", "utf8",
            str(SCRIPTS_DIR / "post_draft_check.py"),
            str(chapter),
            "--project-root",
            str(project_root),
        ],
        cwd=project_root,
    )


def run_hygiene_check(project_root: Path, chapter: int) -> tuple[int, str]:
    """Use project's local hygiene_check shim if present, else plugin's version."""
    local = project_root / ".webnovel" / "hygiene_check.py"
    script = str(local) if local.exists() else str(SCRIPTS_DIR / "hygiene_check.py")
    return run_subprocess(
        [sys.executable, "-X", "utf8", script, str(chapter), "--project-root", str(project_root)],
        cwd=project_root,
    )


def parse_narrative_version(current: Optional[str]) -> tuple[str, int]:
    """Parse 'v2.1' → ('v', 2, 1) → returns ('v', 2). Returns ('v', 1) if missing.

    For simplicity, only supports vN[.M] form. Bump increments N (not M).
    """
    if not current:
        return ("v", 1)
    m = re.match(r"^v(\d+)", str(current))
    if not m:
        return ("v", 1)
    return ("v", int(m.group(1)))


def update_state_after_polish(
    project_root: Path,
    chapter: int,
    chapter_file: Path,
    new_version: str,
    checker_scores: Optional[dict] = None,
    notes: Optional[str] = None,
) -> dict:
    """Update state.json's chapter_meta after polish. Returns the diff summary."""
    state_p = project_root / ".webnovel" / "state.json"
    if not state_p.exists():
        raise FileNotFoundError(f"state.json missing: {state_p}")

    s = json.loads(state_p.read_text(encoding="utf-8"))
    chapter_meta = s.setdefault("chapter_meta", {})
    key = f"{chapter:04d}"
    meta = chapter_meta.setdefault(key, {})

    diff = {}
    text = chapter_file.read_text(encoding="utf-8")
    actual_wc = count_chinese_chars(text)
    old_wc = meta.get("word_count")
    if old_wc != actual_wc:
        diff["word_count"] = {"old": old_wc, "new": actual_wc}
        meta["word_count"] = actual_wc

    old_version = meta.get("narrative_version")
    if old_version != new_version:
        diff["narrative_version"] = {"old": old_version, "new": new_version}
        meta["narrative_version"] = new_version

    meta["updated_at"] = _utc_iso()

    if checker_scores:
        existing = meta.setdefault("checker_scores", {})
        cs_diff = {}
        for k, v in checker_scores.items():
            old = existing.get(k)
            if old != v:
                cs_diff[k] = {"old": old, "new": v}
                existing[k] = v
        if cs_diff:
            diff["checker_scores"] = cs_diff

    if notes:
        polish_log = meta.setdefault("polish_log", [])
        polish_log.append(
            {
                "version": new_version,
                "timestamp": _utc_iso(),
                "notes": notes,
            }
        )
        diff["polish_log_appended"] = True

    state_p.write_text(
        json.dumps(s, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return diff


def register_workflow_polish_task(
    project_root: Path,
    chapter: int,
    reason: str,
    new_version: str,
    diff_lines: int,
    state_diff: dict,
    commit_sha: Optional[str] = None,
    round_tag: Optional[str] = None,
) -> bool:
    """Append a polish-only task to workflow_state.json history.

    This is a single-step task (Step 8 · Polish), distinct from the Step 1-7 cycle.
    Direct file write rather than calling workflow_manager because Step 8 has its
    own minimal artifact contract (no need for Step 1-7 chain).
    """
    wf_p = project_root / ".webnovel" / "workflow_state.json"
    if wf_p.exists():
        wf = json.loads(wf_p.read_text(encoding="utf-8"))
    else:
        wf = {"current_task": None, "history": []}

    history = wf.setdefault("history", [])
    task_index = len(history) + 1
    started = _now_iso()
    completed = _now_iso()

    artifacts = {
        "polish_cycle": True,
        "narrative_version": new_version,
        "reason": reason,
        "diff_lines": diff_lines,
        "state_diff": state_diff,
    }
    if round_tag:
        artifacts["round_tag"] = round_tag
    if commit_sha:
        artifacts["commit"] = commit_sha
        artifacts["commit_sha"] = commit_sha
        artifacts["branch"] = "master"

    history.append(
        {
            "task_id": f"polish_{task_index:03d}",
            "command": "webnovel-polish",
            "chapter": chapter,
            "status": "completed",
            "started_at": started,
            "completed_at": completed,
            "failed_at": None,
            "failure_reason": None,
            "args": {
                "chapter_num": chapter,
                "reason": reason,
                "narrative_version": new_version,
            },
            "artifacts": artifacts,
            "completed_steps": [
                {
                    "id": "Step 8",
                    "name": "Polish Cycle",
                    "status": "completed",
                    "started_at": started,
                    "running_at": started,
                    "attempt": 1,
                    "progress_note": None,
                    "completed_at": completed,
                    "artifacts": artifacts,
                }
            ],
            "failed_steps": [],
        }
    )

    wf["last_stable_state"] = {
        "command": "webnovel-polish",
        "chapter_num": chapter,
        "completed_at": completed,
        "artifacts": artifacts,
    }
    wf_p.write_text(
        json.dumps(wf, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return True


def git_status(project_root: Path) -> str:
    rc, out = run_subprocess(["git", "status", "--porcelain"], project_root)
    return out


def git_commit_polish(
    project_root: Path,
    chapter: int,
    new_version: str,
    reason: str,
    round_tag: Optional[str],
) -> tuple[int, str, Optional[str]]:
    """Stage all changes and commit. Returns (rc, output, sha)."""
    rc, out_add = run_subprocess(["git", "add", "."], project_root)
    if rc != 0:
        return rc, out_add, None

    msg_suffix = f" [polish:{round_tag}]" if round_tag else " [polish]"
    msg = f"第{chapter}章 {new_version}: {reason}{msg_suffix}"
    rc, out_commit = run_subprocess(
        [
            "git",
            "-c", "i18n.commitEncoding=UTF-8",
            "commit",
            "-m", msg,
        ],
        project_root,
    )
    if rc != 0:
        return rc, out_commit, None

    rc, sha = run_subprocess(["git", "rev-parse", "HEAD"], project_root)
    sha = sha.strip() if rc == 0 else None
    return 0, out_commit, sha


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Step 8 · 提交后再润色循环（Post-Commit Polish Loop）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("chapter", type=int, help="章节号（整数）")
    ap.add_argument("--reason", required=True, help="润色原因（commit message + workflow log）")
    ap.add_argument(
        "--project-root", type=Path, default=None,
        help="项目根目录（默认：当前目录如果含 .webnovel）",
    )
    ap.add_argument(
        "--round-tag", default=None,
        help="round 标签（如 round13v2），追加到 commit message",
    )
    ap.add_argument(
        "--narrative-version-bump", action="store_true",
        help="自动从 state.narrative_version 自增（v2 → v3）",
    )
    ap.add_argument(
        "--narrative-version", default=None,
        help="手动指定新版本（如 v3）；与 --narrative-version-bump 二选一",
    )
    ap.add_argument(
        "--checker-rerun", default=None,
        help="逗号分隔：要补录的 checker（naturalness,reader-critic,flow）",
    )
    ap.add_argument(
        "--checker-scores", default=None,
        help="JSON：补录的 checker 分数（如 '{\"reader-naturalness-checker\": 91}'）",
    )
    ap.add_argument(
        "--no-commit", action="store_true",
        help="只跑检查 + 同步 state，不 commit（用于 dry-run / CI）",
    )
    ap.add_argument(
        "--allow-no-change", action="store_true",
        help="即使章节文件未变化也继续（用于纯 state 修复场景）",
    )
    args = ap.parse_args()

    if args.narrative_version and args.narrative_version_bump:
        print("ERROR: --narrative-version 与 --narrative-version-bump 不能同时使用")
        return 2

    project_root = (args.project_root or Path.cwd()).resolve()
    if not (project_root / ".webnovel" / "state.json").exists():
        print(f"ERROR: {project_root} 下未找到 .webnovel/state.json")
        return 2

    chapter_file = find_chapter_file(project_root, args.chapter)
    if not chapter_file:
        print(f"ERROR: 第{args.chapter:04d}章正文文件不存在")
        return 2

    print("=" * 70)
    print(f" Step 8 · 提交后再润色循环 · Ch{args.chapter}")
    print(f" 项目：{project_root.name}")
    print(f" 文件：{chapter_file.relative_to(project_root)}")
    print(f" 原因：{args.reason}")
    print("=" * 70)

    changed, diff_lines = detect_chapter_changed(project_root, chapter_file)
    print(f"\n[1/6] 变化检测：changed={changed}, diff_lines={diff_lines}")
    if not changed and not args.allow_no_change:
        print("  ✓ 章节文件与 HEAD 一致，无需 polish。如需仅修 state，加 --allow-no-change")
        return 2

    print(f"\n[2/6] post_draft_check（硬约束 7 类）...")
    rc, out = run_post_draft_check(project_root, args.chapter)
    if rc != 0:
        print("  ❌ post_draft_check 失败：")
        print(out)
        print("\n  必须修到 exit 0 才能 polish。常见修法：")
        print("    - ASCII 引号：python scripts/quote_pair_fix.py")
        print("    - U+FFFD：Grep 定位后 Edit 修复")
        print("    - 字数越界：扩写或压缩")
        return 1
    print("  ✓ post_draft_check 通过")

    state_p = project_root / ".webnovel" / "state.json"
    s = json.loads(state_p.read_text(encoding="utf-8"))
    meta = s.get("chapter_meta", {}).get(f"{args.chapter:04d}", {})
    cur_version = meta.get("narrative_version")
    if args.narrative_version:
        new_version = args.narrative_version
    elif args.narrative_version_bump:
        prefix, n = parse_narrative_version(cur_version)
        new_version = f"{prefix}{n + 1}"
    else:
        new_version = cur_version or "v1"

    checker_scores = None
    if args.checker_scores:
        try:
            checker_scores = json.loads(args.checker_scores)
        except json.JSONDecodeError as exc:
            print(f"ERROR: --checker-scores JSON 解析失败: {exc}")
            return 2

    print(f"\n[3/6] state.json 同步（narrative_version: {cur_version} → {new_version}）...")
    state_diff = update_state_after_polish(
        project_root,
        args.chapter,
        chapter_file,
        new_version,
        checker_scores=checker_scores,
        notes=args.reason,
    )
    if state_diff:
        for k, v in state_diff.items():
            print(f"  · {k}: {json.dumps(v, ensure_ascii=False)}")
    else:
        print("  · state 无字段变化")

    print(f"\n[4/6] hygiene_check...")
    rc, out = run_hygiene_check(project_root, args.chapter)
    print(out)
    if rc == 1:
        print("  ❌ hygiene_check P0 失败：必须修到通过才能 commit")
        return 1
    if rc == 2:
        print("  ⚠ hygiene_check 仅 P1 警告，继续（建议尽快修复警告项）")
    else:
        print("  ✓ hygiene_check 全通过")

    if args.no_commit:
        print("\n[5/6] --no-commit 模式：跳过 git commit")
        register_workflow_polish_task(
            project_root,
            args.chapter,
            args.reason,
            new_version,
            diff_lines,
            state_diff,
            commit_sha=None,
            round_tag=args.round_tag,
        )
        print("[6/6] workflow_state 已登记（无 commit_sha）")
        return 0

    print(f"\n[5/6] git commit...")
    pending = git_status(project_root)
    if not pending.strip():
        print("  ⚠ git 工作区无待提交修改（可能 state.json 也已 stage 在 commit 里）")
    rc, out, sha = git_commit_polish(
        project_root, args.chapter, new_version, args.reason, args.round_tag
    )
    if rc != 0:
        print("  ❌ git commit 失败：")
        print(out)
        return 3
    print(f"  ✓ commit {sha}")

    print(f"\n[6/6] workflow_state 登记 polish task...")
    register_workflow_polish_task(
        project_root,
        args.chapter,
        args.reason,
        new_version,
        diff_lines,
        state_diff,
        commit_sha=sha,
        round_tag=args.round_tag,
    )
    print("  ✓ workflow_state.history 已追加 polish task")

    print("\n" + "=" * 70)
    print(" ✅ Step 8 完成。修订版本：" + new_version)
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
