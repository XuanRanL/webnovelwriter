# Webnovel Writer Skills 重构与 Reference 缺口设计

> 日期：2026-04-09
> 状态：草案 v4.3（v4.2 + Codex 二轮 review 3 处修正）
> 目标：在 Claude 已具备通用智能与通用写作能力的前提下，重构 `skills/` 体系，并为后续 `references/` 补全提供缺口清单。

---

## 1. 为什么要写一份新的 spec

### 1.1 与 v6 spec 的关系

本 spec 是 `2026-04-02-harness-v6-design.md`（v7）的**补充**，不是替代。

- **v6 spec** 解决主流程架构：废弃/合并、状态机、memory contract、审查流程、迁移退出标准。Phase 1/2A/3/4 已完成。
- **本 spec** 解决 v6 完成后的文档体系收敛：skills 怎么瘦身、references 怎么设计和补缺。
- **关于 reference 的设计原则**（渐进式披露、三层内容、按需加载、双轨知识库等），以本 spec 为准。

v6 spec 中的以下设计决策本 spec 继承不变：
- Write 流程 Step 0.5-6 及状态机
- reviewer 单 agent + blocking 修复循环
- memory contract v0/v1 接口
- 章纲字段草案与 `writer_exposure_policy` 分层

### 1.2 当前问题

旧的 harness v6 spec 主要解决的是迁移问题（现已大部分完成）。当前真正的问题，已经从“主流程能力缺失”转为“文档体系不够收敛”：

1. `skills/` 的结构风格混杂，有的像主链 SOP，有的像命令手册，有的像小型 spec。
2. `references/` 的职责不稳定：有的在重复 Claude 本来就知道的常识，有的又缺少针对模型缺陷的关键约束。
3. `skills`、`references`、`scripts` 的边界不够清楚，导致信息重复、维护成本高、补充方向模糊。
4. 对中文网文场景下的模型缺陷补偿不足，例如人物命名复用、套路化桥段复用、题材语汇漂移、对话口吻趋同等。

因此需要一份新的 spec，不再延续“迁移”叙事，而是回答一个更直接的问题：

**在 Claude 已经足够聪明的前提下，这个系统还需要哪些最小必要 skills，以及哪些 references 缺口值得补？**

---

## 2. 核心设计哲学

### 2.1 Claude 足够聪明

默认前提：Claude 已具备以下能力，不需要在技能文档里重复教学：
- 通用写作能力
- 通用总结、提炼、润色能力
- 常见叙事技巧与常见角色塑造常识
- 常规软件工程与文件读写能力
- 一般性的“如何提问用户”“如何组织步骤”“如何做检查”的能力

因此，`skills` 和 `references` 不应该承载这些通用常识。

### 2.2 文档只补“Claude 不稳定、不知道、易做错”的部分

应保留在文档里的内容，必须至少满足以下一种：
- **项目私有知识**：本仓库特有的状态字段、CLI、文件路径、契约、产物位置。
- **模型缺陷补偿**：Claude 高频犯错点，且不能稳定靠通识解决。
- **题材/平台特异约束**：中文网文场景下的特殊要求、风格偏好、禁区。
- **流程闸门**：必须显式满足的步骤顺序、验证条件、失败恢复。
- **高价值参考**：真实范例、反例、命名规则、反模板约束等。

不满足上述条件的信息，原则上不应出现在 `skills` 或 `references` 中。

### 2.3 Reference 设计四原则

以下四条原则是 reference 体系设计的核心约束，所有 reference 新增、保留、删除决策都必须以此为准。

#### 原则 1：渐进式披露

Reference 不是按“知识主题”组织，而是按“哪个 skill 的哪个 step 在执行时需要什么指导”组织。

- 每个 reference **应尽量**能映射到至少一个具体的 skill + step。
- 若为跨 skill 通用缺陷补偿，应明确**主服务场景**与**次服务场景**。
- Skill 的引用加载策略必须写清楚“Step N 遇到 X 条件时加载 Y reference”。

#### 原则 2：三层内容分级

同一个 reference 文件内，内容按三个层级组织：

| 层级 | 性质 | 说明 | 示例 |
|------|------|------|------|
| **提醒层** | Claude 知道，但长文写作时容易忘或不稳定执行 | 轻量条目，起“别忘了”的作用 | “对话不要全员书面语”、“不要每段都以总结句收尾” |
| **缺陷补偿层** | Claude 的系统性弱点，靠通识解决不了 | 需要明确的禁止项、替代方案、判断标准 | 命名同质化防护、“缓缓/淡淡/微微”固定语式替换、四段闭环结构检测 |
| **知识补充层** | Claude 知道但不够深/不够全，需要领域知识注入 | 提供中文网文特有的技法、模式、正反例 | 追读力钩子技法、特定题材节奏模式、真实小说片段 |

