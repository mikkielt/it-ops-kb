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
  rag.py pack QUESTION --revalidate        also check the cited sources of the printed fact lines against their pages
                                           now (the network, within a time budget; only these sources and lines) and
                                           mark each line current, moved (with the new passage), not found or
                                           source-dated only; a source that cannot be checked keeps its offline stamp
  rag.py pack --root _self QUESTION        the best passages of the kb/_self rule docs and the decisions tied to them;
  rag.py pack --root _self --item ID [QUESTION]   the brief of a backlog item: its docs (kb/_self/map.csv) and decisions
  rag.py pack --root _self --set NAME      the tested questions of a set (`skill` or `skill:step`, the `sets` column of
                                           kb/_self/_retrieval/lookup_eval.csv), their passages and the decisions tied to them
  rag.py facts PREFIX [--tag UNK,COMMUNITY] [--format detailed]
                                           fact lines under a path prefix (a domain, topic or file), by tag kind
  rag.py audit [PREFIX] [--status partial] [--entries] [--unlinked] [--format detailed]
                                           per article: status, retrieved_utc, fact counts by tag kind and the
                                           _gaps.md/_conflicts.md entries linked to it (named, or via its sources);
                                           --unlinked lists the entries no topic marker, path or section links
  rag.py src S1824 --cited                 also every file line that names the id
  rag.py eval [--file FILE] [--root NAME] [--free] [--min N] [--all] | --write-shares   pack against the lookup eval sets (every
                                           root's lookup_eval.csv and kb/_self's, or FILE): expected article found,
                                           verdict, expected phrase; prints the failing rows and the totals line
                                           (--all: every row); exit 1 unless every row (or at least N) passes,
                                           or, with no --file, when noted= (good rows whose pack prints a
                                           check: or route: line) is above NOTED_BASELINE;
                                           --free adds the _self rows' leave-one-out rate (slow);
                                           a row failing only through a key word whose share crossed COMMON_SHARE
                                           since word_shares.csv was written prints DRIFT and passes, left out of
                                           noted= unless its pack carries a note; --write-shares rewrites that file for every root
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
import argparse, csv, difflib, json, os, re, sys
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


def format_logs(lines):
    """The observed signals (LOG lines, kbfacts.logs_for) a show or an audit prints after its table or lines, under their
    label; "" for none."""
    return "\n".join([kbfacts.LOG_LABEL] + lines) if lines else ""


def format_decision_conflicts(items):
    """The possible contradictions of kbfacts.decision_conflicts: per shared context, its active decisions. Text for a
    person to read; a kb with none prints nothing."""
    out = []
    for ref, ds in items:
        out.append(f"possible contradiction: {len(ds)} active decisions share {ref} (read them; nothing is blocked)")
        out += [f"  {d['id']} {d['path']}:{d['line']} {kbfacts.clip(d['text'], 200)}" for d in ds]
    return "\n".join(out)


def eval_cases(path=None, root=None):
    """[(root name, case)] of every root's lookup_eval.csv (under DATA_DIR) and kb/_self's, or of one root's, or of
    one file: `path` as given (else as a qualified or repository path), its cases belonging to `root`, else to the
    root that holds it (else the public root). The root name SELF_ROOT is the kb's own rule docs."""
    if path is None:
        files = [(r.name, os.path.join(r.path, kbcommon.DATA_DIR, "lookup_eval.csv")) for r in kbcommon.roots()]
        files.append((kbfacts.SELF_ROOT, os.path.join(kbcommon.SELF, kbcommon.DATA_DIR, "lookup_eval.csv")))
        files = [(n, p) for n, p in files if os.path.exists(p) and root in (None, n)]
    else:
        full = os.path.abspath(path) if os.path.exists(path) else kbcommon.path_of(path)
        owner = root or next((r.name for r in kbcommon.roots()
                              if os.path.commonpath([full, r.path]) == r.path), kbcommon.public().name)
        files = [(owner, full)]
    out = []
    for name, p in files:
        with open(p, encoding="utf-8", newline="") as f:
            out += [(name, c) for c in csv.DictReader(f)]
    return out


HELDOUT_FILE = "lookup_heldout.csv"  # the file name of the held-out eval set the gates read
FROZEN_FILES = (HELDOUT_FILE, "repro_bench.csv")  # the file names eval --file holds to the held-out rule: no row rewords a tuned one
REWORD_RATIO = 0.75  # a held-out question this similar to a tuned one (difflib, lower-cased) is a rewording of it


