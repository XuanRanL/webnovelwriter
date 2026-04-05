#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Tavily direct API client — bypasses MCP proxy to avoid shared rate limits.

Usage:
  python tavily_search.py search "query text" [--max 5] [--depth advanced] [--answer advanced]
  python tavily_search.py research "research question" [--model pro|mini|auto] [--max-wait 600]

Key discovery order:
  1. env var TAVILY_API_KEYS (comma-separated) or TAVILY_API_KEY
  2. .env files:  <project>/.env  ->  <script>/.env  ->  CWD/.env
  3. ~/.claude.json  (extracted from MCP tavily url: tavilyApiKey=tvly-...)

Output: markdown to stdout (UTF-8 forced on Windows). Use --json for raw JSON.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# Force UTF-8 stdout/stderr on Windows (avoid GBK encode errors)
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass

API_BASE = "https://api.tavily.com"


# ---------- Key discovery ----------
def _load_keys():
    keys = []
    seen = set()

    def _add(k):
        k = k.strip().strip('"').strip("'")
        if k and k not in seen:
            seen.add(k)
            keys.append(k)

    # (a) env var
    env_val = os.environ.get("TAVILY_API_KEYS") or os.environ.get("TAVILY_API_KEY")
    if env_val:
        for k in env_val.split(","):
            _add(k)

    # (b) .env files
    script_dir = Path(__file__).resolve().parent
    candidates = [
        script_dir.parent.parent / ".env",  # workspace root .env
        script_dir.parent / ".env",         # plugin root .env
        script_dir / ".env",                # scripts/.env
        Path.cwd() / ".env",                # cwd .env
    ]
    for p in candidates:
        if not p.exists():
            continue
        try:
            for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("TAVILY_API_KEYS="):
                    val = line.split("=", 1)[1]
                    for k in val.split(","):
                        _add(k)
                elif line.startswith("TAVILY_API_KEY="):
                    _add(line.split("=", 1)[1])
        except Exception:
            continue

    # (c) ~/.claude.json fallback — extract from MCP URL query param
    if not keys:
        claude_json = Path.home() / ".claude.json"
        if claude_json.exists():
            try:
                text = claude_json.read_text(encoding="utf-8", errors="ignore")
                for m in re.finditer(r"tavilyApiKey=(tvly-[A-Za-z0-9_\-]+)", text):
                    _add(m.group(1))
            except Exception:
                pass

    return keys


# ---------- HTTP client with key rotation ----------
class TavilyClient:
    def __init__(self, keys):
        if not keys:
            raise RuntimeError(
                "No Tavily API keys found. Set TAVILY_API_KEYS env var, "
                "or add TAVILY_API_KEYS=k1,k2,k3 to .env, "
                "or ensure ~/.claude.json has tavily MCP entries."
            )
        self.keys = keys
        self.idx = 0

    def _rotate(self):
        k = self.keys[self.idx]
        self.idx = (self.idx + 1) % len(self.keys)
        return k

    def _request(self, method, path, body=None, key=None, timeout=90):
        url = f"{API_BASE}{path}"
        data = None
        headers = {}
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        headers["Authorization"] = f"Bearer {key}"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        r = urllib.request.urlopen(req, timeout=timeout)
        raw = r.read().decode("utf-8", errors="replace")
        return json.loads(raw) if raw else {}

    # HTTP status codes that indicate a key-specific problem (quota/auth/rate-limit)
    # and warrant rotating to the next key rather than failing immediately.
    # 432 = Tavily-specific: "This request exceeds this API key's set usage limit."
    _ROTATE_CODES = (401, 403, 429, 432)

    def _post_with_rotation(self, path, body, timeout=90):
        last = None
        tried = 0
        while tried < len(self.keys):
            key = self._rotate()
            tried += 1
            try:
                return self._request("POST", path, body=body, key=key, timeout=timeout), key
            except urllib.error.HTTPError as e:
                if e.code in self._ROTATE_CODES:
                    err_body = ""
                    try:
                        err_body = e.read().decode("utf-8", errors="replace")[:200]
                    except Exception:
                        pass
                    print(f"[warn] key #{tried} returned {e.code}: {err_body}", file=sys.stderr)
                    last = e
                    continue
                raise
            except Exception as e:
                last = e
                continue
        raise RuntimeError(f"All {len(self.keys)} keys failed on POST {path}. Last error: {last}")

    def search(self, query, max_results=5, search_depth="advanced",
               include_answer="advanced", topic="general", extras=None):
        body = {
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "include_answer": include_answer,
            "topic": topic,
        }
        if extras:
            body.update({k: v for k, v in extras.items() if v is not None})
        d, _ = self._post_with_rotation("/search", body, timeout=90)
        return d

    def research(self, input_text, model="pro", poll_interval=6, max_wait=600):
        # Submit (try each key until one accepts)
        body = {"input": input_text, "model": model}
        d, submit_key = self._post_with_rotation("/research", body, timeout=60)
        rid = d.get("request_id")
        if not rid:
            return d

        print(f"[info] research submitted, rid={rid}, polling every {poll_interval}s (max {max_wait}s)...",
              file=sys.stderr)

        start = time.time()
        while True:
            elapsed = time.time() - start
            if elapsed > max_wait:
                raise TimeoutError(f"Research timed out after {max_wait}s, rid={rid}")

            try:
                d = self._request("GET", f"/research/{rid}", key=submit_key, timeout=30)
            except urllib.error.HTTPError as e:
                # Submit key might have hit limit/quota for polling — rotate
                if e.code in self._ROTATE_CODES:
                    for k in self.keys:
                        if k == submit_key:
                            continue
                        try:
                            d = self._request("GET", f"/research/{rid}", key=k, timeout=30)
                            submit_key = k  # switch permanently for this job
                            break
                        except Exception:
                            continue
                    else:
                        raise
                else:
                    raise

            status = d.get("status")
            if status not in ("pending", "in_progress", "queued"):
                print(f"[info] research finished after {elapsed:.1f}s status={status}", file=sys.stderr)
                return d
            time.sleep(poll_interval)


