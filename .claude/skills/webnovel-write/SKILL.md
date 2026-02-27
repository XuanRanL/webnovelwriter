---
name: webnovel-write
description: Writes webnovel chapters (3000-5000 words). Use when the user asks to write a chapter or runs /webnovel-write. Runs context, drafting, review, polish, and data extraction.
allowed-tools: Read Write Edit Grep Bash Task
---

# Chapter Writing Skill

## 0. 项目根校验（必须）

- 必须在项目根目录执行（需存在 `.webnovel/state.json`）。
- 若当前目录不存在该文件，先询问用户项目路径并切换目录。
- 进入后设置变量：`$PROJECT_ROOT = (Resolve-Path ".").Path`。

## 0.5 工作流断点（best-effort，不得阻断主流程）

> 目标：让 `/webnovel-resume` 能基于真实断点恢复。即使 workflow_manager 出错，也**只记录警告**，写作继续。

推荐（bash）：
```bash
# 启动任务（失败不阻断）
python "${CLAUDE_PLUGIN_ROOT}/scripts/workflow_manager.py" start-task --command webnovel-write --chapter {chapter_num} || true

# 每个 Step 开始/结束都记录（失败不阻断）
python "${CLAUDE_PLUGIN_ROOT}/scripts/workflow_manager.py" start-step --step-id "Step 1" --step-name "Context Agent" || true
python "${CLAUDE_PLUGIN_ROOT}/scripts/workflow_manager.py" complete-step --step-id "Step 1" --artifacts '{"ok":true}' || true

# 全部结束后完成任务
python "${CLAUDE_PLUGIN_ROOT}/scripts/workflow_manager.py" complete-task --artifacts '{"ok":true}' || true
```

注：`--step-id` 必须严格使用：`Step 1` / `Step 1.5` / `Step 2A` / `Step 2B` / `Step 3` / `Step 4` / `Step 5` / `Step 6`。

## 1. 模式定义

| 模式 | 启用步骤 | 说明 |
|------|---------|------|
| `/webnovel-write` | Step 1 → 1.5 → 2A → 2B → 3 → 4 → 5 → 6 | 标准流程 |
| `/webnovel-write --fast` | Step 1 → 1.5 → 2A → 3 → 4 → 5 → 6 | 跳过 Step 2B |
| `/webnovel-write --minimal` | Step 1 → 1.5 → 2A → 3(仅3个基础审查) → 4 → 5 → 6 | 跳过 Step 2B；不产出追读力数据 |

## References（按步骤导航）

- Step 2A（必读，写作硬约束）：[core-constraints.md](../../references/shared/core-constraints.md)
- Step 4（必读，润色规则）：[polish-guide.md](references/polish-guide.md)
- Step 4（必读，排版规范）：[typesetting.md](references/writing/typesetting.md)
- Step 1.5（可选，题材/风格/钩子细化）：[style-variants.md](references/style-variants.md)
- Step 1.5（可选，题材/风格/钩子细化）：[reading-power-taxonomy.md](../../references/reading-power-taxonomy.md)
- Step 1.5（可选，题材/风格/钩子细化）：[genre-profiles.md](../../references/genre-profiles.md)
- Step 1.5（可选，电竞/直播文/克苏鲁钩子库）：[genre-hook-payoff-library.md](references/writing/genre-hook-payoff-library.md)
- Step 2B（可选，风格适配细则）：[style-adapter.md](references/style-adapter.md)
- Step 3（可选，审查指标 JSON 结构/流程细则）：[workflow-details.md](references/workflow-details.md)

## 2. 引用加载策略（严格按需）

- L0：不提前加载参考。
- L1：执行某个 Step 前，只加载 References 区该 Step 的“必读”条目。
- L2：仅在触发条件满足时加载 References 区该 Step 的“可选”条目。

## 3. 执行步骤

### Step 1：Context Agent（生成创作任务书）

使用 Task 调用 `context-agent`：

