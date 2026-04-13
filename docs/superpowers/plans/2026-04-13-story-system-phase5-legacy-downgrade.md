# Story System Phase 5 Legacy Downgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把旧中枢正式降级为兼容/投影层，让写前默认输入统一到 Story Contracts，让写后默认事实统一到 accepted `CHAPTER_COMMIT`，并让 preflight / dashboard / skills / agents 都显式反映这条主链。

**Architecture:** 新增统一 runtime 来源解析层，集中回答“本章现在应该信什么”。`context_manager`、`memory_contract_adapter`、`extract_chapter_context`、skills 与 dashboard 都只认 `MASTER / VOLUME / CHAPTER / REVIEW + latest accepted CHAPTER_COMMIT`；`state.json / index.db / summaries / memory_scratchpad` 保留，但只作为 commit 投影和查询 read-model。旧 `genre-profiles.md`、旧散写命令、旧 state-first 心智模型继续存在时，必须只以 fallback / compatibility 明示暴露，不能再伪装成主链。

**Tech Stack:** Python 3.13, pytest, Pydantic, SQLite (`index.db`), FastAPI dashboard, React frontend, Story System JSON artifacts under `.story-system/`

**Spec:** `docs/superpowers/specs/2026-04-12-story-system-evolution-spec.md`

**Companion Plans:** `docs/superpowers/plans/2026-04-12-story-system-phase2-contract-first-runtime.md`, `docs/superpowers/plans/2026-04-12-story-system-phase3-chapter-commit-chain.md`, `docs/superpowers/plans/2026-04-12-story-system-phase4-event-log-and-override-ledger.md`

---

## Scope Split

本计划只覆盖 Phase 5：

1. 合同成为默认主输入
2. accepted `CHAPTER_COMMIT` 成为默认写后事实入口
3. `state / index / summary / memory` 显式降级为投影/read-model
4. `genre-profiles.md` 与旧 reference 判断链显式退化为 fallback
5. preflight / dashboard / query / write / review / context-agent / data-agent 全部切到新主链认知

明确不做：

- 不重写 `StateManager / IndexManager / ScratchpadManager` 的底层存储
- 不删除 `.webnovel/state.json`、`.webnovel/index.db`、`.webnovel/memory_scratchpad.json`
- 不重建历史全量 commit / event 数据
- 不新增第二套 commit / projection 体系
- 不做与 Phase 5 无关的 UI 大改版

退出标准：

1. `context_manager`、`memory_contract_adapter`、`extract_chapter_context` 默认读取合同与 latest accepted commit，而不是先读旧状态再拼判断
2. `ChapterCommitService` 写出的 commit 元数据足以声明其为唯一写后事实来源，并能稳定定位 `MASTER / VOLUME / CHAPTER / REVIEW`
3. `webnovel-write` / `webnovel-query` / `webnovel-review` / `webnovel-plan` 与 `context-agent` / `data-agent` 的默认指令已切到 contract-first + commit-first
4. preflight 与 dashboard 能直接暴露“主链是否就绪、是否仍落入 legacy fallback、是否存在 rejected / projection backlog”
5. `genre-profiles.md` 被明示为 fallback-only；合同存在时不再参与全局系统判断
6. 文档、命令说明、运维手册都能准确描述 `.story-system` 主链和 `.webnovel/*` 投影链的关系

---

## File Structure

### 要创建的文件

- `webnovel-writer/scripts/data_modules/story_runtime_sources.py`
- `webnovel-writer/scripts/data_modules/story_runtime_health.py`
- `webnovel-writer/scripts/data_modules/tests/test_story_runtime_sources.py`
- `webnovel-writer/scripts/data_modules/tests/test_story_runtime_health.py`
- `docs/architecture/story-system-phase5.md`

### 要修改的文件

- `webnovel-writer/scripts/data_modules/chapter_commit_service.py`
- `webnovel-writer/scripts/data_modules/context_manager.py`
- `webnovel-writer/scripts/data_modules/memory_contract_adapter.py`
- `webnovel-writer/scripts/extract_chapter_context.py`
- `webnovel-writer/scripts/data_modules/tests/test_chapter_commit_service.py`
- `webnovel-writer/scripts/data_modules/tests/test_context_manager.py`
- `webnovel-writer/scripts/data_modules/tests/test_memory_contract_adapter.py`
- `webnovel-writer/scripts/data_modules/tests/test_extract_chapter_context.py`
- `webnovel-writer/scripts/data_modules/webnovel.py`
- `webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py`
- `webnovel-writer/dashboard/app.py`
- `webnovel-writer/dashboard/frontend/src/App.jsx`
- `webnovel-writer/dashboard/frontend/src/api.js`
- `webnovel-writer/skills/webnovel-write/SKILL.md`
- `webnovel-writer/skills/webnovel-review/SKILL.md`
- `webnovel-writer/skills/webnovel-query/SKILL.md`
- `webnovel-writer/skills/webnovel-plan/SKILL.md`
- `webnovel-writer/skills/webnovel-dashboard/SKILL.md`
- `webnovel-writer/agents/context-agent.md`
- `webnovel-writer/agents/data-agent.md`
- `webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py`
- `webnovel-writer/references/genre-profiles.md`
- `README.md`
- `docs/architecture/overview.md`
- `docs/guides/commands.md`
- `docs/operations/operations.md`
- `docs/superpowers/README.md`

