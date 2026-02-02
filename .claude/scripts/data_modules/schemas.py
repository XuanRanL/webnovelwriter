#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pydantic schemas for data_modules outputs.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError, ConfigDict


class EntityAppeared(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    type: str
    mentions: List[str] = Field(default_factory=list)
    confidence: float = 1.0


class EntityNew(BaseModel):
    model_config = ConfigDict(extra="allow")

    suggested_id: str
    name: str
    type: str
    tier: str = "装饰"


class StateChange(BaseModel):
    model_config = ConfigDict(extra="allow")

    entity_id: str
    field: str
    old: Optional[str] = None
    new: str
    reason: Optional[str] = None


class RelationshipNew(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    from_entity: str = Field(alias="from")
    to_entity: str = Field(alias="to")
    type: str
    description: Optional[str] = None
    chapter: Optional[int] = None


class UncertainCandidate(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str
    id: str


class UncertainMention(BaseModel):
    model_config = ConfigDict(extra="allow")

    mention: str
    candidates: List[UncertainCandidate] = Field(default_factory=list)
    confidence: float = 0.0
    adopted: Optional[str] = None


class DataAgentOutput(BaseModel):
    model_config = ConfigDict(extra="allow")

    entities_appeared: List[EntityAppeared] = Field(default_factory=list)
    entities_new: List[EntityNew] = Field(default_factory=list)
    state_changes: List[StateChange] = Field(default_factory=list)
    relationships_new: List[RelationshipNew] = Field(default_factory=list)
    scenes_chunked: int = 0
    uncertain: List[UncertainMention] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ErrorSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    code: str
    message: str
    suggestion: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


def validate_data_agent_output(payload: Dict[str, Any]) -> DataAgentOutput:
    return DataAgentOutput.model_validate(payload)


def format_validation_error(exc: ValidationError) -> Dict[str, Any]:
    return {
        "code": "SCHEMA_VALIDATION_FAILED",
        "message": "数据结构校验失败",
        "details": {"errors": exc.errors()},
        "suggestion": "请检查 data-agent 输出字段是否完整且类型正确",
    }


def normalize_data_agent_output(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    def _ensure_list(key: str):
        value = payload.get(key)
        if value is None:
            payload[key] = []
        elif isinstance(value, list):
            return
        else:
            payload[key] = [value]

    for key in [
        "entities_appeared",
        "entities_new",
        "state_changes",
        "relationships_new",
        "uncertain",
        "warnings",
    ]:
        _ensure_list(key)

    payload.setdefault("scenes_chunked", 0)
    return payload
