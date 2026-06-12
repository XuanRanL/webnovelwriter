#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 29 Phase 6.1 · 签名族闸门默认降级为 warn-only。

背景（docs/RCA-CHANGELOG.md R29）：
签名词量化封禁有实证副作用——"没X→未X"替换污染三复发（Ch16/Ch23）、
"过+量词"替代效应（R28.33）、签名打地鼠循环。Round 29 起：
- SIGNATURE_DENSITY / SIGNATURE_AGGREGATE / DASH_DENSITY / H78 默认只 warn 不 block，
  自然度判断权交还 reader-naturalness checker；
- 项目可在 `.webnovel/signature_density_config.json` 设 `"_enforcement": "block"`
  恢复整族硬闸（家族级开关）。
"""

import json
import sys
from pathlib import Path


def _ensure_scripts_on_path():
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def _make_project(tmp_path, text, chapter=99):
    (tmp_path / "正文").mkdir(exist_ok=True)
    (tmp_path / ".webnovel").mkdir(exist_ok=True)
    (tmp_path / ".webnovel" / "state.json").write_text(
        json.dumps(
            {
                "project_info": {"word_count_policy": {"hard_min": 500, "hard_max": 9000}},
                "chapter_meta": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "正文" / f"第{chapter:04d}章-测试.md").write_text(text, encoding="utf-8")
    return tmp_path


def _filler(n):
    return "院子里的菜苗按时浇水，土翻得松软，鸡棚也加了新草。" * n


def test_signature_density_breach_warns_not_blocks(tmp_path):
    """那一X ≥ block 阈值时默认进 warnings，不进 errors。"""
    _ensure_scripts_on_path()
    import post_draft_check

    text = _filler(40) + "那一刻他抬头。" * 14
    proj = _make_project(tmp_path, text)
    errors, warnings = post_draft_check.check(proj, 99)

    assert not [e for e in errors if "SIGNATURE_DENSITY" in e], (
        f"R29 P6.1: 签名密度超限默认不应 block; errors={errors}"
    )
    assert [w for w in warnings if "SIGNATURE_DENSITY" in w and not w.startswith("[INFO]")], (
        f"R29 P6.1: 签名密度超限必须保留 warn 可见性; warnings={warnings}"
    )


def test_signature_aggregate_breach_warns_not_blocks(tmp_path):
    """没/未/不曾 累计超 25/千字 默认进 warnings，不进 errors。"""
    _ensure_scripts_on_path()
    import post_draft_check

    text = "堂屋。" * 200
    text += "他没动。她没回。林川未出声。她到这会还无回信。" * 6
    text += "他不曾眨眼。他没看。他未碰。他没说话。他不曾出声。他没念。"
    proj = _make_project(tmp_path, text)
    errors, warnings = post_draft_check.check(proj, 99)

    assert not [e for e in errors if "SIGNATURE_AGGREGATE" in e], (
        f"R29 P6.1: 否定签名累计超限默认不应 block; errors={errors}"
    )
    assert [w for w in warnings if "SIGNATURE_AGGREGATE" in w], (
        f"R29 P6.1: 否定签名累计超限必须保留 warn 可见性; warnings={warnings}"
    )


def test_dash_density_breach_warns_not_blocks(tmp_path):
    """破折号 ≥ block 阈值时默认进 warnings，不进 errors。"""
    _ensure_scripts_on_path()
    import post_draft_check

    text = _filler(40) + "他想说——又停住——再开口——还是停住——" * 3
    proj = _make_project(tmp_path, text)
    errors, warnings = post_draft_check.check(proj, 99)

    assert not [e for e in errors if "DASH_DENSITY" in e], (
        f"R29 P6.1: 破折号超限默认不应 block; errors={errors}"
    )
    assert [w for w in warnings if "DASH_DENSITY" in w], (
        f"R29 P6.1: 破折号超限必须保留 warn 可见性; warnings={warnings}"
    )


def test_h78_cross_reuse_warns_not_blocks(tmp_path):
    """跨章 6-gram 重合 ≥ block 阈值时默认进 warnings，不进 errors。"""
    _ensure_scripts_on_path()
    import post_draft_check

    reuse = "蓝铁门那头很安静。送水车今早一辆还没过来，巷子里只有早班三轮车的链条声断断续续。"
    prev_text = _filler(30) + reuse
    cur_text = reuse + _filler(30)
    proj = _make_project(tmp_path, cur_text, chapter=2)
    (proj / "正文" / "第0001章-测试.md").write_text(prev_text, encoding="utf-8")

    errors, warnings = post_draft_check.check(proj, 2)

    assert not [e for e in errors if "H78" in e], (
        f"R29 P6.1: H78 默认不应 block; errors={errors}"
    )
    assert [w for w in warnings if "H78" in w], (
        f"R29 P6.1: H78 必须保留 warn 可见性; warnings={warnings}"
    )


def test_signature_enforcement_block_optin(tmp_path):
    """signature_density_config.json `\"_enforcement\": \"block\"` 恢复整族硬闸。"""
    _ensure_scripts_on_path()
    import post_draft_check

    text = _filler(40) + "那一刻他抬头。" * 14 + "他想说——又停住——再开口——还是停住——" * 3
    proj = _make_project(tmp_path, text)
    (proj / ".webnovel" / "signature_density_config.json").write_text(
        json.dumps({"_enforcement": "block"}, ensure_ascii=False), encoding="utf-8"
    )
    errors, warnings = post_draft_check.check(proj, 99)

    assert [e for e in errors if "SIGNATURE_DENSITY" in e], (
        f"R29 P6.1: opt-in block 时签名密度必须回到 errors; errors={errors}"
    )
    assert [e for e in errors if "DASH_DENSITY" in e], (
        f"R29 P6.1: opt-in block 时破折号必须回到 errors; errors={errors}"
    )
