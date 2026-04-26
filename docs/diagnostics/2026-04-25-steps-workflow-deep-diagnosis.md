# webnovel-writer Steps 流程深度诊断报告

> **生成日期**：2026-04-25
> **诊断范围**：末世重生 Ch1-Ch12 + 17+ RCA 元层面 + 流程架构
> **目标**：让"高质量、有读者爱看"的小说真正落地，识别当前流程在质量和工程效率上的所有阻碍
> **作者**：deep research 三路并行调度（读者视角 + 数据实绩 + RCA 元模式）

---

## 0. 执行摘要（Executive Summary）

**核心结论一句话**：当前流程**工程很硬、质量分很高、读者口碑可疑**，已陷入"工程闸门膨胀 > 写作内容增益"的负反馈，到了**该停手减法**而非继续叠 patch 的拐点。

**三个不舒服的事实**：

1. **90 分作品 ≠ 好看小说**。Ch1-12 平均 overall 88-92，但读者代理评分 **5.5/10**——评分体系和读者口味发生了系统性脱节。Ch4 `consistency-checker=47`、`reader-critic=58` 仍合成 `overall=88`，加权稀释让硬伤被掩盖。
2. **修流程时间 > 写章节时间**。Ch6 全流程跨度 28 小时、Ch7 19 小时，hygiene_check 从 12 项膨胀到 25 项（H1-H25 共 1479 行），SKILL.md 1195 行，post_draft_check 12 类 703 行。Round 1→19 累计 24 个 round commit，**0 个 commit 是删除/简化的**。
3. **17+ RCA 修不到根**。`audit-agent 伪窄字数区间`同一个 bug 跨 5 个 Round 修了 5 次（R15.1/17.1/17.4/17.5/Ch10/Ch11），每次"根治"下章再犯。问题不在闸门，在架构层（自由文本生成 + 下游字面 grep 是注定打不完的 whack-a-mole）。

**最重要的判断**：项目正在用越来越精密的工程刻度做错事——把"评分高"误当作"好看"。读者诊断给出的 **5.5/10** 是这本书最重要的一个数字，所有 13 维度 / 14 模型 / 7 层审计都没看见它。

---

## 1. 当前流程全景（Steps 0→8 一览）

### 1.1 流程图

```
Step 0   预检 + 三层缓存同步（CLAUDE_PLUGIN_ROOT / sync-agents / sync-cache / polish-drift）
Step 0.5 workflow start-task（4 步登记契约：start-task → start-step → complete-step → complete-task）
Step 1   Context Agent（生成"创作执行包"+ Context Contract，落盘 JSON+MD）
Step 2A  正文起草（中文思维 + visual-concreteness + anti-ai-guide + 前 5 章写前自检）
         ↓ post_draft_check.py（12 类硬闸门）
Step 2B  风格适配（仅标准模式，--fast/--minimal 跳过）
         ↓ post_draft_check.py（再跑一次）
Step 3   13 checker 内部审查（Batch 0+1+2，2+6+5 分批）
Step 3.5 14 外部模型 × 13 维度（核心 3 + 补充 11，3 供应商 fallback 链）
         ↓ overall_score = round(internal*0.6 + external*0.4)
Step 4   定向修复（critical → high → medium → anti_ai_force_check）
Step 4.5 选择性复测（任一 checker <75 强制 Task 复测，单点拉分）
         ↓ 字数预算 +200 净增 + ≤hard_max + 对话占比 ≥0.20
Step 5   Data Agent（A-K 11 子步：实体/索引/摘要/RAG/style/Step K 设定集追加）
Step 6   Audit Gate（Part 1 CLI 结构 5s + Part 2 audit-agent 60-300s 七层 A-G）
         ↓ approve / approve_with_warnings / block
[step gap] hygiene_check.py（25 项 H1-H25）+ pre_commit_step_k.py
Step 7   git commit + complete-step + complete-task
Step 8   Post-commit polish_cycle.py（v2/v3/v4 ... 多轮闭环）
```

**总计**：9 个明面 Step + 25 个 hygiene 子检查 + 12 个 post_draft 子检查 + 13 个内部 checker + 14 个外部模型 × 13 维度 = **每章约 250+ 个独立的 pass/fail 节点**。

