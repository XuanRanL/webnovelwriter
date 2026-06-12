---
name: webnovel-write
description: Writes webnovel chapters (default 2200-3800 words, Round 21.1 elastic ±500). Use when the user asks to write a chapter or runs /webnovel-write. Runs context, drafting, review, polish, and data extraction.
allowed-tools: Read Write Edit Grep Bash Task
---

# Chapter Writing (Structured Workflow)

> Round 29 Phase 2：本文件为骨架（目标 / 模式 / 跨步硬约束 / 闸门清单）。每个 Step 的完整执行协议
> 已拆分到 `references/steps/step-N.md`，**进入该步时必须先 `cat` 对应文件全文再执行**。

## 目标

- 以稳定流程产出可发布章节：优先使用 `正文/第{NNNN}章-{title_safe}.md`，无标题时回退 `正文/第{NNNN}章.md`。
- 默认章节字数目标：**弹性区间 2200-3800**。

  **字数弹性模型**：
  - **SSOT 字段**：`state.project_info.word_count_policy.hard_min` / `hard_max`（默认 2200/3800 · Round 21.1）
  - **弹性准则**：根据章节类型在硬区间内自由浮动（约 ±500 · Round 21.1）· `average_words_per_chapter_target=3000` 只是项目级软目标**参考**，**不是**单章硬下限
  - **chapter_type_guide 推荐区间**：
    - 过渡章/铺垫章：2200-2900
    - 推进章/日常章：2700-3300（默认）
    - 情感章/揭秘章：2900-3500
    - 战斗章/高潮章/卷末章：3200-3800（大纲/用户明确可破上限）
  - **禁止伪造区间**：禁止在 editor_notes / context JSON / 审查报告写 2900-3800 / 2700-3300 / 2400-3300 等自造区间（硬 min/max 之外的数字）· 禁止引用不存在的 state 字段名（如 `target_words_per_chapter_target`）
  - **冲突解决**：editor_notes（audit-agent 写）与 state.json SSOT 冲突时**以 state.json 为准**，context-agent 静默覆盖并在执行包 `warnings[]` 追加 `EDITOR_NOTES_WORD_COUNT_DRIFT`
  - **硬闸门**：post_draft_check.py 第 8 项 warn 扫描 editor_notes/context 字数漂移；audit-agent.md §8 block 凭印象自造区间
- 保证审查、润色、数据回写完整闭环，避免"写完即丢上下文"。
- 输出直接可被后续章节消费的结构化数据：`review_metrics`、`summaries`、`chapter_meta`。

## 执行原则

1. 先校验输入完整性，再进入写作流程；缺关键输入时立即阻断。
2. 审查与数据回写是硬步骤，`--fast`/`--minimal` 只允许降级可选环节。
3. 参考资料严格按步骤按需加载，不一次性灌入全部文档。
4. Step 2B 与 Step 4 职责分离：2B 只做风格转译，4 只做问题修复与质控。
5. 任一步失败优先做最小回滚，不重跑全流程。
6. **每个 Step 开始时必须先 `cat "${SKILL_ROOT}/references/steps/step-N.md"` 全文**（Round 29 拆分）；未加载该文件不得执行该步任何动作。

## 模式定义

- `/webnovel-write`：Step 0 → 0.5 → 1 → 2A → 2B → 3+3.5(并行) → 4 → 5 → 6 → 7
- `/webnovel-write --fast`：Step 0 → 0.5 → 1 → 2A → 3+3.5(并行) → 4 → 5 → 6 → 7（跳过 2B）
- `/webnovel-write --minimal`：Step 0 → 0.5 → 1 → 2A → 3（仅5个基础审查，跳过3.5）→ 4 → 5 → 6 → 7

最小产物（所有模式）：
- `正文/第{NNNN}章-{title_safe}.md` 或 `正文/第{NNNN}章.md`
- `index.db.review_metrics` 新纪录（含 `overall_score`）
- `.webnovel/summaries/ch{NNNN}.md`
- `.webnovel/state.json` 的进度与 `chapter_meta` 更新

