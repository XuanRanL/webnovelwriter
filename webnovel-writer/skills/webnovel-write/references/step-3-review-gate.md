# Step 3 Review Gate

## 调用约束（硬规则）

- 必须使用 `Task` 调用审查 subagent，禁止主流程直接内联“自审结论”。
- 审查任务可并行发起，必须在全部返回后统一聚合。
- `overall_score` 必须来自聚合结果，不可主观估分。
- 单章写作场景下，统一传入：`{chapter, chapter_file, project_root}`。

## 审查路由模式

- 标准/`--fast`：全量 13 个审查器（2 读者视角 + 6 核心 + 5 工艺）分 0+6+5 三段执行。
- `--minimal`：固定核心 5 个（naturalness + reader-critic + consistency + continuity + ooc）。**两个读者视角 checker 在任何模式下都必跑**——读者本能反应是检测规则 pass 但读者会弃的底线。

审查器（标准模式全部执行）：

**Batch 0 · 读者视角维度（2 个并行，Round 13 v2）**：

两个 checker **并行先跑**，输出 `overall_score` 和 `problems` 与其他 11 个 checker 同等进入聚合。两把尺子互补：一个量"字句像不像人写的"，一个量"读者本能愿不愿追"。

- `reader-naturalness-checker`（汉语母语自然度 · 首句语病/AI 腔/伪神经科学痕迹 · 独立于规则污染 · 不读设定集）
  - 输出 `overall_score`（0-100）与 `problems`，纳入 `internal_avg`
  - 附带 `verdict ∈ {PASS, POLISH_NEEDED, REWRITE_RECOMMENDED, REJECT_HIGH, REJECT_CRITICAL}` 作为严重度信号——REJECT_* 会产生 critical/high 级 problems 强制 Step 4 修复
- `reader-critic-checker`（读者锐评 · 极简 prompt · 无规则约束 · 模拟追更读者本能反应 · Round 13 新增）
  - 输出 `overall_score`（0-100）与 `problems`，纳入 `internal_avg`
  - 附带 `will_continue_reading ∈ {yes, hesitant, no}` 作为读者追读意愿信号——`no` 会产生 critical 级 problems 强制 Step 4 修复

**Round 13 v2 · 取消 block**：两个 checker **不 block Step 3/3.5/4 流程**。它们的 problems 和其他 checker 的 issues 合并进入 Step 4 定向修复。只有在 Step 4 polish 后复查仍 REJECT_CRITICAL 或 will_continue_reading=no，才考虑回 Step 2A 重写整章。

**Batch 1 · 核心审查（6 个并发）**：
- `consistency-checker`（设定一致性）
- `continuity-checker`（连贯性）
- `ooc-checker`（人物OOC）
- `reader-pull-checker`（追读力）
- `high-point-checker`（爽点密度）
- `flow-checker`（读者视角流畅度——一人分饰两角失忆阅读协议）

**Batch 2 · 工艺维度（5 个并发）**：
- `pacing-checker`（节奏平衡）
- `dialogue-checker`（对话质量）
- `density-checker`（信息密度）
- `prose-quality-checker`（文笔质感）
- `emotion-checker`（情感表现）

## Task 调用模板（示意）

**硬规则：0+6+5 三段启动，禁止 13 个 checker 同时并发。**

原因：Claude Code Agent 并发池限制约 4-6 个，13 个同时启动会排队超时。Batch 0 的 2 个读者视角 checker 先跑不是为了 block，而是尽早为 Step 4 积累修复反馈。

