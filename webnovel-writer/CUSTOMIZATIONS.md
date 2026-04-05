# Webnovel-Writer Customizations Log

> Fork: https://github.com/XuanRanL/webnovel-writer
> Upstream: https://github.com/lingfengQAQ/webnovel-writer
> This file tracks all custom modifications made to this fork.
> When merging upstream updates, use this file to verify no customizations are lost.

---

## [2026-04-05] Step 6 审计闸门（7层约70检查项 + Step 7 Git）

**动机**：Ch1 事故暴露 Step 3 审查是"自审自证"——checker 评它自己读的章节，无法检测 subagent fallback、checker 坍缩、Step K 静默跳过、钩子虚标等跨步骤问题。新增 Step 6 审计闸门作为"他审他证"，独立审视 Step 1-5 的执行痕迹与所有产物之间的一致性。目标：写最高质量、让真实读者留下来的小说。

**新增组件**：
- 新 Step 6「Audit Gate」：audit-agent 七层审计（Layer A 过程真实性 / B 跨产物一致性 / C 读者体验 / D 作品连续性 / E 创作工艺 / F 题材兑现 / G 跨章趋势），约 70 个检查项
- 原 Step 6「Git 备份」改为 Step 7
- 混合执行模型：Part 1 CLI 快速结构审计（Layer A/B/G，< 5s）+ Part 2 audit-agent 深度判断（Layer C/D/E/F，60-300s）
- 闭环质量反馈：`.webnovel/editor_notes/ch{NNNN+1}_prep.md` 由 audit-agent 写入，下章 context-agent 必读

**新增文件**：
- `agents/audit-agent.md`（子代理规范）
- `skills/webnovel-write/references/step-6-audit-gate.md`（Part1+Part2 时序、决议规则、产物约定、失败恢复路径）
- `skills/webnovel-write/references/step-6-audit-matrix.md`（7 层 × ~70 检查项矩阵）
- `scripts/data_modules/chapter_audit.py`（Layer A/B/G 确定性 CLI）
- `scripts/data_modules/tests/test_chapter_audit.py`（24 单元测试）
- `scripts/data_modules/tests/test_webnovel_audit_cli.py`（5 CLI 集成测试）

**修改文件**：
- `scripts/data_modules/webnovel.py`：新增 `audit` 子命令，转发到 `chapter_audit`
- `scripts/workflow_manager.py`：
  - `expected_step_owner`: Step 6 owner = audit-agent, 新增 Step 7 owner = backup-agent
  - `get_pending_steps`: `[..., 'Step 5', 'Step 6', 'Step 7']`
  - `get_recovery_options`: Step 5 reference 改为 Step 6 Audit Gate；Step 6 recovery 改为"按 blocking_issues 修复 / 重跑 audit-agent / 强制跳过（高风险）"；新增 Step 7 Git 恢复选项
- `skills/webnovel-write/SKILL.md`：
  - 章节间闸门新增 `audit_reports/ch{NNNN}.json` 存在 + `audit check-decision` 通过
  - `--step-id` 白名单追加 Step 7
  - 新增 Step 6（审计闸门）与 Step 7（Git 备份）完整章节
  - 充分性闸门条目扩展到 10 条
  - 验证与交付 bash 新增 audit 检查
  - 失败处理新增 Step 6 block / 超时恢复
  - References 新增 step-6-audit-gate.md 与 step-6-audit-matrix.md
- `agents/context-agent.md`：输入数据新增 `.webnovel/editor_notes/ch{NNNN}_prep.md`（第 2 章起必读，形成跨章闭环）
- `agents/data-agent.md`：Step J 输出 schema 新增 `step_k_status`（含 executed / outcome / applied_additions / proposed_additions / skipped_reasons），供 Step 6 Layer B5/B6 对账

**硬约束**：
- Step 6 Part1 与 Part2 必须全部完成才能判定；Part1 fail 时 Part2 仍执行（给完整诊断）
- `decision == block` 禁止进入 Step 7；必须按 `blocking_issues[].remediation` 修复后重跑
- audit-agent 只读不写（除审计产物 audit_reports / editor_notes / observability/chapter_audit.jsonl）
- 时间预算 300s 硬上限；超时视为"审计未完成"block
- `--minimal` 模式跳过 Layer A3 9 外部模型 / Layer G 跨章趋势 / editor_notes 写入

**测试结果**：
- 新增 29 个测试（24 unit + 5 integration）全部通过
- 不影响现有 `test_workflow_manager.py`（9 passed）与 `test_webnovel_unified_cli.py`（5 passed）
- 9 个 pre-existing CLI test 失败与本次改动无关（tmp_path 下缺少 `.webnovel/state.json` 的项目定位器问题）

**审计触发命令**：
```bash
# Part 1 CLI 快速审计
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" \
  audit chapter --chapter {N} --mode standard \
  --out "${PROJECT_ROOT}/.webnovel/tmp/audit_layer_abg_ch{NNNN}.json"

# Part 2 audit-agent 深度审计
Task(audit-agent, {chapter: N, project_root, mode, chapter_file, time_budget_seconds: 300})

# 章节间闸门验证
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" \
  audit check-decision --chapter {N} --require approve,approve_with_warnings
```

