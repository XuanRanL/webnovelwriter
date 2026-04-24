# Step 6 审计矩阵（A-G 七层）

> 本文件被 `audit-agent` 在执行 Step 6 时必读。定义完整的 70+ 检查项、每项的输入/方法/严重等级/修复命令。

## 严重等级定义

> 本节与本文件底部「决议矩阵」共同构成权威规范，二者必须一致。若出现偏差以「决议矩阵」为准。

- **critical**: 任一命中 → 立即 `block`。代表链路执行可疑或作品会崩。
- **high**: 3+ 命中 → `block`；1-2 命中 → `approve_with_warnings` 并强制写入 editor_notes。
- **medium**: 任一命中 → `approve_with_warnings`。
- **low**: 仅记录，不影响决议。

## Layer A — 过程真实性（critical 层，抓伪装执行）

Ch1 事故全在这一层。目的：验证 Step 1-5 的子代理真的跑了而不是 fallback。

| ID | 检查项 | 方法 | 通过标准 | 严重 | 修复 |
|---|---|---|---|---|---|
| A1 | Context Contract 完整性 | 读 `context_snapshots/ch{NNNN}.json`，验证 8 板块全在、Contract 12 字段全填 | 字段覆盖 ≥ 18/20 | critical | 重跑 Step 1 context-agent |
| A2 | 13 checker 独立性 | 读 `审查报告/第{NNNN}章审查报告.md`，提取 13 个 checker 段落（含 flow-checker + reader-naturalness + reader-critic · Round 13 v2），计算两两文本相似度（词袋 Jaccard） | 最高相似度 < 0.6；分数方差 ≥ 3 | critical | 重跑 Step 3（显式 Task 调用每个 checker） |
| A3 | 外部模型覆盖 | 读 `.webnovel/tmp/external_review_*_ch{NNNN}.json`，统计有效模型数（路由 verified + 无 phantom_zero + 维度完整） | **Round 16 · 扁平共识**：≥ 10/14 有效 pass · 8-9 medium warn · 5-7 high warn（仍不阻塞） · <5 critical fail | **high**（仅 <5/14 时才 critical） | 重跑 Step 3.5（`--model-key all`）· 若 provider outage 可接受 |
| A4 | Data Agent A-K 子步真实执行 | 读 `.webnovel/observability/data_agent_timing.jsonl` 最后一条，每子步 elapsed_ms > 0；B 步 > 3000ms；K 步有 applied_additions | A-F 均 > 100ms | critical | 重跑 Step 5 |
| A5 | 无 fallback subagent | 读 `.webnovel/observability/call_trace.jsonl` 本章区间，grep `"subagent_type": "general-purpose"` | 命中数 = 0 | critical | 确认插件 enable + 重跑对应 Step |
| A6 | workflow_state 时序合理 | 读 `.webnovel/workflow_state.json.history` 或 `completed_steps`，时间戳单调递增；Step 3 > 60s、Step 5 > 30s | 时序 OK 且耗时合理 | high | 重跑可疑步骤 |
| A7 | 正文字符卫生 | grep `\ufffd` / `��` / `\x00` 在正文文件 | 命中数 = 0 | critical | 从 Step 2A 重写 |
| A8 | anti_ai_force_check 非 stub | 读 Step 4 变更摘要，验证列出具体检查项清单而非只写"pass" | 至少 3 个检查项被列出 | high | 重跑 Step 4 终检 |

## Layer B — 跨产物一致性（防数据漂移）

所有产物之间必须同源。

| ID | 检查项 | 方法 | 通过标准 | 严重 | 修复 |
|---|---|---|---|---|---|
| B1 | 摘要 ↔ 正文 | 摘要 `## 关键节点` / `## 核心事件` 每条，grep 正文能命中 | 命中率 ≥ 90% | high | 补跑 Step 5 E |
| B2 | 新实体三处对账 | 摘要"新实体" ∩ state.entities ∩ 设定集 grep | 差集 = ∅ | high | 补跑 Step 5 K + 手工补设定集 |
| B3 | 伏笔三处对账 | 摘要伏笔 ∩ `state.plot_threads.foreshadowing` ∩ `设定集/伏笔追踪.md` | 三处一致 | critical | 补跑 Step 5 D + K |
| B4 | review_metrics 三处一致 | `state.chapter_meta[{NNNN}].review_metrics.combined_score` ↔ index.db latest ↔ 审查报告数值 | 三处相等 | high | 重跑 index save-review-metrics |
| B5 | 主角状态传播 | 若 `state.protagonist_state` 有变化，`主角卡.md` 应有 `[Ch{N}]` 追加段 | 变化时标签存在 | medium | 手动追加或重跑 Step 5 K |
| B6 | 反派存在信号传播 | 本章反派出场 → `设定集/反派设计.md` 的"当前状态"段应更新 | 出场时状态更新 | medium | 重跑 Step 5 K |
| B7 | 章纲 → 实际章节 | `大纲/第N卷-章纲.md` 的本章目标/阻力/代价/爽点/钩子，每项正文可对应 | 5/5 兑现 | high | Step 4 补写 |
| B8 | 时间锚点传播 | 章纲时间锚点 ↔ 正文时间描写 ↔ 设定集时间线表 | 三处一致 | high | 修正正文或设定集 |
| B9 | chapter_meta 22 字段完备 | `state.chapter_meta[{NNNN}]` 必填字段检查 | 全字段非空 | critical | 重跑 Step 5 D |

