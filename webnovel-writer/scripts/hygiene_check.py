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
    H19a 正文与 HEAD 不一致 + narrative_version=v1 → 必须立即跑 polish_cycle
         （Round 14.5 · <example-project> Ch1 血教训：禁止裸跑 polish commit）
  P1 重要（exit 2，不阻断但警告）：
    H7  章节字数与 state.word_count 一致（误差 < 2%）
    H8  foreshadowing 字段无重复（planted vs added、paid vs resolved）
    H9  overall_score 与 checker_scores.overall 对齐
    H10 项目根布局干净（5 个合法目录 + 允许的隐藏文件）
    H11 审查报告中 overall_score 出现次数 <= 1
    H17 chapter_meta.allusions_used schema 合规（list[dict] with 7 fields）
    H18 checker_scores key 必须 canonical（13 个 CHECKER_NAMES ∪ {overall}，
        Round 13 v2 · 含 reader-naturalness-checker + reader-critic-checker）；
        检测 AI fallback 写中文/legacy key（Ch1 血教训）
    H19 polish_log 末尾时间早于 git 最新 commit（可能历史裸跑 polish）
    H20 chapter_meta[{NNNN}].polish_log schema 合规：每条含
        {version=vN/vN.M.K, timestamp=ISO-8601, notes=非空}（Round 14.5.2）
    H22 现实常识红旗扫描（Round 17 · 2026-04-23 · 根治<example-project> Ch1-6 deep research P0）：
        7 类红旗（律所时间 / 单笔大额刷卡 / 反洗钱 / 职务作品 / 期货极值 / 学校医院 / 陈年种子）
        项目通过 .webnovel/reality_check_config.json 覆盖/扩展/exemption
    H21 跨章风格漂移监控（Round 16 · Ch6 RCA RC-1 根治）：
        - 对话占比连 2-3 章 < 0.20（低 reader-critic 风险）
        - 章末形式同型 ≥ 3 章（纯主角内心独白收尾）
        - "没 X" 句式单章 ≥ 25-30 次（签名句式过载）
        - 签名动作（印记跳/后颈凉等）单章超载
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


# Single source of truth: import the artifact whitelist + helpers from
# workflow_manager rather than mirror them here. Round 13 v2 RCA showed that
# duplicating these constants drifts the moment one file is updated — Step 3
# gained naturalness_verdict/reader_critic_score but the local copy stayed on
# the old 4-field list. See memory:feedback_hygiene_import_workflow.
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from workflow_manager import (  # noqa: E402  (sys.path must be primed first)
    REQUIRED_ARTIFACT_FIELDS,
    PLACEHOLDER_ONLY_FIELDS,
    _is_semantically_empty,
)

CORE_META_FIELDS = {
    "chapter", "title", "word_count", "summary", "hook_strength", "scene_count",
    "key_beats", "characters", "locations", "created_at", "updated_at",
    "protagonist_state", "location_current", "power_realm", "golden_finger_level",
    "time_anchor", "end_state", "foreshadowing_planted", "foreshadowing_paid",
    "strand_dominant", "review_score", "checker_scores", "allusions_used",
}
# Back-compat alias: older code referenced CORE_22_FIELDS even though the set
# actually contains 23 fields (allusions_used was added in Round 9). Keep the
# alias so any straggler import keeps working; drop after a deprecation cycle.
CORE_22_FIELDS = CORE_META_FIELDS
# Fields in CORE_META where an empty list/dict is semantically valid
# (e.g. Ch1 has 0 paid foreshadowing; a bridge chapter has 0 new allusions)
CORE_META_LIST_FIELDS_ALLOW_EMPTY = {
    "foreshadowing_planted", "foreshadowing_paid", "allusions_used",
    "key_beats", "characters", "locations", "checker_scores",
}
CORE_22_LIST_FIELDS_ALLOW_EMPTY = CORE_META_LIST_FIELDS_ALLOW_EMPTY

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
        # Round 20.x · Ch13 P0 根治（Bug 4）：exit_code 与 P0/P1/P2 fail count 严格对齐 + 显式标识
        # 防止"P0 fail: 0 但 exit!=0"的误导用户场景。
        rc = self.exit_code()
        rc_label = {0: "通过", 1: "P0 阻断 commit", 2: "P1/P2 警告（不阻断）"}.get(rc, "未知")
        lines.append(f"最终 exit_code = {rc} ({rc_label})")
        return "\n".join(lines)


def check_rogue_empty_files(root: Path, rep: HygieneReport):
    """H1: 项目根下无 0 字节空文件

    Round 15.3 · 2026-04-23 · Ch6 RCA Bug #2 根治：
    - audit-agent 或主流程 bash 命令偶尔会把变量展开成中文字符串或 markdown 内容，
      被 shell redirect parser 误解析成文件名（例：`echo "..." > 上章决议：**approve**` 会创建 0 字节文件）
    - 这类文件特征：名字含 `=` / `**` / markdown 符号 / 单汉字 / 可执行符（`<` `>` `|`）
    - H1 检测到且文件名匹配 accident pattern 时自动清除，记 observability/bash_accident_cleanup.jsonl
    - 其他 0 字节文件仍按 P0 fail 处理（可能是用户真实创建）
    """
    # 可允许的 0 字节文件白名单
    allowlist = {".env.example", ".gitignore"}
    # bash redirect accident 特征
    accident_patterns = [
        re.compile(r"^=$"),  # 单个 =
        re.compile(r"\*\*"),  # 含 markdown bold
        re.compile(r"^[一-鿿]{1,3}$"),  # 纯 1-3 个汉字（如 "供" "由" "上章决议"）
        re.compile(r"[<>|]"),  # 含 shell redirect 符
        re.compile(r"^[:：]"),  # 以冒号开头（markdown 引用残片）
        re.compile(r"^-{2,}$"),  # --- 分隔线被当文件名
    ]
    def _is_accident(name: str) -> bool:
        return any(p.search(name) for p in accident_patterns)

    rogue = []
    cleaned = []
    for entry in root.iterdir():
        if entry.is_file() and entry.stat().st_size == 0:
            if entry.name in allowlist:
                continue
            if _is_accident(entry.name):
                # 自动清除 + observability 记录
                try:
                    entry.unlink()
                    cleaned.append(entry.name)
                except Exception:
                    # unlink 失败仍记为 rogue
                    rogue.append(entry.name)
            else:
                rogue.append(entry.name)

    # 记 observability（best-effort · 不阻断 H1）
    if cleaned:
        try:
            import json as _j
            from datetime import datetime, timezone
            obs_dir = root / ".webnovel" / "observability"
            obs_dir.mkdir(parents=True, exist_ok=True)
            log_f = obs_dir / "bash_accident_cleanup.jsonl"
            entry_record = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "cleaned": cleaned,
                "source": "hygiene_check_H1_auto_cleanup",
                "note": "Round 15.3 · Ch6 RCA · 自动识别 bash redirection accident 0 字节文件并清除",
            }
            with log_f.open("a", encoding="utf-8") as _fh:
                _fh.write(_j.dumps(entry_record, ensure_ascii=False) + "\n")
            print(f"  🔧 [H1 auto-clean] 清除 {len(cleaned)} 个 bash accident 0 字节文件: {cleaned[:5]}")
        except Exception:
            pass

    ok = not rogue
    rep.record("P0", "H1", f"项目根有 {len(rogue)} 个未识别 0 字节空文件: {rogue[:5]}", ok)