### 1.2 Step 关键产物清单（充分性闸门 17 项）

正文 / 执行包 JSON+MD / 审查报告 .md / review_metrics 落库 / 润色报告 / state.json 字段（chapter_meta, polish_log, narrative_version, checker_scores, post_polish_recheck）/ summaries / audit_reports JSON / editor_notes 下章 / observability JSONL / workflow_state 完整四步登记 / git commit。

### 1.3 流程的"心跳"

- **每轮加 patch 必同步 7 处真源**：SKILL.md / hygiene_check.py / post_draft_check.py / workflow_manager.py / 各 agent prompt / 文档 / context-agent。Ch7 RCA-3 再次记录第 7 处遗漏。
- **三层缓存 + 第四层 in-memory registry**：fork → marketplace mirror → cache → session。任一层不同步，AI 跑旧代码（Ch6 reader_flow 血教训）。
- **元数据真源争夺**：state.json 是 SSOT，但 chapter_meta/editor_notes/审查报告/summaries 任一漂移都污染下章 context-agent。

---

## 2. 三视角诊断（最重要的部分）

### 2.1 读者视角（"卧槽这小说我追不下去"）

**追读评分：5.5 / 10。** 一句话：**"被写成纯文学的网文"——技术分 90，市场分 5.5**。

#### 致命劝退点（按致命度排序）

| 排名 | 病症 | 证据 | 病灶 |
|---:|---|---|---|
| 1 | **节奏散文化** | Ch11 整章只发生"看新闻 → 见老张 → 接电话 → 听汽笛"；Ch12 只发生"小女孩说手心有星星"。单章信息密度低于网文及格线 | 大纲层"过渡章/铺垫章 2200-2800"被当成正常推进章 |
| 2 | **金手指吝啬** | 标题"我在空间里种出了整个基地"，Ch12 空间还在"绿芽冒头"。前 12 章主角靠"重生信息差"+ 现金赚钱准备末世，**空间是摆设** | reader-pull-checker 长期偏低（Ch3=62/Ch4=58/Ch9=62→85 单点救场）反映的就是这个 |
| 3 | **AI 腔越改越浓** | "X 了一下，又 Y" 单章 20+ 次（"沙漏冷了一下又停"成口头禅）；"指节压了一下又松开" / "温了一下" 成 reflex | Ch1 v1→v7 反复 polish + Round 17.3 戏剧升级让"显得高级"压过"读起来好看" |
| 4 | **方言密度过载** | "得味""嗯呐"在 Ch6 一章出现 6 次以上，**像 AI 学会了梗就玩到死**。真合肥人不这么说话 | reader-naturalness-checker 把方言识别成正向，无密度上限阈值 |
| 5 | **情绪密度过低** | 情绪是真的，但读者要"这一章我哭了/笑了/气了"，给的是"这一章我品出一点东西" | emotion-checker 评估 Show vs Tell 过关，但不评估"情绪事件密度"——读完一章主角和读者**没有共同发生过一件事** |

#### 同样致命的反向问题（流程未识别）

- **前 12 章主角无正面冲突**。没怼过苏蕊（绿茶前任）、没揍过陈默（职场背叛者）、未与任何反派对线。**12 章攒的火没有发射口**。这是末世重生赛道的红线问题，13 维度 checker 全部漏报。
- **题材识别度低**。Ch1 前 500 字读完不知道这是末世——一个绿茶劈腿+职场被裁的悲情男主，跟 2018 年都市重生没区别。番茄读者会划走，留下来的是起点老白。
- **差异点是文学差异不是爽点差异**。陆沉是"算账的、隐忍的、藏锋的"——谍战小说男主套末世壳。番茄读者要的是"渣女回头跪求男主一个眼神不给"，给的是"男主路过陈默公司楼下停了两秒往左拐了"。

#### 优势（流程做对的部分）

- 文笔在线（中文母语自然度高，无翻译腔）
- 钩子设计精确（Ch1 前 100 字"第七次拨号 + 跪在月台 + 拉黑 + 没回妹妹的信"）
- 主角立得住（有羞耻感，自我审视，少见的"软底子"末世男主）
- 沙漏金手指设定本身有趣

