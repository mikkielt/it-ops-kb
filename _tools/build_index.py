#!/usr/bin/env python3
"""Regenerate the kb's index files from the articles and data (stdlib only). Never edit these by hand.

  build_index.py            rewrite what is out of date: _coverage.csv, the coverage table, used_in in _sources.csv
  build_index.py --check    write nothing; exit 1 and list what differs when a generated file is out of date

Content files are the files under the domain directories: every path with a `/` whose top directory does not
start with `_` or `.` (so not `_tools/`, `_cache/`, `.claude/`), skipping dot-files, `__pycache__` and `*.pyc`.

_coverage.csv (topic,priority,status,files,n_sources), one row per topic:
  - an article is a content `.md` whose front matter has `topic:`. topic, priority and status come from its front
    matter; n_sources is the number of distinct source ids in its `sources:` header.
  - files = the article, then its sibling files sharing its stem (`auth/flows.md` -> `auth/flows.csv`,
    `graph/csdl-device.properties.csv`), sorted, then the extras its optional front-matter key lists, in order:
    `files: [dsc/cli/, graph/csdl/device.v1.0.xml]` (kb-root-relative paths; a directory ends in `/`).
  - an article named in another article's `files:` (e.g. an artifact digest) is part of that topic, not a row.
  - a topic with no article (e.g. a CSV-only table) is a row of kb/public/_retrieval/index_extra.csv (topic,priority,status,files;
    files `;`-separated). Its n_sources is the number of distinct known source ids cited in those files.
  - rows are ordered by domain, then priority, then topic id.
kb/_self/coverage.md: the table between `<!-- coverage:start -->` and `<!-- coverage:end -->` is the same rows; nothing
  else in the file is touched. A kb without that file (a team kb served with KB_ROOT) keeps the table in its README.md.
_sources.csv used_in: the sorted `;`-joined content files whose text cites the id (legacy `\\bS\\d+\\b`, hash
  `\\bS-[a-z2-7]{8}\\b`, anywhere in the file). Root files (_answers.md, ...) never count; a pinned
  artifact that does not cite its source is linked to it by _artifacts.csv, not by used_in. Every other column and the row order are kept.
Output is deterministic: `\\n` line endings, no BOM, stable order. Running it twice changes nothing.
Exit 0 up to date (or written), 1 out of date (--check), 2 cannot build (unreadable ledger, missing table markers).
"""
import argparse, csv, io, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kbcommon, kbid  # noqa: E402

KB = kbcommon.KB  # KB_ROOT, else this repository
EXTRA = kbcommon.data_rel("index_extra.csv")
COVERAGE_FIELDS = ["topic", "priority", "status", "files", "n_sources"]
START, END = "<!-- coverage:start -->", "<!-- coverage:end -->"
# the coverage page in SELF, relative to the public root (a kb given by KB_ROOT keeps its own, coverage_page)
COVERAGE_MD = os.path.relpath(os.path.join(kbcommon.SELF, "coverage.md"), kbcommon.PUBLIC).replace(os.sep, "/")
CITE = kbid.SOURCE_ID


class BuildError(Exception):
    pass


def read(rel):
    return kbcommon.read(rel, newline="")


def read_csv(rel, required, text=None):
    text = read(rel) if text is None else text
    if text is None:
        raise BuildError(f"cannot read {rel}")
    try:
        return kbcommon.parse_csv(rel, text, required, nul=True)
    except kbcommon.CsvError as e:
        raise BuildError(str(e))


def content_files():
    """Sorted kb-relative paths of the files under the domain directories."""
    out = []
    for root, dirs, files in os.walk(KB):
        rel_root = os.path.relpath(root, KB)
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d != "__pycache__"
                         and not (rel_root == "." and d.startswith("_")))
        if rel_root == ".":
            continue
        for f in files:
            if not f.startswith(".") and not f.endswith(".pyc"):
                out.append(os.path.relpath(os.path.join(root, f), KB).replace(os.sep, "/"))
    return sorted(out)


