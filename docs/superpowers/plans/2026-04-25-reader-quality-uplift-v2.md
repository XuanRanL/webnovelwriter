# 读者视角质量提升计划 v2 · 30 小时分 3 周

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把"提升小说质量"重新定义为读者真正在意的三件事——自然度（不像 AI）/ 画面感（具象、感官、节奏）/ 追读力（情绪欠债 + 悬念 + 爽点节奏）；所有改动必须能直接映射到这 3 件事的至少 1 件，否则不做。

**Architecture:** 三条并行注入链——
1. **写作期预防层**（Step 2 起草前 + 起草中即时纠正）
2. **审查期精准化**（5 子维度 + 4 类钩子 + 画面感子规则 + 私库回溯）
3. **跨章趋势追踪**（钩子分类、自建 RCA 私库、第 1 章特殊待遇）

不动 13-checker 评分体系 / 14 外审 / workflow_manager / state.json 真源；所有新增都是**旁路读取 + 子规则补强**。

**Tech Stack:** Python 3.11；fork ↔ plugin cache 双向同步；既有 hygiene_check 24+ H 项；reader-naturalness-checker / reader-pull-checker / prose-quality-checker / emotion-checker 已部署；末世重生项目 11 章 polish_reports + naturalness JSON 已积累作为私库素材。

---

## 0 · 标尺与判断

### 0.1 重新定义"提升小说质量"

读者不会为"upstream 用了 story_system 还是 workflow_manager"多看一章。追读理由只有 3 件：

| 标尺 | 读者实际感受 | fork 现有覆盖 | 缺口 |
|---|---|---|---|
| **自然度** | 不像 AI 写的 | reader-naturalness-checker（事后退稿）+ polish-guide 200+ 高频词库 | 缺起草前预防 + 缺 5 子维度反馈细化 + 缺血教训私库自动回灌 |
| **画面感** | 看得见、闻得到、节奏对 | prose-quality-checker（综合分） | 缺"画面感"子规则（视觉锚点 / 非视觉感官 / 抽象动作触发改写） |
| **追读力** | 想看下一章 | reader-pull-checker（钩子强度 0-100 单数字） | 缺 4 类钩子分类（信息 / 情绪 / 决策 / 动作）+ 跨章趋势 + Ch1 特殊 rubric |

任何"升级"映射不到上面 3 件之一，本计划直接拒绝（包括 upstream 的 story-system / vector / dashboard / token-rewrite 等）。

### 0.2 三类来源

| 来源 | 用途 | 风险 |
|---|---|---|
| **上游借工具**（v6 之前的好东西） | anti-ai-guide 起草预防 / polish-guide 4 类新词库 / reviewer 5 子维度 rubric / plan 跨卷感知 | 低，纯 additive，不引 v6 评分体系替换 |
| **自建私库**（基于 11 章 RCA） | 私 4 张 CSV：AI 替代词 / 章末钩子优秀模板 / 情感 earned-vs-forced 反例 / 本作设定禁区 | 零，从已有数据派生 |
| **死磕读者指标**（自创 rubric） | Ch1 开篇钩 9+3 / 章末钩子 4 分类 / 画面感 3 子规则 | 零，纯子规则补强 |

### 0.3 ROI 排序与执行排程

| 优先级 | 项目 | 来源 | 直接映射 | 工作量 |
|---|---|---|---|---|
| P0-1 | A. anti-ai-guide.md 起草预防层 | 上游 | 自然度 | 1h |
| P0-2 | I. Ch1 开篇钩 rubric 升级 | 自创 | 追读力 | 2h |
| P1-1 | C. reviewer ai_flavor 5 子维度 → reader-naturalness-checker | 上游借鉴 | 自然度 | 3h |
| P1-2 | F. 自建 4 张私库 CSV（从 11 章 RCA 自动提取） | 自创 | 自然度 + 设定一致性 | 8h |
| P1-3 | G. 章末钩子 4 分类跨章追踪 | 自创 | 追读力 | 4h |
| P2-1 | B. polish-guide 4 类新词库吸收 | 上游 | 自然度 | 2h |
| P2-2 | H. 画面感 3 子规则 → prose-quality-checker | 自创 | 画面感 | 3h |
| P2-3 | E. plan 跨卷感知 | 上游 | 追读力 | 1h |
| P3-1 | D. CSV 9 张知识表（视干货度决定） | 上游 | 全部 | 4h |
| P3-2 | knowledge_query temporal API | 上游 | 设定一致性辅助 | 2h |
| ❌ | upstream token-efficiency rewrite | — | — | 拒绝 |
| ❌ | story-system / vector / memory_contract | — | — | 拒绝 |
| ❌ | dashboard / hooks / chapter status 状态机 | — | — | 拒绝 |

**3 周分摊**：
- W1：A + I（5h）→ Ch12 基线验证 → C（3h）→ Ch12 复测
- W2：F 自建私库（8h）→ G 钩子分类（4h）→ B（2h）
- W3：H 画面感（3h）→ E plan 跨卷（1h）→ D 视情况（4h）

### 0.4 操作纪律

- 每个 Phase 独立 commit：`feat(reader-quality): Phase X · ...`
- 改 fork 文件后必跑：`webnovel.py sync-cache` + `preflight` + `末世重生-我在空间里种出了整个基地/.webnovel/hygiene_check.py`，三个都 exit=0 才能 commit
- CUSTOMIZATIONS.md 每 Phase 追加变更日志（含 upstream commit 引用 / 私库脚本路径 / 验证数据）
- 严禁 `git merge upstream/master`；upstream 取文件用 `git show upstream/master:<path>` 手动 Read + Write
- 每 Phase 完成后 Ch12 / Ch13 实际写作期回灌兑现数据，不达标进 RCA 修补

### 0.5 验证项目

末世重生-我在空间里种出了整个基地（11 章已成稿）作为基线项目。Ch12 起所有新机制都在该项目上跑。

---

## 1 · 文件结构

```
webnovel-writer/
├── skills/webnovel-write/references/
│   ├── anti-ai-guide.md                                  # NEW · Phase A
│   ├── first-chapter-hook-rubric.md                      # NEW · Phase I（首章 9+3 rubric 文档化）
│   ├── chapter-end-hook-taxonomy.md                      # NEW · Phase G（4 类钩子分类规范）
│   ├── visual-concreteness-rubric.md                     # NEW · Phase H（画面感子规则）
│   └── polish-guide.md                                   # Modify · Phase B（吸收 4 类新词库到既有 7 层）
├── agents/
│   ├── reader-naturalness-checker.md                     # Modify · Phase C（升级到 5 子维度评分）
│   ├── reader-pull-checker.md                            # Modify · Phase G + I（钩子分类 + 首章 rubric）
│   ├── prose-quality-checker.md                          # Modify · Phase H（画面感 3 子规则）
│   └── context-agent.md                                  # Modify · Phase A + F（加载预防层 + 私库提醒）
├── references/private-csv/                               # NEW · Phase F（自建私库目录）
│   ├── README.md
│   ├── ai-replacement-vocab.csv                          # 18 轮 RCA 抓到的 AI 词→替代词对
│   ├── strong-chapter-end-hooks.csv                      # reader-pull ≥ 90 的章末模板
│   ├── emotion-earned-vs-forced.csv                      # emotion-checker 反例
│   └── canon-violation-traps.csv                         # consistency-checker 抓过的设定漏洞
├── scripts/
│   ├── private_csv_extractor.py                          # NEW · Phase F（从 polish_reports + tmp/*.json 自动提取私库）
│   └── data_modules/
│       └── webnovel.py                                   # Modify · Phase F（加 private-csv 子命令转发）
├── skills/webnovel-plan/
│   └── SKILL.md                                          # Modify · Phase E（跨卷读 write history）
└── CUSTOMIZATIONS.md                                     # Modify · 每 Phase 追加

末世重生-我在空间里种出了整个基地/.webnovel/
├── private_csv/                                          # NEW · Phase F（项目本地私库，提取脚本输出）
└── reports/quality_baseline.json                         # NEW · Phase 0（Ch1-11 基线快照）
```

---

## Phase 0 · 基线快照（30 min）

### Task 0.1: 锁定 Ch1-11 质量基线

**Files:**
- Create: `末世重生-我在空间里种出了整个基地/.webnovel/reports/quality_baseline.json`
- Create: `docs/superpowers/plans/upstream-snapshot/COMMIT_REF.txt`

- [ ] **Step 1: 锁 upstream + main commit hash**

```bash
mkdir -p docs/superpowers/plans/upstream-snapshot
{ git rev-parse upstream/master; git log -1 --format="%H %ai %s" upstream/master; \
  git rev-parse main; git log -1 --format="%H %ai %s" main; \
  git merge-base main upstream/master; } \
  > docs/superpowers/plans/upstream-snapshot/COMMIT_REF.txt
cat docs/superpowers/plans/upstream-snapshot/COMMIT_REF.txt
```

Expected: 包含 upstream HEAD `1d7c952`、main HEAD `84249bd`、merge-base `535d60d`。

- [ ] **Step 2: 提取 Ch1-11 各 checker 评分基线**

```bash
mkdir -p 末世重生-我在空间里种出了整个基地/.webnovel/reports
python -X utf8 - <<'PY'
import sqlite3, json
from pathlib import Path
proj = Path("末世重生-我在空间里种出了整个基地")
conn = sqlite3.connect(str(proj / ".webnovel" / "index.db"))
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT chapter, overall_score FROM review_metrics WHERE chapter <= 11 ORDER BY chapter").fetchall()
data = {"chapters": [dict(r) for r in rows]}
data["overall_avg"] = round(sum(r["overall_score"] or 0 for r in rows) / max(1, len(rows)), 2)
out = proj / ".webnovel" / "reports" / "quality_baseline.json"
out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print("baseline overall_avg =", data["overall_avg"])
PY
```