### 流程硬约束（禁止事项）

- **禁止并步**：不得将两个 Step 合并为一个动作执行（如同时做 2A 和 3）。**唯一例外**：Step 2A 可被 context-agent 在 Step 1 尾部内联调度（详见 `workflow_manager.py` 的 `OPTIONAL_PRECEDING_STEPS`），但即使内联执行也必须显式 `workflow start-step --step-id "Step 2A"` 和 `complete-step`，让工作流登记完整。
- **禁止跳步**：不得跳过未被模式定义标记为可跳过的 Step。即使批量写多章、赶进度、上下文紧张，也必须每章完整执行所有 Step。任何"先写完再补审"、"跳过 Context Agent 直接起草"、"只跑外部审查不跑内部审查"的行为均视为违规。
- **禁止赶进度降级**：批量写作多章时，每一章都必须独立走完完整流程（Step 0→1→2A→2B→3→3.5→4→5→6→7）。不得因为"后面还有很多章"而简化任何一章的流程。质量优先于速度，这是不可协商的硬规则。
- **禁止省略审查报告**：Step 3 完成后必须生成审查报告文件（`审查报告/第{NNNN}章审查报告.md`），包含所有审查器的结果汇总。不得只在内存中汇总分数而不写文件。
- **审查报告模板规范 (Round 28.27)**：`overall_score: X` 唯一出现在 frontmatter 顶头；其他位置分数用别名（`综合分`/`thrill_score`/`sub_score`）；各 checker 行禁共用同一 token ≥3 次；外部模型分数必须用 disk JSON 真值。细则见 `references/steps/step-3.md`。
- **禁止临时改名**：不得将 Step 的输出产物改写为非标准文件名或格式。
- **禁止自创模式**：`--fast` / `--minimal` 只允许按上方定义裁剪步骤，不允许自创混合模式、"半步"或"简化版"。
- **禁止自审替代**：Step 3 审查必须由 Task 子代理执行，主流程不得内联伪造审查结论。
- **禁止主观估分**：`overall_score` 必须来自审查子代理的聚合结果，不得因为"子代理还没返回"而自行估算分数。
- **禁止源码探测**：脚本调用方式以本文档与 data-agent 文档中的命令示例为准，命令失败时查日志定位问题，不去翻源码学习调用方式。
- **禁止裸跑 polish commit**：Step 7 commit 之后任何对正文文件（`正文/第NNNN章*.md`）的修改，**必须**通过 `polish_cycle.py`（Step 8）完成，**严禁**直接 `git add . && git commit -m "polish"` 或 `git commit --amend`。裸跑会绕过 `post_draft_check`/`hygiene_check`，让 ASCII 引号、word_count 漂移、checker 数据滞留，并且 polish 任务在 `workflow_state.json` 不留痕。
- **禁止三连排比金句 / 诗化对偶金句 (Round 28.30 · post_draft H15 AI_SLOGAN warn 1 / block 2)**：单章 ABAB 三连排比 ≥1 组或诗化对偶金句 ≥3 处即触发。修法细则见 `references/steps/step-2a.md`。
- **META_DRIFT 自动根治 (Round 28.30)**：state_manager 已 auto-touch updated_at，无需手动同步；背景见 `references/steps/step-7.md`。
- **A2 未复测标签禁用 (Round 28.30)**：不复测 checker 行用"-"或留空，禁止 "(未复测)" 标签；细则见 `references/steps/step-3.md`。

### 章节间闸门（Chapter Gate）

在开始下一章的任何步骤（包括 Step 0）之前，必须验证当前章的以下条件全部满足：

