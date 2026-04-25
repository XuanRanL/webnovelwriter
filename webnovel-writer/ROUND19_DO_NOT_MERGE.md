# Round 19 · DO NOT MERGE 永久清单

> **Round 19 Phase 7 立项**：本地 fork 与 upstream 在以下 10 类维度已分叉为不同产品。**每次 git fetch upstream 看到属于以下类别的新 commit，直接跳过，不必重新评估架构选型。**

> **关联文档**：
> - `CUSTOMIZATIONS.md` — fork 改动总日志
> - `docs/superpowers/plans/2026-04-25-reader-quality-uplift-v3-final.md` — Round 19 终版计划
> - `docs/superpowers/plans/round19-research/ch1-11-root-cause-analysis.md` — Round 19 RCA 深度分析
> - `docs/superpowers/plans/upstream-snapshot/COMMIT_REF.txt` — 锁定基线 commit

---

## 1. v6 单 reviewer.md（替代 13 checker）

- **upstream commits**: `264dd24` `b7a944d` `b488401` `ce6bf35` `5339e83`（仅 5339e83 的 5 子维度 rubric 借鉴到 Round 19 Phase C，不引入 reviewer.md 整体）
- **拒绝原因**：用户明确要求 90-100 评分体系（feedback_review_score_target.md）；upstream 砍掉评分；本地 13 checker × 14 外部模型 = 182 共识样本是 18 轮加固的核心
- **替代**：本地继续 13 checker；如需"摘要式输出"在 review_pipeline 后加聚合层即可，不动评分

## 2. workflow_manager 移除（依赖 Claude Code /resume）

- **upstream commit**: `b1e7402`
- **拒绝原因**：本地 Step 0-7 流程严重依赖 workflow_manager（feedback_ch7_workflow_must_log.md）；并已对 complete-task --force 等做 RCA 加固（Round 15.3 Bug #1）
- **替代**：本地继续维护 workflow_manager；CC `/resume` 作并行能力

## 3. story-system 事件溯源 + projection writers

- **upstream commits**: `a3c19cf` `b80e5a5` `ac748d2` 等 Phase 1-5 全套
- **拒绝原因**：本地 state.json 已被 hygiene H1-H24 + 多个 CLI 当作直接真源；改成 CHAPTER_COMMIT + projection 投影模式 = 重做 18 轮加固
- **替代**：state.json 继续直写；如需事件审计链，在 state_manager 加事件日志

## 4. vector_projection_writer + vectors.db

- **upstream commits**: `29c8ac1` `7c849f8`
- **拒绝原因**：边际收益低（已有摘要 + index.db；Phase G 又新加 hook_trend）；引入需 embedding 模型 + 新数据层
- **替代**：knowledge_query 时序 API（Round 20 视情况评估）

## 5. dashboard 路由多页重建

- **upstream commits**: `a033f36` `34c436d` `65c220b` `b57754d` `bb9829a`
- **拒绝原因**：纯 QoL，不影响小说质量；前端重写代价高
- **替代**：保留本地现有 dashboard

## 6. Token 压缩整文件替换

- **upstream commits**: `8bdd18e` `3d64506`
- **拒绝原因**：本地 context-agent 755 行多出来的部分是 18 轮 RCA 加固
- **替代**：未来手术式压缩（不允许整文件替换）

## 7. v6 chapter_drafted/reviewed/committed 状态机

- **upstream commit**: `a2a209c`
- **拒绝原因**：与本地 chapter_meta.review_metrics.overall_score 评分门控语义不一致
- **替代**：本地继续评分门控

## 8. SKILL.md 充分性闸门切到状态机

- **upstream commit**: `bf013cf`
- **拒绝原因**：本地 SKILL.md 是评分驱动多 Step 闸门
- **替代**：本地继续多 Step 闸门

## 9. 移除 golden_three_checker / Step 2B legacy

- **upstream commit**: `80b3503`
- **拒绝原因**：feedback_no_skip_2b 明确要求 Step 2B 不可跳
- **替代**：本地保留 Step 2B

## 10. Memory contract / scratchpad 大改

- **upstream commits**: `33ea944` `085c223` `39a1f1b` `2d6762e` `beefb95` `02e9f39`
- **拒绝原因**：本地 context-agent 已通过 webnovel.py state/index/extract-context 多 CLI 实现按需加载
- **替代**：Round 19 Phase G hook_trend / Phase E get-recent-meta 已覆盖跨章查询场景

---

## 选择性借鉴（已纳入 Round 19）

下列 upstream 资产已**部分借鉴**到 Round 19，但不引入 v6 整体架构：

| upstream 资产 | 借鉴方式 | Round 19 Phase |
|---|---|---|
| `f774f2b` anti-ai-guide.md（74 行） | 1:1 引入 + 本地 N1-N5 根因映射 | Phase A |
| `74717aa` polish-guide K/L/M/N 词库 | 取并集合并到本地 200+ 词库 | Phase B |
| `5339e83` reviewer ai_flavor 5 子维度 rubric | 借鉴到 reader-naturalness-checker（不引入 reviewer.md） | Phase C |
| `3e36417` plan reads write history | 借鉴思路 + 本地 state get-recent-meta CLI 实现 | Phase E |

---

## 长期纪律

- **每次 git fetch upstream**：先看 commit log，落入上述 10 类直接跳过
- **每次 Round N 立项**：只看"自然度 / 画面感 / 追读力" 3 件标尺；映射不到的不做（参 v3 计划 §0.1）
- **每次发现 upstream 有"似乎不错"的新功能**：先问"读者会因为这个多看一章吗？"，否 → 不做
- **每次有人要求"和 upstream 同步"**：拿这份清单解释为什么 fork 走了不同路线（user feedback memory 已锁定）
