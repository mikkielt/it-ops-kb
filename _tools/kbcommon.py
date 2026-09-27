#!/usr/bin/env python3
"""Helpers the kb tools share (stdlib only): reading kb files, reading and writing CSV the canonical way, and the
source ledger. One copy, so every tool reads and writes these files the same way (_self/reports/plan-tooling-efficiency.md R4).

  read(rel)                   a kb file's text, or None when it cannot be read
  load_csv(name, required)    (fieldnames, rows) of a kb CSV; CsvError names the file and the problem
  parse_csv(name, text, ...)  the same for text already read
  csv_text(header, rows)      canonical CSV text of dict rows: csv-module quoting, `\\n` line ends, header first
  rows_text(rows)             the same for list rows (the header is the first row)
  write_csv(path, header, rows, atomic=False)
  read_sources()              the rows of _sources.csv, in file order
  source_rows()               {id: row} of _sources.csv
  data_path(rel, shared)      a file of the kb's own retrieval data under <kb>/_tools/

KB_ROOT=DIR serves another kb with the same layout (articles, _sources.csv, ledgers, and its own retrieval data in
DIR/_tools/) with these tools: for a team's own facts, which never go into this repository. The read tools (rag.py,
kbfacts, kb_mcp.py, the kb: hook) and the checks (check.py, build_index.py, kbid.py) honour it; git, census and fetch
tooling always works on this repository.
"""
import csv, io, os

TOOLS = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.dirname(TOOLS)  # this repository: the tools' code, the shared product aliases
KB = os.path.abspath(os.path.expanduser(os.environ["KB_ROOT"])) if os.environ.get("KB_ROOT") else HOME
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
    """A file of the kb's own retrieval data, `rel` under <kb>/_tools/ (signals.csv, lookup_eval.csv,
    doc2query/expansions.csv, index_extra.csv). `shared` (aliases.csv: product names, not kb content) falls back to
    this repository's copy when a kb given by KB_ROOT has none."""
    path = os.path.join(KB, "_tools", rel)
    return path if not shared or os.path.exists(path) else os.path.join(TOOLS, rel)


def read_sources():
    """The rows of _sources.csv in file order (OSError when it cannot be read)."""
    with open(os.path.join(KB, "_sources.csv"), encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def source_rows():
    """{id: row} of _sources.csv."""
    return {r["id"]: r for r in read_sources()}
