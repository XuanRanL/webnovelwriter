---
name: webnovel-write
description: Writes webnovel chapters (default 2200-3500 words). Use when the user asks to write a chapter or runs /webnovel-write. Runs context, drafting, review, polish, and data extraction.
allowed-tools: Read Write Edit Grep Bash Task
---

# Chapter Writing (Structured Workflow)

## 目标

- 以稳定流程产出可发布章节：优先使用 `正文/第{NNNN}章-{title_safe}.md`，无标题时回退 `正文/第{NNNN}章.md`。
- 默认章节字数目标：**弹性区间 2200-3500**（SSOT = `state.project_info.word_count_policy` · 根据章节类型在 chapter_type_guide 里选）。

  **字数弹性模型（Round 15.1 · 2026-04-22 根治三次漂移复现）**：
  - **SSOT 字段**：`state.project_info.word_count_policy.hard_min` / `hard_max`（默认 2200/3500）
  - **弹性准则**：根据章节类型在硬区间内自由浮动（约 ±400）· `average_words_per_chapter_target=3000` 只是项目级软目标**参考**，**不是**单章硬下限
  - **chapter_type_guide 推荐区间**：
    - 过渡章/铺垫章：2200-2800
    - 推进章/日常章：2600-3200（默认）
    - 情感章/揭秘章：2800-3400
    - 战斗章/高潮章/卷末章：3000-3500（大纲/用户明确可破上限）
  - **禁止伪造区间**：禁止在 editor_notes / context JSON / 审查报告写 2800-3500 / 2700-3200 / 2400-3200 等自造区间（硬 min/max 之外的数字）· 禁止引用不存在的 state 字段名（如 `target_words_per_chapter_target`）
  - **冲突解决**：editor_notes（audit-agent 写）与 state.json SSOT 冲突时**以 state.json 为准**，context-agent 静默覆盖并在执行包 `warnings[]` 追加 `EDITOR_NOTES_WORD_COUNT_DRIFT`
  - **硬闸门**：post_draft_check.py 第 8 项 warn 扫描 editor_notes/context 字数漂移；audit-agent.md §8 block 凭印象自造区间
- 保证审查、润色、数据回写完整闭环，避免“写完即丢上下文”。
- 输出直接可被后续章节消费的结构化数据：`review_metrics`、`summaries`、`chapter_meta`。

## 执行原则

1. 先校验输入完整性，再进入写作流程；缺关键输入时立即阻断。
2. 审查与数据回写是硬步骤，`--fast`/`--minimal` 只允许降级可选环节。
3. 参考资料严格按步骤按需加载，不一次性灌入全部文档。
4. Step 2B 与 Step 4 职责分离：2B 只做风格转译，4 只做问题修复与质控。
5. 任一步失败优先做最小回滚，不重跑全流程。

## 模式定义

- `/webnovel-write`：Step 0 → 0.5 → 1 → 2A → 2B → 3+3.5(并行) → 4 → 5 → 6 → 7
- `/webnovel-write --fast`：Step 0 → 0.5 → 1 → 2A → 3+3.5(并行) → 4 → 5 → 6 → 7（跳过 2B）
- `/webnovel-write --minimal`：Step 0 → 0.5 → 1 → 2A → 3（仅3个基础审查，跳过3.5）→ 4 → 5 → 6 → 7

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
- **禁止临时改名**：不得将 Step 的输出产物改写为非标准文件名或格式。
- **禁止自创模式**：`--fast` / `--minimal` 只允许按上方定义裁剪步骤，不允许自创混合模式、"半步"或"简化版"。
- **禁止自审替代**：Step 3 审查必须由 Task 子代理执行，主流程不得内联伪造审查结论。
- **禁止主观估分**：`overall_score` 必须来自审查子代理的聚合结果，不得因为"子代理还没返回"而自行估算分数。
- **禁止源码探测**：脚本调用方式以本文档与 data-agent 文档中的命令示例为准，命令失败时查日志定位问题，不去翻源码学习调用方式。
- **禁止裸跑 polish commit**（2026-04-20 新增）：Step 7 commit 之后任何对正文文件（`正文/第NNNN章*.md`）的修改，**必须**通过 `polish_cycle.py`（Step 8）完成，**严禁**直接 `git add . && git commit -m "polish"` 或 `git commit --amend`。裸跑会绕过 `post_draft_check`/`hygiene_check`，让 ASCII 引号、word_count 漂移、checker 数据滞留，并且 polish 任务在 `workflow_state.json` 不留痕。

### 章节间闸门（Chapter Gate）

在开始下一章的任何步骤（包括 Step 0）之前，必须验证当前章的以下条件全部满足：

1. Step 3 的内部 checker 全部返回并汇总出 overall_score。**术语固定**（见 `feedback_checker_count_13`）：`checker` = 跑的 subagent 数量 = 评分维度数量（**Round 13 v2 取消 veto 架构**，全部 checker 平等参与评分）。标准/`--fast` = **13 checker / 13 评分维度**（2 读者视角维度：naturalness + reader-critic，11 工艺维度含 flow-checker）。`--minimal` = **5 checker**（naturalness + reader-critic + consistency + continuity + ooc）。`overall_score = avg(所有评分维度)`。**两个读者视角 checker 不 block 流程**，其 problems 和其他 checker 同等进入 Step 4 定向修复。极端情况（Step 4 修复后 critical 仍未消除）才回 Step 2A 重写。
2. Step 3.5 的 9 个外部模型审查完成（核心3模型 kimi/glm/qwen-plus 必须成功，补充6模型失败不阻塞），每模型审查 **13 个维度**（11 工艺维度 + naturalness_dim + reader_critic_dim，Round 13 v2 新增后 2 个，让外部模型也做读者视角评估）（`--minimal` 模式跳过此条件）
3. 所有 critical 问题已修复，high 问题已修复或有 deviation 记录
4. 审查报告 .md 文件已生成（标准/`--fast` 模式含内部 13 评分维度分数 + 外部 14 模型×13 维度评分矩阵（Round 14+）；`--minimal` 模式仅含内部 5 评分维度分数）
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
- L1：每步仅加载该步“必读”文件。
- L2：仅在触发条件满足时加载“条件必读/可选”文件。

路径约定：
- `references/...` 相对当前 skill 目录。
- `../../references/...` 指向全局共享参考。

## References（逐文件引用清单）

### 根目录

- `references/step-3-review-gate.md`
  - 用途：Step 3 审查调用模板、汇总格式、落库 JSON 规范。
  - 触发：Step 3 必读。
- `references/step-3.5-external-review.md`
  - 用途：Step 3.5 外部模型审查完整规范（14模型架构/供应商 fallback 链/Prompt模板/输出JSON Schema/路由验证/审查报告模板）。
  - 触发：Step 3.5 必读。
- `references/step-5-debt-switch.md`
  - 用途：Step 5 债务利息开关规则（默认关闭）。
  - 触发：Step 5 必读。
- `references/step-6-audit-gate.md`
  - 用途：Step 6 审计闸门调用模板、执行时序、决议逻辑、产物约定、失败恢复路径。
  - 触发：Step 6 必读（主流程 + audit-agent 共同消费）。
- `references/step-6-audit-matrix.md`
  - 用途：Step 6 七层审计矩阵（A 过程真实性 / B 跨产物一致性 / C 读者体验 / D 作品连续性 / E 创作工艺 / F 题材兑现 / G 跨章趋势），约 70 个检查项。
  - 触发：Step 6 必读（audit-agent 执行时加载）。
- `../../references/shared/core-constraints.md`
  - 用途：Step 2A 写作硬约束（大纲即法律 / 设定即物理 / 发明需识别）。
  - 触发：Step 2A 必读。
- `references/polish-guide.md`
  - 用途：Step 4 问题修复、Anti-AI 与 No-Poison 规则。
  - 触发：Step 4 必读。
- `references/writing/typesetting.md`
  - 用途：Step 4 移动端阅读排版与发布前速查。
  - 触发：Step 4 必读。
- `references/style-adapter.md`
  - 用途：Step 2B 风格转译规则，不改剧情事实。
  - 触发：Step 2B 执行时必读（`--fast`/`--minimal` 跳过）。
- `references/style-variants.md`
  - 用途：Step 1（内置 Contract）开头/钩子/节奏变体与重复风险控制。
  - 触发：Step 1 当需要做差异化设计时加载。
- `../../references/reading-power-taxonomy.md`
  - 用途：Step 1（内置 Contract）钩子、爽点、微兑现 taxonomy。
  - 触发：Step 1 当需要追读力设计时加载。
- `../../references/genre-profiles.md`
  - 用途：Step 1（内置 Contract）按题材配置节奏阈值与钩子偏好。
  - 触发：Step 1 当 `state.project.genre` 已知时加载。
