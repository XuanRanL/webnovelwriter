---
name: webnovel-query
description: 查询项目设定、角色、力量体系、势力、伏笔等信息。支持紧急度分析与金手指状态查询。
allowed-tools: Read Grep Bash AskUserQuestion
---

# Information Query Skill

## Use when

用户询问关于故事设定、角色、力量体系、势力、伏笔、金手指、节奏等项目内信息时触发。

## 项目根保护

```bash
export WORKSPACE_ROOT=”${CLAUDE_PROJECT_DIR:-$PWD}”
export SCRIPTS_DIR=”${CLAUDE_PLUGIN_ROOT}/scripts”
export SKILL_ROOT=”${CLAUDE_PLUGIN_ROOT}/skills/webnovel-query”
export PROJECT_ROOT=”$(python “${SCRIPTS_DIR}/webnovel.py” --project-root “${WORKSPACE_ROOT}” where)”
```

- `PROJECT_ROOT` 必须包含 `.webnovel/state.json`
- **禁止**在 `${CLAUDE_PLUGIN_ROOT}/` 下读取或写入项目文件

## 查询类型识别

| 关键词 | 查询类型 | 数据源 |
|--------|---------|--------|
| 角色/主角/配角 | 标准查询 | 主角卡.md, 角色库/ |
| 境界/筑基/金丹 | 标准查询 | 力量体系.md |
| 宗门/势力/地点 | 标准查询 | 世界观.md |
| 伏笔/紧急伏笔 | 伏笔分析 | state.json + foreshadowing.md |
| 金手指/系统 | 金手指状态 | state.json |
| 节奏/Strand | 节奏分析 | state.json + strand-weave-pattern.md |
| 标签/实体格式 | 格式查询 | tag-specification.md |

## 引用加载策略

先识别查询类型，再按需加载：

| 查询类型 | Reference |
|---------|-----------|
| 所有查询 | `references/system-data-flow.md` |
| 伏笔分析 | `references/advanced/foreshadowing.md` |
| 节奏分析 | `references/shared/strand-weave-pattern.md` |
| 格式查询 | `references/tag-specification.md` |

不得同时加载两个以上 L2 文件，除非用户请求明确跨多类型。

## 查询流程

1. **识别查询类型**：根据用户关键词匹配上表
2. **加载参考**：只加载该类型需要的 reference
3. **加载数据**：`cat “$PROJECT_ROOT/.webnovel/state.json”`
4. **确认上下文充足**：查询类型已识别 + 参考已加载 + state 已加载
5. **执行查询**：按类型检索对应数据源
6. **格式化输出**：按下方模板输出

## 输出格式

```markdown
# 查询结果：{关键词}

## 概要
- **匹配类型**: {type}
- **数据源**: state.json + 设定集 + 大纲
- **匹配数量**: X 条

## 详细信息
{结构化数据，含文件路径和行号}

## 数据一致性检查
{state.json 与静态文件的差异，若无差异则省略}
```

## 边界与失败恢复

- 只读操作，不修改任何项目文件
- 若数据源缺失，明确告知用户缺少什么文件
- 若查询无匹配，返回空结果并建议检查范围
