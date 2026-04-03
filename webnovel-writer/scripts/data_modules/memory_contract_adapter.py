#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MemoryContractAdapter——薄适配器，包装现有模块满足 MemoryContract Protocol。

不做存储重构，仅委托给 StateManager / IndexManager / ScratchpadManager 等。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import DataModulesConfig, get_config
from .memory_contract import (
    CommitResult,
    ContextPack,
    EntitySnapshot,
    OpenLoop,
    Rule,
    TimelineEvent,
)

logger = logging.getLogger(__name__)


class MemoryContractAdapter:
    """满足 MemoryContract Protocol 的具体实现。"""

    def __init__(self, config: DataModulesConfig | None = None):
        self.config = config or get_config()

    # ------------------------------------------------------------------
    # 内部懒加载（避免在构造时就初始化所有重量级模块）
    # ------------------------------------------------------------------

    def _state_manager(self):
        from .state_manager import StateManager
        return StateManager(self.config)

    def _index_manager(self):
        from .index_manager import IndexManager
        return IndexManager(self.config)

    def _memory_writer(self):
        from .memory.writer import MemoryWriter
        return MemoryWriter(self.config)

    def _memory_store(self):
        from .memory.store import ScratchpadManager
        return ScratchpadManager(self.config)

    def _memory_orchestrator(self):
        from .memory.orchestrator import MemoryOrchestrator
        return MemoryOrchestrator(self.config)

    # ------------------------------------------------------------------
    # 契约方法
    # ------------------------------------------------------------------

    def commit_chapter(self, chapter: int, result: dict) -> CommitResult:
        warnings: List[str] = []
        entities_added = 0
        entities_updated = 0
        state_changes_recorded = 0
        relationships_added = 0
        memory_items_added = 0
        summary_path = ""

        # 1. StateManager: process_chapter_result
        try:
            sm = self._state_manager()
            sm._load_state()
            sm_warnings = sm.process_chapter_result(chapter, result)
            warnings.extend(sm_warnings or [])
            entities_added = len(result.get("entities_new", []) or [])
            entities_updated = len(result.get("entities_appeared", []) or [])
            state_changes_recorded = len(result.get("state_changes", []) or [])
            relationships_added = len(result.get("relationships_new", []) or [])
        except Exception as e:
            logger.warning("commit_chapter: StateManager failed: %s", e)
            warnings.append(f"StateManager error: {e}")

        # 2. MemoryWriter: update_from_chapter_result
        try:
            mw = self._memory_writer()
            mem_stats = mw.update_from_chapter_result(chapter, result)
            memory_items_added = mem_stats.get("items_added", 0)
            if mem_stats.get("warnings"):
                warnings.extend(mem_stats["warnings"])
        except Exception as e:
            logger.warning("commit_chapter: MemoryWriter failed: %s", e)
            warnings.append(f"MemoryWriter error: {e}")

        # 3. 摘要路径
        padded = f"{chapter:04d}"
        summary_file = self.config.webnovel_dir / "summaries" / f"ch{padded}.md"
        if summary_file.exists():
            summary_path = str(summary_file)

        return CommitResult(
            chapter=chapter,
            entities_added=entities_added,
            entities_updated=entities_updated,
            state_changes_recorded=state_changes_recorded,
            relationships_added=relationships_added,
            memory_items_added=memory_items_added,
            summary_path=summary_path,
            warnings=warnings,
        )

    def load_context(self, chapter: int, budget_tokens: int = 4000) -> ContextPack:
        try:
            orch = self._memory_orchestrator()
            pack = orch.build_memory_pack(chapter)
            return ContextPack(
                chapter=chapter,
                sections=pack,
                budget_used_tokens=0,  # orchestrator 不计 token，由调用者按需裁剪
            )
        except Exception as e:
            logger.warning("load_context failed: %s", e)
            return ContextPack(chapter=chapter)

    def query_entity(self, entity_id: str) -> Optional[EntitySnapshot]:
        try:
            sm = self._state_manager()
            sm._load_state()
            entity = sm.get_entity(entity_id)
            if not entity:
                return None

            entity_type = sm.get_entity_type(entity_id) or "角色"
            state_changes = sm.get_state_changes(entity_id)
            recent_changes = state_changes[-5:] if state_changes else []

            return EntitySnapshot(
                id=entity_id,
                name=entity.get("name", entity_id),
                type=entity_type,
                tier=entity.get("tier", "核心"),
                aliases=entity.get("aliases", []),
                attributes={k: v for k, v in entity.items()
                            if k not in ("name", "tier", "aliases", "first_appearance", "last_appearance")},
                first_appearance=entity.get("first_appearance", 0),
                last_appearance=entity.get("last_appearance", 0),
                recent_state_changes=recent_changes,
            )
        except Exception as e:
            logger.warning("query_entity(%s) failed: %s", entity_id, e)
            return None

    def query_rules(self, domain: str = "") -> List[Rule]:
        try:
            store = self._memory_store()
            items = store.query(category="world_rule", status="active")
            rules = []
            for item in items:
                if domain and item.subject != domain and domain not in item.value:
                    continue
                rules.append(Rule(
                    id=item.id,
                    subject=item.subject,
                    field=item.field,
                    value=item.value,
                    domain=item.subject,
                    source_chapter=item.source_chapter,
                ))
            return rules
        except Exception as e:
            logger.warning("query_rules failed: %s", e)
            return []

    def read_summary(self, chapter: int) -> str:
        padded = f"{chapter:04d}"
        summary_file = self.config.webnovel_dir / "summaries" / f"ch{padded}.md"
        try:
            if summary_file.exists():
                return summary_file.read_text(encoding="utf-8")
            return ""
        except Exception as e:
            logger.warning("read_summary(%d) failed: %s", chapter, e)
            return ""

    def get_open_loops(self, status: str = "active") -> List[OpenLoop]:
        try:
            store = self._memory_store()
            items = store.query(category="open_loop", status=status)
            return [
                OpenLoop(
                    id=item.id,
                    content=item.value,
                    status=item.status,
                    planted_chapter=item.source_chapter,
                    expected_payoff=item.payload.get("expected_payoff", ""),
                    urgency=float(item.payload.get("urgency", 0.0)),
                )
                for item in items
            ]
        except Exception as e:
            logger.warning("get_open_loops failed: %s", e)
            return []

    def get_timeline(self, from_ch: int, to_ch: int) -> List[TimelineEvent]:
        try:
            store = self._memory_store()
            items = store.query(category="timeline", status="active")
            events = []
            for item in items:
                ch = item.source_chapter
                if from_ch <= ch <= to_ch:
                    events.append(TimelineEvent(
                        event=item.value,
                        chapter=ch,
                        time_hint=item.field,
                        event_type=item.subject,
                    ))
            events.sort(key=lambda e: e.chapter)
            return events
        except Exception as e:
            logger.warning("get_timeline failed: %s", e)
            return []
