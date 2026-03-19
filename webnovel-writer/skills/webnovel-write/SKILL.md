---
name: webnovel-write
description: 产出可发布章节，完整执行上下文、起草、审查、润色、数据回写与备份。
allowed-tools: Read Write Edit Grep Bash Task
---

# Chapter Writing（结构化写作流程）

## 目标

- 产出可发布章节，优先写入 `正文/第{NNNN}章-{title_safe}.md`，无标题时回退 `正文/第{NNNN}章.md`。
- 默认目标字数 2000-2500；若用户或大纲另有要求，以用户和大纲为准。
- 保证审查、润色、数据回写、长期记忆提取全部闭环。
- 输出内容必须能被下一章直接消费。

## 执行原则

1. 先校验输入，再进入写作主链。
2. 审查与数据回写是硬步骤，`--fast` 与 `--minimal` 只允许裁剪可选环节。
3. 参考资料按步骤按需加载，不一次性灌入全部文档。
4. Step 4 只做问题修复与终检，不回写结构化数据。
5. 任一步失败优先最小补跑，不重跑整条链路。

## 模式定义

- `/webnovel-write`：Step 1 → Step 2A → Step 2B → Step 3 → Step 4 → Step 5 → Step 6
- `/webnovel-write --fast`：Step 1 → Step 2A → Step 3 → Step 4 → Step 5 → Step 6
- `/webnovel-write --minimal`：Step 1 → Step 2A → Step 2B → Step 3（仅核心 3 个审查器）→ Step 4 → Step 5 → Step 6

最小产物：
- 章节正文文件
- `index.db.review_metrics` 新记录
- `.webnovel/summaries/ch{NNNN}.md`
- `.webnovel/state.json` 的进度与 `chapter_meta`
- `.webnovel/memory_scratchpad.json` 的长期记忆事实

## 流程硬约束

- 禁止并步：不得把两个 Step 合并执行。
- 禁止跳步：除模式定义明确允许外，不得跳过任何 Step。
- 禁止改名：标准产物文件名和格式不得私自改写。
- 禁止伪造审查：Step 3 必须由 Task 子代理执行。
- 禁止源码探测：CLI 调用方式以本文档和 agent 文档为准，命令失败优先查日志。
- Workflow step-id 必须使用实现侧真实编号：`Step 1`、`Step 2A`、`Step 2B`、`Step 3`、`Step 4`、`Step 5`、`Step 6`。

## 引用加载等级

- L0：未进入对应步骤前，不加载参考资料。
- L1：只加载当前步骤必读文件。
- L2：仅在触发条件满足时加载条件参考。

## References

- `references/step-3-review-gate.md`
  - 用途：Step 3 审查调用模板与落库规范。
- `references/step-5-debt-switch.md`
  - 用途：Step 5 债务利息开关规则。
- `../../references/shared/core-constraints.md`
  - 用途：Step 2A 起草硬约束。
- `references/polish-guide.md`
  - 用途：Step 4 润色与终检规则。
- `references/writing/typesetting.md`
  - 用途：Step 4 排版检查。
- `references/style-adapter.md`
  - 用途：Step 2B 风格适配规则。
- `references/style-variants.md`
  - 用途：Step 1 差异化设计。
- `../../references/reading-power-taxonomy.md`
  - 用途：Step 1 追读力设计。
- `../../references/genre-profiles.md`
  - 用途：Step 1 题材节奏与钩子偏好。
- `references/writing/genre-hook-payoff-library.md`
  - 用途：Step 1 特定题材快速库。

问题定向参考：
- `references/writing/combat-scenes.md`
- `references/writing/dialogue-writing.md`
- `references/writing/emotion-psychology.md`
- `references/writing/scene-description.md`
- `references/writing/desire-description.md`

## 工具策略

- `Read/Grep`：读取大纲、状态、正文与参考资料。
- `Bash`：运行 `webnovel.py` 与相关脚本。
- `Task`：调用 `context-agent`、审查器与 `data-agent`。

## 执行流程

### 准备阶段：预检与环境准备

