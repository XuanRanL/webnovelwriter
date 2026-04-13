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
        return deltas
