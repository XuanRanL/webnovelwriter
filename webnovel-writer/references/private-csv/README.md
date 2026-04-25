# 私库 CSV（Round 19 Phase F · 基于 18 轮 RCA + Ch1-11 实战数据沉淀）

## 设计原则

- **零新数据来源**：全部从 `.webnovel/tmp/*.json` + `polish_reports/*.md` + `audit_reports/*.md` 派生
- **每条带证据**：必有“坏样本”原文引用 + “修复方向”具体 fix_hint
- **跨项目可移植**：4 张表沉淀到 fork `references/private-csv/`，sync-cache 后所有项目自动受益
- **可机读**：reader-naturalness-checker / consistency-checker / writer 都能查表回灌

## 4 张表

| 表 | 用途 | 提取来源 | 标尺 |
|---|---|---|---|
| `ai-replacement-vocab.csv` | AI 词→替代词对，writer 起草前查 + reader-naturalness 复测时回查升级 severity | `tmp/(reader_)?naturalness_(check_)?ch*.json` issues | 自然度 |
| `strong-chapter-end-hooks.csv` | reader_pull ≥ 90 章节末段模板，writer 写章末时参考 | `tmp/reader_pull_(check_)?ch*.json` + 正文末段 | 追读力 |
| `emotion-earned-vs-forced.csv` | emotion-checker 抓到的“earned vs forced”反例 + 正例 | `tmp/emotion_(check_)?ch*.json` issues | 自然度 |
| `canon-violation-traps.csv` | consistency-checker + audit_reports B 层禁区 | `tmp/consistency_(check_)?ch*.json` + `audit_reports/*.md` | 追读力 |

## schema（4 表共享通用列 + 表特有列）

通用列（必填）：

| 列 | 说明 |
|---|---|
| `编号` | 表前缀-序号（AV-001 / SH-001 / EE-001 / CV-001） |
| `章节` | 提取自第几章（'1'-'11' 字符串）|
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
- 手工追加条目走 `webnovel.py private-csv --append` 走相同 schema 验证
- 严禁手编辑 CSV 破坏 BOM / 行尾 / 编号唯一性