def reworded_pairs(held, tuned):
    """[(held id, tuned label, ratio)] of the held-out rows that reword a tuned row. `held` is [(id, expected paths,
    question)] and `tuned` [(label, expected paths, question)] (a lookup_eval.csv row or a doc2query expansion of the
    article); a pair shares an expected path and its lower-cased questions have a difflib ratio of REWORD_RATIO or more."""
    out = []
    for hid, hpaths, hq in held:
        hq = hq.lower()
        for label, tpaths, tq in tuned:
            if hpaths & tpaths:
                ratio = difflib.SequenceMatcher(None, hq, tq.lower()).ratio()
                if ratio >= REWORD_RATIO:
                    out.append((hid, label, ratio))
    return out


def heldout_rewordings(path, root=None):
    """The reworded_pairs of the held-out file `path` against the lookup_eval.csv beside it and the doc2query expansions
    of the facts of its rows' expected articles."""
    owner = root or next((r.name for r in kbcommon.roots()
                          if os.path.commonpath([os.path.abspath(path), r.path]) == r.path), kbcommon.public().name)
    def rows(p):
        return [(c["id"], {x.strip() for x in c["expect_paths"].split(";") if x.strip()}, c["question"])
                for _, c in eval_cases(p, owner)]
    held = rows(path)
    beside = os.path.join(os.path.dirname(os.path.abspath(path)), "lookup_eval.csv")
    tuned = rows(beside) if os.path.exists(beside) else []
    wanted = {kbcommon.qualify(owner, p): p for _, ps, _ in held for p in ps}
    exps = kbfacts.expansions() if wanted else {}
    for u in kbfacts.units(owner) if exps else ():
        if u["path"] in wanted:
            tuned += [(f"doc2query:{kbfacts.fact_key(u['text'])}", {wanted[u["path"]]}, q)
                      for q in exps.get(kbfacts.fact_key(u["text"]), ())]
    return reworded_pairs(held, tuned)


OFFKB_FILE = os.path.join("doc2query", "offkb_questions.txt")  # a root's off-kb list, under its _retrieval directory


def question_key(q):
    """A question as the off-kb overlap compares it: lower-cased, spacing collapsed, no closing question mark."""
    return " ".join(q.lower().split()).rstrip("?").rstrip()


def offkb_overlaps(path=None, root=None):
    """[(row id, eval file name, off-kb list path, its line)] of the eval rows that expect the verdict `good` (a `weak` or
    `none` row is a guard that an off-kb question stays below it) and whose question is also a line of the off-kb list beside the file (OFFKB_FILE next to it): a question
    the kb answers and one it lacks at once. `path` names one file, else every root's lookup_eval.csv and HELDOUT_FILE
    (`root` keeps one root), as eval_cases does."""
    if path is None:
        dirs = [(r.name, os.path.join(r.path, kbcommon.DATA_DIR)) for r in kbcommon.roots()]
        dirs.append((kbfacts.SELF_ROOT, os.path.join(kbcommon.SELF, kbcommon.DATA_DIR)))
        files = [(n, os.path.join(d, f)) for n, d in dirs if root in (None, n) for f in ("lookup_eval.csv", HELDOUT_FILE)]
    else:
        files = [(root, os.path.abspath(path) if os.path.exists(path) else kbcommon.path_of(path))]
    out = []
    for name, p in files:
        offkb = os.path.join(os.path.dirname(p), OFFKB_FILE)
        if not (os.path.isfile(p) and os.path.isfile(offkb)):
            continue
        with open(offkb, encoding="utf-8") as f:
            lines = {}
            for n, line in enumerate(f, 1):
                lines.setdefault(question_key(line), n)
        out += [(c["id"], os.path.basename(p), offkb, lines[question_key(c["question"])])
                for _, c in eval_cases(p, name) if c["expect_verdict"] == "good" and question_key(c["question"]) in lines]
    return out


def offkb_questions(root=None):
    """The questions of a root's off-kb list (OFFKB_FILE under its DATA_DIR; the public root's by default), in file
    order, without blank lines and `#` comments."""
    base = kbcommon.public().path if root is None else next(r.path for r in kbcommon.roots() if r.name == root)
    with open(os.path.join(base, kbcommon.DATA_DIR, OFFKB_FILE), encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]