def check_root_layout(root: Path, rep: HygieneReport):
    """H10: 项目根只含预期目录

    白名单 = plugin 默认（dirs + hidden + files）
            + 项目可选 .webnovel/hygiene_config.json 的 extra_allowed_root_items
    """
    expected_dirs = {"大纲", "审查报告", "正文", "设定集", "调研笔记"}
    expected_hidden = {".webnovel", ".git", ".gitattributes"}
    expected_files = {
        ".env.example",
        ".gitignore",
        "KNOWN_ISSUES.md",
        "README.md",
        "ROOT_CAUSE_GUARD_RAILS.md",
        "CHANGELOG.md",
        "LICENSE",
        # Round 17.1 · 2026-04-24 · Ch7 RCA P2.6：项目北极星文件
        "CLAUDE.md",
    }
    # 项目特化扩展白名单（Round 15.1 · 2026-04-22）
    cfg_path = root / ".webnovel" / "hygiene_config.json"
    extra = set()
    if cfg_path.exists():
        try:
            import json as _j

            extra = set(
                _j.loads(cfg_path.read_text(encoding="utf-8")).get(
                    "extra_allowed_root_items", []
                )
            )
        except Exception:
            pass
    actual = set(os.listdir(root))
    unexpected = (
        actual - expected_dirs - expected_hidden - expected_files - extra
    )
    ok = not unexpected
    rep.record(
        "P1", "H10", f"项目根有 {len(unexpected)} 个意外项: {sorted(unexpected)[:5]}", ok
    )


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
    for f in CORE_META_FIELDS:
        if f not in meta:
            missing.append(f)
            continue
        v = meta[f]
        if v is None or v == "":
            missing.append(f)
            continue
        if v == [] or v == {}:
            if f not in CORE_META_LIST_FIELDS_ALLOW_EMPTY:
                missing.append(f)
    total = len(CORE_META_FIELDS)
    if missing:
        rep.record(
            "P0",
            "H2",
            f"core {total} 字段缺失 {len(missing)}/{total}: {sorted(missing)[:8]}",
            False,
        )
    else:
        rep.record("P0", "H2", f"core {total} 字段齐全", True)


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
    # Round 18.2 · 2026-04-25 · Ch11 RCA #3 双兜底
    # 主流程是先 hygiene → 再 start-step Step 7（SKILL 修订后明确）。
    # 但若 AI 偶尔顺序错（先 start-step Step 7 再 hygiene），允许 Step 7 active 时
    # 调 hygiene（commit 前再确认一次合理）。其他 Step active 仍 P0 fail。
    cur_step_id = (current_step.get("id") or "").strip()
    if cur_step_id == "Step 7":
        rep.record(
            "P0",
            "H3",
            "current_task running + Step 7 active：commit 前 hygiene 双兜底（合法）",
            True,
        )
        return
    rep.record(
        "P0",
        "H3",
        f"current_task running 且正在执行 {cur_step_id}：不应在 step 中间调 hygiene",
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
    """H11: 审查报告 overall_score **key-value 形式** 出现次数 <= 1

    Round 15.3 · 2026-04-23 · Ch6 RCA Bug #6 根治：
    - 旧实现用 `t.count("overall_score")` 会把表头列名 / 描述性文字 / 命令示例全算上
    - Ch6 报告里表格列名 `| 模型 | provider | routing | overall_score |` + 正文 `overall_score = 85`
      误报 "2 次 > 1" P1 fail
    - 新实现：只匹配真正的 key-value 形式（`overall_score: N` / `overall_score = N` / `"overall_score": N`）
    - 这类形式才代表"作者真在声明一个分数值"，列名/描述文字不算
    """
    matches = list(root.glob(f"审查报告/第{chapter:04d}章审查报告.md"))
    if not matches:
        return
    t = matches[0].read_text(encoding="utf-8")
    # key-value 形式：overall_score 后紧跟 `:` 或 `=`（忽略引号/反引号/星号等 markdown 修饰）
    # 覆盖：`overall_score: 85` / `overall_score = round(...) = 85` / `"overall_score": 85` / `**overall_score**: 85`
    # 不覆盖（正确 reject）：表头列名 `| overall_score |` / 描述性 `overall_score 通过加权计算`
    kv_pattern = re.compile(r'overall_score\s*["\*`]*\s*[:=]', re.IGNORECASE)
    cnt = len(kv_pattern.findall(t))
    ok = cnt <= 1
    rep.record("P1", "H11", f"overall_score key-value 在报告中出现 {cnt} 次", ok)


def check_context_snapshot(root: Path, chapter: int, rep: HygieneReport):
    """H12: context_snapshot 存在"""
    p = root / ".webnovel" / "context_snapshots" / f"ch{chapter:04d}.json"
    rep.record("P2", "H12", f"{p.name} {'存在' if p.exists() else '缺失'}", p.exists())


def check_execution_package_persistence(root: Path, chapter: int, rep: HygieneReport):
    """H14: Step 1 执行包 JSON + MD 已落盘

    兼容字段名漂移：context-agent 如果绕过 build_execution_package.py 直写 JSON，
    可能把 step_2a_write_prompt 写成 step2a_direct_prompt / step2a_write_prompt。
    为防止 commit 阻塞，此处接受已知 alias，但会记录 P1 警告提示字段名不规范。
    治本仍是 context-agent.md Step 7 的"禁止绕过助手脚本"硬规则。
    """
    json_p = root / ".webnovel" / "context" / f"ch{chapter:04d}_context.json"
    md_p = root / ".webnovel" / "context" / f"ch{chapter:04d}_context.md"
    json_ok = json_p.exists() and json_p.stat().st_size > 0
    md_ok = md_p.exists() and md_p.stat().st_size > 0
    STEP2A_ALIASES = ("step_2a_write_prompt", "step2a_direct_prompt", "step2a_write_prompt")
    if json_ok and md_ok:
        try:
            pkg = json.loads(json_p.read_text(encoding="utf-8"))
            missing_sections: list = []
            if not pkg.get("task_brief"):
                missing_sections.append("task_brief")
            if not pkg.get("context_contract"):
                missing_sections.append("context_contract")
            step2a_key_found = next((k for k in STEP2A_ALIASES if pkg.get(k)), None)
            if step2a_key_found is None:
                missing_sections.append("step_2a_write_prompt")
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
        if step2a_key_found != "step_2a_write_prompt":
            rep.record(
                "P1",
                "H14-alias",
                f"{json_p.name} 使用非规范字段名 '{step2a_key_found}' 替代 'step_2a_write_prompt'"
                f"（context-agent 可能绕过了 build_execution_package.py）",
                False,
            )
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


def check_checker_scores_canonical(root: Path, chapter: int, rep: HygieneReport):
    """H18: checker_scores key 必须 canonical

    规则：
    - 合法 key = 11 CHECKER_NAMES ∪ {"overall"}
    - 支持通过 CHECKER_ALIASES 映射的中文/legacy 别名（映射后等价于 canonical）
    - 非法 key（Anti-AI/钩子强度/伏笔埋设 等 AI 手写常见 fallback）→ P1 fail

    根因：AI 受 data-agent.md 历史示例 `{"设定一致性": 82}` 诱导写中文 key，
    而 chapter_audit 只认英文 canonical，导致 silent mismatch（Ch1 血教训）。
    """
    state_p = root / ".webnovel" / "state.json"
    if not state_p.exists():
        return
    s = json.loads(state_p.read_text(encoding="utf-8"))
    meta = s.get("chapter_meta", {}).get(f"{chapter:04d}", {})
    cs = meta.get("checker_scores")
    if not isinstance(cs, dict) or not cs:
        return  # H2 will cover missing case
    # 延迟 import 防循环依赖（hygiene_check 是独立脚本）
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from data_modules.chapter_audit import normalize_checker_scores_keys
    except Exception as exc:
        rep.record("P1", "H18", f"无法加载 normalize_checker_scores_keys: {exc}", False)
        return
    _norm, renamed, invalid = normalize_checker_scores_keys(cs)
    if invalid:
        rep.record(
            "P1",
            "H18",
            f"checker_scores 含非 canonical key {len(invalid)} 个: {invalid[:5]}（修：改成 CHECKER_NAMES 英文 key）",
            False,
        )
    elif renamed:
        rep.record(
            "P1",
            "H18",
            f"checker_scores 用中文别名 {len(renamed)} 项（audit 会 normalize，但建议写 canonical 英文）：{renamed[:5]}",
            True,
        )
    else:
        rep.record("P1", "H18", f"checker_scores {len(cs)} 个 key 全部 canonical", True)


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


def check_post_commit_polish_drift(root: Path, chapter: int, rep: HygieneReport):
    """H19: post-commit polish 漂移检测（2026-04-20 Round 14.5 新增）

    背景：Step 7 commit 之后，作者/AI 经常根据读者视角 checker 反馈手动改正文然后
    裸跑 `git commit -m "polish"`。这绕过了 post_draft_check / hygiene_check / state
    同步 / workflow 登记。本检查在 commit 前发现这种"未走 polish_cycle"的迹象。

    检测策略：
    - 读 git show HEAD:正文/第NNNN章*.md → 与工作区文件 hash 比对
    - 若 hash 不一致（=正文已改动但未 commit）→ 检查是否需要走 polish_cycle：
        H19a (P0): 仍是 v1（从未走过 polish_cycle）→ 必须立即跑
        H19  (P1): chapter_meta.polish_log 末尾时间 < git log 最新 commit 时间 →
                   可能存在历史裸跑 polish commit
    - 若 hash 一致 → skip（无 drift）
    - 若 git show HEAD 失败（文件未跟踪）→ skip（首次 commit 走 Step 1-7）
    """
    import subprocess
    chapter_files = sorted((root / "正文").glob(f"第{chapter:04d}章*.md"))
    if not chapter_files:
        return
    chapter_file = chapter_files[0]
    rel = str(chapter_file.relative_to(root)).replace("\\", "/")

    try:
        out = subprocess.run(
            ["git", "show", f"HEAD:{rel}"],
            cwd=root,
            capture_output=True,
            timeout=10,
        )
    except Exception as exc:
        rep.record("P2", "H19", f"git show HEAD 调用失败: {exc}", True)
        return
    if out.returncode != 0:
        return

    head_text = out.stdout.decode("utf-8", errors="replace")
    cur_text = chapter_file.read_text(encoding="utf-8")
    if head_text == cur_text:
        rep.record("P2", "H19", "正文与 HEAD 一致（无 polish drift）", True)
        return

    state_p = root / ".webnovel" / "state.json"
    if not state_p.exists():
        rep.record("P0", "H19a", "state.json 缺失，无法判断 polish 状态", False)
        return

    try:
        s = json.loads(state_p.read_text(encoding="utf-8"))
    except Exception as exc:
        rep.record("P0", "H19a", f"state.json 解析失败: {exc}", False)
        return

    meta = s.get("chapter_meta", {}).get(f"{chapter:04d}", {})
    narrative_version = meta.get("narrative_version")
    polish_log = meta.get("polish_log", [])

    if not narrative_version or narrative_version == "v1":
        rep.record(
            "P0", "H19a",
            f"正文已改动但 narrative_version={narrative_version!r}（从未走 polish_cycle）。"
            f"必须运行：python scripts/polish_cycle.py {chapter} --reason '...' --narrative-version-bump",
            False,
        )
        return

    try:
        log_out = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", rel],
            cwd=root,
            capture_output=True,
            timeout=10,
        )
        last_commit_iso = log_out.stdout.decode("utf-8", errors="replace").strip()
    except Exception:
        last_commit_iso = ""

    last_polish_iso = ""
    if polish_log:
        last_polish_iso = polish_log[-1].get("timestamp", "")

    if last_commit_iso and last_polish_iso and last_polish_iso < last_commit_iso:
        rep.record(
            "P1", "H19",
            f"polish_log 末尾时间 ({last_polish_iso}) 早于 git 最新 commit ({last_commit_iso})。"
            f"可能存在裸跑 polish commit。建议：补登一次 polish_cycle --allow-no-change --no-commit",
            False,
        )
        return

    rep.record(
        "P1", "H19",
        f"正文已改动且未 commit；narrative_version={narrative_version}，建议走 polish_cycle 提交",
        False,
    )


def check_audit_post_polish_drift(root: Path, chapter: int, rep: HygieneReport):
    """H24: Step 6 audit 后到 Step 7 commit 前的正文漂移检测（Round 17.3 · 2026-04-24）

    背景（Ch8 血教训）：
    Step 6 audit-agent 写完 audit_reports/ch{N}.json 后，audit 结论基于那个时间点的正文。
    如果作者/AI 在 Step 7 commit 前对正文做了 hygiene 修复（如为过 H21 把"没X"批量改）
    或手动微调，audit 结论就与 commit 的正文脱节。Ch8 Round 17.2 就遇到：
      - audit_reports/ch0008.json mtime: 2026-04-24T07:33:00Z
      - 正文 mtime: 2026-04-24T08:04:20Z
      - 漂移 1869s，正文比 audit 晚 31 分钟
    Step 5 的 checker_scores 反映 2750 字稿，但 commit 的是 hygiene 后 2791 字稿。

    检测策略（commit 前触发，非破坏性）：
      - P2 info: 正文 mtime > audit mtime + 5s → audit 后有修改
      - P1 warn: 正文 mtime > audit mtime + 300s → 建议 polish_cycle 补录或重跑 Step 6
      - 不 block，只记 warn（polish_cycle 是根治路径）

    免单场景：
      - audit_reports 不存在 → skip（Step 6 未跑 · 由其他检查覆盖）
      - 正文 mtime < audit mtime → OK
    """
    chapter_padded = f"{chapter:04d}"
    audit_p = root / ".webnovel" / "audit_reports" / f"ch{chapter_padded}.json"
    if not audit_p.exists():
        return
    chapter_files = sorted((root / "正文").glob(f"第{chapter_padded}章*.md"))
    if not chapter_files:
        return
    chapter_file = chapter_files[0]
    try:
        file_m = chapter_file.stat().st_mtime
        audit_m = audit_p.stat().st_mtime
    except Exception:
        return
    drift_s = file_m - audit_m
    if drift_s <= 5:
        rep.record("P2", "H24", f"audit-后 drift OK（正文 mtime 比 audit 早/近 {drift_s:.0f}s）", True)
        return

    # Round 17.3 · Ch8 P1 根治：polish_cycle 合法路径豁免
    # 查该章节文件的最新 git log commit（不是全仓 HEAD · 避免被其他章 polish 覆盖误判）
    # 若那个 commit message 含 `[polish:]` 或 `第N章 v` → 说明是 polish_cycle 合法重提
    # 这种情况 drift 是设计预期（polish_cycle 已经跑过 post_draft_check + hygiene），
    # 不应报 P1 干扰 commit 流程，降级为 P2 info。
    import subprocess
    rel = str(chapter_file.relative_to(root)).replace("\\", "/")
    try:
        last_msg = subprocess.run(
            ["git", "log", "-1", "--pretty=%s", "--", rel],
            cwd=root, capture_output=True, timeout=5,
        ).stdout.decode("utf-8", errors="replace").strip()
    except Exception:
        last_msg = ""
    is_polish_cycle_commit = (
        "[polish:" in last_msg
        or f"第{chapter}章 v" in last_msg  # polish_cycle message 格式: 第N章 v{X}: ...
        or f"第{chapter:04d}章 v" in last_msg
    )
    if is_polish_cycle_commit:
        rep.record(
            "P2", "H24",
            f"audit-后 drift {drift_s:.0f}s · HEAD 是 polish_cycle 合法重提（{last_msg[:60]}）· 豁免",
            True,
        )
        return

    if drift_s <= 300:
        rep.record(
            "P2", "H24",
            f"audit-后 drift 小（正文比 audit 晚 {drift_s:.0f}s · 可能是 hygiene 阶段同步修改）",
            True,
        )
        return
    # drift > 300s 且非 polish_cycle commit：正文在 audit 后显著修改未合法提交
    rep.record(
        "P1", "H24",
        f"audit-后 drift 显著（正文 mtime 晚于 audit {drift_s:.0f}s ≈ {drift_s/60:.1f}min）· "
        f"Step 5 checker_scores 与 audit 结论可能反映旧稿 · "
        f"建议：若仅措辞替换→polish_cycle 补录；若新增内容→重跑 Step 5/6",
        False,
    )


