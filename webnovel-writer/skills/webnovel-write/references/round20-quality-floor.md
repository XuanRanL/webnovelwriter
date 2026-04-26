# Round 20.x 质量护栏完整规范

> **生效日期**：2026-04-25 起（Round 20 → Round 20.3 累计 4 批根治）
> **适用范围**：所有项目（不限末世重生），新书启动即生效
> **设计目标**：从"评分越高越好"转向"读者越爱看越好"。建立 5 道质量护栏让"标题反向 / 评分掩盖硬伤 / polish 沉没成本 / 12 章 0 决策钩 / hook_close 落库漂移"等 7 类质量陷阱在代码层永久封死。

---

## 1. A9 评分硬底线（apply_overall_floor）

**问题根因**：旧 overall = 加权平均，硬伤被稀释。Ch4 真实历史数据：consistency=47 + reader-critic=58 + 其余 11 维 80-97 → overall 88（撒谎）→ audit approve_with_warnings → 进 Step 7 commit。读者代理 4/10。

**根治位置**：`scripts/data_modules/chapter_audit.py:apply_overall_floor()` + Layer A9 + `state_manager.set-checker-score` 写库路径

**三规则**（取最严）：

| 规则 ID | 触发 | 后果 |
|---|---|---|
| FLOOR_HARD | 任一维度 < 60 | overall ≤ **70** + audit fail critical (block) |
| FLOOR_SOFT | 任一维度 < 75 | overall ≤ **85** + audit warn high |
| FLOOR_EARLY_RC | 前 5 章 reader-critic < 80 | overall ≤ **80** + audit fail critical (首章追读契约) |

**实战验证**：Ch4 v2 cs={cons:47, rc:58, ooc:74, flow:70, ...} → 旧 overall 88 / 新 overall 70 (raw_avg=81 floor=70) / audit fail critical block。Round 20.2 重写 Ch4 v3 后所有维度 ≥75 → floor 解除 → overall 87 → audit pass。

**代码接口**：
```python
from data_modules.chapter_audit import apply_overall_floor
result = apply_overall_floor(checker_scores_dict, chapter_int)
# {"overall": 70, "raw_avg": 81, "floor": 70, "floor_reasons": ["FLOOR_HARD: ..."]}
```

**禁止事项**：
- 禁止手动 Edit state.json 绕过 floor（hygiene H9 score_alignment 检测 overall vs checker_scores.overall 不一致）
- 禁止 `--set-chapter-meta-field overall_score` 写非 floor-cap 值
- canonical 13 维度限定：`{consistency, continuity, ooc, reader-pull, high-point, pacing, dialogue, density, prose-quality, emotion, flow, reader-naturalness, reader-critic}`-checker

---

## 2. reader-thrill-checker 6 子维度

**问题根因**：13 内 + 14 外 + 7 层审计共 250+ pass/fail 节点，**没有一个评估"读完爽不爽"**。13 维度评工艺/批评/钩子/连贯/情感，缺市场维度。Ch1-12 平均 overall 88-92，读者代理 5.5/10。

**根治位置**：`agents/reader-thrill-checker.md`（207 行）+ SKILL.md Step 3 Batch 2 注册

**6 子维度（每个 0-100）**：

| 子维度 | 评估 | 强 (90+) 例 |
|---|---|---|
| `golden_finger_release` | 金手指释放强度 | 空间救命/扭转局势 |
| `protagonist_victory` | 主角胜利强度 | 当面打脸反派/扳回劣势 |
| `antagonist_setback` | 反派受挫强度 | 反派被当面打脸/失关键 |
| `info_advantage_payoff` | 信息差兑现 | 信息差精准操盘大赢 |
| `title_promise_payoff` | 标题承诺兑现 | 关键里程碑（标题方向 milestone）|
| `plot_momentum` | 节奏推进 | 重大转折/关键决策/分水岭 |

**verdict 4 档**：
- `thrilling`（≥80）→ 读者爽
- `neutral`（65-79）→ 普通
- `tepid`（50-64）→ 淡
- `frustrating`（< 50）→ 让读者烦躁/弃书

**3 个硬约束**：
- **THRILL_HARD_001 标题反向**：本章在标题方向倒退（如标题种田，本章只搞文学独白）→ critical block
- **THRILL_HARD_002 金手指吝啬连续 3 章**：连续 3 章 golden_finger_release ≤ 50 → critical（前 5 章为 high）
- **THRILL_HARD_003 主角无决策**：连续 3 章 plot_momentum ≤ 50 + decisions_by_protagonist = 0 → high

