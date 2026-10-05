"""The query log's capture (kb/_self/querylog.md, Surfaces and Capture): the hook that turns one Claude Code event
into at most one spool row, and `record` for the tools that write their own rows (kb_hook.py, kb_ask.py, fetch.py,
census.py). Standard library only, and cheap to import: the kb: hook and every capture hook load it.

Every row has a fresh UUID `id`, the UTC time `ts`, its `surface` and the row format `v` (ROW_FORMAT); a hook row also
has `session_id` and `prompt_id`. Nothing is written when logging is off (ql_base.logging_off).

An `ops` row (OPS_EVENTS) is what a tool of the kb's own work did and took: an `event` from a closed set and the keys
that event has, each a name, an exit code, a count, milliseconds, an item id, a short sha, a test file name or a
closed reason class, never free text. `record` writes none that breaks that shape (ops_problems), and the store
gates the written lines by the same function.
"""
import datetime, functools, hashlib, json, re, secrets, sys, threading, time, uuid
from pathlib import Path
from urllib.parse import urlsplit

from ql_base import DISABLED_NAME, HOME, json_lines, logging_off, now, places, read_mode

SPOOL_MAX_AGE_DAYS = 30
SPOOL_ROW_MAX_CHARS = 4000
LINES_MAX = 12  # kb lines a spool row keeps of one kb tool's result
ROW_FORMAT = 1  # the `v` of the spool rows capture writes; a row without `v` is format 0 (querylog.md, Spool)
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
WORK_ACTIONS = ("claim", "done", "release")  # the backlog.py commands that open or end a window of work on an item
AGENT_ACTIONS = ("agent-start", "agent-stop")  # the `work` rows of a subagent's start and stop (agent_row)
AGENT_SALT_NAME = "agent.salt"  # beside the spool, never committed: what a hash of an agent id is salted with
AGENT_HASH_CHARS = 12
WORK_BRANCH_REF = "ref: refs/heads/work/"
WORK_REFUSED_EXIT = 1  # the exit code of a refused backlog.py command (its Refused; bad usage exits 2)
WORK_ITEM = re.compile(r"(?:EP|ST|TK|SB|BG|SP)-[a-z2-7]{8}")  # backlog.py's ID_RE
WORK_LAUNCHER = re.compile(r"(?:sh|bash|python[\d.]*|py)(?:\.exe)?|kbpy|-[\w.-]+|[A-Za-z_]\w*=\S*", re.I)  # beside backlog.py
WORK_VALUE_FLAGS = ("--by", "--trailer", "--root", "--branch", "--why")  # backlog.py options that take a value
SHELL_TOKEN = re.compile(r"\"[^\"]*\"|'[^']*'|[^\s\"']+")
CUT = " [...]"
ARG_MAX_CHARS = 1000
VERDICTS = ("none", "weak", "good")  # worst first
TAGS = ("DOC", "CODE", "DER", "COMMUNITY", "UNK", "DECISION")
KB_LINE = re.compile(r"^\s*(- |\[[\d.]+\] )([\w-]+(?:/[\w.-]+)+:[1-9]\d*)(?![\w:])(.*)$")  # a pack line, a search hit
LINE_TAG = re.compile(r"\[(DOC|CODE|DER|COMMUNITY|UNK|DECISION)\b[^\]]*\]\s*$")
COVERAGE = re.compile(r"^coverage: (good|weak|none)\b", re.M)
_lock = threading.Lock()

# ---------------------------------------------------------------- operational rows (the `ops` surface)

OPS = "ops"
OPS_ROW_MAX_CHARS = 32000  # an ops row is never cut (a cut row is no event): one longer than this is not written
OPS_MS_MAX = 10 ** 11  # about three years of milliseconds
OPS_COUNT_MAX = 10 ** 7
OPS_LIST_MAX = 300  # items of a list or rows of a table in one ops row
OPS_TOKEN = re.compile(r"[a-z][a-z0-9_.-]{0,39}")  # a step, lane, check, state or detector name: never a sentence
OPS_SHA = re.compile(r"[0-9a-f]{7,12}")
OPS_AGENT = re.compile(r"[0-9a-f]{8,16}")  # a salted short hash of an agent id, never the id
OPS_TEST_FILE = re.compile(r"(?:test_[a-z0-9_]{1,60}|conftest)\.py")  # a test file's name, never a node id or a path
OPS_REFUSED = ("children-open", "not-ready", "status", "provisional-answer", "uncommitted", "no-work-commit",
               "unlanded-code", "outside-touches", "check-failed", "no-op-proof")  # why a `done` was refused
