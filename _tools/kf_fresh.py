"""The freshness stamp of a pack and its entry points: the offline stamp of a cited source read from the ledgers on disk
(`fresh_state`, `source_stamp`, `fresh_mark`), the revalidation a caller asks for (`revalidated`, `revalidate_pack`),
`pack_many` and the stored pack handles (`handled`, `keep_pack`), and `cited_lines` (stdlib only; kb/_self/tools.md,
"How the lookup tools decide").

`kbfacts.py` is the facade: it imports this module at its end, so every name here stays importable from it, and this
module reads the ground (files, units, source rows, the index directory) from it. Import `kbfacts`; imported first,
this module has the facade load it, so every module still holds the one copy `kbfacts` loads."""
import sys
if "kbfacts" not in sys.modules:  # imported first: the facade loads this stage under its name, then this copy reads it
    sys.modules.pop(__name__, None)
    import kbfacts
import csv, hashlib, json, os, re, tempfile, time
from collections import defaultdict
from datetime import date

import kbcommon, kbid
import kbfacts  # keep_pack reads pack_store() through the facade, so a caller that replaces it redirects the packs
from kbfacts import (
    ID, ROOT_LEDGERS, TOOLS, bare, fact_key, git_out, index_dir, kb_files, read, remove_file, root_files,
    source_rows
)


# ---------------------------------------------------------------- freshness stamp (offline)

CONFIRMED = re.compile(r"confirmed (\d{4}-\d\d-\d\d)")  # the census's suffix of a source row's version_or_date
_FRESH = [None, {}, {}, {}, set(), 0, False]  # [file signature, anchors, newest verified_utc per source, fetch state per source,
#                                                  ids read, scans made, every row read]
_SCOPED = [0]  # scans of _sources.csv for some ids made by ledger_rows
_PROVIDER_ROWS = []


def _ledger_rows(path, column, sids):
    """The rows of the csv at `path` whose `column` is in `sids` (every row when None), as csv.DictReader makes them:
    the file is read by csv's own reader, which takes a quoted field that holds a comma or a newline whole, and a
    dict is built only for a row of a wanted source."""
    rows = []
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            head = next(reader, [])
            if column not in head:
                return rows
            col = head.index(column)
            for row in reader:
                if row and (sids is None or len(row) > col and row[col] in sids):
                    out = dict(zip(head, row))
                    out.update(dict.fromkeys(head[len(row):]))  # a missing field is None, the extra ones a list under None
                    if len(row) > len(head):
                        out[None] = row[len(head):]
                    rows.append(out)
    except (OSError, UnicodeDecodeError, csv.Error):
        pass
    return rows


def fresh_state(sids):
    """(anchors, verified, state) of the served roots for the source ids `sids`, their rows read from the two ledgers
    when first asked and again when a file's time or size changes: `anchors` {(fact key, root-relative path, source
    id): (located, verified_utc)} of the `_anchors.csv` rows of those sources, `verified` the newest verified_utc of a
    source's anchors, `state` {source id: `_fetch_state.csv` row}. A process's first read takes the rows of `sids`
    alone, so a caller names all it will need first; its next one that finds an id unread takes every row, once, so a
    server answering many questions scans the ledgers no more than twice. No network."""
    files = [os.path.join(r.path, n) for r in kbcommon.roots() for n in (kbcommon.ANCHORS, kbcommon.STATE)]
    sig = []
    for full in files:
        try:
            st = os.stat(full)
            sig.append((full, st.st_mtime_ns, st.st_size))
        except OSError:
            continue
    if _FRESH[0] != sig:
        _FRESH[:] = [sig, {}, {}, {}, set(), _FRESH[5], False]
    _, anchors, verified, state, read = _FRESH[:5]
    todo = set(sids) - read
    if todo and not _FRESH[6]:
        _FRESH[5] += 1
        every = _FRESH[5] > 1
        want = None if every else todo
        for r in kbcommon.roots():
            for row in _ledger_rows(os.path.join(r.path, kbcommon.ANCHORS), "source_id", want):
                sid, day = row.get("source_id") or "", row.get("verified_utc") or ""
                anchors[(row.get("fact") or "", row.get("path") or "", sid)] = (row.get("status") == "located", day)
                if day > verified.get(sid, ""):
                    verified[sid] = day
            for row in _ledger_rows(os.path.join(r.path, kbcommon.STATE), "id", want):
                state[row.get("id") or ""] = row
        read |= todo
        _FRESH[6] = every
    return anchors, verified, state