### 文件职责

- `story_runtime_sources.py`：统一解析本章 contracts、latest commit、fallback 状态，避免各入口各自判断
- `story_runtime_health.py`：把主链状态、legacy fallback、rejected/backlog 汇总为 preflight / dashboard 共用健康报告
- `chapter_commit_service.py`：补齐 write-fact provenance，确保 commit 能明确引用 volume 合同与写后真理角色
- `context_manager.py`：把 runtime pack 切成“合同主链 + commit 摘要 + legacy fallback hints”
- `memory_contract_adapter.py`：让 `load_context` 和 `commit_chapter` 都服从 contract/commit 主链
- `extract_chapter_context.py`：把导出文本从“旧状态摘要”升级为“主链状态 + fallback 显示”
- `webnovel.py`：preflight 暴露 story runtime health，统一 CLI 对外语义
- `dashboard/app.py` + `frontend/src/*`：提供可视化 runtime health / commit 状态 / legacy fallback 观测
- `skills/*` + `agents/*`：把人机提示词中的默认工作流从旧散写链切到 commit 主链

---

## Task 1: 建立统一 runtime 来源解析与 commit provenance

**Files:**
- Create: `webnovel-writer/scripts/data_modules/story_runtime_sources.py`
- Create: `webnovel-writer/scripts/data_modules/tests/test_story_runtime_sources.py`
- Modify: `webnovel-writer/scripts/data_modules/chapter_commit_service.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_chapter_commit_service.py`

- [ ] **Step 1: 先写 runtime 来源与 commit provenance 的失败测试**

```python
# webnovel-writer/scripts/data_modules/tests/test_story_runtime_sources.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json

from data_modules.story_runtime_sources import load_runtime_sources


def test_load_runtime_sources_prefers_latest_accepted_commit(tmp_path):
    story_root = tmp_path / ".story-system"
    (story_root / "chapters").mkdir(parents=True, exist_ok=True)
    (story_root / "volumes").mkdir(parents=True, exist_ok=True)
    (story_root / "reviews").mkdir(parents=True, exist_ok=True)
    (story_root / "commits").mkdir(parents=True, exist_ok=True)

    (story_root / "MASTER_SETTING.json").write_text(
        json.dumps({"meta": {"contract_type": "MASTER_SETTING"}, "route": {"primary_genre": "玄幻"}}),
        encoding="utf-8",
    )
    (story_root / "chapters" / "chapter_003.json").write_text(
        json.dumps({"meta": {"contract_type": "CHAPTER_BRIEF", "chapter": 3}}),
        encoding="utf-8",
    )
    (story_root / "volumes" / "volume_001.json").write_text(
        json.dumps({"meta": {"contract_type": "VOLUME_BRIEF", "volume": 1}}),
        encoding="utf-8",
    )
    (story_root / "reviews" / "chapter_003.review.json").write_text(
        json.dumps({"meta": {"contract_type": "REVIEW_CONTRACT", "chapter": 3}}),
        encoding="utf-8",
    )
    (story_root / "commits" / "chapter_003.commit.json").write_text(
        json.dumps(
            {
                "meta": {"schema_version": "story-system/v1", "chapter": 3, "status": "accepted"},
                "provenance": {"write_fact_role": "chapter_commit"},
                "projection_status": {"state": "done", "index": "done", "summary": "done", "memory": "done"},
            }
        ),
        encoding="utf-8",
    )

    snapshot = load_runtime_sources(tmp_path, chapter=3)

    assert snapshot.latest_accepted_commit["meta"]["status"] == "accepted"
    assert snapshot.primary_write_source == "chapter_commit"
    assert snapshot.fallback_sources == []
```

```python
# webnovel-writer/scripts/data_modules/tests/test_chapter_commit_service.py
def test_commit_service_includes_volume_ref_and_write_fact_provenance(tmp_path):
    service = ChapterCommitService(tmp_path)
    payload = service.build_commit(
        chapter=3,
        review_result={"blocking_count": 0},
        fulfillment_result={"planned_nodes": ["发现陷阱"], "covered_nodes": ["发现陷阱"], "missed_nodes": [], "extra_nodes": []},
        disambiguation_result={"pending": []},
        extraction_result={"state_deltas": [], "entity_deltas": [], "accepted_events": []},
    )

    assert payload["contract_refs"]["volume"] == "volume_001.json"
    assert payload["provenance"]["write_fact_role"] == "chapter_commit"
    assert payload["provenance"]["projection_role"] == "derived_read_models"
```

