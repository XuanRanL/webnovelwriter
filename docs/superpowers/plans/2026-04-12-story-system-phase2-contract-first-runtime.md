# Story System Phase 2 Contract-First Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Phase 1 合同种子层之上，落地 `VOLUME_BRIEF`、`REVIEW_CONTRACT`、写前禁区与消歧域、大纲履约 diff、`context_manager` contract-first pack，让规划/写作/审查默认先消费合同而不是临时拼资料。

**Architecture:** 以 `.story-system/*.json` 为唯一合同真源，在 Phase 1 的 `MASTER_SETTING / CHAPTER_BRIEF / anti_patterns` 基础上新增卷级与审查级合同，并把 Phase 1 的扁平聚合结果拆成 schema 化合同家族。运行时遵循 `chapter -> volume -> master -> old profile/reference fallback` 的固定优先级；Markdown 在本阶段退化为 JSON 的只读渲染产物。

**Tech Stack:** Python 3.13, Pydantic, argparse, pytest, unified CLI `webnovel.py`, Markdown + JSON contract artifacts

**Spec:** `docs/superpowers/specs/2026-04-12-story-system-evolution-spec.md`

**Companion Specs:** `docs/superpowers/specs/2026-04-12-webnovel-story-intelligence-system-spec.md`, `docs/superpowers/plans/2026-04-12-story-system-phase1-contract-seed.md`

---

## Scope Split

本计划只覆盖 Phase 2：

1. `VOLUME_BRIEF`
2. `REVIEW_CONTRACT`
3. 写前禁区与消歧域
4. 大纲履约 diff
5. `context_manager` contract-first pack

明确不做：

- 不引入 `CHAPTER_COMMIT`
- 不把写后回写改成 commit 驱动
- 不建立 canonical event log
- 不做 override ledger 扩展迁移

本阶段的退出标准：

1. `MASTER / VOLUME / CHAPTER / REVIEW` 都有稳定 JSON schema
2. `context_manager` 能按合同优先级输出 pack
3. 写前能产出 `prewrite_validation` 与 `fulfillment_seed`
4. `webnovel-plan` / `webnovel-write` / `webnovel-review` 的默认读取顺序已切到合同优先
5. `genre-profiles.md` 与旧 reference 只作为 fallback，不再并列充当系统判断真源

文档更新沿用 Phase 1 已建好的 `Story System` 段落：

- Phase 2 只追加 `contract-first runtime`、`VOLUME_BRIEF`、`REVIEW_CONTRACT`
- 不重写 `README.md / overview.md / commands.md` 的总体结构

---

## File Structure

### 要创建的文件

- `webnovel-writer/scripts/data_modules/story_contract_schema.py`
- `webnovel-writer/scripts/data_modules/runtime_contract_builder.py`
- `webnovel-writer/scripts/data_modules/prewrite_validator.py`
- `webnovel-writer/scripts/data_modules/tests/test_story_contract_schema.py`
- `webnovel-writer/scripts/data_modules/tests/test_runtime_contract_builder.py`
- `webnovel-writer/scripts/data_modules/tests/test_prewrite_validator.py`
- `docs/architecture/story-system-phase2.md`

### 要修改的文件

- `webnovel-writer/scripts/data_modules/story_contracts.py`
- `webnovel-writer/scripts/data_modules/story_system_engine.py`
- `webnovel-writer/scripts/story_system.py`
- `webnovel-writer/scripts/data_modules/context_manager.py`
- `webnovel-writer/scripts/data_modules/tests/test_context_manager.py`
- `webnovel-writer/scripts/extract_chapter_context.py`
- `webnovel-writer/scripts/data_modules/tests/test_extract_chapter_context.py`
- `webnovel-writer/scripts/chapter_outline_loader.py`
- `webnovel-writer/scripts/data_modules/webnovel.py`
- `webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py`
- `webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py`
- `webnovel-writer/skills/webnovel-plan/SKILL.md`
- `webnovel-writer/skills/webnovel-write/SKILL.md`
- `webnovel-writer/skills/webnovel-review/SKILL.md`
- `README.md`
- `docs/architecture/overview.md`
- `docs/guides/commands.md`
- `docs/superpowers/README.md`

### 文件职责

