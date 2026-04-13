#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json

from data_modules.prewrite_validator import PrewriteValidator


def test_prewrite_validator_builds_disambiguation_domain_and_fulfillment_seed(tmp_path):
    project_root = tmp_path
    (project_root / ".webnovel").mkdir(parents=True, exist_ok=True)
    (project_root / ".webnovel" / "state.json").write_text(
        json.dumps(
            {
                "disambiguation_pending": [],
                "disambiguation_warnings": [{"mention": "宗主"}],
                "chapter_meta": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    review_contract = {"must_check": ["发现陷阱"], "blocking_rules": ["不可提前摊牌"]}
    plot_structure = {"mandatory_nodes": ["发现陷阱"], "prohibitions": ["不可提前摊牌"]}

    payload = PrewriteValidator(project_root).build(
        chapter=3,
        review_contract=review_contract,
        plot_structure=plot_structure,
    )

    assert payload["blocking"] is False
    assert payload["fulfillment_seed"]["planned_nodes"] == ["发现陷阱"]
    assert payload["disambiguation_domain"]["pending_count"] == 0


def test_prewrite_validator_blocks_when_required_contracts_missing(tmp_path):
    project_root = tmp_path
    (project_root / ".webnovel").mkdir(parents=True, exist_ok=True)
    (project_root / ".webnovel" / "state.json").write_text(
        json.dumps(
            {
                "disambiguation_pending": [],
                "disambiguation_warnings": [],
                "chapter_meta": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = PrewriteValidator(project_root).build(
        chapter=3,
        review_contract={},
        plot_structure={},
        story_contract={
            "master_setting": {},
            "chapter_brief": {},
            "volume_brief": {},
            "review_contract": {},
        },
    )

    assert payload["blocking"] is True
    assert "missing_contracts" in payload
    assert set(payload["missing_contracts"]) >= {"master_setting", "review_contract"}
