"""The questions a tool answers instead of ranking them, routed by their kind (`routed`, `pack_routed`, the experts for a
count, a decision, a conflict, a gap and a citation, fused by `rrf`), and the topics for code: the host workspace's
signals, the package names a file declares and the kb topics they match (`topics_for`, `format_topics_for`) (stdlib
only; kb/_self/tools.md, "How the lookup tools decide").

`kbfacts.py` is the facade: it imports this module at its end, so every name here stays importable from it, and this
module reads the ground (articles, ledgers, decisions, scope) from it and the ranking from `kf_index`. Import
`kbfacts`; imported first, this module has the facade load it, so every module still holds the one copy `kbfacts`
loads."""
import sys
if "kbfacts" not in sys.modules:  # imported first: the facade loads this stage under its name, then this copy reads it
    sys.modules.pop(__name__, None)
    import kbfacts
import ast, json, math, os, re, subprocess, warnings
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from fractions import Fraction

import kbcommon, kbid
from kbfacts import (
    ID, SELF_ROOT, WORD, articles, bare, cached, clip, data_rows, decision_line, decision_rows, in_prefix,
    key_terms, ledger_entries, read, root_files, root_name, scope, source_rows, stem, terms
)
from kf_fresh import cited_lines, format_sources
from kf_index import pack, store


# ---------------------------------------------------------------- questions a tool answers, routed by their kind

RRF_K = 60  # reciprocal rank fusion's rank constant: the original paper's and Elasticsearch's default `rank_constant`
ROUTED_ITEMS = 6  # items (ledger entries, decision rows, citing files) a routed answer prints
ENTRY_CHARS = 1800  # characters of one ledger entry it prints (clip): the whole entry, its source ids included
TOPIC_MIN = 3  # topic words a question needs for a ledger expert to answer it
GAP_TITLE_SHARE = 1 / 3  # weight share of an open gap's title that the question's topic words must hold (idf weights)
ROUTED_PATHS = 40  # article paths a routed list of articles prints

COUNT_CUE = re.compile(r"\b(?:how many|number of|count of|total number of)\b[^?]*\b(?:articles?|topics?)\b"
                       r"|\b(?:list|which|what)\b[^?]*\b(?:articles?|topics?)\b[^?]*\b(?:are|is|with status|status)\s+"
                       r"(?:partial|complete|unknown)\b", re.I)
LIST_CUE = re.compile(r"\b(?:list|which|what)\b", re.I)
STATUS_CUE = re.compile(r"\b(partial|complete|unknown)\b", re.I)
SCOPE_CUE = re.compile(r"\b(?:kb|all|every|total|whole)\b", re.I)
COUNT_STEMS = frozenset(stem(w) for w in (
    "article", "articles", "topic", "topics", "many", "number", "count", "list", "hold", "holds", "have", "contain",
    "contains", "cover", "covers", "domain", "domains", "total", "partial", "complete", "unknown", "status", "kb",
    "all", "every", "whole", "exist", "each", "per", "currently", "which", "what", "public"))
_CITE_ID = rf"(?-i:{ID.pattern})"
CITE_CUE = re.compile(  # a word that asks who cites an id: `cite` forms anywhere, the others only beside the id itself
    r"\bcit(?:e[sd]?|ing|ations?)\b"
    rf"|\b(?:mention\w*|refer\w*|name[sd]?)\s+(?:(?:to|both|either)\s+)?(?:the\s+)?(?:(?:sources?\s+)?ids?\s+|sources?\s+)?{_CITE_ID}"
    rf"|{_CITE_ID}\s+(?:(?:is|are)\s+)?(?:used|mentioned|referenced|referred to|named)\s+(?:by|in)\b", re.I)
DECISION_REF = re.compile(rf"(?<![\w-]){kbcommon.DECISION_ID.pattern}(?![\w-])")
CONFLICT_CUE = re.compile(r"\b(?:disagree\w*|conflict\w*|contradict\w*|inconsisten\w*)\b", re.I)
GAP_CUE = re.compile(r"\bwhat (?:does|do) the kb (?:say|know|document|cover|record|hold|have)\b"
                     r"|\bdoes the kb (?:cover|document|have|say|know|mention|hold|record)\b", re.I)
LEDGER_STEMS = frozenset(stem(w) for w in (
    "source", "sources", "disagree", "disagrees", "conflict", "conflicts", "contradict", "contradicts", "inconsistent",
    "page", "pages", "doc", "docs", "documentation", "kb", "cover", "know", "document", "record", "hold", "mention",
    "about", "regarding", "say", "have"))