- `story_contract_schema.py`：`MASTER_SETTING / VOLUME_BRIEF / CHAPTER_BRIEF / REVIEW_CONTRACT` 的 Pydantic schema 与版本元数据
- `runtime_contract_builder.py`：从 Phase 1 seed、卷范围、大纲结构、plot structure 生成 `VOLUME_BRIEF` 与 `REVIEW_CONTRACT`
- `prewrite_validator.py`：写前禁区检查、消歧域构建、履约 seed 与 must-check 列表生成
- `story_contracts.py`：新增 `volumes/`、`reviews/` 路径、JSON 真源写入、只读 Markdown 重建
- `context_manager.py`：把 contract-first pack 作为默认装配顺序
- `skills/*/SKILL.md`：把运行时入口切换为先生成/读取合同，再写作或审查

---

## Task 1: 建立 Phase 2 合同 schema 与目录扩展

**Files:**
- Create: `webnovel-writer/scripts/data_modules/story_contract_schema.py`
- Create: `webnovel-writer/scripts/data_modules/tests/test_story_contract_schema.py`
- Modify: `webnovel-writer/scripts/data_modules/story_contracts.py`

- [ ] **Step 1: 先写 schema 失败测试**

```python
# webnovel-writer/scripts/data_modules/tests/test_story_contract_schema.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pytest

from data_modules.story_contract_schema import ChapterBrief, MasterSetting, ReviewContract, VolumeBrief


def test_master_setting_and_chapter_brief_accept_phase1_seed_shape():
    master = MasterSetting.model_validate(
        {
            "meta": {"schema_version": "story-system/v1", "contract_type": "MASTER_SETTING"},
            "route": {"primary_genre": "玄幻退婚流"},
            "master_constraints": {"core_tone": "先压后爆", "pacing_strategy": "三章内首个反打"},
            "base_context": [],
            "source_trace": [],
            "override_policy": {"locked": ["route.primary_genre"], "append_only": ["anti_patterns"], "override_allowed": []},
        }
    )
    chapter = ChapterBrief.model_validate(
        {
            "meta": {"schema_version": "story-system/v1", "contract_type": "CHAPTER_BRIEF"},
            "override_allowed": {"chapter_focus": "退婚现场反打"},
            "dynamic_context": [],
            "source_trace": [],
        }
    )
    assert master.route["primary_genre"] == "玄幻退婚流"
    assert chapter.override_allowed["chapter_focus"] == "退婚现场反打"


def test_volume_brief_requires_selected_fields():
    payload = {
        "meta": {"schema_version": "story-system/v1", "contract_type": "VOLUME_BRIEF"},
        "volume_goal": {"summary": "卷一站稳脚跟"},
        "selected_tropes": ["退婚反击"],
        "selected_pacing": {"wave": "压抑后爆"},
        "selected_scenes": ["宗门大厅", "资源争夺"],
        "anti_patterns": ["配角抢主角兑现"],
        "system_constraints": ["金手指每日限一次"],
        "overrides": {"locked": {}, "append_only": {}, "override_allowed": {}},
    }
    model = VolumeBrief.model_validate(payload)
    assert model.volume_goal["summary"] == "卷一站稳脚跟"


def test_review_contract_requires_blocking_rules_list():
    with pytest.raises(Exception):
        ReviewContract.model_validate(
            {
                "meta": {"schema_version": "story-system/v1", "contract_type": "REVIEW_CONTRACT"},
                "must_check": ["mandatory_nodes"],
                "blocking_rules": "not-a-list",
                "genre_specific_risks": [],
                "anti_patterns": [],
                "system_constraints": [],
                "review_thresholds": {"blocking_count": 0},
                "overrides": {"locked": {}, "append_only": {}, "override_allowed": {}},
            }
        )
```

- [ ] **Step 2: 运行测试确认红灯**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_story_contract_schema.py -q --no-cov`

Expected: `ModuleNotFoundError: No module named 'data_modules.story_contract_schema'`

- [ ] **Step 3: 实现 Phase 2 schema 与目录路径**

```python
# webnovel-writer/scripts/data_modules/story_contract_schema.py
from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class ContractMeta(BaseModel):
    schema_version: str = "story-system/v1"
    contract_type: str
    generator_version: str = "phase2"
    source_trace: List[Dict[str, Any]] = Field(default_factory=list)


