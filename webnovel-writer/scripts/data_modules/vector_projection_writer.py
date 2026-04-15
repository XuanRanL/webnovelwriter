#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class VectorProjectionWriter:
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)

    def apply(self, commit_payload: dict) -> dict:
        if commit_payload["meta"]["status"] != "accepted":
            return {"applied": False, "writer": "vector", "reason": "commit_rejected"}

        chunks = self._collect_chunks(commit_payload)
        if not chunks:
            return {"applied": False, "writer": "vector", "reason": "no_chunks"}

        try:
            stored = self._store_chunks(chunks)
            return {"applied": stored > 0, "writer": "vector", "stored": stored}
        except Exception as exc:
            logger.warning("vector_projection_failed: %s", exc)
            return {"applied": False, "writer": "vector", "reason": f"error:{exc}"}

    def _collect_chunks(self, commit_payload: dict) -> List[Dict[str, Any]]:
        chunks: List[Dict[str, Any]] = []
        chapter = int(commit_payload.get("meta", {}).get("chapter") or 0)

        for event in commit_payload.get("accepted_events") or []:
            if not isinstance(event, dict):
                continue
            text = self._event_to_text(event)
            if text:
                evt_chapter = int(event.get("chapter") or chapter)
                chunks.append({
                    "chapter": evt_chapter,
                    "scene_index": 0,
                    "content": text,
                    "chunk_type": "event",
                    "parent_chunk_id": f"ch{evt_chapter:04d}_summary",
                    "source_file": f"commit:chapter_{evt_chapter:03d}",
                })

        for delta in commit_payload.get("entity_deltas") or []:
            if not isinstance(delta, dict):
                continue
            text = self._delta_to_text(delta)
            if text:
                d_chapter = int(delta.get("chapter") or chapter)
                chunks.append({
                    "chapter": d_chapter,
                    "scene_index": 0,
                    "content": text,
                    "chunk_type": "entity_delta",
                    "parent_chunk_id": f"ch{d_chapter:04d}_summary",
                    "source_file": f"commit:chapter_{d_chapter:03d}",
                })

        return chunks

    def _event_to_text(self, event: dict) -> str:
        chapter = int(event.get("chapter") or 0)
        subject = str(event.get("subject") or "").strip()
        event_type = str(event.get("event_type") or "").strip()
        payload = event.get("payload") or {}

        if event_type == "power_breakthrough":
            new_val = str(payload.get("new") or payload.get("to") or "").strip()
            return f"第{chapter}章：{subject}突破至{new_val}" if new_val else ""
        elif event_type == "character_state_changed":
            field = str(payload.get("field") or "").strip()
            new_val = str(payload.get("new") or payload.get("to") or "").strip()
            return f"第{chapter}章：{subject}的{field}变为{new_val}" if field and new_val else ""
        elif event_type == "relationship_changed":
            to_entity = str(payload.get("to_entity") or payload.get("to") or "").strip()
            rel_type = str(payload.get("relationship_type") or payload.get("type") or "").strip()
            return f"第{chapter}章：{subject}与{to_entity}关系变为{rel_type}" if to_entity else ""
        elif event_type in ("world_rule_revealed", "world_rule_broken"):
            desc = str(payload.get("description") or payload.get("rule") or "").strip()
            action = "揭示" if "revealed" in event_type else "打破"
            return f"第{chapter}章：{action}世界规则——{desc}" if desc else ""
        elif event_type == "artifact_obtained":
            name = str(payload.get("name") or subject or "").strip()
            owner = str(payload.get("owner") or payload.get("holder") or "").strip()
            return f"第{chapter}章：{owner}获得{name}" if owner else f"第{chapter}章：获得{name}"
        return ""

    def _delta_to_text(self, delta: dict) -> str:
        chapter = int(delta.get("chapter") or 0)
        from_e = str(delta.get("from_entity") or "").strip()
        to_e = str(delta.get("to_entity") or "").strip()
        rel = str(delta.get("relationship_type") or "").strip()

        if from_e and to_e and rel:
            return f"第{chapter}章：{from_e}与{to_e}关系变为{rel}"

        entity_id = str(delta.get("entity_id") or "").strip()
        canonical = str(delta.get("canonical_name") or entity_id).strip()
        if entity_id:
            return f"第{chapter}章：实体变更——{canonical}"
        return ""

    def _store_chunks(self, chunks: List[Dict[str, Any]]) -> int:
        from .config import DataModulesConfig
        from .rag_adapter import RAGAdapter

        config = DataModulesConfig.from_project_root(self.project_root)
        adapter = RAGAdapter(config)
        try:
            stored = asyncio.run(adapter.store_chunks(chunks))
            return stored
        except Exception as exc:
            logger.warning("vector_store_failed: %s", exc)
            return 0
