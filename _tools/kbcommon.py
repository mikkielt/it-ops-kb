#!/usr/bin/env python3
"""Helpers the kb tools share (stdlib only): reading kb files, reading and writing CSV the canonical way, and the
source ledger. One copy, so every tool reads and writes these files the same way.

  read(rel)                   a kb file's text, or None when it cannot be read
  load_csv(name, required)    (fieldnames, rows) of a kb CSV; CsvError names the file and the problem
  parse_csv(name, text, ...)  the same for text already read
  csv_text(header, rows)      canonical CSV text of dict rows: csv-module quoting, `\\n` line ends, header first
  rows_text(rows)             the same for list rows (the header is the first row)
  write_csv(path, header, rows, atomic=False)
  read_sources()              the rows of _sources.csv, in file order
  REUSE                       the classes of the `reuse` column of _sources.csv and what each allows
  source_rows()               {id: row} of _sources.csv
  DECISIONS, DECISION_MAKERS  the decision files a root and kb/_self may hold; DECISION_COLS, MAKER_COLS their columns,
                              DECISION_ID the `D-<8 base32>` id (D is reserved), DECISION_STATUS, CONTEXT_KINDS
  context_refs(text)          [(kind, value)] of a decision's context; split_list(text) any `;`-separated field
  maker_names_allowed(root)   whether a root's decision-makers file may hold a name (visibility and the root's policy)
  root_policy(root)           the storage policy for decision makers a root's decision-makers.csv sets ('' when unset)
  data_path(rel, shared)      a file of the kb's own retrieval data under <kb>/DATA_DIR/
  repo_rel(rel)               a path relative to the kb root as a path relative to this repository (git pathspecs)
  kb_rel(path)                the inverse: a repository path (or absolute path) relative to the kb root, or None
  resolve(rel)                the absolute path of a file named relative to the kb root, else to this repository

Roots. Knowledge lives in roots: kb/public (the upstream facts) and any kb/<name>/ a team adds, each a directory
with a ROOT_FILE (`_root.md`: front matter `root`, `id_prefix`, `visibility`, `description`) and the same layout:
domain directories of articles, the ledgers (SOURCES, ANSWERS, GAPS, CONFLICTS, COVERAGE_CSV, COVERAGE_MD, STATE,
ARTIFACTS, ANCHORS), `_census/`, SNAPSHOTS and DATA_DIR. Every path inside a root is relative to that root, so moving a root moves no
line inside it. Tools that span roots name a file by its qualified path `<root>/<path in root>` (`public/intune/x.md`)
and a topic by `<root>/<topic>`.

  roots()                     [Root] in order: public first, then kb/<name>/ by name, then the KB_ROOTS dirs
                              (only the named ones after serve_only)
  serve_only(names)           limit roots() to the named roots for this process (kb_mcp.py --roots); RootError
                              names an unknown one; serving() gives the names, () when every root is served
  root(name)                  the Root of that name (KeyError when there is none)
  public()                    the public Root (whether served or not)
  qualify(root, rel)          `<root name>/<rel>`
  split(qpath)                (Root, rel) of a qualified path; (None, qpath) when its first part names no root
  path_of(qpath)              the absolute path of a qualified path (a root's file), else of a repository path
  root_of_prefix(prefix)      the Root whose id_prefix it is, or None

KB_ROOTS=DIR[:DIR...] adds roots kept outside this repository (a team's private repository with the same root
layout and its own ROOT_FILE): the read tools and the checks serve them with kb/'s roots; git, census and fetch work
on this repository's roots only.

Layout. The paths below are the only place that says where knowledge sits in this repository: the tools' code in
_tools/, the roots in KB_DIR, the kb's own docs in SELF. KB is the public root, the default of the tools that work on
one root.
"""
import csv, io, os, re, sys


def utf8_stdio():
    """Print UTF-8 on every OS. A pipe on Windows defaults to the locale code page (cp1252), which cannot encode much
    of the kb and which a reader expecting UTF-8 cannot decode; a UTF-8 stream (macOS, Linux) is left as it is."""
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure") and (s.encoding or "").lower().replace("-", "") != "utf8":
            s.reconfigure(encoding="utf-8")