OPS_TEST_MODES = ("full", "changed", "fast", "files", "keyword", "stress")


def _number(v, high, low=0):
    return type(v) is int and low <= v <= high


OPS_KINDS = {  # the value shapes an ops key may have
    "item": lambda v: isinstance(v, str) and WORK_ITEM.fullmatch(v) is not None,
    "sprint": lambda v: isinstance(v, str) and WORK_ITEM.fullmatch(v) is not None and v.startswith("SP-"),
    "token": lambda v: isinstance(v, str) and OPS_TOKEN.fullmatch(v) is not None,
    "sha": lambda v: isinstance(v, str) and OPS_SHA.fullmatch(v) is not None,
    "agent": lambda v: isinstance(v, str) and OPS_AGENT.fullmatch(v) is not None,
    "test_file": lambda v: isinstance(v, str) and OPS_TEST_FILE.fullmatch(v) is not None,
    "reason": lambda v: v in OPS_REFUSED,
    "mode": lambda v: v in OPS_TEST_MODES,
    "ms": lambda v: _number(v, OPS_MS_MAX),
    "count": lambda v: _number(v, OPS_COUNT_MAX),
    "exit": lambda v: _number(v, 2 ** 32, -2 ** 31),  # a Windows status code is above 255
    "flag": lambda v: isinstance(v, bool),
}


def _spec(required, optional=None):
    """{key: (shape, required)} of one event: a shape is a name of OPS_KINDS, ("list", most, name) or ("rows", most,
    {key: name}), a list of objects each of those keys alone."""
    return {**{k: (v, True) for k, v in required.items()},
            **{k: (v, False) for k, v in (optional or {}).items()}}


_CHECK_ROW = ("rows", 40, {"name": "token", "ran": "flag", "why": "token", "exit": "exit", "ms": "ms"})
_FILE_MS = {"file": "test_file", "ms": "ms"}
OPS_EVENTS = {  # the closed set of events, each with its closed keys
    "land.step": _spec({"item": "item", "step": "token", "exit": "exit", "ms": "ms"}),
    "land.end": _spec({"item": "item", "exit": "exit", "ms": "ms"}, {"lane": "token"}),
    "sync.gate": _spec({"ms": "ms"}, {"checks": _CHECK_ROW, "scope": "token", "files": "count", "push": "token",
                                       "exit": "exit"}),
    "done.refused": _spec({"item": "item", "reasons": ("list", len(OPS_REFUSED), "reason"), "ms": "ms"},
                          {"checks": ("list", 20, "token")}),
    "sprint.close": _spec({"sprint": "sprint", "landed": "count", "dropped": "count", "bugs": "count",
                           "confirmed": "count", "refused": "count", "ms": "ms"}),
    "ci.pipeline": _spec({"state": "token", "calls": "count"}, {"sha": "sha"}),
    "intake.detect": _spec({"detector": "token"}, {"found": "count", "budget": "flag", "coverage": "count"}),
    "test.run": _spec({"mode": "mode", "ms": "ms", "exit": "exit"},
                      {"selected": "count", "total": "count", "workers": "count", "passed": "count",
                       "failed": "count", "skipped": "count", "slow": ("rows", 20, _FILE_MS),
                       "files": ("rows", OPS_LIST_MAX, _FILE_MS),
                       "failed_files": ("list", OPS_LIST_MAX, "test_file")}),
    "agent.run": _spec({"group": "token", "ms": "ms"}, {"agent": "agent", "item": "item"}),
    "stall.remedy": _spec({"item": "item", "signal": "token", "remedy": "token", "count": "count"}),
    "call.tool": _spec({"tool": "token", "group": "token", "outcome": "token", "size": "token"},
                       {"class": "token", "purpose": "token", "ms": "ms"}),
}
OPS_EVENTS.update({  # the hook events of permission, compaction and API-error turn ends (ST-mkczg5gs): classes only
    "permission.request": _spec({"tool": "token", "group": "token"}),
    "permission.denied": _spec({"tool": "token", "group": "token"}, {"rule": "token"}),
    "compact.pre": _spec({"trigger": "token", "group": "token"}),
    "compact.post": _spec({"trigger": "token", "group": "token"}, {"size": "token"}),
    "turn.error": _spec({"error": "token", "group": "token"}),
})
CALL_OUTCOMES = ("ok", "error", "interrupt")  # a call.tool row's outcome
# The purpose of hand-written Python (python3 -c, or a script on stdin): the first rule that matches the code, in this
# order; the code itself is never kept (ST-75eg7e2h).
PYTHON_PURPOSES = (
    ("test-run", re.compile(r"\bpytest\b|_tools/tests\.py|\bunittest\b")),
    ("backlog-edit", re.compile(r"kb/_self/backlog/[^\n]*?(?:write_text|json\.dump|open\([^)]*[\"'][wa][\"'])"
                                r"|(?:write_text|json\.dump)[^\n]*?kb/_self/backlog/", re.S)),
    ("kb-read", re.compile(r"\bkb/(?:public|_self)/|\bimport (?:kbfacts|rag|kbcommon|bl_\w+|backlog)\b"
                           r"|\bfrom (?:kbfacts|rag|kbcommon|bl_\w+|backlog) import\b")),
    ("parse", re.compile(r"\bjson\.loads?\(|\bcsv\.|\bast\.parse\(|\bre\.(?:findall|search|match|sub|finditer)\(")),
)
PYTHON_INLINE = ("python-c", "python")  # the classes whose code is in the command: -c, or a script on stdin


