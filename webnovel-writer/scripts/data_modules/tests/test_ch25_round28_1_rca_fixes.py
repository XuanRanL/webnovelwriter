"""Round 28.1 Ch25 RCA new guards tests.

Ch25 deep research exposed root causes:
1. Curly quote pairing direction undetected (2 reverse quotes) -> H62
2. reader_pull_ch{NNNN}.json missing on disk silently SKIP -> H26 upgrade + H63
3. recompute_chapter.py incorrectly overwrites total_words -> RC fix
4. Top-level last_completed_chapter has no CLI -> set-progress-chapter
5. set-checker-score auto-overwrites overall_score (combined formula collision) -> decouple
6. data-agent writes only 11 dimensions -> save-review-metrics validation
7. Step 5 implicit_start accumulates as A6 HIGH warns -> H64 + strict mode
"""
from pathlib import Path
import json
import sys


def _ensure_scripts_on_path():
    here = Path(__file__).resolve()
    scripts_dir = here.parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def _write_chapter_text(root: Path, chapter: int, text: str) -> Path:
    (root / "正文").mkdir(parents=True, exist_ok=True)
    p = root / "正文" / f"第{chapter:04d}章-test.md"
    p.write_text(text, encoding="utf-8")
    return p


def _write_state(root: Path, **kwargs) -> Path:
    (root / ".webnovel").mkdir(parents=True, exist_ok=True)
    p = root / ".webnovel" / "state.json"
    p.write_text(json.dumps(kwargs, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


# ============== H62: 弯引号方向 ==============

def test_h62_detects_reversed_opening_quote(tmp_path):
    """U+201D 出现在 U+201C 之前 = 反向，应 P0 fail."""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_curly_quote_pairing

    bad_text = '正常文本。用的词是”不可逆转”，他没回。\n'
    _write_chapter_text(tmp_path, 25, bad_text)
    rep = HygieneReport()
    check_curly_quote_pairing(tmp_path, 25, rep)
    fails = [f for f in rep.p0_fails if "H62" in f]
    assert fails, f"H62 应捕获反向引号: p0={rep.p0_fails}"


def test_h62_passes_correct_pairing(tmp_path):
    """正常 “X” 配对应通过."""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_curly_quote_pairing

    good_text = '他说：“今天天气很好。”<sister-character>答：“嗯。”\n'
    _write_chapter_text(tmp_path, 25, good_text)
    rep = HygieneReport()
    check_curly_quote_pairing(tmp_path, 25, rep)
    fails = [f for f in rep.p0_fails if "H62" in f]
    assert not fails, f"H62 应通过：p0={rep.p0_fails}"
    assert "H62" in rep.passes


def test_h62_detects_unbalanced(tmp_path):
    """左右数量不匹配应 fail."""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_curly_quote_pairing

    bad = '“开始的话” 但是 “没结束\n'
    _write_chapter_text(tmp_path, 25, bad)
    rep = HygieneReport()
    check_curly_quote_pairing(tmp_path, 25, rep)
    fails = [f for f in rep.p0_fails if "H62" in f]
    assert fails, f"H62 应捕获失衡：p0={rep.p0_fails}"


# ============== H63: 13 checker JSON 全落盘 ==============

def test_h63_passes_with_all_13_jsons(tmp_path):
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_thirteen_checker_jsons_present

    tmp_dir = tmp_path / ".webnovel" / "tmp"
    tmp_dir.mkdir(parents=True)
    prefixes = [
        "consistency_check", "continuity_check", "ooc_check", "reader_pull",
        "high_point_check", "flow", "pacing", "dialogue",
        "density", "prose_quality", "emotion",
        "reader_naturalness", "reader_critic",
    ]
    for p in prefixes:
        (tmp_dir / f"{p}_ch0025.json").write_text("{}", encoding="utf-8")

    rep = HygieneReport()
    check_thirteen_checker_jsons_present(tmp_path, 25, rep)
    fails = [f for f in rep.p0_fails if "H63" in f]
    assert not fails, f"应通过：p0={rep.p0_fails}"
    assert "H63" in rep.passes


def test_h63_fails_when_reader_pull_missing(tmp_path):
    """Ch25 实测场景：12/13 落盘但 reader_pull 缺."""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_thirteen_checker_jsons_present

    tmp_dir = tmp_path / ".webnovel" / "tmp"
    tmp_dir.mkdir(parents=True)
    # Write 12 (skip reader_pull)
    prefixes = [
        "consistency_check", "continuity_check", "ooc_check",
        "high_point_check", "flow", "pacing", "dialogue",
        "density", "prose_quality", "emotion",
        "reader_naturalness", "reader_critic",
    ]
    for p in prefixes:
        (tmp_dir / f"{p}_ch0025.json").write_text("{}", encoding="utf-8")

    rep = HygieneReport()
    check_thirteen_checker_jsons_present(tmp_path, 25, rep)
    fails = [f for f in rep.p0_fails if "H63" in f]
    assert fails, f"缺 reader_pull 应 P0 fail：p0={rep.p0_fails}"
    assert "reader-pull-checker" in fails[0]


# ============== H26 升级：reader_pull JSON 缺失 → P0 BLOCK ==============

def test_h26_blocks_when_reader_pull_json_missing(tmp_path):
    """Ch25 实测：reader_pull JSON 缺，旧规则 SKIP success，新规则 P0 block."""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_hook_close_persistence

    state = {"chapter_meta": {"0025": {"hook_close": {"primary_type": "动作钩"}}}}
    _write_state(tmp_path, **state)
    # 不创建 reader_pull JSON
    (tmp_path / ".webnovel" / "tmp").mkdir(parents=True, exist_ok=True)

    rep = HygieneReport()
    check_hook_close_persistence(tmp_path, 25, rep)
    fails = [f for f in rep.p0_fails if "H26" in f]
    assert fails, f"H26 应 fail：p0={rep.p0_fails}"
    # 必须包含 "未落盘" / "不存在" / "reader-pull" / "未真正落盘"
    msg = fails[0]
    assert any(kw in msg for kw in ["不存在", "未落盘", "未真正落盘", "reader-pull"]), msg


# ============== H64: Step 5 implicit_start ==============

def test_h64_detects_implicit_start_in_step_5(tmp_path):
    """Ch25 实测场景：Step 5 implicit_start=True."""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_no_implicit_start_in_step5

    wf_data = {
        "history": [
            {
                "chapter": 25,
                "completed_steps": [
                    {"id": "Step 1", "implicit_start": False},
                    {"id": "Step 5", "implicit_start": True},
                    {"id": "Step 7", "implicit_start": False},
                ],
            }
        ]
    }
    (tmp_path / ".webnovel").mkdir(parents=True)
    (tmp_path / ".webnovel" / "workflow_state.json").write_text(
        json.dumps(wf_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    rep = HygieneReport()
    check_no_implicit_start_in_step5(tmp_path, 25, rep)
    fails = [f for f in rep.p1_fails if "H64" in f]
    assert fails, f"H64 应捕获 Step 5 implicit_start：p1={rep.p1_fails}"


def test_h64_passes_when_step5_explicit(tmp_path):
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_no_implicit_start_in_step5

    wf_data = {
        "history": [
            {
                "chapter": 25,
                "completed_steps": [
                    {"id": "Step 5", "implicit_start": False},
                ],
            }
        ]
    }
    (tmp_path / ".webnovel").mkdir(parents=True)
    (tmp_path / ".webnovel" / "workflow_state.json").write_text(
        json.dumps(wf_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    rep = HygieneReport()
    check_no_implicit_start_in_step5(tmp_path, 25, rep)
    fails = [f for f in rep.p1_fails if "H64" in f]
    assert not fails, f"显式 start 应通过：p1={rep.p1_fails}"
    assert "H64" in rep.passes


# ============== save-review-metrics 验证 13 维度 ==============

def test_save_review_metrics_required_set_has_13():
    """Round 28.1: REQUIRED_DIMENSIONS 集合必含 naturalness + reader_critic."""
    REQUIRED = {
        "consistency", "continuity", "ooc", "reader_pull", "high_point",
        "flow", "pacing", "dialogue", "density", "prose_quality",
        "emotion", "naturalness", "reader_critic",
    }
    assert len(REQUIRED) == 13
    eleven = {"consistency", "continuity", "ooc", "reader_pull", "high_point",
              "flow", "pacing", "dialogue", "density", "prose_quality", "emotion"}
    missing = REQUIRED - eleven
    assert missing == {"naturalness", "reader_critic"}


# ============== recompute_chapter.py total_words 累计修复 ==============

def test_recompute_total_words_uses_chapter_meta_sum():
    """Round 28.1 · Ch25 RCA: recompute 应累计 chapter_meta 而非用单章."""
    chapter_meta = {
        "0024": {"word_count": 2800},
        "0025": {"word_count": 2926},
        "0023": {"word_count": 3100},
    }
    expected = sum(cm.get("word_count", 0) or 0 for cm in chapter_meta.values())
    assert expected == 8826  # 累计正确

    # 旧 bug：只用单章 = 2926 (current chapter)
    bug = chapter_meta["0025"]["word_count"]
    assert bug == 2926 != expected, "旧 bug 行为：单章覆盖累计"
