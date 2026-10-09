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
id (`[CODE _tools/kbfacts.py#pack]`; a test checks the file and the symbol exist).
A `;` or `,` directly followed by a KIND starts the next part, so `[DOC S1208, COMMUNITY S1209]` has two parts and
`[DER S328,S329: different property; Type has no table]` has one. Canonical form: `[DOC S1, S2]`, `[DER S1: how]`,
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

The pack index. `store()` holds the pack corpus as postings lists (per term: the units that hold it). A process
that finds an index file for the current fingerprint (a key of the content of every file the tools read, the same in
every checkout of that content: `fingerprint()`) reads only the postings of the question's words from it (stdlib
sqlite3); otherwise it builds the corpus, answers from memory and saves the index for the next process. Output is
identical either way: scores are summed in the same term order per unit and ties keep corpus order. Where the file
goes: `index_path()`, in a directory a clone's worktrees share (`index_dir()`); which old files go: `prune_indexes()`.
The same index serves `search()` (rag.py search, kb_search): the corpus also holds untagged prose paragraphs, and at
its end the index files (README.md, each root's ledgers, the kb's own docs in kb/_self/), which only a search with
`index` sees.
"""
import array, ast, bisect, csv, functools, hashlib, io, json, marshal, math, os, re, sqlite3, subprocess, sys, tempfile, threading, time, warnings
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from fractions import Fraction

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
_PART_SPLIT = re.compile(rf"\s*[;,]\s*(?=(?:{_K})\b)")
_PART = re.compile(rf"({_K})(?:/({_K}))?\b\s*(?:from\s+)?"
                   rf"((?:{kbid.ID_PATTERN})(?:[\s,]+(?:{kbid.ID_PATTERN})\b)*)?(.*)", re.S)  # every root's id prefix
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
        if not m:  # a `;` inside a note: belongs to the previous part
            if parts:
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
    the ledgers, aliases.csv, signals.csv, doc2query/expansions.csv, the `_self` eval and aliases files, this module
    and kbid.py. The domain files come with their directory entry (kb_entries): on Windows its stat() needs no call."""
    extra = [*root_files((kbcommon.SOURCES,)), *index_files(), *alias_files(), *data_files("signals.csv"),
             *data_files("doc2query/expansions.csv"), kbcommon.repo_rel(SELF_EVAL), kbcommon.repo_rel(SELF_ALIASES),
             os.path.join(TOOLS, "kbfacts.py"), os.path.join(TOOLS, "kbid.py")]
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


def _git(*args):
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
    staged, changed = _git("ls-files", "-s", "-v", "-z"), _git("ls-files", "-z", "-m", "-o", "--exclude-standard")
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
            _remove(tmp)
    now = time.time()
    for name in names:
        full = os.path.join(d, name)
        try:
            if name.startswith("kbkey-") and full != memo and now - os.stat(full).st_mtime > MEMO_DAYS * 86400:
                os.remove(full)
        except OSError:
            pass
    return key


