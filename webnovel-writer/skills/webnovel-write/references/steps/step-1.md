# webnovel-write · Step 1 Context Agent

> Round 29 Phase 2 由 SKILL.md 原文拆分（lazy-load）。进入对应 Step 时必须先加载本文件全文，
> 按其中规则执行；跨步骤硬约束 / 章节间闸门 / 充分性闸门见 SKILL.md 骨架。

### Step 1：Context Agent（内置 Context Contract，生成直写执行包）

> **🔴 Round 29 Phase 8 · Step 1 前置：追读趋势 + arc 连读审查（所有项目通用）**
>
> 1. **每章必跑**（Step 1 之前，~1s）：
>    ```bash
>    python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" \
>      state get-reading-trend --last-n 8
>    ```
>    输出的 `prescriptions[]`（THRILL_RELEASE_DUE / EMOTION_HOOK_DUE / DECISION_HOOK_DUE /
>    HOOK_SHAPE_VARY / READING_LINE_POLISH_PRIORITY）**原样传给 context-agent**，
>    context-agent 必须把每条处方落进执行包的追读力策略/beat 设计（见 context-agent.md §追读处方消费）。
> 2. **每 5 章一跑**（`chapter % 5 == 1` 且 `chapter > 5`）：Step 1 之前先
>    `Task(arc-review-checker, {start_chapter: N-5, end_chapter: N-1, next_chapter: N})`，
>    等待其落盘 `.webnovel/arc_reviews/arc_ch{start}-{end}.json` 后，把 `prescriptions_next_5`
>    一并传给 context-agent。arc 审查抓的是单章 checker 看不见的跨章病（连续无胜利/题材跑偏/
>    悬念拖延/情感压平/连读疲劳），是追读质量的主防线。
>
> 设计依据：52 章实测 thrill thrilling 仅 9/39、reader-critic 首稿三连 68-77，而 overall 86-89
> 完全看不出来——读者去留信号必须有独立消费通道，不能靠 1/13 平均。

使用 Task 调用 `context-agent`，参数：
- `chapter`
- `project_root`
- `storage_path=.webnovel/`
- `state_file=.webnovel/state.json`

Context Agent 额外输入（必读）：
- `设定集/伏笔追踪.md`（所有“活跃”伏笔线，确保长线伏笔不被遗忘）
- `设定集/道具与技术.md`（带章节时间线，防止引用“还没出现的”道具）
- `设定集/典故引用库.md`（若存在：检查本章大纲是否有引用锚点，推荐 0-2 条引用并标注载体与融入方式。无锚点时输出“本章不引用”。若不存在：跳过）
- `设定集/原创诗词口诀.md`（若存在：原创口诀优先级高于外部典故，检查本章是否命中使用规划。若不存在：跳过）
- `大纲/第N卷-节拍表.md`（本卷宏观节奏锚点）
- 相关角色卡的“语音规则”段落（注入 beat 的对话风格指导）

硬要求：
- 若 `state` 或大纲不可用，立即阻断并返回缺失项。
- 输出必须同时包含：
  - 8 板块任务书（核心任务/承接/角色/场景约束/时间约束/风格指导/连续性与伏笔/追读力策略）；
  - Context Contract 全字段（目标/阻力/代价/本章变化/未闭合问题/核心冲突一句话/开头类型/情绪节奏/信息密度/是否过渡章/追读力设计/爽点规划/情感锚点规划/时间约束）；
  - Step 2A 可直接消费的“写作执行包”（章节节拍、不可变事实清单、禁止事项、终检清单）。
- 写作执行包的每个 beat 必须包含：字数分配、场景描述（地点+氛围）、情绪曲线位置、感官锚点（至少1个画面）、情感锚点（情感beat：锚点类型+梯度位置）、关键对话方向+语音规则（若有对话）、本beat禁止事项。
- 合同与任务书出现冲突时，以“大纲与设定约束更严格者”为准。

输出：
- 单一“创作执行包”（任务书 + Context Contract + 直写提示词），供 Step 2A 直接消费。Context Contract 内置于 Step 1，无独立 Step。
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

**首章专属审查 rubric**：
当 chapter == 1 时，下列 checker 自动启用“首章加严”子项：

| Checker | 首章额外检查 | 触发条件 → 判级 |
|---|---|---|
| consistency-checker | **金手指激活时序交叉校验**（设定集·激活章节 vs 正文·前世闪回描写） | “前世 + 金手指具名使用”共现句 → critical |
| reader-pull-checker | **核心悬念不裸露**（payoff ≥80 章的 A 级伏笔，Ch1 不得泄露内容关键字） | 首章泄露跨卷悬念 → high |
| reader-pull-checker | **大纲爽点兑现**（卷大纲承诺本章爽点必须落点） | 承诺未兑现 → high |
| density-checker | **前 500 字认知载入量**（新设定计数） | ≥10 个 → high；7-9 个 → medium |
| density-checker | **信息锚点密度**（新设定必须有 ≥2 个具象锚） | 纯抽象新设定（无视觉/触觉/数字锚） → medium |
| emotion-checker | **首章 distress 具身化**（主角绝望情绪必须有外化生理反应） | 只内心描写无具身动作 → medium |
| pacing-checker | **前 500 字节奏分段合理性**（避免多个大信息同段轰炸） | 单段 ≥ 4 个新设定 → high |
| prose-quality-checker | **反派妥协博弈深度**（首章反派决策至少经过 1 次“先拒绝/压价” 拉扯） | 反派一次性通过主角要求 → medium |
| external-review-agent | **quote 存在性验证**（外部模型引用的“原文”必须真实在正文出现） | 幻觉 quote → 该 issue severity 降一档 |
