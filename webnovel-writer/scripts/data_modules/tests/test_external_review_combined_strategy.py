#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 3.5 combined review strategy regression tests.

Root cause locked here: the old external review path sent the full project
context + chapter text once per dimension, so one model consumed the same large
prompt 13 times. Round 21.4 makes combined (one request per model returning all
13 dimension_reports) the default, with legacy split kept as fallback.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _ensure_scripts_on_path() -> None:
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def _load_external_review():
    _ensure_scripts_on_path()
    import external_review as module

    return module


def _make_project(tmp_path: Path) -> Path:
    project = tmp_path / "book"
    (project / ".webnovel" / "tmp").mkdir(parents=True)
    (project / "正文").mkdir(parents=True)
    (project / "正文" / "第0001章-测试.md").write_text(
        "第一句自然。这里有一句真实引用，用来测试 quote 校验。", encoding="utf-8"
    )
    context = {
        "outline_excerpt": "本章测试外部审查 combined 策略。" + ("上下文" * 600),
        "protagonist_card": "主角稳定。",
        "golden_finger_card": "金手指稳定。",
        "world_settings": "世界观稳定。",
        "prev_chapters_text": "前章摘要稳定。",
    }
    (project / ".webnovel" / "tmp" / "external_context_ch0001.json").write_text(
        json.dumps(context, ensure_ascii=False), encoding="utf-8"
    )
    return project


def _args(project: Path, strategy: str):
    return argparse.Namespace(
        project_root=str(project),
        chapter=1,
        model_key="qwen3.6-plus",
        max_concurrent=1,
        dimension_strategy=strategy,
        no_merge_partial=True,
    )


def _combined_payload(er, omit_dimension: str | None = None):
    reports = []
    for key in er.DIMENSION_ORDER:
        if key == omit_dimension:
            continue
        reports.append(
            {
                "dimension": key,
                "score": 88,
                "issues": (
                    [
                        {
                            "id": "PQ_001",
                            "type": "PROSE_FLAT",
                            "severity": "low",
                            "location": "测试句",
                            "description": "轻微测试问题",
                            "suggestion": "保持自然表达",
                            "quote": "一句真实引用",
                        }
                    ]
                    if key == "prose_quality"
                    else []
                ),
                "summary": f"{key} ok",
            }
        )
    return {"overall_score": 88, "dimension_reports": reports, "issues": [], "summary": "ok"}


def test_combined_strategy_writes_13_dimensions_with_one_provider_call(tmp_path, monkeypatch):
    er = _load_external_review()
    project = _make_project(tmp_path)
    calls = []

    def fake_try_provider_chain(*args, **kwargs):
        calls.append(kwargs.get("parse_mode"))
        return (
            _combined_payload(er),
            "Qwen3.6-Plus",
            "openclawroot",
            "qwen3.6-plus",
            True,
            {"prompt_tokens": 1000, "completion_tokens": 500},
            [{"provider": "openclawroot", "attempt": 1, "result": "success"}],
        )

    monkeypatch.setattr(er, "try_provider_chain", fake_try_provider_chain)

    er._run_single_model(_args(project, "combined"), {"openclawroot": "dummy"})

    out_path = project / ".webnovel" / "tmp" / "external_review_qwen3.6-plus_ch0001.json"
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert calls == ["combined"]
    assert data["api_meta"]["review_strategy"] == "combined"
    assert data["api_meta"]["prompt_tokens"] == 1000
    assert data["metrics"]["dimensions_ok"] == 13
    assert len(data["dimension_reports"]) == 13
    assert data["overall_score"] == 88