## Layer C — 读者体验（核心！Step 3 管不到这层）

这一层的判断依赖 agent 阅读理解。不能只看声明的 strength，要看实际效果。

| ID | 检查项 | 方法 | 通过标准 | 严重 | 修复 |
|---|---|---|---|---|---|
| C1 | 开头 500 字抓人度 | 读正文前 500 字，判定"冷启动读者会不会读下去" | 有动作/悬念/具象画面 ≥ 2 种 | critical | Step 4 重写开场 |
| C2 | 章末钩子实际强度 | 读末段 200 字，与章纲 `hook.strength=strong` 对照 | 声称 vs 实际一致 | critical | Step 4 追加危机信号 |
| C3 | 末段未闭合问题 | 读末段，找出"必须读下一章才能解决的具体问题" | ≥ 1 个 | critical | Step 4 补钩子 |
| C4 | 爽点兑现度 | 对每个规划爽点在正文定位，判定铺垫-兑现-余韵完整度 | 每爽点三段齐 | high | Step 4 补兑现 |
| C5 | 情绪曲线起伏 | 全章切 5 段，每段情绪强度打分，绘曲线 | 与 Contract emotion_rhythm 一致 | high | Step 4 调节奏 |
| C6 | 读者代入锚点 | 本章是否 ≥ 1 个具象细节让人心头一动 | ≥ 1 | high | Step 4 加锚点 |
| C7 | 上章钩子回应 | 读上章末段 200 字 + 本章前 800 字，判定是否回应 | 回应或合理延迟 | high | Step 4 补前情 |
| C8 | 新读者可读性 | 关键人物/术语是否有轻量复习 | 关键项 ≥ 80% 有复习 | medium | Step 4 加简短复习 |
| C9 | 信息负担 | 本章新名词/新设定数量 | ≤ 3 个硬核新概念 | medium | Step 4 简化或拆到下章 |
| C10 | 段落长度分布 | 最长段字数 / > 200 字段数 | 最长 ≤ 250；> 200 段数 ≤ 2 | high | Step 4 拆段 |
| C11 | 对话密度 | 连续无对话段数 / 对话占比 | 连续 ≤ 5 段；对话占比 20-60% | medium | Step 4 补对话/叙述 |
| C12 | 指代清晰度 | 同一人物称呼切换次数 / 代词距先行词 | 切换 ≤ 3 次 | medium | Step 4 统一称呼 |
| C13 | 跨层共识聚合 | 读 flow-checker（A 内部）+ reader_flow（C 外部）两层 issue，按 quote 归一化聚合；≥ 2 模型命中 = 共识 high/medium；单模型孤报 high 降级 medium | 共识 high = 0；共识 medium ≤ 2 | critical | Step 4 修共识 high；共识 medium 列优先 |
| C14 | 反应可追溯性 | 识别主角 3-5 类关键反应（主动动作/规则推断/情绪爆发/技能使用/内心顿悟），逆向 grep 前置线索（**双通道**：同章距离 ≤ 30 段 OR 跨章线索 + 本章呼应锚点） | 每个关键反应至少 1 条前置线索 | high | Step 4 补动机/线索/锚点 |
| C15 | Flow 趋势滑动窗口 | 本章 flow_score_median vs 近 5 章 flow_score_median 的 Δ（历史不足 3 章时 warn-only；≥ 3 章启用 block 规则） | Δ ≤ 10 不 block；Δ ≤ 5 不 warn | critical（Δ > 10）/ high（Δ > 5） | Step 4 重写突降段落 |

## Layer D — 作品连续性（防风格/人设/数值崩坏）

跨章对比，Ch1 时大多数项降级为 skipped。

