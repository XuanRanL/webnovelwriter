#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
webnovel 统一入口（面向 skills / agents 的稳定 CLI）

设计目标：
- 只有一个入口命令，避免到处拼 `python -m data_modules.xxx ...` 导致参数位置/引号/路径炸裂。
- 自动解析正确的 book project_root（包含 `.webnovel/state.json` 的目录）。
- 所有写入类命令在解析到 project_root 后，统一前置 `--project-root` 传给具体模块。

典型用法（推荐，不依赖 PYTHONPATH / 不要求 cd）：
  python "<SCRIPTS_DIR>/webnovel.py" preflight
  python "<SCRIPTS_DIR>/webnovel.py" where
  python "<SCRIPTS_DIR>/webnovel.py" use D:\\wk\\xiaoshuo\\凡人资本论
  python "<SCRIPTS_DIR>/webnovel.py" --project-root D:\\wk\\xiaoshuo index stats
  python "<SCRIPTS_DIR>/webnovel.py" --project-root D:\\wk\\xiaoshuo state process-chapter --chapter 100 --data @payload.json
  python "<SCRIPTS_DIR>/webnovel.py" --project-root D:\\wk\\xiaoshuo extract-context --chapter 100 --format json

也支持（不推荐，容易踩 PYTHONPATH/cd/参数顺序坑）：
  python -m data_modules.webnovel where
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from runtime_compat import normalize_windows_path
from project_locator import resolve_project_root, write_current_project_pointer, update_global_registry_current_project


def _scripts_dir() -> Path:
    # data_modules/webnovel.py -> data_modules -> scripts
    return Path(__file__).resolve().parent.parent


def _resolve_root(explicit_project_root: Optional[str]) -> Path:
    # 允许显式传入工作区根目录或书项目根目录
    raw = explicit_project_root
    if raw:
        return resolve_project_root(raw)
    return resolve_project_root()


def _strip_project_root_args(argv: list[str]) -> list[str]:
    """
    下游工具统一由本入口注入 `--project-root`，避免重复传参导致 argparse 报错/歧义。
    """
    out: list[str] = []
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok == "--project-root":
            i += 2
            continue
        if tok.startswith("--project-root="):
            i += 1
            continue
        out.append(tok)
        i += 1
    return out


def _run_data_module(module: str, argv: list[str]) -> int:
    """
    Import `data_modules.<module>` and call its main(), while isolating sys.argv.
    """
    mod = importlib.import_module(f"data_modules.{module}")
    main = getattr(mod, "main", None)
    if not callable(main):
        raise RuntimeError(f"data_modules.{module} 缺少可调用的 main()")

    old_argv = sys.argv
    try:
        sys.argv = [f"data_modules.{module}"] + argv
        try:
            main()
            return 0
        except SystemExit as e:
            return int(e.code or 0)
    finally:
        sys.argv = old_argv


def _run_script(script_name: str, argv: list[str]) -> int:
    """
    Run a script under the current `scripts/` directory via a subprocess.

    用途：兼容没有 main() 的脚本（例如 workflow_manager.py）。
    """
    script_path = _scripts_dir() / script_name
    if not script_path.is_file():
        raise FileNotFoundError(f"未找到脚本: {script_path}")
    proc = subprocess.run([sys.executable, str(script_path), *argv])
    return int(proc.returncode or 0)


def cmd_where(args: argparse.Namespace) -> int:
    root = _resolve_root(args.project_root)
    print(str(root))
    return 0


