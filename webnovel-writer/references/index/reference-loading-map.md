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
| webnovel-write | Step 4 | always | `skills/webnovel-write/references/writing/typesetting.md` |
| webnovel-write | Step 4 | always | `skills/webnovel-write/references/style-adapter.md` |
| webnovel-review | Step 2 | always | `references/shared/core-constraints.md` |
| webnovel-review | Step 2 | always | `references/review-schema.md` |
| webnovel-review | Step 6 | blocking issue 需用户决策 | `references/review/blocking-override-guidelines.md` |
| webnovel-plan | 章纲拆分 | always | `references/outlining/plot-signal-vs-spoiler.md` |
| webnovel-init | 卖点/题材采集 | always | `references/genre-profiles.md` |

## CSV 检索（调用 `reference_search.py`）

| Skill | Step | Trigger | 检索参数 |
|-------|------|---------|---------|
| webnovel-write | Step 2 | 本章有新角色首次出场 | `--skill write --table 命名规则 --query "角色命名" --genre {题材}` |
| webnovel-write | Step 2 | 本章有战斗/对峙场景 | `--skill write --query "战斗描写" --genre {题材}` |
| webnovel-write | Step 2 | 本章有多角色对话 | `--skill write --query "对话声线 口吻区分"` |
| webnovel-write | Step 2 | 本章有情感/心理描写 | `--skill write --query "情感描写 心理"` |
| webnovel-write | Step 2 | 本章涉及高频桥段 | `--skill write --table 场景写法 --query "{桥段类型}"` |
| webnovel-write | Step 4 | ai_flavor issue 存在 | `--skill write --query "AI味 反例 替换"` |
| webnovel-review | Step 4 | ai_flavor issue ≥ 3 | `--skill review --query "AI味 反例 替换"` |
| webnovel-plan | 卷级规划 | always | `--skill plan --table 场景写法 --query "卷级结构 叙事功能"` |
| webnovel-plan | 章纲拆分 | 新增角色出现 | `--skill plan --table 命名规则 --query "角色命名" --genre {题材}` |
| webnovel-init | 起名采集 | 用户设定角色/书名/势力名 | `--skill init --table 命名规则 --query "{命名对象} {题材}" --genre {题材}` |

## 无独立 reference 需求的 skills

| Skill | 说明 |
|-------|------|
| webnovel-query | 参考需求主要是项目私有知识（CLI、数据源），已内联 skill |
| webnovel-dashboard | P2，当前功能自洽，不挂独立 reference |
| webnovel-learn | P2，分类规则可内联 skill |
