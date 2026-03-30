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
      "type": "问题类型",
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
    "cool_value": {
      "suppression_intensity": 8,
      "reversal_speed": 7,
      "logic_completeness": 9,
      "score": 62,
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
    "density-checker": {"score": 88, "pass": true, "critical": 0, "high": 0}
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
