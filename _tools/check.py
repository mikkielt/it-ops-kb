#!/usr/bin/env python3
"""Check kb consistency (stdlib only). Exit 1 on any error.

- _sources.csv and _artifacts.csv exist and have their required columns;
- every .csv has the same number of columns in every row;
- source ids in _sources.csv are unique and well-formed: legacy S<digits>, or S-<8 base32> equal to the hash of
  the row's url, with no two different urls sharing a hash id (see kbid.py);
- a non-empty superseded_by names another known source id and forms no cycle;
- every _artifacts.csv row names a known source and an existing file;
- every Markdown file is readable UTF-8;
- every [DOC|CODE|DER|COMMUNITY S...] tag in a Markdown file cites a known source id (S123 or S-k3f7q2zd);
- no answer id (`## <ID>. ` heading) appears twice in _answers.md; QK answers use QK-<slug>;
- every topic file's front matter has topic, priority, retrieved_utc, sources and status in {complete, partial, unknown};
- every `topic: <domain>/<slug>` marker in _gaps.md and _conflicts.md names an existing topic (kbfacts.py).
"""
import csv, glob, os, re, sys
from collections import Counter
import kbcommon, kbid, kbfacts

KB = kbcommon.KB  # KB_ROOT, else this repository's public root
# the public root is checked with the rest of this repository (SELF, _tools/ data, README.md): the same files
# wherever the layout puts the root; a kb given by KB_ROOT is checked on its own
SCAN = kbcommon.HOME if KB == kbcommon.PUBLIC else KB
errors = []


def rel_of(p):
    """A scanned file's path for messages: relative to the kb root, else to this repository."""
    return kbcommon.kb_rel(p) or os.path.relpath(p, SCAN).replace(os.sep, "/")


def read_csv(name, required):
    """Rows of a kb index CSV, or [] with an error if it is missing or lacks a required column."""
    try:
        return kbcommon.load_csv(name, required)[1]
    except kbcommon.CsvError as e:
        errors.append(str(e))
        return []


sources = read_csv("_sources.csv", ("id", "url", "superseded_by"))
ids = [r["id"] for r in sources]
known = set(ids)
errors += [f"duplicate source id {i}" for i, n in sorted(Counter(ids).items()) if n > 1]
errors += [f"malformed source id {i!r} (want S<digits> or S-<8 base32>)" for i in ids if not kbid.is_source_id(i)]
errors += kbid.check_sources(sources)
succ = {r["id"]: r["superseded_by"].strip() for r in sources if (r.get("superseded_by") or "").strip()}
for sid, nxt in sorted(succ.items()):
    if nxt not in known:
        errors.append(f"source {sid} superseded_by unknown source {nxt}")
        continue
    seen, cur = {sid}, nxt
    while cur in succ and cur not in seen:
        seen.add(cur)
        cur = succ[cur]
    if cur in seen:
        errors.append(f"source {sid} superseded_by chain forms a cycle through {cur}")
try:
    with open(os.path.join(KB, "_answers.md"), encoding="utf-8") as f:
        aids = kbid.answer_ids(f.read())
except FileNotFoundError:
    aids = []
except (OSError, UnicodeDecodeError) as e:
    errors.append(f"_answers.md is unreadable: {e}")
    aids = []
errors += [f"duplicate answer id {i} in _answers.md" for i, n in sorted(Counter(aids).items()) if n > 1]
errors += [f"answer id {i} in _answers.md: QK ids are QK-<slug> (lowercase, hyphenated)"
           for i in aids if i.startswith("QK") and not kbid.QK_ID.fullmatch(i)]
for r in read_csv("_artifacts.csv", ("path", "source_id", "sha256")):
    if r["source_id"] not in known:
        errors.append(f"artifact {r['path']} names unknown source {r['source_id']}")
    if not os.path.isfile(os.path.join(KB, r["path"])):
        errors.append(f"artifact {r['path']} is missing")
cited = 0
for p in glob.glob(os.path.join(SCAN, "**", "*.csv"), recursive=True):
    rel = rel_of(p)
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
    if rows and not os.path.basename(rel).startswith("_"):
        cols = [i for i, h in enumerate(rows[0]) if h.strip().lower().endswith(("source", "sources", "source_id", "source_ids"))]
        for n, r in enumerate(rows[1:], start=2):
            for i in cols:
                for sid in kbid.ANY_ID.findall(r[i] if i < len(r) else ""):
                    cited += 1
                    if sid not in known:
                        errors.append(f"{rel}:{n} cites unknown source {sid}")
for p in glob.glob(os.path.join(SCAN, "**", "*.md"), recursive=True):
    rel = rel_of(p)
    try:
        with open(p, encoding="utf-8") as f:
            text = f.read()
    except (OSError, UnicodeDecodeError) as e:
        errors.append(f"{rel} is unreadable: {e}")
        continue
    for tag in re.findall(r"\[(?:DOC|CODE|DER|COMMUNITY)\s([^\]]+)\]", text):  # \s: a tag may wrap after DOC
        for sid in kbid.ANY_ID.findall(tag):
            cited += 1
            if sid not in known:
                errors.append(f"{rel} cites unknown source {sid}")
    if text.startswith("---\n") and "\ntopic:" in text.split("\n---", 2)[0]:
        head = text.split("\n---", 2)[0]
        for key in ("topic", "priority", "retrieved_utc", "sources", "status"):
            if f"\n{key}:" not in head:
                errors.append(f"{rel} front matter lacks {key}")
        m = re.search(r"\nstatus:\s*(\S+)", head)
        if m and m.group(1) not in ("complete", "partial", "unknown"):
            errors.append(f"{rel} has status {m.group(1)}")
topics = set(kbfacts.topic_files())
for name in ("_gaps.md", "_conflicts.md"):
    for e in kbfacts.ledger_entries(name):
        for m in kbfacts.TOPIC_MARK.finditer(e["text"]):
            t = m.group(1).removesuffix(".md").removesuffix(".csv")
            if t not in topics:
                errors.append(f"{name}:{e['line']} names unknown topic {t!r} (topic: <domain>/<slug>)")
print(f"sources={len(known)} citations={cited} errors={len(errors)}")
for e in errors:
    print("ERROR", e)
sys.exit(1 if errors else 0)
