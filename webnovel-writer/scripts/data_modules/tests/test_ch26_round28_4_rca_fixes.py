"""Round 28.4 · Ch26 RCA · 12 个根因新护栏与修复测试.

Ch26 deep research exposed:
- P0-1: data-agent 静默改 11 处 checker 分数（emotion 91→81 / reader-pull 94→83 等）
- P0-2: chapter_meta 缺 7 个核心字段（dialogue_ratio/signature_density/etc）
- P0-3: chapter_type 误标导致 word_count_hard_min 矛盾
- P0-4: high_point_check_ch0026.json 是非法 JSON（ASCII " 在字符串值里）
- P1-5: workflow stale FP 报 "241 min" 实际只过了 50 秒
- P1-6: audit A1 读错路径（snapshot.payload.contract 永远空）
- P1-7: 手动 Step 4 polish 后 narrative_version 不 bump
- P1-8: hook_close 别名 "危机钩" 被 CLI reject
- P1-9: 单模型补跑后 external aggregate 不刷新
- P1-10: review_score=82.0 vs overall_score=82 类型漂移
- P1-11: Step K markdown 推给主 agent
- P1-12: Step 4.5 step-id 不在白名单
"""
from pathlib import Path
import json
import sys


def _ensure_scripts_on_path():
    here = Path(__file__).resolve()
    scripts_dir = here.parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def _setup_state(root, meta=None):
    (root / ".webnovel" / "tmp").mkdir(parents=True, exist_ok=True)
    state = {"chapter_meta": {"0026": meta or {}}, "progress": {}}
    (root / ".webnovel" / "state.json").write_text(
        json.dumps(state, ensure_ascii=False), encoding="utf-8"
    )


def _write_disk_json(root, prefix, score):
    p = root / ".webnovel" / "tmp" / f"{prefix}_ch0026.json"
    p.write_text(json.dumps({"score": score}, ensure_ascii=False), encoding="utf-8")


# ---------- H68: disk-state checker score consistency ----------

def test_h68_passes_when_disk_matches_state(tmp_path):
    _ensure_scripts_on_path()
    import hygiene_check as hc
    meta = {
        "checker_scores": {
            "consistency-checker": 88, "continuity-checker": 87,
            "ooc-checker": 88, "reader-pull-checker": 94,
            "high-point-checker": 82, "flow-checker": 76,
            "pacing-checker": 82, "dialogue-checker": 84,
            "density-checker": 82, "prose-quality-checker": 86,
            "emotion-checker": 91, "reader-naturalness-checker": 84,
            "reader-critic-checker": 80,
        }
    }
    _setup_state(tmp_path, meta)
    for prefix, score in [
        ("consistency", 88), ("continuity", 87), ("ooc", 88),
        ("reader_pull", 94), ("high_point", 82), ("flow", 76),
        ("pacing", 82), ("dialogue", 84), ("density", 82),
        ("prose_quality", 86), ("emotion", 91),
        ("reader_naturalness", 84), ("reader_critic", 80),
    ]:
        _write_disk_json(tmp_path, prefix, score)
    rep = hc.HygieneReport()
    hc.check_disk_state_score_consistency(tmp_path, 26, rep)
    assert "H68" in rep.passes


def test_h68_blocks_on_drift(tmp_path):
    """Ch26 实测: emotion disk=91 vs state=81 (Δ=10)."""
    _ensure_scripts_on_path()
    import hygiene_check as hc
    meta = {
        "checker_scores": {
            "emotion-checker": 81, "reader-pull-checker": 83,
        }
    }
    _setup_state(tmp_path, meta)
    _write_disk_json(tmp_path, "emotion", 91)
    _write_disk_json(tmp_path, "reader_pull", 94)
    rep = hc.HygieneReport()
    hc.check_disk_state_score_consistency(tmp_path, 26, rep)
    assert any("H68" in f for f in rep.p0_fails)


def test_h68_skips_recheck_whitelist(tmp_path):
    """post_polish_recheck 中的 checker 跳过（Step 4.5 合法改分）."""
    _ensure_scripts_on_path()
    import hygiene_check as hc
    meta = {
        "checker_scores": {"reader-critic-checker": 80, "emotion-checker": 91},
        "post_polish_recheck": {
            "reader-critic-checker": {"before": 72, "after": 80, "delta": 8},
        },
    }
    _setup_state(tmp_path, meta)
    _write_disk_json(tmp_path, "reader_critic", 72)  # disk 是 pre-polish 的 72
    _write_disk_json(tmp_path, "emotion", 91)
    rep = hc.HygieneReport()
    hc.check_disk_state_score_consistency(tmp_path, 26, rep)
    # H68 should pass because reader-critic is whitelisted via recheck
    assert "H68" in rep.passes