# a continuation line that ends a gaps.md entry's open-gap route (the research queue's `Tried` and `Partly resolved`
# rule is `ql_research.SETTLED`'s: a partly resolved entry is a lead there and an answered lookup here)
OPEN_GAP = re.compile(r"(?:^|\s)- (?:Resolved|Superseded|Closed|Partly resolved|Mostly resolved|Narrowed)\b")
KIND_PHRASE = {"count": "the audit totals", "decision": "the decisions ledger", "conflict": "the whole _conflicts.md entry",
               "gap": "an open _gaps.md entry: the kb lacks it", "cites": "the lines that cite the source (src --cited)"}


def rrf(lists, k=RRF_K):
    """Reciprocal rank fusion of ranked lists of keys: [(key, score)] best first, where a key scores the sum of
    1/(k + rank) over the lists that hold it, ranks counted from 1, and adds nothing for a list that lacks it. Only
    ranks are read, so no score is calibrated. Scores are exact fractions; equal ones go to the best single rank, then
    to the key (a (path, line) pair: path, then line)."""
    score, best = defaultdict(Fraction), {}
    for items in lists:
        for rank, key in enumerate(dict.fromkeys(items), start=1):
            score[key] += Fraction(1, k + rank)
            best[key] = min(best.get(key, rank), rank)
    return sorted(score.items(), key=lambda kv: (-kv[1], best[kv[0]], kv[0]))


def _topic_terms(question, drop):
    """The question's key words that are not cue words (`drop`): the topic a ledger entry has to hold."""
    return {t for t in key_terms(question) if t not in drop}


def _entry_in_domain(e, domain):
    """Whether a ledger entry belongs to bare domain `domain`: its `## ` section is the domain's or starts with it, or
    its text names a `topic: <domain>/...` marker."""
    d = bare(domain.strip("/"))
    return e["section"] == d or e["section"].startswith(d + "-") or f"topic: {d}/" in e["text"]


def _entry_title(e, lines):
    """The heading of a ledger entry: its `### ` line, or the bold lead of a bullet (else the bullet's first
    sentence)."""
    line = lines[e["line"] - 1] if 0 < e["line"] <= len(lines) else e["text"]
    line = line.lstrip("#- ").strip()
    m = re.match(r"\*\*(.+?)\*\*", line)
    return m.group(1).strip(" .:") if m else line.split(". ")[0]


def _heading_blocks(name):
    """The `### ` blocks of a ledger that ledger_entries() leaves as sub-headings (the heading is followed by bullets:
    `### on-prem / Windows / ConfigMgr / SQL`): {file, line, end, section, text} with the heading and every line under
    it up to the next heading, so a question that names the heading finds what its bullets say."""
    out = []
    for q in root_files((name,)):
        section, cur = "", None
        for n, ln in enumerate((read(q) or "").splitlines(), start=1):
            if ln.startswith("#"):
                cur = None
                if ln.startswith("## "):
                    section = ln[3:].strip()
                elif ln.startswith("### "):
                    cur = {"file": q, "line": n, "end": n, "section": section, "text": ln[4:].strip()}
                    out.append(cur)
            elif cur is not None and ln.strip():
                cur["text"] += " " + ln.strip()
                cur["end"] = n
    return out


def _title_share(topic, held):
    """The share of a title's weight its words in `topic` hold, a word weighing its inverse document frequency over
    the kb's units (rank()'s idf): a title's rare words count more than its common ones, so a question that names
    only the subject of a narrow entry holds a small share and one that names its missing fact a large one."""
    st = store()
    n = max(st.n, 1)

    def weight(t):
        df = len(st.own(t))
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    return sum(weight(t) for t in topic) / sum(weight(t) for t in held)


def _ledger_items(question, name, kind, cue_stems, domain, root, open_only):
    """The entries of ledger `name` whose title holds every topic word of the question (TOPIC_MIN of them at least),
    tightest title first, as routed items. `open_only`: a gaps entry that is tagged UNK and has no line OPEN_GAP
    reads (Resolved, Superseded, Closed, Partly resolved, Mostly resolved, Narrowed), and whose title the topic words
    hold GAP_TITLE_SHARE of at least: a broad question whose words only fit inside a narrower entry's title is a
    lookup the pack answers."""
    topic = _topic_terms(question, cue_stems)
    if len(topic) < TOPIC_MIN:
        return []
    found, files = [], {}
    entries = ledger_entries(name)
    if not open_only:
        have = {(e["file"], e["line"]) for e in entries}
        entries += [b for b in _heading_blocks(name) if (b["file"], b["line"]) not in have and b["end"] > b["line"]]
    for e in entries:
        if root and root_name(e["file"]) != root or domain and not _entry_in_domain(e, domain):
            continue
        if open_only and ("[UNK" not in e["text"] or OPEN_GAP.search(e["text"])):
            continue
        if e["file"] not in files:
            files[e["file"]] = (read(e["file"]) or "").splitlines()
        title = _entry_title(e, files[e["file"]])
        if open_only and title.startswith(("Closed", "Resolved")):
            continue
        held = set(terms(title))
        if topic <= held and (not open_only or _title_share(topic, held) >= GAP_TITLE_SHARE):
            found.append((len(held), e["file"], e["line"], e, title))
    out = []
    for _, path, line, e, title in sorted(found, key=lambda x: x[:3]):
        span = f"line {line}" if e["end"] == line else f"lines {line}-{e['end']}"
        word = "open gap entry, the kb lacks it" if open_only else "conflict entry"
        out.append({"key": (path, line), "kind": kind, "path": path, "title": title, "lacks": open_only,
                    "lines": [f"- {path}:{line} [{word}; {span}] {clip(e['text'], ENTRY_CHARS)}"]})
    return out