def check_polish_log_schema(root: Path, chapter: int, rep: HygieneReport):
    """H20: chapter_meta[{NNNN}].polish_log schema 合规（Round 14.5.2）。

    每条 polish_log 条目必须含 version / timestamp / notes 三个必填字段，
    且 version 匹配 ``vN`` 或 ``vN.M.K`` 形式，timestamp 为 ISO-8601。
    违规会让 context-agent 解析上章 polish 经验时失败（跨章传递断层）。
    """
    state_p = root / ".webnovel" / "state.json"
    if not state_p.exists():
        return
    try:
        s = json.loads(state_p.read_text(encoding="utf-8"))
    except Exception:
        return
    meta = s.get("chapter_meta", {}).get(f"{chapter:04d}", {})
    polish_log = meta.get("polish_log")
    if polish_log is None:
        rep.record("P1", "H20", "polish_log 字段缺失（非必需，首稿未 polish 时允许缺）", True)
        return
    if not isinstance(polish_log, list):
        # Round 18 · 2026-04-24 · Ch10 P1-9 根治：dict→list auto-fix
        # 旧逻辑：dict 直接 P1 fail，要求人工转
        # 新逻辑：自动包装成 list[dict]，注入 version/timestamp/notes 兜底字段
        # 减少跨章传递断层（context-agent 解析失败）
        if isinstance(polish_log, dict):
            from datetime import datetime as _dt, timezone as _tz
            wrapped = {
                "version": polish_log.get("version", "v1"),
                "timestamp": polish_log.get(
                    "timestamp", _dt.now(_tz.utc).isoformat()
                ),
                "notes": polish_log.get("notes")
                    or f"auto-wrapped from dict (H20 fix · Round 18) · "
                       f"原 dict 字段：{', '.join(polish_log.keys())}",
                **polish_log,
            }
            try:
                s["chapter_meta"][f"{chapter:04d}"]["polish_log"] = [wrapped]
                state_p.write_text(
                    json.dumps(s, ensure_ascii=False, indent=2),
                    encoding="utf-8", newline="\n",
                )
                rep.record(
                    "P1", "H20",
                    f"polish_log dict→list auto-fix 已应用（Round 18 P1-9）",
                    True,
                )
                return
            except Exception as _ex:
                rep.record("P1", "H20", f"polish_log dict→list auto-fix 失败: {_ex}", False)
                return
        rep.record("P1", "H20", f"polish_log 不是 list（{type(polish_log).__name__}）", False)
        return
    if not polish_log:
        rep.record("P1", "H20", "polish_log 存在但为空数组", True)
        return

    required = {"version", "timestamp", "notes"}
    version_re = re.compile(r"^v\d+(\.\d+){0,3}$")
    errs: list[str] = []
    for i, entry in enumerate(polish_log):
        if not isinstance(entry, dict):
            errs.append(f"[{i}] 非 dict")
            continue
        missing = required - set(entry.keys())
        if missing:
            errs.append(f"[{i}] 缺字段 {sorted(missing)}")
            continue
        v = entry.get("version", "")
        if not isinstance(v, str) or not version_re.match(v):
            errs.append(f"[{i}] version={v!r} 不合规（应形如 v2/v3.8.1）")
        t = entry.get("timestamp", "")
        if not isinstance(t, str) or "T" not in t:
            errs.append(f"[{i}] timestamp={t!r} 非 ISO-8601")
        n = entry.get("notes", "")
        if not isinstance(n, str) or not n.strip():
            errs.append(f"[{i}] notes 为空或非字符串")

    if errs:
        rep.record("P1", "H20", f"polish_log schema 违规 {len(errs)} 处: {errs[:3]}", False)
    else:
        rep.record("P1", "H20", f"polish_log {len(polish_log)} 条全部合规", True)


def check_cross_chapter_style_drift(root: Path, chapter: int, rep: HygieneReport):
    """H21: 跨章风格漂移监控（2026-04-23 Round 16 · Ch6 RCA 根治 RC-1 作者风格克制漂移）

    监控 4 条红线（Ch6 血教训：reader-critic 连 4 章 58-71 低位的根因）：
      1. 对话占比：连续 2 章 < 0.20 → warn；连续 3 章 → P1 fail
      2. 章末形式同型 ≥ 3 章（如连续"心里默念 N 字"）→ P1 fail
      3. "没 X" 句式单章 > 25 次 → warn；> 30 次 → P1 fail
      4. 印记跳/后颈凉等签名动作单章超载（印记跳 > 5 / 后颈凉 > 3 · 项目可配）→ warn

    数据源：
      - 正文/第{NNNN}章*.md（当前章 + 上 2 章）
      - state.chapter_meta[NNNN].checker_scores（对话占比可能在 dialogue score 里）
      - 可选项目配置：.webnovel/style_drift_config.json 覆盖默认阈值 / 签名动作清单

    设计目标：此检查只 P1 warn · 不 P0 阻断 commit · 作为"章末决策前的跨章信号"
    """
    cfg_path = root / ".webnovel" / "style_drift_config.json"
    cfg = {}
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    # 可配置参数
    dialogue_min = float(cfg.get("dialogue_ratio_min", 0.20))
    # Round 17.2 · Ch8 P0-R5 根治（2026-04-24）：阈值收紧
    # Ch8 polish 后"没X" 34 次漏抓（旧阈值 warn 25/fail 30 太宽），
    # editor_notes 一直建议 ≤15，代码闸门未对齐。现在 warn 15 / fail 20。
    # post_draft_check section 11 同步 SIGNATURE_DENSITY 签名密度硬线。
    no_x_warn = int(cfg.get("no_x_warn_threshold", 15))
    no_x_fail = int(cfg.get("no_x_fail_threshold", 20))
    signature_actions = cfg.get("signature_actions", {
        # 项目默认 · 可被 .webnovel/style_drift_config.json 覆盖
        "印记跳": 5,
        "后颈凉": 3,
    })
    chapter_end_dedup_min = int(cfg.get("chapter_end_dedup_min", 3))

    # 加载当前 + 上 2 章正文
    def _load_chapter_text(ch):
        files = list((root / "正文").glob(f"第{ch:04d}章*.md")) if (root / "正文").exists() else []
        if not files:
            return None
        try:
            return files[0].read_text(encoding="utf-8")
        except Exception:
            return None

    cur_text = _load_chapter_text(chapter)
    if cur_text is None:
        rep.record("P2", "H21", "正文文件缺失，跳过风格漂移检测", True)
        return

    # 1. 对话占比（粗估：U+201C/U+201D 对包裹的字数 / 总字数）
    def _dialogue_ratio(text: str) -> float:
        if not text:
            return 0.0
        # 匹配弯引号配对（允许跨行）
        pairs = re.findall(r"\u201c([^\u201c\u201d]*)\u201d", text, flags=re.DOTALL)
        dialogue_chars = sum(len(re.findall(r"[\u4e00-\u9fff]", p)) for p in pairs)
        total_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
        return dialogue_chars / total_chars if total_chars > 0 else 0.0

    cur_ratio = _dialogue_ratio(cur_text)
    prev1_text = _load_chapter_text(chapter - 1) if chapter >= 2 else None
    prev2_text = _load_chapter_text(chapter - 2) if chapter >= 3 else None
    prev1_ratio = _dialogue_ratio(prev1_text) if prev1_text else None
    prev2_ratio = _dialogue_ratio(prev2_text) if prev2_text else None

    # Round 17.1 · 2026-04-24 · Ch7 RCA P0.2：浮点容差
    # 根因：Ch7 对话占比 = 0.200 但 `r < 0.20` 浮点比较仍判 True（float 精度问题）
    # 修法：留 2.5% 容差（与 post_draft_check DIALOGUE_RATIO 一致）
    dialogue_min_effective = dialogue_min - 0.005

    # Round 20.6 · 2026-04-26 · 读 post_draft_config.json 的 dialogue_ratio_override_chapters
    # Root cause：H21 一直无视 post_draft_config 的 override（Ch2/Ch3 已豁免），
    # 导致项目级豁免章节仍报 P1 假阳。post_draft_check.py 已读，hygiene 没读 → 漂移。
    # 根治：豁免章不计入连续低对话占比 streak
    override_chapters: set[int] = set()
    config_p = root / ".webnovel" / "post_draft_config.json"
    if config_p.exists():
        try:
            cfg = json.loads(config_p.read_text(encoding="utf-8"))
            override_chapters = set(int(c) for c in cfg.get("dialogue_ratio_override_chapters", []) or [])
        except Exception:
            override_chapters = set()

    low_streak = 0
    skipped_overrides: list[int] = []
    for offset, r in enumerate([cur_ratio, prev1_ratio, prev2_ratio]):
        if r is None:
            break
        ch_idx = chapter - offset
        if ch_idx in override_chapters:
            skipped_overrides.append(ch_idx)
            continue  # 豁免章不打断也不计数
        if r < dialogue_min_effective:
            low_streak += 1
        else:
            break

    if low_streak >= 3:
        rep.record("P1", "H21",
                   f"对话占比连 3 章 < {dialogue_min}（Ch{chapter}={cur_ratio:.3f} / "
                   f"Ch{chapter-1}={prev1_ratio:.3f} / Ch{chapter-2}={prev2_ratio:.3f}）· "
                   f"读者 reader-critic 低位风险"
                   + (f" · override skipped {sorted(skipped_overrides)}" if skipped_overrides else ""), False)
    elif low_streak == 2:
        rep.record("P2", "H21",
                   f"对话占比连 2 章 < {dialogue_min}（Ch{chapter}={cur_ratio:.3f} / "
                   f"Ch{chapter-1}={prev1_ratio:.3f}）· warn", True)
    else:
        rep.record("P1", "H21_dialogue", f"对话占比 {cur_ratio:.3f} OK（≥ {dialogue_min} 或非连续低）", True)

    # 2. 章末形式同型检测（粗启发式：末段 150 字内是否纯主角内心独白）
    def _is_inner_monologue_end(text: str) -> bool:
        if not text:
            return False
        # 取最后 200 中文字符
        cjk = re.findall(r"[\u4e00-\u9fff]", text)
        if len(cjk) < 50:
            return False
        tail = text[-1500:] if len(text) >= 1500 else text
        # 启发：末尾无弯引号 + 出现"心里/默念/在心里/想/他想"等内省标记
        has_dialogue = "\u201c" in tail
        inner_markers = any(m in tail for m in ["心里", "默念", "他想", "在心底", "脑子里"])
        return (not has_dialogue) and inner_markers

    ends_inner = [
        _is_inner_monologue_end(t) for t in [cur_text, prev1_text, prev2_text] if t is not None
    ]
    if len(ends_inner) >= chapter_end_dedup_min and all(ends_inner[:chapter_end_dedup_min]):
        rep.record("P1", "H21_chapter_end",
                   f"章末形式同型连 {chapter_end_dedup_min} 章（纯主角内心独白收尾）· "
                   f"reader-pull SOFT_PATTERN_REPEAT 风险 · 建议 Ch{chapter+1} 换"
                   "四选一形式（行动定格/外部对话/外部景象/伏笔物件特写）", False)
    else:
        rep.record("P1", "H21_chapter_end", "章末形式无同型累积", True)

    # 3. "没 X" 句式密度
    no_x_matches = re.findall(r"没[一-鿿]{1,3}", cur_text or "")
    no_x_count = len(no_x_matches)
    if no_x_count >= no_x_fail:
        rep.record("P1", "H21_no_x",
                   f"'没X' 句式 {no_x_count} 次（≥ {no_x_fail} 硬线）· 签名句式过载 · 建议降到 15-20 区间", False)
    elif no_x_count >= no_x_warn:
        rep.record("P2", "H21_no_x",
                   f"'没X' 句式 {no_x_count} 次（>= {no_x_warn} warn 阈值）· 建议降到 15-20", True)
    else:
        rep.record("P1", "H21_no_x", f"'没X' 句式 {no_x_count} 次 OK", True)

    # 4. 签名动作超载（可配置）
    overload = []
    for action, max_n in signature_actions.items():
        n = (cur_text or "").count(action)
        if n > max_n:
            overload.append(f"{action}×{n}>{max_n}")
    if overload:
        rep.record("P2", "H21_signature",
                   f"签名动作超载: {', '.join(overload)}（载体差异化不足）", True)
    else:
        rep.record("P1", "H21_signature", "签名动作密度 OK", True)


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