def _remove(path):
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
    counts by kind (a fact counts once per kind it carries) and the gap/conflict entries linked to it."""
    prefix = scope(prefix, root)
    tfiles = topic_files()
    srcs = source_rows()
    ledgers = {n: link_entries(ledger_entries(n), tfiles, srcs) for n in (kbcommon.GAPS, kbcommon.CONFLICTS)}
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
               **{k: counts.get(k, 0) for k in EVIDENCE_KINDS}}
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


def show_logs(qpath, first, last):
    """LOG lines for lines `first`..`last` of the kb file `qpath` (`rag.py show`, `kb_show`), as logs_for() ties them
    to the article and the facts that start in that range; [] when none, or the file is no article or data file."""
    if not _active_logs() or not qpath.endswith((".md", ".csv")):
        return []
    text = read(qpath)
    if text is None:
        return []
    us = md_units(qpath, text) if qpath.endswith(".md") else csv_units(qpath, text)
    return [log_line(r) for r in logs_for({qpath}, [u for u in us if first <= u["line"] <= last])[:MAX_LOGS]]


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


@functools.lru_cache(maxsize=None)
def stem(w):
    """A light suffix stripper, the same for query and kb: disable/disabled/disabling -> disabl, settings -> set."""
    for _ in range(2):  # settings -> setting -> sett
        for suf in ("ies", "ing", "ed", "es", "s"):
            if len(w) > len(suf) + 3 and w.endswith(suf) and not (suf == "s" and w.endswith(("ss", "us", "is"))):
                w = w[: -len(suf)] + ("y" if suf == "ies" else "")
                break
        else:
            break
    if len(w) > 4 and w.endswith("e"):
        w = w[:-1]
    if len(w) > 3 and w[-1] == w[-2] and w[-1] not in "aeiouls":
        w = w[:-1]
    return w


def key_terms(text):
    """Stems of whole words only (no hyphen/dot parts): what the coverage verdict counts."""
    return [stem(t) for t in WORD.findall(text.lower()) if t not in STOP and len(t) > 1]


CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")
NUMBER = re.compile(r"\d+(?:\.\d+)+")  # a decimal or dotted number: its dot parts alone do not match it


def terms(text, camel=True):
    """Stems of the words, plus the parts of compounds: hyphen/dot parts (what-if -> what, if), a number joined to a
    unit by a hyphen as the number itself (1.5-second -> 1.5, so a question's `1.5 seconds` finds it) and identifier
    parts (approximateLastSignInDateTime -> approximate, last, sign, in, date, time; US_NPI -> us, npi)."""
    out = []
    for w in WORD.findall(text):
        t = w.lower()
        parts = [t] + ([p for p in re.split(r"[.\-]", t) if p] if ("-" in t or "." in t) else [])
        if "-" in t:
            parts += [p for p in t.split("-") if NUMBER.fullmatch(p)]
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
    product is (all words of a multi-word alias). Expansions never become key words of their own, so they cannot
    raise the coverage verdict on words the question did not use."""
    toks = WORD.findall(question.lower())
    extra, variants = {}, defaultdict(set)
    for canon, forms in aliases(rules).items():
        found = [(i, len(f)) for f in forms for i in range(len(toks) - len(f) + 1) if tuple(toks[i:i + len(f)]) == f]
        if not found:
            continue
        stems = [tuple(stem(w) for w in f if w not in STOP) for f in forms]
        stems = [s for s in stems if s]
        for i, n in found:
            for w in toks[i:i + n]:
                if w not in STOP and len(w) > 1:
                    variants[stem(w)].update(stems)
        for s in stems:
            for t in s:
                extra[t] = ALIAS_WEIGHT / len(s)
    q = set(terms(question))
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
    return sorted(kbcommon.repo_rel(os.path.join(SELF_DIR, f)) for f in os.listdir(SELF_DIR)
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


UNIT_CACHE = "kbunits.sqlite"  # in index_dir(), one per root set: weighed()'s result per unit, keyed by everything it reads
UNIT_CACHE_SLACK = 2  # the cache keeps up to this many times the units weighed; beyond, rows no unit used are dropped


def _code_digest(code):
    """A hash of a code object's instructions, names and constants, nested code included, with no line numbers: a
    comment or a moved function keeps it, an edited statement changes it."""
    consts = [_code_digest(c) if hasattr(c, "co_code") else repr(c) for c in code.co_consts]
    return hashlib.sha1(repr((code.co_code, code.co_names, code.co_varnames, consts)).encode()).hexdigest()


@functools.lru_cache(maxsize=1)
def _weigh_code():
    """The digest of the functions that weigh a unit: _weigh, terms, stem (without its cache wrapper) and bare."""
    return [_code_digest(f.__code__) for f in (_weigh, terms, getattr(stem, "__wrapped__", stem), bare)]


@functools.lru_cache(maxsize=4)
def _weigh_data(stop, kbid_stop, patterns):
    """The digest of the sets and patterns the weighing functions read as globals (see _unit_key)."""
    return hashlib.sha1(repr((sorted(stop), sorted(kbid_stop), patterns)).encode()).hexdigest()


def _unit_key(u, art, meta, sums, exps):
    """The cache key of unit `u`'s weighing: a hash of INDEX_VERSION, the doc2query mode, the weighing code (the
    weights, the STOP sets and the word patterns that terms() reads, and the code of _weigh, terms, stem and bare)
    and every input weighed() reads for the unit (path, title or lead, section, text, its article's Summary, its
    expansions, its tested questions), so an unchanged unit keeps its key across an edit elsewhere or a change to
    this file outside the weighing, while an edit to the weighing re-weighs every unit without an INDEX_VERSION bump."""
    if meta and not u["section"].startswith("Summary"):
        if art not in sums:
            sums[art] = hashlib.sha1(summary_text(art).encode()).hexdigest()
        summ = sums[art]
    else:
        summ = None
    ex = exps.get(fact_key(u["text"]), ()) if exps and u["tags"] and not u.get("root") else ()
    wdata = _weigh_data(frozenset(STOP), frozenset(kbid.STOP), (WORD.pattern, CAMEL.pattern, NUMBER.pattern))
    raw = json.dumps([INDEX_VERSION, os.environ.get("KB_DOC2QUERY", ""), _weigh_code(), wdata,
                      TITLE_WEIGHT, SUMMARY_WEIGHT, EXPANSION_WEIGHT, u["path"], u["title"], u.get("lead", ""),
                      u["section"], u["text"], summ, list(ex), [q for _, q in u.get("anchors", ())]], ensure_ascii=False)
    return hashlib.sha1(raw.encode()).digest()


def _unit_cache_name():
    """The unit cache file name of this root set, named as the index files are (_root_key): `kbunits.sqlite` for this
    repository's roots alone, else `kbunits-r<hash>.sqlite`."""
    key = _root_key()
    return UNIT_CACHE.replace(".sqlite", f"-{key[:-1]}.sqlite") if key else UNIT_CACHE


def _unit_cache_open():
    """A connection to the unit cache of this root set in index_dir() with its table, or None (KB_INDEX=0, or it
    cannot be opened). One file per root set (_unit_cache_name), so a build over fewer roots never prunes the rows
    of the full corpus. Opening marks the file used (its mtime), which prune_indexes() reads for a root set no
    process has used for PRUNE_OTHER_ROOTS."""
    d = index_dir()
    if not d:
        return None
    path = os.path.join(d, _unit_cache_name())
    try:
        os.makedirs(d, exist_ok=True)
        con = sqlite3.connect(path, timeout=10)
        con.execute("CREATE TABLE IF NOT EXISTS u(k BLOB PRIMARY KEY, v BLOB) WITHOUT ROWID")
    except (OSError, sqlite3.Error):
        return None
    try:
        os.utime(path)
    except OSError:
        pass
    return con


def _unit_cache_save(con, new, keys):
    """Add the `new` {key: value} rows; when the cache holds more than UNIT_CACHE_SLACK times `keys` (the keys of this
    weighing), drop every row not in `keys` and give the freed pages back with VACUUM, since a DELETE leaves the file
    its size (kb/public/python/stdlib-sqlite3-csv.md:104). The prune runs only after the rows have doubled, so the
    VACUUM's rewrite of the file is rare. It runs after the `with con` block has committed: the module's default
    connection keeps a transaction open after the DELETE until then and a VACUUM inside one is refused
    (kb/public/python/stdlib-sqlite3-csv.md:118). Best effort: another process may hold the file."""
    pruned = False
    try:
        with con:
            con.executemany("INSERT OR IGNORE INTO u VALUES (?, ?)", sorted(new.items()))
            if con.execute("SELECT count(*) FROM u").fetchone()[0] > UNIT_CACHE_SLACK * max(len(keys), 1):
                con.execute("CREATE TEMP TABLE keep(k BLOB PRIMARY KEY) WITHOUT ROWID")
                con.executemany("INSERT OR IGNORE INTO keep VALUES (?)", ((k,) for k in sorted(keys)))
                pruned = con.execute("DELETE FROM u WHERE k NOT IN (SELECT k FROM keep)").rowcount > 0
                con.execute("DROP TABLE keep")
        if pruned:
            con.execute("VACUUM")
    except sqlite3.Error:
        pass


def weighed(us, metas, exps):
    """`us` with each unit's `title`, `len`, `own` (the words it holds) and `tf` (its weighted words: title, Summary,
    doc2query expansions of a fact `exps` holds, tested questions of a passage). A unit whose inputs are unchanged
    since an earlier weighing reads its result from the unit cache (UNIT_CACHE) instead of splitting its words again,
    so an edit to one article re-weighs only that article's units."""
    con = _unit_cache_open()
    try:
        memo = dict(con.execute("SELECT k, v FROM u")) if con else {}
    except sqlite3.Error:
        memo = {}
    summaries, sums, new, keys = {}, {}, {}, []
    for u in us:
        art = u["path"] if u["path"] in metas else u["path"][:-4] + ".md"
        meta = metas.get(art) or {}
        u["title"] = meta.get("title", "")
        if con:
            key = _unit_key(u, art, meta, sums, exps)
            keys.append(key)
            hit = memo.get(key)
            if hit is not None:
                u["len"], own, tf = marshal.loads(hit)
                u["own"], u["tf"] = frozenset(own), Counter(tf)
                continue
        _weigh(u, art, meta, summaries, exps)
        if con:
            new[key] = marshal.dumps((u["len"], tuple(sorted(u["own"])), dict(u["tf"])))
    if con:
        if new or len(memo) > UNIT_CACHE_SLACK * max(len(keys), 1):
            _unit_cache_save(con, new, keys)
        con.close()
    return us


def _weigh(u, art, meta, summaries, exps):
    """Set unit `u`'s `len`, `own` and `tf` (weighed()'s work for one unit; `summaries` caches each article's)."""
    tf = Counter(terms(f"{bare(u['path'])} {u['title']} {u['section']} {u['text']}"))  # a root name is no word
    # own: words the unit itself has (verdict, df). Directory names rank but are not own words: every unit of a
    # domain holds its name, so a growing domain (agents/) would push that word past the 20% common-word cut.
    own = terms(f"{os.path.basename(bare(u['path']))} {u['title']} {u['section']} {u['text']}")
    u["len"], u["own"] = sum(tf.values()), frozenset(own)
    for t in terms(u["title"] or u.get("lead", "")):
        tf[t] += TITLE_WEIGHT - 1
    if meta and not u["section"].startswith("Summary"):
        if art not in summaries:
            summaries[art] = Counter(terms(summary_text(art)))
        for t, c in summaries[art].items():
            tf[t] += SUMMARY_WEIGHT * c
    for q in exps.get(fact_key(u["text"]), ()) if exps and u["tags"] and not u.get("root") else ():
        for t in terms(q):
            tf[t] += EXPANSION_WEIGHT  # ranks the fact for other wordings; never a verdict word (not in own)
    for _, q in u.get("anchors", ()):
        for t in terms(q):
            tf[t] += EXPANSION_WEIGHT  # a tested question: ranks its passage for other wordings; never a verdict word
    u["tf"] = tf


# ---------------------------------------------------------------- the pack index (postings; persisted with sqlite3)

INDEX_VERSION = 8 # bump when the index layout or what goes into a unit's tf/own changes


class Store:
    """The pack corpus as postings lists. A unit's id is its position in corpus order, so ties in the ranking keep
    the order a full scan would give. `own(t)`: ids of the units whose own words hold t (verdict, df); `tf(t)`:
    [(id, weighted tf)] in id order (ranking). Per unit: `lens`, `summ` (a Summary unit), `tagged`, `root` (a unit of
    a root index file; they come last) and `paths`. Units, article metadata and source urls are read only for what a
    pack or search prints. `anchors`: [(tested question id, question, unit id)] of the `_self` passages."""

    def __init__(self, fp, lens, summ, tagged, paths, arts, srcs, root=None, passage=None, anchors=()):
        self.fp, self.lens, self.summ, self.tagged, self.paths = fp, lens, summ, tagged, paths
        self.arts, self.srcs, self.anchors, self.rules = arts, srcs, list(anchors), False
        self.root = root if root is not None else [False] * len(lens)
        self.passage = passage if passage is not None else [False] * len(lens)
        self.n, self.lensum = len(lens), sum(lens)
        self.n_main = next((i for i, r in enumerate(self.root) if r), len(lens))
        self.n_index = next((i for i, p in enumerate(self.passage) if p), len(lens))
        self._own, self._tf, self._main, self._index, self._rules = {}, {}, None, None, None
        self._anchor_words = None  # tested_matches: each anchored question's informative words, per anchor

    def own(self, t):
        if t not in self._own:
            self._own[t] = self._load_own(t)
        return self._own[t]

    def tf(self, t):
        if t not in self._tf:
            self._tf[t] = self._load_tf(t)
        return self._tf[t]

    def view(self, domain, index=False):
        """The units a pack (or a search) over `domain` (a path prefix: in_prefix) sees: its units, with `index` its
        roots' ledgers too; else every unit but the index files'; with `index`, every unit but the rule passages.
        The domain SELF_ROOT is the rule passages alone."""
        if domain == SELF_ROOT:
            if self._rules is None:
                self._rules = Subset(self, domain, rules=True)
            return self._rules
        if domain:
            return Subset(self, domain, index)
        if index:
            if self.n_index == self.n:
                return self
            if self._index is None:
                self._index = Prefix(self, self.n_index)
            return self._index
        if self.n_main == self.n:
            return self
        if self._main is None:
            self._main = Prefix(self, self.n_main)
        return self._main


class MemStore(Store):
    """Postings built in memory from corpus()."""

    def __init__(self, fp, us):
        own, tfp = defaultdict(list), defaultdict(list)
        for i, u in enumerate(us):
            for t in u["own"]:
                own[t].append(i)
            for t, v in u["tf"].items():
                tfp[t].append((i, v))
        self.own_lists, self.tf_lists, self.us = own, tfp, us
        metas = articles()
        try:
            rows = source_rows()
        except OSError:  # no _sources.csv: packs print its ids as UNKNOWN, search still works (check.py reports it)
            rows = {}
        srcs = {k: [r.get("url") or "", (r.get("superseded_by") or "").strip()] for k, r in rows.items()}
        super().__init__(fp, [u["len"] for u in us], [u["section"].startswith("Summary") for u in us],
                         [bool(u["tags"]) for u in us], [u["path"] for u in us],
                         {k: dict(v) for k, v in metas.items()}, srcs, [bool(u.get("root")) for u in us],
                         [bool(u.get("passage")) for u in us],
                         [(rid, q, i) for i, u in enumerate(us) for rid, q in u.get("anchors", ())])

    def _load_own(self, t):
        return set(self.own_lists.get(t, ()))

    def _load_tf(self, t):
        return self.tf_lists.get(t, [])

    def unit(self, i):
        u = self.us[i]
        return {"id": i, "path": u["path"], "line": u["line"], "section": u["section"], "text": u["text"], "tags": u["tags"]}

    def save(self, path):
        """Write the index to `path` (via a temporary file in the same directory, renamed into place)."""
        d = os.path.dirname(path)
        os.makedirs(d, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".kbindex-", suffix=".tmp", dir=d)
        os.close(fd)
        try:
            con = sqlite3.connect(tmp)
            con.executescript("PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;"
                              "CREATE TABLE meta(k TEXT PRIMARY KEY, v BLOB) WITHOUT ROWID;"
                              "CREATE TABLE post(term TEXT PRIMARY KEY, own BLOB, tfid BLOB, tfv BLOB) WITHOUT ROWID;"
                              "CREATE TABLE unit(id INTEGER PRIMARY KEY, path TEXT, line INTEGER, section TEXT, text TEXT, tags TEXT);")
            pathlist = sorted(set(self.paths))
            pix = {p: i for i, p in enumerate(pathlist)}
            meta = {"version": str(INDEX_VERSION), "fp": self.fp, "lens": array.array("I", self.lens).tobytes(),
                    "flags": bytes(1 * s + 2 * t + 4 * r + 8 * p
                                   for s, t, r, p in zip(self.summ, self.tagged, self.root, self.passage)),
                    "pathix": array.array("I", (pix[p] for p in self.paths)).tobytes(),
                    "paths": json.dumps(pathlist), "arts": json.dumps(self.arts), "srcs": json.dumps(self.srcs),
                    "anchors": json.dumps(self.anchors)}
            con.executemany("INSERT INTO meta VALUES (?, ?)", meta.items())
            terms_ = sorted(set(self.own_lists) | set(self.tf_lists))  # in key order: a WITHOUT ROWID table fills
            # its b-tree in order, where random order splits pages on every insert (a third of a build's time on Windows)
            con.executemany("INSERT INTO post VALUES (?, ?, ?, ?)", (
                (t, array.array("I", self.own_lists.get(t, ())).tobytes(),
                 array.array("I", (i for i, _ in self.tf_lists.get(t, ()))).tobytes(),
                 array.array("d", (v for _, v in self.tf_lists.get(t, ()))).tobytes()) for t in terms_))
            con.executemany("INSERT INTO unit VALUES (?, ?, ?, ?, ?, ?)", (
                (i, u["path"], u["line"], u["section"], u["text"], json.dumps(u["tags"])) for i, u in enumerate(self.us)))
            con.commit()
            con.close()
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)


class SqlStore(Store):
    """Postings read on demand from an index file that MemStore.save wrote."""

    def __init__(self, path):
        self.con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        m = dict(self.con.execute("SELECT k, v FROM meta"))
        if m.get("version") != str(INDEX_VERSION):
            raise ValueError("index version")
        lens = array.array("I")
        lens.frombytes(m["lens"])
        pix = array.array("I")
        pix.frombytes(m["pathix"])
        pathlist = json.loads(m["paths"])
        flags = m["flags"]
        super().__init__(m["fp"], lens.tolist(), [bool(f & 1) for f in flags], [bool(f & 2) for f in flags],
                         [pathlist[i] for i in pix], json.loads(m["arts"]), json.loads(m["srcs"]), [bool(f & 4) for f in flags],
                         [bool(f & 8) for f in flags], json.loads(m["anchors"]))
        self.lock = threading.Lock()

    def _row(self, t):
        with self.lock:
            return self.con.execute("SELECT own, tfid, tfv FROM post WHERE term = ?", (t,)).fetchone()

    def _load_own(self, t):
        r = self._row(t)
        a = array.array("I")
        if r:
            a.frombytes(r[0])
        return set(a)

    def _load_tf(self, t):
        r = self._row(t)
        if not r:
            return []
        ids, vals = array.array("I"), array.array("d")
        ids.frombytes(r[1])
        vals.frombytes(r[2])
        return list(zip(ids, vals))

    def unit(self, i):
        with self.lock:
            path, line, section, text, tags = self.con.execute(
                "SELECT path, line, section, text, tags FROM unit WHERE id = ?", (i,)).fetchone()
        return {"id": i, "path": path, "line": line, "section": section, "text": text, "tags": json.loads(tags)}


class Subset(Store):
    """The units of one domain (a path prefix) of a full store: df, n and the average length over those units only,
    as a pack over corpus(domain) computes them. With `rules`, the rule passages alone."""

    def __init__(self, base, domain, index=False, rules=False):
        self.base = base
        if rules:
            self.keep = {i for i, p in enumerate(base.passage) if p}
        else:
            self.keep = {i for i, p in enumerate(base.paths)
                         if in_prefix(p, domain) and (index or not base.root[i]) and not base.passage[i]}
        ids = sorted(self.keep)
        super().__init__(base.fp, base.lens, base.summ, base.tagged, base.paths, base.arts, base.srcs, base.root,
                         base.passage, base.anchors)
        self.rules = rules
        self.n, self.lensum = len(ids), sum(base.lens[i] for i in ids)

    def own(self, t):  # a filter of the base's list, no read of the index file
        if t not in self._own:
            self._own[t] = self.base.own(t) & self.keep
        return self._own[t]

    def _load_tf(self, t):
        return [(i, v) for i, v in self.base.tf(t) if i in self.keep]

    def unit(self, i):
        return self.base.unit(i)


class Prefix(Store):
    """The first `n` units of a full store (every unit but the root index files'), as a pack over them computes."""

    def __init__(self, base, n):
        super().__init__(base.fp, base.lens, base.summ, base.tagged, base.paths, base.arts, base.srcs, base.root,
                         base.passage, base.anchors)
        self.base, self.n, self.lensum = base, n, sum(base.lens[:n])

    def own(self, t):  # a filter of the base's list, no read of the index file
        if t not in self._own:
            self._own[t] = {i for i in self.base.own(t) if i < self.n}
        return self._own[t]

    def _load_tf(self, t):
        lst = self.base.tf(t)
        return lst[:bisect.bisect_left(lst, (self.n, float("-inf")))]

    def unit(self, i):
        return self.base.unit(i)


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


def index_path(fp):
    """Where the index for fingerprint `fp` lives (in index_dir()), or None when KB_INDEX=0. One file per
    fingerprint and doc2query mode, so a new index never replaces a file a server has open. One index covers every
    served root; with KB_ROOTS set or the roots limited the files are named `kbindex-r<hash of the root set>-...`,
    so servers with different root sets can share a directory without pruning each other's index (store())."""
    where = index_dir()
    return os.path.join(where, f"kbindex-{_root_key()}{fp[:16]}.sqlite") if where else None


def _root_key():
    """'' for this repository's roots alone, else `r<8 hex>-` for the root set KB_ROOTS adds (the fingerprint is
    hex, so never starts with r); a server limited to some roots (kbcommon.serve_only) keys on every root it serves.
    A root inside this repository counts by its repository path, so every checkout of the clone gets the same key."""
    extra = [home_label(r.path) for r in kbcommon.roots()
             if kbcommon.serving() or os.path.dirname(r.path) != kbcommon.KB_DIR]
    if kbcommon.serving():
        extra.insert(0, "only")
    return "r" + hashlib.sha1(os.pathsep.join(extra).encode()).hexdigest()[:8] + "-" if extra else ""


def _same_root(name):
    """Whether an index file name belongs to the current root (store() prunes only those)."""
    key = _root_key()
    return name.startswith("kbindex-" + key) and (key or not name.startswith("kbindex-r"))


def _writable(d):
    if os.path.isdir(d):
        return os.access(d, os.W_OK)
    return os.access(os.path.dirname(d) or ".", os.W_OK)


_STORE = [None, None, 0.0]  # the store this process holds, its index file, when this process last marked it used
_STORE_LOCK = threading.Lock()
KEEP_INDEXES = 4  # index files of the root set store() keeps besides the current one, the most recently used
PRUNE_GRACE = 900  # seconds: an index file used this recently is never pruned, however many newer ones there are
PRUNE_OTHER_ROOTS = 14 * 86400  # seconds: the files of another root set unused this long are pruned (prune_indexes)
USED_EVERY = 60  # seconds: a process serving from an index file marks it used (its mtime) at most this often


def _mark_used(path):
    """Set the index file's mtime to now: what prune_indexes() reads as its last use. Best effort."""
    _STORE[2] = time.monotonic()
    try:
        os.utime(path)
    except OSError:
        pass


def prune_indexes(d, keep):
    """Remove the index files of the current root set in directory `d` other than `keep` that are beyond the
    KEEP_INDEXES most recently used and unused for PRUNE_GRACE: the worktrees of one clone share the directory, so
    one checkout's new index never deletes another's current one, and a process holding a file open marks it used
    (store()). The index files and the unit cache of any other root set (a name _same_root does not match, a
    `kbunits*.sqlite` that is not this root set's) go once unused for PRUNE_OTHER_ROOTS, however many there are:
    no process of a root set in use leaves its files that long unmarked. A file that cannot be removed (open in
    another process on Windows) is left."""
    now, found = time.time(), []
    try:
        names = os.listdir(d)
    except OSError:
        return
    for f in names:
        if not f.endswith(".sqlite") or f == keep:
            continue
        own = _same_root(f)
        if not own and not (f.startswith(("kbindex-", "kbunits")) and f != _unit_cache_name()):
            continue
        try:
            mtime = os.stat(os.path.join(d, f)).st_mtime
        except OSError:
            continue
        if own:
            found.append((mtime, f))
        elif now - mtime > PRUNE_OTHER_ROOTS:
            _remove(os.path.join(d, f))
    found.sort(reverse=True)
    for mtime, f in found[KEEP_INDEXES:]:
        if now - mtime > PRUNE_GRACE:
            _remove(os.path.join(d, f))


def store(domain=None, index=False):
    """The pack index for the current kb: the one this process holds, else the index file for the current
    fingerprint, else built from corpus() now and saved for the next process (a process that cannot write keeps
    it in memory). Rebuilt only when a kb file changed. The view: Store.view(domain, index)."""
    fp = fingerprint()
    with _STORE_LOCK:
        st = _STORE[0]
        if st is None or st.fp != fp:
            st = None
            path = index_path(fp)
            if path and os.path.exists(path):
                try:
                    st = SqlStore(path)
                    _mark_used(path)
                except (sqlite3.Error, ValueError, KeyError):
                    st = None
            if st is None:
                st = MemStore(fp, corpus())
                if path:
                    try:
                        st.save(path)
                        _mark_used(path)
                        prune_indexes(os.path.dirname(path), os.path.basename(path))
                    except (OSError, sqlite3.Error):
                        path = None
            _STORE[:2] = [st, path]
        elif _STORE[1] and time.monotonic() - _STORE[2] > USED_EVERY:
            _mark_used(_STORE[1])
    return st.view(domain, index)


def rank(st, question):
    """BM25 over the units of store view `st` for a question: (ranked [(score, unit id)] best first, the question's
    key words, {key word: ids of the units holding it (alias variants included)}, {key word: that count}).
    A Summary unit scores 1.15 times, an untagged one UNTAGGED_WEIGHT times; ties keep corpus order."""
    q = sorted(set(terms(question)))
    extra, variants = expand(question, st.rules)
    whole = set(terms(question, camel=False))
    weight = {**extra, **{t: 1.0 if t in whole else PART_WEIGHT for t in q}}
    df = {t: len(st.own(t)) for t in weight}
    n = max(st.n, 1)
    avg = st.lensum / n
    keys = sorted(set(key_terms(question)))

    def has_ids(t):  # the units that hold key word t: itself, or every word of one of its alias variants
        ids = set(st.own(t))
        for v in variants.get(t, ()):
            ids |= set.intersection(*(st.own(x) for x in v))
        return ids

    holders = {t: has_ids(t) for t in keys}
    kdf = {t: len(holders[t]) if t in variants or not df.get(t) else df[t] for t in keys}
    acc = {}
    for t, w in weight.items():  # the same arithmetic, in the same order per unit, as a scan over every unit
        if not df[t]:
            continue
        idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
        for i, tf in st.tf(t):
            acc[i] = acc.get(i, 0.0) + w * idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * st.lens[i] / avg))
    ranked = []
    for i in sorted(acc):
        s = acc[i]
        if st.summ[i]:
            s *= 1.15
        if not st.tagged[i]:
            s *= UNTAGGED_WEIGHT
        ranked.append((s, i))
    ranked.sort(key=lambda x: -x[0])
    return ranked, keys, holders, kdf