- [ ] **Step 2: 跑红灯，确认新测试确实失败**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_story_runtime_sources.py webnovel-writer/scripts/data_modules/tests/test_chapter_commit_service.py -q --no-cov`

Expected:
- `ModuleNotFoundError: No module named 'data_modules.story_runtime_sources'`
- 或 `KeyError: 'volume' / 'provenance'`

- [ ] **Step 3: 实现统一 runtime 来源解析器**

```python
# webnovel-writer/scripts/data_modules/story_runtime_sources.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .story_contracts import StoryContractPaths, read_json_if_exists


@dataclass
class RuntimeSourceSnapshot:
    chapter: int
    contracts: dict[str, dict[str, Any]]
    latest_commit: dict[str, Any] | None
    latest_accepted_commit: dict[str, Any] | None
    fallback_sources: list[str] = field(default_factory=list)
    primary_write_source: str = "chapter_commit"

    def to_dict(self) -> dict[str, Any]:
        return {
            "chapter": self.chapter,
            "contracts": self.contracts,
            "latest_commit": self.latest_commit,
            "latest_accepted_commit": self.latest_accepted_commit,
            "fallback_sources": self.fallback_sources,
            "primary_write_source": self.primary_write_source,
        }


def load_runtime_sources(project_root: Path, chapter: int) -> RuntimeSourceSnapshot:
    paths = StoryContractPaths.from_project_root(project_root)
    contracts = {
        "master": read_json_if_exists(paths.master_json) or {},
        "chapter": read_json_if_exists(paths.chapter_json(chapter)) or {},
        "volume": read_json_if_exists(paths.volume_json(1)) or {},
        "review": read_json_if_exists(paths.review_json(chapter)) or {},
    }

    latest_commit = read_json_if_exists(paths.commit_json(chapter))
    latest_accepted_commit = latest_commit if (latest_commit or {}).get("meta", {}).get("status") == "accepted" else None

    fallback_sources: list[str] = []
    for key, payload in contracts.items():
        if not payload:
            fallback_sources.append(f"missing_{key}_contract")
    if latest_accepted_commit is None:
        fallback_sources.append("missing_accepted_commit")

    return RuntimeSourceSnapshot(
        chapter=chapter,
        contracts=contracts,
        latest_commit=latest_commit,
        latest_accepted_commit=latest_accepted_commit,
        fallback_sources=fallback_sources,
    )
```

- [ ] **Step 4: 在 commit service 中补齐 provenance 字段和 volume 引用**

```python
# webnovel-writer/scripts/data_modules/chapter_commit_service.py
from chapter_outline_loader import volume_num_for_chapter_from_state


def build_commit(
    self,
    chapter: int,
    review_result: Dict[str, Any],
    fulfillment_result: Dict[str, Any],
    disambiguation_result: Dict[str, Any],
    extraction_result: Dict[str, Any],
) -> Dict[str, Any]:
    volume = volume_num_for_chapter_from_state(self.project_root, chapter) or 1
    return {
        "meta": {
            "schema_version": "story-system/v1",
            "chapter": chapter,
            "status": status,
        },
        "contract_refs": {
            "master": "MASTER_SETTING.json",
            "volume": f"volume_{volume:03d}.json",
            "chapter": f"chapter_{chapter:03d}.json",
            "review": f"chapter_{chapter:03d}.review.json",
        },
        "provenance": {
            "write_fact_role": "chapter_commit",
            "projection_role": "derived_read_models",
            "legacy_state_role": "projection_only",
        },
        "outline_snapshot": {
            "planned_nodes": fulfillment_result.get("planned_nodes", []),
            "covered_nodes": fulfillment_result.get("covered_nodes", []),
            "missed_nodes": fulfillment_result.get("missed_nodes", []),
            "extra_nodes": fulfillment_result.get("extra_nodes", []),
        },
        "review_result": review_result,
        "fulfillment_result": fulfillment_result,
        "disambiguation_result": disambiguation_result,
        "accepted_events": extraction_result.get("accepted_events", []),
        "state_deltas": extraction_result.get("state_deltas", []),
        "entity_deltas": extraction_result.get("entity_deltas", []),
        "summary_text": extraction_result.get("summary_text", ""),
        "projection_status": {"state": "pending", "index": "pending", "summary": "pending", "memory": "pending"},
    }
```

- [ ] **Step 5: 重新跑聚焦测试**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_story_runtime_sources.py webnovel-writer/scripts/data_modules/tests/test_chapter_commit_service.py -q --no-cov`

Expected: `2 passed`

- [ ] **Step 6: 提交本任务**

```bash
git add webnovel-writer/scripts/data_modules/story_runtime_sources.py \
        webnovel-writer/scripts/data_modules/chapter_commit_service.py \
        webnovel-writer/scripts/data_modules/tests/test_story_runtime_sources.py \
        webnovel-writer/scripts/data_modules/tests/test_chapter_commit_service.py
git commit -m "feat: add story runtime source resolver"
```

---

## Task 2: 把上下文入口切到 contract-first + commit-first

**Files:**
- Modify: `webnovel-writer/scripts/data_modules/context_manager.py`
- Modify: `webnovel-writer/scripts/data_modules/memory_contract_adapter.py`
- Modify: `webnovel-writer/scripts/extract_chapter_context.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_context_manager.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_memory_contract_adapter.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_extract_chapter_context.py`

