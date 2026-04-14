#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from reference_search import search as search_reference

from .story_contracts import merge_anti_patterns


ANTI_PATTERN_SOURCE_FIELDS = {
    "场景写法": ["毒点"],
    "写作技法": ["毒点"],
    "爽点与节奏": ["毒点"],
    "人设与关系": ["毒点"],
    "桥段套路": ["毒点"],
    "题材与调性推理": ["毒点"],
    "命名规则": ["毒点"],
    "金手指与设定": ["毒点"],
}


class StorySystemEngine:
    def __init__(self, csv_dir: str | Path):
        self.csv_dir = Path(csv_dir)

    def build(self, query: str, genre: Optional[str], chapter: Optional[int]) -> Dict[str, Any]:
        route = self._route(query=query, genre=genre)
        search_query = self._expand_query(query, route.get("default_query", ""))
        base_context = self._collect_tables(
            search_query,
            route["recommended_base_tables"],
            genre=route["genre_filter"],
            top_k=1,
        )
        dynamic_context = self._collect_tables(
            search_query,
            route["recommended_dynamic_tables"],
            genre=route["genre_filter"],
            top_k=2,
        )
        source_trace = route["source_trace"] + self._build_source_trace(base_context, dynamic_context)
        anti_patterns = merge_anti_patterns(
            route["route_anti_patterns"],
            self._extract_anti_patterns(base_context),
            self._extract_anti_patterns(dynamic_context),
        )
        return {
            "meta": {"query": query, "chapter": chapter, "explicit_genre": genre or ""},
            "master_setting": {
                "meta": {
                    "schema_version": "story-system/v1",
                    "contract_type": "MASTER_SETTING",
                    "generator_version": "phase1",
                    "query": query,
                },
                "route": route["meta"],
                "master_constraints": {
                    "core_tone": route["core_tone"],
                    "pacing_strategy": route["pacing_strategy"],
                },
                "base_context": base_context,
                "source_trace": source_trace,
                "override_policy": {
                    "locked": ["route.primary_genre", "master_constraints.core_tone"],
                    "append_only": ["anti_patterns"],
                    "override_allowed": [],
                },
            },
            "chapter_brief": (
                {
                    "meta": {
                        "schema_version": "story-system/v1",
                        "contract_type": "CHAPTER_BRIEF",
                        "generator_version": "phase1",
                        "chapter": chapter,
                    },
                    "override_allowed": {
                        "chapter_focus": self._suggest_chapter_focus(query, dynamic_context),
                    },
                    "dynamic_context": dynamic_context,
                    "source_trace": source_trace,
                }
                if chapter is not None
                else None
            ),
            "anti_patterns": anti_patterns,
        }

    def _route(self, query: str, genre: Optional[str]) -> Dict[str, Any]:
        route_rows = self._load_csv_rows("题材与调性推理")
        query_text = self._normalize_text(" ".join([query or "", genre or ""]))

        matched = None
        route_source = "empty_csv_fallback"
        for row in route_rows:
            aliases = (
                self._split_multi_value(row.get("关键词"))
                + self._split_multi_value(row.get("意图与同义词"))
                + self._split_multi_value(row.get("题材别名"))
            )
            if any(alias and self._normalize_text(alias) in query_text for alias in aliases):
                matched = row
                route_source = "keyword_or_alias_match"
                break
        if matched is None and genre:
            matched = self._fallback_row_for_genre(route_rows, genre)
            if matched is not None:
                route_source = "explicit_genre_fallback"
        if matched is None and route_rows:
            matched = route_rows[0]
            route_source = "default_seed_fallback"
        if matched is None:
            return self._empty_route(query=query, genre=genre)

        primary_genre = str(matched.get("题材/流派") or genre or "").strip()
        genre_filter = str(matched.get("适用题材") or genre or primary_genre).strip()
        return {
            "meta": {
                "primary_genre": primary_genre,
                "route_source": route_source,
                "genre_filter": genre_filter,
                "recommended_base_tables": self._split_multi_value(matched.get("推荐基础检索表")),
                "recommended_dynamic_tables": self._split_multi_value(matched.get("推荐动态检索表")),
            },
            "core_tone": str(matched.get("核心调性") or "").strip(),
            "pacing_strategy": str(matched.get("节奏策略") or "").strip(),
            "route_anti_patterns": self._extract_route_anti_patterns(matched),
            "recommended_base_tables": self._split_multi_value(matched.get("推荐基础检索表")),
            "recommended_dynamic_tables": self._split_multi_value(matched.get("推荐动态检索表")),
            "genre_filter": genre_filter,
            "default_query": str(matched.get("默认查询词") or "").strip(),
            "source_trace": [{"table": "题材与调性推理", "id": matched.get("编号", ""), "reason": route_source}],
        }

    def _collect_tables(self, query: str, tables: List[str], genre: str, top_k: int) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for table_name in tables:
            result = search_reference(
                csv_dir=self.csv_dir,
                skill="write",
                query=query,
                table=table_name,
                genre=genre or None,
                max_results=top_k,
            )
            raw_rows = {str(row.get("编号") or ""): row for row in self._load_csv_rows(table_name)}
            for item in result.get("data", {}).get("results", []):
                row_id = str(item.get("编号") or "")
                full_row = dict(raw_rows.get(row_id) or {})
                full_row["_table"] = str(item.get("表") or table_name)
                full_row["编号"] = row_id
                full_row["核心摘要"] = str(
                    full_row.get("核心摘要")
                    or item.get("内容摘要")
                    or item.get("核心摘要")
                    or ""
                ).strip()
                rows.append(full_row)
        return rows

    def _extract_anti_patterns(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        extracted: List[Dict[str, Any]] = []
        for row in rows:
            table_name = str(row.get("_table") or "")
            for field_name in ANTI_PATTERN_SOURCE_FIELDS.get(table_name, []):
                for text in self._split_multi_value(row.get(field_name)):
                    extracted.append(
                        {
                            "text": text,
                            "source_table": table_name,
                            "source_id": row.get("编号", ""),
                        }
                    )
        return extracted

    def _suggest_chapter_focus(self, query: str, dynamic_rows: List[Dict[str, Any]]) -> str:
        for row in dynamic_rows:
            summary = str(row.get("核心摘要") or "").strip()
            if summary:
                return summary
        return query

    def _build_source_trace(self, *groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        trace: List[Dict[str, Any]] = []
        for group in groups:
            for row in group:
                trace.append(
                    {
                        "table": row.get("_table", ""),
                        "id": row.get("编号", ""),
                        "summary": row.get("核心摘要", ""),
                    }
                )
        return trace

    def _load_csv_rows(self, table_name: str) -> List[Dict[str, Any]]:
        csv_path = self.csv_dir / f"{table_name}.csv"
        if not csv_path.is_file():
            return []
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))

    def _normalize_text(self, text: str) -> str:
        return str(text or "").strip().lower()

    def _split_multi_value(self, raw: Any) -> List[str]:
        return [item.strip() for item in re.split(r"[|；;]+", str(raw or "")) if item.strip()]

    def _expand_query(self, query: str, default_query: str) -> str:
        items: List[str] = []
        for candidate in [query, *self._split_multi_value(default_query)]:
            text = str(candidate or "").strip()
            if text and text not in items:
                items.append(text)
        return " ".join(items)

    def _fallback_row_for_genre(self, rows: List[Dict[str, Any]], genre: str) -> Dict[str, Any] | None:
        genre_text = self._normalize_text(genre)
        for row in rows:
            candidates = self._split_multi_value(row.get("适用题材")) + self._split_multi_value(row.get("题材/流派"))
            if any(self._normalize_text(candidate) == genre_text for candidate in candidates):
                return row
        return None

    def _extract_route_anti_patterns(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            {"text": text, "source_table": "题材与调性推理", "source_id": row.get("编号", "")}
            for text in self._split_multi_value(row.get("毒点"))
        ]

    def _empty_route(self, query: str, genre: Optional[str]) -> Dict[str, Any]:
        fallback_genre = str(genre or "未命中题材").strip()
        route_source = "explicit_genre_fallback" if genre else "empty_csv_fallback"
        return {
            "meta": {
                "primary_genre": fallback_genre,
                "route_source": route_source,
                "genre_filter": fallback_genre,
                "recommended_base_tables": ["命名规则", "人设与关系"],
                "recommended_dynamic_tables": ["桥段套路", "爽点与节奏", "场景写法"],
            },
            "core_tone": "",
            "pacing_strategy": "",
            "route_anti_patterns": [],
            "recommended_base_tables": ["命名规则", "人设与关系"],
            "recommended_dynamic_tables": ["桥段套路", "爽点与节奏", "场景写法"],
            "genre_filter": fallback_genre,
            "default_query": "",
            "source_trace": [{"table": "题材与调性推理", "id": "", "reason": f"{route_source}:{query}"}],
        }