Expected: 输出 `baseline overall_avg = XX.XX`（约 86-90）。

- [ ] **Step 3: 提取 Ch1-11 reader-naturalness / reader-pull / prose-quality 各分项**

```bash
python -X utf8 - <<'PY'
import sqlite3, json
from pathlib import Path
proj = Path("末世重生-我在空间里种出了整个基地")
conn = sqlite3.connect(str(proj / ".webnovel" / "index.db"))
conn.row_factory = sqlite3.Row
state_path = proj / ".webnovel" / "state.json"
state = json.loads(state_path.read_text(encoding="utf-8"))
checker_avg = {k: 0 for k in ["reader_naturalness","reader_pull","prose_quality","high_point","emotion","consistency","pacing","ooc","dialogue","density","continuity","reader_critic","reader_flow"]}
counts = {k: 0 for k in checker_avg}
for ch_str, meta in state.get("chapter_meta", {}).items():
    scores = (meta or {}).get("checker_scores") or {}
    for k in checker_avg:
        v = scores.get(k)
        if isinstance(v, (int, float)):
            checker_avg[k] += v; counts[k] += 1
for k in checker_avg:
    if counts[k]:
        checker_avg[k] = round(checker_avg[k] / counts[k], 2)
report = proj / ".webnovel" / "reports" / "quality_baseline.json"
data = json.loads(report.read_text(encoding="utf-8"))
data["checker_avg_ch1_11"] = checker_avg
data["checker_counts"] = counts
report.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(checker_avg, ensure_ascii=False, indent=2))
PY
```

Expected：每个 checker 给出 Ch1-11 平均分。这些数字是 Ch12+ 兑现的对比基线。

- [ ] **Step 4: Commit 基线**

```bash
git add docs/superpowers/plans/upstream-snapshot/COMMIT_REF.txt \
        末世重生-我在空间里种出了整个基地/.webnovel/reports/quality_baseline.json \
        docs/superpowers/plans/2026-04-25-reader-quality-uplift-v2.md
git commit -m "plan(reader-quality): v2 计划 + Ch1-11 质量基线快照"
```

---

## Phase A · anti-ai-guide.md 起草预防层（P0 · 1h）

> 直接映射：**自然度**。读者一看就知道是 AI 写的，因为副词堆叠、瞳孔微缩、心中一凛。事前预防比事后退稿便宜 10 倍。

### Task A.1: 引入 anti-ai-guide.md

**Files:**
- Create: `webnovel-writer/skills/webnovel-write/references/anti-ai-guide.md`

- [ ] **Step 1: 抓 upstream 内容**

```bash
git show upstream/master:webnovel-writer/skills/webnovel-write/references/anti-ai-guide.md \
  > webnovel-writer/skills/webnovel-write/references/anti-ai-guide.md
wc -l webnovel-writer/skills/webnovel-write/references/anti-ai-guide.md
```

Expected: 74 行，UTF-8。

- [ ] **Step 2: 末尾追加本地接入说明**

用 Edit 工具在文件末尾追加：

```markdown

---

## 本地 fork 接入（Round 19 / 5.6.0）

- **加载时机**：Step 2 起草正文前，由 SKILL.md Step 2 references 列表加载
- **与 polish-guide.md 的关系**：本文件是**起草期预防**（8 倾向 + 即时检查 + 替代速查表）；polish-guide 是**polish 期检测+修复**（7 层规则、200+ 高频词库、anti_ai_force_check）。二者**互补**，不取代
- **预期效果**：Ch12+ reader-naturalness-checker 首稿评分从 78-85 → 88-95，polish 周期数从 2-3 → 1-2 轮
- **不引入的 upstream 配套**：upstream `docs/specs/2026-04-03-ai-writing-quirks.md`（148 行 6 层 60+ 癖好全景图）暂不引入，避免与本文件 + polish-guide 冗余；如需扩展，在私库 `references/private-csv/ai-replacement-vocab.csv` 补充
```

### Task A.2: SKILL.md Step 2 加载点

**Files:**
- Modify: `webnovel-writer/skills/webnovel-write/SKILL.md`

- [ ] **Step 1: 定位 Step 2 references 加载段**

```bash
grep -n "core-constraints\|style-adapter\|references/" webnovel-writer/skills/webnovel-write/SKILL.md | head -10
```

- [ ] **Step 2: 用 Edit 把现有 Step 2 加载列表追加 anti-ai-guide.md**

将形如：

```
- references/core-constraints.md
- references/style-adapter.md
```

替换为：

```
- references/core-constraints.md
- references/style-adapter.md
- references/anti-ai-guide.md（Round 19 新增 · Step 2 起草前预防 AI 腔，与 polish-guide.md 检测层互补）
```

### Task A.3: context-agent 创作执行包注入 Anti-AI 提醒

**Files:**
- Modify: `webnovel-writer/agents/context-agent.md`

- [ ] **Step 1: 在核心参考段追加 anti-ai-guide 引用**

定位 context-agent.md 第 12-14 行核心参考列表，追加：

```
- **Anti-AI 起草预防**: `${CLAUDE_PLUGIN_ROOT}/skills/webnovel-write/references/anti-ai-guide.md`（Round 19 · Step 2 起草前消费 · 8 倾向 + 即时检查 + 替代速查表）
```

- [ ] **Step 2: 在创作执行包 writing_guidance.constraints 输出段强制注入 6 条提醒**

定位 context-agent 输出 schema 段，在 `writing_guidance` 对象内追加（或在 constraints 数组生成逻辑里硬编码 6 条最低）：

```markdown
**Anti-AI 提醒（writing_guidance.constraints 必含至少 6 条具体提醒）**：
1. 删段末感悟句，留余味（避免起因→经过→结果→感悟四段闭环）
2. 删万能副词"缓缓/淡淡/微微/轻轻"，换具体动作或前置动作
3. 情绪用生理反应+微动作（如"指节捏得发白""舌尖尝到铁锈味"），禁止"他感到X"
4. 角色专属微动作（咬笔帽=焦虑、拧手表=不耐烦），禁止全员"瞳孔微缩"
5. 章末禁止安全着陆（冲突完美解决），留至少 1 个未解决的问题
6. 展示后不解释（删"他显然很生气"），信任读者
完整 8 倾向 + 替代速查表见 `${CLAUDE_PLUGIN_ROOT}/skills/webnovel-write/references/anti-ai-guide.md`
```

### Task A.4: sync-cache + 验证 + commit

- [ ] **Step 1: sync + preflight + hygiene**

```bash
python -X utf8 webnovel-writer/scripts/data_modules/webnovel.py sync-cache
python -X utf8 webnovel-writer/scripts/data_modules/webnovel.py preflight
python -X utf8 末世重生-我在空间里种出了整个基地/.webnovel/hygiene_check.py
```

三条全部 exit=0。

- [ ] **Step 2: 在 CUSTOMIZATIONS.md 顶部插入 Phase A 段**

```markdown
## [2026-04-25 · Round 19 Phase A] anti-ai-guide.md 起草预防层

upstream 1d7c952 引入 Step 2 起草前 Anti-AI 预防 reference。本地全程缺"起草前预防"层，AI 腔靠 polish_cycle 反复修。

| # | 文件 | 改动 | 行数 |
|---|------|------|------|
| 1 | `skills/webnovel-write/references/anti-ai-guide.md` | NEW（upstream@f774f2b 1:1 + 本地接入说明） | +89 |
| 2 | `skills/webnovel-write/SKILL.md` | Step 2 references 加 anti-ai-guide | +1 |
| 3 | `agents/context-agent.md` | 核心参考 + writing_guidance.constraints 6 条硬注入 | +9 |

预期效果：Ch12+ reader-naturalness-checker 首稿 +10 分，polish 周期 -1 轮。
互补关系：本文件起草期预防；polish-guide.md 仍负责 polish 期检测+修复。
```

- [ ] **Step 3: Commit**

```bash
git add webnovel-writer/skills/webnovel-write/references/anti-ai-guide.md \
        webnovel-writer/skills/webnovel-write/SKILL.md \
        webnovel-writer/agents/context-agent.md \
        webnovel-writer/CUSTOMIZATIONS.md
git commit -m "feat(reader-quality): Phase A · anti-ai-guide.md 起草预防层 · upstream@f774f2b"
```

---

## Phase I · Ch1 开篇钩 9+3 rubric 升级（P0 · 2h）

> 直接映射：**追读力**。网文平台第 1 章前 300 字决定弃读还是追读。fork 现有 first-chapter-rubric 9 项偏"安全检查"，缺"读者承诺信号"。

### Task I.1: 写 first-chapter-hook-rubric.md

**Files:**
- Create: `webnovel-writer/skills/webnovel-write/references/first-chapter-hook-rubric.md`

- [ ] **Step 1: 新建文件**

