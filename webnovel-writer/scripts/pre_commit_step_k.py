#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 7 commit 前硬闸门 · Step K 设定集 Markdown 追加核对（通用版）

目的：Data Agent 的 Step K（设定集同步）会把新增实体/状态变化/伏笔写入
index.db + state.json，但 Markdown 文件的追加标注（`[Ch{N}]`）通常被推给
主 agent。若主 agent 忘记追加，则设定集 md 与 state.json 长期脱节，下章
context-agent 读取时会看不到上一章的新增。

检查项：
  1. 核心设定集文件（项目可配置，默认 伏笔追踪.md / 资产变动表.md / 主角卡.md）
     必须含 `[Ch{N}]` 标注
  2. state.chapter_meta.{NNNN}.foreshadowing_planted 里新增伏笔 ID 必须在
     伏笔追踪.md 可查

配置（可选）：
  项目侧 `.webnovel/step_k_config.json`:
      {
        "target_files": ["设定集/伏笔追踪.md", "设定集/资产变动表.md", "设定集/主角卡.md"],
        "check_foreshadowing_ids": true
      }

用法：
  python scripts/pre_commit_step_k.py <chapter_num> [--project-root PATH]

退出码：
  0 全追加完整
  1 硬追加遗漏（阻塞 commit）
  2 结构错误
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_TARGETS = [
    "设定集/伏笔追踪.md",
    "设定集/资产变动表.md",
    "设定集/主角卡.md",
]

# Round 28.35 (Ch44 v3 deep research RCA): 扩白名单 default · 缺失文件 skip 不阻断
# 用于：当项目存在 01/02/11.md 时自动追加 [ChN] 标注（不存在则 silent skip）
EXTENDED_TARGETS_OPTIONAL = [
    "设定集/01-卷一承诺-兑现表.md",
    "设定集/02-损失与代价表.md",
    "设定集/11-反派压强表.md",
]


