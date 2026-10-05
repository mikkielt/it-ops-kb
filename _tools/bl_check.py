"""The checks of backlog.py (kb/_self/backlog.md, Checking the backlog; kb/_self/tools.md): `validate`, the rules every
item file must meet, the knowledge an item names (`KbAtHead`, `knowledge_check`) and the state of it (`KnowledgeState`,
`knowledge_lines`), the host and user name findings `validate` reports, the selector helpers `selectors` counts with,
the repro and no-op warnings (`text_only_repro`, `trivial_command`, `noop_output`, `noop_warnings`, the warnings
`check` prints), the errors `check` adds for an open item's refused repro or check (`refused_command_errors`) and the
commands `check` and `selectors`.

Standard library only; imports `bl_base`, `bl_intake` (the program rule an open item's commands meet) and `bl_plan`
(the rules about code and its docs, which `check` runs) and never `backlog`; `bl_plan` never imports this module. `backlog.py` registers `check` and `selectors` with `bl_cli`, in
its usage order, with the handlers defined here."""
import re
import shlex
import subprocess
from pathlib import Path

import bl_authority
import bl_intake
from bl_base import (
    APPROVALS, FIELDS, GATE_KINDS, ID_RE, IN_SPRINT, KINDS, NEEDS_CHECKS, NEEDS_TOUCHES, PARENTS, PREFIX_KIND,
    PRIORITIES, Refused, SEVERITIES, SPRINT_ID_RE, SPRINT_STATUSES, START_GATE, STATUSES, TEXT_MAX, WORKED, canonical,
    REL_DIR, host_user_pieces, items_holding_names, research_in_planned, say, scope, withhold_names,
)
from bl_plan import docs_after_code, docs_warnings, shared_file_warnings, stale_touches


# ------------------------------------------------------------------ validation

def _text_ok(v):
    return isinstance(v, str) and v.strip() and len(v) <= TEXT_MAX


def _check_ok(c):
    return (isinstance(c, dict) and isinstance(c.get("run"), list) and c["run"]
            and all(isinstance(x, str) for x in c["run"]) and set(c) <= {"run", "exit", "match"}
            and isinstance(c.get("exit", 0), int) and isinstance(c.get("match", ""), str))


# ------------------------------------------------------------------ knowledge

KNOWLEDGE_KEYS = ("ask", "refs")
ANSWER_REF = re.compile(r"(?:([a-z0-9][a-z0-9-]*):)?(QK-[a-z0-9]+(?:-[a-z0-9]+)*)")  # `QK-<slug>`, `<root>:QK-<slug>`
FACT_KEY = re.compile(r"[0-9a-f]{12}")


class KbAtHead:
    """The kb roots of a clone (kb/<name>/ with a _root.md), read on demand for the references of an item's
    `knowledge`. Source ids, QK answer ids, topics and fact keys are resolved with the kb's own readers (kbid,
    kbfacts), so a fact key is the one _anchors.csv and doc2query use. Files are read from the checkout, which is
    HEAD once the work is committed."""

    def __init__(self, root):
        import kbcommon
        self.roots, self._sources, self._facts = {}, None, {}
        kb = Path(root) / "kb"
        for p in sorted(kb.iterdir()) if kb.is_dir() else []:
            if (p / kbcommon.ROOT_FILE).is_file():
                try:
                    self.roots[kbcommon.load_root(str(p)).name] = p
                except kbcommon.RootError:
                    continue  # check.py reports a malformed root

    @staticmethod
    def text(path):
        try:
            return Path(path).read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            return None

    def split(self, qpath):
        """(root name, path inside the root) of `<root>/<path>`; a path whose first part names no root is public's."""
        head, _, rest = qpath.partition("/")
        return (head, rest) if head in self.roots else ("public", qpath)

    def source_rows(self):
        """{id: row} of every root's _sources.csv."""
        import csv, io, kbcommon
        if self._sources is None:
            self._sources = {}
            for p in self.roots.values():
                text = self.text(p / kbcommon.SOURCES)
                if text:
                    for r in csv.DictReader(io.StringIO(text, newline="")):
                        self._sources.setdefault(r.get("id", ""), r)
        return self._sources

    def source_ids(self):
        """Every root's ids of its _sources.csv."""
        return set(self.source_rows())

    def answer_ids(self, root):
        """The answer ids (`## <id>. ` headings) of a root's _answers.md."""
        import kbcommon, kbid
        p = self.roots.get(root)
        return set(kbid.answer_ids(self.text(p / kbcommon.ANSWERS) or "")) if p else set()

    def is_topic(self, qpath):
        """Whether `<root>/<domain>/<slug>` (public's without the root) is an article of a root."""
        import kbfacts
        root, rel = self.split(qpath)
        p = self.roots.get(root)
        ok = p and rel and ".." not in rel.split("/") and not rel.startswith(("_", "."))
        text = self.text(p / f"{rel}.md") if ok else None
        return text is not None and kbfacts.is_article(text)

    def fact_units(self, qpath):
        """{fact key (kbfacts.fact_key): its unit} for the tagged facts of one article or data file `<root>/<path>`;
        None when there is no such file."""
        import kbfacts
        if qpath not in self._facts:
            root, rel = self.split(qpath)
            p = self.roots.get(root)
            ok = p and rel.endswith((".md", ".csv")) and ".." not in rel.split("/")
            text = self.text(p / rel) if ok else None
            if text is None:
                units = None
            elif rel.endswith(".md"):
                units = kbfacts.md_units(rel, text) if kbfacts.is_article(text) else []
            else:
                units = kbfacts.csv_units(rel, text)
            self._facts[qpath] = None if units is None else {kbfacts.fact_key(u["text"]): u for u in units
                                                             if u["tags"]}
        return self._facts[qpath]

    def fact_keys(self, qpath):
        """The fact keys (kbfacts.fact_key) of the tagged facts of one article or data file `<root>/<path>`; None
        when there is no such file."""
        units = self.fact_units(qpath)
        return None if units is None else set(units)

    def answer_question(self, root, aid):
        """The question in the heading `## <aid>. <question>` of a root's _answers.md, or None."""
        import kbcommon
        p = self.roots.get(root)
        m = re.search(rf"(?m)^## {re.escape(aid)}\.\s+(.+?)\s*$", (self.text(p / kbcommon.ANSWERS) or "") if p else "")
        return m.group(1) if m else None


