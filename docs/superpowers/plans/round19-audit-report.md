# Round 19 端到端独立审计报告

> **审计时间**：2026-04-25
> **审计范围**：Round 19 全部 15 commits（529e966 → 514eb7b），9 Phase（A/I/X1/F/H/B/E/C/G）+ Phase 0/7/8 + Phase D 决策
> **审计方法**：直读代码 / 配置 / 数据；独立运行 9 类 CLI；不信测试报告自陈
> **审计员视角**：独立质量 subagent，对所有交付物去伪存真

---

## 1. 交付清单完整性

### 1.1 v3 计划落地清单 vs 实际 (35 文件改动 / +9001 / -336)

| v3 计划文件 | 实际 git 改动 | 包含关键字段 | 备注 |
|---|---|---|---|
| `skills/webnovel-write/SKILL.md` | M (+102) | `anti-ai-guide` × 3, `visual-concreteness-rubric` × 1, cat 加载 × 2 | 已加载 anti-ai 与 visual 文件；first-chapter-hook / chapter-end-hook / private-csv 仅在 references 目录列了名字，**无 cat 加载** |
| `references/anti-ai-guide.md` | A (+177) | 8 倾向 + 5 即时检查 + 替代速查表 + N1-N5 本作根因 + Phase X1 写前自检 | 完整 |
| `references/first-chapter-hook-rubric.md` | A (+104) | A/B/C 9+3 rubric + Ch2/3 跨章弱版 | 完整，由 reader-pull-checker 引用 |
| `references/chapter-end-hook-taxonomy.md` | A (+96) | 4 类 + 跨章趋势 | 完整 |
| `references/visual-concreteness-rubric.md` | A (+121) | 视觉锚点 / 5+1 感官 / 抽象动作 | 完整 |
| `references/polish-guide.md` | M (+155) | K/L/M/N 4 类（15+10+10+9=44 词）+ **4 句式** | **不一致**：v3 计划写"K/L/M/N + 6 句式"，落地仅 4 句式 |
| `skills/webnovel-plan/SKILL.md` | M (+48) | Step 1.5 cross-volume + get-recent-meta + get-hook-trend 调用 | 完整 |
| `agents/context-agent.md` | M | Phase A 6 提醒 + Phase F 私库注入 | 完整，但内含**硬编码"本作（末世重生）"** |
| `agents/reader-naturalness-checker.md` | M | Phase C 5 子维度 + Phase F 回查 | 完整，但**verdict schema 内部冲突**（line 41 5 类 vs line 184 3 类） |
| `agents/reader-pull-checker.md` | M | Phase I 9+3 + Phase G 4 分类 + 趋势 | 完整 |
| `agents/prose-quality-checker.md` | M | Phase H 画面感 3 子规则 | 完整 |
| `agents/consistency-checker.md` | M | Phase F 私库回查 canon-violation-traps | 完整 |
| `agents/data-agent.md` | M | Phase C/G 落库段 | 完整，但段落**追加在 Step K 之外**（line 591+），不是嵌进 Step K 主流程 1-5 步 |
| `references/private-csv/` | A 5 file | 4 CSV + README | 完整 |
| `scripts/private_csv_extractor.py` | A (+439) | 4 表 schema + extractor | 完整，但**默认输出 fork 共享路径**（跨项目污染 bug） |
| `scripts/data_modules/webnovel.py` | M (+26) | private-csv 子命令转发 | 完整 |
| `scripts/data_modules/state_manager.py` | M (+192) | set-checker-subdimensions / set-hook-close / get-hook-trend / get-recent-meta | 4 命令均落库 |
| `scripts/hygiene_check.py` | M (+54) | H25 注册到主调度 (line 1468) | 完整 |
| `scripts/polish_cycle.py` | M (+23) | _lowest 真路径 (line 601-618) | 完整，向下兼容 |
| `scripts/quote_pair_fix.py` | M (+35) | _mask_fenced 保护 | 完整，但**未对 .py/.json/.yaml/.csv 跳过**（Phase E subagent 已踩雷） |
| `CUSTOMIZATIONS.md` | M | 9 段 Round 19 (A/I/X1/F/H/B/E/C/G) + 1 复审段 | **缺 DO NOT MERGE 段**（v3 计划 Task 7.1 要求"写入 CUSTOMIZATIONS.md DO NOT MERGE 段"未兑现） |
| `ROUND19_DO_NOT_MERGE.md` | A (+93) | 10 类拒绝清单 | 文件存在，但 CUSTOMIZATIONS.md 没有引用链接 |
| `quality_baseline.json` | A (10091 字节) | per_chapter + avg | 完整 |
| `docs/superpowers/plans/upstream-snapshot/COMMIT_REF.txt` | A (+517) | 三组 commit | 完整 |
| `docs/superpowers/plans/round19-research/` | A 2 file | RCA + Phase D 决策 | 完整 |

