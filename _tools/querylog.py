#!/usr/bin/env python3
"""The query log pipeline: capture, distill, learn and apply for kb lookups, and its digest (stdlib only).

kb/_self/querylog.md is the design, and the Query log items of kb/_self/work-left.md build the commands in order.
Capture, distill, learn, a local apply with its gap step and opt-in research, the quote check, apply's direct
push, the weekly digest and status are built.

  querylog.py capture   the capture hook (UserPromptSubmit, PostToolUse, PostToolUseFailure and Stop, async, in
                        .claude/settings.json and the plugin): reads one hook event as JSON on stdin and appends at
                        most one row to the spool; prints nothing and exits 0 whatever happens (a logging hook must
                        never get in the way of a prompt)
  querylog.py launch    the SessionEnd and SessionStart hook: marks the ended session closed, then starts a detached
                        `distill --settle LAUNCH_SETTLE_S` when a closed session waits and no distill holds the lock;
                        prints nothing and exits 0
  querylog.py distill [--replay FILE] [--settle S]
                        the closed sessions of the spool -> one run file in the local store (the `store` directory
                        beside the spool, laid out as kb/_querylog/): the rules, then Haiku in capped batches, then
                        the rules and the leak scan again; an entry a local run file already holds is not distilled
                        again. Mode `local` deletes the spool rows of the entries written or dropped. Mode `auto` in
                        a clone deletes those of dropped entries only, then runs `apply --push` under the same lock,
                        which deletes the others once their run file is on origin/main. --replay answers the Haiku
                        calls from a recorded reply file ({"replies": [...]}) instead of `claude -p`. Exit 0 done (or
                        nothing to do), 1 the push of mode `auto` failed, 3 another distill holds the lock
  querylog.py learn [--store DIR]
                        the store's run files and the kb at HEAD -> findings (default: the local store): every judged
                        miss re-run with pack first (`fixed-since` when it now passes), then eval, alias, expansion,
                        gap-candidate and report-only source findings; writes one findings file,
                        findings/<yyyy-mm>/<run-id>.jsonl, holding only the records that change a finding's state
                        (none: no file). Exit 0
  querylog.py apply [--store DIR] [--hold ID ...]
                        the store's open eval findings (default: the local store) -> changes in this clone's working
                        tree, never committed or pushed: each eval row is written together with its fix (alias rows,
                        or the question as a doc2query expansion of one of the article's facts), the first candidate
                        with which every `rag.py eval` question passes, the mean pack of the eval questions does not
                        grow and off-kb `good` does not rise; an alias term already in an alias file or held by the kb
                        is refused. No accepted fix: the miss becomes a gap candidate (`no-fix`) and its fix
                        `rejected`. The gap step: an open gap candidate whose miss the pack still reproduces, with
                        an article in the lead (not `none`), becomes a dated entry under that article's topic in its
                        root's _gaps.md (candidate-gap -> gap). Research, only when the user's config turns it on
                        (`research`, `research_daily`; --clone DIR reads that clone's config and daily count): at
                        most the day's runs left and RESEARCH_RUNS_PER_APPLY, one `claude -p` (hooks off) per gap
                        finding, whose candidate facts
                        are kept only when their quote is on the page (quotecheck); accepted facts and their source
                        rows are added (gap -> candidate-fact -> claim), a disagreement becomes a _conflicts.md
                        entry, and nothing existing is edited (build_index and check.py errors=0 after, else every
                        file is put back). --replay-research FILE answers the runs and page fetches from a recorded
                        file. Source findings are left alone, and so are the findings named by --hold and those
                        recorded `apply-failed` (FAILED_RETRIES). One findings file records each outcome (none: no
                        file). Exit 0, 1 when `rag.py eval` fails before an eval change
  querylog.py quotecheck URL QUOTE [--page FILE [--ctype TYPE]]
                        whether QUOTE (QUOTE_MIN_WORDS to QUOTE_MAX_WORDS words) is on the page at URL, fetched as
                        fetch.py fetches (or read from a recorded FILE) and reduced by fetch.py's to_text; entities,
                        whitespace, quote marks, Markdown links and emphasis normalized on both sides. Exit 0 on the
                        page, 1 not (the reason on stdout)
  querylog.py apply --push
                        the direct push, from a clone (explicit in every mode but `off`), under the distill lock:
                        fetch origin; check the CI of the last automatic commit on origin/main with `glab` or `gh`
                        (skipped with a note when neither is signed in; the host comes from origin's url, else
                        FALLBACK_GITLAB_HOST): a finished failure is red and gets a revert commit (KB-Auto: revert)
                        that keeps the store's files and records its findings `apply-failed`, an unfinished pipeline
                        stops the run; then, in the worktree beside the spool reset to origin/main: the local store's
                        run files that origin/main lacks, and its findings files that hold only learn's states for
                        findings origin/main does not record yet, copied into kb/_querylog, gated by `check` and the
                        leak scan, and committed (KB-Auto: querylog); the worktree's learn and apply on that store,
                        one commit with its KB-Auto trailer; one `kbgit.py sync --push` (gate, rebase on
                        origin/main, push to origin only). Once the run files are on origin/main, the spool rows of
                        their entries are deleted (a failed push deletes nothing). A conflict sync cannot resolve pushes
                        querylog/<run-id> with `-o merge_request.create -o merge_request.target=main`, main unchanged,
                        and later runs leave that branch's findings alone until main holds them. Exit 0 (pushed,
                        nothing to push, CI pending, conflict branch pushed), 1 a step failed, 2 refused, 3 the lock
  querylog.py check [DIR]  the store gates over DIR (default kb/_querylog): header and provenance fields, entry fields,
                        identifiers, fetch entries, duplicate ids and the findings files; one line per problem, exit 1
                        when there is any
  querylog.py where     prints the mode, the config file, the spool directory and whether capture writes
  querylog.py digest [--store DIR] [--week YYYY-Www]
                        the week's numbers from the committed store (default kb/_querylog): lookups by surface,
                        verdicts, judgements, misses and how many are fixed, fetches and their result characters, run
                        files and dropped entries, finding records written, and findings by kind and state at the
                        week's end. The week defaults to the ISO week of the store's newest entry; only the store and
                        the week go in, so every clone at one commit prints the same lines. Exit 0, 2 a bad week
  querylog.py digest --hook
                        the SessionStart hook (synchronous, `timeout` DIGEST_HOOK_TIMEOUT_S): at the first
                        SessionStart of an ISO week (the marker `digest-week` beside the spool), last week's digest
                        as one JSON line {"systemMessage": ...}, which Claude Code shows the person; nothing when
                        logging is off, the week is empty or reading the store took over DIGEST_BUDGET_S. Exit 0
  querylog.py status [--store DIR]
                        open source findings of the committed store, most result characters first; open merge
                        requests from querylog/ branches on origin's forge (glab or gh, skipped with a note when not
                        signed in); automatic commits reverted (KB-Auto: revert in git log). Exit 0

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
DEFAULT_RESEARCH = False  # research writes facts: each person turns it on in their own config file
DEFAULT_RESEARCH_DAILY = 3  # research runs per user per day when the config file turns research on and names no cap
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
PIPELINE_VERSION = 2  # bumped when what distill writes, or how it decides it, changes
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


def read_research(cfg):
    """(on, daily cap) the config file sets for research: off with no file (DEFAULT_RESEARCH), off when the file
    cannot be read, `research` is not true, or `research_daily` is not a whole number of 0 or more (fail closed);
    the cap is `research_daily`, else DEFAULT_RESEARCH_DAILY."""
    try:
        data = json.loads(Path(cfg).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return DEFAULT_RESEARCH, DEFAULT_RESEARCH_DAILY if DEFAULT_RESEARCH else 0
    except (OSError, ValueError):
        return False, 0
    if not isinstance(data, dict) or data.get("research", DEFAULT_RESEARCH) is not True:
        return False, 0
    daily = data.get("research_daily", DEFAULT_RESEARCH_DAILY)
    if isinstance(daily, bool) or not isinstance(daily, int) or daily < 0:
        return False, 0
    return True, daily


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
        chars = len(text_of(event.get("tool_response"))) if ok and tool not in SHELL_TOOLS else None
        return record("fetch", sid, prompt_id=pid, tool=tool, fetcher=fetcher, host=host, path=path,
                      outcome=fetch_outcome(tool, ok, event, host), chars=chars)
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
              "judged", "best", "fetches", "tool", "fetcher", "host", "path", "outcome", "chars")
FETCH_KEYS = ("tool", "fetcher", "host", "path", "outcome", "n", "chars")
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
    c = r.get("chars")
    item["chars"] = c if isinstance(c, int) and not isinstance(c, bool) and c >= 0 else None
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
            chars = item.pop("chars", None)
            key = json.dumps(item, sort_keys=True)
            f = fetches.setdefault(key, dict(item, n=0))
            f["n"] += 1
            if chars is not None:
                f["chars"] = f.get("chars", 0) + chars
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

def distill(qdir=None, cfg=None, haiku=None, now_dt=None, run_id=None, kb_commit=None, settle=0.0, out=print,
            deliver=None):
    """One distill: 0 done (or nothing to do, or logging off), 1 when the push of mode `auto` failed, 3 when another
    distill holds the lock. Mode `auto` in a clone keeps the spool rows of the entries it writes and then runs
    `deliver(qdir, out)` under the same lock (default: the push of `apply --push`), which deletes them once their
    run file is on origin/main; mode `local` (and `auto` in a plugin host) deletes them at once."""
    d, c = places()
    qdir, cfg = Path(qdir or d), Path(cfg or c)
    mode = read_mode(cfg)
    if (qdir / "DISABLED").exists() or mode == "off":
        out("distill: logging is off")
        return 0
    if mode == "auto" and deliver is None and qdir.resolve() == (HOME / "_cache" / "querylog").resolve():
        def deliver(q, say):
            return Pusher(HOME, q, run_cmd, None, say)()
    if mode != "auto":
        deliver = None
    lock = acquire(qdir)
    if lock is None:
        out("distill: another distill holds the lock")
        return 3
    try:
        if settle:
            time.sleep(settle)
        now_dt = now_dt or datetime.datetime.now(datetime.timezone.utc)
        rc = _distill(qdir, haiku or claude_haiku, now_dt, run_id, kb_commit, out, keep=deliver is not None)
        if deliver is not None:
            rc = 1 if deliver(qdir, out) not in (0, None) else rc
        return rc
    finally:
        release(lock)


def _plan(qdir, t_now, today, k):
    """One reading of the spool: (spool, sessions, tools, consumed, todo), `todo` holding one item {entry, texts,
    sid, key, tools, ts} per kb lookup of a closed session or of a finished day, in time order."""
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
    return spool, sessions, tools, consumed, todo


def _distill(qdir, haiku, now_dt, run_id, kb_commit, out, keep=False):
    """The run file of the closed sessions (entries a run file of the local store already holds are not distilled
    again), then the spool: the rows of dropped entries go, and so do those of written ones unless `keep`."""
    import redact
    k = redact.known()
    t_now, today = now_dt.timestamp(), now_dt.date().isoformat()
    spool, sessions, tools, consumed, todo = _plan(qdir, t_now, today, k)
    stored = {e["id"] for _, e in store_entries(qdir / "store")}
    done = [t for t in todo if t["entry"]["id"] in stored]
    todo = [t for t in todo if t["entry"]["id"] not in stored]

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
    if keep:
        _settle(spool, sessions, tools, consumed, qdir, today, dropped, waiting + written + done)
        if written or done:
            out(f"distill: the spool keeps the rows of {len(written) + len(done)} entries until their run file is "
                f"on {REMOTE}/{BRANCH}")
    else:
        _settle(spool, sessions, tools, consumed, qdir, today, written + dropped + done, waiting)
    return 0


def _settle(spool, sessions, tools, consumed, qdir, today, gone, stay):
    """The spool after a pass: the rows of the `gone` entries and of the prompts that never used the kb go, the rows
    of the `stay` entries stay (a closed session keeps its window end), and a finished day's tools file goes once all
    its rows are consumed."""
    wait_keys = {(t["sid"], t["key"]) for t in stay if t["sid"]}
    for t in gone:
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


def spool_delivered(qdir, ids, now_dt=None):
    """Delete the spool rows of the entries `ids`, whose run file is on origin/main; every other entry's rows stay.
    The number of entries whose rows went. Runs under the distill lock (distill and apply --push hold it)."""
    ids = set(ids)
    if not ids or not (Path(qdir) / "spool").is_dir():
        return 0
    import redact
    now_dt = now_dt or datetime.datetime.now(datetime.timezone.utc)
    today = now_dt.date().isoformat()
    spool, sessions, tools, consumed, todo = _plan(Path(qdir), now_dt.timestamp(), today, redact.known())
    gone = [t for t in todo if t["entry"]["id"] in ids]
    if gone:
        _settle(spool, sessions, tools, consumed, Path(qdir), today, gone,
                [t for t in todo if t["entry"]["id"] not in ids])
    return len(gone)


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
    for key in ("n", "chars"):
        if key in item and not (isinstance(item[key], int) and not isinstance(item[key], bool) and item[key] >= 0):
            out.append(f"{where}: fetch {key} is not a count")
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
    return out + duplicate_ids(store) + findings_problems(store, k)


# --- learn: the store and the kb at HEAD -> findings (querylog.md, Learn and apply) ---------------------------------

FINDINGS = "findings"
FINDING_KINDS = ("eval", "alias", "expansion", "gap", "source")
LEARN_STATES = ("open", "fixed-since")  # the states learn writes; a record in any other state is apply's to change
STAGES = ("miss", "candidate-gap", "gap", "candidate-fact", "claim")
SIGNALS = ("stage", "route")  # a host that needs staging, a fetch by a tool its route avoids
FINDING_ID = re.compile(r"F-[0-9a-f]{12}")
FINDING_KEYS = ("id", "kind", "state", "stage", "promotions", "entry", "expect", "article", "terms", "signal", "host",
                "level", "needs", "triggers", "tool", "route", "observed")
FAILED = re.compile(r"http-[45]\d\d|empty|truncated|error")  # fetch outcomes that count as failures on the host
WEB_SOURCES = HOME / "kb" / "_self" / "web-sources.md"
ROUTE_HOST = re.compile(r"(?:[a-z0-9-]+\.)+[a-z]{2,}")
FILE_SUFFIXES = ("txt", "md", "mdx", "json", "html", "xml", "csv", "py", "yml", "yaml")  # `llms.txt` is no host


def _findings_dir(store):
    return Path(store) / FINDINGS


def findings_files(store):
    """The findings files of a store, oldest run first: findings/<yyyy-mm>/<run-id>.jsonl."""
    d = _findings_dir(store)
    return sorted(d.glob("*/*.jsonl"), key=lambda p: p.stem) if d.is_dir() else []


def finding_states(store):
    """{finding id: its last record} across the store's findings files, in run order."""
    last = {}
    for p in findings_files(store):
        try:
            objs = load_run(p)
        except (OSError, ValueError):
            continue
        for _, rec in objs[1:]:
            if isinstance(rec.get("id"), str):
                last[rec["id"]] = rec
    return last


