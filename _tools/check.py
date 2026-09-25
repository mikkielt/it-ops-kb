#!/usr/bin/env python3
"""Check kb consistency (stdlib only). Exit 1 on any error.

- source ids in _sources.csv are unique;
- every _artifacts.csv row names a known source and an existing file;
- every [DOC|DER|COMMUNITY S...] tag in a Markdown file cites a known source id;
- every topic file's front matter has topic, priority, retrieved_utc, sources and status in {complete, partial, unknown}.
"""
import csv, glob, os, re, sys

KB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
errors = []
with open(os.path.join(KB, "_sources.csv"), encoding="utf-8") as f:
    ids = [r["id"] for r in csv.DictReader(f)]
known = set(ids)
errors += [f"duplicate source id {i}" for i in sorted({i for i in ids if ids.count(i) > 1})]
with open(os.path.join(KB, "_artifacts.csv"), encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r["source_id"] not in known:
            errors.append(f"artifact {r['path']} names unknown source {r['source_id']}")
        if not os.path.exists(os.path.join(KB, r["path"])):
            errors.append(f"artifact {r['path']} is missing")
cited = 0
for p in glob.glob(os.path.join(KB, "**", "*.md"), recursive=True):
    rel, text = os.path.relpath(p, KB), open(p, encoding="utf-8").read()
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