### 1.2 v3 计划列了但未落地

- **`ROOT_CAUSE_GUARD_RAILS.md`** Modify Phase 7 未发生（grep 无 DO NOT MERGE 引用）
- **`CUSTOMIZATIONS.md` DO NOT MERGE 段**未追加（v3 Task 7.1 要求）
- **polish-guide 6 句式** 实际仅 4 句式

### 1.3 落地了但 v3 计划未列的

- `webnovel-writer/agents/audit-agent.md` 改动（grep 未做深入审计 — Phase X1 间接相关）
- `2026-04-25-reader-quality-uplift-v2.md`、`upstream-cherry-pick-quality-uplift.md` 两份过程产物计划文件

---

## 2. CLI 端到端真实测试结果

| # | 命令 | exit | 关键字段 | 评估 |
|---|---|---|---|---|
| 1 | `webnovel.py sync-cache` | 0 | +0/~0/=308 | OK |
| 2 | `webnovel.py preflight` | 0 | 8/8 OK | OK |
| 3 | `hygiene_check.py 11` | 0 | **27 通过 / 0 P0 / 0 P1 / 0 P2** | OK |
| 4 | X1 `check_a_x1_reader_critic_hard_block` Ch1-11 | 0 | Ch1=pass / Ch2=warn / Ch3=fail / Ch4=fail / Ch5-11=pass | OK，与测试报告 §2.2 一致；severity=critical 字段在 pass 路径上是阈值类别非真实"严重"，不混淆 |
| 5 | `state get-hook-trend --last-n 11` | 0 | recent_primary 11 章全在；no_decision_hook_8=true | OK |
| 6 | `state get-recent-meta --last-n 5` | 0 | Ch7-11 完整字段（hook_close + overall + word_count + narrative_version） | OK |
| 7 | `state update --set-checker-subdimensions` | 0 | _lowest=a 自动算出，落库正确 | OK |
| 8 | `private-csv --table ai-replacement-vocab --chapters 5` | 0 | +0/total 89 | OK |
| 9 | 新建 `/tmp/dummy-project` 跑 get-hook-trend | 0 | 优雅返回空 chapters[] | OK，不崩 |
| 10 | 新建 `/tmp/dummy-project` 跑 private-csv | 0 | **+0/total 89** | **重大 bug**：dummy 项目未提供任何数据，但写到与末世重生同一份 CSV（共享 fork 目录） |
| 11 | 拷贝 .py 文件跑 quote_pair_fix --dry-run | 0 | "fixed=162" | **bug**：仍会改 .py，未做扩展名跳过 |

---

## 3. 流程逻辑 bug

### 3.1 SKILL.md 加载链不完整 (P1)

只有 anti-ai-guide.md 和 visual-concreteness-rubric.md 被 Step 2A 显式 cat 加载（line 470-471）。

- `first-chapter-hook-rubric.md` — 仅 chapter==1 由 reader-pull-checker 加载（OK，因为 Ch1 写前 reader-pull 还没跑）。**但 writer Step 2A 起草前不会读首章 rubric**，违背 Phase I 设计意图（"Ch1 必须签下情绪契约"应该在起草时即遵守）
- `chapter-end-hook-taxonomy.md` — 仅 reader-pull-checker / data-agent 引用名字（OK，定位为审查/落库时用）
- `private-csv` 4 张 CSV — 没在 SKILL.md 任何地方提及，**仅依赖 context-agent.md / reader-naturalness-checker.md / consistency-checker.md / data-agent.md 自身段落**。LLM 子代理是否读到取决于运气
- `pre_draft_self_check_ch{NNNN}.json` — anti-ai-guide.md line 113 要求"chapter ∈ (1,2,3,4,5) 起草前必须执行 5 类自检并写 tmp/pre_draft_self_check"，但 **SKILL.md Step 2A 没有触发该自检**。grep "pre_draft_self_check" 在 SKILL.md 0 命中。**这是最严重的 dead spec**——X1 写前自检规范存在但流程不会执行