# H22 现实常识红旗扫描（2026-04-23 Round 17 · 根治<example-project> Ch1-6 deep research P0 常识硬伤）
# 默认规则包：律所时间 / 大额刷卡 / 职务作品 / 反洗钱 / 期货收益极值
# 项目可通过 .webnovel/reality_check_config.json 覆盖/扩展
DEFAULT_REALITY_RULES = [
    {
        "id": "law_firm_hours",
        "domain": "律所/法院",
        "pattern": r"(早上|上午|凌晨)?\s*(六点|七点|6:\d{2}|7:\d{2}|6点\d{0,2}|7点\d{0,2})[^。]{0,20}(律所|律师事务所|法院)",
        "severity": "P1",
        "message": "律所/法院 ≤ 7:30 营业不合理（国内律所标准 9:00，个别 8:30）。合理化：改为 9:00+/'昨晚预约今早上门'，或加一行说明（'合伙人本人 7 点到所'）",
    },
    {
        "id": "single_swipe_large",
        "domain": "银行/刷卡",
        "pattern": r"(单笔|一笔|一次)?[^。]{0,10}(刷卡|划卡|划卡|POS|pos)[^。]{0,15}(五十万|50 ?万|一百万|100 ?万|八十万|80 ?万)",
        "severity": "P1",
        "message": "国内单笔刷卡限额一般 ≤ 5 万（少数银行 5-20 万）。合理化：改'分 N 笔转账' / 网银大额转账 / 柜面支票，并加一行合规性说明",
    },
    {
        "id": "anti_money_laundering",
        "domain": "反洗钱",
        "pattern": r"(刷卡|转账|支付|打卡|现金).{0,20}(五十万|50 ?万|一百万|100 ?万|二百万|200 ?万|三百万|300 ?万)",
        "severity": "P2",
        "message": "单日现金/转账 ≥ 5 万现金或 ≥ 20 万对公/10 万对私会触发央行反洗钱监测。合理化：'分 N 天打' / '提前跟银行经理托过关系' / 走对公账户",
    },
    {
        "id": "work_product_copyright",
        "domain": "职务作品",
        "pattern": r"(职务|公司项目|公司内部).{0,30}(版权|著作权)[^。]{0,15}(归个人|归我|权利人是(我|本人|个人)|登记.{0,5}(我|本人))",
        "severity": "P1",
        "message": "著作权法第 18 条：职务作品著作权归公司。合理化：'入职时特批私活协议' / '独立于工作时间开发'（必须写进正文情节）",
    },
    {
        "id": "futures_extreme_yield",
        "domain": "期货/股市",
        "pattern": r"(期货|股市|股票)[^。]{0,30}(十倍|百倍|十四倍|100%|1000%|三百四十七|347 ?万|五百万|500 ?万).{0,30}(一天|当日|单日|一夜)",
        "severity": "P2",
        "message": "单日 10 倍以上收益仅在极端锁板/杠杆+涨停连击下可能。合理化：'他知道这是史上极少几次的连续涨停锁板' / 改小倍数（3-8 倍更稳）",
    },
    {
        "id": "hospital_school_hours",
        "domain": "学校/医院",
        "pattern": r"(周六|周日|周末|法定节假日)[^。]{0,15}(教务处|财务处|学生处|助学金|教务|工商局|社保局).{0,10}办",
        "severity": "P2",
        "message": "行政机关/学校周末一般不办公。合理化：改到周一至周五，或加一行说明",
    },
    {
        "id": "fresh_germination_ancient_seed",
        "domain": "种子存活",
        "pattern": r"(十五年|20 ?年|二十年|30 ?年|三十年)[^。]{0,15}(种子|麦种|谷种).{0,15}(发芽|出苗|长出)",
        "severity": "P2",
        "message": "普通麦种保存 15+ 年后发芽率极低。合理化：'生石灰封装 / 低温干燥 / 灵泉激活' 必须在正文情节出现",
    },
]


def check_cross_chapter_cadence(root: Path, chapter: int, rep: HygieneReport):
    """H23: 跨章主线角色锚点纪律（Round 17.1 · 2026-04-24 · Ch7 RCA P1.5 根治）

    为什么需要（Ch7 血教训）：
    - Ch3-6 连 4 章不提妹妹<sister-character> · Ch2-6 连 5 章深灰夹克男悬空
    - 全靠 editor_notes/chN_prep.md 的软约束 + continuity-checker 抽查
    - Round 17 editor_notes 才补回约束 XI-XV，但下次遗漏风险仍在
    - 读者头号弃书抱怨之一："作者忘了某角色" / "情感线断层"

    怎么工作：
    1. 读 .webnovel/context/chNNNN_context.json 的 main_character_cadence.cadence_table
       （context-agent 已生成，Ch7 起每章都有）
    2. 对每个角色按 every_n_chapters 判断本章是否该命中
    3. 扫描本章正文是否含角色名（或别名/转述关键词）
    4. 该命中未命中 → P1 fail · 未到期 → skip

    配置豁免：
    .webnovel/hygiene_config.json.character_cadence_exemptions = [chapter_numbers]
    """
    import json as _j

    ctx_path = (
        root / ".webnovel" / "context" / f"ch{chapter:04d}_context.json"
    )
    if not ctx_path.exists():
        rep.record(
            "P2", "H23",
            f"context JSON 缺失·跳过锚点纪律检查（ch{chapter:04d}_context.json）",
            True,
        )
        return

    try:
        ctx = _j.loads(ctx_path.read_text(encoding="utf-8"))
    except Exception as e:
        rep.record("P2", "H23", f"context JSON 解析失败: {e}", True)
        return

    # 从执行包读 cadence_table（context-agent Round 17 生成）
    cadence = (
        ctx.get("step_2a_write_prompt", {})
        .get("main_character_cadence")
        or ctx.get("contract", {}).get("main_character_cadence")
        or ctx.get("main_character_cadence")
    )
    if not cadence or not cadence.get("applicable"):
        rep.record(
            "P2", "H23",
            "main_character_cadence 未启用（Round 17 前章节或非重生题材）·跳过",
            True,
        )
        return

    cadence_table = cadence.get("cadence_table", [])
    if not cadence_table:
        rep.record("P2", "H23", "cadence_table 为空·跳过", True)
        return

    # 读本章正文
    text = _load_chapter_text(chapter)
    if not text:
        rep.record("P2", "H23", "正文文件缺失·跳过", True)
        return

    # 配置豁免
    cfg_path = root / ".webnovel" / "hygiene_config.json"
    exemptions = set()
    if cfg_path.exists():
        try:
            exemptions = set(
                _j.loads(cfg_path.read_text(encoding="utf-8")).get(
                    "character_cadence_exemptions", []
                )
            )
        except Exception:
            pass
    if chapter in exemptions:
        rep.record("P2", "H23", f"Ch{chapter} 在豁免列表·跳过", True)
        return

    # 遍历每个角色，判断到期 + 命中
    missing = []
    hit = []
    skipped = []
    for entry in cadence_table:
        name = entry.get("name", "?")
        every_n = entry.get("every_n_chapters", 1)
        # 简单名匹配 + 别名扩展
        aliases = entry.get("aliases", [])
        search_terms = [name] + aliases
        # 仅扫描正文文本（去掉首行"章节标题"若有）
        found_any = any(term and term in text for term in search_terms)
        # 到期逻辑：chapter % every_n_chapters == 0 (每 N 章至少 1 次)
        # 更宽松：只要本章在窗口内（上次出现 + every_n 之内）就算到期
        # 简化实现：chapter == 1 或 every_n == 1 总是到期
        due = (every_n == 1) or ((chapter - 1) % every_n == 0)
        if due and not found_any:
            missing.append(f"{name}(every={every_n})")
        elif found_any:
            hit.append(f"{name}")
        else:
            skipped.append(f"{name}(未到期)")

    if missing:
        rep.record(
            "P1", "H23",
            f"跨章锚点纪律未兑现 {len(missing)}/{len(cadence_table)}: {missing[:3]}· "
            f"读者情感线断层风险（Round 17 约束 XI-XV）",
            False,
        )
    else:
        rep.record(
            "P1", "H23",
            f"跨章锚点纪律 OK (hit={len(hit)} skipped={len(skipped)})",
            True,
        )