utf8_stdio()  # every tool imports this module before it prints
from typing import NamedTuple

TOOLS = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.dirname(TOOLS)  # this repository: the tools' code, the shared product aliases
KB_DIR = os.path.join(HOME, "kb")  # all knowledge: the roots and SELF
PUBLIC = os.path.normpath(os.path.join(KB_DIR, "public"))  # the public root: articles, ledgers, retrieval data
SELF = os.path.join(KB_DIR, "_self")  # the kb's own docs: rules, tool reference, design (searched with --index only)
DATA_DIR = "_retrieval"  # a root's retrieval data (signals, eval set, doc2query, index extras), relative to the root
KB = PUBLIC
ROOT_FILE = "_root.md"
SOURCES, STATE, ARTIFACTS = "_sources.csv", "_fetch_state.csv", "_artifacts.csv"
# _fetch_state.csv: fetch.py's columns (the text hash of --diff), then factdiff.py detect's (the provider's signals as
# last seen: validators, version id, the normalized document's hash, where the url led, its status and simhash)
STATE_COLS = ["id", "url", "checked_utc", "fetched_utc", "changed_utc", "sha256", "text_sha256", "bytes", "error",
              "etag", "last_modified", "version", "doc_sha256", "final_url", "http_status", "simhash", "detected_utc"]
ANSWERS, GAPS, CONFLICTS = "_answers.md", "_gaps.md", "_conflicts.md"
COVERAGE_CSV, COVERAGE_MD = "_coverage.csv", "_coverage.md"
CENSUS_DIR = "_census"
# Fact anchors (factdiff.py): where each fact's backing passage sits in its source; check.py enforces the format.
ANCHORS = "_anchors.csv"
ANCHOR_COLS = ["fact", "path", "source_id", "status", "heading", "terms", "sha", "quote", "verified_utc"]
ANCHOR_REASONS = ("fetch-error", "not-text", "no-match", "gone")
SNAPSHOTS = "_snapshots"  # normalized copies of the root's live `copy` sources, with attribution (factdiff.py snapshot)
NO_HOOKS = ["--settings", '{"disableAllHooks": true}']  # every `claude -p` the tools start runs no hook
QUOTE_WORDS = 25  # the longest quote a `quote` source allows (kb/_self/content-rules.md, Licensing)
# What a source's licence allows with its text: the `reuse` column of _sources.csv (check.py rejects anything else).
REUSE = {
    "copy": "an open licence allows a verbatim copy and redistribution, with attribution (and its other conditions)",
    "quote": "no reuse licence (terms of use, all rights reserved): paraphrase, quotes of 25 words or fewer",
    "paraphrase": "the terms forbid copying the text (CIS, ISO): paraphrase and cite ids only, no quotes",
    "unknown": "the terms could not be read or determined: treated as paraphrase",
}
PREFIX = re.compile(r"[A-Z]{1,4}")  # a root's source id prefix: its ids are <prefix>-<8 base32 chars>
RESERVED_PREFIXES = {"DOC", "CODE", "DER", "UNK", "QK", "EV", "PL", "D"}  # tag kinds, answer, eval and decision ids, placeholders
# Decisions. Any root, and kb/_self, may keep two files (check.py checks them; kb/_self/content-rules.md, Decisions):
# _decisions.csv holds the operator's decisions, one row each, and decision-makers.csv who may make them; the file in
# kb/_self is the central register that a root's `by_ref` may name when the root keeps no row for the maker itself.
DECISIONS, DECISION_MAKERS = "_decisions.csv", "decision-makers.csv"
DECISION_COLS = ["id", "text", "by", "by_ref", "source", "date", "context", "status", "invalidated_reason",
                 "invalidated_date", "supersedes", "review_by", "links"]
