#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Round 21.8 外部锐评硬伤根治回归测试 · 2026-04-30

覆盖外部锐评指出的 7 处硬伤根治：

H37 · 章首 D-N 时间锚连续性
  Ch4→5 跳 D-26（已 callback）/ Ch10→11 跳 D-19 / Ch14→15 跳 D-14 /
  Ch20→21 跳 D-7。倒计时是核心紧张感，跳日必须显式 callback。

H38 · 正文禁用 markdown **加粗**
  Ch15 出现 5 处 ** 加粗 ** 笔记残留（破坏沉浸感，编辑直接退稿）。

H39 · 跨章签名词频率上限
  存储位 45 / 手册 42 / 生机值 36 / 这一次 35 / 晓得 18 / 停了一拍 16。
  重复形成模板感会让读者觉得"作者在套路"。

测试矩阵 (12 项)：
  H37: 连续 / 跳1天有callback / 跳1天无callback / 倒退 / 首章 / 解析失败
  H38: 无加粗 pass / 单加粗 fail / 5加粗 fail / blockquote 豁免 / code fence 豁免
  H39: 单章超载 fail / 滑窗超载 fail / 正常 pass
"""
import json
import sys
from pathlib import Path

import pytest


def _ensure_scripts_on_path() -> None:
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def _load_hygiene():
    _ensure_scripts_on_path()
    import hygiene_check
    return hygiene_check


def _make_chapter(root: Path, ch: int, dn: int, day_count: int, body: str = "正文内容。"):
    chapters = root / "正文"
    chapters.mkdir(exist_ok=True)
    f = chapters / f"第{ch:04d}章-test.md"
    f.write_text(
        f"D-{dn} · 2026-04-{15+day_count-1:02d} 周一 · 重生第 {day_count} 天\n\n{body}\n",
        encoding="utf-8"
    )
    return f


# ---------------------------------------------------------------------------
# H37 · D-N 连续性
# ---------------------------------------------------------------------------


def test_h37_continuous_passes(tmp_path):
    hg = _load_hygiene()
    _make_chapter(tmp_path, 1, 30, 1)
    _make_chapter(tmp_path, 2, 29, 2)
    rep = hg.HygieneReport()
    hg.check_chapter_date_anchor_continuity(tmp_path, 2, rep)
    assert "H37" in rep.passes


def test_h37_skip_1_day_with_callback_passes(tmp_path):
    hg = _load_hygiene()
    _make_chapter(tmp_path, 4, 27, 4)
    body = "他想了想 D-26 那天发生的事。\n继续叙述。"
    _make_chapter(tmp_path, 5, 25, 6, body=body)
    rep = hg.HygieneReport()
    hg.check_chapter_date_anchor_continuity(tmp_path, 5, rep)
    assert "H37" in rep.passes, f"应 pass (含 D-26 callback), got p1={rep.p1_fails}"


def test_h37_skip_1_day_without_callback_warns(tmp_path):
    hg = _load_hygiene()
    _make_chapter(tmp_path, 10, 20, 11)
    _make_chapter(tmp_path, 11, 18, 13, body="完全没有提到中间那天。")
    rep = hg.HygieneReport()
    hg.check_chapter_date_anchor_continuity(tmp_path, 11, rep)
    h37_p1 = [f for f in rep.p1_fails if f.startswith("H37:")]
    assert len(h37_p1) == 1, f"应 P1 warn 缺 callback, got passes={rep.passes} p1={rep.p1_fails}"
    assert "callback" in h37_p1[0] and "19" in h37_p1[0]


def test_h37_first_chapter_skipped(tmp_path):
    hg = _load_hygiene()
    rep = hg.HygieneReport()
    hg.check_chapter_date_anchor_continuity(tmp_path, 1, rep)
    assert "H37" in rep.passes


# ---------------------------------------------------------------------------
# H38 · markdown 加粗扫描
# ---------------------------------------------------------------------------


def test_h38_no_bold_passes(tmp_path):
    hg = _load_hygiene()
    _make_chapter(tmp_path, 1, 30, 1, body="这是普通正文，没有任何加粗标记。")
    rep = hg.HygieneReport()
    hg.check_no_markdown_bold_in_prose(tmp_path, 1, rep)
    assert "H38" in rep.passes


def test_h38_single_bold_fails(tmp_path):
    hg = _load_hygiene()
    body = "这是正文。**这件事他这一刻才明白。**继续叙述。"
    _make_chapter(tmp_path, 15, 13, 18, body=body)
    rep = hg.HygieneReport()
    hg.check_no_markdown_bold_in_prose(tmp_path, 15, rep)
    h38_fails = [f for f in rep.p0_fails if f.startswith("H38:")]
    assert len(h38_fails) == 1, f"应 P0 fail, got passes={rep.passes} p0={rep.p0_fails}"


def test_h38_five_bolds_fails(tmp_path):
    """Ch15 真实复刻：5 处加粗"""
    hg = _load_hygiene()
    body = (
        "**第一段加粗。**\n\n"
        "正文。**第二段加粗。**\n\n"
        "**第三段加粗。**正文。\n\n"
        "**第四段加粗。**\n\n"
        "**第五段加粗。**\n"
    )
    _make_chapter(tmp_path, 15, 13, 18, body=body)
    rep = hg.HygieneReport()
    hg.check_no_markdown_bold_in_prose(tmp_path, 15, rep)
    h38_fails = [f for f in rep.p0_fails if f.startswith("H38:")]
    assert len(h38_fails) == 1
    assert "5" in h38_fails[0] or "处" in h38_fails[0]


def test_h38_blockquote_exempted(tmp_path):
    hg = _load_hygiene()
    body = "正文。\n\n> **手册第一条**：<power-faction>系统。\n\n继续正文。"
    _make_chapter(tmp_path, 1, 30, 1, body=body)
    rep = hg.HygieneReport()
    hg.check_no_markdown_bold_in_prose(tmp_path, 1, rep)
    assert "H38" in rep.passes, f"blockquote 应豁免, got p0={rep.p0_fails}"


def test_h38_code_fence_exempted(tmp_path):
    hg = _load_hygiene()
    body = "正文。\n\n```\n**code bold inside fence**\n```\n\n继续。"
    _make_chapter(tmp_path, 1, 30, 1, body=body)
    rep = hg.HygieneReport()
    hg.check_no_markdown_bold_in_prose(tmp_path, 1, rep)
    assert "H38" in rep.passes


# ---------------------------------------------------------------------------
# H39 · 签名词频率
# ---------------------------------------------------------------------------


def test_h39_single_chapter_overuse_warns(tmp_path):
    """单章存储位 8 次 > 5 限"""
    hg = _load_hygiene()
    body = ("存储位 " * 8) + "其他内容。"
    _make_chapter(tmp_path, 1, 30, 1, body=body)
    rep = hg.HygieneReport()
    hg.check_signature_word_overuse(tmp_path, 1, rep)
    h39 = [f for f in rep.p1_fails if f.startswith("H39:")]
    assert len(h39) == 1, f"应 P1 warn, got passes={rep.passes} p1={rep.p1_fails}"
    assert "存储位" in h39[0]


def test_h39_normal_passes(tmp_path):
    hg = _load_hygiene()
    body = "存储位用了一次。手册翻了一页。生机值 90。普通叙述。"
    _make_chapter(tmp_path, 1, 30, 1, body=body)
    rep = hg.HygieneReport()
    hg.check_signature_word_overuse(tmp_path, 1, rep)
    assert "H39" in rep.passes


def test_h39_window_overload_warns(tmp_path):
    """5 章累计 手册 26 > 25 限"""
    hg = _load_hygiene()
    for ch in range(1, 6):
        body = ("手册 " * 6) + "正文。"
        _make_chapter(tmp_path, ch, 30 - ch + 1, ch, body=body)
    rep = hg.HygieneReport()
    hg.check_signature_word_overuse(tmp_path, 5, rep)
    h39 = [f for f in rep.p1_fails if f.startswith("H39:")]
    assert len(h39) == 1
    assert "手册" in h39[0] or "5 章累计" in h39[0]


# ---------------------------------------------------------------------------
# 项目侧 8 处硬伤实际复测（<example-project>）· 标记 xfail 当项目未链接
# ---------------------------------------------------------------------------


def test_real_project_ch15_no_markdown_bold():
    """<example-project> Ch15 真实复测：修复后无 markdown 加粗"""
    project = Path(r"I:\AI-extention\webnovel-writer\<example-project>")
    if not project.exists():
        pytest.skip("<example-project>项目未挂载")
    text = (project / "正文" / "第0015章-第一只活体异变.md").read_text(encoding="utf-8")
    import re
    bold_count = len(re.findall(r"\*\*[^\*\n]+\*\*", text))
    assert bold_count == 0, f"Ch15 应无 markdown 加粗，实际 {bold_count} 处"


def test_real_project_ch12_dark_network_actor():
    """<example-project> Ch12 真实复测：'那张网' 应是<antagonist>不是林老师"""
    project = Path(r"I:\AI-extention\webnovel-writer\<example-project>")
    if not project.exists():
        pytest.skip("<example-project>项目未挂载")
    text = (project / "正文" / "第0012章-那个小女孩.md").read_text(encoding="utf-8")
    assert "林老师那个网" not in text and "林老师那张网" not in text, "Ch12 不应再有 林老师那个网"
    assert "<antagonist>那张网" in text or "<antagonist-2>" in text, "Ch12 应明指反派"


def test_real_project_ch20_distance_consistent():
    """<example-project> Ch20 真实复测：5 公里 vs 6 公里 一致性"""
    project = Path(r"I:\AI-extention\webnovel-writer\<example-project>")
    if not project.exists():
        pytest.skip("<example-project>项目未挂载")
    text = (project / "正文" / "第0020章-<female-lead>觉醒.md").read_text(encoding="utf-8")
    # 不能出现 "升至 5 公里" 配 "6 公里——刚好覆盖"
    if "升至 5 公里" in text or "升至 5公里" in text:
        # 必须有 distance >= 6 才合法
        pytest.fail("Ch20 仍写 升至 5 公里（与 6 公里覆盖矛盾），应改 ≥6.5 公里")