def python_purpose(command):
    """The closed purpose of hand-written Python in a shell command (PYTHON_PURPOSES, else `other`): read from the
    command's text, which is never returned or stored."""
    text = command if isinstance(command, str) else ""
    return next((name for name, rx in PYTHON_PURPOSES if rx.search(text)), "other")
COMPACT_TRIGGERS = ("manual", "auto")
STOP_ERRORS = ("rate_limit", "overloaded", "authentication_failed", "oauth_org_not_allowed", "account_on_hold",
               "billing_error", "invalid_request", "model_not_found", "server_error", "max_output_tokens",
               "cloud_credential_error", "unknown")  # StopFailure's documented error classes (claude/hooks.md)
DENIED_RULES = frozenset((  # the labels of the classifier's built-in soft_deny and hard_deny rules, as
    # `claude auto-mode defaults` printed them (v2.1.289); a denial naming any other rule (a custom one) stores none
    'Account & Standing-Rule Changes', 'Auto-Mode Bypass', 'Blind Apply', 'Browser File Upload Exfil',
    'Browser Input Exfil', 'Browser JS Exfil', 'Browser Navigate Exfil', 'Browser Shortcut Execution', 'CI Bypass',
    'ChatOps Trigger Comments', 'Cloud Storage Mass Delete', 'Cluster-Wide Workload Creation',
    'Code That Leaks When Run', 'Code from External', 'Command Network Lists', 'Containment Escape',
    'Create Public Surface', 'Create RCE Surface', 'Create Unsafe Agents', 'Credential Exploration',
    'Credential Leakage', 'Credential Materialization', 'DNS / Domain / Cert Changes', 'Data Exfiltration',
    'Excess Sensitive Detail', 'Exfil Scouting', 'Expose Local Services', 'External Ingress Tunnel',
    'External System Writes', 'Feature Flag Writes', 'Git Destructive', 'Instruction Poisoning',
    'Interfere With Workloads', 'Irreversible Deletion (general)', 'Irreversible Local Destruction',
    'Live-Shared Artifact Sensitive Delta', 'Logging/Audit Tampering', 'Merge Without Review',
    'Modify Shared Resources', 'Node Lifecycle Operations', 'Out-of-Place Publication', 'PII Data Handling',
    'Package Registry Bypass', 'Permission Grant', 'Production Deploy', 'Production Reads',
    'Protected-Scope IaC Apply', 'Public Data-Sharing Upload', 'Real-World Transactions', 'Remote Repoint',
    'Remote Shell Writes', 'Safety Bypass Flag', 'Sandbox Network Callback', 'Secret-Store Writes',
    'Security Test Removal', 'Security Weaken', 'Self-Approval', 'Self-Modification', 'Sensitive Remote Exec',
    'Sensitive-Source Provenance', 'Session Transcript Tampering', 'Shared Cluster Mutation', 'Shared Scratch Sweep',
    'TLS/Auth Weaken', 'Third-Party Attack', 'Tmux Self Drive', 'Traffic Redirection', 'Unauthorized Persistence',
    'Unrequested Artifact Publish', 'Unrequested Commit in a Connected App', 'Untrusted Code Integration',
    'Unverifiable Deletion Scope', 'Unverifiable Deletion Target',
))
DENIED_RULE = re.compile(r"\[([^\[\]]{1,60})\]")  # a bracketed rule name in a PermissionDenied reason


