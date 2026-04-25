# 新项目接入 Round 19 流程指南

> **适用场景**：你已经用本 fork 写过《末世重生》，现在要开新项目（如《画山海》/《归途》/《镇妖谱》或全新作品），需要让 Round 19 的所有质量护栏在新项目自动生效。

> **Round 19.1 P0-1 关键变更**：私库 CSV 改为**项目本地** `{project}/.webnovel/private-csv/`，跨项目隔离 — 不会再被《末世重生》的"陆沉/麦穗/印记"反例污染。

---

## 1. Round 19 在新项目的自动生效 vs 手工初始化项

### 1.1 自动生效（无需任何操作）

新项目跑 `webnovel-init` 后立即生效：

| Phase | 兑现 | 路径 |
|---|---|---|
| **A** anti-ai-guide.md 起草预防 | Step 2A 自动 cat | `${SKILL_ROOT}/references/anti-ai-guide.md` |
| **A** 8 倾向 + 替代速查表 | writer 起草前必读 | 同上 |
| **B** polish K/L/M/N 词库 + 4 句式 | Step 4 polish 自动扫 | `${SKILL_ROOT}/references/polish-guide.md` |
| **C** reader-naturalness 5 子维度 | reader-naturalness-checker 默认输出 | `${PROJECT}/.webnovel/state.json::checker_subdimensions` |
| **E** plan 跨卷感知 | plan SKILL Step 1.5 自动跑 | `webnovel.py state get-recent-meta` |
| **G** 章末钩子 4 分类 | reader-pull-checker 默认输出 + H25 自动检查 | hook_close + `state get-hook-trend` |
| **H** 画面感 3 子规则 | prose-quality-checker 默认输出 | `${SKILL_ROOT}/references/visual-concreteness-rubric.md` |
| **I** Ch1 追读契约 | chapter ≤ 5 自动 cat | `${SKILL_ROOT}/references/first-chapter-hook-rubric.md` |
| **X1** reader-critic <75 全卷 P0 阻止 | 每章 audit 自动检测 | `chapter_audit.check_a_x1_reader_critic_hard_block` |
| **X1B** 前 5 章写前自检 | Step 2A 必输出 + audit 强制检查 | `${PROJECT}/.webnovel/tmp/pre_draft_self_check_ch{NNNN}.json` |

### 1.2 需要手工初始化（写完 1-2 章后跑 1 次）

只有 **Phase F 私库** 需要在新项目积累 1-2 章 checker 数据后手工跑 extractor：

```bash
# 假设新项目 "画山海" 已经跑完 Ch1-2 完整 Step 0-7
PROJ="画山海"

# 跑 4 张私库表提取（首次运行会从 fork 共享 schema 复制表头）
for tbl in ai-replacement-vocab canon-violation-traps emotion-earned-vs-forced strong-chapter-end-hooks; do
  python -X utf8 webnovel-writer/scripts/webnovel.py \
    --project-root "${PROJ}" \
    private-csv --table $tbl --chapters 1-2
done

# 验证
ls "${PROJ}/.webnovel/private-csv/"
# 应该看到 4 张本项目专属 CSV
```

### 1.3 私库本作专属 — 不要复制其他项目的 CSV

**禁止**把《末世重生》的 `private-csv/*.csv` 拷到《画山海》下！末世重生反例（"半度/半秒/陆沉/麦穗/印记"）对其他题材是**误导**。每个项目的私库必须从该项目自己的 `tmp/*.json` checker 数据派生。

---

## 2. 新项目 Round 19 流程检查清单

按以下顺序确认新项目就绪：

### Step 1：webnovel-init 完成后

```bash
PROJ="画山海"
python -X utf8 webnovel-writer/scripts/webnovel.py --project-root "${PROJ}" preflight
```

期望：8 项全 OK。

### Step 2：第一次写 Ch1 时（最关键）

由于 chapter ≤ 5 触发 Phase X1B 写前自检：

1. Step 2A 起草前 writer 必须 Read 三个 references：core-constraints / anti-ai-guide / visual-concreteness-rubric + first-chapter-hook-rubric（chapter==1 自动加载）
2. Step 2A 起草前必须输出 `tmp/pre_draft_self_check_ch0001.json`（5 类自检 + verdict）
3. 起草完正文后 reader-pull-checker 强制走 first-chapter A/B/C 三项（A 触发 → REWRITE_RECOMMENDED）
4. Step 6 audit 检查 X1 + X1B（reader-critic ≥ 75 + self-check JSON 存在）

### Step 3：Ch1-Ch2 完成后初始化私库

```bash
for tbl in ai-replacement-vocab canon-violation-traps emotion-earned-vs-forced strong-chapter-end-hooks; do
  python -X utf8 webnovel-writer/scripts/webnovel.py --project-root "${PROJ}" \
    private-csv --table $tbl --chapters 1-2
done
```

### Step 4：Ch3+ 起 writer 自动消费私库

context-agent 在创作执行包注入：
- `writing_guidance.local_blacklist`（本项目 ai-replacement-vocab 前 10 条）
- `writing_guidance.canon_traps`（本项目 canon-violation-traps 前 5 条）
- `writing_guidance.hook_close_examples`（本项目 strong-chapter-end-hooks 前 2-3 条）

