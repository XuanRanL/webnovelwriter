# Webnovel-Writer Customizations Log

> Fork: https://github.com/XuanRanL/webnovel-writer
> Upstream: https://github.com/lingfengQAQ/webnovel-writer
> This file tracks all custom modifications made to this fork.
> When merging upstream updates, use this file to verify no customizations are lost.

---

## [2026-03-27] Step 3.5 外部模型审查

**Commit:** d1015e1

**改动文件：**
| 文件 | 类型 | 说明 |
|------|------|------|
| `skills/webnovel-write/SKILL.md` | 修改 | 模式定义加入 3.5、引用清单、step-id、充分性闸门、步骤定义 |
| `scripts/external_review.py` | 新增 | 调用硅基流动 API (Qwen3.5 + GLM-5) 双模型审查脚本 |
| `skills/webnovel-write/references/step-3.5-external-review.md` | 新增 | Step 3.5 执行规范文档 |

**背景：**
- 7模型对比测试（DeepSeek-V3.2, Qwen3.5-397B, MiniMax-M2.5, GLM-5, Kimi-K2.5, GLM-4.7, DS-Terminus）
- 最终选定 Qwen3.5-397B（设定/逻辑，区分度80-93）+ GLM-5（编辑/读者感受，区分度80-93）
- 淘汰原因：DS-Terminus 零区分度、MiniMax 格式不稳、DeepSeek-V3.2 区分度低

**SKILL.md 具体改动点（合并时注意）：**
1. 第26-28行：三个模式定义加入 `→ 3.5`
2. 第62-64行：references 清单新增 `step-3.5-external-review.md` 条目
3. 第152行：`--step-id` 允许列表加入 `Step 3.5`
4. 第259-280行：插入完整的 `### Step 3.5` 段落（在 Step 3 和 Step 4 之间）
5. 第370行：充分性闸门新增第3条（Step 3.5 外部审查必须完成）

---

## [2026-03-28] Step 3.5 双供应商架构 + 失败重试

**改动文件：**
| 文件 | 类型 | 说明 |
|------|------|------|
| `scripts/external_review.py` | 重写 | 主力 codexcc + 备用硅基流动，失败自动切换 |
| `skills/webnovel-write/references/step-3.5-external-review.md` | 更新 | 双供应商配置文档、重试机制说明 |

**背景：**
- 11模型×多轮稳定性测试（硅基流动 + codexcc 两个供应商）
- 硅基流动 GLM-5 成功率仅 60%（6/10），Qwen3.5-397B 稳定性 ACCEPTABLE
- codexcc qwen3.5-plus 成功率 100%（20/20），稳定性 GOOD（StdDev 1.9）
- codexcc kimi-k2.5 成功率 100%（5/5），区分度 HIGH（spread=9）
- 决策：codexcc 升主力，硅基流动降备用

**模型配置变更（2026-03-28 更新为三模型）：**
- qwen: codexcc `qwen3.5-plus` → 备用 硅基流动 `Qwen/Qwen3.5-397B-A17B`（稳定锚点）
- kimi: codexcc `kimi-k2.5` → 备用 硅基流动 `Pro/moonshotai/Kimi-K2.5`（逻辑/设定视角）
- glm: codexcc `glm-5` → 备用 硅基流动 `Pro/zai-org/GLM-5`（编辑/读者感受视角）

**脚本改动要点（合并时注意）：**
1. PROVIDERS 字典：双供应商 base_url + env_key_names
2. MODELS 字典：三个模型（qwen/kimi/glm），每个有 primary/fallback 两套配置
3. `try_provider()`: 单供应商最多重试 2 次（含 JSON 解析失败重试）
4. `call_model_with_failover()`: 主力 2 次 → 切备用 2 次
5. `load_api_keys()`: 支持多供应商 key 加载
6. `--models` 参数默认值：`qwen,kimi,glm`
7. 输出 JSON 增加 `provider` 字段标记实际使用的供应商

---

## [2026-03-28] Step 3 审查路由改为全量执行

**改动文件：**
| 文件 | 类型 | 说明 |
|------|------|------|
| `skills/webnovel-write/references/step-3-review-gate.md` | 更新 | 6个审查器标准模式全部执行，去掉条件路由 |

**背景：**
- 原 auto 路由导致 reader-pull/high-point/pacing 三个审查器经常被跳过
- 用户要求所有章节必须走完整流程，6个审查器全跑