def denied_rule(reason):
    """The rule token of a PermissionDenied reason: the first bracketed name that is one of DENIED_RULES (lower case,
    each run of other characters one `-`), `classifier-unavailable` for that reason, else None; the reason's text is
    never returned or stored."""
    text = reason if isinstance(reason, str) else ""
    named = next((m.group(1).strip() for m in DENIED_RULE.finditer(text) if m.group(1).strip() in DENIED_RULES), None)
    if named:
        return re.sub(r"[^a-z0-9]+", "-", named.lower()).strip("-")[:40]
    return "classifier-unavailable" if text.strip().lower().startswith("classifier unavailable") else None


def _shape_ok(shape, v):
    if isinstance(shape, str):
        return OPS_KINDS[shape](v)
    kind, most, sub = shape
    if not (isinstance(v, list) and len(v) <= most):
        return False
    if kind == "list":
        return all(OPS_KINDS[sub](x) for x in v)
    return all(isinstance(x, dict) and x and set(x) <= set(sub) and all(OPS_KINDS[sub[k]](x[k]) for k in x) for x in v)


def ops_problems(fields, where=""):
    """The problems of the fields of one ops row (`event` and its keys; the row's id, time, surface and format are
    not read): an event outside OPS_EVENTS, a key the event does not have, a required key missing, a value outside
    its shape. [] when it is a row the store keeps. A value is never repeated in full, only its start."""
    pre = f"{where}: " if where else ""
    event = fields.get("event")
    spec = OPS_EVENTS.get(event) if isinstance(event, str) else None
    if spec is None:
        return [f"{pre}event {str(event)[:40]!r} is not one of {', '.join(OPS_EVENTS)}"]
    out = []
    other = sorted(set(map(str, fields)) - set(spec) - {"event"})
    if other:
        out.append(f"{pre}keys event {event} never has: {', '.join(k[:40] for k in other)}")
    for key, (shape, needed) in spec.items():
        if key not in fields:
            if needed:
                out.append(f"{pre}event {event} lacks {key}")
        elif not _shape_ok(shape, fields[key]):
            out.append(f"{pre}{key} of {event} is not a closed {shape if isinstance(shape, str) else shape[0]} value: "
                       f"{str(fields[key])[:40]!r}")
    return out



# ---------------------------------------------------------------- where rows go, and whether they are written

@functools.lru_cache(maxsize=None)
def spool_dir():
    """The spool directory, or None when capture writes nothing (mode off, or the DISABLED marker). Read once per
    process: a hook is one process, and a tool's requests share its answer."""
    d, cfg = places()
    return None if logging_off(d, cfg) else d / "spool"


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
    keep = {k: row[k] for k in ("id", "ts", "surface", "v", "session_id", "prompt_id") if k in row}
    return json.dumps(dict(keep, cut=True), ensure_ascii=False, separators=(",", ":"))


def spool_file(spool, session_id, ts):
    if session_id and SAFE_SESSION.fullmatch(session_id):
        return spool / f"{session_id}.jsonl"
    return spool / f"tools-{ts[:10]}.jsonl"


def record(surface, session_id=None, **fields):
    """Append one spool row and return it, or None when capture is off. Never raises: a caller's work never fails
    for its log. An `ops` row (`record("ops", event="land.step", item=..., ...)`) is written only when it is a
    closed event with its closed keys (ops_problems) and short enough to stay whole (OPS_ROW_MAX_CHARS); it is
    never given a session."""
    try:
        spool = spool_dir()
        if spool is None:
            return None
        row = {"id": str(uuid.uuid4()), "ts": now(), "surface": surface, "v": ROW_FORMAT}
        given = {k: v for k, v in fields.items() if v is not None}
        if surface == OPS:  # no session, and nothing but a closed event: a row that breaks its shape is not written
            if ops_problems(given):
                return None
            session_id = None
        if isinstance(session_id, str) and session_id:
            row["session_id"] = session_id
        row.update(given)
        line = json.dumps(row, ensure_ascii=False, separators=(",", ":")) if surface == OPS else fit(dict(row))
        if surface == OPS and len(line) > OPS_ROW_MAX_CHARS:
            return None
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
    """The outcome class of one HTTP request made by a tool: facts only (querylog.md, Surfaces)."""
    if error is not None:
        return "error"
    if final_url and url and host_path(final_url)[0] != host_path(url)[0]:
        return "redirect-cross-host"
    if body_len == 0:
        return "empty"
    if limit and body_len is not None and body_len >= limit:
        return "truncated"
    return f"http-{status}" if isinstance(status, int) else "unknown"


