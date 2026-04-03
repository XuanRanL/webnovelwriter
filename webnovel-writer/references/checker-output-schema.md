# Checker 统一输出 Schema

所有审查 Agent 应遵循此统一输出格式，便于自动化汇总和趋势分析。

说明：
- 单章写作场景默认使用 `chapter` 字段。
- 若需要兼容区间统计，可在聚合层补充 `start_chapter/end_chapter`，不要求单个 checker 必填。
- 允许扩展字段，但不得删除或替代本文件定义的必填字段。

## 标准 JSON Schema

```json
{
  "agent": "checker-name",
  "chapter": 100,
  "overall_score": 85,
  "pass": true,
  "issues": [
    {
      "id": "ISSUE_001",
      "type": "<见下方问题类型枚举>",
      "severity": "critical|high|medium|low",
      "location": "位置描述",
      "description": "问题描述",
      "suggestion": "修复建议",
      "can_override": false
    }
  ],
  "metrics": {},
  "summary": "简短总结"
}
```

## 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `agent` | string | ✅ | Agent 名称 |
| `chapter` | int | ✅ | 章节号 |
| `overall_score` | int | ✅ | 总分 (0-100) |
| `pass` | bool | ✅ | 是否通过 |
| `issues` | array | ✅ | 问题列表 |
| `metrics` | object | ✅ | Agent 特定指标 |
| `summary` | string | ✅ | 简短总结 |

扩展字段约定（可选）：
- 可附加 checker 私有字段（如 `hard_violations`、`soft_suggestions`、`override_eligible`）。
- 私有字段用于增强解释，不用于替代 `issues`。

## 问题严重度定义

| severity | 含义 | 处理方式 |
|----------|------|----------|
| `critical` | 严重问题，必须修复 | 润色步骤必须修复 |
| `high` | 高优先级问题 | 优先修复 |
| `medium` | 中等问题 | 建议修复 |
| `low` | 轻微问题 | 可选修复 |

## 统一评分公式

所有 Checker 使用统一的扣分制评分公式：

```
overall_score = max(0, 100 - sum(deductions))
```

**扣分标准**:

| severity | 每个 issue 扣分 |
|----------|----------------|
| `critical` | 25 分 |
| `high` | 15 分 |
| `medium` | 8 分 |
| `low` | 3 分 |

**通过阈值**: `overall_score >= 75` 即 `pass: true`

**示例**:
- 1 个 critical + 1 个 medium = 100 - 25 - 8 = 67 → `pass: false`
- 2 个 medium + 1 个 low = 100 - 8 - 8 - 3 = 81 → `pass: true`

> 注意：reader-pull-checker 内部使用 Hard/Soft 两层分析体系，硬约束违规映射为 `critical`/`high` 扣分，软建议映射为 `medium`/`low` 扣分。最终 `overall_score` 使用与其他 checker 一致的统一扣分制公式（`max(0, 100 - sum(deductions))`），确保跨 checker 评分刻度一致。加权百分制仅作为内部诊断参考写入 `metrics` 扩展字段。

## 问题类型枚举

所有 Checker 的 `issues[].type` 必须使用以下 13 个标准类型之一：

| type | 主要适用 Checker | 含义 |
|------|-----------------|------|
| `SETTING_CONFLICT` | consistency | 设定/能力/等级/物品与已有世界观矛盾 |
| `CONTINUITY` | continuity, consistency | 时间线/因果链/前后章衔接/倒计时错误 |
| `OOC` | ooc | 角色言行与已建立的人设不符 |
| `PACING` | pacing | 节奏失衡（信息过密/过疏、情绪无层次） |
| `READER_PULL` | reader-pull | 钩子弱/微兑现缺失/悬念管理不当 |
| `STYLE` | all | 句式AI化/说明腔/排版/对话自然度 |
| `DIALOGUE_FLAT` | dialogue | 不同角色说话风格过于相似，遮住人名后无法分辨 |
| `DIALOGUE_INFODUMP` | dialogue | 角色对话只为向读者传递设定信息，缺少意图和冲突 |
| `DIALOGUE_MONOLOGUE` | dialogue | 单人连续独白过长（超过200字），缺少互动打断 |
| `PADDING` | density | 段落无信息增量，不推进剧情/角色/情绪，属水分填充 |
| `REPETITION` | density | 同一信息已通过其他方式传达后再次重复描述 |
| `PROSE_FLAT` | prose-quality | 文笔平淡/表现力不足（句式单调、比喻陈腐、感官贫乏、动词无力、画面感缺失、具象化不足） |
| `EMOTION_SHALLOW` | emotion | 情感表达生硬/未落地（直述替代展示、情感梯度断裂、缺乏锚点、强行煽情、情感惯性断裂） |

