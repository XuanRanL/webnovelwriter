"""Round 28.53 + R28.54 · Ch50 deep RCA · 2 道新 hygiene 护栏 + A3 mandatory_review 单测.

测试范围:
- H88 同章内时间锚物理一致性 (R28.53 Ch50 实战 + R28.54 Ch11 false positive 修复)
- H89 dialogue tag 单调度防护 (Ch50 "陆沉说" 22 次实战)
- A3 mandatory_human_review_models (Ch50 gemini-3.1-pro 62.3 偏 effective_avg ≥15)
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


def _make_project(tmp_path, ch_text=""):
    pr = tmp_path / "book"
    (pr / ".webnovel").mkdir(parents=True)
    (pr / "正文").mkdir()
    (pr / "正文" / "第0999章-test.md").write_text(ch_text, encoding="utf-8")
    state = {
        "project_info": {"name": "test", "protagonist": "陆沉",
                         "word_count_policy": {"hard_min": 2200, "hard_max": 3800}},
        "chapter_meta": {"0999": {"chapter": 999, "narrative_version": "v1"}},
    }
    (pr / ".webnovel" / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    return pr


class _Rep:
    def __init__(self):
        self.records = []

    def record(self, priority, h_id, msg, ok=True):
        self.records.append({"priority": priority, "h": h_id, "ok": ok, "msg": msg})


# ===== H88 同章内时间锚物理一致性 =====

def test_h88_ch50_v1_time_paradox_caught(tmp_path):
    """R28.53 核心 case: Ch50 v1 时间悖论 11:20 接电话报告 11:28-32 才动手必须 P0 fail."""
    _ensure_scripts_on_path()
    import hygiene_check
    text = """十一点二十的时候，手机响。

那不是苏瑾。

“陆先生。”那边说。“我是苏老师同事。”

“苏老师十一点二十进所，到这会儿还出不来。门里头有血。”

“十一点二十八到三十二之间。从外头看，那段没人进出。”
"""
    pr = _make_project(tmp_path, ch_text=text)
    rep = _Rep()
    hygiene_check.check_intra_chapter_time_anchor_physical_consistency(pr, 999, rep)
    fails = [r for r in rep.records if r["h"] == "H88" and not r["ok"]]
    assert len(fails) == 1, f"expected 1 H88 fail, got {len(fails)}: {rep.records}"
    assert "物理悖论" in fails[0]["msg"]


def test_h88_ch50_v5_time_fix_silent(tmp_path):
    """R28.53 修复后 (11:20 → 11:40 给 20min 缓冲): silent pass."""
    _ensure_scripts_on_path()
    import hygiene_check
    text = """十一点四十的时候，手机响。

那不是苏瑾。

“陆先生。”那边说。“我是苏老师同事。”

“苏老师十一点二十进所，到这会儿还出不来。门里头有血。”

“十一点二十八到三十二之间。从外头看，那段没人进出。”
"""
    pr = _make_project(tmp_path, ch_text=text)
    rep = _Rep()
    hygiene_check.check_intra_chapter_time_anchor_physical_consistency(pr, 999, rep)
    fails = [r for r in rep.records if r["h"] == "H88" and not r["ok"]]
    assert not fails, f"expected silent pass, got fails: {fails}"


def test_h88_ch11_news_same_line_false_positive_fixed(tmp_path):
    """R28.54 修复: 同行新闻播报式时间双锚不触发 (Ch11 实战 false positive)."""
    _ensure_scripts_on_path()
    import hygiene_check
    # Ch11 L21 真实场景: 同一行包含"凌晨四点"叙述 + "今晨四点至五点"引号内
    text = """陆沉把茶杯放下。

电视画面继续走。下一段画面是西郊一段巷子里的路灯——三盏路灯里有两盏不亮，画面右下角时间显示凌晨四点。主持人声音平稳：“另据合肥供电局通报，今晨四点至五点，西郊部分线路出现间歇性跳闸。”

陆沉指节在桌面上压了一下。
"""
    pr = _make_project(tmp_path, ch_text=text)
    rep = _Rep()
    hygiene_check.check_intra_chapter_time_anchor_physical_consistency(pr, 999, rep)
    fails = [r for r in rep.records if r["h"] == "H88" and not r["ok"]]
    assert not fails, f"R28.54 should silent pass news same-line, got: {fails}"


def test_h88_cai_word_alone_does_not_trigger(tmp_path):
    """R28.54 修复: '才' 单字不再触发 (Ch11 'X 才会' 自然语流)."""
    _ensure_scripts_on_path()
    import hygiene_check
    # 早叙述 "三点" + 晚引号内 "四点" + "才会" 但无强事件词
    text = """下午三点的时候，他走到院子里。

天色慢慢暗。

