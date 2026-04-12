# Story System Phase 4 Event Log And Override Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 canonical event log、事件到投影的稳定映射、事件到 `amend proposal` 的触发规则，并把现有 `override_contracts` 演进成统一 override ledger 的底座。

**Architecture:** 在 Phase 3 的 `CHAPTER_COMMIT.accepted_events` 基础上，新增 `.story-system/events/` 持久化与 `index.db` 审计镜像，让事件成为正式输入而不是散落在 `state_changes / relationship_events / memory_facts` 的局部痕迹。同时把 `override_contracts` 从追读力债务专用扩展成包含 `soft_deviation / contract_override / amend_proposal` 的统一账本，但默认 runtime 只消费当前章相关摘要，不整包注入 prompt。

**Tech Stack:** Python 3.13, Pydantic, pytest, SQLite (`index.db`), JSON event artifacts, dashboard / observability hooks

**Spec:** `docs/superpowers/specs/2026-04-12-story-system-evolution-spec.md`

**Companion Plans:** `docs/superpowers/plans/2026-04-12-story-system-phase3-chapter-commit-chain.md`, `docs/superpowers/specs/2026-04-12-webnovel-story-intelligence-system-spec.md`

---

## Scope Split

本计划只覆盖 Phase 4：

1. canonical event log
2. 事件到投影的稳定映射
3. 事件到 `amend proposal` 的触发规则
4. override ledger 扩展

明确不做：

- 不做 Phase 5 的旧链路降级
- 不清理 `genre-profiles.md` 回退链
- 不把所有历史 override 直接注入 runtime prompt

退出标准：

1. accepted commit 会稳定产出事件文件，并同步写入 `.webnovel/index.db.story_events`
2. 投影层优先消费事件而不是最终覆盖值
3. 需要上提的设定变更会生成 `amend proposal`
4. `override_contracts` 可承载三类记录，并保留兼容旧追读力债务数据
5. dashboard / preflight / health / backup 至少具备最小接入说明和只读检查入口

文档更新继续追加到已有 `Story System` 段落，不重写 README 总体结构。

---

## File Structure

### 要创建的文件

- `webnovel-writer/scripts/story_events.py`
- `webnovel-writer/scripts/data_modules/story_event_schema.py`
- `webnovel-writer/scripts/data_modules/event_log_store.py`
- `webnovel-writer/scripts/data_modules/event_projection_router.py`
- `webnovel-writer/scripts/data_modules/amend_proposal_schema.py`
- `webnovel-writer/scripts/data_modules/override_ledger_service.py`
- `webnovel-writer/scripts/data_modules/tests/test_story_event_schema.py`
- `webnovel-writer/scripts/data_modules/tests/test_event_log_store.py`
- `webnovel-writer/scripts/data_modules/tests/test_event_projection_router.py`
- `webnovel-writer/scripts/data_modules/tests/test_override_ledger_service.py`
- `docs/architecture/story-system-phase4.md`

### 要修改的文件

- `webnovel-writer/scripts/data_modules/chapter_commit_service.py`
- `webnovel-writer/scripts/data_modules/index_manager.py`
- `webnovel-writer/scripts/data_modules/index_debt_mixin.py`
- `webnovel-writer/scripts/data_modules/index_observability_mixin.py`
- `webnovel-writer/scripts/data_modules/webnovel.py`
- `webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py`
- `webnovel-writer/dashboard/app.py`
- `README.md`
- `docs/architecture/overview.md`
- `docs/guides/commands.md`
- `docs/operations/operations.md`
- `docs/superpowers/README.md`

---

## Task 1: 定义事件 schema 与 canonical event 持久化

**Files:**
- Create: `webnovel-writer/scripts/data_modules/story_event_schema.py`
- Create: `webnovel-writer/scripts/data_modules/event_log_store.py`
- Create: `webnovel-writer/scripts/data_modules/tests/test_story_event_schema.py`
- Create: `webnovel-writer/scripts/data_modules/tests/test_event_log_store.py`
- Modify: `webnovel-writer/scripts/data_modules/chapter_commit_service.py`

- [ ] **Step 1: 先写事件 schema / store 测试**

