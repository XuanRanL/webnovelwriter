# Step 3.5 外部模型审查规范（Round 11+ openclawroot 架构）

## 九模型共识架构 · 2 供应商

### 核心层（必须成功，异构性覆盖）

| 模型 key | openclawroot id | siliconflow 备用 | 特点 |
|---|---|---|---|
| `qwen3.6-plus` | `qwen3.6-plus` | — | 国产旗舰，识别语义重复最细致 |
| `gpt-5.4` | `gpt-5.4` | — | OpenAI 系，西方叙事视角，最快 2-7s |
| `gemini-3.1-pro` | `gemini-3.1-pro-high` | — | 谷歌系，画面感审视 |

### 补充层（失败不阻塞，累计 3 维度失败早停）

| 模型 key | openclawroot id | siliconflow 备用 | 特点 |
|---|---|---|---|
| `doubao-pro` | `Doubao-Seed-2.0-pro` | — | 结构审查严苛 |
| `glm-5` | `GLM-5` | `Pro/zai-org/GLM-5` | 中文编辑权威 |
| `glm-4.7` | `GLM-4.7` | `Pro/zai-org/GLM-4.7` | 文学质感 |
| `mimo-v2-pro` | `mimo-v2-pro` | — | 小米推理 |
| `minimax-m2.7-hs` | `MiniMax-M2.7-highspeed` | — | 对话情感推理 |
| `deepseek-v3.2-thinking` | `DeepSeek-V3.2-Thinking` | `Pro/deepseek-ai/DeepSeek-V3.2` | 技术考据 + 深度推理 |

## 供应商配置（2-tier）

- **主力**：openclawroot (`https://openclawroot.com/v1`)，key: `OPENCLAWROOT_API_KEY`，RPM=30
- **兜底**：siliconflow (`https://api.siliconflow.cn/v1`)，key: `EMBED_API_KEY`/`SILICONFLOW_API_KEY`，RPM=30（仅部分模型）

## 共识机制（核心设计）

- **9 模型 × 13 维度 = 117 份独立评分**
- 每个模型都跑**全 13 维度**（无分工！role 字段已删除 2026-04-16 Round 11）
- 多模型命中同一 issue → 真 bug；单模型孤例 → 模型偏见（cross_validation 自动过滤）
- 异构覆盖：国产（Doubao/GLM×2/Qwen/MiMo/MiniMax/DeepSeek）+ 西方（GPT/Gemini）

## Thinking 全开 + max_tokens 最大

- 所有模型 `max_tokens = 65536`（模型最大）
- OpenAI 系（gpt-5.4）：`reasoning_effort = "high"`
- Gemini 系：`thinking_budget = 16384`
- Qwen/DeepSeek/Doubao/GLM/MiMo 系：`enable_thinking = True`
- MiniMax 推理：`enable_thinking = True`
- 推理模型（mimo/minimax-hs/deepseek-thinking）若 `content` 为空，fallback 读 `reasoning_content`

## 重试与 fallback 规则

- **openclawroot**：重试 2 次，429 等 6s，403 立即切
- **siliconflow**：兜底，重试 1 次
- 幽灵零分（score=0 + 空摘要）：provider 层自动检测并切下一供应商重试
- 每次 API 调用后**路由验证**：检查 `response.model` 字段是否匹配请求模型
- Round 10+ 新增：外部模型 quote 幻觉自动 severity 降级（见 `_verify_quote_exists`）

## 并发控制

- `--model-key all` 模式：9 模型并发 × 每模型最多 6 维度并发（`DEFAULT_MAX_CONCURRENT=6`）
- 单模型全并发：13 维度同时跑（openclawroot RPM=30 够用）
- 补充层维度并发自动降至 min(6, 3) = 3（启用早停拦截排队中的维度）
- CLI 参数：`--max-concurrent N`、`--rpm-override N`

**推荐调用策略：**
- **首选**：`--model-key all` 一次性跑全部9个模型（9模型并发 × 维度并发，ProviderRateLimiter 自动控制 RPM）
- 单模型调用：`--model-key kimi`（调试或补跑单个模型时使用）
- `--max-concurrent N`：覆盖每模型的维度并发数（默认6；补充层自动降至 min(N, 3)）

