"""kbotel.py: the local OTLP/HTTP JSON receiver of Claude Code's events and their join to a transcript (ST-zqnngn67;
kb/_self/usage.md, OpenTelemetry events). Each test runs the receiver in a thread on a free port of 127.0.0.1 and
posts what Claude Code's exporter posts (kb/public/claude/otel-monitoring.md: resourceLogs, scopeLogs, logRecords,
lowerCamelCase keys, int64 as decimal strings); none reaches the network.
"""
import json, os, subprocess, sys, threading, urllib.request

import pytest

import kbotel

FREE = "FREE-TEXT /home/jan.kowalski/secret.md"


def attrs(**kv):
    out = []
    for k, v in kv.items():
        k = k.replace("__", ".")
        if isinstance(v, bool):
            out.append({"key": k, "value": {"boolValue": v}})
        elif isinstance(v, int):
            out.append({"key": k, "value": {"intValue": str(v)}})
        elif isinstance(v, float):
            out.append({"key": k, "value": {"doubleValue": v}})
        else:
            out.append({"key": k, "value": {"stringValue": v}})
    return out


def payload(*records):
    return {"resourceLogs": [{"resource": {"attributes": attrs(service__name="claude-code")},
                              "scopeLogs": [{"scope": {"name": "com.anthropic.claude_code"},
                                             "logRecords": list(records)}]}]}


def record(name, by_attribute=False, body=None, **kv):
    rec = {"timeUnixNano": "1790000000123000000", "attributes": attrs(**kv)}
    if by_attribute:
        rec["attributes"] += attrs(event__name=name)
    else:
        rec["eventName"] = name
    if body is not None:
        rec["body"] = {"stringValue": body}
    return rec


def serve(tmp_path):
    out = tmp_path / "otel" / "events.jsonl"
    rx = kbotel.Receiver(out, port=0)
    t = threading.Thread(target=rx.run, kwargs={"idle": 30}, daemon=True)
    t.start()
    return rx, out


