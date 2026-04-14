# Story System 最终收束 Spec

> **日期**: 2026-04-14
> **状态**: 草案 v1
> **定位**: 基于当前代码真实状态，把 Story System 从“半成品并存”收束到“六层主链 + 消费端同步”的最终 spec

---

## 1. 文档定位

### 1.1 这份 spec 解决什么问题

前面的文档已经分别回答了三个问题：

- [`current-system-diagnosis.md`](../../architecture/current-system-diagnosis.md)
  - 当前系统哪里散、哪里重复、哪里有半成品
- [`2026-04-12-story-system-evolution-spec.md`](./2026-04-12-story-system-evolution-spec.md)
  - 六层主链应该长什么样
- [`2026-04-14-context-agent-writing-brief-design.md`](./2026-04-14-context-agent-writing-brief-design.md)
  - 写前任务书入口怎么收束

这份 spec 解决的是更直接的问题：

> 在不考虑向后兼容的前提下，如何把现在的代码、CSV、合同、提交链、投影链和消费端，一次性收束到最终可用状态。

### 1.2 一句话结论

这次收束的目标不是“再补一个模块”，而是：

- 六层全做
- 旧散写路径直接删
- `context_manager` 降级为纯 JSON 组装器
- `CSV_CONFIG + 裁决表 + 合同树 + commit/projection` 成为唯一主链
- 所有消费者只吃合同和投影视图

---

## 2. 已确认的关键决策

这轮 brainstorming 已经确认以下决策，不再反复摇摆：

### 2.1 范围

- 做 **六层全覆盖**
- 不只改代码层
- 必须同步改 skill / agent / CLI / eval / docs 等消费端

### 2.2 向后兼容

- **不考虑向后兼容**
- 旧散写路径、旧直读路径、旧 fallback 路径，能删就删
- 不保留 deprecated 双路径

### 2.3 `context_manager`

- 降级为 **纯 JSON payload 组装器**
- 不再负责 text 渲染
- 不再保留为旧说明书式文本输出服务的 snapshot 逻辑

### 2.4 `CSV_CONFIG`

- 放在 `reference_search.py` 里
- 形态模仿 `ui-ux-pro-max/core.py`
- 每张表显式声明 `file / search_cols / output_cols / poison_cols / role`

### 2.5 裁决层

- 新建独立 `裁决规则.csv`
- key 为题材
- 它回答的是“命中后怎么裁决、优先谁、注入哪层”，不是“查哪些表”

### 2.6 `anti-ai-guide.md` 与 `core-constraints.md`

- `anti-ai-guide.md` 保留为 md 真源
  - 不拆 CSV
  - 不给消费者直读
  - 只在需要的步骤被上游吸收后转写
- `core-constraints.md` 不再整篇读取
  - 拆成具体约束
  - 分步骤落到合同、runtime、review、commit 校验和消费端文案里

### 2.7 消费端真源

- 所有消费者只允许直接吃：
  - 合同树
  - `CHAPTER_COMMIT`
  - 投影视图
- 不再允许运行时直接读 CSV / md / reference 来补洞

### 2.8 首批题材范围

这次先做好 7 个题材：

1. 西方奇幻
2. 东方仙侠
3. 科幻末世
4. 都市日常
5. 都市修真
6. 都市高武
7. 历史古代

其余题材不在本轮收束范围内。

### 2.9 实施顺序

- 从底层往上推
- 走串行，不走并行
- 先把基础收稳，再做消费者同步

---

## 3. 总体链路

最终链路固定为：

```text
知识表 / 裁决表
        ↓
CSV_CONFIG + reference_search
        ↓
story_system_engine
        ↓
MASTER / VOLUME / CHAPTER / REVIEW
        ↓
context_manager（只出 JSON）
        ↓
context-agent（按示例写任务书）
        ↓
webnovel-write Step 2（只吃任务书）
        ↓
review / data-agent
        ↓
CHAPTER_COMMIT
        ↓
projection writers
        ↓
state / index / summaries / memory / vector
```

这里有两个硬边界：

1. 消费端不再运行时直读知识层
2. 写后事实只允许经 `CHAPTER_COMMIT -> projection` 进入各存储

---

## 4. Section 1：`CSV_CONFIG` 注册层

### 4.1 要做什么

在 `reference_search.py` 里引入注册式 `CSV_CONFIG`，替代当前全局硬编码的：

- `_SEARCH_FIELD_WEIGHTS`
- `_CONTENT_COLUMNS`

