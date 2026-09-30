"""Helpers the query log's tests share: test_ql_capture.py, test_ql_distill.py, test_ql_store.py, test_ql_learn.py,
test_ql_deliver.py, test_ql_research.py, test_ql_report.py, test_querylog_e2e.py and test_sync.py import them. A test
helper, not a stage module: its tests are the stage modules'.

The spool and the fixture store: the paths (`QL`, `FIXTURES`, `LAPS`), the session id and run id the fixtures carry
(`SID`, `RUN_ID`, `S_ENDED`, `S_IDLE`, `S_OPEN`), the clock (`NOW`), builders of hook events (`prompt`, `tool`, `stop`,
`session_start`), planted spool, store, config and plugin directories (`plant_spool`, `golden_store`, `auto_config`,
`plugins_dir`), readers (`spool`, `jsonl`, `store_files`, `load`), the finding id of the fixture store (`E`) and a local
HTTP server (`serve`).

What the learn, apply, research and delivery tests share: the fixture store copied and learned (`learn_store`,
`run_learn`, `findings`, `by_id`, `tree`, the pack stubs `failing` and `passing`, `none_entry`, `plant_entries`), the
planted provider registry and routes table every stage module's autouse fixture `staging_planted` reads
(`plant_staging`, `planted_staging`), the apply store and its questions (`apply_store`, `ALIAS_Q`, `PARAPHRASE_Q`), the
recorded page and candidate facts of research (`PAGE`, `PAGE_URL`, `cand`, `reply`, `GOOD_QUOTE`, `BAD_QUOTE`,
`LEGACY_QUOTE`, `LAPS_GAP_Q`), and what the push tests and test_querylog_e2e.py stub (`run_here`, `signed_out`, `pipeline`,
`PASSED`, `QUOTA`, `PUSH_OPTIONS_HOOK`, `REJECT_HOOK`).
"""
import contextlib, datetime, http.server, io, json, os, re, shutil, threading
from pathlib import Path

import pytest

import ql_base, ql_learn, ql_store
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


LEARN_STORE = FIXTURES / "store"


# a host's level in these tests comes from these rows, so a provider row the clone gains changes no test result
PLANTED_PROVIDERS = (("learn", "learn.microsoft.com/"), ("github-raw", "raw.githubusercontent.com/"), ("generic", "*"))
PLANTED_ROUTES = """| family | find | read | avoid |
|---|---|---|---|
| `learn.microsoft.com` | `microsoft_docs_search` | `microsoft_docs_fetch` of the url you cite | WebFetch |
| pinned files (`raw.githubusercontent.com`) | the repository | the file at a commit | a branch url |
| sites that publish `llms.txt` or `.md` pages (`platform.claude.com`) | `llms.txt` | the page's `.md` form | the HTML page |
| PyPI | `pypi.org/pypi/<name>/json` | the same JSON | the project page |
"""


def plant_registry(path):
    """A provider registry holding PLANTED_PROVIDERS only."""
    import provider
    rows = [",".join([name, match] + [""] * (len(provider.COLS) - 2)) for name, match in PLANTED_PROVIDERS]
    Path(path).write_text("\n".join([",".join(provider.COLS), *rows]) + "\n", encoding="utf-8", newline="\n")


def plant_routes(text):
    """web-sources.md `text` with PLANTED_ROUTES as its routes table; its other sections as they are."""
    head, sep, rest = text.partition("## Routes by family\n")
    nxt = re.search(r"^## ", rest, re.M)
    assert sep and nxt, "web-sources.md has no routes table followed by a section"
    return head + sep + "\n" + PLANTED_ROUTES + "\n" + rest[nxt.start():]


def plant_staging(registry, doc, source_doc):
    """Write the planted registry to `registry` and `source_doc` with the planted routes table to `doc`."""
    text = Path(source_doc).read_text(encoding="utf-8")
    plant_registry(registry)
    Path(doc).write_text(plant_routes(text), encoding="utf-8", newline="\n")


@contextlib.contextmanager
def planted_staging(d):
    """provider.py and ql_learn.py read a registry and a routes table planted under `d` (from the routes source they
    read on entry), whatever the clone's _tools/providers.csv and web-sources.md serve."""
    import provider
    d = Path(d)
    d.mkdir(parents=True, exist_ok=True)
    plant_staging(d / "providers.csv", d / "web-sources.md", ql_learn.WEB_SOURCES)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(provider, "SHARED", str(d / "providers.csv"))
        mp.setattr(ql_learn, "WEB_SOURCES", d / "web-sources.md")
        yield d


@pytest.fixture(scope="module", autouse=True)
def staging_planted(tmp_path_factory):
    """Every test of this module, its module fixtures included, reads the planted registry and routes table."""
    with planted_staging(tmp_path_factory.mktemp("staging")) as d:
        yield d


def learn_store(tmp_path, name="store"):
    """A copy of the fixture store: one run file with judged misses, an answered lookup and fetch.py requests."""
    dst = Path(tmp_path) / name
    shutil.copytree(LEARN_STORE, dst)
    return dst


def run_learn(store, pack, **kw):
    said = []
    rc = ql_learn.learn(store, pack=pack, kb_commit="0" * 40, out=said.append, **kw)
    return rc, said


def findings(store):
    """[(file, [records])] of the store's findings files, oldest first."""
    return [(p, jsonl(p)[1:]) for p in ql_store.findings_files(store)]