def _conflict_items(question, domain, root, invalidated):
    return _ledger_items(question, kbcommon.CONFLICTS, "conflict", LEDGER_STEMS, domain, root, False)


def _gap_items(question, domain, root, invalidated):
    return _ledger_items(question, kbcommon.GAPS, "gap", LEDGER_STEMS, domain, root, True)


def _decision_items(question, domain, root, invalidated):
    """The rows of the decisions ledgers (every status: the question names the id) of the ids the question names, in
    the order named, each as `rag.py show` and kbdecide list read it."""
    rows = {d["id"]: d for d in decision_rows() if not root or d["root"] == root}
    out = []
    for i in dict.fromkeys(DECISION_REF.findall(question)):
        d = rows.get(i)
        if d:
            out.append({"key": (d["path"], d["line"]), "kind": "decision", "path": d["path"],
                        "lines": [decision_line(d, source=True)]})
    return out


def _cites_items(question, domain, root, invalidated):
    """One item per file that names a source id of the question (src --cited), files naming most of the ids first,
    then in path order; its line is the file's first citing line."""
    ids = list(dict.fromkeys(kbid.canonical_id(i) for i in ID.findall(question)))
    prefix = scope(domain, root)
    cited = cited_lines(ids) if ids else {}
    by_file = {}
    for i in ids:
        for path, n in cited.get(i, []):
            if prefix and not in_prefix(path, prefix):
                continue
            by_file.setdefault(path, {}).setdefault(i, []).append(n)
    out = []
    for path, hits in sorted(by_file.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        first = min(n for ns in hits.values() for n in ns)
        said = "; ".join(f"{i}: line{'s' if len(ns) > 1 else ''} {', '.join(map(str, ns[:6]))}"
                         + (f" (+{len(ns) - 6})" if len(ns) > 6 else "") for i, ns in hits.items())
        out.append({"key": (path, first), "kind": "cites", "path": path, "ids": sorted(hits),
                    "lines": [f"- {path}:{first} cites {said}"]})
    return out


def _count_items(question, domain, root, invalidated):
    """The audit totals (rag.py audit) of the domains the question names, or of the kb: the number of articles and
    their statuses, and the article paths when the question asks for a list. Nothing when the question also names a
    topic (`how many articles about Kerberos`), which is a lookup."""
    doms = sorted({bare(p).split("/", 1)[0] for p in articles() if "/" in bare(p)})
    words = {w.lower() for w in WORD.findall(question)}
    named = [d for d in doms if d.lower() in words]
    known = COUNT_STEMS | {stem(d.lower()) for d in named}
    if set(key_terms(question)) - known:
        return []
    if not named and not (domain or SCOPE_CUE.search(question)):
        return []
    found = STATUS_CUE.search(question)
    status = found.group(1).lower() if found else None
    wanted = named or [domain or None]
    rows, lines = [], []
    for d in wanted:  # the selection audit() makes, without its ledger links: the totals are the same
        prefix = scope(d, root)
        part = [{"path": p, "status": m.get("status", "")} for p, m in sorted(articles().items())
                if (not prefix or in_prefix(p, prefix)) and (not status or m.get("status") == status)]
        rows += part
        counts = Counter(r["status"] or "unknown" for r in part)
        label = d or "the kb"
        lines.append(f"{label}: articles={len(part)}" + (f" with status {status}" if status else "")
                     + (" (" + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) + ")" if counts else ""))
    if len(wanted) > 1:
        lines.append(f"total: articles={len(rows)}")
    shown = " ".join(w for w in wanted if w) + (f" --status {status}" if status else "")
    if LIST_CUE.search(question):
        lines += [f"- {r['path']} {r['status'] or 'unknown'}" for r in rows[:ROUTED_PATHS]]
        if len(rows) > ROUTED_PATHS:
            lines.append(f"  (+{len(rows) - ROUTED_PATHS} more: python3 _tools/rag.py audit {shown})".replace(" )", ")"))
    lines.append(f"(the totals of python3 _tools/rag.py audit {shown})".replace(" )", ")"))
    return [{"key": ("audit:" + (shown.strip() or "kb"), 0), "kind": "count", "path": "", "lines": lines}]


