# v6 Migration Completion Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成 v6 迁移剩余工作——清理 legacy 代码、落地章节状态模型、修正 spec 与实现的不一致、通过退出标准验证。

**Architecture:** 三条并行工作线：(A) legacy 代码删除与清理，(B) 章节状态模型新增，(C) spec/参考资料修正。A 和 C 无依赖可并行，B 是新功能需独立开发测试。

**Tech Stack:** Python 3.13, pytest, SQLite (state.json + index.db), Claude Code plugin (markdown skills/agents)

**Spec:** `docs/superpowers/specs/2026-04-02-harness-v6-design.md` (v6)

**前置条件：** Phase 1 的"创建新模块"部分已完成（reviewer.md、review_schema.py、review_pipeline.py 均已存在且通过测试）。Phase 3（memory_contract）和 Phase 4（context-agent research 模式）已完成。

---

## 当前差距摘要

| 类别 | 残留项 | 文件 |
|------|--------|------|
| 旧 checker 函数 | `_normalize_checker_issue`, `_build_timeline_gate`, `_aggregate_checker_results`, `ReviewAggregateResult` | `index_manager.py:208-232, 678-808` |
| 旧 checker CLI | `aggregate-review-results`, `materialize-review-metrics` | `index_manager.py:963-969, 1318-1327` |
| 旧 checker 脚本 | 整文件 570 行 | `golden_three_checker.py` |
| 旧 checker 测试 | `test_aggregate_checker_results_cli` (L1428-1551), `test_aggregate_checker_results_blocks_...` (L1553-1596) | `test_data_modules.py` |
| 旧 checker 测试 | `test_index_aggregate_review_results_forwards_...` (L173) | `test_webnovel_unified_cli.py:173-218` |
| 旧 checker 引用 | `continuity-checker` 在已知 checker 列表 | `test_prompt_integrity.py:247` |
| workflow 残留 | 注释引用 + 测试白名单 | `webnovel.py:94`, `test_prompt_integrity.py:221` |
| Step 2B 残留 | 职责边界说明 | `polish-guide.md:13-17` |
| legacy 引用 | `continuity-checker` 映射表 | `reading-power-taxonomy.md:343-348` |
| legacy 消费 | `overall_score` 用于低分告警 | `context_manager.py:310-318` |
| 缺失功能 | 章节状态模型 | 无（需新增到 `state_manager.py`） |
| spec 不一致 | "v0 接口尚未实现"但实际已实现 | spec 4.5 |

---

## File Structure

### 要删除的文件

| 文件 | 原因 |
|------|------|
| `scripts/golden_three_checker.py` | 旧 checker 模式，570 行，已被 reviewer 替代 |

### 要修改的文件

| 文件 | 改什么 |
|------|--------|
| `scripts/data_modules/index_manager.py` | 删除 `ReviewAggregateResult`、旧 checker 函数、旧 CLI 命令 |
| `scripts/data_modules/context_manager.py` | `overall_score` 低分判断改为 severity_counts |
| `scripts/data_modules/tests/test_data_modules.py` | 删除旧 checker 聚合测试（~170 行） |
| `scripts/data_modules/tests/test_webnovel_unified_cli.py` | 删除旧 aggregate-review-results 转发测试 |
| `scripts/data_modules/tests/test_prompt_integrity.py` | 清理 checker 白名单、workflow_manager 白名单 |
| `scripts/data_modules/webnovel.py` | 清理 workflow_manager 注释 |
| `scripts/data_modules/state_manager.py` | 新增 chapter_status 管理 |
| `skills/webnovel-write/references/polish-guide.md` | 删除 Step 2B 边界段落 |
| `references/reading-power-taxonomy.md` | 更新 checker 映射表 |
| `docs/superpowers/specs/2026-04-02-harness-v6-design.md` | 修正 spec 与实现不一致 |

### 要创建的文件

| 文件 | 职责 |
|------|------|
| `scripts/data_modules/tests/test_chapter_status.py` | 章节状态模型测试 |