class OverrideBundle(BaseModel):
    locked: Dict[str, Any] = Field(default_factory=dict)
    append_only: Dict[str, Any] = Field(default_factory=dict)
    override_allowed: Dict[str, Any] = Field(default_factory=dict)


class MasterSetting(BaseModel):
    meta: ContractMeta
    route: Dict[str, Any] = Field(default_factory=dict)
    master_constraints: Dict[str, Any] = Field(default_factory=dict)
    base_context: List[Dict[str, Any]] = Field(default_factory=list)
    source_trace: List[Dict[str, Any]] = Field(default_factory=list)
    override_policy: Dict[str, List[str]] = Field(default_factory=dict)


class ChapterBrief(BaseModel):
    meta: ContractMeta
    override_allowed: Dict[str, Any] = Field(default_factory=dict)
    dynamic_context: List[Dict[str, Any]] = Field(default_factory=list)
    source_trace: List[Dict[str, Any]] = Field(default_factory=list)


class VolumeBrief(BaseModel):
    meta: ContractMeta
    volume_goal: Dict[str, Any]
    selected_tropes: List[str] = Field(default_factory=list)
    selected_pacing: Dict[str, Any] = Field(default_factory=dict)
    selected_scenes: List[str] = Field(default_factory=list)
    anti_patterns: List[str] = Field(default_factory=list)
    system_constraints: List[str] = Field(default_factory=list)
    overrides: OverrideBundle = Field(default_factory=OverrideBundle)


class ReviewContract(BaseModel):
    meta: ContractMeta
    must_check: List[str] = Field(default_factory=list)
    blocking_rules: List[str] = Field(default_factory=list)
    genre_specific_risks: List[str] = Field(default_factory=list)
    anti_patterns: List[str] = Field(default_factory=list)
    system_constraints: List[str] = Field(default_factory=list)
    review_thresholds: Dict[str, Any] = Field(default_factory=dict)
    overrides: OverrideBundle = Field(default_factory=OverrideBundle)
```

`blocking_rules` 在 Phase 2 先保持 `List[str]`，避免过早引入复杂 schema；但在文档中明确标注它是 **Phase 5 可升级为 `List[BlockingRule]` 的预留位**，后续如果要附带严重级、来源和匹配模式，再做结构化收口。

- [ ] **Step 4: 扩展 `story_contracts.py` 的卷级/审查级路径**

```python
# webnovel-writer/scripts/data_modules/story_contracts.py
@property
def volumes_dir(self) -> Path:
    return self.root / "volumes"

@property
def reviews_dir(self) -> Path:
    return self.root / "reviews"

def volume_json(self, volume: int) -> Path:
    return self.volumes_dir / f"volume_{volume:03d}.json"

def review_json(self, chapter: int) -> Path:
    return self.reviews_dir / f"chapter_{chapter:03d}.review.json"
```

- [ ] **Step 5: 回跑测试**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_story_contract_schema.py -q --no-cov`

Expected: 通过

- [ ] **Step 6: 提交**

```bash
git add webnovel-writer/scripts/data_modules/story_contract_schema.py \
        webnovel-writer/scripts/data_modules/story_contracts.py \
        webnovel-writer/scripts/data_modules/tests/test_story_contract_schema.py
git commit -m "feat: add phase2 contract schemas and paths"
```

---

## Task 2: 生成 `VOLUME_BRIEF` 与 `REVIEW_CONTRACT`

**Files:**
- Create: `webnovel-writer/scripts/data_modules/runtime_contract_builder.py`
- Create: `webnovel-writer/scripts/data_modules/tests/test_runtime_contract_builder.py`
- Modify: `webnovel-writer/scripts/data_modules/story_system_engine.py`
- Modify: `webnovel-writer/scripts/data_modules/story_contracts.py`
- Modify: `webnovel-writer/scripts/story_system.py`
- Modify: `webnovel-writer/scripts/chapter_outline_loader.py`

- [ ] **Step 1: 先写生成器测试**