EXPERTS = (("decision", DECISION_REF, _decision_items), ("cites", None, _cites_items),
           ("count", COUNT_CUE, _count_items), ("conflict", CONFLICT_CUE, _conflict_items),
           ("gap", GAP_CUE, _gap_items))  # (kind, cue, expert): the cues are deterministic, an expert may answer nothing


def kinds_of_question(question):
    """The kinds of the experts whose cue the question shows, in EXPERTS order (an expert may still answer nothing).
    `cites` shows when the question names a source id and a citation word."""
    out = []
    for kind, cue, _ in EXPERTS:
        if kind == "cites":
            hit = bool(ID.search(question) and CITE_CUE.search(question))
        else:
            hit = bool(cue.search(question))
        if hit:
            out.append(kind)
    return out


def routed(question, domain=None, root=None, fmt="detailed", footer=True, invalidated=False):
    """The answer of the experts that hold the answer to a question of a kind a tool decides, or None when no cue
    shows or no expert answers (the question ranks as pack() ranks it): a count or list of articles (audit totals), a
    decision id (the decisions ledgers' row), a 'which sources disagree' question (the whole _conflicts.md entry with
    its source ids), a 'what does the kb say about' question that an open _gaps.md entry records (`kb lacks:`), a
    citation question (src --cited). When more than one expert answers, their lists are fused by rrf() and at most
    ROUTED_ITEMS items print, each with its path:line. The result has pack()'s keys (verdict `good`, `none` when only
    gap entries answer; route `web` then, else None) and `routed`: the kinds, the printed path:line keys."""
    if root == SELF_ROOT:
        return None
    asked = kinds_of_question(question)
    if not asked:
        return None
    experts = {k: f for k, _, f in EXPERTS}
    lists = []
    for k in asked:
        items = experts[k](question, domain, root, invalidated)
        if items:
            lists.append((k, items))
    if not lists:
        return None
    by_key = {}
    for _, items in lists:
        for it in items:
            by_key.setdefault(it["key"], it)
    fused = rrf([[it["key"] for it in items] for _, items in lists])
    chosen = [by_key[k] for k, _ in fused][:ROUTED_ITEMS]
    kinds = sorted({it["kind"] for it in chosen}, key=[k for k, _, _ in EXPERTS].index)
    verdict = "none" if all(it.get("lacks") for it in chosen) else "good"
    out = [f"coverage: {verdict} (routed by kind: " + "; ".join(f"{k}, from {KIND_PHRASE[k]}" for k in kinds) + ")"]
    if verdict == "none":
        out += ["route: web", "kb has: -", f"kb lacks: {clip(chosen[0]['title'], 160)}"]
    for it in chosen:
        out += it["lines"]
    cited = []
    for it in chosen:
        cited += it.get("ids") or ID.findall("\n".join(it["lines"]))
    rows, seen, srcs = source_rows(), set(), []
    for i in cited:
        if i not in seen:
            seen.add(i)
            row = rows.get(i) or {}
            srcs.append((i, row.get("url") or "UNKNOWN id", (row.get("superseded_by") or "").strip()))
    if srcs and footer and fmt != "concise":
        out += ["", "sources:"] + format_sources(srcs)
    paths = list(dict.fromkeys(it["path"] for it in chosen if it["path"]))
    keys = [f"{k[0]}:{k[1]}" for k in (it["key"] for it in chosen) if not k[0].startswith("audit:")]
    return {"verdict": verdict, "missing": [], "matched": [], "informative": [], "known": [], "unmatched": [],
            "spread": None, "scatter": None, "passing": [], "priced": False, "parted": [], "top_score": None, "top_domains": [],
            "route": "web" if verdict == "none" else None, "has": [],
            "lacks": [chosen[0]["title"]] if verdict == "none" else [], "paths": paths, "tested": [], "pinned": 0,
            "key_missing": [], "sources": [s[0] for s in srcs], "source_rows": srcs, "text": "\n".join(out),
            "decisions": [], "logs": [], "flags": [], "routed": {"kinds": kinds, "lines": keys}}


