"""The query log's distill (kb/_self/querylog.md, Spool and Distill): the closed sessions of the spool become one run
file in the local store. Per lookup the question the kb was asked (never the prompt) after the rules and the leak
scan, the path:line citations of the kb lines it returned (never the reply), and Haiku's judgement in capped batches;
no text of Haiku's is stored. Started by SessionEnd with the session's transcript, distill first writes a `usage` row
per kb prompt of that session and per prompt inside one of its work windows (ql_capture.add_usage), and the usage rows
of the written entries become the run's usage sidecar, and the prompts of the closed sessions' work windows, summed per
item (a prompt in several windows once, on their sprint; a work-branch subagent on its item), become its work sidecar,
which also holds the run's own Haiku calls' token counts as an overhead line (Spend, haiku_result). The `ops` rows of
the tools files, rows of what the kb's own tools did and took, become the run's ops sidecar (plan_ops).
Also the SessionEnd and SessionStart launcher that starts a detached distill.

Distill reads every row format capture has written (ROW_FORMAT, format 0 for a row without `v`) and skips and counts a
row it cannot read.
"""
import datetime, functools, json, os, re, subprocess, sys, time, uuid
from pathlib import Path

import kbusage
import ql_store as store_
from ql_base import (ENTRY, HOME, LOCK_NAME, LOCK_STALE_S, acquire, claude_p, iso, json_lines, lock_age,
                     logging_off, one_line, places, plugin_data, read_json, read_mode, release, run_cmd, write_text)
from ql_capture import AGENT_ACTIONS, OPS, ROW_FORMAT, SAFE_SESSION, TAGS, VERDICTS, WORK_ITEM, add_usage, pack_lines
from ql_store import (ANSWER_LINE, ANSWER_LINES_MAX, ARTICLE, CITATION, CITATIONS_MAX, ENTRY_KEYS, JUDGED, KEY_MISSING_MAX,
                      KEY_WORD, NAME, OUTCOME, QUESTION_MAX_CHARS, ROW_SURFACES, RULES_ROOT, SET_NAME, SKIPPED_KEY,
                      SOURCES_MAX, TESTED_ID, TESTED_MAX, URL_PATH, public_host)

HAIKU_MODEL = "haiku"
HAIKU_BATCH_ENTRIES = 25
HAIKU_BATCHES_PER_RUN = 4
HAIKU_DAILY_CALLS = 20
HAIKU_TIMEOUT_S = 180
HAIKU_TEXT_MAX_CHARS = 1500
LAUNCH_BUDGET_S = 0.5
LAUNCH_SETTLE_S = 2
SESSION_IDLE_CLOSED_S = 86400
USAGE_LOCK_WAIT_S = 600  # a distill started with a transcript waits this long for the lock
USAGE_LOCK_POLL_S = 2
LOG_NAME = "distill.log"
LOG_MAX_BYTES = 1_000_000  # the launcher starts a fresh log above it
CALLS_NAME = "haiku-calls.json"  # {"day", "calls"}: the Haiku calls this machine made today
CONSUMED_NAME = "consumed.json"  # {tools file: [row ids]}: tools rows already distilled into an entry
WORKED_NAME = "worked.json"  # {session id: [prompt ids]}: prompts whose usage a work sidecar already holds
BACKLOG_REL = "kb/_self/backlog"  # the item files that name each item's sprint (sprint_finder)
KB_SURFACES = ("kb_hook", "mcp", "kb_ask", "tool_fetch")
REPLY_CITE = re.compile(r"(?<![\w./-])(?:kb/)?((?:[\w-]+/)+[\w.-]+:[1-9]\d*)")  # a path:line a reply names
DISTILL_TASK = (
    "Each entry below is one lookup in an IT knowledge base, already stripped of addresses, ids, paths and secrets: "
    "`question` is what the kb was asked, `prompt` what the person typed and `answer` the reply they got (either may "
    "be empty), `candidates` the kb articles the lookup's kb calls returned. Judge each entry; write no text of your "
    "own. Give only: `judged`: \"answered\", \"partly\" or \"missed\", whether the reply answered the question from the "
    "kb; `best`: the one candidate that answers the question, copied exactly, or null (never an article that is not a "
    "candidate); `identifying`: true when `question` names a person or an organisation's own name (the company, a "
    "customer, a team; product, vendor and technology names and placeholders such as PL-..., jan.kowalski, CORP and "
    "corp.example.com do not count). Reply with only a JSON array, one object per entry, in order, with no other "
    'fields: [{"i": 0, "judged": "answered", "best": null, "identifying": false}, ...].')


def ts_of(r):
    return r.get("ts") if isinstance(r.get("ts"), str) else ""


def _text(path):
    """The text of a file, or None when it cannot be read."""
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return None


# ---------------------------------------------------------------- reading the spool

def row_format(r):
    """The format of a spool row: 0 for a row without `v` (every row written before the field), its `v` when it is a
    format this code reads (1 to ROW_FORMAT), else None."""
    if "v" not in r:
        return 0
    v = r["v"]
    return v if isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= ROW_FORMAT else None


def readable(r):
    """Whether distill reads a spool row: a JSON object with a string `id` and `ts`, a surface capture writes and a
    row format this code reads. Any other row is skipped and counted (querylog.md, Spool)."""
    return (isinstance(r, dict) and isinstance(r.get("id"), str) and bool(r["id"]) and isinstance(r.get("ts"), str)
            and r.get("surface") in ROW_SURFACES and row_format(r) is not None)


def spool_rows(path):
    """(the rows distill reads, the number of rows it skips) of one spool file; blank lines are neither."""
    good, skipped = [], 0
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    r = None
                if readable(r):
                    good.append(r)
                else:
                    skipped += 1
    except OSError:
        pass
    return good, skipped