```
调用 context-agent，参数：
- chapter: {chapter_num}
- project_root: {PROJECT_ROOT}
- storage_path: .webnovel/
- state_file: .webnovel/state.json
```

要求：

- 大纲或 state 缺失时，明确提示先初始化。
- 任务书必须包含“反派层级”（无则标注“无”）。

### Step 1.5：Contract v2 Guidance 注入

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/extract_chapter_context.py" --chapter {chapter_num} --project-root "{PROJECT_ROOT}" --format json
```

- 必读：`writing_guidance.guidance_items`
- 选读：`reader_signal`、`genre_profile.reference_hints`

### Step 2A：正文起草

- 遵循三原则：大纲即法律 / 设定即物理 / 发明需识别。
- 输出纯正文：`正文/第{NNNN}章.md`
- 开写前加载：

```bash
cat "${CLAUDE_PLUGIN_ROOT}/references/shared/core-constraints.md"
```

### Step 2B：风格适配（`--fast` / `--minimal` 跳过）

- 仅做风格转译，不改剧情事实。
- 执行前加载（按需，若本章需要强网文化/去AI化处理则必读）：

```bash
cat "${CLAUDE_PLUGIN_ROOT}/skills/webnovel-write/references/style-adapter.md"
```

### Step 3：审查

调用约束：

- 必须使用 `Task` 工具调用各审查 subagent，禁止主流程直接内联“自审”替代。
- 可并行发起审查 Task，全部返回后统一汇总 `issues/severity/overall_score`。
- 审查汇总后必须将审查指标写入 `index.db.review_metrics`（包括 `--minimal` 模式）。

默认核心 4 审查器：

- `consistency-checker`
- `continuity-checker`
- `ooc-checker`
- `reader-pull-checker`

关键章/卷末/用户明确要求时追加：

- `high-point-checker`
- `pacing-checker`

`--minimal` 模式仅运行前三个基础审查器，不产出追读力数据。

审查指标落库（必做）：
```bash
python -m data_modules.index_manager save-review-metrics --data '{...}' --project-root "${PROJECT_ROOT}"
```

说明：`--minimal` 可只包含 3 维 `dimension_scores`（设定一致性/人物塑造/连贯性），但必须给出 `overall_score`。JSON 结构见 [workflow-details.md](references/workflow-details.md)。

### Step 4：润色

```bash
cat "${CLAUDE_PLUGIN_ROOT}/skills/webnovel-write/references/polish-guide.md"
cat "${CLAUDE_PLUGIN_ROOT}/skills/webnovel-write/references/writing/typesetting.md"
```

- 先修复 critical/high，再处理 medium/low。
- 这里执行去AI化与毒点规避规则（见 `polish-guide.md`）。

### Step 5：Data Agent

使用 Task 调用 `data-agent`：

```
调用 data-agent，参数：
- chapter: {chapter_num}
- chapter_file: "正文/第{NNNN}章.md"
- review_score: {overall_score from Step 3}
- project_root: {PROJECT_ROOT}
- storage_path: .webnovel/
- state_file: .webnovel/state.json
```

- `review_score` 必须使用 Step 3 汇总后的 `overall_score`（`--minimal` 也必须产出）。
- 债务利息默认关闭，仅在用户明确要求或开启追踪时执行（详见 [workflow-details.md](references/workflow-details.md)）。

### Step 6：Git 备份

```bash
git add . && git commit -m "Ch{chapter_num}: {title}"
```

## 4. 最小交付检查

- [ ] 正文文件已生成（章节编号正确）。
- [ ] 审查已执行（模式对应的最小集合）。
- [ ] 润色已处理 critical/high。
- [ ] data-agent 已回写状态与索引。
- [ ] Git 备份成功或已说明失败原因。

## 5. 参考入口

- 执行模板与细节统一以 [workflow-details.md](references/workflow-details.md) 为准。
- 写作硬约束以 `${CLAUDE_PLUGIN_ROOT}/references/shared/core-constraints.md` 为准。
- 润色规则以 [polish-guide.md](references/polish-guide.md) 为准。
