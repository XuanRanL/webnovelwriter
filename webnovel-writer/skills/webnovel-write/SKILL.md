---
name: webnovel-write
description: Writes webnovel chapters (default 2200-3500 words). Use when the user asks to write a chapter or runs /webnovel-write. Runs context, drafting, review, polish, and data extraction.
allowed-tools: Read Write Edit Grep Bash Task WebSearch WebFetch
---

# Chapter Writing (Structured Workflow)

## 目标

- 以稳定流程产出可发布章节：优先使用 `正文/第{NNNN}章-{title_safe}.md`，无标题时回退 `正文/第{NNNN}章.md`。
- 默认章节字数目标：2200-3500（用户或大纲明确覆盖时从其约定）。
- 保证审查、润色、数据回写完整闭环，避免“写完即丢上下文”。
- 输出直接可被后续章节消费的结构化数据：`review_metrics`、`summaries`、`chapter_meta`。

## 执行原则

1. 先校验输入完整性，再进入写作流程；缺关键输入时立即阻断。
2. 审查与数据回写是硬步骤，`--fast`/`--minimal` 只允许降级可选环节。
3. 参考资料严格按步骤按需加载，不一次性灌入全部文档。
4. Step 2B 与 Step 4 职责分离：2B 只做风格转译，4 只做问题修复与质控。
5. 任一步失败优先做最小回滚，不重跑全流程。

## 模式定义

- `/webnovel-write`：Step 0 → 0.5 → 1 → 2A → 2B → 3+3.5(并行) → 4 → 5 → 6
- `/webnovel-write --fast`：Step 0 → 0.5 → 1 → 2A → 3+3.5(并行) → 4 → 5 → 6（跳过 2B）
- `/webnovel-write --minimal`：Step 0 → 0.5 → 1 → 2A → 3（仅3个基础审查，跳过3.5）→ 4 → 5 → 6

最小产物（所有模式）：
- `正文/第{NNNN}章-{title_safe}.md` 或 `正文/第{NNNN}章.md`
- `index.db.review_metrics` 新纪录（含 `overall_score`）
- `.webnovel/summaries/ch{NNNN}.md`
- `.webnovel/state.json` 的进度与 `chapter_meta` 更新

### 流程硬约束（禁止事项）

- **禁止并步**：不得将两个 Step 合并为一个动作执行（如同时做 2A 和 3）。
- **禁止跳步**：不得跳过未被模式定义标记为可跳过的 Step。即使批量写多章、赶进度、上下文紧张，也必须每章完整执行所有 Step。任何"先写完再补审"、"跳过 Context Agent 直接起草"、"只跑外部审查不跑内部审查"的行为均视为违规。
- **禁止赶进度降级**：批量写作多章时，每一章都必须独立走完完整流程（Step 0→1→2A→2B→3→3.5→4→5→6）。不得因为"后面还有很多章"而简化任何一章的流程。质量优先于速度，这是不可协商的硬规则。
- **禁止省略审查报告**：Step 3 完成后必须生成审查报告文件（`审查报告/第{NNNN}章审查报告.md`），包含所有审查器的结果汇总。不得只在内存中汇总分数而不写文件。
- **禁止临时改名**：不得将 Step 的输出产物改写为非标准文件名或格式。
- **禁止自创模式**：`--fast` / `--minimal` 只允许按上方定义裁剪步骤，不允许自创混合模式、"半步"或"简化版"。
- **禁止自审替代**：Step 3 审查必须由 Task 子代理执行，主流程不得内联伪造审查结论。
- **禁止主观估分**：`overall_score` 必须来自审查子代理的聚合结果，不得因为"子代理还没返回"而自行估算分数。
- **禁止源码探测**：脚本调用方式以本文档与 data-agent 文档中的命令示例为准，命令失败时查日志定位问题，不去翻源码学习调用方式。

### 章节间闸门（Chapter Gate）

在开始下一章的任何步骤（包括 Step 0）之前，必须验证当前章的以下条件全部满足：

1. Step 3 的内部 checker 全部返回并汇总出 overall_score（标准/`--fast` 为 10 个，`--minimal` 为 3 个核心 checker）
2. Step 3.5 的 8 个外部模型审查完成（核心3模型 kimi/glm/qwen-plus 必须成功，补充5模型失败不阻塞），每模型审查 10 个维度（`--minimal` 模式跳过此条件）
3. 所有 critical 问题已修复，high 问题已修复或有 deviation 记录
4. 审查报告 .md 文件已生成（标准/`--fast` 模式含内部10维度分数+外部8模型×10维度评分矩阵；`--minimal` 模式仅含内部3维度分数）
5. Step 4 的 `anti_ai_force_check=pass`
6. Step 5 Data Agent 已完成
7. Step 6 Git 已提交