def knowledge_check(bl, iid):
    """([errors], [stale]) for the `knowledge` {ask: [questions], refs: [references]} of one item. A reference is a
    topic id (`intune/win32-apps`, `<root>/<domain>/<slug>` outside public), a QK answer id (`QK-<slug>`,
    `<root>:QK-<slug>`), a source id (`S2150`, `S-o3v6ozch`) or `<root>/<path>#<fact key>` (12 hex). One absent
    from the kb is an error. A fact key no longer found in a file that exists (the fact was reworded or removed) is
    stale: a finding `check` prints and does not count as an error, since a refresh of the kb rewords facts."""
    know = bl.items[iid].get("knowledge")
    if know is None:
        return [], []
    errs, stale = [], []
    e = lambda msg: errs.append(f"{bl.label(iid)}: knowledge {msg}")  # noqa: E731
    if not isinstance(know, dict) or set(know) - set(KNOWLEDGE_KEYS):
        e("must be {ask: [questions], refs: [references]}")
        return errs, stale
    for f in KNOWLEDGE_KEYS:
        if f in know and not (isinstance(know[f], list) and all(_text_ok(x) for x in know[f])):
            e(f"{f} must be a list of non-empty texts")
    if errs:
        return errs, stale
    import kbid
    if not hasattr(bl, "kb"):
        bl.kb = KbAtHead(bl.root)
    kb = bl.kb
    for ref in (r.strip() for r in know.get("refs", [])):
        answer = ANSWER_REF.fullmatch(ref)
        if "#" in ref:
            path, _, key = ref.rpartition("#")
            if not FACT_KEY.fullmatch(key):
                e(f"ref {ref!r}: not <root>/<path>#<fact key> (12 lowercase hex characters)")
            elif kb.fact_keys(path) is None:
                e(f"ref {ref!r}: no article or data file {path!r} in the kb")
            elif key not in kb.fact_keys(path):
                stale.append(f"{bl.label(iid)}: stale knowledge: fact {key} is no longer in {path} "
                             f"(reworded or removed)")
        elif answer:
            root = answer.group(1) or "public"
            if root not in kb.roots:
                e(f"ref {ref!r}: no kb root {root!r}")
            elif answer.group(2) not in kb.answer_ids(root):
                e(f"ref {ref!r}: no such answer in root {root!r}")
        elif kbid.id_prefix(ref):
            if ref not in kb.source_ids():
                e(f"ref {ref!r}: no such source id in any root's _sources.csv")
        elif "/" in ref:
            if not kb.is_topic(ref):
                e(f"ref {ref!r}: no such topic (an article of a kb root)")
        else:
            e(f"ref {ref!r}: not a topic id, QK answer id, source id or <root>/<path>#<fact key>")
    return errs, stale


def knowledge_worked(bl, iid):
    """True when the item is todo or doing in an active sprint (its own `sprint`, or the one of the story or bug above
    it): the only items whose knowledge refs `check` validates and counts as stale. A draft, a done or a dropped item,
    or one in a planned sprint, keeps its refs unchecked, so a kb refresh that renames an article they cite does not
    turn the gate red."""
    if bl.items[iid].get("status") not in ("todo", "doing"):
        return False
    sid = bl.sprint_of(iid)
    return bool(sid) and bl.items.get(sid, {}).get("status") == "active"


def stale_knowledge(bl):
    """The stale-knowledge findings of the items `check` validates (knowledge_worked), per knowledge_check."""
    return [x for iid in bl.items if knowledge_worked(bl, iid) for x in knowledge_check(bl, iid)[1]]


OPEN_STATUSES = ("draft", "todo", "doing")  # the statuses of an item still to do
CLOSED_STATUSES = ("done", "dropped")  # an item whose gates cannot be answered again


# ------------------------------------------------------------------ selectors

def selector_of(argv):
    """(display text, targets, -k expression, -m expression) for a check argv that runs tests.py with -k (other
    pass-through flags are ignored), else None. The default -m is tests.py's own, `not stress`; a `--changed` run
    selects by the change, not by name, so it is no selector."""
    if not isinstance(argv, list) or "--changed" in argv:
        return None
    at = next((n for n, x in enumerate(argv) if isinstance(x, str) and re.split(r"[\\/]", x)[-1] == "tests.py"), None)
    if at is None:
        return None
    k = m = None
    targets = []
    rest = [x for x in argv[at + 1:] if isinstance(x, str)]
    n = 0
    while n < len(rest):
        if rest[n] in ("-k", "-m") and n + 1 < len(rest):
            if rest[n] == "-k":
                k = rest[n + 1]
            else:
                m = rest[n + 1]
            n += 2
            continue
        if not rest[n].startswith("-"):
            targets.append(rest[n])
        n += 1
    if k is None:
        return None
    return shlex.join(targets + ["-k", k] + (["-m", m] if m else [])), targets, k, m or "not stress"


def collected(root, cmd, targets, k, m):
    """How many tests pytest --collect-only selects under -m M -k K in TARGETS (default _tools), run from root: (count,
    None), or (None, why) when the collection itself failed. Exit 5 (everything deselected) is a count of 0."""
    argv = cmd + ["--collect-only", "-q", "--color=no", "-p", "no:cacheprovider", "-m", m, "-k", k] + (targets or ["_tools"])
    try:
        r = subprocess.run(argv, cwd=str(root), capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=600)
    except (OSError, subprocess.SubprocessError) as e:
        return None, type(e).__name__
    if r.returncode not in (0, 5):
        return None, f"pytest exit {r.returncode}"
    return sum(1 for ln in r.stdout.splitlines() if re.match(r"[^\s:]+\.py::", ln)), None


def selector_rows(bl, cmd):
    """[(count or None, why, selector text, item id)] for every tests.py -k selector in the checks of the open items,
    each distinct selector collected once, fewest tests first (collection errors, then zeros)."""
    seen, rows = {}, []
    for iid, it in bl.items.items():
        if it.get("kind") == "sprint" or it.get("status") not in OPEN_STATUSES:
            continue
        for c in it.get("checks", []) or []:
            sel = selector_of(c.get("run") if isinstance(c, dict) else None)
            if sel is None:
                continue
            text, targets, k, m = sel
            if text not in seen:
                seen[text] = collected(bl.root, cmd, targets, k, m)
            rows.append((*seen[text], text, iid))
    return sorted(rows, key=lambda r: (-1 if r[0] is None else r[0], r[2], r[3]))


# ------------------------------------------------------------------ knowledge state

STATES = ("sufficient", "partial", "unknown", "stale", "conflicting")
SETTLED_NOTE = re.compile(r"(?:^|\s)- (?:(?:Resolved|Superseded) \d{4}-\d{2}-\d{2}\b"
                          r"|Reviewed \d{4}-\d{2}-\d{2}, not a source disagreement\b)")  # the notes that close an entry


