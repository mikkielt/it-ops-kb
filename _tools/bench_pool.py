"""The benchmarks' question pool: a stratified, checked set of questions built from the kb's own sources, and the
`pool` scenario that runs it over the kb, router, hook and web arms (stdlib only).

`benchmarks.py pool build` writes kb/public/_retrieval/bench_pool.csv, `pool build --querylog` writes the query-log
pool under kb/_querylog/bench/, and `pool check` reads either back (kb/_self/tools.md, benchmarks.py pool). Every row
has at least one check regex, a kind the report groups by and the route a pack should take. The held-out rows name
lookup_heldout.csv rows by id and hold no question text: `question_of` reads it at run time. The only paid step is one
Sonnet call that writes the answer regexes of the eval rows, through bench_retrieval's blind-question call; a rebuild
reuses the regexes of the file it replaces, so it asks nothing. `benchmarks.py run pool` is `s_pool` (the arms, the
effort levels, the per-run record and the per-cell figures, described in kb/_self/reports/benchmarks.md); its
`--shape session` runs the rows in groups of six, one `claude -p` session per group. This module
imports agent_bench, bench_core and bench_retrieval and no facade (kb/_self/code.md, Layout and Imports).
"""
import csv, hashlib, json, os, random, re, shutil, subprocess, sys, tempfile, time, uuid
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

import agent_bench
from bench_core import (HOME, PRICE, RAW, RESULTS, SPEND, Skip, est_cost, no_plugin_env, prompt_tokens, read_rows,
                        resolve_model, run_tokens, spent_run, spent_usd, usage_sum)
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


# ------------------------------------------------------------------------------------------------------ the scenario

KB_ARMS = ("haiku-5-5", "haiku-4-5", "sonnet-5-5")  # agent_bench configs: the models pinned by id, with the kb's tools
NO_EFFORT = ("haiku-4-5",)  # Claude Code sets no effort level for Haiku 4.5: its arm runs once, at its only level
WEB_ARMS = ("web-haiku-5-5", "web-sonnet-5-5")
ARMS = (*KB_ARMS, "router", "hook", *WEB_ARMS)
EFFORTS = ("low", "default")  # `default` passes no --effort: the level the model starts with
WEB_KINDS = (*EVAL_KINDS, "offkb", "snippet", "false_good")  # the kinds a web search can answer; the web arms run these
WEB_ASK = " Cite the source urls."
HOOK_TIMEOUT_S = 120
ROUTER_TIMEOUT_S = 1800
SHAPES = ("fresh", "session")  # a fresh session per question, or six questions in one session
SESSION_ARMS = ("haiku-5-5", "sonnet-5-5")  # the arms of the session shape: the kb's tools, models pinned by id
GROUP_SIZE = 6
SESSION_SUFFIX = "/session"  # an arm label of the session shape: `model:level/session`, beside the fresh label


def load_pool(home=HOME, kinds=None):
    """The rows of the public pool file and, when it exists, the query-log file, each with its question text read
    (`question_of`), only the kinds in `kinds` when given."""
    rows = []
    for rel in (PUBLIC_FILE, QUERYLOG_FILE):
        if (Path(home) / rel).is_file():
            rows += read_csv(Path(home) / rel)
    return [{**r, "question": question_of(r, home)} for r in rows if not kinds or r["kind"] in kinds]


def plan_cells(arms, efforts):
    """[(arm, effort, label)] to run: a kb arm once per effort level (Haiku 4.5 once), every other arm at its default."""
    out = []
    for arm in arms:
        if arm in KB_ARMS and arm not in NO_EFFORT:
            out += [(arm, e, f"{arm}:{e}") for e in efforts]
        else:
            out.append((arm, "default", arm))
    return out


def accepts(arm, kind):
    return arm not in WEB_ARMS or kind in WEB_KINDS


def record_of(row, arm, label, r, cc=""):
    """One run's record: the pool row's id and kind, the arm and its label, the tokens (run_tokens, priced as the arm's
    alias resolves on Claude Code version `cc` when the transcript names no model), the kb results' tokens
    (`pack_tokens`: those of the stream plus the router's pack text at CHARS_PER_TOKEN), tool calls, turns, seconds,
    cost and one boolean per check; or the error."""
    base = {"id": row["id"], "kind": row["kind"], "arm": arm, "label": label}
    if "error" in r:
        return {**base, "error": str(r["error"])[:200]}
    t = run_tokens(r, agent_bench.MODEL.get(arm.removeprefix("web-"), ""), cc)
    checks = [bool(agent_bench.check(c, r)) for c in json.loads(row["checks"])]
    return {**base, **t, "model": "+".join(sorted(set(t.pop("models")))),
            "pack_tokens": r.get("kb_tokens", 0) + r.get("pack_chars", 0) // agent_bench.CHARS_PER_TOKEN,
            "tool_calls": sum(r.get("tools", {}).values()) + sum(r.get("sub_tools", {}).values()),
            "turns": r.get("turns", 0), "wall_s": r.get("wall_s", 0), "cost": r.get("cost", 0), "checks": checks}


