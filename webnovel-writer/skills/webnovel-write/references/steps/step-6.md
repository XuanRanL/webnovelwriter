# webnovel-write · Step 6 审计闸门

> Round 29 Phase 2 由 SKILL.md 原文拆分（lazy-load）。进入对应 Step 时必须先加载本文件全文，
> 按其中规则执行；跨步骤硬约束 / 章节间闸门 / 充分性闸门见 SKILL.md 骨架。

### Step 6：审计闸门（Audit Gate）

> **定位**：Step 6 是 git 提交前的最后一道防线，跨步骤/跨产物/跨章审链路真实性、承诺兑现、作品连续性。完整规范见 `references/step-6-audit-gate.md` 与 `references/step-6-audit-matrix.md`（audit-agent 必读）。

Step 6 一次调用由两部分组成，**必须全部完成**：

**Part 1 — CLI 结构审计（快速路径，< 5s）**

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" \
  audit chapter --chapter ${chapter_num} --mode ${mode} \
  --out "${PROJECT_ROOT}/.webnovel/tmp/audit_layer_abg_ch${chapter_padded}.json"
```

完成 Layer A（过程真实性）、Layer B（跨产物一致性）、Layer G（跨章趋势）的确定性检查。退出码：0=pass / 1=critical fail / 2=warnings / 3=CLI 错误。

**Part 2 — audit-agent 深度审计（60-300s）**

```
Task(audit-agent, {
  chapter: <chapter_num>,
  project_root: <PROJECT_ROOT>,
  mode: <standard|fast|minimal>,
  chapter_file: <正文/第NNNN章-*.md>,
  time_budget_seconds: 300
})
```

audit-agent 自动读取 Part 1 的 JSON 输出，完成 Layer C / D / E / F 判断性检查，把 findings 写到
`.webnovel/tmp/audit_agent_findings_ch{NNNN}.json`，然后**调用 finalize CLI 完成决议与落盘**
（Round 29 Phase 4 · 决议矩阵代码计算，agent 不再自算 decision）：

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" \
  audit finalize --chapter ${chapter_num} \
  --part1 "${PROJECT_ROOT}/.webnovel/tmp/audit_layer_abg_ch${chapter_padded}.json" \
  --agent-findings "${PROJECT_ROOT}/.webnovel/tmp/audit_agent_findings_ch${chapter_padded}.json" \
  --mode ${mode}
```

finalize 确定性完成：7 层合并 → 决议矩阵（命中=warn|fail · critical→block · high≥3→block）→
`audit_reports/ch{NNNN}.json` 落盘 → `chapter_audit.jsonl` 追加。退出码 0=approve /
2=approve_with_warnings / 1=block。agent 仍负责两份人读产物：审查报告追加段 + 下章
`editor_notes/ch{NNNN+1}_prep.md`（决议非 block 时必写）。

**决议规则**：
- `decision == block` → 按 blocking_issues 的 remediation 修复，重跑对应步骤，**不得进入 Step 7**
- `decision == approve_with_warnings` → 记录 warnings，进入 Step 7，commit message 附 `[audit:warn:layerX]`
- `decision == approve` → 直接进入 Step 7

**硬要求**：
- Part 1 与 Part 2 都必须完成；即使 Part 1 失败，Part 2 仍要执行以给出完整诊断
- `audit_reports/ch{NNNN}.json` 必须成功写出（不可跳过 editor_notes 与 trend 日志）
- audit-agent 只读不写（除审计产物），禁止修改正文/设定集/state
- Step 6 超时（300s）视为未完成，block 进入 Step 7
- 禁止强制跳过（除非用户显式确认且记录到 forced_skip 字段）