文件内三层从上到下排列，加载时可根据 token 预算裁剪深度。

#### 原则 3：按需条件加载

Reference 只在当前章节/任务确实触发了对应场景时才加载。

- 本章没有战斗 → 不加载战斗描写参考
- 本章没有新角色首次出场 → 不加载命名参考
- 本章不涉及时间跳跃 → 不加载时间过渡参考

Skill 的引用加载策略必须写明**触发条件**，而不是“每次都加载全部”。

#### 原则 4：粒度优先对齐稳定问题域

**md 文件**：优先按稳定问题域、稳定决策点组织，而不是机械切成极小碎片。只有当不同场景确实会产生冲突时，才进一步细拆。

**CSV 检索**：一次检索返回的结果集等于一个子任务的粒度（同一张 CSV 可包含多种子任务的条目，靠检索过滤）。

- 这个 step 需要命名 → 检索只返回命名相关条目
- 这个 step 需要战斗描写 → 检索只返回战斗相关条目
- 不扩展到“相关但当前不需要”的知识

### 2.4 references 不是越少越好，而是越“补缺”越好

本轮不追求压缩 references 数量。判断标准不是“文件是否减少”，而是：

**该 reference 是否真正补到了 Claude 的稳定性缺口或项目私有知识缺口。**

因此：
- 若现有 references 冗余，应删除或合并。
- 若现有 references 缺失，而该缺失会稳定导致错误，应新增。
- 新增 reference 的理由必须清楚说明“它补的是什么缺口”。

例如：
- 人物命名规则
- 题材专属命名禁区
- 中文网文对话口吻差异
- 特定题材常见模板腔与避坑清单

这些都属于合理新增。

### 2.5 skills 是工作流入口，不是百科

`SKILL.md` 负责：
- 定义适用场景
- 组织执行顺序
- 指定必要输入输出
- 指明何时读哪些 reference
- 定义验证与恢复规则

`SKILL.md` 不负责：
- 展开大量常识性方法论
- 承载完整范例库
- 细讲脚本内部实现
- 变成“小型全书教程”

### 2.6 中文化与网文化优先

本系统服务于中文网络小说写作，文档语言应优先使用中文网文领域词汇。原则如下：
- 正文叙述默认中文。
- 优先使用网文专用名词：章纲、卷纲、钩子、爽点、微兑现、追读力、吃书、毒点、设定冲突等。
- 字段名、CLI 子命令、frontmatter、JSON key、协议名保留必要英文。
- 同一概念尽量只保留一个主称呼。

#### 题材分类中文化

现有 `genres/` 目录使用英文名（`xuanhuan`、`realistic` 等），本轮需统一为中文题材名。**当前第一版默认以番茄小说网题材分类作为映射基准**，后续允许扩展平台映射层。

**男频：** 都市、玄幻、仙侠、奇幻、武侠、历史、军事、科幻、悬疑、游戏、体育、轻小说
**女频：** 现言、古言、幻言、悬疑、轻小说

CSV 知识库中的 `适用题材` 列使用上述中文名。`全部` 表示不限题材。

现有 `genres/` 目录的映射关系：

| 现有目录名 | 对应番茄题材 |
|-----------|------------|
| `xuanhuan/` | 玄幻 |
| `realistic/` | 都市 |
| `dog-blood-romance/` | 现言 |
| `rules-mystery/` | 悬疑 |
| `period-drama/` | 古言、历史 |
| `zhihu-short/` | 短篇 / 轻小说（临时映射） |

---

## 3. 文档分层职责

本轮只重构三层：
- `skills/`
- `references/`
- `scripts/`

### 3.1 skills 负责什么

`skills` 负责：
- 任务入口与适用场景
- 主流程步骤
- 前置条件
- 必要 references 的加载策略
- 交付物与成功标准
- 失败恢复与补跑规则

`skills` 不负责：
- 大段方法论教学
- 完整案例库
- 模型常识补课
- 重复解释底层脚本实现

### 3.2 references 负责什么

`references` 负责（遵循 §2.3 四原则）：
- 绑定到具体 skill + step 的子任务指导
- Claude 不稳定的高频缺陷补偿（缺陷补偿层）
- Claude 知道但容易遗忘的执行要点（提醒层）
- Claude 知道但不够深的领域知识补充（知识补充层）
- 项目私有规范（CLI、字段、路径等）
- 高价值正反例（真实小说片段）
- 题材特异规则与禁区清单

`references` 不负责：
- 通用写作常识（Claude 已知且稳定执行的部分）
- 大而空的方法论概述
- 不带判断标准的结构模板
- 不绑定到任何 step 的知识堆积

