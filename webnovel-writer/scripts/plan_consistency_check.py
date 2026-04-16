#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
规划层一致性检查（框架通用版 · v1）

把曾经写死在项目里的 plan_consistency_check 改成"引擎 + 规则"架构：引擎在 plugin 里，
规则放项目自己的 `.webnovel/plan_consistency_config.json`。没有 config 时整体跳过（退出 0）。

支持的检查器（可单独启用/关闭）：
  1. drift_check —— 章号/事件漂移检测
     以"事件索引"为单一事实源，扫描其他规划文件里是否还引用了 v1 旧章号。
  2. gender_check —— 人物伏笔性别一致性
     扫描指定伏笔 ID 的性别表述，发现冲突即 fail。
  3. density_check —— 阅读密度窗口
     按章解析大纲，滑窗统计关键角色/反派出场次数，低于阈值报软警告。

退出码：
  0  全部通过 / 无 config
  1  发现硬漂移 / 性别冲突
  2  结构性错误（事件索引缺失 / config JSON 损坏 等）

命令行：
  python plan_consistency_check.py --project-root /path/to/project
  python plan_consistency_check.py --project-root . --check drift
  python plan_consistency_check.py --project-root . --quiet

与 hygiene_check 集成：
  项目 .webnovel/hygiene_check.py 优先跑项目本地的 plan_consistency_check.py（若存在），
  否则回退到本框架版（见 docs/hygiene-shim-fallback.md）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


DEFAULT_PLAN_DIRS = ("大纲", "设定集", "调研笔记")
DEFAULT_EXEMPT_MARKERS = ("v2", "V2", "修订", "注：", "注:", "原 v1", "原v1", "历史", "（应为", "(应为")


# --------------------------------------------------------------------------
# Utilities
# --------------------------------------------------------------------------
def _load_config(project_root: Path, cli_config: Path | None) -> dict[str, Any] | None:
    if cli_config is not None:
        if not cli_config.exists():
            raise FileNotFoundError(f"config 不存在：{cli_config}")
        return json.loads(cli_config.read_text(encoding="utf-8"))
    default = project_root / ".webnovel" / "plan_consistency_config.json"
    if default.exists():
        return json.loads(default.read_text(encoding="utf-8"))
    return None


def _iter_plan_files(project_root: Path, plan_dirs: list[str], ignore_paths: list[str]):
    def _matches_ignore(rel: str) -> bool:
        return any(rel.startswith(ig.rstrip("/")) or ig in rel for ig in ignore_paths)

    for d in plan_dirs:
        dir_path = project_root / d
        if not dir_path.exists():
            continue
        for p in dir_path.rglob("*.md"):
            rel = p.relative_to(project_root).as_posix()
            if _matches_ignore(rel):
                continue
            yield p


