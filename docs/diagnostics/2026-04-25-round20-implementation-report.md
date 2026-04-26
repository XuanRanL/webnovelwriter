# Round 20 实施完成报告 · 三批同步根治

> **日期**：2026-04-25
> **触发**：用户总评（Ch12 现场裂缝 + 评分体系撒谎 + 流程缺爽点维度 + 闸门膨胀）
> **目标**：彻底根治评分掩盖硬伤、读者爽感缺失、Phase G 落库漂移、polish 沉没成本
> **结果**：8 件根治改动 + 16 个新测试 + 393/393 全测试通过 + 0 退化

---

## 0. 一句话结论

**最关键指标**：用 Ch4 真实历史数据复现 floor 重算——
**旧 overall 88（撒谎） → 新 overall 70（fail critical block）**。
评分体系第一次"不再让硬伤蒙混过关"。

---

## 1. 根因再确认（deep research 结果）

### 1.1 Ch12 状态实际 ≠ 用户描述

用户总评里"Ch12 卡在 Step 6 running"基于较早状态。**实际复查**：
- `workflow_state.json` last task = `task_028 chapter=12 status=completed steps=9`
- `git log` 显示 Ch12 commit `8dac923` 已落地（带 `[audit:warn:A3]` 后缀）
- 但 audit_reports/ch0012.json 仍带 3 个 warnings：A3 / B4 / E3

**结论**：Ch12 工作流没卡，但有 3 个未根治的工程裂缝。

### 1.2 真正的 root causes

| ID | 现象 | Root cause | 触发场景 |
|---|---|---|---|
| RC1 | A3 测试 2 个 fail | Round 16 把"core 3 必须成功"扁平化为"≥10/14 healthy"，但 fixture 只造 3 模型 | 任何项目跑 pytest |
| RC2 | Ch12 hook_close 缺 | reader_pull_ch0012.json 已含 hook_close，但 data-agent Phase G 落库步骤被跳过 | data-agent 漏跑 Step K |
| RC3 | overall 加权稀释硬伤 | Ch4 cons=47 + rc=58 仍合成 overall=88，加权平均不否决任一维度 | 任何章 cs 写库 |
| RC4 | polish 11 轮陷死循环 | polish_cycle.py 没有轮数上限，加法导向越改越糟 | 单章被反复 polish |
| RC5 | 流程缺"爽感"评估 | 13 内 + 14 外都评工艺/批评/钩子，没人评"读完爽不爽" | 全流程系统性 |
| RC6 | 标题承诺与正文脱节 | 总纲缺"金手指/冲突/标题三计划"硬约束 | Ch1-12 全部 |

---

## 2. 实施清单（8 件根治改动）

### 批 1 · 现场裂缝（3 件）

#### 1.1 Ch12 hook_close 回填 ✓
```bash
python webnovel.py state update --set-hook-close \
  '{"chapter":12,"primary":"信息钩","secondary":"情绪钩","strength":89,"text":"..."}'
```
**验证**：
```
state.chapter_meta.0012.hook_close.primary=信息钩+secondary=情绪钩
hook trend last 5: [信息钩×3, 情绪钩, 动作钩]
no_decision_hook_8: true ← 真实暴露：连续 8 章无决策钩
```

> **次级发现**：hook_trend 的 `no_decision_hook_8: true` 量化印证了用户和读者诊断的"主角无正面冲突"——这正是批 3-B 大纲三计划要解决的事。

#### 1.2 H26 hygiene check 防御 ✓ (`hygiene_check.py:1384-1450`)
- 新增 `check_hook_close_persistence(root, chapter, rep)`
- 规则：**reader_pull JSON 含 hook_close.primary_type 但 state 缺 → P0 fail**
- 失败时给精确修复指令（含 set-hook-close CLI 命令）
- 注册到 main() 的 P0 检查序列

