#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 3.5 外部审查 Context 构建脚本

背景：
  原本在 skills/webnovel-write/SKILL.md 里用内联 python -c 脚本构建，
  但 fork 版 SKILL.md 存在中文双重编码损坏问题，且内联脚本只加载 9 个字段，
  导致外部 9 个模型"盲评"——不知道作者要求的克制风格、情感蓝图、典故规划。

  本脚本是一个干净的 UTF-8 文件，加载完整的 14 字段 context，确保外部审查
  能看到作者的所有质感设定，做有据可依的评分。

用法：
  python -X utf8 scripts/build_external_context.py \
    --project-root "{PROJECT_ROOT}" \
    --chapter {N}

输出：
  {PROJECT_ROOT}/.webnovel/tmp/external_context_ch{NNNN}.json

新增字段（相比原 SKILL.md 内联脚本的 9 字段）：
  + narrative_voice       —— 叙事声音基准（避免"通用网文标准"盲评）
  + emotional_blueprint   —— 情感蓝图（避免"克制"被误判为"情感不足"）
  + opening_strategy      —— 开篇策略（仅 Ch1-3，避免误判前 3 章特殊钩子）
  + classical_references  —— 典故引用库（识别预约的典故伏笔）
  + original_poems        —— 原创诗词口诀（识别原创资产，避免误判为炫学）

与 step-3.5-external-review.md 的"上下文加载规则"严格对齐。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys


def read_file(base: pathlib.Path, rel: str, max_bytes: int | None = None) -> str:
    """读取相对路径的文本文件。不存在则返回空字符串。"""
    f = base / rel
    if not f.exists():
        return ""
    try:
        text = f.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # 降级：尝试 GBK（用于可能存在的历史文件）
        try:
            text = f.read_text(encoding="gbk")
        except Exception:
            return ""
    if max_bytes and len(text) > max_bytes:
        return text[:max_bytes]
    return text


def collect_prev_chapters(base: pathlib.Path, chapter_num: int, max_chars: int = 15000) -> str:
    """收集本章之前的所有章节正文，总字数上限 15000。"""
    chapters_dir = base / "正文"
    if not chapters_dir.exists():
        return ""

    # 匹配 "第NNNN章" 开头的文件（带或不带章节名）
    all_files = sorted(chapters_dir.glob("第*章*.md"))

    # 取前 chapter_num 个（即第 1 章到第 chapter_num-1 章，若存在）
    prev_files = [f for f in all_files if _extract_chapter_num(f.name) < chapter_num]

    texts = []
    for f in prev_files:
        try:
            texts.append(f.read_text(encoding="utf-8"))
        except Exception:
            continue

    combined = "\n---\n".join(texts)
    if len(combined) > max_chars:
        combined = combined[-max_chars:]  # 保留最后 N 字，接续性更强
    return combined


def _extract_chapter_num(filename: str) -> int:
    """从文件名 "第NNNN章..." 提取章节号。"""
    import re
    m = re.match(r"第(\d+)章", filename)
    return int(m.group(1)) if m else 0


def build_context(project_root: str, chapter_num: int) -> dict:
    """构建 Step 3.5 外部审查的完整 context（14 字段）。"""
    pr = pathlib.Path(project_root)
    if not pr.exists():
        raise FileNotFoundError(f"project_root 不存在: {project_root}")

    # 读取 state.json 的部分字段
    state_file = pr / ".webnovel" / "state.json"
    protagonist_state = {}
    if state_file.exists():
        try:
            state_data = json.loads(state_file.read_text(encoding="utf-8"))
            protagonist_state = state_data.get("protagonist_state", {})
            # 移除动态数值（避免与正文冲突）
            if isinstance(protagonist_state.get("attributes"), dict):
                protagonist_state["attributes"].pop("credits", None)
        except Exception as e:
            print(f"[WARN] 读取 state.json 失败: {e}", file=sys.stderr)

    # 开篇策略仅 Ch1-3 加载
    opening_strategy = read_file(pr, "设定集/开篇策略.md") if chapter_num <= 3 else ""

    ctx = {
        # ===== 核心 6 个（必读·原 9 字段的一部分）=====
        "outline_excerpt": read_file(pr, "大纲/总纲.md", max_bytes=3000),
        "protagonist_card": read_file(pr, "设定集/主角卡.md"),
        "golden_finger_card": read_file(pr, "设定集/金手指设计.md"),
        "female_lead_card": read_file(pr, "设定集/女主卡.md"),
        "villain_design": read_file(pr, "设定集/反派设计.md"),
        "power_system": read_file(pr, "设定集/力量体系.md"),
        "world_settings": read_file(pr, "设定集/世界观.md", max_bytes=5000),

        # ===== 质感 3 个（必读·新增，解决通用网文标准盲评）=====
        "narrative_voice": read_file(pr, "设定集/叙事声音.md"),
        "emotional_blueprint": read_file(pr, "设定集/情感蓝图.md"),
        "opening_strategy": opening_strategy,

        # ===== 典故 2 个（条件必读·新增，解决预约伏笔误判）=====
        "classical_references": read_file(pr, "设定集/典故引用库.md"),
        "original_poems": read_file(pr, "设定集/原创诗词口诀.md"),

        # ===== 状态与前章正文 =====
        "protagonist_state": protagonist_state,
        "prev_chapters_text": collect_prev_chapters(pr, chapter_num),
    }

    return ctx


def main():
    parser = argparse.ArgumentParser(description="构建 Step 3.5 外部审查 Context")
    parser.add_argument("--project-root", required=True, help="项目根目录")
    parser.add_argument("--chapter", type=int, required=True, help="章节号")
    args = parser.parse_args()

    ctx = build_context(args.project_root, args.chapter)

    # 统计字段非空情况
    field_stats = {}
    for k, v in ctx.items():
        if isinstance(v, str):
            field_stats[k] = f"{len(v)} chars"
        elif isinstance(v, dict):
            field_stats[k] = f"dict[{len(v)}]"
        else:
            field_stats[k] = str(type(v).__name__)

    # 写入 JSON
    chapter_padded = f"{args.chapter:04d}"
    out = pathlib.Path(args.project_root) / ".webnovel" / "tmp" / f"external_context_ch{chapter_padded}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ctx, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] Context written: {out}")
    print(f"[OK] Size: {out.stat().st_size} bytes")
    print(f"[OK] Fields ({len(ctx)}):")
    for k, stat in field_stats.items():
        print(f"     - {k}: {stat}")

    # 硬校验：质感三宝和典故两个文件至少要有一个非空（早期章节可能都缺）
    quality_fields = ["narrative_voice", "emotional_blueprint", "classical_references", "original_poems"]
    all_empty = all(not ctx.get(f) for f in quality_fields)
    if all_empty:
        print("[WARN] 质感三宝 + 典故两件套全部为空。外部模型可能按通用网文标准盲评。", file=sys.stderr)
        print("[WARN] 建议在 init 阶段创建这些文件以提升外部审查准确性。", file=sys.stderr)


if __name__ == "__main__":
    main()
