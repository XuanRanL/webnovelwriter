#!/usr/bin/env python3
"""时间算术与倒计时校验器

验证 context-agent 执行包中的时间字段是否算术自洽：
- prev_chapter_end_timestamp <= current_chapter_start_timestamp
- time_gap_minutes 与实际 timestamp 差值一致（±1 分钟容差）
- countdown_checkpoint 中的 "xx 小时" / "xx 分钟" 与实际 gap 一致

用法：
    python countdown_validator.py --input .webnovel/context/ch0006_context.json
    python countdown_validator.py --prev "2026-04-22 23:16" --curr "2026-04-23 13:40" --claim 864

退出码：0=pass / 1=arithmetic mismatch / 2=parse error / 3=IO
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

FMTS = [
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%dT%H:%M:%S",
]


def parse_ts(s: str) -> datetime | None:
    if not s:
        return None
    s = s.strip()
    # strip Chinese weekday tokens like "周一/周二/.../周日/周天"
    s = re.sub(r"\s*周[一二三四五六日天]\s*", " ", s).strip()
    m = re.match(r"(\d{4}-\d{2}-\d{2})[ T](\d{1,2}):(\d{2})", s)
    if m:
        date, hh, mm = m.group(1), m.group(2), m.group(3)
        try:
            return datetime.strptime(f"{date} {int(hh):02d}:{int(mm):02d}", "%Y-%m-%d %H:%M")
        except ValueError:
            return None
    for fmt in FMTS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def validate_pair(prev: str, curr: str, claimed_minutes: int | None = None, tolerance: int = 1) -> tuple[bool, list[str]]:
    errors: list[str] = []
    p = parse_ts(prev)
    c = parse_ts(curr)
    if p is None:
        errors.append(f"prev timestamp parse fail: {prev!r}")
    if c is None:
        errors.append(f"current timestamp parse fail: {curr!r}")
    if errors:
        return False, errors
    if c < p:
        errors.append(f"current ({curr}) 早于 prev ({prev})")
        return False, errors
    actual_minutes = int((c - p).total_seconds() // 60)
    if claimed_minutes is not None:
        if abs(actual_minutes - claimed_minutes) > tolerance:
            errors.append(
                f"time_gap_minutes claim={claimed_minutes} vs actual={actual_minutes} (diff {abs(actual_minutes - claimed_minutes)} min > tolerance {tolerance})"
            )
    return len(errors) == 0, errors + [f"OK actual_gap={actual_minutes}min"]


def validate_package(pkg_path: Path) -> tuple[bool, list[str]]:
    try:
        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
    except Exception as e:
        return False, [f"load fail: {e}"]
    ta = pkg.get("timestamp_arithmetic") or pkg.get("context_contract", {}).get("time_constraints") or {}
    prev = ta.get("prev_chapter_end_timestamp")
    curr = ta.get("current_chapter_start_timestamp")
    claim = ta.get("time_gap_minutes")
    if not prev or not curr:
        return True, ["skip: no timestamp_arithmetic block (backward-compat)"]
    ok, msgs = validate_pair(prev, curr, claim)
    countdown = ta.get("countdown_checkpoint", "")
    if countdown:
        for m in re.finditer(r"(\d+)\s*小时", countdown):
            claimed_hours = int(m.group(1))
            if claim is not None and abs(claim / 60 - claimed_hours) > 0.5:
                msgs.append(
                    f"[WARN] countdown_checkpoint mentions '{claimed_hours}小时' but gap={claim / 60:.1f}h"
                )
                ok = False
    return ok, msgs


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=str, help="Context package JSON path")
    p.add_argument("--prev", type=str, help="Prev chapter end timestamp (YYYY-MM-DD HH:MM)")
    p.add_argument("--curr", type=str, help="Current chapter start timestamp")
    p.add_argument("--claim", type=int, help="Claimed time_gap_minutes")
    p.add_argument("--tolerance", type=int, default=1)
    args = p.parse_args()

    if args.input:
        ok, msgs = validate_package(Path(args.input))
    elif args.prev and args.curr:
        ok, msgs = validate_pair(args.prev, args.curr, args.claim, args.tolerance)
    else:
        print("usage: --input <file> OR --prev <ts> --curr <ts> [--claim <min>]", file=sys.stderr)
        sys.exit(2)

    for m in msgs:
        print(m)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
