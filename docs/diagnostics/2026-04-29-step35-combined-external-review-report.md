# Step 3.5 Combined External Review 根治报告

日期：2026-04-29

## 一、问题结论

Step 3.5 的 token 爆炸 root cause 不是 14 模型本身，而是旧 `dimensions` 路径把同一模型拆成 13 次维度请求。每次请求都重新发送完整 `context_block + chapter_text`，导致同一模型重复消耗 13 份大上下文。

Ch20 实测：

- 外审产物记录 prompt tokens 合计约 `12,325,450`
- provider attempts 合计 `249`
- 成功维度 `166/182`
- `external_context_ch0020.json` 约 `276KB`
- 正文约 `9.5KB`

这说明物理请求层面是 `14 模型 × 13 维度 = 182 次主请求`（再叠加 retry/fallback），而不是“每个模型一次审完 13 维”。

## 二、Root Cause

1. `call_dimension()` 对每个维度独立构造 prompt，并把 `{context_block}` + `{chapter_text}` 塞入每次请求。
2. `_run_single_model()` 旧实现遍历 `DIMENSIONS.items()`，为同一个模型提交 13 个维度任务。
3. `--model-key all` 只是一次启动全部模型，不等于每个模型一次请求；模型层还被线程池限制为 4 并发排队。
4. 文档混有旧口径（9 模型、核心3、补充层、14 模型并发），掩盖了真实物理请求数与成本。

## 三、目标

- 正常路径：每个外部模型只发 1 次请求，一次返回 13 个 `dimension_reports`。
- 保留逻辑评分矩阵：14 模型 × 13 维度 = 182 个评分点。
- 保持产物兼容：继续写 `.webnovel/tmp/external_review_{model_key}_chNNNN.json`，字段结构兼容 Step 4 / Step 6。
- 保留旧 split：只用于 debug、combined 坏 JSON、缺维度、provider context 异常时 fallback。

## 四、实施内容

### 1. `scripts/external_review.py`

- 新增 `--dimension-strategy auto|combined|split`，默认 `auto`
- 新增 `--model-concurrent N` 控制 `--model-key all` 模型层并发，默认 4
- `auto` 流程：
  - 先走 combined：每模型 1 次请求返回全部 13 维
  - 校验 `dimension_reports` 是否含完整 canonical 13 维
  - JSON 不可用 / 维度缺失 / score 非法 → 记录 `strategy_fallback_reason` 并退回 split
- `split` 流程：
  - 保留旧 13 次维度请求
  - `--max-concurrent` 仅控制 split/fallback 的维度并发
- 输出新增：
  - `api_meta.review_strategy = combined|split`
  - `api_meta.strategy_fallback_reason`（仅 auto fallback 时出现）
  - dimension 内 `review_strategy`
- 抽出公共保存逻辑，保留原 merge-partial 行为。

### 2. 文档与技能同步

已同步：

- `webnovel-writer/skills/webnovel-write/SKILL.md`
- `webnovel-writer/skills/webnovel-write/references/step-3.5-external-review.md`
- `webnovel-writer/agents/external-review-agent.md`
- `.cursor/rules/external-review-spec.mdc`
- `.cursor/rules/webnovel-workflow.mdc`
- `webnovel-writer/CUSTOMIZATIONS.md`

旧口径已清理：

- “9 个外部模型 / 共9个文件”
- “核心3必须成功 / 补充6失败不阻塞”
- “补充层累计3维度失败早停”
- “gpt-5.4 主模型 / mimo-v2-pro 主模型”
- “14 模型并发 × 每模型 6 维度并发”作为默认路径

### 3. 测试新增

新增：

- `webnovel-writer/scripts/data_modules/tests/test_external_review_combined_strategy.py`

覆盖：

- combined 策略下单模型只调用 provider 一次，并写出 13 个维度
- auto 策略遇到 combined 缺维度，自动 fallback 到 split
- split 策略跳过 combined，保持旧行为

## 五、预期效果

正常路径物理请求数：

- 旧：`14 × 13 = 182` 次主请求
- 新：`14 × 1 = 14` 次主请求

按 Ch20 的上下文规模估算：

- prompt token 下降约 85%-90%
- provider attempts 从数百级降到十几到几十级
- rate limit / timeout / partial file 风险显著下降
- Step 3.5 更接近“模型共识”而不是“维度线程池压力测试”

## 六、外部能力参考

- OpenAI Prompt Caching 官方文档：长 prompt（≥1024 tokens）可显示 `cached_tokens`，重复前缀有缓存收益；combined 进一步从源头减少重复输入。
  https://developers.openai.com/api/docs/guides/prompt-caching
- OpenAI Structured Outputs 官方文档：支持 strict JSON schema；当前第三方 OpenAI-compatible provider 不保证全支持，所以本次没有强依赖，只保留为后续 provider capability 优化方向。
  https://developers.openai.com/api/docs/guides/structured-outputs
- OpenAI Batch API FAQ：Batch 有成本优势，但 Step 3.5 是同步写作闸门，不适合作为主路径，只适合历史补审/离线回归。
  https://help.openai.com/en/articles/9197833-batch-api-faq

## 七、测试结果

通过：

```text
python -X utf8 -m py_compile webnovel-writer\scripts\external_review.py
python -X utf8 -m pytest webnovel-writer\scripts\data_modules\tests\test_external_review_combined_strategy.py -q --no-cov
3 passed
python -X utf8 -m pytest webnovel-writer\scripts\data_modules\tests\test_round13_consistency.py webnovel-writer\scripts\data_modules\tests\test_ch1_round10_rca.py -q --no-cov
28 passed
python -X utf8 -m pytest webnovel-writer\scripts\data_modules\tests\test_external_review_combined_strategy.py webnovel-writer\scripts\data_modules\tests\test_round13_consistency.py webnovel-writer\scripts\data_modules\tests\test_ch1_round10_rca.py -q --no-cov
31 passed
git diff --check
exit 0
```

注意：

```text
python -X utf8 -m pytest webnovel-writer\scripts\data_modules\tests\test_chapter_audit.py -q --no-cov
1 failed: test_G2_word_count_trend_warns_when_too_long
```

该失败位于 G2 字数趋势检查，断言 3601 字应 warn，但当前返回 pass。`chapter_audit.py` 与其测试文件在本次修改前已处于 dirty 状态；此失败与 Step 3.5 combined 外审产物兼容性无关，未在本轮改动中处理。

## 八、后续优化建议

1. 对支持 strict JSON schema 的 provider 增加 capability 开关，优先用 provider 原生结构化输出。
2. 增加 combined 质量监控：13 维 summary 高相似、所有分数相同、低分无 issue 等偷懒模式自动 warn/fallback。
3. 增加真实单模型 dry-run：先用 `--model-key qwen3.6-plus --dimension-strategy combined` 对 Ch20 做一次低风险验证，再放开 `--model-key all`。
4. 单独修复 `chapter_audit.py` 的 G2 字数趋势测试，避免全量测试长期带红。
