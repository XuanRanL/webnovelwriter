# Webnovel-Writer Harness v6 设计文档

> 日期：2026-04-02（更新：2026-04-09）
> 状态：草案 v7（v6 + 实现对齐修正，Phase 1/2A/3/4 已完成）
> 基于：用户反馈 + issue#5 token 分析 + 23 条问题清单

---

## 1. 终极目标

写出一本长篇网络小说（500-2000 章），支持多种主流题材。要求：
- 文笔优秀，减少 AI 味
- 剧情跌宕起伏，出人意料（AI 主导创意，作者事后审核）
- 长上下文后保持文风且不吃书
- 完善的人机协作，可注入作者灵感
- 系统稳定，减少上下文消耗
- 合适的错误改善机制

## 2. 核心原则

- **Claude Code 本身就是 harness**——不另建编排层，充分利用原生能力（/resume、Task、子 agent 隔离、自动 compaction）
- **卷纲是 harness**——给写作 AI 足够约束，防止跑偏、失控、遗忘
- **记忆是根基**——防吃书靠记忆系统，不靠大纲节点
- **减法优先**——砍掉不产生价值的环节，而非叠加更多流程

### 2.1 本轮非目标（Out of Scope for v6 Migration Baseline）

以下事项方向已确认但**不在 v6 迁移基线内**，避免 scope creep：

- **Plan schema 全量落地**——章纲字段草案仅作为参考，plan skill 重构排在 Phase 6
- **References 全量范例化**——P0 方法论先补，P1 允许后续迭代
- **Memory 底层存储重构**——Phase 5，先冻结 v0 契约即可
- **Init 迭代打磨机制**——待 init 方案细化，不阻塞主链
- **Anti-AI 超越黑名单的新机制**——Phase 7，当前先用 reviewer ai_flavor 维度兜底

本轮优先：**主流程收敛（废弃 → 合并 → 接口冻结）+ 迁移退出标准达成**。

---

## 3. 问题清单（23 条）

### 3.1 Init

| # | 问题 | 根因 |
|---|------|------|
| 1 | 参考文件重结构轻范例 | 教了"格式"没教"品味"，LLM 知道填什么字段但不知道什么内容算好 |
| 2 | 缺少题材标杆 | 没有"好世界书长什么样"的真实小说范例作为 few-shot |
| 3 | 生成不可迭代 | 总纲、设定集一次生成就结束，无打磨循环 |

### 3.2 Plan

| # | 问题 | 根因 |
|---|------|------|
| 4 | 约束了"发生什么"而非"方向和边界" | 章纲写"主角救了叫朵朵的小女孩"→全量灌入写作 AI→剧透 |
| 5 | 缺少卷级叙事功能定义 | 每章在卷中承担什么角色（起/承/转/合）不明确 |
| 6 | 时间约束太显性 | 时间锚点、倒计时直接写在章纲里，AI 反复在正文中提及 |
| 7 | Strand 比例硬编码 60/20/20 | 不同题材节奏不同，末世文和甜宠文不可能一样 |
| 8 | 四层产出下游利用率不明 | 节拍表、时间线、卷纲、章纲——write 阶段真正消费的只有章纲 |
| 9 | 10 章/批生成质量递减 | 后面几章趋向套路化 |

### 3.3 Write

| # | 问题 | 根因 |
|---|------|------|
| 10 | 流水线太重 | 8 步 + workflow 记录，大量 token 花在流程管理而非写作 |
| 11 | context-agent 是 token 黑洞 | 全量灌入所有数据，输出巨大执行包 |
| 12 | 审查消耗大产出低 | 6 个 checker 各自独立 context，打 90 分但用户觉得很差 |
| 13 | anti-AI 必须加强 | 黑名单只能挡已知口癖，挡不了叙事结构/情绪表达/节奏层面的 AI 味 |
| 14 | data-agent 太重 | 9 个子步骤，归入记忆模块统一设计 |
| 15 | 写作和回写耦合 | 回写失败卡住整条链，但回写时机不变（下一章前必须完成） |
| 16 | workflow_manager + resume skill 浪费 | Claude Code 原生 /resume 即可恢复中断会话 |

