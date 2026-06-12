# webnovel-write · Step 7 Git 备份 + Step 8 Post-Commit Polish

> Round 29 Phase 2 由 SKILL.md 原文拆分（lazy-load）。进入对应 Step 时必须先加载本文件全文，
> 按其中规则执行；跨步骤硬约束 / 章节间闸门 / 充分性闸门见 SKILL.md 骨架。

### Step 7：Git 备份 + workflow 收尾（必须同时完成）

**⚠ 顺序严格固定**：

> **关键时序约束**：hygiene_check + pre_commit_step_k 这两个**前置闸门**必须在 **Step 6 已 complete-step** 之后、**Step 7 还没 start-step** 之前的 **step gap** 状态下执行。
>
> **不能**先 `workflow start-step --step-id "Step 7"` 再跑 hygiene_check —— hygiene 的 H3 检查项会判定为“current_task running 且正在执行 Step 7：不应在 step 中间调 hygiene”并 P0 fail（即使其他质量项全过）。
>
> 正确顺序：
> ```
> Step 6 complete-step  →  (step gap)  →  hygiene_check + pre_commit_step_k  →
>   start-step Step 7  →  git commit  →  complete-step Step 7  →  complete-task
> ```

**commit 前硬闸门**：
```bash
python -X utf8 "${SCRIPTS_DIR}/pre_commit_step_k.py" ${chapter_num} --project-root "${PROJECT_ROOT}"
```
2 类检查（详见 `references/post-draft-gate.md`）：
1. 核心设定集文件（`.webnovel/step_k_config.json` 配置，默认 伏笔追踪/资产变动表/主角卡）含 `[Ch{N}]` 标注
2. `chapter_meta.{NNNN}.foreshadowing_planted` 里新增伏笔 ID 在 `设定集/伏笔追踪.md` 可查

**为什么需要这个闸门**：Data Agent Step K 会把新增实体/状态写入 index.db + state.json，但 Markdown 追加通常被推给主 agent。若主 agent 忘记追加，设定集与 state 长期脱节，下章 context-agent 读不到新增，质量连锁下降。本闸门阻塞 commit 直到追加完成。

exit=0 后才能走 commit：
```bash
# 前置：AI 必须先在 shell 里 export 下列变量（来自 Step 3 / 章节大纲）。
# 未 export 会让后续命令产出非法 JSON（'"overall_score":' 后面为空）。
export chapter_num=3
export chapter_padded=0003
export title="本章标题（去除特殊字符）"
export overall_score=92          # 来自 Step 3 的合并加权分（必须整数）
export audit_decision="approve_with_warnings"  # Step 6 决议

# 0) commit 前硬闸门：hygiene_check 必须 exit 0
# ⚠ MUST run in step gap (after Step 6 complete-step, BEFORE Step 7 start-step)
# ⚠ NEVER run inside Step 7 active state — hygiene H3 will P0 fail
python -X utf8 "${PROJECT_ROOT}/.webnovel/hygiene_check.py" ${chapter_num} || { echo "FAIL: hygiene_check 未通过，禁止 commit"; exit 1; }

# 1) start-step Step 7（hygiene 通过后才登记 Step 7 active）
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow start-step --step-id "Step 7" --step-name "Git backup"

# 2) 执行 git commit
git add .
git -c i18n.commitEncoding=UTF-8 commit -m "第${chapter_num}章: ${title}"
export COMMIT_SHA=$(git rev-parse HEAD)

# 3) complete-step 带语义 artifact（必须在 git commit 成功后调用）
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow complete-step --step-id "Step 7" --artifacts "{\"commit\": \"${COMMIT_SHA}\", \"branch\": \"master\", \"pushed\": false}"

# 4) complete-task 收尾（标记整个 webnovel-write 任务结束）
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow complete-task --artifacts "{\"chapter_completed\": true, \"commit\": \"${COMMIT_SHA}\", \"overall_score\": ${overall_score}, \"audit_decision\": \"${audit_decision}\"}"
```

**JSON 转义说明**：bash 的 `"..."` 字符串内需要 `\"` 转义内部双引号。`${var}` 替换仍生效。**避免**用单引号 `'...'` 包 artifact，因为单引号内 `${var}` 不会替换。

