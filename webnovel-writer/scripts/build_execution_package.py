#!/usr/bin/env python3
"""
创作执行包持久化助手脚本 — context-agent Step 7 使用

目标：让 context-agent 不需要在 prompt 里构造复杂 Python 字面量。Agent 只
生成三段 JSON（task_brief / context_contract / step_2a_write_prompt），通过
stdin 传给本脚本，由脚本负责：
    1. 拼装完整执行包 pkg 对象
    2. 三段非空校验（schema 最小保证）
    3. 落盘 .webnovel/context/ch{NNNN}_context.json + .md
    4. 返回成功/失败到 stdout/stderr

用法：

    python -X utf8 {SCRIPTS_DIR}/build_execution_package.py \
        --chapter 3 \
        --project-root /path/to/project \
        --chapter-title "账册空白的第一页和陆沉" \
        --narrative-version v3 \
        --word-count-target "2400-3200" \
        --is-transition-chapter false \
        < input.json

或通过 heredoc：

    python ... build_execution_package.py --chapter 3 --project-root . \
        --chapter-title "xxx" --narrative-version v3 --word-count-target 2400-3200 \
        --is-transition-chapter false <<'JSON_IN'
    {"task_brief": {...}, "context_contract": {...}, "step_2a_write_prompt": {...}}
    JSON_IN

退出码：
    0  落盘成功
    1  参数错误
    2  输入 JSON 解析失败
    3  三段 schema 校验失败
    4  落盘 IO 失败
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


REQUIRED_SECTIONS = ("task_brief", "context_contract", "step_2a_write_prompt")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--chapter", type=int, required=True)
    p.add_argument("--project-root", type=str, required=True)
    p.add_argument("--chapter-title", type=str, required=True)
    p.add_argument("--narrative-version", type=str, default="v3")
    p.add_argument("--word-count-target", type=str, default="2400-3200")
    p.add_argument("--is-transition-chapter", type=str, default="false", choices=["true", "false"])
    p.add_argument("--context-agent-version", type=str, default="v3")
    p.add_argument("--input", type=str, default="-", help="JSON input path, default stdin")
    return p.parse_args()


def load_input(path: str) -> dict:
    try:
        if path == "-":
            raw = sys.stdin.read()
        else:
            raw = Path(path).read_text(encoding="utf-8")
        if not raw.strip():
            print("[FAIL] stdin/input 为空", file=sys.stderr)
            sys.exit(2)
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"[FAIL] JSON 解析失败: {exc}", file=sys.stderr)
        sys.exit(2)
    except OSError as exc:
        print(f"[FAIL] 读取输入失败: {exc}", file=sys.stderr)
        sys.exit(2)


def validate_sections(sections: dict) -> list[str]:
    errors = []
    for key in REQUIRED_SECTIONS:
        if key not in sections:
            errors.append(f"缺段落: {key}")
            continue
        v = sections[key]
        if not isinstance(v, dict):
            errors.append(f"{key} 必须是 object，得到 {type(v).__name__}")
            continue
        if not v:
            errors.append(f"{key} 为空对象")
    return errors


def render_markdown(pkg: dict) -> str:
    chapter = pkg["chapter"]
    lines = [
        f"# 第 {chapter} 章 · 创作执行包",
        "",
        f"> 章节：Ch{chapter:04d}《{pkg.get('chapter_title', '')}》",
        f"> 版本：{pkg.get('narrative_version', 'v3')}",
        f"> 字数目标：{pkg.get('word_count_target', '')}",
        f"> 生成时间：{pkg.get('generated_at', '')}",
        "",
        "---",
        "",
        "## 第一层 · 任务书",
        "",
        "```json",
        json.dumps(pkg["task_brief"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## 第二层 · Context Contract",
        "",
        "```json",
        json.dumps(pkg["context_contract"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## 第三层 · Step 2A 直写提示词",
        "",
        "```json",
        json.dumps(pkg["step_2a_write_prompt"], ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    if pkg.get("quality_feedback"):
        lines += [
            "## 附录 · 质量反馈注入",
            "",
            "```json",
            json.dumps(pkg["quality_feedback"], ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    return "\n".join(lines)


def main():
    args = parse_args()

    project_root = Path(args.project_root).resolve()
    if not (project_root / ".webnovel").exists():
        print(f"[FAIL] {project_root} 下无 .webnovel 目录", file=sys.stderr)
        sys.exit(1)

    sections = load_input(args.input)
    errs = validate_sections(sections)
    if errs:
        print("[FAIL] 三段 schema 校验失败：", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(3)

    pkg = {
        "chapter": args.chapter,
        "chapter_title": args.chapter_title,
        "project_root": str(project_root),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "context_agent_version": args.context_agent_version,
        "narrative_version": args.narrative_version,
        "word_count_target": args.word_count_target,
        "is_transition_chapter": args.is_transition_chapter == "true",
        "task_brief": sections["task_brief"],
        "context_contract": sections["context_contract"],
        "step_2a_write_prompt": sections["step_2a_write_prompt"],
        "quality_feedback": sections.get("quality_feedback", {
            "recurring_issues": [],
            "avoidance_notes": [],
            "success_reference": None,
            "style_anchor": "",
        }),
    }

    ctx_dir = project_root / ".webnovel" / "context"
    try:
        ctx_dir.mkdir(parents=True, exist_ok=True)
        json_path = ctx_dir / f"ch{args.chapter:04d}_context.json"
        md_path = ctx_dir / f"ch{args.chapter:04d}_context.md"
        json_path.write_text(
            json.dumps(pkg, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        md_path.write_text(render_markdown(pkg), encoding="utf-8", newline="\n")
    except OSError as exc:
        print(f"[FAIL] 落盘失败: {exc}", file=sys.stderr)
        sys.exit(4)

    # Sanity post-check: files exist and non-empty, 3 sections non-empty in disk JSON
    for p in (json_path, md_path):
        if not p.exists() or p.stat().st_size == 0:
            print(f"[FAIL] post-check: {p} 不存在或为空", file=sys.stderr)
            sys.exit(4)
    reread = json.loads(json_path.read_text(encoding="utf-8"))
    for key in REQUIRED_SECTIONS:
        if not reread.get(key):
            print(f"[FAIL] post-check: 回读 {key} 为空", file=sys.stderr)
            sys.exit(4)

    print(f"[OK] 执行包已落盘: {json_path} ({json_path.stat().st_size} bytes)")
    print(f"[OK] Markdown: {md_path} ({md_path.stat().st_size} bytes)")
    print(f"[OK] Sections: {', '.join(REQUIRED_SECTIONS)} 全部非空")
    return 0


if __name__ == "__main__":
    sys.exit(main())