**改动要点（合并时注意）：**
1. 审查路由模式：标准/--fast 改为全量6个，--minimal 保持核心3个
2. 去掉 Auto 路由判定信号整个段落
3. Task 调用模板：去掉条件判断，标准模式直接选全部6个

---

## [2026-03-28] SKILL.md 流程硬约束强化

**改动文件：**
| 文件 | 类型 | 说明 |
|------|------|------|
| `skills/webnovel-write/SKILL.md` | 更新 | 流程硬约束新增4条禁止规则 |

**背景：**
- Ch13-20写作时为赶进度跳过了Context Agent和内部审查子代理，审查报告文件也没生成
- 用户明确要求：任何情况下不能跳过任何Step，质量优先于速度

**新增禁止规则：**
1. 禁止赶进度降级：批量写多章时每章必须独立走完完整流程
2. 禁止跳步（强化）：补充了具体违规场景描述
3. 禁止省略审查报告：Step 3 必须生成审查报告 .md 文件
4. 禁止主观估分：overall_score 必须来自子代理聚合，不得自行估算

---

## [2026-03-28] Step 3.5 升级为Agent化6维度审查

**改动文件：**
| 文件 | 类型 | 说明 |
|------|------|------|
| `agents/external-review-agent.md` | 新增 | 外部审查Agent定义，读上下文+调API+交叉验证 |
| `scripts/external_review.py` | 重写 | 新增 `--mode dimensions` 6维度并发模式 |
| `skills/webnovel-write/references/step-3.5-external-review.md` | 重写 | 3模型×6维度架构，与Step 3并行 |
| `skills/webnovel-write/SKILL.md` | 更新 | 模式定义改为 Step 3+3.5 并行 |

**背景：**
- 旧方案：脚本直调API，单prompt 4维度合并审查，无项目上下文，误判率高
- 新方案：3个external-review-agent并行，每个内部6维度并发API调用，带完整项目上下文
- 测试结果：Ch5-8测试，qwen/kimi/glm全部6/6维度成功，共72+个维度报告0失败

**架构变更：**
```
旧：Step 3完成 → 脚本调3模型各1次 → Claude复核
新：Step 3(6个checker) + Step 3.5(3个agent×6维度) 并行 → Claude统一复核24份报告
```

---

## [2026-03-29] 默认字数目标调整 2000-2500 → 3000-3500

**改动文件：**
| 文件 | 类型 | 说明 |
|------|------|------|
| `skills/webnovel-write/SKILL.md` | 修改 | 第12行全局目标 + 第205行Step 2A硬要求，2000-2500→3000-3500 |
| `skills/webnovel-write/references/style-adapter.md` | 修改 | 第22行默认字数 + 第66行章节类型适配，2000-2500→3000-3500 |

**背景：**
- 实际章节字数分布1700-4100，目标值偏低导致大量章节"超标"但无人拦截
- 用户要求先调高目标观察效果，后续可能加硬性检测

---

## [2026-03-29] Step 3.5 升级：healwrap 主力 + 6模型 + 升级输出格式

**改动文件：**
| 文件 | 类型 | 说明 |
|------|------|------|
| `skills/webnovel-write/SKILL.md` | 修改 | 章节闸门从"3个外部模型"改为"6个外部模型（核心3必须成功）" |
| `agents/external-review-agent.md` | 修改 | 加入优先引用 workspace rules 的说明；provider 示例从 codexcc 改为 healwrap |

**对应 workspace 规则文件（非插件文件，不受上游合并影响）：**
| 文件 | 说明 |
|------|------|
| `.cursor/rules/webnovel-workflow.mdc` | Step 3.5 完整配置：6模型双层架构 + 三级 fallback + RPM 控制 + 路由验证 |
| `.cursor/rules/external-review-spec.mdc` | 升级版 Prompt 模板 + 输出 JSON Schema + 审查报告 Markdown 模板 |
| `.env` | 新增 HEALWRAP_API_KEY，保留 CODEXCC 和硅基流动作为备用 |

**架构变更：**
```
旧：codexcc 主力，3模型(qwen/kimi/glm)，备用硅基流动
新：healwrap 主力，6模型(核心kimi/glm/qwen-plus + 补充qwen/deepseek/minimax)
    fallback: healwrap(2次) → codexcc(1次) → 硅基流动(兜底)
    6并发发送，遇429等6秒重试
    每次调用后验证 response.model 字段确保路由正确
```

