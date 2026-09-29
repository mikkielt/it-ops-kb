"""The `kb` MCP server over Streamable HTTP, _tools/kb_http.py (`python3 _tools/tests.py -k kb_http_transport`).

test_kb_http_transport_*  one server per module, built on 127.0.0.1 port 0 and served on a thread: the legacy
                initialize and the 2026-07-28 server/discover handshakes, tools/list and tools/call through
                kb_mcp.handle as application/json, 202 with no body for a notification, 405 (Allow: POST) for GET
                and DELETE, 404 off the endpoint, no Mcp-Session-Id minted or echoed (even when the request sends
                one), 400 for a parse error and a batch, era-aware statuses for JSON-RPC errors (404 and 400 for a
                modern request, 200 for a legacy one), concurrent requests, and the script's own startup on --port 0.
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