**脚本调用命令（Agent 必须使用以下格式）：**
```bash
# 推荐：一次跑全部 9 模型
python -X utf8 "${SCRIPTS_DIR}/external_review.py" \
  --project-root "${PROJECT_ROOT}" \
  --chapter {chapter_num} \
  --mode dimensions \
  --model-key all

# 补跑单个模型
python -X utf8 "${SCRIPTS_DIR}/external_review.py" \
  --project-root "${PROJECT_ROOT}" \
  --chapter {chapter_num} \
  --mode dimensions \
  --model-key {model_key}
```

**⚠️ 脚本仅支持以下参数：**
`--project-root`, `--chapter`, `--mode`, `--model-key`, `--models`, `--max-concurrent`, `--rpm-override`
不支持 `--chapter-file`、`--outline-file` 等参数，传入会导致脚本直接报错退出。

**补充层早停机制：**
- 补充层维度并发自动降至3（而非核心层的全并发），使排队中的维度可被拦截
- 累计 3 个维度失败后触发 `threading.Event`，排队中的维度启动时立即跳过
- 避免 healwrap 连接中断时的无意义重试（如 minimax 21次失败）

## 路由验证规则

判定 routing_verified 的逻辑：
1. `response.model == model_requested` → true
2. `response.model` 含 "MiniMax" 但请求的是 glm → false（codexcc 已知问题）
3. `response.model` 含 "qianfan" 但请求的是 kimi → false（codexcc 已知问题）
4. 硅基流动的 model 名格式为 `Pro/xxx/Model`，与请求匹配时也算 true

## 外审 Prompt 模板

调用外部模型时，system 消息使用以下模板（`{context}` 替换为章节特定描述）：

```
你是一个资深网文章节审查专家。请从以下13个维度对章节进行严格审查并打分（0-100，Round 13 v2 · 新增 naturalness + reader_critic 读者视角双维度）：
1.设定一致性 2.连贯性 3.人物塑造 4.追读力 5.爽点密度 6.节奏控制 7.对话质量 8.信息密度 9.文笔质感 10.情感表现 11.读者视角流畅度（reader_flow，一人分饰两角失忆裸读协议）12.汉语母语自然度（naturalness，字句像不像真人写的、首句语病、AI 腔、伪神经科学痕迹）13.读者锐评（reader_critic，追更读者本能反应：是否愿意继续读、是否会弃章、亮点与劝退点）

{context}

请严格按以下 JSON 格式返回（不要加 ```json 标记，直接返回纯 JSON）：

{
  "overall_score": <0-100的数字>,
  "dimensions": [
    {
      "name": "<维度名>",
      "score": <0-100>,
      "comment": "<该维度的整体评语，2-3句>",
      "issues": [
        {
          "type": "<SETTING_CONFLICT|CONTINUITY|OOC|PACING|READER_PULL|STYLE|DIALOGUE_FLAT|DIALOGUE_INFODUMP|DIALOGUE_MONOLOGUE|PADDING|REPETITION|PROSE_FLAT|EMOTION_SHALLOW>",
          "severity": "<critical|high|medium|low>",
          "location": "<定位到具体段落，如'第3段主角与配角A对话处'>",
          "description": "<问题描述>",
          "suggestion": "<具体修改建议，给出改写方向或示例>",
          "quote": "<引用正文中的原句，便于定位>"
        }
      ]
    }
  ],
  "issues": [<所有维度的 issues 扁平化汇总>],
  "summary": "<80字以内的整体评价>"
}

**文笔质感维度补充 — 典故/诗词引用评审**（若正文含引用，纳入"文笔质感"维度评分）：
- 引用是否自然融入叙事？（"化用"好于"硬引"，"角色内化"好于"旁白注释"）
- 引用是否服务于剧情/角色/伏笔？（纯装饰=炫学，应在文笔质感维度扣分）
- 引用载体是否合理？（主角不应直接说互联网梗，学者型角色可以引经据典）
- 是否存在"正如XX所言"等生硬引导语？
- 无引用的章节不因此扣分

评分标准：
- 95-100: 出版级品质，几乎无可挑剔
- 90-94: 优秀，仅有轻微瑕疵
- 85-89: 良好，有少量可优化空间
- 80-84: 合格，存在若干需改进之处
- 75-79: 及格，有明显问题需要修复
- <75: 不合格，存在严重问题

