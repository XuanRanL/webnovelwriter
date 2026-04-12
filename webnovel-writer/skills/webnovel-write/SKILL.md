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
- 若章纲包含结构化节点，则正文必须围绕节点骨架展开。

## 执行原则

1. 先校验输入，再进入写作主链。
2. 审查与数据回写是硬步骤，`--fast` 与 `--minimal` 只允许裁剪可选环节。
3. 参考资料按步骤按需加载，不一次性灌入全部文档。
4. Step 4 只做问题修复与终检，不回写结构化数据。
5. 任一步失败优先最小补跑，不重跑整条链路。

## 常见误区

- ❌ 认为本章简单就跳过 Step 3 审查
- ❌ blocking issue 还在时继续 Step 4 / Step 5
- ❌ 把全部 references 一次性读完再起草
- ❌ 用文件存在性替代 `chapter_status` 判断
- ❌ 润色时改动事件顺序、设定结果或节点收束方向
- ❌ Step 5 失败后直接开始下一章（状态还在 `chapter_reviewed`）
- ❌ 把全部 reference 一次性读完再开始写

## 优先级链

当多个指令来源冲突时，按以下顺序裁决：

1. 用户明确要求（最高）
2. 状态机 / `chapter_status` / `blocking` 硬门槛
3. 项目私有约束（总纲、设定集、已有剧情、长期记忆）
4. skill 默认流程
5. reference 建议（最低）

## 决策树入口

在进入 Step 0.5 之前，先判断：

- 若 `preflight` 失败或项目根不合法 → **阻断**，先修环境
- 若当前章缺少章纲或章纲关键字段缺失 → **阻断**，请求用户补全
- 若 Step 3 返回 `blocking=true` → 进入"修复 → 重审"循环，不得进入 Step 4/5
- 若 Step 4 `anti_ai_force_check=fail` → 回到 Step 4 修复，不得进入 Step 5
- 若 Step 5 仅数据回写失败 → 只补跑 Step 5，不回退 Step 1-4
- 若用户要求跳过某步骤但不在模式定义允许范围内 → 拒绝并说明原因

## 模式定义

- `/webnovel-write`：Step 0.5 → Step 1 → Step 2 → Step 3 → Step 4 → Step 5 → Step 6
- `/webnovel-write --fast`：Step 0.5 → Step 1 → Step 2 → Step 3（轻量） → Step 4 → Step 5 → Step 6
- `/webnovel-write --minimal`：Step 0.5 → Step 1 → Step 2 → Step 4（仅排版） → Step 5 → Step 6

最小产物：
- 章节正文文件
- `index.db.review_metrics` 新记录（`--minimal` 除外）
- `.webnovel/summaries/ch{NNNN}.md`
- `.webnovel/state.json` 的进度与 `chapter_meta`
- `.webnovel/memory_scratchpad.json` 的长期记忆事实

## 流程硬约束

- 禁止并步：不得把两个 Step 合并执行。
- 禁止跳步：除模式定义明确允许外，不得跳过任何 Step。
- 禁止改名：标准产物文件名和格式不得私自改写。
- 禁止伪造审查：Step 3 必须由 Task 子代理执行。
- 禁止源码探测：CLI 调用方式以本文档和 agent 文档为准，命令失败优先查日志。

## 引用加载策略

加载等级：
- L0：未进入对应步骤前，不加载参考资料。
- L1：只加载当前步骤必读文件。
- L2：仅在触发条件满足时加载条件参考。

### md 必读（L1，直接 Read）

路径说明：`../../references/` 指共享 references；`references/` 指 skill 私有 `skills/webnovel-write/references/`。

| Step | Trigger | Reference | 实际路径 |
|------|---------|-----------|---------|
| Step 1 | always | 追读力分类 | `${SKILL_ROOT}/../../references/reading-power-taxonomy.md` |
| Step 1 | always | 题材配置 | `${SKILL_ROOT}/../../references/genre-profiles.md` |
| Step 1 | always | 风格差异化 | `${SKILL_ROOT}/references/style-variants.md` |
| Step 2 | always | 核心约束 | `${SKILL_ROOT}/../../references/shared/core-constraints.md` |
| Step 2 | always | Anti-AI 预防 | `${SKILL_ROOT}/references/anti-ai-guide.md` |
| Step 3 | always | 审查 schema | `${SKILL_ROOT}/../../references/review-schema.md`（reviewer 内部使用） |
| Step 4 | always | 润色指南 | `${SKILL_ROOT}/references/polish-guide.md` |
| Step 4 | always | 排版规则 | `${SKILL_ROOT}/references/writing/typesetting.md` |
| Step 4 | always | 风格适配 | `${SKILL_ROOT}/references/style-adapter.md` |