def read_spool(spool, t_now):
    """({session id: session}, {tools file name: rows}, {file name: rows skipped}). A session is closed when its
    SessionEnd marker exists or it has been idle for SESSION_IDLE_CLOSED_S; its `end` bounds the window of its last
    prompt."""
    sessions, tools, skipped = {}, {}, {}
    if not Path(spool).is_dir():
        return sessions, tools, skipped
    for p in sorted(Path(spool).glob("*.jsonl")):
        rs, bad = spool_rows(p)
        if bad:
            skipped[p.name] = bad
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
    return sessions, tools, skipped


def is_agent_row(r):
    """Whether a spool row is the start or stop of a subagent (ql_capture.agent_row): a `work` row of no prompt."""
    return r.get("surface") == "work" and r.get("action") in AGENT_ACTIONS


def groups(session):
    """[key, rows, window start, window end] per prompt of a session, in time order: a prompt's window runs from its
    prompt row to its Stop row, else to the next prompt (the last one: to the session's end)."""
    by = {}
    for r in session["rows"]:
        if is_agent_row(r):
            continue  # a subagent's start or stop is no prompt's row and opens no window (plan_agents)
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


# ---------------------------------------------------------------- entries

def plan_ops(tools, consumed, held=()):
    """([ops sidecar line], rows dropped, [(tools file, row id)] read): the `ops` rows of the tools files that no run
    has consumed, in time order. A row that is not the closed shape the store keeps (ql_store.ops_line), or that the
    leak scan flags (ql_store.ops_line_leaks), is dropped and counted; a row whose id `held` has (a sidecar of an earlier
    run wrote it before its consumption was recorded) writes no second line. Every row read is in the third value,
    to be recorded as consumed once the sidecar is written."""
    lines, bad, read, seen = [], 0, [], set(held)
    for name, rs in sorted(tools.items()):
        for r in rs:
            if r.get("surface") != OPS or r["id"] in consumed.get(name, ()):
                continue
            read.append((name, r["id"]))
            if r["id"] in seen:
                continue
            seen.add(r["id"])
            line = store_.ops_line(r)
            if line is None or store_.ops_line_leaks(line):
                bad += 1
            else:
                lines.append(line)
    lines.sort(key=lambda ln: (ln["ts"], ln["id"]))
    return lines, bad, read


def _epoch_ms(ts):
    """The milliseconds since the epoch of a spool time, or None when it is not one."""
    try:
        return round(datetime.datetime.fromisoformat(ts).timestamp() * 1000)
    except (TypeError, ValueError):
        return None


def plan_agents(sessions, held=()):
    """([ops lines], rows skipped): one `agent.run` line per subagent that has a start and a stop row in a closed
    session (ql_capture.agent_row: the salted hash of the agent id, its group and item). SubagentStart can fire more
    than once for one agent, so the earliest start and the latest stop of a hash make the pair, and `ms` is the time
    between them. A hash with a start and no stop, a stop and no start, or a stop before every start is skipped, one
    for each hash, and so is a pair whose line is not the closed shape the store keeps (ql_store.ops_line) or that the
    leak scan flags. The line's id is derived from the pair's two row ids, so a pass over the same rows writes it once;
    a line whose id `held` has is not written again."""
    lines, bad, seen = [], 0, set(held)
    for s in sessions.values():
        if not s["closed"]:
            continue
        by = {}
        for r in sorted((r for r in s["rows"] if is_agent_row(r)), key=lambda r: (ts_of(r), r["id"])):
            by.setdefault(r.get("agent"), {"agent-start": [], "agent-stop": []})[r["action"]].append(r)
        for agent, kinds in by.items():
            starts, stops = kinds["agent-start"], kinds["agent-stop"]
            a, b = (_epoch_ms(starts[0]["ts"]), _epoch_ms(stops[-1]["ts"])) if starts and stops else (None, None)
            if a is None or b is None or b < a:
                bad += 1
                continue
            rid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"agent.run:{starts[0]['id']}:{stops[-1]['id']}"))
            if rid in seen:
                continue
            seen.add(rid)
            item = next((r["item"] for r in (starts[0], stops[-1]) if r.get("item")), None)
            group = starts[0].get("group") or stops[-1].get("group")
            row = {"id": rid, "ts": stops[-1]["ts"], "event": "agent.run", "group": group, "agent": agent,
                   "item": item, "ms": b - a}
            line = store_.ops_line({k: v for k, v in row.items() if v is not None})
            if line is None or store_.ops_line_leaks(line):
                bad += 1
            else:
                lines.append(line)
    return lines, bad


def worst(verdicts):
    vs = [v for v in verdicts if v in VERDICTS]
    return min(vs, key=VERDICTS.index) if vs else None


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


def row_questions(r):
    """The questions one kb row recorded, in order: the `kb:` hook's or kb_ask.py's `question`, else a kb MCP call's
    `question`, the parts of its `questions`, or its `query`."""
    if r.get("surface") in ("kb_hook", "kb_ask"):
        q = r.get("question")
    else:
        args = r.get("args") if r.get("surface") == "mcp" and isinstance(r.get("args"), dict) else {}
        q = args.get("question") or args.get("questions") or args.get("query")
    qs = q if isinstance(q, list) else [q]
    return [x for x in qs if isinstance(x, str) and x.strip()]


def kb_question(kb):
    """The question the kb was asked, from the first of the kb rows (time order) that names one (row_questions, its
    first). The prompt as typed is never a question. None when no kb row names one."""
    return next((qs[0] for qs in map(row_questions, kb) if qs), None)


