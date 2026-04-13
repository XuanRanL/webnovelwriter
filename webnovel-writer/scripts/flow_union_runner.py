"""
Phase IV: reader_flow N=3 重跑 + issue union 聚合器

用途：对"首章/规则揭示章/反派首露章"等关键章节，对 reader_flow 维度做 N=3 重复跑，
取跨 run 的 issue **union**（并集）而非 intersection，以对冲 LLM 偷懒。

调用链：
  1. 对每个 run i ∈ [1..N]：调 external_review.py --mode dimensions --models <核心3>
     但仅保留 reader_flow 维度输出
  2. 合并 N 次产物的 issue 列表（quote 归一化模糊去重）
  3. 聚合规则：
     - 同一 quote 在 ≥ 2 个 run 中命中 → severity = max(那些命中的 severity)
     - 只在 1 个 run 命中的 high → 降级 medium
  4. 输出合并报告 + 各 run 原始 JSON

用法：
  python flow_union_runner.py --project-root <...> --chapter N --runs 3 \
    --models glm,kimi,qwen-plus --out <output.json>

触发条件（由 SKILL 层决定是否调用）：
  - 首章（chapter_num == 1）
  - 规则揭示章（在章纲中标注 is_rule_reveal=true）
  - 反派首露章（villain_first_appear=true）
  - 其他可手动触发
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


SCRIPT_DIR = Path(__file__).parent.resolve()


def norm_quote(s: str) -> str:
    """Normalize quote for fuzzy match: strip all whitespace, trim to 15 chars."""
    if not s:
        return ""
    return "".join(s.split())[:15]


def severity_rank(s: str) -> int:
    return {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(s, 0)


def rank_to_severity(r: int) -> str:
    return {4: "critical", 3: "high", 2: "medium", 1: "low"}.get(r, "low")


def run_one_iteration(project_root: Path, chapter: int, models: str, run_idx: int) -> dict:
    """Run external_review.py once for reader_flow only."""
    out_tmp = project_root / ".webnovel" / "tmp" / f"flow_union_run{run_idx}_ch{chapter:04d}.json"
    out_tmp.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "-X", "utf8",
        str(SCRIPT_DIR / "external_review.py"),
        "--project-root", str(project_root),
        "--chapter", str(chapter),
        "--mode", "dimensions",
        "--model-key", "all",
        "--models", models,
    ]

    t0 = time.time()
    result = {"run_idx": run_idx, "cmd": cmd, "elapsed_s": 0, "reader_flow": []}
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900, encoding="utf-8", errors="replace")
        result["elapsed_s"] = round(time.time() - t0, 1)
        result["returncode"] = proc.returncode
        if proc.returncode != 0:
            result["error"] = f"returncode={proc.returncode} stderr={proc.stderr[:500]}"
            return result

        # Parse external_review_{model}_ch{NNNN}.json outputs (each model has own file)
        model_list = [m.strip() for m in models.split(",") if m.strip()]
        for m in model_list:
            per_model = project_root / ".webnovel" / "tmp" / f"external_review_{m}_ch{chapter:04d}.json"
            if not per_model.exists():
                continue
            with per_model.open("r", encoding="utf-8") as f:
                mdata = json.load(f)
            for dr in mdata.get("dimension_reports", []):
                if dr.get("dimension") == "reader_flow":
                    for issue in dr.get("issues", []):
                        issue["_model"] = m
                        issue["_run_idx"] = run_idx
                        issue["_score"] = dr.get("score")
                        result["reader_flow"].append(issue)
    except subprocess.TimeoutExpired:
        result["error"] = "timeout_900s"
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"

    return result


def aggregate_union(runs_data: list, chapter_text: str) -> dict:
    """Aggregate N runs' reader_flow issues into union with severity arbitration."""
    chapter_compact = "".join(chapter_text.split())

    # Bucket by norm_quote
    bucket = {}  # key: norm_quote, value: list of (run_idx, model, issue)
    for run_data in runs_data:
        for issue in run_data.get("reader_flow", []):
            quote = issue.get("quote", "") or ""
            key = norm_quote(quote)
            if not key:
                continue
            # Validate quote in chapter (compact match)
            if "".join(quote.split()) not in chapter_compact:
                issue["_halluc"] = True
            bucket.setdefault(key, []).append(issue)

    # Arbitration rules
    consensus_issues = []  # ≥2 runs OR ≥2 models
    solo_demoted = []      # single run + single model, high → medium
    advisory = []          # single + low/medium, keep as-is

    for key, issues in bucket.items():
        run_set = set(i.get("_run_idx") for i in issues)
        model_set = set(i.get("_model") for i in issues)
        max_sev = max(severity_rank(i.get("severity", "low")) for i in issues)

        rep = dict(issues[0])  # first as representative
        rep["_hits_runs"] = sorted(run_set)
        rep["_hits_models"] = sorted(model_set)
        rep["_hit_count"] = len(issues)
        rep["_original_severity"] = rep.get("severity")

        consensus = (len(run_set) >= 2) or (len(model_set) >= 2)

        if consensus:
            rep["severity"] = rank_to_severity(max_sev)
            rep["_arbitration"] = "consensus"
            consensus_issues.append(rep)
        elif severity_rank(rep.get("severity", "low")) >= 3:  # solo high
            rep["severity"] = "medium"
            rep["_arbitration"] = "solo_high_demoted"
            solo_demoted.append(rep)
        else:
            rep["_arbitration"] = "advisory"
            advisory.append(rep)

    all_issues = consensus_issues + solo_demoted + advisory
    sev_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for i in all_issues:
        s = i.get("severity")
        if s in sev_counts:
            sev_counts[s] += 1

    # Median score across all (run × model) combinations
    import statistics
    scores = []
    for run_data in runs_data:
        seen = set()
        for issue in run_data.get("reader_flow", []):
            score = issue.get("_score")
            key = (run_data["run_idx"], issue.get("_model"))
            if score is not None and key not in seen:
                scores.append(score)
                seen.add(key)

    return {
        "chapter_compact_len": len(chapter_compact),
        "runs_count": len(runs_data),
        "total_unique_issues": len(all_issues),
        "consensus_count": len(consensus_issues),
        "solo_demoted_count": len(solo_demoted),
        "advisory_count": len(advisory),
        "severity_counts_union": sev_counts,
        "score_median_over_runs_models": round(statistics.median(scores), 1) if scores else None,
        "score_samples_count": len(scores),
        "consensus_issues": consensus_issues,
        "solo_demoted_issues": solo_demoted,
        "advisory_issues": advisory,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", type=str, required=True)
    ap.add_argument("--chapter", type=int, required=True)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--models", type=str, default="glm,kimi,qwen-plus")
    ap.add_argument("--chapter-file", type=str, help="Explicit chapter file path (optional)")
    ap.add_argument("--out", type=str, required=True)
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve()

    # Resolve chapter file
    if args.chapter_file:
        chapter_file = Path(args.chapter_file)
    else:
        import glob
        pat = str(project_root / "正文" / f"第{args.chapter:04d}章*.md")
        matches = glob.glob(pat)
        if not matches:
            print(json.dumps({"error": f"no chapter file for ch{args.chapter}"}, ensure_ascii=False))
            sys.exit(1)
        chapter_file = Path(matches[0])

    chapter_text = chapter_file.read_text(encoding="utf-8")

    print(f"[flow-union] project={project_root} chapter={args.chapter} runs={args.runs} models={args.models}", file=sys.stderr)

    runs_data = []
    for i in range(1, args.runs + 1):
        print(f"[flow-union] starting run {i}/{args.runs} ...", file=sys.stderr)
        r = run_one_iteration(project_root, args.chapter, args.models, i)
        runs_data.append(r)
        rf_count = len(r.get("reader_flow", []))
        err = r.get("error", "")
        print(f"[flow-union] run {i} done: reader_flow={rf_count} elapsed={r['elapsed_s']}s err={err}", file=sys.stderr)

    agg = aggregate_union(runs_data, chapter_text)

    out = {
        "chapter": args.chapter,
        "chapter_file": str(chapter_file),
        "runs": args.runs,
        "models": args.models.split(","),
        "runs_data": runs_data,
        "aggregation": agg,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[flow-union] DONE output={out_path}", file=sys.stderr)

    print(json.dumps({
        "chapter": args.chapter,
        "runs": args.runs,
        "total_unique_issues": agg["total_unique_issues"],
        "consensus_count": agg["consensus_count"],
        "solo_demoted_count": agg["solo_demoted_count"],
        "advisory_count": agg["advisory_count"],
        "severity_counts_union": agg["severity_counts_union"],
        "score_median": agg["score_median_over_runs_models"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
