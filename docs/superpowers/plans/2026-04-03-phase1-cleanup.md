# Phase 1: 清理废弃模块 + 审查合并 + 流程精简

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 砍掉不产生价值的模块（workflow、resume），将 6 个 checker 合并为 1 个审查 agent，Step 2B 合并到 Step 4，预计单章 Token 降低 60-70%。

**Architecture:** 纯减法重构。删除 workflow_manager.py 及其测试、resume skill 及其引用。将 6 个独立 checker agent 合并为 1 个 `reviewer.md`，输出新的结构化问题清单 schema。更新 webnovel-write SKILL.md 流程从 8 步变 7 步。更新 review_pipeline.py 适配新 schema。更新 webnovel.py CLI 移除 workflow 命令。

**Tech Stack:** Python 3.13, pytest, Claude Code plugin (markdown agents/skills)

**Spec:** `docs/superpowers/specs/2026-04-02-harness-v6-design.md`

---

## File Structure

### 要删除的文件

| 文件 | 原因 |
|------|------|
| `scripts/workflow_manager.py` | Claude Code 原生 /resume 替代 |
| `scripts/data_modules/tests/test_workflow_manager.py` | 对应模块删除 |
| `skills/webnovel-resume/SKILL.md` | 同上 |
| `skills/webnovel-resume/references/workflow-resume.md` | 同上 |
| `agents/consistency-checker.md` | 合并到 reviewer.md |
| `agents/continuity-checker.md` | 合并到 reviewer.md |
| `agents/ooc-checker.md` | 合并到 reviewer.md |
| `agents/high-point-checker.md` | 合并到 reviewer.md |
| `agents/pacing-checker.md` | 合并到 reviewer.md |
| `agents/reader-pull-checker.md` | 合并到 reviewer.md |
| `references/checker-output-schema.md` | 被新 schema 替代 |
| `skills/webnovel-write/references/step-3-review-gate.md` | 逻辑内联到 SKILL.md |
| `skills/webnovel-write/references/step-5-debt-switch.md` | 0.6KB，内联到 SKILL.md |
| `skills/webnovel-write/references/workflow-details.md` | 已标记 deprecated |
| `skills/webnovel-write/references/step-1.5-contract.md` | context-agent 将重构 |

### 要创建的文件

| 文件 | 职责 |
|------|------|
| `agents/reviewer.md` | 统一审查 agent，输出结构化问题清单 |
| `references/review-schema.md` | 新审查输出 schema 定义 |
| `scripts/data_modules/review_schema.py` | 新 schema 的 Python 数据类 + 校验 |
| `scripts/data_modules/tests/test_review_schema.py` | 新 schema 测试 |

### 要修改的文件

| 文件 | 改什么 |
|------|--------|
| `skills/webnovel-write/SKILL.md` | 7 步新流程，去 workflow 记录，去 Step 2B，合并审查 |
| `scripts/review_pipeline.py` | 适配新 schema（无 overall_score，有 blocking_count） |
| `scripts/data_modules/webnovel.py` | 移除 workflow 命令路由 |
| `scripts/data_modules/index_manager.py` | review_metrics 表结构适配（去 overall_score，加 issues_count/blocking_count） |
| `scripts/data_modules/tests/test_webnovel_unified_cli.py` | 移除 workflow 相关测试 |
| `scripts/data_modules/tests/test_coverage_boost.py` | 移除 workflow 相关引用 |

---

## Task 1: 定义新审查 schema

**Files:**
- Create: `scripts/data_modules/review_schema.py`
- Create: `scripts/data_modules/tests/test_review_schema.py`
- Create: `references/review-schema.md`

- [ ] **Step 1: 写 schema 测试**

