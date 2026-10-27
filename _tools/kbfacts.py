#!/usr/bin/env python3
"""Facts, fact tags and ledger entries of the kb, parsed one way for every tool (stdlib only).

rag.py (pack, facts, audit, src --cited, eval), kb_mcp.py, check.py and the kb-verify lint all read the kb through
this module, so a count or a join gives the same answer whichever tool asks.

Roots. The module spans every root (kbcommon.roots(): kb/public, a team's kb/<name>/, the KB_ROOTS directories) and
names a file by its qualified path `<root>/<path in root>` (`public/intune/x.md`) and a topic by `<root>/<topic>`;
what is stored inside a root (front matter, used_in, ledger topic markers, retrieval data) stays root-relative and is
qualified here as it is read. A prefix (`units`, `audit`, a pack's domain) is qualified (`public/intune`) or bare
(`intune`: that domain in every root): in_prefix(), scope().

Tag grammar. A tag is `[PART; PART ...]`; a PART is `KIND[/KIND] [from] [IDS] [NOTE]`:
  KIND  DOC | CODE | DER | COMMUNITY | UNK | DECISION | LOG
  IDS   source ids (S123, S-k3f7q2zd) separated by commas or spaces
  NOTE  free text after `:`, ` - `, ` — ` or `,` (a derivation, a pointer to _gaps.md, ...)
CODE is the implementation read at a pinned commit, not a documented contract: `[CODE S-id: path#symbol]` (or
`path#L10-L20`); code_pointer() returns the pointer. In kb/_self/ a CODE part may point into this repository without an
id (`[CODE _tools/kf_index.py#pack]`; a test checks the file and the symbol exist).
A `;` or `,` directly followed by a KIND starts the next part, so `[DOC S1208, COMMUNITY S1209]` has two parts and
`[DER S328,S329: different property; Type has no table]` has one. A `;` followed by ids and a colon, with no KIND
(`[CODE S-a: path#x; S-b: path#y]`), is another source of the part before it, read as a part of the same kind with its
own note, so every id of such a tag is cited. Canonical form: `[DOC S1, S2]`, `[DER S1: how]`,
`[UNK]` or `[UNK: why]`, `[CODE S1: path#symbol]`. DOC, CODE and COMMUNITY parts must name at least one source id,
and a CODE part a pointer and a pinned source (kb-verify lint reports those that do not).
DECISION cites an operator decision of the root's `_decisions.csv`, not a source: `[DECISION D-k3f7q2zd]` or
`[DECISION D-k3f7q2zd: note]`. Its id is `kbcommon.DECISION_ID`; the part carries it as `part["decision"]` (empty when
the tag names none) and `part["ids"]` stays empty, so no tool reads a decision id as a source id. check.py resolves it.
Decisions are rows, not facts: decision_rows() reads every `_decisions.csv`; pack() and show_decisions() print the
active and proposed ones beside the facts they are tied to (decision_link) or that their text answers, and
decision_conflicts() lists active decisions that share a context (audit).
LOG cites an observed signal of the root's `_logs.csv` (`[LOG L-k3f7q2zd]`, also after another tag: `[DOC S1; LOG L-...]`);
the part carries it as `part["log"]` and `ids` stays empty. A LOG part is parsed (parse_tag) but is no evidence: tags_in()
and so every unit's `tags` leave it out (EVIDENCE_KINDS are the kinds that count), log_ids_in() reads the ids a text cites,
and a fact whose only tag is a LOG one is a fact with no tag. Logs are rows, not facts: log_rows() reads every `_logs.csv`;
pack(), show_logs() and audit_logs() print the active ones beside the facts whose article they are about, labelled as
observed signal and never counted in a pack's verdict, route or `check:` lines.
A feedback report of the committed query-log store that names a line `wrong` or `stale` prints beside them as
`flagged (feedback, not a fact)` (feedback_flags, flags_in), also outside any verdict; audit() counts such lines per article.

Snippets. A bullet that starts `SNIPPET:` introduces the fenced code block right below it: `- SNIPPET: <what it does>;
context: <versions, prerequisites>; checked: no|syntax|run [DER S1: ...]`. It is an ordinary fact unit (the pack
shows the bullet with path:line and the code block indented below it; `show` prints the block) and must carry an evidence tag other than UNK.

Fact units. In an article (a .md with `topic:` front matter): a bullet with its continuation lines, a table row, or
a paragraph line that carries at least one tag. In a data .csv: a row. Each unit has its path, first line, section,
text and parsed tags.

Ledger entries. `_gaps.md` and `_conflicts.md` are split into entries: a top-level `- ` bullet with its
continuation lines, or a `### ` block. An entry is linked to a topic explicitly (a `topic: <domain>/<slug>` marker,
a path of an existing topic file in its text, or a `## <domain>/<slug>` section heading) or through its sources
(a source id in the entry whose `used_in` names the topic's files). New entries carry an explicit
`topic: <domain>/<slug>` marker.

The pack index (kf_index.py). `store()` holds the pack corpus as postings lists (per term: the units that hold it). A process
that finds an index file for the current fingerprint (a key of the content of every file the tools read, the same in
every checkout of that content: `fingerprint()`) reads only the postings of the question's words from it (stdlib
sqlite3); otherwise it builds the corpus, answers from memory and saves the index for the next process. Output is
identical either way: scores are summed in the same term order per unit and ties keep corpus order. Where the file
goes: `index_path()`, in a directory a clone's worktrees share (`index_dir()`); which old files go: `prune_indexes()`.
The same index serves `search()` (rag.py search, kb_search): the corpus also holds untagged prose paragraphs, and at
its end the index files (README.md, each root's ledgers, the kb's own docs in kb/_self/), which only a search with
`index` sees.

The modules behind this facade. kf_index.py holds the index, the ranking and `pack`; kf_fresh.py the freshness stamp,
`pack_many` and the stored pack handles; kf_route.py the questions a tool answers by their kind and the topics for
code. They read the ground in this file (files, tags, units, ledgers, decisions, the index directory) by name and are
imported at its end, so every name of theirs is also a name of this module: other modules import from `kbfacts`.
"""
import csv, functools, hashlib, io, json, os, re, subprocess, sys, tempfile, time
from collections import Counter, defaultdict
from datetime import date, datetime, timezone

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import kbcommon, kbid  # noqa: E402

ROOT_LEDGERS = (kbcommon.ANSWERS, kbcommon.GAPS, kbcommon.CONFLICTS)

EVIDENCE_KINDS = ("DOC", "CODE", "DER", "COMMUNITY", "UNK", "DECISION")  # the tag kinds a fact's `tags` holds and counts
KINDS = EVIDENCE_KINDS + ("LOG",)  # every kind parse_tag knows: a LOG part is observed signal, never evidence
_K = "|".join(KINDS)
SKIP_DIRS = {"_tools", kbcommon.DATA_DIR, "_private", "_cache", "_census", "_self", "artifacts", kbcommon.SNAPSHOTS}
TAG = re.compile(rf"\[(?:{_K})\b[^\]]*\]")
ID = kbid.SOURCE_ID
_PART_SPLIT = re.compile(rf"\s*(?:[;,]\s*(?=(?:{_K})\b)|;\s*(?=(?:{kbid.ID_PATTERN})\b(?:[\s,]+(?:{kbid.ID_PATTERN})\b)*\s*:))")
_PART = re.compile(rf"({_K})(?:/({_K}))?\b\s*(?:from\s+)?"
                   rf"((?:{kbid.ID_PATTERN})(?:[\s,]+(?:{kbid.ID_PATTERN})\b)*)?(.*)", re.S)  # every root's id prefix
_SOURCE_KINDS = ("DOC", "CODE", "DER", "COMMUNITY")  # the kinds whose parts name source ids
# a segment with no kind that opens with ids and a colon (`S-b: path`): another source of the part before it
_MORE_SOURCE = re.compile(rf"((?:{kbid.ID_PATTERN})(?:[\s,]+(?:{kbid.ID_PATTERN})\b)*)\s*:(.*)", re.S)
TOPIC_MARK = re.compile(r"\btopic:\s*`?([a-z0-9-]+/[a-z0-9./-]+?)`?(?=[\s,;.)\]]|$)")
_DECISION_PART = re.compile(rf"DECISION\b\s*({kbcommon.DECISION_ID.pattern}\b)?(.*)", re.S)
LOG_ID = re.compile(r"L-[a-z2-7]{8}")  # check.LOG_ID, which this module cannot import (a test holds them equal)
LOG_FILE = "_logs.csv"  # check.LOGS, likewise
_LOG_PART = re.compile(rf"LOG\b\s*({LOG_ID.pattern}\b)?(.*)", re.S)
csv.field_size_limit(2**31 - 1)


# ---------------------------------------------------------------- tags

def parse_tag(tag):
    """`[DOC S1, S2; UNK: why]` -> [{"kind": "DOC", "ids": ["S1", "S2"], "note": ""}, {"kind": "UNK", ...}]."""
    inner = " ".join(tag.strip()[1:-1].split())
    parts = []
    for seg in _PART_SPLIT.split(inner):
        d = _DECISION_PART.match(seg)
        if d:  # its id is a decision's, not a source's: kept apart from `ids`
            parts.append({"kind": "DECISION", "ids": [], "decision": d.group(1) or "",
                          "note": d.group(2).strip().lstrip(":,—–- ").strip()})
            continue
        g = _LOG_PART.match(seg)
        if g:  # likewise an observed signal's id, not a source's
            parts.append({"kind": "LOG", "ids": [], "log": g.group(1) or "",
                          "note": g.group(2).strip().lstrip(":,—–- ").strip()})
            continue
        m = _PART.match(seg)
        if not m:
            more = _MORE_SOURCE.match(seg)
            if more and parts and parts[-1]["kind"] in _SOURCE_KINDS:  # `[CODE S-a: p; S-b: q]`: another source of that kind
                parts.append({"kind": parts[-1]["kind"], "ids": ID.findall(more.group(1)),
                              "note": more.group(2).strip().lstrip(":,—–- ").strip()})
                continue
            if parts:  # a `;` inside a note: belongs to the previous part
                parts[-1]["note"] = (parts[-1]["note"] + "; " + seg).strip("; ")
            continue
        parts.append({"kind": m.group(1), "ids": ID.findall(m.group(3) or ""),
                      "note": m.group(4).strip().lstrip(":,—–- ").strip()})
    return parts


def tags_in(text):
    """Every evidence tag in a text as parsed parts, flattened: a LOG part is left out (log_ids_in), so no unit, count
    or verdict reads an observed signal as evidence."""
    return [p for t in TAG.findall(text) for p in parse_tag(t) if p["kind"] != "LOG"]


def log_ids_in(text):
    """The ids of the observed signals a text cites (`[LOG L-k3f7q2zd]`), in order, each once; '' ids left out."""
    return list(dict.fromkeys(p["log"] for t in TAG.findall(text) for p in parse_tag(t) if p["kind"] == "LOG" and p["log"]))


def kinds_of(parts):
    return sorted({p["kind"] for p in parts}, key=KINDS.index)


# ---------------------------------------------------------------- validity windows

# `(valid START..END)` before a fact's tag: dates for a DOC or DER fact, short commit ids for a CODE fact, an open end
# written as nothing after the dots. A parenthesis of prose that starts `(valid signature` is no marker: a marker is one
# token that holds `..` or starts with a digit.
WINDOW_MARK = re.compile(r"\(valid\s+([^\s()]+)\)")
_DATE = re.compile(r"\d{4}-\d\d-\d\d")
_REV = re.compile(r"[0-9a-f]{7,40}")


def _parse_window(raw):
    """`2024-03-01..2025-09-30` -> {"kind": "date", "start": ..., "end": ..., "error": ""}; kind is "rev" for commit ids and
    "" with an `error` when the token is no window (end before start, an impossible date, one end of each kind, no dots)."""
    out = {"raw": raw, "kind": "", "start": "", "end": "", "error": ""}
    start, dots, end = raw.partition("..")
    if not dots:
        out["error"] = "needs two dots between its start and its end"
    elif _DATE.fullmatch(start) and (not end or _DATE.fullmatch(end)):
        out.update(kind="date", start=start, end=end)
        try:
            if date.fromisoformat(start) and end and date.fromisoformat(end) < date.fromisoformat(start):
                out["error"] = "ends before it starts"
        except ValueError:
            out["error"] = "holds a date that does not exist"
    elif _REV.fullmatch(start) and (not end or _REV.fullmatch(end)):
        out.update(kind="rev", start=start, end=end)
    else:
        out["error"] = "is neither YYYY-MM-DD..[YYYY-MM-DD] nor REV..[REV] (7 to 40 lowercase hex digits)"
    return out