SEARCH_PER_FILE = 2  # hits are lines, not sections: at most this many per file, so k hits span several files


def search(query, k=8, domain=None, index=False, notes=None, root=None):
    """The top-k units for a query (rag.py search, kb_search): the pack's ranking over every unit, prose and code
    blocks included, and with `index` the index files too (each root's ledgers, the kb's own docs, README.md); at
    most SEARCH_PER_FILE hits per file; `domain` and `root` narrow it (scope()). `notes`, if a list, receives
    warnings: key words found nowhere in the searched units, or a top hit that holds under half of the informative
    ones (in fewer than 25% of the units)."""
    st = store(scope(domain, root), index)
    ranked, keys, holders, kdf = rank(st, query)
    hits, per_file = [], Counter()
    for s, i in ranked:
        if len(hits) >= k:
            break
        if per_file[st.paths[i]] >= SEARCH_PER_FILE:
            continue
        per_file[st.paths[i]] += 1
        u = st.unit(i)
        matched = sorted(t for t in keys if i in holders[t])
        heading = u["section"] or (st.arts.get(u["path"]) or {}).get("title") or os.path.basename(u["path"])
        hits.append({"score": round(s, 2), "path": u["path"], "line": u["line"], "heading": heading, "text": u["text"],
                     "matched": matched, "sources": sorted(set(ID.findall(u["text"])), key=kbid.sort_key)})
    if notes is not None:
        word = {}  # stem -> the query's own word, for the notes
        for w in WORD.findall(query.lower()):
            word.setdefault(stem(w), w)
        missing = [word.get(t, t) for t in keys if not kdf[t]]
        if missing:
            notes.append(f"not found anywhere in the searched files: {', '.join(missing)}")
        informative = {t for t in keys if kdf[t] < 0.25 * max(st.n, 1)}
        top = set(hits[0]["matched"]) if hits else set()
        if hits and informative and len(informative & top) * 2 < len(informative):
            notes.append(f"weak match: the top hit contains {len(informative & top)} of {len(informative)} informative "
                         f"query words ({', '.join(sorted(word.get(t, t) for t in informative))})")
    return hits


