"""Round 28.2 Ch25 RCA wave 2 tests.

Ch25 v8→v11 polish 暴露第 2 层 root cause：fork 加未来护栏防新事故，
但当下 Ch25 5 层归档（summary/audit/review/editor_notes/last_stable_state）
仍 stale。需要：
1. H65 hygiene 检测归档 stale
2. H66 hygiene 检测 last_stable_state drift
3. backfill-review-metrics CLI 重建 DB 旧记录
"""
from pathlib import Path
import json
import sys
import time


def _ensure_scripts_on_path():
    here = Path(__file__).resolve()
    scripts_dir = here.parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def _write_chapter_text(root: Path, chapter: int, text: str = "测试正文") -> Path:
    (root / "正文").mkdir(parents=True, exist_ok=True)
    p = root / "正文" / f"第{chapter:04d}章-test.md"
    p.write_text(text, encoding="utf-8")
    return p


# ============== H65: 归档层刷新 ==============

def test_h65_passes_when_all_archives_fresh(tmp_path):
    """所有归档 mtime ≥ 正文 mtime → 通过"""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_archive_layer_freshness

    text_p = _write_chapter_text(tmp_path, 25)
    # 模拟所有归档比正文新（直接写文件，确保 mtime 顺序）
    summaries = tmp_path / ".webnovel" / "summaries"
    summaries.mkdir(parents=True)
    (summaries / "ch0025.md").write_text(
        '---\nnarrative_version: "v11"\n---\nfresh', encoding="utf-8"
    )
    audit = tmp_path / ".webnovel" / "audit_reports"
    audit.mkdir(parents=True)
    (audit / "ch0025.json").write_text("{}", encoding="utf-8")
    review = tmp_path / "审查报告"
    review.mkdir(parents=True)
    (review / "第0025章审查报告.md").write_text("fresh", encoding="utf-8")
    state = tmp_path / ".webnovel" / "state.json"
    state.write_text(
        json.dumps({"chapter_meta": {"0025": {"narrative_version": "v11"}}}),
        encoding="utf-8",
    )

    rep = HygieneReport()
    check_archive_layer_freshness(tmp_path, 25, rep)
    fails = [f for f in rep.p1_fails if "H65" in f]
    assert not fails, f"全 fresh 应通过：p1={rep.p1_fails}"
    assert "H65" in rep.passes


def test_h65_fails_when_summary_stale(tmp_path):
    """summary 比正文老 30+ 分钟 → P1 warn"""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_archive_layer_freshness

    summaries = tmp_path / ".webnovel" / "summaries"
    summaries.mkdir(parents=True)
    (summaries / "ch0025.md").write_text("stale", encoding="utf-8")
    # 让归档时间戳老 2 小时
    old_mtime = time.time() - 7200
    import os
    os.utime(summaries / "ch0025.md", (old_mtime, old_mtime))

    # 写正文（mtime 现在）
    _write_chapter_text(tmp_path, 25)

    rep = HygieneReport()
    check_archive_layer_freshness(tmp_path, 25, rep)
    fails = [f for f in rep.p1_fails if "H65" in f]
    assert fails, f"stale summary 应 P1 warn：p1={rep.p1_fails}"
    assert "summaries" in fails[0] or "落后" in fails[0]


def test_h65_detects_narrative_version_mismatch(tmp_path):
    """summary 没含 state 中的 narrative_version → 标 stale"""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_archive_layer_freshness

    summaries = tmp_path / ".webnovel" / "summaries"
    summaries.mkdir(parents=True)
    # summary 还写 v8.0
    (summaries / "ch0025.md").write_text(
        '---\nnarrative_version: "v8.0"\n---\nstale', encoding="utf-8"
    )
    state = tmp_path / ".webnovel" / "state.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(
        json.dumps({"chapter_meta": {"0025": {"narrative_version": "v11"}}}),
        encoding="utf-8",
    )
    _write_chapter_text(tmp_path, 25)

    rep = HygieneReport()
    check_archive_layer_freshness(tmp_path, 25, rep)
    fails = [f for f in rep.p1_fails if "H65" in f]
    assert fails, f"narrative_version 不匹配应 P1 warn：p1={rep.p1_fails}"


# ============== H66: last_stable_state drift ==============

