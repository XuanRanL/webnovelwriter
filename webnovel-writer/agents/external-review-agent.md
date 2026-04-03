---
name: external-review-agent
description: 外部模型审查Agent，调用外部API对章节进行10维度独立审查，输出结构化报告
tools: Read, Grep, Bash
model: inherit
---

# external-review-agent (外部模型审查器)

> **职责**: 读取完整项目上下文，构建10维度审查prompt，调用外部模型API获取独立审查意见，交叉验证后输出结构化报告。

> **输出格式**: 遵循 `${CLAUDE_PLUGIN_ROOT}/references/checker-output-schema.md` 统一 JSON Schema
>
> **重要**: Prompt 模板、输出 JSON Schema、供应商配置、fallback 链、路由验证规则以 `${CLAUDE_PLUGIN_ROOT}/skills/webnovel-write/references/step-3.5-external-review.md` 为准（优先于本文件中的旧示例）。若 workspace 存在 `.cursor/rules/external-review-spec.mdc`，以其为最高优先级。

## 输入参数

```json
{
  "chapter": 11,
  "chapter_file": "正文/第0011章-猎人公会.md",
  "project_root": "{PROJECT_ROOT}",
  "model_key": "qwen-plus|kimi|glm|qwen|deepseek|minimax",
  "scripts_dir": "{SCRIPTS_DIR}"
}
```

**model_key 说明**:
- 核心层（必须成功，有 fallback 保障）：`qwen-plus`（网文/爽点）、`kimi`（严审/逻辑）、`glm`（编辑/读者感受）
- 补充层（仅 healwrap，失败不阻塞）：`qwen`（宽松锚点）、`deepseek`（技术考据）、`minimax`（快速参考）
- 编排层应为 6 个模型各调用一次本 Agent（或脚本），核心 3 个必须全部成功才能进入 Step 4

## 执行流程

### 第一步: 加载项目上下文

并行读取：
1. 目标章节正文（`chapter_file`）
2. `{project_root}/.webnovel/state.json`（主角状态、chapter_meta）
3. `{project_root}/设定集/世界观.md`
4. `{project_root}/设定集/主角卡.md`
5. `{project_root}/设定集/力量体系.md`
6. `{project_root}/大纲/第{volume_id}卷-详细大纲.md`（当前章节对应的大纲段落；volume_id 从 state.json 当前卷信息获取，缺失时从 `大纲/总纲.md` 的章节范围反推）
7. 前3章正文：`{project_root}/正文/第{N-1:04d}章*.md`、`第{N-2:04d}章*.md`、`第{N-3:04d}章*.md`（正文文件缺失时退化为摘要）

### 第二步: 调用外部审查脚本

```bash
python -X utf8 "${scripts_dir}/external_review.py" \
  --project-root "${project_root}" \
  --chapter {chapter} \
  --model-key {model_key} \
  --mode dimensions
```

脚本会自动从 `{project_root}/.webnovel/tmp/external_context_ch{NNNN}.json` 加载上下文。调用前，agent必须先将收集到的上下文写入该文件：

```bash
cat > "${project_root}/.webnovel/tmp/external_context_ch{NNNN}.json" << 'EOF'
{
  "outline_excerpt": "本章大纲段落...",
  "protagonist_card": "主角卡全文...",
  "golden_finger_card": "金手指设计全文...",
  "female_lead_card": "女主卡全文...",
  "villain_design": "反派设计全文...",
  "power_system": "力量体系全文...",
  "world_settings": "世界观全文...",
  "protagonist_state": { ... },
  "prev_chapters_text": "前3章正文（正文缺失时用摘要替代）..."
}
EOF
```

> **注意**：脚本对每个字段有磁盘 fallback——如果 JSON 中某字段缺失或为空，会自动从 `设定集/`、`正文/`、`.webnovel/` 目录读取。但 agent 应尽量填充完整以减少磁盘 I/O。

脚本会对8个维度并发调用外部模型API，返回8份JSON报告。

### 第三步: 交叉验证（不可省略）

> **此步骤为必做步骤**。脚本层面的 `cross_validation.dismissed` 始终为 0（脚本无法访问项目上下文），必须由 Agent 在此步骤中完成项目数据对比验证。

对脚本返回的每个issue，agent用自己读到的项目上下文做快速验证：

- `verified`：issue 提到的事实与 state.json/设定集/前章正文的数据一致（确认为真问题）
- `unverified`：无法从已有数据确认或否认
- `dismissed`：issue 提到的"错误"实际上在项目数据中有依据支持（误报），标注 `reason: "项目数据支持: {具体依据}"`

验证完成后，更新 `cross_validation` 统计，将 `dismissed` 数量更新为非零值（如有误报）。

### 第四步: 输出报告

输出统一格式JSON，agent名称为 `external-{model_key}-{dimension}`：

```json
{
  "agent": "external-qwen",
  "chapter": 11,
  "model_key": "qwen",
  "model_name": "qwen3.5-plus",
  "provider": "healwrap",
  "overall_score": 88,
  "pass": true,
  "dimension_reports": [
    {
      "dimension": "consistency",
      "name": "设定一致性",
      "status": "ok",
      "score": 90,
      "issues": [...],
      "summary": "...",
      "model": "Kimi-K2.5",
      "model_actual": "kimi-k2.5",
      "provider": "healwrap",
      "routing_verified": true,
      "elapsed_ms": 8500
    }
  ],
  "issues": [ ... ],
  "metrics": {
    "api_calls": 8,
    "api_failures": 0,
    "verified_issues": 3,
    "unverified_issues": 1,
    "dismissed_issues": 2
  },
  "summary": "总结"
}
```

## 失败处理

- 单个维度API调用失败：重试2次，仍失败则标记该维度为 `"status": "failed"`，继续其他维度
- 全部8个维度失败：输出 `"pass": false, "error": "all_dimensions_failed"`
- JSON解析失败：重试1次，仍失败则标记 `"status": "parse_error"`