def by_id(store):
    return {r["id"]: r for _, recs in findings(store) for r in recs}


def tree(store):
    return {p.relative_to(store).as_posix(): p.read_bytes() for p in sorted(Path(store).rglob("*")) if p.is_file()}


def failing(q):
    return {"verdict": "none", "paths": [], "missing": []}


def passing(q):
    return {"verdict": "good", "paths": [LAPS, "public/intune/win32-apps.md"], "missing": []}


FN = "55555555-0000-4000-8000-0000000000{}"


def none_entry(n, question, *fetches, **extra):
    """A stored lookup with verdict none whose session fetched `fetches` (host, path, outcome)."""
    return {"id": FN.format(n), "surface": "prompt", "day": "2026-09-27", "tools": ["kb_pack"], "question": question,
            "verdict": "none", "articles": [], "judged": "missed",
            "fetches": [{"tool": "WebFetch", "host": h, "path": p, "outcome": o, "n": 1} for h, p, o in fetches],
            **extra}


def plant_entries(store, *entries):
    """Append `entries` to the store's run file and count them in its header."""
    run = ql_store.run_files(store)[0]
    lines = run.read_text(encoding="utf-8").splitlines()
    header = json.loads(lines[0])
    header["counts"]["entries"] += len(entries)
    lines = [json.dumps(header, separators=(",", ":"))] + lines[1:] + [json.dumps(e) for e in entries]
    run.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


ALIAS_Q = "Which zqxlapsor setting picks the backup directory?"  # a word the kb never holds, for LAPS
PARAPHRASE_Q = "How long is the default password?"  # every word known; the pack on HEAD misses the LAPS article


def apply_store(tmp_path, name="store"):
    """The fixture store with a1 a paraphrase an expansion fixes and a2 an unknown word an alias fixes; a3 (its best
    article cannot be reached without breaking the eval set), a4 (a gap) and the fetches as they are."""
    store = learn_store(tmp_path, name)
    (p,) = ql_store.run_files(store)
    objs = jsonl(p)
    for o in objs:
        o["question"] = {E("a1"): PARAPHRASE_Q, E("a2"): ALIAS_Q}.get(o.get("id"), o.get("question"))
        if o.get("question") is None:
            o.pop("question")
    p.write_text("".join(json.dumps(o, separators=(",", ":")) + "\n" for o in objs), encoding="utf-8", newline="\n")
    return store


QUOTA = {"status": "failed", "failure_reason": "ci_quota_exceeded", "allow_failure": True}
PASSED = [{"name": "kb-trailers", "status": "success"}, {"name": "kb-tests", "status": "success"}]


def signed_out(argv):
    return 1, "", "not logged in"


def run_here(argv, cwd=None, env=None):
    """ql_base.run_cmd, but a worktree's `querylog.py check DIR` runs in this process: the same store gates
    (ql_store.check on that directory), with the public root's known ids read once per process instead of once per
    push. The command line of `check` is tested on its own (TestStore, TestSpoolFormats)."""
    if len(argv) == 4 and Path(argv[1]).name == "querylog.py" and argv[2] == "check":
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = ql_store.check(argv[3])
        return code, out.getvalue(), ""
    return ql_base.run_cmd(argv, cwd=cwd, env=env)


def pipeline(status, jobs=()):
    """A signed-in glab that answers one pipeline of `status` for any commit, and `jobs` as its job list."""
    def ci(argv):
        if argv[1:3] == ["auth", "status"]:
            return 0, "", "Logged in"
        if "/jobs?" in argv[-1]:
            return 0, json.dumps(list(jobs)), ""
        return 0, json.dumps([{"id": 1, "status": status}]), ""
    return ci


PUSH_OPTIONS_HOOK = """#!/bin/sh
i=0
while [ "$i" -lt "${GIT_PUSH_OPTION_COUNT:-0}" ]; do
  eval "printf '%s\\n' \\"\\$GIT_PUSH_OPTION_$i\\"" >> push-options.txt
  i=$((i+1))
done
"""


REJECT_HOOK = "#!/bin/sh\necho 'planted: push refused' >&2\nexit 1\n"


PAGE = FIXTURES / "pages" / "laps-platforms.html"
PAGE_URL = "https://docs.example.com/laps/platforms"
GOOD_QUOTE = "it doesn't support Windows Server 2012 R2"  # the page writes doesn&#8217;t and 2012&nbsp;R2
BAD_QUOTE = "Windows LAPS supports Windows Server 2012 R2 with the April 2023 update"
LEGACY_QUOTE = "The legacy Microsoft LAPS product remains available for older operating systems"  # a link and <em>


def cand(**kw):
    c = {"text": "Windows LAPS does not back up passwords from Windows Server 2012 R2 devices.", "tag": "DOC",
         "url": PAGE_URL, "title": "Windows LAPS platform support", "publisher": "Example Docs",
         "licence": "CC BY 4.0, stated on the page (test page)", "reuse": "copy", "quote": GOOD_QUOTE,
         "conflicts_with": None}
    c.update(kw)
    return c


def reply(*cands):
    return "Here is what I found.\n" + json.dumps({"facts": list(cands)})


LAPS_GAP_Q ="Can Windows LAPS back up the password of a Windows Server 2016 member server to Azure?"