TOPIC_SHARE = 0.6  # a word one article is about: that article, named after it, holds this share of its lines
RARE_NAME = 0.01  # a name held by under this share of all lines is mentioned in passing, not covered
COMMON_SHARE = 0.2  # a key word held by this share of the searched units or more is common, not informative


def informative_words(keys, kdf, n):
    """The key words that tell units apart: those held by under COMMON_SHARE of the n searched units, and always
    those held by at most one, since a word one unit holds is never common. Without that floor a small index (a
    root of one article: 3 units, cut below 0.6) keeps no word at all and every question is `none`."""
    return [t for t in keys if kdf[t] < max(COMMON_SHARE * n, 2)]
IDENT = re.compile(r"\w[_./]\w|^--?\w")  # python_files, list/get, ansible.windows.win_dsc, --frozen


def specific(st, question, named, known, keys, holders):
    """True when the question uses a word that names something specific, so a `good` may rest on key words spread
    over several facts: a name (a capital or a digit), an identifier (`python_files`, `list/get`, `--frozen`,
    `gitlab-runner`), a one-word product alias (`dsc`), a word an article is about (named in its title or file name,
    holding TOPIC_SHARE of the word's lines: `ruff`, `krbtgt`, `kiosk`), or a word the kb itself mostly writes as a
    brand (an inner capital or all capitals: `cmpivot` -> CMPivot, `bitlocker` -> BitLocker, `laps` -> LAPS).
    Called only for a `good` no single fact covers, so the unit reads of the last test stay rare."""
    keys = set(keys)
    if named & set(known):
        return True
    words = [w.lower() for w in WORD.findall(question)]
    found = {stem(w) for w in words if "-" in w} & set(known)
    for raw in question.split():
        if IDENT.search(raw):
            found |= set(key_terms(raw.replace("/", " "))) & keys
    single = {f[0] for forms in aliases().values() for f in forms if len(f) == 1}
    found |= {stem(w) for w in words if w in single} & keys
    if found:
        return True
    for w in dict.fromkeys(words):
        t = stem(w)
        if t not in known:
            continue
        for art, k in Counter(st.paths[i] for i in holders[t]).most_common(1):
            meta = st.arts.get(art, {})
            base = re.sub(r"[-_.]", " ", os.path.splitext(os.path.basename(art))[0])
            if k >= TOPIC_SHARE * len(holders[t]) and t in set(key_terms(f"{meta.get('title', '')} {base}")):
                return True
        spelled = re.compile(r"(?<![\w.\-])" + re.escape(w) + r"(?![\w\-])", re.I)
        brand = Counter(bool(re.search(r"[A-Z]", m[1:]) or (m.isupper() and len(m) > 1))
                        for i in sorted(holders[t])[:40] for m in spelled.findall(st.unit(i)["text"]))
        if brand[True] > brand[False]:
            return True
    return False


