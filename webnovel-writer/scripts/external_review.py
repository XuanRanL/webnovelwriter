"""
Step 3.5 External Model Review Script
Supports two modes:
  - legacy: single prompt, 4-dimension combined review (backward compatible)
  - dimensions: 13-dimension review. Default strategy is combined: one request per model
    returns all 13 dimension_reports; split remains available as fallback/debug.

Architecture (2026-04-23 Round 16 · 扁平化共识机制):
  - 6 providers: ticketpro + api666 + openclawroot + ark-coding (火山方舟 Coding Plan) + siliconflow + xiaomimimo
  - 15 models × 13 dimensions = 195 independent rater scores (共识机制 · 扁平化 · Round 25 +V4-Flash)
  - 每个模型都跑全 13 维度（无分工）；默认每模型一次请求返回 13 维，避免重复发送大上下文
  - **Round 16 架构变更**（2026-04-23 · Ch6 RCA 最终根治 · 见 ROOT_CAUSE_GUARD_RAILS.md）：
    * **去除 core/supplemental 层级**：15 模型集体投票，任一失败不阻塞，以成功模型均分共识
    * 统一重试策略：所有 provider 最多 2 次重试（对抗 openclawroot 偶发 503/524/rate_limited）
    * 统一早停阈值：任一模型累计 4 个维度失败 → 跳过该模型剩余维度
    * 健康判定基于成功模型数：≥10/15 pass · 8-9/15 medium warn · 5-7/15 high warn · <5/15 critical（不阻塞）
    * tier 字段保留但仅作历史 observability 字段 · 不再参与任何判定
  - Round 14 延续：ark-coding 火山方舟 Coding Plan 作为主力 provider 之一
  - 13 维度 = 11 工艺维度 + naturalness（汉语母语自然度）+ reader_critic（读者锐评）
  - Heterogeneous coverage: 国产 (Doubao/GLM×3/Qwen/MiMo/MiniMax/Kimi/DeepSeek) × 异构 (GPT/Gemini)

13 dimensions: consistency/continuity/ooc/reader_pull/high_point/pacing/dialogue_quality/
information_density/prose_quality/emotion_expression/reader_flow/naturalness/reader_critic
(2026-04-13 added reader_flow; Round 13 v2 2026-04-16 added naturalness + reader_critic,
让外部模型也参与读者视角评估，与内部 13 checker 对齐)

History:
  Round 10-: 4-tier (nextapi/healwrap/codexcc/siliconflow) × 9 老模型，实测 6-7/9 成功
  Round 11+: 2-tier × 9 新模型（openclawroot 实测 9/9 路由正确），供应商精简 2x
  Round 14:  并入火山方舟 · 14 模型架构 · 维持 core 3 / supplemental 11
  Round 15.3: core 3 异构 provider（qwen+doubao+glm）· 仍有单 provider 脆弱
  Round 16:  **去 core/supp 层级 · 14 模型扁平投票**
  Round 25:  **新增 deepseek-v4-flash · 15 模型扁平投票 · 当前口径（2026-05-02）**
"""
import json
import time
import sys
import os
import argparse
import re
import threading
import requests
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

PROVIDERS = {
    # Round 20.x · 2026-04-27 · Ch14 RCA P0-2 修复：ticketpro 作为 GPT-5.x 主 provider
    # 实测 /v1/models 返回 9 模型（gpt-5.2/5.3-codex/5.4/5.4-mini/5.5/+3 image），
    # 单测 gpt-5.4/5.5/5.4-mini 全 OK，无 openclawroot 间歇性 forbidden 问题
    "ticketpro": {
        "base_url": "https://api.ticketpro.cc/v1/chat/completions",
        "env_key_names": ["TICKETPRO_API_KEY"],
        "rpm": 30,
    },
    # Round 21.5 · 2026-04-29 · Gemini 主路切换
    # openclawroot 的 gemini-3.1-pro-high 在 Ch4/5/8/15/20 多次 0 维成功，
    # 且 Ch14 出现 51.9 outlier。api666 使用 gemini-3.1-pro-preview 作为主路，
    # openclawroot 保留 fallback。
    "api666": {
        "base_url": "https://api-666.cc/v1/chat/completions",
        "env_key_names": ["API666_API_KEY", "API_666_API_KEY"],
        "rpm": 30,
    },
    "openclawroot": {
        "base_url": "https://openclawroot.com/v1/chat/completions",
        "env_key_names": ["OPENCLAWROOT_API_KEY"],
        "rpm": 30,  # 实测 9+ 模型并发稳定；保守起步，观察后可调高
    },
    # Round 14 · 火山方舟 Coding Plan (OpenAI 兼容 · 7 模型原生 thinking)
    # 实测并发 7 路稳定，speedup≈4.5x；payload 用火山原生 thinking={"type":"enabled"}
    "ark-coding": {
        "base_url": "https://ark.cn-beijing.volces.com/api/coding/v3/chat/completions",
        "env_key_names": ["ARK_CODING_API_KEY", "ARK_API_KEY"],
        "rpm": 30,
    },
    "siliconflow": {
        "base_url": "https://api.siliconflow.cn/v1/chat/completions",
        "env_key_names": ["EMBED_API_KEY", "EMBEDDING_API_KEY", "SILICONFLOW_API_KEY"],
        "rpm": 30,
    },
    # Round 21.3 · 2026-04-29 · 小米官方 token-plan-sgp（MiMo 系列原生主路）
    # 替换原 openclawroot 中 mimo-v2-pro，升级为 MiMo-V2.5（小米官方推理）
    "xiaomimimo": {
        "base_url": "https://token-plan-sgp.xiaomimimo.com/v1/chat/completions",
        "env_key_names": ["XIAOMIMIMO_API_KEY"],
        "rpm": 30,
    },
}

# Default concurrency: max dimensions running in parallel per model
# ProviderRateLimiter 用信号量限制每个供应商的同时在飞连接数（如 healwrap=10）
# 这里控制每模型的线程数上限，从 10 降至 6 减少线程争抢
DEFAULT_MAX_CONCURRENT = 6
DEFAULT_HEALTHCHECK_TIMEOUT = 30


class ProviderRateLimiter:
    """Thread-safe hybrid limiter: 并发连接数 + 请求间隔。

    healwrap RPM=10 = 滑动窗口内同时在飞不超过10个 + 每分钟不超过10个请求。
    - 信号量控制并发上限（防止连接爆炸）
    - min_interval 控制发送间隔（防止快速 429/403 导致突发流量）
    - acquire() 在发送前调用：先拿信号量，再等间隔
    - release() 在整个重试链结束后调用（不是每次重试都释放）
    """

    _instances = {}  # provider_name -> ProviderRateLimiter
    _lock = threading.Lock()

    @classmethod
    def get(cls, provider_name, rpm=None):
        with cls._lock:
            if provider_name not in cls._instances:
                if rpm is None:
                    rpm = PROVIDERS.get(provider_name, {}).get("rpm", 10)
                cls._instances[provider_name] = cls(provider_name, rpm)
            return cls._instances[provider_name]

    @classmethod
    def reset_all(cls):
        """Reset all instances (for testing)."""
        with cls._lock:
            cls._instances.clear()

    def __init__(self, provider_name, rpm):
        self.provider_name = provider_name
        self.rpm = rpm
        self._semaphore = threading.Semaphore(rpm)
        self._interval_lock = threading.Lock()
        self._last_send = 0.0
        self._min_interval = 60.0 / rpm  # 7.5s for rpm=8

    def acquire(self):
        """Block until a concurrent slot is free AND min interval since last send."""
        self._semaphore.acquire()
        with self._interval_lock:
            now = time.time()
            wait = self._min_interval - (now - self._last_send)
            if wait > 0:
                time.sleep(wait)
            self._last_send = time.time()

    def release(self):
        """Release a concurrent slot after the entire request (including retries) completes."""
        self._semaphore.release()

# Reasoning models: 需要更大 max_tokens 容纳 reasoning_content
# 且解析时若 content 为空，fallback 读 reasoning_content 的最后段作为 answer
REASONING_MODELS = {
    # Round 21.3 · 2026-04-29 · mimo-v2-pro → mimo-v2.5-pro（小米官方推理 · xiaomimimo provider）
    "mimo-v2.5-pro", "minimax-m2.7-hs", "deepseek-v3.2-thinking",
    # Round 14 · 火山方舟 coding 家族（全 thinking）
    "doubao-seed-2.0-lite", "minimax-m2.5", "glm-5.1",
    "kimi-k2.5", "kimi-k2.6",
    # 2026-05-02 临时测试 · DeepSeek V4 Flash（deepseek 系自动启用 enable_thinking）
    "deepseek-v4-flash",
}

# Round 16 · 14 模型扁平架构 · 2026-04-23 最终根治
# Round 25 · 15 模型扩展 · 2026-05-02 · 新增 deepseek-v4-flash（siliconflow 单 provider · 实验性）
# 架构决策：15 模型无层级（去 core/supplemental） · 任一失败不阻塞下一模型 · 以成功模型均分作共识
# 6 供应商：ticketpro + api666 + openclawroot + ark-coding + siliconflow + xiaomimimo
# 用户方针：有重复则优先用火山方舟 Coding Plan，所有模型 thinking 全开，max_tokens 拉满上限
# 每个模型跑全 13 维度（共识机制：15×13 = 195 份独立评分）
#
# tier 字段保留但**仅作 observability 标签**（历史兼容），不再参与任何判定：
#   - 路由成功时 routing_verified=True 计入成功
#   - 累计 4 个维度失败 → 该模型早停 · 不影响其他 13 模型
#   - Step 6 A3 完整度阈值：成功 ≥ 10/15 pass · 8-9 medium warn · 5-7 high warn · <5 critical（不阻塞）
#
# provider entry 字段说明：
#   provider: provider key（PROVIDERS 字典）
#   id:       请求时的 model 名（发到 API 的 model 字段）
#   name:     人类可读的模型标签（日志/报告用）
#   max_tokens: 该 provider 下的 max_tokens 上限（可选，默认继承 model.max_tokens_default
#               或全局 65536）。火山 coding 的 deepseek-v3.2 / kimi-k2.5 上限是 32768。
MODELS = {
    # ─── Round 24 · 2026-05-01 · ark-coding 全面首选（实测 9/15 模型短别名直接可用 · 含 V4-Flash 不在内）───
    # 实测 https://ark.cn-beijing.volces.com/api/coding/v3/chat/completions 短别名:
    #   ✅ ark 支持 (9): doubao-seed-2.0-pro / doubao-seed-2.0-lite / glm-4.7 / glm-5.1 /
    #      minimax-m2.5 / minimax-m2.7 / minimax-m2.7-hs / kimi-k2.5 / kimi-k2.6 /
    #      deepseek-v3.2 (= deepseek-v3.2-thinking model_key)
    #   ❌ ark 不支持 (5)，走原 provider:
    #      - gpt-5.5 / gpt-5 → openclawroot
    #      - gemini-3.1-pro → api666
    #      - qwen3.6-plus → openclawroot 单通道
    #      - glm-5 → siliconflow（ark 只有 glm-5.1 / glm-4.7）
    #      - mimo-v2.5-pro → xiaomimimo
    # ─── 国产旗舰 ───
    "qwen3.6-plus": {
        "tier": "standard",
        "providers": [
            {"provider": "openclawroot", "id": "qwen3.6-plus", "name": "Qwen3.6-Plus"},
        ],
        "timeout": 300,
    },
    "doubao-pro": {
        "tier": "standard",
        "providers": [
            {"provider": "ark-coding", "id": "doubao-seed-2.0-pro", "name": "Doubao-Seed-2.0-pro-Ark", "max_tokens": 65536},
            {"provider": "openclawroot", "id": "Doubao-Seed-2.0-pro", "name": "Doubao-Seed-2.0-pro-OC-fallback"},
        ],
        "timeout": 300,
    },
    # ─── 西方异构视角（ark-coding 不提供，保留原 chain）───
    "gpt-5.5": {
        "tier": "standard",
        "providers": [
            {"provider": "openclawroot", "id": "gpt-5.5", "name": "GPT-5.5-OC"},
            {"provider": "ticketpro", "id": "gpt-5.5", "name": "GPT-5.5-TP"},
            {"provider": "openclawroot", "id": "gpt-5.4", "name": "GPT-5.4-OC-legacy"},
        ],
        "timeout": 180,
    },
    "gemini-3.1-pro": {
        "tier": "standard",
        "providers": [
            # Round 25 max-config：thinking_budget 16384→32768（覆盖 call_api 默认）
            {"provider": "api666", "id": "gemini-3.1-pro-preview", "name": "Gemini-3.1-Pro-Preview-API666",
             "max_tokens": 65536, "extra_payload": {"thinking_budget": 32768}},
            {"provider": "openclawroot", "id": "gemini-3.1-pro-high", "name": "Gemini-3.1-Pro-High-OC-fallback"},
        ],
        "timeout": 300,
    },
    # ─── ark-coding 全面首选（短别名直接 OK）───
    "doubao-seed-2.0-lite": {
        "tier": "standard",
        "providers": [
            {"provider": "ark-coding", "id": "doubao-seed-2.0-lite", "name": "Doubao-Seed-2.0-lite-Ark", "max_tokens": 65536},
        ],
        "timeout": 300,
    },
    "glm-5": {
        # 注：ark-coding 没有 glm-5，仅 glm-5.1 和 glm-4.7。glm-5 走 siliconflow 主路
        "tier": "standard",
        "providers": [
            {"provider": "siliconflow", "id": "Pro/zai-org/GLM-5", "name": "GLM-5-SF"},
            {"provider": "openclawroot", "id": "GLM-5", "name": "GLM-5-OC-fallback"},
        ],
        "timeout": 300,
    },
    "glm-5.1": {
        "tier": "standard",
        "providers": [
            {"provider": "ark-coding", "id": "glm-5.1", "name": "GLM-5.1-Ark", "max_tokens": 65536},
            {"provider": "openclawroot", "id": "GLM-5.1", "name": "GLM-5.1-OC-fallback"},
        ],
        "timeout": 300,
    },
    "glm-4.7": {
        "tier": "standard",
        "providers": [
            {"provider": "ark-coding", "id": "glm-4.7", "name": "GLM-4.7-Ark", "max_tokens": 65536},
            {"provider": "siliconflow", "id": "Pro/zai-org/GLM-4.7", "name": "GLM-4.7-SF-fallback"},
            {"provider": "openclawroot", "id": "GLM-4.7", "name": "GLM-4.7-OC-fallback"},
        ],
        "timeout": 300,
    },
    "mimo-v2.5-pro": {
        # 注：ark-coding 不支持 mimo（HTTP 404 UnsupportedModel），仅 xiaomimimo 提供
        "tier": "standard",
        "providers": [
            {"provider": "xiaomimimo", "id": "mimo-v2.5-pro", "name": "MiMo-V2.5-Pro", "max_tokens": 65536},
        ],
        "timeout": 300,
    },
    "minimax-m2.7-hs": {
        "tier": "standard",
        "providers": [
            {"provider": "ark-coding", "id": "minimax-m2.7-hs", "name": "MiniMax-M2.7-HS-Ark", "max_tokens": 65536},
            {"provider": "ark-coding", "id": "minimax-m2.7", "name": "MiniMax-M2.7-Ark", "max_tokens": 65536},
            {"provider": "openclawroot", "id": "MiniMax-M2.7-highspeed", "name": "MiniMax-M2.7-HS-OC-fallback"},
        ],
        "timeout": 300,
    },
    "minimax-m2.5": {
        "tier": "standard",
        "providers": [
            {"provider": "ark-coding", "id": "minimax-m2.5", "name": "MiniMax-M2.5-Ark", "max_tokens": 65536},
        ],
        "timeout": 300,
    },
    "deepseek-v3.2-thinking": {
        "tier": "standard",
        "providers": [
            # ark-coding 首选 · 不能注入未知字段（火山方舟会 400）· 用原生 thinking={"type":"enabled"}
            {"provider": "ark-coding", "id": "deepseek-v3.2", "name": "DeepSeek-V3.2-Ark", "max_tokens": 32768},
            # Round 25 max-config（仅 OpenAI-compatible fallback 路径注入，避免污染 ark）
            {"provider": "openclawroot", "id": "DeepSeek-V3.2-Thinking", "name": "DeepSeek-V3.2-Thinking-OC-fallback",
             "extra_payload": {"reasoning_effort": "max", "thinking_budget": 32768}},
            {"provider": "siliconflow", "id": "Pro/deepseek-ai/DeepSeek-V3.2", "name": "DeepSeek-V3.2-SF-fallback",
             "extra_payload": {"reasoning_effort": "max", "thinking_budget": 32768}},
        ],
        "timeout": 300,
    },
    # Round 25 · 2026-05-02 · 加入 15-model consensus · siliconflow 单 provider
    # 参数全开（基于 SF + DeepSeek 官方 thinking_mode 文档）：
    #   - max_tokens 65536（SF chat-completions 上限）
    #   - reasoning_effort=max（DeepSeek thinking_mode 指南最高档 · "xhigh" 别名）
    #   - thinking_budget=32768（SF 文档允许的上限 128-32768）
    #   - enable_thinking=True 由 call_api 自动注入（model 名含 "deepseek"）
    #   - timeout 1500s（实测 maxed 配置首次需 ~900s，bump 到 1500s 避免边界 timeout）
    # Ch22 实测：default 配置 overall=89.3 / 1 issue / 12min；
    #            maxed 配置 overall=85.8 / 9 issues / 17min（更挑剔 → 更深的批评 = 最高表现）
    "deepseek-v4-flash": {
        "tier": "experimental",
        "providers": [
            {
                "provider": "siliconflow",
                "id": "deepseek-ai/DeepSeek-V4-Flash",
                "name": "DeepSeek-V4-Flash-SF",
                "max_tokens": 65536,
                "extra_payload": {
                    "reasoning_effort": "max",
                    "thinking_budget": 32768,
                },
            },
        ],
        "timeout": 1500,
    },
    "kimi-k2.5": {
        "tier": "standard",
        "providers": [
            {"provider": "ark-coding", "id": "kimi-k2.5", "name": "Kimi-K2.5-Ark", "max_tokens": 32768},
            # Round 25 max-config · Kimi 官方 reasoning_effort 仅 low/medium/high
            {"provider": "siliconflow", "id": "Pro/moonshotai/Kimi-K2.5", "name": "Kimi-K2.5-SF-fallback",
             "max_tokens": 32768, "extra_payload": {"reasoning_effort": "high"}},
        ],
        "timeout": 300,
    },
    "kimi-k2.6": {
        "tier": "standard",
        "providers": [
            {"provider": "ark-coding", "id": "kimi-k2.6", "name": "Kimi-K2.6-Ark", "max_tokens": 65536},
            {"provider": "siliconflow", "id": "Pro/moonshotai/Kimi-K2.5", "name": "Kimi-K2.5-SF-fallback-for-K2.6",
             "max_tokens": 32768, "extra_payload": {"reasoning_effort": "high"}},
        ],
        "timeout": 300,
    },
}