@functools.lru_cache(maxsize=512)
def head_pack_text(question):
    """The text of `pack` on this clone's kb for a question; "" when the kb cannot be read."""
    import kbfacts
    try:
        return kbfacts.pack(question, fmt="concise")["text"]
    except Exception:  # noqa: BLE001 - a question pack cannot run keeps no citations; distill goes on
        return ""


def row_lines(r):
    """(the kb lines of one kb row, whether pack re-ran them). A row of format 1 on, or of format 0 with `lines`,
    gives its own `lines`. A row of format 0 without `lines` (written before capture kept them) that names articles
    gets the lines of `pack` on the kb at HEAD for each question it recorded, only those in the articles it recorded;
    no question, or no such line, gives none."""
    if "lines" in r or row_format(r) != 0:
        return (r.get("lines") if isinstance(r.get("lines"), list) else []), False
    arts = {a for a in r.get("articles") or [] if isinstance(a, str)} if isinstance(r.get("articles"), list) else set()
    if not arts:
        return [], False
    out = []
    for q in row_questions(r):
        out += [x for x in pack_lines(head_pack_text(q)) or [] if x["line"].rsplit(":", 1)[0] in arts]
    return out, bool(out)


def citations(kb, answer):
    """(citations, cited) of one lookup: the kb lines its kb rows returned ({line, tag, verdict}, each once; for a
    format 0 row without them, row_lines), those whose path:line the reply's text names when it names any
    (`reply`), else the first ones (`pack`); at most CITATIONS_MAX. Lines that pack re-ran give the first ones,
    `pack`. ([], None) when no line."""
    lines, seen, rerun = [], set(), False
    for r in kb:
        got, again = row_lines(r)
        rerun = rerun or again
        for x in got:
            if not (isinstance(x, dict) and isinstance(x.get("line"), str) and CITATION.fullmatch(x["line"])) \
                    or x["line"] in seen:
                continue
            seen.add(x["line"])
            lines.append({"line": x["line"], "tag": x.get("tag") if x.get("tag") in TAGS else None,
                          "verdict": x.get("verdict") if x.get("verdict") in VERDICTS else None})
    lines = [{key: v for key, v in x.items() if v} for x in lines]
    named = set() if rerun else set(REPLY_CITE.findall(answer or ""))
    used = [x for x in lines if any(x["line"] == n or x["line"].endswith("/" + n) for n in named)]
    if used:
        return used[:CITATIONS_MAX], "reply"
    return lines[:CITATIONS_MAX], ("pack" if lines else None)


def ask_sources(kb):
    """The kb source ids the kb_ask.py rows of one lookup carry in `sources` (the sources whose urls the researcher's
    answer named), each once, sorted, at most SOURCES_MAX; only an id's shape is read, never a url or text."""
    import kbid
    ids = {x for r in kb if r.get("surface") == "kb_ask" and isinstance(r.get("sources"), list)
           for x in r["sources"] if isinstance(x, str) and kbid.SOURCE_ID.fullmatch(x)}
    return sorted(ids)[:SOURCES_MAX]


def rules_fields(r, k):
    """The fields of a `_self` kb_ask row an entry keeps (querylog.md, Store): `root`, `tested`, `set`, `item`,
    `model`, `answer_lines`, `key_missing` and `chars`, each only in its closed shape (a list of unique matches of
    the store's pattern, at most its cap; `key_missing` only when the leak scan finds nothing in its words).
    Anything else the row holds (`sections`, `docs`, `lines`, `budget`) stays out."""
    import redact

    def listed(key, rx, cap):
        v = r.get(key)
        got = [x for x in dict.fromkeys(v) if isinstance(x, str) and rx.fullmatch(x)] if isinstance(v, list) else []
        return got[:cap] or None

    def one(key, rx):
        v = r.get(key)
        return v if isinstance(v, str) and rx.fullmatch(v) else None
    words = listed("key_missing", KEY_WORD, KEY_MISSING_MAX)
    chars = r.get("chars")
    return {"root": RULES_ROOT, "tested": listed("tested", TESTED_ID, TESTED_MAX), "set": one("set", SET_NAME),
            "item": one("item", WORK_ITEM), "model": one("model", NAME),
            "answer_lines": listed("answer_lines", ANSWER_LINE, ANSWER_LINES_MAX),
            "key_missing": None if words and redact.scan(" ".join(words), k) else words,
            "chars": chars if isinstance(chars, int) and not isinstance(chars, bool) and chars >= 0 else None}


def entry_of(rs, k):
    """(entry without the Haiku fields, what Haiku judges or None, why the entry is dropped or None), or None when
    the rows never used the kb. `rs` is one prompt's rows with the tools rows of its window, or a single tools row
    outside every window. The entry's `question` is the kb's own (kb_question), after the rules and the leak scan;
    Haiku judges an entry that has one, from it, the prompt and the reply, which it sees rule-redacted and which are
    never stored."""
    import redact
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
        return ordered({"id": first["id"], "surface": "tool_fetch", "day": ts_of(first)[:10], **item}), None, None
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
             "fetches": sorted(fetches.values(), key=lambda f: json.dumps(f, sort_keys=True)),
             "sources": ask_sources(kb)}
    answer = "\n".join(r["answer"] for r in rs if r.get("surface") == "stop" and isinstance(r.get("answer"), str))
    own = [r for r in kb if r.get("surface") == "kb_ask" and r.get("root") == RULES_ROOT]
    rules = own[0] if own and len(own) == len(kb) else None  # a prompt that also used the public kb is a public entry
    if rules:  # a lookup in the rule docs: no public article or citation, and nothing for Haiku to judge
        entry.update(rules_fields(rules, k))
        entry["articles"], entry["citations"], entry["cited"] = [], [], None
    else:
        entry["citations"], entry["cited"] = citations(kb, answer)
    candidates = entry["articles"]
    if not entry["citations"]:
        entry["articles"] = []  # an article is stored only with the kb lines that back it
    asked = kb_question(kb)
    if asked is None:
        return ordered(entry), None, None
    question = redact.finish(one_line(asked, QUESTION_MAX_CHARS), k)
    if not question:
        return ordered(entry), None, "the leak scan"
    entry["question"] = question[:QUESTION_MAX_CHARS]
    if rules:
        return ordered(entry), None, None
    typed = prompt.get("prompt") if prompt and isinstance(prompt.get("prompt"), str) else ""
    return ordered(entry), {"question": entry["question"], "prompt": typed.strip(), "answer": answer.strip(),
                            "candidates": candidates}, None


