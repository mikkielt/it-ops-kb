"""The query log's learn (kb/_self/querylog.md, Learn): the store's run files and the kb at HEAD become findings, and
only findings: every judged miss re-run with pack first (`fixed-since` when it now passes), then eval, alias,
expansion and gap-candidate findings, and report-only source findings on the hosts the store's fetches name. One
findings file holds the records that change a finding's state (none: no file).
"""
import csv, re
from pathlib import Path

from ql_base import HOME, places
from ql_capture import host_path
from ql_store import FETCH_KEYS, LEARN_STATES, STAGES, finding_id, finding_states, store_entries, write_findings

WEB_SOURCES = HOME / "kb" / "_self" / "web-sources.md"
ROUTE_HOST = re.compile(r"(?:[a-z0-9-]+\.)+[a-z]{2,}")
FILE_SUFFIXES = ("txt", "md", "mdx", "json", "html", "xml", "csv", "py", "yml", "yaml")  # `llms.txt` is no host
FAILED = re.compile(r"http-[45]\d\d|empty|truncated|error")  # fetch outcomes that count as failures on the host
# the staging triggers (web-sources.md, "When a family needs staging"): the numbers a test holds equal to the doc
STAGE_SHARE_ROWS = 25  # Share: a host backing at least this many rows of a root's _sources.csv
STAGE_SHARE_PERCENT = 5  # Share: or at least this share of them
STAGE_FAILURES = 3  # Failures: this many failed fetches on the host
STAGE_NEEDED_LEVEL = 1  # what a Share or Failures trigger asks for first: a route
NUMBER_WORDS = {w: i for i, w in enumerate(("zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
                                            "nine", "ten"))}


# ---------------------------------------------------------------- where a host stands

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
    """Each staging trigger whose number in ql_learn.py differs from web-sources.md."""
    ours = {"share_rows": STAGE_SHARE_ROWS, "share_percent": STAGE_SHARE_PERCENT, "failures": STAGE_FAILURES}
    doc = doc_triggers(text)
    return [f"trigger {k}: ql_learn.py has {v}, web-sources.md has {doc[k]}" for k, v in ours.items() if doc[k] != v]


def kb_host_counts():
    """({host: [(rows, the root's rows) per root]} from the roots' _sources.csv, {host: fetch errors} from their
    _fetch_state.csv), read at HEAD."""
    import kbcommon
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


# ---------------------------------------------------------------- the findings

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


def later_stage(prev, rec):
    """Whether a finding's last record is at a later stage than the one learn derives for it (a gap the research
    queue recorded `fixed-since` at stage gap): learn leaves such a finding as it is."""
    at = {s: i for i, s in enumerate(STAGES)}
    return at.get(prev.get("stage"), 0) > at.get(rec.get("stage"), 0)


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
        if prev is None or (prev.get("state") in LEARN_STATES and not later_stage(prev, rec)
                            and _key(prev) != _key(rec)):
            new.append(rec)
    for fid, prev in last.items():  # an open finding learn no longer derives: the kb at HEAD handles it now
        if fid not in derived and prev.get("state") == "open":
            new.append({**_key(prev), "state": "fixed-since"})
    total = len({**last, **{r["id"]: r for r in new}})
    if not new:
        out(f"learn: nothing new (findings={total})")
        return 0
    run_id, states = write_findings(store, entries, new, LEARN_STATES, kb_commit)
    out(f"learn: run={run_id} records={len(new)} open={states['open']} fixed-since={states['fixed-since']} "
        f"findings={total}")
    return 0
