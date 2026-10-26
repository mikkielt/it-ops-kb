"""kbmon's coord panel (kb/_self/monitoring.md): the live claims with their holder, seconds left and budget beside spend,
the newest events with their sequence numbers, the live intent and progress digest, the asks addressed to the operator
that no closing answer has ended, and the effective coordination settings with the file that set each.

The panel runs `coord.py list`, `coord.py wait --since 0 --timeout 0` and `coord.py digest` as three child processes at
once, then `coord.py get` of the question of each of the first open asks to the operator, on the local store (`--store`, else `KB_COORD_STORE`, else the default of the clone at `--root`) or on a `coord.py serve` server
(`--url` with `--key-file`, which coord.py reads: the panel never opens the key file). A local store that is not there
is `absent` and is not created. A server that cannot be reached, or that answers no command within `CHILD_SECONDS`, is
`timeout`. A session id (a holder, a `session/` key, an event's session fields) shows as its label
(`mon_view.session_label`). An ask is open when an `ask` event names `operator` and no `answer` event of its id has a
closing state (`CLOSED`, the coord hook's); its question is redacted before it is cut to `ASK_CHARS`. The settings are
`kbsettings.explain` of the clone at `--root` (its settings.json, and the one `kb/NAME/settings.json` when exactly one
root has one): each key with its value and its source, `default` or the file relative to the clone; a settings file that
cannot be read gives `settings_error` and no settings. Imports `mon_base` and `mon_view`; `coord` only to name
the clone's store, `kbsettings` and `redact` where they are used.
"""
import atexit
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import mon_base
import mon_view

COORD = Path(__file__).resolve().with_name("coord.py")
CHILD_SECONDS = 30  # the longest the three commands may take; the panel's own bound is kbmon's --timeout
EVENTS_KEPT = 10  # newest events in the data
EVENTS_SHOWN = 5  # newest events in the text view
DIGEST_LINES = 20
SIDE_WIDTH = 100  # columns from which the events sit beside the claims
SIDE_COLUMN = 50  # where they start in a body row: column 52 less the two gutter columns
MIN_KEY = 8
SUBJECTS = ("key", "item", "topic", "touch", "path", "fact", "session")
WHOS = ("holder", "operator", "session")
OPERATOR = "operator"  # the target of the asks the needs-you line names
CLOSED = ("completed", "failed", "rejected")  # the answer states that end an ask (the coord hook's)
ASKS_KEPT = 20  # open asks in the data, the oldest first
ASKS_READ = 3  # open asks whose question is read (the needs-you line names three of a kind)
ASK_CHARS = 60  # characters of a question in the data, after redaction
UNREACHABLE = "cannot reach"  # what coord.py prints when it cannot connect to a --url
WAIT_KEYS = "wait/"  # the leases of a blocking `coord.py wait`: the sessions panel's waits, no claims

_children = set()


def _reap():
    for child in list(_children):
        if child.poll() is None:
            child.kill()


atexit.register(_reap)


def local_store(ctx):
    """The local store: `--store`, else `KB_COORD_STORE`, else the one of the clone at `--root`; None when that is no git
    clone."""
    store = ctx.store or os.environ.get("KB_COORD_STORE")
    if not store:
        import coord
        store = coord.store_of(ctx.root)
    return str(Path(store).expanduser()) if store else None


def connection(ctx):
    """(coord.py's connection arguments, the data's source) for the url or the local store; absent when no store file is
    there."""
    if ctx.url:
        if not ctx.key_file:
            raise mon_base.Unsupported("--url needs --key-file")
        return ["--url", ctx.url, "--key-file", ctx.key_file], "url"
    store = local_store(ctx)
    if not store or not Path(store).is_file():
        raise mon_base.Absent(f"no coord store file at {store}" if store else f"no coord store file: {ctx.root} is in no git clone")
    return ["--store", store], "local"


def start(argv):
    child = subprocess.Popen([sys.executable, str(COORD), *argv], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, encoding="utf-8")
    _children.add(child)
    return child


def last_line(text):
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    return lines[-1].removeprefix("coord.py: ") if lines else ""