| ID | 检查项 | 方法 | 通过标准 | 严重 | 修复 |
|---|---|---|---|---|---|
| D1 | 与前 3 章风格一致 | 本章 vs 前 3 章：词汇分布、句长分布、描写密度 | 偏离度 < 30% | high | Step 4 风格回调 |
| D2 | 作品 DNA 一致 | 本章关键词 vs Ch1-3 建立的调性 | DNA 保留 ≥ 80% | high | Step 4 风格回调 |
| D3 | 主角人设连续 | 本章主角决策 vs `设定集/主角卡.md` 性格红线 | 无红线违反 | critical | Step 4 改写 OOC |
| D4 | 女主人设连续 | 本章女主戏 vs 女主卡 | 无工具人化 | high | Step 4 补女主性格 |
| D5 | 反派逻辑连续 | 本章反派行为 vs 反派动机链 | 逻辑自洽 | high | Step 4 调反派 |
| D6 | 战力曲线合理 | 主角能力 vs 境界表 vs 前 5 章增长速度 | 无跳级 | critical | Step 4 降能力表现 |
| D7 | 金手指代价执行 | 本章金手指使用 vs 代价规则 | 用则必付 | critical | Step 4 补代价 |
| D8 | 世界规则不越界 | 本章规则 vs 设定集 + 力量体系边界 | 无越界 | critical | Step 4 改写越界点 |
| D9 | 地理/时间物理合规 | 人物位置变动是否提供时间/交通 | 合理 | high | Step 4 补过渡 |
| D10 | 伏笔债务跟踪 | 已埋伏笔超期兑现计数 | ≤ 卷纲规划上限 | medium | 下卷规划调整 |

Ch1 特殊：D1/D2 跳过（无前章基线），其他照跑。

## Layer E — 创作工艺（AI 味重度检测）

Step 4 anti-AI 的补充。用 regex/grep 做硬指标。

| ID | 检查项 | 方法 | 通过标准 | 严重 | 修复 |
|---|---|---|---|---|---|
| E1 | AI 口头禅扫描 | grep：`首先\|其次\|总的来说\|不仅.*而且\|我们需要意识到\|综上所述\|值得注意的是` | 命中 ≤ 1 | high | Step 4 删除/改写 |
| E2 | Show vs Tell 比 | 情感命名句（"他感到"/"心中一紧"）vs 具象句（动作/生理反应）比例 | Show ≥ 60% | high | Step 4 具象化 |
| E3 | 模板化开头结尾 | 开头前 100 字 + 结尾后 100 字 与 AI 套路模板匹配度 | 匹配 < 30% | high | Step 4 改写 |
| E4 | 排比堆砌 | 连续 3 个以上对称结构句 | 命中 ≤ 1 段 | medium | Step 4 打散 |
| E5 | 信息倾倒 | 纯设定段字数占比 / 对话中单边 > 150 字段数 | 占比 < 10%，无 > 150 字单边 | high | Step 4 拆分 |
| E6 | 感官多样性 | 视/听/触/嗅/味 5 感使用数量 | ≥ 3 种 | medium | Step 4 补感官 |
| E7 | 镜头感锚点 | 本章可脑内成像的具体画面数量 | ≥ 5 | medium | Step 4 加画面 |
| E8 | 空间方位清晰 | 关键动作场景方位词锚定 | 战斗场景方位明确 | high | Step 4 补方位 |
| E9 | 对白辨识度 | 不同角色对白词汇/语气差异 | 关键角色有辨识 | medium | Step 4 调语音 |
| E10 | 潜台词密度 | 对白中"没说出口"占比 | ≥ 20%（避免全大白话）| medium | Step 4 加潜台词 |
| E11 | 典故使用真实性 | 对照 prose-quality-checker 的 `reference_naturalness_score` 与 `chapter_meta.allusions_used`；若 checker 给出非空评分但 allusions_used 为空/缺失，判为 subagent fallback 或未抽取；若二者都为空且正文肉眼可见典故，判为漏抽 | 两侧一致（同有或同无）；若有值，数量差 ≤ 1 | medium | Step 4 重跑 prose-quality-checker + data-agent Step B.5 |
| E12 | 典故密度合规 | 统计 `chapter_meta.allusions_used` 条数 vs `classical-references.md` 规定（单章上限 2 处）；统计近 5 章累计 vs 卷级上限 15 处 | 本章 ≤ 2；近 5 章 ≤ 3 | low | 规划调整或下章少用 |
| E13 | 典故载体合规 | 逐条检查 `allusions_used[*].carrier` 与角色设定（如主角话少 → 主角直接引用诗词 ≥ 3 处判 high；互联网梗的 carrier 不能是主角）| 无违规载体 | medium | Step 4 改写载体 |

> **E11-E13 触发条件**：`设定集/典故引用库.md` 或 `设定集/原创诗词口诀.md` 至少一个存在时执行；两者都不存在时 skip（不扣分）。
>
> **数据依赖**：依赖 data-agent Step B.5 产出的 `chapter_meta.allusions_used` 字段。若 Step 5 未产出该字段（如 chapter_meta 缺字段 > 30% 已被 B9 fail），E11-E13 同步 skip。