```python
# scripts/data_modules/tests/test_review_schema.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审查 schema 测试"""
import pytest
from data_modules.review_schema import ReviewIssue, ReviewResult, parse_review_output


def test_review_issue_blocking_defaults():
    """critical severity 默认 blocking=True"""
    issue = ReviewIssue(
        severity="critical",
        category="continuity",
        location="第3段",
        description="主角使用了已失去的能力",
    )
    assert issue.blocking is True


def test_review_issue_non_critical_not_blocking():
    """非 critical 默认 blocking=False"""
    issue = ReviewIssue(
        severity="high",
        category="setting",
        location="第7段",
        description="时间线矛盾",
    )
    assert issue.blocking is False


def test_review_result_counts():
    """blocking_count 自动计算"""
    result = ReviewResult(
        chapter=10,
        issues=[
            ReviewIssue(severity="critical", category="continuity", location="p1", description="d1"),
            ReviewIssue(severity="high", category="setting", location="p2", description="d2"),
            ReviewIssue(severity="high", category="timeline", location="p3", description="d3", blocking=True),
        ],
        summary="测试",
    )
    assert result.blocking_count == 2
    assert result.issues_count == 3
    assert result.has_blocking is True


def test_review_result_no_issues():
    result = ReviewResult(chapter=10, issues=[], summary="无问题")
    assert result.blocking_count == 0
    assert result.has_blocking is False


def test_review_result_to_dict_roundtrip():
    result = ReviewResult(
        chapter=10,
        issues=[
            ReviewIssue(severity="medium", category="ai_flavor", location="p5", description="AI味重",
                        evidence="'稳住心神'出现3次", fix_hint="替换为具体动作描写"),
        ],
        summary="1个AI味问题",
    )
    d = result.to_dict()
    assert d["chapter"] == 10
    assert d["blocking_count"] == 0
    assert len(d["issues"]) == 1
    assert d["issues"][0]["category"] == "ai_flavor"
    assert d["issues"][0]["fix_hint"] == "替换为具体动作描写"


def test_parse_review_output_from_dict():
    raw = {
        "issues": [
            {"severity": "critical", "category": "continuity", "location": "p1",
             "description": "矛盾", "evidence": "证据", "fix_hint": "修复"},
        ],
        "summary": "1个严重问题",
    }
    result = parse_review_output(chapter=5, raw=raw)
    assert result.chapter == 5
    assert result.blocking_count == 1


def test_parse_review_output_tolerates_missing_fields():
    raw = {
        "issues": [
            {"severity": "low", "description": "小问题"},
        ],
        "summary": "轻微",
    }
    result = parse_review_output(chapter=1, raw=raw)
    assert result.issues[0].category == "other"
    assert result.issues[0].location == ""


def test_review_result_to_metrics_dict():
    result = ReviewResult(
        chapter=10,
        issues=[
            ReviewIssue(severity="critical", category="continuity", location="p1", description="d1"),
            ReviewIssue(severity="high", category="ai_flavor", location="p2", description="d2"),
        ],
        summary="测试",
    )
    metrics = result.to_metrics_dict()
    assert metrics["chapter"] == 10
    assert metrics["issues_count"] == 2
    assert metrics["blocking_count"] == 1
    assert "continuity" in metrics["categories"]
    assert "ai_flavor" in metrics["categories"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd webnovel-writer/scripts && python -m pytest data_modules/tests/test_review_schema.py -v --no-cov`
Expected: FAIL — `ModuleNotFoundError: No module named 'data_modules.review_schema'`

- [ ] **Step 3: 实现 review_schema.py**

