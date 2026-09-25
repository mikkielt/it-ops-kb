#!/usr/bin/env python3
"""Check kb consistency (stdlib only). Exit 1 on any error.

- _sources.csv and _artifacts.csv exist and have their required columns;
- every .csv has the same number of columns in every row;
- source ids in _sources.csv are unique;
- every _artifacts.csv row names a known source and an existing file;
- every Markdown file is readable UTF-8;
- every [DOC|DER|COMMUNITY S...] tag in a Markdown file cites a known source id;
- every topic file's front matter has topic, priority, retrieved_utc, sources and status in {complete, partial, unknown}.
"""
import csv, glob, os, re, sys

KB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
errors = []


def read_csv(name, required):
    """Rows of a kb index CSV, or [] with an error if it is missing or lacks a required column."""
    try:
        with open(os.path.join(KB, name), encoding="utf-8-sig", newline="") as f:
            r = csv.DictReader(f)
            rows = list(r)
            missing = [c for c in required if c not in (r.fieldnames or [])]
    except (OSError, UnicodeDecodeError, csv.Error) as e:
        errors.append(f"cannot read {name}: {e}")
        return []
    if missing:
        errors.append(f"{name} lacks column(s) {', '.join(missing)}")
        return []
    return rows


ids = [r["id"] for r in read_csv("_sources.csv", ("id", "url"))]
known = set(ids)
errors += [f"duplicate source id {i}" for i in sorted({i for i in ids if ids.count(i) > 1})]
for r in read_csv("_artifacts.csv", ("path", "source_id", "sha256")):
    if r["source_id"] not in known:
        errors.append(f"artifact {r['path']} names unknown source {r['source_id']}")
    if not os.path.isfile(os.path.join(KB, r["path"])):
        errors.append(f"artifact {r['path']} is missing")
for p in glob.glob(os.path.join(KB, "**", "*.csv"), recursive=True):
    rel = os.path.relpath(p, KB)
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
cited = 0
for p in glob.glob(os.path.join(KB, "**", "*.md"), recursive=True):
    rel = os.path.relpath(p, KB)
    try:
        with open(p, encoding="utf-8") as f:
            text = f.read()
    except (OSError, UnicodeDecodeError) as e:
        errors.append(f"{rel} is unreadable: {e}")
        continue
    for tag in re.findall(r"\[(?:DOC|DER|COMMUNITY) ([^\]]+)\]", text):
        for sid in re.findall(r"S\d+", tag):
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
print(f"sources={len(known)} citations={cited} errors={len(errors)}")
for e in errors:
    print("ERROR", e)
sys.exit(1 if errors else 0)