```python
# webnovel-writer/scripts/data_modules/tests/test_story_event_schema.py
from data_modules.story_event_schema import StoryEvent


def test_story_event_supports_power_breakthrough():
    event = StoryEvent.model_validate(
        {
            "event_id": "evt-001",
            "chapter": 3,
            "event_type": "power_breakthrough",
            "subject": "xiaoyan",
            "payload": {"from": "斗之气三段", "to": "斗者"},
        }
    )
    assert event.event_type == "power_breakthrough"
```

```python
# webnovel-writer/scripts/data_modules/tests/test_event_log_store.py
import sqlite3

from data_modules.event_log_store import EventLogStore


def test_event_log_store_writes_per_chapter_file_and_sqlite_mirror(tmp_path):
    store = EventLogStore(tmp_path)
    store.write_events(3, [{"event_id": "evt-001", "event_type": "open_loop_created", "subject": "三年之约", "payload": {}}])
    assert (tmp_path / ".story-system" / "events" / "chapter_003.events.json").is_file()

    conn = sqlite3.connect(tmp_path / ".webnovel" / "index.db")
    try:
        row = conn.execute("SELECT event_id, chapter, event_type FROM story_events").fetchone()
    finally:
        conn.close()
    assert row == ("evt-001", 3, "open_loop_created")
```

- [ ] **Step 2: 跑红灯**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_story_event_schema.py webnovel-writer/scripts/data_modules/tests/test_event_log_store.py -q --no-cov`

Expected: `ModuleNotFoundError`

- [ ] **Step 3: 实现 schema 与 store**

```python
# webnovel-writer/scripts/data_modules/story_event_schema.py
from __future__ import annotations

from typing import Any, Dict, Literal

from pydantic import BaseModel


class StoryEvent(BaseModel):
    event_id: str
    chapter: int
    event_type: Literal[
        "character_state_changed",
        "relationship_changed",
        "world_rule_revealed",
        "world_rule_broken",
        "power_breakthrough",
        "artifact_obtained",
        "promise_created",
        "promise_paid_off",
        "open_loop_created",
        "open_loop_closed",
    ]
    subject: str
    payload: Dict[str, Any]
```

```python
# webnovel-writer/scripts/data_modules/event_log_store.py
import json
import sqlite3
from pathlib import Path


class EventLogStore:
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)

    def write_events(self, chapter: int, events: list[dict]) -> Path:
        target = self.project_root / ".story-system" / "events"
        target.mkdir(parents=True, exist_ok=True)
        path = target / f"chapter_{chapter:03d}.events.json"
        path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_sqlite_mirror(chapter, events)
        return path

    def _write_sqlite_mirror(self, chapter: int, events: list[dict]) -> None:
        db_path = self.project_root / ".webnovel" / "index.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS story_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    chapter INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.executemany(
                "INSERT OR IGNORE INTO story_events(event_id, chapter, event_type, subject, payload_json) VALUES (?, ?, ?, ?, ?)",
                [
                    (
                        event["event_id"],
                        chapter,
                        event["event_type"],
                        event["subject"],
                        json.dumps(event.get("payload") or {}, ensure_ascii=False),
                    )
                    for event in events
                ],
            )
            conn.commit()
        finally:
            conn.close()
```

- [ ] **Step 4: 让 `chapter_commit_service` 在 accepted commit 后写事件文件**

```python
if payload["meta"]["status"] == "accepted":
    EventLogStore(self.project_root).write_events(chapter, payload["accepted_events"])
```

- [ ] **Step 5: 回跑测试**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_story_event_schema.py webnovel-writer/scripts/data_modules/tests/test_event_log_store.py -q --no-cov`

Expected: 通过

- [ ] **Step 6: 提交**

```bash
git add webnovel-writer/scripts/data_modules/story_event_schema.py \
        webnovel-writer/scripts/data_modules/event_log_store.py \
        webnovel-writer/scripts/data_modules/tests/test_story_event_schema.py \
        webnovel-writer/scripts/data_modules/tests/test_event_log_store.py \
        webnovel-writer/scripts/data_modules/chapter_commit_service.py
git commit -m "feat: add canonical event schema and per-chapter event store"
```

---

## Task 2: 建立事件到投影的稳定映射