def test_auto_strategy_falls_back_to_split_when_combined_misses_dimension(tmp_path, monkeypatch):
    er = _load_external_review()
    project = _make_project(tmp_path)
    calls = []

    def fake_try_provider_chain(*args, **kwargs):
        parse_mode = kwargs.get("parse_mode")
        calls.append(parse_mode)
        if parse_mode == "combined":
            return (
                _combined_payload(er, omit_dimension="reader_flow"),
                "Qwen3.6-Plus",
                "openclawroot",
                "qwen3.6-plus",
                True,
                {"prompt_tokens": 1000, "completion_tokens": 500},
                [{"provider": "openclawroot", "attempt": 1, "result": "success"}],
            )
        return (
            {"score": 90, "issues": [], "summary": "split ok"},
            "Qwen3.6-Plus",
            "openclawroot",
            "qwen3.6-plus",
            True,
            {"prompt_tokens": 10, "completion_tokens": 2},
            [{"provider": "openclawroot", "attempt": 1, "result": "success"}],
        )

    monkeypatch.setattr(er, "try_provider_chain", fake_try_provider_chain)

    er._run_single_model(_args(project, "auto"), {"openclawroot": "dummy"})

    out_path = project / ".webnovel" / "tmp" / "external_review_qwen3.6-plus_ch0001.json"
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert calls.count("combined") == 1
    assert calls.count("dimension") == 13
    assert data["api_meta"]["review_strategy"] == "split"
    assert data["api_meta"]["strategy_fallback_reason"] == "combined_incomplete:12/13"
    assert data["metrics"]["dimensions_ok"] == 13
    assert data["overall_score"] == 90


def test_split_strategy_skips_combined_path(tmp_path, monkeypatch):
    er = _load_external_review()
    project = _make_project(tmp_path)
    calls = []

    def fake_try_provider_chain(*args, **kwargs):
        calls.append(kwargs.get("parse_mode"))
        return (
            {"score": 86, "issues": [], "summary": "split ok"},
            "Qwen3.6-Plus",
            "openclawroot",
            "qwen3.6-plus",
            True,
            {"prompt_tokens": 10, "completion_tokens": 2},
            [{"provider": "openclawroot", "attempt": 1, "result": "success"}],
        )

    monkeypatch.setattr(er, "try_provider_chain", fake_try_provider_chain)

    er._run_single_model(_args(project, "split"), {"openclawroot": "dummy"})

    assert calls == ["dimension"] * 13
    out_path = project / ".webnovel" / "tmp" / "external_review_qwen3.6-plus_ch0001.json"
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["api_meta"]["review_strategy"] == "split"
    assert data["metrics"]["dimensions_ok"] == 13


def test_gemini_uses_api666_preview_before_openclawroot_fallback():
    er = _load_external_review()

    providers = er.MODELS["gemini-3.1-pro"]["providers"]

    assert providers[0]["provider"] == "api666"
    assert providers[0]["id"] == "gemini-3.1-pro-preview"
    assert providers[0]["max_tokens"] == 65536
    assert providers[1]["provider"] == "openclawroot"
    assert providers[1]["id"] == "gemini-3.1-pro-high"
    assert "API666_API_KEY" in er.PROVIDERS["api666"]["env_key_names"]


