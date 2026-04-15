#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json

from data_modules.chapter_commit_service import ChapterCommitService
from data_modules.config import DataModulesConfig
from data_modules.index_manager import IndexManager
from data_modules.memory.store import ScratchpadManager
from data_modules.index_projection_writer import IndexProjectionWriter
from data_modules.memory_projection_writer import MemoryProjectionWriter
from data_modules.state_projection_writer import StateProjectionWriter
from data_modules.summary_projection_writer import SummaryProjectionWriter


def test_state_projection_writer_handles_rejected_commit(tmp_path):
    (tmp_path / ".webnovel").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")
    writer = StateProjectionWriter(tmp_path)
    result = writer.apply({"meta": {"status": "rejected", "chapter": 3}, "state_deltas": []})
    assert result["applied"] is True
    state = json.loads((tmp_path / ".webnovel" / "state.json").read_text(encoding="utf-8"))
    assert state["progress"]["chapter_status"]["3"] == "chapter_rejected"


def test_state_projection_writer_applies_accepted_commit(tmp_path):
    (tmp_path / ".webnovel").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")
    writer = StateProjectionWriter(tmp_path)
    result = writer.apply(
        {
            "meta": {"status": "accepted", "chapter": 3},
            "state_deltas": [{"entity_id": "x", "field": "realm", "new": "斗者"}],
        }
    )
    assert result["applied"] is True
    payload = json.loads((tmp_path / ".webnovel" / "state.json").read_text(encoding="utf-8"))
    assert payload["entity_state"]["x"]["realm"] == "斗者"
    assert payload["progress"]["chapter_status"]["3"] == "chapter_committed"


def test_state_projection_writer_derives_delta_from_power_breakthrough_event(tmp_path):
    (tmp_path / ".webnovel").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")
    writer = StateProjectionWriter(tmp_path)
    result = writer.apply(
        {
            "meta": {"status": "accepted", "chapter": 3},
            "state_deltas": [],
            "accepted_events": [
                {
                    "event_id": "evt-001",
                    "chapter": 3,
                    "event_type": "power_breakthrough",
                    "subject": "xiaoyan",
                    "payload": {"from": "斗者", "to": "斗师"},
                }
            ],
        }
    )

    payload = json.loads((tmp_path / ".webnovel" / "state.json").read_text(encoding="utf-8"))
    assert result["applied"] is True
    assert payload["entity_state"]["xiaoyan"]["realm"] == "斗师"


def test_accepted_commit_updates_state_json_end_to_end(tmp_path):
    (tmp_path / ".webnovel").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")

    service = ChapterCommitService(tmp_path)
    commit_payload = service.build_commit(
        chapter=3,
        review_result={"blocking_count": 0},
        fulfillment_result={"planned_nodes": ["发现陷阱"], "covered_nodes": ["发现陷阱"], "missed_nodes": [], "extra_nodes": []},
        disambiguation_result={"pending": []},
        extraction_result={"state_deltas": [{"entity_id": "x", "field": "realm", "new": "斗者"}], "entity_deltas": [], "accepted_events": []},
    )

    StateProjectionWriter(tmp_path).apply(commit_payload)
    payload = json.loads((tmp_path / ".webnovel" / "state.json").read_text(encoding="utf-8"))
    assert payload["entity_state"]["x"]["realm"] == "斗者"


def test_index_projection_writer_applies_entity_delta(tmp_path):
    cfg = DataModulesConfig.from_project_root(tmp_path)
    cfg.ensure_dirs()
    writer = IndexProjectionWriter(tmp_path)

    result = writer.apply(
        {
            "meta": {"status": "accepted", "chapter": 3},
            "entity_deltas": [
                {
                    "entity_id": "xiaoyan",
                    "canonical_name": "萧炎",
                    "type": "角色",
                    "current": {"realm": "斗者"},
                    "chapter": 3,
                }
            ],
        }
    )

    entity = IndexManager(cfg).get_entity("xiaoyan")
    assert result["applied"] is True
    assert entity["canonical_name"] == "萧炎"
    assert entity["current_json"]["realm"] == "斗者"


