# 2026-04-29 Step 3.5 外部模型 api666 / max_tokens / thinking 根因报告

## 结论

- `gemini-3.1-pro` 原主路 `openclawroot/gemini-3.1-pro-high` 历史不稳定：Ch4/5/8/15/20 为 0 维成功，Ch6/11/19 partial，Ch14 出现 51.9 outlier；错误集中在 `http_503` / `http_524` / `http_400`。
- 已将 `gemini-3.1-pro` 主 provider 切到 `api666/gemini-3.1-pro-preview`，保留 openclawroot fallback。
- 正式 Step 3.5 dimensions 模式已是 combined 默认：正常路径每个模型 1 次请求返回 13 个 `dimension_reports`，不再按维度重复发送大上下文。
- 所有正式外审路由的 `max_tokens` 已锁定为 provider 上限：默认 65536；已知受限路由为 `ark-coding/deepseek-v3.2`、`ark-coding/kimi-k2.5`、`siliconflow/Pro/moonshotai/Kimi-K2.5`，均为 32768。
- 所有正式外审路由已显式打开 thinking/reasoning：ark-coding 用 `thinking={"type":"enabled"}`；GPT 用 `reasoning_effort="high"`；Gemini 用 `thinking_budget=16384`；Qwen/DeepSeek/Doubao/GLM/MiMo/MiniMax/Kimi 用 `enable_thinking=True`。

## 根因

1. Gemini 主路供应商不稳  
   历史产物显示 openclawroot 的 Gemini 路由在多章出现整模型 0 维成功或 partial，且 Ch14 有低分 outlier。这不是章节内容问题，而是供应商路由/网关稳定性问题。

2. Kimi fallback thinking 缺口  
   `call_api()` 的通用 OpenAI-compatible 分支只匹配 `qwen/deepseek/doubao/glm/mimo/minimax`，没有匹配 `kimi`。因此当 Kimi 走 `siliconflow/Pro/moonshotai/Kimi-K2.5` fallback 时，虽然 max_tokens 正确为 32768，但没有显式发送 `enable_thinking=True`。

3. healthcheck 误报  
   旧 healthcheck 使用 8 秒超时。`glm-5.1` 正式调用约 10-20 秒返回，8 秒探针会把慢但正常的 reasoning 模型误报为不可用。

## 修改

- `webnovel-writer/scripts/external_review.py`
  - 新增 provider `api666`：`https://api-666.cc/v1/chat/completions`。
  - `gemini-3.1-pro` provider 顺序改为 `api666/gemini-3.1-pro-preview` → `openclawroot/gemini-3.1-pro-high`。
  - 通用 thinking 匹配补上 `kimi`，修复 SiliconFlow Kimi fallback 未显式开启 thinking。
  - healthcheck timeout 从 8s 提升到 30s。
  - 注释同步为 6 provider 架构。

- Skills / agents / rules
  - `webnovel-writer/skills/webnovel-write/references/step-3.5-external-review.md`
  - `webnovel-writer/agents/external-review-agent.md`
  - `.cursor/rules/webnovel-workflow.mdc`
  - `.cursor/rules/external-review-spec.mdc`
  - `webnovel-writer/CUSTOMIZATIONS.md`

- Tests
  - `test_gemini_uses_api666_preview_before_openclawroot_fallback`
  - `test_gemini_api666_payload_keeps_max_tokens_and_thinking`
  - `test_kimi_siliconflow_fallback_payload_enables_thinking`
  - `test_model_provider_max_tokens_are_declared_caps`
  - `test_all_external_review_routes_apply_reasoning_payload`

## 实测

### api666 Gemini 直连 smoke

- provider: `api666`
- requested model: `gemini-3.1-pro-preview`
- actual model: `gemini-3.1-pro-preview-maxthinking-search`
- error: `null`
- attempts: 1
- usage: prompt 15 / completion 866 / reasoning 402
- 结论：api666 路由可用，Gemini thinking 实际生效。

### Step 3.5 dimensions combined 临时项目 E2E

- command: `external_review.py --mode dimensions --model-key gemini-3.1-pro --dimension-strategy combined`
- provider: `api666`
- requested model: `gemini-3.1-pro-preview`
- actual model: `gemini-3.1-pro-preview-maxthinking-search`
- routing_verified: `true`
- review_strategy: `combined`
- dimensions_ok: 13/13
- overall_score: 90.1
- prompt_tokens: 20666
- completion_tokens: 5132
- attempts_total: 1
- elapsed_ms: 44908
- 结论：Step 3.5 正式 combined 路径正常，一次请求拿到全部 13 维报告。

### 14 模型 healthcheck

- 修复前：13/14 healthy，`glm-5.1` 8 秒探针 ReadTimeout。
- `glm-5.1` 正式参数单测：成功，actual `glm-5.1`，reasoning_tokens 800。
- 修复后：14/14 healthy。

## 安全

- API key 只写入本地 `.env` / 用户全局 `.env`，不写入 tracked 代码、skills、rules 或报告。
