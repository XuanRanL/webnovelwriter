#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def _ensure_scripts_on_path() -> None:
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def _load_module():
    _ensure_scripts_on_path()
    import data_modules.webnovel as module

    return module


@pytest.mark.parametrize(
    ("tool", "expected_module"),
    [
        ("index", "index_manager"),
        ("state", "state_manager"),
        ("rag", "rag_adapter"),
        ("style", "style_sampler"),
        ("entity", "entity_linker"),
        ("context", "context_manager"),
        ("migrate", "migrate_state_to_sqlite"),
        ("audit", "chapter_audit"),
    ],
)
def test_main_dispatches_data_modules(monkeypatch, tmp_path, tool, expected_module):
    module = _load_module()
    book_root = (tmp_path / "book").resolve()
    called = {}

    monkeypatch.setattr(module, "_resolve_root", lambda _explicit=None: book_root)

    def _fake_run_data_module(module_name, argv):
        called["module_name"] = module_name
        called["argv"] = list(argv)
        return 0

    monkeypatch.setattr(module, "_run_data_module", _fake_run_data_module)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "webnovel",
            tool,
            "stats",
            "--project-root",
            "ignored",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        module.main()

    assert int(exc.value.code or 0) == 0
    assert called["module_name"] == expected_module
    assert called["argv"] == ["--project-root", str(book_root), "stats"]


@pytest.mark.parametrize(
    ("tool", "expected_script"),
    [
        ("workflow", "workflow_manager.py"),
        ("status", "status_reporter.py"),
        ("update-state", "update_state.py"),
        ("backup", "backup_manager.py"),
        ("archive", "archive_manager.py"),
    ],
)
def test_main_dispatches_script_tools(monkeypatch, tmp_path, tool, expected_script):
    module = _load_module()
    book_root = (tmp_path / "book").resolve()
    called = {}

    monkeypatch.setattr(module, "_resolve_root", lambda _explicit=None: book_root)

    def _fake_run_script(script_name, argv):
        called["script_name"] = script_name
        called["argv"] = list(argv)
        return 0

    monkeypatch.setattr(module, "_run_script", _fake_run_script)
    monkeypatch.setattr(sys, "argv", ["webnovel", tool, "inspect"])

    with pytest.raises(SystemExit) as exc:
        module.main()

    assert int(exc.value.code or 0) == 0
    assert called["script_name"] == expected_script
    assert called["argv"] == ["--project-root", str(book_root), "inspect"]


def test_strip_project_root_args_removes_both_forms():
    module = _load_module()
    argv = ["stats", "--project-root", "book", "--project-root=ignored", "--limit", "5"]
    assert module._strip_project_root_args(argv) == ["stats", "--limit", "5"]


def test_resolve_root_prefers_explicit_then_falls_back(monkeypatch, tmp_path):
    module = _load_module()
    explicit_root = (tmp_path / "explicit").resolve()
    default_root = (tmp_path / "default").resolve()

    monkeypatch.setattr(module, "resolve_project_root", lambda arg=None: explicit_root if arg else default_root)

    assert module._resolve_root(str(explicit_root)) == explicit_root
    assert module._resolve_root(None) == default_root


def test_run_data_module_handles_system_exit_and_missing_main(monkeypatch):
    module = _load_module()

    class _WithMain:
        @staticmethod
        def main():
            raise SystemExit(2)

    monkeypatch.setattr(module.importlib, "import_module", lambda _name: _WithMain)
    assert module._run_data_module("index_manager", ["stats"]) == 2

    monkeypatch.setattr(module.importlib, "import_module", lambda _name: SimpleNamespace())
    with pytest.raises(RuntimeError):
        module._run_data_module("index_manager", ["stats"])


def test_run_data_module_returns_zero_when_main_completes(monkeypatch):
    module = _load_module()
    calls = {}

    class _WithMain:
        @staticmethod
        def main():
            calls["argv"] = list(sys.argv)

    monkeypatch.setattr(module.importlib, "import_module", lambda _name: _WithMain)
    assert module._run_data_module("index_manager", ["stats"]) == 0
    assert calls["argv"][0] == "data_modules.index_manager"


def test_run_script_invokes_subprocess(tmp_path, monkeypatch):
    module = _load_module()
    script_path = tmp_path / "helper.py"
    script_path.write_text("print('ok')", encoding="utf-8")
    called = {}

    monkeypatch.setattr(module, "_scripts_dir", lambda: tmp_path)

    def _fake_run(argv):
        called["argv"] = list(argv)
        return SimpleNamespace(returncode=7)

    monkeypatch.setattr(module.subprocess, "run", _fake_run)
    assert module._run_script("helper.py", ["--demo"]) == 7
    assert called["argv"][1] == str(script_path)