_SIGNALS = {}  # url -> its provider's signals, under registry key `_SIGNALS_KEY[0]`
_SIGNALS_KEY = [None]


def _registry_key():
    """sha1 over the time and size of the files a url's signals come from: the shared registry, each root's own and
    provider.py (its pinned-url rule); a root's file name is provider.ROOT_FILE."""
    h = hashlib.sha1()
    for full in [os.path.join(TOOLS, "providers.csv"), os.path.join(TOOLS, "provider.py"),
                 *(os.path.join(r.path, "_providers.csv") for r in kbcommon.roots())]:
        try:
            st = os.stat(full)
            h.update(f"{full}\0{st.st_mtime_ns}\0{st.st_size}\n".encode())
        except OSError:
            h.update(f"{full}\0-\n".encode())
    return h.hexdigest()


def provider_signals(url):
    """The signals of the provider that serves `url` (provider.signals of provider.for_url), kept in a file of the index
    directory per registry key (_registry_key), so a lookup that cites urls it has seen imports no network module:
    `provider` is imported, at the first url the file lacks, for that url alone."""
    d = index_dir()
    memo = os.path.join(d, f"kbkey-signals-{hashlib.sha1(kbcommon.HOME.encode()).hexdigest()[:12]}.json") if d else None
    key = _registry_key()
    if _SIGNALS_KEY[0] != key:
        _SIGNALS.clear()
        _PROVIDER_ROWS.clear()  # filled again from the registry this key names, at the first url the memo lacks
        try:
            with open(memo, encoding="utf-8") as f:
                got = json.load(f)
            if got.get("key") == key:
                _SIGNALS.update({u: s for u, s in got.get("signals", {}).items() if isinstance(s, list)})
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        _SIGNALS_KEY[0] = key
    if url in _SIGNALS:
        return _SIGNALS[url]
    import provider  # not at load: it brings the network modules a pack with no source footer never needs
    if not _PROVIDER_ROWS:
        try:
            _PROVIDER_ROWS[:] = provider.providers() or [{}]
        except OSError:
            _PROVIDER_ROWS[:] = [{}]
    _SIGNALS[url] = provider.signals(provider.for_url(url, _PROVIDER_ROWS) or {}, url)
    tmp = None
    try:
        os.makedirs(d, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".kbkey-", suffix=".tmp", dir=d)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"key": key, "signals": _SIGNALS}, f, sort_keys=True)
        os.replace(tmp, memo)
    except (OSError, TypeError):  # no index directory (KB_INDEX=0) or not writable: the next lookup asks provider again
        pass
    finally:
        if tmp and os.path.exists(tmp):
            remove_file(tmp)
    return _SIGNALS[url]


def source_signal(sid, url):
    """The change signal a source's check rests on, offline: the first of its provider's signals (provider.signals, in
    the order factdiff.detect_source tries them) that its `_fetch_state.csv` row holds: `pinned` (a url whose text
    cannot change), `git` (a page of a git repository: the row's version id is its file's), `etag`, `lastmod` (a
    Last-Modified validator), `version` (a version id the page carries) or `hash` (its text's hash); `no baseline`
    when the row holds none."""
    st = fresh_state([sid])[2].get(sid) or {}
    held = {"etag": st.get("etag"), "lastmod": st.get("last_modified"), "version": st.get("version"),
            "git": st.get("version"), "hash": st.get("doc_sha256")}
    for s in provider_signals(url):
        if s == "pin":
            return "pinned"
        if held.get(s):
            return s
    return "no baseline"


def ledger_rows(ids=None):
    """source_rows(), or {} when a ledger cannot be read (a stamp is a note: it never stops a lookup); `ids`: only the
    rows of those sources, read by a scan of each root's `_sources.csv` that parses no other row, the first time in a
    process; later every row, cached as source_rows() is."""
    if ids is None or _SCOPED[0]:
        try:
            return source_rows()
        except OSError:
            return {}
    _SCOPED[0] += 1
    out, want = {}, set(ids)
    for r in kbcommon.roots():
        for row in _ledger_rows(os.path.join(r.path, kbcommon.SOURCES), "id", want):
            out.setdefault(row["id"], {**row, "root": r.name})
    return out


