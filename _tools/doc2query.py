#!/usr/bin/env python3
"""Doc2query pilot: expand fact units with generated questions to close vocabulary gaps in pack (stdlib only).

Document expansion: a model writes a few questions each fact answers; the questions' words are indexed with the
fact at a low weight, so a question worded differently from the fact still finds it. Retrieval stays deterministic;
the model runs only when facts are written or changed. Filtered as in Doc2Query-- (a generated question is kept only
if pack, without expansion, already places it in its fact's article), so hallucinated questions do not pollute the
index.

  doc2query.py split [--seed 7] [--n 12] [--exclude ARMS.json ...]
                                              choose the pilot and control articles (stratified by domain), write
                                              kb/public/_retrieval/doc2query/arms.json; --exclude leaves out the articles of earlier
                                              rounds' arms files, so a confirmation round tests fresh articles
  doc2query.py batch ARM|--path PREFIX [--out FILE]
                                              the facts of an arm (pilot or control), or under a path prefix (an
                                              article to regenerate), as JSON [{key, path, line, text}]: the input for
                                              question generation or for blind test questions
  doc2query.py ingest GENERATED.json          filter generated [{key, questions: [...]}] and write the kept ones to
                                              kb/public/_retrieval/doc2query/expansions.csv (key,question); prints kept/dropped
  doc2query.py evaluate QUESTIONS.json        blind test questions [{key, question}] per arm: fact line in pack with
                                              expansion off and on, verdicts, plus the eval set and the off-kb set
  doc2query.py stale                          expansion keys whose fact no longer exists (text changed or removed),
                                              in every root; exit 1 when there are any
  doc2query.py prune                          delete the stale keys' rows from each root's expansions.csv

--root NAME (before the command): the root whose facts and doc2query data (DATA_DIR/doc2query/) a command works on;
default: the public root for split, batch, ingest and evaluate, every root for stale and prune. arms.json names
articles by their path inside the root.

A key is the first 12 hex digits of sha256 over the fact text with whitespace collapsed: stable when lines move,
new when the text changes. kbfacts.pack reads expansions.csv when it exists and KB_DOC2QUERY is not "0".
"""
import argparse, collections, csv, json, os, random, sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import kbcommon  # noqa: E402

HOME = kbcommon.HOME  # this repository: arms files of earlier rounds are recorded relative to it
ROOT = DIR = ARMS = EXPANSIONS = None


def use_root(name=None):
    """Work on root `name` (default public): its facts and its doc2query data (arms, expansions, off-kb questions)."""
    global ROOT, DIR, ARMS, EXPANSIONS
    ROOT = kbcommon.root(name) if name else kbcommon.public()
    DIR = os.path.join(ROOT.path, kbcommon.DATA_DIR, "doc2query")
    ARMS = os.path.join(DIR, "arms.json")
    EXPANSIONS = os.path.join(DIR, "expansions.csv")


def bare(qpath):
    import kbfacts
    return kbfacts.bare(qpath)


def key_of(text):
    import kbfacts
    return kbfacts.fact_key(text)


def facts(paths=None):
    """The tagged article facts of ROOT (paths qualified); `paths` narrows them to these paths inside the root."""
    import kbfacts
    return [u for u in kbfacts.units(ROOT.name) if u["tags"] and u["path"].endswith(".md")
            and (paths is None or bare(u["path"]) in paths)]


