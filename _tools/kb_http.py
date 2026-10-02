#!/usr/bin/env python3
"""`kb` over Streamable HTTP: the read-only MCP server of kb_mcp.py on one HTTP endpoint (stdlib only).

  python3 _tools/kb_http.py                   serve http://127.0.0.1:8080/mcp until interrupted (Ctrl+C); logs to stderr
  python3 _tools/kb_http.py --port N          another port; 0 picks a free one (the startup line on stderr names it)
  python3 _tools/kb_http.py --bind ADDR       listen on another IP address (default 127.0.0.1); one outside loopback
                                              (127.0.0.0/8, ::1) is refused, exit 2, unless --bind-any is given too
  python3 _tools/kb_http.py --bind-any        allow a non-loopback --bind (0.0.0.0, a LAN address): the server has
                                              no authentication, so put it behind something that has
  python3 _tools/kb_http.py --allow-origin O  a browser origin (scheme://host[:port]) whose requests are served;
                                              repeatable; none by default
  python3 _tools/kb_http.py --max-body N      the largest request body in bytes (default 1048576, 1 MiB)
  python3 _tools/kb_http.py --roots NAME[,NAME]
                                              the roots to serve, repository roots or KB_ROOTS directories, as the
                                              full set (`--roots public,team` serves both); default: public only.
                                              An unknown name stops the start before anything is bound, exit 2

Roots: this server serves only kb/public unless --roots names more, where kb_mcp.py serves every root by default.
A hosted endpoint answers clients outside the team that runs it, and a root is a filter on what the tools read,
not access control: an internal root is served only when --roots names it. The limit is kbcommon.serve_only, the
same one kb_mcp.py --roots sets, so every tool and kb_status see the named roots alone; the startup line lists them.
Being limited, it also names no local path or update command: a clone behind its upstream gets a `kb copy:` line
in kb_pack without them, and kb_status leaves out kb_dir and update (kb_mcp.behind_note).

The endpoint is `/mcp`. Every JSON-RPC message goes to kb_mcp.handle, so the tools, the instructions and both
handshakes are the stdio server's: a legacy client's `initialize` (2025-11-25 and earlier, as Copilot Studio uses)
and a 2026-07-28 client's `server/discover` with the protocol version in each request's `_meta`.

Guards, checked on every request before its path is routed (the MCP transport requires Origin validation against
DNS rebinding, and recommends a loopback bind for a local server):
  Origin          a request whose `Origin` header is not in --allow-origin gets 403 Forbidden (compared without
                  case or a trailing slash; `null` is refused too). A request with no Origin header passes: it
                  comes from a server-to-server client such as Copilot Studio's connector, not a browser page
  Content-Type    a POST whose Content-Type is not `application/json` (parameters such as charset allowed), or
                  that has none, gets 415 Unsupported Media Type: a browser page can send text/plain to another
                  origin without a CORS preflight, but not application/json
  body size       a POST whose Content-Length is over --max-body gets 413 Content Too Large, decided on the header.
                  The default 1 MiB is far above any real request (a tool call carries a question or a path, a
                  few KB) and bounds the memory one request can make a serving thread hold
  chunked body    a POST sent with `Transfer-Encoding: chunked` (and no Content-Length) is read chunk by chunk up
                  to --max-body; one that runs past it gets 413 as an over-long body does, when the limit is
                  reached. Any other transfer coding gets 501 Not Implemented; both Transfer-Encoding and
                  Content-Length, or broken chunk framing, get 400 Bad Request
  stalled body    a connection that sends nothing for 30 seconds (a body announced and not sent) is dropped.
  A refusal is plain text and closes the connection. A refused body up to 64 KiB is read and dropped first, so the
  client is not reset before it reads the refusal; a larger one is never read. A 404 reads and drops its body the
  same way, and closes the connection when the body was not read to its end.

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

Log: one line per answered request on stderr, `kb_http: METHOD STATUS MSms` (the method, the status, the milliseconds
since the request line was read). Never the client address, the path or the request line, so a host journal holds
no personal data and no question; the base class's own access and error lines are dropped. An internal error adds
one line, `kb_http: internal error: CLASS`: the exception's class, never its message, which can hold a question
or a path from the request.

Exit codes: 0 after an interrupt, 1 when the address cannot be bound, 2 for a bad option (a non-loopback --bind
without --bind-any, and a --roots name that is no root, among them).
"""
import argparse, ipaddress, json, re, socket, sys, threading, time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import kb_mcp, kbcommon  # noqa: E402

