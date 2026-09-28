"""The query log's research and quote check (kb/_self/querylog.md, Research), and the add-only writers apply's gap step
shares with it. Research is opt-in per user, capped by the user's own daily count: one `claude -p` run per gap
finding at stage `gap`, whose candidate facts are kept only when deterministic gates pass and their quote is on the
page; nothing existing is edited.
"""
import collections, csv, io, json, re
from pathlib import Path
from urllib.parse import urlsplit

from ql_base import (DISABLED_NAME, HOME, Replay, claude_p, one_line, places, read_json, read_mode, read_research,
                     restore, write_text)
from ql_store import HOSTNAME, PRIVATE_TLDS, QUESTION_MAX_CHARS

QUOTE_MAX_WORDS = 25  # the longest quote the kb's rules allow (kbcommon.QUOTE_WORDS, kb/_self/content-rules.md)
QUOTE_MIN_WORDS = 5  # a shorter quote is found on almost any page and backs nothing
QUOTE_CHARS = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-",
                             "\xa0": " ", "​": ""})
MD_LINK = re.compile(r"!\[[^\]]*\]\([^)]*\)|\[([^\]]*)\]\([^)]*\)")
RESEARCH_MODEL = "sonnet"
RESEARCH_TIMEOUT_S = 600
RESEARCH_RUNS_PER_APPLY = 2  # research runs in one apply, whatever the daily cap leaves: bounds LOCK_STALE_S
RESEARCH_FACTS_MAX = 5  # candidate facts read from one research reply
RESEARCH_RUNS_NAME = "research-runs.json"  # {"day", "runs"}: the research runs this user started today
RESEARCH_TOOLS = ("WebSearch", "WebFetch")
RESEARCH_MCP_TOOLS = ("mcp__microsoft-learn__microsoft_docs_search", "mcp__microsoft-learn__microsoft_docs_fetch",
                      "mcp__claude-code-docs__search_claude_code_docs",
                      "mcp__claude-code-docs__query_docs_filesystem_claude_code_docs",
                      "mcp__mcp-docs__search_model_context_protocol",
                      "mcp__mcp-docs__query_docs_filesystem_model_context_protocol")
RESEARCH_TAGS = ("DOC", "COMMUNITY")
RESEARCH_FIELDS = ("text", "tag", "url", "title", "publisher", "licence", "reuse", "quote")
RESEARCH_TASK = (
    "You research one question for an IT knowledge base whose lookup found no answer. Read official documentation "
    "(the vendor's own docs, release notes, API reference or repository) with the tools you have; blogs and forums "
    "only as COMMUNITY. For each fact the question needs, give: `text`, the fact in your own words, one sentence, "
    "no citation; `tag`: \"DOC\" for an official page, \"COMMUNITY\" otherwise; `url`, the page where the sentence is "
    "(not a page linking to it); `title`, `publisher`; `licence`, the page's licence or terms in words and where they "
    "are stated; `reuse`: \"copy\" (an open licence), \"quote\" (terms of use, no reuse licence), \"paraphrase\" (the "
    "terms forbid copying) or \"unknown\"; `quote`, 5 to 25 words copied verbatim from that page that state the "
    "fact; `conflicts_with`: the line number of an existing fact below that the page contradicts, else null. Never "
    "restate an existing fact. Use placeholders, never real hosts, tenants or people. Reply with only JSON: "
    '{"facts": [{"text": "...", "tag": "DOC", "url": "https://...", "title": "...", "publisher": "...", '
    '"licence": "...", "reuse": "quote", "quote": "...", "conflicts_with": null}]}; at most %d facts; '
    '{"facts": []} when no official page answers it.' % RESEARCH_FACTS_MAX)


# ---------------------------------------------------------------- the quote check

def quote_norm(s):
    """Text as the quote check compares it: entities decoded, Markdown links and emphasis marks gone, NFKC, straight
    quotes and dashes, lower case, single spaces."""
    import html, unicodedata
    s = html.unescape(html.unescape(s))
    s = MD_LINK.sub(lambda m: m.group(1) or "", s)
    s = unicodedata.normalize("NFKC", s).translate(QUOTE_CHARS)
    s = re.sub(r"[*_`]+", "", s)
    return " ".join(s.split()).lower()