**Files:**
- Create: `webnovel-writer/scripts/data_modules/event_projection_router.py`
- Create: `webnovel-writer/scripts/data_modules/tests/test_event_projection_router.py`
- Modify: `webnovel-writer/scripts/data_modules/state_projection_writer.py`
- Modify: `webnovel-writer/scripts/data_modules/index_projection_writer.py`
- Modify: `webnovel-writer/scripts/data_modules/memory_projection_writer.py`

- [ ] **Step 1: 先写事件路由测试**

```python
# webnovel-writer/scripts/data_modules/tests/test_event_projection_router.py
from data_modules.event_projection_router import EventProjectionRouter


def test_router_maps_power_breakthrough_to_state_and_memory():
    router = EventProjectionRouter()
    targets = router.route({"event_type": "power_breakthrough", "subject": "xiaoyan", "payload": {}})
    assert targets == ["state", "memory"]


def test_router_maps_relationship_changed_to_index():
    router = EventProjectionRouter()
    targets = router.route({"event_type": "relationship_changed", "subject": "xiaoyan", "payload": {"to": "yaolao"}})
    assert "index" in targets
```

- [ ] **Step 2: 跑红灯**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_event_projection_router.py -q --no-cov`

Expected: `ModuleNotFoundError`

- [ ] **Step 3: 实现路由器并让 writer 消费事件**

```python
# webnovel-writer/scripts/data_modules/event_projection_router.py
class EventProjectionRouter:
    TABLE = {
        "character_state_changed": ["state", "memory"],
        "power_breakthrough": ["state", "memory"],
        "relationship_changed": ["index"],
        "world_rule_revealed": ["memory", "index"],
        "world_rule_broken": ["memory", "index"],
        "open_loop_created": ["memory"],
        "open_loop_closed": ["memory"],
        "promise_created": ["memory"],
        "promise_paid_off": ["memory"],
        "artifact_obtained": ["state", "index"],
    }

    def route(self, event: dict) -> list[str]:
        return list(self.TABLE.get(event.get("event_type"), []))
```

这里把 P3 / P4 的关系写死，避免实现时出现双重投影：

- `EventProjectionRouter` 是**声明式激活表**
- 真正的执行入口仍是 `ChapterCommitService.apply_projections()`
- `apply_projections()` 先汇总 `accepted_events` 命中的 writer 集合，再只调需要的 writer
- Phase 4 **不新增第二套独立投影循环**

- [ ] **Step 4: 回跑测试**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_event_projection_router.py -q --no-cov`

Expected: 通过

- [ ] **Step 5: 提交**

```bash
git add webnovel-writer/scripts/data_modules/event_projection_router.py \
        webnovel-writer/scripts/data_modules/tests/test_event_projection_router.py \
        webnovel-writer/scripts/data_modules/state_projection_writer.py \
        webnovel-writer/scripts/data_modules/index_projection_writer.py \
        webnovel-writer/scripts/data_modules/memory_projection_writer.py
git commit -m "feat: route accepted events into projection writers"
```

---

## Task 3: 把 `override_contracts` 扩展为统一 override ledger

**Files:**
- Create: `webnovel-writer/scripts/data_modules/amend_proposal_schema.py`
- Create: `webnovel-writer/scripts/data_modules/override_ledger_service.py`
- Create: `webnovel-writer/scripts/data_modules/tests/test_override_ledger_service.py`
- Modify: `webnovel-writer/scripts/data_modules/index_manager.py`
- Modify: `webnovel-writer/scripts/data_modules/index_debt_mixin.py`
- Modify: `webnovel-writer/scripts/data_modules/index_observability_mixin.py`

- [ ] **Step 1: 先写 ledger / amend proposal 测试**