**输出格式升级：**
- issue 增加 type/location/suggestion/quote 字段（可直接驱动 Step 4）
- JSON 增加 model_actual/routing_verified/provider_chain/cross_validation/api_meta
- 审查报告增加 6模型评分矩阵 + 共识问题 + Step 4 修复清单

**SKILL.md 具体改动点（合并时注意）：**
1. 第53行：章节闸门 Step 3.5 条件从"3个"改为"6个（核心3必须成功，补充3失败不阻塞）"
2. 第55行：审查报告描述从"外部3模型分数"改为"外部6模型评分矩阵"
3. 第86-88行：references 清单新增 `step-3.5-external-review.md` 条目
4. 第286-300行：在 Step 3 和 Step 4 之间插入完整的 `### Step 3.5` 执行段落（加载 reference + 硬要求 + 输出）

**新增文件（合并时注意）：**
- `skills/webnovel-write/references/step-3.5-external-review.md`：Step 3.5 完整规范（6模型架构/供应商fallback/Prompt模板/输出Schema/路由验证/审查报告模板）

**external-review-agent.md 具体改动点（合并时注意）：**
1. 第12行后：新增说明段落，指向 reference 文件优先
2. 第86行：provider 示例从 "codexcc" 改为 "healwrap"

---

## [2026-03-29] Step 5 增加 Step K: 设定集同步检查

**改动文件：**
| 文件 | 类型 | 说明 |
|------|------|------|
| `skills/webnovel-write/SKILL.md` | 修改 | Step 5 子步骤列表增加 K + 设定集同步说明段落 |
| `agents/data-agent.md` | 修改 | 增加 Step K 执行规范（新实体/道具状态/伏笔/资产变动/字数） |

**背景：**
- 设定集与正文内容长期脱节（女主卡空白、暴走系统/猎人公会运作未记录、道具无时间线）
- 新增 Step K 在每章写完后自动检查设定集文件是否需要更新
- 所有追加带 `[ChN]` 章节标注——确保重写任意章节时能判断"此时此刻什么存在"

**SKILL.md 具体改动点（合并时注意）：**
1. Step 5 子步骤列表：在 I 后增加 `- K. 设定集同步检查（每章执行，best-effort，失败不阻断）`
2. 债务利息段落后：新增"设定集同步（Step K）"说明段落

**data-agent.md 具体改动点（合并时注意）：**
1. Step I 和 Step J 之间：插入完整的 `### Step K: 设定集同步检查` 段落
2. 包含4个子检查：新实体检查 / 已有条目状态更新 / 伏笔追踪 / 资产变动

**配套的设定集文件（在项目目录中，非插件文件）：**
- `设定集/道具与技术.md`：每个条目带 `[ChN 动作]` 时间线标注
- `设定集/伏笔追踪.md`：9条伏笔线的完整埋设→推进→兑现链
- `设定集/资产变动表.md`：信用点交易账本
- `设定集/老周卡.md`：配角卡（带身体状态时间线）

---

## [2026-03-29] 写前规划全面升级（11项改进）

**改动文件：**
| 文件 | 改动概述 |
|------|---------|
| `skills/webnovel-init/SKILL.md` | 新增Step3"自动填充设定集"（角色卡实质内容+语音规则+配套文件）+ 充分性闸门增加5条 |
| `skills/webnovel-plan/SKILL.md` | 章节模板增加5字段（读者情绪/氛围/场景预案/对话种子/视觉锚点/爽值预估/钩子强度）+ 情绪连续性/钩子交替/爽值阈值3项检查 |
| `skills/webnovel-write/SKILL.md` | Context Agent增加4项额外输入（伏笔/道具/节拍表/语音规则）+ beat标准输出 + 开篇黄金协议(Ch1-3) |
| `skills/webnovel-write/references/step-3.5-external-review.md` | 增加DIALOGUE_FLAT issue type + Ch1-3开篇特殊审查prompt |
| `skills/webnovel-write/references/polish-guide.md` | 新增对话辨识度终检 + 网文模板套路检测(7类) + 具象化终检 |
| `skills/webnovel-write/references/style-adapter.md` | 新增具象化规则(Hard) + 钩子强度交替规则 |
| `references/checker-output-schema.md` | high-point-checker metrics增加cool_value(爽值公式) |

