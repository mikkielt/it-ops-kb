#!/usr/bin/env python3
"""Retrieve from the kb for RAG (stdlib only).

  rag.py topics [DOMAIN]                   domains -> articles, subdirectories, data files
  rag.py search QUERY [-k 8] [-d DOMAIN] [-u]   BM25 over heading-aware chunks of .md and .csv;
                                           -u adds each hit's source origin urls
  rag.py src S1824 [S-k3f7q2zd ...]        source id -> title, url, version (and "superseded by" when set)
  rag.py show PATH[:LINE] [-n 40]          print lines of a kb file
  rag.py pack QUESTION [--budget 1200] [-d DOMAIN] [--format concise]
                                           the evidence pack for a question: a `coverage: good|weak|none` verdict,
                                           the best fact lines grouped by article (path:line, tag) and one footer of
                                           the cited sources' urls, within about BUDGET tokens. Start every lookup here.
  rag.py pack -q PART -q PART ...          one batch for a question with several parts (1-6): a section with its
                                           own verdict per part and one shared source footer
  rag.py facts PREFIX [--tag UNK,COMMUNITY] [--format detailed]
                                           fact lines under a path prefix (a domain, topic or file), by tag kind
  rag.py audit [PREFIX] [--status partial] [--entries] [--unlinked] [--format detailed]
                                           per article: status, retrieved_utc, fact counts by tag kind and the
                                           _gaps.md/_conflicts.md entries linked to it (named, or via its sources);
                                           --unlinked lists the entries no topic marker, path or section links
  rag.py src S1824 --cited                 also every file line that names the id
  rag.py eval [--file _tools/lookup_eval.csv]   pack against the lookup eval set: expected article found, verdict
  rag.py topics-for PATH... | --keywords TEXT   kb topics that code touches, from the curated code signals in
                                           _tools/signals.csv (e.g. PublicClientApplication -> auth/msal-public-client)

--format concise|detailed: pack defaults to detailed (answers need the urls); facts, audit and search to concise
(facts grouped by file with a short tag and text, no url footer). Words that are product aliases
(_tools/aliases.csv: sccm, memcm, configmgr, ...) also match the product's other names. pack also searches untagged
Summary, Reference and Examples lines and untagged data rows, printed with `(no tag)`; they never make it `good`.

Add --json (before the command) for machine output. artifacts/ directories are not indexed. search skips the
root-level index files (README.md, _answers.md, _gaps.md, _conflicts.md, _coverage.csv, ...) unless --index.
"""
import argparse, csv, io, json, math, os, re, sys
from collections import Counter, defaultdict
import kbcommon, kbid, kbfacts

KB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {"_tools", "_private", "_cache", "_census", "artifacts"}  # _census: dated verdict logs, not facts
TOKEN = re.compile(r"\w+(?:[.\-]\w+)*")  # Unicode words; `gmsa-dmsa`, `dsc.exe` stay whole
MAX_CHUNK = 900
CITED = kbid.SOURCE_ID  # legacy ids (not prose like S1/S3 sleep states) and hash ids
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


def search(query, k, domain, index=False, notes=None):
    """BM25 top-k chunks. Root-level files (the kb's own index and logs) are left out unless `index`.
    `notes`, if a list, receives warnings about a weak match: query words found nowhere in the searched files,
    or a top hit matching under half of the query's informative words (those in fewer than 25% of chunks)."""
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
            scored.append((round(s, 2), c, sorted(q & tf.keys())))
    scored.sort(key=lambda x: -x[0])
    if notes is not None:
        words = {t for t in q if len(t) > 2}
        missing = sorted(t for t in words if not df[t])
        if missing:
            notes.append(f"not found anywhere in the searched files: {', '.join(missing)}")
        informative = {t for t in words if df[t] < 0.25 * len(docs)}
        if scored and informative and len(informative & set(scored[0][2])) * 2 < len(informative):
            notes.append(f"weak match: the top hit contains {len(informative & set(scored[0][2]))} of "
                         f"{len(informative)} informative query words ({', '.join(sorted(informative))})")
    return [{"score": s, "path": p, "line": ln, "heading": h, "text": t, "matched": m,
             "sources": sorted(set(CITED.findall(t)), key=kbid.sort_key)}
            for s, (p, ln, h, t), m in scored[:k]]


def topics(domain):
    out = defaultdict(lambda: {"articles": [], "dirs": Counter(), "data": []})
    for root, dirs, files in os.walk(KB):
        dirs[:] = sorted(d for d in dirs if d not in {"_tools", "_private", "_cache", "_census"} and not d.startswith("."))
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
        rows = kbcommon.read_sources()
    except OSError as e:
        sys.exit(f"cannot read _sources.csv: {e.strerror}")
    if rows and not {"id", "url"} <= rows[0].keys():
        sys.exit("_sources.csv lacks an 'id' or 'url' column")
    return {r["id"]: r for r in rows}


