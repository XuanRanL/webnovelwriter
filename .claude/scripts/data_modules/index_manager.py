#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Index Manager - 索引管理模块 (v5.1)

管理 index.db (SQLite) 的读写操作：
- 章节元数据索引
- 实体出场记录
- 场景索引
- 实体存储 (从 state.json 迁移)
- 别名索引 (一对多)
- 状态变化记录
- 关系存储
- 快速查询接口

v5.1 变更:
- 新增 entities 表替代 state.json 中的 entities_v3
- 新增 aliases 表替代 state.json 中的 alias_index (支持一对多)
- 新增 state_changes 表替代 state.json 中的 state_changes
- 新增 relationships 表替代 state.json 中的 structured_relationships
"""

import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from contextlib import contextmanager
from datetime import datetime

from .config import get_config


@dataclass
class ChapterMeta:
    """章节元数据"""
    chapter: int
    title: str
    location: str
    word_count: int
    characters: List[str]
    summary: str = ""


@dataclass
class SceneMeta:
    """场景元数据"""
    chapter: int
    scene_index: int
    start_line: int
    end_line: int
    location: str
    summary: str
    characters: List[str]


@dataclass
class EntityMeta:
    """实体元数据 (v5.1 新增)"""
    id: str
    type: str  # 角色/地点/物品/势力/招式
    canonical_name: str
    tier: str = "装饰"  # 核心/重要/次要/装饰
    desc: str = ""
    current: Dict = field(default_factory=dict)  # 当前状态 (realm/location/items等)
    first_appearance: int = 0
    last_appearance: int = 0
    is_protagonist: bool = False
    is_archived: bool = False


@dataclass
class StateChangeMeta:
    """状态变化记录 (v5.1 新增)"""
    entity_id: str
    field: str
    old_value: str
    new_value: str
    reason: str
    chapter: int


@dataclass
class RelationshipMeta:
    """关系记录 (v5.1 新增)"""
    from_entity: str
    to_entity: str
    type: str
    description: str
    chapter: int


class IndexManager:
    """索引管理器"""

    def __init__(self, config=None):
        self.config = config or get_config()
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        self.config.ensure_dirs()

        with self._get_conn() as conn:
            cursor = conn.cursor()

            # 章节表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chapters (
                    chapter INTEGER PRIMARY KEY,
                    title TEXT,
                    location TEXT,
                    word_count INTEGER,
                    characters TEXT,
                    summary TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 场景表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scenes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chapter INTEGER,
                    scene_index INTEGER,
                    start_line INTEGER,
                    end_line INTEGER,
                    location TEXT,
                    summary TEXT,
                    characters TEXT,
                    UNIQUE(chapter, scene_index)
                )
            """)

            # 实体出场表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS appearances (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_id TEXT,
                    chapter INTEGER,
                    mentions TEXT,
                    confidence REAL,
                    UNIQUE(entity_id, chapter)
                )
            """)

            # 创建索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_scenes_chapter ON scenes(chapter)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_appearances_entity ON appearances(entity_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_appearances_chapter ON appearances(chapter)")

            # ==================== v5.1 新增表 ====================

            # 实体表 (替代 state.json 中的 entities_v3)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS entities (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    canonical_name TEXT NOT NULL,
                    tier TEXT DEFAULT '装饰',
                    desc TEXT,
                    current_json TEXT,
                    first_appearance INTEGER DEFAULT 0,
                    last_appearance INTEGER DEFAULT 0,
                    is_protagonist INTEGER DEFAULT 0,
                    is_archived INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 别名表 (替代 state.json 中的 alias_index，支持一对多)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS aliases (
                    alias TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (alias, entity_id, entity_type)
                )
            """)

            # 状态变化表 (替代 state.json 中的 state_changes)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS state_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_id TEXT NOT NULL,
                    field TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT,
                    reason TEXT,
                    chapter INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 关系表 (替代 state.json 中的 structured_relationships)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_entity TEXT NOT NULL,
                    to_entity TEXT NOT NULL,
                    type TEXT NOT NULL,
                    description TEXT,
                    chapter INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(from_entity, to_entity, type)
                )
            """)

            # v5.1 新索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_tier ON entities(tier)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_protagonist ON entities(is_protagonist)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_aliases_entity ON aliases(entity_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_aliases_alias ON aliases(alias)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_state_changes_entity ON state_changes(entity_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_state_changes_chapter ON state_changes(chapter)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_relationships_from ON relationships(from_entity)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_relationships_to ON relationships(to_entity)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_relationships_chapter ON relationships(chapter)")

            conn.commit()

    @contextmanager
    def _get_conn(self):
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.config.index_db))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    # ==================== 章节操作 ====================

    def add_chapter(self, meta: ChapterMeta):
        """添加/更新章节元数据"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO chapters
                (chapter, title, location, word_count, characters, summary)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                meta.chapter,
                meta.title,
                meta.location,
                meta.word_count,
                json.dumps(meta.characters, ensure_ascii=False),
                meta.summary
            ))
            conn.commit()

    def get_chapter(self, chapter: int) -> Optional[Dict]:
        """获取章节元数据"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM chapters WHERE chapter = ?", (chapter,))
            row = cursor.fetchone()
            if row:
                return self._row_to_dict(row, parse_json=["characters"])
            return None

    def get_recent_chapters(self, limit: int = None) -> List[Dict]:
        """获取最近章节"""
        if limit is None:
            limit = self.config.query_recent_chapters_limit
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM chapters
                ORDER BY chapter DESC
                LIMIT ?
            """, (limit,))
            return [self._row_to_dict(row, parse_json=["characters"]) for row in cursor.fetchall()]

    # ==================== 场景操作 ====================

    def add_scenes(self, chapter: int, scenes: List[SceneMeta]):
        """添加章节场景"""
        with self._get_conn() as conn:
            cursor = conn.cursor()

            # 先删除该章节旧场景
            cursor.execute("DELETE FROM scenes WHERE chapter = ?", (chapter,))

            # 插入新场景
            for scene in scenes:
                cursor.execute("""
                    INSERT INTO scenes
                    (chapter, scene_index, start_line, end_line, location, summary, characters)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    scene.chapter,
                    scene.scene_index,
                    scene.start_line,
                    scene.end_line,
                    scene.location,
                    scene.summary,
                    json.dumps(scene.characters, ensure_ascii=False)
                ))

            conn.commit()

    def get_scenes(self, chapter: int) -> List[Dict]:
        """获取章节场景"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM scenes
                WHERE chapter = ?
                ORDER BY scene_index
            """, (chapter,))
            return [self._row_to_dict(row, parse_json=["characters"]) for row in cursor.fetchall()]

    def search_scenes_by_location(self, location: str, limit: int = None) -> List[Dict]:
        """按地点搜索场景"""
        if limit is None:
            limit = self.config.query_scenes_by_location_limit
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM scenes
                WHERE location LIKE ?
                ORDER BY chapter DESC
                LIMIT ?
            """, (f"%{location}%", limit))
            return [self._row_to_dict(row, parse_json=["characters"]) for row in cursor.fetchall()]

    # ==================== 出场记录操作 ====================

    def record_appearance(
        self,
        entity_id: str,
        chapter: int,
        mentions: List[str],
        confidence: float = 1.0,
        skip_if_exists: bool = False
    ):
        """记录实体出场

        Args:
            entity_id: 实体ID
            chapter: 章节号
            mentions: 提及列表
            confidence: 置信度
            skip_if_exists: 如果为True，当记录已存在时跳过（避免覆盖已有mentions）
        """
        with self._get_conn() as conn:
            cursor = conn.cursor()

            if skip_if_exists:
                # 先检查是否已存在
                cursor.execute(
                    "SELECT 1 FROM appearances WHERE entity_id = ? AND chapter = ?",
                    (entity_id, chapter)
                )
                if cursor.fetchone():
                    return  # 已存在，跳过

            cursor.execute("""
                INSERT OR REPLACE INTO appearances
                (entity_id, chapter, mentions, confidence)
                VALUES (?, ?, ?, ?)
            """, (
                entity_id,
                chapter,
                json.dumps(mentions, ensure_ascii=False),
                confidence
            ))
            conn.commit()

    def get_entity_appearances(self, entity_id: str, limit: int = None) -> List[Dict]:
        """获取实体出场记录"""
        if limit is None:
            limit = self.config.query_entity_appearances_limit
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM appearances
                WHERE entity_id = ?
                ORDER BY chapter DESC
                LIMIT ?
            """, (entity_id, limit))
            return [self._row_to_dict(row, parse_json=["mentions"]) for row in cursor.fetchall()]

    def get_recent_appearances(self, limit: int = None) -> List[Dict]:
        """获取最近出场的实体"""
        if limit is None:
            limit = self.config.query_recent_appearances_limit
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT entity_id, MAX(chapter) as last_chapter, COUNT(*) as total
                FROM appearances
                GROUP BY entity_id
                ORDER BY last_chapter DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_chapter_appearances(self, chapter: int) -> List[Dict]:
        """获取某章所有出场实体"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM appearances
                WHERE chapter = ?
                ORDER BY confidence DESC
            """, (chapter,))
            return [self._row_to_dict(row, parse_json=["mentions"]) for row in cursor.fetchall()]

    # ==================== v5.1 实体操作 ====================

    def upsert_entity(self, entity: EntityMeta, update_metadata: bool = False) -> bool:
        """
        插入或更新实体 (智能合并)

        - 新实体: 直接插入
        - 已存在: 更新 current_json, last_appearance, updated_at
        - update_metadata=True: 同时更新 canonical_name/tier/desc/is_protagonist/is_archived

        返回是否为新实体
        """
        with self._get_conn() as conn:
            cursor = conn.cursor()

            # 检查是否存在
            cursor.execute("SELECT id, current_json FROM entities WHERE id = ?", (entity.id,))
            existing = cursor.fetchone()

            if existing:
                # 已存在: 智能合并 current_json
                old_current = {}
                if existing["current_json"]:
                    try:
                        old_current = json.loads(existing["current_json"])
                    except json.JSONDecodeError:
                        pass

                # 合并 current (新值覆盖旧值)
                merged_current = {**old_current, **entity.current}

                if update_metadata:
                    # 完整更新（包括元数据）
                    cursor.execute("""
                        UPDATE entities SET
                            canonical_name = ?,
                            tier = ?,
                            desc = ?,
                            current_json = ?,
                            last_appearance = ?,
                            is_protagonist = ?,
                            is_archived = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (
                        entity.canonical_name,
                        entity.tier,
                        entity.desc,
                        json.dumps(merged_current, ensure_ascii=False),
                        entity.last_appearance,
                        1 if entity.is_protagonist else 0,
                        1 if entity.is_archived else 0,
                        entity.id
                    ))
                else:
                    # 只更新 current 和 last_appearance
                    cursor.execute("""
                        UPDATE entities SET
                            current_json = ?,
                            last_appearance = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (
                        json.dumps(merged_current, ensure_ascii=False),
                        entity.last_appearance,
                        entity.id
                    ))
                conn.commit()
                return False
            else:
                # 新实体: 插入
                cursor.execute("""
                    INSERT INTO entities
                    (id, type, canonical_name, tier, desc, current_json,
                     first_appearance, last_appearance, is_protagonist, is_archived)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entity.id,
                    entity.type,
                    entity.canonical_name,
                    entity.tier,
                    entity.desc,
                    json.dumps(entity.current, ensure_ascii=False),
                    entity.first_appearance,
                    entity.last_appearance,
                    1 if entity.is_protagonist else 0,
                    1 if entity.is_archived else 0
                ))
                conn.commit()
                return True

    def get_entity(self, entity_id: str) -> Optional[Dict]:
        """获取单个实体"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM entities WHERE id = ?", (entity_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_dict(row, parse_json=["current_json"])
            return None

    def get_entities_by_type(self, entity_type: str, include_archived: bool = False) -> List[Dict]:
        """按类型获取实体"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            if include_archived:
                cursor.execute("""
                    SELECT * FROM entities WHERE type = ?
                    ORDER BY last_appearance DESC
                """, (entity_type,))
            else:
                cursor.execute("""
                    SELECT * FROM entities WHERE type = ? AND is_archived = 0
                    ORDER BY last_appearance DESC
                """, (entity_type,))
            return [self._row_to_dict(row, parse_json=["current_json"]) for row in cursor.fetchall()]

    def get_entities_by_tier(self, tier: str) -> List[Dict]:
        """按重要度获取实体 (核心/重要/次要/装饰)"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM entities WHERE tier = ? AND is_archived = 0
                ORDER BY last_appearance DESC
            """, (tier,))
            return [self._row_to_dict(row, parse_json=["current_json"]) for row in cursor.fetchall()]

    def get_core_entities(self) -> List[Dict]:
        """获取所有核心实体 (用于 Context Agent 全量加载)"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM entities
                WHERE (tier IN ('核心', '重要') OR is_protagonist = 1) AND is_archived = 0
                ORDER BY is_protagonist DESC, tier, last_appearance DESC
            """)
            return [self._row_to_dict(row, parse_json=["current_json"]) for row in cursor.fetchall()]

    def get_protagonist(self) -> Optional[Dict]:
        """获取主角实体"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM entities WHERE is_protagonist = 1 LIMIT 1")
            row = cursor.fetchone()
            if row:
                return self._row_to_dict(row, parse_json=["current_json"])
            return None

    def update_entity_current(self, entity_id: str, updates: Dict) -> bool:
        """
        增量更新实体的 current 字段 (不覆盖其他字段)

        例如: update_entity_current("xiaoyan", {"realm": "斗师"})
        """
        with self._get_conn() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT current_json FROM entities WHERE id = ?", (entity_id,))
            row = cursor.fetchone()
            if not row:
                return False

            current = {}
            if row["current_json"]:
                try:
                    current = json.loads(row["current_json"])
                except json.JSONDecodeError:
                    pass

            current.update(updates)

            cursor.execute("""
                UPDATE entities SET
                    current_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (json.dumps(current, ensure_ascii=False), entity_id))
            conn.commit()
            return True

    def archive_entity(self, entity_id: str) -> bool:
        """归档实体 (不删除，只是标记)"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE entities SET is_archived = 1, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (entity_id,))
            conn.commit()
            return cursor.rowcount > 0

    # ==================== v5.1 别名操作 ====================

    def register_alias(self, alias: str, entity_id: str, entity_type: str) -> bool:
        """
        注册别名 (支持一对多)

        同一别名可映射多个实体 (如 "天云宗" → 地点 + 势力)
        """
        with self._get_conn() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO aliases (alias, entity_id, entity_type)
                    VALUES (?, ?, ?)
                """, (alias, entity_id, entity_type))
                conn.commit()
                return cursor.rowcount > 0
            except sqlite3.IntegrityError:
                return False

    def get_entities_by_alias(self, alias: str) -> List[Dict]:
        """
        根据别名查找实体 (一对多)

        返回所有匹配的实体 (可能有多个不同类型)
        """
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT e.*, a.entity_type as alias_type
                FROM entities e
                JOIN aliases a ON e.id = a.entity_id
                WHERE a.alias = ?
            """, (alias,))
            return [self._row_to_dict(row, parse_json=["current_json"]) for row in cursor.fetchall()]

    def get_entity_aliases(self, entity_id: str) -> List[str]:
        """获取实体的所有别名"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT alias FROM aliases WHERE entity_id = ?", (entity_id,))
            return [row["alias"] for row in cursor.fetchall()]

    def remove_alias(self, alias: str, entity_id: str) -> bool:
        """移除别名"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM aliases WHERE alias = ? AND entity_id = ?", (alias, entity_id))
            conn.commit()
            return cursor.rowcount > 0

    # ==================== v5.1 状态变化操作 ====================

    def record_state_change(self, change: StateChangeMeta) -> int:
        """
        记录状态变化

        返回记录 ID
        """
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO state_changes
                (entity_id, field, old_value, new_value, reason, chapter)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                change.entity_id,
                change.field,
                change.old_value,
                change.new_value,
                change.reason,
                change.chapter
            ))
            conn.commit()
            return cursor.lastrowid

    def get_entity_state_changes(self, entity_id: str, limit: int = 20) -> List[Dict]:
        """获取实体的状态变化历史"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM state_changes
                WHERE entity_id = ?
                ORDER BY chapter DESC, id DESC
                LIMIT ?
            """, (entity_id, limit))
            return [dict(row) for row in cursor.fetchall()]

    def get_recent_state_changes(self, limit: int = 50) -> List[Dict]:
        """获取最近的状态变化"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM state_changes
                ORDER BY chapter DESC, id DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_chapter_state_changes(self, chapter: int) -> List[Dict]:
        """获取某章的所有状态变化"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM state_changes
                WHERE chapter = ?
                ORDER BY id
            """, (chapter,))
            return [dict(row) for row in cursor.fetchall()]

    # ==================== v5.1 关系操作 ====================

    def upsert_relationship(self, rel: RelationshipMeta) -> bool:
        """
        插入或更新关系

        相同 (from, to, type) 会更新 description 和 chapter
        返回是否为新关系
        """
        with self._get_conn() as conn:
            cursor = conn.cursor()

            # 检查是否存在
            cursor.execute("""
                SELECT id FROM relationships
                WHERE from_entity = ? AND to_entity = ? AND type = ?
            """, (rel.from_entity, rel.to_entity, rel.type))
            existing = cursor.fetchone()

            if existing:
                cursor.execute("""
                    UPDATE relationships SET
                        description = ?,
                        chapter = ?
                    WHERE id = ?
                """, (rel.description, rel.chapter, existing["id"]))
                conn.commit()
                return False
            else:
                cursor.execute("""
                    INSERT INTO relationships
                    (from_entity, to_entity, type, description, chapter)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    rel.from_entity,
                    rel.to_entity,
                    rel.type,
                    rel.description,
                    rel.chapter
                ))
                conn.commit()
                return True

    def get_entity_relationships(self, entity_id: str, direction: str = "both") -> List[Dict]:
        """
        获取实体的关系

        direction: "from" | "to" | "both"
        """
        with self._get_conn() as conn:
            cursor = conn.cursor()

            if direction == "from":
                cursor.execute("""
                    SELECT * FROM relationships WHERE from_entity = ?
                    ORDER BY chapter DESC
                """, (entity_id,))
            elif direction == "to":
                cursor.execute("""
                    SELECT * FROM relationships WHERE to_entity = ?
                    ORDER BY chapter DESC
                """, (entity_id,))
            else:  # both
                cursor.execute("""
                    SELECT * FROM relationships
                    WHERE from_entity = ? OR to_entity = ?
                    ORDER BY chapter DESC
                """, (entity_id, entity_id))

            return [dict(row) for row in cursor.fetchall()]

    def get_relationship_between(self, entity1: str, entity2: str) -> List[Dict]:
        """获取两个实体之间的所有关系"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM relationships
                WHERE (from_entity = ? AND to_entity = ?)
                   OR (from_entity = ? AND to_entity = ?)
                ORDER BY chapter DESC
            """, (entity1, entity2, entity2, entity1))
            return [dict(row) for row in cursor.fetchall()]

    def get_recent_relationships(self, limit: int = 30) -> List[Dict]:
        """获取最近建立的关系"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM relationships
                ORDER BY chapter DESC, id DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    # ==================== 批量操作 ====================

    def process_chapter_data(
        self,
        chapter: int,
        title: str,
        location: str,
        word_count: int,
        entities: List[Dict],
        scenes: List[Dict]
    ) -> Dict[str, int]:
        """
        处理章节数据，批量写入索引

        返回写入统计
        """
        stats = {"chapters": 0, "scenes": 0, "appearances": 0}

        # 提取出场角色
        characters = [e.get("id") for e in entities if e.get("type") == "角色"]

        # 写入章节元数据
        self.add_chapter(ChapterMeta(
            chapter=chapter,
            title=title,
            location=location,
            word_count=word_count,
            characters=characters,
            summary=""  # 可后续由 Data Agent 生成
        ))
        stats["chapters"] = 1

        # 写入场景
        scene_metas = []
        for s in scenes:
            scene_metas.append(SceneMeta(
                chapter=chapter,
                scene_index=s.get("index", 0),
                start_line=s.get("start_line", 0),
                end_line=s.get("end_line", 0),
                location=s.get("location", ""),
                summary=s.get("summary", ""),
                characters=s.get("characters", [])
            ))
        self.add_scenes(chapter, scene_metas)
        stats["scenes"] = len(scene_metas)

        # 写入出场记录
        for entity in entities:
            entity_id = entity.get("id")
            if entity_id and entity_id != "NEW":
                self.record_appearance(
                    entity_id=entity_id,
                    chapter=chapter,
                    mentions=entity.get("mentions", []),
                    confidence=entity.get("confidence", 1.0)
                )
                stats["appearances"] += 1

        return stats

    # ==================== 辅助方法 ====================

    def _row_to_dict(self, row: sqlite3.Row, parse_json: List[str] = None) -> Dict:
        """将 Row 转换为字典"""
        d = dict(row)
        if parse_json:
            for key in parse_json:
                if key in d and d[key]:
                    try:
                        d[key] = json.loads(d[key])
                    except json.JSONDecodeError:
                        pass
        return d

    def get_stats(self) -> Dict[str, int]:
        """获取索引统计"""
        with self._get_conn() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM chapters")
            chapters = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM scenes")
            scenes = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT entity_id) FROM appearances")
            appearances = cursor.fetchone()[0]

            cursor.execute("SELECT MAX(chapter) FROM chapters")
            max_chapter = cursor.fetchone()[0] or 0

            # v5.1 新增统计
            cursor.execute("SELECT COUNT(*) FROM entities")
            entities = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM entities WHERE is_archived = 0")
            active_entities = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM aliases")
            aliases = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM state_changes")
            state_changes = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM relationships")
            relationships = cursor.fetchone()[0]

            return {
                "chapters": chapters,
                "scenes": scenes,
                "appearances": appearances,
                "max_chapter": max_chapter,
                # v5.1 新增
                "entities": entities,
                "active_entities": active_entities,
                "aliases": aliases,
                "state_changes": state_changes,
                "relationships": relationships
            }