def page_fetch(url):
    """(bytes, content type) of a page, as fetch.py fetches it (one request per host per fetch.DELAY, a spool row)."""
    import fetch
    return fetch.fetch(url)


def quotecheck(url, quote, fetcher=None):
    """(ok, why): whether `quote` (QUOTE_MIN_WORDS to QUOTE_MAX_WORDS words) is on the page at `url`, fetched by
    `fetcher` (default: fetch.py's fetch) and reduced to text by fetch.py's to_text; both sides normalized by
    quote_norm."""
    quote = str(quote or "").strip().strip("\"'“”").strip()
    n = len(quote.split())
    if n > QUOTE_MAX_WORDS:
        return False, f"quote has {n} words, over {QUOTE_MAX_WORDS}"
    if n < QUOTE_MIN_WORDS:
        return False, f"quote has {n} words, under {QUOTE_MIN_WORDS}"
    try:
        body, ctype = (fetcher or page_fetch)(url)
    except Exception as e:  # noqa: BLE001 - any failure to read the page rejects the quote
        return False, one_line(f"page not fetched: {type(e).__name__}: {e}", 160)
    import fetch
    text = fetch.to_text(body, ctype)
    if text is None:
        return False, "page is not text"
    want = quote_norm(quote).rstrip(" .,;:")
    if want and want in quote_norm(text):
        return True, "quote is on the page"
    return False, "quote is not on the page"


def page_file(path, ctype=""):
    """A fetcher that answers every url with the recorded page at `path` (its content type from its suffix)."""
    page = Path(path)
    ctype = ctype or {".html": "text/html", ".htm": "text/html", ".md": "text/markdown"}.get(page.suffix.lower(),
                                                                                             "text/plain")

    def fetcher(url):
        return page.read_bytes(), ctype
    return fetcher


# ---------------------------------------------------------------- who may research, and how much

def research_places(clone=None, data=None):
    """(querylog directory, config file) whose research setting and daily count apply: a clone's own
    _cache/querylog and _private/querylog.json when `clone` names one (apply --push names its clone), a plugin host's
    querylog directory and its config.json when `data` names one (the push from a host names it), else places()."""
    if data:
        return Path(data), Path(data) / "config.json"
    if clone:
        return Path(clone) / "_cache" / "querylog", Path(clone) / "_private" / "querylog.json"
    return places()


def research_used(qdir, day):
    data = read_json(Path(qdir) / RESEARCH_RUNS_NAME, {})
    runs = data.get("runs") if isinstance(data, dict) and data.get("day") == day else 0
    return runs if isinstance(runs, int) and not isinstance(runs, bool) and runs > 0 else 0


def count_research(qdir, day):
    """One more research run today in the user's count."""
    write_text(Path(qdir) / RESEARCH_RUNS_NAME, json.dumps({"day": day, "runs": research_used(qdir, day) + 1}) + "\n")


def research_budget(qdir, cfg, day):
    """The research runs left today: 0 unless the config file turns research on (read_research) and logging is on
    (not mode off, no DISABLED marker); else its daily cap less the runs counted today."""
    on, daily = read_research(cfg)
    if not on or read_mode(cfg) == "off" or (Path(qdir) / DISABLED_NAME).exists():
        return 0
    return max(0, daily - research_used(qdir, day))


def research_argv(model=RESEARCH_MODEL):
    """The `claude -p` argument list of one research run: hooks off (the pipeline never logs itself), no user plugins
    or MCP servers but the kb's three documentation servers, web search and fetch as the only built-in tools, nothing
    else allowed. The prompt goes on stdin."""
    import shutil, kbcommon
    docs = HOME / ".claude-plugin" / "it-ops-kb-docs" / ".mcp.json"
    return [shutil.which("claude") or "claude", "-p", "--model", model, "--no-session-persistence", *kbcommon.NO_HOOKS,
            "--setting-sources", "project,local", "--strict-mcp-config", "--mcp-config", str(docs),
            "--tools", ",".join(RESEARCH_TOOLS), "--permission-mode", "dontAsk",
            "--allowedTools", *RESEARCH_TOOLS, *RESEARCH_MCP_TOOLS]