必须完成：
- 解析真实书项目根，必须包含 `.webnovel/state.json`
- 校验核心输入：`大纲/总纲.md`、`${CLAUDE_PLUGIN_ROOT}/scripts/extract_chapter_context.py`
- 规范化变量：`WORKSPACE_ROOT`、`PROJECT_ROOT`、`SKILL_ROOT`、`SCRIPTS_DIR`、`chapter_num`、`chapter_padded`

```bash
export WORKSPACE_ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
export SCRIPTS_DIR="${CLAUDE_PLUGIN_ROOT:?CLAUDE_PLUGIN_ROOT is required}/scripts"
export SKILL_ROOT="${CLAUDE_PLUGIN_ROOT:?CLAUDE_PLUGIN_ROOT is required}/skills/webnovel-write"

python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${WORKSPACE_ROOT}" preflight
export PROJECT_ROOT="$(python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${WORKSPACE_ROOT}" where)"
```

硬门槛：
- `preflight` 必须成功。
- 任一核心输入缺失立即阻断。

任务记录：

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow start-task --command webnovel-write --chapter {chapter_num} || true
```

### Step 1：调用 Context Agent 生成执行包

记录开始：

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow start-step --step-id "Step 1" --step-name "Context Agent" || true
```

使用 Task 调用 `context-agent`，输入：
- `chapter`
- `project_root`
- `storage_path=.webnovel/`
- `state_file=.webnovel/state.json`

硬要求：
- 输出必须包含任务书、Context Contract、Step 2A 直写提示词。
- 执行包中必须纳入长期记忆约束与时间约束。

记录完成：

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow complete-step --step-id "Step 1" --artifacts '{"context_package":true}' || true
```

### Step 2A：起草正文

执行前必须加载：

```bash
cat "${SKILL_ROOT}/../../references/shared/core-constraints.md"
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow start-step --step-id "Step 2A" --step-name "正文起草" || true
```

硬要求：
- 只输出纯正文到章节文件。
- 不得出现 `[TODO]`、`[待补充]` 等占位符。
- 若上章存在明确钩子，本章必须回应。
- 中文思维写作，不使用英文框架骨架驱动正文。

完成后记录：

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow complete-step --step-id "Step 2A" --artifacts '{"chapter_draft":true}' || true
```

### Step 2B：风格适配（`--fast` 跳过）

执行前加载：

```bash
cat "${SKILL_ROOT}/references/style-adapter.md"
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow start-step --step-id "Step 2B" --step-name "风格适配" || true
```

硬要求：
- 只改表达，不改事实、事件顺序、人物行为结果、设定规则。
- 重点消除模板腔、说明腔、机械腔。

完成后记录：

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow complete-step --step-id "Step 2B" --artifacts '{"style_adapted":true}' || true
```

### Step 3：执行审查并落库

执行前加载：

```bash
cat "${SKILL_ROOT}/references/step-3-review-gate.md"
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow start-step --step-id "Step 3" --step-name "审查" || true
```

调用约束：
- 必须用 Task 调用审查子代理。
- 默认使用 `auto` 路由动态选择检查器。

核心审查器：
- `consistency-checker`
- `continuity-checker`
- `ooc-checker`

条件审查器：
- `reader-pull-checker`
- `high-point-checker`
- `pacing-checker`

模式规则：
- 标准模式与 `--fast`：核心 3 个 + auto 命中的条件审查器
- `--minimal`：只跑核心 3 个

审查指标落库：

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" index save-review-metrics --data "@${PROJECT_ROOT}/.webnovel/tmp/review_metrics.json"
```

硬要求：
- 必须产出 `overall_score`。
- `notes` 必须是单个字符串。
- 未落库 `review_metrics` 不得进入 Step 4。

完成后记录：

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow complete-step --step-id "Step 3" --artifacts '{"review_completed":true}' || true
```

### Step 4：润色与全文终检

执行前必须加载：

```bash
cat "${SKILL_ROOT}/references/polish-guide.md"
cat "${SKILL_ROOT}/references/writing/typesetting.md"
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow start-step --step-id "Step 4" --step-name "润色" || true
```

执行顺序：
1. 修复已知严重问题
2. 统一段落、节奏、排版
3. 执行 Anti-AI 与 No-Poison 全文终检

硬要求：
- 必须输出 `anti_ai_force_check=pass/fail`
- `fail` 时不得进入 Step 5

完成后记录：

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow complete-step --step-id "Step 4" --artifacts '{"anti_ai_force_check":"pass"}' || true
```

