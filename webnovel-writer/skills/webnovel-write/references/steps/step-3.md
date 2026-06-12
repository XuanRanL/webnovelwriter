# webnovel-write · Step 3 内部审查（含 checker_scores 双通道落库）

> Round 29 Phase 2 由 SKILL.md 原文拆分（lazy-load）。进入对应 Step 时必须先加载本文件全文，
> 按其中规则执行；跨步骤硬约束 / 章节间闸门 / 充分性闸门见 SKILL.md 骨架。

### Step 3：审查（全量审查，必须由 Task 子代理执行）

执行前加载：
```bash
cat "${SKILL_ROOT}/references/step-3-review-gate.md"
```

> **🔴 Round 28.22 checker JSON quote 字段 ASCII 引号嵌套硬禁（H71 三复发根治）**
>
> 所有 14 个 checker subagent 在写 JSON 时，**`quote` / `reason` / `suggestion` / `description` / `improvement_notes` 等字符串字段内禁止嵌套 ASCII `"` 和中文 `""`**，否则 JSON parse fail → hygiene H71 P0 阻断 commit。
>
> 正文若含中文弯引号 `""""`，写入 JSON 时**必须**替换为括号 `()` / `〈〉` / `...`（省略）。
>
> Ch33/Ch37 三复发
> - 反例：`"quote": "一种属于"我的兄弟在替我挡着"的什么"` → JSON parse error
> - 正例：`"quote": "一种属于(我的兄弟在替我挡着)的什么"` / `"quote": "一种属于...的什么"`
>
> 全部 14 checker subagent 落盘前必须做字符串字段值 `"` 字符自检。主流程在 Step 3 complete-step 前必须 `python -c "import json; json.load(open(f))"` 逐文件验证。

调用约束：
- 必须用 `Task` 调用审查 subagent，禁止主流程伪造审查结论。
- **标准/--fast 模式必须分批启动**（0+6+5 三段，详见 `step-3-review-gate.md`），禁止 13 个 checker 同时并发（Claude Code Agent 并发池上限约 4-6 个）。
- 必须等待全部 checker 返回后才能统一聚合 `issues/severity/overall_score`。
- **禁止在任何 checker 仍在运行时进入 Step 4**。即使外部审查已完成，内部 checker 未全部返回也不得开始润色。
- **Round 13 v2 · 取消 veto block**：两个读者视角 checker（naturalness + reader-critic）和其他 11 个 checker **平等参与评分**。它们的 `problems` 和其他 checker 的 `issues` 同等进入 Step 4 修复。不再单方面 block 流程——因为 block 回 Step 2A 重写整章对大多数问题是浪费，Step 4 能修的就应该在 Step 4 修。

审查器（标准模式全部执行，0+6+5 三段）：
- **Batch 0（读者视角维度，2 个并行先跑，Round 13 v2）**：
  - `reader-naturalness-checker`（汉语母语自然度 · 独立于规则污染 · 专补 Ch1 v1 “<protagonist>在死”语病被 10+9 审查器集体放行的盲区）
  - `reader-critic-checker`（读者锐评 · 极简 prompt · 无规则约束 · 模拟追更读者本能反应 · Round 13 新增，专补“规则 pass 但读者会弃”的盲区）
  - 两个 checker 都返回 `overall_score` 和 `problems`，统一计入 `internal_avg`
  - Batch 0 先跑的原因：规模小（2 个）+ 读者视角反馈对 Batch 1/2 无依赖，早跑早反馈
- Batch 1（核心优先，6 个并发）：
  - `consistency-checker`（设定一致性）
  - `continuity-checker`（连贯性）
  - `ooc-checker`（人物OOC）
  - `reader-pull-checker`（追读力）
  - `high-point-checker`（爽点密度）
  - `flow-checker`（读者视角流畅度 · 失忆裸读协议）
- Batch 2（Batch 1 全部返回后启动，6 个并发 · Round 20 新增 reader-thrill-checker）：
  - `pacing-checker`（节奏平衡）
  - `dialogue-checker`（对话质量）
  - `density-checker`（信息密度）
  - `prose-quality-checker`（文笔质感）
  - `emotion-checker`（情感表现）
  - `reader-thrill-checker`（**P0 新增**）爽感强度 6 子维度（金手指释放/主角胜利/反派受挫/信息差兑现/标题承诺兑现/节奏推进）· 与 reader-pull-checker（追读力）+ reader-critic-checker（读者批评）+ high-point-checker（爽点密度）互补：thrill 评"读完爽不爽"，pull 评"会不会追下一章"
  - **reader-thrill-checker 触发 block 规则**：前 5 章 verdict ∈ {tepid, frustrating} 且 reader-critic-checker < 80 → 双 floor 联动 block；连续 3 章 golden_finger_release ≤ 50（前 5 章为 high）→ critical block