### 3.3 scripts 负责什么

`scripts` 负责：
- 容易出错、可执行、可验证的稳定操作
- 数据处理、验证、生成、迁移、索引等可程序化步骤

`scripts` 不负责：
- 替代 skill 的流程设计
- 承载主业务说明
- 替代 reference 的领域规则解释

### 3.4 脚本化触发条件

出现以下任一情况时，应优先评估是否脚本化，而不是继续扩写 skill 或 reference：

1. 同一操作会被多个 skill 重复调用
2. 成败可程序化判断
3. 人工描述过长且容易误解
4. 需要稳定过滤 / 检索 / 校验
5. 出错代价较高，且希望避免靠人工执行记忆

---

## 4. 本轮重写原则

### 4.1 不先写抽象模板文档，直接逐 skill 设计

本轮不先产出一份“统一 skill 模板”。原因：
- 不同 skill 的功能差异很大。
- 先写抽象模板容易过早收敛，反而束缚设计。
- 当前更适合直接对现有 skill 做问题导向重构。

但所有 skill 重写后都应满足以下共同要求：
- 适用场景清楚
- 前置条件清楚
- 流程主线清楚
- references 加载策略清楚
- 验证与恢复规则清楚
- 正文语言中文化、网文化

### 4.2 先 skill，后 reference 正文

本轮顺序固定为：
1. 先明确每个 skill 的职责与结构。
2. 再列出它缺哪些 reference 文件。
3. references 正文在下一阶段逐个补齐。

因此本 spec 中，references 只写：
- 文件名
- 作用
- 解决的缺陷类型
- 归属 skill

不展开全文内容设计。

### 4.3 reference 新增判断标准

新增 reference 必须同时满足：

1. **绑定检查**：能指出“哪个 skill 的哪个 step 在什么条件下加载它”；若为跨 skill 通用 reference，需写清主服务场景与次服务场景。
2. **缺口检查**：Claude 当前在这个子任务中是稳定犯错（缺陷补偿）、容易遗忘（提醒）、还是知识不足（补充）；至少命中一种。
3. **独立性检查**：这个指导是否无法靠 skill 主流程的一两句话自然覆盖；若能内联解决，不独立建文件。
4. **必要性检查**：如果不新增这份 reference，是否会稳定导致错误重复发生；若不会，优先通过 skill 流程、脚本或验证机制解决。

四条全过才新增。

### 4.4 Skill 正文必须包含的结构要素

除 §4.1 的共同要求外，按优先级分层：

- **P0 skills**：必须包含红旗 / 常见误区、优先级链、决策树入口三项
- **P1 skills**：至少显式包含其中 1-2 项
- **P2 skills**：按需采用，不强制

#### 红旗 / 常见误区区块

每个主链 skill 必须包含一个专门的“常见误区”列表，描述 Claude **真实会犯的思维错误**而非抽象禁令。

示例（`webnovel-write`）：

```text
## 常见误区
- ❌ 认为本章简单就跳过 Step 3 审查
- ❌ Step 5 失败后直接开始下一章（状态还在 chapter_reviewed）
- ❌ 把全部 reference 一次性读完再开始写
- ❌ blocking issue 存在但觉得“不严重”就跳过
- ❌ 用文件存在性替代 chapter_status 判断
- ❌ 润色时改了事件顺序或设定
```

#### 优先级链

当多个指令来源冲突时，skill 必须写明裁决顺序：

```text
1. 用户明确要求（最高）
2. 状态机 / 流程硬门槛（chapter_status、blocking）
3. 项目私有约束（设定集、已有剧情）
4. skill 默认工作流
5. reference 建议（最低）
```

#### 决策树入口

Skill 正文不只是线性步骤列表，还必须在流程开头或关键分支处提供决策判断。最少覆盖：
- 什么情况下继续下一步
- 什么情况下阻断
- 什么情况下回退到上一步
- 什么情况下需要用户裁决

---

## 5. 技能总览矩阵

| Skill | 当前主要问题 | 重写目标 | 需补 references | 优先级 |
|------|--------------|----------|-----------------|--------|
| `webnovel-write` | 主链过重，已有大量规则堆叠；需进一步明确主流程与引用边界 | 作为主链总控 skill，只保留主流程、闸门、交付物、恢复规则 | 高 | P0 |
| `webnovel-review` | 结构较简，但需与 reviewer / review-pipeline / 状态机更清晰衔接 | 成为独立审查流程入口，收敛报告与阻断处理 | 中 | P0 |
| `webnovel-plan` | 内容多、层级杂，兼有规则与参考说明 | 收敛为规划流程入口，结构化节点与卷级规划清楚 | 高 | P0 |
| `webnovel-init` | 过重，像 mini-spec；交互采集、规则、资料混在一起 | 收敛为初始化工作流 skill，复杂知识下沉到 reference | 高 | P1 |
| `webnovel-query` | 查询逻辑清楚，但文档像操作手册；可进一步减少低层命令暴露 | 收敛为查询 / 分析型 skill | 中 | P1 |
| `webnovel-dashboard` | 过轻，像启动命令说明；缺验证与失败恢复结构 | 收敛为工具启动型 skill | 低 | P2 |
| `webnovel-learn` | 过轻，像命令说明；缺边界与恢复规则 | 收敛为轻量记录型 skill | 低 | P2 |

