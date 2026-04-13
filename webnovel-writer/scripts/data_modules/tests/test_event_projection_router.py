#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from data_modules.event_projection_router import EventProjectionRouter


def test_router_maps_power_breakthrough_to_state_and_memory():
    router = EventProjectionRouter()
    targets = router.route(
        {"event_type": "power_breakthrough", "subject": "xiaoyan", "payload": {}}
    )
    assert targets == ["state", "memory"]


def test_router_maps_relationship_changed_to_index():
    router = EventProjectionRouter()
    targets = router.route(
        {
            "event_type": "relationship_changed",
            "subject": "xiaoyan",
            "payload": {"to": "yaolao"},
        }
    )
    assert "index" in targets


def test_router_collects_required_writers_from_commit_payload():
    router = EventProjectionRouter()
    targets = router.required_writers(
        {
            "accepted_events": [
                {"event_type": "power_breakthrough", "subject": "xiaoyan", "payload": {}},
                {
                    "event_type": "relationship_changed",
                    "subject": "xiaoyan",
                    "payload": {"to": "yaolao"},
                },
            ],
            "summary_text": "本章摘要",
        }
    )
    assert targets == ["index", "memory", "state", "summary"]
