---
name: webnovel-resume
description: 检测中断点并按安全策略恢复小说工作流。
allowed-tools: Read Bash AskUserQuestion
---

# Task Resume Skill

## 目标

- 检测真实中断点，禁止凭感觉续写。
- 让用户基于清晰风险选择恢复策略。
- 恢复时只做最小清理，不擅自扩写半成品。

## 执行流程

### Step 1：解析项目根目录并加载恢复协议

```bash
export WORKSPACE_ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
export SKILL_ROOT="${CLAUDE_PLUGIN_ROOT}/skills/webnovel-resume"
export SCRIPTS_DIR="${CLAUDE_PLUGIN_ROOT}/scripts"
export PROJECT_ROOT="$(python "${SCRIPTS_DIR}/webnovel.py" --project-root "${WORKSPACE_ROOT}" where)"
cat "${SKILL_ROOT}/references/workflow-resume.md"
```

核心原则：
- 禁止智能续写半成品
- 必须先检测再恢复
- 必须用户确认后执行

### Step 2：按需加载数据规范

```bash
cat "${SKILL_ROOT}/references/system-data-flow.md"
```

要求：
- 仅在需要核对状态字段、恢复策略或数据一致性时加载

### Step 3：确认上下文充足

必须确认：
- 已理解恢复协议
- 已理解状态结构
- 已明确“删除重来”优先于“智能续写”

### Step 4：检测中断状态

```bash
python "${SCRIPTS_DIR}/webnovel.py" --project-root "$PROJECT_ROOT" workflow detect
```

结果处理：
- 无中断：直接结束并通知用户
- 有中断：进入 Step 5

### Step 5：展示恢复选项并让用户决策

必须展示：
- 原任务命令和参数
- 中断时间与已过时长
- 已完成步骤
- 当前中断步骤
- 剩余步骤
- 恢复选项与风险说明

### Step 6：执行恢复操作

选项 A：删除半成品并清理工作流状态

```bash
python "${SCRIPTS_DIR}/webnovel.py" --project-root "$PROJECT_ROOT" workflow cleanup --chapter {N} --confirm
python "${SCRIPTS_DIR}/webnovel.py" --project-root "$PROJECT_ROOT" workflow clear
```

选项 B：按既有版本回退，再清理工作流状态

```bash
git -C "$PROJECT_ROOT" rev-parse --verify "ch{N-1:04d}"
git -C "$PROJECT_ROOT" switch --detach "ch{N-1:04d}"
python "${SCRIPTS_DIR}/webnovel.py" --project-root "$PROJECT_ROOT" workflow clear
```

说明：
- `workflow cleanup --confirm` 与 Git 回退都属于高风险操作，执行前必须获得用户明确确认。
- 若用户只是要保留现场排查问题，不应执行上述清理或回退。

### Step 7：按用户意愿继续任务

若用户要求立即继续，则执行原始命令；若未要求，则仅完成恢复并结束。

## 禁止事项

- 禁止智能续写半成品
- 禁止自动替用户选择恢复策略
- 禁止跳过中断检测
- 禁止在未验证前修复 `state.json`