HOST = "127.0.0.1"
PORT = 8080
ENDPOINT = "/mcp"
MAX_BODY = 1 << 20  # 1 MiB: the module docstring says why
JSON_TYPE = "application/json"
ROOTS = ("public",)  # served when --roots is not given: the module docstring says why
DRAIN = 64 << 10  # a refused body up to this size is read and dropped before the refusal is sent
CHUNK_SIZE = re.compile(rb"[0-9A-Fa-f]{1,16}")  # a chunk-size line's size, before any chunk extension
LINE_MAX = 64 << 10  # the longest chunk-size or trailer line read
LOGGED_METHODS = frozenset({"GET", "POST", "DELETE", "PUT", "PATCH", "HEAD", "OPTIONS"})  # a method named in a log line
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
        print(f"kb_http: internal error: {type(e).__name__}", file=sys.stderr)  # never the message: it can hold the request
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
    timeout = 30  # seconds a connection may stall (a body announced and not sent) before it is dropped

    def refuse(self):
        """(status, message) that stops this request before it is routed, or None to let it through."""
        origin = self.headers.get("Origin")
        if origin is not None and norm_origin(origin) not in self.server.allow_origins:
            return HTTPStatus.FORBIDDEN, f"forbidden: Origin {origin!r} is not allowed (kb_http.py --allow-origin)"
        if self.command != "POST":
            return None
        te = self.headers.get("Transfer-Encoding")
        if te is not None:
            if self.headers.get("Content-Length") is not None:
                return HTTPStatus.BAD_REQUEST, "bad request: both Transfer-Encoding and Content-Length"
            if [c.strip().lower() for c in te.split(",")] != ["chunked"]:
                return (HTTPStatus.NOT_IMPLEMENTED,
                        f"not implemented: Transfer-Encoding {te!r}; send chunked or a Content-Length")
        media = (self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if media != JSON_TYPE:
            return (HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                    f"unsupported media type: POST one JSON-RPC message as {JSON_TYPE}, not {media or 'no type'}")
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None  # do_POST answers a bad Content-Length with a JSON-RPC error
        if length > self.server.max_body:
            return (HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    f"content too large: {length} bytes, the limit is {self.server.max_body} (kb_http.py --max-body)")
        return None

    def routed(self):
        """True when the request may go on: the path is the endpoint and `refuse` let it through; else the refusal
        is already sent."""
        stop = self.refuse()
        if stop is not None:
            self.discard_body()
            self.send_plain(*stop, {"Connection": "close"})
            return False
        if urlsplit(self.path).path != ENDPOINT:
            whole = self.discard_body()
            self.send_plain(HTTPStatus.NOT_FOUND, f"not found: the MCP endpoint is {ENDPOINT}",
                            None if whole else {"Connection": "close"})
            return False
        return True

    def is_chunked(self):
        return self.headers.get("Transfer-Encoding") is not None

    def read_chunked(self, limit):
        """The body of a chunked request, or None when it runs past `limit` bytes (reading stops there).
        ValueError when the chunk framing is broken or the connection ends inside it."""
        body = bytearray()
        while True:
            line = self.rfile.readline(LINE_MAX + 1)
            if not line.endswith(b"\n"):
                raise ValueError("chunk-size line cut off or too long")
            size = line.split(b";", 1)[0].strip()
            if not CHUNK_SIZE.fullmatch(size):
                raise ValueError(f"bad chunk size {size[:20]!r}")
            n = int(size, 16)
            if n == 0:
                break
            if len(body) + n > limit:
                return None
            data = self.rfile.read(n)
            if len(data) != n or self.rfile.readline(3) not in (b"\r\n", b"\n"):
                raise ValueError("chunk data cut off or not ended by CRLF")
            body += data
        for _ in range(100):  # the trailer section: header lines up to an empty one, which are dropped
            line = self.rfile.readline(LINE_MAX + 1)
            if not line.endswith(b"\n"):
                raise ValueError("trailer cut off or too long")
            if line in (b"\r\n", b"\n"):
                return bytes(body)
        raise ValueError("too many trailer lines")

    def discard_body(self):
        """Read and drop a refused request's body when it is small (up to DRAIN bytes): closing a socket with unread
        data resets the connection on most systems, and the client could lose the refusal. A larger body stays
        unread, so it is never taken in. True when the body was read to its end (or there was none)."""
        if self.is_chunked():
            try:
                return self.read_chunked(DRAIN) is not None
            except (OSError, ValueError):
                return False
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return False
        if length == 0:
            return True
        if 0 < length <= DRAIN:
            return len(self.rfile.read(length)) == length
        return False

    def do_POST(self):
        if not self.routed():
            return
        if self.is_chunked():
            try:
                body = self.read_chunked(self.server.max_body)
            except ValueError as e:
                self.send_plain(HTTPStatus.BAD_REQUEST, f"bad request: chunked body: {e}", {"Connection": "close"})
                return
            if body is None:
                self.send_plain(HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                                f"content too large: the chunked body passed the limit of {self.server.max_body} "
                                "bytes (kb_http.py --max-body)", {"Connection": "close"})
                return
            self.reply_to(body)
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if length < 0:
            self.send_json(HTTPStatus.BAD_REQUEST, kb_mcp.error(None, -32600, "Invalid Request: bad Content-Length"))
            return
        self.reply_to(self.rfile.read(length) if length else b"")

    def reply_to(self, body):
        """Parse one request body and send its answer."""
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

    def parse_request(self):
        """The base class's, after noting when the request line was read: log_request measures from here."""
        self._started = time.monotonic()
        return super().parse_request()

    def log_request(self, code="-", size="-"):
        """One structured line per answered request on stderr: the method, the status and the milliseconds since
        its request line was read. The client address, the path and the request line are never logged: a host
        journal then holds no personal data, nor the question a client asked."""
        started = getattr(self, "_started", None)
        ms = 0 if started is None else int((time.monotonic() - started) * 1000)
        method = self.command if self.command in LOGGED_METHODS else "-"
        status = int(code) if str(code).isdigit() else "-"
        if not getattr(self.server, "quiet", False):
            print(f"kb_http: {method} {status} {ms}ms", file=sys.stderr, flush=True)

    def log_message(self, format, *args):  # noqa: A002 - the base class's signature
        """The base class's address-and-text line, dropped: its arguments carry the client address, a request line
        or a client's own words (a malformed request's error text). log_request writes the one line kept."""


def norm_origin(origin):
    """An Origin header or --allow-origin value as they are compared: lower case, no trailing slash."""
    return origin.strip().rstrip("/").lower()


def check_bind(host, bind_any=False):
    """The address to listen on as an ip_address. ValueError when it is not an IP address, or when it is outside
    loopback (127.0.0.0/8, ::1) and bind_any is not set."""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        raise ValueError(f"--bind takes an IP address, not {host!r}") from None
    if not ip.is_loopback and not bind_any:
        raise ValueError(f"--bind {host} is not a loopback address; the server has no authentication, "
                         "so listening there needs --bind-any")
    return ip


class Server(ThreadingHTTPServer):
    daemon_threads = True


class Server6(Server):
    address_family = socket.AF_INET6


def build(port=PORT, quiet=False, host=HOST, bind_any=False, allow_origins=(), max_body=MAX_BODY):
    """The server bound to host:port (0: a free port, in server_address) and not yet serving: tests run
    serve_forever on a thread and call shutdown. ValueError, before anything is bound, for a host that
    check_bind refuses."""
    ip = check_bind(host, bind_any)
    httpd = (Server6 if ip.version == 6 else Server)((str(ip), port), Handler)
    httpd.quiet = quiet
    httpd.allow_origins = frozenset(norm_origin(o) for o in allow_origins)
    httpd.max_body = max_body
    return httpd


def url(httpd):
    """The endpoint's url, as the startup line names it."""
    host, port = httpd.server_address[:2]
    return f"http://{f'[{host}]' if ':' in host else host}:{port}{ENDPOINT}"


def serve(port=PORT, host=HOST, bind_any=False, allow_origins=(), max_body=MAX_BODY):
    """Serve until interrupted. Returns the exit code."""
    try:
        httpd = build(port, host=host, bind_any=bind_any, allow_origins=allow_origins, max_body=max_body)
    except ValueError as e:
        print(f"kb_http: {e}", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"kb_http: cannot listen on {host}:{port}: {e}", file=sys.stderr)
        return 1
    threading.Thread(target=kb_mcp.warm, daemon=True).start()
    if not ipaddress.ip_address(httpd.server_address[0]).is_loopback:
        print("kb_http: warning: listening outside loopback, with no authentication (--bind-any)", file=sys.stderr)
    print(f"kb_http: serving {url(httpd)}, roots {','.join(r.name for r in kbcommon.roots())}", file=sys.stderr,
          flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=PORT, help=f"TCP port (default {PORT}; 0 picks a free one)")
    ap.add_argument("--bind", default=HOST, metavar="ADDR", help=f"IP address to listen on (default {HOST})")
    ap.add_argument("--bind-any", action="store_true", help="allow a --bind address outside loopback")
    ap.add_argument("--allow-origin", action="append", default=[], metavar="ORIGIN",
                    help="a browser origin to serve (scheme://host[:port]); repeatable")
    ap.add_argument("--max-body", type=int, default=MAX_BODY, metavar="BYTES",
                    help=f"largest request body in bytes (default {MAX_BODY})")
    ap.add_argument("--roots", metavar="NAME[,NAME]",
                    help=f"the roots to serve, as the full set (default {','.join(ROOTS)})")
    args = ap.parse_args(argv)
    if not 0 <= args.port <= 65535:
        ap.error("--port must be 0-65535")
    if args.max_body < 1:
        ap.error("--max-body must be at least 1")
    try:
        check_bind(args.bind, args.bind_any)
    except ValueError as e:
        ap.error(str(e))
    try:  # before binding: a wrong name never serves anything
        kbcommon.serve_only(kb_mcp.roots_arg(["--roots", args.roots]) if args.roots is not None else list(ROOTS))
    except (ValueError, kbcommon.RootError) as e:
        print(f"kb_http: {e}", file=sys.stderr)
        return 2
    return serve(args.port, args.bind, args.bind_any, args.allow_origin, args.max_body)


if __name__ == "__main__":
    sys.exit(main())