# ---------- H69: extended chapter_meta fields ----------

def test_h69_warns_on_missing_fields(tmp_path):
    _ensure_scripts_on_path()
    import hygiene_check as hc
    meta = {
        "chapter": 26, "title": "t", "word_count": 3063,
        # intentionally missing total_words / dialogue_ratio etc
    }
    _setup_state(tmp_path, meta)
    rep = hc.HygieneReport()
    hc.check_extended_meta_fields(tmp_path, 26, rep)
    assert any("H69" in f for f in rep.p1_fails)


def test_h69_passes_with_all_extended(tmp_path):
    _ensure_scripts_on_path()
    import hygiene_check as hc
    meta = {
        "total_words": 74041, "dialogue_ratio": 0.21,
        "signature_density": 0.012, "naturalness_score": 84,
        "naturalness_verdict": "POLISH_NEEDED",
        "reader_critic_score": 80, "reader_critic_verdict": "yes",
        "reader_thrill_score": 56, "external_avg": 88.2,
        "hook_close": {"primary_type": "动作钩", "strength": 91},
    }
    _setup_state(tmp_path, meta)
    rep = hc.HygieneReport()
    hc.check_extended_meta_fields(tmp_path, 26, rep)
    assert "H69" in rep.passes


# ---------- H70: chapter_type word_count match ----------

def test_h70_warns_on_chapter_type_mismatch(tmp_path):
    """Ch26 实测：context_contract 标 战斗章 (3200-3800) 但 word_count=3063."""
    _ensure_scripts_on_path()
    import hygiene_check as hc
    (tmp_path / ".webnovel" / "context").mkdir(parents=True)
    (tmp_path / ".webnovel" / "context" / "ch0026_context.json").write_text(
        json.dumps({
            "context_contract": {
                "chapter_type": "战斗章/高潮章延续",
                "word_count_hard_min": 3200, "word_count_hard_max": 3800,
            }
        }, ensure_ascii=False), encoding="utf-8"
    )
    _setup_state(tmp_path, {"word_count": 3063})
    rep = hc.HygieneReport()
    hc.check_chapter_type_word_count_match(tmp_path, 26, rep)
    assert any("H70" in f for f in rep.p1_fails)


def test_h70_passes_when_word_count_in_range(tmp_path):
    _ensure_scripts_on_path()
    import hygiene_check as hc
    (tmp_path / ".webnovel" / "context").mkdir(parents=True)
    (tmp_path / ".webnovel" / "context" / "ch0026_context.json").write_text(
        json.dumps({
            "context_contract": {
                "chapter_type": "推进章/日常章",
                "word_count_hard_min": 2700, "word_count_hard_max": 3300,
            }
        }, ensure_ascii=False), encoding="utf-8"
    )
    _setup_state(tmp_path, {"word_count": 3063})
    rep = hc.HygieneReport()
    hc.check_chapter_type_word_count_match(tmp_path, 26, rep)
    assert "H70" in rep.passes


# ---------- H71: disk JSON validity ----------

def test_h71_blocks_on_invalid_json(tmp_path):
    """Ch26 实测: high_point JSON 含 ASCII " 双引号撞车."""
    _ensure_scripts_on_path()
    import hygiene_check as hc
    _setup_state(tmp_path)
    bad = tmp_path / ".webnovel" / "tmp" / "high_point_check_ch0026.json"
    bad.write_text(
        '{"score": 82, "issues": [{"suggestion": "形成"余波"——例如..."}]}',
        encoding="utf-8",
    )
    rep = hc.HygieneReport()
    hc.check_disk_json_validity(tmp_path, 26, rep)
    assert any("H71" in f for f in rep.p0_fails)


def test_h71_passes_on_valid_json(tmp_path):
    _ensure_scripts_on_path()
    import hygiene_check as hc
    _setup_state(tmp_path)
    _write_disk_json(tmp_path, "consistency", 88)
    rep = hc.HygieneReport()
    hc.check_disk_json_validity(tmp_path, 26, rep)
    assert "H71" in rep.passes


# ---------- H72: narrative_version bump on polish ----------

def test_h72_warns_when_polished_but_v1(tmp_path):
    _ensure_scripts_on_path()
    import hygiene_check as hc
    _setup_state(tmp_path, {"narrative_version": "v1"})
    ws = {"history": [{
        "chapter": 26,
        "completed_steps": [
            {"id": "Step 4", "name": "Polish - Fix Critical+High Issues",
             "artifacts": {"fixes": ["H1", "H2"]}}
        ],
    }]}
    (tmp_path / ".webnovel" / "workflow_state.json").write_text(
        json.dumps(ws, ensure_ascii=False), encoding="utf-8"
    )
    rep = hc.HygieneReport()
    hc.check_polish_narrative_version_bump(tmp_path, 26, rep)
    assert any("H72" in f for f in rep.p1_fails)


