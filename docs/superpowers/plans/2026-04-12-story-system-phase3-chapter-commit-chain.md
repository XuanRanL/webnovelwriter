# Story System Phase 3 Chapter Commit Chain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 `CHAPTER_COMMIT` 主链、accepted / rejected 语义与四类 projection writers，让章节事实写后回写统一经过提交对象，而不再散写到 `state / index / summary / memory`。

**Architecture:** 在 Phase 2 的合同优先运行时之上，引入 `CHAPTER_COMMIT.json` 作为写后唯一事实入口。提交阶段先汇总 `review_result / fulfillment_result / disambiguation_result / accepted_events / deltas`，只有 `commit accepted` 才允许投影器分发到下游存储。`state_manager / memory writer / index_manager` 在本阶段重定位为投影写入器底座，而不是章节事实真源。

**Tech Stack:** Python 3.13, Pydantic, argparse, pytest, SQLite (`index.db`), JSON commit artifacts under `.story-system/commits`

**Spec:** `docs/superpowers/specs/2026-04-12-story-system-evolution-spec.md`

**Companion Plans:** `docs/superpowers/plans/2026-04-12-story-system-phase1-contract-seed.md`, `docs/superpowers/plans/2026-04-12-story-system-phase2-contract-first-runtime.md`

---

## Scope Split

本计划只覆盖 Phase 3：

1. `CHAPTER_COMMIT`
2. 四类 projection writers
3. accepted / rejected commit 语义
4. 写后回写改为 commit 驱动

明确不做：

- 不引入 canonical event log 全局主链
- 不把 override ledger 扩展成完整审计账本
- 不做旧链路降级收尾

退出标准：

1. `PROJECT_ROOT/.story-system/commits/chapter_XXX.commit.json` 成为写后事实入口
2. rejected commit 不写下游存储
3. accepted commit 才触发 `state / index / summary / memory` 投影，其中 `StateProjectionWriter` 必须真实更新 `state.json`
4. `projection_status` 可追踪每个 writer 的完成情况；写入失败只记录到对应 writer 状态，不回滚 `commit accepted/rejected` 判定

文档更新继续追加到已有 `Story System` 段落，不重写 README 总体结构。

---

## File Structure

### 要创建的文件

- `webnovel-writer/scripts/chapter_commit.py`
- `webnovel-writer/scripts/data_modules/story_commit_schema.py`
- `webnovel-writer/scripts/data_modules/chapter_commit_service.py`
- `webnovel-writer/scripts/data_modules/state_projection_writer.py`
- `webnovel-writer/scripts/data_modules/index_projection_writer.py`
- `webnovel-writer/scripts/data_modules/summary_projection_writer.py`
- `webnovel-writer/scripts/data_modules/memory_projection_writer.py`
- `webnovel-writer/scripts/data_modules/tests/test_story_commit_schema.py`
- `webnovel-writer/scripts/data_modules/tests/test_chapter_commit_service.py`
- `webnovel-writer/scripts/data_modules/tests/test_projection_writers.py`
- `docs/architecture/story-system-phase3.md`

### 要修改的文件

- `webnovel-writer/scripts/data_modules/story_contracts.py`
- `webnovel-writer/scripts/data_modules/webnovel.py`
- `webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py`
- `webnovel-writer/scripts/review_pipeline.py`
- `webnovel-writer/scripts/data_modules/state_manager.py`
- `webnovel-writer/scripts/data_modules/memory/writer.py`
- `webnovel-writer/skills/webnovel-write/SKILL.md`
- `webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py`
- `README.md`
- `docs/architecture/overview.md`
- `docs/guides/commands.md`
- `docs/superpowers/README.md`

---

## Task 1: 定义 `CHAPTER_COMMIT` schema 与落盘路径

**Files:**
- Create: `webnovel-writer/scripts/data_modules/story_commit_schema.py`
- Create: `webnovel-writer/scripts/data_modules/tests/test_story_commit_schema.py`
- Modify: `webnovel-writer/scripts/data_modules/story_contracts.py`

- [ ] **Step 1: 先写 schema 测试**

