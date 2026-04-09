---
name: webnovel-review
description: 使用审查 Agent 评估章节质量，生成报告并写回审查指标。
allowed-tools: Read Grep Write Edit Bash Task AskUserQuestion
---

# Quality Review Skill

## 目标

- 解析真实书项目根目录，按统一流程完成章节审查。
- 调用统一 `reviewer` 生成结构化问题列表与审查报告。
- 把审查指标写入 `index.db`，并把审查记录写回 `state.json`。
- 若存在关键问题，明确交给用户决定是否立即返工。

## 执行流程

### Step 1：解析项目根目录并建立环境变量

```bash
export WORKSPACE_ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
export SKILL_ROOT="${CLAUDE_PLUGIN_ROOT}/skills/webnovel-review"
export SCRIPTS_DIR="${CLAUDE_PLUGIN_ROOT}/scripts"
export PROJECT_ROOT="$(python "${SCRIPTS_DIR}/webnovel.py" --project-root "${WORKSPACE_ROOT}" where)"
```

要求：
- `PROJECT_ROOT` 必须包含 `.webnovel/state.json`
- 任一关键目录不存在时立即阻断

### Step 2：按需加载参考资料

必读：

```bash
cat "${SKILL_ROOT}/../../references/shared/core-constraints.md"
cat "${SKILL_ROOT}/../../references/review-schema.md"
```

按需加载：

```bash
cat "${SKILL_ROOT}/../../references/shared/cool-points-guide.md"
cat "${SKILL_ROOT}/../../references/shared/strand-weave-pattern.md"
cat "${SKILL_ROOT}/references/common-mistakes.md"
cat "${SKILL_ROOT}/references/pacing-control.md"
```

规则：
- 先判定 Core 或 Full 审查深度，再加载对应参考
- 不得在未触发时一次性读完全部资料

### Step 3：加载项目状态与待审正文

```bash
cat "${PROJECT_ROOT}/.webnovel/state.json"
```

要求：
- 明确当前章节号与对应正文文件
- 若缺少正文或状态文件，立即阻断

### Step 4：调用统一审查 Agent

必须通过 `Task` 调用 `reviewer`，禁止主流程伪造结论。

输入：
- `chapter`
- `chapter_file`
- `project_root`
- `scripts_dir`

输出约束：
- 只输出 JSON
- 每个 issue 必须有 `evidence`
- 不输出 `overall_score`

中间产物约定：
- reviewer 原始结果：`${PROJECT_ROOT}/.webnovel/tmp/review_results.json`
- 落库指标：`${PROJECT_ROOT}/.webnovel/tmp/review_metrics.json`

### Step 5：生成审查报告并落库

报告保存到：`审查报告/第{chapter_num}章审查报告.md`

报告结构：
- 总览（问题数 / 阻断数）
- 阻断问题
- 其他问题
- 修复方向

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

要求：
- `review-pipeline` 生成的 `review_metrics.json` 必须可直接写入 `review_metrics` 表
- 阻断判断以 reviewer 原始结果中的 `blocking=true` 为准

### Step 6：写回审查记录并处理阻断

先写回审查记录：

```bash
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" update-state -- --add-review "{chapter_num}-{chapter_num}" "审查报告/第{chapter_num}章审查报告.md"
```

如存在任意 `blocking=true` 问题，必须使用 `AskUserQuestion` 询问用户：
- 立即修复
- 仅保存报告，稍后处理

若用户选择立即修复：
- 输出返工清单
- 在用户明确授权下做最小修改

若用户选择稍后处理：
- 保留报告与指标记录，结束流程

## 成功标准

1. 已解析真实书项目根目录。
2. 已通过 `reviewer` 输出结构化问题 JSON。
3. 审查报告已生成。
4. `review_metrics` 已写入 `index.db`。
5. 审查记录已写回 `state.json`。
6. 如存在阻断问题，用户已明确选择处理策略。