### 3.4 记忆

| # | 问题 | 根因 |
|---|------|------|
| 17 | 6 种存储太分散 | state.json / index.db / scratchpad / summaries / vectors / snapshots 各自读写 |
| 18 | 分层不符合写作直觉 | 应按时效分级：近期（详细）→ 中期（摘要）→ 远期（活跃事实） |
| 19 | 时间线不是索引轴 | 所有记忆应挂在时间线上，支持"第 N 章时角色是什么状态"的查询 |
| 20 | 记忆类型需明确 | 角色状态（可变）、世界规则（稳定）、伏笔（有生命周期）、时间线（单调递增） |

### 3.5 系统级

| # | 问题 | 根因 |
|---|------|------|
| 21 | Skill/Agent prompt 格式混乱 | 缺少统一模板，每个文件组织方式不同，LLM 抓不住重点 |
| 22 | 参考资料需要清理和补充 | 删冗余、补方法论（含真实小说片段作为正面/反面范例） |
| 23 | Token 消耗过高 | 单章 300-500 万，审查占大头但产出最低 |

---

## 4. 已确认的设计方向

### 4.1 废弃项

| 废弃 | 替代 |
|------|------|
| workflow_manager.py | Claude Code 原生 /resume |
| resume skill | Claude Code 原生 /resume |
| Step 2B（独立风格适配步骤） | 合并到 Step 4 润色 |
| 6 个独立 checker agent | 合并为 1 个审查 agent |
| 审查评分机制 | 改为 code review 格式输出具体问题清单 |
| memory_scratchpad.json（长记忆系统） | 基于远端无长记忆版本重新设计统一记忆模块 |

### 4.2 Write 流程（新）

```
Step 0.5 预检
  → Step 1 上下文搜集（context-agent，research 模式）
  → Step 2 起草
  → Step 3 审查（单 agent，code review 格式）
  → Step 4 润色 + 风格适配 + anti-AI
  → Step 5 数据回写（统一记忆模块，单次调用）
  → Step 6 Git 备份
```

**章节状态模型（单调递进，不可回退）：**

| 状态 | 进入条件 | 允许结束会话 | 允许开始下一章 | 允许 git backup |
|------|----------|:---:|:---:|:---:|
| `chapter_drafted` | Step 2 完成，正文初稿存在 | ✅ | ❌ | ❌ |
| `chapter_reviewed` | Step 3-4 完成，blocking 清零且 anti-AI 复检通过 | ✅ | ❌ | ❌ |
| `chapter_committed` | Step 5 完成，记忆回写成功 | ✅ | ✅ | ✅ |

状态推进规则：
- 由 Step 2/4/5 完成时分别推进，写入 `state.json.progress.chapter_status[NNNN]`
- Step 5 失败不回滚 Step 1-4，章节停留在 `chapter_reviewed`，不得开始下一章
- 允许带着回写 debt 结束会话，但下次会话必须先补完 Step 5
- 查询入口：`python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" state get-chapter-status --chapter {N}`

### 4.3 Context-Agent（新模式）

从"一次性全量灌入 → 输出巨大执行包"改为 research 模式：

1. 调用记忆模块合并接口 → 拿到基础上下文（章纲目标、角色状态、未闭合伏笔）
2. 思考：这章还需要什么额外信息？
3. 按需调用记忆模块独立接口补充（某角色历史、某条世界规则、上章结尾）
4. 确认信息充分 → 按固定格式输出写作提示

### 4.4 审查（新模式）

- 默认 1 个 agent，一次灌入正文 + 记忆中的角色状态/世界规则
- 输出格式为结构化问题清单（code review 风格）
- **保留拆分口**：若实测发现 ai_flavor 检出率显著下降或单次上下文过载，允许追加一次轻量二次专项检查（如仅 ai_flavor 维度），但不回到 6 agent 模式：

**最小 schema：**