- [ ] **Step 1: 先补三组失败测试，锁定新主链语义**

```python
# webnovel-writer/scripts/data_modules/tests/test_context_manager.py
def test_context_manager_prefers_contract_route_over_legacy_genre_profile(temp_project):
    refs_dir = temp_project.project_root / ".claude" / "references"
    refs_dir.mkdir(parents=True, exist_ok=True)
    (refs_dir / "genre-profiles.md").write_text("## 都市\n- 旧画像提示", encoding="utf-8")
    (refs_dir / "reading-power-taxonomy.md").write_text("## 都市\n- 旧分类", encoding="utf-8")

    state = {
        "project": {"genre": "都市"},
        "protagonist_state": {"name": "林默"},
        "chapter_meta": {},
        "disambiguation_warnings": [],
        "disambiguation_pending": [],
    }
    temp_project.state_file.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    story_root = temp_project.story_system_dir
    story_root.mkdir(parents=True, exist_ok=True)
    (story_root / "MASTER_SETTING.json").write_text(
        json.dumps(
            {
                "meta": {"schema_version": "story-system/v1", "contract_type": "MASTER_SETTING"},
                "route": {"primary_genre": "都市异能"},
                "master_constraints": {"core_tone": "先压后爆"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    manager = ContextManager(temp_project)
    payload = manager.build_context(3, use_snapshot=False, save_snapshot=False)

    assert payload["sections"]["story_contract"]["content"]["master"]["route"]["primary_genre"] == "都市异能"
    assert payload["sections"]["runtime_status"]["content"]["fallback_sources"] == ["missing_volume_contract", "missing_chapter_contract", "missing_review_contract", "missing_accepted_commit"]
```

```python
# webnovel-writer/scripts/data_modules/tests/test_memory_contract_adapter.py
def test_commit_chapter_delegates_to_chapter_commit_mainline(tmp_path):
    cfg = _make_project(tmp_path)
    adapter = MemoryContractAdapter(cfg)

    result = adapter.commit_chapter(
        3,
        {
            "review_result": {"blocking_count": 0},
            "fulfillment_result": {"planned_nodes": ["发现陷阱"], "covered_nodes": ["发现陷阱"], "missed_nodes": [], "extra_nodes": []},
            "disambiguation_result": {"pending": []},
            "extraction_result": {"state_deltas": [], "entity_deltas": [], "accepted_events": [], "summary_text": "本章摘要"},
        },
    )

    assert (tmp_path / ".story-system" / "commits" / "chapter_003.commit.json").is_file()
    assert result.chapter == 3
    assert "commit_status=accepted" in result.warnings
```

```python
# webnovel-writer/scripts/data_modules/tests/test_extract_chapter_context.py
def test_render_text_contains_runtime_status_section(tmp_path):
    from extract_chapter_context import _render_text

    text = _render_text(
        {
            "chapter": 3,
            "outline": "测试大纲",
            "previous_summaries": [],
            "state_summary": "旧状态摘要",
            "context_contract_version": "v2",
            "reader_signal": {},
            "genre_profile": {},
            "writing_guidance": {},
            "runtime_status": {
                "primary_write_source": "chapter_commit",
                "fallback_sources": ["missing_accepted_commit"],
            },
            "latest_commit": {"meta": {"chapter": 3, "status": "rejected"}},
        }
    )

    assert "## Runtime Status" in text
    assert "- 写后事实入口: chapter_commit" in text
    assert "- Legacy Fallback: missing_accepted_commit" in text
```

- [ ] **Step 2: 跑红灯，确认当前入口仍然偏旧链路**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_context_manager.py webnovel-writer/scripts/data_modules/tests/test_memory_contract_adapter.py webnovel-writer/scripts/data_modules/tests/test_extract_chapter_context.py -q --no-cov`

Expected:
- `KeyError: 'runtime_status'`
- `AssertionError`（`commit_chapter` 仍未生成 `.story-system/commits/chapter_003.commit.json`）
- `_render_text` 中不存在 runtime status 段

- [ ] **Step 3: 重写 ContextManager 的 pack 组装顺序**

```python
# webnovel-writer/scripts/data_modules/context_manager.py
from .story_runtime_sources import load_runtime_sources


def _build_pack(self, chapter: int) -> Dict[str, Any]:
    runtime_sources = load_runtime_sources(self.config.project_root, chapter)
    state = self._load_state()

    story_contract = {
        "master": runtime_sources.contracts.get("master") or {},
        "volume": runtime_sources.contracts.get("volume") or {},
        "chapter": runtime_sources.contracts.get("chapter") or {},
        "review_contract": runtime_sources.contracts.get("review") or {},
    }

    genre_profile = {}
    if runtime_sources.fallback_sources:
        genre_profile = self._load_genre_profile(state)
        genre_profile["mode"] = "fallback_only"

    reader_signal = self._load_reader_signal(chapter)
    return {
        "story_contract": story_contract,
        "runtime_status": runtime_sources.to_dict(),
        "latest_commit": runtime_sources.latest_accepted_commit or runtime_sources.latest_commit or {},
        "genre_profile": genre_profile,
        "reader_signal": reader_signal,
        "preferences": self._load_json_optional(self.config.webnovel_dir / "preferences.json"),
        "writing_guidance": self._build_writing_guidance(chapter, reader_signal, genre_profile),
    }
