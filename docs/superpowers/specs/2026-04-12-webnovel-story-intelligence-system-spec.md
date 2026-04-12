# Webnovel Writer Story Intelligence System 理想态重构 Spec

> 日期：2026-04-12
> 状态：草案 v2
> 定位：理想态总架构蓝图

---

## 1. 文档定位

### 1.1 这份 spec 解决什么问题

当前 `webnovel-writer` 已经具备以下能力：

- `references/csv/` 提供条目化知识检索
- `references/*.md` 提供方法论与流程约束
- `scripts/data_modules/` 提供 state / index / memory / context 的运行时能力
- `skills/webnovel-*` 提供初始化、规划、写作、审查等执行入口

但当前系统更准确的状态是：

- 已经具备 `L0 / L1 / L2` 的按步加载能力
- 已经具备 `md 必读 + CSV 检索` 的双轨 reference 体系
- 已经具备 `context_manager + genre_*` 这类半成品聚合能力

真正缺的不是“会不会按需读取资料”，而是：

1. 缺少统一的**聚合中间层**，把题材、节奏、桥段、毒点、人设、金手指装成一个系统
2. `reference_search.py` 只能返回散条目，不能生成稳定的故事系统合同
3. `context_manager / genre_*` 还没有演进成可持久化的 `Story Contract`
4. 全局设定与章节局部要求没有稳定的 `Master + Overrides` 承载结构

本 spec 的目标不是继续增强“检索”，而是把项目升级成一个：

- 先推理
- 再聚合
- 再持久化
- 最后由 skill 消费合同

的 `Story Intelligence System`。

### 1.2 与现有 spec 的关系

仓库中已有：

- `2026-04-09-skills-restructure-and-reference-gaps.md`
- `2026-04-12-story-system-pro-max-retrofit-spec.md`

它们分别解决：

- `2026-04-09`：`skills / references / scripts` 的职责边界与资料缺口
- `2026-04-12 retrofit`：在不大改现有链路的前提下，为现系统补一个较保守的 `story_system`

本 spec 与它们不同：

- 本 spec **不以兼容旧入口为前提**
- 本 spec **不遵守最小改动原则**
- 本 spec 讨论的是项目的**理想态重构目标**

换句话说：

- `retrofit spec` 是“怎么稳妥地补”
- 本 spec 是“如果重做一版，最优架构应该长什么样”

### 1.2.1 与 retrofit spec 的复用 / 替代边界

为避免后续实施时两份 spec 相互打架，这里明确边界：

#### 可直接复用的部分

- CSV 通用列契约
- `reference_search.py` 作为底层 primitive 的定位
- `.story-system/` 作为持久化目录的基本方向
- anti-pattern 的“显式负面字段优先”原则
- `StorySystemDict` 作为 phase 1 JSON contract 的种子结构

#### 本 spec 对 retrofit 的超集扩展

- 把两层持久化扩展为 `Master / Volume / Chapter` 三层
- 把 `StorySystemDict` 扩展为合同家族，而不再只是一份聚合结果
- 把 `skills` 的定位从“直接读 reference”升级为“合同优先 + 局部按需加载”
- 把 `state / memory / index` 明确下沉为运行时事实层

#### 本 spec 对 retrofit 的替代决策

- `story_system.py` 不再只是一个附加脚本，而是未来的一线中枢
- `genre-profiles.md` 不再担任核心配置中心
- `templates/genres/*.md` 不再担任题材主知识源

如果两份 spec 出现冲突，裁决原则为：

1. phase 1 工程落地，优先服从 `retrofit spec`
2. phase 2 及以后重构目标，优先服从本 spec

### 1.3 借鉴对象

本 spec 明确借鉴 `ui-ux-pro-max-skill` 的核心链路，而不是照搬它的文件名：

1. 多域数据仓
2. reasoning engine
3. 聚合器
4. anti-patterns 汇总
5. 稳定输出 contract
6. skill 以 contract 为主消费系统信息

对 `webnovel-writer` 来说，真正需要学习的是这条系统链，而不是“多几个 CSV”。

---

## 2. 设计结论

### 2.1 一句话结论

`webnovel-writer` 的理想态，不应再是：

- `md reference + csv search + skill 手动拼装`

而应重构为：

- `Reasoning Layer + Multi-domain Knowledge Layer + Story System Generator + Persistence Contracts + Skill Runtime`

### 2.2 核心判断

#### 判断 1：CSV 应成为主知识层

`references/csv/` 已经具备良好的条目化方向，理想态中它应升级为：

- 主知识层
- 主检索层
- 主规则层

而不是“补充资料”。

#### 判断 2：MD 应降级为方法论层

`references/*.md` 中的方法论、审查规则、AI 味规避、流程规范，仍应保留为 md。

但它们不再直接承担：

- 题材配置中心
- 故事系统主设定
- skill 主输入源

#### 判断 3：skill 不应再直接读散乱 reference

`webnovel-init / plan / write / review` 的最佳状态是：

- 不直接拼装多份 reference
- 不直接决定先查什么表、再查什么 md
- 只消费统一生成的 story contract

但这里的“只消费合同”，不是说 skill 从此不再按步加载任何 reference，而是指：

- 全局设定、题材调性、毒点红线、系统边界应优先来自 contract
- 局部写作技法、场景模式、命名规则、排版和审查规范仍可按 step 按需加载

#### 判断 4：原有 data_modules 不是废弃，而是下沉为运行时底盘

现有：

- `state.json`
- `memory_contract`
- `index.db / vectors / bm25`
- `context_manager`
- `query_router`

都仍然有价值。

但它们的定位应从“主流程拼装器”变为：

- 运行时事实层
- 检索证据层
- 写作执行支持层

### 2.3 Contract 与渐进式披露的分工

本 spec 不推翻 `2026-04-09` 中“渐进式披露 + 双轨制 + 按需加载”的哲学，而是重新划分消费边界。

#### 由 contract 优先承接的内容

- 题材推理结果
- 全局调性与节奏承诺
- `anti_patterns`
- `system_constraints`
- 卷级 / 章级目标
- override ledger

这些内容的共同特点是：

- 影响全局
- 需要跨 step 稳定一致
- 不适合每个 skill 临时再拼一次

但运行时还必须补一条消费边界：

- skill 默认消费的是**最终结算态**
- 完整 override ledger 默认属于**审计 / debug / dashboard 数据**
- 写作 prompt 只应拿到“本章相关的 override 摘要”，不应注入全量历史账本

#### 继续由按需 reference 承接的内容

- 写作技法
- 场景模式
- 命名规则
- 对话口吻
- 排版规范
- 润色与 anti-ai 修正
- review schema 与 blocking override 规则

这些内容的共同特点是：

- 强依赖具体 step
- 触发条件明确
- 更像“局部执行手册”而不是“全局故事合同”

因此理想态不是“contract 替代所有 reference”，而是：

- contract 接管全局系统信息
- step-bound reference 保留局部执行知识

---

## 3. 目标与非目标

### 3.1 目标

理想态重构要达成 8 个目标：

