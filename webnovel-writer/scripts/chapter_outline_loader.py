#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

try:
    from chapter_paths import volume_num_for_chapter
except ImportError:  # pragma: no cover
    from scripts.chapter_paths import volume_num_for_chapter


_CHAPTER_RANGE_RE = re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*$")


def _parse_chapters_range(value: object) -> tuple[int, int] | None:
    if not isinstance(value, str):
        return None
    match = _CHAPTER_RANGE_RE.match(value)
    if not match:
        return None
    try:
        start = int(match.group(1))
        end = int(match.group(2))
    except ValueError:
        return None
    if start <= 0 or end <= 0 or start > end:
        return None
    return start, end


def volume_num_for_chapter_from_state(project_root: Path, chapter_num: int) -> int | None:
    state_path = project_root / ".webnovel" / "state.json"
    if not state_path.exists():
        return None

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    if not isinstance(state, dict):
        return None

    progress = state.get("progress")
    if not isinstance(progress, dict):
        return None

    volumes_planned = progress.get("volumes_planned")
    if not isinstance(volumes_planned, list):
        return None

    best: tuple[int, int] | None = None
    for item in volumes_planned:
        if not isinstance(item, dict):
            continue
        volume = item.get("volume")
        if not isinstance(volume, int) or volume <= 0:
            continue
        parsed = _parse_chapters_range(item.get("chapters_range"))
        if not parsed:
            continue
        start, end = parsed
        if start <= chapter_num <= end:
            candidate = (start, volume)
            if best is None or candidate[0] > best[0] or (candidate[0] == best[0] and candidate[1] < best[1]):
                best = candidate

    return best[1] if best else None


def _find_split_outline_file(outline_dir: Path, chapter_num: int) -> Path | None:
    patterns = [
        f"第{chapter_num}章*.md",
        f"第{chapter_num:02d}章*.md",
        f"第{chapter_num:03d}章*.md",
        f"第{chapter_num:04d}章*.md",
    ]
    for pattern in patterns:
        matches = sorted(outline_dir.glob(pattern))
        if matches:
            return matches[0]
    return None


def _find_volume_outline_file(project_root: Path, chapter_num: int) -> Path | None:
    outline_dir = project_root / "大纲"
    volume_num = volume_num_for_chapter_from_state(project_root, chapter_num) or volume_num_for_chapter(chapter_num)
    candidates = [
        outline_dir / f"第{volume_num}卷-详细大纲.md",
        outline_dir / f"第{volume_num}卷 - 详细大纲.md",
        outline_dir / f"第{volume_num}卷 详细大纲.md",
    ]
    return next((path for path in candidates if path.exists()), None)


def _extract_outline_section(content: str, chapter_num: int) -> str | None:
    patterns = [
        rf"###\s*第\s*{chapter_num}\s*章[：:]\s*(.+?)(?=###\s*第\s*\d+\s*章|##\s|$)",
        rf"###\s*第{chapter_num}章[：:]\s*(.+?)(?=###\s*第\d+章|##\s|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(0).strip()
    return None


def load_chapter_outline(project_root: Path, chapter_num: int, max_chars: int | None = 1500) -> str:
    outline_dir = project_root / "大纲"

    split_outline = _find_split_outline_file(outline_dir, chapter_num)
    if split_outline is not None:
        return split_outline.read_text(encoding="utf-8")

    volume_outline = _find_volume_outline_file(project_root, chapter_num)
    if volume_outline is None:
        return f"⚠️ 大纲文件不存在：第 {chapter_num} 章"

    outline = _extract_outline_section(volume_outline.read_text(encoding="utf-8"), chapter_num)
    if outline is None:
        return f"⚠️ 未找到第 {chapter_num} 章的大纲"

    if max_chars and len(outline) > max_chars:
        return outline[:max_chars] + "\n...(已截断)"
    return outline

_PLOT_SECTION_FIELD_MAP = {
    "cbn": "cbn",
    "cpns": "cpns",
    "cen": "cen",
    "必须覆盖节点": "mandatory_nodes",
    "本章禁区": "prohibitions",
}


def _clean_plot_line(line: str) -> str:
    text = str(line or "").strip()
    text = re.sub(r"^[\-\*•]+\s*", "", text)
    text = re.sub(r"^\d+[\.、]\s*", "", text)
    return text.strip()


def _append_plot_value(target: Dict[str, Any], field: str, value: str) -> None:
    value = _clean_plot_line(value)
    if not value:
        return

    if field in {"cpns", "mandatory_nodes", "prohibitions"}:
        target.setdefault(field, [])
        candidates = [value]
        if field in {"mandatory_nodes", "prohibitions"}:
            split_values = [part.strip() for part in re.split(r"[、,，；;|]+", value) if part.strip()]
            if split_values:
                candidates = split_values
        for item in candidates:
            if item not in target[field]:
                target[field].append(item)
        return

    if field not in target:
        target[field] = value


def parse_chapter_plot_structure(outline_text: str) -> Dict[str, Any]:
    text = str(outline_text or "")
    if not text or text.startswith("⚠️"):
        return {}

    structure: Dict[str, Any] = {}
    current_field = ""

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            current_field = ""
            continue
        if re.match(r"^#{1,6}\s*第\s*\d+\s*章", stripped):
            current_field = ""
            continue

        cleaned = _clean_plot_line(stripped)
        matched_field = ""
        matched_value = ""
        for label, field in _PLOT_SECTION_FIELD_MAP.items():
            match = re.match(rf"^{re.escape(label)}\s*[：:]\s*(.*)$", cleaned, re.IGNORECASE)
            if match:
                matched_field = field
                matched_value = match.group(1).strip()
                break

        if matched_field:
            current_field = matched_field
            _append_plot_value(structure, matched_field, matched_value)
            continue

        if current_field:
            _append_plot_value(structure, current_field, cleaned)

    cpns = structure.get("cpns") or []
    mandatory_nodes = structure.get("mandatory_nodes") or []
    prohibitions = structure.get("prohibitions") or []
    if not any([structure.get("cbn"), cpns, structure.get("cen"), mandatory_nodes, prohibitions]):
        return {}

    return {
        "cbn": str(structure.get("cbn") or "").strip(),
        "cpns": cpns,
        "cen": str(structure.get("cen") or "").strip(),
        "mandatory_nodes": mandatory_nodes,
        "prohibitions": prohibitions,
        "source": "chapter_outline",
    }


def load_chapter_plot_structure(project_root: Path, chapter_num: int) -> Dict[str, Any]:
    outline = load_chapter_outline(project_root, chapter_num, max_chars=None)
    return parse_chapter_plot_structure(outline)
