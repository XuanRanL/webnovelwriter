# Webnovel Writer Story System 渐进演进 Spec

> **日期**: 2026-04-12
> **状态**: 草案 v1
> **定位**: 基于当前系统真实状态的 superpowers 架构收敛 spec

---

## 1. 文档定位

### 1.1 这份 spec 解决什么问题

[`current-system-diagnosis.md`](../../architecture/current-system-diagnosis.md) 已经明确指出：当前系统的主要问题，不是模型能力不够，而是：

1. 真理源分散
2. 缺少统一故事合同
3. 缺少统一章节提交主链
4. 上下文装配与数据回写都存在结构性缺口

但诊断报告只回答了“哪里有问题”，没有回答“如何从当前系统稳态演进到新系统”。

这份 spec 补的就是中间层：

- 不重写现有项目历史
- 不假装当前系统一无所有
- 不直接把理想态蓝图当实施方案
- 而是定义一条**从现状出发、逐步收束为 Story Contract 主链**的演进路线

### 1.2 与其他文档的关系

这份文档与现有文档的关系如下：

- [`current-system-diagnosis.md`](../../architecture/current-system-diagnosis.md)
  - 负责诊断当前系统的结构性问题
- [`2026-04-12-story-system-pro-max-retrofit-spec.md`](./2026-04-12-story-system-pro-max-retrofit-spec.md)
  - 负责保守改造思路
- [`2026-04-12-webnovel-story-intelligence-system-spec.md`](./2026-04-12-webnovel-story-intelligence-system-spec.md)
  - 负责理想态目标架构

这份 spec 的定位是：

- **以上三者之间的桥**
- 用“现状基线 -> 阶段性收束 -> 最终合同系统”的方式，把诊断、retrofit、理想态串起来

### 1.2.1 与 diagnosis / retrofit / ideal spec 的边界

为避免这份文档与另外两份 story system spec 打架，这里明确边界：

#### `current-system-diagnosis`

负责回答：

- 当前系统到底哪里有结构性缺口
- 哪些问题是真问题
- 哪些地方其实已经有半成品底座

它不负责给出演进实施路径。

#### `retrofit spec`

负责回答：

- 如何在尽量不破坏现有主链的前提下，补出最小可用的 `story_system`

它偏向：

- phase 1
- 保守落地
- 最小侵入

#### `理想态 spec`

负责回答：

- 如果不考虑最小改动原则，最终最佳架构应该长什么样

它偏向：

- phase 2 以后
- 最终目标
- 完整合同系统

#### 本 spec

负责回答：

- 如何从真实现状出发，把半成品中枢逐步收束成合同主链
- 哪些旧链路先接入、哪些后降级、哪些最后替换

换句话说：

- 诊断文档定义问题
- retrofit spec 定义保守补法
- 理想态 spec 定义终局目标
- **本 spec 定义从现状走到终局的渐进路径**

### 1.3 一句话结论

当前系统不是“推倒重来”型问题，而是“多个半成品中枢需要收束成一个主链”型问题。

因此最优策略不是：

- 再堆一个新脚本
- 再加一层提示词补丁
- 再给 `context_manager` 增加几条预算规则

而是建立：

- **统一故事合同层**
- **统一章节提交主链**
- **统一覆盖账本**
- **统一事件主链**

再把 `state / index / summary / memory / RAG` 统统降级为合同提交后的投影层。

---

## 2. 当前基线

### 2.1 当前系统已经存在的半成品中枢

根据现状诊断，当前系统并不是完全无结构，而是已经存在以下可复用底座：

1. `context_manager + context_ranker`
   - 已能做上下文聚合、预算控制、优先级排序
2. `genre_aliases.py + genre_profile_builder.py + genre-profiles.md`
   - 已能做题材归一化、题材 hints 生成、题材画像构建
3. `reference_search.py + references/csv`
   - 已能做条目检索与轻量打分
4. `state_manager`
   - 已能做结构化状态回写，并承担 `state.json + SQLite` 的双写同步
5. `index.db`
   - 已承载实体、关系、事件、索引等结构化事实
6. `memory writer / orchestrator / summaries`
   - 已承担长期事实沉淀与章节摘要
7. `override_contracts`
   - 已经存在“违背记录”的雏形机制

### 2.2 当前系统最根本的缺失