1. 建立统一的题材推理层
2. 建立统一的多域知识仓
3. 建立统一的故事系统生成器
4. 建立统一的 anti-pattern 汇总机制
5. 建立统一的 `Master / Volume / Chapter` 合同结构
6. 建立统一的持久化目录 `.story-system/`
7. 让 `skills` 只消费合同，不再直接拼 reference
8. 让现有 state / index / memory 数据链继续作为运行时事实层

### 3.2 非目标

本 spec 明确不追求以下事情：

1. 不保留旧 CLI 的完全兼容调用方式
2. 不要求 `reference_search.py` 继续作为一线入口
3. 不要求 `genre-profiles.md` 继续担任核心配置中心
4. 不要求每个旧模板都被保留原职责
5. 不要求为每条知识点编写测试

### 3.3 知识迁移边界

知识迁移必须遵守以下硬规则：

1. `AI味`、去 AI 腔、润色替换规则，不进入 CSV
2. 这类内容继续保留在独立 md 文件
3. 知识迁移只允许人工整理和人工录入
4. 禁止编写“把 md 自动抽成 csv 条目”的迁移脚本

这里的“禁止脚本迁移”，针对的是知识内容迁移，不针对正常的工程脚本开发。

---

## 4. 理想态总架构

### 4.1 总体分层

理想态系统分为五层：

1. `Reasoning Layer`
2. `Knowledge Layer`
3. `Contract Layer`
4. `Persistence Layer`
5. `Skill Runtime Layer`

### 4.2 分层关系

```text
用户意图 / 题材诉求
        ↓
Reasoning Layer
        ↓
Knowledge Layer
        ↓
Story System Generator
        ↓
Contract Layer
        ↓
Persistence Layer
        ↓
Skill Runtime Layer
        ↓
正文 / 大纲 / 审查 / 状态回写
```

### 4.3 推荐目录

```text
${CLAUDE_PLUGIN_ROOT}/
├── story_system/
│   ├── data/
│   │   ├── reasoning/
│   │   ├── rules/
│   │   ├── tropes/
│   │   ├── characters/
│   │   ├── pacing/
│   │   └── naming/
│   ├── engine/
│   │   ├── search_engine.py
│   │   ├── reasoning_engine.py
│   │   ├── aggregator.py
│   │   ├── anti_pattern_engine.py
│   │   ├── contract_builder.py
│   │   ├── renderer.py
│   │   └── persistence.py
│   ├── runtime/
│   │   ├── memory_bridge.py
│   │   ├── state_bridge.py
│   │   ├── index_bridge.py
│   │   └── review_bridge.py
│   ├── templates/
│   │   ├── master_setting.md.j2
│   │   ├── volume_brief.md.j2
│   │   ├── chapter_brief.md.j2
│   │   ├── anti_patterns.md.j2
│   │   └── review_contract.md.j2
│   └── cli.py
├── references/
│   ├── csv/
│   ├── shared/
│   ├── outlining/
│   └── review/
├── skills/
└── scripts/

${PROJECT_ROOT}/
├── .webnovel/
└── .story-system/
```

说明：

- 这里采用的是**插件运行时目录模型**，不是当前源码仓库目录模型
- 当前开发仓库只用于产出插件，不参与运行时 story contract 的落盘路径判定
- `CLAUDE_PLUGIN_ROOT` 是插件安装目录，负责承载代码、skills、scripts、references
- `PROJECT_ROOT` 是真实书项目根目录，定义为包含 `.webnovel/state.json` 的目录
- `.story-system/` 必须落在 `PROJECT_ROOT` 下，而不是 `CLAUDE_PLUGIN_ROOT`
- `story_system/` 是新的一线中枢
- 旧 `scripts/reference_search.py` 与 `scripts/data_modules/` 可继续存在，但不再承载主设计中心
- `engine/` 下的多个文件表示“职责分层目标”，不是 day 1 必须拆成 7 个文件

### 4.4 初始实现颗粒度

理想态需要清晰的职责边界，但不意味着第一版工程实现必须把每个职责拆成独立文件。

推荐做法：

1. phase 1 可先合并为 `search_reasoning.py + contract_runtime.py + persistence.py`
2. phase 2 再按职责拆成更细模块

也就是说：

- 架构分层要先定清
- 文件颗粒度可以渐进收敛

---

## 5. Reasoning Layer 设计

### 5.1 职责

`Reasoning Layer` 是整个系统的大脑，负责把模糊的创作意图，转成可执行的系统约束。

它回答的不是：

- “某个技巧怎么写”

而是：

- 这本书本质上是什么题材
- 核心读者承诺是什么
- 应该优先交付什么爽点
- 节奏应该偏快还是偏压抑
- 哪些毒点绝对不能碰
- 后续应该优先检索哪些知识域

### 5.2 核心数据表

新增核心路由表：

- 文件名：`题材与调性推理.csv`
- 中文名：`题材与调性推理`

### 5.3 建议字段

`题材与调性推理.csv` 仍然必须遵守现有 CSV 通用契约。

这里列出的，是**通用列之外的专属列**：

| 字段 | 说明 |
|------|------|
| `题材/流派` | 主题材名 |
| `中文名` | 供人读的标准名 |
| `题材别名` | 黑话、俗称、平台常用叫法 |
| `核心调性` | 草根逆袭、极致拉扯、压抑蓄爆、诡异压迫等 |
| `节奏策略` | 黄金三章、慢热蓄势、持续兑现、节点爆发等 |
| `主爽点` | 该题材最核心的兑现类型 |
| `辅助爽点` | 次级交付 |
| `冲突引擎` | 冲突主要如何生成 |
| `适配人设` | 推荐的人设框架 |
| `适配金手指` | 推荐的外挂或设定类型 |
| `适配桥段` | 高频桥段方向 |
| `强制禁忌/毒点` | 题材级红线 |
| `推荐基础检索表` | 生成系统时优先查的基础域 |
| `推荐动态检索表` | 生成卷/章简报时优先查的动态域 |
| `默认查询词` | 当用户输入模糊时的扩展查询词 |

### 5.4 题材推理原则

推理顺序应为：

1. 识别主题材
2. 识别辅题材
3. 识别核心承诺
4. 锁定调性
5. 锁定节奏
6. 锁定毒点
7. 生成后续多域检索计划

这里必须允许“主辅题材”结构，而不是只识别单一标签。

### 5.5 多标签推理规则

网文题材经常不是单标签，而是：

- `赛博朋克 + 克苏鲁`
- `修仙 + 直播`
- `都市异能 + 恋爱修罗场`

因此 reasoning engine 不应采用简单的 `Top 1` 命中逻辑，而应支持多标签加权融合。

建议规则如下：

1. 先识别 `主题材`
2. 再识别 `辅题材`
3. `核心调性` 以主题材为主，辅题材只允许调味，不得反客为主
4. `强制禁忌/毒点` 采用并集策略
5. `主爽点` 按主题材排序，`辅助爽点` 允许来自辅题材
6. `推荐基础检索表 / 推荐动态检索表` 采用加权合并，而不是单条覆盖