---

## [2026-04-05] 插件 subagent_type 注册修复（workspace 级 .claude/agents/ 兜底）

**症状**：在 Claude Code 会话里调用 `Agent(subagent_type="context-agent"/"data-agent"/"*-checker")` 报错
`Agent type 'context-agent' not found. Available agents: general-purpose, statusline-setup, Explore, Plan, claude-code-guide`。

**根因链（按发现顺序）**：
1. **插件被 disable**：`claude plugin list` 显示 `webnovel-writer@webnovel-writer-marketplace Status: ✘ disabled`
   —— 某次会话里插件被禁用后未重新启用，所有 plugin-scope agents 停止加载。
2. **cache 版本落后 local fork**：installed cache `5.5.4` 只含 11 个 agent，缺 `emotion-checker.md` 和 `prose-quality-checker.md`
   （这两个是 fork 里后加的），所以即便启用也拿不到最新的 10 维 checker 全家桶。
3. **subagent 需要会话重启才生效**：官方文档明示
   "Subagents are loaded at session start. If you create a subagent by manually adding a file, restart your session or use `/agents` to load it immediately."
   —— 这意味着启用插件/创建新 agent 后，**本会话仍不可用**，必须新开会话。

**修复（三层）**：
1. **启用插件**：`claude plugin enable webnovel-writer@webnovel-writer-marketplace`
2. **workspace 级 standalone 兜底**：将 fork 里的 13 个 agent 复制到 `I:/AI-extention/webnovel-writer/.claude/agents/`
   —— 项目 scope 优先级高于 plugin scope（3 > 5），从任一书项目子目录 cwd 向上搜索都能命中
   —— 避免对 cache 同步的依赖，local fork 改动立即生效（下次会话）
3. **路径修正**：将 standalone 副本里的 `${CLAUDE_PLUGIN_ROOT}` 替换为 fork 绝对路径
   `I:/AI-extention/webnovel-writer/webnovel-writer`，因为 standalone subagent 运行时无 `CLAUDE_PLUGIN_ROOT` env。

**修改位置**：
| 位置 | 内容 |
|------|------|
| plugin 启用状态 | disabled → enabled（user scope） |
| `I:/AI-extention/webnovel-writer/.claude/agents/*.md` | 新增 13 个文件（workspace 级 standalone fallback） |
| 上述文件内的 `${CLAUDE_PLUGIN_ROOT}` | 全部替换为 fork 绝对路径 |

**启用后的 subagent 优先级**（官方文档 `/en/sub-agents`）：
1. Managed settings（组织级）
2. `--agents` CLI flag（会话级）
3. **`.claude/agents/`（项目级）← 本次兜底落点**
4. `~/.claude/agents/`（用户级）
5. **Plugin's `agents/` directory（插件级）← 原始来源**

同名 agent 项目级覆盖插件级，因此 workspace fallback 与插件可共存，以 fork 的最新版本为准。

**验收路径**（下次会话）：
```
/agents                                     # 确认列表中出现 context-agent/data-agent/*-checker
Agent(subagent_type="context-agent",        # 调用时不再报 "not found"
      prompt="...")
```

**对比：上一次会话（Ch1 写作）**：
- 当时因本问题 fallback 到 `general-purpose` + 嵌入 agent.md 全文的方式执行
- 产出质量未受影响（Ch1 combined=93, 16/16 硬约束），但上下文成本高、无工具隔离
- 本次修复后，下次会话可直接 `subagent_type="context-agent"`，节约 token 并获得 agent 的 `tools: Read, Grep, Bash` 隔离

---

## [2026-04-03] 幽灵零分修复 + 补充模型 fallback 链

**问题1**：模型返回合法JSON但内容为空（`score:0, summary:""`），被视为有效评分。

**修复（双层防御）**：
1. **Provider 层**（`try_provider_chain`）：score=0+空摘要 → 记录 `phantom_score0_retry` → 自动尝试下一供应商
2. **Model 层**（`_run_single_model`）：所有供应商都返回 phantom → 标记 `status:"failed"`，不计入均分

**问题2**：补充模型只有 1-2 个供应商，失败后无处可退。

**修复**：给所有补充模型增加多供应商 fallback 链：
- qwen-3.5: healwrap → siliconflow
- deepseek-v3.2: healwrap → siliconflow
- minimax-m2.5: nextapi → healwrap → codexcc → siliconflow
- minimax-m2.7: nextapi → healwrap → codexcc
- glm-4.7: healwrap → siliconflow
- doubao-seed-2.0: healwrap only（其他供应商无此模型）

**效果**：90/90 维度 100% 成功率（之前 79/90 = 87.8%），8 次 phantom 自动重试全部恢复。

**修改文件：**
| 文件 | 修改内容 |
|------|---------|
| `scripts/external_review.py` | MODELS 补充模型 providers 扩展; `try_provider_chain` phantom 检测+重试; `_run_single_model` phantom 二级拦截 |

---