def _check_agents_sync(plugin_root: Path, workspace_root: Optional[Path]) -> Optional[dict]:
    """Verify plugin agents/ fully covered by workspace .claude/agents/ (fallback copy).

    Rationale: Workspace .claude/agents/ is the fallback when plugin cache is stale or
    when plugin cache version lags behind fork. If a checker exists in plugin agents/
    but NOT in workspace .claude/agents/, Task(checker) may silently fallback to
    general-purpose, causing phantom "skipped" steps. This has happened (Ch6 with
    flow-checker, 2026-04-13). Gate catches drift at Step 0 preflight.

    Returns None if workspace_root is None or agents/ does not exist (non-applicable).
    Returns dict with ok/missing when drift is detected or verified.
    """
    plugin_agents_dir = plugin_root / "agents"
    if not plugin_agents_dir.is_dir():
        return None
    if workspace_root is None:
        return None
    ws_agents_dir = workspace_root / ".claude" / "agents"
    if not ws_agents_dir.is_dir():
        return None  # workspace 未启用 .claude/agents 覆盖，不检查

    plugin_set = {p.name for p in plugin_agents_dir.glob("*.md")}
    ws_set = {p.name for p in ws_agents_dir.glob("*.md")}
    missing_in_ws = sorted(plugin_set - ws_set)
    extra_in_ws = sorted(ws_set - plugin_set)
    return {
        "name": "agents_sync",
        "ok": not missing_in_ws,
        "path": str(ws_agents_dir),
        "plugin_agents_count": len(plugin_set),
        "workspace_agents_count": len(ws_set),
        "missing_in_workspace": missing_in_ws,
        "extra_in_workspace": extra_in_ws,
        **(
            {"error": f"workspace .claude/agents/ 缺少 {len(missing_in_ws)} 个 agent: {missing_in_ws[:5]}"}
            if missing_in_ws else {}
        ),
    }


def _check_cache_sync(plugin_root: Path) -> Optional[dict]:
    """Verify fork plugin content matches the plugin cache Claude Code actually loads.

    Claude Code 运行 subagent/scripts 时从 `~/.claude/plugins/cache/{marketplace}/{plugin}/{version}/`
    加载（环境变量 CLAUDE_PLUGIN_ROOT 指向这里），不从 fork 工作区加载。fork 改动不会
    自动同步到 cache，导致 "commit 了但 AI 跑的还是旧代码" 的幽灵 bug。Ch6 flow-checker
    未运行（2026-04-13）即此事故。

    两条工作模式（Ch7 RCA 修复）：

    * **invoked from fork** — plugin_root 就是 fork 路径。直接跑 fork↔cache 漂移检查。
    * **invoked from cache** — plugin_root 是 cache 路径（CLAUDE_PLUGIN_ROOT 指向 cache，
      生产路径）。先通过 ``WEBNOVEL_FORK_PATH`` env var / fork-registry 找到 fork，
      然后用 fork vs 当前 plugin_root(cache) 做漂移对比。若找不到 fork，**返回带 note 的非 ok 项**
      （不再静默 return None）——让用户看到"未检查"提示而不是以为"无漂移"。
    """
    cache_root = _resolve_plugin_cache_dir(plugin_root)
    if cache_root is None:
        # plugin cache 不存在（用户可能没装 plugin 或走 local CLI）
        return {
            "name": "cache_sync",
            "ok": True,
            "path": "(cache_not_installed)",
            "note": "plugin cache 目录不存在，跳过漂移检查",
        }

    # 判断当前 plugin_root 是 fork 还是 cache
    try:
        running_from_cache = plugin_root.resolve() == cache_root.resolve()
    except Exception:
        running_from_cache = False

    if running_from_cache:
        # 生产路径：CLAUDE_PLUGIN_ROOT 指向 cache。必须通过 env/registry 找 fork。
        fork_root = _resolve_fork_for_cache(plugin_root)
        if fork_root is None:
            return {
                "name": "cache_sync",
                "ok": True,  # 非阻断，但 note 显眼
                "path": str(cache_root),
                "note": (
                    "invoked_from_cache 且 fork 未登记：跳过 fork→cache 漂移检查。"
                    "修复：从 fork 跑一次 `python /path/to/fork/scripts/webnovel.py sync-cache` "
                    "自动写入 registry；或设置 WEBNOVEL_FORK_PATH 环境变量。"
                ),
            }
        fork_side = fork_root
    else:
        fork_side = plugin_root

    drift = _compute_cache_drift(fork_side, cache_root)
    has_drift = bool(drift["fork_only"] or drift["different"])
    evidence_samples = (drift["different"] + drift["fork_only"])[:5]
    return {
        "name": "cache_sync",
        "ok": not has_drift,
        "path": str(cache_root),
        "fork_path": str(fork_side),
        "fork_only_count": len(drift["fork_only"]),
        "different_count": len(drift["different"]),
        "identical_count": drift["identical_count"],
        "sample_drift_files": evidence_samples,
        **(
            {"error": (
                f"fork→cache 漂移 {len(drift['different']) + len(drift['fork_only'])} 个文件 "
                f"(cache 缺 {len(drift['fork_only'])} / 内容不同 {len(drift['different'])}); "
                f"从 fork 跑 `webnovel.py sync-cache` 修复"
            )}
            if has_drift else {}
        ),
    }