改成每张表自己定义：

- `file`
- `search_cols`
- `output_cols`
- `poison_cols`
- `role`

### 4.2 目标形态

```python
CSV_CONFIG = {
    "命名规则": {
        "file": "命名规则.csv",
        "search_cols": ["关键词", "意图与同义词", "核心摘要"],
        "output_cols": ["编号", "命名对象", "核心摘要", "大模型指令", "详细展开"],
        "poison_cols": ["毒点"],
        "role": "base",
    },
    "场景写法": {
        "file": "场景写法.csv",
        "search_cols": ["关键词", "意图与同义词", "核心摘要"],
        "output_cols": ["编号", "模式名称", "核心摘要", "大模型指令", "详细展开"],
        "poison_cols": ["毒点"],
        "role": "base",
    },
    "题材与调性推理": {
        "file": "题材与调性推理.csv",
        "search_cols": ["题材关键词", "别名"],
        "output_cols": ["题材", "默认调性", "推荐基础表", "推荐动态表"],
        "poison_cols": ["毒点"],
        "role": "route",
    },
    "裁决规则": {
        "file": "裁决规则.csv",
        "search_cols": ["题材"],
        "output_cols": [
            "题材",
            "风格优先级",
            "爽点优先级",
            "节奏默认策略",
            "毒点权重",
            "冲突裁决",
            "contract注入层",
            "反模式",
        ],
        "poison_cols": [],
        "role": "reasoning",
    },
}
```

### 4.3 改动要求

- `reference_search.py`
  - 改为从 `CSV_CONFIG` 读取 per-table 配置
- `story_system_engine.py`
  - 不再内部硬编码表角色
  - 改为使用 `CSV_CONFIG`
- 新增校验脚本
  - 校验 `CSV_CONFIG`
  - 校验 CSV 表头
  - 校验 `README.md`

### 4.4 验收

- 同一 CLI 在不同表上确实用的是不同 `search_cols`
- `CSV_CONFIG` 的每张表字段都能在 CSV 头里找到
- 校验脚本通过

---

## 5. Section 2：CSV 内容修补

### 5.1 要做什么

对现有表做一次统一审计和修补，让它们能稳定被裁决层和合同层消费。

### 5.2 重点问题

- 毒点列命名不统一
- 路由表字段不足
- 同义词填充不足
- 各题材覆盖不均衡

### 5.3 具体改造

#### 5.3.1 毒点列统一

把以下旧列统一改名为 `毒点`：

- `反面写法`
- `忌讳写法`
- `常见误区`
- `常见崩盘误区`

#### 5.3.2 路由表补字段

`题材与调性推理.csv` 至少补齐：

- `推荐基础表`
- `推荐动态表`
- `默认调性`
- `风格锚点`

#### 5.3.3 内容补全规则

所有补全都手工做，不写自动迁移脚本。

最低要求：

- 每张表至少覆盖这 7 个题材的常见场景
- 每条 `意图与同义词` 至少 3 个同义表达
- 每条 `毒点` 非空

#### 5.3.4 README 同步

`README.md` 必须同步更新：

- 毒点列统一命名
- 路由表新字段
- 各表 schema 描述

### 5.4 验收

- 所有表的毒点列统一叫 `毒点`
- 路由表能返回推荐基础表和动态表
- `README` 与 `CSV_CONFIG` 对齐

---

## 6. Section 3：裁决表

### 6.1 要做什么

新建 `裁决规则.csv`，作为独立 `Reasoning Layer`。

它不负责“查哪些表”，只负责：

- 多条命中后怎么选
- 哪类爽点优先
- 哪类毒点更致命
- 结果注入合同树哪一层

### 6.2 与路由表的边界

- 路由表：回答“查哪些表”
- 裁决表：回答“查到之后怎么用”

这正是 `ui-ux-pro-max` 里：

- `products.csv`
- `ui-reasoning.csv`

的对应关系。

### 6.3 字段

`裁决规则.csv` 至少包含：

- `题材`
- `风格优先级`
- `爽点优先级`
- `节奏默认策略`
- `毒点权重`
- `冲突裁决`
- `contract注入层`
- `反模式`

### 6.4 首批覆盖

先覆盖 7 个题材，各 1 行。

### 6.5 验收

- `source_trace` 能追溯到裁决表
- 多表命中时，顺序符合 `冲突裁决`
- 同题材输出能解释“为什么是这些条目进入合同”

