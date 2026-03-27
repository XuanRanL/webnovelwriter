"""
Step 3.5 External Model Review Script
Calls Qwen3.5-397B and GLM-5 via SiliconFlow API for independent chapter review.
"""
import json
import time
import sys
import argparse
import requests
from pathlib import Path


# Model configurations
MODELS = {
    "qwen": {
        "id": "Qwen/Qwen3.5-397B-A17B",
        "name": "Qwen3.5-397B",
        "timeout": 300,
    },
    "glm5": {
        "id": "Pro/zai-org/GLM-5",
        "name": "GLM-5",
        "timeout": 300,
    },
}

BASE_URL = "https://api.siliconflow.cn/v1/chat/completions"


def load_api_key():
    """Load API key from .env file"""
    env_paths = [
        Path.home() / ".claude" / "webnovel-writer" / ".env",
    ]
    key_names = ["EMBED_API_KEY", "EMBEDDING_API_KEY", "SILICONFLOW_API_KEY"]
    for env_path in env_paths:
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                for key_name in key_names:
                    if line.startswith(f"{key_name}="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
    print("ERROR: No API key found in .env files", file=sys.stderr)
    sys.exit(1)


def read_chapter(project_root, chapter_num):
    """Read chapter file"""
    chapters_dir = Path(project_root) / "正文"
    files = list(chapters_dir.glob(f"第{chapter_num:04d}章*.md"))
    if not files:
        return None, None
    return files[0].read_text(encoding="utf-8"), files[0].name


def read_context(project_root, chapter_num):
    """Read summaries of previous chapters for context"""
    summaries = []
    summaries_dir = Path(project_root) / ".webnovel" / "summaries"
    for prev in range(max(1, chapter_num - 2), chapter_num):
        summary_file = summaries_dir / f"ch{prev:04d}.md"
        if summary_file.exists():
            summaries.append(f"--- 第{prev}章摘要 ---\n{summary_file.read_text(encoding='utf-8')}")
    return "\n\n".join(summaries) if summaries else "无前序章节摘要"


def read_novel_info(project_root):
    """Read novel info from state.json"""
    state_file = Path(project_root) / ".webnovel" / "state.json"
    if state_file.exists():
        state = json.loads(state_file.read_text(encoding="utf-8"))
        project = state.get("project", {})
        title = project.get("title", "未知")
        genre = project.get("genre", "未知")
        protagonist = state.get("protagonist_state", {})
        return {
            "title": title,
            "genre": genre,
            "protagonist": protagonist,
        }
    return {"title": "未知", "genre": "未知", "protagonist": {}}


def build_review_prompt(chapter_text, chapter_num, novel_info, context):
    """Build the review prompt"""
    return f"""你是一个专业的网文审查编辑。请对以下章节进行严格的质量审查，从以下四个维度评分（0-100），并指出具体问题。

## 审查维度

### 1. 设定一致性 (Consistency)
- 战力/能力是否合理
- 地点/角色是否前后一致
- 时间线是否有矛盾

### 2. 连贯性 (Continuity)
- 场景过渡是否流畅
- 情节线是否连贯（无遗忘/突兀）
- 伏笔管理是否到位
- 逻辑是否有漏洞

### 3. 人物塑造 (Character/OOC)
- 角色行为是否符合人设
- 对话风格是否一致
- 角色成长是否合理

### 4. 追读力 (Reader Pull)
- 章末是否有钩子让读者想看下一章
- 是否有微爽点/满足感
- 节奏是否合理

## 输出格式

请严格按以下JSON格式输出（不要输出其他内容）：

```json
{{
  "chapter": {chapter_num},
  "scores": {{
    "consistency": 分数,
    "continuity": 分数,
    "ooc": 分数,
    "reader_pull": 分数,
    "overall": 综合分数
  }},
  "issues": [
    {{
      "severity": "critical/high/medium/low",
      "dimension": "维度名",
      "location": "位置描述",
      "description": "问题描述",
      "suggestion": "修复建议"
    }}
  ],
  "strengths": ["优点1", "优点2"],
  "summary": "一句话总结"
}}
```

## 背景信息

小说：《{novel_info['title']}》，{novel_info['genre']}题材
章节号：第{chapter_num}章

## 前序章节摘要

{context}

## 本章正文

{chapter_text}
"""


def call_model(api_key, model_config, prompt, max_retries=2):
    """Call SiliconFlow API"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_config["id"],
        "messages": [
            {"role": "system", "content": "你是一个专业的网文质量审查编辑，请严格按要求输出JSON格式的审查报告。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
    }

    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(
                BASE_URL, headers=headers, json=payload,
                timeout=model_config["timeout"]
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return content, None
            elif resp.status_code == 429:
                wait = 10 * (attempt + 1)
                time.sleep(wait)
            else:
                err = f"API error {resp.status_code}: {resp.text[:200]}"
                if attempt < max_retries:
                    time.sleep(5)
                else:
                    return None, err
        except requests.exceptions.Timeout:
            if attempt < max_retries:
                time.sleep(5)
            else:
                return None, f"Timeout after {model_config['timeout']}s"
        except Exception as e:
            if attempt < max_retries:
                time.sleep(5)
            else:
                return None, str(e)

    return None, "Max retries exceeded"


def extract_json(text):
    """Extract JSON from response text"""
    if not text:
        return None
    import re
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None


def main():
    parser = argparse.ArgumentParser(description="External model review for webnovel chapters")
    parser.add_argument("--project-root", required=True, help="Project root directory")
    parser.add_argument("--chapter", required=True, type=int, help="Chapter number")
    parser.add_argument("--models", default="qwen,glm5", help="Comma-separated model keys")
    args = parser.parse_args()

    api_key = load_api_key()
    project_root = Path(args.project_root)
    chapter_num = args.chapter
    model_keys = [m.strip() for m in args.models.split(",")]

    # Read chapter
    chapter_text, chapter_file = read_chapter(project_root, chapter_num)
    if not chapter_text:
        print(json.dumps({"status": "error", "message": f"Chapter {chapter_num} not found"}))
        sys.exit(1)

    # Read context
    context = read_context(project_root, chapter_num)
    novel_info = read_novel_info(project_root)

    # Build prompt
    prompt = build_review_prompt(chapter_text, chapter_num, novel_info, context)

    # Call models
    results = {}
    for key in model_keys:
        if key not in MODELS:
            results[key] = {"error": f"Unknown model: {key}"}
            continue

        model_config = MODELS[key]
        start = time.time()
        raw, error = call_model(api_key, model_config, prompt)
        elapsed = time.time() - start

        if error:
            results[key] = {
                "model": model_config["name"],
                "error": error,
                "elapsed": round(elapsed, 1),
            }
        elif raw:
            parsed = extract_json(raw)
            if parsed:
                parsed["model"] = model_config["name"]
                parsed["elapsed"] = round(elapsed, 1)
                results[key] = parsed
            else:
                results[key] = {
                    "model": model_config["name"],
                    "error": "json_parse_fail",
                    "raw_preview": raw[:300],
                    "elapsed": round(elapsed, 1),
                }
        else:
            results[key] = {
                "model": model_config["name"],
                "error": "no_response",
                "elapsed": round(elapsed, 1),
            }

        # Rate limit buffer between models
        if key != model_keys[-1]:
            time.sleep(2)

    # Save results
    out_path = project_root / ".webnovel" / "tmp" / f"external_review_ch{chapter_num:04d}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Print summary
    output = {
        "status": "success",
        "chapter": chapter_num,
        "results": {},
        "output_file": str(out_path),
    }
    for key, data in results.items():
        if "error" in data:
            output["results"][key] = {"status": "error", "error": data["error"]}
        else:
            scores = data.get("scores", {})
            issues = data.get("issues", [])
            output["results"][key] = {
                "status": "ok",
                "model": data.get("model", key),
                "overall_score": scores.get("overall", "?"),
                "issue_count": len(issues),
                "elapsed": data.get("elapsed", 0),
            }

    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