def front_matter(text):
    """Front-matter keys of an article, or None when the file is not one (no `---` block with `topic:`)."""
    if not text.startswith("---\n"):
        return None
    head = text.split("\n---", 1)[0]
    if "\ntopic:" not in head:
        return None
    fm = {}
    for ln in head.splitlines()[1:]:
        k, sep, v = ln.partition(":")
        if sep:
            fm[k.strip()] = v.strip()
    return fm


def inline_list(value):
    """`[a, "b", c]` (or a bare `a, b`) -> ['a', 'b', 'c']."""
    value = (value or "").strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    return [x.strip().strip("'\"") for x in value.split(",") if x.strip().strip("'\"")]


def sort_key(row):
    return (row["topic"].split("/", 1)[0], row["priority"], row["topic"])


def coverage_rows(files, texts, known, warnings):
    """The _coverage.csv rows, in order."""
    articles = {}
    for p in files:
        if p.endswith(".md"):
            fm = front_matter(texts[p])
            if fm is not None:
                articles[p] = fm
    parts = {f for fm in articles.values() for f in inline_list(fm.get("files"))}
    by_dir = {}  # dir -> [(path, file name)] in path order: a topic's same-stem files are found in its own directory
    for f in files:
        d, _, name = f.rpartition("/")
        by_dir.setdefault(d, []).append((f, name))
    rows = []
    for p, fm in articles.items():
        if p in parts:
            continue
        topic = fm.get("topic") or p[:-3]
        if topic != p[:-3]:
            warnings.append(f"{p}: front matter topic {topic!r} differs from the path")
        d, _, name = p.rpartition("/")
        listed = [p] + [f for f, n in by_dir.get(d, ()) if n.startswith(name[:-3] + ".") and f != p]
        for f in inline_list(fm.get("files")):
            if not os.path.exists(os.path.join(KB, f)):
                warnings.append(f"{p}: files: lists missing {f}")
            if f not in listed:
                listed.append(f)
        rows.append({"topic": topic, "priority": fm.get("priority", ""), "status": fm.get("status", ""),
                     "files": ";".join(listed), "n_sources": str(len(set(CITE.findall(fm.get("sources", "")))))})
    have = {r["topic"] for r in rows}
    if os.path.exists(os.path.join(KB, EXTRA)):
        for r in read_csv(EXTRA, ("topic", "priority", "status", "files"))[1]:
            if r["topic"] in have:
                warnings.append(f"{EXTRA}: {r['topic']} has an article; its row there is ignored")
                continue
            listed = [f.strip() for f in r["files"].split(";") if f.strip()]
            ids = set()
            for f in listed:
                if not os.path.exists(os.path.join(KB, f)):
                    warnings.append(f"{EXTRA}: {r['topic']} lists missing {f}")
                for g in files:
                    if g == f or (f.endswith("/") and g.startswith(f)):
                        ids.update(s for s in CITE.findall(texts[g]) if s in known)
            rows.append({"topic": r["topic"], "priority": r["priority"], "status": r["status"],
                         "files": ";".join(listed), "n_sources": str(len(ids))})
            have.add(r["topic"])
    return sorted(rows, key=sort_key)


csv_text = kbcommon.csv_text


def coverage_page(override=None):
    """The file that holds the coverage table: coverage.md in SELF, or README.md in a kb without it (KB_ROOT)."""
    page = COVERAGE_MD if KB == kbcommon.PUBLIC else "_self/coverage.md"
    if page in (override or {}) or os.path.exists(os.path.join(KB, page)):
        return page
    return "README.md"


def readme_table(rows):
    lines = [START, "| Topic | Priority | Status | Files | Sources |", "|---|---|---|---|---|"]
    for r in rows:
        files = ", ".join(f"`{f}`" for f in r["files"].split(";") if f)
        lines.append(f"| `{r['topic']}` | {r['priority']} | {r['status']} | {files} | {r['n_sources']} |")
    return "\n".join(lines + [END])