```

- [ ] **Step 4: 让 MemoryContractAdapter 同时切换读链与写链**

```python
# webnovel-writer/scripts/data_modules/memory_contract_adapter.py
from .chapter_commit_service import ChapterCommitService
from .story_runtime_sources import load_runtime_sources


def load_context(self, chapter: int, budget_tokens: int = 4000) -> ContextPack:
    runtime_sources = load_runtime_sources(self.config.project_root, chapter)
    sections = {
        "story_contracts": runtime_sources.contracts,
        "runtime_status": runtime_sources.to_dict(),
        "latest_commit": runtime_sources.latest_accepted_commit or runtime_sources.latest_commit or {},
    }
    return ContextPack(chapter=chapter, sections=sections, budget_used_tokens=0)


def commit_chapter(self, chapter: int, result: dict) -> CommitResult:
    service = ChapterCommitService(self.config.project_root)
    payload = service.build_commit(
        chapter=chapter,
        review_result=result.get("review_result", {}),
        fulfillment_result=result.get("fulfillment_result", {}),
        disambiguation_result=result.get("disambiguation_result", {}),
        extraction_result=result.get("extraction_result", {}),
    )
    service.persist_commit(payload)
    payload = service.apply_projections(payload) if payload["meta"]["status"] == "accepted" else payload
    summary_path = str(self.config.webnovel_dir / "summaries" / f"ch{chapter:04d}.md")
    return CommitResult(
        chapter=chapter,
        entities_added=len((payload.get("entity_deltas") or [])),
        entities_updated=0,
        state_changes_recorded=len((payload.get("state_deltas") or [])),
        relationships_added=0,
        memory_items_added=0,
        summary_path=summary_path if Path(summary_path).exists() else "",
        warnings=[f"commit_status={payload['meta']['status']}"],
    )
```

- [ ] **Step 5: 更新 `extract_chapter_context.py` 的文本输出，让 legacy fallback 显式可见**

```python
# webnovel-writer/scripts/extract_chapter_context.py
def _render_text(payload: Dict[str, Any]) -> str:
    lines = [f"# 第{payload.get('chapter', 0)}章上下文"]
    runtime_status = payload.get("runtime_status") or {}
    latest_commit = payload.get("latest_commit") or {}
    lines.extend(
        [
            "## Runtime Status",
            f"- 写后事实入口: {runtime_status.get('primary_write_source', 'unknown')}",
            f"- Legacy Fallback: {', '.join(runtime_status.get('fallback_sources') or ['none'])}",
            f"- Latest Commit: {(latest_commit.get('meta') or {}).get('status', 'missing')}",
        ]
    )
    return "\n".join(lines)
```

- [ ] **Step 6: 重跑聚焦测试**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_context_manager.py webnovel-writer/scripts/data_modules/tests/test_memory_contract_adapter.py webnovel-writer/scripts/data_modules/tests/test_extract_chapter_context.py -q --no-cov`

Expected: `3 passed` 或对应文件内全部通过

- [ ] **Step 7: 提交本任务**

```bash
git add webnovel-writer/scripts/data_modules/context_manager.py \
        webnovel-writer/scripts/data_modules/memory_contract_adapter.py \
        webnovel-writer/scripts/extract_chapter_context.py \
        webnovel-writer/scripts/data_modules/tests/test_context_manager.py \
        webnovel-writer/scripts/data_modules/tests/test_memory_contract_adapter.py \
        webnovel-writer/scripts/data_modules/tests/test_extract_chapter_context.py
git commit -m "feat: switch context loading to contract and commit chain"
```

---

## Task 3: 把 skills / agents 的默认工作流切到 commit 主链

**Files:**
- Modify: `webnovel-writer/skills/webnovel-write/SKILL.md`
- Modify: `webnovel-writer/skills/webnovel-review/SKILL.md`
- Modify: `webnovel-writer/skills/webnovel-query/SKILL.md`
- Modify: `webnovel-writer/skills/webnovel-plan/SKILL.md`
- Modify: `webnovel-writer/skills/webnovel-dashboard/SKILL.md`
- Modify: `webnovel-writer/agents/context-agent.md`
- Modify: `webnovel-writer/agents/data-agent.md`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py`

- [ ] **Step 1: 先写 prompt integrity 失败测试，锁住新主链叙述**

```python
# webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py
def test_webnovel_write_skill_uses_chapter_commit_as_step5_mainline():
    text = (SKILLS_DIR / "webnovel-write" / "SKILL.md").read_text(encoding="utf-8")
    assert "chapter-commit" in text
    assert "accepted `CHAPTER_COMMIT`" in text
    assert "state process-chapter" not in text