def cell_metrics(rs):
    """[(metric, value)] of one cell's good runs: the means of the token fields, tool calls, turns, seconds and cost, the
    checks passed over all, the runs whose checks all passed, `fixed_share` (the mean first prompt over the mean input)
    and `tokens_per_right` (the effective input of all the runs over the runs that were right, left out when none was)."""
    n = len(rs)
    mean = lambda k: sum(r[k] for r in rs) / n  # noqa: E731
    right = sum(bool(r["checks"]) and all(r["checks"]) for r in rs)
    out = [(k, mean(k)) for k in ("input", "cache_read", "cache_write", "effective_input", "out", "start_ctx",
                                  "pack_tokens", "tool_calls", "turns", "wall_s", "cost")]
    out.append(("checks", f"{sum(sum(r['checks']) for r in rs)}/{sum(len(r['checks']) for r in rs)}"))
    out.append(("fully_right", f"{right} of {n}"))
    if mean("input"):
        out.append(("fixed_share", mean("start_ctx") / mean("input")))
    if right:
        out.append(("tokens_per_right", sum(r["effective_input"] for r in rs) / right))
    return out


def cell_rows(runs):
    """[(case, label, metric, value, runs, model, note)] of the results rows: per arm label, one cell for each kind and
    one for all kinds (`all`); a cell with failed runs also has an `errors` row."""
    out = []
    labels = list(dict.fromkeys(r["label"] for r in runs))
    for label in labels:
        mine = [r for r in runs if r["label"] == label]
        for case in [*dict.fromkeys(r["kind"] for r in mine), "all"]:
            rs = [r for r in mine if case == "all" or r["kind"] == case]
            ok = [r for r in rs if "error" not in r]
            if len(ok) < len(rs):
                out.append((case, label, "errors", len(rs) - len(ok), len(rs), "", rs[0].get("error", "")[:80] if not ok else ""))
            if not ok:
                continue
            model = Counter(r["model"] for r in ok).most_common(1)[0][0]
            tier = max(r["tier"] for r in ok)
            for metric, value in cell_metrics(ok):
                note = (f"highest price tier {tier}" if tier and metric == "effective_input" else
                        "no effort setting: one level" if metric == "checks" and ok[0]["arm"] in NO_EFFORT else "")
                out.append((case, label, metric, value, len(ok), model, note))
    return out


def run_tasks(tasks, work, jobs=1, cap=None, emit=None):
    """([result of each task started], [the tasks not started]): `work(task)` runs up to `jobs` at once, each task started
    in list order; `emit(i, task, result)` sees the results in list order, on the calling thread, whatever order the
    runs finish in. With `cap` (US dollars), no task is started once the spend of finished runs (bench_core.spent_usd,
    since the call began) has reached it; the runs in flight finish."""
    base = spent_usd()
    done, flight, nxt, emitted = {}, {}, 0, 0
    with ThreadPoolExecutor(max_workers=max(1, jobs)) as ex:
        while True:
            while nxt < len(tasks) and len(flight) < jobs and not (cap is not None and spent_usd() - base >= cap):
                flight[ex.submit(work, tasks[nxt])] = nxt
                nxt += 1
            if not flight:
                break
            for f in wait(flight, return_when=FIRST_COMPLETED)[0]:
                done[flight.pop(f)] = f.result()
            while emitted in done:
                if emit:
                    emit(emitted, tasks[emitted], done[emitted])
                emitted += 1
    return [done[i] for i in range(nxt)], tasks[nxt:]