issue 的 type 分类说明：
- SETTING_CONFLICT: 设定/能力/等级/物品与已有世界观矛盾
- CONTINUITY: 时间线/因果链/前后章衔接/倒计时错误
- OOC: 角色言行与已建立的人设不符
- PACING: 节奏失衡（信息过密/过疏、情绪无层次、段落过长）
- READER_PULL: 钩子弱/微兑现缺失/悬念管理不当
- STYLE: 句式AI化/说明腔/排版/对话自然度
- DIALOGUE_FLAT: 不同角色说话风格过于相似，遮住人名后无法分辨说话者
- DIALOGUE_INFODUMP: 角色对话只为向读者传递设定信息，缺少意图和冲突
- DIALOGUE_MONOLOGUE: 单人连续独白过长（超过200字），缺少互动打断
- PADDING: 段落无信息增量，不推进剧情/角色/情绪，属于水分填充
- REPETITION: 同一信息已通过其他方式传达后再次重复描述
- PROSE_FLAT: 文笔平淡/表现力不足（句式单调、比喻陈腐、感官贫乏、动词无力、画面感缺失）
- EMOTION_SHALLOW: 情感表达生硬/未落地（直述替代展示、情感梯度断裂、缺乏锚点、强行煽情）
```

## 开篇章节特殊处理（Ch1-3）

当审查的章节为 Ch1-3 时，在 system prompt 的 `{context}` 中额外追加：

```
【特别注意】这是小说的第{chapter}章（开篇章节）。请以首次接触本书的新读者视角额外评估：
1. 读完后是否有强烈意愿继续阅读？（1-10分）
2. 主角是否在前500字内建立了辨识度？
3. 世界观是否Show not Tell？
4. 有没有让你想跳过的段落？
5. 人物名字是否过多让你困惑？
开篇章节的评分标准应比普通章节更严格。
```

## User 消息结构（必须注入项目上下文）

外审 API 调用的 user 消息**不能只发章节正文**。必须按以下结构组装，让模型基于项目数据做有据可依的审查：

```
===== 项目上下文（请基于以下信息严格审查正文） =====

【本章大纲】
{从 大纲/第{volume_id}卷-详细大纲.md 中提取本章对应的 "### 第 N 章" 段落全文；volume_id 从 state.json 或总纲章节范围确定}

【主角设定】
{设定集/主角卡.md 全文}
{设定集/金手指设计.md 全文}

【配角设定】
{设定集/女主卡.md 全文}
{设定集/反派设计.md 全文}

【力量体系】
{设定集/力量体系.md 全文}

【世界观】
{设定集/世界观.md 全文}

【叙事声音基准（判断文笔风格是否符合作者设定，避免外部模型按"通用网文标准"盲评）】
{设定集/叙事声音.md 全文，若不存在则省略该节}

【情感蓝图（判断情感表现是否符合作者规划的基调，避免"克制冷峻"被误判为"情感不足"）】
{设定集/情感蓝图.md 全文，若不存在则省略该节}

【开篇策略（仅 Ch1-3 加载，判断前 3 章的特殊钩子规划是否执行到位）】
{设定集/开篇策略.md 全文，仅 chapter ≤ 3 时加载，否则省略}

【典故引用库（判断本章典故使用是否命中规划，避免"蓼蓼者莪"等预约伏笔被误判为"引用莫名其妙"）】
{设定集/典故引用库.md 全文，若不存在则省略该节}

【原创诗词口诀（判断原创资产使用是否按分批释放计划，避免原创口诀被误判为"炫学"）】
{设定集/原创诗词口诀.md 全文，若不存在则省略该节}

【前章正文（用于判断连贯性、角色一致性、节奏差异化、钩子回应）】
{正文/第{N-3:04d}章*.md 全文，若不存在则用 summaries/ch{N-3}.md 摘要替代}
{正文/第{N-2:04d}章*.md 全文，若不存在则用 summaries/ch{N-2}.md 摘要替代}
{正文/第{N-1:04d}章*.md 全文，若不存在则用 summaries/ch{N-1}.md 摘要替代}

【主角当前状态（注意：以下为第{当前章号}章后的最新状态，审查早期章节时信用点等动态数值可能与正文不一致，请以正文描述为准）】
{从 state.json 提取 protagonist_state 和 progress 字段，移除 attributes.credits}

