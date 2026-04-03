"""
Step 3.5 External Model Review Script
Supports two modes:
  - legacy: single prompt, 4-dimension combined review (backward compatible)
  - dimensions: 10 separate dimension prompts, concurrent API calls
Four-tier fallback: nextapi (primary) → healwrap (secondary) → codexcc (backup) → siliconflow (fallback)
Nine-model architecture: 3 core (kimi/glm/qwen-plus) + 6 supplemental (qwen/deepseek/minimax/doubao/glm4/minimax-m2.7)
"""
import json
import time
import sys
import argparse
import re
import threading
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

PROVIDERS = {
    "nextapi": {
        "base_url": "https://api.nextapi.store/v1/chat/completions",
        "env_key_names": ["NEXTAPI_API_KEY"],
        "rpm": 999,  # 无限制
    },
    "healwrap": {
        "base_url": "https://llm-api.healwrap.cn/v1/chat/completions",
        "env_key_names": ["HEALWRAP_API_KEY"],
        "rpm": 10,
    },
    "codexcc": {
        "base_url": "https://api.codexcc.top/v1/chat/completions",
        "env_key_names": ["CODEXCC_API_KEY"],
        "rpm": 30,
    },
    "siliconflow": {
        "base_url": "https://api.siliconflow.cn/v1/chat/completions",
        "env_key_names": ["EMBED_API_KEY", "EMBEDDING_API_KEY", "SILICONFLOW_API_KEY"],
        "rpm": 30,
    },
}

# Default concurrency: max dimensions running in parallel per model
# RPM=10 由 ProviderRateLimiter 强制执行，这里只控制线程数
DEFAULT_MAX_CONCURRENT = 10


class ProviderRateLimiter:
    """Thread-safe token-bucket rate limiter, one instance per provider.

    Ensures that across all threads, requests to a given provider
    respect its RPM (requests per minute) limit.
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
        self.min_interval = 60.0 / rpm  # seconds between requests
        self._timestamps = []           # recent request timestamps
        self._sem_lock = threading.Lock()

    def acquire(self):
        """Block until it's safe to make the next request."""
        while True:
            sleep_time = self._try_acquire()
            if sleep_time == 0:
                return
            time.sleep(sleep_time)

    def _try_acquire(self):
        """Try to acquire a slot. Returns 0 if acquired, or seconds to sleep."""
        with self._sem_lock:
            now = time.time()
            # Purge timestamps older than 60s
            self._timestamps = [t for t in self._timestamps if now - t < 60.0]
            if len(self._timestamps) >= self.rpm:
                # At RPM limit — must wait for oldest to expire
                return 60.0 - (now - self._timestamps[0]) + 0.1
            if self._timestamps:
                wait = self.min_interval - (now - self._timestamps[-1])
                if wait > 0:
                    return max(wait, 0.1)
            # Slot available — record and return
            self._timestamps.append(now)
            return 0