**问题不在能力，在导向**——流程把作品往"显得高级"推，远离了"读起来爽"。

---

### 2.2 数据实绩视角（用 state.json 说话）

#### 12 章核心数据表

| 章 | 标题 | 字数 | overall | 版本 | polish | audit | 触底 checker (<80) |
|---:|---|---:|---:|:---:|:---:|---|---|
| 01 | 我又活了 | 2355 | 92 | **v7** | **9** | approve | ooc 81 |
| 02 | 二十九天 | 3489 | 89 | v2 | 1 | warn | flow 81 / **rc 76** |
| 03 | 一颗种子 | 2449 | 85 | v1 | 1 | pending | **rc 62** / cont 78 / flow 78 / emo 77 / prose 78 |
| 04 | 邻居陆老师 | 2872 | 88 | v2 | 1 | pending | **cons 47** / **rc 58** / flow 70 / ooc 74 |
| 05 | 雨夜便当 | 3406 | 89 | v2 | 1 | warn | hp 86 / nat 78 / rc 71 |
| 06 | 邻居的狗叫 | 3451 | 85 | **v3** | 2 | warn | cont 78 / flow 79 / rp 80 / hp 80 / pace 83 |
| 07 | 一根烟的工夫 | 3346 | 89 | **v3** | 2 | warn | **pace 58→90** / nat 83→88 |
| 08 | 老朋友请客 | 2872 | 88 | **v3** | 2 | warn | dial 81 / pace 82 |
| 09 | 后怕 | 3497 | 89 | v1 | 1 | warn | **rp 62→85** / cons 74→88 / cont 74→89 |
| 10 | 老张 | 3495 | 88 | v1 | 1 | warn | nat 70→89 / rc 78→88 |
| 11 | 浓雾新闻 | 2471 | 90 | v2 | 1 | warn | nat 78→88 / prose 81→91 |
| 12 | 那个小女孩 | 2652 | 88 | v1 | 1 | warn | nat 78→88 / flow 86→89 |

> rc = reader-critic / nat = naturalness / cons = consistency / cont = continuity / rp = reader-pull / pace = pacing / hp = high-point / dial = dialogue / emo = emotion

#### 5 个最严重的数据级问题

**P1. overall 加权机制系统性掩盖硬伤**
Ch4 `consistency-checker=47` + `reader-critic=58` 仍合成 `overall=88`。state.json 自承"checker_scores 落库原始 Step 3 分数（修复前）·overall 88 为合并后加权"。**这不是数据展示问题，是评分体系撒谎**——加权 + 加修复后参数让任何单维度硬伤都能被稀释。

**P2. Step 4.5 单点拉分救场已成常态**
Ch7 pacing 58→90 (+32)、Ch9 reader-pull 62→85 (+23)、Ch10 naturalness 70→89 (+19)、Ch11 prose 81→91 (+10)。这些都是单维度补测后写回 state，**13 维度共识从未重跑过**。流程上等于"只补考最低那门"。一旦 Step 4 polish 改动跨维度（修了 pacing 但破坏了 dialogue），单点复测看不见。

**P3. reader-critic 长期红区无系统对策**
Ch2=76 / Ch3=62 / Ch4=58 / Ch5=71，**连 4 章 ≤ 76**。这是"读者代理"视角——最贴近真实读者的维度——的最低分。Ch3-4 的 62/58 本应触发 P0 阻塞，但 audit 给的是 approve_with_warnings/pending 放行。Round 13 v2 主动取消 veto 架构（理由："block 重写浪费"），结果是**真正反映读者口碑的维度被永久降级为 warning**。

**P4. Ch1 polish 11 轮是流程沉没成本警报**
v1→v7 + v5.1/v6.1/v6.3/v6.4/v6.5 总共 11 个里程碑，state.json `worldbuilding_clarifications` 自承："v1→v5.1 5 轮全是加法累积失焦 / 字数 3166→2296 减 870 字 / Step 6 七层检测器盲区=作品整体真实感"。**早期"加法导向 polish"会陷死循环**——这是当前 polish_cycle 架构的固有病。