真正缺失的不是某一个模块，而是四个主链能力：

1. **统一故事真理源**
   - 当前没有 `MASTER / VOLUME / CHAPTER` 合同家族作为单一真理源
2. **统一章节提交主链**
   - 写作后的状态回写仍是多处散写，不是一次章节提交、再多投影分发
3. **统一设定演进账本**
   - 当前只有追读力债务的 override 雏形，没有全局设定演进账本
4. **统一事件主链**
   - 当前已有很多 Delta 事件痕迹，但没有 canonical event log

### 2.3 演进判断

这意味着演进不能按“新增一个大模块，旧链路先不管”的方式做。

必须遵守：

1. 先建立统一合同
2. 再让运行时消费合同
3. 再让章节提交变成主链
4. 最后把旧链路降级为投影与回退

如果顺序反过来，系统只会多一个并行中枢，而不是更收敛。

---

## 3. 设计目标与非目标

### 3.1 目标

本演进 spec 要达成 8 个目标：

1. 建立基于当前系统的统一故事合同体系
2. 建立合同优先的上下文装配顺序
3. 建立写前而不是写后的强约束输入
4. 建立大纲履约校验与 review contract
5. 建立统一章节提交主链
6. 建立统一 override ledger
7. 建立统一 canonical event log
8. 把现有模块重定位为合同系统的底盘和投影层

### 3.2 非目标

本 spec 明确不做以下承诺：

1. 不要求一次性替换全部旧链路
2. 不要求一次性废弃 `context_manager`、`genre_*`、`reference_search.py`
3. 不要求知识内容自动从 md 迁移到 csv
4. 不要求对每个 CSV 条目编写测试
5. 不要求在第一阶段就实现完全事件驱动架构

### 3.3 硬约束

整个演进过程必须持续遵守以下约束：

1. `AI味`、anti-AI、润色替换规则继续保留在 md，不进入 CSV
2. CSV 知识迁移只允许人工整理与人工录入
3. 演进不得制造新的双真理源
4. 任一阶段的 implementation plan 都必须把**文档更新**作为显式任务

---

## 4. 核心设计原则

### 4.1 收束，不并列

新系统的职责必须是**收束旧中枢**，不是与旧中枢并列竞争。

反模式：

- 新增 `story_system`，但 `context_manager` 仍单独输出另一套题材判断
- 新增合同文件，但 `genre-profiles.md` 仍作为同级真源参与写作输入
- 新增章节提交对象，但状态回写仍绕过它直接散写

### 4.2 合同优先，运行时补充

运行时输入应拆成两层：

1. **合同层**
   - 题材调性、毒点红线、系统边界、卷章目标
2. **事实层**
   - state、recent summaries、entity facts、reader signals

原则上：

- 合同负责“应该怎么写”
- 事实负责“已经发生了什么”

### 4.3 提交优先，投影随后

章节完成后的正确顺序必须是：

1. 形成结构化章节提交对象
2. 校验其是否满足合同和大纲
3. 只有提交通过，才向 `state / index / summary / memory` 投影

而不是：

- 先散写
- 再在各模块里尽量圆回来

### 4.4 显式覆盖，禁止静默漂移

任何设定变化必须回答四个问题：

1. 变了什么
2. 基于哪一层改的
3. 为什么改
4. 是否影响上层合同

如果回答不了，就不允许把它当作合法设定演进。

### 4.5 先补主链，再补精度

本项目当前最缺的是主链，不是精度。

因此演进顺序必须是：

1. 先补合同主链
2. 再补提交主链
3. 再补事件主链
4. 最后再提升检索、推理、多标签融合精度

---

## 5. 诊断问题到演进工作流的映射

现状诊断中的 10 个问题，可以归并为 5 条演进工作流。

### 5.1 真理源收束工作流

对应问题：

- 1. 多头真理
- 2. Override Ledger 缺口

要解决的事：

- 引入合同家族作为唯一故事真理源
- 把 `override_contracts` 从追读力债务专用，扩展为故事设定演进账本

### 5.2 上下文合同化工作流

对应问题：

- 3. 上下文截断黑洞
- 4. 知识延迟绑定与泛化割裂

要解决的事：

- 让 `context_manager` 合同优先
- 把通用知识预聚合为当前书的专属合同，而不是让写作时临时散查

### 5.3 写前校验工作流

对应问题：