MAKER_COLS = ["id", "role", "name", "source"]
# A root's storage policy for decision makers is one reserved row of its decision-makers.csv: id POLICY_ROW (no slug,
# so no maker has it) and the policy in `role`. A root with no such row has no policy, and kbdecide.py refuses its
# first decision until the operator sets one; kb/_self, the central register, holds roles only and has none.
POLICY_ROW = "_policy"
POLICIES = {
    "role-only": "the root keeps the role of a decision maker only",
    "role-and-name": "the root keeps the role and the name (an internal root only)",
    "central-register": "the root keeps no makers of its own and references the central register kb/_self/decision-makers.csv",
}
DECISION_PREFIX = "D"  # a decision id is D-<8 base32 characters> like a source id, and `D` is a reserved root prefix
DECISION_ID = re.compile(r"D-[a-z2-7]{8}")
MAKER_ID = re.compile(r"[a-z][a-z0-9-]{0,39}")  # a decision maker's id in decision-makers.csv: a short lowercase slug
DECISION_STATUS = ("proposed", "active", "invalidated", "superseded")
# What a decision's `context` may name: `;`-separated `kind:value` references to the things it is scoped to
CONTEXT_KINDS = {
    "item": re.compile(r"[A-Z]{2}-[a-z0-9]{8}"),  # a backlog item
    "fact": re.compile(r"[0-9a-f]{12}"),  # a fact's key (kbfacts.fact_key)
    "source": re.compile(r"(?:[A-Z]{1,4}-[a-z2-7]{8}|S\d+)"),  # a source id of the root
    "article": re.compile(r"[a-z0-9][a-z0-9-]*(?:/[a-z0-9][a-z0-9._-]*)+"),  # <domain>/<slug> in the root (<root>/<domain>/<slug> in kb/_self)
    "domain": re.compile(r"[a-z0-9][a-z0-9-]*(?:/[a-z0-9][a-z0-9-]*)?"),  # a domain directory of the root (<root>/<domain> in kb/_self)
}


def split_list(text):
    """The `;`-separated parts of a decision field (context, supersedes, links), trimmed, without empty parts."""
    return [p.strip() for p in (text or "").split(";") if p.strip()]


def context_refs(text):
    """[(kind, value)] of a decision's `context`; a part that names no kind of CONTEXT_KINDS has kind ''."""
    out = []
    for part in split_list(text):
        kind, sep, value = part.partition(":")
        out.append((kind.strip(), value.strip()) if sep and kind.strip() in CONTEXT_KINDS else ("", part))
    return out


def root_policy(root):
    """The storage policy for decision makers of `root` (a key of POLICIES), or '' when its decision-makers.csv sets none,
    is missing or cannot be read (check.py reports a bad file on the file itself); '' for None (kb/_self)."""
    if root is None:
        return ""
    try:
        rows = load_csv(os.path.join(root.path, DECISION_MAKERS))[1]
    except CsvError:
        return ""
    return next(((r.get("role") or "").strip() for r in rows if (r.get("id") or "").strip() == POLICY_ROW), "")


def maker_names_allowed(root, policy=None):
    """Whether a decision maker's name may be stored in `root`'s files (None: kb/_self, the central register). Only an
    internal root may: kb/_self is published, so its register holds roles only. A root whose policy keeps roles only
    or references the central register keeps no names either; one with no policy yet is bound by its visibility alone.
    `policy` is the one to ask about (default: the root's own). Every check of names asks this one function."""
    if root is None or root.visibility != "internal":
        return False
    policy = root_policy(root) if policy is None else policy
    return policy in ("", "role-and-name")