### 3.2 reader-naturalness-checker.md verdict schema 冲突 (P1)

- line 41 verdict ∈ {`REJECT_CRITICAL | REJECT_HIGH | REWRITE_RECOMMENDED | POLISH_NEEDED | PASS`} (5 类)
- Phase C 升级段 line 184 verdict ∈ {`PASS | NEEDS_POLISH | REWRITE_RECOMMENDED`} (3 类)

LLM 输出会困惑：用 NEEDS_POLISH 还是 POLISH_NEEDED？hygiene/data-agent 的 naturalness_verdict 解析也可能漏 NEEDS_POLISH。

### 3.3 data-agent.md Phase C/G 段是追加段不是嵌主流程 (P2)

Phase C/G 段（line 591/607）紧贴在 Step K 主流程（line 426-481）后面，不是嵌进 Step K 内 5 个步骤里。data-agent 实际跑 Step K 时是否会读后续段落取决于 prompt 完整性——Anthropic LLM 通常会读全文，但是当主流程明确说"Step K 步骤 1/2/3/4/5"时，data-agent 会聚焦在这 5 步上。Phase C/G 落库段可能被某些子代理执行漏。

### 3.4 dead doc reference: webnovel.py private-csv --append (P2)

`references/private-csv/README.md` line 47 说"`webnovel.py private-csv --append` 走相同 schema 验证"——但实际 CLI 不支持 `--append` flag（只有 --table/--chapters/--output-dir）。文档误导。

### 3.5 hook_close.strength 字段全是 80 (P2)

11 章 hook_close 全部启发式回填后 strength 固定 80（除 Ch5=85）；与 reader-pull 主分（实际 81-95 不等）解耦——这只是历史回填的兜底，不影响新章节，但是数据不真实。

---

## 4. 跨项目可移植性问题（用户 explicit 关注："我写其他小说也要这样"）

### 4.1 私库 CSV 跨项目污染（**P0 严重**）

`private_csv_extractor.py` line 411 默认 out_dir = `webnovel-writer/references/private-csv/`（fork 共享目录），不是项目本地 `.webnovel/private_csv/`。

**实测**：在新建 dummy-project 跑 `private-csv --table ai-replacement-vocab --chapters 1-5`，CLI 直接对**末世重生的 89 条共享 CSV** 操作（exit=0）。如果 dummy 项目有数据可提取，会**追加到末世重生的 CSV**。

context-agent.md line 714 明确读 `${CLAUDE_PLUGIN_ROOT}/references/private-csv/ai-replacement-vocab.csv`（fork 共享路径）。

**后果**：用户开新项目"画山海"，跑一次 private-csv 后：
- 末世重生 89 条本作专属反例（含"陆沉/麦穗/末世重生 Ch4 末"等本作人物/情节锚点）会注入"画山海" 的 writing_guidance.local_blacklist
- "画山海"提取的反例会污染末世重生的 CSV
- 两本书互相干扰

README.md line 7 自称"sync-cache 后所有项目自动受益"——**与本作专属内容矛盾**：跨项目自动注入"陆沉专属：拧手表/咬笔帽"会让其他项目角色变得奇怪。

### 4.2 anti-ai-guide.md 5 类本作根因边界标注（P2）

anti-ai-guide.md line 88 表头明标"**本作（末世重生）专属 5 类根因映射**"，N1-N5 列出"半度/半秒/半指/半分"、"陆沉特有的微动作（咬笔帽/拧手表/数手指）"等。

边界标注**正确**——N1-N5 表本身有"本作（末世重生）专属"标题。但是 Step 2A 加载该文件时，跨项目 writer 会把"陆沉拧手表"当作通用规则，可能**轻度误导**。

