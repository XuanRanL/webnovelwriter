# 闸门一致性对照表（Gate Matrix）

> Round 14.5.2 新增 · 保证"人读 SKILL 规则"与"机读闸门脚本"一一对应
> 每次增改闸门必须同步更新本表，避免文档承诺 > 代码实现的断层
> 最后校对：2026-04-20

## 设计原则

任何一条 SKILL.md 的"充分性闸门"都必须有至少一个**机读**检查项与之对应；
反之任何一个机读检查项也必须在 SKILL.md 的规则段落能找到文字描述。
不一致的条目会在 **每次 session 首次 preflight** 输出对照表提醒。

## 对照表

| # | SKILL.md 充分性闸门（人读） | 机读检查点 | 位置 | 阻断级 |
|---|---|---|---|---|
| 1 | 章节正文文件存在且非空 | `H4` + `H14` 前置必读 | `hygiene_check.py` | P0 |
| 2 | Step 1 执行包（JSON + MD）已落盘 | `H14` | `hygiene_check.py:check_execution_package_persistence` | P0 |
| 3 | Step 2A/2B 后 `post_draft_check` exit=0 | `post_draft_check.py` 调用 | Step 2A/2B 流程 | P0 |
| 4 | Step 3 `overall_score` 聚合 + review_metrics 落库 | `H9` (score alignment) | `hygiene_check.py:check_score_alignment` | P1 |
| 5 | Step 3.5 外部审查（核心3模型成功） | `external_review.py` 退出码 0 | 主流程调用 | P0 |
| 6 | 审查报告 .md 存在 | `H15` 扩展（审查报告路径） | `hygiene_check.py` | P0 |
| 7 | Step 4 处理全部 critical，high 有 deviation | `H15` (polish_reports 必要段落) | `hygiene_check.py:check_polish_report_persistence` | P0 |
| 8 | Step 4 润色报告已落盘 | `H15` | `hygiene_check.py:check_polish_report_persistence` | P0 |
| 9 | `anti_ai_force_check=pass` | `H15` (内含 anti_ai_force_check 解析) | `hygiene_check.py` | P0 |
| 10 | Step 5 回写 state/index/summary | `H2` (chapter_meta core 字段) | `hygiene_check.py:check_chapter_meta_core` | P0 |
| 11 | Step 6 审计产物齐全 + decision ≠ block | `audit check-decision` CLI | `webnovel.py audit` | P0 |
| 12 | workflow 四步登记完整 | `H3` + `H16` | `hygiene_check.py:check_workflow_{not_dangling,artifact_integrity}` | P0 |
| 13 | Step 7 commit 前 `pre_commit_step_k` exit=0 | `pre_commit_step_k.py` 调用 | Step 7 流程 | P0 |
| 14 | Step 7 Git 已提交 | `H19` (HEAD vs 工作区) | `hygiene_check.py:check_post_commit_polish_drift` | P0 (via preflight H19a) |
| 15 | 性能观测 timing 有输出 | （无机读闸门 · 人读校验） | — | 软要求 |

## 硬约束（禁止事项）与机读闸门对应

| SKILL.md 硬约束 | 机读闸门 | 位置 |
|---|---|---|
| 禁止并步（2A+3 合并等） | `H16` `missing_steps` 检测 | `hygiene_check.py:check_workflow_artifact_integrity` |
| 禁止跳步 | `H16` + `REQUIRED_ARTIFACT_FIELDS` 白名单 | `workflow_manager.py:_validate_artifact_has_semantic_field` |
| 禁止占位 artifact (`{"v2": true}`) | `H16` `PLACEHOLDER_ONLY_FIELDS` 拒绝 | `workflow_manager.py` |
| 禁止 ASCII 双引号 | `H5` + `post_draft_check` 第 1 项 | `hygiene_check.py:check_chapter_text_hygiene` + `post_draft_check.py` |
| 禁止 U+FFFD | `H4` + `post_draft_check` 第 2 项 | `hygiene_check.py` + `post_draft_check.py` |
| 禁止 Markdown 结构 | `post_draft_check.py` 第 3 项 | `post_draft_check.py` |
| 禁止裸跑 polish commit | **多层闸门**（见下一节） | 多文件协同 |
| 禁止手动改 workflow_state.json | `H16` artifact 校验 + `PLACEHOLDER_ONLY_FIELDS` | `workflow_manager.py` + `hygiene_check.py` |