# Secret shapes: the leak scan over tracked files (test_kb_leaks.py, TestLeaks) and kbingest.py's survey of a repository.
SECRETS = (
    r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP |ENCRYPTED )?PRIVATE KEY-----",
    r"\bAKIA[0-9A-Z]{16}\b",
    r"\bgh[pousr]_[A-Za-z0-9]{36}\b", r"\bgithub_pat_[A-Za-z0-9_]{22,}\b",
    r"\bglpat-[A-Za-z0-9_-]{20,}\b", r"\bglrt-[A-Za-z0-9_-]{20,}\b",
    r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b",
    r"\bsk-ant-[A-Za-z0-9_-]{20,}\b", r"\bsk-(?:proj-)?[A-Za-z0-9]{32,}\b",
    r"AccountKey=[A-Za-z0-9+/]{40,}={0,2}", r"[?&]sig=[A-Za-z0-9%+/]{30,}",
    r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
    r"(?i)\b(?:password|passwd|pwd|client_secret|api_key|apikey|secret)\b\s*[:=]\s*[\"'][^\"'\s<>${}]{8,}[\"']",
)
# The placeholders-only shapes: what the leak scan flags in authored files (test_kb_leaks.py, TestLeaks) and what drops a
# query-log entry after redaction (redact.py). One copy, so the redactor keeps nothing the scan would flag.
LEAK_HOME = r"(?:/Users/|/home/|[A-Za-z]:\\+Users\\+)(?!<)[A-Za-z][\w.-]+"
HOME_GENERIC = ("public", "default", "all users", "username", "user", "administrator", "jan.kowalski")
LEAK_IPV4 = (r"(?<![\w.])(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}"
             r"\.\d{1,3})(?![\w.])")
LEAK_EMAIL = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b"
EMAIL_OK = re.compile(r"(?i)@([\w-]+\.)*example\.(com|org|net)$|@noreply\.|@users\.noreply\.github\.com$")
LEAK_GUID = r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
GUID_OK = re.compile(r"0{8}-0{4}-0{4}-0{4}-0{8}[0-9a-f]{4}")  # the tenant placeholder and its numbered siblings


def secrets_rx():
    """SECRETS as one pattern (one pass per text)."""
    return "|".join(f"(?i:{p[4:]})" if p.startswith("(?i)") else f"(?:{p})" for p in SECRETS)


def leak_hits(text, allow=None):
    """[(kind, value)] of the leak scan's shapes in `text`: secret, home, ip, email, guid; `allow` maps a kind to
    lowercased values that pass (the scan of tracked files reads them from _tools/tests_allowlist.txt)."""
    allow = allow or {}
    out = [("secret", m.group(0)) for m in re.finditer(secrets_rx(), text)
           if m.group(0).lower() not in allow.get("secret", ())]
    out += [("home", m.group(0)) for m in re.finditer(LEAK_HOME, text)
            if re.split(r"[/\\]+", m.group(0))[-1].lower() not in HOME_GENERIC]
    out += [("ip", m.group(0)) for m in re.finditer(LEAK_IPV4, text)
            if m.group(0) not in allow.get("ip", ()) and all(int(x) < 256 for x in m.group(0).split("."))]
    out += [("email", m.group(0)) for m in re.finditer(LEAK_EMAIL, text)
            if not EMAIL_OK.search(m.group(0)) and m.group(0).lower() not in allow.get("email", ())]
    out += [("guid", m.group(0)) for m in re.finditer(LEAK_GUID, text)
            if not GUID_OK.fullmatch(m.group(0).lower()) and m.group(0).lower() not in allow.get("guid", ())]
    return out


csv.field_size_limit(2**31 - 1)  # a very wide cell must not abort a whole read


class CsvError(Exception):
    """A kb CSV that cannot be read, or that lacks required columns; the message names the file."""


def read(rel, newline=None, strict=False):
    """The text of a kb file (path relative to the kb, or absolute), or None when it cannot be read. `newline=""`
    keeps `\\r\\n` as written. `strict`: undecodable bytes raise, and only a missing file gives None."""
    try:
        with open(os.path.join(KB, rel), encoding="utf-8", errors="strict" if strict else "replace", newline=newline) as f:
            return f.read()
    except FileNotFoundError:
        return None
    except OSError:
        if strict:
            raise
        return None


def parse_csv(name, text, required=(), nul=False):
    """(fieldnames, rows) of CSV text; a leading BOM is ignored and `nul` drops NUL characters first."""
    text = text.lstrip("﻿")
    if nul:
        text = text.replace("\0", "")
    try:
        r = csv.DictReader(io.StringIO(text))
        rows = list(r)
    except csv.Error as e:
        raise CsvError(f"cannot read {name}: {e}")
    missing = [c for c in required if c not in (r.fieldnames or [])]
    if missing:
        raise CsvError(f"{name} lacks column(s) {', '.join(missing)}")
    return r.fieldnames, rows


