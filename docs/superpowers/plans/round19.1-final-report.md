# Round 19.1 P0 根治 · 完整测试报告

> **触发**：Round 19 deep research 审计揪出 3 个 P0 bug + 7 个 P1，影响"我写其他小说也要这样"用户目标。Round 19.1 优先根治 3 个 P0。
> **基线**：Round 19 14 commits（529e966 → 514eb7b）
> **末态**：Round 19.1 (P0-1 + P0-2 + P0-3 + 迁移 + 测试)

---

## 1. 3 个 P0 bug 与根治方案

### P0-1 · 私库 CSV 跨项目污染（致命）

**Root cause**：

- `private_csv_extractor.py` 默认输出到 fork 共享目录 `webnovel-writer/references/private-csv/`
- `context-agent.md` / `reader-naturalness-checker.md` / `consistency-checker.md` 三个 agent 引用 `${CLAUDE_PLUGIN_ROOT}/references/private-csv/...`
- Round 19 Phase F 已往 fork 共享目录写了 89+28+16+3 = 136 条**末世重生本作专属反例**（含"陆沉/麦穗/印记/半度/半秒"等本作私有标记）
- 用户开新项目（如《画山海》/《镇妖谱》）时，writer 起草前会 Read 这 136 条末世重生反例 → **跨项目误导写作**

**Fix patch**：

1. `private_csv_extractor.py:407-411` 默认输出改为 `project / ".webnovel" / "private-csv"`（项目本地）
2. 新增 schema 自动 seed 逻辑：项目本地未初始化时，从 fork 共享 seed 表头（不带数据）
3. 3 个 agent .md 路径全改 `${PROJECT_ROOT}/.webnovel/private-csv/`
4. 末世重生 4 张表 140 条数据迁移到 `末世重生-我在空间里种出了整个基地/.webnovel/private-csv/`
5. fork 共享 4 张表清空仅保留表头 1 行（plugin 携带 schema seed）

**Verification**：

| 验证项 | 期望 | 实测 |
|---|---|---|
| fork 共享 4 表行数 | 各 1（仅表头） | ✅ 4×1=4 行 |
| 末世重生本地 4 表行数 | 90+29+17+4=140 | ✅ 140 行 |
| 新项目 `/tmp/dummy` 跑 extractor | 自动 seed schema 表头，不污染 | ✅ 仅 1 行表头 |
| 3 个 agent 引用路径 | `${PROJECT_ROOT}/.webnovel/private-csv/` | ✅ 全替换 |

### P0-2 · quote_pair_fix.py 不按文件扩展名跳过（已踩雷）

**Root cause**：脚本默认对任何文件按段奇偶配对 ASCII " → 中文弯引号。Phase E subagent 实测对 state_manager.py 误改 158 段 Python 字符串，破坏 .py 语法。

**Fix patch**：

1. main() 加 `SKIP_EXTENSIONS = {.py, .json, .yaml, .yml, .toml, .csv, .tsv, .xml, .js, .ts, .sh, .bat, .ps1, .sql}`
2. 默认对这些扩展名跳过 + 提示 `[SKIP]`
3. 新增 `--force` flag 允许手动绕过守卫
4. 无扩展名文件也默认跳过

**Verification**：

| 文件 | 默认行为 | 实测 |
|---|---|---|
| state_manager.py | SKIP | ✅ |
| state.json | SKIP | ✅ |
| ai-replacement-vocab.csv | SKIP | ✅ |
| MIGRATION_NEW_PROJECT.md | 正常 fix | ✅ fixed=3 段 |
| state_manager.py --force | 强制 fix（dry-run） | ✅ fixed=162 段（与之前一致） |

### P0-3 · 写前自检 dead spec（anti-ai-guide.md 写了但 SKILL.md 不触发）

**Root cause**：

- Phase X1 在 anti-ai-guide.md 末尾追加了 70 行"前 5 章 reader-critic 写前自检清单"段
- 但 SKILL.md Step 2A 起草段没有任何 cat / Read 触发该自检
- 结果：规范在文档里，writer 实际不会跑 → dead spec

**Fix patch**：

