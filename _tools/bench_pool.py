"""The benchmarks' question pool: a stratified, checked set of questions built from the kb's own sources (stdlib only).

`benchmarks.py pool build` writes kb/public/_retrieval/bench_pool.csv, `pool build --querylog` writes the query-log
pool under kb/_querylog/bench/, and `pool check` reads either back (kb/_self/tools.md, benchmarks.py pool). Every row
has at least one check regex, a kind the report groups by and the route a pack should take. The held-out rows name
lookup_heldout.csv rows by id and hold no question text: `question_of` reads it at run time. The only paid step is one
Sonnet call that writes the answer regexes of the eval rows, through bench_retrieval's blind-question call; a rebuild
reuses the regexes of the file it replaces, so it asks nothing. This module imports bench_core and bench_retrieval and
no facade (kb/_self/code.md, Layout and Imports).
"""
import csv, hashlib, json, os, random, re, tempfile
from pathlib import Path

from bench_core import HOME, SPEND
from bench_retrieval import numbered, sonnet_json

SEED = 11
COLUMNS = ["id", "kind", "domain", "phrasing", "source", "question", "checks", "expected_route"]
ROUTES = ("good", "web", "split", "tool", "none")
PUBLIC_FILE = "kb/public/_retrieval/bench_pool.csv"
QUERYLOG_FILE = "kb/_querylog/bench/pool.csv"
EVAL_KINDS = ("fact", "csv_fact", "multi", "synthesis")  # the kinds the 40 eval rows fall into
VARIANT_KINDS = ("variant_keyword", "variant_sentence", "variant_typo")
PLAN = {"heldout": 20, "offkb": 15, "false_good": 2, "near_miss": 3, "gap": 5, "count": 3, "cites": 3, "decision": 2,
        "conflict": 2, "snippet": 5, **{k: 10 for k in VARIANT_KINDS}}
EVAL_ROWS = 40  # sampled from lookup_eval.csv, stratified by domain
QUERYLOG_ROWS = 20
NONE_CHECK = r"(?i)(not cover|doesn.t cover|does not cover|no coverage|not in the kb|kb lacks|isn.t in|none)"
GAP_CHECK = r"(?i)(not (confirmed|documented|covered|in the kb)|unknown|unconfirmed|kb lacks|live docs)"
SENTENCE = ("I need to know this for a task today: ", "Please explain, in full sentences: ")
STOP = set("the and for are was what which how does did that this with from have has can you your into when where why "
           "not but any all use used using about there their they them then than over under between each per via "
           "should would could will may might must".split())
EVAL_FILE = "kb/public/_retrieval/lookup_eval.csv"
HELDOUT_FILE = "kb/public/_retrieval/lookup_heldout.csv"
OFFKB_FILE = "kb/public/_retrieval/doc2query/offkb_questions.txt"
SOURCE_ID = re.compile(r"(?<![\w-])(S-[a-z0-9]{8}|S\d+)(?![\w-])")
BRAND = re.compile(r"\b(?:[A-Z]{2,}[A-Za-z0-9]*|[A-Z][a-z0-9]+[A-Z][A-Za-z0-9]*)\b")
REGEX_ASK = ("For each numbered item below (a question, then the fact line of the kb that answers it), write one regular "
             "expression (Python re, case-insensitive) that a correct answer to the question matches because it states "
             "the fact's own value: a number, a name, a setting, a cmdlet. Do not build it from the question's words. "
             'Reply with only a JSON array: [{"i": 0, "regex": "..."}, ...].\n\n')