---

## Task 1: 删除旧 checker 聚合函数与 CLI

**Files:**
- Modify: `scripts/data_modules/index_manager.py`
- Modify: `scripts/data_modules/tests/test_data_modules.py`
- Modify: `scripts/data_modules/tests/test_webnovel_unified_cli.py`

- [ ] **Step 1: 从 index_manager.py 删除 ReviewAggregateResult dataclass**

删除 `index_manager.py` 中 L208-232 的 `ReviewAggregateResult` dataclass 及其 `to_review_metrics` 方法。保留 `ReviewMetrics` dataclass（仍被 `save-review-metrics` CLI 使用）。

```python
# 删除以下代码块（约 25 行）：
@dataclass
class ReviewAggregateResult:
    """Step 3 审查聚合结果"""
    chapter: int
    start_chapter: int
    end_chapter: int
    selected_checkers: List[str] = field(default_factory=list)
    checkers: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    issues: List[Dict[str, Any]] = field(default_factory=list)
    overall_score: float = 0.0
    severity_counts: Dict[str, int] = field(default_factory=dict)
    timeline_gate: Dict[str, Any] = field(default_factory=dict)
    # ... 及其所有方法
```

- [ ] **Step 2: 从 index_manager.py 删除旧 checker 函数**

删除以下 3 个函数（L678-808）：

```python
# 删除这 3 个函数：
def _normalize_checker_issue(issue: object) -> dict: ...
def _build_timeline_gate(issues: ...) -> Dict[str, Any]: ...
def _aggregate_checker_results(chapter: int, raw_data: object) -> dict: ...
```

- [ ] **Step 3: 从 index_manager.py 删除旧 CLI 命令注册**

删除 `aggregate-review-results` 和 `materialize-review-metrics` 的 parser 注册（L963-969）：

```python
# 删除：
review_aggregate_parser = subparsers.add_parser("aggregate-review-results")
review_aggregate_parser.add_argument("--chapter", ...)
review_aggregate_parser.add_argument("--data", ...)

review_materialize_parser = subparsers.add_parser("materialize-review-metrics")
review_materialize_parser.add_argument("--chapter", ...)
review_materialize_parser.add_argument("--data", ...)
```

删除对应的 CLI 处理分支（L1318-1327）：

```python
# 删除：
elif args.command == "aggregate-review-results":
    ...
elif args.command == "materialize-review-metrics":
    ...
```

- [ ] **Step 4: 删除旧 checker 测试**

从 `test_data_modules.py` 删除以下测试函数（L1428-1596，~170 行）：

```python
# 删除这 2 个测试函数：
def test_aggregate_checker_results_cli(temp_project, monkeypatch, capsys): ...
def test_aggregate_checker_results_blocks_overall_pass_for_high_timeline_issue(temp_project, monkeypatch, capsys): ...
```

从 `test_webnovel_unified_cli.py` 删除旧 aggregate 转发测试（L173-218）：

```python
# 删除：
def test_index_aggregate_review_results_forwards_with_resolved_project_root(monkeypatch, tmp_path): ...
```

- [ ] **Step 5: 运行测试确认无破损**

Run: `cd "D:/wk/novel skill/webnovel-writer" && python -m pytest webnovel-writer/scripts -x --tb=short --no-cov`
Expected: 全部通过

- [ ] **Step 6: 提交**

```bash
cd "D:/wk/novel skill/webnovel-writer"
git add webnovel-writer/scripts/data_modules/index_manager.py webnovel-writer/scripts/data_modules/tests/test_data_modules.py webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py
git commit -m "$(cat <<'EOF'
refactor: 移除旧 checker 聚合函数和 CLI

删除 ReviewAggregateResult、_aggregate_checker_results、
_build_timeline_gate、_normalize_checker_issue 及对应 CLI
和测试。reviewer + review_pipeline 已完全替代。
EOF
)"
```

---

## Task 2: 删除 golden_three_checker.py

