"""The query log's store (kb/_self/querylog.md, Store): the run files and findings files under kb/_querylog/ (or a
local store laid out the same way), their readers and writers, and the gates `querylog.py check` runs over them.

  <yyyy-mm>/<run-id>.jsonl            a header line (HEADER_KEYS), then one entry per line (ENTRY_KEYS)
  findings/<yyyy-mm>/<run-id>.jsonl   the same header, then one record per finding whose state the run changed
  usage/<yyyy-mm>/<run-id>.jsonl      the usage sidecar of a run file: a header (USAGE_HEADER_KEYS), then one line per
                                      entry with token counts (USAGE_KEYS)
  work/<yyyy-mm>/<run-id>.jsonl       the work sidecar of a run file: a header (WORK_HEADER_KEYS), then one line per
                                      item worked (WORK_ITEM_KEYS), one per session that worked one (WORK_SHARED_KEYS)
                                      and one per kind of the kb's own background runs (WORK_OVERHEAD_KEYS)
  ops/<yyyy-mm>/<run-id>.jsonl        the ops sidecar of a run file: a header (OPS_HEADER_KEYS), then one line per
                                      operational row of the spool (ql_capture.OPS_EVENTS): names, exit codes,
                                      milliseconds, item ids, short shas and test file names, never free text
"""
import datetime, hashlib, json, re, subprocess
from pathlib import Path

from ql_base import HOME, PIPELINE_VERSION, STORE, json_lines, write_text
from ql_capture import ARG_MAX_CHARS, OPS, OPS_COUNT_MAX, OPS_EVENTS, TAGS, VERDICTS, WORK_ITEM, ops_problems

HEADER_KEYS = ("run", "pipeline", "retrieval", "kb_commit", "counts")
COUNT_KEYS = ("entries", "dropped", "waiting")
SKIPPED_KEY = "skipped"  # a count a header holds only when distill skipped spool rows
ENTRY_KEYS = ("id", "surface", "day", "intent", "tools", "route", "question", "verdict", "articles", "citations",
              "cited", "judged", "best", "fetches", "sources", "tool", "fetcher", "host", "path", "outcome", "chars",
              "root", "tested", "set", "item", "model", "answer_lines", "key_missing")
RULES_ROOT = "_self"  # the `root` of a kb_ask row of a lookup in the kb's own rule docs (kb/_self)
RULES_KEYS = ("root", "tested", "set", "item", "model", "answer_lines", "key_missing")  # an entry holds them only with `root`
CITATION_KEYS = ("line", "tag", "verdict")
CITED = ("reply", "pack")  # the citations the reply named, else the pack's first lines
FREE_TEXT_KEYS = ("summary",)  # an outcome in words: the entry's citations say what the kb gave
INTENTS = ("lookup", "skill", "change")
FETCH_KEYS = ("tool", "fetcher", "host", "path", "outcome", "n", "chars")
RAW_KEYS = ("prompt", "answer", "session_id", "prompt_id", "transcript_path", "cwd", "user", "hostname", "command",
            "args", "ts")  # spool fields a run file never holds