1. SKILL.md Step 2A 起草前加载块加条件分支：`if [ "${CHAPTER_NUM}" -le 5 ]; then cat "${SKILL_ROOT}/references/first-chapter-hook-rubric.md"; fi`
2. SKILL.md Step 2A 新增 P0-3 段：要求 chapter ≤ 5 必须输出 `tmp/pre_draft_self_check_ch{NNNN}.json`（5 类自检 + verdict）
3. verdict 处理规则硬要求：REWRITE_RECOMMENDED → 回 Step 1；NEEDS_ADJUST → 起草携带 writing_constraints_addendum
4. `chapter_audit.py` 新增 `check_a_x1b_pre_draft_self_check`：chapter ≤ 5 时验证 self-check JSON 存在 + verdict 合法 + items ≥ 5
5. 注册到 Layer A `_run_layer_a` checks 列表，与 X1 同级

**Verification**：

| 章节 | 期望 | 实测 |
|---|---|---|
| Ch3（历史无 self-check） | fail high | ✅ fail high |
| Ch5（造正常 self-check verdict=PASS） | pass medium | ✅ pass medium |
| Ch12（chapter > 5） | skipped low | ✅ skipped low |
| Ch1-5 历史所有章节 | 全 fail（历史无 self-check 是预期） | ✅ Ch1/3/5 全 fail high（不阻断已 commit 章节，但 audit 提示） |

---

## 2. 12 项端到端测试矩阵

| # | 测试项 | 期望 | 实测 |
|---|---|---|---|
| 1 | sync-cache | exit=0 + 增量同步 | ✅ +0/~3/=304 |
| 2 | preflight 8 项 | 全 OK | ✅（首跑 agents_sync 漂移，sync-agents 后绿）|
| 3 | hygiene Ch11 | 27/0/0/0 | ✅ 27 通过 / 0 P0/P1/P2 |
| 4 | fork 共享 CSV 仅表头 | 4×1 行 | ✅ 4 总行（每张 1 行） |
| 5 | 末世重生本地 CSV 含数据 | 140 条 | ✅ 90+29+17+4=140 |
| 6 | 新项目首次 extractor 自动 seed | 仅复制表头不复制数据 | ✅ 1 行表头 + +0 rows |
| 7 | quote_pair_fix .py/.json/.csv 跳过 | SKIP 提示 | ✅ 3 类全 SKIP |
| 8 | quote_pair_fix .md 仍正常 | fixed=N | ✅ fixed=3 段 |
| 9 | X1 Ch1-11 历史回测 | Ch3/4 fail，其余 pass/warn | ✅ Ch3=62 fail / Ch4=58 fail |
| 10 | G hook trend 5 章 | 4 类分布 + 跨章字段 | ✅ no_decision_hook_8=true |
| 11 | F private-csv 转发项目本地 | total 89（末世重生本地） | ✅ +0/total 89 |
| 12 | E get-recent-meta 3 章 | hook_close + overall_score 完整 | ✅ Ch9/10/11 全字段 |

**12/12 全过**。

---

## 3. 文件改动清单（Round 19.1）

| # | 文件 | 改动 | 行数 |
|---|------|------|------|
| 1 | `webnovel-writer/scripts/private_csv_extractor.py` | 默认输出改项目本地 + schema seed 自动复制 | +18/-3 |
| 2 | `webnovel-writer/scripts/quote_pair_fix.py` | 文件扩展名守卫 + --force flag | +18/-1 |
| 3 | `webnovel-writer/scripts/data_modules/chapter_audit.py` | check_a_x1b_pre_draft_self_check + 注册 | +60/-1 |
| 4 | `webnovel-writer/agents/context-agent.md` | private-csv 路径改项目本地 + 新项目首次初始化指引 | +12/-12 |
| 5 | `webnovel-writer/agents/reader-naturalness-checker.md` | private-csv 路径改项目本地 | +3/-1 |
| 6 | `webnovel-writer/agents/consistency-checker.md` | private-csv 路径改项目本地 | +3/-1 |
| 7 | `webnovel-writer/skills/webnovel-write/SKILL.md` | Step 2A chapter ≤ 5 加 first-chapter-hook-rubric + X1B 写前自检要求 | +35 |
| 8 | `webnovel-writer/references/private-csv/*.csv` × 4 | 清空仅保留表头 | -136 行数据 |
| 9 | `webnovel-writer/MIGRATION_NEW_PROJECT.md` | NEW · 新项目接入 Round 19 流程指南 | +180 |
| 10 | `末世重生-我在空间里种出了整个基地/.webnovel/private-csv/*.csv` × 4 | NEW · 项目本地（被 gitignore，不入主仓） | +140 行 |

主仓 commit 范围：1-9（第 10 项是项目本地数据，gitignore）。

---

## 4. 真实小说质量提升验证

回到核心问题"这次更新提升小说质量吗？"，按读者三件标尺重审：

