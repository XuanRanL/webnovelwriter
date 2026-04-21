# Step 8 · Post-Commit Polish 完整规范

> 引入版本：2026-04-20（Round 14.5）
> 触发血教训：<example-project> Ch1 v3 polish 裸跑事故 — 58 个 ASCII 引号 + 414 字 word_count 漂移
> 唯一执行入口：`scripts/polish_cycle.py`

---

## 1. 定位与目的

**Step 8 = Step 7 commit 之后任何对正文文件的修改的标准化执行通道。**

Step 1-7 完成后，章节正文进入"已提交但允许迭代"状态。读者视角 checker（naturalness / reader-critic）经常在多轮 polish 后才能稳定到 90+，外部模型 reader_flow 维度也常给出 medium/low 反馈，作者/AI 必然要回头改正文。

如果不强制走 Step 8：
- `post_draft_check.py` 不再跑 → ASCII 引号、Markdown 残留、U+FFFD 等机械错误漏过
- `hygiene_check.py` 不再跑 → word_count、文件结构、checker 数据等无人校验
- `state.json.chapter_meta` 不更新 → `narrative_version` 永远停在 v2，下章 context-agent 看到旧版本
- `workflow_state.json` 不登记 → polish 任务在工作流系统里"不存在"，跨章 trend / Step 6 Layer A 链路真实性都失真

Step 8 把这些散落在裸 git commit 里的隐性依赖收束为一个原子操作。

---

## 2. 触发场景（满足任一即必须走）

| 场景 | 典型来源 | 示例 reason |
| --- | --- | --- |
| 读者视角 checker 反馈修正 | naturalness / reader-critic / reader-pull | "naturalness 88 → 92 修语病" |
| 外部模型 reader_flow 反馈修读者卡点 | external-review-agent | "Gemini reader_flow medium 修复" |
| 修复 hygiene_check P1 警告 | post-commit lint | "ASCII 引号清理 + 字数同步" |
| 修复 audit-agent editor_notes 提出的本章遗留 | Step 6 audit | "audit Layer C 提示氛围打卡，加 1 段感官" |
| 任何手动微调正文 | 作者直接编辑 | "调整开场节奏" |

**反例**（不属于 Step 8 触发）：
- 仅修改 `.webnovel/state.json`（用 `--allow-no-change` 走 Step 8 仍可，但属边缘场景）
- 仅修改设定集 / outline / 配置文件（属 Step K / 设定迭代，不在 Step 8 范围）
- 完全重写章节（应走 Step 1-7 重跑，而不是 polish）

---

## 3. 唯一入口

```bash
python -X utf8 "${SCRIPTS_DIR}/polish_cycle.py" ${chapter_num} \
  --project-root "${PROJECT_ROOT}" \
  --reason "<人类可读的 polish 原因>" \
  --narrative-version-bump \
  --round-tag round13v2 \
  [--checker-scores '{"reader-naturalness-checker": 91, "reader-critic-checker": 88}']
```

参数说明：

| 参数 | 必需 | 用途 |
| --- | --- | --- |
| `chapter` (位置参数) | ✓ | 章节号整数 |
| `--reason` | ✓ | 一句话说明本次 polish 原因，落入 commit message + workflow log |
| `--project-root` | 推荐 | 项目根目录绝对路径 |
| `--round-tag` | 推荐 | round 标签（如 `round13v2`），追加到 commit message 末尾 |
| `--narrative-version-bump` | 二选一 | 自动 vN → vN+1 |
| `--narrative-version v3` | 二选一 | 手动指定版本号 |
| `--checker-scores` | 可选 | JSON：补录新跑的 checker 分数（已规范化键名） |
| `--no-commit` | 可选 | 只跑检查 + 同步 state，不 commit（CI / dry-run） |
| `--allow-no-change` | 可选 | 允许章节文件未变化也继续（纯 state 修复场景） |

---

## 4. 执行流程（脚本内部 6 步）

```
[1/6] 变化检测     git show HEAD:正文/第NNNN章*.md vs 工作区
                  无变化默认拒绝（exit 2），除非 --allow-no-change
[2/6] post_draft_check  ASCII引号/Markdown/U+FFFD/字数/虚词/术语 7 类
                        必须 exit 0；fail 即 exit 1
[3/6] state.json 同步   word_count / narrative_version / updated_at
                        polish_log[] 追加 / checker_scores 合并
[4/6] hygiene_check     17+ 类项目卫生
                        P0 fail = exit 1；P1 warn 允许继续
[5/6] git commit        消息：第N章 vX: {reason} [polish:{round_tag}]
                        自动 git add . + commit
[6/6] workflow_state    history[] 追加 polish_NNN task
                        完整登记 Step 8 artifact
```