```json
{
  "issues": [
    {
      "severity": "critical | high | medium | low",
      "category": "continuity | setting | character | timeline | ai_flavor | logic | pacing | other",
      "location": "第3段",
      "description": "主角使用了第15章已失去的能力'xxx'",
      "evidence": "原文：'萧炎催动xxx斗技' vs 记忆：第15章已失去该能力",
      "fix_hint": "改为使用当前已有的yyy能力",
      "blocking": true
    }
  ],
  "blocking_count": 1,
  "summary": "发现1个阻断问题，2个高优问题"
}
```

**阻断规则：**
- `blocking=true` 的问题替代原 `timeline_gate` 语义——存在任何 blocking issue 时，不得进入 Step 4
- `severity=critical` 默认 `blocking=true`；其余 severity 由审查 agent 判断

**blocking 修复循环：**
- 存在 blocking issue 时，由主流程（非 reviewer）修复对应问题
- 修复后必须重跑 Step 3（完整审查），确认 blocking 清零
- 若用户明确覆盖（如判断为误报），可跳过重审直接进入 Step 4，需在 review report 中标注覆盖原因

**指标沉淀（轻量）：**
- 每次审查结果写入 `index.db.review_metrics`，字段：`chapter, issues_count, blocking_count, categories, severity_counts, timestamp`
- 用于趋势观测（连续 N 章某类问题反复出现 → 提示系统性问题）
- `overall_score` 保留为**衍生兼容字段**（由 severity_weighted 扣分计算），仅用于排序/趋势，**不可用于 gate 决策**
- gate 决策始终以 `blocking=true` 和 issue 明细为准
- 落库 schema 以 `review-schema.md` 冻结版为准；逻辑观测以轻量字段（issues_count/blocking_count/categories）为主，物理落库可保留兼容字段（overall_score/dimension_scores），待 dashboard/consumer 完成迁移后再评估裁撤

**anti-AI 职责划分：**
- **Step 3 负责发现** anti-AI 问题（category="ai_flavor"），列入问题清单
- **Step 4 负责修复**——消费 Step 3 的 ai_flavor issue 逐条修改
- **Step 4 修复后，必须独立复检**——默认路径：重跑 `reviewer`，仅启用 `ai_flavor` 维度。Step 4 不得自判 pass/fail
- 替代检查方案必须同时满足以下全部条件才视为等价：
  1. 独立于 Step 4 执行（不可由润色流程自判）
  2. 结构化 JSON 输出（含 `blocking_count`）
  3. 结果可落盘、可追溯（写入 `.webnovel/tmp/`）
- 理由：避免"自己改、自己说通过"的闭环偏差

### 4.5 记忆模块（分两阶段交付）

**阶段 A：接口契约（先定，不依赖存储实现）**

上层消费者（context-agent、data-agent、审查 agent）只依赖以下契约：

**v0（已实现，当前冻结）：**

> v0 接口已通过 `memory_contract.py`（Protocol + 类型定义）和 `memory_contract_adapter.py`（适配器）实现，CLI 入口为 `webnovel.py memory-contract` 子命令。context-agent 已在使用。

```python
# 合并接口
memory.commit_chapter(chapter: int, result: dict) -> CommitResult
memory.load_context(chapter: int, budget_tokens: int) -> ContextPack

# 独立接口（context-agent research 模式按需调用）
memory.query_entity(entity_id: str) -> EntitySnapshot
memory.query_rules(domain: str) -> list[Rule]
memory.read_summary(chapter: int) -> str
memory.get_open_loops(status: str = "active") -> list[OpenLoop]
memory.get_timeline(from_ch: int, to_ch: int) -> list[TimelineEvent]
```

**v1（Phase 3 增强目标，v0 冻结后再迭代）：**

- `commit_chapter` 的 `result: dict` → 替换为类型化 `CommitPayload`（明确字段：chapter_file、review_result、entities、summary 等）
- `load_context` 增加 `intent: Literal["draft", "review", "repair"]` 参数，按意图裁剪返回内容
- `query_rules` 的 `domain: str` → 细化为 `domain: str, scope: str = "all"` 支持子域过滤
- 所有返回结构统一包含横切元数据：`source`、`chapter_range`、`confidence`

v0 → v1 的升级不影响上层 prompt，仅影响 CLI 参数和返回字段丰富度。

**阶段 B：存储实现（后做）**