def finding_id(*parts):
    import hashlib
    return "F-" + hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:12]


# --- where a host stands: the provider registry, else the routes table of web-sources.md ---------------------------

def routes_table(text=None):
    """The rows of the routes table ("Routes by family" in kb/_self/web-sources.md): {family, find, read, avoid,
    hosts}, `hosts` being the host names its family, find and read cells name in backticks."""
    text = WEB_SOURCES.read_text(encoding="utf-8") if text is None else text
    m = re.search(r"^## Routes by family\n(.*?)(?=^## )", text, re.M | re.S)
    out = []
    for line in (m.group(1) if m else "").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.startswith("|") else []
        if len(cells) != 4 or cells[0] in ("family", "") or set(cells[0]) <= set("-: "):
            continue
        hosts = []
        for cell in cells[:3]:
            for tok in re.findall(r"`([^`]+)`", cell):
                h = tok.split("/", 1)[0].lower()
                if ROUTE_HOST.fullmatch(h) and h.rsplit(".", 1)[-1] not in FILE_SUFFIXES and h not in hosts:
                    hosts.append(h)
        out.append(dict(zip(("family", "find", "read", "avoid"), cells), hosts=hosts))
    return out


def registry_row(host, registry=None):
    """The provider-registry row (_tools/providers.csv, or a root's _providers.csv) serving `host`, not the `*` one."""
    import provider
    row = provider.for_url(f"https://{host}/", provider.providers() if registry is None else registry)
    return row if row and "*" not in (row.get("match") or "").split() else None


def staging_level(host, registry=None, routes=None):
    """(level, where from) of a host (kb/_self/web-sources.md, Staging levels): 3 with a provider-registry row, else 1
    with a row of the routes table, else 0."""
    if registry_row(host, registry):
        return 3, "registry"
    if any(host in r["hosts"] for r in (routes_table() if routes is None else routes)):
        return 1, "routes"
    return 0, None


def registry_problems(registry=None, routes=None):
    """A registry row whose host the routes table does not name: a staged family adds its routes row first, so the
    two sources of a host's level agree. The shared registry only; a root's own providers are its team's."""
    import provider
    rows = provider._read(provider.SHARED) if registry is None else registry
    hosts = {h for r in (routes_table() if routes is None else routes) for h in r["hosts"]}
    out = []
    for r in rows:
        if r.get("_root"):
            continue
        for m in (r.get("match") or "").split():
            h = m.split("/", 1)[0].lower()
            if m != "*" and h not in hosts:
                out.append(f"provider {r.get('provider')}: {h} has a registry row but no row in the routes table")
    return out


# --- the staging triggers (web-sources.md, "When a family needs staging"): the numbers a test holds equal to the doc

STAGE_SHARE_ROWS = 25  # Share: a host backing at least this many rows of a root's _sources.csv
STAGE_SHARE_PERCENT = 5  # Share: or at least this share of them
STAGE_FAILURES = 3  # Failures: this many failed fetches on the host
STAGE_NEEDED_LEVEL = 1  # what a Share or Failures trigger asks for first: a route
NUMBER_WORDS = {w: i for i, w in enumerate(("zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
                                            "nine", "ten"))}


def doc_triggers(text=None):
    """{share_rows, share_percent, failures} as the staging triggers of web-sources.md state them (None when absent)."""
    text = WEB_SOURCES.read_text(encoding="utf-8") if text is None else text
    m = re.search(r"^## When a family needs staging\n(.*?)(?=^## )", text, re.M | re.S)
    sec = m.group(1) if m else ""

    def num(rx):
        g = re.search(rx, sec, re.I)
        if not g:
            return None
        v = g.group(1).lower()
        return int(v) if v.isdigit() else NUMBER_WORDS.get(v)
    return {"share_rows": num(r"\*\*Share\.\*\*[^\n]*?at least (\d+) rows"),
            "share_percent": num(r"\*\*Share\.\*\*[^\n]*?at least (\d+)%"),
            "failures": num(r"\*\*Failures\.\*\*\s*(\w+) or more failures")}


def trigger_problems(text=None):
    """Each staging trigger whose number in querylog.py differs from web-sources.md."""
    ours = {"share_rows": STAGE_SHARE_ROWS, "share_percent": STAGE_SHARE_PERCENT, "failures": STAGE_FAILURES}
    doc = doc_triggers(text)
    return [f"trigger {k}: querylog.py has {v}, web-sources.md has {doc[k]}" for k, v in ours.items() if doc[k] != v]


def kb_host_counts():
    """({host: [(rows, the root's rows) per root]} from the roots' _sources.csv, {host: fetch errors} from their
    _fetch_state.csv), read at HEAD."""
    import csv, kbcommon
    share, errors = {}, {}
    for r in kbcommon.roots():
        for name, col in (("_sources.csv", None), ("_fetch_state.csv", "error")):
            p = Path(r.path) / name
            if not p.is_file():
                continue
            with open(p, encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
            counts = {}
            for row in rows:
                h, _ = host_path(row.get("url") or "")
                if h and (col is None or (row.get(col) or "").strip()):
                    counts[h] = counts.get(h, 0) + 1
            for h, n in counts.items():
                if col:
                    errors[h] = errors.get(h, 0) + n
                else:
                    share.setdefault(h, []).append((n, len(rows)))
    return share, errors


def share_trigger(per_root):
    """Whether a host backs at least STAGE_SHARE_ROWS rows, or STAGE_SHARE_PERCENT percent, of some root's sources."""
    return any(n >= STAGE_SHARE_ROWS or n * 100 >= STAGE_SHARE_PERCENT * total for n, total in per_root)


# --- the findings -----------------------------------------------------------------------------------------------------

def store_entries(store):
    """[(run id, entry)] of the store's run files, each entry id once (its first run)."""
    out, seen = [], set()
    for p in run_files(store):
        try:
            objs = load_run(p)
        except (OSError, ValueError):
            continue
        for _, e in objs[1:]:
            if isinstance(e.get("id"), str) and e["id"] not in seen:
                seen.add(e["id"])
                out.append((p.stem, e))
    return out


def is_miss(e):
    """A judged miss: Haiku judged the lookup missed or partly answered, or the pack's verdict was weak or none."""
    return isinstance(e.get("question"), str) and (e.get("judged") in ("missed", "partly")
                                                    or e.get("verdict") in ("weak", "none"))


def passes(res, best):
    """Whether a pack on HEAD answers the question: `good`, with the article that answers it among the pack's (the
    eval rule, rag.py run_eval); without one, `good` with no `check:` line."""
    if res.get("verdict") != "good":
        return False
    return best in res.get("paths", []) if best else not (res.get("unmatched") or res.get("spread"))


def unknown_words(question, res):
    """The question's words, lower case, whose stems the pack reports as nowhere in the kb."""
    import kbfacts
    missing = set(res.get("missing") or [])
    out = []
    for w in kbfacts.WORD.findall(question):
        w = w.lower()
        if kbfacts.stem(w) in missing and w not in out:
            out.append(w)
    return out


def default_pack(question):
    import kbfacts
    return kbfacts.pack(question, fmt="concise")


def miss_findings(e, res):
    """The findings of one judged miss after its re-run on HEAD: eval (an article answers it) with its fix, alias
    (the question uses a word the kb never holds) or expansion (every word is known: a paraphrase), or a gap
    candidate (no candidate article answers it). All `fixed-since` when the re-run passes."""
    best = e.get("best")
    ok = passes(res, best)
    state = "fixed-since" if ok else "open"
    obs = {"verdict": res.get("verdict"), "paths": list(res.get("paths") or [])[:4]}
    if not best:
        return [{"id": finding_id("gap", e["id"]), "kind": "gap", "state": state, "stage": "candidate-gap",
                 "promotions": [{"from": "miss", "to": "candidate-gap", "by": "learn"}], "entry": e["id"],
                 "observed": obs}]
    out = [{"id": finding_id("eval", e["id"]), "kind": "eval", "state": state, "stage": "miss", "entry": e["id"],
            "expect": best, "observed": obs}]
    if not ok:
        terms = unknown_words(e["question"], res)
        if terms:
            out.append({"id": finding_id("alias", e["id"]), "kind": "alias", "state": "open", "stage": "miss",
                        "entry": e["id"], "article": best, "terms": terms, "observed": obs})
        else:
            out.append({"id": finding_id("expansion", e["id"]), "kind": "expansion", "state": "open", "stage": "miss",
                        "entry": e["id"], "article": best, "observed": obs})
    return out


def host_fetches(entries):
    """{host: {failures, entries, webfetch, chars}} of the fetches the store's entries record; `chars` sums the
    result characters of the fetches that recorded them."""
    hosts = {}
    for _, e in entries:
        items = [f for f in e.get("fetches") or [] if isinstance(f, dict)]
        if e.get("host"):
            items.append({k: e[k] for k in FETCH_KEYS if k in e})
        for f in items:
            h = f.get("host")
            if not isinstance(h, str):
                continue
            n = f.get("n") if isinstance(f.get("n"), int) else 1
            s = hosts.setdefault(h, {"failures": 0, "entries": set(), "webfetch": set(), "chars": 0})
            s["entries"].add(e["id"])
            if isinstance(f.get("chars"), int):
                s["chars"] += f["chars"]
            if isinstance(f.get("outcome"), str) and FAILED.fullmatch(f["outcome"]):
                s["failures"] += n
            if f.get("tool") == "WebFetch":
                s["webfetch"].add(e["id"])
    return hosts


def source_findings(entries, registry=None, routes=None, counts=None):
    """Report-only findings on the hosts the store's fetches name: `stage` when a Share or Failures trigger holds
    and the host has less than STAGE_NEEDED_LEVEL; `route` when WebFetch read a host whose route avoids it."""
    routes = routes_table() if routes is None else routes
    share, errors = kb_host_counts() if counts is None else counts
    out = []
    for host, s in sorted(host_fetches(entries).items()):
        level, _ = staging_level(host, registry, routes)
        per_root = share.get(host, [])
        rows = max((n for n, _ in per_root), default=0)
        failures = s["failures"] + errors.get(host, 0)
        triggers = [t for t, hit in (("share", share_trigger(per_root)), ("failures", failures >= STAGE_FAILURES))
                    if hit]
        if triggers and level < STAGE_NEEDED_LEVEL:
            out.append({"id": finding_id("source", "stage", host), "kind": "source", "state": "open",
                        "signal": "stage", "host": host, "level": level, "needs": STAGE_NEEDED_LEVEL,
                        "triggers": triggers, "observed": {"rows": rows, "failures": failures,
                                                           "entries": len(s["entries"])}})
        route = next((r for r in routes if host in r["hosts"]), None)
        if s["webfetch"] and route and "WebFetch" in route["avoid"]:
            out.append({"id": finding_id("source", "route", host), "kind": "source", "state": "open",
                        "signal": "route", "host": host, "tool": "WebFetch", "route": route["family"].replace("`", ""),
                        "observed": {"entries": len(s["webfetch"])}})
    return out


def _key(rec):
    return {k: v for k, v in rec.items() if k != "observed"}


def learn_run_id(store, entries_runs, body):
    """`<time>Z-<8 hex>`: the time of the newest run file, or one second after the newest findings file when that is
    later, so the findings files sort in the order they were written; the hex is a hash of the records. The same
    store and HEAD give the same name in any clone."""
    def t(run):
        return datetime.datetime.strptime(run[:16], "%Y%m%dT%H%M%SZ").replace(tzinfo=datetime.timezone.utc)
    when = max(t(r) for r in entries_runs)
    done = findings_files(store)
    if done:
        when = max(when, t(done[-1].stem) + datetime.timedelta(seconds=1))
    import hashlib
    return f"{when.strftime('%Y%m%dT%H%M%SZ')}-{hashlib.sha256(body.encode('utf-8')).hexdigest()[:8]}"


def learn(store=None, pack=None, kb_commit=None, registry=None, routes=None, counts=None, out=print):
    """One learn over `store` (default: the local store beside the spool): every judged miss re-run with `pack` on
    HEAD, the source findings, then one findings file holding only the records that change a finding's state. 0."""
    store = Path(store or places()[0] / "store")
    pack = pack or default_pack
    entries = store_entries(store)
    if not entries:
        out("learn: no run files")
        return 0
    derived = {}
    for _, e in entries:
        if is_miss(e):
            for rec in miss_findings(e, pack(e["question"])):
                derived[rec["id"]] = rec
    for rec in source_findings(entries, registry, routes, counts):
        derived[rec["id"]] = rec
    last = finding_states(store)
    new = []
    for fid, rec in derived.items():
        prev = last.get(fid)
        if prev is None or (prev.get("state") in LEARN_STATES and _key(prev) != _key(rec)):
            new.append(rec)
    for fid, prev in last.items():  # an open finding learn no longer derives: the kb at HEAD handles it now
        if fid not in derived and prev.get("state") == "open":
            new.append({**{k: v for k, v in prev.items() if k != "observed"}, "state": "fixed-since"})
    total = len({**last, **{r["id"]: r for r in new}})
    if not new:
        out(f"learn: nothing new (findings={total})")
        return 0
    run_id, states = write_findings(store, entries, new, LEARN_STATES, kb_commit)
    out(f"learn: run={run_id} records={len(new)} open={states['open']} fixed-since={states['fixed-since']} "
        f"findings={total}")
    return 0


def write_findings(store, entries, new, states, kb_commit=None):
    """One findings file of records `new` (kind order, then id), with the counts of `states`: (run id, counts)."""
    new = sorted(new, key=lambda r: (FINDING_KINDS.index(r["kind"]), r["id"]))
    new = [{k: r[k] for k in FINDING_KEYS if k in r} for r in new]
    body = "".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in new)
    run_id = learn_run_id(store, [r for r, _ in entries], body)
    counts = {s: sum(1 for r in new if r["state"] == s) for s in states}
    header = {"run": run_id, "pipeline": PIPELINE_VERSION, "retrieval": retrieval_version(),
              "kb_commit": kb_commit or head_commit(), "counts": {"findings": len(new), **counts}}
    path = _findings_dir(store) / f"{run_id[:4]}-{run_id[4:6]}" / f"{run_id}.jsonl"
    write_text(path, json.dumps(header, ensure_ascii=False, separators=(",", ":")) + "\n" + body)
    return run_id, counts