```python
# webnovel-writer/scripts/data_modules/tests/test_runtime_contract_builder.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json

from data_modules.runtime_contract_builder import RuntimeContractBuilder


def test_runtime_contract_builder_creates_volume_and_review_contracts(tmp_path):
    project_root = tmp_path
    (project_root / ".webnovel").mkdir(parents=True, exist_ok=True)
    (project_root / ".webnovel" / "state.json").write_text(
        json.dumps(
            {
                "progress": {"volumes_planned": [{"volume": 1, "chapters_range": "1-20"}]},
                "chapter_meta": {},
                "disambiguation_pending": [],
                "disambiguation_warnings": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (project_root / ".story-system" / "MASTER_SETTING.json").parent.mkdir(parents=True, exist_ok=True)
    (project_root / ".story-system" / "MASTER_SETTING.json").write_text(
        json.dumps(
            {
                "meta": {"schema_version": "story-system/v1", "contract_type": "MASTER_SETTING"},
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
    (project_root / ".story-system" / "anti_patterns.json").write_text(
        json.dumps([{"text": "配角不能抢主角兑现"}], ensure_ascii=False),
        encoding="utf-8",
    )
    (project_root / "大纲").mkdir(parents=True, exist_ok=True)
    (project_root / "大纲" / "第1卷-详细大纲.md").write_text(
        "### 第3章：试压\\nCBN：继续压迫\\n必须覆盖节点：发现陷阱、决定隐忍\\n本章禁区：不可提前摊牌",
        encoding="utf-8",
    )

    builder = RuntimeContractBuilder(project_root)
    volume_brief, review_contract = builder.build_for_chapter(3)

    assert volume_brief["meta"]["contract_type"] == "VOLUME_BRIEF"
    assert review_contract["meta"]["contract_type"] == "REVIEW_CONTRACT"
    assert "发现陷阱" in review_contract["must_check"]
    assert "不可提前摊牌" in review_contract["blocking_rules"]
```

- [ ] **Step 2: 跑红灯**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_runtime_contract_builder.py -q --no-cov`

Expected: `ModuleNotFoundError: No module named 'data_modules.runtime_contract_builder'`

- [ ] **Step 3: 实现生成器**

```python
# webnovel-writer/scripts/data_modules/runtime_contract_builder.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple

from chapter_outline_loader import load_chapter_plot_structure, volume_num_for_chapter_from_state

from data_modules.story_contract_schema import MasterSetting, ReviewContract, VolumeBrief


class RuntimeContractBuilder:
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)

    def build_for_chapter(self, chapter: int) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        master = self._load_master_setting()
        anti_patterns = self._load_anti_patterns()
        plot = self._load_plot_structure(chapter)
        volume = self._resolve_volume(chapter)

        volume_brief = VolumeBrief.model_validate(
            {
                "meta": {"schema_version": "story-system/v1", "contract_type": "VOLUME_BRIEF"},
                "volume_goal": {"summary": f"第{volume}卷延续 {master.route.get('primary_genre', '')} 的主冲突"},
                "selected_tropes": [master.route.get("primary_genre", "")],
                "selected_pacing": {"wave": master.master_constraints.get("pacing_strategy", "")},
                "selected_scenes": list(plot.get("cpns") or []),
                "anti_patterns": [row.get("text", "") for row in anti_patterns if row.get("text")],
                "system_constraints": [master.master_constraints.get("core_tone", "")],
                "overrides": {"locked": {}, "append_only": {}, "override_allowed": {}},
            }
        ).model_dump()
        review_contract = ReviewContract.model_validate(
            {
                "meta": {"schema_version": "story-system/v1", "contract_type": "REVIEW_CONTRACT"},
                "must_check": list(plot.get("mandatory_nodes") or []),
                "blocking_rules": list(plot.get("prohibitions") or []),
                "genre_specific_risks": [master.route.get("primary_genre", "")],
                "anti_patterns": volume_brief["anti_patterns"],
                "system_constraints": volume_brief["system_constraints"],
                "review_thresholds": {"blocking_count": 0, "missed_nodes": 0},
                "overrides": {"locked": {}, "append_only": {}, "override_allowed": {}},
            }
        ).model_dump()
        return volume_brief, review_contract

    def _load_master_setting(self) -> MasterSetting:
        raw = json.loads((self.project_root / ".story-system" / "MASTER_SETTING.json").read_text(encoding="utf-8"))
        return MasterSetting.model_validate(raw)

    def _load_anti_patterns(self) -> list[Dict[str, Any]]:
        raw = json.loads((self.project_root / ".story-system" / "anti_patterns.json").read_text(encoding="utf-8"))
        return list(raw or [])

    def _load_plot_structure(self, chapter: int) -> Dict[str, Any]:
        raw = load_chapter_plot_structure(self.project_root, chapter) or {}
        return {
            "mandatory_nodes": list(raw.get("mandatory_nodes") or []),
            "prohibitions": list(raw.get("prohibitions") or []),
            "cpns": list(raw.get("cpns") or []),
        }

    def _resolve_volume(self, chapter: int) -> int:
        return volume_num_for_chapter_from_state(self.project_root, chapter) or 1