def pack_routed(question, budget=1200, domain=None, max_articles=4, fmt="detailed", footer=True, root=None,
                invalidated=False, item=None, st=None, as_of=None):
    """routed() when an expert answers the question, else pack() with the same arguments: the one entry the lookup
    tools (rag.py pack, kb_pack, kb_ask.py, the kb: hook) call. A brief for a backlog item (`item`), a store view (`st`),
    the rule docs (root `_self`) and a pack `as_of` a date (the experts answer from the kb as it is now) are never
    routed."""
    res = None if item or st is not None or as_of else routed(question, domain, root, fmt, footer, invalidated)
    return res or pack(question, budget, domain, max_articles, fmt, footer, root, invalidated, item, st, as_of=as_of)


# ---------------------------------------------------------------- topics for code (host workspace signals)

SKIP_CODE_DIRS = {".git", "node_modules", "dist", "build", "out", "coverage", "target", "vendor", "__pycache__", ".venv",
                  "venv", ".next", ".turbo", ".cache"}
MAX_FILES, MAX_FILE_BYTES = 500, 1_000_000


def signals():
    """[(signal, qualified topic, regex)] from each root's signals.csv (`signal,topic`, under DATA_DIR; the topic is
    the root's own): code words that point at a kb topic, matched case-insensitively as whole words (a signal that
    starts or ends with punctuation matches there as is)."""
    return cached("signals", _signals)


def _signals():
    out = []
    for root, r in data_rows("signals.csv"):
        sig, topic = (r.get("signal") or "").strip(), (r.get("topic") or "").strip()
        if sig and topic:
            out.append((sig, kbcommon.qualify(root, topic), signal_regex(sig)))
    return out


def signal_regex(sig):
    """The pattern of one signal: case-insensitive, whole word (a signal that starts or ends with punctuation matches
    there as is)."""
    rx = (r"(?<!\w)" if sig[0].isalnum() else "") + re.escape(sig) + (r"(?!\w)" if sig[-1].isalnum() else "")
    return re.compile(rx, re.I)


def code_files(paths, base=None):
    """Text files under the given paths (files or directories, relative to `base`), skipping dependency and build
    directories: ([(shown path, full path)], [skipped notes])."""
    base = base or os.getcwd()
    files, skipped = [], []
    for p in paths:
        full = os.path.normpath(os.path.join(base, os.path.expanduser(p)))
        if os.path.isfile(full):
            files.append((p, full))
        elif os.path.isdir(full):
            for root, dirs, names in os.walk(full):
                dirs[:] = sorted(d for d in dirs if d not in SKIP_CODE_DIRS and not d.startswith("."))
                for n in sorted(names):
                    files.append((os.path.relpath(os.path.join(root, n), base), os.path.join(root, n)))
        else:
            skipped.append(f"{p}: no such file or directory")
    if len(files) > MAX_FILES:
        skipped.append(f"{len(files) - MAX_FILES} files over the {MAX_FILES}-file limit")
        files = files[:MAX_FILES]
    return files, skipped


# ---- imports mode: the package names a file declares, matched against the signals instead of its text

MAX_AST_BYTES = 500_000  # Python source over this is not parsed (a parse tree costs many times the text)
GENERATED_ATTRS = ("linguist-generated", "linguist-vendored")
PY_SUFFIXES = (".py", ".pyi", ".pyw")
MSBUILD_SUFFIXES = (".csproj", ".fsproj", ".vbproj", ".props", ".targets")
PS_SUFFIXES = (".ps1", ".psm1")
PACKAGE_JSON_SECTIONS = ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")
PS_MODULE_NAME = re.compile(r"ModuleName\s*=\s*['\"]?([^'\";}\s,]+)", re.I)
PS_HASHTABLE = re.compile(r"@\{[^{}]*\}")
PS_REQUIRES = re.compile(r"^[ \t]*#requires[ \t]+(.*)$", re.I | re.M)
PS_MODULES_SWITCH = re.compile(r"(?i)(?<!\S)-Modules?\s+")
PS_NEXT_SWITCH = re.compile(r"\s-[A-Za-z]")
PS_REQUIRED_MODULES = re.compile(r"(?im)^[ \t]*RequiredModules[ \t]*=[ \t]*")
PS_QUOTED = re.compile(r"'([^'\r\n]+)'|\"([^\"\r\n]+)\"")
PS_NAME = re.compile(r"[\w.\-]+")


def _line_of(body, pos):
    return body.count("\n", 0, pos) + 1


def _line_of_name(body, name):
    i = body.find(name)
    return _line_of(body, i) if i >= 0 else 1


def _python_imports(body):
    """[(name, line)] of the import statements of Python source, read with ast.parse (the source is never run):
    `import a.b` gives a.b, `from a.b import c` gives a.b.c (a.b for `*`). Relative imports name the project's own
    modules and are left out; a source that does not parse gives none."""
    if len(body) > MAX_AST_BYTES:
        return []
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree = ast.parse(body.lstrip("﻿"))
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return []
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [(a.name, node.lineno) for a in node.names]
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            out += [(node.module if a.name == "*" else f"{node.module}.{a.name}", node.lineno) for a in node.names]
    return sorted(set(out), key=lambda x: (x[1], x[0]))


