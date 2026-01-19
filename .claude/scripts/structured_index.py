#!/usr/bin/env python3
"""
结构化索引系统（Structured Index System）v4.0

⚠️ DEPRECATED: 本模块已被 v5.1 index_manager 替代。
   - v5.1 使用不同的 schema（entities.id, aliases, current_json）
   - 本模块仅保留用于兼容旧项目迁移
   - 新项目请使用 data_modules.index_manager

目标：取代向量化检索，使用 SQLite 提供精确、快速的结构化查询

v4.0 变更：
- 新增 entities/entity_aliases/entity_kv/entity_history 表
- 主键从 name 迁移到 entity_id
- relationships 表使用 char1_id/char2_id
- 不再写回 state.json（消除循环依赖）
- 从 entities_v3 + alias_index 同步数据

核心功能：
1. 实体索引（entities, entity_aliases, entity_kv, entity_history）
2. 章节元数据索引（location, characters, word_count）
3. 伏笔追踪索引（status, urgency calculation）
4. 文件 Hash 自愈机制（auto-rebuild on change）

性能目标：
- 查询速度：2-5ms（vs 文件遍历 500ms，提升 250x）
- 索引构建：10ms/章（增量更新）
- 存储开销：200 章 ≈ 100 KB

使用方式：
  # 更新单章索引
  python structured_index.py --update-chapter 7 --metadata-file /tmp/ch7.json

  # 批量重建索引（历史章节）
  python structured_index.py --rebuild-index

  # 查询地点相关章节
  python structured_index.py --query-location "血煞秘境"

  # 查询紧急伏笔
  python structured_index.py --query-urgent-foreshadowing

  # 模糊查询角色
  python structured_index.py --fuzzy-search "姓李" "女弟子"

  # 查看统计信息
  python structured_index.py --stats
"""

import json
import os
import sys
import argparse
import sqlite3
import hashlib
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Tuple

# ============================================================================
# 安全修复：导入安全工具函数（P1 MEDIUM）
# ============================================================================
from security_utils import create_secure_directory
from project_locator import resolve_project_root
from chapter_paths import find_chapter_file


