#!/usr/bin/env python3
"""A local receiver for Claude Code's OpenTelemetry events, and their join to a transcript (kb/_self/usage.md,
OpenTelemetry events; kb/_self/tools.md). Standard library only.

  kbotel.py serve [--out FILE] [--port N] [--idle SECONDS] [--parent PID]
      listen on 127.0.0.1 only for OTLP/HTTP JSON logs (`POST /v1/logs`, the session run with
      CLAUDE_CODE_ENABLE_TELEMETRY=1, OTEL_LOGS_EXPORTER=otlp, OTEL_EXPORTER_OTLP_LOGS_PROTOCOL=http/json and
      OTEL_EXPORTER_OTLP_LOGS_ENDPOINT=http://127.0.0.1:<port>/v1/logs, OTEL_LOG_TOOL_DETAILS and
      OTEL_LOG_USER_PROMPTS unset) and append one line per `tool_result` or `api_request` event to FILE (default: the
      query log's data directory, outside the repository): the allowlisted ids, model names, counts and flags of
      EVENT_KEYS, never a prompt, a tool's input or output, an error message or any other text. It exits after
      --idle seconds without a request (default 600), or once --parent is gone (POSIX).
  kbotel.py join TRANSCRIPT [--events FILE]
      the events of FILE joined to a main transcript: per prompt id of the transcript, the cost and the requests
      whose request_id the transcript holds, and the tool results whose tool_use_id it holds. Read only; exit 0,
      2 for an unreadable file.

The event names, attributes and the OTLP JSON encoding are in kb/public/claude/otel-monitoring.md."""
import argparse, json, os, re, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = "127.0.0.1"  # never another interface: the events are the operator's own
PORT = 4318  # OTLP/HTTP's default port
IDLE_S = 600
EVENT_KEYS = {  # the attributes kept per event, each in its closed shape; any other attribute is dropped
    "tool_result": {"tool_name": "name", "tool_use_id": "id", "success": "flag", "duration_ms": "number",
                    "prompt.id": "id", "tool_result_size_bytes": "number"},
    "api_request": {"model": "name", "cost_usd": "number", "duration_ms": "number", "input_tokens": "number",
                    "output_tokens": "number", "cache_read_tokens": "number", "cache_creation_tokens": "number",
                    "request_id": "id", "prompt.id": "id"},
}
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}")  # an id or a model name: no space, no slash, no text
NAME = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{0,59}")


def default_out():
    import ql_base
    return ql_base.places()[0] / "otel" / "events.jsonl"


def any_value(v):
    """The plain value of an OTLP `AnyValue` (JSON encoding: int64 as a decimal string), else None."""
    if not isinstance(v, dict):
        return None
    if "stringValue" in v:
        return v["stringValue"]
    if "boolValue" in v:
        return v["boolValue"]
    if "doubleValue" in v:
        return v["doubleValue"]
    if "intValue" in v:
        try:
            return int(v["intValue"])
        except (TypeError, ValueError):
            return None
    return None


def kept(shape, v):
    """`v` in its closed shape, else None."""
    if shape == "flag":
        return v if isinstance(v, bool) else None
    if shape == "number":
        return v if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 else None
    if shape == "id":
        return v if isinstance(v, str) and ID.fullmatch(v) else None
    if shape == "name":
        return v if isinstance(v, str) and NAME.fullmatch(v) else None
    return None


def event_of(record):
    """The kept line of one OTLP log record, or None: its event name (`eventName`, else the `event.name` attribute,
    without the `claude_code.` prefix) when EVENT_KEYS has it, its time in milliseconds and the allowlisted
    attributes."""
    if not isinstance(record, dict):
        return None
    attrs = {a.get("key"): any_value(a.get("value")) for a in record.get("attributes") or []
             if isinstance(a, dict) and isinstance(a.get("key"), str)}
    name = record.get("eventName") or attrs.get("event.name")
    name = name.split(".", 1)[1] if isinstance(name, str) and name.startswith("claude_code.") else name
    keys = EVENT_KEYS.get(name)
    if keys is None:
        return None
    line = {"event": name}
    try:
        line["ms"] = int(record.get("timeUnixNano")) // 1_000_000
    except (TypeError, ValueError):
        pass
    for k, shape in keys.items():
        v = kept(shape, attrs.get(k))
        if v is not None:
            line[k] = v
    return line


