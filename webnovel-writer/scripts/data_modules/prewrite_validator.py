#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


class PrewriteValidator:
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)

    def build(
        self,
        chapter: int,
        review_contract: Dict[str, Any],
        plot_structure: Dict[str, Any],
    ) -> Dict[str, Any]:
        state = json.loads(
            (self.project_root / ".webnovel" / "state.json").read_text(encoding="utf-8")
        )
        pending = state.get("disambiguation_pending") or []
        warnings = state.get("disambiguation_warnings") or []
        return {
            "chapter": chapter,
            "blocking": bool(pending),
            "blocking_reasons": ["存在高优先级 disambiguation_pending"] if pending else [],
            "forbidden_zones": list(review_contract.get("blocking_rules") or []),
            "disambiguation_domain": {
                "pending_count": len(pending),
                "warning_count": len(warnings),
                "allowed_mentions": [
                    item.get("mention", "")
                    for item in warnings
                    if isinstance(item, dict) and item.get("mention")
                ],
            },
            "fulfillment_seed": {
                "planned_nodes": list(plot_structure.get("mandatory_nodes") or []),
                "prohibitions": list(plot_structure.get("prohibitions") or []),
            },
        }