### 4.1 自然度（不像 AI）

- ✅ Phase A 起草前预防 8 倾向 + 本作 N1-N5 根因映射 — **真兑现**
- ✅ Phase C 5 子维度反馈精准（vocab/syntax/narrative/emotion/dialogue + _lowest）— **真兑现**
- ⚠️ Phase F 私库 89 条 ai-replacement-vocab — Round 19.1 **跨项目隔离修复后真兑现**（之前会污染新项目）
- ⚠️ Phase B polish K/L/M/N 44 词 — 边际收益（200+ 已存）

### 4.2 画面感

- ✅ Phase H 视觉锚点 + 5+1 感官色谱（嗅觉强制） — **真兑现**（捕获 Ch4/8/9 嗅觉零）

### 4.3 追读力

- ✅ Phase X1 reader-critic <75 全卷 P0 — **真兑现**（Ch3=62/Ch4=58 这种首稿低分以后无法 commit）
- ✅ Phase X1B 前 5 章写前自检 — Round 19.1 **dead spec 根治后真兑现**（5 类自检前置阻止"金手指披露突兀/编号无铺垫/爽点未兑现"）
- ✅ Phase I Ch1 追读契约 A/B/C — 真兑现（Ch1 重写或新书首章）
- ✅ Phase G 4 类钩子 + H25 跨章疲劳检测 — 真兑现（11 章已回填 + Ch12 起强制输出）
- ⚠️ Phase E 跨卷感知 — get-recent-meta CLI 真用，但是否真改进 plan 待 Ch12-13 实写验证

### 4.4 跨项目可移植

- ✅ Round 19.1 P0-1 后**新项目（《画山海》/新作）开干 Round 19 全部 9 个 Phase 自动生效**
- ✅ 私库每项目专属，不污染
- ✅ 新项目接入指南 MIGRATION_NEW_PROJECT.md 有详细 step-by-step

---

## 5. Round 19 + Round 19.1 总成果

| 维度 | 末态 |
|---|---|
| **Commits** | Round 19 (15) + Round 19.1 (待 commit) |
| **Phase 实施** | A/I/X1/F/H/B/E/C/G + Phase 7 + Phase D 决策 + Round 19.1 P0×3 |
| **新文件** | 18 个（5 references + 4 私库 schema seed + extractor + 6 docs + MIGRATION 指南 + 测试报告） |
| **改动文件** | 12 个 agent / skill / script |
| **修复 bug** | RCA 12 类 top 根因覆盖 + Round 19.1 P0×3 + Phase A 复审 fenced + X1 复审 fallback |
| **跨项目可移植** | ✅ 已根治 |
| **hygiene 通过** | 27/0/0/0（含 H25） |
| **保留 18 轮 102 commits** | ✅ 全部保留 |
| **拒绝 upstream** | DO NOT MERGE 10 类 |

---

## 6. 发布决策

✅ **可以发布**到 `origin = https://github.com/XuanRanL/webnovelwriter.git`（用户的 fork，不是上游 lingfengQAQ）

**发布前 checklist**：

- [x] P0×3 全部根治
- [x] 12 项端到端测试全过
- [x] 末世重生本作数据从 fork 共享迁移到项目本地（gitignore，不会推到 GitHub）
- [x] fork 共享 CSV 清空到仅表头（plugin schema seed）
- [x] 新项目接入指南 MIGRATION_NEW_PROJECT.md 完整
- [x] hygiene + preflight + sync-cache 全绿
- [x] git remote -v 确认 origin = XuanRanL/webnovelwriter ✅

---

## 7. Round 20 待办（不阻断本次发布）

P1 修补未来批次处理：

- P1-1 reader-naturalness verdict schema 内部冲突
- P1-2 context-agent.md 硬编码 "本作（末世重生）" 字面（影响新项目阅读）
- P1-3 ai-replacement-vocab.csv "好样本"列填的是 fix_hint（extractor 兜底改进）
- P1-4 canon-violation-traps.csv 禁区类型映射错位
- P1-5 CUSTOMIZATIONS.md 缺 DO NOT MERGE 引用
- P1-6 strong-chapter-end-hooks 仅 3 条（写到 Ch20+ 自然增长）
- P1-7 hook_close.strength 启发式回填全 80（Ch12+ checker 真填后自动修）
- 文档不一致（v3 计划 vs 测试报告 vs Phase 1.1 commits 数）

Round 20 触发条件：Ch12-13 实写后 ROI 报告显示某个 P1 真的影响数据 → 立项修。
