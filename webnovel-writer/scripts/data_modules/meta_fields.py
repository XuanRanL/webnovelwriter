#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""chapter_meta core 字段单一真源（Round 29 Phase 3）。

此前 CORE_META_FIELDS 定义在 hygiene_check.py（commit 期闸门），core 字段漏写要到
Step 7 才被 H2 P0 抓（Ch18/24/29/32 四次复发，返工成本最高）。R29 把定义移到这里：
- hygiene_check.py 改为 import（is-identity 单测锁死，沿用 REQUIRED_ARTIFACT_FIELDS 模式）；
- `state process-chapter` 写库后立即用 missing_core_fields() 报告缺失，把发现时刻
  从 commit 前移到写库时。

改字段集合时同步：references/data-agent 接口规范 + audit B9 + 本模块单测。
"""
from __future__ import annotations

from typing import List, Optional

CORE_META_FIELDS = {
    "chapter", "title", "word_count", "summary", "hook_strength", "scene_count",
    "key_beats", "characters", "locations", "created_at", "updated_at",
    "protagonist_state", "location_current", "power_realm", "golden_finger_level",
    "time_anchor", "end_state", "foreshadowing_planted", "foreshadowing_paid",
    "strand_dominant", "review_score", "checker_scores", "allusions_used",
}

# 空 list/dict 语义合法的字段（如 Ch1 0 兑现伏笔 / 过渡章 0 新典故）
CORE_META_LIST_FIELDS_ALLOW_EMPTY = {
    "foreshadowing_planted", "foreshadowing_paid", "allusions_used",
    "key_beats", "characters", "locations", "checker_scores",
}


def missing_core_fields(meta: Optional[dict]) -> List[str]:
    """返回 chapter_meta 中缺失/空值的 core 字段列表（语义与 hygiene H2 完全一致）。"""
    if not meta:
        return sorted(CORE_META_FIELDS)
    missing = []
    for f in CORE_META_FIELDS:
        if f not in meta:
            missing.append(f)
            continue
        v = meta[f]
        if v is None or v == "":
            missing.append(f)
            continue
        if v == [] or v == {}:
            if f not in CORE_META_LIST_FIELDS_ALLOW_EMPTY:
                missing.append(f)
    return sorted(missing)