```python
# webnovel-writer/scripts/data_modules/tests/test_story_commit_schema.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from data_modules.story_commit_schema import ChapterCommit


def test_chapter_commit_accepts_required_sections():
    payload = {
        "meta": {"schema_version": "story-system/v1", "chapter": 3, "status": "accepted"},
        "contract_refs": {"master": "MASTER_SETTING.json", "chapter": "chapter_003.json"},
        "outline_snapshot": {"planned_nodes": ["发现陷阱"]},
        "review_result": {"blocking_count": 0},
        "fulfillment_result": {"missed_nodes": []},
        "disambiguation_result": {"pending": []},
        "accepted_events": [],
        "state_deltas": [],
        "entity_deltas": [],
        "projection_status": {"state": "pending", "index": "pending", "summary": "pending", "memory": "pending"},
    }
    model = ChapterCommit.model_validate(payload)
    assert model.meta["status"] == "accepted"
```

- [ ] **Step 2: 跑红灯**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_story_commit_schema.py -q --no-cov`

Expected: `ModuleNotFoundError: No module named 'data_modules.story_commit_schema'`

- [ ] **Step 3: 实现 schema 与 commit 路径**

```python
# webnovel-writer/scripts/data_modules/story_commit_schema.py
from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class ChapterCommit(BaseModel):
    meta: Dict[str, Any]
    contract_refs: Dict[str, str]
    outline_snapshot: Dict[str, Any]
    review_result: Dict[str, Any]
    fulfillment_result: Dict[str, Any]
    disambiguation_result: Dict[str, Any]
    accepted_events: List[Dict[str, Any]] = Field(default_factory=list)
    state_deltas: List[Dict[str, Any]] = Field(default_factory=list)
    entity_deltas: List[Dict[str, Any]] = Field(default_factory=list)
    projection_status: Dict[str, str]
```

```python
# webnovel-writer/scripts/data_modules/story_contracts.py
@property
def commits_dir(self) -> Path:
    return self.root / "commits"

def commit_json(self, chapter: int) -> Path:
    return self.commits_dir / f"chapter_{chapter:03d}.commit.json"
```

- [ ] **Step 4: 回跑测试**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_story_commit_schema.py -q --no-cov`

Expected: 通过

- [ ] **Step 5: 提交**

```bash
git add webnovel-writer/scripts/data_modules/story_commit_schema.py \
        webnovel-writer/scripts/data_modules/story_contracts.py \
        webnovel-writer/scripts/data_modules/tests/test_story_commit_schema.py
git commit -m "feat: add chapter commit schema and paths"
```

---

## Task 2: 实现 `chapter_commit_service` 与提交校验

**Files:**
- Create: `webnovel-writer/scripts/data_modules/chapter_commit_service.py`
- Create: `webnovel-writer/scripts/data_modules/tests/test_chapter_commit_service.py`
- Modify: `webnovel-writer/scripts/review_pipeline.py`

- [ ] **Step 1: 先写提交通过/阻断测试**

```python
# webnovel-writer/scripts/data_modules/tests/test_chapter_commit_service.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from data_modules.chapter_commit_service import ChapterCommitService


def test_commit_service_rejects_when_missed_nodes_exist(tmp_path):
    service = ChapterCommitService(tmp_path)
    payload = service.build_commit(
        chapter=3,
        review_result={"blocking_count": 0},
        fulfillment_result={"planned_nodes": ["发现陷阱"], "missed_nodes": ["发现陷阱"]},
        disambiguation_result={"pending": []},
        extraction_result={"state_deltas": [], "entity_deltas": [], "accepted_events": []},
    )
    assert payload["meta"]["status"] == "rejected"


def test_commit_service_accepts_when_all_checks_pass(tmp_path):
    service = ChapterCommitService(tmp_path)
    payload = service.build_commit(
        chapter=3,
        review_result={"blocking_count": 0},
        fulfillment_result={"planned_nodes": ["发现陷阱"], "covered_nodes": ["发现陷阱"], "missed_nodes": [], "extra_nodes": []},
        disambiguation_result={"pending": []},
        extraction_result={"state_deltas": [], "entity_deltas": [], "accepted_events": []},
    )
    assert payload["meta"]["status"] == "accepted"
    assert payload["contract_refs"]["master"] == "MASTER_SETTING.json"
    assert payload["contract_refs"]["chapter"] == "chapter_003.json"
    assert payload["outline_snapshot"]["covered_nodes"] == ["发现陷阱"]
```

