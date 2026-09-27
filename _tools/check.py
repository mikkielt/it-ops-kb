#!/usr/bin/env python3
"""Check kb consistency (stdlib only). Exit 1 on any error.

  check.py [--root NAME]      every root (kbcommon.roots(): kb/public, kb/<name>/, KB_ROOTS), or one

- every root's _root.md is well-formed, and no two roots share a name or an id prefix;
- per root: _sources.csv and _artifacts.csv exist and have their required columns;
- every .csv has the same number of columns in every row;
- source ids in a root's _sources.csv are unique and well-formed: the root's `<prefix>-<8 base32>` equal to the
  hash of the row's url (public also keeps legacy S<digits>), with no two different urls sharing a hash id (kbid.py);
- a non-empty superseded_by names another source id of the same root and forms no cycle;
- every _artifacts.csv row names a known source of its root and an existing file;
- every Markdown file is readable UTF-8;
- every [DOC|CODE|DER|COMMUNITY <id>] tag and data-file source column cites a source of its own root: an id of
  another root is an error that says so (a root cites only its own sources; add the source to its _sources.csv);
  files outside the roots (kb/_self, _tools/ data, README.md) may cite any root's ids;
- no answer id (`## <ID>. ` heading) appears twice in a root's _answers.md; QK answers use QK-<slug>;
- every topic file's front matter has topic, priority, retrieved_utc, sources and status in {complete, partial, unknown};
- every `topic: <domain>/<slug>` marker in a root's _gaps.md and _conflicts.md names a topic of that root.
Messages name files by their qualified path `<root>/<path>`, or by their path in this repository outside the roots.
"""
import argparse, csv, os, re, sys
from collections import Counter
import kbcommon, kbid

TOPIC_MARK = re.compile(r"\btopic:\s*`?([a-z0-9-]+/[a-z0-9./-]+?)`?(?=[\s,;.)\]]|$)")
TAG = re.compile(r"\[(?:DOC|CODE|DER|COMMUNITY)\s([^\]]+)\]")  # \s: a tag may wrap after DOC
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
    sources = read_csv(root, kbcommon.SOURCES, ("id", "url", "superseded_by"))
    ids = [r["id"] for r in sources]
    known = set(ids)
    errors.extend(f"{q(kbcommon.SOURCES)}: duplicate source id {i}" for i, n in sorted(Counter(ids).items()) if n > 1)
    errors.extend(f"{q(kbcommon.SOURCES)}: {e}" for e in kbid.check_sources(sources, root.id_prefix, root.name))
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
    for r in read_csv(root, kbcommon.ARTIFACTS, ("path", "source_id", "sha256")):
        if r["source_id"] not in known:
            errors.append(f"artifact {q(r['path'])} names unknown source {r['source_id']}")
        if not os.path.isfile(os.path.join(root.path, r["path"])):
            errors.append(f"artifact {q(r['path'])} is missing")
    return known


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
    scans = [(r, r.path) for r in roots if not a.root or r.name == a.root]
    if not a.root:
        scans.append((None, kbcommon.HOME))  # this repository outside the roots: kb/_self, _tools/ data, README.md
    root_dirs = {os.path.abspath(r.path) for r in roots}
    cited = 0

    def name_of(root, p):
        return kbcommon.qualify(root, os.path.relpath(p, root.path)) if root else os.path.relpath(p, kbcommon.HOME).replace(os.sep, "/")

    for root, base in scans:
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