class KnowledgeState:
    """The state of each ask and each ref of an item's `knowledge`, derived from the kb on every call and never
    stored: the pack (kbfacts.pack: no network, no model) of the ask, or of the text a ref stands for (a topic's
    title, a QK answer's question, a source's title, a fact's own text), then, in this order:
      unknown      the ref is not in the kb, or the pack's coverage is `none` (or the pack could not run);
      stale        a fact key no longer found in its file, or a source that the ref is, that the fact cites or that
                   the pack cites has `superseded_by` set in _sources.csv;
      conflicting  the ref's article (a source ref: any entry naming it), or the pack's lead article, has an open
                   entry in _conflicts.md: an entry with no `- Resolved <date>`, `- Superseded <date>` or
                   `- Reviewed <date>, not a source disagreement` note (`Reviewed <date>, still open` keeps it open);
      partial      coverage `weak`, or `good` with a `check:` line (a possible false good);
      sufficient   coverage `good` with no `check:` line.
    A pack whose coverage is `none` shows no article or source, so only what the ref itself is (its own fact, source
    or article) can make it stale or conflicting. The pack is the one `rag.py pack "<text>"` prints, in this process."""

    def __init__(self, bl):
        import kbcommon, kbfacts
        if not hasattr(bl, "kb"):
            bl.kb = KbAtHead(bl.root)
        self.kb, self.kf, self.kc, self._packs, self._open = bl.kb, kbfacts, kbcommon, {}, None

    def pack(self, question):
        if question not in self._packs:
            self._packs[question] = self.kf.pack(question)
        return self._packs[question]

    def open_conflicts(self):
        """([(entry, linked topics)]) of the entries of every root's _conflicts.md that no Resolved, Superseded or
        "Reviewed <date>, not a source disagreement" note closes."""
        if self._open is None:
            kf = self.kf
            entries = kf.link_entries(kf.ledger_entries(self.kc.CONFLICTS))
            self._open = [e for e in entries if not SETTLED_NOTE.search(e["text"])]
        return self._open

    def topic_of(self, qpath):
        """The qualified topic of an article or of a data file that an article lists, or None."""
        kf = self.kf
        meta = kf.articles().get(qpath)
        if meta:
            return meta["topic"]
        return next((t for t, files in kf.topic_files().items() if qpath in files), None)

    def conflict_of(self, qpaths, source_id=None):
        """The `file:line` of an open conflict entry that names one of the articles' topics (or the source id)."""
        topics = {t for t in map(self.topic_of, qpaths) if t}
        if not topics and not source_id:
            return None
        for e in self.open_conflicts():
            if topics & set(e["explicit"]) or (source_id and source_id in e["ids"]):
                return f"{e['file']}:{e['line']}"
        return None

    def superseded(self, ids):
        rows = self.kb.source_rows()
        return [(i, (rows[i].get("superseded_by") or "").strip()) for i in dict.fromkeys(ids)
                if i in rows and (rows[i].get("superseded_by") or "").strip()]

    def judge(self, question, articles=(), ids=(), source=None):
        """(state, why) for a question; `articles` the qualified paths and `ids` the source ids the ref itself is or
        cites; `source` the source id a source ref is."""
        try:
            res = self.pack(question)
        except Exception as ex:  # a kb the pack cannot read: no evidence, so no better than unknown
            return "unknown", f"the pack could not run: {type(ex).__name__}: {ex}"
        covered = res["verdict"] != "none"
        old = self.superseded(list(ids) + (res["sources"] if covered else []))
        if old:
            return "stale", "; ".join(f"source {i} is superseded by {new}" for i, new in old)
        clash = self.conflict_of(list(articles) + (res["paths"][:1] if covered else []), source)
        if clash:
            return "conflicting", f"open entry at {clash}"
        if not covered:
            return "unknown", "the kb does not cover it: coverage none"
        if res["verdict"] == "weak":
            return "partial", "coverage weak"
        if res["unmatched"] or res["spread"]:
            return "partial", "coverage good, but the pack's check: line flags a possible false good"
        return "sufficient", ""

    def of_ask(self, question):
        return self.judge(question)

    def of_ref(self, ref):
        """(state, why) for one reference, resolved as knowledge_check resolves it."""
        kb, ref = self.kb, ref.strip()
        answer = ANSWER_REF.fullmatch(ref)
        if "#" in ref:
            path, _, key = ref.rpartition("#")
            units = kb.fact_units(path) if FACT_KEY.fullmatch(key) else None
            if units is None:
                return "unknown", "no such article or data file, or not a fact key"
            if key not in units:
                return "stale", f"fact {key} is no longer in {path}, reworded or removed"
            u = units[key]
            root, rel = kb.split(path)
            text = self.kf.TAG.sub("", u["text"]).strip(" |")
            return self.judge(text, [f"{root}/{rel}"], [i for t in u["tags"] for i in t["ids"]])
        if answer:
            root = answer.group(1) or "public"
            question = kb.answer_question(root, answer.group(2)) if root in kb.roots else None
            return self.judge(question, ()) if question else ("unknown", "no such answer")
        import kbid
        if kbid.id_prefix(ref):
            row = kb.source_rows().get(ref)
            return self.judge(row.get("title") or row.get("url") or ref, (), [ref], ref) if row else (
                "unknown", "no such source id")
        if "/" in ref and kb.is_topic(ref):
            root, rel = kb.split(ref)
            title = self.kf.front_matter(kb.text(kb.roots[root] / f"{rel}.md") or "")["title"]
            return self.judge(title or rel, [f"{root}/{rel}.md"])
        return "unknown", "no such topic"


# The clone whose kb this process reads: the pack, the article index and the ledgers (kbfacts, kbcommon) read the
# clone the tools run from, whatever --root names.
KB_HOME = Path(__file__).resolve().parent.parent
OTHER_CLONE = ("knowledge state not derived: --root names another clone, and this process's pack and ledgers read "
               "the kb of the clone its tools run from; run that clone's own _tools/backlog.py")


def other_clone(bl):
    """True when bl.root is not the clone whose kb this process reads (KB_HOME): its knowledge state would mix that
    clone's refs with this clone's pack and conflicts (BG-aycs7kml)."""
    return Path(bl.root).resolve() != KB_HOME