### Step 5：Ch6+ 起 X1B 自动跳过

chapter > 5 时 Phase X1B audit 跳过；Phase X1（reader-critic <75 全卷阻止）继续硬卡。

### Step 6：每章 commit 前

```bash
python -X utf8 webnovel-writer/scripts/webnovel.py sync-cache
python -X utf8 webnovel-writer/scripts/webnovel.py preflight
python -X utf8 "${PROJ}/.webnovel/hygiene_check.py" ${CHAPTER}
```

三套 exit=0 才能 commit。

---

## 3. 已存在项目（如《镇妖谱》/《画山海》）补 Round 19

如果项目已写过 N 章但还没用 Round 19：

### 3.1 一次性补 Phase F 私库（拿之前 N 章 checker 数据派生）

```bash
PROJ="镇妖谱"
N=10  # 已写章数

for tbl in ai-replacement-vocab canon-violation-traps emotion-earned-vs-forced strong-chapter-end-hooks; do
  python -X utf8 webnovel-writer/scripts/webnovel.py --project-root "${PROJ}" \
    private-csv --table $tbl --chapters 1-$N
done
```

### 3.2 新章节自动走 Round 19 全流程

无需特殊操作，写 Ch{N+1} 时 SKILL.md 已经更新过的 Step 2A 流程会自动跑。

### 3.3 历史章节 reader-critic 复测（可选）

如果担心历史章节有 reader-critic <75 谷底（如《末世重生》Ch3=62/Ch4=58），跑：

```bash
python -X utf8 webnovel-writer/scripts/webnovel.py --project-root "${PROJ}" \
  audit --chapter 3
```

会自动跑 X1（reader-critic <75 P0）+ X1B（chapter ≤ 5 写前自检），看是否需要补救。

历史章节 X1B 大概率 fail（因为之前没输出 pre_draft_self_check JSON）— 这是**预期行为**，audit fail 不阻断已 commit 章节，但提示未来若重写该章必须补自检。

---

## 4. 跨项目 hygiene 检查

### 4.1 hygiene_check 在新项目的兼容性

每个项目应有自己的 `.webnovel/hygiene_check.py`（项目本地，因为它含项目特定字段如 `state.project_info.naturalness_log` 验证逻辑）。

新项目通过 webnovel-init 创建时 hygiene_check.py 应当被自动复制（参 `init_project.py`）。如果新项目缺这文件：

```bash
cp 末世重生-我在空间里种出了整个基地/.webnovel/hygiene_check.py "${PROJ}/.webnovel/hygiene_check.py"
```

注：hygiene_check.py H25（章末钩子趋势）是 Round 19 Phase G 在 fork 共享 `webnovel-writer/scripts/hygiene_check.py` 加的，新项目本地 hygiene_check.py 应该已经 import 共享版（如 Round 17 项目本地 hygiene 设计），所以自动生效。

### 4.2 项目级 ROOT_CAUSE_GUARD_RAILS.md

每个项目可以有自己的 `ROOT_CAUSE_GUARD_RAILS.md` 记录该项目特有 RCA。**末世重生的 ROOT_CAUSE_GUARD_RAILS.md 不要复制到新项目**（项目特定根因）。

---

## 5. 故障排查

| 症状 | 可能原因 | 解决 |
|---|---|---|
| reader-naturalness 没输出 subdimensions | checker 跑的是缓存版 | `webnovel.py sync-cache && sync-agents` |
| reader-pull 没输出 hook_close | 同上 | 同上 |
| audit X1B 报 self_check_ch0001.json 缺失 | Step 2A 没跑写前自检 | 回 Step 2A 输出 `tmp/pre_draft_self_check_ch{NNNN}.json` |
| context-agent 没注入 local_blacklist | 项目本地 private-csv 未初始化 | 跑 §1.2 私库初始化命令 |
| `private-csv --table X` 报 +0 rows | 该 checker 还没跑 issues 数据 | 写完 ≥ 1 章完整流程后再跑 |
| H25 永远 skip | 已写章数 < 5 | 等写到 Ch5+ 自动启用 |

---

## 6. 关键纪律（跨项目通用）

1. **私库 CSV 不跨项目复制**（每项目专属反例）
2. **fork 共享 `references/private-csv/` 仅作 schema seed**（永远只有表头）
3. **chapter ≤ 5 必须输出 pre_draft_self_check JSON**（X1B 强制）
4. **reader-critic ≥ 75 才能 commit**（X1 全卷强制）
5. **chapter == 1 必须满足 A/B/C 追读契约**（Phase I 强制）
6. **每章末必须输出 hook_close.primary_type**（Phase G 强制）
7. **reader-naturalness 必须输出 5 子维度**（Phase C 必须，老 schema 兼容）
8. **正文中文弯引号 + 无 ASCII " + 无 Markdown 标题**（永久纪律）
9. **严禁手改 state.json**（feedback_no_manual_state_edits）
10. **严禁跳步**（feedback_no_skip_steps）

---

## 7. 升级路径

将来 Round 20+ 新增 Phase 时，本指南的 §1 表会随之更新。每次 git pull fork 后跑：

```bash
python -X utf8 webnovel-writer/scripts/webnovel.py sync-cache
```

新项目和已存在项目都自动获得最新规则（私库数据保留本地不会被 sync 覆盖）。