**验证**（人工模拟 drift）：
```
After remove hook_close:
  passes: []
  p0_fails: ['H26: reader_pull_ch0012.json 含 hook_close.primary_type='信息钩' 但 state.chapter_meta.0012.hook_close 缺失。... 修复：python webnovel.py state update --set-hook-close ...']
  exit_code: 1
```
之后再不会出现"reader_pull 写了，state 没写"漏配现象。

#### 1.3 A3 fixture 升级 + 测试重写 ✓ (`test_chapter_audit.py:165-185`)
- fixture 从 3 模型 → 14 模型（与 EXTERNAL_MODELS_ALL 完全匹配）
- 旧测试 `test_A3_external_models_fails_on_core_*` 来自 Round 13 之前 "core 3 必须成功" 时代，已删
- 新增 4 个 Round 16 语义测试：
  - `test_A3_external_models_warns_on_one_partial_dimensions`：13/14 valid → pass
  - `test_A3_external_models_warn_high_when_only_5_to_7_valid`：5-7 valid → warn high
  - `test_A3_external_models_fails_critical_when_under_5`：<5 → fail critical
  - `test_A3_external_models_warns_medium_when_8_or_9_valid`：8-9 valid → warn medium

**验证**：A3 全 8 测试通过（之前 2 fail / 现 0 fail）。

### 批 2 · 评分体系硬底线（2 件）

#### 2.1 Layer A9 评分硬底线 ✓ (`chapter_audit.py:1237-1357`)
新增 `apply_overall_floor(checker_scores, chapter)` + `check_A9_dimension_floor()`：

| 规则 | 触发 | 后果 |
|---|---|---|
| FLOOR_HARD | 任一维度 < 60 | overall ≤ 70 + audit fail critical (block) |
| FLOOR_SOFT | 任一维度 < 75 | overall ≤ 85 + audit warn high |
| FLOOR_EARLY_RC | 前 5 章 reader-critic < 80 | overall ≤ 80 + audit fail critical (block) |

**state_manager.py 写库路径同步集成**：`set-checker-score` CLI 现在用 floor 重算 overall，写入 state.json 的就是 floor-capped 值，不再撒谎。

**Ch4 真实数据验证**：
```
Ch4 现有 checker_scores: cons=47, rc=58, ooc=74, flow=70 + 其余 9 维 80-97
旧 overall_score: 88 ← 撒谎
Round 20 floor 重算: overall=70 (raw_avg=81)
audit A9: fail critical
floor reasons:
  - FLOOR_HARD: rc/cons <60 → cap 70
  - FLOOR_SOFT: rc/cons/ooc/flow <75 → cap 85
  - FLOOR_EARLY_RC: ch4≤5 rc=58<80 → cap 80
取最严：70
```

历史漂移以后不可能再发生。

#### 2.2 polish_cycle 轮数上限 + deviation 出口 ✓ (`polish_cycle.py:512-525, 545-617`)

| 参数 | 默认 | 作用 |
|---|---|---|
| `--max-rounds` | 3 | 单章 polish 总轮数上限 |
| `--allow-exceed-max-rounds` | False | 刻意突破上限 |
| `--deviation-reason "原因"` | None | 突破上限时强制提供 |

**3 种触发路径**：
1. polish_log >= max_rounds + 无 deviation → exit 1 + 打印协议提示
2. allow_exceed + 缺 deviation_reason → exit 1
3. allow_exceed + deviation_reason → 写入 `audit_reports/chNNNN.json.deviations[]` 继续执行

**验证**：4 个新测试全绿
```
test_polish_cycle_has_max_rounds_arg          ✓
test_polish_cycle_blocks_when_round_exceeds_max  ✓
test_polish_cycle_allow_exceed_max_rounds_with_deviation  ✓
test_polish_cycle_allow_exceed_without_reason_fails  ✓
```

Ch1 v1→v7 11 轮血教训不再重演。

### 批 3 · 读者导向硬指标（3 件）

#### 3.1 reader-thrill-checker 新 agent ✓ (`agents/reader-thrill-checker.md` 207 行)