def sources(ids):
    rows = source_rows()
    return [rows.get(kbid.canonical_id(i), {"id": i, "title": "UNKNOWN id"}) for i in ids]


def add_urls(hits):
    """Give each hit a `urls` map: cited source id -> origin url (None if the id is unknown)."""
    rows = source_rows()
    for x in hits:
        x["urls"] = {i: rows.get(i, {}).get("url") for i in x["sources"]}
    return hits


def format_cited(pairs):
    by = defaultdict(list)
    for p, n in pairs:
        by[p].append(n)
    return "\n".join(f"  cited at {p}:{','.join(map(str, ns))}" for p, ns in by.items()) or "  cited nowhere"


FORMATS = ("concise", "detailed")


def short_tag(parts):
    """`[DOC S1, S2; DOC S3; UNK]` parsed -> `DOC S1,S2,S3; UNK` (one entry per kind, ids deduplicated)."""
    by = {}
    for p in parts:
        ids = by.setdefault(p["kind"], [])
        ids += [i for i in p["ids"] if i not in ids]
    return "; ".join(k + (" " + ",".join(v) if v else "") for k, v in by.items())


def format_facts(us, fmt="concise", limit=400):
    """Fact lines. detailed: `path:line  [KINDS]  text` (300 characters). concise: grouped by file, `  LINE [tag] text`
    with the tags moved to the front and the text cut at 160 characters."""
    out, last, cut = [], None, 0
    for u in us[:limit]:
        if fmt == "detailed":
            text = kbfacts.clip(u["text"], 300)
            cut += text != u["text"]
            out.append(f"{u['path']}:{u['line']}  [{'/'.join(kbfacts.kinds_of(u['tags']))}]  {text}")
            continue
        if u["path"] != last:
            out.append(u["path"])
            last = u["path"]
        full = " ".join(kbfacts.TAG.sub("", u["text"]).split())
        text = full if len(full) <= 160 else full[:160].rsplit(" ", 1)[0] + " ..."
        cut += text != full
        out.append(f"  {u['line']} [{short_tag(u['tags'])}] {text}")
    return "\n".join(out + [f"facts={len(us)}" + (f" (first {limit} shown)" if len(us) > limit else "")
                            + (f"; {cut} cut at {300 if fmt == 'detailed' else 160} characters (' ...'): kb_show PATH:LINE (in a clone: "
                               f"rag.py show) for the full text" if cut else "")])


def format_hits(hits, fmt="concise"):
    """Search hits. detailed: 600 characters of text each and a footer of the cited sources' urls (when resolved).
    concise: 300 characters, the cited ids only."""
    out = []
    for x in hits:
        n = 600 if fmt == "detailed" else 300
        text = x["text"] if len(x["text"]) <= n else x["text"][:n] + " ..."
        out.append(f"\n[{x['score']}] {x['path']}:{x['line']}  § {x['heading']}\n  " + text.replace("\n", "\n  "))
    urls = {i: u for x in hits for i, u in x.get("urls", {}).items()}
    if urls and fmt == "detailed":
        out.append("\nsources:")
        out += [f"  -> {i}  {u or 'UNKNOWN id'}" for i, u in urls.items()]
    elif fmt == "concise":
        ids = sorted({i for x in hits for i in x["sources"]}, key=kbid.sort_key)
        if ids:
            out.append("\ncited ids (urls: kb_source, or response_format detailed): " + ", ".join(ids))
    return "\n".join(out).strip()


