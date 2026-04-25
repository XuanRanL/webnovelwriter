# 读者视角质量提升计划 v3 · 终版

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把"提升小说质量"重定义为读者只在意的三件事——**自然度**（不像 AI）/ **画面感**（具象、感官、节奏）/ **追读力**（情绪欠债 + 悬念 + 爽点节奏）；所有改动必须直接映射到这 3 件事的至少 1 件，否则不做。

**Architecture:** 三条并行注入链——
1. 起草前预防层（Step 2 Anti-AI 即时纠正 + 首章追读契约 + 画面感子规则）
2. 审查精准化层（reader-naturalness 5 子维度 / prose-quality 视觉子维度 / reader-pull 4 类钩子分类）
3. 跨章趋势 + 自建私库回灌层（4 张 CSV：AI 替代词 / 强钩子模板 / earned-vs-forced / 设定禁区）

不动 13-checker 评分体系 / 14 外审 / workflow_manager / state.json 真源；所有新增都是**旁路读取 + 子规则补强 + 现有 CLI 扩展**。

**Tech Stack:** Python 3.11；fork ↔ plugin cache 双向同步（`webnovel.py sync-cache`）；既有 hygiene_check 24+ H 项；13 checker（含 reader-naturalness / reader-pull / prose-quality / consistency）已部署；末世重生项目 11 章 polish_reports + naturalness/consistency/pacing/emotion 等 13 类 tmp JSON 已积累作为私库素材；state_manager.py 已有 `update --set-checker-score / --set-chapter-meta-field / --append-recheck / --sync-protagonist-display` 子命令架构可直接扩展。

---

## 0 · 标尺、范围、纪律

### 0.1 三件标尺

| 标尺 | 读者实际感受 | fork 现有覆盖 | 缺口 |
|---|---|---|---|
| **自然度** | 不像 AI 写的 | reader-naturalness-checker（事后退稿）+ polish-guide 200+ 高频词库 | 缺起草前预防 + 缺 5 子维度反馈细化 + 缺 11 章 RCA 数据沉淀私库自动回灌 |
| **画面感** | 看得见、闻得到、节奏对 | prose-quality-checker（综合分） | 缺"画面感"子规则（视觉锚点 / 非视觉感官 ≥30% / 抽象动作改写） |
| **追读力** | 想看下一章 | reader-pull-checker（钩子强度 0-100 单数字 + hook_type 已存但只 1 维） | 缺章末钩子 4 分类（信息/情绪/决策/动作） + 跨章趋势 + Ch1 追读契约 A/B/C |

任何"升级"映射不到上面 3 件之一，本计划直接拒绝（包括 upstream story-system / vector / dashboard / token-rewrite 等）。

### 0.2 三类来源 + 互补关系

