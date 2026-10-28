#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Tavily direct API client — bypasses MCP proxy to avoid shared rate limits.

Usage:
  python tavily_search.py search "query text" [--max 5] [--depth advanced] [--answer advanced]
  python tavily_search.py research "research question" [--model pro|mini|auto] [--max-wait 600]

Credential precedence:
  1. Tavily gateway (preferred) — ~/.xuanran-seo/credentials/tavily-gateway.json
     {"base_url": "https://...", "token": "..."}; env TAVILY_GATEWAY_URL / TAVILY_GATEWAY_TOKEN override it.
     Configured = gateway mode: every request carries the gateway token, the gateway picks the Tavily key
     (no client-side rotation, no /usage, no api_key in the body). A broken config is an error, never a
     silent switch to raw keys. Only TAVILY_GATEWAY_FALLBACK=pool (or =keys) lets an unreachable gateway
     fall back to the legacy keys below, with a loud warning.
  2. Legacy raw keys, only when no gateway is configured:
     a. env var TAVILY_API_KEYS (comma-separated) or TAVILY_API_KEY
     b. .env files:  <project>/.env  ->  <script>/.env  ->  CWD/.env
     c. ~/.claude.json  (extracted from MCP tavily url: tavilyApiKey=tvly-...)

Exit codes: 0 ok · 1 other error · 2 no usable credentials (no keys, broken gateway config, gateway
rejected the token) · 3 gateway has no available keys (503) · 4 gateway unreachable.