### CSV 检索（L2，调用 `reference_search.py`）

| Step | Trigger | 检索命令 |
|------|---------|---------|
| Step 2 | 本章有新角色首次出场 | `python -X utf8 "${SCRIPTS_DIR}/reference_search.py" --skill write --table 命名规则 --query "角色命名" --genre {题材}` |
| Step 2 | 本章有战斗/对峙场景 | `... --skill write --table 场景写法 --query "战斗描写" --genre {题材}` |
| Step 2 | 本章有多角色对话 | `... --skill write --table 写作技法 --query "对话声线 口吻区分"` |
| Step 2 | 本章有情感/心理描写 | `... --skill write --table 写作技法 --query "情感描写 心理"` |
| Step 2 | 本章涉及高频桥段 | `... --skill write --table 场景写法 --query "{桥段类型}"` |

## 工具策略

- `Read/Grep`：读取大纲、状态、正文与参考资料。
- `Bash`：运行 `webnovel.py` 与相关脚本。
- `Task`：调用 `context-agent`、`reviewer` 与 `data-agent`。

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

### Step 0.5：轻量节点预检

目的：在不阻断流程的前提下，对章纲中的结构化节点做轻量一致性提醒。

规则：
- 只在当前章详细大纲存在 `CBN/CEN` 时执行。
- 只检查主角或 POV 角色相关节点。
- 第一版仅检查：
  - `CBN` 中地点是否与 `protagonist_state.location` 明显冲突
  - `CBN/CEN` 中主角境界或能力要求是否与 `protagonist_state.power` 明显冲突
- 检查结果仅作为警告注入给 `context-agent`，不得阻断流程。
- 若无节点字段，直接跳过。

警告示例：
- `[NODE_WARNING] CBN 地点与当前状态不一致: 章纲=迦南学院入口, 实际=乌坦城`
- `[NODE_WARNING] CBN 强度要求与当前境界不一致: 章纲=斗师级压制, 实际=斗者三星`

### Step 1：调用 Context Agent 生成执行包

使用 Task 调用 `context-agent`，输入：
- `chapter`
- `project_root`
- `storage_path=.webnovel/`
- `state_file=.webnovel/state.json`
- 若存在 `NODE_WARNING`，一并传入

硬要求：
- 输出必须包含任务书、Context Contract、Step 2 直写提示词。
- 执行包中必须纳入长期记忆约束与时间约束。
- 若章纲提供结构化节点，执行包中必须包含"情节结构"板块与节拍映射。

### Step 2：起草正文

执行前必须加载：

```bash
cat "${SKILL_ROOT}/../../references/shared/core-constraints.md"
cat "${SKILL_ROOT}/references/anti-ai-guide.md"
```

硬要求：
- 只输出纯正文到章节文件。
- 不得出现 `[TODO]`、`[待补充]` 等占位符。
- 若上章存在明确钩子，本章必须回应。
- 中文思维写作，不使用英文框架骨架驱动正文。
- 若存在结构化节点：正文必须围绕 `CBN -> CPNs -> CEN` 展开，不得跳过必须节点。

状态推进：

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" state set-chapter-status --chapter {chapter_num} --status chapter_drafted
```

### Step 3：执行审查

使用 Task 调用 `reviewer` agent，输入：
- `chapter`
- `chapter_file`（正文文件路径）
- `project_root`
- `scripts_dir`

reviewer 输出为结构化问题清单 JSON（参见 `review-schema.md`），保存到中间产物路径。

Step 3 中间产物约定：
- reviewer 原始结果：`${PROJECT_ROOT}/.webnovel/tmp/review_results.json`
- 落库指标：`${PROJECT_ROOT}/.webnovel/tmp/review_metrics.json`

标准文件流：

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" review-pipeline \
  --chapter {chapter_num} \
  --review-results "${PROJECT_ROOT}/.webnovel/tmp/review_results.json" \
  --metrics-out "${PROJECT_ROOT}/.webnovel/tmp/review_metrics.json" \
  --report-file "审查报告/第{chapter_num}章审查报告.md"

python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" index save-review-metrics \
  --data "@${PROJECT_ROOT}/.webnovel/tmp/review_metrics.json"
```