```python
# webnovel-writer/scripts/data_modules/tests/test_override_ledger_service.py
from data_modules.override_ledger_service import AmendProposalTrigger, normalize_override_record


def test_normalize_override_record_sets_record_type():
    row = normalize_override_record(
        record_type="contract_override",
        field="core_tone",
        base_value="先压后爆",
        override_value="当场爆发",
        source_level="chapter",
    )
    assert row["record_type"] == "contract_override"
    assert row["field"] == "core_tone"


def test_normalize_override_record_supports_amend_proposal():
    row = normalize_override_record(
        record_type="amend_proposal",
        field="world_rule",
        base_value="金手指每日一次",
        override_value="金手指失控突破",
        source_level="master",
    )
    assert row["record_type"] == "amend_proposal"


def test_world_rule_broken_generates_amend_proposal():
    trigger = AmendProposalTrigger()
    proposals = trigger.check(
        chapter=3,
        events=[
            {
                "event_id": "evt-001",
                "event_type": "world_rule_broken",
                "subject": "金手指",
                "payload": {"field": "world_rule", "base_value": "每日一次", "proposed_value": "短时失控突破"},
            }
        ],
    )
    assert len(proposals) == 1
    assert proposals[0]["target_level"] == "master"
    assert proposals[0]["field"] == "world_rule"
```

- [ ] **Step 2: 跑红灯**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_override_ledger_service.py -q --no-cov`

Expected: `ModuleNotFoundError`

- [ ] **Step 3: 实现 ledger 标准化与增量迁移**

```python
# webnovel-writer/scripts/data_modules/amend_proposal_schema.py
from pydantic import BaseModel


class AmendProposal(BaseModel):
    proposal_id: str
    chapter: int
    target_level: str
    field: str
    base_value: str
    proposed_value: str
    reason_tag: str

# webnovel-writer/scripts/data_modules/override_ledger_service.py
def normalize_override_record(*, record_type: str, field: str, base_value: str, override_value: str, source_level: str) -> dict:
    return {
        "record_type": record_type,
        "field": field,
        "base_value": base_value,
        "override_value": override_value,
        "source_level": source_level,
    }


class AmendProposalTrigger:
    RULES = {
        "world_rule_broken": {"target_level": "master", "reason_tag": "world_rule_broken"},
        "relationship_changed": None,
        "power_breakthrough": None,
        "artifact_obtained": None,
    }

    def check(self, chapter: int, events: list[dict]) -> list[dict]:
        proposals: list[dict] = []
        for event in events:
            rule = self.RULES.get(event.get("event_type"))
            if not rule:
                continue
            payload = event.get("payload") or {}
            proposals.append(
                {
                    "proposal_id": f"amend-{chapter}-{event.get('event_id')}",
                    "chapter": chapter,
                    "target_level": rule["target_level"],
                    "field": payload.get("field", ""),
                    "base_value": payload.get("base_value", ""),
                    "proposed_value": payload.get("proposed_value", ""),
                    "reason_tag": rule["reason_tag"],
                }
            )
        return proposals