def run_pool(rows, cells, reps, runner, sink=None, jobs=1, cap=None, left=None, cc=""):
    """Every row on every cell (a web arm only on WEB_KINDS), `reps` times: the run records, in cell order whatever order
    `jobs` parallel runs finish in. `runner(arm, effort, row)` is one run's result; `sink(record, result)` sees each as it
    is made, in that order. With `cap` (run_tasks), `left` is extended with (label, "id#rep") of each run not started.
    `cc` is the run's Claude Code version, which record_of prices an alias arm by."""
    tasks = [(arm, effort, label, row, rep) for arm, effort, label in cells for row in rows if accepts(arm, row["kind"])
             for rep in range(1, reps + 1)]
    runs = []

    def emit(i, t, r):
        runs.append(record_of(t[3], t[0], t[2], r, cc))
        if sink:
            sink(runs[-1], r)
    _, rest = run_tasks(tasks, lambda t: runner(t[0], t[1], t[3]), jobs, cap, emit)
    if left is not None:
        left += [(t[2], f"{t[3]['id']}#{t[4]}") for t in rest]
    for _, _, label in cells:
        n = sum(t[2] == label for t in tasks)
        print(f"pool: {label}: {n} runs, {sum('error' in x for x in runs if x['label'] == label)} failed"
              + (f", {sum(t[2] == label for t in rest)} not started" if rest else ""), flush=True)
    return runs


def session_groups(rows, seed=SEED, size=GROUP_SIZE):
    """([groups of `size` rows], [rows left out]). The rows are shuffled by their own generator (`seed`), and a group
    takes rows of different kinds first, then any, never two of one `source` (a base question and its variants name the
    same fact). The rows that cannot fill a last group are left out."""
    pending = sorted(rows, key=lambda r: r["id"])
    rng_for(seed, "session").shuffle(pending)
    groups = []
    while len(pending) >= size:
        group = []
        for distinct_kind in (True, False):
            for r in list(pending):
                if (len(group) < size and r["source"] not in {g["source"] for g in group}
                        and not (distinct_kind and r["kind"] in {g["kind"] for g in group})):
                    group.append(r)
                    pending.remove(r)
        if len(group) < size:
            return groups, pending + group
        groups.append(group)
    return groups, pending


def session_fields(r, before):
    """The fields a session run adds to its record: `marginal_input`, the whole prompt of the run's last request less
    `before`, the last prompt of the question before it (0 for the first question: all of its prompt is new), and
    `cache_read_share`, the run's cache reads over its input; and that last prompt, for the next question."""
    last = prompt_tokens(r["requests"][-1]["usage"]) if r.get("requests") else before
    inp = r["in_uncached"] + r["cache_write"] + r["cache_read"]
    out = {"marginal_input": last - before}
    if inp:
        out["cache_read_share"] = r["cache_read"] / inp
    return out, last


def run_sessions(groups, cells, reps, runner, sink=None, jobs=1, cap=None, left=None, cc=""):
    """Every group on every cell, `reps` times, each in one session of its own: the run records in cell order, with the
    arm label `SESSION_SUFFIX` added, the group's number, the question's `position` and the `session_fields`.
    `runner(arm, effort, row, sid, position)` is one question's result: the first starts the session `sid`, each later
    one resumes it. A failed question ends its session: the questions after it are recorded as errors. Up to `jobs`
    sessions run at once (a session's questions stay in order inside it), the records come in the order `jobs` 1 gives,
    and `cap`, `left` and `cc` work as in run_pool, a session being the unit started or not (the name `group N#rep`)."""
    tasks = [(arm, effort, label + SESSION_SUFFIX, number, group, rep) for arm, effort, label in cells
             for number, group in enumerate(groups, 1) for rep in range(1, reps + 1)]

    def session(t):
        arm, effort, _, _, group, _ = t
        sid, got, ended = str(uuid.uuid4()), [], 0
        for position, row in enumerate(group, 1):
            r = {"error": f"the session ended at position {ended}"} if ended else runner(arm, effort, row, sid, position)
            if "error" in r:
                ended = ended or position
            got.append(r)
        return got
    runs = []

    def emit(i, t, results):
        before = 0
        for position, (row, r) in enumerate(zip(t[4], results), 1):
            rec = {**record_of(row, t[0], t[2], r, cc), "group": t[3], "position": position}
            if "error" not in r:
                extra, before = session_fields(r, before)
                rec.update(extra)
            runs.append(rec)
            if sink:
                sink(rec, r)
    _, rest = run_tasks(tasks, session, jobs, cap, emit)
    if left is not None:
        left += [(t[2], f"group {t[3]}#{t[5]}") for t in rest]
    for _, _, label in cells:
        label += SESSION_SUFFIX
        n = sum(t[2] == label for t in tasks)
        print(f"pool: {label}: {n * len(groups[0])} runs, {sum('error' in x for x in runs if x['label'] == label)} failed"
              + (f", {sum(t[2] == label for t in rest)} sessions not started" if rest else ""), flush=True)
    return runs