```markdown
---
name: first-chapter-hook-rubric
purpose: 第 1 章专属"读者 3 秒决定追读"硬规则，加在既有 9 项严格 rubric（feedback_round10_first_chapter_rubric.md）之上
---

# 第 1 章追读契约 rubric（Round 19）

> **核心 insight**：网文平台读者在第 1 章前 300 字决定弃读还是追读。前 300 字必须签下"情绪契约"——告诉读者继续读能拿到什么。

## 既有 9 项严格规则（来自 Round 10）

见 `feedback_round10_first_chapter_rubric.md`：金手指时序 / 大纲兑现 / 核心悬念保护 / 认知载入 / distress 具身 / 反派博弈 / 等。

## Round 19 新增 3 项追读契约规则

### A. 首句钩（critical）

第 1 句**必须**含至少 1 项：
- 冲突信号（"她举起斧头时，门外的笑声还在持续"）
- 反差信号（"病房 305 号的男人已经死了七天，但今天他终于决定起床"）
- 悬念信号（"第三次，林夏又看见了那扇不该存在的门"）

**禁止**：天气描写 / 姓名介绍 / 时代背景介绍 / "今天是 X 月 X 日" / 任何说明性首句。

命中违例 → reader-pull-checker 直接给 critical issue，blocking=true。

### B. 第 1 段=承诺（high）

第 1 段（≤ 200 字）结束前**必须**给读者"这书会爽在哪"的信号至少 1 条：
- 主角的反差身份（弱者→强者 / 普通人→天选 / 失败者→翻身）
- 待解的核心冲突（仇 / 谜 / 限期 / 不可能任务）
- 主角的核心动机（为什么这事必须做）

**禁止**：第 1 段全是环境描写或心理活动；第 1 段不暗示卖点。

### C. 300 字内必有"金手指或核心冲突触发器"（high）

正文开头 300 字内**必须**出现：
- 金手指首次显形（哪怕是部分）
- 或核心冲突触发器（杀手登门 / 末世广播响起 / 系统绑定 / 倒计时启动）

**禁止**：开头 500+ 字全是回忆 / 日常 / 内心独白；金手指延迟到 1000 字后。

## 自检表（reader-pull-checker 评第 1 章时强制走）

| 项 | 通过条件 | 不通过扣分 |
|---|---|---|
| A 首句钩 | 含冲突/反差/悬念信号之一 | -10 |
| B 第 1 段承诺 | 含反差身份/核心冲突/核心动机之一 | -8 |
| C 300 字内触发器 | 含金手指或核心冲突触发器 | -10 |
| 完读率信号（综合 A/B/C） | 三项至少 2 项达标 | 直接 verdict=REWRITE_RECOMMENDED |

## 跨章衔接

第 2-3 章每章末必须留至少 1 个由第 1 章悬念衍生的子悬念，避免"开篇炸街中段平淡"读者期待落空。
```

### Task I.2: reader-pull-checker 接入 first-chapter rubric

**Files:**
- Modify: `webnovel-writer/agents/reader-pull-checker.md`

- [ ] **Step 1: 找到第 1 章特殊处理段**

```bash
grep -n "第 1 章\|chapter == 1\|首章\|Ch1\|first" webnovel-writer/agents/reader-pull-checker.md | head -10
```

- [ ] **Step 2: 加 Round 19 段**

在 reader-pull-checker.md 的"第 1 章"或"特殊章节"段追加：

```markdown
### 第 1 章额外检查（Round 19）

仅当 `chapter == 1` 时强制走 `${CLAUDE_PLUGIN_ROOT}/skills/webnovel-write/references/first-chapter-hook-rubric.md` 的 A/B/C 三项追读契约：

- A 首句钩缺失 → critical issue, fix_hint = "首句必须含冲突/反差/悬念信号"
- B 第 1 段承诺缺失 → high issue, fix_hint = "第 1 段必须暗示卖点（反差身份/核心冲突/核心动机）"
- C 300 字内触发器缺失 → high issue, fix_hint = "300 字内必须显形金手指或核心冲突触发器"

任何 critical 直接 verdict=REWRITE_RECOMMENDED；2 个 high 也升级为 REWRITE_RECOMMENDED。
```

### Task I.3: SKILL.md 加首章 rubric 加载点

**Files:**
- Modify: `webnovel-writer/skills/webnovel-write/SKILL.md`

- [ ] **Step 1: 在 SKILL.md 第 1 章特殊处理段**追加 references 加载

```
- 当 chapter == 1：额外加载 `references/first-chapter-hook-rubric.md`（Round 19 · 追读契约 A/B/C 三项硬规则）
```

### Task I.4: 验证 + commit

- [ ] **Step 1: sync + preflight + hygiene 三套**

同 Phase A.4 Step 1。

- [ ] **Step 2: CUSTOMIZATIONS.md 加 Phase I 段**

```markdown
## [2026-04-25 · Round 19 Phase I] Ch1 追读契约 9+3 rubric

网文平台第 1 章前 300 字决定弃读率。Round 10 已加 9 项严格 rubric（金手指时序/大纲兑现等"安全检查"），Round 19 补 3 项"读者承诺信号"。

| # | 文件 | 改动 |
|---|------|------|
| 1 | `skills/webnovel-write/references/first-chapter-hook-rubric.md` | NEW · A/B/C 三项追读契约 |
| 2 | `agents/reader-pull-checker.md` | 第 1 章强制走 A/B/C；critical → REWRITE |
| 3 | `skills/webnovel-write/SKILL.md` | chapter==1 加载 first-chapter-hook-rubric |

预期效果：Ch1 完读率（网文平台命门指标）显著提升；首句不再写天气；前 300 字必有金手指或冲突触发器。
```

- [ ] **Step 3: Commit**

```bash
git add webnovel-writer/skills/webnovel-write/references/first-chapter-hook-rubric.md \
        webnovel-writer/agents/reader-pull-checker.md \
        webnovel-writer/skills/webnovel-write/SKILL.md \
        webnovel-writer/CUSTOMIZATIONS.md
git commit -m "feat(reader-quality): Phase I · Ch1 追读契约 9+3 rubric"
```

---

## Phase C · reader-naturalness-checker 升级 5 子维度（P1 · 3h）

> 直接映射：**自然度**。现在 reader-naturalness-checker 反馈是"AI 味重，分数 78"——修起来打地鼠。upstream `5339e83` 把它细化成 5 子维度（词汇 / 句式 / 叙事 / 情感 / 对话），反馈变成"句式层 70（长句过多），叙事层 60（每段闭环），对话层 65（缺潜台词）"——精准定向修。

### Task C.1: reader-naturalness-checker.md 升级到 5 子维度

**Files:**
- Modify: `webnovel-writer/agents/reader-naturalness-checker.md`

- [ ] **Step 1: 备份现有文件**

```bash
cp webnovel-writer/agents/reader-naturalness-checker.md \
   webnovel-writer/agents/reader-naturalness-checker.md.bak_pre_round19
```

- [ ] **Step 2: 在评分段插入 5 子维度 rubric（保留现有 Ch11 血教训等本地段）**

定位现有"评分维度"段，将单数字评分扩展为 5 子维度：

```markdown
## 评分（Round 19 升级 · 5 子维度结构化）

> 不再输出单一 reader_naturalness 分数，改为 5 子维度各 0-100，主分数 = 5 子维度算术平均。
> 反馈给 polish_cycle 时**必须**指明哪个子维度低，否则 polish 无法定向修。

### 子维度 1: 词汇层（vocab）

- 高频 AI 词汇密度（参考 polish-guide K/L/M/N 类）
- "缓缓/淡淡/微微"+动词 在 500 字内 ≥ 3 次
- "眸中闪过""瞳孔微缩"等神态模板出现
- 万能副词（缓缓/淡淡/微微/轻轻/静静/默默/悄悄/慢慢/渐渐/暗暗）密度

扣分：个别命中 -3；密集（5+ 处） -10。

### 子维度 2: 句式层（syntax）

- "起因→经过→结果→感悟"四段闭环
- 连续同构句（≥3 句主谓宾结构一致）
- 每段以总结句收尾（"他终于明白了""由此可见"）
- 同一信息用不同句式重复说 2-3 遍

扣分：闭环 -8；同构句 -5；总结句 -5；重复 -5。

### 子维度 3: 叙事层（narrative）

- 节奏匀速（段落信息密度过于均匀，无快慢）
- "他不知道的是……""殊不知……"戏剧性反讽提示
- 章末"安全着陆"（冲突完美解决，无遗留）
- 展示后紧跟解释（动作展示后一句话解释）

扣分：匀速 -5；反讽提示 -3；安全着陆 -10；展示后解释 -5。

### 子维度 4: 情感层（emotion）

- 情绪标签化（"他感到愤怒""她非常紧张"）
- 情绪即时切换（无过渡）
- 全员同款反应模板（全员"瞳孔微缩"）

扣分：标签化 -10；即时切换 -5；同款模板 -8。

### 子维度 5: 对话层（dialogue）

- 信息宣讲（解释背景而非推进冲突）
- 全员书面语、无口语特征、无个人口癖
- 对白后跟解释性叙述（"他这么说是因为……"）

扣分：信息宣讲 -10；全员书面 -8；解释性叙述 -5。

### 主分数计算

```
reader_naturalness = round(mean(vocab, syntax, narrative, emotion, dialogue), 2)
```

### 输出 schema 扩展

```json
{
  "reader_naturalness": 88,
  "subdimensions": {
    "vocab": 92, "syntax": 78, "narrative": 85, "emotion": 90, "dialogue": 95
  },
  "lowest_subdimension": "syntax",
  "verdict": "PASS | NEEDS_POLISH | REWRITE_RECOMMENDED",
  "issues": [...]
}
```

polish_cycle 必须读 `lowest_subdimension` 优先修该子维度。
```