def _build_preflight_report(explicit_project_root: Optional[str]) -> dict:
    scripts_dir = _scripts_dir().resolve()
    plugin_root = scripts_dir.parent
    skill_root = plugin_root / "skills" / "webnovel-write"
    entry_script = scripts_dir / "webnovel.py"
    extract_script = scripts_dir / "extract_chapter_context.py"

    checks: list[dict[str, object]] = [
        {"name": "scripts_dir", "ok": scripts_dir.is_dir(), "path": str(scripts_dir)},
        {"name": "entry_script", "ok": entry_script.is_file(), "path": str(entry_script)},
        {"name": "extract_context_script", "ok": extract_script.is_file(), "path": str(extract_script)},
        {"name": "skill_root", "ok": skill_root.is_dir(), "path": str(skill_root)},
    ]

    project_root = ""
    project_root_error = ""
    workspace_root: Optional[Path] = None
    try:
        resolved_root = _resolve_root(explicit_project_root)
        project_root = str(resolved_root)
        checks.append({"name": "project_root", "ok": True, "path": project_root})
        # 把 workspace_root 猜成 project_root 的父目录（多项目工作区）或自身（单项目）
        # 检查两级：父级 和 自身
        for candidate in (resolved_root, resolved_root.parent):
            if (candidate / ".claude" / "agents").is_dir():
                workspace_root = candidate
                break
    except Exception as exc:
        project_root_error = str(exc)
        checks.append({"name": "project_root", "ok": False, "path": explicit_project_root or "", "error": project_root_error})

    # Agents sync check — non-blocking warning (不阻断 preflight)
    sync_check = _check_agents_sync(plugin_root, workspace_root)
    if sync_check is not None:
        checks.append(sync_check)

    # Cache sync check — non-blocking warning（fork→cache 漂移检测，Ch6 根因）
    cache_check = _check_cache_sync(plugin_root)
    if cache_check is not None:
        checks.append(cache_check)

    # ok 聚合：只看 P0（必需）项；agents_sync/cache_sync 缺失只警告，不阻断 preflight
    p0_names = {"scripts_dir", "entry_script", "extract_context_script", "skill_root", "project_root"}
    return {
        "ok": all(bool(item["ok"]) for item in checks if item["name"] in p0_names),
        "project_root": project_root,
        "scripts_dir": str(scripts_dir),
        "skill_root": str(skill_root),
        "checks": checks,
        "project_root_error": project_root_error,
    }


def cmd_preflight(args: argparse.Namespace) -> int:
    report = _build_preflight_report(args.project_root)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for item in report["checks"]:
            status = "OK" if item["ok"] else "ERROR"
            path = item.get("path") or ""
            print(f"{status} {item['name']}: {path}")
            if item.get("error"):
                print(f"  detail: {item['error']}")
    return 0 if report["ok"] else 1


