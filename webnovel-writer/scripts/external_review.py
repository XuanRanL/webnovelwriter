"""
Step 3.5 External Model Review Script
Supports two modes:
  - legacy: single prompt, 4-dimension combined review (backward compatible)
  - dimensions: 6 separate dimension prompts, concurrent API calls
Three-tier fallback: healwrap (primary) → codexcc (backup) → siliconflow (fallback)
Six-model architecture: 3 core (kimi/glm/qwen-plus) + 3 supplemental (qwen/deepseek/minimax)
"""
import json
import time
import sys
import argparse
import re
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

PROVIDERS = {
    "healwrap": {
        "base_url": "https://llm-api.healwrap.cn/v1/chat/completions",
        "env_key_names": ["HEALWRAP_API_KEY"],
    },
    "codexcc": {
        "base_url": "https://api.codexcc.top/v1/chat/completions",
        "env_key_names": ["CODEXCC_API_KEY"],
    },
    "siliconflow": {
        "base_url": "https://api.siliconflow.cn/v1/chat/completions",
        "env_key_names": ["EMBED_API_KEY", "EMBEDDING_API_KEY", "SILICONFLOW_API_KEY"],
    },
}

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
            {"provider": "healwrap", "id": "glm-5", "name": "GLM-5"},
            {"provider": "codexcc", "id": "glm-5", "name": "GLM-5"},
            {"provider": "siliconflow", "id": "Pro/zai-org/GLM-5", "name": "GLM-5-SF"},
        ],
        "timeout": 300,
    },
    # Supplemental models: healwrap only, failure doesn't block
    "qwen": {
        "tier": "supplemental",
        "role": "宽松锚点",
        "providers": [
            {"provider": "healwrap", "id": "qwen-3.5", "name": "Qwen-3.5"},
        ],
        "timeout": 300,
    },
    "deepseek": {
        "tier": "supplemental",
        "role": "技术考据",
        "providers": [
            {"provider": "healwrap", "id": "deepseek-v3.2", "name": "DeepSeek-V3.2"},
        ],
        "timeout": 300,
    },
    "minimax": {
        "tier": "supplemental",
        "role": "快速参考",
        "providers": [
            {"provider": "healwrap", "id": "minimax-m2.5", "name": "MiniMax-M2.5"},
        ],
        "timeout": 300,
    },
}

# Backward-compatible aliases for legacy --model-key usage
MODEL_ALIASES = {
    "qwen": "qwen-plus",  # legacy "qwen" maps to core qwen-plus
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
{{"dimension":"consistency","score":0-100,"issues":[{{"id":"CON_001","severity":"critical/high/medium/low","location":"位置","description":"问题","suggestion":"建议"}}],"summary":"一句话"}}

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
{{"dimension":"continuity","score":0-100,"issues":[{{"id":"CONT_001","severity":"critical/high/medium/low","location":"位置","description":"问题","suggestion":"建议"}}],"summary":"一句话"}}

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
{{"dimension":"ooc","score":0-100,"issues":[{{"id":"OOC_001","severity":"critical/high/medium/low","location":"位置","description":"问题","suggestion":"建议"}}],"summary":"一句话"}}

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
{{"dimension":"reader_pull","score":0-100,"issues":[{{"id":"RP_001","severity":"critical/high/medium/low","location":"位置","description":"问题","suggestion":"建议"}}],"summary":"一句话"}}

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
{{"dimension":"high_point","score":0-100,"issues":[{{"id":"HP_001","severity":"critical/high/medium/low","location":"位置","description":"问题","suggestion":"建议"}}],"summary":"一句话"}}

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
{{"dimension":"pacing","score":0-100,"issues":[{{"id":"PACE_001","severity":"critical/high/medium/low","location":"位置","description":"问题","suggestion":"建议"}}],"summary":"一句话"}}

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


def verify_routing(model_key, provider_name, response_model):
    """Check if the response model matches what was requested."""
    if not response_model:
        return False, "no_model_in_response"

    # Check known routing bugs
    if provider_name in ROUTING_BUGS:
        bugs = ROUTING_BUGS[provider_name].get(model_key, [])
        for bug_pattern in bugs:
            if bug_pattern.lower() in response_model.lower():
                return False, f"known_bug:{bug_pattern}_returned_for_{model_key}"

    return True, "ok"


def call_api(base_url, api_key, model_id, system_msg, user_msg, timeout=300, max_retries=2):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
    }
    provider_chain = []
    for attempt in range(max_retries + 1):
        start_ts = time.time()
        try:
            resp = requests.post(base_url, headers=headers, json=payload, timeout=timeout)
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
        except Exception as e:
            elapsed = int((time.time() - start_ts) * 1000)
            provider_chain.append({"attempt": attempt + 1, "result": str(e)[:100], "elapsed_ms": elapsed})
            if attempt < max_retries:
                time.sleep(5)
            else:
                return None, str(e), None, None, provider_chain
    return None, "Max retries", None, None, provider_chain