## [2026-04-03] nextapi 供应商集成 + 9模型架构 + 早停修复

**架构变更：**
- 新增 nextapi 供应商（`https://api.nextapi.store/v1`，RPM=999 无限制）作为主力，支持 kimi/glm/minimax/minimax-m2.7
- 四级 fallback：nextapi → healwrap → codexcc → 硅基流动
- 新增模型 minimax-m2.7（对话/情感深度），总计 9 模型（3核心+6补充）
- healwrap 压力从 90 请求/章降至约 50 请求/章（4模型走 nextapi）

**代码修复：**
1. **ProviderRateLimiter 竞态条件**：重构 `acquire()` 为 `_try_acquire()` 模式，消除锁外变量使用
2. **早停机制失效**：`max_concurrent=10` 时全部 future 立即启动，`cancel()` 无效。修复：补充层维度并发降至3 + `threading.Event` 信号 + 累计失败替代连续失败
3. **nextapi 路由验证**：`glm-5.0` → `glm-5` 版本号归一化匹配

**修改文件：**
| 文件 | 修改内容 |
|------|---------|
| `scripts/external_review.py` | PROVIDERS+MODELS 新增 nextapi/minimax-m2.7；RateLimiter 重构；早停修复；路由 `.0` 归一化 |
| `skills/webnovel-write/SKILL.md` | 8模型→9模型，fallback 链更新，调用命令去掉 `--max-concurrent 1` |
| `skills/webnovel-write/references/step-3.5-external-review.md` | 全面重写：九模型双层架构表、四级 fallback、nextapi 描述、早停机制说明 |
| `.env` | 新增 NEXTAPI_BASE_URL / NEXTAPI_API_KEY |

---

## [2026-04-03] external_review.py 稳定性修复 + --model-key all 模式

**修复的问题：**
1. **连接池中毒**：`call_api()` 中 `requests.post()` 共享 urllib3 连接池，ConnectionResetError(10054) 后连接池被污染导致后续调用全部秒失败。改用显式 `requests.Session()`，连接错误后关闭重建。
2. **error=success bug**：`call_dimension()` 中 API 返回 success 但 JSON 解析失败时，error 标识错误地显示 "success"。现改为 "json_parse_failed"。
3. **模型遗漏**：Agent 手动逐个调用模型时遗漏 doubao/glm4（Ch30-35 除 Ch34 外全部遗漏）。新增 `--model-key all` 模式，脚本自动遍历全部 8 个模型。
4. **补充层无效重试**：minimax 连接断开后 21 次无意义重试。新增早停机制——补充层连续 3 个维度失败后跳过剩余维度。

**修改文件：**
| 文件 | 修改内容 |
|------|---------|
| `scripts/external_review.py` | Session 重建、error=success 修复、`--model-key all` 模式、补充层早停 |
| `skills/webnovel-write/SKILL.md` | Step 3.5 调用命令改为 `--model-key all`，添加参数说明 |
| `skills/webnovel-write/references/step-3.5-external-review.md` | 推荐调用策略更新、调用命令示例、参数白名单、早停说明 |

---

## [2026-04-03] 默认字数目标调整 2100-3200 → 2200-3500

**改动文件：**
| 文件 | 类型 | 说明 |
|------|------|------|
| `skills/webnovel-write/SKILL.md` | 修改 | 第3行description + 第12行全局目标 + 第252行Step 2A硬要求，2100-3200→2200-3500 |
| `skills/webnovel-write/references/style-adapter.md` | 修改 | 第22行默认字数 + 第86行章节类型适配，2100-3200→2200-3500 |

**背景：**
- 用户要求上调上限至3500，下限微调至2200，适配更宽松的字数弹性

---

## [2026-04-02] Step 3.5 外部审查：6模型→8模型升级

**新增模型（2个补充层）**:
- `doubao-seed-2.0`（结构审查/逻辑一致性）：字节跳动 thinking 模型，256K 上下文，强推理+中文能力，healwrap only
- `glm-4.7`（文学质感/角色声音）：智谱 355B MoE thinking 模型，200K 上下文，强写作/角色扮演，healwrap only

**架构变更**:
- 核心层不变（3模型：kimi-k2.5/glm-5/qwen3.5-plus，三级 fallback）
- 补充层从3→5模型（+doubao-seed-2.0, +glm-4.7，均 healwrap only）
- thinking 模型检测新增 `doubao` 和 `glm-4` 模式匹配
- `DEFAULT_MAX_CONCURRENT` 已从 2 降为 1（避免 RPM 超限）

**修改文件**:
| 文件 | 修改内容 |
|------|---------|
| `scripts/external_review.py` | MODELS 字典新增 doubao/glm4 条目；thinking 检测扩展；docstring/argparse/注释更新 |
| `skills/webnovel-write/references/step-3.5-external-review.md` | 六模型→八模型架构；补充层表格+fallback规则+并发控制+报告模板更新 |
| `skills/webnovel-write/SKILL.md` | 章节间闸门/充分性闸门/Step 3.5 硬要求中 6模型→8模型 |

---

## [2026-04-02] 小说质量优化全面升级