def session_rows(runs):
    """[(case, label, metric, value, runs, model, note)] of the session shape: per arm label and position (case
    `position N`), the means of `marginal_input`, the pooled `cache_read_share` (cache reads over input of the position's
    runs) and the checks passed over all; a position with failed runs also has an `errors` row."""
    out = []
    for label in dict.fromkeys(r["label"] for r in runs):
        mine = [r for r in runs if r["label"] == label]
        for position in sorted({r["position"] for r in mine}):
            rs = [r for r in mine if r["position"] == position]
            ok = [r for r in rs if "error" not in r]
            case = f"position {position}"
            if len(ok) < len(rs):
                out.append((case, label, "errors", len(rs) - len(ok), len(rs), "", rs[0].get("error", "")[:80] if not ok else ""))
            if not ok:
                continue
            model = Counter(r["model"] for r in ok).most_common(1)[0][0]
            note = "the whole prompt: no request before it" if position == 1 else ""
            out.append((case, label, "marginal_input", sum(r["marginal_input"] for r in ok) / len(ok), len(ok), model, note))
            inp = sum(r["input"] for r in ok)
            if inp:
                out.append((case, label, "cache_read_share", sum(r["cache_read"] for r in ok) / inp, len(ok), model, ""))
            out.append((case, label, "checks", f"{sum(sum(r['checks']) for r in ok)}/{sum(len(r['checks']) for r in ok)}",
                        len(ok), model, ""))
    return out


def hook_result(stdout, wall):
    """The run of the `kb:` hook: its block reason or context as the answer, no model tokens."""
    try:
        out = json.loads(stdout) if stdout.strip() else {}
    except ValueError:
        return {"error": "the hook printed no JSON: " + stdout[-200:]}
    text = out.get("reason") or (out.get("hookSpecificOutput") or {}).get("additionalContext") or ""
    return {"wall_s": round(wall, 3), "cost": 0, "turns": 0, "in_uncached": 0, "cache_write": 0, "cache_read": 0, "out": 0,
            "tools": {}, "sub_tools": {}, "requests": [], "kb_tokens": 0, "answer": text}