- `references/writing/genre-hook-payoff-library.md`
  - 用途：电竞/直播文/克苏鲁的钩子与微兑现快速库。
  - 触发：Step 1 题材命中 `esports/livestream/cosmic-horror` 时必读。
- `references/post-commit-polish.md`
  - 用途：Step 8（Post-Commit Polish）完整规范：触发场景、polish_cycle.py 用法、多轮 polish、跨章影响、审计兼容性、恢复策略。
  - 触发：Step 7 commit 之后任何修改正文前必读。
- `references/gate-matrix.md`
  - 用途：充分性闸门 vs hygiene_check H* 项的一一对应表 + 多层防御设计 + 同步维护规则（Round 14.5.2 新增）。
  - 触发：新增/修改/删除任一闸门前必读；调试闸门打架时必读。

### writing（问题定向加读）

- `references/writing/combat-scenes.md`
  - 触发：战斗章或审查命中“战斗可读性/镜头混乱”。
- `references/writing/dialogue-writing.md`
  - 触发：审查命中 OOC、对话说明书化、对白辨识差。
- `references/writing/emotion-psychology.md`
  - 触发：情绪转折生硬、动机断层、共情弱。
- `references/writing/scene-description.md`
  - 触发：场景空泛、空间方位不清、切场突兀。
- `references/writing/desire-description.md`
  - 触发：主角目标弱、欲望驱动力不足。
- `references/writing/classical-references.md`
  - 用途：典故/诗词/史料/原创口诀/互联网梗的融入技巧、密度控制、"典故即伏笔"技法、项目设定集模板。
  - 触发：Step 1 设计引用方案时 / 审查命中"引用生硬/炫学/出处错误" / Step 4 修复引用问题。

## 工具策略（按需）

- `Read/Grep`：读取 `state.json`、大纲、章节正文与参考文件。
- `Bash`：运行 `extract_chapter_context.py`、`index_manager`、`workflow_manager`。
- `Task`：调用 `context-agent`、审查 subagent、`data-agent` 并行执行。

## 交互流程

### Step 0：预检与上下文最小加载

必须做：
- 解析真实书项目根（book project_root）：必须包含 `.webnovel/state.json`。
- 校验核心输入：`大纲/总纲.md`、`${CLAUDE_PLUGIN_ROOT}/scripts/extract_chapter_context.py` 存在。
- 规范化变量：
  - `WORKSPACE_ROOT`：Claude Code 打开的工作区根目录（可能是书项目的父目录，例如 `D:\wk\xiaoshuo`）
  - `PROJECT_ROOT`：真实书项目根目录（必须包含 `.webnovel/state.json`，例如 `D:\wk\xiaoshuo\凡人资本论`）
  - `SKILL_ROOT`：skill 所在目录（固定 `${CLAUDE_PLUGIN_ROOT}/skills/webnovel-write`）
  - `SCRIPTS_DIR`：脚本目录（固定 `${CLAUDE_PLUGIN_ROOT}/scripts`）
  - `chapter_num`：当前章号（整数）
  - `chapter_padded`：四位章号（如 `0007`）

环境设置（bash 命令执行前）：
```bash
# Round 15.2 (2026-04-23)：CLAUDE_PLUGIN_ROOT 在某些 shell（如 Git Bash）不会被自动 export。
# AI 应先用下面这段自动推导 fallback 代替 `:?CLAUDE_PLUGIN_ROOT is required` 硬失败。
# 根因：Ch5 Step 0 preflight 在 bash 里直接报 "CLAUDE_PLUGIN_ROOT: CLAUDE_PLUGIN_ROOT is required"，
#      AI 需要手工 export 才能继续。Round 15.2 加入这套 fallback 解析后，Ch6+ 可免手工导出。
if [ -z "${CLAUDE_PLUGIN_ROOT:-}" ]; then
  # 从 PATH 里的 plugin bin 目录反推（claude-code 启动时会把 {PLUGIN_ROOT}/bin 加到 PATH）
  _pg=$(echo "$PATH" | tr ':' '\n' | grep -i "plugins/cache/webnovel-writer.*/bin$" | head -1)
  if [ -n "$_pg" ]; then export CLAUDE_PLUGIN_ROOT="${_pg%/bin}"; fi
  # 如果上面没找到，再用常见位置兜底（按优先级）
  for _cand in \
    "$HOME/.claude/plugins/cache/webnovel-writer-marketplace/webnovel-writer/5.6.0" \
    "C:/Users/$USERNAME/.claude/plugins/cache/webnovel-writer-marketplace/webnovel-writer/5.6.0"; do
    [ -z "${CLAUDE_PLUGIN_ROOT:-}" ] && [ -d "$_cand/scripts" ] && export CLAUDE_PLUGIN_ROOT="$_cand"
  done
fi
if [ -z "${CLAUDE_PLUGIN_ROOT:-}" ]; then
  echo "ERROR: CLAUDE_PLUGIN_ROOT 未能自动推导，请手动 export 后重试" >&2
  exit 1
fi

export WORKSPACE_ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
export SCRIPTS_DIR="${CLAUDE_PLUGIN_ROOT}/scripts"
export SKILL_ROOT="${CLAUDE_PLUGIN_ROOT}/skills/webnovel-write"

python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${WORKSPACE_ROOT}" preflight
export PROJECT_ROOT="$(python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${WORKSPACE_ROOT}" where)"
```

**硬门槛**：`preflight` 必须成功。它统一校验 `CLAUDE_PLUGIN_ROOT` 派生出的 `SKILL_ROOT` / `SCRIPTS_DIR`、`webnovel.py`、`extract_chapter_context.py` 和解析出的 `PROJECT_ROOT`。任一失败都立即阻断。

**plugin 同步闸门**（preflight 两个非阻断警告，必须在 Step 1 前全部清零）：

Claude Code 的 plugin 系统是**三层缓存架构**：
```
fork (你改代码的地方) → marketplace mirror (~/.claude/plugins/marketplaces/...) → cache (~/.claude/plugins/cache/...)
```
AI 运行时通过 `CLAUDE_PLUGIN_ROOT` 从 **cache** 加载脚本和 subagent 定义，**不从 fork 读取**。fork 修改后 cache 不会自动同步——这是 Ch6 flow-checker 空跑的根因（fork 已含 flow-checker，但 cache 是旧版）。

### warning 1: `ERROR agents_sync`

说明 plugin `agents/` 新增/修改的 subagent 未同步到**工作区** `.claude/agents/`（工作区 fallback 层，独立于 cache）。Task(subagent) 会静默 fallback 到 general-purpose，导致 checker 空跑（Ch6 血教训：flow-checker 加入后未同步到工作区，Step 3 Batch 2 只实际跑了 5 个而非 6 个，审查报告里写"内部 10 维度"其实应该是 11）。

一键修复：
```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" sync-agents
```

### warning 2: `ERROR cache_sync`

说明 fork 内容与 plugin cache 不一致（通常因为 `git pull` 后没同步）。**直接后果：AI 跑的是 cache 的旧代码**，fork 的 bug fix / 新 checker / 新维度都不生效。例证：

- 2026-04-13 c511802 commit 在 fork 加入 reader_flow，但 cache 没同步 → Ch6 外部审查只跑 10 维度（应 11）
- 2026-04-13 某次修复把 chapter_audit.py 中文注释写坏，cache 同步了 37 行 `??????` → 后续审计 evidence 全乱码

**注意：`sync-cache` 必须从 fork 跑，不能从 cache 跑**（Ch7 RCA：从 cache 跑会自反拷贝 + 无法找到 fork）。生产里 AI 会通过 `CLAUDE_PLUGIN_ROOT`（= cache 路径）跑 `webnovel.py`，所以：

一键修复（**必须 cd 到 fork 目录跑，不是从 cache 跑**）：
```bash
# 从 fork 目录跑（替换为你的 fork 路径）：
cd /path/to/fork/webnovel-writer
python -X utf8 scripts/webnovel.py sync-cache
```

该命令：
1. 把 fork 所有文件复制到 `~/.claude/plugins/cache/{marketplace}/{plugin}/{version}/`，按 bytes diff 只更新变化文件
2. 清理 cache 里的 `.pyc`（防止 stale bytecode shadow 新 `.py`）
3. 写入 `~/.claude/plugins/webnovel-fork-registry.json`，登记 fork 路径，让后续 preflight（从 cache 跑）也能检测到漂移

**`preflight` 的 cache_sync 检查**（2026-04-16 Ch7 RCA 修复后的行为）：
- 从 fork 跑：直接 fork↔cache 漂移对比，有漂移 → ERROR
- 从 cache 跑（生产路径）：先通过 `WEBNOVEL_FORK_PATH` env var 或 fork-registry 找 fork；找到则对比；找不到则输出 NOTE "fork 未登记，跳过"（不阻断，但提示修复）
- **从 fork 跑过一次 sync-cache 后，registry 自动建立，后续从 cache 跑也能查漂移**

