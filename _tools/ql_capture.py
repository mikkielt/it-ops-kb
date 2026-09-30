"""The query log's capture (kb/_self/querylog.md, Surfaces and Capture): the hook that turns one Claude Code event
into at most one spool row, and `record` for the tools that write their own rows (kb_hook.py, kb_ask.py, fetch.py,
census.py). Standard library only, and cheap to import: the kb: hook and every capture hook load it.

Every row has a fresh UUID `id`, the UTC time `ts`, its `surface` and the row format `v` (ROW_FORMAT); a hook row also
has `session_id` and `prompt_id`. Nothing is written when logging is off (ql_base.logging_off).
"""
import datetime, functools, json, re, sys, threading, time, uuid
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
CUT = " [...]"
ARG_MAX_CHARS = 1000
VERDICTS = ("none", "weak", "good")  # worst first
TAGS = ("DOC", "CODE", "DER", "COMMUNITY", "UNK")
KB_LINE = re.compile(r"^\s*(- |\[[\d.]+\] )([\w-]+(?:/[\w.-]+)+:[1-9]\d*)(?![\w:])(.*)$")  # a pack line, a search hit
LINE_TAG = re.compile(r"\[(DOC|CODE|DER|COMMUNITY|UNK)\b[^\]]*\]\s*$")
COVERAGE = re.compile(r"^coverage: (good|weak|none)\b", re.M)
_lock = threading.Lock()


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
    for its log."""
    try:
        spool = spool_dir()
        if spool is None:
            return None
        row = {"id": str(uuid.uuid4()), "ts": now(), "surface": surface, "v": ROW_FORMAT}
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


def add_usage(spool, session_id, transcript_path, skip=None):
    """Append a `usage` row (kbusage.prompt_usage) to the spool file of `session_id` for each of its prompts but
    `skip` that used the kb (a kb_hook or mcp row, or a prompt with a kb intent) and has no usage row of this reader
    yet. The number of rows written; the transcript path is never written."""
    if not (isinstance(session_id, str) and SAFE_SESSION.fullmatch(session_id)
            and isinstance(transcript_path, str) and transcript_path):
        return 0
    path = Path(spool) / f"{session_id}.jsonl"
    kb, done = [], set()
    for r in rows(path):
        pid = r.get("prompt_id") if isinstance(r, dict) else None
        if not isinstance(pid, str) or pid == skip:
            continue
        if r.get("surface") == "usage":
            done.add((pid, r.get("reader")))
        elif (r.get("surface") in ("kb_hook", "mcp") or r.get("kb_intent")) and pid not in kb:
            kb.append(pid)
    if not kb:
        return 0
    import kbusage
    out = []
    for pid in kb:
        rec = None if (pid, kbusage.READER_VERSION) in done else kbusage.prompt_usage(transcript_path, pid)
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