```python
# scripts/data_modules/review_schema.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
审查结果 schema（v6）。

替代原 checker-output-schema.md 的评分制，改为结构化问题清单。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

VALID_SEVERITIES = {"critical", "high", "medium", "low"}
VALID_CATEGORIES = {
    "continuity", "setting", "character", "timeline",
    "ai_flavor", "logic", "pacing", "other",
}


@dataclass
class ReviewIssue:
    severity: str
    category: str = "other"
    location: str = ""
    description: str = ""
    evidence: str = ""
    fix_hint: str = ""
    blocking: Optional[bool] = None

    def __post_init__(self):
        if self.severity not in VALID_SEVERITIES:
            self.severity = "medium"
        if self.category not in VALID_CATEGORIES:
            self.category = "other"
        if self.blocking is None:
            self.blocking = self.severity == "critical"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewResult:
    chapter: int
    issues: List[ReviewIssue] = field(default_factory=list)
    summary: str = ""

    @property
    def issues_count(self) -> int:
        return len(self.issues)

    @property
    def blocking_count(self) -> int:
        return sum(1 for i in self.issues if i.blocking)

    @property
    def has_blocking(self) -> bool:
        return self.blocking_count > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chapter": self.chapter,
            "issues": [i.to_dict() for i in self.issues],
            "issues_count": self.issues_count,
            "blocking_count": self.blocking_count,
            "has_blocking": self.has_blocking,
            "summary": self.summary,
        }

    def to_metrics_dict(self) -> Dict[str, Any]:
        categories = sorted(set(i.category for i in self.issues))
        return {
            "chapter": self.chapter,
            "issues_count": self.issues_count,
            "blocking_count": self.blocking_count,
            "categories": categories,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }


def parse_review_output(chapter: int, raw: Dict[str, Any]) -> ReviewResult:
    issues = []
    for item in raw.get("issues", []):
        if not isinstance(item, dict):
            continue
        issues.append(ReviewIssue(
            severity=str(item.get("severity", "medium")),
            category=str(item.get("category", "other")),
            location=str(item.get("location", "")),
            description=str(item.get("description", "")),
            evidence=str(item.get("evidence", "")),
            fix_hint=str(item.get("fix_hint", "")),
            blocking=item.get("blocking"),
        ))
    return ReviewResult(
        chapter=chapter,
        issues=issues,
        summary=str(raw.get("summary", "")),
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd webnovel-writer/scripts && python -m pytest data_modules/tests/test_review_schema.py -v --no-cov`
Expected: 8 passed

- [ ] **Step 5: 写 review-schema.md 参考文档**

```markdown
# 审查输出 Schema（v6）

统一审查 Agent 输出格式。替代原 checker-output-schema.md 的评分制。

## 核心变化

- **无总分**：不再输出 overall_score，改为结构化问题清单
- **blocking 语义**：替代原 timeline_gate，severity=critical 默认阻断
- **单 agent**：不再区分 6 个 checker，统一由 reviewer agent 输出

## Issue Schema

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| severity | critical/high/medium/low | ✅ | 严重度 |
| category | continuity/setting/character/timeline/ai_flavor/logic/pacing/other | ✅ | 问题分类 |
| location | string | ✅ | 位置（如"第3段"） |
| description | string | ✅ | 问题描述 |
| evidence | string | ❌ | 原文引用或记忆对比 |
| fix_hint | string | ❌ | 修复建议 |
| blocking | bool | ❌ | 是否阻断（critical 默认 true） |

## 阻断规则

- 存在任何 `blocking=true` 的 issue → Step 4 不得开始
- `severity=critical` 自动 `blocking=true`
- 其余 severity 由审查 agent 根据上下文判断

## 指标沉淀

每次审查写入 `index.db.review_metrics`：
- `chapter, issues_count, blocking_count, categories, timestamp`
- 用于趋势观测，不用于 gate 决策
```

- [ ] **Step 6: 提交**

```bash
git add scripts/data_modules/review_schema.py scripts/data_modules/tests/test_review_schema.py references/review-schema.md
git commit -m "feat: 新审查 schema（v6）——结构化问题清单替代评分制"
```

---

## Task 2: 创建统一审查 agent

**Files:**
- Create: `agents/reviewer.md`

- [ ] **Step 1: 写 reviewer.md**

```markdown
---
name: reviewer
description: 统一审查 agent。检查正文的设定一致性、叙事连贯性、角色一致性、时间线、AI味，输出结构化问题清单。
tools: Read, Grep, Bash
model: inherit
---

# reviewer（统一审查 agent）

## 身份与目标

你是章节审查员。你的职责是读完正文后，找出所有可验证的问题，输出结构化问题清单。

你不评分、不给建议、不写摘要性评价。你只找问题、给证据、给修复方向。

## 可用工具

- `Read`：读取正文、设定集、记忆数据
- `Grep`：在正文中搜索关键词
- `Bash`：调用记忆模块查询

```bash
# 查询角色当前状态
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" state get-entity --id "{entity_id}"