# --------------------------------------------------------------------------
# Check 1: drift_check
# --------------------------------------------------------------------------
def check_drift(project_root: Path, cfg: dict[str, Any], quiet: bool) -> list[str]:
    """
    config["drift"] schema:
      {
        "enabled": bool,
        "event_index": "大纲/第1卷-事件索引.md",      # 事实源，必须存在
        "rules": [
          {
            "feature_pattern": "regex",
            "old_values": ["第 40 章", "第40章"],
            "new_value": "第 35 章",
            "description": "末世爆发章"
          }
        ],
        "exempt_markers": ["v2", ...],                 # 可选，覆盖 DEFAULT_EXEMPT_MARKERS
        "ignore_paths": [".webnovel/backups/"],        # 可选
        "plan_dirs": ["大纲", "设定集"]                  # 可选，默认 DEFAULT_PLAN_DIRS
      }
    """
    drift_cfg = cfg.get("drift")
    if not drift_cfg or not drift_cfg.get("enabled", True):
        return []

    errors: list[str] = []
    event_index_rel = drift_cfg.get("event_index")
    if event_index_rel:
        event_index = project_root / event_index_rel
        if not event_index.exists():
            errors.append(f"[ERROR] 事件索引缺失：{event_index}")
            return errors

    rules = drift_cfg.get("rules", [])
    if not rules:
        if not quiet:
            print("  ⚠️  drift_check: 未定义规则，跳过")
        return []

    exempt_markers = tuple(drift_cfg.get("exempt_markers", DEFAULT_EXEMPT_MARKERS))
    ignore_paths = drift_cfg.get(
        "ignore_paths",
        [
            ".webnovel/backups/",
            ".webnovel/migrations/",
            ".webnovel/plan_consistency_check.py",
        ],
    )
    if event_index_rel:
        ignore_paths = list(ignore_paths) + [event_index_rel]
    plan_dirs = drift_cfg.get("plan_dirs", list(DEFAULT_PLAN_DIRS))

    compiled_rules = []
    for r in rules:
        try:
            compiled_rules.append((
                re.compile(r["feature_pattern"]),
                list(r.get("old_values", [])),
                r.get("new_value", ""),
                r.get("description", ""),
            ))
        except re.error as e:
            errors.append(f"[ERROR] drift 规则正则不合法: {r.get('feature_pattern')!r}: {e}")

    for fp in _iter_plan_files(project_root, plan_dirs, ignore_paths):
        try:
            text = fp.read_text(encoding="utf-8")
        except Exception as e:
            errors.append(f"[ERROR] 读取失败 {fp}: {e}")
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            if any(mk in line for mk in exempt_markers):
                continue
            for feature_re, old_vals, new_val, desc in compiled_rules:
                if not feature_re.search(line):
                    continue
                for old in old_vals:
                    if old in line:
                        rel = fp.relative_to(project_root).as_posix()
                        errors.append(
                            f"[DRIFT] {rel}:{line_no} · {desc} 仍引用旧值 "
                            f"'{old}'（应为 {new_val}）\n    → {line.strip()[:120]}"
                        )

    if not quiet and not errors:
        print(f"  ✅ drift_check: 0 处章号漂移（{len(compiled_rules)} 条规则）")
    return errors


