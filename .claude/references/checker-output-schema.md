# Checker 统一输出 Schema (v5.4)

所有审查 Agent 应遵循此统一输出格式，便于自动化汇总和趋势分析。

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
    "milestone_present": false
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
    "pacing-checker": {"score": 80, "pass": true, "critical": 0, "high": 0}
  },
  "overall": {
    "score": 82.5,
    "pass": true,
    "critical_total": 0,
    "high_total": 2,
    "can_proceed": true
  }
}
```