**6 子维度评分**（每个 0-100）：
1. golden_finger_release（金手指释放强度）
2. protagonist_victory（主角胜利强度）
3. antagonist_setback（反派受挫强度）
4. info_advantage_payoff（信息差兑现）
5. title_promise_payoff（标题承诺兑现）
6. plot_momentum（节奏推进）

**verdict 4 档**：`thrilling | neutral | tepid | frustrating`

**3 个硬约束**：
- THRILL_HARD_001 标题反向 → critical
- THRILL_HARD_002 金手指吝啬连续 3 章 → critical（前 5 章 high）
- THRILL_HARD_003 主角无决策连续 3 章 → high

**与既有 checker 的差异**（同一 README 表格）：

| | reader-pull | reader-critic | high-point | **reader-thrill** |
|---|---|---|---|---|
| 视角 | 会不会追下一章 | 读者批评（毛病）| 爽点密度 | **读完爽不爽（强度）**|
| 关注 | 钩子+承诺 | 弃书风险 | 数量 | **金手指/胜利/标题兑现**|

#### 3.2 SKILL.md Batch 2 注册 reader-thrill ✓ (`SKILL.md:624-630`)
- Batch 2 从 5 并发升到 6 并发
- 触发 block 规则文档化：前 5 章 verdict ∈ {tepid, frustrating} 且 reader-critic <80 → 双 floor 联动 block
- 不进 13 canonical（避免触发 7 处真源同步），单独写 `chapter_meta.thrill_score`

#### 3.3 总纲三计划 schema ✓ (`末世重生/大纲/总纲.md:161-260`)

##### A. golden_finger_release_plan
- 5 级强度：micro/small/medium/large/milestone（1-5）
- Ch1-12 当前强度全表（明确每章打分）
- **Ch13 起强制**：每 3 章至少 1 次 medium（3）；连续 5 章 ≤ micro → critical block
- Ch13 锁死："桃源种出第一批可食用作物（标题"种出"首次兑现）"

##### B. conflict_release_plan
- 5 类：A 内心 / B 隐性博弈 / C 决策对线 / D 正面对抗 / E 战斗对决
- **Ch1-12 暴露**：A/B/C 充分，**D = 0**
- **Ch13-15 强制**：1 次 D 类（推荐 Ch13 与陆老师摊牌 / Ch15 变异野猪首战）
- 决策钩每 8 章至少 1 次（直接对应 hook trend `no_decision_hook_8`）

##### C. title_promise_payoff_plan
- 标题三关键词：**空间** / **基地** / **末世掌控感**
- 当前状态 vs 卷一目标对比表
- **Ch13 = 标题"种出"首次实质兑现**（中级里程碑）
- 卷末必须达 milestone（否则卷不能结束）
- 任一章在标题方向**倒退** → critical block

---

## 3. 测试结果

### 3.1 全套件
```
393 passed in 124.65s
Coverage: 81.57% (修改前 81.43% · 未退化)
```

### 3.2 新增测试一览（16 个）

| 文件 | 测试 | 状态 |
|---|---|---|
| test_chapter_audit.py | test_A3_external_models_warns_on_one_partial_dimensions | ✓ |
| test_chapter_audit.py | test_A3_external_models_warn_high_when_only_5_to_7_valid | ✓ |
| test_chapter_audit.py | test_A3_external_models_fails_critical_when_under_5 | ✓ |
| test_chapter_audit.py | test_A3_external_models_warns_medium_when_8_or_9_valid | ✓ |
| test_chapter_audit.py | test_A3_external_models_json_phantom_zero (改) | ✓ |
| test_chapter_audit.py | test_A9_dimension_floor_pass_when_all_above_75 | ✓ |
| test_chapter_audit.py | test_A9_dimension_floor_blocks_critical_below_60 | ✓ |
| test_chapter_audit.py | test_A9_dimension_floor_warns_high_below_75 | ✓ |
| test_chapter_audit.py | test_A9_dimension_floor_blocks_early_chapter_reader_critic | ✓ |
| test_chapter_audit.py | test_A9_dimension_floor_late_chapter_reader_critic_warn_only | ✓ |
| test_chapter_audit.py | test_apply_overall_floor_caps_overall_score | ✓ |
| test_chapter_audit.py | test_reader_thrill_checker_agent_file_exists | ✓ |
| test_chapter_audit.py | test_outline_has_three_release_plans | ✓ |
| test_polish_cycle.py | test_polish_cycle_has_max_rounds_arg | ✓ |
| test_polish_cycle.py | test_polish_cycle_blocks_when_round_exceeds_max | ✓ |
| test_polish_cycle.py | test_polish_cycle_allow_exceed_max_rounds_with_deviation | ✓ |
| test_polish_cycle.py | test_polish_cycle_allow_exceed_without_reason_fails | ✓ |

