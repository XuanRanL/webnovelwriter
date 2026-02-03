# CLAUDE.md - Webnovel Writer 项目指南

> 本文档为 Claude Code 提供项目上下文。

## 项目概述

**Webnovel Writer** 是基于 Claude Code 的长篇网文辅助创作系统（v5.5），解决 AI 写作中的"遗忘"和"幻觉"问题。

## 核心原则（仅3条）

1. **大纲即法律** - 100%执行大纲，不擅自发挥
2. **设定即物理** - 能力/境界不能超设定
3. **新实体需记录** - 新角色/物品/地点要入库

> 其他都是建议，不是强制。Claude 已经很懂网文写作。

## 关键目录

```
.claude/
├── agents/                 # Agent 定义
│   ├── context-agent.md    # 上下文搜集
│   ├── data-agent.md       # 数据处理
│   └── *-checker.md        # 各类检查器
├── skills/                 # Skill 定义
│   └── webnovel-write/     # 主写作流程
├── scripts/                # Python 脚本
│   └── data_modules/       # 数据模块
└── references/             # 参考文档（按需加载）
```

## 核心命令

| 命令 | 说明 |
|------|------|
| `/webnovel-init` | 初始化项目 |
| `/webnovel-plan` | 规划大纲 |
| `/webnovel-write` | 创作章节 |
| `/webnovel-review` | 质量审查 |
| `/webnovel-query` | 信息查询 |

## 写作流程

```
1. Context Agent → 创作任务书（5个板块）
2. 写作 → 3000-5000字正文
3. 审查 → 根据章节类型选择 Checker
4. 润色 → 修复问题
5. Data Agent → 提取数据
6. Git → 备份
```

## 审查深度（按章节类型）

| 章节类型 | Checker 数量 | 说明 |
|----------|-------------|------|
| 高潮章 | 6 个全跑 | 重要章节全面检查 |
| 标准章 | 3-4 个 | consistency + continuity + 按需 |
| 过渡章 | 2 个 | consistency + continuity 即可 |

## 数据存储

- `state.json` - 精简状态（进度、主角、章节元数据）
- `index.db` - SQLite（实体、别名、关系、状态变化）
- `vectors.db` - RAG 向量索引
- `summaries/` - 章节摘要

## 常用命令

```bash
# 查询统计
python -m data_modules.index_manager stats --project-root "."

# 获取核心实体
python -m data_modules.index_manager get-core-entities --project-root "."

# 搜索
python -m data_modules.rag_adapter search --query "xxx" --project-root "."
```

## 关键文件

| 文件 | 说明 |
|------|------|
| `.webnovel/state.json` | 项目状态 |
| `.webnovel/index.db` | SQLite 索引 |
| `.claude/references/reading-power-taxonomy.md` | 追读力分类（按需加载） |
| `.claude/references/genre-profiles.md` | 题材配置（按需加载） |
