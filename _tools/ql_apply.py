"""The query log's apply (kb/_self/querylog.md, Apply): accepted findings become changes in this clone's working
tree, never committed here (`apply --push` commits them in its worktree). Each open eval finding's row is written
together with its alias or expansion fix when the kb gates pass; an open gap candidate the pack still reproduces
under an article becomes a `_gaps.md` entry; then opt-in research (ql_research). One findings file records each
outcome.
"""
import csv, datetime, re, sys
from pathlib import Path

from ql_base import HOME, one_line, places, restore, run_cmd, write_text
from ql_learn import passes, unknown_words
from ql_research import add_under, research_one
from ql_store import (APPLY_STATES, FIX_KINDS, failed_counts, finding_states, store_entries, write_findings)

FAILED_RETRIES = 0  # times a finding recorded apply-failed is applied again: never
ALIAS_CANDIDATES = 3  # canonical words tried per alias finding: the article's file-name words, then its title's
EXPANSION_CANDIDATES = 3  # facts of the article tried per expansion finding, most words shared with the question first
CSV_HEADERS = {"eval": ["id", "question", "expect_paths", "expect_verdict", "allow_weak"],
               "aliases": ["term", "canonical"], "expansions": ["key", "question"]}


class Gate:
    """pack and the kb gates on the working tree of this clone: `rag.py eval`, the off-kb verdicts, the pack size,
    and where a fix, a gap entry or a researched fact goes."""

    @staticmethod
    def fresh():
        import kbfacts
        kbfacts._FP[:] = [0.0, None]  # a file was just written: the next call fingerprints the kb again

    def pack(self, question):
        import kbfacts
        self.fresh()
        return kbfacts.pack(question, fmt="concise")

    def measure(self):
        """{n, passed, failed, chars {eval id: pack characters}, offkb_good} on the working tree."""
        import kbcommon, kbfacts, rag
        self.fresh()
        res = rag.run_eval()
        good = 0
        for r in kbcommon.roots():
            p = Path(r.path) / kbcommon.DATA_DIR / "doc2query" / "offkb_questions.txt"
            if p.is_file():
                qs = [q for q in p.read_text(encoding="utf-8").splitlines() if q.strip()]
                good += sum(kbfacts.pack(q, fmt="concise")["verdict"] == "good" for q in qs)
        return {"n": res["n"], "passed": res["passed"], "failed": [r["id"] for r in res["rows"] if not r["ok"]],
                "chars": {r["id"]: r["chars"] for r in res["rows"]}, "offkb_good": good}

    def targets(self, article):
        """The files a fix for `article` writes: its root's eval set and expansions, and the aliases (the shared
        _tools/aliases.csv for the public root, a root's own _retrieval/aliases.csv otherwise)."""
        import kbcommon, kbfacts
        r = self.root(article)
        data = Path(r.path) / kbcommon.DATA_DIR
        return {"root": r.name, "eval": data / "lookup_eval.csv", "expansions": data / "doc2query" / "expansions.csv",
                "aliases": Path(kbfacts.ALIASES) if r.name == kbcommon.public().name else data / "aliases.csv"}

    def alias_terms(self):
        """{term: canonical} of every alias file."""
        import kbfacts
        out = {}
        for p in kbfacts.alias_files():
            with open(p, encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    t = " ".join((row.get("term") or "").lower().split())
                    if t:
                        out.setdefault(t, (row.get("canonical") or "").strip().lower())
        return out

    def facts(self, article):
        """[(line, text)] of the tagged facts of `article`."""
        import kbfacts
        return [(u["line"], u["text"]) for u in kbfacts.units(article) if u["path"] == article and u["tags"]]

    def title(self, article):
        import kbfacts
        return (kbfacts.articles().get(article) or {}).get("title", "")

    def article_of(self, path):
        """The qualified article (.md) whose topic holds the qualified `path` (the article itself, a same-stem data
        file or a file its `files:` lists), or None."""
        import kbfacts
        arts = kbfacts.articles()
        if path in arts:
            return path
        for topic, files in sorted(kbfacts.topic_files().items()):
            if path in files:
                return next((q for q in files if q in arts and arts[q].get("topic") == topic), None)
        return None

    def topic(self, article):
        """The topic of a qualified article, as its root's ledgers name it: `<domain>/<slug>`."""
        import kbfacts
        return kbfacts.bare((kbfacts.articles().get(article) or {}).get("topic") or article[:-3])

    def root(self, article):
        import kbcommon, kbfacts
        return kbcommon.root(kbfacts.root_name(article) or kbcommon.public().name)

    def ledger(self, article, name):
        """A file of the article's root: `_gaps.md`, `_conflicts.md`, `_sources.csv`."""
        return Path(self.root(article).path) / name

    def file(self, article):
        import kbcommon
        return Path(kbcommon.path_of(article))

    def id_prefix(self, article):
        return self.root(article).id_prefix

    def research_files(self, article):
        """Every file research may write for `article`, so a failed gate can put each back: the article, its root's
        sources, conflicts and the coverage files build_index regenerates."""
        return [self.file(article)] + [self.ledger(article, n) for n in ("_sources.csv", "_conflicts.md",
                                                                          "_coverage.csv", "_coverage.md")]

    def index_and_check(self):
        """build_index.py, then check.py over every root: the ERROR lines when check.py does not end errors=0."""
        tools = HOME / "_tools"
        code, o, e = run_cmd([sys.executable, str(tools / "build_index.py")], cwd=HOME)
        if code:
            return [one_line(f"build_index.py exit {code}: {(o + e).strip()[-200:]}", 240)]
        code, o, e = run_cmd([sys.executable, str(tools / "check.py")], cwd=HOME)
        m = re.search(r"errors=(\d+)", o)
        if code == 0 and m and m.group(1) == "0":
            return []
        errs = [one_line(ln, 200) for ln in o.splitlines() if ln.startswith("ERROR")]
        return errs[:6] or [one_line(f"check.py exit {code}: {(o + e).strip()[-200:]}", 240)]


def csv_rows(path):
    if not Path(path).is_file():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.reader(f))[1:]


