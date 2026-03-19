# LIGHT 改造现有系统计划

## 文档目标

本文档给出一份可直接执行的改造计划，用于在当前 `webnovel-writer` 基础上引入 LIGHT 风格的三层记忆系统，同时尽量复用现有的 `state.json`、`index.db`、`vectors.db`、`ContextManager` 与写作工作流。

目标不是推翻现有架构，而是在低风险前提下补齐：

- 独立的长期摘要记忆层 `scratchpad`
- 统一的记忆编排层 `memory orchestrator`
- 面向写作场景的冲突裁决与记忆状态管理

## 当前系统现状摘要

当前项目已经具备以下能力：

- `state.json`：精简运行态与章节元信息
- `index.db`：实体、别名、状态变化、关系、追读力、审查指标
- `vectors.db`：章节摘要与场景切片的向量检索
- `ContextManager`：多源上下文拼装与预算裁剪
- `extract_chapter_context.py`：写作前统一上下文入口
- `workflow_manager.py`：写作工作流状态机与中断恢复

当前缺口主要有两项：

- 缺独立维护的长期摘要记忆层
- 缺统一调度 `working / episodic / scratchpad` 的记忆编排器

## 改造目标

### 总目标

将系统升级为三层记忆架构：

- `working memory`：近期写作上下文
- `episodic memory`：可检索历史证据
- `scratchpad memory`：长期高密度摘要记忆

### 子目标

- 不破坏现有 `/webnovel-write` 主流程
- 不修改已有数据模型的核心职责边界
- 新增能力尽量通过“增量接入”完成
- 保持现有 CLI 与测试体系可持续演进

## 目标架构

```text
Skills / Agents
   │
   ▼
Chapter Context Facade
   │  extract_chapter_context.py
   │  ContextManager
   ▼
Memory Orchestrator
   ├── Working Memory
   ├── Episodic Memory
   └── Scratchpad Memory
   ▼
Final Context Pack

写入侧：
Data Agent / Step 5
   ├── state.json
   ├── index.db
   ├── vectors.db
   ├── summaries/
   └── memory_scratchpad.json
```

## 设计原则

### 1. 最小侵入

优先复用：

- `ContextManager`
- `extract_chapter_context.py`
- `StateManager`
- `IndexManager`
- `RAGAdapter`

### 2. 单一职责

- `state.json` 继续保存运行态精简信息
- `index.db` 继续保存结构化事实
- `vectors.db` 继续保存语义检索向量
- `memory_scratchpad.json` 专门保存长期摘要记忆

### 3. 渐进替换

先“旁路接入”，再逐步把逻辑迁入编排器，而不是一次性重写 `ContextManager`

### 4. 可回滚

每个阶段都能独立上线和回退，避免一次改太大导致写作链失稳

## 记忆分层映射

### Working Memory

来源：

- 本章大纲
- 最近章节摘要
- 当前 `state.json`
- `reader_signal`
- `writing_guidance`

当前主要载体：

- `scripts/extract_chapter_context.py`
- `scripts/data_modules/context_manager.py`

### Episodic Memory

来源：

- `index.db`
- `vectors.db`
- `.webnovel/summaries/chNNNN.md`

当前主要载体：

- `scripts/data_modules/index_manager.py`
- `scripts/data_modules/rag_adapter.py`
- `scripts/data_modules/state_manager.py`

### Scratchpad Memory

新增：

- `.webnovel/memory_scratchpad.json`

用途：

- 汇总长期有效事实
- 维护角色当前稳定状态
- 沉淀世界规则与长期约束
- 存储时间线与未回收开放环
- 服务写作前的高密度摘要注入

## 新增模块规划

建议新增以下文件：

```text
webnovel-writer/scripts/data_modules/
├── memory_orchestrator.py
├── scratchpad_manager.py
├── scratchpad_schema.py
└── memory_conflict_resolver.py
```

### `scratchpad_schema.py`

职责：