def load_csv(name, required=(), strict=True):
    """(fieldnames, rows) of a kb CSV file; CsvError when it is missing, undecodable (`strict`), malformed or lacks
    a required column."""
    try:
        with open(os.path.join(KB, name), encoding="utf-8-sig", errors="strict" if strict else "replace", newline="") as f:
            text = f.read()
    except (OSError, UnicodeDecodeError) as e:
        raise CsvError(f"cannot read {name}: {e}")
    return parse_csv(name, text, required)


def csv_text(header, rows):
    """Canonical CSV text of dict rows: the header, then each row's values in header order ('' when absent)."""
    buf = io.StringIO()
    w = csv.DictWriter(buf, header, lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def rows_text(rows):
    """Canonical CSV text of list rows (the first row is the header)."""
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows(rows)
    return buf.getvalue()


def write_csv(path, header, rows, atomic=False):
    """Write dict rows as canonical CSV; `atomic` writes a temporary file and renames it into place."""
    target = path + ".tmp" if atomic else path
    with open(target, "w", encoding="utf-8", newline="") as f:
        f.write(csv_text(header, rows))
    if atomic:
        os.replace(target, path)


def data_path(rel, shared=False):
    """A file of the kb's own retrieval data, `rel` under <kb>/DATA_DIR/ (signals.csv, lookup_eval.csv,
    doc2query/expansions.csv, index_extra.csv). `shared` (aliases.csv: product names, not kb content) falls back to
    this repository's copy in _tools/ when the kb has none."""
    path = os.path.join(KB, DATA_DIR, rel)
    return path if not shared or os.path.exists(path) else os.path.join(TOOLS, rel)


def data_rel(rel):
    """data_path(rel) relative to the kb root, `/`-separated (for messages, defaults and git pathspecs via repo_rel)."""
    return f"{DATA_DIR}/{rel}"


def _slash(p):
    return p.replace(os.sep, "/")


def repo_rel(rel, root=None):
    """`rel` (relative to the kb root `root`, default KB) as a `/`-separated path relative to this repository: what
    git takes as a pathspec and prints in a diff. An absolute `rel` is taken as is."""
    return _slash(os.path.relpath(os.path.join(root or KB, rel), HOME))


def kb_rel(path, root=None):
    """A repository-relative (or absolute) path relative to the kb root `root` (default KB), `/`-separated; None when
    the path lies outside that root."""
    full = os.path.normpath(os.path.join(HOME, path))
    rel = os.path.relpath(full, root or KB)
    return None if rel == ".." or rel.startswith(".." + os.sep) else _slash(rel)


def resolve(rel):
    """The absolute path of a file named relative to the kb root, else relative to this repository (the SELF docs,
    README.md): for reading and showing a path a tool printed. A path that exists in neither is taken as the kb
    root's, so the caller reports it missing. An absolute `rel` is returned as is."""
    path, repo = os.path.join(KB, rel), os.path.join(HOME, rel)
    return repo if not os.path.exists(path) and os.path.exists(repo) else path


class Root(NamedTuple):
    name: str
    path: str  # absolute
    id_prefix: str
    visibility: str  # public | internal
    description: str


class RootError(Exception):
    """A root whose ROOT_FILE is missing, malformed or clashes with another root; the message names it."""


def _meta(text):
    """`key: value` pairs of a ROOT_FILE's front matter."""
    lines = (text or "").lstrip("\ufeff").split("\n")
    if lines[:1] != ["---"] or "---" not in lines[1:]:
        return {}
    out = {}
    for ln in lines[1:lines.index("---", 1)]:
        k, sep, v = ln.partition(":")
        if sep and k.strip():
            out[k.strip()] = v.strip().strip('"')
    return out


def load_root(path):
    """The Root of a directory with a ROOT_FILE (RootError when it has none or it is malformed)."""
    path = os.path.abspath(os.path.expanduser(path))
    try:
        with open(os.path.join(path, ROOT_FILE), encoding="utf-8") as f:
            meta = _meta(f.read())
    except OSError as e:
        raise RootError(f"{path}: no readable {ROOT_FILE} ({e.strerror})")
    name, prefix = meta.get("root", ""), meta.get("id_prefix", "")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name) or name == "kb":
        raise RootError(f"{path}/{ROOT_FILE}: `root` must be a lowercase name (a-z, 0-9, -), got {name!r}")
    if not PREFIX.fullmatch(prefix) or prefix in RESERVED_PREFIXES:
        raise RootError(f"{path}/{ROOT_FILE}: `id_prefix` must be 1-4 capital letters, not one of "
                        f"{', '.join(sorted(RESERVED_PREFIXES))}; got {prefix!r}")
    vis = meta.get("visibility", "internal")
    if vis not in ("public", "internal"):
        raise RootError(f"{path}/{ROOT_FILE}: `visibility` must be public or internal, got {vis!r}")
    return Root(name, path, prefix, vis, meta.get("description", ""))


