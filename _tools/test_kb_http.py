"""The `kb` MCP server over Streamable HTTP, _tools/kb_http.py (`python3 _tools/tests.py -k kb_http`).

test_kb_http_transport_*  one server per module, built on 127.0.0.1 port 0 and served on a thread: the legacy
                initialize and the 2026-07-28 server/discover handshakes, tools/list and tools/call through
                kb_mcp.handle as application/json, 202 with no body for a notification, 405 (Allow: POST) for GET
                and DELETE, 404 off the endpoint, no Mcp-Session-Id minted or echoed (even when the request sends
                one), 400 for a parse error and a batch, era-aware statuses for JSON-RPC errors (404 and 400 for a
                modern request, 200 for a legacy one), concurrent requests, and the script's own startup on --port 0.
test_kb_http_guard_*  the refusals before routing, each beside the request it must still let through: 403 for an
                Origin not in --allow-origin (an allowed one and no Origin pass), 415 for a POST that is not
                application/json (with a charset it passes), 413 for a body over --max-body (one at the cap
                passes), and no start on a non-loopback --bind without --bind-any (loopback and --bind-any pass).
test_kb_http_roots_*  the script as a subprocess with the test_kb_root.py fixture root in KB_ROOTS (the root limit
                is process-wide, so it never runs in this process): by default only public is served over HTTP
                (kb_pack and kb_status leave the fixture out), --roots public,fixture serves both, and an unknown
                or empty --roots stops the start with exit 2 and nothing bound.
"""
import http.client, json, os, subprocess, sys, threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from conftest import TOOLS

import kb_http, kb_mcp  # noqa: E402  (conftest puts _tools on sys.path)

SCRIPT = os.path.join(TOOLS, "kb_http.py")
MODERN = {"io.modelcontextprotocol/protocolVersion": "2026-07-28", "io.modelcontextprotocol/clientCapabilities": {}}


@pytest.fixture(scope="module")
def port():
    httpd = kb_http.build(0, quiet=True)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()


