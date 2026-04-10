#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for reference_search.py — BM25 keyword search over CSV reference files.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = str(Path(__file__).resolve().parents[1] / "reference_search.py")
CSV_DIR = str(Path(__file__).resolve().parents[2] / "references" / "csv")


def run_search(*args: str) -> dict:
    """Run reference_search.py as a subprocess and return parsed JSON."""
    result = subprocess.run(
        [sys.executable, SCRIPT, "--csv-dir", CSV_DIR, *args],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Script failed: {result.stderr}"
    return json.loads(result.stdout)


class TestSkillAndGenreFiltering:
    """Test filtering by skill and genre."""

    def test_skill_write_genre_xuanhuan_returns_nr001_not_nr002(self):
        """--skill write --table 命名规则 --query 角色命名 --genre 玄幻 → NR-001, not NR-002."""
        out = run_search(
            "--skill", "write",
            "--table", "命名规则",
            "--query", "角色命名",
            "--genre", "玄幻",
        )
        assert out["status"] == "success"
        ids = [r["编号"] for r in out["data"]["results"]]
        assert "NR-001" in ids
        assert "NR-002" not in ids

    def test_skill_write_cross_table_search(self):
        """--skill write --query 战斗描写 → SP-001 from 场景写法."""
        out = run_search(
            "--skill", "write",
            "--query", "战斗描写",
        )
        assert out["status"] == "success"
        assert out["data"]["total"] >= 1
        ids = [r["编号"] for r in out["data"]["results"]]
        assert "SP-001" in ids
        # Verify it comes from the right table
        tables = [r["表"] for r in out["data"]["results"] if r["编号"] == "SP-001"]
        assert tables[0] == "场景写法"

    def test_nonexistent_query_returns_empty(self):
        """--skill plan --query nonexistent → empty results, no error."""
        out = run_search(
            "--skill", "plan",
            "--query", "nonexistent",
        )
        assert out["status"] == "success"
        assert out["data"]["total"] == 0
        assert out["data"]["results"] == []


class TestErrorHandling:
    """Test error cases."""

    def test_missing_csv_dir_returns_error(self):
        """Missing CSV dir → error JSON."""
        result = subprocess.run(
            [sys.executable, SCRIPT,
             "--csv-dir", "/nonexistent/path/that/does/not/exist",
             "--skill", "write",
             "--query", "test"],
            capture_output=True,
            text=True,
        )
        out = json.loads(result.stdout)
        assert out["status"] == "error"
        assert "CSV_DIR_NOT_FOUND" in out["error"]["code"]


class TestOutputFormat:
    """Test output JSON structure."""

    def test_result_has_required_fields(self):
        """Each result has 编号, 表, 分类, 层级, 适用题材, 内容摘要."""
        out = run_search(
            "--skill", "write",
            "--table", "命名规则",
            "--query", "角色命名",
        )
        assert out["status"] == "success"
        for r in out["data"]["results"]:
            assert "编号" in r
            assert "表" in r
            assert "分类" in r
            assert "层级" in r
            assert "适用题材" in r
            assert "内容摘要" in r

    def test_data_envelope_fields(self):
        """Data envelope has query, skill, genre, total, results."""
        out = run_search(
            "--skill", "write",
            "--query", "命名",
            "--genre", "玄幻",
        )
        data = out["data"]
        assert data["query"] == "命名"
        assert data["skill"] == "write"
        assert data["genre"] == "玄幻"
        assert isinstance(data["total"], int)
        assert isinstance(data["results"], list)

    def test_max_results_limits_output(self):
        """--max-results 1 limits to 1 result."""
        out = run_search(
            "--skill", "write",
            "--query", "命名",
            "--max-results", "1",
        )
        assert out["data"]["total"] <= 1
