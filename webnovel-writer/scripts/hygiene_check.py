#!/usr/bin/env python3
"""
章节收尾守门脚本 (hygiene_check) — 框架版

触发时机：
  - Step 7 (git commit) 前强制执行
  - 每次章节收尾调用：python hygiene_check.py <chapter_num> [--project-root <path>]

目标：
  在审计通过和 git commit 之间加一道独立闸门，阻止已知类型的 bug 再次流入 git。
  框架版提供所有通用检查项 H1-H17，项目可通过 .webnovel/hygiene_check_local.py
  追加项目特定检查（如力量体系版本对齐）。

检查项：
  P0 致命（exit 1）：
    H1  项目根下无 0 字节空文件
    H2  state.chapter_meta[NNNN] 存在且 core 22 字段完备
    H3  workflow_state.current_task 正常闭环（非 running、非伪造登记）
    H4  正文无 U+FFFD 乱码字符
    H5  正文无 ASCII 双引号（必须中文弯引号）
    H6  正文行尾统一 LF
    H14 Step 1 执行包已落盘：.webnovel/context/chNNNN_context.json + .md
    H15 Step 4 润色报告已落盘：.webnovel/polish_reports/chNNNN.md 且含 anti_ai_force_check
    H16 workflow_state completed_steps 每步 artifact 含语义字段（非 {"v2":true} 占位）
  P1 重要（exit 2，不阻断但警告）：
    H7  章节字数与 state.word_count 一致（误差 < 2%）
    H8  foreshadowing 字段无重复（planted vs added、paid vs resolved）
    H9  overall_score 与 checker_scores.overall 对齐
    H10 项目根布局干净（5 个合法目录 + 允许的隐藏文件）
    H11 审查报告中 overall_score 出现次数 <= 1
    H17 chapter_meta.allusions_used schema 合规（list[dict] with 7 fields）
  P2 建议（exit 2）：
    H12 context_snapshot 存在
    H13 项目特定检查（通过 .webnovel/hygiene_check_local.py 扩展）

输出：
  - 所有 P0 通过 → exit 0（允许 commit）
  - 有 P0 失败 → exit 1 + 明细
  - 只有 P1/P2 失败 → exit 2 + 明细（警告，不阻断）
"""
import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional


REQUIRED_ARTIFACT_FIELDS = {
    "webnovel-write": {
        "Step 1": ["file", "snapshot", "context_file"],
        "Step 2A": ["word_count"],
        "Step 2B": ["style_applied", "deviation_notes"],
        "Step 3": ["overall_score", "checker_count", "internal_avg", "review_score"],
        "Step 3.5": ["external_avg", "models_ok", "external_models_ok"],
        "Step 4": ["anti_ai_force_check", "polish_report", "fixes"],
        "Step 5": ["state_modified", "entities", "foreshadowing", "scene_count", "chapter_meta_fields"],
        "Step 6": ["decision", "audit_report", "audit_decision"],
        "Step 7": ["commit", "branch", "commit_sha"],
    }
}
PLACEHOLDER_ONLY_FIELDS = {"v2", "ok", "chapter_completed", "committed"}


def _is_semantically_empty(value):
    """Mirror of workflow_manager._is_semantically_empty — must stay in sync.

    Numeric 0 / 0.0 counts as empty (word_count=0 / score=0 are forgery signals).
    bool False/True always count as non-empty (style_applied=False is signal).
    """
    if value is None or value == "":
        return True
    if isinstance(value, (list, dict, tuple, set)) and len(value) == 0:
        return True
    if type(value) is bool:
        return False
    if isinstance(value, (int, float)) and value == 0:
        return True
    return False

CORE_22_FIELDS = {
    "chapter", "title", "word_count", "summary", "hook_strength", "scene_count",
    "key_beats", "characters", "locations", "created_at", "updated_at",
    "protagonist_state", "location_current", "power_realm", "golden_finger_level",
    "time_anchor", "end_state", "foreshadowing_planted", "foreshadowing_paid",
    "strand_dominant", "review_score", "checker_scores", "allusions_used",
}
# Fields in CORE_22 where an empty list/dict is semantically valid
# (e.g. Ch1 has 0 paid foreshadowing; a bridge chapter has 0 new allusions)
CORE_22_LIST_FIELDS_ALLOW_EMPTY = {
    "foreshadowing_planted", "foreshadowing_paid", "allusions_used",
    "key_beats", "characters", "locations", "checker_scores",
}