def usage_of(rs):
    """The usage record of one prompt's rows: its last `usage` row's, when that row's reader is this code's
    (kbusage.READER_VERSION); else None."""
    rows_ = [r for r in sorted(rs, key=ts_of) if r.get("surface") == "usage"]
    last = rows_[-1] if rows_ else None
    if last is None or last.get("reader") != kbusage.READER_VERSION or not isinstance(last.get("usage"), dict):
        return None
    return {k: v for k, v in last["usage"].items() if k != "routed"}


def routed_of(rs):
    """{item id: sub counts} the last usage row of this reader routes to items (`routed`: the subagents of the prompt
    that worked on a `work/<id>` branch, kbusage.prompt_usage); {} when it routes none, None when `routed` is outside
    the closed shape (an item id, and the `sub` shape the store keeps)."""
    rows_ = [r for r in sorted(rs, key=ts_of) if r.get("surface") == "usage"]
    last = rows_[-1] if rows_ else None
    if last is None or last.get("reader") != kbusage.READER_VERSION or not isinstance(last.get("usage"), dict):
        return {}
    routed = last["usage"].get("routed", {})
    zero = {"other": dict.fromkeys(store_.USAGE_COUNTS, 0)}
    if not (isinstance(routed, dict) and all(isinstance(i, str) and WORK_ITEM.fullmatch(i) and isinstance(sub, dict)
                                             and sub and store_.usage_counts({"main": zero, "sub": sub, "start": 0}) is not None
                                             for i, sub in routed.items())):
        return None
    return routed


# ---------------------------------------------------------------- work windows

def work_windows(rows):
    """({prompt id: the items whose window holds it}, the items the rows claimed), the prompts in the order they began.
    The windows of `ql_capture.usage_targets`: a prompt is inside an item's window when the item was open as the
    prompt began, or the prompt's own row claims it, or closes it with `done` or `release`; a `done` or `release` with
    no open claim in these rows opens and closes nothing. Windows of several items may overlap."""
    inside, worked, open_items = {}, set(), set()
    for r in rows:
        pid = r.get("prompt_id")
        if r.get("surface") == "usage" or not isinstance(pid, str):
            continue
        inside.setdefault(pid, set(open_items))
        item = r.get("item") if r.get("surface") == "work" else None
        if not (isinstance(item, str) and WORK_ITEM.fullmatch(item)):
            continue
        if r.get("action") == "claim":
            open_items.add(item)
            worked.add(item)
            inside[pid].add(item)
        elif r.get("action") in ("done", "release") and item in open_items:
            open_items.discard(item)
            inside[pid].add(item)
    return inside, worked


def rework_windows(rows):
    """{prompt id: the items in rework at it}, for the prompts in the order they began: an item is in rework from the
    prompt of its first `refused` row (a `backlog.py done` that exited 1) while its window is open, up to the prompt
    that closes it with `done` or `release`, both included. A `refused` row of an item with no open claim in these
    rows is none, and a later `claim` of an item that was released starts a window with no rework: the windows are
    those of work_windows, and a session's refusals never carry into another session's rows."""
    out, open_items, refused = {}, set(), set()
    for r in rows:
        pid = r.get("prompt_id")
        if r.get("surface") == "usage" or not isinstance(pid, str):
            continue
        out.setdefault(pid, set(refused))
        item = r.get("item") if r.get("surface") == "work" else None
        if not (isinstance(item, str) and WORK_ITEM.fullmatch(item)):
            continue
        action = r.get("action")
        if action == "claim":
            open_items.add(item)
        elif action == "refused" and item in open_items:
            refused.add(item)
            out[pid].add(item)
        elif action in ("done", "release") and item in open_items:
            open_items.discard(item)
            refused.discard(item)
    return out


def sprint_finder(directory=None):
    """sprint_of(item id): the sprint of a backlog item read from its file in `directory` (default: the clone's
    kb/_self/backlog): its own `sprint`, else that of the nearest item above it with one (the story or bug of a task),
    a sprint being its own; None when no file names one (a clone without the backlog, an item whose sprint was closed
    and its files deleted). Reads the files only; a sprint is stored as its id alone."""
    d = Path(directory) if directory else HOME / BACKLOG_REL

    def sprint_of(item):
        cur, seen = item, set()
        while isinstance(cur, str) and WORK_ITEM.fullmatch(cur) and cur not in seen:
            seen.add(cur)
            if cur.startswith("SP-"):
                return cur
            obj = read_json(d / f"{cur}.json", None)
            if not isinstance(obj, dict):
                return None
            sprint = obj.get("sprint")
            if isinstance(sprint, str) and WORK_ITEM.fullmatch(sprint) and sprint.startswith("SP-"):
                return sprint
            cur = obj.get("parent")
        return None
    return sprint_of


