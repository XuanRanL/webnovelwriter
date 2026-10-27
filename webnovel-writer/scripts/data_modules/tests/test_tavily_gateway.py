"""tavily_search.py gateway mode.

Configured (~/.xuanran-seo/credentials/tavily-gateway.json, or TAVILY_GATEWAY_URL / TAVILY_GATEWAY_TOKEN which
override it) = every request goes to the gateway with `Authorization: Bearer <token>`, no key rotation, no
api_key in the body. Absent = the legacy key rotation, unchanged. A broken config is an error, never a silent
fallback to raw keys; only TAVILY_GATEWAY_FALLBACK=pool|keys lets an unreachable gateway use the keys, loudly.

The gateway here is a real local HTTP server, so urllib's HTTPError / Retry-After handling is exercised.
No test reads the real gateway config, the workspace .env keys, or the network.
"""
from __future__ import annotations

import json
import threading
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import tavily_search as ts

TOKEN = "gw-test-token-0001"
RAW_KEY = "tvly-test-raw-1"


class FakeGateway:
    def __init__(self):
        self.script: list = []      # (status, json, headers) answered in order before the defaults
        self.requests: list = []
        self.polls = 0
        state = self

        class Handler(BaseHTTPRequestHandler):
            def _handle(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length)) if length else None
                state.requests.append({"method": self.command, "path": self.path,
                                       "auth": self.headers.get("Authorization"), "body": body})
                status, payload, headers = state.script.pop(0) if state.script else state.default(self.command, self.path)
                data = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            do_GET = do_POST = _handle

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def default(self, method, path):
        if method == "POST" and path == "/search":
            return 200, {"query": "q", "answer": "A", "usage": {"credits": 1},
                         "results": [{"title": "T", "url": "https://example.com/a", "content": "c", "score": 0.9}]}, {}
        if method == "POST" and path == "/research":
            return 201, {"request_id": "rid-1", "status": "pending"}, {}
        if method == "GET" and path == "/research/rid-1":
            self.polls += 1
            if self.polls < 2:
                return 200, {"request_id": "rid-1", "status": "in_progress"}, {}
            return 200, {"request_id": "rid-1", "status": "completed", "content": "report",
                         "sources": [{"title": "S", "url": "https://example.com/s"}]}, {}
        return 404, {"error": "not_found"}, {}

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def gw(monkeypatch, tmp_path):
    for name in ("TAVILY_GATEWAY_URL", "TAVILY_GATEWAY_TOKEN", "TAVILY_GATEWAY_FALLBACK",
                 "TAVILY_API_KEYS", "TAVILY_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(ts, "GATEWAY_FILE", tmp_path / "tavily-gateway.json")
    # Legacy mode must never reach the real workspace .env keys or api.tavily.com from a test.
    monkeypatch.setattr(ts, "_load_keys", lambda: [RAW_KEY])
    server = FakeGateway()
    monkeypatch.setattr(ts, "API_BASE", server.url)
    yield server
    server.close()


def use_gateway_env(monkeypatch, url):
    monkeypatch.setenv("TAVILY_GATEWAY_URL", url)
    monkeypatch.setenv("TAVILY_GATEWAY_TOKEN", TOKEN)


# ---------- config ----------

def test_absent_config_means_legacy(tmp_path):
    assert ts.load_gateway({}, tmp_path / "none.json") is None


def test_file_config_and_env_override(tmp_path):
    path = tmp_path / "tavily-gateway.json"
    path.write_text(json.dumps({"base_url": "https://file.example/", "token": "gw-file-token", "note": "ignored"}),
                    encoding="utf-8")
    assert ts.load_gateway({}, path) == {"base_url": "https://file.example", "token": "gw-file-token"}
    env = {"TAVILY_GATEWAY_URL": "https://env.example", "TAVILY_GATEWAY_TOKEN": "gw-env-token"}
    assert ts.load_gateway(env, path) == {"base_url": "https://env.example", "token": "gw-env-token"}
    assert ts.load_gateway({"TAVILY_GATEWAY_URL": "https://env.example"}, path)["token"] == "gw-file-token"


@pytest.mark.parametrize("payload,env", [
    ({"base_url": "https://gw.example"}, {}),                              # no token
    ("{broken", {}),                                                       # unreadable
    (None, {"TAVILY_GATEWAY_URL": "https://gw.example"}),                  # env URL, no token anywhere
    ({"base_url": "http://gw.example", "token": "gw-file-token"}, {}),     # token over plain http
])
def test_broken_config_is_an_error(tmp_path, payload, env):
    path = tmp_path / "tavily-gateway.json"
    if payload is not None:
        path.write_text(payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8")
    with pytest.raises(ts.GatewayConfigError) as caught:
        ts.load_gateway(env, path)
    assert "gw-file-token" not in str(caught.value)


def test_fallback_is_explicit():
    assert not ts.fallback_allowed({})
    assert ts.fallback_allowed({"TAVILY_GATEWAY_FALLBACK": "pool"})
    assert ts.fallback_allowed({"TAVILY_GATEWAY_FALLBACK": "keys"})
    assert not ts.fallback_allowed({"TAVILY_GATEWAY_FALLBACK": "1"})


# ---------- client: the gateway's error contract ----------

def client(gw, waits=None):
    return ts.GatewayClient(gw.url, TOKEN, sleep=(waits.append if waits is not None else lambda _s: None))


def test_search_sends_the_token_and_no_api_key(gw):
    got = client(gw).search("q", max_results=3)
    assert got["results"][0]["url"] == "https://example.com/a"
    assert [(r["method"], r["path"], r["auth"]) for r in gw.requests] == [("POST", "/search", f"Bearer {TOKEN}")]
    assert "api_key" not in gw.requests[0]["body"]
    assert TOKEN not in repr(client(gw))


def test_401_fails_fast(gw):
    gw.script = [(401, {"error": "invalid_token"}, {})]
    with pytest.raises(ts.GatewayError) as caught:
        client(gw).search("q")
    assert caught.value.status == 401 and len(gw.requests) == 1


def test_503_no_available_keys_fails_fast(gw):
    gw.script = [(503, {"error": "no_available_keys"}, {})]
    with pytest.raises(ts.GatewayError) as caught:
        client(gw).search("q")
    assert (caught.value.status, caught.value.code, len(gw.requests)) == (503, "no_available_keys", 1)


def test_429_waits_for_retry_after_at_most_twice(gw):
    waits = []
    gw.script = [(429, {"error": "rate_limited"}, {"Retry-After": "3"})] * 3
    with pytest.raises(ts.GatewayError) as caught:
        client(gw, waits).search("q")
    assert (caught.value.status, len(gw.requests), waits) == (429, 3, [3.0, 3.0])
    gw.requests.clear()
    waits.clear()
    gw.script = [(429, {"error": "rate_limited"}, {"Retry-After": "2"})]
    assert client(gw, waits).search("q")["results"]
    assert (len(gw.requests), waits) == (2, [2.0])


def test_502_is_retried_once(gw):
    gw.script = [(502, {"error": "bad_gateway"}, {})]
    assert client(gw).search("q")["results"]
    assert len(gw.requests) == 2
    gw.requests.clear()
    gw.script = [(502, {"error": "bad_gateway"}, {})] * 2
    with pytest.raises(ts.GatewayError):
        client(gw).search("q")
    assert len(gw.requests) == 2


def test_research_polls_the_gateway_with_the_same_token(gw):
    got = client(gw).research("question", poll_interval=0, max_wait=30)
    assert got["status"] == "completed"
    assert [(r["method"], r["path"]) for r in gw.requests] == [
        ("POST", "/research"), ("GET", "/research/rid-1"), ("GET", "/research/rid-1")]
    assert {r["auth"] for r in gw.requests} == {f"Bearer {TOKEN}"}


def test_unreachable_gateway_raises_unreachable(monkeypatch):
    def refuse(request, timeout=None):
        raise urllib.error.URLError(ConnectionRefusedError("refused"))
    monkeypatch.setattr(ts.urllib.request, "urlopen", refuse)
    with pytest.raises(ts.GatewayUnreachable):
        ts.GatewayClient("https://gateway.invalid", TOKEN, sleep=lambda _s: None).search("q")


# ---------- CLI: precedence gateway config, then legacy ----------

def test_cli_prefers_the_gateway_over_raw_keys(gw, monkeypatch, capsys):
    use_gateway_env(monkeypatch, gw.url)
    monkeypatch.setenv("TAVILY_API_KEYS", RAW_KEY)
    ts.main(["search", "q", "--json"])
    out, err = capsys.readouterr()
    assert json.loads(out)["results"][0]["url"] == "https://example.com/a"
    assert {r["auth"] for r in gw.requests} == {f"Bearer {TOKEN}"}
    assert "gateway" in err and TOKEN not in out + err and RAW_KEY not in out + err


def test_cli_reads_the_config_file(gw, capsys):
    ts.GATEWAY_FILE.write_text(json.dumps({"base_url": gw.url, "token": TOKEN}), encoding="utf-8")
    ts.main(["search", "q"])
    assert "## Results (1)" in capsys.readouterr().out
    assert gw.requests[0]["auth"] == f"Bearer {TOKEN}"


def test_cli_without_gateway_config_keeps_the_legacy_keys(gw, capsys):
    ts.main(["search", "q", "--json"])
    assert gw.requests[0]["auth"] == f"Bearer {RAW_KEY}"


def test_cli_broken_config_never_falls_back_to_keys(gw, capsys):
    ts.GATEWAY_FILE.write_text(json.dumps({"base_url": gw.url}), encoding="utf-8")
    with pytest.raises(SystemExit) as caught:
        ts.main(["search", "q"])
    assert caught.value.code == 2
    assert gw.requests == []
    assert "tavily-gateway.json" in capsys.readouterr().err


@pytest.mark.parametrize("status,code,exit_code", [(401, "invalid_token", 2), (503, "no_available_keys", 3)])
def test_cli_gateway_refusals_fail_fast_with_their_exit_code(gw, monkeypatch, capsys, status, code, exit_code):
    use_gateway_env(monkeypatch, gw.url)
    gw.script = [(status, {"error": code}, {})]
    with pytest.raises(SystemExit) as caught:
        ts.main(["search", "q"])
    assert caught.value.code == exit_code
    assert len(gw.requests) == 1
    assert code in capsys.readouterr().err


def _gateway_down(monkeypatch):
    real = ts.urllib.request.urlopen

    def urlopen(request, timeout=None):
        if request.full_url.startswith("https://gateway.invalid"):
            raise urllib.error.URLError(ConnectionRefusedError("refused"))
        return real(request, timeout=timeout)
    monkeypatch.setattr(ts.urllib.request, "urlopen", urlopen)
    use_gateway_env(monkeypatch, "https://gateway.invalid")


def test_cli_unreachable_gateway_without_opt_in_never_uses_keys(gw, monkeypatch, capsys):
    _gateway_down(monkeypatch)
    with pytest.raises(SystemExit) as caught:
        ts.main(["search", "q"])
    assert caught.value.code == 4
    assert gw.requests == []  # the legacy endpoint (API_BASE) was never called
    assert "TAVILY_GATEWAY_FALLBACK" in capsys.readouterr().err


def test_cli_fallback_opt_in_uses_keys_loudly(gw, monkeypatch, capsys):
    _gateway_down(monkeypatch)
    monkeypatch.setenv("TAVILY_GATEWAY_FALLBACK", "pool")
    ts.main(["search", "q", "--json"])
    out, err = capsys.readouterr()
    assert json.loads(out)["results"]
    assert [r["auth"] for r in gw.requests] == [f"Bearer {RAW_KEY}"]
    assert "TAVILY_GATEWAY_FALLBACK" in err and TOKEN not in err