---

## 7. Section 4：engine 接入裁决表

### 7.1 当前问题

现在的 `story_system_engine.build()` 只有：

1. 路由
2. 检索
3. 直接组装

没有显式裁决层。

### 7.2 目标流程

改成：

1. `_route()`
2. `_collect_tables()`
3. `_load_reasoning()`
4. `_apply_reasoning()`
5. `_rank_anti_patterns()`
6. `_assemble_contract()`

### 7.3 新增方法

- `_load_reasoning(genre)`
- `_apply_reasoning(reasoning, base, dynamic)`
- `_rank_anti_patterns(reasoning, ...)`
- `_assemble_contract(ranked, anti_patterns, reasoning)`

### 7.4 `source_trace`

最终进入合同的内容都要带：

- `source_table`
- `source_id`
- `reasoning_rule`
- `priority_rank`
- `inject_target`

### 7.5 验收

- `writing_guidance` 顺序符合裁决表
- `source_trace` 都有 `reasoning_rule`
- 低优先级冲突条目能被过滤或降级

---

## 8. Section 5：`context_manager` 瘦身

### 8.1 目标

把 `context_manager.py` 从：

- 数据组装
- 文本渲染
- snapshot 缓存
- checklist/评分说明书

降级为：

- **纯 JSON payload 组装器**

### 8.2 保留职责

- 读 contracts
- 读 runtime sources
- 组装 `genre_profile`
- 组装 `writing_guidance`
- 组装 `reader_signal`
- 组装 `plot_structure`
- 组装 `prewrite_validation`
- 返回统一 dict

### 8.3 删除职责

- 所有 `_render_*`
- 所有旧说明书式 text 输出
- 为 text 渲染服务的 snapshot 管理
- 与已拆 builder 重复的内联逻辑

### 8.4 输出形态

`build_context()` 只返回：

```json
{
  "meta": {"context_contract_version": "v3", "chapter": 12},
  "story_contract": {},
  "runtime_status": {},
  "latest_commit": {},
  "prewrite_validation": {},
  "plot_structure": {},
  "scene": {},
  "writing_guidance": {},
  "reader_signal": {},
  "genre_profile": {},
  "long_term_memory": {},
  "core": {}
}
```

### 8.5 相关要求

- `snapshot_manager.py`
  - 若无其他消费方，整文件删除
- `extract_chapter_context.py`
  - 不再承担旧审计式文本说明书职责
- 最终写作任务书
  - 由 `context-agent` 直接根据 JSON payload + 示例生成

### 8.6 验收

- `context_manager.py` 行数压到 400 行以下
- 不再有字符串拼接型说明书输出
- snapshot 逻辑已删除

---

## 9. Section 6：旧散写路径清理

### 9.1 问题

现在仍有两条写入路径并存：

- 新链：`data-agent -> chapter-commit -> projection`
- 旧链：skill / agent 直接写 `state / index / summaries / memory`

这必须收束成一条。

### 9.2 要删的路径

#### `webnovel-write`

- Step 2 直接 `state set-chapter-status`
- Step 4 直接 `state set-chapter-status`

#### 其他直写入口

- skill / agent 中任何 `index process-chapter`
- data-agent 中任何直接写 `state/index/memory` 的描述

### 9.3 合法直写保留

只保留：

- `webnovel-init`
- `webnovel-plan`
- 运维类人工修复命令

都不在创作主链内。

### 9.4 `chapter_status`

不再由 skill 分步手推。

改成：

- accepted commit -> projection 推到 `chapter_committed`
- rejected commit -> projection 推到 `chapter_rejected`

### 9.5 验收

- `skills/` 和 `agents/` 里不再有 `state set-chapter-status`
- `skills/` 和 `agents/` 里不再有 `index process-chapter`
- 各存储只由对应 projection writer 写入

---

## 10. Section 7：projection 层收束

### 10.1 目标

确认 `CHAPTER_COMMIT -> projection` 是唯一写入链路，并补完 event 路由覆盖。

### 10.2 要做的事

#### 10.2.1 补全 `EventProjectionRouter`

对照 `story_event_schema.py`，确保事件类型覆盖完整。

#### 10.2.2 `chapter_status` 统一由 `state_projection_writer` 推进

- accepted -> `chapter_committed`
- rejected -> `chapter_rejected`

#### 10.2.3 `projection_status` 回写 commit

最终 commit 文件里不允许残留 `pending`。