简化说法：

- 调性允许主次
- 毒点必须并集
- 检索计划必须融合

这条规则必须写进实现，而不能只停留在概念层。

### 5.6 Reasoning Engine 实现边界

reasoning engine 不能走向两个极端：

- 不能试图用纯规则代码“理解一切文学语义”
- 也不能把题材识别、调性融合、毒点判断全部放给 LLM 黑盒完成

推荐采用 `L0 / L1 / L2` 三层：

1. `L0 Deterministic Router`
2. `L1 Deterministic Fusion`
3. `L2 LLM Classifier / Synthesizer`

#### L0：确定性路由

负责：

- alias 归一化
- 显式标签提取
- BM25 / 关键词候选召回
- 置信度初算

这层的职责是把自然语言意图收敛成**候选集合**，而不是直接输出最终文学判断。

#### L1：确定性融合

负责：

- 主辅题材候选加权
- 毒点并集
- 基础检索计划融合
- 生成“可离线运行”的 baseline contract

这层保证：即便没有 LLM，也能对清晰输入产出一个可用但偏保守的 `MASTER`。

#### L2：LLM 分类 / 融合

只有在以下场景才启用：

- 输入低置信
- 题材混搭明显
- 调性描述高度模糊
- 多候选之间差距不足以稳定裁决

LLM 的职责不是自由发挥，而是：

- 在候选集合内做分类或重排
- 解释为什么某个融合更合理
- 产出严格结构化 JSON

随后必须经过本地 schema 校验，失败则回退到 L1 baseline。

默认要求：

- 离线可运行
- 不依赖 LLM 也能生成可用的 `MASTER`
- LLM 负责语义补洞与模糊融合，不负责绕过规则层直接产生命令式合同

fallback 策略：

1. 若 `L0 + L1` 已得到高置信结果，则不调用 LLM
2. 若结果低置信，先输出候选题材列表和冲突点
3. 若启用 LLM 辅助，再让 LLM 仅基于候选集合输出结构化融合建议
4. 若 LLM 输出未通过校验，则丢弃该结果并回退到确定性 baseline

这样做的目的，是把：

- 成本
- 延迟
- 可用性
- 可解释性
- 可测试性

同时控制在工程可接受范围内

---

## 6. Knowledge Layer 设计

### 6.1 知识分层

理想态中，知识层应分成三类，而不是全塞在一起：

1. `Reasoning Tables`
2. `Rule Tables`
3. `Methodology Docs`

### 6.2 Reasoning Tables

这些表负责“全局推理与路由”：

| 文件名 | 中文名 | 角色 |
|------|------|------|
| `题材与调性推理.csv` | 题材与调性推理 | 题材路由与全局调度 |

### 6.3 Rule Tables

这些表负责“结构化规则与条目知识”：

| 文件名 | 中文名 | 角色 |
|------|------|------|
| `命名规则.csv` | 命名规则 | 人名、地名、势力、功法等命名规则 |
| `场景写法.csv` | 场景写法 | 战斗、对话、冲突、桥段场景的写法模式 |
| `写作技法.csv` | 写作技法 | 技法与误区 |
| `桥段套路.csv` | 桥段套路 | 套路、铺垫、反转、变种 |
| `人设与关系.csv` | 人设与关系 | 人设原型、关系互动、禁区 |
| `爽点与节奏.csv` | 爽点与节奏 | 节奏阶段、情绪调度、崩盘误区 |
| `金手指与设定.csv` | 金手指与设定 | 金手指、世界规则、限制、代价 |

建议后续补两张表：

| 文件名 | 中文名 | 角色 |
|------|------|------|
| `冲突设计.csv` | 冲突设计 | 冲突触发源、升级链、回收方式 |
| `反派机制.csv` | 反派机制 | 反派逻辑、层级、失败方式、禁区 |

### 6.4 Methodology Docs

这些内容继续保留 md，不进 csv：

- `review-schema.md`
- `reading-power-taxonomy.md`
- `shared/core-constraints.md`
- `webnovel-write/references/anti-ai-guide.md`
- `webnovel-write/references/polish-guide.md`
- `webnovel-write/references/style-adapter.md`

原因很简单：

- 它们是流程与方法论
- 不是检索条目
- 强行塞入 csv 会劣化表达

---

## 7. Contract Layer 设计

### 7.1 核心思想

skill 不应再直接消费：

- 散乱 CSV 结果
- 多份 md 引用
- 零散模板

skill 只应消费标准合同。

### 7.2 合同类型

理想态至少有五类合同：

1. `MASTER_SETTING`
2. `VOLUME_BRIEF`
3. `CHAPTER_BRIEF`
4. `ANTI_PATTERNS`
5. `REVIEW_CONTRACT`

### 7.3 每类合同的职责

#### MASTER_SETTING

负责全书级稳定设定：

- 题材与调性
- 主角与核心角色基线
- 世界规则与金手指边界
- 全局节奏策略
- 全局毒点

#### VOLUME_BRIEF

负责卷级目标：

- 本卷核心冲突
- 本卷兑现目标
- 本卷反派层级
- 本卷关键桥段
- 本卷节奏波形

#### CHAPTER_BRIEF

负责本章执行要求：

- 本章目标
- 本章桥段
- 本章场景策略
- 本章情绪预期
- 本章禁区

#### ANTI_PATTERNS

负责把所有题材级、桥段级、角色级、节奏级毒点聚合成显式红线。

#### REVIEW_CONTRACT

负责告诉审查环节：

- 本章/本卷必须检查什么
- 哪些红线最优先
- 哪些风险点是题材特定风险

### 7.4 双产物要求与单一真理源

每份合同可以同时存在两种产物：

1. Markdown
2. JSON

但必须明确：

- `JSON` 是唯一真理源
- `Markdown` 只是从 `JSON` 渲染出的只读产物

原因：

- Markdown 给人看
- JSON 给程序和 skill 稳定消费
- 一旦允许人手改 Markdown，就会出现双重真理源

因此必须执行以下硬规则：

1. 所有持久化更新先改 JSON，再渲染 Markdown
2. Markdown 顶部必须显式标注 `GENERATED FILE / DO NOT EDIT`
3. skill、runtime、dashboard、测试一律只消费 JSON，不消费 Markdown 作为真值
4. 人工修订只能通过 CLI / Dashboard / 显式 JSON 编辑入口完成，不支持“手改 Markdown 自动回写”

如果 Markdown 被人工修改：

- 视为非受支持操作
- 下次渲染时允许被覆盖

### 7.4.1 与 Retrofit Spec 的 Markdown 迁移裁决

这里需要与 `retrofit spec` 的 marker 方案明确裁决，避免两份 spec 在 phase 1/2 打架。

#### phase 1

- 服从 `retrofit spec`
- 若 Markdown 中存在 `<!-- STORY-SYSTEM:BEGIN -->` / `END` 自动生成区块，则脚本只更新 marker 内内容
- marker 外的人工备注区可暂时保留

#### phase 2 及以后