【近期章节模式（判断钩子/情绪/模式是否重复）】
{从 state.json 的 chapter_meta 提取最近3章的钩子类型/强度、开场方式、情绪节奏、结束情绪/地点}

【活跃伏笔线（判断伏笔是否有回应、是否遗忘）】
{从 state.json 的 plot_threads.foreshadowing 提取所有 status=active/planted 的伏笔，标注埋设章号和紧迫度}

【节奏历史（判断节奏是否有差异化，避免连续同类型）】
{从 state.json 的 strand_tracker.history 提取最近5章的 dominant strand 类型}

===== 待审查正文 =====

{章节正文全文}
```

### 推荐执行方式（使用独立脚本）

> **注意**：原 SKILL.md 内联的 python -c 脚本只加载 9 个字段，存在"外部模型盲评"缺口。推荐改用独立脚本 `scripts/build_external_context.py`，加载完整 14 字段。

```bash
python -X utf8 "${SCRIPTS_DIR}/build_external_context.py" \
  --project-root "${PROJECT_ROOT}" \
  --chapter {chapter_num}
```

**新脚本的 14 个字段**：

| 类别 | 字段 | 来源 | 功能 |
|---|---|---|---|
| 核心 6 | outline_excerpt | 大纲/总纲.md | 主线参照 |
| | protagonist_card | 设定集/主角卡.md | 人设参照 |
| | golden_finger_card | 设定集/金手指设计.md | 金手指参照 |
| | female_lead_card | 设定集/女主卡.md | 配角参照 |
| | villain_design | 设定集/反派设计.md | 反派参照 |
| | power_system | 设定集/力量体系.md | 力量规则参照 |
| | world_settings | 设定集/世界观.md | 世界参照 |
| **质感 3** | **narrative_voice** | **设定集/叙事声音.md** | **避免通用网文盲评** |
| | **emotional_blueprint** | **设定集/情感蓝图.md** | **避免克制被误判** |
| | **opening_strategy**（Ch1-3） | **设定集/开篇策略.md** | **前 3 章钩子参照** |
| **典故 2** | **classical_references** | **设定集/典故引用库.md** | **识别预约典故伏笔** |
| | **original_poems** | **设定集/原创诗词口诀.md** | **识别原创资产** |
| 状态与前章 | protagonist_state | state.json | 主角状态 |
| | prev_chapters_text | 正文/第*章*.md | 前章正文 |

### 上下文加载规则

- 大纲提取：用 `### 第 N 章` 标题分割详细大纲，取本章完整段落（到下一个 `### 第` 或文件末尾）
- 前章正文：优先读 `正文/` 目录的完整章节文件（约3000字/章），缺失时退化为 `summaries/` 摘要。Ch1 无前章跳过；Ch2 只有1章；Ch3 有2章
- state.json：提取 `protagonist_state`、`progress`、最近3章 `chapter_meta`、活跃 `foreshadowing`、最近5条 `strand_tracker.history`
- **设定集（核心 6 个 · 必读）**：世界观 + 主角卡 + 金手指 + 力量体系 + 女主卡 + 反派 （约 7500 字）
- **设定集（质感 3 个 · 必读）**：叙事声音 + 情感蓝图 + （仅 Ch1-3）开篇策略 （约 3500 字）
  - **必须加载原因**：缺失会导致外部模型按"通用网文标准"盲评，把作者有意的"克制冷峻"误判为"情感不足"、把"慢热开篇"误判为"爽点密度低"
- **设定集（典故 2 个 · 条件必读）**：典故引用库 + 原创诗词口诀 （约 3000 字，若两文件存在）
  - **必须加载原因**：缺失会导致外部模型不识别预约的典故伏笔（如 S01《蓼莪》）和原创资产（如老陈遗诗），误判为"引用莫名其妙/炫学"
- 所有上下文在批量执行时一次性加载缓存，多章共用
- 总 user 消息约 **25000 字**（核心设定 7500 + 质感设定 3500 + 典故设定 3000 + 前3章正文 9000 + 状态/伏笔/节奏 1500 + 本章正文 3000），对 32K+ 模型无压力；若模型 context 窗口紧张，典故 2 个文件可降级为摘要（典故引用库只保留"角色文学图腾 + 第 N 卷规划总表"，原创诗词口诀只保留"全文索引表"）

