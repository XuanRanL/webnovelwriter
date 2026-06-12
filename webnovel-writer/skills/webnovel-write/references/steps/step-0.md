# webnovel-write · Step 0 预检 + Step 0.5 工作流登记 + Search Tool 规则

> Round 29 Phase 2 由 SKILL.md 原文拆分（lazy-load）。进入对应 Step 时必须先加载本文件全文，
> 按其中规则执行；跨步骤硬约束 / 章节间闸门 / 充分性闸门见 SKILL.md 骨架。

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
# Round 15.2 ()：CLAUDE_PLUGIN_ROOT 在某些 shell（如 Git Bash）不会被自动 export。
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

说明 plugin `agents/` 新增/修改的 subagent 未同步到**工作区** `.claude/agents/`（工作区 fallback 层，独立于 cache）。Task(subagent) 会静默 fallback 到 general-purpose，导致 checker 空跑（：flow-checker 加入后未同步到工作区，Step 3 Batch 2 只实际跑了 5 个而非 6 个，审查报告里写“内部 10 维度”其实应该是 11）。

一键修复：
```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" sync-agents
```

### warning 2: `ERROR cache_sync`

说明 fork 内容与 plugin cache 不一致（通常因为 `git pull` 后没同步）。**直接后果：AI 跑的是 cache 的旧代码**，fork 的 bug fix / 新 checker / 新维度都不生效。例证：

-c511802 commit 在 fork 加入 reader_flow，但 cache 没同步 → Ch6 外部审查只跑 10 维度（应 11）
-某次修复把 chapter_audit.py 中文注释写坏，cache 同步了 37 行 `??????` → 后续审计 evidence 全乱码

**注意：`sync-cache` 必须从 fork 跑，不能从 cache 跑**（：从 cache 跑会自反拷贝 + 无法找到 fork）。生产里 AI 会通过 `CLAUDE_PLUGIN_ROOT`（= cache 路径）跑 `webnovel.py`，所以：

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

**`preflight` 的 cache_sync 检查**：
- 从 fork 跑：直接 fork↔cache 漂移对比，有漂移 → ERROR
- 从 cache 跑（生产路径）：先通过 `WEBNOVEL_FORK_PATH` env var 或 fork-registry 找 fork；找到则对比；找不到则输出 NOTE “fork 未登记，跳过”（不阻断，但提示修复）
- **从 fork 跑过一次 sync-cache 后，registry 自动建立，后续从 cache 跑也能查漂移**

### 硬规则

**任何 `ERROR agents_sync` / `ERROR cache_sync` / `ERROR polish_drift` 必须在 Step 1 前清零**。不得“跳过 warning 开始写章”，因为：
- agents_sync 漂移 → Task checker 空跑（你看不见 fallback，章节走完了才发现审查报告维度少了）
- cache_sync 漂移 → 所有 fix / 新功能不生效（你 commit 了但 AI 跑的是老代码）
- **polish_drift P0 漂移**→ 上一章正文已手动改但未走 polish_cycle，直接进入下章会污染上下文。修法：对每个 drifted 章节运行 `polish_cycle.py <N> --reason '补录裸跑 commit' --narrative-version-bump`；若是 WIP（未完成）改动则 `git stash` 暂存

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

**可选：安装 git pre-commit hook**：

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
- “已就绪输入”与“缺失输入”清单；缺失则阻断并提示先补齐。
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

# 推荐（Round 29）：shell 类步骤（Step 3.5 / Step 6 Part 1 / Step 7 等）用 run-step 一次完成
# start-step → 命令执行 → complete-step；命令非零退出自动 fail-step 并透传退出码。
# artifacts 在命令执行后才产生时用 --artifacts-file（命令把 artifacts JSON 写到该路径）。
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow run-step \
  --step-id "Step 3.5" --step-name "External review" \
  --artifacts-file "${PROJECT_ROOT}/.webnovel/tmp/step35_artifacts.json" \
  -- python -X utf8 "${SCRIPTS_DIR}/external_review.py" --project-root "${PROJECT_ROOT}" --chapter ${chapter_num} --mode dimensions --model-key all --dimension-strategy auto

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
| Step 3.5 | `external_avg` / `models_ok` / `external_models_ok` | 外部多模型均分 + 成功模型列表 |
| Step 4 | `anti_ai_force_check` / `polish_report` / `fixes` | `pass`/`fail`, 润色报告路径, 修复项列表 |
| Step 5 | `state_modified` / `entities` / `foreshadowing` / `scene_count` / `chapter_meta_fields` | data-agent 写库确认 + 实体/伏笔/场景计数 |
| Step 6 | `decision` / `audit_report` / `audit_decision` | `approve` / `approve_with_warnings` / `block` |
| Step 7 | `commit` / `branch` / `commit_sha` / `word_count` | git commit SHA + 分支名 + 最终字数|

