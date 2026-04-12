# Story System Phase 1 Contract Seed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不破坏现有 `reference_search.py`、`context_manager.py` 与写作主流程的前提下，落地 Story System Phase 1 合同种子层：`题材与调性推理.csv`、最小 `MASTER_SETTING` / `CHAPTER_BRIEF` / `anti_patterns` 持久化，以及 `context_manager` 的合同读取入口。

**Architecture:** 采用“数据层 -> 合同聚合器 -> `.story-system/` 持久化 -> runtime 注入”的四段式。Phase 1 只建立最小合同真源，不引入 `VOLUME_BRIEF`、`REVIEW_CONTRACT`、`CHAPTER_COMMIT`，并继续允许 `genre-profiles.md` 作为回退源存在。

**Tech Stack:** Python 3.13, argparse, pytest, CSV（UTF-8 with BOM）, Markdown + JSON 合同文件, unified CLI `webnovel.py`

**Spec:** `docs/superpowers/specs/2026-04-12-story-system-evolution-spec.md`

**Companion Spec:** `docs/superpowers/specs/2026-04-12-story-system-pro-max-retrofit-spec.md`

---

## Scope Split

这份 plan **只覆盖 evolution spec 的 Phase 1**，原因如下：

- `Phase 2` 以后会引入 `VOLUME_BRIEF`、`REVIEW_CONTRACT`、大纲履约 diff、review blocking rules。
- `Phase 3` 会新增 `CHAPTER_COMMIT` 与四类 projection writers。
- `Phase 4` 会新增 canonical event log。
- `Phase 5` 才能安全降级旧链路。

把这些内容塞进一份实现计划会导致：

- 文件责任边界失真
- TDD 粒度失控
- 文档与代码修改无法形成可验证的阶段产物

因此本计划的退出标准固定为：

1. `PROJECT_ROOT/.story-system/` 能生成最小 `MASTER_SETTING`、`chapter_XXX`、`anti_patterns`
2. `context_manager` 能读取并注入 `story_contract` section
3. 旧 `genre_profile` 仍可作为回退层保留
4. 文档已明确 Phase 1 的路径语义、schema 与使用方式

后续应另写三份计划：

- `Phase 2 Contract-First Runtime`
- `Phase 3 Chapter Commit Chain`
- `Phase 4 Event Log + Override Ledger`

文档边界也在本阶段定死：

- `README.md` 只新增 `Story System` 一级段落与基础目录说明
- 后续 Phase 2/3/4 只能在既有段落下追加，不重写整段结构

---

## File Structure

### 要创建的文件

- `webnovel-writer/references/csv/题材与调性推理.csv`
- `webnovel-writer/scripts/data_modules/story_contracts.py`
- `webnovel-writer/scripts/data_modules/story_system_engine.py`
- `webnovel-writer/scripts/data_modules/tests/test_story_contracts.py`
- `webnovel-writer/scripts/data_modules/tests/test_story_system_engine.py`
- `webnovel-writer/scripts/data_modules/tests/test_story_system_cli.py`
- `webnovel-writer/scripts/story_system.py`
- `docs/architecture/story-system-phase1.md`

### 要修改的文件

- `webnovel-writer/references/csv/README.md`
- `webnovel-writer/references/csv/桥段套路.csv`
- `webnovel-writer/scripts/data_modules/config.py`
- `webnovel-writer/scripts/data_modules/context_manager.py`
- `webnovel-writer/scripts/data_modules/tests/test_context_manager.py`
- `webnovel-writer/scripts/extract_chapter_context.py`
- `webnovel-writer/scripts/data_modules/tests/test_extract_chapter_context.py`
- `webnovel-writer/scripts/data_modules/webnovel.py`
- `webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py`
- `README.md`
- `docs/architecture/overview.md`
- `docs/guides/commands.md`
- `docs/superpowers/README.md`

### 文件职责

- `story_contracts.py`：合同路径、merge 规则、JSON/Markdown 持久化、marker 安全更新
- `story_system_engine.py`：题材路由、多表检索编排、anti-pattern 聚合、最小合同字典构造
- `story_system.py`：CLI 入口，负责 `query -> build -> render -> persist`
- `context_manager.py`：读取 `MASTER_SETTING` / `chapter_XXX` / `anti_patterns` 并注入 `story_contract` section
- `extract_chapter_context.py`：把 `story_contract` 纳入可视化文本/JSON 提取结果
- `docs/architecture/story-system-phase1.md`：Phase 1 合同 schema、目录结构、覆盖规则、迁移说明

---

## Task 1: 建立合同路径层与最小 merge 规则

**Files:**
- Create: `webnovel-writer/scripts/data_modules/story_contracts.py`
- Create: `webnovel-writer/scripts/data_modules/tests/test_story_contracts.py`
- Modify: `webnovel-writer/scripts/data_modules/config.py`

- [ ] **Step 1: 先写 `story_contracts` 的失败测试**

```python
# webnovel-writer/scripts/data_modules/tests/test_story_contracts.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from data_modules.config import DataModulesConfig
from data_modules.story_contracts import StoryContractPaths, merge_contract_layers, merge_anti_patterns


def test_story_contract_paths_live_under_project_root(tmp_path):
    cfg = DataModulesConfig.from_project_root(tmp_path)
    paths = StoryContractPaths.from_project_root(cfg.project_root)

    assert paths.root == tmp_path / ".story-system"
    assert paths.master_json == tmp_path / ".story-system" / "MASTER_SETTING.json"
    assert paths.anti_patterns_json == tmp_path / ".story-system" / "anti_patterns.json"
    assert paths.chapter_json(1) == tmp_path / ".story-system" / "chapters" / "chapter_001.json"


def test_merge_contract_layers_respects_lock_categories():
    master = {
        "locked": {
            "core_tone": "冷硬升级",
            "golden_finger_limit": "每天只能触发一次",
        },
        "append_only": {
            "anti_patterns": ["配角连续抢戏超过 300 字"],
        },
        "override_allowed": {
            "scene_focus": "拍卖会打脸",
        },
    }
    chapter = {
        "locked": {
            "core_tone": "轻喜日常",
        },
        "append_only": {
            "anti_patterns": ["本章禁止解释性旁白"],
        },
        "override_allowed": {
            "scene_focus": "退婚当场反杀",
        },
    }

    merged = merge_contract_layers(master, chapter)

    assert merged["locked"]["core_tone"] == "冷硬升级"
    assert merged["locked"]["golden_finger_limit"] == "每天只能触发一次"
    assert merged["append_only"]["anti_patterns"] == [
        "配角连续抢戏超过 300 字",
        "本章禁止解释性旁白",
    ]
    assert merged["override_allowed"]["scene_focus"] == "退婚当场反杀"


def test_merge_anti_patterns_deduplicates_by_text():
    rows = merge_anti_patterns(
        [{"text": "打脸节奏不能缺补刀", "source_table": "题材与调性推理", "source_id": "GR-001"}],
        [{"text": "打脸节奏不能缺补刀", "source_table": "爽点与节奏", "source_id": "PA-002"}],
    )

    assert [item["text"] for item in rows] == ["打脸节奏不能缺补刀"]
    assert rows[0]["source_table"] == "题材与调性推理"
```