### 上下文对维度审查的作用

| 上下文 | 使模型能够 |
|--------|----------|
| 大纲本章段落 | 判断正文是否偏离计划、爽点/钩子是否按纲执行 |
| 前3章正文 | 判断时间线衔接、角色状态延续、对话风格一致性、场景过渡、上章钩子回应、节奏差异化 |
| 近期章节模式 | 判断本章钩子/情绪/开场是否与近期重复 |
| 活跃伏笔线 | 判断伏笔是否有回应、是否被遗忘 |
| 节奏历史 | 判断节奏差异化，避免连续同类型章节 |
| 主角卡+金手指 | 判断主角言行是否符合人设、能力使用是否合规 |
| 力量体系 | 判断等级、技能、代价描述是否符合体系规则 |
| 世界观 | 判断地点、势力、社会规则是否与设定矛盾 |
| 女主卡+反派 | 判断配角言行是否 OOC |
| 前3章正文/角色卡 | 判断文笔是否有表现力、感官是否丰富、情感表达是否到位 |
| **叙事声音基准** | **按作者设定的视角/语气/密度/感官/对话比例/风格禁忌做文笔检查，避免"通用网文标准"盲评** |
| **情感蓝图** | **判断情感表现是否符合作者规划的基调（如"深沉治愈+间歇燃"），避免把克制误判为情感不足** |
| **开篇策略（Ch1-3）** | **判断前 3 章是否按开篇策略执行钩子、金手指展示、必传信息** |
| **典故引用库** | **识别本章典故是否命中卷规划表、角色文学图腾是否对应、引用密度是否超标** |
| **原创诗词口诀** | **识别本章原创资产是否按分批释放计划、是否有角色标志性台词** |

## 外审输出 JSON Schema

每个模型的审查结果文件（`.webnovel/tmp/external_review_{model_key}_ch{NNNN}.json`）必须包含：

```json
{
  "agent": "external-{model_key}",
  "chapter": 27,
  "model_key": "kimi",
  "model_requested": "kimi-k2.5",
  "model_actual": "<response.model字段的值>",
  "provider": "healwrap",
  "routing_verified": true,
  "overall_score": 87,
  "pass": true,
  "dimension_reports": [
    {
      "dimension": "consistency",
      "name": "设定一致性",
      "status": "ok",
      "score": 88,
      "issues": [
        {
          "type": "SETTING_CONFLICT",
          "severity": "low",
          "location": "第5段",
          "description": "...",
          "suggestion": "...",
          "quote": "原文引用...",
          "verified": "verified|unverified|dismissed"
        }
      ],
      "summary": "评语...",
      "model": "Kimi-K2.5",
      "model_actual": "kimi-k2.5",
      "provider": "healwrap",
      "routing_verified": true,
      "elapsed_ms": 8500
    }
  ],
  "issues": [],
  "cross_validation": {
    "total_issues": 5,
    "verified": 3,
    "unverified": 1,
    "dismissed": 1
  },
  "provider_chain": [
    {"provider": "healwrap", "attempt": 1, "result": "success", "routing_ok": true}
  ],
  "api_meta": {
    "final_provider": "healwrap",
    "elapsed_ms": 8500,
    "prompt_tokens": 2300,
    "completion_tokens": 1800,
    "attempts_total": 1
  },
  "summary": "..."
}
```

## 交叉验证规则

外审 Agent 在拿到模型返回后，用已读取的项目上下文（state.json/前章摘要/大纲）验证每个 issue：
- `verified`: issue 提到的事实与项目数据一致
- `unverified`: 无法从已有数据确认或否认
- `dismissed`: issue 提到的"错误"实际上项目数据中有依据支持（误报）

## 审查报告格式

`审查报告/第{NNNN}章审查报告.md` 必须包含：

1. **9模型评分矩阵**（可用模型 × 13维度 + 总分 + 路由状态 + 供应商，Round 13 v2 · 含 reader_flow + naturalness + reader_critic）
2. **共识问题**（>=3个模型指出的同类问题 = 真问题）
3. **Step 4 修复清单**（从共识问题 + severity >= medium + verified 中筛选，按优先级排序）
4. **模型路由验证结果**（每个模型的请求/实际/通过状态）
5. **润色记录**（Step 4 修复后填写 anti_ai_force_check 和毒点检查结果）
