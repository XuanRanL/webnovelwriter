# webnovel-write · Step 4 润色 + Step 4.5 选择性复测

> Round 29 Phase 2 由 SKILL.md 原文拆分（lazy-load）。进入对应 Step 时必须先加载本文件全文，
> 按其中规则执行；跨步骤硬约束 / 章节间闸门 / 充分性闸门见 SKILL.md 骨架。

### Step 4：润色（问题修复优先）

> **🔴 Round 28.46 · polish 新增有名角色行为 / 物件位置前必 grep（防 R28.36 v5 + R28.46 同源根因）**
>
> 在 polish 修复涉及到新增"角色 X 在 Y 地点 / 与 Z 交互"或"物件 X 在桌上 / 兜里 / 手上"等段落前，**必须**先 grep Canon + 同章正文确认：
>
> ```bash
> # § canon-grep — 任何有名角色 (非临时配角) 新增段
> grep -n "<角色名>" 设定集/00-Canon-Bible.md
> grep -n "<角色名>" 设定集/08-连续性锁死表.md  # 或 SSOT
> grep -nE "<角色名>.*(觉醒|印记|入基地|移居|住|学校)" 设定集/
> # § physical-state-trace — 任何随身物 / 容器内物新增位置
> grep -nE "(物件名)" 正文/第00{N}章*.md  # 看前后位置链
> ```
>
> **R28.36 v5 教训**: Ch45 polish 凭印象造"合肥物科院"传染 12 处。
> **R28.46 #1 教训**: Ch46 polish 凭印象写"陆灵今晚在内院" — Canon SSOT 一.D-7 锁"未移居" 硬冲突。
> **R28.46 #6 教训**: Ch46 polish L341 引入折角广告纸"兜里→桌上"瞬移，flow recheck 报 high。
>
> 详见 `references/polish-guide.md` §2.0c.bis (canon-grep) + §2.0c.tri (physical-state-trace)。

执行前必须加载：
```bash
cat "${SKILL_ROOT}/references/polish-guide.md"
cat "${SKILL_ROOT}/references/writing/typesetting.md"
```

执行顺序：
1. 修复 `critical`（必须）
2. 修复 `high`（不能修复则记录 deviation）
3. 处理 `medium/low`（按收益择优）
4. 执行 Anti-AI 与 No-Poison 全文终检（必须输出 `anti_ai_force_check: pass/fail`）

**字数预算硬约束**：

**为什么需要**：
- Step 2B 后字数 3453（在 2600-3200 推进章区间偏上）
- Step 4 polish 加 4 critical + 9 high 新内容 → 字数涨到 3638（超 3500 硬上限 +138 字）
- 手动压缩 5 次才回到 3493（浪费 10+ 分钟）
- 根因：polish 没有“字数预算”意识，加内容前不算账

**硬规则**：
1. **净增上限 +200**：polish 导致字数净增超过 200，必须自检是否冗余
2. **硬上限**：polish 后总字数 ≤ state.json `word_count_policy.hard_max`（默认 3800 · Round 21.1），否则触发强制压缩
3. **推荐顺序**：先删冗余段（reader-critic/pacing 标记的“非必要对话/描写”）再扩 critical 修复，而不是“先加后砍”
4. **边界豁免**：若项目有 `word_count_policy.hard_max_polish_allowance`（如 +5%），polish 期可临时用，但 Step 5 前必须压回 hard_max 内

**检查点**（Step 4 complete 前必跑）：
```bash
python -X utf8 "${SCRIPTS_DIR}/post_draft_check.py" ${chapter_num} --project-root "${PROJECT_ROOT}"
```
hard_max 超限会直接 fail，回 Step 4 继续压缩。

输出（两个必须同时产出，缺一视为 Step 4 未完成）：
1. **润色后正文**（覆盖 `正文/第{chapter_padded}章-{title_safe}.md`）
2. **润色报告**（必须落盘到 `.webnovel/polish_reports/ch{chapter_padded}.md`，结构规范如下）