def _package_json_imports(body):
    """The keys of dependencies, devDependencies, peerDependencies and optionalDependencies."""
    try:
        data = json.loads(body.lstrip("﻿"))
    except (ValueError, RecursionError):
        return []
    if not isinstance(data, dict):
        return []
    names = []
    for sec in PACKAGE_JSON_SECTIONS:
        if isinstance(data.get(sec), dict):
            names += [n for n in data[sec] if isinstance(n, str)]
    return [(n, _line_of_name(body, json.dumps(n))) for n in dict.fromkeys(names)]


def _go_mod_imports(body):
    """The module paths of `require` (one line, or a block); replace, exclude and retract are not requirements."""
    out, block = [], ""
    for n, line in enumerate(body.splitlines(), start=1):
        line = line.split("//", 1)[0].strip()
        if not line:
            continue
        if line == ")":
            block = ""
            continue
        opened = re.match(r"^(\w+)\s*\($", line)
        if opened:
            block = opened.group(1)
            continue
        parts = line.split()
        if block == "require":
            path = parts[0]
        elif not block and parts[0] == "require" and len(parts) > 1:
            path = parts[1]
        else:
            continue
        out.append((path.strip("\"`"), n))
    return out


def _msbuild_imports(body):
    """PackageReference / PackageVersion / GlobalPackageReference (Include, or Update in a props file) of an MSBuild
    file, read with xml.etree (a document with a DOCTYPE is refused: no entity is ever expanded)."""
    if re.search(r"<!(?:DOCTYPE|ENTITY)", body, re.I):
        return []
    try:
        root = ET.fromstring(re.sub(r"^\s*<\?xml[^>]*\?>", "", body.lstrip("﻿")))
    except (ET.ParseError, ValueError, RecursionError):
        return []
    names = []
    for el in root.iter():
        if isinstance(el.tag, str) and el.tag.rsplit("}", 1)[-1] in ("PackageReference", "PackageVersion", "GlobalPackageReference"):
            name = el.get("Include") or el.get("Update")
            if name:
                names.append(name.strip())
    return [(n, _line_of_name(body, n)) for n in dict.fromkeys(names)]


def _blank_ps_comments(body):
    """The PowerShell source with comments replaced by spaces (offsets and lines kept); `#` inside a quoted string
    stays."""
    out, i, n, quote = [], 0, len(body), ""
    while i < n:
        c = body[i]
        if quote:
            out.append(c)
            if c == quote:
                quote = ""
        elif c in "'\"":
            quote = c
            out.append(c)
        elif body.startswith("<#", i):
            j = body.find("#>", i + 2)
            j = n if j < 0 else j + 2
            out.append("".join(ch if ch in "\r\n" else " " for ch in body[i:j]))
            i = j
            continue
        elif c == "#":
            j = body.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
            continue
        else:
            out.append(c)
        i += 1
    return "".join(out)


def _ps_names(chunk, offset, body):
    """[(name, line)] of a module list: hashtable `@{ModuleName='X'}` items, quoted names, or bare names."""
    out = []
    for m in PS_MODULE_NAME.finditer(chunk):
        out.append((m.group(1), _line_of(body, offset + m.start(1))))
    plain = PS_HASHTABLE.sub(lambda m: " " * len(m.group()), chunk)
    quoted = list(PS_QUOTED.finditer(plain))
    for m in quoted:
        name = (m.group(1) or m.group(2)).strip()
        if PS_NAME.fullmatch(name):
            out.append((name, _line_of(body, offset + m.start())))
    if not quoted:
        out += [(m.group(), _line_of(body, offset + m.start())) for m in PS_NAME.finditer(plain)]
    return out


def _ps_requires_imports(body):
    """Modules of `#Requires -Modules A, B` and `#Requires -Modules @{ModuleName='X'; ModuleVersion='1.0'}` lines. A
    `#Requires` that sits inside a longer comment (`# #Requires ...`) is not a directive and is left out."""
    out = []
    for m in PS_REQUIRES.finditer(body):
        sw = PS_MODULES_SWITCH.search(m.group(1))
        if not sw:
            continue
        start = m.start(1) + sw.end()
        rest = body[start:m.end(1)]
        masked = PS_HASHTABLE.sub(lambda h: " " * len(h.group()), rest)
        cut = PS_NEXT_SWITCH.search(masked)
        out += _ps_names(rest[:cut.start() if cut else len(rest)], start, body)
    return list(dict.fromkeys(out))