def call(port, method="POST", body=None, headers=None, path="/mcp"):
    """(status, headers as a lower-cased dict, raw body bytes)."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
    try:
        data = body if isinstance(body, bytes) or body is None else json.dumps(body).encode("utf-8")
        hdrs = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream", **(headers or {})}
        conn.request(method, path, body=data, headers=hdrs)
        r = conn.getresponse()
        return r.status, {k.lower(): v for k, v in r.getheaders()}, r.read()
    finally:
        conn.close()


def rpc(port, msg, headers=None):
    status, hdrs, raw = call(port, body=msg, headers=headers)
    return status, hdrs, json.loads(raw.decode("utf-8")) if raw else None


def test_kb_http_transport_binds_loopback():
    httpd = kb_http.build(0, quiet=True)
    try:
        assert httpd.server_address[0] == "127.0.0.1"
    finally:
        httpd.server_close()
    assert kb_http.PORT == 8080


def test_kb_http_transport_legacy_initialize(port):
    msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
           "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}}
    status, hdrs, reply = rpc(port, msg)
    assert status == 200
    assert hdrs["content-type"] == "application/json"
    assert "mcp-session-id" not in hdrs
    assert reply["id"] == 1
    assert reply["result"]["protocolVersion"] == "2025-03-26"
    assert reply["result"]["serverInfo"]["name"] == kb_mcp.NAME
    assert reply["result"]["instructions"] == kb_mcp.INSTRUCTIONS


def test_kb_http_transport_never_echoes_session_id(port):
    sent = {"Mcp-Session-Id": "planted-session-0001"}
    for msg in ({"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
                {"jsonrpc": "2.0", "method": "notifications/initialized"}):
        status, hdrs, raw = call(port, body=msg, headers=sent)
        assert status in (200, 202)
        assert "mcp-session-id" not in hdrs, msg["method"]
        assert b"planted-session-0001" not in raw


def test_kb_http_transport_server_discover(port):
    status, hdrs, reply = rpc(port, {"jsonrpc": "2.0", "id": 4, "method": "server/discover", "params": {"_meta": MODERN}},
                              {"MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "server/discover"})
    assert status == 200 and hdrs["content-type"] == "application/json"
    assert "2026-07-28" in reply["result"]["supportedVersions"]
    assert reply["result"]["resultType"] == "complete"
    assert "mcp-session-id" not in hdrs


def test_kb_http_transport_tools_list_and_call(port):
    _, _, listed = rpc(port, {"jsonrpc": "2.0", "id": 5, "method": "tools/list", "params": {"_meta": MODERN}})
    assert {t["name"] for t in listed["result"]["tools"]} == set(kb_mcp.HANDLERS)
    status, _, shown = rpc(port, {"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                                  "params": {"name": "kb_show", "arguments": {"path": "README.md:1", "n": 2},
                                             "_meta": MODERN}})
    assert status == 200
    assert shown["result"]["isError"] is False
    assert shown["result"]["content"][0]["text"].startswith("# README.md lines 1-2")
    # the same message over stdio's handler gives the same reply: the transport adds nothing
    same = kb_mcp.handle({"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                          "params": {"name": "kb_show", "arguments": {"path": "README.md:1", "n": 2}, "_meta": MODERN}})
    assert shown == same


def test_kb_http_transport_notification_is_202_without_body(port):
    status, hdrs, raw = call(port, body={"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert status == 202
    assert raw == b""
    assert hdrs.get("content-length") == "0"
    assert "content-type" not in hdrs


@pytest.mark.parametrize("method", ["GET", "DELETE"])
def test_kb_http_transport_get_and_delete_are_405(port, method):
    status, hdrs, _ = call(port, method=method, headers={"Mcp-Session-Id": "planted-session-0002"})
    assert status == 405
    assert hdrs["allow"] == "POST"
    assert "mcp-session-id" not in hdrs


def test_kb_http_transport_other_paths_are_404(port):
    assert call(port, body={"jsonrpc": "2.0", "id": 7, "method": "ping"}, path="/")[0] == 404
    assert call(port, method="GET", path="/sse")[0] == 404
    # a query string does not move the endpoint
    assert rpc(port, {"jsonrpc": "2.0", "id": 8, "method": "ping"})[0] == 200
    assert call(port, body={"jsonrpc": "2.0", "id": 8, "method": "ping"}, path="/mcp?x=1")[0] == 200


def test_kb_http_transport_malformed_bodies_are_400(port):
    status, hdrs, raw = call(port, body=b"{not json")
    assert status == 400 and hdrs["content-type"] == "application/json"
    assert json.loads(raw)["error"]["code"] == -32700
    status, _, reply = rpc(port, [{"jsonrpc": "2.0", "id": 9, "method": "ping"}])
    assert status == 400 and reply["error"]["code"] == -32600
    status, _, reply = rpc(port, {"jsonrpc": "1.0", "id": 10, "method": "ping"})
    assert status == 400 and reply["error"]["code"] == -32600
    status, _, reply = rpc(port, {"jsonrpc": "2.0", "id": 11, "result": {}})  # a client must not send responses
    assert status == 400 and reply["error"]["code"] == -32600


def test_kb_http_transport_error_status_by_era(port):
    status, _, reply = rpc(port, {"jsonrpc": "2.0", "id": 12, "method": "no/such/method", "params": {"_meta": MODERN}})
    assert status == 404 and reply["error"]["code"] == -32601
    status, _, reply = rpc(port, {"jsonrpc": "2.0", "id": 13, "method": "no/such/method"})
    assert status == 200 and reply["error"]["code"] == -32601  # legacy: a 404 would read as an expired session
    old = {"io.modelcontextprotocol/protocolVersion": "1999-01-01"}
    status, _, reply = rpc(port, {"jsonrpc": "2.0", "id": 14, "method": "tools/list", "params": {"_meta": old}})
    assert status == 400 and reply["error"]["code"] == -32022
    assert "2026-07-28" in reply["error"]["data"]["supported"]
    status, _, reply = rpc(port, {"jsonrpc": "2.0", "id": 15, "method": "tools/call",
                                  "params": {"name": "no_such_tool", "arguments": {}, "_meta": MODERN}})
    assert status == 400 and reply["error"]["code"] == -32602


def test_kb_http_transport_internal_error_is_500(port, monkeypatch):
    def boom(_msg):
        raise RuntimeError("planted failure")
    monkeypatch.setattr(kb_mcp, "handle", boom)
    status, _, reply = rpc(port, {"jsonrpc": "2.0", "id": 16, "method": "ping"})
    assert status == 500 and reply == kb_mcp.error(16, -32603, "Internal error")


def test_kb_http_transport_concurrent_requests(port):
    def one(i):
        return rpc(port, {"jsonrpc": "2.0", "id": 100 + i, "method": "tools/call",
                          "params": {"name": "kb_show", "arguments": {"path": "README.md:1", "n": 1}}})
    with ThreadPoolExecutor(8) as ex:
        out = list(ex.map(one, range(16)))
    assert [r[0] for r in out] == [200] * 16
    assert sorted(r[2]["id"] for r in out) == list(range(100, 116))


def test_kb_http_transport_script_starts_on_a_free_port():
    p = subprocess.Popen([sys.executable, SCRIPT, "--port", "0"], stderr=subprocess.PIPE, stdout=subprocess.PIPE,
                         text=True, encoding="utf-8")
    try:
        line = p.stderr.readline()
        assert line.startswith("kb_http: serving http://127.0.0.1:"), line
        port = int(line.rsplit(":", 1)[1].split("/")[0])
        status, _, reply = rpc(port, {"jsonrpc": "2.0", "id": 1, "method": "ping"})
        assert status == 200 and reply["result"]["resultType"] == "complete"
    finally:
        p.terminate()
        p.communicate(timeout=30)


def test_kb_http_transport_help_and_bad_port():
    out = subprocess.run([sys.executable, SCRIPT, "--help"], capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0 and "POST /mcp" in out.stdout and "Mcp-Session-Id" in out.stdout
    bad = subprocess.run([sys.executable, SCRIPT, "--port", "70000"], capture_output=True, text=True, encoding="utf-8")
    assert bad.returncode == 2 and "--port" in bad.stderr


ALLOWED = "https://copilot.example.com"
CAP = 256
PING = {"jsonrpc": "2.0", "id": 200, "method": "ping"}


@pytest.fixture(scope="module")
def guarded():
    """A server with one allowed Origin and a small body cap."""
    httpd = kb_http.build(0, quiet=True, allow_origins=[ALLOWED], max_body=CAP)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()


def sized(n):
    """A ping request body of exactly n bytes (JSON allows trailing whitespace)."""
    raw = json.dumps(PING).encode("utf-8")
    assert len(raw) <= n
    return raw + b" " * (n - len(raw))


def raw_post(port, headers, data=b""):
    """POST with exactly these headers (http.client adds none of its own here): (status, headers, body)."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
    try:
        conn.putrequest("POST", "/mcp", skip_accept_encoding=True)
        for k, v in headers.items():
            conn.putheader(k, v)
        conn.endheaders(data or None)
        r = conn.getresponse()
        return r.status, {k.lower(): v for k, v in r.getheaders()}, r.read()
    finally:
        conn.close()