- [ ] **Step 2: 跑红灯**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_chapter_commit_service.py -q --no-cov`

Expected: `ModuleNotFoundError: No module named 'data_modules.chapter_commit_service'`

- [ ] **Step 3: 实现提交服务**

```python
# webnovel-writer/scripts/data_modules/chapter_commit_service.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from data_modules.index_projection_writer import IndexProjectionWriter
from data_modules.memory_projection_writer import MemoryProjectionWriter
from data_modules.state_projection_writer import StateProjectionWriter
from data_modules.summary_projection_writer import SummaryProjectionWriter


class ChapterCommitService:
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)

    def build_commit(
        self,
        chapter: int,
        review_result: Dict[str, Any],
        fulfillment_result: Dict[str, Any],
        disambiguation_result: Dict[str, Any],
        extraction_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        rejected = bool(review_result.get("blocking_count")) or bool(fulfillment_result.get("missed_nodes")) or bool(disambiguation_result.get("pending"))
        status = "rejected" if rejected else "accepted"
        return {
            "meta": {"schema_version": "story-system/v1", "chapter": chapter, "status": status},
            "contract_refs": {
                "master": "MASTER_SETTING.json",
                "chapter": f"chapter_{chapter:03d}.json",
                "review": f"chapter_{chapter:03d}.review.json",
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
            "projection_status": {"state": "pending", "index": "pending", "summary": "pending", "memory": "pending"},
        }

    def persist_commit(self, payload: Dict[str, Any]) -> Path:
        target = self.project_root / ".story-system" / "commits"
        target.mkdir(parents=True, exist_ok=True)
        path = target / f"chapter_{int(payload['meta']['chapter']):03d}.commit.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def apply_projections(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if payload["meta"]["status"] != "accepted":
            return payload

        writers = {
            "state": StateProjectionWriter(self.project_root),
            "index": IndexProjectionWriter(self.project_root),
            "summary": SummaryProjectionWriter(self.project_root),
            "memory": MemoryProjectionWriter(self.project_root),
        }
        for name, writer in writers.items():
            try:
                result = writer.apply(payload)
                payload["projection_status"][name] = "done" if result.get("applied") else "skipped"
            except Exception as exc:
                payload["projection_status"][name] = f"failed:{exc}"
        self.persist_commit(payload)
        return payload
```

这里补一条 Phase 3 / Phase 4 的职责协议，后续实现必须遵守：

- `ChapterCommitService.apply_projections()` 始终是唯一调度入口
- Phase 4 引入的 `EventProjectionRouter` 只负责判定“哪些 writer 应被激活”
- `EventProjectionRouter` **不单独再跑一轮投影**，避免 `state_deltas` 与 `accepted_events` 双重落库

`review_pipeline.py` 在本 Task 必须补一条明确接线：

- 汇总 `review_result / fulfillment_result / disambiguation_result / extraction_result`
- 调 `ChapterCommitService.build_commit()`
- 先 `persist_commit()`，再依据 `payload["meta"]["status"]` 决定是否进入投影阶段

也就是说，`review_pipeline.py` 不再只是“被列进修改文件”，而是 Phase 3 写后主链真正的调用入口。

- [ ] **Step 4: 回跑测试**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_chapter_commit_service.py -q --no-cov`

Expected: 通过

- [ ] **Step 5: 提交**

```bash
git add webnovel-writer/scripts/data_modules/chapter_commit_service.py \
        webnovel-writer/scripts/data_modules/tests/test_chapter_commit_service.py \
        webnovel-writer/scripts/review_pipeline.py
git commit -m "feat: add chapter commit service and status semantics"
```

---

## Task 3: 落地四类 projection writers

**Files:**
- Create: `webnovel-writer/scripts/data_modules/state_projection_writer.py`
- Create: `webnovel-writer/scripts/data_modules/index_projection_writer.py`
- Create: `webnovel-writer/scripts/data_modules/summary_projection_writer.py`
- Create: `webnovel-writer/scripts/data_modules/memory_projection_writer.py`
- Create: `webnovel-writer/scripts/data_modules/tests/test_projection_writers.py`
- Modify: `webnovel-writer/scripts/data_modules/index_manager.py`
- Modify: `webnovel-writer/scripts/data_modules/state_manager.py`
- Modify: `webnovel-writer/scripts/data_modules/memory/writer.py`

- [ ] **Step 1: 先写 accepted / rejected 投影测试**

```python
# webnovel-writer/scripts/data_modules/tests/test_projection_writers.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json

from data_modules.chapter_commit_service import ChapterCommitService
from data_modules.state_projection_writer import StateProjectionWriter


def test_state_projection_writer_skips_rejected_commit(tmp_path):
    writer = StateProjectionWriter(tmp_path)
    result = writer.apply({"meta": {"status": "rejected"}, "state_deltas": []})
    assert result["applied"] is False


def test_state_projection_writer_applies_accepted_commit(tmp_path):
    (tmp_path / ".webnovel").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")
    writer = StateProjectionWriter(tmp_path)
    result = writer.apply({"meta": {"status": "accepted"}, "state_deltas": [{"entity_id": "x", "field": "realm", "new": "斗者"}]})
    assert result["applied"] is True
    payload = json.loads((tmp_path / ".webnovel" / "state.json").read_text(encoding="utf-8"))
    assert payload["entity_state"]["x"]["realm"] == "斗者"


def test_accepted_commit_updates_state_json_end_to_end(tmp_path):
    (tmp_path / ".webnovel").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")

    service = ChapterCommitService(tmp_path)
    commit_payload = service.build_commit(
        chapter=3,
        review_result={"blocking_count": 0},
        fulfillment_result={"planned_nodes": ["发现陷阱"], "covered_nodes": ["发现陷阱"], "missed_nodes": [], "extra_nodes": []},
        disambiguation_result={"pending": []},
        extraction_result={"state_deltas": [{"entity_id": "x", "field": "realm", "new": "斗者"}], "entity_deltas": [], "accepted_events": []},
    )

    StateProjectionWriter(tmp_path).apply(commit_payload)
    payload = json.loads((tmp_path / ".webnovel" / "state.json").read_text(encoding="utf-8"))
    assert payload["entity_state"]["x"]["realm"] == "斗者"
```

- [ ] **Step 2: 跑红灯**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_projection_writers.py -q --no-cov`

Expected: `ModuleNotFoundError` for projection writer modules

- [ ] **Step 3: 实现四类 writer**

```python
# webnovel-writer/scripts/data_modules/state_projection_writer.py
from data_modules.story_contracts import read_json_if_exists


class StateProjectionWriter:
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)

    def apply(self, commit_payload: dict) -> dict:
        if commit_payload["meta"]["status"] != "accepted":
            return {"applied": False, "writer": "state", "reason": "commit_rejected"}

        state_path = self.project_root / ".webnovel" / "state.json"
        state = read_json_if_exists(state_path) or {}
        entity_state = state.setdefault("entity_state", {})
        applied_count = 0
        for delta in commit_payload.get("state_deltas", []):
            entity_id = str(delta.get("entity_id") or "").strip()
            field = str(delta.get("field") or "").strip()
            if not entity_id or not field:
                continue
            entity_state.setdefault(entity_id, {})[field] = delta.get("new")
            applied_count += 1

        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"applied": applied_count > 0, "writer": "state", "applied_count": applied_count}