def opening_passage(st, u):
    """The first passage of the source line of passage `u`: the passages of a line are neighbours in the corpus."""
    i = u["id"]
    while i and st.paths[i - 1] == u["path"] and st.unit(i - 1)["line"] == u["line"]:
        i -= 1
    return u if i == u["id"] else st.unit(i)


TESTED_PINS = 3  # tested questions a `_self` pack pins the passages of
TESTED_FURTHER = 3  # passages a pack with a tested match prints besides the pinned ones (a weak pack keeps its budget)
TESTED_SHARE = 0.75 # of the question's key words a tested question must hold, and half of its own the question


def tested_matches(st, informative):
    """[(id, tested question, passage unit id)] of the (at most TESTED_PINS) anchored tested questions of `_self` store
    view `st` that the question matches: at least TESTED_SHARE of the question's `informative` key words are in the
    tested question and at least half of its informative key words in the question. The best match first, then
    store order."""
    asked, found = {w for w in informative if len(w) >= 3}, []
    if asked and st._anchor_words is None:  # the words depend on the view's counts alone: computed once per view
        st._anchor_words = []
        for rid, text, i in st.anchors:
            keys = sorted(set(key_terms(text)))
            st._anchor_words.append({w for w in informative_words(keys, {t: len(st.own(t)) for t in keys}, st.n)
                                     if len(w) >= 3})
    for n, (rid, text, i) in enumerate(st.anchors if asked else ()):
        theirs = st._anchor_words[n]
        both = asked & theirs
        if theirs and len(both) >= TESTED_SHARE * len(asked) and len(both) * 2 >= len(theirs):
            found.append((-len(both), n, (rid, text, i)))
    return [x[2] for x in sorted(found)[:TESTED_PINS]]


LIST_INTRO_CHARS = 80  # a passage whose own text is shorter than this and ends in `:` introduces a list


def list_intro(u):
    """Whether passage `u`, without its context prefix, is a list introduction ("… refuses when any of these hold:"):
    its children carry it as their parent context, and alone it says nothing."""
    own = u["text"].rsplit(CONTEXT_SEP, 1)[-1]
    return own.endswith(":") and len(own) < LIST_INTRO_CHARS


def pick_passages(st, scored, best, cost, limit, pins=()):
    """{doc: [(score, passage)]} of a `_self` pack: the `pins` (passages marked `tested`) first, in their docs, then the
    passages of every doc compete, best first until `limit` characters are used (`cost` is spent already), no text
    twice, at most PASSAGES_PER_LINE of one source line. A line shows its opening passage, which states the rule: for
    a table row, whose later passages carry only its first cell, when it is not among the line's chosen ones it takes
    the place of the lowest-scored of its unpinned ones. With pins, at most TESTED_FURTHER further passages."""
    taken, shown, per_line = defaultdict(list), set(), Counter()
    for u in pins:
        cost += len(clip(u["text"], PASSAGE_CHARS + PARENT_CHARS + CLAUSE_CHARS)) + len(u["path"]) + 12 + (
            0 if u["path"] in taken else len(u["path"]) + 50)
        shown.add(u["text"])
        per_line[(u["path"], u["line"])] += 1
        taken[u["path"]].append((float("inf"), u))
    further = 0
    for s, u in scored:
        if pins and further >= TESTED_FURTHER:
            break
        if s < 0.4 * best or u["text"] in shown or per_line[(u["path"], u["line"])] >= PASSAGES_PER_LINE or list_intro(u):
            continue
        line_cost = len(clip(u["text"], PASSAGE_CHARS + PARENT_CHARS + CLAUSE_CHARS)) + len(u["path"]) + 12
        head_cost = 0 if u["path"] in taken else len(u["path"]) + 50
        if cost + line_cost + head_cost > limit and any(taken.values()):
            break
        cost += line_cost + head_cost
        shown.add(u["text"])
        per_line[(u["path"], u["line"])] += 1
        taken[u["path"]].append((s, u))
        further += 1
    for rel, items in taken.items():
        rows = (read(rel) or "").splitlines()
        for line in dict.fromkeys(u["line"] for _, u in items):
            on_line = [x for x in items if x[1]["line"] == line]
            mine = [x for x in on_line if not x[1].get("tested")]
            if not mine:
                continue
            first = opening_passage(st, mine[0][1])
            if not rows[line - 1].lstrip().startswith("|") or first["id"] in {u["id"] for _, u in on_line} or first["text"] in shown:
                continue
            low = min(mine, key=lambda x: x[0])
            items[items.index(low)] = (low[0], first)
            shown.add(first["text"])
    return taken