@pytest.mark.parametrize("origin", ["https://evil.example.net", "http://copilot.example.com", "null",
                                    "https://copilot.example.com:8443"])
def test_kb_http_guard_bad_origin_is_403(guarded, origin):
    for method in ("POST", "GET", "DELETE"):
        status, hdrs, raw = call(guarded, method=method, body=PING if method == "POST" else None,
                                 headers={"Origin": origin})
        assert status == 403, (method, origin)
        assert hdrs["connection"] == "close"
        assert b"Origin" in raw and b"result" not in raw
    # off the endpoint too: the Origin is checked before the path is routed
    assert call(guarded, body=PING, headers={"Origin": origin}, path="/")[0] == 403


def test_kb_http_guard_allowed_or_absent_origin_passes(guarded, port):
    for origin in (ALLOWED, ALLOWED.upper() + "/"):
        status, _, reply = rpc(guarded, PING, {"Origin": origin})
        assert status == 200 and reply["id"] == 200, origin
    status, _, reply = rpc(guarded, PING)  # a server-to-server client sends no Origin
    assert status == 200 and reply["id"] == 200
    # planted failure: the default server allows no Origin, so the one allowed above is refused there
    assert call(port, body=PING, headers={"Origin": ALLOWED})[0] == 403
    assert call(port, body=PING)[0] == 200