```text
if mode == "minimal":
  # minimal 模式 5 个（2 读者视角 + 核心 3）
  selected = ["reader-naturalness-checker", "reader-critic-checker",
              "consistency-checker", "continuity-checker", "ooc-checker"]
  parallel Task(agent, {chapter, chapter_file, project_root}) for agent in selected
  # Round 13 v2：所有 5 个 checker 都只输出 score + problems，不 block
else:
  # 标准/--fast 模式：Batch 0（2 读者视角）→ Batch 1（6 核心）→ Batch 2（5 工艺）

  # Batch 0：并行跑两个读者视角 checker（不 block，只拿反馈）
  batch0 = ["reader-naturalness-checker", "reader-critic-checker"]
  batch0_tasks = parallel Task(agent, {chapter, chapter_file, project_root}) for agent in batch0
  wait_all(batch0_tasks, polling=30s, timeout=600s)

  # Batch 1：启动 6 个 checker
  batch1 = ["consistency-checker", "continuity-checker", "ooc-checker",
            "reader-pull-checker", "high-point-checker", "flow-checker"]
  batch1_tasks = parallel Task(agent, {chapter, chapter_file, project_root}) for agent in batch1
  wait_all(batch1_tasks, polling=30s, timeout=600s)

  # Batch 2：Batch 1 全部返回后再启动 5 个
  batch2 = ["pacing-checker", "dialogue-checker", "density-checker",
            "prose-quality-checker", "emotion-checker"]
  batch2_tasks = parallel Task(agent, {chapter, chapter_file, project_root}) for agent in batch2
  wait_all(batch2_tasks, polling=30s, timeout=600s)

  # 合并全部 13 个 checker 的 problems/issues，统一进入 Step 4 修复
  all_results = batch0_tasks + batch1_tasks + batch2_tasks
```

**Step 3 artifacts 要求（workflow complete-step 必须含）**：
```json
{
  "overall_score": 92,
  "checker_count": 13,
  "internal_avg": 93.7,
  "review_score": 92,
  "naturalness_score": 88,
  "naturalness_verdict": "PASS",
  "reader_critic_score": 82,
  "reader_critic_verdict": "yes"
}
```

**Round 13 v2 · 无 block 条件在 Step 3**：13 个 checker 的 `problems`/`issues` 全部传给 Step 4 定向修复。只有在 Step 4 polish 后复查，若 `naturalness_verdict` 仍 ∈ {`REJECT_CRITICAL`, `REJECT_HIGH`} 或 `reader_critic_verdict == "no"`，才考虑回 Step 2A 重写整章（极端情况，正常流程不触发）。

**分批规则**（Round 13 v2 · 0+6+5 三段）：
- Batch 0（读者视角，先跑）：reader-naturalness + reader-critic（2 个并行）
- Batch 1（核心优先，Batch 0 返回后启动）：consistency + continuity + ooc + reader-pull + high-point + flow-checker（6 个并行）
- Batch 2（工艺维度，Batch 1 返回后启动）：pacing + dialogue + density + prose-quality + emotion（5 个并行）
- 每批内部并行，批间串行
- 单批超时 10 分钟，总超时 20 分钟（0+6+5 比原 5+6 略慢但早期读者反馈给 Step 4 用）
- 若单批中某 checker 超时，标记该 checker 为 timeout，不阻塞同批其他 checker

## 输出契约（统一）

每个 checker 返回值必须遵循 `${CLAUDE_PLUGIN_ROOT}/references/checker-output-schema.md`：
- 必含：`agent`、`chapter`、`overall_score`、`pass`、`issues`、`metrics`、`summary`
- 允许扩展字段（如 `hard_violations`、`soft_suggestions`），但不得替代必填字段

聚合输出最小字段：
- `chapter`（单章）
- `start_chapter`、`end_chapter`（单章时二者都等于 `chapter`）
- `selected_checkers`
- `overall_score`
- `severity_counts`
- `critical_issues`
- `issues`（扁平化聚合）
- `dimension_scores`（按已启用 checker 计算）

## 汇总输出模板

```text
审查汇总 - 第 {chapter_num} 章
- 已启用审查器: {list}
- 严重问题: {N} 个
- 高优先级问题: {N} 个
- 综合评分: {score}
- 可进入润色: {是/否}
```

## 审查指标落库（必做）

