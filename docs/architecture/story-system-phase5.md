# Story System Phase 5

## 核心结论

- 写前真源：`.story-system/MASTER_SETTING.json`、`volumes/*.json`、`chapters/*.json`、`reviews/*.review.json`
- 写后真源：accepted `CHAPTER_COMMIT`
- `.webnovel/state.json`、`index.db`、`summaries/`、`memory_scratchpad.json`：投影 / read-model
- `references/genre-profiles.md`：fallback-only

## 默认链路

```text
story-system --persist/--emit-runtime-contracts
    -> 生成 MASTER / VOLUME / CHAPTER / REVIEW 合同
context / query / write / review
    -> 默认读取合同主链
chapter-commit --chapter N
    -> accepted CHAPTER_COMMIT
    -> state / index / summary / memory projection writers
preflight + dashboard
    -> 暴露 story runtime health / fallback 状态 / latest commit 状态
```

## 运行时优先级

1. Story Contracts
2. latest accepted `CHAPTER_COMMIT`
3. `.webnovel/*` read-model
4. `genre-profiles.md` 等 legacy fallback

## Phase 5 落地结果

- `ContextManager`、`memory_contract_adapter`、`extract_chapter_context` 已默认走 contract-first + commit-first
- `webnovel-write` / `webnovel-query` / `webnovel-review` / `webnovel-plan` 与 `context-agent` / `data-agent` 已切到新主链叙述
- `preflight` 与 dashboard 已直接暴露 `story_runtime` / `story-runtime/health`
- 旧 state-first 心智模型降级为兼容层，不再伪装为主链

## 运维含义

- 看到 `.webnovel/state.json` 与 `.story-system/commits/` 不一致时，优先检查 commit 链与 projection 状态
- `fallback_sources` 非空表示主链不完整，系统仍可兼容运行，但不能视为 fully-mainline-ready
- 排查写后问题时，优先检查：
  1. `.story-system/commits/chapter_XXX.commit.json`
  2. `projection_status`
  3. `story-events --health`
  4. `.webnovel/*` 投影结果
