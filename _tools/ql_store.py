"""The query log's store (kb/_self/querylog.md, Store): the run files and findings files under kb/_querylog/ (or a
local store laid out the same way), their readers and writers, and the gates `querylog.py check` runs over them.

  <yyyy-mm>/<run-id>.jsonl            a header line (HEADER_KEYS), then one entry per line (ENTRY_KEYS)
  findings/<yyyy-mm>/<run-id>.jsonl   the same header, then one record per finding whose state the run changed
"""
import datetime, hashlib, json, re, subprocess
from pathlib import Path

from ql_base import HOME, PIPELINE_VERSION, STORE, json_lines, write_text
from ql_capture import ARG_MAX_CHARS, TAGS, VERDICTS

HEADER_KEYS = ("run", "pipeline", "retrieval", "kb_commit", "counts")
COUNT_KEYS = ("entries", "dropped", "waiting")
SKIPPED_KEY = "skipped"  # a count a header holds only when distill skipped spool rows
ENTRY_KEYS = ("id", "surface", "day", "intent", "tools", "route", "question", "verdict", "articles", "citations",
              "cited", "judged", "best", "fetches", "tool", "fetcher", "host", "path", "outcome", "chars")
CITATION_KEYS = ("line", "tag", "verdict")
CITED = ("reply", "pack")  # the citations the reply named, else the pack's first lines
FREE_TEXT_KEYS = ("summary",)  # an outcome in words: the entry's citations say what the kb gave
INTENTS = ("lookup", "skill", "change")
FETCH_KEYS = ("tool", "fetcher", "host", "path", "outcome", "n", "chars")
RAW_KEYS = ("prompt", "answer", "session_id", "prompt_id", "transcript_path", "cwd", "user", "hostname", "command",
            "args", "ts")  # spool fields a run file never holds
SURFACES = ("prompt", "kb_hook", "mcp", "kb_ask", "tool_fetch", "fetch", "stop")
TEXT_KEYS = ("question",)
JUDGED = ("answered", "partly", "missed")
QUESTION_MAX_CHARS = 500
CITATIONS_MAX = 5  # kb lines an entry keeps
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
FINDING_KINDS = ("eval", "alias", "expansion", "gap", "source")
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


# ---------------------------------------------------------------- reading

def run_files(store):
    """The run files of a store: <yyyy-mm>/<run-id>.jsonl (findings/ has its own layout)."""
    store = Path(store)
    return sorted(p for p in store.glob("*/*.jsonl") if p.parent.name != FINDINGS) if store.is_dir() else []


def findings_files(store):
    """The findings files of a store, oldest run first: findings/<yyyy-mm>/<run-id>.jsonl."""
    d = Path(store) / FINDINGS
    return sorted(d.glob("*/*.jsonl"), key=lambda p: p.stem) if d.is_dir() else []


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


def run_path(store, run_id, findings=False):
    return Path(store) / (FINDINGS if findings else "") / f"{run_id[:4]}-{run_id[4:6]}" / f"{run_id}.jsonl"


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
    checks = (("day", lambda v: isinstance(v, str) and DAY.fullmatch(v)), ("intent", lambda v: v in INTENTS),
              ("tools", lambda v: names(v, NAME)), ("route", lambda v: isinstance(v, str) and NAME.fullmatch(v)),
              ("verdict", lambda v: v in VERDICTS), ("articles", lambda v: names(v, ARTICLE)),
              ("judged", lambda v: v in JUDGED), ("best", lambda v: isinstance(v, str) and ARTICLE.fullmatch(v)))
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
    if any(key in e for key in FETCH_KEYS):
        fetches.append({key: e[key] for key in FETCH_KEYS if key in e})
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
    return out + duplicate_ids(store) + findings_problems(store, k)


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
    if "tried" in r and not (r.get("kind") == "gap" and isinstance(r["tried"], str) and DAY.fullmatch(r["tried"])):
        out.append(f"{where}: `tried` is not the day of a gap finding's tried note: {r['tried']!r:.40}")
    if r.get("kind") == "gap" and r.get("stage") in STAGES[2:] and not ARTICLE.fullmatch(str(r.get("article", ""))):
        out.append(f"{where}: a gap finding at stage {r.get('stage')} names no article")
    return out


def leak_problems(store, rels, k=None):
    """The leak scan (redact.scan: kbcommon.leak_hits with what the public root contains allowed) over every value of
    the store files `rels`, the ids that name runs, entries and findings aside: one problem per hit."""
    import redact
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


def check(store=None):
    """`check [DIR]`: every store gate over DIR (default kb/_querylog), one line per problem; 1 when any."""
    problems = store_problems(store)
    for p in problems:
        print(p)
    print(f"querylog check: problems={len(problems)}")
    return 1 if problems else 0
