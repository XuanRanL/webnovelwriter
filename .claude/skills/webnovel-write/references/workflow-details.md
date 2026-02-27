# Webnovel Write - Workflow Details

## Contents
- 模式与步骤映射
- Step 1.5 章节设计
- Step 2B 风格适配器
- Step 3 审查模板（按模式）
- Step 4 润色执行细则（含 Phase 1）
- Step 5 债务与利息开关

## 模式与步骤映射

- 标准模式：Step 1 → 1.5 → 2A → 2B → 3 → 4 → 5 → 6
- `--fast`：Step 1 → 1.5 → 2A → 3 → 4 → 5 → 6（跳过 Step 2B）
- `--minimal`：Step 1 → 1.5 → 2A → 3（3个基础审查）→ 4 → 5 → 6

说明：
- `--minimal` 不运行 `reader-pull-checker`、`high-point-checker`、`pacing-checker`。
- `--minimal` 不生成追读力专项结论，但仍应生成 `overall_score` 供 Step 5 使用。

## Step 1.5 章节设计（标准/关键章建议执行）

加载参考：
```bash
cat "${CLAUDE_PLUGIN_ROOT}/skills/webnovel-write/references/style-variants.md"
cat "${CLAUDE_PLUGIN_ROOT}/references/reading-power-taxonomy.md"
cat "${CLAUDE_PLUGIN_ROOT}/references/genre-profiles.md"
cat "${CLAUDE_PLUGIN_ROOT}/skills/webnovel-write/references/writing/genre-hook-payoff-library.md"
```

输出结构（必须覆盖 Scene–Sequel 最小闭环）：
- 目标（20字以内）
- 阻力（20字以内）
- 代价（20字以内）
- 本章变化（30字以内，优先可量化变化：关系/资源/风险/地位/能力）
- 章末未闭合问题（30字以内；必须与钩子类型/强度一致）
- 核心冲突一句话
- 开头类型（冲突/悬疑/动作/对话/氛围）
- 情绪节奏（低→高/高→低/低→高→低/平稳）
- 信息密度（low/medium/high）
- 是否过渡章（true/false）
- 追读力设计：钩子类型/强度、微兑现清单、爽点模式

差异化检查：
- 钩子类型避免与最近 3 章重复
- 开头类型避免与最近 3 章重复
- 爽点模式避免与最近 5 章过度重复

题材快速调用（电竞/直播文/克苏鲁）：
- 先从 `genre-hook-payoff-library.md` 选 1 条章末钩子。
- 再选 1-2 条微兑现，优先与本章核心冲突同方向。
- 若连续两章使用同类型钩子，必须在“对象/代价/结果”至少变更一项。

如必须重复，记录 Override 理由并给出差异化执行方式。

## Step 2B 风格适配器（`--fast` / `--minimal` 可跳过）

```bash
cat "${CLAUDE_PLUGIN_ROOT}/skills/webnovel-write/references/style-adapter.md"
```

目标：不改剧情事实，只提升网文口感与张力。

执行清单（网文增强）：
- 保证章首 300 字内交代“目标 + 阻力”。
- 按 600-900 字间隔埋入微兑现，避免长段无反馈。
- 章内至少出现 1 次可量化变化（关系/资源/风险/地位）。
- 章末钩子优先“选择钩/危机钩”，并与下章目标可衔接。
- 直播/电竞题材增加“外部反馈（弹幕/舆论/比分）→ 主角决策”链路。

## Step 3 审查模板（按模式）

调用约束：
- 必须使用 `Task` 工具调用审查 subagent，禁止主流程直接给出“审查结论”。
- 审查阶段先并行调用，再聚合结果；`overall_score` 必须来自聚合结果。

