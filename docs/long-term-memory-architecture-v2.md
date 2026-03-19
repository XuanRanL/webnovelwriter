# 长期记忆新架构规划（V2）

## 文档目标

基于长期记忆方向的论文与工程调研结果，重新规划 `webnovel-writer` 的目标架构。

这版架构不再把重点放在“补一个 scratchpad 文件”，而是把系统正式升级为：

- `记忆写入层`
- `记忆存储层`
- `记忆编排层`
- `写作消费层`

四层协同的长期记忆系统。

## 一句话结论

新架构应采用：

- `LIGHT` 的三层记忆分层
- `Mem0` 的独立 memory layer 思路
- `Zep / Graphiti` 的时态事实与关系建模

也就是说，目标不是“在 ContextManager 上继续堆逻辑”，而是：

**把记忆系统独立出来，让 ContextManager 退化成消费记忆编排结果的适配层。**

## 为什么要重规划

旧方案的问题在于：

- 仍然以 `ContextManager` 为中心
- 更像“现有系统增强”
- 不够清晰地区分“写记忆”和“读记忆”

基于调研后，新的核心认识是：

1. 长期记忆的关键不只是检索，而是写入与更新
2. 长期记忆必须有自己的生命周期管理
3. 事实、关系、时间线应当进入同一记忆体系
4. 上下文组装只是消费层，不应继续承担全部核心职责

## 新架构核心原则

### 1. 记忆系统独立化

新增独立 `memory` 子系统，负责：

- 记忆抽取
- 记忆归档
- 记忆压缩
- 记忆检索
- 冲突裁决

### 2. 记忆分层化

固定分成三层：

- `Working Memory`
- `Episodic Memory`
- `Semantic/Scratchpad Memory`

### 3. 时态事实化

角色状态、关系、势力、伏笔等信息都必须支持：

- 当前有效
- 历史版本
- 变更时间
- 来源证据

### 4. 消费与存储解耦

- `ContextManager` 只负责消费记忆编排结果
- 写作技能/查询技能不直接拼接多源原始数据

## 目标总架构

```text
┌──────────────────────────────────────────────────────────────┐
│                    Skills / Agents / Dashboard              │
│   write / review / query / resume / dashboard              │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                    Context Facade Layer                     │
│  ContextManager / extract_chapter_context / query adapter   │
│  只负责接收 Memory Orchestrator 输出并适配不同命令           │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                    Memory Orchestrator                      │
│  统一读取 Working / Episodic / Semantic Memory             │
│  做预算控制、相关性过滤、冲突裁决、输出 context pack         │
└───────────────┬───────────────────────┬──────────────────────┘
                │                       │
                ▼                       ▼
     ┌───────────────────┐   ┌───────────────────────────────┐
     │ Working Memory    │   │ Long-Term Memory Layer        │
     │ 近期写作上下文      │   │ Episodic + Semantic           │
     └───────────────────┘   └───────────────────────────────┘
                                          │
                                          ▼
                       ┌──────────────────────────────────────┐
                       │ Memory Write Pipeline                │
                       │ Chapter result -> extract -> update  │
                       └──────────────────────────────────────┘
                                          │
                                          ▼
                       ┌──────────────────────────────────────┐
                       │ Memory Storage Layer                 │
                       │ state/index/vectors/scratchpad/graph │
                       └──────────────────────────────────────┘
```

## 四层模型

## 1. 记忆写入层

这是新架构中最重要的新层。

### 职责

- 从章节产物中提取长期有效信息
- 判断哪些信息进入哪种记忆层
- 对已有事实做更新、失效、冲突标记
- 生成可供后续读取的标准化记忆项

### 写入入口

主入口仍然挂在 Step 5 / Data Agent 完成之后。

输入来源：

- `entities_new`
- `entities_appeared`
- `state_changes`
- `relationships_new`
- `chapter_meta`
- `summary`
- `plot_threads`
- 后续可扩展：审查报告、用户偏好、人工修订

### 建议新增模块

```text
scripts/data_modules/memory/
├── write_pipeline.py
├── extractors/
│   ├── fact_extractor.py
│   ├── relationship_extractor.py
│   ├── timeline_extractor.py
│   └── promise_extractor.py
```

### 设计理由

这部分吸收的是 `Mem0` 的思路：

- 记忆不是原样存对话
- 而是先做显著信息提炼，再写入 memory layer

## 2. 记忆存储层