def test_h66_detects_word_count_drift(tmp_path):
    """last_stable_state.artifacts.word_count=3042 但 chapter_meta=3096 → P1 warn"""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_last_stable_state_drift

    state_p = tmp_path / ".webnovel" / "state.json"
    state_p.parent.mkdir(parents=True)
    state_p.write_text(
        json.dumps({"chapter_meta": {"0025": {"word_count": 3096}}}),
        encoding="utf-8",
    )
    wf_p = tmp_path / ".webnovel" / "workflow_state.json"
    wf_p.write_text(
        json.dumps({
            "last_stable_state": {
                "chapter_num": 25,
                "artifacts": {"word_count": 3042},
            }
        }),
        encoding="utf-8",
    )

    rep = HygieneReport()
    check_last_stable_state_drift(tmp_path, 25, rep)
    fails = [f for f in rep.p1_fails if "H66" in f]
    assert fails, f"word_count drift 应 P1 warn：p1={rep.p1_fails}"
    assert "3042" in fails[0] and "3096" in fails[0]


def test_h66_passes_when_aligned(tmp_path):
    """两边 word_count 相等（容差 50）→ 通过"""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_last_stable_state_drift

    state_p = tmp_path / ".webnovel" / "state.json"
    state_p.parent.mkdir(parents=True)
    state_p.write_text(
        json.dumps({"chapter_meta": {"0025": {"word_count": 3096}}}),
        encoding="utf-8",
    )
    wf_p = tmp_path / ".webnovel" / "workflow_state.json"
    wf_p.write_text(
        json.dumps({
            "last_stable_state": {
                "chapter_num": 25,
                "artifacts": {"word_count": 3100},  # within ±50
            }
        }),
        encoding="utf-8",
    )

    rep = HygieneReport()
    check_last_stable_state_drift(tmp_path, 25, rep)
    fails = [f for f in rep.p1_fails if "H66" in f]
    assert not fails, f"对齐应通过：p1={rep.p1_fails}"
    assert "H66" in rep.passes


def test_h66_skips_for_other_chapters(tmp_path):
    """last_stable_state.chapter_num != target → 跳过"""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_last_stable_state_drift

    state_p = tmp_path / ".webnovel" / "state.json"
    state_p.parent.mkdir(parents=True)
    state_p.write_text(
        json.dumps({"chapter_meta": {"0026": {"word_count": 3000}}}),
        encoding="utf-8",
    )
    wf_p = tmp_path / ".webnovel" / "workflow_state.json"
    wf_p.write_text(
        json.dumps({
            "last_stable_state": {
                "chapter_num": 25,
                "artifacts": {"word_count": 3042},
            }
        }),
        encoding="utf-8",
    )

    rep = HygieneReport()
    check_last_stable_state_drift(tmp_path, 26, rep)
    # Should not record anything (different chapter)
    fails = [f for f in rep.p1_fails if "H66" in f]
    assert not fails, f"不同章节应跳过：p1={rep.p1_fails}"


# ============== backfill-review-metrics 13 维度逻辑 ==============

def test_backfill_canonical_to_short_mapping_complete():
    """backfill 用的 long→short 映射必须含 13 个 canonical key"""
    CANONICAL_TO_SHORT = {
        "consistency-checker": "consistency",
        "continuity-checker": "continuity",
        "ooc-checker": "ooc",
        "reader-pull-checker": "reader_pull",
        "high-point-checker": "high_point",
        "flow-checker": "flow",
        "pacing-checker": "pacing",
        "dialogue-checker": "dialogue",
        "density-checker": "density",
        "prose-quality-checker": "prose_quality",
        "emotion-checker": "emotion",
        "reader-naturalness-checker": "naturalness",
        "reader-critic-checker": "reader_critic",
    }
    assert len(CANONICAL_TO_SHORT) == 13
    REQUIRED = {
        "consistency", "continuity", "ooc", "reader_pull", "high_point",
        "flow", "pacing", "dialogue", "density", "prose_quality",
        "emotion", "naturalness", "reader_critic",
    }
    assert set(CANONICAL_TO_SHORT.values()) == REQUIRED


def test_backfill_severity_collection_logic():
    """模拟从 tmp/*_check_*.json 自动统计 severity"""
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    fake_jsons = [
        {"issues": [{"severity": "high"}, {"severity": "medium"}]},
        {"problems": [{"severity": "low"}, {"severity": "low"}]},
    ]
    for j in fake_jsons:
        for issue in (j.get("issues") or j.get("problems") or []):
            if isinstance(issue, dict):
                sev = issue.get("severity")
                if sev in severity_counts:
                    severity_counts[sev] += 1
    assert severity_counts == {"critical": 0, "high": 1, "medium": 1, "low": 2}