**P5. context/editor_notes/audit 多层归档常态性漂移**
Ch6-8 在 Round 17.3-17.4 才修好"v3 正文 / v1 归档"不一致；Ch9 RCA：editor_notes 来自 Ch8 v3 audit，没读 v4 大纲，南瓜汁 payoff 漏 → reader-pull 62；Ch12 data-agent 仍在出 `foreshadowing F-B1 不存在` 报错。**第 5 次复现同类问题**。

#### 时间投入实测

| 章节 | 全流程跨度 | 备注 |
|---:|---:|---|
| Ch3 | ~7 h | 早期相对快 |
| Ch6 | **~28 h** | 含 Round 17.3 戏剧升级 |
| Ch7 | **~19 h** | 含 pacing 单点复测 + 多轮 polish |
| Ch9 | ~4.7 h | 首次接近流程目标 |
| Ch11 | **~56 min** | 当前最快 |
| Ch12 | ~3 h | 较稳 |

**Step 6 audit ≈ 4 分钟/次（单 agent 调用）**。**Step 3+3.5+4+4.5 整个写作改进闭环才是大头（30+ 分钟 + AI 决策 + 多轮 polish）**。Step 6 反而是"快环节"。

---

### 2.3 RCA 元层面视角（17+ 根因模式）

#### 6 桶分类（24+ RCA 条目分布）

| 桶 | 条目数 | 代表 |
|---|---:|---|
| A 流程登记/状态漂移 | 4 | Ch2 FLOW-01 / Ch5 Bug 4 / Ch11 #3 / Round 17.4 三层归档 |
| B 缓存/同步层 | 5 | Ch6 sync-agents / sync-cache / Round 14 session reload / Ch7 路径感知 / preflight 内容漂移 |
| C 子代理 fallback | 2 | Ch6 reader_flow / Ch5 Bug 6 |
| **D schema/canonical key** | **7** | Ch1 6 层防御 / Ch2 schema 双套 / Ch5 字段级 CLI / Ch7 白名单 / Ch10 双路径 / Round 17.3 list/dict / doc_counter 7 处真源 |
| **E 写作内容** | **6** | Ch1 披露时序 / Ch4 三 RC / Ch5 RC1/4/5 / Ch9 元叙事 / Ch10 P0-1 引号 / Ch11 那一X 18 次 |
| **F 审计盲区** | **7** | Ch5 RC2/3 / Ch7 polish_recheck / Ch9 audit 大纲 / Ch10 伪窄区间 / Ch11 audit/flow 复测 / Ch11 方言 false_positive / "11 vs 12" 术语 |

**最高频是 D + F 耦合**：状态字段无单一真源 + 审计 agent 自由文本输出污染下游 context-agent，形成"AI 给 AI 喂坏数据"闭环。

#### 元层面 4 个判断

**1) 全是叠 patch，0 简化**
24 个 round commit 一路 `feat(round N): 根治 X 类 bug`。**没有任何一个 commit 删除或合并旧流程**。post_draft_check 7 类→12 类，hygiene 12 项→25 项，SKILL.md 增到 1195 行，**~10 倍膨胀**。

**2) 修法连锁反应**
Ch10 P0-1：修 ASCII 引号 auto-fix 触发条件 → Edit 工具 normalize 成 U+201D → 旧条件不触发；之前 Ch5 RC5 + Ch6 修复 #3 已修过两次"引号"。
Ch11 #2：押了 polish-guide 的"没X≤15"硬线，AI 起草迁移到"那一X" 18 次，又得加新签名扫描。
Ch9 audit 伪窄区间已**第 4 次复现**（Round 15.1/17.1/17.4/17.5），每次"根治"都没真正根治。

**3) 修一次就不复发的反例（真根治）**
Ch5 末世 Bug 5：CLAUDE_PLUGIN_ROOT 未自动 export → SKILL Step 0 加 3 级 fallback 推导。之后所有章节、所有 shell 环境都 OK，没再出现。**修的是确定性环境逻辑**——不是"AI 行为模式"。

**4) 同类反复出现的正例（伪根治）**
audit-agent 写伪窄字数区间到 editor_notes 污染下章 context-agent——**5 次 round 修同一类 bug**。原因是问题不在代码，在"自由文本生成 + 下游字面 grep"这个架构本身——只要 audit 还在自由文本输出，下游正则就永远会被新表述绕开。

