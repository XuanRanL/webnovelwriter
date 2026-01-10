#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
500章索引系统压力测试

测试目标：
1. index.db 大小增长曲线
2. 实体同步性能（entities_v3 → index.db）
3. 别名查询性能
4. 模糊搜索性能
5. 伏笔紧急度计算性能
6. 关系图查询性能
7. 并发读写稳定性

依赖：stress_test_500chapters.py 生成的 state.json
"""

import json
import os
import sys
import time
import random
import sqlite3
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Tuple

# 添加脚本目录到路径
script_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(script_dir))

from security_utils import atomic_write_json, read_json_safe

# Windows 编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


# ============================================================================
# 模拟配置（与 stress_test_500chapters.py 保持一致）
# ============================================================================

CONFIG = {
    "total_chapters": 500,
    "words_per_chapter": 3500,
    "new_character_base_rate": 0.8,
    "new_character_decay": 0.95,
    "new_location_rate": 0.3,
    "new_item_rate": 0.2,
    "foreshadow_plant_rate": 0.5,
    "foreshadow_resolve_rate": 0.3,
    "relationship_update_interval": 5,
}

SURNAME_POOL = ["林", "陈", "王", "李", "张", "刘", "赵", "黄", "周", "吴", "徐", "孙", "马", "朱", "胡", "郭", "何", "高", "罗", "郑"]
NAME_POOL = ["天", "云", "风", "雷", "火", "水", "月", "星", "龙", "凤", "虎", "鹤", "剑", "刀", "枪", "棍", "拳", "掌", "指", "心"]


class IndexMetrics:
    """索引性能指标收集器"""

    def __init__(self):
        self.checkpoints: List[Dict] = []
        self.sync_times: List[float] = []
        self.query_times: Dict[str, List[float]] = {
            "alias_lookup": [],
            "fuzzy_search": [],
            "foreshadow_urgency": [],
            "relationship_query": [],
            "entity_by_type": [],
        }
        self.errors: List[str] = []

    def record_checkpoint(self, chapter: int, db_path: Path, state: Dict):
        """记录检查点"""
        db_size = db_path.stat().st_size if db_path.exists() else 0

        # 统计各表行数
        table_counts = {}
        if db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                for table in ["chapters", "entities", "entity_aliases", "entity_kv",
                              "entity_history", "foreshadowing_index", "relationships"]:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        table_counts[table] = cursor.fetchone()[0]
                    except sqlite3.OperationalError:
                        table_counts[table] = 0
                conn.close()
            except Exception as e:
                self.errors.append(f"DB stats error: {e}")

        self.checkpoints.append({
            "chapter": chapter,
            "db_size_kb": db_size / 1024,
            "table_counts": table_counts,
            "avg_sync_time_ms": sum(self.sync_times[-10:]) / max(len(self.sync_times[-10:]), 1) * 1000,
            "query_performance": {
                k: sum(v[-10:]) / max(len(v[-10:]), 1) * 1000
                for k, v in self.query_times.items()
            }
        })

    def record_sync_time(self, duration: float):
        self.sync_times.append(duration)

    def record_query_time(self, query_type: str, duration: float):
        if query_type in self.query_times:
            self.query_times[query_type].append(duration)

    def record_error(self, error: str):
        self.errors.append(error)

    def generate_report(self) -> str:
        """生成测试报告"""
        if not self.checkpoints:
            return "No data collected"

        final = self.checkpoints[-1]
        first = self.checkpoints[0] if self.checkpoints else final

        lines = [
            "=" * 70,
            "📊 500章索引系统压力测试报告",
            "=" * 70,
            "",
            "## index.db 增长",
            f"- 初始大小: {first['db_size_kb']:.2f} KB",
            f"- 最终大小: {final['db_size_kb']:.2f} KB",
            f"- 增长倍数: {final['db_size_kb'] / max(first['db_size_kb'], 0.1):.1f}x",
            "",
            "## 表行数统计",
        ]

        for table, count in final.get('table_counts', {}).items():
            lines.append(f"  - {table}: {count:,}")

        lines.extend([
            "",
            "## 同步性能",
            f"- 平均同步时间: {sum(self.sync_times) / max(len(self.sync_times), 1) * 1000:.2f} ms",
            f"- 最大同步时间: {max(self.sync_times) * 1000:.2f} ms" if self.sync_times else "N/A",
            f"- 最小同步时间: {min(self.sync_times) * 1000:.2f} ms" if self.sync_times else "N/A",
            "",
            "## 查询性能（平均）",
        ])

        for query_type, times in self.query_times.items():
            if times:
                avg = sum(times) / len(times) * 1000
                lines.append(f"  - {query_type}: {avg:.2f} ms")

        lines.extend([
            "",
            "## 错误统计",
            f"- 错误数: {len(self.errors)}",
        ])

        if self.errors:
            lines.append("- 错误详情:")
            for err in self.errors[:10]:
                lines.append(f"  - {err[:80]}")

        # 增长曲线
        lines.extend([
            "",
            "## 增长曲线（每100章）",
            "| 章节 | DB大小(KB) | entities | aliases | foreshadow | 同步(ms) |",
            "|------|-----------|----------|---------|------------|----------|",
        ])

        for cp in self.checkpoints:
            if cp['chapter'] % 100 == 0 or cp['chapter'] == final['chapter']:
                tc = cp.get('table_counts', {})
                lines.append(
                    f"| {cp['chapter']} | {cp['db_size_kb']:.1f} | "
                    f"{tc.get('entities', 0)} | {tc.get('entity_aliases', 0)} | "
                    f"{tc.get('foreshadowing_index', 0)} | {cp['avg_sync_time_ms']:.1f} |"
                )

        # 查询性能趋势
        lines.extend([
            "",
            "## 查询性能趋势（每100章）",
            "| 章节 | alias查询(ms) | 模糊搜索(ms) | 伏笔紧急度(ms) | 关系查询(ms) |",
            "|------|--------------|-------------|---------------|-------------|",
        ])

        for cp in self.checkpoints:
            if cp['chapter'] % 100 == 0 or cp['chapter'] == final['chapter']:
                qp = cp.get('query_performance', {})
                lines.append(
                    f"| {cp['chapter']} | {qp.get('alias_lookup', 0):.2f} | "
                    f"{qp.get('fuzzy_search', 0):.2f} | "
                    f"{qp.get('foreshadow_urgency', 0):.2f} | "
                    f"{qp.get('relationship_query', 0):.2f} |"
                )

        # 稳定性评估
        lines.extend([
            "",
            "## 稳定性评估",
        ])

        if final['db_size_kb'] < 1024:
            lines.append("✅ 数据库大小合理 (< 1MB)")
        elif final['db_size_kb'] < 5120:
            lines.append("⚠️ 数据库偏大 (1-5MB)")
        else:
            lines.append("❌ 数据库过大 (> 5MB)")

        avg_sync = sum(self.sync_times) / max(len(self.sync_times), 1) * 1000
        if avg_sync < 100:
            lines.append("✅ 同步性能良好 (< 100ms)")
        elif avg_sync < 500:
            lines.append("⚠️ 同步性能一般 (100-500ms)")
        else:
            lines.append("❌ 同步性能差 (> 500ms)")

        # 查询性能评估
        for query_type, times in self.query_times.items():
            if times:
                avg = sum(times) / len(times) * 1000
                if avg < 10:
                    lines.append(f"✅ {query_type} 查询快速 (< 10ms)")
                elif avg < 50:
                    lines.append(f"⚠️ {query_type} 查询一般 (10-50ms)")
                else:
                    lines.append(f"❌ {query_type} 查询慢 (> 50ms)")

        if not self.errors:
            lines.append("✅ 无错误")
        else:
            lines.append(f"❌ 有 {len(self.errors)} 个错误")

        lines.append("")
        lines.append("=" * 70)

        return "\n".join(lines)


class IndexSimulator:
    """索引系统模拟器"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.state_file = project_root / ".webnovel" / "state.json"
        self.db_path = project_root / ".webnovel" / "index.db"
        self.metrics = IndexMetrics()
        self.generated_names = set()
        self.entity_id_counter = 0

    def _generate_id(self, prefix: str) -> str:
        self.entity_id_counter += 1
        return f"{prefix}_{self.entity_id_counter:05d}"

    def _generate_character_name(self) -> str:
        for _ in range(100):
            name = random.choice(SURNAME_POOL) + random.choice(NAME_POOL) + random.choice(NAME_POOL)
            if name not in self.generated_names:
                self.generated_names.add(name)
                return name
        return f"角色_{len(self.generated_names)}"

    def _get_character_rate(self, chapter: int) -> float:
        decay_periods = chapter // 50
        rate = CONFIG["new_character_base_rate"] * (CONFIG["new_character_decay"] ** decay_periods)
        return max(rate, 0.1)

    def init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # 创建表结构（与 structured_index.py 一致）
        cursor.executescript("""
            -- 章节表
            CREATE TABLE IF NOT EXISTS chapters (
                chapter_num INTEGER PRIMARY KEY,
                title TEXT,
                word_count INTEGER,
                summary TEXT,
                main_location TEXT,
                characters TEXT,
                content_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- 实体主表
            CREATE TABLE IF NOT EXISTS entities (
                entity_id TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL,
                canonical_name TEXT,
                tier TEXT,
                desc TEXT,
                created_chapter INTEGER,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- 别名表
            CREATE TABLE IF NOT EXISTS entity_aliases (
                alias TEXT,
                entity_id TEXT,
                entity_type TEXT,
                first_seen_chapter INTEGER,
                context TEXT,
                PRIMARY KEY (alias, entity_id)
            );
            CREATE INDEX IF NOT EXISTS idx_alias ON entity_aliases(alias);

            -- 实体属性 (KV)
            CREATE TABLE IF NOT EXISTS entity_kv (
                entity_id TEXT,
                key TEXT,
                value TEXT,
                last_chapter INTEGER,
                PRIMARY KEY (entity_id, key)
            );

            -- 实体历史
            CREATE TABLE IF NOT EXISTS entity_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id TEXT,
                chapter INTEGER,
                changes_json TEXT,
                reasons_json TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- 伏笔索引
            CREATE TABLE IF NOT EXISTS foreshadowing_index (
                foreshadow_id TEXT PRIMARY KEY,
                content TEXT,
                tier TEXT,
                status TEXT,
                planted_chapter INTEGER,
                target_chapter INTEGER,
                resolved_chapter INTEGER,
                urgency_score REAL
            );

            -- 关系表
            CREATE TABLE IF NOT EXISTS relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                char1_id TEXT,
                char2_id TEXT,
                rel_type TEXT,
                intensity INTEGER,
                established_chapter INTEGER,
                description TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_rel_char1 ON relationships(char1_id);
            CREATE INDEX IF NOT EXISTS idx_rel_char2 ON relationships(char2_id);
        """)

        conn.commit()
        conn.close()

    def init_project(self):
        """初始化模拟项目"""
        self.project_root.mkdir(parents=True, exist_ok=True)
        (self.project_root / ".webnovel").mkdir(exist_ok=True)

        # 初始 state.json
        initial_state = {
            "project_info": {"title": "索引测试小说", "genre": "玄幻"},
            "progress": {"current_chapter": 0, "total_words": 0},
            "protagonist_state": {"name": "林天", "realm": "练气", "layer": 1},
            "entities_v3": {"角色": {}, "地点": {}, "物品": {}, "势力": {}, "招式": {}},
            "alias_index": {},
            "foreshadowing": [],
            "relationships": [],
        }

        # 添加主角
        protagonist_id = "protagonist_lintian"
        initial_state["entities_v3"]["角色"][protagonist_id] = {
            "canonical_name": "林天",
            "desc": "主角",
            "tier": "核心",
            "aliases": ["林天", "天哥"],
            "current": {"realm": "练气"},
            "history": [],
        }
        initial_state["alias_index"]["林天"] = [{"type": "角色", "id": protagonist_id}]

        atomic_write_json(self.state_file, initial_state, backup=False)
        self.init_database()
        return initial_state

    def sync_to_index(self, state: Dict, chapter: int):
        """同步 state.json 到 index.db"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            # 同步章节
            cursor.execute("""
                INSERT OR REPLACE INTO chapters
                (chapter_num, title, word_count, summary)
                VALUES (?, ?, ?, ?)
            """, (chapter, f"第{chapter}章", CONFIG["words_per_chapter"], f"第{chapter}章摘要"))

            # 同步实体
            entities_v3 = state.get("entities_v3", {})
            for entity_type, entities in entities_v3.items():
                for entity_id, entity_data in entities.items():
                    cursor.execute("""
                        INSERT OR REPLACE INTO entities
                        (entity_id, entity_type, canonical_name, tier, desc, created_chapter)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        entity_id,
                        entity_type,
                        entity_data.get("canonical_name", ""),
                        entity_data.get("tier", "装饰"),
                        entity_data.get("desc", ""),
                        chapter
                    ))

                    # 同步别名
                    for alias in entity_data.get("aliases", []):
                        cursor.execute("""
                            INSERT OR IGNORE INTO entity_aliases
                            (alias, entity_id, entity_type, first_seen_chapter)
                            VALUES (?, ?, ?, ?)
                        """, (alias, entity_id, entity_type, chapter))

                    # 同步当前属性
                    for key, value in entity_data.get("current", {}).items():
                        cursor.execute("""
                            INSERT OR REPLACE INTO entity_kv
                            (entity_id, key, value, last_chapter)
                            VALUES (?, ?, ?, ?)
                        """, (entity_id, key, str(value), chapter))

            # 同步伏笔
            for fs in state.get("foreshadowing", []):
                # 计算紧急度
                if fs.get("status") == "未回收":
                    target = fs.get("target_chapter", chapter + 100)
                    urgency = max(0, 100 - (target - chapter))
                else:
                    urgency = 0

                cursor.execute("""
                    INSERT OR REPLACE INTO foreshadowing_index
                    (foreshadow_id, content, tier, status, planted_chapter,
                     target_chapter, resolved_chapter, urgency_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    fs.get("id", f"fs_{chapter}"),
                    fs.get("content", ""),
                    fs.get("tier", "装饰"),
                    fs.get("status", "未回收"),
                    fs.get("planted_chapter", chapter),
                    fs.get("target_chapter"),
                    fs.get("resolved_chapter"),
                    urgency
                ))

            # 同步关系（使用 REPLACE 避免重复）
            # 先清空再重建（简化策略，实际生产应增量同步）
            cursor.execute("DELETE FROM relationships WHERE established_chapter <= ?", (chapter,))
            for rel in state.get("relationships", []):
                cursor.execute("""
                    INSERT INTO relationships
                    (char1_id, char2_id, rel_type, intensity, established_chapter)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    rel.get("char1_id", ""),
                    rel.get("char2_id", ""),
                    rel.get("type", "ally"),
                    rel.get("intensity", 50),
                    rel.get("established_chapter", chapter)
                ))

            conn.commit()

        finally:
            conn.close()

    def run_queries(self, state: Dict, chapter: int):
        """执行各类查询并计时"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            # 1. 别名查询
            alias_list = list(state.get("alias_index", {}).keys())
            if alias_list:
                test_alias = random.choice(alias_list)
                start = time.time()
                cursor.execute("SELECT entity_id, entity_type FROM entity_aliases WHERE alias = ?", (test_alias,))
                cursor.fetchall()
                self.metrics.record_query_time("alias_lookup", time.time() - start)

            # 2. 模糊搜索
            if alias_list:
                search_term = random.choice(alias_list)[:2]  # 取前两个字
                start = time.time()
                cursor.execute("""
                    SELECT DISTINCT entity_id, entity_type, alias
                    FROM entity_aliases
                    WHERE alias LIKE ?
                    LIMIT 20
                """, (f"%{search_term}%",))
                cursor.fetchall()
                self.metrics.record_query_time("fuzzy_search", time.time() - start)

            # 3. 伏笔紧急度查询
            start = time.time()
            cursor.execute("""
                SELECT foreshadow_id, content, urgency_score
                FROM foreshadowing_index
                WHERE status = '未回收'
                ORDER BY urgency_score DESC
                LIMIT 10
            """)
            cursor.fetchall()
            self.metrics.record_query_time("foreshadow_urgency", time.time() - start)

            # 4. 关系查询
            entities_v3 = state.get("entities_v3", {})
            char_ids = list(entities_v3.get("角色", {}).keys())
            if char_ids:
                test_char = random.choice(char_ids)
                start = time.time()
                cursor.execute("""
                    SELECT char2_id, rel_type, intensity
                    FROM relationships
                    WHERE char1_id = ?
                    UNION
                    SELECT char1_id, rel_type, intensity
                    FROM relationships
                    WHERE char2_id = ?
                """, (test_char, test_char))
                cursor.fetchall()
                self.metrics.record_query_time("relationship_query", time.time() - start)

            # 5. 按类型查询实体
            start = time.time()
            cursor.execute("""
                SELECT entity_id, canonical_name, tier
                FROM entities
                WHERE entity_type = '角色' AND tier = '核心'
            """)
            cursor.fetchall()
            self.metrics.record_query_time("entity_by_type", time.time() - start)

        finally:
            conn.close()

    def simulate_chapter(self, chapter: int, state: Dict) -> Dict:
        """模拟一章的数据变化（与主测试脚本类似）"""
        state["progress"]["current_chapter"] = chapter
        state["progress"]["total_words"] += CONFIG["words_per_chapter"]

        entities_v3 = state["entities_v3"]
        alias_index = state["alias_index"]

        # 新增角色
        if random.random() < self._get_character_rate(chapter):
            char_name = self._generate_character_name()
            char_id = self._generate_id("char")
            tier = random.choices(["核心", "支线", "装饰"], weights=[0.1, 0.3, 0.6])[0]

            entities_v3["角色"][char_id] = {
                "canonical_name": char_name,
                "desc": f"第{chapter}章出场",
                "tier": tier,
                "aliases": [char_name],
                "current": {"first_appearance": chapter},
                "history": [],
            }
            alias_index[char_name] = [{"type": "角色", "id": char_id}]

            # 额外别名
            if random.random() < 0.5:
                alias = char_name[0] + "兄"
                entities_v3["角色"][char_id]["aliases"].append(alias)
                if alias not in alias_index:
                    alias_index[alias] = []
                alias_index[alias].append({"type": "角色", "id": char_id})

        # 新增地点
        if random.random() < CONFIG["new_location_rate"]:
            loc_name = random.choice(["天", "云", "龙"]) + random.choice(["山", "谷", "城"])
            loc_id = self._generate_id("loc")
            entities_v3["地点"][loc_id] = {
                "canonical_name": loc_name,
                "desc": f"第{chapter}章",
                "tier": "装饰",
                "aliases": [loc_name],
                "current": {},
                "history": [],
            }
            if loc_name not in alias_index:
                alias_index[loc_name] = []
            alias_index[loc_name].append({"type": "地点", "id": loc_id})

        # 伏笔
        if random.random() < CONFIG["foreshadow_plant_rate"]:
            state["foreshadowing"].append({
                "id": f"fs_{chapter}_{random.randint(1000, 9999)}",
                "content": f"第{chapter}章伏笔",
                "tier": random.choice(["核心", "支线", "装饰"]),
                "status": "未回收",
                "planted_chapter": chapter,
                "target_chapter": chapter + random.randint(10, 100),
            })

        # 回收伏笔
        for fs in state["foreshadowing"]:
            if (fs.get("status") == "未回收" and
                fs.get("target_chapter", 999) <= chapter and
                random.random() < CONFIG["foreshadow_resolve_rate"]):
                fs["status"] = "已回收"
                fs["resolved_chapter"] = chapter

        # 关系
        if chapter % CONFIG["relationship_update_interval"] == 0:
            char_ids = list(entities_v3["角色"].keys())
            if len(char_ids) >= 2:
                char1, char2 = random.sample(char_ids, 2)
                state["relationships"].append({
                    "char1_id": char1,
                    "char2_id": char2,
                    "type": random.choice(["ally", "enemy", "romance", "rival"]),
                    "intensity": random.randint(30, 100),
                    "established_chapter": chapter,
                })

        return state

    def run_simulation(self, checkpoint_interval: int = 10):
        """运行完整模拟"""
        print("🚀 开始500章索引系统压力测试...")
        print(f"📁 测试目录: {self.project_root}")
        print()

        state = self.init_project()
        self.metrics.record_checkpoint(0, self.db_path, state)

        start_time = time.time()

        for chapter in range(1, CONFIG["total_chapters"] + 1):
            try:
                # 模拟章节数据
                state = self.simulate_chapter(chapter, state)

                # 保存 state.json
                atomic_write_json(self.state_file, state, use_lock=True, backup=False)

                # 同步到索引
                sync_start = time.time()
                self.sync_to_index(state, chapter)
                sync_duration = time.time() - sync_start
                self.metrics.record_sync_time(sync_duration)

                # 执行查询测试
                self.run_queries(state, chapter)

                # 记录检查点
                if chapter % checkpoint_interval == 0:
                    self.metrics.record_checkpoint(chapter, self.db_path, state)
                    elapsed = time.time() - start_time
                    eta = elapsed / chapter * (CONFIG["total_chapters"] - chapter)
                    db_size = self.db_path.stat().st_size / 1024 if self.db_path.exists() else 0
                    print(f"  第 {chapter:3d} 章 | "
                          f"DB {db_size:.1f}KB | "
                          f"同步 {sync_duration*1000:.1f}ms | "
                          f"ETA {eta:.0f}s")

            except Exception as e:
                self.metrics.record_error(f"Chapter {chapter}: {str(e)}")
                print(f"  ❌ 第 {chapter} 章错误: {e}")

        # 最终检查点
        self.metrics.record_checkpoint(CONFIG["total_chapters"], self.db_path, state)

        total_time = time.time() - start_time
        print()
        print(f"✅ 索引测试完成！总耗时: {total_time:.1f}s")
        print()

        return self.metrics.generate_report()


def main():
    """主函数"""
    test_dir = Path(tempfile.mkdtemp(prefix="webnovel_index_test_"))

    try:
        simulator = IndexSimulator(test_dir)
        report = simulator.run_simulation(checkpoint_interval=10)

        print(report)

        # 保存报告
        report_file = test_dir / "index_stress_test_report.md"
        report_file.write_text(report, encoding="utf-8")
        print(f"\n📄 报告已保存: {report_file}")
        print(f"\n测试数据目录: {test_dir}")

    except KeyboardInterrupt:
        print("\n⚠️ 测试被中断")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