def source_stamp(sid, rows=None):
    """`[confirmed 2026-10-10, hash]` for a cited source: the newest of its anchors' verified_utc, its
    `_fetch_state.csv` checked_utc and the census's `confirmed <date>` in its version_or_date, and its change signal
    (source_signal); `[unconfirmed, ...]` when none dates it; "" for an id no ledger holds."""
    row = (ledger_rows([sid]) if rows is None else rows).get(sid)
    if not row:
        return ""
    _, verified, state = fresh_state([sid])
    days = [verified.get(sid, ""), ((state.get(sid) or {}).get("checked_utc") or "")[:10],
            (CONFIRMED.findall(row.get("version_or_date") or "") or [""])[-1]]
    day = max(days)
    return f"[{'confirmed ' + day if day else 'unconfirmed'}, {source_signal(sid, (row.get('url') or '').strip())}]"


def printed_lines(units, rows):
    """[{path, line, key, text, ids}] of the printed fact units that cite a source (not UNK, as factdiff.cited_facts
    reads it) the ledger holds: what revalidate (factdiff) checks and apply_revalidation marks."""
    out = []
    for u in units:
        ids = list(dict.fromkeys(i for p in u["tags"] if p["kind"] != "UNK" for i in p["ids"] if i in rows))
        if ids:
            out.append({"path": u["path"], "line": u["line"], "key": fact_key(u["text"]), "text": u["text"], "ids": ids})
    return out


def cited_ids(u, rows):
    """The source ids a fact unit cites (not UNK, as factdiff.cited_facts reads it) that the ledger `rows` holds."""
    return [i for p in u["tags"] if p["kind"] != "UNK" for i in p["ids"] if i in rows]


def fresh_mark(u, rows=None):
    """`unanchored` and `source changed` for a printed fact unit, joined by `; `, "" for neither: a source the fact
    cites (not UNK, as factdiff.cited_facts reads it) has no located anchor for it (the fact is dated at its source
    only), or the anchor's verified_utc is before the source's changed_utc. Offline; "" for a unit citing no source."""
    rows = ledger_rows() if rows is None else rows
    sids = cited_ids(u, rows)
    if not sids:
        return ""
    anchors, _, state = fresh_state(sids)
    key, rel = fact_key(u["text"]), bare(u["path"])
    unanchored = changed = False
    for sid in dict.fromkeys(sids):
        located, day = anchors.get((key, rel, sid), (False, ""))
        unanchored |= not located
        changed |= bool(day) and day < ((state.get(sid) or {}).get("changed_utc") or "")[:10]
    return "; ".join(m for m, on in (("unanchored", unanchored), ("source changed", changed)) if on)


def format_sources(srcs, rows=None):
    """The footer lines of `srcs` [(id, url, superseded by)], `rows` the ledger rows of their ids when the caller has
    read them."""
    if rows is None:
        rows = ledger_rows([i for i, _, _ in srcs])
    fresh_state(i for i, _, _ in srcs if i in rows)  # one read of the ledgers for all the footer's sources
    return [f"  -> {i}  {u}" + (f"  (superseded by {s})" if s else "") + (f"  {st}" if (st := source_stamp(i, rows)) else "")
            for i, u, s in srcs]


FACT_LINE = re.compile(r"^- (\S+):(\d+)(?=[ \n]|$)")
OFFLINE_MARK = re.compile(r" \[(?:unanchored|source changed)(?:; (?:unanchored|source changed))*\]")
FOOTER_LINE = re.compile(r"^  -> (\S+)  ")
LIVE_WORD = {"pinned": "unchanged", "unchanged": "unchanged", "changed": "changed", "replaced": "changed",
             "moved": "moved", "gone": "gone", "soft-404": "gone", "new": "read, no earlier baseline"}