**与既有 checker 的差异**：

| | reader-pull | reader-critic | high-point | **reader-thrill** |
|---|---|---|---|---|
| 视角 | 会不会追下一章 | 读者批评（毛病）| 爽点密度 | **读完爽不爽（强度）**|
| 关注 | 钩子+承诺 | 弃书风险 | 数量 | 金手指/胜利/标题兑现 |

**落库**：
- 不计入 13 canonical（避免触发 7 处真源同步）
- 写 `chapter_meta.thrill_score`（Round 20.1 加入 set-chapter-meta-field 白名单）
```bash
python webnovel.py state update --set-chapter-meta-field \
  '{"chapter":N,"field":"thrill_score","value":{"overall":75,"verdict":"neutral","will_recommend":"yes","subdimensions":{...},"note":"..."}}'
```

**实战验证**（与读者代理对照）：
- Ch4 v2: thrill 38 frustrating · 读者 4/10 ✓
- Ch3 v3: thrill 73 neutral · 读者 8/10 ✓
- Ch4 v3 重写后: thrill 75 neutral（+37 跨档）

---

## 3. H26 hook_close 落库一致性

**问题根因**：Phase G（Round 19）规定 reader-pull-checker 章末输出 `hook_close.primary_type`，data-agent Step K 落库到 state。Ch12 血教训：reader_pull_ch0012.json 写了 hook_close 但 data-agent 跳过 Phase G 步骤，state.chapter_meta.0012.hook_close 缺失。后果：H25 hook_trend 退化跳过 + cross-chapter 决策钩缺失探测失效。

**根治位置**：`scripts/hygiene_check.py:check_hook_close_persistence` (P0)

**检查规则**：
- 若 `reader_pull_chNNNN.json` 含 `hook_close.primary_type`
- 但 `state.chapter_meta.NNNN.hook_close` 缺失或 primary_type 为空
- → **P0 fail** + 给精确修复 CLI 指令

**修复命令**（自动给出）：
```bash
python webnovel.py state update --set-hook-close \
  '{"chapter":N,"primary":"信息钩|情绪钩|决策钩|动作钩","strength":N,"text":"..."}'
```

---

## 4. H25 连续 8 章无决策钩 P0

**问题根因**：Round 19 Phase G 设计 `state get-hook-trend --last-n 5` 输出 `no_decision_hook_8: true`，但旧版仅 reader-pull-checker 输出 issue，hygiene 不强制阻断 → 12 章累积 0 决策钩警报无效。

**根治位置**：`scripts/hygiene_check.py:check_hook_trend` 末尾

**检查规则**：
- 最近 8 章 hook_close.primary_type 全部非空
- "决策钩" 不在最近 8 章里
- → **P0 fail**

**chapter-aware（Round 20.2 修订）**：仅当 `chapter >= chs[-1]`（polish 当前最新章或更新章）时触发，避免 polish 早章被未来章状态误伤。

**修复路径**：
- 下章 hook_close.primary_type = "决策钩"，或
- reader-thrill protagonist_victory ≥ 80（让"主角主动选择"显式化）

---

## 5. H27 polish sunk cost 警报

**问题根因**：Ch6 v3+polish 2 轮+5 项 80 一线（continuity/flow/reader-pull/high-point/pacing 全在 78-83）→ 没人识别这是 sunk cost，AI 还想再 polish。Ch1 v7 11 轮 polish 血教训同源。

**根治位置**：`scripts/hygiene_check.py:check_polish_sunk_cost` (P1) + `polish_cycle.py --max-rounds=3` (硬上限)

**两道防御**：

**防御 1：H27 P1 警报**（条件 AND）：
- narrative_version ≥ v3
- polish_log ≥ 2 轮
- ≥ 5 项 checker_scores ∈ [80, 84]（"80 一线"集群）
- → 提示"建议 Step 0 重写而非继续 polish"

**防御 2：polish_cycle max-rounds 硬上限**：
- 默认 `--max-rounds 3`
- polish_log >= 3 轮 → exit 1 + 协议提示
- 突破上限必须 `--allow-exceed-max-rounds --deviation-reason "为何还要再修"`
- deviation 自动写入 `audit_reports/chNNNN.json.deviations[]`

**实战验证**：Ch6 v5 重写时正确触发 H27 P1 + polish_cycle 通过 deviation 出口路径正常 commit。

---

## 6. dialogue_ratio_override 章型豁免