### 硬规则

**任何 `ERROR agents_sync` / `ERROR cache_sync` / `ERROR polish_drift` 必须在 Step 1 前清零**。不得"跳过 warning 开始写章"，因为：
- agents_sync 漂移 → Task checker 空跑（你看不见 fallback，章节走完了才发现审查报告维度少了）
- cache_sync 漂移 → 所有 fix / 新功能不生效（你 commit 了但 AI 跑的是老代码）
- **polish_drift P0 漂移**（Round 14.5.2）→ 上一章正文已手动改但未走 polish_cycle，直接进入下章会污染上下文。修法：对每个 drifted 章节运行 `polish_cycle.py <N> --reason '补录裸跑 commit' --narrative-version-bump`；若是 WIP（未完成）改动则 `git stash` 暂存

**触发 sync-cache 的时机**（硬约束）：
1. 每次 `git pull` 或 `git checkout` 切换 fork 分支后
2. 每次你修改 plugin 源码文件（`webnovel-writer/scripts/*.py` / `agents/*.md` / `skills/*.md` / `references/*.md`）后
3. 每次使用 Claude Code 开始新 session 时（preflight 会提示）

**预检一次通过模板**（推荐放 Step 0 起始）：
```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" preflight
# 若看到 ERROR agents_sync：
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" sync-agents
# 若看到 ERROR cache_sync（注意：SKILL 里的 SCRIPTS_DIR 指向 cache，sync-cache 从 cache 跑会失败，
# 必须 cd 到 fork 再跑）：
#   cd /path/to/fork/webnovel-writer
#   python scripts/webnovel.py sync-cache
# 若看到 NOTE "invoked_from_cache 且 fork 未登记"：
#   说明从 cache 跑 preflight 时找不到 fork。从 fork 跑一次 sync-cache 即自动登记 registry。
# 然后重跑 preflight 确认全 OK
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" preflight
```

**可选：安装 git pre-commit hook**（Round 14.5.2 · 硬技术拦截裸跑 polish commit）：

```bash
# 一次性安装（幂等，重跑无副作用）
python -X utf8 "${SCRIPTS_DIR}/install_git_hooks.py" --project-root "${PROJECT_ROOT}"

# 或卸载（仅恢复到 webnovel hook 安装前的状态）
python -X utf8 "${SCRIPTS_DIR}/install_git_hooks.py" --project-root "${PROJECT_ROOT}" --uninstall
```

安装后效果：任何 `git commit` 带 staged 章节文件但 message 不符合 `第N章 v{X}: ... [polish:...]`（polish_cycle 产出）或 `第N章: {title}`（Step 7 产出）格式时，pre-commit 会阻断并打印修复提示。可用 `git commit --no-verify` 主动绕过（但会被下次 preflight 的 polish_drift 检查到）。

**非强制安装**：preflight + hygiene_check 已是主要防线；此 hook 是锦上添花的第三层。若你只用 Claude Code 的 webnovel skill 流程，可以不装；若你担心 AI 偶尔手滑裸跑 commit，推荐装上。

典故引用库检查（非阻断，仅提示）：
```bash
test -f "${PROJECT_ROOT}/设定集/典故引用库.md" && echo "典故引用库: 已就绪" || echo "典故引用库: 未创建（建议创建以提升文化质感，模板见 references/writing/classical-references.md）"
test -f "${PROJECT_ROOT}/设定集/原创诗词口诀.md" && echo "原创诗词口诀: 已就绪" || echo "原创诗词口诀: 未创建（可选）"
```

输出：
- “已就绪输入”与”缺失输入”清单；缺失则阻断并提示先补齐。
- 典故引用库存在状态（不阻断，仅提示建议）。

### Step 0.5：工作流登记（必做，不可伪造）

工作流登记是 Step 6 Layer A（过程真实性）和 hygiene_check 的信任基础。**禁止使用 `|| true` 吞掉错误，禁止手动编辑 workflow_state.json，禁止用 `{"v2": true}` 之类占位 artifact 填充**。

```bash
# 章节开始：start-task 必须成功（失败则阻断）
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow start-task --command webnovel-write --chapter ${chapter_num}

# 每个 Step 开始前：start-step（必须成功）
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow start-step --step-id "Step 1" --step-name "Context Agent"

# Step 执行完毕：complete-step 必须带语义 artifact（不可只写 {"ok": true} 或 {"v2": true}）
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow complete-step --step-id "Step 1" --artifacts '{"ok": true, "file": ".webnovel/context/ch0001_context.json", "snapshot": ".webnovel/context_snapshots/ch0001.json"}'

# 全部 Step（Step 1 → Step 7）完成后：complete-task 必须成功
# 注：complete-task 不受 REQUIRED_ARTIFACT_FIELDS 约束，但仍应给真实字段。示例里的 ${COMMIT_SHA}/${overall_score}
# 必须是已定义的 shell 变量，不得是 <sha>/<int> 占位。
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow complete-task --artifacts "{\"chapter_completed\": true, \"commit\": \"${COMMIT_SHA}\", \"overall_score\": ${overall_score}}"
```

**artifact 语义字段白名单**（每个 Step 至少一个必须存在；以 `REQUIRED_ARTIFACT_FIELDS` 代码定义为权威，本节为人读说明）：

| Step | 至少一个必需字段 | 备注 |
|---|---|---|
| Step 1 | `file` / `snapshot` / `context_file` | 执行包 JSON 路径、context_snapshot 路径 |
| Step 2A | `word_count` | 正文字数（整数，>0） |
| Step 2B | `style_applied` / `deviation_notes` | 正常执行填 `style_applied: true`；跳过则填 `deviation_notes: "..."` |
| Step 3 | `overall_score` / `checker_count` / `internal_avg` / `review_score` / `naturalness_verdict` / `naturalness_score` / `reader_critic_verdict` / `reader_critic_score` | 内部 13 checker = 13 评分维度（Batch 0 的 2 个读者视角维度：naturalness + reader-critic；Batch 1 的 6 含 flow-checker；Batch 2 的 5）；`overall_score = avg(13 维度)`。**Round 13 v2 取消 veto 架构**：两个读者视角 checker 输出 score + problems 与其他 checker 同等进入 Step 4 修复，不 block 流程。`naturalness_verdict ∈ {PASS, POLISH_NEEDED, REWRITE_RECOMMENDED, REJECT_HIGH, REJECT_CRITICAL}` / `reader_critic_verdict ∈ {yes, hesitant, no}` 作为严重度信号记录（不 block） |
| Step 3.5 | `external_avg` / `models_ok` / `external_models_ok` | 外部多模型均分（Round 14 = 14 模型） + 成功模型列表 |
| Step 4 | `anti_ai_force_check` / `polish_report` / `fixes` | `pass`/`fail`, 润色报告路径, 修复项列表 |
| Step 5 | `state_modified` / `entities` / `foreshadowing` / `scene_count` / `chapter_meta_fields` | data-agent 写库确认 + 实体/伏笔/场景计数 |
| Step 6 | `decision` / `audit_report` / `audit_decision` | `approve` / `approve_with_warnings` / `block` |
| Step 7 | `commit` / `branch` / `commit_sha` | git commit SHA + 分支名 |

**占位字段（不能单独存在）**：`v2`, `ok`, `chapter_completed`, `committed` 只有在至少一个语义字段存在时才被允许。单独用这些字段会被 `workflow_manager.complete_step` 直接 reject，参考 `_validate_artifact_has_semantic_field` 源码。

**硬规则**：
- `--step-id` 仅允许：`Step 1` / `Step 2A` / `Step 2B` / `Step 3` / `Step 3.5` / `Step 4` / `Step 5` / `Step 6` / `Step 7`
- 任何 `workflow` 子命令失败都必须立即阻断并报错，禁止 `|| true` 吞错误
- complete-step 的 artifact 必须包含至少一个上述白名单字段，否则 Step 6 Layer A 会 fail
- **严禁**任何形式的"事后补登记"：不得用 Python/Edit 工具直接修改 `workflow_state.json`，不得用 `{"v2": true}` 或类似占位填充；违规将被 hygiene_check H3/H16 检出并阻断 commit
- Step 6 审计通过后 Step 7 git commit 成功才调用 `complete-task`，**顺序不可调换**

### Search Tool 使用规则（全流程适用）

**搜索统一使用 Tavily 直连 API 脚本**（`${SCRIPTS_DIR}/tavily_search.py`），禁止使用 MCP 工具（WebSearch/WebFetch）。

**两种搜索模式**：
- **快速搜索**（大多数场景）：`python -X utf8 "${SCRIPTS_DIR}/tavily_search.py" search "查询词" --max 5`
- **深度研究**（复杂专业领域）：`python -X utf8 "${SCRIPTS_DIR}/tavily_search.py" research "研究问题" --model pro`