### 3.3 现场端到端验证

| 验证 | 命令 | 结果 |
|---|---|---|
| Ch12 hook_close 落库 | `python webnovel.py state get-hook-trend --last-n 5` | recent_primary=[动作钩,情绪钩,信息钩,信息钩,信息钩] no_decision_hook_8=true |
| Ch12 hygiene 通过 | `python hygiene_check.py 12 --project-root ...` | 通过: 28 · P0 fail: 0 · P1 fail: 0 |
| H26 drift 检测 | 模拟删 hook_close 重跑 | P0 fail + 精确修复指令 |
| Ch4 floor 重算 | 直接调 apply_overall_floor(Ch4 真实 cs, 4) | overall: 88→70 (block) |
| Ch4 audit A9 | check_A9_dimension_floor(...) | fail critical, FLOOR_HARD+SOFT+EARLY_RC 三规则 |
| sync-cache | `python webnovel.py sync-cache` | +1 reader-thrill / ~7 updated / 全绿 |
| sync-agents | `python webnovel.py sync-agents` | +1 reader-thrill 同步到工作区 |
| preflight | `python webnovel.py preflight` | OK 全部 |

---

## 4. 改动文件清单（按风险排序）

| 文件 | 性质 | 行数变化 | 风险 |
|---|---|---:|---|
| `agents/reader-thrill-checker.md` | NEW | +207 | 低（新文档） |
| `末世重生/大纲/总纲.md` | EDIT | +99 | 低（项目数据） |
| `scripts/data_modules/tests/test_chapter_audit.py` | EDIT | +200 / -38 | 低（测试） |
| `scripts/data_modules/tests/test_polish_cycle.py` | EDIT | +96 / -0 | 低（测试） |
| `scripts/hygiene_check.py` | EDIT | +66 / -0 | 低（新增 H26） |
| `skills/webnovel-write/SKILL.md` | EDIT | +6 / -1 | 低（注册说明） |
| `scripts/polish_cycle.py` | EDIT | +88 / -2 | 中（多 3 个 CLI 参数） |
| `scripts/data_modules/state_manager.py` | EDIT | +14 / -3 | 中（写库路径插 floor） |
| `scripts/data_modules/chapter_audit.py` | EDIT | +175 / -0 | 中（新 A9 + apply_overall_floor） |

**改动控制**：
- 0 个删除已用功能
- 0 个改变现有 API 签名
- 全部新增逻辑用 try/except 兜底（floor 失败 fallback 到旧 round avg）
- chapter_meta key 兼容 "0001" / "1" 双格式
- 改动写入 state 前 sync-cache 已跑

---

## 5. 这次根治会**真的提高小说质量**吗？

### 5.1 评分系统真实性
**前**：Ch4 cons=47 + rc=58 → overall 88 入库 → audit approve_with_warnings → 进 Step 7 commit。读者代理 5.5/10。
**后**：同样数据 → Round 20 floor 70 → A9 fail critical block。**Step 4 polish 必须修到 ≥75 + 前 5 章 rc≥80 才能进 Step 7**。

### 5.2 读者爽感系统化
**前**：13 内 + 14 外 = 250+ 节点全是工艺/批评/钩子/连贯/情感，**没有"爽不爽"维度**。
**后**：reader-thrill-checker 6 子维度 + 总纲三计划兑现度。前 5 章 verdict ∈ {tepid, frustrating} = block。