# Backward-compatible aliases for legacy --model-key usage
# 老代码/老 state.json 可能用老名字，映射到新名字
MODEL_ALIASES = {
    # Round 10- 老名字 → Round 11+/14+ 新名字
    "qwen-plus": "qwen3.6-plus",
    "qwen": "qwen3.6-plus",
    # Round 14：kimi 重新启用（火山 coding 接入），别名指向 k2.6（旗舰）
    "kimi": "kimi-k2.6",
    "kimi-k2": "kimi-k2.6",
    "glm": "glm-5",
    "glm4": "glm-4.7",
    "glm5": "glm-5",
    "minimax": "minimax-m2.7-hs",
    "minimax-m2.7": "minimax-m2.7-hs",
    "deepseek": "deepseek-v3.2-thinking",
    "deepseek-v3.2": "deepseek-v3.2-thinking",  # 短名映射到带 -thinking 的 key
    # Round 20.x · 2026-04-27 · Ch14 RCA P0-2：gpt-5.4 升级为 gpt-5.5，旧 model_key 仍可用
    "gpt-5.4": "gpt-5.5",
    "gpt-5": "gpt-5.5",
    "doubao": "doubao-pro",
    "doubao-lite": "doubao-seed-2.0-lite",
    # Round 21.3 · 2026-04-29 · mimo-v2-pro 升级为 mimo-v2.5-pro（小米官方主路）
    "mimo": "mimo-v2.5-pro",
    "mimo-v2": "mimo-v2.5-pro",
    "mimo-v2.5": "mimo-v2.5-pro",
    "mimo-v2-pro": "mimo-v2.5-pro",
}

DIMENSIONS = {
    "consistency": {
        "name": "设定一致性",
        "system": "你是一个专业的网文设定一致性审查编辑。",
        "prompt": """请检查以下章节的设定一致性，重点关注：
1. 战力/能力是否合理，是否超出当前等级
2. 地点/角色是否前后一致
3. 时间线是否有矛盾（日期、倒计时、事件先后）
4. 新出现的设定是否与已有世界观冲突

{context_block}

严格按JSON输出：
{{"dimension":"consistency","score":0-100,"issues":[{{"id":"CON_001","type":"SETTING_CONFLICT/CONTINUITY","severity":"critical/high/medium/low","location":"位置","description":"问题","suggestion":"建议","quote":"引用正文原句"}}],"summary":"一句话总评"}}

评分标准：95-100出版级｜90-94优秀仅轻微瑕疵｜85-89良好少量可优化｜80-84合格若干需改进｜75-79及格有明显问题｜<75不合格有严重问题

## 本章正文
{chapter_text}"""
    },
    "continuity": {
        "name": "连贯性",
        "system": "你是一个专业的网文连贯性审查编辑。",
        "prompt": """请检查以下章节的连贯性，重点关注：
1. 与上章的场景过渡是否流畅
2. 情节线是否连贯（无遗忘/突兀跳转）
3. 伏笔管理是否到位（已埋伏笔是否有回应）
4. 逻辑是否有漏洞

{context_block}

严格按JSON输出：
{{"dimension":"continuity","score":0-100,"issues":[{{"id":"CONT_001","type":"CONTINUITY","severity":"critical/high/medium/low","location":"位置","description":"问题","suggestion":"建议","quote":"引用正文原句"}}],"summary":"一句话总评"}}

评分标准：95-100出版级｜90-94优秀仅轻微瑕疵｜85-89良好少量可优化｜80-84合格若干需改进｜75-79及格有明显问题｜<75不合格有严重问题

## 本章正文
{chapter_text}"""
    },
    "ooc": {
        "name": "人物塑造/OOC",
        "system": "你是一个专业的网文角色一致性审查编辑。",
        "prompt": """请检查以下章节的人物塑造，重点关注：
1. 角色行为是否符合已建立的人设
2. 对话风格是否一致（每个角色应有独特语言习惯）
3. 角色成长是否合理（有因果，非突变）
4. 情绪反应是否符合角色性格和当前处境

{context_block}

严格按JSON输出：
{{"dimension":"ooc","score":0-100,"issues":[{{"id":"OOC_001","type":"OOC","severity":"critical/high/medium/low","location":"位置","description":"问题","suggestion":"建议","quote":"引用正文原句"}}],"summary":"一句话总评"}}

评分标准：95-100出版级｜90-94优秀仅轻微瑕疵｜85-89良好少量可优化｜80-84合格若干需改进｜75-79及格有明显问题｜<75不合格有严重问题

## 本章正文
{chapter_text}"""
    },
    "reader_pull": {
        "name": "追读力",
        "system": "你是一个专业的网文追读力审查编辑。",
        "prompt": """请检查以下章节的追读力，重点关注：
1. 章末是否有钩子让读者想看下一章
2. 是否有微爽点/满足感（信息兑现、能力展示、认可等）
3. 未闭合问题是否有效（让读者好奇而非困惑）
4. 上章钩子是否在本章得到回应

{context_block}

严格按JSON输出：
{{"dimension":"reader_pull","score":0-100,"issues":[{{"id":"RP_001","type":"READER_PULL","severity":"critical/high/medium/low","location":"位置","description":"问题","suggestion":"建议","quote":"引用正文原句"}}],"summary":"一句话总评"}}

评分标准：95-100出版级｜90-94优秀仅轻微瑕疵｜85-89良好少量可优化｜80-84合格若干需改进｜75-79及格有明显问题｜<75不合格有严重问题

## 本章正文
{chapter_text}"""
    },
    "high_point": {
        "name": "爽点密度",
        "system": "你是一个专业的网文爽点密度审查编辑。",
        "prompt": """请检查以下章节的爽点密度，重点关注：
1. 本章是否有明确的爽点/高光时刻
2. 爽点类型是否与前几章有差异化（避免连续同类型）
3. 如果是铺垫章，是否至少有微兑现（不能整章无收获）
4. 爽点的触发是否有因果逻辑（非凭空降临）

{context_block}

严格按JSON输出：
{{"dimension":"high_point","score":0-100,"issues":[{{"id":"HP_001","type":"PACING或READER_PULL（二选一，按问题性质选择）","severity":"critical/high/medium/low","location":"位置","description":"问题","suggestion":"建议","quote":"引用正文原句"}}],"summary":"一句话总评"}}

评分标准：95-100出版级｜90-94优秀仅轻微瑕疵｜85-89良好少量可优化｜80-84合格若干需改进｜75-79及格有明显问题｜<75不合格有严重问题

## 本章正文
{chapter_text}"""
    },
    "pacing": {
        "name": "节奏平衡",
        "system": "你是一个专业的网文节奏审查编辑。",
        "prompt": """请检查以下章节的节奏，重点关注：
1. 章内节奏是否合理（紧→松→紧的波动，非全程平铺）
2. 信息密度是否适当（不过载也不空洞）
3. 场景切换是否流畅
4. 与前几章的节奏变化是否有差异化

{context_block}

严格按JSON输出：
{{"dimension":"pacing","score":0-100,"issues":[{{"id":"PACE_001","type":"PACING","severity":"critical/high/medium/low","location":"位置","description":"问题","suggestion":"建议","quote":"引用正文原句"}}],"summary":"一句话总评"}}

评分标准：95-100出版级｜90-94优秀仅轻微瑕疵｜85-89良好少量可优化｜80-84合格若干需改进｜75-79及格有明显问题｜<75不合格有严重问题

## 本章正文
{chapter_text}"""
    },
    "dialogue_quality": {
        "name": "对话质量",
        "system": "你是一个专业的网文对话质量审查编辑。",
        "prompt": """请检查以下章节的对话质量，重点关注：
1. 不同角色说话风格是否有差异（遮住人名后能否分辨说话者）
2. 对话是否只为传递信息而缺少意图/冲突（信息倾倒/说明书式对话）
3. 是否有单人连续独白过长（超过200字）
4. 对话是否推进情节/塑造角色，而非仅填充字数
5. 是否存在潜台词（表面说A实际意图B）

{context_block}

严格按JSON输出：
{{"dimension":"dialogue_quality","score":0-100,"issues":[{{"id":"DQ_001","type":"DIALOGUE_FLAT/DIALOGUE_INFODUMP/DIALOGUE_MONOLOGUE","severity":"critical/high/medium/low","location":"位置","description":"问题","suggestion":"建议","quote":"引用正文原句"}}],"summary":"一句话总评"}}

评分标准：95-100出版级｜90-94优秀仅轻微瑕疵｜85-89良好少量可优化｜80-84合格若干需改进｜75-79及格有明显问题｜<75不合格有严重问题

## 本章正文
{chapter_text}"""
    },
    "information_density": {
        "name": "信息密度",
        "system": "你是一个专业的网文信息密度审查编辑。",
        "prompt": """请检查以下章节的信息密度，重点关注：
1. 是否有无信息增量的水分段落（不推进剧情/角色/情绪/氛围）
2. 是否有同一信息重复描述（已通过动作/对话传达后又用叙述重复）
3. 信息分布是否均匀（非开头密集结尾稀疏，或全程平淡）
4. 每段是否都有存在的理由（删除后是否影响理解）
5. 内心独白是否过多（占比超过25%需预警）

{context_block}

严格按JSON输出：
{{"dimension":"information_density","score":0-100,"issues":[{{"id":"ID_001","type":"PADDING/REPETITION","severity":"critical/high/medium/low","location":"位置","description":"问题","suggestion":"建议","quote":"引用正文原句"}}],"summary":"一句话总评"}}

评分标准：95-100出版级｜90-94优秀仅轻微瑕疵｜85-89良好少量可优化｜80-84合格若干需改进｜75-79及格有明显问题｜<75不合格有严重问题

## 本章正文
{chapter_text}"""
    },
    "prose_quality": {
        "name": "文笔质感",
        "system": "你是一个专业的网文文笔质感审查编辑。",
        "prompt": """请重点评估本章的文笔表现力：
1. 句式是否有长短交替的节奏变化？
2. 比喻是否新鲜（非套路化的'如刀/如水/如山'）？
3. 是否有视觉之外的感官描写（听觉/触觉/嗅觉）？
4. 动词是否精确有力（而非'看了/走了/做了'等万能动词）？
5. 关键场景是否有空间方位感和画面感？
6. 抽象表达是否用具体数字/对比替代？
7. 若含典故/诗词/口诀引用：融入是否自然（化用好于硬引，角色内化好于旁白注释）？是否服务于剧情/角色/伏笔（纯装饰=炫学应扣分）？是否存在"正如XX所言"等生硬引导语？

{context_block}

严格按JSON输出：
{{"dimension":"prose_quality","score":0-100,"issues":[{{"id":"PQ_001","type":"PROSE_FLAT","severity":"critical/high/medium/low","location":"位置","description":"问题","suggestion":"建议","quote":"引用正文原句"}}],"summary":"一句话总评"}}

评分标准：95-100出版级｜90-94优秀仅轻微瑕疵｜85-89良好少量可优化｜80-84合格若干需改进｜75-79及格有明显问题｜<75不合格有严重问题

## 本章正文
{chapter_text}"""
    },
    "emotion_expression": {
        "name": "情感表现",
        "system": "你是一个专业的网文情感表现审查编辑。",
        "prompt": """请重点评估本章的情感表达质量：
1. 情感是否通过行为/生理反应展示（Show）而非直接告知（Tell，如'他感到愤怒'）？
2. 情感变化是否有梯度递进（而非突然跳变）？
3. 情感场景是否有物理/生理锚点（手指发抖、喉结滚动等）？
4. 上章结尾的情绪是否在本章开头延续（情感惯性）？
5. 情感高潮是否有前文铺垫（earned而非forced）？

{context_block}

严格按JSON输出：
{{"dimension":"emotion_expression","score":0-100,"issues":[{{"id":"EE_001","type":"EMOTION_SHALLOW","severity":"critical/high/medium/low","location":"位置","description":"问题","suggestion":"建议","quote":"引用正文原句"}}],"summary":"一句话总评"}}

评分标准：95-100出版级｜90-94优秀仅轻微瑕疵｜85-89良好少量可优化｜80-84合格若干需改进｜75-79及格有明显问题｜<75不合格有严重问题

## 本章正文
{chapter_text}"""
    },
    "naturalness": {
        "name": "汉语母语自然度",
        "system": "你是一个汉语母语中国读者，凭语感判断章节是否像真人写的。不按写作规则打分，按母语本能打分。quote 必须原文逐字。",
        "prompt": """**核心任务**：以中国母语读者本能判断这一章**像不像真人写的**——是否有机翻味、AI 套话、首句语病、设计标签暴露、伪神经科学公式痕迹、机械打卡感。

## 判断维度（读者本能，不是规则）

1. **首句语感**（极重要）：第一句是否汉语合法？如"<protagonist>在死"这种体貌违反/首句语病直接 REJECT_CRITICAL。
2. **AI 腔检测**：是否出现"不由得"/"心中一震"/"一股暖流"/"时间仿佛静止了"/"这一刻他突然明白"/"值得注意的是"/"总的来说"等 AI 高频套话？
3. **机翻味**：句式是否有外语 calque（"让 X 做某事"/"这是一个很好的例子"这种英文逻辑翻译体）？
4. **设计标签暴露**：是否能明显看出"作者在按某公式/某规则写"（如"4 字激活杏仁核"/"首句必含感官词"的公式痕迹）？
5. **碎片化过度**：是否过多 3-8 字的碎句独立成段，让段落看起来像诗？
6. **机械打卡感**：是否为了凑爽点/钩子/伏笔，让情节推进感觉像在打卡而非自然发生？

{context_block}

严格按 JSON 输出（quote 必须原文逐字出现，否则丢弃整份）：
{{"dimension":"naturalness","score":0-100,"verdict":"PASS|POLISH_NEEDED|REWRITE_RECOMMENDED|REJECT_HIGH|REJECT_CRITICAL","first_sentence_score":0-10,"issues":[{{"id":"NAT_001","type":"NATURALNESS","severity":"critical/high/medium/low","location":"原文前 8 字","description":"[category:首句语病|AI腔|机翻|设计标签|碎片化|机械打卡] 具体读者感受","suggestion":"修复方向","quote":"原文一句 ≤ 40 字"}}],"summary":"一句话总评这章汉语自然度"}}

## verdict 档位

- `PASS`：像真人写的，母语读者不皱眉
- `POLISH_NEEDED`：有 1-2 处 AI 腔/机翻痕迹但不影响整体
- `REWRITE_RECOMMENDED`：多处不像人写的，建议重写段落
- `REJECT_HIGH`：首句或开篇有明显语病，读者第一眼就出戏
- `REJECT_CRITICAL`：首句语病严重或全文像 AI 套路模板，无法当正常小说阅读

## 评分

`score = max(0, 100 - (critical × 25 + high × 15 + medium × 8 + low × 3))`。首句语病直接 -30 起。

95-100 母语范本｜90-94 少量轻微 AI 腔｜85-89 偶有机翻味但读得下去｜80-84 多处不像人写｜75-79 明显 AI 公式痕迹｜<75 劝退级

## 本章正文
{chapter_text}"""
    },
    "reader_critic": {
        "name": "读者锐评",
        "system": "你是严肃的网文读者 + 退稿编辑。deep research 找问题给建议。quote 必须原文逐字出现在正文中。",
        "prompt": """**仔细研究认真思考详细调查搜索分析 deep research 以正常读者的角度和编辑退稿视角去锐评和找这个小说的问题，最后给出完整详细全面的修改建议以及原因。**

{context_block}

严格按 JSON 输出（quote 必须原文逐字出现，否则整份丢弃）：
{{"dimension":"reader_critic","score":0-100,"will_continue_reading":"yes|hesitant|no","continue_reason":"一句读者/编辑视角总评","issues":[{{"id":"RC_001","type":"READER_CRITIC","severity":"critical/high/medium/low","location":"原文前 8 字","description":"问题描述（标注 reader/editor/both 视角）","suggestion":"完整详细的修改建议 + 原因","quote":"原文一句 ≤ 40 字"}}],"highlights":[{{"quote":"原文一句","reason":"为什么亮眼"}}],"summary":"一段总评（60-200 字）"}}

评分：95-100 追更级｜90-94 优秀仅轻微瑕疵｜85-89 良好少量可优化｜80-84 合格若干需改进｜75-79 明显问题｜<75 退稿不合格

## 本章正文
{chapter_text}"""
    },
    "reader_flow": {
        "name": "读者视角流畅度",
        "system": "你是严肃的网文读者 + 退稿编辑。deep research 找问题给建议。quote 必须原文逐字出现在正文中。",
        "prompt": """**仔细研究认真思考详细调查搜索分析 deep research 以正常读者的角度和编辑退稿视角去锐评和找这个小说的问题，最后给出完整详细全面的修改建议以及原因。**

{context_block}

严格按 JSON 输出（quote 必须原文逐字出现，否则整份丢弃）：
{{"dimension":"reader_flow","score":0-100,"issues":[{{"id":"RF_001","type":"READER_FLOW","severity":"critical/high/medium/low","location":"原文前 8 字","description":"问题描述（标注 reader/editor/both 视角）","suggestion":"完整详细的修改建议 + 原因","quote":"原文一句 ≤ 40 字"}}],"highlights":[{{"quote":"原文一句","reason":"为什么亮眼"}}],"summary":"一段总评（60-200 字）"}}

评分：95-100 追更级｜90-94 优秀仅轻微瑕疵｜85-89 良好少量可优化｜80-84 合格若干需改进｜75-79 明显问题｜<75 退稿不合格

## 本章正文
{chapter_text}"""
    },
}