搜索触发规则：
- **强制触发**：涉及专业领域（机甲技术/军事/科学/法律）→ 搜索术语和真实细节
- **强制触发**：需要特定案例或参考（如"真实驾驶舱布局""地下通道地质结构"）→ 搜索具体资料
- **推荐触发**：章节类型特殊（战斗/情感/揭秘/追逐/谈判）→ 搜索该类型写作技巧
- **推荐触发**：新卷首章或Ch1-3 → 搜索同题材开篇技巧
- **推荐触发**：审查发现 HIGH 级 STYLE/PACING 问题 → 搜索改进方法
- **按需触发**：普通推进章无特殊场景 → 不搜索

各 Step 的具体搜索内容：
- Step 1：搜索本章场景类型的写作技巧（"机甲战斗 描写技巧""谈判场景 张力写法"）
- Step 2A：搜索专业领域术语和真实细节（"机甲驾驶舱 操控界面""军事通讯 加密术语"）
- Step 2B：搜索风格参考（"硬核科幻 技术描写 范例"）
- Step 4：搜索审查问题的改进方法（"对话平淡 改进技巧""节奏拖沓 如何加快"）

搜索结果归档：有价值的专业信息保存到 `调研笔记/` 对应主题文件，供后续章节复用。

**Search 失败处理协议（硬规则）**：
如果 `tavily_search.py` 执行失败（API key 缺失/全部 key 耗尽/网络超时）：
1. 立即停止当前工作
2. 告知用户搜索脚本执行失败及具体错误信息
3. 建议用户检查 API key 配置（环境变量 `TAVILY_API_KEYS` / `.env` 文件 / `~/.claude.json`）
4. 等待用户修复配置后再继续
5. 不要跳过搜索步骤直接继续——搜索获取的专业细节直接影响质量

### Step 1：Context Agent（内置 Context Contract，生成直写执行包）

使用 Task 调用 `context-agent`，参数：
- `chapter`
- `project_root`
- `storage_path=.webnovel/`
- `state_file=.webnovel/state.json`

Context Agent 额外输入（必读）：
- `设定集/伏笔追踪.md`（所有"活跃"伏笔线，确保长线伏笔不被遗忘）
- `设定集/道具与技术.md`（带章节时间线，防止引用"还没出现的"道具）
- `设定集/典故引用库.md`（若存在：检查本章大纲是否有引用锚点，推荐 0-2 条引用并标注载体与融入方式。无锚点时输出"本章不引用"。若不存在：跳过）
- `设定集/原创诗词口诀.md`（若存在：原创口诀优先级高于外部典故，检查本章是否命中使用规划。若不存在：跳过）
- `大纲/第N卷-节拍表.md`（本卷宏观节奏锚点）
- 相关角色卡的"语音规则"段落（注入 beat 的对话风格指导）

硬要求：
- 若 `state` 或大纲不可用，立即阻断并返回缺失项。
- 输出必须同时包含：
  - 8 板块任务书（核心任务/承接/角色/场景约束/时间约束/风格指导/连续性与伏笔/追读力策略）；
  - Context Contract 全字段（目标/阻力/代价/本章变化/未闭合问题/核心冲突一句话/开头类型/情绪节奏/信息密度/是否过渡章/追读力设计/爽点规划/情感锚点规划/时间约束）；
  - Step 2A 可直接消费的“写作执行包”（章节节拍、不可变事实清单、禁止事项、终检清单）。
- 写作执行包的每个 beat 必须包含：字数分配、场景描述（地点+氛围）、情绪曲线位置、感官锚点（至少1个画面）、情感锚点（情感beat：锚点类型+梯度位置）、关键对话方向+语音规则（若有对话）、本beat禁止事项。
- 合同与任务书出现冲突时，以“大纲与设定约束更严格者”为准。

输出：
- 单一”创作执行包”（任务书 + Context Contract + 直写提示词），供 Step 2A 直接消费。Context Contract 内置于 Step 1，无独立 Step。
- context-agent 必须同时把执行包落盘为 `.webnovel/context/ch{NNNN}_context.json` 与 `.webnovel/context/ch{NNNN}_context.md`（见 `agents/context-agent.md` 的 Step 7）。

Step 1 完成后必须同时验证三份产物（Step 6 A1 审计硬依赖）：
```bash
test -f "${PROJECT_ROOT}/.webnovel/context_snapshots/ch${chapter_padded}.json" && echo "snapshot OK" || { echo "FAIL: context_snapshot 未生成"; exit 1; }
test -f "${PROJECT_ROOT}/.webnovel/context/ch${chapter_padded}_context.json" && echo "execution package JSON OK" || { echo "FAIL: 执行包 JSON 未落盘"; exit 1; }
test -f "${PROJECT_ROOT}/.webnovel/context/ch${chapter_padded}_context.md" && echo "execution package MD OK" || { echo "FAIL: 执行包 MD 未落盘"; exit 1; }
```

若 context_snapshot 缺失，手动补跑：
```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" context -- --chapter ${chapter_num}
```
若执行包 JSON/MD 缺失，**禁止进入 Step 2A**，必须让 context-agent 重跑直到落盘成功。Step 1 的 `workflow complete-step` artifact 必须写 `{"ok": true, "file": ".webnovel/context/ch{NNNN}_context.json", "snapshot": ".webnovel/context_snapshots/ch{NNNN}.json"}`，严禁只写 `{"ok": true}` 或 `{"v2": true}`。

开篇黄金协议（Ch1-3 专用，叠加在标准流程之上）：
- Ch1：主角在前 500 字内出场且用行动展示（非旁白介绍）
- Ch1：核心冲突或世界规则在前 1000 字内暗示（Show not Tell）
- Ch1：章末钩子强度强制 strong
- Ch1-2：金手指至少暗示存在
- Ch1-3：人物名字总数不超过 5 个
- Ch1-3：至少 5 个冲突点
- Ch1-3：第一个场景必须包含至少 1 个具象数字（展示世界观量级）

**首章专属审查 rubric（2026-04-16 Round 10 新增 · Ch1 末世重生血教训）**：
当 chapter == 1 时，下列 checker 自动启用"首章加严"子项：

| Checker | 首章额外检查 | 触发条件 → 判级 |
|---|---|---|
| consistency-checker | **金手指激活时序交叉校验**（设定集·激活章节 vs 正文·前世闪回描写） | "前世 + 金手指具名使用"共现句 → critical |
| reader-pull-checker | **核心悬念不裸露**（payoff ≥80 章的 A 级伏笔，Ch1 不得泄露内容关键字） | 首章泄露跨卷悬念 → high |
| reader-pull-checker | **大纲爽点兑现**（卷大纲承诺本章爽点必须落点） | 承诺未兑现 → high |
| density-checker | **前 500 字认知载入量**（新设定计数） | ≥10 个 → high；7-9 个 → medium |
| density-checker | **信息锚点密度**（新设定必须有 ≥2 个具象锚） | 纯抽象新设定（无视觉/触觉/数字锚） → medium |
| emotion-checker | **首章 distress 具身化**（主角绝望情绪必须有外化生理反应） | 只内心描写无具身动作 → medium |
| pacing-checker | **前 500 字节奏分段合理性**（避免多个大信息同段轰炸） | 单段 ≥ 4 个新设定 → high |
| prose-quality-checker | **反派妥协博弈深度**（首章反派决策至少经过 1 次"先拒绝/压价" 拉扯） | 反派一次性通过主角要求 → medium |
| external-review-agent | **quote 存在性验证**（外部模型引用的"原文"必须真实在正文出现） | 幻觉 quote → 该 issue severity 降一档 |

### Step 2A：正文起草

执行前必须加载：
```bash
cat "${SKILL_ROOT}/../../references/shared/core-constraints.md"
```

硬要求：
- 只输出纯正文到章节正文文件；若详细大纲已有章节名，优先使用 `正文/第{chapter_padded}章-{title_safe}.md`，否则回退为 `正文/第{chapter_padded}章.md`。
- 默认按 2200-3500 字执行；若大纲为关键战斗章/高潮章/卷末章或用户明确指定，则按大纲/用户优先。
- 禁止占位符正文（如 `[TODO]`、`[待补充]`）。
- 保留承接关系：若上章有明确钩子，本章必须回应（可部分兑现）。
- 爽点密度约束：每 800 字至少安排 1 个微爽点（信息揭示/小胜/认可/逆转/兑现）；纯铺垫章允许降至每 1200 字 1 个，但全章不得为零。
- 典故引用融入：若 Context Agent 在执行包中推荐了引用（0-2 条），按推荐的载体和融入方式写入正文。化用 > 引用，角色内化 > 旁白注释。判断不适合时可跳过——**允许不用**。无推荐时不主动引用。（详见 `references/writing/classical-references.md`）

