#!/usr/bin/env python3
"""Retrieve from the kb for RAG (stdlib only).

  rag.py topics [DOMAIN]                   domains -> articles, subdirectories, data files
  rag.py search QUERY [-k 8] [-d DOMAIN] [-u]   BM25 over heading-aware chunks of .md and .csv;
                                           -u adds each hit's source origin urls
  rag.py src S1824 [S1825 ...]             source id -> title, url, version
  rag.py show PATH[:LINE] [-n 40]          print lines of a kb file

Add --json to any command for machine output. artifacts/ directories are not indexed. search skips the
root-level index files (README.md, _answers.md, _gaps.md, _conflicts.md, _coverage.csv, ...) unless --index.
"""
import argparse, csv, io, json, math, os, re, sys
from collections import Counter, defaultdict

KB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {"_tools", "_private", "_cache", "artifacts"}
TOKEN = re.compile(r"\w+(?:[.\-]\w+)*")  # Unicode words; `gmsa-dmsa`, `dsc.exe` stay whole
MAX_CHUNK = 900
csv.field_size_limit(2**31 - 1)  # a very wide cell must not abort the whole search


def read_text(rel):
    """Return a kb file's text, or None (with a warning on stderr) if it cannot be read."""
    try:
        with open(os.path.join(KB, rel), encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError as e:
        print(f"warning: skipped {rel}: {e.strerror}", file=sys.stderr)
        return None


def positive_int(v):
    n = int(v)
    if n < 1:
        raise argparse.ArgumentTypeError(f"must be >= 1, got {n}")
    return n


def kb_files(exts):
    for root, dirs, files in os.walk(KB):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        for f in sorted(files):
            if f.endswith(exts) and f != "_sources.csv":
                yield os.path.relpath(os.path.join(root, f), KB)


def front_matter(lines):
    meta = {}
    if lines and lines[0].strip() == "---":
        for ln in lines[1:]:
            if ln.strip() == "---":
                break
            k, _, v = ln.partition(":")
            meta[k.strip()] = v.strip().strip('"')
    meta["title"] = next((ln[2:].strip() for ln in lines if ln.startswith("# ")), meta.get("topic", ""))
    return meta


def chunks():
    """Yield (path, line, heading, text): markdown split at headings, then at blank lines/bullets up to MAX_CHUNK."""
    for rel in kb_files((".md", ".csv")):
        raw = read_text(rel)
        if raw is None:
            continue
        if rel.endswith(".csv"):
            try:
                for i, row in enumerate(csv.DictReader(io.StringIO(raw.lstrip("\ufeff").replace("\0", ""), newline="")), start=2):
                    text = "; ".join(f"{k}={v}" for k, v in row.items() if v and k)
                    yield rel, i, os.path.basename(rel), text[:MAX_CHUNK * 2]
            except csv.Error as e:
                print(f"warning: skipped rest of {rel}: {e}", file=sys.stderr)
            continue
        lines = raw.splitlines()
        heading, buf, start, fenced = front_matter(lines)["title"], [], 1, False
        body = lines.index("---", 1) + 1 if lines[:1] == ["---"] and "---" in lines[1:] else 0
        for n, ln in enumerate(lines, start=1):
            if n <= body:
                start = n + 1
                continue
            if len(ln) > MAX_CHUNK * 2:  # one huge line: flush, then index it in MAX_CHUNK slices
                if "".join(buf).strip():
                    yield rel, start, heading, "\n".join(buf).strip()
                buf, start = [], n + 1
                for i in range(0, len(ln), MAX_CHUNK):
                    yield rel, n, heading, ln[i:i + MAX_CHUNK]
                continue
            if ln.lstrip().startswith(("```", "~~~")):
                fenced = not fenced
            is_head = ln.startswith("#") and not fenced
            if buf and (is_head or (len("\n".join(buf)) > MAX_CHUNK and (not ln.strip() or ln.lstrip().startswith(("- ", "| "))))):
                yield rel, start, heading, "\n".join(buf).strip()
                buf, start = [], n
            if is_head:
                heading = ln.lstrip("#").strip()
                start = n + 1
            elif ln.strip() or buf:
                buf.append(ln)
        if "".join(buf).strip():
            yield rel, start, heading, "\n".join(buf).strip()


def tokens(text):
    """Lowercase word tokens; a hyphen/dot compound also yields its parts (`what-if` -> what-if, what, if)."""
    out = []
    for t in TOKEN.findall(text.lower()):
        out.append(t)
        if "-" in t or "." in t:
            out += [p for p in re.split(r"[.\-]", t) if p]
    return out


def search(query, k, domain, index=False):
    """BM25 top-k chunks. Root-level files (the kb's own index and logs) are left out unless `index`."""
    docs = [c for c in chunks() if (index or os.sep in c[0]) and (not domain or c[0].startswith(domain.rstrip("/") + "/"))]
    toks = [Counter(tokens(f"{c[0]} {c[2]} {c[3]}")) for c in docs]
    q = set(tokens(query))
    df = Counter(t for tf in toks for t in q & tf.keys())
    avg = sum(sum(tf.values()) for tf in toks) / max(len(toks), 1)
    scored = []
    for c, tf in zip(docs, toks):
        dl, s = sum(tf.values()), 0.0
        for t in q & tf.keys():
            idf = math.log(1 + (len(docs) - df[t] + 0.5) / (df[t] + 0.5))
            s += idf * tf[t] * 2.2 / (tf[t] + 1.2 * (0.25 + 0.75 * dl / avg))
        if s:
            scored.append((round(s, 2), c))
    scored.sort(key=lambda x: -x[0])
    return [{"score": s, "path": p, "line": ln, "heading": h, "text": t,
             "sources": sorted(set(re.findall(r"\bS\d{3,4}\b", t)), key=lambda x: int(x[1:]))}
            for s, (p, ln, h, t) in scored[:k]]


def topics(domain):
    out = defaultdict(lambda: {"articles": [], "dirs": Counter(), "data": []})
    for root, dirs, files in os.walk(KB):
        dirs[:] = sorted(d for d in dirs if d not in {"_tools", "_private", "_cache"} and not d.startswith("."))
        for f in sorted(files):
            rel = os.path.relpath(os.path.join(root, f), KB)
            parts = rel.split(os.sep)
            dom = parts[0] if len(parts) > 1 else "(index)"
            if domain and dom != domain:
                continue
            if len(parts) > 2:  # nested directory: summarise by its first level
                out[dom]["dirs"]["/".join(parts[:2]) + "/"] += 1
            elif f.endswith(".md"):
                text = read_text(rel)
                if text is None:
                    continue
                m = front_matter(text.splitlines())
                out[dom]["articles"].append({"path": rel, "topic": m.get("topic", ""), "title": m["title"],
                                             "priority": m.get("priority", ""), "status": m.get("status", "")})
            else:
                out[dom]["data"].append(rel)
    return {d: {**v, "dirs": dict(v["dirs"])} for d, v in sorted(out.items())}


def source_rows():
    try:
        with open(os.path.join(KB, "_sources.csv"), encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
    except OSError as e:
        sys.exit(f"cannot read _sources.csv: {e.strerror}")
    if rows and not {"id", "url"} <= rows[0].keys():
        sys.exit("_sources.csv lacks an 'id' or 'url' column")
    return {r["id"]: r for r in rows}


def sources(ids):
    rows = source_rows()
    return [rows.get(i.upper(), {"id": i, "title": "UNKNOWN id"}) for i in ids]


def add_urls(hits):
    """Give each hit a `urls` map: cited source id -> origin url (None if the id is unknown)."""
    rows = source_rows()
    for x in hits:
        x["urls"] = {i: rows.get(i, {}).get("url") for i in x["sources"]}
    return hits


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("topics"); t.add_argument("domain", nargs="?")
    s = sub.add_parser("search"); s.add_argument("query", nargs="+"); s.add_argument("-k", type=positive_int, default=8); s.add_argument("-d", "--domain")
    s.add_argument("-u", "--urls", action="store_true", help="resolve each hit's cited source ids to their origin url")
    s.add_argument("--index", action="store_true", help="also search the root-level index files (README.md, _answers.md, ...)")
    r = sub.add_parser("src"); r.add_argument("ids", nargs="+")
    w = sub.add_parser("show"); w.add_argument("target"); w.add_argument("-n", type=positive_int, default=40)
    a = ap.parse_args()

    if a.cmd == "topics":
        res = topics(a.domain)
        if not res:
            sys.exit(f"no domain {a.domain!r}")
        if a.json:
            return print(json.dumps(res, indent=1))
        for dom, v in res.items():
            print(f"\n## {dom}  ({len(v['articles'])} articles)")
            for x in v["articles"]:
                tag = " ".join(filter(None, (x["priority"], x["status"])))
                print(f"  {x['path']:<52} {x['title'][:70]}" + (f"  [{tag}]" if tag else ""))
            for d, n in v["dirs"].items():
                print(f"  {d:<52} ({n} files)")
            if v["data"]:
                print("  data: " + ", ".join(os.path.basename(p) for p in v["data"]))
    elif a.cmd == "search":
        res = search(" ".join(a.query), a.k, a.domain, a.index)
        if a.urls:
            add_urls(res)
        if a.json:
            return print(json.dumps(res, indent=1))
        for x in res:
            print(f"\n[{x['score']}] {x['path']}:{x['line']}  § {x['heading']}")
            print("  " + x["text"][:600].replace("\n", "\n  "))
            for i, u in x.get("urls", {}).items():
                print(f"  -> {i}  {u or 'UNKNOWN id'}")
        if not res:
            sys.exit("no match")
    elif a.cmd == "src":
        res = sources(a.ids)
        if a.json:
            return print(json.dumps(res, indent=1))
        for x in res:
            print(f"{x['id']}  {x['title']}" + (f"\n  {x['url']}  ({x['publisher']}; {x['version_or_date']})" if "url" in x else ""))
    else:
        path, _, line = a.target.partition(":")
        root = os.path.realpath(KB)
        full = os.path.realpath(os.path.join(root, path))
        if os.path.commonpath([full, root]) != root:
            sys.exit(f"{path}: outside the kb")
        if not os.path.isfile(full):
            sys.exit(f"{path}: no such file")
        if line and not line.isdigit():
            sys.exit(f"{line!r}: line must be a positive number")
        text = read_text(os.path.relpath(full, root))
        if text is None:
            sys.exit(1)
        lines = text.splitlines()
        start = max(int(line or 1), 1)
        for n in range(start, min(start + a.n, len(lines) + 1)):
            print(f"{n:>5}  {lines[n - 1]}")


if __name__ == "__main__":
    main()