def append_rows(path, which, rows):
    """Append `rows` to the CSV at `path` (its header first when the file is new); the file's bytes before, or None."""
    import kbcommon
    path = Path(path)
    old = path.read_bytes() if path.is_file() else None
    text = old.decode("utf-8") if old is not None else kbcommon.rows_text([CSV_HEADERS[which]])
    if text and not text.endswith("\n"):
        text += "\n"
    write_text(path, text + kbcommon.rows_text(rows))
    return old


# ---------------------------------------------------------------- eval rows with their fixes

def alias_problems(terms, canonical, existing, unknown):
    """Why aliasing `terms` to `canonical` collides with an existing term: a term already in an alias file, or a
    word the kb holds (not among the question's `unknown` words); and a canonical word another product owns."""
    out = []
    for t in terms:
        if t in existing:
            out.append(f"alias {t}: already a term of {existing[t]}")
        elif t not in unknown:
            out.append(f"alias {t}: a word the kb holds")
    if existing.get(canonical, canonical) != canonical:
        out.append(f"alias {canonical}: a term of {existing[canonical]}")
    return out


def alias_fixes(finding, entry, gate, res):
    """[(rows by file, problems)] per candidate canonical word: the words of the article's file name, then of its
    title, each mapped to its alias group when it is a term of one, else a new group of its own."""
    import kbfacts
    article = finding["article"]
    existing = gate.alias_terms()
    unknown = unknown_words(entry["question"], res)
    stem = Path(kbfacts.bare(article)).stem
    words = []
    for w in kbfacts.WORD.findall(stem.replace("-", " ") + " " + gate.title(article)):
        w = w.lower()
        c = existing.get(w, w)
        if w not in kbfacts.STOP and len(w) > 2 and not w.isdigit() and c not in words:
            words.append(c)
    out = []
    for c in words[:ALIAS_CANDIDATES]:
        rows = [[t, c] for t in finding.get("terms") or []]
        if c not in existing:
            rows.append([c, c])
        out.append(({"aliases": rows}, alias_problems(finding.get("terms") or [], c, existing, unknown)))
    return out


def expansion_fixes(finding, entry, gate):
    """[(rows by file, [])] per candidate fact: the article's facts sharing the most words with the question."""
    import kbfacts
    q = set(kbfacts.terms(entry["question"]))
    facts = sorted(gate.facts(finding["article"]), key=lambda f: (-len(q & set(kbfacts.terms(f[1]))), f[0]))
    return [({"expansions": [[kbfacts.fact_key(text), entry["question"]]]}, [])
            for _, text in facts[:EXPANSION_CANDIDATES]]