中文思维写作约束（硬规则）：
- **禁止"先英后中"**：不得先用英文工程化骨架（如 ABCDE 分段、Summary/Conclusion 框架）组织内容，再翻译成中文。
- **中文叙事单元优先**：以"动作、反应、代价、情绪、场景、关系位移"为基本叙事单元，不使用英文结构标签驱动正文生成。
- **禁止英文结论话术**：正文、审查说明、润色说明、变更摘要、最终报告中不得出现 Overall / PASS / FAIL / Summary / Conclusion 等英文结论标题。
- **英文仅限机器标识**：CLI flag（`--fast`）、checker id（`consistency-checker`）、DB 字段名（`anti_ai_force_check`）、JSON 键名等不可改的接口名保持英文，其余一律使用简体中文。

引号与格式清洁硬约束（起草时必须严格遵守）：
- **禁止 ASCII 半角引号 `"`**：从第一笔起就必须用 U+201C（“）/U+201D（”）中文弯引号对。不得"先用 ASCII 写完再批量替换"——批量 flip-pair 脚本在段内多重嵌套引号时会跨段翻转配对，导致 7 处+错乱（Ch6 首稿血教训）。
- **禁止 Markdown 标题/分隔线**：正文不得含 `#` / `##` / `---` / 粗体 `**...**`。章节文件直接以第一段叙事开头。
- **禁止 CRLF**：所有写入必须 LF 行尾。Windows 下注意 Write 工具的默认行尾。
- **禁止全角数字** 用于时间锚（"13:40" 保持半角，"一小时五十八分钟" 允许中文数字作叙述）。

ASCII 引号自动扫描（起草后立即执行，**任何 >0 必须停下来修**）：
```bash
python -c "
import pathlib, glob
files = glob.glob('${PROJECT_ROOT}/正文/第${chapter_padded}章*.md')
if not files: raise SystemExit('no chapter file')
t = pathlib.Path(files[0]).read_text(encoding='utf-8')
ascii_q = t.count(chr(34))
if ascii_q:
    raise SystemExit(f'FAIL: {ascii_q} ASCII 双引号（必须用 U+201C/U+201D）')
print('quote check: 0 ASCII, OK')
"
```

U+FFFD 编码验证（写入后立即执行）：
```bash
python -c "
import glob, pathlib, sys
files = glob.glob('${PROJECT_ROOT}/正文/第${chapter_padded}章*.md')
if not files: sys.exit('No chapter file found')
t = pathlib.Path(files[0]).read_text(encoding='utf-8')
n = t.count('\ufffd')
print(f'FFFD check: {n} corrupted chars in {files[0]}')
sys.exit(1 if n > 0 else 0)
"
```
若检测到 U+FFFD（通常因上下文压缩截断中文字符），立即用 Grep 定位损坏位置，用 Edit 修复，修复后重新验证。**禁止带 FFFD 进入下一步。**

**起草后硬闸门**（Step 2A 完成后、Step 2B 开始前必跑 · 2026-04-15 新增）：
```bash
python -X utf8 "${SCRIPTS_DIR}/post_draft_check.py" ${chapter_num} --project-root "${PROJECT_ROOT}"
```
7 类硬检查（详见 `references/post-draft-gate.md`）：
1. ASCII 双引号 = 0（必须 U+201C/U+201D）
2. U+FFFD = 0
3. Markdown（# 标题 / --- 分隔 / ** 粗体）= 0
4. 章号敏感禁用词（项目 `.webnovel/post_draft_config.json` 配置，如 Ch1 守夜人/桃源/灵泉）
5. 破例预算（如主角粗口 Ch1 最多 1 次）
6. 必须伏笔种子（如 Ch1 系统首发必含"你不是第一个"/"#4732"等精确短语）
7. 字数在 state.json 的 `average_words_per_chapter_min/max` 区间内

exit=0 才能进入 Step 2B。**禁止带任何 hard fail 进入 Step 3**——审查子代理的 13 内部 + 14 外部算力不应被机械问题浪费。

输出：
- 章节草稿（可进入 Step 2B 或 Step 3）。

### Step 2B：风格适配（`--fast` / `--minimal` 跳过）

执行前加载：
```bash
cat "${SKILL_ROOT}/references/style-adapter.md"
```

硬要求：
- 只做表达层转译，不改剧情事实、事件顺序、角色行为结果、设定规则。
- 对“模板腔、说明腔、机械腔”做定向改写，为 Step 4 留出问题修复空间。

输出：
- 风格化正文（覆盖原章节文件）。

U+FFFD 编码验证（同 Step 2A，风格转译后再次执行，确保转译未引入损坏）。

**起草后硬闸门再次执行**（Step 2B 后 · 转译可能引入新问题）：
```bash
python -X utf8 "${SCRIPTS_DIR}/post_draft_check.py" ${chapter_num} --project-root "${PROJECT_ROOT}"
```

### Step 3：审查（全量审查，必须由 Task 子代理执行）

执行前加载：
```bash
cat "${SKILL_ROOT}/references/step-3-review-gate.md"
```

调用约束：
- 必须用 `Task` 调用审查 subagent，禁止主流程伪造审查结论。
- **标准/--fast 模式必须分批启动**（0+6+5 三段，详见 `step-3-review-gate.md`），禁止 13 个 checker 同时并发（Claude Code Agent 并发池上限约 4-6 个）。
- 必须等待全部 checker 返回后才能统一聚合 `issues/severity/overall_score`。
- **禁止在任何 checker 仍在运行时进入 Step 4**。即使外部审查已完成，内部 checker 未全部返回也不得开始润色。
- **Round 13 v2 · 取消 veto block**：两个读者视角 checker（naturalness + reader-critic）和其他 11 个 checker **平等参与评分**。它们的 `problems` 和其他 checker 的 `issues` 同等进入 Step 4 修复。不再单方面 block 流程——因为 block 回 Step 2A 重写整章对大多数问题是浪费，Step 4 能修的就应该在 Step 4 修。

审查器（标准模式全部执行，0+6+5 三段）：
- **Batch 0（读者视角维度，2 个并行先跑，Round 13 v2）**：
  - `reader-naturalness-checker`（汉语母语自然度 · 独立于规则污染 · 专补 Ch1 v1 "陆沉在死"语病被 10+9 审查器集体放行的盲区）
  - `reader-critic-checker`（读者锐评 · 极简 prompt · 无规则约束 · 模拟追更读者本能反应 · Round 13 新增，专补"规则 pass 但读者会弃"的盲区）
  - 两个 checker 都返回 `overall_score` 和 `problems`，统一计入 `internal_avg`
  - Batch 0 先跑的原因：规模小（2 个）+ 读者视角反馈对 Batch 1/2 无依赖，早跑早反馈
- Batch 1（核心优先，6 个并发）：
  - `consistency-checker`（设定一致性）
  - `continuity-checker`（连贯性）
  - `ooc-checker`（人物OOC）
  - `reader-pull-checker`（追读力）
  - `high-point-checker`（爽点密度）
  - `flow-checker`（读者视角流畅度 · 失忆裸读协议）
- Batch 2（Batch 1 全部返回后启动，5 个并发）：
  - `pacing-checker`（节奏平衡）
  - `dialogue-checker`（对话质量）
  - `density-checker`（信息密度）
  - `prose-quality-checker`（文笔质感）
  - `emotion-checker`（情感表现）

模式说明：
- 标准/`--fast`：全量 13 个审查器（2 + 6 + 5），分段执行。
- `--minimal`：固定核心 5 个（naturalness + reader-critic + consistency + continuity + ooc），单批并发。**两个读者视角 checker 即使在 minimal 也必跑**。

审查指标落库（必做）：
```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" index save-review-metrics --data "@${PROJECT_ROOT}/.webnovel/tmp/review_metrics.json"
```

review_metrics 字段约束（当前工作流约定只传以下字段）：
```json
{
  "start_chapter": 100,
  "end_chapter": 100,
  "overall_score": 85.0,
  "dimension_scores": {"consistency-checker": 80, "continuity-checker": 90, "ooc-checker": 82, "reader-pull-checker": 87, "high-point-checker": 85, "pacing-checker": 78, "dialogue-checker": 83, "density-checker": 88, "prose-quality-checker": 82, "emotion-checker": 80, "flow-checker": 84, "reader-naturalness-checker": 86, "reader-critic-checker": 81},
  "severity_counts": {"critical": 0, "high": 1, "medium": 2, "low": 0},
  "critical_issues": ["问题描述"],
  "report_file": "审查报告/第0100章审查报告.md",
  "notes": "单个字符串；selected_checkers / timeline_gate / anti_ai_force_check 等扩展信息压成单行文本写入此字段"
}
```
- `notes` 在当前执行契约中必须是单个字符串，不得传入对象或数组。
- 当前工作流不额外传入其它顶层字段；脚本侧未在此处做新增硬校验。