- [ ] **Step 2: 运行测试，确认是正确的红灯**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_story_contracts.py -q --no-cov`

Expected: `ModuleNotFoundError: No module named 'data_modules.story_contracts'`

- [ ] **Step 3: 在 `config.py` 增加 `.story-system` 路径属性**

```python
# webnovel-writer/scripts/data_modules/config.py
@property
def story_system_dir(self) -> Path:
    return self.project_root / ".story-system"

@property
def story_system_chapters_dir(self) -> Path:
    return self.story_system_dir / "chapters"

@property
def story_system_master_json(self) -> Path:
    return self.story_system_dir / "MASTER_SETTING.json"

@property
def story_system_anti_patterns_json(self) -> Path:
    return self.story_system_dir / "anti_patterns.json"
```

- [ ] **Step 4: 实现 `StoryContractPaths`、merge 规则与 marker 更新工具**

```python
# webnovel-writer/scripts/data_modules/story_contracts.py
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List


MARKER_BEGIN = "<!-- STORY-SYSTEM:BEGIN -->"
MARKER_END = "<!-- STORY-SYSTEM:END -->"


@dataclass(frozen=True)
class StoryContractPaths:
    project_root: Path

    @classmethod
    def from_project_root(cls, project_root: str | Path) -> "StoryContractPaths":
        return cls(Path(project_root).expanduser().resolve())

    @property
    def root(self) -> Path:
        return self.project_root / ".story-system"

    @property
    def chapters_dir(self) -> Path:
        return self.root / "chapters"

    @property
    def master_json(self) -> Path:
        return self.root / "MASTER_SETTING.json"

    @property
    def anti_patterns_json(self) -> Path:
        return self.root / "anti_patterns.json"

    def chapter_json(self, chapter: int) -> Path:
        return self.chapters_dir / f"chapter_{chapter:03d}.json"


def merge_contract_layers(master: Dict[str, Any], chapter: Dict[str, Any] | None) -> Dict[str, Any]:
    chapter = chapter or {}
    return {
        "locked": dict(master.get("locked") or {}),
        "append_only": _merge_append_only(master.get("append_only") or {}, chapter.get("append_only") or {}),
        "override_allowed": {
            **(master.get("override_allowed") or {}),
            **(chapter.get("override_allowed") or {}),
        },
    }


