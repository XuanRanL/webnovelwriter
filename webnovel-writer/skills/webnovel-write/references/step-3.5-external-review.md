# Step 3.5 外部模型审查（External Model Review）

## 目的

在 Claude 审查（Step 3）通过后，调用外部大模型做独立的"生产评分"。
外部模型视角与 Claude 不同，能发现 Claude 自审盲区（设定偏差、逻辑漏洞、读者感受）。

## 触发条件

- Step 3 `overall_score` 已生成且 ≥ 70（即 Step 3 基本通过）。
- **所有模式均执行**（标准 / `--fast` / `--minimal`），不可跳过。

## 外部模型配置

使用硅基流动（SiliconFlow）API，双模型并行审查：

| 模型 | ID | 角色 |
|------|----|------|
| Qwen3.5-397B | `Qwen/Qwen3.5-397B-A17B` | 设定/逻辑审查（区分度高，敢给 critical） |
| GLM-5 | `Pro/zai-org/GLM-5` | 编辑/读者感受审查（视角独特，嗅觉锐利） |

API 配置：
```
BASE_URL: https://api.siliconflow.cn/v1/chat/completions
API_KEY: 从 ~/.claude/webnovel-writer/.env 的 EMBED_API_KEY 读取
```

## 执行流程

### 1. 调用外部审查脚本

```bash
python -X utf8 "${SCRIPTS_DIR}/external_review.py" \
  --project-root "${PROJECT_ROOT}" \
  --chapter {chapter_num} \
  --models "qwen,glm5"
```

脚本输出：`${PROJECT_ROOT}/.webnovel/tmp/external_review_ch{NNNN}.json`

### 2. Claude 综合讨论

主流程读取外部审查结果，逐条评估：

**采纳标准**：
- **必须采纳**：外部模型发现的 `critical` 或 `high` 问题，且 Claude 复核确认属实
- **建议采纳**：外部模型发现的 `medium` 问题，Claude 认为有道理
- **可忽略**：外部模型的 `low` 问题，或 Claude 判断为误报/过度解读

**讨论输出格式**：
```
外部审查讨论 - 第 {chapter_num} 章
- Qwen3.5 评分: {score} | GLM-5 评分: {score}
- 采纳问题: {N} 个
  - [来源] 问题描述 → 修复方案
- 驳回问题: {N} 个
  - [来源] 问题描述 → 驳回理由
```

### 3. 执行修复

将采纳的问题修复写入正文（覆盖章节文件），然后进入 Step 4。

## 审查 Prompt 模板

外部模型使用统一的审查 prompt，包含：
- 四维度评分（设定一致性 / 连贯性 / 人物塑造 / 追读力）
- 小说背景信息（从 state.json 动态读取）
- 前序章节摘要（从 summaries/ 读取最近 2-3 章）
- JSON 格式输出要求

## 输出契约

Step 3.5 完成后必须产出：
1. 外部审查 JSON 文件（双模型结果）
2. Claude 讨论摘要（采纳/驳回列表）
3. 修复后的正文（如有修改）

## 进入 Step 4 前闸门

- Step 3.5 外部审查已完成（双模型均返回结果或超时）
- Claude 已逐条评估并记录采纳/驳回决定
- 采纳的问题已修复写入正文

## 禁止事项

- 禁止跳过外部审查（即使 Step 3 分数很高）
- 禁止不经 Claude 讨论直接采纳外部模型意见
- 禁止忽略外部模型发现的 critical/high 问题（必须复核并给出明确结论）