新架构不废弃现有存储，而是重新定义职责。

### 2.1 `state.json`

继续保留，但职责进一步收缩为：

- 当前写作运行态
- 主角快照
- 进度
- strand tracker
- 少量即时风险提示

不再承载长期知识沉淀。

### 2.2 `index.db`

继续作为结构化事实库，但要明确升级为：

- `episodic structured memory`

主要存：

- 实体
- 别名
- 关系
- 关系事件
- 状态变化
- chapter/meta
- 追读力和审查指标

### 2.3 `vectors.db`

继续作为：

- `episodic retrieval memory`

主要存：

- 章节摘要
- 场景切片
- 后续可扩展：
  - 长期摘要块 embedding
  - 伏笔块 embedding
  - 角色关系摘要块 embedding

### 2.4 `memory_scratchpad.json`

保留，但重新定义为：

- `semantic memory cache`

它不应该只是一个杂项摘要文件，而应该是一个可压缩、高密度、面向消费的长期摘要缓存。

建议结构：

```json
{
  "character_state": [],
  "story_state": [],
  "world_rules": [],
  "timeline": [],
  "open_loops": [],
  "reader_promises": [],
  "active_constraints": [],
  "meta": {}
}
```

### 2.5 `memory_graph.db` 或图表扩展

这是新规划中和旧方案最大的差异之一。

建议新增图记忆层，哪怕初期只是 SQLite 表，也要预留语义：

- 实体节点
- 关系边
- 时间有效性
- 来源章节
- 版本变化

形式上可以有两种方案：

1. 保守方案：
   - 先继续放在 `index.db`
   - 新增 graph-oriented tables
2. 进阶方案：
   - 新建 `memory_graph.db`

第一阶段建议用保守方案，避免基础设施过重。

## 3. 记忆编排层

这是新的核心中台。

### 职责

- 按章节或查询意图读取三层记忆
- 根据任务类型动态分配预算
- 合并 working / episodic / semantic memory
- 对冲突事实做优先级裁决
- 输出标准化 context pack

### 建议新增模块

```text
scripts/data_modules/memory/
├── orchestrator.py
├── budget_manager.py
├── relevance_filter.py
├── conflict_resolver.py
└── memory_pack.py
```

### 三层记忆定义

#### Working Memory

来源：

- 本章大纲
- 最近摘要
- 当前状态
- 当前 chapter guidance
- 当前债务与风险

特点：

- 强时效
- 高优先级
- 不需要长期存档

#### Episodic Memory

来源：

- `index.db`
- `vectors.db`
- `summaries`

特点：

- 保留历史证据
- 可追溯
- 适合回答“发生过什么”

#### Semantic Memory

来源：

- `memory_scratchpad.json`
- 图记忆层生成的高阶摘要

特点：

- 保留稳定抽象事实
- 适合回答“当前应该认为是真的是什么”

### 编排流程

```text
写作请求
   │
   ▼
意图分析
   │
   ├── chapter_write
   ├── consistency_check
   ├── continuity_query
   └── review
   ▼
Memory Orchestrator
   │
   ├── load working memory
   ├── retrieve episodic memory
   ├── load semantic memory
   ├── resolve conflicts
   ├── apply budget
   └── build final pack
```

## 4. 写作消费层

这一层包括：

- `ContextManager`
- `extract_chapter_context.py`
- `/webnovel-write`
- `/webnovel-query`
- `/webnovel-review`

### 新职责

- 不直接拼装底层数据
- 只根据任务类型请求 memory pack
- 将 memory pack 渲染成：
  - text
  - json
  - prompt context

### 这意味着什么

`ContextManager` 不再是记忆逻辑中心，而是：

- 一个适配器
- 一个模板层
- 一个输出格式层

## 模块目录规划

建议新增独立目录：

```text
webnovel-writer/scripts/data_modules/
├── memory/
│   ├── __init__.py
│   ├── schema.py
│   ├── storage.py
│   ├── write_pipeline.py
│   ├── orchestrator.py
│   ├── conflict_resolver.py
│   ├── relevance_filter.py
│   ├── budget_manager.py
│   ├── summary_compactor.py
│   └── graph_memory.py
```

### 各模块职责

#### `schema.py`

- 定义记忆项结构
- 定义状态字段与版本字段

#### `storage.py`

- 封装对 `memory_scratchpad.json`、`index.db`、`vectors.db` 的统一读写

#### `write_pipeline.py`