- 5. 事后验尸
- 6. 缺乏大纲履约校验

要解决的事：

- 建立 review contract
- 建立写前禁区、写前消歧域、写后履约 diff

### 5.4 章节提交工作流

对应问题：

- 7. 跨存储事务割裂
- 8. 后置消歧污染风险
- 9. 消歧警告向后传染

要解决的事：

- 引入统一章节提交对象
- 把消歧和事实提取前移到提交校验链，而不是回写尾部兜底

### 5.5 事件主链工作流

对应问题：

- 10. 事件只有痕迹没有主链

要解决的事：

- 定义 canonical event log
- 让“事件”而不是“覆盖后的状态”成为演进触发器

---

## 6. 演进后的总体架构

### 6.1 总体分层

演进后的系统分为六层：

1. `Knowledge Layer`
2. `Reasoning Layer`
3. `Contract Layer`
4. `Runtime Assembly Layer`
5. `Chapter Commit Layer`
6. `Projection Layer`

### 6.2 总体链路

```text
用户意图 / 书籍题材诉求
        ↓
Reasoning Layer
        ↓
Story Contract Generator
        ↓
MASTER / VOLUME / CHAPTER / REVIEW / ANTI_PATTERNS
        ↓
context_manager(contract-first)
        ↓
规划 / 写作 / 审查
        ↓
CHAPTER_COMMIT
        ↓
Projection Writers
        ↓
state / index / summaries / memory / rag
```

### 6.3 最终判断

未来系统的主链不应是：

- `reference_search -> prompt -> reviewer -> data agent -> state`

而应是：

- `knowledge -> reasoning -> contract -> runtime pack -> chapter commit -> projections`

---

## 7. 单一真理源与优先级规则

### 7.1 故事真理源

故事系统的唯一真理源应为合同家族：

1. `MASTER_SETTING.json`
2. `VOLUME_BRIEF.json`
3. `CHAPTER_BRIEF.json`
4. `REVIEW_CONTRACT.json`
5. `anti_patterns.json`

其中：

- 分层真源是 `MASTER / VOLUME / CHAPTER`
- `anti_patterns.json` 是派生视图，不反向成为真源
- `REVIEW_CONTRACT.json` 是审查用派生合同

### 7.2 运行时优先级

运行时拼上下文时，优先级固定为：

1. `chapter contract`
2. `volume contract`
3. `master contract`
4. `题材与调性推理.csv`
5. `genre-profiles.md`
6. `templates/genres/*.md`
7. 其他局部 reference

一旦合同存在：

- `context_manager`
- `webnovel-plan`
- `webnovel-write`
- `webnovel-review`

都不得再输出与合同冲突的全局系统判断。

### 7.3 写后真理源

章节完成后，真理链固定为：

1. `CHAPTER_COMMIT`
2. 投影到 `state`
3. 投影到 `index`
4. 投影到 `summaries`
5. 投影到 `memory`

也就是说：

- `state / index / summary / memory` 不再是章节事实的并列真源
- 它们是 `CHAPTER_COMMIT` 的派生投影

---

## 8. 合同体系设计

### 8.1 合同家族

完整合同家族定义如下：

1. `MASTER_SETTING`
2. `VOLUME_BRIEF`
3. `CHAPTER_BRIEF`
4. `REVIEW_CONTRACT`
5. `ANTI_PATTERNS`
6. `CHAPTER_COMMIT`

这里新增 `CHAPTER_COMMIT`，原因很简单：

- 前五类合同负责“写之前”
- `CHAPTER_COMMIT` 负责“写之后”

如果没有它，系统就无法真正修复诊断里关于回写割裂、履约丢失、事件断链的问题。

### 8.2 合同职责

#### `MASTER_SETTING`

负责全书级稳定系统：

- 题材与调性
- 世界规则
- 核心人设
- 金手指边界
- 全局毒点
- 全局 override policy

#### `VOLUME_BRIEF`

负责卷级系统：

- 本卷冲突轴
- 本卷兑现目标
- 本卷阶段性角色关系
- 本卷节奏波形
- 本卷补充红线

#### `CHAPTER_BRIEF`

负责本章执行：

- 本章目标
- 本章场景策略
- 本章 hook
- must cover 节点
- 本章禁区
- 本章局部 override

#### `REVIEW_CONTRACT`