def try_fix(fix, eval_row, targets, gate, base):
    """Write the fix and the eval row, then hold the kb gates against `base`: every eval question passes, the pack of
    the questions `base` measured does not grow on average, off-kb `good` does not rise. (ok, problems); the files
    are put back unless ok."""
    saved = {}
    for which, rows in [*fix.items(), ("eval", [eval_row])]:
        have = {tuple(r) for r in csv_rows(targets[which])}
        rows = [r for r in rows if tuple(r) not in have]
        if rows:
            p = targets[which]
            old = append_rows(p, which, rows)
            saved.setdefault(p, old)
    m = gate.measure()
    problems = []
    if m["passed"] != m["n"]:
        problems.append(f"eval fails: {', '.join(m['failed'][:3])}")
    ids = [i for i in base["chars"] if i in m["chars"]]
    before = sum(base["chars"][i] for i in ids) / max(len(ids), 1)
    after = sum(m["chars"][i] for i in ids) / max(len(ids), 1)
    if after > before:
        problems.append(f"mean pack grows: {before:.0f} -> {after:.0f} characters")
    if m["offkb_good"] > base["offkb_good"]:
        problems.append(f"off-kb good rises: {base['offkb_good']} -> {m['offkb_good']}")
    if problems:
        restore(saved)
        gate.fresh()
    return not problems, problems


def without_observed(r):
    return {k: v for k, v in r.items() if k != "observed"}


def apply_one(ev, fix, entry, gate, base):
    """The records of one open eval finding and its fix finding (or None): the eval row with the first candidate fix
    that passes the gates (both `applied`), else the miss promoted to a gap candidate (`no-fix`) and its fix
    `rejected`. [] when the question passes on the working tree already (learn records that)."""
    import kbid
    question, article = entry["question"], ev["expect"]
    res = gate.pack(question)
    if passes(res, article):
        return []
    targets = gate.targets(article)
    bare_path = article.split("/", 1)[1] if article.startswith(targets["root"] + "/") else article
    eid = kbid.eval_id(question)
    taken = {r[0]: r[1] for r in csv_rows(targets["eval"]) if len(r) > 1}
    problems = []
    if eid in taken and taken[eid] != question:
        problems.append(f"eval id {eid} is taken by another question")
    elif fix is None:
        problems.append("no fix finding")
    else:
        cands = alias_fixes(fix, entry, gate, res) if fix["kind"] == "alias" else expansion_fixes(fix, entry, gate)
        if not cands:
            problems.append(f"no candidate {fix['kind']}")
        row = [eid, question, bare_path, "good", ""]
        for rows, why in cands:
            if why:
                problems += why
                continue
            ok, why = try_fix(rows, row, targets, gate, base)
            if ok:
                return [{**without_observed(ev), "state": "applied", "observed": {"eval": eid}},
                        {**without_observed(fix), "state": "applied",
                         "observed": {"rows": sum(len(v) for v in rows.values())}}]
            problems += why
    promoted = {**without_observed(ev), "state": "no-fix", "stage": "candidate-gap",
                "promotions": [*(ev.get("promotions") or []), {"from": ev.get("stage", "miss"), "to": "candidate-gap",
                                                               "by": "apply"}],
                "observed": {"gate": sorted(set(problems))[:6]}}
    out = [promoted]
    if fix is not None:
        out.append({**without_observed(fix), "state": "rejected", "observed": {"gate": sorted(set(problems))[:6]}})
    return out


# ---------------------------------------------------------------- the gap step

def gap_one(g, entry, gate, day):
    """The record of one open gap candidate (kind gap, stage candidate-gap), re-run with pack on the working tree: it
    reproduces when it still fails (`passes` without a best article), and it lies in a kb domain when the pack's lead
    path belongs to an article (a `none` verdict is off the kb's domains). Then a _gaps.md entry under the article's
    topic, in the article's root, dated `day`, and the finding promoted from candidate-gap to gap (`applied`). []
    when it passes now (learn records that) or lies outside the kb's domains (it stays a candidate)."""
    res = gate.pack(entry["question"])
    if passes(res, None) or res.get("verdict") == "none" or not res.get("paths"):
        return []
    article = gate.article_of(res["paths"][0])
    if not article:
        return []
    topic = gate.topic(article)
    path = gate.ledger(article, "_gaps.md")
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    if g["id"] not in text:
        write_text(path, add_under(text, topic, (
            f"- **{one_line(entry['question']).replace('**', '')}** The kb was asked this in a logged lookup of "
            f"{entry.get('day', day)}, and no article answered it (query log finding {g['id']}). Looked in the kb "
            f"{day}: `rag.py pack` gives "
            f"`{res.get('verdict')}`, with this topic in the lead. Needs an official source that states it "
            f"(`/kb-research`, or the query log's opt-in research). (topic: {topic})")))
    return [{**without_observed(g), "state": "applied", "stage": "gap", "article": article,
             "promotions": [*(g.get("promotions") or []), {"from": "candidate-gap", "to": "gap", "by": "apply"}],
             "observed": {"verdict": res.get("verdict"), "topic": topic}}]