1. Step 3 的内部 checker 全部返回并汇总出 overall_score。**术语固定**（见 `feedback_checker_count_13`）：`checker` = 跑的 subagent 数量 = 评分维度数量（**Round 13 v2 取消 veto 架构**，全部 checker 平等参与评分）。标准/`--fast` = **13 checker / 13 评分维度**（2 读者视角维度：naturalness + reader-critic，11 工艺维度含 flow-checker）。`--minimal` = **5 checker**（naturalness + reader-critic + consistency + continuity + ooc）。`overall_score = avg(所有评分维度)`。**两个读者视角 checker 不 block 流程**，其 problems 和其他 checker 同等进入 Step 4 定向修复。极端情况（Step 4 修复后 critical 仍未消除）才回 Step 2A 重写。
2. Step 3.5 的 15 模型外部审查已完成；健康线为 ≥10/15 有效，8-9/15 degraded_ok，5-7/15 degraded_warn，<5/15 critical。每个模型审查 **13 个维度**（10 工艺维度 + reader_flow + naturalness + reader_critic）；Round 21.4 默认每模型一次 combined 请求返回 13 维，失败才 split fallback（`--minimal` 模式跳过此条件）
3. 所有 critical 问题已修复，high 问题已修复或有 deviation 记录
4. 审查报告 .md 文件已生成（标准/`--fast` 模式含内部 13 评分维度分数 + 外部 15 模型×13 维度评分矩阵；`--minimal` 模式仅含内部 5 评分维度分数）
5. Step 4 的 `anti_ai_force_check=pass`
6. Step 5 Data Agent 已完成
7. Step 6 Audit Gate 决议 ∈ {approve, approve_with_warnings}（block 禁止进入 Step 7）
8. Step 7 Git 已提交

验证方式：在开始下一章 Step 0 之前，执行以下检查：
```bash
ls "${PROJECT_ROOT}/正文/第${chapter_padded}章"*.md >/dev/null 2>&1 && \
test -f "${PROJECT_ROOT}/审查报告/第${chapter_padded}章审查报告.md" && \
test -f "${PROJECT_ROOT}/.webnovel/summaries/ch${chapter_padded}.md" && \
test -f "${PROJECT_ROOT}/.webnovel/audit_reports/ch${chapter_padded}.json" && \
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" audit check-decision --chapter ${chapter_num} --require approve,approve_with_warnings && \
git log --oneline -1 | grep "第${chapter_num}章"
```
任一条件不满足，禁止开始下一章。新增闸门条件：
- `audit_reports/ch{NNNN}.json` 存在（Step 6 产物）
- audit decision 不等于 `block`（审计未通过禁止进入下一章）

**禁止在 checker 运行期间开始下一章的起草。** 等待是流程的一部分，不是浪费时间。

## 引用加载等级（strict, lazy）

- L0：未进入对应步骤前，不加载任何参考文件。
- L1：每步仅加载该步"必读"文件——首先是 `references/steps/step-N.md`，其内列明该步其余必读。
- L2：仅在触发条件满足时加载"条件必读/可选"文件（触发条件清单见 `references/reference-index.md`）。

路径约定：
- `references/...` 相对当前 skill 目录。
- `../../references/...` 指向全局共享参考。

## References（索引）

- **每步执行协议（L1 必读）**：`references/steps/step-0.md`（含 Step 0.5 + 搜索规则）/ `step-1.md` / `step-2a.md` / `step-2b.md` / `step-3.md` / `step-3.5.md` / `step-4.md`（含 4.5）/ `step-5.md` / `step-6.md` / `step-7.md`（含 Step 8）
- **逐文件引用索引（L2 触发条件）**：`references/reference-index.md`
- **充分性闸门 vs hygiene H* 对应表**：`references/gate-matrix.md`（新增/修改/删除任一闸门前必读）

## 工具策略（按需）

- `Read/Grep`：读取 `state.json`、大纲、章节正文与参考文件。
- `Bash`：运行 `extract_chapter_context.py`、`index_manager`、`workflow_manager`。
- `Task`：调用 `context-agent`、审查 subagent、`data-agent` 并行执行。

## 交互流程

### Step 0 + 0.5：预检与工作流登记

```bash
cat "${SKILL_ROOT}/references/steps/step-0.md"
```

