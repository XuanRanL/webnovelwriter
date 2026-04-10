#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reference CSV 检索工具。

在 references/csv/ 目录下的 CSV 文件中执行 BM25 关键词搜索，
支持按技能、题材过滤，返回 JSON 格式结果。

用法:
    python reference_search.py --skill write --query "角色命名" --genre 玄幻
    python reference_search.py --skill write --table 命名规则 --query "战斗描写" --max-results 3
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# CSV loading
# ---------------------------------------------------------------------------

def _load_csv(path: Path) -> List[Dict[str, str]]:
    """Load a single CSV file (UTF-8 with BOM)."""
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_tables(csv_dir: Path, table: Optional[str] = None) -> Dict[str, List[Dict[str, str]]]:
    """
    Load CSV tables from *csv_dir*.

    If *table* is given, load only that file (``<table>.csv``).
    Otherwise load every ``.csv`` file in the directory.

    Returns ``{table_name: [row_dict, ...]}``.
    """
    tables: Dict[str, List[Dict[str, str]]] = {}
    if table:
        target = csv_dir / f"{table}.csv"
        if target.is_file():
            tables[table] = _load_csv(target)
    else:
        for p in sorted(csv_dir.glob("*.csv")):
            tables[p.stem] = _load_csv(p)
    return tables


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def _skill_matches(row: Dict[str, str], skill: str) -> bool:
    """Return True if *skill* appears in the pipe-separated ``适用技能`` column."""
    cell = row.get("适用技能", "")
    return skill in cell.split("|")


def _genre_matches(row: Dict[str, str], genre: Optional[str]) -> bool:
    """Return True if *genre* is None, or matches ``适用题材`` (``全部`` always matches)."""
    if genre is None:
        return True
    cell = row.get("适用题材", "")
    if cell.strip() == "全部":
        return True
    return genre in [g.strip() for g in cell.split(",")]


# ---------------------------------------------------------------------------
# BM25-lite scoring
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> List[str]:
    """Split Chinese text into individual characters and comma-separated terms."""
    # For the 关键词 field: terms are comma-separated
    # For the query: we just split on common separators
    tokens: List[str] = []
    for part in text.replace(",", " ").replace("，", " ").replace("|", " ").split():
        tokens.append(part)
    return tokens


def _bm25_score(query_terms: List[str], doc_terms: List[str],
                avg_dl: float, k1: float = 1.5, b: float = 0.75,
                idf_map: Optional[Dict[str, float]] = None) -> float:
    """
    Simplified BM25 score for a single document.

    *idf_map* maps each query term to its IDF value.
    """
    if not doc_terms:
        return 0.0
    dl = len(doc_terms)
    score = 0.0
    tf_map: Dict[str, int] = {}
    for t in doc_terms:
        tf_map[t] = tf_map.get(t, 0) + 1
    for qt in query_terms:
        tf = tf_map.get(qt, 0)
        if tf == 0:
            # Also check substring match (important for Chinese compound words)
            for dt in tf_map:
                if qt in dt or dt in qt:
                    tf = max(tf, 1)
                    break
        if tf == 0:
            continue
        idf = idf_map.get(qt, 1.0) if idf_map else 1.0
        numerator = tf * (k1 + 1)
        denominator = tf + k1 * (1 - b + b * dl / max(avg_dl, 1))
        score += idf * numerator / denominator
    return score


def _compute_idf(query_terms: List[str], all_docs: List[List[str]]) -> Dict[str, float]:
    """Compute IDF for each query term across all documents."""
    n = len(all_docs)
    if n == 0:
        return {}
    idf: Dict[str, float] = {}
    for qt in query_terms:
        df = 0
        for doc in all_docs:
            for dt in doc:
                if qt in dt or dt in qt:
                    df += 1
                    break
        # BM25 IDF: log((N - df + 0.5) / (df + 0.5) + 1)
        idf[qt] = math.log((n - df + 0.5) / (df + 0.5) + 1)
    return idf


# ---------------------------------------------------------------------------
# Content summary builder
# ---------------------------------------------------------------------------