```

其他三个 writer 在 Phase 3 可以先保持“最小投影”，但**不能是 no-op stub**，至少要薄适配到现有底座：

```python
class IndexProjectionWriter:
    def apply(self, commit_payload: dict) -> dict:
        if commit_payload["meta"]["status"] != "accepted":
            return {"applied": False, "writer": "index", "reason": "commit_rejected"}
        manager = IndexManager(self.project_root)
        for delta in commit_payload.get("entity_deltas", []):
            manager.apply_entity_delta(delta)
        return {"applied": True, "writer": "index", "applied_count": len(commit_payload.get("entity_deltas", []))}


class SummaryProjectionWriter:
    def apply(self, commit_payload: dict) -> dict:
        if commit_payload["meta"]["status"] != "accepted":
            return {"applied": False, "writer": "summary", "reason": "commit_rejected"}
        return append_summary_projection(self.project_root, commit_payload)


class MemoryProjectionWriter:
    def apply(self, commit_payload: dict) -> dict:
        if commit_payload["meta"]["status"] != "accepted":
            return {"applied": False, "writer": "memory", "reason": "commit_rejected"}
        return MemoryWriter(self.project_root).apply_commit_projection(commit_payload)
```

这里的交付要求写死：

- `StateProjectionWriter` 必须真实落地
- `Index / Summary / Memory` 允许是薄适配，但必须调用真实底座或真实文件写入
- 如果仓库当前不存在 `IndexManager.apply_entity_delta()`、`append_summary_projection()`、`MemoryWriter.apply_commit_projection()`，就在本 Task 一并补最小适配器骨架；函数名可调整，但 writer 层对外协议不变
- `projection_status` 记录 `"done"` / `"skipped"` / `"failed:..."`，不能一律回 `"pending"`

- [ ] **Step 4: 回跑测试**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_projection_writers.py -q --no-cov`