已确认方向：
- 按时效分层：近期（详细）→ 中期（摘要）→ 远期（活跃事实）
- 时间线作为索引轴
- 记忆类型：角色状态（可变）、世界规则（稳定）、伏笔（有生命周期）
- 具体实现方案搁置，待进一步思考

### 4.6 Plan（章纲约束重构方向）

章纲作为 harness 给 write 足够约束，但约束形式需要变：
- **约束"方向和边界"**，不约束"具体发生什么"
- **时间约束隐性化**——不在章纲里写死时间锚点，通过记忆系统间接传递，写后校验
- **Strand 比例按题材预设**，不硬编码 60/20/20
- **卷级叙事功能**——每章需要标注在卷中的叙事角色（起/承/转/合）
- 具体章纲字段设计待定

**章纲最小字段草案（待验证）：**

内容层（章纲本体）：
```json
{
  "chapter_goal": "主角通过考验进入迦南学院",
  "must_payoff": ["第3章埋下的丹药伏笔"],
  "forbidden_turns": ["主角不可直接暴露隐藏身份"],
  "narrative_role_in_arc": "承",
  "strand_profile": "main_heavy",
  "time_pressure_source": "入学截止"
}
```

消费策略层（控制章纲如何喂给写作 AI，不属于故事内容）：
```json
{
  "writer_exposure_policy": {
    "verbatim_fields": ["chapter_goal", "must_payoff", "forbidden_turns"],
    "transform_fields": {
      "narrative_role_in_arc": "转为隐性节奏提示，不直接告知'承'",
      "time_pressure_source": "仅作为校验依据，不在正文中直接提及具体数字或倒计时"
    }
  }
}
```

说明：
- `chapter_goal`：方向而非剧透，不写"主角救了叫朵朵的小女孩"
- `forbidden_turns`：明确边界，防止跑偏
- `strand_profile`：取代硬编码数值配比，由 genre-profiles 定义具体权重（如 `main_heavy` = 主线 70%+、`balanced` = 均衡、`relationship_heavy` = 感情线主导）
- `writer_exposure_policy`：独立于内容层，由 context-agent 消费时解释，章纲 schema 本身不混入传输逻辑

### 4.7 Skill/Agent Prompt 统一模板

每个 skill/agent 文件按固定结构编写：

```
1. 身份与目标
2. 可用工具与脚本（含调用方式）
3. 思维链（ReAct / 其他）
4. 输入
5. 执行流程（每步：输入 → 动作 → 输出）
6. 边界与禁区
7. 检查清单
8. 输出格式
9. 错误处理
```

### 4.8 参考资料

**删除**：冗余引用、已废弃文档、重复的 shared 引用（共 13 个文件）

**补充**（P0，16 条）：
- 反派设计、镜像反派、对手梯度、人物关系动力学
- 时间线设计、长篇升级节奏、反派压迫递进、伏笔埋设与回收
- 感情线递进、身份隐藏与曝光
- 暧昧/打脸/反转/对峙场景写法
- 章节开头钩子、章节结尾 cliffhanger

**要求**：参考资料按优先级分层补充真实小说片段：
- **P0（关键方法论）**：必须包含真实小说片段作为正面/反面范例——追读力钩子、反转写法、对峙场景等直接影响写作质量的方法论
- **P1（次级方法论）**：允许先用自写范例或抽象示例，后续逐步替换为真实片段

**改造**：现有 genres/ 和 write/references/ 下的文件从"结构模板"改为"方法论 + 范例 + 反面教材"

---

## 5. 未解决的设计问题

| # | 问题 | 状态 |
|---|------|------|
| 1 | 记忆模块具体实现（分层、存储、接口） | 搁置，待进一步思考 |
| 2 | 章纲具体字段设计（什么算"方向和边界"） | 已有最小草案（见 4.6），待实际 plan 验证后定稿 |
| 3 | anti-AI 的具体机制（超越黑名单的方案） | 待写作 prompt 设计时解决 |
| 4 | context-agent 输出的写作提示具体格式 | 待 write 方案细化 |
| 5 | 参考资料的真实小说片段收集 | 待用户收集 |
| 6 | Init 的迭代打磨机制 | 待 init 方案细化 |
| 7 | 节拍表/时间线是否保留 | 待确认下游是否消费 |
| 8 | 批量生成章纲的最佳批次大小 | 待实验 |
| 9 | Memory 契约 v0→v1 增强 | Phase 3 细化：CommitPayload 类型化、load_context 增加 intent、返回结构加横切元数据（详见 4.5 v1 目标） |