硬要求：
- `--minimal` 也必须产出 `overall_score`。
- 未落库 `review_metrics` 不得进入 Step 5。
- `overall_score` 必须按 `step-3-review-gate.md` 的"内外部分数合并规则"计算：`round(internal * 0.6 + external_avg * 0.4)`。若 Step 3.5 全部失败或被模式跳过（`--minimal`），则退化为纯内部分数。
- **Round 13 v2 · naturalness 和 reader-critic 作为常规评分维度**：两个读者视角 checker 的 `overall_score` 和 `problems` 与其他 11 个 checker **平等进入 `overall_score` 聚合**，不 block 流程。它们的 high/critical problems 与其他 checker 的 issues **合并**给 Step 4 做定向修复。**极端 block 条件**：仅当 Step 4 polish 后重新审查，`naturalness` 或 `reader-critic` 仍返回 `REJECT_CRITICAL` / `will_continue_reading=no`，才回到 Step 2A 重写。背景：Ch1 v1 case 中 19 审查器 + 7 层审计给 91 分 approve_with_warnings，但用户一眼看出"陆沉在死"语病——说明规则同源污染会让评分系统集体失灵。解决方案不是 block，而是**把读者视角纳入评分，强制 Step 4 必须修**。

### Step 3.5：外部模型审查（与 Step 3 并行或紧接执行）

执行前必须加载：
```bash
cat "${SKILL_ROOT}/references/step-3.5-external-review.md"
```

硬要求：
- **必须使用 `--model-key all` 一次性执行全部 14 模型（Round 14+）**，禁止手动逐个调用（防止遗漏模型）。
- 核心3模型必须全部成功，补充6模型失败不阻塞。
- 按 reference 文件中的 Prompt 模板构建 system 消息。
- 每次 API 调用后验证路由（检查 response.model 字段）。
- Round 14+ 3-tier fallback 链：ark-coding（火山，主 · 重试 2 次）/ openclawroot（主 · fail-fast）→ siliconflow（兜底，仅 glm-5/glm-4.7/deepseek 备用）。
- 输出 JSON 必须包含 model_actual、routing_verified、provider_chain、cross_validation。
- 生成审查报告必须包含 14 模型 × 13 维度（Round 14+）（含 reader_flow + naturalness + reader_critic · Round 13 v2）评分矩阵 + 共识问题 + Step 4 修复清单。

**上下文文件准备（调用脚本前必须完成）**：

脚本从 `{PROJECT_ROOT}/.webnovel/tmp/external_context_ch{chapter_padded}.json` 加载上下文。**若文件不存在，脚本将报错退出（exit 1）**。主流程必须在调用脚本前构建此文件，包含 **14 个字段**（核心 6 + 质感 3 + 典故 2 + 状态 + 前章）：

```bash
# 收集设定集、大纲、前章正文，写入 14 字段 context JSON
python -X utf8 "${SCRIPTS_DIR}/build_external_context.py" \
  --project-root "${PROJECT_ROOT}" \
  --chapter ${chapter_num}
```

`build_external_context.py` 加载的 14 字段：
- 核心 6：总纲 / 主角卡 / 金手指设计 / 女主卡 / 反派设计 / 力量体系 / 世界观
- 质感 3：叙事声音 / 情感蓝图 / 开篇策略
- 典故 2：典故引用库 / 原创诗词口诀（存在即加载，不存在自动跳过）
- 状态：protagonist_state（来自 state.json）
- 前章：前 N-1 章正文（最多 15000 字）

若脚本失败，手动从设定集文件读取并用 `Write` 工具写入 JSON。**禁止跳过此步骤直接调用 external_review.py**。**禁止回退到旧的 9 字段内联脚本，否则外部 14 个模型将盲评无法看到作者要求的克制风格、情感蓝图、典故伏笔等关键信息。**

调用命令：
```bash
python -X utf8 "${SCRIPTS_DIR}/external_review.py" \
  --project-root "${PROJECT_ROOT}" \
  --chapter {chapter_num} \
  --mode dimensions \
  --model-key all
```
⚠️ 脚本仅支持：`--project-root`, `--chapter`, `--mode`, `--model-key`, `--models`, `--max-concurrent`, `--rpm-override`。不要传其他参数。

输出：
- 每模型一个 `.webnovel/tmp/external_review_{model_key}_ch{NNNN}.json`（共9个文件）
- 审查报告 `审查报告/第{NNNN}章审查报告.md`（含 14 模型 × 13 维度矩阵（Round 14+），包括 reader_flow + naturalness + reader_critic · Round 13 v2）

### Step 3+3.5 完成闸门（进入 Step 4 前必须通过）

**硬规则：Step 4 不得在 Step 3 或 Step 3.5 有任何子任务仍在运行时开始。**

验证方式：
1. 逐一检查所有 Step 3 内部 checker 的 Task 状态（`TaskOutput` 或等价轮询），确认每个 checker 都已返回结果（非空输出）。
2. 确认 Step 3.5 外部审查脚本已退出且 9 个 `external_review_{model_key}_ch{NNNN}.json` 文件已生成。
3. 按 `step-3-review-gate.md` 的"内外部分数合并规则"计算 `overall_score`（需要内部 + 外部都有分数）。
4. 生成审查报告（含内部 13 评分维度 + 外部 14 模型×13 维度矩阵（Round 14+），内外均含 reader_flow + naturalness + reader_critic · Round 13 v2 读者视角双维度进入外部模型评分体系）。
5. 落库 `review_metrics`。

**以上 5 步全部完成后，方可进入 Step 4。等待是流程的一部分。**

**Step 3→4 闸门强制验证**（在标记 Step 3 完成前必须执行）：
1. 对每个已启动的内部 checker Task 调用 `TaskOutput`，确认输出非空。若任一 checker 输出为空，继续等待（轮询间隔30s，每批最多等待10分钟，总超时20分钟）。超时仍未返回的 checker 标记为 timeout 并写入审查报告。注意：0+6+5 三段模式下，Batch 0（2 个读者视角 checker 并行：naturalness + reader-critic · Round 13 v2）先跑，两个都返回后启动 Batch 1（6 个含 flow-checker），Batch 1 全部返回后再启动 Batch 2（5 个），每段独立计时。Round 13 v2 取消 veto block——Batch 0 的结果直接合并进聚合，不单独 block。
2. 检查 `.webnovel/tmp/external_review_{model}_ch{NNNN}.json`：核心3模型文件必须存在且非空，补充模型缺失可接受。
3. 聚合分数：内部 13 个评分维度取平均（含 flow-checker + naturalness + reader-critic · Round 13 v2）；外部已成功模型取平均（13 维度）；合并 `round(internal * 0.6 + external * 0.4)`。
4. 写审查报告 + 落库 review_metrics。
**违规后果**：跳过此验证直接进入 Step 4，Step 6 审计 A2 检查项将检测到 checker 坍缩并可能 block 提交。

### Step 4：润色（问题修复优先）

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

**字数预算硬约束**（Round 17.1 · 2026-04-24 · Ch7 RCA Task #10 根治）：

**为什么需要**（Ch7 血教训）：
- Step 2B 后字数 3453（在 2600-3200 推进章区间偏上）
- Step 4 polish 加 4 critical + 9 high 新内容 → 字数涨到 3638（超 3500 硬上限 +138 字）
- 手动压缩 5 次才回到 3493（浪费 10+ 分钟）
- 根因：polish 没有"字数预算"意识，加内容前不算账

**硬规则**：
1. **净增上限 +200**：polish 导致字数净增超过 200，必须自检是否冗余
2. **硬上限**：polish 后总字数 ≤ state.json `word_count_policy.hard_max`（默认 3500），否则触发强制压缩
3. **推荐顺序**：先删冗余段（reader-critic/pacing 标记的"非必要对话/描写"）再扩 critical 修复，而不是"先加后砍"
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
- `.webnovel/polish_reports/ch{chapter_padded}.md` 必须由主 agent 用 Write 工具写入，不得用"变更摘要打印到 stdout 就算数"的方式处理
- `anti_ai_force_check` 必须为字符串 `pass` 或 `fail`，不允许 `None` / 空字符串
- 若 Step 4 `anti_ai_force_check=fail`，留在 Step 4 继续改写，**不进入 Step 5**（见充分性闸门 #6）
- 充分性闸门 #6 新增一条：`.webnovel/polish_reports/ch{chapter_padded}.md` 存在且非空