Task 调用模板（示意）：
```text
Task("consistency-checker", {chapter, chapter_file, project_root})
Task("continuity-checker", {chapter, chapter_file, project_root})
Task("ooc-checker", {chapter, chapter_file, project_root})
Task("reader-pull-checker", {chapter, chapter_file, project_root})   # minimal 跳过
Task("high-point-checker", {chapter, chapter_file, project_root})    # 可选
Task("pacing-checker", {chapter, chapter_file, project_root})        # 可选
```

审查汇总表格：
```text
┌─────────────────────────────────────────────────┐
│ 审查汇总 - 第 {chapter_num} 章                  │
├──────────────────────┬───────────┬──────────────┤
│ Agent                │ 结果      │ 关键问题数   │
├──────────────────────┼───────────┼──────────────┤
│ consistency-checker  │ PASS/FAIL │ {N}          │
│ continuity-checker   │ PASS/FAIL │ {N}          │
│ ooc-checker          │ PASS/FAIL │ {N}          │
│ reader-pull-checker* │ PASS/FAIL │ {N}          │
│ high-point-checker** │ PASS/FAIL │ {N}          │
│ pacing-checker**     │ PASS/FAIL │ {N}          │
├──────────────────────┴───────────┴──────────────┤
│ critical issues: {N} | high issues: {N}         │
│ 是否可进入润色: {是/否}                          │
└─────────────────────────────────────────────────┘
```

标注说明：
- `*` 标准模式启用；`--minimal` 不启用。
- `**` 关键章/卷末/用户明确要求时启用。

审查指标 JSON（标准/fast）：
```json
{
  "start_chapter": {chapter_num},
  "end_chapter": {chapter_num},
  "overall_score": 48,
  "dimension_scores": {
    "爽点密度": 8,
    "设定一致性": 7,
    "节奏控制": 7,
    "人物塑造": 8,
    "连贯性": 9,
    "追读力": 9
  },
  "severity_counts": {"critical": 1, "high": 2, "medium": 3, "low": 1},
  "critical_issues": ["设定自相矛盾"],
  "report_file": "",
  "notes": ""
}
```

审查指标 JSON（`--minimal`）：
```json
{
  "start_chapter": {chapter_num},
  "end_chapter": {chapter_num},
  "overall_score": 52,
  "dimension_scores": {
    "设定一致性": 8,
    "人物塑造": 7,
    "连贯性": 8
  },
  "severity_counts": {"critical": 0, "high": 1, "medium": 2, "low": 1},
  "critical_issues": [],
  "report_file": "",
  "notes": "minimal mode without reader-pull/high-point/pacing"
}
```

保存审查指标：
```bash
python -m data_modules.index_manager save-review-metrics --data '{...}' --project-root "."
```

## Step 4 润色执行细则（含 Phase 1）

第一优先级（必须先做）：
- 修复审查报告中的 `critical`。
- 修复 `high`，如无法修复必须记录 deviation。

第二优先级（网文化硬规则）：
- 开头 120 字出现冲突/风险/强情绪。
- 每 800-1200 字至少一次局面变化。
- 结尾 80-150 字设置钩子。
- 对话每句带意图。
- 连续 400 字纯解释必须打散。

第三优先级（Phase 1：Anti-AI + No-Poison）：
- 词库采用“抽样检查”而非全量扫描，至少覆盖章首/章中/章末。
- 禁止三段式说明句（首先/其次/最后）。
- 对话去说明书化，保留试探/回避/施压等意图。
- 检查 5 类毒点红线（降智推进/强行误会/圣母无底线/工具人配角/双标裁决）。
- 不得破坏“大纲即法律 / 设定即物理”。

润色完成清单：
- [ ] critical 已修复
- [ ] high 已修复或记录 deviation
- [ ] 网文化硬规则通过
- [ ] Phase 1 抽样检查已完成
- [ ] 未触发毒点红线或已补充代价说明

## Step 5 债务与利息开关

- 默认不计算利息。
- 仅在“开启债务追踪”或用户明确要求时执行：

```bash
python -m data_modules.index_manager accrue-interest --current-chapter {chapter_num} --project-root "."
```
