#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
from pathlib import Path

import pytest


def _ensure_scripts_on_path() -> None:
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def _load_webnovel_module():
    _ensure_scripts_on_path()
    import data_modules.webnovel as webnovel_module

    return webnovel_module


def test_init_does_not_resolve_existing_project_root(monkeypatch):
    module = _load_webnovel_module()

    called = {}

    def _fake_run_script(script_name, argv):
        called["script_name"] = script_name
        called["argv"] = list(argv)
        return 0

    def _fail_resolve(_explicit_project_root=None):
        raise AssertionError("init 子命令不应触发 project_root 解析")

    monkeypatch.setenv("WEBNOVEL_PROJECT_ROOT", r"D:\invalid\root")
    monkeypatch.setattr(module, "_run_script", _fake_run_script)
    monkeypatch.setattr(module, "_resolve_root", _fail_resolve)
    monkeypatch.setattr(sys, "argv", ["webnovel", "init", "proj-dir", "测试书", "修仙"])

    with pytest.raises(SystemExit) as exc:
        module.main()

    assert int(exc.value.code or 0) == 0
    assert called["script_name"] == "init_project.py"
    assert called["argv"] == ["proj-dir", "测试书", "修仙"]


def test_extract_context_forwards_with_resolved_project_root(monkeypatch, tmp_path):
    module = _load_webnovel_module()

    book_root = (tmp_path / "book").resolve()
    called = {}

    def _fake_resolve(explicit_project_root=None):
        return book_root

    def _fake_run_script(script_name, argv):
        called["script_name"] = script_name
        called["argv"] = list(argv)
        return 0

    monkeypatch.setattr(module, "_resolve_root", _fake_resolve)
    monkeypatch.setattr(module, "_run_script", _fake_run_script)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "webnovel",
            "--project-root",
            str(tmp_path),
            "extract-context",
            "--chapter",
            "12",
            "--format",
            "json",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        module.main()

    assert int(exc.value.code or 0) == 0
    assert called["script_name"] == "extract_chapter_context.py"
    assert called["argv"] == [
        "--project-root",
        str(book_root),
        "--chapter",
        "12",
        "--format",
        "json",
    ]


def test_preflight_succeeds_for_valid_project_root(monkeypatch, tmp_path, capsys):
    module = _load_webnovel_module()

    project_root = tmp_path / "book"
    (project_root / ".webnovel").mkdir(parents=True, exist_ok=True)
    (project_root / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["webnovel", "--project-root", str(project_root), "preflight"])

    with pytest.raises(SystemExit) as exc:
        module.main()

    captured = capsys.readouterr()
    assert int(exc.value.code or 0) == 0
    assert "OK project_root" in captured.out
    assert str(project_root.resolve()) in captured.out


def test_preflight_fails_when_required_scripts_are_missing(monkeypatch, tmp_path, capsys):
    module = _load_webnovel_module()

    project_root = tmp_path / "book"
    (project_root / ".webnovel").mkdir(parents=True, exist_ok=True)
    (project_root / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")

    fake_scripts_dir = tmp_path / "fake-scripts"
    fake_scripts_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(module, "_scripts_dir", lambda: fake_scripts_dir)
    monkeypatch.setattr(sys, "argv", ["webnovel", "--project-root", str(project_root), "preflight", "--format", "json"])

    with pytest.raises(SystemExit) as exc:
        module.main()

    captured = capsys.readouterr()
    assert int(exc.value.code or 0) == 1
    assert '"ok": false' in captured.out
    assert '"name": "entry_script"' in captured.out


def test_quality_trend_report_writes_to_book_root_when_input_is_workspace_root(tmp_path, monkeypatch):
    _ensure_scripts_on_path()
    import quality_trend_report as quality_trend_report_module

    workspace_root = (tmp_path / "workspace").resolve()
    book_root = (workspace_root / "凡人资本论").resolve()

    (workspace_root / ".claude").mkdir(parents=True, exist_ok=True)
    (workspace_root / ".claude" / ".webnovel-current-project").write_text(str(book_root), encoding="utf-8")

    (book_root / ".webnovel").mkdir(parents=True, exist_ok=True)
    (book_root / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")

    output_path = workspace_root / "report.md"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "quality_trend_report",
            "--project-root",
            str(workspace_root),
            "--limit",
            "1",
            "--output",
            str(output_path),
        ],
    )

    quality_trend_report_module.main()

    assert output_path.is_file()
    assert (book_root / ".webnovel" / "index.db").is_file()
    assert not (workspace_root / ".webnovel" / "index.db").exists()