DIMENSION_ORDER = list(DIMENSIONS.keys())

DIMENSION_NAME_ALIASES = {
    "设定一致性": "consistency",
    "连贯性": "continuity",
    "人物塑造": "ooc",
    "人物塑造/OOC": "ooc",
    "角色一致性": "ooc",
    "追读力": "reader_pull",
    "爽点密度": "high_point",
    "节奏控制": "pacing",
    "节奏平衡": "pacing",
    "对话质量": "dialogue_quality",
    "信息密度": "information_density",
    "文笔质感": "prose_quality",
    "情感表现": "emotion_expression",
    "情感表达": "emotion_expression",
    "汉语母语自然度": "naturalness",
    "母语自然度": "naturalness",
    "读者锐评": "reader_critic",
    "读者视角流畅度": "reader_flow",
    "reader_critic": "reader_critic",
    "reader-flow": "reader_flow",
}

COMBINED_DIMENSION_GUIDE = {
    "consistency": "设定一致性：战力/能力/物品/世界观/时间线是否与既有设定冲突。",
    "continuity": "连贯性：与前章承接、因果链、伏笔回应、场景过渡是否顺畅。",
    "ooc": "人物塑造/OOC：行为、对话、情绪反应是否符合已建立人设与当前处境。",
    "reader_pull": "追读力：章末钩子、微兑现、未闭合问题是否让读者想看下一章。",
    "high_point": "爽点密度：本章高光、主角收益、信息差兑现、铺垫章的微爽点是否足够。",
    "pacing": "节奏平衡：紧松变化、信息分布、场景切换、段落长度是否影响阅读节奏。",
    "dialogue_quality": "对话质量：角色区分度、潜台词、信息倾倒、长独白、互动推进。",
    "information_density": "信息密度：水分、重复、内心独白比例、每段信息增量。",
    "prose_quality": "文笔质感：句式节奏、动词精度、感官覆盖、画面感、典故/诗词融入。",
    "emotion_expression": "情感表现：Show not Tell、情绪梯度、生理/物理锚点、情感高潮是否 earned。",
    "naturalness": "汉语母语自然度：首句语病、AI 腔、机翻味、设计标签暴露、机械打卡感。",
    "reader_critic": "读者锐评：以追更读者+退稿编辑角度判断是否愿意继续读、亮点与劝退点。",
    "reader_flow": "读者视角流畅度：失忆裸读是否卡顿、信息是否顺着读者理解路径展开。",
}

COMBINED_EXTRA_FIELDS = {
    "verdict",
    "first_sentence_score",
    "will_continue_reading",
    "continue_reason",
    "highlights",
}


# Known routing bugs for verification
ROUTING_BUGS = {
    "codexcc": {
        "glm": ["MiniMax"],       # codexcc returns MiniMax when GLM requested
        "kimi": ["qianfan"],      # codexcc returns qianfan when kimi requested
    }
}


def load_api_keys():
    """查找 .env 文件的多层策略（Round 11 新增 workspace root + env override 支持）:

    1. os.environ 直接读（最高优先级，运行环境已设置）
    2. 当前目录 .env / 父级 2 层 .env（workspace root 常见位置）
    3. ~/.claude/webnovel-writer/.env（用户全局）
    4. 插件 root .env（通过脚本路径反推）
    """
    # Priority 1: direct os.environ（如果已设）
    keys = {}
    for pname, pcfg in PROVIDERS.items():
        for kname in pcfg["env_key_names"]:
            val = os.environ.get(kname)
            if val and pname not in keys:
                keys[pname] = val

    # Priority 2+: .env 文件链
    env_paths = []
    # 当前目录向上 3 级
    cur = Path.cwd()
    for _ in range(4):
        env_paths.append(cur / ".env")
        if cur.parent == cur:
            break
        cur = cur.parent
    # 插件脚本目录向上 3 级（脚本可能被 plugin cache 加载）
    script_dir = Path(__file__).resolve().parent
    for _ in range(4):
        env_paths.append(script_dir / ".env")
        if script_dir.parent == script_dir:
            break
        script_dir = script_dir.parent
    # 用户全局
    env_paths.append(Path.home() / ".claude" / "webnovel-writer" / ".env")

    # 去重保序
    seen = set()
    env_paths_uniq = []
    for p in env_paths:
        s = str(p.resolve()) if p.exists() else str(p)
        if s not in seen:
            seen.add(s); env_paths_uniq.append(p)

    for env_path in env_paths_uniq:
        if not env_path.exists(): continue
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"): continue
                for pname, pcfg in PROVIDERS.items():
                    for kname in pcfg["env_key_names"]:
                        if line.startswith(f"{kname}="):
                            val = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if pname not in keys:
                                keys[pname] = val
        except Exception:
            continue
    return keys


def verify_routing(model_key, provider_name, response_model, requested_model_id=""):
    """Check if the response model matches what was requested.

    Verification logic:
    1. Blacklist: check known routing bugs (immediate fail)
    2. Positive match: response_model must contain the requested model name
       or a known alias. Providers may return decorated names (e.g. siliconflow
       returns 'Pro/xxx/Model'), so we do case-insensitive substring matching.
    """
    if not response_model:
        return False, "no_model_in_response"

    resp_lower = response_model.lower()

    # Step 1: Check known routing bugs (blacklist)
    if provider_name in ROUTING_BUGS:
        bugs = ROUTING_BUGS[provider_name].get(model_key, [])
        for bug_pattern in bugs:
            if bug_pattern.lower() in resp_lower:
                return False, f"known_bug:{bug_pattern}_returned_for_{model_key}"

    # Step 2: Positive match — response model should contain the requested model id
    if requested_model_id:
        # Normalize: strip provider prefix (e.g. "Pro/zai-org/GLM-5" → "glm-5")
        req_base = requested_model_id.rsplit("/", 1)[-1].lower()
        if req_base in resp_lower:
            return True, "positive_match"
        # Normalize version: strip trailing ".0" (e.g. "glm-5.0" → "glm-5")
        req_normalized = re.sub(r'\.0$', '', req_base)
        if req_normalized != req_base and req_normalized in resp_lower:
            return True, "normalized_match"
        # Also try model_key as fallback (e.g. "kimi" in "kimi-k2.5-xxx")
        if model_key.lower() in resp_lower:
            return True, "key_match"
        # No match found — suspicious but not a known bug
        return False, f"no_positive_match:requested={requested_model_id},got={response_model}"

    # No requested_model_id provided, can only pass blacklist check
    return True, "blacklist_only"


