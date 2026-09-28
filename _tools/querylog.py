#!/usr/bin/env python3
"""The query log pipeline: capture, distill, learn and apply for kb lookups (stdlib only).

kb/_self/querylog.md is the design, and the Query log items of kb/_self/work-left.md build the commands in order.
Capture and distill are built; learn and apply are not yet: those commands print this text and exit 2.

  querylog.py capture   the capture hook (UserPromptSubmit, PostToolUse, PostToolUseFailure and Stop, async, in
                        .claude/settings.json and the plugin): reads one hook event as JSON on stdin and appends at
                        most one row to the spool; prints nothing and exits 0 whatever happens (a logging hook must
                        never get in the way of a prompt)
  querylog.py launch    the SessionEnd and SessionStart hook: marks the ended session closed, then starts a detached
                        `distill --settle LAUNCH_SETTLE_S` when a closed session waits and no distill holds the lock;
                        prints nothing and exits 0
  querylog.py distill [--replay FILE] [--settle S]
                        the closed sessions of the spool -> one run file in the store (mode `local`: the `store`
                        directory beside the spool, laid out as kb/_querylog/): the rules, then Haiku in capped
                        batches, then the rules and the leak scan again. --replay answers the Haiku calls from a
                        recorded reply file ({"replies": [...]}) instead of `claude -p`. Exit 0 done (or nothing to
                        do), 3 another distill holds the lock
  querylog.py check [DIR]  the store gates over DIR (default kb/_querylog): header and provenance fields, entry fields,
                        identifiers, fetch entries and duplicate ids; one line per problem, exit 1 when there is any
  querylog.py where     prints the mode, the config file, the spool directory and whether capture writes

Tools write their own rows with `record(surface, session_id, **fields)`: kb_hook.py (`kb:` prompts), kb_ask.py (one
row per run), fetch.py and census.py (one row per request, through `record_request`). Every row has a fresh UUID
`id`, the UTC time `ts` and its `surface`; the fields per surface are in kb/_self/querylog.md (Capture).

Where (querylog.md, Spool and Configuration): in a clone `_cache/querylog/spool/<session_id>.jsonl` (rows without a
session: `tools-<yyyy-mm-dd>.jsonl`), the config file `_private/querylog.json` and the marker
`_cache/querylog/DISABLED`; in a plugin host (the hook runs this copy as CLAUDE_PLUGIN_ROOT) the same names under
`${CLAUDE_PLUGIN_DATA}/querylog/`, with `config.json`. No environment variable configures anything.
Nothing is written when the mode is `off` (or the config file cannot be read: fail closed), when the DISABLED marker
exists, or when Claude Code does not run the hooks (`--settings '{"disableAllHooks": true}'`, which every `claude -p`
the pipeline starts carries).
"""
import datetime, functools, json, os, re, subprocess, sys, tempfile, threading, time, uuid
from pathlib import Path
from urllib.parse import urlsplit

TOOLS = Path(__file__).resolve().parent
HOME = TOOLS.parent

# Program defaults (kb/_self/querylog.md, "Program defaults"); the rest arrive with the items that use them.
DEFAULT_MODE = "local"
MODES = ("auto", "local", "off")
SPOOL_MAX_AGE_DAYS = 30
SPOOL_ROW_MAX_CHARS = 4000
HAIKU_MODEL = "haiku"
HAIKU_BATCH_ENTRIES = 25
HAIKU_BATCHES_PER_RUN = 4
HAIKU_DAILY_CALLS = 20
HAIKU_TIMEOUT_S = 180
HAIKU_TEXT_MAX_CHARS = 1500
LAUNCH_BUDGET_S = 0.5
LAUNCH_SETTLE_S = 2
LOCK_STALE_S = 3600
SESSION_IDLE_CLOSED_S = 86400
QUESTION_MAX_CHARS = 500
SUMMARY_MAX_CHARS = 300
PIPELINE_VERSION = 1  # bumped when what distill writes, or how it decides it, changes
STORE = HOME / "kb" / "_querylog"
NO_HOOKS = ["--settings", json.dumps({"disableAllHooks": True})]  # every `claude -p` the pipeline starts carries it

KB_TOOL = re.compile(r"mcp__(?:kb|plugin_it-ops-kb_kb)__(\w+)$")
DOCS_TOOL = re.compile(r"mcp__(?:plugin_it-ops-kb-docs_)?(?:microsoft-learn|claude-code-docs|mcp-docs)__\w+$")
SHELL_TOOLS = ("Bash", "PowerShell")  # on Windows shell commands may reach PowerShell (claude/hooks.md)
FETCHER = re.compile(r"(?:^|[\s;&|(`]|\$\()(?:[^\s;&|()`'\"]*[/\\])?(curl|wget)(?:\.exe)?(?=\s|$)", re.I)
URL = re.compile(r"https?://[^\s'\"<>|;&()`\\]+", re.I)
KB_ARGS = ("question", "questions", "path", "paths", "prefix", "query", "ids", "domain", "root", "tags", "line")
KB_PREFIX = re.compile(r"\s*kb\+?\s*:", re.I)
SKILL = re.compile(r"\s*/(?:it-ops-kb:)?kb-[\w-]+")  # a kb skill typed as a slash command
SAFE_SESSION = re.compile(r"[A-Za-z0-9_-]{1,80}")  # a session id that is safe as a file name
STATUS = re.compile(r"\b(?:HTTP(?:/[\d.]+)?|status(?: code)?)\D{0,3}([1-5]\d\d)\b", re.I)
CUT = " [...]"
ARG_MAX_CHARS = 1000
VERDICTS = ("none", "weak", "good")  # worst first
_lock = threading.Lock()


# ---------------------------------------------------------------- where rows go, and whether they are written

