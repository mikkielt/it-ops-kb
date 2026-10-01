#!/usr/bin/env python3
"""Check kb consistency (stdlib only). Exit 1 on any error.

  check.py [--root NAME]      every root (kbcommon.roots(): kb/public, kb/<name>/, KB_ROOTS), or one

- every root's _root.md is well-formed, and no two roots share a name or an id prefix;
- per root: _sources.csv and _artifacts.csv exist and have their required columns;
- every .csv has the same number of columns in every row;
- source ids in a root's _sources.csv are unique and well-formed: the root's `<prefix>-<8 base32>` equal to the
  hash of the row's url (public also keeps legacy S<digits>), with no two different urls sharing a hash id (kbid.py);
- every source has a licence and a reuse class from kbcommon.REUSE (copy, quote, paraphrase, unknown);
- a non-empty superseded_by names another source id of the same root and forms no cycle;
- every _artifacts.csv row names a known source of its root and an existing file;
- every <root>/_snapshots/<id>.txt is a copy source of that root and starts with its attribution header (source, url,
  title, publisher, licence as in the source row, retrieved, changes);
- a root's _anchors.csv (factdiff.py), when present: a 12-hex fact key, an existing file, a known source, status
  located (16-hex sha and terms) or unlocated:<reason> (no sha, terms or quote), a quote of at most 25 words and only
  from a copy or quote source, a YYYY-MM-DD verified_utc, no (fact, path, source_id) twice;
- every Markdown file is readable UTF-8;
- every [DOC|CODE|DER|COMMUNITY <id>] tag and data-file source column cites a source of its own root: an id of
  another root is an error that says so (a root cites only its own sources; add the source to its _sources.csv);
  files outside the roots (kb/_self, _tools/ data, README.md) may cite any root's ids;
- no answer id (`## <ID>. ` heading) appears twice in a root's _answers.md; QK answers use QK-<slug>;
- a root's and kb/_self's _decisions.csv and decision-makers.csv (kbcommon.DECISION_COLS, MAKER_COLS), when present: the
  exact header; a decision with a `D-<8 base32>` id (unique), text, a source (its ids known), a YYYY-MM-DD date, a status
  of proposed|active|invalidated|superseded, a `;`-separated context of `kind:value` references (item, fact, source,
  article, domain: the source, article or domain of a decision not invalidated must exist), a `by_ref` that names a maker of
  the root's file or of kb/_self's central register, `invalidated_reason` and `invalidated_date` exactly when the status
  is invalidated, `supersedes` naming other decisions of the file (and every superseded one named by another), an empty or
  valid review_by; a maker with a slug id (unique) and a role; and no name in a row of a root that is not internal or
  of kb/_self (kbcommon.maker_names_allowed: the makers' `name` is empty, and a decision's `by` is its maker's role);
- every [DECISION <id>] tag names a decision of its own root's _decisions.csv (an id of another root is an error that
  says so; a tag with no id is one too); files outside the roots (kb/_self, README.md) may cite any root's or
  kb/_self's decisions, and a first word that does not start `D-` there is a placeholder in prose, not checked;
- every topic file's front matter has topic, priority, retrieved_utc, sources and status in {complete, partial, unknown};
- every `topic: <domain>/<slug>` marker in a root's _gaps.md and _conflicts.md names a topic of that root.
Messages name files by their qualified path `<root>/<path>`, or by their path in this repository outside the roots.
"""
import argparse, csv, datetime, os, re, sys
from collections import Counter
from pathlib import Path
import kbcommon, kbid

TOPIC_MARK = re.compile(r"\btopic:\s*`?([a-z0-9-]+/[a-z0-9./-]+?)`?(?=[\s,;.)\]]|$)")
TAG = re.compile(r"\[(?:DOC|CODE|DER|COMMUNITY)\s([^\]]+)\]")  # \s: a tag may wrap after DOC
DECISION_TAG = re.compile(r"\[(?:DOC|CODE|DER|COMMUNITY|UNK|DECISION)\b[^\]]*\]")  # a DECISION part may follow another
DECISION_PART = re.compile(r"(?:\[|[;,])\s*DECISION\b\s*([^\s:;,\]]*)")  # a part of a tag: its first word is the id
SKIP = {"_cache", "_private", "node_modules", "__pycache__"}
errors = []