def windows_in(text):
    """The validity markers of a fact's text, in order, each as `_parse_window` gives it plus `before_tag` (the marker
    stands before the fact's first tag, where the content rules put it)."""
    tag = TAG.search(text)
    out = []
    for m in WINDOW_MARK.finditer(text):
        tok = m.group(1)
        if ".." in tok or tok[0].isdigit():
            out.append({**_parse_window(tok), "before_tag": not tag or m.start() < tag.start()})
    return out


def window_ended(text, today=None):
    """Whether a fact's validity window has ended: a date window whose end is before `today` (an ISO date, default
    today in UTC), or a commit window with an end. A fact with no window, or an open one, has not ended."""
    for w in windows_in(text):
        if w["error"] or not w["end"]:
            continue
        if w["kind"] == "rev" or w["end"] < (today or datetime.now(timezone.utc).date().isoformat()):
            return True
    return False


# a file name carries an extension, or sits under a directory (src/adr-new, a script with none)
POINTER = re.compile(r"(?<![\w/.-])((?:[\w.-]+/)+[\w.-]+|[\w.-]+\.[A-Za-z0-9]+)#([\w.:-]+)")
# a url without its scheme (github.com/o/r/blob/main/x#y, host.example.com/-/x): a first segment that is a host name
# (letters, a dot and one of these tails, never a leading dot) followed, in a later segment, by a forge's own path marker.
# A first segment that merely looks like a host (Contoso.Web.App/Program.cs, Foo.Net/Bar.cs, README.org) is a real path.
_HOST = re.compile(r"[A-Za-z0-9][\w-]*(?:\.[\w-]+)*\.(?:com|org|net|io|dev|app|gov|edu|info|cloud|ai|ms|microsoft|azure|eu|uk)", re.I)
_FORGE_MARKERS = frozenset(("blob", "tree", "-", "raw"))
# prose written as a pair of words, which is no extensionless script path (and/or#x, his/her#y); a closed list
_PROSE_PAIRS = frozenset(("and/or", "either/or", "neither/nor", "he/she", "his/her", "him/her", "yes/no", "on/off",
                          "true/false", "if/else", "pass/fail", "input/output", "read/write", "enable/disable",
                          "allow/deny", "add/remove", "can/cannot", "is/are", "was/were", "has/have"))


def _prose_or_host(path):
    first, *rest = path.split("/")
    if _HOST.fullmatch(first) and _FORGE_MARKERS.intersection(rest):
        return True
    return path.lower() in _PROSE_PAIRS


def code_pointer(part):
    """The `path#symbol` (or `path#L10-L20`) a CODE part points at, as (path, anchor), or None: a path whose first
    segment is a host name followed by a forge marker (`/blob/`, `/tree/`, `/-/`, `/raw/`: a url without its scheme), or a
    pair of prose words such as `and/or`, is no file of a repository."""
    for m in POINTER.finditer(part.get("note") or ""):
        if not _prose_or_host(m.group(1)):
            return m.group(1), m.group(2)
    return None


FLOATING = {"main", "master", "head", "develop", "dev", "trunk", "latest", "stable", "default", "next", "nightly"}
_REF = (re.compile(r"^https://raw\.githubusercontent\.com/[^/]+/[^/]+/(refs/(?:heads|tags)/)?([^/]+)/"),
        re.compile(r"^https://github\.com/[^/]+/[^/]+/(?:blob|raw|tree)/(refs/(?:heads|tags)/)?([^/]+)/"),
        # GitLab, gitlab.com or a self-managed host (a team's repositories): the `/-/` segment is GitLab's own
        re.compile(r"^https://[^/?#]+/.+?/-/(?:raw|blob|tree)/(refs/(?:heads|tags)/)?([^/?#]+)/"))


_CODE_FILE = re.compile(r"\.(?:py|rs|ps1|psm1|psd1|cs|go|ts|js|json|ya?ml|xml|proto|toml|sh|bicep)(?:[#?].*)?$", re.I)
_DOCS_PATH = re.compile(r"/(?:docs?|doc/en|Doc|documentation|articles|peps)/|\.(?:md|rst)(?:[#?].*)?$", re.I)


def code_file_source(row):
    """A source row whose url is a source-code or config file, not a documentation page (the CODE candidates)."""
    url = (row.get("url") or "").strip()
    return bool(_CODE_FILE.search(url)) and not _DOCS_PATH.search(url)


_CONTRACT = re.compile(r"(?:schema|metadata|swagger|openapi|stix)[^?#]*\.(?:json|ya?ml|xml|ts)(?:[#?].*)?$|\.proto(?:[#?].*)?$",
                       re.I)


def contract_source(row):
    """A source file that is a published contract, so a fact read from it is DOC, not CODE: a data file (json, yaml,
    xml, ts) whose path names a schema, metadata (Graph CSDL, OTel component metadata), a swagger/openapi definition
    or a STIX bundle, or a .proto; not a build file such as `schemas.config.yaml`. Neither artifact_sha256 nor
    _artifacts.csv tells this apart: both also hold pinned code and example configs."""
    url = (row.get("url") or "").strip()
    return bool(_CONTRACT.search(url)) and ".config." not in url.rsplit("/", 1)[-1]


def pinned_source(row):
    """A source row a CODE fact may cite: a pinned artifact (artifact_sha256), or a repository file url at a tag or
    commit, not at a branch (main, master, HEAD, refs/heads/...)."""
    if (row.get("artifact_sha256") or "").strip():
        return True
    for rx in _REF:
        m = rx.match((row.get("url") or "").strip())
        if m:
            return m.group(1) != "refs/heads/" and m.group(2).lower() not in FLOATING
    return False


# ---------------------------------------------------------------- files

def read(qpath):
    """The text of a kb file by its qualified path (`public/intune/x.md`), or of a repository file (the kb/_self docs,
    README.md), or None when it cannot be read."""
    return kbcommon.read(kbcommon.path_of(qpath))


def bare(qpath):
    """The path inside its root of a qualified path; a repository path as is."""
    r, rel = kbcommon.split(qpath)
    return rel if r else qpath


def root_name(qpath):
    """The root name of a qualified path, or None for a repository path."""
    r = kbcommon.split(qpath)[0]
    return r.name if r else None


def scope(domain=None, root=None):
    """The path prefix a pack, search or audit covers: a domain (bare `intune`: in every root; qualified
    `public/intune`) narrowed to one root. A domain of another root than `root` covers nothing."""
    if not root:
        return domain or None
    if not domain:
        return root
    r, _ = kbcommon.split(domain.strip("/"))
    if r:
        return domain if r.name == root else "\0"
    return f"{root}/{domain.strip('/')}"


def domain_prefix(domain):
    """A pack or search `domain` as the kb spells it, matched against the indexed paths without regard to case:
    `Intune` or `/intune/` is `intune`, `Public/Intune` is `public/intune`. None when no path is under it, so a
    caller can refuse it instead of reporting a question it narrowed to nothing as not in the kb."""
    p = (domain or "").strip().strip("/")
    if not p:
        return None
    paths = set(store().paths)
    if any(in_prefix(x, p) for x in paths):
        return p
    low, qualified = p.lower(), kbcommon.split(p.lower())[0] is not None
    for x in sorted(paths):
        rel = x if qualified else bare(x)
        if in_prefix(rel.lower(), low):
            return rel[:len(p)]
    return None


def domains():
    """The domain directories of every root (bare names, sorted): what a pack or search `domain` can name."""
    return sorted({bare(x).split("/")[0] for x in store().paths if "/" in bare(x) and not bare(x).startswith("_")})


def front_matter(text):
    meta = {}
    lines = text.splitlines()
    if lines[:1] == ["---"]:
        for ln in lines[1:]:
            if ln.strip() == "---":
                break
            k, _, v = ln.partition(":")
            meta[k.strip()] = v.strip().strip('"')
    meta["title"] = next((ln[2:].strip() for ln in lines if ln.startswith("# ")), meta.get("topic", ""))
    return meta


def is_article(text):
    return text.startswith("---\n") and "\ntopic:" in text.split("\n---", 2)[0]


# searched with --index only: this repository's README.md, each root's ledgers (qualified), the kb's own docs
INDEX_FILES = ("README.md",)
ROOT_INDEX_FILES = (kbcommon.ANSWERS, kbcommon.GAPS, kbcommon.CONFLICTS, kbcommon.COVERAGE_CSV)
# the kb's own docs (rules, tool reference, design): searched with --index only, never packed; listed by repository path
SELF_DIR = kbcommon.SELF
SELF_EVAL = os.path.join(SELF_DIR, kbcommon.DATA_DIR, "lookup_eval.csv")  # the `_self` tested questions
SELF_ALIASES = os.path.join(SELF_DIR, kbcommon.DATA_DIR, "aliases.csv")  # rule vocabulary, applied under `_self` only


def root_files(names):
    """The qualified paths of the named root-level files (ledgers) that exist, root by root."""
    return [kbcommon.qualify(r, n) for r in kbcommon.roots() for n in names if os.path.exists(os.path.join(r.path, n))]


def index_files():
    """The files only a search with `index` sees: this repository's README.md, each root's ledgers, then every .md
    under the kb's own docs (SELF_DIR, by repository path), sorted."""
    out = list(INDEX_FILES) + root_files(ROOT_INDEX_FILES)
    for root, dirs, files in os.walk(SELF_DIR):
        dirs.sort()
        out += sorted(kbcommon.repo_rel(os.path.join(root, f)) for f in files if f.endswith(".md"))
    return out


def locate(path):
    """The absolute real path a tool shows for `path`: a qualified path (`public/intune/x.md`), a repository path
    (kb/_self docs, README.md), or a bare path inside the public root (`intune/x.md`) when no root and no repository
    file has that name; a path found nowhere is taken as the public root's, so the caller reports it missing. The
    caller checks showable() and that the file exists."""
    full = kbcommon.path_of(path)
    if not os.path.exists(full) and kbcommon.split(path)[0] is None and not os.path.isabs(path):
        full = os.path.join(kbcommon.public().path, path)
    return os.path.realpath(full)


def qpath_of(full):
    """The qualified path (`public/intune/x.md`) of an absolute real path inside a root, '' for any other file."""
    for r in kbcommon.roots():
        base = os.path.realpath(r.path)
        if os.path.commonpath([full, base]) == base:
            return kbcommon.qualify(r, os.path.relpath(full, base))
    return ""


def showable(full):
    """Whether an absolute (real) path may be shown: a file of a root, of the kb's own docs (SELF_DIR) or the
    README.md an index search lists."""
    for base in [r.path for r in kbcommon.roots()] + [SELF_DIR]:
        base = os.path.realpath(base)
        if os.path.commonpath([full, base]) == base:
            return True
    return full == os.path.realpath(os.path.join(kbcommon.HOME, "README.md"))


def kb_files(exts=(".md", ".csv")):
    """Domain files of every root (not the root-level ledgers), by qualified path, root by root, sorted."""
    for rel, _entry in kb_entries(exts):
        yield rel


def kb_entries(exts=(".md", ".csv")):
    """(qualified path, os.DirEntry) of kb_files(), in its order: a top-down walk, each directory's files by name,
    then its subdirectories by name (SKIP_DIRS and dot directories left out, a symlinked directory not entered, as
    os.walk does). On Windows the entry's stat() comes from the directory listing, with no call per file."""
    for r in kbcommon.roots():
        yield from _walk_entries(r, r.path, "", exts)


def _walk_entries(r, path, rel, exts):
    try:
        with os.scandir(path) as it:
            entries = list(it)
    except OSError:
        return
    dirs, files = [], []
    for e in entries:
        try:
            (dirs if e.is_dir() else files).append(e)
        except OSError:
            files.append(e)
    if rel:  # the root's own files are its ledgers, not domain files
        for e in sorted(files, key=lambda e: e.name):
            if e.name.endswith(exts):
                yield kbcommon.qualify(r, rel + e.name), e
    for e in sorted(dirs, key=lambda e: e.name):
        if e.name in SKIP_DIRS or e.name.startswith("."):
            continue
        try:
            if e.is_symlink():
                continue
        except OSError:
            continue
        yield from _walk_entries(r, e.path, rel + e.name + "/", exts)


_CACHE = {}
FP_MEMO = 2.0  # seconds: one command computes the fingerprint once; a long-running server sees an edit on its next call
_FP = [0.0, None]