# 查询最近状态变更
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" index get-recent-state-changes --limit 20
```

## 思维链（ReAct）

对每个检查维度：
1. **读取**相关数据（角色状态、世界规则、上章摘要）
2. **对比**正文内容与数据
3. **判断**是否存在矛盾/问题
4. **记录**问题到清单（含 evidence 和 fix_hint）

## 输入

- `chapter`：章节号
- `chapter_file`：正文文件路径
- `project_root`：项目根目录
- `scripts_dir`：脚本目录

## 检查维度（按顺序执行）

### 1. 设定一致性（category: setting）
- 角色能力是否与当前境界匹配
- 地点描述是否与世界观一致
- 物品/货币使用是否符合已建立规则

### 2. 时间线（category: timeline）
- 本章时间是否与上章衔接（无回跳或有合理解释）
- 倒计时/截止日期是否正确推进
- 角色同时出现在两个地点

### 3. 叙事连贯（category: continuity）
- 上章钩子是否有回应
- 场景转换是否有过渡
- 情绪弧是否连续（上章愤怒本章突然平静无过渡）

### 4. 角色一致性（category: character）
- 对话风格是否符合角色特征
- 行为是否与已建立的性格/动机一致
- 角色知识边界——角色是否使用了不应知道的信息

### 5. 逻辑（category: logic）
- 因果关系是否成立
- 角色决策是否有合理动机
- 战斗/冲突结果是否符合已建立的力量对比

### 6. AI味（category: ai_flavor）
- 是否存在禁用词/禁用句式（稳住心神、不禁XXX、嘴角微微上扬等）
- 是否存在每段"起因→经过→结果→感悟"的四段式结构
- 是否存在过度解释（展示而非讲述的缺失）
- 情绪描写是否模板化（"眼中闪过一丝XXX"）

## 边界与禁区

- **不评分**——不输出 overall_score、不输出 pass/fail
- **不评价文笔质量**——"写得不够好"不是 issue，"与角色性格矛盾"才是
- **不建议情节改动**——"这里应该加个反转"不是 issue
- **不重复大纲内容**——不在 issue 中暴露未发生的剧情
- **只报可验证的问题**——必须有 evidence（原文引用 or 数据对比）

## 检查清单

完成审查前自检：
- [ ] 每个 issue 都有 evidence
- [ ] 没有"感觉"类的主观评价
- [ ] severity 分级合理（critical 仅用于确定的事实矛盾）
- [ ] category 归类正确
- [ ] blocking 字段只在 critical 或确认阻断时为 true

## 输出格式

严格按以下 JSON 格式输出（无其他文本）：

```json
{
  "issues": [
    {
      "severity": "critical | high | medium | low",
      "category": "continuity | setting | character | timeline | ai_flavor | logic | pacing | other",
      "location": "第N段 或 具体引用",
      "description": "问题描述",
      "evidence": "原文引用 vs 数据记录",
      "fix_hint": "修复方向",
      "blocking": true
    }
  ],
  "summary": "N个问题：X个阻断，Y个高优"
}
```

## 错误处理

- 无法读取角色状态 → 跳过设定一致性检查，在 summary 中标注"无法校验设定一致性：数据读取失败"
- 无法读取上章摘要 → 跳过连贯性检查中的"上章钩子回应"项
- 正文为空 → 输出单条 critical issue："正文为空"
```

- [ ] **Step 2: 提交**

```bash
git add agents/reviewer.md
git commit -m "feat: 统一审查 agent reviewer.md——合并6个checker为1个"
```

---

## Task 3: 删除 workflow 模块和 resume skill