def knowledge_todo(bl, iid):
    """[(kind, text)] for each ask and each ref of an item's `knowledge`, `kind` `ask` or `ref`."""
    know = bl.items[iid].get("knowledge")
    if not isinstance(know, dict):
        return []
    return [(k, x) for k, f in (("ask", "ask"), ("ref", "refs")) for x in (know.get(f) if isinstance(know.get(f), list) else [])
            if isinstance(x, str) and x.strip()]


def knowledge_states(bl, iid):
    """[(kind, text, state, why)] for each ask and each ref of an item's `knowledge`, `kind` `ask` or `ref`; [] for an
    item with no asks or refs, without loading the pack (a malformed field is `check`'s to report), and for an item of
    another clone (other_clone), whose state this process cannot derive."""
    todo = knowledge_todo(bl, iid)
    if not todo or other_clone(bl):
        return []
    if not hasattr(bl, "state"):
        bl.state = KnowledgeState(bl)
    out = []
    for kind, text in todo:
        state, why = bl.state.of_ask(text) if kind == "ask" else bl.state.of_ref(text)
        out.append((kind, text.strip(), state, why))
    return out


def knowledge_lines(bl, iid, indent="  "):
    """One line per ask and per ref of an item's `knowledge`: `knowledge <state> ask|ref: <text>` and, for any state
    but sufficient, why. [] for an item with no asks or refs (knowledge_states); one line saying the state is not
    derived for an item of another clone (other_clone)."""
    if other_clone(bl) and knowledge_todo(bl, iid):
        return [f"{indent}{OTHER_CLONE}"]
    return [f"{indent}knowledge {state:<11} {kind}: {text}" + (f" ({why})" if why else "")
            for kind, text, state, why in knowledge_states(bl, iid)]


def item_strings(v, path=""):
    """(field path, text) of every string value of an item's JSON, dict keys left out: `gates[0].question`."""
    if isinstance(v, str):
        yield path, v
    elif isinstance(v, dict):
        for k, x in v.items():
            yield from item_strings(x, f"{path}.{k}" if path else k)
    elif isinstance(v, list):
        for n, x in enumerate(v):
            yield from item_strings(x, f"{path}[{n}]")


def item_leak_hits(text, allow):
    """[(kind, value)] the leak scan finds in one text of an item, read as the scan of tracked files reads a file."""
    import kbpublic
    return kbpublic.file_hits("item.json", text, allow)


def leak_errors(bl):
    """One error for each field of each item that holds a leak-scan hit, naming the item id, the field and the kinds
    (secret, home, ip, email, guid), never the value, and withholding the title of an item whose title holds one; the allowlist is the clone's _tools/tests_allowlist.txt."""
    import kbpublic
    path = bl.root / kbpublic.ALLOWLIST_PATH
    try:
        allow = kbpublic.parse_allowlist(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, UnicodeDecodeError):
        allow = {}
    errs = []
    for iid, it in bl.items.items():
        for field, text in item_strings(it):
            kinds = sorted({k for k, _ in item_leak_hits(text, allow)})
            if kinds:
                if field == "title":
                    bl.withheld.add(iid)  # label() prints a title, which holds the hit: no error prints it
                errs.append(f"{iid}: field {field} has a leak-scan hit ({', '.join(kinds)}; value not "
                            f"printed): write a placeholder instead (kb/_self/backlog.md, Writing about items)")
    return errs