**为什么必须落盘**：
1. **跨章工艺学习**：近 5 章反复被改写的 beat 类型可以注入 context-agent 的 quality_feedback，Step 2A 提前规避
2. **作者自我反思**：某章为什么质感突然好/差，看润色报告就知道
3. **Step 6 Layer F/G 依赖**：审计要读 anti_ai_force_check 和 fixes 列表，没有文件就只能假设 pass

### Step 4.5：选择性复测（Round 17.1 · 2026-04-24 · Ch7 RCA F1 根治）

**定位**：Step 4 polish 后，对被 polish 集中修复的低分 checker 做**选择性复测**，确保 `chapter_meta.checker_scores` 反映的是修后真实分数，而不是修前数据。

**为什么需要**（Ch7 血教训）：
- Step 3 pacing-checker=58（Beat 2 超限 + B2/B3 结构同构 + B4 过短）
- Step 4 针对性全部修复（拆段 + 差异化 + 扩写）
- Step 4 直接进入 Step 5，`checker_scores.pacing-checker` 仍是 58
- Step 6 审计 C6 警告 "pacing 58 FAIL polish-only no retest"
- 本次 Ch7 后追加复测：pacing 58→90（+32），真实 overall 应为 88 而非 85
- **后果**：chapter_meta 存的是修前数据，下章 trend 监控误判"Ch7 pacing 突降"

**触发规则（硬约束）**：
如果 Step 3 任一 checker 首次分数 `< 75`，Step 4 polish 后**必须**重跑该 checker。

**执行模板**（Round 17.2 · Ch8 P0-R3 根治后实装 · 2026-04-24）：
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

**CLI 参数契约**（R3.1 实现 · 2026-04-24）：
- `--set-checker-score` 参数：`{chapter, checker (canonical 13 之一), score}` · 自动重算 `checker_scores.overall` 与 `overall_score`
- `--append-recheck` 参数：`{chapter, checker, before, after, reason?}` · `delta = after - before` 自动计算
- **两个 CLI 是 Step 4.5 的唯一正确接口**，禁止用 `state update --set-chapter-meta-field` 写 `checker_scores` 子键（白名单不含），也禁止走 data-agent `process-chapter` 全量回写（容易 hallucinate `before` 值 · 见 R2）

**硬规则**：
- 复测 checker ≥ 75：更新 checker_scores · 重算 overall · 记入 post_polish_recheck
- 复测 checker 仍 < 75：Step 4 未完成，继续 polish 直到 ≥ 75（或回到 Step 2A 重写该 beat）
- **不许**因为"不想再跑"而跳过复测；Step 6 审计 C6 会 block

**审计兼容性**：
- audit-agent 读 `chapter_meta.post_polish_recheck` 判断修前/修后数据
- 如无该字段且 Step 4 fixes 列表含 checker id 的 PACE_/FLOW_/etc，audit C6 自动 warn

**字数预算硬约束**（Round 17.1 Ch7 RCA + **Round 17.2 Ch8 P0-R8 根治 · 2026-04-24**）：

Ch8 血教训：writer 首稿 1930 字（-33% 预算 2900）· 对话占比 0.124（<0.20 硬线）· 用户 3 次手动扩写才达标。根治在 Step 2A 执行包（`context-agent` 与 `build_execution_package.py`）硬写入：

- **首稿总字数 ≥ hard_min**（默认 2200）：低于 hard_min 自动 post_draft_check fail
- **每 Beat 字数 ≥ 目标 85%**：如规划 700 字，首稿该 Beat < 595 字 → post_draft_check warn `BEAT_UNDERRUN`
- **对话占比 ≥ 0.20**（饭局/对峙/情感章 ≥ 0.25）：低于阈值 post_draft_check fail `DIALOGUE_RATIO`
- **chapter_type 特例**：空间视觉章/纯动作章可将 dialogue_min 降到 0.10，必须在 `context_contract.structural_exemptions.dialogue_ratio_override` 声明

### Step 5：Data Agent（状态与索引回写）

使用 Task 调用 `data-agent`，参数：
- `chapter`
- `chapter_file` 必须传入实际章节文件路径；若详细大纲已有章节名，优先传 `正文/第{chapter_padded}章-{title_safe}.md`，否则传 `正文/第{chapter_padded}章.md`
- `review_score=Step 3 overall_score`
- `project_root`
- `storage_path=.webnovel/`
- `state_file=.webnovel/state.json`

Data Agent 默认子步骤（全部执行）：
- A. 加载上下文
- B. AI 实体提取
- C. 实体消歧
- D. 写入 state/index
- E. 写入章节摘要
- F. AI 场景切片
- G. RAG 向量索引（`rag index-chapter --scenes ...`）
- H. 风格样本评估（`style extract --scenes ...`，仅 `review_score >= 80` 时）
- I. 债务利息（默认跳过）
- J. 生成处理报告（必须记录 A-I 每步耗时；写入 `.webnovel/observability/data_agent_timing.jsonl`）
- K. 设定集同步检查（每章执行，best-effort，失败不阻断）

`--scenes` 来源优先级（G/H 步骤共用）：
1. 优先从 `index.db` 的 scenes 记录获取（Step F 写入的结果）
2. 其次按 `start_line` / `end_line` 从正文切片构造
3. 最后允许单场景退化（整章作为一个 scene）

Step 5 失败隔离规则：
- 若 G/H 失败原因是 `--scenes` 缺失、scene 为空、scene JSON 格式错误：只补跑 G/H 子步骤，不回滚或重跑 Step 1-4。
- 若 A-E 失败（state/index/summary 写入失败）：仅重跑 Step 5，不回滚已通过的 Step 1-4。
- 禁止因 RAG/style 子步骤失败而重跑整个写作链。

执行后检查（最小白名单）：
- `.webnovel/state.json`
- `.webnovel/index.db`
- `.webnovel/summaries/ch{chapter_padded}.md`
- `.webnovel/observability/data_agent_timing.jsonl`（观测日志）

**数据完整性后验证（Step 5 完成后必须执行）**：
```python
# 用 Bash 执行以下 Python 验证，任一项 FAIL 则必须立即补修
import json, re
with open('.webnovel/state.json','r',encoding='utf-8') as f: s=json.load(f)
meta = s['chapter_meta'][f'{chapter:04d}']
# 1. checker_scores 非空 + 13 个 canonical key（Round 13 v2 · 新增 reader-naturalness / reader-critic）
assert meta.get('checker_scores') and len(meta['checker_scores']) >= 3, 'FAIL: checker_scores empty'
_canonical_set = {"consistency-checker","continuity-checker","ooc-checker","reader-pull-checker","high-point-checker","pacing-checker","dialogue-checker","density-checker","prose-quality-checker","emotion-checker","flow-checker","reader-naturalness-checker","reader-critic-checker","overall"}
_banned = {"Anti-AI","anti-ai","naturalness_veto"}
_alias_lists = [["设定一致性","一致性检查","伏笔埋设","伏笔检查"],["连贯性","连续性检查"],["人物塑造","人物OOC","OOC检查","人物"],["追读力","追读检查","钩子强度","钩子检查"],["爽点密度","爽点检查"],["节奏控制","节奏检查","节奏"],["对话质量","对话检查","对话"],["信息密度","密度检查"],["文笔质感","文笔检查","Prose质量","Prose","文笔"],["情感表现","情感检查","情绪曲线","情感"],["读者流畅度","读者视角流畅度","流畅度检查"],["汉语母语自然度","自然度","naturalness","reader-naturalness"],["读者锐评","reader-critic","读者视角锐评"]]
_bad_keys = [k for k in meta['checker_scores'].keys() if k in _banned or (k not in _canonical_set and not any(k in al for al in _alias_lists))]
assert not _bad_keys, f'FAIL: checker_scores 含非 canonical/banned key: {_bad_keys}（需用 13 个英文 checker 名）'
# 2. word_count 准确（用标准方法重算对比，误差<=2%）
with open(chapter_file,'r',encoding='utf-8') as f: text=f.read()
actual = len(re.findall(r'[\u4e00-\u9fff]', text))
assert abs(meta['word_count'] - actual) / actual < 0.02, f'FAIL: word_count {meta["word_count"]} vs actual {actual}'
# 3. strand_tracker 与 chapter_meta 一致
history = s['strand_tracker']['history']
tracker_strand = [h for h in history if h['chapter']==chapter][0]['dominant']
assert tracker_strand == meta['strand_dominant'].lower(), f'FAIL: strand mismatch {tracker_strand} vs {meta["strand_dominant"]}'
```

性能要求：
- 读取 timing 日志最近一条；
- 当 `TOTAL > 30000ms` 时，输出最慢 2-3 个环节与原因说明。

观测日志说明：
- `call_trace.jsonl`：外层流程调用链（agent 启动、排队、环境探测等系统开销）。
- `data_agent_timing.jsonl`：Data Agent 内部各子步骤耗时。
- 当外层总耗时远大于内层 timing 之和时，默认先归因为 agent 启动与环境探测开销，不误判为正文或数据处理慢。