# --- apply: open findings -> eval rows with their fixes, in the working tree (querylog.md, Learn and apply) --------

APPLY_STATES = ("applied", "rejected", "no-fix")  # fix written / fix failed its gates / a miss with no accepted fix
APPLY_FAILED = "apply-failed"  # its automatic commit turned CI red and was reverted (apply --push)
FINDING_STATES = LEARN_STATES + APPLY_STATES + (APPLY_FAILED,)
FAILED_RETRIES = 0  # times a finding recorded apply-failed is applied again: never
FIX_KINDS = ("alias", "expansion")
ALIAS_CANDIDATES = 3  # canonical words tried per alias finding: the article's file-name words, then its title's
EXPANSION_CANDIDATES = 3  # facts of the article tried per expansion finding, most words shared with the question first


class Gate:
    """pack and the kb gates on the working tree of this clone: `rag.py eval`, the off-kb verdicts, the pack size."""

    @staticmethod
    def fresh():
        import kbfacts
        kbfacts._FP[:] = [0.0, None]  # a file was just written: the next call fingerprints the kb again

    def pack(self, question):
        import kbfacts
        self.fresh()
        return kbfacts.pack(question, fmt="concise")

    def measure(self):
        """{n, passed, failed, chars {eval id: pack characters}, offkb_good} on the working tree."""
        import kbcommon, kbfacts, rag
        self.fresh()
        res = rag.run_eval()
        good = 0
        for r in kbcommon.roots():
            p = Path(r.path) / kbcommon.DATA_DIR / "doc2query" / "offkb_questions.txt"
            if p.is_file():
                qs = [q for q in p.read_text(encoding="utf-8").splitlines() if q.strip()]
                good += sum(kbfacts.pack(q, fmt="concise")["verdict"] == "good" for q in qs)
        return {"n": res["n"], "passed": res["passed"], "failed": [r["id"] for r in res["rows"] if not r["ok"]],
                "chars": {r["id"]: r["chars"] for r in res["rows"]}, "offkb_good": good}

    def targets(self, article):
        """The files a fix for `article` writes: its root's eval set and expansions, and the aliases (the shared
        _tools/aliases.csv for the public root, a root's own _retrieval/aliases.csv otherwise)."""
        import kbcommon, kbfacts
        r = kbcommon.root(kbfacts.root_name(article) or kbcommon.public().name)
        data = Path(r.path) / kbcommon.DATA_DIR
        return {"root": r.name, "eval": data / "lookup_eval.csv", "expansions": data / "doc2query" / "expansions.csv",
                "aliases": Path(kbfacts.ALIASES) if r.name == kbcommon.public().name else data / "aliases.csv"}

    def alias_terms(self):
        """{term: canonical} of every alias file."""
        import csv, kbfacts
        out = {}
        for p in kbfacts.alias_files():
            with open(p, encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    t = " ".join((row.get("term") or "").lower().split())
                    if t:
                        out.setdefault(t, (row.get("canonical") or "").strip().lower())
        return out

    def facts(self, article):
        """[(line, text)] of the tagged facts of `article`."""
        import kbfacts
        return [(u["line"], u["text"]) for u in kbfacts.units(article) if u["path"] == article and u["tags"]]

    def title(self, article):
        import kbfacts
        return (kbfacts.articles().get(article) or {}).get("title", "")

    def article_of(self, path):
        """The qualified article (.md) whose topic holds the qualified `path` (the article itself, a same-stem data
        file or a file its `files:` lists), or None."""
        import kbfacts
        arts = kbfacts.articles()
        if path in arts:
            return path
        for topic, files in sorted(kbfacts.topic_files().items()):
            if path in files:
                return next((q for q in files if q in arts and arts[q].get("topic") == topic), None)
        return None

    def topic(self, article):
        """The topic of a qualified article, as its root's ledgers name it: `<domain>/<slug>`."""
        import kbfacts
        return kbfacts.bare((kbfacts.articles().get(article) or {}).get("topic") or article[:-3])

    def root(self, article):
        import kbcommon, kbfacts
        return kbcommon.root(kbfacts.root_name(article) or kbcommon.public().name)

    def ledger(self, article, name):
        """A file of the article's root: `_gaps.md`, `_conflicts.md`, `_sources.csv`."""
        return Path(self.root(article).path) / name

    def file(self, article):
        import kbcommon
        return Path(kbcommon.path_of(article))

    def id_prefix(self, article):
        return self.root(article).id_prefix

    def research_files(self, article):
        """Every file research may write for `article`, so a failed gate can put each back: the article, its root's
        sources, conflicts and the coverage files build_index regenerates."""
        return [self.file(article)] + [self.ledger(article, n) for n in ("_sources.csv", "_conflicts.md",
                                                                          "_coverage.csv", "_coverage.md")]

    def index_and_check(self):
        """build_index.py, then check.py over every root: the ERROR lines when check.py does not end errors=0."""
        tools = HOME / "_tools"
        code, o, e = run_cmd([sys.executable, str(tools / "build_index.py")], cwd=HOME)
        if code:
            return [one_line(f"build_index.py exit {code}: {(o + e).strip()[-200:]}", 240)]
        code, o, e = run_cmd([sys.executable, str(tools / "check.py")], cwd=HOME)
        m = re.search(r"errors=(\d+)", o)
        if code == 0 and m and m.group(1) == "0":
            return []
        errs = [one_line(ln, 200) for ln in o.splitlines() if ln.startswith("ERROR")]
        return errs[:6] or [one_line(f"check.py exit {code}: {(o + e).strip()[-200:]}", 240)]


CSV_HEADERS = {"eval": ["id", "question", "expect_paths", "expect_verdict", "allow_weak"],
               "aliases": ["term", "canonical"], "expansions": ["key", "question"]}


def csv_rows(path):
    import csv
    if not Path(path).is_file():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.reader(f))[1:]


def append_rows(path, which, rows):
    """Append `rows` to the CSV at `path` (its header first when the file is new); the file's bytes before, or None."""
    import kbcommon
    path = Path(path)
    old = path.read_bytes() if path.is_file() else None
    text = old.decode("utf-8") if old is not None else kbcommon.rows_text([CSV_HEADERS[which]])
    if text and not text.endswith("\n"):
        text += "\n"
    write_text(path, text + kbcommon.rows_text(rows))
    return old


def restore(saved):
    """Put back the files `append_rows` changed: their bytes before, or no file."""
    for path, old in saved.items():
        if old is None:
            Path(path).unlink(missing_ok=True)
        else:
            Path(path).write_bytes(old)


def alias_problems(terms, canonical, existing, unknown):
    """Why aliasing `terms` to `canonical` collides with an existing term: a term already in an alias file, or a
    word the kb holds (not among the question's `unknown` words); and a canonical word another product owns."""
    out = []
    for t in terms:
        if t in existing:
            out.append(f"alias {t}: already a term of {existing[t]}")
        elif t not in unknown:
            out.append(f"alias {t}: a word the kb holds")
    if existing.get(canonical, canonical) != canonical:
        out.append(f"alias {canonical}: a term of {existing[canonical]}")
    return out


def alias_fixes(finding, entry, gate, res):
    """[(rows by file, problems)] per candidate canonical word: the words of the article's file name, then of its
    title, each mapped to its alias group when it is a term of one, else a new group of its own."""
    import kbfacts
    article = finding["article"]
    existing = gate.alias_terms()
    unknown = unknown_words(entry["question"], res)
    stem = Path(kbfacts.bare(article)).stem
    words = []
    for w in kbfacts.WORD.findall(stem.replace("-", " ") + " " + gate.title(article)):
        w = w.lower()
        c = existing.get(w, w)
        if w not in kbfacts.STOP and len(w) > 2 and not w.isdigit() and c not in words:
            words.append(c)
    out = []
    for c in words[:ALIAS_CANDIDATES]:
        rows = [[t, c] for t in finding.get("terms") or []]
        if c not in existing:
            rows.append([c, c])
        out.append(({"aliases": rows}, alias_problems(finding.get("terms") or [], c, existing, unknown)))
    return out


def expansion_fixes(finding, entry, gate):
    """[(rows by file, [])] per candidate fact: the article's facts sharing the most words with the question."""
    import kbfacts
    q = set(kbfacts.terms(entry["question"]))
    facts = sorted(gate.facts(finding["article"]), key=lambda f: (-len(q & set(kbfacts.terms(f[1]))), f[0]))
    return [({"expansions": [[kbfacts.fact_key(text), entry["question"]]]}, [])
            for _, text in facts[:EXPANSION_CANDIDATES]]


def try_fix(fix, eval_row, targets, gate, base):
    """Write the fix and the eval row, then hold the kb gates against `base`: every eval question passes, the pack of
    the questions `base` measured does not grow on average, off-kb `good` does not rise. (ok, problems); the files
    are put back unless ok."""
    saved = {}
    for which, rows in [*fix.items(), ("eval", [eval_row])]:
        have = {tuple(r) for r in csv_rows(targets[which])}
        rows = [r for r in rows if tuple(r) not in have]
        if rows:
            p = targets[which]
            old = append_rows(p, which, rows)
            saved.setdefault(p, old)
    m = gate.measure()
    problems = []
    if m["passed"] != m["n"]:
        problems.append(f"eval fails: {', '.join(m['failed'][:3])}")
    ids = [i for i in base["chars"] if i in m["chars"]]
    before = sum(base["chars"][i] for i in ids) / max(len(ids), 1)
    after = sum(m["chars"][i] for i in ids) / max(len(ids), 1)
    if after > before:
        problems.append(f"mean pack grows: {before:.0f} -> {after:.0f} characters")
    if m["offkb_good"] > base["offkb_good"]:
        problems.append(f"off-kb good rises: {base['offkb_good']} -> {m['offkb_good']}")
    if problems:
        restore(saved)
        gate.fresh()
    return not problems, problems


def apply_one(ev, fix, entry, gate, base):
    """The records of one open eval finding and its fix finding (or None): the eval row with the first candidate fix
    that passes the gates (both `applied`), else the miss promoted to a gap candidate (`no-fix`) and its fix
    `rejected`. [] when the question passes on the working tree already (learn records that)."""
    import kbid
    question, article = entry["question"], ev["expect"]
    res = gate.pack(question)
    if passes(res, article):
        return []
    targets = gate.targets(article)
    bare_path = article.split("/", 1)[1] if article.startswith(targets["root"] + "/") else article
    eid = kbid.eval_id(question)
    taken = {r[0]: r[1] for r in csv_rows(targets["eval"]) if len(r) > 1}
    problems = []
    if eid in taken and taken[eid] != question:
        problems.append(f"eval id {eid} is taken by another question")
    elif fix is None:
        problems.append("no fix finding")
    else:
        cands = alias_fixes(fix, entry, gate, res) if fix["kind"] == "alias" else expansion_fixes(fix, entry, gate)
        if not cands:
            problems.append(f"no candidate {fix['kind']}")
        row = [eid, question, bare_path, "good", ""]
        for rows, why in cands:
            if why:
                problems += why
                continue
            ok, why = try_fix(rows, row, targets, gate, base)
            if ok:
                done = {k: v for k, v in ev.items() if k != "observed"}
                return [{**done, "state": "applied", "observed": {"eval": eid}},
                        {**{k: v for k, v in fix.items() if k != "observed"}, "state": "applied",
                         "observed": {"rows": sum(len(v) for v in rows.values())}}]
            problems += why
    miss = {k: v for k, v in ev.items() if k != "observed"}
    promoted = {**miss, "state": "no-fix", "stage": "candidate-gap",
                "promotions": [*(ev.get("promotions") or []), {"from": ev.get("stage", "miss"), "to": "candidate-gap",
                                                               "by": "apply"}],
                "observed": {"gate": sorted(set(problems))[:6]}}
    out = [promoted]
    if fix is not None:
        out.append({**{k: v for k, v in fix.items() if k != "observed"}, "state": "rejected",
                    "observed": {"gate": sorted(set(problems))[:6]}})
    return out


def failed_counts(store):
    """{finding id: how many apply-failed records it has} across the store's findings files."""
    out = {}
    for p in findings_files(store):
        try:
            objs = load_run(p)
        except (OSError, ValueError):
            continue
        for _, rec in objs[1:]:
            if rec.get("state") == APPLY_FAILED and isinstance(rec.get("id"), str):
                out[rec["id"]] = out.get(rec["id"], 0) + 1
    return out


