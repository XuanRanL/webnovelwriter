#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Writing guidance and checklist builders.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .genre_aliases import to_profile_key


GENRE_GUIDANCE_TEXT: dict[str, str] = {
    "xianxia": "题材加权：强化升级/对抗结果的可见反馈，术语解释后置。",
    "shuangwen": "题材加权：维持高爽点密度，主爽点外叠加一个副轴反差。",
    "urban-power": "题材加权：优先写社会反馈链（他人反应→资源变化→地位变化）。",
    "romance": "题材加权：每章推进关系位移，避免情绪原地打转。",
    "mystery": "题材加权：线索必须可回收，优先以规则冲突制造悬念。",
    "rules-mystery": "题材加权：规则先于解释，代价先于胜利。",
    "zhihu-short": "题材加权：压缩铺垫，优先反转与高强度结尾钩。",
    "substitute": "题材加权：强化误解-拉扯-决断链路，避免重复虐点。",
    "esports": "题材加权：每场对抗至少写清一个战术决策点与其后果。",
    "livestream": "题材加权：强化“外部反馈→主角反制→数据变化”即时闭环。",
    "cosmic-horror": "题材加权：恐怖来源于规则与代价，不依赖空泛惊悚形容。",
}


def build_guidance_items(
    *,
    chapter: int,
    reader_signal: Dict[str, Any],
    genre_profile: Dict[str, Any],
    low_score_threshold: float,
    hook_diversify_enabled: bool,
) -> Dict[str, Any]:
    guidance: List[str] = []

    low_ranges = reader_signal.get("low_score_ranges") or []
    if low_ranges:
        worst = min(
            low_ranges,
            key=lambda row: float(row.get("overall_score", 9999)),
        )
        guidance.append(
            f"第{chapter}章优先修复近期低分段问题：参考{worst.get('start_chapter')}-{worst.get('end_chapter')}章，强化冲突推进与结尾钩子。"
        )

    hook_usage = reader_signal.get("hook_type_usage") or {}
    if hook_usage and hook_diversify_enabled:
        dominant_hook = max(hook_usage.items(), key=lambda kv: kv[1])[0]
        guidance.append(
            f"近期钩子类型“{dominant_hook}”使用偏多，本章建议做钩子差异化，避免连续同构。"
        )

    pattern_usage = reader_signal.get("pattern_usage") or {}
    if pattern_usage:
        top_pattern = max(pattern_usage.items(), key=lambda kv: kv[1])[0]
        guidance.append(
            f"爽点模式“{top_pattern}”近期高频，本章可保留主爽点但叠加一个新爽点副轴。"
        )

    review_trend = reader_signal.get("review_trend") or {}
    overall_avg = review_trend.get("overall_avg")
    if isinstance(overall_avg, (int, float)) and float(overall_avg) < low_score_threshold:
        guidance.append(
            f"最近审查均分{overall_avg:.1f}低于阈值{low_score_threshold:.1f}，建议先保稳：减少跳场、每段补动作结果闭环。"
        )

    genre = str(genre_profile.get("genre") or "").strip()
    refs = genre_profile.get("reference_hints") or []
    if genre:
        guidance.append(f"题材锚定：按“{genre}”叙事主线推进，保持题材读者预期稳定兑现。")
    if refs:
        guidance.append(f"题材策略可执行提示：{refs[0]}")

    guidance.append("网文节奏基线：章首300字内给出目标与阻力，章末保留未闭合问题。")
    guidance.append("兑现密度基线：每600-900字给一次微兑现，并确保本章至少1处可量化变化。")

    normalized_genre = to_profile_key(genre)
    genre_hint = GENRE_GUIDANCE_TEXT.get(normalized_genre)
    if genre_hint:
        guidance.append(genre_hint)

    composite_hints = genre_profile.get("composite_hints") or []
    if composite_hints:
        guidance.append(f"复合题材协同：{composite_hints[0]}")

    if not guidance:
        guidance.append("本章执行默认高可读策略：冲突前置、信息后置、段末留钩。")

    return {
        "guidance": guidance,
        "low_ranges": low_ranges,
        "hook_usage": hook_usage,
        "pattern_usage": pattern_usage,
        "genre": genre,
    }


