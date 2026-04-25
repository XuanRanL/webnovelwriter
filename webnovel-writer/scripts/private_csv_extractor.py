#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
私库 CSV 自动提取器（Round 19 Phase F）

输入：项目 .webnovel/tmp/*.json + audit_reports/*.json + polish_reports/*.md
输出：{project}/.webnovel/private-csv/*.csv 追加新条目（不重复）

Round 19.1 P0-1 根治：私库默认写到**项目本地**而不是 fork 共享目录。
fork 共享 references/private-csv/ 仅留空表头作为 plugin 携带的 schema。
跨项目隔离：写"画山海" 不会被"末世重生"反例污染。

用法:
    python private_csv_extractor.py --project 末世重生-我在空间里种出了整个基地 \
                                    --table ai-replacement-vocab \
                                    --chapters 1-11
"""
from __future__ import annotations
import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

CSV_HEADERS = {
    "ai-replacement-vocab": ["编号","章节","严重度","坏样本","好样本","子维度","修复方向","源RCA"],
    "strong-chapter-end-hooks": ["编号","章节","严重度","坏样本","好样本","钩子类型","章节分数","修复方向","源RCA"],
    "emotion-earned-vs-forced": ["编号","章节","严重度","坏样本","好样本","情感类型","修复方向","源RCA"],
    "canon-violation-traps": ["编号","章节","严重度","坏样本","好样本","禁区类型","修复方向","源RCA"],
}

PREFIX = {
    "ai-replacement-vocab": "AV",
    "strong-chapter-end-hooks": "SH",
    "emotion-earned-vs-forced": "EE",
    "canon-violation-traps": "CV",
}

# 历史命名兼容（Ch9 用 {checker}_ch{NNNN}.json，多数用 {checker}_check_ch{NNNN}.json，
# Ch1-5 早期用 {checker}_ch{N}.json 单数字位，Ch9 也有部分单数字位）
def _candidate_paths(tmp: Path, checker: str, ch: int) -> List[Path]:
    nnnn = f"{ch:04d}"
    n = str(ch)
    bases = [
        f"{checker}_check_ch{nnnn}",
        f"{checker}_ch{nnnn}",
        f"{checker}_ch{n}",
        f"{checker}_recheck_ch{nnnn}",
    ]
    suffixes = ["", "_v2", "_v3", "_v4", "_v5"]
    paths = []
    for b in bases:
        for s in suffixes:
            paths.append(tmp / f"{b}{s}.json")
    return paths

def _load_json(p: Path) -> Optional[dict]:
    if not p.exists(): return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

def _trunc(s: str, n: int = 200) -> str:
    if not s: return ""
    s = str(s).strip().replace("\n", " ").replace("\r", " ")
    return s[:n]

def _get_issues(data: dict) -> List[dict]:
    """统一获取 issues / problems / red_flags 列表。"""
    out = []
    for k in ("issues", "problems", "red_flags"):
        v = data.get(k)
        if isinstance(v, list):
            out.extend([x for x in v if isinstance(x, dict)])
    return out

def _evidence(issue: dict) -> str:
    return issue.get("evidence") or issue.get("quote") or ""

def _evidence_or_desc(issue: dict) -> str:
    """对于 emotion-checker 等无 quote/evidence 字段的，提取 description 作为坏样本。"""
    e = _evidence(issue)
    if e: return e
    d = _description(issue)
    if not d: return ""
    # 尝试抓「...」/"..." 内引文作为优先证据
    m = re.search(r"[「『\"“]([^」』\"”]{4,80})[」』\"”]", d)
    if m: return m.group(1)
    return d

def _fix_hint(issue: dict) -> str:
    return (
        issue.get("fix_hint")
        or issue.get("fix_suggestion")
        or issue.get("suggestion")
        or ""
    )

def _description(issue: dict) -> str:
    return issue.get("description") or issue.get("reason") or ""

def load_existing(csv_path: Path) -> List[Dict[str, str]]:
    if not csv_path.exists():
        return []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def next_id(prefix: str, rows: List[Dict[str, str]]) -> str:
    nums = []
    for r in rows:
        m = re.match(rf"^{prefix}-(\d+)$", r.get("编号", ""))
        if m:
            nums.append(int(m.group(1)))
    n = (max(nums) + 1) if nums else 1
    return f"{prefix}-{n:03d}"

def is_duplicate(new_row: Dict[str, str], existing: List[Dict[str, str]]) -> bool:
    bs = (new_row.get("坏样本") or "").strip()
    ch = str(new_row.get("章节") or "").strip()
    if not bs:
        # 空坏样本（如 strong-hook 行）按章节+好样本去重
        gs = (new_row.get("好样本") or "").strip()
        for r in existing:
            if r.get("章节", "").strip() == ch and (r.get("好样本") or "").strip() == gs:
                return True
        return False
    for r in existing:
        if r.get("章节", "").strip() == ch and (r.get("坏样本") or "").strip() == bs:
            return True
    return False

# --- Sub-dimension classification helpers ---

def _classify_subdimension(issue: dict) -> str:
    """根据 issue 类型/描述/证据推断子维度。"""
    txt = " ".join([
        str(issue.get("type", "")),
        str(issue.get("category", "")),
        str(issue.get("subdimension", "")),
        str(issue.get("subcategory", "")),
        _description(issue),
        _evidence(issue),
    ]).lower()
    # 直接命中
    for sub in ("vocab", "syntax", "narrative", "emotion", "dialogue"):
        if sub in txt:
            return sub
    # 关键词降级
    if any(k in txt for k in ("ai腔", "ai 腔", "套话", "口头禅", "词", "形容词", "副词")):
        return "vocab"
    if any(k in txt for k in ("句法", "句式", "语序", "病句", "破折号", "省略号")):
        return "syntax"
    if any(k in txt for k in ("叙事", "声音", "作者签名", "镜头", "比喻", "节奏")):
        return "narrative"
    if any(k in txt for k in ("情绪", "show", "tell", "具身")):
        return "emotion"
    if any(k in txt for k in ("对白", "对话", "台词")):
        return "dialogue"
    return "vocab"

# --- Extractors ---

def extract_ai_replacement_vocab(project: Path, chapters: range) -> List[Dict[str, str]]:
    rows = []
    tmp = project / ".webnovel" / "tmp"
    for ch in chapters:
        # 兼容多种命名：reader_naturalness / naturalness
        candidates = _candidate_paths(tmp, "naturalness", ch) + _candidate_paths(tmp, "reader_naturalness", ch)
        seen_files = set()
        for p in candidates:
            if p in seen_files: continue
            seen_files.add(p)
            data = _load_json(p)
            if not data: continue
            for issue in _get_issues(data):
                ev = _evidence(issue)
                fh = _fix_hint(issue)
                if not ev: continue
                # 严重度过滤：忽略 critical/high/medium 才入库；low 也入库（信息量足）
                rows.append({
                    "章节": str(ch),
                    "严重度": issue.get("severity") or "medium",
                    "坏样本": _trunc(ev, 200),
                    "好样本": _trunc(fh, 200),
                    "子维度": _classify_subdimension(issue),
                    "修复方向": _trunc(fh or _description(issue), 120),
                    "源RCA": "",
                })
    return rows

def extract_strong_chapter_end_hooks(project: Path, chapters: range) -> List[Dict[str, str]]:
    rows = []
    tmp = project / ".webnovel" / "tmp"
    text_dir = project / "正文"
    for ch in chapters:
        score = None
        data = None
        for p in _candidate_paths(tmp, "reader_pull", ch):
            d = _load_json(p)
            if d:
                data = d
                break
        if not data: continue
        # score: 兼容 overall_score / reader_pull / score
        raw_score = data.get("overall_score")
        if raw_score is None: raw_score = data.get("reader_pull")
        if raw_score is None: raw_score = data.get("score")
        try:
            score = int(raw_score)
        except (TypeError, ValueError):
            continue
        if score < 90: continue
        # hook_type：优先 hook_close.primary_type（Phase G 之后），降级 hook_type，降级"信息钩"默认
        hc = data.get("hook_close") or {}
        hook_type = hc.get("primary_type") or data.get("hook_type") or "信息钩"
        # 找正文章末段
        candidates = list(text_dir.glob(f"第{ch:04d}章*.md")) + list(text_dir.glob(f"第{ch}章*.md"))
        last_chunk = ""
        if candidates:
            try:
                text = candidates[0].read_text(encoding="utf-8", errors="ignore")
                # 去 fenced code blocks（粗略）
                text = re.sub(r"```[\s\S]*?```", "", text)
                last_chunk = text.strip().split("\n\n")[-1][-200:]
            except Exception:
                last_chunk = ""
        rows.append({
            "章节": str(ch),
            "严重度": "low",
            "坏样本": "",
            "好样本": _trunc(last_chunk, 200),
            "钩子类型": hook_type,
            "章节分数": str(score),
            "修复方向": f"参考章 {ch} 末段（reader_pull={score}）",
            "源RCA": "",
        })
    return rows

def extract_emotion_earned_forced(project: Path, chapters: range) -> List[Dict[str, str]]:
    rows = []
    tmp = project / ".webnovel" / "tmp"
    for ch in chapters:
        seen = set()
        for p in _candidate_paths(tmp, "emotion", ch):
            if p in seen: continue
            seen.add(p)
            data = _load_json(p)
            if not data: continue
            for issue in _get_issues(data):
                blob = " ".join([
                    str(issue.get("type", "")),
                    str(issue.get("subcategory", "")),
                    str(issue.get("category", "")),
                    _description(issue),
                    _evidence(issue),
                    _fix_hint(issue),
                ]).lower()
                # earned 关键词
                if any(k in blob for k in ("earned", "挣得", "真挚", "earned_ok", "natural_emotion")):
                    kind = "earned"
                # forced 关键词（含 EMOTION_SHALLOW / tell not show / 抒情过早 / 情感透支）
                elif any(k in blob for k in (
                    "forced", "勉强", "造作", "煽情", "强加", "虚浮", "shallow",
                    "emotion_shallow", "情感过早", "情感透支", "情感失衡",
                    "tell not show", "tell_not_show", "tell ", " tell.", "轻度 tell", "轻量tell", "轻量 tell",
                    "抒情",
                )):
                    kind = "forced"
                else:
                    continue
                ev = _evidence_or_desc(issue)
                if not ev: continue
                rows.append({
                    "章节": str(ch),
                    "严重度": issue.get("severity") or "medium",
                    "坏样本": _trunc(ev, 200),
                    "好样本": _trunc(_fix_hint(issue), 200),
                    "情感类型": kind,
                    "修复方向": _trunc(_fix_hint(issue) or _description(issue), 120),
                    "源RCA": "",
                })
    return rows

# audit B 层 id → 禁区类型映射
B_ID_TO_TRAP = {
    "B1": "设定矛盾",
    "B2": "关系漂移",
    "B3": "时间线漂移",
    "B4": "战力越权",
    "B5": "战力越权",
    "B6": "设定矛盾",
    "B7": "时间线漂移",
    "B8": "关系漂移",
    "B9": "设定矛盾",
    "B-VF": "战力越权",
    "B-TL": "时间线漂移",
    "B-REL": "关系漂移",
    "B-CONS": "设定矛盾",
    "B-RC": "设定矛盾",
    "B-WC": "时间线漂移",
    "B-POL": "设定矛盾",
}

CONS_TYPE_TO_TRAP = {
    "SETTING_CONFLICT": "设定矛盾",
    "TIMELINE": "时间线漂移",
    "TIMELINE_CONFLICT": "时间线漂移",
    "CONTINUITY": "时间线漂移",
    "CHARACTER_CONFLICT": "关系漂移",
    "RELATION_DRIFT": "关系漂移",
    "POWER_OVERREACH": "战力越权",
    "LOGIC_CONFLICT": "战力越权",
    "setting": "设定矛盾",
    "timeline": "时间线漂移",
    "character": "关系漂移",
    "logic": "战力越权",
}

def extract_canon_violations(project: Path, chapters: range) -> List[Dict[str, str]]:
    rows = []
    tmp = project / ".webnovel" / "tmp"
    audit = project / ".webnovel" / "audit_reports"
    for ch in chapters:
        # 1) consistency-checker 抓 problems / issues
        seen = set()
        for p in _candidate_paths(tmp, "consistency", ch):
            if p in seen: continue
            seen.add(p)
            data = _load_json(p)
            if not data: continue
            for issue in _get_issues(data):
                t = str(issue.get("type") or issue.get("category") or "").strip()
                trap = CONS_TYPE_TO_TRAP.get(t) or CONS_TYPE_TO_TRAP.get(t.lower())
                if not trap:
                    # 关键词降级
                    blob = (t + " " + _description(issue)).lower()
                    if "时间" in blob or "倒计时" in blob or "timeline" in blob:
                        trap = "时间线漂移"
                    elif "关系" in blob or "称呼" in blob or "人物" in blob:
                        trap = "关系漂移"
                    elif "战力" in blob or "等级" in blob or "金手指" in blob:
                        trap = "战力越权"
                    else:
                        trap = "设定矛盾"
                ev = _evidence(issue)
                if not ev: continue
                rows.append({
                    "章节": str(ch),
                    "严重度": issue.get("severity") or "medium",
                    "坏样本": _trunc(ev, 200),
                    "好样本": _trunc(_fix_hint(issue), 200),
                    "禁区类型": trap,
                    "修复方向": _trunc(_fix_hint(issue) or _description(issue), 120),
                    "源RCA": "",
                })
        # 2) audit_reports（JSON 格式）B 层 warn/fail
        for ar_name in [f"ch{ch:04d}.json", f"ch{ch:04d}_audit.json"]:
            ar = audit / ar_name
            if not ar.exists(): continue
            ad = _load_json(ar)
            if not ad: continue
            layers = ad.get("layers") or {}
            for lk, lv in layers.items():
                if not lk.startswith("B"): continue
                for c in (lv.get("checks") or []):
                    if c.get("status") not in ("warn", "fail"): continue
                    cid = str(c.get("id") or "").strip()
                    trap = B_ID_TO_TRAP.get(cid) or "设定矛盾"
                    ev = c.get("evidence") or c.get("name") or ""
                    if not ev: continue
                    rows.append({
                        "章节": str(ch),
                        "严重度": c.get("severity") or "medium",
                        "坏样本": _trunc(ev, 200),
                        "好样本": "",
                        "禁区类型": trap,
                        "修复方向": f"audit B 层 {cid} {c.get('status')} · 参 audit_reports/ch{ch:04d}.json",
                        "源RCA": "",
                    })
    return rows

EXTRACTORS = {
    "ai-replacement-vocab": extract_ai_replacement_vocab,
    "strong-chapter-end-hooks": extract_strong_chapter_end_hooks,
    "emotion-earned-vs-forced": extract_emotion_earned_forced,
    "canon-violation-traps": extract_canon_violations,
}

def parse_chapters(s: str) -> range:
    s = s.strip()
    if "-" in s:
        a, b = s.split("-")
        return range(int(a), int(b) + 1)
    return range(int(s), int(s) + 1)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--table", required=True, choices=list(CSV_HEADERS.keys()))
    ap.add_argument("--chapters", required=True, help="e.g. 1-11 or 5")
    ap.add_argument("--output-dir", default=None)
    args = ap.parse_args()

    project = Path(args.project).resolve()
    if not project.exists():
        print(f"[ERR] project not found: {project}", file=sys.stderr); return 2

    # Round 19.1 P0-1：默认输出到项目本地 .webnovel/private-csv/，跨项目隔离
    # 老路径（fork 共享 references/private-csv/）仅作 schema 携带，不写本作专属数据
    if args.output_dir:
        out_dir = Path(args.output_dir)
    else:
        out_dir = project / ".webnovel" / "private-csv"
    # 自动从 fork 共享路径继承 schema（如项目本地未初始化）
    fork_shared = Path(__file__).resolve().parent.parent / "references" / "private-csv"
    if not (out_dir / f"{args.table}.csv").exists():
        seed_csv = fork_shared / f"{args.table}.csv"
        if seed_csv.exists():
            out_dir.mkdir(parents=True, exist_ok=True)
            # 复制 schema 表头（不带数据）
            with open(seed_csv, "r", encoding="utf-8-sig", newline="") as f:
                first_line = f.readline()
            with open(out_dir / f"{args.table}.csv", "w", encoding="utf-8-sig", newline="") as f:
                f.write(first_line)
            print(f"[INFO] 项目首次初始化私库：复制 schema 从 {seed_csv} → {out_dir}")

    csv_path = out_dir / f"{args.table}.csv"
    headers = CSV_HEADERS[args.table]
    existing = load_existing(csv_path)
    new_rows = EXTRACTORS[args.table](project, parse_chapters(args.chapters))

    added = 0
    final_rows = list(existing)
    for r in new_rows:
        if is_duplicate(r, final_rows): continue
        r["编号"] = next_id(PREFIX[args.table], final_rows)
        for h in headers:
            r.setdefault(h, "")
        final_rows.append(r)
        added += 1

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        for r in final_rows:
            w.writerow({k: r.get(k, "") for k in headers})

    print(f"[OK] {args.table}: +{added} rows (total {len(final_rows)})")
    return 0

if __name__ == "__main__":
    sys.exit(main())