“四点会下雨。”外公说。“早早收。再过一周才会真凉。”
"""
    pr = _make_project(tmp_path, ch_text=text)
    rep = _Rep()
    hygiene_check.check_intra_chapter_time_anchor_physical_consistency(pr, 999, rep)
    fails = [r for r in rep.records if r["h"] == "H88" and not r["ok"]]
    assert not fails, f"才 alone should not trigger, got: {fails}"


def test_h88_few_time_anchors_skipped(tmp_path):
    """时间锚 <3 个跳过检测."""
    _ensure_scripts_on_path()
    import hygiene_check
    text = "陆沉走到院门口。下午三点过。\n"
    pr = _make_project(tmp_path, ch_text=text)
    rep = _Rep()
    hygiene_check.check_intra_chapter_time_anchor_physical_consistency(pr, 999, rep)
    # 应 record OK (跳过)
    assert any(r["h"] == "H88" and r["ok"] for r in rep.records)


# ===== H89 dialogue tag 单调度 =====

def test_h89_ch50_lu_chen_say_22_times_caught(tmp_path):
    """R28.53 核心: 单角色 say tag >12 次 → P1 warn."""
    _ensure_scripts_on_path()
    import hygiene_check
    # 构造 22 处 "陆沉说"
    text = "\n\n".join([f"“嗯。”陆沉说。\n\n“好。”陆沉说。" for _ in range(11)])
    pr = _make_project(tmp_path, ch_text=text)
    rep = _Rep()
    hygiene_check.check_dialogue_tag_diversity(pr, 999, rep)
    fails = [r for r in rep.records if r["h"] == "H89" and not r["ok"]]
    assert fails, f"expected H89 fail for 22 陆沉说, got: {rep.records}"
    assert "陆沉说" in fails[0]["msg"]


def test_h89_few_tags_skipped(tmp_path):
    """tag 总数 <5 跳过."""
    _ensure_scripts_on_path()
    import hygiene_check
    text = "“嗯。”陆沉说。\n\n“好。”周明说。"
    pr = _make_project(tmp_path, ch_text=text)
    rep = _Rep()
    hygiene_check.check_dialogue_tag_diversity(pr, 999, rep)
    assert any(r["h"] == "H89" and r["ok"] for r in rep.records)


def test_h89_diverse_tags_silent(tmp_path):
    """多样化 tag → silent pass."""
    _ensure_scripts_on_path()
    import hygiene_check
    text = """“嗯。”陆沉说。
“好。”周明应。
“在。”林晚秋接。
“您说。”陆沉道。
“晓得。”外公答。
“嗯。”朵朵问。
"""
    pr = _make_project(tmp_path, ch_text=text)
    rep = _Rep()
    hygiene_check.check_dialogue_tag_diversity(pr, 999, rep)
    fails = [r for r in rep.records if r["h"] == "H89" and not r["ok"]]
    assert not fails


# ===== A3 mandatory_human_review_models =====

def test_a3_mandatory_review_for_low_outlier(tmp_path):
    """R28.53 核心: lowest_model 偏离 effective_avg ≥15 分 → 进 mandatory_review."""
    _ensure_scripts_on_path()
    from data_modules.chapter_audit import check_A3_external_models

    # 构造 mock external_review JSON: 14 模型 87 + 1 模型 (gemini-3.1-pro) 62.3
    pr = tmp_path / "book"
    (pr / ".webnovel" / "tmp").mkdir(parents=True)
    models = [
        "qwen3.6-plus", "doubao-pro", "gpt-5.5", "doubao-seed-2.0-lite",
        "glm-5", "glm-5.1", "glm-4.7", "mimo-v2.5-pro",
        "minimax-m2.7-hs", "minimax-m2.5", "deepseek-v3.2-thinking",
        "deepseek-v4-flash", "kimi-k2.5", "kimi-k2.6",
    ]
    for m in models:
        (pr / ".webnovel" / "tmp" / f"external_review_{m}_ch0050.json").write_text(
            json.dumps({
                "agent": f"external-{m}", "chapter": 50, "model_key": m,
                "model_actual": m, "provider": "ark-coding", "routing_verified": True,
                "overall_score": 87.0, "pass": True, "dimension_reports": [],
            }, ensure_ascii=False),
            encoding="utf-8",
        )
    # gemini 是 outlier 但 >60，不进 critical_score_outliers，但偏 effective_avg=87 - 62.3 = 24.7 >=15 → mandatory
    (pr / ".webnovel" / "tmp" / "external_review_gemini-3.1-pro_ch0050.json").write_text(
        json.dumps({
            "agent": "external-gemini-3.1-pro", "chapter": 50, "model_key": "gemini-3.1-pro",
            "model_actual": "gemini-3.1-pro", "provider": "openclawroot", "routing_verified": True,
            "overall_score": 62.3, "pass": True, "dimension_reports": [],
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    result = check_A3_external_models(pr, 50)
    measured = result.measured or {}
    assert "mandatory_human_review_models" in measured, f"mandatory_review missing: {measured}"
    assert "gemini-3.1-pro" in measured["mandatory_human_review_models"]


def test_a3_no_mandatory_when_models_tight(tmp_path):
    """全模型分数接近 → 无 mandatory."""
    _ensure_scripts_on_path()
    from data_modules.chapter_audit import check_A3_external_models

    pr = tmp_path / "book"
    (pr / ".webnovel" / "tmp").mkdir(parents=True)
    models = [
        "qwen3.6-plus", "doubao-pro", "gpt-5.5", "doubao-seed-2.0-lite",
        "glm-5", "glm-5.1", "glm-4.7", "mimo-v2.5-pro",
        "minimax-m2.7-hs", "minimax-m2.5", "deepseek-v3.2-thinking",
        "deepseek-v4-flash", "kimi-k2.5", "kimi-k2.6", "gemini-3.1-pro",
    ]
    for m in models:
        (pr / ".webnovel" / "tmp" / f"external_review_{m}_ch0050.json").write_text(
            json.dumps({
                "agent": f"external-{m}", "chapter": 50, "model_key": m,
                "model_actual": m, "provider": "ark-coding", "routing_verified": True,
                "overall_score": 87.0 + (hash(m) % 5),  # 87-91 紧凑
                "pass": True, "dimension_reports": [],
            }, ensure_ascii=False),
            encoding="utf-8",
        )
    result = check_A3_external_models(pr, 50)
    measured = result.measured or {}
    # mandatory_review 应缺省或空
    assert not measured.get("mandatory_human_review_models"), \
        f"expected no mandatory_review when scores tight, got: {measured.get('mandatory_human_review_models')}"