负责本次审查必须检查的事项：

- blocking rules
- 题材特定风险
- 大纲履约检查项
- 消歧检查项
- 高风险事实校验项

#### `ANTI_PATTERNS`

负责将可见层级的所有红线聚合为运行时平面视图。

#### `CHAPTER_COMMIT`

负责承载本章最终提交结果：

- 使用了哪些合同
- 实际发生了哪些事实
- 实际产生了哪些事件
- 是否完成了 outline/mandatory nodes
- 消歧是否通过
- review 是否通过
- 哪些投影已完成

### 8.3 字段类型

仍采用三类字段策略：

1. `locked`
2. `append_only`
3. `override_allowed`

并保留 `lock_policy`：

1. `system_locked`
2. `user_locked`
3. `story_locked`

### 8.4 覆盖规则

优先级固定为：

1. `chapter`
2. `volume`
3. `master`

但这不是静默覆盖，而是必须记录：

- `field`
- `base_value`
- `override_value`
- `source_level`
- `reason`
- `reason_tag`
- `approved_by`

### 8.5 override ledger 的新定位

当前 `override_contracts` 不能废弃，而应演进为统一 override ledger 的底座。

演进后的职责：

1. 记录追读力债务层面的软违背
2. 记录卷章对上层故事合同的受控覆盖
3. 记录需要上提到 `amend-master / amend-volume` 的提案

最终应区分三类记录：

1. `soft_deviation`
2. `contract_override`
3. `amend_proposal`

---

## 9. 章节提交主链设计

### 9.1 为什么必须新增提交主链

当前系统的问题不是“写完后没保存”，而是“写完后被拆成多处异步散写”。

这会导致：

- 状态不同步
- 消歧后置污染
- 履约丢失
- 事件断链

所以必须把章节完成后的提交改为：

- 先形成一个统一提交对象
- 再由投影器把它分发到各存储

### 9.2 `CHAPTER_COMMIT` 最小结构

最小应包含：

- `meta`
- `contract_refs`
- `outline_snapshot`
- `review_result`
- `fulfillment_result`
- `disambiguation_result`
- `accepted_events`
- `state_deltas`
- `entity_deltas`
- `projection_status`

### 9.3 提交流程

标准链路应为：

1. 读取 `CHAPTER_BRIEF`
2. 写作完成
3. 生成 `REVIEW_CONTRACT`
4. 完成审查
5. 生成 `CHAPTER_COMMIT` 草案
6. 校验履约、消歧、blocking rules
7. 通过后标记 commit accepted
8. 投影到各存储

### 9.4 投影层职责

投影层至少分成四个 writer：

1. `state_projection_writer`
2. `index_projection_writer`
3. `summary_projection_writer`
4. `memory_projection_writer`

未来可选：

5. `rag_projection_writer`

### 9.5 失败语义

一旦 `CHAPTER_COMMIT` 未通过，不允许：

1. 部分写入 `state`
2. 部分写入 `index`
3. 先写摘要再回头补状态
4. 让下一章读取未确认事实

也就是说：

- “章节已生成”不等于“章节已提交”
- 只有 `commit accepted` 才能进入事实主链

---

## 10. canonical event log 设计

### 10.1 当前问题

当前系统已经有：

- `state_changes`
- `relationship_events`
- `timeline_events`
- `world_rules`
- `open_loops`
- `reader_promises`

但这些都还是局部事件，没有统一事件主链。

### 10.2 演进目标

应新增统一事件视角：

- 所有章节提交都必须产出 `accepted_events`
- 投影层基于事件更新状态，而不是只根据最终值覆盖

### 10.3 事件类型

最小事件族建议包括：

1. `character_state_changed`
2. `relationship_changed`
3. `world_rule_revealed`
4. `world_rule_broken`
5. `power_breakthrough`
6. `artifact_obtained`
7. `promise_created`
8. `promise_paid_off`
9. `open_loop_created`
10. `open_loop_closed`

### 10.4 事件与合同的关系

事件不直接修改 `MASTER / VOLUME / CHAPTER`。

正确做法是：

1. 事件先进入 `CHAPTER_COMMIT.accepted_events`
2. 若事件触发上层设定变更条件，则生成 `amend proposal`
3. 人工确认后再更新上层合同

这样才能兼顾：

- 文学反转的灵活性
- 合同系统的稳定性

