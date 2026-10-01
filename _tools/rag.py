#!/usr/bin/env python3
"""Retrieve from the kb for RAG (stdlib only).

  rag.py topics [DOMAIN]                   domains -> articles, subdirectories, data files
  rag.py search QUERY [-k 8] [-d DOMAIN] [-u]   the pack's ranking over every line of the kb (facts, prose, code
                                           blocks, data rows), at most 2 hits per file; -u adds each hit's
                                           source origin urls
  rag.py src S1824 [S-k3f7q2zd ...]        source id -> title, url, version (and "superseded by" when set)
  rag.py show PATH[:LINE] [-n 40]          print lines of a kb file (a path as the tools print it)
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
  rag.py eval [--file FILE]                pack against the lookup eval sets (every root's lookup_eval.csv, or FILE):
                                           expected article found, verdict
  rag.py topics-for PATH... | --keywords TEXT [--imports]   kb topics that code touches, from the curated code signals in
                                           each root's signals.csv (e.g. PublicClientApplication -> public/auth/msal-public-client);
                                           --imports matches only the packages the files declare, not comments or strings

Roots: every command spans all roots (kb/public, a team's kb/<name>/, KB_ROOTS) and prints qualified paths and
topics (`public/intune/x.md:12`); --root NAME (topics, search, pack, facts, audit) keeps one root. A DOMAIN or PREFIX
is qualified (`public/intune`) or bare (`intune`: that domain in every root).

--format concise|detailed: pack defaults to detailed (answers need the urls); facts, audit and search to concise
(facts grouped by file with a short tag and text, no url footer). Words that are product aliases
(_tools/aliases.csv: sccm, memcm, configmgr, ...) also match the product's other names. pack also searches untagged
Summary, Reference and Examples lines and untagged data rows, printed with `(no tag)`; they never make it `good`.

Add --json (before the command) for machine output. artifacts/ directories are not indexed. search skips the
index files (README.md, each root's _answers.md, _gaps.md, _conflicts.md, _coverage.csv) and the kb's own docs
(kb/_self/) unless --index; pack never sees them.
"""
import argparse, csv, json, os, sys
from collections import Counter, defaultdict
import kbcommon, kbid, kbfacts

CITED = kbid.SOURCE_ID  # legacy ids (not prose like S1/S3 sleep states) and hash ids
csv.field_size_limit(2**31 - 1)  # a very wide cell must not abort a read