def apply(store=None, gate=None, kb_commit=None, out=print, hold=(), research=None, day=None):
    """One apply over `store` (default: the local store beside the spool), in the working tree of this clone: every
    open eval finding with its open fix finding, in id order; then the gap step (each open gap candidate whose miss
    reproduces under an article becomes a _gaps.md entry under that article's topic); then, when `research` (a
    Researcher) has runs left, research on the gap findings; then one findings file with each outcome. Source findings
    are left as they are, and so are the findings in `hold` (pending on a conflict branch) and those recorded
    apply-failed more than FAILED_RETRIES times, even when a later record opens them again. 0; 1 when `rag.py eval`
    fails before an eval change."""
    store = Path(store or places()[0] / "store")
    gate = gate or Gate()
    day = day or datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    entries = store_entries(store)
    by_entry = {e["id"]: e for _, e in entries}
    last = finding_states(store)
    failed = failed_counts(store)

    def actionable(r):
        return r["id"] not in hold and failed.get(r["id"], 0) <= FAILED_RETRIES

    def entry_of(r):
        e = by_entry.get(r.get("entry"))
        return e if e and isinstance(e.get("question"), str) else None

    evals = sorted((r for r in last.values() if r.get("kind") == "eval" and r.get("state") == "open"
                    and actionable(r)), key=lambda r: r["id"])
    gaps = sorted((r for r in last.values() if r.get("kind") == "gap" and r.get("state") == "open"
                   and r.get("stage") == "candidate-gap" and actionable(r)), key=lambda r: r["id"])
    new, base = [], None
    if evals:
        base = gate.measure()
        if base["passed"] != base["n"]:
            out(f"apply: rag.py eval fails before any change ({base['passed']} of {base['n']} pass); nothing applied")
            return 1
        fixes = {r["entry"]: r for r in last.values() if r.get("kind") in FIX_KINDS and r.get("state") == "open"
                 and actionable(r)}
        for ev in evals:
            entry = entry_of(ev)
            if entry:
                new += apply_one(ev, fixes.get(ev["entry"]), entry, gate, base)
    for g in gaps:
        entry = entry_of(g)
        if entry:
            new += gap_one(g, entry, gate, day)
    runs = {"runs": 0, "facts": 0, "conflicts": 0}
    if research is not None and research.left():
        now = {**last, **{r["id"]: r for r in new}}
        todo = sorted((r for r in now.values() if r.get("kind") == "gap" and r.get("stage") == "gap"
                       and r.get("state") == "applied" and actionable(r) and entry_of(r)), key=lambda r: r["id"])
        for g in todo:
            if not research.left():
                break
            rec = research_one(g, entry_of(g), gate, research, day)
            runs["runs"] += 1
            if rec is not None:
                new = [r for r in new if r["id"] != rec["id"]] + [rec]
                runs["facts"] += (rec.get("observed") or {}).get("facts", 0)
                runs["conflicts"] += (rec.get("observed") or {}).get("conflicts", 0)
    if not new:
        out("apply: nothing to apply" + (f" (research runs={runs['runs']}, no reply)" if runs["runs"] else ""))
        return 0
    run_id, counts = write_findings(store, entries, new, APPLY_STATES, kb_commit)
    said = f"apply: run={run_id} records={len(new)} " + " ".join(f"{s}={n}" for s, n in counts.items())
    if base is not None and any(r["kind"] in FIX_KINDS and r["state"] == "applied" for r in new):
        m = gate.measure()
        ids = [i for i in base["chars"] if i in m["chars"]]
        mean = [round(sum(d["chars"][i] for i in ids) / max(len(ids), 1)) for d in (base, m)]
        said += (f" eval={m['passed']}/{m['n']} mean-pack={mean[0]}->{mean[1]} "
                 f"offkb-good={base['offkb_good']}->{m['offkb_good']}")
    n_gaps = sum(1 for r in new if r["kind"] == "gap" and any(p.get("to") == "gap" and p.get("by") == "apply"
                                                              for p in r.get("promotions") or []))
    if n_gaps:
        said += f" gaps={n_gaps}"
    if runs["runs"]:
        said += f" research={runs['runs']} facts={runs['facts']} conflicts={runs['conflicts']}"
    out(said)
    return 0


# --- the gap step: a reproduced gap candidate under an article -> a _gaps.md entry (querylog.md, Learn and apply) --

def one_line(s, n=300):
    return " ".join(str(s).split())[:n]