**新增 Checker Agent（2个）**:
- `agents/prose-quality-checker.md`：文笔质感检查器，评估句式节奏、比喻新鲜度、感官丰富度、动词力度、画面感、具象化程度。使用新 issue type `PROSE_FLAT`
- `agents/emotion-checker.md`：情感表现检查器，评估 Show vs Tell、情感梯度、情感锚点、情感惯性、共鸣设计。使用新 issue type `EMOTION_SHALLOW`

**Schema 更新**:
- `references/checker-output-schema.md`：问题类型从11→13（+PROSE_FLAT, +EMOTION_SHALLOW），新增2个checker的metrics模板，汇总模板从8→10个checker

**审查流程更新**:
- `skills/webnovel-write/references/step-3-review-gate.md`：标准模式从8→10个checker
- `skills/webnovel-write/references/step-3.5-external-review.md`：外审维度从8→10（+文笔质感, +情感表现）
- `scripts/external_review.py`：新增2个维度的审查prompt
- `skills/webnovel-write/SKILL.md`：Chapter Gate 更新为10 checker，维度更新为10
- `skills/webnovel-review/SKILL.md`：Full depth 追加 prose-quality-checker 和 emotion-checker

**现有 Checker 增强**:
- `agents/ooc-checker.md`：+配角能动性检查（独立动机、反应vs主动、消失追踪、反派智商）
- `agents/reader-pull-checker.md`：+开篇吸引力检查（HARD-005开头进入速度、开头钩子、解释性开场检测、上章钩子回应速度）
- `agents/continuity-checker.md`：+伏笔回收质量评估、+章末过渡质量评估、+主题一致性轻量检查
- `agents/density-checker.md`：+跨章重复模式检测（开头模式、描写套路、情绪节奏重复）

**润色系统升级**:
- `skills/webnovel-write/references/polish-guide.md`：
  - 新增 PROSE_FLAT/EMOTION_SHALLOW 修复规则
  - Anti-AI 动作套话从"禁用"改为"频率限制"（每章≤2次/词）
  - 新增结构级 Anti-AI 检测（信息密度均匀度、情绪强度曲线、段落功能分布、句长方差）
  - 新增润色迭代收益递减判断（最多3轮，收益递减警告）

**工作流增强**:
- `skills/webnovel-write/references/step-1.5-contract.md`：+风险预估（预测Step 3弱项）、+读者认知追踪（reader_knows/expects/info_gap）
- `skills/webnovel-write/references/style-adapter.md`：+角色语音DNA（6维度语音特征约束）
- `agents/context-agent.md`：+质量反馈注入（近期高频问题规避、成功模式参考、范文锚定）
- `agents/data-agent.md`：+审查报告持久化、+实体状态交叉验证、+风格样本段落级采样（阈值降低）

**影响范围**: 18个文件（2个新建+16个修改），涵盖审查、润色、上下文、数据管线全流程

---

## [2026-04-01] 默认字数目标调整 3000-3500 → 2100-3200

**改动文件：**
| 文件 | 类型 | 说明 |
|------|------|------|
| `skills/webnovel-write/SKILL.md` | 修改 | 第3行description + 第12行全局目标 + 第252行Step 2A硬要求，3000-3500→2100-3200 |
| `skills/webnovel-write/references/style-adapter.md` | 修改 | 第22行默认字数 + 第74行章节类型适配，3000-3500→2100-3200 |

**背景：**
- 用户要求下调字数区间，扩大弹性范围（下限2100，上限3200），适配不同章节节奏需求

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

## [2026-03-30] Step 3.5 外部审查 build_context_block 输入数据补全

**改动文件：**
| 文件 | 类型 | 说明 |
|------|------|------|
| `scripts/external_review.py` | 修改 | 重写 `build_context_block` 函数，新增3个辅助函数，修复输入数据不完整问题 |

**背景：**
- Ch28 8维度测试发现：外部审查模型收到的上下文严重缺失
- `external_context_ch0028.json` 缺少女主卡、反派设计、金手指设计等关键字段
- 旧 `build_context_block` 完全依赖 context JSON，JSON 缺字段则审查模型无法获取对应设定
- 导致模型在"设定一致性"维度可能误判（无参照物）

**修复方案：**
- 新增 `_read_setting_file(project_root, filename)`：直接从 `设定集/` 目录读取设定文件
- 新增 `_load_state_json(project_root)`：从 `state.json` 读取主角状态和进度
- 新增 `_load_prev_summaries(project_root, chapter_num)`：读取前2章摘要
- 重写 `build_context_block(context_data, project_root, chapter_num)`：
  - 每个上下文字段先查 context JSON，缺失则 fallback 到磁盘文件
  - 覆盖7大上下文块：本章大纲/主角设定(主角卡+金手指)/配角设定(女主卡+反派)/力量体系/世界观/前2章摘要/主角当前状态
  - 主角状态剔除 credits 字段（避免泄露精确经济数值给审查模型）
  - 新增进度信息块
- 调用处传入 `project_root` 和 `chapter_num` 参数