---

## 11. 写前校验与写后校验

### 11.1 写前校验

写前必须显式检查：

1. 当前章可见合同是否存在
2. 本章禁区是否完整
3. 是否存在高优先级消歧 pending
4. must cover 是否明确
5. 当前章是否需要局部 override 摘要

### 11.2 写后校验

写后必须显式检查：

1. `blocking rules`
2. `mandatory_nodes` 是否履约
3. `anti_patterns` 是否命中
4. 关键实体命名是否稳定
5. 是否产生需要上提的设定修改

### 11.3 大纲履约机制

当前系统的缺口之一，是只记录“写了什么”，不校验“该写的写了没有”。

因此 `CHAPTER_COMMIT` 必须新增：

- `planned_nodes`
- `covered_nodes`
- `missed_nodes`
- `extra_nodes`

最低要求：

- `missed_nodes` 非空时，不允许静默提交成功

### 11.4 消歧机制前移

消歧不能只在尾部回写阶段兜底。

应拆成两段：

1. 写前提供 `disambiguation domain`
   - 当前章允许出现的高频实体、别名、称谓集合
2. 写后在 `CHAPTER_COMMIT` 阶段再做提交校验

只有无法通过两段机制解决时，才进入 `disambiguation_pending`。

---

## 12. 现有模块的演进路径

### 12.1 `reference_search.py`

新定位：

- 底层 primitive
- CSV 搜索内核
- 不再承担系统聚合职责

### 12.2 `context_manager.py`

新定位：

- 合同优先的运行时装配器

演进顺序：

1. phase 1 保留原有结构
2. phase 1 新增 `story_contract` section
3. phase 2 固定 pack 优先级为 `chapter -> volume -> master -> old profile`
4. phase 3 移除与“全局系统生成”重叠的逻辑

### 12.3 `genre_aliases.py / genre_profile_builder.py / genre-profiles.md`

新定位：

- route table 建设期间的活跃种子源

演进顺序：

1. 人工把稳定字段迁入 `题材与调性推理.csv`
2. `story_system` 优先读 CSV
3. `genre-profiles.md` 退化为回退源和参考源

### 12.4 `state_manager`

新定位：

- `CHAPTER_COMMIT` 的投影写入器协调层

它不再承担“章节事实真源”的角色，而只负责：

- 把已接受 commit 的状态投影写入 `state.json`
- 与 SQLite 同步
- 维护局部原子写和恢复机制

### 12.5 `index.db`

新定位：

- 事实检索层
- 事件索引层
- 审计回溯层

不再承担“故事规则主源”职责。

### 12.6 `memory writer / orchestrator / summaries`

新定位：

- 事实补充层
- 历史回顾层
- 伏笔回收层

阶段要求：

1. phase 1 可继续沿用现状
2. phase 2 开始只消费已 accepted 的 `CHAPTER_COMMIT`
3. phase 3 与 canonical event log 对齐

### 12.7 `override_contracts`

新定位：

- 统一 override ledger 的底座

不能继续只服务追读力债务。

### 12.8 `scripts/data_modules/config.py`

新定位：

- 继续作为项目级统一配置入口

演进约束：

1. phase 1 直接复用现有 `DataModulesConfig`
2. `story_system` 新增配置必须挂在明确命名空间下
3. 禁止为 `story_system` 平行再造一套完全独立的配置树

否则后果会非常直接：

- runtime 一套预算
- contract 一套预算
- projection 一套路径

三套配置分叉后，合同系统会在工程层面重新失真。

---

## 13. 分阶段演进计划

### 13.1 Phase 0：现状收束准备

目标：

- 不改主流程，只明确真源和优先级

交付：

1. 统一文档化当前真源优先级
2. 明确 `context_manager` 的 contract 注入口
3. 明确 `genre-profiles.md` 的过渡期定位
4. 明确 `override_contracts` 的扩展方向

### 13.2 Phase 1：合同种子层

目标：

- 让系统第一次拥有稳定合同

交付：

1. `题材与调性推理.csv`
2. 最小 `MASTER_SETTING`
3. 最小 `CHAPTER_BRIEF`
4. `anti_patterns.json`
5. `context_manager` 读取合同

此阶段仍允许：

- 保留旧写作链
- 保留 `genre-profiles.md` 回退
- 不引入 `VOLUME_BRIEF`

