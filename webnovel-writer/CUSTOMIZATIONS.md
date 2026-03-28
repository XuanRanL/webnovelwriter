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

<!-- 新的改动记录追加在此线下方 -->