def record_request(url, outcome, body=None):
    """One row per request made by fetch.py or census.py (the tool is the running script); `chars` is the length of
    the body read, decoded as UTF-8, when there is one."""
    host, path = host_path(url)
    if host:
        chars = len(body.decode("utf-8", "replace")) if isinstance(body, bytes) else None
        record("tool_fetch", tool=Path(sys.argv[0]).name or None, host=host, path=path, outcome=outcome, chars=chars)


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


def pack_lines(text):
    """[{line, tag, verdict}] of the kb lines a kb tool's result returned, in order, each once, at most LINES_MAX: a
    pack's `- path:line ...` and a search hit's `[score] path:line` (its text on the next line). `tag` is the line's
    `[TAG ids]` and `verdict` the `coverage:` line above it, each left out when there is none. None when no line."""
    out, seen, verdict = [], set(), None
    ls = (text or "").splitlines()
    for n, ln in enumerate(ls):
        m = COVERAGE.match(ln)
        if m:
            verdict = m.group(1)
            continue
        m = KB_LINE.match(ln)
        if not m or m.group(2) in seen or len(out) >= LINES_MAX:
            continue
        seen.add(m.group(2))
        rest = m.group(3) if m.group(1) == "- " else (ls[n + 1] if n + 1 < len(ls) else "")
        tag = LINE_TAG.search(rest)
        out.append({k: v for k, v in (("line", m.group(2)), ("tag", tag and tag.group(1)), ("verdict", verdict)) if v})
    return out or None


def pack_summary(text):
    """{verdict, verdicts, articles, lines} of a kb tool's result text (the pack's `coverage:` lines, `## path` heads
    and kb lines)."""
    verdicts = COVERAGE.findall(text)
    articles = list(dict.fromkeys(re.findall(r"^## (\S+/\S+)", text, re.M)))[:20]
    out = {"articles": articles or None, "lines": pack_lines(text)}
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
    (kb_ask.py, fetch.py, census.py) written since the prompt began; an ops row of the tools file is none."""
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
        if any(r.get("ts", "") >= began and r.get("surface") != OPS  # an ops row (call.tool) is no kb use
               for r in rows(spool / f"tools-{day.isoformat()}.jsonl")):
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


def shell_segments(command):
    """(piece, separator) pairs of a shell command split at unquoted `;`, `&`, `|` and newlines; the separator is
    the character that ended the piece ("" for the last). A separator inside quotes stays in its piece, so a quoted
    sentence that mentions a command is no command. An `&` that belongs to a redirect (`2>&1`, `&>file`) is no
    separator."""
    out, cur, quote = [], [], None
    for n, ch in enumerate(command):
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            cur.append(ch)
        elif ch == "&" and (command[n - 1:n] in (">", "<") or command[n + 1:n + 2] == ">"):
            cur.append(ch)
        elif ch in ";&|\n":
            out.append(("".join(cur), ch))
            cur = []
        else:
            cur.append(ch)
    return [*out, ("".join(cur), "")]


def work_action(command):
    """(item, action) of the first piece of a shell command that runs `backlog.py claim|done|release ID`, or None.
    Only the command's own shape counts: the script's name after nothing but an interpreter, a launcher, its flags
    and environment assignments (a path, `python3`, `py -3`, `sh .../kbpy`, a PowerShell `&` call), then an optional
    `--root DIR`, the action and the item id, with any `--by`, `--commit` or `--trailer` after it. `done --dry-run`
    changes nothing and is none; so is a mention in a quoted text, in `echo`, `git commit -m` or a search, and a
    command piped into another (`done ID | tail`, `done ID || echo`: the exit code is the last command's, so a
    refusal would read as a success). Never the command's other text."""
    def unquote(t):
        return t[1:-1] if len(t) > 1 and t[0] == t[-1] and t[0] in "\"'" else t

    def base(t):
        return re.split(r"[/\\]", t)[-1]

    for piece, sep in shell_segments(command):
        toks = [unquote(t) for t in SHELL_TOKEN.findall(piece)]
        at = next((n for n, t in enumerate(toks) if base(t) == "backlog.py"), None)
        if at is None or not all(WORK_LAUNCHER.fullmatch(t) or WORK_LAUNCHER.fullmatch(base(t)) for t in toks[:at]):
            continue
        rest = toks[at + 1:]
        if rest[:1] == ["--root"]:
            rest = rest[2:]
        elif rest and rest[0].startswith("--root="):
            rest = rest[1:]
        if not rest or rest[0] not in WORK_ACTIONS:
            continue
        flags, item, skip = rest[1:], None, False
        for t in flags:
            if skip:
                skip = False
            elif t in WORK_VALUE_FLAGS:
                skip = True
            elif not t.startswith("-") and item is None:
                item = t
        if item and WORK_ITEM.fullmatch(item) and not {"--dry-run", "-h", "--help"} & set(flags):
            # a pipeline's exit code is its last command's: a refused `done` piped on would be read as a success
            return None if sep == "|" else (item, rest[0])
    return None


