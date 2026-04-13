#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from .story_contracts import read_json_if_exists, write_json


class StateProjectionWriter:
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)

    def apply(self, commit_payload: dict) -> dict:
        if commit_payload["meta"]["status"] != "accepted":
            return {"applied": False, "writer": "state", "reason": "commit_rejected"}

        chapter = int(commit_payload.get("meta", {}).get("chapter") or 0)
        state_path = self.project_root / ".webnovel" / "state.json"
        state = read_json_if_exists(state_path) or {}
        entity_state = state.setdefault("entity_state", {})
        progress = state.setdefault("progress", {})
        chapter_status = progress.setdefault("chapter_status", {})

        applied_count = 0
        for delta in self._collect_state_deltas(commit_payload):
            entity_id = str(delta.get("entity_id") or "").strip()
            field = str(delta.get("field") or "").strip()
            if not entity_id or not field:
                continue
            entity_state.setdefault(entity_id, {})[field] = delta.get("new")
            applied_count += 1

        if chapter > 0:
            chapter_status[str(chapter)] = "chapter_committed"

        write_json(state_path, state)
        return {
            "applied": applied_count > 0 or chapter > 0,
            "writer": "state",
            "applied_count": applied_count,
        }

    def _collect_state_deltas(self, commit_payload: dict) -> list[dict]:
        deltas = [dict(delta) for delta in (commit_payload.get("state_deltas") or []) if isinstance(delta, dict)]
        seen = {
            (
                str(delta.get("entity_id") or "").strip(),
                str(delta.get("field") or "").strip(),
            )
            for delta in deltas
        }

        for event in commit_payload.get("accepted_events") or []:
            if not isinstance(event, dict):
                continue
            event_type = str(event.get("event_type") or "").strip()
            payload = dict(event.get("payload") or {})
            entity_id = str(payload.get("entity_id") or event.get("subject") or "").strip()
            if not entity_id:
                continue

            field = ""
            if event_type == "power_breakthrough":
                field = str(payload.get("field") or "realm").strip()
            elif event_type == "character_state_changed":
                field = str(payload.get("field") or "").strip()
            else:
                continue

            key = (entity_id, field)
            if not field or key in seen:
                continue

            seen.add(key)
            deltas.append(
                {
                    "entity_id": entity_id,
                    "field": field,
                    "old": payload.get("old") if "old" in payload else payload.get("from"),
                    "new": payload.get("new") if "new" in payload else payload.get("to"),
                }
            )
        return deltas