def source_freshness(ids, rows=None):
    """{source id: {age_days, lifetime_days, basis, stale}} for the ids a ledger holds, with no network: the source's
    freshness lifetime (provider.lifetimes: its recorded changes, its Learn file's commits, its page date, its
    provider's default; None for a pinned url) against its age, the time since the newer of its last check and its
    facts' verified date. A source no check or anchor dates (age None) is stale unless it is pinned."""
    rows = rows or ledger_rows()
    ids = list(ids)
    _, verified, state = fresh_state(ids)
    now, by_root = time.time(), defaultdict(dict)
    for i in ids:
        if rows.get(i):
            by_root[rows[i].get("root") or ""][i] = rows[i]
    out = {}
    for name, srcs in by_root.items():
        try:
            root = kbcommon.root(name)
        except (KeyError, kbcommon.RootError):
            continue
        out.update(root_freshness(srcs, state, verified, root, now))
    return out


def root_freshness(srcs, state, verified, root, now):
    """source_freshness of the sources `srcs` ({id: `_sources.csv` row}) of one root `root`, against `state` ({id:
    `_fetch_state.csv` row}), `verified` ({id: newest verified_utc of its anchors}) and the epoch `now`: the one place
    a source's age and staleness are decided, which a lookup and `fetch.py --status` both read."""
    import provider  # not at load: it brings the network modules a pack with no source footer never needs
    out = {}
    for i, lt in provider.lifetimes(srcs, state, provider.providers(root), root, now).items():
        dates = (provider.last_check(state.get(i), srcs[i]), provider.stamp_epoch(verified.get(i, "")))
        last = max((d for d in dates if d is not None), default=None)
        age = None if last is None else max(now - last, 0) / provider.DAY
        out[i] = {"age_days": age, "lifetime_days": lt["days"], "basis": lt["basis"],
                  "stale": lt["days"] is not None and (age is None or age > lt["days"])}
    return out


def revalidated(text, rev, fresh=None):
    """`text` of a pack with the outcome of a revalidation (factdiff.revalidate) put in: each printed fact line it
    checked gets `[current DATE]`, `[moved DATE]` (a line under it holds the new passage, and the page), `[not found
    DATE]` or `[source-dated only DATE]` in place of the offline marks; a line none of whose sources could be checked
    keeps them. A footer line of a source it asked ends with what the page showed; the last line says how many sources
    it asked, how many it answered from a check younger than the provider's pacing, and, with the reason, each it could
    not check (its facts keep the offline stamp). `fresh` (source_freshness of the cited sources; the revalidation
    asked only those past their lifetime): each such source's footer line first carries `[stale: AGE old, lifetime
    DAYS]`, the stamp the page's answer follows, and the last line counts the sources past their lifetime."""
    out = []
    for ln in text.split("\n"):
        m = FACT_LINE.match(ln)
        r = rev["lines"].get((m.group(1), int(m.group(2)))) if m else None
        if r and r["outcome"]:
            tail = OFFLINE_MARK.sub("", ln[m.end():], count=1)
            note = f"; {', '.join(r['unchecked'])} not checked" if r["unchecked"] else ""
            out.append(f"{ln[:m.end()]} [{r['outcome']} {r['checked_utc'][:10]}{note}]{tail}")
            if r["outcome"] == "moved":
                where = f" ({r['target']})" if r["target"] else ""
                out.append(f'    now{where}: "{r["passage"]}"' if r["passage"] else f"    now{where}: no passage located")
            continue
        if r:  # a source asked live whose answer for this line was cut short: the footer does not say it
            cut = sorted({w for i, w in r["unchecked"].items() if rev["sources"].get(i, {}).get("state") != "offline"})
            if cut:
                ln = f"{ln[:m.end()]} [not checked live: {', '.join(cut)}]{ln[m.end():]}"
            out.append(ln)
            continue
        f = FOOTER_LINE.match(ln)
        src = rev["sources"].get(f.group(1)) if f else None
        due = (fresh or {}).get(f.group(1)) if f else None
        if due and due["stale"]:
            ln += (f"  [stale: {due['age_days']:.0f}d old, lifetime {due['lifetime_days']:.0f}d]" if due["age_days"] is not None
                   else f"  [stale: never confirmed, lifetime {due['lifetime_days']:.0f}d]")
        if src and src["state"] != "offline":
            ln += f"  [live {src['checked_utc'][:10]}: {LIVE_WORD.get(src['verdict'], src['verdict'] or 'checked')}]"
        elif src:
            ln += "  [not checked live]"
        out.append(ln)
    live = sum(1 for v in rev["sources"].values() if v["state"] == "live")
    cached = sum(1 for v in rev["sources"].values() if v["state"] == "cached")
    why = defaultdict(list)
    for i, v in rev["sources"].items():
        if v["state"] == "offline":
            why[v["why"]].append(i)
    stale = sum(1 for v in (fresh or {}).values() if v["stale"])
    if fresh is not None and not fresh:
        out.append(f"revalidate {rev['date']}: no printed fact line cites a source to check")
    elif fresh is not None and not stale:
        out.append(f"revalidate {rev['date']}: none of the {len(fresh)} cited source(s) is past its freshness lifetime, "
                   "none asked")
    elif not rev["sources"]:
        out.append(f"revalidate {rev['date']}: no printed fact line cites a source to check")
    else:
        head = f"{stale} of the {len(fresh)} cited source(s) past their freshness lifetime: " if fresh is not None else ""
        out.append(f"revalidate {rev['date']}: {head}{live} source(s) asked live, {cached} answered from a check younger than "
                   + ("its freshness lifetime" if fresh is not None else "its provider's pacing")
                   + ("; not checked, the offline stamp stands: "
                      + "; ".join(f"{', '.join(ids)} ({w})" for w, ids in why.items()) if why else ""))
    return "\n".join(out)


