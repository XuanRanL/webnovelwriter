"""Round 28.50 · Ch48 deep audit RCA · 5 道新 hygiene 护栏单测.

测试范围:
- H82 NPC entry/exit pairing (ghost-exit 防御)
- H83 timeline gap fill (>30 min 跳过过快防御)
- H84 emotion climax depth (情感高潮浅打发防御)
- H85 intra-chapter timestamp sanity (同章时间精度矛盾防御)
- H86 foreshadowing_planted consistency (chapter_meta vs plot_threads 对账)
"""
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"


def _ensure_scripts_on_path():
    p = str(SCRIPTS_DIR)
    if p not in sys.path:
        sys.path.insert(0, p)


def _make_project(tmp_path, ch_text="", characters=None, plot_threads_fl=None, meta_fp=None):
    pr = tmp_path / "book"
    (pr / ".webnovel").mkdir(parents=True)
    (pr / "正文").mkdir()
    (pr / ".webnovel" / "context").mkdir()
    (pr / "正文" / "第0048章-林母先开了口.md").write_text(ch_text, encoding="utf-8")
    state = {
        "project_info": {"name": "test", "protagonist": "陆沉",
                         "word_count_policy": {"hard_min": 2200, "hard_max": 3800}},
        "chapter_meta": {
            "0048": {
                "chapter": 48, "narrative_version": "v1",
                "characters": characters or [],
                "foreshadowing_planted": meta_fp or [],
            },
        },
        "plot_threads": {
            "foreshadowing_list": plot_threads_fl or [],
        },
        "progress": {"current_chapter": 48},
    }
    (pr / ".webnovel" / "state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return pr


# ============================================================
# H82 NPC entry/exit pairing
# ============================================================

def test_h82_npc_ghost_exit_detected(tmp_path):
    """老吴入场+大段对话+章末无exit描写 → P1 warn (Ch48 实战)."""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_npc_entry_exit_pairing

    # 模拟: 老吴入场对话, 然后到章末老吴的物件还在桌子上但没出门描写
    text = "天色还灰。\n\n" + "陆沉走进堂屋。\n\n" * 5 + \
        "老吴到了。老吴坐下喝水。\n\n" + \
        "老吴说：你那个事情，我听了一耳朵。\n\n" + \
        "其他正文段...\n\n" * 10 + \
        "陆沉迈出门槛。老吴的竹篮还在桌沿。"  # 老吴章末仍出现 但无 exit
    pr = _make_project(tmp_path, ch_text=text, characters=["陆沉", "老吴"])
    rep = HygieneReport()
    check_npc_entry_exit_pairing(pr, 48, rep)
    assert any("H82" in p for p in rep.p1_fails), f"应当 P1 warn 老吴 ghost-exit: {rep.p1_fails}"


def test_h82_npc_with_proper_exit_passes(tmp_path):
    """老吴入场+对话+明确 exit 描写 → PASS."""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_npc_entry_exit_pairing

    text = "天色还灰。\n\n" + \
        "老吴到了。老吴坐下喝水。\n\n" * 3 + \
        "老吴说：你那个事情。\n\n" + \
        "老吴起身。我得走了。\n\n" + \
        "外公送他到门口。\n\n" + \
        "老吴拎着布包出院门。\n\n" + \
        "陆沉继续做事...\n\n" * 5
    pr = _make_project(tmp_path, ch_text=text, characters=["陆沉", "老吴"])
    rep = HygieneReport()
    check_npc_entry_exit_pairing(pr, 48, rep)
    assert "H82" in rep.passes, f"应当 PASS: passes={rep.passes}, p1={rep.p1_fails}"


def test_h82_resident_npc_exempt(tmp_path):
    """常驻 NPC (林晚秋/朵朵/林母/外公) 不查 ghost-exit."""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_npc_entry_exit_pairing

    text = "陆沉在堂屋。林晚秋走进。林晚秋蹲下浇水。" * 3
    pr = _make_project(tmp_path, ch_text=text, characters=["陆沉", "林晚秋", "朵朵"])
    rep = HygieneReport()
    check_npc_entry_exit_pairing(pr, 48, rep)
    # 林晚秋是常驻, 没 exit 不报
    assert "H82" in rep.passes, f"常驻 NPC 应豁免: passes={rep.passes}"


# ============================================================
# H83 timeline gap fill
# ============================================================

def test_h83_short_gap_passes(tmp_path):
    """六点整 → 七点整 (60min) 但 prose 充分 → PASS."""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_timeline_gap_fill

    text = "六点整。陆沉做事。" + "做事做事做事做事做事做事做事做事。" * 30 + "七点整。陆沉继续。"
    pr = _make_project(tmp_path, ch_text=text)
    rep = HygieneReport()
    check_timeline_gap_fill(pr, 48, rep)
    assert "H83" in rep.passes, f"应当 PASS (prose 充分): {rep.p1_fails}"


def test_h83_long_gap_with_no_fill_detected(tmp_path):
    """六点整 → 七点四十 (100min) 但 prose <100 字 → P1 warn (Ch48 实战)."""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_timeline_gap_fill

    text = "六点整。陆沉做事。七点四十。老吴到了。"
    pr = _make_project(tmp_path, ch_text=text)
    rep = HygieneReport()
    check_timeline_gap_fill(pr, 48, rep)
    assert any("H83" in p for p in rep.p1_fails), f"应当 P1 warn: passes={rep.passes}"


def test_h83_in_dialogue_anchor_ignored(tmp_path):
    """对话内时间锚不算 narrative anchor."""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_timeline_gap_fill

    # 时间锚都在引号内，narrative 中只有一处时间锚
    text = "陆沉问：“八点过了吗。” 周明答：“两点拨过一次电波。” 陆沉走开。"
    pr = _make_project(tmp_path, ch_text=text)
    rep = HygieneReport()
    check_timeline_gap_fill(pr, 48, rep)
    # 排除引号内, narrative 锚 <2, 应通过
    assert "H83" in rep.passes, f"对话内时间锚不应计入: {rep.p1_fails}"


# ============================================================
# H84 emotion climax depth
# ============================================================

def test_h84_no_context_skips(tmp_path):
    """无 context JSON → skip."""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_emotion_climax_depth

    pr = _make_project(tmp_path, ch_text="正文段...")
    rep = HygieneReport()
    check_emotion_climax_depth(pr, 48, rep)
    assert "H84" in rep.passes


def test_h84_shallow_emotion_climax_detected(tmp_path):
    """情感高潮场景仅 1 round dialog + 0 body language → P1 warn (Ch48 林母 实战)."""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_emotion_climax_depth

    text = "其他正文。\n\n林母先开了口质疑五十米规则。陆叔叔不改。林母退后。\n\n后续。"
    pr = _make_project(tmp_path, ch_text=text)
    ctx = {
        "context_contract": {
            "emotional_anchors_plan": {
                "scene_identification": [
                    {"scene": "林母先开了口质疑", "type": "Internal-trust pressure peak"},
                ]
            }
        }
    }
    (pr / ".webnovel" / "context" / "ch0048_context.json").write_text(
        json.dumps(ctx, ensure_ascii=False), encoding="utf-8"
    )
    rep = HygieneReport()
    check_emotion_climax_depth(pr, 48, rep)
    assert any("H84" in p for p in rep.p1_fails), f"浅情感高潮应 warn: passes={rep.passes}"


def test_h84_deep_emotion_climax_passes(tmp_path):
    """情感高潮场景 ≥2 dialog + ≥3 body language → PASS."""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_emotion_climax_depth

    text = ("正文段。\n\n" +
            "林母先开了口。林母说：“五十米规则。” 林晚秋的指尖在把手上压一下。"
            "陆沉喉头紧住。 林母又说：“万一你不在。” 朵朵抬眼。林晚秋手腕一拨。"
            "林母低头看孙女。陆沉慢慢说：“等老吴这趟过完。”")
    pr = _make_project(tmp_path, ch_text=text)
    ctx = {
        "context_contract": {
            "emotional_anchors_plan": {
                "scene_identification": [
                    {"scene": "林母先开了口", "type": "Internal-trust pressure peak"},
                ]
            }
        }
    }
    (pr / ".webnovel" / "context" / "ch0048_context.json").write_text(
        json.dumps(ctx, ensure_ascii=False), encoding="utf-8"
    )
    rep = HygieneReport()
    check_emotion_climax_depth(pr, 48, rep)
    assert "H84" in rep.passes, f"深情感高潮应 PASS: p1={rep.p1_fails}"


# ============================================================
# H85 intra-chapter timestamp sanity
# ============================================================

def test_h85_same_event_gap_no_explain_detected(tmp_path):
    """SMS 同事件: 八点整屏幕亮起 + 七点五十四发送 - 无解释 → P1 warn (Ch48 实战)."""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_intra_chapter_timestamp_sanity

    text = ("八点整。周明的屏幕亮起。短信只有一行：南二村那边没人了。"
            "短信发完时间，是七点五十四。陆沉看一眼。")
    pr = _make_project(tmp_path, ch_text=text)
    rep = HygieneReport()
    check_intra_chapter_timestamp_sanity(pr, 48, rep)
    assert any("H85" in p for p in rep.p1_fails), f"应当 warn 同事件 6min gap 无解释: {rep.p1_fails}"


def test_h85_with_explain_passes(tmp_path):
    """同事件 + 解释 → PASS (Ch48 实战修复)."""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_intra_chapter_timestamp_sanity

    text = ("八点整。周明的屏幕亮起。短信发完时间，是七点五十四。"
            "这边收到的提示音卡在八点整——周明的手机一直静音，到点震动才看见。")
    pr = _make_project(tmp_path, ch_text=text)
    rep = HygieneReport()
    check_intra_chapter_timestamp_sanity(pr, 48, rep)
    assert "H85" in rep.passes, f"加 explain 后应当 PASS: p1={rep.p1_fails}"


def test_h85_different_scenes_skip(tmp_path):
    """不同场景的时间锚 (位置远) 不查矛盾."""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_intra_chapter_timestamp_sanity

    text = "六点整。" + ("正文段。" * 200) + "八点整。"  # 距离 >500 字
    pr = _make_project(tmp_path, ch_text=text)
    rep = HygieneReport()
    check_intra_chapter_timestamp_sanity(pr, 48, rep)
    assert "H85" in rep.passes


# ============================================================
# H86 foreshadowing_planted consistency
# ============================================================

def test_h86_plot_threads_match_meta_passes(tmp_path):
    """plot_threads = chapter_meta foreshadowing → PASS."""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_foreshadowing_planted_consistency

    pr = _make_project(
        tmp_path, ch_text="正文",
        plot_threads_fl=[
            {"id": "F-CH48-01", "planted_chapter": 48, "content": "着落"},
            {"id": "F-CH48-02", "planted_chapter": 48, "content": "竹篮"},
        ],
        meta_fp=[
            "F-CH48-01 着落悬置",
            "F-CH48-02 竹篮膏药",
        ],
    )
    rep = HygieneReport()
    check_foreshadowing_planted_consistency(pr, 48, rep)
    assert "H86" in rep.passes, f"对齐应 PASS: p0={rep.p0_fails}"


def test_h86_meta_missing_detected(tmp_path):
    """plot_threads 有 F-CH48-03 但 meta 没 → P0 block (Ch48 实战)."""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_foreshadowing_planted_consistency

    pr = _make_project(
        tmp_path, ch_text="正文",
        plot_threads_fl=[
            {"id": "F-CH48-01", "planted_chapter": 48},
            {"id": "F-CH48-02", "planted_chapter": 48},
            {"id": "F-CH48-03", "planted_chapter": 48},  # plot 有但 meta 漏
        ],
        meta_fp=[
            "F-CH48-01 着落悬置",
            "F-CH48-02 竹篮膏药",
        ],
    )
    rep = HygieneReport()
    check_foreshadowing_planted_consistency(pr, 48, rep)
    assert any("H86" in p for p in rep.p0_fails), f"漂移应 P0 block: passes={rep.passes}, p0={rep.p0_fails}"


def test_h86_both_empty_passes(tmp_path):
    """plot_threads 和 meta 都空 → PASS (空集对齐)."""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_foreshadowing_planted_consistency

    pr = _make_project(tmp_path, ch_text="正文", plot_threads_fl=[], meta_fp=[])
    rep = HygieneReport()
    check_foreshadowing_planted_consistency(pr, 48, rep)
    assert "H86" in rep.passes


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