def cmd_sync_agents(args: argparse.Namespace) -> int:
    """Sync plugin agents/ to workspace .claude/agents/ to prevent subagent fallback.

    Root cause of Ch6 flow-checker silent skip (2026-04-13): `.claude/agents/` in
    workspace was not re-synced after new agents (e.g. flow-checker.md) were added
    to `webnovel-writer/agents/`. Task(flow-checker) silently fell back to
    general-purpose agent, so the 11th checker never ran even though ABC deployment
    had been marked complete.

    This command copies every .md in plugin agents/ into workspace .claude/agents/,
    printing added/updated/unchanged counts. Use after every commit that modifies
    plugin agents/.
    """
    import shutil
    from .cli_output import print_success, print_error

    scripts_dir = _scripts_dir().resolve()
    plugin_root = scripts_dir.parent
    plugin_agents_dir = plugin_root / "agents"
    if not plugin_agents_dir.is_dir():
        print_error("plugin_agents_missing", f"{plugin_agents_dir} 不存在")
        return 1

    try:
        resolved_root = _resolve_root(args.project_root)
    except Exception as exc:
        print_error("project_root_error", str(exc))
        return 1

    workspace_root: Optional[Path] = None
    for candidate in (resolved_root, resolved_root.parent):
        if (candidate / ".claude").is_dir():
            workspace_root = candidate
            break
    if workspace_root is None:
        print_error("workspace_not_found", f"未在 {resolved_root} 或父目录找到 .claude/ 子目录")
        return 1

    ws_agents_dir = workspace_root / ".claude" / "agents"
    ws_agents_dir.mkdir(parents=True, exist_ok=True)

    added: list[str] = []
    updated: list[str] = []
    unchanged: list[str] = []
    for src in sorted(plugin_agents_dir.glob("*.md")):
        dst = ws_agents_dir / src.name
        if not dst.exists():
            if not args.dry_run:
                shutil.copy2(src, dst)
            added.append(src.name)
        else:
            src_bytes = src.read_bytes()
            dst_bytes = dst.read_bytes()
            if src_bytes != dst_bytes:
                if not args.dry_run:
                    shutil.copy2(src, dst)
                updated.append(src.name)
            else:
                unchanged.append(src.name)

    result = {
        "workspace": str(workspace_root),
        "agents_dir": str(ws_agents_dir),
        "added": added,
        "updated": updated,
        "unchanged_count": len(unchanged),
        "dry_run": bool(args.dry_run),
    }
    msg = (
        f"agents 同步: +{len(added)} 新增, ~{len(updated)} 更新, ={len(unchanged)} 未变"
        + (" (dry-run)" if args.dry_run else "")
    )
    print_success(result, message=msg)
    return 0


def _walk_plugin_files(src_root: Path):
    """Yield (relative_path, absolute_path) for every file in fork plugin directory.

    Skips __pycache__, .pyc, test coverage / fixture artifacts that shouldn't
    propagate to plugin cache (where AI actually runs).
    """
    skip_dirs = {"__pycache__", ".git", ".pytest_cache", ".ruff_cache", ".mypy_cache", "htmlcov"}
    skip_ext = {".pyc", ".pyo"}
    # `.coverage` 和 `.coverage.<host>.<id>` 是 pytest-cov 运行产物；`.coveragerc` 是配置文件要保留
    skip_exact = {".DS_Store", "Thumbs.db", ".coverage"}
    for path in src_root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        if path.suffix in skip_ext:
            continue
        if path.name in skip_exact:
            continue
        # 匹配 .coverage.HOSTNAME.12345 这种 pattern 但放行 .coveragerc
        if path.name.startswith(".coverage.") and not path.name == ".coveragerc":
            continue
        yield path.relative_to(src_root), path


def _resolve_plugin_cache_dir(plugin_root: Path, explicit: Optional[str] = None) -> Optional[Path]:
    """Resolve plugin cache directory for current version.

    Reads plugin name+version from `.claude-plugin/plugin.json` (NOT from
    ``plugin_root.name``). This matters because when running from cache the
    directory name is the version string (e.g. ``5.6.0``), not the plugin name;
    using ``plugin_root.name`` would construct a wrong path and silently return
    None — this was the Round 7 cache_sync silent-skip bug (Ch7 RCA).

    Returns the cache directory path if found, None otherwise. Does NOT raise.
    """
    if explicit:
        p = Path(explicit)
        return p if p.is_dir() else None
    plugin_json = plugin_root / ".claude-plugin" / "plugin.json"
    if not plugin_json.exists():
        return None
    try:
        data = json.loads(plugin_json.read_text(encoding="utf-8"))
        plugin_name = str(data.get("name", "")).strip()
        version = str(data.get("version", "")).strip()
    except Exception:
        return None
    if not version or not plugin_name:
        return None
    home = Path(os.path.expanduser("~"))
    cand = home / ".claude" / "plugins" / "cache" / f"{plugin_name}-marketplace" / plugin_name / version
    return cand if cand.is_dir() else None


def _fork_registry_path() -> Path:
    """Registry that maps plugin name → fork path.

    Written by ``sync-cache`` when invoked from fork; read by ``preflight``
    when invoked from cache so drift can still be detected in the production
    invocation path (CLAUDE_PLUGIN_ROOT points to cache).
    """
    return Path(os.path.expanduser("~")) / ".claude" / "plugins" / "webnovel-fork-registry.json"


def _read_fork_registry() -> dict:
    path = _fork_registry_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_fork_registry(plugin_name: str, fork_path: Path) -> None:
    """Record ``plugin_name → fork_path`` so cache-side preflight can find fork."""
    path = _fork_registry_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = _read_fork_registry()
        data[plugin_name] = str(fork_path.resolve())
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        # best-effort; registry is optional
        pass


