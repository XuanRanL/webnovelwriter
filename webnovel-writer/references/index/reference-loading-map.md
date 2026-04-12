# Reference Loading Map

> 本文件记录 skill → step → trigger → reference 的统一映射。
> 来源：`docs/superpowers/specs/2026-04-09-skills-restructure-and-reference-gaps.md` §6.1-6.7

---

## md 必读（直接 Read）

| Skill | Step | Trigger | Reference |
|-------|------|---------|-----------|
| webnovel-write | Step 1 | always | `references/reading-power-taxonomy.md` |
| webnovel-write | Step 1 | always | `references/genre-profiles.md` |
| webnovel-write | Step 1 | always | `skills/webnovel-write/references/style-variants.md` |
| webnovel-write | Step 2 | always | `references/shared/core-constraints.md` |
| webnovel-write | Step 2 | always | `skills/webnovel-write/references/anti-ai-guide.md` |
| webnovel-write | Step 4 | always | `skills/webnovel-write/references/polish-guide.md` |
| webnovel-write | Step 4 | ai_flavor issue 存在 | `skills/webnovel-write/references/anti-ai-guide.md` |
| webnovel-write | Step 4 | always | `skills/webnovel-write/references/writing/typesetting.md` |
| webnovel-write | Step 4 | always | `skills/webnovel-write/references/style-adapter.md` |
| webnovel-review | Step 2 | always | `references/shared/core-constraints.md` |
| webnovel-review | Step 2 | always | `references/review-schema.md` |
| webnovel-review | Step 4 | ai_flavor issue ≥ 3 | `skills/webnovel-write/references/anti-ai-guide.md` |
| webnovel-review | Step 6 | blocking issue 需用户决策 | `references/review/blocking-override-guidelines.md` |
| webnovel-plan | 章纲拆分 | always | `references/outlining/plot-signal-vs-spoiler.md` |
| webnovel-init | 卖点/题材采集 | always | `references/genre-profiles.md` |
| webnovel-init | Step 1 | always | `skills/webnovel-init/references/system-data-flow.md` |
| webnovel-init | Step 1 | always | `skills/webnovel-init/references/genre-tropes.md` |
| webnovel-init | Step 4 | always | `skills/webnovel-init/references/worldbuilding/faction-systems.md` |
| webnovel-init | Step 4 | always | `skills/webnovel-init/references/worldbuilding/world-rules.md` |
| webnovel-init | Step 5 | always | `skills/webnovel-init/references/creativity/creativity-constraints.md` |
| webnovel-init | Step 5 | always | `skills/webnovel-init/references/creativity/selling-points.md` |
| webnovel-init | Step 6 | always | `skills/webnovel-init/references/worldbuilding/setting-consistency.md` |
| webnovel-query | 所有查询 | always | `skills/webnovel-query/references/system-data-flow.md` |
| webnovel-query | 伏笔分析 | 伏笔相关查询 | `skills/webnovel-query/references/advanced/foreshadowing.md` |
| webnovel-query | 节奏分析 | 节奏相关查询 | `references/shared/strand-weave-pattern.md` |
| webnovel-query | 格式查询 | 标签相关查询 | `skills/webnovel-query/references/tag-specification.md` |

## CSV 检索（调用 `reference_search.py`）

| Skill | Step | Trigger | 检索参数 |
|-------|------|---------|---------|
| webnovel-write | Step 2 | 本章有新角色首次出场 | `--skill write --table 命名规则 --query "角色命名" --genre {题材}` |
| webnovel-write | Step 2 | 本章有战斗/对峙场景 | `--skill write --table 场景写法 --query "战斗描写" --genre {题材}` |
| webnovel-write | Step 2 | 本章有多角色对话 | `--skill write --table 写作技法 --query "对话声线 口吻区分"` |
| webnovel-write | Step 2 | 本章有情感/心理描写 | `--skill write --table 写作技法 --query "情感描写 心理"` |
| webnovel-write | Step 2 | 本章涉及高频桥段 | `--skill write --table 场景写法 --query "{桥段类型}"` |
| webnovel-plan | 卷级规划 | always | `--skill plan --table 场景写法 --query "卷级结构 叙事功能"` |
| webnovel-plan | 章纲拆分 | 新增角色出现 | `--skill plan --table 命名规则 --query "角色命名" --genre {题材}` |
| webnovel-init | 起名采集 | 用户设定角色/书名/势力名 | `--skill init --table 命名规则 --query "{命名对象} {题材}" --genre {题材}` |

## 补充说明

| Skill | 说明 |
|-------|------|
| webnovel-init | 按需 reference 较多（worldbuilding/creativity），完整清单见 skill 内引用表 |
| webnovel-query | skill 私有 reference 已完整列入上表 |
| webnovel-dashboard | P2，当前功能自洽，不挂独立 reference |
| webnovel-learn | P2，分类规则可内联 skill |