def extract_json(text):
    if not text:
        return None
    m = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    m = re.search(r'\{.*\}', text, re.DOTALL)
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
        max_attempts = 2 if provider_name == "healwrap" else 1

        raw, error, model_actual, usage, attempts = call_api(
            base_url, api_keys[provider_name], provider_cfg["id"],
            system_msg, user_msg, timeout, max_retries=max_attempts
        )

        for a in attempts:
            a["provider"] = provider_name
        full_chain.extend(attempts)

        if error:
            continue

        if raw:
            # Verify routing
            routing_ok, routing_reason = verify_routing(model_key, provider_name, model_actual)
            if not routing_ok:
                full_chain.append({
                    "provider": provider_name,
                    "attempt": 0,
                    "result": f"routing_failed:{routing_reason}",
                })
                continue  # Route mismatch -> try next provider

            parsed = extract_json(raw)
            if parsed:
                return parsed, provider_cfg["name"], provider_name, model_actual, routing_ok, usage, full_chain

    return None, None, "none", None, False, None, full_chain


def call_dimension(api_keys, model_key, model_config, dim_key, dim_cfg, chapter_text, context_block, chapter_num):
    timeout = model_config["timeout"]
    novel_header = f"## 小说信息\n章节号：第{chapter_num}章\n\n"
    user_msg = novel_header + dim_cfg["prompt"].replace("{chapter_text}", chapter_text).replace("{context_block}", context_block)
    system_msg = dim_cfg["system"]

    start_ts = time.time()
    parsed, model_name, provider, model_actual, routing_ok, usage, chain = try_provider_chain(
        api_keys, model_key, model_config, system_msg, user_msg, timeout
    )
    elapsed = int((time.time() - start_ts) * 1000)

    if parsed:
        return dim_key, parsed, model_name, provider, model_actual, routing_ok, usage, chain, elapsed, None

    last_error = chain[-1]["result"] if chain else "no_providers"
    return dim_key, None, model_name or "none", "none", None, False, None, chain, elapsed, last_error


def build_context_block(context_data):
    parts = ["## 审查上下文\n"]
    if not context_data:
        parts.append("**警告：无项目上下文，审查结果可能不准确**\n")
        return "\n".join(parts)
    if context_data.get("novel_info"):
        parts.append(f"### 小说基础信息\n{context_data['novel_info']}\n")
    if context_data.get("protagonist_state"):
        parts.append(f"### 主角当前状态\n{json.dumps(context_data['protagonist_state'], ensure_ascii=False, indent=2)}\n")
    if context_data.get("world_settings"):
        parts.append(f"### 世界观设定\n{context_data['world_settings']}\n")
    if context_data.get("power_system"):
        parts.append(f"### 力量体系\n{context_data['power_system']}\n")
    if context_data.get("protagonist_card"):
        parts.append(f"### 主角卡\n{context_data['protagonist_card']}\n")
    if context_data.get("outline_excerpt"):
        parts.append(f"### 本章大纲\n{context_data['outline_excerpt']}\n")
    if context_data.get("prev_summaries"):
        parts.append(f"### 前序章节摘要\n{context_data['prev_summaries']}\n")
    return "\n".join(parts)


def run_dimensions_mode(args, api_keys):
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

    context_block = build_context_block(context_data)

    # Run 6 dimensions concurrently
    results = {}
    all_issues = []
    scores = {}
    full_provider_chain = []
    total_prompt_tokens = 0
    total_completion_tokens = 0

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {}
        for dim_key, dim_cfg in DIMENSIONS.items():
            f = executor.submit(call_dimension, api_keys, resolved_key, model_config,
                                dim_key, dim_cfg, chapter_text, context_block, chapter_num)
            futures[f] = dim_key

        for f in as_completed(futures):
            dim_key, parsed, model_name, provider, model_actual, routing_ok, usage, chain, elapsed, error = f.result()
            full_provider_chain.extend(chain)

            if parsed:
                dim_score = parsed.get("score", 0)
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
                    "summary": parsed.get("summary", ""),
                    "model": model_name,
                    "model_actual": model_actual,
                    "provider": provider,
                    "routing_verified": routing_ok,
                    "elapsed_ms": elapsed,
                }
            else:
                results[dim_key] = {"status": "failed", "error": error}

    # Calculate overall
    valid_scores = [s for s in scores.values() if isinstance(s, (int, float))]
    overall = round(sum(valid_scores) / len(valid_scores), 1) if valid_scores else 0

    # Determine final provider (most common successful provider)
    successful_providers = [r["provider"] for r in results.values() if r.get("status") == "ok"]
    final_provider = max(set(successful_providers), key=successful_providers.count) if successful_providers else "none"

    # Total elapsed
    total_elapsed = sum(r.get("elapsed_ms", 0) for r in results.values() if r.get("status") == "ok")

    output = {
        "agent": f"external-{resolved_key}",
        "chapter": chapter_num,
        "model_key": resolved_key,
        "model_requested": model_config["providers"][0]["id"],
        "model_actual": results.get(list(results.keys())[0], {}).get("model_actual", ""),
        "provider": final_provider,
        "routing_verified": all(r.get("routing_verified", False) for r in results.values() if r.get("status") == "ok"),
        "overall_score": overall,
        "pass": overall >= 60,
        "dimension_reports": results,
        "issues": all_issues,
        "cross_validation": {
            "total_issues": len(all_issues),
            "verified": 0,
            "unverified": len(all_issues),
            "dismissed": 0,
        },
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
            "total_issues": len(all_issues),
        },
        "summary": f"{resolved_key} 6维度审查完成，{len(valid_scores)}/6成功，综合{overall}分，{len(all_issues)}个问题",
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
    parser.add_argument("--model-key", default="qwen-plus", help="For dimensions mode: qwen-plus/kimi/glm/qwen/deepseek/minimax")
    parser.add_argument("--models", default="qwen-plus,kimi,glm", help="For legacy mode: comma-separated")
    args = parser.parse_args()

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
