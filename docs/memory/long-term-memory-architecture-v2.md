# 长期记忆现有架构设计

## 文档定位

本文只描述当前仓库里已经落地、并被主写作链路实际消费的长期记忆架构。

这里不再保留历史改造计划，也不把理想态蓝图混进来。判断标准只有一个：当前代码里是否真实存在、是否已经接入主链路。

## 一句话结论

当前长期记忆的真实实现是：

- 以 `.webnovel/memory_scratchpad.json` 作为长期语义记忆缓存
- 以 `index.db`、`summaries/`、`state.json` 作为近期状态和历史证据层
- 由 `MemoryOrchestrator` 组装 `working / episodic / semantic` 三层结果
- 再由 `ContextManager`、`extract_chapter_context.py` 和 `MemoryContractAdapter` 对外消费

它已经是一条可运行的数据链，但还不是完全独立的记忆子系统。

## 核心边界

### 已经属于长期记忆主链路

- `scripts/data_modules/memory/schema.py`
- `scripts/data_modules/memory/store.py`
- `scripts/data_modules/memory/writer.py`
- `scripts/data_modules/memory/orchestrator.py`
- `scripts/data_modules/memory/bootstrap.py`
- `scripts/data_modules/memory/compactor.py`
- `scripts/data_modules/memory_contract_adapter.py`
- `scripts/memory_cli.py`
- `scripts/data_modules/context_manager.py` 中的 `long_term_memory` 注入

### 仍然是旁路或相邻能力

- `.webnovel/project_memory.json`
- `/webnovel-learn` 产出的项目经验记忆
- `ContextManager` 里的 `memory` section

这部分会被上下文一起读取，但不等同于 `memory_scratchpad.json` 这条长期记忆主链路。

## 现有架构图

```text
章节结果 / 审查产物
        │
        ▼
MemoryWriter
        │
        ├── 写入 memory_scratchpad.json
        ├── 维护 active/outdated/contradicted/tentative
        └── 触发压缩与冲突检查

state.json / index.db / summaries/ / memory_scratchpad.json
        │
        ▼
MemoryOrchestrator
        │
        ├── working_memory
        ├── episodic_memory
        ├── semantic_memory
        └── long_term_facts / active_constraints / warnings / stats

        ▼
ContextManager
        │
        ├── long_term_memory section
        ├── extract_chapter_context.py
        └── MemoryContractAdapter / memory CLI

        ▼
webnovel-write / review / query / 其他消费端
```

## 数据分层

### 1. Working Memory

当前不是单独存储，而是运行时临时拼装，主要来源于：

- 本章章纲
- 最近几章摘要
- `state.json` 中的主角状态、情节线程、待消歧项

这层由 `MemoryOrchestrator._build_working_memory()` 生成。

### 2. Episodic Memory

当前主要来自 `index.db` 的近期结构化证据，而不是独立的通用历史检索系统。

主要来源：

- 最近状态变化
- 最近关系变化
- 最近出场记录

这层由 `MemoryOrchestrator._build_episodic_memory()` 生成，特点是偏“最近证据”，不是全量全库语义召回。

### 3. Semantic Memory

当前长期记忆的核心存储是 `.webnovel/memory_scratchpad.json`。

它由 `ScratchpadManager` 读写，按分类分桶保存：

- `character_state`
- `story_facts`
- `world_rules`
- `timeline`
- `open_loops`
- `reader_promises`
- `relationships`

每条记忆项统一使用 `MemoryItem` 结构，核心字段包括：

- `id`
- `layer`
- `category`
- `subject`
- `field`
- `value`
- `payload`
- `status`
- `source_chapter`
- `evidence`
- `updated_at`

支持的状态为：

- `active`
- `outdated`
- `contradicted`
- `tentative`

## 写入链路

### 1. 章节结果进入 `MemoryWriter`

写作主链在章节提交后，会把结构化结果交给 `MemoryWriter.update_from_chapter_result()`。

当前已实现的写入来源包括：

- `state_changes`
- `entities_new`
- `relationships_new`
- `chapter_meta.hook`
- `memory_facts`

其中 `memory_facts` 用于更深一层的结构化映射，当前支持：

- `timeline_events`
- `world_rules`
- `open_loops`
- `reader_promises`

### 2. `ScratchpadManager` 做去重与状态收敛

`ScratchpadManager.upsert_item()` 的核心规则是：

- 按分类主键规则计算去重 key
- 同 key 的旧值降级为 `outdated`
- 新值写成当前有效项
- 保留旧值用于审计和回溯

当前各分类的主键规则由 `schema.py` 统一定义，例如：

- `character_state`：`subject + field`
- `relationship`：`subject + field`
- `world_rule`：`subject + field`
- `open_loop`：`subject`

### 3. 超阈值时压缩

`ScratchpadManager.save()` 会在达到阈值后调用 `compactor.py`。

当前压缩策略包括：

- 同 key 的 `outdated` 只保留最新一条
- 清理已回收的伏笔
- 过旧时间线合并为摘要型 `story_fact`
- 总量仍超限时按状态和新鲜度做全局截断

### 4. 历史项目可回填

`memory bootstrap` 会从现有 `index.db` 与 `summaries/` 回填出一版初始长期记忆。

当前可回填的内容包括：

- 角色当前状态
- 历史状态变化
- 最近关系
- 摘要中的“伏笔”区块