def build(override=None, texts_out=None):
    """{path: (old text or None, new text)} for every generated file, and a list of warnings.
    `override` {path: text} replaces files on disk as input (kbgit.py fix builds from ledgers it has not written yet);
    `texts_out`, a dict, receives the text of every content file read (kbgit.py fix checks them for conflict markers)."""
    override = override or {}
    get = lambda rel: override[rel] if rel in override else read(rel)  # noqa: E731
    warnings = []
    fields, sources = read_csv("_sources.csv", ("id", "used_in"), get("_sources.csv"))
    known = {r["id"] for r in sources}
    files = content_files()
    texts = {f: get(f) or "" for f in files}
    if texts_out is not None:
        texts_out.update(texts)
    rows = coverage_rows(files, texts, known, warnings)
    out = {"_coverage.csv": csv_text(COVERAGE_FIELDS, rows)}

    page = coverage_page(override)
    doc = get(page)
    if doc is None:
        raise BuildError(f"cannot read {page}")
    i, j = doc.find(START), doc.find(END)
    if i < 0 or j < i:
        raise BuildError(f"{page} lacks the {START} ... {END} markers around the coverage table")
    out[page] = doc[:i] + readme_table(rows) + doc[j + len(END):]

    used = {}
    for f in files:
        for sid in set(CITE.findall(texts[f])) & known:
            used.setdefault(sid, set()).add(f)
    for r in sources:
        r["used_in"] = ";".join(sorted(used.get(r["id"], ())))
    out["_sources.csv"] = csv_text(fields, sources)
    return {p: (read(p), new) for p, new in out.items()}, rows, warnings


def describe(path, old, new):
    """Human-readable differences between the file on disk and the generated one."""
    if old is None:
        return [f"{path}: missing"]
    if path == "_coverage.csv":
        try:
            have = {r["topic"]: r for r in csv.DictReader(io.StringIO(old.lstrip("﻿")))}
        except csv.Error:
            have = {}
        want = {r["topic"]: r for r in csv.DictReader(io.StringIO(new))}
        out = [f"_coverage.csv: {t} is not a topic (no article, no {EXTRA} row)" for t in sorted(set(have) - set(want))]
        out += [f"_coverage.csv: {t} row missing" for t in sorted(set(want) - set(have))]
        for t in sorted(set(want) & set(have)):
            diff = [f"{k} {have[t].get(k)!r} -> {want[t][k]!r}" for k in COVERAGE_FIELDS if have[t].get(k) != want[t][k]]
            if diff:
                out.append(f"_coverage.csv: {t}: " + ", ".join(diff))
        if not out:
            out.append("_coverage.csv: row order or formatting differs (domain, priority, topic)")
        return out
    if path == "_sources.csv":
        try:
            have = {r.get("id"): r for r in csv.DictReader(io.StringIO(old.lstrip("﻿")))}
        except csv.Error:
            have = {}
        out = []
        for r in csv.DictReader(io.StringIO(new)):
            if (have.get(r["id"]) or {}).get("used_in") != r["used_in"]:
                out.append(f"_sources.csv: {r['id']} used_in {(have.get(r['id']) or {}).get('used_in')!r} -> {r['used_in']!r}")
        return out or ["_sources.csv: formatting differs (quoting, line endings or BOM)"]
    return [f"{path}: coverage table differs from _coverage.csv rows"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="write nothing; exit 1 when a generated file is out of date")
    a = ap.parse_args()
    try:
        result, rows, warnings = build()
    except BuildError as e:
        sys.exit(print(f"ERROR {e}", file=sys.stderr) or 2)
    for w in warnings:
        print("WARN", w)
    stale = [p for p, (old, new) in result.items() if old != new]
    if a.check:
        for p in stale:
            lines = describe(p, *result[p])
            for ln in lines[:30]:
                print("DIFF", ln)
            if len(lines) > 30:
                print(f"DIFF {p}: ... +{len(lines) - 30} more")
        print(f"topics={len(rows)} out_of_date={len(stale)}" + (" (run python3 _tools/build_index.py)" if stale else ""))
        sys.exit(1 if stale else 0)
    for p in stale:
        with open(os.path.join(KB, p), "w", encoding="utf-8", newline="") as f:
            f.write(result[p][1])
        print(f"wrote {p}")
    print(f"topics={len(rows)} written={len(stale)}")


if __name__ == "__main__":
    main()