def validate(bl, pieces=None):
    errs = list(bl.load_errors)
    errs += leak_errors(bl)
    named = items_holding_names(bl, pieces)
    bl.withheld |= set(named)
    for iid, hits in named.items():
        for path, kind in hits:
            errs.append(f"{bl.label(iid)}: field {path} holds a piece of this host's "
                        f"{'computer' if kind == 'host' else 'user'} name (read from the environment, not printed); "
                        f"write a placeholder instead")
    for iid, it in bl.items.items():
        e = lambda msg, iid=iid: errs.append(f"{bl.label(iid)}: {msg}")  # noqa: E731
        if it.get("id") != iid:
            e(f"id {it.get('id')!r} does not match its file name")
        if not ID_RE.fullmatch(iid):
            e("id is not <EP|ST|TK|SB|BG|SP>-<8 base32 characters>")
        kind = it.get("kind")
        if kind not in KINDS:
            e(f"kind {kind!r} is not one of {', '.join(KINDS)}")
            continue
        if ID_RE.fullmatch(iid) and PREFIX_KIND[iid[:2]] != kind:
            e(f"id prefix {iid[:2]} does not match kind {kind}")
        unknown = set(it) - FIELDS
        if unknown:
            e(f"unknown fields {sorted(unknown)}")
        if not _text_ok(it.get("title")):
            e("title missing or longer than TEXT_MAX")
        for f in ("goal", "notes"):
            if f in it and not _text_ok(it[f]):
                e(f"{f} empty or longer than TEXT_MAX")
        if "links" in it and not (isinstance(it["links"], list) and all(_text_ok(x) for x in it["links"])):
            e("links must be a list of texts (each non-empty, at most TEXT_MAX)")
        if bl.raw.get(iid) != canonical(it):
            e("not in canonical form (python3 _tools/backlog.py fmt)")
        if kind == "sprint":
            if it.get("status") not in SPRINT_STATUSES:
                e(f"sprint status must be one of {SPRINT_STATUSES}")
            if not _text_ok(it.get("goal")):
                e("a sprint needs a goal")
            if not any(g.get("id") == START_GATE for g in it.get("gates", []) if isinstance(g, dict)):
                e("a sprint needs its start gate")
            reviews = [i for i in bl.sprint_items(iid) if bl.items[i].get("review")]
            if len(reviews) != 1:
                e(f"a sprint needs exactly one review story (has {len(reviews)})")
        else:
            if it.get("status") not in STATUSES:
                e(f"status must be one of {STATUSES}")
            if it.get("priority") not in PRIORITIES:
                e(f"priority must be one of {PRIORITIES}")
            if not isinstance(it.get("rank", 0), int):
                e("rank must be an integer")
            if kind != "subtask" and kind != "epic" and not _text_ok(it.get("goal")):
                e("goal (the end state) missing")
        par = it.get("parent")
        if par:
            if par not in bl.items:
                e(f"parent {par} does not exist")
            elif bl.items[par].get("kind") not in PARENTS[kind]:
                e(f"a {kind} cannot sit under a {bl.items[par].get('kind')}")
        elif kind in ("task", "subtask"):
            e(f"a {kind} needs a parent ({' or '.join(PARENTS[kind])})")
        if "sprint" in it:
            s = it["sprint"]
            if kind not in IN_SPRINT:
                e("only stories and bugs name a sprint; tasks and subtasks follow theirs")
            elif s not in bl.items or bl.items[s].get("kind") != "sprint":
                e(f"sprint {s} does not exist")
        if it.get("review") and (kind != "story" or not it.get("sprint")):
            e("a review item is a story in a sprint")
        if "goal_research" in it and (it["goal_research"] is not True or kind != "story" or not it.get("sprint")
                                 or it.get("review")):
            e("goal_research is true on the goal research story of a sprint, a story in it that is not the review")
        if kind == "bug":
            if it.get("severity") not in SEVERITIES:
                e(f"a bug needs a severity {SEVERITIES}")
            if not _check_ok(it.get("repro")):
                e("a bug needs a repro check (a command that fails until it is fixed)")
            if "repro_reason" in it and not _text_ok(it["repro_reason"]):
                e("repro_reason must be text: why the repro can only match text in a file")
        elif "severity" in it or "repro" in it or "repro_reason" in it:
            e("severity and repro are for bugs only")
        checks = it.get("checks", [])
        if not isinstance(checks, list) or not all(_check_ok(c) for c in checks):
            e("checks must be a list of {run: [argv...], exit?: int, match?: regex}")
        elif kind in NEEDS_CHECKS and not checks and not (kind == "bug" and it.get("repro")):
            e("checks missing: the commands that prove the end state")
        for c in checks if isinstance(checks, list) else []:
            if isinstance(c, dict) and c.get("match"):
                try:
                    re.compile(c["match"])
                except re.error as x:
                    e(f"check match is not a regex: {x}")
        touches = it.get("touches", [])
        if not isinstance(touches, list) or not all(isinstance(t, str) and t for t in touches):
            e("touches must be a list of path globs")
        elif kind in NEEDS_TOUCHES and not touches:
            e("touches missing: the path globs this item may change")
        for f in ("depends_on", "relates_to"):
            for d in it.get(f, []):
                if d not in bl.items:
                    e(f"{f} names {d}, which does not exist")
                elif d == iid:
                    e(f"{f} names the item itself")
                elif f == "depends_on" and bl.items[d].get("status") == "dropped":
                    e(f"depends on dropped {bl.label(d)}")
        gate_ids = set()
        for g in it.get("gates", []):
            if not isinstance(g, dict) or not _text_ok(g.get("question", "")) or g.get("kind") not in GATE_KINDS:
                e("a gate needs id, kind (blocking|provisional) and question")
                continue
            if not g.get("id"):
                e("a gate has no id")
            elif g["id"] in gate_ids:  # readers take the first gate with an id: a repeat can hide the real one
                e(f"gate id {g['id']!r} is repeated: a gate id names one gate")
            gate_ids.add(g.get("id"))
            if g["kind"] == "provisional" and not g.get("recommendation"):
                e(f"provisional gate {g['id']} needs a recommendation")
            if "answer" in g and g.get("by") not in ("operator", "agent"):
                e(f"gate {g['id']}: an answer needs by: operator|agent")
            if "class" in g and g["class"] not in bl_authority.CLASSES:
                e(f"gate {g['id']}: class {g['class']!r} is not one of {', '.join(bl_authority.CLASSES)}")
            elif bl_authority.lowered(it, g):
                e(f"gate {g['id']}: class {g['class']} is lower than {bl_authority.derived_class(it, g)}, which its "
                  "item's touches and its question give it")
            settled = it.get("status") in CLOSED_STATUSES and g.get("by") == "agent" \
                and "answer" in g  # a warning (refused_answer_warnings), not an error
            if bl_authority.derived_class(it, g) in bl_authority.OPERATOR_CLASSES and not settled:
                if g["kind"] == "provisional" and g.get("by") != "operator":  # one the operator answered stands
                    e(f"gate {g['id']} is class {bl_authority.derived_class(it, g)} and provisional: it is blocking, "
                      "only the operator answers it")
                if g.get("by") == "agent":
                    e(f"gate {g['id']} is class {bl_authority.derived_class(it, g)}: an answer by agent is not "
                      "the operator's")
            if g["kind"] == "blocking" and g.get("by") == "agent":
                e(f"gate {g['id']} is blocking: only the operator answers it")
            hc = g.get("host_check")
            if "host_check" in g and not (isinstance(hc, dict) and isinstance(hc.get("run"), list) and hc["run"]
                                          and all(isinstance(w, str) and w for w in hc["run"])):
                e(f"gate {g['id']}: host_check needs run: a command as a list of words")
            for opt, how in (g.get("do") or {}).items() if isinstance(g.get("do", {}), dict) else ():
                if opt not in g.get("options", []):
                    e(f"gate {g['id']}: do names {opt!r}, which is not one of its options")
                elif not (isinstance(how, list) and how and all(isinstance(w, str) and w for w in how)
                          or isinstance(how, str) and how in bl.items):
                    e(f"gate {g['id']}: do for {opt!r} needs an argv (a list of words) or the id of an item")
            if "do" in g and not isinstance(g["do"], dict):
                e(f"gate {g['id']}: do maps an option to its command")
            if "host_checked" in g and not (isinstance(g["host_checked"], dict)
                                            and isinstance(g["host_checked"].get("ok"), bool)):
                e(f"gate {g['id']}: host_checked needs ok: true or false")
        if "recurs" in it:
            rc = it["recurs"]
            if not isinstance(rc, list) or not all(isinstance(r, str) and SPRINT_ID_RE.fullmatch(r) for r in rc):
                e("recurs must be a list of sprint ids (SP-...): the sprints the work came back in")
            elif len(set(rc)) != len(rc):
                e("recurs names a sprint twice")
        trig = it.get("trigger")
        if trig is not None and not (isinstance(trig, dict) and _text_ok(trig.get("when", ""))
                                     and isinstance(trig.get("fired", False), bool)):
            e("trigger must be {when: text, fired: bool}")
        if knowledge_worked(bl, iid):
            errs.extend(knowledge_check(bl, iid)[0])
        st = it.get("status")
        if st == "doing" and not it.get("claimed_by"):
            e("status doing needs claimed_by")
        sp = bl.sprint_of(iid) if kind != "sprint" else None
        if st in WORKED and sp in bl.items and bl.items[sp].get("status") == "planned" \
                and not (st in ("doing", "done") and research_in_planned(bl, iid)):
            e(f"status {st} while its sprint {bl.label(sp)} is planned: not in a started sprint "
              f"(a planned sprint's items stay draft until backlog.py start)")
        if st == "done" and kind in NEEDS_CHECKS + ("bug",) and not it.get("evidence"):
            e("status done without evidence (set only by backlog.py done)")
    # cycles over depends_on and parent
    state = {}

    def visit(i, path):
        state[i] = 1
        for d in bl.items[i].get("depends_on", []) + ([bl.items[i]["parent"]] if bl.items[i].get("parent") else []):
            if d not in bl.items:
                continue
            if state.get(d) == 1:
                errs.append(f"cycle: {' -> '.join(bl.label(x) for x in path + [d])}")
            elif not state.get(d):
                visit(d, path + [d])
        state[i] = 2

    for i in bl.items:
        if not state.get(i):
            visit(i, [i])
    return errs




