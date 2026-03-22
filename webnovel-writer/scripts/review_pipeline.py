#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
review_pipeline.py - Step 3 审查结果文件流辅助脚本

职责：
- 读取 checker 原始结果文件
- 调用 index_manager 聚合审查结果
- 物化为 review_metrics 结构
- 可选写入 review_metrics 到 index.db
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from runtime_compat import enable_windows_utf8_stdio


def _ensure_scripts_path() -> None:
    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

def build_review_artifacts(project_root: Path, chapter: int, review_results_path: Path, report_file: str = "") -> Dict[str, Any]:
    _ensure_scripts_path()
    from data_modules.config import DataModulesConfig
    from data_modules.index_manager import _aggregate_checker_results, ReviewAggregateResult

    _ = DataModulesConfig.from_project_root(project_root)
    raw_data = _load_json(review_results_path)
    aggregated = ReviewAggregateResult(**_aggregate_checker_results(chapter, raw_data))
    review_metrics = aggregated.to_review_metrics(report_file=report_file)
    return {
        "chapter": chapter,
        "review_results": raw_data,
        "aggregated": aggregated.__dict__,
        "review_metrics": review_metrics.__dict__,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="构建 Step 3 审查中间产物")
    parser.add_argument("--project-root", required=True, help="项目根目录")
    parser.add_argument("--chapter", type=int, required=True, help="章节号")
    parser.add_argument("--review-results", required=True, help="checker 原始结果 JSON 文件")
    parser.add_argument("--aggregated-out", help="聚合结果输出文件")
    parser.add_argument("--review-metrics-out", help="review_metrics 输出文件")
    parser.add_argument("--report-file", default="", help="审查报告路径")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    review_results_path = Path(args.review_results).resolve()
    payload = build_review_artifacts(
        project_root=project_root,
        chapter=args.chapter,
        review_results_path=review_results_path,
        report_file=args.report_file,
    )

    if args.aggregated_out:
        _write_json(Path(args.aggregated_out), payload["aggregated"])

    if args.review_metrics_out:
        _write_json(Path(args.review_metrics_out), payload["review_metrics"])

    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if sys.platform == "win32":
        enable_windows_utf8_stdio()
    main()
