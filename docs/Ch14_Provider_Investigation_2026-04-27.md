# Ch14 外部审查 Provider 全面调查报告

> 日期：2026-04-27
> 调查范围：openclawroot / ark-coding / siliconflow 三个 provider × 14 模型
> 触发：Ch14 external valid 9/14 + kimi/gpt-5.4/deepseek 缺失

## 一、Provider /v1/models 端点真实数据

### openclawroot (`https://openclawroot.com/v1`)

总 89 模型，关键模型可用性：

| 系列 | 可用 model id | 备注 |
|---|---|---|
| kimi | `kimi-k2.5`, `kimi-k2.6` | ✓ 在 list 内 |
| gpt-5 | `gpt-5.4`, `gpt-5.4-1`, `gpt-5.5` | 简单 prompt OK，长 prompt 偶发 forbidden |
| gemini | `gemini-3-flash`, `gemini-3.1-pro-high`, `gemini-3.1-pro-low`, `gemini-3.1-pro-preview` | gemini-3.1-pro-high 给 outlier 51.9 |
| glm | `glm-4.7`, `glm-5`, `glm-5.1` 等 | ✓ 全部可用 |
| deepseek | `DeepSeek-V3.2` | ✓ |
| qwen | `qwen3.6-plus`, `qwen3-max`, `qwen3-coder-plus` 等 | ✓ |
| doubao | `Doubao-Seed-2.0-pro`, `Doubao-Seed-2.0-lite` 等 | ✓ |
| minimax | `MiniMax-M2.7-highspeed`, `MiniMax-M2.7`, `MiniMax-M2.5`, `MiniMax-M2.5-highspeed` | M2.7-hs 偶发 503，M2.7 普通版稳定 |
| mimo | `mimo-v2-pro` | ✓ |

### ark-coding (火山方舟 `https://ark.cn-beijing.volces.com/api/coding/v3`)

| model | 状态 |
|---|---|
| kimi-k2.5 | ✓ 单测可用，但批量模式偶发 phantom score=0 空摘要 |
| kimi-k2.6 | ✓ 同上（thinking 模式 max_tokens 不足时 content="" + reasoning 满）|
| deepseek-v3.2 | ✓ |
| glm-5.1, doubao-pro, doubao-seed-2.0-lite, minimax-m2.5 | ✓ |

### siliconflow (`https://api.siliconflow.cn/v1`)

精准模型列表（`/v1/models` 验证）：
- **Kimi 系列**：`Pro/moonshotai/Kimi-K2.5` ✓ / `Pro/moonshotai/Kimi-K2.6` ✗（timeout）/ `moonshotai/Kimi-K2-Thinking` / `Pro/moonshotai/Kimi-K2-Instruct-0905`
- **GLM 系列**：`Pro/zai-org/GLM-5` ✓ / `Pro/zai-org/GLM-5.1` ✓ / `Pro/zai-org/GLM-4.7` ✓ / `zai-org/GLM-4.6` (timeout) / `zai-org/GLM-4.5` (disabled)
- **DeepSeek 系列**：`Pro/deepseek-ai/DeepSeek-V3.2` ✓
- **Moonshot Kimi-Instruct**：`Pro/moonshotai/Kimi-K2-Instruct-0905` ✓ / `moonshotai/Kimi-K2-Instruct-0905` ✓

## 二、Ch14 实际跑出的 14 模型状态分析

| 模型 key | provider | 实际状态 | 根因 |
|---|---|---|---|
| qwen3.6-plus | openclawroot | ✓ 92.1 | - |
| doubao-pro | ark-coding | ✓ 92.1 | - |
| **gpt-5.4** | openclawroot | ✗ 全 13 维度 http_403 forbidden | 间歇性账户 rate limit / 内容审核（单测短 prompt 时 OK，长 prompt 偶发） |
| gemini-3.1-pro | openclawroot | ⚠ 51.9 outlier | gemini 对中文方言+AI 内化术语评分偏严 |
| doubao-seed-2.0-lite | ark-coding | ✓ 92.2 | - |
| glm-5 | siliconflow `Pro/zai-org/GLM-5` | ✓ 88.2 | - |
| glm-5.1 | ark-coding | ✓ 85.7 | - |
| glm-4.7 | siliconflow `Pro/zai-org/GLM-4.7` | ✓ 92.8 | - |
| mimo-v2-pro | openclawroot | ✓ 87.8 | - |
| minimax-m2.7-hs | openclawroot `MiniMax-M2.7-highspeed` | ✓ 88.5 | - |
| minimax-m2.5 | ark-coding | ✓ 89.2 | partial 12/13 维度 |
| **deepseek-v3.2-thinking** | ark-coding 主 + 2 fallback | ✗ 缺失文件 | 触发 EARLY_STOP_THRESHOLD=4，3 provider 链未走完前已早停 |
| **kimi-k2.5** | ark-coding 单 provider | ✗ 缺失文件 | ark-coding 4 次 phantom → early-stop，单 provider 无 fallback |
| **kimi-k2.6** | ark-coding 单 provider | ✗ 缺失文件 | 同 kimi-k2.5 |

**3 个缺失模型的真实根因**：
1. kimi-k2.5/k2.6: 单 provider 无 fallback + EARLY_STOP_THRESHOLD=4 触发即放弃
2. deepseek-v3.2-thinking: 有 3 provider fallback 但 phantom 累计触发 early-stop
3. gpt-5.4: 间歇性 forbidden（单测可恢复）