# What a tool prints when it ran but did nothing in this clone (a missing remote, an empty selection): a check or repro
# whose output says so proves nothing, whatever its exit code (BG-uqmjlqfl's repro, publish --dry-run, printed the
# first two in a clone with no public remote and passed).
NOOP_MARKERS = (re.compile(r"\bno public remote\b", re.I),
                re.compile(r"\bnothing (?:published|to publish|to push|to land|to do|to check|to run)\b", re.I),
                re.compile(r"\bno test can be affected\b", re.I))
TEST_SUMMARY = re.compile(r"^=*\s*(\d+ [a-z]+(?:, \d+ [a-z]+)*) in \d+(?:\.\d+)?s\b", re.M)
RAN_TESTS = {"passed", "failed", "error", "errors", "xfailed", "xpassed"}
TRIVIAL_CMDS = {"true", ":", "echo", "printf", "rem"}
TRIVIAL_CODE = re.compile(r"(?:pass|None|True|0|\.\.\.|(?:sys\.)?exit\(\s*0?\s*\)|quit\(\s*\)|import sys"
                          r"|print\([^()]*\)|true|:|exit(?: 0)?|echo\b.*)?")
SHELLS = {"sh", "bash", "zsh", "cmd", "pwsh", "powershell"}
HOST_BOUND_GATE = "host-bound"  # the gate whose operator answer accepts a proof that does nothing in this clone
HOST_BOUND_ACCEPTS = APPROVALS + ("accept", "accepted")


def noop_output(out):
    """Why a check's or repro's output says it did nothing in this clone, or None: a known no-op marker
    (NOOP_MARKERS), or a pytest summary where every selected test was skipped."""
    for rx in NOOP_MARKERS:
        m = rx.search(out)
        if m:
            return f"its output says it did nothing here ({m.group(0)!r})"
    for m in TEST_SUMMARY.finditer(out):
        kinds = {w.split()[1] for w in m.group(1).split(", ")}
        if "skipped" in kinds and not kinds & RAN_TESTS:
            return f"every test it selected was skipped ({m.group(1)})"
    return None


def trivial_command(argv):
    """Why a check's command runs no test or tool code, or None: a shell builtin (true, echo), or a python -c or
    shell -c string of statements that only pass, print or exit 0. It passes whatever the code does."""
    if not argv:
        return None
    base, code = _command_code(argv)
    if base in TRIVIAL_CMDS:
        return f"it runs {base}, no test or tool"
    if code is not None and (base.startswith("python") or base in SHELLS):
        if all(TRIVIAL_CODE.fullmatch(s.strip()) for s in re.split(r"[;\n]", code)):
            return f"its code ({code.strip()[:60]!r}) only passes, prints or exits 0"
    return None


# A repro that only matches text in a file proves the text, not the behaviour: BG-qtphqxt2's rejected the literal
# '>&2', which the fix met by writing '>& 2'; BG-g6qpxe5x's was a regex over a test's text; BG-rrht7uts's grepped
# _tools/ for 'worktrees' and passed on a fix that did not work. `new` refuses one without a stated reason
# (--repro-reason, kept as the item's repro_reason) and `check` warns of an open bug's.
GREP_CMDS = {"grep", "egrep", "fgrep", "rg", "ag", "findstr", "select-string", "sls"}
TEXT_FILTERS = {"cat", "head", "tail", "tr", "sort", "uniq", "cut", "wc", "nl", "tac", "rev", "fold", "type", "gc",
                "get-content"}  # read-only filters of a file's text: no match of their own
MATCHERS = {"awk", "gawk", "mawk", "nawk", "sed"}  # match text like grep does
SUBSTITUTION = re.compile(r"\$\(\s*!?\s*(git\s+grep|[\w./\\-]+)|`\s*(git\s+grep|[\w./\\-]+)")
FILE_ARG = re.compile(r"[\w./\\-]+\.\w{1,5}")  # a file named with an extension; an awk or sed program is not one
READS_FILE = re.compile(r"\bopen\(|\.read_text\(|\.read_bytes\(")
TEXT_MODULES = {"sys", "re", "json", "csv", "pathlib", "os", "io", "fnmatch", "glob", "ast", "tomllib", "itertools",
                "functools", "collections", "string"}
IMPORTS = re.compile(r"(?:^|[;\n])\s*(?:from\s+([\w.]+)\s+import\b|import\s+([\w.]+(?:\s*,\s*[\w.]+)*))")
RUNS_CODE = re.compile(r"\b(?:subprocess|runpy|importlib|exec|eval|compile|__import__|system|popen|spawn\w*"
                       r"|sys\.path)\b")
TOOL_SOURCE = re.compile(r"_tools/[\w./-]+\.py\b")


def _command_code(argv):
    """(base command name, the -c / /c / -Command string or None) of a check's argv."""
    base = re.sub(r"\.exe$", "", Path(argv[0]).name.lower()) if argv else ""
    code = argv[2] if len(argv) > 2 and argv[1].lower() in ("-c", "/c", "-command") else None
    return base, code


def _is_grep(words):
    """True when a command's words (a leading ! dropped) run a grep: GREP_CMDS or git grep."""
    words = words[1:] if words[:1] == ["!"] else words
    base = re.sub(r"\.exe$", "", Path(words[0]).name.lower()) if words else ""
    return base in GREP_CMDS or (base == "git" and words[1:2] == ["grep"])


def _base(words):
    """The lower-cased program name of a command's words (a leading ! dropped, a directory and .exe removed)."""
    words = words[1:] if words[:1] == ["!"] else words
    return re.sub(r"\.exe$", "", Path(words[0]).name.lower()) if words else ""


def _substituted(words):
    """The program names of the commands a segment substitutes with $( ) or backticks (git grep counts as grep)."""
    out = []
    for m in SUBSTITUTION.finditer(" ".join(words)):
        first = (m.group(1) or m.group(2) or "").split()
        out.append("grep" if first[:1] == ["git"] else re.sub(r"\.exe$", "", Path(first[0]).name.lower()) if first else "")
    return out