**验证：** 12/12 结构检查 + 7/7 内容检查全部通过，三份副本（cache/fork/marketplace）MD5 一致。

---

## [2026-03-30] 8维度全面落地 + 爽点密度加强 + 交叉验证实现

**改动文件：**
| 文件 | 类型 | 说明 |
|------|------|------|
| `scripts/external_review.py` | 修改 | DIMENSIONS 从6→8维度（新增 dialogue_quality + information_density），pass 阈值 60→75，实现真正的 cross_validation 逻辑，动态化所有硬编码数字 |
| `agents/dialogue-checker.md` | **新增** | 对话质量审查 agent（辨识度/意图层次/信息倾倒/独白控制），8 个 metrics 字段 |
| `agents/density-checker.md` | **新增** | 信息密度审查 agent（有效字数比/填充段/重复段/死段落/推进跨度），8 个 metrics 字段 |
| `scripts/workflow_manager.py` | 修改 | 移除 expected_step_owner 中残留的 Step 1.5 映射 |
| `skills/webnovel-write/references/polish-guide.md` | 修改 | 章节重编号(8/9/10)消除重复，新增 §11 爽点密度补种机制 |
| `skills/webnovel-write/references/step-1.5-contract.md` | 修改 | 追读力设计新增"爽点规划"必填子字段（类型/铺垫来源/兑现方式） |
| `skills/webnovel-write/SKILL.md` | 修改 | Step 2A 新增"爽点密度约束"硬规则（每800字至少1微爽点） |

**背景：**
- 2026-03-30 的 8 维度升级更新了所有规范文件但遗漏了实际执行脚本 `external_review.py`
- DIMENSIONS 字典仍为 6 维，缺少 dialogue_quality 和 information_density
- dialogue-checker.md 和 density-checker.md agent 定义文件未创建，导致 Step 3 内部审查无法执行这两个 checker
- cross_validation 是空壳（verified/dismissed 永远为 0）
- pass 阈值 60 与规范的 75 分不合格线矛盾
- 爽点密度 avg 61.1 是质量最弱维度，缺乏系统性加强机制

**P0 修复（严重）：**
1. `external_review.py` DIMENSIONS 字典添加 `dialogue_quality` 和 `information_density` 两个完整条目
2. `dialogue-checker.md` 191 行完整 agent 定义（遮名辨识度测试/意图层次/信息倾倒/独白控制/推进检查）
3. `density-checker.md` 231 行完整 agent 定义（有效字数比/填充段/重复段/死段落/推进跨度/内心独白/冗余描写）

**P1 修复（中等）：**
4. pass 阈值 `overall >= 60` → `overall >= 75`（与规范对齐）
5. `_compute_cross_validation()` 真实实现：按 issue_type + location 分组，≥2 个维度标记同类问题 = verified
6. `polish-guide.md` 重编号：§6.对话辨识度→§8，§7.模板套路→§9，§8.具象化→§10

**P2 修复（轻微）：**
7. `workflow_manager.py` 移除 `expected_step_owner` 中的 `"Step 1.5"` 残留映射

**P3 增强（爽点密度专项）：**
8. `step-1.5-contract.md` 追读力设计新增"爽点规划"必填字段：类型 + 铺垫来源 + 兑现方式 + 过渡章微兑现
9. `SKILL.md` Step 2A 新增硬约束：每 800 字至少 1 微爽点，铺垫章降至 1200 字/个，全章不得为零
10. `polish-guide.md` 新增 §11 爽点密度补种：high-point-checker < 70 时强制在薄弱区间插入微爽点

**动态化改动（external_review.py）：**
- `max_workers=6` → `max_workers=len(DIMENSIONS)`
- `"6维度审查完成"` → `f"{len(DIMENSIONS)}维度审查完成"`
- docstring `"6 separate dimension prompts"` → `"8 separate dimension prompts"`
- cross_validation 字段从硬编码 stub → 调用 `_compute_cross_validation(all_issues)`

**架构变更：**
```
旧：Step 3(8 checker, 但 dialogue/density 无 agent 文件→实际只执行6个) + Step 3.5(6模型×6维度) = 42份报告
新：Step 3(8 checker, 全部有 agent 文件→真正执行8个) + Step 3.5(6模型×8维度) = 56份报告
```

**验证：**
- Python ast.parse: SYNTAX OK
- DIMENSIONS count: 8/8 ✅
- 所有 dimension 条目含 name/system/prompt + 正确占位符 ✅
- cross_validation 5 项单元测试全部通过 ✅
- pass threshold = 75 ✅
- max_workers/summary 动态化 ✅
- 两个新 agent 文件存在且格式正确 ✅
- workflow_manager Step 1.5 已移除 ✅
- polish-guide 章节编号无重复 ✅
- SKILL.md 爽点密度约束已添加 ✅

---

<!-- 新的改动记录追加在此线下方 -->

## [2026-03-30] Step 0-6 全流程审计修复（22项bug）