def test_run_script_reports_missing_file(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "_scripts_dir", lambda: tmp_path)
    with pytest.raises(FileNotFoundError):
        module._run_script("missing.py", ["--help"])


def test_cmd_where_and_cmd_use(monkeypatch, tmp_path, capsys):
    module = _load_module()
    book_root = (tmp_path / "book").resolve()
    workspace_root = (tmp_path / "workspace").resolve()
    book_root.mkdir(parents=True, exist_ok=True)
    workspace_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(module, "_resolve_root", lambda _explicit=None: book_root)
    assert module.cmd_where(SimpleNamespace(project_root=str(book_root))) == 0
    where_output = capsys.readouterr().out
    assert str(book_root) in where_output

    monkeypatch.setattr(module, "write_current_project_pointer", lambda project_root, workspace_root=None: workspace_root / "pointer.txt")
    monkeypatch.setattr(module, "update_global_registry_current_project", lambda workspace_root=None, project_root=None: workspace_root / "registry.json")
    args = SimpleNamespace(project_root=str(book_root), workspace_root=str(workspace_root))
    assert module.cmd_use(args) == 0
    use_output = capsys.readouterr().out
    assert "pointer.txt" in use_output
    assert "registry.json" in use_output


def test_cmd_use_reports_skipped_when_pointer_and_registry_are_unavailable(monkeypatch, tmp_path, capsys):
    module = _load_module()
    book_root = (tmp_path / "book").resolve()
    book_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(module, "write_current_project_pointer", lambda project_root, workspace_root=None: None)
    monkeypatch.setattr(module, "update_global_registry_current_project", lambda workspace_root=None, project_root=None: None)
    args = SimpleNamespace(project_root=str(book_root), workspace_root=None)
    assert module.cmd_use(args) == 0
    output = capsys.readouterr().out
    assert "(skipped)" in output


def test_cmd_preflight_text_mode_prints_error_detail(monkeypatch, capsys):
    module = _load_module()
    monkeypatch.setattr(
        module,
        "_build_preflight_report",
        lambda _root: {
            "ok": False,
            "checks": [{"name": "project_root", "ok": False, "path": "broken", "error": "bad root"}],
        },
    )
    assert module.cmd_preflight(SimpleNamespace(project_root="broken", format="text")) == 1
    output = capsys.readouterr().out
    assert "detail: bad root" in output


def test_cmd_use_handles_resolve_exceptions(monkeypatch, capsys):
    module = _load_module()

    class _BrokenPath:
        def __init__(self, raw):
            self.raw = raw

        def expanduser(self):
            return self

        def resolve(self):
            raise RuntimeError("cannot resolve")

        def __str__(self):
            return self.raw

    monkeypatch.setattr(module, "normalize_windows_path", lambda raw: _BrokenPath(raw))
    monkeypatch.setattr(module, "write_current_project_pointer", lambda project_root, workspace_root=None: None)
    monkeypatch.setattr(module, "update_global_registry_current_project", lambda workspace_root=None, project_root=None: None)
    args = SimpleNamespace(project_root="book", workspace_root="workspace")
    assert module.cmd_use(args) == 0
    output = capsys.readouterr().out
    assert "(skipped)" in output


def test_main_strips_remainder_separator_before_forwarding(monkeypatch, tmp_path):
    module = _load_module()
    book_root = (tmp_path / "book").resolve()
    called = {}

    monkeypatch.setattr(module, "_resolve_root", lambda _explicit=None: book_root)

    def _fake_run_data_module(module_name, argv):
        called["result"] = (module_name, list(argv))
        return 0

    monkeypatch.setattr(module, "_run_data_module", _fake_run_data_module)
    monkeypatch.setattr(
        sys,
        "argv",
        ["webnovel", "index", "--", "stats", "--project-root", "ignored"],
    )

    with pytest.raises(SystemExit):
        module.main()

    assert called["result"] == ("index_manager", ["--project-root", str(book_root), "stats"])


def test_build_preflight_report_captures_project_root_error(monkeypatch, tmp_path):
    module = _load_module()
    scripts_dir = tmp_path / "scripts"
    skill_root = scripts_dir.parent / "skills" / "webnovel-write"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    skill_root.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "webnovel.py").write_text("", encoding="utf-8")
    (scripts_dir / "extract_chapter_context.py").write_text("", encoding="utf-8")

    monkeypatch.setattr(module, "_scripts_dir", lambda: scripts_dir)
    monkeypatch.setattr(module, "_resolve_root", lambda _explicit=None: (_ for _ in ()).throw(RuntimeError("bad root")))

    report = module._build_preflight_report("broken")
    assert report["ok"] is False
    assert report["project_root_error"] == "bad root"
    failed = next(item for item in report["checks"] if item["name"] == "project_root")
    assert failed["ok"] is False