要点：`preflight` 必须成功（CLAUDE_PLUGIN_ROOT fallback 推导见 step-0.md）；`agents_sync` / `cache_sync` / `polish_drift` 任何 ERROR 必须在 Step 1 前清零；`workflow start-task` 必须成功。Step 登记三件套（start-step → 工作 → complete-step 带语义 artifact）贯穿全流程，strict 默认开启（无 start-step 的 complete-step 直接被拒）；shell 类步骤优先用 `workflow run-step` 原子包装。搜索统一走 `tavily_search.py`（禁 MCP 工具），失败必须停下报告用户。

### Step 1：Context Agent（内置 Context Contract）

```bash
cat "${SKILL_ROOT}/references/steps/step-1.md"
```

要点：Task 调用 `context-agent` 产出单一创作执行包（8 板块任务书 + Contract 全字段 + 直写提示词）；完成后必须验证三份产物落盘（context_snapshot + 执行包 JSON + MD），任一缺失禁止进入 Step 2A。Ch1-3 叠加开篇黄金协议与首章加严 rubric。

### Step 2A：正文起草

```bash
cat "${SKILL_ROOT}/references/steps/step-2a.md"
```

要点：起草前必读 core-constraints / anti-ai-guide / visual-concreteness（前 5 章另加 first-chapter-hook-rubric + 写前自检）；起草前 outline + 签名预算 self-check、起草后 4 项 self-check；只输出纯正文（禁 Markdown / ASCII 引号 / U+FFFD / 元叙述 / 章号距离指代）；起草后必跑引号扫描 + FFFD 验证 + `post_draft_check.py` exit=0 才能进入下一步。

### Step 2B：风格适配（`--fast` / `--minimal` 跳过）

```bash
cat "${SKILL_ROOT}/references/steps/step-2b.md"
```

要点：只做表达层转译，不改剧情事实；起草已符合项目风格时可声明 no-op，但必须显式登记 deviation_notes；完成后再跑一次 post_draft_check + FFFD 验证。

### Step 3：内部审查（13 checker · 必须由 Task 子代理执行）

```bash
cat "${SKILL_ROOT}/references/steps/step-3.md"
```

要点：0+6+5 三批启动（Batch 0 读者视角双 checker 先行）；全部 checker 返回前禁止进入 Step 4；13 份 checker JSON 落盘逐一验证 parseable（H71 嵌套引号自检）；`review_metrics` 落库 + `checker_scores` 双通道落库（索引层 + 状态层）缺一不可；`overall_score = round(internal*0.6 + external*0.4)`。

### Step 3.5：外部模型审查（15 模型 × 13 维度 · `--minimal` 跳过）

```bash
cat "${SKILL_ROOT}/references/steps/step-3.5.md"
```

要点：`build_external_context.py` 构建 14 字段上下文 → healthcheck → `external_review.py --model-key all --dimension-strategy auto` 一次性跑全部 15 模型；≥10/15 有效为健康线；与 Step 3 并行但必须显式 start-step。**Step 3+3.5 完成闸门（5 项验证）全部通过才可进入 Step 4**（清单见 step-3.5.md）。

### Step 4 / 4.5：润色与选择性复测

```bash
cat "${SKILL_ROOT}/references/steps/step-4.md"
```

要点：修复顺序 critical（必须）→ high（修复或 deviation）→ medium/low（择优）；polish 新增有名角色行为/物件位置前必 canon-grep；字数预算（净增 ≤200 · 不破 hard_max）；产出润色后正文 + 润色报告（`polish_reports/` 落盘，含 `anti_ai_force_check`，fail 不得进入 Step 5）。Step 4.5 复测触发档（<75 强制 / <80 近线 / 下滑 ≥5 / HIGH-issue 全面）；复测组合调用后必须最后重设 `overall_score = combined`。

### Step 5：Data Agent（状态与索引回写）

```bash
cat "${SKILL_ROOT}/references/steps/step-5.md"
```