# ---------- Output formatting ----------
def fmt_search(d, query):
    out = [f"# Search: {query}", ""]
    ans = d.get("answer")
    if ans:
        out.append("## Answer")
        out.append(str(ans).strip())
        out.append("")
    results = d.get("results") or []
    out.append(f"## Results ({len(results)})")
    for i, r in enumerate(results, 1):
        title = r.get("title", "") or ""
        url = r.get("url", "") or ""
        score = r.get("score", 0) or 0
        content = (r.get("content") or "").strip()
        out.append("")
        out.append(f"### [{i}] {title}")
        out.append(f"- URL: {url}")
        try:
            out.append(f"- Score: {float(score):.3f}")
        except Exception:
            out.append(f"- Score: {score}")
        if content:
            snippet = content[:600].replace("\n", " ")
            out.append(f"- Content: {snippet}")
    rt = d.get("response_time")
    if rt is not None:
        out.append("")
        out.append(f"_response_time={rt}s_")
    return "\n".join(out)


def fmt_research(d, query):
    out = [f"# Research: {query}", ""]
    content = d.get("content")
    if content:
        out.append("## Content")
        out.append(str(content).strip())
        out.append("")
    sources = d.get("sources") or []
    if sources:
        out.append(f"## Sources ({len(sources)})")
        for i, s in enumerate(sources, 1):
            if isinstance(s, dict):
                title = s.get("title", "") or ""
                url = s.get("url", "") or ""
                out.append(f"- [{i}] {title} — {url}")
            else:
                out.append(f"- [{i}] {s}")
    out.append("")
    meta = []
    if d.get("status"):
        meta.append(f"status={d['status']}")
    if d.get("response_time") is not None:
        meta.append(f"time={d['response_time']}s")
    if d.get("request_id"):
        meta.append(f"rid={d['request_id']}")
    if meta:
        out.append("_" + "  ".join(meta) + "_")
    return "\n".join(out)


# ---------- CLI ----------
def main():
    parser = argparse.ArgumentParser(
        description="Tavily direct API client (bypasses MCP proxy for rate-limit reliability)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_search = sub.add_parser("search", help="Quick search with synthesized answer")
    p_search.add_argument("query", type=str)
    p_search.add_argument("--max", type=int, default=5, dest="max_results")
    p_search.add_argument("--depth", default="advanced",
                          choices=["basic", "advanced", "fast", "ultra-fast"])
    p_search.add_argument("--answer", default="advanced",
                          help="include_answer: basic | advanced | none")
    p_search.add_argument("--topic", default="general",
                          choices=["general", "news", "finance"])
    p_search.add_argument("--days", type=int, default=None)
    p_search.add_argument("--time-range", default=None,
                          choices=["day", "week", "month", "year"])
    p_search.add_argument("--include-domains", default=None,
                          help="comma-separated domains")
    p_search.add_argument("--exclude-domains", default=None,
                          help="comma-separated domains")
    p_search.add_argument("--json", action="store_true", help="raw JSON output")

    p_res = sub.add_parser("research", help="Deep async research (multiple sub-queries)")
    p_res.add_argument("query", type=str)
    p_res.add_argument("--model", default="pro", choices=["pro", "mini", "auto"])
    p_res.add_argument("--max-wait", type=int, default=600,
                       help="max seconds to wait for async completion")
    p_res.add_argument("--poll-interval", type=int, default=6)
    p_res.add_argument("--json", action="store_true")

    args = parser.parse_args()

    keys = _load_keys()
    if not keys:
        print("[ERR] No Tavily keys found.", file=sys.stderr)
        print("      Set TAVILY_API_KEYS env var, or add to .env, "
              "or ensure ~/.claude.json has tavily MCP entries.", file=sys.stderr)
        sys.exit(2)

    print(f"[info] {len(keys)} tavily key(s) loaded", file=sys.stderr)
    client = TavilyClient(keys)

    if args.cmd == "search":
        include_answer = args.answer
        if include_answer.lower() in ("none", "no", "false", "off", ""):
            include_answer = False
        extras = {}
        if args.days is not None:
            extras["days"] = args.days
        if args.time_range:
            extras["time_range"] = args.time_range
        if args.include_domains:
            extras["include_domains"] = [d.strip() for d in args.include_domains.split(",") if d.strip()]
        if args.exclude_domains:
            extras["exclude_domains"] = [d.strip() for d in args.exclude_domains.split(",") if d.strip()]

        d = client.search(
            args.query,
            max_results=args.max_results,
            search_depth=args.depth,
            include_answer=include_answer,
            topic=args.topic,
            extras=extras,
        )
        if args.json:
            print(json.dumps(d, ensure_ascii=False, indent=2))
        else:
            print(fmt_search(d, args.query))

    elif args.cmd == "research":
        d = client.research(
            args.query,
            model=args.model,
            poll_interval=args.poll_interval,
            max_wait=args.max_wait,
        )
        if args.json:
            print(json.dumps(d, ensure_ascii=False, indent=2))
        else:
            print(fmt_research(d, args.query))


if __name__ == "__main__":
    main()