def _tests_text(words):
    """(reads, matches) for a `test` or `[` segment that tests the output of a substituted command: it reads text when
    that command is a grep, a text filter or a matcher, and matches text when it is a grep or a matcher."""
    if _base(words) not in ("test", "[", "[["):
        return False, False
    subs = _substituted(words)
    return (any(s in GREP_CMDS | TEXT_FILTERS | MATCHERS for s in subs), any(s in GREP_CMDS | MATCHERS for s in subs))


def _reads_text(words):
    """True when a shell segment only reads text: a grep, a text filter, a matcher, or a test of one's output."""
    return _is_grep(words) or _base(words) in TEXT_FILTERS | MATCHERS or _tests_text(words)[0]


def _matches_text(words):
    """True when a shell segment matches text: a grep, a matcher, or a test of the output of one."""
    return _is_grep(words) or _base(words) in MATCHERS or _tests_text(words)[1]


def text_only_repro(argv):
    """Why a repro only matches text in a file and runs no behaviour, or None: grep (git grep, rg, findstr,
    Select-String), awk or sed run over a file, a shell -c of nothing but greps, or of text filters (cat, head, sort...)
    feeding a grep, awk or sed, or testing the output of one (`test -z "$(grep ...)"`), or a python -c that reads a file
    and imports only text modules (TEXT_MODULES), running no other code. It names a _tools/ source file it reads. A
    script repro is not judged."""
    if not argv:
        return None
    base, code = _command_code(argv)
    if _is_grep(argv[:2]):
        what = "it greps a file"
    elif code is not None and base in SHELLS:
        segs = [s.split() for s in re.split(r"&&|\|\||[;|\n]", code)]
        segs = [w for w in segs if w and w[0] not in ("set", "exit")]
        if segs and all(map(_is_grep, segs)):
            what = "its shell code only greps files"
        elif segs and all(map(_reads_text, segs)) and any(map(_matches_text, segs)):
            what = "its shell code only reads files through grep, awk, sed or a text filter"
        else:
            what = None
    elif base in MATCHERS and any(FILE_ARG.fullmatch(a) for a in argv[2:]):
        what = f"it runs {base} over a file"
    elif code is not None and base.startswith("python"):
        mods = {m.split(".")[0].strip() for pair in IMPORTS.findall(code) for g in pair if g for m in g.split(",")}
        ok = READS_FILE.search(code) and mods <= TEXT_MODULES and not RUNS_CODE.search(code)
        what = "its python code only reads a file and tests its text" if ok else None
    else:
        what = None
    if not what:
        return None
    src = sorted(set(TOOL_SOURCE.findall(" ".join(argv))))
    return f"{what}{', reading source of ' + ', '.join(src) + ' for a string' if src else ''}"


def repro_text_warnings(bl):
    """check's warnings: an open bug whose repro only matches text in a file (text_only_repro) with no repro_reason."""
    out = []
    for iid, it in sorted(bl.items.items()):
        rp = it.get("repro")
        if it.get("kind") != "bug" or it.get("status") not in OPEN_STATUSES or it.get("repro_reason") \
                or not _check_ok(rp):
            continue
        why = text_only_repro(rp["run"])
        if why:
            out.append(f"{bl.label(iid)}: the repro only matches text in a file ({why}), so it can pass on a fix that "
                       "does not work or fail on one that does: run the behaviour (a test, a command on a planted "
                       "input), or state why it cannot in repro_reason")
    return out


STATE_READER = re.compile(r"\bitems?'?s?\s+(?:status|presence)\b|\b(?:status|presence) of (?:an?|each|every|the)? ?items?\b"
                          r"|\bbacklog state\b|\breads? (?:the )?backlog\b", re.I)
STATE_PATHS = (("done", r"(?<![a-z])done(?![a-z])"),
               ("drop inside a sprint", r"drop\w*[\s_-]*(?:in|inside)[\s_-]*(?:a[\s_-]*)?sprint"),
               ("drop outside a sprint", r"drop\w*[\s_-]*(?:out|outside)"),
               ("close", r"(?<![a-z])close(?![a-z])"), ("release", r"(?<![a-z])release(?![a-z])"))


def state_path_warnings(bl):
    """check's warnings: an open story, task or bug whose goal says its code reads an item's status or presence
    (STATE_READER) and whose checks name fewer than every way that state changes (STATE_PATHS: done, a drop inside and
    outside a sprint, close, release), each way found by its words in the checks' commands (a -k selector names a
    test by them). It answers SP-jtfo4ael, where a sweep passed checks that never dropped an item outside a sprint."""
    out = []
    for iid, it in sorted(bl.items.items()):
        if it.get("kind") not in ("story", "task", "bug") or it.get("status") not in OPEN_STATUSES \
                or not isinstance(it.get("goal"), str) or not STATE_READER.search(it["goal"]):
            continue
        text = " ".join(" ".join(c["run"]) for c in it.get("checks", []) if _check_ok(c)).lower()
        absent = [name for name, rx in STATE_PATHS if not re.search(rx, text)]
        if absent:
            out.append(f"{bl.label(iid)}: its goal reads an item's status or presence, and its checks name no test "
                       f"for these ways the state changes: {', '.join(absent)} (a check per path, "
                       "`-k` selectors naming them: kb/_self/backlog.md, planning)")
    return out


def refused_answer_warnings(bl):
    """check's warnings: a gate of a done or dropped item, of a class only the operator answers, that an agent
    answered. An open item's such gate is an error (validate); a closed item's cannot be answered again by
    the item's work, so the operator re-confirms it. `answer` stays strict: a new answer in such a class is refused."""
    out = []
    for iid, it in sorted(bl.items.items()):
        if it.get("status") not in CLOSED_STATUSES:
            continue
        for g in it.get("gates", []):
            if not isinstance(g, dict) or g.get("by") != "agent" or "answer" not in g:
                continue
            cls = bl_authority.derived_class(it, g)
            if cls in bl_authority.OPERATOR_CLASSES:
                out.append(f"{bl.label(iid)}: gate {g.get('id')} class {cls}: answered by {g['by']} in a refused "
                           "class: the operator re-confirms")
    return out