def fingerprint():
    """The key of the current kb's content, which names its index file (index_path) and keys the in-process caches:
    any edit of a file the tools read gives a new value, and two checkouts of one content (a clone and its fresh
    worktree) get the same one, so a new worktree reads the index its clone already built. Replaces a time-to-live
    cache: nothing is rebuilt while no file changed, however long a server idles.
    Two steps keep a warm call cheap. stat_fingerprint(), over each file's path, time and size, says whether
    anything changed since this checkout last asked; a memo file in the index directory maps it to the content key
    (content_key: git's blob ids, independent of the checkout's path and the files' times), which is computed, with
    two git calls, only when the stat fingerprint is new. Without an index directory (KB_INDEX=0) or git, the stat
    fingerprint is the key, as before. The memo counts from the end of the computation."""
    if _FP[1] is not None and time.monotonic() - _FP[0] < FP_MEMO:
        return _FP[1]
    files = fingerprint_files()
    sfp = stat_fingerprint(files)
    d = index_dir()
    fp = _memo_key(d, sfp, files) if d else sfp
    _FP[:] = [time.monotonic(), fp]
    return _FP[1]


def fingerprint_files():
    """[(label, absolute path, os.DirEntry or None)] of every file the tools read: domain .md/.csv, _sources.csv,
    the ledgers, aliases.csv, signals.csv, doc2query/expansions.csv, the `_self` eval and aliases files, this module,
    kf_index.py (the weighing and the index layout) and kbid.py. The domain files come with their directory entry (kb_entries): on Windows its stat() needs no call."""
    extra = [*root_files((kbcommon.SOURCES,)), *index_files(), *alias_files(), *data_files("signals.csv"),
             *data_files("doc2query/expansions.csv"), kbcommon.repo_rel(SELF_EVAL), kbcommon.repo_rel(SELF_ALIASES),
             os.path.join(TOOLS, "kbfacts.py"), os.path.join(TOOLS, "kf_index.py"), os.path.join(TOOLS, "kbid.py")]
    return [*((rel, e.path, e) for rel, e in kb_entries()), *((rel, kbcommon.path_of(rel), None) for rel in extra)]


def _stat(path, entry):
    return entry.stat() if entry is not None else os.stat(path)


def stat_fingerprint(files):
    """sha1 over (path, mtime_ns, size) of `files`, the set of roots and KB_DOC2QUERY: whether anything changed in
    this checkout. The domain files' times and sizes come from the directory listing: an os.stat per file costs about
    0.7 ms in a Hyper-V container, most of a warm pack there, and on a loaded host each pack outlasted FP_MEMO and
    paid it again."""
    h = hashlib.sha1(f"{INDEX_VERSION}|{os.environ.get('KB_DOC2QUERY', '')}".encode())
    h.update(os.pathsep.join(r.path for r in kbcommon.roots()).encode())  # the set of roots: one added or removed
    for rel, path, entry in files:
        try:
            st = _stat(path, entry)
            h.update(f"{rel}\0{st.st_mtime_ns}\0{st.st_size}\n".encode())
        except OSError:
            h.update(f"{rel}\0-\n".encode())
    return h.hexdigest()


def home_label(path):
    """`path` relative to this repository with `/` (the same in every checkout), or the absolute path outside it."""
    try:
        rel = os.path.relpath(path, kbcommon.HOME)
    except ValueError:  # another drive (Windows)
        return os.path.abspath(path)
    return os.path.abspath(path) if rel == os.pardir or rel.startswith(os.pardir + os.sep) else rel.replace(os.sep, "/")


