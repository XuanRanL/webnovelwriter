#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VectorProjectionWriter 单元测试。"""
from data_modules.vector_projection_writer import VectorProjectionWriter


def test_event_to_text_formats_power_breakthrough():
    writer = VectorProjectionWriter.__new__(VectorProjectionWriter)
    event = {
        "event_type": "power_breakthrough",
        "chapter": 47,
        "subject": "韩立",
        "payload": {"field": "realm", "new": "筑基初期"},
    }
    text = writer._event_to_text(event)
    assert "第47章" in text
    assert "韩立" in text
    assert "筑基初期" in text


def test_delta_to_text_formats_relationship():
    writer = VectorProjectionWriter.__new__(VectorProjectionWriter)
    delta = {
        "from_entity": "韩立",
        "to_entity": "陈巧倩",
        "relationship_type": "合作",
        "chapter": 47,
    }
    text = writer._delta_to_text(delta)
    assert "第47章" in text
    assert "韩立" in text
    assert "陈巧倩" in text
    assert "合作" in text


def test_collect_chunks_from_commit():
    writer = VectorProjectionWriter.__new__(VectorProjectionWriter)
    payload = {
        "meta": {"chapter": 47, "status": "accepted"},
        "accepted_events": [
            {
                "event_type": "power_breakthrough",
                "chapter": 47,
                "subject": "韩立",
                "payload": {"field": "realm", "new": "筑基初期"},
            },
        ],
        "entity_deltas": [
            {
                "from_entity": "韩立",
                "to_entity": "陈巧倩",
                "relationship_type": "合作",
                "chapter": 47,
            },
        ],
    }
    chunks = writer._collect_chunks(payload)
    assert len(chunks) == 2
    assert chunks[0]["chunk_type"] == "event"
    assert chunks[1]["chunk_type"] == "entity_delta"


def test_rejected_commit_returns_not_applied():
    writer = VectorProjectionWriter.__new__(VectorProjectionWriter)
    writer.project_root = None
    result = writer.apply({"meta": {"status": "rejected", "chapter": 1}})
    assert result["applied"] is False