**Files:**
- Delete: `scripts/workflow_manager.py`
- Delete: `scripts/data_modules/tests/test_workflow_manager.py`
- Delete: `skills/webnovel-resume/SKILL.md`
- Delete: `skills/webnovel-resume/references/workflow-resume.md`
- Modify: `scripts/data_modules/webnovel.py`
- Modify: `scripts/data_modules/tests/test_coverage_boost.py`

- [ ] **Step 1: 从 webnovel.py 移除 workflow 命令路由**

在 `scripts/data_modules/webnovel.py` 中删除 workflow 相关的 parser 和路由：

删除 parser 定义：
```python
# 删除这两行
p_workflow = sub.add_parser("workflow", help="转发到 workflow_manager.py")
p_workflow.add_argument("args", nargs=argparse.REMAINDER)
```

删除路由分支：
```python
# 删除这两行
if tool == "workflow":
    raise SystemExit(_run_script("workflow_manager.py", [*forward_args, *rest]))
```

- [ ] **Step 2: 从 test_coverage_boost.py 移除 workflow 相关测试**

删除 `test_webnovel_passthrough_workflow_script` 测试函数。

- [ ] **Step 3: 删除 workflow_manager.py 和测试**

```bash
git rm scripts/workflow_manager.py
git rm scripts/data_modules/tests/test_workflow_manager.py
```

- [ ] **Step 4: 删除 resume skill**

```bash
git rm skills/webnovel-resume/SKILL.md
git rm skills/webnovel-resume/references/workflow-resume.md
rmdir skills/webnovel-resume/references 2>/dev/null || true
rmdir skills/webnovel-resume 2>/dev/null || true
```

- [ ] **Step 5: 运行测试确认无破损**

Run: `cd "D:\wk\novel skill\webnovel-writer" && python -m pytest --no-cov --tb=short`
Expected: 全部通过（数量会减少，因为删了 test_workflow_manager.py 的 10 个测试）

- [ ] **Step 6: 提交**

```bash
git add -A
git commit -m "refactor: 移除 workflow_manager + resume skill，由 Claude Code /resume 替代"
```

---

## Task 4: 删除 6 个旧 checker agent 和旧 schema

**Files:**
- Delete: `agents/consistency-checker.md`
- Delete: `agents/continuity-checker.md`
- Delete: `agents/ooc-checker.md`
- Delete: `agents/high-point-checker.md`
- Delete: `agents/pacing-checker.md`
- Delete: `agents/reader-pull-checker.md`
- Delete: `references/checker-output-schema.md`
- Delete: `skills/webnovel-write/references/step-3-review-gate.md`

- [ ] **Step 1: 删除旧 checker agents**

```bash
git rm agents/consistency-checker.md
git rm agents/continuity-checker.md
git rm agents/ooc-checker.md
git rm agents/high-point-checker.md
git rm agents/pacing-checker.md
git rm agents/reader-pull-checker.md
```

- [ ] **Step 2: 删除旧 schema 和 review gate**

```bash
git rm references/checker-output-schema.md
git rm skills/webnovel-write/references/step-3-review-gate.md
```

- [ ] **Step 3: 提交**

```bash
git add -A
git commit -m "refactor: 移除6个旧checker agent和旧schema，由reviewer.md替代"
```

---

## Task 5: 更新 review_pipeline.py 适配新 schema

**Files:**
- Modify: `scripts/review_pipeline.py`
- Modify: `scripts/data_modules/tests/test_webnovel_unified_cli.py`

- [ ] **Step 1: 写测试——review_pipeline 适配新 schema**

在 `test_webnovel_unified_cli.py` 中修改 `test_review_pipeline_builds_artifacts`，将旧的 checker 多结果格式改为新的单 reviewer 输出：