def hook_run(sh, clone, question, env):
    """The `kb:` hook as the query log's hook scenarios start it (`sh _tools/kbpy _tools/kb_hook.py`, the prompt event on
    stdin), in the throwaway clone."""
    event = json.dumps({"hook_event_name": "UserPromptSubmit", "session_id": "bench-pool", "prompt": "kb: " + question,
                        "cwd": str(clone)})
    t = time.perf_counter()
    try:
        p = subprocess.run([sh, str(clone / "_tools" / "kbpy"), "_tools/kb_hook.py"], cwd=str(clone), input=event,
                           capture_output=True, text=True, encoding="utf-8", env=env, timeout=HOOK_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return {"error": f"the hook took over {HOOK_TIMEOUT_S} s"}
    return hook_result(p.stdout, time.perf_counter() - t)


def router_run(clone, question, env):
    """kb_ask.py's routing with the routed models pinned (agent_bench `--route`), run from the throwaway clone."""
    try:
        p = subprocess.run([sys.executable, str(clone / "_tools" / "agent_bench.py"), "--route", question], cwd=str(clone),
                           capture_output=True, text=True, encoding="utf-8", env=env, timeout=ROUTER_TIMEOUT_S)
        return json.loads(p.stdout.strip().splitlines()[-1])
    except (subprocess.TimeoutExpired, ValueError, IndexError) as e:
        return {"error": f"the router run failed: {type(e).__name__}"}


def live_runner(b, sh):
    """The runner of a paid run: a kb arm is `claude -p` in the lookup clone (kb server registered, hooks off) with
    --effort for a non-default level, a web arm the bare web session of agent_bench in an empty directory, the router and
    the hook run from the clone. A paid run is counted in the run's spend."""
    clone, env = b.lookup(), no_plugin_env()
    empty = b.scratch / "pool-web"
    empty.mkdir(parents=True, exist_ok=True)

    def run(arm, effort, row):
        q = row["question"]
        if arm == "hook":
            return hook_run(sh, clone, q, env)
        if arm == "router":
            r = router_run(clone, q, env)
        elif arm in WEB_ARMS:
            r = agent_bench.execute(agent_bench.web_argv(agent_bench.MODEL[arm.removeprefix("web-")]), q + WEB_ASK,
                                    cwd=str(empty), env=env, clean=True)
        else:
            r = agent_bench.execute(agent_bench.kb_argv(arm) + effort_args(arm, effort), q, cwd=str(clone), env=env, clean=True)
        spent_run(r)
        return r
    return run


def effort_args(arm, effort):
    return ["--effort", effort] if effort != "default" and arm not in NO_EFFORT else []


def session_argv(arm, effort, sid, position):
    """The kb arm's command for one question of a session: the first question starts the session `sid` (`--session-id`,
    the session kept), a later one resumes it (`--resume`), both with the arm's effort. The session flag sits before
    the variadic `--allowedTools` list."""
    argv = [a for a in agent_bench.kb_argv(arm) if a != "--no-session-persistence"]
    return argv[:2] + ["--session-id" if position == 1 else "--resume", sid] + argv[2:] + effort_args(arm, effort)


def live_session_runner(b):
    """The runner of a paid session run: `claude -p` in the lookup clone (kb server registered, hooks off) per question,
    the follow-ups resuming the first question's session in the same directory. A resumed run's result event reports
    the session's running total cost, so a question's cost is that total less the question before it's; the spend
    counts the question's own cost."""
    clone, env = b.lookup(), no_plugin_env()
    total = {}  # session id: the running cost its last question's result event reported

    def run(arm, effort, row, sid, position):
        r = agent_bench.execute(session_argv(arm, effort, sid, position), row["question"], cwd=str(clone), env=env, clean=True)
        if "error" not in r:
            before = total.get(sid, 0.0) if position > 1 else 0.0
            total[sid] = r.get("cost") or 0.0
            r["cost"] = total[sid] - before
        spent_run(r)
        return r
    return run


def s_pool(b):
    """The question pool over the arms of `b.arms` (default ARMS) at the effort levels of `b.efforts`, on the kinds of
    `b.kinds` (default all), `b.reps` runs of each row on each cell. Shape `fresh` (default) makes each run a fresh
    session; shape `session` (`b.shape`) runs groups of six rows (`session_groups`, seed `b.seed`) each in one session on
    the kb arms of SESSION_ARMS, and records per position (`session_rows`) beside the per-kind rows of its arm labels.
    Rows per kind and arm label, and for all kinds (cell_rows); each run's record is appended to the scenario's runs
    file. With `b.dry` it prints the plan and starts nothing."""
    session = getattr(b, "shape", "fresh") == "session"
    arms = list(getattr(b, "arms", None) or (SESSION_ARMS if session else ARMS))
    sh = shutil.which("sh")
    if "hook" in arms and not sh:
        print("pool: the hook arm needs sh on PATH (Windows: run it from Git Bash); left out")
        arms.remove("hook")
    cells = plan_cells(arms, getattr(b, "efforts", None) or EFFORTS)
    rows = load_pool(HOME, getattr(b, "kinds", None))
    if not rows:
        raise Skip("no pool rows: python3 _tools/benchmarks.py pool build, or the --kinds list matches none")
    groups, left = session_groups(rows, getattr(b, "seed", SEED)) if session else ([], [])
    if session and not groups:
        raise Skip(f"{len(rows)} rows make no group of {GROUP_SIZE}")
    runs_of = (lambda arm: len(groups) * GROUP_SIZE * b.reps) if session else (  # noqa: E731
        lambda arm: sum(accepts(arm, r["kind"]) for r in rows) * b.reps)
    total = sum(runs_of(a) for a, _, _ in cells)
    jobs, cap, cc = max(1, getattr(b, "jobs", 1)), getattr(b, "max_usd", None), getattr(b, "cc", "")
    if getattr(b, "dry", False):
        for arm, _, label in cells:
            print(f"pool: {label}{SESSION_SUFFIX if session else ''}: {runs_of(arm)} runs")
        what = (f"{len(groups)} groups of {GROUP_SIZE} ({len(left)} rows left out), {len(cells) * len(groups) * b.reps} sessions"
                if session else f"{len(rows)} rows")
        usd = estimate_lines(cells, runs_of, SESSION_SUFFIX if session else "", read_rows(RESULTS), jobs, cap)
        raise Skip(f"dry run: {what}, {len(cells)} cells, {total} runs, no model started; estimated spend ${usd:.2f}")

    def sink(rec, r):
        if RAW.get("path"):
            with open(RAW["path"], "a", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps({**rec, "answer": (r.get("answer") or "")[:2000]}) + "\n")
    not_started = []
    if session:
        runs = run_sessions(groups, cells, b.reps, live_session_runner(b), sink, jobs, cap, not_started, cc)
        for case, label, metric, value, n, model, note in session_rows(runs):
            b.row("pool", case, label, metric, value, n, model, note)
    else:
        runs = run_pool(rows, cells, b.reps, live_runner(b, sh), sink, jobs, cap, not_started, cc)
    for case, label, metric, value, n, model, note in cell_rows(runs):
        b.row("pool", case, label, metric, value, n, model, note)
    for label in dict.fromkeys(label for label, _ in not_started):
        names = [name for lab, name in not_started if lab == label]
        b.row("pool", "not started", label, "spend_stopped", len(names), len(names), note=", ".join(names))
    if not_started:
        b.status = 1
        print(f"pool: stopped at the --max-usd cap of ${cap:.2f} with {len(not_started)} runs "
              f"({'sessions' if session else 'runs'}) not started; the rows `spend_stopped` name them", flush=True)


# ------------------------------------------------------------------------------------------------ the spend estimate

# one run when the results hold no earlier pool record of its arm: about the mean of a Sonnet 5.5 lookup with the kb tools
# (the `new-model` record of 2026-09-28: 90,140 input, 1,161 output), the input split as a run mostly reads its cache
DEFAULT_RUN = {"uncached": 2_000, "cache_write": 8_000, "cache_read": 80_000, "out": 1_200}
NO_MODEL_ARMS = ("hook",)  # no model: costs nothing


def assumed_run(label, arm, history):
    """(the figures of one run of arm label `label`, the pinned model that prices it, where they come from): the means of
    the label's `all` cell in the newest earlier record of the results `history` when that record holds them, else
    DEFAULT_RUN (none for the hook arm) priced as the arm's model (the router as sonnet-5-5)."""
    mine = [r for r in history if r["scenario"] == "pool" and r["arm"] == label and r["case"] == "all"]
    if mine:
        record = max(r["record"] for r in mine)
        got = {r["metric"]: r for r in mine if r["record"] == record}
        if all(m in got for m in ("input", "cache_read", "cache_write", "out")):
            v = {m: float(got[m]["value"]) for m in ("input", "cache_read", "cache_write", "out")}
            model = got["input"]["model"]
            return ({"uncached": v["input"] - v["cache_read"] - v["cache_write"], "cache_write": v["cache_write"],
                     "cache_read": v["cache_read"], "out": v["out"]},
                    model if model in PRICE else "claude-sonnet-5-5",
                    f"the means of the record {record}")
    model = resolve_model(agent_bench.MODEL.get(arm.removeprefix("web-"), "claude-sonnet-5-5"))
    return ({k: 0 for k in DEFAULT_RUN} if arm in NO_MODEL_ARMS else dict(DEFAULT_RUN)), model, "the default"


def run_usd(tokens, model):
    """The list-price cost of one run of `tokens` ({uncached, cache_write, cache_read, out}) as a single request of `model`."""
    usage = {"input_tokens": tokens["uncached"], "cache_creation_input_tokens": tokens["cache_write"],
             "cache_read_input_tokens": tokens["cache_read"], "output_tokens": tokens["out"]}
    return est_cost(usage_sum([{"model": model, "usage": usage}], model))


def estimate_lines(cells, runs_of, suffix, history, jobs, cap):
    """Print one line per cell with its expected spend, then the total; return the total in US dollars. An estimate, not a
    measurement: each run is priced (bench_core.PRICE, single request) at the tokens `assumed_run` states for its cell,
    web searches are not included, and the real spend depends on the runs."""
    total = 0.0
    for arm, _, label in cells:
        tokens, model, basis = assumed_run(label + suffix, arm, history)
        usd = runs_of(arm) * run_usd(tokens, model)
        total += usd
        print(f"pool: {label}{suffix}: estimate ${usd:.2f} for {runs_of(arm)} runs at {"no model" if arm in NO_MODEL_ARMS else model}: per run uncached "
              f"{tokens['uncached']:,.0f}, cache write {tokens['cache_write']:,.0f}, cache read {tokens['cache_read']:,.0f}, "
              f"output {tokens['out']:,.0f} tokens ({basis})")
    print(f"pool: estimate ${total:.2f} in all at --jobs {jobs}: an estimate from the per-run token figures above and "
          "bench_core's list prices (web searches left out), not a measurement")
    if cap is not None and total > cap:
        print(f"pool: the estimate is over --max-usd ${cap:.2f}: a run would stop before the last runs start")
    return total