### 13.3 Phase 2：合同优先运行时

目标：

- 让写作、规划、审查都以合同为主输入

交付：

1. `VOLUME_BRIEF`
2. `REVIEW_CONTRACT`
3. 写前禁区与消歧域
4. 大纲履约 diff
5. `context_manager` contract-first pack

此阶段的关键变化：

- “临时拼资料”不再是默认路径
- “合同优先 + 局部 reference 按需加载”成为默认路径

### 13.4 Phase 3：章节提交主链

目标：

- 让所有事实回写经过统一章节提交对象

交付：

1. `CHAPTER_COMMIT`
2. 四类 projection writers
3. accepted / rejected commit 语义
4. 写后回写改为 commit 驱动

此阶段完成后：

- 章节事实真源将从散写转为统一提交对象

### 13.5 Phase 4：统一事件主链

目标：

- 让事件成为系统演进的正式输入

交付：

1. canonical event log
2. 事件到投影的稳定映射
3. 事件到 amend proposal 的触发规则

### 13.6 Phase 5：旧链路降级

目标：

- 把旧中枢从主链降级为回退或投影层

退出条件：

1. 合同已成为默认主输入
2. `CHAPTER_COMMIT` 已成为默认提交主链
3. `genre-profiles.md` 已完成高频题材迁移
4. `context_manager` 不再独立生成与合同冲突的全局系统判断

---

## 14. 数据与目录建议

### 14.1 合同目录

本项目已有权威**运行时**目录术语，后续 story system 必须复用，不得自造新说法。

需要先明确一件事：

- 当前这个仓库只是**插件源码开发目录**
- 它不是插件安装后的运行时根目录
- story system 的落盘路径必须基于**Claude Code 安装后的真实运行目录模型**来定义

因此后续所有路径说明，都应基于运行时的三层目录：

1. `CLAUDE_PLUGIN_ROOT`
   - Claude Code 插件安装目录
   - 存放 `skills/ agents/ scripts/ references/`
   - **不允许**在这里写入小说项目数据
2. `WORKSPACE_ROOT`
   - 当前工作区根目录，可通过 `.claude/.webnovel-current-project` 指针解析当前书项目
3. `PROJECT_ROOT`
   - **书项目根目录**
   - 定义为：**包含 `.webnovel/state.json` 的目录**

`Story Contract` 和 `CHAPTER_COMMIT` 都是**某一本书**的持久化产物，因此必须落在 `PROJECT_ROOT`，而不是：

- 当前源码仓库目录
- `CLAUDE_PLUGIN_ROOT`
- `WORKSPACE_ROOT`

基于当前已有真实目录，可以直接参考：

- `WORKSPACE_ROOT = D:\wk\xiaoshuo`
- `PROJECT_ROOT = D:\wk\xiaoshuo\凡人资本论`
- 指针文件 = `D:\wk\xiaoshuo\.claude\.webnovel-current-project`

该例也说明两件事：

1. `PROJECT_ROOT` 是工作区内的某一本书目录
2. `PROJECT_ROOT` 自身可以是一个独立 git 仓库（例如当前示例里就存在 `.git/`）

建议目录如下：

```text
WORKSPACE_ROOT/
├── .claude/
│   └── .webnovel-current-project
├── 小说A/
├── 小说B/
└── ...

PROJECT_ROOT/
├── .git/                  # 可选：书项目自身可独立版本管理
├── 正文/
├── 大纲/
├── 设定集/
├── 审查报告/
├── .webnovel/
└── .story-system/
    ├── MASTER_SETTING.json
    ├── MASTER_SETTING.md
    ├── anti_patterns.json
    ├── anti_patterns.md
    ├── volumes/
    │   ├── volume_001.json
    │   └── volume_001.md
    ├── chapters/
    │   ├── chapter_001.json
    │   └── chapter_001.md
    ├── reviews/
    │   ├── chapter_001.review.json
    │   └── chapter_001.review.md
    └── commits/
        ├── chapter_001.commit.json
        └── chapter_001.commit.md
```

这里的 `.story-system/` 必须明确为：

- **相对于 `PROJECT_ROOT`**

而不是：

- 当前源码仓库目录
- `CLAUDE_PLUGIN_ROOT`
- `WORKSPACE_ROOT`
- 任意当前工作目录