要点：Task 调用 `data-agent` 执行 A-K 子步全量；完成后必跑数据完整性后验证（checker_scores 13 canonical key / word_count 误差 ≤2% / strand 一致）；失败隔离——G/H 子步失败只补跑子步，禁止重跑写作链。

### Step 6：审计闸门（Audit Gate）

```bash
cat "${SKILL_ROOT}/references/steps/step-6.md"
```

要点：Part 1 CLI 结构审计（Layer A/B/G）+ Part 2 audit-agent 深度审计（Layer C/D/E/F）都必须完成；`audit_reports/ch{NNNN}.json` 与下章 `editor_notes` 必须落盘；decision=block 禁止进入 Step 7；超时 300s 视为未完成。

### Step 7：Git 备份 + workflow 收尾

```bash
cat "${SKILL_ROOT}/references/steps/step-7.md"
```

要点：顺序锁死——Step 6 complete-step → **(step gap) hygiene_check + pre_commit_step_k 双闸 exit=0** → start-step Step 7 → git commit → complete-step → complete-task。在 Step 7 active 状态跑 hygiene 会 H3 P0；commit 失败必须 fail-step 且不得调 complete-task。

### Step 8：Post-Commit Polish Loop（提交后再润色循环）

```bash
cat "${SKILL_ROOT}/references/steps/step-7.md"
```

要点：Step 7 commit 之后任何正文修改的**唯一入口**是 `polish_cycle.py`（自动完成 7 步，commit 是最后一步原子落盘；轮数上限 3，突破需 deviation）。严禁裸跑 `git commit` / `--amend`。完整规范另见 `references/post-commit-polish.md`（Post-Commit Polish 触发场景 / 多轮 / 恢复策略）。

## 充分性闸门（必须通过）

未满足以下条件前，不得结束流程：