def run_all(conn, commands, strict=True):
    """{name: output} of the coord.py COMMANDS ({name: argv}), started together and each read until CHILD_SECONDS after the
    start. A command that exits non-zero raises (a RuntimeError, a Timeout where the server cannot be reached); with
    `strict` False its output is None."""
    children = {name: start(conn + argv) for name, argv in commands.items()}
    deadline = time.monotonic() + CHILD_SECONDS
    out = {}
    try:
        for name, child in children.items():
            try:
                text, err = child.communicate(timeout=max(0.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                raise mon_base.Timeout(f"coord.py {name} gave no answer in {CHILD_SECONDS} seconds")
            if child.returncode != 0:
                why = last_line(err) or f"exit {child.returncode}"
                if UNREACHABLE in why:
                    raise mon_base.Timeout(why)
                if strict:
                    raise RuntimeError(f"coord.py {name}: {why}")
                text = None
            out[name] = text
    finally:
        for child in children.values():
            if child.poll() is None:
                child.kill()
            child.wait()
            for pipe in (child.stdout, child.stderr):
                pipe.close()
            _children.discard(child)
    return out


def fetch(conn):
    """The output of list, wait and digest."""
    return run_all(conn, {"list": ["list"], "wait": ["wait", "--since", "0", "--timeout", "0"],
                          "digest": ["digest", "--key", "*", "--lines", str(DIGEST_LINES)]})


def open_asks(events):
    """[{id, since, ref}] of the asks to the operator in EVENTS (coord's, oldest first) that no closing answer ended, the
    oldest first; `since` is the ask's time as `2026-10-24T14:02:36Z`."""
    closed = {e["fields"].get("id") for e in events if e["kind"] == "answer" and e["fields"].get("state") in CLOSED}
    found, seen = [], set()
    for e in events:
        f = e["fields"]
        if e["kind"] != "ask" or f.get("to") != OPERATOR or not f.get("id") or f["id"] in closed or f["id"] in seen:
            continue
        seen.add(f["id"])
        at = e.get("at")
        found.append({"id": f["id"], "since": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(at)) if isinstance(at, (int, float)) else "",
                      "ref": f.get("ref")})
    return found


def ask_texts(conn, asks):
    """ASKS ({id, since, ref}) as {id, since, text}: the question of each of the first ASKS_READ read with `coord.py
    get`, redacted and cut to ASK_CHARS words-wise, "" for the rest and for a question that cannot be read."""
    import redact
    from mon_status import short_name
    shown = asks[:ASKS_READ]
    got = run_all(conn, {a["id"]: ["get", a["ref"]] for a in shown if a.get("ref")}, strict=False) if shown else {}
    out = []
    for a in asks:
        try:
            value = json.loads(got.get(a["id"]) or "{}").get("value")
        except ValueError:
            value = None
        text = redact.redact(" ".join(str(value or "").split())) if value else ""
        out.append({"id": a["id"], "since": a["since"], "text": short_name(text, ASK_CHARS)})
    return out


def kb_root_of(root):
    """The name of the one kb root under ROOT/kb that has a settings.json, else None (none has one, or several do)."""
    found = sorted(p.parent.name for p in Path(root).glob("kb/*/settings.json") if p.is_file())
    return found[0] if len(found) == 1 else None


def settings_of(root):
    """({key: {value, source}}, the error text or None): the effective coordination settings of the clone at ROOT, each
    key with its source, `default` or the settings file relative to ROOT."""
    import kbsettings
    try:
        rows = kbsettings.explain(root, kb_root_of(root))
    except kbsettings.SettingsError as e:
        return {}, " ".join(str(e).replace(str(root) + os.sep, "").split())
    def source(text):
        if text == "default":
            return text
        try:
            return Path(text).relative_to(root).as_posix()
        except ValueError:
            return Path(text).name
    return {r["key"]: {"value": r["value"], "source": source(r["source"])} for r in rows}, None


def claim_of(row, now):
    return {"key": mon_view.session_key(row["key"]), "holder": mon_view.session_label(row["holder"]), "left_s": max(0, int(row["expires"] - now)),
            "budget_usd": row.get("budget_usd"), "spend_usd": row.get("spend_usd"),
            "over_budget": bool(row.get("over_budget"))}


def runs_of(rows, events, now):
    """[{item, state, age_s, step, gates}] of the run states: each `run/<item>` row of `coord.py list` with a state `coord.RUN_STATES` names,
    the seconds since the item's newest progress event (None when it has none) and the `step` and `gates` (a list of ids) of the
    newest progress event that names the state the key holds (None and [] when it has none)."""
    import coord
    newest, moved = {}, {}
    for e in events:
        fields = e.get("fields") if isinstance(e.get("fields"), dict) else {}
        if e.get("kind") == "progress" and isinstance(fields.get("item"), str) and isinstance(e.get("at"), (int, float)):
            newest[fields["item"]] = e["at"]
            moved[(fields["item"], fields.get("state"))] = fields
    out = []
    for r in rows:
        key, state = str(r.get("key")), r.get("value")
        if key.startswith(coord.RUN_KEYS) and state in coord.RUN_STATES:
            item = key[len(coord.RUN_KEYS):]
            at, fields = newest.get(item), moved.get((item, state), {})
            out.append({"item": item, "state": state, "age_s": None if at is None else max(0, int(now - at)),
                        "step": fields.get("step") or None,
                        "gates": [g for g in str(fields.get("gates") or "").split(",") if g]})
    return out


def transcript_age(sessions, now):
    """The seconds since the newest write to the transcript of any of SESSIONS (`kbusage.find_transcript`) or to a transcript of
    its subagents (`<session>/subagents/agent-*.jsonl` beside it): a session that fans out writes there while its own transcript
    waits. None when none of them has one."""
    import kbusage
    from ql_capture import SAFE_SESSION
    stamps = []
    for session in sessions:
        path = kbusage.find_transcript(session) if SAFE_SESSION.fullmatch(session) else None
        if path is None:
            continue
        try:
            files = [path, *path.with_suffix("").joinpath("subagents").glob("agent-*.jsonl")]
        except OSError:
            files = [path]
        for f in files:
            try:
                stamps.append(f.stat().st_mtime)
            except OSError:
                pass
    return max(0, int(now - max(stamps))) if stamps else None


def with_silence(runs, rows, events, root, now, local=True):
    """RUNS (`runs_of`) with `silent_s` added to each working run: the seconds it has gone with no sign of life, which `kbmon.coord.run.working_silent`
    reads. A worker the coord `own/` records and the claims ledger name (`bl_items.worker_of`) that no longer runs, or that no record
    names, leaves the seconds since the item's newest progress event; a worker that runs leaves the lesser of that and the seconds since the
    newest write to the transcript of the item's sessions (the `session` of the item's `own/` records and of its intents that are no
    claim's), and 0 where none of those has a transcript. A store read over a url (LOCAL false) names workers of another host: no pid is probed there
    and the seconds are the progress event's. None for a working run with no progress event."""
    import bl_clean
    import bl_items
    from types import SimpleNamespace
    owners = [r for r in (bl_clean.recorded(x) for x in rows if str(x.get("key")).startswith(bl_clean.PREFIX)) if r]
    coord = bl_items.coord_workers(owners)
    table = bl_clean.host_table(root) if local else None
    sessions = {}
    for r in owners:
        if r.get("item") and isinstance(r.get("session"), str):
            sessions.setdefault(r["item"], set()).add(r["session"])
    for e in events:
        f = e.get("fields") if isinstance(e.get("fields"), dict) else {}
        if e.get("kind") == "intent" and f.get("topic") != "backlog-claim" and isinstance(f.get("item"), str) \
                and isinstance(f.get("session"), str):
            sessions.setdefault(f["item"], set()).add(f["session"])
    out = []
    for run in runs:
        if run["state"] == "working":
            silent = run["age_s"]
            if local and silent is not None and bl_items.worker_of(SimpleNamespace(root=Path(root)), run["item"], coord, table)[1]:
                quiet = transcript_age(sorted(sessions.get(run["item"], ())), now)
                silent = 0 if quiet is None else min(silent, quiet)
            run = {**run, "silent_s": silent}
        out.append(run)
    return out


def run_rows(ctx):
    """`runs_of` of the store the panels read (`--store`, `KB_COORD_STORE`, the clone's, or `--url`), read with `coord.py list
    --prefix run/` and one `wait --since 0 --timeout 0`; None where there is no store, the server cannot be reached or coord
    cannot be read: a reader of the run states then shows none."""
    try:
        conn, _ = connection(ctx)
        out = run_all(conn, {"list": ["list", "--prefix", "run/"], "wait": ["wait", "--since", "0", "--timeout", "0"]})
        return runs_of(json.loads(out["list"]), json.loads(out["wait"])["events"], time.time())
    except (mon_base.Absent, mon_base.Unsupported, mon_base.Timeout, RuntimeError, ValueError, KeyError, OSError):
        return None


def event_fields(event):
    """The fields of a coord event with its session ids labelled (`mon_view.session_fields`) and its key's."""
    fields = event.get("fields") if isinstance(event.get("fields"), dict) else {}
    fields = mon_view.session_fields(fields)
    return {**fields, "key": mon_view.session_key(fields["key"])} if "key" in fields else fields


def collect(ctx):
    conn, source = connection(ctx)
    out = fetch(conn)
    now = time.time()
    rows = json.loads(out["list"])
    claims = [claim_of(r, now) for r in rows if r.get("holder") and not str(r.get("key")).startswith(WAIT_KEYS)]
    every = json.loads(out["wait"])["events"]
    events = every[-EVENTS_KEPT:]
    asks = open_asks(every)
    settings, bad = settings_of(ctx.root)
    data = {"source": source, "claims": claims, "runs": with_silence(runs_of(rows, every, now), rows, every, ctx.root, now, source == "local"),
            "events": [{"seq": e["seq"], "kind": e["kind"], "fields": event_fields(e)} for e in reversed(events)],
            "digest": [mon_view.session_text(x) for x in out["digest"].splitlines() if x.strip()],
            "asks": ask_texts(conn, asks[:ASKS_KEPT]), "asks_open": len(asks), "settings": settings}
    if bad:
        data["settings_error"] = bad
    return data


def usd(value):
    return "-" if value is None else f"${value:.2f}"


def cell(text, n):
    return text if len(text) <= n else text[:max(1, n - 1)] + "…"


def table(claims, limit):
    """The claims as rows [(flag, text)]: a header and a row for each claim, no wider than `limit` characters, the key cut
    first, then the holder, with the gap between columns 2 and, where that is too wide, 1."""
    head = ("key", "holder", "left", "budget", "spend")
    body = [(c["key"], c["holder"], f"{c['left_s']}s", usd(c["budget_usd"]), usd(c["spend_usd"])) for c in claims]
    widths = [max(len(h), *(len(r[i]) for r in body)) for i, h in enumerate(head)]
    gap = 2
    for floor, index in ((MIN_KEY, 0), (6, 1)):
        while sum(widths) + gap * 4 > limit and widths[index] > floor:
            widths[index] -= 1
    if sum(widths) + gap * 4 > limit:
        gap = 1
    gap_text = " " * gap

    def row(cells):
        return gap_text.join(cell(c, w).ljust(w) for c, w in zip(cells, widths)).rstrip()

    return [(False, row(head))] + [(c["over_budget"], row(r)) for c, r in zip(claims, body)]


def event_text(event):
    fields = event["fields"] if isinstance(event.get("fields"), dict) else {}
    pick = lambda names: next((str(fields[n]) for n in names if fields.get(n)), "")  # noqa: E731
    subject = pick(SUBJECTS) or next((str(v) for v in fields.values()), "")
    who = pick(WHOS)
    kind = str(event["kind"])
    kind = kind.ljust(10) if len(kind) < 10 else kind + " "
    return f"#{event['seq']}  {kind}{subject}" + (f"  {who}" if who and who != subject else "")


def non_default(data):
    """{key: {value, source}} of the settings whose source is a file."""
    found = data.get("settings") if isinstance(data.get("settings"), dict) else {}
    return {k: v for k, v in found.items() if isinstance(v, dict) and v.get("source") not in (None, "default")}


def value_text(value):
    return value if isinstance(value, str) else json.dumps(value)


def settings_text(data):
    """`strategy.working=after (settings.json), …` for the settings a file sets, `all default` for none."""
    found = non_default(data)
    return ", ".join(f"{k}={value_text(v.get('value'))} ({v.get('source')})" for k, v in sorted(found.items())) or "all default"


def lines(data, width=80):
    """The body rows: the claims table (a row over budget starts `! `) with the newest events beside it from column 52 at
    100 columns or more, else under it, then two lines of the intent digest, the one-row summary of the settings a file
    sets (`settings  all default` where none does; `settings  not read: …` for a file that cannot be read) and, where
    asks to the operator are open, their count."""
    claims, events = data.get("claims", []), data.get("events", [])[:EVENTS_SHOWN]
    side = width >= SIDE_WIDTH
    left = table(claims, SIDE_COLUMN - 2 if side else width - 2) if claims else [(False, "claims    none")]
    right = ["events"] + [event_text(e) for e in events] if events else ["events    none"]
    rows = []
    if side:
        for i in range(max(len(left), len(right))):
            flag, text = left[i] if i < len(left) else (False, "")
            rows.append(("! " if flag else "") + (text.ljust(SIDE_COLUMN) + (right[i] if i < len(right) else "")).rstrip())
    else:
        rows = [("! " if flag else "") + text for flag, text in left] + right
    intents = [x for x in data.get("digest", []) if x.startswith("intent ")][:2]
    rows.append("intents   " + (intents[0] if intents else "none"))
    rows += ["          " + x for x in intents[1:]]
    if data.get("asks_open"):
        rows.append(f"asks      {data['asks_open']} open to the operator")
    rows.append("settings  " + (f"not read: {data['settings_error']}" if data.get("settings_error") else settings_text(data)))
    return rows