SURFACES = ("prompt", "kb_hook", "mcp", "kb_ask", "tool_fetch", "fetch", "stop")
ROW_SURFACES = SURFACES + ("usage", "work", OPS)  # spool rows; `usage`, `work` and `ops` rows go to the sidecars, never an entry
TEXT_KEYS = ("question",)
JUDGED = ("answered", "partly", "missed")
QUESTION_MAX_CHARS = 500
CITATIONS_MAX = 5  # kb lines an entry keeps
SOURCES_MAX = 10  # kb source ids an entry keeps: those a kb_ask.py researcher's answer named (never the urls)
TESTED_MAX = 40  # tested-question ids a rules entry keeps
ANSWER_LINES_MAX = 12  # kb/_self lines a rules entry keeps of the reader's answer
KEY_MISSING_MAX = 12  # key words no printed passage held that a rules entry keeps
TESTED_ID = re.compile(r"[A-Z]{2,4}\d{0,2}-\d{1,4}")  # a tested question's id in kb/_self/_retrieval/lookup_eval.csv
SET_NAME = re.compile(r"[a-z0-9][a-z0-9:_.-]{0,59}")  # a set of tested questions: `skill`, `skill:step`, `kb-item:land`
ANSWER_LINE = re.compile(r"kb/_self/[\w.-]+\.md:[1-9]\d*")
KEY_WORD = re.compile(r"[\w.-]{1,40}")
DAY = re.compile(r"\d{4}-\d{2}-\d{2}")
OUTCOME = re.compile(r"http-[1-5]\d\d|empty|redirect-cross-host|truncated|error|unknown")
RUN_ID = re.compile(r"(\d{4})(\d{2})\d{2}T\d{6}Z-[0-9a-f]{8}")
ENTRY_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
COMMIT = re.compile(r"[0-9a-f]{7,64}")
NAME = re.compile(r"[A-Za-z0-9_.-]{1,80}")  # a tool or fetcher name: never command text
ARTICLE = re.compile(r"[\w-]+(?:/[\w.-]+)+")
CITATION = re.compile(r"[\w-]+(?:/[\w.-]+)+:[1-9]\d*")  # root/path:line
HOSTNAME = re.compile(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{0,61}[a-z0-9]")
URL_PATH = re.compile(r"/[^\s?#]{0,%d}" % (ARG_MAX_CHARS - 1))
PRIVATE_TLDS = ("local", "lan", "corp", "internal", "intra", "home", "localdomain", "arpa", "localhost", "test",
                "invalid", "example")

FINDINGS = "findings"
FINDING_KINDS = ("eval", "alias", "expansion", "gap", "source", "rules")
FIX_KINDS = ("alias", "expansion")
LEARN_STATES = ("open", "fixed-since")  # the states learn writes; a record in any other state is apply's to change
APPLY_STATES = ("applied", "rejected", "no-fix")  # fix written / fix failed its gates / a miss with no accepted fix
APPLY_FAILED = "apply-failed"  # its automatic commit turned CI red and was reverted (apply --push)
FINDING_STATES = LEARN_STATES + APPLY_STATES + (APPLY_FAILED,)
STAGES = ("miss", "candidate-gap", "gap", "candidate-fact", "claim")
PROMOTERS = ("learn", "apply", "research", "kb-research")  # kb-research: a person's `/kb-research --queue` run
SIGNALS = ("stage", "route")  # a host that needs staging, a fetch by a tool its route avoids
FINDING_ID = re.compile(r"F-[0-9a-f]{12}")
FINDING_KEYS = ("id", "kind", "state", "stage", "promotions", "entry", "expect", "article", "terms", "tried", "signal",
                "host", "level", "needs", "triggers", "tool", "route", "observed")
CLOSED_STAGE = "claim"  # a gap finding at this stage is closed: its _gaps.md entry is resolved

USAGE = "usage"
USAGE_HEADER_KEYS = ("run", "reader", "counts")
USAGE_COUNT_KEYS = ("entries", "missing")
USAGE_KEYS = ("id", "main", "sub", "start", "steps", "cut")
USAGE_COUNTS = ("requests", "in", "cw", "cw1h", "cr", "out")
USAGE_STEP_KEYS = ("tools", "grow")
USAGE_TOOL_KEYS = ("tool", "ok", "chars")

WORK = "work"
WORK_HEADER_KEYS = ("run", "reader", "counts")
WORK_COUNT_KEYS = ("items", "shared", "missing")
WORK_ITEM_KEYS = ("item", "prompts", "main", "sub", "rework", "interrupts")  # one item worked: its window prompts' summed counts
WORK_REWORK_KEYS = ("prompts", "main", "sub")  # an item line's `rework`: the part of its counts from its first refused done
WORK_SHARED_KEYS = ("items", "prompts", "main", "sub")  # one session that worked items: its prompts outside any window
WORK_OVERHEAD_KEYS = ("overhead", "calls", "main")  # one kind of the kb's own background runs: no item, no prompt
OVERHEAD_KINDS = ("distill", "digest", "eval", "census")  # the background runs a line may name (usage.md)
OVERHEAD_COUNT_KEY = "overhead"  # a header count that is there only when the file has an overhead line
SAMPLE_ENTRY_ID = "00000000-0000-4000-8000-000000000000"  # a stand-in id, to read a usage record with usage_line

OPS_HEADER_KEYS = ("run", "counts")
OPS_COUNT_KEYS = ("rows",)
OPS_LINE_KEYS = ("id", "ts", "event")  # an ops line: these, then the keys of its event (ql_capture.OPS_EVENTS)
OPS_TS = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z")  # the spool's time format


# ---------------------------------------------------------------- reading

def run_files(store):
    """The run files of a store: <yyyy-mm>/<run-id>.jsonl (findings/ has its own layout)."""
    store = Path(store)
    return sorted(p for p in store.glob("*/*.jsonl") if p.parent.name != FINDINGS) if store.is_dir() else []


def findings_files(store):
    """The findings files of a store, oldest run first: findings/<yyyy-mm>/<run-id>.jsonl."""
    d = Path(store) / FINDINGS
    return sorted(d.glob("*/*.jsonl"), key=lambda p: p.stem) if d.is_dir() else []


def usage_files(store):
    """The usage sidecars of a store, oldest run first: usage/<yyyy-mm>/<run-id>.jsonl."""
    d = Path(store) / USAGE
    return sorted(d.glob("*/*.jsonl"), key=lambda p: p.stem) if d.is_dir() else []


def work_files(store):
    """The work sidecars of a store, oldest run first: work/<yyyy-mm>/<run-id>.jsonl."""
    d = Path(store) / WORK
    return sorted(d.glob("*/*.jsonl"), key=lambda p: p.stem) if d.is_dir() else []


def ops_files(store):
    """The ops sidecars of a store, oldest run first: ops/<yyyy-mm>/<run-id>.jsonl."""
    d = Path(store) / OPS
    return sorted(d.glob("*/*.jsonl"), key=lambda p: p.stem) if d.is_dir() else []


def usage_records(store):
    """{entry id: usage line} of the store's usage sidecars, each id once (its first sidecar)."""
    out = {}
    for _, objs in records(usage_files(store)):
        for _, u in objs:
            if isinstance(u.get("id"), str):
                out.setdefault(u["id"], u)
    return out


def load_run(p):
    """[(line number, object)] of a run or findings file; ValueError naming the first line that is not a JSON
    object."""
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


def records(files):
    """(file, [(line number, object)] after its header) of each file that reads; the others are left to `check`."""
    for p in files:
        try:
            objs = load_run(p)
        except (OSError, ValueError):
            continue
        yield p, objs[1:]


def store_entries(store):
    """[(run id, entry)] of the store's run files, each entry id once (its first run)."""
    out, seen = [], set()
    for p, objs in records(run_files(store)):
        for _, e in objs:
            if isinstance(e.get("id"), str) and e["id"] not in seen:
                seen.add(e["id"])
                out.append((p.stem, e))
    return out


def run_ids(store):
    """The run ids of a store, oldest first: those of its run files and of its usage, work and ops sidecars."""
    return sorted({p.stem for p in run_files(store) + usage_files(store) + work_files(store) + ops_files(store)})


def resolve_id(names, given):
    """(the one name `given` is or starts with, the names it starts): an exact name wins over a longer one it prefixes;
    the first is None when no name, or more than one, starts with `given`."""
    hits = [n for n in names if n.startswith(given)]
    if given in hits:
        return given, hits
    return (hits[0] if len(hits) == 1 else None), hits


def finding_states(store):
    """{finding id: its last record} across the store's findings files, in run order."""
    last = {}
    for _, objs in records(findings_files(store)):
        for _, rec in objs:
            if isinstance(rec.get("id"), str):
                last[rec["id"]] = rec
    return last


def failed_counts(store):
    """{finding id: how many apply-failed records it has} across the store's findings files."""
    out = {}
    for _, objs in records(findings_files(store)):
        for _, rec in objs:
            if rec.get("state") == APPLY_FAILED and isinstance(rec.get("id"), str):
                out[rec["id"]] = out.get(rec["id"], 0) + 1
    return out


def finding_id(*parts):
    return "F-" + hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------- writing

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


def header(run_id, counts, kb_commit=None):
    """A run or findings file's header: the run's provenance, once per file."""
    return {"run": run_id, "pipeline": PIPELINE_VERSION, "retrieval": retrieval_version(),
            "kb_commit": kb_commit or head_commit(), "counts": counts}


def run_path(store, run_id, findings=False, usage=False, work=False, ops=False):
    sub = FINDINGS if findings else USAGE if usage else WORK if work else OPS if ops else ""
    return Path(store) / sub / f"{run_id[:4]}-{run_id[4:6]}" / f"{run_id}.jsonl"


def usage_line(entry_id, usage):
    """The sidecar line of one entry from a `usage` spool row's record, or None when the record is not the closed
    shape the store keeps (usage_problems)."""
    if not isinstance(usage, dict):
        return None
    line = {"id": entry_id, **{k: usage[k] for k in USAGE_KEYS[1:] if k in usage}}
    return None if usage_line_problems(line, "") or set(usage) - set(USAGE_KEYS[1:]) else line


def write_usage(store, run_id, lines, missing, reader):
    """The usage sidecar of run `run_id`: a header (the run, the transcript reader's version, counts), then one line
    per entry that has usage. Nothing is written without a line."""
    if not lines:
        return None
    path = run_path(store, run_id, usage=True)
    write_text(path, json_lines([{"run": run_id, "reader": reader,
                                  "counts": {"entries": len(lines), "missing": missing}}] + lines))
    return path


def usage_counts(usage):
    """(main, sub) of a usage record that is the closed shape the store keeps, else None."""
    line = usage_line(SAMPLE_ENTRY_ID, usage)
    return None if line is None else (line["main"], line.get("sub", {}))


def add_models(into, models):
    """Add per-model counts (`{model: {requests, in, cw, cw1h, cr, out}}`) into `into`."""
    for m, c in models.items():
        t = into.setdefault(m, dict.fromkeys(USAGE_COUNTS, 0))
        for k in USAGE_COUNTS:
            t[k] += c[k]


def new_tally():
    """An empty tally of prompts and their counts (work_line)."""
    return {"prompts": 0, "main": {}, "sub": {}}


def tally_add(tally, counts):
    """One prompt's (main, sub) counts (usage_counts) added into `tally`."""
    main, sub = counts
    tally["prompts"] += 1
    add_models(tally["main"], main)
    for g, models in sub.items():
        add_models(tally["sub"].setdefault(g, {}), models)


def work_counts(tally):
    """The counts of a tally in their sorted order: `prompts`, `main`, and `sub` only when a subagent ran."""
    sort = lambda models: {m: models[m] for m in sorted(models)}  # noqa: E731
    out = {"prompts": tally["prompts"], "main": sort(tally["main"])}
    if tally["sub"]:
        out["sub"] = {g: sort(tally["sub"][g]) for g in sorted(tally["sub"])}
    return out


def work_line(key, value, tally, rework=None, interrupts=0):
    """The work sidecar line of a tally: `item` (an id) for one item's line, `items` (ids) for a session's shared
    line; the summed counts in their sorted order, `sub` only when a subagent ran. `rework`, the tally of the part
    of an item's counts from its first refused done (a part of the line's counts, not added to them), becomes the
    line's `rework` block when it holds a prompt or a subagent."""
    line = {key: value, **work_counts(tally)}
    if rework and (rework["prompts"] or rework["sub"]):
        line["rework"] = work_counts(rework)
    if interrupts and key == "item":
        line["interrupts"] = interrupts  # the tool calls interrupted in the item's window: a count, nothing else
    return line


def overhead_line(kind, calls, models):
    """The work sidecar line of one kind of the kb's own background runs: `overhead` (the kind), `calls` (the
    `claude -p` calls counted) and `main`, their counts per model in work_line's order; None when it breaks the gates
    (overhead_line_problems) or `models` is empty."""
    line = {"overhead": kind, "calls": calls, "main": {m: models[m] for m in sorted(models)}}
    return None if not models or overhead_line_problems(line, "") else line


def write_work(store, run_id, lines, missing, reader):
    """The work sidecar of run `run_id`: a header (the run, the transcript reader's version, counts), then the lines
    (item lines, shared lines, then overhead lines). Nothing is written without a line."""
    if not lines:
        return None
    path = run_path(store, run_id, work=True)
    counts = {"items": sum(1 for ln in lines if "item" in ln), "shared": sum(1 for ln in lines if "items" in ln),
              "missing": missing}
    if any("overhead" in ln for ln in lines):
        counts[OVERHEAD_COUNT_KEY] = sum(1 for ln in lines if "overhead" in ln)
    write_text(path, json_lines([{"run": run_id, "reader": reader, "counts": counts}] + lines))
    return path


def ops_line(row):
    """The ops sidecar line of one spool row (`id`, `ts`, `event` and the event's keys, in the event's order), or None
    when the row is not the closed shape the store keeps (ops_line_problems)."""
    spec = OPS_EVENTS.get(row.get("event")) if isinstance(row, dict) else None
    if spec is None:
        return None
    line = {k: row[k] for k in OPS_LINE_KEYS if k in row}
    line.update((k, row[k]) for k in spec if k in row)
    return None if ops_line_problems(line, "") or set(row) - set(line) - {"surface", "v"} else line


def write_ops(store, run_id, lines):
    """The ops sidecar of run `run_id`: a header (the run, the count of lines), then the lines (ops_line, in the
    order given). Nothing is written without a line."""
    if not lines:
        return None
    path = run_path(store, run_id, ops=True)
    write_text(path, json_lines([{"run": run_id, "counts": {"rows": len(lines)}}] + list(lines)))
    return path


def ops_ids(store):
    """The row ids of the store's ops sidecars: the rows a sidecar already holds."""
    return {u["id"] for _, objs in records(ops_files(store)) for _, u in objs if isinstance(u.get("id"), str)}


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
    return f"{when.strftime('%Y%m%dT%H%M%SZ')}-{hashlib.sha256(body.encode('utf-8')).hexdigest()[:8]}"


def write_findings(store, entries, new, states, kb_commit=None):
    """One findings file of records `new` (kind order, then id), with the counts of `states`: (run id, counts)."""
    new = sorted(new, key=lambda r: (FINDING_KINDS.index(r["kind"]), r["id"]))
    new = [{k: r[k] for k in FINDING_KEYS if k in r} for r in new]
    body = json_lines(new)
    run_id = learn_run_id(store, [r for r, _ in entries], body)
    counts = {s: sum(1 for r in new if r["state"] == s) for s in states}
    write_text(run_path(store, run_id, findings=True),
               json_lines([header(run_id, {"findings": len(new), **counts}, kb_commit)]) + body)
    return run_id, counts


# ---------------------------------------------------------------- the gates

def public_host(host, k=None):
    """Whether a fetch host may be stored: a DNS name (no IP literal) outside the private and example names, which
    the rules leave as it is (a host the public root names)."""
    import redact
    if not isinstance(host, str) or not HOSTNAME.fullmatch(host):
        return False
    if host.rsplit(".", 1)[-1] in PRIVATE_TLDS:
        return False
    return redact.redact(host, k) == host


def duplicate_ids(store):
    """One problem per entry id that appears more than once across the store's run files."""
    seen, out = {}, []
    for p, objs in records(run_files(store)):
        rel = p.relative_to(store).as_posix()
        for n, e in objs:
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


def closed_problems(e, where):
    """The entry fields that hold a closed value (a day, a verdict, a judgement, names and article paths) holding
    anything else: free text has no field of its own in an entry."""
    def names(v, rx):
        return isinstance(v, list) and all(isinstance(x, str) and rx.fullmatch(x) for x in v)

    def bounded(v, rx, cap):
        return names(v, rx) and 0 < len(v) <= cap and len(set(v)) == len(v)
    import kbid
    checks = (("day", lambda v: isinstance(v, str) and DAY.fullmatch(v)), ("intent", lambda v: v in INTENTS),
              ("tools", lambda v: names(v, NAME)), ("route", lambda v: isinstance(v, str) and NAME.fullmatch(v)),
              ("verdict", lambda v: v in VERDICTS), ("articles", lambda v: names(v, ARTICLE)),
              ("judged", lambda v: v in JUDGED), ("best", lambda v: isinstance(v, str) and ARTICLE.fullmatch(v)),
              ("sources", lambda v: isinstance(v, list) and 0 < len(v) <= SOURCES_MAX and len(set(v)) == len(v)
               and all(isinstance(x, str) and kbid.SOURCE_ID.fullmatch(x) for x in v)),
              ("root", lambda v: v == RULES_ROOT), ("model", lambda v: isinstance(v, str) and NAME.fullmatch(v)),
              ("tested", lambda v: bounded(v, TESTED_ID, TESTED_MAX)),
              ("set", lambda v: isinstance(v, str) and SET_NAME.fullmatch(v)),
              ("item", lambda v: isinstance(v, str) and WORK_ITEM.fullmatch(v)),
              ("answer_lines", lambda v: bounded(v, ANSWER_LINE, ANSWER_LINES_MAX)),
              ("key_missing", lambda v: bounded(v, KEY_WORD, KEY_MISSING_MAX)))
    return [f"{where}: `{key}` is not a {key} value: {e[key]!r:.60}" for key, ok in checks
            if key in e and not ok(e[key])]


def entry_problems(e, where, k):
    import redact
    out = []
    raw = sorted(set(e) & set(RAW_KEYS))
    if raw:
        out.append(f"{where}: raw spool fields: {', '.join(raw)}")
    prov = sorted(set(e) & set(HEADER_KEYS))
    if prov:
        out.append(f"{where}: run metadata in an entry: {', '.join(prov)}")
    free = sorted(set(e) & set(FREE_TEXT_KEYS))
    if free:
        out.append(f"{where}: free text in an entry: {', '.join(free)}")
    other = sorted(set(e) - set(ENTRY_KEYS) - set(RAW_KEYS) - set(HEADER_KEYS) - set(FREE_TEXT_KEYS))
    if other:
        out.append(f"{where}: unknown fields: {', '.join(other)}")
    bare = sorted(set(e) & set(RULES_KEYS) - {"root"}) if "root" not in e else []
    if bare:
        out.append(f"{where}: rules lookup fields without `root`: {', '.join(bare)}")
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
    out += closed_problems(e, where)
    cits = e.get("citations")
    if cits is not None:
        if not (isinstance(cits, list) and cits and len(cits) <= CITATIONS_MAX):
            out.append(f"{where}: citations are not a list of 1 to {CITATIONS_MAX} kb lines")
            cits = []
        for x in cits:
            if not (isinstance(x, dict) and set(x) <= set(CITATION_KEYS) and isinstance(x.get("line"), str)
                    and CITATION.fullmatch(x["line"]) and x.get("tag", "DOC") in TAGS
                    and x.get("verdict", "good") in VERDICTS):
                out.append(f"{where}: a citation that is not a path:line with its tag and verdict: {x!r:.80}")
    if e.get("articles") and not cits:
        out.append(f"{where}: articles without citations (path:line of the kb lines the lookup returned)")
    if ("cited" in e) != bool(cits) or e.get("cited", "pack") not in CITED:
        out.append(f"{where}: `cited` is not {' or '.join(CITED)} beside the citations")
    fetches = e.get("fetches", [])
    fetches = list(fetches) if isinstance(fetches, list) else [None]
    own = [key for key in FETCH_KEYS if "root" not in e or key != "chars"]  # a rules entry's `chars` is its lookup's
    if any(key in e for key in own):
        fetches.append({key: e[key] for key in own if key in e})
    for f in fetches:
        out += fetch_problems(f, where, k) if isinstance(f, dict) else [f"{where}: a fetch is not an object"]
    return out


def header_problems(p, rel, hn, h):
    """The header gates a run file and a findings file share: every provenance field, a run id that names the file."""
    out = []
    missing = [key for key in HEADER_KEYS if key not in h]
    if missing:
        out.append(f"{rel}:{hn}: header lacks {', '.join(missing)}")
    m = RUN_ID.fullmatch(str(h.get("run", "")))
    if "run" in h and not (m and h["run"] == p.stem and p.parent.name == f"{m.group(1)}-{m.group(2)}"):
        out.append(f"{rel}:{hn}: run id does not name this file")
    return out


def store_problems(store=None, k=None):
    """Every store gate over `store` (default kb/_querylog): run files with a header with the run's provenance,
    entries without it and without raw fields, no identifier in a text field, fetches with a public host and a bare
    path, no entry id twice, and the findings gates."""
    store = Path(store or STORE)
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
        out += header_problems(p, rel, hn, h)
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
        if isinstance(counts, dict):
            n = counts.get(SKIPPED_KEY, 1)
            if set(counts) - set(COUNT_KEYS) - {SKIPPED_KEY} or not (isinstance(n, int) and not isinstance(n, bool)
                                                                     and n > 0):
                out.append(f"{rel}:{hn}: counts hold a field other than {', '.join(COUNT_KEYS)} and a positive "
                           f"{SKIPPED_KEY}")
        extra = sorted(set(h) - set(HEADER_KEYS))
        if extra:
            out.append(f"{rel}:{hn}: header fields a header never has: {', '.join(extra)}")
        for n, e in entries:
            out += entry_problems(e, f"{rel}:{n}", k)
    return out + duplicate_ids(store) + findings_problems(store, k) + usage_problems(store) + work_problems(store) \
        + ops_sidecar_problems(store, k)


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
        out += header_problems(p, rel, hn, h)
        if isinstance(h.get("counts"), dict) and h["counts"].get("findings") != len(recs):
            out.append(f"{rel}:{hn}: counts.findings is {h['counts'].get('findings')}, the file has {len(recs)}")
        for n, r in recs:
            out += record_problems(r, f"{rel}:{n}", ids, k)
    out += reopened_problems(store)
    last = finding_states(store)
    fixed = {r.get("entry") for r in last.values() if r.get("kind") in FIX_KINDS and r.get("state") == "applied"}
    for r in last.values():
        if r.get("kind") == "eval" and r.get("state") == "applied" and r.get("entry") not in fixed:
            out.append(f"findings: eval finding {r.get('id')} is applied without its fix")
    return out


def closed_gaps(store):
    """The ids of the gap findings a record of the store's findings files put at CLOSED_STAGE."""
    return {rec["id"] for _, objs in records(findings_files(store)) for _, rec in objs
            if rec.get("kind") == "gap" and rec.get("stage") == CLOSED_STAGE and isinstance(rec.get("id"), str)}


def reopened_problems(store):
    """A gap finding closed at CLOSED_STAGE whose later record puts it at another stage: a closed gap reappears."""
    closed, out = set(), []
    for p, objs in records(findings_files(store)):
        rel = p.relative_to(store).as_posix()
        for n, rec in objs:
            fid = rec.get("id")
            if rec.get("kind") != "gap" or not isinstance(fid, str):
                continue
            if rec.get("stage") == CLOSED_STAGE:
                closed.add(fid)
            elif fid in closed:
                out.append(f"{rel}:{n}: gap finding {fid} was closed at {CLOSED_STAGE} and reappears at stage "
                           f"{rec.get('stage')}")
    return out


def record_problems(r, where, ids, k):
    """The gates on one findings record: its id, fields, kind, state, and per kind its stage, entry and promotions,
    or a source finding's signal and public host."""
    out = []
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
        return out
    if r.get("kind") not in FINDING_KINDS:
        return out
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
    if "tried" in r and not ((r.get("kind") == "gap" or (r.get("kind") == "eval" and r.get("state") == "no-fix"))
                             and isinstance(r["tried"], str) and DAY.fullmatch(r["tried"])):
        out.append(f"{where}: `tried` is not the day of a gap finding's, or a no-fix eval finding's, tried note: "
                   f"{r['tried']!r:.40}")
    if r.get("kind") == "rules" and r.get("stage") != "miss":
        out.append(f"{where}: a rules finding stays at stage miss: no public gap or fact comes of it")
    if r.get("kind") == "gap" and r.get("stage") in STAGES[2:] and not ARTICLE.fullmatch(str(r.get("article", ""))):
        out.append(f"{where}: a gap finding at stage {r.get('stage')} names no article")
    return out


def _values(x):
    """The strings of a JSON value, nested ones included."""
    if isinstance(x, dict):
        for v in x.values():
            yield from _values(v)
    elif isinstance(x, list):
        for v in x:
            yield from _values(v)
    elif isinstance(x, str):
        yield x


def ops_line_leaks(line, k=None):
    """[kind] of the leak scan's hits over every value of an ops line but its id (the scan of leak_problems)."""
    import redact
    return [kind for v in _values({key: val for key, val in line.items() if key != "id"})
            for kind, _ in redact.scan(v, k)]


def leak_problems(store, rels, k=None):
    """The leak scan (redact.scan: kbcommon.leak_hits with what the public root contains allowed) over every value of
    the store files `rels`, the ids that name runs, entries and findings aside: one problem per hit."""
    import redact
    out = []
    values = _values

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


def _count(v):
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def _models_problems(models, where):
    import kbusage
    if not (isinstance(models, dict) and models):
        return [f"{where}: not a map of model ids to counts"]
    out = []
    for m, c in models.items():
        if not (m == "other" or kbusage.MODEL.fullmatch(m)):
            out.append(f"{where}: {m!r:.60} is not a model id")
        if not (isinstance(c, dict) and set(c) == set(USAGE_COUNTS) and all(_count(v) for v in c.values())):
            out.append(f"{where}: counts of {m!r:.60} are not {', '.join(USAGE_COUNTS)} as counts")
        elif c["cw1h"] > c["cw"]:
            out.append(f"{where}: cw1h of {m!r:.60} exceeds cw")
    return out


def _sub_problems(sub, where):
    """A `sub` field's gates: a map of agent groups (kbusage.AGENTS, else `other`) to model counts."""
    import kbusage
    groups = set(kbusage.AGENTS.values()) | {kbusage.OTHER_AGENT}
    if not (isinstance(sub, dict) and sub):
        return [f"{where}: sub is not a map of agent groups"]
    out = []
    for g, models in sub.items():
        if g not in groups:
            out.append(f"{where}: {g!r:.60} is not an agent group")
        out += _models_problems(models, f"{where}: sub {g!r:.40}")
    return out


def usage_line_problems(u, where):
    """The gates on one usage line: an entry id, only numbers, model ids, agent groups and tool groups in their
    closed shapes."""
    import kbusage
    out = []
    other = sorted(set(u) - set(USAGE_KEYS))
    if other:
        out.append(f"{where}: fields a usage line never has: {', '.join(other)}")
    if not (isinstance(u.get("id"), str) and ENTRY_ID.fullmatch(u["id"])):
        out.append(f"{where}: usage id is not an entry id")
    out += _models_problems(u.get("main"), f"{where}: main")
    if "sub" in u:
        out += _sub_problems(u["sub"], where)
    if not _count(u.get("start")):
        out.append(f"{where}: start is not a count")
    if "cut" in u and not (_count(u["cut"]) and u["cut"] > 0):
        out.append(f"{where}: cut is not a positive count")
    st = u.get("steps", [])
    if not (isinstance(st, list) and len(st) <= kbusage.STEPS_MAX):
        out.append(f"{where}: steps are not a list of at most {kbusage.STEPS_MAX}")
        st = []
    for s in st:
        ok = (isinstance(s, dict) and set(s) <= set(USAGE_STEP_KEYS) and isinstance(s.get("tools"), list)
              and s["tools"] and ("grow" not in s or _count(s["grow"])))
        tools = s.get("tools") if ok else []
        ok = ok and all(isinstance(t, dict) and set(t) == set(USAGE_TOOL_KEYS) and isinstance(t["tool"], str)
                        and kbusage.TOOL_GROUP.fullmatch(t["tool"]) and isinstance(t["ok"], bool)
                        and _count(t["chars"]) for t in tools)
        if not ok:
            out.append(f"{where}: a step that is not tool groups with ok and chars, and a grow count: {s!r:.80}")
    return out


def usage_problems(store):
    """The usage sidecar gates: a header (run, reader, counts) naming its file beside a run file of the same run, a
    line count that matches, lines of entries that run file holds, each id once across sidecars, and the line
    gates."""
    store = Path(store)
    out, seen = [], {}
    runs = {p.stem: p for p in run_files(store)}
    for p in usage_files(store):
        rel = p.relative_to(store).as_posix()
        try:
            objs = load_run(p)
        except (OSError, ValueError) as e:
            out.append(f"{rel}: not a usage sidecar ({e})")
            continue
        if not objs:
            out.append(f"{rel}: empty usage sidecar")
            continue
        (hn, h), lines = objs[0], objs[1:]
        m = RUN_ID.fullmatch(str(h.get("run", "")))
        if not (m and h["run"] == p.stem and p.parent.name == f"{m.group(1)}-{m.group(2)}"):
            out.append(f"{rel}:{hn}: run id does not name this file")
        if set(h) != set(USAGE_HEADER_KEYS):
            out.append(f"{rel}:{hn}: a usage header is exactly {', '.join(USAGE_HEADER_KEYS)}")
        if not (_count(h.get("reader")) and h.get("reader")):
            out.append(f"{rel}:{hn}: reader is not a version number")
        c = h.get("counts")
        if not (isinstance(c, dict) and set(c) == set(USAGE_COUNT_KEYS) and all(_count(v) for v in c.values())):
            out.append(f"{rel}:{hn}: counts are not {', '.join(USAGE_COUNT_KEYS)} as counts")
        elif c["entries"] != len(lines):
            out.append(f"{rel}:{hn}: counts.entries is {c['entries']}, the file has {len(lines)}")
        run = runs.get(p.stem)
        ids = set()
        if run is None:
            out.append(f"{rel}: no run file {p.stem} beside it")
        else:
            try:
                ids = {e.get("id") for _, e in load_run(run)[1:]}
            except (OSError, ValueError):
                pass
        for n, u in lines:
            where = f"{rel}:{n}"
            out += usage_line_problems(u, where)
            i = u.get("id")
            if run is not None and i not in ids:
                out.append(f"{where}: entry {i} is not in run file {p.stem}")
            if isinstance(i, str):
                if i in seen:
                    out.append(f"{where}: duplicate usage id {i} (also {seen[i]})")
                else:
                    seen[i] = where
    return out


def overhead_line_problems(w, where):
    """The gates on one overhead line (`overhead`, `calls`, `main`): a background run kind of OVERHEAD_KINDS, a
    positive count of calls and counts per model in the usage record's closed shape, and nothing else: no item,
    session, prompt, command or text."""
    out = []
    other = sorted(set(w) - set(WORK_OVERHEAD_KEYS))
    if other:
        out.append(f"{where}: fields an overhead line never has: {', '.join(other)}")
    if w.get("overhead") not in OVERHEAD_KINDS:
        out.append(f"{where}: overhead is not a background run kind ({', '.join(OVERHEAD_KINDS)})")
    if not (_count(w.get("calls")) and w["calls"] > 0):
        out.append(f"{where}: calls is not a positive count")
    return out + _models_problems(w.get("main"), f"{where}: main")


def _counted_problems(w, where, may_have_no_prompt):
    """The gates on the counts of a work line or of its `rework` block: a positive prompt count and `main` per model,
    or, for an item line (`may_have_no_prompt`), no prompt (`prompts` 0), an empty `main` and a `sub`; and `sub` in
    its closed shape when there is one."""
    out = []
    if may_have_no_prompt and type(w.get("prompts")) is int and w["prompts"] == 0:
        if w.get("main") != {} or "sub" not in w:
            out.append(f"{where}: an item line with no prompt holds an empty main and a sub")
    else:
        if not (_count(w.get("prompts")) and w["prompts"] > 0):
            out.append(f"{where}: prompts is not a positive count")
        out += _models_problems(w.get("main"), f"{where}: main")
    if "sub" in w:
        out += _sub_problems(w["sub"], where)
    return out


def _within_problems(part, whole, where):
    """A `rework` block `part` of a line `whole`, both with sound counts, is a part of it: no more prompts, and for
    each model (and agent group) no count above the line's."""
    out = []
    if part["prompts"] > whole["prompts"]:
        out.append(f"{where}: rework prompts exceed the line's")
    pairs = [("main", part["main"], whole["main"])]
    pairs += [(f"sub {g!r:.40}", models, whole.get("sub", {}).get(g, {})) for g, models in part.get("sub", {}).items()]
    for name, mine, theirs in pairs:
        for m, c in mine.items():
            if any(c[k] > theirs.get(m, {}).get(k, 0) for k in USAGE_COUNTS):
                out.append(f"{where}: {name} counts of {m!r:.60} exceed the line's")
    return out


def rework_problems(w, where):
    """The gates on an item line's `rework` block: a closed shape (`prompts`, `main`, `sub`, nothing else), the
    counts of a line (a positive prompt count and `main`, or no prompt, an empty `main` and a `sub`), a part of the
    line's own counts, and on no sprint's line (a prompt in several windows is never split)."""
    b = w["rework"]
    if not isinstance(b, dict):
        return [f"{where}: rework is not a block of counts"]
    here = f"{where}: rework"
    out = []
    other = sorted(set(b) - set(WORK_REWORK_KEYS))
    if other:
        out.append(f"{here} has fields it never has: {', '.join(other)}")
    if isinstance(w.get("item"), str) and w["item"].startswith("SP-"):
        out.append(f"{here}: a sprint's line has no rework")
    out += _counted_problems(b, here, True)
    if not out and not _counted_problems(w, where, True):
        out += _within_problems(b, w, here)
    return out


def work_line_problems(w, where):
    """The gates on one work sidecar line: an item line (`item`, `prompts`, `main`, `sub`, and `rework`, the counts
    from its first refused done: rework_problems) or a shared line (`items`, `prompts`, `main`, `sub`), with an item
    id, a prompt count and counts in the usage record's closed shapes, and nothing else: no session, prompt,
    transcript, command or text. A shared line has a positive prompt count and a `main`; an item line has them too,
    or no prompt (`prompts` 0) and an empty `main` with a `sub`: the counts of subagents routed to the item, none of
    its prompts counted on its own line. An overhead line is a third kind (overhead_line_problems), with no item at
    all."""
    out = []
    if sum(1 for k in ("item", "items", "overhead") if k in w) != 1:
        return [f"{where}: a work line has an `item` or an `items` or an `overhead`, one of them and not several or "
                f"none"]
    if "overhead" in w:
        return overhead_line_problems(w, where)
    shared = "items" in w
    keys = WORK_SHARED_KEYS if shared else WORK_ITEM_KEYS
    other = sorted(set(w) - set(keys))
    if other:
        out.append(f"{where}: fields a work line never has: {', '.join(other)}")
    if shared:
        ids = w["items"]
        if not (isinstance(ids, list) and ids and all(isinstance(i, str) and WORK_ITEM.fullmatch(i) for i in ids)):
            out.append(f"{where}: items are not a list of item ids")
        elif ids != sorted(set(ids)):
            out.append(f"{where}: items are not sorted, each once")
    elif not (isinstance(w["item"], str) and WORK_ITEM.fullmatch(w["item"])):
        out.append(f"{where}: item is not an item id")
    out += _counted_problems(w, where, not shared)
    if "rework" in w and not shared:
        out += rework_problems(w, where)
    if "interrupts" in w and not (isinstance(w["interrupts"], int) and not isinstance(w["interrupts"], bool)
                                  and 0 < w["interrupts"] <= OPS_COUNT_MAX):
        out.append(f"{where}: interrupts is not a positive count")
    return out


def work_problems(store):
    """The work sidecar gates: a header (run, reader, counts) naming its file beside a run file of the same run, line
    counts that match, the line gates, and each item once in a file."""
    store = Path(store)
    out = []
    runs = {p.stem for p in run_files(store)}
    for p in work_files(store):
        rel = p.relative_to(store).as_posix()
        try:
            objs = load_run(p)
        except (OSError, ValueError) as e:
            out.append(f"{rel}: not a work sidecar ({e})")
            continue
        if not objs:
            out.append(f"{rel}: empty work sidecar")
            continue
        (hn, h), lines = objs[0], objs[1:]
        m = RUN_ID.fullmatch(str(h.get("run", "")))
        if not (m and h["run"] == p.stem and p.parent.name == f"{m.group(1)}-{m.group(2)}"):
            out.append(f"{rel}:{hn}: run id does not name this file")
        if set(h) != set(WORK_HEADER_KEYS):
            out.append(f"{rel}:{hn}: a work header is exactly {', '.join(WORK_HEADER_KEYS)}")
        if not (_count(h.get("reader")) and h.get("reader")):
            out.append(f"{rel}:{hn}: reader is not a version number")
        c = h.get("counts")
        keys = WORK_COUNT_KEYS + ((OVERHEAD_COUNT_KEY,) if any("overhead" in w for _, w in lines) else ())
        if not (isinstance(c, dict) and set(c) == set(keys) and all(_count(v) for v in c.values())):
            out.append(f"{rel}:{hn}: counts are not {', '.join(keys)} as counts")
        else:
            for key, name in (("items", "item"), ("shared", "items"), (OVERHEAD_COUNT_KEY, "overhead")):
                if key not in c:
                    continue
                n = sum(1 for _, w in lines if name in w)
                if c[key] != n:
                    out.append(f"{rel}:{hn}: counts.{key} is {c[key]}, the file has {n}")
        if p.stem not in runs:
            out.append(f"{rel}: no run file {p.stem} beside it")
        seen = {}
        for n, w in lines:
            where = f"{rel}:{n}"
            out += work_line_problems(w, where)
            i = w.get("item")
            if isinstance(i, str):
                if i in seen:
                    out.append(f"{where}: duplicate item {i} (also {seen[i]})")
                else:
                    seen[i] = where
            kind = w.get("overhead")
            if isinstance(kind, str):
                if ("overhead", kind) in seen:
                    out.append(f"{where}: duplicate overhead {kind} (also {seen[('overhead', kind)]})")
                else:
                    seen[("overhead", kind)] = where
    return out


def ops_line_problems(w, where):
    """The gates on one ops sidecar line: `id` (a UUID, the spool row's), `ts` (the spool's time format), an `event`
    of ql_capture.OPS_EVENTS and the keys that event has, each in its closed shape (ql_capture.ops_problems), and
    nothing else: no session, prompt, command, path or text."""
    out = []
    if not (isinstance(w.get("id"), str) and ENTRY_ID.fullmatch(w["id"])):
        out.append(f"{where}: ops id is not a row id")
    if not (isinstance(w.get("ts"), str) and OPS_TS.fullmatch(w["ts"])):
        out.append(f"{where}: ops ts is not a UTC time")
    return out + ops_problems({k: v for k, v in w.items() if k not in ("id", "ts")}, where)


def ops_sidecar_problems(store, k=None):
    """The ops sidecar gates: a header of exactly `run` and `counts` (`rows`) naming its file and its month beside a
    run file of the same run, a count that matches, the line gates (ops_line_problems), each row id once across
    sidecars, and the leak scan over every value (leak_problems)."""
    store = Path(store)
    out, seen = [], {}
    runs = {p.stem for p in run_files(store)}
    rels = []
    for p in ops_files(store):
        rel = p.relative_to(store).as_posix()
        try:
            objs = load_run(p)
        except (OSError, ValueError) as e:
            out.append(f"{rel}: not an ops sidecar ({e})")
            continue
        if not objs:
            out.append(f"{rel}: empty ops sidecar")
            continue
        rels.append(rel)
        (hn, h), lines = objs[0], objs[1:]
        m = RUN_ID.fullmatch(str(h.get("run", "")))
        if not (m and h["run"] == p.stem and p.parent.name == f"{m.group(1)}-{m.group(2)}"):
            out.append(f"{rel}:{hn}: run id does not name this file")
        if set(h) != set(OPS_HEADER_KEYS):
            out.append(f"{rel}:{hn}: an ops header is exactly {', '.join(OPS_HEADER_KEYS)}")
        c = h.get("counts")
        if not (isinstance(c, dict) and set(c) == set(OPS_COUNT_KEYS) and all(_count(v) for v in c.values())):
            out.append(f"{rel}:{hn}: counts are not {', '.join(OPS_COUNT_KEYS)} as counts")
        elif c["rows"] != len(lines):
            out.append(f"{rel}:{hn}: counts.rows is {c['rows']}, the file has {len(lines)}")
        if p.stem not in runs:
            out.append(f"{rel}: no run file {p.stem} beside it")
        for n, w in lines:
            where = f"{rel}:{n}"
            out += ops_line_problems(w, where)
            i = w.get("id")
            if isinstance(i, str):
                if i in seen:
                    out.append(f"{where}: duplicate ops id {i} (also {seen[i]})")
                else:
                    seen[i] = where
    return out + leak_problems(store, rels, k)


def check(store=None):
    """`check [DIR]`: every store gate over DIR (default kb/_querylog), one line per problem; 1 when any."""
    problems = store_problems(store)
    for p in problems:
        print(p)
    print(f"querylog check: problems={len(problems)}")
    return 1 if problems else 0