债务利息：
- 默认关闭，仅在用户明确要求或开启追踪时执行（见 `step-5-debt-switch.md`）。

设定集同步（Step K）：
- 每章执行，检查新实体/道具状态变化/伏笔/资产变动，追加到设定集文件
- 所有追加带 `[Ch{N}]` 章节标注
- 失败不阻断流程

### Step 6：审计闸门（Audit Gate）

> **定位**：Step 6 是 git 提交前的最后一道防线，跨步骤/跨产物/跨章审链路真实性、承诺兑现、作品连续性。完整规范见 `references/step-6-audit-gate.md` 与 `references/step-6-audit-matrix.md`（audit-agent 必读）。

Step 6 一次调用由两部分组成，**必须全部完成**：

**Part 1 — CLI 结构审计（快速路径，< 5s）**

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" \
  audit chapter --chapter ${chapter_num} --mode ${mode} \
  --out "${PROJECT_ROOT}/.webnovel/tmp/audit_layer_abg_ch${chapter_padded}.json"
```

完成 Layer A（过程真实性）、Layer B（跨产物一致性）、Layer G（跨章趋势）的确定性检查。退出码：0=pass / 1=critical fail / 2=warnings / 3=CLI 错误。

**Part 2 — audit-agent 深度审计（60-300s）**

```
Task(audit-agent, {
  chapter: <chapter_num>,
  project_root: <PROJECT_ROOT>,
  mode: <standard|fast|minimal>,
  chapter_file: <正文/第NNNN章-*.md>,
  time_budget_seconds: 300
})
```

audit-agent 自动读取 Part 1 的 JSON 输出，完成 Layer C / D / E / F 判断性检查，聚合所有层级，产出最终 `.webnovel/audit_reports/ch{NNNN}.json` 与下章 `editor_notes/ch{NNNN+1}_prep.md`。

**决议规则**：
- `decision == block` → 按 blocking_issues 的 remediation 修复，重跑对应步骤，**不得进入 Step 7**
- `decision == approve_with_warnings` → 记录 warnings，进入 Step 7，commit message 附 `[audit:warn:layerX]`
- `decision == approve` → 直接进入 Step 7

**硬要求**：
- Part 1 与 Part 2 都必须完成；即使 Part 1 失败，Part 2 仍要执行以给出完整诊断
- `audit_reports/ch{NNNN}.json` 必须成功写出（不可跳过 editor_notes 与 trend 日志）
- audit-agent 只读不写（除审计产物），禁止修改正文/设定集/state
- Step 6 超时（300s）视为未完成，block 进入 Step 7
- 禁止强制跳过（除非用户显式确认且记录到 forced_skip 字段）

### Step 7：Git 备份 + workflow 收尾（必须同时完成）

**⚠ 顺序严格固定**（Round 18.2 · 2026-04-25 · Ch11 RCA #3 根治）：

> **关键时序约束**：hygiene_check + pre_commit_step_k 这两个**前置闸门**必须在 **Step 6 已 complete-step** 之后、**Step 7 还没 start-step** 之前的 **step gap** 状态下执行。
>
> **不能**先 `workflow start-step --step-id "Step 7"` 再跑 hygiene_check —— hygiene 的 H3 检查项会判定为"current_task running 且正在执行 Step 7：不应在 step 中间调 hygiene"并 P0 fail（即使其他质量项全过）。
>
> 正确顺序：
> ```
> Step 6 complete-step  →  (step gap)  →  hygiene_check + pre_commit_step_k  →
>   start-step Step 7  →  git commit  →  complete-step Step 7  →  complete-task
> ```

**commit 前硬闸门**（2026-04-15 新增 · Step K 设定集 Markdown 追加核对）：
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

**PowerShell 专属转义**（Round 15.3 · 2026-04-23 · Ch6 血教训）：
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

**工作流 unfail 恢复路径**（Round 15.3 新增 · Ch6 血教训）：
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

### Step 8：Post-Commit Polish Loop（提交后再润色循环 · 2026-04-20 新增）

**定位**：Step 7 commit 完成后，**任何对正文的修改**都必须走本步骤，**严禁裸跑 `git commit`**。

**为什么需要**（2026-04-20 末世重生 Ch1 血教训）：
Round 13 v2 上线 13 checker 后，作者/AI 经常根据 reader-critic / reader-naturalness 反馈手动改正文，然后裸跑 `git commit -m "v3 polish"`。结果：
- `post_draft_check.py` 不再跑 → 58 个 ASCII 引号漏过去（H5 P0 fail）
- `hygiene_check.py` 不再跑 → `word_count` 漂移（state=3498 vs actual=3084）
- `workflow_state.json` 不再登记 → polish 任务在工作流系统里"不存在"
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

**与 Step 1-7 的关系**：
- Step 8 是 **Step 7 之后的开放循环**，可无限次触发（每次产生一个 `polish_NNN` task）
- Step 8 **不替代** Step 1-7：从草稿到首次 commit 必须走完整 Step 1-7
- Step 8 的 `Step 8` 只是 `completed_steps` 里的单步标识，不与 Step 1-7 序号冲突
- 触发新章节写作时，下章 context-agent 读取 `state.json` 自动获取最新 `narrative_version` 与 polish_log

完整规范见 `references/post-commit-polish.md`（含恢复策略、多轮 polish、跨章影响、审计兼容性）。

## 充分性闸门（必须通过）

未满足以下条件前，不得结束流程：

1. 章节正文文件存在且非空：`正文/第{chapter_padded}章-{title_safe}.md` 或 `正文/第{chapter_padded}章.md`
2. **Step 1 执行包已落盘**：`.webnovel/context/ch{chapter_padded}_context.json` 与 `.webnovel/context/ch{chapter_padded}_context.md` 同时存在且非空
3. **Step 2A/2B 后 `post_draft_check.py` exit=0**（2026-04-15 新增 · 7 类硬检查通过）
4. Step 3 已产出 `overall_score`（聚合 **13 评分维度** · Round 13 v2）且 `review_metrics` 成功落库；`naturalness_verdict` / `reader_critic_verdict` 作为报告字段记录，不 block 流程；其 problems 与其他 checker 的 issues 合并进入 Step 4 修复
5. Step 3.5 外部审查已完成（核心3模型必须成功）（`--minimal` 模式跳过此条件）
6. 审查报告 `.md` 文件已生成（标准/`--fast` 模式含内部 13 评分维度分数 + 外部 14 模型×13 维度评分矩阵（Round 14+），内外均含 reader_flow + naturalness + reader_critic · Round 13 v2；`--minimal` 模式含内部 5 评分维度分数）
7. Step 4 已处理全部 `critical`，`high` 未修项有 deviation 记录
8. **Step 4 润色报告已落盘**：`.webnovel/polish_reports/ch{chapter_padded}.md` 存在且非空，含 `anti_ai_force_check` 字段
9. Step 4 的 `anti_ai_force_check=pass`（基于全文检查；fail 时不得进入 Step 5）
10. Step 5 已回写 `state.json`、`index.db`、`summaries/ch{chapter_padded}.md`
11. Step 6 审计产物齐全：`audit_reports/ch{chapter_padded}.json`、`editor_notes/ch{next_padded}_prep.md`、`observability/chapter_audit.jsonl` 追加一行；audit decision ∈ {approve, approve_with_warnings}
12. **workflow 四步登记完整**：`workflow_state.json` 的当前 task 已 `complete-task` 且 `completed_steps` 覆盖 Step 1/2A/2B/3/3.5/4/5/6/7 全量（Step 2A 可由 context-agent 内联但必须显式登记）；每个 step 的 artifact 非空且非 `{"v2": true}` 占位
13. **Step 7 commit 前 `pre_commit_step_k.py` exit=0**（2026-04-15 新增 · 设定集 Markdown 追加已完成）
14. Step 7 Git 已提交
15. 若开启性能观测，已读取最新 timing 记录并输出结论
16. **polish_log schema 合规**（2026-04-20 Round 14.5.2 新增 · hygiene `H20`）：若 `chapter_meta.{NNNN}.polish_log` 存在，每条必须含 `version` / `timestamp` / `notes` 三字段，`version` 匹配 `vN` 或 `vN.M.K`，`timestamp` 为 ISO-8601。schema 违规会让下章 context-agent 解析 polish 经验失败（跨章传递断层）
17. **polish_drift 零 P0**（2026-04-20 Round 14.5.2 新增 · preflight `polish_drift`）：Step 0 preflight 必须报告 `polish_drift: ok=True`；若 P0 drift（正文已改 + `narrative_version=v1`）则 preflight 失败，必须先走 `polish_cycle.py` 提交或 `git stash` 暂存

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
3. 重新执行”验证与交付”全部检查，通过后结束。