def test_h72_passes_after_bump(tmp_path):
    _ensure_scripts_on_path()
    import hygiene_check as hc
    _setup_state(tmp_path, {"narrative_version": "v2"})
    ws = {"history": [{
        "chapter": 26,
        "completed_steps": [
            {"id": "Step 4", "name": "Polish - Fix Critical+High Issues",
             "artifacts": {"fixes": ["H1", "H2"]}}
        ],
    }]}
    (tmp_path / ".webnovel" / "workflow_state.json").write_text(
        json.dumps(ws, ensure_ascii=False), encoding="utf-8"
    )
    rep = hc.HygieneReport()
    hc.check_polish_narrative_version_bump(tmp_path, 26, rep)
    assert "H72" in rep.passes


# ---------- H73: stale failure_reason clock skew ----------

def test_h73_detects_clock_skew(tmp_path):
    """Ch26 实测: failure_reason 报 '241 min' 实际过了 50 秒."""
    _ensure_scripts_on_path()
    import hygiene_check as hc
    ws = {"history": [{
        "chapter": 26,
        "completed_steps": [],
        "failed_steps": [{
            "id": "Step 5",
            "started_at": "2026-05-03T13:25:02",
            "failed_at": "2026-05-03T13:25:52",
            "failure_reason": "Step 5 stale: process died after 241 min, restarting data-agent",
        }],
    }]}
    (tmp_path / ".webnovel").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".webnovel" / "workflow_state.json").write_text(
        json.dumps(ws, ensure_ascii=False), encoding="utf-8"
    )
    rep = hc.HygieneReport()
    hc.check_stale_failure_reason_consistency(tmp_path, 26, rep)
    assert any("H73" in f for f in rep.p2_fails)


# ---------- mirror-disk-scores CLI ----------

def test_mirror_disk_scores_cli_propagates_disk(tmp_path):
    """Verify --mirror-disk-scores reads disk JSON and writes state.checker_scores."""
    _ensure_scripts_on_path()
    import sys as _sys
    from data_modules import state_manager as sm

    state = {
        "chapter_meta": {"0026": {
            "checker_scores": {
                "emotion-checker": 81,
                "reader-pull-checker": 83,
            }
        }}
    }
    (tmp_path / ".webnovel" / "tmp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".webnovel" / "state.json").write_text(
        json.dumps(state, ensure_ascii=False), encoding="utf-8"
    )
    _write_disk_json(tmp_path, "emotion", 91)
    _write_disk_json(tmp_path, "reader_pull", 94)

    old_argv = _sys.argv[:]
    try:
        _sys.argv = [
            "state_manager", "--project-root", str(tmp_path),
            "update", "--mirror-disk-scores", '{"chapter":26}',
        ]
        try:
            sm.main()
        except SystemExit:
            pass
    finally:
        _sys.argv = old_argv

    new_state = json.loads((tmp_path / ".webnovel" / "state.json").read_text(encoding="utf-8"))
    cs = new_state["chapter_meta"]["0026"]["checker_scores"]
    assert cs["emotion-checker"] == 91, f"emotion not mirrored: {cs}"
    assert cs["reader-pull-checker"] == 94, f"reader-pull not mirrored: {cs}"


# ---------- bump-narrative-version CLI ----------

def test_bump_narrative_version_cli(tmp_path):
    _ensure_scripts_on_path()
    import sys as _sys
    from data_modules import state_manager as sm

    state = {"chapter_meta": {"0026": {"narrative_version": "v1"}}}
    (tmp_path / ".webnovel").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".webnovel" / "state.json").write_text(
        json.dumps(state, ensure_ascii=False), encoding="utf-8"
    )
    old_argv = _sys.argv[:]
    try:
        _sys.argv = [
            "state_manager", "--project-root", str(tmp_path),
            "update", "--bump-narrative-version",
            '{"chapter":26,"reason":"Step 4 polish"}',
        ]
        try:
            sm.main()
        except SystemExit:
            pass
    finally:
        _sys.argv = old_argv

    new_state = json.loads((tmp_path / ".webnovel" / "state.json").read_text(encoding="utf-8"))
    entry = new_state["chapter_meta"]["0026"]
    assert entry["narrative_version"] == "v2"
    polog = entry.get("polish_log", [])
    assert len(polog) == 1
    assert polog[0]["from_version"] == "v1"
    assert polog[0]["to_version"] == "v2"
    assert polog[0]["reason"] == "Step 4 polish"


