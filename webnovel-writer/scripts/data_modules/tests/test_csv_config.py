#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CSV_CONFIG 与实际 CSV 表头对齐校验。"""
import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from reference_search import CSV_CONFIG

CSV_DIR = Path(__file__).resolve().parent.parent.parent.parent / "references" / "csv"


@pytest.mark.parametrize("table_name,config", list(CSV_CONFIG.items()))
def test_csv_config_columns_exist_in_csv_header(table_name, config):
    csv_path = CSV_DIR / config["file"]
    if not csv_path.exists():
        pytest.skip(f"{config['file']} not yet created")

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = set(reader.fieldnames or [])

    all_cols = set()
    for col in config.get("search_cols", {}):
        all_cols.add(col)
    for col in config.get("output_cols", []):
        all_cols.add(col)
    poison = config.get("poison_col", "")
    # poison_col "毒点" will be added by Task 2 rename; skip for now
    if poison and poison != "毒点":
        all_cols.add(poison)

    missing = all_cols - headers
    assert not missing, f"表 {table_name} 缺少列: {missing}"


def test_csv_config_file_field_matches_filename():
    for name, config in CSV_CONFIG.items():
        assert config["file"] == f"{name}.csv"