def claude_research(prompt):
    """One research run: research_argv in an empty directory (no project instructions load). OSError when it cannot
    answer."""
    return claude_p(research_argv(), prompt, RESEARCH_TIMEOUT_S)


class ResearchReplay(Replay):
    """Recorded research replies and pages: {"replies": [text, ...], "pages": {url: file relative to this file}}.
    A url with no recorded page raises OSError."""

    def __init__(self, path):
        super().__init__(path)
        self.pages = {u: self.path.parent / f for u, f in (self.data.get("pages") or {}).items()}

    def fetch(self, url):
        p = self.pages.get(url)
        if p is None:
            raise OSError(f"no recorded page for {url}")
        ctype = {".html": "text/html; charset=utf-8", ".md": "text/markdown"}.get(p.suffix, "text/plain")
        return p.read_bytes(), ctype


class Researcher:
    """The research step of one apply: `runs` left (the user's daily cap less today's count), the model `call`
    (default claude_research), the page `fetcher` for the quote check (default fetch.py's fetch) and `counted`, called
    once per run started (it adds the run to the user's count)."""

    def __init__(self, runs, call=None, fetcher=None, counted=None):
        self.runs, self.call, self.fetcher = runs, call or claude_research, fetcher
        self.counted = counted or (lambda: None)

    def left(self):
        return self.runs > 0

    def ask(self, prompt):
        self.runs -= 1
        self.counted()
        return self.call(prompt)


# ---------------------------------------------------------------- add-only writers (the gap step's too)

def fact_lines(text):
    """[(line number, line)] of the tagged fact lines of an article's body (bullets and table rows with a tag)."""
    import kbfacts
    lines = text.split("\n")
    start = 0
    if lines and lines[0] == "---":
        start = next((i + 1 for i in range(1, len(lines)) if lines[i] == "---"), 0)
    return [(n, ln) for n, ln in enumerate(lines, 1) if n > start and ln.lstrip().startswith(("- ", "* ", "|"))
            and kbfacts.TAG.search(ln)]


def edit_problems(rel, old, new):
    """The existing lines a change to the kb file `rel` removes or edits, from `old` to `new` text: an article's fact
    lines, a ledger's lines, a source row other than its generated `used_in`. The gap step and research add only."""
    if old is None:
        return []
    name = rel.replace("\\", "/").rsplit("/", 1)[-1]
    if name == "_sources.csv":
        def rows(t):
            return {r.get("id"): {k: v for k, v in r.items() if k != "used_in"} for r in csv.DictReader(io.StringIO(t))}
        now = rows(new or "")
        return [f"{rel}: changes source row {sid}" for sid, r in rows(old).items() if now.get(sid) != r][:6]
    if name in ("_gaps.md", "_conflicts.md"):
        keep, what = [ln for ln in old.split("\n") if ln.strip()], "an existing entry line"
    elif name.endswith(".md") and not name.startswith("_"):
        keep, what = [ln for _, ln in fact_lines(old)], "an existing fact line"
    else:
        return []
    lost = collections.Counter(keep) - collections.Counter((new or "").split("\n"))
    return [f"{rel}: removes or edits {what}: {one_line(ln, 80)}" for ln in list(lost.elements())[:6]]


