---
name: webnovel-write
description: Writes webnovel chapters (3000-5000 words). Gathers context, writes draft, reviews quality, extracts data. Use when user wants to write a chapter or /webnovel-write.
allowed-tools: Read Write Edit Grep Bash Task
---

# Chapter Writing Skill

## Quick Start

```
章节创作流程：
1. Context Agent → 创作任务书
2. 写作 → 3000-5000字正文
3. 审查 → 发现问题
4. 润色 → 修复问题
5. Data Agent → 提取数据
6. Git → 备份
```

## 核心原则（仅3条）

1. **大纲即法律** - 100%执行大纲，不擅自发挥
2. **设定即物理** - 能力/境界不能超设定
3. **新实体需记录** - 新角色/物品/地点要入库

> 其他都是建议，不是强制。Claude 已经很懂网文写作。

---

## Step 1: Context Agent

调用 `context-agent` 获取创作任务书：
- 本章大纲要点
- 上章钩子（需要接住）
- 出场角色状态
- 场景/能力约束

**失败时**: 手动读取大纲和 state.json 继续。

---

## Step 2: 写作

**输出**: `正文/第{NNNN}章.md`，3000-5000字

**写作建议**（非强制）:
- 开头尽快进入状态（冲突/悬念/动作）
- 章末留个钩子让读者想看下一章
- 避免大段解释，用动作和对话推进

**按需加载参考**（仅在需要时读取）:
- 战斗戏 → `references/writing/combat-scenes.md`
- 情感戏 → `references/writing/emotion-psychology.md`
- 对话密集 → `references/writing/dialogue-writing.md`

---

## Step 3: 审查

根据章节类型选择审查深度：

| 章节类型 | 推荐 Checker | 说明 |
|----------|-------------|------|
| **高潮章** | 全部 6 个 | 重要章节全面检查 |
| **标准章** | 3-4 个 | consistency + continuity + ooc + 按需 |
| **过渡章** | 2 个 | consistency + continuity 即可 |

**核心 Checker**（建议始终运行）:
- `consistency-checker` - 设定是否矛盾
- `continuity-checker` - 前后是否连贯

**可选 Checker**（按需运行）:
- `ooc-checker` - 角色是否失真
- `pacing-checker` - 节奏是否拖沓
- `high-point-checker` - 爽点是否足够
- `reader-pull-checker` - 追读力是否到位

**输出**: 简要汇总发现的问题，按严重度排序。

---

## Step 4: 润色

**必须修复**: 设定矛盾、逻辑漏洞、严重 OOC
**建议修复**: 节奏问题、爽点不足
**可选修复**: 风格建议、微调优化

加载 `references/polish-guide.md` 获取润色技巧。

---

## Step 5: Data Agent

调用 `data-agent` 处理数据链：
- 提取出场实体
- 记录状态变化
- 生成章节摘要
- 向量索引

**失败时**: 记录 warning，继续 Git 备份。

---

## Step 6: Git 备份

```bash
git add . && git commit -m "Ch{N}: {title}"
```

---

## 模式选项

```
/webnovel-write           # 标准：完整流程
/webnovel-write --fast    # 快速：跳过可选审查
/webnovel-write --minimal # 极简：仅核心2个Checker
```

---

## 详细参考（按需加载）

需要更多指导时，读取以下文件：

| 需求 | 文件 |
|------|------|
| 网文口感规则 | `references/polish-guide.md` |
| 追读力设计 | `references/reading-power-taxonomy.md` |
| 题材配置 | `references/genre-profiles.md` |
| 风格变体 | `references/style-variants.md` |
