# 长期记忆论文与项目调研报告

## 文档目标

本文档汇总大语言模型长期记忆方向中较有代表性的论文、基准和开源项目，重点回答四个问题：

- 长期记忆问题到底在解决什么
- 这个领域近两年的主流技术路线是什么
- 哪些项目已经做到较强的工程落地
- 对当前 `webnovel-writer` 最值得借鉴的能力是什么

说明：

- 本报告优先使用论文原文、arXiv 页面和项目官方仓库
- 报告不是穷举式综述，而是面向架构决策的工程调研
- 截止本次检索时间，最新参考到 2026 年 3 月可见资料

## 一句话结论

当前长期记忆方向已经很明确地形成了三条主线：

1. `外部记忆 + 检索`：把历史信息存到外部存储，再按需召回
2. `分层记忆 + 编排`：把近期上下文、历史证据、长期摘要分层管理
3. `图结构 / 时态记忆`：用知识图谱或时态图来处理事实更新、关系变化和时间推理

对我们项目最直接有用的不是“更大上下文”，而是：

- 独立的长期摘要层
- 统一的记忆编排层
- 面向事实更新的状态管理

## 为什么长期记忆仍然是独立问题

代表性基准都在说明同一件事：

- 单纯增加上下文窗口，并不能稳定解决长期记忆
- 模型在多会话、多时间点、事实更新、跨章节整合时仍然容易退化
- 记忆系统的核心不只是“存”，还包括“写入、压缩、检索、更新、冲突裁决”

这一点在以下基准中都被反复验证：

- `LoCoMo`
- `LongMemEval`
- `BEAM`

## 评测基准

### 1. LoCoMo

论文：

- `Evaluating Very Long-Term Conversational Memory of LLM Agents`
- arXiv:2402.17753
- 链接：<https://arxiv.org/abs/2402.17753>

关键点：

- 数据集聚焦“超长期对话记忆”
- 每条对话平均约 `300 turns`
- 平均约 `9K tokens`
- 覆盖最多 `35 sessions`
- 评测问答、事件总结、多模态对话生成

价值：

- 是很多后续 memory 系统对比的常用基准
- 强调多轮会话与长期连续性，而不只是单文档检索

来源：LoCoMo 论文摘要页 <https://arxiv.org/abs/2402.17753>

### 2. LongMemEval

论文：

- `LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory`
- arXiv:2410.10813
- 链接：<https://arxiv.org/abs/2410.10813>

关键点：

- 明确拆出五种长期记忆能力：
  - 信息抽取
  - 多会话推理
  - 时间推理
  - 知识更新
  - 拒答
- 包含 `500` 个精心构造的问题
- 论文指出，商业助手和长上下文模型在持续交互上的准确率会出现约 `30%` 下滑

价值：

- 比纯“召回率”更接近真实助手场景
- 很适合衡量“事实更新”和“跨会话推理”

来源：LongMemEval 论文摘要页 <https://arxiv.org/abs/2410.10813>

### 3. BEAM

论文：

- `Beyond a Million Tokens: Benchmarking and Enhancing Long-Term Memory in LLMs`
- arXiv:2510.27246
- 链接：<https://arxiv.org/abs/2510.27246>

关键点：

- 生成最长可达 `10M tokens` 的连贯对话
- 构建 `100` 段对话和 `2000` 个校验问题
- 同时提出 `LIGHT` 记忆框架
- 作者报告 LIGHT 相对强基线平均提升 `3.5% - 12.69%`

价值：

- 把“超长上下文”与“长期记忆”区分得更清楚
- 对我们这种长篇创作系统非常有参考价值

来源：BEAM/LIGHT 论文摘要页 <https://arxiv.org/abs/2510.27246>

## 代表论文

### A. 早期外部记忆路线

#### MemoryBank

- 论文：`MemoryBank: Enhancing Large Language Models with Long-Term Memory`
- arXiv:2305.10250
- 链接：<https://arxiv.org/abs/2305.10250>

核心思想：

- 把对话历史转成外部记忆
- 检索相关记忆参与回答
- 引入类似“遗忘曲线”的更新机制
- 强调用户画像和长期陪伴式交互

意义：

- 很早就提出“记忆不是纯存档，而是要更新和遗忘”
- 适合人格化、陪伴式、个性化场景

局限：

- 更偏对话陪伴
- 工程结构相对较早，抽象层级不够细

#### LongMem

- 论文：`Augmenting Language Models with Long-Term Memory`
- arXiv:2306.07174
- 链接：<https://arxiv.org/abs/2306.07174>

核心思想：

- 冻结 backbone LLM 作为 memory encoder
- 旁路引入 retriever/reader side-network
- 把长期上下文缓存为外部记忆

意义：

- 代表“模型架构级长期记忆”的路线
- 不只是 prompt engineering，而是显式引入 memory 模块