def read_csv(root, name, required):
    """Rows of a root's index CSV, or [] with an error if it is missing or lacks a required column."""
    try:
        return kbcommon.load_csv(os.path.join(root.path, name), required)[1]
    except kbcommon.CsvError as e:
        errors.append(f"{root.name}: {e}".replace(root.path + os.sep, ""))
        return []


def walk(base, exts, skip_roots=()):
    """Files under base with these extensions, skipping hidden dirs, caches and (absolute) skip_roots."""
    for d, dirs, files in os.walk(base):
        dirs[:] = sorted(x for x in dirs if not x.startswith(".") and x not in SKIP
                         and os.path.join(d, x) not in skip_roots)
        for f in sorted(files):
            if f.endswith(exts):
                yield os.path.join(d, f)


def check_root_ledgers(root, owner):
    """The ledger checks of one root; returns its known source ids."""
    q = lambda p: kbcommon.qualify(root, p)  # noqa: E731
    sources = read_csv(root, kbcommon.SOURCES, ("id", "url", "licence", "reuse", "superseded_by"))
    ids = [r["id"] for r in sources]
    known = set(ids)
    errors.extend(f"{q(kbcommon.SOURCES)}: duplicate source id {i}" for i, n in sorted(Counter(ids).items()) if n > 1)
    errors.extend(f"{q(kbcommon.SOURCES)}: {e}" for e in kbid.check_sources(sources, root.id_prefix, root.name))
    for r in sources:
        if not (r.get("licence") or "").strip():
            errors.append(f"{q(kbcommon.SOURCES)}: source {r['id']} has no licence")
        reuse = (r.get("reuse") or "").strip()
        if reuse not in kbcommon.REUSE:
            errors.append(f"{q(kbcommon.SOURCES)}: source {r['id']} reuse {reuse!r} is not one of "
                          f"{', '.join(kbcommon.REUSE)}" if reuse else f"{q(kbcommon.SOURCES)}: source {r['id']} has no reuse class")
    succ = {r["id"]: r["superseded_by"].strip() for r in sources if (r.get("superseded_by") or "").strip()}
    for sid, nxt in sorted(succ.items()):
        if nxt not in known:
            errors.append(f"{q(kbcommon.SOURCES)}: source {sid} superseded_by unknown source {nxt}")
            continue
        seen, cur = {sid}, nxt
        while cur in succ and cur not in seen:
            seen.add(cur)
            cur = succ[cur]
        if cur in seen:
            errors.append(f"{q(kbcommon.SOURCES)}: source {sid} superseded_by chain forms a cycle through {cur}")
    try:
        with open(os.path.join(root.path, kbcommon.ANSWERS), encoding="utf-8") as f:
            aids = kbid.answer_ids(f.read())
    except FileNotFoundError:
        aids = []
    except (OSError, UnicodeDecodeError) as e:
        errors.append(f"{q(kbcommon.ANSWERS)} is unreadable: {e}")
        aids = []
    errors.extend(f"duplicate answer id {i} in {q(kbcommon.ANSWERS)}" for i, n in sorted(Counter(aids).items()) if n > 1)
    errors.extend(f"answer id {i} in {q(kbcommon.ANSWERS)}: QK ids are QK-<slug> (lowercase, hyphenated)"
                  for i in aids if i.startswith("QK") and not kbid.QK_ID.fullmatch(i))
    check_anchors(root, {r["id"]: (r.get("reuse") or "").strip() for r in sources})
    check_snapshots(root, {r["id"]: r for r in sources})
    for r in read_csv(root, kbcommon.ARTIFACTS, ("path", "source_id", "sha256")):
        if r["source_id"] not in known:
            errors.append(f"artifact {q(r['path'])} names unknown source {r['source_id']}")
        if not os.path.isfile(os.path.join(root.path, r["path"])):
            errors.append(f"artifact {q(r['path'])} is missing")
    return known


ANCHOR_STATUS = re.compile(r"located|unlocated:(?:%s)" % "|".join(kbcommon.ANCHOR_REASONS))


