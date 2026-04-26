#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
State Manager - 状态管理模块 (v5.4)

管理 state.json 的读写操作：
- 实体状态管理
- 进度追踪
- 关系记录

v5.1 变更（v5.4 沿用）:
- 集成 SQLStateManager，同步写入 SQLite (index.db)
- state.json 保留精简数据，大数据自动迁移到 SQLite
"""

import json
import logging
import sys
import time
from copy import deepcopy
from pathlib import Path

from runtime_compat import enable_windows_utf8_stdio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import filelock

from .config import get_config
from .observability import safe_append_perf_timing, safe_log_tool_call


logger = logging.getLogger(__name__)

try:
    # 当 scripts 目录在 sys.path 中（常见：从 scripts/ 运行）
    from security_utils import atomic_write_json, read_json_safe
except ImportError:  # pragma: no cover
    # 当以 `python -m scripts.data_modules...` 从仓库根目录运行
    from scripts.security_utils import atomic_write_json, read_json_safe


@dataclass
class EntityState:
    """实体状态"""
    id: str
    name: str
    type: str  # 角色/地点/物品/势力
    tier: str = "装饰"  # 核心/重要/次要/装饰
    aliases: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    first_appearance: int = 0
    last_appearance: int = 0


@dataclass
class Relationship:
    """实体关系"""
    from_entity: str
    to_entity: str
    type: str
    description: str
    chapter: int


@dataclass
class StateChange:
    """状态变化记录"""
    entity_id: str
    field: str
    old_value: Any
    new_value: Any
    reason: str
    chapter: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class _EntityPatch:
    """待写入的实体增量补丁（用于锁内合并）"""
    entity_type: str
    entity_id: str
    replace: bool = False
    base_entity: Optional[Dict[str, Any]] = None  # 新建实体时的完整快照（用于填充缺失字段）
    top_updates: Dict[str, Any] = field(default_factory=dict)
    current_updates: Dict[str, Any] = field(default_factory=dict)
    appearance_chapter: Optional[int] = None


class StateManager:
    """状态管理器（v5.1 entities_v3 格式 + SQLite 同步，v5.4 沿用）"""

    # v5.0 引入的实体类型
    ENTITY_TYPES = ["角色", "地点", "物品", "势力", "招式"]

    def __init__(self, config=None, enable_sqlite_sync: bool = True):
        """
        初始化状态管理器

        参数:
        - config: 配置对象
        - enable_sqlite_sync: 是否启用 SQLite 同步 (默认 True)
        """
        self.config = config or get_config()
        self._state: Dict[str, Any] = {}
        # 与 security_utils.atomic_write_json 保持一致：state.json.lock
        self._lock_path = self.config.state_file.with_suffix(self.config.state_file.suffix + ".lock")

        # v5.1 引入: SQLite 同步
        self._enable_sqlite_sync = enable_sqlite_sync
        self._sql_state_manager = None
        if enable_sqlite_sync:
            try:
                from .sql_state_manager import SQLStateManager
                self._sql_state_manager = SQLStateManager(self.config)
            except ImportError:
                pass  # SQLStateManager 不可用时静默降级

        # 待写入的增量（锁内重读 + 合并 + 写入）
        self._pending_entity_patches: Dict[tuple[str, str], _EntityPatch] = {}
        self._pending_alias_entries: Dict[str, List[Dict[str, str]]] = {}
        self._pending_state_changes: List[Dict[str, Any]] = []
        self._pending_structured_relationships: List[Dict[str, Any]] = []
        self._pending_disambiguation_warnings: List[Dict[str, Any]] = []
        self._pending_disambiguation_pending: List[Dict[str, Any]] = []
        self._pending_progress_chapter: Optional[int] = None
        self._pending_progress_words_delta: int = 0
        self._pending_chapter_meta: Dict[str, Any] = {}
        # Bug fix 2026-04-13: state update 子命令直接改 _state 但未走 pending 机制，
        # 导致 save_state 因 has_pending=False 提前 return。这里登记 top-level 字段名
        # （如 "strand_tracker" / "plot_threads"），save_state 锁内会把 _state[k] 合并到 disk_state。
        self._pending_raw_state_mutations: set[str] = set()

        # v5.1 引入: 缓存待同步到 SQLite 的数据
        self._pending_sqlite_data: Dict[str, Any] = {
            "entities_appeared": [],
            "entities_new": [],
            "state_changes": [],
            "relationships_new": [],
            "chapter": None
        }

        self._load_state()

    def _now_progress_timestamp(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _ensure_state_schema(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """确保 state.json 具备运行所需的关键字段（尽量不破坏既有数据）。"""
        if not isinstance(state, dict):
            state = {}

        state.setdefault("project_info", {})
        state.setdefault("progress", {})
        state.setdefault("protagonist_state", {})

        # relationships: 旧版本可能是 list（实体关系），v5.0 运行态用 dict（人物关系/重要关系）
        relationships = state.get("relationships")
        if isinstance(relationships, list):
            state.setdefault("structured_relationships", [])
            if isinstance(state.get("structured_relationships"), list):
                state["structured_relationships"].extend(relationships)
            state["relationships"] = {}
        elif not isinstance(relationships, dict):
            state["relationships"] = {}

        state.setdefault("world_settings", {"power_system": [], "factions": [], "locations": []})
        state.setdefault("plot_threads", {"active_threads": [], "foreshadowing": []})
        state.setdefault("review_checkpoints", [])
        state.setdefault("chapter_meta", {})
        state.setdefault(
            "strand_tracker",
            {
                "last_quest_chapter": 0,
                "last_fire_chapter": 0,
                "last_constellation_chapter": 0,
                "current_dominant": "quest",
                "chapters_since_switch": 0,
                "history": [],
            },
        )

        entities_v3 = state.get("entities_v3")
        # v5.1 引入: entities_v3, alias_index, state_changes, structured_relationships 已迁移到 index.db
        # 不再在 state.json 中初始化或维护这些字段

        if not isinstance(state.get("disambiguation_warnings"), list):
            state["disambiguation_warnings"] = []

        if not isinstance(state.get("disambiguation_pending"), list):
            state["disambiguation_pending"] = []

        # progress 基础字段
        progress = state["progress"]
        if not isinstance(progress, dict):
            progress = {}
            state["progress"] = progress
        progress.setdefault("current_chapter", 0)
        progress.setdefault("total_words", 0)
        progress.setdefault("last_updated", self._now_progress_timestamp())

        return state

    def _load_state(self):
        """加载状态文件"""
        if self.config.state_file.exists():
            self._state = read_json_safe(self.config.state_file, default={})
            self._state = self._ensure_state_schema(self._state)
        else:
            self._state = self._ensure_state_schema({})

    def save_state(self):
        """
        保存状态文件（锁内重读 + 合并 + 原子写入）。

        解决多 Agent 并行下的“读-改-写覆盖”风险：
        - 获取锁
        - 重新读取磁盘最新 state.json
        - 仅合并本实例产生的增量（pending_*）
        - 原子化写入
        """
        # 无增量时不写入，避免无意义覆盖
        has_pending = any(
            [
                self._pending_entity_patches,
                self._pending_alias_entries,
                self._pending_state_changes,
                self._pending_structured_relationships,
                self._pending_disambiguation_warnings,
                self._pending_disambiguation_pending,
                self._pending_chapter_meta,
                self._pending_progress_chapter is not None,
                self._pending_progress_words_delta != 0,
                bool(self._pending_raw_state_mutations),
            ]
        )
        if not has_pending:
            return

        self.config.ensure_dirs()

        lock = filelock.FileLock(str(self._lock_path), timeout=10)
        try:
            with lock:
                disk_state = read_json_safe(self.config.state_file, default={})
                disk_state = self._ensure_state_schema(disk_state)

                # progress（合并为 max(chapter) + words_delta 累加）
                if self._pending_progress_chapter is not None or self._pending_progress_words_delta != 0:
                    progress = disk_state.get("progress", {})
                    if not isinstance(progress, dict):
                        progress = {}
                        disk_state["progress"] = progress

                    try:
                        current_chapter = int(progress.get("current_chapter", 0) or 0)
                    except (TypeError, ValueError):
                        current_chapter = 0

                    if self._pending_progress_chapter is not None:
                        progress["current_chapter"] = max(current_chapter, int(self._pending_progress_chapter))

                    if self._pending_progress_words_delta:
                        try:
                            total_words = int(progress.get("total_words", 0) or 0)
                        except (TypeError, ValueError):
                            total_words = 0
                        progress["total_words"] = total_words + int(self._pending_progress_words_delta)

                    progress["last_updated"] = self._now_progress_timestamp()

                # v5.1 引入: 强制使用 SQLite 模式，移除大数据字段
                # 确保 state.json 中不存在这些膨胀字段
                for field in ["entities_v3", "alias_index", "state_changes", "structured_relationships"]:
                    disk_state.pop(field, None)
                # 标记已迁移
                disk_state["_migrated_to_sqlite"] = True

                # disambiguation_warnings（追加去重 + 截断）
                if self._pending_disambiguation_warnings:
                    warnings_list = disk_state.get("disambiguation_warnings")
                    if not isinstance(warnings_list, list):
                        warnings_list = []
                        disk_state["disambiguation_warnings"] = warnings_list

                    def _warn_key(w: Dict[str, Any]) -> tuple:
                        return (
                            w.get("chapter"),
                            w.get("mention"),
                            w.get("chosen_id"),
                            w.get("confidence"),
                        )

                    existing_keys = {_warn_key(w) for w in warnings_list if isinstance(w, dict)}
                    for w in self._pending_disambiguation_warnings:
                        if not isinstance(w, dict):
                            continue
                        k = _warn_key(w)
                        if k in existing_keys:
                            continue
                        warnings_list.append(w)
                        existing_keys.add(k)

                    # 只保留最近 N 条，避免文件无限增长
                    max_keep = self.config.max_disambiguation_warnings
                    if len(warnings_list) > max_keep:
                        disk_state["disambiguation_warnings"] = warnings_list[-max_keep:]

                # disambiguation_pending（追加去重 + 截断）
                if self._pending_disambiguation_pending:
                    pending_list = disk_state.get("disambiguation_pending")
                    if not isinstance(pending_list, list):
                        pending_list = []
                        disk_state["disambiguation_pending"] = pending_list

                    def _pending_key(w: Dict[str, Any]) -> tuple:
                        return (
                            w.get("chapter"),
                            w.get("mention"),
                            w.get("suggested_id"),
                            w.get("confidence"),
                        )

                    existing_keys = {_pending_key(w) for w in pending_list if isinstance(w, dict)}
                    for w in self._pending_disambiguation_pending:
                        if not isinstance(w, dict):
                            continue
                        k = _pending_key(w)
                        if k in existing_keys:
                            continue
                        pending_list.append(w)
                        existing_keys.add(k)

                    max_keep = self.config.max_disambiguation_pending
                    if len(pending_list) > max_keep:
                        disk_state["disambiguation_pending"] = pending_list[-max_keep:]

                # chapter_meta（新增：按章节号覆盖写入）
                if self._pending_chapter_meta:
                    chapter_meta = disk_state.get("chapter_meta")
                    if not isinstance(chapter_meta, dict):
                        chapter_meta = {}
                        disk_state["chapter_meta"] = chapter_meta
                    chapter_meta.update(self._pending_chapter_meta)

                # raw state mutations（Bug fix 2026-04-13: state update --strand-dominant /
                # --add-foreshadowing 等直接改 _state 的子命令，由调用方登记 top-level key）
                if self._pending_raw_state_mutations:
                    for k in self._pending_raw_state_mutations:
                        if k in self._state:
                            disk_state[k] = self._state[k]

                # 原子写入（锁已持有，不再二次加锁）
                atomic_write_json(self.config.state_file, disk_state, use_lock=False, backup=True)

                # v5.1 引入: 同步到 SQLite（失败时保留 pending 以便重试）
                sqlite_pending_snapshot = self._snapshot_sqlite_pending()
                sqlite_sync_ok = self._sync_to_sqlite()

                # 同步内存为磁盘最新快照
                self._state = disk_state

                # state.json 侧 pending 已写盘，直接清空
                self._pending_disambiguation_warnings.clear()
                self._pending_disambiguation_pending.clear()
                self._pending_chapter_meta.clear()
                self._pending_progress_chapter = None
                self._pending_progress_words_delta = 0
                self._pending_raw_state_mutations.clear()

                # SQLite 侧 pending：成功后清空，失败则恢复快照（避免静默丢数据）
                if sqlite_sync_ok:
                    self._pending_entity_patches.clear()
                    self._pending_alias_entries.clear()
                    self._pending_state_changes.clear()
                    self._pending_structured_relationships.clear()
                    self._clear_pending_sqlite_data()
                else:
                    self._restore_sqlite_pending(sqlite_pending_snapshot)

        except filelock.Timeout:
            raise RuntimeError("无法获取 state.json 文件锁，请稍后重试")

    def _sync_to_sqlite(self) -> bool:
        """同步待处理数据到 SQLite（v5.1 引入，v5.4 沿用）"""
        if not self._sql_state_manager:
            return True

        # 方式1: 通过 process_chapter_result 收集的数据
        sqlite_data = self._pending_sqlite_data
        chapter = sqlite_data.get("chapter")

        # 记录已处理的 (entity_id, chapter) 组合，避免重复写入 appearances
        processed_appearances = set()

        if chapter is not None:
            try:
                self._sql_state_manager.process_chapter_entities(
                    chapter=chapter,
                    entities_appeared=sqlite_data.get("entities_appeared", []),
                    entities_new=sqlite_data.get("entities_new", []),
                    state_changes=sqlite_data.get("state_changes", []),
                    relationships_new=sqlite_data.get("relationships_new", [])
                )
                # 标记已处理的出场记录
                for entity in sqlite_data.get("entities_appeared", []):
                    if entity.get("id"):
                        processed_appearances.add((entity.get("id"), chapter))
                for entity in sqlite_data.get("entities_new", []):
                    eid = entity.get("suggested_id") or entity.get("id")
                    if eid:
                        processed_appearances.add((eid, chapter))
            except Exception as exc:
                logger.warning("SQLite sync failed (process_chapter_entities): %s", exc)
                return False

        # 方式2: 使用 add_entity/update_entity 收集的增量数据。
        # 数据缓存在 _pending_entity_patches 等变量中。
        return self._sync_pending_patches_to_sqlite(processed_appearances)

    def _sync_pending_patches_to_sqlite(self, processed_appearances: set = None) -> bool:
        """同步 _pending_entity_patches 等到 SQLite（v5.1 引入，v5.4 沿用）

        Args:
            processed_appearances: 已通过 process_chapter_entities 处理的 (entity_id, chapter) 集合，
                                   用于避免重复写入 appearances 表（防止覆盖 mentions）
        """
        if not self._sql_state_manager:
            return True

        if processed_appearances is None:
            processed_appearances = set()

        # 元数据字段（不应写入 current_json）
        METADATA_FIELDS = {"canonical_name", "tier", "desc", "is_protagonist", "is_archived"}

        try:
            from .sql_state_manager import EntityData
            from .index_manager import EntityMeta

            # 同步实体补丁
            for (entity_type, entity_id), patch in self._pending_entity_patches.items():
                if patch.base_entity:
                    # 新实体
                    entity_data = EntityData(
                        id=entity_id,
                        type=entity_type,
                        name=patch.base_entity.get("canonical_name", entity_id),
                        tier=patch.base_entity.get("tier", "装饰"),
                        desc=patch.base_entity.get("desc", ""),
                        current=patch.base_entity.get("current", {}),
                        aliases=[],
                        first_appearance=patch.base_entity.get("first_appearance", 0),
                        last_appearance=patch.base_entity.get("last_appearance", 0),
                        is_protagonist=patch.base_entity.get("is_protagonist", False)
                    )
                    self._sql_state_manager.upsert_entity(entity_data)

                    # 记录首次出场（跳过已处理的，避免覆盖 mentions）
                    if patch.appearance_chapter is not None:
                        if (entity_id, patch.appearance_chapter) not in processed_appearances:
                            self._sql_state_manager._index_manager.record_appearance(
                                entity_id=entity_id,
                                chapter=patch.appearance_chapter,
                                mentions=[entity_data.name],
                                confidence=1.0,
                                skip_if_exists=True  # 关键：不覆盖已有记录
                            )
                else:
                    # 更新现有实体
                    has_metadata_updates = bool(patch.top_updates and
                                                 any(k in METADATA_FIELDS for k in patch.top_updates))

                    # 非元数据的 top_updates 应该当作 current 更新
                    # 例如：realm, layer, location 等状态字段
                    non_metadata_top_updates = {
                        k: v for k, v in patch.top_updates.items()
                        if k not in METADATA_FIELDS
                    } if patch.top_updates else {}

                    # 合并 current_updates 和非元数据的 top_updates
                    effective_current_updates = {**non_metadata_top_updates}
                    if patch.current_updates:
                        effective_current_updates.update(patch.current_updates)

                    if has_metadata_updates:
                        # 有元数据更新：使用 upsert_entity(update_metadata=True)
                        existing = self._sql_state_manager.get_entity(entity_id)
                        if existing:
                            # 合并 current
                            current = existing.get("current_json", {})
                            if isinstance(current, str):
                                import json
                                current = json.loads(current) if current else {}
                            if effective_current_updates:
                                current.update(effective_current_updates)

                            new_canonical_name = patch.top_updates.get("canonical_name")
                            old_canonical_name = existing.get("canonical_name", "")

                            entity_meta = EntityMeta(
                                id=entity_id,
                                type=existing.get("type", entity_type),
                                canonical_name=new_canonical_name or old_canonical_name,
                                tier=patch.top_updates.get("tier", existing.get("tier", "装饰")),
                                desc=patch.top_updates.get("desc", existing.get("desc", "")),
                                current=current,
                                first_appearance=existing.get("first_appearance", 0),
                                last_appearance=patch.appearance_chapter or existing.get("last_appearance", 0),
                                is_protagonist=patch.top_updates.get("is_protagonist", existing.get("is_protagonist", False)),
                                is_archived=patch.top_updates.get("is_archived", existing.get("is_archived", False))
                            )
                            self._sql_state_manager._index_manager.upsert_entity(entity_meta, update_metadata=True)

                            # 如果 canonical_name 改名，自动注册新名字为 alias
                            if new_canonical_name and new_canonical_name != old_canonical_name:
                                self._sql_state_manager.register_alias(
                                    new_canonical_name, entity_id, existing.get("type", entity_type)
                                )
                    elif effective_current_updates:
                        # 只有 current 更新（包括非元数据的 top_updates）
                        self._sql_state_manager.update_entity_current(entity_id, effective_current_updates)

                    # 更新 last_appearance 并记录出场
                    if patch.appearance_chapter is not None:
                        self._sql_state_manager._update_last_appearance(entity_id, patch.appearance_chapter)
                        # 补充 appearances 记录
                        # 使用 skip_if_exists=True 避免覆盖已有记录的 mentions
                        if (entity_id, patch.appearance_chapter) not in processed_appearances:
                            self._sql_state_manager._index_manager.record_appearance(
                                entity_id=entity_id,
                                chapter=patch.appearance_chapter,
                                mentions=[],
                                confidence=1.0,
                                skip_if_exists=True  # 关键：不覆盖已有记录
                            )

            # 同步别名
            for alias, entries in self._pending_alias_entries.items():
                for entry in entries:
                    entity_type = entry.get("type")
                    entity_id = entry.get("id")
                    if entity_type and entity_id:
                        self._sql_state_manager.register_alias(alias, entity_id, entity_type)

            # 同步状态变化
            for change in self._pending_state_changes:
                self._sql_state_manager.record_state_change(
                    entity_id=change.get("entity_id", ""),
                    field=change.get("field", ""),
                    old_value=change.get("old", change.get("old_value", "")),
                    new_value=change.get("new", change.get("new_value", "")),
                    reason=change.get("reason", ""),
                    chapter=change.get("chapter", 0)
                )

            # 同步关系
            for rel in self._pending_structured_relationships:
                self._sql_state_manager.upsert_relationship(
                    from_entity=rel.get("from_entity", ""),
                    to_entity=rel.get("to_entity", ""),
                    type=rel.get("type", "相识"),
                    description=rel.get("description", ""),
                    chapter=rel.get("chapter", 0)
                )

            return True

        except Exception as e:
            # SQLite 同步失败时记录警告（不中断主流程）
            logger.warning("SQLite sync failed: %s", e)
            return False

    def _snapshot_sqlite_pending(self) -> Dict[str, Any]:
        """抓取 SQLite 侧 pending 快照，用于同步失败回滚内存队列。"""
        return {
            "entity_patches": deepcopy(self._pending_entity_patches),
            "alias_entries": deepcopy(self._pending_alias_entries),
            "state_changes": deepcopy(self._pending_state_changes),
            "structured_relationships": deepcopy(self._pending_structured_relationships),
            "sqlite_data": deepcopy(self._pending_sqlite_data),
        }

    def _restore_sqlite_pending(self, snapshot: Dict[str, Any]) -> None:
        """恢复 SQLite 侧 pending 快照，避免同步失败后数据静默丢失。"""
        self._pending_entity_patches = snapshot.get("entity_patches", {})
        self._pending_alias_entries = snapshot.get("alias_entries", {})
        self._pending_state_changes = snapshot.get("state_changes", [])
        self._pending_structured_relationships = snapshot.get("structured_relationships", [])
        self._pending_sqlite_data = snapshot.get("sqlite_data", {
            "entities_appeared": [],
            "entities_new": [],
            "state_changes": [],
            "relationships_new": [],
            "chapter": None,
        })

    def _clear_pending_sqlite_data(self):
        """清空待同步的 SQLite 数据"""
        self._pending_sqlite_data = {
            "entities_appeared": [],
            "entities_new": [],
            "state_changes": [],
            "relationships_new": [],
            "chapter": None
        }

    # ==================== 进度管理 ====================

    def get_current_chapter(self) -> int:
        """获取当前章节号"""
        return self._state.get("progress", {}).get("current_chapter", 0)

    def update_progress(self, chapter: int, words: int = 0):
        """更新进度"""
        if "progress" not in self._state:
            self._state["progress"] = {}
        self._state["progress"]["current_chapter"] = chapter
        if words > 0:
            total = self._state["progress"].get("total_words", 0)
            self._state["progress"]["total_words"] = total + words

        # 记录增量：锁内合并时用 max(chapter) + words_delta 累加
        if self._pending_progress_chapter is None:
            self._pending_progress_chapter = chapter
        else:
            self._pending_progress_chapter = max(self._pending_progress_chapter, chapter)
        if words > 0:
            self._pending_progress_words_delta += int(words)

    # ==================== 实体管理 (v5.1 SQLite-first) ====================

    def get_entity(self, entity_id: str, entity_type: str = None) -> Optional[Dict]:
        """获取实体（v5.1 引入：优先从 SQLite 读取）"""
        # v5.1 引入: 优先从 SQLite 读取
        if self._sql_state_manager:
            entity = self._sql_state_manager._index_manager.get_entity(entity_id)
            if entity:
                return entity

        # 回退到内存 state (兼容未迁移场景)
        entities_v3 = self._state.get("entities_v3", {})
        if entity_type:
            return entities_v3.get(entity_type, {}).get(entity_id)

        # 遍历所有类型查找
        for type_name, entities in entities_v3.items():
            if entity_id in entities:
                return entities[entity_id]
        return None

    def get_entity_type(self, entity_id: str) -> Optional[str]:
        """获取实体所属类型"""
        # v5.1 引入: 优先从 SQLite 读取
        if self._sql_state_manager:
            entity = self._sql_state_manager._index_manager.get_entity(entity_id)
            if entity:
                return entity.get("type")

        # 回退到内存 state
        for type_name, entities in self._state.get("entities_v3", {}).items():
            if entity_id in entities:
                return type_name
        return None

    def get_all_entities(self) -> Dict[str, Dict]:
        """获取所有实体（扁平化视图）"""
        # v5.1 引入: 优先从 SQLite 读取
        if self._sql_state_manager:
            result = {}
            for entity_type in self.ENTITY_TYPES:
                entities = self._sql_state_manager._index_manager.get_entities_by_type(entity_type)
                for e in entities:
                    eid = e.get("id")
                    if eid:
                        result[eid] = {**e, "type": entity_type}
            if result:
                return result

        # 回退到内存 state
        result = {}
        for type_name, entities in self._state.get("entities_v3", {}).items():
            for eid, e in entities.items():
                result[eid] = {**e, "type": type_name}
        return result

    def get_entities_by_type(self, entity_type: str) -> Dict[str, Dict]:
        """按类型获取实体"""
        # v5.1 引入: 优先从 SQLite 读取
        if self._sql_state_manager:
            entities = self._sql_state_manager._index_manager.get_entities_by_type(entity_type)
            if entities:
                return {e.get("id"): e for e in entities if e.get("id")}

        # 回退到内存 state
        return self._state.get("entities_v3", {}).get(entity_type, {})

    def get_entities_by_tier(self, tier: str) -> Dict[str, Dict]:
        """按层级获取实体"""
        # v5.1 引入: 优先从 SQLite 读取
        if self._sql_state_manager:
            result = {}
            for entity_type in self.ENTITY_TYPES:
                entities = self._sql_state_manager._index_manager.get_entities_by_tier(tier)
                for e in entities:
                    eid = e.get("id")
                    if eid and e.get("type") == entity_type:
                        result[eid] = {**e, "type": entity_type}
            if result:
                return result

        # 回退到内存 state
        result = {}
        for type_name, entities in self._state.get("entities_v3", {}).items():
            for eid, e in entities.items():
                if e.get("tier") == tier:
                    result[eid] = {**e, "type": type_name}
        return result

    def add_entity(self, entity: EntityState) -> bool:
        """添加新实体（v5.0 entities_v3 格式，v5.4 沿用）"""
        entity_type = entity.type
        if entity_type not in self.ENTITY_TYPES:
            entity_type = "角色"

        if "entities_v3" not in self._state:
            self._state["entities_v3"] = {t: {} for t in self.ENTITY_TYPES}

        if entity_type not in self._state["entities_v3"]:
            self._state["entities_v3"][entity_type] = {}

        # 检查是否已存在
        if entity.id in self._state["entities_v3"][entity_type]:
            return False

        # 转换为 v3 格式
        v3_entity = {
            "canonical_name": entity.name,
            "tier": entity.tier,
            "desc": "",
            "current": entity.attributes,
            "first_appearance": entity.first_appearance,
            "last_appearance": entity.last_appearance,
            "history": []
        }
        self._state["entities_v3"][entity_type][entity.id] = v3_entity

        # 记录实体补丁（新建：仅填充缺失字段，避免覆盖并发写入）
        patch = self._pending_entity_patches.get((entity_type, entity.id))
        if patch is None:
            patch = _EntityPatch(entity_type=entity_type, entity_id=entity.id)
            self._pending_entity_patches[(entity_type, entity.id)] = patch
        patch.replace = True
        patch.base_entity = v3_entity

        # v5.1 引入: 注册别名到 index.db (通过 SQLStateManager)
        if self._sql_state_manager:
            self._sql_state_manager._index_manager.register_alias(entity.name, entity.id, entity_type)
            for alias in entity.aliases:
                if alias:
                    self._sql_state_manager._index_manager.register_alias(alias, entity.id, entity_type)

        return True

    def _register_alias_internal(self, entity_id: str, entity_type: str, alias: str):
        """内部方法：注册别名到 index.db（v5.1 引入）"""
        if not alias:
            return
        # v5.1 引入: 直接写入 SQLite
        if self._sql_state_manager:
            self._sql_state_manager._index_manager.register_alias(alias, entity_id, entity_type)

    def update_entity(self, entity_id: str, updates: Dict[str, Any], entity_type: str = None) -> bool:
        """更新实体属性（v5.0 引入，v5.4 沿用）"""
        # v5.1+ SQLite-first:
        # - entity_type 可能来自 SQLite（entities 表），但 state.json 不再持久化 entities_v3。
        # - 因此不能假设 self._state["entities_v3"][type][id] 一定存在（issues7 日志曾 KeyError）。
        resolved_type = entity_type or self.get_entity_type(entity_id)
        if not resolved_type:
            return False
        if resolved_type not in self.ENTITY_TYPES:
            resolved_type = "角色"

        # 仅在内存存在 v3 实体时才更新内存快照（不强行创建，避免 state.json 再膨胀）
        entities_v3 = self._state.get("entities_v3")
        entity = None
        if isinstance(entities_v3, dict):
            bucket = entities_v3.get(resolved_type)
            if isinstance(bucket, dict):
                entity = bucket.get(entity_id)

        # SQLite 启用时，即使内存实体缺失，也要记录 patch，确保 current 能增量写回 index.db
        patch = None
        if self._sql_state_manager:
            patch = self._pending_entity_patches.get((resolved_type, entity_id))
            if patch is None:
                patch = _EntityPatch(entity_type=resolved_type, entity_id=entity_id)
                self._pending_entity_patches[(resolved_type, entity_id)] = patch

        if entity is None and patch is None:
            return False

        did_any = False
        for key, value in updates.items():
            if key == "attributes" and isinstance(value, dict):
                if entity is not None:
                    if "current" not in entity:
                        entity["current"] = {}
                    entity["current"].update(value)
                if patch is not None:
                    patch.current_updates.update(value)
                did_any = True
            elif key == "current" and isinstance(value, dict):
                if entity is not None:
                    if "current" not in entity:
                        entity["current"] = {}
                    entity["current"].update(value)
                if patch is not None:
                    patch.current_updates.update(value)
                did_any = True
            else:
                if entity is not None:
                    entity[key] = value
                if patch is not None:
                    patch.top_updates[key] = value
                did_any = True

        return did_any

    def update_entity_appearance(self, entity_id: str, chapter: int, entity_type: str = None):
        """更新实体出场章节"""
        if not entity_type:
            entity_type = self.get_entity_type(entity_id)
        if not entity_type:
            return

        entities_v3 = self._state.get("entities_v3")
        if not isinstance(entities_v3, dict):
            entities_v3 = {t: {} for t in self.ENTITY_TYPES}
            self._state["entities_v3"] = entities_v3
        entities_v3.setdefault(entity_type, {})

        entity = entities_v3[entity_type].get(entity_id)
        if entity:
            if entity.get("first_appearance", 0) == 0:
                entity["first_appearance"] = chapter
            entity["last_appearance"] = chapter

            # 记录补丁：锁内应用 first=min(non-zero), last=max
            patch = self._pending_entity_patches.get((entity_type, entity_id))
            if patch is None:
                patch = _EntityPatch(entity_type=entity_type, entity_id=entity_id)
                self._pending_entity_patches[(entity_type, entity_id)] = patch
            if patch.appearance_chapter is None:
                patch.appearance_chapter = chapter
            else:
                patch.appearance_chapter = max(int(patch.appearance_chapter), int(chapter))

    # ==================== 状态变化记录 ====================

    def record_state_change(
        self,
        entity_id: str,
        field: str,
        old_value: Any,
        new_value: Any,
        reason: str,
        chapter: int
    ):
        """记录状态变化"""
        if "state_changes" not in self._state:
            self._state["state_changes"] = []

        change = StateChange(
            entity_id=entity_id,
            field=field,
            old_value=old_value,
            new_value=new_value,
            reason=reason,
            chapter=chapter
        )
        change_dict = asdict(change)
        self._state["state_changes"].append(change_dict)
        self._pending_state_changes.append(change_dict)

        # 同时更新实体属性
        self.update_entity(entity_id, {"attributes": {field: new_value}})

    def get_state_changes(self, entity_id: Optional[str] = None) -> List[Dict]:
        """获取状态变化历史"""
        changes = self._state.get("state_changes", [])
        if entity_id:
            changes = [c for c in changes if c.get("entity_id") == entity_id]
        return changes

    # ==================== 关系管理 ====================

    def add_relationship(
        self,
        from_entity: str,
        to_entity: str,
        rel_type: str,
        description: str,
        chapter: int
    ):
        """添加关系"""
        rel = Relationship(
            from_entity=from_entity,
            to_entity=to_entity,
            type=rel_type,
            description=description,
            chapter=chapter
        )

        # v5.0 引入: 实体关系存入 structured_relationships，避免与 relationships(人物关系字典) 冲突
        if "structured_relationships" not in self._state:
            self._state["structured_relationships"] = []
        rel_dict = asdict(rel)
        self._state["structured_relationships"].append(rel_dict)
        self._pending_structured_relationships.append(rel_dict)

    def get_relationships(self, entity_id: Optional[str] = None) -> List[Dict]:
        """获取关系列表"""
        rels = self._state.get("structured_relationships", [])
        if entity_id:
            rels = [
                r for r in rels
                if r.get("from_entity") == entity_id or r.get("to_entity") == entity_id
            ]
        return rels

    # ==================== 批量操作 ====================

    def _record_disambiguation(self, chapter: int, uncertain_items: Any) -> List[str]:
        """
        记录消歧反馈到 state.json，便于 Writer/Context Agent 感知风险。

        约定：
        - >= extraction_confidence_medium：写入 disambiguation_warnings（采用但警告）
        - < extraction_confidence_medium：写入 disambiguation_pending（需人工确认）
        """
        if not isinstance(uncertain_items, list) or not uncertain_items:
            return []

        warnings: List[str] = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for item in uncertain_items:
            if not isinstance(item, dict):
                continue

            mention = str(item.get("mention", "") or "").strip()
            if not mention:
                continue

            raw_conf = item.get("confidence", 0.0)
            try:
                confidence = float(raw_conf)
            except (TypeError, ValueError):
                confidence = 0.0

            # 候选：支持 [{"type","id"}...] 或 ["id1","id2"] 两种形式
            candidates_raw = item.get("candidates", [])
            candidates: List[Dict[str, str]] = []
            if isinstance(candidates_raw, list):
                for c in candidates_raw:
                    if isinstance(c, dict):
                        cid = str(c.get("id", "") or "").strip()
                        ctype = str(c.get("type", "") or "").strip()
                        entry: Dict[str, str] = {}
                        if ctype:
                            entry["type"] = ctype
                        if cid:
                            entry["id"] = cid
                        if entry:
                            candidates.append(entry)
                    else:
                        cid = str(c).strip()
                        if cid:
                            candidates.append({"id": cid})

            entity_type = str(item.get("type", "") or "").strip()
            suggested_id = str(item.get("suggested", "") or "").strip()

            adopted_raw = item.get("adopted", None)
            chosen_id = ""
            if isinstance(adopted_raw, str):
                chosen_id = adopted_raw.strip()
            elif adopted_raw is True:
                chosen_id = suggested_id
            else:
                # 兼容字段名：entity_id / chosen_id
                chosen_id = str(item.get("entity_id") or item.get("chosen_id") or "").strip() or suggested_id

            context = str(item.get("context", "") or "").strip()
            note = str(item.get("warning", "") or "").strip()

            record: Dict[str, Any] = {
                "chapter": int(chapter),
                "mention": mention,
                "type": entity_type,
                "suggested_id": suggested_id,
                "chosen_id": chosen_id,
                "confidence": confidence,
                "candidates": candidates,
                "context": context,
                "note": note,
                "created_at": now,
            }

            if confidence >= float(self.config.extraction_confidence_medium):
                self._state.setdefault("disambiguation_warnings", []).append(record)
                self._pending_disambiguation_warnings.append(record)
                chosen_part = f" → {chosen_id}" if chosen_id else ""
                warnings.append(f"消歧警告: {mention}{chosen_part} (confidence: {confidence:.2f})")
            else:
                self._state.setdefault("disambiguation_pending", []).append(record)
                self._pending_disambiguation_pending.append(record)
                warnings.append(f"消歧需人工确认: {mention} (confidence: {confidence:.2f})")

        return warnings

    def _count_chapter_chars(self, chapter: int) -> int:
        """从实际章节文件统计汉字数（权威字数数据源）。失败返回 0。"""
        try:
            import re as _re
            from pathlib import Path as _Path
            padded = f"{int(chapter):04d}"
            正文_dir = _Path(self.config.project_root) / "正文"
            candidates = list(正文_dir.glob(f"第{padded}章-*.md")) + list(正文_dir.glob(f"第{padded}章.md"))
            if not candidates:
                return 0
            text = candidates[0].read_text(encoding="utf-8")
            return len(_re.findall(r"[\u4e00-\u9fff]", text))
        except Exception:
            return 0

    def _count_chapter_scenes(self, chapter: int) -> int:
        """查询 index.db 中该章节 scenes 数。失败返回 0。"""
        try:
            import sqlite3 as _sqlite3
            from pathlib import Path as _Path
            db = _Path(self.config.project_root) / ".webnovel" / "index.db"
            if not db.exists():
                return 0
            conn = _sqlite3.connect(str(db))
            try:
                row = conn.execute(
                    "SELECT COUNT(*) FROM scenes WHERE chapter = ?", (int(chapter),)
                ).fetchone()
                return int(row[0]) if row else 0
            finally:
                conn.close()
        except Exception:
            return 0

    def _query_checker_scores(self, chapter: int) -> Optional[Dict[str, Any]]:
        """查询 index.db review_metrics 表该章节最新评分。失败返回 None。"""
        try:
            import sqlite3 as _sqlite3
            from pathlib import Path as _Path
            db = _Path(self.config.project_root) / ".webnovel" / "index.db"
            if not db.exists():
                return None
            conn = _sqlite3.connect(str(db))
            try:
                row = conn.execute(
                    "SELECT overall_score, dimension_scores FROM review_metrics "
                    "WHERE start_chapter <= ? AND end_chapter >= ? "
                    "ORDER BY created_at DESC LIMIT 1",
                    (int(chapter), int(chapter)),
                ).fetchone()
                if not row:
                    return None
                overall, dims_json = row
                result: Dict[str, Any] = {"overall": overall}
                if dims_json:
                    try:
                        dims = json.loads(dims_json)
                        if isinstance(dims, dict):
                            result.update(dims)
                    except Exception:
                        pass
                return result
            finally:
                conn.close()
        except Exception:
            return None

    def _backfill_chapter_meta(self, chapter: int, chapter_meta: Dict[str, Any]) -> None:
        """集中修复 Data Agent 产生的 chapter_meta 字段漂移。

        根本原因：data-agent.md 使用嵌套结构（hook.strength / hook.type），
        但 audit CLI 的 B9 检查要求扁平字段。word_count 和 strand_dominant
        无权威源约束。本方法是唯一的补全入口。
        """
        # --- 1. word_count：始终以实际文件汉字数为权威源 ---
        # 正文文件是 source of truth。允许 <1% 微小偏差，超出则强制使用文件计数。
        real_wc = self._count_chapter_chars(chapter)
        if real_wc > 0:
            existing_wc = chapter_meta.get("word_count")
            if not isinstance(existing_wc, int) or existing_wc <= 0:
                chapter_meta["word_count"] = real_wc
            elif abs(real_wc - existing_wc) / max(real_wc, 1) > 0.01:
                chapter_meta["word_count"] = real_wc

        # --- 2. strand_dominant：从 strand_tracker 权威读取 ---
        tracker = self._state.get("strand_tracker", {}) or {}
        history = tracker.get("history", []) or []
        matched_strand = None
        for entry in reversed(history):
            if isinstance(entry, dict) and int(entry.get("chapter", -1)) == int(chapter):
                matched_strand = entry.get("strand")
                break
        if matched_strand:
            chapter_meta["strand_dominant"] = matched_strand
        elif not chapter_meta.get("strand_dominant"):
            chapter_meta["strand_dominant"] = tracker.get("current_dominant", "quest")

        # --- 3. 扁平字段从嵌套补齐（hook_strength/hook_type/hook_content）---
        hook = chapter_meta.get("hook")
        if isinstance(hook, dict):
            if "hook_strength" not in chapter_meta and hook.get("strength"):
                chapter_meta["hook_strength"] = hook["strength"]
            if "hook_type" not in chapter_meta and hook.get("type"):
                chapter_meta["hook_type"] = hook["type"]
            if "hook_content" not in chapter_meta and hook.get("content"):
                chapter_meta["hook_content"] = hook["content"]

        # --- 4. scene_count：从 index.db 反查 ---
        if "scene_count" not in chapter_meta or not chapter_meta.get("scene_count"):
            sc = self._count_chapter_scenes(chapter)
            if sc > 0:
                chapter_meta["scene_count"] = sc

        # --- 5. 时间戳：创建/更新时间 ---
        now_iso = datetime.now(timezone.utc).isoformat()
        meta_key = f"{int(chapter):04d}"
        existing = (self._state.get("chapter_meta") or {}).get(meta_key) or {}
        if "created_at" not in chapter_meta:
            chapter_meta["created_at"] = existing.get("created_at") or now_iso
        chapter_meta["updated_at"] = now_iso

        # --- 6. checker_scores：从 review_metrics 反查 ---
        if "checker_scores" not in chapter_meta or not chapter_meta.get("checker_scores"):
            scores = self._query_checker_scores(chapter)
            if scores:
                chapter_meta["checker_scores"] = scores

    def process_chapter_result(self, chapter: int, result: Dict) -> List[str]:
        """
        处理 Data Agent 的章节处理结果（v5.1 引入，v5.4 沿用）

        输入格式:
        - entities_appeared: 出场实体列表
        - entities_new: 新实体列表
        - state_changes: 状态变化列表
        - relationships_new: 新关系列表

        返回警告列表
        """
        warnings = []

        # v5.1 引入: 记录章节号用于 SQLite 同步
        self._pending_sqlite_data["chapter"] = chapter

        # 处理出场实体
        for entity in result.get("entities_appeared", []):
            entity_id = entity.get("id")
            entity_type = entity.get("type")
            if entity_id:
                self.update_entity_appearance(entity_id, chapter, entity_type)
                # v5.1 引入: 缓存用于 SQLite 同步
                self._pending_sqlite_data["entities_appeared"].append(entity)

        # 处理新实体
        for entity in result.get("entities_new", []):
            entity_id = entity.get("suggested_id") or entity.get("id")
            if entity_id and entity_id != "NEW":
                new_entity = EntityState(
                    id=entity_id,
                    name=entity.get("name", ""),
                    type=entity.get("type", "角色"),
                    tier=entity.get("tier", "装饰"),
                    aliases=entity.get("mentions", []),
                    first_appearance=chapter,
                    last_appearance=chapter
                )
                if not self.add_entity(new_entity):
                    warnings.append(f"实体已存在: {entity_id}")
                # v5.1 引入: 缓存用于 SQLite 同步
                self._pending_sqlite_data["entities_new"].append(entity)

        # 处理状态变化
        for change in result.get("state_changes", []):
            self.record_state_change(
                entity_id=change.get("entity_id", ""),
                field=change.get("field", ""),
                old_value=change.get("old"),
                new_value=change.get("new"),
                reason=change.get("reason", ""),
                chapter=chapter
            )
            # v5.1 引入: 缓存用于 SQLite 同步
            self._pending_sqlite_data["state_changes"].append(change)

        # 处理关系
        for rel in result.get("relationships_new", []):
            self.add_relationship(
                from_entity=rel.get("from", ""),
                to_entity=rel.get("to", ""),
                rel_type=rel.get("type", ""),
                description=rel.get("description", ""),
                chapter=chapter
            )
            # v5.1 引入: 缓存用于 SQLite 同步
            self._pending_sqlite_data["relationships_new"].append(rel)

        # 处理消歧不确定项（不影响实体写入，但必须对 Writer 可见）
        warnings.extend(self._record_disambiguation(chapter, result.get("uncertain", [])))

        # 写入 chapter_meta（钩子/模式/结束状态）
        chapter_meta = result.get("chapter_meta")
        if isinstance(chapter_meta, dict):
            meta_key = f"{int(chapter):04d}"
            # Data Agent 自由填充的 chapter_meta 常出现 3 类漂移，此处集中兜底：
            # 1. word_count 缺失或为 0 → 从实际正文重新统计（权威数据源）
            # 2. strand_dominant 缺失或硬编码为默认 "quest" → 从 strand_tracker 取
            # 3. audit B9 要求的扁平字段（hook_strength/scene_count/...）→ 从嵌套字段补齐
            self._backfill_chapter_meta(chapter, chapter_meta)
            self._state.setdefault("chapter_meta", {})
            self._state["chapter_meta"][meta_key] = chapter_meta
            self._pending_chapter_meta[meta_key] = chapter_meta

        # 更新进度
        self.update_progress(chapter)

        # 同步主角状态（entities_v3 → protagonist_state）
        self.sync_protagonist_from_entity()

        return warnings

    # ==================== 导出 ====================

    def export_for_context(self) -> Dict:
        """导出用于上下文的精简版状态（v5.0 引入，v5.4 沿用）"""
        # 从 entities_v3 构建精简视图
        entities_flat = {}
        for type_name, entities in self._state.get("entities_v3", {}).items():
            for eid, e in entities.items():
                entities_flat[eid] = {
                    "name": e.get("canonical_name", eid),
                    "type": type_name,
                    "tier": e.get("tier", "装饰"),
                    "current": e.get("current", {})
                }

        return {
            "progress": self._state.get("progress", {}),
            "entities": entities_flat,
            # v5.1 引入: alias_index 已迁移到 index.db，这里返回空（兼容性）
            "alias_index": {},
            "recent_changes": [],  # v5.1 引入: 从 index.db 查询
            "disambiguation": {
                "warnings": self._state.get("disambiguation_warnings", [])[-self.config.export_disambiguation_slice:],
                "pending": self._state.get("disambiguation_pending", [])[-self.config.export_disambiguation_slice:],
            },
        }

    # ==================== 主角同步 ====================

    def get_protagonist_entity_id(self) -> Optional[str]:
        """获取主角实体 ID（通过 is_protagonist 标记或 SQLite 查询）"""
        # 方式1: 通过 SQLStateManager 查询 (v5.1)
        if self._sql_state_manager:
            protagonist = self._sql_state_manager.get_protagonist()
            if protagonist:
                return protagonist.get("id")

        # 方式2: 通过 protagonist_state.name 查找别名
        protag_name = self._state.get("protagonist_state", {}).get("name")
        if protag_name and self._sql_state_manager:
            entities = self._sql_state_manager._index_manager.get_entities_by_alias(protag_name)
            for entry in entities:
                if entry.get("type") == "角色":
                    return entry.get("id")

        return None

    def sync_protagonist_from_entity(self, entity_id: str = None):
        """
        将主角实体的状态同步到 protagonist_state (v5.1: 从 SQLite 读取)

        用于确保 consistency-checker 等依赖 protagonist_state 的组件获取最新数据
        """
        if entity_id is None:
            entity_id = self.get_protagonist_entity_id()
        if entity_id is None:
            return

        entity = self.get_entity(entity_id, "角色")
        if not entity:
            return

        current = entity.get("current")
        if not isinstance(current, dict):
            current = entity.get("current_json", {})
        if isinstance(current, str):
            try:
                current = json.loads(current) if current else {}
            except (json.JSONDecodeError, TypeError):
                current = {}
        if not isinstance(current, dict):
            current = {}
        protag = self._state.setdefault("protagonist_state", {})

        # 同步境界
        if "realm" in current:
            power = protag.setdefault("power", {})
            power["realm"] = current["realm"]
            if "layer" in current:
                power["layer"] = current["layer"]

        # 同步位置
        if "location" in current:
            loc = protag.setdefault("location", {})
            loc["current"] = current["location"]
            if "last_chapter" in current:
                loc["last_chapter"] = current["last_chapter"]

    def sync_protagonist_to_entity(self, entity_id: str = None):
        """
        将 protagonist_state 同步到 entities_v3 中的主角实体

        用于初始化或手动编辑 protagonist_state 后保持一致性
        """
        if entity_id is None:
            entity_id = self.get_protagonist_entity_id()
        if entity_id is None:
            return

        protag = self._state.get("protagonist_state", {})
        if not protag:
            return

        updates = {}

        # 同步境界
        power = protag.get("power", {})
        if power.get("realm"):
            updates["realm"] = power["realm"]
        if power.get("layer"):
            updates["layer"] = power["layer"]

        # 同步位置
        loc = protag.get("location", {})
        if loc.get("current"):
            updates["location"] = loc["current"]

        if updates:
            self.update_entity(entity_id, updates, "角色")


# ==================== CLI 接口 ====================

def main():
    import argparse
    import sys
    from pydantic import ValidationError
    from .cli_output import print_success, print_error
    from .cli_args import normalize_global_project_root, load_json_arg
    from .schemas import validate_data_agent_output, format_validation_error, normalize_data_agent_output
    from .index_manager import IndexManager

    parser = argparse.ArgumentParser(description="State Manager CLI (v5.4)")
    parser.add_argument("--project-root", type=str, help="项目根目录")

    subparsers = parser.add_subparsers(dest="command")

    # 读取进度
    subparsers.add_parser("get-progress")

    # Round 19 Phase E · 跨卷规划数据读取（upstream@3e36417 借鉴）
    # plan 阶段下卷规划前必须读最近 N 章已写真实数据（hook_close / unresolved_loops / overall_score）
    recent_parser = subparsers.add_parser(
        "get-recent-meta",
        help="取最近 N 章 chapter_meta 摘要供 plan 阶段读 write history",
    )
    recent_parser.add_argument(
        "--last-n", type=int, default=10, help="取最近 N 章（默认 10）"
    )

    # 获取实体
    get_entity_parser = subparsers.add_parser("get-entity")
    get_entity_parser.add_argument("--id", required=True)

    # 列出实体
    list_parser = subparsers.add_parser("list-entities")
    list_parser.add_argument("--type", help="按类型过滤")
    list_parser.add_argument("--tier", help="按层级过滤")

    # 处理章节结果
    process_parser = subparsers.add_parser("process-chapter")
    process_parser.add_argument("--chapter", type=int, required=True, help="章节号")
    process_parser.add_argument("--data", required=True, help="JSON 格式的处理结果")

    # update subcommand: let data-agent cleanly mutate strand_tracker / plot_threads
    # instead of manually atomic-writing state.json (which bypasses locks)
    update_parser = subparsers.add_parser("update", help="细粒度更新 state.json（strand_tracker/伏笔/chapter_meta 字段/protagonist_state 冗余显示字段）")
    update_parser.add_argument("--strand-dominant", help='JSON: {"chapter":N,"dominant":"quest","sub":"fire"}')
    update_parser.add_argument("--add-foreshadowing", help='JSON: {"id":"F01","description":"...","planted_chapter":N,"urgency":30,"level":"主线"}')
    update_parser.add_argument("--resolve-foreshadowing", help='JSON: {"id":"F01","resolution":"...","resolved_chapter":N}')
    # Round 15.2 (2026-04-23)：补全 chapter_meta 字段级 CLI + protagonist_state 冗余字段同步 CLI
    # 根因：Ch5 Step 5 后 hygiene_check H9 报 P1 warn "chapter_meta.0005.overall_score=None"；
    #        同时 data-agent 通过 SQL 权威源更新了 hourglass 和 location，但 state.json 的
    #        冗余显示字段无 CLI 路径同步，只能违规手改。本补丁根治该 gap。
    update_parser.add_argument("--set-chapter-meta-field", help='JSON: {"chapter":N,"field":"overall_score","value":89}（field 支持白名单：overall_score/narrative_version/naturalness_verdict/naturalness_score/reader_critic_verdict/reader_critic_score/strand_dominant/word_count/chapter_type/review_score）')
    # Round 17.2 · Ch8 P0-R3 根治（2026-04-24）：SKILL.md Step 4.5 CLI 幻觉补实
    update_parser.add_argument(
        "--set-checker-score",
        help='JSON: {"chapter":N,"checker":"pacing-checker","score":90}（canonical key；同步更新 checker_scores.overall 为 13 checker 平均）',
    )
    update_parser.add_argument(
        "--append-recheck",
        help='JSON: {"chapter":N,"checker":"pacing-checker","before":58,"after":90,"reason":"..."}（追加到 chapter_meta.post_polish_recheck；Step 4.5 选择性复测产物）',
    )
    update_parser.add_argument("--sync-protagonist-display", help='JSON: {"hourglass_remaining":28,"location_current":"堂屋·雨夜·D-25","vital_force_current":80}（protagonist_state 冗余显示字段同步 · SQL 权威源改过后手工 sync）')
    # Round 18.2 · 2026-04-25 · Ch11 RCA #4 根治：progress.total_words 自动累加 CLI
    # 根因：data-agent Step J 后 progress.total_words 未自动累加（state_manager 缺入口）。
    # 用户需手动加，违反 feedback_no_manual_state_edits。本补丁加 --add-words 入口。
    update_parser.add_argument(
        "--add-words",
        help='JSON: {"chapter":N,"words":2443}（追加 progress.total_words；幂等：同章节多次调用以最后一次为准）',
    )
    # Round 19 · 2026-04-25 · Phase C：reader-naturalness 5 子维度入口
    # 借鉴 upstream@5339e83 reviewer.md 5 子维度 rubric（不引入 reviewer.md 整体）。
    # data-agent 读 tmp/naturalness_check_ch{NNNN}.json.subdimensions 后写入 chapter_meta；
    # polish_cycle 读 _lowest 字段定向修最低子维度。
    update_parser.add_argument(
        "--set-checker-subdimensions",
        help='JSON: {"chapter":N,"checker":"reader-naturalness-checker","subdimensions":{"vocab":92,"syntax":78,"narrative":85,"emotion":90,"dialogue":95}}（写入 chapter_meta.NNNN.checker_subdimensions.{checker}；自动计算 _lowest）',
    )
    # Round 19 Phase G · 章末钩子 4 分类入口（信息/情绪/决策/动作）
    # reader-pull-checker 章末必输出 hook_close 子对象；data-agent Step K 调本入口落库。
    # 与既有自由文本字段 hook_type 并存（不替换）。
    update_parser.add_argument(
        "--set-hook-close",
        help='JSON: {"chapter":N,"primary":"信息钩|情绪钩|决策钩|动作钩","secondary":null,"strength":88,"text":"章末最后 200 字"}',
    )

    # Round 19 Phase E · 跨卷规划数据：get-hook-trend 与 get-recent-meta 同级
    # Round 19 Phase G · 跨章钩子趋势查询：取最近 N 章 hook_close.primary_type 序列 + 自动判定
    trend_parser = subparsers.add_parser(
        "get-hook-trend",
        help="查询最近 N 章 hook_close.primary_type 序列 + 自动判定连续 5 章同型 / 8 章缺类",
    )
    trend_parser.add_argument("--last-n", type=int, default=5)

    argv = normalize_global_project_root(sys.argv[1:])
    args = parser.parse_args(argv)
    command_started_at = time.perf_counter()

    # 初始化
    config = None
    if args.project_root:
        # 允许传入“工作区根目录”，统一解析到真正的 book project_root（必须包含 .webnovel/state.json）
        from project_locator import resolve_project_root
        from .config import DataModulesConfig

        resolved_root = resolve_project_root(args.project_root)
        config = DataModulesConfig.from_project_root(resolved_root)

    manager = StateManager(config)
    logger = IndexManager(config)
    tool_name = f"state_manager:{args.command or 'unknown'}"

    def _append_timing(success: bool, *, error_code: str | None = None, error_message: str | None = None, chapter: int | None = None):
        elapsed_ms = int((time.perf_counter() - command_started_at) * 1000)
        safe_append_perf_timing(
            manager.config.project_root,
            tool_name=tool_name,
            success=success,
            elapsed_ms=elapsed_ms,
            chapter=chapter,
            error_code=error_code,
            error_message=error_message,
        )

    def emit_success(data=None, message: str = "ok", chapter: int | None = None):
        print_success(data, message=message)
        safe_log_tool_call(logger, tool_name=tool_name, success=True)
        _append_timing(True, chapter=chapter)

    def emit_error(code: str, message: str, suggestion: str | None = None, chapter: int | None = None):
        print_error(code, message, suggestion=suggestion)
        safe_log_tool_call(
            logger,
            tool_name=tool_name,
            success=False,
            error_code=code,
            error_message=message,
        )
        _append_timing(False, error_code=code, error_message=message, chapter=chapter)

    if args.command == "get-progress":
        emit_success(manager._state.get("progress", {}), message="progress")

    elif args.command == "get-recent-meta":
        # Round 19 Phase E · 跨卷规划数据（upstream@3e36417 借鉴）
        # 输出最近 N 章 chapter_meta 摘要：hook_close / hook_type / unresolved_loops /
        # overall_score / narrative_version / word_count，供 plan 阶段消费
        chapter_meta = manager._state.get("chapter_meta", {}) or {}
        chs_str = sorted(chapter_meta.keys())
        chs = sorted([int(k) for k in chs_str if str(k).isdigit()])
        last_n = int(getattr(args, "last_n", 10) or 10)
        recent = chs[-last_n:] if len(chs) >= last_n else chs
        out: dict = {}
        for ch in recent:
            m = chapter_meta.get(f"{ch:04d}") or {}
            out[str(ch)] = {
                "hook_close": m.get("hook_close"),  # Phase G 后会填充
                "hook_type": m.get("hook_type"),
                "hook_strength": m.get("hook_strength"),
                "hook_content": (m.get("hook_content") or "")[:120],
                "unresolved_loops": m.get("unresolved_loops") or [],
                "overall_score": m.get("overall_score")
                or (m.get("checker_scores") or {}).get("overall"),
                "narrative_version": m.get("narrative_version"),
                "word_count": m.get("word_count"),
            }
        payload = {
            "last_n": last_n,
            "chapters_returned": list(out.keys()),
            "data": out,
        }
        emit_success(payload, message="recent_meta")

    elif args.command == "get-hook-trend":
        # Round 19 Phase G · 跨章钩子趋势查询（信息钩 / 情绪钩 / 决策钩 / 动作钩）
        # 取最近 N 章 hook_close.primary_type / secondary_type 序列 + 自动判定:
        # - all_same_primary：连续 N 章 primary 相同（H25 P1 warn 信号）
        # - combo_repeated_3：连续 3 章 primary+secondary 组合相同
        # - no_decision_hook_8：连续 8 章无决策钩
        # - no_emotion_hook_8：连续 8 章无情绪钩
        chapter_meta = manager._state.get("chapter_meta", {}) or {}
        chs = sorted([int(k) for k in chapter_meta.keys() if str(k).isdigit()])
        last_n = int(getattr(args, "last_n", 5) or 5)
        recent = chs[-last_n:] if len(chs) >= last_n else chs
        primaries: list[str] = []
        secs: list[str] = []
        for ch in recent:
            hc = (chapter_meta.get(f"{ch:04d}") or {}).get("hook_close") or {}
            primaries.append(hc.get("primary_type") or "")
            secs.append(hc.get("secondary_type") or "")
        # 跨章趋势判定（空字符串不算连续相同）
        all_same_primary = bool(
            primaries
            and len(set(primaries)) == 1
            and len(primaries) == last_n
            and primaries[0]
        )
        # combo（primary, secondary）连续 3 章相同
        combo_repeated_3 = (
            len(primaries) >= 3
            and len({(p, s) for p, s in zip(primaries[-3:], secs[-3:])}) == 1
            and primaries[-1] != ""
        )
        # 8 章窗口对决策钩 / 情绪钩缺位检查（取所有章节最近 8 个，不只 last_n）
        last_8_primaries = [
            (chapter_meta.get(f"{c:04d}") or {}).get("hook_close", {}).get("primary_type") or ""
            for c in chs[-8:]
        ]
        no_decision_hook_8 = (
            len(last_8_primaries) >= 8 and "决策钩" not in last_8_primaries
        )
        no_emotion_hook_8 = (
            len(last_8_primaries) >= 8 and "情绪钩" not in last_8_primaries
        )
        out = {
            "last_n": last_n,
            "chapters": recent,
            "recent_primary": primaries,
            "recent_secondary": secs,
            "all_same_primary": all_same_primary,
            "combo_repeated_3": combo_repeated_3,
            "no_decision_hook_8": no_decision_hook_8,
            "no_emotion_hook_8": no_emotion_hook_8,
            "last_8_primaries": last_8_primaries,
        }
        emit_success(out, message="hook_trend")

    elif args.command == "get-entity":
        entity = manager.get_entity(args.id)
        if entity:
            emit_success(entity, message="entity")
        else:
            emit_error("NOT_FOUND", f"未找到实体: {args.id}")

    elif args.command == "list-entities":
        if args.type:
            entities = manager.get_entities_by_type(args.type)
        elif args.tier:
            entities = manager.get_entities_by_tier(args.tier)
        else:
            entities = manager.get_all_entities()

        payload = [{"id": eid, **e} for eid, e in entities.items()]
        emit_success(payload, message="entities")

    elif args.command == "process-chapter":
        data = load_json_arg(args.data)
        validated = None
        last_exc = None
        for _ in range(3):
            try:
                validated = validate_data_agent_output(data)
                break
            except ValidationError as exc:
                last_exc = exc
                data = normalize_data_agent_output(data)
        if validated is None:
            err = format_validation_error(last_exc) if last_exc else {
                "code": "SCHEMA_VALIDATION_FAILED",
                "message": "数据结构校验失败",
                "details": {"errors": []},
                "suggestion": "请检查 data-agent 输出字段是否完整且类型正确",
            }
            emit_error(err["code"], err["message"], suggestion=err.get("suggestion"))
            return

        warnings = manager.process_chapter_result(args.chapter, validated.model_dump(by_alias=True))
        manager.save_state()
        emit_success({"chapter": args.chapter, "warnings": warnings}, message="chapter_processed", chapter=args.chapter)

    elif args.command == "update":
        # At least one of the mutation flags must be provided
        if not (args.strand_dominant or args.add_foreshadowing or args.resolve_foreshadowing):
            if not (
                args.set_chapter_meta_field
                or args.sync_protagonist_display
                or args.set_checker_score
                or args.append_recheck
                or args.add_words
                or args.set_checker_subdimensions
                or args.set_hook_close
            ):
                emit_error(
                    "MISSING_ARG",
                    "state update 需要至少一个参数（--strand-dominant / --add-foreshadowing / --resolve-foreshadowing / --set-chapter-meta-field / --sync-protagonist-display / --set-checker-score / --append-recheck / --add-words / --set-checker-subdimensions / --set-hook-close）",
                )
                return
        changes: list[str] = []
        applied_chapter: int | None = None
        if args.strand_dominant:
            payload = load_json_arg(args.strand_dominant)
            ch = int(payload.get("chapter", 0))
            dominant = str(payload.get("dominant", "")).lower().strip()
            if not ch or not dominant:
                emit_error("INVALID_ARG", "--strand-dominant 需要 {chapter,dominant[,sub]}")
                return
            sub = str(payload.get("sub", "")).lower().strip()
            tracker = manager._state.setdefault("strand_tracker", {})
            history = tracker.setdefault("history", [])
            # Replace any existing entry for this chapter
            history = [h for h in history if int(h.get("chapter", 0)) != ch]
            entry = {"chapter": ch, "dominant": dominant}
            if sub:
                entry["sub"] = sub
            history.append(entry)
            history.sort(key=lambda h: int(h.get("chapter", 0)))
            tracker["history"] = history
            tracker["last_dominant"] = dominant
            if sub:
                tracker["last_sub"] = sub
            manager._pending_raw_state_mutations.add("strand_tracker")
            changes.append(f"strand_tracker.ch{ch}={dominant}/{sub or '-'}")
            applied_chapter = ch
        if args.add_foreshadowing:
            payload = load_json_arg(args.add_foreshadowing)
            fid = payload.get("id")
            if not fid:
                emit_error("INVALID_ARG", "--add-foreshadowing 需要 id 字段")
                return
            plot_threads = manager._state.setdefault("plot_threads", {})
            fs_list = plot_threads.setdefault("foreshadowing", [])
            # Replace if exists
            fs_list = [f for f in fs_list if f.get("id") != fid]
            fs_list.append(payload)
            plot_threads["foreshadowing"] = fs_list
            manager._pending_raw_state_mutations.add("plot_threads")
            changes.append(f"add_foreshadowing:{fid}")
            if applied_chapter is None and payload.get("planted_chapter"):
                applied_chapter = int(payload["planted_chapter"])
        if args.resolve_foreshadowing:
            payload = load_json_arg(args.resolve_foreshadowing)
            fid = payload.get("id")
            if not fid:
                emit_error("INVALID_ARG", "--resolve-foreshadowing 需要 id 字段")
                return
            plot_threads = manager._state.setdefault("plot_threads", {})
            fs_list = plot_threads.get("foreshadowing", [])
            updated = False
            for f in fs_list:
                if f.get("id") == fid:
                    f["status"] = "resolved"
                    f["resolution"] = payload.get("resolution", "")
                    f["resolved_chapter"] = int(payload.get("resolved_chapter", 0))
                    updated = True
                    break
            if not updated:
                emit_error("NOT_FOUND", f"foreshadowing {fid} 不存在")
                return
            manager._pending_raw_state_mutations.add("plot_threads")
            changes.append(f"resolve_foreshadowing:{fid}")
            if applied_chapter is None and payload.get("resolved_chapter"):
                applied_chapter = int(payload["resolved_chapter"])
        # Round 15.2：chapter_meta 字段级更新（白名单限定 · 禁止任意字段）
        if args.set_chapter_meta_field:
            payload = load_json_arg(args.set_chapter_meta_field)
            ch = int(payload.get("chapter", 0))
            field = str(payload.get("field", "")).strip()
            value = payload.get("value")
            CHAPTER_META_FIELD_WHITELIST = {
                "overall_score", "narrative_version",
                "naturalness_verdict", "naturalness_score",
                "reader_critic_verdict", "reader_critic_score",
                "strand_dominant", "word_count",
                "chapter_type", "review_score",
                "thrill_score",  # Round 20.1 · Ch1-12 体检 Bug 1：reader-thrill-checker 6 子维度结构
            }
            if not ch or not field:
                emit_error("INVALID_ARG", "--set-chapter-meta-field 需要 chapter + field 字段")
                return
            if field not in CHAPTER_META_FIELD_WHITELIST:
                emit_error(
                    "FIELD_NOT_ALLOWED",
                    f"field={field} 不在白名单内，允许集: {sorted(CHAPTER_META_FIELD_WHITELIST)}",
                )
                return
            cm = manager._state.setdefault("chapter_meta", {})
            key = f"{ch:04d}"
            entry = cm.setdefault(key, {})
            entry[field] = value
            # Round 17.2 · Ch8 P1-R6 根治：overall_score 与 checker_scores.overall 双字段同步
            # 写其一必同步另一（hygiene H9 强制两者相等的对偶实现）
            if field == "overall_score":
                cs = entry.setdefault("checker_scores", {})
                if cs.get("overall") != value:
                    cs["overall"] = value
                    changes.append(f"chapter_meta.{key}.checker_scores.overall={value} (auto-sync)")
            manager._pending_raw_state_mutations.add("chapter_meta")
            changes.append(f"chapter_meta.{key}.{field}={value}")
            if applied_chapter is None:
                applied_chapter = ch

        # Round 17.2 · Ch8 P0-R3 根治：SKILL.md Step 4.5 CLI 实现
        # --set-checker-score 更新单个 checker 分数 + 自动重算 overall
        if args.set_checker_score:
            payload = load_json_arg(args.set_checker_score)
            ch = int(payload.get("chapter", 0))
            checker = str(payload.get("checker", "")).strip()
            score = payload.get("score")
            CANONICAL_CHECKERS = {
                "consistency-checker", "continuity-checker", "ooc-checker",
                "reader-pull-checker", "high-point-checker", "pacing-checker",
                "dialogue-checker", "density-checker", "prose-quality-checker",
                "emotion-checker", "flow-checker",
                "reader-naturalness-checker", "reader-critic-checker",
            }
            if not ch or not checker or score is None:
                emit_error("INVALID_ARG", "--set-checker-score 需要 chapter + checker + score 字段")
                return
            if checker not in CANONICAL_CHECKERS:
                emit_error(
                    "CHECKER_NOT_CANONICAL",
                    f"checker={checker} 非 canonical，允许集: {sorted(CANONICAL_CHECKERS)}",
                )
                return
            cm = manager._state.setdefault("chapter_meta", {})
            key = f"{ch:04d}"
            entry = cm.setdefault(key, {})
            cs = entry.setdefault("checker_scores", {})
            cs[checker] = score
            # 重算 overall 为 13 canonical 平均（存在多少算多少）
            present = [v for k, v in cs.items() if k in CANONICAL_CHECKERS]
            if present:
                # Round 20 · Ch12 RCA P0：apply_overall_floor 防加权稀释
                # 任一 <60 → cap 70；任一 <75 → cap 85；前 5 章 reader-critic <80 → cap 80
                try:
                    from data_modules.chapter_audit import apply_overall_floor as _aof
                    floor_result = _aof(cs, ch)
                    new_overall = floor_result["overall"]
                    floor = floor_result.get("floor")
                    floor_note = (
                        f" (raw_avg={floor_result['raw_avg']}, floor={floor})"
                        if floor is not None else ""
                    )
                except Exception:
                    new_overall = round(sum(present) / len(present))
                    floor_note = ""
                cs["overall"] = new_overall
                entry["overall_score"] = new_overall
                changes.append(
                    f"chapter_meta.{key}.checker_scores.{checker}={score} "
                    f"(overall 重算={new_overall}{floor_note})"
                )
                # Round 18 · 2026-04-24 · Ch10 P1-7 根治：Step 4.5 复测后自动同步 review_metrics
                # 旧逻辑：review_metrics.overall_score 在 Step 3 首次写入后不更新，
                # 导致 audit B4 用旧分数（86）vs report 新分数（88）出现 medium warn。
                # 新逻辑：每次 set-checker-score 后，把新 overall 同步到 index.db.review_metrics。
                try:
                    db_path = manager.config.project_root / ".webnovel" / "index.db"
                    if db_path.exists():
                        import sqlite3 as _sqlite3
                        _conn = _sqlite3.connect(str(db_path))
                        _conn.execute(
                            "UPDATE review_metrics SET overall_score = ? "
                            "WHERE start_chapter <= ? AND end_chapter >= ?",
                            (float(new_overall), ch, ch),
                        )
                        _conn.commit()
                        _conn.close()
                        changes.append(
                            f"index.db.review_metrics[ch={ch}].overall_score={new_overall} (auto-sync)"
                        )
                except Exception as _ex:
                    changes.append(
                        f"WARN: review_metrics auto-sync 失败（不阻塞）: {_ex}"
                    )
            manager._pending_raw_state_mutations.add("chapter_meta")
            if applied_chapter is None:
                applied_chapter = ch

        # --append-recheck 追加到 post_polish_recheck
        if args.append_recheck:
            payload = load_json_arg(args.append_recheck)
            ch = int(payload.get("chapter", 0))
            checker = str(payload.get("checker", "")).strip()
            before = payload.get("before")
            after = payload.get("after")
            reason = str(payload.get("reason", "")).strip()
            if not ch or not checker or before is None or after is None:
                emit_error(
                    "INVALID_ARG",
                    "--append-recheck 需要 chapter + checker + before + after 字段",
                )
                return
            cm = manager._state.setdefault("chapter_meta", {})
            key = f"{ch:04d}"
            entry = cm.setdefault(key, {})
            ppr = entry.setdefault("post_polish_recheck", {})
            # Round 17.3 · Ch6-8 RCA 根治：兼容 dict 与 list 两种历史格式
            # Ch6/Ch8 是 dict {checker: {...}}；Ch7 是 list [{checker, before, after, ...}]
            # 本 CLI 优先保持原格式，减少破坏性迁移
            recheck_entry = {
                "before": before,
                "after": after,
                "delta": after - before,
                "reason": reason or None,
            }
            if isinstance(ppr, list):
                # list 格式：找到同 checker 则替换，否则 append
                replaced = False
                for i, item in enumerate(ppr):
                    if isinstance(item, dict) and item.get("checker") == checker:
                        ppr[i] = {"checker": checker, **recheck_entry}
                        replaced = True
                        break
                if not replaced:
                    ppr.append({"checker": checker, **recheck_entry})
            else:
                # dict 格式（新章节默认）
                ppr[checker] = recheck_entry
            manager._pending_raw_state_mutations.add("chapter_meta")
            changes.append(
                f"chapter_meta.{key}.post_polish_recheck.{checker}={before}->{after} ({after-before:+d})"
            )
            if applied_chapter is None:
                applied_chapter = ch

        # Round 18.2 · Ch11 RCA #4：progress.total_words 从 chapter_meta 重算（幂等且鲁棒）
        if args.add_words:
            payload = load_json_arg(args.add_words)
            ch = int(payload.get("chapter", 0))
            words = int(payload.get("words", 0))
            if not ch or words <= 0:
                emit_error("INVALID_ARG", "--add-words 需要 {chapter,words} 且 words>0")
                return
            cm = manager._state.setdefault("chapter_meta", {})
            key = f"{ch:04d}"
            entry = cm.setdefault(key, {})
            entry["word_count"] = words
            # 从 chapter_meta 全表重算 progress.total_words（幂等，不依赖增量正确）
            new_total = sum(
                int(v.get("word_count", 0) or 0)
                for v in cm.values()
                if isinstance(v, dict)
            )
            progress = manager._state.setdefault("progress", {})
            cur_total = int(progress.get("total_words", 0))
            progress["total_words"] = max(0, new_total)
            manager._pending_raw_state_mutations.add("progress")
            manager._pending_raw_state_mutations.add("chapter_meta")
            changes.append(
                f"progress.total_words={cur_total}->{new_total} (chapter {ch} word_count={words}; recomputed from chapter_meta)"
            )
            if applied_chapter is None:
                applied_chapter = ch

        # Round 19 · Phase C：reader-naturalness 5 子维度落库
        # 借鉴 upstream@5339e83 reviewer.md 5 子维度 rubric（不引入 reviewer.md 整体）。
        # 写入 chapter_meta.{NNNN}.checker_subdimensions.{checker}.{vocab/syntax/narrative/emotion/dialogue}
        # 自动计算 _lowest 字段（最低子维度名）供 polish_cycle 定向修。
        if args.set_checker_subdimensions:
            payload = load_json_arg(args.set_checker_subdimensions)
            ch = int(payload.get("chapter", 0))
            checker = str(payload.get("checker", "")).strip()
            subdims = payload.get("subdimensions") or {}
            if not ch or not checker or not isinstance(subdims, dict):
                emit_error(
                    "INVALID_ARG",
                    "--set-checker-subdimensions 需要 chapter(int) + checker(str) + subdimensions(dict)",
                )
                return
            cm = manager._state.setdefault("chapter_meta", {})
            key = f"{ch:04d}"
            entry = cm.setdefault(key, {})
            csd = entry.setdefault("checker_subdimensions", {})
            # 仅保留 numeric 子维度，过滤非数值键防污染
            checker_subs = {
                k: v for k, v in subdims.items()
                if isinstance(v, (int, float)) and not str(k).startswith("_")
            }
            if checker_subs:
                checker_subs["_lowest"] = min(
                    checker_subs,
                    key=lambda k: checker_subs[k],
                )
            csd[checker] = checker_subs
            manager._pending_raw_state_mutations.add("chapter_meta")
            changes.append(
                f"chapter_meta.{key}.checker_subdimensions.{checker}={checker_subs}"
            )
            if applied_chapter is None:
                applied_chapter = ch

        # Round 19 Phase G · 章末钩子 4 分类落库（信息钩 / 情绪钩 / 决策钩 / 动作钩）
        # reader-pull-checker 章末必输出 hook_close 子对象；data-agent Step K 调本入口写入。
        # 与既有自由文本字段 hook_type 并存不替换。
        if args.set_hook_close:
            payload = load_json_arg(args.set_hook_close)
            ch = int(payload.get("chapter", 0))
            primary = str(payload.get("primary", "")).strip()
            VALID_HOOK_TYPES = {"信息钩", "情绪钩", "决策钩", "动作钩"}
            if not ch or primary not in VALID_HOOK_TYPES:
                emit_error(
                    "INVALID_ARG",
                    f"--set-hook-close 需要 chapter(int) + primary∈{sorted(VALID_HOOK_TYPES)}",
                )
                return
            sec = payload.get("secondary")
            if sec and sec not in VALID_HOOK_TYPES:
                sec = None
            cm = manager._state.setdefault("chapter_meta", {})
            key = f"{ch:04d}"
            entry = cm.setdefault(key, {})
            entry["hook_close"] = {
                "primary_type": primary,
                "secondary_type": sec,
                "strength": int(payload.get("strength", 80)),
                "text_excerpt": (str(payload.get("text") or ""))[:200],
            }
            manager._pending_raw_state_mutations.add("chapter_meta")
            changes.append(
                f"chapter_meta.{key}.hook_close.primary={primary}"
                + (f"+secondary={sec}" if sec else "")
            )
            if applied_chapter is None:
                applied_chapter = ch

        # Round 15.2：protagonist_state 冗余显示字段同步（SQL 改过后手工触发）
        if args.sync_protagonist_display:
            payload = load_json_arg(args.sync_protagonist_display)
            ps = manager._state.setdefault("protagonist_state", {})
            if "hourglass_remaining" in payload:
                gf = ps.setdefault("golden_finger", {})
                hg = gf.setdefault("hourglass", {})
                hg["remaining"] = int(payload["hourglass_remaining"])
                changes.append(f"hourglass.remaining={payload['hourglass_remaining']}")
            if "location_current" in payload:
                loc = ps.setdefault("location", {})
                loc["current"] = str(payload["location_current"])
                changes.append(f"location.current={payload['location_current']}")
            if "vital_force_current" in payload:
                # Round 18 · 2026-04-24 · Ch10 P0-3 根治：vital_force 双路径同步
                # 项目历史上有两条 vital_force 路径：
                #   - protagonist_state.vital_force.current（顶层，CLI 旧路径）
                #   - protagonist_state.golden_finger.vital_force.current（金手指卡权威源）
                # Ch9-Ch10 之前只更新顶层，导致 golden_finger 子树仍是旧值，
                # context-agent 读权威源时漂移，audit B-VF 触发 medium warn。
                # 根治：sync 时同时写两条路径，保持双源一致。
                _new_vf = int(payload["vital_force_current"])
                vf_top = ps.setdefault("vital_force", {})
                vf_top["current"] = _new_vf
                gf_for_vf = ps.setdefault("golden_finger", {})
                vf_gf = gf_for_vf.setdefault("vital_force", {})
                vf_gf["current"] = _new_vf
                changes.append(
                    f"vital_force.current={_new_vf}（顶层+golden_finger 双源同步）"
                )
            if "seal_jump_count" in payload:
                seal = ps.setdefault("seal_state", {})
                seal["jump_count"] = int(payload["seal_jump_count"])
                changes.append(f"seal.jump_count={payload['seal_jump_count']}")
            if "countdown_current" in payload:
                cd = ps.setdefault("countdown", {})
                cd["current"] = str(payload["countdown_current"])
                changes.append(f"countdown.current={payload['countdown_current']}")
            manager._pending_raw_state_mutations.add("protagonist_state")

        manager.save_state()
        emit_success(
            {"changes": changes, "chapter": applied_chapter},
            message="state_updated",
            chapter=applied_chapter,
        )

    else:
        emit_error("UNKNOWN_COMMAND", "未指定有效命令", suggestion="请查看 --help")


if __name__ == "__main__":
    if sys.platform == "win32":
        enable_windows_utf8_stdio()
    main()