def revalidate_pack(res, stale_only=False):
    """pack_many's result with its printed fact lines revalidated against their sources now (revalidated): `text` is
    rewritten and `revalidate` holds factdiff.revalidate's answer. `stale_only`: only the cited sources past their
    freshness lifetime (source_freshness) are asked, and a result of a live check younger than the lifetime is reused;
    the others keep the offline stamp, and `revalidate` also holds `freshness`. Never raises: a lookup that cannot
    revalidate says so and keeps its offline text."""
    import factdiff  # not at load: the detection tool and the network modules it brings are for this call only
    printed = list({(p["path"], p["line"]): p for r in res["results"] for p in r.get("printed", [])}.values())
    fresh = reuse = None
    try:
        if stale_only:
            fresh = source_freshness(list(dict.fromkeys(i for p in printed for i in p["ids"])))
            if not fresh:  # no printed line cites a source: the pack has nothing to add
                return {**res, "revalidate": None}
            due = {i: f["lifetime_days"] * 86400 for i, f in fresh.items() if f["stale"]}
            printed = [{**p, "ids": [i for i in p["ids"] if i in due], "cites": len(set(p["ids"]))} for p in printed]
            reuse = due
        rev = (factdiff.revalidate(printed, reuse=reuse) if reuse or not stale_only
               else {"date": factdiff.today(), "lines": {}, "sources": {}})  # nothing past its lifetime: nothing asked
    except Exception as e:  # noqa: BLE001 - a lookup always answers
        return {**res, "text": res["text"] + f"\nrevalidate: not done, the offline stamp stands ({type(e).__name__}: {str(e)[:120]})",
                "revalidate": None}
    res["revalidate"] = {"date": rev["date"], "sources": rev["sources"],
                         "lines": {f"{p}:{n}": {k: v for k, v in r.items() if k != "text"} for (p, n), r in rev["lines"].items()}}
    if fresh is not None:
        res["revalidate"]["freshness"] = fresh
    res["text"] = revalidated(res["text"], rev, fresh)
    return res


MAX_QUESTIONS = 6
PART_BUDGET_MIN = 800  # tokens per part of a 3+ part pack


