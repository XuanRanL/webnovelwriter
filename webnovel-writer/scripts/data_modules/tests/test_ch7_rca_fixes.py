#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ch7 RCA 回归测试 · 2026-04-16

覆盖两个 root cause：

1. ``_resolve_plugin_cache_dir`` 之前用 ``plugin_root.name`` 解析 plugin 名字，
   从 cache 跑时 ``plugin_root.name`` 是版本号 "5.6.0" 而不是 "webnovel-writer"，
   导致 preflight 的 ``cache_sync`` 检查静默返回 None（生产路径完全不报警）。
   修复后：从 plugin.json 读取 name 字段，并引入 fork-registry 机制。

2. ``workflow_manager.REQUIRED_ARTIFACT_FIELDS["Step 3"]`` 缺 ``naturalness_verdict``
   / ``naturalness_score``，虽然 SKILL.md 和 step-3-review-gate.md 在 2026-04-16
   文档里声明这两个字段为 Step 3 合法语义字段，代码却拒收。

这些 case 都是 "文档说改了，代码没改" 的熟悉 pattern。该文件锁死回归。
"""

import json
import sys
from pathlib import Path

import pytest


def _ensure_scripts_on_path() -> None:
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def _load_webnovel_module():
    _ensure_scripts_on_path()
    import data_modules.webnovel as module

    return module


# ---------------------------------------------------------------------------
# BUG-1: _resolve_plugin_cache_dir reads plugin.json (not plugin_root.name)
# ---------------------------------------------------------------------------


def _make_plugin_dir(root: Path, name: str, version: str) -> Path:
    plugin_dir = root
    plugin_json_dir = plugin_dir / ".claude-plugin"
    plugin_json_dir.mkdir(parents=True, exist_ok=True)
    (plugin_json_dir / "plugin.json").write_text(
        json.dumps({"name": name, "version": version}), encoding="utf-8"
    )
    return plugin_dir


def test_resolve_cache_dir_uses_plugin_json_name_not_dirname(tmp_path, monkeypatch):
    """从 cache 跑时 plugin_root.name 是版本号；必须读 plugin.json 的 name 字段。"""
    module = _load_webnovel_module()

    # 模拟 "cache 目录" 场景：plugin_root = .../cache/foo-marketplace/foo/5.6.0/
    # plugin_root.name == "5.6.0"，但 plugin.json 里 name == "foo"
    fake_home = tmp_path / "home"
    version_dir = fake_home / ".claude" / "plugins" / "cache" / "foo-marketplace" / "foo" / "5.6.0"
    _make_plugin_dir(version_dir, name="foo", version="5.6.0")

    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))

    # 当从 cache 目录本身出发时，必须能成功解析（plugin_root.name == "5.6.0" 是陷阱）
    resolved = module._resolve_plugin_cache_dir(version_dir)
    assert resolved is not None, "读取 plugin.json name 失败 — 这是 Ch7 RCA BUG-1 回归"
    assert resolved.resolve() == version_dir.resolve()


def test_resolve_cache_dir_returns_none_when_plugin_json_missing(tmp_path):
    module = _load_webnovel_module()
    plugin_dir = tmp_path / "fake-plugin"
    plugin_dir.mkdir()
    assert module._resolve_plugin_cache_dir(plugin_dir) is None


def test_resolve_cache_dir_returns_none_when_name_missing(tmp_path, monkeypatch):
    module = _load_webnovel_module()
    fake_home = tmp_path / "home"
    version_dir = fake_home / ".claude" / "plugins" / "cache" / "-marketplace" / "" / "5.6.0"
    version_dir.mkdir(parents=True)
    (version_dir / ".claude-plugin").mkdir()
    (version_dir / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"version": "5.6.0"}), encoding="utf-8"
    )
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))
    assert module._resolve_plugin_cache_dir(version_dir) is None


# ---------------------------------------------------------------------------
# BUG-1 cont.: fork-registry so cache-side preflight can locate fork
# ---------------------------------------------------------------------------


def test_fork_registry_roundtrip(tmp_path, monkeypatch):
    """sync-cache 从 fork 跑时写 registry，preflight 从 cache 跑时读 registry。"""
    module = _load_webnovel_module()
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))
    monkeypatch.delenv("WEBNOVEL_FORK_PATH", raising=False)

    fork_root = tmp_path / "fork"
    _make_plugin_dir(fork_root, name="webnovel-writer", version="5.6.0")

    # 从 fork 侧登记
    module._write_fork_registry("webnovel-writer", fork_root)

    # 从 cache 侧模拟查询：plugin_root 是 cache，但 plugin.json 里 name 对得上
    cache_root = fake_home / ".claude" / "plugins" / "cache" / "webnovel-writer-marketplace" / "webnovel-writer" / "5.6.0"
    _make_plugin_dir(cache_root, name="webnovel-writer", version="5.6.0")

    resolved = module._resolve_fork_for_cache(cache_root)
    assert resolved is not None
    assert resolved.resolve() == fork_root.resolve()


def test_fork_registry_env_var_takes_priority(tmp_path, monkeypatch):
    module = _load_webnovel_module()
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))

    env_fork = tmp_path / "env-fork"
    _make_plugin_dir(env_fork, name="webnovel-writer", version="5.6.0")
    registry_fork = tmp_path / "registry-fork"
    _make_plugin_dir(registry_fork, name="webnovel-writer", version="5.6.0")
    module._write_fork_registry("webnovel-writer", registry_fork)

    monkeypatch.setenv("WEBNOVEL_FORK_PATH", str(env_fork))
    cache_root = fake_home / ".claude" / "plugins" / "cache" / "webnovel-writer-marketplace" / "webnovel-writer" / "5.6.0"
    _make_plugin_dir(cache_root, name="webnovel-writer", version="5.6.0")
    resolved = module._resolve_fork_for_cache(cache_root)
    assert resolved is not None
    assert resolved.resolve() == env_fork.resolve()


def test_fork_registry_returns_none_when_fork_missing(tmp_path, monkeypatch):
    module = _load_webnovel_module()
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))
    monkeypatch.delenv("WEBNOVEL_FORK_PATH", raising=False)

    cache_root = fake_home / ".claude" / "plugins" / "cache" / "webnovel-writer-marketplace" / "webnovel-writer" / "5.6.0"
    _make_plugin_dir(cache_root, name="webnovel-writer", version="5.6.0")
    # registry 不存在
    resolved = module._resolve_fork_for_cache(cache_root)
    assert resolved is None


# ---------------------------------------------------------------------------
# BUG-1 cont.: _check_cache_sync never silently returns None in production
# ---------------------------------------------------------------------------


def test_check_cache_sync_from_cache_without_fork_emits_note(tmp_path, monkeypatch):
    """生产路径：从 cache 跑 preflight 时，即使 fork 未登记也必须输出检查项（不能静默 None）。"""
    module = _load_webnovel_module()
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))
    monkeypatch.delenv("WEBNOVEL_FORK_PATH", raising=False)

    cache_root = fake_home / ".claude" / "plugins" / "cache" / "webnovel-writer-marketplace" / "webnovel-writer" / "5.6.0"
    _make_plugin_dir(cache_root, name="webnovel-writer", version="5.6.0")

    result = module._check_cache_sync(cache_root)
    assert result is not None, "绝不能返回 None（Ch7 RCA：这正是 Round 7 cache_sync 静默失效的根因）"
    assert result["name"] == "cache_sync"
    assert "note" in result
    assert "invoked_from_cache" in result["note"] or "fork" in result["note"].lower()


def test_check_cache_sync_from_cache_with_registry_detects_drift(tmp_path, monkeypatch):
    """从 cache 跑 preflight 时，通过 registry 找到 fork 后能检测漂移。"""
    module = _load_webnovel_module()
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))
    monkeypatch.delenv("WEBNOVEL_FORK_PATH", raising=False)

    fork_root = tmp_path / "fork"
    _make_plugin_dir(fork_root, name="webnovel-writer", version="5.6.0")
    # fork 里放一个 cache 没有的文件
    (fork_root / "scripts").mkdir()
    (fork_root / "scripts" / "new_checker.py").write_text("# fork only\n", encoding="utf-8")

    cache_root = fake_home / ".claude" / "plugins" / "cache" / "webnovel-writer-marketplace" / "webnovel-writer" / "5.6.0"
    _make_plugin_dir(cache_root, name="webnovel-writer", version="5.6.0")
    (cache_root / "scripts").mkdir()  # cache 有 scripts 目录但无 new_checker.py

    module._write_fork_registry("webnovel-writer", fork_root)

    result = module._check_cache_sync(cache_root)
    assert result is not None
    assert result["name"] == "cache_sync"
    assert result["ok"] is False
    assert result["fork_only_count"] >= 1
    assert "error" in result


def test_check_cache_sync_from_fork_still_works(tmp_path, monkeypatch):
    module = _load_webnovel_module()
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))

    fork_root = tmp_path / "fork"
    _make_plugin_dir(fork_root, name="webnovel-writer", version="5.6.0")

    cache_root = fake_home / ".claude" / "plugins" / "cache" / "webnovel-writer-marketplace" / "webnovel-writer" / "5.6.0"
    _make_plugin_dir(cache_root, name="webnovel-writer", version="5.6.0")

    # fork 与 cache 都只有 plugin.json，一致 → ok
    result = module._check_cache_sync(fork_root)
    assert result is not None
    assert result["ok"] is True


# ---------------------------------------------------------------------------
# BUG-2: Step 3 artifact whitelist includes naturalness_verdict / score
# ---------------------------------------------------------------------------


def test_step3_whitelist_accepts_naturalness_verdict_alone():
    """SKILL.md 和 step-3-review-gate.md 声明 naturalness_verdict 是 Step 3 合法字段。"""
    _ensure_scripts_on_path()
    import workflow_manager

    artifacts = {"naturalness_verdict": "PASS"}
    reason = workflow_manager._validate_artifact_has_semantic_field(
        "webnovel-write", "Step 3", artifacts
    )
    ok = reason is None
    assert ok is True, f"Ch7 RCA BUG-2: naturalness_verdict 必须被视为 Step 3 合法字段 — {reason}"


def test_step3_whitelist_accepts_naturalness_score_alone():
    _ensure_scripts_on_path()
    import workflow_manager

    artifacts = {"naturalness_score": 88}
    reason = workflow_manager._validate_artifact_has_semantic_field(
        "webnovel-write", "Step 3", artifacts
    )
    ok = reason is None
    assert ok is True, f"naturalness_score 必须被视为 Step 3 合法字段 — {reason}"


def test_step3_whitelist_still_rejects_pure_placeholder():
    _ensure_scripts_on_path()
    import workflow_manager

    artifacts = {"v2": True, "ok": True}
    reason = workflow_manager._validate_artifact_has_semantic_field(
        "webnovel-write", "Step 3", artifacts
    )
    ok = reason is None
    assert ok is False
    assert reason


def test_step3_whitelist_contains_all_documented_fields():
    """SKILL.md Step 0.5 artifact 表必须与 REQUIRED_ARTIFACT_FIELDS 保持一致。

    Round 13 v2 扩展：Step 3 新增 reader_critic_verdict + reader_critic_score
    两个字段（读者锐评 checker 产出），SKILL.md 表已同步登记。
    """
    _ensure_scripts_on_path()
    import workflow_manager

    step3 = workflow_manager.REQUIRED_ARTIFACT_FIELDS["webnovel-write"]["Step 3"]
    required_in_docs = {
        "overall_score",
        "checker_count",
        "internal_avg",
        "review_score",
        "naturalness_verdict",
        "naturalness_score",
        "reader_critic_verdict",
        "reader_critic_score",
    }
    assert required_in_docs.issubset(set(step3)), (
        f"SKILL.md 声明的字段 {required_in_docs - set(step3)} 不在 REQUIRED_ARTIFACT_FIELDS"
    )