def work_lines_of(windows, sprint_of=None):
    """The lines one prompt's counts go to, once: the item of its one window; for several windows (a session holding
    several claims) the sprint they all belong to, never one item of them; the session's shared line, here the empty
    set, for no window or when the items do not all belong to one sprint (`sprint_of(item)`, None: unknown)."""
    if len(windows) <= 1:
        return set(windows)
    sprints = {sprint_of(i) if sprint_of else None for i in windows}
    return sprints if len(sprints) == 1 and None not in sprints else set()


def add_sub(tally, sub):
    """The `sub` counts of a subagent routed to an item, added into `tally` without a prompt (the subagent is no
    prompt of the item's window)."""
    store_.tally_add(tally, ({}, sub))
    tally["prompts"] -= 1


def session_work(rows, done, items, sprint_of=None, rework=None, interrupts=None):
    """One closed session's work: (its shared line or None, the window prompts without usage, the prompt ids
    counted). Each prompt not in `done` with a usage record of this reader (usage_of) adds its counts to the tally of
    the line work_lines_of names (`items`: {item or sprint: tally}, which the run's sessions share), or to the
    session's shared tally when that is none; the subagents the record routes to items (routed_of) add their counts
    to those items' tallies. A session that claimed no item is unrecorded. `rework` ({item: tally}, shared by the
    run's sessions like `items`) also takes the counts that fall in an item's rework (rework_windows): a prompt of
    one window only, and a subagent routed to an item, in rework at that prompt; a prompt in several windows counts
    on its sprint's line with no split."""
    rework = {} if rework is None else rework
    interrupts = {} if interrupts is None else interrupts  # {item: interrupted calls in its window's prompts}
    inside, worked = work_windows(rows)
    if not worked:
        return None, 0, set()
    again = rework_windows(rows)
    by_prompt = {}
    for r in rows:
        if isinstance(r.get("prompt_id"), str):
            by_prompt.setdefault(r["prompt_id"], []).append(r)
    shared, missing, counted = store_.new_tally(), 0, set()
    for pid, windows in inside.items():
        if pid in done:
            continue
        usage = usage_of(by_prompt[pid])
        counts = store_.usage_counts(usage) if usage else None
        routed = routed_of(by_prompt[pid]) if counts else None
        if counts is None or routed is None:
            missing += 1 if windows else 0
            continue
        counted.add(pid)
        lines = work_lines_of(windows, sprint_of)
        cut = sum(1 for r in by_prompt[pid] if r.get("surface") == "work" and r.get("action") == "interrupt")
        if cut and len(windows) == 1:  # a prompt of one item's window: its interrupted calls are that item's
            (item,) = windows
            interrupts[item] = interrupts.get(item, 0) + cut
        for key in lines:
            store_.tally_add(items.setdefault(key, store_.new_tally()), counts)
            if len(windows) == 1 and key in again[pid]:
                store_.tally_add(rework.setdefault(key, store_.new_tally()), counts)
        if not lines:
            store_.tally_add(shared, counts)
        for item, sub in routed.items():
            add_sub(items.setdefault(item, store_.new_tally()), sub)
            if item in again[pid]:
                add_sub(rework.setdefault(item, store_.new_tally()), sub)
    return (store_.work_line("items", sorted(worked), shared) if shared["prompts"] else None), missing, counted


def plan_work(sessions, worked, sprint_of=None):
    """(the work sidecar's lines, the window prompts without usage, {session id: prompt ids counted}) of the closed
    sessions: the items' lines in id order, then the sessions' shared lines. `worked` ({session id: prompt ids}) holds
    the prompts an earlier run counted, so a session whose rows stayed in the spool is never counted twice;
    `sprint_of` (sprint_finder) names the sprint of an item."""
    items, rework, shared, missing, counted, interrupts = {}, {}, [], 0, {}, {}
    for sid in sorted(sessions):
        if not sessions[sid]["closed"]:
            continue
        line, m, pids = session_work(sessions[sid]["rows"], set(worked.get(sid, ())), items, sprint_of, rework,
                                     interrupts)
        missing += m
        if pids:
            counted[sid] = pids
        if line:
            shared.append(line)
    lines = [store_.work_line("item", i, items[i], rework.get(i), interrupts.get(i, 0)) for i in sorted(items)]
    return lines + sorted(shared, key=lambda ln: json.dumps(ln, sort_keys=True)), missing, counted


# ---------------------------------------------------------------- Haiku

def count_of(v):
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else 0


def haiku_result(stdout):
    """(text, {model: counts}) of a `claude -p --output-format json` result: its `result` text and, from
    `modelUsage` (whole-run counts per model, `claude/ci-and-headless.md`), the counts in the usage record's shape
    (`requests`: the run's `num_turns` for one model, else 1 per model; `cw1h` 0, since the result does not split
    the cache write by lifetime). A stdout that is not such a result (an older CLI) is the text itself with no
    counts; an error result is an OSError. Nothing else of the result is read, and none of it is kept."""
    try:
        r = json.loads(stdout)
    except ValueError:
        return stdout, {}
    if not (isinstance(r, dict) and r.get("type") == "result"):
        return stdout, {}
    if r.get("is_error") or str(r.get("subtype", "")).startswith("error") or not isinstance(r.get("result"), str):
        raise OSError("claude -p returned an error result")
    usage = r.get("modelUsage")
    usage = {m: u for m, u in usage.items() if isinstance(u, dict)} if isinstance(usage, dict) else {}
    models = {}
    for m, u in usage.items():
        c = {"requests": 1, "in": count_of(u.get("inputTokens")), "cw": count_of(u.get("cacheCreationInputTokens")),
             "cw1h": 0, "cr": count_of(u.get("cacheReadInputTokens")), "out": count_of(u.get("outputTokens"))}
        if any(c[k] for k in ("in", "cw", "cr", "out")):
            if len(usage) == 1:
                c["requests"] = max(1, count_of(r.get("num_turns")))
            store_.add_models(models, {kbusage.model_of(m): c})
    return r["result"], models


