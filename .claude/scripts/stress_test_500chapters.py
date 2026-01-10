#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
500章写作沙盘模拟 - 数据链稳定性压力测试

测试目标：
1. state.json 增长曲线（文件大小随章节变化）
2. entities_v3 实体数量增长
3. alias_index 别名索引膨胀
4. 伏笔追踪（埋设/回收比例）
5. 原子写入性能
6. index.db 查询性能

模拟参数（基于典型网文）：
- 500章，每章约3500字
- 平均每章新增 0.8 个角色（前100章密集，后期稀疏）
- 平均每章新增 0.3 个地点
- 平均每章埋设 0.5 个伏笔，回收 0.3 个
- 主角每 10 章升级一次境界
- 每 5 章更新一次关系
"""

import json
import os
import sys
import time
import random
import shutil
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

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
# 模拟配置
# ============================================================================

CONFIG = {
    "total_chapters": 500,
    "words_per_chapter": 3500,

    # 实体生成概率（随章节递减）
    "new_character_base_rate": 0.8,  # 前50章
    "new_character_decay": 0.95,      # 每50章衰减
    "new_location_rate": 0.3,
    "new_item_rate": 0.2,
    "new_faction_rate": 0.1,
    "new_technique_rate": 0.15,

    # 伏笔
    "foreshadow_plant_rate": 0.5,
    "foreshadow_resolve_rate": 0.3,
    "foreshadow_tiers": ["核心", "支线", "装饰"],
    "foreshadow_tier_weights": [0.1, 0.3, 0.6],

    # 主角升级
    "protagonist_upgrade_interval": 10,
    "realms": ["练气", "筑基", "金丹", "元婴", "化神", "炼虚", "合体", "大乘", "渡劫"],
    "layers_per_realm": 9,

    # 关系更新
    "relationship_update_interval": 5,
    "relationship_types": ["ally", "enemy", "romance", "mentor", "rival", "family"],

    # 别名生成
    "alias_per_character": 2.5,  # 平均每个角色的别名数
}

# 随机名字池
SURNAME_POOL = ["林", "陈", "王", "李", "张", "刘", "赵", "黄", "周", "吴", "徐", "孙", "马", "朱", "胡", "郭", "何", "高", "罗", "郑"]
NAME_POOL = ["天", "云", "风", "雷", "火", "水", "月", "星", "龙", "凤", "虎", "鹤", "剑", "刀", "枪", "棍", "拳", "掌", "指", "心"]
LOCATION_PREFIX = ["天", "云", "龙", "凤", "青", "白", "黑", "红", "金", "玉"]
LOCATION_SUFFIX = ["山", "谷", "城", "峰", "洞", "海", "林", "湖", "殿", "宗"]


class SimulationMetrics:
    """模拟指标收集器"""

    def __init__(self):
        self.checkpoints: List[Dict] = []
        self.write_times: List[float] = []
        self.errors: List[str] = []

    def record_checkpoint(self, chapter: int, state: Dict, state_file: Path):
        """记录检查点"""
        file_size = state_file.stat().st_size if state_file.exists() else 0

        entities_v3 = state.get("entities_v3", {})
        entity_counts = {
            etype: len(entities)
            for etype, entities in entities_v3.items()
        }
        total_entities = sum(entity_counts.values())

        alias_count = len(state.get("alias_index", {}))

        foreshadowing = state.get("foreshadowing", [])
        active_foreshadow = len([f for f in foreshadowing if f.get("status") == "未回收"])
        resolved_foreshadow = len([f for f in foreshadowing if f.get("status") == "已回收"])

        relationships = state.get("relationships", [])
        if isinstance(relationships, dict):
            relationships = list(relationships.values())

        self.checkpoints.append({
            "chapter": chapter,
            "file_size_kb": file_size / 1024,
            "total_entities": total_entities,
            "entity_counts": entity_counts,
            "alias_count": alias_count,
            "active_foreshadow": active_foreshadow,
            "resolved_foreshadow": resolved_foreshadow,
            "relationship_count": len(relationships) if isinstance(relationships, list) else 0,
            "avg_write_time_ms": sum(self.write_times[-10:]) / max(len(self.write_times[-10:]), 1) * 1000,
        })

    def record_write_time(self, duration: float):
        self.write_times.append(duration)

    def record_error(self, error: str):
        self.errors.append(error)

    def generate_report(self) -> str:
        """生成测试报告"""
        if not self.checkpoints:
            return "No data collected"

        final = self.checkpoints[-1]
        first = self.checkpoints[0]

        lines = [
            "=" * 60,
            "📊 500章沙盘模拟测试报告",
            "=" * 60,
            "",
            "## 基础指标",
            f"- 总章节数: {final['chapter']}",
            f"- 总字数: {final['chapter'] * CONFIG['words_per_chapter']:,}",
            "",
            "## state.json 增长",
            f"- 初始大小: {first['file_size_kb']:.2f} KB",
            f"- 最终大小: {final['file_size_kb']:.2f} KB",
            f"- 增长倍数: {final['file_size_kb'] / max(first['file_size_kb'], 0.1):.1f}x",
            "",
            "## 实体统计",
            f"- 总实体数: {final['total_entities']}",
        ]

        for etype, count in final['entity_counts'].items():
            lines.append(f"  - {etype}: {count}")

        lines.extend([
            f"- 别名索引条目: {final['alias_count']}",
            "",
            "## 伏笔统计",
            f"- 活跃伏笔: {final['active_foreshadow']}",
            f"- 已回收伏笔: {final['resolved_foreshadow']}",
            f"- 回收率: {final['resolved_foreshadow'] / max(final['active_foreshadow'] + final['resolved_foreshadow'], 1) * 100:.1f}%",
            "",
            "## 性能指标",
            f"- 平均写入时间: {sum(self.write_times) / max(len(self.write_times), 1) * 1000:.2f} ms",
            f"- 最大写入时间: {max(self.write_times) * 1000:.2f} ms" if self.write_times else "N/A",
            f"- 最小写入时间: {min(self.write_times) * 1000:.2f} ms" if self.write_times else "N/A",
            "",
            "## 错误统计",
            f"- 错误数: {len(self.errors)}",
        ])

        if self.errors:
            lines.append("- 错误详情:")
            for err in self.errors[:5]:
                lines.append(f"  - {err}")

        # 增长曲线（每100章采样）
        lines.extend([
            "",
            "## 增长曲线（每100章）",
            "| 章节 | 文件大小(KB) | 实体数 | 别名数 | 活跃伏笔 | 写入时间(ms) |",
            "|------|-------------|-------|-------|---------|-------------|",
        ])

        for cp in self.checkpoints:
            if cp['chapter'] % 100 == 0 or cp['chapter'] == final['chapter']:
                lines.append(
                    f"| {cp['chapter']} | {cp['file_size_kb']:.1f} | "
                    f"{cp['total_entities']} | {cp['alias_count']} | "
                    f"{cp['active_foreshadow']} | {cp['avg_write_time_ms']:.1f} |"
                )

        # 稳定性评估
        lines.extend([
            "",
            "## 稳定性评估",
        ])

        # 检查文件大小是否在合理范围
        if final['file_size_kb'] < 500:
            lines.append("✅ 文件大小合理 (< 500KB)")
        elif final['file_size_kb'] < 1024:
            lines.append("⚠️ 文件大小偏大 (500KB-1MB)，建议启用归档")
        else:
            lines.append("❌ 文件过大 (> 1MB)，需要优化")

        # 检查写入性能
        avg_write = sum(self.write_times) / max(len(self.write_times), 1) * 1000
        if avg_write < 50:
            lines.append("✅ 写入性能良好 (< 50ms)")
        elif avg_write < 200:
            lines.append("⚠️ 写入性能一般 (50-200ms)")
        else:
            lines.append("❌ 写入性能差 (> 200ms)")

        # 检查错误率
        if not self.errors:
            lines.append("✅ 无错误")
        else:
            lines.append(f"❌ 有 {len(self.errors)} 个错误")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)


class ChapterSimulator:
    """章节模拟器"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.state_file = project_root / ".webnovel" / "state.json"
        self.metrics = SimulationMetrics()
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

    def _generate_location_name(self) -> str:
        return random.choice(LOCATION_PREFIX) + random.choice(LOCATION_SUFFIX)

    def _get_character_rate(self, chapter: int) -> float:
        """根据章节获取角色生成概率（递减）"""
        decay_periods = chapter // 50
        rate = CONFIG["new_character_base_rate"] * (CONFIG["new_character_decay"] ** decay_periods)
        return max(rate, 0.1)  # 最低 10%

    def init_project(self):
        """初始化模拟项目"""
        self.project_root.mkdir(parents=True, exist_ok=True)
        (self.project_root / ".webnovel").mkdir(exist_ok=True)
        (self.project_root / "正文").mkdir(exist_ok=True)

        # 初始 state.json
        initial_state = {
            "project_info": {
                "title": "模拟测试小说",
                "genre": "玄幻",
                "created_at": datetime.now().strftime("%Y-%m-%d"),
                "target_chapters": 500,
            },
            "progress": {
                "current_chapter": 0,
                "total_words": 0,
            },
            "protagonist_state": {
                "name": "林天",
                "realm": "练气",
                "layer": 1,
                "golden_finger": {"name": "混沌珠", "level": 1},
            },
            "entities_v3": {
                "角色": {},
                "地点": {},
                "物品": {},
                "势力": {},
                "招式": {},
            },
            "alias_index": {},
            "foreshadowing": [],
            "relationships": [],
        }

        # 添加主角到实体
        protagonist_id = "protagonist_lintian"
        initial_state["entities_v3"]["角色"][protagonist_id] = {
            "canonical_name": "林天",
            "desc": "主角，拥有混沌珠",
            "tier": "核心",
            "aliases": ["林天", "天哥", "林少侠"],
            "current": {"realm": "练气", "layer": 1},
            "history": [],
        }
        initial_state["alias_index"]["林天"] = [{"type": "角色", "id": protagonist_id}]
        initial_state["alias_index"]["天哥"] = [{"type": "角色", "id": protagonist_id}]

        atomic_write_json(self.state_file, initial_state, backup=False)
        return initial_state

    def simulate_chapter(self, chapter: int, state: Dict) -> Dict:
        """模拟一章的数据变化"""

        # 1. 更新进度
        state["progress"]["current_chapter"] = chapter
        state["progress"]["total_words"] += CONFIG["words_per_chapter"]

        entities_v3 = state["entities_v3"]
        alias_index = state["alias_index"]

        # 2. 新增角色（概率递减）
        if random.random() < self._get_character_rate(chapter):
            char_name = self._generate_character_name()
            char_id = self._generate_id("char")
            tier = random.choices(
                ["核心", "支线", "装饰"],
                weights=[0.1, 0.3, 0.6]
            )[0]

            entities_v3["角色"][char_id] = {
                "canonical_name": char_name,
                "desc": f"第{chapter}章出场的{tier}角色",
                "tier": tier,
                "aliases": [char_name],
                "current": {"first_appearance": chapter},
                "history": [],
            }
            alias_index[char_name] = [{"type": "角色", "id": char_id}]

            # 生成额外别名
            if random.random() < 0.5:
                alias = char_name[0] + "兄" if random.random() < 0.5 else char_name + "前辈"
                entities_v3["角色"][char_id]["aliases"].append(alias)
                if alias not in alias_index:
                    alias_index[alias] = []
                alias_index[alias].append({"type": "角色", "id": char_id})

        # 3. 新增地点
        if random.random() < CONFIG["new_location_rate"]:
            loc_name = self._generate_location_name()
            loc_id = self._generate_id("loc")
            entities_v3["地点"][loc_id] = {
                "canonical_name": loc_name,
                "desc": f"第{chapter}章出现的地点",
                "tier": "装饰",
                "aliases": [loc_name],
                "current": {},
                "history": [],
            }
            alias_index[loc_name] = [{"type": "地点", "id": loc_id}]

        # 4. 新增物品
        if random.random() < CONFIG["new_item_rate"]:
            item_name = random.choice(["灵", "仙", "神", "圣"]) + random.choice(["剑", "丹", "符", "器"])
            item_id = self._generate_id("item")
            entities_v3["物品"][item_id] = {
                "canonical_name": item_name,
                "desc": f"第{chapter}章获得的物品",
                "tier": "装饰",
                "aliases": [item_name],
                "current": {},
                "history": [],
            }
            if item_name not in alias_index:
                alias_index[item_name] = []
            alias_index[item_name].append({"type": "物品", "id": item_id})

        # 5. 埋设伏笔
        if random.random() < CONFIG["foreshadow_plant_rate"]:
            tier = random.choices(
                CONFIG["foreshadow_tiers"],
                weights=CONFIG["foreshadow_tier_weights"]
            )[0]
            target = chapter + random.randint(10, 100)

            state["foreshadowing"].append({
                "id": f"fs_{chapter}_{random.randint(1000, 9999)}",
                "content": f"第{chapter}章埋设的{tier}伏笔",
                "tier": tier,
                "status": "未回收",
                "planted_chapter": chapter,
                "target_chapter": target,
            })

        # 6. 回收伏笔
        active_foreshadows = [
            f for f in state["foreshadowing"]
            if f.get("status") == "未回收" and f.get("target_chapter", 999) <= chapter
        ]
        for fs in active_foreshadows:
            if random.random() < CONFIG["foreshadow_resolve_rate"]:
                fs["status"] = "已回收"
                fs["resolved_chapter"] = chapter

        # 7. 主角升级
        if chapter % CONFIG["protagonist_upgrade_interval"] == 0:
            ps = state["protagonist_state"]
            current_layer = ps.get("layer", 1)
            current_realm_idx = CONFIG["realms"].index(ps.get("realm", "练气"))

            if current_layer < CONFIG["layers_per_realm"]:
                ps["layer"] = current_layer + 1
            elif current_realm_idx < len(CONFIG["realms"]) - 1:
                ps["realm"] = CONFIG["realms"][current_realm_idx + 1]
                ps["layer"] = 1

        # 8. 更新关系
        if chapter % CONFIG["relationship_update_interval"] == 0:
            char_ids = list(entities_v3["角色"].keys())
            if len(char_ids) >= 2:
                char1, char2 = random.sample(char_ids, 2)
                rel_type = random.choice(CONFIG["relationship_types"])

                state["relationships"].append({
                    "char1_id": char1,
                    "char2_id": char2,
                    "type": rel_type,
                    "intensity": random.randint(30, 100),
                    "established_chapter": chapter,
                })

        return state

    def run_simulation(self, checkpoint_interval: int = 10):
        """运行完整模拟"""
        print("🚀 开始500章沙盘模拟...")
        print(f"📁 测试目录: {self.project_root}")
        print()

        state = self.init_project()
        self.metrics.record_checkpoint(0, state, self.state_file)

        start_time = time.time()

        for chapter in range(1, CONFIG["total_chapters"] + 1):
            try:
                # 模拟章节
                state = self.simulate_chapter(chapter, state)

                # 原子写入
                write_start = time.time()
                atomic_write_json(self.state_file, state, use_lock=True, backup=False)
                write_duration = time.time() - write_start
                self.metrics.record_write_time(write_duration)

                # 记录检查点
                if chapter % checkpoint_interval == 0:
                    self.metrics.record_checkpoint(chapter, state, self.state_file)
                    elapsed = time.time() - start_time
                    eta = elapsed / chapter * (CONFIG["total_chapters"] - chapter)
                    print(f"  第 {chapter:3d} 章完成 | "
                          f"文件 {self.state_file.stat().st_size / 1024:.1f}KB | "
                          f"实体 {sum(len(e) for e in state['entities_v3'].values())} | "
                          f"写入 {write_duration*1000:.1f}ms | "
                          f"ETA {eta:.0f}s")

            except Exception as e:
                self.metrics.record_error(f"Chapter {chapter}: {str(e)}")
                print(f"  ❌ 第 {chapter} 章错误: {e}")

        # 最终检查点
        self.metrics.record_checkpoint(CONFIG["total_chapters"], state, self.state_file)

        total_time = time.time() - start_time
        print()
        print(f"✅ 模拟完成！总耗时: {total_time:.1f}s")
        print()

        return self.metrics.generate_report()


def main():
    """主函数"""
    # 创建临时测试目录
    test_dir = Path(tempfile.mkdtemp(prefix="webnovel_stress_test_"))

    try:
        simulator = ChapterSimulator(test_dir)
        report = simulator.run_simulation(checkpoint_interval=10)

        print(report)

        # 保存报告
        report_file = test_dir / "stress_test_report.md"
        report_file.write_text(report, encoding="utf-8")
        print(f"\n📄 报告已保存: {report_file}")

        # 询问是否保留测试数据
        print(f"\n测试数据目录: {test_dir}")
        print("（测试完成后可手动删除）")

    except KeyboardInterrupt:
        print("\n⚠️ 测试被中断")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        raise


if __name__ == "__main__":
    main()