- 服从本 spec
- Markdown 退化为从 JSON 全量重建的只读渲染产物
- phase 1 的 marker 兼容逻辑可以废弃

无论 phase 1 还是 phase 2，都必须坚持：

- `JSON` 是唯一真理源
- marker 外人工备注不构成合同真值
- skill/runtime/test 一律不以 Markdown 作为真值输入

### 7.5 JSON 合同校验

既然 JSON 要作为 skill 的稳定输入，就不能只“尽量输出正确”，而必须做结构校验。

建议实现：

1. 为 `MASTER_SETTING / VOLUME_BRIEF / CHAPTER_BRIEF / REVIEW_CONTRACT` 定义显式 schema
2. 使用 `Pydantic` 或等价 schema 校验机制
3. 在生成 JSON 后先做本地校验，再落盘
4. 校验失败时不得生成“看起来成功、实际结构不稳定”的伪合同

最低要求：

- `anti_patterns` 必须始终是列表
- `overrides` 必须始终是结构化对象
- `locked / append_only / override_allowed` 必须可机读
- `lock_policy` 必须始终可机读
- 缺省值要稳定，不能时而为空字符串、时而为空数组

这不是“测试增强”，而是合同系统的基础完整性约束。

### 7.5.1 Schema Version 与兼容策略

所有合同 JSON 都必须带版本元数据，最低要求：

- `schema_version`
- `contract_type`
- `generator_version`

推荐规则：

1. `schema_version` 使用显式字符串，例如 `story-system/v1`
2. 读取方必须先校验 `schema_version`，再决定：
   - 直接读取
   - 运行显式 migrator
   - 报错并要求人工升级
3. 禁止在 schema 不兼容时静默忽略字段
4. phase 1 由 `StorySystemDict` 过渡来的合同，也必须显式写入版本号，而不是默认“无版本”

否则 phase 1 生成的旧合同进入 phase 2 后，会在新代码下出现“静默丢字段”或“校验失败但原因不明”的问题。

### 7.6 合同 JSON 基线

本 spec 不从零重新发明 JSON contract，而采用以下策略：

1. phase 1 复用 `retrofit spec` 中的 `StorySystemDict` 作为基础结构
2. phase 2 在其外层扩展出 `MASTER / VOLUME / CHAPTER / REVIEW / ANTI_PATTERNS` 五类合同

最小字段要求如下。

#### `MASTER_SETTING.json`

至少包含：

- `meta`
- `genre_reasoning`
- `core_rules`
- `anti_patterns`
- `system_constraints`
- `contracts`
- `overrides`

#### `VOLUME_BRIEF.json`

至少包含：

- `meta`
- `volume_goal`
- `selected_tropes`
- `selected_pacing`
- `selected_scenes`
- `anti_patterns`
- `system_constraints`
- `overrides`

#### `CHAPTER_BRIEF.json`

至少包含：

- `meta`
- `chapter_goal`
- `scene_strategy`
- `hook_strategy`
- `must_cover`
- `anti_patterns`
- `system_constraints`
- `overrides`

这里的 `system_constraints` 与 `anti_patterns` 必须区分：

- `anti_patterns`：明确禁止项
- `system_constraints`：能力边界、世界规则、数值限制

一个实用判据是：

- 违反后会直接让读者觉得“有毒、崩盘、降智”的，归入 `anti_patterns`
- 违反后会先造成设定自洽性破裂、逻辑漏洞或数值失衡的，归入 `system_constraints`

例如：

- `金手指每天只能用三次` 属于 `system_constraints`
- `打脸桥段必须靠反派强行降智才能成立` 属于 `anti_patterns`

#### `REVIEW_CONTRACT.json`

至少包含：

- `meta`
- `must_check`
- `blocking_rules`
- `genre_specific_risks`
- `anti_patterns`
- `system_constraints`
- `review_thresholds`
- `overrides`

其中：

- `must_check`：本章/本卷必须重点检查的审查项
- `blocking_rules`：命中后直接阻断通过的规则
- `genre_specific_risks`：题材特定高风险点
- `review_thresholds`：各维度最低通过阈值或 blocking 条件

### 7.6.1 `StorySystemDict` 到合同家族的映射

为避免 phase 1 的 `StorySystemDict` 到 phase 2 的合同家族迁移时产生歧义，这里给出最小映射。

| `StorySystemDict` 字段 | phase 2 目标位置 | 说明 |
|------|------|------|
| `meta` | `MASTER_SETTING.meta` | 生成来源、查询词、时间戳等元信息 |
| `route` | `MASTER_SETTING.genre_reasoning` | 题材路由、候选题材、命中依据 |
| `master_constraints` | `MASTER_SETTING.core_rules` + `MASTER_SETTING.system_constraints` | 题材调性、世界边界、硬约束分拆进入核心规则与系统边界 |
| `base_context` | `MASTER_SETTING.contracts.base_context_seed` | 基础表命中结果作为全书级种子上下文 |
| `dynamic_context` | `VOLUME_BRIEF.selected_*` + `CHAPTER_BRIEF.scene_strategy / hook_strategy / must_cover` | phase 2 由“动态上下文”拆成卷级选择与章级执行要求 |
| `anti_patterns` | 各级合同中的 `anti_patterns` + 派生 `anti_patterns.json` | 条目级与题材级毒点进入各合同，再生成运行时聚合视图 |
| `override_policy` | `MASTER_SETTING.contracts.override_policy` | 字段覆盖规则与默认 policy |
| `source_trace` | 各合同 `meta.source_trace` 或审计区 | 调试、审计与追溯信息 |

这张映射表的作用不是冻结最终字段名，而是明确：

- phase 1 的扁平聚合结果不会直接消失
- 它会被拆分并沉淀到更细粒度的合同家族中
- 实施时不得靠“语义猜测”去决定字段归属

---

## 8. Persistence Layer 设计

### 8.1 目录规范

在真实书项目根目录 `PROJECT_ROOT` 下建立：

```text
PROJECT_ROOT/
├── .webnovel/
└── .story-system/
    ├── MASTER_SETTING.md
    ├── MASTER_SETTING.json
    ├── anti_patterns.md
    ├── anti_patterns.json
    ├── volumes/
    │   ├── volume_001.md
    │   ├── volume_001.json
    │   └── ...
    └── chapters/
        ├── chapter_001.md
        ├── chapter_001.json
        └── ...
```

补充规则：

- `*.json` 是合同真源
- `*.md` 是渲染产物
- 渲染器必须支持“从 JSON 全量重建 Markdown”
- skills/agents 默认从 `WORKSPACE_ROOT` 出发，但必须先统一解析到真实 `PROJECT_ROOT` 再读写 `.story-system/`

### 8.1.1 `ANTI_PATTERNS` 独立文件与各级合同的关系

这里必须避免双真理源：

1. `MASTER_SETTING / VOLUME_BRIEF / CHAPTER_BRIEF` 中各自的 `anti_patterns` 字段，才是**分层真源**
2. `.story-system/` 根目录下的 `anti_patterns.json` 是**派生聚合视图**
3. `anti_patterns.md` 只从 `anti_patterns.json` 渲染

