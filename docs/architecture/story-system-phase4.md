# Story System Phase 4

## 目标

Phase 4 把 Phase 3 的 `accepted_events` 升级为正式事件主链，并把
`override_contracts` 扩成统一 override ledger。

本阶段新增两条稳定链路：

1. `CHAPTER_COMMIT.accepted_events -> .story-system/events/*.events.json`
2. `world_rule_broken -> amend_proposal -> override_contracts`

## 产物

运行后会出现这些核心文件或表：

- `.story-system/events/chapter_XXX.events.json`
- `.webnovel/index.db.story_events`
- `.webnovel/index.db.override_contracts.record_type=*`

`story_events` 是 canonical 审计镜像，`override_contracts` 继续保留旧
Override Contract / 债务链，同时新增：

- `soft_deviation`
- `contract_override`
- `amend_proposal`

## 执行关系

```text
review / fulfillment / disambiguation / extraction
                │
                ▼
         CHAPTER_COMMIT.accepted
                │
                ├── apply_projections()
                │     ├── state/index/summary/memory
                │     └── EventProjectionRouter 决定激活哪些 writer
                │
                ├── EventLogStore.write_events()
                │     ├── JSON 文件
                │     └── SQLite story_events 镜像
                │
                └── AmendProposalTrigger.check()
                      └── persist_amend_proposals() -> override_contracts
```

## CLI

统一入口仍然是 `webnovel.py`：

```bash
python -X utf8 "<CLAUDE_PLUGIN_ROOT>/scripts/webnovel.py" --project-root "<PROJECT_ROOT>" story-system "玄幻退婚流" --persist
python -X utf8 "<CLAUDE_PLUGIN_ROOT>/scripts/webnovel.py" --project-root "<PROJECT_ROOT>" story-system "玄幻退婚流" --emit-runtime-contracts --chapter 12
python -X utf8 "<CLAUDE_PLUGIN_ROOT>/scripts/webnovel.py" --project-root "<PROJECT_ROOT>" chapter-commit --chapter 12 --review-result .webnovel/tmp/review.json --fulfillment-result .webnovel/tmp/fulfillment.json --disambiguation-result .webnovel/tmp/disambiguation.json --extraction-result .webnovel/tmp/extraction.json
python -X utf8 "<CLAUDE_PLUGIN_ROOT>/scripts/webnovel.py" --project-root "<PROJECT_ROOT>" story-events --chapter 12
python -X utf8 "<CLAUDE_PLUGIN_ROOT>/scripts/webnovel.py" --project-root "<PROJECT_ROOT>" story-events --health
```

## 最小运维检查

- `story-system --persist` 后应存在 `MASTER_SETTING.json`
- `story-system --emit-runtime-contracts --chapter N` 后应存在 `volume_XXX.json`
  与 `chapter_XXX.review.json`
- `chapter-commit` accepted 后应存在 `chapter_XXX.commit.json`
- `story-events --health` 应返回 `sqlite_rows` 与 `event_files`

## 当前边界

- 事件路由仍由 `ChapterCommitService.apply_projections()` 统一调度
- Phase 4 不新增第二套独立投影循环
- 旧链路降级与完全切换留到 Phase 5