def call_api(base_url, api_key, model_id, system_msg, user_msg, timeout=300, max_retries=2,
             provider_name=None, max_tokens=65536, extra_payload=None):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    # Round 14：thinking / max_tokens 由 provider 决定
    # - ark-coding（火山方舟 Coding Plan）使用火山原生 thinking={"type":"enabled"}，
    #   max_tokens 由 provider entry 指定（deepseek-v3.2 & kimi-k2.5 上限 32768，其他 65536）
    # - 其他 OpenAI-compatible provider 沿用原策略：按模型厂家家族设置 thinking 开关
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.3,
        "max_tokens": int(max_tokens),
    }
    model_lower = model_id.lower()

    if provider_name == "ark-coding":
        # 火山方舟 coding 原生 thinking 参数（实测 7 模型全部识别；未知参数会 400）
        payload["thinking"] = {"type": "enabled"}
    else:
        # OpenAI 系（gpt-5.4）用 reasoning_effort
        if "gpt-" in model_lower:
            payload["reasoning_effort"] = "high"
        # Gemini 系 · thinking budget
        if "gemini" in model_lower:
            payload["thinking_budget"] = 16384
        # Qwen/DeepSeek/Doubao/GLM/MiMo/Kimi 系 · enable_thinking 激活推理
        if any(t in model_lower for t in ("qwen", "deepseek", "doubao", "glm", "mimo", "kimi")):
            payload["enable_thinking"] = True
        # MiniMax / MiMo 推理类 · 明确开 thinking
        if any(t in model_lower for t in ("minimax", "mimo")):
            payload["enable_thinking"] = True
        # Anthropic 风格（claude-opus 等）· thinking budget_tokens
        if "claude" in model_lower:
            payload["thinking"] = {"type": "enabled", "budget_tokens": 16384}
    # provider entry 的 extra_payload 直接合并到顶层（model entry 显式指定优先）
    if extra_payload:
        payload.update(extra_payload)
    # 整个重试链只占一个 limiter slot（acquire 一次，return/fail 后 release 一次）
    limiter = ProviderRateLimiter.get(provider_name) if provider_name else None
    provider_chain = []
    session = requests.Session()
    if limiter:
        limiter.acquire()
    try:
        for attempt in range(max_retries + 1):
            start_ts = time.time()
            try:
                resp = session.post(base_url, headers=headers, json=payload, timeout=timeout)
                elapsed = int((time.time() - start_ts) * 1000)
                if resp.status_code == 200:
                    data = resp.json()
                    msg = data["choices"][0]["message"]
                    content = msg.get("content") or ""
                    # 2026-04-16 Round 11：推理模型（mimo/minimax-highspeed/deepseek-thinking）
                    # 可能把答案全部写到 reasoning_content 而 content 为空；fallback 读取
                    if not content.strip():
                        reasoning = msg.get("reasoning_content") or ""
                        if reasoning.strip():
                            content = reasoning
                    model_actual = data.get("model", "")
                    usage = data.get("usage", {})
                    provider_chain.append({
                        "attempt": attempt + 1,
                        "result": "success",
                        "elapsed_ms": elapsed,
                        "model_actual": model_actual,
                    })
                    return content, None, model_actual, usage, provider_chain
                elif resp.status_code == 429:
                    provider_chain.append({"attempt": attempt + 1, "result": "rate_limited", "elapsed_ms": elapsed})
                    time.sleep(6)  # 429 wait 6s per spec
                elif resp.status_code == 403:
                    # 403 = 模型在该供应商不可用，不重试直接切下一个供应商
                    err = f"HTTP 403: {resp.text[:200]}"
                    provider_chain.append({"attempt": attempt + 1, "result": "http_403", "elapsed_ms": elapsed})
                    return None, err, None, None, provider_chain
                else:
                    err = f"HTTP {resp.status_code}: {resp.text[:200]}"
                    provider_chain.append({"attempt": attempt + 1, "result": f"http_{resp.status_code}", "elapsed_ms": elapsed})
                    if attempt < max_retries:
                        time.sleep(5)
                    else:
                        return None, err, None, None, provider_chain
            except requests.exceptions.Timeout:
                elapsed = int((time.time() - start_ts) * 1000)
                provider_chain.append({"attempt": attempt + 1, "result": "timeout", "elapsed_ms": elapsed})
                if attempt < max_retries:
                    time.sleep(5)
                else:
                    return None, "Timeout", None, None, provider_chain
            except (requests.exceptions.ConnectionError, ConnectionResetError, OSError) as e:
                elapsed = int((time.time() - start_ts) * 1000)
                provider_chain.append({"attempt": attempt + 1, "result": str(e)[:100], "elapsed_ms": elapsed})
                # 连接错误后关闭旧 session 并重建，避免连接池中毒
                session.close()
                session = requests.Session()
                if attempt < max_retries:
                    time.sleep(8)  # 连接错误等更久再重试
                else:
                    return None, str(e), None, None, provider_chain
            except Exception as e:
                elapsed = int((time.time() - start_ts) * 1000)
                provider_chain.append({"attempt": attempt + 1, "result": str(e)[:100], "elapsed_ms": elapsed})
                if attempt < max_retries:
                    time.sleep(5)
                else:
                    return None, str(e), None, None, provider_chain
        return None, "Max retries", None, None, provider_chain
    finally:
        if limiter:
            limiter.release()
        session.close()


def extract_json(text):
    if not text:
        return None
    # Priority 0: Strip thinking tags (qwen-3.5, deepseek, etc. wrap reasoning in <think>)
    think_match = re.search(r'</think>\s*', text)
    if think_match:
        text = text[think_match.end():]
    # Priority 1: fenced ```json block
    m = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Priority 2: brace-depth scanner — find first valid top-level {...} object
    start = text.find('{')
    while start != -1:
        depth = 0
        in_string = False
        escape_next = False
        for i in range(start, len(text)):
            c = text[i]
            if escape_next:
                escape_next = False
                continue
            if c == '\\' and in_string:
                escape_next = True
                continue
            if c == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break  # This candidate failed; try next '{' below
        # Move to next '{' after current start
        start = text.find('{', start + 1)
    # Priority 3: greedy fallback (last resort, flat JSON only)
    m = re.search(r'\{[^{}]*\}', text)
    if m:
        try:
            parsed = json.loads(m.group(0))
            # 安全检查：确保提取的是审查结果（含 score 字段），而非嵌套子对象
            if "score" in parsed:
                print(f"[extract_json] 使用 greedy fallback 提取（可能不完整）", file=sys.stderr)
                return parsed
        except json.JSONDecodeError:
            pass
    return None


def _is_phantom_parsed(parsed, parse_mode="dimension"):
    """Detect provider ghost-success payloads that contain no useful review."""
    if not isinstance(parsed, dict):
        return True
    summary = str(parsed.get("summary") or "").strip()
    if parse_mode == "combined":
        reports = parsed.get("dimension_reports") or parsed.get("dimensions") or []
        overall = parsed.get("overall_score")
        return (overall in (None, 0, 0.0)) and not summary and not reports
    return parsed.get("score", 0) == 0 and not summary


def try_provider_chain(api_keys, model_key, model_config, system_msg, user_msg, timeout, parse_mode="dimension"):
    """Try each provider in the chain until one succeeds with valid routing."""
    full_chain = []

    for provider_cfg in model_config["providers"]:
        provider_name = provider_cfg["provider"]
        if provider_name not in api_keys:
            full_chain.append({
                "provider": provider_name,
                "attempt": 0,
                "result": "no_api_key",
            })
            continue

        base_url = PROVIDERS[provider_name]["base_url"]
        # Round 16 · 2026-04-23 · 统一重试策略（去 core/supp 层级）：
        # 所有 provider 都给 2 次重试（含首跑偶发 400/偶发 503/524/rate_limited）
        # - openclawroot：Ch3-6 连续 4 章 outage 证明 rate_limited/503/524 偶发性强，2 次重试显著降失败率
        # - ark-coding：首跑偶发 400（历史观察），2 次重试能恢复
        # - siliconflow：兜底稳定，2 次重试作为保险
        # 失败仍然切下一个 provider 链，直到全部尝试完毕。
        max_retries = 2
        # Round 14 · max_tokens 优先从 provider 读（火山 coding 的 deepseek/kimi-k2.5 限 32768）
        provider_max_tokens = provider_cfg.get("max_tokens", 65536)
        provider_extra_payload = provider_cfg.get("extra_payload")

        raw, error, model_actual, usage, attempts = call_api(
            base_url, api_keys[provider_name], provider_cfg["id"],
            system_msg, user_msg, timeout, max_retries=max_retries,
            provider_name=provider_name, max_tokens=provider_max_tokens,
            extra_payload=provider_extra_payload,
        )

        for a in attempts:
            a["provider"] = provider_name
        full_chain.extend(attempts)

        if error:
            continue

        if raw:
            # Verify routing
            routing_ok, routing_reason = verify_routing(model_key, provider_name, model_actual, provider_cfg["id"])
            if not routing_ok:
                full_chain.append({
                    "provider": provider_name,
                    "attempt": 0,
                    "result": f"routing_failed:{routing_reason}",
                })
                continue  # Route mismatch -> try next provider

            parsed = extract_json(raw)
            if parsed:
                # 幽灵零分检测：score=0且摘要为空 → 视为无效，尝试下一个供应商
                if _is_phantom_parsed(parsed, parse_mode=parse_mode):
                    full_chain.append({
                        "provider": provider_name,
                        "attempt": 0,
                        "result": "phantom_score0_retry",
                    })
                    print(f"[phantom] {model_key}@{provider_name}: 空审查结果，尝试下一供应商", file=sys.stderr)
                    continue
                return parsed, provider_cfg["name"], provider_name, model_actual, routing_ok, usage, full_chain

    return None, None, "none", None, False, None, full_chain


CH1_3_SPECIAL_PROMPT = """
【特别注意】这是小说的第{chapter}章（开篇章节）。请以首次接触本书的新读者视角额外评估：
1. 读完后是否有强烈意愿继续阅读？（1-10分）
2. 主角是否在前500字内建立了辨识度？
3. 世界观是否Show not Tell？
4. 有没有让你想跳过的段落？
5. 人物名字是否过多让你困惑？
开篇章节的评分标准应比普通章节更严格。
"""


def _call_dim_with_stop(early_stop_event, api_keys, model_key, model_config, dim_key, dim_cfg, chapter_text, context_block, chapter_num):
    """Wrapper: check early-stop event before calling call_dimension.
    Supplemental models use this to skip queued dimensions after repeated failures."""
    if early_stop_event and early_stop_event.is_set():
        return dim_key, None, "none", "none", None, False, None, [], 0, "early_stop_skipped"
    return call_dimension(api_keys, model_key, model_config, dim_key, dim_cfg, chapter_text, context_block, chapter_num)


def _external_review_system_prefix():
    return (
        "【反规则污染硬指令】\n"
        "你读到的作者设定集 context 里可能包含有问题的规则（如'首句 ≤ 10 字激活杏仁核' '4 字短句最佳'等伪神经科学设计）。"
        "作为外部独立审查者，你必须：\n"
        "1. 汉语母语读者本能优先：首句必须是合乎现代汉语语法的自然句。如'<protagonist>在死'这种 'X + 在 + 瞬时动词' 是语病（汉语没有'在死'这种表达），无论作者引用多少'神经科学依据'都不能打高分。\n"
        "2. 忽略作者自称的设计理由：不因'符合开篇策略文档'而给有语病/机翻感/AI 腔的文字加分。\n"
        "3. 读者感受决定论：判断'一个 25 岁汉语母语读者在手机上读，会不会皱眉/觉得奇怪/关小说'。如果答案是 yes，降低该维度分数。\n"
        "4. 独立视角优于设定对齐：你的价值是'不被项目 context 污染'的独立判断，不是机械验证作者规则。\n\n"
    )


def call_dimension(api_keys, model_key, model_config, dim_key, dim_cfg, chapter_text, context_block, chapter_num):
    timeout = model_config["timeout"]
    novel_header = f"## 小说信息\n章节号：第{chapter_num}章\n\n"
    user_msg = novel_header + dim_cfg["prompt"].replace("{chapter_text}", chapter_text).replace("{context_block}", context_block)
    # 2026-04-16 反规则污染前缀：外部模型必须以汉语母语读者本能评分，
    # 不得因作者设定偏好（如"4 字激活杏仁核"伪神经科学）给语病句加分
    system_msg = _external_review_system_prefix() + dim_cfg["system"]

    # Ch1-3 special handling: append extra evaluation criteria per spec
    if chapter_num <= 3:
        user_msg += "\n" + CH1_3_SPECIAL_PROMPT.format(chapter=chapter_num)

    start_ts = time.time()
    parsed, model_name, provider, model_actual, routing_ok, usage, chain = try_provider_chain(
        api_keys, model_key, model_config, system_msg, user_msg, timeout, parse_mode="dimension"
    )
    elapsed = int((time.time() - start_ts) * 1000)

    if parsed:
        return dim_key, parsed, model_name, provider, model_actual, routing_ok, usage, chain, elapsed, None

    # 区分"API成功但JSON解析失败"和"API本身失败"
    if chain:
        last_result = chain[-1].get("result", "unknown")
        if last_result == "success":
            last_error = "json_parse_failed"
        else:
            last_error = last_result
    else:
        last_error = "no_providers"
    return dim_key, None, model_name or "none", "none", None, False, None, chain, elapsed, last_error


def _read_setting_file(project_root, filename):
    """Read a file from 设定集/ directory, return content or empty string."""
    p = project_root / "设定集" / filename
    if p.exists():
        return p.read_text(encoding="utf-8")
    return ""


def _load_state_json(project_root):
    """Load state.json and return dict with protagonist_state, progress, and review context fields."""
    state_path = project_root / ".webnovel" / "state.json"
    if state_path.exists():
        data = json.loads(state_path.read_text(encoding="utf-8"))
        # Extract chapter_meta (recent 3 chapters for hook/pattern/emotion tracking)
        # Use `or` pattern: data.get("key") returns None when JSON value is null
        chapter_meta = data.get("chapter_meta") or {}
        recent_meta = {}
        if chapter_meta:
            sorted_keys = sorted(chapter_meta.keys(), reverse=True)[:3]
            recent_meta = {k: chapter_meta[k] for k in sorted_keys}
        # Extract active foreshadowing threads
        plot_threads = data.get("plot_threads") or {}
        foreshadowing = plot_threads.get("foreshadowing") or []
        # Extract recent strand_tracker history
        strand_tracker = data.get("strand_tracker") or {}
        strand_history = (strand_tracker.get("history") or [])[-5:]
        return {
            "protagonist_state": data.get("protagonist_state") or {},
            "progress": data.get("progress") or {},
            "recent_chapter_meta": recent_meta,
            "foreshadowing": foreshadowing,
            "strand_history": strand_history,
        }
    return {
        "protagonist_state": {},
        "progress": {},
        "recent_chapter_meta": {},
        "foreshadowing": [],
        "strand_history": [],
    }


def _load_prev_chapters(project_root, chapter_num, window=3):
    """Load previous chapters' full text (default: 3 chapters).

    Priority: full chapter text from 正文/ > summary from summaries/ as fallback.
    """
    parts = []
    chapters_dir = project_root / "正文"
    summaries_dir = project_root / ".webnovel" / "summaries"
    for prev in range(max(1, chapter_num - window), chapter_num):
        # Try full chapter text first
        ch_files = list(chapters_dir.glob(f"第{prev:04d}章*.md")) if chapters_dir.exists() else []
        if ch_files:
            text = ch_files[0].read_text(encoding="utf-8")
            parts.append(f"### 第{prev}章正文\n{text}")
        else:
            # Fallback to summary
            summary_path = summaries_dir / f"ch{prev:04d}.md"
            if summary_path.exists():
                text = summary_path.read_text(encoding="utf-8")
                parts.append(f"### 第{prev}章摘要（正文文件缺失，仅有摘要）\n{text}")
    return "\n\n".join(parts)