class Spend:
    """The tokens of one distill run's own `claude -p` calls, per model: what `claude_haiku` counts, written as the
    run's `distill` overhead line (querylog.md, Store)."""

    def __init__(self):
        self.calls, self.models = 0, {}

    def add(self, models):
        """One call's counts (haiku_result); a call that reported none is not counted."""
        if models:
            self.calls += 1
            store_.add_models(self.models, models)

    def lines(self):
        """The overhead lines of the run: one for `distill`, or none when no call reported counts."""
        line = store_.overhead_line("distill", self.calls, self.models) if self.calls else None
        return [line] if line else []


def claude_haiku(prompt, spend=None):
    """One `claude -p` call of the Haiku stage (redact.names_argv: hooks off, no tools, no user plugins or MCP
    servers, and `--output-format json` so the result carries the call's token counts), in an empty directory so no
    project instructions load; the reply's text, and the counts added to `spend`. OSError when it cannot answer."""
    import redact
    text, models = haiku_result(claude_p(redact.names_argv(HAIKU_MODEL) + ["--output-format", "json"], prompt,
                                         HAIKU_TIMEOUT_S))
    if spend is not None:
        spend.add(models)
    return text


def haiku_items(texts, candidates, k):
    """The batch Haiku judges: per entry the question the entry stores, and the rule-redacted prompt and reply, each
    cut to HAIKU_TEXT_MAX_CHARS, only to judge (querylog.md, Redaction); nothing Haiku writes is stored."""
    import redact
    return [{"i": i, "question": t["question"], "prompt": redact.redact(t["prompt"], k)[:HAIKU_TEXT_MAX_CHARS],
             "answer": redact.redact(t["answer"], k)[:HAIKU_TEXT_MAX_CHARS], "candidates": c}
            for i, (t, c) in enumerate(zip(texts, candidates))]


def parse_distill(reply, items):
    """[{judged, best, identifying}] of a Haiku reply; ValueError when it is not that JSON. Any other field of the
    reply (free text included) is left out, and a `best` that is not one of the entry's candidates becomes null:
    Haiku judges only among what code listed, and writes nothing that is stored."""
    a, b = reply.find("["), reply.rfind("]")
    if a < 0 or b < a:
        raise ValueError("no JSON array in the reply")
    got = json.loads(reply[a:b + 1])
    if not isinstance(got, list) or len(got) != len(items):
        raise ValueError(f"expected {len(items)} entries")
    out = []
    for i, (r, it) in enumerate(zip(got, items)):
        if not isinstance(r, dict) or r.get("i") != i or r.get("judged") not in JUDGED \
                or not isinstance(r.get("identifying"), bool) \
                or not (r.get("best") is None or isinstance(r.get("best"), str)):
            raise ValueError(f"entry {i} is malformed")
        out.append({"judged": r["judged"], "best": r.get("best") if r.get("best") in it["candidates"] else None,
                    "identifying": r["identifying"]})
    return out


def judged(r):
    """The Haiku fields one entry stores ({judged, best}), or None to drop it (Haiku found it identifying)."""
    return None if r["identifying"] else {"judged": r["judged"], "best": r["best"]}


# ---------------------------------------------------------------- the run

def distill(qdir=None, cfg=None, haiku=None, now_dt=None, run_id=None, kb_commit=None, settle=0.0, out=print,
            deliver=None, usage_from=None):
    """One distill: 0 done (or nothing to do, or logging off), 1 when the push of mode `auto` failed, 3 when another
    distill holds the lock. Mode `auto` keeps the spool rows of the entries it writes and then runs
    `deliver(qdir, out)` under the same lock (default: the push of `apply --push`, from the clone, or in a plugin
    host from its managed clone), which deletes them once their run file is on origin/main; mode `local` deletes
    them at once. `usage_from` (session id, transcript path): the `usage` rows of that session are written first
    (add_usage), waiting up to USAGE_LOCK_WAIT_S for the lock."""
    d, c = places()
    qdir, cfg = Path(qdir or d), Path(cfg or c)
    mode = read_mode(cfg)
    if logging_off(qdir, cfg):
        out("distill: logging is off")
        return 0
    if mode == "auto" and deliver is None:
        import ql_deliver
        if qdir.resolve() == (HOME / "_cache" / "querylog").resolve():
            def deliver(q, say):
                return ql_deliver.Pusher(HOME, q, run_cmd, None, say)()
        elif plugin_data() is not None and qdir.resolve() == d.resolve():
            def deliver(q, say):
                return ql_deliver.host_push(q, run_cmd, None, say)
    if mode != "auto":
        deliver = None
    lock = acquire(qdir)
    waited = 0.0
    while lock is None and usage_from and waited < USAGE_LOCK_WAIT_S:
        time.sleep(USAGE_LOCK_POLL_S)
        waited += USAGE_LOCK_POLL_S
        lock = acquire(qdir)
    if lock is None:
        out("distill: another distill holds the lock")
        return 3
    try:
        if settle:
            time.sleep(settle)
        if usage_from:
            n = add_usage(qdir / "spool", *usage_from)
            if n:
                out(f"distill: usage rows written: {n}")
        now_dt = now_dt or datetime.datetime.now(datetime.timezone.utc)
        spend = Spend()
        rc = _distill(qdir, haiku or functools.partial(claude_haiku, spend=spend), now_dt, run_id, kb_commit, out,
                      keep=deliver is not None, spend=spend)
        if deliver is not None:
            rc = 1 if deliver(qdir, out) not in (0, None) else rc
        return rc
    finally:
        release(lock)


