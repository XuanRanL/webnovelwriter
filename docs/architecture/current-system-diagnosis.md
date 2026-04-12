# 当前系统架构诊断报告 (Current System Diagnosis)

> **文档状态**: 诊断报告 (未引入 Story Intelligence System Spec 前)
> **诊断前提**: 假设大语言模型（如 Opus 4.6）的指令遵循能力完美，能够完美解析并执行所有 Bash 命令和格式要求。
> **核心结论**: 系统的痛点不在于模型写不好或执行失误，而在于**系统提供给模型的信息结构、校验时机和数据流转机制存在根本性硬伤**。系统试图用一套松散的管道脚本（Pipeline）去管理极其复杂的网文世界状态机（State Machine），最终不可避免地导致长篇连载走向崩盘。
> 同时需要补一层更准确的校准：当前系统并不是完全没有结构化能力，而是**已经具备多个半成品中枢，但仍缺少统一故事合同（SSOT）与统一章节提交主链**。

---

## 一、 核心架构与真理源缺陷 (Architecture & Single Source of Truth)

### 1. 多头真理（Multiple Sources of Truth）导致的认知撕裂

* **现象**：系统的设定散落在 `state.json`（动态状态）、`genre-profiles.md`（静态调性）、`index.db`（碎片化实体）和 `memory`（长期事实）中。虽然 `context_manager`、`genre_*` 已经在尝试聚合这些信息，但它们本质上仍是运行时装配器和局部中枢，而不是统一的单一真理源（SSOT）。
* **危害**：当剧情发生合理反转或设定升级时，系统无法做到全局同步。模型会同时接到冲突的指令（例如 md 要求主角废柴隐忍，而 state 显示已经天下无敌）。极度聪明的模型为了兼顾双方，反而会写出精神分裂般的割裂剧情。

### 2. 设定演进账本仅有雏形，尚未覆盖核心世界设定（Override Ledger Gap）

* **现象**：网文的核心规则是会随着剧情推进被打破的（如主角打破了某项世界限制）。当前系统已在 v5.3 引入了 `override_contracts` 表（见 `index_debt_mixin.py`），具备完整的 CRUD 操作（含 `constraint_type`、`rationale_type`、`rationale_text`、`payback_plan`、`due_chapter`、`status`）。但该机制目前**仅服务于追读力债务系统的软建议违背记录**，尚未扩展为核心世界设定（力量体系、角色命运、世界规则）的演进账本。对于这些核心设定的修改，系统本质上仍只有静默覆盖（Overwrite）或局部投影更新。
* **危害**：没有机制明确告诉 AI 注意，卷五已经合法推翻了卷一的隐忍设定，现在的最高准则是无敌爽文。系统把所有的旧规则和新状态一锅端地喂给 AI，造成严重的上下文污染和逻辑死锁。Override Contract 的基础设施已经存在，但其应用范围的局限性使得它无法解决这个核心问题。

---

## 二、 上下文装配与知识供给痛点 (Context & Knowledge Assembly)

### 3. 机械截断导致的信息黑洞（The Blind Spot of Context Truncation）

* **现象**：`context_manager.py` 确实已经在做上下文聚合，且 `context_ranker.py` 已经对 alerts 等信息做了优先级排序与筛选（说明系统并非完全无脑塞上下文）。但最终输出仍采用按权重（`TEMPLATE_WEIGHTS`）和字数预算，强行截断字符串（`_compact_json_text`）的方式来组装上下文。
* **危害**：模型再聪明，也无法遵守它没看到的规则。关键毒点、核心力量限制或重要伏笔，极容易因为刚好超出字符串预算而被底层脚本静默丢弃。导致模型不得不靠幻觉（Hallucination）填补空白，引发设定崩塌。问题不在“没有聚合”，而在于**聚合后的输入仍可能被预算逻辑打成信息黑洞**。

### 4. 知识延迟绑定（Late-Binding）与泛化割裂

* **现象**：系统并不只是中途临时查 CSV，它其实已经有 `md 必读 + CSV 检索 + genre_profile` 的双轨资料体系。但在写作中，系统仍要求大模型在具体阶段按需调用 `reference_search.py` 查通用条目（如如何写战斗）。
* **危害**：查出来的大多是通用网文技巧，而不是本书专属设定。系统缺乏一个前置的聚合层把通用套路和本书主角特质、题材调性、系统边界揉合在一起，导致写出的剧情虽然套路标准，但千篇一律，缺乏本书的灵魂与特色。

---

## 三、 流程编排与校验机制漏洞 (Workflow & Verification)

### 5. 事后验尸而非事前避坑的防线设计

* **现象**：系统高度依赖 Step 3 的 Reviewer Agent 去审查**已经写完的正文**，发现 Blocking 毒点后再打回 Step 4（润色）修复。
* **危害**：防线设得太晚。如果模型在起草时犯了方向性或结构性错误（如写死了不该死的核心角色，或触碰了严重毒点），依靠润色（改表达不改事实）是根本救不回来的。这会导致无解的死循环，或只能产出打补丁式的劣质文本。

### 6. 缺乏大纲履约的强制校验（No Fulfillment Verification）