# Core models: must succeed, have full fallback chain
MODELS = {
    "qwen-plus": {
        "tier": "core",
        "role": "网文/爽点结构",
        "providers": [
            {"provider": "healwrap", "id": "qwen3.5-plus", "name": "Qwen3.5-Plus"},
            {"provider": "codexcc", "id": "qwen3.5-plus", "name": "Qwen3.5-Plus"},
            {"provider": "siliconflow", "id": "Qwen/Qwen3.5-397B-A17B", "name": "Qwen3.5-397B"},
        ],
        "timeout": 300,
    },
    "kimi": {
        "tier": "core",
        "role": "严审/逻辑设定",
        "providers": [
            {"provider": "nextapi", "id": "kimi-k2.5", "name": "Kimi-K2.5"},
            {"provider": "healwrap", "id": "kimi-k2.5", "name": "Kimi-K2.5"},
            {"provider": "codexcc", "id": "kimi-k2.5", "name": "Kimi-K2.5"},
            {"provider": "siliconflow", "id": "Pro/moonshotai/Kimi-K2.5", "name": "Kimi-K2.5-SF"},
        ],
        "timeout": 300,
    },
    "glm": {
        "tier": "core",
        "role": "编辑/读者感受",
        "providers": [
            {"provider": "nextapi", "id": "glm-5.0", "name": "GLM-5.0"},
            {"provider": "healwrap", "id": "glm-5", "name": "GLM-5"},
            {"provider": "codexcc", "id": "glm-5", "name": "GLM-5"},
            {"provider": "siliconflow", "id": "Pro/zai-org/GLM-5", "name": "GLM-5-SF"},
        ],
        "timeout": 300,
    },
    # Supplemental models: multi-provider fallback, failure doesn't block
    "qwen": {
        "tier": "supplemental",
        "role": "宽松锚点",
        "providers": [
            {"provider": "healwrap", "id": "qwen-3.5", "name": "Qwen-3.5"},
            {"provider": "siliconflow", "id": "Qwen/Qwen3.5-397B-A17B", "name": "Qwen3.5-397B-SF"},
        ],
        "timeout": 300,
    },
    "deepseek": {
        "tier": "supplemental",
        "role": "技术考据",
        "providers": [
            {"provider": "healwrap", "id": "deepseek-v3.2", "name": "DeepSeek-V3.2"},
            {"provider": "siliconflow", "id": "Pro/deepseek-ai/DeepSeek-V3.2", "name": "DeepSeek-V3.2-SF"},
        ],
        "timeout": 300,
    },
    "minimax": {
        "tier": "supplemental",
        "role": "快速参考",
        "providers": [
            {"provider": "nextapi", "id": "minimax-m2.5", "name": "MiniMax-M2.5"},
            {"provider": "healwrap", "id": "minimax-m2.5", "name": "MiniMax-M2.5"},
            {"provider": "codexcc", "id": "minimax-m2.5", "name": "MiniMax-M2.5"},
            {"provider": "siliconflow", "id": "Pro/MiniMaxAI/MiniMax-M2.5", "name": "MiniMax-M2.5-SF"},
        ],
        "timeout": 300,
    },
    "doubao": {
        "tier": "supplemental",
        "role": "结构审查/逻辑一致性",
        "providers": [
            {"provider": "healwrap", "id": "doubao-seed-2.0", "name": "Doubao-Seed-2.0"},
        ],
        "timeout": 300,
    },
    "glm4": {
        "tier": "supplemental",
        "role": "文学质感/角色声音",
        "providers": [
            {"provider": "healwrap", "id": "glm-4.7", "name": "GLM-4.7"},
            {"provider": "siliconflow", "id": "Pro/zai-org/GLM-4.7", "name": "GLM-4.7-SF"},
        ],
        "timeout": 300,
    },
    "minimax-m2.7": {
        "tier": "supplemental",
        "role": "对话/情感深度",
        "providers": [
            {"provider": "nextapi", "id": "minimax-m2.7", "name": "MiniMax-M2.7"},
            {"provider": "healwrap", "id": "minimax-m2.7", "name": "MiniMax-M2.7"},
            {"provider": "codexcc", "id": "MiniMax-M2.7", "name": "MiniMax-M2.7"},
        ],
        "timeout": 300,
    },
}

# Backward-compatible aliases for legacy --model-key usage
# NOTE: "qwen" is now a distinct supplemental model (qwen-3.5) in MODELS dict,
# so it must NOT be aliased to "qwen-plus". Only add aliases for truly retired keys.
MODEL_ALIASES = {}

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

{context_block}

严格按JSON输出：
{{"dimension":"prose_quality","score":0-100,"issues":[{{"id":"PQ_001","type":"PROSE_FLAT/PROSE_CLICHE/PROSE_WEAK_VERB","severity":"critical/high/medium/low","location":"位置","description":"问题","suggestion":"建议","quote":"引用正文原句"}}],"summary":"一句话总评"}}

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
{{"dimension":"emotion_expression","score":0-100,"issues":[{{"id":"EE_001","type":"EMOTION_TELL/EMOTION_JUMP/EMOTION_UNANCHORED","severity":"critical/high/medium/low","location":"位置","description":"问题","suggestion":"建议","quote":"引用正文原句"}}],"summary":"一句话总评"}}