def check_anchors(root, reuse):
    """The format of a root's _anchors.csv (factdiff.py), when it has one."""
    if not os.path.exists(os.path.join(root.path, kbcommon.ANCHORS)):
        return
    name = kbcommon.qualify(root, kbcommon.ANCHORS)
    seen = set()
    for n, r in enumerate(read_csv(root, kbcommon.ANCHORS, kbcommon.ANCHOR_COLS), start=2):
        bad = []
        key = (r["fact"], r["path"], r["source_id"])
        if key in seen:
            bad.append("duplicate (fact, path, source_id)")
        seen.add(key)
        if not re.fullmatch(r"[0-9a-f]{12}", r["fact"]):
            bad.append(f"fact {r['fact']!r} is not a 12-hex fact key")
        if r["source_id"] not in reuse:
            bad.append(f"unknown source {r['source_id']}")
        if not os.path.isfile(os.path.join(root.path, r["path"])):
            bad.append(f"no file {r['path']}")
        if not ANCHOR_STATUS.fullmatch(r["status"]):
            bad.append(f"status {r['status']!r} (located or unlocated:{'|'.join(kbcommon.ANCHOR_REASONS)})")
        elif r["status"] == "located":
            if not re.fullmatch(r"[0-9a-f]{16}", r["sha"]):
                bad.append("a located anchor needs a 16-hex sha")
            if not r["terms"].strip():
                bad.append("a located anchor needs its terms")
        elif r["sha"] or r["terms"] or r["quote"]:
            bad.append("an unlocated anchor has no sha, terms or quote")
        if r["quote"]:
            if len(r["quote"].split()) > kbcommon.QUOTE_WORDS:
                bad.append(f"quote over {kbcommon.QUOTE_WORDS} words")
            if reuse.get(r["source_id"]) not in ("copy", "quote"):
                bad.append(f"a quote of a source whose reuse is {reuse.get(r['source_id'])!r} (only copy or quote)")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["verified_utc"]):
            bad.append("verified_utc is not YYYY-MM-DD")
        errors.extend(f"{name}:{n} {b}" for b in bad)


SNAP_KEYS = ("source", "url", "title", "publisher", "licence", "retrieved", "changes")


def check_snapshots(root, sources):
    """Every <root>/_snapshots/<id>.txt: a copy source of the root, with its attribution header."""
    d = os.path.join(root.path, kbcommon.SNAPSHOTS)
    if not os.path.isdir(d):
        return
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".txt"):
            continue
        name = kbcommon.qualify(root, f"{kbcommon.SNAPSHOTS}/{fn}")
        sid = fn[:-4]
        try:
            with open(os.path.join(d, fn), encoding="utf-8") as f:
                head = f.read(4000).partition("\n---\n")[0]
        except (OSError, UnicodeDecodeError) as e:
            errors.append(f"{name} is unreadable: {e}")
            continue
        meta = dict(ln.split(": ", 1) for ln in head.splitlines() if ": " in ln)
        missing = [k for k in SNAP_KEYS if not meta.get(k, "").strip()]
        if missing:
            errors.append(f"{name}: attribution header lacks {', '.join(missing)}")
        src = sources.get(sid)
        if src is None or meta.get("source") != sid:
            errors.append(f"{name}: not a source of {root.name} (or its header names another)")
        elif (src.get("reuse") or "").strip() != "copy":
            errors.append(f"{name}: source {sid} has reuse {src.get('reuse')!r}; only copy sources may be kept verbatim")
        elif meta.get("licence") != " ".join((src.get("licence") or "").split()):
            errors.append(f"{name}: licence differs from {sid}'s row in {kbcommon.SOURCES}")


def is_date(s):
    """Whether s is a real YYYY-MM-DD date."""
    try:
        datetime.date.fromisoformat(s)
    except ValueError:
        return False
    return re.fullmatch(r"\d{4}-\d{2}-\d{2}", s) is not None


def read_table(path, label, cols):
    """The rows of an optional decision file: None when there is none, or (with an error) when it cannot be read or
    its header is not exactly `cols`."""
    if not path.is_file():
        return None
    try:
        header, rows = kbcommon.load_csv(str(path))
    except kbcommon.CsvError as e:
        errors.append(f"{label}: {e}".replace(str(path), label))
        return None
    if header != cols:
        errors.append(f"{label}: header is {','.join(header or [])!r}, not {','.join(cols)!r}")
        return None
    return rows


def central_makers():
    """{id: role} of the central register, kb/_self/decision-makers.csv; {} when it is absent or unreadable (check.py
    reports that on the file itself)."""
    try:
        rows = kbcommon.load_csv(str(Path(kbcommon.SELF) / kbcommon.DECISION_MAKERS))[1]
    except kbcommon.CsvError:
        return {}
    return {(r.get("id") or "").strip(): (r.get("role") or "").strip() for r in rows}