---

## 6. 逐个 skill 改造方案

### 6.1 `webnovel-write`

#### 当前问题
- 承载了太多细节，容易继续膨胀。
- 某些 reference 内容仍偏“方法论说明”，未完全下沉。
- 已有状态机闸门，但结构仍偏大而全。

#### 重写目标
- 明确它是**主链总控 skill**。
- 保留：主流程、状态推进、阻断规则、必要 references、交付物、恢复规则。
- 明确不承载：命名细则、对话风格方法论、题材命名库、桥段范例库，这些必须下沉到 references。

#### 结构改动
建议正文只保留这些块：
1. 目标与适用场景
2. 常见误区（§4.4 红旗区块）
3. 优先级链（§4.4）
4. 前置条件与环境准备
5. 引用加载策略（Step 级，含 CSV 检索触发条件）
6. 主流程（Step 0.5-6，含决策树入口）
7. 状态推进与阻断规则
8. 充分性闸门
9. 验证与交付
10. 失败恢复

#### 当前 SKILL.md 段落去留表

| 当前段落 | 处置 | 理由 |
|---------|------|------|
| 目标 | 保留 | 核心定义 |
| 执行原则 | 保留 | 闸门硬约束 |
| 模式定义 | 保留 | 标准 / fast / minimal 区分 |
| 引用加载等级（L0/L1/L2） | 保留 | 按需加载策略 |
| References 列表 | 重写 | 改为按 Step 触发条件组织，加条件加载说明 |
| 工具策略 | 保留，精简 | 只保留 CLI 入口，不展开参数细节 |
| 准备阶段 | 保留 | preflight + 环境变量 |
| Step 0.5-6 | 保留 | 核心流程 |
| 问题定向参考列表 | 下沉 | 移到 reference index 或 Step 内触发条件 |
| 充分性闸门 | 保留 | 已切到状态机 |
| 验证与交付 | 保留 | 已用 chapter_status |
| 失败处理 | 保留 | 补跑规则 |

#### references 触发绑定

以 §2.3 四原则为标准，按 Step + 触发条件组织。**md 文件直接 Read，CSV 通过检索脚本按需获取。**

##### md 必读（直接 Read）

| Step | 触发条件 | 加载的 reference |
|------|---------|-----------------|
| Step 1 | 每次执行 | `references/reading-power-taxonomy.md`、`references/genre-profiles.md`、`skills/webnovel-write/references/style-variants.md` |
| Step 2 | 每次执行 | `references/shared/core-constraints.md`、`skills/webnovel-write/references/anti-ai-guide.md` |
| Step 4 | 每次执行 | `skills/webnovel-write/references/polish-guide.md`、`skills/webnovel-write/references/writing/typesetting.md`、`skills/webnovel-write/references/style-adapter.md` |

##### CSV 检索（调用 `reference_search.py`）

| Step | 触发条件 | 检索参数 |
|------|---------|---------|
| Step 2 | 本章有新角色首次出场 | `--skill write --table 命名规则 --query "角色命名" --genre {题材}` |
| Step 2 | 本章有战斗 / 对峙场景 | `--skill write --query "战斗描写" --genre {题材}` |
| Step 2 | 本章有多角色对话 | `--skill write --query "对话声线 口吻区分"` |
| Step 2 | 本章有情感 / 心理描写 | `--skill write --query "情感描写 心理"` |
| Step 2 | 本章涉及高频桥段 | `--skill write --table 场景写法 --query "{桥段类型}"` |
| Step 4 | ai_flavor issue 存在 | `--skill write --query "AI味 反例 替换"` |

#### scripts 需求
- 暂不新增脚本作为前置条件。
- 若后续发现命名校验可程序化，可新增轻量命名检查脚本。

#### 验收点
- 主流程阅读路径明显缩短
- 每一步只在触发条件满足时加载对应 references
- 状态机与交付物逻辑不弱化
- 不再在 skill 正文中展开大段常识性写作建议

---

### 6.2 `webnovel-review`