def merge_anti_patterns(*groups: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    merged: List[Dict[str, Any]] = []
    for group in groups:
        for row in group:
            text = str(row.get("text") or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            merged.append(dict(row))
    return merged


def read_json_if_exists(path: Path) -> Any | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Bad JSON in {path}") from exc
```

同时补一个统一读取约定，供后续 Phase 2-4 复用：

- `read_json_if_exists(path) -> dict | list | None`
- 文件不存在时返回 `None`
- JSON 格式错误时抛带路径的 `ValueError`
- 本阶段先在 `story_contracts.py` 落这个 helper，后续 projection / runtime builder 不再各写一套吞错逻辑

- [ ] **Step 5: 回跑测试，确认基础层转绿**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_story_contracts.py -q --no-cov`

Expected: 通过

- [ ] **Step 6: 提交**

```bash
git add webnovel-writer/scripts/data_modules/config.py \
        webnovel-writer/scripts/data_modules/story_contracts.py \
        webnovel-writer/scripts/data_modules/tests/test_story_contracts.py
git commit -m "feat: add story contract path helpers and merge rules"
```

---

## Task 2: 落地题材路由表与合同聚合器

**Files:**
- Create: `webnovel-writer/references/csv/题材与调性推理.csv`
- Create: `webnovel-writer/scripts/data_modules/story_system_engine.py`
- Create: `webnovel-writer/scripts/data_modules/tests/test_story_system_engine.py`
- Modify: `webnovel-writer/references/csv/README.md`
- Modify: `webnovel-writer/references/csv/桥段套路.csv`

- [ ] **Step 1: 先写 `story_system_engine` 的失败测试**

```python
# webnovel-writer/scripts/data_modules/tests/test_story_system_engine.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv

from data_modules.story_system_engine import StorySystemEngine


def _write_csv(path, headers, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def test_story_system_routes_explicit_genre_and_collects_anti_patterns(tmp_path):
    csv_dir = tmp_path / "csv"
    csv_dir.mkdir()

    _write_csv(
        csv_dir / "题材与调性推理.csv",
        [
            "编号", "适用技能", "分类", "层级", "关键词", "意图与同义词", "适用题材",
            "大模型指令", "核心摘要", "详细展开", "题材/流派", "题材别名", "核心调性",
            "节奏策略", "强制禁忌/毒点", "推荐基础检索表", "推荐动态检索表", "默认查询词",
        ],
        [
            {
                "编号": "GR-001",
                "适用技能": "write|plan",
                "分类": "题材路由",
                "层级": "知识补充",
                "关键词": "玄幻退婚流|退婚打脸",
                "意图与同义词": "退婚流|废材逆袭",
                "适用题材": "玄幻",
                "大模型指令": "先给压抑，再给爆发兑现。",
                "核心摘要": "玄幻退婚流需要耻辱起手和强兑现。",
                "详细展开": "",
                "题材/流派": "玄幻退婚流",
                "题材别名": "退婚流|废材逆袭",
                "核心调性": "压抑蓄势后爆裂反击",
                "节奏策略": "前压后爆，三章内必须首个反打",
                "强制禁忌/毒点": "打脸节奏不能缺最后一拍补刀|配角不能压过主角兑现",
                "推荐基础检索表": "命名规则|人设与关系|金手指与设定",
                "推荐动态检索表": "桥段套路|爽点与节奏|场景写法",
                "默认查询词": "退婚|打脸|废材逆袭",
            }
        ],
    )

    _write_csv(
        csv_dir / "桥段套路.csv",
        ["编号", "适用技能", "分类", "层级", "关键词", "适用题材", "核心摘要", "桥段名称", "忌讳写法"],
        [
            {
                "编号": "TR-001",
                "适用技能": "write",
                "分类": "桥段",
                "层级": "知识补充",
                "关键词": "退婚|打脸",
                "适用题材": "玄幻",
                "核心摘要": "退婚现场要给足羞辱和反击空间",
                "桥段名称": "退婚反击",
                "忌讳写法": "主角还没反打就被配角替他出手",
            }
        ],
    )

    _write_csv(
        csv_dir / "爽点与节奏.csv",
        ["编号", "适用技能", "分类", "层级", "关键词", "适用题材", "核心摘要", "常见崩盘误区", "节奏类型"],
        [
            {
                "编号": "PA-001",
                "适用技能": "write",
                "分类": "节奏",
                "层级": "知识补充",
                "关键词": "打脸|兑现",
                "适用题材": "玄幻",
                "核心摘要": "兑现必须补刀",
                "常见崩盘误区": "打脸收尾太软，没有读者情绪补刀",
                "节奏类型": "爆发期",
            }
        ],
    )

    engine = StorySystemEngine(csv_dir=csv_dir)
    contract = engine.build(query="玄幻退婚流", genre=None, chapter=None)

    assert contract["master_setting"]["route"]["primary_genre"] == "玄幻退婚流"
    assert contract["master_setting"]["master_constraints"]["core_tone"] == "压抑蓄势后爆裂反击"
    assert "命名规则" in contract["master_setting"]["route"]["recommended_base_tables"]
    assert {
        item["text"] for item in contract["anti_patterns"]
    } >= {
        "打脸节奏不能缺最后一拍补刀",
        "主角还没反打就被配角替他出手",
        "打脸收尾太软，没有读者情绪补刀",
    }


def test_story_system_falls_back_to_explicit_genre(tmp_path):
    csv_dir = tmp_path / "csv"
    csv_dir.mkdir()

    _write_csv(
        csv_dir / "题材与调性推理.csv",
        [
            "编号", "适用技能", "分类", "层级", "关键词", "意图与同义词", "适用题材",
            "大模型指令", "核心摘要", "详细展开", "题材/流派", "题材别名", "核心调性",
            "节奏策略", "强制禁忌/毒点", "推荐基础检索表", "推荐动态检索表", "默认查询词",
        ],
        [],
    )

    engine = StorySystemEngine(csv_dir=csv_dir)
    contract = engine.build(query="压抑一点，后面爆", genre="现言", chapter=None)

    assert contract["master_setting"]["route"]["primary_genre"] == "现言"
    assert contract["master_setting"]["route"]["route_source"] == "explicit_genre_fallback"
    assert contract["master_setting"]["route"]["recommended_dynamic_tables"] == ["桥段套路", "爽点与节奏", "场景写法"]
```

- [ ] **Step 2: 跑红灯，确认缺的是聚合器而不是测试本身**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_story_system_engine.py -q --no-cov`

Expected: `ModuleNotFoundError: No module named 'data_modules.story_system_engine'`

- [ ] **Step 3: 实现 `StorySystemEngine` 与 anti-pattern 归一化映射**

```python
# webnovel-writer/scripts/data_modules/story_system_engine.py
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional

from reference_search import search as search_reference

from .story_contracts import merge_anti_patterns


ANTI_PATTERN_SOURCE_FIELDS = {
    "场景写法": ["反面写法"],
    "写作技法": ["常见误区"],
    "爽点与节奏": ["常见崩盘误区"],
    "人设与关系": ["忌讳写法"],
    "桥段套路": ["忌讳写法"],
    "题材与调性推理": ["强制禁忌/毒点"],
}


class StorySystemEngine:
    def __init__(self, csv_dir: str | Path):
        self.csv_dir = Path(csv_dir)

    def build(self, query: str, genre: Optional[str], chapter: Optional[int]) -> Dict[str, Any]:
        route = self._route(query=query, genre=genre)
        base_context = self._collect_tables(query, route["recommended_base_tables"], genre=route["genre_filter"], top_k=1)
        dynamic_context = self._collect_tables(query, route["recommended_dynamic_tables"], genre=route["genre_filter"], top_k=2)
        source_trace = route["source_trace"] + self._build_source_trace(base_context, dynamic_context)
        anti_patterns = merge_anti_patterns(
            route["route_anti_patterns"],
            self._extract_anti_patterns(base_context),
            self._extract_anti_patterns(dynamic_context),
        )
        return {
            "meta": {"query": query, "chapter": chapter, "explicit_genre": genre or ""},
            "master_setting": {
                "meta": {
                    "schema_version": "story-system/v1",
                    "contract_type": "MASTER_SETTING",
                    "generator_version": "phase1",
                    "query": query,
                },
                "route": route["meta"],
                "master_constraints": {
                    "core_tone": route["core_tone"],
                    "pacing_strategy": route["pacing_strategy"],
                },
                "base_context": base_context,
                "source_trace": source_trace,
                "override_policy": {
                    "locked": ["route.primary_genre", "master_constraints.core_tone"],
                    "append_only": ["anti_patterns"],
                    "override_allowed": [],
                },
            },
            "chapter_brief": (
                {
                    "meta": {
                        "schema_version": "story-system/v1",
                        "contract_type": "CHAPTER_BRIEF",
                        "generator_version": "phase1",
                        "chapter": chapter,
                    },
                    "override_allowed": {
                        "chapter_focus": self._suggest_chapter_focus(query, dynamic_context),
                    },
                    "dynamic_context": dynamic_context,
                    "source_trace": source_trace,
                }
                if chapter is not None
                else None
            ),
            "anti_patterns": anti_patterns,
        }

    def _route(self, query: str, genre: Optional[str]) -> Dict[str, Any]:
        route_rows = self._load_csv_rows("题材与调性推理")
        query_text = self._normalize_text(" ".join([query or "", genre or ""]))

        # 命中顺序固定：关键词/同义词命中 -> 显式 genre 回退 -> 默认首行回退
        matched = None
        for row in route_rows:
            aliases = self._split_multi_value(row.get("关键词")) + self._split_multi_value(row.get("意图与同义词")) + self._split_multi_value(row.get("题材别名"))
            if any(alias and alias in query_text for alias in aliases):
                matched = row
                route_source = "keyword_or_alias_match"
                break
        if matched is None and genre:
            matched = self._fallback_row_for_genre(route_rows, genre)
            route_source = "explicit_genre_fallback"
        if matched is None and route_rows:
            matched = route_rows[0]
            route_source = "default_seed_fallback"
        if matched is None:
            return self._empty_route(query=query, genre=genre)

        primary_genre = str(matched.get("题材/流派") or genre or "").strip()
        genre_filter = str(matched.get("适用题材") or genre or primary_genre).strip()
        return {
            "meta": {
                "primary_genre": primary_genre,
                "route_source": route_source,
                "genre_filter": genre_filter,
                "recommended_base_tables": self._split_multi_value(matched.get("推荐基础检索表")),
                "recommended_dynamic_tables": self._split_multi_value(matched.get("推荐动态检索表")),
            },
            "core_tone": str(matched.get("核心调性") or "").strip(),
            "pacing_strategy": str(matched.get("节奏策略") or "").strip(),
            "route_anti_patterns": self._extract_route_anti_patterns(matched),
            "recommended_base_tables": self._split_multi_value(matched.get("推荐基础检索表")),
            "recommended_dynamic_tables": self._split_multi_value(matched.get("推荐动态检索表")),
            "genre_filter": genre_filter,
            "source_trace": [{"table": "题材与调性推理", "id": matched.get("编号", ""), "reason": route_source}],
        }

    def _collect_tables(self, query: str, tables: List[str], genre: str, top_k: int) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for table_name in tables:
            result = search_reference(
                csv_dir=self.csv_dir,
                skill="write",
                query=query,
                table=table_name,
                genre=genre,
                max_results=top_k,
            )
            rows.extend(result.get("data", {}).get("results", []))
        return rows

    def _extract_anti_patterns(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        extracted: List[Dict[str, Any]] = []
        for row in rows:
            table_name = str(row.get("_table") or "")
            for field_name in ANTI_PATTERN_SOURCE_FIELDS.get(table_name, []):
                for text in self._split_multi_value(row.get(field_name)):
                    extracted.append({"text": text, "source_table": table_name, "source_id": row.get("编号", "")})
        return extracted

    def _suggest_chapter_focus(self, query: str, dynamic_rows: List[Dict[str, Any]]) -> str:
        for row in dynamic_rows:
            summary = str(row.get("核心摘要") or "").strip()
            if summary:
                return summary
        return query

    def _build_source_trace(self, *groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        trace: List[Dict[str, Any]] = []
        for group in groups:
            for row in group:
                trace.append(
                    {
                        "table": row.get("_table", ""),
                        "id": row.get("编号", ""),
                        "summary": row.get("核心摘要", ""),
                    }
                )
        return trace

    def _load_csv_rows(self, table_name: str) -> List[Dict[str, Any]]:
        csv_path = self.csv_dir / f"{table_name}.csv"
        if not csv_path.is_file():
            return []
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))

    def _normalize_text(self, text: str) -> str:
        return str(text or "").strip().lower()

    def _split_multi_value(self, raw: Any) -> List[str]:
        return [item.strip() for item in str(raw or "").split("|") if item.strip()]

    def _fallback_row_for_genre(self, rows: List[Dict[str, Any]], genre: str) -> Dict[str, Any] | None:
        genre = str(genre or "").strip()
        for row in rows:
            if genre and genre in self._split_multi_value(row.get("适用题材")):
                return row
        return None

    def _extract_route_anti_patterns(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            {"text": text, "source_table": "题材与调性推理", "source_id": row.get("编号", "")}
            for text in self._split_multi_value(row.get("强制禁忌/毒点"))
        ]

    def _empty_route(self, query: str, genre: Optional[str]) -> Dict[str, Any]:
        fallback_genre = str(genre or "未命中题材").strip()
        return {
            "meta": {
                "primary_genre": fallback_genre,
                "route_source": "empty_csv_fallback",
                "genre_filter": fallback_genre,
                "recommended_base_tables": ["命名规则", "人设与关系"],
                "recommended_dynamic_tables": ["桥段套路", "爽点与节奏", "场景写法"],
            },
            "core_tone": "",
            "pacing_strategy": "",
            "route_anti_patterns": [],
            "recommended_base_tables": ["命名规则", "人设与关系"],
            "recommended_dynamic_tables": ["桥段套路", "爽点与节奏", "场景写法"],
            "genre_filter": fallback_genre,
            "source_trace": [{"table": "题材与调性推理", "id": "", "reason": f"empty_route_for:{query}"}],
        }
```

这里显式约束测试策略：

- 直接使用 `tmp_path / csv` 喂给 `reference_search.search()`
- 不需要 monkeypatch 搜索函数
- 如果后续 `reference_search.search()` 签名变化，优先同步这里的聚合器封装，不在测试层绕过真实接口

- [ ] **Step 4: 落地真实 CSV 数据和字段文档**

`题材与调性推理.csv` 至少先录入 3 条手工种子数据，覆盖：

```csv
编号,适用技能,分类,层级,关键词,意图与同义词,适用题材,大模型指令,核心摘要,详细展开,题材/流派,题材别名,核心调性,节奏策略,主冲突模板,必选爽点,强制禁忌/毒点,推荐基础检索表,推荐动态检索表,基础检索权重,动态检索权重,默认查询词
GR-001,write|plan,题材路由,知识补充,玄幻退婚流|退婚打脸,退婚流|废材逆袭,玄幻,先压后爆，首个反打必须有羞辱反弹,玄幻退婚流需要耻辱起手和强兑现,,玄幻退婚流,退婚流|废材逆袭,压抑蓄势后爆裂反击,前压后爆，三章内必须首个反打,退婚羞辱→资源争夺→当场反杀,当众反打|身份翻盘,打脸节奏不能缺最后一拍补刀|配角不能压过主角兑现,命名规则|人设与关系|金手指与设定,桥段套路|爽点与节奏|场景写法,命名规则:1.0|人设与关系:0.9,桥段套路:1.0|爽点与节奏:0.9,退婚|打脸|废材逆袭
GR-002,write|plan,题材路由,知识补充,规则动物园|怪谈副本,规则怪谈|动物园规则,悬疑|轻小说,规则先立死，代价必须兑现,规则动物园重在规则压迫与试错代价,,规则动物园,规则怪谈|动物园规则,诡异压迫与冷感观察,每章至少一个规则验证或误判后果,入园规则→试错牺牲→发现隐藏规则,规则反转|错误成本兑现,规则解释过量|系统提前剧透真相,命名规则|人设与关系,桥段套路|场景写法|写作技法,命名规则:0.7|人设与关系:0.8,场景写法:1.0|写作技法:0.9,规则|动物园|副本
GR-003,write|plan,题材路由,知识补充,压抑后爆|后期翻盘,压抑一点后面爆|前面憋屈后面翻盘,现言|都市,压抑不能空耗，必须绑定后续兑现资产,压抑后爆路线需要持续累积反弹势能,,压抑后爆,前憋后爆|后期翻盘,持续压迫后的集中爆发,每 2-3 章必须补一个可见反抗信号,压迫累积→误判反扑→情绪总兑现,情绪爆点|身份反转,压抑没有收益|委屈全靠旁白硬说,命名规则|人设与关系|写作技法,爽点与节奏|场景写法|桥段套路,写作技法:0.9|人设与关系:0.8,爽点与节奏:1.0|场景写法:0.8,压抑|翻盘|反弹
```

同时给 `桥段套路.csv` 增加 `忌讳写法` 列，并在 `references/csv/README.md` 新增：

```markdown
### 题材与调性推理.csv

| 列名 | 说明 |
|------|------|
| `题材/流派` | 路由主标签 |
| `题材别名` | 同义词 / 平台黑话 |
| `核心调性` | 全局情绪基调 |
| `节奏策略` | 开局与兑现节奏 |
| `强制禁忌/毒点` | 题材级绝对红线 |
| `推荐基础检索表` | 默认基础检索表 |
| `推荐动态检索表` | 默认动态检索表 |
```

- [ ] **Step 5: 回跑测试，确认路由 + 聚合契约转绿**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_story_system_engine.py -q --no-cov`

Expected: 通过

- [ ] **Step 6: 提交**

```bash
git add webnovel-writer/references/csv/题材与调性推理.csv \
        webnovel-writer/references/csv/桥段套路.csv \
        webnovel-writer/references/csv/README.md \
        webnovel-writer/scripts/data_modules/story_system_engine.py \
        webnovel-writer/scripts/data_modules/tests/test_story_system_engine.py
git commit -m "feat: add genre routing csv and story system engine"
```

---

## Task 3: 实现 `.story-system` 持久化与统一 CLI 接入

**Files:**
- Create: `webnovel-writer/scripts/story_system.py`
- Create: `webnovel-writer/scripts/data_modules/tests/test_story_system_cli.py`
- Modify: `webnovel-writer/scripts/data_modules/story_contracts.py`
- Modify: `webnovel-writer/scripts/data_modules/webnovel.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py`

- [ ] **Step 1: 先写 `--persist` 和统一 CLI 转发的失败测试**

```python
# webnovel-writer/scripts/data_modules/tests/test_story_system_cli.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import json
import sys


def _write_csv(path, headers, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def test_story_system_persist_writes_master_chapter_and_anti_patterns(tmp_path, monkeypatch):
    project_root = tmp_path / "book"
    (project_root / ".webnovel").mkdir(parents=True, exist_ok=True)
    (project_root / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")

    csv_dir = tmp_path / "csv"
    csv_dir.mkdir()
    _write_csv(
        csv_dir / "题材与调性推理.csv",
        [
            "编号", "适用技能", "分类", "层级", "关键词", "意图与同义词", "适用题材",
            "大模型指令", "核心摘要", "详细展开", "题材/流派", "题材别名", "核心调性",
            "节奏策略", "强制禁忌/毒点", "推荐基础检索表", "推荐动态检索表", "默认查询词",
        ],
        [
            {
                "编号": "GR-001",
                "适用技能": "write",
                "分类": "题材路由",
                "层级": "知识补充",
                "关键词": "玄幻退婚流",
                "意图与同义词": "退婚流",
                "适用题材": "玄幻",
                "大模型指令": "先压后爆",
                "核心摘要": "退婚起手",
                "详细展开": "",
                "题材/流派": "玄幻退婚流",
                "题材别名": "退婚流",
                "核心调性": "先压后爆",
                "节奏策略": "三章内反打",
                "强制禁忌/毒点": "打脸不能软收尾",
                "推荐基础检索表": "命名规则",
                "推荐动态检索表": "桥段套路",
                "默认查询词": "退婚|打脸",
            }
        ],
    )
    _write_csv(csv_dir / "命名规则.csv", ["编号", "适用技能", "分类", "层级", "关键词", "适用题材", "核心摘要"], [])
    _write_csv(csv_dir / "桥段套路.csv", ["编号", "适用技能", "分类", "层级", "关键词", "适用题材", "核心摘要", "忌讳写法"], [])

    from story_system import main

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "story_system",
            "玄幻退婚流",
            "--project-root",
            str(project_root),
            "--chapter",
            "1",
            "--persist",
            "--csv-dir",
            str(csv_dir),
            "--format",
            "both",
        ],
    )
    main()

    story_root = project_root / ".story-system"
    assert (story_root / "MASTER_SETTING.json").is_file()
    assert (story_root / "MASTER_SETTING.md").is_file()
    assert (story_root / "anti_patterns.json").is_file()
    assert (story_root / "chapters" / "chapter_001.json").is_file()
    assert (story_root / "chapters" / "chapter_001.md").is_file()

    payload = json.loads((story_root / "MASTER_SETTING.json").read_text(encoding="utf-8"))
    assert payload["route"]["primary_genre"] == "玄幻退婚流"


def test_markdown_writer_preserves_manual_notes_outside_markers(tmp_path):
    from data_modules.story_contracts import write_marked_markdown

    target = tmp_path / "MASTER_SETTING.md"
    target.write_text(
        "# 手工说明\n手工备注\n<!-- STORY-SYSTEM:BEGIN -->\n旧内容\n<!-- STORY-SYSTEM:END -->\n",
        encoding="utf-8",
    )

    write_marked_markdown(target, "## Auto\n新内容\n")

    text = target.read_text(encoding="utf-8")
    assert "# 手工说明" in text
    assert "手工备注" in text
    assert "## Auto" in text
    assert "旧内容" not in text
```

在 `test_webnovel_unified_cli.py` 增加：

```python
def test_webnovel_story_system_forwards_with_resolved_project_root(monkeypatch, tmp_path):
    from data_modules import webnovel as cli

    project_root = tmp_path / "book"
    (project_root / ".webnovel").mkdir(parents=True, exist_ok=True)
    (project_root / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")

    called = {}

    def _fake_run_script(script_name, argv):
        called["script_name"] = script_name
        called["argv"] = argv
        return 0

    monkeypatch.setattr(cli, "_run_script", _fake_run_script)
    monkeypatch.setattr(sys, "argv", ["webnovel", "--project-root", str(project_root), "story-system", "玄幻退婚流"])

    cli.main()

    assert called["script_name"] == "story_system.py"
    assert called["argv"][:2] == ["--project-root", str(project_root.resolve())]
```

- [ ] **Step 2: 跑红灯**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_story_system_cli.py webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py -q --no-cov`

Expected: 失败于 `No module named 'story_system'` 或 `write_marked_markdown` 未实现

- [ ] **Step 3: 实现持久化写入器与 `story_system.py` CLI**

在 `story_contracts.py` 增补持久化函数。这里明确一个边界：**每个 `.md` 文件只允许一组 `<!-- STORY-SYSTEM:BEGIN/END -->` marker**；如果检测到多组 marker，直接抛 `ValueError`，避免 Phase 2 以后出现局部覆盖残留。

```python
def write_marked_markdown(path: Path, generated_block: str) -> None:
    wrapped = f"{MARKER_BEGIN}\n{generated_block.rstrip()}\n{MARKER_END}\n"
    if path.exists():
        current = path.read_text(encoding="utf-8")
        if current.count(MARKER_BEGIN) > 1 or current.count(MARKER_END) > 1:
            raise ValueError(f"{path} contains multiple STORY-SYSTEM markers")
        if MARKER_BEGIN in current and MARKER_END in current:
            before, _, rest = current.partition(MARKER_BEGIN)
            _, _, after = rest.partition(MARKER_END)
            path.write_text(f"{before}{wrapped}{after.lstrip()}", encoding="utf-8")
            return
    path.write_text(wrapped, encoding="utf-8")


def render_master_markdown(master_payload: dict) -> str:
    route = master_payload.get("route") or {}
    constraints = master_payload.get("master_constraints") or {}
    return "\n".join(
        [
            "# MASTER_SETTING",
            f"- 题材：{route.get('primary_genre', '')}",
            f"- 调性：{constraints.get('core_tone', '')}",
            f"- 节奏：{constraints.get('pacing_strategy', '')}",
        ]
    )


def render_anti_patterns_markdown(anti_patterns: list[dict]) -> str:
    lines = ["# ANTI_PATTERNS"]
    for row in anti_patterns:
        lines.append(f"- {row.get('text', '')}")
    return "\n".join(lines)


def render_chapter_markdown(chapter_payload: dict) -> str:
    focus = (chapter_payload.get("override_allowed") or {}).get("chapter_focus", "")
    return "\n".join(
        [
            f"# CHAPTER_{int(chapter_payload['meta']['chapter']):03d}",
            f"- 章节焦点：{focus}",
        ]
    )


def persist_story_seed(project_root: Path, master_payload: dict, chapter_payload: dict | None, anti_patterns: list[dict]) -> None:
    paths = StoryContractPaths.from_project_root(project_root)
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.chapters_dir.mkdir(parents=True, exist_ok=True)
    write_json(paths.master_json, master_payload)
    write_json(paths.anti_patterns_json, anti_patterns)
    write_marked_markdown(paths.master_json.with_suffix(".md"), render_master_markdown(master_payload))
    write_marked_markdown(paths.anti_patterns_json.with_suffix(".md"), render_anti_patterns_markdown(anti_patterns))
    if chapter_payload is not None:
        chapter_num = int(chapter_payload["meta"]["chapter"])
        write_json(paths.chapter_json(chapter_num), chapter_payload)
        write_marked_markdown(paths.chapter_json(chapter_num).with_suffix(".md"), render_chapter_markdown(chapter_payload))
```

新增 CLI 入口：

```python
# webnovel-writer/scripts/story_system.py
def main() -> None:
    parser = argparse.ArgumentParser(description="Story System 聚合器")
    parser.add_argument("query", help="题材描述或当前意图")
    parser.add_argument("--project-root", help="书项目根目录或工作区根目录")
    parser.add_argument("--genre", default="", help="显式题材")
    parser.add_argument("--chapter", type=int, default=0, help="章节号")
    parser.add_argument("--persist", action="store_true", help="写入 PROJECT_ROOT/.story-system/")
    parser.add_argument("--format", choices=["json", "markdown", "both"], default="json")
    parser.add_argument("--csv-dir", default="", help="测试时覆写 CSV 目录")
    args = parser.parse_args()

    project_root = resolve_project_root(args.project_root) if args.project_root else resolve_project_root()
    csv_dir = Path(args.csv_dir) if args.csv_dir else Path(__file__).resolve().parent.parent / "references" / "csv"

    engine = StorySystemEngine(csv_dir=csv_dir)
    payload = engine.build(query=args.query, genre=args.genre or None, chapter=args.chapter or None)
    if args.persist:
        persist_story_seed(project_root, payload["master_setting"], payload.get("chapter_brief"), payload["anti_patterns"])
```

- [ ] **Step 4: 在统一 CLI `webnovel.py` 中挂接 `story-system`**

```python
# webnovel-writer/scripts/data_modules/webnovel.py
p_story_system = sub.add_parser("story-system", help="转发到 story_system.py")
p_story_system.add_argument("args", nargs=argparse.REMAINDER)

# main() 路由分支
elif args.tool == "story-system":
    forward_args = ["--project-root", str(project_root), *(_strip_project_root_args(args.args))]
    raise SystemExit(_run_script("story_system.py", forward_args))
```

- [ ] **Step 5: 回跑测试，确认持久化与 CLI 契约转绿**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_story_system_cli.py webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py -q --no-cov`

Expected: 通过

- [ ] **Step 6: 提交**

```bash
git add webnovel-writer/scripts/story_system.py \
        webnovel-writer/scripts/data_modules/story_contracts.py \
        webnovel-writer/scripts/data_modules/webnovel.py \
        webnovel-writer/scripts/data_modules/tests/test_story_system_cli.py \
        webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py
git commit -m "feat: persist story system seed contracts and expose unified cli"
```

---

## Task 4: 把合同种子接到 `context_manager` 与 `extract_chapter_context`

**Files:**
- Modify: `webnovel-writer/scripts/data_modules/context_manager.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_context_manager.py`
- Modify: `webnovel-writer/scripts/extract_chapter_context.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_extract_chapter_context.py`

- [ ] **Step 1: 先写合同读取入口的失败测试**

在 `test_context_manager.py` 增加：

```python
def test_context_manager_includes_story_contract_section_before_genre_profile(temp_project):
    state = {
        "genre": "玄幻",
        "protagonist_state": {"name": "萧炎"},
        "chapter_meta": {},
        "disambiguation_warnings": [],
        "disambiguation_pending": [],
    }
    temp_project.state_file.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    story_root = temp_project.project_root / ".story-system"
    (story_root / "chapters").mkdir(parents=True, exist_ok=True)
    (story_root / "MASTER_SETTING.json").write_text(
        json.dumps(
            {
                "meta": {"schema_version": "story-system/v1", "contract_type": "MASTER_SETTING", "query": "玄幻退婚流"},
                "route": {"primary_genre": "玄幻退婚流"},
                "master_constraints": {"core_tone": "先压后爆"},
                "base_context": [],
                "source_trace": [],
                "override_policy": {"locked": ["route.primary_genre"], "append_only": ["anti_patterns"], "override_allowed": []},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (story_root / "anti_patterns.json").write_text(
        json.dumps([{"text": "打脸不能软收尾"}], ensure_ascii=False),
        encoding="utf-8",
    )
    (story_root / "chapters" / "chapter_001.json").write_text(
        json.dumps(
            {
                "meta": {"schema_version": "story-system/v1", "contract_type": "CHAPTER_BRIEF", "chapter": 1},
                "override_allowed": {"chapter_focus": "退婚现场反打"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = ContextManager(temp_project).build_context(1, use_snapshot=False, save_snapshot=False)

    assert "story_contract" in payload["sections"]
    assert payload["sections"]["story_contract"]["content"]["route"]["primary_genre"] == "玄幻退婚流"
    assert payload["sections"]["story_contract"]["content"]["chapter_brief"]["override_allowed"]["chapter_focus"] == "退婚现场反打"
    assert ContextManager.SECTION_ORDER.index("story_contract") < ContextManager.SECTION_ORDER.index("genre_profile")
```

在 `test_extract_chapter_context.py` 增加：

```python
def test_build_chapter_context_payload_includes_story_contract(tmp_path):
    from extract_chapter_context import build_chapter_context_payload

    project_root = tmp_path
    (project_root / ".webnovel").mkdir(parents=True, exist_ok=True)
    (project_root / ".webnovel" / "state.json").write_text(
        json.dumps({"protagonist_state": {}, "chapter_meta": {}}, ensure_ascii=False),
        encoding="utf-8",
    )
    story_root = project_root / ".story-system"
    (story_root / "chapters").mkdir(parents=True, exist_ok=True)
    (story_root / "MASTER_SETTING.json").write_text(
        json.dumps({"route": {"primary_genre": "规则动物园"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (story_root / "anti_patterns.json").write_text(
        json.dumps([{"text": "不要提前解释真相"}], ensure_ascii=False),
        encoding="utf-8",
    )
    (story_root / "chapters" / "chapter_001.json").write_text(
        json.dumps({"override_allowed": {"chapter_focus": "游客须知初次触发"}}, ensure_ascii=False),
        encoding="utf-8",
    )

    payload = build_chapter_context_payload(project_root, 1)

    assert payload["story_contract"]["route"]["primary_genre"] == "规则动物园"
    assert payload["story_contract"]["anti_patterns"][0]["text"] == "不要提前解释真相"
```

- [ ] **Step 2: 跑红灯**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_context_manager.py webnovel-writer/scripts/data_modules/tests/test_extract_chapter_context.py -q --no-cov`

Expected: `story_contract` section / payload 字段不存在

- [ ] **Step 3: 在 `context_manager.py` 增加合同加载与 section 注入**

```python
# webnovel-writer/scripts/data_modules/context_manager.py
SECTION_ORDER = [
    "core",
    "story_contract",
    "scene",
    "global",
    "reader_signal",
    "genre_profile",
    "writing_guidance",
    "plot_structure",
    "story_skeleton",
    "memory",
    "long_term_memory",
    "preferences",
    "alerts",
]

def _load_story_contract(self, chapter: int) -> Dict[str, Any]:
    paths = StoryContractPaths.from_project_root(self.config.project_root)
    master = read_json_if_exists(paths.master_json)
    chapter_payload = read_json_if_exists(paths.chapter_json(chapter))
    anti_patterns = read_json_if_exists(paths.anti_patterns_json) or []
    if not master and not chapter_payload and not anti_patterns:
        return {}
    return {
        "master_setting": master,
        "chapter_brief": chapter_payload,
        "route": (master or {}).get("route", {}),
        "master_constraints": (master or {}).get("master_constraints", {}),
        "anti_patterns": anti_patterns,
    }

# 在 _build_pack() 组装 pack 时插入：
story_contract = self._load_story_contract(chapter)
pack = {
    "meta": {"chapter": chapter},
    "core": core,
    "scene": scene,
    "global": global_ctx,
    "reader_signal": reader_signal,
    "genre_profile": genre_profile,
    "writing_guidance": writing_guidance,
    "plot_structure": plot_structure,
    "story_skeleton": story_skeleton,
    "memory": memory_ctx,
    "long_term_memory": long_term_memory,
    "preferences": preferences,
    "alerts": alerts,
}
if story_contract:
    pack["story_contract"] = story_contract
```

- [ ] **Step 4: 在 `extract_chapter_context.py` 中透出 `story_contract`**

```python
# webnovel-writer/scripts/extract_chapter_context.py
def _load_contract_context(project_root: Path, chapter_num: int) -> Dict[str, Any]:
    manager = ContextManager(get_config(project_root))
    payload = manager.build_context(chapter_num, use_snapshot=False, save_snapshot=False)
    sections = payload.get("sections") or {}
    return {
        "reader_signal": (sections.get("reader_signal") or {}).get("content", {}),
        "genre_profile": (sections.get("genre_profile") or {}).get("content", {}),
        "story_contract": (sections.get("story_contract") or {}).get("content", {}),
        "writing_guidance": (sections.get("writing_guidance") or {}).get("content", {}),
        "plot_structure": (sections.get("plot_structure") or {}).get("content", {}),
        "long_term_memory": (sections.get("long_term_memory") or {}).get("content", {}),
    }
```

文本渲染新增一个紧凑章节：

```python
story_contract = payload.get("story_contract") or {}
if story_contract:
    lines.append("## Story Contract")
    route = story_contract.get("route") or {}
    if route.get("primary_genre"):
        lines.append(f"- 主路由题材: {route['primary_genre']}")
    anti_patterns = story_contract.get("anti_patterns") or []
    for row in anti_patterns[:5]:
        lines.append(f"- 红线: {row.get('text')}")
```

- [ ] **Step 5: 回跑测试**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_context_manager.py webnovel-writer/scripts/data_modules/tests/test_extract_chapter_context.py -q --no-cov`

Expected: 通过

- [ ] **Step 6: 提交**

```bash
git add webnovel-writer/scripts/data_modules/context_manager.py \
        webnovel-writer/scripts/data_modules/tests/test_context_manager.py \
        webnovel-writer/scripts/extract_chapter_context.py \
        webnovel-writer/scripts/data_modules/tests/test_extract_chapter_context.py
git commit -m "feat: load story contract seed into context assembly"
```

---

## Task 5: 更新架构文档、命令文档与回归验证

**Files:**
- Create: `docs/architecture/story-system-phase1.md`
- Modify: `README.md`
- Modify: `docs/architecture/overview.md`
- Modify: `docs/guides/commands.md`
- Modify: `docs/superpowers/README.md`

- [ ] **Step 1: 新建 Phase 1 架构文档**

`docs/architecture/story-system-phase1.md` 至少写清楚以下四段，避免 Phase 1 代码上线后又变成“隐式约定”：

```markdown
# Story System Phase 1

## JSON 真源
- `PROJECT_ROOT/.story-system/MASTER_SETTING.json`
- `PROJECT_ROOT/.story-system/anti_patterns.json`
- `PROJECT_ROOT/.story-system/chapters/chapter_XXX.json`

## 覆盖规则
- `locked`：chapter 不得覆盖
- `append_only`：chapter 只能补充
- `override_allowed`：chapter 可局部覆盖

## 运行时读取顺序
1. chapter brief
2. master setting
3. anti-patterns
4. genre profile fallback

## 迁移边界
- Phase 1 不引入 `VOLUME_BRIEF`
- Phase 1 不改写后回写主链
- `genre-profiles.md` 继续保留为回退层
```

- [ ] **Step 2: 更新命令与总览文档**

在 `docs/guides/commands.md` 增加：

````markdown
## Story System（Phase 1）

```bash
python -X utf8 "<CLAUDE_PLUGIN_ROOT>/scripts/webnovel.py" \
  --project-root "<WORKSPACE_ROOT>" \
  story-system "玄幻退婚流" --chapter 1 --persist --format both
```

说明：
- `--project-root` 允许传工作区根或书项目根
- 真实落盘位置始终是 `PROJECT_ROOT/.story-system/`
- `*.json` 为真源，`*.md` 为投影视图
````

在 `README.md` 与 `docs/architecture/overview.md` 补一条 Phase 1 说明：

```markdown
- Story System Phase 1：新增最小合同种子层（`MASTER_SETTING` / `chapter_XXX` / `anti_patterns`），
  作为 `context_manager` 的合同输入前置层。
```

- [ ] **Step 3: 更新 `docs/superpowers/README.md` 导航**

```markdown
- [`plans/2026-04-12-story-system-phase1-contract-seed.md`](./plans/2026-04-12-story-system-phase1-contract-seed.md)：Story System Phase 1 合同种子层实施计划
```

- [ ] **Step 4: 跑 Phase 1 目标测试集**

Run:

```bash
python -m pytest \
  webnovel-writer/scripts/data_modules/tests/test_story_contracts.py \
  webnovel-writer/scripts/data_modules/tests/test_story_system_engine.py \
  webnovel-writer/scripts/data_modules/tests/test_story_system_cli.py \
  webnovel-writer/scripts/data_modules/tests/test_context_manager.py \
  webnovel-writer/scripts/data_modules/tests/test_extract_chapter_context.py \
  webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py \
  -q --no-cov
```

Expected: 全部通过

- [ ] **Step 5: 跑 `reference_search.py` 回归，证明没有破坏底层 primitive**

Run: `python -m pytest webnovel-writer/scripts/tests/test_reference_search.py -q --no-cov`

Expected: 通过

- [ ] **Step 6: 最终提交**

```bash
git add README.md \
        docs/architecture/story-system-phase1.md \
        docs/architecture/overview.md \
        docs/guides/commands.md \
        docs/superpowers/README.md
git commit -m "docs: document story system phase1 contract seed layer"
```

---

## Spec Coverage Check

本计划对 `2026-04-12-story-system-evolution-spec.md` 的覆盖关系如下：

- `13.2 Phase 1：合同种子层`
  - `题材与调性推理.csv`：Task 2
  - 最小 `MASTER_SETTING`：Task 3
  - 最小 `CHAPTER_BRIEF`：Task 3
  - `anti_patterns.json`：Task 3
  - `context_manager` 读取合同：Task 4

- `14.1 / 14.1.1 路径解析约束`
  - `PROJECT_ROOT/.story-system`：Task 1 / Task 3
  - `resolve_project_root(args.project_root)` 经 unified CLI 注入：Task 3

- `15.3 当前阶段结论`
  - 保留 CSV + MD 双体系，不做自动迁移：Task 2

- `17.1 文档更新要求`
  - 合同 schema / 目录 / 运行流程 / 迁移说明文档：Task 5

- `19. 实施建议`
  - 明确先做合同种子层，不提前做 `CHAPTER_COMMIT` 或 event log：全计划范围

---

## Placeholder Scan

已避免以下占位式写法：

- 没有使用 “TODO / TBD / 后续补”
- 没有把“写测试”写成空泛口号，均给出测试骨架
- 没有把文档更新写成一句“同步更新文档”，而是明确到目标文件
- 没有把 Phase 2-4 内容混进 Phase 1 实施任务

---

## Next Plan

Phase 1 完成并稳定后，再进入下一份计划：

1. `Phase 2 Contract-First Runtime`：`VOLUME_BRIEF`、`REVIEW_CONTRACT`、写前禁区、履约 diff
2. `Phase 3 Chapter Commit Chain`：`CHAPTER_COMMIT`、accepted/rejected 语义、projection writers
3. `Phase 4 Event Log + Override Ledger`：canonical event log、`contract_override` / `amend_proposal`
