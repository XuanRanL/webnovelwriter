"""
Step 3.5 External Model Review Script
Supports two modes:
  - legacy: single prompt, 4-dimension combined review (backward compatible)
  - dimensions: 6 separate dimension prompts, concurrent API calls
Primary: codexcc, Fallback: SiliconFlow
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
    "codexcc": {
        "base_url": "https://api.codexcc.top/v1/chat/completions",
        "env_key_names": ["CODEXCC_API_KEY"],
    },
    "siliconflow": {
        "base_url": "https://api.siliconflow.cn/v1/chat/completions",
        "env_key_names": ["EMBED_API_KEY", "EMBEDDING_API_KEY", "SILICONFLOW_API_KEY"],
    },
}

MODELS = {
    "qwen": {
        "primary": {"provider": "codexcc", "id": "qwen3.5-plus", "name": "Qwen3.5-Plus"},
        "fallback": {"provider": "siliconflow", "id": "Qwen/Qwen3.5-397B-A17B", "name": "Qwen3.5-397B"},
        "timeout": 300,
    },
    "kimi": {
        "primary": {"provider": "codexcc", "id": "kimi-k2.5", "name": "Kimi-K2.5"},
        "fallback": {"provider": "siliconflow", "id": "Pro/moonshotai/Kimi-K2.5", "name": "Kimi-K2.5-SF"},
        "timeout": 300,
    },
    "glm": {
        "primary": {"provider": "codexcc", "id": "glm-5", "name": "GLM-5"},
        "fallback": {"provider": "siliconflow", "id": "Pro/zai-org/GLM-5", "name": "GLM-5-SF"},
        "timeout": 300,
    },
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


def load_api_keys():
    env_paths = [Path.home() / ".claude" / "webnovel-writer" / ".env"]
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
                            keys[pname] = line.split("=", 1)[1].strip().strip('"').strip("'")
    return keys


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
    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(base_url, headers=headers, json=payload, timeout=timeout)
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"], None
            elif resp.status_code == 429:
                time.sleep(10 * (attempt + 1))
            else:
                err = f"HTTP {resp.status_code}: {resp.text[:200]}"
                if attempt < max_retries:
                    time.sleep(5)
                else:
                    return None, err
        except requests.exceptions.Timeout:
            if attempt < max_retries:
                time.sleep(5)
            else:
                return None, "Timeout"
        except Exception as e:
            if attempt < max_retries:
                time.sleep(5)
            else:
                return None, str(e)
    return None, "Max retries"


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


def try_provider(api_keys, provider_cfg, system_msg, user_msg, timeout, max_attempts=2):
    provider = provider_cfg["provider"]
    if provider not in api_keys:
        return None, None, "no_api_key"
    base_url = PROVIDERS[provider]["base_url"]
    for _ in range(max_attempts):
        raw, error = call_api(base_url, api_keys[provider], provider_cfg["id"], system_msg, user_msg, timeout)
        if error:
            continue
        if raw:
            parsed = extract_json(raw)
            if parsed:
                return parsed, provider_cfg["name"], None
    return None, provider_cfg["name"], error or "parse_fail"


def call_dimension(api_keys, model_config, dim_key, dim_cfg, chapter_text, context_block, chapter_num):
    timeout = model_config["timeout"]
    novel_header = f"## 小说信息\n章节号：第{chapter_num}章\n\n"
    user_msg = novel_header + dim_cfg["prompt"].replace("{chapter_text}", chapter_text).replace("{context_block}", context_block)
    system_msg = dim_cfg["system"]

    parsed, model_name, error = try_provider(api_keys, model_config["primary"], system_msg, user_msg, timeout)
    if parsed:
        return dim_key, parsed, model_name, model_config["primary"]["provider"], None

    parsed, model_name, error = try_provider(api_keys, model_config["fallback"], system_msg, user_msg, timeout)
    if parsed:
        return dim_key, parsed, model_name, model_config["fallback"]["provider"], None

    return dim_key, None, model_name or "none", "none", error


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

    if model_key not in MODELS:
        print(json.dumps({"error": f"Unknown model: {model_key}"}))
        sys.exit(1)

    model_config = MODELS[model_key]

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

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {}
        for dim_key, dim_cfg in DIMENSIONS.items():
            f = executor.submit(call_dimension, api_keys, model_config, dim_key, dim_cfg, chapter_text, context_block, chapter_num)
            futures[f] = dim_key

        for f in as_completed(futures):
            dim_key, parsed, model_name, provider, error = f.result()
            if parsed:
                dim_score = parsed.get("score", 0)
                dim_issues = parsed.get("issues", [])
                scores[dim_key] = dim_score
                for issue in dim_issues:
                    issue["source_model"] = model_key
                    issue["source_dimension"] = dim_key
                all_issues.extend(dim_issues)
                results[dim_key] = {
                    "status": "ok",
                    "score": dim_score,
                    "issues": dim_issues,
                    "summary": parsed.get("summary", ""),
                    "model": model_name,
                    "provider": provider,
                }
            else:
                results[dim_key] = {"status": "failed", "error": error}

    # Calculate overall
    valid_scores = [s for s in scores.values() if isinstance(s, (int, float))]
    overall = round(sum(valid_scores) / len(valid_scores), 1) if valid_scores else 0

    output = {
        "agent": f"external-{model_key}",
        "chapter": chapter_num,
        "model_key": model_key,
        "model_name": model_config["primary"]["name"],
        "overall_score": overall,
        "pass": overall >= 60,
        "dimension_reports": results,
        "issues": all_issues,
        "metrics": {
            "dimensions_ok": sum(1 for r in results.values() if r.get("status") == "ok"),
            "dimensions_failed": sum(1 for r in results.values() if r.get("status") == "failed"),
            "total_issues": len(all_issues),
        },
        "summary": f"{model_key} 6维度审查完成，{len(valid_scores)}/6成功，综合{overall}分，{len(all_issues)}个问题",
    }

    # Save
    out_path = project_root / ".webnovel" / "tmp" / f"external_review_{model_key}_ch{chapter_num:04d}.json"
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
        if key not in MODELS:
            continue
        mc = MODELS[key]
        parsed, name, error = try_provider(api_keys, mc["primary"], "严格JSON输出", prompt, mc["timeout"])
        if not parsed:
            parsed, name, error = try_provider(api_keys, mc["fallback"], "严格JSON输出", prompt, mc["timeout"])
        if parsed:
            parsed["model"] = name
            results[key] = parsed
        else:
            results[key] = {"error": error}

    out_path = project_root / ".webnovel" / "tmp" / f"external_review_ch{chapter_num:04d}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "success", "results": {k: v.get("scores", {}).get("overall", "?") for k, v in results.items()}}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--chapter", required=True, type=int)
    parser.add_argument("--mode", default="legacy", choices=["legacy", "dimensions"])
    parser.add_argument("--model-key", default="qwen", help="For dimensions mode: qwen/kimi/glm")
    parser.add_argument("--models", default="qwen,kimi,glm", help="For legacy mode: comma-separated")
    args = parser.parse_args()

    api_keys = load_api_keys()
    if not api_keys:
        print(json.dumps({"error": "No API keys found"}))
        sys.exit(1)

    if args.mode == "dimensions":
        run_dimensions_mode(args, api_keys)
    else:
        run_legacy_mode(args, api_keys)


if __name__ == "__main__":
    main()