**核心改进清单：**
1. Init自动填充设定集（不再生成空模板）+ 语音规则段落
2. 大纲增加5新字段（场景预案/对话种子/氛围/视觉锚点/读者情绪）
3. Context Agent读伏笔追踪+道具+节拍表 + beat标准化输出
4. 开篇黄金协议（Ch1-3特殊高标准审查）
5. 对话辨识度检查（DIALOGUE_FLAT）
6. 反模板检测（7类网文毒点）
7. 角色语音规则（3-5条具体规则/角色）
8. 爽值公式化评估（压抑×反转÷逻辑漏洞）
9. 具象化规则（抽象→数字，每千字≥3锚点）
10. 读者情绪连续性检查
11. 钩子强度交替规则（1强2缓）

---

## [2026-03-29] Search Tool 全环节集成

**改动文件：**
| 文件 | 改动 |
|------|------|
| `skills/webnovel-write/SKILL.md` | frontmatter 加 WebSearch WebFetch + Search规则段落（触发条件+各Step搜索内容+失败即停协议+调研笔记归档） |
| `skills/webnovel-plan/SKILL.md` | frontmatter 加 WebSearch WebFetch + 新增 Step 2.5 卷前调研（必做） + Step 4 search触发 |
| `skills/webnovel-init/SKILL.md` | 新增 Search 使用规则段落（各Step具体搜索内容+高频要求） + 验证标准增加调研笔记目录 |
| `agents/data-agent.md` | Step K 增加调研笔记归档（WebSearch结果保存到调研笔记/主题文件） |
| `skills/webnovel-write/references/step-3-review-gate.md` | 同步推送fork（时间线闸门修改） |

**核心机制：**
1. WebSearch 在 init/plan/write 三个环节全部启用
2. Search 失败处理协议：失败即停→要求用户配置Tavily/Brave MCP→不跳过
3. 卷前调研会（Step 2.5）：每卷规划前集中搜索专业领域+爆款+场景技巧
4. 调研笔记归档：搜索结果按主题保存到 `调研笔记/` 目录，跨章复用
5. init 阶段高频搜索：每 Step 至少1次，关键 Step 2-3次

**SKILL.md 改动点（合并时注意）：**
- webnovel-write: frontmatter + Step 0.5后插入Search规则段落（在Step 1之前）
- webnovel-plan: frontmatter(新增行) + Step 2和3之间插入Step 2.5 + Step 4 beat前加search触发
- webnovel-init: Step 1前插入Search规则段落 + 验证脚本增加调研笔记目录检查

---

## [2026-03-29] Marketplace fork 与插件 cache(5.5.4) 技能文件对齐

**原因：** Cursor/Claude 实际加载的是 `plugins/cache/.../5.5.4/`；marketplace 里的 fork 副本曾落后（例如 `step-3-review-gate.md` 仍为 auto 路由、缺少 `agents/external-review-agent.md`）。

**操作：** 将以下文件从 cache **覆盖同步**到 `webnovel-writer/` fork 目录，使内容与运行时一致：

- `skills/webnovel-write/SKILL.md`
- `skills/webnovel-plan/SKILL.md`
- `skills/webnovel-init/SKILL.md`
- `skills/webnovel-write/references/step-3.5-external-review.md`
- `skills/webnovel-write/references/polish-guide.md`
- `skills/webnovel-write/references/style-adapter.md`
- `skills/webnovel-write/references/step-3-review-gate.md`
- `references/checker-output-schema.md`
- `agents/data-agent.md`
- `agents/external-review-agent.md`（fork 侧新增）

**说明：** `scripts/external_review.py` 仍以 fork 为准（上游 cache 5.5.4 包内无此文件）。

---

## [2026-03-30] Claude Code 与 Cursor 完全对齐

**背景：** 调查发现 Claude Code 的技能/脚本/配置与 Cursor 存在多处不一致，导致两个环境下写作流程不完全相同。

**修复清单：**

| 修复项 | 文件 | 说明 |
|--------|------|------|
| SKILL.md Step 3 仍为 auto 路由 | `skills/webnovel-write/SKILL.md` | 改为"全量审查"，6个 checker 始终执行，与 step-3-review-gate.md 一致 |
| ~/.claude/.env 缺少 HEALWRAP 密钥 | `~/.claude/webnovel-writer/.env` | 添加 HEALWRAP_BASE_URL + HEALWRAP_API_KEY + SILICONFLOW_BASE_URL，三级 fallback 完整 |
| external_review.py 只支持 codexcc 双级 | `scripts/external_review.py` | 全面重写：healwrap 主力 + codexcc 备用 + siliconflow 兜底；6模型并发(max_workers=6)；路由验证；provider_chain/api_meta/cross_validation 输出 |
| external_review.py 不在 cache 中 | cache `scripts/external_review.py` | 复制到 cache，否则 Claude Code SCRIPTS_DIR 找不到脚本 |
| Claude Code memory 过时 | `project_step3.5_external_review.md` | 从"3模型+codexcc主力"更新为"6模型+healwrap主力+三级fallback" |