验证方式：在开始下一章 Step 0 之前，执行以下检查：
```bash
ls "${PROJECT_ROOT}/正文/第${chapter_padded}章"*.md >/dev/null 2>&1 && \
test -f "${PROJECT_ROOT}/审查报告/第${chapter_padded}章审查报告.md" && \
test -f "${PROJECT_ROOT}/.webnovel/summaries/ch${chapter_padded}.md" && \
git log --oneline -1 | grep "第${chapter_num}章"
```
任一条件不满足，禁止开始下一章。

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
  - 用途：Step 3.5 外部模型审查完整规范（8模型架构/供应商fallback链/Prompt模板/输出JSON Schema/路由验证/审查报告模板）。
  - 触发：Step 3.5 必读。
- `references/step-5-debt-switch.md`
  - 用途：Step 5 债务利息开关规则（默认关闭）。
  - 触发：Step 5 必读。
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
export WORKSPACE_ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
export SCRIPTS_DIR="${CLAUDE_PLUGIN_ROOT:?CLAUDE_PLUGIN_ROOT is required}/scripts"
export SKILL_ROOT="${CLAUDE_PLUGIN_ROOT:?CLAUDE_PLUGIN_ROOT is required}/skills/webnovel-write"

python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${WORKSPACE_ROOT}" preflight
export PROJECT_ROOT="$(python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${WORKSPACE_ROOT}" where)"
```

**硬门槛**：`preflight` 必须成功。它统一校验 `CLAUDE_PLUGIN_ROOT` 派生出的 `SKILL_ROOT` / `SCRIPTS_DIR`、`webnovel.py`、`extract_chapter_context.py` 和解析出的 `PROJECT_ROOT`。任一失败都立即阻断。

输出：
- “已就绪输入”与“缺失输入”清单；缺失则阻断并提示先补齐。

### Step 0.5：工作流断点记录（best-effort，不阻断）

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow start-task --command webnovel-write --chapter {chapter_num} || true
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow start-step --step-id "Step 1" --step-name "Context Agent" || true
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow complete-step --step-id "Step 1" --artifacts '{"ok":true}' || true
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" workflow complete-task --artifacts '{"ok":true}' || true
```

要求：
- `--step-id` 仅允许：`Step 1` / `Step 2A` / `Step 2B` / `Step 3` / `Step 3.5` / `Step 4` / `Step 5` / `Step 6`。
- 任何记录失败只记警告，不阻断写作。
- 每个 Step 执行结束后，同样需要 `complete-step`（失败不阻断）。

### Search Tool 使用规则（全流程适用）

WebSearch/WebFetch 触发规则：
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
如果 WebSearch 工具调用失败（返回错误/不可用/超时）：
1. 立即停止当前工作
2. 告知用户："WebSearch 工具不可用，需要您提供搜索能力"
3. 建议用户配置 Tavily MCP / Brave Search MCP，或手动提供搜索结果
4. 等待用户配置完成或手动提供信息后再继续
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
- `大纲/第N卷-节拍表.md`（本卷宏观节奏锚点）
- 相关角色卡的"语音规则"段落（注入 beat 的对话风格指导）

硬要求：
- 若 `state` 或大纲不可用，立即阻断并返回缺失项。
- 输出必须同时包含：
  - 8 板块任务书（核心任务/承接/角色/场景约束/时间约束/风格指导/连续性与伏笔/追读力策略）；
  - Context Contract 全字段（目标/阻力/代价/本章变化/未闭合问题/开头类型/情绪节奏/信息密度/过渡章判定/追读力设计/爽点规划）；
  - Step 2A 可直接消费的“写作执行包”（章节节拍、不可变事实清单、禁止事项、终检清单）。
- 写作执行包的每个 beat 必须包含：字数分配、场景描述（地点+氛围）、情绪曲线位置、感官锚点（至少1个画面）、关键对话方向+语音规则（若有对话）、本beat禁止事项。
- 合同与任务书出现冲突时，以“大纲与设定约束更严格者”为准。

输出：
- 单一“创作执行包”（任务书 + Context Contract + 直写提示词），供 Step 2A 直接消费，不再拆分独立 Step 1.5。

开篇黄金协议（Ch1-3 专用，叠加在标准流程之上）：
- Ch1：主角在前 500 字内出场且用行动展示（非旁白介绍）
- Ch1：核心冲突或世界规则在前 1000 字内暗示（Show not Tell）
- Ch1：章末钩子强度强制 strong
- Ch1-2：金手指至少暗示存在
- Ch1-3：人物名字总数不超过 5 个
- Ch1-3：至少 5 个冲突点
- Ch1-3：第一个场景必须包含至少 1 个具象数字（展示世界观量级）

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

中文思维写作约束（硬规则）：
- **禁止"先英后中"**：不得先用英文工程化骨架（如 ABCDE 分段、Summary/Conclusion 框架）组织内容，再翻译成中文。
- **中文叙事单元优先**：以"动作、反应、代价、情绪、场景、关系位移"为基本叙事单元，不使用英文结构标签驱动正文生成。
- **禁止英文结论话术**：正文、审查说明、润色说明、变更摘要、最终报告中不得出现 Overall / PASS / FAIL / Summary / Conclusion 等英文结论标题。
- **英文仅限机器标识**：CLI flag（`--fast`）、checker id（`consistency-checker`）、DB 字段名（`anti_ai_force_check`）、JSON 键名等不可改的接口名保持英文，其余一律使用简体中文。

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