模式说明：
- 标准/`--fast`：全量 13 个审查器（2 + 6 + 5），分段执行。
- `--minimal`：固定核心 5 个（naturalness + reader-critic + consistency + continuity + ooc），单批并发。**两个读者视角 checker 即使在 minimal 也必跑**。

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
  "dimension_scores": {"consistency-checker": 80, "continuity-checker": 90, "ooc-checker": 82, "reader-pull-checker": 87, "high-point-checker": 85, "pacing-checker": 78, "dialogue-checker": 83, "density-checker": 88, "prose-quality-checker": 82, "emotion-checker": 80, "flow-checker": 84, "reader-naturalness-checker": 86, "reader-critic-checker": 81},
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
- `overall_score` 必须按 `step-3-review-gate.md` 的“内外部分数合并规则”计算：`round(internal * 0.6 + external_avg * 0.4)`。若 Step 3.5 全部失败或被模式跳过（`--minimal`），则退化为纯内部分数。
- **追读线状态必须显式输出（Round 29 Phase 8）**：Step 3 聚合时除 overall 外，单独报告一行追读线：
  `追读线: reader-critic={分} (目标 ≥85) · thrill={verdict}/gf_release={分} · reader-pull={分}`。
  追读线未达标（rc < 85 或 thrill ∈ {tepid, frustrating}）**不 block**，但 Step 4 的修复排序必须
  以追读维度 problems 优先（见 steps/step-4.md 追读线规则）。理由：overall 的 1/13 平均会把
  读者去留信号淹没（52 章实测 overall 86-89 vs thrill thrilling 仅 9/39）。

### Round 28.24 · checker_scores 双通道落库硬规则（防 H18 P0 重发）

**血教训**（Ch39 Step 7 hygiene H18 P0 阻断 commit）：Step 3 仅把 13 个 checker 分数写到 `review_metrics.dimension_scores`（索引层），未逐个写到 `chapter_meta.checker_scores`（状态层）。Step 4.5 复测后 data-agent PROTECTED_FIELDS 只保留已存在的 4 个 canonical key，导致 hygiene H18 检测 `chapter_meta.checker_scores` 缺 10 个 canonical key → P0 阻断 commit，必须手动 set-checker-score × 10 + reset overall_score 才解除。

**永久规则**：Step 3 落库时必须**同时**做两件事：

1. **索引层**（已有 · 必做）：`index save-review-metrics --data "@review_metrics.json"`
2. **状态层**（新增 · 必做）：对 13 个 canonical checker 逐个 `state update --set-checker-score`，触发 chapter_meta.checker_scores 落库 + auto-sync overall

**批量落库脚本模板**（Step 3 13 个 checker 全部返回后 + review_metrics 落库后立即执行）：

```bash
# 读 review_metrics.json 把 13 个 dimension_scores 逐个 set-checker-score
python -X utf8 -c "
import json, subprocess, sys
data = json.load(open('${PROJECT_ROOT}/.webnovel/tmp/review_metrics.json', encoding='utf-8'))
chap = data['start_chapter']
for ckr, score in data['dimension_scores'].items():
    payload = json.dumps({'chapter': chap, 'checker': ckr, 'score': score}, ensure_ascii=False)
    r = subprocess.run(['python', '-X', 'utf8', '${SCRIPTS_DIR}/webnovel.py',
                        '--project-root', '${PROJECT_ROOT}',
                        'state', 'update', '--set-checker-score', payload],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f'FAIL {ckr}: {r.stderr}', file=sys.stderr); sys.exit(1)
    print(f'OK {ckr}={score}')
# 最后修 overall_score 到 combined（避免被纯内部均分覆盖）
overall = data['overall_score']
payload = json.dumps({'chapter': chap, 'field': 'overall_score', 'value': overall}, ensure_ascii=False)
subprocess.run(['python', '-X', 'utf8', '${SCRIPTS_DIR}/webnovel.py',
                '--project-root', '${PROJECT_ROOT}',
                'state', 'update', '--set-chapter-meta-field', payload], check=True)
"
```

**Step 4.5 复测后**：用 `--set-checker-score` 覆盖单维度新分 + `--append-recheck` 留 before/after，然后再用 `--set-chapter-meta-field overall_score` 修回 combined 值。

**Step 4.5 触发的复测档（CLI 自动重算 overall）必然把 overall_score 拉到纯内部均分**，所以每次复测组合调用结束后**必须**最后一步重新设置 overall_score = combined。