def build_context_block(context_data, project_root=None, chapter_num=None):
    """Build user message context following step-3.5-external-review.md spec.

    Assembles context from context_data JSON first, then supplements missing
    fields by reading directly from project files (设定集/, state.json, summaries/).
    Includes chapter_meta, foreshadowing, and strand history for accurate
    continuity/reader_pull/pacing/ooc/prose_quality/emotion_expression dimension reviews.
    """
    parts = ["===== 项目上下文（请基于以下信息严格审查正文） =====\n"]
    if not context_data and not project_root:
        parts.append("**警告：无项目上下文，审查结果可能不准确**\n")
        return "\n".join(parts)

    if not project_root:
        project_root = Path(".")
    else:
        project_root = Path(project_root)

    # Load state.json once (provides protagonist_state, progress, and review context)
    state_info = _load_state_json(project_root)

    # 【本章大纲】
    outline = context_data.get("outline_excerpt", "") if context_data else ""
    if outline:
        parts.append(f"【本章大纲】\n{outline}\n")

    # 【主角设定】= 主角卡 + 金手指设计
    protagonist_card = context_data.get("protagonist_card", "") if context_data else ""
    if not protagonist_card:
        protagonist_card = _read_setting_file(project_root, "主角卡.md")
    golden_finger = context_data.get("golden_finger_card", "") if context_data else ""
    if not golden_finger:
        golden_finger = _read_setting_file(project_root, "金手指设计.md")
    if protagonist_card or golden_finger:
        parts.append(f"【主角设定】\n{protagonist_card}\n{golden_finger}\n")

    # 【配角设定】= 女主卡 + 反派设计
    female_lead = context_data.get("female_lead_card", "") if context_data else ""
    if not female_lead:
        female_lead = _read_setting_file(project_root, "女主卡.md")
    villain = context_data.get("villain_design", "") if context_data else ""
    if not villain:
        villain = _read_setting_file(project_root, "反派设计.md")
    if female_lead or villain:
        parts.append(f"【配角设定】\n{female_lead}\n{villain}\n")

    # 【力量体系】
    power = context_data.get("power_system", "") if context_data else ""
    if not power:
        power = _read_setting_file(project_root, "力量体系.md")
    if power:
        parts.append(f"【力量体系】\n{power}\n")

    # 【世界观】
    world = context_data.get("world_settings", "") if context_data else ""
    if not world:
        world = _read_setting_file(project_root, "世界观.md")
    if world:
        parts.append(f"【世界观】\n{world}\n")

    # 【前章正文】(window=3, full chapter text for accurate cross-chapter review)
    # Accept both new key "prev_chapters_text" and legacy key "prev_summaries"
    prev_text = (context_data.get("prev_chapters_text") or context_data.get("prev_summaries") or "") if context_data else ""
    if not prev_text and chapter_num:
        prev_text = _load_prev_chapters(project_root, chapter_num)
    if prev_text:
        parts.append(f"【前章正文（用于判断连贯性、角色一致性、节奏差异化、钩子回应）】\n{prev_text}\n")

    # 【主角当前状态】- remove credits, add progress
    prot_state = (context_data.get("protagonist_state") or {}) if context_data else {}
    if not prot_state:
        prot_state = state_info["protagonist_state"]
    progress = state_info["progress"]
    if prot_state:
        state_copy = json.loads(json.dumps(prot_state))  # deep copy
        if "attributes" in state_copy and "credits" in state_copy["attributes"]:
            del state_copy["attributes"]["credits"]
        state_block = json.dumps(state_copy, ensure_ascii=False, indent=2)
        if progress:
            progress_block = json.dumps(progress, ensure_ascii=False, indent=2)
            state_block += f"\n\n进度信息：\n{progress_block}"
        ch_label = f"第{chapter_num}章后的" if chapter_num else ""
        parts.append(f"【主角当前状态（注意：以下为{ch_label}最新状态，审查早期章节时动态数值可能与正文不一致，请以正文描述为准）】\n{state_block}\n")

    # 【近期章节模式】- recent 3 chapters' hook/emotion/pattern (for reader_pull & high_point)
    recent_meta = state_info.get("recent_chapter_meta") or {}
    if recent_meta:
        meta_lines = []
        for ch_key in sorted(recent_meta.keys()):
            meta = recent_meta[ch_key] if isinstance(recent_meta[ch_key], dict) else {}
            # R28.23 Ch38 RCA: defensive dict checks (chapter_meta fields may drift to str/None/int)
            # 历史漂移：Ch37/Ch38 ending 写成 str 触发 AttributeError 让外审 15/15 失败
            hook_raw = meta.get("hook")
            hook = hook_raw if isinstance(hook_raw, dict) else {}
            pattern_raw = meta.get("pattern")
            pattern = pattern_raw if isinstance(pattern_raw, dict) else {}
            ending_raw = meta.get("ending")
            ending = ending_raw if isinstance(ending_raw, dict) else {}
            # Fallback: 顶层扁平字段（新 schema） — hook_type/hook_strength/emotion_rhythm
            hook_type = hook.get("type") or meta.get("hook_type") or "?"
            hook_strength = hook.get("strength") or meta.get("hook_strength") or "?"
            emotion_rhythm = pattern.get("emotion_rhythm") or meta.get("emotion_rhythm") or "?"
            ending_emotion = ending.get("emotion") or "?"
            ending_location = ending.get("location") or meta.get("location_current") or "?"
            # 若 ending 是 str（旧漂移）作为人读描述插入
            if isinstance(ending_raw, str) and ending_raw.strip():
                ending_emotion = ending_raw[:50]
            meta_lines.append(
                f"第{ch_key}章: 钩子={hook_type}({hook_strength}) "
                f"开场={pattern.get('opening','?')} 情绪={emotion_rhythm} "
                f"结束情绪={ending_emotion} 地点={ending_location}"
            )
        parts.append(f"【近期章节模式（判断钩子/情绪/模式是否重复）】\n" + "\n".join(meta_lines) + "\n")

    # 【活跃伏笔线】- active foreshadowing threads (for continuity)
    foreshadowing = state_info.get("foreshadowing") or []
    if foreshadowing:
        fs_lines = []
        for fs in foreshadowing:
            if isinstance(fs, dict):
                status = fs.get("status", "active")
                if status in ("active", "planted"):
                    desc = fs.get("description", fs.get("content", "?"))
                    planted = fs.get("planted_chapter", "?")
                    urgency = fs.get("urgency", "")
                    urgency_str = f" 紧迫度={urgency}" if urgency else ""
                    fs_lines.append(f"- [Ch{planted}埋设] {desc}{urgency_str}")
        if fs_lines:
            parts.append(f"【活跃伏笔线（判断伏笔是否有回应、是否遗忘）】\n" + "\n".join(fs_lines) + "\n")

    # 【节奏历史】- recent 5 strand history (for pacing differentiation)
    strand_history = state_info.get("strand_history") or []
    if strand_history:
        sh_lines = []
        for sh in strand_history:
            if isinstance(sh, dict):
                ch = sh.get("chapter", "?")
                dom = sh.get("dominant", "?")
                sh_lines.append(f"第{ch}章: {dom}")
        if sh_lines:
            parts.append(f"【节奏历史（判断节奏是否有差异化，避免连续同类型）】\n" + "\n".join(sh_lines) + "\n")

    return "\n".join(parts)


def _norm_text(s: str) -> str:
    """Normalize quote marks + whitespace + common Chinese punct for fuzzy matching.

    Round 12: strip ALL quote marks entirely (both curly & straight) so that
    external models wrapping quote strings in leading/trailing quote marks
    don't break substring matching. Also strips em-dash variants.
    """
    if not s:
        return ""
    out = s
    # Remove all quote-like chars (they're mostly visual markers in model outputs)
    for ch in ('"', '"', '"', ''', ''', "'", '「', '」', '『', '』', '《', '》'):
        out = out.replace(ch, '')
    # Normalize CJK punctuation to ASCII equivalents
    out = (out
           .replace('，', ',').replace('。', '.').replace('；', ';')
           .replace('：', ':').replace('！', '!').replace('？', '?')
           .replace('—', '-').replace('–', '-').replace('·', '.'))
    return ''.join(out.split())


