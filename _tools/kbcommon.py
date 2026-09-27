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
  data_path(rel, shared)      a file of the kb's own retrieval data under <kb>/DATA_DIR/
  repo_rel(rel)               a path relative to the kb root as a path relative to this repository (git pathspecs)
  kb_rel(path)                the inverse: a repository path (or absolute path) relative to the kb root, or None
  resolve(rel)                the absolute path of a file named relative to the kb root, else to this repository

Roots. Knowledge lives in roots: kb/public (the upstream facts) and any kb/<name>/ a team adds, each a directory
with a ROOT_FILE (`_root.md`: front matter `root`, `id_prefix`, `visibility`, `description`) and the same layout:
domain directories of articles, the ledgers (SOURCES, ANSWERS, GAPS, CONFLICTS, COVERAGE_CSV, COVERAGE_MD, STATE,
ARTIFACTS), `_census/` and DATA_DIR. Every path inside a root is relative to that root, so moving a root moves no
line inside it. Tools that span roots name a file by its qualified path `<root>/<path in root>` (`public/intune/x.md`)
and a topic by `<root>/<topic>`.

  roots()                     [Root] in order: public first, then kb/<name>/ by name, then the KB_ROOTS dirs
  root(name)                  the Root of that name (KeyError when there is none)
  public()                    the public Root
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
import csv, io, os, re
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
ANSWERS, GAPS, CONFLICTS = "_answers.md", "_gaps.md", "_conflicts.md"
COVERAGE_CSV, COVERAGE_MD = "_coverage.csv", "_coverage.md"
CENSUS_DIR = "_census"
# What a source's licence allows with its text: the `reuse` column of _sources.csv (check.py rejects anything else).
REUSE = {
    "copy": "an open licence allows a verbatim copy and redistribution, with attribution (and its other conditions)",
    "quote": "no reuse licence (terms of use, all rights reserved): paraphrase, quotes of 25 words or fewer",
    "paraphrase": "the terms forbid copying the text (CIS, ISO): paraphrase and cite ids only, no quotes",
    "unknown": "the terms could not be read or determined: treated as paraphrase",
}
PREFIX = re.compile(r"[A-Z]{1,4}")  # a root's source id prefix: its ids are <prefix>-<8 base32 chars>
RESERVED_PREFIXES = {"DOC", "CODE", "DER", "UNK", "QK", "EV", "PL"}  # tag kinds, answer and eval ids, placeholders
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


_ROOTS = []


def roots():
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


def root(name):
    for r in roots():
        if r.name == name:
            return r
    raise KeyError(name)


def public():
    return roots()[0]


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
