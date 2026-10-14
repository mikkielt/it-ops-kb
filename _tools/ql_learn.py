"""The query log's learn (kb/_self/querylog.md, Learn): the store's run files and the kb at HEAD become findings, and
only findings: every judged miss re-run with pack first (`fixed-since` when it now passes), then eval, alias,
expansion and gap-candidate findings, and report-only source findings on the hosts the store's fetches name. A
lookup with verdict none whose fetched pages the kb cites is a false none: an eval finding, in place of a gap; so is
a miss whose pack on HEAD is none with an article in the lead that holds every word the pack says the kb lacks. One
findings file holds the records that change a finding's state (none: no file). A weak or none lookup in the kb's own
rule docs (an entry with `root` _self) is a `rules` finding of its own, never one of those.
"""
import csv, json, re
from pathlib import Path

from ql_base import HOME, places
from ql_capture import FEEDBACK, host_path
from ql_store import (FETCH_KEYS, LEARN_STATES, RULES_ROOT, SOURCES_MAX, STAGES, finding_id, finding_states, store_entries,
                      write_findings)

WEB_SOURCES = HOME / "kb" / "_self" / "web-sources.md"
ROUTE_HOST = re.compile(r"(?:[a-z0-9-]+\.)+[a-z]{2,}")
FILE_SUFFIXES = ("txt", "md", "mdx", "json", "html", "xml", "csv", "py", "yml", "yaml")  # `llms.txt` is no host
FAILED = re.compile(r"http-[45]\d\d|empty|truncated|error")  # fetch outcomes that count as failures on the host
NO_PAGE = re.compile(r"http-[45]\d\d|empty|error")  # fetch outcomes with no page read: no evidence for a false none
ANSWER_URL = re.compile(r"https?://[^\s<>\"'`\[\]()]+")  # a url in an answer's text; Markdown and prose end it
LEARN_LOCALE = re.compile(r"^/[a-z]{2}-[a-z]{2}(?=/|$)")  # Microsoft Learn's locale segment (agent_bench.norm_url)
# the staging triggers (web-sources.md, "When a family needs staging"): the numbers a test holds equal to the doc
STAGE_SHARE_ROWS = 25  # Share: a host backing at least this many rows of a root's _sources.csv
STAGE_SHARE_PERCENT = 5  # Share: or at least this share of them
STAGE_FAILURES = 3  # Failures: this many failed fetches on the host
STAGE_NEEDED_LEVEL = 1  # what a Share or Failures trigger asks for first: a route
NUMBER_WORDS = {w: i for i, w in enumerate(("zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
                                            "nine", "ten"))}


# ---------------------------------------------------------------- where a host stands

def routes_table(text=None):
    """The rows of the routes table ("Routes by family" in kb/_self/web-sources.md): {family, find, read, avoid,
    hosts}, `hosts` being the host names its family, find and read cells name in backticks."""
    text = WEB_SOURCES.read_text(encoding="utf-8") if text is None else text
    m = re.search(r"^## Routes by family\n(.*?)(?=^## )", text, re.M | re.S)
    out = []
    for line in (m.group(1) if m else "").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.startswith("|") else []
        if len(cells) != 4 or cells[0] in ("family", "") or set(cells[0]) <= set("-: "):
            continue
        hosts = []
        for cell in cells[:3]:
            for tok in re.findall(r"`([^`]+)`", cell):
                h = tok.split("/", 1)[0].lower()
                if ROUTE_HOST.fullmatch(h) and h.rsplit(".", 1)[-1] not in FILE_SUFFIXES and h not in hosts:
                    hosts.append(h)
        out.append(dict(zip(("family", "find", "read", "avoid"), cells), hosts=hosts))
    return out


def registry_row(host, registry=None):
    """The provider-registry row (_tools/providers.csv, or a root's _providers.csv) serving `host`, not the `*` one."""
    import provider
    row = provider.for_url(f"https://{host}/", provider.providers() if registry is None else registry)
    return row if row and "*" not in (row.get("match") or "").split() else None