def test_gemini_api666_payload_keeps_max_tokens_and_thinking(monkeypatch):
    er = _load_external_review()
    captured = {}

    class DummyResponse:
        status_code = 200
        text = ""

        def json(self):
            return {
                "model": "gemini-3.1-pro-preview",
                "choices": [{"message": {"content": '{"score":88,"issues":[],"summary":"ok"}'}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }

    class DummySession:
        def post(self, base_url, headers, json, timeout):
            captured["base_url"] = base_url
            captured["payload"] = json
            return DummyResponse()

        def close(self):
            pass

    class DummyLimiter:
        def acquire(self):
            pass

        def release(self):
            pass

    monkeypatch.setattr(er.requests, "Session", lambda: DummySession())
    monkeypatch.setattr(er.ProviderRateLimiter, "get", classmethod(lambda cls, provider_name, rpm=None: DummyLimiter()))

    raw, error, model_actual, usage, chain = er.call_api(
        er.PROVIDERS["api666"]["base_url"],
        "dummy",
        "gemini-3.1-pro-preview",
        "system",
        "user",
        timeout=3,
        max_retries=0,
        provider_name="api666",
        max_tokens=65536,
    )

    assert error is None
    assert model_actual == "gemini-3.1-pro-preview"
    assert captured["base_url"] == "https://api-666.cc/v1/chat/completions"
    assert captured["payload"]["max_tokens"] == 65536
    assert captured["payload"]["thinking_budget"] == 16384
    assert "enable_thinking" not in captured["payload"]


def test_kimi_siliconflow_fallback_payload_enables_thinking(monkeypatch):
    er = _load_external_review()
    captured = {}

    class DummyResponse:
        status_code = 200
        text = ""

        def json(self):
            return {
                "model": "Pro/moonshotai/Kimi-K2.5",
                "choices": [{"message": {"content": '{"score":88,"issues":[],"summary":"ok"}'}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }

    class DummySession:
        def post(self, base_url, headers, json, timeout):
            captured["base_url"] = base_url
            captured["payload"] = json
            return DummyResponse()

        def close(self):
            pass

    class DummyLimiter:
        def acquire(self):
            pass

        def release(self):
            pass

    monkeypatch.setattr(er.requests, "Session", lambda: DummySession())
    monkeypatch.setattr(er.ProviderRateLimiter, "get", classmethod(lambda cls, provider_name, rpm=None: DummyLimiter()))

    raw, error, model_actual, usage, chain = er.call_api(
        er.PROVIDERS["siliconflow"]["base_url"],
        "dummy",
        "Pro/moonshotai/Kimi-K2.5",
        "system",
        "user",
        timeout=3,
        max_retries=0,
        provider_name="siliconflow",
        max_tokens=32768,
    )

    assert error is None
    assert model_actual == "Pro/moonshotai/Kimi-K2.5"
    assert captured["payload"]["max_tokens"] == 32768
    assert captured["payload"]["enable_thinking"] is True
    assert "thinking_budget" not in captured["payload"]


def test_model_provider_max_tokens_are_declared_caps():
    er = _load_external_review()

    known_limited_routes = {
        ("ark-coding", "deepseek-v3.2"),
        ("ark-coding", "kimi-k2.5"),
        ("siliconflow", "Pro/moonshotai/Kimi-K2.5"),
    }

    for model_key, spec in er.MODELS.items():
        for provider in spec["providers"]:
            route = (provider["provider"], provider["id"])
            max_tokens = provider.get("max_tokens", 65536)
            expected = 32768 if route in known_limited_routes else 65536
            assert max_tokens == expected, f"{model_key}:{route} max_tokens={max_tokens}"


def test_all_external_review_routes_apply_reasoning_payload(monkeypatch):
    er = _load_external_review()
    captured = []

    class DummyResponse:
        status_code = 200
        text = ""

        def __init__(self, model_id):
            self.model_id = model_id

        def json(self):
            return {
                "model": self.model_id,
                "choices": [{"message": {"content": '{"score":88,"issues":[],"summary":"ok"}'}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }

    class DummySession:
        def post(self, base_url, headers, json, timeout):
            captured.append(json)
            return DummyResponse(json["model"])

        def close(self):
            pass

    class DummyLimiter:
        def acquire(self):
            pass

        def release(self):
            pass

    monkeypatch.setattr(er.requests, "Session", lambda: DummySession())
    monkeypatch.setattr(er.ProviderRateLimiter, "get", classmethod(lambda cls, provider_name, rpm=None: DummyLimiter()))

    for spec in er.MODELS.values():
        for provider in spec["providers"]:
            provider_name = provider["provider"]
            model_id = provider["id"]
            max_tokens = provider.get("max_tokens", 65536)
            er.call_api(
                er.PROVIDERS[provider_name]["base_url"],
                "dummy",
                model_id,
                "system",
                "user",
                timeout=3,
                max_retries=0,
                provider_name=provider_name,
                max_tokens=max_tokens,
            )

            payload = captured[-1]
            model_lower = model_id.lower()
            assert payload["max_tokens"] == max_tokens
            if provider_name == "ark-coding":
                assert payload["thinking"] == {"type": "enabled"}
                assert "enable_thinking" not in payload
                continue
            if "gpt-" in model_lower:
                assert payload["reasoning_effort"] == "high"
            if "gemini" in model_lower:
                assert payload["thinking_budget"] == 16384
            if any(t in model_lower for t in ("qwen", "deepseek", "doubao", "glm", "mimo", "minimax", "kimi")):
                assert payload["enable_thinking"] is True
            if "claude" in model_lower:
                assert payload["thinking"] == {"type": "enabled", "budget_tokens": 16384}
