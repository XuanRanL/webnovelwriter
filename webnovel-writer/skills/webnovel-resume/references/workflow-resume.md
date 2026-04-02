---
name: workflow-resume
purpose: 任务恢复时加载，指导中断恢复流程
---

<context>
此文件用于中断任务恢复。Claude 已知通用错误处理流程，这里只补充网文创作工作流的步骤难度分级和恢复策略。
</context>

<instructions>

## Step 中断难度分级

| Step | 名称 | 影响 | 难度 | 默认策略 |
|------|------|------|------|----------|
| Step 1 | Context Agent | 无副作用（仅读取） | ⭐ | 直接重新执行 |
| Step 2A | 生成粗稿 | 半成品章节文件 | ⭐⭐ | 删除半成品，从 Step 1 重新开始 |
| Step 2B | 风格适配 | 部分改写内容 | ⭐⭐ | 继续适配或回到 Step 2A |
| Step 3 | 审查 | 审查未完成 | ⭐⭐⭐ | 用户决定：重审或跳过 |
| Step 4 | 网文化润色 | 部分润色的文件 | ⭐⭐ | 继续润色或删除重写 |
| Step 5 | Data Agent | 实体、摘要、长期记忆未写完 | ⭐⭐ | 重新运行（幂等） |
| Step 6 | Git 备份 | 未提交 | ⭐⭐⭐ | 检查暂存区，决定提交或保留现场 |

## 恢复流程

### Step 1：检测中断状态

```bash
python "${SCRIPTS_DIR}/webnovel.py" --project-root "$PROJECT_ROOT" workflow detect
```

### Step 2：询问用户

必须展示：
- 任务命令和参数
- 中断时间和位置
- 已完成步骤
- 恢复选项和风险等级

### Step 3：执行恢复

选项 A：删除半成品后重新开始

```bash
python "${SCRIPTS_DIR}/webnovel.py" --project-root "$PROJECT_ROOT" workflow cleanup --chapter {N} --confirm
python "${SCRIPTS_DIR}/webnovel.py" --project-root "$PROJECT_ROOT" workflow clear
/webnovel-write {N}
```

选项 B：切到上一稳定标签，再清理中断状态

```bash
git -C "$PROJECT_ROOT" rev-parse --verify "ch{N-1:04d}"
git -C "$PROJECT_ROOT" switch --detach "ch{N-1:04d}"
python "${SCRIPTS_DIR}/webnovel.py" --project-root "$PROJECT_ROOT" workflow clear
```

硬规则：
- `workflow cleanup --confirm` 与 Git 切换都属于高风险操作，执行前必须获得用户明确确认。
- 若用户要保留现场排查问题，禁止执行清理或回退。

## 为什么删除而不续写

1. 半成品可能包含未完成句子、逻辑断裂。
2. 新会话缺失创作时的隐含上下文。
3. 直接续写更容易引入前后矛盾。
4. 重新生成的成本通常低于修半成品加重审。

## 特殊场景

| 场景 | 策略 |
|------|------|
| 超过 24 小时 | 推荐重新开始 |
| 超过 1 小时 | 默认删除半成品后重来 |
| 多个半成品 | 删除所有半成品，从稳定状态重新开始 |
| workflow_state.json 不存在 | 启发式检测 `state.json` 与正文文件 |

</instructions>

<examples>

<example>
<input>Step 2A 中断（最常见）</input>
<output>
检测到中断任务：

任务：/webnovel-write 7
中断位置：Step 2A - 章节内容生成中

已完成：
  ✅ Step 1: Context Agent 搜集上下文

未完成：
  ⏸️ Step 2A: 生成章节内容（已写1500字）
  ⏹️ Step 2B-6: 未开始

恢复选项：
A) 删除半成品，从 Step 1 重新开始（推荐）
B) 切到 Ch6 稳定标签，放弃 Ch7 当前进度

请选择（A/B）：
</output>
</example>

<example>
<input>Step 3 中断（审查）</input>
<output>
恢复选项：
A) 重新执行审查
   - 调用审查员
   - 生成审查报告
   - 继续 Step 4 润色

B) 跳过审查，直接润色
   - 不生成审查报告
   - 可后续用 /webnovel-review 补审

请选择（A/B）：
</output>
</example>

<example>
<input>Step 4 中断（润色）</input>
<output>
恢复选项：
A) 继续润色
   - 打开并继续润色实际章节文件（优先 `正文/第0007章-章节标题.md`）
   - 保存文件
   - 继续 Step 5（Data Agent）

B) 删除润色稿，从 Step 2A 重写
   - 删除实际章节文件（优先 `正文/第0007章-章节标题.md`）
   - 重新生成章节内容

请选择（A/B）：
</output>
</example>

</examples>

<errors>
❌ 智能续写半成品 → ✅ 删除后重新生成
❌ 自动决定恢复策略 → ✅ 必须用户确认
❌ 跳过中断检测 → ✅ 先运行 workflow detect
❌ 不确认就做高风险清理 → ✅ 先获得用户明确确认
</errors>