# ---------------------------------------------------------------- one apply

def apply(store=None, gate=None, kb_commit=None, out=print, hold=(), research=None, day=None):
    """One apply over `store` (default: the local store beside the spool), in the working tree of this clone: every
    open eval finding with its open fix finding, in id order; then the gap step (each open gap candidate whose miss
    reproduces under an article becomes a _gaps.md entry under that article's topic); then, when `research` (a
    Researcher) has runs left, research on the gap findings; then one findings file with each outcome. Source findings
    are left as they are, and so are the findings in `hold` (pending on a conflict branch) and those recorded
    apply-failed more than FAILED_RETRIES times, even when a later record opens them again. 0; 1 when `rag.py eval`
    fails before an eval change."""
    store = Path(store or places()[0] / "store")
    gate = gate or Gate()
    day = day or datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    entries = store_entries(store)
    by_entry = {e["id"]: e for _, e in entries}
    last = finding_states(store)
    failed = failed_counts(store)

    def actionable(r):
        return r["id"] not in hold and failed.get(r["id"], 0) <= FAILED_RETRIES

    def entry_of(r):
        e = by_entry.get(r.get("entry"))
        return e if e and isinstance(e.get("question"), str) else None

    evals = sorted((r for r in last.values() if r.get("kind") == "eval" and r.get("state") == "open"
                    and actionable(r)), key=lambda r: r["id"])
    gaps = sorted((r for r in last.values() if r.get("kind") == "gap" and r.get("state") == "open"
                   and r.get("stage") == "candidate-gap" and actionable(r)), key=lambda r: r["id"])
    new, base = [], None
    if evals:
        base = gate.measure()
        if base["passed"] != base["n"]:
            out(f"apply: rag.py eval fails before any change ({base['passed']} of {base['n']} pass); nothing applied")
            return 1
        fixes = {r["entry"]: r for r in last.values() if r.get("kind") in FIX_KINDS and r.get("state") == "open"
                 and actionable(r)}
        for ev in evals:
            entry = entry_of(ev)
            if entry:
                new += apply_one(ev, fixes.get(ev["entry"]), entry, gate, base)
    for g in gaps:
        entry = entry_of(g)
        if entry:
            new += gap_one(g, entry, gate, day)
    runs = {"runs": 0, "facts": 0, "conflicts": 0}
    if research is not None and research.left():
        now = {**last, **{r["id"]: r for r in new}}
        todo = sorted((r for r in now.values() if r.get("kind") == "gap" and r.get("stage") == "gap"
                       and r.get("state") == "applied" and actionable(r) and entry_of(r)), key=lambda r: r["id"])
        for g in todo:
            if not research.left():
                break
            rec = research_one(g, entry_of(g), gate, research, day)
            runs["runs"] += 1
            if rec is not None:
                new = [r for r in new if r["id"] != rec["id"]] + [rec]
                runs["facts"] += (rec.get("observed") or {}).get("facts", 0)
                runs["conflicts"] += (rec.get("observed") or {}).get("conflicts", 0)
    if not new:
        out("apply: nothing to apply" + (f" (research runs={runs['runs']}, no reply)" if runs["runs"] else ""))
        return 0
    run_id, counts = write_findings(store, entries, new, APPLY_STATES, kb_commit)
    said = f"apply: run={run_id} records={len(new)} " + " ".join(f"{s}={n}" for s, n in counts.items())
    if base is not None and any(r["kind"] in FIX_KINDS and r["state"] == "applied" for r in new):
        m = gate.measure()
        ids = [i for i in base["chars"] if i in m["chars"]]
        mean = [round(sum(d["chars"][i] for i in ids) / max(len(ids), 1)) for d in (base, m)]
        said += (f" eval={m['passed']}/{m['n']} mean-pack={mean[0]}->{mean[1]} "
                 f"offkb-good={base['offkb_good']}->{m['offkb_good']}")
    n_gaps = sum(1 for r in new if r["kind"] == "gap" and any(p.get("to") == "gap" and p.get("by") == "apply"
                                                              for p in r.get("promotions") or []))
    if n_gaps:
        said += f" gaps={n_gaps}"
    if runs["runs"]:
        said += f" research={runs['runs']} facts={runs['facts']} conflicts={runs['conflicts']}"
    out(said)
    return 0