**PowerShell 专属转义**：
PowerShell 下 `--artifacts '{"commit": "..."}'` 会导致 Python argparse 看到 `{commit: ...}` 缺双引号解析失败。必须用反斜杠转义：
```powershell
$j = '{\"commit\": \"abc\", \"branch\": \"master\"}'
python -X utf8 ... workflow complete-step --step-id "Step 7" --artifacts $j
```
或用 here-string + 双引号：
```powershell
$j = @"
{"commit": "$COMMIT_SHA", "branch": "master"}
"@
```

**工作流 unfail 恢复路径**：
若 complete-step 因 JSON escape 错误失败 → 紧接 complete-task 会把 task 标 failed → 此时用 `--force` 恢复：
```bash
# 确认 Step 1-7 全部 completed + 无 active step running 时：
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow complete-task --force --artifacts "${final_artifacts_json}"
# 输出：🔧 --force 已解除 failed 状态 · 🎀 任务完成
```
`--force` 的硬约束：
- 所有 `REQUIRED_STEPS`（Step 1/2A/3/3.5/4/5/6/7）的 id 必须在 `completed_steps` 列表里
- `current_step` 必须已 None 或 status ∈ {completed}
- 否则拒绝并打印 diag 信息

规则：
- 提交时机：Step 6 审计通过 + hygiene_check 通过 + pre_commit_step_k 通过后最后执行。
- 提交信息默认中文，格式：`第{chapter_num}章: {title}`；若 Step 6 决议为 `approve_with_warnings`，追加 `[audit:warn:layerX]` 后缀。
- 若 commit 失败：先 `workflow fail-step --step-id "Step 7" --reason "git commit failed: ..."`，再报告失败原因与未提交文件范围；**不得调用 complete-task**。
- `complete-task` 必须在 git commit 成功后才能调用，顺序不可调换。
- **违规场景**（任何一条都视为 Step 7 失败）：
  - 跳过 hygiene_check 直接 commit
  - 跳过 start-step/complete-step 直接 commit
  - 用 Edit/Write 工具直接改 `workflow_state.json`
  - complete-step artifact 为空或只含 `{"ok": true}` / `{"v2": true}`

### Step 8：Post-Commit Polish Loop（提交后再润色循环 新增）

**定位**：Step 7 commit 完成后，**任何对正文的修改**都必须走本步骤，**严禁裸跑 `git commit`**。

**为什么需要**：
Round 13 v2 上线 13 checker 后，作者/AI 经常根据 reader-critic / reader-naturalness 反馈手动改正文，然后裸跑 `git commit -m "v3 polish"`。结果：
- `post_draft_check.py` 不再跑 → 58 个 ASCII 引号漏过去（H5 P0 fail）
- `hygiene_check.py` 不再跑 → `word_count` 漂移（state=3498 vs actual=3084）
- `workflow_state.json` 不再登记 → polish 任务在工作流系统里“不存在”
- `chapter_meta.narrative_version` 不变 → 下章 context-agent 看到旧版本
- `checker_scores` 仍是旧 10 维 → A2 审计跨章 trend 失真

**触发场景**（满足任一即必须走 Step 8）：
- 根据读者视角 checker 反馈修正语病/AI 腔/逻辑跳跃
- 根据外部模型 reader_flow 反馈修读者卡点
- 修复 hygiene_check 报告的 P1 警告（如 ASCII 引号、字数误差）
- 任何在 Step 7 commit 之后对 `正文/第NNNN章*.md` 的内容修改

**唯一入口**（禁止替代）：

```bash
python -X utf8 "${SCRIPTS_DIR}/polish_cycle.py" ${chapter_num} \
  --project-root "${PROJECT_ROOT}" \
  --reason "读者视角 6 medium 修复" \
  --narrative-version-bump \
  --round-tag round13v2 \
  [--checker-scores '{"reader-naturalness-checker": 91, "reader-critic-checker": 88}']
```