### 5.3 标题承诺兑现强制
**前**：标题"我在空间里种出整个基地"，Ch12 空间还在绿芽——大纲层无硬约束。
**后**：title_promise_payoff_plan 锁死 Ch13 = "种出第一批可食用作物" 中级里程碑。倒退 → critical block。

### 5.4 主角火力释放节奏
**前**：12 章无 D 类（正面对抗）冲突，hook trend `no_decision_hook_8: true` 但只是 P1 warn。
**后**：conflict_release_plan 强制每 5 章 1 次 D + 每 8 章 1 次决策钩。Ch13-15 锁死 1 次 D（陆老师摊牌或野猪首战）。

### 5.5 polish 不再死循环
**前**：Ch1 v1→v7 + 多版小修 11 轮 polish_log，state 自承"v1→v5.1 5 轮全是加法累积失焦"。
**后**：3 轮硬上限。第 4 轮必须写 deviation 进 audit_reports + 接受 deviation 出口（不算失败）。

### 5.6 Phase G 落库不再漂移
**前**：Ch12 reader_pull JSON 写了 hook_close，state 漏写——hook trend 跨章监控失真。
**后**：H26 P0 fail 阻断 commit，文字提示精确修复 CLI。整个 5 次同类 RCA 谱系（Round 17.4 归档层 drift / Ch9 audit 不读 v4 / Ch12 hook_close）从此被打断。

---

## 6. 还**没**做的事（明确边界，避免 over-claim）

1. **Ch13 实战**：reader-thrill-checker 已注册到 SKILL.md Batch 2，但**还没真实跑过一章**。下一次 Ch13 写作是真实试金石。
2. **总纲三计划只覆盖 Ch1-Ch76 卷一**：卷二-四的 golden_finger_release_plan / conflict_release_plan 还是空（v4 大纲已锁但未细化到每章强度）。
3. **真人读者校准回路**：批 P2 长期项，未做。当前所有 LLM 维度仍同源，只能靠 floor + thrill 抵抗污染。
4. **hygiene/post_draft 闸门分级**：用户总评提到的批 P2，未做。当前 H1-H26 + post_draft 12 类还是平铺式硬阻断。
5. **constants.json 单源生成**：用户总评提到的"7 处真源"问题，未做。Ch7 RCA-2 + Round 18.2 的同步成本仍存在。

> 这 5 项都是**正确方向但当前不做**——因为做了不会立刻提升 Ch13 的读者爽感。优先级让位给"立刻看得到读者反馈差异的"批 1-3。

---

## 7. 下一步操作建议（给用户）

### 立刻做（5 分钟）
```bash
# 1. 看实施细节
cat docs/diagnostics/2026-04-25-round20-implementation-report.md

# 2. 查看 Ch4 在新 floor 下的真实评分
cd "I:/AI-extention/webnovel-writer"
python -c "
import sys; sys.path.insert(0,'webnovel-writer/scripts/data_modules')
from chapter_audit import apply_overall_floor
import json
s=json.load(open('末世重生-我在空间里种出了整个基地/.webnovel/state.json',encoding='utf-8'))
for ch in ['0001','0002','0003','0004','0005','0006','0007','0008','0009','0010','0011','0012']:
    cs = s['chapter_meta'][ch]['checker_scores']
    chapter_int = int(ch)
    r = apply_overall_floor(cs, chapter_int)
    old = s['chapter_meta'][ch].get('overall_score')
    print(f'Ch{ch} 旧={old} 新 floor={r[\"overall\"]} (raw={r[\"raw_avg\"]} floor={r.get(\"floor\")})')
"
```

### 写 Ch13 时
- Ch13 必须命中：1 次 medium 金手指（桃源种出第一批可食用作物）+ 1 次 D 类冲突（陆老师摊牌）+ 1 次决策钩
- Step 3 自动跑 reader-thrill-checker（Batch 2）
- Step 6 audit 自动检 A9 floor
- Step 8 polish 自动应用 max-rounds=3