---

## 6. Token 优化预估

> 以下为方向性估算，具体取决于正文长度、审查轮次、research 命中率。需用真实运行日志验证。

| 环节 | 当前 | 优化后（预估区间） | 节省 |
|------|------|--------|------|
| 审查 | ~200 万（6 agent × ~33 万） | 30-50 万（1 agent，含 Step 4 后 ai_flavor 复检） | ~75-85% |
| Context-agent | ~50 万（全量灌入） | 10-20 万（按需检索） | ~60-80% |
| 风格适配 | ~30 万（独立 Step 2B） | 0（合并到润色） | 100% |
| Workflow 记录 | ~5 万（16 次 CLI） | 0（废弃） | 100% |
| **单章总计** | 300-500 万 | **预估 80-150 万** | ~60-70% |

假设条件：
- 单章正文 2000-2500 字
- 审查无 blocking 需返工的情况
- context-agent research 模式命中率 > 80%

---

## 7. 实施路径（建议）

| 阶段 | 内容 | 依赖 | 状态 |
|------|------|------|------|
| Phase 1 | 废弃 workflow/resume + 审查合并 + Step 2B 合并 | 无 | **✅ 已完成** |
| Phase 2A | Skill/Agent prompt 统一模板 + 参考资料清理（删冗余） | 无 | **✅ 已完成** |
| Phase 2B | 参考资料范例补强（真实小说片段） | 用户收集素材 | 待定 |
| Phase 3 | 记忆模块接口契约设计 | 无 | **✅ 已完成** |
| Phase 4 | Context-agent research 模式重构 | Phase 3（契约） | **✅ 已完成** |
| Phase 5 | 记忆模块存储实现 | Phase 3（契约）+ 用户设计确认 | 待定 |
| Phase 6 | Plan 章纲约束重构 | Phase 4+5 | 待定 |
| Phase 7 | anti-AI 加强 + 写作 prompt 优化 | Phase 2A+4 | 待定 |

注：Phase 1/2A/3 可并行探索，但合并前需一次**接口冻结**，优先冻结以下两项：
- `review-schema`（reviewer 输出格式 + metrics 落库字段）
- `memory-contract CLI`（记忆模块接口签名 + 返回类型）

冻结后 Phase 1/2A 的 prompt 改动才有稳定的接口可依赖。

---

## 8. 迁移退出标准（Migration Exit Criteria）

以下条件全部满足时，视为 v6 迁移完成：

1. **仓库内不再存在对 6 个 checker 的运行时引用**——skill/agent prompt 中无 `continuity-checker`、`setting-checker` 等旧名
2. **webnovel-write / webnovel-review 均只走 reviewer 流**——审查路径唯一
3. **`workflow_manager` 相关代码完全移除**——不残留 import、调用或配置
4. **legacy 术语分层清零**：
   - 运行时引用（skill/agent/script 中）：**0 处**
   - prompt/skill 生效路径引用：**0 处**
   - 测试 fixture / 迁移兼容样本：允许存在，但必须集中在 `evals/` 或 `tests/` 目录
   - 历史文档（docs/）：允许存在，但必须标注 `[deprecated]`
5. **至少 1 个真实项目完成连续 10 章验证**，验收维度：
   - 无流程阻断异常（全链路 plan → write → review → data 跑通）
   - 无状态回写错乱（chapter_status 单调递进，state.json / index.db 一致）
   - 无 review / write / data 契约不一致（reviewer 输出可被 review-pipeline 正确解析，data-agent 产物符合 memory v0 契约）
6. **章节状态模型已落地到 state.json**——`chapter_drafted` / `chapter_reviewed` / `chapter_committed` 可通过 CLI 查询，状态推进由 Step 2/4/5 原子写入
