---
name: webnovel-review
description: 使用审查 Agent 评估章节质量，生成报告并写回审查指标。
allowed-tools: Read Grep Write Edit Bash Task AskUserQuestion
---

# Quality Review Skill

## 目标

- 解析真实书项目根目录，按统一流程完成章节审查。
- 调用审查 Agent 生成结构化问题列表、综合评分与审查报告。
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

### Step 2：记录工作流断点（best-effort）

```bash
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow start-task --command webnovel-review --chapter {end} || true
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow start-step --step-id "Step 1" --step-name "解析项目根目录" || true
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow complete-step --step-id "Step 1" --artifacts '{"project_root_ready":true}' || true
```

要求：
- 记录失败只记警告，不阻断主流程

### Step 3：按需加载参考资料

```bash
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow start-step --step-id "Step 2" --step-name "加载参考" || true
```

必读：

```bash
cat "${SKILL_ROOT}/../../references/shared/core-constraints.md"
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

```bash
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow complete-step --step-id "Step 2" --artifacts '{"references_loaded":true}' || true
```

### Step 4：加载项目状态与待审正文

```bash
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow start-step --step-id "Step 3" --step-name "加载项目状态" || true
```

```bash
cat "${PROJECT_ROOT}/.webnovel/state.json"
```

要求：
- 明确当前章节范围与对应正文文件
- 若缺少正文或状态文件，立即阻断

```bash
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow complete-step --step-id "Step 3" --artifacts '{"review_input_ready":true}' || true
```

### Step 5：并行调用检查员并汇总结果

```bash
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow start-step --step-id "Step 4" --step-name "并行调用检查员" || true
```

必须通过 `Task` 调用审查子代理，禁止主流程伪造结论。

Core：
- `consistency-checker`
- `continuity-checker`
- `ooc-checker`
- `reader-pull-checker`

Full 追加：
- `high-point-checker`
- `pacing-checker`

要求：
- 所有子代理结果返回后，统一汇总 `issues`、`severity`、`overall_score`

```bash
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow complete-step --step-id "Step 4" --artifacts '{"review_completed":true}' || true
```

### Step 6：生成审查报告与审查指标 JSON

```bash
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow start-step --step-id "Step 5" --step-name "生成审查报告" || true
```

报告保存到：`审查报告/第{start}-{end}章审查报告.md`

报告结构：
- 综合评分
- 修改优先级
- 改进建议

审查指标 JSON 必须包含：
- `start_chapter`
- `end_chapter`
- `overall_score`
- `dimension_scores`
- `severity_counts`
- `critical_issues`
- `report_file`
- `notes`

```bash
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow complete-step --step-id "Step 5" --artifacts '{"report_generated":true}' || true
```

### Step 7：写入 index.db 与 state.json

```bash
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow start-step --step-id "Step 6" --step-name "写入审查指标" || true
```

保存审查指标：

```bash
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" index save-review-metrics --data '@review_metrics.json'
```

写回审查记录：

```bash
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" update-state -- --add-review "{start}-{end}" "审查报告/第{start}-{end}章审查报告.md"
```

```bash
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow complete-step --step-id "Step 6" --artifacts '{"review_metrics_saved":true}' || true
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow start-step --step-id "Step 7" --step-name "写回审查记录" || true
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow complete-step --step-id "Step 7" --artifacts '{"review_checkpoint_saved":true}' || true
```

### Step 8：处理关键问题并收尾

```bash
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow start-step --step-id "Step 8" --step-name "处理关键问题并收尾" || true
```

如存在 `critical` 问题，必须使用 `AskUserQuestion` 询问用户：
- 立即修复
- 仅保存报告，稍后处理

若用户选择立即修复：
- 输出返工清单
- 在用户明确授权下做最小修改

若用户选择稍后处理：
- 保留报告与指标记录，结束流程

收尾：

```bash
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow complete-step --step-id "Step 8" --artifacts '{"ok":true}' || true
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow complete-task --artifacts '{"ok":true}' || true
```

## 成功标准

1. 已解析真实书项目根目录。
2. 已完成至少 Core 审查深度。
3. 审查报告已生成。
4. `review_metrics` 已写入 `index.db`。
5. 审查记录已写回 `state.json`。
6. 如存在关键问题，用户已明确选择处理策略。