#### 复杂度判断

时间比 ≈ **修流程 : 写章节 = 1 : 1 至 1 : 2**（修流程 > 写）。
Ch6 28h、Ch7 19h、Ch11 报告"5 小时全流程" + Round 18.2 "7 类 fork 改动"。元数据/审查/归档层的工程总投入已远超"写 2200-3500 字 + 一次 polish"应有的成本。

---

## 3. 三个根本矛盾（系统级问题）

### 矛盾 1：评分体系 vs 读者口味

**症状**：13 内部 checker + 14 外部 × 13 维度 + 7 层审计共 **250+ 个 pass/fail 节点**给出 90 分，读者代理给出 5.5 分。

**根因**：
- **加权稀释**：overall 是平均/加权，硬伤不否决（Ch4 consistency 47 不阻塞）
- **规则同源污染**：reader-critic / naturalness 是 LLM checker，跟 writer 同源，规则趋同导致集体失灵（Ch1 v1 "陆沉在死"语病被 19 个 checker + 7 层审计放行的血教训）
- **"高质量"被定义成"显得高级"**：visual-concreteness rubric 推 Show not Tell + 5+1 感官色谱，结果是"每个动作必须配一个内心微反应"——前 3 次叫风格，第 30 次叫机器
- **缺市场维度**：流程评估"对不对"，不评估"读者会不会追下去/会不会爽"

**最反映这个矛盾的数据点**：reader-critic 连续 4 章 ≤ 76 + Round 13 v2 主动取消 veto → 真正贴近读者的维度被结构性降级为 warning。

### 矛盾 2：流程精度 vs 写作通顺度

**症状**：流程节点越来越多，AI 起草时背的"硬约束"越来越多——每章要满足 25 个 hygiene + 12 个 post_draft + 18 个 anti-AI 倾向 + 8 个 first-chapter-rubric 子项 + 5 类前 5 章写前自检 + 13 维度起草目标 + 字数预算 + 对话占比 + 视觉锚点 + 章末钩子 4 分类 + ...

**结果**：AI 不是在写小说，是在做填空题。symptom 包括：
- 每个动作都要配一次内心微反应（达成 visual-concreteness）→ AI 腔
- 方言重复堆砌（达成 naturalness）→ "得味"一章 6 次
- 句式刻意 patch（避开"没X" → 出"那一X" 18 次）
- 信息密度严格控制（避免认知载入超标）→ 节奏散文化
- 金手指披露时序严控（"前世金手指共现 critical"）→ 12 章了空间还在"绿芽冒头"

**根因**：**约束的颗粒度变细 ≠ 作品质量变好**。约束总数过载时，AI 会优先满足可机器测的约束（quote、字数、对话比、引号），牺牲不可机器测的约束（戏剧张力、爽感、读者投入度）。

### 矛盾 3：自由文本 vs 字面 grep

**症状**：audit-agent 写自由文本"建议下章 2400-3200 字" → context-agent 字面 grep 读到 → 写进执行包 → AI 起草按 2400-3200 → 与 SSOT hard_min/max 2200/3500 冲突。

**修法历史**：Round 15.1 加 marker → Round 17.1 加 SSOT 优先 → Round 17.4 改 audit 输出 → Round 17.5 P0-2 扩窗口 → Ch10 P0-2 升 WARN → Ch11 #1 又加签名扫描。

**根因**：**架构层错**——只要"audit-agent 自由文本输出"和"context-agent 字面 grep"这两个机制存在，下游正则永远会被新表述绕开。修的是表象，不是机制。

---

## 4. 优先级问题清单

### P0 / 该立刻动手 / 决定能不能写出"好看"小说

#### P0-1 把"读者爽感"重新装回流程
**当前流程没有"爽点维度"——只有 high-point-checker 数密度，没人评估爽感 strength**。
- 加 `reader-thrill-checker`（不是 critic 的语言批评，是"这章看完爽不爽"），从故事节奏 / 金手指释放 / 主角胜利 / 反派打脸 / 逆转 / 信息差 6 维评分
- 接入 reader-thrill ≤ 70 = block（不是 warning）—— 把 Round 13 v2 取消的 veto 用在这一个最重要的维度
- 给 Ch13-20 强制 KPI：金手指释放强度递增（空间出货从 Ch13 起每 2 章一次小爽点）