def check_reality_red_flags(root: Path, chapter: int, rep: HygieneReport):
    """H22: 现实常识红旗扫描（Round 17 · 根治<example-project> Ch2/Ch6 律所+版权+刷卡 3 项硬伤）

    支持项目级覆盖：.webnovel/reality_check_config.json
    格式：
        {
          "rules": [...],  // 替换默认规则（同 DEFAULT_REALITY_RULES 格式）
          "extra_rules": [...],  // 追加到默认规则
          "disabled_rule_ids": ["law_firm_hours"],  // 禁用默认规则
          "exemptions": {  // 本章白名单：正则命中但明确由情节合理化
            "0006": ["single_swipe_large"],  // Ch6 50 万刷卡已合理化为分笔
            "0002": ["work_product_copyright"]  // Ch2 职务作品已加特批私活
          }
        }
    """
    text_p = None
    for pat in [f"第{chapter:04d}章-*.md", f"第{chapter:04d}章*.md"]:
        cands = list((root / "正文").glob(pat)) if (root / "正文").exists() else []
        if cands:
            text_p = cands[0]
            break
    if not text_p or not text_p.exists():
        rep.record("P2", "H22", "正文文件缺失，跳过现实常识红旗扫描", True)
        return

    rules = list(DEFAULT_REALITY_RULES)
    exemptions = {}
    cfg_p = root / ".webnovel" / "reality_check_config.json"
    if cfg_p.exists():
        try:
            cfg = json.loads(cfg_p.read_text(encoding="utf-8"))
            if cfg.get("rules"):
                rules = list(cfg["rules"])
            if cfg.get("extra_rules"):
                rules.extend(cfg["extra_rules"])
            disabled = set(cfg.get("disabled_rule_ids", []))
            rules = [r for r in rules if r.get("id") not in disabled]
            exemptions = cfg.get("exemptions", {}) or {}
        except Exception as exc:
            rep.record("P2", "H22", f"reality_check_config.json 解析失败: {exc}（使用默认规则）", True)

    chapter_key = f"{chapter:04d}"
    exempted_ids = set(exemptions.get(chapter_key, []))

    text = text_p.read_text(encoding="utf-8", errors="ignore")
    findings = []
    for rule in rules:
        rid = rule.get("id", "unnamed")
        if rid in exempted_ids:
            continue
        pattern = rule.get("pattern", "")
        if not pattern:
            continue
        try:
            matches = list(re.finditer(pattern, text))
        except re.error:
            continue
        if matches:
            severity = rule.get("severity", "P2")
            sample = matches[0].group(0)[:40].replace("\n", " ")
            findings.append({
                "id": rid,
                "domain": rule.get("domain", ""),
                "severity": severity,
                "count": len(matches),
                "sample": sample,
                "message": rule.get("message", ""),
            })

    if not findings:
        rep.record("P1", "H22", "现实常识红旗 0 处（律所/刷卡/版权/反洗钱等 7 类）", True)
        return

    for f in findings:
        rep.record(
            f["severity"],
            f"H22_{f['id']}",
            f"[{f['domain']}] {f['count']} 处命中 · 样例: {f['sample']} · {f['message']} · 合理化后请在 reality_check_config.json 设 exemptions.{chapter_key}",
            False,
        )


def check_polish_sunk_cost(root: Path, chapter: int, rep: HygieneReport):
    """H27: polish sunk cost 警报（Round 20.1 · Ch1-12 体检 Bug 3 根治）

    Ch6 血教训：narrative_version=v3 + polish_log=2 + 五项 80 一线 + 空间方向 -1 倒退
    → 已是 sunk cost 但流程没识别，AI 还会继续 polish。

    检查规则：
      - chapter_meta.{NNNN}.narrative_version 解析 >= 3
      - polish_log 长度 >= 2
      - checker_scores 中存在 ≥ 5 项 ∈ [80, 84]（"80 一线" 集群）
      - → P1 warn 提示考虑回 Step 0 重写而非继续 polish
    """
    state_p = root / ".webnovel" / "state.json"
    if not state_p.exists():
        rep.record("P1", "H27", "state.json 不存在，跳过 sunk cost 检查", True)
        return
    try:
        state = json.loads(state_p.read_text(encoding="utf-8"))
    except Exception as exc:
        rep.record("P1", "H27", f"state.json 解析失败：{exc}", True)
        return
    meta = (state.get("chapter_meta") or {}).get(f"{chapter:04d}") or {}
    if not meta:
        rep.record("P1", "H27", f"chapter_meta.{chapter:04d} 不存在", True)
        return

    nv = meta.get("narrative_version") or "v1"
    nv_n = 1
    if isinstance(nv, str) and nv.startswith("v"):
        try:
            nv_n = int(nv[1:].split(".")[0])
        except Exception:
            nv_n = 1

    polish_log = meta.get("polish_log") or []
    polish_rounds = len([e for e in polish_log if isinstance(e, dict)])

    cs = meta.get("checker_scores") or {}
    canonical_set = {
        "consistency-checker", "continuity-checker", "ooc-checker",
        "reader-pull-checker", "high-point-checker", "pacing-checker",
        "dialogue-checker", "density-checker", "prose-quality-checker",
        "emotion-checker", "flow-checker",
        "reader-naturalness-checker", "reader-critic-checker",
    }
    eighty_line = [
        k for k, v in cs.items()
        if k in canonical_set and isinstance(v, (int, float)) and 80 <= v <= 84
    ]

    if nv_n >= 3 and polish_rounds >= 2 and len(eighty_line) >= 5:
        rep.record(
            "P1", "H27",
            f"sunk cost 警报：nv={nv} polish={polish_rounds} 轮 + {len(eighty_line)} 项 80 一线"
            f"（{sorted(eighty_line)}） · 建议 Step 0 重写而非继续 polish"
            f" · 命中 Round 20 max-rounds=3 上限，刻意突破需 --deviation-reason",
            False,
        )
        return
    rep.record("P1", "H27", f"polish 状态健康（nv={nv}, polish={polish_rounds} 轮）", True)


def check_hook_close_persistence(root: Path, chapter: int, rep: HygieneReport):
    """H26: hook_close 落库一致性（Round 20 · Ch12 RCA P0）

    Ch12 血教训：reader_pull_ch0012.json 已含 hook_close 子对象，
    但 data-agent Phase G 落库步骤被跳过，state.chapter_meta.0012.hook_close 缺失。
    后果：H25 hook_trend 被迫退化跳过、cross-chapter 决策钩缺失探测失效、
    private_csv 取 hook_type 兜底而非 primary_type、跨卷 plan 读不到。

    检查规则：
      - 若 reader_pull_ch{NNNN}.json 存在且含 hook_close.primary_type
      - 但 state.chapter_meta.{NNNN}.hook_close 缺失或 primary_type 为空
      - → P0 fail（必须落库后才能 commit）
    """
    state_p = root / ".webnovel" / "state.json"
    if not state_p.exists():
        rep.record("P0", "H26", "state.json 不存在，跳过 hook_close 落库检查", True)
        return
    rp_p = root / ".webnovel" / "tmp" / f"reader_pull_ch{chapter:04d}.json"
    if not rp_p.exists():
        rep.record("P0", "H26", f"reader_pull_ch{chapter:04d}.json 不存在，跳过", True)
        return
    try:
        rp = json.loads(rp_p.read_text(encoding="utf-8"))
    except Exception:
        rep.record("P0", "H26", f"reader_pull_ch{chapter:04d}.json 解析失败，跳过", True)
        return
    src_hc = rp.get("hook_close") or {}
    src_primary = src_hc.get("primary_type") or ""
    if not src_primary:
        # 老 checker 版本无 hook_close 子对象 - 兼容跳过（不阻断）
        rep.record("P0", "H26", "reader_pull JSON 无 hook_close 子对象（老版本），跳过", True)
        return
    try:
        state = json.loads(state_p.read_text(encoding="utf-8"))
    except Exception as exc:
        rep.record("P0", "H26", f"state.json 解析失败：{exc}", False)
        return
    meta = (state.get("chapter_meta") or {}).get(f"{chapter:04d}") or {}
    state_hc = meta.get("hook_close") or {}
    state_primary = state_hc.get("primary_type") or ""
    if not state_primary:
        rep.record(
            "P0", "H26",
            f"reader_pull_ch{chapter:04d}.json 含 hook_close.primary_type='{src_primary}' "
            f"但 state.chapter_meta.{chapter:04d}.hook_close 缺失。"
            f" data-agent Phase G 落库被跳过。修复："
            f" python webnovel.py state update --set-hook-close "
            f"'{{\"chapter\":{chapter},\"primary\":\"{src_primary}\",\"strength\":{src_hc.get('strength',80)},\"text\":\"...\"}}'",
            False,
        )
        return
    if state_primary != src_primary:
        rep.record(
            "P1", "H26",
            f"reader_pull primary='{src_primary}' 与 state primary='{state_primary}' 不一致，请核对",
            False,
        )
        return
    rep.record("P0", "H26", f"hook_close 落库一致（primary='{src_primary}'）", True)