润色报告必须 Markdown 格式，且至少含下列段落：
```markdown
# 第{N}章 润色报告

> chapter: {N}
> polished_at: {ISO-8601 UTC}
> anti_ai_force_check: pass | fail
> final_weighted_score: {数值}

## 修复项（critical + high）
- [CONS_001] 设定一致性问题描述 → 修法: ...
- [OOC_002] 对话人设偏差 → 修法: ...

## 保留项（未修复并附 deviation 理由）
- [PACING_003] 节奏偏慢 → 保留: 本章为铺垫章，节奏克制是设计

## 放弃修复（medium/low）
- [PROSE_008] 比喻略平淡 → 成本高收益低

## Anti-AI 全文终检
- 禁语扫描: pass
- 重复句式扫描: pass
- 结论: **anti_ai_force_check = pass**

## 变更摘要（与原稿 diff 的 key changes）
- Beat 3 扩写 80 字：加入母亲照片特写
- Beat 6 缩写 40 字：删除重复情绪副词
- Ch 末尾钩子从 medium 升到 strong（新增"信里最后那句话"）
```

**持久化硬要求**：
- `.webnovel/polish_reports/ch{chapter_padded}.md` 必须由主 agent 用 Write 工具写入，不得用“变更摘要打印到 stdout 就算数”的方式处理
- `anti_ai_force_check` 必须为字符串 `pass` 或 `fail`，不允许 `None` / 空字符串
- 若 Step 4 `anti_ai_force_check=fail`，留在 Step 4 继续改写，**不进入 Step 5**（见充分性闸门 #6）
- 充分性闸门 #6 新增一条：`.webnovel/polish_reports/ch{chapter_padded}.md` 存在且非空

**为什么必须落盘**：
1. **跨章工艺学习**：近 5 章反复被改写的 beat 类型可以注入 context-agent 的 quality_feedback，Step 2A 提前规避
2. **作者自我反思**：某章为什么质感突然好/差，看润色报告就知道
3. **Step 6 Layer F/G 依赖**：审计要读 anti_ai_force_check 和 fixes 列表，没有文件就只能假设 pass

### Step 4.5：选择性复测

**定位**：Step 4 polish 后，对被 polish 集中修复的低分 checker 做**选择性复测**，确保 `chapter_meta.checker_scores` 反映的是修后真实分数，而不是修前数据。

**为什么需要**：
- Step 3 pacing-checker=58（Beat 2 超限 + B2/B3 结构同构 + B4 过短）
- Step 4 针对性全部修复（拆段 + 差异化 + 扩写）
- Step 4 直接进入 Step 5，`checker_scores.pacing-checker` 仍是 58
- Step 6 审计 C6 警告 “pacing 58 FAIL polish-only no retest”
- 本次 Ch7 后追加复测：pacing 58→90（+32），真实 overall 应为 88 而非 85
- **后果**：chapter_meta 存的是修前数据，下章 trend 监控误判“Ch7 pacing 突降”

**触发规则（硬约束 · Round 28.1 第 4 档加入）**：
- **强制复测档**：Step 3 任一 checker 首次分数 `< 75` → Step 4 polish 后**必须**重跑该 checker（旧规则保留）
- **近线复测档**：Step 3 任一 checker 首次分数 `< 80` 且该次 polish 报告含针对此 checker 的 fix（PACE_/FLOW_/EMO_/HP_/PRO_/OOC_/CONT_/CONS_/DIA_/DEN_ 任一前缀）→ **必须**重跑该 checker（验证修复真效）
- **下滑复测档**：Step 3 任一 checker 首次分数与上一章同维度差 `≥ 5` 且 polish 含此 checker 修法 → **必须**重跑（验证回归是否被止住）
- **HIGH-issue 全面复测档**：Step 3 任一 checker 输出含 `severity=high` 的 issue → Step 4 polish 后**必须**重跑该 checker，且复测分数必须比修前 **≥ +3**（验证 HIGH 问题真正修复，不是表面替换）。即使首次分数已 ≥ 80 也强制走，因为 ：prose_quality 81 含 3 HIGH，polish 后仍 81——显示修复无效但因 ≥75 跳过复测。
- 复测均使用 `_recheck_ch{NNNN}.json` 作为输出文件名