如果后续 implementation plan 中出现“根目录”表述，必须显式区分：

1. `CLAUDE_PLUGIN_ROOT`
2. `WORKSPACE_ROOT`
3. `PROJECT_ROOT`

### 14.1.1 路径解析约束

所有运行时入口都应遵守现有统一规则：

1. 允许外部传入 `WORKSPACE_ROOT`
2. 统一经 `resolve_project_root(...)` 解析到真实 `PROJECT_ROOT`
3. 所有 `.story-system` 读写都基于解析后的 `PROJECT_ROOT`

这意味着：

- CLI 可以接受 `--project-root`，但它实际允许传入“书项目根目录或工作区根目录”
- 入口层负责解析
- 合同层和提交层只认最终解析后的 `PROJECT_ROOT`
- 如果用户当前只站在 `WORKSPACE_ROOT`，也应先经统一入口解析到真实书项目，再操作 `.story-system/`

### 14.2 真源规则

规则固定为：

1. `*.json` 是真源
2. `*.md` 是只读渲染产物
3. `reviews/` 和 `commits/` 也遵循相同规则

### 14.3 命名规范

统一使用零填充：

- `volume_001`
- `chapter_001`

不要把自然语言标题写进文件名。

---

## 15. 知识层承接策略

### 15.1 CSV 的职责

CSV 继续承担：

- 条目知识
- 路由知识
- 结构化红线
- 检索触发词与同义词

### 15.2 MD 的职责

MD 继续承担：

- 方法论
- 审查规则
- anti-AI
- 润色、口吻、排版规范

### 15.3 当前阶段的结论

在演进完成前，不应说“CSV 已完全替代 MD”。

正确说法是：

- CSV 承担规则与路由
- MD 承担方法论与执行手册
- 合同负责把当前书真正需要的那部分结构化知识前置收束出来

---

## 16. 测试与验证策略

### 16.1 总原则

不做“每条知识点一个测试”的重型方案。

### 16.2 必须验证的内容

最小验证集应覆盖：

1. 合同生成成功
2. 覆盖规则正确
3. `anti_patterns` 聚合正确
4. `context_manager` 能正确读取合同
5. `REVIEW_CONTRACT` 能正确表达 blocking rules
6. `CHAPTER_COMMIT` 能阻止未通过校验的回写
7. projection writers 只消费 accepted commit
8. 事件能进入 canonical event log

### 16.3 不需要做的事

不需要：

1. 为每条 CSV 内容单独断言
2. 为每个知识点做机械语义测试
3. 把数据内容测试做成主工作量

---

## 17. 文档与运维要求

### 17.1 文档更新要求

后续任何 implementation plan 都必须显式包含：

1. 合同 schema 文档更新
2. 目录结构文档更新
3. 运行流程文档更新
4. 迁移说明文档更新

### 17.2 运维接入要求

`.story-system` 不得成为运维盲区。

至少应接入：

1. preflight
2. dashboard
3. health check
4. backup / restore

### 17.3 健康检查最低项

最低应检查：

1. `MASTER_SETTING.json` 是否存在
2. 合同 schema 是否可读
3. `chapter commit` 是否存在 rejected 未处理积压
4. projection status 是否出现长期未完成

---

## 18. 最终架构结论

这份演进 spec 的最终判断可以压缩成四句话：

1. 当前系统的主要问题不是模块太少，而是主链缺失
2. 现有的 `context_manager / genre_* / state_manager / memory / override_contracts` 都应保留，但要重定位
3. 真正要新增的核心不是又一个检索入口，而是 `Story Contract + Chapter Commit + Override Ledger + Canonical Event Log`
4. 当合同成为写前真源、提交成为写后真源后，系统才算真正从“多中枢缝合”进化为“统一故事操作系统”

---

## 19. 实施建议

如果后续进入开发，不建议直接从“事件总线”开工。

正确顺序应是：

1. 先把合同种子层跑通
2. 再让运行时 contract-first
3. 再建立 `CHAPTER_COMMIT`
4. 最后统一事件主链

否则项目会先陷入“事件建模很完整，但写作主链仍然散乱”的伪进展。

这份 spec 的直接后续产物应当是：

- implementation plan

并且该 plan 必须显式包含：

1. 文档更新任务
2. 目录与路径语义更新任务
3. runtime 接入点更新任务