**退出码语义**：
- `0` 全通过 + commit 完成
- `1` 检查 fail（post_draft 或 hygiene P0），必须修到通过
- `2` 结构错（无变化、文件缺失、state 损坏、参数冲突）
- `3` git 操作失败

---

## 5. 数据写入契约

### 5.1 `chapter_meta.{NNNN}` 增量字段

```json
{
  "word_count": 3084,                      // 实测中文字符数
  "narrative_version": "v3",               // 自动自增或手动指定
  "updated_at": "2026-04-20T12:34:56+00:00",
  "checker_scores": {                      // --checker-scores 合并
    "reader-naturalness-checker": 91,
    "reader-critic-checker": 88
  },
  "polish_log": [                          // 追加，不覆盖
    {
      "version": "v3",
      "timestamp": "2026-04-20T12:34:56+00:00",
      "notes": "读者视角 6 medium 修复"
    }
  ]
}
```

### 5.2 `workflow_state.json.history[]` 新增条目

```json
{
  "task_id": "polish_001",
  "command": "webnovel-polish",
  "chapter": 1,
  "status": "completed",
  "started_at": "2026-04-20T12:34:56Z",
  "completed_at": "2026-04-20T12:34:58Z",
  "args": { "chapter_num": 1, "reason": "...", "narrative_version": "v3" },
  "artifacts": {
    "polish_cycle": true,
    "narrative_version": "v3",
    "reason": "读者视角 6 medium 修复",
    "diff_lines": 47,
    "state_diff": { "word_count": {"old": 3498, "new": 3084}, "narrative_version": {"old": "v2", "new": "v3"} },
    "round_tag": "round13v2",
    "commit_sha": "abc123...",
    "branch": "master"
  },
  "completed_steps": [
    { "id": "Step 8", "name": "Polish Cycle", "status": "completed", "artifacts": { ... } }
  ]
}
```

### 5.3 Git commit message 格式

```
第N章 vX: {reason} [polish:{round_tag}]
```

例：
- `第1章 v3: ASCII 引号清理 + 字数同步 [polish:round13v2]`
- `第7章 v4: reader-critic 严重→良好 [polish:round14]`

---

## 6. 多轮 polish 规范

每一轮独立调用 `polish_cycle.py`，**不要把多轮 polish 压成一次 commit**：

```
Step 7 commit:  第1章: 觉醒                    (v2, 生于 Step 1-7)
Step 8 第1轮:   第1章 v3: 修读者视角 6 medium  (commit 1)
Step 8 第2轮:   第1章 v4: 微调开场节奏          (commit 2)
Step 8 第3轮:   第1章 v5: 修 audit Layer C     (commit 3)
```

理由：
- 每个 commit 单独可回退
- `polish_log[]` 留下完整修订史，下章 context-agent 可读
- workflow_state 每轮独立 task_id，跨章 trend 可拉到精确数据

---

## 7. 跨章影响

### 7.1 下章 context-agent 行为

context-agent 读 `state.json.chapter_meta.{NNNN}` 时：
- 优先读 `narrative_version` 最新值
- 读 `polish_log[]` 最后一条的 `notes`，作为"本章近期修订摘要"注入下章 Contract
- 读 `checker_scores` 最新合并值，做"前章弱项"提示

### 7.2 跨章 trend / Step 6 Layer G

`audit-agent` Layer G（跨章趋势）扫描时：
- 同时读 Step 1-7 task 与 Step 8 polish task
- polish task 的 `state_diff.checker_scores` 用于绘制"经 polish 修订后的真实 checker 趋势"
- 若某章的 polish 轮次 > 3 且 reason 都指向同一类问题（如反复 reader-critic medium），Layer G 应给出"该 checker 长期不稳定"告警

---

## 8. 审计兼容性

### 8.1 历史章节兼容

Round 13 v2 之前提交的章节，`chapter_meta` 没有 `narrative_version` / `polish_log` / 13 维 checker_scores。这种章节走 Step 8 时：
- `narrative_version`：默认从 `v1` 起算，bump 为 `v2`
- `polish_log`：首次 polish 创建数组
- `checker_scores`：合并而非覆盖（保留旧 10 维分数 + 新维度）