def staging_level(host, registry=None, routes=None):
    """(level, where from) of a host (kb/_self/web-sources.md, Staging levels): 3 with a provider-registry row, else 1
    with a row of the routes table, else 0."""
    if registry_row(host, registry):
        return 3, "registry"
    if any(host in r["hosts"] for r in (routes_table() if routes is None else routes)):
        return 1, "routes"
    return 0, None


def avoided_route(host, routes=None):
    """The routes-table row of HOST (the first that names it) when its avoid cell names WebFetch, else None: the
    route signal of source_findings and the WebFetch hook's deny (kb_hook.webfetch_deny) both read it here."""
    route = next((r for r in (routes_table() if routes is None else routes) if host in r["hosts"]), None)
    return route if route and "WebFetch" in route["avoid"] else None


def registry_problems(registry=None, routes=None):
    """A registry row whose host the routes table does not name: a staged family adds its routes row first, so the
    two sources of a host's level agree. The shared registry only; a root's own providers are its team's."""
    import provider
    rows = provider._read(provider.SHARED) if registry is None else registry
    hosts = {h for r in (routes_table() if routes is None else routes) for h in r["hosts"]}
    out = []
    for r in rows:
        if r.get("_root"):
            continue
        for m in (r.get("match") or "").split():
            h = m.split("/", 1)[0].lower()
            if m != "*" and h not in hosts:
                out.append(f"provider {r.get('provider')}: {h} has a registry row but no row in the routes table")
    return out


def doc_triggers(text=None):
    """{share_rows, share_percent, failures} as the staging triggers of web-sources.md state them (None when absent)."""
    text = WEB_SOURCES.read_text(encoding="utf-8") if text is None else text
    m = re.search(r"^## When a family needs staging\n(.*?)(?=^## )", text, re.M | re.S)
    sec = m.group(1) if m else ""

    def num(rx):
        g = re.search(rx, sec, re.I)
        if not g:
            return None
        v = g.group(1).lower()
        return int(v) if v.isdigit() else NUMBER_WORDS.get(v)
    return {"share_rows": num(r"\*\*Share\.\*\*[^\n]*?at least (\d+) rows"),
            "share_percent": num(r"\*\*Share\.\*\*[^\n]*?at least (\d+)%"),
            "failures": num(r"\*\*Failures\.\*\*\s*(\w+) or more failures")}


def trigger_problems(text=None):
    """Each staging trigger whose number in ql_learn.py differs from web-sources.md."""
    ours = {"share_rows": STAGE_SHARE_ROWS, "share_percent": STAGE_SHARE_PERCENT, "failures": STAGE_FAILURES}
    doc = doc_triggers(text)
    return [f"trigger {k}: ql_learn.py has {v}, web-sources.md has {doc[k]}" for k, v in ours.items() if doc[k] != v]