def check_hook_close_freshness(root: Path, chapter: int, rep: HygieneReport):
    """H28: hook_close 版本新鲜度（Round 20.5 · post-polish drift 根治）

    Root cause：Step 8 polish 能改正文章末决策，但旧 hook_close 仍留在
    state.chapter_meta，H26 只比对 reader_pull JSON 与 state 是否一致，无法判断
    二者是否都已经落后于最新 narrative_version。结果是"正文写出决策钩，
    hook trend 仍读旧信息钩"，H25 继续 P0。

    根治：
      - set-hook-close 写入 source_narrative_version
      - 当前 narrative_version 与 hook_close.source_narrative_version 不一致 → P0
      - 老数据缺 source_narrative_version 但已经有 polish_log → P1，提示回填
    """
    state_p = root / ".webnovel" / "state.json"
    if not state_p.exists():
        rep.record("P0", "H28", "state.json 不存在，跳过 hook_close 版本检查", True)
        return
    try:
        state = json.loads(state_p.read_text(encoding="utf-8"))
    except Exception as exc:
        rep.record("P0", "H28", f"state.json 解析失败：{exc}", False)
        return

    meta = (state.get("chapter_meta") or {}).get(f"{chapter:04d}") or {}
    if not meta:
        rep.record("P0", "H28", f"chapter_meta.{chapter:04d} 不存在，跳过", True)
        return
    hook_close = meta.get("hook_close") or {}
    if not hook_close:
        rep.record("P0", "H28", "hook_close 缺失，交由 H26/H25 判断", True)
        return

    # Round 20.6 · needs_reclassify=True 必须先 set-hook-close 重分类才能通过
    # polish_cycle 末尾自动设此 flag，迫使 AI/人工立即重分类，永不留 stale primary_type
    if hook_close.get("needs_reclassify"):
        old_primary = hook_close.get("primary_type") or "未知"
        synced = hook_close.get("polish_synced_at") or "?"
        rep.record(
            "P0", "H28",
            f"hook_close 待重分类：polish 改了正文（synced_at={synced}），"
            f"旧 primary_type='{old_primary}' 可能已不准。"
            f" 修复：阅读章末后执行 state update --set-hook-close 重新分类，"
            f"设新 primary∈[信息钩,情绪钩,决策钩,动作钩] + source_narrative_version={meta.get('narrative_version','')}",
            False,
        )
        return

    current_nv = str(meta.get("narrative_version") or "").strip()
    hook_nv = str(
        hook_close.get("source_narrative_version")
        or hook_close.get("narrative_version")
        or ""
    ).strip()
    if current_nv and hook_nv and current_nv != hook_nv:
        rep.record(
            "P0", "H28",
            f"hook_close stale：state narrative_version={current_nv}，"
            f"hook_close.source_narrative_version={hook_nv}。"
            f" 说明正文 polish 后未重跑 reader-pull/未重新 set-hook-close，"
            f"会污染 H25 hook trend。修复：重跑 reader-pull-checker 或执行 "
            f"state update --set-hook-close 并带 source_narrative_version={current_nv}",
            False,
        )
        return

    polish_log = meta.get("polish_log") or []
    has_polish = bool([e for e in polish_log if isinstance(e, dict)])
    if current_nv and has_polish and not hook_nv:
        rep.record(
            "P1", "H28",
            f"hook_close 缺 source_narrative_version（当前 {current_nv}，polish_log 已存在）。"
            f" 老数据无法证明章末钩子来自最新版正文；建议重跑 reader-pull 或用 set-hook-close 回填版本。",
            False,
        )
        return

    rep.record("P0", "H28", f"hook_close 版本新鲜（source_narrative_version={hook_nv or 'legacy-none'}）", True)


def check_hook_trend(root: Path, chapter: int, rep: HygieneReport):
    """H25: 章末钩子 4 类跨章趋势（Round 19 Phase G）

    扫描最近 5 章 chapter_meta.{NNNN}.hook_close.primary_type：
      - 全部相同（且非空）→ P1 warn（节奏疲劳，提醒下章切换钩子类型）
      - 任意为空（未回填）→ skip（历史章节兼容）
      - 全 5 章 < 5 章已成稿 → skip
    """
    state_p = root / ".webnovel" / "state.json"
    if not state_p.exists():
        rep.record("P2", "H25", "state.json 不存在，跳过 hook 趋势检查", True)
        return
    try:
        state = json.loads(state_p.read_text(encoding="utf-8"))
    except Exception as exc:
        rep.record("P2", "H25", f"state.json 解析失败：{exc}", True)
        return

    metas = state.get("chapter_meta", {}) or {}
    chs = sorted([k for k in metas.keys() if str(k).isdigit()])
    if len(chs) < 5:
        rep.record("P2", "H25", f"已成稿 {len(chs)} < 5 章，跳过趋势检查", True)
        return

    recent = chs[-5:]
    primaries = [
        ((metas.get(k) or {}).get("hook_close") or {}).get("primary_type") or ""
        for k in recent
    ]
    # 任意为空 → skip（兼容历史未回填章节）
    if any(not p for p in primaries):
        rep.record(
            "P2", "H25",
            f"最近 5 章 hook_close.primary_type 含未回填，跳过（{[int(k) for k in recent]}）",
            True,
        )
        return

    if all(p == primaries[0] for p in primaries):
        rep.record(
            "P1", "H25",
            f"连续 5 章 hook_close.primary_type 相同：{primaries[0]}（章 {[int(k) for k in recent]}）"
            f" · 下章 reader-pull-checker 提醒切换钩子类型",
            False,
        )
        return
    rep.record(
        "P1", "H25",
        f"最近 5 章 hook_close.primary_type 多样性 OK: {primaries}",
        True,
    )

    # Round 20.1 · Ch1-12 体检 P0 升级：连续 8 章无决策钩升 P0 fail
    # 决策钩 = 主角主动选择 = 网文核心爽点。Ch1-12 累计 0 个决策钩是结构信号。
    # 旧逻辑：state get-hook-trend CLI 只在 reader-pull-checker 输出 issue，
    #         hygiene 不强制阻断，导致 12 章累积警报无效。
    # 新逻辑：H25 直接读最近 8 章 primary_type，全无决策钩 → P0 fail。
    #
    # Round 20.2 · 2026-04-26 · Ch3 polish 误伤根治：
    # 旧 H25 P0 不区分当前 chapter，导致 polish 早期章节（如 Ch3）时被未来章节
    # 状态（Ch5-12 全无决策钩）阻断 commit。
    # 修法：H25 P0 仅在"当前 chapter ≥ 当前章号窗口包含的最末章"时触发——
    # 即只有当 polish/写当前最末章及之前 7 章范围时才检查。
    # 早期章节 polish 不受未来章节状态阻断。
    if len(chs) >= 8 and chapter >= int(chs[-1]):
        # 仅在 polish 当前最新章或更新章时检查"未来 8 章"窗口
        recent_8 = chs[-8:]
        primaries_8 = []
        decision_signals = []
        for k in recent_8:
            meta = metas.get(k) or {}
            primary = ((meta.get("hook_close") or {}).get("primary_type") or "")
            primaries_8.append(primary)
            victory = (
                ((meta.get("thrill_score") or {}).get("subdimensions") or {})
                .get("protagonist_victory")
            )
            if primary == "决策钩":
                decision_signals.append(f"Ch{int(k)} hook_close=决策钩")
            elif isinstance(victory, (int, float)) and victory >= 80:
                decision_signals.append(f"Ch{int(k)} protagonist_victory={victory}")
        if all(p for p in primaries_8) and not decision_signals:
            rep.record(
                "P0", "H25",
                f"连续 8 章无决策钩（章 {[int(k) for k in recent_8]} primary_types={primaries_8}）"
                f" · 决策钩=主角主动选择=网文核心爽点，必须在下章兑现"
                f" · 修复：下章 hook_close.primary_type=决策钩 或 reader-thrill protagonist_victory ≥ 80",
                False,
            )
        elif decision_signals:
            rep.record(
                "P0", "H25",
                f"最近 8 章存在主角主动决策/胜利信号：{decision_signals}",
                True,
            )


def check_cross_chapter_overstep(root: Path, chapter: int, rep: HygieneReport):
    """H29: 跨章节正文越权检测（Round 20.x · Ch13 P0 根治 · 2026-04-26）

    Why（Ch13 血教训）：
        Step 5 data-agent 在 Step K 阶段越权改写了 Ch3-12 共 9 章已 commit 正文
        （Ch10 加 "有个姓老的"、Ch12 改"再往后的画面被他按住"），违反 SKILL
        "禁止裸跑 polish commit"——任何正文修改必须经 polish_cycle.py。

    检测策略：
        - 扫描 git status --porcelain 找到所有 M（modified）的 正文/第NNNN章*.md
        - 排除当前 chapter
        - 排除最新一次 commit message 含 [polish:...] 标识的章节（polish_cycle 路径合法）
        - 任一其他章节正文 staged 或 modified → P0 fail
    """
    import subprocess
    try:
        out = subprocess.run(
            ["git", "-c", "core.quotepath=false", "status", "--porcelain", "--", "正文/"],
            cwd=root, capture_output=True, timeout=10,
        )
    except Exception as exc:
        rep.record("P2", "H29", f"git status 调用失败: {exc}", True)
        return

    if out.returncode != 0:
        return

    text = out.stdout.decode("utf-8", errors="replace")
    other_modified = []
    cur_padded = f"第{chapter:04d}章"
    for line in text.splitlines():
        if not line:
            continue
        # porcelain 格式：'XY filename'，X=staged, Y=worktree
        status = line[:2]
        if "M" not in status and "A" not in status:
            continue
        rel = line[3:].strip().strip('"')
        # 仅检测 正文/第NNNN章*.md
        m = re.match(r"^正文/第(\d{4})章", rel.replace("\\", "/"))
        if not m:
            continue
        if cur_padded in rel:
            continue
        other_modified.append(rel)

    if other_modified:
        rep.record(
            "P0", "H29",
            f"检测到非当前章节（Ch{chapter}）的正文文件被修改: "
            f"{other_modified[:5]}（共 {len(other_modified)} 个）· 这违反"
            f" SKILL '禁止裸跑 polish commit'，正文修改必须经 polish_cycle.py。"
            f" 修复：git checkout HEAD -- <文件> 回滚，或用 polish_cycle.py 走合规路径",
            False,
        )
    else:
        rep.record("P0", "H29", "无跨章节正文越权（仅当前章修改）", True)


def check_canon_overstep(root: Path, chapter: int, rep: HygieneReport):
    """H30: Canon Bible / 项目 CLAUDE.md 越权检测（Round 20.x · Ch13 P0 根治）

    Why（Ch13 血教训）：
        data-agent Step K 越权把 Canon Bible 中"Ch24-28 末世爆发窗口"改成
        "Ch35 主爆发"（多处 + 4 个设定集同款字段一起改）。这是项目北极星等级
        的 canon 漂移事故。

    检测策略：
        - 扫描 git diff（含 staged + worktree）涉及 设定集/00-Canon-Bible.md
          和 项目根/CLAUDE.md
        - 任一文件有 M 状态 → P0 fail（要求作者明确确认）
        - 例外：用户主动通过 git commit 时显式带 chore(canon): ... 前缀豁免
          （但 hygiene 仍会发出 warning 提示用户自查）
    """
    import subprocess
    canon_files = ["设定集/00-Canon-Bible.md", "CLAUDE.md"]
    try:
        out = subprocess.run(
            ["git", "-c", "core.quotepath=false", "status", "--porcelain", "--"] + canon_files,
            cwd=root, capture_output=True, timeout=10,
        )
    except Exception as exc:
        rep.record("P2", "H30", f"git status 调用失败: {exc}", True)
        return

    if out.returncode != 0:
        return

    text = out.stdout.decode("utf-8", errors="replace")
    canon_modified = []
    for line in text.splitlines():
        if not line:
            continue
        status = line[:2]
        if "M" not in status:
            continue
        rel = line[3:].strip().strip('"').replace("\\", "/")
        canon_modified.append(rel)

    if canon_modified:
        rep.record(
            "P0", "H30",
            f"检测到 canon 级文件被修改: {canon_modified} · "
            f"Canon Bible / 项目 CLAUDE.md 是北极星等级真源，禁止 data-agent / "
            f"context-agent / 写作主流程在常规章节 commit 中修改。"
            f" 修复：git checkout HEAD -- <文件> 回滚；如确需改动，必须用单独"
            f" 的 chore(canon) commit 并附完整 RCA 说明",
            False,
        )
    else:
        rep.record("P0", "H30", "Canon Bible / CLAUDE.md 未被修改", True)


