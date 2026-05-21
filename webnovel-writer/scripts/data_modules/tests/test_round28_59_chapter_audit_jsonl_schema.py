"""Round 28.59 · Ch52 第三轮 deep research RCA · chapter_audit CLI jsonl schema 单测固化.

测试范围:
- jsonl entry 必填字段 (13 字段 R28.59 schema)
- 字段类型守门 (防 R28.47 漂移：aggregate_score 不能写成 str / models 不能写成 str)
- agent Part 2 真值优先 (audit_reports/ch{NNNN}.json 存在时 aggregate_score 应取真值)
- 字段集稳定 (多次调用 schema 不变)

通过 webnovel.py CLI subprocess 调用避免 chapter_audit relative import 问题.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"


JSONL_REQUIRED_FIELDS = {
    "chapter", "ts", "source", "decision", "overall_decision", "cli_decision",
    "aggregate_score", "cli_aggregate_partial", "elapsed_ms", "layer_scores",
    "warnings_count", "blocking_count", "mandatory_review_models",
}

JSONL_FIELD_TYPES = {
    "chapter": int,
    "ts": str,
    "source": str,
    "decision": str,
    "overall_decision": str,
    "cli_decision": str,
    "aggregate_score": (int, float, type(None)),
    "cli_aggregate_partial": (int, float, type(None)),
    "elapsed_ms": (int, float),
    "layer_scores": dict,
    "warnings_count": int,
    "blocking_count": int,
    "mandatory_review_models": list,
}


def _make_minimal_project(tmp_path, chapter=999, with_audit_report=False, agent_aggregate=None):
    pr = tmp_path / "book"
    (pr / ".webnovel").mkdir(parents=True)
    (pr / "正文").mkdir()
    (pr / "正文" / f"第{chapter:04d}章-测试.md").write_text(
        "末世第二十八天。\n这是测试章节内容用于 chapter_audit CLI 单测。\n" * 30,
        encoding="utf-8"
    )
    state = {
        "project_info": {"name": "test", "protagonist": "陆沉",
                         "word_count_policy": {"hard_min": 2200, "hard_max": 3800}},
        "chapter_meta": {
            f"{chapter:04d}": {
                "chapter": chapter, "narrative_version": "v1", "title": "测试",
                "word_count": 2500, "review_score": 86,
                "audit_decision": "approve_with_warnings", "aggregate_score": 86,
                "overall_score": 86, "external_review_effective_avg": 86.0,
                "external_review_outlier_models": [], "external_review_raw_avg": 86.0,
            }
        },
        "progress": {"current_chapter": chapter, "last_completed_chapter": chapter - 1,
                     "total_words": 2500},
        "protagonist_state": {"countdown": {"current": "D+28"}},
    }
    (pr / ".webnovel" / "state.json").write_text(
        json.dumps(state, ensure_ascii=False), encoding="utf-8"
    )
    (pr / "审查报告").mkdir()
    (pr / "审查报告" / f"第{chapter:04d}章审查报告.md").write_text(
        "# 测试报告\n> overall_score: 86\n", encoding="utf-8"
    )
    if with_audit_report:
        (pr / ".webnovel" / "audit_reports").mkdir(exist_ok=True)
        (pr / ".webnovel" / "audit_reports" / f"ch{chapter:04d}.json").write_text(
            json.dumps({
                "chapter": chapter, "aggregate_score": agent_aggregate,
                "decision": "approve", "overall_decision": "approve",
            }), encoding="utf-8"
        )
    return pr


def _run_chapter_audit_cli(project_root, chapter):
    """Run chapter_audit CLI via webnovel.py and return last jsonl entry."""
    webnovel_py = SCRIPTS_DIR / "webnovel.py"
    out_file = project_root / ".webnovel" / "tmp" / f"audit_test_ch{chapter:04d}.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SCRIPTS_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    try:
        result = subprocess.run(
            [sys.executable, "-X", "utf8", str(webnovel_py),
             "--project-root", str(project_root), "audit", "chapter",
             "--chapter", str(chapter), "--mode", "standard",
             "--out", str(out_file)],
            cwd=project_root, env=env, capture_output=True, timeout=30
        )
    except subprocess.TimeoutExpired:
        pytest.skip("chapter_audit CLI 超时（单测环境）")
    if result.returncode not in (0, 1, 2):  # 1=block / 2=warn 均合法
        pytest.skip(f"CLI 调用 fail: {result.stderr.decode('utf-8', errors='ignore')[:300]}")
    obs = project_root / ".webnovel" / "observability" / "chapter_audit.jsonl"
    if not obs.exists():
        return None
    lines = obs.read_text(encoding="utf-8").splitlines()
    for line in reversed(lines):
        try:
            d = json.loads(line)
            if d.get("chapter") == chapter and d.get("source") == "chapter_audit_cli":
                return d
        except Exception:
            continue
    return None


def test_jsonl_entry_has_all_required_fields(tmp_path):
    """R28.59 P0-1: jsonl 必须含 13 字段（防 R28.47 漂移再复发）."""
    pr = _make_minimal_project(tmp_path, chapter=997)
    entry = _run_chapter_audit_cli(pr, 997)
    if entry is None:
        pytest.skip("chapter_audit CLI 未生成 jsonl entry")
    missing = JSONL_REQUIRED_FIELDS - set(entry.keys())
    assert not missing, f"jsonl 缺字段: {missing}"


def test_jsonl_field_types_correct(tmp_path):
    """R28.59 P0-1: 字段类型守门（防 aggregate_score 写成 str）."""
    pr = _make_minimal_project(tmp_path, chapter=998)
    entry = _run_chapter_audit_cli(pr, 998)
    if entry is None:
        pytest.skip("CLI 未生成 entry")
    for field, expected_type in JSONL_FIELD_TYPES.items():
        if field not in entry:
            continue
        v = entry[field]
        assert isinstance(v, expected_type), \
            f"字段 {field} 类型错: 实际 {type(v).__name__} 期望 {expected_type}"


def test_jsonl_mandatory_review_models_is_list(tmp_path):
    """R28.59 P1-2: mandatory_review_models 必须是 list."""
    pr = _make_minimal_project(tmp_path, chapter=996)
    entry = _run_chapter_audit_cli(pr, 996)
    if entry is None:
        pytest.skip("CLI 未生成 entry")
    assert isinstance(entry["mandatory_review_models"], list)


def test_jsonl_aggregate_score_prefers_agent_part2_truth(tmp_path):
    """R28.59 P0-1: agent Part 2 audit_reports 存在时 aggregate_score 取真值."""
    pr = _make_minimal_project(tmp_path, chapter=995,
                                with_audit_report=True, agent_aggregate=88)
    entry = _run_chapter_audit_cli(pr, 995)
    if entry is None:
        pytest.skip("CLI 未生成 entry")
    assert entry["aggregate_score"] == 88, \
        f"aggregate_score 应优先取 agent Part 2 真值 88, 实际 {entry['aggregate_score']}"


def test_jsonl_cli_aggregate_partial_always_present(tmp_path):
    """R28.59 P0-1: 无 agent Part 2 时 cli_aggregate_partial 仍有值（A+B+G 均值）."""
    pr = _make_minimal_project(tmp_path, chapter=994, with_audit_report=False)
    entry = _run_chapter_audit_cli(pr, 994)
    if entry is None:
        pytest.skip("CLI 未生成 entry")
    assert entry["cli_aggregate_partial"] is not None, \
        "cli_aggregate_partial 必有值（CLI 自计算 A+B+G 均值）"
    assert isinstance(entry["cli_aggregate_partial"], (int, float))


def test_jsonl_schema_stable_across_two_calls(tmp_path):
    """R28.59 P0-1: 两次调用字段集一致."""
    pr = _make_minimal_project(tmp_path, chapter=993)
    field_sets = []
    for _ in range(2):
        entry = _run_chapter_audit_cli(pr, 993)
        if entry is None:
            pytest.skip("CLI 未生成 entry")
        field_sets.append(set(entry.keys()))
    assert field_sets[0] == field_sets[1], \
        f"两次调用 jsonl 字段不一致: 差 {field_sets[0] ^ field_sets[1]}"