#### 当前问题
- 流程清楚，但与 `reviewer` / `review-pipeline` / 报告落盘的边界还可再清楚。
- 阻断与返工逻辑可进一步明确成“审查型 workflow”。

#### 重写目标
- 成为独立审查 skill：从输入章节到输出审查报告、落库、写回记录。
- 不承载过多审查理论；理论交给 reviewer 和 references。

#### 结构改动
保留：
1. 适用场景
2. 常见误区（§4.4）
3. 优先级链（§4.4）
4. 项目根解析
5. 引用加载
6. 调用 reviewer（含决策树：blocking → 返工 / override）
7. 生成报告与落库
8. 处理 blocking 与用户决策
9. 成功标准与恢复规则

#### references 触发绑定

##### md 必读

| Step | 触发条件 | 加载的 reference |
|------|---------|-----------------|
| Step 2（加载参考） | 每次执行 | `references/shared/core-constraints.md`、`references/review-schema.md` |
| Step 6（处理阻断） | 存在 blocking issue 需用户决策 | `references/review/blocking-override-guidelines.md` |

##### CSV 检索

| Step | 触发条件 | 检索参数 |
|------|---------|---------|
| Step 4（调用 reviewer） | ai_flavor issue 数量 ≥ 3 | `--skill review --query "AI味 反例 替换"` |

#### scripts 需求
- 不新增主流程脚本。
- 后续若独立复检需要稳定接口，可考虑加 `review-ai-flavor-check.py`。

#### 验收点
- 阻断处理路径清楚
- 审查产物路径稳定
- 不再重复 reviewer 本身的详细检查维度

---

### 6.3 `webnovel-plan`

#### 当前问题
- 文档同时承担：设定补齐、卷节拍、时间线、章纲、节点规范、写回设定。
- 很多规则适合作为 reference，而不是主 skill 正文。

#### 重写目标
- 成为**规划主流程入口**，重点强调：
  - 卷级目标
  - 时间线硬约束
  - 批量拆章流程
  - 结构化节点产物
- 将题材节奏、冲突设计等下沉到 reference。

#### 结构改动
建议主结构为：
1. 目标与适用范围
2. 常见误区（§4.4 红旗区块）
3. 优先级链（§4.4）
4. 前置条件
5. 引用加载策略
6. 规划主流程（Step 1-9，含决策树入口）
7. 结构化节点产物要求
8. 硬失败条件
9. 恢复规则

#### references 触发绑定

##### md 必读

| Step | 触发条件 | 加载的 reference |
|------|---------|-----------------|
| 章纲拆分 | 每次执行 | `references/outlining/plot-signal-vs-spoiler.md` |

##### CSV 检索

| Step | 触发条件 | 检索参数 |
|------|---------|---------|
| 卷级规划 | 每次执行 | `--skill plan --table 场景写法 --query "卷级结构 叙事功能"` |
| 章纲拆分 | 新增角色出现 | `--skill plan --table 命名规则 --query "角色命名" --genre {题材}` |

#### scripts 需求
- 暂不新增。
- 后续若时间线验证继续复杂化，可考虑补独立校验脚本。

#### 验收点
- 主流程更像“规划入口”，不是“全量教程”
- 题材与冲突知识显著下沉到 references
- 批次、节点、时间线规则清楚且集中

---

### 6.4 `webnovel-init`

#### 当前问题
- 体量过大，已接近 mini-spec。
- 用户采集、题材策略、创意约束、资料索引混在一起。

#### 重写目标
- 成为**初始化访谈与生成工作流**。
- 主 skill 只保留信息采集流程、充分性闸门、生成与验证。
- 题材、命名、卖点、创意约束等知识下沉到 references。

#### 结构改动
建议主结构为：
1. 目标与适用场景
2. 交互原则
3. 分步采集流程
4. 充分性闸门
5. 生成步骤
6. 验证与交付
7. 最小回滚

#### references 触发绑定

##### md 必读

| Step | 触发条件 | 加载的 reference |
|------|---------|-----------------|
| 卖点 / 题材采集 | 每次执行 | `references/genre-profiles.md` |

##### CSV 检索

| Step | 触发条件 | 检索参数 |
|------|---------|---------|
| 起名采集 | 用户开始设定角色 / 书名 / 势力名 | `--skill init --table 命名规则 --query "{命名对象} {题材}" --genre {题材}` |

注：原 `title-patterns-and-anti-patterns.md` 和 `protagonist-flaw-patterns.md` 不直接纳入本轮缺口清单，后续若实测出现稳定缺陷再补回。

#### scripts 需求
- 暂不新增，仍以现有 `init_project.py` 为主。

#### 验收点
- skill 正文显著瘦身
- 交互流程更清楚
- 创意 / 题材 / 命名类细节下沉