def format_audit(rows, entries=False, fmt="detailed"):
    if fmt == "concise":
        out = ["| path | status | facts | DOC | DER | COMMUNITY | UNK | gaps | conflicts |", "|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            gv, cv = len(r["gaps_via_sources"]), len(r["conflicts_via_sources"])
            out.append(f"| {r['path']} | {r['status']} | {r['facts']} | {r['DOC']} | {r['DER']} | {r['COMMUNITY']} | "
                       f"{r['UNK']} | {len(r['gaps'])}" + (f"+{gv}" if gv else "") + f" | {len(r['conflicts'])}"
                       + (f"+{cv}" if cv else "") + " |")
        if entries:
            for r in rows:
                for key in ("gaps", "gaps_via_sources", "conflicts", "conflicts_via_sources"):
                    for e in r[key]:
                        out.append(f"{r['topic']}  {key}: {e['file']}:{e['line']}  {e['text'][:100]}")
        out.append(f"articles={len(rows)}; gaps/conflicts N+M: N name the topic, M cite a source it uses")
        return "\n".join(out)
    out = ["| path | status | retrieved | facts | DOC | DER | COMMUNITY | UNK | gaps | conflicts |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        g, c = len(r["gaps"]), len(r["conflicts"])
        gv, cv = len(r["gaps_via_sources"]), len(r["conflicts_via_sources"])
        out.append(f"| {r['path']} | {r['status']} | {r['retrieved_utc']} | {r['facts']} | {r['DOC']} | {r['DER']} | "
                   f"{r['COMMUNITY']} | {r['UNK']} | {g}" + (f" (+{gv} via sources)" if gv else "") + f" | {c}"
                   + (f" (+{cv} via sources)" if cv else "") + " |")
    if entries:
        for r in rows:
            for key in ("gaps", "gaps_via_sources", "conflicts", "conflicts_via_sources"):
                for e in r[key]:
                    out.append(f"{r['topic']}  {key}: {e['file']}:{e['line']}  {e['text'][:140]}")
    out.append(f"articles={len(rows)}; gaps/conflicts: named = the entry names the topic (marker, path or section); "
               f"via sources = it cites a source the topic uses")
    return "\n".join(out)


def run_eval(path):
    """Run pack on every question of the eval set: an expected path must be among the pack's articles, and the
    verdict must equal the expected one (`none` rows expect no path)."""
    with open(os.path.join(KB, path), encoding="utf-8", newline="") as f:
        cases = list(csv.DictReader(f))
    rows = []
    for c in cases:
        res = kbfacts.pack(c["question"])
        want = [p.strip() for p in c["expect_paths"].split(";") if p.strip()]
        found = [p for p in want if p in res["paths"]]
        vok = res["verdict"] == c["expect_verdict"] or (c["expect_verdict"] == "good" and res["verdict"] == "weak" and c.get("allow_weak") == "yes")
        fok = bool(found) if want else True
        rows.append({"id": c["id"], "verdict": res["verdict"], "want_verdict": c["expect_verdict"], "found": found,
                     "paths": res["paths"], "chars": len(res["text"]), "ok": vok and fok, "verdict_ok": vok, "found_ok": fok})
    n = len(rows)
    return {"n": n, "passed": sum(r["ok"] for r in rows), "verdict_ok": sum(r["verdict_ok"] for r in rows),
            "found_ok": sum(r["found_ok"] for r in rows), "mean_chars": round(sum(r["chars"] for r in rows) / max(n, 1)),
            "rows": rows}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("topics"); t.add_argument("domain", nargs="?")
    s = sub.add_parser("search"); s.add_argument("query", nargs="+"); s.add_argument("-k", type=positive_int, default=8); s.add_argument("-d", "--domain")
    s.add_argument("-u", "--urls", action="store_true", help="resolve each hit's cited source ids to their origin url")
    s.add_argument("--index", action="store_true", help="also search the root-level index files (README.md, _answers.md, ...)")
    s.add_argument("--format", choices=FORMATS, default="concise", help="detailed: 600 characters per hit (-u implies it)")
    r = sub.add_parser("src"); r.add_argument("ids", nargs="+")
    r.add_argument("--cited", action="store_true", help="also list every file line that names each id")
    pk = sub.add_parser("pack"); pk.add_argument("question", nargs="*"); pk.add_argument("--budget", type=positive_int, default=1200)
    pk.add_argument("-q", dest="parts", action="append", default=[], help="one part of a multi-part question (repeat, up to 6)")
    pk.add_argument("-d", "--domain"); pk.add_argument("--format", choices=FORMATS, default="detailed")
    fa = sub.add_parser("facts"); fa.add_argument("prefix"); fa.add_argument("--tag", help="comma-separated kinds, e.g. UNK,COMMUNITY")
    fa.add_argument("--format", choices=FORMATS, default="concise")
    au = sub.add_parser("audit"); au.add_argument("prefix", nargs="?"); au.add_argument("--status")
    au.add_argument("--entries", action="store_true", help="list the linked _gaps.md/_conflicts.md entries")
    au.add_argument("--unlinked", action="store_true", help="list _gaps.md/_conflicts.md entries no marker, path or section links to a topic")
    au.add_argument("--format", choices=FORMATS, default="concise")
    tf = sub.add_parser("topics-for"); tf.add_argument("paths", nargs="*", help="files or directories of the code to map")
    tf.add_argument("--keywords", help="text to map instead of (or as well as) files")
    ev = sub.add_parser("eval"); ev.add_argument("--file", default=os.path.join("_tools", "lookup_eval.csv"))
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
        notes = []
        res = search(" ".join(a.query), a.k, a.domain, a.index, notes)
        for n in notes:
            print(f"note: {n}", file=sys.stderr)
        if a.urls:
            add_urls(res)
        if a.json:
            return print(json.dumps(res, indent=1))
        if res:
            print(format_hits(res, "detailed" if a.urls else a.format))
        if not res:
            sys.exit("no match")
    elif a.cmd == "src":
        res = sources(a.ids)
        cited = kbfacts.cited_lines([x["id"] for x in res]) if a.cited else {}
        if a.json:
            for x in res:
                if a.cited:
                    x["cited_at"] = [f"{p}:{n}" for p, n in cited.get(x["id"], [])]
            return print(json.dumps(res, indent=1))
        for x in res:
            print(f"{x['id']}  {x['title']}" + (f"\n  {x['url']}  ({x['publisher']}; {x['version_or_date']})" if "url" in x else "")
                  + (f"\n  superseded by {x['superseded_by']}" if (x.get("superseded_by") or "").strip() else "")
                  + (f"\n  used in: {x['used_in'].replace(';', ', ')}" if x.get("used_in") else ""))
            if a.cited:
                print(format_cited(cited.get(x["id"], [])))
    elif a.cmd == "pack":
        parts = a.parts + ([" ".join(a.question)] if a.question else [])
        if not parts:
            sys.exit("pack: give a question, or -q PART for each part")
        if len(parts) > kbfacts.MAX_QUESTIONS:
            sys.exit(f"pack: at most {kbfacts.MAX_QUESTIONS} parts")
        res = kbfacts.pack_many(parts, a.budget, a.domain, a.format)
        if a.json:
            return print(json.dumps(res, indent=1))
        print(res["text"])
    elif a.cmd == "facts":
        kinds = {k.strip().upper() for k in (a.tag or "").split(",") if k.strip()}
        bad = kinds - set(kbfacts.KINDS)
        if bad:
            sys.exit(f"unknown tag kind(s): {', '.join(sorted(bad))} (use {', '.join(kbfacts.KINDS)})")
        res = [u for u in kbfacts.units(a.prefix) if u["tags"] and (not kinds or kinds & set(kbfacts.kinds_of(u["tags"])))]
        if a.json:
            return print(json.dumps([{k: u[k] for k in ("path", "line", "section", "text", "tags")} for u in res], indent=1))
        print(format_facts(res, a.format, limit=len(res)))
    elif a.cmd == "audit" and a.unlinked:
        tf, srcs, n = kbfacts.topic_files(), kbfacts.source_rows(), 0
        for name in ("_gaps.md", "_conflicts.md"):
            for e in kbfacts.link_entries(kbfacts.ledger_entries(name), tf, srcs):
                if not e["explicit"] and (not a.prefix or any(kbfacts.in_prefix(t, a.prefix) for t in e["via_sources"]) or e["section"].startswith(a.prefix.split("/")[0])):
                    n += 1
                    hint = f"  [via sources: {', '.join(e['via_sources'][:4])}]" if e["via_sources"] else ""
                    print(f"{name}:{e['line']}  ({e['section']})  {e['text'][:110]}{hint}")
        print(f"unlinked={n}: add `(topic: <domain>/<slug>)` at the end of each entry")
    elif a.cmd == "audit":
        rows = kbfacts.audit(a.prefix, a.status)
        if a.json:
            return print(json.dumps(rows, indent=1))
        print(format_audit(rows, a.entries, a.format))
    elif a.cmd == "topics-for":
        if not a.paths and not a.keywords:
            sys.exit("topics-for: give files or directories, or --keywords TEXT")
        res = kbfacts.topics_for(a.paths, a.keywords or "")
        if a.json:
            return print(json.dumps(res, indent=1))
        print(kbfacts.format_topics_for(res))
    elif a.cmd == "eval":
        res = run_eval(a.file)
        if a.json:
            return print(json.dumps(res, indent=1))
        width = max((len(r["id"]) for r in res["rows"]), default=6)
        for r in res["rows"]:
            print(f"{'ok  ' if r['ok'] else 'FAIL'} {r['id']:<{width}} verdict={r['verdict']:<5} (want {r['want_verdict']:<5}) "
                  f"found={','.join(r['found']) or '-'} chars={r['chars']}")
        print(f"questions={res['n']} passed={res['passed']} verdict_ok={res['verdict_ok']} found_ok={res['found_ok']} "
              f"mean_chars={res['mean_chars']}")
        if res["passed"] != res["n"]:
            sys.exit(1)
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