ALLUSION_REQUIRED_KEYS = {"id", "snippet", "type", "source", "carrier", "function", "is_original"}
# 注意：type 和 function 允许作者扩展与复合（例如 "伏笔+氛围+角色底色"），hygiene 只检查字段结构
# 完整性，不强制枚举值。典故密度与载体合规由 Step 6 audit-agent 的 E11-E13 负责语义判断。


def find_project_root(override: Optional[str] = None) -> Path:
    if override:
        p = Path(override).resolve()
        if (p / ".webnovel" / "state.json").exists():
            return p
        raise SystemExit(f"ERROR: --project-root {p} 下未找到 .webnovel/state.json")
    cur = Path.cwd().resolve()
    while cur != cur.parent:
        if (cur / ".webnovel" / "state.json").exists():
            return cur
        cur = cur.parent
    raise SystemExit("ERROR: cannot locate project root (missing .webnovel/state.json)")


class HygieneReport:
    def __init__(self):
        self.p0_fails = []
        self.p1_fails = []
        self.p2_fails = []
        self.passes = []

    def record(self, level: str, check_id: str, msg: str, ok: bool):
        if ok:
            self.passes.append(check_id)
            return
        bucket = {"P0": self.p0_fails, "P1": self.p1_fails, "P2": self.p2_fails}[level]
        bucket.append(f"{check_id}: {msg}")

    def exit_code(self) -> int:
        if self.p0_fails:
            return 1
        if self.p1_fails or self.p2_fails:
            return 2
        return 0

    def render(self) -> str:
        lines = []
        if self.p0_fails:
            lines.append("P0 致命失败 (阻断 commit):")
            for f in self.p0_fails:
                lines.append(f"  [P0] {f}")
        if self.p1_fails:
            lines.append("P1 重要警告:")
            for f in self.p1_fails:
                lines.append(f"  [P1] {f}")
        if self.p2_fails:
            lines.append("P2 建议:")
            for f in self.p2_fails:
                lines.append(f"  [P2] {f}")
        lines.append(
            f"通过: {len(self.passes)} · "
            f"P0 fail: {len(self.p0_fails)} · "
            f"P1 fail: {len(self.p1_fails)} · "
            f"P2 fail: {len(self.p2_fails)}"
        )
        return "\n".join(lines)


def check_rogue_empty_files(root: Path, rep: HygieneReport):
    """H1: 项目根下无 0 字节空文件"""
    rogue = []
    for entry in root.iterdir():
        if entry.is_file() and entry.stat().st_size == 0:
            if entry.name in {".env.example", ".gitignore"}:
                continue
            rogue.append(entry.name)
    ok = not rogue
    rep.record("P0", "H1", f"项目根有 {len(rogue)} 个 0 字节空文件: {rogue[:5]}", ok)


def check_root_layout(root: Path, rep: HygieneReport):
    """H10: 项目根只含预期目录"""
    expected_dirs = {"大纲", "审查报告", "正文", "设定集", "调研笔记"}
    expected_hidden = {".webnovel", ".git"}
    expected_files = {".env.example", ".gitignore", "KNOWN_ISSUES.md"}
    actual = set(os.listdir(root))
    unexpected = actual - expected_dirs - expected_hidden - expected_files
    ok = not unexpected
    rep.record("P1", "H10", f"项目根有 {len(unexpected)} 个意外项: {sorted(unexpected)[:5]}", ok)


