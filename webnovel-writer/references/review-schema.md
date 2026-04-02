# 审查输出 Schema（v6）

统一审查 Agent 输出格式。替代原 checker-output-schema.md 的评分制。

## 核心变化

- **无总分**：不再输出 overall_score，改为结构化问题清单
- **blocking 语义**：替代原 timeline_gate，severity=critical 默认阻断
- **单 agent**：不再区分 6 个 checker，统一由 reviewer agent 输出

## Issue Schema

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| severity | critical/high/medium/low | ✅ | 严重度 |
| category | continuity/setting/character/timeline/ai_flavor/logic/pacing/other | ✅ | 问题分类 |
| location | string | ✅ | 位置（如"第3段"） |
| description | string | ✅ | 问题描述 |
| evidence | string | ❌ | 原文引用或记忆对比 |
| fix_hint | string | ❌ | 修复建议 |
| blocking | bool | ❌ | 是否阻断（critical 默认 true） |

## 阻断规则

- 存在任何 `blocking=true` 的 issue → Step 4 不得开始
- `severity=critical` 自动 `blocking=true`
- 其余 severity 由审查 agent 根据上下文判断

## 指标沉淀

每次审查写入 `index.db.review_metrics`：
- `chapter, issues_count, blocking_count, categories, timestamp`
- 用于趋势观测，不用于 gate 决策