def _plan(qdir, t_now, today, k):
    """One reading of the spool: (spool, sessions, tools, consumed, todo, skipped), `todo` holding one item {entry,
    texts, sid, key, tools, ts} per kb lookup of a closed session or of a finished day, in time order, and `skipped`
    the rows distill does not read ({file name: count}) in the files of the closed sessions and the finished days."""
    spool = qdir / "spool"
    sessions, tools, bad = read_spool(spool, t_now)
    skipped = {n: c for n, c in bad.items()
               if (n[6:16] < today if n.startswith("tools-") else sessions.get(n[:-6], {}).get("closed"))}
    consumed = {n: set(ids) for n, ids in read_json(qdir / CONSUMED_NAME, {}).items()
                if n in tools and isinstance(ids, list)}
    for s in sessions.values():
        s["groups"] = groups(s)
    attached, left = assign(sessions, {n: [r for r in rs if r.get("surface") != OPS] for n, rs in tools.items()},
                            consumed)  # an ops row joins no prompt: plan_ops reads it from `tools`

    todo = []  # {entry, texts, sid, key, tools}: one per kb lookup of a closed session or a finished day
    for sid, s in sessions.items():
        if not s["closed"]:
            continue
        for key, rs, _, _ in s["groups"]:
            extra = attached.get((sid, key), [])
            built = entry_of(rs + [r for _, r in extra], k)
            if built:
                todo.append({"entry": built[0], "texts": built[1], "drop": built[2], "sid": sid, "key": key,
                             "tools": extra, "ts": ts_of(rs[0]), "usage": usage_of(rs)})
            else:
                s.setdefault("skipped", []).append(extra)  # tools rows of a prompt that never used the kb
    for name, rs in left.items():
        if name[6:16] >= today:
            continue  # tools rows outside every window wait for their day to end
        for r in rs:
            built = entry_of([r], k)
            if built:
                todo.append({"entry": built[0], "texts": built[1], "drop": built[2], "sid": None, "key": None,
                             "tools": [(name, r)], "ts": ts_of(r)})
            else:
                consumed.setdefault(name, set()).add(r["id"])
    todo.sort(key=lambda t: (t["ts"], t["entry"]["id"]))
    return spool, sessions, tools, consumed, todo, skipped


def _distill(qdir, haiku, now_dt, run_id, kb_commit, out, keep=False, spend=None):
    """The run file of the closed sessions (entries a run file of the local store already holds are not distilled
    again), then the spool: the rows of dropped entries go, and so do those of written ones unless `keep`. `spend`
    holds the tokens of the run's own Haiku calls, which become its overhead line."""
    k = None  # the known ids of the public root (redact.known) are read when an entry first needs them
    t_now, today = now_dt.timestamp(), now_dt.date().isoformat()
    spool, sessions, tools, consumed, todo, skipped = _plan(qdir, t_now, today, k)
    stored = {e["id"] for _, e in store_.store_entries(qdir / "store")}
    done = [t for t in todo if t["entry"]["id"] in stored]
    todo = [t for t in todo if t["entry"]["id"] not in stored]

    dropped = [t for t in todo if t["drop"]]  # the leak scan caught its question
    need = [t for t in todo if t["texts"] and not t["drop"]]
    written = [t for t in todo if not t["texts"] and not t["drop"]]
    waiting = []
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
        items = haiku_items([t["texts"] for t in batch], [t["texts"]["candidates"] for t in batch], k)
        try:
            reply = haiku(DISTILL_TASK + "\n\n" + json.dumps(items, ensure_ascii=False))
        except (OSError, subprocess.SubprocessError) as e:
            out(f"distill: Haiku call failed ({type(e).__name__}); its entries wait")
            waiting += [t for b in batches[n:] for t in b]
            break
        try:
            results = [judged(r) for r in parse_distill(reply, items)]
        except ValueError:
            dropped += batch  # a reply that is not the expected JSON drops its batch
            continue
        for t, res in zip(batch, results):
            if res is None:
                dropped.append(t)
            else:
                t["entry"] = ordered({**t["entry"], **res})
                written.append(t)

    held = store_.ops_ids(qdir / "store")
    ops_lines, ops_bad, ops_read = plan_ops(tools, consumed, held)
    agent_lines, agent_bad = plan_agents(sessions, held)
    ops_lines = sorted(ops_lines + agent_lines, key=lambda ln: (ln["ts"], ln["id"]))
    ops_bad += agent_bad  # an agent that never started or never stopped is a pair distill cannot read
    counts = {"entries": len(written), "dropped": len(dropped), "waiting": len(waiting)}
    if skipped or ops_bad:  # an ops row outside the closed shape is a row distill cannot read
        counts[SKIPPED_KEY] = sum(skipped.values()) + ops_bad
    worked = read_json(qdir / WORKED_NAME, {})
    worked = {sid: ids for sid, ids in worked.items() if sid in sessions and isinstance(ids, list)} \
        if isinstance(worked, dict) else {}
    work_lines, work_missing, work_counted = plan_work(sessions, worked, sprint_finder())
    overhead = spend.lines() if spend is not None else []
    if written or dropped or skipped or work_lines or overhead or ops_lines or ops_bad:
        run_id = run_id or f"{now_dt.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
        written.sort(key=lambda t: (t["ts"], t["entry"]["id"]))
        write_text(store_.run_path(qdir / "store", run_id),
                   json_lines([store_.header(run_id, counts, kb_commit)] + [t["entry"] for t in written]))
        lines = [ln for ln in (store_.usage_line(t["entry"]["id"], t.get("usage")) for t in written) if ln]
        store_.write_usage(qdir / "store", run_id, lines, len(written) - len(lines), kbusage.READER_VERSION)
        store_.write_work(qdir / "store", run_id, work_lines + overhead, work_missing, kbusage.READER_VERSION)
        store_.write_ops(qdir / "store", run_id, ops_lines)
        for sid, pids in work_counted.items():
            worked[sid] = sorted(set(worked.get(sid, ())) | pids)
        out(f"distill: run={run_id} entries={counts['entries']} dropped={counts['dropped']} "
            f"waiting={counts['waiting']}" + (f" skipped={counts[SKIPPED_KEY]}" if SKIPPED_KEY in counts else "")
            + (f" usage={len(lines)}" if lines else "") + (f" work={len(work_lines)}" if work_lines else "") + (f" overhead={len(overhead)}" if overhead else "")
            + (f" ops={len(ops_lines)}" if ops_lines else ""))
    else:
        out(f"distill: nothing to write (waiting={counts['waiting']})")
    for name, i in ops_read:
        consumed.setdefault(name, set()).add(i)
    text = json.dumps(dict(sorted(worked.items()))) + "\n"
    if (worked or (qdir / WORKED_NAME).exists()) and text != _text(qdir / WORKED_NAME):
        write_text(qdir / WORKED_NAME, text)
    if keep:
        _settle(spool, sessions, tools, consumed, qdir, today, dropped, waiting + written + done, skipped)
        if written or done:
            from ql_deliver import BRANCH, REMOTE
            out(f"distill: the spool keeps the rows of {len(written) + len(done)} entries until their run file is "
                f"on {REMOTE}/{BRANCH}")
    else:
        _settle(spool, sessions, tools, consumed, qdir, today, written + dropped + done, waiting, skipped)
    return 0