`polish_cycle.py` 自动完成 7 步（**commit 是最后一步原子落盘**，与 Step 7 对称设计）：
1. **变化检测**：`git show HEAD:正文/...` vs 工作区文件，无变化默认拒绝（`--allow-no-change` 例外）
2. **`post_draft_check`**：必须 exit 0（ASCII 引号/Markdown/字数/U+FFFD/虚词等 7 类硬约束）
3. **state.json 同步**：
   - `chapter_meta.{NNNN}.word_count` ← 实测中文字符数
   - `chapter_meta.{NNNN}.narrative_version` ← `vN+1`（或手动指定）
   - `chapter_meta.{NNNN}.updated_at` ← 当前 UTC
   - `chapter_meta.{NNNN}.polish_log[]` ← 追加 `{version, timestamp, notes}`
   - 可选：`chapter_meta.{NNNN}.checker_scores` ← 补录新 checker 分
4. **`hygiene_check`**：必须 exit 0（P0 fail = block，P1 warn 允许继续但建议修）
5. **workflow 预登记**：在 `history[]` 追加 `task_id=polish_NNN`，`Step 8` artifact 含 `narrative_version` / `reason` / `diff_lines` / `state_diff`（`commit_sha=None` 占位）— 与 Step 7 的 `start-step` 对称，确保 commit 里含 workflow 痕迹
6. **`git commit`**（真正最后一步原子落盘）：一次 commit 包含正文 + `state.json` + `workflow_state.json` 三者全部变更。消息格式 `第N章 v{X}: {reason} [polish:roundN]`
7. **回填 commit_sha**：把 commit 的 sha 写回 workflow_state 刚登记的 polish task — 这是唯一尾巴，与 Step 7 的 `complete-step` 尾巴性质一致；即使回填失败，commit message `[polish:{round_tag}]` 标签 + `git log --grep` 也能重建 sha 映射

**硬约束**：
- 退出码 0 = 全通过 + commit 完成；1 = 检查 fail 必须先修；2 = 结构错（无变化/state 缺失）；3 = git fail
- `--no-commit` 模式仅供 dry-run / CI；正常流程必须 commit
- **禁止**：`git commit -m "polish"` / `git commit --amend --no-verify` 等绕过手段
- **禁止**：用 Edit/Write 直接改 `state.json` 的 `word_count` / `narrative_version`（必须经 polish_cycle.py）
- 同一章节多轮 polish 应每轮独立调用一次（每轮 v3 → v4 → v5），保留完整 polish_log
- **polish 轮数硬上限**（`--max-rounds` 默认 3）：
  - 单章 polish_log >= 3 轮 → polish_cycle.py exit 1 给出协议提示
  - 突破上限必须 `--allow-exceed-max-rounds --deviation-reason "为何还要再修"`
  - deviation 自动写入 `audit_reports/chNNNN.json.deviations[]`
  - 配套 H27 sunk cost 警报（v3+polish≥2+5 项 80 一线 → P1 提示考虑 Step 0 重写）
  - Ch1 v7 11 轮 polish 沉没成本加法导向 polish 会陷死循环

**与 Step 1-7 的关系**：
- Step 8 是 **Step 7 之后的开放循环**，可无限次触发（每次产生一个 `polish_NNN` task）
- Step 8 **不替代** Step 1-7：从草稿到首次 commit 必须走完整 Step 1-7
- Step 8 的 `Step 8` 只是 `completed_steps` 里的单步标识，不与 Step 1-7 序号冲突
- 触发新章节写作时，下章 context-agent 读取 `state.json` 自动获取最新 `narrative_version` 与 polish_log

完整规范见 `references/post-commit-polish.md`（含恢复策略、多轮 polish、跨章影响、审计兼容性）。

## 本步专属硬约束（Round 29 自 SKILL.md 流程硬约束迁入）

- **禁止 META_DRIFT 阻塞 commit (Round 28.30 自动根治)**：Step 4/6 polish 修复后只改 word_count/score 不改 updated_at → 正文 mtime > chapter_meta.updated_at + 300s → pre_commit_step_k.py META_DRIFT 阻塞 commit。**根治**：state_manager.py 已加 auto-touch updated_at（任何非 updated_at 字段修改后自动同步），无需手动 set-chapter-meta-field updated_at。