#### 10.2.4 失败隔离

单个 writer 失败：

- 不阻断其他 writer
- 失败项写 `failed`
- 允许只补跑失败 writer

### 10.3 验收

- `projection_status` 最终都是 `done / failed / skipped`
- accepted commit 后状态自动推进
- 单个 writer 失败不拖死全链

---

## 11. Section 8：消费端同步

### 11.1 要改的文件

- `agents/context-agent.md`
- `agents/data-agent.md`
- `agents/reviewer.md`（必要时）
- `skills/webnovel-write/SKILL.md`
- `skills/webnovel-review/SKILL.md`
- `skills/webnovel-query/SKILL.md`
- `skills/webnovel-plan/SKILL.md`（检查）
- `skills/webnovel-init/SKILL.md`（检查）
- `skills/webnovel-dashboard/SKILL.md`
- `skills/webnovel-write/evals/evals.json`
- `docs/guides/commands.md`

### 11.2 关键改动

#### `webnovel-write`

- 删除 Step 2/4 的状态直写
- 删除 Step 2 直接加载 `core-constraints` / `anti-ai-guide`
- Step 1 生成任务书
- Step 2 只吃任务书
- Step 5 简化为：
  - 调 data-agent
  - 调 chapter-commit
  - 确认 projection 完成

#### `context-agent`

- research 用底稿
- 最终按示例写任务书
- 不再输出旧执行包三层结构

#### `data-agent`

- 只提取事实
- 只产出 commit artifacts
- 不再直接写 `state/index/memory`

#### `webnovel-query`

- 查询路径改成 commit / projection
- 不再运行时直接拼旧真源

### 11.3 静态测试

`test_prompt_integrity.py` 至少新增：

- skill / agent 不得引用已删散写命令
- `data-agent` 不直写
- CLI 子命令引用都在注册表里

### 11.4 验收

- skills / agents 不再引用旧散写路径
- 静态测试通过
- eval 与命令文档同步

---

## 12. Section 9：向量索引增强 + 时序查询接口

### 12.1 这轮只做轻量增强

不引入真正的图引擎，不做新项目级图谱系统。

这轮只做两件轻量事：

1. commit 后把实体/事件写进向量索引
2. 给现有 SQLite 表加统一的时序查询接口

### 12.2 向量索引补实体语义

#### `EventProjectionRouter`

给关键事件加 `vector` 路由：

- `character_state_changed`
- `power_breakthrough`
- `relationship_changed`
- `world_rule_revealed`
- `world_rule_broken`
- `artifact_obtained`

#### 新增 `vector_projection_writer.py`

职责：

- 把 `accepted_events`
- 把 `entity_deltas`

转成自然语言句子，再写入向量库。

例如：

- `第47章：韩立突破筑基初期`
- `第47章：韩立与陈巧倩关系变为合作`

### 12.3 时序查询接口

新建 `knowledge_query.py`，提供：

- `entity_state_at_chapter(entity_id, chapter)`
- `entity_relationships_at_chapter(entity_id, chapter)`

供 `context-agent` research 阶段调用。

### 12.4 不做的事

- 不引入 `neo4j`
- 不引入 `petgraph`
- 不做图遍历
- 不做关系可视化

### 12.5 验收

- 事件 chunk 能进向量库
- 指定章节状态查询可用
- 指定章节关系查询可用
- RAG 能同时命中正文 chunk 和事件 chunk

---

## 13. 实施顺序

这轮按严格串行走：

1. `CSV_CONFIG`
2. CSV 内容修补
3. 裁决表
4. engine 接入裁决表
5. `context_manager` 瘦身
6. 旧散写路径清理
7. projection 层收束
8. 消费端同步
9. 向量索引增强 + 时序查询

原因很简单：

- 这不是日常迭代
- 这是一次性系统收束
- 中间态存在多久不重要
- 重要的是每一步的验收标准清楚，最终状态正确

---

## 14. 最终判断

这份 spec 的最终判断可以压成五句话：

1. 六层必须一起收束，不能只补前四层
2. 消费端不能再直读知识层，必须只吃合同和投影视图
3. `core-constraints` 要被拆成具体约束，不再整篇读
4. `anti-ai-guide` 保留，但只由上游吸收后转写
5. `CHAPTER_COMMIT -> projection` 是唯一写后真源路径

做到这一步，`webnovel-writer` 才算真正从“半成品并存”进入“统一主链”状态。