def check_chapter_meta_core(root: Path, chapter: int, rep: HygieneReport):
    """H2: chapter_meta 存在且 core 22 字段齐全"""
    state_p = root / ".webnovel" / "state.json"
    if not state_p.exists():
        rep.record("P0", "H2", "state.json 不存在", False)
        return
    s = json.loads(state_p.read_text(encoding="utf-8"))
    ch_key = f"{chapter:04d}"
    meta = s.get("chapter_meta", {}).get(ch_key)
    if not meta:
        rep.record("P0", "H2", f"chapter_meta[{ch_key}] 不存在", False)
        return
    missing = []
    for f in CORE_22_FIELDS:
        if f not in meta:
            missing.append(f)
            continue
        v = meta[f]
        if v is None or v == "":
            missing.append(f)
            continue
        if v == [] or v == {}:
            if f not in CORE_22_LIST_FIELDS_ALLOW_EMPTY:
                missing.append(f)
    if missing:
        rep.record(
            "P0",
            "H2",
            f"core 22 字段缺失 {len(missing)}/{len(CORE_22_FIELDS)}: {sorted(missing)[:8]}",
            False,
        )
    else:
        rep.record("P0", "H2", "core 22 字段齐全", True)


def check_score_alignment(root: Path, chapter: int, rep: HygieneReport):
    """H9: overall_score 与 checker_scores.overall 对齐"""
    state_p = root / ".webnovel" / "state.json"
    if not state_p.exists():
        return
    s = json.loads(state_p.read_text(encoding="utf-8"))
    meta = s.get("chapter_meta", {}).get(f"{chapter:04d}", {})
    state_score = meta.get("overall_score")
    cs_overall = meta.get("checker_scores", {}).get("overall")
    if state_score is None and cs_overall is None:
        return  # both missing, not applicable
    ok = state_score is not None and cs_overall is not None
    rep.record(
        "P1",
        "H9",
        f"overall_score={state_score} vs checker_scores.overall={cs_overall}",
        ok,
    )


def check_workflow_not_dangling(root: Path, rep: HygieneReport):
    """H3: workflow_state 当前 task 正常闭环或处于合法空档

    合法状态：
    - current_task is None → 流程已闭环（commit 后）
    - current_task.status != running → 已失败/暂停（需要人工介入，但不阻断 hygiene）
    - current_task.status == running AND current_step is None → 合法空档
      （通常是 Step 6 complete 后、Step 7 start 前的 commit 前闸门调用）
    非法状态：
    - current_task.status == running AND current_step != None → 某 Step 正在执行中调 hygiene
    """
    wf_p = root / ".webnovel" / "workflow_state.json"
    if not wf_p.exists():
        rep.record("P1", "H3", "workflow_state.json 不存在", True)
        return
    wf = json.loads(wf_p.read_text(encoding="utf-8"))
    t = wf.get("current_task")
    if t is None:
        rep.record("P0", "H3", "current_task == None (已正常闭环)", True)
        return
    status = t.get("status")
    current_step = t.get("current_step")
    if status != "running":
        rep.record("P0", "H3", f"current_task.status = {status} (非 running)", True)
        return
    if current_step is None:
        rep.record(
            "P0",
            "H3",
            "current_task running 但无 active step (commit 前合法空档)",
            True,
        )
        return
    rep.record(
        "P0",
        "H3",
        f"current_task running 且正在执行 {current_step.get('id')}：不应在 step 中间调 hygiene",
        False,
    )