**hygiene H18 检测点**：
- chapter_meta.checker_scores 必须含 **13 canonical key + overall**（共 14 项）
- 缺任一 → P0 阻断 commit
- 修法：用上面的批量脚本一次性补齐

**违反此规则 → Step 7 commit 必然 P0 失败**（Ch24 H18 升级 + Ch39 实战验证）。
- **A9 评分硬底线（apply_overall_floor）**：`set-checker-score` 写库时自动应用 floor 重算 overall：
  - 任一维度 < 60 → overall ≤ **70**（FLOOR_HARD）+ Step 6 audit Layer A9 fail critical block
  - 任一维度 < 75 → overall ≤ **85**（FLOOR_SOFT）+ A9 warn high
  - 前 5 章 reader-critic < 80 → overall ≤ **80**（FLOOR_EARLY_RC，首章追读契约保护）+ A9 fail critical block
  - **不得手动 Edit state.json 绕过 floor**（hygiene H9 score_alignment 会检测 overall vs checker_scores.overall 不一致）
  - Round 20 上线 · Ch4 Round 20.2 重写实战验证（cons 47 / rc 58 双触发 → cap 70 → 重写后全维 ≥75 解除 floor）
- **reader-thrill-checker 6 子维度评分**（`agents/reader-thrill-checker.md`）：
  - 6 子维度：`golden_finger_release` / `protagonist_victory` / `antagonist_setback` / `info_advantage_payoff` / `title_promise_payoff` / `plot_momentum`
  - 4 verdict 档：`thrilling`(≥80) / `neutral`(65-79) / `tepid`(50-64) / `frustrating`(<50)
  - **不计入 13 canonical**（避免触发 7 处真源同步），单独写 `chapter_meta.thrill_score`
  - 落库通道：`set-chapter-meta-field --field thrill_score --value '{...嵌套 dict...}'`
  - block 规则：前 5 章 verdict ∈ {tepid, frustrating} 且 reader-critic-checker < 80 → 双 floor 联动 block；连续 3 章 golden_finger_release ≤ 50（前 5 章为 high）→ critical block
  - THRILL_HARD_001：标题反向（如标题种田，本章只搞文学独白）→ critical block
- **Round 13 v2 · naturalness 和 reader-critic 作为常规评分维度**：两个读者视角 checker 的 `overall_score` 和 `problems` 与其他 11 个 checker **平等进入 `overall_score` 聚合**，不 block 流程。它们的 high/critical problems 与其他 checker 的 issues **合并**给 Step 4 做定向修复。**极端 block 条件**：仅当 Step 4 polish 后重新审查，`naturalness` 或 `reader-critic` 仍返回 `REJECT_CRITICAL` / `will_continue_reading=no`，才回到 Step 2A 重写。背景：Ch1 v1 case 中 19 审查器 + 7 层审计给 91 分 approve_with_warnings，但用户一眼看出“<protagonist>在死”语病——说明规则同源污染会让评分系统集体失灵。解决方案不是 block，而是**把读者视角纳入评分，强制 Step 4 必须修**。

## 本步专属硬约束（Round 29 自 SKILL.md 流程硬约束迁入）

- **审查报告模板规范 (Round 28.27 加入 · 防 B4 regex 冲突)**：
  - `overall_score: X` 字段**必须唯一出现在 frontmatter 顶头**（首条 `> overall_score: X`）
  - 其他位置的 score（如 reader-thrill）**必须**用别名（`综合分` / `thrill_score` / `sub_score`）而非 `overall_score`，否则 B4 regex 抓到第二条命中导致 audit B4 high fail（：thrill section `- overall_score: 55` 触发，应改为 `- 综合分: 55`）
  - 各 checker 行**禁止共用同一 token ≥3 次**（如多个 `(未复测)`），否则 audit A2 检测为 checker 坍缩 critical fail（：5+ checker 共用"未复测"误判）
  - 外部模型矩阵中每个 score**必须用 disk JSON `overall_score` 字段真值**，而非 stdout 早期值或自己估的值（：minimax-m2.7-hs 写 73.2 实际 disk 88.5，差 15.3）
- **禁止 A2 false positive 误判 (Round 28.30 audit 启发式扩展)**：5+ 未复测 checker 行共享"未复测/PASS/unchanged"等状态文案 → audit A2 启发式判 ≥3 token 重复 → critical fallback 警报。**根治**：chapter_audit._normalize_checker_snippet 已扩展 12 类状态词排除（未复测/未跑/不变/PASS_WITH_NOTE/REVISION_RECOMMENDED 等）。**写报告硬规则**：不复测 checker 行用"-"或留空，禁止用 "(未复测)" 标签。