Expected: 通过

- [ ] **Step 5: 提交**

```bash
git add webnovel-writer/scripts/data_modules/state_projection_writer.py \
        webnovel-writer/scripts/data_modules/index_projection_writer.py \
        webnovel-writer/scripts/data_modules/summary_projection_writer.py \
        webnovel-writer/scripts/data_modules/memory_projection_writer.py \
        webnovel-writer/scripts/data_modules/tests/test_projection_writers.py \
        webnovel-writer/scripts/data_modules/state_manager.py \
        webnovel-writer/scripts/data_modules/memory/writer.py
git commit -m "feat: add commit-driven projection writers"
```

---

## Task 4: CLI / Skill 接入、文档与验证

**Files:**
- Create: `webnovel-writer/scripts/chapter_commit.py`
- Modify: `webnovel-writer/scripts/data_modules/webnovel.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_chapter_commit_service.py`
- Modify: `webnovel-writer/skills/webnovel-write/SKILL.md`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py`
- Create: `docs/architecture/story-system-phase3.md`
- Modify: `README.md`
- Modify: `docs/architecture/overview.md`
- Modify: `docs/guides/commands.md`
- Modify: `docs/superpowers/README.md`

- [ ] **Step 1: 增加统一 CLI 转发测试**

```python
def test_webnovel_commit_forwards(monkeypatch, tmp_path):
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
    monkeypatch.setattr(sys, "argv", ["webnovel", "--project-root", str(project_root), "chapter-commit", "--chapter", "3"])
    cli.main()

    assert called["script_name"] == "chapter_commit.py"


def test_chapter_commit_cli_builds_and_persists_commit(tmp_path, monkeypatch):
    review_path = tmp_path / "review.json"
    fulfillment_path = tmp_path / "fulfillment.json"
    disambiguation_path = tmp_path / "disambiguation.json"
    extraction_path = tmp_path / "extraction.json"
    review_path.write_text('{"blocking_count": 0}', encoding="utf-8")
    fulfillment_path.write_text('{"planned_nodes": ["发现陷阱"], "covered_nodes": ["发现陷阱"], "missed_nodes": [], "extra_nodes": []}', encoding="utf-8")
    disambiguation_path.write_text('{"pending": []}', encoding="utf-8")
    extraction_path.write_text('{"state_deltas": [], "entity_deltas": [], "accepted_events": []}', encoding="utf-8")

    from chapter_commit import main

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chapter_commit",
            "--project-root",
            str(tmp_path),
            "--chapter",
            "3",
            "--review-result",
            str(review_path),
            "--fulfillment-result",
            str(fulfillment_path),
            "--disambiguation-result",
            str(disambiguation_path),
            "--extraction-result",
            str(extraction_path),
        ],
    )
    main()

    assert (tmp_path / ".story-system" / "commits" / "chapter_003.commit.json").is_file()