def test_index_projection_writer_derives_relationship_from_event(tmp_path):
    cfg = DataModulesConfig.from_project_root(tmp_path)
    cfg.ensure_dirs()
    writer = IndexProjectionWriter(tmp_path)

    result = writer.apply(
        {
            "meta": {"status": "accepted", "chapter": 3},
            "entity_deltas": [],
            "accepted_events": [
                {
                    "event_id": "evt-001",
                    "chapter": 3,
                    "event_type": "relationship_changed",
                    "subject": "xiaoyan",
                    "payload": {
                        "to_entity": "yaolao",
                        "relationship_type": "师徒",
                        "description": "关系正式确立",
                    },
                }
            ],
        }
    )

    rels = IndexManager(cfg).get_relationship_between("xiaoyan", "yaolao")
    assert result["applied"] is True
    assert rels[0]["type"] == "师徒"


def test_index_projection_writer_derives_artifact_entity_from_event(tmp_path):
    cfg = DataModulesConfig.from_project_root(tmp_path)
    cfg.ensure_dirs()
    writer = IndexProjectionWriter(tmp_path)

    result = writer.apply(
        {
            "meta": {"status": "accepted", "chapter": 3},
            "entity_deltas": [],
            "accepted_events": [
                {
                    "event_id": "evt-002",
                    "chapter": 3,
                    "event_type": "artifact_obtained",
                    "subject": "黑戒",
                    "payload": {
                        "artifact_id": "black_ring",
                        "name": "黑戒",
                        "owner": "xiaoyan",
                    },
                }
            ],
        }
    )

    entity = IndexManager(cfg).get_entity("black_ring")
    assert result["applied"] is True
    assert entity["canonical_name"] == "黑戒"
    assert entity["current_json"]["holder"] == "xiaoyan"


def test_summary_projection_writer_writes_summary_markdown(tmp_path):
    cfg = DataModulesConfig.from_project_root(tmp_path)
    cfg.ensure_dirs()
    writer = SummaryProjectionWriter(tmp_path)

    result = writer.apply(
        {
            "meta": {"status": "accepted", "chapter": 3},
            "summary_text": "本章主角发现陷阱并决定隐忍。",
        }
    )

    summary_path = tmp_path / ".webnovel" / "summaries" / "ch0003.md"
    assert result["applied"] is True
    assert summary_path.is_file()
    assert "剧情摘要" in summary_path.read_text(encoding="utf-8")


def test_memory_projection_writer_maps_commit_into_scratchpad(tmp_path):
    cfg = DataModulesConfig.from_project_root(tmp_path)
    cfg.ensure_dirs()
    writer = MemoryProjectionWriter(tmp_path)

    result = writer.apply(
        {
            "meta": {"status": "accepted", "chapter": 3},
            "state_deltas": [
                {"entity_id": "xiaoyan", "field": "realm", "old": "斗者", "new": "斗师"}
            ],
            "entity_deltas": [],
            "accepted_events": [],
        }
    )

    store = ScratchpadManager(cfg)
    chars = store.query(category="character_state", status="active")
    assert result["applied"] is True
    assert any(x.subject == "xiaoyan" and x.field == "realm" for x in chars)


def test_memory_projection_writer_maps_open_loop_event_into_scratchpad(tmp_path):
    cfg = DataModulesConfig.from_project_root(tmp_path)
    cfg.ensure_dirs()
    writer = MemoryProjectionWriter(tmp_path)

    result = writer.apply(
        {
            "meta": {"status": "accepted", "chapter": 3},
            "state_deltas": [],
            "entity_deltas": [],
            "accepted_events": [
                {
                    "event_id": "evt-001",
                    "chapter": 3,
                    "event_type": "open_loop_created",
                    "subject": "三年之约",
                    "payload": {"content": "三年之约"},
                }
            ],
        }
    )

    store = ScratchpadManager(cfg)
    loops = store.query(category="open_loop", status="active")
    assert result["applied"] is True
    assert any("三年之约" in x.subject for x in loops)