**章号校验（硬规则，防止落库旧章数据）**：
1. 在写入 `review_metrics.json` 之前，必须由主流程（而非 Data Agent）直接构造 JSON 并写入文件。
2. 写入后立即校验 `start_chapter` 和 `end_chapter` 是否等于当前章号。
3. **禁止 Data Agent 或其他步骤覆盖 `review_metrics.json`。**

```bash
# 1. 主流程写入 review_metrics.json（必须包含当前章号）
python -c "
import json, sys
data = json.loads(sys.argv[1])
assert data['start_chapter'] == data['end_chapter'] == ${chapter_num}, \
    f\"章号不匹配: expected ${chapter_num}, got {data['start_chapter']}/{data['end_chapter']}\"
open('${PROJECT_ROOT}/.webnovel/tmp/review_metrics.json','w',encoding='utf-8').write(json.dumps(data,ensure_ascii=False,indent=2))
" '${REVIEW_METRICS_JSON}'

# 2. 落库
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" index save-review-metrics --data "@${PROJECT_ROOT}/.webnovel/tmp/review_metrics.json"

# 3. 验证落库章号
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" index get-recent-review-metrics --limit 1
# 确认输出的 end_chapter == ${chapter_num}
```

review_metrics 文件字段约束（当前工作流约定只传以下字段）：
- `start_chapter`（int）、`end_chapter`（int）：单章时二者相等
- `overall_score`（float）：必填
- `dimension_scores`（Dict[str, float]）：按已启用 checker 计算，**刻度 0-100**（与各 checker 的 `overall_score` 同刻度，直接取各 checker 的 `overall_score` 值）。**Round 13 v2 · 13 键**（推荐直接用 canonical 英文 key：`consistency-checker / continuity-checker / ooc-checker / reader-pull-checker / high-point-checker / flow-checker / pacing-checker / dialogue-checker / density-checker / prose-quality-checker / emotion-checker / reader-naturalness-checker / reader-critic-checker`）。旧中文键名映射（audit 会自动 normalize）：设定一致性 / 连贯性 / 人物塑造 / 追读力 / 爽点密度 / 读者流畅度 / 节奏控制 / 对话质量 / 信息密度 / 文笔质感 / 情感表现 / **汉语母语自然度** / **读者锐评**。
- `severity_counts`（Dict[str, int]）：键为 critical / high / medium / low
- `critical_issues`（List[str]）
- `report_file`（str）
- `notes`（str）：在当前执行契约中必须是单个字符串；`selected_checkers`、`timeline_gate`、`anti_ai_force_check` 等扩展信息统一压成单行文本写入此字段，不得作为独立顶层键传入
- 当前工作流不额外传入其它顶层字段；脚本侧未在此处做新增硬校验

## 进入 Step 4 前闸门

### 完成性闸门（硬阻断，最高优先级）

**Step 4 不得在 Step 3 或 Step 3.5 有任何子任务仍在运行时开始。**

等待方式（Round 13 v2 · 0+6+5 分批模式）：
1. Batch 0 的 2 个读者视角 checker（reader-naturalness + reader-critic）先并行启动，逐一通过 `TaskOutput` 检查输出是否非空。若任一 checker 输出为空（0 bytes），说明仍在运行，继续等待（轮询间隔 30s，单批最多 10 分钟）。
2. Batch 0 全部返回后，启动 Batch 1 的 6 个 checker（consistency + continuity + ooc + reader-pull + high-point + flow-checker），同样等待全部返回。
3. Batch 1 全部返回后，启动 Batch 2 的 5 个工艺 checker（pacing + dialogue + density + prose-quality + emotion），等待全部返回。
4. 对 Step 3.5 外部审查，确认脚本已退出且所有 `external_review_*_ch{NNNN}.json` 文件已写入。
5. **三批全部返回后**，按"内外部分数合并规则"计算 `overall_score` 并写入审查报告。
6. **禁止用外部审查分数代替内部 checker 分数**。二者是独立维度，必须各自完整返回后合并。

