#!/usr/bin/env python3
"""Doc2query pilot: expand fact units with generated questions to close vocabulary gaps in pack (stdlib only).

Document expansion: a model writes a few questions each fact answers; the questions' words are indexed with the
fact at a low weight, so a question worded differently from the fact still finds it. Retrieval stays deterministic;
the model runs only when facts are written or changed. Filtered as in Doc2Query-- (a generated question is kept only
if pack, without expansion, already places it in its fact's article), so hallucinated questions do not pollute the
index.

  doc2query.py split [--seed 7] [--n 12]      choose the pilot and control articles (stratified by domain), write
                                              _tools/doc2query/arms.json
  doc2query.py batch ARM [--out FILE]         the facts of an arm (pilot or control) as JSON [{key, path, line, text}]:
                                              the input for question generation or for blind test questions
  doc2query.py ingest GENERATED.json          filter generated [{key, questions: [...]}] and write the kept ones to
                                              _tools/doc2query/expansions.csv (key,question); prints kept/dropped
  doc2query.py evaluate QUESTIONS.json        blind test questions [{key, question}] per arm: fact line in pack with
                                              expansion off and on, verdicts, plus the eval set and the off-kb set
  doc2query.py stale                          expansion keys whose fact no longer exists (text changed or removed)

A key is the first 12 hex digits of sha256 over the fact text with whitespace collapsed: stable when lines move,
new when the text changes. kbfacts.pack reads expansions.csv when it exists and KB_DOC2QUERY is not "0".
"""
import argparse, collections, csv, json, os, random, sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
KB = os.path.dirname(TOOLS)
DIR = os.path.join(TOOLS, "doc2query")
ARMS = os.path.join(DIR, "arms.json")
EXPANSIONS = os.path.join(DIR, "expansions.csv")
sys.path.insert(0, TOOLS)


def key_of(text):
    import kbfacts
    return kbfacts.fact_key(text)


def facts(paths=None):
    import kbfacts
    return [u for u in kbfacts.units() if u["tags"] and u["path"].endswith(".md") and (paths is None or u["path"] in paths)]


def split(seed, n):
    """n pilot and n control articles, alternating within each domain so both arms span the same domains."""
    import kbfacts
    by = collections.defaultdict(list)
    counts = collections.Counter(u["path"] for u in facts())
    for rel in sorted(kbfacts.articles()):
        if counts[rel] >= 8:  # enough facts to test
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
        json.dump({"seed": seed, **arms}, f, indent=1)
    for arm, arts in arms.items():
        print(f"{arm}: {len(arts)} articles, {sum(counts[a] for a in arts)} facts")
    return arms


def load_arms():
    with open(ARMS, encoding="utf-8") as f:
        return json.load(f)


def batch(arm):
    return [{"key": key_of(u["text"]), "path": u["path"], "line": u["line"], "text": u["text"]}
            for u in facts(set(load_arms()[arm]))]


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
            arm = "pilot" if u["path"] in arms["pilot"] else "control" if u["path"] in arms["control"] else "other"
            p = kbfacts.pack(q["question"])
            c = res[arm]
            c["n"] += 1
            c["line"] += f"{u['path']}:{u['line']} " in p["text"]
            c["article"] += u["path"] in p["paths"]
            c[p["verdict"]] += 1
        ev = rag.run_eval(os.path.join("_tools", "lookup_eval.csv"))
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


def stale():
    live = {key_of(u["text"]) for u in facts()}
    gone = sorted(set(load_expansions()) - live)
    print("\n".join(gone) + (f"\nstale={len(gone)}" if gone else "stale=0"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("split"); s.add_argument("--seed", type=int, default=7); s.add_argument("--n", type=int, default=12)
    b = sub.add_parser("batch"); b.add_argument("arm", choices=["pilot", "control"]); b.add_argument("--out")
    i = sub.add_parser("ingest"); i.add_argument("file")
    e = sub.add_parser("evaluate"); e.add_argument("file")
    sub.add_parser("stale")
    a = ap.parse_args()
    if a.cmd == "split":
        split(a.seed, a.n)
    elif a.cmd == "batch":
        out = json.dumps(batch(a.arm), indent=1, ensure_ascii=False)
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
    else:
        stale()


if __name__ == "__main__":
    main()