def pack(question, budget=1200, domain=None, max_articles=4, fmt="detailed", footer=True, root=None, invalidated=False,
         item=None, st=None):
    """Rank fact units for a question and return {verdict, route, has, lacks, missing, matched, sources, text, ...}.

    The corpus is every fact unit plus the untagged bullets, table rows and data rows (Summary, Reference, Examples,
    untagged csv rows), which rank at UNTAGGED_WEIGHT and print with `(no tag)`: a word the kb has anywhere is never
    reported as "not in the kb".

    verdict (counted on whole query words, not hyphen parts), on the top-ranked article that matches the most key
    words: `none` when a third or more of the named words (with a capital or a digit: products, ids) occur nowhere in
    the kb (unless it is one name of up to 3 letters among 75%+ matched words, like AV or PC), when half or more of
    the informative words occur nowhere, or when that article matches under a third of the known ones; `good` when a
    tagged-fact article matches 60% or more (80% if some word is unknown), no named word is missing, and every
    informative name appears in a top-ranked tagged fact; else `weak`. Then two corrections: a `good` whose question
    names nothing specific (specific()) and whose key words no single tagged fact holds all of becomes `weak`; and a
    verdict becomes `none` when a name the question uses is held by under RARE_NAME of all lines and by none of the
    lines the pack could print (up to 6 per shown article), since the question is then about another product.
    Untagged content alone never makes a question `good`. A `good` pack gets a
    `check:` note (verdict unchanged) when a name the question uses is nowhere in the lead article, or when no tagged
    fact among the top hits holds half of 4+ key words. A word that is a product alias (_tools/aliases.csv) counts as present where any alias of the product is;
    the other aliases rank at a lower weight but never count as key words. `budget` is in tokens (about 3.5
    characters each) and bounds the text. A `weak` or `none` pack, and a flagged `good` one (a `check:` line, or a
    word nowhere in the kb), also prints `route:` (`split`, or `web` for a `none` unless only language or format names are missing), `kb has:` (the question's own words
    the best article matches) and `kb lacks:` (its informative words it does not match), after the coverage, check:,
    freshness: and none-sentence lines. A `none` that routes `split` (a near miss) prints no none sentence and keeps
    the facts and source footer a `weak` pack prints; a `none` that routes `web` prints the sentence, two lines of one
    article and no footer. `route` is None for a clean `good` pack, whose text has no such line.
    Decisions: a kb that keeps `_decisions.csv` rows adds a `## decisions` section after the articles (decisions_for:
    at most MAX_DECISIONS lines, `decided`, `proposed (not confirmed)`, or with `invalidated` also `invalidated because
    <reason>`), counted inside `budget`. An active decision whose text holds 60% of the informative words and every
    name of the question makes the verdict `good` (its words leave `missing` and the route lines, and no `check:` line
    follows from the facts); a proposed or invalidated one never changes it. A kb with none prints what it always did,
    byte for byte.
    Root `_self` (the kb's own rule docs) prints, after the passages, the decisions tied by an `article:_self/<doc>` or
    `article:_self/<doc>#<Heading>` context to a doc or section a printed passage is in (tied_decisions), each with its
    source, beside those the question's words find; at most MAX_DECISIONS lines. With `item` (item_brief) the question
    ranks the item's docs only, and the decisions are item_decisions: at most ITEM_DECISIONS lines. A `_self` pack
    first compares the question with the anchored tested questions (tested_matches): the passage of each that matches
    is printed first, marked `[tested <id>]`, and the verdict is `good` only then (`coverage: good (tested question
    <id>: <question>)`); with none it is at most `weak`, `none` by the key words alone. `st` is the store view to use
    (self_store), else the index's.
    Observed signals: a kb that keeps `_logs.csv` rows adds, after the decisions, `observed signal (LOG, not a fact):`
    and the active rows whose context is a printed article or fact (logs_for: at most MAX_LOGS lines, newest first, each
    with the dates it covers), paid from what budget the facts leave, so a small budget drops them first. They are
    computed after the verdict, the route and the `check:` lines and change none of them, nor any fact line; a `none`
    that routes web prints none. A kb with none prints what it always did, byte for byte. fmt
    `concise` drops the article flags and the source url footer; footer=False leaves the footer out of the text (pack_many prints one shared footer). `domain` (bare `intune`
    or qualified `public/intune`) and `root` narrow the units (scope()); paths print qualified (`public/intune/x.md`)."""
    rules = scope(domain, root) == SELF_ROOT  # the kb's own rule docs: facts without sources, no web route
    st = st or store(scope(domain, root))
    ranked, keys, holders, kdf = rank(st, question)
    if item:
        ranked = [x for x in ranked if st.paths[x[1]] in item["docs"]]
    n = max(st.n, 1)
    informative = informative_words(keys, kdf, n)
    missing = [t for t in informative if not kdf[t]]
    scored = [(s, st.unit(i)) for s, i in ranked[:40]]
    tested = tested_matches(st, informative) if rules else []
    pins = [{**st.unit(i), "tested": rid} for rid, _, i in tested]
    anchor_phrases = {r["id"]: eval_phrases(r) for r in self_eval_rows()} if tested else {}

    def has(u, t):
        return u["id"] in holders[t]

    # verdict: named words (product names, ids: a capital or a digit, not the question's first word) that the kb
    # never mentions mean it does not cover the question; else the share of the kb-known key words that the best
    # article's units match
    named = {stem(w.lower()) for w in WORD.findall(question) if re.search(r"[A-Z0-9]", w) and w.lower() not in STOP}
    named = {t for t in named if t in kdf}
    named_missing = sorted(t for t in named if not kdf[t])
    known = [t for t in informative if kdf[t]]
    # the verdict counts the key words of the top-ranked article (among the first 40 units) that matches the most
    # `good` needs tagged facts; untagged rows and lines (reference data, Summary, Examples) can lift a question
    # from `none` to `weak` but never to `good`, since a list row that merely names a product is no answer
    arts_hit, arts_fact = defaultdict(set), defaultdict(set)
    for s_, u in scored[:40]:
        words = {t for t in known if has(u, t)}
        arts_hit[u["path"]] |= words
        if u["tags"]:
            arts_fact[u["path"]] |= words
    hit = max(arts_hit.values(), key=len, default=set())
    fact_hit = max(arts_fact.values(), key=len, default=set())
    share = len(hit) / len(known) if known else 0.0
    fact_share = len(fact_hit) / len(known) if known else 0.0
    # one unknown abbreviation (AV, PC) among well-matched words; a longer unknown name (NinjaOne, Ivanti) is the subject
    lone_name = len(named_missing) == 1 and len(named_missing[0]) <= 3 and share >= 0.75
    if not scored or (named and len(named_missing) * 3 >= len(named) and not lone_name) or (informative and len(missing) * 2 >= len(informative)):
        verdict = "none"
    elif fact_share >= 0.6 and not named_missing and (not missing or fact_share >= 0.8) and not (named & set(known)) - set().union(*arts_fact.values()):
        verdict = "good"  # and every informative name the question uses (Okta, SCIM) is in a top-ranked fact
    elif share >= 0.34:
        verdict = "weak"
    else:
        verdict = "none"
    # a `good` on common words only ("email attachment size" matched the Email* hunting tables, "mailbox size limit" a
    # batching fact and a manifest row): a question that names nothing specific needs one tagged fact holding every
    # key word
    if (verdict == "good" and len(known) >= 2 and not any(u["tags"] and all(has(u, t) for t in known) for _, u in scored)
            and not specific(st, question, named, known, keys, holders)):
        verdict = "weak"
    # group the best units by article, strongest article first
    by_art, order = defaultdict(list), []
    for s, u in scored[:40]:
        art = u["path"]
        if art not in by_art:
            order.append(art)
        by_art[art].append((s, u))
    best = scored[0][0] if scored else 0
    order = [a for a in order if by_art[a][0][0] >= (0.5 if a.endswith(".md") else 0.65) * best][:max_articles]
    # an off-domain question (VMware Horizon, SAP GUI): its product is a rare name the kb mentions in passing, and no
    # line the pack could print holds it, whatever the other words match
    if verdict != "none":
        cand = [u for a in order for _, u in sorted((x for x in by_art[a] if x[0] >= 0.4 * best), key=lambda x: -x[0])[:6]]
        if any(len(t) > 2 and kdf[t] < RARE_NAME * n and not any(has(u, t) for u in cand) for t in named & set(known)):
            verdict = "none"
    # operator decisions beside the facts (decisions_for): an active one that answers the question lifts the coverage
    # to `good` and its words count as held; their lines count inside the budget, so the facts get what is left
    dec, dheld, lifted, answering = [], set(), False, []
    if item:
        dec = [{**d, "hit": [], "answers": False} for d in item_decisions(item)]
    elif decision_rows():
        cand = [u for a in order for _, u in sorted((x for x in by_art[a] if x[0] >= 0.4 * best), key=lambda x: -x[0])[:6]]
        dec = decisions_for(informative, named, set(order), cand, scope(domain, root), invalidated)
        answering = [d for d in dec if d["answers"] and d["status"] == "active" and not rules]
        if answering:
            dheld = set().union(*(d["hit"] for d in answering))
            lifted = verdict != "good"
            verdict = "good"
            missing = [t for t in missing if t not in dheld]
    cap = ITEM_DECISIONS if item else MAX_DECISIONS
    dlines, kept = decision_block(dec, budget, cap, rules)
    dused = sum(map(len, dlines)) + (40 if dlines else 0)  # the section's heading
    concise = fmt == "concise"
    url_cost = 0 if concise or rules else 110  # a source footer line is about 110 characters
    limit, used, groups, cited, paths, printed = int(budget * 3.5), dused, [], [], [], []
    taken = defaultdict(list)
    if rules:
        taken = pick_passages(st, scored, best, dused, limit, pins)
        if not item:
            # the decisions tied to a doc or section a chosen passage is in follow the ones the question's words found
            # and only when its text or source shares a key word with the question or the tested question pinned
            have = {d["id"] for d in dec}
            bears = set(informative).union(*(key_terms(q) for _, q, _ in tested))
            dec = dec + [{**d, "hit": [], "answers": False} for d in
                         tied_decisions(self_places(u for g in taken.values() for _, u in g), invalidated)
                         if d["id"] not in have and bears & set(key_terms(d["text"] + " " + d["source"]))]
            dlines, kept = decision_block(dec, budget, cap, True)
            dused = sum(map(len, dlines)) + (40 if dlines else 0)
            taken = pick_passages(st, scored, best, dused, limit, pins)
            used = dused
        order = list(taken)
    for art in order:
        if rules:
            picked = taken[art]
        else:
            picked = sorted(sorted((x for x in by_art[art] if x[0] >= 0.4 * best), key=lambda x: -x[0])[:6],
                            key=lambda x: x[1]["line"])
        items = []
        one_section = len({u["section"] for _, u in picked}) == 1  # rule docs: the heading once, else on each line
        for s, u in picked:
            if rules:
                text = clip_around(u["text"], PASSAGE_CHARS + PARENT_CHARS + CLAUSE_CHARS,
                                   anchor_phrases.get(u.get("tested"), ()), set(informative))
            else:
                text = clip(u["text"], 420)
            where = f" § {u['section']}:" if rules and u["section"] and not one_section else ""
            mark = f" [tested {u['tested']}]" if u.get("tested") else ""
            line = f"- {u['path']}:{u['line']}{mark}{where} {text}" + ("" if u["tags"] else " (no tag)")
            line += ("\n" + snippet_code(u)) if snippet_code(u) else ""
            new_ids = [i for p in u["tags"] for i in p["ids"]] + ID.findall(text)
            # the root prefix of the path (`public/`) is not counted: a pack chooses the same lines in any layout
            cost = len(line) - (len(u["path"]) - len(bare(u["path"]))) + url_cost * len(set(new_ids) - set(cited))
            if used + cost > limit and (items or groups):
                used = limit
                break
            items.append(line)
            printed.append(u)
            used += cost
            cited += new_ids
        if items:
            more = sum(1 for x in ranked if st.paths[x[1]] == art and x[0] >= 0.4 * best) - len(items)
            if more > 0:  # e.g. hundreds of similar rows in a data file: the answer may be one of these
                items.append(f"  (+{more} more matching lines in {art}: kb_search with more words, or kb_show)")
            meta = st.arts.get(art, {})
            head = f"## {art}" + (f"  {meta.get('title', '')}" if meta else "")
            if rules and one_section and picked[0][1]["section"]:
                head += f"  § {picked[0][1]['section']}"
            flags = ", ".join(filter(None, (meta.get("status"), f"retrieved {meta['retrieved_utc']}" if meta.get("retrieved_utc") else "")))
            groups.append((head + (f"  [{flags}]" if flags and not concise else ""), items))
            paths.append(art)
            used += len(head) - (len(art) - len(bare(art))) + 40
        if used >= limit:
            break
    if rules and not item:
        tied = {d["id"] for d in tied_decisions(self_places(printed), invalidated)}
        dlines, kept = decision_block([d for d in dec if d["answers"] or d["id"] in tied], budget, cap, True)
    unheld = []
    if rules:
        # the docs are so large that "the best article matches most key words" holds for almost any question: the
        # verdict counts the key words one printed passage (with its context and heading) holds
        informative_set = set(informative)
        words = [{t for t in informative if has(u, t)} for u in printed]
        hit = max(words, key=len, default=set())
        unheld = [t for t in informative if not any(t in w for w in words)]
        best_share = len(hit) / len(informative) if informative else 0.0
        names = named & informative_set
        # one printed passage holds every named word, and no key word is missing from the docs
        names_held = bool(names) and not missing and any(names <= w for w in words)
        if tested:
            verdict = "good"
        elif not printed or (best_share < 0.34 and not names_held) or names - set().union(*words):
            verdict = "none"
        else:
            verdict = "weak"
    seen, srcs = set(), []
    for i in cited:
        if i not in seen:
            seen.add(i)
            url, sup = st.srcs.get(i, ("", ""))
            srcs.append((i, url or "UNKNOWN id", sup))
    # a name the question uses (ServiceNow) that the lead article never mentions, not even in its title or applies_to,
    # though another printed line holds it (a rare name no printable line holds made the verdict `none` above): the
    # verdict counts words, not meaning, so such a pack may be about something related (a false `good`). A note, not a
    # verdict change: the name alone does not tell a related pack from a right one (the NTLMv1 row's
    # LmCompatibilityLevel sits in a second article). Names of two letters (AV, PC) are left out.
    unmatched = []
    if verdict != "none" and paths and not lifted:
        lead, meta = paths[0], st.arts.get(paths[0], {})
        own = set(key_terms(f"{meta.get('title', '')} {meta.get('applies_to', '')}"))
        unmatched = sorted(t for t in named & set(known) if len(t) > 2 and t not in own
                           and not any(st.paths[i] == lead for i in holders[t]))
    # a `good` whose key words are spread over separate facts, none holding half of them (mailboxes, calendars and
    # contacts between tenants, matched by a tenant fact and a mailbox fact) though the question names something
    # specific (Graph): the other sign of a false `good`. No true `good` in the eval set falls under half; a note only.
    spread = None
    if verdict == "good" and len(known) >= 4 and not lifted:
        top = max((sum(1 for t in known if has(u, t)) for _, u in scored if u["tags"]), default=0)
        if top * 2 < len(known):
            spread = (top, len(known))
    head = f"coverage: {verdict}"
    counted = informative if rules else known
    if tested:
        head += f" (tested question {tested[0][0]}: {tested[0][1]})"
    elif counted:
        head += (f" ({'an active decision answers it; ' if lifted else ''}{'no tested question matches; ' if rules else ''}"
                 f"best {'passage' if rules else 'article'} matches {len(hit)} of {len(counted)} key words: "
                 f"{', '.join(sorted(hit)) or '-'})")
    elif rules:
        head += " (no tested question matches)"
    elif lifted:
        head += " (an active decision answers it)"
    if missing:
        head += f"; not in the kb: {', '.join(missing)}"
    out = [head]
    if unmatched:
        names = {stem(w.lower()): w for w in WORD.findall(question)}
        out.append(f"check: {paths[0]} never mentions {', '.join(names.get(t, t) for t in unmatched)}; the facts may be "
                   "about something related. Answer only if a cited line answers the question itself.")
    if spread:
        out.append(f"check: no single fact holds half the key words (at most {spread[0]} of {spread[1]}); the facts may "
                   "be about something related. Answer only if a cited line answers the question itself.")
    fresh = freshness(question, missing, st.arts.get(paths[0] if paths else (order[0] if order else ""), {}))
    if fresh:
        out.append(fresh)
    route = None if rules and verdict == "none" else route_of(verdict, unmatched, spread, missing)
    # a near miss (a `none` that routes split: only a language or format name is nowhere in the kb) prints what a
    # `weak` pack would, its facts and source footer, and no none sentence, so the reader answers the part the kb has
    # (sp_getapplock for the T-SQL question) and looks up only the rest
    shut = verdict == "none" and (rules or route != "split") and not item  # an item's brief prints its passages whatever the verdict
    if shut and not rules:
        out.append(NONE_SENTENCE)
    has = own_words(question, set(hit) | dheld)
    lacks = own_words(question, [t for t in informative if t not in hit and t not in dheld])
    if route:
        out += ([] if rules else [f"route: {route}"]) + [f"kb has: {', '.join(has) or '-'}", f"kb lacks: {', '.join(lacks) or '-'}"]
        if rules:
            route = None  # the web never applies to the rule docs
    elif rules and verdict == "none" and not item:
        out += [f"kb has: {', '.join(has) or '-'}", f"kb lacks: {', '.join(lacks) or '-'}",
                'the rule docs do not answer it: python3 _tools/rag.py search --index "<words>" (ledgers, README.md, '
                "every kb/_self doc)"]
    if rules and verdict != "good" and not item:
        out.append("reword once with the rule's own words, or read the section: python3 _tools/selfdoc.py section DOC HEADING")
    for h, items in groups if not shut else [(g[0], g[1][:2]) for g in groups[:1]]:
        out += ["", h] + items
    if dlines:
        out += ["", "## decisions"] + dlines
    # observed signals (LOG rows) of the printed articles and facts, after everything above and out of its verdict: they
    # take what budget the facts leave, so a small budget cuts them first
    llines, lshown, lused = [], [], len(LOG_LABEL) + 1
    for r in ([] if shut else logs_for(set(paths), printed)[:MAX_LOGS]):
        line = log_line(r)
        if used + lused + len(line) + 1 > limit:
            break
        llines.append(line)
        lshown.append(r)
        lused += len(line) + 1
    if llines:
        out += ["", LOG_LABEL] + llines
    if shut or rules:
        srcs = []
    if srcs and footer and not concise:
        out += ["", "sources:"] + format_sources(srcs)
    return {"verdict": verdict, "missing": missing, "matched": sorted(hit), "informative": informative, "known": known,
            "unmatched": unmatched, "spread": spread, "route": route, "has": has, "lacks": lacks, "paths": paths,
            "tested": [t[0] for t in tested], "pinned": sum(1 for u in printed if u.get("tested")),
            "key_missing": own_words(question, unheld),
            "sources": [s[0] for s in srcs], "source_rows": srcs, "text": "\n".join(out),
            "decisions": [{"id": d["id"], "status": d["status"], "label": decision_label(d), "path": d["path"],
                           "line": d["line"], "text": d["text"], "answers": d["answers"]} for d in kept],
            "logs": [{"id": r["id"], "path": r["path"], "line": r["line"], "observed_from": r["observed_from"],
                      "observed_to": r["observed_to"], "text": r["text"]} for r in lshown]}