def test_data_agent_is_described_as_extraction_only_not_direct_write_mainline():
    text = (AGENTS_DIR / "data-agent.md").read_text(encoding="utf-8")
    assert "chapter-commit" in text
    assert "直接写入 index.db 和 state.json" not in text


def test_webnovel_query_skill_prefers_story_system_and_memory_contract():
    text = (SKILLS_DIR / "webnovel-query" / "SKILL.md").read_text(encoding="utf-8")
    assert "memory-contract load-context" in text
    assert ".story-system/" in text
    assert 'cat "$PROJECT_ROOT/.webnovel/state.json"' not in text
```

- [ ] **Step 2: 跑红灯**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py -q --no-cov`

Expected: 至少 1 个断言失败，说明提示词仍在使用旧散写心智模型

- [ ] **Step 3: 改写 `webnovel-write`，让 Step 5 以 commit 为成功判定**

````md
<!-- webnovel-writer/skills/webnovel-write/SKILL.md -->
### Step 5：构建 extraction artifacts 并提交 `CHAPTER_COMMIT`

必须产出中间文件：
- `${PROJECT_ROOT}/.webnovel/tmp/review_results.json`
- `${PROJECT_ROOT}/.webnovel/tmp/fulfillment_result.json`
- `${PROJECT_ROOT}/.webnovel/tmp/disambiguation_result.json`
- `${PROJECT_ROOT}/.webnovel/tmp/extraction_result.json`

主命令：

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" chapter-commit \
  --chapter {chapter_num} \
  --review-result "${PROJECT_ROOT}/.webnovel/tmp/review_results.json" \
  --fulfillment-result "${PROJECT_ROOT}/.webnovel/tmp/fulfillment_result.json" \
  --disambiguation-result "${PROJECT_ROOT}/.webnovel/tmp/disambiguation_result.json" \
  --extraction-result "${PROJECT_ROOT}/.webnovel/tmp/extraction_result.json"
```

成功标准：
- `.story-system/commits/chapter_{chapter_num}.commit.json` 已存在
- `meta.status == accepted`
- `projection_status` 中 `state/index/summary/memory` 均为 `done` 或明确 `skipped`
````

- [ ] **Step 4: 改写 query / review / plan / context-agent / data-agent 的默认读取与写入叙述**

```md
<!-- webnovel-writer/agents/data-agent.md -->
你负责生成 `extraction_result.json`，并为 `chapter-commit` 提供：
- `accepted_events`
- `state_deltas`
- `entity_deltas`
- `summary_text`

你不是写后真理源。
`state.json / index.db / summaries / memory_scratchpad` 的最终写入由 accepted `CHAPTER_COMMIT` 的 projection writers 完成。
```

```md
<!-- webnovel-writer/skills/webnovel-query/SKILL.md -->
查询顺序固定为：
1. `.story-system/MASTER_SETTING.json`
2. `.story-system/volumes/*.json`
3. `.story-system/chapters/*.json`
4. latest accepted `.story-system/commits/chapter_XXX.commit.json`
5. `memory-contract load-context`
6. `.webnovel/state.json` / `index.db`（仅 fallback/read-model）
```

- [ ] **Step 5: 重新跑 prompt integrity**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py -q --no-cov`

Expected: `passed`

- [ ] **Step 6: 提交本任务**

```bash
git add webnovel-writer/skills/webnovel-write/SKILL.md \
        webnovel-writer/skills/webnovel-review/SKILL.md \
        webnovel-writer/skills/webnovel-query/SKILL.md \
        webnovel-writer/skills/webnovel-plan/SKILL.md \
        webnovel-writer/skills/webnovel-dashboard/SKILL.md \
        webnovel-writer/agents/context-agent.md \
        webnovel-writer/agents/data-agent.md \
        webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py
git commit -m "docs: cut skills over to chapter commit mainline"
```

---

## Task 4: 暴露 story runtime health，消灭“看起来切了，实际上没切”

**Files:**
- Create: `webnovel-writer/scripts/data_modules/story_runtime_health.py`
- Create: `webnovel-writer/scripts/data_modules/tests/test_story_runtime_health.py`
- Modify: `webnovel-writer/scripts/data_modules/webnovel.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py`
- Modify: `webnovel-writer/dashboard/app.py`
- Modify: `webnovel-writer/dashboard/frontend/src/api.js`
- Modify: `webnovel-writer/dashboard/frontend/src/App.jsx`

- [ ] **Step 1: 先写 health helper 与 preflight 的失败测试**

```python
# webnovel-writer/scripts/data_modules/tests/test_story_runtime_health.py
from data_modules.story_runtime_health import build_story_runtime_health


def test_story_runtime_health_reports_missing_commit_as_not_ready(tmp_path):
    report = build_story_runtime_health(tmp_path, chapter=3)
    assert report["mainline_ready"] is False
    assert "missing_accepted_commit" in report["fallback_sources"]
```