| 来源 | 用途 | 为什么不冲突 |
|---|---|---|
| **上游借工具**（v6 之前的好东西） | anti-ai-guide 起草预防 / polish-guide K/L/M/N 词库 / reviewer ai_flavor 5 子维度 / plan 跨卷感知 | 这些都是 v5 时期产物，与本地 Round 1-18 评分体系**正交**；upstream 后来 v6 删评分是另一回事 |
| **自建私库**（基于 11 章 RCA） | 4 张自有 CSV：ai-replacement-vocab / strong-chapter-end-hooks / emotion-earned-vs-forced / canon-violation-traps | 全是从已有 tmp/*.json + polish_reports/*.md 派生，零新数据来源 |
| **死磕读者指标**（自创 rubric） | Ch1 追读契约 A/B/C / 章末钩 4 分类 / 画面感 3 子规则 | 全是给现有 checker 加子规则；不动评分主轴 |

### 0.3 ROI 排序与 3 周排程

| 阶段 | Phase | 工作量 | 自然度 | 画面感 | 追读力 |
|---|---|---|:---:|:---:|:---:|
| W1 | 0  基线快照 | 0.5h | 基础 | 基础 | 基础 |
| W1 | A  anti-ai-guide 起草预防 | 1h | ✅ | | |
| W1 | I  Ch1 追读契约 9+3 | 2h | | | ✅ |
| W1 | C  reader-naturalness 5 子维度 | 3h | ✅ | | |
| W1 | **W1 中检**（Ch12 写作 dry-run） | 2h | ✅ | | ✅ |
| W2 | F  4 张私库 CSV + extractor | 8h | ✅ | | ✅ |
| W2 | G  章末钩子 4 分类 + 跨章追踪 | 4h | | | ✅ |
| W2 | B  polish-guide K/L/M/N + 6 句式规则 | 2h | ✅ | | |
| W3 | H  prose-quality 画面感 3 子规则 | 3h | | ✅ | |
| W3 | E  plan 跨卷感知 | 1h | | | ✅ |
| W3 | D  upstream CSV 9 表（条件执行） | 4h | 视干货度 | | |
| W3 | 7  DO NOT MERGE 永久清单 | 0.5h | (元数据) | | |
| W3 | 8  Ch12-13 端到端兑现 | 4h | ✅ | ✅ | ✅ |
| 总 |  | **35h** | | | |

### 0.4 操作纪律（贯穿所有 Phase）

1. **每个 Phase 独立 commit**，message 前缀 `feat(reader-quality): Phase X · ...` 或 `docs(reader-quality): Phase X · ...`
2. **每个改 fork 文件的 Phase 必跑**：
   ```bash
   python -X utf8 webnovel-writer/scripts/data_modules/webnovel.py sync-cache
   python -X utf8 webnovel-writer/scripts/data_modules/webnovel.py preflight
   python -X utf8 末世重生-我在空间里种出了整个基地/.webnovel/hygiene_check.py
   ```
   三条 exit=0 才能 commit
3. **CUSTOMIZATIONS.md 每 Phase 追加一节**（顶部插入），含：upstream commit hash（如有）、改动文件列表 + 行数、验证结论、互补关系说明
4. **严禁 `git merge upstream/master` / `git cherry-pick`** —— upstream 取文件用 `git show upstream/master:<path>` 手动 Read + Write（避开 fork ↔ upstream 文件路径 / 编码 / 命名差异）
5. **严禁手动改 state.json** —— 用 `webnovel.py state update --xxx` 既有或扩展 CLI（feedback_no_manual_state_edits）
6. **正文必须用中文弯引号 U+201C/201D** —— 改 Python / md 也避免 ASCII " 污染（feedback_chinese_quotes）
7. **所有搜索关键词用中文**（feedback_search_in_chinese）
8. **Phase 间不并行实施** —— 上一 Phase commit 通过且 hygiene 绿色才能开下一 Phase；一次一章一 Phase（feedback_no_skip_steps）

### 0.5 验证项目

末世重生-我在空间里种出了整个基地（路径中含中文，bash 注意引号）作为基线项目。Ch1-11 已成稿；Ch12 起所有新机制必须在该项目跑出兑现指标。

### 0.6 背景已查清的环境事实（Phase 设计基于这些）

- chapter_meta key 是**4 位补零字符串**（'0001'-'0011'），不是 '1'-'11'
- checker_scores 的 key 是 **canonical 名（带 -checker 后缀）**：consistency-checker / continuity-checker / ooc-checker / reader-pull-checker / high-point-checker / pacing-checker / dialogue-checker / density-checker / prose-quality-checker / emotion-checker / flow-checker / reader-naturalness-checker / reader-critic-checker + overall（13 个）
- Ch11 已经有 `hook_type='意象钩'` + `hook_content` + `hook_strength='strong'|'weak'` —— 但**和本计划的 4 分类（信息钩 / 情绪钩 / 决策钩 / 动作钩）不同**，需要在 Phase G 平行新增 `hook_close.primary_type` 字段而不是覆盖既有 hook_type
- Ch1 reader-naturalness 已经回填过；Ch5 用了非 canonical 名 'naturalness'/'reader-critic'（缺 -checker 后缀），是历史污点，本计划不修，但 Phase F extractor 要兼容
- state_manager.py main() 的 CLI 注册段在 line 1366-1530；既有子命令 `update --set-checker-score / --set-chapter-meta-field / --append-recheck / --sync-protagonist-display / --add-words` 的注册风格是 `update_parser.add_argument(...)`；新增子维度入口必须延用此风格
- hygiene_check 已有 H1-H24（H22 缺号），新增章末钩子趋势检查用 H25
- reader-naturalness-checker.md 已有 "Ch11 方言血教训" 段（"得味/嗯呐/哎哟"被误判为 false_positive 的历史），改它时**绝对不能覆盖此段**
- post_draft_check.py 已有 ASCII 引号 auto-fix（Round 15.3 Bug #3 已根治），编辑文件后引号问题已自愈，但**手工写文件**仍可能误转 ASCII，多保险一次跑 quote_pair_fix
- 末世重生项目 .webnovel/tmp/ 中 checker JSON 命名有两套历史格式：`{checker}_check_ch{NNNN}.json`（多数）和 `{checker}_ch{NNNN}.json`（Ch9）—— Phase F extractor 必须两种都扫
- upstream HEAD = `1d7c952` (2026-04-25)；main HEAD = `84249bd`；merge-base = `535d60d` (2026-03-23)

---

## 1 · 落地清单

```
webnovel-writer/                                                        # fork 根
├── skills/webnovel-write/
│   ├── SKILL.md                                                        # Modify · A / I / H
│   └── references/
│       ├── anti-ai-guide.md                                            # NEW · A
│       ├── first-chapter-hook-rubric.md                                # NEW · I
│       ├── chapter-end-hook-taxonomy.md                                # NEW · G
│       ├── visual-concreteness-rubric.md                               # NEW · H
│       └── polish-guide.md                                             # Modify · B
├── skills/webnovel-plan/SKILL.md                                       # Modify · E
├── agents/
│   ├── context-agent.md                                                # Modify · A / F
│   ├── reader-naturalness-checker.md                                   # Modify · C / F
│   ├── reader-pull-checker.md                                          # Modify · I / G
│   ├── prose-quality-checker.md                                        # Modify · H
│   ├── consistency-checker.md                                          # Modify · F
│   └── data-agent.md                                                   # Modify · C / G
├── references/private-csv/                                             # NEW · F
│   ├── README.md
│   ├── ai-replacement-vocab.csv
│   ├── strong-chapter-end-hooks.csv
│   ├── emotion-earned-vs-forced.csv
│   └── canon-violation-traps.csv
├── scripts/
│   ├── private_csv_extractor.py                                        # NEW · F
│   ├── data_modules/
│   │   ├── webnovel.py                                                 # Modify · F（私库子命令转发）
│   │   └── state_manager.py                                            # Modify · C / G / E
│   ├── hygiene_check.py                                                # Modify · G（H25）
│   └── polish_cycle.py                                                 # Modify · C（lowest_subdimension 优先）
└── CUSTOMIZATIONS.md                                                   # Modify · 每 Phase

末世重生-我在空间里种出了整个基地/.webnovel/
├── reports/
│   ├── quality_baseline.json                                           # NEW · 0
│   ├── ch12_roi.json                                                   # NEW · 8
│   └── ch13_roi.json                                                   # NEW · 8
└── private_csv/                                                        # 项目本地缓存（提取脚本运行产物，可选）

docs/superpowers/plans/
├── 2026-04-25-reader-quality-uplift-v3-final.md                        # 本文件
├── upstream-snapshot/COMMIT_REF.txt                                    # NEW · 0
└── round19-roi-final-report.md                                         # NEW · 8

ROOT_CAUSE_GUARD_RAILS.md                                               # Modify · 7（DO NOT MERGE 段）
```

---

## Phase 0 · 基线快照（30 min）

### Task 0.1: 锁定 upstream + main commit hash

**Files:**
- Create: `docs/superpowers/plans/upstream-snapshot/COMMIT_REF.txt`

- [ ] **Step 1: 写 commit ref 文件**

```bash
mkdir -p docs/superpowers/plans/upstream-snapshot
{
  echo "=== upstream/master HEAD ===";
  git rev-parse upstream/master;
  git log -1 --format="%H %ai %s" upstream/master;
  echo "";
  echo "=== main HEAD ===";
  git rev-parse main;
  git log -1 --format="%H %ai %s" main;
  echo "";
  echo "=== merge-base ===";
  git merge-base main upstream/master;
  git log -1 --format="%ai %s" $(git merge-base main upstream/master);
} > docs/superpowers/plans/upstream-snapshot/COMMIT_REF.txt
```

- [ ] **Step 2: 验证内容**

Read 该文件，确认包含：upstream HEAD `1d7c952`、main HEAD `84249bd`、merge-base `535d60d`。

### Task 0.2: 提取 Ch1-11 质量基线

**Files:**
- Create: `末世重生-我在空间里种出了整个基地/.webnovel/reports/quality_baseline.json`

- [ ] **Step 1: 跑提取脚本**

```bash
mkdir -p "末世重生-我在空间里种出了整个基地/.webnovel/reports"
python -X utf8 - <<'PY'
import json
from pathlib import Path
proj = Path("末世重生-我在空间里种出了整个基地")
state = json.loads((proj / ".webnovel" / "state.json").read_text(encoding="utf-8"))
metas = state.get("chapter_meta", {})

CANONICAL_KEYS = [
    "consistency-checker","continuity-checker","ooc-checker","reader-pull-checker",
    "high-point-checker","pacing-checker","dialogue-checker","density-checker",
    "prose-quality-checker","emotion-checker","flow-checker",
    "reader-naturalness-checker","reader-critic-checker","overall",
]
LEGACY_ALIASES = {"naturalness":"reader-naturalness-checker","reader-critic":"reader-critic-checker"}

per_chapter = {}
sums = {k: 0 for k in CANONICAL_KEYS}
counts = {k: 0 for k in CANONICAL_KEYS}

for ch_key in sorted(metas.keys()):
    ch_int = int(ch_key)
    if ch_int > 11: continue
    cm = metas[ch_key] or {}
    raw_scores = cm.get("checker_scores") or {}
    norm = {}
    for k, v in raw_scores.items():
        canonical = LEGACY_ALIASES.get(k, k)
        if canonical in CANONICAL_KEYS and isinstance(v, (int, float)):
            norm[canonical] = v
    per_chapter[ch_key] = {
        "scores": norm,
        "hook_type": cm.get("hook_type"),
        "hook_strength": cm.get("hook_strength"),
        "word_count": cm.get("word_count"),
        "narrative_version": cm.get("narrative_version"),
    }
    for k, v in norm.items():
        sums[k] += v; counts[k] += 1

avg = {k: round(sums[k]/counts[k], 2) for k in CANONICAL_KEYS if counts[k]}
out = {
    "captured_at": "2026-04-25",
    "chapters": list(sorted(per_chapter.keys())),
    "per_chapter": per_chapter,
    "avg_ch1_11": avg,
    "counts_ch1_11": counts,
    "polish_rounds_estimate": "见 polish_reports/ch00*.md",
}
target = proj / ".webnovel" / "reports" / "quality_baseline.json"
target.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("[OK] baseline written:", target)
print("avg_overall =", avg.get("overall"))
print("avg_naturalness =", avg.get("reader-naturalness-checker"))
print("avg_prose =", avg.get("prose-quality-checker"))
print("avg_pull =", avg.get("reader-pull-checker"))
PY
```

Expected: 输出 4 个 avg 数字（overall ≈ 88-90, naturalness ≈ 82-88, prose ≈ 86-91, pull ≈ 82-88）。

- [ ] **Step 2: 验证文件**

```bash
ls -la "末世重生-我在空间里种出了整个基地/.webnovel/reports/quality_baseline.json"
python -X utf8 -c "import json; d=json.load(open('末世重生-我在空间里种出了整个基地/.webnovel/reports/quality_baseline.json',encoding='utf-8')); print(json.dumps(d['avg_ch1_11'],ensure_ascii=False,indent=2))"
```

Expected: 14 个 checker（含 overall）的平均分；每个 ≥ 70。

### Task 0.3: Commit 基线

- [ ] **Step 1: 三套验证**

```bash
python -X utf8 webnovel-writer/scripts/data_modules/webnovel.py preflight
python -X utf8 末世重生-我在空间里种出了整个基地/.webnovel/hygiene_check.py
```

两条都 exit=0。

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/plans/upstream-snapshot/COMMIT_REF.txt \
        docs/superpowers/plans/2026-04-25-reader-quality-uplift-v3-final.md \
        "末世重生-我在空间里种出了整个基地/.webnovel/reports/quality_baseline.json"
git commit -m "$(cat <<'EOF'
plan(reader-quality): v3 终版计划 + Ch1-11 质量基线快照

锁 upstream@1d7c952 + main@84249bd 基线；提取 Ch1-11 13 checker 平均分快照供 Phase 8 兑现对比。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase A · anti-ai-guide.md 起草预防层（P0 · 1h · 自然度）

### Task A.1: 引入 anti-ai-guide.md

**Files:**
- Create: `webnovel-writer/skills/webnovel-write/references/anti-ai-guide.md`

- [ ] **Step 1: 抓 upstream 内容到 fork**

```bash
git show upstream/master:webnovel-writer/skills/webnovel-write/references/anti-ai-guide.md \
  > webnovel-writer/skills/webnovel-write/references/anti-ai-guide.md
wc -l webnovel-writer/skills/webnovel-write/references/anti-ai-guide.md
file webnovel-writer/skills/webnovel-write/references/anti-ai-guide.md
```

Expected: 74 行，UTF-8 (no BOM)。

- [ ] **Step 2: 末尾追加本地接入说明（用 Edit 追加，不覆盖）**

通过 Edit 工具，把文件末尾最后一行（"坏节奏特征" 段最后一句）后面追加：

```markdown

---

## 本地 fork 接入（Round 19 / 5.6.0）

- **加载时机**：Step 2 起草正文前，由 SKILL.md Step 2 references 列表加载
- **与 polish-guide.md 的关系**：本文件是**起草期预防**（8 倾向 + 即时检查 + 替代速查表）；polish-guide 是**polish 期检测+修复**（7 层规则、200+ 高频词库、anti_ai_force_check）。二者互补，不取代
- **预期效果**：Ch12+ reader-naturalness-checker 首稿评分从 78-85 → 88-95，polish 周期数从 2-3 → 1-2 轮
- **不引入的 upstream 配套**：upstream `docs/specs/2026-04-03-ai-writing-quirks.md`（148 行 6 层 60+ 癖好全景图）暂不引入，避免与本文件 + polish-guide 冗余；如需扩展，往 `references/private-csv/ai-replacement-vocab.csv` 沉淀（Phase F）
```

- [ ] **Step 3: 引号扫描自愈（防 Edit 转 ASCII）**

```bash
python -X utf8 webnovel-writer/scripts/quote_pair_fix.py --ascii-to-curly \
  webnovel-writer/skills/webnovel-write/references/anti-ai-guide.md
```

Expected: 报告 0 处需要修复，或自动修复后再次 0 处。

### Task A.2: SKILL.md Step 2 加载点

**Files:**
- Modify: `webnovel-writer/skills/webnovel-write/SKILL.md`

- [ ] **Step 1: 定位 Step 2 references 加载行**

```bash
grep -n "core-constraints.md\|style-adapter.md\|references/" webnovel-writer/skills/webnovel-write/SKILL.md | head -15
```

记录 `references/style-adapter.md` 出现的行号。

- [ ] **Step 2: 用 Edit 在 style-adapter.md 之后追加 anti-ai-guide.md 一行**

把（具体格式以 grep 输出为准）：
```
- references/style-adapter.md
```
替换为：
```
- references/style-adapter.md
- references/anti-ai-guide.md（Round 19 · Step 2 起草前消费 · 8 倾向 + 即时检查 + 替代速查表 · 与 polish-guide 检测层互补）
```

### Task A.3: context-agent 创作执行包注入 6 条 Anti-AI 提醒

**Files:**
- Modify: `webnovel-writer/agents/context-agent.md`

- [ ] **Step 1: 定位核心参考段**

```bash
grep -n "Taxonomy\|Genre Profile\|核心参考" webnovel-writer/agents/context-agent.md | head -5
```

- [ ] **Step 2: 在核心参考列表追加 anti-ai-guide 引用**

在 "Genre Profile" 行之后追加：
```
- **Anti-AI 起草预防**: `${CLAUDE_PLUGIN_ROOT}/skills/webnovel-write/references/anti-ai-guide.md`（Round 19 · Step 2 起草前消费 · 8 倾向 + 即时检查 + 替代速查表）
```

- [ ] **Step 3: 在创作执行包 writing_guidance 输出段强制注入 6 条提醒**

```bash
grep -n "writing_guidance\|风格指导\|constraints" webnovel-writer/agents/context-agent.md | head -10
```

定位输出 schema 描述段，在 `writing_guidance` 对象描述后追加（如该段是表格或 JSON 示例，则在示例后追加说明段）：

```markdown
### Round 19 新增 · Anti-AI 提醒（writing_guidance.constraints 必含至少 6 条）

每章创作执行包的 `writing_guidance.constraints` 字段**必须包含以下 6 条具体提醒**（缺任意 1 条 → context-agent 自检 fail）：

1. 删段末感悟句，留余味（避免起因→经过→结果→感悟四段闭环）
2. 删万能副词"缓缓/淡淡/微微/轻轻"，换具体动作或前置动作
3. 情绪用生理反应+微动作（如"指节捏得发白""舌尖尝到铁锈味"），禁止"他感到X"
4. 角色专属微动作（咬笔帽=焦虑、拧手表=不耐烦），禁止全员"瞳孔微缩"
5. 章末禁止安全着陆（冲突完美解决），留至少 1 个未解决的问题
6. 展示后不解释（删"他显然很生气"），信任读者

完整 8 倾向 + 替代速查表 + 5 即时检查见 `${CLAUDE_PLUGIN_ROOT}/skills/webnovel-write/references/anti-ai-guide.md`，writer 在 Step 2 起草前必须 Read 一次。
```

### Task A.4: sync + verify + commit

- [ ] **Step 1: 三套验证**

```bash
python -X utf8 webnovel-writer/scripts/data_modules/webnovel.py sync-cache
python -X utf8 webnovel-writer/scripts/data_modules/webnovel.py preflight
python -X utf8 末世重生-我在空间里种出了整个基地/.webnovel/hygiene_check.py
```

三条 exit=0。

- [ ] **Step 2: CUSTOMIZATIONS.md 顶部插入 Phase A 段**

在 `webnovel-writer/CUSTOMIZATIONS.md` line 8（`---`）之后、line 10（`## [2026-04-24...`）之前 Edit 插入：

```markdown
## [2026-04-25 · Round 19 Phase A] anti-ai-guide.md 起草预防层

upstream@f774f2b 引入 Step 2 起草前 Anti-AI 预防 reference。本地全程缺"起草前预防"层，AI 腔靠 polish_cycle 反复修。

### 变更摘要

| # | 文件 | 改动 | 行数 |
|---|------|------|------|
| 1 | `skills/webnovel-write/references/anti-ai-guide.md` | NEW · upstream 1:1 + 本地接入说明 | +89 |
| 2 | `skills/webnovel-write/SKILL.md` | Step 2 references 列表加载 | +1 |
| 3 | `agents/context-agent.md` | 核心参考 + writing_guidance.constraints 6 条硬注入 | +9 |

### 互补关系（重要）

| 时机 | 文件 | 职责 |
|------|------|------|
| Step 2 起草前 | `anti-ai-guide.md`（Round 19 NEW） | 预防 · 8 倾向 + 即时检查 + 替代速查表 |
| Step 4 polish | `polish-guide.md`（Round 1-18 累计 616 行） | 检测+修复 · 7 层规则、200+ 高频词库、anti_ai_force_check |

### 预期效果

- Ch12+ reader-naturalness-checker 首稿评分从 78-85 → 88-95
- polish 周期数从 2-3 → 1-2 轮
- 与本地 polish-guide.md / reader-naturalness-checker 的 11 章历史数据无冲突（纯加载新 reference）

### 验证

- preflight + hygiene + sync-cache 全绿
- Ch12 写作首稿 AI 签名命中数 vs Ch11（基线 见 reports/quality_baseline.json）：**待 Ch12 完成 polish 后回填**

---

```

- [ ] **Step 3: Commit**

```bash
git add webnovel-writer/skills/webnovel-write/references/anti-ai-guide.md \
        webnovel-writer/skills/webnovel-write/SKILL.md \
        webnovel-writer/agents/context-agent.md \
        webnovel-writer/CUSTOMIZATIONS.md
git commit -m "$(cat <<'EOF'
feat(reader-quality): Phase A · anti-ai-guide.md 起草预防层

upstream@f774f2b · 74 行 8 倾向 + 即时检查 + 替代速查表 · Step 2 起草前消费
与 polish-guide.md 检测层互补，不取代既有 7 层 + 200+ 词库
context-agent writing_guidance.constraints 强制 6 条注入

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase I · Ch1 追读契约 9+3 rubric（P0 · 2h · 追读力）

### Task I.1: 写 first-chapter-hook-rubric.md

**Files:**
- Create: `webnovel-writer/skills/webnovel-write/references/first-chapter-hook-rubric.md`

- [ ] **Step 1: 用 Write 创建文件，全文如下**

```markdown
---
name: first-chapter-hook-rubric
purpose: 第 1 章专属"读者 3 秒决定追读"硬规则，加在 Round 10 既有 9 项严格 rubric（feedback_round10_first_chapter_rubric.md）之上
---

# 第 1 章追读契约 rubric（Round 19）

> **核心 insight**：网文平台读者在第 1 章前 300 字决定弃读还是追读。Ch1 必须签下"情绪契约"——告诉读者继续读能拿到什么。

## 与既有规则的关系

- **Round 10 既有 9 项严格规则**（金手指时序 / 大纲兑现 / 核心悬念保护 / 认知载入 / distress 具身 / 反派博弈 等）—— 偏向"安全检查"，本文件**不取代**
- **Round 19 新增 3 项追读契约**（A 首句钩 / B 第 1 段承诺 / C 300 字内触发器）—— 偏向"读者承诺信号"，本文件提供
- 综合判定：9 项严格规则 + 3 项追读契约 全过 → reader-pull-checker 给 Ch1 至少 88 分

## Round 19 新增 3 项追读契约规则

### A. 首句钩（critical）

第 1 章第 1 句**必须**含以下信号至少 1 项：

| 信号 | 示例 |
|---|---|
| 冲突信号 | 她举起斧头时，门外的笑声还在持续。 |
| 反差信号 | 病房 305 号的男人已经死了七天，但今天他终于决定起床。 |
| 悬念信号 | 第三次，林夏又看见了那扇不该存在的门。 |

**禁止**（命中其一 → critical issue, blocking=true）：

- 天气描写开头（"今天阳光明媚" / "雨从清晨就开始下"）
- 姓名介绍开头（"林夏，二十六岁，开发部程序员"）
- 时代背景介绍开头（"故事发生在 2099 年" / "末世第七年"）
- 时间标记开头（"今天是 X 月 X 日"）
- 任何说明性 / 描述性首句

### B. 第 1 段=承诺（high）

第 1 段（≤ 200 字）结束前**必须**给读者"这书会爽在哪"的信号至少 1 条：

| 信号类型 | 含义 | 示例 |
|---|---|---|
| 反差身份 | 弱者→强者 / 普通人→天选 / 失败者→翻身 | 这个被妹妹嘲笑半生的废物，今天怀里揣着一份能让全家闭嘴的体检报告。 |
| 待解核心冲突 | 仇 / 谜 / 限期 / 不可能任务 | 她离丈夫死亡时间还剩二十八天。 |
| 核心动机 | 为什么这事必须做 | 答应母亲的事，今天必须见血。 |

**禁止**：

- 第 1 段全是环境描写或心理活动
- 第 1 段不暗示卖点
- 第 1 段读完读者还不知道主角面对什么

### C. 300 字内"金手指或核心冲突触发器"（high）

正文开头 300 字内**必须**出现：

- 金手指首次显形（哪怕是部分预兆，如"掌心一热" / "脑海中传来声音" / 时间倒流闪回）
- 或核心冲突触发器（杀手登门 / 末世广播响起 / 系统绑定 / 倒计时启动 / 重要 NPC 出场）

**禁止**：

- 开头 500+ 字全是回忆 / 日常 / 内心独白
- 金手指延迟到 1000 字后
- 主角在前 500 字没有"将要发生什么大事"的暗示

## reader-pull-checker 评 Ch1 时的强制流程

```
chapter == 1 →
  1. 走 Round 10 既有 9 项严格 rubric（feedback_round10_first_chapter_rubric.md）
  2. 走 Round 19 新增 A/B/C（本文件）
  3. 综合 verdict 规则：
     - A 不通过 → critical issue, blocking=true, verdict=REWRITE_RECOMMENDED
     - B 不通过 → high issue
     - C 不通过 → high issue
     - A 通过 + B/C 任一通过 → 至少 PASS
     - A/B/C 全过 + 9 项严格全过 → 期望 ≥ 88
```

## 跨章衔接（Ch2-3 弱版本）

第 2-3 章每章末必须留至少 1 个由第 1 章悬念衍生的子悬念（保护"开篇炸街中段平淡"陷阱）：

- Ch2 末必须有"Ch1 主悬念的新进展或新分支"
- Ch3 末必须有"Ch1 卖点的第一次小兑现 + 抛出更大悬念"
- reader-pull-checker 评 Ch2/Ch3 时检查此条款，缺失 → medium warn

## 自检表（reader-pull-checker 必须输出）

| 项 | 通过条件 | 不通过扣分 |
|---|---|---|
| A 首句钩 | 含冲突/反差/悬念信号之一，无 5 项禁止 | -10（critical） |
| B 第 1 段承诺 | 含反差身份/核心冲突/核心动机之一 | -8（high） |
| C 300 字内触发器 | 金手指或核心冲突触发器 | -10（high） |
| Ch2/Ch3 跨章衔接 | 末段含 Ch1 悬念子分支 | -5（medium） |
```

- [ ] **Step 2: 引号扫描自愈**

```bash
python -X utf8 webnovel-writer/scripts/quote_pair_fix.py --ascii-to-curly \
  webnovel-writer/skills/webnovel-write/references/first-chapter-hook-rubric.md
```

### Task I.2: reader-pull-checker 接入 first-chapter rubric

**Files:**
- Modify: `webnovel-writer/agents/reader-pull-checker.md`

- [ ] **Step 1: 找到第 1 章特殊处理段或评分维度段**

```bash
grep -n "第 1 章\|chapter == 1\|首章\|Ch1\|first" webnovel-writer/agents/reader-pull-checker.md | head -10
```

- [ ] **Step 2: 在评分维度段末尾追加 Round 19 段**

```markdown
### Round 19 新增 · 第 1 章追读契约（参 first-chapter-hook-rubric.md）

仅当 `chapter == 1` 时强制走 `${CLAUDE_PLUGIN_ROOT}/skills/webnovel-write/references/first-chapter-hook-rubric.md` 的 A/B/C 三项追读契约：

- A 首句钩缺失（含冲突/反差/悬念之一 OR 命中 5 项禁止之一） → critical issue, blocking=true
  fix_hint = "首句必须含冲突/反差/悬念信号之一；禁止天气/姓名/时代背景/时间标记/纯说明开头"
- B 第 1 段承诺缺失 → high issue
  fix_hint = "第 1 段必须暗示卖点：反差身份 / 核心冲突 / 核心动机 三选一"
- C 300 字内触发器缺失 → high issue
  fix_hint = "300 字内必须显形金手指或核心冲突触发器"

任何 A 触发 → verdict=REWRITE_RECOMMENDED；2 个 B/C 同时触发也升级为 REWRITE_RECOMMENDED。

### Round 19 新增 · Ch2/Ch3 跨章衔接（弱版本）

仅当 `chapter in (2, 3)` 时检查：

- Ch2 末段必须含 Ch1 主悬念的新进展或新分支 → 缺失 medium warn
- Ch3 末段必须含 Ch1 卖点的第一次小兑现 + 抛出更大悬念 → 缺失 medium warn

证据通过 Read Ch1 末段 + 当前章末段 200 字对比判定。
```

### Task I.3: SKILL.md 加首章 rubric 加载点

**Files:**
- Modify: `webnovel-writer/skills/webnovel-write/SKILL.md`

- [ ] **Step 1: 找第 1 章特殊处理段**

```bash
grep -n "chapter == 1\|首章\|Ch1\|第 1 章\|first.chapter" webnovel-writer/skills/webnovel-write/SKILL.md | head -5
```

- [ ] **Step 2: 在该段（或紧挨 Step 2 references 列表）追加加载条件**

```
- 当 chapter == 1：额外加载 `references/first-chapter-hook-rubric.md`（Round 19 · 追读契约 A/B/C 三项硬规则 + Ch2/Ch3 跨章衔接弱版）
```

### Task I.4: sync + verify + commit

- [ ] **Step 1: 三套验证**（同 A.4）

- [ ] **Step 2: CUSTOMIZATIONS.md 顶部插入 Phase I 段**

```markdown
## [2026-04-25 · Round 19 Phase I] Ch1 追读契约 9+3 rubric

网文平台第 1 章前 300 字决定弃读率。Round 10 已加 9 项严格 rubric（feedback_round10_first_chapter_rubric.md，偏"安全检查"），Round 19 补 3 项"读者承诺信号"。

| # | 文件 | 改动 | 行数 |
|---|------|------|------|
| 1 | `skills/webnovel-write/references/first-chapter-hook-rubric.md` | NEW · A/B/C 三项追读契约 + Ch2/Ch3 跨章弱版 | +90 |
| 2 | `agents/reader-pull-checker.md` | 第 1 章强制走 A/B/C；A → REWRITE | +20 |
| 3 | `skills/webnovel-write/SKILL.md` | chapter==1 加载 first-chapter-hook-rubric | +1 |

### 三项追读契约

- A 首句钩（critical）：冲突 / 反差 / 悬念信号三选一；禁天气 / 姓名 / 时代背景 / 时间标记 / 纯说明开头
- B 第 1 段承诺（high）：反差身份 / 核心冲突 / 核心动机三选一
- C 300 字内触发器（high）：金手指或核心冲突触发器

### 预期效果

- Ch1 完读率显著提升（网文平台命门指标）
- 不会出现"前 1000 字全是回忆 / 日常"
- 与 Round 10 9 项严格规则叠加 → Ch1 reader-pull-checker ≥ 88

---

```

- [ ] **Step 3: Commit**

```bash
git add webnovel-writer/skills/webnovel-write/references/first-chapter-hook-rubric.md \
        webnovel-writer/agents/reader-pull-checker.md \
        webnovel-writer/skills/webnovel-write/SKILL.md \
        webnovel-writer/CUSTOMIZATIONS.md
git commit -m "$(cat <<'EOF'
feat(reader-quality): Phase I · Ch1 追读契约 9+3 rubric

A 首句钩（critical · 5 项禁止）/ B 第 1 段承诺 / C 300 字内触发器
+ Ch2/Ch3 跨章衔接弱版（medium warn）
reader-pull-checker chapter==1 强制走，A 触发 REWRITE_RECOMMENDED

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase C · reader-naturalness-checker 升级 5 子维度（P1 · 3h · 自然度）

### Task C.1: reader-naturalness-checker.md 升级到 5 子维度

**Files:**
- Modify: `webnovel-writer/agents/reader-naturalness-checker.md`

- [ ] **Step 1: 备份**

```bash
cp webnovel-writer/agents/reader-naturalness-checker.md \
   webnovel-writer/agents/.reader-naturalness-checker.md.bak_pre_phase_C
```

注：以 `.` 开头的备份文件须确认 `.gitignore` 排除（grep `\.bak` webnovel-writer/.gitignore 确认）。

- [ ] **Step 2: 在评分段插入 5 子维度 rubric（保留 Ch11 方言血教训段）**

```bash
grep -n "评分\|score\|Ch11\|血教训\|方言" webnovel-writer/agents/reader-naturalness-checker.md | head -10
```

定位评分段，**在评分段末尾追加**（不替换既有内容，保留 Ch11 方言血教训段不变）：

```markdown
## Round 19 升级 · 5 子维度结构化评分

> 兼容契约：本升级**新增** `subdimensions` 输出对象 + `lowest_subdimension` 字段；主分数 `reader_naturalness` 仍输出（计算方式改为 5 子维度算术平均），向下兼容 polish_cycle / state_manager / chapter_meta 既有读取路径。

### 子维度 1: 词汇层（vocab）

检查项：

- 高频 AI 词汇密度（参 polish-guide K/L/M/N 类，Phase B 后扩充至全集）
- "缓缓/淡淡/微微/轻轻"+动词 在 500 字内 ≥ 3 次
- "眸中闪过""瞳孔微缩""嘴角微扬"等神态模板出现
- 万能副词（缓缓/淡淡/微微/轻轻/静静/默默/悄悄/慢慢/渐渐/暗暗）整章密度

扣分：个别命中 -3 / 处；密集（5+ 处） -10。子维度上限 100。

### 子维度 2: 句式层（syntax）

检查项：

- "起因→经过→结果→感悟"四段闭环（每段末有感悟句）
- 连续同构句（≥ 3 句主谓宾结构一致）
- 每段以总结句收尾（"他终于明白了" / "由此可见"）
- 同一信息用不同句式重复说 2-3 遍

扣分：闭环 -8；同构句 -5；总结句 -5；重复 -5。

### 子维度 3: 叙事层（narrative）

检查项：

- 节奏匀速（段落信息密度均匀，无快慢）
- "他不知道的是……" "殊不知……" 戏剧性反讽提示
- 章末"安全着陆"（冲突完美解决，无遗留不安感）
- 展示后紧跟解释（动作展示后一句话解释含义）

扣分：匀速 -5；反讽提示 -3；安全着陆 -10；展示后解释 -5。

### 子维度 4: 情感层（emotion）

检查项：

- 情绪标签化（"他感到愤怒" "她非常紧张"）
- 情绪即时切换（无过渡）
- 全员同款反应模板（全员"瞳孔微缩"）

扣分：标签化 -10；即时切换 -5；同款模板 -8。

### 子维度 5: 对话层（dialogue）

检查项：

- 信息宣讲（解释背景而非推进冲突）
- 全员书面语，无口语特征，无个人口癖
- 对白后跟解释性叙述（"他这么说是因为……"）

**与 Ch11 方言血教训的关系**：本子维度的"全员书面语"判定**必须先读** `项目级 references/03-角色口径表.md` / `07-本地化资料包.md` 等设定集中的方言白名单；命中白名单的方言词不算违例（参 reader-naturalness-checker.md 既有方言血教训段）。

扣分：信息宣讲 -10；全员书面（且无方言豁免） -8；解释性叙述 -5。

### 主分数计算

```
reader_naturalness = round(mean(vocab, syntax, narrative, emotion, dialogue), 2)
```

每个子维度独立 0-100 计分（满分 100，扣到 0 截止）。

### 输出 schema 扩展

```json
{
  "checker": "reader-naturalness-checker",
  "chapter": 12,
  "reader_naturalness": 88,
  "subdimensions": {
    "vocab": 92, "syntax": 78, "narrative": 85, "emotion": 90, "dialogue": 95
  },
  "lowest_subdimension": "syntax",
  "verdict": "PASS | NEEDS_POLISH | REWRITE_RECOMMENDED",
  "issues": [
    {
      "subdimension": "syntax",
      "severity": "high",
      "evidence": "...",
      "fix_hint": "..."
    }
  ]
}
```

下游消费：

- `polish_cycle.py` 必须读 `lowest_subdimension`，定向修该子维度（见 Task C.3）
- `data-agent` 必须把 `subdimensions` 落库到 `chapter_meta[NNNN].checker_subdimensions.reader-naturalness-checker`（见 Task C.2）

### 兼容性

- 老 polish_cycle / data-agent 不读 `subdimensions` 时：仍能读到 `reader_naturalness` 主分数，行为不变
- 老 reader-naturalness JSON（无 `subdimensions` 字段）：data-agent Phase F 兼容兜底为空 dict
```

- [ ] **Step 3: 跑引号自愈**

```bash
python -X utf8 webnovel-writer/scripts/quote_pair_fix.py --ascii-to-curly \
  webnovel-writer/agents/reader-naturalness-checker.md
```

### Task C.2: data-agent 落库 subdimensions

**Files:**
- Modify: `webnovel-writer/agents/data-agent.md`

- [ ] **Step 1: 找 chapter_meta 写入段**

```bash
grep -n "chapter_meta\|checker_scores\|set-checker-score" webnovel-writer/agents/data-agent.md | head -10
```

- [ ] **Step 2: 在 set-checker-score 调用段后追加子维度落库**

```markdown
### Round 19 新增 · reader-naturalness 5 子维度落库

读 `tmp/naturalness_check_ch{NNNN}.json` 时（兼容 `naturalness_check_ch{NNNN}_v2.json` / `naturalness_ch{NNNN}.json` 历史命名）：

1. 取 `reader_naturalness` → `set-checker-score --checker reader-naturalness-checker --score N`（既有路径不变）
2. 取 `subdimensions` 对象（5 键 vocab/syntax/narrative/emotion/dialogue）→ 跑：
   ```bash
   python -X utf8 "${SCRIPTS_DIR}/data_modules/webnovel.py" --project-root "${PROJECT_ROOT}" \
     state update --set-checker-subdimensions '{"chapter":N,"checker":"reader-naturalness-checker","subdimensions":{"vocab":92,"syntax":78,"narrative":85,"emotion":90,"dialogue":95}}'
   ```
3. 若 JSON 缺 `subdimensions` 字段（老版 checker 输出）→ 写空 dict `{}` 兜底，不阻断
4. 同时 `lowest_subdimension` 字段也写到 chapter_meta.checker_subdimensions.reader-naturalness-checker._lowest 字段供 polish_cycle 读
```

### Task C.3: state_manager.py 加 --set-checker-subdimensions CLI

**Files:**
- Modify: `webnovel-writer/scripts/data_modules/state_manager.py`

- [ ] **Step 1: 找 update_parser 注册段（line ~1399-1418）**

- [ ] **Step 2: 在 `--append-recheck` 之后追加新参数**

定位：

```python
    update_parser.add_argument(
        "--append-recheck",
        help='JSON: {"chapter":N,"checker":"pacing-checker","before":58,"after":90,"reason":"..."}（追加到 chapter_meta.post_polish_recheck；Step 4.5 选择性复测产物）',
    )
```

在它之后 Edit 追加：

```python
    # Round 19 Phase C · reader-naturalness 5 子维度入口
    update_parser.add_argument(
        "--set-checker-subdimensions",
        help='JSON: {"chapter":N,"checker":"reader-naturalness-checker","subdimensions":{"vocab":92,"syntax":78,"narrative":85,"emotion":90,"dialogue":95}}（写入 chapter_meta.NNNN.checker_subdimensions.{checker}；自动计算 _lowest）',
    )
```

- [ ] **Step 3: 在 update 分发段（line ~1530-1700）追加 dispatch**

定位 `--set-checker-score` 的 dispatch 块（约 line 1637-1680），在其结束（写完 review_metrics 同步那段）后追加：

```python
        # Round 19 Phase C · 子维度入口（与 set-checker-score 平行，不互斥）
        if args.set_checker_subdimensions:
            try:
                payload = json.loads(args.set_checker_subdimensions)
            except Exception as exc:
                emit_error("INVALID_JSON", f"--set-checker-subdimensions JSON 解析失败：{exc}")
                return 1
            ch = payload.get("chapter")
            checker = payload.get("checker")
            subdims = payload.get("subdimensions") or {}
            if not (isinstance(ch, int) and isinstance(checker, str) and isinstance(subdims, dict)):
                emit_error("INVALID_ARG", "--set-checker-subdimensions 需要 chapter(int) + checker(str) + subdimensions(dict)")
                return 1
            ch_key = f"{ch:04d}"
            cm = state.setdefault("chapter_meta", {}).setdefault(ch_key, {})
            csd = cm.setdefault("checker_subdimensions", {})
            checker_subs = {k: v for k, v in subdims.items() if isinstance(v, (int, float))}
            if checker_subs:
                checker_subs["_lowest"] = min(checker_subs, key=lambda k: checker_subs[k] if not k.startswith("_") else 999)
            csd[checker] = checker_subs
            atomic_write_state(state)
            print(json.dumps({"ok": True, "chapter": ch, "checker": checker, "subdimensions": checker_subs}, ensure_ascii=False))
            return 0
```

注：`atomic_write_state` 是 state_manager 既有写入函数；如名字不同（如 `_persist_state`），grep 文件确认实际函数名替换之。

- [ ] **Step 4: 在 update 子命令的"至少一个参数"检查段（line ~1530）追加 --set-checker-subdimensions**

把：
```python
"state update 需要至少一个参数（--strand-dominant / --add-foreshadowing / --resolve-foreshadowing / --set-chapter-meta-field / --sync-protagonist-display / --set-checker-score / --append-recheck / --add-words）",
```
替换为：
```python
"state update 需要至少一个参数（--strand-dominant / --add-foreshadowing / --resolve-foreshadowing / --set-chapter-meta-field / --sync-protagonist-display / --set-checker-score / --append-recheck / --add-words / --set-checker-subdimensions）",
```

- [ ] **Step 5: 烟雾测试**

```bash
python -X utf8 webnovel-writer/scripts/data_modules/webnovel.py \
  --project-root 末世重生-我在空间里种出了整个基地 \
  state update --set-checker-subdimensions '{"chapter":11,"checker":"reader-naturalness-checker","subdimensions":{"vocab":92,"syntax":78,"narrative":85,"emotion":90,"dialogue":95}}'
```

Expected: 输出 `{"ok": true, "chapter": 11, "checker": "reader-naturalness-checker", "subdimensions": {..., "_lowest": "syntax"}}`。

- [ ] **Step 6: 验证落库**

```bash
python -X utf8 -c "
import json
s=json.loads(open('末世重生-我在空间里种出了整个基地/.webnovel/state.json',encoding='utf-8').read())
print(json.dumps(s['chapter_meta']['0011'].get('checker_subdimensions',{}),ensure_ascii=False,indent=2))
"
```

Expected: 看到 `reader-naturalness-checker` 对象含 5 子维度 + `_lowest: 'syntax'`。

### Task C.4: polish_cycle 读 lowest_subdimension 定向修

**Files:**
- Modify: `webnovel-writer/scripts/polish_cycle.py`

- [ ] **Step 1: 找 reader_naturalness 触发 polish 的代码**

```bash
grep -n "reader_naturalness\|reader-naturalness\|polish_target\|lowest" webnovel-writer/scripts/polish_cycle.py | head -10
```

- [ ] **Step 2: 把单一阈值判定升级为子维度定向**

定位形如 `if score < 75: polish_targets.append("reader_naturalness")` 的代码（grep 输出确定具体行）。

替换为：

```python
        # Round 19 Phase C · reader-naturalness 子维度定向 polish
        nat_score = scores.get("reader-naturalness-checker", 100)
        if nat_score < 75:
            sub_obj = (chapter_meta.get("checker_subdimensions", {}) or {}).get("reader-naturalness-checker", {}) or {}
            lowest = sub_obj.get("_lowest")
            if lowest and lowest in ("vocab", "syntax", "narrative", "emotion", "dialogue"):
                polish_targets.append({"checker": "reader-naturalness-checker", "subdimension": lowest, "score": nat_score})
            else:
                polish_targets.append({"checker": "reader-naturalness-checker", "subdimension": None, "score": nat_score})
```

如果 `polish_targets` 既有结构是字符串列表，先扩展容器结构再做以上修改（保持向后兼容：旧字符串 → 新 dict 格式）。

### Task C.5: sync + verify + commit

- [ ] **Step 1: 三套验证**

```bash
python -X utf8 webnovel-writer/scripts/data_modules/webnovel.py sync-cache
python -X utf8 webnovel-writer/scripts/data_modules/webnovel.py preflight
python -X utf8 末世重生-我在空间里种出了整个基地/.webnovel/hygiene_check.py
```

- [ ] **Step 2: CUSTOMIZATIONS.md 顶部插入 Phase C 段**

```markdown
## [2026-04-25 · Round 19 Phase C] reader-naturalness-checker 5 子维度

upstream@5339e83 借鉴：把单数字 reader_naturalness 升级为 5 子维度（vocab / syntax / narrative / emotion / dialogue）。反馈精准定位到子维度后，polish 周期数从 2-3 → 1-2 轮。

| # | 文件 | 改动 |
|---|------|------|
| 1 | `agents/reader-naturalness-checker.md` | 评分段尾追加 5 子维度 rubric + schema 扩展（保留 Ch11 方言血教训段） |
| 2 | `agents/data-agent.md` | Step K 落 checker_subdimensions（兼容老 JSON 缺字段） |
| 3 | `scripts/data_modules/state_manager.py` | `update --set-checker-subdimensions` 新 CLI · 自动计算 _lowest |
| 4 | `scripts/polish_cycle.py` | polish_target 携带 subdimension 字段，polish 定向修 |

### 与 Ch11 方言血教训的关系

子维度 5（dialogue）"全员书面语"判定必须先读项目设定集方言白名单；命中白名单不算违例。维持 reader-naturalness-checker.md 既有 Ch11 血教训段的逻辑。

### 兼容性

- 主分数 reader_naturalness 仍输出（5 子维度算术平均）
- 老 JSON / 老 polish_cycle 不读 subdimensions 时行为不变
- chapter_meta.checker_subdimensions 是新字段，hygiene_check 不会因其缺失报错

### 预期效果

- polish 周期 -1 轮
- polish 修正命中率提升（不再是"地鼠式打"）

---

```

- [ ] **Step 3: Commit**

```bash
git add webnovel-writer/agents/reader-naturalness-checker.md \
        webnovel-writer/agents/data-agent.md \
        webnovel-writer/scripts/data_modules/state_manager.py \
        webnovel-writer/scripts/polish_cycle.py \
        webnovel-writer/CUSTOMIZATIONS.md
git commit -m "$(cat <<'EOF'
feat(reader-quality): Phase C · reader-naturalness 5 子维度

upstream@5339e83 借鉴 · vocab/syntax/narrative/emotion/dialogue
+ state_manager update --set-checker-subdimensions CLI
+ polish_cycle 读 _lowest 定向修
保留 Ch11 方言血教训段；老路径向下兼容

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## 中检 W1 · Ch12 写作 dry-run（2h）

> Phase A/I/C 都改了写作链。开 Phase F 之前必须用 Ch12 实际跑一遍验证三件事：(1) anti-ai-guide 真被 Step 2 加载；(2) Ch1 rubric 不会误伤 Ch12（Ch12 不应该走 first-chapter rubric）；(3) reader-naturalness JSON 出现 subdimensions 字段。

### Task W1.1: 启动 Ch12 写作 + 观察

- [ ] **Step 1: 跑 webnovel-write Ch12 Step 0-3**（不必跑完 Step 4-7，dry-run）

按 `feedback_must_run_full_review.md` 走完整流程到 Step 3 审查报告产出。

- [ ] **Step 2: 验证 anti-ai-guide 加载**

```bash
grep -E "anti-ai-guide|起草前预防|Anti-AI" 末世重生-我在空间里种出了整个基地/.webnovel/context/ch0012_context.json 2>/dev/null | head
```

Expected: writing_guidance.constraints 含至少 6 条 Anti-AI 提醒。

- [ ] **Step 3: 验证 Ch12 不走 Ch1 rubric**

```bash
grep -E "first-chapter\|Round 19.*A.*首句钩" 末世重生-我在空间里种出了整个基地/.webnovel/tmp/reader_pull_ch0012.json 2>/dev/null
```

Expected: 无输出（Ch12 不该触发 first-chapter rubric）。

- [ ] **Step 4: 验证 subdimensions 字段**

```bash
python -X utf8 -c "
import json
p='末世重生-我在空间里种出了整个基地/.webnovel/tmp/naturalness_check_ch0012.json'
try:
    d=json.load(open(p,encoding='utf-8'))
    print('subdimensions:', d.get('subdimensions','MISSING'))
    print('lowest_subdimension:', d.get('lowest_subdimension','MISSING'))
except Exception as e:
    print('SKIP:', e)
"
```

Expected: subdimensions 是 dict 含 5 键，lowest_subdimension 是字符串。
若 reader-naturalness-checker 还没识别新 schema → 回到 Phase C Task C.1 检查 prompt 是否清晰。

### Task W1.2: 不通过则 RCA，通过则继续

- [ ] **Step 1: 写 dry-run 报告**

写 `docs/superpowers/plans/upstream-snapshot/w1-dry-run-report.md`，含：
- anti-ai-guide 是否生效（Y/N + 证据）
- Ch12 走 first-chapter rubric 误判（Y/N）
- subdimensions 落库情况

如果有问题：进 Phase RCA（不计入 Phase F+）。

---

## Phase F · 4 张私库 CSV + 自动提取器（P1 · 8h · 自然度+追读力·核心护城河）

### Task F.1: 设计 4 表 schema + README

**Files:**
- Create: `webnovel-writer/references/private-csv/README.md`
- Create: `webnovel-writer/references/private-csv/ai-replacement-vocab.csv`
- Create: `webnovel-writer/references/private-csv/strong-chapter-end-hooks.csv`
- Create: `webnovel-writer/references/private-csv/emotion-earned-vs-forced.csv`
- Create: `webnovel-writer/references/private-csv/canon-violation-traps.csv`

- [ ] **Step 1: 建目录**

```bash
mkdir -p webnovel-writer/references/private-csv
```

- [ ] **Step 2: 写 README.md**（用 Write 工具创建）

```markdown
# 私库 CSV（Round 19 Phase F · 基于 18 轮 RCA + Ch1-11 实战数据沉淀）

## 设计原则

- **零新数据来源**：全部从 `.webnovel/tmp/*.json` + `.webnovel/polish_reports/*.md` + `.webnovel/audit_reports/*.md` 派生
- **每条带证据**：必有"坏样本"原文引用 + "修复方向"具体 fix_hint
- **跨项目可移植**：4 张表沉淀到 fork 的 `references/private-csv/`，sync-cache 后所有用此 plugin 的项目都自动受益
- **可机读**：reader-naturalness-checker / consistency-checker / writer 都能查表回灌

## 4 张表

| 表 | 用途 | 提取来源 | 标尺映射 |
|---|---|---|---|
| `ai-replacement-vocab.csv` | AI 词→替代词对，writer 起草前查 + reader-naturalness 复测时回查升级 severity | `tmp/naturalness_check_ch*.json` issues | 自然度 |
| `strong-chapter-end-hooks.csv` | reader_pull ≥ 90 章节末段模板，writer 写章末时参考 | `tmp/reader_pull_ch*.json` + 正文末段 | 追读力 |
| `emotion-earned-vs-forced.csv` | emotion-checker 抓到的"earned vs forced"反例 + 正例 | `tmp/emotion_check_ch*.json` issues | 自然度 |
| `canon-violation-traps.csv` | consistency-checker 抓过的设定漏洞 + audit_reports B 层警告 | `tmp/consistency_check_ch*.json` + `audit_reports/*.md` | 追读力（避免读者出戏） |

## schema（所有 4 表共享通用列 + 表特有列）

通用列（必填）：

| 列 | 说明 |
|---|---|
| `编号` | 表前缀-序号（AV-001 / SH-001 / EE-001 / CV-001） |
| `章节` | 提取自第几章（'1'-'11'） |
| `严重度` | critical / high / medium / low |
| `坏样本` | 原文引用，违例文本（≤ 200 字） |
| `好样本` | 替代或正例（≤ 200 字，可空） |
| `修复方向` | 一句话 fix_hint（≤ 120 字） |
| `源RCA` | 关联 CUSTOMIZATIONS.md Round 编号（可空） |

表特有列：

- `ai-replacement-vocab.csv` 加 `子维度`（vocab / syntax / narrative / emotion / dialogue）
- `strong-chapter-end-hooks.csv` 加 `钩子类型`（信息钩 / 情绪钩 / 决策钩 / 动作钩）+ `章节分数`
- `emotion-earned-vs-forced.csv` 加 `情感类型`（earned / forced）
- `canon-violation-traps.csv` 加 `禁区类型`（设定矛盾 / 时间线漂移 / 关系漂移 / 战力越权）

## 编码

UTF-8 with BOM；行尾 LF；CSV 逗号分隔；含中文 / 引号字段必须用双引号包裹。

## 维护

- `scripts/private_csv_extractor.py` 是唯一自动入库路径
- 手工追加条目走 `webnovel.py private-csv --append` 走相同 schema 验证（Phase F.3 实现）
- 严禁手编辑 CSV 文件破坏 BOM / 行尾 / 编号唯一性
```

- [ ] **Step 3: 4 张 CSV 写表头行（空数据）**

每张文件写仅一行表头（含 BOM）：

```bash
python -X utf8 - <<'PY'
import csv
from pathlib import Path

HEADERS = {
    "ai-replacement-vocab": ["编号","章节","严重度","坏样本","好样本","子维度","修复方向","源RCA"],
    "strong-chapter-end-hooks": ["编号","章节","严重度","坏样本","好样本","钩子类型","章节分数","修复方向","源RCA"],
    "emotion-earned-vs-forced": ["编号","章节","严重度","坏样本","好样本","情感类型","修复方向","源RCA"],
    "canon-violation-traps": ["编号","章节","严重度","坏样本","好样本","禁区类型","修复方向","源RCA"],
}

base = Path("webnovel-writer/references/private-csv")
for name, hdr in HEADERS.items():
    p = base / f"{name}.csv"
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(hdr)
    print("[OK]", p)
PY
```

- [ ] **Step 4: 验证 BOM**

```bash
for f in webnovel-writer/references/private-csv/*.csv; do
  echo -n "$f: "
  head -c 3 "$f" | xxd | head -1
done
```

Expected: 每个文件开头是 `efbbbf`（UTF-8 BOM）。

### Task F.2: 写自动提取脚本

**Files:**
- Create: `webnovel-writer/scripts/private_csv_extractor.py`

- [ ] **Step 1: Write 脚本（完整代码 ~270 行）**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
私库 CSV 自动提取器（Round 19 Phase F）

输入：项目 .webnovel/tmp/*.json + .webnovel/polish_reports/*.md + .webnovel/audit_reports/*.md
输出：webnovel-writer/references/private-csv/*.csv 追加新条目（不重复）

用法:
    python private_csv_extractor.py --project 末世重生-我在空间里种出了整个基地 \
                                    --table ai-replacement-vocab \
                                    --chapters 1-11 \
                                    [--output-dir webnovel-writer/references/private-csv]
"""
from __future__ import annotations
import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

CSV_HEADERS = {
    "ai-replacement-vocab": ["编号","章节","严重度","坏样本","好样本","子维度","修复方向","源RCA"],
    "strong-chapter-end-hooks": ["编号","章节","严重度","坏样本","好样本","钩子类型","章节分数","修复方向","源RCA"],
    "emotion-earned-vs-forced": ["编号","章节","严重度","坏样本","好样本","情感类型","修复方向","源RCA"],
    "canon-violation-traps": ["编号","章节","严重度","坏样本","好样本","禁区类型","修复方向","源RCA"],
}

PREFIX = {
    "ai-replacement-vocab": "AV",
    "strong-chapter-end-hooks": "SH",
    "emotion-earned-vs-forced": "EE",
    "canon-violation-traps": "CV",
}

# 历史命名兼容（Ch9 用 {checker}_ch{NNNN}.json，多数用 {checker}_check_ch{NNNN}.json）
def _candidate_paths(tmp: Path, checker: str, ch: int) -> List[Path]:
    patterns = [
        f"{checker}_check_ch{ch:04d}.json",
        f"{checker}_check_ch{ch:04d}_v2.json",
        f"{checker}_ch{ch:04d}.json",
        f"{checker}_recheck_ch{ch:04d}.json",
    ]
    return [tmp / p for p in patterns]

def _load_json(p: Path) -> Optional[dict]:
    if not p.exists(): return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

def _trunc(s: str, n: int = 200) -> str:
    if not s: return ""
    s = str(s).strip().replace("\n", " ").replace("\r", " ")
    return s[:n]

def load_existing(csv_path: Path) -> List[Dict[str, str]]:
    if not csv_path.exists():
        return []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def next_id(prefix: str, rows: List[Dict[str, str]]) -> str:
    nums = []
    for r in rows:
        m = re.match(rf"^{prefix}-(\d+)$", r.get("编号", ""))
        if m:
            nums.append(int(m.group(1)))
    n = (max(nums) + 1) if nums else 1
    return f"{prefix}-{n:03d}"

def is_duplicate(new_row: Dict[str, str], existing: List[Dict[str, str]]) -> bool:
    bs = (new_row.get("坏样本") or "").strip()
    ch = str(new_row.get("章节") or "").strip()
    if not bs: return False
    for r in existing:
        if r.get("章节", "").strip() == ch and (r.get("坏样本") or "").strip() == bs:
            return True
    return False

# --- Extractors ---

def extract_ai_replacement_vocab(project: Path, chapters: range) -> List[Dict[str, str]]:
    rows = []
    tmp = project / ".webnovel" / "tmp"
    for ch in chapters:
        for p in _candidate_paths(tmp, "naturalness", ch):
            data = _load_json(p)
            if not data: continue
            for issue in (data.get("issues") or []):
                if not isinstance(issue, dict): continue
                cat = (issue.get("category") or "").lower()
                sub = (issue.get("subdimension") or issue.get("subcategory") or "").lower()
                if cat not in ("ai_flavor","ai","naturalness") and sub not in ("vocab","syntax","narrative","emotion","dialogue"):
                    continue
                rows.append({
                    "章节": str(ch),
                    "严重度": issue.get("severity","medium"),
                    "坏样本": _trunc(issue.get("evidence",""), 200),
                    "好样本": _trunc(issue.get("fix_hint",""), 200),
                    "子维度": sub or "vocab",
                    "修复方向": _trunc(issue.get("fix_hint",""), 120),
                    "源RCA": "",
                })
    return rows

def extract_strong_chapter_end_hooks(project: Path, chapters: range) -> List[Dict[str, str]]:
    rows = []
    tmp = project / ".webnovel" / "tmp"
    text_dir = project / "正文"
    for ch in chapters:
        score = None; hook_type = None; data = None
        for p in _candidate_paths(tmp, "reader_pull", ch):
            data = _load_json(p)
            if data: break
        if not data: continue
        score = data.get("reader_pull") or data.get("score") or 0
        try: score = int(score)
        except: continue
        if score < 90: continue
        # hook_type 从 reader_pull JSON 取 hook_close.primary_type，再降级到 hook_type，再到推断
        hc = data.get("hook_close") or {}
        hook_type = hc.get("primary_type") or data.get("hook_type") or "信息钩"
        candidates = list(text_dir.glob(f"第{ch:04d}章*.md")) + list(text_dir.glob(f"第{ch}章*.md"))
        if not candidates: continue
        text = candidates[0].read_text(encoding="utf-8", errors="ignore")
        last_chunk = text.strip().rstrip("```").strip().split("\n\n")[-1][-200:]
        rows.append({
            "章节": str(ch),
            "严重度": "low",
            "坏样本": "",
            "好样本": _trunc(last_chunk, 200),
            "钩子类型": hook_type,
            "章节分数": str(score),
            "修复方向": f"参考章 {ch} 末段（reader_pull={score}）",
            "源RCA": "",
        })
    return rows

def extract_emotion_earned_forced(project: Path, chapters: range) -> List[Dict[str, str]]:
    rows = []
    tmp = project / ".webnovel" / "tmp"
    for ch in chapters:
        for p in _candidate_paths(tmp, "emotion", ch):
            data = _load_json(p)
            if not data: continue
            for issue in (data.get("issues") or []):
                if not isinstance(issue, dict): continue
                blob = (issue.get("subcategory","") + " " + issue.get("description","") + " " + issue.get("evidence","")).lower()
                if "earned" in blob: kind = "earned"
                elif "forced" in blob: kind = "forced"
                else: continue
                rows.append({
                    "章节": str(ch),
                    "严重度": issue.get("severity","medium"),
                    "坏样本": _trunc(issue.get("evidence",""), 200),
                    "好样本": _trunc(issue.get("fix_hint",""), 200),
                    "情感类型": kind,
                    "修复方向": _trunc(issue.get("fix_hint",""), 120),
                    "源RCA": "",
                })
    return rows

def extract_canon_violations(project: Path, chapters: range) -> List[Dict[str, str]]:
    rows = []
    tmp = project / ".webnovel" / "tmp"
    audit = project / ".webnovel" / "audit_reports"
    cat_to_trap = {"setting":"设定矛盾","timeline":"时间线漂移","character":"关系漂移","logic":"战力越权"}
    for ch in chapters:
        for p in _candidate_paths(tmp, "consistency", ch):
            data = _load_json(p)
            if not data: continue
            for issue in (data.get("issues") or []):
                if not isinstance(issue, dict): continue
                cat = (issue.get("category") or "").lower()
                trap = cat_to_trap.get(cat)
                if not trap: continue
                rows.append({
                    "章节": str(ch),
                    "严重度": issue.get("severity","medium"),
                    "坏样本": _trunc(issue.get("evidence",""), 200),
                    "好样本": "",
                    "禁区类型": trap,
                    "修复方向": _trunc(issue.get("fix_hint",""), 120),
                    "源RCA": "",
                })
        # 兼容 audit_reports 的 B 层警告（regex 抓 B-XX warning 段）
        ar = audit / f"ch{ch:04d}_audit.md"
        if ar.exists():
            content = ar.read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r"\bB-(VF|TL|REL|CONS)\b[^\n]*\n[^\n]*\n[^\n]*evidence[:：]\s*([^\n]+)", content):
                trap = {"VF":"战力越权","TL":"时间线漂移","REL":"关系漂移","CONS":"设定矛盾"}.get(m.group(1),"设定矛盾")
                rows.append({
                    "章节": str(ch),
                    "严重度": "medium",
                    "坏样本": _trunc(m.group(2), 200),
                    "好样本": "",
                    "禁区类型": trap,
                    "修复方向": "audit B 层警告 · 参 audit_reports",
                    "源RCA": "",
                })
    return rows

EXTRACTORS = {
    "ai-replacement-vocab": extract_ai_replacement_vocab,
    "strong-chapter-end-hooks": extract_strong_chapter_end_hooks,
    "emotion-earned-vs-forced": extract_emotion_earned_forced,
    "canon-violation-traps": extract_canon_violations,
}

def parse_chapters(s: str) -> range:
    s = s.strip()
    if "-" in s:
        a, b = s.split("-")
        return range(int(a), int(b) + 1)
    return range(int(s), int(s) + 1)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--table", required=True, choices=list(CSV_HEADERS.keys()))
    ap.add_argument("--chapters", required=True, help="e.g. 1-11 or 5")
    ap.add_argument("--output-dir", default="webnovel-writer/references/private-csv")
    args = ap.parse_args()

    project = Path(args.project).resolve()
    if not project.exists():
        print(f"[ERR] project not found: {project}", file=sys.stderr); return 2

    csv_path = Path(args.output_dir) / f"{args.table}.csv"
    headers = CSV_HEADERS[args.table]
    existing = load_existing(csv_path)
    new_rows = EXTRACTORS[args.table](project, parse_chapters(args.chapters))

    added = 0
    final_rows = list(existing)
    for r in new_rows:
        if is_duplicate(r, final_rows): continue
        r["编号"] = next_id(PREFIX[args.table], final_rows)
        for h in headers:
            r.setdefault(h, "")
        final_rows.append(r)
        added += 1

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        for r in final_rows:
            w.writerow({k: r.get(k, "") for k in headers})

    print(f"[OK] {args.table}: +{added} rows (total {len(final_rows)})")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 烟雾测试单表**

```bash
python -X utf8 webnovel-writer/scripts/private_csv_extractor.py \
  --project 末世重生-我在空间里种出了整个基地 \
  --table ai-replacement-vocab --chapters 1-11
```

Expected: 输出 `[OK] ai-replacement-vocab: +N rows (total N+1)`，N ≥ 5（11 章 reader-naturalness 报告应有 ai_flavor 类 issues）。

- [ ] **Step 3: 4 表全跑**

```bash
for t in ai-replacement-vocab strong-chapter-end-hooks emotion-earned-vs-forced canon-violation-traps; do
  python -X utf8 webnovel-writer/scripts/private_csv_extractor.py \
    --project 末世重生-我在空间里种出了整个基地 \
    --table $t --chapters 1-11
done
ls -la webnovel-writer/references/private-csv/
wc -l webnovel-writer/references/private-csv/*.csv
```

Expected: 4 张表各自 ≥ 表头 + 1 行；总行数能反映 11 章 RCA 数据规模（预计 30-100 条）。

- [ ] **Step 4: 抽查 5 条验证质量**

```bash
head -6 webnovel-writer/references/private-csv/ai-replacement-vocab.csv
head -6 webnovel-writer/references/private-csv/canon-violation-traps.csv
```

人工核对：
- 坏样本是否有意义（不是空 / 不是 "[REDACTED]" / 不是 fix_hint 倒灌）
- 子维度 / 钩子类型 / 情感类型 / 禁区类型 字段是否填上
- 严重度合理（critical 仅用于阻断级证据）

如有问题：调整 extractor 截断长度 / 兜底逻辑 / 重新跑。

### Task F.3: webnovel.py 加 private-csv 子命令

**Files:**
- Modify: `webnovel-writer/scripts/data_modules/webnovel.py`

- [ ] **Step 1: 找 sub.add_parser("extract-context") 注册行**

```bash
grep -n 'sub.add_parser("extract-context")' webnovel-writer/scripts/data_modules/webnovel.py
```

- [ ] **Step 2: 在它之后追加 private-csv 注册**

```python
    p_extract_context = sub.add_parser("extract-context", help="转发到 extract_chapter_context.py")
    # Round 19 Phase F · 私库 CSV 提取转发
    p_pcsv = sub.add_parser("private-csv", help="转发到 scripts/private_csv_extractor.py（4 张私库 CSV 提取）")
    p_pcsv.add_argument("--table", required=True, choices=["ai-replacement-vocab","strong-chapter-end-hooks","emotion-earned-vs-forced","canon-violation-traps"])
    p_pcsv.add_argument("--chapters", required=True)
    p_pcsv.add_argument("--output-dir", default=None)
```

- [ ] **Step 3: 在 dispatch 段追加分支**

```bash
grep -n 'if tool == "extract-context"' webnovel-writer/scripts/data_modules/webnovel.py
```

定位 dispatch 后追加：

```python
    if tool == "private-csv":
        import subprocess as _sp
        # 解析 SCRIPTS_DIR（参考既有 extract-context 解析）
        scripts_dir = (Path(__file__).resolve().parent.parent)  # data_modules/ 上一层 = scripts/
        cmd = [sys.executable, "-X", "utf8",
               str(scripts_dir / "private_csv_extractor.py"),
               "--project", str(args.project_root),
               "--table", args.table,
               "--chapters", args.chapters]
        if args.output_dir:
            cmd += ["--output-dir", args.output_dir]
        return _sp.call(cmd)
```

注：上面 `scripts_dir` 计算方式以本地实际目录结构为准，参 `extract-context` 的现有实现风格（grep `extract_chapter_context.py` 找现成模式仿写）。

- [ ] **Step 4: 端到端测试**

```bash
python -X utf8 webnovel-writer/scripts/data_modules/webnovel.py \
  --project-root 末世重生-我在空间里种出了整个基地 \
  private-csv --table ai-replacement-vocab --chapters 1-11
```

Expected: 与直接调用 extractor 一致输出。

### Task F.4: 写读双向回灌

#### F.4.1: writer 起草前查 ai-replacement-vocab + canon-violation-traps

**Files:**
- Modify: `webnovel-writer/agents/context-agent.md`

- [ ] **Step 1: 在创作执行包 writing_guidance 输出段追加私库提醒**

```markdown
### Round 19 新增 · 私库提醒（writing_guidance 末尾追加）

每章生成创作执行包时**必须**注入私库前 N 条到 `writing_guidance.local_blacklist` + `writing_guidance.canon_traps`：

1. 读 `${CLAUDE_PLUGIN_ROOT}/references/private-csv/ai-replacement-vocab.csv`
2. 按"严重度"排序（critical > high > medium）取前 10 条
3. 把每条的"坏样本→好样本"作为本章起草禁词清单写入 `writing_guidance.local_blacklist`：
   ```json
   {
     "local_blacklist": [
       {"bad": "缓缓开口", "good_hint": "前置动作 + 引号", "subdimension": "vocab", "ref": "AV-003"}
     ]
   }
   ```
4. 同样读 `canon-violation-traps.csv`，取本作（末世重生）相关的前 5 条到 `writing_guidance.canon_traps`：
   ```json
   {
     "canon_traps": [
       {"trap": "战力越权", "evidence": "...", "ref": "CV-002"}
     ]
   }
   ```
5. 任意一表读取失败（文件缺失 / 解析错误） → log 警告但不阻断
```

#### F.4.2: reader-naturalness-checker 复测时回查升级 severity

**Files:**
- Modify: `webnovel-writer/agents/reader-naturalness-checker.md`

- [ ] **Step 1: 在评分段末尾追加私库回查**

```markdown
### Round 19 新增 · 私库回查（reader-naturalness-checker 输出 issues 时执行）

完成 5 子维度评分 + issues 列表后，对每条 issue 回查 `${CLAUDE_PLUGIN_ROOT}/references/private-csv/ai-replacement-vocab.csv`：

1. 读 CSV 全部行
2. 对当前 issue 的 `evidence` 做模糊匹配（substring 或编辑距离 ≤ 2）
3. 命中 → severity 升级一级（medium→high, high→critical），evidence 末尾追加 `[recurring_violation: AV-XXX]` 标记
4. 同时把本次 issue 的"新违例 + fix_hint"写入 `tmp/private_csv_proposal_ch{NNNN}.json`，data-agent Step K 时提示用户是否追加私库
```

#### F.4.3: consistency-checker 同样回查 canon-violation-traps

**Files:**
- Modify: `webnovel-writer/agents/consistency-checker.md`

- [ ] **Step 1: 在 setting/timeline/character 类 issue 输出段追加回查**

```markdown
### Round 19 新增 · 私库回查 canon-violation-traps

发现 setting/timeline/character/logic 类 issue 时回查 `${CLAUDE_PLUGIN_ROOT}/references/private-csv/canon-violation-traps.csv`：

- 该类禁区在私库已存在 → severity 升级 + evidence 追加 `recurring_canon_violation: CV-XXX` 标记
- 新禁区 → 写 `tmp/canon_proposal_ch{NNNN}.json`，data-agent 提示追加
```

### Task F.5: sync + verify + commit

- [ ] **Step 1: 三套验证**

```bash
python -X utf8 webnovel-writer/scripts/data_modules/webnovel.py sync-cache
python -X utf8 webnovel-writer/scripts/data_modules/webnovel.py preflight
python -X utf8 末世重生-我在空间里种出了整个基地/.webnovel/hygiene_check.py
```

- [ ] **Step 2: 跑首次实数据提取**

```bash
for t in ai-replacement-vocab strong-chapter-end-hooks emotion-earned-vs-forced canon-violation-traps; do
  python -X utf8 webnovel-writer/scripts/data_modules/webnovel.py \
    --project-root 末世重生-我在空间里种出了整个基地 \
    private-csv --table $t --chapters 1-11
done
wc -l webnovel-writer/references/private-csv/*.csv
```

- [ ] **Step 3: CUSTOMIZATIONS.md 顶部插入 Phase F 段**（参 Phase A 格式，记录每张表实际行数）

- [ ] **Step 4: Commit**

```bash
git add webnovel-writer/references/private-csv/ \
        webnovel-writer/scripts/private_csv_extractor.py \
        webnovel-writer/scripts/data_modules/webnovel.py \
        webnovel-writer/agents/context-agent.md \
        webnovel-writer/agents/reader-naturalness-checker.md \
        webnovel-writer/agents/consistency-checker.md \
        webnovel-writer/CUSTOMIZATIONS.md
git commit -m "$(cat <<'EOF'
feat(reader-quality): Phase F · 4 张私库 CSV + 自动提取器 + 写读双向回灌

ai-replacement-vocab / strong-chapter-end-hooks / emotion-earned-vs-forced / canon-violation-traps
private_csv_extractor.py 兼容多种 tmp/*.json 命名 + audit_reports B 层
writer 起草前查 + reader-naturalness/consistency 复测时回查升级 severity
零新数据来源 · 全部从 11 章 RCA tmp + audit + polish 派生

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase G · 章末钩子 4 分类 + 跨章追踪（P1 · 4h · 追读力）

### Task G.1: 写 chapter-end-hook-taxonomy.md

**Files:**
- Create: `webnovel-writer/skills/webnovel-write/references/chapter-end-hook-taxonomy.md`

- [ ] **Step 1: Write 完整文件**

```markdown
---
name: chapter-end-hook-taxonomy
purpose: 章末钩子 4 分类规范 + 跨章趋势规则
---

# 章末钩子 4 分类（Round 19）

## 与既有 hook_type 的关系

- Ch1-11 既有 `chapter_meta[NNNN].hook_type` 字段（值如"意象钩"）—— 是历史遗留的自由文本，**不动**
- Round 19 平行新增 `chapter_meta[NNNN].hook_close.primary_type` —— 强约束 4 类枚举
- Phase G 后两个字段并存；hygiene_check 不要求历史章节回填 hook_close

## 4 类定义

| 类型 | 触发读者动机 | 示例 | 强信号 |
|---|---|---|---|
| **信息钩** | 想知道"是什么"、"为什么"、"谁" | 她终于看清了那张脸——是十年前应该已经死去的人。 | 揭示 / 反转 / 真相缺片 |
| **情绪钩** | 想知道"她会怎么应对"、"他下一步什么心情" | 他没有回头，把那枚戒指扔进了海里。 | 决断 / 离别 / 隐忍 |
| **决策钩** | 想知道"她选哪边"、"他怎么选" | 面前两扇门，左边是父亲，右边是仇人。她伸出了手—— | 二选 / 道德困境 / 立场抉择 |
| **动作钩** | 想知道"打赢了吗"、"逃掉了吗"、"接住了吗" | 刀光起处，他终于看清了那双眼睛。 | 战斗 / 追逐 / 关键瞬间 |

## 评判标准

每章末由 reader-pull-checker 二选：

1. `primary_type`（必填）：4 类之一
2. `secondary_type`（可选）：4 类之一（多重钩子 / null）

判断窗口：章末**最后 200 字**。

## 跨章趋势规则

| 规则 | 严重度 | 理由 |
|---|---|---|
| 连续 5 章 primary 相同 | medium | 节奏疲劳 |
| 连续 3 章 primary+secondary 组合相同 | high | 模式可预测 |
| 连续 8 章无"决策钩" | medium | 主角失去主动性 |
| 连续 8 章无"情绪钩" | medium | 关系线断档 |
| 单卷（默认 20 章）内 4 类全缺 1 类 | medium | 情绪面单一 |

## reader-pull-checker 输出 schema 扩展

```json
{
  "checker": "reader-pull-checker",
  "chapter": 12,
  "reader_pull": 88,
  "hook_close": {
    "primary_type": "信息钩",
    "secondary_type": "情绪钩",
    "strength": 88,
    "text_excerpt": "章末最后 200 字"
  },
  "cross_chapter_trend": {
    "recent_5_primary": ["信息钩","信息钩","情绪钩","信息钩","信息钩"],
    "recent_8_categories": ["信息钩","信息钩","情绪钩","信息钩","信息钩","信息钩","信息钩","信息钩"],
    "warnings": [
      {"rule": "连续 5/5 章信息钩", "severity": "medium", "fix_hint": "Ch12 切换为决策钩或动作钩"}
    ]
  }
}
```

## hygiene_check H25 联动

H25（Phase G 新增）扫描最近 5 章 chapter_meta.hook_close.primary_type，命中"连续 5 章相同" → P1 warn。

## CLI 集成

- `webnovel.py state set-hook-close` 写入字段（Phase G Task G.3）
- `webnovel.py state get-hook-trend --last-n 5` 查询趋势（Phase G Task G.3）
- data-agent Step K 自动从 reader_pull_ch{NNNN}.json 提取 hook_close 并落库（Phase G Task G.4）
```

### Task G.2: reader-pull-checker 接入 4 分类

**Files:**
- Modify: `webnovel-writer/agents/reader-pull-checker.md`

- [ ] **Step 1: 在评分维度段末尾追加 Round 19 段**

```markdown
### Round 19 新增 · 章末钩子 4 分类（参 chapter-end-hook-taxonomy.md）

每章除给主分数 reader_pull 外**必须**输出：

```json
"hook_close": {
  "primary_type": "信息钩 | 情绪钩 | 决策钩 | 动作钩",
  "secondary_type": "...或 null",
  "strength": 88,
  "text_excerpt": "章末最后 200 字原文"
}
```

判断方法：

1. Read 章末最后 200 字
2. 对照 chapter-end-hook-taxonomy.md 4 类强信号定义二选
3. strength 来自既有 reader_pull 主分数；text_excerpt 是原文片段不超过 200 字

### Round 19 新增 · 跨章趋势检查（必跑）

跑：

```bash
python -X utf8 "${SCRIPTS_DIR}/data_modules/webnovel.py" --project-root "${PROJECT_ROOT}" \
  state get-hook-trend --last-n 5
```

CLI 返回 `recent_5_primary` 数组 + 自动判定字段。按以下规则把命中规则写入 issues：

- recent_5_primary 全部相同 → issue (severity=medium, category=pacing)
- 连续 3 章 primary+secondary 组合相同 → issue (severity=high)
- recent_8_no_decision_hook → issue (severity=medium)
- recent_8_no_emotion_hook → issue (severity=medium)

cross_chapter_trend 子对象作为 reader-pull 输出附加字段。
```

### Task G.3: state_manager.py 加 set-hook-close + get-hook-trend

**Files:**
- Modify: `webnovel-writer/scripts/data_modules/state_manager.py`

- [ ] **Step 1: 注册新参数（在 Phase C 已加的 --set-checker-subdimensions 之后）**

```python
    # Round 19 Phase G · 章末钩子 4 分类入口
    update_parser.add_argument(
        "--set-hook-close",
        help='JSON: {"chapter":N,"primary":"信息钩|情绪钩|决策钩|动作钩","secondary":null,"strength":88,"text":"章末最后 200 字"}',
    )
```

- [ ] **Step 2: 添加新独立子命令 get-hook-trend**

在 update_parser 注册之后，subparsers 块末尾追加：

```python
    # Round 19 Phase G · 跨章趋势查询
    trend_parser = subparsers.add_parser("get-hook-trend", help="查询最近 N 章 hook_close.primary_type 序列 + 自动判定")
    trend_parser.add_argument("--last-n", type=int, default=5)
```

- [ ] **Step 3: dispatch 段追加 set-hook-close**

在 update 分发段（Phase C 加的子维度块之后）追加：

```python
        if args.set_hook_close:
            try: payload = json.loads(args.set_hook_close)
            except Exception as exc:
                emit_error("INVALID_JSON", f"--set-hook-close JSON 解析失败：{exc}"); return 1
            ch = payload.get("chapter"); primary = payload.get("primary")
            valid_types = {"信息钩","情绪钩","决策钩","动作钩"}
            if not (isinstance(ch, int) and primary in valid_types):
                emit_error("INVALID_ARG", f"--set-hook-close chapter(int) + primary∈{valid_types} 必填"); return 1
            sec = payload.get("secondary")
            if sec and sec not in valid_types: sec = None
            ch_key = f"{ch:04d}"
            cm = state.setdefault("chapter_meta", {}).setdefault(ch_key, {})
            cm["hook_close"] = {
                "primary_type": primary,
                "secondary_type": sec,
                "strength": payload.get("strength", 80),
                "text_excerpt": (payload.get("text") or "")[:200],
            }
            atomic_write_state(state)
            print(json.dumps({"ok": True, "chapter": ch, "hook_close": cm["hook_close"]}, ensure_ascii=False))
            return 0
```

- [ ] **Step 4: dispatch 段追加 get-hook-trend（注意是 subparsers 顶级命令，不是 update 子命令）**

在主 dispatch（command 级）追加：

```python
    if args.command == "get-hook-trend":
        chs_str = sorted(state.get("chapter_meta", {}).keys())
        chs = [int(k) for k in chs_str if k.isdigit()]
        recent = sorted(chs)[-args.last_n:]
        primaries = []
        secs = []
        for ch in recent:
            hc = (state["chapter_meta"].get(f"{ch:04d}") or {}).get("hook_close") or {}
            primaries.append(hc.get("primary_type", ""))
            secs.append(hc.get("secondary_type", ""))
        out = {
            "recent_n": args.last_n,
            "chapters": recent,
            "recent_primary": primaries,
            "recent_secondary": secs,
            "all_same_primary": len(set(primaries)) == 1 and len(primaries) == args.last_n and primaries[0] != "",
            "no_decision_hook_8": "决策钩" not in primaries[-8:] if len(primaries) >= 8 else False,
            "no_emotion_hook_8": "情绪钩" not in primaries[-8:] if len(primaries) >= 8 else False,
            "combo_repeated_3": len(primaries) >= 3 and len({(p,s) for p,s in zip(primaries[-3:], secs[-3:])}) == 1,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
```

注：`atomic_write_state` 等函数名以 state_manager 实际为准。

- [ ] **Step 5: 烟雾测试**

```bash
python -X utf8 webnovel-writer/scripts/data_modules/webnovel.py \
  --project-root 末世重生-我在空间里种出了整个基地 \
  state update --set-hook-close '{"chapter":11,"primary":"信息钩","secondary":null,"strength":82,"text":"汽笛长鸣从不该响的方位压来又退回..."}'

python -X utf8 webnovel-writer/scripts/data_modules/webnovel.py \
  --project-root 末世重生-我在空间里种出了整个基地 \
  state get-hook-trend --last-n 5
```

Expected:
- 第 1 条：`{"ok": true, "chapter": 11, "hook_close": {...}}`
- 第 2 条：返回 5 章 `recent_primary` 数组（其中 Ch11 是 "信息钩"，其余暂为空字符串，待 Task G.5 回填）

### Task G.4: data-agent Step K 写 hook_close

**Files:**
- Modify: `webnovel-writer/agents/data-agent.md`

- [ ] **Step 1: 在 Step K 章节摘要写入段追加**

```markdown
### Round 19 Phase G · 章末钩子分类落库

读 `tmp/reader_pull_ch{NNNN}.json` 取 `hook_close` 子对象（Phase G 起 reader-pull-checker 必输出此字段），跑：

```bash
python -X utf8 "${SCRIPTS_DIR}/data_modules/webnovel.py" --project-root "${PROJECT_ROOT}" \
  state update --set-hook-close '{"chapter":N,"primary":"信息钩","secondary":null,"strength":88,"text":"章末 200 字"}'
```

若 reader_pull JSON 缺 hook_close 子对象（老 checker 版本）→ Step K 提示但不阻断；启发式兜底（基于 hook_type 历史字段映射）：

- "意象钩" / "未知" / 空 → 不写
- "信息钩" / "悬念钩" / "真相钩" → 信息钩
- "情绪钩" / "决断钩" → 情绪钩
- "决策钩" / "选择钩" → 决策钩
- "动作钩" / "战斗钩" → 动作钩

### 跨章趋势提示

Step K 完成所有写库后，跑 `state get-hook-trend --last-n 5` 取结果：

- `all_same_primary == true` → 在 polish_log[-1].notes 追加："Ch{N+1} 提醒：连续 5 章 {primary} 钩，下章建议切换"
- `no_decision_hook_8 == true` → 同样追加提醒

提醒**不阻断**当前章 commit。
```

### Task G.5: hygiene_check 加 H25

**Files:**
- Modify: `webnovel-writer/scripts/hygiene_check.py`

- [ ] **Step 1: 在 hygiene_check.py 主函数注册段追加 H25**

```bash
grep -n "def h2[0-4]\|H21\|H23\|H24" webnovel-writer/scripts/hygiene_check.py | head -10
```

定位 H24 函数定义后追加：

```python
def h25_hook_trend_check(project_root: Path) -> Dict[str, Any]:
    """H25: 章末钩子 4 类跨章趋势（Round 19 Phase G）"""
    try:
        state = json.loads((project_root / ".webnovel" / "state.json").read_text(encoding="utf-8"))
    except Exception as exc:
        return {"id": "H25", "status": "error", "msg": f"读 state.json 失败：{exc}"}

    metas = state.get("chapter_meta", {}) or {}
    chs = sorted([k for k in metas.keys() if k.isdigit()])
    if len(chs) < 5:
        return {"id": "H25", "status": "skip", "reason": "< 5 章已成稿，跳过趋势检查"}

    recent = chs[-5:]
    primaries = [(metas[k].get("hook_close") or {}).get("primary_type", "") for k in recent]
    if all(p and p == primaries[0] for p in primaries):
        return {
            "id": "H25", "status": "warn", "severity": "P1",
            "msg": f"连续 5 章 hook_close.primary_type 相同：{primaries[0]}（章 {[int(k) for k in recent]}）",
            "fix_hint": "下章 reader-pull-checker 提醒切换钩子类型",
        }
    return {"id": "H25", "status": "ok"}
```

- [ ] **Step 2: 注册到主循环**

找到 hygiene_check 主循环（grep `H24\|hygiene_checks =\|run_all`），在它列表中追加 `h25_hook_trend_check`。

- [ ] **Step 3: 烟雾测试**

```bash
python -X utf8 末世重生-我在空间里种出了整个基地/.webnovel/hygiene_check.py
```

Expected: 报告含 H25 项；Ch1-11 因 hook_close 字段还没回填，H25 应 status=skip 或 warn 但**不阻断**。

### Task G.6: 回填 Ch1-11 hook_close

- [ ] **Step 1: 启发式回填脚本**

```bash
python -X utf8 - <<'PY'
import json, subprocess, sys
from pathlib import Path

proj = Path("末世重生-我在空间里种出了整个基地")
state = json.loads((proj / ".webnovel" / "state.json").read_text(encoding="utf-8"))

# 启发式映射：从既有 hook_type 推断 4 类
def heuristic(ch_meta):
    ht = (ch_meta.get("hook_type") or "").strip()
    hc = (ch_meta.get("hook_content") or "").strip()
    if "决" in ht or "选" in ht or "决策" in hc or "选择" in hc:
        return "决策钩"
    if "动作" in ht or "战" in ht or any(w in hc for w in ["刀光","拳","逃","追","抓","扑"]):
        return "动作钩"
    if "情绪" in ht or "感" in ht or any(w in hc for w in ["扔","转身","停下","哭","笑","沉默"]):
        return "情绪钩"
    # 默认信息钩
    return "信息钩"

text_dir = proj / "正文"
for ch_key in sorted(state.get("chapter_meta", {}).keys()):
    if not ch_key.isdigit(): continue
    ch = int(ch_key)
    if ch > 11: continue
    cm = state["chapter_meta"][ch_key]
    if (cm.get("hook_close") or {}).get("primary_type"): continue  # 已有不重写
    primary = heuristic(cm)
    # 取章末 200 字
    candidates = list(text_dir.glob(f"第{ch:04d}章*.md")) + list(text_dir.glob(f"第{ch}章*.md"))
    text = candidates[0].read_text(encoding="utf-8", errors="ignore") if candidates else ""
    last_200 = text.strip().rstrip("```").strip().split("\n\n")[-1][-200:] if text else ""
    payload = json.dumps({
        "chapter": ch, "primary": primary, "secondary": None,
        "strength": 80, "text": last_200,
    }, ensure_ascii=False)
    print(f"Ch{ch}: {primary}")
    subprocess.run([
        sys.executable, "-X", "utf8",
        "webnovel-writer/scripts/data_modules/webnovel.py",
        "--project-root", str(proj),
        "state", "update", "--set-hook-close", payload,
    ], check=True)
PY
```

Expected: 11 章全部回填，输出每章的判定 primary。

- [ ] **Step 2: 人工抽查 Ch5/Ch10/Ch11**（启发式可能误判）

```bash
python -X utf8 webnovel-writer/scripts/data_modules/webnovel.py \
  --project-root 末世重生-我在空间里种出了整个基地 \
  state get-hook-trend --last-n 11
```

Read 输出，对照 Ch5/10/11 实际章末，必要时手动校正：

```bash
python -X utf8 webnovel-writer/scripts/data_modules/webnovel.py \
  --project-root 末世重生-我在空间里种出了整个基地 \
  state update --set-hook-close '{"chapter":5,"primary":"决策钩","secondary":"情绪钩","strength":85,"text":"..."}'
```

### Task G.7: sync + verify + commit

- [ ] **Step 1: 三套验证**

- [ ] **Step 2: CUSTOMIZATIONS.md 顶部插入 Phase G 段**

- [ ] **Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(reader-quality): Phase G · 章末钩子 4 分类 + 跨章追踪 + H25

chapter-end-hook-taxonomy.md · 信息/情绪/决策/动作钩
state update --set-hook-close + get-hook-trend CLI
hygiene_check H25 · 连续 5 章同钩 P1 warn
data-agent Step K 自动落库 + 启发式兜底
回填 Ch1-11 hook_close 实数据

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase B · polish-guide K/L/M/N + 6 句式规则吸收（P2 · 2h · 自然度）

### Task B.1: 比对合并 4 类新词库

**Files:**
- Modify: `webnovel-writer/skills/webnovel-write/references/polish-guide.md`

- [ ] **Step 1: 取 upstream + 本地各自 K/L/M/N 段**

```bash
git show upstream/master:webnovel-writer/skills/webnovel-write/references/polish-guide.md > /tmp/upstream-polish.md
grep -n "^#### [KLMN]\.\|^### 第1层\|^### 第2层" /tmp/upstream-polish.md webnovel-writer/skills/webnovel-write/references/polish-guide.md
```

- [ ] **Step 2: 用 Read + Edit 把 upstream K/L/M/N 段（连描述 + 词表）合并到本地**

如果本地已有 K/L/M/N：取 word union（手工）保留本地词 + 增 upstream 新词；保留本地"血教训"标注。

如果本地缺：把 upstream 4 段（K 神态模板词 / L 万能副词 / M 内心活动套话 / N 转折递进模板）整段插入到本地"第 1 层"末尾。

- [ ] **Step 3: 第 2 层 6 条句式规则**

upstream 第 2 层（10 条），本地第 2 层 grep 数一下条目数：

```bash
grep -c "^- 禁止\|^- 每" webnovel-writer/skills/webnovel-write/references/polish-guide.md
```

把缺的 6 条加上（10-本地数）。

- [ ] **Step 4: 引号自愈**

```bash
python -X utf8 webnovel-writer/scripts/quote_pair_fix.py --ascii-to-curly \
  webnovel-writer/skills/webnovel-write/references/polish-guide.md
```

### Task B.2: 验证 + commit

- [ ] **Step 1: 三套验证**

- [ ] **Step 2: CUSTOMIZATIONS.md Phase B 段**

- [ ] **Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(reader-quality): Phase B · polish-guide K/L/M/N 词库 + 6 句式规则

upstream@74717aa · 4 类新分类（神态模板/万能副词/内心活动/转折递进）
+ 6 条句式规则补强；保留本地 Round 17.2 签名密度硬线

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase H · prose-quality 画面感 3 子规则（P2 · 3h · 画面感）

### Task H.1: 写 visual-concreteness-rubric.md

**Files:**
- Create: `webnovel-writer/skills/webnovel-write/references/visual-concreteness-rubric.md`

- [ ] **Step 1: Write 完整文件**

```markdown
---
name: visual-concreteness-rubric
purpose: 画面感 3 子规则 · 视觉锚点 / 非视觉感官 / 抽象动作改写
---

# 画面感 3 子规则（Round 19 Phase H）

## 子规则 1: 场景首句视觉锚点

每个新场景的**首句**必须含至少 1 项视觉锚点：

| 锚点类型 | 示例 |
|---|---|
| 光线 | 窗外的光斜斜地切过他的左肩。 |
| 空间 | 地下室只有三步深，墙在他左手边发凉。 |
| 物体 | 刀就摆在桌角，刀尖朝着她。 |

**禁止**：场景首句写心理活动 / 抽象状态 / 时间流逝 / 概括性描述。

判断"新场景"：空行 + 时间地点切换标志（"次日清晨" / "三天后" / "他到了医院"）。

扣分：每违例 -10 critical（直接 blocking 给 reader_critic）。

## 子规则 2: 每段非视觉感官 ≥ 30%

每段（≥ 50 字）至少含 1 个非视觉感官：

- 听觉（远处有人在喊她的名字）
- 触觉（门把冰得像一截铁）
- 嗅觉（血腥味开始压过消毒水的味道）
- 温度（风停了，但空气还是凉的）
- 味觉（舌尖尝到铁锈味）

**统计**：每章总段数 ≥ 50 字的段中，含非视觉感官的段数占比。

| 占比 | 评分 |
|---|---|
| ≥ 30% | 100 |
| 15-30% | 线性 50-100 |
| < 15% | 0（critical） |

## 子规则 3: 抽象动作触发改写

下列抽象动作短语必须改为具象描写：

| 抽象动作 | 改写要求 | 示例 |
|---|---|---|
| 展开攻势 | 具体动作链 | 试探 / 突进 / 拨开 / 反手 |
| 陷入沉思 | 微动作 | 拧笔帽 / 摸下巴 / 看窗外 / 数手指 |
| 气氛凝固 | 感官锚点 | 声音消失 / 温度下降 / 谁的呼吸声 |
| 心潮澎湃 | 生理反应 | 指节发白 / 心跳乱拍 / 呼吸不稳 |
| 目光交汇 | 时长+动作 | 多久 / 谁先移开 |
| 浑身一震 | 具体反射 | 手指抖 / 后退半步 / 重心一沉 |
| 缓缓睁开眼 | 删副词 + 前置/后置动作 | 睁眼，光太亮，他立刻又闭上 |
| 微微点头 | 删副词 | 他点了下头 |

扣分：每出现 1 处未改写抽象动作 -3，单章 ≥ 5 处 → high。

## prose-quality-checker 输出 schema 扩展

```json
{
  "checker": "prose-quality-checker",
  "chapter": 12,
  "prose_quality": 88,
  "visual_subdimensions": {
    "scene_visual_anchor": 95,
    "non_visual_sensory_ratio": 78,
    "abstract_action_count": 2
  },
  "issues": [
    {"category": "visual", "subcategory": "non_visual_sensory", "severity": "high", "evidence": "...", "fix_hint": "..."}
  ]
}
```

主分加权：

```
prose_quality = round(原综合 × 0.6 + visual_subdimensions 平均 × 0.4, 2)
```

## SKILL.md 加载

writer 在 Step 2 起草时加载本文件作为参考；prose-quality-checker 在 Step 3 审查时强制走 3 子规则。
```

### Task H.2: prose-quality-checker 接入

**Files:**
- Modify: `webnovel-writer/agents/prose-quality-checker.md`

- [ ] **Step 1: 在评分维度段末尾追加 Round 19 段**

```markdown
### Round 19 新增 · 画面感 3 子规则（参 visual-concreteness-rubric.md）

#### visual_subdimensions 子对象（必输出）

1. **scene_visual_anchor** (0-100)：扫所有场景切换点（空行 + 时间/地点切换标志），首句缺视觉锚点 → 每处 -10
2. **non_visual_sensory_ratio** (0-100)：≥ 50 字段中含非视觉感官的占比映射到 0-100
3. **abstract_action_count** (0-N)：扫"展开攻势 / 陷入沉思 / 气氛凝固 / 心潮澎湃 / 目光交汇 / 浑身一震 / 缓缓睁开 / 微微点头"等模板，未改写计数

#### 主分加权

```
prose_quality = round(原综合 × 0.6 + mean(scene_visual_anchor, non_visual_sensory_ratio, max(0, 100-10*abstract_action_count)) × 0.4, 2)
```

#### issues 字段格式

每个违例 → 一个 issue，category="visual"，subcategory ∈ {scene_anchor, non_visual_sensory, abstract_action}。
```

### Task H.3: SKILL.md 加 visual-rubric 加载点

**Files:**
- Modify: `webnovel-writer/skills/webnovel-write/SKILL.md`

```
- references/visual-concreteness-rubric.md（Round 19 · 画面感 3 子规则 · writer 起草时即时遵守）
```

### Task H.4: 验证 + commit

- [ ] **Step 1: 三套验证**

- [ ] **Step 2: CUSTOMIZATIONS.md Phase H 段**

- [ ] **Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(reader-quality): Phase H · prose-quality 画面感 3 子规则

视觉锚点 / 非视觉感官 30% / 抽象动作改写
visual_subdimensions 落库；主分加权（原 ×0.6 + 视觉 ×0.4）

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase E · plan 跨卷感知（P2 · 1h · 追读力）

### Task E.1: webnovel-plan SKILL 加 history 加载段

**Files:**
- Modify: `webnovel-writer/skills/webnovel-plan/SKILL.md`

- [ ] **Step 1: 找 plan 数据加载段**

```bash
grep -n "state.json\|chapter_meta\|history\|大纲\|Step" webnovel-writer/skills/webnovel-plan/SKILL.md | head -10
```

- [ ] **Step 2: 在合适位置追加 Round 19 跨卷加载步骤**

```markdown
### Step 1.5 · Cross-volume awareness（Round 19 Phase E · upstream@3e36417 借鉴）

下卷规划前必须读已写章节真实数据，不能只看大纲：

1. 跑：
   ```bash
   python -X utf8 ${SCRIPTS_DIR}/data_modules/webnovel.py state get-recent-meta --last-n 10
   ```
   取最近 10 章 `hook_close / unresolved_loops / protagonist_state.golden_finger / overall_score`。

2. 跑（Phase G 之后）：
   ```bash
   python -X utf8 ${SCRIPTS_DIR}/data_modules/webnovel.py state get-hook-trend --last-n 10
   ```
   取 4 类钩子分布。

3. 在新卷规划必须**显式回应**：
   - 至少 1 个上卷未解决的伏笔在本卷开篇 3 章内被触及
   - 主角金手指曲线在新卷保持单调或带显式弱化事件
   - 上卷读者钩子若得分 < 70，新卷开篇加强同类钩子
   - 上卷 hook_trend 若 primary 连续 5+ 章相同 → 新卷必须切换钩子组合
```

### Task E.2: state_manager 加 get-recent-meta CLI

**Files:**
- Modify: `webnovel-writer/scripts/data_modules/state_manager.py`

- [ ] **Step 1: 注册新独立子命令**

```python
    # Round 19 Phase E · 跨卷规划
    recent_parser = subparsers.add_parser("get-recent-meta", help="取最近 N 章 chapter_meta 摘要供 plan 读")
    recent_parser.add_argument("--last-n", type=int, default=10)
```

- [ ] **Step 2: dispatch**

```python
    if args.command == "get-recent-meta":
        chs_str = sorted(state.get("chapter_meta", {}).keys())
        chs = [int(k) for k in chs_str if k.isdigit()]
        recent = sorted(chs)[-args.last_n:]
        out = {}
        for ch in recent:
            m = (state["chapter_meta"].get(f"{ch:04d}") or {})
            out[ch] = {
                "hook_close": m.get("hook_close"),
                "hook_type": m.get("hook_type"),
                "hook_strength": m.get("hook_strength"),
                "unresolved_loops": m.get("unresolved_loops") or [],
                "overall_score": m.get("overall_score") or (m.get("checker_scores") or {}).get("overall"),
                "narrative_version": m.get("narrative_version"),
                "word_count": m.get("word_count"),
            }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
```

- [ ] **Step 3: 烟雾测试**

```bash
python -X utf8 webnovel-writer/scripts/data_modules/webnovel.py \
  --project-root 末世重生-我在空间里种出了整个基地 \
  state get-recent-meta --last-n 5
```

Expected: JSON 输出 5 章摘要。

### Task E.3: 验证 + commit

```bash
git commit -m "$(cat <<'EOF'
feat(reader-quality): Phase E · plan 跨卷感知

state get-recent-meta CLI · plan SKILL Step 1.5 加载
upstream@3e36417 借鉴

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase D · upstream CSV 9 表（P3 · 4h · 条件执行）

### Task D.1: 干货度抽查 + 决策

- [ ] **Step 1: 抽查 3 张 CSV 各前 8 行**

```bash
git show upstream/master:webnovel-writer/references/csv/裁决规则.csv | head -8
git show upstream/master:webnovel-writer/references/csv/场景写法.csv | head -8
git show upstream/master:webnovel-writer/references/csv/爽点与节奏.csv | head -8
```

- [ ] **Step 2: 评分**

每张 CSV 按 4 项打分（每项 0/1）：
- 条目数 ≥ 10
- "大模型指令"具体可执行
- "毒点"列对本作（末世重生 · 科幻末世）适用
- "示例片段"是干货

3 张 CSV 总分 ≥ 8 → 执行 Task D.2；< 8 → 跳过 Phase D，直接进 Phase 7。

### Task D.2:（条件）按 v1 计划 Phase 2 完整流程引入

参照 v1 计划 `2026-04-25-upstream-cherry-pick-quality-uplift.md` 的 Phase 2 全套：

- 引入 10 张 CSV（含 README + genre-canonical.md）到 `webnovel-writer/references/csv/`
- 引入 `reference_search.py` BM25 检索引擎到 `webnovel-writer/scripts/`
- `webnovel.py` 加 `reference` 子命令转发
- context-agent 加 Stage 2.5 题材-场景检索 + writing_guidance.csv_hints 输出
- high-point-checker / pacing-checker 引用对应 CSV 维度

完整步骤略，按 v1 计划复制。

---

## Phase 7 · DO NOT MERGE 永久清单（必做 · 30 min）

### Task 7.1: 写入 CUSTOMIZATIONS.md DO NOT MERGE 段

**Files:**
- Modify: `webnovel-writer/CUSTOMIZATIONS.md`
- Modify: `ROOT_CAUSE_GUARD_RAILS.md`（如存在）

- [ ] **Step 1: CUSTOMIZATIONS.md 顶部追加 DO NOT MERGE 段**

```markdown
## [2026-04-25 · DO NOT MERGE 永久清单 · Round 19 立项]

下列 upstream 改动**永久不合并**。本地 fork 与 upstream 在这些维度已分叉为不同产品。每条都给出原因 + 替代路径。**每次 git fetch upstream 看到属于以下类别的新 commit，直接跳过，不必重新评估。**

### 1. v6 单 reviewer.md（替代 13 checker）

- upstream commits: `264dd24` `b7a944d` `b488401` `ce6bf35` `5339e83`（仅 5 子维度 rubric 借鉴到 Phase C，不引入 reviewer.md 整体）
- 拒绝原因：用户明确要求 90-100 评分体系（feedback_review_score_target.md）；upstream 砍掉评分；本地 13 checker × 14 外部模型 = 182 共识样本是 18 轮加固的核心
- 替代：本地继续 13 checker；如需"摘要式输出"在 review_pipeline 后加聚合层，不动评分

### 2. workflow_manager 移除（依赖 Claude Code /resume）

- upstream commit: `b1e7402`
- 拒绝原因：本地 Step 0-7 流程严重依赖 workflow_manager（feedback_ch7_workflow_must_log）；并已对 complete-task --force 等做 RCA 加固（Round 15.3 Bug #1）
- 替代：本地继续维护 workflow_manager；CC `/resume` 作并行能力

### 3. story-system 事件溯源 + projection writers

- upstream commits: `a3c19cf` `b80e5a5` `ac748d2` 等 Phase 1-5 全套
- 拒绝原因：本地 state.json 已被 hygiene H1-H24 + 多个 CLI 当作直接真源；改成 CHAPTER_COMMIT + projection 投影模式 = 重做 18 轮加固
- 替代：state.json 继续直写；如需事件审计链，在 state_manager 加事件日志

### 4. vector_projection_writer + vectors.db

- upstream commits: `29c8ac1` `7c849f8`
- 拒绝原因：边际收益低（已有摘要 + index.db；Phase G 又新加了 hook_trend）；引入需 embedding 模型 + 新数据层
- 替代：knowledge_query 时序 API（Round 20 视情况评估）

### 5. dashboard 路由多页重建

- upstream commits: `a033f36` `34c436d` `65c220b` `b57754d` `bb9829a`
- 拒绝原因：纯 QoL，不影响小说质量；前端重写代价高
- 替代：保留本地现有 dashboard

### 6. Token 压缩整文件替换

- upstream commits: `8bdd18e` `3d64506`
- 拒绝原因：本地 context-agent 755 行多出来的部分是 18 轮 RCA 加固
- 替代：未来手术式压缩（不允许整文件替换）

### 7. v6 chapter_drafted/reviewed/committed 状态机

- upstream commit: `a2a209c`
- 拒绝原因：与本地 chapter_meta.review_metrics.overall_score 评分门控语义不一致
- 替代：本地继续评分门控

### 8. SKILL.md 充分性闸门切到状态机

- upstream commit: `bf013cf`
- 拒绝原因：本地 SKILL.md 是评分驱动多 Step 闸门
- 替代：本地继续多 Step 闸门

### 9. 移除 golden_three_checker / Step 2B legacy

- upstream commit: `80b3503`
- 拒绝原因：feedback_no_skip_2b 明确要求 Step 2B 不可跳
- 替代：本地保留 Step 2B

### 10. Memory contract / scratchpad 大改

- upstream commits: `33ea944` `085c223` `39a1f1b` `2d6762e` `beefb95` `02e9f39`
- 拒绝原因：本地 context-agent 已通过 webnovel.py state/index/extract-context 多 CLI 实现按需加载
- 替代：Phase G hook_trend / Phase E get-recent-meta 已覆盖跨章查询场景

---

**纪律**：每次 git fetch upstream 看到上述类别的新 commit，**直接跳过**，不必每次重新评估。
```

- [ ] **Step 2: ROOT_CAUSE_GUARD_RAILS.md 加 Round 19 段**

如该文件存在，在末尾追加引用：
```markdown
## Round 19 · DO NOT MERGE 长期清单

参 `webnovel-writer/CUSTOMIZATIONS.md` Round 19 立项段。10 类 upstream 改动永久不合并；每次 fetch upstream 跳过这些类别。
```

如不存在则不强制创建。

### Task 7.2: Commit

```bash
git add webnovel-writer/CUSTOMIZATIONS.md ROOT_CAUSE_GUARD_RAILS.md 2>/dev/null
git commit -m "$(cat <<'EOF'
docs(reader-quality): Phase 7 · DO NOT MERGE 永久清单

10 类 upstream 改动永久拒绝合并：
v6 单 reviewer / workflow_manager 移除 / story-system / vector / dashboard /
token 整压缩 / chapter 状态机 / 充分闸门状态机 / golden_three / memory contract

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 8 · Ch12-13 端到端兑现回归（必做 · 4h）

### Task 8.1: 写 Ch12（按既有 webnovel-write 流程）

- [ ] **Step 1: 全流程 Step 0-7**

按 `feedback_must_run_full_review.md` 跑全套审查；不跳步。

观察点：
- context-agent writing_guidance.constraints 含 6 条 Anti-AI 提醒（Phase A）
- writing_guidance.local_blacklist + canon_traps 含私库前 N 条（Phase F）
- reader-naturalness JSON 含 subdimensions + lowest_subdimension（Phase C）
- prose-quality JSON 含 visual_subdimensions（Phase H）
- reader-pull JSON 含 hook_close.primary_type + cross_chapter_trend（Phase G）

### Task 8.2: 写 Ch13（验证连续两章稳定性）

同 Step 1，重点观察：
- Ch13 hook_close.primary_type 与 Ch12 不同（Phase G 跨章趋势提醒生效）
- Ch12-13 reader-naturalness avg 比 Ch1-11 baseline 高 5+

### Task 8.3: 兑现报告

**Files:**
- Create: `docs/superpowers/plans/round19-roi-final-report.md`

- [ ] **Step 1: 跑兑现脚本**

```bash
python -X utf8 - <<'PY' > /tmp/round19_roi.json
import json, sqlite3
from pathlib import Path
proj = Path("末世重生-我在空间里种出了整个基地")

baseline = json.loads((proj / ".webnovel" / "reports" / "quality_baseline.json").read_text(encoding="utf-8"))
state = json.loads((proj / ".webnovel" / "state.json").read_text(encoding="utf-8"))
metas = state.get("chapter_meta", {})

def get_score(ch_str, key):
    cm = metas.get(ch_str, {}) or {}
    sc = cm.get("checker_scores") or {}
    return sc.get(key)

ch12 = "0012"; ch13 = "0013"
report = {
    "baseline_avg": baseline["avg_ch1_11"],
    "ch12": {
        "overall": get_score(ch12, "overall"),
        "naturalness": get_score(ch12, "reader-naturalness-checker"),
        "naturalness_subs": (metas.get(ch12, {}).get("checker_subdimensions") or {}).get("reader-naturalness-checker"),
        "prose": get_score(ch12, "prose-quality-checker"),
        "pull": get_score(ch12, "reader-pull-checker"),
        "hook_close": metas.get(ch12, {}).get("hook_close"),
    },
    "ch13": {
        "overall": get_score(ch13, "overall"),
        "naturalness": get_score(ch13, "reader-naturalness-checker"),
        "naturalness_subs": (metas.get(ch13, {}).get("checker_subdimensions") or {}).get("reader-naturalness-checker"),
        "prose": get_score(ch13, "prose-quality-checker"),
        "pull": get_score(ch13, "reader-pull-checker"),
        "hook_close": metas.get(ch13, {}).get("hook_close"),
    },
}
report["delta_naturalness_ch12"] = (report["ch12"]["naturalness"] or 0) - baseline["avg_ch1_11"].get("reader-naturalness-checker", 0)
report["delta_naturalness_ch13"] = (report["ch13"]["naturalness"] or 0) - baseline["avg_ch1_11"].get("reader-naturalness-checker", 0)
report["delta_prose_ch12"] = (report["ch12"]["prose"] or 0) - baseline["avg_ch1_11"].get("prose-quality-checker", 0)
report["hook_diversity"] = report["ch12"]["hook_close"] != report["ch13"]["hook_close"] if report["ch12"]["hook_close"] and report["ch13"]["hook_close"] else None

print(json.dumps(report, ensure_ascii=False, indent=2))
PY
cat /tmp/round19_roi.json
```

- [ ] **Step 2: 写 markdown 报告**

`docs/superpowers/plans/round19-roi-final-report.md` 内容：

```markdown
# Round 19 兑现报告 · Ch12-13 vs Ch1-11 baseline

> 数据来源：`末世重生-我在空间里种出了整个基地/.webnovel/reports/quality_baseline.json`
> 报告时间：（写报告的真实日期）

## 关键指标

| 指标 | Baseline (Ch1-11) | Ch12 | Ch13 | Δ |
|---|---|---|---|---|
| reader-naturalness | XX | XX | XX | +X / +X |
| prose-quality | XX | XX | XX | +X / +X |
| reader-pull | XX | XX | XX | +X / +X |
| overall | XX | XX | XX | +X / +X |

## Ch12 5 子维度

| 子维度 | 分数 | 命中 issues 数 |
|---|---|---|
| vocab | XX | X |
| syntax | XX | X |
| narrative | XX | X |
| emotion | XX | X |
| dialogue | XX | X |

## 钩子多样性

- Ch12: {primary_type, secondary_type}
- Ch13: {primary_type, secondary_type}
- 多样性: ✅/❌

## 私库回灌效果

- ai-replacement-vocab Ch12 回查命中数：X 处 recurring_violation
- canon-violation-traps Ch12 回查命中：X 处

## 判定

- naturalness +10 → 大成功，全部 Phase 留下
- naturalness +5 → 部分成功
- naturalness +0 或负 → 进 Round 20 RCA，定位回归来源

## 后续行动

（基于上面判定写）
```

### Task 8.4: Commit + 收尾

```bash
git add "末世重生-我在空间里种出了整个基地/.webnovel/reports/quality_baseline.json" \
        docs/superpowers/plans/round19-roi-final-report.md
git commit -m "$(cat <<'EOF'
feat(reader-quality): Phase 8 · Ch12-13 端到端兑现报告

Ch12-13 vs Ch1-11 baseline 各 checker delta + 子维度 + 钩子多样性 + 私库回灌命中
作为 Round 19 收尾兑现凭证

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## 自检（Self-Review）

### 1. 标尺映射

| Phase | 自然度 | 画面感 | 追读力 |
|---|:---:|:---:|:---:|
| 0 基线快照 | ✅ | ✅ | ✅ |
| A anti-ai-guide | ✅ | | |
| I Ch1 钩 | | | ✅ |
| C 5 子维度 | ✅ | | |
| F 4 私库 | ✅ | | ✅（钩子库） |
| G 钩子 4 分类 | | | ✅ |
| B polish 词库 | ✅ | | |
| H 画面感 3 规则 | | ✅ | |
| E plan 跨卷 | | | ✅ |
| D upstream CSV（条件） | ✅ | ✅ | ✅ |
| 7 DO NOT MERGE | （元） | | |
| 8 兑现 | ✅ | ✅ | ✅ |

每个 Phase 都至少有 1 个 ✅ 标尺映射，无对读者无感的项。

### 2. Placeholder scan

- 没有 "TBD" / "implement later" / "类似 Task N"
- 每个 Bash / Edit / Python 都给具体路径与可验证 expected
- 每个 Phase 都有 sync-cache + preflight + hygiene_check 三套验证收尾
- CUSTOMIZATIONS.md 模板 Phase 0/A/I/C/F/G/B/H/E/D/7/8 格式一致

### 3. Type / signature 一致性

- chapter_meta key **全部用 4 位补零字符串**（`'0001'-'0011'`），脚本里用 `f"{ch:04d}"`
- checker key **全部 canonical**（`reader-naturalness-checker` 不是 `reader_naturalness` 不是 `naturalness`）
- 新 CLI 命名一致：`update --set-checker-subdimensions` / `update --set-hook-close` / `get-hook-trend` / `get-recent-meta` / `private-csv` 都遵循 verb-noun
- chapter_meta 下新挂载字段：`checker_subdimensions` (C) / `hook_close` (G)，与既有 `checker_scores` / `review_metrics` 同级
- `subdimensions` 字段在 reader-naturalness (C) 和 prose-quality (H) 都用相同结构（dict + _lowest 计算）
- 私库 CSV (F) 和 upstream CSV (D) 用统一 BM25 编码 UTF-8 BOM；schema 列名 4 表共享 + 表特有列扩展

### 4. 依赖关系

- Phase 0 → 全部
- A / I / B / E / H 互相独立
- C 是 F 的弱依赖（F extractor 用 subdimension 字段）
- G 加 hook_close 字段；F (strong-chapter-end-hooks) extractor 之后再回填 4 类标
- D 条件执行
- Phase 8 必须 A+I+C+F+G 都做完后再做（G 需 11 章已回填 hook_close）
- 中检 W1 在 A+I+C 后 / F 前

### 5. 与本地 RCA 历史的兼容性

| 本地 RCA / feedback | 本计划遵循方式 |
|---|---|
| feedback_review_score_target（90-100） | 不动 13 checker 评分；Phase C/H 加子维度但主分数仍输出 |
| feedback_must_run_full_review | Phase 8 强调跑完整 Step 0-7 |
| feedback_no_skip_steps | Phase 间不并行，一 Phase 一 commit |
| feedback_chinese_quotes | 引号自愈步骤 + 末尾 `--ascii-to-curly` |
| feedback_force_tavily_search | 不影响（本计划改 reference / agent / state，不改搜索路径） |
| feedback_ch7_workflow_must_log | workflow_manager 完全保留 |
| feedback_hygiene_check_before_commit | 每 Phase commit 前必跑 hygiene |
| feedback_no_manual_state_edits | 全部走 state update CLI（含 Phase C/G 新增） |
| feedback_search_in_chinese | 本计划描述全中文 |
| feedback_word_count_target（2200-3500） | 不影响 |
| feedback_checker_count_13 | 13 checker 数量不变 |
| feedback_round10_first_chapter_rubric | Phase I 与 Round 10 rubric 互补，不取代 |
| feedback_pov_disclosure_order | 不影响 |
| feedback_quote_hallucination_false_positive | 不影响 |
| feedback_rca_ch1_disclosure | 不影响（Phase I 是 Ch1 钩，不动披露时序） |
| feedback_ch5_末世重生_root_causes | hygiene check / state update CLI 保留 |
| feedback_ch6_root_causes | core 3 模型 / merge-partial / H11 保留 |
| feedback_ch7_root_causes（17.1） | polish_cycle stage 精确 / preflight 保留 |
| feedback_ch11_root_causes | flow 复测 24min 超时 / canon-aware 优先（Phase F canon-violation-traps 用） |
| feedback_step3.5_external_review (R14) | 14 模型 × 13 维度 = 182 全部保留 |
| feedback_force_force_tavily_search | 不影响 |

---

## 总结

**核心 insight**：fork 已在质量维度上比 upstream v6.0.0 更强；upstream v6 走"轻量化、降 token、少检查"反方向。真正升级路径：

1. **从 upstream 借工具**（v6 之前的好东西，与本地评分体系正交）：anti-ai-guide / polish-guide K/L/M/N + 6 句式 / reader-naturalness 5 子维度 / plan 跨卷感知
2. **基于 11 章 RCA 沉淀私库**（4 张自有 CSV）：这才是别人复制不了的护城河
3. **死磕读者关键指标**（自创 rubric）：首章追读契约 / 章末钩 4 分类 / 画面感 3 子规则——直接量化质量

**35 小时分 3 周**，每 Phase 都映射到自然度 / 画面感 / 追读力其中至少 1 件。映射不到的（v6 token-rewrite / story-system / vector / dashboard / 状态机大改）全部拒绝。

**Round 19 完成后预期**：
- Ch12+ reader-naturalness 从 baseline → +5 至 +10（A + C + F + B 合力）
- Ch12+ prose-quality 视觉子维度 +13（H）
- Ch12+ reader-pull 跨章趋势可观测，钩子分布健康（G）
- Ch1（如重写）完读率显著提升（I）
- 跨卷规划自洽性 ↑（E）
- 重犯率 ↓（F 私库回灌）

**18 轮 102 commit 加固全部保留** —— 这是过去几周堆出来的护城河，不能为了"看起来跟上 upstream"拆掉。