# language and format names: a question asking for a topic the kb covers in one of them (T-SQL for sp_getapplock) is a
# near miss when they are the only words the kb lacks, not a topic it does not cover
LANGUAGE_NAMES = frozenset(("t-sql", "tsql", "powershell", "python", "bash", "kql", "json", "yaml", "xml", "csv"))


def route_of(verdict, unmatched, spread, missing):
    """Where a question goes after the pack: None (answer from the pack), `split` (the kb has part of it: answer what
    the pack holds, look up what it lacks in the live docs) or `web` (the kb does not cover it). A `good` pack is
    flagged, and routes `split`, when it has a `check:` line (`unmatched`, `spread`) or a word nowhere in the kb
    (`missing`); a clean `good` routes nowhere. A `none` pack routes `web`, except a near miss: when every word
    nowhere in the kb is a language or format name (LANGUAGE_NAMES) it routes `split`."""
    if verdict == "none":
        return "split" if missing and all(t in LANGUAGE_NAMES for t in missing) else "web"
    if verdict == "weak" or unmatched or spread or missing:
        return "split"
    return None


def own_words(question, stems):
    """The question's own words, in question order, whose stems are in `stems` (each stem once, the first spelling):
    the stems the verdict counts, mapped back the way kb_hook.respond names the missing words."""
    want, out = set(stems), {}
    for w in WORD.findall(question):
        t = stem(w.lower())
        if w.lower() not in STOP and len(w) > 1 and t in want:
            out.setdefault(t, w)
    return list(out.values())