def _resolve_fork_for_cache(plugin_root: Path) -> Optional[Path]:
    """When running from cache, locate the fork via env var or registry.

    Priority:
      1. ``WEBNOVEL_FORK_PATH`` env var (explicit override)
      2. Fork registry at ``~/.claude/plugins/webnovel-fork-registry.json``
      3. None (caller should emit actionable note)
    """
    env_fork = os.environ.get("WEBNOVEL_FORK_PATH", "").strip()
    if env_fork:
        p = Path(env_fork)
        if (p / ".claude-plugin" / "plugin.json").exists():
            return p.resolve()
    plugin_json = plugin_root / ".claude-plugin" / "plugin.json"
    if not plugin_json.exists():
        return None
    try:
        name = json.loads(plugin_json.read_text(encoding="utf-8")).get("name", "").strip()
    except Exception:
        return None
    if not name:
        return None
    registry = _read_fork_registry()
    fork_path_str = registry.get(name, "")
    if not fork_path_str:
        return None
    p = Path(fork_path_str)
    if (p / ".claude-plugin" / "plugin.json").exists():
        return p.resolve()
    return None


def _compute_cache_drift(plugin_root: Path, cache_root: Path) -> dict:
    """Compute drift between fork plugin and cache. Returns summary dict.

    Returns:
        {
          "fork_only": [rel_paths],       # in fork but not cache
          "cache_only": [rel_paths],      # in cache but not fork (legacy / .pyc)
          "different": [rel_paths],       # exist in both but content differs
          "identical_count": int,
          "total_fork": int,
          "total_cache": int,
        }
    """
    fork_files = {}
    for rel_path, abs_path in _walk_plugin_files(plugin_root):
        fork_files[str(rel_path).replace("\\", "/")] = abs_path
    cache_files = {}
    skip_dirs = {"__pycache__", ".git", ".pytest_cache"}
    for path in cache_root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        rel = str(path.relative_to(cache_root)).replace("\\", "/")
        cache_files[rel] = path
    fork_set = set(fork_files.keys())
    cache_set = set(cache_files.keys())
    fork_only = sorted(fork_set - cache_set)
    cache_only = sorted(cache_set - fork_set)
    different: list[str] = []
    identical = 0
    for rel in sorted(fork_set & cache_set):
        try:
            if fork_files[rel].read_bytes() != cache_files[rel].read_bytes():
                different.append(rel)
            else:
                identical += 1
        except Exception:
            different.append(rel)
    return {
        "fork_only": fork_only,
        "cache_only": cache_only,
        "different": different,
        "identical_count": identical,
        "total_fork": len(fork_set),
        "total_cache": len(cache_set),
    }