# --------------------------------------------------------------------------
# Check 2: gender_check
# --------------------------------------------------------------------------
def check_gender(project_root: Path, cfg: dict[str, Any], quiet: bool) -> list[str]:
    """
    config["gender"] schema:
      {
        "enabled": bool,
        "state_file": ".webnovel/state.json",         # 可选，默认
        "checks": [
          {
            "id": "B1",
            "state_path": "plot_threads.foreshadowing",   # 可选
            "state_match_field": "id",                     # 可选
            "state_match_value": "B1",
            "state_content_field": "content",              # 可选
            "line_regex": "林晚秋.{0,15}(侄子|侄女)|林朵朵",
            "tokens": [["侄子", "男"], ["侄女", "女"]]
          }
        ],
        "plan_dirs": ["大纲", "设定集"],                    # 可选
        "ignore_paths": [".webnovel/backups/"]             # 可选
      }
    """
    gender_cfg = cfg.get("gender")
    if not gender_cfg or not gender_cfg.get("enabled", True):
        return []

    errors: list[str] = []
    checks = gender_cfg.get("checks", [])
    if not checks:
        if not quiet:
            print("  ⚠️  gender_check: 未定义规则，跳过")
        return []

    state_file_rel = gender_cfg.get("state_file", ".webnovel/state.json")
    state_file = project_root / state_file_rel
    plan_dirs = gender_cfg.get("plan_dirs", list(DEFAULT_PLAN_DIRS))
    ignore_paths = gender_cfg.get("ignore_paths", [".webnovel/backups/", ".webnovel/migrations/"])

    state_data: dict[str, Any] | None = None
    if state_file.exists():
        try:
            state_data = json.loads(state_file.read_text(encoding="utf-8"))
        except Exception as e:
            errors.append(f"[ERROR] state.json 解析失败: {e}")

    for check in checks:
        check_id = check.get("id", "?")
        tokens: list[list[str]] = check.get("tokens", [])
        if not tokens:
            continue
        try:
            pattern = re.compile(check["line_regex"])
        except (re.error, KeyError) as e:
            errors.append(f"[ERROR] gender check {check_id} line_regex 不合法: {e}")
            continue

        observations: list[tuple[str, int, str, str]] = []

        # state.json 查找
        if state_data is not None:
            state_path = check.get("state_path", "plot_threads.foreshadowing")
            match_field = check.get("state_match_field", "id")
            match_value = check.get("state_match_value", check_id)
            content_field = check.get("state_content_field", "content")
            node: Any = state_data
            for part in state_path.split("."):
                if isinstance(node, dict):
                    node = node.get(part)
                else:
                    node = None
                    break
            if isinstance(node, list):
                for item in node:
                    if isinstance(item, dict) and item.get(match_field) == match_value:
                        c = item.get(content_field, "")
                        if isinstance(c, str):
                            for tok, g in tokens:
                                if tok in c:
                                    observations.append(("state.json", 0, g, c[:80]))

        # 规划文件扫描
        for fp in _iter_plan_files(project_root, plan_dirs, ignore_paths):
            try:
                text = fp.read_text(encoding="utf-8")
            except Exception:
                continue
            for line_no, line in enumerate(text.splitlines(), 1):
                if pattern.search(line):
                    for tok, g in tokens:
                        if tok in line:
                            rel = fp.relative_to(project_root).as_posix()
                            observations.append((rel, line_no, g, line.strip()[:80]))

        genders = {g for _, _, g, _ in observations}
        if len(genders) > 1:
            errors.append(f"[GENDER_CONFLICT] 伏笔 {check_id} 存在性别冲突：")
            for src, ln, g, ctx in observations:
                loc = f"{src}:{ln}" if ln else src
                errors.append(f"    {loc} [{g}] {ctx}")
        elif not quiet:
            print(
                f"  ✅ gender_check[{check_id}]: "
                f"{len(observations)} 处表述一致（{','.join(genders) or '—'}）"
            )

    return errors