```

- [ ] **Step 4: 在 `story_system.py` 中新增 `build-runtime-contracts` 入口**

```python
# webnovel-writer/scripts/data_modules/story_contracts.py
from chapter_outline_loader import volume_num_for_chapter_from_state


def persist_runtime_contracts(project_root: Path, chapter: int, volume_brief: dict, review_contract: dict) -> None:
    paths = StoryContractPaths.from_project_root(project_root)
    volume = volume_num_for_chapter_from_state(project_root, chapter) or 1
    paths.volumes_dir.mkdir(parents=True, exist_ok=True)
    paths.reviews_dir.mkdir(parents=True, exist_ok=True)
    write_json(paths.volume_json(volume), volume_brief)
    write_json(paths.review_json(chapter), review_contract)

# webnovel-writer/scripts/story_system.py
parser.add_argument("--emit-runtime-contracts", action="store_true")

if args.emit_runtime_contracts:
    builder = RuntimeContractBuilder(project_root)
    volume_brief, review_contract = builder.build_for_chapter(args.chapter)
    persist_runtime_contracts(project_root, args.chapter, volume_brief, review_contract)
```

- [ ] **Step 5: 回跑测试**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_runtime_contract_builder.py -q --no-cov`

Expected: 通过

- [ ] **Step 6: 提交**

```bash
git add webnovel-writer/scripts/data_modules/runtime_contract_builder.py \
        webnovel-writer/scripts/data_modules/tests/test_runtime_contract_builder.py \
        webnovel-writer/scripts/data_modules/story_contracts.py \
        webnovel-writer/scripts/story_system.py \
        webnovel-writer/scripts/chapter_outline_loader.py
git commit -m "feat: generate volume brief and review contract"
```

---

## Task 3: 写前禁区、消歧域与大纲履约 diff

**Files:**
- Create: `webnovel-writer/scripts/data_modules/prewrite_validator.py`
- Create: `webnovel-writer/scripts/data_modules/tests/test_prewrite_validator.py`
- Modify: `webnovel-writer/scripts/data_modules/context_manager.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_context_manager.py`

- [ ] **Step 1: 先写 `prewrite_validator` 失败测试**

```python
# webnovel-writer/scripts/data_modules/tests/test_prewrite_validator.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json

from data_modules.prewrite_validator import PrewriteValidator


def test_prewrite_validator_builds_disambiguation_domain_and_fulfillment_seed(tmp_path):
    project_root = tmp_path
    (project_root / ".webnovel").mkdir(parents=True, exist_ok=True)
    (project_root / ".webnovel" / "state.json").write_text(
        json.dumps(
            {
                "disambiguation_pending": [],
                "disambiguation_warnings": [{"mention": "宗主"}],
                "chapter_meta": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    review_contract = {"must_check": ["发现陷阱"], "blocking_rules": ["不可提前摊牌"]}
    plot_structure = {"mandatory_nodes": ["发现陷阱"], "prohibitions": ["不可提前摊牌"]}

    payload = PrewriteValidator(project_root).build(chapter=3, review_contract=review_contract, plot_structure=plot_structure)

    assert payload["blocking"] is False
    assert payload["fulfillment_seed"]["planned_nodes"] == ["发现陷阱"]
    assert payload["disambiguation_domain"]["pending_count"] == 0
```

- [ ] **Step 2: 跑红灯**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_prewrite_validator.py -q --no-cov`

Expected: `ModuleNotFoundError: No module named 'data_modules.prewrite_validator'`

- [ ] **Step 3: 实现写前校验器**

```python
# webnovel-writer/scripts/data_modules/prewrite_validator.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