---

### 6.5 `webnovel-query`

#### 当前问题
- 查询流程本身合理，但文档风格偏操作手册。
- 暴露较多低层步骤，可进一步强调“查询类型识别 + 数据源选择 + 输出格式”。

#### 重写目标
- 成为**查询 / 分析型 skill**。
- 强调：
  - 查询意图识别
  - 按需加载 reference
  - 读取最少必要数据
  - 输出结构化回答

#### 结构改动
建议保留：
1. Use when
2. 项目根保护
3. 查询类型识别
4. 引用加载等级
5. 查询流程
6. 输出格式
7. 边界

#### references 触发绑定

无新增刚需。当前 query skill 的参考需求主要是项目私有知识（CLI 用法、数据源），已内联在 skill 中。

注：`entity-alias-resolution.md`、`foreshadowing-urgency-rules.md` 暂列为候选，待实测若输出不稳则补回。

#### scripts 需求
- 无新增刚需。

#### 验收点
- 更像查询工作流，而不是大段说明书
- 输出风格统一

---

### 6.6 `webnovel-dashboard`（P2，方向简述）

收敛为**工具启动型 skill**：补齐环境检查、启动步骤、成功判定、常见故障处理。P2 不强制三件套，不挂独立 reference，现有功能已基本自洽。

---

### 6.7 `webnovel-learn`（P2，方向简述）

收敛为**轻量记录型 skill**：重点明确何时记录、输入结构、幂等 / 去重、写回格式、失败处理。P2 不强制三件套，是否补 `pattern-taxonomy` 视实测而定。

---

## 7. Reference 体系设计（双轨制）

本轮 reference 采用**双轨制**：流程必读型（md）+ 写作知识库型（CSV + 检索脚本）。

### 7.1 双轨分工

| 轨道 | 格式 | 加载方式 | 承载内容 | 示例 |
|------|------|---------|---------|------|
| **流程必读型** | `.md` 文件 | Skill 指定 step 直接 `Read` | 闸门规则、schema 定义、核心约束、审查标准 | `core-constraints.md`、`review-schema.md`、`polish-guide.md` |
| **写作知识库型** | `.csv` + Python 检索脚本 | Step 遇到特定场景时调用脚本，只返回命中条目 | 写作技法、题材写法、场景灵感、命名规则、正反例 | `写作技法.csv`、`命名规则.csv`、`场景写法.csv` |

分界标准：
- **流程/契约/闸门/schema** → md（必须完整读取，不能只看片段）
- **写作知识/技法/灵感/正反例** → CSV（条目多、按需检索、只取相关的几条）

### 7.2 CSV 知识库设计

#### 文件位置

```
webnovel-writer/
  data/                          # CSV 知识库根目录
    写作技法.csv
    命名规则.csv
    场景写法.csv
  scripts/
    reference_search.py          # 统一检索脚本（BM25）
```

#### 编码

所有 CSV 文件使用 **UTF-8 with BOM**（`utf-8-sig`），确保 Windows 下 Excel 可正确打开中文。

#### 通用列（所有 CSV 共有）

| 列名 | 类型 | 说明 | 示例值 |
|------|------|------|-------|
| `编号` | string | 唯一 ID，前缀区分表 | `WT-001`、`NR-012`、`SP-003` |
| `适用技能` | string | 粗筛，逗号分隔 | `write` 或 `init,plan` 或 `init,plan,write` |
| `分类` | string | 场景大类 | `战斗`、`对话`、`命名`、`情感`、`场景` |
| `层级` | string | 三层标记 | `提醒` / `缺陷补偿` / `知识补充` |
| `关键词` | string | BM25 检索用，逗号分隔 | `打斗,武斗,对决,境界压制` |
| `适用题材` | string | 番茄分类题材名，逗号分隔 | `全部` 或 `玄幻,仙侠` |

#### 写作技法表（`写作技法.csv`）

| 列名 | 说明 |
|------|------|
| （通用列） | |
| `技法名称` | 技法的简短名称 |
| `说明` | 技法描述 |
| `正例` | 正面示范，可放长片段（200-500 字） |
| `反例` | 反面示范，可放长片段 |
| `修复建议` | 从反例到正例的修改方向 |

示例行：

```
编号,适用技能,分类,层级,关键词,适用题材,技法名称,说明,正例,反例,修复建议
WT-001,write,对话,缺陷补偿,"口吻趋同,对话区分,角色声线",全部,对话声线差异化,不同角色的对话应有可辨识的口语特征和节奏差异,"老张头叼着烟袋锅子，""嘿，你小子又来蹭饭？""...","两人对话风格完全一致，都是标准书面语",给每个角色设定 1-2 个口语标记词和句式习惯
```