def _psd1_imports(body):
    """Modules of a manifest's `RequiredModules = @('A', @{ModuleName='B'; ModuleVersion='1.0'})` (comments blanked)."""
    text = _blank_ps_comments(body)
    out = []
    for m in PS_REQUIRED_MODULES.finditer(text):
        pos = m.end()
        if text.startswith("@(", pos):
            depth, quote, i = 0, "", pos + 1
            while i < len(text):
                c = text[i]
                if quote:
                    quote = "" if c == quote else quote
                elif c in "'\"":
                    quote = c
                elif c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            end = i
        else:
            end = text.find("\n", pos)
            end = len(text) if end < 0 else end
        out += _ps_names(text[pos:end], pos, text)
    return list(dict.fromkeys(out))


def import_reader(name):
    """The reader of a file's imports by its name, or None: package.json (dependencies, devDependencies,
    peerDependencies, optionalDependencies), go.mod (require), .py (ast), .csproj/.fsproj/.vbproj/.props/.targets
    (PackageReference, PackageVersion), .ps1/.psm1 (#Requires -Modules) and .psd1 (RequiredModules)."""
    base = name.replace("\\", "/").rsplit("/", 1)[-1].lower()
    if base == "package.json":
        return _package_json_imports
    if base == "go.mod":
        return _go_mod_imports
    if base.endswith(PY_SUFFIXES):
        return _python_imports
    if base.endswith(MSBUILD_SUFFIXES):
        return _msbuild_imports
    if base.endswith(PS_SUFFIXES):
        return _ps_requires_imports
    if base.endswith(".psd1"):
        return _psd1_imports
    return None


def imports_of(name, body):
    """[(imported name, line)] a file declares, by the reader for its name (import_reader); a given text with no file
    name (`name` empty) is read as Python, then as a PowerShell script. Nothing is executed."""
    if name:
        reader = import_reader(name)
        return reader(body) if reader else []
    return _python_imports(body) or _ps_requires_imports(body)


def _repo_top(directory, cache):
    """The directory holding the `.git` (a directory, or a file for a worktree) above `directory`, or None."""
    chain, d, top = [], directory, None
    while True:
        if d in cache:
            top = cache[d]
            break
        chain.append(d)
        if os.path.exists(os.path.join(d, ".git")):
            top = d
            break
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    for c in chain:
        cache[c] = top
    return top


