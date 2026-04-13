#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from .config import DataModulesConfig
from .index_manager import IndexManager


class IndexProjectionWriter:
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)

    def apply(self, commit_payload: dict) -> dict:
        if commit_payload["meta"]["status"] != "accepted":
            return {"applied": False, "writer": "index", "reason": "commit_rejected"}

        manager = IndexManager(DataModulesConfig.from_project_root(self.project_root))
        applied_count = 0
        for delta in self._collect_entity_deltas(commit_payload):
            result = manager.apply_entity_delta(delta)
            if result:
                applied_count += 1
        return {
            "applied": applied_count > 0,
            "writer": "index",
            "applied_count": applied_count,
        }

    def _collect_entity_deltas(self, commit_payload: dict) -> list[dict]:
        deltas = [dict(delta) for delta in (commit_payload.get("entity_deltas") or []) if isinstance(delta, dict)]
        for event in commit_payload.get("accepted_events") or []:
            if not isinstance(event, dict):
                continue
            event_type = str(event.get("event_type") or "").strip()
            payload = dict(event.get("payload") or {})
            chapter = int(event.get("chapter") or commit_payload.get("meta", {}).get("chapter") or 0)
            if event_type == "relationship_changed":
                from_entity = str(payload.get("from_entity") or event.get("subject") or "").strip()
                to_entity = str(payload.get("to_entity") or payload.get("to") or "").strip()
                rel_type = str(
                    payload.get("relationship_type")
                    or payload.get("relation_type")
                    or payload.get("type")
                    or ""
                ).strip()
                if from_entity and to_entity and rel_type:
                    deltas.append(
                        {
                            "from_entity": from_entity,
                            "to_entity": to_entity,
                            "relationship_type": rel_type,
                            "description": str(payload.get("description") or "").strip(),
                            "chapter": chapter,
                        }
                    )
            elif event_type == "artifact_obtained":
                entity_id = str(
                    payload.get("artifact_id")
                    or payload.get("entity_id")
                    or payload.get("id")
                    or event.get("subject")
                    or ""
                ).strip()
                if not entity_id:
                    continue
                current = {}
                owner = str(payload.get("owner") or payload.get("holder") or "").strip()
                location = str(payload.get("location") or "").strip()
                if owner:
                    current["holder"] = owner
                if location:
                    current["location"] = location
                deltas.append(
                    {
                        "entity_id": entity_id,
                        "canonical_name": str(payload.get("name") or event.get("subject") or entity_id).strip(),
                        "type": str(payload.get("type") or "物品").strip() or "物品",
                        "current": current,
                        "desc": str(payload.get("description") or "").strip(),
                        "chapter": chapter,
                    }
                )
        return deltas
