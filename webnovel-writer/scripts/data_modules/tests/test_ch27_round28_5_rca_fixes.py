"""Round 28.5 · Ch27 RCA · external_avg + H69 持续缺失字段根治测试.

Ch27 deep research exposed:
- P0-1: external_avg 长期陈旧（Step 3.5 完成时 12/15 → 88，aggregate 后续刷新到 87.4 但 chapter_meta 永不更新）
- P0-2: H69 4 个扩展字段持续缺失（total_words/dialogue_ratio/signature_density/reader_thrill_score）
       根因：CLI whitelist 不含这 4 字段，data-agent process-chapter 写入失败时无法 fallback
- P0-3: reader_thrill_ch0027.json 含未转义 ASCII " 触发 H71（已被 H71 现有规则覆盖）
- P0-4: review_metrics SQLite vs chapter_meta 长期 13 项漂移（mirror-disk-scores 不刷新 SQLite）

新增护栏：
- mirror-disk-scores 同时刷新 external_avg / models_ok / models_count（从 aggregate 文件）
- CHAPTER_META_FIELD_WHITELIST 加入 7 个字段：external_avg / external_models_ok / external_models_count
  / total_words / dialogue_ratio / signature_density / reader_thrill_score
"""
from pathlib import Path
import json
import sys


def _ensure_scripts_on_path():
    here = Path(__file__).resolve()
    scripts_dir = here.parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def _setup_state(root, ch=27, meta=None):
    (root / ".webnovel" / "tmp").mkdir(parents=True, exist_ok=True)
    pad = f"{ch:04d}"
    state = {"chapter_meta": {pad: meta or {}}, "progress": {}}
    (root / ".webnovel" / "state.json").write_text(
        json.dumps(state, ensure_ascii=False), encoding="utf-8"
    )


def _write_disk_json(root, prefix, score, ch=27):
    pad = f"{ch:04d}"
    p = root / ".webnovel" / "tmp" / f"{prefix}_ch{pad}.json"
    p.write_text(json.dumps({"score": score}, ensure_ascii=False), encoding="utf-8")


def _write_external_aggregate(root, ext_avg, models_ok_count, models_ok=None, ch=27):
    pad = f"{ch:04d}"
    p = root / ".webnovel" / "tmp" / f"external_review_ch{pad}.json"
    p.write_text(json.dumps({
        "chapter": ch,
        "external_avg": ext_avg,
        "models_ok": models_ok or [f"model_{i}" for i in range(models_ok_count)],
        "models_ok_count": models_ok_count,
        "coverage_status": "healthy" if models_ok_count >= 10 else "degraded_warn",
    }, ensure_ascii=False), encoding="utf-8")


# ---------- mirror-disk-scores 刷新 external_avg（Round 28.5 P0-1）----------

def test_mirror_disk_scores_refreshes_external_avg_from_aggregate(tmp_path):
    """验证 mirror-disk-scores 同时从 aggregate 文件读 external_avg 写到 chapter_meta."""
    _ensure_scripts_on_path()
    import sys as _sys
    from data_modules import state_manager as sm

    # 初始：chapter_meta 有陈旧 external_avg=88（12/15 时刻）
    meta = {
        "checker_scores": {"emotion-checker": 81},
        "external_avg": 88.0,
        "external_models_count": 12,
    }
    _setup_state(tmp_path, ch=27, meta=meta)
    _write_disk_json(tmp_path, "emotion", 91, ch=27)
    # aggregate 文件已被刷新到 15/15
    _write_external_aggregate(tmp_path, 87.4, 15, ch=27)

    old_argv = _sys.argv[:]
    try:
        _sys.argv = [
            "state_manager", "--project-root", str(tmp_path),
            "update", "--mirror-disk-scores", '{"chapter":27}',
        ]
        try:
            sm.main()
        except SystemExit:
            pass
    finally:
        _sys.argv = old_argv

    new_state = json.loads((tmp_path / ".webnovel" / "state.json").read_text(encoding="utf-8"))
    entry = new_state["chapter_meta"]["0027"]
    assert entry["external_avg"] == 87.4, f"external_avg 未刷新: {entry.get('external_avg')}"
    assert entry["external_models_count"] == 15, f"models_count 未更新: {entry.get('external_models_count')}"
    assert len(entry.get("external_models_ok", [])) == 15, "models_ok list 未刷新"