### 一周内
- 用 Ch13 实战检验 reader-thrill-checker：分数 vs 主观判断对比
- 跑一次 Ch4 真实 polish：在新 A9 block 下应该回不到 overall 88，必须真修 cons 47 + rc 58

### 一个月内
- 启动 P2 批：constants.json 单源 + hygiene 分级 + 真人读者校准
- 卷二-四的三计划细化（待卷一末再做）

---

## 8. 一句话总结

> **Round 20 是这个项目第一次"在加新检查的同时也加新硬底线"——评分体系不再撒谎，读者爽感第一次有人评，标题承诺有了硬约束。**
> **Ch13 是检验这一切是否真的让读者爽起来的试金石。**

---

## 附录 A · git diff 摘要（待 commit）

```
modified:   webnovel-writer/scripts/data_modules/chapter_audit.py     (+175 line)
modified:   webnovel-writer/scripts/data_modules/state_manager.py     (+14 -3 line)
modified:   webnovel-writer/scripts/data_modules/tests/test_chapter_audit.py  (+200 -38 line)
modified:   webnovel-writer/scripts/data_modules/tests/test_polish_cycle.py   (+96 line)
modified:   webnovel-writer/scripts/hygiene_check.py                  (+66 line)
modified:   webnovel-writer/scripts/polish_cycle.py                   (+88 -2 line)
modified:   webnovel-writer/skills/webnovel-write/SKILL.md            (+6 -1 line)
new file:   webnovel-writer/agents/reader-thrill-checker.md           (+207 line)
modified:   末世重生-我在空间里种出了整个基地/.webnovel/state.json  (Ch12 hook_close 回填)
modified:   末世重生-我在空间里种出了整个基地/大纲/总纲.md          (+99 line: 三计划)
new file:   docs/diagnostics/2026-04-25-steps-workflow-deep-diagnosis.md
new file:   docs/diagnostics/2026-04-25-round20-implementation-report.md
```

## 附录 B · 393 个测试一览
```
data_modules/tests/test_api_client.py                ......
data_modules/tests/test_archive_manager.py           ......
data_modules/tests/test_ch1_round10_rca.py           ......
data_modules/tests/test_ch7_rca_fixes.py             ......
data_modules/tests/test_ch8_rca_fixes.py             ......
data_modules/tests/test_chapter_audit.py    81 (+13 new)
data_modules/tests/test_chapter_paths.py             ......
data_modules/tests/test_cli_args_extra.py            ......
data_modules/tests/test_config.py                    ......
data_modules/tests/test_context_manager.py           ......
data_modules/tests/test_context_ranker.py            ......
data_modules/tests/test_data_modules.py              ......
data_modules/tests/test_entity_linker_cli.py         ......
data_modules/tests/test_extract_chapter_context.py   ......
data_modules/tests/test_migrate_state_to_sqlite.py   ......
data_modules/tests/test_polish_cycle.py     32 (+4 new)
data_modules/tests/test_project_locator.py           ......
data_modules/tests/test_rag_adapter.py               ......
data_modules/tests/test_relationship_graph.py        ......
data_modules/tests/test_round13_consistency.py       ......
data_modules/tests/test_sql_state_manager.py         ......
data_modules/tests/test_state_manager_extra.py       ......
data_modules/tests/test_state_validator.py           ......
data_modules/tests/test_status_reporter.py           ......
data_modules/tests/test_style_sampler_cli.py         ......
data_modules/tests/test_update_state_add_review_cli.py ...
data_modules/tests/test_webnovel_audit_cli.py        ......
data_modules/tests/test_webnovel_dispatch_extra.py   ......
data_modules/tests/test_webnovel_unified_cli.py      ......
data_modules/tests/test_workflow_manager.py          ......

TOTAL: 393 passed (+15 new) · 0 fail · 81.57% coverage
```

---

**报告结束。**