def _same(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def places():
    """(querylog directory, config file): the plugin's data directory when this copy runs as the plugin, else the
    clone's _cache/querylog and _private/querylog.json."""
    data, root = os.environ.get("CLAUDE_PLUGIN_DATA"), os.environ.get("CLAUDE_PLUGIN_ROOT")
    if data and root and _same(root, HOME):
        d = Path(data) / "querylog"
        return d, d / "config.json"
    return HOME / "_cache" / "querylog", HOME / "_private" / "querylog.json"


def read_mode(cfg):
    """The mode the config file sets: DEFAULT_MODE when there is no file, `off` when it cannot be read or names no
    known mode (fail closed: a broken file never turns logging on)."""
    try:
        data = json.loads(Path(cfg).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return DEFAULT_MODE
    except (OSError, ValueError):
        return "off"
    m = data.get("mode", DEFAULT_MODE) if isinstance(data, dict) else None
    return m if m in MODES else "off"


@functools.lru_cache(maxsize=None)
def spool_dir():
    """The spool directory, or None when capture writes nothing (mode off, or the DISABLED marker). Read once per
    process: a hook is one process, and a tool's requests share its answer."""
    d, cfg = places()
    if (d / "DISABLED").exists() or read_mode(cfg) == "off":
        return None
    return d / "spool"


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def fit(row):
    """The row as one JSON line of at most SPOOL_ROW_MAX_CHARS characters: the longest text field is cut first."""
    line = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
    for _ in range(50):
        if len(line) <= SPOOL_ROW_MAX_CHARS:
            return line
        texts = [k for k, v in row.items() if isinstance(v, str) and k not in ("id", "ts", "surface") and len(v) > len(CUT)]
        if not texts:
            break
        k = max(texts, key=lambda k: len(row[k]))
        v = row[k]
        encoded = len(json.dumps(v, ensure_ascii=False))  # escapes (\", \n) make the line longer than the text
        target = encoded - (len(line) - SPOOL_ROW_MAX_CHARS)
        row[k] = v[:max(0, int(len(v) * target / encoded) - len(CUT) - 1)] + CUT
        line = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
    keep = {k: row[k] for k in ("id", "ts", "surface", "session_id", "prompt_id") if k in row}
    return json.dumps(dict(keep, cut=True), ensure_ascii=False, separators=(",", ":"))


def spool_file(spool, session_id, ts):
    if session_id and SAFE_SESSION.fullmatch(session_id):
        return spool / f"{session_id}.jsonl"
    return spool / f"tools-{ts[:10]}.jsonl"


def record(surface, session_id=None, **fields):
    """Append one spool row and return it, or None when capture is off. Never raises: a caller's work never fails
    for its log."""
    try:
        spool = spool_dir()
        if spool is None:
            return None
        row = {"id": str(uuid.uuid4()), "ts": now(), "surface": surface}
        if isinstance(session_id, str) and session_id:
            row["session_id"] = session_id
        row.update((k, v) for k, v in fields.items() if v is not None)
        line = fit(dict(row))
        spool.mkdir(parents=True, exist_ok=True)
        with _lock, open(spool_file(spool, row.get("session_id"), row["ts"]), "a", encoding="utf-8", newline="\n") as f:
            f.write(line + "\n")
        return row
    except Exception:  # noqa: BLE001 - see the docstring
        return None


def host_path(url):
    """(host, path) of an http(s) url, lower-case host without user or port; query and fragment dropped. (None,
    None) for anything else."""
    try:
        u = urlsplit(str(url).strip())
        host = u.hostname
    except ValueError:
        return None, None
    if u.scheme.lower() not in ("http", "https") or not host:
        return None, None
    return host.lower(), (u.path or "/")[:ARG_MAX_CHARS]


def request_outcome(status=None, error=None, body_len=None, url=None, final_url=None, limit=None):
    """The outcome class of one HTTP request made by a tool: facts only (querylog.md, Fetch outcomes)."""
    if error is not None:
        return "error"
    if final_url and url and host_path(final_url)[0] != host_path(url)[0]:
        return "redirect-cross-host"
    if body_len == 0:
        return "empty"
    if limit and body_len is not None and body_len >= limit:
        return "truncated"
    return f"http-{status}" if isinstance(status, int) else "unknown"


def record_request(url, outcome):
    """One row per request made by fetch.py or census.py (the tool is the running script)."""
    host, path = host_path(url)
    if host:
        record("tool_fetch", tool=Path(sys.argv[0]).name or None, host=host, path=path, outcome=outcome)


# ---------------------------------------------------------------- the capture hook

def text_of(x, depth=0):
    """The text of a tool response: a string, a list of content blocks, or an object holding one."""
    if depth > 6:
        return ""
    if isinstance(x, str):
        return x
    if isinstance(x, list):
        return "\n".join(text_of(i, depth + 1) for i in x)
    if isinstance(x, dict):
        for k in ("text", "content", "result", "structuredContent", "output"):
            if k in x:
                return text_of(x[k], depth + 1)
    return ""


def clip(v):
    if isinstance(v, str):
        return v if len(v) <= ARG_MAX_CHARS else v[:ARG_MAX_CHARS - len(CUT)] + CUT
    if isinstance(v, list):
        return [clip(i) for i in v[:6]]
    return v if isinstance(v, (int, float, bool)) or v is None else clip(str(v))


def pack_summary(text):
    """{verdict, verdicts, articles} of a kb tool's result text (the pack's `coverage:` lines and `## path` heads)."""
    verdicts = re.findall(r"^coverage: (good|weak|none)\b", text, re.M)
    articles = list(dict.fromkeys(re.findall(r"^## (\S+/\S+)", text, re.M)))[:20]
    out = {"articles": articles or None}
    if verdicts:
        out["verdict"] = min(verdicts, key=VERDICTS.index)
        if len(verdicts) > 1:
            out["verdicts"] = verdicts
    return out


def intent(prompt):
    """How a prompt uses the kb before any tool runs: `lookup` (kb: or kb+:), `skill` (a /kb-... command), `change`
    (the clone's change router routes it to a change skill), else None."""
    if KB_PREFIX.match(prompt):
        return "lookup"
    if SKILL.match(prompt):
        return "skill"
    router = HOME / ".claude" / "hooks"
    if (router / "kb_change_router.py").is_file():
        try:
            sys.path.insert(0, str(router))
            import kb_change_router
            if kb_change_router.answer(prompt) is not None:
                return "change"
        except Exception:  # noqa: BLE001 - the router is a hint, never a reason to lose the row
            pass
    return None


def rows(path, needle=None):
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if needle is None or needle in line:
                    try:
                        yield json.loads(line)
                    except ValueError:
                        continue
    except OSError:
        return


def used_kb(spool, session_id, prompt_id):
    """Whether this prompt used the kb so far: a `kb:` hook or kb MCP row, a prompt with a kb intent, or a tool row
    (kb_ask.py, fetch.py, census.py) written since the prompt began."""
    if not (prompt_id and isinstance(session_id, str) and SAFE_SESSION.fullmatch(session_id)):
        return False
    began = None
    for r in rows(spool / f"{session_id}.jsonl", prompt_id):
        if r.get("prompt_id") != prompt_id:
            continue
        if r.get("surface") in ("kb_hook", "mcp") or r.get("kb_intent"):
            return True
        if r.get("surface") == "prompt":
            began = r.get("ts")
    if not began:
        return False
    day = datetime.date.fromisoformat(began[:10])
    today = datetime.datetime.now(datetime.timezone.utc).date()
    while day <= today:
        if any(r.get("ts", "") >= began for r in rows(spool / f"tools-{day.isoformat()}.jsonl")):
            return True
        day += datetime.timedelta(days=1)
    return False


def fetch_target(tool, args):
    """(host, path, fetcher) of a web or docs-server fetch, (None, None, None) for a docs-server call without a url,
    or None when the call is not a fetch the log keeps (shell commands only for curl and wget, never their text)."""
    if tool == "WebFetch":
        return (*host_path(args.get("url")), None)
    if DOCS_TOOL.fullmatch(tool):
        return (*host_path(args.get("url")), None) if args.get("url") else (None, None, None)
    if tool in SHELL_TOOLS:
        cmd = args.get("command")
        m = FETCHER.search(cmd) if isinstance(cmd, str) else None
        u = URL.search(cmd, m.end()) if m else None
        if not u:
            return None
        host, path = host_path(u.group(0))
        return (host, path, m.group(1).lower()) if host else None
    return None


def fetch_outcome(tool, ok, event, host):
    """The outcome class of a hook-seen fetch: facts only, else `unknown` (querylog.md, Fetch outcomes)."""
    if not ok:
        m = STATUS.search(str(event.get("error") or ""))
        return f"http-{m.group(1)}" if m else "error"
    resp = event.get("tool_response")
    if tool in SHELL_TOOLS:
        return "unknown"  # an exit code 0 says nothing about the HTTP status, and the output is never read
    code = resp.get("code") if isinstance(resp, dict) else None
    if isinstance(code, int) and 100 <= code <= 599:
        return f"http-{code}"
    text = text_of(resp)
    if not text.strip():
        return "empty"
    if tool == "WebFetch" and re.search(r"redirect", text[:2000], re.I):
        targets = {host_path(u)[0] for u in URL.findall(text[:2000])} - {None, host}
        if targets:
            return "redirect-cross-host"  # WebFetch names a cross-host target instead of following it
    return "unknown"


def prune(spool):
    """Delete spool files and session end markers untouched for SPOOL_MAX_AGE_DAYS (rows never distilled;
    querylog.md, Spool)."""
    cutoff = time.time() - SPOOL_MAX_AGE_DAYS * 86400
    try:
        for p in [*spool.glob("*.jsonl"), *spool.glob("*.end")]:
            if p.stat().st_mtime < cutoff:
                p.unlink()
    except OSError:
        pass


def capture(event):
    """The row one hook event writes, or None."""
    if not isinstance(event, dict):
        return None
    spool = spool_dir()
    if spool is None:
        return None
    name, sid, pid = event.get("hook_event_name"), event.get("session_id"), event.get("prompt_id")
    if name == "UserPromptSubmit":
        prune(spool)
        prompt = str(event.get("prompt") or "")
        return record("prompt", sid, prompt_id=pid, prompt=prompt, kb_intent=intent(prompt))
    if name in ("PostToolUse", "PostToolUseFailure"):
        tool = str(event.get("tool_name") or "")
        args = event.get("tool_input") if isinstance(event.get("tool_input"), dict) else {}
        ok = name == "PostToolUse"
        m = KB_TOOL.fullmatch(tool)
        if m:
            summary = pack_summary(text_of(event.get("tool_response"))) if ok else {"outcome": "error"}
            return record("mcp", sid, prompt_id=pid, tool=m.group(1),
                          args={k: clip(args[k]) for k in KB_ARGS if k in args} or None, **summary)
        target = fetch_target(tool, args)
        if target is None or not used_kb(spool, sid, pid):
            return None  # a fetch counts only in a prompt that also used the kb (querylog.md, Surfaces)
        host, path, fetcher = target
        return record("fetch", sid, prompt_id=pid, tool=tool, fetcher=fetcher, host=host, path=path,
                      outcome=fetch_outcome(tool, ok, event, host))
    if name == "Stop":
        if not used_kb(spool, sid, pid):
            return None
        return record("stop", sid, prompt_id=pid, answer=str(event.get("last_assistant_message") or ""))
    return None


# ---------------------------------------------------------------- distill: closed sessions -> one run file

LOCK_NAME = "distill.lock"
LOG_NAME = "distill.log"
LOG_MAX_BYTES = 1_000_000  # the launcher starts a fresh log above it
CALLS_NAME = "haiku-calls.json"  # {"day", "calls"}: the Haiku calls this machine made today
CONSUMED_NAME = "consumed.json"  # {tools file: [row ids]}: tools rows already distilled into an entry
HEADER_KEYS = ("run", "pipeline", "retrieval", "kb_commit", "counts")
COUNT_KEYS = ("entries", "dropped", "waiting")
ENTRY_KEYS = ("id", "surface", "day", "intent", "tools", "route", "question", "verdict", "articles", "summary",
              "judged", "best", "fetches", "tool", "fetcher", "host", "path", "outcome")
FETCH_KEYS = ("tool", "fetcher", "host", "path", "outcome", "n")
RAW_KEYS = ("prompt", "answer", "session_id", "prompt_id", "transcript_path", "cwd", "user", "hostname", "command",
            "args", "ts")  # spool fields a run file never holds
SURFACES = ("prompt", "kb_hook", "mcp", "kb_ask", "tool_fetch", "fetch", "stop")
KB_SURFACES = ("kb_hook", "mcp", "kb_ask", "tool_fetch")
TEXT_KEYS = ("question", "summary")
JUDGED = ("answered", "partly", "missed")
OUTCOME = re.compile(r"http-[1-5]\d\d|empty|redirect-cross-host|truncated|error|unknown")
RUN_ID = re.compile(r"(\d{4})(\d{2})\d{2}T\d{6}Z-[0-9a-f]{8}")
ENTRY_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
COMMIT = re.compile(r"[0-9a-f]{7,64}")
NAME = re.compile(r"[A-Za-z0-9_.-]{1,80}")  # a tool or fetcher name: never command text
ARTICLE = re.compile(r"[\w-]+(?:/[\w.-]+)+")
HOSTNAME = re.compile(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{0,61}[a-z0-9]")
URL_PATH = re.compile(r"/[^\s?#]{0,%d}" % (ARG_MAX_CHARS - 1))
PRIVATE_TLDS = ("local", "lan", "corp", "internal", "intra", "home", "localdomain", "arpa", "localhost", "test",
                "invalid", "example")
DISTILL_TASK = (
    "Each entry below is one lookup in an IT knowledge base, already stripped of addresses, ids, paths and secrets: "
    "`prompt` is what the person typed, `answer` the reply they got (may be empty), `candidates` the kb articles the "
    "lookup cited. For each entry give: `question`, the question the person asked, as one plain sentence in the "
    "prompt's language; `summary`, one sentence on the outcome (answered from the kb, partly, or not found), without "
    "the answer's content; `judged`: \"answered\", \"partly\" or \"missed\"; `best`: the one candidate that answers the "
    "question, copied exactly, or null (never an article that is not a candidate); `identifying`: true when the entry "
    "would still identify a person or an organisation. In `question` and `summary`, replace every person's name with "
    "jan.kowalski and every organisation's own name (the company, a customer, a team) with CORP; keep product, vendor "
    "and technology names and placeholders (PL-..., corp.example.com, <secret>) as written. Reply with only a JSON "
    'array, one object per entry, in order: [{"i": 0, "question": "...", "summary": "...", "judged": "answered", '
    '"best": null, "identifying": false}, ...].')


def iso(t):
    """Epoch seconds in the spool's time format."""
    return datetime.datetime.fromtimestamp(t, datetime.timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z")


def ts_of(r):
    return r.get("ts") if isinstance(r.get("ts"), str) else ""


def write_text(path, text):
    """Write `text` to `path` atomically (a temporary file beside it, then os.replace)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


def read_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


# --- the per-machine lock: an O_EXCL file, stale by age only (querylog.md, Portability) ---------------------------

def lock_age(path):
    """Seconds since the lock at `path` was taken (its recorded start, else its mtime); None when there is none."""
    try:
        started = Path(path).stat().st_mtime
    except OSError:
        return None
    data = read_json(path, {})
    if isinstance(data, dict) and isinstance(data.get("started_epoch"), (int, float)):
        started = data["started_epoch"]
    return time.time() - started


def acquire(qdir):
    """Take the distill lock of `qdir`: its path, or None when another distill holds it. A lock older than
    LOCK_STALE_S is taken over; the holder's PID is never signalled (os.kill(pid, 0) ends a process on Windows)."""
    path = Path(qdir) / LOCK_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            age = lock_age(path)
            if attempt or (age is not None and age < LOCK_STALE_S):
                return None
            if age is not None:
                stale = path.with_name(f"{LOCK_NAME}.stale-{uuid.uuid4().hex[:8]}")
                try:
                    os.rename(path, stale)  # atomic: of two takers, one wins
                    stale.unlink()
                except OSError:
                    return None
            continue
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"pid": os.getpid(), "started": now(), "started_epoch": time.time()}, f)
        return path
    return None


def release(path):
    try:
        Path(path).unlink()
    except OSError:
        pass


# --- reading the spool ----------------------------------------------------------------------------------------------

def read_spool(spool, t_now):
    """({session id: session}, {tools file name: rows}). A session is closed when its SessionEnd marker exists or it
    has been idle for SESSION_IDLE_CLOSED_S; its `end` bounds the window of its last prompt."""
    sessions, tools = {}, {}
    if not Path(spool).is_dir():
        return sessions, tools
    for p in sorted(Path(spool).glob("*.jsonl")):
        rs = [r for r in rows(p) if isinstance(r, dict) and isinstance(r.get("id"), str)]
        if p.name.startswith("tools-"):
            tools[p.name] = rs
            continue
        marker = p.with_suffix(".end")
        try:
            mtime = p.stat().st_mtime
            ended = marker.stat().st_mtime if marker.exists() else None
        except OSError:
            continue
        closed = ended is not None or t_now - mtime >= SESSION_IDLE_CLOSED_S
        sessions[p.stem] = {"path": p, "marker": marker, "rows": rs, "closed": closed,
                            "end": iso(max(mtime, ended or 0)) if closed else "9999"}
    return sessions, tools


def groups(session):
    """[key, rows, window start, window end] per prompt of a session, in time order: a prompt's window runs from its
    prompt row to its Stop row, else to the next prompt (the last one: to the session's end)."""
    by = {}
    for r in session["rows"]:
        by.setdefault(r.get("prompt_id") if isinstance(r.get("prompt_id"), str) else f"row:{r['id']}", []).append(r)
    out = []
    for key, rs in by.items():
        rs.sort(key=ts_of)
        prompt = next((r for r in rs if r.get("surface") == "prompt"), rs[0])
        out.append([key, rs, ts_of(prompt), None])
    out.sort(key=lambda g: (g[2], g[0]))
    for i, g in enumerate(out):
        stops = [ts_of(r) for r in g[1] if r.get("surface") == "stop"]
        g[3] = max(stops) if stops else (out[i + 1][2] if i + 1 < len(out) else session["end"])
    return out


def assign(sessions, tools, consumed):
    """Tools rows (kb_ask.py, fetch.py, census.py) not yet distilled, by the prompt window that holds their time
    (the latest-starting one when several do): ({(session id, key): [(file, row)]}, {file: [rows in no window]})."""
    windows = [(g[2], g[3], sid, g[0]) for sid, s in sessions.items() for g in s["groups"]]
    attached, left = {}, {}
    for name, rs in tools.items():
        done = consumed.get(name, set())
        for r in rs:
            if r["id"] in done:
                continue
            t = ts_of(r)
            inside = [w for w in windows if w[0] <= t <= w[1]]
            if inside:
                w = max(inside, key=lambda w: (w[0], w[2]))
                attached.setdefault((w[2], w[3]), []).append((name, r))
            else:
                left.setdefault(name, []).append(r)
    return attached, left


# --- entries --------------------------------------------------------------------------------------------------------

def worst(verdicts):
    vs = [v for v in verdicts if v in VERDICTS]
    return min(vs, key=VERDICTS.index) if vs else None


def public_host(host, k=None):
    """Whether a fetch host may be stored: a DNS name (no IP literal) outside the private and example names, which
    the rules leave as it is (a host the public root names)."""
    import redact
    if not isinstance(host, str) or not HOSTNAME.fullmatch(host):
        return False
    if host.rsplit(".", 1)[-1] in PRIVATE_TLDS:
        return False
    return redact.redact(host, k) == host


def fetch_item(r, k):
    """The stored form of a fetch or tool_fetch row: tool, fetcher, outcome class, and host and path only for a
    public host (querylog.md, Store)."""
    import redact
    item = {"tool": r.get("tool") if isinstance(r.get("tool"), str) and NAME.fullmatch(r["tool"]) else None,
            "fetcher": r.get("fetcher") if r.get("fetcher") in ("curl", "wget") else None,
            "host": None, "path": None,
            "outcome": r.get("outcome") if isinstance(r.get("outcome"), str) and OUTCOME.fullmatch(r["outcome"]) else "unknown"}
    host = r.get("host")
    if public_host(host, k):
        item["host"] = host
        path = redact.redact(r["path"], k) if isinstance(r.get("path"), str) else None
        item["path"] = path if path and URL_PATH.fullmatch(path) else None
    return {key: v for key, v in item.items() if v is not None}


def ordered(entry):
    return {key: entry[key] for key in ENTRY_KEYS if entry.get(key) not in (None, [], "")}


def lookup_text(rs):
    """(prompt text, answer text) for Haiku: the prompt as typed, else the question a tool row names."""
    prompt = next((r.get("prompt") for r in rs if r.get("surface") == "prompt" and isinstance(r.get("prompt"), str)), "")
    if not prompt.strip():
        for r in rs:
            q = r.get("question") if r.get("surface") in ("kb_hook", "kb_ask") else None
            args = r.get("args") if r.get("surface") == "mcp" and isinstance(r.get("args"), dict) else {}
            q = q or args.get("question") or args.get("questions") or args.get("query")
            if q:
                prompt = "\n".join(map(str, q)) if isinstance(q, list) else str(q)
                break
    answer = "\n".join(r["answer"] for r in rs if r.get("surface") == "stop" and isinstance(r.get("answer"), str))
    return prompt.strip(), answer.strip()


def entry_of(rs, k):
    """(entry without the Haiku fields, (prompt, answer) for Haiku or None), or None when the rows never used the kb.
    `rs` is one prompt's rows with the tools rows of its window, or a single tools row outside every window."""
    rs = sorted(rs, key=ts_of)
    prompt = next((r for r in rs if r.get("surface") == "prompt"), None)
    intent_ = prompt.get("kb_intent") if prompt and prompt.get("kb_intent") in ("lookup", "skill", "change") else None
    kb = [r for r in rs if r.get("surface") in KB_SURFACES]
    if not kb and not intent_:
        return None
    first = prompt or rs[0]
    alone = prompt is None and len(rs) == 1
    if alone and first.get("surface") == "tool_fetch":
        item = fetch_item(first, k)
        return ordered({"id": first["id"], "surface": "tool_fetch", "day": ts_of(first)[:10], **item}), None
    tools = []
    for r in kb:
        name = r["surface"] if r["surface"] in ("kb_hook", "kb_ask") else r.get("tool")
        if isinstance(name, str) and NAME.fullmatch(name) and name not in tools:
            tools.append(name)
    articles = []
    for r in kb:
        for a in r.get("articles") or []:
            if isinstance(a, str) and ARTICLE.fullmatch(a) and a not in articles:
                articles.append(a)
    fetches = {}
    for r in rs:
        if r.get("surface") in ("fetch", "tool_fetch"):
            item = fetch_item(r, k)
            key = json.dumps(item, sort_keys=True)
            fetches.setdefault(key, dict(item, n=0))["n"] += 1
    route = next((r.get("route") for r in kb if r.get("surface") == "kb_ask" and isinstance(r.get("route"), str)
                  and NAME.fullmatch(r["route"])), None)
    entry = {"id": first["id"], "surface": "prompt" if prompt else first.get("surface"), "day": ts_of(first)[:10],
             "intent": intent_, "tools": tools, "route": route,
             "verdict": worst(r.get("verdict") for r in kb), "articles": articles[:20],
             "fetches": sorted(fetches.values(), key=lambda f: json.dumps(f, sort_keys=True))}
    text, answer = lookup_text(rs)
    return ordered(entry), ((text, answer) if text else None)


# --- Haiku ----------------------------------------------------------------------------------------------------------

def claude_haiku(prompt):
    """One `claude -p` call of the Haiku stage (redact.names_argv: hooks off, no tools, no user plugins or MCP
    servers), in an empty directory so no project instructions load. OSError when it cannot answer."""
    import redact
    with tempfile.TemporaryDirectory() as d:
        try:
            p = subprocess.run(redact.names_argv(HAIKU_MODEL), input=prompt, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=HAIKU_TIMEOUT_S, cwd=d)
        except subprocess.TimeoutExpired as e:
            raise OSError(f"claude -p gave no reply in {HAIKU_TIMEOUT_S} s") from e
    if p.returncode:
        raise OSError(f"claude -p exited {p.returncode}")
    return p.stdout


class Replay:
    """Recorded Haiku replies ({"replies": [text, ...]}), answered in order; OSError once they run out."""

    def __init__(self, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.replies, self.prompts = list(data["replies"]), []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        if not self.replies:
            raise OSError("no recorded reply left")
        return self.replies.pop(0)


def haiku_items(texts, candidates, k):
    """The batch Haiku sees: rule-redacted text only (querylog.md, Redaction)."""
    import redact
    return [{"i": i, "prompt": redact.redact(p, k)[:HAIKU_TEXT_MAX_CHARS], "answer": redact.redact(a, k)[:HAIKU_TEXT_MAX_CHARS],
             "candidates": c} for i, ((p, a), c) in enumerate(zip(texts, candidates))]


def distill_prompt(items):
    return DISTILL_TASK + "\n\n" + json.dumps(items, ensure_ascii=False)


def parse_distill(reply, items):
    """[{question, summary, judged, best, identifying}] of a Haiku reply; ValueError when it is not that JSON. A
    `best` that is not one of the entry's candidates becomes null: Haiku judges only among what code listed."""
    a, b = reply.find("["), reply.rfind("]")
    if a < 0 or b < a:
        raise ValueError("no JSON array in the reply")
    got = json.loads(reply[a:b + 1])
    if not isinstance(got, list) or len(got) != len(items):
        raise ValueError(f"expected {len(items)} entries")
    out = []
    for i, (r, it) in enumerate(zip(got, items)):
        if not isinstance(r, dict) or r.get("i") != i or not all(isinstance(r.get(f), str) for f in TEXT_KEYS) \
                or r.get("judged") not in JUDGED or not isinstance(r.get("identifying"), bool) \
                or not (r.get("best") is None or isinstance(r.get("best"), str)):
            raise ValueError(f"entry {i} is malformed")
        out.append(dict(r, best=r["best"] if r["best"] in it["candidates"] else None))
    return out


def clip_text(s, n):
    return " ".join(s.split())[:n]


def judged(r, k):
    """The Haiku fields of one entry after the rules and the leak scan again, or None to drop it."""
    import redact
    if r["identifying"]:
        return None
    q = redact.finish(clip_text(r["question"], QUESTION_MAX_CHARS), k)
    s = redact.finish(clip_text(r["summary"], SUMMARY_MAX_CHARS), k)
    if not q or s is None:
        return None
    return {"question": q[:QUESTION_MAX_CHARS], "summary": s[:SUMMARY_MAX_CHARS] or None, "judged": r["judged"],
            "best": r["best"]}


# --- provenance -----------------------------------------------------------------------------------------------------

def retrieval_version():
    import kbfacts
    return kbfacts.INDEX_VERSION


def head_commit():
    try:
        p = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HOME, capture_output=True, text=True, encoding="utf-8",
                           timeout=30)
        sha = p.stdout.strip()
        return sha if p.returncode == 0 and COMMIT.fullmatch(sha) else "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


# --- the run --------------------------------------------------------------------------------------------------------

def distill(qdir=None, cfg=None, haiku=None, now_dt=None, run_id=None, kb_commit=None, settle=0.0, out=print):
    """One distill: 0 done (or nothing to do, or logging off), 3 when another distill holds the lock."""
    d, c = places()
    qdir, cfg = Path(qdir or d), Path(cfg or c)
    if (qdir / "DISABLED").exists() or read_mode(cfg) == "off":
        out("distill: logging is off")
        return 0
    lock = acquire(qdir)
    if lock is None:
        out("distill: another distill holds the lock")
        return 3
    try:
        if settle:
            time.sleep(settle)
        return _distill(qdir, haiku or claude_haiku, now_dt or datetime.datetime.now(datetime.timezone.utc), run_id,
                        kb_commit, out)
    finally:
        release(lock)


def _distill(qdir, haiku, now_dt, run_id, kb_commit, out):
    import redact
    k = redact.known()
    t_now, today = now_dt.timestamp(), now_dt.date().isoformat()
    spool = qdir / "spool"
    sessions, tools = read_spool(spool, t_now)
    consumed = {n: set(ids) for n, ids in read_json(qdir / CONSUMED_NAME, {}).items()
                if n in tools and isinstance(ids, list)}
    for s in sessions.values():
        s["groups"] = groups(s)
    attached, left = assign(sessions, tools, consumed)

    todo = []  # {entry, texts, sid, key, tools}: one per kb lookup of a closed session or a finished day
    for sid, s in sessions.items():
        if not s["closed"]:
            continue
        for key, rs, _, _ in s["groups"]:
            extra = attached.get((sid, key), [])
            built = entry_of(rs + [r for _, r in extra], k)
            if built:
                todo.append({"entry": built[0], "texts": built[1], "sid": sid, "key": key, "tools": extra,
                             "ts": ts_of(rs[0])})
            else:
                s.setdefault("skipped", []).append(extra)  # tools rows of a prompt that never used the kb
    for name, rs in left.items():
        if name[6:16] >= today:
            continue  # tools rows outside every window wait for their day to end
        for r in rs:
            built = entry_of([r], k)
            item = {"entry": built[0], "texts": built[1], "sid": None, "key": None, "tools": [(name, r)],
                    "ts": ts_of(r)} if built else None
            if item:
                todo.append(item)
            else:
                consumed.setdefault(name, set()).add(r["id"])
    todo.sort(key=lambda t: (t["ts"], t["entry"]["id"]))

    need = [t for t in todo if t["texts"]]
    written = [t for t in todo if not t["texts"]]
    dropped, waiting = [], []
    calls = read_json(qdir / CALLS_NAME, {})
    used = calls.get("calls", 0) if isinstance(calls, dict) and calls.get("day") == today else 0
    budget = max(0, min(HAIKU_BATCHES_PER_RUN, HAIKU_DAILY_CALLS - used))
    batches = [need[i:i + HAIKU_BATCH_ENTRIES] for i in range(0, len(need), HAIKU_BATCH_ENTRIES)]
    for n, batch in enumerate(batches):
        if n >= budget:
            waiting += batch
            continue
        used += 1
        write_text(qdir / CALLS_NAME, json.dumps({"day": today, "calls": used}) + "\n")
        items = haiku_items([t["texts"] for t in batch], [t["entry"].get("articles", []) for t in batch], k)
        try:
            reply = haiku(distill_prompt(items))
        except (OSError, subprocess.SubprocessError) as e:
            out(f"distill: Haiku call failed ({type(e).__name__}); its entries wait")
            waiting += [t for b in batches[n:] for t in b]
            break
        try:
            results = [judged(r, k) for r in parse_distill(reply, items)]
        except ValueError:
            dropped += batch  # a reply that is not the expected JSON drops its batch
            continue
        for t, res in zip(batch, results):
            if res is None:
                dropped.append(t)
            else:
                t["entry"] = ordered({**t["entry"], **res})
                written.append(t)

    counts = {"entries": len(written), "dropped": len(dropped), "waiting": len(waiting)}
    if written or dropped:
        run_id = run_id or f"{now_dt.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
        header = {"run": run_id, "pipeline": PIPELINE_VERSION, "retrieval": retrieval_version(),
                  "kb_commit": kb_commit or head_commit(), "counts": counts}
        written.sort(key=lambda t: (t["ts"], t["entry"]["id"]))
        path = qdir / "store" / f"{run_id[:4]}-{run_id[4:6]}" / f"{run_id}.jsonl"
        write_text(path, "".join(json.dumps(x, ensure_ascii=False, separators=(",", ":")) + "\n"
                                 for x in [header] + [t["entry"] for t in written]))
        out(f"distill: run={run_id} entries={counts['entries']} dropped={counts['dropped']} "
            f"waiting={counts['waiting']}")
    else:
        out(f"distill: nothing to write (waiting={counts['waiting']})")

    # the spool: rows of written and dropped entries go; rows of waiting entries stay for the next run
    wait_keys = {(t["sid"], t["key"]) for t in waiting if t["sid"]}
    for t in written + dropped:
        for name, r in t["tools"]:
            consumed.setdefault(name, set()).add(r["id"])
    for sid, s in sessions.items():
        if not s["closed"]:
            continue
        for extra in s.get("skipped", []):
            for name, r in extra:
                consumed.setdefault(name, set()).add(r["id"])
        keep = [r for key, rs, _, _ in s["groups"] if (sid, key) in wait_keys for r in rs]
        try:
            if keep:  # the session stays closed, with the same window end: marker first, then the old times
                st = s["path"].stat()
                if not s["marker"].exists():  # closed by idleness: it stays closed although the file is rewritten
                    s["marker"].touch()
                    os.utime(s["marker"], (st.st_atime, st.st_mtime))
                write_text(s["path"], "".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n"
                                              for r in keep))
                os.utime(s["path"], (st.st_atime, st.st_mtime))
            else:
                s["path"].unlink()
                if s["marker"].exists():
                    s["marker"].unlink()
        except OSError:
            pass
    for name, rs in tools.items():
        if name[6:16] < today and all(r["id"] in consumed.get(name, ()) for r in rs):
            try:
                (spool / name).unlink()
                consumed.pop(name, None)
            except OSError:
                pass
    if consumed or (qdir / CONSUMED_NAME).exists():
        write_text(qdir / CONSUMED_NAME, json.dumps({n: sorted(ids) for n, ids in sorted(consumed.items())}) + "\n")
    return 0


# --- the SessionEnd and SessionStart launcher -----------------------------------------------------------------------

def ready(spool, t_now):
    """Whether the spool holds a closed session, or a tools file whose day is over."""
    try:
        files = list(Path(spool).iterdir())
    except OSError:
        return False
    names = {p.name for p in files}
    today = iso(t_now)[:10]
    for p in files:
        n = p.name
        if not n.endswith(".jsonl"):
            continue
        if n.startswith("tools-"):
            if n[6:16] < today:
                return True
        elif f"{n[:-6]}.end" in names:
            return True
        else:
            try:
                if t_now - p.stat().st_mtime >= SESSION_IDLE_CLOSED_S:
                    return True
            except OSError:
                pass
    return False


def detach(argv, log):
    """Start `argv` detached from this process, its output appended to `log`; its PID. POSIX: a new session.
    Windows: DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP, plus CREATE_BREAKAWAY_FROM_JOB when the job the hook runs
    in allows it (a job that forbids breakaway refuses the flag, and the child is started without it)."""
    log = Path(log)
    log.parent.mkdir(parents=True, exist_ok=True)
    try:
        fresh = log.stat().st_size > LOG_MAX_BYTES
    except OSError:
        fresh = False
    with open(log, "w" if fresh else "a", encoding="utf-8", newline="\n") as f:
        kw = dict(stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT, cwd=str(HOME), close_fds=True)
        if os.name == "nt":
            flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            try:
                return subprocess.Popen(argv, creationflags=flags | subprocess.CREATE_BREAKAWAY_FROM_JOB, **kw).pid
            except OSError:
                return subprocess.Popen(argv, creationflags=flags, **kw).pid
        return subprocess.Popen(argv, start_new_session=True, **kw).pid


def launch(event):
    """The PID of the distill a SessionEnd or SessionStart event starts, or None. SessionEnd first marks its session
    closed. Nothing starts when logging is off, nothing is ready, or a distill holds a fresh lock."""
    if not isinstance(event, dict) or event.get("hook_event_name") not in ("SessionEnd", "SessionStart"):
        return None
    qdir, cfg = places()
    if (qdir / "DISABLED").exists() or read_mode(cfg) == "off":
        return None
    spool = qdir / "spool"
    sid = event.get("session_id")
    if event["hook_event_name"] == "SessionEnd" and isinstance(sid, str) and SAFE_SESSION.fullmatch(sid) \
            and (spool / f"{sid}.jsonl").exists():
        (spool / f"{sid}.end").touch()
    if not ready(spool, time.time()):
        return None
    age = lock_age(qdir / LOCK_NAME)
    if age is not None and age < LOCK_STALE_S:
        return None
    return detach([sys.executable, str(Path(__file__).resolve()), "distill", "--settle", str(LAUNCH_SETTLE_S)],
                  qdir / LOG_NAME)


def hook_launch():
    """`launch`: one event on stdin, no output, exit 0."""
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        launch(json.load(sys.stdin))
    except Exception:  # noqa: BLE001 - a session must end whatever happens here
        pass
    return 0


# --- the store gates (querylog.md, Store) ---------------------------------------------------------------------------

def run_files(store):
    """The run files of a store: <yyyy-mm>/<run-id>.jsonl (findings/ has its own layout)."""
    store = Path(store)
    return sorted(p for p in store.glob("*/*.jsonl") if p.parent.name != "findings") if store.is_dir() else []


def load_run(p):
    """[(line number, object)] of a run file; ValueError naming the first line that is not a JSON object."""
    out = []
    with open(p, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            obj = json.loads(line)
            if not isinstance(obj, dict):
                raise ValueError(f"line {n} is not a JSON object")
            out.append((n, obj))
    return out


def duplicate_ids(store):
    """One problem per entry id that appears more than once across the store's run files."""
    seen, out = {}, []
    for p in run_files(store):
        try:
            objs = load_run(p)
        except (OSError, ValueError):
            continue
        rel = p.relative_to(store).as_posix()
        for n, e in objs[1:]:
            i = e.get("id")
            if isinstance(i, str):
                if i in seen:
                    out.append(f"{rel}:{n}: duplicate entry id {i} (also {seen[i]})")
                else:
                    seen[i] = f"{rel}:{n}"
    return out


def fetch_problems(item, where, k):
    out = []
    extra = sorted(set(item) - set(FETCH_KEYS))
    if extra:
        out.append(f"{where}: fetch fields a fetch never keeps: {', '.join(extra)}")
    for key in ("tool", "fetcher"):
        if key in item and not (isinstance(item[key], str) and NAME.fullmatch(item[key])):
            out.append(f"{where}: fetch {key} is not a tool name (command text?)")
    if "host" in item and not public_host(item["host"], k):
        out.append(f"{where}: fetch host is not a public host")
    if "path" in item:
        if not (isinstance(item["path"], str) and URL_PATH.fullmatch(item["path"])):
            out.append(f"{where}: fetch path has a query string, a fragment or spaces")
        if "host" not in item:
            out.append(f"{where}: fetch path without a public host")
    if not (isinstance(item.get("outcome"), str) and OUTCOME.fullmatch(item["outcome"])):
        out.append(f"{where}: fetch outcome is not an outcome class")
    return out


def entry_problems(e, where, k):
    import redact
    out = []
    raw = sorted(set(e) & set(RAW_KEYS))
    if raw:
        out.append(f"{where}: raw spool fields: {', '.join(raw)}")
    prov = sorted(set(e) & set(HEADER_KEYS))
    if prov:
        out.append(f"{where}: run metadata in an entry: {', '.join(prov)}")
    other = sorted(set(e) - set(ENTRY_KEYS) - set(RAW_KEYS) - set(HEADER_KEYS))
    if other:
        out.append(f"{where}: unknown fields: {', '.join(other)}")
    if not (isinstance(e.get("id"), str) and ENTRY_ID.fullmatch(e["id"])):
        out.append(f"{where}: entry id is not a UUID")
    if e.get("surface") not in SURFACES:
        out.append(f"{where}: unknown surface {e.get('surface')!r}")
    for key in TEXT_KEYS:
        v = e.get(key)
        if v is None:
            continue
        if not isinstance(v, str) or redact.scan(v, k) or redact.redact(v, k) != v:
            out.append(f"{where}: an identifier in `{key}`")
    fetches = e.get("fetches", [])
    fetches = list(fetches) if isinstance(fetches, list) else [None]
    if any(key in e for key in FETCH_KEYS):
        fetches.append({key: e[key] for key in FETCH_KEYS if key in e})
    for f in fetches:
        out += fetch_problems(f, where, k) if isinstance(f, dict) else [f"{where}: a fetch is not an object"]
    return out


def store_problems(store=None, k=None):
    """Every store gate over the run files of `store` (default kb/_querylog): a header with the run's provenance, entries
    without it and without raw fields, no identifier in a text field, fetches with a public host and a bare path, and
    no entry id twice."""
    import redact
    store = Path(store or STORE)
    k = k or redact.known()
    out = []
    for p in run_files(store):
        rel = p.relative_to(store).as_posix()
        try:
            objs = load_run(p)
        except (OSError, ValueError) as e:
            out.append(f"{rel}: not a run file ({e})")
            continue
        if not objs:
            out.append(f"{rel}: empty run file")
            continue
        (hn, h), entries = objs[0], objs[1:]
        missing = [key for key in HEADER_KEYS if key not in h]
        if missing:
            out.append(f"{rel}:{hn}: header lacks {', '.join(missing)}")
        m = RUN_ID.fullmatch(str(h.get("run", "")))
        if "run" in h and not (m and h["run"] == p.stem and p.parent.name == f"{m.group(1)}-{m.group(2)}"):
            out.append(f"{rel}:{hn}: run id does not name this file")
        if "pipeline" in h and not isinstance(h["pipeline"], int):
            out.append(f"{rel}:{hn}: pipeline version is not a number")
        if "retrieval" in h and not (isinstance(h["retrieval"], (int, str)) and str(h["retrieval"]).strip()):
            out.append(f"{rel}:{hn}: retrieval version is empty")
        if "kb_commit" in h and not (isinstance(h["kb_commit"], str) and COMMIT.fullmatch(h["kb_commit"])):
            out.append(f"{rel}:{hn}: kb commit is not a commit id")
        counts = h.get("counts")
        if "counts" in h and not (isinstance(counts, dict) and all(isinstance(counts.get(c), int) for c in COUNT_KEYS)):
            out.append(f"{rel}:{hn}: counts lack {', '.join(COUNT_KEYS)}")
        elif isinstance(counts, dict) and counts.get("entries") != len(entries):
            out.append(f"{rel}:{hn}: counts.entries is {counts.get('entries')}, the file has {len(entries)}")
        extra = sorted(set(h) - set(HEADER_KEYS))
        if extra:
            out.append(f"{rel}:{hn}: header fields a header never has: {', '.join(extra)}")
        for n, e in entries:
            out += entry_problems(e, f"{rel}:{n}", k)
    return out + duplicate_ids(store)


def check(argv):
    problems = store_problems(argv[0] if argv else None)
    for p in problems:
        print(p)
    print(f"querylog check: problems={len(problems)}")
    return 1 if problems else 0


def hook():
    """`capture`: one event on stdin, no output, exit 0."""
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        capture(json.load(sys.stdin))
    except Exception:  # noqa: BLE001 - a logging hook never fails
        pass
    return 0


def where():
    d, cfg = places()
    spool = spool_dir()
    print(f"mode={read_mode(cfg)} config={cfg} dir={d} disabled={(d / 'DISABLED').exists()} "
          f"writes={'yes' if spool else 'no'}")
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["capture"]:
        return hook()
    if argv == ["where"]:
        return where()
    if argv == ["launch"]:
        return hook_launch()
    if argv[:1] == ["check"] and len(argv) <= 2:
        return check(argv[1:])
    if argv[:1] == ["distill"]:
        import argparse
        ap = argparse.ArgumentParser(prog="querylog.py distill")
        ap.add_argument("--replay", help="answer the Haiku calls from this recorded reply file")
        ap.add_argument("--settle", type=float, default=0.0, help="seconds to wait after taking the lock")
        a = ap.parse_args(argv[1:])
        return distill(haiku=Replay(a.replay) if a.replay else None, settle=a.settle)
    if argv in (["-h"], ["--help"]):
        print(__doc__.strip())
        return 0
    print(__doc__.strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