* **现象**：系统已经能读取 `chapter outline`、`plot_structure`、`mandatory_nodes`、`prohibitions` 这类计划信息，但在写后提交阶段，只会提取记录实际写了什么（What is），不会严谨地进行结构化 Diff，对比大纲要求写什么（What was planned vs. achieved，如 CBN/CEN 节点）。
* **危害**：如果模型因为篇幅原因漏写了一个关键的暗杀伏笔，系统只会完美地提取已写的内容，而不会报错大纲要求未履约。这会悄无声息地引发后续章节大纲的连锁崩盘。

---

## 四、 数据回写与后置处理隐患 (Data Write-back & Disambiguation)

### 7. 事务割裂与幽灵状态（Fragmented DB Transactions）

* **现象**：Step 5 要求将结果分别写入 `state.json`、`index.db`、`summaries` 和 `memory` 四个不同的地方。需要校准的是：当前 `state_manager` 对自身写盘已经有局部原子写和 pending 快照保护，但这仍然不是跨存储的章节级事务一致性（ACID）。此外，`StateManager` 内部还维护了 `state.json` + SQLite（`index.db`）的**双写同步逻辑**（`_sync_to_sqlite`、`_sync_pending_patches_to_sqlite`），包含 pending 快照恢复机制，这在单个模块内部就已经引入了额外的一致性复杂度。
* **危害**：风险存在于两个层面。**内层**：`StateManager` 的 JSON + SQLite 双写如果部分失败，虽然有快照恢复，但恢复逻辑本身也可能在极端情况下不完整。**外层**：四个存储的跨库写操作一旦中途发生中断，仍然会导致 DB 记录角色已死，而 `state.json` 里角色还活着，或摘要和长期记忆没有同步更新。这种幽灵状态会在生成下一章时把模型彻底搞疯。

### 8. 幻觉错误被后置消歧放大为索引污染风险（Index Pollution via Disambiguation）

* **现象**：如果在 Step 2 模型产生了幻觉，把主角林辰错写成了张辰，后置消歧未必会直接报错打回。需要校准的是：当前系统对消歧有置信度分层，不是无脑把所有错误都写死；但它确实存在一个风险窗口，**一旦错误命中“可采用”区间，后置消歧就可能把错误实体归并写入后续索引链路。**
* **危害**：这意味着纯粹的写作幻觉，不一定会被当场拦截，反而可能以“低置信但被采用”的形式被沉淀为别名、出场记录、关系记录或状态更新。长期来看，这仍会污染数据库，使后续消歧越来越乱。

### 9. 消歧警告的向后传染（Context Leaking）

* **现象**：如果 Step 5 发现模棱两可的名字且无法自动消歧，会将其记入 `state.json` 的 `disambiguation_pending`，高于阈值但仍不稳的则进入 `disambiguation_warnings`，并在写**下一章**时通过上下文装配链被继续读取。
* **危害**：上一章的消歧烂账，变成了下一章起草时的噪音。这极大地分散了模型写新剧情的注意力，甚至诱导模型在新章节中强行加戏去解释上一章的名字问题，破坏行文流畅度。

### 10. 状态投影主导，语义事件只有痕迹没有主链（State Overwrite vs. Delta Events）

* **现象**：Data Agent 和数据链并不是完全没有 Delta 事件，实际上已经存在：
  - `state_changes`
  - `relationship_events`
  - `timeline_events`
  - `world_rules`
  - `open_loops`
  - `reader_promises`

  其中关系事件层面，代码里已经有比 `relationships_new` 更完整的 `relationship_events` 表，具备较强的结构化能力；但这些事件整体仍分散在 `state`、`index`、`memory` 等不同层里，没有统一的 canonical event log。系统主链仍然更偏向“状态投影更新”，而不是“事件驱动更新”。
* **危害**：结果就是系统能记录“已经变成金丹”，却很难以统一方式表达“如何突破、消耗了什么资源、引发了什么异象、这次突破应如何修改上层世界规则”。这使得系统无法自动感知并触发设定升级或力量体系阈值扩展，模型仍然需要像瞎子摸象一样去猜目前的战力天花板。

---

## 总结

在没有引入 `Story Intelligence System Spec` 的前置契约约束之前，系统并不是完全靠大模型“裸奔”，而是已经靠多个半成品中枢在**缝缝补补**：

- `context_manager` + `context_ranker` 在做上下文聚合与优先级排序
- `genre_*` 在做题材归一化与画像构建
- `state_manager` 在做结构化状态回写（含 JSON + SQLite 双写同步）
- `memory writer / orchestrator` 在做长期事实沉淀
- `override_contracts` 在做追读力债务的违背记录（Override Ledger 雏形）

但这些能力还没有被收束成一个统一的故事事实系统。

因此，当前系统最根本的问题不是“模型不够强”，而是：

**系统已经有多个局部结构层（包括 Override Contract 雏形和 Delta 事件底座），但还没有统一故事合同（Story Contract）、统一章节提交主链（Commit Chain）和覆盖全局世界设定的统一演进账本（Override Ledger）。**

这也正是新架构的核心价值所在：

- 生成强约束的 `Master / Volume / Chapter` JSON 合同
- 建立显式的 Override 账本
- 事前给足绝对红线、系统边界和消歧域
- 把 `state / index / summary / memory / RAG` 从“散落真理源”降级为“合同提交后的投影层”

只有提供完美、无歧义、可追溯且前后一致的输入，大模型才能持续、稳定地输出高质量的长篇连载。