**改动文件：**
| 文件 | 类型 | 说明 |
|------|------|------|
| `skills/webnovel-write/SKILL.md` | 修改 | BUG-01/02/03 + CROSS-03/04 修复 |
| `skills/webnovel-write/references/polish-guide.md` | 修改 | BUG-20 + BUG-14/21 + CROSS-02 修复 |
| `skills/webnovel-write/references/step-3-review-gate.md` | 修改 | BUG-08/15 + CROSS-03 修复 |
| `skills/webnovel-write/references/step-3.5-external-review.md` | 修改 | BUG-20 + CROSS-02 修复 |
| `skills/webnovel-write/references/step-5-debt-switch.md` | 修改 | BUG-26 修复 |
| `skills/webnovel-plan/SKILL.md` | 修改 | BUG-20 修复 |
| `agents/data-agent.md` | 修改 | DATA-1/2/3 修复 |

**修复清单：**

🔴 Critical:
- **BUG-20**: 移除 polish-guide.md §8 + step-3.5-external-review.md + webnovel-plan/SKILL.md 中的硬编码角色名(陆衍/老周/沈映雪/刘疤/韩远)，替换为通用描述
- **CROSS-02**: 统一三套不兼容的 issue type 系统——polish-guide.md 新增11个type的修复规则 + type映射表（内部↔外部）
- **BUG-14/21**: polish-guide.md 新增5个缺失type的修复动作（DIALOGUE_FLAT/INFODUMP/MONOLOGUE/PADDING/REPETITION）
- **BUG-10/11**: 确认 TIMELINE_ISSUE 由 consistency-checker 产出（非phantom），在映射表中关联 CONTINUITY type
- **DATA-1**: 修复 chapter_meta 双层嵌套——data-agent.md 输出规范改为扁平对象（不含章节号外层键）
- **DATA-2**: data-agent.md Step K 伏笔追踪新增 state.json 同步写入（`--add-foreshadowing` / `--resolve-foreshadowing`）

🟠 High:
- **BUG-01**: `--step-id` 允许列表新增 `Step 3.5`
- **BUG-02**: 验证命令和Chapter Gate改为 glob 匹配，支持带标题/无标题两种文件名
- **BUG-03**: report_file 示例从范围格式 `第100-100章` 改为单章格式 `第0100章`
- **BUG-08/15**: step-3-review-gate.md 新增数字及格线（≥75合格）和4级评分阈值规则
- **BUG-26**: step-5-debt-switch.md python 命令添加 `-X utf8` 标志
- **CROSS-03**: 定义内外部分数合并算法（internal×0.6 + external_avg×0.4），写入 step-3-review-gate.md 和 SKILL.md
- **CROSS-04**: 充分性闸门与章节间闸门条件同步（充分性闸门新增3.5/报告/Git条件；章节闸门新增anti_ai_force_check条件）
- **DATA-3**: 修正 data-agent.md Step D 写入内容说明——明确 strand_tracker 需额外 CLI 调用，protagonist_state.power 依赖 SQLite 实体数据

**已确认无需修复：**
- BUG-05: style-adapter.md 字数引用已在上次更新中修正 ✅
- BUG-12: checker-output-schema.md 已包含全部8个checker ✅
- BUG-17: data-agent.md Step K 已有完整定义 ✅

**已知限制（暂不修改）：**
- DATA-3: world_settings 无自动化写入路径（init后永远为空骨架）——实际无消费者，设定数据存于 `设定集/*.md`

---

## [2026-03-31] Python 代码修复：外审上下文大幅补全 + 窗口对齐

**改动文件：**
| 文件 | 类型 | 说明 |
|------|------|------|
| `scripts/external_review.py` | 修改 | BUG-22 + DATA-4：build_context_block 补全3个上下文块 + 前章从摘要改为全文 + 窗口2→3 |
| `scripts/extract_chapter_context.py` | 修改 | DATA-4：上下文窗口从硬编码2改为3，对齐 ContextManager |
| `agents/external-review-agent.md` | 修改 | 前章摘要→前章正文，窗口2→3 |
| `skills/webnovel-write/references/step-3.5-external-review.md` | 修改 | user 消息模板、上下文加载规则、token 估算全部更新 |

**BUG-22 修复（external_review.py 上下文补全）：**
1. `_load_state_json()` 重写：从只返回 protagonist_state+progress 扩展为同时返回 recent_chapter_meta(最近3章)、foreshadowing(活跃伏笔)、strand_history(最近5条节奏)
2. `build_context_block()` 新增3个上下文块：
   - 【近期章节模式】：从 chapter_meta 提取钩子类型/强度、开场方式、情绪节奏（供 reader_pull/high_point 维度判断重复）
   - 【活跃伏笔线】：从 plot_threads.foreshadowing 提取未兑现伏笔链（供 continuity 维度判断遗忘）
   - 【节奏历史】：从 strand_tracker.history 提取 dominant strand（供 pacing 维度判断差异化）
3. 前章上下文从**摘要**升级为**全文**：`_load_prev_summaries()` → `_load_prev_chapters()`，优先读 `正文/` 目录完整章节，缺失时退化为 `summaries/` 摘要