def check_checker_scores_consistency(root: Path, chapter: int, rep: HygieneReport):
    """H31: chapter_meta.checker_scores 与 review_metrics 一致性
    （Round 20.x · Ch13 P0 根治 · 2026-04-26）

    Why（Ch13 血教训）：
        Step 5 data-agent process-chapter 用自己估算值覆盖了 Step 3+4.5 通过 Task
        subagent 实际跑出的 checker_scores（consistency 88→91 / ooc 86→90 等），
        同时清空了 post_polish_recheck 三条记录。state_manager.process_chapter_result
        已加保护层（PROTECTED_FIELDS），本检查在 hygiene 层做最后一道兜底。

    检测策略：
        - 读 state.json.chapter_meta.{NNNN}.checker_scores.overall
        - 读 index.db 最近一条 review_metrics.overall_score（chapter == 当前章）
        - 两者误差 ≤ 2 → pass
        - 误差 > 2 → P0 fail（说明 data-agent 写库后没经 set-checker-score CLI 重算）
    """
    state_p = root / ".webnovel" / "state.json"
    if not state_p.exists():
        return

    try:
        s = json.loads(state_p.read_text(encoding="utf-8"))
    except Exception:
        return

    meta = s.get("chapter_meta", {}).get(f"{chapter:04d}", {})
    checker_scores = meta.get("checker_scores", {}) or {}
    cs_overall = checker_scores.get("overall")
    meta_overall = meta.get("overall_score")

    if cs_overall is None and meta_overall is None:
        return  # 章未完成评分，跳过

    if cs_overall is None or meta_overall is None:
        rep.record(
            "P1", "H31",
            f"checker_scores.overall={cs_overall} 与 chapter_meta.overall_score="
            f"{meta_overall} 至少一个缺失。两者应同步（set-checker-score CLI 自动维护）",
            False,
        )
        return

    try:
        diff = abs(float(cs_overall) - float(meta_overall))
    except (TypeError, ValueError):
        rep.record(
            "P1", "H31",
            f"checker_scores.overall / overall_score 类型异常: {cs_overall} / {meta_overall}",
            False,
        )
        return

    if diff > 2.0:
        rep.record(
            "P0", "H31",
            f"checker_scores.overall={cs_overall} 与 overall_score={meta_overall}"
            f" 误差 {diff:.1f} > 2 · 通常意味着 data-agent process-chapter 越权"
            f" 覆盖了 Step 3+4.5 真源后未经 set-checker-score CLI 重算。"
            f" 修复：用 `webnovel.py state update --set-checker-score` 重写 13 维"
            f" 真实分数，CLI 会自动重算 overall",
            False,
        )
    else:
        rep.record(
            "P0", "H31",
            f"checker_scores.overall={cs_overall} ≈ overall_score={meta_overall}（diff={diff:.1f}）",
            True,
        )


def check_chapter_meta_overstep(root: Path, chapter: int, rep: HygieneReport):
    """H35: state.json chapter_meta 一刀切越权检测（Round 21.7 · Ch22 P0 根治 · 2026-04-30）

    Why（Ch22 血教训）：
        audit-agent Step 6 越权把 state.json 中 22 章的 chapter_meta.NNNN.narrative_version
        全部一刀切刷成 'v7.1'（混淆 Canon Bible 文档版本号 v7.1 与 chapter_meta
        narrative_version 字段的版本计数 v1/v2/v3）。同时把 progress.total_words 从
        62357（22 章累计）覆盖成 2587（仅 Ch22 单章）。这两个 bug 都不在现有 H29
        （正文）/ H30（Canon）/ H31（checker_scores 一致性）的检测范围内。

    检测策略：
        1. git diff 工作区 + staged 找 .webnovel/state.json
        2. 解析 diff 中 chapter_meta.{NNNN} 同字段被改成相同值的章数
        3. 触发条件：narrative_version / overall_score / review_score / naturalness_verdict
           / reader_critic_verdict / thrill_score 任一字段同值改动 ≥ 3 章
           且不在 polish_cycle 历史（commit message 含 [polish:...]）
           且当前不在 chore(state-rebase) / chore(round*-data-repair) / [round*-rebase]
           豁免清单 → P0 fail（典型 audit/data-agent 越权或 LLM 一刀切模式）
    """
    import subprocess
    state_file = ".webnovel/state.json"
    try:
        out = subprocess.run(
            ["git", "diff", "HEAD", "--", state_file],
            cwd=root, capture_output=True, timeout=10,
        )
    except Exception as exc:
        rep.record("P2", "H35", f"git diff state.json 失败: {exc}", True)
        return

    diff_text = out.stdout.decode("utf-8", errors="replace") if out.stdout else ""
    if not diff_text.strip():
        rep.record("P0", "H35", "state.json chapter_meta 无一刀切越权", True)
        return

    # 解析 diff：找 chapter block + 各字段改动
    PROTECTED_META_FIELDS = (
        "narrative_version", "overall_score", "review_score",
        "naturalness_verdict", "reader_critic_verdict", "thrill_score",
    )
    field_value_chapters = {}  # {(field, new_value): set(chapters)}
    current_chapter = None
    for line in diff_text.splitlines():
        m_ch = re.match(r'^[+\- ]*"(\d{4})":\s*\{', line)
        if m_ch:
            current_chapter = m_ch.group(1)
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        if current_chapter is None:
            continue
        line_stripped = line[1:].strip().rstrip(",")
        for field in PROTECTED_META_FIELDS:
            m_f = re.match(rf'"{field}":\s*(.+)$', line_stripped)
            if m_f:
                value = m_f.group(1).strip().strip('"').rstrip(",").strip().strip('"')
                key = (field, value)
                field_value_chapters.setdefault(key, set()).add(current_chapter)
                break

    # 检测一刀切（≥ 3 章同字段改成相同值）
    overstep_groups = []
    for (field, value), chapters in field_value_chapters.items():
        if len(chapters) >= 3:
            overstep_groups.append((field, value, sorted(chapters)))

    if not overstep_groups:
        rep.record("P0", "H35", "state.json chapter_meta 无一刀切越权", True)
        return

    # 豁免：commit message / 当前 commit 在 polish/rebase 路径
    # 检查最近一次 commit message（HEAD~..HEAD 不存在则跳）
    try:
        last_msg = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            cwd=root, capture_output=True, timeout=5,
        ).stdout.decode("utf-8", errors="replace").strip()
    except Exception:
        last_msg = ""
    exempted_keywords = ("[polish:", "chore(state-rebase)", "chore(round", "data-repair", "[rebase]", "round21.7")
    is_exempted = any(kw in last_msg for kw in exempted_keywords)

    detail = "; ".join(
        f"{field}={value!r}@{len(chs)}章({','.join(chs[:3])}...)"
        for field, value, chs in overstep_groups[:3]
    )

    if is_exempted:
        rep.record(
            "P1", "H35",
            f"state.json chapter_meta 一刀切检测到 {len(overstep_groups)} 组改动 ({detail})，"
            f"但当前 commit 在豁免路径 ({last_msg[:80]})；仍提示自查",
            True,
        )
    else:
        rep.record(
            "P0", "H35",
            f"state.json chapter_meta 一刀切越权: {len(overstep_groups)} 组字段改成同值跨 ≥3 章 "
            f"({detail})。这是典型的 audit-agent / data-agent 越权或 LLM 一刀切模式。"
            f" 修复：git checkout HEAD -- .webnovel/state.json 回滚；"
            f" 如确需批量改动，必须用 chore(state-rebase) commit 前缀豁免",
            False,
        )


def check_total_words_consistency(root: Path, chapter: int, rep: HygieneReport):
    """H36: progress.total_words 与 chapter_meta 一致性（Round 21.7 · Ch22 P0 根治）

    Why（Ch22 血教训）：
        data-agent Step D 直接 Edit state.json 把 progress.total_words 覆盖成
        本章字数（2587）而非累加。Round 18.2 已加 state update --add-words CLI
        从 chapter_meta 全表幂等重算，但 data-agent 没用 CLI，绕过守卫直接覆盖。

    检测策略：
        progress.total_words ≈ sum(chapter_meta.*.word_count)（容差 ±1%，至少 ±100 字）
        否则 P0 fail，提示用 state update --add-words 重算
    """
    state_file = root / ".webnovel" / "state.json"
    if not state_file.exists():
        rep.record("P2", "H36", "state.json 不存在", True)
        return
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except Exception as exc:
        rep.record("P1", "H36", f"state.json 解析失败: {exc}", True)
        return

    progress = state.get("progress") or {}
    chapter_meta = state.get("chapter_meta") or {}
    if not chapter_meta:
        rep.record("P0", "H36", "chapter_meta 为空，跳过", True)
        return

    total_actual = sum(
        int(v.get("word_count", 0) or 0)
        for v in chapter_meta.values()
        if isinstance(v, dict)
    )
    total_recorded = int(progress.get("total_words", 0) or 0)
    if total_actual == 0:
        rep.record("P2", "H36", "chapter_meta 字数全 0，跳过", True)
        return

    diff = abs(total_recorded - total_actual)
    tolerance = max(int(total_actual * 0.01), 100)

    if diff > tolerance:
        rep.record(
            "P0", "H36",
            f"progress.total_words={total_recorded} 与 sum(chapter_meta.*.word_count)={total_actual} "
            f"差 {diff} > 容差 {tolerance}。"
            f" 这是 data-agent Step D 直接覆盖 total_words 的典型 bug。"
            f" 修复：python webnovel.py state update --add-words "
            f"'{{\"chapter\":{chapter},\"words\":{chapter_meta.get(f'{chapter:04d}', {}).get('word_count', 0)}}}'",
            False,
        )
    else:
        rep.record(
            "P0", "H36",
            f"progress.total_words={total_recorded} ≈ sum(chapter_meta.*.word_count)={total_actual} "
            f"(diff={diff}, tolerance={tolerance})",
            True,
        )