也就是说：

- `MASTER_SETTING.json.anti_patterns` 负责全书级红线
- `VOLUME_BRIEF.json.anti_patterns` 负责卷级补充红线
- `CHAPTER_BRIEF.json.anti_patterns` 负责章级补充红线
- `anti_patterns.json` 负责把“当前可见层级”的红线汇总成运行时/审计友好的扁平视图

若出现冲突，以各级合同中的分层字段为准，`anti_patterns.json` 必须重算，不得反向成为真源。

### 8.1.2 命名与版本控制约束

文件命名规范：

- 卷文件统一使用零填充编号：`volume_001.json`
- 章文件统一使用零填充编号：`chapter_001.json`
- 人类可读标题放在 `meta.title` 中，而不是写进文件名

版本控制建议：

- `.story-system/*.json` 与其对应的主 Markdown 渲染文件应默认纳入 git 追踪
- 它们属于项目级合同，不是临时缓存
- 仅调试 diff、health report、临时审计快照等可放入 `.gitignore`

### 8.2 覆盖规则

覆盖优先级固定为：

1. `chapter_xxx`
2. `volume_xxx`
3. `MASTER_SETTING`

但覆盖不是“静默替换”，而必须显式记录覆盖行为。

### 8.2.1 三层覆盖矩阵

`Master / Volume / Chapter` 的覆盖关系必须按字段类型区分，而不是统一“下层覆盖上层”。

| 字段类型 | Master -> Volume | Volume -> Chapter | 说明 |
|------|------|------|------|
| `locked` | 默认不可直接覆盖 | 默认不可直接覆盖 | 是否允许通过 `amend-*` 突破，取决于 `lock_policy` |
| `append_only` | 可追加，不可删除 | 可追加，不可删除 | 最终值为并集 |
| `override_allowed` | 可覆盖，需记录 reason | 可覆盖，需记录 reason | 最终值取最近一层 |

补充规则：

1. `Master.locked` 对 `Volume / Chapter` 都生效
2. `Volume.locked` 只约束本卷下属 `Chapter`
3. `Chapter` 不能直接“解锁”上层已锁定字段
4. `append_only` 字段的最终值始终是 `Master + Volume + Chapter` 的合并结果
5. `override_allowed` 字段的最终值采用最近一层，但必须保留 override ledger

### 8.2.1.1 `lock_policy`

为避免把小说创作中的“合理反转”也物理锁死，所有 `locked` 字段都必须额外带一个 `lock_policy`：

1. `system_locked`
2. `user_locked`
3. `story_locked`

含义如下：

- `system_locked`：系统 schema、基础运行约束、不可被下游合同修改
- `user_locked`：用户明确给出的硬约束，运行时不得自动修改，只能由用户显式确认后上游修订
- `story_locked`：当前故事系统中的核心稳定设定，不能被 `Volume / Chapter` 直接覆盖，但允许通过 `amend-master / amend-volume proposal + 人工确认` 上游改写

也就是说：

- `locked` 仍然存在
- 但不是所有 `locked` 都是同一强度
- 真正允许剧情反转的出口，是“先提修订建议，再改上层合同”，而不是让 `Chapter` 直接冲破锁

### 8.2.2 冲突覆盖记录

当 `chapter_xxx` 或 `volume_xxx` 与上层合同发生冲突时，生成器必须产出显式 override 标记，而不是只保留最终值。

Markdown 层建议使用类似格式：

- `本章节奏：[Override 自 MASTER: 慢热蓄势 -> 极限爆发]`
- `本章桥段：[Override 自 VOLUME: 试探对峙 -> 当场打脸]`

JSON 层至少要记录：

- `field`
- `base_value`
- `override_value`
- `source_level`
- `reason`

目的不是给人审美，而是让模型和后续脚本明确知道：

- 这里发生了状态切换
- 这是受控覆盖，不是随机漂移

### 8.2.3 Override Ledger 消费边界

override ledger 必须保留，但默认不应整包注入写作 prompt。

推荐分成两种消费模式：

1. `audit/debug mode`
2. `runtime prompt mode`

#### audit/debug mode

允许读取完整账本，用于：

- dashboard 审计
- 合同 diff
- 健康检查
- 问题排查

#### runtime prompt mode

只应暴露：

- 当前字段的最终生效值
- 本章 / 本卷直接相关的 override 摘要
- 必要的覆盖原因短句

默认禁止：

- 把历史全量 override ledger 直接塞进 `webnovel-write` prompt
- 把几十章前的覆盖记录反复注入当前章节上下文

原因很简单：

- 这会浪费 token
- 会制造噪音
- 会让模型更关注“历史解释”而不是“当前执行约束”

### 8.2.4 覆盖原因字段

所有 `override_allowed` 字段在发生覆盖时，都应尽量附带 `reason`。

推荐原因标签：

- `ARC_ESCALATION`
- `CHAPTER_PAYOFF`
- `TWIST_REQUIREMENT`
- `POV_SWITCH`
- `CONFLICT_INTENSIFICATION`

这些标签是推荐值，不是封闭枚举。

允许格式：

- `reason_tag + free_text`
- 纯 `free_text`

没有原因的覆盖，只能视为低可信覆盖。

### 8.3 字段类型

字段必须被标记为三类之一：

1. `locked`
2. `append_only`
3. `override_allowed`

示例：

- `世界规则`：`locked`
- `全局毒点`：`append_only`
- `本章桥段策略`：`override_allowed`

没有这个字段级规则，后续局部覆盖会失控。

补充规则：

- 若字段为 `locked`，则必须同时声明 `lock_policy`
- `lock_policy` 未声明时，默认按 `story_locked` 处理，不允许静默放宽

对于 `append_only` 字段，还应补一条规则：

- 允许新增
- 不允许删除既有上层约束

尤其是：

- `anti_patterns`
- `世界规则限制`
- `金手指边界`

这些字段一旦下层能删除上层内容，合同体系就会失去刚性。

此外必须明确 phase 1 的去重策略：

1. `append_only` 默认**不做语义级自动合并**
2. 对字符串列表，去重键为规范化后的文本：
   - 去首尾空白
   - 折叠连续空白
   - 统一常见全角/半角分隔差异
3. 对结构化对象，去重键必须显式定义；若未定义，则保留并标记为待审计
4. 对 `anti_patterns`：
   - 文本完全一致时去重
   - 文本不同但语义相近时，phase 1 默认**同时保留**
   - 若上层和下层只是数值阈值不同（如 300 字 vs 200 字），不得静默删除更严格版本

也就是说，phase 1 的策略是：

- 宁可保留重叠项
- 不可静默弱化上层红线
- 更激进的语义去重留到后续显式规则或人工审计

### 8.4 持久化入口

对 skill / agent / 测试体系可见的**稳定入口**，必须挂到现有统一 CLI `webnovel.py` 下，而不是在主链里直接引入第二套平行入口。

