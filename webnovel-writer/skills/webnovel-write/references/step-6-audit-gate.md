# Step 6 审计闸门规范

> Step 6 的调用模板、执行时序、决议逻辑、产物约定。本文件被 SKILL.md 的 Step 6 章节引用，也被 audit-agent 必读。

## 定位

- **Step 6 = 章节审计闸门**，Step 7 = Git 提交
- Step 6 是 `/webnovel-write` 流程的倒数第二步，位于 Step 5（Data Agent）之后、Step 7（Git）之前
- 与 Step 3 的区别：Step 3 在章节内审质量，Step 6 跨步骤/跨产物/跨章审链路与承诺兑现
- Step 6 是最后一道防线：如果 Step 6 通过后章节仍有问题，大概率是审计矩阵需要扩充，不是流程问题

## 执行模型

Step 6 一次调用由两部分组成，**必须全部完成**后才能判定：

### Part 1 — CLI 结构审计（快速路径）

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" \
  audit chapter --chapter ${chapter_num} --mode ${mode} \
  --out "${PROJECT_ROOT}/.webnovel/tmp/audit_layer_abg_ch${chapter_padded}.json"
```

该命令由 `data_modules/chapter_audit.py` 实现，完成 Layer A / B / G 的确定性检查。预期耗时 < 5s。

退出码：
- `0` = 全部通过
- `1` = 结构层面有 critical fail
- `2` = 有 warnings 但无 critical
- `3` = CLI 自身错误（脚本 bug / 文件缺失等）

### Part 2 — audit-agent 深度审计（判断路径）

```
Task(audit-agent, {
  chapter: <chapter_num>,
  project_root: <PROJECT_ROOT>,
  mode: <standard|fast|minimal>,
  chapter_file: <正文/第NNNN章-*.md>,
  time_budget_seconds: 300
})
```

audit-agent 自动读取 Part 1 的 JSON 输出，完成 Layer C / D / E / F 判断性检查，聚合所有层级，产出最终 `audit_report.json`。

预期耗时 60-300s（取决于本章字数、历史章节数）。

### Part 1 与 Part 2 的串行关系

- Part 1 必须先完成（Part 2 的 Layer A/B/G 读 Part 1 的结果）
- 若 Part 1 有 critical fail，Part 2 **仍然执行**（给用户完整诊断），但最终决议必然 block
- 主流程不得因为 Part 1 失败就跳过 Part 2

## 调用时序

```
Step 5 complete
    ↓
Step 0.5: workflow start-step --step-id "Step 6" --step-name "Audit Gate"
    ↓
Part 1 CLI: webnovel.py audit chapter ...
    ↓
Part 2 Agent: Task(audit-agent, ...)
    ↓
读取 audit-agent 输出 JSON
    ↓
IF decision == block:
    报告阻断原因 + remediation
    workflow complete-step --step-id "Step 6" --status failed
    流程终止，不进入 Step 7
IF decision == approve_with_warnings:
    记录 warnings
    workflow complete-step --step-id "Step 6" --artifacts '{"warnings": N}'
    进入 Step 7，commit message 附 [audit:warn:layerX]
IF decision == approve:
    workflow complete-step --step-id "Step 6" --artifacts '{"ok": true}'
    进入 Step 7
```

## 产物约定

| 产物 | 路径 | 作者 | 用途 |
|---|---|---|---|
| CLI 结构审计 JSON | `.webnovel/tmp/audit_layer_abg_ch{NNNN}.json` | CLI (Part 1) | audit-agent 消费 |
| 完整审计 JSON | `.webnovel/audit_reports/ch{NNNN}.json` | audit-agent (Part 2) | 机读、归档、趋势 |
| 审计段追加 | `审查报告/第{NNNN}章审查报告.md` 末尾追加 `## Step 6 审计闸门` | audit-agent | 人读 |
| 下章准备 | `.webnovel/editor_notes/ch{NNNN+1}_prep.md` | audit-agent | 下章 context-agent 必读 |
| 趋势日志 | `.webnovel/observability/chapter_audit.jsonl` 追加单行 | audit-agent | Layer G 基线 |

## 决议规则（主流程读 audit-agent 输出后应用）

```python
decision = report['overall_decision']
if decision == 'block':
    blockers = report['blocking_issues']
    print_remediation(blockers)
    fail_step_6()
    return  # 流程终止
elif decision == 'approve_with_warnings':
    warnings = report['warnings']
    log_warnings(warnings)
    complete_step_6(artifacts={'warnings_count': len(warnings)})
    proceed_to_step_7(commit_message_suffix=f"[audit:warn:{'|'.join(set(w['layer'] for w in warnings))}]")
elif decision == 'approve':
    complete_step_6(artifacts={'ok': True})
    proceed_to_step_7()
```

