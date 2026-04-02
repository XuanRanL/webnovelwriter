# Step 3 Review Gate

## 调用约束（硬规则）

- 必须使用 `Task` 调用审查 subagent，禁止主流程直接内联“自审结论”。
- 审查任务可并行发起，必须在全部返回后统一聚合。
- `overall_score` 必须来自聚合结果，不可主观估分。
- 单章写作场景下，统一传入：`{chapter, chapter_file, project_root}`。

## 审查路由模式

- 标准/`--fast`：全量 8 个审查器始终执行。
- `--minimal`：固定核心 3 个（consistency/continuity/ooc，不启用扩展审查器）。

审查器（标准模式全部执行）：
- `consistency-checker`（设定一致性）
- `continuity-checker`（连贯性）
- `ooc-checker`（人物OOC）
- `reader-pull-checker`（追读力）
- `high-point-checker`（爽点密度）
- `pacing-checker`（节奏平衡）
- `dialogue-checker`（对话质量）
- `density-checker`（信息密度）

## Task 调用模板（示意）

```text
if mode == "minimal":
  selected = ["consistency-checker", "continuity-checker", "ooc-checker"]
else:
  selected = ["consistency-checker", "continuity-checker", "ooc-checker",
              "reader-pull-checker", "high-point-checker", "pacing-checker",
              "dialogue-checker", "density-checker"]

parallel Task(agent, {chapter, chapter_file, project_root}) for agent in selected
```

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
- `dimension_scores`（Dict[str, float]）：按已启用 checker 计算，**刻度 0-100**（与各 checker 的 `overall_score` 同刻度，直接取各 checker 的 `overall_score` 值）
- `severity_counts`（Dict[str, int]）：键为 critical / high / medium / low
- `critical_issues`（List[str]）
- `report_file`（str）
- `notes`（str）：在当前执行契约中必须是单个字符串；`selected_checkers`、`timeline_gate`、`anti_ai_force_check` 等扩展信息统一压成单行文本写入此字段，不得作为独立顶层键传入
- 当前工作流不额外传入其它顶层字段；脚本侧未在此处做新增硬校验

## 进入 Step 4 前闸门

- `overall_score` 已生成且 **≥ 75 分**（低于 75 分为不合格，必须回到 Step 2A 重写后重审）。
- `save-review-metrics` 已成功。
- 审查报告中的 `issues`、`severity_counts` 可被 Step 4 直接消费。
- **时间线闸门（新增）**：若存在时间线相关的 `CONTINUITY` 问题且 `severity >= high`，禁止进入 Step 4/5，必须先修复。

### 评分阈值规则

| 分数区间 | 处理方式 |
|----------|---------|
| ≥ 90 | 优秀，进入 Step 4 做常规润色 |
| 75-89 | 合格，进入 Step 4 重点修复审查问题 |
| 60-74 | 不合格，回到 Step 2A 重写核心段落后重审 |
| < 60 | 严重不合格，回到 Step 1 重新规划后重写 |

## 内外部分数合并规则

当 Step 3 内部审查和 Step 3.5 外部审查同时完成时，按以下规则合并为最终 `overall_score`：

1. `internal_score`：Step 3 内部 8 个 checker 的聚合分数
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