理想态 CLI 应支持：

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" story-system generate-master --genre "修仙退婚流"
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" story-system generate-volume --title "拍卖会卷"
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" story-system generate-chapter --query "拍卖会打脸"
```

如果保留 `story_system/cli.py`，它也只能作为：

- 开发期本地调试入口
- 内部封装入口

而不应成为 skill/prompt 直接依赖的外部命令。

原因：

- 当前项目已有统一 CLI、project_root 解析、workspace pointer、registry、prompt 完整性校验
- 若 story system 另起一套外部 CLI，skills、tests、dashboard、文档会立刻分叉
- 因此对外只保留 `webnovel.py story-system ...` 一条稳定入口

参数设计补充规则：

- 优先使用命名参数，而不是依赖带空格的位置参数
- 这样可以降低 PowerShell / Bash / zsh 下的转义差异
- 对 skill 暴露的示例命令也应遵守这个约束

此外必须预留显式合同修订入口：

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" story-system amend-master --event "主角获得第二核心金手指"
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" story-system amend-volume --volume 2 --event "阵营关系反转"
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" story-system refresh-chapter --chapter 15
```

这类命令的职责不是“随便重算”，而是：

1. 读取当前合同
2. 读取运行时重大事件
3. 只在允许变更的字段上做受控修订
4. 记录修订原因与修订时间

### 8.4.1 幂等性与覆盖策略

合同生成与修订命令必须遵守幂等性规则。

#### `generate-*`

1. 若目标合同不存在：创建
2. 若目标合同已存在且输入指纹相同：直接返回现有合同，不重复覆盖
3. 若目标合同已存在且输入指纹不同：默认拒绝静默覆盖，并提示使用：
   - `amend-*`
   - 或显式 `--force-rebuild`

也就是说：

- `generate-master` 不是“无限次覆盖”
- 它是“首次生成 + 相同输入幂等返回”

#### `amend-*`

- 是合同的**语义修订入口**
- 用于在已有合同基础上追加或修改受控字段
- 不应伪装成重新生成

#### `--force-rebuild`

- 属于显式破坏性再生成
- 必须由调用方主动声明
- 执行前应先备份旧 JSON 或写入历史快照

### 8.4.2 phase 1 并发约束

phase 1 不应假定 `.story-system/*.json` 已具备复杂的多写者并发合并能力。

因此最低要求是：

1. `generate-* / amend-* / refresh-*` 对同一目标文件必须串行执行
2. 实现上应使用文件锁或等价互斥机制
3. 若目标已被其他进程持有写锁，应返回显式 `BUSY / RETRY` 错误，而不是继续写入
4. 真正的多写者合并策略留到 day 2+ 单独设计

---

## 9. Skill Runtime Layer 设计

### 9.1 总原则

skill 只负责执行，不负责系统拼装。

### 9.2 `webnovel-init`

职责应收敛为：

1. 理解开书意图
2. 调用 `generate-master`
3. 先落 `.story-system/MASTER_SETTING.json`
4. 再渲染 `.story-system/MASTER_SETTING.md`
5. 最后把结果写入设定集骨架

### 9.3 `webnovel-plan`

职责应收敛为：

1. 读取 `MASTER_SETTING`
2. 调用 `generate-volume`
3. 调用 `generate-chapter`
4. 产出卷纲、章纲、时间线

如果规划阶段发现以下事件，允许提出 `amend-master / amend-volume`：

- 新核心阵营形成
- 世界规则新增硬限制
- 金手指边界发生明确扩展
- 题材承诺发生结构性偏移

默认流程应为：

1. plan skill 识别到“可能需要修订”
2. 调用 `contract-auditor / diff analyzer` 生成结构化修订建议
3. 输出人类可读的修订摘要与受影响字段
4. 由用户确认后再执行 `amend-master / amend-volume`

除非系统明确配置了自动修订策略，否则不应由 plan skill 自行改写 `MASTER`

它不应该再自己决定：

- 先读哪些题材 md
- 再查哪些 csv
- 再拼哪些规则

这些应该由 story system 统一处理。

### 9.4 `webnovel-write`

职责应收敛为：

1. 读取 `chapter brief`
2. 若不存在则回退 `volume brief`
3. 再回退 `master`
4. 读取该层级最终结算后的有效字段
5. 只注入本章直接相关的 override 摘要
6. 再结合 runtime memory/state/context 写正文

写作阶段默认不允许直接修改 `MASTER_SETTING`。

只有在检测到“重大结构事件”时，才允许通过显式 hook 进入：

- `amend-master`
- `amend-volume`

重大结构事件示例：

- 主角新增长期保留的核心能力
- 世界观新增不可逆规则
- 核心阵营关系永久翻转
- 主线承诺发生升级而非临时偏移

也就是说：

- 运行时事实可以推动合同修订
- 但必须通过显式修订入口
- 不能让 `MASTER` 因章节波动而持续漂移

推荐增加一个独立钩子：

- `contract-auditor`

它的职责不是改合同，而是：

1. 比较当前运行时事实与上层合同
2. 判断是“临时章节偏移”还是“应升级为合同修订”
3. 生成 `amend proposal`
4. 等待用户确认

### 9.5 `webnovel-review`

职责应收敛为：

1. 读取 `review contract`
2. 读取 `anti_patterns`
3. 按合同做结构化审查
4. 将结果回写 review/index/state

---

## 10. 原有数据链的承接方案

这是本 spec 最关键的部分之一：不是抛弃旧数据链，而是重新定位。

### 10.1 `references/csv/`

新定位：

- 主知识层
- 主规则层
- 主检索层

### 10.2 `references/*.md`

新定位：

- 方法论层
- 流程规范层
- 审查规则层
- 在 CSV 覆盖度不足的阶段，仍可作为过渡期活跃知识源

### 10.3 `templates/genres/*.md`

新定位：

- 降级为“样例模板层”
- 可作为人工参考和初始化草稿
- 在 route table 覆盖度不足前，仍可作为补充题材源

### 10.4 `templates/output/*.md`

新定位：

- 升级为 story-system 的渲染模板来源

### 10.5 `scripts/reference_search.py`

新定位：

- 底层 primitive
- 可复用的 CSV 搜索内核
- 不再作为 skill 主入口

### 10.6 `scripts/data_modules/context_manager.py`

新定位：

- 运行时上下文装配器
- 消费 `story-system contract + memory/state/index`
- 不再负责“全局故事系统生成”

演进路径应为：

1. phase 1 保留 `context_manager`，不做平地重写
2. phase 1 让它优先消费 contract，同时继续聚合 state / summaries / reader_signal / plot_structure
3. phase 2 把其中与“全局系统生成”重叠的逻辑逐步抽到 `story_system`
4. phase 3 再把 `context_manager` 收敛为纯运行时上下文装配器

也就是说：

- 不是直接废弃
- 而是先接入，再抽离，再收敛

### 10.6.1 Contract 注入口

Day 2 以后，`context_manager` 必须有明确的 contract 注入口，而不是只在文档层说“合同优先”。

最小要求：