**占位字段（不能单独存在）**：`v2`, `ok`, `chapter_completed`, `committed` 只有在至少一个语义字段存在时才被允许。单独用这些字段会被 `workflow_manager.complete_step` 直接 reject，参考 `_validate_artifact_has_semantic_field` 源码。

**硬规则**：
- `--step-id` 仅允许：`Step 1` / `Step 2A` / `Step 2B` / `Step 3` / `Step 3.5` / `Step 4` / `Step 5` / `Step 6` / `Step 7`
- **所有 Step（含 2B/3.5/4/5）在执行任何 Edit/Task/脚本之前必须先 start-step**。Round 29 起 strict workflow **默认开启**：complete-step 没有预先 start-step 会被直接拒绝（不再有 implicit_start 兜底）；被拒后当场补 `start-step` 再 `complete-step` 即可。遗留恢复场景可设 `WEBNOVEL_STRICT_WORKFLOW=0` 临时关闭。
- 任何 `workflow` 子命令失败都必须立即阻断并报错，禁止 `|| true` 吞错误
- complete-step 的 artifact 必须包含至少一个上述白名单字段，否则 Step 6 Layer A 会 fail
- **严禁**任何形式的“事后补登记”：不得用 Python/Edit 工具直接修改 `workflow_state.json`，不得用 `{"v2": true}` 或类似占位填充；违规将被 hygiene_check H3/H16 检出并阻断 commit
- Step 6 审计通过后 Step 7 git commit 成功才调用 `complete-task`，**顺序不可调换**

### Search Tool 使用规则（全流程适用）

**搜索统一使用 Tavily 直连 API 脚本**（`${SCRIPTS_DIR}/tavily_search.py`），禁止使用 MCP 工具（WebSearch/WebFetch）。

**两种搜索模式**：
- **快速搜索**（大多数场景）：`python -X utf8 "${SCRIPTS_DIR}/tavily_search.py" search "查询词" --max 5`
- **深度研究**（复杂专业领域）：`python -X utf8 "${SCRIPTS_DIR}/tavily_search.py" research "研究问题" --model pro`

搜索触发规则：
- **强制触发**：涉及专业领域（机甲技术/军事/科学/法律）→ 搜索术语和真实细节
- **强制触发**：需要特定案例或参考（如“真实驾驶舱布局”“地下通道地质结构”）→ 搜索具体资料
- **推荐触发**：章节类型特殊（战斗/情感/揭秘/追逐/谈判）→ 搜索该类型写作技巧
- **推荐触发**：新卷首章或Ch1-3 → 搜索同题材开篇技巧
- **推荐触发**：审查发现 HIGH 级 STYLE/PACING 问题 → 搜索改进方法
- **按需触发**：普通推进章无特殊场景 → 不搜索

各 Step 的具体搜索内容：
- Step 1：搜索本章场景类型的写作技巧（“机甲战斗 描写技巧”“谈判场景 张力写法”）
- Step 2A：搜索专业领域术语和真实细节（“机甲驾驶舱 操控界面”“军事通讯 加密术语”）
- Step 2B：搜索风格参考（“硬核科幻 技术描写 范例”）
- Step 4：搜索审查问题的改进方法（“对话平淡 改进技巧”“节奏拖沓 如何加快”）

搜索结果归档：有价值的专业信息保存到 `调研笔记/` 对应主题文件，供后续章节复用。

**Search 失败处理协议（硬规则）**：
如果 `tavily_search.py` 执行失败（API key 缺失/全部 key 耗尽/网络超时）：
1. 立即停止当前工作
2. 告知用户搜索脚本执行失败及具体错误信息
3. 建议用户检查 API key 配置（环境变量 `TAVILY_API_KEYS` / `.env` 文件 / `~/.claude.json`）
4. 等待用户修复配置后再继续
5. 不要跳过搜索步骤直接继续——搜索获取的专业细节直接影响质量