**external_review.py 主要变更：**
- PROVIDERS 新增 healwrap（主力）
- MODELS 从3个扩展到6个（3核心+3补充），支持 tier 分层和多供应商链
- 新增 `verify_routing()` 函数：检查 response.model 是否匹配，含已知 codexcc 路由 bug 检测
- `call_api()` 返回 model_actual/usage/provider_chain
- `try_provider_chain()` 替代旧 `try_provider()`：按供应商链顺序尝试，路由失败自动切下一个
- 输出 JSON 新增 routing_verified/provider_chain/api_meta/cross_validation 字段
- max_workers 从 3 改为 6
- load_api_keys() 增加项目 .env 优先读取

**验证：** Python 语法检查通过，Tavily MCP 可用，所有 skill 文件 cache↔fork 一致。

---

## [2026-03-30] Step 3 审查维度从6个扩展到8个（新增对话质量+信息密度）

**改动文件：**
| 文件 | 类型 | 说明 |
|------|------|------|
| `references/checker-output-schema.md` | 修改 | 新增 dialogue-checker 和 density-checker 的 metrics schema + 汇总示例更新 |
| `skills/webnovel-write/references/step-3-review-gate.md` | 修改 | 审查器列表从6个扩展到8个，Task调用模板更新，模式说明更新 |
| `skills/webnovel-write/references/step-3.5-external-review.md` | 修改 | 外审prompt从6维度改为8维度，新增5个issue type，报告格式改为8维矩阵 |
| `skills/webnovel-write/SKILL.md` | 修改 | checker列表/模式说明/dimension_scores/闸门条件/报告描述全部从6维更新为8维 |

**对应 workspace 规则文件（非插件文件，不受上游合并影响）：**
| 文件 | 说明 |
|------|------|
| `.cursor/rules/external-review-spec.mdc` | 外审prompt 8维度 + 审查报告8维矩阵模板 + 新增issue type |
| `.cursor/rules/webnovel-workflow.mdc` | 审查子代理从6个改为8个 + 外审8维度描述 |

**背景：**
- 基于专业编辑评估框架、网文读者弃书原因分析、AI写作痕迹研究的综合调研
- 现有6维度在"正确性"（设定/连贯/OOC）和"网文特色"（追读力/爽点/节奏）方面完善
- 但在"表达质量"方面存在空白：对话质量和信息密度是网文读者最高频的差评维度

**新增维度说明：**

dialogue-checker（对话质量）：
- 检测说明书对话（info-dump）、声音辨识度、潜台词层次、对话节奏
- 指标：dialogue_ratio, info_dump_lines, subtext_instances, distinguishable_voices, indistinguishable_pairs, intent_types, longest_monologue_chars, dialogue_advances_plot

density-checker（信息密度）：
- 检测水分填充、重复表达、无效段落、过长无推进跨度
- 指标：effective_word_ratio, filler_paragraphs, repeat_segments, info_per_paragraph_avg, dead_paragraphs, longest_no_progress_span, inner_monologue_ratio, redundant_descriptions

**新增 issue type：**
- DIALOGUE_INFODUMP: 角色对话只为向读者传递设定信息
- DIALOGUE_MONOLOGUE: 单人连续独白过长
- PADDING: 段落无信息增量，属于水分填充
- REPETITION: 同一信息重复描述

**SKILL.md 具体改动点（合并时注意）：**
1. 审查器列表：新增 dialogue-checker 和 density-checker 两行
2. 模式说明：标准/--fast 从"6个"改为"8个"
3. dimension_scores 示例：新增"对话质量"和"信息密度"两个键
4. Step 3.5 报告描述：从"6模型评分矩阵"改为"6模型×8维度评分矩阵"
5. 章节间闸门：内部checker从6个改为8个，报告从6维改为8维

**架构变更：**
```
旧：Step 3(6 checker) + Step 3.5(6模型×6维度) = 42份报告
新：Step 3(8 checker) + Step 3.5(6模型×8维度) = 56份报告
```

---

<!-- 新的改动记录追加在此线下方 -->