@pytest.mark.parametrize("ctype", ["text/plain", "application/x-www-form-urlencoded", "multipart/form-data; boundary=x",
                                   "application/jsonx", None])
def test_kb_http_guard_non_json_content_type_is_415(guarded, ctype):
    data = json.dumps(PING).encode("utf-8")
    headers = {"Content-Length": str(len(data))} | ({"Content-Type": ctype} if ctype else {})
    status, hdrs, raw = raw_post(guarded, headers, data)
    assert status == 415, ctype
    assert hdrs["connection"] == "close"
    assert b"application/json" in raw


def test_kb_http_guard_json_content_type_passes(guarded):
    for ctype in ("application/json", "application/json; charset=utf-8", "Application/JSON"):
        status, _, reply = rpc(guarded, PING, {"Content-Type": ctype})
        assert status == 200 and reply["id"] == 200, ctype
    # GET and DELETE carry no body: their Content-Type is not checked on the way to 405
    assert call(guarded, method="GET", headers={"Content-Type": "text/plain"})[0] == 405


def test_kb_http_guard_body_over_cap_is_413(guarded):
    status, hdrs, raw = call(guarded, body=sized(CAP + 1))
    assert status == 413
    assert hdrs["connection"] == "close"
    assert str(CAP).encode("utf-8") in raw
    # the Content-Length alone decides: a huge one is refused without a byte of body sent
    assert raw_post(guarded, {"Content-Type": "application/json", "Content-Length": str(1 << 40)})[0] == 413


def test_kb_http_guard_body_at_cap_passes(guarded, port):
    status, _, reply = rpc(guarded, sized(CAP))
    assert status == 200 and reply["id"] == 200
    # planted failure: the default cap is far above this size, so the body refused above passes there
    assert kb_http.MAX_BODY > CAP + 1
    status, _, reply = rpc(port, sized(CAP + 1))
    assert status == 200 and reply["id"] == 200


@pytest.mark.parametrize("host", ["0.0.0.0", "192.0.2.10", "::", "2001:db8::1", "localhost", "not-an-ip"])
def test_kb_http_guard_public_bind_refused(host):
    with pytest.raises(ValueError):
        kb_http.build(0, quiet=True, host=host)
    bad = subprocess.run([sys.executable, SCRIPT, "--bind", host, "--port", "0"], capture_output=True, text=True,
                         encoding="utf-8", timeout=60)
    assert bad.returncode == 2 and "--bind" in bad.stderr and "serving" not in bad.stderr


def test_kb_http_guard_loopback_or_bind_any_passes():
    for host in ("127.0.0.1", "127.255.255.254", "::1"):
        assert kb_http.check_bind(host).is_loopback
    # planted failure: --bind-any lets the addresses refused above through the check
    for host in ("0.0.0.0", "192.0.2.10", "::"):
        assert str(kb_http.check_bind(host, bind_any=True)) == host
    try:
        httpd6 = kb_http.build(0, quiet=True, host="::1")
    except OSError:
        pytest.skip("no IPv6 loopback on this host")
    try:
        assert httpd6.server_address[0] == "::1"
        assert kb_http.url(httpd6).startswith("http://[::1]:")
    finally:
        httpd6.server_close()


