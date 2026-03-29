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

**并发控制（RPM=10）：**
- 6模型一次性并发发出（max_workers=6），不分批
- 若遇 429 限流：等6秒后重试
- fallback 到 codexcc/硅基流动不占 healwrap RPM

## 路由验证规则

判定 routing_verified 的逻辑：
1. `response.model == model_requested` → true
2. `response.model` 含 "MiniMax" 但请求的是 glm → false（codexcc 已知问题）
3. `response.model` 含 "qianfan" 但请求的是 kimi → false（codexcc 已知问题）
4. 硅基流动的 model 名格式为 `Pro/xxx/Model`，与请求匹配时也算 true

## 外审 Prompt 模板

调用外部模型时，system 消息使用以下模板（`{context}` 替换为章节特定描述）：

```
你是一个资深网文章节审查专家。请从以下6个维度对章节进行严格审查并打分（0-100）：
1.设定一致性 2.连贯性 3.人物塑造 4.追读力 5.爽点密度 6.节奏控制

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
          "type": "<SETTING_CONFLICT|CONTINUITY|OOC|PACING|READER_PULL|STYLE>",
          "severity": "<critical|high|medium|low>",
          "location": "<定位到具体段落，如'第3段陆衍与韩远对话处'>",
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
```

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
      "name": "设定一致性",
      "score": 88,
      "comment": "评语...",
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
      ]
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

1. **6模型评分矩阵**（可用模型 × 6维度 + 总分 + 路由状态 + 供应商）
2. **共识问题**（>=3个模型指出的同类问题 = 真问题）
3. **Step 4 修复清单**（从共识问题 + severity >= medium + verified 中筛选，按优先级排序）
4. **模型路由验证结果**（每个模型的请求/实际/通过状态）
5. **润色记录**（Step 4 修复后填写 anti_ai_force_check 和毒点检查结果）