## 读取与编排链路

### 1. `MemoryOrchestrator` 负责统一出包

`MemoryOrchestrator.build_memory_pack()` 是当前长期记忆的统一读取入口。

它会做四件事：

1. 构建 `working_memory`
2. 构建 `episodic_memory`
3. 读取 `memory_scratchpad.json` 中的 `active` 项
4. 过滤、限额、补充告警与统计信息

输出的核心字段包括：

- `working_memory`
- `episodic_memory`
- `semantic_memory`
- `long_term_facts`
- `active_constraints`
- `recent_changes`
- `warnings`
- `stats`

其中：

- `semantic_memory` 与 `long_term_facts` 当前是同一批可直接注入的长期语义事实
- `active_constraints` 主要抽取 `world_rule` 和 `open_loop`
- `warnings` 当前主要用于暴露记忆冲突

### 2. 当前过滤规则

`semantic_memory` 不是全量注入，而是先做一轮轻量过滤。

现有过滤依据：

- 记忆项的 `subject / field / value` 是否出现在本章章纲中
- 来源章节是否落在配置允许的窗口内

然后再按预算截断。当前预算由 `budget.py` 和配置项共同控制。

## 消费层

### 1. `ContextManager`

`ContextManager` 仍然是写作上下文的总装配器。

当 `context_use_memory_orchestrator=true` 时，它会：

- 调用 `MemoryOrchestrator.build_memory_pack()`
- 把结果注入到 `long_term_memory` section
- 再和 `reader_signal / genre_profile / writing_guidance / plot_structure` 一起组装最终 context

所以当前真实关系不是“记忆系统完全替代 ContextManager”，而是“记忆系统已经接入 ContextManager”。

### 2. `extract_chapter_context.py`

写作前置上下文脚本会从 `ContextManager` 里抽取几个关键 section，其中已经包含：

- `reader_signal`
- `genre_profile`
- `writing_guidance`
- `plot_structure`
- `long_term_memory`

这意味着长期记忆已经进入主写作上下文，而不是停留在独立实验脚本里。

### 3. `MemoryContractAdapter`

`MemoryContractAdapter` 是对外的薄适配层。

它会把现有模块包装成统一接口，提供：

- `commit_chapter()`
- `load_context()`
- `query_entity()`
- `query_rules()`
- `read_summary()`
- `get_open_loops()`
- `get_timeline()`

这层的意义是：当前记忆链路已经有稳定接口，但底层存储仍然复用现有 `state / index / scratchpad / summaries`。

### 4. CLI

当前长期记忆相关的 CLI 分成两类：

- `webnovel.py memory ...`
- `memory_cli.py`

常用命令包括：

- `memory stats`
- `memory query`
- `memory dump`
- `memory conflicts`
- `memory bootstrap`
- `memory update`

## 存储职责划分

### `state.json`

负责运行时状态，不负责长期知识沉淀。

当前主要承载：

- 主角快照
- 进度
- 情节线程
- 待消歧项

### `index.db`

负责结构化历史证据。

当前长期记忆在读取 `episodic_memory` 时，主要从这里拿：

- 状态变化
- 关系
- 出场记录
- 部分追读力与审查数据

### `summaries/`

负责章节摘要与最近写作上下文。

在长期记忆链路里，它有两个作用：

- 作为 `working_memory` 的最近摘要来源
- 在 `bootstrap` 时用于回填“伏笔”类开放问题

### `memory_scratchpad.json`

负责长期语义记忆缓存，是当前长期记忆的主真源。

### `project_memory.json`

负责项目经验/学习沉淀，当前仍是独立旁路，不与 `memory_scratchpad.json` 合并。

## 当前已实现的关键能力

- 长期记忆已可持久化读写
- 已有统一 schema、状态枚举和分桶结构
- 已有冲突检测与简单状态降级
- 已有压缩器防止 scratchpad 持续膨胀
- 已能把长期记忆注入主写作上下文
- 已有 CLI 查询、回填和手工更新入口
- 已有 `MemoryContractAdapter` 作为稳定外部接口

## 当前边界与限制

### 1. 不是完全独立的 memory runtime

当前仍依赖：

- `ContextManager` 做最终装配
- `index.db` 提供近期历史证据
- `state.json` 提供运行时快照

### 2. `episodic_memory` 偏近期，不是全量历史召回

目前更像“最近结构化证据层”，不是统一的跨全书语义回忆系统。

### 3. `semantic_memory` 仍是 JSON scratchpad

当前没有单独的长期语义向量层，也没有图数据库层。

### 4. `project_memory.json` 与长期记忆主链还未统一

项目经验记忆和剧情长期记忆现在是两套并行数据源。

### 5. 冲突裁决还是轻量规则

当前主要是：

- 主键去重
- 旧值降级
- 冲突统计

还没有更重的跨章节语义裁决流程。

## 结论

当前仓库里的长期记忆已经从“方案讨论”进入“可运行架构”阶段，但它的真实定位应当是：

- 已接入主写作链路
- 已有持久化、编排、消费和运维入口
- 仍然建立在现有 `ContextManager + state/index/summaries` 生态之上

因此，这份文档只保留“现状架构说明”。

历史计划文档已经移除；如果后续继续演进，应重新按当时的真实代码状态单独写新 spec。
