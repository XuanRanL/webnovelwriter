#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import sys
from pathlib import Path

from data_modules.event_log_store import EventLogStore


def _ensure_scripts_on_path() -> None:
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def test_event_log_store_writes_per_chapter_file_and_sqlite_mirror(tmp_path):
    store = EventLogStore(tmp_path)
    store.write_events(
        3,
        [
            {
                "event_id": "evt-001",
                "chapter": 3,
                "event_type": "open_loop_created",
                "subject": "三年之约",
                "payload": {},
            }
        ],
    )
    assert (tmp_path / ".story-system" / "events" / "chapter_003.events.json").is_file()

    conn = sqlite3.connect(tmp_path / ".webnovel" / "index.db")
    try:
        row = conn.execute(
            "SELECT event_id, chapter, event_type FROM story_events"
        ).fetchone()
    finally:
        conn.close()
    assert row == ("evt-001", 3, "open_loop_created")


def test_event_log_store_ignores_duplicate_event_id(tmp_path):
    store = EventLogStore(tmp_path)
    event = {
        "event_id": "evt-001",
        "chapter": 3,
        "event_type": "open_loop_created",
        "subject": "三年之约",
        "payload": {},
    }
    store.write_events(3, [event])
    store.write_events(3, [event])

    conn = sqlite3.connect(tmp_path / ".webnovel" / "index.db")
    try:
        count = conn.execute("SELECT COUNT(*) FROM story_events").fetchone()[0]
    finally:
        conn.close()
    assert count == 1


def test_story_events_cli_reads_chapter_file(tmp_path, monkeypatch, capsys):
    _ensure_scripts_on_path()
    events_dir = tmp_path / ".story-system" / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    (events_dir / "chapter_003.events.json").write_text(
        '[{"event_id":"evt-001","chapter":3,"event_type":"open_loop_created","subject":"三年之约","payload":{}}]',
        encoding="utf-8",
    )

    from story_events import main

    monkeypatch.setattr(
        sys,
        "argv",
        ["story_events", "--project-root", str(tmp_path), "--chapter", "3"],
    )
    main()

    out = capsys.readouterr().out
    assert "open_loop_created" in out