def section_end(lines, at):
    """The index after the last non-blank line of the section headed at `at` (up to the next `## ` heading)."""
    end = next((i for i in range(at + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    while end - 1 > at and not lines[end - 1].strip():
        end -= 1
    return end


def add_under(text, heading, line):
    """`text` with `line` added at the end of the section `## <heading>` (the last one of that name), or in a new
    section at the end. Existing lines are never changed or moved."""
    lines = text.split("\n") if text else []
    while lines and not lines[-1].strip():
        lines.pop()
    head = f"## {heading}"
    at = max((i for i, ln in enumerate(lines) if ln.rstrip() == head), default=None)
    if at is None:
        lines += ([""] if lines else []) + [head, "", line]
    else:
        end = section_end(lines, at)
        lines[end:end] = ["", line] if end - 1 == at else [line]
    return "\n".join(lines) + "\n"


def add_fact(text, line):
    """An article's text with the fact `line` added at the end of its Facts section; ValueError without one."""
    lines = text.split("\n")
    at = next((i for i, ln in enumerate(lines) if ln.rstrip() == "## Facts"), None)
    if at is None:
        raise ValueError("the article has no Facts section")
    end = section_end(lines, at)
    prev = lines[end - 1]
    bullet = prev.lstrip().startswith(("- ", "* ")) or (prev[:1] == " " and prev.strip())
    lines[end:end] = [line] if bullet else ["", line]
    return "\n".join(lines)


def add_header_source(text, sid):
    """An article's text with `sid` in its front matter `sources: [...]` list (unchanged when it is there or the list
    is not written inline)."""
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        return text
    head = m.group(1)
    s = re.search(r"(?m)^sources:\s*\[(.*)\]\s*$", head)
    if not s or sid in [x.strip() for x in s.group(1).split(",")]:
        return text
    items = [x.strip() for x in s.group(1).split(",") if x.strip()] + [sid]
    head = head[:s.start()] + f"sources: [{', '.join(items)}]" + head[s.end():]
    return "---\n" + head + "\n---\n" + text[m.end():]


def insert_rows(text, lines):
    """A root's _sources.csv `text` with each record of `lines` (one record per line) put before the first row whose
    id sorts after its own, in kbgit.py's id order, so `kbgit.py fix` finds the file canonical; no existing line moves
    or changes."""
    import kbgit
    rows = text.split("\n")
    while rows and not rows[-1]:
        rows.pop()
    for line in lines:
        key = kbgit.id_key(line.split(",", 1)[0])
        at = next((i for i in range(1, len(rows)) if kbgit.id_key(rows[i].split(",", 1)[0]) > key), len(rows))
        rows.insert(at, line)
    return "\n".join(rows) + "\n"


# ---------------------------------------------------------------- one research run

def research_prompt(question, topic, facts):
    listed = "\n".join(f"{n}: {one_line(ln, 400)}" for n, ln in facts[:200])
    return (f"{RESEARCH_TASK}\n\nQuestion: {one_line(question, QUESTION_MAX_CHARS)}\nTopic: {topic}\n\n"
            f"Existing facts (line: text):\n{listed or '(none)'}")


def parse_research(reply):
    """[candidate dict] of a research reply, at most RESEARCH_FACTS_MAX; ValueError when it is not that JSON."""
    a, b = reply.find("{"), reply.rfind("}")
    if a < 0 or b < a:
        raise ValueError("no JSON object in the reply")
    data = json.loads(reply[a:b + 1])
    facts = data.get("facts") if isinstance(data, dict) else None
    if not isinstance(facts, list):
        raise ValueError("no facts list")
    for i, c in enumerate(facts[:RESEARCH_FACTS_MAX]):
        cw = c.get("conflicts_with") if isinstance(c, dict) else None
        if not isinstance(c, dict) or not all(isinstance(c.get(f), str) for f in RESEARCH_FIELDS) \
                or not (cw is None or (isinstance(cw, int) and not isinstance(cw, bool))):
            raise ValueError(f"fact {i} is malformed")
    return facts[:RESEARCH_FACTS_MAX]


def candidate_problems(c, facts):
    """Why a candidate fact cannot be written, before its quote is checked: its text (one sentence of our own, no
    tag, nothing the leak scan flags, not already a fact), tag, url (http(s), a public DNS name), source fields and
    reuse class, and a `conflicts_with` that names a fact line."""
    import kbcommon, kbfacts
    out = []
    text = one_line(c["text"], 10_000)
    if not 20 <= len(text) <= 600:
        out.append("text is not one short sentence")
    if kbfacts.TAG.search(text) or "topic:" in text or "\n" in c["text"].strip():
        out.append("text carries a tag, a topic marker or a line break")
    if kbcommon.leak_hits(text + " " + c["url"]):
        out.append("text or url holds what the leak scan flags")
    if c["tag"] not in RESEARCH_TAGS:
        out.append(f"tag {one_line(c['tag'], 20)!r} is not one of {', '.join(RESEARCH_TAGS)}")
    u = urlsplit(c["url"].strip())
    host = (u.hostname or "").lower()
    if u.scheme not in ("http", "https") or u.username or not HOSTNAME.fullmatch(host) \
            or host.rsplit(".", 1)[-1] in PRIVATE_TLDS:
        out.append("url is not a public http(s) page")
    if c["reuse"] not in kbcommon.REUSE:
        out.append(f"reuse {one_line(c['reuse'], 20)!r} is not a reuse class")
    if not all(one_line(c[f]) for f in ("title", "publisher", "licence")):
        out.append("title, publisher or licence is empty")
    if any(one_line(ln, 10_000).lower().lstrip("-* ").startswith(text.lower()) for _, ln in facts):
        out.append("text is already a fact")
    cw = c.get("conflicts_with")
    if cw is not None and cw not in {n for n, _ in facts}:
        out.append(f"conflicts_with {cw} names no fact line")
    return out


def write_research(g, article, accepted, conflicts, gate, day):
    """Add the accepted facts at the end of the article's Facts section (their ids in its `sources:` header), a
    _conflicts.md entry under the topic per conflict, and a source row per new url (id from kbid.source_id with the
    root's prefix, `retrieved_utc` today). [source ids]; ValueError when the article cannot take a fact."""
    import kbfacts, kbid
    src = gate.ledger(article, "_sources.csv")
    old = src.read_text(encoding="utf-8") if src.is_file() else ""
    reader = csv.DictReader(io.StringIO(old))
    by_url = {kbid.normalize_url(r.get("url") or ""): r.get("id") for r in reader}
    fields = list(reader.fieldnames or [])
    prefix, add, ids = gate.id_prefix(article), [], []
    for c in accepted + conflicts:
        url = c["url"].strip()
        sid = by_url.get(kbid.normalize_url(url))
        if not sid:
            sid = by_url[kbid.normalize_url(url)] = kbid.source_id(url, prefix)
            add.append({**{f: "" for f in fields}, "id": sid, "url": url, "title": one_line(c["title"], 200),
                        "publisher": one_line(c["publisher"], 120), "licence": one_line(c["licence"], 300),
                        "reuse": c["reuse"], "retrieved_utc": day})
        c["sid"] = sid
        ids.append(sid)
    path = gate.file(article)
    text = path.read_text(encoding="utf-8")
    facts = dict(fact_lines(text))
    for c in accepted:
        text = add_header_source(add_fact(text, f"- {one_line(c['text'], 600)} [{c['tag']} {c['sid']}]"), c["sid"])
    topic = gate.topic(article)
    ledger = gate.ledger(article, "_conflicts.md")
    ltext = ledger.read_text(encoding="utf-8") if ledger.is_file() else ""
    for c in conflicts:
        was = facts[c["conflicts_with"]]
        old_ids = sorted({i for t in kbfacts.TAG.findall(was) for i in kbfacts.ID.findall(t) if i != c["sid"]})
        body = one_line(kbfacts.TAG.sub("", was).strip().lstrip("-*| ").rstrip(" |"), 240)
        vs = f" vs {', '.join(old_ids)}" if old_ids else ""
        ltext = add_under(ltext, topic, (
            f"- **{body}** (line {c['conflicts_with']} of the article) and {c['url'].strip()} disagree: that page backs "
            f"\"{one_line(c['text'], 400)}\". Found by the query log's research {day} (finding {g['id']}); not settled. "
            f"[{c['tag']} {c['sid']}{vs}] (topic: {topic})"))
    if add:
        buf = io.StringIO()
        csv.DictWriter(buf, fieldnames=fields, lineterminator="\n").writerows(add)
        write_text(src, insert_rows(old, buf.getvalue().splitlines()))
    if accepted:
        write_text(path, text)
    if conflicts:
        write_text(ledger, ltext)
    return sorted(set(ids))


def research_one(g, entry, gate, research, day):
    """One research run on a gap finding (stage gap): the model's candidate facts (the finding promoted to
    candidate-fact), each checked (candidate_problems, then quotecheck on its page), the accepted ones written
    (write_research), then the gates: no existing fact, entry or source line edited (edit_problems), build_index and
    check.py with errors=0, no eval question newly failing and off-kb `good` not rising. A fact written promotes the
    finding to claim (`applied`); conflicts only leave it at candidate-fact (`applied`); nothing accepted, a reply
    that is not the expected JSON, or a failed gate is `rejected` with the reasons, and every file is put back. None
    when the call itself fails (no record: a later run tries again)."""
    article = g["article"]
    path = gate.file(article)
    facts = fact_lines(path.read_text(encoding="utf-8") if path.is_file() else "")
    keep = {k: v for k, v in g.items() if k != "observed"}
    promos = list(g.get("promotions") or [])
    try:
        reply = research.ask(research_prompt(entry["question"], gate.topic(article), facts))
    except OSError:
        return None

    def record(state, stage, observed, more=()):
        return {**keep, "state": state, "stage": stage, "promotions": promos + list(more), "observed": observed}
    try:
        cands = parse_research(reply)
    except ValueError as e:
        return record("rejected", "gap", {"gate": [one_line(f"reply: {e}", 160)]})
    to_fact = [{"from": "gap", "to": "candidate-fact", "by": "research"}]
    accepted, conflicts, problems = [], [], []
    for i, c in enumerate(cands):
        why = candidate_problems(c, facts)
        if not why:
            ok, said = quotecheck(c["url"], c["quote"], research.fetcher)
            why = [] if ok else [said]
        if why:
            problems += [f"fact {i}: {w}" for w in why]
        else:
            (conflicts if c.get("conflicts_with") is not None else accepted).append(c)
    if not accepted and not conflicts:
        return record("rejected", "candidate-fact", {"candidates": len(cands),
                                                     "gate": problems[:6] or ["no candidate fact"]}, to_fact)
    files = gate.research_files(article)
    saved = {p: (p.read_bytes() if p.is_file() else None) for p in files}
    base = gate.measure()
    try:
        ids = write_research(g, article, accepted, conflicts, gate, day)
    except ValueError as e:
        restore(saved)
        gate.fresh()
        return record("rejected", "candidate-fact", {"gate": [str(e)]}, to_fact)
    gate.fresh()
    after = []
    for p in files:
        old = saved[p]
        after += edit_problems(p.name, None if old is None else old.decode("utf-8"),
                               p.read_text(encoding="utf-8") if p.is_file() else "")
    if not after:
        after += gate.index_and_check()
    if not after:
        m = gate.measure()
        newly = [i for i in m["failed"] if i not in base["failed"]]
        if newly:
            after.append(f"eval fails: {', '.join(newly[:3])}")
        if m["offkb_good"] > base["offkb_good"]:
            after.append(f"off-kb good rises: {base['offkb_good']} -> {m['offkb_good']}")
    if after:
        restore(saved)
        gate.fresh()
        return record("rejected", "candidate-fact", {"gate": after[:6]}, to_fact)
    observed = {"facts": len(accepted), "conflicts": len(conflicts), "sources": ids}
    if problems:
        observed["gate"] = problems[:6]
    if accepted:
        return record("applied", "claim", observed,
                      to_fact + [{"from": "candidate-fact", "to": "claim", "by": "research"}])
    return record("applied", "candidate-fact", observed, to_fact)
