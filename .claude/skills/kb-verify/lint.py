#!/usr/bin/env python3
"""Contract checks that _tools/check.py does not make (stdlib only). Reports only; never edits.

  lint.py                    every topic
  lint.py auth dsc/what-if   only topics whose path starts with one of these prefixes
  lint.py --json             machine output

ERROR (exit 1): topic id differs from the path; header/coverage mismatch (status, priority, source count);
coverage lists a missing file; topic missing from _coverage.csv or README; a missing section; a fact tag
without a source id; a Facts bullet with no tag.
WARN: no H1 title; a Facts bullet mixing tag kinds; header source ids never cited in the body, or cited
ids missing from the header.
"""
import csv, glob, json, os, re, sys

KB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
TAG = re.compile(r"\[(DOC|DER|COMMUNITY|UNK)\b[^\]]*\]")
SID = re.compile(r"\bS-[a-z2-7]{8}\b|S\d+")  # hash source ids (S-k3f7q2zd) and legacy ones (S123)


def main():
    args = [a for a in sys.argv[1:] if a != "--json"]
    os.chdir(KB)
    with open("_coverage.csv", encoding="utf-8-sig", newline="") as f:
        cov = {r["topic"]: r for r in csv.DictReader(f)}
    readme = open("README.md", encoding="utf-8").read()
    out = []

    def add(level, path, msg):
        out.append({"level": level, "path": path, "message": msg})

    for p in sorted(glob.glob("**/*.md", recursive=True)):
        if args and not any(p.startswith(a.rstrip("/")) for a in args):
            continue
        text = open(p, encoding="utf-8", errors="replace").read()
        if not text.startswith("---\n") or "\ntopic:" not in text.split("\n---", 2)[0]:
            continue
        head, body = text.split("\n---", 2)[0], text.split("\n---", 2)[-1]
        fm = dict((k.strip(), v.strip()) for k, _, v in (ln.partition(":") for ln in head.splitlines()[1:]))
        topic, want = fm.get("topic", ""), p[:-3]
        if topic != want:
            add("ERROR", p, f"topic is {topic!r}, path says {want!r}")
        row = cov.get(want)
        if not row:
            if "/artifacts/" not in p and not p.startswith("agents/a2a/"):
                add("ERROR", p, "not listed in _coverage.csv")
        else:
            fms = set(SID.findall(fm.get("sources", "")))
            for key, have, csv_v in (("status", fm.get("status"), row["status"]), ("priority", fm.get("priority"), row["priority"]),
                                     ("source count", str(len(fms)), row["n_sources"])):
                if have != csv_v:
                    add("ERROR", p, f"{key}: header {have!r}, _coverage.csv {csv_v!r}")
            for f in filter(None, row["files"].split(";")):
                if not os.path.exists(f):
                    add("ERROR", p, f"_coverage.csv lists missing file {f}")
            if f"| `{want}` |" not in readme:
                add("ERROR", p, "no row in the README coverage table")
        heads = re.findall(r"^## (.+)$", body, re.M)
        for s in ("Summary", "Facts", "Reference", "Examples"):
            if not any(h.startswith(s) for h in heads):
                add("ERROR", p, f"missing section ## {s}")
        if not re.search(r"^# ", body, re.M):
            add("WARN", p, "no '# ' title line")
        for t in re.findall(r"\[(DOC|DER|COMMUNITY)\]", body):
            add("ERROR", p, f"[{t}] tag without a source id")
        m = re.search(r"^## Facts.*?$(.*?)(?=^## |\Z)", body, re.M | re.S)
        if m:
            for item in re.split(r"\n(?=- )", m.group(1)):
                item = item.strip()
                if not item.startswith("- "):
                    continue
                kinds = set(TAG.findall(item))
                if not kinds:
                    add("ERROR", p, f"untagged fact: {item[2:80]!r}")
                elif len(kinds) > 1:
                    add("WARN", p, f"fact mixes tags {sorted(kinds)}: {item[2:60]!r}")
        cited = {s for tag in re.findall(r"\[(?:DOC|DER|COMMUNITY)[^\]]*\]", body) for s in SID.findall(tag)}
        fms = set(SID.findall(fm.get("sources", "")))
        if fms - cited:
            add("WARN", p, f"header sources not cited in the body: {' '.join(sorted(fms - cited))}")
        if cited - fms:
            add("WARN", p, f"cited sources missing from the header: {' '.join(sorted(cited - fms))}")

    if "--json" in sys.argv:
        print(json.dumps(out, indent=1))
    else:
        for x in out:
            print(f"{x['level']:<5} {x['path']}: {x['message']}")
        n = sum(1 for x in out if x["level"] == "ERROR")
        print(f"errors={n} warnings={len(out) - n}")
    sys.exit(1 if any(x["level"] == "ERROR" for x in out) else 0)


if __name__ == "__main__":
    main()