def gate_do_warnings(bl):
    """check's warnings, one for each option of an unanswered blocking gate of an open item that carries no `do` (the
    argv that carries the option out, or the id of the item whose work adds that command), so an answer would wait on
    a command nobody planned; an option with one does not silence the others (BG-ynaowysf)."""
    out = []
    for iid, it in sorted(bl.items.items()):
        if it.get("status") not in OPEN_STATUSES:
            continue
        for g in it.get("gates", []):
            if not (isinstance(g, dict) and g.get("kind") == "blocking" and "answer" not in g
                    and g.get("id") != START_GATE):
                continue
            do = g.get("do") if isinstance(g.get("do"), dict) else {}
            for opt in g.get("options") or []:
                if not do.get(opt):
                    out.append(f"{bl.label(iid)}: blocking gate {g.get('id')} has no `do` for option {opt!r}, the "
                               "command that carries it out or the item that adds it (gate add --do OPTION=CMD|ID)")
    return out


def item_files_only(touches):
    """True when every touches glob, of at least one, names backlog item files only (inside kb/_self/backlog/): done
    can never close such an item, since it needs a KB-Work commit that changes a file other than item files."""
    globs = [t for t in touches or [] if isinstance(t, str) and t]
    return bool(globs) and all(t.startswith(REL_DIR + "/") for t in globs)


ITEM_FILES_ROUTE = ("its touches are item files only, which done can never close (done needs a KB-Work commit that "
                    "changes another file): land the fix as a planning commit, then close the item with backlog.py "
                    "drop ID --why naming the fixing commit")


def item_files_warnings(bl):
    """check's warnings: an open story, task, subtask or bug whose scope (its touches and its descendants') is item
    files only (item_files_only), naming the route that closes it (BG-2hxjopue)."""
    return [f"{bl.label(iid)}: {ITEM_FILES_ROUTE}" for iid, it in sorted(bl.items.items())
            if it.get("kind") in ("story", "task", "subtask", "bug") and it.get("status") in OPEN_STATUSES
            and item_files_only(scope(bl, iid))]


def is_test_run(argv):
    """True when a check runs tests: tests.py or pytest, so it exercises the code it proves."""
    return any(Path(x).name == "tests.py" for x in argv[1:3]) or "pytest" in argv[:3]


def noop_warnings(it, repro_out=""):
    """new's warnings of a proof that may do nothing in this clone: a check or repro that runs no test or tool code,
    a bug's failing repro whose output says it did nothing here, and a bug whose repro runs a tool against this
    clone's state with no check that runs tests (done refuses such a repro that passes doing nothing)."""
    out = []
    for c in it.get("checks", []) + ([it["repro"]] if it.get("repro") else []):
        why = trivial_command(c["run"])
        if why:
            out.append(f"{shlex.join(c['run'])} proves nothing: {why}, so it passes whatever the code does")
    if it.get("repro"):
        run, tests = it["repro"]["run"], any(is_test_run(c["run"]) for c in it.get("checks", []))
        why = noop_output(repro_out)
        if why:
            out.append(f"the repro failed while doing nothing in this clone ({why}): its failure may not be the "
                       "defect's, and it can pass here the same way")
        if not tests and not is_test_run(run) and len(run) > 1 and run[1].endswith(".py"):
            out.append(f"the repro runs {run[1]} against this clone's state and no --check runs tests: should it pass "
                       "here doing nothing, done refuses it; add --check 'python3 _tools/tests.py -k <the test that "
                       "plants the defect>'")
    return out


def refused_command_errors(bl):
    """check's errors: an open item whose repro or check bl_intake.check_program_refusal refuses or trivial_command
    flags, the predicates test_open_repros_run_headless and test_done_flags_noop_check_real_backlog_commands assert
    over the live item files. new only warns of them, so without this an item file passed the fast content gate and
    turned those tests red for every later landing that selected them. The error names the part, never its command:
    the command may hold a value the leak scan withholds."""
    out = []
    for iid, it in sorted(bl.items.items()):
        if it.get("status") not in OPEN_STATUSES:
            continue
        checks = it.get("checks") or []
        parts = ([("repro", it["repro"])] if it.get("repro") else []) \
            + [(f"check {n}" if len(checks) > 1 else "check", c) for n, c in enumerate(checks, 1)]
        for name, part in parts:
            if not _check_ok(part):
                continue
            if bl_intake.check_program_refusal(part["run"]):
                why = "its program is not python3 on a _tools/ script or inline code (bl_intake.check_program_refusal)"
            elif trivial_command(part["run"]):
                why = "it runs no test or tool code, so it passes whatever the code does (trivial_command)"
            else:
                continue
            out.append(f"{bl.label(iid)}: {name} is refused: {why}; an open item's repro and checks run without a "
                       "shell and run a test or tool")
    return out


def host_bound_accepted(it):
    g = next((g for g in it.get("gates", []) if g.get("id") == HOST_BOUND_GATE), {})
    return g.get("by") == "operator" and str(g.get("answer", "")).strip().lower() in HOST_BOUND_ACCEPTS


def cmd_check(bl, a):
    pieces = host_user_pieces()
    planned = [i for sid, sp in bl.items.items() if sp.get("kind") == "sprint" and sp.get("status") == "planned"
               for i in bl.sprint_items(sid)]
    errs = validate(bl, pieces) + stale_touches(bl) + docs_after_code(bl, planned) + refused_command_errors(bl)
    stale = stale_knowledge(bl)
    warns = docs_warnings(bl) + repro_text_warnings(bl) + state_path_warnings(bl) \
        + gate_do_warnings(bl) + refused_answer_warnings(bl) + shared_file_warnings(bl) + item_files_warnings(bl)
    for x in errs + stale + warns:
        say(withhold_names(x, pieces))  # an error that quotes an item's text never prints a name either
    say(f"backlog check: items={len(bl.items)} errors={len(errs)} stale={len(stale)} warnings={len(warns)}")
    return 1 if errs else 0


def cmd_selectors(bl, a):
    import tests
    cmd = tests.pytest_cmd()
    if cmd is None:
        raise Refused("pytest is needed to count the tests a selector collects: install uv (https://docs.astral.sh/uv/) "
                      "and rerun, or `pip install pytest pytest-xdist`")
    rows = selector_rows(bl, cmd)
    for count, why, text, iid in rows:
        flag = "error" if count is None else "NONE" if count == 0 else ""
        say(f"{'?' if count is None else count:>5}  {flag:<5}  {text}  {bl.label(iid)}" + (f"  ({why})" if why else ""))
    say(f"backlog selectors: checks={len(rows)} selectors={len({r[2] for r in rows})} "
        f"none={sum(1 for r in rows if r[0] == 0)} errors={sum(1 for r in rows if r[0] is None)}")
    return 0