class PrewriteValidator:
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)

    def build(self, chapter: int, review_contract: Dict[str, Any], plot_structure: Dict[str, Any]) -> Dict[str, Any]:
        state = json.loads((self.project_root / ".webnovel" / "state.json").read_text(encoding="utf-8"))
        pending = state.get("disambiguation_pending") or []
        warnings = state.get("disambiguation_warnings") or []
        return {
            "chapter": chapter,
            "blocking": bool(pending),
            "blocking_reasons": ["存在高优先级 disambiguation_pending"] if pending else [],
            "forbidden_zones": list(review_contract.get("blocking_rules") or []),
            "disambiguation_domain": {
                "pending_count": len(pending),
                "warning_count": len(warnings),
                "allowed_mentions": [item.get("mention", "") for item in warnings if item.get("mention")],
            },
            "fulfillment_seed": {
                "planned_nodes": list(plot_structure.get("mandatory_nodes") or []),
                "prohibitions": list(plot_structure.get("prohibitions") or []),
            },
        }
```

- [ ] **Step 4: 在 `context_manager` 中新增 `prewrite_validation` section**

```python
# webnovel-writer/scripts/data_modules/context_manager.py
SECTION_ORDER = [
    "core",
    "story_contract",
    "prewrite_validation",
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

validator = PrewriteValidator(self.config.project_root)
pack["prewrite_validation"] = validator.build(
    chapter=chapter,
    review_contract=story_contract.get("review_contract") or {},
    plot_structure=plot_structure,
)
```

- [ ] **Step 5: 回跑测试**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_prewrite_validator.py webnovel-writer/scripts/data_modules/tests/test_context_manager.py -q --no-cov`

Expected: 通过

- [ ] **Step 6: 提交**

```bash
git add webnovel-writer/scripts/data_modules/prewrite_validator.py \
        webnovel-writer/scripts/data_modules/tests/test_prewrite_validator.py \
        webnovel-writer/scripts/data_modules/context_manager.py \
        webnovel-writer/scripts/data_modules/tests/test_context_manager.py
git commit -m "feat: add prewrite validation and fulfillment seed"
```

---

## Task 4: 切换 runtime 为 contract-first，并接入 skills / CLI

**Files:**
- Modify: `webnovel-writer/scripts/extract_chapter_context.py`
- Modify: `webnovel-writer/scripts/data_modules/webnovel.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py`
- Modify: `webnovel-writer/skills/webnovel-plan/SKILL.md`
- Modify: `webnovel-writer/skills/webnovel-write/SKILL.md`
- Modify: `webnovel-writer/skills/webnovel-review/SKILL.md`

- [ ] **Step 1: 先补 contract-first 读取顺序测试**

在 `test_prompt_integrity.py` 增加更稳的“步骤块”断言，而不是裸字符串包含：

```python
def test_story_system_runtime_contract_commands_exist():
    import re

    text = Path("webnovel-writer/skills/webnovel-write/SKILL.md").read_text(encoding="utf-8")
    block = re.search(r"story-system[\\s\\S]+--emit-runtime-contracts[\\s\\S]+REVIEW_CONTRACT", text)
    assert block, "webnovel-write skill 必须包含生成 runtime contracts 的完整步骤块"
```

在 `test_webnovel_unified_cli.py` 增加：

```python
def test_webnovel_story_system_runtime_forwards(monkeypatch, tmp_path):
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
    monkeypatch.setattr(sys, "argv", ["webnovel", "--project-root", str(project_root), "story-system", "玄幻退婚流", "--emit-runtime-contracts"])
    cli.main()

    assert called["script_name"] == "story_system.py"
    assert "--emit-runtime-contracts" in called["argv"]
```

- [ ] **Step 2: 跑红灯**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py -q --no-cov`

Expected: 新断言失败

- [ ] **Step 3: 修改技能与文本提取脚本**

在三个 skill 中统一插入 Phase 2 前置步骤：

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${WORKSPACE_ROOT}" \
  story-system "{chapter_goal}" --chapter {chapter_num} --persist --emit-runtime-contracts --format both
```

并在 `extract_chapter_context.py` 输出：

```python
story_contract = contract_context.get("story_contract") or {}
review_contract = story_contract.get("review_contract") or {}
prewrite_validation = payload.get("prewrite_validation") or {}

lines.append("## Contract-First Runtime")
lines.append(f"- Review blocking rules: {len(review_contract.get('blocking_rules') or [])}")
lines.append(f"- Prewrite blocking: {prewrite_validation.get('blocking')}")
```

- [ ] **Step 4: 回跑测试**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py webnovel-writer/scripts/data_modules/tests/test_extract_chapter_context.py -q --no-cov`

Expected: 通过

- [ ] **Step 5: 提交**

```bash
git add webnovel-writer/scripts/extract_chapter_context.py \
        webnovel-writer/scripts/data_modules/webnovel.py \
        webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py \
        webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py \
        webnovel-writer/skills/webnovel-plan/SKILL.md \
        webnovel-writer/skills/webnovel-write/SKILL.md \
        webnovel-writer/skills/webnovel-review/SKILL.md
git commit -m "feat: switch runtime entrypoints to contract-first flow"
```

---

## Task 5: 文档更新与 Phase 2 回归验证

**Files:**
- Create: `docs/architecture/story-system-phase2.md`
- Modify: `README.md`
- Modify: `docs/architecture/overview.md`
- Modify: `docs/guides/commands.md`
- Modify: `docs/superpowers/README.md`

- [ ] **Step 1: 新建 Phase 2 架构文档**

`docs/architecture/story-system-phase2.md` 必须至少包含：

```markdown
# Story System Phase 2

## 合同真源
- `MASTER_SETTING.json`
- `volumes/volume_XXX.json`
- `chapters/chapter_XXX.json`
- `reviews/chapter_XXX.review.json`

## 运行时顺序
1. chapter brief
2. volume brief
3. master setting
4. fallback references

## 写前校验
- forbidden zones
- disambiguation domain
- fulfillment seed

## 非目标
- 不引入 `CHAPTER_COMMIT`
- 不引入 canonical event log
```

- [ ] **Step 2: 更新命令文档**

在 `docs/guides/commands.md` 增加：

```bash
python -X utf8 "<CLAUDE_PLUGIN_ROOT>/scripts/webnovel.py" \
  --project-root "<WORKSPACE_ROOT>" \
  story-system "玄幻退婚流" --chapter 3 --persist --emit-runtime-contracts --format both
```

- [ ] **Step 3: 跑 Phase 2 最小验证集**

Run:

```bash
python -m pytest \
  webnovel-writer/scripts/data_modules/tests/test_story_contract_schema.py \
  webnovel-writer/scripts/data_modules/tests/test_runtime_contract_builder.py \
  webnovel-writer/scripts/data_modules/tests/test_prewrite_validator.py \
  webnovel-writer/scripts/data_modules/tests/test_context_manager.py \
  webnovel-writer/scripts/data_modules/tests/test_extract_chapter_context.py \
  webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py \
  webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py \
  -q --no-cov
```

Expected: 全部通过

- [ ] **Step 4: 回归 `reference_search.py`**

Run: `python -m pytest webnovel-writer/scripts/tests/test_reference_search.py -q --no-cov`

Expected: 通过

- [ ] **Step 5: 最终提交**

```bash
git add README.md \
        docs/architecture/story-system-phase2.md \
        docs/architecture/overview.md \
        docs/guides/commands.md \
        docs/superpowers/README.md
git commit -m "docs: document story system phase2 contract-first runtime"
```

---

## Spec Coverage Check

- `13.3 Phase 2：合同优先运行时`
  - `VOLUME_BRIEF`：Task 1 / Task 2
  - `REVIEW_CONTRACT`：Task 1 / Task 2
  - 写前禁区与消歧域：Task 3
  - 大纲履约 diff seed：Task 3
  - `context_manager` contract-first pack：Task 3 / Task 4

- `7.2 运行时优先级`
  - `chapter -> volume -> master -> old profile`：Task 3 / Task 4

- `11.1 写前校验`
  - 可见合同、禁区、消歧 pending、must cover：Task 3

- `17.1 文档更新要求`
  - schema、目录、流程、命令：Task 5

---

## Placeholder Scan

- 没有使用 `TODO / TBD / implement later`
- 没有把“接入 skill”写成空话，已给出具体 skill 文件
- 没有把 Phase 3 的 `CHAPTER_COMMIT` 混入本阶段任务

---

## Next Plan

Phase 2 完成后进入：

1. `Phase 3 Chapter Commit Chain`
2. `Phase 4 Event Log And Override Ledger`