def check_workflow_artifact_integrity(root: Path, chapter: int, rep: HygieneReport):
    """H16: workflow_state 里本章 completed_steps 的 artifact 非伪造（每步含语义字段）

    双分支逻辑：
    - 章节已 complete-task（history 里找到）→ Step 1..7 必须全齐
    - 章节仍在 current_task（commit 前闸门调用场景）→ 允许 Step 7 尚未登记
    每 step 的 artifact 都必须：非空、非纯占位、含至少一个白名单语义字段、name 不含 v2_。
    """
    wf_p = root / ".webnovel" / "workflow_state.json"
    if not wf_p.exists():
        rep.record("P0", "H16", "workflow_state.json 不存在", False)
        return
    wf = json.loads(wf_p.read_text(encoding="utf-8"))

    target = None
    in_progress = False
    for h in wf.get("history", []):
        if h.get("chapter") == chapter and h.get("command") == "webnovel-write":
            target = h
            break
    if target is None:
        ct = wf.get("current_task") or {}
        if ct.get("args", {}).get("chapter_num") == chapter and ct.get("command") == "webnovel-write":
            target = ct
            in_progress = True

    if target is None:
        rep.record(
            "P0",
            "H16",
            f"workflow_state 里找不到 ch{chapter} 的 webnovel-write 任务",
            False,
        )
        return

    completed = target.get("completed_steps", [])
    if not completed:
        rep.record("P0", "H16", f"ch{chapter} 没有 completed_steps", False)
        return

    required_map = REQUIRED_ARTIFACT_FIELDS.get("webnovel-write", {})
    fakes = []
    for step in completed:
        sid = str(step.get("id") or "")
        name = str(step.get("name") or "")
        art = step.get("artifacts") or {}
        if not isinstance(art, dict):
            fakes.append(f"{sid}: artifact 非 dict")
            continue
        if "v2_" in name or name.startswith("v2"):
            fakes.append(f"{sid}: name='{name}' 疑似伪造")
            continue
        present_keys = {k for k, v in art.items() if not _is_semantically_empty(v)}
        if not present_keys:
            fakes.append(f"{sid}: artifact 全空占位（含数字 0）")
            continue
        if present_keys.issubset(PLACEHOLDER_ONLY_FIELDS):
            fakes.append(f"{sid}: artifact 只含占位字段 {sorted(present_keys)}")
            continue
        required_fields = required_map.get(sid, [])
        if required_fields and not any(f in present_keys for f in required_fields):
            fakes.append(f"{sid}: 缺语义字段 {required_fields}")

    # Expected step set depends on mode:
    # - history entry (completed task): all 9 steps required
    # - in-progress current_task (commit-pre gate): Step 7 may be absent yet
    all_expected = {"Step 1", "Step 2A", "Step 2B", "Step 3", "Step 3.5", "Step 4", "Step 5", "Step 6", "Step 7"}
    seen = {str(s.get("id")) for s in completed}
    if in_progress and "Step 7" not in seen:
        expected = all_expected - {"Step 7"}
    else:
        expected = all_expected
    missing_steps = sorted(expected - seen)

    if fakes:
        rep.record("P0", "H16", f"ch{chapter} 有 {len(fakes)} 个伪造/空 artifact: {fakes[:3]}", False)
    elif missing_steps:
        rep.record("P0", "H16", f"ch{chapter} 缺 workflow 登记: {missing_steps}", False)
    else:
        mode_tag = "in-progress (Step 7 pending)" if in_progress else "complete"
        rep.record("P0", "H16", f"ch{chapter} workflow 登记完整（{mode_tag}）", True)


def check_chapter_text_hygiene(root: Path, chapter: int, rep: HygieneReport):
    """H4/H5/H6/H7: 正文编码 + 引号 + 行尾 + 字数一致"""
    matches = list(root.glob(f"正文/第{chapter:04d}章*.md"))
    if not matches:
        rep.record("P0", "H4", f"第{chapter}章正文文件不存在", False)
        return
    cf = matches[0]
    raw = cf.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    rep.record("P0", "H4", f"{cf.name} 含 {text.count(chr(0xFFFD))} 个 U+FFFD", text.count(chr(0xFFFD)) == 0)
    ascii_dq = text.count('"')
    rep.record("P0", "H5", f"{cf.name} 含 {ascii_dq} 个 ASCII 双引号", ascii_dq == 0)
    crlf = raw.count(b"\r\n")
    rep.record("P0", "H6", f"{cf.name} 含 {crlf} 个 CRLF 行尾", crlf == 0)
    actual_zh = len(re.findall(r"[\u4e00-\u9fff]", text))
    state_p = root / ".webnovel" / "state.json"
    if state_p.exists():
        s = json.loads(state_p.read_text(encoding="utf-8"))
        meta = s.get("chapter_meta", {}).get(f"{chapter:04d}", {})
        stored = meta.get("word_count")
        if stored:
            diff = abs(stored - actual_zh)
            ok = diff / max(1, actual_zh) < 0.02
            rep.record(
                "P1",
                "H7",
                f"word_count state={stored} vs actual={actual_zh} (diff {diff})",
                ok,
            )