**补充**：Step 3 prose-quality=81 含 3 HIGH（PRO_001/PRO_002/PRO_003），polish 后名义"修了"但 不是X是Y 16→14、像 16→11、D-3/D-2/D-1 仅替换标签——量化未达 target，复测会暴露分数不动甚至下滑。HIGH 全面复测档会在所有这种情况触发，通过对比 before/after 分数来 GATE 真伪修复。

**Round 21.2 血教训背景**：Ch16 的 emotion 78 / pacing 78 / high-point 79 / prose 82 / ooc 81 五个维度全部相对 Ch15 下滑 8-16 分，但因为都 ≥75，旧 trigger 不命中，post_polish_recheck 整章未触发，结果 polish 是否真起效完全不可验证。新档命中后，下次再发生类似 −10 量级回归会被 Step 4.5 强制兜住。

**执行模板**：
```bash
# 在 Step 4 complete-step 前
# 对每个首次分数 <75 的 checker 做 Task 复测
Task(pacing-checker, chapter=N, chapter_file=..., post_polish=true, prev_score=58)

# 更新 checker_scores（自动重算 overall 为 13 canonical 平均 + 同步 overall_score）
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" \
  state update --set-checker-score '{"chapter":N,"checker":"pacing-checker","score":90}'

# 追加 post_polish_recheck（before/after/delta/reason）
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" \
  state update --append-recheck '{"chapter":N,"checker":"pacing-checker","before":58,"after":90,"reason":"Beat2 拆段+B3 差异化+B4 扩写"}'
```

**CLI 参数契约**（R3.1 实现 ）：
- `--set-checker-score` 参数：`{chapter, checker (canonical 13 之一), score}` · 自动重算 `checker_scores.overall` 与 `overall_score`
- `--append-recheck` 参数：`{chapter, checker, before, after, reason?}` · `delta = after - before` 自动计算
- **两个 CLI 是 Step 4.5 的唯一正确接口**，禁止用 `state update --set-chapter-meta-field` 写 `checker_scores` 子键（白名单不含），也禁止走 data-agent `process-chapter` 全量回写（容易 hallucinate `before` 值 · 见 R2）

**硬规则**：
- 复测 checker ≥ 75：更新 checker_scores · 重算 overall · 记入 post_polish_recheck
- 复测 checker 仍 < 75：Step 4 未完成，继续 polish 直到 ≥ 75（或回到 Step 2A 重写该 beat）
- **不许**因为“不想再跑”而跳过复测；Step 6 审计 C6 会 block

**审计兼容性**：
- audit-agent 读 `chapter_meta.post_polish_recheck` 判断修前/修后数据
- 如无该字段且 Step 4 fixes 列表含 checker id 的 PACE_/FLOW_/etc，audit C6 自动 warn

**字数预算硬约束**：

：writer 首稿 1930 字（-33% 预算 2900）· 对话占比 0.124（<0.20 硬线）· 用户 3 次手动扩写才达标。根治在 Step 2A 执行包（`context-agent` 与 `build_execution_package.py`）硬写入：

- **首稿总字数 ≥ hard_min**（默认 2200）：低于 hard_min 自动 post_draft_check fail
- **每 Beat 字数 ≥ 目标 85%**：如规划 700 字，首稿该 Beat < 595 字 → post_draft_check warn `BEAT_UNDERRUN`
- **对话占比 ≥ 0.20**（饭局/对峙/情感章 ≥ 0.25）：低于阈值 post_draft_check fail `DIALOGUE_RATIO`
- **chapter_type 特例**：空间视觉章/纯动作章可将 dialogue_min 降到 0.10，必须在 `context_contract.structural_exemptions.dialogue_ratio_override` 声明