修复建议：N1-N5 段加 frontmatter 字段 `applies_to: ["末世重生"]`，跨项目按当前 project_id 自动跳过这一段。

### 4.3 anti-ai-guide.md Phase X1 自检 5 项跨项目通用 (OK)

Phase X1 5 项前置自检（金手指首披露 / 突兀编号 / 大纲爽点兑现 / 伏笔铺设 / 读者卡点）通用，不绑定本作。

### 4.4 context-agent.md 硬编码"本作（末世重生）" (P1)

line 723: "同样读 canon-violation-traps.csv，取**本作（末世重生）**相关前 5 条到 writing_guidance.canon_traps"。

**这是字面文本"本作（末世重生）"硬编码进 prompt**。跨项目用户开新书时，context-agent 会按字面"末世重生"过滤 canon_traps（找不到匹配 → 退化为不注入）。

修复建议：改为"本项目（{project_name}）相关前 5 条"，由 LLM 按当前 project_id 解析。

---

## 5. 文档不一致

### 5.1 v3 计划 vs 实际落地不一致

| 项 | v3 计划 | 实际 | 差异 |
|---|---|---|---|
| polish-guide 句式数 | K/L/M/N + **6 句式** | 4 句式 | **缺 2 句式** |
| CUSTOMIZATIONS.md DO NOT MERGE 段 | 必写（Task 7.1） | 单独写到 ROUND19_DO_NOT_MERGE.md，CUSTOMIZATIONS 无引用 | **未兑现** |
| ROOT_CAUSE_GUARD_RAILS.md 引用 | Modify · 7（DO NOT MERGE 段） | 文件无改动 | **未兑现** |
| Round 19 commit 数 | v3 没数字承诺 | 15（含 plan + 测试报告） | OK |

### 5.2 测试报告 §1.1 错描述

测试报告 §1.1 说 "**14 commits 时间线**"，但实际 git log 84249bd..HEAD 是**15 commits**（含 Phase 0 plan commit 529e966 + 14 实施 commits = 15）。测试报告把 Phase 0 漏数了。

### 5.3 测试报告 §1.3 "拒绝清单 10 类" vs DO NOT MERGE 文件 "10 类"

测试报告说"DO NOT MERGE 10 类"，实际 ROUND19_DO_NOT_MERGE.md 列了 **10 类**。一致。OK。

### 5.4 reader-naturalness-checker.md 内部冲突

参 §3.2 — verdict schema 5 类 vs 3 类内部矛盾。

---

## 6. 真实 bug 清单（按 P0/P1/P2 严重度）

### P0（必修，阻断可移植性 / 引发数据污染）

| # | bug | 影响 |
|---|---|---|
| **P0-1** | 私库 CSV 跨项目共享 fork 目录 | 用户开第二本小说会污染本作私库；context-agent 读 fork 共享 CSV 会注入本作专属反例到新项目 |
| **P0-2** | quote_pair_fix.py 不按文件扩展名跳过（仍会改 .py） | Phase E subagent 已经踩过雷（state_manager.py 误改 158 段）；下一次任何代理对 .py 跑就会破坏代码 |
| **P0-3** | SKILL.md Step 2A 不触发 pre_draft_self_check | X1 设计的"前 5 章写前自检 5 类"是 dead spec — writer 起草时不会执行该自检；anti-ai-guide.md 的 §X1 段落只是文档不是流程 |

### P1（影响兑现效果）

| # | bug | 影响 |
|---|---|---|
| **P1-1** | reader-naturalness-checker verdict schema 内部冲突（5 类 vs 3 类） | LLM 可能输出 NEEDS_POLISH（Phase C 升级段定义）但 hygiene 解析 5 类 schema 不识别 → naturalness_verdict 落库错乱 |
| **P1-2** | context-agent.md 硬编码"本作（末世重生）" | 跨项目用户开新书时，canon_traps 注入因字面字符串不匹配而退化 |
| **P1-3** | private-csv ai-replacement-vocab.csv 数据列错位（"好样本"列 = "修复方向"列内容） | 私库回灌时 writer 拿到"好样本=修复方向 fix_hint 文字"，不是真正的对照样本 — Phase F 杠杆失效 |
| **P1-4** | canon-violation-traps.csv 禁区类型误填 | 实际坏样本是 audit-drift 流程问题，但禁区类型列填"战力越权/设定矛盾/时间线漂移/关系漂移"等小说世界观禁区，分类完全错位 |
| **P1-5** | CUSTOMIZATIONS.md 缺 DO NOT MERGE 引用 | v3 Task 7.1 未兑现；以后维护者找不到 ROUND19_DO_NOT_MERGE.md |
| **P1-6** | strong-chapter-end-hooks.csv 仅 3 条数据 | 测试报告说 11 章中仅 Ch3/4/8 ≥ 90 分；样本量太少，writer 起草章末几乎拿不到参考 |
| **P1-7** | hook_close.strength 11 章固定 80 | 启发式回填没有真实信号；下章 reader-pull-checker 跨章对比时分数失真 |