def check_foreshadowing_dedup(root: Path, chapter: int, rep: HygieneReport):
    """H8: foreshadowing 字段无重复"""
    state_p = root / ".webnovel" / "state.json"
    if not state_p.exists():
        return
    s = json.loads(state_p.read_text(encoding="utf-8"))
    meta = s.get("chapter_meta", {}).get(f"{chapter:04d}", {})
    duplicates = []
    if "foreshadowing_added" in meta and "foreshadowing_planted" in meta:
        duplicates.append("added/planted 同时存在")
    if "foreshadowing_resolved" in meta and "foreshadowing_paid" in meta:
        duplicates.append("resolved/paid 同时存在")
    ok = not duplicates
    rep.record("P1", "H8", f"foreshadowing 字段重复: {duplicates}", ok)


def check_report_overall_score_count(root: Path, chapter: int, rep: HygieneReport):
    """H11: 审查报告 overall_score 出现次数 <= 1"""
    matches = list(root.glob(f"审查报告/第{chapter:04d}章审查报告.md"))
    if not matches:
        return
    t = matches[0].read_text(encoding="utf-8")
    cnt = t.count("overall_score")
    ok = cnt <= 1
    rep.record("P1", "H11", f"overall_score 在报告中出现 {cnt} 次", ok)


def check_context_snapshot(root: Path, chapter: int, rep: HygieneReport):
    """H12: context_snapshot 存在"""
    p = root / ".webnovel" / "context_snapshots" / f"ch{chapter:04d}.json"
    rep.record("P2", "H12", f"{p.name} {'存在' if p.exists() else '缺失'}", p.exists())


def check_execution_package_persistence(root: Path, chapter: int, rep: HygieneReport):
    """H14: Step 1 执行包 JSON + MD 已落盘"""
    json_p = root / ".webnovel" / "context" / f"ch{chapter:04d}_context.json"
    md_p = root / ".webnovel" / "context" / f"ch{chapter:04d}_context.md"
    json_ok = json_p.exists() and json_p.stat().st_size > 0
    md_ok = md_p.exists() and md_p.stat().st_size > 0
    if json_ok and md_ok:
        # deeper check — JSON must have 3 sections
        try:
            pkg = json.loads(json_p.read_text(encoding="utf-8"))
            missing_sections = [
                k for k in ("task_brief", "context_contract", "step_2a_write_prompt") if not pkg.get(k)
            ]
            if missing_sections:
                rep.record(
                    "P0",
                    "H14",
                    f"{json_p.name} 三个段落缺失: {missing_sections}",
                    False,
                )
                return
        except Exception as exc:
            rep.record("P0", "H14", f"{json_p.name} 解析失败: {exc}", False)
            return
        rep.record("P0", "H14", f"执行包 JSON + MD 已落盘且结构完整", True)
    else:
        missing = []
        if not json_ok:
            missing.append("JSON")
        if not md_ok:
            missing.append("MD")
        rep.record(
            "P0", "H14", f"执行包 {'+'.join(missing)} 缺失（path: .webnovel/context/ch{chapter:04d}_context.*）", False
        )


def check_polish_report_persistence(root: Path, chapter: int, rep: HygieneReport):
    """H15: Step 4 润色报告已落盘且含 anti_ai_force_check"""
    p = root / ".webnovel" / "polish_reports" / f"ch{chapter:04d}.md"
    if not p.exists():
        rep.record("P0", "H15", f".webnovel/polish_reports/ch{chapter:04d}.md 不存在", False)
        return
    text = p.read_text(encoding="utf-8")
    if not text.strip():
        rep.record("P0", "H15", f"polish_reports/ch{chapter:04d}.md 为空", False)
        return
    has_anti = "anti_ai_force_check" in text
    if not has_anti:
        rep.record("P0", "H15", f"polish_reports/ch{chapter:04d}.md 未含 anti_ai_force_check 字段", False)
        return
    # Extract value — pass/fail 可能在 anti_ai_force_check 标题/字段后任意 300 字符内
    idx = text.find("anti_ai_force_check")
    window = text[idx : idx + 400].lower()
    # Look for pass or fail as a standalone word (avoid matching "passenger" etc.)
    has_pass = bool(re.search(r"\bpass\b", window))
    has_fail = bool(re.search(r"\bfail\b", window))
    if has_fail and not has_pass:
        rep.record("P0", "H15", "anti_ai_force_check=fail，不得进入 Step 5", False)
        return
    if not has_pass:
        rep.record("P0", "H15", "anti_ai_force_check 值无法识别（须为 pass / fail）", False)
        return
    rep.record("P0", "H15", "润色报告齐全且 anti_ai_force_check=pass", True)