def context_error(kind, value, root, base, owner, known):
    """Why a context reference names nothing (an existing source, article or domain), or None. kb/_self (root None)
    qualifies an article or a domain as <root>/<path>."""
    if kind == "source":
        return cite_error(value, root, owner, known)
    if kind not in ("article", "domain"):  # an item or a fact may be gone: kbdecide.py sweep invalidates or relinks
        return None
    where, rel = base, value
    if root is None:
        owner_root, rel = kbcommon.split(value)
        if owner_root is None:
            return f"names no root; kb/_self decisions write {kind}:<root>/<path>"
        where = Path(owner_root.path)
    if kind == "article":
        return None if rel and (where / f"{rel}.md").is_file() else f"names no article {value}"
    return None if rel and (where / rel).is_dir() else f"names no domain {value}"


def check_decisions(root, owner, known):
    """The format of a root's decision files, or of kb/_self's when `root` is None (kbcommon.DECISION_COLS, MAKER_COLS):
    each is optional, and a root's by_ref names a maker of its own file or of the central register."""
    base = Path(kbcommon.SELF) if root is None else Path(root.path)
    name = (lambda n: f"kb/_self/{n}") if root is None else (lambda n: kbcommon.qualify(root, n))
    field = lambda r, k: (r.get(k) or "").strip()  # noqa: E731
    mname = name(kbcommon.DECISION_MAKERS)
    who = "kb/_self, which is published" if root is None else f"a root that is {root.visibility}"
    own, seen = {}, set()
    for n, r in enumerate(read_table(base / kbcommon.DECISION_MAKERS, mname, kbcommon.MAKER_COLS) or [], start=2):
        mid, bad = field(r, "id"), []
        if not kbcommon.MAKER_ID.fullmatch(mid):
            bad.append(f"id {mid!r} is not a lowercase slug (a-z, 0-9, -)")
        elif mid in seen:
            bad.append(f"duplicate decision maker id {mid}")
        seen.add(mid)
        own[mid] = field(r, "role")
        if not own[mid]:
            bad.append("no role")
        if field(r, "name") and not kbcommon.maker_names_allowed(root):
            bad.append(f"a name in {who}, not an internal root: keep the role only")
        errors.extend(f"{mname}:{n} {b}" for b in bad)
    central = own if root is None else central_makers()
    dname = name(kbcommon.DECISIONS)
    rows = read_table(base / kbcommon.DECISIONS, dname, kbcommon.DECISION_COLS) or []
    ids = [field(r, "id") for r in rows]
    superseding = {s for r in rows for s in kbcommon.split_list(r.get("supersedes"))}
    for n, r in enumerate(rows, start=2):
        did, status, by, ref, bad = field(r, "id"), field(r, "status"), field(r, "by"), field(r, "by_ref"), []
        if not kbcommon.DECISION_ID.fullmatch(did):
            bad.append(f"id {did!r} is not D-<8 base32>")
        elif ids.count(did) > 1:
            bad.append(f"duplicate decision id {did}")
        if not field(r, "text"):
            bad.append("no text")
        if status not in kbcommon.DECISION_STATUS:
            bad.append(f"status {status!r} is not one of {'|'.join(kbcommon.DECISION_STATUS)}")
        if not is_date(field(r, "date")):
            bad.append(f"date {field(r, 'date')!r} is not YYYY-MM-DD")
        src = field(r, "source")
        if not src:
            bad.append("no source")
        bad.extend(e for e in (cite_error(s, root, owner, known) for s in kbid.SOURCE_ID.findall(src)) if e)
        if ref and ref not in own and ref not in central:
            bad.append(f"by_ref {ref!r} names no decision maker in {mname} or the central register")
        elif status != "proposed" and not (by or ref):
            bad.append("names no decision maker (by or by_ref) though it is not proposed")
        if not kbcommon.maker_names_allowed(root) and (by or ref):  # no names: `by` is the role of a maker it references
            role = own.get(ref, central.get(ref)) if ref else None
            if not ref:
                bad.append(f"by_ref is empty: {who}, not an internal root, keeps no names, so by "
                           f"is the role of a maker it references")
            elif role is not None and by != role:
                bad.append(f"by {by!r} is not the role {role!r} of {ref}: {who}, not an internal root, keeps no names")
        refs = kbcommon.context_refs(r.get("context"))
        if not refs:
            bad.append("no context (kind:value references to the item, fact, source, article or domain it is about)")
        for kind, value in refs:
            if not kind:
                bad.append(f"context part {value!r} is not <kind>:<value> with kind {'|'.join(kbcommon.CONTEXT_KINDS)}")
            elif not kbcommon.CONTEXT_KINDS[kind].fullmatch(value):
                bad.append(f"context {kind}:{value} is not a valid {kind} reference")
            elif status != "invalidated" and (e := context_error(kind, value, root, base, owner, known)):
                bad.append(f"context {kind}:{value} {e}")
        reason, when = field(r, "invalidated_reason"), field(r, "invalidated_date")
        if status == "invalidated":
            if not reason:
                bad.append("invalidated without an invalidated_reason")
            if not is_date(when):
                bad.append(f"invalidated_date {when!r} is not YYYY-MM-DD")
        elif reason or when:
            bad.append(f"invalidated_reason or invalidated_date on a decision that is {status or 'without a status'}, not invalidated")
        for old in kbcommon.split_list(r.get("supersedes")):
            if old == did or old not in ids:
                bad.append(f"supersedes {old!r}: not another decision of {dname}")
        if status == "superseded" and did not in superseding:
            bad.append("superseded, but no decision names it in supersedes")
        if field(r, "review_by") and not is_date(field(r, "review_by")):
            bad.append(f"review_by {field(r, 'review_by')!r} is not YYYY-MM-DD")
        errors.extend(f"{dname}:{n} {b}" for b in bad)