def build_writing_checklist(
    *,
    guidance_items: List[str],
    reader_signal: Dict[str, Any],
    genre_profile: Dict[str, Any],
    min_items: int,
    max_items: int,
    default_weight: float,
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    def _add_item(
        item_id: str,
        label: str,
        *,
        weight: float | None = None,
        required: bool = False,
        source: str = "writing_guidance",
        verify_hint: str = "",
    ) -> None:
        if len(items) >= max_items:
            return
        if any(row.get("id") == item_id for row in items):
            return

        item_weight = float(weight if weight is not None else default_weight)
        if item_weight <= 0:
            item_weight = default_weight

        items.append(
            {
                "id": item_id,
                "label": label,
                "weight": round(item_weight, 2),
                "required": bool(required),
                "source": source,
                "verify_hint": verify_hint,
            }
        )

    low_ranges = reader_signal.get("low_score_ranges") or []
    if low_ranges:
        worst = min(low_ranges, key=lambda row: float(row.get("overall_score", 9999)))
        span = f"{worst.get('start_chapter')}-{worst.get('end_chapter')}"
        _add_item(
            "fix_low_score_range",
            f"修复低分区间问题（参考第{span}章）",
            weight=max(default_weight, 1.4),
            required=True,
            source="reader_signal.low_score_ranges",
            verify_hint="至少完成1处冲突升级，并在段末留下钩子。",
        )

    hook_usage = reader_signal.get("hook_type_usage") or {}
    if hook_usage:
        dominant_hook = max(hook_usage.items(), key=lambda kv: kv[1])[0]
        _add_item(
            "hook_diversification",
            f"钩子差异化（避免继续单一“{dominant_hook}”）",
            weight=max(default_weight, 1.2),
            required=True,
            source="reader_signal.hook_type_usage",
            verify_hint="结尾钩子类型与近20章主类型至少有一处差异。",
        )

    pattern_usage = reader_signal.get("pattern_usage") or {}
    if pattern_usage:
        top_pattern = max(pattern_usage.items(), key=lambda kv: kv[1])[0]
        _add_item(
            "coolpoint_combo",
            f"主爽点+副爽点组合（主爽点：{top_pattern}）",
            weight=default_weight,
            required=False,
            source="reader_signal.pattern_usage",
            verify_hint="新增至少1个副爽点，并与主爽点形成因果链。",
        )

    review_trend = reader_signal.get("review_trend") or {}
    overall_avg = review_trend.get("overall_avg")
    if isinstance(overall_avg, (int, float)):
        _add_item(
            "readability_loop",
            "段落可读性闭环（动作→结果→情绪）",
            weight=max(default_weight, 1.1),
            required=True,
            source="reader_signal.review_trend",
            verify_hint="抽查3段，均包含动作结果闭环。",
        )

    genre = str(genre_profile.get("genre") or "").strip()
    if genre:
        _add_item(
            "genre_anchor_consistency",
            f"题材锚定一致性（{genre}）",
            weight=max(default_weight, 1.1),
            required=True,
            source="genre_profile.genre",
            verify_hint="主冲突与题材核心承诺保持一致。",
        )

    for idx, text in enumerate(guidance_items, start=1):
        if len(items) >= max_items:
            break
        label = str(text).strip()
        if not label:
            continue
        _add_item(
            f"guidance_item_{idx}",
            label,
            weight=default_weight,
            required=False,
            source="writing_guidance.guidance_items",
            verify_hint="完成后可在正文中定位对应段落。",
        )

    fallback_items = [
        (
            "opening_conflict",
            "开篇300字内给出冲突触发",
            "开头段出现明确目标与阻力。",
        ),
        (
            "scene_goal_block",
            "场景目标与阻力清晰",
            "每个场景至少有1个可验证目标。",
        ),
        (
            "ending_hook",
            "段末留钩并引出下一问",
            "结尾出现未解问题或下一步行动。",
        ),
    ]
    for item_id, label, verify_hint in fallback_items:
        if len(items) >= min_items or len(items) >= max_items:
            break
        _add_item(
            item_id,
            label,
            weight=default_weight,
            required=False,
            source="fallback",
            verify_hint=verify_hint,
        )

    return items[:max_items]


def is_checklist_item_completed(item: Dict[str, Any], reader_signal: Dict[str, Any]) -> bool:
    item_id = str(item.get("id") or "")
    if item_id in {"fix_low_score_range", "readability_loop"}:
        review_trend = reader_signal.get("review_trend") or {}
        overall = review_trend.get("overall_avg")
        return isinstance(overall, (int, float)) and float(overall) >= 75.0

    if item_id == "hook_diversification":
        hook_usage = reader_signal.get("hook_type_usage") or {}
        return len(hook_usage) >= 2

    if item_id == "coolpoint_combo":
        pattern_usage = reader_signal.get("pattern_usage") or {}
        return len(pattern_usage) >= 2

    if item_id == "genre_anchor_consistency":
        return True

    source = str(item.get("source") or "")
    if source.startswith("fallback"):
        return True

    return False

