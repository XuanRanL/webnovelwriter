#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 8 · 提交后再润色循环 (Post-Commit Polish Loop)

引入背景（2026-04-20 · 末世重生 Ch1 血教训）：
  Round 13 v2 / Round 14 升级了内部 13 checker + 外部 13 维度后，作者/AI 经常根据
  reader-critic-checker / reader-naturalness-checker 反馈手动改正文，然后裸跑
  `git commit -m "v3 polish"`。结果：
  - post_draft_check.py 不再跑 → 58 个 ASCII 引号漏过去（H5 P0 fail）
  - hygiene_check.py 不再跑 → word_count 漂移（state=3498 vs actual=3084）
  - workflow_state.json 不再登记 → polish 任务在工作流系统里"不存在"
  - chapter_meta.narrative_version 不变 → 下章 context-agent 看到旧版本

Step 7 commit 之后任何对正文的修改都必须走本脚本，**不得裸跑 git commit**。

职责顺序（**commit 是最后一步原子落盘 · 2026-04-20 v2 修正**）：
1. 检测变化（hash diff against last committed version）
2. 重跑 post_draft_check（必须 exit 0）
3. 同步 state.json:
   - chapter_meta.{NNNN}.word_count = actual chapter word count
   - chapter_meta.{NNNN}.narrative_version 自增（v2 → v3）
   - chapter_meta.{NNNN}.updated_at = now
   - chapter_meta.{NNNN}.polish_log 追加
   - 可选：补录 reader-perspective checker 的新分数
4. 重跑 hygiene_check（必须 exit 0 或 仅 P1 警告）
5. **预登记** workflow_state polish_NNN task（commit_sha=None 占位）
   — 与 Step 7 的 start-step 对称：commit 里必须包含 workflow 登记痕迹
6. **Git commit**（真正最后一步原子落盘）：一次 commit 包含
   正文 + state.json + workflow_state.json 三者全部变更
7. 回填 commit_sha 到 workflow_state.json
   — 唯一尾巴，与 Step 7 的 complete-step 尾巴性质一致；
   即使回填失败，commit message `[polish:{round_tag}]` 标签 + `git log --grep`
   也足以重建 sha 映射

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