## 裸跑 polish commit 的多层拦截（Round 14.5.2）

这是一个需要多层防御的场景，因为单点闸门容易被绕过：

```
┌──────────────────────────────────────────────────────────────────┐
│ 层 1：pre-commit hook（可选安装，可 --no-verify 绕过）           │
│   scripts/install_git_hooks.py 安装                              │
│   拦截：正文 staged + commit msg 非 polish_cycle/Step 7 格式     │
│   适用：有意愿防护的用户层，硬技术拦截                           │
└──────────────────────────────────────────────────────────────────┘
                            ↓ 若绕过
┌──────────────────────────────────────────────────────────────────┐
│ 层 2：preflight polish_drift 检查（下次 preflight 触发）         │
│   webnovel.py preflight 每次 Step 0 必跑                         │
│   拦截：正文 HEAD vs 工作区不同 + narrative_version=v1 → P0       │
│   适用：写下章时早期发现                                         │
└──────────────────────────────────────────────────────────────────┘
                            ↓ 若绕过
┌──────────────────────────────────────────────────────────────────┐
│ 层 3：hygiene_check H19/H19a（Step 7 commit 前强制）             │
│   主流程 Step 7 的 "0) commit 前硬闸门" 调用                      │
│   拦截：正文已改 + narrative_version=v1 → 阻断 commit             │
│   适用：Step 7 前最后一道防线                                    │
└──────────────────────────────────────────────────────────────────┘
                            ↓ 若绕过（--no-verify + 跳过 Step 7 流程）
┌──────────────────────────────────────────────────────────────────┐
│ 层 4：context-agent 读 polish_log 检测 narrative_version 漂移    │
│   下章 Step 1 时：narrative_version !=v1 但 polish_log 为空 → WARN│
│   适用：事后检测，但无法阻断（只能提醒）                         │
└──────────────────────────────────────────────────────────────────┘
```

## 充分性闸门扩充（Round 14.5.2 后）

SKILL.md 充分性闸门除了上述 15 条，再增加：

16. **polish_log schema 合规**（Round 14.5.2 · `H20`）：若 `chapter_meta.{NNNN}.polish_log` 存在，每条必须含 `version/timestamp/notes` 三字段，version 匹配 `vN` 或 `vN.M.K`，timestamp 为 ISO-8601
17. **polish drift 零 P0**（Round 14.5.2 · preflight `polish_drift`）：Step 0 preflight 必须报告 `polish_drift: ok=True`；P0 drift 视为 preflight 失败

## 同步维护规则

**新增闸门时必须做**：
1. 在 SKILL.md "充分性闸门" 列表增加一行
2. 在 `hygiene_check.py` 的 H* 列表添加新项 + 对应 `check_*` 函数
3. 在本表（gate-matrix.md）添加一行
4. 在 `scripts/data_modules/tests/` 补测试

**删除闸门时必须做**：
1. 确认该闸门的功能已被其它机制覆盖（或确实不需要）
2. 同步删除 SKILL.md 和本表的对应条目
3. 删除 `hygiene_check.py` 的函数但保留历史注释说明废弃原因
4. 在 `CUSTOMIZATIONS.md` 记录删除原因和时间

**争议裁决**：SKILL.md 的描述与本表有冲突时，以**代码实际实现的 hygiene 检查行为**为最高权威；本表次之；SKILL.md 的文字描述最低——因为代码是真正执行的闸门，文字可能滞后。发现不一致必须在 24 小时内对齐。