### Step 3：审查（全量审查，必须由 Task 子代理执行）

执行前加载：
```bash
cat "${SKILL_ROOT}/references/step-3-review-gate.md"
```

调用约束：
- 必须用 `Task` 调用审查 subagent，禁止主流程伪造审查结论。
- 可并行发起审查，统一汇总 `issues/severity/overall_score`。

审查器（标准模式全部执行）：
- `consistency-checker`（设定一致性）
- `continuity-checker`（连贯性）
- `ooc-checker`（人物OOC）
- `reader-pull-checker`（追读力）
- `high-point-checker`（爽点密度）
- `pacing-checker`（节奏平衡）
- `dialogue-checker`（对话质量）
- `density-checker`（信息密度）

模式说明：
- 标准/`--fast`：全量 10 个审查器始终执行。
- `--minimal`：固定核心 3 个（consistency/continuity/ooc）。

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
  "dimension_scores": {"爽点密度": 85, "设定一致性": 80, "节奏控制": 78, "人物塑造": 82, "连贯性": 90, "追读力": 87, "对话质量": 83, "信息密度": 88, "文笔质感": 82, "情感表现": 80},
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

### Step 3.5：外部模型审查（与 Step 3 并行或紧接执行）

执行前必须加载：
```bash
cat "${SKILL_ROOT}/references/step-3.5-external-review.md"
```

硬要求：
- **必须使用 `--model-key all` 一次性执行全部 8 模型**，禁止手动逐个调用（防止遗漏模型）。
- 核心3模型必须全部成功，补充5模型失败不阻塞。
- 按 reference 文件中的 Prompt 模板构建 system 消息。
- 每次 API 调用后验证路由（检查 response.model 字段）。
- 核心模型 fallback 链：healwrap(2次) → codexcc(1次) → 硅基流动(兜底)。
- 输出 JSON 必须包含 model_actual、routing_verified、provider_chain、cross_validation。
- 生成审查报告必须包含 8 模型 × 10 维度评分矩阵 + 共识问题 + Step 4 修复清单。

调用命令：
```bash
python -X utf8 "${SCRIPTS_DIR}/external_review.py" \
  --project-root "${PROJECT_ROOT}" \
  --chapter {chapter_num} \
  --mode dimensions \
  --model-key all \
  --max-concurrent 1
```
⚠️ 脚本仅支持：`--project-root`, `--chapter`, `--mode`, `--model-key`, `--models`, `--max-concurrent`, `--rpm-override`。不要传其他参数。

输出：
- 每模型一个 `.webnovel/tmp/external_review_{model_key}_ch{NNNN}.json`（共8个文件）
- 审查报告 `审查报告/第{NNNN}章审查报告.md`（含 8 模型 × 10 维度矩阵）

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

输出：
- 润色后正文（覆盖章节文件）
- 变更摘要（至少含：修复项、保留项、deviation、`anti_ai_force_check`）

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

### Step 6：Git 备份（可失败但需说明）

```bash
git add .
git -c i18n.commitEncoding=UTF-8 commit -m "第{chapter_num}章: {title}"
```

规则：
- 提交时机：验证、回写、清理全部完成后最后执行。
- 提交信息默认中文，格式：`第{chapter_num}章: {title}`。
- 若 commit 失败，必须给出失败原因与未提交文件范围。

## 充分性闸门（必须通过）

未满足以下条件前，不得结束流程：

1. 章节正文文件存在且非空：`正文/第{chapter_padded}章-{title_safe}.md` 或 `正文/第{chapter_padded}章.md`
2. Step 3 已产出 `overall_score` 且 `review_metrics` 成功落库
3. Step 3.5 外部审查已完成（核心3模型必须成功）（`--minimal` 模式跳过此条件）
4. 审查报告 `.md` 文件已生成（标准/`--fast` 模式含内部10维度分数+外部8模型×10维度评分矩阵；`--minimal` 模式仅含内部3维度分数）
5. Step 4 已处理全部 `critical`，`high` 未修项有 deviation 记录
6. Step 4 的 `anti_ai_force_check=pass`（基于全文检查；fail 时不得进入 Step 5）
7. Step 5 已回写 `state.json`、`index.db`、`summaries/ch{chapter_padded}.md`
8. Step 6 Git 已提交
9. 若开启性能观测，已读取最新 timing 记录并输出结论

## 验证与交付

执行检查：

```bash
test -f "${PROJECT_ROOT}/.webnovel/state.json"
ls "${PROJECT_ROOT}/正文/第${chapter_padded}章"*.md >/dev/null 2>&1
test -f "${PROJECT_ROOT}/.webnovel/summaries/ch${chapter_padded}.md"
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" index get-recent-review-metrics --limit 1
tail -n 1 "${PROJECT_ROOT}/.webnovel/observability/data_agent_timing.jsonl" || true
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
3. 重新执行”验证与交付”全部检查，通过后结束。