def _verify_quote_style(quote: str, chapter_text: str) -> str:
    """Return match style for quote against chapter_text.

    Styles (from strongest to weakest evidence):
    - "exact": raw substring match
    - "normalized": matches after punct/whitespace/quote-mark normalization
    - "elision": quote uses explicit elision markers (……/…/...) OR is an implicit
      segmented quote whose head+tail both appear within <= 120 normalized chars
      of each other in the chapter — the external model is doing legitimate
      "A…B" style omission quoting, which is NOT a hallucination.
    - "truncated": long quote (>=15) whose first 10 chars appear in chapter
    - "missing": none of the above — likely hallucination

    Rationale (Ch1 <example-project> Round 12 RCA): Qwen 正确识别"三十天后末世爆发"信息倾倒 bug，
    但其 quote 用省略引用（跳过中间旁白"那声音说"），被误判幻觉 severity 强降 info，
    导致真实问题被吞。elision 识别使省略引用保留原 severity。
    """
    if not quote or not chapter_text:
        return "missing"

    # Fast path: raw substring match
    if quote in chapter_text:
        return "exact"

    nq = _norm_text(quote)
    nc = _norm_text(chapter_text)
    if nq and nq in nc:
        return "normalized"

    # Explicit elision marker: quote contains …/.../……
    # Split by any ellipsis token, verify every non-empty segment appears in chapter
    # AND verify the segments appear in-order with reasonable distance (<= 200 norm chars)
    ellipsis_tokens = ['……', '...', '…', '… …']
    has_ellipsis = any(tok in quote for tok in ellipsis_tokens)
    if has_ellipsis:
        # Replace all ellipsis variants with a single delimiter for splitting
        split_quote = quote
        for tok in ellipsis_tokens:
            split_quote = split_quote.replace(tok, '\x00')
        segments = [s.strip() for s in split_quote.split('\x00') if s.strip()]
        if len(segments) >= 2 and all(len(s) >= 2 for s in segments):
            positions = []
            search_pos = 0
            all_found = True
            for seg in segments:
                nseg = _norm_text(seg)
                if not nseg:
                    continue
                idx = nc.find(nseg, search_pos)
                if idx < 0:
                    all_found = False
                    break
                positions.append(idx)
                search_pos = idx + len(nseg)
            if all_found and positions:
                # Check max gap between consecutive segments is reasonable (<= 200 chars in normalized text)
                gaps = []
                for i in range(1, len(positions)):
                    prev_end = positions[i-1] + len(_norm_text(segments[i-1]))
                    gaps.append(positions[i] - prev_end)
                if all(g <= 200 for g in gaps):
                    return "elision"

    # Implicit elision: head + tail both appear and are reasonably close
    # Guards against false-positives: require quote long enough to carry info
    if len(quote) >= 12:
        head_len = min(6, max(4, len(quote) // 4))
        tail_len = head_len
        head = _norm_text(quote[:head_len])
        tail = _norm_text(quote[-tail_len:])
        if head and tail and head != tail:
            head_idx = nc.find(head)
            if head_idx >= 0:
                # Tail must appear AFTER head, within 120 normalized chars
                search_from = head_idx + len(head)
                tail_idx = nc.find(tail, search_from)
                if 0 <= tail_idx - search_from <= 120:
                    return "elision"

    # Fallback: for long quotes, require core 10-char substring presence
    if len(quote) >= 15:
        core = quote[:10]
        if core in chapter_text or _norm_text(core) in nc:
            return "truncated"
    return "missing"


def _verify_quote_exists(quote: str, chapter_text: str) -> bool:
    """Backwards-compatible boolean wrapper around _verify_quote_style.

    Returns True for exact/normalized/elision/truncated styles; False for missing.
    """
    return _verify_quote_style(quote, chapter_text) != "missing"


def _downgrade_severity(severity: str) -> str:
    """Downgrade severity one tier for hallucinated-quote issues.

    critical → high → medium → low → info
    Unknown levels default to 'info' (safest reduction).
    """
    tiers = ["critical", "high", "medium", "low", "info"]
    try:
        idx = tiers.index((severity or "").lower())
        return tiers[min(idx + 1, len(tiers) - 1)]
    except ValueError:
        return "info"


def _compute_cross_validation(all_issues):
    """Cross-validate issues: group by type+location similarity, mark consensus.

    Rules:
    - Issues with the same type AND similar location from the same model
      are grouped together.
    - Since this runs per-model (single model), cross-validation within
      a single model marks issues based on dimension agreement:
      - verified: issue flagged by >=2 dimensions (corroborated)
      - unverified: issue flagged by only 1 dimension
      - dismissed: 0 (requires cross-model data, handled at aggregation layer)

    When used at the aggregation layer (across all configured models), the caller should
    re-run cross-validation across all model results for true consensus.
    """
    if not all_issues:
        return {
            "total_issues": 0,
            "verified": 0,
            "unverified": 0,
            "dismissed": 0,
            "consensus_groups": [],
        }

    # Group issues by (severity, type_or_id_prefix, approximate_location)
    from collections import defaultdict
    groups = defaultdict(list)
    for issue in all_issues:
        # Build grouping key: severity + issue type pattern + location
        severity = issue.get("severity", "unknown")
        # Try to extract issue type from id prefix (e.g., "CON_001" -> "CON")
        issue_id = issue.get("id", "")
        issue_type = issue.get("type", "")
        if not issue_type and issue_id:
            issue_type = issue_id.split("_")[0] if "_" in issue_id else issue_id
        location = issue.get("location", "unknown")
        # Normalize location: strip whitespace, take first 10 chars for fuzzy match
        loc_key = location.strip()[:15] if location else "unknown"
        group_key = f"{issue_type}|{loc_key}"
        groups[group_key].append(issue)

    verified_count = 0
    unverified_count = 0
    consensus_groups = []

    for key, group_issues in groups.items():
        # Count unique source dimensions
        source_dims = set()
        for iss in group_issues:
            dim = iss.get("source_dimension", "")
            if dim:
                source_dims.add(dim)

        if len(source_dims) >= 2:
            # Corroborated by multiple dimensions
            verified_count += len(group_issues)
            consensus_groups.append({
                "type": key.split("|")[0],
                "location": key.split("|")[1] if "|" in key else "unknown",
                "dimension_count": len(source_dims),
                "dimensions": sorted(source_dims),
                "issue_count": len(group_issues),
                "max_severity": max(
                    (iss.get("severity", "low") for iss in group_issues),
                    key=lambda s: {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(s, 0)
                ),
            })
        else:
            unverified_count += len(group_issues)

    return {
        "total_issues": len(all_issues),
        "verified": verified_count,
        "unverified": unverified_count,
        "dismissed": 0,  # Requires project data comparison, done at aggregation layer
        "consensus_groups": consensus_groups,
    }


class CombinedReviewError(RuntimeError):
    """Combined per-model review failed before a usable output object existed."""


def _coerce_score(value):
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if score < 0 or score > 100:
        return None
    return round(score, 1)


def _dimension_key_from_report(report):
    if not isinstance(report, dict):
        return None
    raw = (
        report.get("dimension")
        or report.get("key")
        or report.get("id")
        or report.get("name")
        or ""
    )
    raw = str(raw).strip()
    if raw in DIMENSIONS:
        return raw
    if raw in DIMENSION_NAME_ALIASES:
        return DIMENSION_NAME_ALIASES[raw]
    raw_lower = raw.lower().replace("-", "_").replace(" ", "_")
    if raw_lower in DIMENSIONS:
        return raw_lower
    if raw_lower in DIMENSION_NAME_ALIASES:
        return DIMENSION_NAME_ALIASES[raw_lower]
    for key, cfg in DIMENSIONS.items():
        if raw == cfg.get("name"):
            return key
    return None


def _process_dimension_issues(dim_issues, resolved_key, dim_key, chapter_text):
    clean_issues = [it for it in (dim_issues or []) if isinstance(it, dict)]
    for issue in clean_issues:
        issue["source_model"] = resolved_key
        issue["source_dimension"] = dim_key
        quote = issue.get("quote")
        if isinstance(quote, str) and quote.strip():
            style = _verify_quote_style(quote, chapter_text)
            verified = style != "missing"
            issue["quote_verified"] = verified
            issue["quote_style"] = style
            if style == "elision":
                issue["quote_elision_note"] = (
                    "quote 使用省略引用（head+tail 均在正文中），"
                    "保留原 severity 不降级"
                )
            elif not verified:
                original_severity = issue.get("severity", "medium")
                issue["original_severity"] = original_severity
                issue["severity"] = _downgrade_severity(original_severity)
                issue["quote_hallucination_note"] = (
                    "外部模型引用的 quote 未在正文中找到，severity 已降级一档"
                )
    return clean_issues


def build_combined_prompt(chapter_text, context_block, chapter_num):
    """Build one large prompt asking one model to return all 13 dimension reports."""
    dimension_lines = []
    for idx, key in enumerate(DIMENSION_ORDER, 1):
        dimension_lines.append(f"{idx}. `{key}` / {DIMENSIONS[key]['name']}：{COMBINED_DIMENSION_GUIDE[key]}")

    dimension_objects = []
    for key in DIMENSION_ORDER:
        item = {
            "dimension": key,
            "score": 88,
            "issues": [
                {
                    "id": f"{key.upper()}_001",
                    "type": "SETTING_CONFLICT|CONTINUITY|OOC|PACING|READER_PULL|STYLE|DIALOGUE_FLAT|DIALOGUE_INFODUMP|DIALOGUE_MONOLOGUE|PADDING|REPETITION|PROSE_FLAT|EMOTION_SHALLOW|NATURALNESS|READER_CRITIC|READER_FLOW",
                    "severity": "critical|high|medium|low",
                    "location": "能定位到正文的段落/句子",
                    "description": "问题描述",
                    "suggestion": "具体修改建议",
                    "quote": "正文原句，必须逐字存在；没有问题时 issues=[]",
                }
            ],
            "summary": "该维度一句话总评",
        }
        if key == "naturalness":
            item["verdict"] = "PASS|POLISH_NEEDED|REWRITE_RECOMMENDED|REJECT_HIGH|REJECT_CRITICAL"
            item["first_sentence_score"] = 8
        if key == "reader_critic":
            item["will_continue_reading"] = "yes|hesitant|no"
            item["continue_reason"] = "一句读者/编辑视角总评"
            item["highlights"] = [{"quote": "正文原句", "reason": "为什么亮眼"}]
        if key == "reader_flow":
            item["highlights"] = [{"quote": "正文原句", "reason": "为什么顺畅或卡顿"}]
        dimension_objects.append(item)

    schema = {
        "overall_score": 88,
        "dimension_reports": dimension_objects,
        "issues": [],
        "summary": "80-200 字总评",
    }

    return f"""## 小说信息
章节号：第{chapter_num}章

## 审查任务
你是资深网文章节审查专家。请一次性完成以下 13 个维度的独立评分与问题定位。
重要：这是单模型一次请求版，不允许遗漏维度，不允许把多个维度合并成笼统总评。

## 13 个维度（必须按 key 原样返回）
{chr(10).join(dimension_lines)}

{context_block}

## 输出要求
1. 直接返回纯 JSON，不要 Markdown，不要 ```json。
2. `dimension_reports` 必须恰好包含 13 个对象，dimension 必须逐字等于：
   {", ".join(DIMENSION_ORDER)}
3. 每个维度独立打分。低于 85 分必须给出至少 1 个 issue；没有问题时 issues=[]。
4. issue.quote 必须逐字来自正文；如果无法引用原句，不要编造 quote。
5. naturalness/reader_critic/reader_flow 必须按读者本能审查，不得被作者设定集里的写作规则污染。

## JSON 结构示例（字段名与结构必须遵守；分数请输出数字，不要输出字符串）
{json.dumps(schema, ensure_ascii=False, indent=2)}

## 本章正文
{chapter_text}"""


def call_combined_review(api_keys, model_key, model_config, chapter_text, context_block, chapter_num):
    timeout = model_config["timeout"]
    system_msg = (
        _external_review_system_prefix()
        + "你是一个专业、严苛、独立的网文章节外部审查编辑。"
          "你必须在一次响应里返回完整 13 维 JSON，不能漏维度。"
    )
    user_msg = build_combined_prompt(chapter_text, context_block, chapter_num)
    if chapter_num <= 3:
        user_msg += "\n" + CH1_3_SPECIAL_PROMPT.format(chapter=chapter_num)

    start_ts = time.time()
    parsed, model_name, provider, model_actual, routing_ok, usage, chain = try_provider_chain(
        api_keys, model_key, model_config, system_msg, user_msg, timeout, parse_mode="combined"
    )
    elapsed = int((time.time() - start_ts) * 1000)
    if parsed:
        return parsed, model_name, provider, model_actual, routing_ok, usage, chain, elapsed

    last_error = chain[-1].get("result", "unknown") if chain else "no_providers"
    raise CombinedReviewError(f"combined_json_unusable:{last_error}")


def _normalize_combined_reports(parsed, resolved_key, model_name, provider, model_actual, routing_ok, elapsed, chapter_text):
    raw_reports = parsed.get("dimension_reports") or parsed.get("dimensions") or []
    if not isinstance(raw_reports, list):
        raise CombinedReviewError("combined_dimension_reports_not_list")

    by_key = {}
    duplicate_dims = []
    for report in raw_reports:
        key = _dimension_key_from_report(report)
        if not key:
            continue
        if key in by_key:
            duplicate_dims.append(key)
            continue
        by_key[key] = report

    results = {}
    all_issues = []
    scores = {}
    validation_errors = []

    for dim_key in DIMENSION_ORDER:
        report = by_key.get(dim_key)
        if not report:
            results[dim_key] = {"status": "failed", "error": "missing_dimension_in_combined"}
            validation_errors.append(f"{dim_key}:missing")
            continue

        score = _coerce_score(report.get("score"))
        if score is None:
            results[dim_key] = {"status": "failed", "error": "invalid_score_in_combined"}
            validation_errors.append(f"{dim_key}:invalid_score")
            continue

        dim_issues = _process_dimension_issues(report.get("issues") or [], resolved_key, dim_key, chapter_text)
        all_issues.extend(dim_issues)
        scores[dim_key] = score

        dim_result = {
            "status": "ok",
            "score": score,
            "issues": dim_issues,
            "summary": report.get("summary") or report.get("comment") or "",
            "model": model_name,
            "model_actual": model_actual,
            "provider": provider,
            "routing_verified": routing_ok,
            "elapsed_ms": elapsed,
            "review_strategy": "combined",
        }
        for extra_key in COMBINED_EXTRA_FIELDS:
            if extra_key in report:
                dim_result[extra_key] = report[extra_key]
        results[dim_key] = dim_result

    if duplicate_dims:
        validation_errors.append("duplicate_dimensions:" + ",".join(sorted(set(duplicate_dims))))

    return results, all_issues, scores, validation_errors


def _build_model_output(resolved_key, model_config, chapter_num, results, all_issues, full_provider_chain,
                        final_provider, model_actual_final, routing_all_ok, total_elapsed,
                        total_prompt_tokens, total_completion_tokens, review_strategy,
                        strategy_fallback_reason=None, validation_errors=None):
    valid_scores = [
        r.get("score")
        for r in results.values()
        if r.get("status") == "ok" and isinstance(r.get("score"), (int, float))
    ]
    overall = round(sum(valid_scores) / len(valid_scores), 1) if valid_scores else 0
    metrics = {
        "dimensions_ok": sum(1 for r in results.values() if r.get("status") == "ok"),
        "dimensions_failed": sum(1 for r in results.values() if r.get("status") == "failed"),
        "dimensions_skipped": sum(1 for r in results.values() if r.get("status") == "skipped"),
        "total_issues": len(all_issues),
    }
    if validation_errors:
        metrics["validation_errors"] = validation_errors

    api_meta = {
        "final_provider": final_provider,
        "elapsed_ms": total_elapsed,
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_completion_tokens,
        "attempts_total": len(full_provider_chain),
        "review_strategy": review_strategy,
    }
    if strategy_fallback_reason:
        api_meta["strategy_fallback_reason"] = strategy_fallback_reason

    return {
        "agent": f"external-{resolved_key}",
        "chapter": chapter_num,
        "model_key": resolved_key,
        "model_requested": model_config["providers"][0]["id"],
        "model_actual": model_actual_final,
        "provider": final_provider,
        "routing_verified": routing_all_ok,
        "overall_score": overall,
        "pass": overall >= 75,
        "dimension_reports": [
            {"dimension": dk, "name": DIMENSIONS[dk]["name"], **dv}
            for dk, dv in sorted(results.items())
        ],
        "issues": all_issues,
        "cross_validation": _compute_cross_validation(all_issues),
        "provider_chain": full_provider_chain,
        "api_meta": api_meta,
        "metrics": metrics,
        "summary": (
            f"{resolved_key} {len(DIMENSIONS)}维度审查完成，"
            f"{len(valid_scores)}/{len(DIMENSIONS)}成功，综合{overall}分，{len(all_issues)}个问题"
        ),
    }


def _save_external_review_output(args, project_root, resolved_key, chapter_num, output):
    # Save · Round 15.3 · 2026-04-23 · Ch6 RCA Bug #5 根治：merge-partial
    out_path = project_root / ".webnovel" / "tmp" / f"external_review_{resolved_key}_ch{chapter_num:04d}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged_output = output
    if out_path.exists() and not getattr(args, "no_merge_partial", False):
        try:
            existing = json.loads(out_path.read_text(encoding="utf-8"))
            existing_dims = {d.get("dimension"): d for d in existing.get("dimension_reports", []) if isinstance(d, dict)}
            merged_dims = []
            for new_dim in output.get("dimension_reports", []):
                dname = new_dim.get("dimension")
                existing_dim = existing_dims.get(dname)
                new_ok = new_dim.get("status") == "ok"
                existing_ok = existing_dim and existing_dim.get("status") == "ok"
                if not new_ok and existing_ok:
                    merged = dict(existing_dim)
                    merged["_merged_from"] = "previous_run"
                    merged_dims.append(merged)
                else:
                    merged_dims.append(new_dim)
            merged_output = dict(output)
            merged_output["dimension_reports"] = merged_dims
            ok_dims = [d for d in merged_dims if d.get("status") == "ok"]
            merged_scores = [d["score"] for d in ok_dims if isinstance(d.get("score"), (int, float))]
            if merged_scores:
                merged_output["overall_score"] = round(sum(merged_scores) / len(merged_scores), 1)
                merged_output["pass"] = merged_output["overall_score"] >= 75
            merged_output["metrics"] = {
                **(merged_output.get("metrics") or {}),
                "dimensions_ok": len(ok_dims),
                "dimensions_failed": sum(1 for d in merged_dims if d.get("status") == "failed"),
                "dimensions_skipped": sum(1 for d in merged_dims if d.get("status") == "skipped"),
                "merged_partial": True,
                "preserved_from_previous": sum(1 for d in merged_dims if d.get("_merged_from") == "previous_run"),
            }
            if merged_output["metrics"]["preserved_from_previous"] > 0:
                print(
                    f"[merge-partial] 保留上次成功的 {merged_output['metrics']['preserved_from_previous']} 个维度数据",
                    file=sys.stderr,
                )
        except Exception as _ex:
            print(f"[merge-partial] 合并失败退化为覆盖: {_ex}", file=sys.stderr)
            merged_output = output

    out_path.write_text(json.dumps(merged_output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(merged_output, ensure_ascii=False))
    return merged_output


def _load_single_model_inputs(args, project_root, chapter_num):
    context_data = getattr(args, '_preloaded_context', None)
    chapter_text = getattr(args, '_preloaded_chapter_text', None)

    if context_data is None:
        context_file = project_root / ".webnovel" / "tmp" / f"external_context_ch{chapter_num:04d}.json"
        if not context_file.exists():
            print(json.dumps({
                "error": f"external_context_ch{chapter_num:04d}.json 不存在",
                "remediation": [
                    f"先运行: python -X utf8 scripts/build_external_context.py --project-root \"{project_root}\" --chapter {chapter_num}",
                    "Round 21.0 H32: 禁止从空 context 启动外部审查"
                ]
            }, ensure_ascii=False), file=sys.stderr)
            sys.exit(1)
        ctx_size = context_file.stat().st_size
        try:
            context_data = json.loads(context_file.read_text(encoding="utf-8"))
        except Exception as e:
            print(json.dumps({"error": f"context 解析失败: {e}"}, ensure_ascii=False), file=sys.stderr)
            sys.exit(1)
        if ctx_size < 1024 or context_data.get("_auto_generated") is True:
            print(json.dumps({
                "error": f"context 是 disk fallback 占位 ({ctx_size} bytes)",
                "remediation": [f"先运行: python -X utf8 scripts/build_external_context.py --project-root \"{project_root}\" --chapter {chapter_num}"]
            }, ensure_ascii=False), file=sys.stderr)
            sys.exit(1)

    if chapter_text is None:
        chapters_dir = project_root / "正文"
        ch_files = list(chapters_dir.glob(f"第{chapter_num:04d}章*.md"))
        if not ch_files:
            print(json.dumps({"error": f"Chapter {chapter_num} not found"}))
            sys.exit(1)
        chapter_text = ch_files[0].read_text(encoding="utf-8")

    return context_data, chapter_text


def _run_single_model_combined(args, api_keys, save=True):
    project_root = Path(args.project_root)
    chapter_num = args.chapter
    model_key = args.model_key
    resolved_key = MODEL_ALIASES.get(model_key, model_key)
    if resolved_key not in MODELS:
        print(json.dumps({"error": f"Unknown model: {model_key} (resolved: {resolved_key})"}))
        sys.exit(1)

    model_config = MODELS[resolved_key]
    context_data, chapter_text = _load_single_model_inputs(args, project_root, chapter_num)
    context_block = build_context_block(context_data, project_root=project_root, chapter_num=chapter_num)

    parsed, model_name, provider, model_actual, routing_ok, usage, chain, elapsed = call_combined_review(
        api_keys, resolved_key, model_config, chapter_text, context_block, chapter_num
    )
    results, all_issues, scores, validation_errors = _normalize_combined_reports(
        parsed, resolved_key, model_name, provider, model_actual, routing_ok, elapsed, chapter_text
    )

    output = _build_model_output(
        resolved_key=resolved_key,
        model_config=model_config,
        chapter_num=chapter_num,
        results=results,
        all_issues=all_issues,
        full_provider_chain=chain,
        final_provider=provider,
        model_actual_final=model_actual or "",
        routing_all_ok=routing_ok,
        total_elapsed=elapsed,
        total_prompt_tokens=(usage or {}).get("prompt_tokens", 0),
        total_completion_tokens=(usage or {}).get("completion_tokens", 0),
        review_strategy="combined",
        validation_errors=validation_errors,
    )

    if save:
        return _save_external_review_output(args, project_root, resolved_key, chapter_num, output)
    return output


def _run_single_model(args, api_keys):
    strategy = getattr(args, "dimension_strategy", "auto")
    if strategy == "split":
        return _run_single_model_split(args, api_keys)

    try:
        output = _run_single_model_combined(args, api_keys, save=False)
        dims_ok = (output.get("metrics") or {}).get("dimensions_ok", 0)
        if dims_ok == len(DIMENSIONS) or strategy == "combined":
            return _save_external_review_output(
                args, Path(args.project_root), output["model_key"], args.chapter, output
            )
        raise CombinedReviewError(f"combined_incomplete:{dims_ok}/{len(DIMENSIONS)}")
    except CombinedReviewError as e:
        if strategy == "combined":
            raise
        print(f"[combined-fallback] {args.model_key}: {e} → split 逐维兜底", file=sys.stderr)
        setattr(args, "_strategy_fallback_reason", str(e))
        return _run_single_model_split(args, api_keys)


def run_dimensions_mode(args, api_keys):
    project_root = Path(args.project_root)
    chapter_num = args.chapter
    model_key = args.model_key

    # --model-key all: 并发执行全部模型（ProviderRateLimiter 自动控制 RPM）
    if model_key == "all":
        all_model_keys = list(MODELS.keys())
        model_concurrent = max(1, int(getattr(args, "model_concurrent", 4) or 4))
        print(
            f"[all-models] 并发执行 {len(all_model_keys)} 个模型 "
            f"(model_concurrent={model_concurrent}, strategy={getattr(args, 'dimension_strategy', 'auto')}): "
            f"{', '.join(all_model_keys)}",
            file=sys.stderr,
        )
        all_results = {}

        # 预加载共享数据（一次读取，所有线程复用，避免15个模型重复IO）
        # Round 21.0 · 2026-04-28 · Ch15 RCA H32 根治：
        #   旧版逻辑（"disk fallback"）允许在 context 文件缺失时落 50-byte stub，
        #   让 build_context_block 在每个 worker 内零散从磁盘读字段。这种"魔法 fallback"
        #   表面上可工作，但：
        #     1. SKILL.md 明确写"若文件不存在，脚本将报错退出（exit 1）"，code 与 doc 不一致
        #     2. 15 个并发 worker 各自从磁盘碎片化读字段，无法保证读到的是 build_external_context.py
        #        生成的"14 字段结构化上下文"（含 narrative_voice / emotional_blueprint / classical_references）
        #     3. Ch15 实战：disk fallback 50-byte stub 让 6 个完成的模型实际是"盲评"
        #   新规则：
        #     - context 文件不存在 → exit 1 + 提示运行 build_external_context.py
        #     - context 文件存在但 < 1KB 或含 "_auto_generated":true → exit 1
        #     - 只有真上下文（>= 1KB 真 14 字段）才允许进入并发审查
        context_file = project_root / ".webnovel" / "tmp" / f"external_context_ch{chapter_num:04d}.json"
        if not context_file.exists():
            print(json.dumps({
                "error": f"external_context_ch{chapter_num:04d}.json 不存在",
                "remediation": [
                    f"先运行: python -X utf8 scripts/build_external_context.py --project-root \"{project_root}\" --chapter {chapter_num}",
                    "build_external_context.py 会落盘 14 字段真上下文 (~250KB)，让 15 个外部模型有据可依地评分",
                    "禁止从空 context 启动外部审查（Round 21.0 H32 根治）"
                ]
            }, ensure_ascii=False), file=sys.stderr)
            sys.exit(1)
        ctx_size = context_file.stat().st_size
        ctx_text = context_file.read_text(encoding="utf-8")
        try:
            _shared_context = json.loads(ctx_text)
        except Exception as e:
            print(json.dumps({
                "error": f"external_context_ch{chapter_num:04d}.json 解析失败: {e}",
                "remediation": ["重新运行 build_external_context.py 重建"]
            }, ensure_ascii=False), file=sys.stderr)
            sys.exit(1)
        if ctx_size < 1024 or _shared_context.get("_auto_generated") is True:
            print(json.dumps({
                "error": f"external_context_ch{chapter_num:04d}.json 是 disk fallback 占位 ({ctx_size} bytes)",
                "detail": "Round 21.0 H32 根治：禁止从 50-byte fallback stub 启动外部审查（盲评）",
                "remediation": [
                    f"删除 stub 文件后，运行: python -X utf8 scripts/build_external_context.py --project-root \"{project_root}\" --chapter {chapter_num}",
                ]
            }, ensure_ascii=False), file=sys.stderr)
            sys.exit(1)
        chapters_dir = project_root / "正文"
        ch_files = list(chapters_dir.glob(f"第{chapter_num:04d}章*.md"))
        _shared_chapter_text = ch_files[0].read_text(encoding="utf-8") if ch_files else None
        if not _shared_chapter_text:
            print(json.dumps({"error": f"Chapter {chapter_num} not found"}))
            sys.exit(1)

        def _run_model_safe(mk):
            args_copy = argparse.Namespace(**vars(args))
            args_copy.model_key = mk
            args_copy._preloaded_context = _shared_context
            args_copy._preloaded_chapter_text = _shared_chapter_text
            try:
                print(f"[all-models] 开始: {mk}", file=sys.stderr)
                _run_single_model(args_copy, api_keys)
                # Round 18 · 2026-04-24 · Ch10 P1-10 根治：success 实际指标
                # 旧逻辑：try/catch 不抛异常即"success"。但 kimi-k2.6 13/13 维度 rate_limited
                # 早停后 _run_single_model 仍正常返回（写出 score=0 的 JSON），被误判 success。
                # 新逻辑：检查输出 JSON 的 dimension_reports 是否有 ≥1 个 ok 维度，
                # 否则改报 "all_dimensions_failed"（仍不抛异常，但 status 准确）。
                try:
                    out_path = (Path(args_copy.project_root) / ".webnovel" / "tmp"
                                / f"external_review_{mk}_ch{args_copy.chapter:04d}.json")
                    if out_path.exists():
                        d = json.loads(out_path.read_text(encoding='utf-8'))
                        ok_dims = [r for r in d.get("dimension_reports") or []
                                   if r.get("status") == "ok"]
                        if not ok_dims:
                            print(f"[all-models] 完成: {mk}（all_dimensions_failed）", file=sys.stderr)
                            return mk, "all_dimensions_failed"
                except Exception:
                    pass
                print(f"[all-models] 完成: {mk}", file=sys.stderr)
                return mk, "success"
            except SystemExit:
                print(f"[all-models] 失败: {mk}", file=sys.stderr)
                return mk, "failed"
            except Exception as e:
                print(f"[all-models] 异常: {mk} — {e}", file=sys.stderr)
                return mk, f"error: {str(e)[:80]}"

        # combined 默认每模型 1 个大请求；split fallback 才会在模型内部开维度并发。
        with ThreadPoolExecutor(max_workers=min(len(all_model_keys), model_concurrent)) as executor:
            futures = {executor.submit(_run_model_safe, mk): mk for mk in all_model_keys}
            for f in as_completed(futures):
                mk, result = f.result()
                all_results[mk] = result

        success_count = sum(1 for v in all_results.values() if v == "success")
        failed_count = sum(1 for v in all_results.values() if v != "success")
        total_count = len(all_model_keys)
        # Round 16/25 · 2026-05-02 · 15 模型扁平健康判定（V4-Flash 加入后阈值保持绝对数）：
        #   ≥ 10/15 成功 → healthy（绿线通过）
        #   8-9/15      → degraded_ok（warn medium · 仍可继续）
        #   5-7/15      → degraded_warn（warn high · 但不阻塞 · 15 模型共识足够）
        #   < 5/15      → critical（多家 provider 同时挂 · 实际基本不会发生）
        if success_count >= 10:
            coverage_status = "healthy"
        elif success_count >= 8:
            coverage_status = "degraded_ok"
        elif success_count >= 5:
            coverage_status = "degraded_warn"
        else:
            coverage_status = "critical"

        summary = {
            "mode": "all-models",
            "chapter": chapter_num,
            "dimension_strategy": getattr(args, "dimension_strategy", "auto"),
            "model_concurrent": model_concurrent,
            "total": total_count,
            "success": success_count,
            "failed": failed_count,
            "coverage_status": coverage_status,
            "coverage_thresholds": {
                "healthy": ">= 10/15",
                "degraded_ok": "8-9/15",
                "degraded_warn": "5-7/15",
                "critical": "< 5/15",
            },
            "details": all_results,
        }
        # Round 28.4 · Ch26 RCA · P1-9 根治：all-models 完成后必须重算 aggregate
        # 根因（Ch26）：单模型补跑（如 deepseek-v4-flash 后台 retry）后
        # external_review_ch{NNNN}.json 永远不刷新，state.external_avg 始终用旧值。
        try:
            refresh_external_aggregate(project_root, chapter_num)
        except Exception as exc:
            print(f"[all-models] aggregate refresh 失败（不阻断）: {exc}", file=sys.stderr)
        print(json.dumps(summary, ensure_ascii=False))
        return

    _run_single_model(args, api_keys)
    # Round 28.4 · Ch26 RCA · P1-9：单模型路径也要在写盘后刷新 aggregate
    try:
        refresh_external_aggregate(Path(args.project_root), args.chapter)
    except Exception as exc:
        print(f"[single-model] aggregate refresh 失败（不阻断）: {exc}", file=sys.stderr)


def refresh_external_aggregate(project_root, chapter_num):
    """Round 28.4 · Ch26 RCA · P1-9 根治：扫描 .webnovel/tmp/external_review_*_ch{NNNN}.json
    重算 external_avg / models_ok / models_failed / coverage_status 写到 aggregate 文件。

    根因（Ch26）：单模型补跑后 aggregate 永远不更新，state.external_avg 始终用旧值。
    本函数是 single source of truth：只读 disk 单模型 JSON，不依赖任何运行时变量。

    Returns dict with refreshed aggregate data.
    """
    tmp_dir = project_root / ".webnovel" / "tmp"
    if not tmp_dir.exists():
        return None
    pad = f"{chapter_num:04d}"
    pattern = f"external_review_*_ch{pad}.json"
    # 排除 aggregate 文件本身（命名 external_review_ch{NNNN}.json，无中间 model key）
    aggregate_path = tmp_dir / f"external_review_ch{pad}.json"
    model_files = [
        p for p in tmp_dir.glob(pattern) if p.name != aggregate_path.name
    ]
    if not model_files:
        return None
    models_ok = []
    models_failed = []
    scores = []
    for mf in model_files:
        # 提取 model key: external_review_{key}_ch{NNNN}.json → key
        name = mf.name
        prefix = "external_review_"
        suffix = f"_ch{pad}.json"
        if not (name.startswith(prefix) and name.endswith(suffix)):
            continue
        mkey = name[len(prefix):-len(suffix)]
        try:
            d = json.loads(mf.read_text(encoding="utf-8"))
        except Exception:
            models_failed.append(mkey)
            continue
        ok_dims = [r for r in d.get("dimension_reports") or [] if r.get("status") == "ok"]
        if d.get("error") or not ok_dims:
            models_failed.append(mkey)
            continue
        score = d.get("overall_score")
        if isinstance(score, (int, float)) and score > 0:
            models_ok.append(mkey)
            scores.append(float(score))
        else:
            models_failed.append(mkey)
    external_avg = round(sum(scores) / len(scores), 1) if scores else None
    n_ok = len(models_ok)
    if n_ok >= 10:
        coverage_status = "healthy"
    elif n_ok >= 8:
        coverage_status = "degraded_ok"
    elif n_ok >= 5:
        coverage_status = "degraded_warn"
    else:
        coverage_status = "critical"
    aggregate = {
        "chapter": chapter_num,
        "external_avg": external_avg,
        "models_ok": models_ok,
        "models_failed": models_failed,
        "models_ok_count": n_ok,
        "models_failed_count": len(models_failed),
        "coverage_status": coverage_status,
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
    }
    aggregate_path.write_text(
        json.dumps(aggregate, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return aggregate


def _run_single_model_split(args, api_keys):
    """执行单个模型的 13 维度审查（含 reader_flow）。"""
    project_root = Path(args.project_root)
    chapter_num = args.chapter
    model_key = args.model_key

    # Resolve alias
    resolved_key = MODEL_ALIASES.get(model_key, model_key)
    if resolved_key not in MODELS:
        print(json.dumps({"error": f"Unknown model: {model_key} (resolved: {resolved_key})"}))
        sys.exit(1)

    model_config = MODELS[resolved_key]

    # 优先使用预加载数据（all-models 模式由调用方预加载，避免重复IO）
    context_data = getattr(args, '_preloaded_context', None)
    chapter_text = getattr(args, '_preloaded_chapter_text', None)

    if context_data is None:
        # Round 21.0 · 2026-04-28 · Ch15 RCA H32 根治：单模型路径同样禁止 disk fallback stub
        context_file = project_root / ".webnovel" / "tmp" / f"external_context_ch{chapter_num:04d}.json"
        if not context_file.exists():
            print(json.dumps({
                "error": f"external_context_ch{chapter_num:04d}.json 不存在",
                "remediation": [
                    f"先运行: python -X utf8 scripts/build_external_context.py --project-root \"{project_root}\" --chapter {chapter_num}",
                    "Round 21.0 H32: 禁止从空 context 启动外部审查"
                ]
            }, ensure_ascii=False), file=sys.stderr)
            sys.exit(1)
        ctx_size = context_file.stat().st_size
        try:
            context_data = json.loads(context_file.read_text(encoding="utf-8"))
        except Exception as e:
            print(json.dumps({"error": f"context 解析失败: {e}"}, ensure_ascii=False), file=sys.stderr)
            sys.exit(1)
        if ctx_size < 1024 or context_data.get("_auto_generated") is True:
            print(json.dumps({
                "error": f"context 是 disk fallback 占位 ({ctx_size} bytes)",
                "remediation": [f"先运行: python -X utf8 scripts/build_external_context.py --project-root \"{project_root}\" --chapter {chapter_num}"]
            }, ensure_ascii=False), file=sys.stderr)
            sys.exit(1)

    if chapter_text is None:
        chapters_dir = project_root / "正文"
        ch_files = list(chapters_dir.glob(f"第{chapter_num:04d}章*.md"))
        if not ch_files:
            print(json.dumps({"error": f"Chapter {chapter_num} not found"}))
            sys.exit(1)
        chapter_text = ch_files[0].read_text(encoding="utf-8")

    context_block = build_context_block(context_data, project_root=project_root, chapter_num=chapter_num)

    # Run dimensions with controlled concurrency (respect provider RPM)
    max_concurrent = getattr(args, 'max_concurrent', DEFAULT_MAX_CONCURRENT)
    results = {}
    all_issues = []
    scores = {}
    full_provider_chain = []
    total_prompt_tokens = 0
    total_completion_tokens = 0

    # Round 16/25 · 统一早停阈值（15 模型扁平化）：
    # 任一模型累计 N 个维度失败 → 该模型早停（节省 API 配额给其他 14 模型）  # Round 25 仍按"该模型外的其他 14"
    # 不再按 core/supplemental 区分 · 15 模型一视同仁
    # 维度并发降至 3 使排队维度可被 early_stop_event 拦截
    #
    # Round 20.x · 2026-04-27 · Ch14 RCA P0-1 修复：
    # 阈值 4 → 6（13 维度多容忍 2 次失败）
    # 根因：kimi-k2.5/k2.6 单 provider ark-coding 偶发 phantom score=0 空摘要，
    # 4 次 phantom 即早停 → core 3 中 kimi 连续 4 章 (Ch11-14) 缺失。
    # 阈值 6 给单 provider 模型留更多重试空间，同时对 13 维度模型仍能保留 7 个
    # 维度数据（避免一直跑无效 API 调用）。
    early_stop_event = threading.Event()
    total_dim_failures = 0
    EARLY_STOP_THRESHOLD = 6  # Round 20.x 提升（原 Round 16 = 4，Ch11-14 kimi 缺失血教训）
    dim_concurrent = min(max_concurrent, 3)

    with ThreadPoolExecutor(max_workers=dim_concurrent) as executor:
        futures = {}
        for dim_key, dim_cfg in DIMENSIONS.items():
            f = executor.submit(_call_dim_with_stop, early_stop_event,
                                api_keys, resolved_key, model_config,
                                dim_key, dim_cfg, chapter_text, context_block, chapter_num)
            futures[f] = dim_key

        for f in as_completed(futures):
            dim_key, parsed, model_name, provider, model_actual, routing_ok, usage, chain, elapsed, error = f.result()
            full_provider_chain.extend(chain)

            if parsed:
                dim_score = parsed.get("score", 0)
                dim_summary = parsed.get("summary", "")
                # 零分空摘要 = 幽灵成功（模型返回了合法JSON但内容为空）
                if dim_score == 0 and not dim_summary.strip():
                    total_dim_failures += 1
                    results[dim_key] = {"status": "failed", "error": "phantom_success_score0_empty"}
                    if total_dim_failures >= EARLY_STOP_THRESHOLD and early_stop_event and not early_stop_event.is_set():
                        early_stop_event.set()
                        print(f"[early-stop] {resolved_key} 累计{total_dim_failures}次失败（阈值{EARLY_STOP_THRESHOLD}），触发早停", file=sys.stderr)
                    continue
                dim_issues = parsed.get("issues") or []
                scores[dim_key] = dim_score
                # 2026-04-16 Round 10 · quote 幻觉检测
                # Ch1 <example-project> qwen 实测报告引用"妹妹那时候在外地读书，他在合肥加班"
                # 该句根本不在正文里——外部模型幻觉。把所有 quote 做文本存在性验证。
                #
                # Round 18 · 2026-04-24 · Ch10 P0-4 根治：
                # 部分模型（如 minimax-m2.7-hs@openclawroot）返回 issues=[null, null]
                # 列表里含 None 元素，对 None 做 issue["source_model"]=... 会抛
                # "'NoneType' object does not support item assignment"，导致整个模型失败。
                # 根治：过滤 None / 非 dict 元素。
                dim_issues = [it for it in dim_issues if isinstance(it, dict)]
                for issue in dim_issues:
                    issue["source_model"] = resolved_key
                    issue["source_dimension"] = dim_key
                    quote = issue.get("quote")
                    if isinstance(quote, str) and quote.strip():
                        # Round 12 RCA: style-aware quote verification.
                        # elision (A…B 式省略引用) 属于合法引用，不降级。
                        # 只有 style == "missing" 才按幻觉处理。
                        style = _verify_quote_style(quote, chapter_text)
                        verified = style != "missing"
                        issue["quote_verified"] = verified
                        issue["quote_style"] = style
                        if style == "elision":
                            issue["quote_elision_note"] = (
                                "quote 使用省略引用（head+tail 均在正文中），"
                                "保留原 severity 不降级"
                            )
                        elif not verified:
                            # 幻觉 quote → severity 降一档（critical→high→medium→low→info）
                            original_severity = issue.get("severity", "medium")
                            issue["original_severity"] = original_severity
                            issue["severity"] = _downgrade_severity(original_severity)
                            issue["quote_hallucination_note"] = (
                                f"quote '{quote[:30]}...' 不在正文中（可能模型幻觉），"
                                f"severity {original_severity}→{issue['severity']}"
                            )
                            issue["needs_human_verify"] = True
                all_issues.extend(dim_issues)
                if usage:
                    total_prompt_tokens += usage.get("prompt_tokens", 0)
                    total_completion_tokens += usage.get("completion_tokens", 0)
                results[dim_key] = {
                    "status": "ok",
                    "score": dim_score,
                    "issues": dim_issues,
                    "summary": dim_summary,
                    "model": model_name,
                    "model_actual": model_actual,
                    "provider": provider,
                    "routing_verified": routing_ok,
                    "elapsed_ms": elapsed,
                    "review_strategy": "split",
                }
            else:
                if error == "early_stop_skipped":
                    results[dim_key] = {"status": "skipped", "error": "early_stop_skipped"}
                else:
                    total_dim_failures += 1
                    results[dim_key] = {"status": "failed", "error": error}

                    # Round 16/25 · 统一早停（15 模型扁平化）：累计达阈值 → 设置 event，排队中的维度立即跳过
                    if total_dim_failures >= EARLY_STOP_THRESHOLD and early_stop_event and not early_stop_event.is_set():
                        early_stop_event.set()
                        print(f"[early-stop] {resolved_key} 累计{total_dim_failures}次失败（阈值{EARLY_STOP_THRESHOLD}），触发早停", file=sys.stderr)

    # Determine final provider (most common successful provider)
    successful_providers = [r["provider"] for r in results.values() if r.get("status") == "ok"]
    final_provider = max(set(successful_providers), key=successful_providers.count) if successful_providers else "none"

    # Determine model_actual deterministically: use first successful dimension by sorted key
    ok_dims = sorted(dim_key for dim_key, r in results.items() if r.get("status") == "ok")
    model_actual_final = results[ok_dims[0]].get("model_actual", "") if ok_dims else ""

    # Total elapsed
    total_elapsed = sum(r.get("elapsed_ms", 0) for r in results.values() if r.get("status") == "ok")

    # H3 fix: all([]) == True, so guard against empty successful list
    ok_results = [r for r in results.values() if r.get("status") == "ok"]
    routing_all_ok = all(r.get("routing_verified", False) for r in ok_results) if ok_results else False

    output = _build_model_output(
        resolved_key=resolved_key,
        model_config=model_config,
        chapter_num=chapter_num,
        results=results,
        all_issues=all_issues,
        full_provider_chain=full_provider_chain,
        final_provider=final_provider,
        model_actual_final=model_actual_final,
        routing_all_ok=routing_all_ok,
        total_elapsed=total_elapsed,
        total_prompt_tokens=total_prompt_tokens,
        total_completion_tokens=total_completion_tokens,
        review_strategy="split",
        strategy_fallback_reason=getattr(args, "_strategy_fallback_reason", None),
    )
    return _save_external_review_output(args, project_root, resolved_key, chapter_num, output)


def run_legacy_mode(args, api_keys):
    """Original combined 4-dimension mode for backward compatibility"""
    project_root = Path(args.project_root)
    chapter_num = args.chapter
    model_keys = [m.strip() for m in args.models.split(",")]

    chapters_dir = project_root / "正文"
    ch_files = list(chapters_dir.glob(f"第{chapter_num:04d}章*.md"))
    if not ch_files:
        print(json.dumps({"status": "error", "message": f"Chapter {chapter_num} not found"}))
        sys.exit(1)
    chapter_text = ch_files[0].read_text(encoding="utf-8")

    prompt = f"""你是专业网文审查编辑。四维度评分(0-100)，JSON输出。
{{"chapter":{chapter_num},"scores":{{"consistency":分,"continuity":分,"ooc":分,"reader_pull":分,"overall":综合}},"issues":[{{"severity":"critical/high/medium/low","dimension":"维度","description":"问题","suggestion":"建议"}}],"summary":"一句话"}}
正文：\n{chapter_text}"""

    results = {}
    for key in model_keys:
        resolved = MODEL_ALIASES.get(key, key)
        if resolved not in MODELS:
            continue
        mc = MODELS[resolved]
        parsed, name, provider, model_actual, routing_ok, usage, chain = try_provider_chain(
            api_keys, resolved, mc, "严格JSON输出", prompt, mc["timeout"]
        )
        if parsed:
            parsed["model"] = name
            parsed["provider"] = provider
            parsed["routing_verified"] = routing_ok
            results[key] = parsed
        else:
            results[key] = {"error": chain[-1]["result"] if chain else "no_providers"}

    out_path = project_root / ".webnovel" / "tmp" / f"external_review_ch{chapter_num:04d}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "success", "results": {k: v.get("scores", {}).get("overall", "?") for k, v in results.items()}}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--chapter", required=True, type=int)
    parser.add_argument("--mode", default="legacy", choices=["legacy", "dimensions"])
    parser.add_argument(
        "--model-key", default="all",
        help=(
            "For dimensions mode: any of the 15 model keys (qwen3.6-plus/gpt-5.5/"
            "gemini-3.1-pro/doubao-pro/doubao-seed-2.0-lite/glm-5/glm-5.1/glm-4.7/"
            "mimo-v2.5-pro/minimax-m2.7-hs/minimax-m2.5/deepseek-v3.2-thinking/"
            "kimi-k2.5/kimi-k2.6/deepseek-v4-flash) or legacy aliases (qwen-plus/kimi/glm/...) or "
            "'all' to run all 15 models (default: all)"
        ),
    )
    parser.add_argument("--models", default="qwen3.6-plus,kimi-k2.6,glm-5", help="For legacy mode: comma-separated")
    parser.add_argument("--max-concurrent", type=int, default=DEFAULT_MAX_CONCURRENT,
                        help=f"Max parallel dimension calls per model in split fallback (default: {DEFAULT_MAX_CONCURRENT})")
    parser.add_argument(
        "--dimension-strategy",
        choices=["auto", "combined", "split"],
        default="auto",
        help="Step 3.5 dimensions strategy: auto=combined first then split fallback; combined=one request/model; split=legacy 13 requests/model",
    )
    parser.add_argument(
        "--model-concurrent",
        type=int,
        default=4,
        help="Max models running concurrently when --model-key all (default: 4)",
    )
    parser.add_argument("--rpm-override", type=int, default=None,
                        help="Override provider RPM limit (default: use provider config)")
    parser.add_argument("--rpm-override-provider", default="ark-coding",
                        choices=list(PROVIDERS.keys()) + ["healwrap", "nextapi"],
                        help="Which provider --rpm-override applies to (default: ark-coding)")
    parser.add_argument(
        "--no-merge-partial",
        action="store_true",
        help="禁用 Round 15.3 的 rerun merge-partial 合并（默认启用 · 根治 Bug #5 rerun 覆盖 ok 维度）",
    )
    parser.add_argument(
        "--healthcheck",
        action="store_true",
        help="Round 20.x · Ch13 P1 根治：仅探测全部 15 模型可达性（每个模型发 1 个最小请求 / 'ping'），"
             "返回 health_report JSON。不触发 13 维度 review。用于 Step 3.5 调用前快速识别 outage 模型。",
    )
    args = parser.parse_args()

    # Apply RPM override if specified
    if args.rpm_override:
        ProviderRateLimiter.get(args.rpm_override_provider, rpm=args.rpm_override)

    api_keys = load_api_keys()
    if not api_keys:
        print(json.dumps({"error": "No API keys found. Check ~/.claude/webnovel-writer/.env"}))
        sys.exit(1)

    if args.healthcheck:
        run_healthcheck_mode(args, api_keys)
        return

    if args.mode == "dimensions":
        run_dimensions_mode(args, api_keys)
    else:
        run_legacy_mode(args, api_keys)


def run_healthcheck_mode(args, api_keys):
    """Round 20.x · Ch13 P1 根治：15 模型 healthcheck

    Why（Ch13 血教训）：
        gpt-5.4 14 维度全 http_403（账户/key 失效），每章浪费 5+ 秒跑必定失败
        的请求。SKILL 的 Step 3.5 流程提到 X6 healthcheck 但 CLI 不支持。

    实现：
        - 对 MODELS 中每个 model_key 发一个最小 prompt（约 20 token）
        - 用 `--max-tokens 8` 限制输出（节省成本）
        - 30s 超时（GLM-5.1 等 reasoning 模型 8s 探针会误报）
        - 返回 JSON：{model_key: {ok: bool, latency_ms: int, provider: str, error: str|None}}
        - 输出到 stdout + .webnovel/tmp/external_healthcheck_{ts}.json
    """
    import time
    from concurrent.futures import ThreadPoolExecutor

    from pathlib import Path as _Path

    project_root = _Path(args.project_root).resolve()
    tmp_dir = project_root / ".webnovel" / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    ping_prompt = "请回复一个字'好'。仅一个字，不解释。"
    ping_messages = [
        {"role": "system", "content": "你是健康检查响应器。"},
        {"role": "user", "content": ping_prompt},
    ]

    def _check_one(model_key):
        spec = MODELS.get(model_key)
        if not spec:
            return model_key, {"ok": False, "error": "unknown_model_key", "latency_ms": 0, "provider": ""}
        start = time.time()
        last_err = ""
        for prov in spec.get("providers", []):
            provider_name = prov["provider"]
            try:
                # 复用最小 prompt，但给 reasoning 模型足够首包时间，避免健康检查误报
                # 不同实现可能函数名不同；这里采用通用 try-except
                resp = _call_provider_simple(
                    provider_name=provider_name,
                    model_id=prov["id"],
                    messages=ping_messages,
                    api_keys=api_keys,
                    timeout=DEFAULT_HEALTHCHECK_TIMEOUT,
                    max_tokens=8,
                )
                if resp:
                    return model_key, {
                        "ok": True,
                        "latency_ms": int((time.time() - start) * 1000),
                        "provider": provider_name,
                        "model_actual": prov.get("name", prov["id"]),
                        "error": None,
                    }
            except Exception as e:
                last_err = f"{provider_name}: {type(e).__name__}: {str(e)[:120]}"
                continue
        return model_key, {
            "ok": False,
            "latency_ms": int((time.time() - start) * 1000),
            "provider": "",
            "error": last_err or "all_providers_failed",
        }

    all_keys = list(MODELS.keys())
    print(f"[healthcheck] probing {len(all_keys)} models...", file=sys.stderr)
    results = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        for mk, res in ex.map(_check_one, all_keys):
            results[mk] = res

    healthy = [k for k, v in results.items() if v["ok"]]
    unhealthy = [k for k, v in results.items() if not v["ok"]]
    summary = {
        "total": len(all_keys),
        "healthy": len(healthy),
        "unhealthy": len(unhealthy),
        "healthy_models": healthy,
        "unhealthy_models": unhealthy,
        "details": results,
        "ts": int(time.time()),
    }
    out_path = tmp_dir / f"external_healthcheck_{summary['ts']}.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if len(healthy) < 10:
        sys.exit(2)  # warning level
    sys.exit(0)


def _call_provider_simple(*, provider_name, model_id, messages, api_keys, timeout, max_tokens):
    """healthcheck 专用最小调用包装。复用现有 provider call 路径，
    避开 dimension prompt 大模板。失败抛异常。"""
    # 尝试直接用 requests 走 OpenAI-compatible /chat/completions
    # （PROVIDERS 字典含 base_url + key 名）
    import requests as _requests

    prov = PROVIDERS.get(provider_name)
    if not prov:
        raise RuntimeError(f"unknown_provider:{provider_name}")
    base_url = prov.get("base_url", "")
    api_key = ""
    if isinstance(api_keys, dict):
        api_key = api_keys.get(provider_name, "")
    if not api_key:
        raise RuntimeError(f"no_api_key_for:{provider_name}")
    # Round 20.8 · Ch15 RCA:
    # PROVIDERS[*].base_url already points to the chat/completions endpoint.
    # The old healthcheck appended "/chat/completions" again and also fell back
    # to the first provider key, causing 14/14 false-negative probes.
    url = base_url.rstrip("/")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model_id, "messages": messages, "max_tokens": max_tokens, "temperature": 0.0}
    r = _requests.post(url, json=payload, headers=headers, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"http_{r.status_code}")
    data = r.json()
    return data.get("choices", [{}])[0].get("message", {}).get("content", "") or "ok"


if __name__ == "__main__":
    main()
