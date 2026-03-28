# Step 3.5 外部模型审查（Agent化，6维度×3模型）

## 目的

在 Step 3 的同时，调用3个外部模型各自独立做6维度审查，产出18份报告供Claude统一复核。

## 触发条件

- Step 2A 完成后，与 Step 3 同时启动（并行）
- 所有模式均执行，不可跳过

## 架构

```
Step 3 + 3.5 并行：
  Claude 6个checker ──────────┐
  external-review-agent(qwen) ──┤── 全部完成 → Claude汇总24份报告
  external-review-agent(kimi) ──┤
  external-review-agent(glm) ───┘
```

## 外部审查Agent执行流程

每个 external-review-agent 内部：
1. 读取完整项目上下文（state.json/大纲/设定集/摘要）
2. 写入 context JSON 文件
3. 调用 `external_review.py --mode dimensions --model-key {key}`
4. 脚本内部并发6个维度的API调用
5. agent用项目上下文交叉验证结果
6. 输出统一格式报告

## 6个审查维度

| 维度 | 对应内部checker | 检查重点 |
|------|----------------|----------|
| consistency | consistency-checker | 设定/战力/时间线一致性 |
| continuity | continuity-checker | 场景过渡/伏笔/逻辑连贯 |
| ooc | ooc-checker | 角色行为/对话/成长一致性 |
| reader_pull | reader-pull-checker | 钩子/微兑现/追读力 |
| high_point | high-point-checker | 爽点密度/类型差异化 |
| pacing | pacing-checker | 章内节奏/信息密度/strand平衡 |

## 模型配置

| 模型 | 主力 (codexcc) | 备用 (硅基流动) |
|------|---------------|----------------|
| qwen | qwen3.5-plus | Qwen/Qwen3.5-397B-A17B |
| kimi | kimi-k2.5 | Pro/moonshotai/Kimi-K2.5 |
| glm | glm-5 | Pro/zai-org/GLM-5 |

## 脚本调用

```bash
python -X utf8 "${SCRIPTS_DIR}/external_review.py" \
  --project-root "${PROJECT_ROOT}" \
  --chapter {chapter_num} \
  --mode dimensions \
  --model-key {qwen|kimi|glm}
```

## Claude汇总复核

Step 3 + 3.5 全部完成后，Claude统一处理24份报告：

**采纳标准：**
- 必须采纳：2个以上来源（含Claude自身）指出同一问题
- 建议采纳：外部模型发现的 critical/high 问题，Claude复核确认属实
- 可忽略：仅1个外部模型提出且Claude判断为误报

**输出：**
```
审查汇总 - 第 {chapter_num} 章
- Claude内部审查: 6个checker，综合 {score}
- 外部审查: qwen={score} kimi={score} glm={score}
- 交叉验证采纳: {N} 个问题
- 驳回: {N} 个问题
- 可进入润色: 是/否
```

## 失败处理

- 单个外部模型全部失败：标记该模型为error，不阻塞流程
- 3个外部模型全部失败：报告错误，Claude基于Step 3结果继续
- Step 3.5 不构成硬闸门，Step 3 通过即可进入 Step 4