1. `_build_pack()` 读取 `.story-system/` 中当前章可见的合同
2. pack 中新增显式 section，例如 `story_contract`
3. `story_contract` 的优先级高于旧的 `genre_profile` 摘要和临时全局拼装结果
4. 若合同缺失，再回退到现有 `genre_profile + global + reader_signal` 组装链

推荐顺序：

1. `chapter contract`
2. `volume contract`
3. `master contract`
4. 现有 `genre_profile / global / references`

换句话说，contract-first 必须落成真实的 pack 组装顺序，而不是停留在 skill 文本。

### 10.6.2 `genre_aliases.py` / `genre_profile_builder.py` / `genre-profiles.md`

这些模块和文档不是“旧包袱”，而是 route table 建设前的重要种子源。

新定位：

- `genre_aliases.py`：继续作为题材归一化字典的现役来源
- `genre_profile_builder.py`：继续作为复合题材 hints 的现役来源
- `genre-profiles.md`：在 phase 1 / phase 2 期间，继续作为结构化题材参考源

它们的退出方式不应是“一刀切降级”，而应是：

1. 先把其中稳定字段人工迁入 `题材与调性推理.csv`
2. 再让 `story_system` 优先读 CSV、缺省回退 md
3. 只有在 CSV 覆盖度达到阈值后，`genre-profiles.md` 才从主源降级为参考源

### 10.6.3 过渡期题材真源优先级

在 phase 1 / phase 2 期间，题材相关信息不能出现“双真源并列”。

优先级必须固定为：

1. `.story-system` 中的 contract
2. `题材与调性推理.csv`
3. `genre-profiles.md`
4. `templates/genres/*.md`

约束：

- 一旦 contract 已存在，`context_manager` 不得再独立输出与 contract 冲突的题材结论
- `genre-profiles.md` 在过渡期只能作为回退源或补充说明源
- `templates/genres/*.md` 在过渡期只能作为样例/补充题材源

否则就会出现：

- contract 说 A
- context pack 仍在塞 B
- skill 最终又混用了 C

这会直接破坏 contract-first 目标

### 10.7 `state.json`

新定位：

- 写作过程状态机
- 角色当前状态
- 章节推进状态

它不是故事总设定中心。

### 10.8 `index.db / vectors / bm25`

新定位：

- 运行期检索证据层
- 剧情事实回溯层
- 不是规则知识层

### 10.9 `memory_contract / orchestrator / summaries`

新定位：

- 长期记忆层
- 已发生事实层
- 伏笔与回收跟踪层

这一层与 CSV 的关系应为：

- `CSV` 给规则
- `memory` 给事实
- `story_system` 负责把规则和事实一起装进合同

### 10.9.1 Memory 最低可用标准

理想态合同系统不能假设 memory 所有子模块都已经工业化完成。

phase 1 的最低事实输入标准应为：

1. `state.json`
2. 最近章节摘要
3. `index.db` 中可直接读取的实体、关系、状态变化

`MemoryOrchestrator` 可作为增强项，但不是 phase 1 的硬依赖。

如果 memory 子系统某些组件不可用，合同系统的降级策略应为：

- 继续生成规则合同
- 对事实合同降级为“state + summaries + index facts”
- 不因 memory 半成品状态阻断 `generate-master / generate-volume`

### 10.10 迁移阶段划分

这部分虽然是理想态 spec，也需要给出最基本的迁移判断标准。

#### Day 1 变更

- 新增 `题材与调性推理.csv`
- 新增最小 `generate-master`
- 保留现有 `reference_search.py`
- 保留现有 `context_manager`
- 保留 `genre-profiles.md` 作为活跃题材源
- skill 继续按 `2026-04-09` 的 L0/L1/L2 策略运行
- `story-system` 先以内核模块存在，不强制对 skill 暴露
- 若提供 CLI，仅先以 `webnovel.py story-system ...` 形式接入统一入口

#### Day 2 变更

- 引入 `Volume` 层合同
- skill 改为“合同优先 + 局部 reference 按需加载”
- `genre-profiles.md` 仍可作为回退源，不应提前降级
- `context_manager` 正式注入 `story_contract`
- dashboard / preflight / health / backup 开始识别 `.story-system`

#### Day 3 及以后

- 在满足知识密度阈值后，`templates/genres/*.md` 逐步退出主链
- `reference_search.py` 只作为底层 primitive
- `story_system` 成为技能层的唯一系统入口

### 10.10.1 知识密度切换阈值

在以下条件满足前，不应把 `genre-profiles.md` 和 `templates/genres/*.md` 提前降级：

1. `题材与调性推理.csv` 已覆盖当前系统支持的主流主题材
2. `genre_aliases.py` 中的高频别名能在 route table 中找到稳定归一化目标
3. init / plan / write 的代表性题材输入，经人工抽样验证后，大部分可以直接由 `CSV + contract` 生成可用结果
4. 对当前活跃题材家族，至少已有一轮真实项目验证，而不是只靠静态录入

简单说：

- 不是 CSV 一出现就替换 md
- 而是 CSV 达到“可稳定承接主链”的知识密度后，才逐步切换

### 10.10.2 Contract 接管边界

Day 2 以后，contract 应优先接管：

- 题材调性
- 毒点红线
- 全局系统边界
- 卷级 / 章级执行目标

继续由 step-bound reference 保留：

- 局部写作技法
- 局部场景模式
- 命名与语汇
- 润色、排版、anti-ai、review schema

运行时还必须补一条：

- `context_manager` 和 `webnovel-write` 默认读取**最终结算态合同**
- 完整 override ledger 只在 debug / dashboard / health report 中默认展开

### 10.11 `scripts/data_modules/config.py`

当前 `DataModulesConfig` 已经是项目级事实上的统一配置入口，覆盖：

- 路径
- 检索参数
- 上下文预算
- memory / index / review 相关调优

理想态 `story_system` 不应再平行发明第二套完全独立的配置树。

推荐策略：

1. phase 1 直接复用 `DataModulesConfig`
2. 新增配置统一采用 `story_system_*` 命名空间
3. 若后续单独拆出 `StorySystemConfig`，也应只是 `DataModulesConfig` 的薄包装或子视图，而不是完全分家

必须避免的反模式：

- 一套配置给 runtime 用
- 另一套配置给 story system 用
- 两边字段重名但语义不同

那样会让 contract、context、memory 三条链路重新分叉。

### 10.12 `.story-system` 的运维接入

既然 `.story-system` 被定义为新的持久化真源，它就不能处于现有运维链路的盲区。

至少需要接入以下四类系统：

#### preflight

在 Day 2 以后，`preflight` 至少应增加：

- `.story-system/MASTER_SETTING.md` 是否存在
- `.story-system/MASTER_SETTING.json` 是否存在
- JSON 合同是否可读

#### dashboard / watcher

dashboard 不应只监听 `.webnovel/`。

至少还应关注：

- `.story-system/MASTER_SETTING.*`
- `.story-system/volumes/*.json`
- `.story-system/chapters/*.json`

否则合同变更后，前端不会刷新。

#### health / status report

状态报告不应只覆盖 `.webnovel/state.json` 和现有运行时数据。

还应增加：