阻断规则：
- 若存在任何 `blocking=true` 的 issue，不得进入 Step 4/5。
- 必须先修复 blocking issue 后重新审查，或用户明确覆盖。

模式规则：
- 标准模式：完整审查（全维度）
- `--fast`：轻量审查（reviewer 仅检查 setting/timeline/continuity 三个维度）
- `--minimal`：跳过 Step 3

### Step 4：润色 + 风格适配 + Anti-AI 修复

执行前必须加载：

```bash
cat "${SKILL_ROOT}/references/polish-guide.md"
cat "${SKILL_ROOT}/references/writing/typesetting.md"
cat "${SKILL_ROOT}/references/style-adapter.md"
```

执行顺序：
1. 消费 Step 3 的问题清单，逐条修复非 blocking issue（blocking 已在 Step 3 阻断）
2. 风格适配：消除模板腔、说明腔、机械腔
3. 统一段落、节奏、排版
4. Anti-AI 全文终检

风格适配硬要求：
- 只改表达，不改事实、事件顺序、人物行为结果、设定规则。
- 若存在结构化节点，不得因风格改写破坏节点顺序和收束方向。

Anti-AI 硬要求：
- 必须输出 `anti_ai_force_check=pass/fail`
- `fail` 时不得进入 Step 5
- 有节点时，不得在润色中删除必须节点对应的情节落点

模式规则：
- `--minimal`：仅排版，跳过问题修复、风格适配和 Anti-AI 终检

状态推进（`--minimal` 除外）：

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" state set-chapter-status --chapter {chapter_num} --status chapter_reviewed
```

### Step 5：调用 Data Agent 回写结构化数据

使用 Task 调用 `data-agent`，参数：
- `chapter`
- `chapter_file`
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
- 债务利息（默认关闭，仅用户明确要求或项目显式启用时开启）

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

状态推进：

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" state set-chapter-status --chapter {chapter_num} --status chapter_committed
```

### Step 6：Git 备份

```bash
git add .
git -c i18n.commitEncoding=UTF-8 commit -m "第{chapter_num}章: {title}"
```

规则：
- 所有验证和回写完成后最后执行。
- commit 失败时，必须说明失败原因与未提交文件范围。

## 充分性闸门

未满足以下条件前，不得结束流程：

1. 章节正文文件存在且非空。
2. `chapter_status` 已推进到 `chapter_drafted`（Step 2 完成）。
3. Step 3 已产出审查结果并落库（`--minimal` 除外）。
4. 若存在 `blocking=true` 的 issue，流程必须停在 Step 3。
5. Step 4 的 `anti_ai_force_check=pass`（`--minimal` 除外），`chapter_status` 已推进到 `chapter_reviewed`。
6. Step 5 已更新 `state.json`、`index.db`、`summaries/ch{chapter_padded}.md`、`memory_scratchpad.json`，`chapter_status` 已推进到 `chapter_committed`。
7. 若启用观测，已读取最新 timing 记录并给出结论。

## 验证与交付

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" state get-chapter-status --chapter {chapter_num}
test -f "${PROJECT_ROOT}/正文/第${chapter_padded}章.md"
test -f "${PROJECT_ROOT}/.webnovel/summaries/ch${chapter_padded}.md"
test -f "${PROJECT_ROOT}/.webnovel/memory_scratchpad.json"
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" index get-recent-review-metrics --limit 1
tail -n 1 "${PROJECT_ROOT}/.webnovel/observability/data_agent_timing.jsonl" || true
```

成功标准：
- `chapter_status` 为 `chapter_committed`（`--minimal` 模式下至少为 `chapter_drafted`）。
- 章节文件、摘要文件、状态文件、长期记忆暂存文件齐全且内容可读。
- 审查结果可追溯。
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
