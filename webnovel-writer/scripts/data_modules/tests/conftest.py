from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path

import pytest


def _manual_tmp_root() -> Path:
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        root = Path(local_appdata) / "Temp" / "webnovel-writer-pytest-manual"
    else:
        root = Path(__file__).resolve().parents[4] / ".tmp" / "webnovel-writer-pytest-manual"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_mkdtemp(suffix: str | None = None, prefix: str | None = None, dir: str | None = None) -> str:
    root = Path(dir) if dir else _manual_tmp_root()
    root.mkdir(parents=True, exist_ok=True)
    prefix = prefix or "tmp"
    suffix = suffix or ""
    path = root / f"{prefix}{uuid.uuid4().hex}{suffix}"
    path.mkdir()
    return str(path)


tempfile.tempdir = str(_manual_tmp_root())
tempfile.mkdtemp = _safe_mkdtemp


@pytest.fixture
def tmp_path() -> Path:
    path = Path(_safe_mkdtemp(prefix="tmp_path_"))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