#### P0-2 大纲层面"金手指释放计划"硬约束
读者诊断：标题"我在空间里种出了整个基地"，Ch12 空间还在绿芽。**这是导向问题不是工艺问题**。
- 在 `大纲/总纲.md` 增 `golden_finger_release_plan`：每 N 章必出货
- context-agent 在执行包里硬塞"本章金手指 payoff 强度"目标，未达成 = warning 升 high
- 现存 Ch1-12 不可逆，但 Ch13 起强制每 3 章一个空间高光时刻

#### P0-3 砍掉"AI 腔放大器"约束
当前 anti-ai-guide.md "8 倾向 + 5 即时检查 + 替代速查表" 推动了：
- "X 了一下，又 Y" 单章 20+ 次
- "沙漏冷了一下又停" 一章 4 次
- 方言堆砌（"得味""嗯呐"作 reflex）
- 每个动作必带内心微反应

**修法**：
- anti-ai-guide 加"反向约束"：内心微反应每章上限 8 次、口头禅型方言上限 3 次
- visual-concreteness 不是"每个动作"，是"每场关键时刻"
- prose-quality-checker 加"句式 reflex 检测"——同一节拍单章 ≥10 次 = high

#### P0-4 给主角配"火力释放阀"
12 章无正面冲突。这是末世重生赛道红线。
- 大纲调整：Ch13-15 必须有一次主角对苏蕊/陈默/或代理人的正面回击
- 不必是物理打脸，但必须是**让读者爽到的"对线时刻"**
- reader-pull-checker 加"未释放火力章数"计数器，连续 3 章无主角胜利 = high

### P1 / 该解决 / 决定流程效率

#### P1-1 替换"加权 overall"为"硬伤一票否决"
**Ch4 cons 47 + rc 58 → overall 88** 这种事不能再发生。
- overall 公式改为：`min(critical_dim_floor, weighted_avg)`
- 任一维度 ≤ 60 = overall 上限 70
- ≤ 75 = overall 上限 85
- 强制 Step 4 polish 直到所有维度 ≥ 75 才允许 Step 5

#### P1-2 砍掉"自由文本字数建议"机制
audit 伪窄区间修了 5 次没根治。
- editor_notes 删除"字数建议"自由文本字段
- 改为 enum：{`保持当前区间` | `偏短 → 推荐 ≤2800` | `偏长 → 推荐 ≥3000`}
- context-agent 读到 enum 才生效，自由文本一律忽略
- 一次架构改动 vs 5 次正则 patch + 未来无穷次

#### P1-3 hygiene/post_draft 闸门分级
当前 25+12 共 37 项硬闸门，许多是启发式（如方言密度、虚词频率）触发 false_positive（Ch11 #5）。
- 拆两类：**P0 硬闸门**（≤ 8 项，纯代码语义违规：ASCII 引号 / U+FFFD / 字数范围 / Markdown 残留 / 编码 / workflow 状态 / artifact 字段 / Step 顺序）
- **P1 启发式 lint**（其余 30+ 项一律降到 INFO，不阻塞 commit）
- 启发式触发 ≥ 3 项 = 综合 warning

#### P1-4 真源单源化
"7 处真源"已记录在案，Ch7 RCA-2 又遗漏一处。
- 创建 `webnovel-writer/scripts/constants.json`（checker 列表 / artifact 字段 / 字数子区间 / 维度数）
- 用脚本生成 SKILL.md / workflow_manager.py / agent prompt 的相应段落
- 改一次 = 7 处自动同步

#### P1-5 polish 时间预算硬上限
Ch1 polish 11 轮、Ch6 跨度 28 小时——polish 没有"何时停止"的判据。
- 单章 polish 总时长上限 **3 小时**，超时触发"放弃完美主义"协议：写 deviation 进 audit_reports，进入下章
- 单章 polish 轮数上限 **3 轮**（v2/v3/v4），第 4 轮触发同上协议
- 触发协议不是失败，是流程出口