def scatter_calibration():
    """The scatter note's threshold fitted to this kb (kbfacts.SCATTER_SCORE, kbfacts.pack's `scatter`). A `good` pack
    is flagged at a whole number T when its best articles lie in SCATTER_DOMAINS or more domains and its best unit
    scores under T. Counted over the questions of the public root's lookup_eval.csv rows that expect `good` (the tuned
    set: lookup_heldout.csv is never read) and over its off-kb list's, each that packs to a `good` the note applies
    to (`top_score` is not None). The threshold maximises the off-kb goods flagged less the eval goods flagged, the
    lower T on a tie. Returns {threshold, off_flagged, off_goods, eval_flagged, eval_goods} at it, {current,
    off_noted, eval_noted} at kbfacts.SCATTER_SCORE (the packs' own `scatter`) and `grid`, [(T, off goods flagged,
    eval goods flagged)]."""
    def feats(questions):
        packs = [kbfacts.pack(q) for q in questions]
        return [p for p in packs if p["top_score"] is not None]
    evals = feats(c["question"] for _, c in eval_cases(root=kbcommon.public().name) if c["expect_verdict"] == "good")
    offs = feats(offkb_questions())

    def flagged(packs, t):
        return sum(1 for p in packs if len(p["top_domains"]) >= kbfacts.SCATTER_DOMAINS and p["top_score"] < t)
    top = max((p["top_score"] for p in evals + offs), default=0)
    grid = [(t, flagged(offs, t), flagged(evals, t)) for t in range(1, int(top) + 2)]
    best = max(grid, key=lambda g: (g[1] - g[2], -g[0]), default=(0, 0, 0))
    return {"threshold": best[0], "off_flagged": best[1], "off_goods": len(offs), "eval_flagged": best[2],
            "eval_goods": len(evals), "current": kbfacts.SCATTER_SCORE,
            "off_noted": sum(1 for p in offs if p["scatter"]), "eval_noted": sum(1 for p in evals if p["scatter"]),
            "grid": grid}


NOTE_LINES = ("check:", "route:")  # the pack's lines that flag a `good` verdict as possibly false (kbfacts.pack)
NOTED_BASELINE = 13  # eval rows expected `good` whose pack carries one: the default run fails above it


def regex_found(rx, text):
    """True when the regex `rx` matches in `text` (re.search, no flags); an uncompilable one matches nothing."""
    try:
        return re.search(rx, text) is not None
    except re.error:
        return False


SHARES_FILE = "word_shares.csv"  # beside a root's lookup_eval.csv: the key-word shares a failing eval row is re-judged on
SHARES_FLOOR = kbfacts.COMMON_SHARE / 2  # the file lists the eval questions' key words held by this share of the units or more