def split(seed, n, exclude=()):
    """n pilot and n control articles, alternating within each domain so both arms span the same domains."""
    import kbfacts
    used = set()
    for path in exclude:
        with open(path, encoding="utf-8") as f:
            prev = json.load(f)
        used |= set(prev.get("pilot", [])) | set(prev.get("control", []))
    by = collections.defaultdict(list)
    counts = collections.Counter(bare(u["path"]) for u in facts())
    for q in sorted(kbfacts.articles()):
        rel = bare(q)
        if kbfacts.root_name(q) == ROOT.name and counts[rel] >= 8 and rel not in used:  # enough facts, not used before
            by[rel.split("/")[0]].append(rel)
    rng = random.Random(seed)
    doms = sorted(by)
    rng.shuffle(doms)
    arms = {"pilot": [], "control": []}
    for d in doms:
        arts = by[d][:]
        rng.shuffle(arts)
        for a, arm in zip(arts[:2], ("pilot", "control")):
            if len(arms[arm]) < n:
                arms[arm].append(a)
    os.makedirs(DIR, exist_ok=True)
    with open(ARMS, "w", encoding="utf-8") as f:
        json.dump({"seed": seed, "excluded": sorted(os.path.relpath(p, HOME) for p in exclude), **arms}, f, indent=1)
    for arm, arts in arms.items():
        print(f"{arm}: {len(arts)} articles, {sum(counts[a] for a in arts)} facts")
    return arms


def load_arms():
    with open(ARMS, encoding="utf-8") as f:
        return json.load(f)


def batch(arm=None, prefix=None):
    import kbfacts
    if prefix:
        us = [u for u in facts() if kbfacts.in_prefix(u["path"], prefix)]
    else:
        us = facts(set(load_arms()[arm]))
    return [{"key": key_of(u["text"]), "path": u["path"], "line": u["line"], "text": u["text"]} for u in us]