## Layer F — 题材兑现（项目特定，动态生成）

从 `state.project_info.core_selling_points` 动态生成。无卖点定义时 skip。

### 生成规则

```python
selling_points = state['project_info']['core_selling_points']  # "命理推演式战斗;天干地支觉醒体系;空亡体质双重代价;甲子赌局战斗机制"
for point in split(selling_points, ';,'):
    generate_check(point, chapter_content)
```

### 镇妖谱示例（审计时动态生成）

| ID | 检查项（基于 core_selling_points） | 方法 | 通过标准 | 严重 |
|---|---|---|---|---|
| F1 | 命理推演硬核度 | 本章推演场景可否让读者跟着推出部分答案 | 推演有可追溯逻辑链 | high |
| F2 | 空亡双重代价体现 | 本章若用空亡能力，是否同时体现妖化侵蚀 + 时辰锁定 | 两重代价均出现 | critical |
| F3 | 天干地支规则严格 | 本章出现的干支/命格 vs 力量体系.md 定义 | 无新规则凭空发明 | critical |
| F4 | 甲子赌局机制渐进 | 本章赌局元素 vs 之前铺垫 | 可追溯或首次埋设 | medium |
| F5 | 金手指独特性 | 本章金手指用法 | 有新 insight 且未同质化 | high |
| F6 | 女主印象碎片 | 若女主出场，留下具体印象锚（动作/物件/台词） | ≥ 1 | medium |

## Layer G — 跨章趋势（用最近 5 章基线）

数据源：`.webnovel/observability/chapter_audit.jsonl` 最后 5 行。Ch1-5 自适应降级。

| ID | 检查项 | 方法 | 通过标准 | 严重 |
|---|---|---|---|---|
| G1 | 评分趋势 | combined_score 最近 5 章曲线 | 下降 < 10 分/章；连续 3 章下降则警告 | high |
| G2 | 字数稳定性 | 本章字数 vs 5 章均值 | 偏离 < 30% | medium |
| G3 | 爽点密度趋势 | 爽点/千字 最近 5 章 | 不持续下降 | high |
| G4 | 章末钩子强度分布 | 最近 5 章 hook.strength 序列 | 有交替，无连续 3 弱 | high |
| G5 | 伏笔埋 vs 兑现差 | 近 10 章埋设数 - 兑现数 | 不超过阈值（10-20）| medium |
| G6 | checker 诊断漂移 | 某 checker 最近 5 章评分方差 | 方差在合理区间 | low |
| G7 | 同类 issue 累积 | 某类 issue 是否连续 3 章出现 | 无长期未修复类别 | high |
| G8 | 女主/反派出场频率 | 与卷纲规划频率对比 | 不偏离 > 30% | medium |
| G9 | Step K 实际产出趋势 | 最近 5 章 applied_additions 总数 | 不全为 0 | high |

Ch1-4 时：
- Ch1：Layer G 整层 skipped + reason "no baseline"
- Ch2：仅 G1/G2/G3 可跑（2 点数据）
- Ch3-4：有限数据，部分检查标注 "insufficient sample"
- Ch5+：全量执行

## 决议矩阵

```
IF any Layer A critical fail        → block
IF any Layer B critical fail        → block
IF any Layer C critical fail        → block
IF any Layer D critical fail        → block
IF any Layer F critical fail        → block
IF count(high) >= 3                 → block
IF count(high) in [1, 2]            → approve_with_warnings
IF count(medium) >= 5               → approve_with_warnings
IF count(medium) in [1, 4]          → approve_with_warnings
ELSE                                → approve
```

## editor_notes 写入规则

决议 ∈ {approve, approve_with_warnings} 时写入 `.webnovel/editor_notes/ch{NNNN+1}_prep.md`：

```markdown
# 第{NNNN+1}章写作准备（由第{NNNN}章审计生成）

> 由 audit-agent 自动生成，供 Step 1 context-agent 必读。

## 上章审计摘要
- 决议: {decision}
- 过程评分: {process} / 读者评分: {reader} / 工艺评分: {craft} / 连续性: {continuity}

## 警告（必须在本章回应）
- {warning 1 with remediation hint}
- {warning 2 ...}

## 未兑现承诺
- {上章钩子/铺垫是否需要本章接住}

## 跨章趋势提醒
- {G 层检测到的下滑/偏离}

## Step-specific 写作建议
### Step 1 Contract
- {对 context-agent 的具体建议}
### Step 2A 起草
- {对 writer 的具体建议}
### Step 4 润色
- {对 polish 的具体建议}
```

决议 = block 时**不写** editor_notes（因为当前章都没通过，没必要给下章建议）。