Output: markdown to stdout (UTF-8 forced on Windows). Use --json for raw JSON.
"""
import argparse
import datetime
import email.utils
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

# Force UTF-8 stdout/stderr on Windows (avoid GBK encode errors)
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass

API_BASE = "https://api.tavily.com"

# ---------- Tavily gateway (one owner of the shared key pool) ----------
# Several tools used to rotate the same Tavily key pool with their own balance tracking; balances drifted,
# bulk /usage checks got the server IP rate-limited and keys ran dry. The self-hosted gateway now owns the
# keys (selection, egress IPs, cooldowns, credits); this client sends only a scoped token.
GATEWAY_FILE = Path.home() / ".xuanran-seo" / "credentials" / "tavily-gateway.json"
GATEWAY_ENV_URL, GATEWAY_ENV_TOKEN, GATEWAY_ENV_FALLBACK = (
    "TAVILY_GATEWAY_URL", "TAVILY_GATEWAY_TOKEN", "TAVILY_GATEWAY_FALLBACK")
GATEWAY_HINT = "~/.xuanran-seo/credentials/tavily-gateway.json or TAVILY_GATEWAY_URL / TAVILY_GATEWAY_TOKEN"
MAX_429_RETRIES = 2
MAX_502_RETRIES = 1
DEFAULT_RETRY_AFTER = 1.0
MAX_RETRY_AFTER = 120.0          # a longer cooldown is reported, not slept through
UNREACHABLE_STATUSES = {520, 521, 522, 523, 524, 530}   # Cloudflare: origin unreachable
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
# Cloudflare in front of the gateway bans urllib's default "Python-urllib/3.x" signature (403, error 1010).
GATEWAY_USER_AGENT = "webnovel-writer-tavily/1.0 (+gateway client)"


class GatewayConfigError(ValueError):
    """The gateway config exists but is unusable. Never contains the token."""


class GatewayError(RuntimeError):
    def __init__(self, message, status=None, code=None):
        super().__init__(message)
        self.status = status
        self.code = code


class GatewayUnreachable(GatewayError):
    """No answer from the gateway (connection, TLS, timeout, Cloudflare origin errors)."""


def load_gateway(environ=None, path=None):
    """{"base_url", "token"} when the gateway is configured, None when not; GatewayConfigError if broken."""
    environ = os.environ if environ is None else environ
    path = GATEWAY_FILE if path is None else Path(path)
    data = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            raise GatewayConfigError(f"{path.name} is not readable JSON") from None
        if not isinstance(data, dict):
            raise GatewayConfigError(f'{path.name} must be {{"base_url": ..., "token": ...}}')
    env_url = str(environ.get(GATEWAY_ENV_URL) or "").strip()
    env_token = str(environ.get(GATEWAY_ENV_TOKEN) or "").strip()
    if not (data or env_url or env_token):
        return None
    url = env_url or str(data.get("base_url") or "").strip()
    token = env_token or str(data.get("token") or "").strip()
    missing = [name for name, value in (("base_url", url), ("token", token)) if not value]
    if missing:
        raise GatewayConfigError(f"Tavily gateway config is missing {' / '.join(missing)} ({GATEWAY_HINT})")
    if any(ch.isspace() for ch in token):
        raise GatewayConfigError("Tavily gateway token contains whitespace")
    parts = urlsplit(url)
    local = parts.scheme == "http" and (parts.hostname or "") in LOCAL_HOSTS
    if not parts.hostname or not (parts.scheme == "https" or local):
        # the bearer token must not travel in clear text
        raise GatewayConfigError(f"Tavily gateway base_url must be https:// (http only for localhost): {url[:80]}")
    return {"base_url": url.rstrip("/"), "token": token}


def fallback_allowed(environ=None):
    environ = os.environ if environ is None else environ
    return str(environ.get(GATEWAY_ENV_FALLBACK) or "").strip().lower() in ("pool", "keys")


def _retry_after(headers):
    value = str((headers or {}).get("Retry-After") or "").strip()
    if not value:
        return DEFAULT_RETRY_AFTER
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        when = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return DEFAULT_RETRY_AFTER
    if when.tzinfo is None:
        when = when.replace(tzinfo=datetime.timezone.utc)
    return max(0.0, (when - datetime.datetime.now(datetime.timezone.utc)).total_seconds())


def _error_code(raw):
    try:
        body = json.loads(raw)
    except ValueError:
        return None
    if isinstance(body, dict):
        code = body.get("error") or body.get("detail")
        if isinstance(code, dict):
            code = code.get("error")
        return str(code)[:120] if code else None
    return None


class GatewayClient:
    """Tavily-compatible client for the gateway: same search/research surface as TavilyClient.

    Error contract: 401 (bad token) and 503 (no_available_keys) fail fast; 429 waits for Retry-After
    at most twice; 502 is retried once. Never rotates keys, never sends api_key, never calls /usage.
    """

    def __init__(self, base_url, token, sleep=None):
        self.base_url = base_url.rstrip("/")
        self._token = token
        self.sleep = sleep if sleep is not None else time.sleep

    def __repr__(self):
        return f"GatewayClient(base_url={self.base_url!r})"

    def _send(self, method, path, body=None, timeout=90):
        data = None
        headers = {"Authorization": f"Bearer {self._token}", "User-Agent": GATEWAY_USER_AGENT,
                   "Accept": "application/json"}
        if body is not None:
            body = {k: v for k, v in body.items() if k != "api_key"}   # the gateway picks the key
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(f"{self.base_url}{path}", data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", errors="replace")
        return json.loads(raw) if raw else {}

    def _call(self, method, path, body=None, timeout=90):
        tries_429 = tries_502 = 0
        while True:
            try:
                return self._send(method, path, body=body, timeout=timeout)
            except urllib.error.HTTPError as e:
                status = e.code
                try:
                    raw = e.read().decode("utf-8", errors="replace")
                except Exception:
                    raw = ""
                code = _error_code(raw)
                where = f"{method} {path}"
                if status == 401:
                    raise GatewayError(f"Tavily gateway rejected the token (HTTP 401 {code or 'unauthorized'}) on {where}",
                                       401, code) from None
                if status == 503:
                    raise GatewayError(f"Tavily gateway HTTP 503 ({code or 'unavailable'}) on {where}", 503, code) from None
                if status == 429 and tries_429 < MAX_429_RETRIES:
                    delay = _retry_after(e.headers)
                    if delay > MAX_RETRY_AFTER:
                        raise GatewayError(f"Tavily gateway 429 with Retry-After {delay:.0f}s (> {MAX_RETRY_AFTER:.0f}s) "
                                           f"on {where}", 429, code) from None
                    tries_429 += 1
                    print(f"[warn] gateway 429 on {where}; retry {tries_429}/{MAX_429_RETRIES} in {delay:.1f}s",
                          file=sys.stderr)
                    self.sleep(delay)
                    continue
                if status == 502 and tries_502 < MAX_502_RETRIES:
                    tries_502 += 1
                    print(f"[warn] gateway 502 on {where}; retrying once", file=sys.stderr)
                    continue
                if status in UNREACHABLE_STATUSES:
                    raise GatewayUnreachable(f"Tavily gateway unreachable (HTTP {status}) on {where}", status) from None
                raise GatewayError(f"Tavily gateway HTTP {status} on {where}: {code or raw[:200]}", status, code) from None
            except OSError as e:   # URLError, timeouts, refused/reset connections, TLS errors
                raise GatewayUnreachable(f"Tavily gateway unreachable ({type(e).__name__}: {str(e)[:120]})") from None

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
        return self._call("POST", "/search", body, timeout=90)

    def research(self, input_text, model="pro", poll_interval=6, max_wait=600):
        d = self._call("POST", "/research", {"input": input_text, "model": model}, timeout=60)
        rid = d.get("request_id")
        if not rid:
            return d
        print(f"[info] research submitted via gateway, rid={rid}, polling every {poll_interval}s (max {max_wait}s)...",
              file=sys.stderr)
        start = time.time()
        while True:
            elapsed = time.time() - start
            if elapsed > max_wait:
                raise TimeoutError(f"Research timed out after {max_wait}s, rid={rid}")
            # same base URL and token: the gateway pins the key that created the task
            d = self._call("GET", f"/research/{rid}", timeout=30)
            status = d.get("status")
            if status not in ("pending", "in_progress", "queued"):
                print(f"[info] research finished after {elapsed:.1f}s status={status}", file=sys.stderr)
                return d
            self.sleep(poll_interval)


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
def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Tavily direct API client (bypasses MCP proxy for rate-limit reliability)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_search = sub.add_parser("search", help="Quick search with synthesized answer")
    p_search.add_argument("query", type=str)
    p_search.add_argument("--max", type=int, default=10, dest="max_results")
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

    args = parser.parse_args(argv)

    def legacy_client():
        keys = _load_keys()
        if not keys:
            print("[ERR] No Tavily keys found.", file=sys.stderr)
            print(f"      Configure the Tavily gateway ({GATEWAY_HINT}), or set TAVILY_API_KEYS env var, "
                  "or add to .env, or ensure ~/.claude.json has tavily MCP entries.", file=sys.stderr)
            sys.exit(2)
        print(f"[info] {len(keys)} tavily key(s) loaded", file=sys.stderr)
        return TavilyClient(keys)

    # Precedence: gateway config, then legacy raw keys. A broken gateway config never falls back.
    try:
        gateway = load_gateway()
    except GatewayConfigError as e:
        print(f"[ERR] {e}", file=sys.stderr)
        print("      Fix the gateway config; raw keys are not used while a gateway config is present.", file=sys.stderr)
        sys.exit(2)
    if gateway:
        print(f"[info] tavily gateway mode: {gateway['base_url']}", file=sys.stderr)
        client = GatewayClient(gateway["base_url"], gateway["token"])
    else:
        client = legacy_client()

    try:
        _run(client, args)
    except GatewayUnreachable as e:
        if not fallback_allowed():
            print(f"[ERR] {e}", file=sys.stderr)
            print(f"      Set {GATEWAY_ENV_FALLBACK}=pool to use the legacy raw keys until the gateway is back "
                  "(not recommended: it brings back client-side rotation of the shared pool).", file=sys.stderr)
            sys.exit(4)
        print("[WARN] " + "!" * 60, file=sys.stderr)
        print(f"[WARN] {GATEWAY_ENV_FALLBACK}={os.environ.get(GATEWAY_ENV_FALLBACK)}: {e}", file=sys.stderr)
        print("[WARN] FALLING BACK TO RAW TAVILY KEYS (client-side rotation of the shared pool). "
              f"Unset {GATEWAY_ENV_FALLBACK} once the gateway is back.", file=sys.stderr)
        print("[WARN] " + "!" * 60, file=sys.stderr)
        _run(legacy_client(), args)
    except GatewayError as e:
        print(f"[ERR] {e}", file=sys.stderr)
        if e.status == 401:
            print(f"      The gateway token is invalid: check {GATEWAY_HINT}.", file=sys.stderr)
            sys.exit(2)
        if e.status == 503:
            print("      The gateway has no available Tavily key right now: add keys on the gateway or wait for "
                  "cooldowns; adding raw keys locally does not help.", file=sys.stderr)
            sys.exit(3)
        sys.exit(1)


def _run(client, args):
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