def uncounted_work(rows, done):
    """Whether a session's rows hold a prompt inside a work window that `done` (the prompt ids worked.json holds for
    it) does not list: a prompt no work sidecar counted."""
    inside, _ = work_windows(rows)
    return any(windows and pid not in done for pid, windows in inside.items())


def _settle(spool, sessions, tools, consumed, qdir, today, gone, stay, skipped=None, work_pending=False):
    """The spool after a pass: the rows of the `gone` entries and of the prompts that never used the kb go, the rows
    of the `stay` entries stay (a closed session keeps its window end), a finished day's tools file goes once all
    its rows are consumed, and the `skipped` rows (counted in this pass) go from the files that stay. With
    `work_pending` (a settle outside a distill pass: no plan_work counted the sessions) a closed session with work
    prompts that worked.json does not hold stays whole, for the pass that counts them."""
    wait_keys = {(t["sid"], t["key"]) for t in stay if t["sid"]}
    worked = read_json(qdir / WORKED_NAME, {})
    worked = worked if isinstance(worked, dict) else {}
    for t in gone:
        for name, r in t["tools"]:
            consumed.setdefault(name, set()).add(r["id"])
    for sid, s in sessions.items():
        if not s["closed"]:
            continue
        if work_pending and uncounted_work(s["rows"], set(worked.get(sid) or ())):
            continue  # the whole file waits for the pass that counts its work
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
                write_text(s["path"], json_lines(keep))
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
        elif name in (skipped or {}):  # a finished day's file, which no capture appends to any more
            write_text(spool / name, json_lines(rs))
    if consumed or (qdir / CONSUMED_NAME).exists():
        write_text(qdir / CONSUMED_NAME, json.dumps({n: sorted(ids) for n, ids in sorted(consumed.items())}) + "\n")


def spool_delivered(qdir, ids, now_dt=None):
    """Delete the spool rows of the entries `ids`, whose run file is on origin/main; every other entry's rows stay.
    The number of entries whose rows went. Runs under the distill lock (distill and apply --push hold it)."""
    ids = set(ids)
    if not ids or not (Path(qdir) / "spool").is_dir():
        return 0
    now_dt = now_dt or datetime.datetime.now(datetime.timezone.utc)
    today = now_dt.date().isoformat()
    spool, sessions, tools, consumed, todo, _ = _plan(Path(qdir), now_dt.timestamp(), today, None)
    gone = [t for t in todo if t["entry"]["id"] in ids]
    if gone:
        _settle(spool, sessions, tools, consumed, Path(qdir), today, gone,
                [t for t in todo if t["entry"]["id"] not in ids], work_pending=True)
    return len(gone)


# ---------------------------------------------------------------- the SessionEnd and SessionStart launcher

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
    closed; when the session has a spool file and the event names its transcript, the distill it starts gets the
    session id and the transcript path (`--session`, `--transcript`) and waits for the lock. Otherwise nothing starts
    when logging is off, nothing is ready, or a distill holds a fresh lock."""
    if not isinstance(event, dict) or event.get("hook_event_name") not in ("SessionEnd", "SessionStart"):
        return None
    qdir, cfg = places()
    if logging_off(qdir, cfg):
        return None
    spool = qdir / "spool"
    sid = event.get("session_id")
    argv = [sys.executable, str(ENTRY), "distill", "--settle", str(LAUNCH_SETTLE_S)]
    if event["hook_event_name"] == "SessionEnd" and isinstance(sid, str) and SAFE_SESSION.fullmatch(sid) \
            and (spool / f"{sid}.jsonl").exists():
        (spool / f"{sid}.end").touch()
        transcript = event.get("transcript_path")
        if isinstance(transcript, str) and transcript:
            return detach(argv + ["--session", sid, "--transcript", transcript], qdir / LOG_NAME)
    if not ready(spool, time.time()):
        return None
    age = lock_age(qdir / LOCK_NAME)
    if age is not None and age < LOCK_STALE_S:
        return None
    return detach(argv, qdir / LOG_NAME)