# --------------------------------------------------------------------------
# Check 3: density_check
# --------------------------------------------------------------------------
def check_density(project_root: Path, cfg: dict[str, Any], quiet: bool) -> tuple[list[str], list[str]]:
    """
    config["density"] schema:
      {
        "enabled": bool,
        "outline_path": "大纲/第1卷-详细大纲.md",
        "chapter_header_regex": "^### 第 (\\d+) 章[:：]",
        "window_size": 5,
        "tracks": [
          {"name": "女主露脸", "tokens": ["林晚秋", "苏瑾"]},
          {"name": "反派阴影", "tokens": ["陈默", "秦岳"]}
        ]
      }
    """
    density_cfg = cfg.get("density")
    if not density_cfg or not density_cfg.get("enabled", True):
        return [], []

    errors: list[str] = []
    warnings: list[str] = []
    outline = project_root / density_cfg.get("outline_path", "大纲/第1卷-详细大纲.md")
    if not outline.exists():
        errors.append(f"[WARN] 详细大纲缺失：{outline}")
        return errors, warnings

    try:
        pattern = re.compile(density_cfg.get("chapter_header_regex", r"^### 第 (\d+) 章[:：]"))
    except re.error as e:
        errors.append(f"[ERROR] density chapter_header_regex 不合法: {e}")
        return errors, warnings

    tracks = density_cfg.get("tracks", [])
    if not tracks:
        if not quiet:
            print("  ⚠️  density_check: 未定义 tracks，跳过")
        return [], []

    window_size = int(density_cfg.get("window_size", 5))

    # 解析章节
    text = outline.read_text(encoding="utf-8")
    chapters: dict[int, str] = {}
    current_idx: int | None = None
    buf: list[str] = []
    for line in text.splitlines():
        m = pattern.match(line)
        if m:
            if current_idx is not None:
                chapters[current_idx] = "\n".join(buf)
            current_idx = int(m.group(1))
            buf = [line]
        elif current_idx is not None:
            buf.append(line)
    if current_idx is not None:
        chapters[current_idx] = "\n".join(buf)

    if not chapters:
        warnings.append(f"[DENSITY·WARN] 详细大纲未匹配到任何章节头: {outline}")
        return errors, warnings

    max_ch = max(chapters)
    # 对每个 track 计算命中 flag
    track_flags: dict[str, dict[int, bool]] = {}
    for track in tracks:
        name = track.get("name", "track")
        tokens = track.get("tokens", [])
        flags = {
            idx: any(tok in body for tok in tokens)
            for idx, body in chapters.items()
        }
        track_flags[name] = flags

    # 滑窗统计
    for name, flags in track_flags.items():
        bad_windows: list[tuple[int, int]] = []
        if max_ch < window_size:
            continue
        for start in range(1, max_ch - window_size + 2):
            window = range(start, start + window_size)
            if sum(flags.get(i, False) for i in window) == 0:
                bad_windows.append((start, start + window_size - 1))
        if bad_windows:
            warnings.append(
                f"[DENSITY·WARN] {name} {window_size} 章滑窗为 0 的窗口 {len(bad_windows)} 个："
                + ", ".join(f"ch{a}-{b}" for a, b in bad_windows[:5])
                + (" ..." if len(bad_windows) > 5 else "")
            )

    if not quiet and not warnings:
        total = len(chapters)
        summary = " · ".join(
            f"{name} 命中 {sum(fl.values())} 章" for name, fl in track_flags.items()
        )
        print(f"  ✅ density_check: {total} 章 · {summary} · {window_size} 章滑窗全部达标")
    elif not quiet:
        print(f"  ⚠️  density_check: {len(warnings)} 处密度稀疏（软警告，不阻塞）")

    return errors, warnings


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="规划层一致性检查（框架通用版）")
    ap.add_argument("--project-root", type=Path, default=Path.cwd())
    ap.add_argument("--config", type=Path, default=None, help="config 路径，默认 .webnovel/plan_consistency_config.json")
    ap.add_argument(
        "--check",
        choices=["drift", "gender", "density", "all"],
        default="all",
    )
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    project_root = args.project_root.resolve()
    try:
        cfg = _load_config(project_root, args.config)
    except FileNotFoundError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as e:
        print(f"❌ config JSON 损坏: {e}", file=sys.stderr)
        return 2

    print("=" * 60)
    print(" 规划层一致性检查 · plan_consistency_check（框架版）")
    print(f" 项目：{project_root.name}")
    print("=" * 60)

    if cfg is None:
        print("  ℹ️  .webnovel/plan_consistency_config.json 未配置，跳过（返回 0）")
        print("=" * 60)
        return 0

    all_errors: list[str] = []
    all_warnings: list[str] = []

    if args.check in ("drift", "all"):
        if not args.quiet:
            print("\n[drift] planning_chapter_drift_check")
        all_errors += check_drift(project_root, cfg, args.quiet)
    if args.check in ("gender", "all"):
        if not args.quiet:
            print("\n[gender] foreshadowing_gender_check")
        all_errors += check_gender(project_root, cfg, args.quiet)
    if args.check in ("density", "all"):
        if not args.quiet:
            print("\n[density] reader_density_window_check")
        errs, warns = check_density(project_root, cfg, args.quiet)
        all_errors += errs
        all_warnings += warns

    print("\n" + "=" * 60)
    if all_errors:
        print(f" ❌ 发现 {len(all_errors)} 项硬问题：\n")
        for e in all_errors:
            print(e)
    if all_warnings:
        print(f"\n ⚠️  发现 {len(all_warnings)} 项软警告（不阻塞 commit）：\n")
        for w in all_warnings:
            print(w)
    print("\n" + "=" * 60)
    if all_errors:
        has_structural = any(e.startswith("[ERROR]") for e in all_errors)
        return 2 if has_structural else 1
    if all_warnings:
        print(" ✅ 硬检查全部通过（含软警告）")
    else:
        print(" ✅ 全部通过")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