def events_of(payload):
    """The kept lines of an `ExportLogsServiceRequest` (resourceLogs, scopeLogs, logRecords)."""
    out = []
    for rl in payload.get("resourceLogs") or [] if isinstance(payload, dict) else []:
        for sl in rl.get("scopeLogs") or [] if isinstance(rl, dict) else []:
            for rec in sl.get("logRecords") or [] if isinstance(sl, dict) else []:
                line = event_of(rec)
                if line:
                    out.append(line)
    return out


class Receiver:
    """The server of `serve`: the lines go to `out`, one write at a time; `last` is the time of the last request."""

    def __init__(self, out, port=PORT):
        self.out, self.lock, self.last = Path(out), threading.Lock(), time.monotonic()
        receiver = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # nothing on stderr: the session's terminal stays clean
                pass

            def answer(self, code, body=b"{}"):
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                receiver.last = time.monotonic()
                if self.path.split("?", 1)[0] != "/v1/logs":
                    return self.answer(404)
                try:
                    payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                except (ValueError, OSError):
                    return self.answer(400)
                receiver.write(events_of(payload))
                self.answer(200)

        self.server = ThreadingHTTPServer((HOST, port), Handler)
        self.port = self.server.server_address[1]

    def write(self, lines):
        if not lines:
            return
        with self.lock:
            self.out.parent.mkdir(parents=True, exist_ok=True)
            with open(self.out, "a", encoding="utf-8", newline="\n") as f:
                f.writelines(json.dumps(ln, sort_keys=True) + "\n" for ln in lines)

    def run(self, idle=IDLE_S, parent=None):
        """Serve until `idle` seconds pass without a request or `parent` (a pid, POSIX) is gone."""
        self.server.timeout = 1
        while time.monotonic() - self.last < idle and alive(parent):
            self.server.handle_request()
        self.server.server_close()


def alive(pid):
    if not pid or os.name != "posix":
        return True
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def transcript_ids(path):
    """({prompt id: [request ids]}, {tool_use ids}) of a main transcript."""
    import kbusage
    prompts, tools, current = {}, set(), None
    for r in kbusage.read_all(path):
        if r.get("isSidechain"):
            continue
        if r.get("type") == "user" and isinstance(r.get("promptId"), str):
            current = r["promptId"]
            prompts.setdefault(current, [])
        msg = r.get("message") if isinstance(r.get("message"), dict) else {}
        if r.get("type") == "assistant":
            if current and isinstance(r.get("requestId"), str) and r["requestId"] not in prompts[current]:
                prompts[current].append(r["requestId"])
            for b in msg.get("content") or [] if isinstance(msg.get("content"), list) else []:
                if isinstance(b, dict) and b.get("type") == "tool_use" and isinstance(b.get("id"), str):
                    tools.add(b["id"])
    return prompts, tools


def join(transcript, events):
    """[(prompt id, cost, requests matched, tool results matched)] for the prompts of the transcript."""
    prompts, tools = transcript_ids(transcript)
    out = []
    for pid, rids in prompts.items():
        reqs = [e for e in events if e.get("event") == "api_request" and e.get("request_id") in rids]
        res = [e for e in events if e.get("event") == "tool_result" and e.get("prompt.id") == pid
               and e.get("tool_use_id") in tools]
        out.append((pid, round(sum(e.get("cost_usd", 0) for e in reqs), 6), len(reqs), len(res)))
    return out


def read_events(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve")
    s.add_argument("--out")
    s.add_argument("--port", type=int, default=PORT)
    s.add_argument("--idle", type=float, default=IDLE_S)
    s.add_argument("--parent", type=int)
    j = sub.add_parser("join")
    j.add_argument("transcript")
    j.add_argument("--events")
    a = ap.parse_args(argv)
    if a.cmd == "serve":
        Receiver(a.out or default_out(), a.port).run(a.idle, a.parent)
        return 0
    try:
        rows = join(a.transcript, read_events(a.events or default_out()))
    except (OSError, ValueError) as e:
        print(f"kbotel join: {type(e).__name__}", file=sys.stderr)
        return 2
    for pid, cost, n_req, n_res in rows:
        print(f"prompt {pid}  cost_usd={cost}  requests={n_req}  tool_results={n_res}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