def refused_done(event, command):
    """The item of a `backlog.py done ID` that ran and was refused, from a `PostToolUseFailure` event, else None. The
    command is read as `work_action` reads a success (the same parser: a mention or a dry run is none), and the
    failure must be the command's own exit: the first line of `error` is `Exit code 1`, backlog.py's refusal code
    (WORK_REFUSED_EXIT). An interrupt, a start failure or timeout with no such line, another exit code (2 is bad
    usage, 127 and 9009 a missing interpreter) and a failed `claim` or `release` are none. Never the error's text."""
    if event.get("is_interrupt"):
        return None
    first = str(event.get("error") or "").split("\n", 1)[0].strip()
    m = re.fullmatch(r"Exit code (\d+)", first)
    if not m or int(m.group(1)) != WORK_REFUSED_EXIT:
        return None
    work = work_action(command)
    return work[0] if work and work[1] == "done" else None


def fetch_outcome(tool, ok, event, host):
    """The outcome class of a hook-seen fetch: facts only, else `unknown` (querylog.md, Surfaces)."""
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


def agent_salt():
    """The salt of the agent hashes: a random string kept in the querylog directory (never in the repository), made on
    first use. None when it can be neither read nor made."""
    path = places()[0] / AGENT_SALT_NAME
    for _ in range(2):
        try:
            salt = path.read_text(encoding="utf-8").strip()
            if len(salt) >= 32:
                return salt
        except OSError:
            pass
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "x", encoding="utf-8") as f:  # exclusive: a second hook that raced reads this one's
                f.write(secrets.token_hex(16) + "\n")
        except OSError:
            pass
    return None


def agent_hash(agent_id):
    """A salted short hash of an agent id (OPS_AGENT), or None without a salt: the id never leaves this function."""
    salt = agent_salt()
    if salt is None or not isinstance(agent_id, str) or not agent_id:
        return None
    return hashlib.sha256(f"{salt}\0{agent_id}".encode("utf-8")).hexdigest()[:AGENT_HASH_CHARS]


def work_branch_item(cwd):
    """The item id of the `work/<id>` branch checked out at `cwd` (or above it), read from the repository's HEAD file
    with no process started, else None. Only the id leaves: never the branch text or a path."""
    if not (isinstance(cwd, str) and cwd):
        return None
    try:
        start = Path(cwd)
        if not start.is_absolute():
            return None
        for d in (start, *start.parents):
            dot = d / ".git"
            if dot.is_dir():
                head = dot / "HEAD"
                break
            if dot.is_file():
                text = dot.read_text(encoding="utf-8").strip()
                if not text.startswith("gitdir:"):
                    return None
                git_dir = Path(text[len("gitdir:"):].strip())
                head = (git_dir if git_dir.is_absolute() else d / git_dir) / "HEAD"
                break
        else:
            return None
        ref = head.read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        return None
    tail = ref[len(WORK_BRANCH_REF):] if ref.startswith(WORK_BRANCH_REF) else ""
    return tail if WORK_ITEM.fullmatch(tail) else None


def agent_row(event, sid):
    """The `work` row of a SubagentStart or SubagentStop event: `action` agent-start or agent-stop, `agent` (a salted
    short hash of the agent id, never the id), `group` (kbusage.agent_group of the agent type, in lower case: a token) and `item` when the
    hook's directory is on a `work/<id>` branch. None for an event with no agent id. Distill pairs the rows
    (ql_distill.plan_agents)."""
    import kbusage
    agent = agent_hash(event.get("agent_id"))
    if agent is None:
        return None
    kind = str(event.get("agent_type") or "").rsplit(":", 1)[-1]
    return record("work", sid, action=AGENT_ACTIONS[event.get("hook_event_name") == "SubagentStop"], agent=agent,
                  group=kbusage.agent_group(kind).lower(), item=work_branch_item(event.get("cwd")))