#### 命名规则表（`命名规则.csv`）

| 列名 | 说明 |
|------|------|
| （通用列） | |
| `命名对象` | `角色` / `地点` / `势力` / `功法` / `道具` / `书名` |
| `规则` | 规则描述 |
| `正例` | |
| `反例` | |

#### 场景写法表（`场景写法.csv`）

| 列名 | 说明 |
|------|------|
| （通用列） | |
| `场景类型` | `告白`、`打脸`、`觉醒`、`战斗`、`谈判`、`追逐`、`日常`、`离别` 等 |
| `模式名称` | 这种写法的名称 |
| `说明` | 模式描述 |
| `示例片段` | 可放长片段（200-500 字） |
| `反面写法` | 要避免的写法 |

### 7.3 检索脚本设计

#### CLI 接口

```bash
# 基本用法：按当前 skill 和关键词检索
python -X utf8 "${SCRIPTS_DIR}/reference_search.py" \
  --skill write \
  --query "战斗描写 境界压制" \
  --max-results 3

# 指定题材过滤
python -X utf8 "${SCRIPTS_DIR}/reference_search.py" \
  --skill write \
  --query "命名 角色" \
  --genre "玄幻" \
  --max-results 5

# 指定表
python -X utf8 "${SCRIPTS_DIR}/reference_search.py" \
  --skill plan \
  --table 命名规则 \
  --query "跨卷 角色命名" \
  --max-results 3
```

#### 检索流程

```
1. 按 `适用技能` 列过滤（粗筛）
2. 按 `适用题材` 列过滤（可选，若指定 --genre）
3. 在过滤后的结果集内做 BM25 关键词检索
4. 返回 top N 条，格式化输出
```

#### 输出格式

```
## 检索结果（写作技法）
查询：战斗描写 境界压制 | 技能：write | 题材：玄幻 | 命中：3 条

### [WT-023] 境界压制的体感描写
- 层级：知识补充
- 说明：通过身体反应而非数值对比来表现境界差距
- 正例：（片段...）
- 反例：（片段...）
- 修复建议：...

### [WT-045] ...
```

### 7.4 流程必读型 reference（md 文件，保留/新增）

以下 md reference 保留或新增，由 Skill 在指定 step 直接 `Read`：

| 文件 | 类型 | 服务 skill | 加载时机 |
|------|------|-----------|---------|
| `references/shared/core-constraints.md` | 保留 | write/Step 2 | 每次执行 |
| `references/review-schema.md` | 保留 | write/Step 3、review/Step 4 | 每次执行 |
| `references/shared/cool-points-guide.md` | 保留 | review | 按需 |
| `references/shared/strand-weave-pattern.md` | 保留 | review | 按需 |
| `references/reading-power-taxonomy.md` | 保留 | write/Step 1 | 每次执行 |
| `references/genre-profiles.md` | 保留 | write/Step 1、init | 每次执行 |
| `skills/webnovel-write/references/style-variants.md` | 保留 | write/Step 1 | 每次执行（差异化设计） |
| `skills/webnovel-write/references/polish-guide.md` | 保留 | write/Step 4 | 每次执行 |
| `skills/webnovel-write/references/anti-ai-guide.md` | 保留 | write/Step 2 | 每次执行 |
| `skills/webnovel-write/references/style-adapter.md` | 保留 | write/Step 4 | 每次执行 |
| `skills/webnovel-write/references/writing/typesetting.md` | 保留 | write/Step 4 | 每次执行 |
| `references/review/blocking-override-guidelines.md` | **新增** | review/Step 6 | 存在 blocking issue 需用户决策时 |
| `references/outlining/plot-signal-vs-spoiler.md` | **新增** | plan/章纲拆分 | 每次执行 |

### 7.5 写作知识库型 reference（CSV 文件，新增）

以下知识从现有 md 文件迁移或新建到 CSV：

| 现有 md 文件 | 迁移到 CSV | 迁移后 md 处置 |
|-------------|-----------|--------------|
| `writing/combat-scenes.md` | `场景写法.csv`（场景类型=战斗） | 删除或保留为空壳指向 CSV |
| `writing/dialogue-writing.md` | `写作技法.csv`（分类=对话） | 同上 |
| `writing/emotion-psychology.md` | `写作技法.csv`（分类=情感） | 同上 |
| `writing/scene-description.md` | `写作技法.csv`（分类=场景） | 同上 |
| `writing/desire-description.md` | `写作技法.csv`（分类=情感） | 同上 |
| `writing/genre-hook-payoff-library.md` | `场景写法.csv`（场景类型=钩子/兑现） | 同上 |
| （新增）命名规则 | `命名规则.csv` | 无现有文件 |
| （新增）对话声线差异化 | `写作技法.csv`（分类=对话，层级=缺陷补偿） | 无现有文件 |
| （新增）反模板桥段 | `场景写法.csv`（层级=缺陷补偿） | 无现有文件 |
| （新增）AI味正反例 | `写作技法.csv`（分类=AI味，层级=缺陷补偿） | 无现有文件 |
| （新增）卷级叙事功能模式 | `场景写法.csv`（场景类型=卷级结构，适用技能=plan） | 无现有文件 |