def post(rx, body, path="/v1/logs"):
    req = urllib.request.Request(f"http://127.0.0.1:{rx.port}{path}", data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""


def lines(out):
    return [json.loads(ln) for ln in out.read_text(encoding="utf-8").splitlines()] if out.exists() else []


def test_otel_receiver_writes_local_file(tmp_path):
    """A tool_result and an api_request event posted to 127.0.0.1/v1/logs become one line each in the local file,
    with their ids, model and counts; the answer is 200 with an empty JSON object; another path is 404 and writes
    nothing; the receiver listens on 127.0.0.1 only."""
    rx, out = serve(tmp_path)
    assert rx.server.server_address[0] == "127.0.0.1"
    code, body = post(rx, payload(
        record("claude_code.tool_result", tool_name="Bash", tool_use_id="toolu_01", success=True, duration_ms=42,
               prompt__id="p-1"),
        record("api_request", by_attribute=True, model="claude-opus-5-5", cost_usd=0.25, duration_ms=900,
               input_tokens=10, output_tokens=20, request_id="req_01", prompt__id="p-1")))
    assert (code, body) == (200, b"{}")
    assert lines(out) == [
        {"event": "tool_result", "ms": 1790000000123, "tool_name": "Bash", "tool_use_id": "toolu_01",
         "success": True, "duration_ms": 42, "prompt.id": "p-1"},
        {"event": "api_request", "ms": 1790000000123, "model": "claude-opus-5-5", "cost_usd": 0.25,
         "duration_ms": 900, "input_tokens": 10, "output_tokens": 20, "request_id": "req_01", "prompt.id": "p-1"}]
    assert post(rx, payload(record("tool_result", tool_use_id="toolu_02")), "/v1/traces")[0] == 404
    assert len(lines(out)) == 2


def test_otel_events_no_text_stored(tmp_path):
    """Free text in every place an event can carry it (a prompt, a tool's input and output, an error, a body, a
    resource attribute, an id-shaped field with a space or a path) never reaches the file; an event outside
    EVENT_KEYS (user_prompt) writes no line; a broken body is 400 and writes nothing."""
    rx, out = serve(tmp_path)
    post(rx, payload(
        record("user_prompt", prompt=FREE, prompt_length=40),
        record("tool_result", body=FREE, tool_name=FREE, tool_use_id=FREE, tool_parameters=FREE, tool_input=FREE,
               error=FREE, success=False, prompt__id="p 1"),
        record("api_request", model="/home/jan.kowalski", request_id="req_01", error=FREE, cost_usd=-1)))
    text = out.read_text(encoding="utf-8")
    for leak in ("FREE-TEXT", "jan.kowalski", "secret.md", "p 1"):
        assert leak not in text, leak
    assert lines(out) == [{"event": "tool_result", "ms": 1790000000123, "success": False},
                          {"event": "api_request", "ms": 1790000000123, "request_id": "req_01"}]
    req = urllib.request.Request(f"http://127.0.0.1:{rx.port}/v1/logs", data=b"not json", method="POST")
    try:
        urllib.request.urlopen(req, timeout=10)
        code = 200
    except urllib.error.HTTPError as e:
        code = e.code
    assert code == 400 and len(lines(out)) == 2


def test_otel_events_join_transcript(tmp_path, capsys):
    """join matches the events to a transcript: per prompt id the cost of the requests whose request_id the
    transcript holds and the tool results whose tool_use_id it holds; an event of another session counts nowhere."""
    transcript = tmp_path / "session.jsonl"
    recs = [{"type": "user", "promptId": "p-1", "message": {"content": "q"}},
            {"type": "assistant", "requestId": "req_01", "message": {"model": "claude-opus-5-5", "usage": {},
                                                                     "content": [{"type": "tool_use", "id": "toolu_01"}]}},
            {"type": "user", "promptId": "p-2", "message": {"content": "q2"}},
            {"type": "assistant", "requestId": "req_02", "message": {"model": "claude-opus-5-5", "usage": {},
                                                                     "content": [{"type": "text", "text": "a"}]}}]
    transcript.write_text("".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8")
    events = tmp_path / "events.jsonl"
    evs = [{"event": "api_request", "request_id": "req_01", "cost_usd": 0.5, "prompt.id": "p-1"},
           {"event": "api_request", "request_id": "req_02", "cost_usd": 0.25, "prompt.id": "p-2"},
           {"event": "api_request", "request_id": "req_99", "cost_usd": 9.0, "prompt.id": "p-9"},  # another session
           {"event": "tool_result", "tool_use_id": "toolu_01", "prompt.id": "p-1", "success": True}]
    events.write_text("".join(json.dumps(e) + "\n" for e in evs), encoding="utf-8")
    assert kbotel.join(transcript, kbotel.read_events(events)) == [("p-1", 0.5, 1, 1), ("p-2", 0.25, 1, 0)]
    assert kbotel.main(["join", str(transcript), "--events", str(events)]) == 0
    assert capsys.readouterr().out.splitlines() == ["prompt p-1  cost_usd=0.5  requests=1  tool_results=1",
                                                    "prompt p-2  cost_usd=0.25  requests=1  tool_results=0"]
    assert kbotel.main(["join", str(transcript), "--events", str(tmp_path / "none.jsonl")]) == 2


def run_until_return(rx, **kw):
    """Run the receiver on a thread; True when `run` returned within 15 seconds."""
    t = threading.Thread(target=rx.run, kwargs=kw, daemon=True)
    t.start()
    t.join(15)
    return not t.is_alive()


def test_otel_receiver_exits_on_idle(tmp_path):
    """ST-xc7bughc planted: with no request for `idle` seconds the receiver's run returns and closes its socket."""
    rx = kbotel.Receiver(tmp_path / "e.jsonl", 0)
    assert run_until_return(rx, idle=0.2)
    assert rx.server.socket.fileno() == -1


@pytest.mark.skipif(os.name != "posix", reason="a gone parent is read with os.kill(pid, 0), POSIX only")
def test_otel_receiver_exits_when_its_parent_is_gone(tmp_path):
    """ST-xc7bughc planted: a parent pid that has exited ends the run at once, whatever the idle bound."""
    gone = subprocess.Popen([sys.executable, "-c", "pass"])
    gone.wait()
    rx = kbotel.Receiver(tmp_path / "e.jsonl", 0)
    assert run_until_return(rx, idle=3600, parent=gone.pid)
    assert not kbotel.alive(gone.pid) and kbotel.alive(os.getpid())