# Columns used for building 内容摘要, in priority order.
_CONTENT_COLUMNS = [
    "规则", "说明", "模式名称",
    "正例", "示例片段",
    "反例", "反面写法",
    "命名对象", "场景类型",
]


def _build_summary(row: Dict[str, str]) -> str:
    """Merge key content columns into a single summary string."""
    parts: List[str] = []
    for col in _CONTENT_COLUMNS:
        val = row.get(col, "").strip()
        if val:
            parts.append(val)
    return "；".join(parts) if parts else ""


# ---------------------------------------------------------------------------
# Search entry point
# ---------------------------------------------------------------------------

def search(
    csv_dir: Path,
    skill: str,
    query: str,
    table: Optional[str] = None,
    genre: Optional[str] = None,
    max_results: int = 5,
) -> Dict[str, Any]:
    """
    Run a BM25 keyword search across CSV reference tables.

    Returns a result dict suitable for JSON serialisation.
    """
    if not csv_dir.is_dir():
        return {
            "status": "error",
            "error": {
                "code": "CSV_DIR_NOT_FOUND",
                "message": f"CSV directory not found: {csv_dir}",
            },
        }

    tables = load_tables(csv_dir, table=table)
    if not tables:
        return {
            "status": "success",
            "message": "search_results",
            "data": {
                "query": query,
                "skill": skill,
                "genre": genre,
                "total": 0,
                "results": [],
            },
        }

    # 1) Collect filtered rows with table name annotation
    candidates: List[tuple] = []  # (table_name, row)
    for tbl_name, rows in tables.items():
        for row in rows:
            if _skill_matches(row, skill) and _genre_matches(row, genre):
                candidates.append((tbl_name, row))

    if not candidates:
        return {
            "status": "success",
            "message": "search_results",
            "data": {
                "query": query,
                "skill": skill,
                "genre": genre,
                "total": 0,
                "results": [],
            },
        }

    # 2) Tokenize
    query_terms = _tokenize(query)
    doc_terms_list = [_tokenize(row.get("关键词", "")) for _, row in candidates]
    avg_dl = sum(len(d) for d in doc_terms_list) / len(doc_terms_list) if doc_terms_list else 1.0
    idf_map = _compute_idf(query_terms, doc_terms_list)

    # 3) Score
    scored: List[tuple] = []
    for idx, (tbl_name, row) in enumerate(candidates):
        score = _bm25_score(query_terms, doc_terms_list[idx], avg_dl, idf_map=idf_map)
        if score > 0:
            scored.append((score, tbl_name, row))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:max_results]

    # 4) Format results
    results: List[Dict[str, Any]] = []
    for _score, tbl_name, row in top:
        results.append({
            "编号": row.get("编号", ""),
            "表": tbl_name,
            "分类": row.get("分类", ""),
            "层级": row.get("层级", ""),
            "适用题材": row.get("适用题材", ""),
            "内容摘要": _build_summary(row),
        })

    return {
        "status": "success",
        "message": "search_results",
        "data": {
            "query": query,
            "skill": skill,
            "genre": genre,
            "total": len(results),
            "results": results,
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _default_csv_dir() -> Path:
    """Auto-detect the csv directory relative to this script's location."""
    return Path(__file__).resolve().parent.parent / "references" / "csv"


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="BM25 keyword search over reference CSV files",
    )
    parser.add_argument("--skill", required=True, help="Filter by 适用技能 column")
    parser.add_argument("--table", default=None, help="Target specific CSV file name (without .csv)")
    parser.add_argument("--query", required=True, help="BM25 search keywords")
    parser.add_argument("--genre", default=None, help="Filter by 适用题材 column")
    parser.add_argument("--max-results", type=int, default=5, help="Max results (default 5)")
    parser.add_argument("--csv-dir", default=None, help="Override CSV directory path")

    args = parser.parse_args(argv)
    csv_dir = Path(args.csv_dir) if args.csv_dir else _default_csv_dir()

    result = search(
        csv_dir=csv_dir,
        skill=args.skill,
        query=args.query,
        table=args.table,
        genre=args.genre,
        max_results=args.max_results,
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