**Files:**
- Delete: `scripts/golden_three_checker.py`

- [ ] **Step 1: 确认无运行时依赖**

Run: `cd "D:/wk/novel skill/webnovel-writer" && grep -r "golden_three" webnovel-writer/ --include="*.py" --include="*.md" | grep -v golden_three_checker.py`
Expected: 无命中（或仅在 test_prompt_integrity 白名单中）

- [ ] **Step 2: 删除文件**

```bash
cd "D:/wk/novel skill/webnovel-writer"
git rm webnovel-writer/scripts/golden_three_checker.py
```

- [ ] **Step 3: 运行测试**

Run: `cd "D:/wk/novel skill/webnovel-writer" && python -m pytest webnovel-writer/scripts -x --tb=short --no-cov`
Expected: 全部通过

- [ ] **Step 4: 提交**

```bash
git commit -m "refactor: 删除 golden_three_checker.py（570行），已被 reviewer 替代"
```

---

## Task 3: 清理散落的 legacy 引用

**Files:**
- Modify: `scripts/data_modules/webnovel.py`
- Modify: `scripts/data_modules/tests/test_prompt_integrity.py`
- Modify: `skills/webnovel-write/references/polish-guide.md`
- Modify: `references/reading-power-taxonomy.md`

- [ ] **Step 1: 清理 webnovel.py 的 workflow_manager 注释**

`webnovel.py:94` 改为不再提及 workflow_manager：

```python
# 旧：
#     用途：兼容没有 main() 的脚本（例如 workflow_manager.py）。
# 新：
#     用途：兼容没有 main() 的脚本。
```

- [ ] **Step 2: 清理 test_prompt_integrity.py**

从 `KNOWN_DELETED_FILES` 列表（L215-223）中添加 `golden_three_checker.py`（如果需要），并从任何 checker 白名单中移除 `continuity-checker` 等旧 checker 名称（L247）。

确认 L247 处 `continuity-checker` 引用的上下文，如果是"不应出现在 prompt 中"的检查，则保留；如果是"允许出现"的白名单，则移除。

- [ ] **Step 3: 清理 polish-guide.md 的 Step 2B 段落**

删除 `polish-guide.md:13-17` 中关于 Step 2B 的职责边界说明：

```markdown
# 删除以下内容：
与 Step 2B 的职责边界：
- Step 2B：风格转译（表达层）
- Step 4：问题修复（质量层），包括审查问题修复、Anti-AI 终检、毒点规避

若已执行 Step 2B，本步骤不重复全量句式改写，只做"必要修改"。
```

替换为：

```markdown
职责定义：
- Step 4 同时负责风格适配（消除模板腔、说明腔、机械腔）和问题修复
- 包括审查问题修复、Anti-AI 终检、毒点规避
```

- [ ] **Step 4: 清理 reading-power-taxonomy.md 的 checker 映射表**

更新 `reading-power-taxonomy.md:343-349` 的旧 checker 映射表：

```markdown
# 旧：
| 现有 Checker | 使用的 Taxonomy |
|--------------|----------------|
| `reader-pull-checker` | 钩子类型、钩子强度、Hard-002 |
| `high-point-checker` | 爽点模式、微兑现 |
| `pacing-checker` | Hard-003 (节奏灾难) |
| `continuity-checker` | Hard-001 (可读性底线) |

# 新：
| 审查维度 (reviewer) | 使用的 Taxonomy |
|---------------------|----------------|
| continuity | Hard-001 (可读性底线)、Hard-002 (结构完整) |
| pacing | Hard-003 (节奏灾难)、爽点模式、微兑现 |
| ai_flavor | 钩子类型、钩子强度 |
```

- [ ] **Step 5: 运行测试**

Run: `cd "D:/wk/novel skill/webnovel-writer" && python -m pytest webnovel-writer/scripts -x --tb=short --no-cov`
Expected: 全部通过

- [ ] **Step 6: 提交**

