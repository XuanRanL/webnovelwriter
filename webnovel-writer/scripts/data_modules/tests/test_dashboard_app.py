#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import importlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient


def test_dashboard_app_imports_without_scripts_path(monkeypatch, tmp_path):
    plugin_root = Path(__file__).resolve().parents[3]
    scripts_dir = plugin_root / "scripts"

    project_root = tmp_path / "book"
    (project_root / ".webnovel").mkdir(parents=True, exist_ok=True)
    (project_root / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")

    clean_path = []
    scripts_resolved = scripts_dir.resolve()
    for entry in sys.path:
        try:
            if Path(entry).resolve() == scripts_resolved:
                continue
        except Exception:
            pass
        clean_path.append(entry)

    if str(plugin_root) not in clean_path:
        clean_path.insert(0, str(plugin_root))

    monkeypatch.setattr(sys, "path", clean_path)
    for name in list(sys.modules):
        if name == "dashboard.app" or name == "data_modules" or name.startswith("data_modules."):
            sys.modules.pop(name, None)

    module = importlib.import_module("dashboard.app")
    app = module.create_app(project_root)
    client = TestClient(app)

    response = client.get("/api/story-runtime/health")
    assert response.status_code == 200
