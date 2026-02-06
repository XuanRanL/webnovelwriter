#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared observability helpers for data modules.
"""

from __future__ import annotations

import sys
from typing import Optional


def safe_log_tool_call(
    logger,
    *,
    tool_name: str,
    success: bool,
    retry_count: int = 0,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    chapter: Optional[int] = None,
) -> None:
    try:
        logger.log_tool_call(
            tool_name,
            success,
            retry_count=retry_count,
            error_code=error_code,
            error_message=error_message,
            chapter=chapter,
        )
    except Exception as exc:
        print(
            f"[observability] failed to log tool call {tool_name}: {exc}",
            file=sys.stderr,
        )