局限：

- 对我们当前项目这种插件式工程系统，可复用性不如外部存储方案高

### B. 分层记忆与虚拟上下文路线

#### MemGPT

- 论文：`MemGPT: Towards LLMs as Operating Systems`
- arXiv:2310.08560
- 链接：<https://arxiv.org/abs/2310.08560>

核心思想：

- 把 LLM 看成“应用层”
- 通过类似操作系统的虚拟内存管理，把不同记忆层在上下文和外部存储间切换
- 用 memory tier 和 control flow 管理超出窗口的历史

意义：

- 是“分层记忆编排”这条路线的关键代表作
- 强调 memory paging、分层存储和自管理

局限：

- 偏 agent runtime
- 对小说写作系统来说，直接照搬成本较高

#### LIGHT

- 论文：`Beyond a Million Tokens: Benchmarking and Enhancing Long-Term Memory in LLMs`
- arXiv:2510.27246
- 链接：<https://arxiv.org/abs/2510.27246>

核心思想：

- 明确拆成三层：
  - `episodic memory`
  - `working memory`
  - `scratchpad`
- 用统一编排器组合三者

意义：

- 和我们项目当前改造方向最接近
- 对“长期写作上下文”非常适配

局限：

- 目前还是较新的研究工作
- 更像工程原型，不是现成平台

### C. 生产化记忆层路线

#### Mem0

- 论文：`Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory`
- arXiv:2504.19413
- 链接：<https://arxiv.org/abs/2504.19413>
- 官方仓库：<https://github.com/mem0ai/mem0>

核心思想：

- 动态提取对话中的显著信息
- 做记忆 consolidation
- 检索时优先使用精炼后的 memory，而不是整段历史
- 还有 graph-based 变体

官方声称：

- 在 LoCoMo 上相对 OpenAI Memory 有 `+26%` 提升
- 相对 full-context 有更低延迟与 token 成本

工程价值：

- 非常重视生产环境指标：延迟、token 成本、SDK 接入
- 是“记忆层产品化”的代表项目

局限：

- 更适合通用 agent/assistant
- 对小说写作的结构化剧情状态，还需要定制

来源：

- 论文摘要页 <https://arxiv.org/abs/2504.19413>
- 官方仓库 README <https://github.com/mem0ai/mem0>

#### Zep

- 论文：`Zep: A Temporal Knowledge Graph Architecture for Agent Memory`
- arXiv:2501.13956
- 链接：<https://arxiv.org/abs/2501.13956>

核心思想：

- 用 `Graphiti` 作为时态知识图谱引擎
- 将对话和业务数据融合到一个可追踪历史的时态图中
- 强调动态知识集成、历史关系维护、低延迟检索

论文报告：

- 在 DMR 上优于 MemGPT
- 在 LongMemEval 上最高可提升 `18.5%`
- 相对基线延迟降低 `90%`

工程价值：

- 很适合“事实会变、关系会变、时间有强语义”的场景
- 对角色关系、势力变化、设定修订这类小说问题很有参考性

来源：Zep 论文摘要页 <https://arxiv.org/abs/2501.13956>

#### MIRIX

- 论文：`MIRIX: Multi-Agent Memory System for LLM-Based Agents`
- arXiv:2507.07957
- 链接：<https://arxiv.org/abs/2507.07957>

核心思想：

- 设计六类记忆：
  - Core
  - Episodic
  - Semantic
  - Procedural
  - Resource Memory
  - Knowledge Vault
- 用多 Agent 协同管理更新和检索
- 扩展到多模态记忆

意义：

- 展示了“记忆分工继续细化”的趋势
- 证明未来 memory system 不一定只分三层

局限：

- 架构更复杂
- 对当前项目来说有参考价值，但不适合第一阶段直接引入

来源：MIRIX 论文摘要页 <https://arxiv.org/abs/2507.07957>

## 代表开源项目

### 1. Letta

- 仓库：<https://github.com/letta-ai/letta>
- 说明：原 MemGPT 项目已经并入 Letta

官方定位：

- `stateful agents`
- 强调 agent 可跨会话持续存在、学习、自我改进

值得关注的点：

- 长寿命 agent
- memory blocks
- 持久化 agent runtime

对我们的启发：

- 适合作为“长期存在的创作 Agent”参考
- 但它更像完整 agent 平台，不适合直接嵌入当前插件架构

来源：

- Letta 仓库 README <https://github.com/letta-ai/letta>
- 官方说明 <https://www.letta.com/blog/memgpt-and-letta>

### 2. Mem0

- 仓库：<https://github.com/mem0ai/mem0>

官方定位：

- `Universal memory layer for AI Agents`

值得关注的点：

- SDK 化程度高
- 支持自托管和托管
- 强调多层 memory、用户偏好、会话和 agent 状态