def cmd_sync_cache(args: argparse.Namespace) -> int:
    """Sync fork plugin files to Claude Code plugin cache — or just check drift.

    Claude Code plugin 三层架构:
      ① fork (I:\\AI-extention\\webnovel-writer\\webnovel-writer\\)
      ② marketplace mirror (~\\.claude\\plugins\\marketplaces\\webnovel-writer-marketplace\\)
      ③ plugin cache (~\\.claude\\plugins\\cache\\webnovel-writer-marketplace\\webnovel-writer\\{VERSION}\\)

    AI 运行时通过 $CLAUDE_PLUGIN_ROOT 从 ③ 加载脚本和 agent 定义，不读 ①。
    fork → cache 无自动同步：必须显式跑 /plugin update 或本命令。

    Root cause of Ch6 flow-checker/reader_flow 从未运行（2026-04-13）：commit 96c9156
    把 fork 的 chapter_audit.py 修复，但 cache 保留 37 行乱码 + 10 checker。
    AI 每次都跑 cache 的旧代码。本命令绕过 marketplace 直接同步 fork→cache。

    模式:
      默认: 同步所有 fork 文件到 cache（overwrite）+ 清理 .pyc
      --check-only: 只报告漂移，不写入（用于 preflight / CI 检测）
      --dry-run: 打印将要同步的文件清单，不写入
      --cache-dir PATH: 手动指定 cache 位置（调试用）

    退出码:
      0 = 无漂移 OR 同步成功
      1 = 运行错误（plugin.json 缺失 / cache 目录不存在 / etc）
      2 = --check-only 且检测到漂移（让 CI / preflight 能据此 alert）
    """
    import shutil
    from .cli_output import print_success, print_error

    scripts_dir = _scripts_dir().resolve()
    plugin_root = scripts_dir.parent

    plugin_json = plugin_root / ".claude-plugin" / "plugin.json"
    if not plugin_json.exists():
        print_error("plugin_json_missing", f"{plugin_json} 不存在")
        return 1
    try:
        version = json.loads(plugin_json.read_text(encoding="utf-8")).get("version", "").strip()
    except Exception as exc:
        print_error("plugin_json_parse", f"parse {plugin_json}: {exc}")
        return 1
    if not version:
        print_error("plugin_version_missing", f"{plugin_json} 缺 version 字段")
        return 1

    cache_root = _resolve_plugin_cache_dir(plugin_root, getattr(args, "cache_dir", None))
    if cache_root is None:
        print_error(
            "cache_not_found",
            f"未找到 plugin cache 目录 (version={version})",
            suggestion="使用 --cache-dir 手动指定；或跑 `/plugin install webnovel-writer@webnovel-writer-marketplace` 初始化"
        )
        return 1

    # 防止"从 cache 里跑 sync-cache"自反拷贝（会让 cache → cache，无意义）
    try:
        if plugin_root.resolve() == cache_root.resolve():
            print_error(
                "invoked_from_cache",
                "sync-cache 在 cache 目录内被调用，无法自同步。请 cd 到 fork 目录再跑。",
                suggestion=f"cd 到 fork（例如 `~/AI-extention/webnovel-writer/webnovel-writer`），再跑 `python scripts/webnovel.py sync-cache`"
            )
            return 1
    except Exception:
        pass

    # 写入 fork 登记（让从 cache 跑的 preflight 能找到 fork 做漂移检查）
    try:
        plugin_name = json.loads((plugin_root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")).get("name", "").strip()
        if plugin_name:
            _write_fork_registry(plugin_name, plugin_root)
    except Exception:
        pass

    drift = _compute_cache_drift(plugin_root, cache_root)

    # --check-only: 只报告，不写入
    if getattr(args, "check_only", False):
        has_drift = bool(drift["fork_only"] or drift["different"])
        result = {
            "fork": str(plugin_root),
            "cache": str(cache_root),
            "version": version,
            "drift_detected": has_drift,
            "fork_only_count": len(drift["fork_only"]),
            "different_count": len(drift["different"]),
            "cache_only_count": len(drift["cache_only"]),
            "identical_count": drift["identical_count"],
            "fork_only_sample": drift["fork_only"][:10],
            "different_sample": drift["different"][:10],
        }
        if has_drift:
            msg = (
                f"检测到 cache 漂移 v{version}: "
                f"fork 缺 cache {len(drift['fork_only'])} 个, "
                f"内容不同 {len(drift['different'])} 个 "
                f"→ 跑 `webnovel.py sync-cache` 修复"
            )
            print_error("cache_drift_detected", msg, suggestion="webnovel.py sync-cache")
            return 2
        else:
            print_success(result, message=f"cache 对齐 v{version}, 无漂移 ({drift['identical_count']} 文件一致)")
            return 0

    # 实际同步（非 check-only）
    added: list[str] = []
    updated: list[str] = []
    unchanged: list[str] = []
    removed_pyc: list[str] = []

    for rel_path, src in _walk_plugin_files(plugin_root):
        dst = cache_root / rel_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            if not args.dry_run:
                shutil.copy2(src, dst)
            added.append(str(rel_path))
        else:
            if src.read_bytes() != dst.read_bytes():
                if not args.dry_run:
                    shutil.copy2(src, dst)
                updated.append(str(rel_path))
            else:
                unchanged.append(str(rel_path))

    # 清理 cache 里的 .pyc（避免 stale bytecode shadow 新 .py）
    if not args.dry_run:
        for pyc in cache_root.rglob("*.pyc"):
            try:
                pyc.unlink()
                removed_pyc.append(str(pyc.relative_to(cache_root)))
            except Exception:
                pass

    result = {
        "fork": str(plugin_root),
        "cache": str(cache_root),
        "version": version,
        "added": added[:20],
        "updated": updated[:20],
        "added_count": len(added),
        "updated_count": len(updated),
        "unchanged_count": len(unchanged),
        "removed_pyc_count": len(removed_pyc),
        "dry_run": bool(args.dry_run),
    }
    msg = (
        f"cache 同步 v{version}: +{len(added)} 新增, ~{len(updated)} 更新, "
        f"={len(unchanged)} 未变, -{len(removed_pyc)} .pyc 清理"
        + (" (dry-run)" if args.dry_run else "")
    )
    print_success(result, message=msg)
    return 0


def cmd_use(args: argparse.Namespace) -> int:
    project_root = normalize_windows_path(args.project_root).expanduser()
    try:
        project_root = project_root.resolve()
    except Exception:
        project_root = project_root

    workspace_root: Optional[Path] = None
    if args.workspace_root:
        workspace_root = normalize_windows_path(args.workspace_root).expanduser()
        try:
            workspace_root = workspace_root.resolve()
        except Exception:
            workspace_root = workspace_root

    # 1) 写入工作区指针（若工作区内存在 `.claude/`）
    pointer_file = write_current_project_pointer(project_root, workspace_root=workspace_root)
    if pointer_file is not None:
        print(f"workspace pointer: {pointer_file}")
    else:
        print("workspace pointer: (skipped)")

    # 2) 写入用户级 registry（保证全局安装/空上下文可恢复）
    reg_path = update_global_registry_current_project(workspace_root=workspace_root, project_root=project_root)
    if reg_path is not None:
        print(f"global registry: {reg_path}")
    else:
        print("global registry: (skipped)")

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="webnovel unified CLI")
    parser.add_argument("--project-root", help="书项目根目录或工作区根目录（可选，默认自动检测）")

    sub = parser.add_subparsers(dest="tool", required=True)

    p_where = sub.add_parser("where", help="打印解析出的 project_root")
    p_where.set_defaults(func=cmd_where)

    p_preflight = sub.add_parser("preflight", help="校验统一 CLI 运行环境与 project_root")
    p_preflight.add_argument("--format", choices=["text", "json"], default="text", help="输出格式")
    p_preflight.set_defaults(func=cmd_preflight)

    p_sync_agents = sub.add_parser("sync-agents", help="将 plugin agents/ 同步到工作区 .claude/agents/（修复 Task subagent fallback）")
    p_sync_agents.add_argument("--dry-run", action="store_true", help="仅打印待同步清单，不写入")
    p_sync_agents.set_defaults(func=cmd_sync_agents)

    p_sync_cache = sub.add_parser("sync-cache", help="将 fork 源码同步到 plugin cache（修复 fork↔cache 漂移，每次 git pull 后必跑）")
    p_sync_cache.add_argument("--dry-run", action="store_true", help="打印待同步清单，不写入")
    p_sync_cache.add_argument("--check-only", action="store_true", help="只检测漂移不同步（退出码 2=有漂移，供 CI/preflight 使用）")
    p_sync_cache.add_argument("--cache-dir", help="手动指定 cache 目录（调试用）")
    p_sync_cache.set_defaults(func=cmd_sync_cache)

    p_use = sub.add_parser("use", help="绑定当前工作区使用的书项目（写入指针/registry）")
    p_use.add_argument("project_root", help="书项目根目录（必须包含 .webnovel/state.json）")
    p_use.add_argument("--workspace-root", help="工作区根目录（可选；默认由运行环境推断）")
    p_use.set_defaults(func=cmd_use)

    # Pass-through to data modules
    p_index = sub.add_parser("index", help="转发到 index_manager")
    p_index.add_argument("args", nargs=argparse.REMAINDER)

    p_state = sub.add_parser("state", help="转发到 state_manager")
    p_state.add_argument("args", nargs=argparse.REMAINDER)

    p_rag = sub.add_parser("rag", help="转发到 rag_adapter")
    p_rag.add_argument("args", nargs=argparse.REMAINDER)

    p_style = sub.add_parser("style", help="转发到 style_sampler")
    p_style.add_argument("args", nargs=argparse.REMAINDER)

    p_entity = sub.add_parser("entity", help="转发到 entity_linker")
    p_entity.add_argument("args", nargs=argparse.REMAINDER)

    p_context = sub.add_parser("context", help="转发到 context_manager")
    p_context.add_argument("args", nargs=argparse.REMAINDER)

    p_migrate = sub.add_parser("migrate", help="转发到 migrate_state_to_sqlite")
    p_migrate.add_argument("args", nargs=argparse.REMAINDER)

    p_audit = sub.add_parser("audit", help="转发到 chapter_audit (Step 6 审计)")
    p_audit.add_argument("args", nargs=argparse.REMAINDER)

    # Pass-through to scripts
    p_workflow = sub.add_parser("workflow", help="转发到 workflow_manager.py")
    p_workflow.add_argument("args", nargs=argparse.REMAINDER)

    p_status = sub.add_parser("status", help="转发到 status_reporter.py")
    p_status.add_argument("args", nargs=argparse.REMAINDER)

    p_update_state = sub.add_parser("update-state", help="转发到 update_state.py")
    p_update_state.add_argument("args", nargs=argparse.REMAINDER)

    p_backup = sub.add_parser("backup", help="转发到 backup_manager.py")
    p_backup.add_argument("args", nargs=argparse.REMAINDER)

    p_archive = sub.add_parser("archive", help="转发到 archive_manager.py")
    p_archive.add_argument("args", nargs=argparse.REMAINDER)

    p_init = sub.add_parser("init", help="转发到 init_project.py（初始化项目）")
    p_init.add_argument("args", nargs=argparse.REMAINDER)

    p_extract_context = sub.add_parser("extract-context", help="转发到 extract_chapter_context.py")
    p_extract_context.add_argument("--chapter", type=int, required=True, help="目标章节号")
    p_extract_context.add_argument("--format", choices=["text", "json"], default="text", help="输出格式")

    # 兼容：允许 `--project-root` 出现在任意位置（减少 agents/skills 拼命令的出错率）
    from .cli_args import normalize_global_project_root

    argv = normalize_global_project_root(sys.argv[1:])
    args = parser.parse_args(argv)

    # where/use 直接执行
    if hasattr(args, "func"):
        code = int(args.func(args) or 0)
        raise SystemExit(code)

    tool = args.tool
    rest = list(getattr(args, "args", []) or [])
    # argparse.REMAINDER 可能以 `--` 开头占位，这里去掉
    if rest[:1] == ["--"]:
        rest = rest[1:]
    rest = _strip_project_root_args(rest)

    # init 是创建项目，不应该依赖/注入已存在 project_root
    if tool == "init":
        raise SystemExit(_run_script("init_project.py", rest))

    # 其余工具：统一解析 project_root 后前置给下游
    project_root = _resolve_root(args.project_root)
    forward_args = ["--project-root", str(project_root)]

    if tool == "index":
        raise SystemExit(_run_data_module("index_manager", [*forward_args, *rest]))
    if tool == "state":
        raise SystemExit(_run_data_module("state_manager", [*forward_args, *rest]))
    if tool == "rag":
        raise SystemExit(_run_data_module("rag_adapter", [*forward_args, *rest]))
    if tool == "style":
        raise SystemExit(_run_data_module("style_sampler", [*forward_args, *rest]))
    if tool == "entity":
        raise SystemExit(_run_data_module("entity_linker", [*forward_args, *rest]))
    if tool == "context":
        raise SystemExit(_run_data_module("context_manager", [*forward_args, *rest]))
    if tool == "migrate":
        raise SystemExit(_run_data_module("migrate_state_to_sqlite", [*forward_args, *rest]))
    if tool == "audit":
        raise SystemExit(_run_data_module("chapter_audit", [*forward_args, *rest]))

    if tool == "workflow":
        raise SystemExit(_run_script("workflow_manager.py", [*forward_args, *rest]))
    if tool == "status":
        raise SystemExit(_run_script("status_reporter.py", [*forward_args, *rest]))
    if tool == "update-state":
        raise SystemExit(_run_script("update_state.py", [*forward_args, *rest]))
    if tool == "backup":
        raise SystemExit(_run_script("backup_manager.py", [*forward_args, *rest]))
    if tool == "archive":
        raise SystemExit(_run_script("archive_manager.py", [*forward_args, *rest]))
    if tool == "extract-context":
        return_args = [*forward_args, "--chapter", str(args.chapter), "--format", str(args.format)]
        raise SystemExit(_run_script("extract_chapter_context.py", return_args))

    raise SystemExit(2)


if __name__ == "__main__":
    main()
