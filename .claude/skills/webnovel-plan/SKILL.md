---
name: webnovel-plan
description: Plans detailed volume outlines with chapter-by-chapter breakdown, cool-point distribution, and Strand Weave pacing. Activates when user requests outline planning or /webnovel-plan.
allowed-tools: Read Write Edit AskUserQuestion Bash
---

# Outline Planning Skill

## Workflow Checklist

Copy and track progress:

```
大纲规划进度：
- [ ] Step 1: 加载爽点指南 (cat "${CLAUDE_PLUGIN_ROOT}/skills/webnovel-plan/references/cool-points-guide.md")
- [ ] Step 2: 加载节奏规范 (cat "${CLAUDE_PLUGIN_ROOT}/skills/webnovel-plan/references/strand-weave-pattern.md")
- [ ] Step 3: 加载题材套路 (cat "${CLAUDE_PLUGIN_ROOT}/skills/webnovel-init/references/genre-tropes.md")
- [ ] Step 4: 加载项目数据 (state.json + 总纲)
- [ ] Step 5: 确认上下文充足
- [ ] Step 6: 交互式收集需求 (AskUserQuestion)
- [ ] Step 7: 生成详细大纲
- [ ] Step 8: 质量验证
- [ ] Step 9: 保存并更新状态
```

---

## Step 1: 加载爽点指南（必须执行）

```bash
cat "${CLAUDE_PLUGIN_ROOT}/skills/webnovel-plan/references/cool-points-guide.md"
```

关键规则：
- 每章 ≥1 个小爽点（单一模式）
- 每 5 章 ≥1 个组合爽点（2种模式叠加）
- 每 10-15 章 ≥1 个里程碑爽点（改变主角地位）
- 避免连续 3 章同类型

## Step 2: 加载节奏规范（必须执行）

```bash
cat "${CLAUDE_PLUGIN_ROOT}/skills/webnovel-plan/references/strand-weave-pattern.md"
```

关键规则：
- Quest ≤5 连续章
- Fire 每 10 章内出现
- Constellation 每 15 章内出现
- 目标比例: Quest 55-65%, Fire 20-30%, Constellation 10-20%

## Step 3: 加载题材套路

```bash
cat "${CLAUDE_PLUGIN_ROOT}/skills/webnovel-init/references/genre-tropes.md"
```

## Step 4: 加载项目数据

```bash
cat .webnovel/state.json
cat 大纲/总纲.md
```

## Step 5: 确认上下文充足

**检查清单**：
- [ ] 爽点类型和密度要求已理解
- [ ] Strand Weave 比例已理解
- [ ] 主角当前状态已知
- [ ] 总纲框架已加载
- [ ] 题材套路已参考

**如有缺失 → 返回对应 Step**

## Step 6: 交互式收集需求（必须执行）

**使用 AskUserQuestion 收集**：
- 本卷核心冲突类型
- 实力提升计划
- 主要爽点类型偏好
- 感情线发展 (Fire strand)
- 金手指差异化

## Step 7: 生成详细大纲

**按需加载大纲设计参考**（推荐）：
```bash
# 章节规划指南
cat "${CLAUDE_PLUGIN_ROOT}/skills/webnovel-plan/references/outlining/chapter-planning.md"
# 冲突设计指南
cat "${CLAUDE_PLUGIN_ROOT}/skills/webnovel-plan/references/outlining/conflict-design.md"
# 大纲结构指南
cat "${CLAUDE_PLUGIN_ROOT}/skills/webnovel-plan/references/outlining/outline-structure.md"
# 情节框架参考
cat "${CLAUDE_PLUGIN_ROOT}/skills/webnovel-plan/references/outlining/plot-frameworks.md"
```

**大纲结构**：

```markdown
# 第 {volume_id} 卷：{卷名}

> **章节范围**: 第 {start} - {end} 章
> **核心冲突**: {conflict}

## 卷摘要
{2-3 段落}

## 章节详细大纲

### 第 {N} 章：{标题}
**目标**: {章节目标}
**爽点**: {类型}: {内容}
**Strand**: {Quest|Fire|Constellation}
**新增实体**: {角色/物品/地点}
**伏笔**: {埋设内容}

## Strand Weave 规划

| 章节范围 | 主导 Strand | 内容概要 |
|---------|------------|---------|
| 第1-5章 | Quest | ... |

### Strand 占比
- Quest: X% (目标: 55-65%)
- Fire: Y% (目标: 20-30%)
- Constellation: Z% (目标: 10-20%)

## 爽点密度规划

| 章节 | 爽点类型 | 内容 | 强度 |
|------|---------|------|------|
| 第1章 | 系统觉醒 | 金手指激活 | ⭐⭐⭐ |
```

## Step 8: 质量验证

**验证清单**：
- [ ] 每章有 ≥1 爽点
- [ ] 每 5 章有 ≥1 大爽点
- [ ] 无 3+ 连续同类型爽点
- [ ] Quest ≤5 连续章
- [ ] Fire 每 10 章内出现
- [ ] Constellation 每 15 章内出现

## Step 9: 保存并更新状态

保存到: `大纲/第{volume_id}卷-详细大纲.md`

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/update_state.py" \
  --volume-planned {volume_id} \
  --chapters-range "{start}-{end}"
```