- 定义 `memory_scratchpad.json` 结构
- 提供默认值与校验函数

建议结构：

```json
{
  "story_facts": [],
  "character_facts": [],
  "world_rules": [],
  "timeline": [],
  "open_loops": [],
  "reader_promises": [],
  "active_constraints": [],
  "meta": {
    "version": 1,
    "last_updated": ""
  }
}
```

### `scratchpad_manager.py`

职责：

- 读写 `memory_scratchpad.json`
- 从章节结果增量更新长期摘要
- 定期压缩与去噪
- 按主题或章节生成相关片段

建议能力：

- `load()`
- `save()`
- `update_from_chapter_result()`
- `compress_if_needed()`
- `filter_for_chapter()`
- `mark_fact_status()`

### `memory_conflict_resolver.py`

职责：

- 处理新旧事实冲突
- 给事实打状态标签

建议状态：

- `active`
- `outdated`
- `contradicted`
- `tentative`

建议处理对象：

- 角色境界/地点/归属变更
- 关系变化
- 世界规则的显式修订
- 伏笔从 active 到 resolved

### `memory_orchestrator.py`

职责：

- 统一调度三层记忆
- 控制预算与优先级
- 输出最终 context pack

建议接口：

- `build_memory_pack(chapter: int) -> dict`
- `load_working_memory(chapter: int) -> dict`
- `load_episodic_memory(chapter: int) -> dict`
- `load_scratchpad_memory(chapter: int) -> dict`
- `resolve_conflicts(...)`
- `assemble(...)`

## 现有文件改造点

### 第一优先级

#### `scripts/data_modules/context_manager.py`

改造目标：

- 从“多源上下文拼装器”升级为“编排器调用方”
- 新增 `scratchpad` section
- 后续逐步委托给 `MemoryOrchestrator`

建议改动：

- `_build_pack()` 中加入 scratchpad 内容
- `SECTION_ORDER` 中加入或重新排序 `scratchpad`
- 新增从 orchestrator 获取结果的兼容入口

#### `scripts/extract_chapter_context.py`

改造目标：

- 接入 `MemoryOrchestrator`
- 输出更完整的三层记忆摘要

建议改动：

- 在 `build_chapter_context_payload()` 中加载 orchestrator 结果
- 保留现有 JSON/text 输出格式兼容
- 新增 `scratchpad_signal` 或 `long_term_memory` 字段

#### `scripts/data_modules/state_manager.py`

改造目标：

- 在 `process_chapter_result()` 完成后触发 scratchpad 更新

建议改动：

- 在章节结果保存成功后调用 `ScratchpadManager.update_from_chapter_result()`
- 失败时只记录 warning，不影响主流程完成

### 第二优先级

#### `scripts/data_modules/rag_adapter.py`

改造目标：

- 让 episodic memory 检索对“长期事实块”更友好

建议改动：

- 为 scratchpad 相关片段预留可选向量化能力
- 允许对 `chunk_type=scratchpad` 做检索
- 不作为第一阶段必做项

#### `scripts/status_reporter.py`

改造目标：

- 利用 scratchpad 生成更高层视角的健康报告

建议改动：

- 报告中增加“长期约束漂移”“未回收开放环”“记忆冲突提醒”

#### Dashboard

改造目标：

- 增加 scratchpad 可视化

建议改动：

- 展示当前长期事实摘要
- 展示冲突事实与待确认事实

## 新数据文件规划

新增：

```text
.webnovel/memory_scratchpad.json
```

建议字段：

- `story_facts`：当前剧情稳定事实
- `character_facts`：角色稳定状态与重要变化
- `world_rules`：长期不可违背设定
- `timeline`：关键事件时间线
- `open_loops`：未回收伏笔、未完成承诺、待兑现悬念
- `reader_promises`：已对读者抛出的期待点
- `active_constraints`：当前章节仍需遵守的重要约束
- `meta`：版本、更新时间、压缩次数

建议事实项结构：