**DATA-4 修复（上下文窗口对齐）：**
1. `extract_chapter_context.py:325`：`chapter_num - 2` → `chapter_num - summary_window`（summary_window=3）
2. `external_review.py:470`：`_load_prev_chapters()` 默认 window=3
3. 与 `ContextManager.context_recent_summaries_window=3` 对齐

**上下文总量变化：**
```
旧：~12000 字（设定集 7500 + 前2章摘要 300 + 状态 1200 + 本章正文 3000）
新：~21000 字（设定集 7500 + 前3章正文 9000 + 状态/伏笔/节奏 1500 + 本章正文 3000）
```
对 32K+ 模型无压力

---

## [2026-03-31] Step 3.5 外审流程 CRITICAL/HIGH bug 修复（9项）

**改动文件：**
| 文件 | 类型 | 说明 |
|------|------|------|
| `scripts/external_review.py` | 修改 | BUG-C1/C2 + H3/H4/H5/H6/H7 + dimension_reports 格式修复 |
| `agents/external-review-agent.md` | 修改 | 移除 --context-file、对齐 context JSON keys、更新 dimension_reports 示例 |
| `skills/webnovel-write/references/step-3.5-external-review.md` | 修改 | dimension_reports 示例对齐代码实际输出 |

**CRITICAL 修复：**
1. **BUG-C1**: agent spec 中 `--context-file` CLI 参数不存在于 argparse → 移除（脚本内部从 --project-root + --chapter 自动构建路径）
2. **BUG-C2**: agent 写入 `prev_summaries` key，脚本读取 `prev_chapters_text` key → 脚本改为同时接受两个 key（`prev_chapters_text || prev_summaries`）；agent spec JSON 模板更新为9个完整字段

**HIGH 修复：**
3. **H3**: `routing_verified: all([]) == True` 当所有维度失败时误报 → 加 `if ok_results else False` 守卫
4. **H4**: `model_actual` 取自 `list(results.keys())[0]`，因 as_completed 非确定性 → 改为 `sorted(ok_dims)[0]` 确定性选取
5. **H5**: Ch1-3 开篇章节特殊审查 prompt 未实现 → 新增 `CH1_3_SPECIAL_PROMPT`，`chapter_num <= 3` 时追加5项额外评估标准
6. **H6**: `verify_routing()` 只有黑名单检查（已知 codexcc bug），无正向匹配 → 新增正向匹配逻辑（请求模型名 ⊂ 响应模型名，key_match fallback）
7. **H7**: `data.get("key", {})` 当 JSON 值为 null 时返回 None 而非 {} → 全部改为 `data.get("key") or {}` 模式（影响 _load_state_json + build_context_block 共11处）

**MEDIUM 修复：**
8. **dimension_reports 格式**: 代码输出 dict（keyed by dim_key），spec 文档要求 array → 改为 sorted array，每项添加 `dimension` 和 `name` 字段
9. **agent spec context JSON 模板**: 补全9个字段（新增 golden_finger_card/female_lead_card/villain_design），与 build_context_block 实际读取的 key 完全对齐

**verify_routing() 升级逻辑：**
```
旧：仅检查黑名单（codexcc GLM→MiniMax / kimi→qianfan）→ 其他一律 True
新：
  Step 1: 黑名单检查（不变）
  Step 2: 正向匹配 — requested_model_id 的 base name ⊂ response_model（不区分大小写）
  Step 3: key_match fallback — model_key ⊂ response_model
  Step 4: 全不匹配 → False + "no_positive_match" 原因
```

**验证：** Python ast.parse SYNTAX OK，9/9 自动化检查全部通过

---

## [2026-03-31] 8内部审查Agent全面规范化 + Schema补全（18项修复）

**改动文件：**
| 文件 | 类型 | 说明 |
|------|------|------|
| `references/checker-output-schema.md` | 修改 | 新增统一评分公式+问题类型枚举(11种)+内心独白权责划分+monotony_risk字段 |
| `agents/consistency-checker.md` | 修改 | 新增JSON输出+评分公式+canonical types映射+id/can_override+Ch1边界处理 |
| `agents/continuity-checker.md` | 修改 | 新增JSON输出+评分公式+canonical types映射+id/can_override+Ch1边界处理 |
| `agents/ooc-checker.md` | 修改 | 新增JSON输出+评分公式+canonical type(OOC)+id/can_override+移除硬编码角色名 |
| `agents/pacing-checker.md` | 修改 | 新增JSON输出+评分公式+canonical type(PACING)+id/can_override+Ch1边界+修复60%/70%阈值歧义+移除硬编码李雪 |
| `agents/reader-pull-checker.md` | 修改 | 新增schema引用+issues[]合并规则+populated issues示例 |
| `agents/high-point-checker.md` | 修改 | issues[]示例填充+cool_value检测规则+monotony_risk声明为扩展+id/can_override+评分公式 |
| `agents/dialogue-checker.md` | 修改 | id/can_override+评分公式+潜台词检测步骤(subtext_instances)+内心独白权责声明 |
| `agents/density-checker.md` | 修改 | id/can_override+评分公式+REPETITION type示例+内心独白权责声明 |