### 8.2 外部审查 JSON 历史问题

Round 13 v2 升 13 维度后，旧的外部审查 JSON 只有 4-11 个 dimension。Step 6 audit 的 A3 检查会报 `incomplete_dimensions critical`。**Step 8 不重跑 Step 3.5 外部审查**（成本太高），如需修这个问题必须显式：

```bash
python -X utf8 "${SCRIPTS_DIR}/external_review.py" ${chapter_num} --models all --force
```

然后再走 Step 8 收尾。

---

## 9. 恢复策略

### 9.1 polish_cycle.py 中途失败

| 失败点 | 已发生的副作用 | 恢复 |
| --- | --- | --- |
| `[2/6] post_draft_check` fail | 无 state/git 变更 | 修正文，重跑 polish_cycle |
| `[3/6] state 同步` 异常 | 可能 state.json 部分写入 | `git checkout -- .webnovel/state.json` 恢复，再跑 |
| `[4/6] hygiene_check` P0 fail | state 已更新 | 修正文，重跑 polish_cycle（state 同步幂等） |
| `[5/6] git commit` fail | state 已更新但未 commit | 修 git 错误，重跑（commit 会包含已更新的 state） |
| `[6/6] workflow 登记` fail | commit 已完成但 workflow 漏登 | 不应发生；如发生，重跑会创建新 polish_NNN |

### 9.2 历史漏登 polish 补录

如果发现某章历史上有裸跑 polish commit 未登记，**不要**手动改 `workflow_state.json`。改用：

```bash
python -X utf8 "${SCRIPTS_DIR}/polish_cycle.py" ${chapter_num} \
  --reason "补登 vN → vN+1 (历史 commit <sha>)" \
  --narrative-version vN+1 \
  --allow-no-change \
  --no-commit
```

`--no-commit` + `--allow-no-change` 用于纯登记，state 同步会反映当前实测 word_count。

---

## 10. 与现有规则的边界

| 现有规则 | Step 8 关系 |
| --- | --- |
| Step 1-7 主流程 | **不替代**；Step 8 只在 Step 7 之后 |
| `post_draft_check.py` | Step 8 复用同一脚本，不修改其逻辑 |
| `hygiene_check.py` | Step 8 复用同一脚本；新增 H19 检查"polish-only commit 但 polish_log 未更新"（见下） |
| `pre_commit_step_k.py` | Step 8 **不**强制跑 Step K 闸门（polish 不修设定集），但若 polish 同时改了设定 Markdown 应手动跑一次 |
| Step 6 audit-agent | Layer A 已被扩展承认 polish task；Layer G 趋势分析需读 polish_log |
| `workflow complete-task` | Step 8 不调用，因为不是新的写作任务，只在 history[] 追加 polish task |

---

## 11. hygiene_check 新增检测项（H19）

`hygiene_check.py` Round 14.5 新增：

```
H19 (P1):  正文文件 hash 与 HEAD 不一致，但 chapter_meta.polish_log 末尾时间戳早于 git log 最新 commit
           → 说明可能存在裸跑 polish commit（绕过 polish_cycle）
H19a (P0): 正文文件 hash 与 HEAD 不一致，且 chapter_meta.narrative_version 仍为 v1（从未走过 polish_cycle）
           → 必须立即跑 polish_cycle 补登
```

详见 `hygiene_check.py` 中 H19 实现。

---

## 12. FAQ

**Q: polish 之后可以 push 吗？**
A: 可以。`polish_cycle.py` 不自动 push（与 Step 7 一致）。push 前再跑一次 `pytest` 与 `webnovel.py preflight`。

**Q: 同章节同一秒内连跑两次 polish_cycle 会怎样？**
A: 第二次会因 git status 干净而 commit "no changes"（git 自身报错），exit 3。这是预期行为。

**Q: 如果只想修 `state.json` 不改正文？**
A: 用 `--allow-no-change --no-commit`。但更推荐反思：state 漂移本身是 bug，应该让 data-agent 修。

**Q: Step 8 失败是否阻塞下一章？**
A: 是。下一章充分性闸门 #1 应包含"上一章如有未提交修改，必须先走 Step 8"。preflight 也会检查 git status 干净度。

**Q: 多人协作怎么办？**
A: 当前规范假设单人 / 单 AI 串行。多人协作下，每人 polish 前 `git pull --rebase`，polish 后 `git push`，冲突按常规 git 流程处理。