def call_row(event, ok):
    """The ops row `call.tool` of one PostToolUse or PostToolUseFailure event of a kb tool, a documentation server's
    tool or a shell command (the operator's scope, ST-rpdfgu3t): the tool's group, the command's closed class for a
    shell (kbusage.command_class, never the command or a path), the agent group (`main` outside a subagent), the
    outcome (ok, error or interrupt), `duration_ms` when the event has one and the result's size class. None for any
    other tool."""
    import kbusage
    tool = str(event.get("tool_name") or "")
    group = kbusage.call_group(tool)
    if not (tool in SHELL_TOOLS or KB_TOOL.fullmatch(tool) or group.startswith("docs.")):
        return None
    args = event.get("tool_input") if isinstance(event.get("tool_input"), dict) else {}
    kind = str(event.get("agent_type") or "").rsplit(":", 1)[-1]
    agent = kbusage.agent_group(kind).lower() if kind else "main"
    outcome = "ok" if ok else "interrupt" if event.get("is_interrupt") is True else "error"
    res = event.get("tool_response") if ok else event.get("error")
    if isinstance(res, dict) and ("stdout" in res or "stderr" in res):  # a shell's result: its two streams
        res = f"{res.get('stdout') or ''}{res.get('stderr') or ''}"
    size = kbusage.size_class(len(text_of(res)))
    ms = event.get("duration_ms")
    cls = kbusage.command_class(args.get("command")) if tool in SHELL_TOOLS else None
    return record(OPS, event="call.tool", tool=group, group=agent, outcome=outcome, size=size,
                  ms=ms if isinstance(ms, int) and not isinstance(ms, bool) and ms >= 0 else None,
                  purpose=python_purpose(args.get("command")) if cls in PYTHON_INLINE else None, **{"class": cls})


def hook_group(event):
    """The agent group of a hook event as a token: `main` outside a subagent."""
    import kbusage
    kind = str(event.get("agent_type") or "").rsplit(":", 1)[-1]
    return kbusage.agent_group(kind).lower() if kind else "main"


def hook_ops_row(event):
    """The ops row of a PermissionRequest, PermissionDenied, PreCompact, PostCompact or StopFailure event (ST-mkczg5gs):
    the tool's group, the classifier rule a denial names (from its `[...]` only, else `classifier-unavailable` or
    none), the compaction trigger, the summary's size class, the API error's class (StopFailure's documented set, else
    `unknown`) and the agent group; never the reason text, the command or tool input, the summary or a path."""
    import kbusage
    name, group = event.get("hook_event_name"), hook_group(event)
    if name in ("PermissionRequest", "PermissionDenied"):
        tool = kbusage.call_group(str(event.get("tool_name") or ""))
        if name == "PermissionRequest":
            return record(OPS, event="permission.request", tool=tool, group=group)
        return record(OPS, event="permission.denied", tool=tool, group=group, rule=denied_rule(event.get("reason")))
    if name in ("PreCompact", "PostCompact"):
        trigger = event.get("trigger") if event.get("trigger") in COMPACT_TRIGGERS else "other"
        if name == "PreCompact":
            return record(OPS, event="compact.pre", trigger=trigger, group=group)
        return record(OPS, event="compact.post", trigger=trigger, group=group,
                      size=kbusage.size_class(len(text_of(event.get("compact_summary")))))
    if name == "StopFailure":
        error = event.get("error") if event.get("error") in STOP_ERRORS else "unknown"
        return record(OPS, event="turn.error", error=error, group=group)
    return None


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
        row = record("prompt", sid, prompt_id=pid, prompt=prompt, kb_intent=intent(prompt))
        try:
            add_usage(spool, sid, event.get("transcript_path"), skip=pid)
        except Exception:  # noqa: BLE001
            pass
        return row
    if name in ("PostToolUse", "PostToolUseFailure"):
        tool = str(event.get("tool_name") or "")
        args = event.get("tool_input") if isinstance(event.get("tool_input"), dict) else {}
        ok = name == "PostToolUse"
        try:
            call_row(event, ok)  # the census row, beside whatever row the call gives below
        except Exception:  # noqa: BLE001 - capture never fails for its log
            pass
        if not ok and event.get("is_interrupt") is True:  # distill counts it on the item of the prompt's window
            record("work", sid, prompt_id=pid, action="interrupt")
        m = KB_TOOL.fullmatch(tool)
        if m:
            summary = pack_summary(text_of(event.get("tool_response"))) if ok else {"outcome": "error"}
            return record("mcp", sid, prompt_id=pid, tool=m.group(1),
                          args={k: clip(args[k]) for k in KB_ARGS if k in args} or None, **summary)
        work = None
        if tool in SHELL_TOOLS and isinstance(args.get("command"), str):
            if ok:
                work = work_action(args["command"])
            else:
                item = refused_done(event, args["command"])
                work = (item, "refused") if item else None
        if work:  # a successful claim, done or release, or a refused done: only the item and the action, never the command
            agent = event.get("agent_id")
            return record("work", sid, prompt_id=pid, agent_id=agent if isinstance(agent, str) and agent else None,
                          item=work[0], action=work[1])
        target = fetch_target(tool, args)
        if target is None or not used_kb(spool, sid, pid):
            return None  # a fetch counts only in a prompt that also used the kb (querylog.md, Surfaces)
        host, path, fetcher = target
        chars = len(text_of(event.get("tool_response"))) if ok and tool not in SHELL_TOOLS else None
        return record("fetch", sid, prompt_id=pid, tool=tool, fetcher=fetcher, host=host, path=path,
                      outcome=fetch_outcome(tool, ok, event, host), chars=chars)
    if name in ("SubagentStart", "SubagentStop"):
        return agent_row(event, sid)
    if name in ("PermissionRequest", "PermissionDenied", "PreCompact", "PostCompact", "StopFailure"):
        return hook_ops_row(event)
    if name == "Stop":
        if not used_kb(spool, sid, pid):
            return None
        return record("stop", sid, prompt_id=pid, answer=str(event.get("last_assistant_message") or ""))
    return None