def git_out(*args):
    """stdout bytes of a read-only git command in this repository, or None when git fails or is missing."""
    try:
        p = subprocess.run(["git", "-C", kbcommon.HOME, *args], capture_output=True, timeout=60,
                           env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    except (OSError, subprocess.SubprocessError):
        return None
    return p.stdout if p.returncode == 0 else None


def git_blob_id(path):
    """The blob id git would give the file's bytes (sha1 of `blob <size>\\0` and the bytes)."""
    with open(path, "rb") as f:
        data = f.read()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def content_key(files):
    """sha1 over (repository path, blob id) of `files`, the set of roots by repository path and KB_DOC2QUERY, or
    None when git cannot list this repository. A tracked file git reports unchanged takes its blob id from git's
    index (`ls-files -s`); a modified or untracked one is hashed as git would hash it (`ls-files -m -o`), and so is
    one marked assume-unchanged or skip-worktree (`ls-files -v` tags it lowercase or `S`), which `-m` never reports
    however its bytes differ; a file outside the repository (a KB_ROOTS root) by its absolute path, time and size,
    which every checkout shares."""
    staged, changed = git_out("ls-files", "-s", "-v", "-z"), git_out("ls-files", "-z", "-m", "-o", "--exclude-standard")
    if staged is None or changed is None:
        return None
    blobs = {}
    for rec in staged.split(b"\0"):
        meta, _, name = rec.partition(b"\t")
        parts = meta.split()
        if len(parts) == 4 and parts[3] == b"0" and not (parts[0].islower() or parts[0] == b"S"):  # stage 0, git checks it
            blobs[name.decode("utf-8", "surrogateescape")] = parts[2].decode()
    dirty = set(changed.decode("utf-8", "surrogateescape").split("\0"))
    h = hashlib.sha1(f"{INDEX_VERSION}|{os.environ.get('KB_DOC2QUERY', '')}|content".encode())
    h.update(os.pathsep.join(home_label(r.path) for r in kbcommon.roots()).encode())
    for _rel, path, entry in files:
        label = home_label(path)
        try:
            if os.path.isabs(label):
                st = _stat(path, entry)
                h.update(f"{label}\0{st.st_mtime_ns}\0{st.st_size}\n".encode())
            else:
                h.update(f"{label}\0{blobs[label] if label in blobs and label not in dirty else git_blob_id(path)}\n".encode())
        except OSError:
            h.update(f"{label}\0-\n".encode())
    return h.hexdigest()


MEMO_DAYS = 7  # a checkout's memo file unused this long is removed (a worktree gone)


def _memo_key(d, sfp, files):
    """The content key for stat fingerprint `sfp`: from this checkout's memo file in index directory `d` when it was
    written for `sfp`, else content_key() now, written there for the next process (best effort). The stat
    fingerprint when git cannot give a key."""
    memo = os.path.join(d, f"kbkey-{hashlib.sha1(kbcommon.HOME.encode()).hexdigest()[:12]}.txt")
    try:
        with open(memo, encoding="utf-8") as f:
            got = f.read().split()
        if len(got) == 2 and got[0] == sfp:
            return got[1]
    except OSError:
        pass
    key = content_key(files)
    if key is None:
        return sfp
    tmp = None
    try:
        os.makedirs(d, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".kbkey-", suffix=".tmp", dir=d)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(f"{sfp} {key}\n")
        os.replace(tmp, memo)
        names = os.listdir(d)
    except OSError:
        names = []
    finally:
        if tmp and os.path.exists(tmp):
            remove_file(tmp)
    now = time.time()
    for name in names:
        full = os.path.join(d, name)
        try:
            if name.startswith("kbkey-") and full != memo and now - os.stat(full).st_mtime > MEMO_DAYS * 86400:
                os.remove(full)
        except OSError:
            pass
    return key


def remove_file(path):
    try:
        os.remove(path)
    except OSError:
        pass


def cached(key, build):
    """build(), kept until any kb file changes (fingerprint)."""
    fp = fingerprint()
    hit = _CACHE.get(key)
    if hit and hit[0] == fp:
        return hit[1]
    val = build()
    _CACHE[key] = (fp, val)
    return val


def articles():
    """{path: meta} for every article."""
    return cached("articles", _articles)


def _articles():
    """{qualified path: front matter}; `topic` qualified by the root (`public/intune/win32-apps`)."""
    out = {}
    for q in kb_files((".md",)):
        text = read(q)
        if text and is_article(text):
            meta = front_matter(text)
            meta["topic"] = kbcommon.qualify(root_name(q), meta.get("topic") or bare(q)[:-3])
            out[q] = meta
    return out


def topic_files():
    """{qualified topic: [qualified files]}: an article's own .md, its `files:` list, and same-stem data files."""
    out = {}
    for q, meta in articles().items():
        r = root_name(q)
        files = [q] + [kbcommon.qualify(r, f.strip()) for f in meta.get("files", "").strip("[]").split(",") if f.strip()]
        files += [f for f in (q[:-3] + ".csv",) if os.path.exists(kbcommon.path_of(f))]
        out[meta["topic"]] = sorted(set(files))
    return out


# ---------------------------------------------------------------- fact units

def md_units(rel, text, untagged=False):
    """Fact units of one article: bullets (with continuation lines), table rows and tagged paragraph lines. With
    `untagged`, also the bullets, table rows and prose paragraphs that carry no tag (Summary, Reference and Examples
    content; table header and separator rows excluded) and each fenced code block as one unit (line = its first
    line), with tags=[]: pack and search rank them, fact counts never include them."""
    lines = text.splitlines()
    body = lines.index("---", 1) + 1 if lines[:1] == ["---"] and "---" in lines[1:] else 0
    section, cur, fenced, block = "", None, False, None
    units = []

    def flush():
        if cur and TAG.search(cur["text"]):
            cur["tags"] = tags_in(cur["text"])
            units.append(cur)
        elif cur and untagged and cur.get("list") and not re.fullmatch(r"\|[\s:|-]*\|?", cur["text"]):
            nxt = lines[cur["line"]] if cur["line"] < len(lines) else ""
            if not (cur["text"].startswith("|") and re.fullmatch(r"\s*\|[\s:|-]+\|?\s*", nxt)):  # a header row
                cur["tags"] = []
                units.append(cur)
        elif cur and untagged and not cur.get("list"):  # a prose paragraph
            cur["tags"] = []
            units.append(cur)

    for n, ln in enumerate(lines, start=1):
        if n <= body:
            continue
        s = ln.strip()
        if s.startswith(("```", "~~~")):
            fenced = not fenced
            if fenced:
                block = {"path": rel, "line": n + 1, "section": section, "text": "", "tags": [], "code": True}
            elif untagged and block["text"].strip():
                block["text"] = block["text"].strip()
                units.append(block)
            continue
        if fenced:
            block["text"] += " " + s
            continue
        if ln.startswith("#"):
            flush()
            cur = None
            section = ln.lstrip("#").strip()
            continue
        if re.match(r"\s*[-*] ", ln) or s.startswith("|"):
            flush()
            cur = {"path": rel, "line": n, "section": section, "text": s[2:] if not s.startswith("|") else s, "list": True}
            if s.startswith("|"):
                flush()
                cur = None
        elif not s:
            flush()
            cur = None
        elif cur is not None:
            cur["text"] += " " + s
        else:
            cur = {"path": rel, "line": n, "section": section, "text": s}
    flush()
    return units


def csv_units(rel, text):
    """One unit per data row. Tags come from `[...]` tags in any cell, or a bare kind in a `tag`/`evidence`
    column together with the ids of the source columns."""
    units = []
    try:
        rows = csv.DictReader(io.StringIO(text.lstrip("﻿").replace("\0", ""), newline=""))
        for i, row in enumerate(rows, start=2):
            cells = {k: (v or "") for k, v in row.items() if k}
            body = "; ".join(f"{k}={v}" for k, v in cells.items() if v)
            tags = tags_in(body)
            if not tags:
                kind = next((cells[c].strip().upper() for c in ("tag", "evidence", "status_evidence")
                             if cells.get(c, "").strip().upper() in EVIDENCE_KINDS), None)
                ids = [i for k, v in cells.items() if "source" in k for i in ID.findall(v)]
                if kind:
                    tags = [{"kind": kind, "ids": ids, "note": ""}]
                elif ids:
                    tags = [{"kind": "DOC", "ids": ids, "note": "source column"}]
            units.append({"path": rel, "line": i, "section": os.path.basename(rel), "text": body, "tags": tags})
    except csv.Error:
        pass
    return units


def in_prefix(rel, prefix):
    """Whether qualified path `rel` is under `prefix`: `public` matches public/..., `public/auth/kerberos` matches
    public/auth/kerberos.md and .csv, never public/authz/...; a bare `auth` (its first part names no root) matches
    auth/ in every root."""
    p = prefix.strip("/")
    if kbcommon.split(p)[0] is None:
        rel = bare(rel)
    return rel == p or rel.startswith(p + "/") or ("/" in p and rel.startswith(p))


def units(prefix=None, with_csv=True, untagged=False):
    """Every fact unit under a path prefix (in_prefix: `public`, `auth`, `public/auth/kerberos`), paths qualified;
    `untagged` adds the
    untagged bullets, table rows and paragraphs of articles, and of the other .md files in the domain directories
    (csv rows are always all included, tagged or not)."""
    out = []
    exts = (".md", ".csv") if with_csv else (".md",)
    for rel in kb_files(exts):
        if prefix and not in_prefix(rel, prefix):
            continue
        text = read(rel)
        if text is None:  # walked a moment ago, so it exists: unreadable (permissions, a directory named .md)
            print(f"warning: skipped {rel}: cannot read", file=sys.stderr)
            continue
        if rel.endswith(".md"):
            if is_article(text) or untagged:
                out += md_units(rel, text, untagged)
        elif with_csv:
            out += csv_units(rel, text)
    return out


# ---------------------------------------------------------------- ledgers

def ledger_entries(name):
    """Entries of `_gaps.md` or `_conflicts.md`: {file, line, end, section, text}, `file` qualified. A bare ledger
    name reads it in every root; a qualified one (`public/_gaps.md`) in that root. A `### ` line followed directly
    by bullets is a sub-heading, not an entry."""
    if kbcommon.split(name)[0] is None:
        return [e for q in root_files((name,)) for e in ledger_entries(q)]
    text = read(name) or ""
    out, section, cur = [], "", None

    def close(nxt_is_bullet=False):
        if cur and not (cur["heading"] and not cur["body"] and nxt_is_bullet):
            out.append({k: v for k, v in cur.items() if k not in ("heading", "body")})

    for n, ln in enumerate(text.splitlines(), start=1):
        if ln.startswith("## "):
            close()
            cur, section = None, ln[3:].strip()
        elif ln.startswith("### ") or ln.startswith("- "):
            close(ln.startswith("- "))
            cur = {"file": name, "line": n, "end": n, "section": section, "text": ln.lstrip("#- ").strip(),
                   "heading": ln.startswith("### "), "body": False}
        elif cur is not None and ln.strip():
            cur["text"] += " " + ln.strip()
            cur["end"], cur["body"] = n, True
    close()
    return out


def link_entries(entries, tfiles=None, sources=None):
    """Add `explicit` (topics named by marker, path or section) and `via_sources` (topics whose files cite a source
    id named in the entry) to each entry."""
    tfiles = tfiles if tfiles is not None else topic_files()
    sources = sources if sources is not None else source_rows()
    file_topic = {f: t for t, fs in tfiles.items() for f in fs}
    for e in entries:  # an entry names its own root's topics root-relative: `topic: intune/x`, `## intune/x`
        r = root_name(e["file"]) or kbcommon.public().name  # a bare ledger name is the public root's
        own = {bare(t): t for t in tfiles if root_name(t) == r}
        named = set()
        for m in TOPIC_MARK.finditer(e["text"]):
            named.add(kbcommon.qualify(r, m.group(1).removesuffix(".md").removesuffix(".csv")))
        for t, q in own.items():
            if re.search(rf"(?<![\w/-]){re.escape(t)}(?:\.md|\.csv)?(?![\w-])", e["text"]):
                named.add(q)
        if e["section"] in own:
            named.add(own[e["section"]])
        e["ids"] = sorted(set(ID.findall(e["text"])), key=kbid.sort_key)
        via = set()
        for sid in e["ids"]:
            row = sources.get(sid, {})
            for f in filter(None, (row.get("used_in") or "").split(";")):
                f = kbcommon.qualify(row.get("root") or r, f.strip())
                if f in file_topic:
                    via.add(file_topic[f])
        e["explicit"], e["via_sources"] = sorted(named), sorted(via - named)
    return entries


def source_rows():
    return cached("sources", _source_rows)


def _source_rows():
    """{id: row} of every root's _sources.csv (ids are unique by their root's prefix); each row gains `root`, the
    name of the root whose ledger holds it (its `used_in` paths are relative to that root). OSError when the public
    root's ledger cannot be read; another root may have none yet."""
    out = {}
    for r in kbcommon.roots():
        path = os.path.join(r.path, kbcommon.SOURCES)
        if r.name != kbcommon.public().name and not os.path.exists(path):
            continue
        with open(path, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                row["root"] = r.name
                out.setdefault(row["id"], row)
    return out


# ---------------------------------------------------------------- audit

def audit(prefix=None, status=None, root=None):
    """One row per article under a prefix (bare or qualified: in_prefix), in one root or all: status, dates, fact
    counts by kind (a fact counts once per kind it carries), `ended` (the facts whose validity window has ended,
    window_ended), the gap/conflict entries linked to it and `flags`, the
    lines of its files that a committed feedback report flags (feedback_flags)."""
    prefix = scope(prefix, root)
    tfiles = topic_files()
    srcs = source_rows()
    ledgers = {n: link_entries(ledger_entries(n), tfiles, srcs) for n in (kbcommon.GAPS, kbcommon.CONFLICTS)}
    flags = feedback_flags()
    rows = []
    for rel, meta in sorted(articles().items()):
        if prefix and not in_prefix(rel, prefix):
            continue
        if status and meta.get("status") != status:
            continue
        topic = meta["topic"]
        us = [u for f in tfiles.get(topic, [rel]) for u in
              (md_units(f, read(f) or "") if f.endswith(".md") else csv_units(f, read(f) or ""))]
        counts = Counter(k for u in us for k in kinds_of(u["tags"]))
        row = {"path": rel, "topic": topic, "status": meta.get("status", ""), "priority": meta.get("priority", ""),
               "retrieved_utc": meta.get("retrieved_utc", ""), "facts": sum(1 for u in us if u["tags"]),
               **{k: counts.get(k, 0) for k in EVIDENCE_KINDS},
               "ended": sum(1 for u in us if u["tags"] and window_ended(u["text"])),
               "flags": sum(len(flags.get(f, {})) for f in tfiles.get(topic, [rel]))}
        for n, key in ((kbcommon.GAPS, "gaps"), (kbcommon.CONFLICTS, "conflicts")):
            row[key] = [e for e in ledgers[n] if topic in e["explicit"]]
            row[key + "_via_sources"] = [e for e in ledgers[n] if topic in e["via_sources"]]
        rows.append(row)
    return rows


# ---------------------------------------------------------------- decisions (beside the facts of a pack and a show)

DECISION_ANSWER_SHARE = 0.6  # an active decision whose text holds this share of a question's informative words answers it
MAX_DECISIONS = 3  # decision lines one pack prints
ITEM_DECISIONS = 6  # decision lines the brief of a backlog item prints
DECISION_CLIP = 300  # characters of a decision's text a line shows
DECISION_BUDGET_SHARE = 3  # a pack's decision lines cost at most 1/3 of its budget, and count inside it
DECISION_RANK = {"active": 0, "proposed": 1, "invalidated": 2}  # `superseded` is never shown


_DECISIONS = [None, []]  # [signature of the decision files, their rows]
_LOGS = [None, []]  # [signature of the log files, their rows]


def _ledger_stores(name):
    """(root name, qualifier, file, label) of each `name` file a lookup reads: every served root's and, unless the
    server is limited to named roots, kb/_self's."""
    stores = [(r.name, r.name, os.path.join(r.path, name), kbcommon.qualify(r, name)) for r in kbcommon.roots()]
    if not kbcommon.serving():
        stores.append(("_self", "", os.path.join(SELF_DIR, name), "kb/_self/" + name))
    return stores


def _cached_rows(cache, name, required, make):
    """The rows of every `name` file (_ledger_stores), read again when a file's time or size changes."""
    stores = _ledger_stores(name)
    sig = []
    for _, _, full, _ in stores:
        try:
            st = os.stat(full)
            sig.append((full, st.st_mtime_ns, st.st_size))
        except OSError:
            continue
    if cache[0] != sig:
        cache[:] = [sig, _read_rows(stores, required, make) if sig else []]
    return cache[1]


def decision_rows():
    """Every decision row of the served roots and, unless the server is limited to named roots, of kb/_self, as dicts
    `id, text, status, by, date, context, source, reason` (its invalidated_reason) plus `root` (its store's name, `_self`),
    `path` and `line` (where the row starts, as `rag.py show` takes it) and `refs`, the context as [(kind, value)]
    with an article's or a domain's value qualified (`public/auth/kerberos`). Rows of every status; a file that cannot
    be read gives none (check.py reports it); [] for a kb that keeps no decision. Read again when a decision file's
    time or size changes, so a decision edit costs no index rebuild (these files are not in the pack index)."""
    return _cached_rows(_DECISIONS, kbcommon.DECISIONS, ("id", "text", "status"), lambda row, at: {
        "id": row["id"], "text": " ".join((row.get("text") or "").split()), "status": row.get("status", ""),
        "by": row.get("by", ""), "date": row.get("date", ""), "context": row.get("context", ""),
        "source": " ".join((row.get("source") or "").split()), "reason": row.get("invalidated_reason", ""), **at})


def _read_rows(stores, required, make):
    out = []
    for name, prefix, full, label in stores:
        if not os.path.isfile(full):
            continue
        try:
            with open(full, encoding="utf-8-sig", newline="") as f:
                rd = csv.reader(f)
                header = next(rd, [])
                last = rd.line_num
                if not set(required) <= set(header):
                    continue
                for cells in rd:
                    first, last = last + 1, rd.line_num
                    row = dict(zip(header, cells))
                    if not row.get("id"):
                        continue
                    refs = [(k, f"{prefix}/{v}" if prefix and k in ("article", "domain") else v)
                            for k, v in kbcommon.context_refs(row.get("context"))]
                    out.append(make(row, {"root": name, "path": label, "line": first, "refs": refs}))
        except (OSError, UnicodeDecodeError, csv.Error):
            continue
    return out


def decision_places(d):
    """The qualified paths a decision is about: its context's articles and domains, and its own root."""
    return [v for k, v in d["refs"] if k in ("article", "domain")] + ([d["root"]] if d["root"] != "_self" else [])


def decision_in_scope(d, prefix):
    """Whether a decision belongs to a pack or audit narrowed to `prefix` (scope(): a root, a domain): its root or
    one of its context's articles or domains is under it."""
    return any(in_prefix(p, prefix) for p in decision_places(d))


def decision_link(d, arts, keys, srcs, cited):
    """How decision `d` is tied to what is being shown: `cited` (a shown fact carries its `[DECISION id]` tag, or the
    decision's `fact:` is a shown fact: strong), `context` (its `article:` is a shown article, its `domain:` holds
    one, or its `source:` is cited by a shown fact), else ''. `arts` are qualified article paths, `keys` fact keys,
    `srcs` source ids, `cited` decision ids."""
    if d["id"] in cited:
        return "cited"
    link = ""
    for kind, v in d["refs"]:
        if kind == "fact" and v in keys:
            return "cited"
        if (kind == "article" and f"{v}.md" in arts) or (kind == "domain" and any(in_prefix(a, v) for a in arts)) \
                or (kind == "source" and v in srcs):
            link = "context"
    return link


def _shown_ties(us):
    """(fact keys, cited source ids, cited decision ids) of fact units; the keys are hashed only when a decision names
    a fact, so a kb with no decision pays nothing."""
    srcs = {i for u in us for p in u["tags"] for i in p["ids"]}
    cited = {p["decision"] for u in us for p in u["tags"] if p.get("decision")}
    keys = {fact_key(u["text"]) for u in us} if any(k == "fact" for d in decision_rows() for k, _ in d["refs"]) else set()
    return keys, srcs, cited


def decision_label(d):
    """What a decision line says it is: `decided by <by> on <date>` (active), `proposed (not confirmed)`, or
    `invalidated because <reason>`."""
    if d["status"] == "active":
        return "decided" + (f" by {d['by']}" if d["by"] else "") + (f" on {d['date']}" if d["date"] else "")
    if d["status"] == "proposed":
        return "proposed (not confirmed)"
    if d["status"] == "superseded":
        return "superseded"
    return f"invalidated because {d['reason'] or 'no reason recorded'}"


def decision_line(d, source=False):
    """`- PATH:LINE <label>: <text> [DECISION id]`; PATH:LINE is the row, which `rag.py show` prints. With `source`,
    the row's source follows the text: `<text> (source: <source>) [DECISION id]`."""
    cited = f" (source: {clip(d['source'], DECISION_CLIP)})" if source and d["source"] else ""
    return f"- {d['path']}:{d['line']} {decision_label(d)}: {clip(d['text'], DECISION_CLIP)}{cited} [DECISION {d['id']}]"


def _shown(invalidated):
    return [d for d in decision_rows()
            if d["status"] in ("active", "proposed") or (invalidated and d["status"] == "invalidated")]


def decisions_for(informative, named, arts, cand, prefix=None, invalidated=False):
    """The decisions a pack prints beside its facts, best first (active, then proposed, then invalidated when
    `invalidated`; a `superseded` one never), each the row plus `hit` (the question's informative words its text
    holds) and `answers`. A decision is printed when it answers the question or is tied to a shown fact or article
    (decision_link) and holds a word of the question (one cited by a shown fact, or naming it, needs none; nor does an
    invalidated one, which is shown only when asked for).
    It answers when its text holds DECISION_ANSWER_SHARE of the informative words and every name the question uses.
    Only an active one that answers lifts the pack's coverage (pack): a proposed or an invalidated one never does.
    `arts` are the shown articles and `cand` the fact units the pack may print; `prefix` is the pack's scope()."""
    rows = _shown(invalidated)
    if not rows:
        return []
    keys, srcs, cited = _shown_ties(cand)
    want, out = set(informative), []
    for d in rows:
        link = decision_link(d, arts, keys, srcs, cited)
        if prefix and not link and not decision_in_scope(d, prefix):
            continue
        dterms = set(key_terms(d["text"]))
        hit = sorted(want & dterms)
        answers = bool(want) and len(hit) >= DECISION_ANSWER_SHARE * len(want) and named <= dterms
        if answers or link == "cited" or (link and (hit or d["status"] == "invalidated")):
            out.append({**d, "hit": hit, "answers": answers})
    out.sort(key=lambda d: (DECISION_RANK[d["status"]], not d["answers"], -len(d["hit"]), d["id"]))
    return out


def show_decisions(qpath, first, last, invalidated=False):
    """Decision lines for lines `first`..`last` of the kb file `qpath` (`rag.py show`, `kb_show`): the decisions a
    fact starting in that range cites (`[DECISION id]`) or names (`fact:`), and those whose `article:` is the file
    or whose `domain:` holds it, labelled as a pack's; [] when none, or the file is no article or data file."""
    rows = _shown(invalidated)
    if not rows or not qpath.endswith((".md", ".csv")):
        return []
    text = read(qpath)
    if text is None:
        return []
    us = md_units(qpath, text) if qpath.endswith(".md") else csv_units(qpath, text)
    keys, srcs, cited = _shown_ties([u for u in us if first <= u["line"] <= last])
    found = [d for d in rows if decision_link(d, {qpath}, keys, srcs, cited)]
    found.sort(key=lambda d: (DECISION_RANK[d["status"]], d["id"]))
    return [decision_line(d) for d in found]


HEADING_RX = re.compile(r" {0,3}(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*\Z")  # selfdoc.HEADING_RX
FENCE_RX = re.compile(r" {0,3}(`{3,}|~{3,})")  # selfdoc.FENCE_RX


def norm_heading(text):
    """A heading without case, runs of spaces or backticks, as `selfdoc.py section` compares it."""
    return " ".join(text.replace("`", "").split()).casefold()


def section_headings(rel, wanted):
    """The normalised headings (norm_heading) of the sections of doc `rel` that hold a line of `wanted`: the nearest
    heading above each line and every heading above that one. Headings in fenced code and front matter are no headings."""
    lines = (read(rel) or "").splitlines()
    start = next((i + 1 for i in range(1, len(lines)) if lines[i].strip() in ("---", "...")), 0) if lines[:1] == ["---"] else 0
    stack, fence, found = [], None, set()
    for n in range(start + 1, len(lines) + 1):
        m = FENCE_RX.match(lines[n - 1])
        if fence:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = None
        elif m:
            fence = m.group(1)
        elif h := HEADING_RX.match(lines[n - 1]):
            while stack and stack[-1][0] >= len(h.group(1)):
                stack.pop()
            stack.append((len(h.group(1)), norm_heading(h.group(2))))
        if n in wanted:
            found.update(t for _, t in stack)
    return found


def self_places(passages):
    """{doc: normalised headings of the sections that hold one of `passages`} for the docs they are in."""
    lines = defaultdict(set)
    for u in passages:
        lines[u["path"]].add(u["line"])
    return {rel: section_headings(rel, at) for rel, at in lines.items()}


def self_ties(d):
    """[(doc path, normalised heading or '')] of the `article:_self/<doc>` and `article:_self/<doc>#<Heading>`
    references of decision `d`: the whole doc or one of its sections."""
    return [(f"kb/_self/{doc.split('/', 1)[1]}.md", norm_heading(heading)) for kind, v in d["refs"] if kind == "article"
            for doc, _, heading in [v.partition("#")] if doc.startswith(SELF_ROOT + "/")]


def tied_decisions(places, invalidated=False, only_active=False):
    """The decisions (best first) tied by an `article:_self/...` context to a doc of `places` ({doc: the normalised
    headings of its sections that count, or None for every section}): a whole-doc reference needs the doc only, a
    section reference one of its headings. As _shown(invalidated); `only_active` leaves out the proposed ones."""
    out = [d for d in _shown(invalidated) if (d["status"] == "active" or not only_active)
           and any(doc in places and (not h or places[doc] is None or h in places[doc]) for doc, h in self_ties(d))]
    return sorted(out, key=lambda d: (DECISION_RANK[d["status"]], d["id"]))


def item_decisions(item):
    """The active decisions of a backlog item's brief (item_brief): those whose context names the item, then those
    tied (tied_decisions) to any section of its docs."""
    named = [d for d in _shown(False) if d["status"] == "active" and ("item", item["id"]) in d["refs"]]
    return named + [d for d in tied_decisions({doc: None for doc in item["docs"]}, only_active=True) if d not in named]


def decision_block(dec, budget, cap, source=False):
    """(lines, decisions) of the first `cap` of `dec`, as many as fit a DECISION_BUDGET_SHARE-th of `budget` tokens
    (the first always)."""
    lines = []
    for d in dec[:cap]:
        line = decision_line(d, source)
        if lines and sum(map(len, lines)) + len(line) > int(budget * 3.5) // DECISION_BUDGET_SHARE:
            break
        lines.append(line)
    return lines, dec[:len(lines)]


def decision_conflicts(prefix=None, root=None):
    """[(context ref, [decision rows])] of every context reference (`kind:value`, an article's or a domain's value
    qualified) that two or more active decisions share, sorted: possible contradictions, for a person to read; no
    check fails on them and nothing is blocked. Narrowed to a prefix or root as audit() is."""
    want = scope(prefix, root)
    by = defaultdict(list)
    for d in decision_rows():
        if d["status"] != "active" or (want and not decision_in_scope(d, want)):
            continue
        for ref in dict.fromkeys(f"{k}:{v}" for k, v in d["refs"] if k):
            by[ref].append(d)
    return sorted(((ref, ds) for ref, ds in by.items() if len(ds) > 1), key=lambda x: x[0])


# ---------------------------------------------------------------- observed signals (LOG lines beside a lookup's facts)

LOG_LABEL = "observed signal (LOG, not a fact):"  # the line a block of LOG lines opens with
MAX_LOGS = 2  # LOG lines one pack or show prints
MAX_AUDIT_LOGS = 20  # LOG lines one audit prints
LOG_CLIP = 200  # characters of an observation a line shows


def log_rows():
    """Every LOG row of the served roots' `_logs.csv` and, unless the server is limited to named roots, of kb/_self's,
    as dicts like decision_rows(): `id, text` (the observation), `status`, `observed_from`, `observed_to`, `context`,
    `reason`, `root`, `path`, `line` and `refs`. Rows of every status; [] for a kb that keeps none (a public root
    holds no such file). Read again when a file's time or size changes."""
    return _cached_rows(_LOGS, LOG_FILE, ("id", "observation", "status"), lambda row, at: {
        "id": row["id"], "text": " ".join((row.get("observation") or "").split()), "status": row.get("status", ""),
        "observed_from": row.get("observed_from", ""), "observed_to": row.get("observed_to", ""),
        "context": row.get("context", ""), "reason": row.get("invalidated_reason", ""), **at})


def log_line(r):
    """`- PATH:LINE observed FROM to TO: <observation> [LOG id]`; PATH:LINE is the row, which `rag.py show` prints."""
    return (f"- {r['path']}:{r['line']} observed {r['observed_from']} to {r['observed_to']}: "
            f"{clip(r['text'], LOG_CLIP)} [LOG {r['id']}]")


def _active_logs():
    return [r for r in log_rows() if r["status"] == "active"]


def _log_ties(us):
    """(fact keys, cited source ids, cited LOG ids) of fact units, as _shown_ties does for decisions."""
    srcs = {i for u in us for p in u["tags"] for i in p["ids"]}
    cited = {i for u in us for i in log_ids_in(u["text"])}
    keys = {fact_key(u["text"]) for u in us} if any(k == "fact" for r in log_rows() for k, _ in r["refs"]) else set()
    return keys, srcs, cited


def logs_for(arts, us):
    """The active LOG rows a lookup prints beside the facts `us` of the qualified articles `arts`, newest first: the row's
    context is a shown article (`article:`, or a `domain:` that holds one), a shown fact (`fact:`), a source a shown
    fact cites, or a shown fact cites the row (`[LOG id]`). A proposed or an invalidated row, and one about an `item:`
    alone, is never printed. A LOG line is context beside the facts, never an answer: it takes no part in a pack's
    verdict, route or `check:` lines."""
    rows = _active_logs()
    if not rows:
        return []
    keys, srcs, cited = _log_ties(us)
    tied = sorted((r for r in rows if decision_link(r, arts, keys, srcs, cited)), key=lambda r: r["id"])
    return sorted(tied, key=lambda r: r["observed_to"], reverse=True)


FLAG_LABEL = "flagged (feedback, not a fact):"  # what a line a feedback report names opens with
FLAG_ISSUES = ("wrong", "stale")  # the issue classes of a report's line that flag it (ql_capture.FEEDBACK_ISSUES)
MAX_FLAGS = 3  # flagged lines one pack or show prints
_FLAGS = [None, []]  # [signature of the store's run files, [(path, line, issue, day)] of every report line]
_CHANGED = {}  # {(path, mtime_ns, size): ([(commit, day)] newest first, whether the working tree differs)}
_BASED = {}  # {(path, commit): the file's lines at that commit, None when git cannot show it}


def _git_out(cwd, *args, strip=True):
    """Stdout of `git -C cwd ARGS`, None on a non-zero exit or a git that cannot run."""
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    try:
        p = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=60, env=env)
    except (OSError, subprocess.SubprocessError):
        return None
    if p.returncode != 0:
        return None
    return p.stdout.strip() if strip else p.stdout


def git_history(path):
    """([(commit, day)], dirty) of the kb file `path` (qualified) in its own git repository: its commits that changed
    it, newest first, each with its committer day (YYYY-MM-DD), and whether the working tree differs from the last
    one; ([], False) when git cannot tell (no repository, an untracked file). Kept per the file's time and size."""
    full = kbcommon.path_of(path)
    try:
        st = os.stat(full)
    except OSError:
        return [], False
    key = (path, st.st_mtime_ns, st.st_size)
    if key not in _CHANGED:
        cwd, name = os.path.dirname(full), os.path.basename(full)
        log = _git_out(cwd, "log", "--format=%H %cs", "--", name) or ""
        commits = [tuple(x.split()) for x in log.splitlines() if len(x.split()) == 2]
        dirty = bool(commits) and bool(_git_out(cwd, "status", "--porcelain", "--untracked-files=no", "--", name))
        _CHANGED[key] = (commits, dirty)
    return _CHANGED[key]


def git_log_day(path):
    """The day (YYYY-MM-DD) the kb file `path` (qualified) last changed: its last commit's date in its own git
    repository, today when the working tree differs from that commit; "" when git cannot tell."""
    commits, dirty = git_history(path)
    return time.strftime("%Y-%m-%d") if dirty else (commits[0][1] if commits else "")


def _flag_reports(store, files):
    """[(path, line, issue, day)] of every report line of the run files `files` (ql_store.run_stats): each entry id
    once (its first run file, as ql_store.store_entries reads them). The entries of a file are kept, with their
    report lines, in a cache file of the index directory under the file's stat, so a process parses only the run
    files that changed since the last one (best effort: no cache, or an unwritable one, parses them all)."""
    import ql_store
    cache = index_dir()
    cache = os.path.join(cache, "flags-" + hashlib.sha1(str(store).encode()).hexdigest()[:12] + ".json") if cache else None
    known = {}
    try:
        with open(cache, encoding="utf-8") as f:
            known = json.load(f)
    except (OSError, TypeError, ValueError):
        pass
    if not isinstance(known, dict):
        known = {}
    kept, seen, reps = {}, set(), []
    for month, name, mtime, size in files:
        key = month + "/" + name
        got = known.get(key)
        if not (isinstance(got, list) and len(got) == 3 and got[0] == mtime and got[1] == size):
            entries = []
            try:
                objs = ql_store.load_run(os.path.join(store, month, name))[1:]
            except (OSError, ValueError):
                objs = []
            for _, e in objs:
                if isinstance(e.get("id"), str):
                    lines = [[path, int(n), x["issue"], e.get("day") or ""]
                             for rep in e.get("feedback") or [] for x in rep.get("lines") or []
                             for path, _, n in [str(x.get("line", "")).rpartition(":")]
                             if x.get("issue") in FLAG_ISSUES and path and n.isdigit()]
                    entries.append([e["id"], lines])
            got = [mtime, size, entries]
        kept[key] = got
        for eid, lines in got[2]:
            if eid not in seen:
                seen.add(eid)
                reps += [tuple(x) for x in lines]
    if cache and kept != known:
        tmp = None
        try:
            os.makedirs(os.path.dirname(cache), exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix=".flags-", suffix=".tmp", dir=os.path.dirname(cache))
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                json.dump(kept, f)
            os.replace(tmp, cache)
            tmp = None
        except OSError:
            pass
        finally:
            if tmp:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
    return reps


def feedback_flags():
    """{qualified path: {line: {issue: [reports, first day]}}} of the lines that a feedback report of the committed
    query-log store (ql_base.STORE, read at the call) names with an issue of FLAG_ISSUES: the entries' `feedback`
    lines, each report counted once per line it names. A report is dropped when its line no longer holds the text it
    held at the start of the report's day (line_holds), also after an edit of that day or an uncommitted one, and
    kept after an edit that left the line alone. A report still in a spool is in no run file and shows nowhere.
    Read again when a run file's time or size, or a flagged article's, changes; {} for a store with none."""
    import ql_base
    store = ql_base.STORE
    if not os.path.isdir(store):
        return {}
    import ql_store
    files = ql_store.run_stats(store)
    if _FLAGS[0] != files:
        _FLAGS[:] = [files, _flag_reports(store, files)]
    out = {}
    for path, n, issue, day in _FLAGS[1]:
        if not line_holds(path, n, day):
            continue
        hit = out.setdefault(path, {}).setdefault(n, {}).setdefault(issue, [0, ""])
        hit[0] += 1
        hit[1] = min(hit[1], day) if hit[1] else day
    return out


def line_holds(path, n, day):
    """Whether line `n` of the kb file `path` (qualified) still holds the text it held when the report of `day` was
    made, so the report still names its fact. The reference is the file as of the start of `day` (its last commit
    on an earlier day), since a report carries a day and no time; the current text is the working tree's, so an
    uncommitted edit counts. True when the file did not change since an earlier day or git cannot tell; a file with
    no commit before `day` keeps the report when it last changed on or before `day`."""
    changed = git_log_day(path)
    if not day or not changed or changed < day:
        return True
    commits, _ = git_history(path)
    base = next((c for c, d in commits if d < day), None)
    if base is None:
        return changed <= day
    full = kbcommon.path_of(path)
    if (path, base) not in _BASED:
        out = _git_out(os.path.dirname(full), "show", f"{base}:./{os.path.basename(full)}", strip=False)
        _BASED[(path, base)] = None if out is None else out.split("\n")
    then = _BASED[(path, base)]
    try:
        with open(full, encoding="utf-8", errors="replace", newline="") as f:
            now = f.read().replace("\r\n", "\n").split("\n")
    except OSError:
        return True
    if then is None or n > len(then):
        return True
    return n <= len(now) and then[n - 1].strip() == now[n - 1].strip()


def flag_line(path, n, issues):
    """`- flagged (feedback, not a fact): PATH:LINE wrong x2, stale x1 since DAY` for one line's issues."""
    since = min((d for _, d in issues.values() if d), default="")
    said = ", ".join(f"{i} x{issues[i][0]}" for i in FLAG_ISSUES if i in issues)
    return f"- {FLAG_LABEL} {path}:{n} {said}" + (f" since {since}" if since else "")


def flags_in(path, lines):
    """The flag lines of `lines` (numbers) of the qualified article `path`, in line order."""
    by = feedback_flags().get(path)
    return [flag_line(path, n, by[n]) for n in sorted(set(lines) & set(by))] if by else []


def show_logs(qpath, first, last):
    """LOG lines for lines `first`..`last` of the kb file `qpath` (`rag.py show`, `kb_show`), as logs_for() ties them
    to the article and the facts that start in that range, then at most MAX_FLAGS flag lines of the lines shown
    (flags_in); [] when none, or the file is no article or data file."""
    if not qpath.endswith((".md", ".csv")):
        return []
    flags = flags_in(qpath, range(first, last + 1))[:MAX_FLAGS]
    if not _active_logs():
        return flags
    text = read(qpath)
    if text is None:
        return flags
    us = md_units(qpath, text) if qpath.endswith(".md") else csv_units(qpath, text)
    return [log_line(r) for r in logs_for({qpath}, [u for u in us if first <= u["line"] <= last])[:MAX_LOGS]] + flags


def audit_logs(rows):
    """LOG lines for the articles of audit() `rows`: the active rows whose `article:` is one of them or whose
    `domain:` holds one, newest first, at most MAX_AUDIT_LOGS."""
    arts = {r["path"] for r in rows}
    return [log_line(r) for r in logs_for(arts, [])[:MAX_AUDIT_LOGS]] if arts else []


# ---------------------------------------------------------------- pack (fact-level retrieval)

STOP =kbid.STOP | {"about", "after", "all", "any", "also", "been", "but", "did", "has", "have", "into", "kb", "much",
                    "long", "more", "not", "only", "same", "than", "that", "their", "then", "there", "these", "they",
                    "this", "those", "was", "were", "will", "would", "you", "your", "who", "whom", "whose", "why",
                    "there", "does", "doing", "get", "set", "use", "used", "using", "via", "per", "say", "says",
                    # words of the request, not of the topic: "answer with citations" must not cost a `good` verdict
                    "answer", "answers", "cite", "citation", "citations", "please", "explain", "tell", "give",
                    "describe", "briefly", "safely", "help", "need", "want", "know"}
WORD = re.compile(r"\w+(?:[.\-]\w+)*")
# the none rule as the pack prints it (the route lines follow it)
NONE_SENTENCE = ("The kb does not cover this. Do not answer from the hits below; state what the kb has and lacks "
                 "(the lines below), research the rest in the live docs, never from memory.")


VPREFIX = re.compile(r"^v(?=\d+\.\d)")  # the v of a version: v2.1.294 and 2.1.294 are one word


@functools.lru_cache(maxsize=None)
def stem(w):
    """A light suffix stripper, the same for query and kb: disable/disabled/disabling -> disabl, settings -> set; a
    version without its v prefix (v2.1.294 -> 2.1.294), so a question and a fact spell it either way."""
    w = VPREFIX.sub("", w)
    for _ in range(2):  # settings -> setting -> sett
        for suf in ("ies", "ing", "ed", "es", "s"):
            if len(w) > len(suf) + 3 and w.endswith(suf) and not (suf == "s" and w.endswith(("ss", "us", "is"))):
                w = w[: -len(suf)] + ("y" if suf == "ies" else "")
                break
        else:
            break
    if len(w) > 4 and w.endswith("e"):
        w = w[:-1]
    if len(w) > 3 and w[-1] == w[-2] and w[-1].isalpha() and w[-1] not in "aeiouls":  # a number keeps its digits
        w = w[:-1]
    return w


def key_terms(text):
    """Stems of whole words only (no hyphen/dot parts): what the coverage verdict counts."""
    return [stem(t) for t in WORD.findall(text.lower()) if t not in STOP and len(t) > 1]


CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")
NUMBER = re.compile(r"\d+(?:\.\d+)+")  # a decimal or dotted number: its dot parts alone do not match it
# a version a model id spells with a hyphen, read only after a model family: claude-opus-5-5 is 5.5, claude-3-5-sonnet
# is 3.5; the S-1-5-18 of a SID or the 8-4-4-4-12 of a GUID is no version
VERSION_ID = re.compile(r"(?<![a-z0-9])(?:opus|sonnet|haiku|fable|claude)-(\d)-(\d)(?![\d.])")


def terms(text, camel=True):
    """Stems of the words, plus the parts of compounds: hyphen/dot parts (what-if -> what, if), a number joined to a
    unit by a hyphen as the number itself (1.5-second -> 1.5, so a question's `1.5 seconds` finds it) and identifier
    parts (approximateLastSignInDateTime -> approximate, last, sign, in, date, time; US_NPI -> us, npi)."""
    out = []
    for w in WORD.findall(text):
        t = VPREFIX.sub("", w.lower())
        parts = [t] + ([p for p in re.split(r"[.\-]", t) if p] if ("-" in t or "." in t) else [])
        if "-" in t:
            parts += [p for p in t.split("-") if NUMBER.fullmatch(p)]
            parts += [f"{m[1]}.{m[2]}" for m in VERSION_ID.finditer(t)]
        if camel and ("_" in w or re.search(r"[a-z][A-Z]", w)):
            parts += [p.lower() for seg in re.split(r"[_.\-]", w) for p in CAMEL.findall(seg)]
        out += [stem(p) for p in dict.fromkeys(parts) if p not in STOP and len(p) > 1]
    return out


ALIASES = os.path.join(TOOLS, "aliases.csv")  # product names, shared by every root


def data_files(rel):
    """The absolute paths of retrieval data file `rel` (under DATA_DIR) in each root that has it, root by root."""
    return [p for p in (os.path.join(r.path, kbcommon.DATA_DIR, rel) for r in kbcommon.roots()) if os.path.exists(p)]


def data_rows(rel):
    """[(Root, row)] of retrieval data CSV `rel` in every root that has it, root by root."""
    out = []
    for r in kbcommon.roots():
        try:
            with open(os.path.join(r.path, kbcommon.DATA_DIR, rel), encoding="utf-8", newline="") as f:
                out += [(r, row) for row in csv.DictReader(f)]
        except OSError:
            pass
    return out


def alias_files(rules=False):
    """The shared product aliases (_tools/aliases.csv), then each root's own aliases.csv (under DATA_DIR); with
    `rules` (the `_self` root), kb/_self's own too."""
    return [ALIASES] + data_files("aliases.csv") + ([SELF_ALIASES] if rules else [])
ALIAS_WEIGHT = 0.5  # an alias the question did not use counts half as much as a word it did
TITLE_WEIGHT = 2    # the article title counts twice in each of its units
SUMMARY_WEIGHT = 0.1  # the article's Summary text is indexed into each of its units at this weight
PART_WEIGHT = 0.2  # a part of a compound identifier the question used (US_NPI -> npi): helps, never dominates
EXPANSION_WEIGHT = 1.0  # words of the generated questions a fact answers (doc2query, kb/public/_retrieval/doc2query/)
UNTAGGED_WEIGHT = 0.8  # an untagged row or line (reference data, Summary, Examples) ranks below a tagged fact


def aliases(rules=False):
    """{canonical: [alias word tuples]} from alias_files(rules) (`term,canonical`, one row per alias)."""
    return cached(("aliases", rules), lambda: _aliases(rules))


def _aliases(rules):
    out = defaultdict(list)
    for path in alias_files(rules):
        try:
            with open(path, encoding="utf-8", newline="") as f:
                for r in csv.DictReader(f):
                    words = tuple(WORD.findall((r.get("term") or "").lower()))
                    canon = (r.get("canonical") or "").strip().lower()
                    if words and canon and words not in out[canon]:
                        out[canon].append(words)
        except OSError:
            pass
    return dict(out)


def expand(question, rules=False):
    """Product aliases in a question (with `rules`, the `_self` aliases too): ({stem: weight} to add to the ranking, {key stem: [variant stem tuples]}).
    A key word that belongs to an alias found in the question also counts as present where any other alias of that
    product is, its canonical name too (all words of a multi-word alias). Expansions never become key words of their
    own, so they cannot raise the coverage verdict on words the question did not use. A word the question holds
    only as a part of a compound (`test` of `test-suite`) is returned too; the ranking's own weight for that part
    replaces its entry."""
    toks = WORD.findall(question.lower())
    extra, variants = {}, defaultdict(set)
    for canon, forms in aliases(rules).items():
        found = [(i, len(f)) for f in forms for i in range(len(toks) - len(f) + 1) if tuple(toks[i:i + len(f)]) == f]
        if not found:
            continue
        name = tuple(WORD.findall(canon))
        stems = [tuple(stem(w) for w in f if w not in STOP) for f in dict.fromkeys([*forms, name])]
        stems = [s for s in stems if s]
        for i, n in found:
            for w in toks[i:i + n]:
                if w not in STOP and len(w) > 1:
                    variants[stem(w)].update(stems)
        for s in stems:
            for t in s:
                extra[t] = ALIAS_WEIGHT / len(s)
    q = set(key_terms(question))  # words the question used as words: a part of its compound still gets its entry
    return {t: w for t, w in extra.items() if t not in q}, {k: sorted(v) for k, v in variants.items()}


def corpus(domain=None):
    """Fact units plus each article's title and Summary bullets as searchable units (cached until a kb file changes)."""
    return cached(("corpus", domain or ""), lambda: _corpus(domain))


def summary_text(rel):
    """The text of an article's `## Summary` section, or ''."""
    m = re.search(r"(?ms)^## Summary[^\n]*\n(.*?)(?=^#{1,2} |\Z)", read(rel) or "")
    return m.group(1) if m else ""


def expansions():
    """{fact key: [generated questions]} from each root's doc2query/expansions.csv (under DATA_DIR); {} when none
    exists or KB_DOC2QUERY=0."""
    if os.environ.get("KB_DOC2QUERY") == "0":
        return {}
    out = defaultdict(list)
    for _, r in data_rows("doc2query/expansions.csv"):
        out[r["key"]].append(r["question"])
    return out


def fact_key(text):
    """The doc2query key of a fact: sha256 of its whitespace-collapsed text, 12 hex digits."""
    return hashlib.sha256(" ".join(text.split()).encode()).hexdigest()[:12]


def index_units():
    """Units of the index files (index_files()): every bullet, table row, paragraph and data row, tagged or not."""
    out = []
    for rel in index_files():
        text = read(rel)
        if text is not None:
            out += md_units(rel, text, untagged=True) if rel.endswith(".md") else csv_units(rel, text)
    for u in out:
        u["root"] = True
    return out


SELF_ROOT = "_self"  # the root name pack and search accept for the kb's own rule docs (not a kb root)
PASSAGE_CHARS = 400  # a rule doc unit longer than this is split into sentence passages of about this size
CLAUSE_CHARS = 80  # the lead a later passage repeats of a unit with no bold lead term: its first clause, this long
PASSAGES_PER_LINE = 2  # a `_self` pack prints at most this many passages of one source line
PARENT_CHARS = 120 # the context of a nested list item: the end of its parent's last sentence, this long
CONTEXT_SEP = " … "  # between a passage's context and the passage
BOUNDARY = re.compile(r"[.;:]\s+(?=[A-Z`]|\*\*)")
RULE_TAG = [{"kind": "DOC", "ids": [], "note": "rule"}]  # a rule passage counts as a fact for the verdict


def self_docs():
    """The top-level .md docs of the kb's own docs (SELF_DIR; no subdirectory), by repository path, sorted."""
    return sorted(kbcommon.repo_rel(os.path.join(SELF_DIR, f)) for f in (os.listdir(SELF_DIR) if os.path.isdir(SELF_DIR) else [])
                  if f.endswith(".md") and os.path.isfile(os.path.join(SELF_DIR, f)))


def sentences(text):
    """`text` cut after `. `, `; ` and `: ` followed by a capital letter, a backtick or `**`, never inside a backtick
    code span, parentheses or brackets."""
    out, start, code, depth = [], 0, False, 0
    for i, c in enumerate(text):
        if c == "`":
            code = not code
        elif code:
            continue
        elif c in "([":
            depth += 1
        elif c in ")]":
            depth = max(depth - 1, 0)
        elif c in ".;:" and not depth:
            m = BOUNDARY.match(text, i)
            if m:
                out.append(text[start:m.end()].strip())
                start = m.end()
    out.append(text[start:].strip())
    return [s for s in out if s]


def cells(row):
    """The cells of a table row `| a | b |`: split at pipes outside backtick code spans and `\\|` escapes."""
    out, cur, code, i = [], "", False, 0
    row = row.strip().removeprefix("|")
    if row.endswith("|") and not row.endswith("\\|"):
        row = row[:-1]
    while i < len(row):
        c = row[i]
        if c == "\\" and row[i + 1:i + 2] == "|":
            cur += "\\|"
            i += 2
            continue
        if c == "`":
            code = not code
        if c == "|" and not code:
            out.append(cur.strip())
            cur = ""
        else:
            cur += c
        i += 1
    return out + [cur.strip()]


def merged(pieces, room):
    """Neighbouring (separator, text) pieces joined while the result stays within `room` characters; a piece longer
    than that stays whole."""
    out = []
    for sep, s in pieces:
        if out and len(out[-1]) + len(sep) + len(s) <= room:
            out[-1] += sep + s
        else:
            out.append(s)
    return out


def list_pieces(s, room):
    """`s` when it fits `room` characters; else cut at its top-level `, ` and `; ` (outside backtick code spans,
    parentheses and brackets), after a `)` or before a backtick when it has such boundaries, and the pieces merged up
    to `room`."""
    if len(s) <= room:
        return [s]
    preferred, plain, code, depth = [], [], False, 0
    for i, c in enumerate(s):
        if c == "`":
            code = not code
        elif code:
            continue
        elif c in "([":
            depth += 1
        elif c in ")]":
            depth = max(depth - 1, 0)
        elif c in ",;" and not depth and s[i + 1:i + 2] == " ":
            plain.append(i + 2)
            if s[i - 1:i] == ")" or s[i + 2:i + 3] == "`":
                preferred.append(i + 2)
    out = [s]
    for marks in (preferred, plain):
        bounds = [0] + marks + [len(s)]
        out = merged([(" ", s[a:b].strip()) for a, b in zip(bounds, bounds[1:]) if s[a:b].strip()], room)
        if max(map(len, out)) <= room:
            break
    return out


def clause(text):
    """`text` up to CLAUSE_CHARS characters, cut at a word boundary and outside a code span, without a trailing
    separator."""
    if len(text) > CLAUSE_CHARS:
        text = text[:CLAUSE_CHARS].rsplit(" ", 1)[0]
        if text.count("`") % 2:
            text = text[:text.rindex("`")] or text + "`"
    return text.rstrip(" ,;:")


def lead_of(text):
    """What a later passage of a unit repeats of its start: the bold lead term, else the first clause (clause)."""
    bold = re.match(r"\*\*[^*]+\*\*", text)
    return bold.group(0) if bold else clause(sentences(text)[0])


def parent_context(lines, n, by_line):
    """For the list item on line n (1-based) of a doc's `lines`: the end of the last sentence of the unit it hangs
    under (the nearest list line above with less indentation, or the paragraph right above its list), clipped to
    PARENT_CHARS characters at a word boundary, when that unit ends in `:`; else ''. `by_line`: unit text by line."""
    raw = lines[n - 1]
    item = re.match(r"(\s*)[-*] ", raw)
    if not item:
        return ""
    j, parent = n - 2, ""
    while j >= 0:
        ln = lines[j]
        if not ln.strip() or ln.startswith("#"):
            break
        above = re.match(r"(\s*)[-*] ", ln)
        if above and len(above.group(1)) < len(item.group(1)):
            parent = by_line.get(j + 1, "")
            break
        if above:
            j -= 1
            continue
        k = j
        while k >= 0 and lines[k].strip() and not lines[k].startswith("#") and not re.match(r"\s*[-*] ", lines[k]):
            k -= 1
        if k >= 0 and re.match(r"\s*[-*] ", lines[k]):
            j = k  # the continuation of a list item: handle that item
            continue
        parent = by_line.get(k + 2, "")
        break
    if not parent.endswith(":"):
        return ""
    last = sentences(parent)[-1]
    if len(last) > PARENT_CHARS:
        last = last[-PARENT_CHARS:].split(" ", 1)[-1]
    return last


def passage_title(text):
    """The natural title of a rule doc unit: the first cell of a table row, else the bold lead term of a bullet, else ''."""
    if text.startswith("|"):
        return cells(text)[0]
    bold = re.match(r"\*\*([^*]+)\*\*", text)
    return bold.group(1) if bold else ""


def passages(u, parent=""):
    """The sentence passages of a rule doc unit, as units of the same line and section: the unit itself when it is at
    most PASSAGE_CHARS long. A sentence too long for a passage is cut at its list separators (list_pieces). A table
    row's passages each start with its first cell and ` | `. Context goes in front of a passage, joined by CONTEXT_SEP
    and part of its text: `parent` (the end of the sentence a nested list item hangs under) on every passage of the
    item, and for each passage after the first the unit's lead (lead_of)."""
    text = u["text"]
    table = text.startswith("|")
    head = ""
    if table:
        first, *rest = cells(text)
        head = clause(first) + " | " if first else ""
    lead = lead_of(text) if not table else ""
    up = parent + CONTEXT_SEP if parent and not table else ""
    if len(text) <= PASSAGE_CHARS:
        return [{**u, "text": up + text}] if up else [u]
    pieces = []
    if table:
        for n, cell in enumerate(rest):
            pieces += [(" | " if n and j == 0 else " ", p) for j, s in enumerate(sentences(cell))
                       for p in list_pieces(s, PASSAGE_CHARS - len(head))]
    else:
        pieces = [(" ", p) for s in sentences(text) for p in list_pieces(s, PASSAGE_CHARS - len(up + lead) - len(CONTEXT_SEP))]
    room = max(PASSAGE_CHARS - len(head or up + lead + CONTEXT_SEP), PASSAGE_CHARS // 4)
    out = []
    for n, s in enumerate(merged(pieces, room)):
        if head:
            s = head + s
        elif n and lead and lead not in s:
            s = up + lead + CONTEXT_SEP + s
        else:
            s = up + s
        out.append({**u, "text": s})
    return out


def self_units(skip=None):
    """The passages of the top-level kb/_self docs (self_docs()), every unit of them: the units the `_self` root
    searches. Each is a rule, so it carries a stand-in tag (RULE_TAG); `root` and `passage` keep them out of every other
    view. `ord` is a passage's place among those of its source line, `whole` the text of that line's unit, `anchors`
    the [(id, question)] of the tested questions it is the anchor of (self_eval_rows, anchor_of), except row `skip`."""
    out = []
    for rel in self_docs():
        text = read(rel)
        units = md_units(rel, text, untagged=True) if text is not None else []
        lines, by_line = (text or "").splitlines(), {u["line"]: u["text"] for u in units}
        for u in units:
            u["lead"] = passage_title(u["text"])
            for n, p in enumerate(passages(u, parent_context(lines, u["line"], by_line))):
                p.update(ord=n, whole=u["text"])
                out.append(p)
    for u in out:
        u.update(root=True, passage=True, tags=RULE_TAG)
    for row in self_eval_rows():
        anchor = anchor_of(row, out) if row["id"] != skip else None
        if anchor:
            anchor.setdefault("anchors", []).append((row["id"], row["question"]))
    return out


def self_eval_rows(path=None):
    """The rows of the `_self` eval file (SELF_EVAL, or `path`), [] when it is missing."""
    try:
        with open(path or SELF_EVAL, encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))
    except OSError:
        return []


def eval_phrases(row):
    """The `;`-separated alternative phrases of an eval row's `expect_text`."""
    return [t.strip() for t in (row.get("expect_text") or "").split(";") if t.strip()]


def anchor_of(row, us):
    """The passage of `us` (self_units) an eval row with `expect_text` anchors: in the first of its `expect_paths`
    docs that holds one of its phrases, the line holding it, and of that line the passage that holds the phrase (the
    one holding its longest start when it spans two). None when no phrase is in any of its docs."""
    for rel in (p.strip() for p in (row.get("expect_paths") or "").split(";") if p.strip()):
        mine = [u for u in us if u["path"] == "kb/_self/" + rel]
        for phrase in eval_phrases(row):
            for u in mine:
                if phrase in u["text"]:
                    return u
                if phrase in u["whole"]:
                    return max((v for v in mine if v["line"] == u["line"]), key=lambda v: phrase_start(phrase, v["text"]))
    return None


def phrase_start(phrase, text):
    """The length of the longest start of `phrase` that `text` holds."""
    n = len(phrase)
    while n and phrase[:n] not in text:
        n -= 1
    return n


def self_store(skip=None):
    """The `_self` view of a store built in memory from the rule passages alone, with tested question `skip` neither
    indexed nor matched: what the rules' ranking gives without that row."""
    return MemStore("", weighed(self_units(skip), articles(), {})).view(SELF_ROOT)


def row_sets(row):
    """The `;`-separated set names (`skill` or `skill:step`) of a `_self` eval row's `sets` cell."""
    return [x.strip() for x in (row.get("sets") or "").split(";") if x.strip()]


def in_set(row, name):
    """Whether eval row `row` is in set `name`: it names it, or, for a bare skill name, any of the skill's steps."""
    return any(x == name or (":" not in name and x.split(":")[0] == name) for x in row_sets(row))


def set_pack(name, info=None):
    """The text of `rag.py pack --root _self --set NAME`: `set NAME: N tested questions`, then for each row of the set
    `# <id>: <question>` and its anchored passage (`path:line § Heading: text`), or a line naming the phrase and docs
    that hold no anchor; then the `## decisions` block with the active decisions tied to the docs or sections of those
    passages, each once. Nothing is ranked and there is no verdict. ValueError naming the known sets when `name` is none.
    A dict `info` is filled with the set's `tested` ids, the `pinned` passages shown and their `docs`."""
    rows = self_eval_rows()
    known = sorted({x for r in rows for s in row_sets(r) for x in (s, s.split(":")[0])})
    if name not in known:
        raise ValueError(f"no set {name!r}; known sets: {', '.join(known) or 'none'}")
    mine = [r for r in rows if in_set(r, name)]
    st = store(SELF_ROOT)
    anchored = {rid: i for rid, _, i in st.anchors}
    out, shown = [f"set {name}: {len(mine)} tested questions"], []
    for r in mine:
        out.append(f"# {r['id']}: {r['question']}")
        if r["id"] not in anchored:
            docs = ", ".join(p.strip() for p in r["expect_paths"].split(";") if p.strip())
            out.append(f"  (no anchor: {(eval_phrases(r) or [''])[0]} not in {docs})")
            continue
        u = st.unit(anchored[r["id"]])
        shown.append(u)
        where = f" § {u['section']}:" if u["section"] else ""
        out.append(f"{u['path']}:{u['line']}{where} {clip(u['text'], PASSAGE_CHARS + PARENT_CHARS + CLAUSE_CHARS)}")
    tied = tied_decisions(self_places(shown), only_active=True)
    if tied:
        out += ["", "## decisions"] + [decision_line(d, True) for d in tied]
    if info is not None:
        info.update(tested=[r["id"] for r in mine], pinned=len(shown), docs=list(dict.fromkeys(u["path"] for u in shown)))
    return "\n".join(out)


def record_self(text, budget, res=None, parts=(), item=None, set_name=None, info=None):
    """Append one query log row for a `_self` lookup (`ql_capture.record`, surface `kb_ask`, the one a tool's own lookup
    has): `root`, the `question` (one part as text, several as a list, each clipped), `verdict` (the worst), `tested`
    (the matched tested-question ids), `pinned` (passages printed for them), `set` or `item`, `budget`, `chars` and
    `lines` of the printed `text`, `parts`, `docs` printed and `key_missing` (key words no printed passage holds).
    `res` is pack_many's result, `info` a set run's (set_pack). Never raises: a lookup never fails for its log."""
    try:
        import ql_capture
        rs = (res or {}).get("results") or []
        uniq = lambda key: list(dict.fromkeys(x for r in rs for x in r[key]))
        ql_capture.record("kb_ask", root=SELF_ROOT, question=(ql_capture.clip(parts[0]) if len(parts) == 1 else ql_capture.clip(list(parts))) if parts else None,
                          verdict=(res or {}).get("verdict"), tested=(info or {}).get("tested") or uniq("tested") or None,
                          pinned=(info or {}).get("pinned", sum(r["pinned"] for r in rs)), set=set_name, item=item, budget=budget,
                          chars=len(text), lines=ql_capture.pack_lines(text), parts=len(parts) or None,
                          docs=(info or {}).get("docs") or uniq("paths") or None, key_missing=uniq("key_missing")[:12] or None)
    except Exception:  # noqa: BLE001 - see the docstring
        pass


def glob_regex(pattern):
    """The regular expression of a path glob: `*` within a directory, `**` across directories."""
    return re.compile("".join(".*" if p == "**" else "[^/]*" if p == "*" else re.escape(p) for p in re.split(r"(\*\*|\*)", pattern)))


def globs_meet(a, b):
    """Whether path globs `a` and `b` are equal or one matches the other as a literal path."""
    return a == b or bool(glob_regex(a).fullmatch(b) or glob_regex(b).fullmatch(a))


def item_brief(item_id):
    """{id, question, docs} of backlog item `item_id` (kb/_self/backlog/<id>.json), None when there is no such item:
    the question is its title and goal, the docs the top-level kb/_self docs that kb/_self/map.csv maps to one of its
    `touches` (self_docs() when none does)."""
    if not kbcommon.CONTEXT_KINDS["item"].fullmatch(item_id):
        return None
    try:
        with open(os.path.join(SELF_DIR, "backlog", f"{item_id}.json"), encoding="utf-8") as f:
            item = json.load(f)
        with open(os.path.join(SELF_DIR, "map.csv"), encoding="utf-8-sig", newline="") as f:
            mapped = list(csv.DictReader(f))
    except (OSError, ValueError):
        return None
    touches, docs = item.get("touches") or [], self_docs()
    hit = sorted({r["doc"] for r in mapped if r.get("doc") in docs and any(globs_meet(r.get("pattern") or "", t) for t in touches)})
    return {"id": item_id, "question": f"{item.get('title', '')}. {item.get('goal', '')}".strip(), "docs": hit or docs}


def _corpus(domain):
    us = units(domain, untagged=True)  # untagged rows and lines too: a word the kb has is never "not in the kb"
    if not domain:
        us += index_units()  # last, so the pack's view is a prefix of the corpus
        us += self_units()  # after those: the index view is a prefix too
    return weighed(us, articles(), expansions())


# ---------------------------------------------------------------- where the index lives

def clone_home():
    """The checkout whose _cache/ holds the index: this repository, or the clone's main worktree when this
    repository is a linked git worktree (its `.git` is a file naming `<common dir>/worktrees/<name>`), so the
    worktrees of one clone share one index directory (ql_base.clone_home reads the spool's place the same way). A
    relative `gitdir:` (git worktree add --relative-paths) is relative to the worktree, not the working directory."""
    try:
        with open(os.path.join(kbcommon.HOME, ".git"), encoding="utf-8") as f:
            text = f.read().strip()
    except OSError:
        return kbcommon.HOME
    if text.startswith("gitdir:"):
        gitdir = os.path.normpath(os.path.join(kbcommon.HOME, text[len("gitdir:"):].strip()))
        parent = os.path.dirname(gitdir)
        if os.path.basename(parent) == "worktrees" and os.path.basename(os.path.dirname(parent)) == ".git":
            return os.path.dirname(os.path.dirname(parent))
    return kbcommon.HOME


def index_dir():
    """The index directory, or None when KB_INDEX=0: KB_INDEX (a directory), else the plugin's data directory
    (CLAUDE_PLUGIN_DATA, survives plugin updates), else _cache/ of the clone (its main worktree's, shared by its
    linked worktrees: clone_home), else a temp directory."""
    where = os.environ.get("KB_INDEX", "")
    if where == "0":
        return None
    if not where:
        home = clone_home()
        where = os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.join(home, "_cache")
        if not _writable(where):
            where = os.path.join(tempfile.gettempdir(), "it-ops-kb-" + hashlib.sha1(home.encode()).hexdigest()[:8])
    return where


def _writable(d):
    if os.path.isdir(d):
        return os.access(d, os.W_OK)
    return os.access(os.path.dirname(d) or ".", os.W_OK)


# ---------------------------------------------------------------- clipping

def clip(text, n):
    """Cut a fact at about n characters, keeping its tags visible: `start ... [DOC S1]`."""
    if len(text) <= n:
        return text
    head = text[:n].rsplit(" ", 1)[0]
    tags = [m.group(0) for m in TAG.finditer(text) if m.end() > len(head)]  # tags cut off, straddling ones included
    return head + " ..." + ("" if TAG.search(head) or not tags else " " + " ".join(tags))


def clip_around(text, n, phrases=(), terms=()):
    """`clip(text, n)`, except that a text longer than n whose `phrases` (the first one it holds) or else most `terms`
    (stems of the question's key words) lie beyond the clip prints as the window of n characters around them, with
    `...` at each cut end: the passage a tested question is pinned on answers by the printed line, not by the part
    cut off. The clip itself when its head holds as many of them."""
    if len(text) <= n:
        return text
    head = clip(text, n)
    found = next(((i, i + len(p)) for p in phrases for i in [text.find(p)] if i >= 0), None)
    if found:
        if found[1] <= len(head.split(" ...")[0]):
            return head
        start = max(0, found[0] - max(0, n - (found[1] - found[0])) // 3)
    else:
        hits = [(m.start(), stem(m.group(0).lower())) for m in WORD.finditer(text)]
        hits = [(i, t) for i, t in hits if t in terms]

        def held(a):
            return len({t for i, t in hits if a <= i < a + n - 20})
        if not hits:
            return head
        start = max(hits, key=lambda h: (held(h[0]), -h[0]))[0]
        if held(start) <= held(0):
            return head
        inside = sorted(i for i, t in hits if start <= i < start + n - 20)
        start = max(0, inside[len(inside) // 2] - n // 2)  # the window centred on the words it holds
    end = min(len(text), start + n)
    start = max(0, end - n)
    if start:
        start = text.find(" ", start) + 1 or start
    if end < len(text):
        end = text.rfind(" ", start, end) if " " in text[start:end] else end
    window = text[start:end]
    tags = [m.group(0) for m in TAG.finditer(text) if m.end() > end]  # tags cut off, straddling ones included
    return ("... " if start else "") + window + (" ..." + ("" if TAG.search(window) or not tags else " " + " ".join(tags))
                                                if end < len(text) else "")


# ---------------------------------------------------------------- the modules behind this facade

# Each imports the ground above by name and the stages it builds on; they are imported here, last, so every name
# they define is also a name of this module (what other modules and the ground itself read as `kbfacts.NAME`).
from kf_fresh import (
    CONFIRMED, FACT_LINE, FOOTER_LINE, LIVE_WORD, MAX_QUESTIONS, OFFLINE_MARK, PACK_HANDLE, PACK_HANDLE_DAYS,
    PACK_HANDLE_KEEP, PART_BUDGET_MIN, cited_ids, cited_lines, format_sources, fresh_mark, fresh_state, handled,
    kb_commit, keep_pack, ledger_rows, pack_handle, pack_many, pack_store, printed_lines, provider_signals,
    revalidate_pack, revalidated, root_freshness, source_freshness, source_signal, source_stamp
)  # noqa: E402, F401
from kf_index import (
    AMOUNT, COMMON_SHARE, IDENT, INDEX_VERSION, KEEP_INDEXES, LANGUAGE_NAMES, LATEST, LIST_INTRO_CHARS, MemStore,
    PASSING_MISSING, PASSING_UNITS, PRICE_ASK, PRUNE_GRACE, PRUNE_OTHER_ROOTS, Prefix, RARE_NAME, SCATTER_ARTICLES,
    SCATTER_DOMAINS, SCATTER_SCORE, SEARCH_PER_FILE, SqlStore, Store, Subset, TESTED_FURTHER, TESTED_PINS,
    TESTED_SHARE, TOPIC_SHARE, UNIT_CACHE, UNIT_CACHE_SLACK, USED_EVERY, VERSION, article_domain, drifted_words,
    freshness, index_path, informative_words, key_shares, list_intro, name_apart, opening_passage, own_words, pack,
    pick_passages, prune_indexes, rank, route_of, search, snippet_code, specific, store, tested_matches, weighed
)  # noqa: E402, F401
from kf_route import (
    CITE_CUE, CONFLICT_CUE, COUNT_CUE, COUNT_STEMS, DECISION_REF, ENTRY_CHARS, EXPERTS, GAP_CUE, GAP_TITLE_SHARE,
    GENERATED_ATTRS, KIND_PHRASE, LEDGER_STEMS, LIST_CUE, MAX_AST_BYTES, MAX_FILES, MAX_FILE_BYTES,
    MSBUILD_SUFFIXES, OPEN_GAP, PACKAGE_JSON_SECTIONS, PS_HASHTABLE, PS_MODULES_SWITCH, PS_MODULE_NAME, PS_NAME,
    PS_NEXT_SWITCH, PS_QUOTED, PS_REQUIRED_MODULES, PS_REQUIRES, PS_SUFFIXES, PY_SUFFIXES, ROUTED_ITEMS,
    ROUTED_PATHS, RRF_K, SCOPE_CUE, SKIP_CODE_DIRS, STATUS_CUE, TOPIC_MIN, _gap_items, code_files,
    format_topics_for, import_reader, imports_of, kinds_of_question, marked_files, pack_routed, routed, rrf,
    signal_regex, signals, topics_for
)  # noqa: E402, F401
