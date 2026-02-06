#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Runtime compatibility helpers.
"""

from __future__ import annotations

import os
import sys


def enable_windows_utf8_stdio(*, skip_in_pytest: bool = False) -> bool:
    """Enable UTF-8 stdio wrappers on Windows.

    Returns:
        True if wrapping was applied, False otherwise.
    """
    if sys.platform != "win32":
        return False
    if skip_in_pytest and os.environ.get("PYTEST_CURRENT_TEST"):
        return False

    stdout_encoding = str(getattr(sys.stdout, "encoding", "") or "").lower()
    stderr_encoding = str(getattr(sys.stderr, "encoding", "") or "").lower()
    if stdout_encoding == "utf-8" and stderr_encoding == "utf-8":
        return False

    try:
        import io

        if hasattr(sys.stdout, "buffer"):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        if hasattr(sys.stderr, "buffer"):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
        return True
    except Exception:
        return False