对我们的启发：

- 非常适合作为“独立 memory layer”的工程参考
- 尤其适合看它怎么做 API、接入层和 memory 抽取流程

来源：Mem0 官方仓库 README <https://github.com/mem0ai/mem0>

### 3. Graphiti

- 仓库：<https://github.com/getzep/graphiti>

官方定位：

- `Build Real-Time Knowledge Graphs for AI Agents`

特点：

- 时态知识图谱
- 支持实体、事实关系、原始 episodes、ontology
- 适合动态环境中的 agent memory

对我们的启发：

- 非常适合角色关系、势力结构、事件时间线
- 如果后续想做“剧情知识图谱”，Graphiti/Zep 是最值得研究的一类

来源：Graphiti 官方仓库 README <https://github.com/getzep/graphiti>

## 研究趋势总结

### 趋势 1：从“长上下文”转向“记忆系统”

近两年最明确的结论是：

- 长上下文不等于长期记忆
- 真正有效的方案都在做外部 memory、结构化抽取、分层编排

### 趋势 2：从“检索片段”转向“记忆写入与更新”

早期系统重点是：

- 怎么检索历史

近年的重点已经变成：

- 记忆写什么
- 什么时候合并
- 什么时候标记过期
- 遇到冲突怎么裁决

### 趋势 3：从“平面向量库”转向“图结构和时态结构”

在纯向量检索之外，越来越多系统开始强调：

- entity / relation
- temporal validity
- provenance
- update / invalidation

这对任何“事实会变化”的系统都非常关键。

### 趋势 4：生产系统开始关注成本和延迟

像 Mem0、Zep 这类项目，不再只讲准确率，而是同时强调：

- p95 延迟
- token 成本
- 开发者接入成本
- 托管与可观测性

## 对当前项目最有用的结论

### 最值得借鉴的不是某一个项目，而是三类能力

#### 1. LIGHT 的分层思想

最适合我们当前项目的核心抽象仍然是：

- `working memory`
- `episodic memory`
- `scratchpad`

原因：

- 我们已经有 working 和 episodic 的基础
- 当前最缺的正是 scratchpad

#### 2. Zep/Graphiti 的时态事实处理

对小说系统特别重要的是：

- 同一角色状态会变
- 同一关系会演化
- 同一设定可能被修订

所以光做向量检索不够，必须有事实状态和时间语义。

#### 3. Mem0 的工程落地方式

Mem0 很值得借鉴的是：

- memory layer 独立化
- SDK/接口清晰
- 生产环境关注延迟和 token 成本

这对我们把长期记忆做成独立模块非常有帮助。

## 对 `webnovel-writer` 的映射建议

### 可以直接吸收的部分

- LIGHT：三层记忆结构
- Mem0：独立 memory layer 设计
- Zep/Graphiti：关系和时间线建模方式

### 暂时不建议直接照搬的部分

- Letta：完整 stateful agent 平台，体量过大
- MIRIX：分类太细，第一阶段会过重
- LongMem：更偏模型架构级改造，不适合当前插件工程

## 我的建议排序

如果以“对当前项目收益 / 改造成本”排序，我建议优先关注：

1. `LIGHT`
2. `Mem0`
3. `Zep / Graphiti`
4. `MemGPT / Letta`
5. `MIRIX`
6. `MemoryBank`
7. `LongMem`

## 结论

长期记忆方向现在已经很清楚：

- 上下文窗口只是基础设施，不是最终答案
- 真正有效的是“分层记忆 + 持续写入 + 智能检索 + 冲突管理”

对当前项目来说，最现实的路线不是做一个通用 agent 平台，而是：

- 保留现有 `state.json / index.db / vectors.db`
- 新增 `scratchpad` 长期摘要层
- 再加一个统一的 `memory orchestrator`

这条路线与近期论文结论最一致，也最贴合当前系统基础。

## 参考链接

- MemoryBank: <https://arxiv.org/abs/2305.10250>
- LongMem: <https://arxiv.org/abs/2306.07174>
- MemGPT: <https://arxiv.org/abs/2310.08560>
- LoCoMo: <https://arxiv.org/abs/2402.17753>
- LongMemEval: <https://arxiv.org/abs/2410.10813>
- Zep: <https://arxiv.org/abs/2501.13956>
- Mem0 论文: <https://arxiv.org/abs/2504.19413>
- Mem0 仓库: <https://github.com/mem0ai/mem0>
- MIRIX: <https://arxiv.org/abs/2507.07957>
- Graphiti 仓库: <https://github.com/getzep/graphiti>
- Letta 仓库: <https://github.com/letta-ai/letta>
- Letta / MemGPT 迁移说明: <https://www.letta.com/blog/memgpt-and-letta>
- LIGHT / BEAM: <https://arxiv.org/abs/2510.27246>