违规场景（明确禁止）：
- ❌ "外部审查已完成，内部 checker 还在跑，先用外部分数开始 Step 4"
- ❌ "13 个 checker 中 10 个返回了，先聚合这 10 个"
- ❌ "checker 跑太久了，用外部模型的对应维度分数替代"

### 质量闸门

- `overall_score` 已生成且 **≥ 75 分**（低于 75 分为不合格，必须回到 Step 2A 重写后重审）。
- `save-review-metrics` 已成功。
- 审查报告中的 `issues`、`severity_counts` 可被 Step 4 直接消费。
- **时间线闸门**：若存在时间线相关的 `CONTINUITY` 问题且 `severity >= high`，禁止进入 Step 4/5，必须先修复。

### 评分阈值规则

| 分数区间 | 处理方式 |
|----------|---------|
| ≥ 90 | 优秀，进入 Step 4 做常规润色 |
| 75-89 | 合格，进入 Step 4 重点修复审查问题 |
| 60-74 | 不合格，回到 Step 2A 重写核心段落后重审 |
| < 60 | 严重不合格，回到 Step 1 重新规划后重写 |

## 内外部分数合并规则

当 Step 3 内部审查和 Step 3.5 外部审查同时完成时，按以下规则合并为最终 `overall_score`：

1. `internal_score`：Step 3 内部 **13 个评分 checker** 的聚合分数（Round 13 v2 · naturalness 和 reader-critic 升格为评分维度与其他 11 个平等）
2. `external_avg`：Step 3.5 外部模型的平均 overall_score（仅统计成功返回的模型）
3. `overall_score = round(internal_score * 0.6 + external_avg * 0.4)`
4. 若 `|internal_score - external_avg| > 15`：标记 `score_divergence_warning`，需在审查报告中说明分歧原因
5. `review_metrics` 落库时使用合并后的 `overall_score`
6. 若 Step 3.5 全部失败（无外部分数），退化为 `overall_score = internal_score`

### 时间线闸门规则

**Hard Block（必须修复才能继续）**：
- `CONTINUITY`（时间线子类） + `severity = critical`（倒计时算术错误）
- `CONTINUITY`（时间线子类） + `severity = high`（事件先后矛盾/年龄冲突/时间回跳/大跨度无过渡）

**Soft Warning（建议修复但可继续）**：
- `CONTINUITY`（时间线子类） + `severity = medium`（时间锚点缺失）
- `CONTINUITY`（时间线子类） + `severity = low`（轻微时间模糊）

**时间线子类识别**：由于 `TIMELINE_ISSUE` 已合并为标准类型 `CONTINUITY`（见 `checker-output-schema.md` 旧类型映射），通过 `description` 关键词识别时间线子类问题：

```text
TIMELINE_KEYWORDS = ["时间线", "倒计时", "时间回跳", "事件先后", "年龄冲突",
                     "时间锚点", "时间过渡", "时间矛盾", "时间流逝", "D-"]

timeline_issues = filter(issues,
    type="CONTINUITY" AND
    any(keyword in issue.description for keyword in TIMELINE_KEYWORDS))
critical_timeline = filter(timeline_issues, severity in ["critical", "high"])

if len(critical_timeline) > 0:
    BLOCK: "存在 {len(critical_timeline)} 个严重时间线问题，必须修复后才能进入润色步骤"
    for issue in critical_timeline:
        print(f"- 第{issue.chapter}章: {issue.description}")
    return BLOCKED
else:
    通过: "时间线检查通过"
```

> **注意**：`consistency-checker` 输出时间线问题时，`type` 字段必须使用标准枚举 `CONTINUITY`，但 `description` 中应包含上述关键词以便闸门识别。Checker 不得使用旧类型 `TIMELINE_ISSUE` 作为 `type` 值。

**修复指引**：
- 倒计时错误 → 修正倒计时推进，确保 D-N → D-(N-1) 连续
- 时间回跳 → 添加闪回标记，或调整时间锚点
- 大跨度无过渡 → 添加时间过渡句/段，或插入过渡章
- 事件先后矛盾 → 调整事件发生顺序或添加时间跳跃说明