1. 章节正文文件存在且非空：`正文/第{chapter_padded}章-{title_safe}.md` 或 `正文/第{chapter_padded}章.md`
2. **Step 1 执行包已落盘**：`.webnovel/context/ch{chapter_padded}_context.json` 与 `.webnovel/context/ch{chapter_padded}_context.md` 同时存在且非空
3. **Step 2A/2B 后 `post_draft_check.py` exit=0**
4. Step 3 已产出 `overall_score`（聚合 **13 评分维度** · Round 13 v2）且 `review_metrics` 成功落库；`naturalness_verdict` / `reader_critic_verdict` 作为报告字段记录，不 block 流程；其 problems 与其他 checker 的 issues 合并进入 Step 4 修复
5. Step 3.5 外部审查已完成且有效模型数达到健康/可降级阈值（`--minimal` 模式跳过此条件）
6. 审查报告 `.md` 文件已生成（标准/`--fast` 模式含内部 13 评分维度分数 + 外部 15 模型×13 维度评分矩阵，内外均含 reader_flow + naturalness + reader_critic · Round 13 v2；`--minimal` 模式含内部 5 评分维度分数）
7. Step 4 已处理全部 `critical`，`high` 未修项有 deviation 记录
8. **Step 4 润色报告已落盘**：`.webnovel/polish_reports/ch{chapter_padded}.md` 存在且非空，含 `anti_ai_force_check` 字段
9. Step 4 的 `anti_ai_force_check=pass`（基于全文检查；fail 时不得进入 Step 5）
10. Step 5 已回写 `state.json`、`index.db`、`summaries/ch{chapter_padded}.md`
11. Step 6 审计产物齐全：`audit_reports/ch{chapter_padded}.json`、`editor_notes/ch{next_padded}_prep.md`、`observability/chapter_audit.jsonl` 追加一行；audit decision ∈ {approve, approve_with_warnings}
12. **workflow 四步登记完整**：`workflow_state.json` 的当前 task 已 `complete-task` 且 `completed_steps` 覆盖 Step 1/2A/2B/3/3.5/4/5/6/7 全量（Step 2A 可由 context-agent 内联但必须显式登记）；每个 step 的 artifact 非空且非 `{"v2": true}` 占位
13. **Step 7 commit 前 `pre_commit_step_k.py` exit=0**
14. Step 7 Git 已提交
15. 若开启性能观测，已读取最新 timing 记录并输出结论
16. **polish_log schema 合规**：若 `chapter_meta.{NNNN}.polish_log` 存在，每条必须含 `version` / `timestamp` / `notes` 三字段，`version` 匹配 `vN` 或 `vN.M.K`，`timestamp` 为 ISO-8601。schema 违规会让下章 context-agent 解析 polish 经验失败（跨章传递断层）
17. **polish_drift 零 P0**：Step 0 preflight 必须报告 `polish_drift: ok=True`；若 P0 drift（正文已改 + `narrative_version=v1`）则 preflight 失败，必须先走 `polish_cycle.py` 提交或 `git stash` 暂存
18. **A9 评分硬底线 pass / warn**：Step 6 audit `layers.A_process_integrity.checks` 中 A9 dimension_floor 必须 status ∈ {pass, warn}；fail critical 阻断 Step 7。任一维度 <60 → cap 70 fail critical；<75 → cap 85 warn high；前 5 章 reader-critic <80 → cap 80 fail critical
19. **H26 hook_close 落库一致性**：若 `tmp/reader_pull_chNNNN.json` 含 `hook_close.primary_type` 但 `state.chapter_meta.NNNN.hook_close` 缺失 → P0 fail（Phase G 落库被跳过的 根治）
20. **H25 连续 8 章无决策钩 P0**：最近 8 章 hook_close.primary_type 全无"决策钩" → P0 fail；触发后下章 reader-pull-checker.hook_close.primary_type 必须为"决策钩" 或 reader-thrill protagonist_victory ≥80。chapter-aware：仅在 polish 当前最新章或更新章时触发，不阻断早章 polish
21. **H27 polish sunk cost 警报**：narrative_version ≥ v3 + polish_log ≥ 2 轮 + ≥ 5 项 checker_scores ∈ [80, 84]（80 一线）→ P1 提示考虑 Step 0 重写而非继续 polish
22. **chapter_meta.thrill_score 落库**：若 Step 3 跑了 reader-thrill-checker（标准模式 Batch 2 默认跑），`set-chapter-meta-field --field thrill_score --value '{...}'` 写库；前 5 章 verdict ∈ {tepid, frustrating} 且 reader-critic <80 → audit 双 floor 联动 block
23. **H28 hook_close 版本新鲜度**：`set-hook-close` 必须写入 `source_narrative_version`；若当前 `chapter_meta.NNNN.narrative_version` 与 `hook_close.source_narrative_version` 不一致 → P0 fail，说明 Step 8 polish 后未重跑 reader-pull/未回填章末钩子，会污染 H25 hook trend。老数据缺 source 但有 polish_log → P1 提醒回填。
24. **polish_cycle 自动 hook_close 同步契约**：`polish_cycle.update_state_after_polish` 末尾必须自动：(a) 抽取章末最后 4 段 200 字内作为 `hook_close.text_excerpt`；(b) `hook_close.source_narrative_version=new_version`；(c) `hook_close.needs_reclassify=True`；(d) `hook_close.polish_synced_at=now`。下游 hygiene H28 检测 `needs_reclassify==True` 直接 P0 fail，迫使作者/AI 阅读章末后立即跑 `state update --set-hook-close` 重新分类（决策钩 / 信息钩 / 情绪钩 / 动作钩），重分类后 set-hook-close 自动清 needs_reclassify=False 解锁 commit。这是从"H28 detect → 人工修"升级到"polish 自动标 stale → 必须重分类才能 commit"的强闭环。
25. **H21 dialogue_ratio_override_chapters 豁免**：post_draft_check 已读 `post_draft_config.json` 的 `dialogue_ratio_override_chapters`，hygiene `H21` 之前漏读，导致项目级豁免章仍报"对话占比连 3 章 < 0.20" P1 假阳。现 H21 同读该字段，豁免章不计入连续低占比 streak（Ch3 空间种田激活章 / Ch2 金融操盘+前世独白章等）。
26. **H18 升级 13 canonical 必齐**：`chapter_meta.{NNNN}.checker_scores` 必须包含全部 13 个 canonical key（11 工艺 + naturalness + reader-critic），缺任一 P0 阻断。Ch24 漏 reader-naturalness-checker 原 H18 只查"已存在 key 是否 canonical"不查完整性，导致下游 audit 静默错算 overall。
27. **H58 真源对账**：`chapter_meta.checker_scores` 与 `review_metrics.dimension_scores` 13 个 canonical 项漂移 ≤±1。例外：`post_polish_recheck` 中的 checker（Step 4.5 合法 polish 真值改）。Ch24 实测 9 项漂移最大 14 分（prose-quality 89 vs 75 真源），P1 警告。
28. **H59 静默改分检测**：任一 checker 与 review_metrics 漂移 >1 必须在 `post_polish_recheck` 留 before/after 记录；无记录则 P1 警告。`state update --set-checker-score` 必须配套 `--append-recheck`，违反 Step 3+4.5 真源不可篡改原则。
29. **H61 progress 字段对齐**：`state.last_completed_chapter` 与 `state.current_chapter` 必须 == max(chapter_meta keys)。Ch24 写到 24 但二字段停在 20（连续 4 章累积漂移），P1 警告。
30. **post_draft 那一X 阈值收紧**：`那一X` block 阈值 18→12（warn 仍 10）。Ch24 实测 14 次仍只 warn 不 block，整章 polish 回避了这个签名。≥12 直接 block 阻止 commit。

