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
  source_rows()               {id: row} of _sources.csv
  data_path(rel, shared)      a file of the kb's own retrieval data under <kb>/DATA_DIR/
  repo_rel(rel)               a path relative to the kb root as a path relative to this repository (git pathspecs)
  kb_rel(path)                the inverse: a repository path (or absolute path) relative to the kb root, or None
  resolve(rel)                the absolute path of a file named relative to the kb root, else to this repository

Layout. The paths below are the only place that says where knowledge sits in this repository: the tools' code in
_tools/, the kb's own docs in SELF, and the public root PUBLIC (its articles, _sources.csv, ledgers and retrieval
data). Every path inside a root is relative to that root, so moving a root moves no line inside it.

KB_ROOT=DIR serves another kb with the same layout (articles, _sources.csv, ledgers, and its own retrieval data in
DIR/DATA_DIR/) with these tools: for a team's own facts, which never go into this repository. The read tools (rag.py,
kbfacts, kb_mcp.py, the kb: hook) and the checks (check.py, build_index.py, kbid.py) honour it; git, census and fetch
tooling always works on this repository's public root.
"""
import csv, io, os

TOOLS = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.dirname(TOOLS)  # this repository: the tools' code, the shared product aliases
KB_DIR = os.path.join(HOME, "kb")  # all knowledge: the public root, team roots and SELF
PUBLIC = os.path.normpath(os.path.join(KB_DIR, "public"))  # the public root: articles, ledgers, retrieval data
SELF = os.path.join(KB_DIR, "_self")  # the kb's own docs: rules, tool reference, design (searched with --index only)
DATA_DIR = "_retrieval"  # a root's retrieval data (signals, eval set, doc2query, index extras), relative to the root
KB = os.path.abspath(os.path.expanduser(os.environ["KB_ROOT"])) if os.environ.get("KB_ROOT") else PUBLIC
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


def read_sources():
    """The rows of _sources.csv in file order (OSError when it cannot be read)."""
    with open(os.path.join(KB, "_sources.csv"), encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def source_rows():
    """{id: row} of _sources.csv."""
    return {r["id"]: r for r in read_sources()}