def check_chapter_date_anchor_continuity(root: Path, chapter: int, rep: HygieneReport):
    """H37: 章首 D-N 时间锚连续性（Round 21.8 · Ch1-22 锐评跳日 P1）

    Why（外部锐评 Ch1-22 5 处跳日血教训）：
        Ch4 D-27 → Ch5 D-25（跳 D-26）/ Ch10 D-20 → Ch11 D-18（跳 D-19）/
        Ch14 D-15 → Ch15 D-13（跳 D-14）/ Ch20 D-8 → Ch21 D-6（跳 D-7）。
        倒计时是核心紧张感，跳日必须文中显式 callback（"D-N 这天他在地窖..."）。

    检测策略：
        - 当前章首行 D-N · YYYY-MM-DD · 重生第 K 天 解析得 N_curr / K_curr
        - 上一章首行同样解析得 N_prev / K_prev
        - 期望: N_curr == N_prev - 1 且 K_curr == K_prev + 1
        - 跳日（≥ 2 天）→ 扫描当前章正文前 30 行是否含 "D-{N_prev-1}" 显式 callback
        - 没 callback → P1 warn（不阻断 commit，但要求作者补一句过渡）
    """
    if chapter <= 1:
        rep.record("P1", "H37", "首章无前序章节，跳过 D-N 连续性检查", True)
        return

    def _parse_date_anchor(text: str):
        """解析 'D-N · 日期 · 重生第 K 天' 首行"""
        first_line = text.split("\n", 1)[0].strip()
        m = re.match(r"D-(\d+)\s*[·•・]\s*\d{4}-\d{2}-\d{2}.*?重生第\s*(\d+)\s*天", first_line)
        if not m:
            return None, None
        return int(m.group(1)), int(m.group(2))

    chapters_dir = root / "正文"
    if not chapters_dir.exists():
        rep.record("P2", "H37", "正文目录不存在", True)
        return

    cur_files = sorted(chapters_dir.glob(f"第{chapter:04d}章*.md"))
    prev_files = sorted(chapters_dir.glob(f"第{chapter-1:04d}章*.md"))
    if not cur_files or not prev_files:
        rep.record("P2", "H37", f"找不到 Ch{chapter} 或 Ch{chapter-1} 正文", True)
        return

    cur_text = cur_files[0].read_text(encoding="utf-8", errors="replace")
    prev_text = prev_files[0].read_text(encoding="utf-8", errors="replace")
    n_cur, k_cur = _parse_date_anchor(cur_text)
    n_prev, k_prev = _parse_date_anchor(prev_text)

    if n_cur is None or n_prev is None:
        rep.record("P2", "H37", f"D-N 锚解析失败 (cur={n_cur}, prev={n_prev})", True)
        return

    expected_gap = 1
    actual_gap = n_prev - n_cur  # 倒计时减少 = N 递减
    if actual_gap == expected_gap:
        rep.record("P0", "H37", f"D-N 连续: Ch{chapter-1} D-{n_prev} → Ch{chapter} D-{n_cur}", True)
        return
    if actual_gap < expected_gap:
        rep.record(
            "P1", "H37",
            f"D-N 倒退或重复: Ch{chapter-1} D-{n_prev} → Ch{chapter} D-{n_cur} "
            f"(gap={actual_gap}; 期望 1)。检查是否同日多事件",
            False,
        )
        return

    # 跳日 ≥ 2 天 → 扫 callback
    skipped_dns = [n_cur + i for i in range(1, actual_gap)]
    head_text = "\n".join(cur_text.split("\n")[:30])
    has_callback = all(f"D-{dn}" in head_text for dn in skipped_dns)
    if has_callback:
        rep.record(
            "P0", "H37",
            f"Ch{chapter-1} D-{n_prev} → Ch{chapter} D-{n_cur} 跳 {actual_gap-1} 天，"
            f"前 30 行已 callback {skipped_dns}",
            True,
        )
    else:
        missing = [dn for dn in skipped_dns if f"D-{dn}" not in head_text]
        rep.record(
            "P1", "H37",
            f"Ch{chapter-1} D-{n_prev} → Ch{chapter} D-{n_cur} 跳 {actual_gap-1} 天，"
            f"前 30 行缺 callback: {missing}。倒计时是核心紧张感，"
            f"必须在章首加一句 'D-N 这天他在...' 过渡说明",
            False,
        )


def check_no_markdown_bold_in_prose(root: Path, chapter: int, rep: HygieneReport):
    """H38: 正文禁用 **加粗** markdown 标记（Round 21.8 · Ch15 锐评 P0）

    Why（Ch15 血教训）：
        Ch15 正文出现 5 处 **加粗** markdown 笔记残留（L121/L161/L181/L187/L243），
        像写作备注或强调笔记，破坏网文沉浸感，编辑视角直接退稿。

    检测策略：
        正文文件中匹配 ``\\*\\*[^\\s\\*]`` (start) 或 ``[^\\s\\*]\\*\\*`` (end)，
        排除三个 markdown 例外区: ``` 代码块、> blockquote 引用、$...$ 数学公式。
        任一 ** 出现 → P0 fail。
    """
    chapters_dir = root / "正文"
    cur_files = sorted(chapters_dir.glob(f"第{chapter:04d}章*.md"))
    if not cur_files:
        rep.record("P2", "H38", "找不到正文", True)
        return
    text = cur_files[0].read_text(encoding="utf-8", errors="replace")
    # 行级扫描：跳过 code fence + blockquote + 行首 `>`
    bold_lines = []
    in_code_fence = False
    for i, line in enumerate(text.split("\n"), 1):
        stripped = line.lstrip()
        if stripped.startswith("```"):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence:
            continue
        if stripped.startswith(">"):
            continue
        # 至少要有一对 ** ... **，且中间非空
        if re.search(r"\*\*[^\*\n]+\*\*", line):
            bold_lines.append((i, line.strip()[:80]))

    if bold_lines:
        sample = "; ".join(f"L{i}: {s}" for i, s in bold_lines[:3])
        rep.record(
            "P0", "H38",
            f"Ch{chapter} 正文出现 markdown 加粗 {len(bold_lines)} 处 ({sample})。"
            f" 网文正文禁用 **...**（破坏沉浸感）。"
            f" 修复：删除 ** 改为普通行文",
            False,
        )
    else:
        rep.record("P0", "H38", "正文无 markdown 加粗", True)


def check_signature_word_overuse(root: Path, chapter: int, rep: HygieneReport):
    """H39: 跨章签名词频率上限（Round 21.8 · Ch1-22 锐评模板感 P1）

    Why（外部锐评血教训）：
        Ch1-22 模板词高频：存储位 45 / 手册 42 / 生机值 36 / 这一次 35 /
        晓得 18 / 停了一拍 16 / 沉默了三秒 9 / 耳朵尖 10。
        重复不是不能用，但形成模板感会让读者觉得"作者在套路"。

    检测策略：
        - 单章高频词 ≥ 5 次 → P1 warn (本章超载)
        - 5 章累计 ≥ 25 次 → P1 warn (滑窗过载)
        - 默认词表（项目可通过 .webnovel/signature_words.json 覆盖）
    """
    DEFAULT_WORDS = {
        "存储位": 5, "手册": 5, "生机值": 5, "这一次": 5,
        "停了一拍": 3, "沉默了三秒": 3, "耳朵尖": 3, "见牙不见眼": 3,
    }
    config_file = root / ".webnovel" / "signature_words.json"
    words_limit = DEFAULT_WORDS.copy()
    if config_file.exists():
        try:
            words_limit.update(json.loads(config_file.read_text(encoding="utf-8")))
        except Exception:
            pass

    chapters_dir = root / "正文"
    cur_files = sorted(chapters_dir.glob(f"第{chapter:04d}章*.md"))
    if not cur_files:
        rep.record("P2", "H39", "找不到正文", True)
        return
    cur_text = cur_files[0].read_text(encoding="utf-8", errors="replace")

    # 单章超载
    over_chapter = []
    for w, lim in words_limit.items():
        cnt = cur_text.count(w)
        if cnt > lim:
            over_chapter.append((w, cnt, lim))

    # 5 章滑窗
    window_files = []
    for ch_n in range(max(1, chapter - 4), chapter + 1):
        files = sorted(chapters_dir.glob(f"第{ch_n:04d}章*.md"))
        if files:
            window_files.append(files[0])
    over_window = []
    for w, lim in words_limit.items():
        total = sum(f.read_text(encoding="utf-8", errors="replace").count(w) for f in window_files)
        win_lim = lim * 5
        if total > win_lim:
            over_window.append((w, total, win_lim))

    msgs = []
    if over_chapter:
        msgs.append(
            "本章超载: " + ", ".join(f"{w}={c}>{l}" for w, c, l in over_chapter[:3])
        )
    if over_window:
        msgs.append(
            "5 章累计超载: " + ", ".join(f"{w}={c}>{l}" for w, c, l in over_window[:3])
        )

    if msgs:
        rep.record(
            "P1", "H39",
            f"签名词模板感警报 · " + "; ".join(msgs) +
            f" · 用其它表达替换或删除冗余念叨（参考: 用'那本书'代'手册'/用'手心冷'代'生机值'）",
            False,
        )
    else:
        rep.record("P1", "H39", "签名词频率正常", True)


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
    check_hook_close_persistence(root, args.chapter, rep)  # H26 · Round 20 · Ch12 RCA P0
    check_hook_close_freshness(root, args.chapter, rep)  # H28 · Round 20.5 · hook_close post-polish freshness
    check_cross_chapter_overstep(root, args.chapter, rep)  # H29 · Round 20.x · Ch13 P0
    check_canon_overstep(root, args.chapter, rep)  # H30 · Round 20.x · Ch13 P0
    check_checker_scores_consistency(root, args.chapter, rep)  # H31 · Round 20.x · Ch13 P0
    check_chapter_meta_overstep(root, args.chapter, rep)  # H35 · Round 21.7 · Ch22 P0
    check_total_words_consistency(root, args.chapter, rep)  # H36 · Round 21.7 · Ch22 P0
    check_no_markdown_bold_in_prose(root, args.chapter, rep)  # H38 · Round 21.8 · Ch15 P0

    # P1 检查
    check_root_layout(root, rep)
    check_score_alignment(root, args.chapter, rep)
    check_foreshadowing_dedup(root, args.chapter, rep)
    check_report_overall_score_count(root, args.chapter, rep)
    check_allusions_schema(root, args.chapter, rep)
    check_checker_scores_canonical(root, args.chapter, rep)
    check_post_commit_polish_drift(root, args.chapter, rep)
    check_audit_post_polish_drift(root, args.chapter, rep)  # H24 · Round 17.3 · Ch8 RCA
    check_polish_log_schema(root, args.chapter, rep)
    check_cross_chapter_style_drift(root, args.chapter, rep)  # H21 · Round 16
    check_reality_red_flags(root, args.chapter, rep)  # H22 · Round 17
    check_cross_chapter_cadence(root, args.chapter, rep)  # H23 · Round 17.1 · Ch7 RCA P1.5
    check_hook_trend(root, args.chapter, rep)  # H25 · Round 19 Phase G · 章末钩子 4 类跨章趋势
    check_polish_sunk_cost(root, args.chapter, rep)  # H27 · Round 20.1 · sunk cost 警报
    check_chapter_date_anchor_continuity(root, args.chapter, rep)  # H37 · Round 21.8 · Ch1-22 跳日 P1
    check_signature_word_overuse(root, args.chapter, rep)  # H39 · Round 21.8 · Ch1-22 模板感 P1

    # P2 检查
    check_context_snapshot(root, args.chapter, rep)
    run_project_local_checks(root, args.chapter, rep)

    print(rep.render())
    return rep.exit_code()


if __name__ == "__main__":
    sys.exit(main())