### 7.6 被过滤掉的原提案

以下提案当前不纳入，但不是永久排除。判断标准：Claude 在中文网文场景下若实测输出稳定性不足，仍可后续补回。

| 原提案 | 当前过滤理由 | 恢复条件 |
|--------|------------|---------|
| `init/title-patterns-and-anti-patterns.md` | 书名命名可作为 `命名规则.csv` 中几行条目（`命名对象=书名`） | 若 CSV 几行不够覆盖、实测书名模板化严重，升级为独立条目组 |
| `init/protagonist-flaw-patterns.md` | Claude 通用能力可覆盖 | 若实测缺陷设计在网文场景下空泛化、标签化严重，补为 CSV 条目 |
| `query/entity-alias-resolution.md` | 别名解析是代码逻辑（entity_linker.py） | 若代码无法覆盖的语义歧义频发，补 reference |
| `query/foreshadowing-urgency-rules.md` | 紧急度排序已在 context-agent 实现 | 若输出解释不稳定，补 reference |
| `learn/pattern-taxonomy.md` | learn skill 低频，分类规则内联 skill 即可 | 若分类质量持续不稳，补 CSV 条目 |

---

## 8. 分批实施顺序

### 第零批：基础设施
- 实现 `reference_search.py`（BM25 检索脚本）
- 建立 `data/` 目录和 3 个 CSV 文件骨架（表头 + 少量种子数据）
- 补测试：确认检索脚本的粗筛 → 题材过滤 → BM25 流程跑通
- 现有 `genres/` 目录名中文化映射

目标：CSV 知识库基础设施就绪，后续批次可直接往里填数据。

### 第一批：主链 skills（P0）
- `webnovel-write`
- `webnovel-review`
- `webnovel-plan`
- 新增 P0 skill 依赖的 md reference：`blocking-override-guidelines.md`（review）、`plot-signal-vs-spoiler.md`（plan）

目标：先收敛主链工作流入口，skill 正文切到双轨 reference 加载。

**冻结点：** 第一批完成后，review 确认主链 skill 结构稳定、md/CSV 触发绑定表无遗漏，再进入第二批。

### 第二批：初始化与查询（P1）
- `webnovel-init`
- `webnovel-query`

目标：收敛前置采集和查询分析文档。

### 第三批：内容填充 + 辅助类（P2）
- `webnovel-dashboard`
- `webnovel-learn`
- 将现有 md reference 中的写作知识迁移到 CSV
- 逐步扩充 CSV 条目（可持续进行，不阻塞主链）

目标：完成轻量技能整理，CSV 知识库进入持续填充阶段。

---

## 9. 验收标准

本轮重构完成时，应满足：

1. 所有 `skills` 都有清晰的主功能定位，不再混合成”手册 + 教程 + spec”。
2. `skills` 正文明显收敛为：流程、闸门、交付物、恢复规则。
3. **skill 结构要素分层落地**：P0 skill 包含红旗/优先级链/决策树全三项，P1 至少 1-2 项，P2 按需（§4.4）。
4. **reference 双轨制落地**：流程必读型 md + 写作知识库型 CSV，职责不混。
5. `reference_search.py` 可正常检索，粗筛（适用技能）→ 题材过滤 → BM25 全链路跑通。
6. CSV 文件均为 UTF-8 with BOM 编码，Windows Excel 可正确打开。
7. 题材分类已中文化（当前以番茄小说网分类为默认基准），现有 `genres/` 目录完成映射。
8. 不再以”减少 reference 数量”为目标，而以”高价值补缺”为目标。
9. 技能正文语言完成中文化/网文化，字段和协议保留必要英文。
10. 新增或重写后的 skill 可通过 prompt integrity 检查与人工走读。

---

## 10. 本 spec 的边界

本 spec 不处理：
- `agents/` 重写（agent 只有 prompt 本体，不挂 reference 文件）
- references 正文具体内容撰写（仅定义文件名、触发绑定、内容层级）
- scripts 的完整实现细节
- v6 迁移 spec 中已确认的架构决策（状态机、memory contract、reviewer 流程等）

本 spec 只回答：
**skills 下一步应该怎么重写，以及 references 下一步该补哪些文件、在什么条件下加载。**