```json
{
  "id": "fact-char-xiaoyan-realm-001",
  "category": "character_facts",
  "subject": "xiaoyan",
  "field": "realm",
  "value": "筑基三层",
  "status": "active",
  "source_chapter": 128,
  "updated_at": "2026-03-19T20:00:00+08:00",
  "evidence": [
    "ch0128_summary",
    "state_change:xiaoyan:realm:128"
  ],
  "confidence": 0.95
}
```

## 分阶段执行计划

### Phase 0：设计冻结与接口先行

目标：

- 明确数据结构和接口，不立即改主流程

任务：

1. 定义 `memory_scratchpad.json` schema
2. 定义 `ScratchpadManager` 最小接口
3. 定义 `MemoryOrchestrator` 输入输出格式
4. 补充设计文档与测试样例

交付物：

- `scratchpad_schema.py`
- 设计说明文档
- 测试用 fixture 样例

验收标准：

- schema 稳定
- 接口命名与现有风格一致
- 不影响现有命令

### Phase 1：落地 Scratchpad 存储层

目标：

- 让项目拥有独立的长期摘要记忆文件

任务：

1. 实现 `scratchpad_schema.py`
2. 实现 `scratchpad_manager.py`
3. 支持加载、保存、初始化默认结构
4. 编写基础单元测试

交付物：

- `memory_scratchpad.json`
- `ScratchpadManager`
- 对应 tests

验收标准：

- 文件创建与读写稳定
- schema 校验通过
- 空项目可自动初始化

### Phase 2：接入章节写后更新链

目标：

- 在现有 Step 5 后自动维护 scratchpad

任务：

1. 在 `StateManager.process_chapter_result()` 后接入 scratchpad 更新
2. 从以下来源提取增量事实：
   - `entities_new`
   - `state_changes`
   - `relationships_new`
   - `chapter_meta`
   - `plot_threads.foreshadowing`
3. 增加错误隔离，保证 scratchpad 失败不阻断主流程

交付物：

- 写后更新逻辑
- 日志与 warning 机制

验收标准：

- 写完一章后 scratchpad 有可见增量
- 工作流不因 scratchpad 失败而中断

### Phase 3：接入读取链

目标：

- 在写作前上下文中引入 scratchpad

任务：

1. 在 `ContextManager` 中加入 scratchpad section
2. 在 `extract_chapter_context.py` 中输出长期记忆摘要
3. 为 scratchpad 分配独立预算
4. 增加按章节相关性过滤

交付物：

- 上下文新增 `scratchpad` / `long_term_memory`
- text 输出中新增相关章节说明

验收标准：

- 第 N 章上下文可看到长期约束与关键开放环
- 上下文长度可控

### Phase 4：引入 Memory Orchestrator

目标：

- 从“多源拼装”升级为“分层记忆编排”

任务：

1. 新建 `memory_orchestrator.py`
2. 把以下逻辑迁入 orchestrator：
   - Working memory 读取
   - Episodic memory 检索
   - Scratchpad 过滤
   - 冲突检查
   - 最终 pack 组装
3. 让 `ContextManager` 调用 orchestrator，而不是自己做全部组装

交付物：

- `MemoryOrchestrator`
- `ContextManager` 兼容适配

验收标准：

- 输出结构与旧接口兼容
- 逻辑可单测
- 能独立关闭 orchestrator，回退旧路径

### Phase 5：冲突裁决与记忆状态化

目标：

- 解决“旧事实覆盖新事实”的问题

任务：

1. 新建 `memory_conflict_resolver.py`
2. 对关键事实打状态：
   - `active`
   - `outdated`
   - `contradicted`
   - `tentative`
3. 处理常见冲突：
   - 人物境界变化
   - 人物位置变化
   - 势力归属变化
   - 伏笔状态变化
   - 关系状态变化

交付物：

- 冲突解析器
- 冲突样例测试

验收标准：

- 最新事实优先
- 旧事实保留历史但不进入高优先上下文