### P2（优化项）

| # | bug | 影响 |
|---|---|---|
| **P2-1** | data-agent.md Phase C/G 段是追加段不是嵌 Step K | 段落级被忽略风险（取决于 LLM prompt 解析） |
| **P2-2** | private-csv README.md `--append` 是 dead doc | CLI 不支持，文档误导 |
| **P2-3** | polish-guide 仅 4 句式 vs v3 计划 6 句式 | 兑现差 2 项（具体哪 2 项 v3 计划未明列，影响小） |
| **P2-4** | 测试报告 §1.1 说 14 commits 实际 15 | 数字小错 |
| **P2-5** | emotion-earned-vs-forced.csv 16 条样本相对稀疏 | 单作样本量少 |

---

## 7. 必修建议（带 fix patch sketch）

### P0-1 修：私库按项目分目录 + 共享目录拆分

```python
# private_csv_extractor.py 主函数
out_dir_base = Path(__file__).resolve().parent.parent / "references" / "private-csv"
project_id = project.name  # 或读 state.project.id
out_dir = out_dir_base / project_id  # 按项目分目录
```

context-agent.md line 714 改：

```diff
- 读 ${CLAUDE_PLUGIN_ROOT}/references/private-csv/ai-replacement-vocab.csv
+ 优先读 ${CLAUDE_PLUGIN_ROOT}/references/private-csv/{project_id}/ai-replacement-vocab.csv（项目专属）
+ 若不存在，回退读 ${CLAUDE_PLUGIN_ROOT}/references/private-csv/ai-replacement-vocab.csv（fork 共享，仅含跨作品通用 AI 癖好）
```

迁移：把现有 4 张 CSV 移动到 `references/private-csv/末世重生-我在空间里种出了整个基地/`，fork 共享目录留空或仅放跨作品通用的 AI 癖好（第二本小说开新目录）。

### P0-2 修：quote_pair_fix.py 文件类型黑名单

```python
SKIP_EXTENSIONS = {".py", ".json", ".yaml", ".yml", ".toml", ".csv", ".db", ".sql"}

def main():
    file_path = Path(sys.argv[1])
    if file_path.suffix.lower() in SKIP_EXTENSIONS:
        print(f"[SKIP] non-prose file extension: {file_path.suffix}")
        return 0
    ...
```

### P0-3 修：SKILL.md Step 2A 触发 pre_draft_self_check

在 SKILL.md Step 2A 起草前 bash 段（line 469-472）追加：

```bash
# Round 19 Phase X1 · 前 5 章写前自检（chapter ≤ 5）
if [ "$chapter" -le 5 ]; then
  cat "${SKILL_ROOT}/references/anti-ai-guide.md" | sed -n '/Phase X1 · 前 5 章/,/与 polish_cycle 的耦合/p'
  # writer 必须按 5 项执行自检并写：
  # ${PROJECT_ROOT}/.webnovel/tmp/pre_draft_self_check_ch{NNNN}.json
fi
```

或加 hygiene 项 `H26 pre_draft_self_check_required (chapter ≤ 5)`，缺该 JSON → P1 warn。

### P1-1 修：reader-naturalness-checker.md verdict schema 统一

把 line 184 的 `{PASS | NEEDS_POLISH | REWRITE_RECOMMENDED}` 改为与 line 41 一致的 `{REJECT_CRITICAL | REJECT_HIGH | REWRITE_RECOMMENDED | POLISH_NEEDED | PASS}`。Phase C 升级段 verdict 取最低子维度推断：