class StructuredIndex:
    """结构化索引管理器（取代向量化检索）"""

    def __init__(self, project_root=None):
        if project_root is None:
            try:
                project_root = resolve_project_root()
            except FileNotFoundError:
                project_root = Path.cwd()
        else:
            project_root = Path(project_root)

        self.project_root = project_root
        self.state_file = project_root / ".webnovel" / "state.json"
        self.chapters_dir = project_root / "正文"
        self.index_db = project_root / ".webnovel" / "index.db"

        # ============================================================================
        # 安全修复：使用安全目录创建函数（P1 MEDIUM）
        # 原代码: self.index_db.parent.mkdir(parents=True, exist_ok=True)
        # 漏洞: 未设置权限，使用OS默认（可能为755，允许同组用户读取）
        # ============================================================================
        create_secure_directory(str(self.index_db.parent))

        # 连接数据库
        self.conn = sqlite3.connect(str(self.index_db))
        self.conn.row_factory = sqlite3.Row  # 返回字典式行

        # 创建表结构
        self._create_tables()

    def _create_tables(self):
        """创建索引表结构（v4.0 主键迁移到 entity_id）"""

        # ============== 新增实体表（v4.0）==============

        # 实体主表（取代旧 characters 表）
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                entity_id TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL,
                canonical_name TEXT,
                tier TEXT,
                desc TEXT,
                created_chapter INTEGER,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 实体类型索引
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_entity_type
            ON entities(entity_type)
        """)

        # 别名表（支持一对多查询）
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS entity_aliases (
                alias TEXT,
                entity_id TEXT,
                entity_type TEXT,
                first_seen_chapter INTEGER,
                context TEXT,
                PRIMARY KEY (alias, entity_id)
            )
        """)

        # 别名索引（加速反向查询）
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_alias
            ON entity_aliases(alias)
        """)

        # 实体属性 KV 表
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS entity_kv (
                entity_id TEXT,
                key TEXT,
                value TEXT,
                last_chapter INTEGER,
                PRIMARY KEY (entity_id, key)
            )
        """)

        # 实体历史表
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS entity_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id TEXT,
                chapter INTEGER,
                changes_json TEXT,
                reasons_json TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 历史索引
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_entity_history
            ON entity_history(entity_id, chapter)
        """)

        # ============== 章节元数据表 ==============

        # 1. 章节元数据表（v4.0: characters 改为存 entity_id 列表）
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS chapters (
                chapter_num INTEGER PRIMARY KEY,
                title TEXT,
                location TEXT,
                location_id TEXT,
                characters TEXT,  -- JSON: ["entity_id_1", "entity_id_2"]
                word_count INTEGER,
                content_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 地点索引（加速查询）
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_location
            ON chapters(location)
        """)

        # 2. 伏笔追踪表
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS foreshadowing_index (
                id INTEGER PRIMARY KEY,
                content TEXT,
                location TEXT,
                characters TEXT,  -- JSON: ["李雪", "主角"]
                introduced_chapter INTEGER,
                resolved_chapter INTEGER,
                status TEXT,  -- '未回收' / '已回收'
                urgency INTEGER DEFAULT 0,  -- 0-100，自动计算
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 状态索引
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_status
            ON foreshadowing_index(status)
        """)

        # 紧急度索引
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_urgency
            ON foreshadowing_index(urgency)
        """)

        # 3. 角色关系表（v4.0: 使用 entity_id）
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                char1_id TEXT,
                char2_id TEXT,
                char1_name TEXT,
                char2_name TEXT,
                relation_type TEXT,  -- 'ally', 'enemy', 'romance', 'mentor', 'debtor'
                intensity INTEGER,    -- 关系强度 0-100
                description TEXT,
                last_update_chapter INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(char1_id, char2_id, relation_type)  -- 防止重复
            )
        """)

        # 关系索引（v4.0: 使用 entity_id）
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_char1_char2
            ON relationships(char1_id, char2_id)
        """)

        # 4. 角色索引表（v4.0 已废弃，保留兼容）
        # 新代码应使用 entities 表
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS characters (
                name TEXT PRIMARY KEY,
                description TEXT,
                personality TEXT,
                importance TEXT,  -- 'major' / 'minor'
                power_level TEXT,
                first_appearance INTEGER,
                last_appearance INTEGER,
                status TEXT DEFAULT 'active',  -- 'active' / 'archived'
                archived_at TEXT,  -- ISO timestamp
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 角色名索引（加速模糊搜索）
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_character_name
            ON characters(name)
        """)

        # 状态索引
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_character_status
            ON characters(status)
        """)

        self.conn.commit()

    # ================== 核心功能 1：章节元数据索引 ==================

    def index_chapter(self, chapter_num: int, metadata: Dict):
        """为新章节建立索引（在 webnovel-write Step 4.6 调用）

        Args:
            chapter_num: 章节编号
            metadata: {
                'title': '章节标题',
                'location': '地点',
                'characters': ['李雪', '主角'],
                'word_count': 3500,
                'hash': 'md5_hash'
            }
        """
        def _normalize_str_list(v) -> List[str]:
            if v is None:
                return []
            if isinstance(v, list):
                return [str(x).strip() for x in v if str(x).strip()]
            if isinstance(v, str):
                return [s.strip() for s in re.split(r"[,，]", v) if s.strip()]
            return [str(v).strip()] if str(v).strip() else []

        def _exists_entity(entity_id: str, entity_type: str) -> bool:
            row = self.conn.execute(
                "SELECT 1 FROM entities WHERE entity_id = ? AND entity_type = ? LIMIT 1",
                (entity_id, entity_type),
            ).fetchone()
            return bool(row)

        def _resolve_alias_ids(alias: str, entity_type: str) -> List[str]:
            rows = self.conn.execute(
                "SELECT entity_id FROM entity_aliases WHERE alias = ? AND entity_type = ?",
                (alias, entity_type),
            ).fetchall()
            return [r["entity_id"] for r in rows] if rows else []

        # v4.0: chapters.characters 存 entity_id 列表（metadata 允许传入 name/alias，索引层负责解析）
        resolved_character_ids: List[str] = []
        seen_ids = set()
        for ref in _normalize_str_list(metadata.get("characters", [])):
            if _exists_entity(ref, "角色"):
                if ref not in seen_ids:
                    resolved_character_ids.append(ref)
                    seen_ids.add(ref)
                continue

            candidates = _resolve_alias_ids(ref, "角色")
            if len(candidates) == 1:
                cid = candidates[0]
                if cid not in seen_ids:
                    resolved_character_ids.append(cid)
                    seen_ids.add(cid)
                continue

            if len(candidates) > 1:
                print(f"⚠️ 角色别名歧义，跳过: {ref!r} 命中 {len(candidates)} 个角色")
            else:
                print(f"⚠️ 未知角色，跳过: {ref!r}")

        # v4.0: 可选 location_id（只解析为地点实体）
        location = str(metadata.get("location", "")).strip()
        location_id = ""
        if location:
            if _exists_entity(location, "地点"):
                location_id = location
            else:
                loc_candidates = _resolve_alias_ids(location, "地点")
                if len(loc_candidates) == 1:
                    location_id = loc_candidates[0]
                elif len(loc_candidates) > 1:
                    print(f"⚠️ 地点别名歧义，location_id 留空: {location!r} 命中 {len(loc_candidates)} 个地点")

        self.conn.execute("""
            INSERT OR REPLACE INTO chapters
            (chapter_num, title, location, location_id, characters, word_count, content_hash, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            chapter_num,
            metadata['title'],
            location,
            location_id,
            json.dumps(resolved_character_ids, ensure_ascii=False),
            metadata['word_count'],
            metadata['hash']
        ))

        self.conn.commit()
        print(f"✅ 章节索引已更新：Ch{chapter_num} - {metadata['title']}")

    # bump_character_last_appearance_in_state 已删除（v4.0）
    # 原因：消除索引层写回 state.json 的循环依赖
    # last_appearance_chapter 现在作为 index.db 的派生字段

    def query_chapters_by_location(self, location: str, limit: int = 10) -> List[Tuple]:
        """O(log n) 查询：返回该地点的最近 N 章

        Args:
            location: 地点名称
            limit: 返回数量

        Returns:
            [(chapter_num, title, characters), ...]
        """
        cursor = self.conn.execute("""
            SELECT chapter_num, title, characters
            FROM chapters
            WHERE location = ?
            ORDER BY chapter_num DESC
            LIMIT ?
        """, (location, limit))

        return cursor.fetchall()

    def calculate_chapter_hash(self, chapter_file: Path) -> str:
        """计算章节文件 MD5 Hash（用于自愈机制）"""
        if not chapter_file.exists():
            return ""

        with open(chapter_file, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()

    def get_stored_hash(self, chapter_num: int) -> Optional[str]:
        """从索引中读取存储的 Hash"""
        cursor = self.conn.execute("""
            SELECT content_hash FROM chapters WHERE chapter_num = ?
        """, (chapter_num,))

        row = cursor.fetchone()
        return row['content_hash'] if row else None

    def validate_and_rebuild_if_needed(self, chapter_num: int):
        """校验章节 Hash，不一致则自动重建索引（Self-Healing Index）

        触发时机：
        - context_manager.py 查询章节前调用
        - 增加耗时：~5ms（Hash 计算 + 对比）
        - 仅当检测到变更时才重建（增量成本）
        """
        chapter_file = find_chapter_file(self.project_root, chapter_num)
        if chapter_file is None or not chapter_file.exists():
            return  # 文件不存在，跳过

        # 计算当前文件 Hash
        current_hash = self.calculate_chapter_hash(chapter_file)

        # 从索引中读取存储的 Hash
        stored_hash = self.get_stored_hash(chapter_num)

        if current_hash != stored_hash:
            print(f"⚠️ 检测到 Ch{chapter_num} 已修改，自动重建索引...")
            self._rebuild_chapter_index(chapter_num, chapter_file)
            print(f"✅ Ch{chapter_num} 索引已更新")

    def _rebuild_chapter_index(self, chapter_num: int, chapter_file: Path):
        """重建单章索引（自动提取元数据）"""

        # 读取章节内容
        with open(chapter_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 提取元数据
        metadata = self._extract_metadata_from_content(content, chapter_num)

        # 重建索引
        self.index_chapter(chapter_num, metadata)

    def _extract_metadata_from_content(self, content: str, chapter_num: int) -> Dict:
        """从章节内容中提取元数据"""

        # 提取标题（第一行）
        lines = content.split('\n')
        title = lines[0].strip('# ').strip() if lines else f"第{chapter_num}章"

        # 提取地点（在章节开头查找，通常格式为 **地点：XXX**）
        location_match = re.search(r'\*\*地点[：:]\s*(.+?)\*\*', content)
        location = location_match.group(1).strip() if location_match else "未知"

        # 提取角色（查找所有对话和描述中的角色名）
        # 简化实现：从 state.json 读取已知角色，匹配出现频率
        characters = self._extract_characters_from_content(content)

        # 计算字数
        word_count = len(content)

        # 计算 Hash
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()

        return {
            'title': title,
            'location': location,
            'characters': characters[:5],  # 最多 5 个主要角色
            'word_count': word_count,
            'hash': content_hash
        }

    def _extract_characters_from_content(self, content: str) -> List[str]:
        """从内容中提取角色（简化实现：读取索引中已知角色 canonical_name）"""

        # 获取已知角色列表（限制规模，避免超大角色库拖慢）
        rows = self.conn.execute(
            "SELECT canonical_name FROM entities WHERE entity_type = ? AND canonical_name != '' LIMIT 800",
            ("角色",),
        ).fetchall()
        known_characters = [r["canonical_name"] for r in rows] if rows else []
        if not known_characters:
            return []

        # 统计每个角色在内容中的出现次数
        char_counts = {}
        for char_name in known_characters:
            count = content.count(char_name)
            if count > 0:
                char_counts[char_name] = count

        # 按出现次数排序，返回前 5 个
        sorted_chars = sorted(char_counts.items(), key=lambda x: x[1], reverse=True)
        return [char for char, _ in sorted_chars[:5]]

    # ================== 核心功能 2：伏笔追踪索引 ==================

    def sync_foreshadowing_from_state(self):
        """从 state.json 同步伏笔数据到索引

        触发时机：
        - update_state.py 更新伏笔后调用
        - --rebuild-index 批量重建时调用
        """
        if not self.state_file.exists():
            print("❌ state.json 不存在，跳过伏笔同步")
            return

        # 读取 state.json
        with open(self.state_file, 'r', encoding='utf-8') as f:
            state = json.load(f)

        current_chapter = state.get('progress', {}).get('current_chapter', 0)

        plot_threads = state.get('plot_threads', {}) or {}

        # 兼容新格式：plot_threads.foreshadowing = [{"content": "...", "status": "active", ...}, ...]
        foreshadowing_items = plot_threads.get('foreshadowing', []) or []
        active_count = 0
        resolved_count = 0

        for item in foreshadowing_items:
            desc = item.get('description') or item.get('content') or ''
            if not desc:
                continue

            raw_status = (item.get('status') or '').strip()
            if raw_status in ['已回收', 'resolved']:
                status = '已回收'
                resolved_count += 1
            else:
                # 默认都视为未回收（兼容 active/未回收/pending/空）
                status = '未回收'
                active_count += 1

            normalized = {
                'description': desc,
                'location': item.get('location', ''),
                'characters': item.get('characters', []),
                # 如果没有明确记录，至少给一个可用的默认值（避免紧急度恒为0）
                'introduced_chapter': item.get('introduced_chapter') or item.get('planted_chapter') or 1,
                'resolved_chapter': item.get('resolved_chapter', None),
            }

            self._index_foreshadowing(normalized, current_chapter, status=status)

        self.conn.commit()
        print(f"✅ 伏笔索引已同步：{active_count} 条活跃 + {resolved_count} 条已回收")

    def _index_foreshadowing(self, plot: Dict, current_chapter: int, status: str):
        """为单个伏笔建立索引"""

        # 计算紧急度
        urgency = self._calculate_urgency(plot, current_chapter)

        # 提取地点和角色（如果有）
        location = plot.get('location', '')
        characters = plot.get('characters', [])

        self.conn.execute("""
            INSERT OR REPLACE INTO foreshadowing_index
            (id, content, location, characters, introduced_chapter, resolved_chapter, status, urgency, updated_at)
            VALUES ((SELECT id FROM foreshadowing_index WHERE content = ?), ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            plot.get('description', ''),  # 用于查重
            plot.get('description', ''),
            location,
            json.dumps(characters, ensure_ascii=False),
            plot.get('introduced_chapter', 0),
            plot.get('resolved_chapter', None),
            status,
            urgency
        ))

    def _calculate_urgency(self, plot: Dict, current_chapter: int) -> int:
        """计算伏笔紧急度（0-100）

        规则：
        - 超过 100 章未回收 → 极度紧急（100）
        - 超过 50 章未回收 → 中等紧急（60）
        - 其他 → 正常（20）
        """
        introduced_ch = plot.get('introduced_chapter', 0)
        chapters_pending = current_chapter - introduced_ch

        if chapters_pending > 100:
            return 100  # 极度紧急
        elif chapters_pending > 50:
            return 60   # 中等紧急
        else:
            return 20   # 正常

    # ================== v4.0 实体同步（使用 entities_v3）==================

    def sync_entities_from_state(self):
        """从 state.json.entities_v3 同步实体到 entities/entity_aliases 表

        v4.0 新增：取代旧的 sync_characters_from_state
        数据源：state.json.entities_v3 + alias_index
        """
        if not self.state_file.exists():
            print("❌ state.json 不存在，跳过实体同步")
            return

        with open(self.state_file, 'r', encoding='utf-8') as f:
            state = json.load(f)

        entities_v3 = state.get('entities_v3', {})
        alias_index = state.get('alias_index', {})

        # v4.0：索引层为派生数据，可直接重建（避免重复插入导致膨胀）
        self.conn.execute("DELETE FROM entity_kv")
        self.conn.execute("DELETE FROM entity_aliases")
        self.conn.execute("DELETE FROM entity_history")
        self.conn.execute("DELETE FROM entities")

        entity_count = 0
        alias_count = 0

        # 遍历所有实体类型
        for entity_type, entities in entities_v3.items():
            for entity_id, entity_data in entities.items():
                # 写入 entities 主表
                canonical_name = entity_data.get('canonical_name', '')
                tier = entity_data.get('tier', '')
                desc = entity_data.get('desc', '')
                created_chapter = entity_data.get('created_chapter', 0)

                self.conn.execute("""
                    INSERT OR REPLACE INTO entities
                    (entity_id, entity_type, canonical_name, tier, desc, created_chapter, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (entity_id, entity_type, canonical_name, tier, desc, created_chapter))
                entity_count += 1

                # 写入实体 KV 属性
                current = entity_data.get('current', {})
                last_chapter = current.get("last_chapter", created_chapter) if isinstance(current, dict) else created_chapter
                try:
                    last_chapter = int(last_chapter)
                except (TypeError, ValueError):
                    last_chapter = int(created_chapter or 0)
                for key, value in current.items():
                    value_str = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
                    self.conn.execute("""
                        INSERT OR REPLACE INTO entity_kv
                        (entity_id, key, value, last_chapter)
                        VALUES (?, ?, ?, ?)
                    """, (entity_id, key, value_str, last_chapter))

                # 写入历史记录
                history = entity_data.get('history', [])
                for record in history:
                    chapter = record.get('chapter', 0)
                    changes = record.get('changes', {})
                    reasons = record.get('reasons', {})
                    self.conn.execute("""
                        INSERT OR IGNORE INTO entity_history
                        (entity_id, chapter, changes_json, reasons_json)
                        VALUES (?, ?, ?, ?)
                    """, (entity_id, chapter, json.dumps(changes, ensure_ascii=False), json.dumps(reasons, ensure_ascii=False)))

        # 同步别名索引
        for alias, entries in alias_index.items():
            # v4.0: entries 必须是数组（一对多）
            if not isinstance(entries, list):
                raise ValueError(
                    f"alias_index 数据格式错误：期望 alias_index[{alias!r}] 为 list[{{type,id,...}}]，实际为 {type(entries).__name__}"
                )
            for entry in entries:
                entry_type = entry.get('type', '')
                entry_id = entry.get('id', '')
                first_seen = entry.get('first_seen_chapter', 0)
                context = entry.get('context', '')

                self.conn.execute("""
                    INSERT OR REPLACE INTO entity_aliases
                    (alias, entity_id, entity_type, first_seen_chapter, context)
                    VALUES (?, ?, ?, ?, ?)
                """, (alias, entry_id, entry_type, first_seen, context))
                alias_count += 1

        self.conn.commit()
        print(f"✅ 实体索引已同步：{entity_count} 个实体，{alias_count} 个别名")

    def query_entity_by_id(self, entity_id: str) -> Optional[Dict]:
        """通过 entity_id 查询实体详情"""
        cursor = self.conn.execute("""
            SELECT entity_id, entity_type, canonical_name, tier, desc, created_chapter
            FROM entities WHERE entity_id = ?
        """, (entity_id,))
        row = cursor.fetchone()
        if not row:
            return None

        result = dict(row)

        # 获取 KV 属性
        cursor = self.conn.execute("""
            SELECT key, value FROM entity_kv WHERE entity_id = ?
        """, (entity_id,))
        result['current'] = {}
        for kv_row in cursor.fetchall():
            try:
                result['current'][kv_row['key']] = json.loads(kv_row['value'])
            except json.JSONDecodeError:
                result['current'][kv_row['key']] = kv_row['value']

        # 获取别名
        cursor = self.conn.execute("""
            SELECT alias FROM entity_aliases WHERE entity_id = ?
        """, (entity_id,))
        result['aliases'] = [row['alias'] for row in cursor.fetchall()]

        return result

    def query_entities_by_alias(self, alias: str) -> List[Dict]:
        """通过别名查询实体（支持一对多）"""
        cursor = self.conn.execute("""
            SELECT ea.entity_id, ea.entity_type, e.canonical_name, e.tier
            FROM entity_aliases ea
            LEFT JOIN entities e ON ea.entity_id = e.entity_id
            WHERE ea.alias = ?
        """, (alias,))
        return [dict(row) for row in cursor.fetchall()]

    def query_entities_by_type(self, entity_type: str, limit: int = 50) -> List[Dict]:
        """按类型查询实体"""
        cursor = self.conn.execute("""
            SELECT entity_id, canonical_name, tier, desc
            FROM entities
            WHERE entity_type = ?
            ORDER BY created_chapter DESC
            LIMIT ?
        """, (entity_type, limit))
        return [dict(row) for row in cursor.fetchall()]

    def sync_characters_from_state(self):
        """从 state.json 同步角色数据到索引（v4.0 已废弃）

        保留兼容：调用新的 sync_entities_from_state
        """
        # v4.0: 委托给新函数
        self.sync_entities_from_state()

    def _index_character(self, char: Dict, status: str = 'active'):
        """为单个角色建立索引"""
        description = char.get('description') or char.get('desc') or ''
        tier = str(char.get('tier', '') or '').strip()
        importance = char.get('importance') or ('major' if tier == '核心' else 'minor')

        first_appearance = char.get('first_appearance_chapter', 0) or 0
        try:
            first_appearance = int(first_appearance)
        except (TypeError, ValueError):
            first_appearance = 0

        if first_appearance == 0:
            src = char.get('first_appearance')
            if isinstance(src, str):
                m = re.search(r'第(\d+)章', src)
                if m:
                    try:
                        first_appearance = int(m.group(1))
                    except ValueError:
                        first_appearance = 0

        last_appearance = char.get('last_appearance_chapter', 0) or first_appearance
        try:
            last_appearance = int(last_appearance)
        except (TypeError, ValueError):
            last_appearance = first_appearance

        self.conn.execute("""
            INSERT OR REPLACE INTO characters
            (name, description, personality, importance, power_level,
             first_appearance, last_appearance, status, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            char.get('name', ''),
            description,
            char.get('personality', ''),
            importance,
            char.get('power_level', ''),
            first_appearance,
            last_appearance,
            status
        ))

    def mark_character_archived(self, name: str, archived_at: str = None):
        """标记角色为已归档状态（Priority 2 修复）

        Args:
            name: 角色名
            archived_at: 归档时间戳（ISO格式），默认当前时间
        """
        if archived_at is None:
            from datetime import datetime
            archived_at = datetime.now().isoformat()

        self.conn.execute("""
            UPDATE characters
            SET status = 'archived', archived_at = ?, updated_at = CURRENT_TIMESTAMP
            WHERE name = ?
        """, (archived_at, name))
        self.conn.commit()

    def mark_character_active(self, name: str):
        """恢复角色为活跃状态（与 mark_character_archived 对应）"""
        self.conn.execute("""
            UPDATE characters
            SET status = 'active', archived_at = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE name = ?
        """, (name,))
        self.conn.commit()

    def query_urgent_foreshadowing(self, threshold: int = 60) -> List[Dict]:
        """查询紧急伏笔（urgency >= threshold）

        Args:
            threshold: 紧急度阈值（60=中等紧急，80=高度紧急，100=极度紧急）

        Returns:
            [{'content': '...', 'introduced_chapter': 45, 'urgency': 80}, ...]
        """
        cursor = self.conn.execute("""
            SELECT content, introduced_chapter, urgency
            FROM foreshadowing_index
            WHERE status = '未回收' AND urgency >= ?
            ORDER BY urgency DESC
        """, (threshold,))

        return [dict(row) for row in cursor.fetchall()]

    def sync_relationships_from_state(self):
        """从 state.json 同步关系数据到索引（v4.0: 使用 entity_id）

        触发时机：
        - extract_entities.py 更新关系后调用
        - --rebuild-index 批量重建时调用

        数据来源: state.json 的 structured_relationships 列表
        """
        if not self.state_file.exists():
            print("❌ state.json 不存在，跳过关系同步")
            return

        # 读取 state.json
        with open(self.state_file, 'r', encoding='utf-8') as f:
            state = json.load(f)

        # 获取结构化关系列表
        relationships = state.get('structured_relationships', [])
        if not relationships:
            print("ℹ️ 无结构化关系数据")
            return

        count = 0
        for rel in relationships:
            # v4.0: 关系必须用 entity_id（chapter tags 是真相，避免 name 漂移）
            char1_id = str(rel.get('char1_id', '') or '').strip()
            char2_id = str(rel.get('char2_id', '') or '').strip()
            char1_name = str(rel.get('char1_name', '') or '').strip()
            char2_name = str(rel.get('char2_name', '') or '').strip()
            rel_type = rel.get('type', 'ally')
            intensity = rel.get('intensity', 50)
            desc = rel.get('description', '')
            last_chapter = rel.get('last_update_chapter', 0)

            if not char1_id or not char2_id:
                print("⚠️ 跳过无效关系（缺少 char1_id/char2_id）")
                continue

            # 补齐显示名（可选）
            if not char1_name:
                row = self.conn.execute("SELECT canonical_name FROM entities WHERE entity_id = ? LIMIT 1", (char1_id,)).fetchone()
                char1_name = (row["canonical_name"] if row else "") or char1_id
            if not char2_name:
                row = self.conn.execute("SELECT canonical_name FROM entities WHERE entity_id = ? LIMIT 1", (char2_id,)).fetchone()
                char2_name = (row["canonical_name"] if row else "") or char2_id

            self.conn.execute("""
                INSERT OR REPLACE INTO relationships
                (id, char1_id, char2_id, char1_name, char2_name, relation_type, intensity, description, last_update_chapter, updated_at)
                VALUES (
                    (SELECT id FROM relationships WHERE char1_id = ? AND char2_id = ? AND relation_type = ?),
                    ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP
                )
            """, (
                char1_id, char2_id, rel_type,  # for subquery
                char1_id, char2_id, char1_name, char2_name, rel_type, intensity, desc, last_chapter
            ))
            count += 1

        self.conn.commit()
        print(f"✅ 关系索引已同步：{count} 条关系")

    def query_relationships(self, char_id: str = None, rel_type: str = None) -> List[Dict]:
        """查询角色关系（v4.0: 使用 entity_id）

        Args:
            char_id: 角色 entity_id（可选，查该角色的所有关系）
            rel_type: 关系类型（可选，过滤特定类型）

        Returns:
            [{'char1_id': '...', 'char2_id': '...', 'type': 'romance', 'intensity': 80, ...}, ...]
        """
        conditions = []
        params = []

        if char_id:
            conditions.append("(char1_id = ? OR char2_id = ?)")
            params.extend([char_id, char_id])

        if rel_type:
            conditions.append("relation_type = ?")
            params.append(rel_type)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        cursor = self.conn.execute(f"""
            SELECT char1_id, char2_id, char1_name, char2_name, relation_type, intensity, description, last_update_chapter
            FROM relationships
            WHERE {where_clause}
            ORDER BY intensity DESC
        """, params)

        return [dict(row) for row in cursor.fetchall()]

    # ================== 核心功能 3：模糊查询（Fuzzy Search via SQL LIKE）==================

    def fuzzy_search_entity(self, keywords: List[str], entity_type: str = None) -> List[Dict]:
        """模糊查询实体（v4.0 新增，支持多关键词 + 类型过滤）

        Args:
            keywords: 关键词列表，如 ["李", "女弟子"]
            entity_type: 可选，过滤实体类型（角色/地点/物品/势力/招式）

        Returns:
            [{'entity_id': '...', 'canonical_name': '...', 'desc': '...', 'tier': '...'}, ...]
        """
        # 构建 WHERE 子句
        conditions = []
        params = []

        for kw in keywords:
            # 每个关键词在 canonical_name/desc 任一字段中出现即可
            conditions.append("(e.canonical_name LIKE ? OR e.desc LIKE ? OR ea.alias LIKE ?)")
            params.extend([f'%{kw}%', f'%{kw}%', f'%{kw}%'])

        if entity_type:
            conditions.append("e.entity_type = ?")
            params.append(entity_type)

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT DISTINCT e.entity_id, e.entity_type, e.canonical_name, e.tier, e.desc, e.created_chapter
            FROM entities e
            LEFT JOIN entity_aliases ea ON e.entity_id = ea.entity_id
            WHERE {where_clause}
            ORDER BY e.tier DESC, e.created_chapter DESC
            LIMIT 20
        """

        cursor = self.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def fuzzy_search_character(self, keywords: List[str]) -> List[Dict]:
        """模糊查询角色（v4.0: 委托给 fuzzy_search_entity）

        Args:
            keywords: 关键词列表，如 ["李", "女弟子"]

        Returns:
            [{'entity_id': '...', 'canonical_name': '...', 'desc': '...', ...}, ...]
        """
        return self.fuzzy_search_entity(keywords, entity_type="角色")

    # ================== 批量操作 ==================

    def rebuild_all_indexes(self):
        """批量重建所有历史章节的索引

        使用场景：
        - 索引系统首次上线
        - 索引数据库损坏
        """
        if not self.chapters_dir.exists():
            print("❌ 章节目录不存在")
            return

        # 获取所有章节文件
        chapter_files = sorted(self.chapters_dir.rglob("第*.md"))

        print(f"🔍 发现 {len(chapter_files)} 个章节文件，开始重建索引...")

        seen = set()
        for chapter_file in chapter_files:
            # 提取章节编号
            match = re.search(r'第(\d+)章', chapter_file.name)
            if not match:
                continue

            chapter_num = int(match.group(1))
            if chapter_num in seen:
                continue
            seen.add(chapter_num)

            # 重建索引
            self._rebuild_chapter_index(chapter_num, chapter_file)

        # 同步伏笔索引
        self.sync_foreshadowing_from_state()
        self.sync_characters_from_state()
        self.sync_relationships_from_state()

        print(f"✅ 批量重建完成：{len(seen)} 章")

    # ================== 查询与统计 ==================

    def get_index_stats(self) -> Dict:
        """获取索引统计信息（v4.0: 增加实体/别名统计）"""

        # 章节统计
        cursor = self.conn.execute("SELECT COUNT(*) as count FROM chapters")
        chapter_count = cursor.fetchone()['count']

        # 实体统计（v4.0 新增）
        cursor = self.conn.execute("""
            SELECT entity_type, COUNT(*) as count
            FROM entities
            GROUP BY entity_type
        """)
        entity_stats = {row['entity_type']: row['count'] for row in cursor.fetchall()}

        # 别名统计（v4.0 新增）
        cursor = self.conn.execute("SELECT COUNT(*) as count FROM entity_aliases")
        alias_count = cursor.fetchone()['count']

        # 伏笔统计
        cursor = self.conn.execute("""
            SELECT status, COUNT(*) as count
            FROM foreshadowing_index
            GROUP BY status
        """)
        foreshadowing_stats = {row['status']: row['count'] for row in cursor.fetchall()}

        # 关系统计
        cursor = self.conn.execute("SELECT COUNT(*) as count FROM relationships")
        relationship_count = cursor.fetchone()['count']

        # 数据库大小
        db_size_kb = self.index_db.stat().st_size / 1024

        return {
            'chapter_count': chapter_count,
            'entity_stats': entity_stats,
            'alias_count': alias_count,
            'foreshadowing_active': foreshadowing_stats.get('未回收', 0),
            'foreshadowing_resolved': foreshadowing_stats.get('已回收', 0),
            'relationship_count': relationship_count,
            'db_size_kb': round(db_size_kb, 2)
        }

    def __del__(self):
        """析构函数：关闭数据库连接"""
        if hasattr(self, 'conn'):
            self.conn.close()


def main():
    parser = argparse.ArgumentParser(description="结构化索引系统（取代向量化检索）")

    # 更新操作
    parser.add_argument("--update-chapter", type=int, metavar="NUM", help="更新单章索引")
    parser.add_argument("--metadata", metavar="PATH", help="章节文件路径（配合 --update-chapter）")
    parser.add_argument("--metadata-json", metavar="JSON", help="元数据 JSON 字符串（配合 --update-chapter，由 metadata-extractor agent 提供）")
    parser.add_argument("--metadata-file", metavar="FILE", help="元数据 JSON 文件路径（配合 --update-chapter，Windows 推荐使用此参数）")

    # 批量操作
    parser.add_argument("--rebuild-index", action="store_true", help="批量重建所有索引")

    # 查询操作
    parser.add_argument("--query-location", metavar="LOCATION", help="查询地点相关章节")
    parser.add_argument("--query-urgent-foreshadowing", action="store_true", help="查询紧急伏笔")
    parser.add_argument("--fuzzy-search", nargs='+', metavar="KEYWORD", help="模糊查询角色（多个关键词）")

    # 统计信息
    parser.add_argument("--stats", action="store_true", help="显示索引统计信息")

    # 项目路径
    parser.add_argument("--project-root", metavar="PATH", help="项目根目录（默认为当前目录）")

    args = parser.parse_args()

    # 创建索引管理器
    index = StructuredIndex(project_root=args.project_root)

    # 执行操作
    if args.update_chapter:
        # 模式1：从 JSON 文件读取（Windows 推荐，避免 CLI 引号转义问题）
        if args.metadata_file:
            try:
                metadata_file = Path(args.metadata_file)
                if not metadata_file.exists():
                    print(f"❌ 元数据文件不存在: {metadata_file}")
                    return

                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)

                # 验证必需字段
                required_fields = ['title', 'location', 'characters', 'word_count', 'hash']
                missing_fields = [f for f in required_fields if f not in metadata]

                if missing_fields:
                    print(f"❌ JSON 缺少必需字段: {', '.join(missing_fields)}")
                    return

                # 先同步实体（用于将 metadata.characters/name 解析为 entity_id）
                index.sync_entities_from_state()

                # 更新章节索引
                index.index_chapter(args.update_chapter, metadata)

                # 同步伏笔索引
                index.sync_foreshadowing_from_state()
                # bump_character_last_appearance_in_state 已删除（v4.0）
                index.sync_relationships_from_state()

            except json.JSONDecodeError as e:
                print(f"❌ JSON 解析失败: {e}")
                return

        # 模式2：直接接收 JSON 字符串（Linux/macOS，或测试时使用）
        elif args.metadata_json:
            try:
                metadata = json.loads(args.metadata_json)

                # 验证必需字段
                required_fields = ['title', 'location', 'characters', 'word_count', 'hash']
                missing_fields = [f for f in required_fields if f not in metadata]

                if missing_fields:
                    print(f"❌ JSON 缺少必需字段: {', '.join(missing_fields)}")
                    return

                # 先同步实体（用于将 metadata.characters/name 解析为 entity_id）
                index.sync_entities_from_state()

                # 更新章节索引
                index.index_chapter(args.update_chapter, metadata)

                # 同步伏笔索引
                index.sync_foreshadowing_from_state()
                # bump_character_last_appearance_in_state 已删除（v4.0）
                index.sync_relationships_from_state()

            except json.JSONDecodeError as e:
                print(f"❌ JSON 解析失败: {e}")
                return

        # 模式3：从章节文件提取元数据（旧模式，保持向后兼容）
        elif args.metadata:
            # 读取章节文件
            chapter_file = Path(args.metadata)
            if not chapter_file.exists():
                print(f"❌ 章节文件不存在: {chapter_file}")
                return

            # 提取元数据
            with open(chapter_file, 'r', encoding='utf-8') as f:
                content = f.read()

            metadata = index._extract_metadata_from_content(content, args.update_chapter)

            # 先同步实体（用于将 metadata.characters/name 解析为 entity_id）
            index.sync_entities_from_state()

            # 更新章节索引
            index.index_chapter(args.update_chapter, metadata)

            # 同步伏笔索引
            index.sync_foreshadowing_from_state()
            # bump_character_last_appearance_in_state 已删除（v4.0）
            index.sync_relationships_from_state()

        else:
            print("❌ 缺少参数：--metadata-file (推荐) / --metadata-json / --metadata")
            return

    elif args.rebuild_index:
        index.rebuild_all_indexes()

    elif args.query_location:
        results = index.query_chapters_by_location(args.query_location)

        if not results:
            print(f"未找到地点相关章节: {args.query_location}")
        else:
            print(f"找到 {len(results)} 个相关章节：")
            for chapter_num, title, characters in results:
                print(f"  Ch{chapter_num}: {title} - 角色: {characters}")

    elif args.query_urgent_foreshadowing:
        results = index.query_urgent_foreshadowing(threshold=60)

        if not results:
            print("✅ 无紧急伏笔")
        else:
            print(f"⚠️ 检测到 {len(results)} 条紧急伏笔：")
            for item in results:
                print(f"  - {item['content'][:30]}...（第 {item['introduced_chapter']} 章埋设，紧急度 {item['urgency']}/100）")

    elif args.fuzzy_search:
        results = index.fuzzy_search_character(args.fuzzy_search)

        if not results:
            print(f"未找到匹配角色: {' + '.join(args.fuzzy_search)}")
        else:
            print(f"找到 {len(results)} 个匹配角色：")
            for i, char in enumerate(results, 1):
                # v4.0: 使用新字段名
                name = char.get('canonical_name', char.get('name', ''))
                desc = char.get('desc', char.get('description', ''))[:50]
                tier = char.get('tier', '')
                print(f"{i}. {name} [{tier}] - {desc}...")

    elif args.stats:
        stats = index.get_index_stats()

        print("📊 索引统计信息：")
        print(f"   章节索引: {stats['chapter_count']}")

        # v4.0: 显示实体统计
        entity_stats = stats.get('entity_stats', {})
        if entity_stats:
            entity_summary = ", ".join([f"{t}: {c}" for t, c in entity_stats.items()])
            print(f"   实体索引: {entity_summary}")
        print(f"   别名索引: {stats.get('alias_count', 0)}")

        print(f"   伏笔索引: {stats['foreshadowing_active']} 条活跃 + {stats['foreshadowing_resolved']} 条已回收")
        print(f"   关系索引: {stats['relationship_count']}")
        print(f"   数据库大小: {stats['db_size_kb']} KB")

    else:
        parser.print_help()


if __name__ == "__main__":
    # Windows UTF-8 编码修复（仅在脚本直接运行时）
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    main()