## 失败恢复路径

### Layer A 失败（过程真实性）
- A1 Context Contract 不全 → 重跑 Step 1：`Task(context-agent, ...)`
- A2 13 checker 坍缩 → 重跑 Step 3，显式 Task 调用 13 个 checker（含 flow-checker + reader-naturalness + reader-critic · Round 13 v2）
- A3 9 外部模型异常 → 重跑 Step 3.5：`external_review.py --model-key all`
- A4 Data Agent 子步跳过 → 重跑 Step 5
- A5 fallback 检测 → 确认 `claude plugin enable webnovel-writer@webnovel-writer-marketplace`，会话重启后重跑
- A6 时序异常 → 重跑可疑步骤
- A7 编码损坏 → 从 Step 2A 重写
- A8 anti_ai_force_check stub → 重跑 Step 4 终检

### Layer B 失败（跨产物一致性）
- B1-B2 摘要/实体漂移 → 补跑 Step 5 E/K
- B3 伏笔三处不一致 → 补跑 Step 5 D+K，手工校对
- B4 数值不一致 → 重跑 `index save-review-metrics`
- B5-B6 设定集未传播 → 重跑 Step 5 K，或手动追加 `[Ch{N}]` 段
- B7 章纲未兑现 → 回 Step 4 补写
- B8 时间漂移 → 修正正文或设定集时间线表
- B9 chapter_meta 字段不全 → 重跑 Step 5 D

### Layer C 失败（读者体验）
- C1-C3 开头/钩子/未闭合问题 → Step 4 改写对应段落
- C4 爽点兑现 → Step 4 补兑现或余韵
- C5 情绪曲线 → Step 4 调节奏
- C6-C12 其他 → Step 4 针对性修复

### Layer D 失败（作品连续性）
- D3-D8 人设/数值/规则越界 → Step 4 改写越界点（critical）
- D1-D2 风格漂移 → Step 4 风格回调
- D9 物理不合规 → Step 4 补过渡
- D10 伏笔债务 → 跨卷规划调整（非本章问题）

### Layer E 失败（创作工艺）
- E1-E10 → 全部 Step 4 针对性修复

### Layer F 失败（题材兑现）
- F 层任一失败 → Step 4 针对性补写（critical 项必须修）

### Layer G 失败（跨章趋势）
- G1-G9 → 警告性质，多数不 block 但强制写入 editor_notes

## 与 workflow_manager.py 的协作

Step 6 需要在 `_VALID_STEP_IDS` / `pending_steps` / 归属映射 / recovery 选项中登记：

- step-id: `"Step 6"` (注意不是 6.1/6.2，整个 audit 视作一步)
- name: `"Audit Gate"`
- owner: `"audit-agent"`
- Step 7: `"Git Commit"`, owner: `"backup-agent"`

Step 6 失败时 recovery 选项：
1. 按 blocking_issues 逐项修复（推荐）
2. 重跑 audit（若怀疑 audit-agent 本身出错）
3. 强制跳过（不推荐，需用户显式确认）

## 时间预算处理

- 软上限 300s
- 若 audit-agent 超时，当前最新返回结果按"未完成"处理：
  - 已完成 layers 的结果保留
  - 未完成 layers 标记 `time_exhausted: true`
  - 主流程视为 block（"审计未完成不得提交"）
- 重跑时 agent 可只跑未完成的 layers（增量审计）

## 与 Chapter Gate（章节间闸门）的协作

章节间闸门（开始下一章前的验证）应同步更新：

```bash
# 下一章 Step 0 之前必须满足
ls "${PROJECT_ROOT}/正文/第${chapter_padded}章"*.md >/dev/null 2>&1 && \
test -f "${PROJECT_ROOT}/审查报告/第${chapter_padded}章审查报告.md" && \
test -f "${PROJECT_ROOT}/.webnovel/summaries/ch${chapter_padded}.md" && \
test -f "${PROJECT_ROOT}/.webnovel/audit_reports/ch${chapter_padded}.json" && \
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" \
  audit check-decision --chapter ${chapter_num} --require approve,approve_with_warnings && \
git log --oneline -1 | grep "第${chapter_num}章"
```

任一条件不满足，禁止开始下一章。新增的两个检查：
1. `audit_reports/ch{NNNN}.json` 存在
2. audit decision ∈ {approve, approve_with_warnings}（不接受 block）