**问题根因**：post_draft_check 硬规则 dialogue_ratio ≥ 0.20，但**空间种田激活章 / 金融操盘独白章** 等章型对话天生低（Ch3 0.053 / Ch2 0.093）。Round 17.5 Ch9 RCA P1-1 已设计 `context_contract.structural_exemptions.dialogue_ratio_override` 单章 schema，Round 20.3 扩展到项目级配置。

**两层豁免**：

**层 1：项目级配置**（推荐）：
```json
// .webnovel/post_draft_config.json
{
    "dialogue_ratio_override_chapters": [2, 3]
}
```

**层 2：单章 context_contract**（Round 17.5 既有机制）：
```json
// .webnovel/context/chNNNN_context.json
{
    "context_contract": {
        "structural_exemptions": {
            "dialogue_ratio_override": "0.10-0.20"
        }
    }
}
```

**适用章型**：
- 空间视觉章（主角独自在空间催种 / 探索）
- 纯动作章（追逐 / 战斗 / 高密度动作）
- 金融操盘独白章（K 线分析 + 内心戏）
- 情感章（独自回忆 / 心理转折）

**底线**：override 不得低于 0.10（绝对底线）。

---

## 7. 大纲三计划 schema（强制）

**问题根因**：12 章过去标题"我在空间里种出整个基地"承诺空间，Ch12 空间还在"绿芽冒头"。作者层面悄悄把书写回"系统/重生世界观文"，违反北极星承诺。流程没有"标题方向兑现"硬约束。

**根治**：`大纲/总纲.md` 必含三计划（详见 `outline-release-plans-template.md`）：

1. **`golden_finger_release_plan`**：每章金手指释放强度（micro/small/medium/large/milestone）
   - 硬约束：连续 5 章 ≤ micro → critical block
2. **`conflict_release_plan`**：每章冲突类型（A 内心 / B 隐性博弈 / C 决策对线 / D 正面对抗 / E 战斗）
   - 硬约束：每 5 章至少 1 次 D 类 + 每 8 章至少 1 次决策钩
3. **`title_promise_payoff_plan`**：标题关键词逐章兑现进度
   - 硬约束：任一章在标题方向倒退 → critical block；卷末必须达 milestone

**Step 1 context-agent** 读取三计划生成执行包硬约束（thrill 6 子维度起草目标）。

**Step 3 reader-thrill-checker** 比对兑现度（title_promise_payoff_check + golden_finger_used + decisions_by_protagonist）。

---

## 8. Round 20.x 累积时间线

| Round | 重点 | Commits |
|---|---|---|
| Round 20 (2026-04-25) | A9 floor + reader-thrill + 三计划 + polish 上限 | `5551f07` |
| Round 20.1 (2026-04-25) | H25 P0 升级 + H27 sunk cost + thrill 白名单 | `c93a70f` |
| Round 20.2 (2026-04-25) | H25 chapter-aware + Ch3 polish v3 + Ch4 重写 v3 | `404bb1f` |
| Round 20.3 (2026-04-26) | Ch6 重写 v5 + Ch2 polish v3 + 全章评分重审 | `9443eb6` |

**累计成果**：
- 8 道护栏建好（A9/H25/H26/H27/thrill 白名单/polish max-rounds/dialogue override/三计划）
- Ch1-12 体检 Ch4 BLOCK→pass / Ch6 tepid→neutral / Ch3+Ch2 polish 完成
- 397/397 测试通过 / coverage 81.57%
- 4 章 reader-thrill 落库验证维度可信

---

## 9. 跨项目通用化清单

新启动项目时：
1. ✅ `init_project.py` 自动包含三计划模板（Round 20.3 后已集成）
2. ✅ `.webnovel/post_draft_config.json` 默认空 `dialogue_ratio_override_chapters: []`
3. ✅ `agents/reader-thrill-checker.md` 通过 sync-agents 自动同步到 .claude/agents/
4. ✅ SKILL.md 通用化（不引用任何"末世重生"具体内容）
5. ✅ A9 floor + H25/H26/H27 pure-script，无项目耦合

**项目特有的需要手动**：
- 三计划具体内容（每个项目的金手指 / 冲突 / 标题不同）
- dialogue_ratio_override_chapters 名单（每个项目章型不同）
- forbidden_terms_by_chapter（每个项目世界观禁用词不同）

---

## 10. 一句话总结

> Round 20.x 把"读者爽感"系统化、把"评分体系撒谎"封死、把"polish 死循环"装上闸门、把"标题反向"变成 critical block——从今天起，不论写哪本书，这五类质量陷阱都不可能再发生。