- 任一子维度 < 50 → REJECT_CRITICAL
- 任一子维度 < 70 → REJECT_HIGH
- 任一子维度 < 80 → REWRITE_RECOMMENDED
- 任一子维度 < 90 → POLISH_NEEDED
- 全部 ≥ 90 → PASS

### P1-2 修：context-agent.md project-aware

line 723 改：

```diff
- 同样读 canon-violation-traps.csv，取本作（末世重生）相关前 5 条
+ 同样读 canon-violation-traps.csv，取本项目（state.project.id）的前 5 条
+ （CSV 行须含 project_id 列，缺失时按字符串包含 project_name 字段过滤）
```

### P1-3/P1-4 修：private_csv_extractor.py 修列填充 + 重新提取

extractor 现在的 bug：`fix_hint` 同时写"好样本"和"修复方向"两列。

```python
# 提取 issue 时分别填充：
row["坏样本"] = _trunc(_evidence_or_desc(issue), 200)  # 反例文本
row["好样本"] = _trunc(_extract_good_example(issue), 200)  # 显式好例（如 highlights[]）；提取不到则空
row["修复方向"] = _trunc(_fix_hint(issue), 120)  # 一句 fix_hint
```

`_extract_good_example` 优先从 issue 的 `correction` / `revised_quote` / `highlights[]` 字段取；不要从 fix_hint 兜底（避免与"修复方向"列重复）。

canon-violation-traps.csv 禁区类型分类：用 keyword 映射规则代替（"data_drift / 27_score / B 层"→ 流程审计；"setting/timeline/character"→ 小说禁区）；先按"流程审计 / 设定矛盾 / 时间线漂移 / 关系漂移 / 战力越权"5 类，让流程审计自成 1 类不混入小说禁区。

### P1-5 修：CUSTOMIZATIONS.md 加 DO NOT MERGE 引用段

在 CUSTOMIZATIONS.md 顶部追加：

```markdown
## [2026-04-25 · DO NOT MERGE 永久清单 · Round 19 立项]

参见 `webnovel-writer/ROUND19_DO_NOT_MERGE.md`。10 类 upstream 改动永久不合并；每次 fetch upstream 跳过这些类别，不必重新评估架构选型。
```

---

## 8. Round 20 候选

不阻断兑现但应进 Round 20 的项：

| 候选 | 触发条件 |
|---|---|
| Phase D upstream CSV 9 表 | Ch12-13 reader_critic 题材契合度 < 80 |
| 私库本地化扩展（按 project 分目录后） | P0-1 修后追加 |
| `webnovel.py private-csv --append` 子命令 | README.md doc 兑现 |
| polish-guide 补 2 句式（凑齐 6 个） | v3 计划完整兑现 |
| anti-ai-guide.md frontmatter `applies_to: [project_id]` 段落级过滤 | 跨项目精确化 |
| reader-naturalness verdict schema 子维度推断逻辑代码化 | hygiene 自动校验 |
| chapter_brief 引入（Phase F 私库回灌效果不显著时） | v3 §6.3 候选 |
| H21 跨章风格漂移加码 | 私库回灌后仍有重犯模式 |
| H26 pre_draft_self_check 强制 | P0-3 加固 |
| `references/03-角色口径表.md / 07-本地化资料包.md` 抽象成 fork-level 跨项目模板 | reader-naturalness Ch11 方言血教训跨项目防御 |

---

## 9. 总评

### 9.1 Round 19 是否成功？**部分成功**

**已兑现**：
- 12 类 RCA top 根因防御层全覆盖（A/B/C/F/G/H 多层联防）
- 4 个新 CLI 全部实现（set-checker-subdimensions / set-hook-close / get-hook-trend / get-recent-meta）
- H25 真注册到主调度（不是 dead code）
- polish_cycle._lowest 真路径
- X1 函数对 Ch1-11 历史数据回测结果与测试报告 §2.2 一致（Ch3=fail / Ch4=fail / Ch1+Ch5-11=pass）
- hygiene_check 27 通过 / 0 P0 / 0 P1 / 0 P2
- 11 章 hook_close 回填
- CUSTOMIZATIONS.md 9 段 Phase 完整
- 私库 4 张 CSV 共 136 条数据（虽然干货度有问题）
- 三套基础测试全绿
- N1-N5 RCA 关键词（半度/半秒/不是X/后颈凉/手心汗/喉咙紧/掌心印记跳/了一下）真在 anti-ai-guide.md 列出

