---
name: post-draft-gate
purpose: Step 2A/2B 后与 Step 7 前的硬闸门规范
---

# 起草后 · commit 前双硬闸门

> 本文件规定 `scripts/post_draft_check.py` 与 `scripts/pre_commit_step_k.py` 的职责、配置与使用方式。两个脚本都是 **通用版**（随 plugin 分发到所有项目），通过项目侧的 JSON 配置文件做项目特化。
>
> 引入背景（2026-04-15）：Ch1 write 流程审计发现 13 个问题，其中 7 类属于"起草期机械污染"或"commit 前设定集脱节"。原先只能靠 Step 3 内部 13 checker + 外部多模型审查（Round 13 v2 = 9 模型；Round 14+ = 14 模型）被动发现，浪费审查算力。引入双硬闸门后，这 7 类问题在起草/commit 的 1 秒内即被拦截。

## 一、Step 2A/2B 后硬闸门 · `post_draft_check.py`

### 职责

起草或风格适配完成后、进入 Step 3 审查前，拦截 7 类起草期污染。

### 触发点

- Step 2A 完成后（起草完）必跑
- Step 2B 完成后（风格适配完）再跑一次（转译可能引入新问题）

### 7 类检查

| # | 检查项 | 默认值 | 项目配置字段 |
|---|---|---|---|
| 1 | ASCII 双引号 | 必须 = 0 | 无（硬约束） |
| 2 | U+FFFD 替换字符 | 必须 = 0 | 无（硬约束） |
| 3 | Markdown 标题/分隔/粗体 | 必须 = 0 | 无（硬约束） |
| 4 | 章号敏感禁用词 | 项目配置 | `forbidden_terms_by_chapter.{N}` |
| 5 | 破例预算 | 项目配置 | `break_budget_by_chapter.{N}` |
| 6 | 必须伏笔种子（正则） | 项目配置 | `required_seeds_by_chapter.{N}` |
| 7 | 字数区间 | state.json | `average_words_per_chapter_min/max` |

### 项目侧配置：`.webnovel/post_draft_config.json`

```json
{
  "forbidden_terms_by_chapter": {
    "1": {
      "守夜人": "Ch1 只能出现 #4732，守夜人三字延后到 Ch3",
      "桃源空间": "Ch3 才首次进入"
    }
  },
  "break_budget_by_chapter": {
    "1": {"老子": 1, "他妈": 0}
  },
  "required_seeds_by_chapter": {
    "1": [
      ["你不是第一个", "A3 伏笔 · 系统首发必须含此短语"],
      ["#4732", "A2 伏笔 · 系统编号"]
    ]
  }
}
```

未提供配置时只跑 5 项通用检查（ASCII/FFFD/Markdown/字数/空文件）。

### 调用方式

```bash
python -X utf8 "${SCRIPTS_DIR}/post_draft_check.py" ${chapter_num} \
  --project-root "${PROJECT_ROOT}"
```

退出码：
- 0 全通过（可进入 Step 3）
- 1 hard fail（必须修到通过才进入 Step 3）
- 2 结构错误（文件缺失等）

### 修复指南

| 问题类型 | 修复方式 |
|---|---|
| ASCII_QUOTE | `scripts/quote_pair_fix.py` 批量替换 |
| FFFD | Grep 定位后 Edit 补 |
| MARKDOWN | 移除 # / --- / ** 字符 |
| FORBIDDEN | 改写避开禁用词 |
| BREAK_BUDGET | 改写主角台词 |
| REQUIRED_SEED | Edit 补入缺失的伏笔句 |
| WORD_COUNT | 扩写或压缩到区间内 |

---

## 二、Step 7 commit 前硬闸门 · `pre_commit_step_k.py`

### 职责

commit 前核对 Data Agent Step K（设定集 Markdown 追加）是否完成。

### 问题根源

Data Agent 的 Step K（Settings Sync）负责追加新增实体/状态到设定集 Markdown（如伏笔追踪.md/资产变动表.md/主角卡.md）。但实际实现中 Step K 把 Markdown append 责任**推给主 agent**，而主 agent 常忘记做。若不检查：
- 设定集 md 与 state.json 长期脱节
- 下章 context-agent 读取时看不到上一章的新增
- 质量连锁下降（伏笔断层、资产跳变、人物状态矛盾）

### 2 类检查

| # | 检查项 | 项目配置字段 |
|---|---|---|
| 1 | 核心设定集文件含 `[Ch{N}]` 标注 | `target_files` |
| 2 | `chapter_meta.foreshadowing_planted` 里 ID 在伏笔追踪.md 可查 | `check_foreshadowing_ids` |

### 项目侧配置：`.webnovel/step_k_config.json`

```json
{
  "target_files": [
    "设定集/伏笔追踪.md",
    "设定集/资产变动表.md",
    "设定集/主角卡.md"
  ],
  "check_foreshadowing_ids": true
}
```

未提供配置时使用默认 3 文件。

### 调用方式

```bash
python -X utf8 "${SCRIPTS_DIR}/pre_commit_step_k.py" ${chapter_num} \
  --project-root "${PROJECT_ROOT}"
```

退出码：
- 0 追加完整（可 commit）
- 1 追加遗漏（阻塞 commit）
- 2 结构错误（state.json 损坏等）

### 修复指南

- 按 `chapter_meta.new_entities / foreshadowing_planted` 逐条追加到 Markdown
- 格式：`[Ch{N}]` 标注行 或 表格新增 `[Ch{N}]` 列
- 参考最近一章的追加格式

---

## 三、两个闸门的共同设计原则

### 通用化 + 项目特化

- 脚本本体（随 plugin 分发）= 通用骨架 + 7 类 / 2 类检查器
- 项目配置（项目侧 JSON）= 章号敏感的禁用词/种子/破例预算/目标文件
- 结果：**一次开发，多项目复用**——不同题材只需改 JSON 配置

### 前置拦截 > 事后修复

- 起草污染在 Step 2A 后 1 秒被抓 vs Step 3 审查后 2 分钟才抓
- 节省 13 checker + 外部多模型（Round 14+ = 14 模型）的算力在软质量（文笔/情感 · Round 13 v2）
- 节省 Step 4 润色的人工注意力

### 硬 block 的哲学

- 技术上可绕过（删除脚本），但硬 block 建立"质量纪律"
- 主 agent 习惯性跑闸门 = 下章不再犯同类错

---

## 四、与其它 hooks 的配合

### hygiene_check.py（项目本地 shim）

项目本地的 `.webnovel/hygiene_check.py` 负责在写章模式下串行跑：
1. plan_consistency_check（规划层一致性）
2. post_draft_check（起草后污染）
3. pre_commit_step_k（Step K 追加）

任一 hard fail 阻塞 `hygiene_check 1` 的 exit=0，从而阻塞 Step 7 的 commit。

### extract_chapter_context.py

Step 2A 执行包已含全部禁用词/种子/破例预算信息——起草时 context-agent 应该主动规避，post_draft_check 是 **兜底**（agent 忘了规避时的拦截）。

---

## 五、版本历史

- **2026-04-15 v1**：初版发布
  - 基于《末世重生》项目 Ch1 write 流程的 13 问题审计
  - 覆盖 7 类起草污染 + 2 类 Step K 追加
  - 文档：`.webnovel/migrations/20260415_ch1_write_audit.md`（项目侧）