```bash
cd "D:/wk/novel skill/webnovel-writer"
git add webnovel-writer/scripts/data_modules/webnovel.py webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py webnovel-writer/skills/webnovel-write/references/polish-guide.md webnovel-writer/references/reading-power-taxonomy.md
git commit -m "$(cat <<'EOF'
refactor: 清理 legacy 引用——workflow_manager 注释、Step 2B 边界、旧 checker 映射
EOF
)"
```

---

## Task 4: context_manager.py 的 overall_score 消费迁移

**Files:**
- Modify: `scripts/data_modules/context_manager.py`

- [ ] **Step 1: 检查 overall_score 消费点**

`context_manager.py:310-318` 用 `overall_score < 75` 判断低分告警。改为使用 `severity_counts` 或 `notes` 字段判断：

```python
# 旧逻辑（L310-318）：
for row in review_trend.get("recent_ranges", []):
    score = row.get("overall_score")
    if isinstance(score, (int, float)) and float(score) < 75:
        low_score_ranges.append({
            "start_chapter": row.get("start_chapter"),
            "end_chapter": row.get("end_chapter"),
            "overall_score": score,
        })

# 新逻辑：
for row in review_trend.get("recent_ranges", []):
    score = row.get("overall_score")
    notes = row.get("notes", "")
    has_issues = "blocking=" in notes and "blocking=0" not in notes
    is_low_score = isinstance(score, (int, float)) and float(score) < 75
    if is_low_score or has_issues:
        low_score_ranges.append({
            "start_chapter": row.get("start_chapter"),
            "end_chapter": row.get("end_chapter"),
            "overall_score": score if isinstance(score, (int, float)) else 0.0,
            "notes": notes,
        })
```

- [ ] **Step 2: 运行相关测试**

Run: `cd "D:/wk/novel skill/webnovel-writer" && python -m pytest webnovel-writer/scripts/data_modules/tests/test_context_manager.py -x --tb=short --no-cov`
Expected: 通过

- [ ] **Step 3: 提交**

```bash
cd "D:/wk/novel skill/webnovel-writer"
git add webnovel-writer/scripts/data_modules/context_manager.py
git commit -m "refactor: context_manager 低分告警兼容 v6 severity_counts"
```

---

## Task 5: 章节状态模型落地

**Files:**
- Modify: `scripts/data_modules/state_manager.py`
- Create: `scripts/data_modules/tests/test_chapter_status.py`

- [ ] **Step 1: 写测试**

```python
# scripts/data_modules/tests/test_chapter_status.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""章节状态模型测试"""
import json
import pytest
from pathlib import Path


@pytest.fixture
def state_project(tmp_path):
    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir()
    state_file = webnovel_dir / "state.json"
    state_file.write_text(json.dumps({
        "progress": {"current_chapter": 5}
    }), encoding="utf-8")
    return tmp_path


def _make_manager(project_root):
    import sys
    scripts_dir = str(Path(__file__).resolve().parent.parent.parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from data_modules.config import DataModulesConfig
    from data_modules.state_manager import StateManager
    config = DataModulesConfig(
        project_root=project_root,
        webnovel_dir=project_root / ".webnovel",
    )
    return StateManager(config)


def test_get_chapter_status_default(state_project):
    sm = _make_manager(state_project)
    sm._load_state()
    status = sm.get_chapter_status(5)
    assert status is None  # 未设置过


def test_set_chapter_status_drafted(state_project):
    sm = _make_manager(state_project)
    sm._load_state()
    sm.set_chapter_status(5, "chapter_drafted")
    status = sm.get_chapter_status(5)
    assert status == "chapter_drafted"


def test_set_chapter_status_monotonic(state_project):
    sm = _make_manager(state_project)
    sm._load_state()
    sm.set_chapter_status(5, "chapter_reviewed")
    # 不能回退到 drafted
    with pytest.raises(ValueError, match="不可回退"):
        sm.set_chapter_status(5, "chapter_drafted")


def test_set_chapter_status_progression(state_project):
    sm = _make_manager(state_project)
    sm._load_state()
    sm.set_chapter_status(5, "chapter_drafted")
    sm.set_chapter_status(5, "chapter_reviewed")
    sm.set_chapter_status(5, "chapter_committed")
    assert sm.get_chapter_status(5) == "chapter_committed"


def test_chapter_status_persists(state_project):
    sm = _make_manager(state_project)
    sm._load_state()
    sm.set_chapter_status(3, "chapter_drafted")
    sm._save_state()

    # 重新加载
    sm2 = _make_manager(state_project)
    sm2._load_state()
    assert sm2.get_chapter_status(3) == "chapter_drafted"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "D:/wk/novel skill/webnovel-writer/webnovel-writer/scripts" && python -m pytest data_modules/tests/test_chapter_status.py -v --no-cov`