# ==================== CLI 接口 ====================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Index Manager CLI (v5.1)")
    parser.add_argument("--project-root", type=str, help="项目根目录")

    subparsers = parser.add_subparsers(dest="command")

    # 获取统计
    subparsers.add_parser("stats")

    # 查询章节
    chapter_parser = subparsers.add_parser("get-chapter")
    chapter_parser.add_argument("--chapter", type=int, required=True)

    # 查询最近出场
    recent_parser = subparsers.add_parser("recent-appearances")
    recent_parser.add_argument("--limit", type=int, default=None)

    # 查询实体出场
    entity_parser = subparsers.add_parser("entity-appearances")
    entity_parser.add_argument("--entity", required=True)
    entity_parser.add_argument("--limit", type=int, default=None)

    # 搜索场景
    search_parser = subparsers.add_parser("search-scenes")
    search_parser.add_argument("--location", required=True)
    search_parser.add_argument("--limit", type=int, default=None)

    # 处理章节数据 (写入)
    process_parser = subparsers.add_parser("process-chapter")
    process_parser.add_argument("--chapter", type=int, required=True)
    process_parser.add_argument("--title", required=True)
    process_parser.add_argument("--location", required=True)
    process_parser.add_argument("--word-count", type=int, required=True)
    process_parser.add_argument("--entities", required=True, help="JSON 格式的实体列表")
    process_parser.add_argument("--scenes", required=True, help="JSON 格式的场景列表")

    # ==================== v5.1 新增命令 ====================

    # 获取实体
    get_entity_parser = subparsers.add_parser("get-entity")
    get_entity_parser.add_argument("--id", required=True, help="实体 ID")

    # 获取核心实体
    subparsers.add_parser("get-core-entities")

    # 获取主角
    subparsers.add_parser("get-protagonist")

    # 按类型获取实体
    type_parser = subparsers.add_parser("get-entities-by-type")
    type_parser.add_argument("--type", required=True, help="实体类型 (角色/地点/物品/势力/招式)")
    type_parser.add_argument("--include-archived", action="store_true")

    # 按别名查找实体
    alias_parser = subparsers.add_parser("get-by-alias")
    alias_parser.add_argument("--alias", required=True, help="别名")

    # 获取实体别名
    aliases_parser = subparsers.add_parser("get-aliases")
    aliases_parser.add_argument("--entity", required=True, help="实体 ID")

    # 注册别名
    reg_alias_parser = subparsers.add_parser("register-alias")
    reg_alias_parser.add_argument("--alias", required=True)
    reg_alias_parser.add_argument("--entity", required=True)
    reg_alias_parser.add_argument("--type", required=True, help="实体类型")

    # 获取实体关系
    rel_parser = subparsers.add_parser("get-relationships")
    rel_parser.add_argument("--entity", required=True)
    rel_parser.add_argument("--direction", choices=["from", "to", "both"], default="both")

    # 获取状态变化
    changes_parser = subparsers.add_parser("get-state-changes")
    changes_parser.add_argument("--entity", required=True)
    changes_parser.add_argument("--limit", type=int, default=20)

    # 写入实体
    upsert_entity_parser = subparsers.add_parser("upsert-entity")
    upsert_entity_parser.add_argument("--data", required=True, help="JSON 格式的实体数据")

    # 写入关系
    upsert_rel_parser = subparsers.add_parser("upsert-relationship")
    upsert_rel_parser.add_argument("--data", required=True, help="JSON 格式的关系数据")

    # 写入状态变化
    state_change_parser = subparsers.add_parser("record-state-change")
    state_change_parser.add_argument("--data", required=True, help="JSON 格式的状态变化数据")

    args = parser.parse_args()

    # 初始化
    config = None
    if args.project_root:
        from .config import DataModulesConfig
        config = DataModulesConfig.from_project_root(args.project_root)

    manager = IndexManager(config)

    if args.command == "stats":
        stats = manager.get_stats()
        print(json.dumps(stats, ensure_ascii=False, indent=2))

    elif args.command == "get-chapter":
        chapter = manager.get_chapter(args.chapter)
        if chapter:
            print(json.dumps(chapter, ensure_ascii=False, indent=2))
        else:
            print(f"未找到章节: {args.chapter}")

    elif args.command == "recent-appearances":
        appearances = manager.get_recent_appearances(args.limit)
        for a in appearances:
            print(f"{a['entity_id']}: 最后出场第 {a['last_chapter']} 章, 共 {a['total']} 次")

    elif args.command == "entity-appearances":
        appearances = manager.get_entity_appearances(args.entity, args.limit)
        print(f"{args.entity} 出场记录:")
        for a in appearances:
            print(f"  第 {a['chapter']} 章: {a['mentions']}")

    elif args.command == "search-scenes":
        scenes = manager.search_scenes_by_location(args.location, args.limit)
        for s in scenes:
            print(f"第 {s['chapter']} 章 场景 {s['scene_index']}: {s['location']}")
            print(f"  {s['summary'][:50]}...")

    elif args.command == "process-chapter":
        entities = json.loads(args.entities)
        scenes = json.loads(args.scenes)
        stats = manager.process_chapter_data(
            chapter=args.chapter,
            title=args.title,
            location=args.location,
            word_count=args.word_count,
            entities=entities,
            scenes=scenes
        )
        print(f"✓ 已处理第 {args.chapter} 章")
        print(f"  章节: {stats['chapters']}, 场景: {stats['scenes']}, 出场记录: {stats['appearances']}")

    # ==================== v5.1 新增命令处理 ====================

    elif args.command == "get-entity":
        entity = manager.get_entity(args.id)
        if entity:
            print(json.dumps(entity, ensure_ascii=False, indent=2))
        else:
            print(f"未找到实体: {args.id}")

    elif args.command == "get-core-entities":
        entities = manager.get_core_entities()
        print(json.dumps(entities, ensure_ascii=False, indent=2))

    elif args.command == "get-protagonist":
        protagonist = manager.get_protagonist()
        if protagonist:
            print(json.dumps(protagonist, ensure_ascii=False, indent=2))
        else:
            print("未设置主角")

    elif args.command == "get-entities-by-type":
        entities = manager.get_entities_by_type(args.type, args.include_archived)
        print(json.dumps(entities, ensure_ascii=False, indent=2))

    elif args.command == "get-by-alias":
        entities = manager.get_entities_by_alias(args.alias)
        if entities:
            print(json.dumps(entities, ensure_ascii=False, indent=2))
        else:
            print(f"未找到别名: {args.alias}")

    elif args.command == "get-aliases":
        aliases = manager.get_entity_aliases(args.entity)
        if aliases:
            print(f"{args.entity} 的别名: {', '.join(aliases)}")
        else:
            print(f"{args.entity} 没有别名")

    elif args.command == "register-alias":
        success = manager.register_alias(args.alias, args.entity, args.type)
        if success:
            print(f"✓ 已注册别名: {args.alias} → {args.entity} ({args.type})")
        else:
            print(f"别名已存在或注册失败: {args.alias}")

    elif args.command == "get-relationships":
        rels = manager.get_entity_relationships(args.entity, args.direction)
        print(json.dumps(rels, ensure_ascii=False, indent=2))

    elif args.command == "get-state-changes":
        changes = manager.get_entity_state_changes(args.entity, args.limit)
        print(json.dumps(changes, ensure_ascii=False, indent=2))

    elif args.command == "upsert-entity":
        data = json.loads(args.data)
        entity = EntityMeta(
            id=data["id"],
            type=data["type"],
            canonical_name=data["canonical_name"],
            tier=data.get("tier", "装饰"),
            desc=data.get("desc", ""),
            current=data.get("current", {}),
            first_appearance=data.get("first_appearance", 0),
            last_appearance=data.get("last_appearance", 0),
            is_protagonist=data.get("is_protagonist", False),
            is_archived=data.get("is_archived", False)
        )
        is_new = manager.upsert_entity(entity)
        print(f"✓ {'新建' if is_new else '更新'}实体: {entity.id}")

    elif args.command == "upsert-relationship":
        data = json.loads(args.data)
        rel = RelationshipMeta(
            from_entity=data["from_entity"],
            to_entity=data["to_entity"],
            type=data["type"],
            description=data.get("description", ""),
            chapter=data["chapter"]
        )
        is_new = manager.upsert_relationship(rel)
        print(f"✓ {'新建' if is_new else '更新'}关系: {rel.from_entity} → {rel.to_entity} ({rel.type})")

    elif args.command == "record-state-change":
        data = json.loads(args.data)
        change = StateChangeMeta(
            entity_id=data["entity_id"],
            field=data["field"],
            old_value=data.get("old_value", ""),
            new_value=data["new_value"],
            reason=data.get("reason", ""),
            chapter=data["chapter"]
        )
        record_id = manager.record_state_change(change)
        print(f"✓ 已记录状态变化 #{record_id}: {change.entity_id}.{change.field}")


if __name__ == "__main__":
    main()