_ROOTS = []  # every root, loaded once
_SERVED = []  # serve_only's names; empty: every root


def _all_roots():
    """Every root, in order: public first, then kb/<name>/ by name, then the KB_ROOTS directories. RootError when a
    ROOT_FILE is malformed, or two roots share a name or an id prefix."""
    if _ROOTS:
        return list(_ROOTS)
    dirs = [PUBLIC] + sorted(os.path.join(KB_DIR, d) for d in os.listdir(KB_DIR) if not d.startswith((".", "_"))
                             and os.path.join(KB_DIR, d) != PUBLIC and os.path.isfile(os.path.join(KB_DIR, d, ROOT_FILE)))
    dirs += [d for d in os.environ.get("KB_ROOTS", "").split(os.pathsep) if d.strip()]
    out, names, prefixes = [], {}, {}
    for d in dirs:
        r = load_root(d)
        for seen, key, what in ((names, r.name, "name"), (prefixes, r.id_prefix, "id_prefix")):
            if key in seen:
                raise RootError(f"roots {seen[key]} and {r.path} share the {what} {key!r}")
            seen[key] = r.path
        out.append(r)
    _ROOTS[:] = out
    return list(out)


def roots():
    """The roots the tools serve, in _all_roots() order: every root, or only those serve_only() named."""
    return [r for r in _all_roots() if not _SERVED or r.name in _SERVED]


def serve_only(names):
    """Limit roots(), and every tool built on it, to the named roots for the rest of this process (a server started
    for one team's roots). RootError, naming every root, when a name is no root; an empty list serves every root."""
    names = [n.strip() for n in names if n and n.strip()]
    known = [r.name for r in _all_roots()]
    unknown = [n for n in names if n not in known]
    if unknown:
        raise RootError(f"no root {', '.join(map(repr, unknown))}; roots: {', '.join(known)}")
    _SERVED[:] = names


def serving():
    """The names serve_only() limited the roots to, () when every root is served."""
    return tuple(_SERVED)


def root(name):
    for r in roots():
        if r.name == name:
            return r
    raise KeyError(name)


def public():
    return _all_roots()[0]


def qualify(r, rel):
    """`<root name>/<rel>` (rel relative to the root r, a Root or a root name)."""
    return f"{getattr(r, 'name', r)}/{_slash(rel)}"


def split(qpath):
    """(Root, path in the root) of a qualified path `<root>/<rel>`; (None, qpath) when its first part names no root."""
    head, _, rest = _slash(qpath).partition("/")
    for r in roots():
        if r.name == head:
            return r, rest
    return None, qpath


def path_of(qpath):
    """The absolute path of a qualified path; a path whose first part names no root is taken relative to this
    repository (the SELF docs, README.md). An absolute path is returned as is."""
    if os.path.isabs(qpath):
        return qpath
    r, rel = split(qpath)
    return os.path.join(r.path, rel) if r else os.path.join(HOME, qpath)


def root_of_prefix(prefix):
    for r in roots():
        if r.id_prefix == prefix:
            return r
    return None


def read_sources():
    """The rows of _sources.csv in file order (OSError when it cannot be read)."""
    with open(os.path.join(KB, "_sources.csv"), encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def source_rows():
    """{id: row} of _sources.csv."""
    return {r["id"]: r for r in read_sources()}