### P2 / 该研究 / 长期方向

#### P2-1 引入真实读者样本作为校准锚
13 维度 + 14 模型都是 LLM——同源污染问题无法靠加 checker 解决。
- 招 5-10 个真人读者每月读 2 章，给 1-10 追读分
- 用真人分校准 reader-critic / reader-pull / naturalness 三个 LLM 维度
- 当 LLM 分 ≥ 85 但真人 ≤ 6 时触发"评分体系再校准"任务

#### P2-2 大纲层"读者承诺"显式化
当前大纲是事件列表 + 节拍表。缺的是**"读者读到这章会得到什么爽感/情绪/信息"的承诺清单**。
- 每章在大纲中显式写 `reader_promise: ["金手指出货-小爽点", "渣女首次面对主角-悬念", "陆沉首次主动出击-火力释放"]`
- Step 1 context-agent 把承诺转成执行包硬约束
- Step 3 reader-pull-checker / high-point-checker 比对承诺兑现度

#### P2-3 流程瘦身实验
- 单章试做"标准流程 vs 简化流程"AB 对比：简化流程跳过 Step 2B + Step 4.5，仅保留 Step 0/1/2A/3+3.5/4/5/6/7
- 让真人读者盲读两版，看哪版好看
- 数据决定哪些 Step 真正贡献质量、哪些只贡献分数

---

## 5. 立刻可做的"减法清单"

> 不再加新东西，先减、合、删。**这是与过去 19 轮 round 完全不同的方向**。

### 减法 A · 砍约束（影响起草直接性）
- [ ] anti-ai-guide.md "8 倾向" 加"上限"概念，避免反向滥用
- [ ] visual-concreteness rubric 改"每场关键时刻"而非"每个动作"
- [ ] 方言密度引入硬上限（口头禅型每章 ≤ 3 次）
- [ ] 删除前 5 章写前自检的 NEEDS_ADJUST 阻塞（保留报告，不阻塞）

### 减法 B · 合闸门
- [ ] hygiene H1-H25 拆 P0/P1 两层，P1 全降 INFO
- [ ] post_draft 12 类拆同上
- [ ] 启发式 lint 改单一聚合 warning，避免 25 个独立 fail

### 减法 C · 删自由文本
- [ ] editor_notes 字数建议改 enum
- [ ] audit-agent 输出从自由文本改 schema-validated JSON
- [ ] context-agent 不再 grep editor_notes，只信 SSOT

### 减法 D · 缩 polish
- [ ] polish 轮数硬上限 3
- [ ] polish 时长硬上限 3 小时
- [ ] 超限触发 deviation 出口协议

### 减法 E · 合真源
- [ ] 7 处真源用 constants.json 生成
- [ ] doc 数字带限定词（"13 个内部 checker（含 2 读者视角）"明确写）

---

## 6. 加法清单（必须新增的少数几样）

> 加法只允许加在 P0：直接服务"读者觉得好看"的目标。

### 加法 1 · reader-thrill-checker（爽点强度）
6 子维度（金手指释放 / 主角胜利 / 反派打脸 / 逆转 / 信息差 / 节奏推进），加权得 thrill_score。
- ≤ 70 = block
- block 不是 polish，是回 Step 1 调大纲

### 加法 2 · 大纲 `golden_finger_release_plan`
每 N 章一次空间出货，强度递增。
- Ch13-15 小爽点（空间种出第一批可食用作物）
- Ch16-20 中爽点（空间救命/喂活动物）
- Ch21+ 大爽点（空间扭转关键局势）

### 加法 3 · 大纲 `reader_promise` 字段
每章 3-5 条承诺（情绪/信息/爽点/悬念）。
- Step 1 转执行包
- Step 3 兑现率检测

### 加法 4 · 真人读者校准回路（季度级）
不进每章 hot path，但作为流程整体健康度的"地面真值"。

---

## 7. 量化目标（KPI）