闸门与 hygiene H* 的一一对应、多层防御设计与同步维护规则见 `references/gate-matrix.md`。

## 验证与交付

执行检查：

```bash
test -f "${PROJECT_ROOT}/.webnovel/state.json"
ls "${PROJECT_ROOT}/正文/第${chapter_padded}章"*.md >/dev/null 2>&1
test -f "${PROJECT_ROOT}/.webnovel/summaries/ch${chapter_padded}.md"
test -f "${PROJECT_ROOT}/.webnovel/audit_reports/ch${chapter_padded}.json"
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" audit check-decision --chapter ${chapter_num} --require approve,approve_with_warnings
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" index get-recent-review-metrics --limit 1
tail -n 1 "${PROJECT_ROOT}/.webnovel/observability/data_agent_timing.jsonl" || true
tail -n 1 "${PROJECT_ROOT}/.webnovel/observability/chapter_audit.jsonl" || true
```

成功标准：
- 章节文件、摘要文件、状态文件齐全且内容可读。
- 审查分数可追溯，`overall_score` 与 Step 5 输入一致。
- 润色后未破坏大纲与设定约束。

## 失败处理（最小回滚）

触发条件：
- 章节文件缺失或空文件；
- 审查结果未落库；
- Data Agent 关键产物缺失；
- 润色引入设定冲突。

恢复流程：
1. 仅重跑失败步骤，不回滚已通过步骤。
2. 常见最小修复：
   - 审查缺失：只重跑 Step 3 并落库；
   - 外部审查缺失/失败：只重跑 Step 3.5（核心模型按 fallback 链重试）；
   - `anti_ai_force_check=fail`：留在 Step 4 继续改写直到 pass，不回退也不跳过；
   - 润色失真：恢复 Step 2A 输出并重做 Step 4；
   - 摘要/状态缺失：只重跑 Step 5；
   - Step 6 audit block：按 `audit_reports/ch{NNNN}.json` 的 `blocking_issues` 逐项 remediation（通常回到 Step 1/3/3.5/4/5），修复后重跑 Step 6；
   - Step 6 audit 超时：重跑 audit-agent（增量模式，仅跑未完成 layers）；
3. 重新执行"验证与交付"全部检查，通过后结束。
