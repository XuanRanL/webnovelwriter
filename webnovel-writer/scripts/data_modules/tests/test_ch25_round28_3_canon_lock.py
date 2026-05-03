"""Round 28.3 Ch25 RCA wave 3 tests · Canon Lock H67.

Ch25 v11 polish 凭空发明了 3 项 canon violation：
1. 金银花 / 银耳（凭空作物）
2. 灶屋木匣（凭空容器）
3. 空气在脱水（凭空物理）

H67 通过扫描高敏感名词模式 + 与 canon 全语料对比识别凭空发明。
"""
from pathlib import Path
import json
import sys


def _ensure_scripts_on_path():
    here = Path(__file__).resolve()
    scripts_dir = here.parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def _setup_project(tmp_path: Path, chapter_text: str, prev_chapters: dict | None = None,
                   canon_text: str = ""):
    """Build a minimal project structure."""
    (tmp_path / "正文").mkdir(parents=True)
    (tmp_path / "正文" / "第0025章-test.md").write_text(chapter_text, encoding="utf-8")
    if prev_chapters:
        for ch, txt in prev_chapters.items():
            (tmp_path / "正文" / f"第{ch:04d}章-prev.md").write_text(txt, encoding="utf-8")
    if canon_text:
        (tmp_path / "设定集").mkdir()
        (tmp_path / "设定集" / "00-Canon-Bible.md").write_text(canon_text, encoding="utf-8")


# ============== H67: canon 锁定检测 ==============

def test_h67_detects_invented_jinyinhua(tmp_path):
    """Ch25 v11 真实场景：金银花未在 canon 中"""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_canon_locked_terms

    # 本章引入金银花，但 canon 没有
    chapter_text = "<sister-character>取了一片金银花叶子敷上去。"
    canon_text = "<golden-finger-space>里有苦瓜、变异南瓜瓤等作物。"  # 没金银花
    prev = {15: "Ch15 用变异南瓜瓤救老张。"}
    _setup_project(tmp_path, chapter_text, prev, canon_text)

    rep = HygieneReport()
    check_canon_locked_terms(tmp_path, 25, rep)
    fails = [f for f in rep.p1_fails if "H67" in f]
    assert fails, f"H67 应捕获金银花：p1={rep.p1_fails}"


def test_h67_passes_canon_locked_pumpkin(tmp_path):
    """变异南瓜瓤 canon 已锁，应通过"""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_canon_locked_terms

    chapter_text = "<sister-character>取了一片变异南瓜瓤切片敷上去。"
    canon_text = "Ch15 老张被野猪救命用变异南瓜瓤。"
    prev = {15: "<protagonist>用变异南瓜瓤救了老张。"}
    _setup_project(tmp_path, chapter_text, prev, canon_text)

    rep = HygieneReport()
    check_canon_locked_terms(tmp_path, 25, rep)
    fails = [f for f in rep.p1_fails if "H67" in f]
    assert not fails, f"canon 已锁应通过：p1={rep.p1_fails}"
    assert "H67" in rep.passes


def test_h67_detects_invented_kongqi_tuoshui(tmp_path):
    """v11 真实场景：'空气在脱水' 凭空物理"""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_canon_locked_terms

    chapter_text = "<apocalypse-event>近了，空气在脱水。"
    canon_text = "<apocalypse-event>设定：D-0 降临。"  # 没"空气在脱水"
    _setup_project(tmp_path, chapter_text, None, canon_text)

    rep = HygieneReport()
    check_canon_locked_terms(tmp_path, 25, rep)
    fails = [f for f in rep.p1_fails if "H67" in f]
    assert fails, f"H67 应捕获'空气在脱水'凭空物理：p1={rep.p1_fails}"


def test_h67_detects_invented_zaowu_muxia(tmp_path):
    """灶屋木匣凭空容器"""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_canon_locked_terms

    chapter_text = "他从灶屋木匣里取出叶子。"
    canon_text = "灶屋是 canon，但木匣不是。"
    prev = {23: "灶屋里有切菜板和白瓷盘。"}
    _setup_project(tmp_path, chapter_text, prev, canon_text)

    rep = HygieneReport()
    check_canon_locked_terms(tmp_path, 25, rep)
    fails = [f for f in rep.p1_fails if "H67" in f]
    assert fails, f"H67 应捕获灶屋木匣：p1={rep.p1_fails}"


def test_h67_passes_when_canon_in_setting(tmp_path):
    """已知词在设定集 → 通过"""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_canon_locked_terms

    # 章节用 canon 已锁的"变异南瓜瓤"，canon 文本必须真含 "变异南瓜瓤"
    chapter_text = "他从橱柜里取了一片变异南瓜瓤。"
    canon_text = "橱柜底层是<protagonist>储物处。变异南瓜瓤：Ch15 已用救老张备货。"
    _setup_project(tmp_path, chapter_text, None, canon_text)

    rep = HygieneReport()
    check_canon_locked_terms(tmp_path, 25, rep)
    fails = [f for f in rep.p1_fails if "H67" in f]
    assert not fails, f"设定集已锁应通过：p1={rep.p1_fails}"


def test_h67_passes_when_in_previous_chapter(tmp_path):
    """已知词在之前章节 → 通过"""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_canon_locked_terms

    chapter_text = "<sister-character>取一片变异南瓜瓤掐成两段。"
    canon_text = "总纲。"
    prev = {15: "<protagonist>用变异南瓜瓤救老张时，把瓜瓤掐扁。"}
    _setup_project(tmp_path, chapter_text, prev, canon_text)

    rep = HygieneReport()
    check_canon_locked_terms(tmp_path, 25, rep)
    fails = [f for f in rep.p1_fails if "H67" in f]
    assert not fails, f"前章已锁应通过：p1={rep.p1_fails}"


def test_h67_skips_when_chapter_text_missing(tmp_path):
    """章节文件缺失 → 跳过（不阻断）"""
    _ensure_scripts_on_path()
    from hygiene_check import HygieneReport, check_canon_locked_terms

    rep = HygieneReport()
    check_canon_locked_terms(tmp_path, 25, rep)
    # No chapter file → returns silently
    assert "H67" not in rep.passes
    fails = [f for f in rep.p1_fails if "H67" in f]
    assert not fails, "缺章节应跳过不报警"


# ============== Canon-aware logic verification ==============

def test_canon_aware_pattern_extraction():
    """Verify the regex patterns capture sensitive nouns."""
    import re
    text = "金银花叶子 银耳 灶屋木匣 橱柜搪瓷盒 灵泉水 苦瓜片 空气在脱水"
    patterns = [
        r"[一-鿿]{2,4}瓤",
        r"[一-鿿]{1,3}木匣",
        r"[一-鿿]{1,3}搪瓷盒",
        r"灵泉[一-鿿]{0,2}",
        r"[一-鿿]{2,3}叶子",
        r"[一-鿿]{1,2}银花",
        r"[一-鿿]{0,2}银耳",
        r"空气在[一-鿿]{1,3}",
    ]
    captured = set()
    for p in patterns:
        for m in re.findall(p, text):
            if isinstance(m, str) and len(m) >= 2:
                captured.add(m)
    assert "金银花" in captured
    assert "银耳" in captured
    assert "灶屋木匣" in captured
    # 模式可能匹配多种长度变体，验证捕获了关键 sensitive 词
    has_搪瓷 = any("搪瓷" in c for c in captured)
    assert has_搪瓷, f"搪瓷盒变体应被捕获: {captured}"
    # 至少 5 个高敏感词被捕获（含变体）
    assert len(captured) >= 5