def marked_files(fulls):
    """{full path: attribute} of the files git marks `linguist-generated` or `linguist-vendored` (set, or true), from
    `git check-attr` in the repository each file lives in; a file outside a repository, or a machine without git,
    marks nothing. An unset or false attribute keeps the file."""
    cache, groups = {}, defaultdict(dict)
    for full in fulls:
        real = os.path.realpath(full)
        top = _repo_top(os.path.dirname(real), cache)
        if top:
            groups[top][os.path.relpath(real, top).replace(os.sep, "/")] = full
    out = {}
    for top, rels in groups.items():
        data = b"".join(r.encode("utf-8", "surrogateescape") + b"\0" for r in rels)
        try:
            p = subprocess.run(["git", "-C", top, "check-attr", "--stdin", "-z", *GENERATED_ATTRS], input=data,
                               capture_output=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            continue
        if p.returncode:
            continue
        parts = p.stdout.split(b"\0")
        for i in range(0, len(parts) - 2, 3):
            rel, attr, val = (x.decode("utf-8", "surrogateescape") for x in parts[i:i + 3])
            if val in ("set", "true") and rel in rels:
                out.setdefault(rels[rel], attr)
    return out


def _topics_by_imports(found):
    """{topic: {signals, where, imports, score}} for {import name: [where, count]}: a signal must match the whole
    import name as a word. An import that matches signals of one topic counts 1 for it, one that matches signals of k
    topics counts 1/k for each, so a specific import ranks its topic above a broad one."""
    sigs = signals()
    hits = defaultdict(lambda: {"signals": Counter(), "where": {}, "imports": [], "score": Fraction(0)})
    for name in sorted(found):
        where, n = found[name]
        matched = [(sig, topic) for sig, topic, rx in sigs if rx.search(name)]
        topics = sorted({t for _, t in matched})
        for sig, topic in matched:
            h = hits[topic]
            h["signals"][sig] += n
            h["where"].setdefault(sig, where)
        for t in topics:
            h = hits[t]
            h["score"] += Fraction(1, len(topics))
            h["imports"].append({"import": name, "where": where, "signals": sorted({s for s, tt in matched if tt == t}),
                                 "topics": len(topics)})
    return hits


def topics_for(paths=(), text="", base=None, imports=False):
    """Rank kb topics for code: every signal found in the files (or in `text`) adds to its topic. Returns
    {"topics": [{topic, signals: {signal: count}, where: {signal: "path:line"}}], "files": n, "text": bool,
    "skipped": [...]}.

    imports=True matches the signals only against the package names the files declare (import_reader: Python
    imports, package.json, go.mod, csproj and props, PowerShell #Requires and .psd1), so a signal that a comment, a
    string or a docstring merely mentions finds nothing; files git marks linguist-generated or linguist-vendored are
    skipped. Each topic then also has "imports": [{import, where, signals, topics}] and a "score" (see
    _topics_by_imports), topics are ranked by score, and the result has "mode": "imports" and "imports": how many
    distinct imports were found. A candidate to look at, never an owner of the code."""
    sources, skipped = [], []
    if text:
        sources.append(("text", text, None))
    files, skipped = code_files(paths, base) if paths else ([], [])
    if imports:
        files = [(s, f) for s, f in files if import_reader(s)]
        marked = marked_files([f for _, f in files])
        skipped += [f"{s}: {marked[f]}" for s, f in files if f in marked]
        files = [(s, f) for s, f in files if f not in marked]
    for shown, full in files:
        try:
            if os.path.getsize(full) > MAX_FILE_BYTES:
                skipped.append(f"{shown}: over {MAX_FILE_BYTES // 1000} KB")
                continue
            with open(full, "rb") as f:
                raw = f.read()
        except OSError as e:
            skipped.append(f"{shown}: {e.strerror}")
            continue
        if b"\0" in raw[:4096]:
            continue  # binary
        sources.append((shown, raw.decode("utf-8", errors="replace"), full))
    if imports:
        found = {}
        for shown, body, full in sources:
            if full and import_reader(shown) is _python_imports and len(body) > MAX_AST_BYTES:
                skipped.append(f"{shown}: over {MAX_AST_BYTES // 1000} KB for the Python reader")
                continue
            for name, line in imports_of("" if full is None else shown, body):
                cur = found.setdefault(name, [f"{shown}:{line}", 0])
                cur[1] += 1
        hits = _topics_by_imports(found)
        ranked = sorted(hits.items(), key=lambda kv: (-kv[1]["score"], -len(kv[1]["imports"]), kv[0]))
        topics = [{"topic": t, "signals": dict(h["signals"].most_common()), "where": h["where"],
                   "imports": sorted(h["imports"], key=lambda i: (i["topics"], i["import"])),
                   "score": round(float(h["score"]), 3)} for t, h in ranked]
        return {"topics": topics, "files": len(sources) - (1 if text else 0), "text": bool(text), "skipped": skipped,
                "mode": "imports", "imports": len(found)}
    hits = defaultdict(lambda: {"signals": Counter(), "where": {}})
    for shown, body, _ in sources:
        for sig, topic, rx in signals():
            ms = list(rx.finditer(body))
            if ms:
                h = hits[topic]
                h["signals"][sig] += len(ms)
                h["where"].setdefault(sig, f"{shown}:{body.count(chr(10), 0, ms[0].start()) + 1}")
    ranked = sorted(hits.items(), key=lambda kv: (-len(kv[1]["signals"]), -sum(kv[1]["signals"].values()), kv[0]))
    return {"topics": [{"topic": t, "signals": dict(h["signals"].most_common()), "where": h["where"]} for t, h in ranked],
            "files": len(sources) - (1 if text else 0), "text": bool(text), "skipped": skipped}


def format_topics_for(res, limit=15):
    by_imports = res.get("mode") == "imports"
    out = [f"kb topics for {res['files']} file(s)" + (" and the given text" if res.get("text") else "")
           + (f" by their imports ({res.get('imports', 0)} found)" if by_imports else "") + ":"]
    for x in res["topics"][:limit]:
        if by_imports:
            via = ", ".join(f"{i['import']} ({i['where']}; {', '.join(i['signals'])}"
                            + (f"; also {i['topics'] - 1} other topic(s)" if i["topics"] > 1 else "") + ")" for i in x["imports"])
            out.append(f"- {x['topic']}  imports: {via}")
            continue
        sigs = ", ".join(f"{s} ({n}, {x['where'][s]})" for s, n in x["signals"].items())
        out.append(f"- {x['topic']}  {sigs}")
    if not res["topics"]:
        out.append("no kb signal found among the imports: none of the declared packages is a curated signal (each root's signals.csv)"
                   if by_imports else
                   "no kb signal found: the code touches none of the curated topics (each root's signals.csv)")
    elif len(res["topics"]) > limit:
        out.append(f"... +{len(res['topics']) - limit} more topics")
    out += [f"skipped: {s}" for s in res["skipped"][:10]]
    out.append("next: kb_facts or kb_pack per topic (response_format detailed) for the facts to check the code against")
    return "\n".join(out)