def backfill_commit_sha(project_root: Path, commit_sha: str) -> None:
    """Commit 成功后，把 sha 回填到最近一次预登记的 polish task。

    这一步是必要的尾巴：sha 是 commit 的内容 hash，不可能提前预测，只能 commit 后回填。
    回填发生在 commit 之后，会让 workflow_state.json 相对工作区为脏（未 commit），
    但这和 Step 7 的 complete-step/complete-task 尾巴是同一性质：下次 git add 带走。

    回填失败不致命：commit message 里的 [polish:{round_tag}] 标签足以让
    `git log --grep="[polish:"` 重建 sha 映射。
    """
    wf_p = project_root / ".webnovel" / "workflow_state.json"
    if not wf_p.exists():
        return
    wf = json.loads(wf_p.read_text(encoding="utf-8"))
    history = wf.get("history", [])
    if not history:
        return
    # 找到最后一个 polish task
    for task in reversed(history):
        if task.get("command") != "webnovel-polish":
            continue
        task.setdefault("artifacts", {})["commit"] = commit_sha
        task["artifacts"]["commit_sha"] = commit_sha
        task["artifacts"]["branch"] = "master"
        # completed_steps 里 Step 8 artifact 也同步
        for cs in task.get("completed_steps", []):
            if cs.get("id") == "Step 8":
                cs.setdefault("artifacts", {})["commit"] = commit_sha
                cs["artifacts"]["commit_sha"] = commit_sha
                cs["artifacts"]["branch"] = "master"
        # last_stable_state 也同步
        lss = wf.get("last_stable_state", {})
        if lss.get("command") == "webnovel-polish":
            lss.setdefault("artifacts", {})["commit"] = commit_sha
            lss["artifacts"]["commit_sha"] = commit_sha
            lss["artifacts"]["branch"] = "master"
        break
    wf_p.write_text(
        json.dumps(wf, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def git_status(project_root: Path) -> str:
    rc, out = run_subprocess(["git", "status", "--porcelain"], project_root)
    return out


def _list_worktree_modifications(project_root: Path) -> list[str]:
    """Return list of modified/added/untracked path strings (POSIX-style) from git status --porcelain."""
    rc, out = run_subprocess(["git", "status", "--porcelain"], project_root)
    if rc != 0:
        return []
    paths: list[str] = []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        # porcelain v1 format: XY path  (或 XY "path with spaces")
        rest = line[3:].strip()
        if " -> " in rest:  # rename: "A -> B", 取 B
            rest = rest.split(" -> ", 1)[1].strip()
        # 去掉 porcelain 给路径加的双引号（有中文/特殊字符时）
        if rest.startswith('"') and rest.endswith('"'):
            rest = rest[1:-1]
            # git 对含 \ 的路径会用 octal escape，简单还原双反斜杠
            rest = rest.replace("\\\\", "\\")
        paths.append(rest.replace("\\", "/"))
    return paths


def _build_polish_stage_targets(project_root: Path, chapter: int, chapter_file: Path) -> list[str]:
    """Return the precise list of git paths allowed into a polish commit.

    设计原则（2026-04-23 Ch7 P0 根治）：
      - 仅包含「当前章正文 + state.json + workflow_state.json + 该章 polish_report」
      - 避免跨章污染（Ch1 v7 commit 连带吞 ch2/4/5/6 的血教训）
    """
    rel_chapter = str(chapter_file.relative_to(project_root)).replace("\\", "/")
    targets: list[str] = [
        rel_chapter,
        ".webnovel/state.json",
        ".webnovel/workflow_state.json",
    ]
    polish_report = project_root / ".webnovel" / "polish_reports" / f"ch{chapter:04d}.md"
    if polish_report.exists():
        targets.append(f".webnovel/polish_reports/ch{chapter:04d}.md")
    audit_report = project_root / ".webnovel" / "audit_reports" / f"ch{chapter:04d}.json"
    if audit_report.exists():
        targets.append(f".webnovel/audit_reports/ch{chapter:04d}.json")
    return targets


def git_commit_polish(
    project_root: Path,
    chapter: int,
    new_version: str,
    reason: str,
    round_tag: Optional[str],
    chapter_file: Path,
) -> tuple[int, str, Optional[str]]:
    """Stage precise polish targets and commit. Returns (rc, output, sha).

    不再用 `git add .` 宽口（2026-04-23 Ch7 RCA P0 根治：Ch1 v7 commit 吞掉
    ch2/4/5/6 drift 正文，造成四章 polish_log/narrative_version 未更新）。
    改为只 stage 目标章 + state + workflow + 该章 polish_report，其他 drift
    会被列在警告里让作者知晓，但不会被本次 polish commit 吞入。
    """
    targets = _build_polish_stage_targets(project_root, chapter, chapter_file)

    # 扫描其他 drift 并警告（不阻断）
    all_dirty = _list_worktree_modifications(project_root)
    target_set = {t for t in targets}
    # state.json 会被写入，也应忽略（已在 targets 里）
    others = [p for p in all_dirty if p not in target_set]
    if others:
        print("  ⚠ 工作区还有其他未 commit 改动（不会被本次 polish commit 吞入）:")
        for f in others[:15]:
            print(f"    - {f}")
        if len(others) > 15:
            print(f"    … 还有 {len(others) - 15} 个文件未列出")
        print("  建议：若是其他章 drift → 分章跑 polish_cycle；若是插件/大纲改动 → 另起 commit。")

    rc, out_add = run_subprocess(["git", "add", "--"] + targets, project_root)
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
    print(f"\n[1/7] 变化检测：changed={changed}, diff_lines={diff_lines}")
    if not changed and not args.allow_no_change:
        print("  ✓ 章节文件与 HEAD 一致，无需 polish。如需仅修 state，加 --allow-no-change")
        return 2

    print(f"\n[2/7] post_draft_check（硬约束 7 类）...")
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

    # 幂等检查（Round 14.5.3）：若 new_version 已存在于 polish_log 里，且 changed=False（--allow-no-change 场景），
    # 通常是误跑/重跑。给出警告但不阻断（允许作者有意重登记）。
    polish_log_existing = meta.get("polish_log", []) or []
    if polish_log_existing and isinstance(polish_log_existing, list):
        existing_versions = [e.get("version") for e in polish_log_existing if isinstance(e, dict)]
        if new_version in existing_versions and not changed:
            print(f"\n  ⚠ 幂等警告：polish_log 里已有 version={new_version}（且正文未改动）。")
            print("     这通常意味着误跑或重复登记。继续会追加一条新的 polish_log 条目。")
            print("     若非预期，Ctrl+C 取消；否则等 3 秒后继续...")
            import time
            try:
                time.sleep(3)
            except KeyboardInterrupt:
                print("  ❌ 用户取消")
                return 2

    checker_scores = None
    if args.checker_scores:
        try:
            checker_scores = json.loads(args.checker_scores)
        except json.JSONDecodeError as exc:
            print(f"ERROR: --checker-scores JSON 解析失败: {exc}")
            return 2

    print(f"\n[3/7] state.json 同步（narrative_version: {cur_version} → {new_version}）...")
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

    print(f"\n[4/7] hygiene_check...")
    rc, out = run_hygiene_check(project_root, args.chapter)
    print(out)
    if rc == 1:
        print("  ❌ hygiene_check P0 失败：必须修到通过才能 commit")
        return 1
    if rc == 2:
        print("  ⚠ hygiene_check 仅 P1 警告，继续（建议尽快修复警告项）")
    else:
        print("  ✓ hygiene_check 全通过")

    # [5/7] workflow 预登记 —— 与 Step 7 对称：commit 里必须包含 workflow 登记痕迹，
    # 而不是登记完全发生在 commit 之后。这样 git 历史能自证"这个 commit 属于 Step 8 polish
    # 的 polish_NNN task"。commit_sha 留 pending，commit 后回填（唯一尾巴，一个字段）。
    print(f"\n[5/7] workflow 预登记 polish task（commit_sha=pending）...")
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
    print("  ✓ workflow_state.history 已预登记 polish task")

    if args.no_commit:
        print("\n[6/7] --no-commit 模式：跳过 git commit")
        print("[7/7] 跳过 commit_sha 回填（dry-run）")
        return 0

    # [6/7] git commit —— 真正的最后一步原子落盘。本次 commit 内容包含：
    #   - 正文（用户手工 polish 的修订）
    #   - state.json（word_count / narrative_version / polish_log 等同步）
    #   - workflow_state.json（polish_NNN task 登记，带 commit_sha=None 占位）
    # 所以 git 历史单独看这一个 commit 就能重建 polish 语义，不再依赖外部解释。
    print(f"\n[6/7] git commit（最后一步原子落盘）...")
    pending = git_status(project_root)
    if not pending.strip():
        print("  ⚠ git 工作区无待提交修改")
    rc, out, sha = git_commit_polish(
        project_root, args.chapter, new_version, args.reason, args.round_tag,
        chapter_file,
    )
    if rc != 0:
        print("  ❌ git commit 失败：")
        print(out)
        print("\n  注意：workflow_state.json 已预登记 polish task 但 commit 失败。")
        print("  修复办法（任选其一）：")
        print("   a) 修复 git 问题后再跑一次 polish_cycle --allow-no-change 会重新登记+commit")
        print("   b) 手动 git add + git commit 完成本次修订后跑 --allow-no-change 回填 sha")
        return 3
    print(f"  ✓ commit {sha}")

    # [7/7] 回填 commit_sha —— 唯一尾巴（与 Step 7 的 complete-step 尾巴性质一致）。
    # 这一步只改 workflow_state.json 里刚才预登记那个 task 的 commit_sha 字段，
    # 留在工作区等下次 git add 带走。失败不致命（有 commit message 里的 [polish:...] 标签兜底）。
    print(f"\n[7/7] 回填 commit_sha 到 workflow_state.json...")
    try:
        backfill_commit_sha(project_root, sha)
        print(f"  ✓ polish task commit_sha 已回填 = {sha[:12]}...")
    except Exception as exc:
        print(f"  ⚠ sha 回填失败（不致命，commit 已成功）: {exc}")

    print("\n" + "=" * 70)
    print(" ✅ Step 8 完成。修订版本：" + new_version)
    print(" ℹ workflow_state.json 的 sha 回填未 commit（与 Step 7 尾巴一致，下次 git add 带走）")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