- 合同存在性检查
- 合同新鲜度检查
- override ledger 摘要
- contract / state 是否明显冲突的健康提醒

#### backup / fallback backup

Git 模式下通常天然覆盖 `.story-system/`，但本地降级备份也必须覆盖它。

最低要求：

- Git 不可用时，fallback backup 不能只备份 `.webnovel/state.json`
- 至少应同时备份 `.story-system/` 的当前合同文件

否则恢复点会丢失新的系统真源。

---

## 11. 旧模块去留决策

### 11.1 保留并降级

以下模块保留，但降级为下层能力：

- `reference_search.py`
- `query_router.py`
- `context_manager.py`
- `genre_aliases.py`
- `genre_profile_builder.py`

其中：

- `context_manager.py` 更准确的路径是“保留并演进后收敛”
- `genre_aliases.py / genre_profile_builder.py` 更准确的路径是“保留并迁移其知识到 route table”

### 11.2 保留并重定位

以下目录保留，但职责改变：

- `references/csv/`
- `references/shared/`
- `references/outlining/`
- `templates/output/`

### 11.3 保留但不再担任主源

以下内容继续保留，但不再是主系统输入：

- `references/genre-profiles.md`
- `templates/genres/*.md`

### 11.4 应新增的一线模块

理想态应新增：

- `story_system/engine/search_engine.py`
- `story_system/engine/reasoning_engine.py`
- `story_system/engine/aggregator.py`
- `story_system/engine/anti_pattern_engine.py`
- `story_system/engine/contract_builder.py`
- `story_system/engine/renderer.py`
- `story_system/engine/persistence.py`

---

## 12. Anti-Patterns 统一机制

### 12.1 统一原则

理想态不要求所有旧表立即统一字段名，但要求 story system 统一抽取。

### 12.2 建议映射

```python
ANTI_PATTERN_SOURCE_FIELDS = {
    "题材与调性推理": ["强制禁忌/毒点"],
    "人设与关系": ["忌讳写法"],
    "爽点与节奏": ["常见崩盘误区"],
    "场景写法": ["反面写法"],
    "写作技法": ["常见误区"],
    "桥段套路": ["忌讳写法"],
}
```

说明：

- 若 phase 1 按 `retrofit spec` 为 `桥段套路.csv` 新增了 `忌讳写法` 列，phase 2 必须继续读取该列，避免两份 spec 再次分叉
- `桥段套路.反套路变种` 是变体灵感来源，不默认纳入 anti-pattern 聚合
- `金手指与设定.数值控制边界` 属于 `system_constraints`，不应直接等同于 anti-pattern
- 只有显式负面字段，才进入 `ANTI_PATTERN_SOURCE_FIELDS`

### 12.3 输出要求

所有生成合同中，必须存在醒目的：

- `## Anti-Patterns`

该区块是不可逾越的硬红线。

---

## 13. 运行时工作流

### 13.1 开书阶段

输入：

- `写个赛博朋克黑客流`

流程：

1. reasoning engine 锁定主辅题材
2. 多域聚合基础表
3. 生成 `MASTER_SETTING`
4. 写入 `.story-system/`
5. 初始化设定集

### 13.2 规划阶段

输入：

- `规划第一卷拍卖会逆袭`

流程：

1. 读取 `MASTER`
2. 聚合桥段、节奏、场景、人设补充
3. 生成 `VOLUME_BRIEF`
4. 再拆 `CHAPTER_BRIEF`

### 13.3 写作阶段

输入：

- `写第 15 章`

流程：

1. 读取 `chapter_015`
2. 若不存在则回退 `volume`
3. 再回退 `master`
4. 读取该层级最终结算后的有效字段
5. 只注入本章直接相关的 override 摘要，而不是完整历史账本
6. 结合 state / memory / recent context 起草正文

### 13.4 审查阶段

输入：

- `审查第 15 章`

流程：

1. 读取 `review contract`
2. 读取 `anti_patterns`
3. 结合 review schema 输出结构化问题

---

## 14. 测试与验证策略

### 14.1 总原则

这个 CSV 数据库不需要做“每条知识点一个测试”的重型方案。

测试只需要覆盖：

1. 合同生成是否成功
2. 覆盖规则是否正确
3. 关键字段是否落地
4. anti-pattern 是否被聚合
5. runtime 是否能读取合同

### 14.2 不建议的测试

不建议：

1. 为每个 CSV 条目写测试
2. 为每个知识点写断言
3. 为内容语义质量写机械化单测

### 14.3 应保留的验证

建议保留：

1. reasoning 命中 smoke test
2. contract schema test
3. persistence 覆盖规则 test
4. CLI 生成最小链路 test

建议额外补两类低成本高价值验证：

5. 多标签推理融合 test
6. override ledger 生成 test
7. JSON -> Markdown 渲染一致性 test
8. `locked + lock_policy` 行为 test

验证重点不是“知识点对不对”，而是：

- 合同结构稳不稳定
- 多标签毒点是否并集
- 覆盖是否有显式记录
- JSON 是否通过 schema 校验

---

## 15. 实施约束

### 15.1 知识迁移约束

知识迁移必须人工完成。

禁止：

- 自动抽取 md 为 csv
- 自动翻译后批量入库
- 自动拆句生成知识条目

允许：

- 人工阅读旧资料
- 人工提炼摘要、关键词、同义词
- 人工翻译英文 prompt 后录入

### 15.2 工程实现约束

工程层可以写脚本、CLI、渲染器、聚合器、持久化模块。

禁止脚本迁移，不等于禁止工程脚本开发。

---

## 16. 最终架构决策

本 spec 给出的理想态决策如下：

1. `references/csv` 升级为主知识仓
2. `references/*.md` 保留为方法论层
3. `templates/genres` 降级为样例模板层
4. `templates/output` 升级为合同模板层
5. `reference_search.py` 退出一线，降级为底层 primitive
6. `genre-profiles.md` 退出核心配置中心，职责转入结构化 reasoning 数据
7. `skills/webnovel-*` 改为“contract 优先 + 局部 step-bound reference 按需加载”
8. `state / index / memory` 继续保留，作为运行时事实与证据层
9. `story_system` 对外只通过统一 CLI `webnovel.py story-system ...` 暴露稳定入口
10. `.story-system` 必须接入 preflight / dashboard / health / backup，不能成为运维盲区
11. `.story-system/*.json` 是唯一真理源，`*.md` 只是只读渲染产物
12. reasoning engine 采用 `L0 / L1 / L2`，由确定性路由保底、LLM 负责低置信语义融合
13. `locked` 字段必须带 `lock_policy`，剧情级核心设定的变更只能走 `amend proposal + 用户确认`

---

## 17. 结语

这次重构真正要完成的，不是“把参考资料查得更准一点”。

真正的目标是：

- 不再让模型每一章都从散资料临时拼世界
- 而是先建立一个稳定的故事系统
- 再让规划、写作、审查都机械地服从这个系统

这就是 `webnovel-writer` 从“离散检索工具”升级为“系统级智能写作底座”的关键跃迁。