def test_index_aggregate_review_results_forwards_with_resolved_project_root(monkeypatch, tmp_path):
    module = _load_webnovel_module()

    book_root = (tmp_path / "book").resolve()
    called = {}

    def _fake_resolve(explicit_project_root=None):
        return book_root

    def _fake_run_data_module(module_name, argv):
        called["module_name"] = module_name
        called["argv"] = list(argv)
        return 0

    monkeypatch.setattr(module, "_resolve_root", _fake_resolve)
    monkeypatch.setattr(module, "_run_data_module", _fake_run_data_module)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "webnovel",
            "--project-root",
            str(tmp_path),
            "index",
            "aggregate-review-results",
            "--chapter",
            "12",
            "--data",
            '{"continuity-checker":{"overall_score":80}}',
        ],
    )

    with pytest.raises(SystemExit) as exc:
        module.main()

    assert int(exc.value.code or 0) == 0
    assert called["module_name"] == "index_manager"
    assert called["argv"] == [
        "--project-root",
        str(book_root),
        "aggregate-review-results",
        "--chapter",
        "12",
        "--data",
        '{"continuity-checker":{"overall_score":80}}',
    ]





def test_review_pipeline_builds_artifacts(tmp_path):
    _ensure_scripts_on_path()
    import review_pipeline as review_pipeline_module

    project_root = (tmp_path / "book").resolve()
    (project_root / ".webnovel").mkdir(parents=True, exist_ok=True)
    (project_root / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")

    review_results_path = tmp_path / "review_results.json"
    review_results_path.write_text(
        json.dumps(
            {
                "issues": [
                    {
                        "severity": "critical",
                        "category": "timeline",
                        "location": "第2段",
                        "description": "时间线回跳",
                        "evidence": "上章深夜，本章突然中午",
                        "fix_hint": "补时间过渡",
                        "blocking": True,
                    },
                    {
                        "severity": "medium",
                        "category": "ai_flavor",
                        "location": "第5段",
                        "description": "'稳住心神'出现2次",
                        "fix_hint": "替换为具体动作",
                    },
                ],
                "summary": "1个阻断，1个中等",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = review_pipeline_module.build_review_artifacts(
        project_root=project_root,
        chapter=20,
        review_results_path=review_results_path,
        report_file="审查报告/第20章.md",
    )

    assert payload["review_result"]["blocking_count"] == 1
    assert payload["review_result"]["has_blocking"] is True
    assert payload["review_result"]["issues_count"] == 2
    assert payload["metrics"]["issues_count"] == 2
    assert payload["metrics"]["blocking_count"] == 1
    assert payload["metrics"]["report_file"] == "审查报告/第20章.md"


def test_review_pipeline_forwards_with_resolved_project_root(monkeypatch, tmp_path):
    module = _load_webnovel_module()

    book_root = (tmp_path / "book").resolve()
    review_results = (tmp_path / "review_results.json").resolve()
    called = {}

    def _fake_resolve(explicit_project_root=None):
        return book_root

    def _fake_run_script(script_name, argv):
        called["script_name"] = script_name
        called["argv"] = list(argv)
        return 0

    monkeypatch.setattr(module, "_resolve_root", _fake_resolve)
    monkeypatch.setattr(module, "_run_script", _fake_run_script)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "webnovel",
            "--project-root",
            str(tmp_path),
            "review-pipeline",
            "--chapter",
            "18",
            "--review-results",
            str(review_results),
            "--metrics-out",
            str(tmp_path / "metrics.json"),
            "--report-file",
            "审查报告/第18章.md",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        module.main()

    assert int(exc.value.code or 0) == 0
    assert called["script_name"] == "review_pipeline.py"
    assert called["argv"] == [
        "--project-root",
        str(book_root),
        "--chapter",
        "18",
        "--review-results",
        str(review_results),
        "--metrics-out",
        str(tmp_path / "metrics.json"),
        "--report-file",
        "审查报告/第18章.md",
    ]


def test_review_pipeline_main_creates_output_directories(tmp_path):
    _ensure_scripts_on_path()
    import review_pipeline as review_pipeline_module

    project_root = (tmp_path / "book").resolve()
    (project_root / ".webnovel").mkdir(parents=True, exist_ok=True)
    (project_root / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")

    review_results_path = tmp_path / "review_results.json"
    review_results_path.write_text(
        json.dumps(
            {
                "issues": [
                    {
                        "severity": "low",
                        "category": "other",
                        "location": "p1",
                        "description": "小问题",
                    }
                ],
                "summary": "轻微",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    metrics_out = project_root / ".webnovel" / "tmp" / "review" / "metrics.json"

    old_argv = sys.argv
    sys.argv = [
        "review_pipeline",
        "--project-root",
        str(project_root),
        "--chapter",
        "9",
        "--review-results",
        str(review_results_path),
        "--metrics-out",
        str(metrics_out),
    ]
    try:
        review_pipeline_module.main()
    finally:
        sys.argv = old_argv

    assert metrics_out.is_file()