def test_kb_http_guard_help_names_the_options():
    out = subprocess.run([sys.executable, SCRIPT, "--help"], capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0
    for word in ("--bind ", "--bind-any", "--allow-origin", "--max-body", "403", "413", "415"):
        assert word in out.stdout, word
    bad = subprocess.run([sys.executable, SCRIPT, "--max-body", "0"], capture_output=True, text=True, encoding="utf-8")
    assert bad.returncode == 2 and "--max-body" in bad.stderr


def roots_env(tmp_path):
    """The environment with the test_kb_root.py fixture root as a KB_ROOTS directory and no shared index."""
    from test_kb_root import make_root
    root = tmp_path / "team-kb"
    make_root(str(root))
    env = {k: v for k, v in os.environ.items() if k not in ("KB_ROOTS", "KB_INDEX", "CLAUDE_PLUGIN_DATA")}
    return env | {"KB_ROOTS": str(root), "KB_INDEX": "0"}


def served_calls(env, args, calls):
    """Start the script with `args` on a free port, send each (tool, arguments) as a tools/call over HTTP, stop it.
    Returns (startup line, [(isError, text)])."""
    p = subprocess.Popen([sys.executable, SCRIPT, "--port", "0", *args], stderr=subprocess.PIPE,
                         stdout=subprocess.DEVNULL, text=True, encoding="utf-8", env=env)
    try:
        line = p.stderr.readline()
        assert line.startswith("kb_http: serving http://127.0.0.1:"), line
        port = int(line.rsplit(":", 1)[1].split("/")[0])
        out = []
        for i, (name, arguments) in enumerate(calls, start=1):
            status, _, reply = rpc(port, {"jsonrpc": "2.0", "id": i, "method": "tools/call",
                                          "params": {"name": name, "arguments": arguments}})
            assert status == 200, (status, reply)
            out.append((reply["result"]["isError"], reply["result"]["content"][0]["text"]))
        return line, out
    finally:
        p.terminate()
        p.communicate(timeout=30)


def test_kb_http_roots_default_serves_public_only(tmp_path):
    from test_kb_root import QUESTION
    line, out = served_calls(roots_env(tmp_path), [], [("kb_status", {}), ("kb_pack", {"question": QUESTION}),
                                                       ("kb_pack", {"question": QUESTION, "root": "fixture"})])
    assert line.rstrip().endswith(", roots public"), line
    assert "roots: public (prefix S, public, " in out[0][1] and "fixture" not in out[0][1], out[0][1]
    assert "fixture/" not in out[1][1], out[1][1][:300]
    assert out[2][0] and "no root 'fixture'; roots: public" in out[2][1], out[2]
    assert kb_http.ROOTS == ("public",)


def test_kb_http_roots_names_the_full_set(tmp_path):
    from test_kb_root import QUESTION
    line, out = served_calls(roots_env(tmp_path), ["--roots", "public,fixture"],
                             [("kb_status", {}), ("kb_pack", {"question": QUESTION})])
    assert line.rstrip().endswith(", roots public,fixture"), line
    assert "roots: public (prefix S, public, " in out[0][1] and "; fixture (prefix FXT, " in out[0][1], out[0][1]
    assert "fixture/print/queues.md:" in out[1][1], out[1][1][:300]
    # the named set is the whole set: --roots fixture leaves public out
    _, out = served_calls(roots_env(tmp_path / "alone"), ["--roots=fixture"], [("kb_status", {})])
    assert "roots: fixture (prefix FXT, " in out[0][1] and "public (prefix" not in out[0][1], out[0][1]


@pytest.mark.parametrize("args, message", [
    (["--roots", "public,no-such-root"], "kb_http: no root 'no-such-root'; roots: public, fixture"),
    (["--roots", "nosuch"], "kb_http: no root 'nosuch'; roots: public, fixture"),
    (["--roots", " , "], "kb_http: --roots needs one or more root names"),
])
def test_kb_http_roots_unknown_name_stops_the_start(tmp_path, args, message):
    """Planted failure: a --roots name that is no root exits 2 before anything is bound, with the error on stderr."""
    p = subprocess.run([sys.executable, SCRIPT, "--port", "0", *args], capture_output=True, text=True,
                       encoding="utf-8", env=roots_env(tmp_path), timeout=120)
    assert p.returncode == 2, (p.returncode, p.stdout, p.stderr)
    assert message in p.stderr and "serving" not in p.stderr and "Traceback" not in p.stderr, p.stderr
    assert p.stdout == ""


def test_kb_http_roots_help_names_the_option():
    out = subprocess.run([sys.executable, SCRIPT, "--help"], capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0 and "--roots NAME[,NAME]" in out.stdout and "not access control" in out.stdout