```python
# webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py
def test_preflight_includes_story_runtime_health(monkeypatch, tmp_path, capsys):
    module = _load_webnovel_module()

    project_root = tmp_path / "book"
    (project_root / ".webnovel").mkdir(parents=True, exist_ok=True)
    (project_root / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["webnovel", "--project-root", str(project_root), "preflight", "--format", "json"])

    with pytest.raises(SystemExit):
        module.main()

    captured = capsys.readouterr()
    assert '"story_runtime"' in captured.out
    assert '"mainline_ready"' in captured.out
```

- [ ] **Step 2: 跑红灯**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_story_runtime_health.py webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py -q --no-cov`

Expected:
- `ModuleNotFoundError: No module named 'data_modules.story_runtime_health'`
- preflight JSON 中不存在 `story_runtime`

- [ ] **Step 3: 实现 health helper，并接到 preflight**

```python
# webnovel-writer/scripts/data_modules/story_runtime_health.py
from __future__ import annotations

from pathlib import Path
from typing import Any

from .story_runtime_sources import load_runtime_sources


def build_story_runtime_health(project_root: Path, chapter: int | None = None) -> dict[str, Any]:
    current_chapter = int(chapter or 0)
    snapshot = load_runtime_sources(project_root, current_chapter) if current_chapter else None
    fallback_sources = list((snapshot.fallback_sources if snapshot else ["chapter_unspecified"]))
    latest_commit = (snapshot.latest_commit if snapshot else None) or {}
    return {
        "chapter": current_chapter,
        "mainline_ready": bool(snapshot and not snapshot.fallback_sources),
        "fallback_sources": fallback_sources,
        "latest_commit_status": (latest_commit.get("meta") or {}).get("status", "missing"),
        "primary_write_source": (snapshot.primary_write_source if snapshot else "chapter_commit"),
    }
```

```python
# webnovel-writer/scripts/data_modules/webnovel.py
from data_modules.story_runtime_health import build_story_runtime_health


def _build_preflight_report(explicit_project_root: Optional[str]) -> dict:
    scripts_dir = _scripts_dir().resolve()
    plugin_root = scripts_dir.parent
    skill_root = plugin_root / "skills" / "webnovel-write"
    entry_script = scripts_dir / "webnovel.py"
    extract_script = scripts_dir / "extract_chapter_context.py"

    checks = [
        {"name": "scripts_dir", "ok": scripts_dir.is_dir(), "path": str(scripts_dir)},
        {"name": "entry_script", "ok": entry_script.is_file(), "path": str(entry_script)},
        {"name": "extract_context_script", "ok": extract_script.is_file(), "path": str(extract_script)},
        {"name": "skill_root", "ok": skill_root.is_dir(), "path": str(skill_root)},
    ]

    project_root = ""
    project_root_error = ""
    try:
        resolved_root = _resolve_root(explicit_project_root)
        project_root = str(resolved_root)
        checks.append({"name": "project_root", "ok": True, "path": project_root})
    except Exception as exc:
        project_root_error = str(exc)
        checks.append({"name": "project_root", "ok": False, "path": explicit_project_root or "", "error": project_root_error})

    story_runtime = build_story_runtime_health(Path(project_root)) if project_root else {}
    return {
        "ok": all(bool(item["ok"]) for item in checks),
        "project_root": project_root,
        "scripts_dir": str(scripts_dir),
        "skill_root": str(skill_root),
        "checks": checks,
        "project_root_error": project_root_error,
        "story_runtime": story_runtime,
    }
```

- [ ] **Step 4: 在 dashboard 暴露 story runtime health 与 latest commit 状态**

```python
# webnovel-writer/dashboard/app.py
from data_modules.story_runtime_health import build_story_runtime_health


@app.get("/api/story-runtime/health")
def story_runtime_health():
    project_root = _get_project_root()
    state_path = project_root / ".webnovel" / "state.json"
    chapter = 0
    if state_path.is_file():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        chapter = int(((state.get("progress") or {}).get("current_chapter") or 0))
    return build_story_runtime_health(project_root, chapter=chapter)
```

```jsx
// webnovel-writer/dashboard/frontend/src/App.jsx
const [runtimeHealth, setRuntimeHealth] = useState(null)

useEffect(() => {
  fetchJSON('/api/story-runtime/health').then(setRuntimeHealth).catch(() => setRuntimeHealth(null))
}, [refreshKey])

{runtimeHealth ? (
  <div className="card stat-card">
    <span className="stat-label">Story Runtime</span>
    <span className="stat-value plain">{runtimeHealth.mainline_ready ? 'Mainline' : 'Fallback'}</span>
    <span className="stat-sub">
      {runtimeHealth.latest_commit_status} · {(runtimeHealth.fallback_sources || []).join(', ') || 'no fallback'}
    </span>
  </div>
) : null}
```

- [ ] **Step 5: 跑后端测试和前端构建**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_story_runtime_health.py webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py -q --no-cov`

Expected: `passed`

Run: `npm --prefix webnovel-writer/dashboard/frontend run build`

Expected: Vite build success，无新增 lint/blocking error

