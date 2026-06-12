# webnovel-write · Step 5 Data Agent

> Round 29 Phase 2 由 SKILL.md 原文拆分（lazy-load）。进入对应 Step 时必须先加载本文件全文，
> 按其中规则执行；跨步骤硬约束 / 章节间闸门 / 充分性闸门见 SKILL.md 骨架。

### Step 5：Data Agent（状态与索引回写）

使用 Task 调用 `data-agent`，参数：
- `chapter`
- `chapter_file` 必须传入实际章节文件路径；若详细大纲已有章节名，优先传 `正文/第{chapter_padded}章-{title_safe}.md`，否则传 `正文/第{chapter_padded}章.md`
- `review_score=Step 3 overall_score`
- `project_root`
- `storage_path=.webnovel/`
- `state_file=.webnovel/state.json`

Data Agent 默认子步骤（全部执行）：
- A. 加载上下文
- B. AI 实体提取
- C. 实体消歧
- D. 写入 state/index
- E. 写入章节摘要
- F. AI 场景切片
- G. RAG 向量索引（`rag index-chapter --scenes ...`）
- H. 风格样本评估（`style extract --scenes ...`，仅 `review_score >= 80` 时）
- I. 债务利息（默认跳过）
- J. 生成处理报告（必须记录 A-I 每步耗时；写入 `.webnovel/observability/data_agent_timing.jsonl`）
- K. 设定集同步检查（每章执行，best-effort，失败不阻断）

`--scenes` 来源优先级（G/H 步骤共用）：
1. 优先从 `index.db` 的 scenes 记录获取（Step F 写入的结果）
2. 其次按 `start_line` / `end_line` 从正文切片构造
3. 最后允许单场景退化（整章作为一个 scene）

Step 5 失败隔离规则：
- 若 G/H 失败原因是 `--scenes` 缺失、scene 为空、scene JSON 格式错误：只补跑 G/H 子步骤，不回滚或重跑 Step 1-4。
- 若 A-E 失败（state/index/summary 写入失败）：仅重跑 Step 5，不回滚已通过的 Step 1-4。
- 禁止因 RAG/style 子步骤失败而重跑整个写作链。

执行后检查（最小白名单）：
- `.webnovel/state.json`
- `.webnovel/index.db`
- `.webnovel/summaries/ch{chapter_padded}.md`
- `.webnovel/observability/data_agent_timing.jsonl`（观测日志）

**数据完整性后验证（Step 5 完成后必须执行）**：
```python
# 用 Bash 执行以下 Python 验证，任一项 FAIL 则必须立即补修
import json, re
with open('.webnovel/state.json','r',encoding='utf-8') as f: s=json.load(f)
meta = s['chapter_meta'][f'{chapter:04d}']
# 1. checker_scores 非空 + 13 个 canonical key
assert meta.get('checker_scores') and len(meta['checker_scores']) >= 3, 'FAIL: checker_scores empty'
_canonical_set = {"consistency-checker","continuity-checker","ooc-checker","reader-pull-checker","high-point-checker","pacing-checker","dialogue-checker","density-checker","prose-quality-checker","emotion-checker","flow-checker","reader-naturalness-checker","reader-critic-checker","overall"}
_banned = {"Anti-AI","anti-ai","naturalness_veto"}
_alias_lists = [["设定一致性","一致性检查","伏笔埋设","伏笔检查"],["连贯性","连续性检查"],["人物塑造","人物OOC","OOC检查","人物"],["追读力","追读检查","钩子强度","钩子检查"],["爽点密度","爽点检查"],["节奏控制","节奏检查","节奏"],["对话质量","对话检查","对话"],["信息密度","密度检查"],["文笔质感","文笔检查","Prose质量","Prose","文笔"],["情感表现","情感检查","情绪曲线","情感"],["读者流畅度","读者视角流畅度","流畅度检查"],["汉语母语自然度","自然度","naturalness","reader-naturalness"],["读者锐评","reader-critic","读者视角锐评"]]
_bad_keys = [k for k in meta['checker_scores'].keys() if k in _banned or (k not in _canonical_set and not any(k in al for al in _alias_lists))]
assert not _bad_keys, f'FAIL: checker_scores 含非 canonical/banned key: {_bad_keys}（需用 13 个英文 checker 名）'
# 2. word_count 准确（用标准方法重算对比，误差<=2%）
with open(chapter_file,'r',encoding='utf-8') as f: text=f.read()
actual = len(re.findall(r'[\u4e00-\u9fff]', text))
assert abs(meta['word_count'] - actual) / actual < 0.02, f'FAIL: word_count {meta["word_count"]} vs actual {actual}'
# 3. strand_tracker 与 chapter_meta 一致
history = s['strand_tracker']['history']
tracker_strand = [h for h in history if h['chapter']==chapter][0]['dominant']
assert tracker_strand == meta['strand_dominant'].lower(), f'FAIL: strand mismatch {tracker_strand} vs {meta["strand_dominant"]}'
```

性能要求：
- 读取 timing 日志最近一条；
- 当 `TOTAL > 30000ms` 时，输出最慢 2-3 个环节与原因说明。

观测日志说明：
- `call_trace.jsonl`：外层流程调用链（agent 启动、排队、环境探测等系统开销）。
- `data_agent_timing.jsonl`：Data Agent 内部各子步骤耗时。
- 当外层总耗时远大于内层 timing 之和时，默认先归因为 agent 启动与环境探测开销，不误判为正文或数据处理慢。

债务利息：
- 默认关闭，仅在用户明确要求或开启追踪时执行（见 `step-5-debt-switch.md`）。

设定集同步（Step K）：
- 每章执行，检查新实体/道具状态变化/伏笔/资产变动，追加到设定集文件
- 所有追加带 `[Ch{N}]` 章节标注
- 失败不阻断流程