**旧类型映射规则**（兼容迁移）:

| 旧类型 | 标准类型 |
|--------|---------|
| `POWER_CONFLICT` | `SETTING_CONFLICT` |
| `LOCATION_ERROR` | `SETTING_CONFLICT` |
| `CHARACTER_CONFLICT` | `SETTING_CONFLICT` |
| `TIMELINE_ISSUE` | `CONTINUITY` |
| `LOGIC_HOLE` | `CONTINUITY` |
| `OUTLINE_DEVIATION` | `CONTINUITY` |

> Checker 可在 `description` 字段中进一步细分（如 "SETTING_CONFLICT: 战力崩坏"），但 `type` 字段必须使用标准枚举值。

## 内心独白检查权责划分

| Checker | 检查维度 | 触发条件 | issue type |
|---------|---------|---------|------------|
| dialogue-checker | 结构连续性 | 连续 3+ 段内心独白无外部动作/对话打断 | `PADDING` |
| density-checker | 总量占比 | `inner_monologue_ratio > 0.25` | `PADDING` |

> 两者互补：dialogue-checker 关注局部结构（连续堆积），density-checker 关注全局比例。

## 各 Checker 特定 metrics

### reader-pull-checker
```json
{
  "metrics": {
    "hook_present": true,
    "hook_type": "危机钩",
    "hook_strength": "strong",
    "prev_hook_fulfilled": true,
    "micropayoff_count": 2,
    "micropayoffs": ["能力兑现", "认可兑现"],
    "is_transition": false,
    "debt_balance": 0.0
  }
}
```

### high-point-checker
```json
{
  "metrics": {
    "cool_point_count": 2,
    "cool_point_types": ["装逼打脸", "越级反杀"],
    "density_score": 8,
    "type_diversity": 0.8,
    "milestone_present": false,
    "monotony_risk": false,
    "cool_value": {
      "suppression_intensity": 8,
      "reversal_speed": 7,
      "logic_completeness": 9,
      "score": 28,
      "formula": "8×7/max(1,11-9)=28"
    }
  }
}
```

### consistency-checker
```json
{
  "metrics": {
    "power_violations": 0,
    "location_errors": 1,
    "timeline_issues": 0,
    "entity_conflicts": 0
  }
}
```

### ooc-checker
```json
{
  "metrics": {
    "severe_ooc": 0,
    "moderate_ooc": 1,
    "minor_ooc": 2,
    "speech_violations": 0,
    "character_development_valid": true
  }
}
```

### continuity-checker
```json
{
  "metrics": {
    "transition_grade": "B",
    "active_threads": 3,
    "dormant_threads": 1,
    "forgotten_foreshadowing": 0,
    "logic_holes": 0,
    "outline_deviations": 0
  }
}
```

### pacing-checker
```json
{
  "metrics": {
    "dominant_strand": "quest",
    "quest_ratio": 0.6,
    "fire_ratio": 0.25,
    "constellation_ratio": 0.15,
    "consecutive_quest": 3,
    "fire_gap": 4,
    "constellation_gap": 8,
    "fatigue_risk": "low"
  }
}
```

### dialogue-checker
```json
{
  "metrics": {
    "dialogue_ratio": 0.35,
    "info_dump_lines": 1,
    "subtext_instances": 3,
    "distinguishable_voices": 4,
    "indistinguishable_pairs": 0,
    "intent_types": ["试探", "施压", "回避"],
    "longest_monologue_chars": 120,
    "dialogue_advances_plot": true
  }
}
```

字段说明：
- `dialogue_ratio`：对话占全文比例（0-1），建议范围 0.25-0.55
- `info_dump_lines`：说明书式对话行数（角色对话只为向读者传递设定信息）
- `subtext_instances`：潜台词实例数（表面说A实际意图B）
- `distinguishable_voices`：可辨识的独立声音数
- `indistinguishable_pairs`：遮住人名后无法区分的角色对数
- `intent_types`：对话中出现的意图类型（试探/施压/回避/诱导/防御/安抚/威胁/请求）
- `longest_monologue_chars`：最长单人连续独白字数（超过200字标记 warning）
- `dialogue_advances_plot`：对话整体是否推进了剧情/关系/信息

### density-checker
```json
{
  "metrics": {
    "effective_word_ratio": 0.85,
    "filler_paragraphs": 1,
    "repeat_segments": 0,
    "info_per_paragraph_avg": 1.2,
    "dead_paragraphs": 0,
    "longest_no_progress_span": 350,
    "inner_monologue_ratio": 0.15,
    "redundant_descriptions": 1
  }
}
```