def kb_host_counts():
    """({host: [(rows, the root's rows) per root]} from the roots' _sources.csv, {host: fetch errors} from their
    _fetch_state.csv), read at HEAD."""
    import kbcommon
    share, errors = {}, {}
    for r in kbcommon.roots():
        for name, col in (("_sources.csv", None), ("_fetch_state.csv", "error")):
            p = Path(r.path) / name
            if not p.is_file():
                continue
            with open(p, encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
            counts = {}
            for row in rows:
                h, _ = host_path(row.get("url") or "")
                if h and (col is None or (row.get(col) or "").strip()):
                    counts[h] = counts.get(h, 0) + 1
            for h, n in counts.items():
                if col:
                    errors[h] = errors.get(h, 0) + n
                else:
                    share.setdefault(h, []).append((n, len(rows)))
    return share, errors


def share_trigger(per_root):
    """Whether a host backs at least STAGE_SHARE_ROWS rows, or STAGE_SHARE_PERCENT percent, of some root's sources."""
    return any(n >= STAGE_SHARE_ROWS or n * 100 >= STAGE_SHARE_PERCENT * total for n, total in per_root)


# ---------------------------------------------------------------- the findings

FEEDBACK_JUDGED = {"answered": "answered", "partly": "partly", "missed": "missed", "misled": "missed"}  # a report's outcome as a judgement: a misled lookup is a miss


def feedback_reports(e):
    """The closed reports of an entry's `feedback`, in time order (none for an entry without one)."""
    f = e.get("feedback")
    return [r for r in f if isinstance(r, dict)] if isinstance(f, list) else []


def judged_of(e):
    """The judgement of a lookup: the outcome of its last feedback report (`misled` as `missed`), which replaces
    Haiku's `judged` for the entry; else Haiku's."""
    for r in reversed(feedback_reports(e)):
        if r.get("outcome") in FEEDBACK_JUDGED:
            return FEEDBACK_JUDGED[r["outcome"]]
    return e.get("judged")


def is_miss(e):
    """A judged miss: the lookup was judged missed or partly answered (`judged_of`: a report's outcome, else Haiku),
    or the pack's verdict was weak or none; but a weak pack judged answered is no miss (a verdict none stays one). A
    lookup in the rule docs is no public miss (`rules_miss`)."""
    if not isinstance(e.get("question"), str) or e.get("root") == RULES_ROOT:
        return False
    judged = judged_of(e)
    if judged in ("missed", "partly"):
        return True
    return e.get("verdict") == "none" or (e.get("verdict") == "weak" and judged != "answered")


QUESTION_WORDS = 30  # the most words of a question a person or skill asks; a longer one is pasted text
RULES_QUESTION_WORDS = QUESTION_WORDS


def pasted_text(question):
    """Whether a question is pasted text, not one a person or skill asked: a backlog item's title and goal, which
    `backlog.py dispatch` packs, or a worker's brief, has more than QUESTION_WORDS words. No finding is derived from
    it, and the gap step files no entry for it."""
    return isinstance(question, str) and len(question.split()) > QUESTION_WORDS


def rules_miss(e):
    """A lookup in the kb's own rule docs (an entry with `root` _self) that missed: it has a question (a set run has
    none), no set, no `item` (a `pack --item` lookup's question is the item's title and goal, text and no question)
    and at most RULES_QUESTION_WORDS words, and its pack verdict was weak or none or the reader found no answer
    (route `miss`)."""
    return (e.get("root") == RULES_ROOT and isinstance(e.get("question"), str) and "set" not in e and "item" not in e
            and not pasted_text(e["question"])
            and (e.get("verdict") in ("weak", "none") or e.get("route") == "miss"))


def default_rules_pack(question):
    """{verdict, known} of the rule docs now: the verdict of `pack --root _self` for the question, and whether the
    `_self` eval file already holds the question as a row."""
    import kbfacts
    asked = " ".join(question.lower().split())
    return {"verdict": kbfacts.pack(question, fmt="concise", root=RULES_ROOT)["verdict"],
            "known": any(" ".join((r.get("question") or "").lower().split()) == asked for r in kbfacts.self_eval_rows())}


def pair_word(word, line, question):
    """The word of `line` that stands for the key word `word` no passage holds, else None: the line's only word that
    is not in the question, not a stop word, not a number, not shorter than three characters and not `word` itself
    (`unsaved` in `land: uncommitted changes`, asked about land with unsaved changes: `uncommitted`; asked about
    unsaved changes alone, `land` is a second such word). With two or more such words the line names no pair."""
    import kbfacts
    asked = {w.lower() for w in kbfacts.WORD.findall(question)}
    words = {w for w in (w.lower() for w in kbfacts.WORD.findall(line))
             if w not in asked and w not in kbfacts.STOP and len(w) >= 3 and not w.isdigit() and w != word}
    return words.pop() if len(words) == 1 else None


def default_rule_lines(refs):
    """The text of each `kb/_self/<doc>.md:<line>` reference that is a line of a rule doc."""
    import kbfacts
    out = []
    for ref in refs:
        path, _, n = ref.rpartition(":")
        lines = (kbfacts.read(path) or "").splitlines() if path in kbfacts.self_docs() else []
        if n.isdigit() and 0 < int(n) <= len(lines):
            out.append(lines[int(n) - 1])
    return out


def rules_pair(e, rule_lines=None):
    """[missing word, the answering line's word] of a rules miss with `key_missing` words and a quoted line, else
    None: the first missing word that has a `pair_word`."""
    lines = (rule_lines or default_rule_lines)(e.get("answer_lines") or [])
    for word in e.get("key_missing") or []:
        word = str(word).lower()
        for line in lines:
            w = pair_word(word, line, e["question"])
            if w:
                return [word, w]
    return None


def rules_finding(e, now, rule_lines=None):
    """The `rules` finding of one missed rules lookup: `fixed-since` when the rule docs answer it now (the pack is
    `good` after a weak or none one) or the eval file holds the question; else `open`. It carries the question, the
    verdict, the `answer_lines` the reader quoted and the `key_missing` words, when the entry has them, and stays at
    stage miss: no public gap or fact comes of it."""
    fixed = now["known"] or (e.get("verdict") in ("weak", "none") and now["verdict"] == "good")
    obs = {"question": e["question"], "verdict": e.get("verdict")}
    if e.get("route") == "miss":
        obs["route"] = "miss"
    for key in ("answer_lines", "key_missing"):
        if e.get(key):
            obs[key] = list(e[key])
    pair = rules_pair(e, rule_lines)
    if pair:
        obs["pair"] = pair
    return {"id": finding_id("rules", e["id"]), "kind": "rules", "state": "fixed-since" if fixed else "open",
            "stage": "miss", "entry": e["id"], "observed": obs}


def passes(res, best):
    """Whether a pack on HEAD answers the question: `good`, with the article that answers it among the pack's (the
    eval rule, rag.py run_eval); without one, `good` with no `check:` line."""
    if res.get("verdict") != "good":
        return False
    if best:
        return best in res.get("paths", [])
    return not any(res.get(k) for k in ("unmatched", "spread", "scatter", "passing", "priced", "parted"))


def unknown_words(question, res):
    """The question's words, lower case, whose stems the pack reports as nowhere in the kb."""
    import kbfacts
    missing = set(res.get("missing") or [])
    out = []
    for w in kbfacts.WORD.findall(question):
        w = w.lower()
        if kbfacts.stem(w) in missing and w not in out:
            out.append(w)
    return out


def default_pack(question):
    import kbfacts
    return kbfacts.pack(question, fmt="concise")


def article_of(path):
    """The qualified article (.md) whose topic holds the qualified `path` (the article itself, a same-stem data file or
    a file its `files:` lists), or None."""
    import kbfacts
    arts = kbfacts.articles()
    if path in arts:
        return path
    for topic, files in sorted(kbfacts.topic_files().items()):
        if path in files:
            return next((q for q in files if q in arts and arts[q].get("topic") == topic), None)
    return None


def article_facts(article):
    """[(line, text)] of the tagged facts of `article`."""
    import kbfacts
    return [(u["line"], u["text"]) for u in kbfacts.units(article) if u["path"] == article and u["tags"]]


def holds_word(word, text):
    """Whether `text` holds `word` as written, case aside, not inside a longer word or number (`1.5` in `1.5-second`,
    not in `v2.1.5` or `1.50`)."""
    return re.search(r"(?<![\w.])" + re.escape(word.lower()) + r"(?![\w]|\.\w)", text.lower()) is not None


def domain_article(res, lead_of=None):
    """The article whose topic a pack's question lies in, else None: the article of the pack's lead path, and for a
    `none` pack only when that lead matches more than half of the question's key words the kb knows (`matched`
    against `known`); a `none` lead with fewer is a stray word match (VMware Horizon led by an Azure OpenAI article)."""
    if not res.get("paths"):
        return None
    if res.get("verdict") == "none" and len(res.get("matched") or []) * 2 <= len(res.get("known") or []):
        return None
    return (lead_of or article_of)(res["paths"][0])


def held_article(res, lead_of=None, facts=None):
    """The article that holds the answer to a `none` pack, else None: the pack's lead is an article of the question's
    domain (`domain_article`), and one of its tagged facts holds, as written, every word the pack says the kb lacks
    (`lacks`). The pack's words missed a fact that is there (a number with a unit suffix, a spelling its terms do not
    split), so the miss is a retrieval miss for an eval finding, not a knowledge gap."""
    lacks = [w for w in res.get("lacks") or [] if isinstance(w, str) and w.strip()]
    if res.get("verdict") != "none" or not lacks:
        return None
    lead = domain_article(res, lead_of)
    if lead is None or lead != res["paths"][0]:
        return None
    lines = (facts or article_facts)(lead)
    return lead if any(all(holds_word(w, text) for w in lacks) for _, text in lines) else None


def miss_findings(e, res, sources=None, lead=None):
    """The findings of one judged miss after its re-run on HEAD: eval (an article answers it) with its fix, alias
    (the question uses a word the kb never holds) or expansion (every word is known: a paraphrase), or a gap
    candidate (no candidate article answers it). All `fixed-since` when the re-run passes. `sources`: the source ids
    that led to the article `e["best"]` (a false none), kept in the eval finding's `observed`. `lead`: the gated url
    a feedback report gave (a gap finding carries it, for the research run)."""
    best = e.get("best")
    ok = passes(res, best)
    state = "fixed-since" if ok else "open"
    obs = {"verdict": res.get("verdict"), "paths": list(res.get("paths") or [])[:4]}
    if not best:
        return [{"id": finding_id("gap", e["id"]), "kind": "gap", "state": state, "stage": "candidate-gap",
                 "promotions": [{"from": "miss", "to": "candidate-gap", "by": "learn"}], "entry": e["id"],
                 **({"lead": lead} if lead else {}), "observed": obs}]
    out = [{"id": finding_id("eval", e["id"]), "kind": "eval", "state": state, "stage": "miss", "entry": e["id"],
            "expect": best, "observed": {**obs, "sources": list(sources)} if sources else obs}]
    if not ok:
        terms = unknown_words(e["question"], res)
        if terms:
            out.append({"id": finding_id("alias", e["id"]), "kind": "alias", "state": "open", "stage": "miss",
                        "entry": e["id"], "article": best, "terms": terms, "observed": obs})
        else:
            out.append({"id": finding_id("expansion", e["id"]), "kind": "expansion", "state": "open", "stage": "miss",
                        "entry": e["id"], "article": best, "observed": obs})
    return out


# ---------------------------------------------------------------- feedback: what the reports add to a lookup's findings

def feedback_best(e, articles=None):
    """The article the last report that names one (`best`) gives, when it is an article of the kb, else None."""
    import kbfacts
    arts = kbfacts.articles() if articles is None else articles
    for r in reversed(feedback_reports(e)):
        if isinstance(r.get("best"), str) and r["best"] in arts:
            return r["best"]
    return None


def feedback_lead(e):
    """The gated lead url of the last report that has one, else None."""
    return next((r["lead"] for r in reversed(feedback_reports(e)) if isinstance(r.get("lead"), str)), None)


def fact_source_ids(text):
    """The source ids the tags of a fact line cite, sorted."""
    import kbfacts
    return sorted({i for tag in kbfacts.TAG.findall(text) for i in kbfacts.ID.findall(tag)})


def source_retrieved(sid):
    """The `retrieved_utc` day of a source row, else None."""
    import kbfacts
    return ((kbfacts.source_rows().get(sid) or {}).get("retrieved_utc") or "")[:10] or None


def feedback_findings(entries, facts=None, retrieved=None):
    """The findings the reports of the store's entries add, each from closed fields only: a `conflict` finding (stage
    miss) per line a report marked `wrong` when it names a page (its `lead`, else the first of its `sources`: `lead`
    or `source_id` of the finding), which apply checks and records; a report-only `source` finding (signal `stale`)
    per source id that a line marked `stale` cites, `fixed-since` once the source was retrieved after the newest such
    report. `helpful` and `irrelevant` marks make no finding: the digest counts them."""
    facts = facts or article_facts
    retrieved = retrieved or source_retrieved
    out, stale = {}, {}
    for _, e in entries:
        for rep in feedback_reports(e):
            page = rep.get("lead") or next(iter(rep.get("sources") or []), None)
            for x in rep.get("lines") or []:
                if not (isinstance(x, dict) and isinstance(x.get("line"), str)):
                    continue
                if x.get("issue") == "wrong" and page:
                    fid = finding_id("conflict", e["id"], x["line"])
                    out[fid] = {"id": fid, "kind": "conflict", "state": "open", "stage": "miss", "entry": e["id"],
                                "line": x["line"], **({"lead": rep["lead"]} if rep.get("lead") else {"source_id": page})}
                elif x.get("issue") == "stale":
                    path, _, n = x["line"].rpartition(":")
                    text = next((t for ln, t in facts(path) if str(ln) == n), None)
                    for sid in fact_source_ids(text or ""):
                        s = stale.setdefault(sid, {"entries": set(), "lines": set(), "day": ""})
                        s["entries"].add(e["id"])
                        s["lines"].add(x["line"])
                        s["day"] = max(s["day"], str(e.get("day") or ""))
    for sid, s in sorted(stale.items()):
        since = retrieved(sid)
        fid = finding_id("source", "stale", sid)
        out[fid] = {"id": fid, "kind": "source", "state": "fixed-since" if since and since > s["day"] else "open",
                    "signal": "stale", "source_id": sid,
                    "observed": {"entries": len(s["entries"]), "lines": sorted(s["lines"])[:5]}}
    return list(out.values())


def spool_claims(spool=None):
    """[(closed report, claim)] of the feedback rows the local spool still holds with a `claim`, the report in the
    closed shape the store keeps (ql_distill.feedback_report), so a stored report finds its row by equality. The
    claim is free text and lives in the spool only (the store keeps closed fields): once distill has delivered a row it
    is gone, and a report whose row is gone has no claim."""
    import ql_distill
    spool = Path(spool) if spool else places()[0] / "spool"
    out, pages = [], KbPages()
    for p in sorted(spool.glob("*.jsonl")) if spool.is_dir() else []:
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for ln in lines:
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            claim = " ".join(r["claim"].split()) if isinstance(r, dict) and isinstance(r.get("claim"), str) else ""
            if claim and r.get("surface") == FEEDBACK:
                for rep in ql_distill.closed_reports([ql_distill.feedback_report(r, None, pages)]):
                    out.append((rep, claim))
    return out


def report_claim(e, claims, wanted=None):
    """The claim of the last report of entry `e` that `wanted` accepts (default: any) and a spool row (`claims`, from
    `spool_claims`) holds, else None."""
    for rep in reversed(feedback_reports(e)):
        if wanted is None or wanted(rep):
            for shape, claim in claims:
                if shape == rep:
                    return claim
    return None


# ---------------------------------------------------------------- a false none: the kb cites a page the lookup fetched

def page_key(host, path):
    """A page as a comparable key: host and path in lower case, without www, Learn's locale segment, query, fragment,
    trailing slash or `.md` (a page's source row may name its Markdown form). None without a host."""
    if not isinstance(host, str) or not host.strip():
        return None
    host = host.strip().lower()
    host = host[4:] if host.startswith("www.") else host
    path = str(path or "").split("#")[0].split("?")[0].strip().lower().rstrip("/")
    if path.endswith(".md"):
        path = path[:-3].rstrip("/")
    if host == "learn.microsoft.com":
        path = LEARN_LOCALE.sub("", path)
    return host + path


class KbPages:
    """The pages the kb cites, read at HEAD once and only when a lookup needs them: `match(entry)` gives the article
    that a none entry's fetched pages point at and the ids of the sources it matched."""

    def __init__(self):
        self._ids = None
        self._lines = {}

    def source_ids(self, key):
        """The ids of the sources (every root's _sources.csv) whose url is the page `key`."""
        import kbfacts
        if self._ids is None:
            self._ids = {}
            for sid, row in kbfacts.source_rows().items():
                k = page_key(*host_path(row.get("url") or ""))
                if k:
                    self._ids.setdefault(k, []).append(sid)
        return self._ids.get(key, [])

    def named_ids(self, text):
        """The ids of the kb sources whose urls `text` names (the page comparison of page_key), sorted, at most
        SOURCES_MAX; never the urls or the text."""
        ids = set()
        for url in ANSWER_URL.findall(text if isinstance(text, str) else ""):
            key = page_key(*host_path(url.rstrip(".,;:!?*_")))
            ids.update(self.source_ids(key) if key else [])
        return sorted(ids)[:SOURCES_MAX]

    def article_lines(self, sid):
        """{article: the number of its lines citing source `sid`}: articles only, never data files or ledgers."""
        import kbfacts
        if sid not in self._lines:
            arts = kbfacts.articles()
            counts = {}
            for path, _ in kbfacts.cited_lines([sid]).get(sid, []):
                if path in arts:
                    counts[path] = counts.get(path, 0) + 1
            self._lines[sid] = counts
        return self._lines[sid]

    def match(self, e):
        """(article, source ids) for a none entry whose fetched pages the kb cites (a false none), else None: the
        pages the entry fetched (a fetch that read no page aside) whose host and path a source row holds, and the
        sources its `sources` names (the ids a kb_ask.py researcher's answer cited, as good as a fetched page), and
        the article with the most lines citing those sources (ties by path). Only sources an article cites count."""
        if e.get("verdict") != "none":
            return None
        items = [f for f in e.get("fetches") or [] if isinstance(f, dict)]
        if e.get("host"):
            items.append({k: e[k] for k in FETCH_KEYS if k in e})
        ids = []
        for sid in e.get("sources") if isinstance(e.get("sources"), list) else []:
            if isinstance(sid, str) and sid not in ids and self.article_lines(sid):
                ids.append(sid)
        for f in items:
            if isinstance(f.get("outcome"), str) and NO_PAGE.fullmatch(f["outcome"]):
                continue
            key = page_key(f.get("host"), f.get("path"))
            for sid in self.source_ids(key) if key else []:
                if sid not in ids and self.article_lines(sid):
                    ids.append(sid)
        totals = {}
        for sid in ids:
            for art, n in self.article_lines(sid).items():
                totals[art] = totals.get(art, 0) + n
        if not totals:
            return None
        return min(totals, key=lambda a: (-totals[a], a)), sorted(ids)


def answer_sources(text, pages=None):
    """The ids of the kb sources whose urls a researcher's answer `text` names: what kb_ask.py's row keeps in
    `sources`, since its `claude -p` runs with hooks off and its fetches are never logged."""
    return (pages or KbPages()).named_ids(text)


def host_fetches(entries):
    """{host: {failures, entries, webfetch, chars}} of the fetches the store's entries record; `chars` sums the
    result characters of the fetches that recorded them."""
    hosts = {}
    for _, e in entries:
        items = [f for f in e.get("fetches") or [] if isinstance(f, dict)]
        if e.get("host"):
            items.append({k: e[k] for k in FETCH_KEYS if k in e})
        for f in items:
            h = f.get("host")
            if not isinstance(h, str):
                continue
            n = f.get("n") if isinstance(f.get("n"), int) else 1
            s = hosts.setdefault(h, {"failures": 0, "entries": set(), "webfetch": set(), "chars": 0})
            s["entries"].add(e["id"])
            if isinstance(f.get("chars"), int):
                s["chars"] += f["chars"]
            if isinstance(f.get("outcome"), str) and FAILED.fullmatch(f["outcome"]):
                s["failures"] += n
            if f.get("tool") == "WebFetch":
                s["webfetch"].add(e["id"])
    return hosts


def source_findings(entries, registry=None, routes=None, counts=None):
    """Report-only findings on the hosts the store's fetches name: `stage` when a Share or Failures trigger holds
    and the host has less than STAGE_NEEDED_LEVEL; `route` when WebFetch read a host whose route avoids it."""
    routes = routes_table() if routes is None else routes
    share, errors = kb_host_counts() if counts is None else counts
    out = []
    for host, s in sorted(host_fetches(entries).items()):
        level, _ = staging_level(host, registry, routes)
        per_root = share.get(host, [])
        rows = max((n for n, _ in per_root), default=0)
        failures = s["failures"] + errors.get(host, 0)
        triggers = [t for t, hit in (("share", share_trigger(per_root)), ("failures", failures >= STAGE_FAILURES))
                    if hit]
        if triggers and level < STAGE_NEEDED_LEVEL:
            out.append({"id": finding_id("source", "stage", host), "kind": "source", "state": "open",
                        "signal": "stage", "host": host, "level": level, "needs": STAGE_NEEDED_LEVEL,
                        "triggers": triggers, "observed": {"rows": rows, "failures": failures,
                                                           "entries": len(s["entries"])}})
        route = avoided_route(host, routes) if s["webfetch"] else None
        if route:
            out.append({"id": finding_id("source", "route", host), "kind": "source", "state": "open",
                        "signal": "route", "host": host, "tool": "WebFetch", "route": route["family"].replace("`", ""),
                        "observed": {"entries": len(s["webfetch"])}})
    return out


def _key(rec):
    """The finding fields a follow-up record carries: no `observed`, and no `tried` on an eval finding (the store
    takes `tried` on a gap finding or a no-fix eval finding only, so a `fixed-since` eval record leaves it behind)."""
    return {k: v for k, v in rec.items() if k != "observed" and not (k == "tried" and rec.get("kind") == "eval")}


def later_stage(prev, rec):
    """Whether a finding's last record is at a later stage than the one learn derives for it (a gap the research
    queue recorded `fixed-since` at stage gap): learn leaves such a finding as it is."""
    at = {s: i for i, s in enumerate(STAGES)}
    return at.get(prev.get("stage"), 0) > at.get(rec.get("stage"), 0)


def learn(store=None, pack=None, kb_commit=None, registry=None, routes=None, counts=None, out=print, rules_pack=None):
    """One learn over `store` (default: the local store beside the spool): every judged miss re-run with `pack` on
    HEAD, a `no-fix` eval finding included, which becomes `fixed-since` when its question now passes (BG-bbfdisfu) (a none entry whose fetched pages the kb cites is an eval finding for the article citing them most, and so is
    a miss whose none pack leads with an article holding the words it lacks, `held_article`), the source findings,
    then one findings file holding only the records that change a finding's state. 0."""
    store = Path(store or places()[0] / "store")
    pack = pack or default_pack
    entries = store_entries(store)
    if not entries:
        out("learn: no run files")
        return 0
    derived, pages = {}, KbPages()
    for _, e in entries:
        if rules_miss(e):
            rec = rules_finding(e, (rules_pack or default_rules_pack)(e["question"]))
            derived[rec["id"]] = rec
        elif is_miss(e) and not pasted_text(e["question"]):
            res = pack(e["question"])
            said = feedback_best(e)  # a report named the article that answers it: an eval finding for it
            hit = (said, sorted({i for r in feedback_reports(e) for i in r.get("sources") or []})[:SOURCES_MAX] or None) \
                if said else pages.match(e)  # a false none: the kb cites a page the lookup fetched
            held = None if hit else held_article(res)  # or the pack's lead article holds the words it says it lacks
            hit = hit or ((held, None) if held else None)
            for rec in miss_findings({**e, "best": hit[0]} if hit else e, res, hit[1] if hit else None,
                                     feedback_lead(e)):
                derived[rec["id"]] = rec
    for rec in source_findings(entries, registry, routes, counts):
        derived[rec["id"]] = rec
    for rec in feedback_findings(entries):
        derived[rec["id"]] = rec
    last = finding_states(store)
    new = []
    for fid, rec in derived.items():
        prev = last.get(fid)
        if prev is None or (prev.get("state") in LEARN_STATES and not later_stage(prev, rec)
                            and _key(prev) != _key(rec)):
            new.append(rec)
        elif prev.get("state") == "no-fix" and prev.get("kind") == "eval" and rec.get("state") == "fixed-since":
            # apply found no fix, but the question now passes on HEAD; one still missing stays no-fix
            new.append({**_key(prev), "state": "fixed-since", "observed": rec.get("observed")})
    for fid, prev in last.items():  # an open finding learn no longer derives: the kb at HEAD handles it now
        if fid not in derived and prev.get("state") == "open":
            new.append({**_key(prev), "state": "fixed-since"})
    total = len({**last, **{r["id"]: r for r in new}})
    if not new:
        out(f"learn: nothing new (findings={total})")
        return 0
    run_id, states = write_findings(store, entries, new, LEARN_STATES, kb_commit)
    out(f"learn: run={run_id} records={len(new)} open={states['open']} fixed-since={states['fixed-since']} "
        f"findings={total}")
    return 0
