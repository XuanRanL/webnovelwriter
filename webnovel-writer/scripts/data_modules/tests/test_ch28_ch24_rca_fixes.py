"""Round 28 Ch24 RCA H58/H59/H61 new guards tests.

Ch24 deep research exposed 5 root causes:
1. checker_scores vs review_metrics divergence (9 drifts) -> H58
2. polish silently changed 7 scores without audit trail -> H59
3. progress.last_completed_chapter stuck across 4 chapters -> H61
4. H18 did not validate 13 canonical completeness -> H18 upgrade
5. NaYi (na yi X) warn 10 / block 18 too lax -> tightened to block 12
"""
from pathlib import Path
import json
import sqlite3
import sys


def _ensure_scripts_on_path():
    here = Path(__file__).resolve()
    scripts_dir = here.parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def _write_state_with_review_metrics(root, checker_scores, dimension_scores, recheck=None):
    (root / ".webnovel").mkdir(parents=True, exist_ok=True)
    meta_entry = {
        "chapter": 1,
        "title": "t",
        "word_count": 2500,
        "summary": "s",
        "hook_strength": "strong",
        "scene_count": 5,
        "key_beats": ["b"],
        "characters": ["c"],
        "locations": ["l"],
        "created_at": "2026-01-01",
        "updated_at": "2026-01-01",
        "protagonist_state": "s",
        "location_current": "l",
        "power_realm": "r",
        "golden_finger_level": 0,
        "time_anchor": "t",
        "end_state": "e",
        "foreshadowing_planted": [],
        "foreshadowing_paid": [],
        "strand_dominant": "quest",
        "review_score": 90,
        "checker_scores": checker_scores,
        "allusions_used": [],
    }
    if recheck:
        meta_entry["post_polish_recheck"] = recheck
    state = {"chapter_meta": {"0001": meta_entry}, "last_completed_chapter": 1, "current_chapter": 1}
    (root / ".webnovel" / "state.json").write_text(
        json.dumps(state, ensure_ascii=False), encoding="utf-8"
    )
    db = root / ".webnovel" / "index.db"
    conn = sqlite3.connect(str(db))
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS review_metrics ("
        "start_chapter INTEGER, end_chapter INTEGER, "
        "overall_score REAL DEFAULT 0, "
        "dimension_scores TEXT, severity_counts TEXT, critical_issues TEXT, "
        "report_file TEXT, notes TEXT, "
        "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
        "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )
    cur.execute(
        "INSERT INTO review_metrics (start_chapter, end_chapter, overall_score, dimension_scores) VALUES (?, ?, ?, ?)",
        (1, 1, 90.0, json.dumps(dimension_scores)),
    )
    conn.commit()
    conn.close()


def _all_canonical_dim_scores(value=90):
    return {
        "naturalness": value, "reader_critic": value, "consistency": value,
        "continuity": value, "ooc": value, "reader_pull": value,
        "high_point": value, "flow": value, "pacing": value,
        "dialogue": value, "density": value, "prose_quality": value, "emotion": value,
    }


def test_h58_consistency_passes_when_aligned(tmp_path):
    _ensure_scripts_on_path()
    import hygiene_check as hc
    from data_modules.chapter_audit import CHECKER_NAMES

    cs = {n: 90 for n in CHECKER_NAMES}
    cs["overall"] = 90
    ds = _all_canonical_dim_scores(90)
    _write_state_with_review_metrics(tmp_path, cs, ds)
    rep = hc.HygieneReport()
    hc.check_checker_scores_review_metrics_consistency(tmp_path, 1, rep)
    assert "H58" in rep.passes, "Expected H58 pass: " + str(rep.p0_fails + rep.p1_fails)


def test_h58_drift_fails(tmp_path):
    """Ch24 actual: prose-quality chapter_meta=89 vs review_metrics=75, drift 14."""
    _ensure_scripts_on_path()
    import hygiene_check as hc
    from data_modules.chapter_audit import CHECKER_NAMES

    cs = {n: 90 for n in CHECKER_NAMES}
    cs["prose-quality-checker"] = 89
    cs["overall"] = 90
    ds = _all_canonical_dim_scores(90)
    ds["prose_quality"] = 75
    _write_state_with_review_metrics(tmp_path, cs, ds)
    rep = hc.HygieneReport()
    hc.check_checker_scores_review_metrics_consistency(tmp_path, 1, rep)
    assert any("H58" in f for f in rep.p1_fails), \
        "Expected H58 P1 fail, passes=" + str(rep.passes)


def test_h58_recheck_whitelist(tmp_path):
    """post_polish_recheck checkers may diverge legitimately."""
    _ensure_scripts_on_path()
    import hygiene_check as hc
    from data_modules.chapter_audit import CHECKER_NAMES

    cs = {n: 90 for n in CHECKER_NAMES}
    cs["reader-critic-checker"] = 79
    cs["high-point-checker"] = 91
    cs["overall"] = 90
    ds = _all_canonical_dim_scores(90)
    ds["reader_critic"] = 71
    ds["high_point"] = 74
    recheck = {
        "reader-critic-checker": {"before": 71, "after": 79, "delta": 8, "reason": "polish"},
        "high-point-checker": {"before": 74, "after": 91, "delta": 17, "reason": "polish"},
    }
    _write_state_with_review_metrics(tmp_path, cs, ds, recheck=recheck)
    rep = hc.HygieneReport()
    hc.check_checker_scores_review_metrics_consistency(tmp_path, 1, rep)
    assert "H58" in rep.passes, "Expected H58 pass with recheck whitelist, fails=" + str(rep.p1_fails)


def test_h59_silent_change_fails(tmp_path):
    """Ch24 case: prose-quality silently 75 -> 89, no recheck record."""
    _ensure_scripts_on_path()
    import hygiene_check as hc
    from data_modules.chapter_audit import CHECKER_NAMES

    cs = {n: 90 for n in CHECKER_NAMES}
    cs["prose-quality-checker"] = 89
    cs["overall"] = 90
    ds = _all_canonical_dim_scores(90)
    ds["prose_quality"] = 75
    _write_state_with_review_metrics(tmp_path, cs, ds)
    rep = hc.HygieneReport()
    hc.check_silent_score_change(tmp_path, 1, rep)
    assert any("H59" in f for f in rep.p1_fails), \
        "Expected H59 P1 fail, passes=" + str(rep.passes)


def test_h61_progress_drift_fails(tmp_path):
    """Ch24: wrote to 24 but last_completed_chapter still 20."""
    _ensure_scripts_on_path()
    import hygiene_check as hc

    (tmp_path / ".webnovel").mkdir(parents=True, exist_ok=True)
    state = {
        "chapter_meta": {f"{i:04d}": {"word_count": 2500} for i in range(1, 25)},
        "last_completed_chapter": 20,
        "current_chapter": 20,
    }
    (tmp_path / ".webnovel" / "state.json").write_text(
        json.dumps(state, ensure_ascii=False), encoding="utf-8"
    )
    rep = hc.HygieneReport()
    hc.check_progress_chapter_consistency(tmp_path, 24, rep)
    assert any("H61" in f for f in rep.p1_fails), \
        "Expected H61 P1 fail, passes=" + str(rep.passes)


def test_h61_progress_aligned_passes(tmp_path):
    _ensure_scripts_on_path()
    import hygiene_check as hc

    (tmp_path / ".webnovel").mkdir(parents=True, exist_ok=True)
    state = {
        "chapter_meta": {f"{i:04d}": {"word_count": 2500} for i in range(1, 25)},
        "last_completed_chapter": 24,
        "current_chapter": 24,
    }
    (tmp_path / ".webnovel" / "state.json").write_text(
        json.dumps(state, ensure_ascii=False), encoding="utf-8"
    )
    rep = hc.HygieneReport()
    hc.check_progress_chapter_consistency(tmp_path, 24, rep)
    assert "H61" in rep.passes