- [ ] **Step 3: 保留 Ch11 方言血教训段（不删）**

确保以下段不被覆盖：
```
**血教训**（Ch11）：本审查器把"得味"误判为武汉方言、"嗯呐"误判为东北方言并给 critical...
```

如不慎覆盖，从 .bak 文件恢复该段。

### Task C.2: data-agent + state_manager 接受新 schema

**Files:**
- Modify: `webnovel-writer/agents/data-agent.md`
- Modify: `webnovel-writer/scripts/data_modules/state_manager.py`

- [ ] **Step 1: data-agent 写 chapter_meta 时把 subdimensions 落库**

定位 data-agent.md 写 chapter_meta 段，追加：

```markdown
### Round 19 · reader-naturalness 5 子维度落库

读 `tmp/naturalness_check_ch{NNNN}.json` 时，除主分数外提取 `subdimensions` 子维度对象，写入：

```json
chapter_meta.checker_scores.reader_naturalness        // 主分数（兼容老 schema）
chapter_meta.checker_subdimensions.reader_naturalness // 新增 · 5 子维度对象
```

如 JSON 缺 subdimensions 字段（来自老 checker 版本），写空 dict `{}` 兜底。
```

- [ ] **Step 2: state_manager.py CLI 加 set-checker-subdimension**

定位 state_manager.py `set-checker-score` 子命令，旁加：

```python
# Round 19: 子维度 setter
p_set_sub = sp.add_parser("set-checker-subdimension")
p_set_sub.add_argument("--chapter", type=int, required=True)
p_set_sub.add_argument("--checker", required=True)
p_set_sub.add_argument("--subdimensions", required=True, help="JSON dict")
```

dispatch：

```python
elif args.cmd == "set-checker-subdimension":
    subdims = json.loads(args.subdimensions)
    state["chapter_meta"][str(args.chapter)].setdefault("checker_subdimensions", {})[args.checker] = subdims
    write_state(state)
```

### Task C.3: polish_cycle 读 lowest_subdimension 定向修

**Files:**
- Modify: `webnovel-writer/scripts/polish_cycle.py`（如存在）或 `webnovel-writer/agents/post-commit-polish-agent.md`

- [ ] **Step 1: 找到 polish_cycle 读 naturalness 分数的位置**

```bash
grep -rn "reader_naturalness\|lowest_sub" webnovel-writer/scripts/polish_cycle.py webnovel-writer/skills/webnovel-write/references/post-commit-polish.md 2>&1 | head
```

- [ ] **Step 2: 加 lowest_subdimension 优先逻辑**

在 polish 决策段，把：

```python
if metrics.get("reader_naturalness", 100) < 75:
    polish_targets.append("reader_naturalness")
```

替换为：

```python
nat_score = metrics.get("reader_naturalness", 100)
if nat_score < 75:
    sub = metrics.get("subdimensions") or {}
    if sub:
        lowest = min(sub, key=lambda k: sub[k])
        polish_targets.append(f"reader_naturalness:{lowest}")  # 定向到子维度
    else:
        polish_targets.append("reader_naturalness")
```

### Task C.4: sync + verify + commit

- [ ] **Step 1: 三套验证**

```bash
python -X utf8 webnovel-writer/scripts/data_modules/webnovel.py sync-cache
python -X utf8 webnovel-writer/scripts/data_modules/webnovel.py preflight
python -X utf8 末世重生-我在空间里种出了整个基地/.webnovel/hygiene_check.py
```

- [ ] **Step 2: CUSTOMIZATIONS.md 加 Phase C 段**（参考 Phase A 格式 · 引用 upstream@5339e83）

- [ ] **Step 3: commit**

```bash
git add webnovel-writer/agents/reader-naturalness-checker.md \
        webnovel-writer/agents/data-agent.md \
        webnovel-writer/scripts/data_modules/state_manager.py \
        webnovel-writer/scripts/polish_cycle.py \
        webnovel-writer/CUSTOMIZATIONS.md
# 不 commit .bak_pre_round19 文件（应在 .gitignore）
git commit -m "feat(reader-quality): Phase C · reader-naturalness-checker 5 子维度 · upstream@5339e83"
```

---

## Phase F · 自建 4 张私库 CSV（P1 · 8h · 自创核心护城河）

> **这才是别人复制不了的护城河**。fork 已经写过 11 章，每章每个 checker 都留下 JSON + 报告。这些数据可以自动提取成可机读 CSV，再回灌到 writer / polish / checker——下次不再重犯。

### Task F.1: 设计 4 张私库表 schema

**Files:**
- Create: `webnovel-writer/references/private-csv/README.md`
- Create: `webnovel-writer/references/private-csv/ai-replacement-vocab.csv`（空表）
- Create: `webnovel-writer/references/private-csv/strong-chapter-end-hooks.csv`（空表）
- Create: `webnovel-writer/references/private-csv/emotion-earned-vs-forced.csv`（空表）
- Create: `webnovel-writer/references/private-csv/canon-violation-traps.csv`（空表）

- [ ] **Step 1: 建目录 + README**

```bash
mkdir -p webnovel-writer/references/private-csv
```

写 README.md：

```markdown
# 私库 CSV（基于 18 轮 RCA + Ch1-11 实战数据沉淀）

## 4 张表

| 表 | 用途 | 提取来源 |
|---|---|---|
| `ai-replacement-vocab.csv` | AI 词→替代词对，writer 起草前查 + polish 修 | `tmp/naturalness_check_ch*.json` 的 issues + polish_log notes |
| `strong-chapter-end-hooks.csv` | reader-pull ≥ 90 的章末模板，writer 写章末时参考 | `tmp/reader_pull_ch*.json` + 章节正文末段 |
| `emotion-earned-vs-forced.csv` | emotion-checker 抓到的"earned vs forced"反例与正例 | `tmp/emotion_check_ch*.json` |
| `canon-violation-traps.csv` | consistency-checker 抓过的设定漏洞 | `tmp/consistency_check_ch*.json` + audit_reports |

## schema（所有 4 张表共享）

| 列 | 必填 | 说明 |
|---|---|---|
| `编号` | 是 | 表前缀 + 序号（AV-001 / SH-001 / EE-001 / CV-001） |
| `章节` | 是 | 提取自第几章 |
| `严重度` | 是 | critical / high / medium / low |
| `坏样本` | 视表 | 原文引用（违例文本） |
| `好样本` | 视表 | 替代或正例（如果有） |
| `子维度` | 表 1 必填 | vocab / syntax / narrative / emotion / dialogue |
| `钩子类型` | 表 2 必填 | 信息钩 / 情绪钩 / 决策钩 / 动作钩 |
| `情感类型` | 表 3 必填 | earned / forced |
| `禁区类型` | 表 4 必填 | 战力越权 / 时间线漂移 / 关系漂移 / 设定矛盾 |
| `修复方向` | 是 | 一句话 fix_hint |
| `源 RCA` | 否 | 关联 CUSTOMIZATIONS.md Round 编号 |

UTF-8 with BOM；新增条目用 `private_csv_extractor.py` 自动提取或手动追加。
```

- [ ] **Step 2: 4 张 CSV 写表头行（空数据）**

每张表头按 schema 列出（写入文件即可）。

### Task F.2: 写自动提取脚本

**Files:**
- Create: `webnovel-writer/scripts/private_csv_extractor.py`

- [ ] **Step 1: 实现核心逻辑**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
私库 CSV 自动提取器（Round 19）