def check_allusions_schema(root: Path, chapter: int, rep: HygieneReport):
    """H17: allusions_used 必须 list[dict] with 7 required fields"""
    state_p = root / ".webnovel" / "state.json"
    if not state_p.exists():
        return
    s = json.loads(state_p.read_text(encoding="utf-8"))
    meta = s.get("chapter_meta", {}).get(f"{chapter:04d}", {})
    allusions = meta.get("allusions_used")
    if allusions is None:
        return  # field missing = not applicable (no allusion libraries)
    if not isinstance(allusions, list):
        rep.record("P1", "H17", f"allusions_used 不是 list（{type(allusions).__name__}）", False)
        return
    errs = []
    for i, item in enumerate(allusions):
        if not isinstance(item, dict):
            errs.append(f"[{i}] 非 dict: {type(item).__name__}")
            continue
        missing = ALLUSION_REQUIRED_KEYS - set(item.keys())
        if missing:
            errs.append(f"[{i}] 缺字段: {sorted(missing)}")
            continue
        for k in ("id", "snippet", "type", "source", "carrier", "function"):
            v = item.get(k)
            if not isinstance(v, str) or not v.strip():
                errs.append(f"[{i}].{k} 必须是非空字符串")
        if not isinstance(item.get("is_original"), bool):
            errs.append(f"[{i}].is_original 必须是 bool")
    if errs:
        rep.record("P1", "H17", f"allusions_used schema 违规 {len(errs)} 处: {errs[:3]}", False)
    else:
        rep.record("P1", "H17", f"allusions_used {len(allusions)} 条全部合规", True)


def run_project_local_checks(root: Path, chapter: int, rep: HygieneReport):
    """H13: 调用 .webnovel/hygiene_check_local.py（若存在）"""
    local_p = root / ".webnovel" / "hygiene_check_local.py"
    if not local_p.exists():
        return
    try:
        spec = importlib.util.spec_from_file_location("hygiene_local", local_p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, "run"):
            mod.run(root=root, chapter=chapter, report=rep)
    except Exception as exc:
        rep.record("P2", "H13", f"项目本地检查失败: {exc}", False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("chapter", type=int, help="章号")
    parser.add_argument("--project-root", default=None, help="项目根路径（默认：自动探测）")
    args = parser.parse_args()

    root = find_project_root(args.project_root)
    rep = HygieneReport()

    # P0 检查
    check_rogue_empty_files(root, rep)
    check_chapter_meta_core(root, args.chapter, rep)
    check_workflow_not_dangling(root, rep)
    check_workflow_artifact_integrity(root, args.chapter, rep)
    check_chapter_text_hygiene(root, args.chapter, rep)
    check_execution_package_persistence(root, args.chapter, rep)
    check_polish_report_persistence(root, args.chapter, rep)

    # P1 检查
    check_root_layout(root, rep)
    check_score_alignment(root, args.chapter, rep)
    check_foreshadowing_dedup(root, args.chapter, rep)
    check_report_overall_score_count(root, args.chapter, rep)
    check_allusions_schema(root, args.chapter, rep)

    # P2 检查
    check_context_snapshot(root, args.chapter, rep)
    run_project_local_checks(root, args.chapter, rep)

    print(rep.render())
    return rep.exit_code()


if __name__ == "__main__":
    sys.exit(main())