def usage_targets(rs, skip=None):
    """(prompt ids that need a usage row, (prompt id, reader) pairs that have one) of one session's spool rows, the
    targets in the order the prompts began. A prompt needs one when it used the kb (a kb_hook or mcp row, or a kb
    intent) or lies inside a work window: from a `claim` row of an item to the `done` or `release` row of the same
    item, the prompts of both rows included, a window still open at the end of the rows running to it. A `done` or
    `release` with no open claim in these rows opens and closes nothing. `skip` (the running prompt) is never a
    target."""
    order, kb, inside, have, open_items = [], set(), set(), set(), set()
    for r in rs:
        pid = r.get("prompt_id") if isinstance(r, dict) else None
        if not isinstance(pid, str):
            continue
        if r.get("surface") == "usage":
            have.add((pid, r.get("reader")))
            continue
        if pid not in order:
            order.append(pid)
            if open_items:
                inside.add(pid)
        if r.get("surface") in ("kb_hook", "mcp") or r.get("kb_intent"):
            kb.add(pid)
        elif r.get("surface") == "work" and isinstance(r.get("item"), str):
            if r.get("action") == "claim":
                open_items.add(r["item"])
                inside.add(pid)
            elif r.get("action") in ("done", "release") and r["item"] in open_items:
                open_items.discard(r["item"])
                inside.add(pid)
    return [pid for pid in order if pid != skip and (pid in kb or pid in inside)], have


def add_usage(spool, session_id, transcript_path, skip=None):
    """Append a `usage` row (kbusage.prompt_usage) to the spool file of `session_id` for each of its prompts but
    `skip` that used the kb (a kb_hook or mcp row, or a prompt with a kb intent) or lies inside a work window of the
    session (usage_targets), kb or not, and has no usage row of this reader yet. The number of rows written; the
    transcript path is never written."""
    if not (isinstance(session_id, str) and SAFE_SESSION.fullmatch(session_id)
            and isinstance(transcript_path, str) and transcript_path):
        return 0
    path = Path(spool) / f"{session_id}.jsonl"
    targets, have = usage_targets(list(rows(path)), skip)
    if not targets:
        return 0
    import kbusage
    out = []
    for pid in targets:
        rec = None if (pid, kbusage.READER_VERSION) in have else kbusage.prompt_usage(transcript_path, pid)
        if rec is not None:
            out.append({"id": str(uuid.uuid4()), "ts": now(), "surface": "usage", "v": ROW_FORMAT,
                        "session_id": session_id, "prompt_id": pid, "reader": kbusage.READER_VERSION, "usage": rec})
    if out:
        with _lock, open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json_lines(out))
    return len(out)


def where():
    """`where`: the mode, the config file, the directory and whether capture writes."""
    d, cfg = places()
    print(f"mode={read_mode(cfg)} config={cfg} dir={d} disabled={(d / DISABLED_NAME).exists()} "
          f"writes={'yes' if spool_dir() else 'no'}")
    return 0