```python
def test_review_pipeline_builds_artifacts_v6(tmp_path):
    _ensure_scripts_on_path()
    import review_pipeline as review_pipeline_module

    project_root = (tmp_path / "book").resolve()
    (project_root / ".webnovel").mkdir(parents=True, exist_ok=True)
    (project_root / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")

    review_results_path = tmp_path / "review_results.json"
    review_results_path.write_text(
        json.dumps(
            {
                "issues": [
                    {
                        "severity": "critical",
                        "category": "timeline",
                        "location": "第2段",
                        "description": "时间线回跳",
                        "evidence": "上章深夜，本章突然中午",
                        "fix_hint": "补时间过渡",
                        "blocking": True,
                    },
                    {
                        "severity": "medium",
                        "category": "ai_flavor",
                        "location": "第5段",
                        "description": "'稳住心神'出现2次",
                        "fix_hint": "替换为具体动作",
                    },
                ],
                "summary": "1个阻断，1个中等",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = review_pipeline_module.build_review_artifacts(
        project_root=project_root,
        chapter=20,
        review_results_path=review_results_path,
        report_file="",
    )

    assert payload["review_result"]["blocking_count"] == 1
    assert payload["review_result"]["has_blocking"] is True
    assert payload["review_result"]["issues_count"] == 2
    assert payload["metrics"]["issues_count"] == 2
    assert payload["metrics"]["blocking_count"] == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd webnovel-writer/scripts && python -m pytest data_modules/tests/test_webnovel_unified_cli.py::test_review_pipeline_builds_artifacts_v6 -v --no-cov`
Expected: FAIL（review_pipeline 还是旧逻辑）

- [ ] **Step 3: 重写 review_pipeline.py**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 3 审查结果处理。

读取 reviewer agent 的原始输出 JSON，解析为 ReviewResult，
生成 metrics 用于 index.db 沉淀。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional


def _ensure_scripts_path() -> None:
    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


_ensure_scripts_path()

from data_modules.review_schema import ReviewResult, parse_review_output