**Batch 1 — Schema Conformance (P0) 修复：**

1. **SYS-1**: checker-output-schema.md 新增"统一评分公式"章节：`max(0, 100 - sum(deductions))` with critical=25/high=15/medium=8/low=3，pass阈值=75
2. **SYS-2**: checker-output-schema.md 新增"问题类型枚举"章节：定义11个canonical types + 旧类型映射表(POWER_CONFLICT→SETTING_CONFLICT等6条)
3. **SYS-3**: consistency/continuity/pacing-checker 新增JSON输出模板（含populated issues[]示例）
4. **SYS-4**: 所有8个checker的issue示例添加 `id` 字段（格式：CONS_001/CONT_001/OOC_001/PACE_001/HP_001/DLG_001/DEN_001等）
5. **SYS-5**: 所有8个checker的issue示例添加 `can_override` 字段
6. **CK-4**: reader-pull-checker issues[]从永远空改为从hard_violations+soft_suggestions合并，新增合并规则说明

**Batch 2 — Quality & Edge Cases (P1-P2) 修复：**

7. **CK-5/CK-6**: high-point-checker 新增 cool_value 完整检测规则（三维度评估+计算公式）；monotony_risk 声明为checker私有扩展字段
8. **CK-7**: pacing-checker 三阈值歧义修复——明确注释区分60%(单章分类)/70%(10章窗口上限)/55-65%(理想比例)三者互补关系
9. **CK-8**: dialogue-checker 新增"第五步半: 潜台词检测"步骤——4条检测规则，赋予 subtext_instances 实际检测逻辑
10. **CK-9**: checker-output-schema.md 新增"内心独白检查权责划分"表格；dialogue-checker+density-checker各自声明权责（结构vs比例）
11. **硬编码角色名移除**: ooc-checker 林天→{主角名}、慕容雪→{女配名}、反派王少→{反派名}；pacing-checker 李雪→{配角}
12. **EDGE-1/2/3**: consistency/continuity/pacing-checker 新增Ch1边界处理说明（无前章/无state.json时的降级策略）

**issue type 映射总表：**
```
consistency-checker: POWER_CONFLICT/LOCATION_ERROR/CHARACTER_CONFLICT → SETTING_CONFLICT; TIMELINE_ISSUE → CONTINUITY
continuity-checker:  场景断裂/前后矛盾/因果缺失/大纲偏离/逻辑漏洞/伏笔遗忘 → CONTINUITY
ooc-checker:         所有OOC问题 → OOC
pacing-checker:      所有节奏问题 → PACING
reader-pull-checker: 所有追读力问题 → READER_PULL
high-point-checker:  密度/单调 → PACING; 铺垫/执行 → READER_PULL
dialogue-checker:    DIALOGUE_FLAT/DIALOGUE_INFODUMP/DIALOGUE_MONOLOGUE/PADDING
density-checker:     PADDING/REPETITION
```

---

## [2026-03-31] 全流程审查 Bug 修复（7处）

**改动文件：**
| 文件 | 类型 | 说明 |
|------|------|------|
| `agents/external-review-agent.md` | 修复 | 大纲路径硬编码"第1卷"→动态 `{volume_id}` |
| `skills/webnovel-write/references/step-3.5-external-review.md` | 修复 | User消息模板中大纲路径同上 |
| `references/checker-output-schema.md` | 修复 | cool_value 示例 score 62→28（匹配公式 8×7/max(1,11-9)=28） |
| `agents/high-point-checker.md` | 修复 | 同上 cool_value score 修正 |
| `skills/webnovel-plan/SKILL.md` | 修复 | 3处 PowerShell 语法→bash heredoc（Set-Content→cat >，Add-Content→cat >>） |

**Bug 1 — 硬编码卷号（2处）：**
- `external-review-agent.md` 第43行：`大纲/第1卷-详细大纲.md` → `大纲/第{volume_id}卷-详细大纲.md`
- `step-3.5-external-review.md` 第127行：同上，并补充 volume_id 来源说明（state.json → 总纲 fallback）
- **根因**: 最初编写时项目只有第1卷，未参考 context-agent.md / chapter_outline_loader.py 的动态模式

**Bug 2 — cool_value 公式/数值不一致（2处）：**
- `checker-output-schema.md` 和 `high-point-checker.md` 的 JSON 示例中 `score: 62` 但公式 `8×7/max(1,11-9)` = 28
- **根因**: 示例手写，S/R/L 值更新后 score 未同步计算

**Bug 3 — PowerShell 语法（3处）：**
- `webnovel-plan/SKILL.md` 第147/172/388行：`@'...'@ | Set-Content` / `Add-Content` → bash `cat > ... << 'EOF'` / `cat >> ... << 'EOF'`
- 第三处使用 `>>` 保持 Add-Content 的追加语义
- **根因**: SKILL.md 编写时使用了 PowerShell 语法，与其他 skill 文件（均为 bash）不一致

**验证结果：**
- grep 确认零残留 PowerShell 语法、零硬编码"第1卷"、零 score:62
- 插件缓存已同步（25文件）