### Step 5：调用 Data Agent 回写结构化数据

执行前记录：

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow start-step --step-id "Step 5" --step-name "Data Agent" || true
```

使用 Task 调用 `data-agent`，参数：
- `chapter`
- `chapter_file`
- `review_score=Step 3 overall_score`
- `project_root`
- `storage_path=.webnovel/`
- `state_file=.webnovel/state.json`

Data Agent 默认子步骤全部执行：
- 加载上下文
- 实体提取与消歧
- 写入 state/index
- 写入章节摘要
- 提取长期记忆 `memory_facts`
- 场景切片
- RAG 向量索引
- 风格样本评估（仅 `review_score >= 80`）
- 债务利息（默认关闭）

失败隔离规则：
- state/index/summary/memory 写入失败：只重跑 Step 5
- `--scenes` 缺失导致的向量或风格样本失败：只补跑对应子步骤
- 禁止因 Step 5 子步骤失败而回滚 Step 1-4

执行后最小检查白名单：
- `.webnovel/state.json`
- `.webnovel/index.db`
- `.webnovel/summaries/ch{chapter_padded}.md`
- `.webnovel/memory_scratchpad.json`
- `.webnovel/observability/data_agent_timing.jsonl`

性能要求：
- 读取最新 timing 记录
- `TOTAL > 30000ms` 时，输出最慢 2-3 个环节与原因说明

完成后记录：

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow complete-step --step-id "Step 5" --artifacts '{"state_json_modified":true,"entities_appeared":true}' || true
```

### Step 6：Git 备份

执行前记录：

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow start-step --step-id "Step 6" --step-name "Git 备份" || true
git add .
git -c i18n.commitEncoding=UTF-8 commit -m "第{chapter_num}章: {title}"
```

规则：
- 所有验证和回写完成后最后执行。
- commit 失败时，必须说明失败原因与未提交文件范围。

完成后记录：

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow complete-step --step-id "Step 6" --artifacts '{"git_status":{"committed":true}}' || true
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow complete-task --artifacts '{"ok":true}' || true
```

## 充分性闸门

未满足以下条件前，不得结束流程：

1. 章节正文文件存在且非空。
2. Step 3 已产出 `overall_score`，且 `review_metrics` 已落库。
3. Step 4 的 `anti_ai_force_check=pass`。
4. Step 5 已更新 `state.json`、`index.db`、`summaries/ch{chapter_padded}.md`。
5. Step 5 已写入 `.webnovel/memory_scratchpad.json`。
6. 若启用观测，已读取最新 timing 记录并给出结论。

## 验证与交付

```bash
test -f "${PROJECT_ROOT}/.webnovel/state.json"
test -f "${PROJECT_ROOT}/正文/第${chapter_padded}章.md"
test -f "${PROJECT_ROOT}/.webnovel/summaries/ch${chapter_padded}.md"
test -f "${PROJECT_ROOT}/.webnovel/memory_scratchpad.json"
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" index get-recent-review-metrics --limit 1
tail -n 1 "${PROJECT_ROOT}/.webnovel/observability/data_agent_timing.jsonl" || true
```

成功标准：
- 章节文件、摘要文件、状态文件、长期记忆暂存文件齐全且内容可读。
- 审查分数可追溯，`overall_score` 与 Step 5 输入一致。
- 润色后未破坏大纲、设定与长期记忆约束。

## 失败处理

触发条件：
- 章节文件缺失或为空
- 审查结果未落库
- Data Agent 关键产物缺失
- 润色引入设定冲突

恢复规则：
1. 只补跑失败步骤，不回滚已通过步骤。
2. 审查缺失：只重跑 Step 3。
3. 摘要、状态、长期记忆缺失：只重跑 Step 5。
4. 润色失真：回到 Step 4 修复后重新执行 Step 5。
