# Webnovel Writer · XuanRanL Fork

[![License](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Compatible-purple.svg)](https://claude.ai/claude-code)

> **本 fork 与原项目 [lingfengQAQ/webnovel-writer](https://github.com/lingfengQAQ/webnovel-writer) 已分叉为不同产品**：
> 原项目走“轻量化 + 降 token + 单 reviewer 不评分”路线；本 fork 走“13-checker 评分硬卡 + 18 轮 RCA 加固 + 读者三件标尺”路线。
> 两者**架构不可合并**，本 fork 选择性吸收原项目精华（v6 之前的好东西），拒绝 v6 删评分 / 删 workflow_manager / 引入 story-system 投影等架构级改动。

---

## 1. 这个 fork 解决什么问题（核心定位）

读者追下一章只看 3 件事：
1. **自然度**：写得不像 AI（不是“缓缓开口、瞳孔微缩、心中一凛”）
2. **画面感**：场景具象、感官层次、节奏对（看得见、闻得到、节奏对）
3. **追读力**：情绪欠债 + 悬念 + 爽点节奏（想看下一章）

**所有功能必须直接映射到这 3 件之一**——映射不到的不做（即使原项目有这功能）。这是本 fork 的取舍底线。

### 实测兑现（基于《末世重生》Ch1-11 真实数据）

| 标尺 | baseline (Ch1-11 平均) | Round 19 期望（Ch12+） |
|---|---|---|
| reader-naturalness | 87.10 | ≥ 92（A + C + F + B 合力） |
| prose-quality | 88.27 | ≥ 91（H 加权） |
| reader-pull | 88.91 | 维持 + 钩子多样性 |
| **reader-critic** | **80.30** | **≥ 87**（X1 谷底自动 block） |
| overall | 88.36 | ≥ 90 |
| polish 周期数 | 2-3 轮 | 1-2 轮（A 起草前预防） |

**关键：Ch3=62 / Ch4=58 这种历史 reader-critic 谷底，Round 19 后自动触发 P0 block 不能 commit**，必须 polish 重写到 ≥75。

---

## 2. Round 19 的 9 个核心 Phase（vs 原项目）

| Phase | 解决什么 | 来源 |
|---|---|---|
| **A** anti-ai-guide.md 起草前预防 | AI 8 倾向 + 本作 N1-N5 根因映射 | 原项目精华（v6 之前） + 本 fork 独有的 RCA 映射 |
| **I** Ch1 追读契约 9+3 rubric | 网文平台前 300 字弃读率（首句钩 critical / 第 1 段承诺 / 300 字内触发器） | 本 fork 独创 |
| **X1** reader-critic <75 全卷 P0 阻止 | Ch3=62/Ch4=58 类首稿低分自动 block，必须 polish 至 ≥75 才能 commit | 本 fork 独创 |
| **X1B** 前 5 章写前自检 5 类 | 金手指时序 / 突兀编号 / 爽点兑现 / 伏笔节奏 / 读者卡点 | 本 fork 独创 |
| **F** 4 张项目本地私库 + 双向回灌 | 跨章 7-10 章重犯模式（polish 修不住的根因）从根源根治 | 本 fork 独创（最大杠杆 Phase） |
| **H** 画面感 3 子规则 | 场景首句视觉锚点 / 5+1 感官色谱（嗅觉强制） / 抽象动作改写 | 本 fork 独创 |
| **B** polish K/L/M/N + 4 句式 | 200+ 词库扩充 + 4 句式对应 N1/N2/N3/P4 根因 | 原项目精华 + 本 fork 句式硬卡 |
| **E** plan 跨卷感知 | 下卷规划读最近 N 章真实 hook_close + 钩子趋势 + 未解决伏笔 | 原项目思路 + 本 fork CLI |
| **C** reader-naturalness 5 子维度 | vocab/syntax/narrative/emotion/dialogue 定向反馈 + polish 定向修最低子维度 | 借鉴原项目 v5（不引入 v6 单 reviewer 整体） |
| **G** 章末钩子 4 分类 + H25 跨章 | 信息/情绪/决策/动作钩 + 连续 5 章同型 P1 warn | 本 fork 独创 |

### 永久拒绝合并的原项目 10 类改动（DO NOT MERGE）

详见 `webnovel-writer/ROUND19_DO_NOT_MERGE.md`：

1. v6 单 reviewer.md 替代 13 checker
2. workflow_manager 移除依赖 Claude Code /resume
3. story-system 事件溯源 + projection writers
4. vector_projection_writer + vectors.db
5. dashboard 路由多页重建
6. Token 整文件压缩替换
7. v6 chapter_drafted/reviewed/committed 状态机
8. SKILL.md 充分性闸门状态机
9. 移除 golden_three_checker / Step 2B legacy
10. Memory contract / scratchpad 大改

每条原因 + 替代路径见专门文档。**未来 git fetch upstream 看到这 10 类直接跳过**。

---

## 3. 跨项目可移植性（Round 19.1 P0-1 根治）

私库 CSV 改为**项目本地** `{project}/.webnovel/private-csv/`，跨项目隔离：
- 写《画山海》不会被《末世重生》“陆沉/麦穗/印记”反例污染
- 每个项目专属反例 + fork 共享 schema seed

**新项目接入流程**见 `webnovel-writer/MIGRATION_NEW_PROJECT.md`，关键步骤：

1. `webnovel-init` 后 9 个 Phase 自动生效
2. 写完 Ch1-2 后跑 1 次 `webnovel.py private-csv --table X --chapters 1-2` 初始化项目本地私库
3. Ch3+ writer 自动消费**本项目专属**私库

---

## 4. 快速开始

### 4.1 安装本 fork（推荐）

```bash
# 直接 clone（保留 18 轮 RCA 加固 + Round 19 全部）
git clone https://github.com/XuanRanL/webnovelwriter.git
cd webnovelwriter
```

### 4.2 安装 Python 依赖

```bash
python -m pip install -r requirements.txt
```

### 4.3 初始化小说项目

在 Claude Code 中执行：

```bash
/webnovel-init
```

### 4.4 配置 RAG 环境

```bash
cp .env.example .env
# 编辑 .env 填入 EMBED / RERANK / LLM API 密钥
```

最小配置：

```bash
EMBED_BASE_URL=https://api-inference.modelscope.cn/v1
EMBED_MODEL=Qwen/Qwen3-Embedding-8B
EMBED_API_KEY=your_embed_api_key

RERANK_BASE_URL=https://api.jina.ai/v1
RERANK_MODEL=jina-reranker-v3
RERANK_API_KEY=your_rerank_api_key
```

### 4.5 开始使用

```bash
/webnovel-plan 1            # 生成第 1 卷大纲
/webnovel-write 1           # 写第 1 章（自动 Step 0-7 + Round 19 全部 Phase）
/webnovel-review 1-5        # 审查 Ch1-5 质量
```

### 4.6 故障排查

```bash
python -X utf8 webnovel-writer/scripts/webnovel.py preflight
python -X utf8 webnovel-writer/scripts/webnovel.py sync-cache
python -X utf8 webnovel-writer/scripts/webnovel.py --project-root <project> sync-agents
```

### 4.7 启动可视化面板（可选）

```bash
/webnovel-dashboard
```

---

## 5. 与原项目同步策略

```bash
# 已配置好 upstream remote，可随时 fetch 最新
git fetch upstream
git log upstream/master ^main --oneline   # 查看上游新增 commits

# 选择性吸收（**必须先看 ROUND19_DO_NOT_MERGE.md 排除清单**）：
# - 落入 DO NOT MERGE 10 类 → 直接跳过
# - 通用工具改进（如 anti-ai-guide / polish-guide 词库扩充）→ 评估后手动取并集
# - bug fix → 直接 cherry-pick
```

**绝不**用 `git merge upstream/master` 整体合并 — 会破坏 18 轮 RCA 加固。

---

## 6. 架构核心（与原项目差异）

```
本 fork (XuanRanL/webnovelwriter)            原项目 (lingfengQAQ/webnovel-writer)
─────────────────────────────────────       ──────────────────────────────────────
13 checker × 14 外部模型 × 13 维度评分      单 reviewer.md（无评分 / 结构化问题清单）
↓
182 共识样本 → overall_score 0-100         "issues 列表"无量化分
↓
90-100 评分硬卡 / Round 14 加固            读者无法对比 Ch10 vs Ch5 质量

workflow_manager 状态机                    依赖 Claude Code /resume
↓
start-step → complete-step → complete-task
↓
Step 0-7 全流程审计闸门

state.json 直接真源                        story-system 事件溯源 + projection
↓
24 项 hygiene_check 硬扫描                 多层投影 / state.json 是只读视图

Round 19.1 项目本地私库                    无私库（用泛用 CSV）
↓                                          ↓
{project}/.webnovel/private-csv/           references/csv/ 共享
跨项目隔离 + 本作 RCA 派生                  题材通用知识表
```

---

## 7. 文档导航

| 文档 | 内容 |
|---|---|
| `docs/architecture.md` | 系统架构与模块设计 |
| `docs/commands.md` | 命令详解 |
| `docs/rag-and-config.md` | RAG 与 .env 配置 |
| `docs/genres.md` | 题材模板 |
| `docs/operations.md` | 运维与恢复 |
| `webnovel-writer/CUSTOMIZATIONS.md` | fork 全部改动日志（Round 1-19.1） |
| `webnovel-writer/ROUND19_DO_NOT_MERGE.md` | 永久拒绝合并的 10 类原项目改动 |
| `webnovel-writer/MIGRATION_NEW_PROJECT.md` | 新项目接入 Round 19 流程指南 |
| `docs/superpowers/plans/round19-comprehensive-test-report.md` | Round 19 全面测试报告 |
| `docs/superpowers/plans/round19.1-final-report.md` | Round 19.1 P0×3 根治测试报告 |
| `docs/superpowers/plans/round19-research/ch1-11-root-cause-analysis.md` | RCA 深度分析 |
| `docs/superpowers/plans/round19-audit-report.md` | Round 19 第三方审计报告 |

---

## 8. 版本简史

| 版本 | 说明 |
|---|---|
| **Round 19.1** | P0×3 根治：私库跨项目隔离 + quote_pair_fix 文件类型守卫 + 写前自检 dead spec 兑现 |
| **Round 19** | 三件标尺重新定位 + 9 Phase 落地：A/I/X1/F/H/B/E/C/G + Phase 7 永久清单 + Phase D 决策 |
| Round 18.x | Ch10/Ch11 RCA 5 类根治批次 |
| Round 17.x | Ch7/Ch8 RCA + polish_cycle 归档层 + 现实红旗 +285 行 |
| Round 16 | 14 外部模型扁平共识 + Bash redirect 安全规则 |
| Round 15.3 | Ch6 6 类 bug 全部根治（complete-task --force / sync-cache --prune / merge-partial 等） |
| Round 14.5 | Step 8 Post-Commit Polish 引入 |
| Round 14 | 9→14 外部模型 × 13 维度 = 182 共识样本 |
| Round 13 v2 | 读者视角双 checker（naturalness + reader-critic）+ 13 维度 |
| Round 12 | Ch1 披露时序 6 道防御 |
| Round 11 | 外审架构重构 · openclawroot 首位供应商 + 9 新模型 |
| Round 10 | Ch1 末世重生 5 个 checker rubric 升级 |
| ... | （Round 1-9 详见 `CUSTOMIZATIONS.md`） |

---

## 9. 开源协议

`GPL v3` 协议，详见 `LICENSE`。

## 10. 致谢

- 原项目作者 [@lingfengQAQ](https://github.com/lingfengQAQ) — 提供本 fork 的初始基线
- 本 fork 由 [@XuanRanL](https://github.com/XuanRanL) 维护，配合 Claude Code (Opus 4.7 1M context) 执行 Round 1-19 加固

## 11. 贡献

本 fork 接受三类贡献：

1. **bug fix**：直接 PR
2. **小说质量提升**：必须能映射到自然度 / 画面感 / 追读力其中至少 1 件，否则不接受
3. **跨项目可移植性改进**：欢迎（特别是非末世题材的私库 schema 验证）

```bash
git checkout -b feature/your-feature
git commit -m "feat: <feature description>"
git push origin feature/your-feature
```

---

## 12. Star 历史

[![Star History Chart](https://api.star-history.com/svg?repos=XuanRanL/webnovelwriter&type=Date)](https://star-history.com/#XuanRanL/webnovelwriter&Date)