- [ ] **Step 6: 提交本任务**

```bash
git add webnovel-writer/scripts/data_modules/story_runtime_health.py \
        webnovel-writer/scripts/data_modules/webnovel.py \
        webnovel-writer/scripts/data_modules/tests/test_story_runtime_health.py \
        webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py \
        webnovel-writer/dashboard/app.py \
        webnovel-writer/dashboard/frontend/src/api.js \
        webnovel-writer/dashboard/frontend/src/App.jsx
git commit -m "feat: surface story runtime health in preflight and dashboard"
```

---

## Task 5: 封板 legacy fallback 文档与运行说明

**Files:**
- Create: `docs/architecture/story-system-phase5.md`
- Modify: `webnovel-writer/references/genre-profiles.md`
- Modify: `README.md`
- Modify: `docs/architecture/overview.md`
- Modify: `docs/guides/commands.md`
- Modify: `docs/operations/operations.md`
- Modify: `docs/superpowers/README.md`

- [ ] **Step 1: 先补 architecture 文档骨架，明确主链已切换**

````md
<!-- docs/architecture/story-system-phase5.md -->
# Story System Phase 5

## 核心结论

- 写前真源：`MASTER / VOLUME / CHAPTER / REVIEW`
- 写后真源：accepted `CHAPTER_COMMIT`
- `state / index / summary / memory`：投影/read-model
- `genre-profiles.md`：fallback-only

## 默认链路

```text
story-system --persist/--emit-runtime-contracts
    -> context / query / write / review 读取合同
chapter-commit --chapter N
    -> accepted commit
    -> projection writers
    -> state / index / summaries / memory
```
````

- [ ] **Step 2: 在 `genre-profiles.md` 文件头显式打上 fallback-only 标记**

```md
<!-- webnovel-writer/references/genre-profiles.md -->
# genre-profiles

> **状态：Fallback Only**
> 高频题材的主判定、主调性、主禁忌已迁移到 Story Contract / CSV route seed。
> 本文件只在合同缺失、项目未升级或显式 fallback 时提供补充提示。
```

- [ ] **Step 3: 更新 README / commands / operations，把主链写成可执行手册**

```md
<!-- docs/guides/commands.md -->
## Story System 主链

1. 生成合同：
   `python -X utf8 "webnovel-writer/scripts/webnovel.py" --project-root "{WORKSPACE_ROOT}" story-system "{goal}" --chapter {N} --persist --emit-runtime-contracts --format both`
2. 提交章节：
   `python -X utf8 "webnovel-writer/scripts/webnovel.py" --project-root "{PROJECT_ROOT}" chapter-commit --chapter {N} --review-result ".webnovel/tmp/review_results.json" --fulfillment-result ".webnovel/tmp/fulfillment_result.json" --disambiguation-result ".webnovel/tmp/disambiguation_result.json" --extraction-result ".webnovel/tmp/extraction_result.json"`
3. 检查健康：
   `python -X utf8 "webnovel-writer/scripts/webnovel.py" --project-root "{PROJECT_ROOT}" preflight --format json`
```

- [ ] **Step 4: 做一次最终回归**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py webnovel-writer/scripts/data_modules/tests/test_context_manager.py webnovel-writer/scripts/data_modules/tests/test_memory_contract_adapter.py -q --no-cov`

Expected: 全部通过

- [ ] **Step 5: 提交本任务**

```bash
git add docs/architecture/story-system-phase5.md \
        webnovel-writer/references/genre-profiles.md \
        README.md \
        docs/architecture/overview.md \
        docs/guides/commands.md \
        docs/operations/operations.md \
        docs/superpowers/README.md
git commit -m "docs: finalize phase5 legacy downgrade"
```

---

## Self-Review

### Spec Coverage

- `13.6 Phase 5：旧链路降级`
  - Task 1 负责统一 runtime 来源与 commit provenance
  - Task 2 负责默认主输入与默认写后事实切换
  - Task 3 负责 skills / agents 提示词切链
  - Task 4 负责 preflight / dashboard / health 观测
  - Task 5 负责 fallback-only 文档封板与命令手册

- `7.2 运行时优先级`
  - Task 2 显式把 `story_contracts -> latest accepted commit -> legacy fallback` 固化到入口层

- `7.3 写后真理源`
  - Task 1 与 Task 2 让 `CHAPTER_COMMIT` 成为唯一写后事实入口

- `17.1 文档更新要求`
  - Task 5 覆盖架构文档、命令文档、运维手册与总览文档

### Placeholder Scan

- 全文没有延后实现的占位表述
- 每个任务都给了具体文件、测试、命令和提交信息
- 没有用跨任务引用代替实际步骤

### Type Consistency

本计划统一使用以下命名，不在后续任务中换名：

- `RuntimeSourceSnapshot`
- `load_runtime_sources(project_root, chapter)`
- `build_story_runtime_health(project_root, chapter=None)`
- `latest_accepted_commit`
- `fallback_sources`
- `write_fact_role = "chapter_commit"`

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-13-story-system-phase5-legacy-downgrade.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
