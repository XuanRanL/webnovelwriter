#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import io
import sys
from pathlib import Path

import pytest


def _load_module():
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from data_modules import cli_args

    return cli_args


def test_extract_flag_value_uses_last_occurrence():
    mod = _load_module()
    value, rest = mod._extract_flag_value(
        ["cmd", "--project-root", "first", "sub", "--project-root=second"],
        "--project-root",
    )
    assert value == "second"
    assert rest == ["cmd", "sub"]


def test_extract_flag_value_keeps_dangling_flag_for_argparse():
    mod = _load_module()
    value, rest = mod._extract_flag_value(["cmd", "--project-root"], "--project-root")
    assert value is None
    assert rest == ["cmd", "--project-root"]


def test_normalize_global_project_root_moves_flag_before_subcommand():
    mod = _load_module()
    argv = ["index", "stats", "--project-root", "book", "--limit", "5"]
    assert mod.normalize_global_project_root(argv) == [
        "--project-root",
        "book",
        "index",
        "stats",
        "--limit",
        "5",
    ]


def test_load_json_arg_supports_inline_file_and_stdin(tmp_path, monkeypatch):
    mod = _load_module()

    assert mod.load_json_arg('{"chapter": 1}') == {"chapter": 1}

    payload_path = tmp_path / "payload.json"
    payload_path.write_text('{"chapter": 2}', encoding="utf-8")
    assert mod.load_json_arg(f"@{payload_path}") == {"chapter": 2}

    monkeypatch.setattr(sys, "stdin", io.StringIO('{"chapter": 3}'))
    assert mod.load_json_arg("@-") == {"chapter": 3}


def test_load_json_arg_rejects_empty_at_reference():
    mod = _load_module()
    with pytest.raises(ValueError):
        mod.load_json_arg("@")


def test_load_json_arg_rejects_missing_raw():
    mod = _load_module()
    with pytest.raises(ValueError):
        mod.load_json_arg(None)