评分标准：95-100出版级｜90-94优秀仅轻微瑕疵｜85-89良好少量可优化｜80-84合格若干需改进｜75-79及格有明显问题｜<75不合格有严重问题

## 本章正文
{chapter_text}"""
    },
}


# Known routing bugs for verification
ROUTING_BUGS = {
    "codexcc": {
        "glm": ["MiniMax"],       # codexcc returns MiniMax when GLM requested
        "kimi": ["qianfan"],      # codexcc returns qianfan when kimi requested
    }
}


def load_api_keys():
    env_paths = [
        Path.home() / ".claude" / "webnovel-writer" / ".env",
    ]
    # Also check project .env if WEBNOVEL_PROJECT_ROOT is set
    project_root = Path.cwd()
    project_env = project_root / ".env"
    if project_env.exists():
        env_paths.insert(0, project_env)

    keys = {}
    for env_path in env_paths:
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                for pname, pcfg in PROVIDERS.items():
                    for kname in pcfg["env_key_names"]:
                        if line.startswith(f"{kname}="):
                            val = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if pname not in keys:  # first found wins (project .env > global)
                                keys[pname] = val
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


def call_api(base_url, api_key, model_id, system_msg, user_msg, timeout=300, max_retries=2, provider_name=None):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.3,
        "max_tokens": 8192,
    }
    # Thinking models (qwen-3.5, deepseek-v3.2, doubao-seed-2.0, glm-4.7, etc.) wrap output in <think> tags,
    # consuming most of max_tokens on reasoning. Remove limit to let API use model max.
    # Thinking models (qwen-3.5, qwen3.5-plus, deepseek-v3.2, doubao-seed-2.0, glm-4.7):
    # - 需要更高 max_tokens（推理+输出共用 completion token 预算）
    # - enable_thinking 可靠激活 qwen-3.5 的 thinking，其余模型无害
    model_lower = model_id.lower()
    if any(t in model_lower for t in ("qwen-3", "qwen3", "deepseek", "doubao", "glm-4")):
        payload["max_tokens"] = 65536
        payload["enable_thinking"] = True
    # Acquire rate limiter before first request
    limiter = ProviderRateLimiter.get(provider_name) if provider_name else None
    provider_chain = []
    session = requests.Session()
    try:
        for attempt in range(max_retries + 1):
            if limiter:
                limiter.acquire()
            start_ts = time.time()
            try:
                resp = session.post(base_url, headers=headers, json=payload, timeout=timeout)
                elapsed = int((time.time() - start_ts) * 1000)
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
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
    # Priority 3: greedy fallback (last resort)
    m = re.search(r'\{[^{}]*\}', text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


def try_provider_chain(api_keys, model_key, model_config, system_msg, user_msg, timeout):
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
        # healwrap: 2 retries (3 total attempts); codexcc/siliconflow: 0 retries (1 attempt, fail-fast)
        max_retries = 2 if provider_name in ("healwrap", "nextapi") else 0

        raw, error, model_actual, usage, attempts = call_api(
            base_url, api_keys[provider_name], provider_cfg["id"],
            system_msg, user_msg, timeout, max_retries=max_retries,
            provider_name=provider_name
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
                if parsed.get("score", 0) == 0 and not str(parsed.get("summary", "")).strip():
                    full_chain.append({
                        "provider": provider_name,
                        "attempt": 0,
                        "result": "phantom_score0_retry",
                    })
                    print(f"[phantom] {model_key}@{provider_name}: score=0+空摘要，尝试下一供应商", file=sys.stderr)
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


def call_dimension(api_keys, model_key, model_config, dim_key, dim_cfg, chapter_text, context_block, chapter_num):
    timeout = model_config["timeout"]
    novel_header = f"## 小说信息\n章节号：第{chapter_num}章\n\n"
    user_msg = novel_header + dim_cfg["prompt"].replace("{chapter_text}", chapter_text).replace("{context_block}", context_block)
    system_msg = dim_cfg["system"]

    # Ch1-3 special handling: append extra evaluation criteria per spec
    if chapter_num <= 3:
        user_msg += "\n" + CH1_3_SPECIAL_PROMPT.format(chapter=chapter_num)

    start_ts = time.time()
    parsed, model_name, provider, model_actual, routing_ok, usage, chain = try_provider_chain(
        api_keys, model_key, model_config, system_msg, user_msg, timeout
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
            hook = meta.get("hook") or {}
            pattern = meta.get("pattern") or {}
            ending = meta.get("ending") or {}
            meta_lines.append(
                f"第{ch_key}章: 钩子={hook.get('type','?')}({hook.get('strength','?')}) "
                f"开场={pattern.get('opening','?')} 情绪={pattern.get('emotion_rhythm','?')} "
                f"结束情绪={ending.get('emotion','?')} 地点={ending.get('location','?')}"
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

    When used at the aggregation layer (across 8 models), the caller should
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


def run_dimensions_mode(args, api_keys):
    project_root = Path(args.project_root)
    chapter_num = args.chapter
    model_key = args.model_key

    # --model-key all: 并发执行全部模型（ProviderRateLimiter 自动控制 RPM）
    if model_key == "all":
        all_model_keys = list(MODELS.keys())
        print(f"[all-models] 并发执行 {len(all_model_keys)} 个模型: {', '.join(all_model_keys)}", file=sys.stderr)
        all_results = {}

        def _run_model_safe(mk):
            args_copy = argparse.Namespace(**vars(args))
            args_copy.model_key = mk
            try:
                print(f"[all-models] 开始: {mk} ({MODELS[mk]['tier']})", file=sys.stderr)
                _run_single_model(args_copy, api_keys)
                print(f"[all-models] 完成: {mk}", file=sys.stderr)
                return mk, "success"
            except SystemExit:
                print(f"[all-models] 失败: {mk}", file=sys.stderr)
                return mk, "failed"
            except Exception as e:
                print(f"[all-models] 异常: {mk} — {e}", file=sys.stderr)
                return mk, f"error: {str(e)[:80]}"

        with ThreadPoolExecutor(max_workers=len(all_model_keys)) as executor:
            futures = {executor.submit(_run_model_safe, mk): mk for mk in all_model_keys}
            for f in as_completed(futures):
                mk, result = f.result()
                all_results[mk] = result

        summary = {
            "mode": "all-models",
            "chapter": chapter_num,
            "total": len(all_model_keys),
            "success": sum(1 for v in all_results.values() if v == "success"),
            "failed": sum(1 for v in all_results.values() if v != "success"),
            "details": all_results,
        }
        print(json.dumps(summary, ensure_ascii=False))
        return

    _run_single_model(args, api_keys)


def _run_single_model(args, api_keys):
    """执行单个模型的10维度审查。"""
    project_root = Path(args.project_root)
    chapter_num = args.chapter
    model_key = args.model_key

    # Resolve alias
    resolved_key = MODEL_ALIASES.get(model_key, model_key)
    if resolved_key not in MODELS:
        print(json.dumps({"error": f"Unknown model: {model_key} (resolved: {resolved_key})"}))
        sys.exit(1)

    model_config = MODELS[resolved_key]

    # Load context
    context_file = project_root / ".webnovel" / "tmp" / f"external_context_ch{chapter_num:04d}.json"
    if context_file.exists():
        context_data = json.loads(context_file.read_text(encoding="utf-8"))
    else:
        print(json.dumps({"error": f"Context file not found: {context_file}. Agent must prepare context before calling script."}), file=sys.stderr)
        context_data = {}

    # Load chapter text
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

    # 补充层早停：累计 3 个维度失败后跳过排队中的剩余维度
    is_supplemental = model_config.get("tier") == "supplemental"
    early_stop_event = threading.Event() if is_supplemental else None
    total_dim_failures = 0
    EARLY_STOP_THRESHOLD = 3
    # 补充层降低维度并发（3），使排队中的 task 能被 early_stop_event 拦截
    # 核心层保持全并发
    dim_concurrent = min(max_concurrent, 3) if is_supplemental else max_concurrent

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
                    if is_supplemental and total_dim_failures >= EARLY_STOP_THRESHOLD and early_stop_event and not early_stop_event.is_set():
                        early_stop_event.set()
                        print(f"[early-stop] {resolved_key}（补充层）累计{total_dim_failures}次失败，触发早停", file=sys.stderr)
                    continue
                dim_issues = parsed.get("issues", [])
                scores[dim_key] = dim_score
                for issue in dim_issues:
                    issue["source_model"] = resolved_key
                    issue["source_dimension"] = dim_key
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
                }
            else:
                if error == "early_stop_skipped":
                    results[dim_key] = {"status": "skipped", "error": "early_stop_skipped"}
                else:
                    total_dim_failures += 1
                    results[dim_key] = {"status": "failed", "error": error}

                    # 补充层累计失败达阈值 → 设置 event，排队中的维度启动时立即跳过
                    if is_supplemental and total_dim_failures >= EARLY_STOP_THRESHOLD and early_stop_event and not early_stop_event.is_set():
                        early_stop_event.set()
                        print(f"[early-stop] {resolved_key}（补充层）累计{total_dim_failures}次失败，触发早停", file=sys.stderr)

    # Calculate overall
    valid_scores = [s for s in scores.values() if isinstance(s, (int, float))]
    overall = round(sum(valid_scores) / len(valid_scores), 1) if valid_scores else 0

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

    output = {
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
        "api_meta": {
            "final_provider": final_provider,
            "elapsed_ms": total_elapsed,
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "attempts_total": len(full_provider_chain),
        },
        "metrics": {
            "dimensions_ok": sum(1 for r in results.values() if r.get("status") == "ok"),
            "dimensions_failed": sum(1 for r in results.values() if r.get("status") == "failed"),
            "dimensions_skipped": sum(1 for r in results.values() if r.get("status") == "skipped"),
            "total_issues": len(all_issues),
        },
        "summary": f"{resolved_key} {len(DIMENSIONS)}维度审查完成，{len(valid_scores)}/{len(DIMENSIONS)}成功，综合{overall}分，{len(all_issues)}个问题",
    }

    # Save
    out_path = project_root / ".webnovel" / "tmp" / f"external_review_{resolved_key}_ch{chapter_num:04d}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(output, ensure_ascii=False))


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
    parser.add_argument("--model-key", default="qwen-plus", help="For dimensions mode: qwen-plus/kimi/glm/qwen/deepseek/minimax/doubao/glm4/minimax-m2.7 or 'all' for all 9 models")
    parser.add_argument("--models", default="qwen-plus,kimi,glm", help="For legacy mode: comma-separated")
    parser.add_argument("--max-concurrent", type=int, default=DEFAULT_MAX_CONCURRENT,
                        help=f"Max parallel dimension calls per model (default: {DEFAULT_MAX_CONCURRENT})")
    parser.add_argument("--rpm-override", type=int, default=None,
                        help="Override healwrap RPM limit (default: use provider config)")
    args = parser.parse_args()

    # Apply RPM override if specified
    if args.rpm_override:
        ProviderRateLimiter.get("healwrap", rpm=args.rpm_override)

    api_keys = load_api_keys()
    if not api_keys:
        print(json.dumps({"error": "No API keys found. Check ~/.claude/webnovel-writer/.env"}))
        sys.exit(1)

    if args.mode == "dimensions":
        run_dimensions_mode(args, api_keys)
    else:
        run_legacy_mode(args, api_keys)


if __name__ == "__main__":
    main()