### prose-quality-checker
```json
{
  "metrics": {
    "sentence_rhythm_score": 72,
    "metaphor_freshness_score": 78,
    "sensory_types_covered": ["视觉", "听觉"],
    "sensory_types_missing": ["触觉"],
    "verb_strength_score": 85,
    "weak_verb_density": 2.1,
    "visual_quality_score": 75,
    "concreteness_score": 80,
    "concrete_anchors_per_1k": 3.5,
    "abstract_words_per_1k": 1.8,
    "style_consistency": "consistent",
    "memorable_expressions": 1,
    "stale_metaphors": 2
  }
}
```

字段说明：
- `sentence_rhythm_score`：句式节奏评分（0-100），长短交替的丰富度
- `metaphor_freshness_score`：比喻新鲜度评分（0-100），陈腐比喻越多越低
- `sensory_types_covered`：已覆盖的感官类型（视觉/听觉/触觉/嗅觉/味觉）
- `sensory_types_missing`：缺失的关键感官类型（战斗/情感场景中应有但缺少的）
- `verb_strength_score`：动词力度评分（0-100），弱动词占比越高越低
- `weak_verb_density`：弱动词密度（处/千字），建议 ≤ 3
- `visual_quality_score`：画面感评分（0-100），空间方位、远近切换、动态描写
- `concreteness_score`：具象化程度评分（0-100），抽象词vs具体数字锚点
- `concrete_anchors_per_1k`：数字锚点密度（处/千字），建议 ≥ 3
- `abstract_words_per_1k`：抽象程度词密度（处/千字），建议 ≤ 2
- `style_consistency`：文风一致性（consistent/minor_shift/broken）
- `memorable_expressions`：令人印象深刻的原创表达数量
- `stale_metaphors`：陈腐比喻数量

### emotion-checker
```json
{
  "metrics": {
    "emotion_scene_count": 4,
    "show_count": 8,
    "tell_count": 5,
    "show_tell_ratio": 1.6,
    "emotion_gradient_quality": "good",
    "gradient_violations": 1,
    "anchor_coverage_percent": 75,
    "anchor_types_used": ["心理描写", "微表情"],
    "anchor_types_missing": ["生理反应", "环境投射"],
    "inertia_breaks": 0,
    "cross_chapter_inertia": "consistent",
    "resonance_triggers": 2,
    "resonance_types": ["信息差共鸣", "代价感"],
    "earned_emotions": 3,
    "partially_earned": 1,
    "forced_emotions": 0
  }
}
```

字段说明：
- `effective_word_ratio`：有效字数占比（0-1），每段至少提供新信息/推进/情绪变化才算有效，建议 >= 0.80
- `filler_paragraphs`：填充段落数（不服务于氛围/角色/剧情的纯填充）
- `repeat_segments`：重复表达段数（同一信息换说法再说一次）
- `info_per_paragraph_avg`：平均每段信息增量（新事实/新情绪/新决策，建议 >= 1.0）
- `dead_paragraphs`：死段落数（完全无信息增量、无氛围贡献、无节奏功能）
- `longest_no_progress_span`：最长无推进跨度（字数），超过500字标记 warning
- `inner_monologue_ratio`：内心独白占比（0-1），超过 0.25 标记 warning
- `redundant_descriptions`：冗余描写段数（已通过其他方式传达的信息再次描述）

## 汇总格式

Step 3 完成后，输出汇总 JSON：

```json
{
  "chapter": 100,
  "checkers": {
    "reader-pull-checker": {"score": 85, "pass": true, "critical": 0, "high": 1},
    "high-point-checker": {"score": 80, "pass": true, "critical": 0, "high": 0},
    "consistency-checker": {"score": 90, "pass": true, "critical": 0, "high": 0},
    "ooc-checker": {"score": 75, "pass": true, "critical": 0, "high": 1},
    "continuity-checker": {"score": 85, "pass": true, "critical": 0, "high": 0},
    "pacing-checker": {"score": 80, "pass": true, "critical": 0, "high": 0},
    "dialogue-checker": {"score": 82, "pass": true, "critical": 0, "high": 0},
    "density-checker": {"score": 88, "pass": true, "critical": 0, "high": 0},
    "prose-quality-checker": {"score": 82, "pass": true, "critical": 0, "high": 0},
    "emotion-checker": {"score": 80, "pass": true, "critical": 0, "high": 0}
  },
  "overall": {
    "score": 83.1,
    "pass": true,
    "critical_total": 0,
    "high_total": 2,
    "can_proceed": true
  }
}
```