def load_expansions():
    """{key: [question, ...]} from expansions.csv, or {} when it does not exist."""
    out = collections.defaultdict(list)
    if os.path.exists(EXPANSIONS):
        with open(EXPANSIONS, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                out[r["key"]].append(r["question"])
    return dict(out)


def ingest(path):
    """Doc2Query-- style filter: keep a generated question only if pack without expansion puts its fact's article
    among the pack's articles (relevant to the fact, not hallucinated); drop duplicates."""
    os.environ["KB_DOC2QUERY"] = "0"
    import kbfacts
    by_key = {key_of(u["text"]): u for u in facts()}
    with open(path, encoding="utf-8") as f:
        gen = json.load(f)
    kept, dropped, unknown = [], 0, 0
    old = load_expansions()
    for g in gen:
        u = by_key.get(g["key"])
        if not u:
            unknown += 1
            continue
        seen = {q.lower() for q in old.get(g["key"], [])}
        for q in g.get("questions", []):
            q = " ".join(str(q).split())
            if not q or q.lower() in seen:
                continue
            seen.add(q.lower())
            if u["path"] in kbfacts.pack(q)["paths"]:
                kept.append((g["key"], q))
            else:
                dropped += 1
    new = not os.path.exists(EXPANSIONS)
    with open(EXPANSIONS, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        if new:
            w.writerow(["key", "question"])
        w.writerows(kept)
    print(f"kept={len(kept)} dropped={dropped} (pack does not reach the fact's article) unknown_keys={unknown}")


def evaluate(path):
    """Blind questions per arm: is the fact's line in the pack, with expansion off and on?"""
    import importlib
    arms = load_arms()
    with open(path, encoding="utf-8") as f:
        qs = json.load(f)
    neg = os.path.join(DIR, "offkb_questions.txt")
    results = {}
    for mode in ("0", "1"):
        os.environ["KB_DOC2QUERY"] = mode
        import kbfacts, rag
        importlib.reload(kbfacts)
        importlib.reload(rag)
        units = {key_of(u["text"]): u for u in facts()}
        res = collections.defaultdict(collections.Counter)
        for q in qs:
            u = units.get(q["key"])
            if not u:
                continue
            rel = bare(u["path"])
            arm = "pilot" if rel in arms["pilot"] else "control" if rel in arms["control"] else "other"
            p = kbfacts.pack(q["question"])
            c = res[arm]
            c["n"] += 1
            c["line"] += f"{u['path']}:{u['line']} " in p["text"]
            c["article"] += u["path"] in p["paths"]
            c[p["verdict"]] += 1
        ev = rag.run_eval(os.path.join(ROOT.path, kbcommon.DATA_DIR, "lookup_eval.csv"))
        negv = collections.Counter(kbfacts.pack(q)["verdict"] for q in open(neg, encoding="utf-8").read().splitlines() if q.strip()) \
            if os.path.exists(neg) else collections.Counter()
        results[mode] = (res, ev, negv)
    for mode, (res, ev, negv) in results.items():
        print(f"== expansion {'on' if mode == '1' else 'off'}")
        for arm, c in sorted(res.items()):
            n = c["n"]
            print(f"  {arm:8} n={n:3}  line={c['line'] / n:5.0%}  article={c['article'] / n:5.0%}  "
                  f"good={c['good'] / n:4.0%} weak={c['weak'] / n:4.0%} none={c['none'] / n:4.0%}")
        print(f"  eval {ev['passed']}/{ev['n']} mean_chars={ev['mean_chars']}; off-kb verdicts {dict(negv)}")


def stale_keys():
    """ROOT's expansion keys whose fact no longer exists in ROOT."""
    live = {key_of(u["text"]) for u in facts()}
    return sorted(set(load_expansions()) - live)


def each_root(name):
    """The roots stale and prune cover: `name`, else every root."""
    return [name] if name else [r.name for r in kbcommon.roots()]


def stale(name=None):
    gone, many = [], len(each_root(name)) > 1
    for n in each_root(name):
        use_root(n)
        gone += [f"{n}: {k}" if many else k for k in stale_keys()]
    print("\n".join(gone) + (f"\nstale={len(gone)}: python3 _tools/doc2query.py prune removes them" if gone else "stale=0"))
    return 1 if gone else 0


def prune(name=None):
    total = pruned = 0
    for n in each_root(name):
        use_root(n)
        gone = set(stale_keys())
        if not gone:
            continue
        with open(EXPANSIONS, encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        keep = [rows[0]] + [r for r in rows[1:] if r and r[0] not in gone]
        with open(EXPANSIONS, "w", encoding="utf-8", newline="") as f:
            f.write(kbcommon.rows_text(keep))
        total, pruned = total + len(gone), pruned + len(rows) - len(keep)
    print(f"pruned {pruned} rows of {total} stale keys" if total else "stale=0: nothing to prune")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", help="the root to work on (default: public; stale and prune: every root)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("split"); s.add_argument("--seed", type=int, default=7); s.add_argument("--n", type=int, default=12)
    s.add_argument("--exclude", nargs="*", default=[], help="arms files of earlier rounds whose articles are left out")
    b = sub.add_parser("batch"); b.add_argument("arm", nargs="?", choices=["pilot", "control"])
    b.add_argument("--path", help="facts under this path prefix instead of an arm (e.g. auth/kerberos)"); b.add_argument("--out")
    i = sub.add_parser("ingest"); i.add_argument("file")
    e = sub.add_parser("evaluate"); e.add_argument("file")
    sub.add_parser("stale")
    sub.add_parser("prune")
    a = ap.parse_args()
    if a.root and a.root not in {r.name for r in kbcommon.roots()}:
        sys.exit(f"no root {a.root!r}")
    use_root(a.root)
    if a.cmd == "split":
        split(a.seed, a.n, a.exclude)
    elif a.cmd == "batch":
        if not a.arm and not a.path:
            sys.exit("batch: give an arm (pilot, control) or --path PREFIX")
        out = json.dumps(batch(a.arm, a.path), indent=1, ensure_ascii=False)
        if a.out:
            with open(a.out, "w", encoding="utf-8") as f:
                f.write(out)
            print(f"wrote {a.out}")
        else:
            print(out)
    elif a.cmd == "ingest":
        ingest(a.file)
    elif a.cmd == "evaluate":
        evaluate(a.file)
    elif a.cmd == "prune":
        sys.exit(prune(a.root))
    else:
        sys.exit(stale(a.root))


if __name__ == "__main__":
    main()