输入：项目 .webnovel/tmp/*.json + .webnovel/polish_reports/*.md + state.json
输出：webnovel-writer/references/private-csv/*.csv 追加新条目（不重复）

用法:
    python private_csv_extractor.py --project 末世重生-我在空间里种出了整个基地 \
                                    --table ai-replacement-vocab \
                                    --chapters 1-11
"""
from __future__ import annotations
import argparse, csv, json, re, sys
from pathlib import Path
from typing import Dict, List

CSV_HEADERS = {
    "ai-replacement-vocab": ["编号","章节","严重度","坏样本","好样本","子维度","修复方向","源RCA"],
    "strong-chapter-end-hooks": ["编号","章节","严重度","坏样本","好样本","钩子类型","修复方向","源RCA"],
    "emotion-earned-vs-forced": ["编号","章节","严重度","坏样本","好样本","情感类型","修复方向","源RCA"],
    "canon-violation-traps": ["编号","章节","严重度","坏样本","好样本","禁区类型","修复方向","源RCA"],
}

PREFIX = {
    "ai-replacement-vocab": "AV",
    "strong-chapter-end-hooks": "SH",
    "emotion-earned-vs-forced": "EE",
    "canon-violation-traps": "CV",
}

def load_existing_rows(csv_path: Path) -> List[Dict[str, str]]:
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
    for r in existing:
        if r.get("章节") == new_row.get("章节") and r.get("坏样本") == new_row.get("坏样本"):
            return True
    return False

def extract_ai_replacement_vocab(project_root: Path, chapters: range) -> List[Dict[str, str]]:
    """从 tmp/naturalness_check_ch*.json 提取 AI 词违例"""
    rows = []
    tmp = project_root / ".webnovel" / "tmp"
    for ch in chapters:
        for pattern in [f"naturalness_check_ch{ch:04d}.json",
                        f"naturalness_check_ch{ch:04d}_v2.json"]:
            p = tmp / pattern
            if not p.exists(): continue
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            for issue in (data.get("issues") or []):
                cat = (issue.get("category") or "").lower()
                if "ai_flavor" not in cat and "ai" not in cat: continue
                rows.append({
                    "章节": str(ch),
                    "严重度": issue.get("severity", "medium"),
                    "坏样本": (issue.get("evidence") or "")[:200],
                    "好样本": (issue.get("fix_hint") or "")[:200],
                    "子维度": issue.get("subdimension", "vocab"),
                    "修复方向": (issue.get("fix_hint") or "")[:120],
                    "源RCA": "",
                })
    return rows

def extract_chapter_end_hooks(project_root: Path, chapters: range) -> List[Dict[str, str]]:
    """从 reader_pull_ch*.json + 章节末段抓 ≥ 90 模板"""
    rows = []
    tmp = project_root / ".webnovel" / "tmp"
    text_dir = project_root / "正文"
    for ch in chapters:
        p = tmp / f"reader_pull_ch{ch:04d}.json"
        if not p.exists(): continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        score = data.get("reader_pull") or data.get("score") or 0
        if score < 90: continue
        # 找正文末段
        candidates = list(text_dir.glob(f"第{ch:04d}章*.md"))
        if not candidates: continue
        text = candidates[0].read_text(encoding="utf-8")
        # 取末尾 200 字
        last_chunk = text.strip().split("\n\n")[-1][-200:]
        hook_type = (data.get("hook_type") or "信息钩")
        rows.append({
            "章节": str(ch),
            "严重度": "low",
            "坏样本": "",
            "好样本": last_chunk,
            "钩子类型": hook_type,
            "修复方向": f"参考章 {ch} 末段（reader_pull={score}）",
            "源RCA": "",
        })
    return rows

def extract_emotion_earned_forced(project_root: Path, chapters: range) -> List[Dict[str, str]]:
    rows = []
    tmp = project_root / ".webnovel" / "tmp"
    for ch in chapters:
        p = tmp / f"emotion_check_ch{ch:04d}.json"
        if not p.exists(): continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for issue in (data.get("issues") or []):
            sub = (issue.get("subcategory") or "").lower()
            if "earned" not in sub and "forced" not in sub: continue
            rows.append({
                "章节": str(ch),
                "严重度": issue.get("severity", "medium"),
                "坏样本": (issue.get("evidence") or "")[:200],
                "好样本": (issue.get("fix_hint") or "")[:200],
                "情感类型": "forced" if "forced" in sub else "earned",
                "修复方向": (issue.get("fix_hint") or "")[:120],
                "源RCA": "",
            })
    return rows

def extract_canon_violations(project_root: Path, chapters: range) -> List[Dict[str, str]]:
    rows = []
    tmp = project_root / ".webnovel" / "tmp"
    for ch in chapters:
        for pattern in [f"consistency_check_ch{ch:04d}.json",
                        f"consistency_ch{ch:04d}.json"]:
            p = tmp / pattern
            if not p.exists(): continue
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            for issue in (data.get("issues") or []):
                cat = (issue.get("category") or "")
                if cat not in ("setting", "timeline", "character"): continue
                trap = {"setting": "设定矛盾", "timeline": "时间线漂移", "character": "关系漂移"}.get(cat, "其他")
                rows.append({
                    "章节": str(ch),
                    "严重度": issue.get("severity", "medium"),
                    "坏样本": (issue.get("evidence") or "")[:200],
                    "好样本": "",
                    "禁区类型": trap,
                    "修复方向": (issue.get("fix_hint") or "")[:120],
                    "源RCA": "",
                })
    return rows

EXTRACTORS = {
    "ai-replacement-vocab": extract_ai_replacement_vocab,
    "strong-chapter-end-hooks": extract_chapter_end_hooks,
    "emotion-earned-vs-forced": extract_emotion_earned_forced,
    "canon-violation-traps": extract_canon_violations,
}

def parse_chapters(s: str) -> range:
    if "-" in s:
        a, b = s.split("-")
        return range(int(a), int(b) + 1)
    return range(int(s), int(s) + 1)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--table", required=True, choices=list(CSV_HEADERS.keys()))
    ap.add_argument("--chapters", required=True, help="e.g. 1-11 or 5")
    ap.add_argument("--output-dir", default="webnovel-writer/references/private-csv")
    args = ap.parse_args()

    project = Path(args.project).resolve()
    csv_path = Path(args.output_dir) / f"{args.table}.csv"
    headers = CSV_HEADERS[args.table]
    existing = load_existing_rows(csv_path)
    new_rows = EXTRACTORS[args.table](project, parse_chapters(args.chapters))

    # 去重 + 编号
    added = 0
    final_rows = list(existing)
    for r in new_rows:
        if is_duplicate(r, final_rows): continue
        r["编号"] = next_id(PREFIX[args.table], final_rows)
        # 补全所有 header 列
        for h in headers:
            r.setdefault(h, "")
        final_rows.append(r)
        added += 1

    # 写回
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for r in final_rows:
            w.writerow({k: r.get(k, "") for k in headers})

    print(f"[OK] {args.table}: +{added} rows (total {len(final_rows)})")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 烟雾测试 4 张表**

```bash
for t in ai-replacement-vocab strong-chapter-end-hooks emotion-earned-vs-forced canon-violation-traps; do
  python -X utf8 webnovel-writer/scripts/private_csv_extractor.py \
    --project 末世重生-我在空间里种出了整个基地 \
    --table $t --chapters 1-11
done
ls -la webnovel-writer/references/private-csv/
wc -l webnovel-writer/references/private-csv/*.csv
```

Expected: 4 张 CSV 全部 > 表头 1 行；至少 ai-replacement-vocab + canon-violation-traps 有非零 rows（chapter 5/6/8/10/11 都有 issue 数据）。

### Task F.3: webnovel.py 加 private-csv 子命令

**Files:**
- Modify: `webnovel-writer/scripts/data_modules/webnovel.py`

- [ ] **Step 1: 加 parser 注册 + dispatch**

```python
p_pcsv = sub.add_parser("private-csv", help="转发到 private_csv_extractor.py（私库提取）")
p_pcsv.add_argument("--table", required=True)
p_pcsv.add_argument("--chapters", required=True)
```

dispatch：

```python
if tool == "private-csv":
    import subprocess as _sp
    cmd = [sys.executable, "-X", "utf8",
           str(SCRIPTS_DIR / "private_csv_extractor.py"),
           "--project", str(args.project_root),
           "--table", args.table,
           "--chapters", args.chapters]
    return _sp.call(cmd)
```

### Task F.4: writer 起草前查 ai-replacement-vocab；reader-naturalness 复测时查全部

**Files:**
- Modify: `webnovel-writer/agents/context-agent.md`
- Modify: `webnovel-writer/agents/reader-naturalness-checker.md`
- Modify: `webnovel-writer/agents/consistency-checker.md`

- [ ] **Step 1: context-agent Stage 5 注入 ai-replacement-vocab top-10 hint**

在创作执行包 writing_guidance.constraints 段追加：

```markdown
**私库提醒（Round 19 · ai-replacement-vocab.csv）**：

读 `${CLAUDE_PLUGIN_ROOT}/references/private-csv/ai-replacement-vocab.csv`，按"严重度"排序取前 10 条 critical/high，把每条的"坏样本→好样本"作为本章起草禁词清单写入 writing_guidance.local_blacklist。

如本章涉及战力对决/情感冲突/末世场景，再追加 canon-violation-traps.csv 中匹配章节的禁区前 5 条到 writing_guidance.canon_traps。
```

- [ ] **Step 2: reader-naturalness-checker.md 复测段加私库回查**

```markdown
### 私库回查（Round 19）

完成 5 子维度评分后，对每条 issue 回查 `${CLAUDE_PLUGIN_ROOT}/references/private-csv/ai-replacement-vocab.csv`：
- 若该坏样本在私库中已存在 → severity 升级 + evidence 追加 `recurring_violation` 标记
- 若新违例 → 写入 `tmp/private_csv_proposal_ch{NNNN}.json`，data-agent Step K 时提示用户是否追加私库
```

- [ ] **Step 3: consistency-checker.md 同样加 canon-violation-traps 回查**

类似逻辑：发现 setting/timeline/character 类问题时，先查 canon-violation-traps.csv 是否已有同类禁区，命中 → severity 升级。

### Task F.5: 跑首次提取生成实数据 + verify + commit

- [ ] **Step 1: 跑 4 张表 Ch1-11 提取**

```bash
for t in ai-replacement-vocab strong-chapter-end-hooks emotion-earned-vs-forced canon-violation-traps; do
  python -X utf8 webnovel-writer/scripts/data_modules/webnovel.py \
    --project-root 末世重生-我在空间里种出了整个基地 private-csv \
    --table $t --chapters 1-11
done
```

- [ ] **Step 2: 人工抽查 5 条 sample 看数据干货度**

```bash
head -10 webnovel-writer/references/private-csv/ai-replacement-vocab.csv
head -10 webnovel-writer/references/private-csv/canon-violation-traps.csv
```

如发现：
- 坏样本/好样本截断不合理 → 调整 extractor 截断长度
- 子维度 / 钩子类型 / 情感类型 字段缺失 → 修 extractor 兜底逻辑
- 重复条目 → 检查 `is_duplicate` 逻辑

- [ ] **Step 3: 三套验证 + sync-cache**

```bash
python -X utf8 webnovel-writer/scripts/data_modules/webnovel.py sync-cache
python -X utf8 webnovel-writer/scripts/data_modules/webnovel.py preflight
python -X utf8 末世重生-我在空间里种出了整个基地/.webnovel/hygiene_check.py
```

- [ ] **Step 4: CUSTOMIZATIONS.md 加 Phase F 段**

```markdown
## [2026-04-25 · Round 19 Phase F] 自建私库 4 表 · 18 轮 RCA 沉淀机器可读化

> 这才是别人复制不了的护城河。fork 已写 11 章，每章每个 checker 都留下 JSON + 报告。Phase F 把这些数据自动提取成 CSV，回灌到 writer / polish / checker——下次不再重犯。

| # | 文件 | 改动 |
|---|------|------|
| 1 | `references/private-csv/{ai-replacement-vocab,strong-chapter-end-hooks,emotion-earned-vs-forced,canon-violation-traps}.csv` | NEW · 4 张私库表 |
| 2 | `references/private-csv/README.md` | NEW · schema |
| 3 | `scripts/private_csv_extractor.py` | NEW · 自动提取器 |
| 4 | `scripts/data_modules/webnovel.py` | 加 private-csv 子命令转发 |
| 5 | `agents/context-agent.md` | writing_guidance.local_blacklist + canon_traps 注入 |
| 6 | `agents/reader-naturalness-checker.md` | issues 回查私库，recurring_violation 升级 |
| 7 | `agents/consistency-checker.md` | 同上，canon-violation-traps 回查 |

实测 Ch1-11 提取数据：
- ai-replacement-vocab: XX 条
- strong-chapter-end-hooks: XX 条
- emotion-earned-vs-forced: XX 条
- canon-violation-traps: XX 条

预期效果：Ch12+ 重犯率显著下降；写作期 AI 词命中数下降；polish 周期数下降；setting 类 audit warn 下降。
```

- [ ] **Step 5: commit**

```bash
git add webnovel-writer/references/private-csv/ \
        webnovel-writer/scripts/private_csv_extractor.py \
        webnovel-writer/scripts/data_modules/webnovel.py \
        webnovel-writer/agents/context-agent.md \
        webnovel-writer/agents/reader-naturalness-checker.md \
        webnovel-writer/agents/consistency-checker.md \
        webnovel-writer/CUSTOMIZATIONS.md
git commit -m "feat(reader-quality): Phase F · 4 张私库 CSV + 自动提取器 + 写读双向回灌"
```

---

## Phase G · 章末钩子 4 分类跨章追踪（P1 · 4h）

> 直接映射：**追读力**。reader-pull-checker 现在给"钩子强度 0-100"单数字，但读者实际感受是 4 类（信息钩 / 情绪钩 / 决策钩 / 动作钩）。连续 5 章用同类钩子读者会疲劳。fork 现在没跨章追踪。

### Task G.1: 写 chapter-end-hook-taxonomy.md

**Files:**
- Create: `webnovel-writer/skills/webnovel-write/references/chapter-end-hook-taxonomy.md`

- [ ] **Step 1: 新建文件**

```markdown
---
name: chapter-end-hook-taxonomy
purpose: 章末钩子 4 分类规范 + 跨章趋势规则
---

# 章末钩子 4 分类（Round 19）

## 4 类定义

| 类型 | 触发读者动机 | 示例 |
|---|---|---|
| **信息钩** | 想知道"是什么"、"为什么" | "她终于看清了那张脸——是十年前应该已经死去的人。" |
| **情绪钩** | 想知道"她会怎么应对"、"他下一步什么心情" | "他没有回头，把那枚戒指扔进了海里。" |
| **决策钩** | 想知道"她选哪边"、"他怎么选" | "面前两扇门，左边是父亲，右边是仇人。她伸出了手——" |
| **动作钩** | 想知道"打赢了吗"、"逃掉了吗" | "刀光起处，他终于看清了那双眼睛。" |

## 评判标准

每章末由 reader-pull-checker 二选：

1. 主类型（必填）：4 类之一
2. 次类型（可选）：4 类之一（多重钩子）

判断窗口：章末最后 200 字。

## 跨章趋势规则

| 规则 | 严重度 |
|---|---|
| 连续 5 章主类型相同 | medium 警告（节奏疲劳） |
| 连续 3 章主类型 + 次类型组合相同 | high 警告 |
| 连续 8 章无"决策钩" | medium 警告（缺主角主动性） |
| 连续 8 章无"情绪钩" | medium 警告（关系线断档） |
| 单卷（默认 20 章）内 4 类全缺 1 类 | medium 警告 |

## reader-pull-checker 输出 schema 扩展

```json
{
  "reader_pull": 88,
  "hook_close": {
    "primary_type": "信息钩 | 情绪钩 | 决策钩 | 动作钩",
    "secondary_type": "...|null",
    "strength": 88,
    "text_excerpt": "章末最后 200 字"
  },
  "cross_chapter_trend": {
    "recent_5_primary": ["信息钩","信息钩","情绪钩","信息钩","信息钩"],
    "warnings": ["连续 4/5 章信息钩，建议下章切换情绪/决策钩"]
  }
}
```
```

### Task G.2: reader-pull-checker 接入分类

**Files:**
- Modify: `webnovel-writer/agents/reader-pull-checker.md`

- [ ] **Step 1: 加分类段**

在 reader-pull-checker.md 评分维度段追加：

```markdown
### Round 19 · 章末钩子 4 分类（参 chapter-end-hook-taxonomy.md）

每章末除给主分数 reader_pull 外，必须二选并填：

- `hook_close.primary_type`：4 类之一（信息钩 / 情绪钩 / 决策钩 / 动作钩）
- `hook_close.secondary_type`：4 类之一或 null
- `hook_close.text_excerpt`：章末最后 200 字原文

### 跨章趋势检查（必跑）

跑：
```bash
python -X utf8 "${SCRIPTS_DIR}/data_modules/webnovel.py" --project-root "${PROJECT_ROOT}" state get-hook-trend --last-n 5
```

CLI 返回 `recent_5_primary` 数组。按以下规则判定：

- 连续 5 章主类型相同 → issue (severity=medium, category=pacing)
- 连续 3 章主+次类型组合相同 → issue (severity=high)
- 8 章无决策钩 → issue (severity=medium)
- 8 章无情绪钩 → issue (severity=medium)

把判定结果写入 `cross_chapter_trend.warnings`。
```

### Task G.3: state_manager 加 hook_close 字段 + get-hook-trend CLI

**Files:**
- Modify: `webnovel-writer/scripts/data_modules/state_manager.py`

- [ ] **Step 1: 加 set-hook-close + get-hook-trend**

```python
p_set_hook = sp.add_parser("set-hook-close")
p_set_hook.add_argument("--chapter", type=int, required=True)
p_set_hook.add_argument("--primary", required=True, choices=["信息钩","情绪钩","决策钩","动作钩"])
p_set_hook.add_argument("--secondary", default=None)
p_set_hook.add_argument("--strength", type=int, default=80)
p_set_hook.add_argument("--text", default="")

p_get_trend = sp.add_parser("get-hook-trend")
p_get_trend.add_argument("--last-n", type=int, default=5)
```

dispatch：

```python
elif args.cmd == "set-hook-close":
    meta = state["chapter_meta"].setdefault(str(args.chapter), {})
    meta["hook_close"] = {
        "primary_type": args.primary,
        "secondary_type": args.secondary,
        "strength": args.strength,
        "text_excerpt": args.text[:200],
    }
    write_state(state)

elif args.cmd == "get-hook-trend":
    chs = sorted([int(k) for k in state["chapter_meta"].keys()], reverse=True)[:args.last_n]
    out = {
        "recent_n": args.last_n,
        "chapters": [],
        "primary_sequence": [],
        "secondary_sequence": [],
    }
    for ch in sorted(chs):
        hc = state["chapter_meta"][str(ch)].get("hook_close") or {}
        out["chapters"].append(ch)
        out["primary_sequence"].append(hc.get("primary_type", ""))
        out["secondary_sequence"].append(hc.get("secondary_type", ""))
    out["all_same_primary_5"] = len(set(out["primary_sequence"][-5:])) == 1 and len(out["primary_sequence"]) >= 5
    out["no_decision_hook_8"] = "决策钩" not in out["primary_sequence"][-8:] and len(out["primary_sequence"]) >= 8
    out["no_emotion_hook_8"] = "情绪钩" not in out["primary_sequence"][-8:] and len(out["primary_sequence"]) >= 8
    print(json.dumps(out, ensure_ascii=False, indent=2))
```

### Task G.4: data-agent Step K 写 hook_close

**Files:**
- Modify: `webnovel-writer/agents/data-agent.md`

- [ ] **Step 1: 在 Step K 章节摘要写入段追加 hook_close 落库**

```markdown
### Round 19 · 章末钩子分类落库

读 `tmp/reader_pull_ch{NNNN}.json` 取 hook_close 子对象，跑：
```bash
python -X utf8 "${SCRIPTS_DIR}/data_modules/webnovel.py" --project-root "${PROJECT_ROOT}" state set-hook-close \
  --chapter {N} --primary "{primary_type}" --secondary "{secondary_type}" --strength {N} --text "{200_chars}"
```

若 reader_pull JSON 缺 hook_close 子对象（老 checker 版本）→ Step K 提示但不阻断。
```

### Task G.5: hygiene_check H25 跨章钩子 trend 检查

**Files:**
- Modify: `webnovel-writer/scripts/hygiene_check.py`

- [ ] **Step 1: 加 H25 检查项**

```python
def h25_hook_trend_check(project_root: Path) -> Dict[str, Any]:
    """H25: 章末钩子 4 类跨章趋势"""
    state = json.loads((project_root / ".webnovel" / "state.json").read_text(encoding="utf-8"))
    metas = state.get("chapter_meta", {})
    chs = sorted([int(k) for k in metas.keys()])
    if len(chs) < 5:
        return {"id": "H25", "status": "skip", "reason": "< 5 章"}
    primaries = [(metas[str(ch)].get("hook_close") or {}).get("primary_type", "") for ch in chs[-5:]]
    if all(p == primaries[0] and primaries[0] for p in primaries):
        return {"id": "H25", "status": "warn", "severity": "medium",
                "msg": f"连续 5 章主钩子类型相同：{primaries[0]}", "chapters": chs[-5:]}
    return {"id": "H25", "status": "ok"}
```

注册到 hygiene_check 主循环。

### Task G.6: 回填 Ch1-11 hook_close

```bash
# 人工或基于 reader_pull JSON 启发式打 4 类标
for ch in $(seq 1 11); do
  echo "Chapter $ch: 阅读 末世重生-我在空间里种出了整个基地/正文/第${ch}章*.md 的最后 200 字，二选 4 类钩子"
  # 然后跑：
  # python -X utf8 webnovel-writer/scripts/data_modules/webnovel.py \
  #   --project-root 末世重生-我在空间里种出了整个基地 \
  #   state set-hook-close --chapter $ch --primary "信息钩" --strength 85 --text "..."
done
```

或写一个简单启发式：扫末段含"？"→信息钩，含"她转身/扔/砸"等动作→动作钩，含"选/决定/伸手"→决策钩，否则→情绪钩。

### Task G.7: verify + commit

- [ ] **Step 1: sync + 三套验证**

- [ ] **Step 2: CUSTOMIZATIONS.md 加 Phase G 段**

- [ ] **Step 3: commit**

```bash
git commit -m "feat(reader-quality): Phase G · 章末钩子 4 分类跨章追踪 + H25 hygiene"
```

---

## Phase B · polish-guide 4 类新词库吸收（P2 · 2h）

> 直接映射：**自然度**。fork polish-guide 现有 200+ 词库，upstream 的 `74717aa` 在 4 个新分类（K 神态模板词 / L 万能副词 / M 内心活动套话 / N 转折递进模板）+ 6 条句式规则补强。

### Task B.1: 对比合并 4 类新词库

**Files:**
- Modify: `webnovel-writer/skills/webnovel-write/references/polish-guide.md`

- [ ] **Step 1: 检查 fork 现有 K/L/M/N 段**

```bash
grep -n "^#### [A-N]\.\|第1层\|第2层\|高频词" webnovel-writer/skills/webnovel-write/references/polish-guide.md | head -20
```

- [ ] **Step 2: 取 upstream 对应段**

```bash
git show upstream/master:webnovel-writer/skills/webnovel-write/references/polish-guide.md > /tmp/upstream-polish.md
grep -n "^#### K\|^#### L\|^#### M\|^#### N" /tmp/upstream-polish.md
```

- [ ] **Step 3: 用 Edit 把 K/L/M/N 段（含描述 + 词表 + 替代方向）合并到本地 polish-guide.md**

如果 fork 已有 K/L/M/N 段：
- 比对词表，合并新增词（取 union）
- 保留 fork 已有的"血教训"标注（如有）
- 不删 fork 已有词

如果 fork 缺这 4 段：
- 直接复制 upstream 内容到 fork polish-guide.md 第 1 层后

- [ ] **Step 4: 6 条句式规则同样合并**

定位 upstream "第2层：句式规则（反模板）"段（10 条），与本地比对，把缺的 6 条加上。

### Task B.2: verify + commit

```bash
python -X utf8 webnovel-writer/scripts/data_modules/webnovel.py sync-cache
python -X utf8 webnovel-writer/scripts/data_modules/webnovel.py preflight
python -X utf8 末世重生-我在空间里种出了整个基地/.webnovel/hygiene_check.py

git add webnovel-writer/skills/webnovel-write/references/polish-guide.md webnovel-writer/CUSTOMIZATIONS.md
git commit -m "feat(reader-quality): Phase B · polish-guide K/L/M/N 词库 + 6 条句式规则 · upstream@74717aa"
```

---

## Phase H · 画面感 3 子规则（P2 · 3h）

> 直接映射：**画面感**。读者投诉"看不到画面"是头号差评。prose-quality-checker 现在评分综合，但没专门拎出"画面感"维度做硬规则。

### Task H.1: 写 visual-concreteness-rubric.md

**Files:**
- Create: `webnovel-writer/skills/webnovel-write/references/visual-concreteness-rubric.md`

- [ ] **Step 1: 新建文件**

```markdown
---
name: visual-concreteness-rubric
purpose: 画面感 3 子规则 · 视觉锚点 / 非视觉感官 / 抽象动作改写
---

# 画面感 3 子规则（Round 19）

## 子规则 1: 场景首句视觉锚点

每个新场景的**首句**必须含至少 1 项视觉锚点：

- 光线（"窗外的光斜斜地切过他的左肩"）
- 空间（"地下室只有三步深，墙在他左手边发凉"）
- 物体（"刀就摆在桌角，刀尖朝着她"）

**禁止**：场景首句写心理活动 / 抽象状态 / 时间流逝 / 概括性描述。

扣分：critical（直接 -10），blocking 给 reader_critic。

## 子规则 2: 每段非视觉感官

每段（≥ 50 字）至少含 1 个非视觉感官：

- 听觉（"远处有人在喊她的名字"）
- 触觉（"门把冰得像一截铁"）
- 嗅觉（"血腥味开始压过消毒水的味道"）
- 温度（"风停了，但空气还是凉的"）
- 味觉（"舌尖尝到铁锈味"）

**统计**：每章总段数 ≥ 50 字的段中，非视觉感官段占比 ≥ 30%。

扣分：占比 < 30% → high（-8）；占比 < 15% → critical（-15）。

## 子规则 3: 抽象动作触发改写

以下抽象动作短语必须改为具象描写：

| 抽象动作 | 改写要求 |
|---|---|
| "展开攻势" | 必须给出具体动作链（试探 / 突进 / 拨开 / 反手） |
| "陷入沉思" | 必须给出微动作（拧笔帽 / 摸下巴 / 看窗外 / 数手指） |
| "气氛凝固" | 必须给出感官锚点（声音消失 / 温度下降 / 谁的呼吸声） |
| "心潮澎湃" | 必须改为生理反应（指节发白 / 心跳乱拍 / 呼吸不稳） |
| "目光交汇" | 必须给出时长 + 动作（多久 / 谁先移开） |

扣分：每出现 1 处未改写抽象动作 -3，单章 ≥ 5 处 → high。

## prose-quality-checker 输出 schema 扩展

```json
{
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
```

### Task H.2: prose-quality-checker 接入

**Files:**
- Modify: `webnovel-writer/agents/prose-quality-checker.md`

- [ ] **Step 1: 在评分维度段追加画面感 3 子规则**

把现有"画面感"评分单点扩展：

```markdown
### Round 19 · 画面感 3 子规则（参 visual-concreteness-rubric.md）

#### 子维度 visual_subdimensions

1. **scene_visual_anchor**（场景首句视觉锚点 0-100）
   - 扫所有场景切换点（空行 + 时间/地点切换标志），首句缺视觉锚点 → 每处 -10
2. **non_visual_sensory_ratio**（非视觉感官段占比 0-100）
   - 计算 ≥ 50 字段中含非视觉感官的占比
   - ≥ 30% → 100；< 15% → 0；线性插值
3. **abstract_action_count**（抽象动作未改写计数）
   - 扫"展开攻势 / 陷入沉思 / 气氛凝固 / 心潮澎湃 / 目光交汇"等模板
   - 每出现 1 处未改写 -3

主分 prose_quality 加权：原综合 × 0.6 + visual_subdimensions 平均 × 0.4
```

### Task H.3: SKILL.md Step 2 加载点

**Files:**
- Modify: `webnovel-writer/skills/webnovel-write/SKILL.md`

```
- references/visual-concreteness-rubric.md（Round 19 · 画面感 3 子规则，writer 起草时即时遵守）
```

### Task H.4: verify + commit

```bash
git commit -m "feat(reader-quality): Phase H · 画面感 3 子规则 · visual-concreteness-rubric"
```

---

## Phase E · plan 跨卷感知（P2 · 1h）

> 直接映射：**追读力**（长线）。plan 现在做下卷规划只看大纲，看不到前卷实际写成什么样，可能重复回收某个伏笔。

### Task E.1: webnovel-plan SKILL 加 history 加载

**Files:**
- Modify: `webnovel-writer/skills/webnovel-plan/SKILL.md`

- [ ] **Step 1: 找 plan 数据加载段**

```bash
grep -n "state.json\|chapter_meta\|history\|大纲" webnovel-writer/skills/webnovel-plan/SKILL.md | head -10
```

- [ ] **Step 2: 追加 Round 19 跨卷加载步骤**

```markdown
### Step 1.5 · Cross-volume awareness（Round 19）

下卷规划前必须读已写章节真实数据，不能只看大纲：

1. 跑 `python -X utf8 ${SCRIPTS_DIR}/data_modules/webnovel.py state get-recent-meta --last-n 10`
   取最近 10 章 `hook_close / unresolved_loops / protagonist_state.golden_finger / overall_score`
2. 跑 `python -X utf8 ${SCRIPTS_DIR}/data_modules/webnovel.py state get-hook-trend --last-n 10`（Phase G 新增）
   取 4 类钩子分布
3. 在新卷规划必须**显式回应**：
   - 至少 1 个上卷未解决的伏笔在本卷开篇 3 章内被触及
   - 主角金手指曲线在新卷保持单调或带显式弱化事件
   - 上卷读者钩子若得分 < 70，新卷开篇加强同类钩子
   - 上卷 hook_trend 若主类型连续 5+ 章相同，新卷必须切换钩子组合
```

### Task E.2: state_manager 加 get-recent-meta CLI

**Files:**
- Modify: `webnovel-writer/scripts/data_modules/state_manager.py`

```python
p_get_recent = sp.add_parser("get-recent-meta")
p_get_recent.add_argument("--last-n", type=int, default=10)
```

dispatch：

```python
elif args.cmd == "get-recent-meta":
    metas = state.get("chapter_meta", {})
    chs = sorted([int(k) for k in metas.keys()], reverse=True)[:args.last_n]
    out = {}
    for ch in sorted(chs):
        m = metas[str(ch)]
        out[ch] = {
            "hook_close": m.get("hook_close"),
            "unresolved_loops": m.get("unresolved_loops") or [],
            "overall_score": m.get("overall_score"),
            "review_metrics": (m.get("review_metrics") or {}).get("overall_score"),
        }
    print(json.dumps(out, ensure_ascii=False, indent=2))
```

### Task E.3: verify + commit

```bash
git commit -m "feat(reader-quality): Phase E · plan 跨卷感知 · upstream@3e36417"
```

---

## Phase D · upstream CSV 9 表（P3 · 4h · 看干货度决定）

> Phase D 是**条件执行**：先抽查 3 张 CSV 干货度，确实高再做。Phase A-H 完成后再判断。

### Task D.1: 干货度抽查

- [ ] **Step 1: 读 3 张 CSV 各前 5 行**

```bash
git show upstream/master:webnovel-writer/references/csv/裁决规则.csv | head -8
git show upstream/master:webnovel-writer/references/csv/场景写法.csv | head -8
git show upstream/master:webnovel-writer/references/csv/爽点与节奏.csv | head -8
```

- [ ] **Step 2: 评分**

每张 CSV 按以下打分：
- 条目数 ≥ 10 → +1
- "大模型指令"列具体可执行（不是空话） → +1
- "毒点"列对本作有用 → +1
- "示例片段"是干货 → +1

3 张 CSV 总分 ≥ 8 → 执行 Phase D；< 8 → 跳过 Phase D，进入 Phase 8 兑现验证。

### Task D.2: 若执行，参考 v1 计划 Phase 2 全套（CSV + reference_search.py + 接入 context-agent）

略，参 `2026-04-25-upstream-cherry-pick-quality-uplift.md` Phase 2。

---

## Phase 8 · Ch12-13 端到端兑现（必做）

### Task 8.1: 写 Ch12 走完整流程

按 webnovel-write SKILL Step 0-7 写 Ch12。Phase A/I/C/F 全套生效。

### Task 8.2: 收集兑现指标

- [ ] **Step 1: 跑 quality_baseline 对比**

```bash
python -X utf8 - <<'PY'
import json, sqlite3
from pathlib import Path
proj = Path("末世重生-我在空间里种出了整个基地")
baseline = json.loads((proj / ".webnovel" / "reports" / "quality_baseline.json").read_text(encoding="utf-8"))

conn = sqlite3.connect(str(proj / ".webnovel" / "index.db"))
conn.row_factory = sqlite3.Row
ch12 = conn.execute("SELECT * FROM review_metrics WHERE chapter = 12").fetchone()
ch12_dict = dict(ch12) if ch12 else {}

state = json.loads((proj / ".webnovel" / "state.json").read_text(encoding="utf-8"))
ch12_scores = (state.get("chapter_meta", {}).get("12", {}) or {}).get("checker_scores", {})
ch12_subs = (state.get("chapter_meta", {}).get("12", {}) or {}).get("checker_subdimensions", {}).get("reader_naturalness", {})

report = {
    "ch12_overall": ch12_dict.get("overall_score"),
    "baseline_overall_avg_ch1_11": baseline["overall_avg"],
    "delta_overall": (ch12_dict.get("overall_score") or 0) - baseline["overall_avg"],
    "ch12_naturalness": ch12_scores.get("reader_naturalness"),
    "baseline_naturalness_avg": baseline["checker_avg_ch1_11"]["reader_naturalness"],
    "delta_naturalness": (ch12_scores.get("reader_naturalness") or 0) - baseline["checker_avg_ch1_11"]["reader_naturalness"],
    "ch12_naturalness_subdimensions": ch12_subs,
    "ch12_pull": ch12_scores.get("reader_pull"),
    "ch12_prose": ch12_scores.get("prose_quality"),
}
out = proj / ".webnovel" / "reports" / "ch12_roi.json"
out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
PY
```

### Task 8.3: 兑现报告 + 决策

判定：
- naturalness +5 / +10 / +0：
  - +10 → 大成功，全部 Phase 留下
  - +5 → 部分成功，Phase 6 体检（v1 计划）下一轮做
  - +0 → 进 RCA，定位是哪个 Phase 引入回归

写报告到 `docs/superpowers/plans/upstream-snapshot/ch12-roi-report.md`，commit。

---

## Phase 7 · DO NOT MERGE 永久清单（必做 · 30 min）

参 v1 计划 Phase 7。10 类 upstream 改动**永久不合并**：

1. v6 单 reviewer.md（替代 13 checker）
2. workflow_manager 移除
3. story-system 事件溯源 + projection writers
4. vector_projection_writer + vectors.db
5. dashboard 路由多页重建
6. Token 压缩整文件替换（8bdd18e + 3d64506）
7. v6 chapter_drafted/reviewed/committed 状态机
8. SKILL.md 充分性闸门切到状态机
9. 移除 golden_three_checker / Step 2B legacy
10. Memory contract / scratchpad 大改

每条原因 + 替代路径见 v1 计划。

写入 `webnovel-writer/CUSTOMIZATIONS.md` + `ROOT_CAUSE_GUARD_RAILS.md` Round 19 段。

```bash
git commit -m "docs(reader-quality): Phase 7 · DO NOT MERGE 永久清单 · 10 类架构级拒绝"
```

---

## 自检（Self-Review）

### 1. 标尺映射

| Phase | 自然度 | 画面感 | 追读力 |
|---|---|---|---|
| A anti-ai-guide | ✅ | | |
| I Ch1 钩 | | | ✅ |
| C 5 子维度 | ✅ | | |
| F 4 私库 | ✅ | | ✅（钩子私库） |
| G 钩子 4 分类 | | | ✅ |
| B polish 词库 | ✅ | | |
| H 画面感 3 规则 | | ✅ | |
| E plan 跨卷 | | | ✅ |

每个 Phase 都有至少 1 个映射，无"对读者无感"的项。

### 2. Placeholder scan

- 每个 Bash / Edit / Python 都有具体路径与可验证 expected
- 每个 Phase 都有 sync-cache + preflight + hygiene_check 三套验证收尾
- CUSTOMIZATIONS.md 模板段格式 Phase A-H 一致

### 3. Type / signature 一致性

- `state set-checker-subdimension` (C) / `state set-hook-close` (G) / `state get-hook-trend` (G) / `state get-recent-meta` (E) 命名一致 verb-noun
- `private-csv` 子命令（F）与 v1 计划 `reference` 子命令风格一致
- checker_subdimensions / hook_close 字段在 chapter_meta 下扁平挂载，与既有 checker_scores 同级
- visual_subdimensions（H） / subdimensions（C 内 reader_naturalness 用） 都是 `_subdimensions` 后缀

### 4. 依赖关系

- Phase 0 → 全部
- A、I、B、E、H 互相独立
- C 是 F 的弱依赖（F extractor 用到 subdimension 字段）
- G 加 hook_close 字段；F (strong-chapter-end-hooks) extractor 之后再回填 4 类标
- D 条件执行
- Phase 8 必须在 A+I+C+F+G 都做完后再做（G 需要 11 章已回填 hook_close）

---

## 总结

**核心 insight**（用户给的）：fork 已经在质量维度上比 upstream v6 更强；upstream v6 走的是"轻量化、降 token、少检查"的反方向。真正升级路径是：

1. **从上游借工具**：anti-ai-guide / polish 词库 / ai_flavor 5 子维度（v6 之前积累的好东西，与本地评分体系正交）
2. **基于 11 章 RCA 沉淀私库**：4 张自有 CSV——这才是别人复制不了的护城河
3. **死磕读者关键指标**：首章钩 / 章末钩 4 分类 / 画面感 3 子规则——直接量化质量

30 小时分 3 周，每个 Phase 都映射到自然度 / 画面感 / 追读力其中至少 1 件。映射不到的（v6 token-rewrite / story-system / vector / dashboard）全部拒绝。

Round 19 完成后预期：
- Ch12+ reader-naturalness 从 78-85 → 88-95（A + C + F + B 合力）
- Ch12+ prose-quality 视觉子维度 + 13（H）
- Ch12+ reader-pull 跨章趋势可观测，钩子分布健康（G）
- Ch1（如重写）完读率显著提升（I）
- 跨卷规划自洽性 ↑（E）
- 重犯率 ↓（F 私库回灌）

而 18 轮 102 commit 加固**全部保留**——这是过去几周堆出来的护城河，不能为了"看起来跟上 upstream"拆掉。