def add_under(text, heading, line):
    """`text` with `line` added at the end of the section `## <heading>` (the last one of that name), or in a new
    section at the end. Existing lines are never changed or moved."""
    lines = text.split("\n") if text else []
    while lines and not lines[-1].strip():
        lines.pop()
    head = f"## {heading}"
    at = max((i for i, ln in enumerate(lines) if ln.rstrip() == head), default=None)
    if at is None:
        lines += ([""] if lines else []) + [head, "", line]
    else:
        end = next((i for i in range(at + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        while end - 1 > at and not lines[end - 1].strip():
            end -= 1
        lines[end:end] = ["", line] if end - 1 == at else [line]
    return "\n".join(lines) + "\n"


def gap_one(g, entry, gate, day):
    """The record of one open gap candidate (kind gap, stage candidate-gap), re-run with pack on the working tree: it
    reproduces when it still fails (`passes` without a best article), and it lies in a kb domain when the pack's lead
    path belongs to an article (a `none` verdict is off the kb's domains). Then a _gaps.md entry under the article's
    topic, in the article's root, dated `day`, and the finding promoted from candidate-gap to gap (`applied`). []
    when it passes now (learn records that) or lies outside the kb's domains (it stays a candidate)."""
    res = gate.pack(entry["question"])
    if passes(res, None) or res.get("verdict") == "none" or not res.get("paths"):
        return []
    article = gate.article_of(res["paths"][0])
    if not article:
        return []
    topic = gate.topic(article)
    path = gate.ledger(article, "_gaps.md")
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    if g["id"] not in text:
        write_text(path, add_under(text, topic, (
            f"- **{one_line(entry['question']).replace('**', '')}** A logged lookup of {entry.get('day', day)} found "
            f"no article that answers it (query log finding {g['id']}). Looked in the kb {day}: `rag.py pack` gives "
            f"`{res.get('verdict')}`, with this topic in the lead. Needs an official source that states it "
            f"(`/kb-research`, or the query log's opt-in research). (topic: {topic})")))
    keep = {k: v for k, v in g.items() if k != "observed"}
    return [{**keep, "state": "applied", "stage": "gap", "article": article,
             "promotions": [*(g.get("promotions") or []), {"from": "candidate-gap", "to": "gap", "by": "apply"}],
             "observed": {"verdict": res.get("verdict"), "topic": topic}}]


# --- quotecheck: a candidate fact's quote on its page, fetched the way the kb fetches (fetch.py) ------------------

QUOTE_MAX_WORDS = 25  # the longest quote the kb's rules allow (kbcommon.QUOTE_WORDS, kb/_self/content-rules.md)
QUOTE_MIN_WORDS = 5  # a shorter quote is found on almost any page and backs nothing
QUOTE_CHARS = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-",
                             "\xa0": " ", "​": ""})
MD_LINK = re.compile(r"!\[[^\]]*\]\([^)]*\)|\[([^\]]*)\]\([^)]*\)")


def quote_norm(s):
    """Text as the quote check compares it: entities decoded, Markdown links and emphasis marks gone, NFKC, straight
    quotes and dashes, lower case, single spaces."""
    import html, unicodedata
    s = html.unescape(html.unescape(s))
    s = MD_LINK.sub(lambda m: m.group(1) or "", s)
    s = unicodedata.normalize("NFKC", s).translate(QUOTE_CHARS)
    s = re.sub(r"[*_`]+", "", s)
    return " ".join(s.split()).lower()


def page_fetch(url):
    """(bytes, content type) of a page, as fetch.py fetches it (one request per host per fetch.DELAY, a spool row)."""
    import fetch
    return fetch.fetch(url)


def quotecheck(url, quote, fetcher=None):
    """(ok, why): whether `quote` (QUOTE_MIN_WORDS to QUOTE_MAX_WORDS words) is on the page at `url`, fetched by
    `fetcher` (default: fetch.py's fetch) and reduced to text by fetch.py's to_text; both sides normalized by
    quote_norm."""
    quote = str(quote or "").strip().strip("\"'“”").strip()
    n = len(quote.split())
    if n > QUOTE_MAX_WORDS:
        return False, f"quote has {n} words, over {QUOTE_MAX_WORDS}"
    if n < QUOTE_MIN_WORDS:
        return False, f"quote has {n} words, under {QUOTE_MIN_WORDS}"
    try:
        body, ctype = (fetcher or page_fetch)(url)
    except Exception as e:  # noqa: BLE001 - any failure to read the page rejects the quote
        return False, one_line(f"page not fetched: {type(e).__name__}: {e}", 160)
    import fetch
    text = fetch.to_text(body, ctype)
    if text is None:
        return False, "page is not text"
    want = quote_norm(quote).rstrip(" .,;:")
    if want and want in quote_norm(text):
        return True, "quote is on the page"
    return False, "quote is not on the page"


# --- research: opt-in per user, add-only, quote-checked (querylog.md, Learn and apply) ------------------------------

RESEARCH_MODEL = "sonnet"
RESEARCH_TIMEOUT_S = 600
RESEARCH_RUNS_PER_APPLY = 2  # research runs in one apply, whatever the daily cap leaves: bounds LOCK_STALE_S
RESEARCH_FACTS_MAX = 5  # candidate facts read from one research reply
RESEARCH_RUNS_NAME = "research-runs.json"  # {"day", "runs"}: the research runs this user started today
RESEARCH_TOOLS = ("WebSearch", "WebFetch")
RESEARCH_MCP_TOOLS = ("mcp__microsoft-learn__microsoft_docs_search", "mcp__microsoft-learn__microsoft_docs_fetch",
                      "mcp__claude-code-docs__search_claude_code_docs",
                      "mcp__claude-code-docs__query_docs_filesystem_claude_code_docs",
                      "mcp__mcp-docs__search_model_context_protocol",
                      "mcp__mcp-docs__query_docs_filesystem_model_context_protocol")
RESEARCH_TAGS = ("DOC", "COMMUNITY")
RESEARCH_FIELDS = ("text", "tag", "url", "title", "publisher", "licence", "reuse", "quote")
PROMOTERS = ("learn", "apply", "research")
RESEARCH_TASK = (
    "You research one question for an IT knowledge base whose lookup found no answer. Read official documentation "
    "(the vendor's own docs, release notes, API reference or repository) with the tools you have; blogs and forums "
    "only as COMMUNITY. For each fact the question needs, give: `text`, the fact in your own words, one sentence, "
    "no citation; `tag`: \"DOC\" for an official page, \"COMMUNITY\" otherwise; `url`, the page where the sentence is "
    "(not a page linking to it); `title`, `publisher`; `licence`, the page's licence or terms in words and where they "
    "are stated; `reuse`: \"copy\" (an open licence), \"quote\" (terms of use, no reuse licence), \"paraphrase\" (the "
    "terms forbid copying) or \"unknown\"; `quote`, 5 to 25 words copied verbatim from that page that state the "
    "fact; `conflicts_with`: the line number of an existing fact below that the page contradicts, else null. Never "
    "restate an existing fact. Use placeholders, never real hosts, tenants or people. Reply with only JSON: "
    '{"facts": [{"text": "...", "tag": "DOC", "url": "https://...", "title": "...", "publisher": "...", '
    '"licence": "...", "reuse": "quote", "quote": "...", "conflicts_with": null}]}; at most %d facts; '
    '{"facts": []} when no official page answers it.' % RESEARCH_FACTS_MAX)


def research_places(clone=None):
    """(querylog directory, config file) whose research setting and daily count apply: a clone's own
    _cache/querylog and _private/querylog.json when `clone` names one (apply --push names its clone), else places()."""
    if clone:
        return Path(clone) / "_cache" / "querylog", Path(clone) / "_private" / "querylog.json"
    return places()


def research_used(qdir, day):
    data = read_json(Path(qdir) / RESEARCH_RUNS_NAME, {})
    runs = data.get("runs") if isinstance(data, dict) and data.get("day") == day else 0
    return runs if isinstance(runs, int) and not isinstance(runs, bool) and runs > 0 else 0


def count_research(qdir, day):
    """One more research run today in the user's count."""
    write_text(Path(qdir) / RESEARCH_RUNS_NAME, json.dumps({"day": day, "runs": research_used(qdir, day) + 1}) + "\n")


def research_budget(qdir, cfg, day):
    """The research runs left today: 0 unless the config file turns research on (read_research) and logging is on
    (not mode off, no DISABLED marker); else its daily cap less the runs counted today."""
    on, daily = read_research(cfg)
    if not on or read_mode(cfg) == "off" or (Path(qdir) / "DISABLED").exists():
        return 0
    return max(0, daily - research_used(qdir, day))


def research_argv(model=RESEARCH_MODEL):
    """The `claude -p` argument list of one research run: hooks off (the pipeline never logs itself), no user plugins
    or MCP servers but the kb's three documentation servers, web search and fetch as the only built-in tools, nothing
    else allowed. The prompt goes on stdin."""
    import shutil
    docs = HOME / ".claude-plugin" / "it-ops-kb-docs" / ".mcp.json"
    return [shutil.which("claude") or "claude", "-p", "--model", model, "--no-session-persistence", *NO_HOOKS,
            "--setting-sources", "project,local", "--strict-mcp-config", "--mcp-config", str(docs),
            "--tools", ",".join(RESEARCH_TOOLS), "--permission-mode", "dontAsk",
            "--allowedTools", *RESEARCH_TOOLS, *RESEARCH_MCP_TOOLS]


def claude_research(prompt):
    """One research run: research_argv in an empty directory (no project instructions load). OSError when it cannot
    answer."""
    with tempfile.TemporaryDirectory() as d:
        try:
            p = subprocess.run(research_argv(), input=prompt, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=RESEARCH_TIMEOUT_S, cwd=d)
        except subprocess.TimeoutExpired as e:
            raise OSError(f"claude -p gave no reply in {RESEARCH_TIMEOUT_S} s") from e
    if p.returncode:
        raise OSError(f"claude -p exited {p.returncode}")
    return p.stdout


class ResearchReplay:
    """Recorded research replies and pages: {"replies": [text, ...], "pages": {url: file relative to this file}}.
    Replies are answered in order (OSError once they run out); a url with no recorded page raises OSError."""

    def __init__(self, path):
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.replies, self.prompts = list(data.get("replies") or []), []
        self.pages = {u: path.parent / f for u, f in (data.get("pages") or {}).items()}

    def __call__(self, prompt):
        self.prompts.append(prompt)
        if not self.replies:
            raise OSError("no recorded reply left")
        return self.replies.pop(0)

    def fetch(self, url):
        p = self.pages.get(url)
        if p is None:
            raise OSError(f"no recorded page for {url}")
        ctype = {".html": "text/html; charset=utf-8", ".md": "text/markdown"}.get(p.suffix, "text/plain")
        return p.read_bytes(), ctype


class Researcher:
    """The research step of one apply: `runs` left (the user's daily cap less today's count), the model `call`
    (default claude_research), the page `fetcher` for the quote check (default fetch.py's fetch) and `counted`, called
    once per run started (it adds the run to the user's count)."""

    def __init__(self, runs, call=None, fetcher=None, counted=None):
        self.runs, self.call, self.fetcher = runs, call or claude_research, fetcher
        self.counted = counted or (lambda: None)

    def left(self):
        return self.runs > 0

    def ask(self, prompt):
        self.runs -= 1
        self.counted()
        return self.call(prompt)


def fact_lines(text):
    """[(line number, line)] of the tagged fact lines of an article's body (bullets and table rows with a tag)."""
    import kbfacts
    lines = text.split("\n")
    start = 0
    if lines and lines[0] == "---":
        start = next((i + 1 for i in range(1, len(lines)) if lines[i] == "---"), 0)
    return [(n, ln) for n, ln in enumerate(lines, 1) if n > start and ln.lstrip().startswith(("- ", "* ", "|"))
            and kbfacts.TAG.search(ln)]


def research_prompt(question, topic, facts):
    listed = "\n".join(f"{n}: {one_line(ln, 400)}" for n, ln in facts[:200])
    return (f"{RESEARCH_TASK}\n\nQuestion: {one_line(question, QUESTION_MAX_CHARS)}\nTopic: {topic}\n\n"
            f"Existing facts (line: text):\n{listed or '(none)'}")


def parse_research(reply):
    """[candidate dict] of a research reply, at most RESEARCH_FACTS_MAX; ValueError when it is not that JSON."""
    a, b = reply.find("{"), reply.rfind("}")
    if a < 0 or b < a:
        raise ValueError("no JSON object in the reply")
    data = json.loads(reply[a:b + 1])
    facts = data.get("facts") if isinstance(data, dict) else None
    if not isinstance(facts, list):
        raise ValueError("no facts list")
    for i, c in enumerate(facts[:RESEARCH_FACTS_MAX]):
        cw = c.get("conflicts_with") if isinstance(c, dict) else None
        if not isinstance(c, dict) or not all(isinstance(c.get(f), str) for f in RESEARCH_FIELDS) \
                or not (cw is None or (isinstance(cw, int) and not isinstance(cw, bool))):
            raise ValueError(f"fact {i} is malformed")
    return facts[:RESEARCH_FACTS_MAX]


def candidate_problems(c, facts):
    """Why a candidate fact cannot be written, before its quote is checked: its text (one sentence of our own, no
    tag, nothing the leak scan flags, not already a fact), tag, url (http(s), a public DNS name), source fields and
    reuse class, and a `conflicts_with` that names a fact line."""
    import kbcommon, kbfacts
    out = []
    text = one_line(c["text"], 10_000)
    if not 20 <= len(text) <= 600:
        out.append("text is not one short sentence")
    if kbfacts.TAG.search(text) or "topic:" in text or "\n" in c["text"].strip():
        out.append("text carries a tag, a topic marker or a line break")
    if kbcommon.leak_hits(text + " " + c["url"]):
        out.append("text or url holds what the leak scan flags")
    if c["tag"] not in RESEARCH_TAGS:
        out.append(f"tag {one_line(c['tag'], 20)!r} is not one of {', '.join(RESEARCH_TAGS)}")
    u = urlsplit(c["url"].strip())
    host = (u.hostname or "").lower()
    if u.scheme not in ("http", "https") or u.username or not HOSTNAME.fullmatch(host) \
            or host.rsplit(".", 1)[-1] in PRIVATE_TLDS:
        out.append("url is not a public http(s) page")
    if c["reuse"] not in kbcommon.REUSE:
        out.append(f"reuse {one_line(c['reuse'], 20)!r} is not a reuse class")
    if not all(one_line(c[f]) for f in ("title", "publisher", "licence")):
        out.append("title, publisher or licence is empty")
    if any(one_line(ln, 10_000).lower().lstrip("-* ").startswith(text.lower()) for _, ln in facts):
        out.append("text is already a fact")
    cw = c.get("conflicts_with")
    if cw is not None and cw not in {n for n, _ in facts}:
        out.append(f"conflicts_with {cw} names no fact line")
    return out


def edit_problems(rel, old, new):
    """The existing lines a change to the kb file `rel` removes or edits, from `old` to `new` text: an article's fact
    lines, a ledger's lines, a source row other than its generated `used_in`. The gap step and research add only."""
    import collections, csv, io
    if old is None:
        return []
    name = rel.replace("\\", "/").rsplit("/", 1)[-1]
    if name == "_sources.csv":
        def rows(t):
            return {r.get("id"): {k: v for k, v in r.items() if k != "used_in"} for r in csv.DictReader(io.StringIO(t))}
        now = rows(new or "")
        return [f"{rel}: changes source row {sid}" for sid, r in rows(old).items() if now.get(sid) != r][:6]
    if name in ("_gaps.md", "_conflicts.md"):
        keep, what = [ln for ln in old.split("\n") if ln.strip()], "an existing entry line"
    elif name.endswith(".md") and not name.startswith("_"):
        keep, what = [ln for _, ln in fact_lines(old)], "an existing fact line"
    else:
        return []
    lost = collections.Counter(keep) - collections.Counter((new or "").split("\n"))
    return [f"{rel}: removes or edits {what}: {one_line(ln, 80)}" for ln in list(lost.elements())[:6]]


def add_fact(text, line):
    """An article's text with the fact `line` added at the end of its Facts section; ValueError without one."""
    lines = text.split("\n")
    at = next((i for i, ln in enumerate(lines) if ln.rstrip() == "## Facts"), None)
    if at is None:
        raise ValueError("the article has no Facts section")
    end = next((i for i in range(at + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    while end - 1 > at and not lines[end - 1].strip():
        end -= 1
    prev = lines[end - 1]
    bullet = prev.lstrip().startswith(("- ", "* ")) or (prev[:1] == " " and prev.strip())
    lines[end:end] = [line] if bullet else ["", line]
    return "\n".join(lines)


def add_header_source(text, sid):
    """An article's text with `sid` in its front matter `sources: [...]` list (unchanged when it is there or the list
    is not written inline)."""
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        return text
    head = m.group(1)
    s = re.search(r"(?m)^sources:\s*\[(.*)\]\s*$", head)
    if not s or sid in [x.strip() for x in s.group(1).split(",")]:
        return text
    items = [x.strip() for x in s.group(1).split(",") if x.strip()] + [sid]
    head = head[:s.start()] + f"sources: [{', '.join(items)}]" + head[s.end():]
    return "---\n" + head + "\n---\n" + text[m.end():]


def write_research(g, article, accepted, conflicts, gate, day):
    """Add the accepted facts at the end of the article's Facts section (their ids in its `sources:` header), a
    _conflicts.md entry under the topic per conflict, and a source row per new url (id from kbid.source_id with the
    root's prefix, `retrieved_utc` today). [source ids]; ValueError when the article cannot take a fact."""
    import csv, io, kbfacts, kbid
    src = gate.ledger(article, "_sources.csv")
    old = src.read_text(encoding="utf-8") if src.is_file() else ""
    reader = csv.DictReader(io.StringIO(old))
    by_url = {kbid.normalize_url(r.get("url") or ""): r.get("id") for r in reader}
    fields = list(reader.fieldnames or [])
    prefix, add, ids = gate.id_prefix(article), [], []
    for c in accepted + conflicts:
        url = c["url"].strip()
        sid = by_url.get(kbid.normalize_url(url))
        if not sid:
            sid = by_url[kbid.normalize_url(url)] = kbid.source_id(url, prefix)
            add.append({**{f: "" for f in fields}, "id": sid, "url": url, "title": one_line(c["title"], 200),
                        "publisher": one_line(c["publisher"], 120), "licence": one_line(c["licence"], 300),
                        "reuse": c["reuse"], "retrieved_utc": day})
        c["sid"] = sid
        ids.append(sid)
    path = gate.file(article)
    text = path.read_text(encoding="utf-8")
    facts = dict(fact_lines(text))
    for c in accepted:
        text = add_header_source(add_fact(text, f"- {one_line(c['text'], 600)} [{c['tag']} {c['sid']}]"), c["sid"])
    topic = gate.topic(article)
    ledger = gate.ledger(article, "_conflicts.md")
    ltext = ledger.read_text(encoding="utf-8") if ledger.is_file() else ""
    for c in conflicts:
        was = facts[c["conflicts_with"]]
        old_ids = sorted({i for t in kbfacts.TAG.findall(was) for i in kbfacts.ID.findall(t) if i != c["sid"]})
        body = one_line(kbfacts.TAG.sub("", was).strip().lstrip("-*| ").rstrip(" |"), 240)
        vs = f" vs {', '.join(old_ids)}" if old_ids else ""
        ltext = add_under(ltext, topic, (
            f"- **{body}** (line {c['conflicts_with']} of the article) and {c['url'].strip()} disagree: that page backs "
            f"\"{one_line(c['text'], 400)}\". Found by the query log's research {day} (finding {g['id']}); not settled. "
            f"[{c['tag']} {c['sid']}{vs}] (topic: {topic})"))
    if add:
        buf = io.StringIO()
        csv.DictWriter(buf, fieldnames=fields, lineterminator="\n").writerows(add)
        write_text(src, old + ("\n" if old and not old.endswith("\n") else "") + buf.getvalue())
    if accepted:
        write_text(path, text)
    if conflicts:
        write_text(ledger, ltext)
    return sorted(set(ids))


def research_one(g, entry, gate, research, day):
    """One research run on a gap finding (stage gap): the model's candidate facts (the finding promoted to
    candidate-fact), each checked (candidate_problems, then quotecheck on its page), the accepted ones written
    (write_research), then the gates: no existing fact, entry or source line edited (edit_problems), build_index and
    check.py with errors=0, no eval question newly failing and off-kb `good` not rising. A fact written promotes the
    finding to claim (`applied`); conflicts only leave it at candidate-fact (`applied`); nothing accepted, a reply
    that is not the expected JSON, or a failed gate is `rejected` with the reasons, and every file is put back. None
    when the call itself fails (no record: a later run tries again)."""
    article = g["article"]
    path = gate.file(article)
    facts = fact_lines(path.read_text(encoding="utf-8") if path.is_file() else "")
    keep = {k: v for k, v in g.items() if k != "observed"}
    promos = list(g.get("promotions") or [])
    try:
        reply = research.ask(research_prompt(entry["question"], gate.topic(article), facts))
    except OSError:
        return None

    def record(state, stage, observed, more=()):
        return {**keep, "state": state, "stage": stage, "promotions": promos + list(more), "observed": observed}
    try:
        cands = parse_research(reply)
    except ValueError as e:
        return record("rejected", "gap", {"gate": [one_line(f"reply: {e}", 160)]})
    to_fact = [{"from": "gap", "to": "candidate-fact", "by": "research"}]
    accepted, conflicts, problems = [], [], []
    for i, c in enumerate(cands):
        why = candidate_problems(c, facts)
        if not why:
            ok, said = quotecheck(c["url"], c["quote"], research.fetcher)
            why = [] if ok else [said]
        if why:
            problems += [f"fact {i}: {w}" for w in why]
        else:
            (conflicts if c.get("conflicts_with") is not None else accepted).append(c)
    if not accepted and not conflicts:
        return record("rejected", "candidate-fact", {"candidates": len(cands),
                                                     "gate": problems[:6] or ["no candidate fact"]}, to_fact)
    files = gate.research_files(article)
    saved = {p: (p.read_bytes() if p.is_file() else None) for p in files}
    base = gate.measure()
    try:
        ids = write_research(g, article, accepted, conflicts, gate, day)
    except ValueError as e:
        restore(saved)
        gate.fresh()
        return record("rejected", "candidate-fact", {"gate": [str(e)]}, to_fact)
    gate.fresh()
    after = []
    for p in files:
        old = saved[p]
        after += edit_problems(p.name, None if old is None else old.decode("utf-8"),
                               p.read_text(encoding="utf-8") if p.is_file() else "")
    if not after:
        after += gate.index_and_check()
    if not after:
        m = gate.measure()
        newly = [i for i in m["failed"] if i not in base["failed"]]
        if newly:
            after.append(f"eval fails: {', '.join(newly[:3])}")
        if m["offkb_good"] > base["offkb_good"]:
            after.append(f"off-kb good rises: {base['offkb_good']} -> {m['offkb_good']}")
    if after:
        restore(saved)
        gate.fresh()
        return record("rejected", "candidate-fact", {"gate": after[:6]}, to_fact)
    observed = {"facts": len(accepted), "conflicts": len(conflicts), "sources": ids}
    if problems:
        observed["gate"] = problems[:6]
    if accepted:
        return record("applied", "claim", observed,
                      to_fact + [{"from": "candidate-fact", "to": "claim", "by": "research"}])
    return record("applied", "candidate-fact", observed, to_fact)


# --- apply --push: the gate, a rebase on origin/main, the push to origin only (querylog.md, Delivery) ----------------

REMOTE, BRANCH = "origin", "main"  # the repository the clone came from, and the branch automatic commits land on
CONFLICT_BRANCH_PREFIX = "querylog/"  # a conflict sync cannot resolve goes to querylog/<run-id>, as a merge request
MR_OPTIONS = ("merge_request.create", f"merge_request.target={BRANCH}")  # push options: no token, no auto-merge
FALLBACK_GITLAB_HOST = "gitlab.com"  # only when origin's url names no host
WORKTREE_NAME = "worktree"  # beside the spool: automatic commits are made there, never in the person's checkout
STORE_REL = "kb/_querylog"
GITLAB_RED = ("failed",)
GITLAB_UNFINISHED = ("created", "waiting_for_resource", "preparing", "waiting_for_callback", "pending", "running",
                     "canceling", "scheduled")
GITHUB_RED = ("failure", "timed_out", "startup_failure")  # conclusions of a completed run
LOOKBACK = 200  # first-parent commits of origin/main searched for the last automatic commit


def run_cmd(argv, cwd=None, env=None, timeout=600):
    """(exit code, stdout, stderr) of a command given as an argument list; 127 when it cannot start or times out."""
    try:
        p = subprocess.run(list(argv), cwd=None if cwd is None else str(cwd), env=env, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as e:
        return 127, "", str(e)
    return p.returncode, p.stdout, p.stderr


def origin_forge(url):
    """(forge, host, project path) of a remote url: https or ssh urls and the scp form user@host:path. A url that
    names no host (a local path, file://) gets FALLBACK_GITLAB_HOST and its last two path segments. `github` for
    github.com, else `gitlab`."""
    u = (url or "").strip()
    host, path = None, u
    if re.match(r"[a-z][a-z0-9+.-]*://", u, re.I):
        s = urlsplit(u)
        host, path = (s.hostname if s.scheme.lower() != "file" else None), s.path
    else:
        m = re.fullmatch(r"(?:[^@/\\]+@)?([^:/\\]{2,}):(?!//)(.*)", u)  # a Windows drive (C:\...) is no host
        if m:
            host, path = m.group(1), m.group(2)
    path = path.replace("\\", "/").strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    if not host:
        return "gitlab", FALLBACK_GITLAB_HOST, "/".join(path.split("/")[-2:])
    host = host.lower()
    return ("github" if host == "github.com" else "gitlab"), host, path


def pipeline_verdict(forge, statuses):
    """`red`, `pending` or `ok` from the CI states of one commit: only a finished failure is red (`failed` on
    GitLab; a completed run concluded failure, timed_out or startup_failure on GitHub); an unfinished state is
    pending; manual, skipped, canceled and success are ok. GitHub: `statuses` are (status, conclusion) pairs."""
    if forge == "github":
        if any(s == "completed" and c in GITHUB_RED for s, c in statuses):
            return "red"
        return "pending" if any(s != "completed" for s, _ in statuses) else "ok"
    if any(s in GITLAB_RED for s in statuses):
        return "red"
    return "pending" if any(s in GITLAB_UNFINISHED for s in statuses) else "ok"


def ci_status(url, sha, run):
    """(verdict, detail) of the CI of commit `sha` on origin's forge: verdict `red`, `pending`, `ok`, `none` (no
    pipeline) or `skip` (no signed-in glab or gh, or the call failed: the check is skipped)."""
    import urllib.parse
    forge, host, project = origin_forge(url)
    cli = "gh" if forge == "github" else "glab"
    code, _, err = run([cli, "auth", "status", "--hostname", host])
    if code:
        return "skip", f"{cli} is not signed in to {host} ({(err.strip().splitlines() or ['not installed'])[-1][:80]})"
    if forge == "github":
        argv = ["gh", "run", "list", "--commit", sha, "-R", f"{host}/{project}", "--json", "status,conclusion",
                "-L", "100"]
    else:
        argv = ["glab", "api", "--hostname", host,
                f"projects/{urllib.parse.quote(project, safe='')}/pipelines?sha={sha}&per_page=1"]
    code, o, err = run(argv)
    try:
        data = json.loads(o) if code == 0 else None
    except ValueError:
        data = None
    if not isinstance(data, list):
        return "skip", f"{' '.join(argv[:2])} failed ({(err.strip().splitlines() or ['no JSON list'])[-1][:80]})"
    if forge == "github":
        states = [(r.get("status"), r.get("conclusion")) for r in data if isinstance(r, dict)]
        shown = ", ".join(f"{s}/{c}" if c else str(s) for s, c in states)
    else:
        states = [r.get("status") for r in data[:1] if isinstance(r, dict)]  # the newest pipeline of the commit
        shown = ", ".join(map(str, states))
    if not states:
        return "none", f"no pipeline for {sha[:9]} on {host}"
    return pipeline_verdict(forge, states), f"{cli} on {host}: {shown}"


def auto_kinds(paths):
    """The KB-Auto values of a commit changing `paths`; ValueError naming a path apply never writes."""
    kinds = set()
    for p in paths:
        if p.startswith(STORE_REL + "/"):
            kinds.add("querylog")
        elif re.fullmatch(r"kb/[^/]+/_retrieval/lookup_eval\.csv", p):
            kinds.add("eval")
        elif p == "_tools/aliases.csv" or re.fullmatch(r"kb/[^/]+/_retrieval/aliases\.csv", p):
            kinds.add("alias")
        elif re.fullmatch(r"kb/[^/]+/_retrieval/doc2query/expansions\.csv", p):
            kinds.add("expansion")
        elif re.fullmatch(r"kb/[^/]+/_gaps\.md", p):
            kinds.add("gap")
        elif re.fullmatch(r"kb/[^/_][^/]*/(?:_sources\.csv|_conflicts\.md|_coverage\.csv|_coverage\.md)", p) \
                or re.fullmatch(r"kb/[^/_][^/]*/[^/_][^/]*/(?:[^/]+/)*[^/_][^/]*\.md", p):
            kinds.add("research")
        else:
            raise ValueError(p)
    return sorted(kinds)


def leak_problems(store, rels, k=None):
    """The leak scan (redact.scan: kbcommon.leak_hits with what the public root contains allowed) over every value of
    the store files `rels`, the ids that name runs, entries and findings aside: one problem per hit."""
    import redact
    k = k or redact.known()
    out = []

    def values(x):
        if isinstance(x, dict):
            for v in x.values():
                yield from values(v)
        elif isinstance(x, list):
            for v in x:
                yield from values(v)
        elif isinstance(x, str):
            yield x

    for rel in rels:
        try:
            objs = load_run(Path(store) / rel)
        except (OSError, ValueError):
            continue  # `check` reports a file that is not JSON lines
        for n, obj in objs:
            for v in values({key: val for key, val in obj.items() if key not in ("id", "entry", "run", "kb_commit")}):
                for kind, _ in redact.scan(v, k):
                    out.append(f"{rel}:{n}: the leak scan flags an identifier ({kind})")
    return out


class Pusher:
    """One `apply --push` in the worktree `wt` of the clone at `home`, whose query log directory `qdir` holds the
    spool and the local store. `run` starts every command (git, kbgit.py sync, glab, gh); `apply_step(wt, store,
    hold, out)` learns and applies the store's findings in the worktree."""

    def __init__(self, home, qdir, run, apply_step, out, now_dt=None):
        self.home, self.qdir, self.run, self.out = Path(home), Path(qdir), run, out
        self.wt = self.qdir / WORKTREE_NAME
        self.apply_step = apply_step or self.learn_and_apply
        self.up = f"refs/remotes/{REMOTE}/{BRANCH}"
        self.on_main = False  # set when deliver pushed to origin's main
        self.now_dt = now_dt  # the time the spool is read at (default: now)

    def git(self, *args, cwd=None):
        return self.run(["git", *args], cwd=str(cwd or self.wt))

    def say(self, text):
        self.out(f"apply --push: {text}")

    def fetch(self):
        """origin's main and its conflict branches (pruned: a merged branch that GitLab deleted goes)."""
        return self.git("fetch", "--quiet", "--prune", REMOTE, f"+refs/heads/{BRANCH}:{self.up}",
                        f"+refs/heads/{CONFLICT_BRANCH_PREFIX}*:refs/remotes/{REMOTE}/{CONFLICT_BRANCH_PREFIX}*",
                        cwd=self.home)

    def reset(self):
        """The worktree at origin/main, detached and clean (a rebase or revert left over is abandoned)."""
        if not (self.wt / ".git").exists():
            self.git("worktree", "prune", cwd=self.home)
            return self.git("worktree", "add", "--quiet", "--detach", str(self.wt), self.up, cwd=self.home)
        for op in (("rebase", "--abort"), ("revert", "--abort"), ("cherry-pick", "--abort")):
            self.git(*op)
        code, o, e = self.git("checkout", "--quiet", "--force", "--detach", self.up)
        if code == 0:
            code, o, e = self.git("clean", "-fdq")
        return code, o, e

    def last_automatic(self):
        """(sha of the last commit on origin/main with a KB-Auto trailer, its values, the push tip: the same commit or
        the kbgit fix commits sync added right after it), or None."""
        import kbgit
        code, o, _ = self.git("log", "--first-parent", "-n", str(LOOKBACK),
                              "--format=%H%x1f%s%x1f%(trailers:key=KB-Auto,valueonly,separator=%x2C)%x1e", self.up)
        recs = [r.strip("\n").split("\x1f") for r in o.split("\x1e") if r.strip()] if code == 0 else []
        for i, (sha, _, auto) in enumerate(recs):
            values = [v.strip() for v in auto.split(",") if v.strip()]
            if values:
                tip = i
                while tip > 0 and recs[tip - 1][1] == kbgit.FIX_COMMIT:
                    tip -= 1
                return sha, values, [r[0] for r in reversed(recs[tip:i + 1])]
        return None

    def held(self):
        """Finding ids pending on a conflict branch of origin that main does not hold yet: the records of the
        findings files the branch adds."""
        code, o, _ = self.git("for-each-ref", "--format=%(refname)", f"refs/remotes/{REMOTE}/{CONFLICT_BRANCH_PREFIX}")
        ids = set()
        for ref in o.split() if code == 0 else []:
            if self.git("merge-base", "--is-ancestor", ref, self.up)[0] == 0:
                continue
            base = self.git("merge-base", ref, self.up)[1].strip()
            if not base:
                continue
            files = self.git("diff", "--name-only", "--diff-filter=A", base, ref, "--", f"{STORE_REL}/{FINDINGS}")[1]
            for f in files.split():
                text = self.git("show", f"{ref}:{f}")[1]
                for line in text.splitlines()[1:]:
                    try:
                        rec = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(rec, dict) and isinstance(rec.get("id"), str):
                        ids.add(rec["id"])
        return ids

    def learn_and_apply(self, wt, store, hold, out):
        """The worktree's own querylog.py learn, then its apply, on its own kb and store."""
        ql = [sys.executable, str(wt / "_tools" / "querylog.py")]
        applying = ql + ["apply", "--store", str(store), "--clone", str(self.home)]
        for h in sorted(hold):
            applying += ["--hold", h]
        for argv in (ql + ["learn", "--store", str(store)], applying):
            code, o, e = self.run(argv, cwd=str(wt))
            for line in (o + (e if code else "")).strip().splitlines():
                out(line)
            if code:
                return code
        return 0

    def local_files(self):
        """(entry ids of the local store's run files that origin/main holds, [(source, published path, entry ids)]
        of the local files to copy, [published paths] of the local findings files that stay local). A run file is
        copied when origin/main lacks its path; a findings file when origin/main lacks its path, all its records
        are in a state learn writes (not apply's outcomes for this clone's working tree) and origin/main records
        none of its findings yet."""
        local, store = self.qdir / "store", self.wt / STORE_REL
        delivered, new, kept = set(), [], []
        for p in run_files(local):
            rel = p.relative_to(local).as_posix()
            try:
                ids = {e["id"] for _, e in load_run(p)[1:] if isinstance(e.get("id"), str)}
            except (OSError, ValueError):
                ids = set()  # copied all the same: `check` refuses it
            if (store / rel).exists():
                delivered |= ids
            else:
                new.append((p, rel, ids))
        recorded = finding_states(store)
        for p in findings_files(local):
            rel = p.relative_to(local).as_posix()
            if (store / rel).exists():
                continue
            try:
                recs = [r for _, r in load_run(p)[1:]]
            except (OSError, ValueError):
                recs = None
            if recs is not None and all(r.get("state") in LEARN_STATES and r.get("id") not in recorded for r in recs):
                new.append((p, rel, set()))
            else:
                kept.append(rel)
        return delivered, new, kept

    def forget(self, ids):
        """The spool rows of the entries `ids`, whose run file is on origin/main, are deleted."""
        n = spool_delivered(self.qdir, ids, self.now_dt)
        if n:
            self.say(f"deleted the spool rows of {n} entries whose run file is on {REMOTE}/{BRANCH}")

    def bring(self, new, kept):
        """The local files `new` copied into the worktree's store, the worktree's `querylog.py check` and the leak
        scan over them, then one commit with `KB-Auto: querylog`. 0, or 1 when a gate fails (nothing committed)."""
        store = self.wt / STORE_REL
        for src, rel, _ in new:
            write_text(store / rel, Path(src).read_text(encoding="utf-8"))
        if kept:
            self.say(f"{len(kept)} local findings file(s) stay local (apply's outcomes, or findings "
                     f"{REMOTE}/{BRANCH} already records)")
        code, o, e = self.run([sys.executable, str(self.wt / "_tools" / "querylog.py"), "check", str(store)],
                              cwd=str(self.wt))
        problems = [ln for ln in o.splitlines() if ln.strip() and not ln.startswith("querylog check:")] if code else []
        if code and not problems:
            problems = [(o + e).strip()[-300:] or f"querylog.py check exit {code}"]
        problems += leak_problems(store, [rel for _, rel, _ in new])
        if problems:
            self.say("refused: the store gates fail on the local store's files; nothing committed or pushed\n  " +
                     "\n  ".join(problems[:10]))
            return 1
        runs = sorted(Path(rel).stem for _, rel, _ in new if not rel.startswith(FINDINGS + "/"))
        found = len(new) - len(runs)
        what = f"{len(runs)} run file(s)" + (f", {found} findings file(s)" if found else "")
        body = (f"Automatic commit of querylog.py: the local store's {what} ({', '.join(runs) or 'no run file'}), "
                "copied into kb/_querylog/ after querylog.py check and the leak scan (kb/_self/querylog.md, "
                "Delivery).")
        return self.commit(f"chore(kb): query log store, {what}", body, ["querylog"])

    def edited(self, paths):
        """The existing lines the worktree's change removes or edits in an article, a ledger or a source row
        (edit_problems against HEAD): apply's changes add only."""
        out = []
        for p in paths:
            f = self.wt / p
            code, old, _ = self.git("show", f"HEAD:{p}")
            if code == 0:
                out += edit_problems(p, old, f.read_text(encoding="utf-8") if f.is_file() else "")
        return out

    def changed(self):
        code, o, _ = self.git("status", "--porcelain", "--untracked-files=all", "-z")
        paths = []
        for rec in o.split("\0") if code == 0 else []:
            if len(rec) > 3:
                paths.append(rec[3:])
        return sorted(set(paths))

    def commit(self, subject, body, kinds):
        """One commit of the worktree's changes with its KB-Auto trailer, then its KB-* trailers. The data files
        apply appends rows to change no doc that describes them (kb/_self/map.csv), so those docs are named in a
        Self-Reviewed trailer, which keeps `selfdoc.py stale` in sync's gate quiet."""
        import kbgit, selfdoc
        assert all(k in kbgit.AUTO_VALUES for k in kinds), kinds
        trailers = [f"{kbgit.AUTO}: " + ", ".join(kinds)]
        reviewed = sorted(selfdoc.describing(selfdoc.load_map(str(self.wt)), self.changed()))
        if reviewed:
            trailers.append(f"{selfdoc.REVIEWED}: " + ", ".join(reviewed))
        code, o, e = self.git("add", "--all")
        if code == 0:
            code, o, e = self.git("commit", "--quiet", "--no-verify", "-m", subject, "-m", body,
                                  "-m", "\n".join(trailers))
        if code == 0:
            code, o, e = self.run([sys.executable, str(self.wt / "_tools" / "kbgit.py"), "trailers", "--amend"],
                                  cwd=str(self.wt))
        if code:
            self.say(f"commit failed: {(o + e).strip()[-300:]}")
        return code

    def deliver(self, run_id):
        """kbgit.py sync --push from the worktree (fetch, rebase on origin/main, fix, gate, push to origin). A
        conflict it cannot resolve (exit 3) pushes the commits as they were before the rebase to
        querylog/<run-id> with the merge-request push options, and main stays as it was."""
        mine = self.git("rev-parse", "HEAD")[1].strip()
        code, o, e = self.run([sys.executable, str(self.wt / "_tools" / "kbgit.py"), "sync", "--push",
                               "--remote", REMOTE, "--branch", BRANCH], cwd=str(self.wt))
        report = [ln for ln in (o + e).splitlines() if ln.startswith(("gate ", "pushed:", "needs-human:", "CONFLICT"))]
        for ln in report:
            self.out("  " + ln)
        if code == 0:
            self.say(f"pushed {mine[:9]} to {REMOTE}/{BRANCH}")
            self.on_main = True
            return 0
        if code != 3:
            self.say(f"kbgit.py sync exit {code}: nothing pushed to {BRANCH}" +
                     ("" if report else f"\n{(o + e).strip()[-600:]}"))
            return code
        self.git("rebase", "--abort")
        branch = CONFLICT_BRANCH_PREFIX + run_id
        argv = ["push"]
        for opt in MR_OPTIONS:
            argv += ["-o", opt]
        code, o, e = self.git(*argv, REMOTE, f"{mine}:refs/heads/{branch}")
        if code:
            self.say(f"conflict, and the push of {branch} failed: {(o + e).strip()[-300:]}")
            return 1
        self.say(f"conflict: pushed {branch} with a merge request for {BRANCH}; its findings stay pending")
        return 0

    def check_ci(self, url):
        """Before any new push: the CI of the last automatic commit's push. Red: a revert commit (an int exit code
        is returned); pending: None (nothing pushed this run); else True."""
        last = self.last_automatic()
        if last is None:
            return True
        sha, values, commits = last
        if "revert" in values:
            return True
        verdict, detail = ci_status(url, commits[-1], self.run)
        if verdict == "skip":
            self.say(f"note: CI status not checked: {detail}")
            return True
        if verdict == "pending":
            self.say(f"CI of the last automatic commit {sha[:9]} is not finished ({detail}); nothing pushed this run")
            return None
        if verdict == "red" and values == ["querylog"]:
            self.say(f"note: CI of the last automatic commit {sha[:9]} is red ({detail}); it changed only "
                     f"{STORE_REL}, whose files a revert keeps: nothing to revert")
            return True
        if verdict == "red":
            self.say(f"CI of the last automatic commit {sha[:9]} is red ({detail}): reverting it")
            return self.revert(sha, commits, detail)
        return True

    def revert(self, sha, commits, detail):
        """A revert commit (KB-Auto: revert) of the automatic push `commits` that keeps the store's files, with one
        findings file recording apply-failed for every finding those commits applied."""
        code, o, e = self.git("revert", "--no-commit", *reversed(commits))
        if code:
            self.git("revert", "--abort")
            self.say(f"the revert of {sha[:9]} does not apply cleanly; nothing pushed ({(o + e).strip()[-200:]})")
            return 1
        self.git("checkout", "HEAD", "--", STORE_REL)
        store = self.wt / STORE_REL
        added = self.git("diff", "--name-only", "--diff-filter=A", f"{commits[0]}^", commits[-1], "--",
                         f"{STORE_REL}/{FINDINGS}")[1].split()
        applied = {}
        for f in added:
            try:
                objs = load_run(self.wt / f)
            except (OSError, ValueError):
                continue
            for _, rec in objs[1:]:
                if rec.get("state") == "applied" and isinstance(rec.get("id"), str):
                    applied[rec["id"]] = rec
        run_id = f"revert-{sha[:12]}"
        if applied:
            new = [{**{k: v for k, v in r.items() if k != "observed"}, "state": APPLY_FAILED,
                    "observed": {"ci": detail[:200], "commit": sha[:12]}} for r in applied.values()]
            run_id, _ = write_findings(store, store_entries(store), new, (APPLY_FAILED,),
                                       self.git("rev-parse", "HEAD")[1].strip())
        body = (f"This reverts commit {sha}" + (f" and the {len(commits) - 1} commit(s) after it" if len(commits) > 1
                                                else "") +
                f".\n\nIts pipeline is red ({detail}). The store's files stay; the {len(applied)} finding(s) it "
                f"applied are recorded {APPLY_FAILED} and are never applied again.")
        if self.commit(f"revert: query log commit {sha[:9]}", body, ["revert"]):
            return 1
        return self.deliver(run_id)

    def __call__(self):
        code, url, _ = self.git("remote", "get-url", REMOTE, cwd=self.home)
        if code:
            self.say(f"refused: {self.home} is not a git clone with a remote {REMOTE}")
            return 2
        code, o, e = self.fetch()
        if code:
            self.say(f"git fetch {REMOTE} failed; nothing pushed ({(o + e).strip()[-300:]})")
            return 1
        code, o, e = self.reset()
        if code:
            self.say(f"the worktree {self.wt} could not be set to {REMOTE}/{BRANCH}: {(o + e).strip()[-300:]}")
            return 1
        delivered, new, kept = self.local_files()
        self.forget(delivered)
        ok = self.check_ci(url.strip())
        if ok is None:
            return 0
        if ok is not True:
            return ok
        hold = self.held()
        if hold:
            self.say(f"{len(hold)} finding(s) wait on a {CONFLICT_BRANCH_PREFIX} branch and are left alone")
        store = self.wt / STORE_REL
        if new and self.bring(new, kept):
            return 1
        code = self.apply_step(self.wt, store, hold, self.out)
        if code:
            return code
        paths = self.changed()
        if not paths and not new:
            self.say("nothing to push")
            return 0
        runs = [Path(p).stem for p in paths if p.startswith(f"{STORE_REL}/{FINDINGS}/") and p.endswith(".jsonl")]
        run_id = max(runs or [Path(rel).stem for _, rel, _ in new]
                     or [self.git("rev-parse", "--short=12", "HEAD")[1].strip()])
        if paths:
            try:
                kinds = auto_kinds(paths)
            except ValueError as e:
                self.say(f"refused: apply changed {e}, which it never writes; nothing committed")
                return 1
            edits = self.edited(paths)
            if edits:
                self.say("refused: " + "; ".join(edits[:3]) + "; nothing committed")
                return 1
            body = (f"Automatic commit of querylog.py apply --push, findings run {run_id}: the findings learn wrote, "
                    "the eval rows with their fixes, gap entries, opt-in research, and the findings file that "
                    "records each outcome (kb/_self/querylog.md, Delivery).")
            if self.commit(f"chore(kb): query log apply {run_id}", body, kinds):
                return 1
        code = self.deliver(run_id)
        if self.on_main:
            self.forget(set().union(*(ids for _, _, ids in new)))
        return code


def push(home=None, qdir=None, run=None, apply_step=None, out=print, now_dt=None):
    """`apply --push`: under the distill lock, the CI check of the last automatic commit (a revert when red), then in
    the worktree beside the spool the local store's new files (a commit of their own), learn and apply, one commit
    with its KB-Auto trailer, and kbgit.py sync --push to origin; the spool rows of pushed entries go after it.
    0 done (pushed, nothing to push, CI pending, or a conflict branch pushed), 1 a step failed, 2 refused, 3 another
    distill or push holds the lock."""
    qdir = Path(qdir or places()[0])
    lock = acquire(qdir)
    if lock is None:
        out("apply --push: another distill or push holds the lock")
        return 3
    try:
        return Pusher(home or HOME, qdir, run or run_cmd, apply_step, out, now_dt)()
    finally:
        release(lock)


def findings_problems(store, k=None):
    """The findings gates: a header with the run's provenance naming its file, records with a finding id, a known
    kind, state and stage, an entry the store holds, and a source finding's public host and signal."""
    store = Path(store)
    ids = {e["id"] for _, e in store_entries(store)}
    out = []
    for p in findings_files(store):
        rel = p.relative_to(store).as_posix()
        try:
            objs = load_run(p)
        except (OSError, ValueError) as e:
            out.append(f"{rel}: not a findings file ({e})")
            continue
        if not objs:
            out.append(f"{rel}: empty findings file")
            continue
        (hn, h), recs = objs[0], objs[1:]
        missing = [key for key in HEADER_KEYS if key not in h]
        if missing:
            out.append(f"{rel}:{hn}: header lacks {', '.join(missing)}")
        m = RUN_ID.fullmatch(str(h.get("run", "")))
        if "run" in h and not (m and h["run"] == p.stem and p.parent.name == f"{m.group(1)}-{m.group(2)}"):
            out.append(f"{rel}:{hn}: run id does not name this file")
        if isinstance(h.get("counts"), dict) and h["counts"].get("findings") != len(recs):
            out.append(f"{rel}:{hn}: counts.findings is {h['counts'].get('findings')}, the file has {len(recs)}")
        for n, r in recs:
            where = f"{rel}:{n}"
            if not (isinstance(r.get("id"), str) and FINDING_ID.fullmatch(r["id"])):
                out.append(f"{where}: finding id is not F-<12 hex>")
            other = sorted(set(r) - set(FINDING_KEYS))
            if other:
                out.append(f"{where}: unknown fields: {', '.join(other)}")
            if r.get("kind") not in FINDING_KINDS:
                out.append(f"{where}: unknown kind {r.get('kind')!r}")
            if r.get("state") not in FINDING_STATES:
                out.append(f"{where}: unknown state {r.get('state')!r}")
            if r.get("kind") == "source":
                if r.get("state") in APPLY_STATES + (APPLY_FAILED,):
                    out.append(f"{where}: a source finding is never applied")
                if r.get("signal") not in SIGNALS:
                    out.append(f"{where}: unknown signal {r.get('signal')!r}")
                if not public_host(r.get("host"), k):
                    out.append(f"{where}: source host is not a public host")
            elif r.get("kind") in FINDING_KINDS:
                if r.get("stage") not in STAGES:
                    out.append(f"{where}: unknown stage {r.get('stage')!r}")
                if r.get("entry") not in ids:
                    out.append(f"{where}: entry {r.get('entry')} is in no run file of the store")
                prs = r.get("promotions") or []
                for pr in prs:
                    if not (isinstance(pr, dict) and pr.get("from") in STAGES and pr.get("to") in STAGES):
                        out.append(f"{where}: a promotion without its from and to stages")
                    elif pr.get("by") not in PROMOTERS:
                        out.append(f"{where}: a promotion by {pr.get('by')!r}, not one of {', '.join(PROMOTERS)}")
                if prs and all(isinstance(pr, dict) for pr in prs):
                    chain = [pr.get("from") for pr in prs[:1]] + [pr.get("to") for pr in prs]
                    if any(pr.get("from") != chain[i] for i, pr in enumerate(prs)):
                        out.append(f"{where}: promotions do not follow each other")
                    elif chain[-1] != r.get("stage") and r.get("stage") in STAGES:
                        out.append(f"{where}: stage {r.get('stage')} is not its last promotion's {chain[-1]}")
                if r.get("kind") == "gap" and r.get("stage") in STAGES[2:] and not ARTICLE.fullmatch(
                        str(r.get("article", ""))):
                    out.append(f"{where}: a gap finding at stage {r.get('stage')} names no article")
    last = finding_states(store)
    fixed = {r.get("entry") for r in last.values() if r.get("kind") in FIX_KINDS and r.get("state") == "applied"}
    for r in last.values():
        if r.get("kind") == "eval" and r.get("state") == "applied" and r.get("entry") not in fixed:
            out.append(f"findings: eval finding {r.get('id')} is applied without its fix")
    return out


# --- reporting: the weekly digest and status (querylog.md, Reporting) ----------------------------------------------

DIGEST_MARKER = "digest-week"  # beside the spool: the ISO week in which the SessionStart digest was last shown
DIGEST_BUDGET_S = 3  # the SessionStart digest prints nothing when reading the store took longer
DIGEST_HOOK_TIMEOUT_S = 10  # the digest hook's `timeout` in .claude/settings.json and the plugin
WEEK = re.compile(r"(\d{4})-W(\d{2})")
MISS_KINDS = ("eval", "gap")  # one finding per judged miss: an eval finding with a best article, else a gap finding


def iso_week(day):
    """`YYYY-Www`, the ISO week of a date."""
    y, w, _ = day.isocalendar()
    return f"{y}-W{w:02d}"


def week_days(week):
    """(Monday, Sunday) of the ISO week `YYYY-Www`; ValueError for anything else."""
    m = WEEK.fullmatch(str(week or ""))
    if not m:
        raise ValueError(f"not an ISO week (YYYY-Www): {week!r}")
    monday = datetime.date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1)
    return monday, monday + datetime.timedelta(days=6)


def run_day(run_id):
    """The UTC date of a run id, or None when it is not one."""
    m = RUN_ID.fullmatch(str(run_id))
    return datetime.date(int(run_id[:4]), int(run_id[4:6]), int(run_id[6:8])) if m else None


def latest_week(store):
    """The ISO week of the newest entry's day in the store, else of its newest run or findings file; None when the
    store holds neither."""
    days = [e["day"] for _, e in store_entries(store) if isinstance(e.get("day"), str)
            and re.fullmatch(r"\d{4}-\d{2}-\d{2}", e["day"])]
    if days:
        return iso_week(datetime.date.fromisoformat(max(days)))
    runs = [d for d in (run_day(p.stem) for p in run_files(store) + findings_files(store)) if d]
    return iso_week(max(runs)) if runs else None


def _counts(pairs):
    return ", ".join(f"{k} {n}" for k, n in pairs)


def digest(store=None, week=None):
    """(week, lines, whether the week holds anything) of the committed store (default kb/_querylog) for the ISO week
    `week` (default: the week of the newest entry). Only the store and `week` go in, so every clone at the same
    commit prints the same lines. Entries count by their `day`, run and findings files by their run id's date, and
    findings states are each finding's last record in the findings files dated up to the week's Sunday."""
    store = Path(store or STORE)
    week = week or latest_week(store)
    if week is None:
        return None, ["query log digest: the store holds no run file"], False
    monday, sunday = week_days(week)
    lo, hi = monday.isoformat(), sunday.isoformat()

    def inside(d):
        return d is not None and monday <= d <= sunday

    entries = [e for _, e in store_entries(store) if isinstance(e.get("day"), str) and lo <= e["day"] <= hi]
    runs, dropped = 0, 0
    for p in run_files(store):
        if not inside(run_day(p.stem)):
            continue
        runs += 1
        try:
            counts = load_run(p)[0][1].get("counts")
        except (OSError, ValueError, IndexError):
            continue
        if isinstance(counts, dict) and isinstance(counts.get("dropped"), int):
            dropped += counts["dropped"]
    state, recorded = {}, 0
    for p in findings_files(store):
        d = run_day(p.stem)
        if d is None or d > sunday:
            continue
        try:
            recs = [r for _, r in load_run(p)[1:] if isinstance(r.get("id"), str)]
        except (OSError, ValueError):
            continue
        recorded += len(recs) if inside(d) else 0
        state.update((r["id"], r) for r in recs)
    surfaces = [(s, sum(1 for e in entries if e.get("surface") == s)) for s in SURFACES]
    verdicts = [(v, sum(1 for e in entries if e.get("verdict") == v)) for v in reversed(VERDICTS)]
    verdicts.append(("no verdict", sum(1 for e in entries if e.get("verdict") not in VERDICTS)))
    judged_ = [(j, sum(1 for e in entries if e.get("judged") == j)) for j in JUDGED]
    judged_.append(("not judged", sum(1 for e in entries if e.get("judged") not in JUDGED)))
    misses = [e for e in entries if is_miss(e)]
    fixed = {"by the kb since": 0, "by apply": 0, "by research": 0}
    for e in misses:
        for kind in MISS_KINDS:
            r = state.get(finding_id(kind, e["id"]))
            if r is None:
                continue
            if r.get("state") == "fixed-since":
                fixed["by the kb since"] += 1
            elif r.get("state") == "applied" and kind == "eval":
                fixed["by apply"] += 1
            elif r.get("state") == "applied" and r.get("stage") == "claim":
                fixed["by research"] += 1
    items = []
    for e in entries:
        items += [f for f in e.get("fetches") or [] if isinstance(f, dict)]
        if e.get("outcome"):
            items.append({k: e[k] for k in FETCH_KEYS if k in e})
    nfetch = sum(f["n"] if isinstance(f.get("n"), int) else 1 for f in items)
    failed = sum(f["n"] if isinstance(f.get("n"), int) else 1 for f in items
                 if isinstance(f.get("outcome"), str) and FAILED.fullmatch(f["outcome"]))
    chars = sum(f["chars"] for f in items if isinstance(f.get("chars"), int))
    lines = [f"query log digest {week} ({lo} to {hi})",
             f"lookups: {len(entries)}" + (f" ({_counts((s, n) for s, n in surfaces if n)})" if entries else ""),
             f"verdicts: {_counts(verdicts)}",
             f"judged: {_counts(judged_)}",
             f"misses: {len(misses)}, fixed: {sum(fixed.values())} ({_counts(fixed.items())})",
             f"fetches: {nfetch}, failed {failed}, result characters {chars}",
             f"runs: {runs}, entries dropped by redaction {dropped}",
             f"finding records written: {recorded}"]
    table = {}
    for r in state.values():
        if r.get("kind") in FINDING_KINDS and r.get("state") in FINDING_STATES:
            table.setdefault(r["kind"], {}).setdefault(r["state"], 0)
            table[r["kind"]][r["state"]] += 1
    lines.append("findings by kind and state at the week's end:" + ("" if table else " none"))
    for kind in FINDING_KINDS:
        if kind in table:
            lines.append(f"  {kind}: " + _counts((s, table[kind][s]) for s in FINDING_STATES if s in table[kind]))
    return week, lines, bool(entries or runs or recorded)


def digest_hook(now_dt=None, store=None):
    """The SessionStart digest: the JSON line `{"systemMessage": ...}` the first SessionStart of an ISO week prints
    (last week's digest), or None: logging off (mode `off`, the DISABLED marker), already shown this week (the marker
    beside the spool names the week), an empty week, or reading the store took more than DIGEST_BUDGET_S. The
    marker is written before the store is read, so a slow or failed digest is not tried again that week."""
    t0 = time.monotonic()
    qdir, cfg = places()
    if (qdir / "DISABLED").exists() or read_mode(cfg) == "off":
        return None
    today = (now_dt or datetime.datetime.now(datetime.timezone.utc)).date()
    this = iso_week(today)
    marker = qdir / DIGEST_MARKER
    try:
        if marker.read_text(encoding="utf-8").strip() == this:
            return None
    except OSError:
        pass
    write_text(marker, this + "\n")
    _, lines, found = digest(store, iso_week(today - datetime.timedelta(days=7)))
    if not found or time.monotonic() - t0 > DIGEST_BUDGET_S:
        return None
    return json.dumps({"systemMessage": "\n".join(lines)}, ensure_ascii=False)


def hook_digest():
    """`digest --hook`: the SessionStart event on stdin is read and left unused; at most one JSON line; exit 0."""
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        sys.stdin.read()
    except Exception:  # noqa: BLE001 - the event carries nothing the digest needs
        pass
    try:
        line = digest_hook()
    except Exception:  # noqa: BLE001 - a session starts whatever happens here
        line = None
    if line:
        sys.stdout.reconfigure(encoding="utf-8")
        print(line)
    return 0


def conflict_mrs(url, run):
    """([(number, branch, title, url)] (`!iid` on GitLab, `#number` on GitHub) of the open merge requests from a CONFLICT_BRANCH_PREFIX branch to BRANCH on
    origin's forge, None and a note when glab or gh is not signed in or the call fails). The API filters by one
    whole branch name, so the open ones targeting BRANCH are listed and the prefix is matched here."""
    import urllib.parse
    forge, host, project = origin_forge(url)
    cli = "gh" if forge == "github" else "glab"
    code, _, err = run([cli, "auth", "status", "--hostname", host])
    if code:
        return None, f"{cli} is not signed in to {host} ({(err.strip().splitlines() or ['not installed'])[-1][:80]})"
    if forge == "github":
        argv = ["gh", "pr", "list", "-R", f"{host}/{project}", "--base", BRANCH, "--state", "open",
                "--json", "number,title,headRefName,url", "-L", "100"]
    else:
        argv = ["glab", "api", "--hostname", host, f"projects/{urllib.parse.quote(project, safe='')}/merge_requests"
                f"?state=opened&target_branch={BRANCH}&per_page=100"]
    code, o, err = run(argv)
    try:
        data = json.loads(o) if code == 0 else None
    except ValueError:
        data = None
    if not isinstance(data, list):
        return None, f"{' '.join(argv[:3] if forge == 'github' else argv[:2])} failed ({(err.strip().splitlines() or ['no JSON list'])[-1][:80]})"
    out = []
    for r in data:
        if not isinstance(r, dict):
            continue
        branch = r.get("headRefName") if forge == "github" else r.get("source_branch")
        if isinstance(branch, str) and branch.startswith(CONFLICT_BRANCH_PREFIX):
            num = f"#{r.get('number')}" if forge == "github" else f"!{r.get('iid')}"
            out.append((num, branch, str(r.get("title") or ""), str(r.get("url") or r.get("web_url") or "")))
    return sorted(out, key=lambda m: m[1]), f"{cli} on {host}"


def reverted_commits(home, run):
    """[(short hash, subject)] of the commits at HEAD whose KB-Auto trailer holds `revert`, newest first."""
    code, o, _ = run(["git", "log", "--format=%h%x1f%s%x1f%(trailers:key=KB-Auto,valueonly,separator=%x2C)%x1e",
                      "HEAD"], cwd=str(home))
    out = []
    for rec in o.split("\x1e") if code == 0 else []:
        parts = rec.strip("\n").split("\x1f")
        if len(parts) == 3 and "revert" in [v.strip() for v in parts[2].split(",")]:
            out.append((parts[0], parts[1]))
    return out


def status(store=None, home=None, run=None, out=print):
    """Three lists from the committed store and the clone at `home`: open source findings, most result characters
    first (the characters the store's fetches of the host returned); open conflict merge requests on origin's forge
    (skipped with a note when glab or gh is not signed in, or there is no origin); automatic commits that were
    reverted (KB-Auto: revert). 0."""
    store, home, run = Path(store or STORE), Path(home or HOME), run or run_cmd
    hosts = host_fetches(store_entries(store))
    found = [r for r in finding_states(store).values() if r.get("kind") == "source" and r.get("state") == "open"]
    chars = {r["id"]: hosts.get(r.get("host"), {}).get("chars", 0) for r in found}
    found.sort(key=lambda r: (-chars[r["id"]], str(r.get("host")), str(r.get("signal")), r["id"]))
    out(f"open source findings, most result characters first: {len(found)}")
    for r in found:
        if r.get("signal") == "stage":
            what = f"stage: level {r.get('level')}, needs {r.get('needs')} ({', '.join(r.get('triggers') or [])})"
        else:
            what = f"route: {r.get('tool')} read a host of `{r.get('route')}`"
        out(f"  {chars[r['id']]} chars  {r.get('host')}  {what}  {r['id']}")
    code, url, _ = run(["git", "remote", "get-url", REMOTE], cwd=str(home))
    if code:
        out(f"open conflict merge requests: not checked: no remote {REMOTE}")
    else:
        mrs, note = conflict_mrs(url.strip(), run)
        if mrs is None:
            out(f"open conflict merge requests: not checked: {note}")
        else:
            out(f"open conflict merge requests ({note}): {len(mrs)}")
            for num, branch, title, link in mrs:
                out(f"  {num} {branch}  {title}  {link}".rstrip())
    reverts = reverted_commits(home, run)
    out(f"reverted automatic commits: {len(reverts)}")
    for h, subject in reverts:
        out(f"  {h} {subject}")
    return 0


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
    if argv[:1] == ["learn"]:
        import argparse
        ap = argparse.ArgumentParser(prog="querylog.py learn")
        ap.add_argument("--store", help="the store to learn from and write findings to (default: the local store)")
        a = ap.parse_args(argv[1:])
        if a.store is None:
            d, cfg = places()
            if (d / "DISABLED").exists() or read_mode(cfg) == "off":
                print("learn: logging is off")
                return 0
        return learn(a.store)
    if argv[:1] == ["apply"]:
        import argparse
        ap = argparse.ArgumentParser(prog="querylog.py apply")
        ap.add_argument("--store", help="the store whose findings to apply and record (default: the local store)")
        ap.add_argument("--hold", action="append", default=[], metavar="ID",
                        help="leave this finding alone (a finding pending on a conflict branch; repeatable)")
        ap.add_argument("--push", action="store_true",
                        help="apply in the worktree beside the spool on origin/main's kb/_querylog, commit, and push "
                             "to origin through kbgit.py sync")
        ap.add_argument("--clone", metavar="DIR",
                        help="the clone whose per-user config (_private/querylog.json) turns research on and whose "
                             "_cache/querylog counts the day's research runs (apply --push names its own clone)")
        ap.add_argument("--replay-research", metavar="FILE",
                        help="answer the research runs and the quote check's page fetches from this recorded file "
                             '({"replies": [...], "pages": {url: file}})')
        a = ap.parse_args(argv[1:])
        if a.push and (a.store or a.clone or a.replay_research):
            print("apply --push: refused: the store is the worktree's kb/_querylog and the clone is this one; "
                  "--store, --clone and --replay-research are for a local apply", file=sys.stderr)
            return 2
        if a.store is None:
            d, cfg = places()
            if (d / "DISABLED").exists() or read_mode(cfg) == "off":
                print("apply: logging is off")
                return 0
        if a.push:
            if places()[0] != HOME / "_cache" / "querylog":
                print("apply --push: refused: it pushes from a clone, not from a plugin host")
                return 2
            return push()
        day = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        rq, rcfg = research_places(a.clone)
        runs = min(research_budget(rq, rcfg, day), RESEARCH_RUNS_PER_APPLY)
        research = None
        if runs:
            replay = ResearchReplay(a.replay_research) if a.replay_research else None
            research = Researcher(runs, call=replay, fetcher=replay.fetch if replay else None,
                                  counted=lambda: count_research(rq, day))
        return apply(a.store, hold=set(a.hold), research=research, day=day)
    if argv[:1] == ["quotecheck"]:
        import argparse
        ap = argparse.ArgumentParser(prog="querylog.py quotecheck")
        ap.add_argument("url")
        ap.add_argument("quote")
        ap.add_argument("--page", metavar="FILE", help="read the page from this recorded file instead of the url")
        ap.add_argument("--ctype", default="", help="the recorded page's content type (default: from its suffix)")
        a = ap.parse_args(argv[1:])
        fetcher = None
        if a.page:
            page = Path(a.page)
            ctype = a.ctype or {".html": "text/html", ".htm": "text/html", ".md": "text/markdown"}.get(
                page.suffix.lower(), "text/plain")

            def fetcher(url):
                return page.read_bytes(), ctype
        ok, why = quotecheck(a.url, a.quote, fetcher)
        print(f"quotecheck: {why}")
        return 0 if ok else 1
    if argv[:1] == ["digest"]:
        import argparse
        ap = argparse.ArgumentParser(prog="querylog.py digest")
        ap.add_argument("--store", help="the store to read (default: kb/_querylog, the committed store)")
        ap.add_argument("--week", help="the ISO week YYYY-Www (default: the week of the store's newest entry)")
        ap.add_argument("--hook", action="store_true", help="the SessionStart hook: last week's digest as a "
                        "systemMessage, once per ISO week")
        a = ap.parse_args(argv[1:])
        if a.hook:
            return hook_digest()
        try:
            _, lines, _ = digest(a.store, a.week)
        except ValueError as e:
            print(f"digest: {e}", file=sys.stderr)
            return 2
        print("\n".join(lines))
        return 0
    if argv[:1] == ["status"]:
        import argparse
        ap = argparse.ArgumentParser(prog="querylog.py status")
        ap.add_argument("--store", help="the store to read (default: kb/_querylog, the committed store)")
        a = ap.parse_args(argv[1:])
        return status(a.store)
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