def shares_baseline(name, path=None):
    """{key word: share of the searched units} of the committed baseline file the cases of root `name` are
    re-judged on: SHARES_FILE beside eval file `path` when there is one, else the root's (`_self`'s for SELF_ROOT).
    Only `eval --write-shares` rewrites it; {} when there is none."""
    if name == kbfacts.SELF_ROOT:
        folder = os.path.join(kbcommon.SELF, kbcommon.DATA_DIR)
    else:
        folder = next((os.path.join(r.path, kbcommon.DATA_DIR) for r in kbcommon.roots() if r.name == name), "")
    if path:
        full = os.path.abspath(path) if os.path.exists(path) else kbcommon.path_of(path)
        if os.path.isfile(os.path.join(os.path.dirname(full), SHARES_FILE)):
            folder = os.path.dirname(full)
    out = {}
    try:
        with open(os.path.join(folder, SHARES_FILE), encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                try:
                    out[row["word"]] = float(row["share"])
                except (KeyError, ValueError):
                    continue
    except OSError:
        pass
    return out


def write_shares(root=None):
    """Write SHARES_FILE beside the lookup_eval.csv of every root (of `root`) that has one: the key words of its
    questions that SHARES_FLOOR of the searched units or more hold, with their share now. [(file, rows written)]."""
    out, cases = [], {}
    for name, c in eval_cases(None, root):
        cases.setdefault(name, []).append(c["question"])
    for name, questions in cases.items():
        own = name == kbfacts.SELF_ROOT
        words = {}
        for q in questions:
            words.update(kbfacts.key_shares(q, name if own else None))
        rows = sorted((t, f"{s:.4f}") for t, s in words.items() if s >= SHARES_FLOOR)
        folder = os.path.join(kbcommon.SELF if own else next(r.path for r in kbcommon.roots() if r.name == name), kbcommon.DATA_DIR)
        target = os.path.join(folder, SHARES_FILE)
        with open(target, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["word", "share"])
            w.writerows(rows)
        out.append((target, len(rows)))
    return out


def run_eval(path=None, root=None, free=False):
    """Run pack on every question of the eval sets (eval_cases): an expected path (relative to the case's root, to
    kb/_self for SELF_ROOT) must be among the pack's articles, the verdict must equal the expected one (`none` rows
    expect no path), when the row has `expect_text` one of its `;`-separated phrases must occur in the pack's text, and
    when it has `expect_re` (`failed=regex`) one of its `;`-separated regexes must match it (`re.search`, no flags, as
    agent_bench.check scores an answer; one that does not compile matches nothing).
    A `_self` row passes on its text alone: its phrase must be in one of its docs (it has an anchor, else
    `failed=anchor`) and in the pack's text (else `failed=text`); a row with no `expect_text` expects the verdict
    `none`. `noted` counts the rows expecting `good` whose pack prints a `check:` or `route:` line (NOTE_LINES). With `free`, `free` counts the anchored `_self` rows whose phrase is still printed when the pack leaves out
    that row's own tested question (kbfacts.self_store with skip), out of `anchored`: one store build per row, so the
    gate's run leaves it out and the figure is None. A row outside `_self` whose question a kind expert routes
    (kbfacts.routed: a count, a decision id, a conflict, a gap, a citation) fails with `routed`: the eval rows rank.
    A row that fails its verdict is judged once more on the committed key-word shares (shares_baseline) of the words
    whose share is on the other side of COMMON_SHARE than the file's: when it then passes, it is `drift` ({word: now,
    baseline}), passes, and counts under `drifted`, and under `noted` only when its re-judged pack carries a `check:` or `route:` line
    (the pack a lookup prints is not re-judged)."""
    rows, hits, anchored, passages, bases = [], 0, 0, None, {}
    for name, c in eval_cases(path, root):
        own = name == kbfacts.SELF_ROOT
        res = kbfacts.pack(c["question"], root=name) if own else kbfacts.pack(c["question"])
        base = "kb/_self/" if own else kbcommon.qualify(name, "")
        want = [base + p.strip() for p in c["expect_paths"].split(";") if p.strip()]
        phrases = [t.strip() for t in (c.get("expect_text") or "").split(";") if t.strip()]
        regexes = [t.strip() for t in (c.get("expect_re") or "").split(";") if t.strip()]
        # every row is a ranking row: a question a kind expert routes (kbfacts.routed) never reaches pack in a lookup
        free_of_routing = own or kbfacts.routed(c["question"]) is None

        def judge(res):
            """(the row's failed checks, verdict_ok, found, found_ok, text_ok) of pack result `res`."""
            found = [p for p in want if p in res["paths"]]
            vok = res["verdict"] == c["expect_verdict"] or (c["expect_verdict"] == "good" and res["verdict"] == "weak" and c.get("allow_weak") == "yes")
            fok = bool(found) if want else True
            tok = any(t in res["text"] for t in phrases) if phrases else True
            rok = any(regex_found(t, res["text"]) for t in regexes) if regexes else True
            failed = [w for w, ok in (("verdict", vok), ("path", fok), ("text", tok), ("regex", rok), ("routed", free_of_routing)) if not ok]
            if own:
                if not phrases:
                    failed = [] if res["verdict"] == "none" else ["verdict"]
                elif not kbfacts.anchor_of(c, passages):
                    failed = ["anchor"]
                else:
                    failed = [w for w, ok in (("text", tok), ("regex", rok)) if not ok]
            return failed, vok, found, fok, tok

        if own:
            passages = passages or kbfacts.self_units()
        failed, vok, found, fok, tok = judge(res)
        if own and phrases and "anchor" not in failed:
            anchored += 1
            if free:
                loo = kbfacts.pack(c["question"], root=name, st=kbfacts.self_store(c["id"]))
                hits += any(t in loo["text"] for t in phrases)
        drift = {}
        if "verdict" in failed:  # re-judged on the committed key-word shares (shares_baseline), never a moved threshold
            bases.setdefault(name, shares_baseline(name, path))
            moved = kbfacts.drifted_words(c["question"], bases[name], name if own else None) if bases[name] else {}
            if moved:
                shares = {t: b for t, (_, b) in moved.items()}
                again = kbfacts.pack(c["question"], root=name, shares=shares) if own else kbfacts.pack(c["question"], shares=shares)
                judged = judge(again)
                if not judged[0]:
                    drift, res = moved, again
                    failed, vok, found, fok, tok = judged
        noted = c["expect_verdict"] == "good" and any(ln.startswith(NOTE_LINES) for ln in res["text"].splitlines())
        rows.append({"id": c["id"], "verdict": res["verdict"], "want_verdict": c["expect_verdict"], "found": found,
                     "paths": res["paths"], "chars": len(res["text"]), "ok": not failed, "verdict_ok": vok,
                     "found_ok": fok, "text_ok": tok, "noted": noted, "failed": failed,
                     "drift": {t: {"now": round(a, 4), "baseline": round(b, 4)} for t, (a, b) in drift.items()}})
    n = len(rows)
    return {"n": n, "passed": sum(r["ok"] for r in rows), "verdict_ok": sum(r["verdict_ok"] for r in rows),
            "found_ok": sum(r["found_ok"] for r in rows), "mean_chars": round(sum(r["chars"] for r in rows) / max(n, 1)),
            "noted": sum(r["noted"] for r in rows), "drifted": sum(bool(r["drift"]) for r in rows), "free": hits if free else None, "anchored": anchored, "rows": rows}


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
    pk.add_argument("--item", help="with --root _self: the brief of a backlog item (its title and goal when no question is given)")
    pk.add_argument("--set", dest="set_name", help="with --root _self: the tested questions of a set (`skill` or `skill:step`), "
                    "their passages and the decisions tied to them; no ranking, no verdict")
    pk.add_argument("--invalidated", action="store_true", help="also print the invalidated decisions, with the reason")
    pk.add_argument("--revalidate", action="store_true", help="check the cited sources of the printed fact lines against "
                    "their pages now (the network, within a time budget) and mark each line current, moved, not found "
                    "or source-dated only; the results are kept under _cache/ only")
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
    ev = sub.add_parser("eval"); ev.add_argument("--file", help="one eval file (default: every root's lookup_eval.csv and kb/_self's)")
    ev.add_argument("--root", help="one root only (a kb root or _self); with --file, the root the file's rows belong to")
    ev.add_argument("--free", action="store_true", help="also the leave-one-out rate of the _self rows (slow: one store build per row)")
    ev.add_argument("--min", type=positive_int, help="exit 0 when at least MIN rows pass (default: every row), e.g. the "
                    "held-out file kb/public/_retrieval/lookup_heldout.csv's answer rate")
    ev.add_argument("--write-shares", action="store_true", help="rewrite word_shares.csv beside every root's lookup_eval.csv "
                    "(the key-word shares a failing row is re-judged on) and exit; no judging")
    ev.add_argument("--all", action="store_true", help="print every row, passing ones too (default: the failing rows and the totals)")
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
    elif a.cmd == "pack" and a.set_name:
        if a.root != kbfacts.SELF_ROOT or a.question or a.parts or a.item:
            print(f"pack: --set needs --root {kbfacts.SELF_ROOT} and takes no question, -q or --item", file=sys.stderr)
            sys.exit(2)
        info = {}
        try:
            text = kbfacts.set_pack(a.set_name, info)
        except ValueError as e:
            print(f"pack: {e}", file=sys.stderr)
            sys.exit(2)
        print(text)
        kbfacts.record_self(text, None, set_name=a.set_name, info=info)
    elif a.cmd == "pack":
        brief = None
        if a.item:
            if a.root != kbfacts.SELF_ROOT:
                print(f"pack: --item needs --root {kbfacts.SELF_ROOT}", file=sys.stderr)
                sys.exit(2)
            brief = kbfacts.item_brief(a.item)
            if brief is None:
                print(f"no item {a.item}", file=sys.stderr)
                sys.exit(2)
        parts = a.parts + ([" ".join(a.question)] if a.question else [])
        if not parts and brief:
            parts = [brief["question"]]
        if not parts:
            sys.exit("pack: give a question, or -q PART for each part")
        if any(not p.strip() for p in parts):
            print("pack: empty question", file=sys.stderr)
            sys.exit(2)
        if len(parts) > kbfacts.MAX_QUESTIONS:
            sys.exit(f"pack: at most {kbfacts.MAX_QUESTIONS} parts")
        res = kbfacts.pack_many(parts, a.budget, domain_arg(a.domain), a.format, a.root, a.invalidated, brief, a.revalidate)
        if a.root == kbfacts.SELF_ROOT:
            kbfacts.record_self(res["text"], a.budget, res, parts, item=a.item)
        if a.json:
            return print(json.dumps(res, indent=1))
        print(res["text"])
    elif a.cmd == "facts":
        kinds = {k.strip().upper() for k in (a.tag or "").split(",") if k.strip()}
        bad = kinds - set(kbfacts.EVIDENCE_KINDS)
        if bad:
            sys.exit(f"unknown tag kind(s): {', '.join(sorted(bad))} (use {', '.join(kbfacts.EVIDENCE_KINDS)})")
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
        if logs := format_logs(kbfacts.audit_logs(rows)):
            print(logs)
    elif a.cmd == "topics-for":
        if not a.paths and not a.keywords:
            sys.exit("topics-for: give files or directories, or --keywords TEXT")
        res = kbfacts.topics_for(a.paths, a.keywords or "", imports=a.imports)
        if a.json:
            return print(json.dumps(res, indent=1))
        print(kbfacts.format_topics_for(res))
    elif a.cmd == "eval":
        if a.root and a.root not in {r.name for r in kbcommon.roots()} | {kbfacts.SELF_ROOT}:
            ap.error(f"no root {a.root!r}")
        if a.write_shares:
            if a.file:
                ap.error("--write-shares writes the roots' files: no --file")
            for target, n in write_shares(a.root):
                print(f"wrote {os.path.relpath(target, kbcommon.HOME)}: {n} words")
            return
        pairs = heldout_rewordings(a.file, a.root) if a.file and os.path.basename(a.file) in FROZEN_FILES else []
        for hid, label, ratio in pairs:
            print(f"REWORD {hid} ~ {label} (ratio {ratio:.2f}): a held-out row rewords a tuned row; replace it")
        overlaps = offkb_overlaps(a.file, a.root)
        for rid, name, offkb, line in overlaps:
            print(f"OFFKB {rid} ({name}): its question is line {line} of {os.path.relpath(offkb, kbcommon.HOME)}, "
                  f"which lists questions the kb lacks; remove the line, or the row if the kb does not answer it")
        if pairs or overlaps:
            sys.exit(1)
        res = run_eval(a.file, a.root, a.free)
        over = a.file is None and res["noted"] > NOTED_BASELINE
        failing = res["passed"] < (res["n"] if a.min is None else a.min) or over  # the exit code, --json or not
        if a.json:
            print(json.dumps(res, indent=1))
            sys.exit(1 if failing else 0)
        width = max((len(r["id"]) for r in res["rows"]), default=6)
        for r in (r for r in res["rows"] if a.all or not r["ok"]):
            print(f"{'ok  ' if r['ok'] else 'FAIL'} {r['id']:<{width}} verdict={r['verdict']:<5} (want {r['want_verdict']:<5}) "
                  f"found={','.join(r['found']) or '-'} chars={r['chars']}" + (f" failed={','.join(r['failed'])}" if r["failed"] else ""))
        print(f"questions={res['n']} passed={res['passed']} verdict_ok={res['verdict_ok']} found_ok={res['found_ok']} "
              f"mean_chars={res['mean_chars']} noted={res['noted']}"
              + (f" free={res['free']}/{res['anchored']}" if res["free"] is not None else ""))
        for r in (r for r in res["rows"] if r["drift"]):  # printed whatever the exit code
            words = ", ".join(f"{t}: baseline {d['baseline']:.4f}, now {d['now']:.4f}" for t, d in sorted(r["drift"].items()))
            print(f"DRIFT {r['id']:<{width}} meets its expect_verdict on the baseline shares ({words}); "
                  f"`rag.py eval --write-shares` takes the new ones")
        if over:
            for r in (r for r in res["rows"] if r["noted"]):
                print(f"NOTED {r['id']:<{width}} carries a check: or route: line though expected good")
            print(f"noted={res['noted']} is above NOTED_BASELINE={NOTED_BASELINE}: a pack note now fires on an answered "
                  "question; fix the note, or raise the constant with the reason")
        if failing:
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
        if logs := format_logs(kbfacts.show_logs(kbfacts.qpath_of(full), start, end - 1)):
            print(logs)


if __name__ == "__main__":
    try:
        main()
    except kbcommon.RootError as e:  # a malformed ROOT_FILE, or two roots sharing a name or an id prefix
        sys.exit(f"error: {e}")