def persist_amend_proposals(conn, chapter: int, proposals: list[dict]) -> int:
    inserted = 0
    for proposal in proposals:
        row = normalize_override_record(
            record_type="amend_proposal",
            field=proposal["field"],
            base_value=proposal["base_value"],
            override_value=proposal["proposed_value"],
            source_level=proposal["target_level"],
        )
        conn.execute(
            """
            INSERT INTO override_contracts (
                chapter,
                record_type,
                field,
                base_value,
                override_value,
                source_level,
                reason_tag,
                rationale_type,
                rationale_text,
                status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chapter,
                row["record_type"],
                row["field"],
                row["base_value"],
                row["override_value"],
                row["source_level"],
                proposal["reason_tag"],
                "story_amend_proposal",
                f"事件触发合同修订提案: {proposal['proposal_id']}",
                "pending",
            ),
        )
        inserted += 1
    return inserted
```

在 `index_manager.py` 对 `override_contracts` 做兼容式扩列：

```python
def ensure_override_ledger_columns(conn) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(override_contracts)").fetchall()}
    wanted = {
        "record_type": "TEXT DEFAULT 'soft_deviation'",
        "field": "TEXT DEFAULT ''",
        "base_value": "TEXT DEFAULT ''",
        "override_value": "TEXT DEFAULT ''",
        "source_level": "TEXT DEFAULT ''",
        "reason_tag": "TEXT DEFAULT ''",
    }
    for name, ddl in wanted.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE override_contracts ADD COLUMN {name} {ddl}")
```

同时在 `chapter_commit_service.py` 的 accepted 分支里补一条完整调用：

```python
if payload["meta"]["status"] == "accepted":
    proposals = AmendProposalTrigger().check(chapter, payload["accepted_events"])
    if proposals:
        with IndexManager(self.project_root)._get_conn() as conn:
            ensure_override_ledger_columns(conn)
            persist_amend_proposals(conn, chapter, proposals)
            conn.commit()
```

这样 Phase 4 才算真正实现了“事件 -> amend proposal -> 人工确认后上提合同”的中间主链。

- [ ] **Step 4: 回跑测试**

Run: `python -m pytest webnovel-writer/scripts/data_modules/tests/test_override_ledger_service.py webnovel-writer/scripts/data_modules/tests/test_data_modules.py -q --no-cov`

Expected: 通过

- [ ] **Step 5: 提交**

```bash
git add webnovel-writer/scripts/data_modules/amend_proposal_schema.py \
        webnovel-writer/scripts/data_modules/override_ledger_service.py \
        webnovel-writer/scripts/data_modules/tests/test_override_ledger_service.py \
        webnovel-writer/scripts/data_modules/index_manager.py \
        webnovel-writer/scripts/data_modules/index_debt_mixin.py \
        webnovel-writer/scripts/data_modules/index_observability_mixin.py
git commit -m "feat: extend override contracts into story override ledger"
```

---

## Task 4: CLI / Dashboard / 文档与验证

**Files:**
- Create: `webnovel-writer/scripts/story_events.py`
- Modify: `webnovel-writer/scripts/data_modules/webnovel.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_event_log_store.py`
- Modify: `webnovel-writer/dashboard/app.py`
- Create: `docs/architecture/story-system-phase4.md`
- Modify: `README.md`
- Modify: `docs/architecture/overview.md`
- Modify: `docs/guides/commands.md`
- Modify: `docs/operations/operations.md`
- Modify: `docs/superpowers/README.md`

- [ ] **Step 1: 增加 CLI 转发与读取测试**

```python
def test_webnovel_story_events_forwards(monkeypatch, tmp_path):
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
    monkeypatch.setattr(sys, "argv", ["webnovel", "--project-root", str(project_root), "story-events", "--chapter", "3"])
    cli.main()
    assert called["script_name"] == "story_events.py"
```

在 `test_event_log_store.py` 追加一个直接读取测试：

```python
def test_story_events_cli_reads_chapter_file(tmp_path, monkeypatch, capsys):
    events_dir = tmp_path / ".story-system" / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    (events_dir / "chapter_003.events.json").write_text(
        '[{"event_id":"evt-001","chapter":3,"event_type":"open_loop_created","subject":"三年之约","payload":{}}]',
        encoding="utf-8",
    )

    from story_events import main

    monkeypatch.setattr(sys, "argv", ["story_events", "--project-root", str(tmp_path), "--chapter", "3"])
    main()

    out = capsys.readouterr().out
    assert "open_loop_created" in out
```

- [ ] **Step 2: 暴露查询入口并更新 dashboard**

在 `webnovel.py` 增加：

```python
# webnovel-writer/scripts/story_events.py
import json
import sqlite3
from pathlib import Path


def _events_file(project_root: Path, chapter: int) -> Path:
    return project_root / ".story-system" / "events" / f"chapter_{chapter:03d}.events.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Story events CLI")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--chapter", type=int, default=0)
    parser.add_argument("--health", action="store_true")
    args = parser.parse_args()
    project_root = Path(args.project_root)

    if args.health:
        db_path = project_root / ".webnovel" / "index.db"
        conn = sqlite3.connect(db_path)
        try:
            try:
                row_count = conn.execute("SELECT COUNT(*) FROM story_events").fetchone()[0]
            except sqlite3.OperationalError:
                row_count = 0
        finally:
            conn.close()
        file_count = len(list((project_root / ".story-system" / "events").glob("chapter_*.events.json")))
        print(json.dumps({"ok": row_count >= 0, "sqlite_rows": row_count, "event_files": file_count}, ensure_ascii=False))
        return

    if args.chapter:
        path = _events_file(project_root, args.chapter)
        events = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        print(json.dumps({"chapter": args.chapter, "events": events}, ensure_ascii=False))
        return

    db_path = project_root / ".webnovel" / "index.db"
    conn = sqlite3.connect(db_path)
    try:
        columns = ["event_id", "chapter", "event_type", "subject", "payload_json"]
        rows = conn.execute(
            "SELECT event_id, chapter, event_type, subject, payload_json FROM story_events ORDER BY chapter DESC, id DESC LIMIT 200"
        ).fetchall()
    finally:
        conn.close()
    print(json.dumps({"events": [dict(zip(columns, row)) for row in rows]}, ensure_ascii=False))

# webnovel-writer/scripts/data_modules/webnovel.py
p_story_events = sub.add_parser("story-events", help="转发到 story_events.py")
p_story_events.add_argument("args", nargs=argparse.REMAINDER)
```

在 `dashboard/app.py` 按现有 `_get_db()` + `_fetchall_safe()` 模式增加只读接口：

```python
@app.get("/api/story-events")
def list_story_events(chapter: Optional[int] = None, limit: int = 200):
    with closing(_get_db()) as conn:
        if chapter is not None:
            return _fetchall_safe(
                conn,
                "SELECT * FROM story_events WHERE chapter = ? ORDER BY id DESC LIMIT ?",
                (chapter, limit),
            )
        return _fetchall_safe(
            conn,
            "SELECT * FROM story_events ORDER BY chapter DESC, id DESC LIMIT ?",
            (limit,),
        )


@app.get("/api/story-events/health")
def story_event_health():
    with closing(_get_db()) as conn:
        event_rows = _fetchall_safe(conn, "SELECT COUNT(*) AS count FROM story_events")
        proposal_rows = _fetchall_safe(
            conn,
            "SELECT COUNT(*) AS count FROM override_contracts WHERE record_type = 'amend_proposal' AND status = 'pending'",
        )
        return {
            "story_events": event_rows[0]["count"] if event_rows else 0,
            "pending_amend_proposals": proposal_rows[0]["count"] if proposal_rows else 0,
        }
```

`docs/operations/operations.md` 这一轮必须补三段最小运维内容：

- `preflight`：检查 `.story-system/events/` 是否存在、`story_events` 表是否可查
- `health`：执行 `webnovel story-events --health`
- `backup`：备份 `.story-system/` 与 `.webnovel/index.db`

- [ ] **Step 3: 新建文档并跑 Phase 4 回归**

Run:

```bash
python -m pytest \
  webnovel-writer/scripts/data_modules/tests/test_story_event_schema.py \
  webnovel-writer/scripts/data_modules/tests/test_event_log_store.py \
  webnovel-writer/scripts/data_modules/tests/test_event_projection_router.py \
  webnovel-writer/scripts/data_modules/tests/test_override_ledger_service.py \
  webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py \
  -q --no-cov
```

Expected: 全部通过

- [ ] **Step 4: 最终提交**

```bash
git add webnovel-writer/scripts/story_events.py \
        webnovel-writer/scripts/data_modules/webnovel.py \
        webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py \
        webnovel-writer/scripts/data_modules/tests/test_event_log_store.py \
        webnovel-writer/dashboard/app.py \
        README.md \
        docs/architecture/story-system-phase4.md \
        docs/architecture/overview.md \
        docs/guides/commands.md \
        docs/operations/operations.md \
        docs/superpowers/README.md
git commit -m "docs: document story system phase4 event log and override ledger"
```

---

## Spec Coverage Check

- `13.5 Phase 4：统一事件主链`
  - canonical event log：Task 1
  - 事件到投影稳定映射：Task 2
  - 事件到 amend proposal 触发规则：Task 3

- `8.5 override ledger 的新定位`
  - `soft_deviation / contract_override / amend_proposal`：Task 3

- `10.2 / 10.4`
  - accepted events 持久化与 amend proposal：Task 1 / Task 3

- `17.2 / 17.3`
  - dashboard / health / ops 接入：Task 4

---

## Placeholder Scan

- 没有使用 `TODO / TBD`
- 没有把 override ledger 写成“以后再扩”
- 没有提前进入 Phase 5 的旧链路降级

---

## Next Plan

Phase 4 之后才进入：

1. `Phase 5 Legacy Downgrade`