- 章节完成后写入记忆

#### `orchestrator.py`

- 对外提供统一 `build_memory_pack()`

#### `conflict_resolver.py`

- 处理 active / outdated / contradicted / tentative

#### `relevance_filter.py`

- 按章节目标、大纲关键词、实体中心过滤长期记忆

#### `budget_manager.py`

- 控制不同任务类型的 token 预算

#### `summary_compactor.py`

- 负责 scratchpad 压缩和去噪

#### `graph_memory.py`

- 封装关系图、时间线和事实图语义

## 数据模型重定义

### 统一记忆项

建议引入统一记忆对象结构：

```json
{
  "id": "mem-001",
  "layer": "semantic",
  "category": "character_state",
  "subject": "xiaoyan",
  "field": "realm",
  "value": "筑基三层",
  "status": "active",
  "source": {
    "chapter": 128,
    "type": "state_change"
  },
  "evidence": [
    "state_change:xiaoyan:realm:128",
    "summary:ch0128"
  ],
  "updated_at": "2026-03-19T20:00:00+08:00",
  "confidence": 0.95
}
```

### 为什么需要统一记忆项

这样可以统一处理：

- 角色状态
- 世界规则
- 伏笔
- 读者承诺
- 关系变化
- 时间线事件

## 新架构的数据流

## 写入流

```text
正文完成
   │
   ▼
Data Agent
   │
   ├── 原有写入：state/index/vectors/summaries
   └── Memory Write Pipeline
           │
           ├── 提取长期事实
           ├── 合并到 semantic memory
           ├── 更新 graph memory
           ├── 标记冲突和过期项
           └── 刷新 scratchpad cache
```

## 读取流

```text
第N章写作 / 查询 / 审查
   │
   ▼
Memory Orchestrator
   │
   ├── Working Memory
   ├── Episodic Memory
   ├── Semantic Memory
   ├── Graph Memory
   └── Conflict Resolution
   ▼
Memory Pack
   ▼
ContextManager / Query Renderer / Review Renderer
```

## 对现有模块的角色调整

### `ContextManager`

从：

- 核心上下文拼装器

变为：

- memory pack 渲染器
- 模板权重应用器

### `StateManager`

从：

- 运行态状态 + 部分知识写入

变为：

- 运行态状态管理器
- 章节结果写入入口
- 记忆写入流水线触发器

### `IndexManager`

从：

- 结构化索引库

变为：

- episodic structured memory backend

### `RAGAdapter`

从：

- 场景检索器

变为：

- episodic retrieval backend

## 推荐实施顺序

### Stage 1：搭 memory 子系统骨架

- 新增 `memory/` 目录
- 定义统一记忆 schema
- 抽出 scratchpad 存储

### Stage 2：接写入管线

- 章节写后自动更新 semantic memory
- 建立冲突状态字段

### Stage 3：接编排器

- `ContextManager` 改为消费 orchestrator
- `extract_chapter_context.py` 改为基于 memory pack 输出

### Stage 4：接图记忆

- 先在 `index.db` 扩展 graph-like tables
- 后续如有必要再拆独立图库

### Stage 5：扩展 dashboard 和观测

- 查看长期事实
- 查看冲突项
- 查看记忆命中来源

## 关键取舍

### 不建议做的事

- 继续把所有逻辑堆进 `ContextManager`
- 只加一个 `memory_scratchpad.json` 就认为问题解决
- 第一阶段就引入完整图数据库
- 直接照搬 Letta/MemGPT 的 agent runtime

### 建议做的事

- 把 memory 作为独立子系统设计
- 先解决记忆写入问题，再优化读取
- 用统一记忆项结构降低后续复杂度
- 让图语义先以轻量方式落在现有 SQLite 中

## 最终目标

最终系统应具备以下能力：

1. 写完一章后，系统能自动沉淀长期有效事实
2. 多章之后，系统能区分历史事实和当前事实
3. 写作前，系统能自动提供“近期上下文 + 历史证据 + 长期约束”
4. 当关系、设定、伏笔变化时，系统能保留版本与证据
5. 审查和查询模块能共享同一套长期记忆底座

## 总结

基于调研，新的最佳架构不是“在现有系统上补一个功能点”，而是：

**把长期记忆升级为一个独立子系统，并让现有写作系统围绕它重新分层。**

这版架构比旧方案更适合长期演化，也更符合当前长期记忆研究和工程实践的主流方向。