def cite_error(sid, root, owner, known):
    """The error for citing sid from a file of root (None: outside the roots), or None when the id is fine."""
    if root is None:
        return None if sid in known["*"] else f"cites unknown source {sid}"
    if sid in known[root.name]:
        return None
    other = owner.get(kbid.id_prefix(sid))
    if other and other.name != root.name and sid in known[other.name]:
        return (f"cites {sid} of root {other.name}; a root cites only its own sources: add the source to "
                f"{root.name}/{kbcommon.SOURCES} (python3 _tools/kbid.py url <URL> --root {root.name})")
    return f"cites unknown source {sid}"


def decision_ids(base):
    """The ids of the decisions in base's `_decisions.csv`; empty when it has none or cannot be read (check_decisions
    reports that on the file itself)."""
    try:
        rows = kbcommon.load_csv(str(Path(base) / kbcommon.DECISIONS))[1]
    except kbcommon.CsvError:
        return set()
    return {(r.get("id") or "").strip() for r in rows}


def decision_cite_error(token, root, decided):
    """The error for a `[DECISION <token>]` tag in a file of root (None: outside the roots), or None when it names a
    decision it may cite. `decided` is {root name or None: ids of its _decisions.csv}."""
    if not kbcommon.DECISION_ID.fullmatch(token):
        if root is None and not token.startswith("D-"):
            return None  # prose outside the roots that explains the tag, with a placeholder for the id
        return f"has a DECISION tag naming {token!r}, not a decision id (D-<8 base32>)" if token else \
            "has a DECISION tag with no decision id (D-<8 base32>)"
    if root is None:
        if any(token in ids for ids in decided.values()):
            return None
    elif token in decided[root.name]:
        return None
    else:
        for name, ids in decided.items():
            if name != root.name and name is not None and token in ids:
                return (f"cites decision {token} of root {name}; a root cites only its own decisions: record it in "
                        f"{root.name}/{kbcommon.DECISIONS}")
    return f"cites unknown decision {token}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", help="check only this root (default: every root and the files outside them)")
    a = ap.parse_args()
    try:
        roots = kbcommon.roots()
    except kbcommon.RootError as e:
        print("sources=0 citations=0 errors=1")
        print("ERROR", e)
        return 1
    if a.root and a.root not in {r.name for r in roots}:
        print(f"ERROR no root {a.root!r}")
        return 2
    owner = {r.id_prefix: r for r in roots}
    known = {r.name: check_root_ledgers(r, owner) if not a.root or r.name == a.root else set() for r in roots}
    if a.root:  # a citation of another root must still be recognised as such
        for r in roots:
            if r.name != a.root:
                try:
                    known[r.name] = {x["id"] for x in kbcommon.load_csv(os.path.join(r.path, kbcommon.SOURCES), ("id",))[1]}
                except kbcommon.CsvError:
                    pass
    known["*"] = set().union(*known.values())
    decided = {r.name: decision_ids(r.path) for r in roots}  # DECISION tags resolve here; None is kb/_self's file
    decided[None] = decision_ids(kbcommon.SELF)
    scans = [(r, r.path) for r in roots if not a.root or r.name == a.root]
    if not a.root:
        scans.append((None, kbcommon.HOME))  # this repository outside the roots: kb/_self, _tools/ data, README.md
    root_dirs = {os.path.abspath(r.path) for r in roots}
    cited = 0

    def name_of(root, p):
        return kbcommon.qualify(root, os.path.relpath(p, root.path)) if root else os.path.relpath(p, kbcommon.HOME).replace(os.sep, "/")

    for root, base in scans:
        check_decisions(root, owner, known)  # a root's own files, or kb/_self's (root None: the repository outside the roots)
        skip = root_dirs - {os.path.abspath(base)}
        for p in walk(base, (".csv",), skip):
            rel = name_of(root, p)
            try:
                with open(p, encoding="utf-8-sig", newline="") as f:
                    rows = list(csv.reader(f))
            except (OSError, UnicodeDecodeError, csv.Error) as e:
                errors.append(f"{rel} is unreadable: {e}")
                continue
            bad = [n for n, r in enumerate(rows, start=1) if r and len(r) != len(rows[0])]
            if bad:
                errors.append(f"{rel} has {len(bad)} row(s) whose column count differs from the header "
                              f"(unquoted comma?), first at line {bad[0]}")
            # a data file's source columns (source, sources, source_id, evidence_source_ids) must name known ids;
            # the root ledgers are checked above
            if rows and not os.path.basename(p).startswith("_"):
                cols = [i for i, h in enumerate(rows[0]) if h.strip().lower().endswith(("source", "sources", "source_id", "source_ids"))]
                for n, r in enumerate(rows[1:], start=2):
                    for i in cols:
                        for sid in kbid.ANY_ID.findall(r[i] if i < len(r) else ""):
                            cited += 1
                            e = cite_error(sid, root, owner, known)
                            if e:
                                errors.append(f"{rel}:{n} {e}")
        topics = set()
        for p in walk(base, (".md",), skip):
            rel = name_of(root, p)
            try:
                with open(p, encoding="utf-8") as f:
                    text = f.read()
            except (OSError, UnicodeDecodeError) as e:
                errors.append(f"{rel} is unreadable: {e}")
                continue
            for tag in TAG.findall(text):
                for sid in kbid.ANY_ID.findall(tag):
                    cited += 1
                    e = cite_error(sid, root, owner, known)
                    if e:
                        errors.append(f"{rel} {e}")
            for tag in DECISION_TAG.findall(text):
                for token in DECISION_PART.findall(tag):
                    e = decision_cite_error(token, root, decided)
                    if e:
                        errors.append(f"{rel} {e}")
            if text.startswith("---\n") and "\ntopic:" in text.split("\n---", 2)[0]:
                head = text.split("\n---", 2)[0]
                for key in ("topic", "priority", "retrieved_utc", "sources", "status"):
                    if f"\n{key}:" not in head:
                        errors.append(f"{rel} front matter lacks {key}")
                m = re.search(r"\nstatus:\s*(\S+)", head)
                if m and m.group(1) not in ("complete", "partial", "unknown"):
                    errors.append(f"{rel} has status {m.group(1)}")
                t = re.search(r"\ntopic:\s*(\S+)", head)
                if root:
                    topics.add(t.group(1) if t else os.path.relpath(p, root.path)[:-3].replace(os.sep, "/"))
        if root is None:
            continue
        for name in (kbcommon.GAPS, kbcommon.CONFLICTS):
            try:
                with open(os.path.join(root.path, name), encoding="utf-8") as f:
                    lines = f.read().splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            for n, ln in enumerate(lines, start=1):
                for m in TOPIC_MARK.finditer(ln):
                    t = m.group(1).removesuffix(".md").removesuffix(".csv")
                    if t not in topics:
                        errors.append(f"{kbcommon.qualify(root, name)}:{n} names unknown topic {t!r} of root "
                                      f"{root.name} (topic: <domain>/<slug>)")
    n_sources = sum(len(v) for k, v in known.items() if k != "*" and (not a.root or k == a.root))
    print(f"sources={n_sources} citations={cited} errors={len(errors)}")
    for e in errors:
        print("ERROR", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