def read_text(rel):
    """Return a kb file's text (a qualified or repository path, or absolute), or None (with a warning on stderr) if
    it cannot be read."""
    try:
        with open(kbcommon.path_of(rel), encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError as e:
        print(f"warning: skipped {rel}: {e.strerror}", file=sys.stderr)
        return None


def positive_int(v):
    n = int(v)
    if n < 1:
        raise argparse.ArgumentTypeError(f"must be >= 1, got {n}")
    return n


def domain_arg(domain):
    """-d as the kb spells it (`Intune` is `intune`); exits naming the domains when no path is under it."""
    if not domain:
        return None
    d = kbfacts.domain_prefix(domain)
    if d is None:
        sys.exit(f"no domain {domain!r}; omit -d, or use one of: {', '.join(kbfacts.domains())}")
    return d


def search(query, k, domain, index=False, notes=None, root=None):
    """The top-k hits for a query: kbfacts.search (the pack index; prose, code blocks and data rows included, the
    index files only with `index`)."""
    return kbfacts.search(query, k, domain, index, notes, root)


def topics(domain, root=None):
    """{qualified domain (`public/intune`, or `public/(index)` for a root's own files): articles, subdirectories,
    data files}, in every root or one; `domain` bare or qualified."""
    want = kbfacts.scope(domain, root)
    out = defaultdict(lambda: {"articles": [], "dirs": Counter(), "data": []})
    for r in kbcommon.roots():
        for base, dirs, files in os.walk(r.path):
            dirs[:] = sorted(d for d in dirs if d not in kbfacts.SKIP_DIRS - {"artifacts"} and not d.startswith("."))
            for f in sorted(files):
                rel = kbcommon.qualify(r, os.path.relpath(os.path.join(base, f), r.path))
                parts = rel.split("/")
                dom = "/".join(parts[:2]) if len(parts) > 2 else f"{r.name}/(index)"
                if want and not (kbfacts.in_prefix(dom, want) and len(parts) > 2):
                    continue
                if len(parts) > 3:  # nested directory: summarise by its first level
                    out[dom]["dirs"]["/".join(parts[:3]) + "/"] += 1
                elif f.endswith(".md"):
                    text = read_text(rel)
                    if text is None:
                        continue
                    m = kbfacts.front_matter(text)
                    out[dom]["articles"].append({"path": rel, "topic": kbcommon.qualify(r, m["topic"]) if m.get("topic") else "",
                                                 "title": m["title"], "priority": m.get("priority", ""), "status": m.get("status", "")})
                else:
                    out[dom]["data"].append(rel)
    return {d: {**v, "dirs": dict(v["dirs"])} for d, v in sorted(out.items())}


def source_rows():
    """{id: row} of every root's _sources.csv (kbfacts.source_rows); exits when a ledger cannot be read."""
    try:
        rows = kbfacts.source_rows()
    except OSError as e:
        sys.exit(f"cannot read _sources.csv: {e.strerror}")
    if rows and not {"id", "url"} <= next(iter(rows.values())).keys():
        sys.exit("_sources.csv lacks an 'id' or 'url' column")
    return rows


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
    """`[DOC S1, S2; DOC S3; UNK]` parsed -> `DOC S1,S2,S3; UNK` (one entry per kind, ids deduplicated); a DECISION
    part prints its decision's id (`DECISION D-k3f7q2zd`), which its `decision` holds, not its `ids`."""
    by = {}
    for p in parts:
        ids = by.setdefault(p["kind"], [])
        ids += [i for i in p["ids"] + [p.get("decision") or ""] if i and i not in ids]
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
        out = ["| path | status | facts | DOC | CODE | DER | COMMUNITY | UNK | gaps | conflicts |", "|---|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            gv, cv = len(r["gaps_via_sources"]), len(r["conflicts_via_sources"])
            out.append(f"| {r['path']} | {r['status']} | {r['facts']} | {r['DOC']} | {r['CODE']} | {r['DER']} | {r['COMMUNITY']} | "
                       f"{r['UNK']} | {len(r['gaps'])}" + (f"+{gv}" if gv else "") + f" | {len(r['conflicts'])}"
                       + (f"+{cv}" if cv else "") + " |")
        if entries:
            for r in rows:
                for key in ("gaps", "gaps_via_sources", "conflicts", "conflicts_via_sources"):
                    for e in r[key]:
                        out.append(f"{r['topic']}  {key}: {e['file']}:{e['line']}  {e['text'][:100]}")
        out.append(f"articles={len(rows)}; gaps/conflicts N+M: N name the topic, M cite a source it uses")
        return "\n".join(out)
    out = ["| path | status | retrieved | facts | DOC | CODE | DER | COMMUNITY | UNK | gaps | conflicts |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        g, c = len(r["gaps"]), len(r["conflicts"])
        gv, cv = len(r["gaps_via_sources"]), len(r["conflicts_via_sources"])
        out.append(f"| {r['path']} | {r['status']} | {r['retrieved_utc']} | {r['facts']} | {r['DOC']} | {r['CODE']} | {r['DER']} | "
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


def format_decision_conflicts(items):
    """The possible contradictions of kbfacts.decision_conflicts: per shared context, its active decisions. Text for a
    person to read; a kb with none prints nothing."""
    out = []
    for ref, ds in items:
        out.append(f"possible contradiction: {len(ds)} active decisions share {ref} (read them; nothing is blocked)")
        out += [f"  {d['id']} {d['path']}:{d['line']} {kbfacts.clip(d['text'], 200)}" for d in ds]
    return "\n".join(out)


def eval_cases(path=None):
    """[(root name, case)] of every root's lookup_eval.csv (under DATA_DIR), or of one file: `path` as given (else
    as a qualified or repository path), its cases belonging to the root that holds it (else the public root)."""
    if path is None:
        files = [(r.name, os.path.join(r.path, kbcommon.DATA_DIR, "lookup_eval.csv")) for r in kbcommon.roots()]
        files = [(n, p) for n, p in files if os.path.exists(p)]
    else:
        full = os.path.abspath(path) if os.path.exists(path) else kbcommon.path_of(path)
        owner = next((r.name for r in kbcommon.roots()
                      if os.path.commonpath([full, r.path]) == r.path), kbcommon.public().name)
        files = [(owner, full)]
    out = []
    for name, p in files:
        with open(p, encoding="utf-8", newline="") as f:
            out += [(name, c) for c in csv.DictReader(f)]
    return out


def run_eval(path=None):
    """Run pack on every question of the eval sets (eval_cases): an expected path (relative to the case's root)
    must be among the pack's articles, and the verdict must equal the expected one (`none` rows expect no path)."""
    rows = []
    for root, c in eval_cases(path):
        res = kbfacts.pack(c["question"])
        want = [kbcommon.qualify(root, p.strip()) for p in c["expect_paths"].split(";") if p.strip()]
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
    t = sub.add_parser("topics"); t.add_argument("domain", nargs="?"); t.add_argument("--root", help="one root only")
    s = sub.add_parser("search"); s.add_argument("query", nargs="+"); s.add_argument("-k", type=positive_int, default=8); s.add_argument("-d", "--domain")
    s.add_argument("--root", help="one root only (e.g. public)")
    s.add_argument("-u", "--urls", action="store_true", help="resolve each hit's cited source ids to their origin url")
    s.add_argument("--index", action="store_true", help="also search the index files (README.md, each root's _answers.md, ...) and the kb/_self/ docs")
    s.add_argument("--format", choices=FORMATS, default="concise", help="detailed: 600 characters per hit (-u implies it)")
    r = sub.add_parser("src"); r.add_argument("ids", nargs="+")
    r.add_argument("--cited", action="store_true", help="also list every file line that names each id")
    pk = sub.add_parser("pack"); pk.add_argument("question", nargs="*"); pk.add_argument("--budget", type=positive_int, default=1200)
    pk.add_argument("-q", dest="parts", action="append", default=[], help="one part of a multi-part question (repeat, up to 6)")
    pk.add_argument("-d", "--domain"); pk.add_argument("--format", choices=FORMATS, default="detailed")
    pk.add_argument("--root", help="one root only")
    pk.add_argument("--invalidated", action="store_true", help="also print the invalidated decisions, with the reason")
    fa = sub.add_parser("facts"); fa.add_argument("prefix"); fa.add_argument("--tag", help="comma-separated kinds, e.g. UNK,COMMUNITY")
    fa.add_argument("--format", choices=FORMATS, default="concise"); fa.add_argument("--root", help="one root only")
    au = sub.add_parser("audit"); au.add_argument("prefix", nargs="?"); au.add_argument("--status")
    au.add_argument("--root", help="one root only")
    au.add_argument("--entries", action="store_true", help="list the linked _gaps.md/_conflicts.md entries")
    au.add_argument("--unlinked", action="store_true", help="list _gaps.md/_conflicts.md entries no marker, path or section links to a topic")
    au.add_argument("--format", choices=FORMATS, default="concise")
    tf = sub.add_parser("topics-for"); tf.add_argument("paths", nargs="*", help="files or directories of the code to map")
    tf.add_argument("--keywords", help="text to map instead of (or as well as) files")
    tf.add_argument("--imports", action="store_true", help="match the signals against the packages the files declare (imports, manifests), not their text")
    ev = sub.add_parser("eval"); ev.add_argument("--file", help="one eval file (default: every root's lookup_eval.csv)")
    w = sub.add_parser("show"); w.add_argument("target"); w.add_argument("-n", type=positive_int, default=40)
    w.add_argument("--invalidated", action="store_true", help="also print the invalidated decisions, with the reason")
    a = ap.parse_args()

    if a.cmd == "topics":
        if a.root and a.root not in {r.name for r in kbcommon.roots()}:
            sys.exit(f"no root {a.root!r}")
        res = topics(a.domain, a.root)
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
        res = search(" ".join(a.query), a.k, domain_arg(a.domain), a.index, notes, a.root)
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
        res = kbfacts.pack_many(parts, a.budget, domain_arg(a.domain), a.format, a.root, a.invalidated)
        if a.json:
            return print(json.dumps(res, indent=1))
        print(res["text"])
    elif a.cmd == "facts":
        kinds = {k.strip().upper() for k in (a.tag or "").split(",") if k.strip()}
        bad = kinds - set(kbfacts.KINDS)
        if bad:
            sys.exit(f"unknown tag kind(s): {', '.join(sorted(bad))} (use {', '.join(kbfacts.KINDS)})")
        res = [u for u in kbfacts.units(kbfacts.scope(a.prefix, a.root))
               if u["tags"] and (not kinds or kinds & set(kbfacts.kinds_of(u["tags"])))]
        if a.json:
            return print(json.dumps([{k: u[k] for k in ("path", "line", "section", "text", "tags")} for u in res], indent=1))
        print(format_facts(res, a.format, limit=len(res)))
    elif a.cmd == "audit" and a.unlinked:
        tf, srcs, n = kbfacts.topic_files(), kbfacts.source_rows(), 0
        want = kbfacts.scope(a.prefix, a.root)
        for name in (kbcommon.GAPS, kbcommon.CONFLICTS):
            for e in kbfacts.link_entries(kbfacts.ledger_entries(name), tf, srcs):
                if a.root and kbfacts.root_name(e["file"]) != a.root:
                    continue
                if not e["explicit"] and (not a.prefix or any(kbfacts.in_prefix(t, want) for t in e["via_sources"])
                                          or e["section"].startswith(kbfacts.bare(a.prefix).split("/")[0])):
                    n += 1
                    hint = f"  [via sources: {', '.join(e['via_sources'][:4])}]" if e["via_sources"] else ""
                    print(f"{e['file']}:{e['line']}  ({e['section']})  {e['text'][:110]}{hint}")
        print(f"unlinked={n}: add `(topic: <domain>/<slug>)` at the end of each entry")
    elif a.cmd == "audit":
        rows = kbfacts.audit(a.prefix, a.status, a.root)
        if a.json:
            return print(json.dumps(rows, indent=1))
        print(format_audit(rows, a.entries, a.format))
        if conflicts := format_decision_conflicts(kbfacts.decision_conflicts(a.prefix, a.root)):
            print(conflicts)
    elif a.cmd == "topics-for":
        if not a.paths and not a.keywords:
            sys.exit("topics-for: give files or directories, or --keywords TEXT")
        res = kbfacts.topics_for(a.paths, a.keywords or "", imports=a.imports)
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
        full = kbfacts.locate(path)
        if not kbfacts.showable(full):
            sys.exit(f"{path}: outside the kb")
        if not os.path.isfile(full):
            sys.exit(f"{path}: no such file")
        if line and not line.isdigit():
            sys.exit(f"{line!r}: line must be a positive number")
        text = read_text(full)
        if text is None:
            sys.exit(1)
        lines = text.splitlines()
        start = max(int(line or 1), 1)
        end = min(start + a.n, len(lines) + 1)
        for n in range(start, end):
            print(f"{n:>5}  {lines[n - 1]}")
        decisions = kbfacts.show_decisions(kbfacts.qpath_of(full), start, end - 1, a.invalidated)
        if decisions:
            print("decisions:")
            print("\n".join(decisions))


if __name__ == "__main__":
    try:
        main()
    except kbcommon.RootError as e:  # a malformed ROOT_FILE, or two roots sharing a name or an id prefix
        sys.exit(f"error: {e}")