def pack_many(questions, budget=1200, domain=None, fmt="detailed", root=None, invalidated=False, item=None,
              revalidate=False, as_of=None):
    """One pack per question (1-6), each with its own coverage verdict, and one shared source footer:
    {verdict (the worst), results, text}. A part of a kind a tool decides is answered by that tool (pack_routed).
    `revalidate` (rag.py pack --revalidate, kb_pack's revalidate): True checks the printed fact lines against their
    sources now and marks them with the outcome (revalidate_pack); "stale" (kb_pack's default, kb_ask.py) asks only
    the cited sources past their freshness lifetime and prints the stale stamp of each; False (the kb: hook, which
    never goes to the network) leaves the pack as it was.
    The text's last line before a revalidation's is `pack: P-<8 hex>`, the handle `pack` holds (handled); a weak or
    none pack has a `feedback:` line above it naming a ready kb_feedback call (none on a server limited to named roots).
    A single question gives exactly pack()'s text, or its routed answer. With 3 or more questions
    each part gets 2 * budget / n tokens, at least PART_BUDGET_MIN (never more than budget): measured on the eval set,
    800 tokens keep 98% of the expected article's fact lines that 1200 print, and a 6-part pack shrinks by a third.
    `route` is the overall route of the parts, printed as the pack's first line: `web` when every part routes web,
    else `split` when any part routes; None (no line) when none does. One question gives its pack's route.
    `as_of` (YYYY-MM-DD; rag.py pack --as-of, kb_pack's as_of) ranks only the facts whose validity window holds the date
    in every part (pack), and answers no part from the experts (pack_routed); a date that is not an existing
    YYYY-MM-DD raises ValueError."""
    from kf_route import pack_routed  # the routed stage builds on this module: imported when a pack is asked for
    if as_of is not None and not (isinstance(as_of, str) and re.fullmatch(r"\d{4}-\d\d-\d\d", as_of) and date.fromisoformat(as_of)):
        raise ValueError(f"as_of {as_of!r} is not a date (YYYY-MM-DD)")
    qs = [q.strip() for q in questions if q and q.strip()][:MAX_QUESTIONS]
    if len(qs) == 1:
        res = pack_routed(qs[0], budget, domain, fmt=fmt, root=root, invalidated=invalidated, item=item, as_of=as_of)
        one = {"verdict": res["verdict"], "route": res["route"], "results": [res], "text": res["text"]}
        one = handled(one, qs, budget, domain, fmt, root, invalidated, item, as_of=as_of)
        return revalidate_pack(one, revalidate == "stale") if revalidate else one
    part = budget if len(qs) < 3 else max(min(budget, PART_BUDGET_MIN), 2 * budget // len(qs))
    results = [pack_routed(q, part, domain, fmt=fmt, footer=False, root=root, invalidated=invalidated, item=item,
                           as_of=as_of) for q in qs]
    routes = [r["route"] for r in results if r["route"]]
    route = None if not routes else "web" if all(r["route"] == "web" for r in results) else "split"
    out, seen, srcs = ([f"route: {route}"] if route else []), set(), []
    for i, (q, res) in enumerate(zip(qs, results), start=1):
        out += [f"# Q{i}: {q}", res["text"], ""]
        for row in res["source_rows"]:
            if row[0] not in seen:
                seen.add(row[0])
                srcs.append(row)
    if srcs and fmt != "concise":
        out += ["sources:"] + format_sources(srcs)
    order = ("none", "weak", "good")
    many = {"verdict": min((r["verdict"] for r in results), key=order.index), "route": route, "results": results,
            "text": "\n".join(out).rstrip()}
    many = handled(many, qs, budget, domain, fmt, root, invalidated, item, as_of=as_of)
    return revalidate_pack(many, revalidate == "stale") if revalidate else many


PACK_HANDLE = re.compile(r"P-[0-9a-f]{8}")
PACK_HANDLE_DAYS = 7  # a stored pack is kept this long (keep_pack)
PACK_HANDLE_KEEP = 500  # and at most this many, the newest


def kb_commit():
    """The kb copy's commit: a clone's HEAD, or an installed plugin copy's version directory when that is a commit id,
    else "" (the handle then names the questions and arguments alone)."""
    out = git_out("rev-parse", "HEAD")
    if out:
        return out.decode("utf-8", "replace").strip()
    name = os.path.basename(os.path.normpath(kbcommon.HOME))
    return name if re.fullmatch(r"[0-9a-f]{7,40}", name) else ""


def pack_handle(questions, budget=1200, domain=None, fmt="detailed", root=None, invalidated=False, item=None,
                commit=None, as_of=None):
    """`P-<8 hex>`: the hash of the questions, the pack arguments and the kb commit, so one pack on one commit has one
    handle on every server and in the tools, with no session. `revalidate` is no argument of it: stdio and kb_http.py
    differ in what they revalidate, not in the pack they answer. An `as_of` date is part of the key when given (a pack
    without one keeps the handle it always had)."""
    qs = [q.strip() for q in questions if q and q.strip()][:MAX_QUESTIONS]
    item = item.get("id") if isinstance(item, dict) else item  # pack_many's brief (item_brief) or its id
    key = json.dumps([qs, budget, domain or None, fmt, root or None, bool(invalidated), item or None,
                      kb_commit() if commit is None else commit],
                     ensure_ascii=False, separators=(",", ":")) + (f"as_of={as_of}" if as_of else "")
    return "P-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]


def pack_store():
    """The directory of stored packs (under the index directory, `_cache/` of the clone: never committed), or None."""
    d = index_dir()
    return os.path.join(d, "packs") if d else None


def keep_pack(handle, questions, text, commit):
    """Store handle -> {questions, lines (the printed lines), commit, ts} for PACK_HANDLE_DAYS and PACK_HANDLE_KEEP
    handles, the oldest pruned. Best effort: a lookup never fails for its handle."""
    d, tmp = kbfacts.pack_store(), None
    if not d:
        return
    try:
        os.makedirs(d, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".pack-", suffix=".tmp", dir=d)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"handle": handle, "questions": questions, "commit": commit, "ts": time.time(),
                       "lines": text.splitlines()}, f, ensure_ascii=False)
        os.replace(tmp, os.path.join(d, handle + ".json"))
        now, kept = time.time(), []
        for name in os.listdir(d):
            full = os.path.join(d, name)
            if not (name.endswith(".json") and PACK_HANDLE.fullmatch(name[:-5])):
                continue
            mtime = os.stat(full).st_mtime
            if now - mtime > PACK_HANDLE_DAYS * 86400:
                os.remove(full)
            else:
                kept.append((mtime, full))
        for _mtime, full in sorted(kept)[:max(0, len(kept) - PACK_HANDLE_KEEP)]:
            os.remove(full)
    except OSError:
        pass
    finally:
        if tmp and os.path.exists(tmp):
            remove_file(tmp)