LATEST = re.compile(r"(?i)\b(latest|newest|most recent)\b|\bcurrent (version|release|build)\b")
VERSION = re.compile(r"\bv?\d+(\.\d+){1,3}\b")


def freshness(question, missing, meta):
    """A note for a question about the latest release, or naming a version the kb never mentions: the kb's facts
    are as of the lead article's retrieval, so the answer needs the live source and the version it is for. Models
    otherwise report the kb's newest version as the latest ("Partial knowledge, newer versions and stale copies" in
    kb/_self/reports/benchmarks.md). None when neither applies."""
    versions = [v for v in dict.fromkeys(m.group(0) for m in VERSION.finditer(question)) if stem(v.lower()) in missing]
    if not (LATEST.search(question) or versions):
        return None
    said = ([f"these facts are as of {meta['retrieved_utc']}"] if meta.get("retrieved_utc") else []) + (
        [f"the kb never names {', '.join(versions)}"] if versions else [])
    return (f"freshness: {'; '.join(said) or 'a kb fact is as of its retrieval'}. A newer release may exist: check the "
            "cited source live and say which version your answer is for.")


def snippet_code(u):
    """The fenced code block right below a `SNIPPET:` bullet unit, as indented lines ("" for any other unit or a
    bullet with no block): a pack that picks the bullet gives the reader the code its words describe."""
    if not u["text"].startswith("SNIPPET:"):
        return ""
    body = (read(u["path"]) or "").splitlines()
    i = u["line"]  # the line after the bullet's first line
    while i < len(body) and body[i].strip() and not body[i].lstrip().startswith(("```", "~~~")):
        i += 1  # the bullet's continuation lines
    while i < len(body) and not body[i].strip():
        i += 1
    if i >= len(body) or not body[i].lstrip().startswith(("```", "~~~")):
        return ""
    code = []
    for ln in body[i + 1:]:
        if ln.lstrip().startswith(("```", "~~~")):
            return "\n".join("  " + c for c in code)
        code.append(ln.rstrip())
    return ""


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


def format_sources(srcs):
    return [f"  -> {i}  {u}" + (f"  (superseded by {s})" if s else "") for i, u, s in srcs]


MAX_QUESTIONS = 6
PART_BUDGET_MIN = 800  # tokens per part of a 3+ part pack


def pack_many(questions, budget=1200, domain=None, fmt="detailed", root=None, invalidated=False, item=None):
    """One pack per question (1-6), each with its own coverage verdict, and one shared source footer:
    {verdict (the worst), results, text}. A single question gives exactly pack()'s text. With 3 or more questions
    each part gets 2 * budget / n tokens, at least PART_BUDGET_MIN (never more than budget): measured on the eval set,
    800 tokens keep 98% of the expected article's fact lines that 1200 print, and a 6-part pack shrinks by a third.
    `route` is the overall route of the parts, printed as the pack's first line: `web` when every part routes web,
    else `split` when any part routes; None (no line) when none does. One question gives its pack's route."""
    qs = [q.strip() for q in questions if q and q.strip()][:MAX_QUESTIONS]
    if len(qs) == 1:
        res = pack(qs[0], budget, domain, fmt=fmt, root=root, invalidated=invalidated, item=item)
        return {"verdict": res["verdict"], "route": res["route"], "results": [res], "text": res["text"]}
    part = budget if len(qs) < 3 else max(min(budget, PART_BUDGET_MIN), 2 * budget // len(qs))
    results = [pack(q, part, domain, fmt=fmt, footer=False, root=root, invalidated=invalidated, item=item) for q in qs]
    routes = [r["route"] for r in results if r["route"]]
    route = None if not routes else "web" if all(r["route"] == "web" for r in results) else "split"
    out, seen, srcs = ([f"route: {route}"] if route else []), set(), []
    for i, (q, res) in enumerate(zip(qs, results), start=1):
        out += [f"# Q{i}: {q}", res["text"], ""]
        for row in res["source_rows"]:
            if row[0] not in seen:
                seen.add(row[0])
                srcs.append(row)
    if srcs and fmt != "concise":
        out += ["sources:"] + format_sources(srcs)
    order = ("none", "weak", "good")
    return {"verdict": min((r["verdict"] for r in results), key=order.index), "route": route, "results": results,
            "text": "\n".join(out).rstrip()}


def cited_lines(ids):
    """{id: [(qualified path, line)]}: every kb file line (every root's domain files and ledgers, not _sources.csv)
    naming the id."""
    want = {kbid.canonical_id(i) for i in ids}
    out = defaultdict(list)
    files = list(kb_files((".md", ".csv"))) + root_files(ROOT_LEDGERS)
    for rel in files:
        text = read(rel)
        if not text or not any(i in text for i in want):
            continue
        for n, ln in enumerate(text.splitlines(), start=1):
            for i in set(ID.findall(ln)) & want:
                out[i].append((rel, n))
    return out


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