# ---------- Hook taxonomy alias ----------

def test_hook_close_alias_危机钩_maps_to_动作钩(tmp_path):
    """Ch26: reader-pull-checker 输出 '危机钩'，CLI 应自动映射到 '动作钩'."""
    _ensure_scripts_on_path()
    import sys as _sys
    from data_modules import state_manager as sm

    (tmp_path / ".webnovel").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".webnovel" / "state.json").write_text(
        json.dumps({"chapter_meta": {}}, ensure_ascii=False), encoding="utf-8"
    )
    old_argv = _sys.argv[:]
    try:
        _sys.argv = [
            "state_manager", "--project-root", str(tmp_path),
            "update", "--set-hook-close",
            '{"chapter":26,"primary":"危机钩","strength":91,"text":"今晚不开门。"}',
        ]
        try:
            sm.main()
        except SystemExit:
            pass
    finally:
        _sys.argv = old_argv

    new_state = json.loads((tmp_path / ".webnovel" / "state.json").read_text(encoding="utf-8"))
    hc = new_state["chapter_meta"]["0026"]["hook_close"]
    assert hc["primary_type"] == "动作钩", f"alias mapping failed: {hc}"


# ---------- review_score / overall_score type unification ----------

def test_review_score_int_unification(tmp_path):
    """Round 28.4: review_score=82.0 (float) -> 82 (int) in _backfill."""
    _ensure_scripts_on_path()
    from data_modules import state_manager as sm
    from data_modules.config import get_config

    (tmp_path / ".webnovel").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".webnovel" / "state.json").write_text(
        json.dumps({"chapter_meta": {}}, ensure_ascii=False), encoding="utf-8"
    )
    cfg = get_config(project_root=str(tmp_path))
    mgr = sm.StateManager(cfg, enable_sqlite_sync=False)
    chapter_meta = {
        "review_score": 82.0,
        "overall_score": 82.0,
        "word_count": 3063,
    }
    mgr._backfill_chapter_meta(26, chapter_meta)
    assert isinstance(chapter_meta["review_score"], int), \
        f"review_score type: {type(chapter_meta['review_score'])}"
    assert chapter_meta["review_score"] == 82
    assert isinstance(chapter_meta["overall_score"], int)
    assert chapter_meta["overall_score"] == 82


# ---------- external aggregate refresh ----------

def test_refresh_external_aggregate_after_single_model(tmp_path):
    """Round 28.4 P1-9: 单模型补跑后 aggregate 必须刷新."""
    _ensure_scripts_on_path()
    import external_review as er

    tmp_dir = tmp_path / ".webnovel" / "tmp"
    tmp_dir.mkdir(parents=True)
    # 13 模型成功 + 1 模型失败 + 1 模型刚补跑
    for i, mk in enumerate(["doubao-pro", "glm-5", "kimi-k2.6", "gemini-3.1-pro",
                             "gpt-5.5", "minimax-m2.5", "deepseek-v3.2-thinking",
                             "doubao-seed-2.0-lite", "glm-4.7", "glm-5.1",
                             "mimo-v2.5-pro", "minimax-m2.7-hs", "kimi-k2.5"]):
        (tmp_dir / f"external_review_{mk}_ch0026.json").write_text(json.dumps({
            "overall_score": 88 + (i % 5), "pass": True,
            "dimension_reports": [{"status": "ok", "score": 88}] * 13,
        }), encoding="utf-8")
    # qwen3.6-plus failed
    (tmp_dir / "external_review_qwen3.6-plus_ch0026.json").write_text(json.dumps({
        "error": "http_503"
    }), encoding="utf-8")
    # deepseek-v4-flash 后台补跑成功
    (tmp_dir / "external_review_deepseek-v4-flash_ch0026.json").write_text(json.dumps({
        "overall_score": 90.5, "pass": True,
        "dimension_reports": [{"status": "ok", "score": 90}] * 13,
    }), encoding="utf-8")

    result = er.refresh_external_aggregate(tmp_path, 26)
    assert result is not None
    assert result["models_ok_count"] == 14
    assert result["coverage_status"] == "healthy"  # >= 10
    assert result["external_avg"] is not None
    assert "deepseek-v4-flash" in result["models_ok"]
    assert "qwen3.6-plus" in result["models_failed"]
    # aggregate 文件已写盘
    agg = tmp_dir / "external_review_ch0026.json"
    assert agg.exists()
    saved = json.loads(agg.read_text(encoding="utf-8"))
    assert saved["models_ok_count"] == 14