def test_mirror_disk_scores_skips_external_when_aggregate_missing(tmp_path):
    """无 aggregate 文件时不应崩溃，external_avg 保持原值."""
    _ensure_scripts_on_path()
    import sys as _sys
    from data_modules import state_manager as sm

    meta = {
        "checker_scores": {"emotion-checker": 81},
        "external_avg": 88.0,
    }
    _setup_state(tmp_path, ch=27, meta=meta)
    _write_disk_json(tmp_path, "emotion", 91, ch=27)
    # 不写 aggregate 文件

    old_argv = _sys.argv[:]
    try:
        _sys.argv = [
            "state_manager", "--project-root", str(tmp_path),
            "update", "--mirror-disk-scores", '{"chapter":27}',
        ]
        try:
            sm.main()
        except SystemExit:
            pass
    finally:
        _sys.argv = old_argv

    new_state = json.loads((tmp_path / ".webnovel" / "state.json").read_text(encoding="utf-8"))
    entry = new_state["chapter_meta"]["0027"]
    assert entry["external_avg"] == 88.0, "缺 aggregate 时不应改 external_avg"


# ---------- CHAPTER_META_FIELD_WHITELIST 扩展（Round 28.5 P0-2）----------

def test_set_chapter_meta_field_accepts_external_avg(tmp_path):
    _ensure_scripts_on_path()
    import sys as _sys
    from data_modules import state_manager as sm

    _setup_state(tmp_path, ch=27)
    old_argv = _sys.argv[:]
    try:
        _sys.argv = [
            "state_manager", "--project-root", str(tmp_path),
            "update", "--set-chapter-meta-field",
            '{"chapter":27,"field":"external_avg","value":87.4}',
        ]
        try:
            sm.main()
        except SystemExit as e:
            assert e.code in (None, 0), f"set-chapter-meta-field external_avg failed: {e.code}"
    finally:
        _sys.argv = old_argv

    new_state = json.loads((tmp_path / ".webnovel" / "state.json").read_text(encoding="utf-8"))
    assert new_state["chapter_meta"]["0027"]["external_avg"] == 87.4


def test_set_chapter_meta_field_accepts_h69_fields(tmp_path):
    """H69 4 个字段必须可通过 CLI 设置（fallback 修复路径）."""
    _ensure_scripts_on_path()
    import sys as _sys
    from data_modules import state_manager as sm

    _setup_state(tmp_path, ch=27)
    test_fields = [
        ("total_words", 2674),
        ("dialogue_ratio", 0.32),
        ("signature_density", 0.0),
        ("reader_thrill_score", 50),
        ("external_models_ok", ["m1", "m2", "m3"]),
        ("external_models_count", 15),
    ]
    for field, value in test_fields:
        old_argv = _sys.argv[:]
        try:
            payload = json.dumps({"chapter": 27, "field": field, "value": value}, ensure_ascii=False)
            _sys.argv = [
                "state_manager", "--project-root", str(tmp_path),
                "update", "--set-chapter-meta-field", payload,
            ]
            try:
                sm.main()
            except SystemExit as e:
                assert e.code in (None, 0), f"set-chapter-meta-field {field} rejected: {e.code}"
        finally:
            _sys.argv = old_argv

    new_state = json.loads((tmp_path / ".webnovel" / "state.json").read_text(encoding="utf-8"))
    entry = new_state["chapter_meta"]["0027"]
    assert entry["total_words"] == 2674
    assert entry["dialogue_ratio"] == 0.32
    assert entry["signature_density"] == 0.0
    assert entry["reader_thrill_score"] == 50
    assert entry["external_models_ok"] == ["m1", "m2", "m3"]
    assert entry["external_models_count"] == 15


def test_set_chapter_meta_field_still_rejects_unknown_field(tmp_path, capsys):
    """未知字段仍应被白名单拒绝（防御范围只扩 7 个，不开闸）."""
    _ensure_scripts_on_path()
    import sys as _sys
    from data_modules import state_manager as sm

    _setup_state(tmp_path, ch=27)
    old_argv = _sys.argv[:]
    try:
        _sys.argv = [
            "state_manager", "--project-root", str(tmp_path),
            "update", "--set-chapter-meta-field",
            '{"chapter":27,"field":"random_unknown_field","value":"x"}',
        ]
        try:
            sm.main()
        except SystemExit:
            pass
    finally:
        _sys.argv = old_argv

    captured = capsys.readouterr()
    out = captured.out + captured.err
    assert "FIELD_NOT_ALLOWED" in out, f"未知字段应被拒绝，实际: {out}"