Expected: FAIL — `AttributeError: 'StateManager' object has no attribute 'get_chapter_status'`

- [ ] **Step 3: 在 state_manager.py 中实现 chapter_status**

在 `StateManager` 类中添加以下方法：

```python
CHAPTER_STATUS_ORDER = ["chapter_drafted", "chapter_reviewed", "chapter_committed"]

def get_chapter_status(self, chapter: int) -> Optional[str]:
    """查询章节状态。"""
    statuses = self._state.get("progress", {}).get("chapter_status", {})
    return statuses.get(str(chapter))

def set_chapter_status(self, chapter: int, status: str) -> None:
    """设置章节状态（单调递进，不可回退）。"""
    if status not in self.CHAPTER_STATUS_ORDER:
        raise ValueError(f"无效状态: {status}，有效值: {self.CHAPTER_STATUS_ORDER}")

    current = self.get_chapter_status(chapter)
    if current is not None:
        current_idx = self.CHAPTER_STATUS_ORDER.index(current)
        new_idx = self.CHAPTER_STATUS_ORDER.index(status)
        if new_idx < current_idx:
            raise ValueError(
                f"章节 {chapter} 状态不可回退: {current} -> {status}"
            )
        if new_idx == current_idx:
            return  # 幂等

    progress = self._state.setdefault("progress", {})
    chapter_status = progress.setdefault("chapter_status", {})
    chapter_status[str(chapter)] = status
    self._save_state()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd "D:/wk/novel skill/webnovel-writer/webnovel-writer/scripts" && python -m pytest data_modules/tests/test_chapter_status.py -v --no-cov`
Expected: 5 passed

- [ ] **Step 5: 添加 CLI 子命令**

在 `state_manager.py` 的 CLI 部分添加 `get-chapter-status` 和 `set-chapter-status` 子命令：

```python
# parser 注册
status_get_parser = subparsers.add_parser("get-chapter-status")
status_get_parser.add_argument("--chapter", type=int, required=True)

status_set_parser = subparsers.add_parser("set-chapter-status")
status_set_parser.add_argument("--chapter", type=int, required=True)
status_set_parser.add_argument("--status", required=True,
    choices=["chapter_drafted", "chapter_reviewed", "chapter_committed"])
```

```python
# 命令处理
elif args.command == "get-chapter-status":
    manager._load_state()
    status = manager.get_chapter_status(args.chapter)
    emit_success({"chapter": args.chapter, "status": status},
                 message="chapter_status")

elif args.command == "set-chapter-status":
    manager._load_state()
    manager.set_chapter_status(args.chapter, args.status)
    emit_success({"chapter": args.chapter, "status": args.status},
                 message="chapter_status_set")
```

- [ ] **Step 6: 提交**

```bash
cd "D:/wk/novel skill/webnovel-writer"
git add webnovel-writer/scripts/data_modules/state_manager.py webnovel-writer/scripts/data_modules/tests/test_chapter_status.py
git commit -m "$(cat <<'EOF'
feat: 章节状态模型——chapter_drafted/reviewed/committed

单调递进状态机，支持 CLI 查询和设置。
用于 v6 Write 流程的充分性闸门。
EOF
)"
```