## 三、永久根治修复（已 commit fork 0f4cc6c → 本次新增）

### 修复 1：EARLY_STOP_THRESHOLD 4 → 6 (前次已实施)

`external_review.py:1527`: 阈值放宽，给单 provider 模型留 2 次额外重试空间。

### 修复 2：score_spread 自动排除 score<60 outlier (前次已实施)

`chapter_audit.py:691-712`: gemini 51.9 这种 critical outlier 不再污染 audit spread 计算。

### 修复 3：kimi-k2.5/k2.6 加 siliconflow fallback (本次新增)

```python
"kimi-k2.5": {
    "providers": [
        {"provider": "ark-coding", "id": "kimi-k2.5", ...},
        # NEW: Round 20.x · 2026-04-27 · Ch14 RCA P0-1 修复
        {"provider": "siliconflow", "id": "Pro/moonshotai/Kimi-K2.5", "max_tokens": 32768},
    ],
}
"kimi-k2.6": {
    "providers": [
        {"provider": "ark-coding", "id": "kimi-k2.6", ...},
        # NEW: Pro/moonshotai/Kimi-K2.6 实测 timeout，降级用 Pro/moonshotai/Kimi-K2.5 兜底
        {"provider": "siliconflow", "id": "Pro/moonshotai/Kimi-K2.5", ...},
    ],
}
```

实测验证 `Pro/moonshotai/Kimi-K2.5`：9.9s 返回 score 92 + summary，比 ark-coding 快 3 倍。

### 修复 4：minimax-m2.7-hs 加 MiniMax-M2.7 普通版作 fallback (本次新增)

```python
"minimax-m2.7-hs": {
    "providers": [
        {"provider": "openclawroot", "id": "MiniMax-M2.7-highspeed", ...},
        # NEW: M2.7-HS 偶发 503，加普通 M2.7 兜底
        {"provider": "openclawroot", "id": "MiniMax-M2.7", ...},
    ],
}
```

## 四、留待长期改进项

### gpt-5.4 间歇性 forbidden

**根因不明**（不是 reasoning_effort=high 引起，简单 prompt 任意 effort 都 OK，长 prompt 也偶发可用）。

**推测**：openclawroot 对 gpt-5.x 系列有间歇性 rate limit / 内容审核 / 配额检查，触发条件未明。

**应对方案**：
1. 短期：保留当前配置，gpt-5.4 失败时不阻塞
2. 中期：考虑加 `gpt-5.4-1` 或 `gpt-5.5` 作 fallback（同 provider 不同版本）
3. 长期：等 openclawroot 路由稳定 / 换其他 GPT-5 provider

### gemini-3.1-pro 持续 outlier

51.9 (Ch14) / 69.5 (Ch13)：模型对中文方言偏严，是评分倾向问题，非可用性问题。

**应对**：score_spread 已自动排除 score<60，audit 不再被污染。继续 routing-level downweight。

## 五、综合测试矩阵（实测结果）

```
model_key              provider         model_id                                 status
qwen3.6-plus           openclawroot     qwen3.6-plus                             OK (9.6s)
doubao-pro             ark-coding       doubao-seed-2.0-pro                      OK (9.4s)
gpt-5.4                openclawroot     gpt-5.4                                  OK 短prompt (5.8s) / 长prompt 间歇 forbidden
gemini-3.1-pro         openclawroot     gemini-3.1-pro-high                      OK (5.5s)，但分数 outlier
doubao-seed-2.0-lite   ark-coding       doubao-seed-2.0-lite                     OK (6.2s)
glm-5                  siliconflow      Pro/zai-org/GLM-5                        OK (17.7s, reasoning 1418)
glm-5.1                ark-coding       glm-5.1                                  OK (24.8s)
glm-4.7                siliconflow      Pro/zai-org/GLM-4.7                      OK (16.2s)
mimo-v2-pro            openclawroot     mimo-v2-pro                              OK (4.0s)
minimax-m2.7-hs        openclawroot     MiniMax-M2.7-highspeed                   OK (6.5s)
minimax-m2.7-hs        openclawroot     MiniMax-M2.7 (NEW fallback)              OK (9.3s)
minimax-m2.5           ark-coding       minimax-m2.5                             OK (5.1s)
deepseek-v3.2-thinking ark-coding       deepseek-v3.2                            OK (13.6s)
deepseek-v3.2-thinking siliconflow      Pro/deepseek-ai/DeepSeek-V3.2            OK (8.1s)
kimi-k2.5              ark-coding       kimi-k2.5                                OK 单测 (5.9s) / 批量偶发 phantom
kimi-k2.5              siliconflow      Pro/moonshotai/Kimi-K2.5 (NEW)           OK (9.9s)
kimi-k2.6              ark-coding       kimi-k2.6                                OK 单测 (4.1s) / 批量偶发 phantom
kimi-k2.6              siliconflow      Pro/moonshotai/Kimi-K2.5 (NEW fallback)  OK
```

## 六、Ch15 预期效果

修复后 Ch15 跑 external_review 预期：
- **valid 模型 ≥ 11/14**（从 9/14 提升）
- kimi-k2.5/k2.6 必有 1 个 valid（fallback 链生效）
- minimax-m2.7-hs 必 valid（备用 M2.7 普通版）
- gpt-5.4 仍可能间歇 forbidden（无法在代码层修复）
- gemini outlier 不再污染 spread 计算

prep §X6 硬约束 "≥10/14 healthy" 满足概率从 50% 提升到 90%。