| 指标 | 当前 | 3 章后 | 10 章后 |
|---|---:|---:|---:|
| 真人读者追读分 | 5.5 / 10 | 7.0 / 10 | 8.0 / 10 |
| 单章流程总时长 | 5-28 h | ≤ 5 h | ≤ 3 h |
| polish 平均轮数 | 1.3 (Ch1=11) | ≤ 1.5 | ≤ 1.5 |
| 任一维度 < 60 章数 | 2/12 | 0/3 | 0/10 |
| 金手指 payoff 章数 | 1/12 (Ch9 南瓜汁) | 2/3 | 5/10 |
| 主角主动冲突章数 | 0/12 | 1/3 | 4/10 |
| RCA 新增 / 章 | 1.5 个 | ≤ 0.5 个 | ≤ 0.2 个 |
| hygiene_check 行数 | 1479 | 持平 | **缩减至 < 1000** |
| post_draft 行数 | 703 | 持平 | **缩减至 < 500** |

---

## 8. 实施优先级路线图

### 阶段 1（本周，最高 ROI）
**目标：让 Ch13 写出读者真的爱看的内容**

1. P0-2 大纲层金手指释放计划（修 `大纲/总纲.md` 加段，2 小时）
2. P0-4 主角火力释放阀（修 Ch13-15 大纲，2 小时）
3. P0-3 anti-ai-guide 反向约束（修 reference 文件，1 小时）
4. 加法 3 reader_promise 字段（先在 Ch13 大纲手写一份，跑完看效果）

**验证**：Ch13 写完后，让另一个 agent 完整复诊（同读者视角脚本），看追读分是否 ≥ 7。

### 阶段 2（2 周内）
**目标：流程瘦身，时间预算回正**

5. P1-1 硬伤一票否决（改 webnovel.py 评分聚合 + state update CLI）
6. P1-3 hygiene 闸门分级（拆 hygiene_check.py P0/P1）
7. P1-5 polish 时间/轮数上限（改 polish_cycle.py）
8. P0-1 reader-thrill-checker（新增 agent，跑 Ch13/14 验证）

### 阶段 3（1 个月内）
**目标：根治架构层 bug，停止 RCA 循环**

9. P1-2 自由文本→enum（改 audit-agent / context-agent 协议）
10. P1-4 constants.json 单源生成（脚本 + CI 校验）
11. 加法 4 真人读者校准（招募 + 流程接入）

### 阶段 4（持续）
**目标：从"AI 写小说"升级为"AI + 真实读者反馈协同"**

12. P2-3 流程瘦身实验（AB 对比）
13. P2-1 真人样本作为 LLM 评分校准锚
14. 反向迭代：根据真人反馈砍掉对追读分无贡献的流程节点

---

## 9. 一句话结论

> **当前流程的最大问题不是没修干净的 bug，是修的方向。**
> **过去 19 轮在做"让分数更高"，应该转向"让读者更爱看"。**
> **第一步是承认 5.5/10 的读者评分比 90/100 的 overall 评分更重要。**

---

## 附录 A · 关键文件路径速查

```
SKILL.md                                    1195 行
hygiene_check.py                            1479 行 (H1-H25)
post_draft_check.py                         703 行 (12 类)
末世重生/.webnovel/state.json              chapter_meta 0001-0012
末世重生/审查报告/第0007章流程诊断报告.md   polish-no-retest 自承
末世重生/审查报告/第0009章Round17.5深度RCA  context-agent 不读 v4 大纲
末世重生/审查报告/第0006-0008章Round17.4    v3 正文 / v1 归档漂移
末世重生/.webnovel/polish_reports/ch0001.md 448 行 Ch1 反复 polish 证据
memory/ 目录                                42 条 feedback + 17+ 章 RCA
```

## 附录 B · 24 个 round commit 演化（feat 但无 simplification）

```
Round 4 → Round 19.1
- 0 simplification commits
- 0 deletion commits
- 24 feat: round N: 根治 X 类 bug commits
- ~10× 闸门膨胀（hygiene 12→25，post_draft 7→12）
- ~5× RCA 同类问题反复（audit 伪窄区间）
```

## 附录 C · 三视角原始诊断（已并行 agent 完成，本报告综合）

- 读者视角：5.5/10，4 章抽样，6 个核心问题诊断
- 数据实绩：12 章 chapter_meta + observability JSONL + 5 个非常规审查报告
- RCA 元层面：6 桶分类 + 4 段判断 + 3 条停手信号

---

**报告结束。**