### Phase 6：高级能力增强

目标：

- 进一步提升检索与可观察性

任务：

1. 可选支持 scratchpad 向量化
2. 在 dashboard 中增加 scratchpad 可视化
3. 增加记忆命中日志
4. 在健康报告中加入记忆冲突提醒

交付物：

- dashboard 页面扩展
- 观测指标扩展

验收标准：

- 能追踪每次写作用了哪些记忆
- 可以人工审计长期记忆质量

## 实施顺序建议

推荐严格按以下顺序做：

1. Phase 0
2. Phase 1
3. Phase 2
4. Phase 3
5. Phase 4
6. Phase 5
7. Phase 6

原因：

- 先落存储层，后接写链
- 先让数据流起来，再做编排优化
- 先保证稳定，再做智能化冲突处理

## 测试计划

### 单元测试

新增测试文件建议：

```text
scripts/data_modules/tests/
├── test_scratchpad_schema.py
├── test_scratchpad_manager.py
├── test_memory_orchestrator.py
└── test_memory_conflict_resolver.py
```

重点测试：

- scratchpad 初始化
- 章节结果增量写入
- 冲突事实状态变化
- 上下文过滤与预算裁剪
- orchestrator 输出兼容性

### 集成测试

建议扩展：

- `test_context_manager.py`
- `test_extract_chapter_context.py`
- `test_state_manager_extra.py`

验证场景：

1. 连续两章更新同一角色境界
2. 伏笔状态从 active 变为 resolved
3. 写作上下文中出现正确的长期约束
4. scratchpad 失败时主流程仍能成功

### 回归测试

必须覆盖：

- `/webnovel-write` 主流程不回归
- `/webnovel-review` 不受影响
- 旧项目无 `memory_scratchpad.json` 时可兼容

## 风险与控制策略

### 风险 1：上下文变长

问题：

- 引入 scratchpad 后上下文膨胀

控制：

- 单独预算
- 分槽位裁剪
- 只注入相关块

### 风险 2：错误事实长期污染

问题：

- scratchpad 写入错误后会长期影响后续章节

控制：

- 先基于结构化数据生成，而不是纯文本自由总结
- 保留 evidence 字段
- 增加 `tentative` 状态

### 风险 3：和现有 ContextManager 职责冲突

问题：

- 逻辑迁移过快，导致重复拼装

控制：

- Phase 3 前只做增量 section
- Phase 4 再逐步收口到 orchestrator

### 风险 4：影响写作主链稳定性

问题：

- 新模块异常阻断主流程

控制：

- scratchpad 写入采用 best-effort
- 失败只记录 warning
- 主流程成功判定不依赖 scratchpad

## 里程碑定义

### M1：Scratchpad 可用

完成标志：

- 可以创建并维护 `.webnovel/memory_scratchpad.json`

### M2：写后自动更新

完成标志：

- 每章写作完成后 scratchpad 自动更新

### M3：写前自动读取

完成标志：

- 写作上下文中包含长期摘要记忆

### M4：统一编排上线

完成标志：

- `MemoryOrchestrator` 成为主读取路径

### M5：冲突管理完成

完成标志：

- 新旧事实状态化，长期记忆可持续演进

## 推荐首批实现范围

如果只做一个最小可落地版本，建议范围限定为：

1. 新增 `memory_scratchpad.json`
2. 实现 `scratchpad_schema.py`
3. 实现 `scratchpad_manager.py`
4. 在 `state_manager.py` 写后更新 scratchpad
5. 在 `context_manager.py` 写前读取 scratchpad

这五项完成后，就已经有一版可运行的 LIGHT MVP。

## 最终结论

当前项目不需要重构重来，而应该走一条“补层”的路线：

- 保留现有 `state/index/rag/workflow`
- 新增独立 `scratchpad`
- 再以 `memory orchestrator` 把三层记忆统一起来

这是对当前工程最稳、最符合现状、也最容易逐步验收的改造方案。