def load_config(project_root: Path) -> dict:
    cfg = project_root / ".webnovel" / "step_k_config.json"
    if cfg.exists():
        try:
            return json.loads(cfg.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def check(project_root: Path, chapter: int) -> list[str]:
    errors: list[str] = []

    state_path = project_root / ".webnovel" / "state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"[ERROR] state.json 读取失败: {e}")
        return errors

    padded = f"{chapter:04d}"
    meta = state.get("chapter_meta", {}).get(padded)
    if not meta:
        errors.append(
            f"[ERROR] chapter_meta.{padded} 缺失（Step 5 Data Agent 未跑完？）"
        )
        return errors

    cfg = load_config(project_root)
    targets = cfg.get("target_files", DEFAULT_TARGETS)
    check_fs_ids = cfg.get("check_foreshadowing_ids", True)
    # Round 28.35: 是否检查扩展可选文件（默认 True · 文件不存在则 skip 不阻断）
    check_extended = cfg.get("check_extended_targets", True)
    extended_targets = cfg.get("extended_targets", EXTENDED_TARGETS_OPTIONAL)

    ch_tag = f"[Ch{chapter}"  # 匹配 [Ch1] [Ch1 埋设] 等所有变体

    for rel_path in targets:
        fp = project_root / rel_path
        if not fp.exists():
            errors.append(f"[ERROR] 设定集文件不存在: {rel_path}")
            continue
        text = fp.read_text(encoding="utf-8")
        if ch_tag not in text:
            errors.append(
                f"[STEP_K_MISSING] {rel_path} 未找到 '{ch_tag}' 标注 — "
                f"Data Agent Step K 把 md_append 责任推给主 agent，"
                f"主 agent 必须在 commit 前追加本章标注"
            )

    # Round 28.35: 扩展可选文件（卷一承诺/损失代价/反派压强）· 文件不存在则 skip
    # Round 28.50 (Ch48 RCA): 升级 — 缺 ≥2 个扩展文件 OR 距上次更新 ≥10 章 → 升级为 STEP_K_HIGH
    # Round 28.50 Ch48 实战：5/9 设定集没标 [Ch48] 我"不阻塞"心态忽略了, 实际是真问题
    extended_warnings = []
    extended_missing_count = 0
    if check_extended:
        for rel_path in extended_targets:
            fp = project_root / rel_path
            if not fp.exists():
                continue  # silent skip · 老项目无此文件不阻断
            text = fp.read_text(encoding="utf-8")
            if ch_tag not in text:
                extended_missing_count += 1
                extended_warnings.append(
                    f"[STEP_K_EXTENDED_WARN] {rel_path} 未找到 '{ch_tag}' 标注 · "
                    f"扩展同步白名单（卷一承诺/损失代价/反派压强）建议每章追加 · 不阻塞 commit"
                )
        # Round 28.50: 缺 >= 2 个扩展文件 → 升级 STEP_K_HIGH warn (仍不阻塞但显眼)
        if extended_missing_count >= 2:
            extended_warnings.append(
                f"[STEP_K_EXTENDED_HIGH] 缺 {extended_missing_count} 个扩展设定集 [Ch{chapter}] 标注 (≥2) · "
                f"Round 28.50 升级警告 · 强烈建议补齐 (即使不阻塞 commit) · "
                f"参考 Ch48 实战: 我跳了 P1 warn 结果 5/9 设定集没标导致下章 context-agent 漏读"
            )
    # 把 extended_warnings 通过模块级别变量暴露给 main · 主流程 print 但不计入 errors

    # 进阶：chapter_meta.foreshadowing_planted 里每条是否在伏笔追踪.md 可查
    if check_fs_ids:
        fs_planted = meta.get("foreshadowing_planted", [])
        fs_md = project_root / "设定集" / "伏笔追踪.md"
        if fs_planted and fs_md.exists():
            fs_text = fs_md.read_text(encoding="utf-8")
            for fs in fs_planted[:5]:  # 只查前 5 条避免过严
                m = re.match(r"([ABCD]\d+)", fs)
                if m and m.group(1) not in fs_text:
                    errors.append(
                        f"[FORESHADOWING_MD_MISSING] 伏笔 {m.group(1)} 在 "
                        f"chapter_meta 里埋设，但 设定集/伏笔追踪.md 未找到 ID 行"
                    )

    # 把扩展 warnings 加到 errors 列表末尾 · main 会区分（前缀 STEP_K_EXTENDED_WARN）
    errors.extend(extended_warnings)

    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("chapter", type=int)
    ap.add_argument("--project-root", type=Path, default=None)
    args = ap.parse_args()

    if args.project_root:
        project_root = args.project_root.resolve()
    else:
        cwd = Path.cwd()
        if (cwd / ".webnovel").exists():
            project_root = cwd
        else:
            print("  ❌ 无法自动定位项目根。请用 --project-root 指定。")
            return 2

    print("=" * 60)
    print(f" Step K 追加核对 · pre_commit_step_k · Ch{args.chapter}")
    print(f" 项目：{project_root.name}")
    print("=" * 60)

    all_errors = check(project_root, args.chapter)

    # Round 28.35: 分离 STEP_K_EXTENDED_WARN（不阻塞）与硬 errors
    blocking_errors = [e for e in all_errors if "STEP_K_EXTENDED_WARN" not in e]
    extended_warnings = [e for e in all_errors if "STEP_K_EXTENDED_WARN" in e]

    if extended_warnings:
        print(f"\n ⚠ Round 28.35 扩展白名单 {len(extended_warnings)} 项 warn（不阻塞）：")
        for w in extended_warnings:
            print(f"  {w}")

    if blocking_errors:
        print(f"\n ❌ 发现 {len(blocking_errors)} 项 Step K 遗漏（阻塞 commit）：")
        for e in blocking_errors:
            print(f"  {e}")
        print(
            "\n  修复方式：\n"
            "    - 按 chapter_meta.new_entities / foreshadowing_planted 逐条追加\n"
            "    - 格式：[Ch{N}] 标注行 或 表格新增 [Ch{N}] 列\n"
            "    - 参考最近一章的追加格式\n"
            "    - 项目可在 .webnovel/step_k_config.json 覆盖 target_files"
        )
        return 1

    print(
        f"\n ✅ Step K 设定集 Markdown 追加完整（[Ch{args.chapter}] 标注已覆盖全部目标文件）"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