def handled(res, questions, budget=1200, domain=None, fmt="detailed", root=None, invalidated=False, item=None,
            as_of=None):
    """`res` (pack_many's or pack_routed's result) with a last line `pack: P-<8 hex>` (pack_handle) added to `text`
    and the handle in `res["pack"]`, and the offline pack stored (keep_pack). A weak or none pack gets one line
    above the handle, `feedback: kb_feedback(pack="P-<8 hex>", outcome="missed")` (a good pack none): the call an agent
    makes when the lookup did not answer, with its handle filled in; none on a server limited to named roots
    (kbcommon.serving(): --roots, kb_http.py), which does not list kb_feedback. Never raises."""
    try:
        commit = kb_commit()
        handle = pack_handle(questions, budget, domain, fmt, root, invalidated, item, commit, as_of)
        hint = res.get("verdict") in ("weak", "none") and not kbcommon.serving()
        ask = f'feedback: kb_feedback(pack="{handle}", outcome="missed")\n' if hint else ""
        res["text"] = f"{res['text']}\n{ask}pack: {handle}"
        res["pack"] = handle
        qs = [q.strip() for q in questions if q and q.strip()][:MAX_QUESTIONS]
        keep_pack(handle, qs, res["text"], commit)
    except Exception:  # noqa: BLE001 - see the docstring
        pass
    return res


def cited_lines(ids):
    """{id: [(qualified path, line)]}: every kb file line (every root's domain files and ledgers, not _sources.csv)
    naming the id."""
    want = {kbid.canonical_id(i) for i in ids}
    out = defaultdict(list)
    files = list(kb_files((".md", ".csv"))) + root_files(ROOT_LEDGERS)
    for rel in files:
        text = read(rel)
        if not text or not any(i in text for i in want):
            continue
        for n, ln in enumerate(text.splitlines(), start=1):
            for i in set(ID.findall(ln)) & want:
                out[i].append((rel, n))
    return out