class PoolError(Exception):
    """A pool that cannot be built: a source short of rows, a missing file."""


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def read_lines(path):
    return [ln.strip() for ln in Path(path).read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")]


def write_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def rng_for(seed, label):
    """One generator per pool section, so a source that gains a row moves no other section's sample."""
    return random.Random(f"{seed}:{label}")


def row(kind, domain, phrasing, source, question, checks, route):
    key = hashlib.sha1(f"{kind}|{source}|{phrasing}".encode("utf-8")).hexdigest()[:8]
    return {"id": f"BP-{key}", "kind": kind, "domain": domain, "phrasing": phrasing, "source": source,
            "question": question, "checks": json.dumps(checks, ensure_ascii=False), "expected_route": route}


def words(text):
    return [w for w in re.findall(r"[a-z0-9]{3,}", text.lower()) if w not in STOP]


def esc_path(rel):
    return re.escape(rel)


def domain_of(rel):
    return rel.split("/", 1)[0] if "/" in rel else rel


# ------------------------------------------------------------------------------------------------------ eval rows

def fact_for(home, case):
    """(path, line number, text) of the line of the case's expected articles that shares most words with its question,
    or None under two shared words."""
    q = set(words(case["question"]))
    best = None
    for rel in [p for p in case["expect_paths"].split(";") if p][:2]:
        path = Path(home) / "kb" / "public" / rel
        if not path.is_file():
            continue
        for n, ln in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if ln.startswith(("#", "---")) or not ln.strip():
                continue
            score = len(q & set(words(ln)))
            if score >= 2 and (best is None or score > best[0]):
                best = (score, rel, n, ln.strip())
    return best[1:] if best else None


def eval_kind(case):
    paths = [p for p in case["expect_paths"].split(";") if p]
    if paths[0].endswith(".csv"):
        return "csv_fact"
    if len(paths) > 1:
        return "multi" if len({domain_of(p) for p in paths}) == 1 else "synthesis"
    return "fact"


def stratified(cases, n, rng):
    """`n` cases spread over the domains round-robin, each domain's order drawn by `rng`."""
    groups = {}
    for c in cases:
        groups.setdefault(domain_of(c["expect_paths"].split(";")[0]), []).append(c)
    for dom in sorted(groups):
        rng.shuffle(groups[dom])
    out = []
    while len(out) < n and any(groups.values()):
        for dom in sorted(groups):
            if groups[dom] and len(out) < n:
                out.append(groups[dom].pop())
    return out


def fallback_check(path):
    """The check when the model's regex is unusable: the answer cites the article the fact line is in."""
    return esc_path(path)


def usable(rx, fact):
    """A model's regex that compiles, matches no empty answer and matches the fact it was written from."""
    try:
        return bool(rx) and len(rx) <= 160 and not re.search(rx, "", re.I) and bool(re.search(rx, fact, re.I))
    except re.error:
        return False


def sonnet_regexes(items):
    """The paid call: one tool-less Sonnet reply with a regex per item (question and fact line), [""] for a miss."""
    scratch = Path(os.environ.get("BENCH_SCRATCH") or Path(tempfile.gettempdir()) / "it-ops-kb-bench")
    scratch.mkdir(parents=True, exist_ok=True)
    got, cost = sonnet_json(REGEX_ASK + numbered([f"QUESTION: {i['question']}\nFACT ({i['where']}): {i['fact']}" for i in items]),
                            scratch)
    out = [""] * len(items)
    for r in got:
        if isinstance(r, dict) and r.get("i") in range(len(items)) and isinstance(r.get("regex"), str):
            out[r["i"]] = r["regex"]
    print(f"pool: Sonnet wrote {sum(1 for x in out if x)} of {len(items)} regexes, ${cost:.3f}")
    return out


def cached_checks(out):
    """{source: checks} of the rows of the file a rebuild replaces: the regexes a paid call wrote once."""
    path = Path(out)
    if not path.is_file():
        return {}
    return {r["source"]: json.loads(r["checks"]) for r in read_csv(path)
            if r["source"].startswith("lookup_eval.csv:") and r["checks"]}


def eval_section(home, seed, ask, out):
    """(eval rows, their variants, the near-miss rows built on eval questions), one `ask` call for the checks."""
    cases = []
    for c in sorted(read_csv(Path(home) / EVAL_FILE), key=lambda c: c["id"]):
        if c["expect_verdict"] == "good" and c["expect_paths"]:
            fact = fact_for(home, c)
            if fact:
                cases.append({**c, "fact": fact})
    picked = stratified(cases, EVAL_ROWS, rng_for(seed, "eval"))
    near = []
    for brand in ("cmpivot", "bitlocker"):
        base = next((c for c in cases if brand in c["question"].lower()), None)
        if base:
            near.append((brand, base))
    ask_for = picked + [b for _, b in near if b not in picked]
    have = cached_checks(out)
    todo = [c for c in ask_for if f"lookup_eval.csv:{c['id']}" not in have]
    got = {}
    if todo:
        regexes = ask([{"question": c["question"], "where": f"{c['fact'][0]}:{c['fact'][1]}", "fact": c["fact"][2]}
                       for c in todo])
        for c, rx in zip(todo, regexes):
            got[f"lookup_eval.csv:{c['id']}"] = [rx if usable(rx, c["fact"][2]) else fallback_check(c["fact"][0])]
    checks = {**have, **got}

    def chk(c):
        return checks.get(f"lookup_eval.csv:{c['id']}", [])
    rows = [row(eval_kind(c), domain_of(c["expect_paths"].split(";")[0]), "original", f"lookup_eval.csv:{c['id']}",
                c["question"], chk(c), "good") for c in picked]
    rng = rng_for(seed, "variants")
    pool = picked[:]
    rng.shuffle(pool)
    seen, bases = set(), []
    for c in pool:  # ten bases, a new domain first
        dom = domain_of(c["expect_paths"].split(";")[0])
        if dom not in seen and len(bases) < PLAN["variant_keyword"]:
            seen.add(dom)
            bases.append(c)
    bases += [c for c in pool if c not in bases][:PLAN["variant_keyword"] - len(bases)]
    variants = []
    for c in sorted(bases, key=lambda c: c["id"]):
        dom, src = domain_of(c["expect_paths"].split(";")[0]), f"lookup_eval.csv:{c['id']}"
        for kind, phrasing, q in (("variant_keyword", "keyword", keyword_form(c["question"])),
                                  ("variant_sentence", "sentence", sentence_form(c["question"])),
                                  ("variant_typo", "typo", typo_form(c["question"], rng))):
            variants.append(row(kind, dom, phrasing, src, q, chk(c), "good"))
    misses = [row("near_miss", domain_of(b["expect_paths"].split(";")[0]), "lowercase brand", f"lookup_eval.csv:{b['id']}",
                  re.sub(brand, brand, b["question"], flags=re.I), chk(b), "good") for brand, b in near]
    return rows, variants, misses


def keyword_form(question):
    seen = []
    for w in words(question):
        if w not in seen:
            seen.append(w)
    return " ".join(seen[:8])


def sentence_form(question):
    lead = SENTENCE[0] if question.rstrip().endswith("?") else SENTENCE[1]
    return lead + question


def typo_form(question, rng):
    """The question with its brand-like words lowercased, else with two adjacent letters of its longest word swapped."""
    low = BRAND.sub(lambda m: m.group(0).lower(), question)
    if low != question:
        return low
    long = max(re.findall(r"[A-Za-z]{5,}", question) or [""], key=len)
    if not long:
        return question
    i = rng.randrange(1, len(long) - 2)
    return question.replace(long, long[:i] + long[i + 1] + long[i] + long[i + 2:], 1)


# -------------------------------------------------------------------------------------------- other public sources

def heldout_section(home, seed):
    """Rows that name held-out cases by id: no question, the expected articles as the checks."""
    cases = sorted(read_csv(Path(home) / HELDOUT_FILE), key=lambda c: c["id"])
    cases = rng_for(seed, "heldout").sample(cases, min(PLAN["heldout"], len(cases)))
    return [row("heldout", domain_of(c["expect_paths"].split(";")[0]), "held-out", f"lookup_heldout.csv:{c['id']}", "",
                [esc_path(p) for p in c["expect_paths"].split(";") if p], "good")
            for c in sorted(cases, key=lambda c: c["id"]) if c["expect_paths"]]


def offkb_section(home, seed):
    qs = sorted(read_lines(Path(home) / OFFKB_FILE))
    qs = rng_for(seed, "offkb").sample(qs, min(PLAN["offkb"], len(qs)))
    return [row("offkb", "offkb", "original", "offkb_questions.txt#" + hashlib.sha1(q.encode("utf-8")).hexdigest()[:8], q,
                [NONE_CHECK], "none") for q in sorted(qs)]


def design_section():
    """The verdict design misses: two false goods (the pack said good, the kb lacks it) from agent_bench's scenarios."""
    from agent_bench import S
    out = []
    for kind, scen, route in (("false_good", "s6_falsegood", "web"), ("false_good", "s8_falsegood2", "web")):
        q, checks = S[scen]
        out.append(row(kind, "design", "original", f"agent_bench.py:{scen}", q, checks, route))
    q, checks = S["h2_applock"]
    out.append(row("near_miss", "sqlserver", "original", "agent_bench.py:h2_applock", q, checks, "split"))
    return out


def gap_section(home, seed):
    """Open entries of the gaps ledger (tagged UNK, with no Resolved or Superseded line under them), asked as topics."""
    lines = (Path(home) / "kb" / "public" / "_gaps.md").read_text(encoding="utf-8").splitlines()
    entries, cur = [], None
    for ln in lines:
        if ln.startswith("- **"):
            cur = [ln]
            entries.append(cur)
        elif cur is not None and ln.startswith("  ") and ln.strip():
            cur.append(ln)
        else:
            cur = None
    open_gaps = []
    for e in entries:
        text = " ".join(x.strip() for x in e)
        m = re.match(r"- \*\*(.+?)\*\*", e[0])
        if not m or "[UNK" not in text or re.search(r"- (Resolved|Superseded)", text) or m.group(1).startswith(("Closed", "Resolved")):
            continue
        title = re.sub(r"^(Still open|Narrowed, not closed):\s*", "", m.group(1)).strip(" .:*")
        topic = re.search(r"\(topic: ([\w./-]+)\)", text)
        if 12 <= len(title) <= 160:
            open_gaps.append((title, domain_of(topic.group(1)) if topic else "gaps"))
    picked = rng_for(seed, "gap").sample(sorted(set(open_gaps)), min(PLAN["gap"], len(set(open_gaps))))
    return [row("gap", dom, "original", "_gaps.md#" + hashlib.sha1(t.encode("utf-8")).hexdigest()[:8],
                f"What does the kb say about {t[0].lower() + t[1:]}?", [GAP_CHECK], "web") for t, dom in sorted(picked)]


def articles_of(home):
    """{path relative to kb/public: text} of the articles (a front matter with a topic)."""
    base = Path(home) / "kb" / "public"
    out = {}
    for p in sorted(base.rglob("*.md")):
        rel = p.relative_to(base).as_posix()
        if not p.name.startswith("_") and not rel.startswith("_"):
            text = p.read_text(encoding="utf-8")
            if text.startswith("---\n") and "\ntopic:" in text.split("\n---", 2)[0]:
                out[rel] = text
    return out


def tool_section(home, seed):
    """Questions a tool answers by counting or joining: articles per domain, who cites a source, a decision, a conflict."""
    base = Path(home) / "kb" / "public"
    arts = articles_of(home)
    out = []
    per = {}
    for rel in arts:
        per[domain_of(rel)] = per.get(domain_of(rel), 0) + 1
    doms = sorted(d for d, n in per.items() if n >= 2)
    for d in sorted(rng_for(seed, "count").sample(doms, min(PLAN["count"], len(doms)))):
        out.append(row("count", d, "original", f"articles:{d}", f"How many articles does the kb hold in the {d} domain?",
                       [rf"\b{per[d]}\b"], "tool"))
    known = {r["id"] for r in read_csv(base / "_sources.csv")}
    cites = {}
    for rel, text in arts.items():
        for sid in set(SOURCE_ID.findall(text)):
            if sid in known:
                cites.setdefault(sid, []).append(rel)
    ids = sorted(s for s, v in cites.items() if len(v) <= 3)
    for sid in sorted(rng_for(seed, "cites").sample(ids, min(PLAN["cites"], len(ids)))):
        out.append(row("cites", domain_of(cites[sid][0]), "original", f"source:{sid}", f"Which kb articles cite source {sid}?",
                       [esc_path(p) for p in sorted(cites[sid])], "tool"))
    decisions = []
    for p in sorted((Path(home) / "kb").glob("*/_decisions.csv")):
        decisions += [(p.parent.name, d) for d in read_csv(p) if d.get("status") == "active" and d.get("by")]
    picks = rng_for(seed, "decision").sample(decisions, min(PLAN["decision"], len(decisions)))
    for root, d in sorted(picks, key=lambda x: x[1]["id"]):
        longest = max(re.findall(r"[A-Za-z]{5,}", d["text"]) or ["decided"], key=len)
        out.append(row("decision", root.lstrip("_"), "original", f"decision:{d['id']}",
                       f"What does the kb record for decision {d['id']}?", [re.escape(d["by"]), "(?i)" + re.escape(longest)], "tool"))
    out += conflict_rows(home, seed)
    return out


def conflict_rows(home, seed):
    text = (Path(home) / "kb" / "public" / "_conflicts.md").read_text(encoding="utf-8")
    found, area = [], ""
    for block in re.split(r"(?m)^(?=#{2,3} )", text):
        head = block.splitlines()[0] if block.strip() else ""
        if head.startswith("## "):
            area = head[3:].strip()
        elif head.startswith("### ") and not head[4:].startswith("Resolved"):
            ids = sorted(set(SOURCE_ID.findall(block)))
            if len(ids) >= 2:
                found.append((head[4:].strip().rstrip("."), domain_of(area.replace("-", "/")), ids[:2]))
    picks = rng_for(seed, "conflict").sample(found, min(PLAN["conflict"], len(found)))
    return [row("conflict", dom, "original", "_conflicts.md#" + hashlib.sha1(t.encode("utf-8")).hexdigest()[:8],
                f"Which sources disagree on: {t}?", [re.escape(i) for i in ids], "tool") for t, dom, ids in sorted(picks)]


def snippet_section(home, seed):
    found = []
    for rel, text in articles_of(home).items():
        for n, ln in enumerate(text.splitlines(), 1):
            if ln.startswith("- SNIPPET:"):
                toks = list(dict.fromkeys(re.findall(r"`([^`\s]{3,})`", ln.split(" [", 1)[0])))[:2]
                desc = ln[len("- SNIPPET:"):].split(";", 1)[0].strip().replace("`", "")
                if toks and desc:
                    found.append((rel, n, desc, toks))
    picks = rng_for(seed, "snippet").sample(found, min(PLAN["snippet"], len(found)))
    return [row("snippet", domain_of(rel), "original", f"{rel}:{n}", f"Show a working example: {desc}",
                [re.escape(t) for t in toks], "good") for rel, n, desc, toks in sorted(picks)]


# ------------------------------------------------------------------------------------------------ build and check

def build_public(home=HOME, seed=SEED, ask=sonnet_regexes, out=None):
    """The public pool's rows, in the order of the kinds, or a PoolError naming a kind short of rows."""
    out = Path(out or Path(home) / PUBLIC_FILE)
    ev, variants, near = eval_section(home, seed, ask, out)
    design = design_section()
    rows = (ev + heldout_section(home, seed) + offkb_section(home, seed) + design[:2] + near + design[2:]
            + gap_section(home, seed) + tool_section(home, seed) + snippet_section(home, seed) + variants)
    problems = count_problems(rows)
    if problems:
        raise PoolError("; ".join(problems))
    return rows


def count_problems(rows):
    got = {}
    for r in rows:
        got[r["kind"]] = got.get(r["kind"], 0) + 1
    want = {**PLAN, "eval": EVAL_ROWS}
    got["eval"] = sum(got.pop(k, 0) for k in EVAL_KINDS)
    return [f"kind {k}: {got.get(k, 0)} rows, the plan has {n}" for k, n in want.items() if got.get(k, 0) != n]


def build_querylog(home=HOME, seed=SEED):
    """Redacted questions of the distilled store (redact.py over each, the leak scan clean), with the article a pack
    cited as the check. A none verdict is left out: the kb may answer it by now, and no article can be named."""
    import redact
    import ql_store
    k = redact.known(Path(home) / "kb" / "public")
    seen, cand = set(), []
    for _, e in sorted(ql_store.store_entries(Path(home) / "kb" / "_querylog"), key=lambda x: x[1]["id"]):
        q = e.get("question")
        if not isinstance(q, str) or not 20 <= len(q) <= 300 or "\n" in q or q.startswith("Research queue gap"):
            continue
        verdict = e.get("verdict")
        arts = [a.split("/", 1)[1] for a in ([e["best"]] if e.get("best") else e.get("articles") or []) if "/" in a]
        if verdict not in ("good", "weak") or not arts:
            continue
        checks, route, dom = [esc_path(arts[0])], "good" if verdict == "good" else "split", domain_of(arts[0])
        text = redact.finish(redact.redact(q, k), k)
        if text and text not in seen:
            seen.add(text)
            cand.append(row("querylog", dom, "original", "querylog:" + e["id"][:8], text, checks, route))
    picks = rng_for(seed, "querylog").sample(cand, min(QUERYLOG_ROWS, len(cand)))
    if len(picks) != QUERYLOG_ROWS:
        raise PoolError(f"the store holds {len(picks)} usable questions, the plan has {QUERYLOG_ROWS}")
    return sorted(picks, key=lambda r: r["id"])


def question_of(r, home=HOME):
    """A row's question: its own, else (a held-out row) the text of the case it names, read now."""
    if r["question"] or r["kind"] != "heldout":
        return r["question"]
    case_id = r["source"].split(":", 1)[1]
    return next(c["question"] for c in read_csv(Path(home) / HELDOUT_FILE) if c["id"] == case_id)


def check_problems(rows, home=HOME, querylog=False):
    """One line per defect of a pool file's rows: a check missing or not a regex, a held-out row with text, a leak."""
    out = []
    ids = set()
    heldout = {c["id"]: c["question"] for c in read_csv(Path(home) / HELDOUT_FILE)} if (Path(home) / HELDOUT_FILE).is_file() else {}
    held_text = {re.sub(r"\W+", " ", q.lower()).strip() for q in heldout.values()}
    for r in rows:
        where = r.get("id", "?")
        if list(r) != COLUMNS:
            out.append(f"{where}: columns are not {','.join(COLUMNS)}")
            continue
        if r["id"] in ids:
            out.append(f"{where}: id twice")
        ids.add(r["id"])
        if r["expected_route"] not in ROUTES:
            out.append(f"{where}: route {r['expected_route']!r} is not one of {', '.join(ROUTES)}")
        try:
            checks = json.loads(r["checks"])
            if not (isinstance(checks, list) and checks and all(isinstance(c, str) and c for c in checks)):
                raise ValueError("no regex")
            for c in checks:
                re.compile(c)
        except (ValueError, re.error) as e:
            out.append(f"{where}: checks are not a list of regexes ({e})")
        if r["kind"] == "heldout":
            case_id = r["source"].split(":", 1)[-1]
            if r["question"] or case_id not in heldout:
                out.append(f"{where}: a held-out row holds no question and names a case of lookup_heldout.csv")
        elif not querylog and re.sub(r"\W+", " ", r["question"].lower()).strip() in held_text:
            out.append(f"{where}: its question is a held-out question")
        elif not r["question"]:
            out.append(f"{where}: no question")
    if querylog:
        import redact
        k = redact.known(Path(home) / "kb" / "public")
        out += [f"{r['id']}: leak scan {kind}" for r in rows for kind, _ in redact.scan(r["question"], k)]
        if len(rows) != QUERYLOG_ROWS:
            out.append(f"{len(rows)} rows, the plan has {QUERYLOG_ROWS}")
    else:
        out += count_problems(rows)
        out += [f"{r['id']}: query-log text in a public file" for r in rows if r["kind"] == "querylog"]
    return out


def cli(a, home=HOME):
    """`pool build` and `pool check`; the argparse namespace comes from benchmarks.py."""
    if a.pool_cmd == "build":
        out = Path(a.out) if a.out else Path(home) / (QUERYLOG_FILE if a.querylog else PUBLIC_FILE)
        try:
            rows = build_querylog(home, a.seed) if a.querylog else build_public(home, a.seed, out=out)
        except PoolError as e:
            print(f"pool build: {e}")
            return 1
        write_csv(out, rows)
        counts = {}
        for r in rows:
            counts[r["kind"]] = counts.get(r["kind"], 0) + 1
        print(f"pool build: {len(rows)} rows to {out}: " + ", ".join(f"{k} {n}" for k, n in sorted(counts.items())))
        if SPEND["runs"]:
            print(f"pool build: {SPEND['runs']} paid run, ${SPEND['usd']:.3f}")
        return 0
    path = Path(a.file) if a.file else Path(home) / (QUERYLOG_FILE if a.querylog else PUBLIC_FILE)
    if not path.is_file():
        print(f"pool check: {path} does not exist")
        return 1
    problems = check_problems(read_csv(path), home, a.querylog)
    for p in problems:
        print(f"pool check: {p}")
    return 1 if problems else 0