---

## Task 6: 修正 spec 与实现不一致

**Files:**
- Modify: `docs/superpowers/specs/2026-04-02-harness-v6-design.md`

- [ ] **Step 1: 修正 memory contract v0 描述**

将 4.5 节中的：

```
**v0（目标接口，供 Phase 1/2A prompt 重构面向编程）：**

> 注：v0 接口当前尚未实现，现有实现通过 `webnovel.py` CLI 子命令（如 `state get-entity`、`index get-recent-state-changes`）充当。Phase 3 将这些 CLI 收口为以下统一契约。
```

改为：

```
**v0（已实现，当前冻结）：**

> v0 接口已通过 `memory_contract.py`（Protocol + 类型）和 `memory_contract_adapter.py`（适配器）实现，CLI 入口为 `webnovel.py memory-contract` 子命令。context-agent 已在使用。
```

- [ ] **Step 2: 更新 Phase 表状态**

在实施路径表格中，Phase 3 和 Phase 4 的状态列加注"已完成"：

```markdown
| Phase 3 | 记忆模块接口契约设计 | 无 | **✅ 已完成** |
| Phase 4 | Context-agent research 模式重构 | Phase 3（契约） | **✅ 已完成** |
```

- [ ] **Step 3: 更新版本号**

```
> 状态：草案 v7（v6 + 实现对齐修正）
```

- [ ] **Step 4: 提交**

```bash
cd "D:/wk/novel skill/webnovel-writer"
git add docs/superpowers/specs/2026-04-02-harness-v6-design.md
git commit -m "docs: spec v7——修正 memory contract 状态，Phase 3/4 标记已完成"
```

---

## Task 7: 全量回归验证 + 退出标准检查

**Files:** 无新文件

- [ ] **Step 1: 全量测试**

Run: `cd "D:/wk/novel skill/webnovel-writer" && python -m pytest webnovel-writer/scripts --tb=short`
Expected: 全部通过

- [ ] **Step 2: 退出标准逐条验证**

```bash
cd "D:/wk/novel skill/webnovel-writer"

# 标准 1: 无旧 checker 运行时引用
echo "--- 标准 1: 旧 checker 引用 ---"
grep -rn "continuity-checker\|setting-checker\|ooc-checker\|high-point-checker\|pacing-checker\|reader-pull-checker" \
  webnovel-writer/skills/ webnovel-writer/agents/ webnovel-writer/scripts/*.py \
  --include="*.md" --include="*.py" || echo "PASS: 无旧 checker 引用"

# 标准 2: 审查路径唯一
echo "--- 标准 2: 审查路径 ---"
grep -l "reviewer" webnovel-writer/skills/webnovel-write/SKILL.md webnovel-writer/skills/webnovel-review/SKILL.md && echo "PASS: 均走 reviewer"

# 标准 3: workflow_manager 移除
echo "--- 标准 3: workflow_manager ---"
test ! -f webnovel-writer/scripts/workflow_manager.py && echo "PASS: 文件已删除" || echo "FAIL: 文件仍存在"

# 标准 4: legacy 术语（运行时路径）
echo "--- 标准 4: legacy 术语 ---"
grep -rn "timeline_gate\|_aggregate_checker\|_normalize_checker\|_build_timeline_gate" \
  webnovel-writer/scripts/ --include="*.py" | grep -v "test_" | grep -v "__pycache__" || echo "PASS: 运行时无 legacy"

# 标准 6: 章节状态模型
echo "--- 标准 6: 章节状态 CLI ---"
cd webnovel-writer/scripts && python -X utf8 data_modules/state_manager.py --help 2>&1 | grep -q "get-chapter-status" && echo "PASS: CLI 已注册" || echo "FAIL: CLI 未注册"
```

- [ ] **Step 3: 如有失败项，修复后提交**

```bash
cd "D:/wk/novel skill/webnovel-writer"
git add -A
git commit -m "chore: v6 迁移退出标准验证通过"
```