```

- [ ] **Step 2: 接入 CLI 与技能**

在 `webnovel.py` 增加：

```python
# webnovel-writer/scripts/chapter_commit.py
def _read_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Chapter commit CLI")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--chapter", type=int, required=True)
    parser.add_argument("--review-result", required=True)
    parser.add_argument("--fulfillment-result", required=True)
    parser.add_argument("--disambiguation-result", required=True)
    parser.add_argument("--extraction-result", required=True)
    args = parser.parse_args()

    service = ChapterCommitService(Path(args.project_root))
    payload = service.build_commit(
        chapter=args.chapter,
        review_result=_read_json(args.review_result),
        fulfillment_result=_read_json(args.fulfillment_result),
        disambiguation_result=_read_json(args.disambiguation_result),
        extraction_result=_read_json(args.extraction_result),
    )
    service.persist_commit(payload)
    if payload["meta"]["status"] == "accepted":
        payload = service.apply_projections(payload)
    print(json.dumps(payload, ensure_ascii=False))

# webnovel-writer/scripts/data_modules/webnovel.py
p_commit = sub.add_parser("chapter-commit", help="转发到 chapter_commit.py")
p_commit.add_argument("args", nargs=argparse.REMAINDER)
```

在 `skills/webnovel-write/SKILL.md` 将原先“写完直接 state / index / summaries / memory 回写”替换为：

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" \
  chapter-commit --chapter {chapter_num} \
  --review-result "{review_json}" \
  --fulfillment-result "{fulfillment_json}" \
  --disambiguation-result "{disambiguation_json}" \
  --extraction-result "{extraction_json}"
```

同时在文档里明确一个运行约束：

- `chapter_commit.py` 是独立人工/CLI 入口
- `review_pipeline.py` 是 skill 主流程中的集成入口
- 同一次写后流程只能走其中一个入口，禁止 `review_pipeline.py` 已提交后再补跑 `chapter_commit.py`

- [ ] **Step 3: 新建 Phase 3 文档并跑回归**

Run:

```bash
python -m pytest \
  webnovel-writer/scripts/data_modules/tests/test_story_commit_schema.py \
  webnovel-writer/scripts/data_modules/tests/test_chapter_commit_service.py \
  webnovel-writer/scripts/data_modules/tests/test_projection_writers.py \
  webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py \
  webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py \
  -q --no-cov
```

Expected: 全部通过

- [ ] **Step 4: 最终提交**

```bash
git add webnovel-writer/scripts/chapter_commit.py \
        webnovel-writer/scripts/data_modules/webnovel.py \
        webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py \
        webnovel-writer/scripts/data_modules/tests/test_chapter_commit_service.py \
        webnovel-writer/skills/webnovel-write/SKILL.md \
        webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py \
        README.md \
        docs/architecture/story-system-phase3.md \
        docs/architecture/overview.md \
        docs/guides/commands.md \
        docs/superpowers/README.md
git commit -m "docs: document story system phase3 chapter commit chain"
```

---

## Spec Coverage Check

- `13.4 Phase 3：章节提交主链`
  - `CHAPTER_COMMIT`：Task 1 / Task 2
  - 四类 projection writers：Task 3
  - accepted / rejected 语义：Task 2 / Task 3
  - 写后回写改为 commit 驱动：Task 3 / Task 4

- `9.2 / 9.3 / 9.5`
  - 最小结构、提交流程、失败语义：Task 1 / Task 2

- `11.2 / 11.3`
  - 履约 / missed nodes 阻断：Task 2

---

## Placeholder Scan

- 没有使用 `TODO / TBD`
- 没有把 projection writer 写成“后续补齐”
- 没有提前把 Phase 4 的 canonical event log 混进本阶段

---

## Next Plan

Phase 3 完成后进入：

1. `Phase 4 Event Log And Override Ledger`
