#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 29 Phase 3 · chapter_meta core 字段单一真源 + 写库时完整性前移。

背景：core 字段漏写 4 次复发（Ch18 6/23、Ch24、Ch29、Ch32）——schema 不强制 core 字段，
缺字段要到 Step 7 commit 时才被 hygiene H2 P0 抓，返工成本最高。R29：
1. CORE_META_FIELDS 移到 data_modules/meta_fields.py 单一真源（hygiene import + is 锁死，
   沿用 REQUIRED_ARTIFACT_FIELDS 模式·两份 hardcode 必然漂移的两年血教训）；
2. `state process-chapter` 写库后立即报告 core_fields_missing，data-agent 必须当场补填重跑。
"""

import sys
from pathlib import Path


def _ensure_scripts_on_path():
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def _full_meta():
    return {
        "chapter": 7, "title": "测试章", "word_count": 3000, "summary": "摘要",
        "hook_strength": "strong", "scene_count": 4, "key_beats": ["b1"],
        "characters": ["主角"], "locations": ["院子"], "created_at": "2026-06-12T00:00:00Z",
        "updated_at": "2026-06-12T00:00:00Z", "protagonist_state": "稳定",
        "location_current": "院子", "power_realm": "Lv2", "golden_finger_level": "Lv2",
        "time_anchor": "末世第30天", "end_state": "悬置", "foreshadowing_planted": [],
        "foreshadowing_paid": [], "strand_dominant": "quest", "review_score": 86,
        "checker_scores": {}, "allusions_used": [],
    }


def test_full_meta_has_no_missing():
    _ensure_scripts_on_path()
    from data_modules.meta_fields import missing_core_fields

    assert missing_core_fields(_full_meta()) == []


def test_missing_and_empty_fields_detected():
    _ensure_scripts_on_path()
    from data_modules.meta_fields import missing_core_fields

    meta = _full_meta()
    del meta["time_anchor"]          # 缺失
    meta["summary"] = ""             # 空字符串
    meta["protagonist_state"] = None  # None
    meta["scene_count"] = {}          # 非 allow-empty 的空容器
    missing = missing_core_fields(meta)
    assert set(missing) == {"time_anchor", "summary", "protagonist_state", "scene_count"}


def test_allow_empty_list_fields_pass_when_empty():
    _ensure_scripts_on_path()
    from data_modules.meta_fields import missing_core_fields

    meta = _full_meta()
    meta["foreshadowing_paid"] = []   # Ch1 0 兑现合法
    meta["allusions_used"] = []
    meta["checker_scores"] = {}
    assert missing_core_fields(meta) == []


def test_hygiene_imports_single_source():
    """hygiene_check.CORE_META_FIELDS 必须 is data_modules.meta_fields 同一对象（防双真源漂移）。"""
    _ensure_scripts_on_path()
    import hygiene_check
    from data_modules import meta_fields

    assert hygiene_check.CORE_META_FIELDS is meta_fields.CORE_META_FIELDS
    assert hygiene_check.CORE_META_LIST_FIELDS_ALLOW_EMPTY is meta_fields.CORE_META_LIST_FIELDS_ALLOW_EMPTY
    assert hygiene_check.CORE_22_FIELDS is meta_fields.CORE_META_FIELDS  # back-compat alias


def test_meta_fields_none_input_safe():
    _ensure_scripts_on_path()
    from data_modules.meta_fields import missing_core_fields, CORE_META_FIELDS

    assert set(missing_core_fields(None)) == set(CORE_META_FIELDS)
    assert set(missing_core_fields({})) == set(CORE_META_FIELDS)