**未兑现 / 有 bug**：
- P0-1 私库跨项目污染（最严重，违反用户"我写其他小说也要这样"诉求）
- P0-2 quote_pair_fix.py 还会改 .py（已踩过雷未根治）
- P0-3 X1 写前自检规范在文档里但流程不会执行（dead spec）
- P1 七项（schema 冲突 / 项目硬编码 / CSV 列错位 / 禁区分类错 / DO NOT MERGE 缺引用 / 章末好样本仅 3 条 / hook_close strength 全是 80）
- v3 计划承诺 polish-guide 6 句式实际 4 句式
- 测试报告 §1.1 commits 数 14 实际 15

### 9.2 评分

**76 / 100**

- 设计层 (40 分)：38 — 三件标尺映射清晰，9 Phase 全有 ROI，RCA 12 类根因覆盖到位
- 代码层 (30 分)：22 — H25/_lowest/X1 函数真路径，CLI 4 件全工作；但 quote_pair_fix.py 未根治、跨项目路径设计错
- 数据层 (15 分)：8 — 私库 4 张 CSV 共 136 条但**列对齐错位**+ **禁区分类错** + 长尾稀疏；私库回灌实际杠杆远低于宣称
- 集成层 (15 分)：8 — SKILL.md 加载链不完整（first-chapter-rubric / chapter-end-taxonomy / private-csv / pre_draft_self_check 都未在 SKILL.md cat），data-agent Phase C/G 段是追加段，verdict schema 内部冲突，CUSTOMIZATIONS.md 缺 DO NOT MERGE 引用

### 9.3 一句话结论

**Round 19 在"自然度 / 画面感 / 追读力"三件标尺上做对了大方向（90% 框架到位），但用户最关心的"我写其他小说也要这样"被 P0-1 和 P1-2 直接破坏，外加 X1 写前自检 dead spec / quote 脚本未根治 / 私库 CSV 列对齐错位 / data-agent 段落集成弱化等多重 bug；推 Round 20 必修 P0×3 + P1×7 才能宣告 Round 19 真正落地。**

---

## P0/P1 必修清单（≤ 10 条 · 按优先级排序）

| # | 严重 | 改动 | 估时 |
|---|---|---|---|
| 1 | P0-1 | 私库 CSV 按 project_id 分目录（extractor 改 out_dir + context-agent 改读路径 + 迁移现有 4 张 CSV） | 2h |
| 2 | P0-2 | quote_pair_fix.py 加文件扩展名黑名单 | 30 min |
| 3 | P0-3 | SKILL.md Step 2A 加 chapter ≤ 5 触发 pre_draft_self_check 自检 + writer.md 配套 | 1h |
| 4 | P1-1 | reader-naturalness-checker.md verdict schema 统一为 5 类，并代码化 5 段子维度推断 | 30 min |
| 5 | P1-2 | context-agent.md 字面"本作（末世重生）"改为按 state.project.id 动态过滤 | 30 min |
| 6 | P1-3 | private_csv_extractor.py 列填充修复（`好样本` 不再用 fix_hint 兜底） + 重新提取 4 张 CSV | 1.5h |
| 7 | P1-4 | canon-violation-traps.csv 禁区类型分类规则修复 + 流程审计单独成类 + 重新提取 | 1h |
| 8 | P1-5 | CUSTOMIZATIONS.md 顶部追加 DO NOT MERGE 引用段（指向 ROUND19_DO_NOT_MERGE.md） | 10 min |
| 9 | P1-6 | strong-chapter-end-hooks.csv 扩样：考虑 reader_pull ≥ 85 而非 ≥ 90 | 30 min |
| 10 | P1-7 | hook_close.strength 11 章用 reader_pull 主分回填（替换固定 80） | 30 min |

**总计**：~7.5 小时根治全部 P0+P1。建议作为 Round 19.1 或 Round 20 首阶段。
