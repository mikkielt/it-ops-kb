#!/usr/bin/env python3
"""`kb` over Streamable HTTP: the read-only MCP server of kb_mcp.py on one HTTP endpoint (stdlib only).

  python3 _tools/kb_http.py              serve http://127.0.0.1:8080/mcp until interrupted (Ctrl+C); logs go to stderr
  python3 _tools/kb_http.py --port N     another port; 0 picks a free one (the startup line on stderr names it)

The endpoint is `/mcp` on 127.0.0.1. Every JSON-RPC message goes to kb_mcp.handle, so the tools, the instructions
and both handshakes are the stdio server's: a legacy client's `initialize` (2025-11-25 and earlier, as Copilot
Studio uses) and a 2026-07-28 client's `server/discover` with the protocol version in each request's `_meta`.

  POST /mcp         one JSON-RPC message per request body (UTF-8 JSON); batches are refused
    request         200 with the response as `application/json` (no SSE stream: every tool answers at once)
    notification    202 Accepted, no body
    malformed       400 with a JSON-RPC error: parse error (-32700), invalid request (-32600), a batch
    modern request  (its `_meta` names a protocol version) an error maps to the status 2026-07-28 gives it:
                    unsupported version (-32022) and invalid params (-32602) 400, unknown method (-32601) 404;
                    a legacy request's JSON-RPC error stays 200, since a legacy client reads a 404 as an
                    expired session
    internal error  500 with JSON-RPC -32603
  GET, DELETE /mcp  405 Method Not Allowed (`Allow: POST`): no standalone SSE stream, no session to end
  other paths       404

Stateless: the server keeps no protocol session. It never mints an `Mcp-Session-Id`, and ignores one a client
sends. Requests are served on threads (ThreadingHTTPServer); the calls into kb_mcp run one at a time, because the
tools redirect the process-wide stdout while they work.
"""
import argparse, json, sys, threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import kb_mcp  # noqa: E402

HOST = "127.0.0.1"
PORT = 8080
ENDPOINT = "/mcp"
MODERN_STATUS = {-32022: HTTPStatus.BAD_REQUEST, -32602: HTTPStatus.BAD_REQUEST, -32601: HTTPStatus.NOT_FOUND}
_HANDLE_LOCK = threading.Lock()


def answer(msg):
    """(HTTP status, JSON-RPC reply or None) for one parsed request body."""
    if isinstance(msg, list):
        return HTTPStatus.BAD_REQUEST, kb_mcp.error(None, -32600, "Invalid Request: batches are not supported")
    try:
        with _HANDLE_LOCK:
            reply = kb_mcp.handle(msg)
    except Exception as e:  # noqa: BLE001 - one bad request must not end the server
        print(f"kb_http: internal error: {type(e).__name__}: {e}", file=sys.stderr)
        return HTTPStatus.INTERNAL_SERVER_ERROR, kb_mcp.error(msg.get("id") if isinstance(msg, dict) else None,
                                                              -32603, "Internal error")
    if reply is None:
        return HTTPStatus.ACCEPTED, None
    code = (reply.get("error") or {}).get("code")
    if code == -32600:
        return HTTPStatus.BAD_REQUEST, reply
    if code in MODERN_STATUS and is_modern(msg):
        return MODERN_STATUS[code], reply
    return HTTPStatus.OK, reply


def is_modern(msg):
    """True when a request states its protocol version in `_meta` (2026-07-28 and later); legacy requests do not."""
    params = msg.get("params") if isinstance(msg, dict) else None
    meta = params.get("_meta") if isinstance(params, dict) else None
    return isinstance(meta, dict) and kb_mcp.PV_KEY in meta


class Handler(BaseHTTPRequestHandler):
    """One HTTP request to the MCP endpoint. `refuse` is the single place every request passes before routing."""
    protocol_version = "HTTP/1.1"
    server_version = "kb-http/" + kb_mcp.VERSION

    def refuse(self):
        """(status, message) that stops this request before it is routed, or None to let it through."""
        return None

    def routed(self):
        """True when the request may go on: the path is the endpoint and `refuse` let it through; else the refusal
        is already sent."""
        stop = self.refuse()
        if stop is not None:
            self.send_plain(*stop)
            return False
        if urlsplit(self.path).path != ENDPOINT:
            self.send_plain(HTTPStatus.NOT_FOUND, f"not found: the MCP endpoint is {ENDPOINT}")
            return False
        return True

    def do_POST(self):
        if not self.routed():
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if length < 0:
            self.send_json(HTTPStatus.BAD_REQUEST, kb_mcp.error(None, -32600, "Invalid Request: bad Content-Length"))
            return
        body = self.rfile.read(length) if length else b""
        try:
            msg = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            self.send_json(HTTPStatus.BAD_REQUEST, kb_mcp.error(None, -32700, "Parse error"))
            return
        self.send_json(*answer(msg))

    def do_GET(self):
        self.not_allowed()

    def do_DELETE(self):
        self.not_allowed()

    def not_allowed(self):
        if self.routed():
            self.send_plain(HTTPStatus.METHOD_NOT_ALLOWED, "method not allowed: POST one JSON-RPC message",
                            {"Allow": "POST"})

    def send_json(self, status, reply):
        if reply is None:
            self.send_body(status, b"", None)
        else:
            self.send_body(status, json.dumps(reply, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
                           "application/json")

    def send_plain(self, status, text, headers=None):
        self.send_body(status, (text + "\n").encode("utf-8"), "text/plain; charset=utf-8", headers)

    def send_body(self, status, data, content_type, headers=None):
        self.send_response(status)
        if content_type:
            self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if data:
            self.wfile.write(data)

    def log_message(self, format, *args):  # noqa: A002 - the base class's signature
        if not getattr(self.server, "quiet", False):
            super().log_message(format, *args)


def build(port=PORT, quiet=False):
    """The server bound to HOST:port (0: a free port, in server_address) and not yet serving: tests run
    serve_forever on a thread and call shutdown."""
    httpd = ThreadingHTTPServer((HOST, port), Handler)
    httpd.daemon_threads = True
    httpd.quiet = quiet
    return httpd


def serve(port=PORT):
    """Serve until interrupted. Returns the exit code."""
    try:
        httpd = build(port)
    except OSError as e:
        print(f"kb_http: cannot listen on {HOST}:{port}: {e}", file=sys.stderr)
        return 1
    threading.Thread(target=kb_mcp.warm, daemon=True).start()
    print(f"kb_http: serving http://{HOST}:{httpd.server_address[1]}{ENDPOINT}", file=sys.stderr, flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=PORT, help=f"TCP port on {HOST} (default {PORT}; 0 picks a free one)")
    args = ap.parse_args(argv)
    if not 0 <= args.port <= 65535:
        ap.error("--port must be 0-65535")
    return serve(args.port)


if __name__ == "__main__":
    sys.exit(main())