def build_review_artifacts(
    project_root: Path,
    chapter: int,
    review_results_path: Path,
    report_file: str = "",
) -> Dict[str, Any]:
    raw = json.loads(review_results_path.read_text(encoding="utf-8"))
    result = parse_review_output(chapter=chapter, raw=raw)
    metrics = result.to_metrics_dict()
    if report_file:
        metrics["report_file"] = report_file

    return {
        "chapter": chapter,
        "review_result": result.to_dict(),
        "metrics": metrics,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Review pipeline v6")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--chapter", type=int, required=True)
    parser.add_argument("--review-results", required=True)
    parser.add_argument("--metrics-out", default="")
    parser.add_argument("--report-file", default="")

    args = parser.parse_args()
    project_root = Path(args.project_root)
    review_results_path = Path(args.review_results)

    payload = build_review_artifacts(
        project_root=project_root,
        chapter=args.chapter,
        review_results_path=review_results_path,
        report_file=args.report_file,
    )

    if args.metrics_out:
        out_path = Path(args.metrics_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(payload["metrics"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd webnovel-writer/scripts && python -m pytest data_modules/tests/test_webnovel_unified_cli.py -v --no-cov`
Expected: 全部通过

- [ ] **Step 5: 提交**

```bash
git add scripts/review_pipeline.py scripts/data_modules/tests/test_webnovel_unified_cli.py
git commit -m "refactor: review_pipeline 适配 v6 schema——无评分，结构化问题清单"
```

---

## Task 6: 更新 webnovel-write SKILL.md（新 7 步流程）

**Files:**
- Modify: `skills/webnovel-write/SKILL.md`
- Delete: `skills/webnovel-write/references/step-5-debt-switch.md`
- Delete: `skills/webnovel-write/references/workflow-details.md`
- Delete: `skills/webnovel-write/references/step-1.5-contract.md`

- [ ] **Step 1: 删除废弃引用文件**

```bash
git rm skills/webnovel-write/references/step-5-debt-switch.md
git rm skills/webnovel-write/references/workflow-details.md
git rm skills/webnovel-write/references/step-1.5-contract.md
```

- [ ] **Step 2: 重写 SKILL.md**

完整重写 `skills/webnovel-write/SKILL.md`，核心变化：

1. **流程从 8 步变 7 步**：
```
Step 0.5 预检 → Step 1 上下文搜集 → Step 2 起草 → Step 3 审查 → Step 4 润色+风格+anti-AI → Step 5 数据回写 → Step 6 Git
```

2. **去掉所有 workflow 记录命令**（删除每步前后的 `workflow start-step` / `complete-step`）

3. **Step 2B 合并到 Step 4**：Step 4 职责变为"润色 + 风格适配 + anti-AI 修复"

4. **Step 3 改为单 reviewer agent**：
```
使用 Task 调用 reviewer agent（不再调用 6 个独立 checker）
输出：review_results.json（新 schema）
通过 review_pipeline 生成 metrics
blocking issue 存在时阻断
```

5. **Step 4 增加 anti-AI 职责**：
```
- 消费 Step 3 的问题清单，逐条修复
- 执行风格适配（原 Step 2B 的工作）
- anti-AI 最终 gate：修复后复检，确认无 blocking 残留
```

6. **模式定义更新**：
```
标准：Step 0.5 → 1 → 2 → 3 → 4 → 5 → 6
--fast：Step 0.5 → 1 → 2 → 3(轻量) → 4 → 5 → 6
--minimal：Step 0.5 → 1 → 2 → 4(仅排版) → 5 → 6
```

7. **References 更新**：移除对已删文件的引用，添加 `review-schema.md` 引用

- [ ] **Step 3: 提交**

```bash
git add -A
git commit -m "refactor: webnovel-write SKILL.md v6——7步流程，单reviewer，合并风格适配"
```

---

## Task 7: 清理旧 review_pipeline 测试并跑全量回归

**Files:**
- Modify: `scripts/data_modules/tests/test_webnovel_unified_cli.py`

- [ ] **Step 1: 移除旧 review_pipeline 测试中不兼容的断言**

更新 `test_review_pipeline_builds_artifacts` 和 `test_review_pipeline_main_creates_output_directories` 以适配新 schema。旧测试依赖 `overall_score`、`timeline_gate` 等已移除的字段。

如果 Task 5 的新测试已覆盖，直接删除旧版测试。

- [ ] **Step 2: 全量回归测试**

Run: `cd "D:\wk\novel skill\webnovel-writer" && python -m pytest --tb=short`
Expected: 全部通过，覆盖率 ≥ 90%

- [ ] **Step 3: 如有失败修复后提交**

```bash
git add -A
git commit -m "test: 清理旧 review 测试，全量回归通过"
```

---

## Task 8: 最终验证

- [ ] **Step 1: 确认删除完整性**

```bash
# 这些文件应该不存在
test ! -f webnovel-writer/scripts/workflow_manager.py
test ! -f webnovel-writer/skills/webnovel-resume/SKILL.md
test ! -f webnovel-writer/agents/consistency-checker.md
test ! -f webnovel-writer/agents/continuity-checker.md
test ! -f webnovel-writer/agents/ooc-checker.md
test ! -f webnovel-writer/agents/high-point-checker.md
test ! -f webnovel-writer/agents/pacing-checker.md
test ! -f webnovel-writer/agents/reader-pull-checker.md
test ! -f webnovel-writer/references/checker-output-schema.md

# 这些文件应该存在
test -f webnovel-writer/agents/reviewer.md
test -f webnovel-writer/references/review-schema.md
test -f webnovel-writer/scripts/data_modules/review_schema.py
```

- [ ] **Step 2: 全量测试 + 覆盖率**

Run: `cd "D:\wk\novel skill\webnovel-writer" && python -m pytest`
Expected: 全部通过，覆盖率 ≥ 90%

- [ ] **Step 3: 确认 agents/ 目录只剩 3 个 agent**

```bash
ls webnovel-writer/agents/
# 期望：context-agent.md  data-agent.md  reviewer.md
```

- [ ] **Step 4: 最终提交（如有遗漏修复）**

```bash
git add -A
git commit -m "chore: Phase 1 完成——清理验证通过"
```
