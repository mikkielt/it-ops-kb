"""Helpers the query log's tests share: test_ql_capture.py, test_ql_distill.py, test_ql_store.py, test_querylog.py and
test_querylog_e2e.py (through test_querylog) import them. A test helper, not a stage module: it holds no query-log code.

The spool and the fixture store: the paths (`QL`, `FIXTURES`, `LAPS`), the session id and run id the fixtures carry
(`SID`, `RUN_ID`, `S_ENDED`, `S_IDLE`, `S_OPEN`), the clock (`NOW`), builders of hook events (`prompt`, `tool`, `stop`,
`session_start`), planted spool, store, config and plugin directories (`plant_spool`, `golden_store`, `auto_config`,
`plugins_dir`), readers (`spool`, `jsonl`, `store_files`, `load`), the finding id of the fixture store (`E`) and a local
HTTP server (`serve`).
"""
import contextlib, datetime, http.server, json, os, shutil, threading
from pathlib import Path

from conftest import KB, TOOLS

SID = "3f2a4c1e-0000-4000-8000-00000000abcd"
QL = os.path.join(TOOLS, "querylog.py")
SH = shutil.which("sh")


FIXTURES = Path(TOOLS) / "fixtures" / "querylog"
NOW = datetime.datetime(2026, 9, 28, 12, 0, tzinfo=datetime.timezone.utc)
RUN_ID = "20260928T120000Z-0000abcd"
S_ENDED, S_IDLE, S_OPEN = (f"aaaaaaaa-0000-4000-8000-00000000000{i}" for i in (1, 2, 3))


def spool(data):
    return Path(data) / "querylog" / "spool"


def prompt(text, pid="p1", sid=SID):
    return {"hook_event_name": "UserPromptSubmit", "session_id": sid, "prompt_id": pid, "prompt": text}


def tool(name, args, response=None, pid="p1", ok=True, error=None, sid=SID):
    ev = {"hook_event_name": "PostToolUse" if ok else "PostToolUseFailure", "session_id": sid, "prompt_id": pid,
          "tool_name": name, "tool_input": args, "tool_use_id": "toolu_01"}
    if ok:
        ev["tool_response"] = response
    else:
        ev["error"] = error or ""
    return ev


def stop(answer, pid="p1", sid=SID):
    return {"hook_event_name": "Stop", "session_id": sid, "prompt_id": pid, "stop_hook_active": False,
            "last_assistant_message": answer}


@contextlib.contextmanager
def serve():
    """A local HTTP server for fetch.py and census.py requests: /ok (200, `hello`), /empty (200, no body), /missing
    (404), anything else 500. Yields its base url."""
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            code, body = {"/ok": (200, b"hello"), "/empty": (200, b""), "/missing": (404, b"no")}.get(
                self.path.split("?")[0], (500, b"x"))
            self.send_response(code)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}"
    finally:
        srv.shutdown()


def load(rel):
    with open(os.path.join(KB, rel), encoding="utf-8") as f:
        return json.load(f)


def c(s):
    """The fixtures break every identifier with `~`, so the leak scan of tracked files passes over them."""
    return s.replace("~", "")


def plant_spool(qdir, now=NOW):
    """The fixture spool under qdir/spool: S_ENDED ended (SessionEnd marker), S_IDLE idle for two days, S_OPEN
    active a minute ago; the tools file of the day before."""
    sp = Path(qdir) / "spool"
    sp.mkdir(parents=True, exist_ok=True)
    for f in (FIXTURES / "spool").iterdir():
        (sp / f.name).write_text(c(f.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    t = now.timestamp()
    for sid, age in ((S_ENDED, 3600), (S_IDLE, 2 * 86400), (S_OPEN, 60)):
        os.utime(sp / f"{sid}.jsonl", (t - age, t - age))
    (sp / f"{S_ENDED}.end").touch()
    return sp


def store_files(qdir):
    return sorted((Path(qdir) / "store").rglob("*.jsonl"))


def jsonl(path):
    return [json.loads(ln) for ln in Path(path).read_text(encoding="utf-8").splitlines() if ln.strip()]


LAPS = "public/windows/laps.md"


def session_start(sid="new-session"):
    return {"hook_event_name": "SessionStart", "session_id": sid, "source": "startup"}


def golden_store(store, lines_=None, name=RUN_ID):
    """The store `store` with the golden run file (or `lines_`, JSON objects) as <yyyy-mm>/<run-id>.jsonl."""
    objs = lines_ if lines_ is not None else jsonl(FIXTURES / "golden.jsonl")
    p = Path(store) / f"{name[:4]}-{name[4:6]}" / f"{name}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(o, ensure_ascii=False) + "\n" for o in objs), encoding="utf-8", newline="\n")
    return Path(store)


E = lambda n: f"55555555-0000-4000-8000-0000000000{n}"  # noqa: E731


def auto_config(qdir, mode="auto"):
    cfg = Path(qdir) / "config.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"mode": mode}), encoding="utf-8", newline="\n")
    return cfg


def plugins_dir(tmp, source):
    """A fake ~/.claude/plugins with one marketplace `mkt` whose known_marketplaces.json entry has `source`; the
    plugin copy's root (cache/mkt/it-ops-kb/<version>)."""
    plugins = Path(tmp) / "plugins"
    root = plugins / "cache" / "mkt" / "it-ops-kb" / "0123abcd4567"
    root.mkdir(parents=True, exist_ok=True)
    entry = {"source": source, "installLocation": str(plugins / "marketplaces" / "mkt"), "lastUpdated": "x"}
    (plugins / "known_marketplaces.json").write_text(json.dumps({"mkt": entry}), encoding="utf-8", newline="\n")
    return root
