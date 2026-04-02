# Step 3.5 外部模型审查规范

## 六模型双层架构

### 核心层（必须成功，有 fallback 保障）

| 模型 | 角色 | healwrap | codexcc | 硅基流动 |
|------|------|---------|---------|---------|
| kimi-k2.5 | 严审/逻辑 | `kimi-k2.5` | `kimi-k2.5` | `Pro/moonshotai/Kimi-K2.5` |
| glm-5 | 编辑/读者感受 | `glm-5` | `glm-5` | `Pro/zai-org/GLM-5` |
| qwen3.5-plus | 网文/爽点 | `qwen3.5-plus` | `qwen3.5-plus` | `Qwen/Qwen3.5-397B-A17B` |

### 补充层（仅 healwrap，失败不阻塞）

| 模型 | 角色 |
|------|------|
| qwen-3.5 | 宽松锚点 |
| deepseek-v3.2 | 技术考据 |
| minimax-m2.5 | 快速参考 |

## 供应商配置

**三级 fallback：**
- 主力：healwrap (`https://llm-api.healwrap.cn/v1`)，key: HEALWRAP_API_KEY，RPM=10
- 备用1：codexcc (`https://api.codexcc.top/v1`)，key: CODEXCC_API_KEY
- 备用2/兜底：硅基流动 (`https://api.siliconflow.cn/v1`)，key: EMBED_API_KEY

**重试与 fallback 规则：**
- 核心3模型统一链：healwrap(重试2次) → codexcc(错误1次切) → 硅基流动(兜底)
- 补充3模型：healwrap(重试2次) → 失败标记 error 继续
- 每次 API 调用后**必须验证路由**：检查 response.model 字段是否匹配请求模型
- 路由错误视为该供应商不可用，不重试直接切下一个
- 429限流：等6秒后重试；超时：计入重试次数

**并发控制（RPM 安全策略）：**
- 每模型的8维度以 `--max-concurrent 2` 并发执行（默认值，避免瞬时打满 healwrap RPM=10）
- 6模型按顺序依次审查（脚本单次调用处理1个模型，由工作流串行/并行调度多模型）
- 内置 `ProviderRateLimiter`：per-provider 令牌桶限速，自动按 RPM 间隔排队
- 若遇 429 限流：等6秒后重试（与限速器协同，不会连续触发 429）
- fallback 到 codexcc/硅基流动不占 healwrap RPM
- CLI 参数：`--max-concurrent N`（覆盖并发数）、`--rpm-override N`（覆盖 healwrap RPM）

**推荐调用策略：**
- 核心3模型可并行调用（各自独立进程，限速器 per-进程独立，healwrap 30 RPM 以内安全）
- 补充3模型串行调用（共享同一 healwrap 连接池，间隔执行）
- 如果 healwrap RPM 升级到 30+，可设置 `--max-concurrent 4`

## 路由验证规则

判定 routing_verified 的逻辑：
1. `response.model == model_requested` → true
2. `response.model` 含 "MiniMax" 但请求的是 glm → false（codexcc 已知问题）
3. `response.model` 含 "qianfan" 但请求的是 kimi → false（codexcc 已知问题）
4. 硅基流动的 model 名格式为 `Pro/xxx/Model`，与请求匹配时也算 true

## 外审 Prompt 模板

调用外部模型时，system 消息使用以下模板（`{context}` 替换为章节特定描述）：

```
你是一个资深网文章节审查专家。请从以下8个维度对章节进行严格审查并打分（0-100）：
1.设定一致性 2.连贯性 3.人物塑造 4.追读力 5.爽点密度 6.节奏控制 7.对话质量 8.信息密度

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
          "type": "<SETTING_CONFLICT|CONTINUITY|OOC|PACING|READER_PULL|STYLE|DIALOGUE_FLAT|DIALOGUE_INFODUMP|DIALOGUE_MONOLOGUE|PADDING|REPETITION>",
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

### 上下文加载规则

- 大纲提取：用 `### 第 N 章` 标题分割详细大纲，取本章完整段落（到下一个 `### 第` 或文件末尾）
- 前章正文：优先读 `正文/` 目录的完整章节文件（约3000字/章），缺失时退化为 `summaries/` 摘要。Ch1 无前章跳过；Ch2 只有1章；Ch3 有2章
- state.json：提取 `protagonist_state`、`progress`、最近3章 `chapter_meta`、活跃 `foreshadowing`、最近5条 `strand_tracker.history`
- 设定集：全部拼接（世界观+主角卡+金手指+力量体系+女主卡+反派），约 7500 字
- 所有上下文在批量执行时一次性加载缓存，多章共用
- 总 user 消息约 21000 字（设定集 7500 + 前3章正文 9000 + 状态/伏笔/节奏 1500 + 本章正文 3000），对 32K+ 模型无压力

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

1. **6模型评分矩阵**（可用模型 × 8维度 + 总分 + 路由状态 + 供应商）
2. **共识问题**（>=3个模型指出的同类问题 = 真问题）
3. **Step 4 修复清单**（从共识问题 + severity >= medium + verified 中筛选，按优先级排序）
4. **模型路由验证结果**（每个模型的请求/实际/通过状态）
5. **润色记录**（Step 4 修复后填写 anti_ai_force_check 和毒点检查结果）
