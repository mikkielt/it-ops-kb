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
with a ROOT_FILE (`_root.md`: front matter `root`, `id_prefix`, `visibility`, `description`, optionally `team`) and the same layout:
domain directories of articles, the ledgers (SOURCES, ANSWERS, GAPS, CONFLICTS, COVERAGE_CSV, COVERAGE_MD, STATE,
ARTIFACTS, ANCHORS), `_census/`, SNAPSHOTS and DATA_DIR. Every path inside a root is relative to that root, so moving a root moves no
line inside it. Tools that span roots name a file by its qualified path `<root>/<path in root>` (`public/intune/x.md`)
and a topic by `<root>/<topic>`.

  roots()                     [Root] in order: public first, then kb/<name>/ by name, then the KB_ROOTS dirs, then the
                              roots a pointer names that resolve (only the named ones after serve_only)
  repo_roots()                the roots() inside this repository's kb/ (not the KB_ROOTS dirs of other repositories)
  missing_roots()             [MissingRoot]: the pointers kb/_roots/<name>.md whose root is not served and the KB_ROOTS
                              directories with no ROOT_FILE, each with its reason; read_pointer(), pointer_problems()
                              read one pointer file; pointers() reads every sound one
  plugin_hosted()             whether this copy runs as the plugin (the copy is read-only: nothing is written to it)
  roots_cache_dir()           where fetch roots are cloned (kbroot.py fetch); fetch_error_path(name) holds why the
                              last fetch of one failed, which its missing reason repeats
  missing_note()              the one line `roots missing: NAME (reason), ...` ('' when none is missing);
                              with_missing_note(text) puts it after the first block of lines of a lookup's text
  serve_only(names)           limit roots() to the named roots for this process (kb_mcp.py --roots); RootError
                              names an unknown one; serving() gives the names, () when every root is served
  root(name)                  the Root of that name (KeyError when there is none)
  public()                    the public Root (whether served or not)
  qualify(root, rel)          `<root name>/<rel>`
  split(qpath)                (Root, rel) of a qualified path; (None, qpath) when its first part names no root
  path_of(qpath)              the absolute path of a qualified path (a root's file), else of a repository path
  root_of_prefix(prefix)      the Root whose id_prefix it is, or None
  private_hits(text)          [(kind, value)] of the private names of the internal roots and pointers (the leak scan's
                              `private-id`, `private-host`, `private-path` kinds; leak_hits adds them)

A remote root, one kept in another repository, is named by a pointer file kb/_roots/<name>.md (front matter `root`,
`id_prefix`, `visibility`, `team`, `url`, `ref`, `pin`, `access`, `description`). Its root is served when it is on
disk (access `submodule`: kb/<name>/; `fetch`: _cache/roots/<name>/, or ${CLAUDE_PLUGIN_DATA}/roots/<name>/ when this
copy runs as the plugin, filled by `kbroot.py fetch`) with a ROOT_FILE that agrees with the pointer;
otherwise it is listed by missing_roots() and the tools go on with the roots they have, never failing for it.

KB_ROOTS=DIR[:DIR...] adds roots kept outside this repository (a team's private repository with the same root
layout and its own ROOT_FILE): the read tools and the checks serve them with kb/'s roots; git, census and fetch work
on this repository's roots only. A directory with no readable ROOT_FILE is listed by missing_roots() under its
directory name, not raised.

Layout. The paths below are the only place that says where knowledge sits in this repository: the tools' code in
_tools/, the roots in KB_DIR, the kb's own docs in SELF. KB is the public root, the default of the tools that work on
one root.
"""
import contextlib, csv, datetime, io, os, re, sys


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
POINTERS_DIR = "_roots"  # kb/_roots/<name>.md: a pointer file for each remote root (Pointer)
ACCESS = ("submodule", "fetch")  # how a remote root is kept: a git submodule at kb/<name>/, a clone in _cache/roots/<name>/
SOURCES, STATE, ARTIFACTS = "_sources.csv", "_fetch_state.csv", "_artifacts.csv"
# _fetch_state.csv: fetch.py's columns (the text hash of --diff), then factdiff.py detect's (the provider's signals as
# last seen: validators, version id, the normalized document's hash, where the url led, its status and simhash, the
# hash of each heading section of that document)
STATE_COLS = ["id", "url", "checked_utc", "fetched_utc", "changed_utc", "sha256", "text_sha256", "bytes", "error",
              "etag", "last_modified", "version", "doc_sha256", "final_url", "http_status", "simhash", "detected_utc",
              "sections"]
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
TEAM = re.compile(r"[a-z0-9][a-z0-9-]*")  # a root's optional `team`: a lowercase name, like a root's name
PREFIX = re.compile(r"[A-Z]{1,4}")  # a root's source id prefix: its ids are <prefix>-<8 base32 chars>
RESERVED_PREFIXES = {"DOC", "CODE", "DER", "UNK", "QK", "EV", "PL", "D", "L"}  # tag kinds, answer, eval, decision and log ids, placeholders
RESERVED_FOR = {"D": "decision ids", "L": "log row ids"}  # the one-letter reserved prefixes and whose ids they are
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
    # <domain>/<slug> in the root (<root>/<domain>/<slug> in kb/_self); in kb/_self also a rule doc, `_self/<doc>`, or
    # one of its sections, `_self/<doc>#<Heading>`
    "article": re.compile(r"(?:[a-z0-9][a-z0-9-]*(?:/[a-z0-9][a-z0-9._-]*)+|_self/[a-z0-9][a-z0-9-]*(?:#[^\s#;][^#;]*)?)"),
    "domain": re.compile(r"[a-z0-9][a-z0-9-]*(?:/[a-z0-9][a-z0-9-]*)?"),  # a domain directory of the root (<root>/<domain> in kb/_self)
}


def today():
    """The UTC date, the day every stamp and log of a run names, whatever the host's time zone."""
    return datetime.datetime.now(datetime.timezone.utc).date().isoformat()


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


# Secret shapes: the leak scan over tracked files (`_tools/test_leaks.py`) and kbingest.py's survey of a repository.
# The first shape is the armor line of a private key: the RSA, OPENSSH, DSA, PGP, ENCRYPTED and plain lines on their own,
# the EC line (quoted in the secret-shapes article) and the OpenPGP block line (`PGP PRIVATE KEY BLOCK`, RFC 9580
# 6.2.1) only when key material follows it: optional `Name: value` header lines (the space after the colon is optional),
# then a run of base64 (a blank line, a newline or an escaped `\n`, `\r` or `\t` apart, however many times escaped:
# `\\n` is JSON inside a JSON string; a Markdown quote `>`, a `#`, `//`, `///` or `//!` comment prefix, a `*` or `-` list bullet (one a
# whitespace follows) or a table `|` may sit between the lines or the cells, and a space may be all there is). Key
# material is 20 base64 characters in a row with an upper-case letter, a digit or a `+` among them, the run not being
# a repository path (slash-separated segments of letters and digits, the last followed by a `.`, `_` or `-`, as in
# `kb/public/mecm/sql2022-views.md`; a segment with a lower-case letter or digit followed by an upper-case letter that no
# lower-case letter follows, or a one-letter to two-letter hump (`tEk`) after a lower-case letter, is no path piece: random
# base64 has one, a word, a `CamelCase` name or a `Win32` has not; nor is a run that starts with three capitalised words of
# three letters or more, `PrivateKeyInfoStructure`, an identifier), or three lines (or cells) of at least 8 base64 characters, each ending its line, for a body wrapped under 20
# characters (a gap before such a line may leave a `//` or `///` to the
# line, as `/` is base64, so `//8x89Kh` is a line of 8). A header value
# is free text up to the first gap (those characters, whitespace, an escaped newline, a pipe) that a header or the
# base64 run follows, never past a real newline and never into the next armor line: a pipe or `C:\new` inside it
# stays in the value. Every part is possessive, so each character has one reading and a row of
# `| Key: value` cells, a run of backslashes or a line of armor labels scans linearly. The lookahead keeps the match
# to the armor line, so a hit never prints the key; either label quoted alone in prose passes.
_GAP = r"(?:\s|\\+[nrt]|[>#|]|[*-](?=\s)|//[/!]?)++"
_GAPS = r"(?:" + _GAP + r"|(?:\s|\\+[nrt]|[>#|]|[*-](?=\s))++)"
_NEXT = r"(?:[A-Za-z][\w-]*+:|[A-Za-z0-9+/]{20}|[A-Za-z0-9+/]{8,}+\\+[nrt])"
_VALUE = (r"(?:(?!" + _GAP + _NEXT + r")(?:(?:[^\S\r\n]|\\+[nrt]|[>#|]|[*-](?=\s)|//[/!]?)++|[^\s\\|>#/-]++|\\++|/|-(?!----BEGIN )))*+")
_LINE = r"[A-Za-z0-9+/]{8,}+(?=[^\S\r\n]*+(?:[\r\n|]|\\+[nrt]|$))"
_PIECE = r"(?![A-Za-z0-9]*?(?:[a-z0-9][A-Z](?![a-z])|[a-z][A-Z][a-z]{1,2}(?![a-z])))[A-Za-z0-9]++"
_KEY = r"(?:(?!(?:[A-Z][a-z]{2,}){3})(?!(?:" + _PIECE + r"/)+" + _PIECE + r"[._-])(?=[A-Za-z0-9+/]{0,19}[A-Z0-9+])[A-Za-z0-9+/]{20}[A-Za-z0-9+/]*+|" +_LINE + r"(?:" + _GAPS + _LINE + r"){2})"
SECRETS = (
    r"-----BEGIN (?:(?:RSA |OPENSSH |DSA |PGP |ENCRYPTED )?PRIVATE KEY-----"
    r"|(?:EC PRIVATE KEY|PGP PRIVATE KEY BLOCK)-----"
    r"(?=(?:" + _GAPS + r")?(?:[A-Za-z][\w-]*+:" + _VALUE + _GAPS + r")*" + _KEY + r"))",
    r"\bAKIA[0-9A-Z]{16}\b",
    r"\bgh[pousr]_[A-Za-z0-9]{36}\b", r"\bgithub_pat_[A-Za-z0-9_]{22,}\b",
    r"\bglpat-[A-Za-z0-9_-]{20,}\b", r"\bglrt-[A-Za-z0-9_-]{20,}\b",
    r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b",
    r"\bsk-ant-[A-Za-z0-9_-]{20,}\b", r"\bsk-(?:proj-)?[A-Za-z0-9]{32,}\b",
    r"AccountKey=[A-Za-z0-9+/]{40,}={0,2}", r"[?&]sig=[A-Za-z0-9%+/]{30,}",
    r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
    r"(?i)\b(?:password|passwd|pwd|client_secret|api_key|apikey|secret)\b\s*[:=]\s*[\"'][^\"'\s<>${}]{8,}[\"']",
)
# The placeholders-only shapes: what the leak scan flags in authored files (`_tools/test_leaks.py`) and what drops a
# query-log entry after redaction (redact.py). One copy, so the redactor keeps nothing the scan would flag.
LEAK_HOME = r"(?:/Users/|/home/|[A-Za-z]:\\+Users\\+)(?!<)[A-Za-z][\w.-]+"
HOME_GENERIC = ("public", "default", "all users", "username", "user", "administrator", "admin", "jan.kowalski")
LEAK_IPV4 = (r"(?<![\w.])(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}"
             r"\.\d{1,3})(?![\w.])")
LEAK_EMAIL = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b"
EMAIL_OK = re.compile(r"(?i)@([\w-]+\.)*example\.(com|org|net)$|@users\.noreply\.github\.com$")
LEAK_GUID = r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
GUID_OK = re.compile(r"0{8}-0{4}-0{4}-0{4}-0{8}[0-9a-f]{4}")  # the tenant placeholder and its numbered siblings


# The structured shapes the query-log redactor replaces (redact.py) and the leak scan flags (leak_hits): one owner here.
# An assignment of a secret whatever the value: key=v, key: v, "key": "v", DB_PASSWORD=v, ?api_key=v, Password=v; in a
# connection string. The key is one of the names or ends in one (aws_secret_access_key, client_secret, x-api-key). The
# key may close its quote behind backslashes (JSON inside a JSON string, \"key\": \"v\") or a bracket (cfg['key'] = 'v'), a
# quoted value may hold an escaped quote ("a\"b"), and an escaped-quote value (\"v\") ends at the escaped quote whose
# backslash run is as long as the opening one; a longer run before a quote (\\\" inside \"...\") is a nested escaped quote.
# One with a nested escaped quote and no closing quote (a JSON string cut off mid-value) runs to the end of the line.
_SECRET_NAME = r"(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?key)"
ASSIGNMENT = re.compile(
    r"""(?i)((?:\[\\*["'][\w.-]*?""" + _SECRET_NAME + r"""\\*["']\]|(?<![\w.-])[\w.-]*?""" + _SECRET_NAME
    + r"""(?:\\*["'])?)[ \t]*[:=](?![=>])[ \t]*)"""
    r"""((?P<bd>\\+)"(?:[^"\\\n]|\\+(?![\\"])|(?P=bd)\\+")*(?P=bd)"|(?P<bs>\\+)'(?:[^'\\\n]|\\+(?![\\'])|(?P=bs)\\+')*(?P=bs)'"""
    r"""|"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*'"""
    r"""|(?P<bu>\\+)"(?:[^"\\\n]|\\+(?![\\"]))*(?P=bu)\\+"(?:[^"\\\n]|\\+(?![\\"])|(?P=bu)\\+")*"""
    r"""|\\*["']?[^\s&;"']+)""")
ASSIGNED_PLACEHOLDER = re.compile(r"<[^<>\s]*>|\$\{[^}\s]*\}|%\w+%|\*{3}")  # a value that is not a secret
# The credential of an Authorization header, Bearer or Basic, whatever its length or entropy; the scheme stays. The name
# and the scheme may sit behind escaped quotes or a bracket, as in ASSIGNMENT; the credential ends at a quote, escaped or not.
AUTH_HEADER = re.compile(
    r"""(?i)((?:\[\\*["']Authorization\\*["']\]|\bAuthorization(?:\\*["'])?)[ \t]*[:=][ \t]*(?:\\*["'])?(?:Bearer|Basic)[ \t]+)"""
    r"""((?:[^\s"',;\\]|\\(?!["']))+)""")
# The password of a URL's user:password@ part; the user stays.
URL_USERINFO = re.compile(r"""(\b[A-Za-z][A-Za-z0-9+.-]*://[^\s/:@"'<>]*:)([^\s/"'<>]+)(?=@)""")
# What the leak scan takes of them (`structured_secrets`): the shapes named in STRUCTURED, each only for a value, not a
# placeholder or a word. A header credential: 12 or more characters, none of `$ { } < > *`, no `...`, not an upper-case
# name (`YOUR_API_KEY`) or lower-case words joined by hyphens. A url password or an unquoted assignment value: 8 or more
# characters with a letter and a digit, none of those characters, not starting with a backtick (a code reference in
# prose). A quoted assignment value is the last SECRETS shape's. The assignment is read in prose files and item text only.
STRUCTURED = ("auth", "url")
PROSE_STRUCTURED = STRUCTURED + ("assign",)
_NOT_A_VALUE = re.compile(r"[${}<>*]|\.\.\.|\u2026")
_NAME_ONLY = re.compile(r"[A-Z]+(?:_[A-Z0-9]+)+|[a-z]+(?:[-_.][a-z]+)+")


def _plain(value, least):
    return len(value) >= least and not _NOT_A_VALUE.search(value) and not ASSIGNED_PLACEHOLDER.fullmatch(value)


def _valuelike(value):
    return _plain(value, 8) and re.search(r"[A-Za-z]", value) and re.search(r"\d", value) and value[0] != "`"


def structured_secrets(text, kinds=STRUCTURED):
    """[matched text] of the shapes named in KINDS ("auth", "url", "assign") that hold a value in `text`."""
    out = []
    if "auth" in kinds:
        out += [m.group(0) for m in AUTH_HEADER.finditer(text)
                if _plain(m.group(2), 12) and not _NAME_ONLY.fullmatch(m.group(2))]
    if "url" in kinds:
        out += [m.group(0) for m in URL_USERINFO.finditer(text) if _valuelike(m.group(2))]
    if "assign" in kinds:
        out += [m.group(0) for m in ASSIGNMENT.finditer(text)
                if m.group(2)[:1] not in "\\\"'" and _valuelike(m.group(2))]
    return out


def secrets_rx():
    """SECRETS as one pattern (one pass per text)."""
    return "|".join(f"(?i:{p[4:]})" if p.startswith("(?i)") else f"(?:{p})" for p in SECRETS)


def leak_hits(text, allow=None, kinds=STRUCTURED):
    """[(kind, value)] of the leak scan's shapes in `text`: secret, home, ip, email, guid, and the private names the
    registry knows (`private_hits`); `allow` maps a kind to lowercased values that pass (the scan of tracked files
    reads them from _tools/tests_allowlist.txt). `kinds`: the structured secret shapes read (`structured_secrets`):
    PROSE_STRUCTURED for a prose file or item text, `()` for a vendor export."""
    allow = allow or {}
    out = [("secret", m.group(0)) for m in re.finditer(secrets_rx(), text)
           if m.group(0).lower() not in allow.get("secret", ())]
    out += [("secret", v) for v in structured_secrets(text, kinds) if v.lower() not in allow.get("secret", ())]
    out += [("home", m.group(0)) for m in re.finditer(LEAK_HOME, text)
            if re.split(r"[/\\]+", m.group(0))[-1].lower() not in HOME_GENERIC
            and m.group(0).lower() not in allow.get("home", ())]
    out += [("ip", m.group(0)) for m in re.finditer(LEAK_IPV4, text)
            if m.group(0) not in allow.get("ip", ()) and all(int(x) < 256 for x in m.group(0).split("."))]
    out += [("email", m.group(0)) for m in re.finditer(LEAK_EMAIL, text)
            if not EMAIL_OK.search(m.group(0)) and m.group(0).lower() not in allow.get("email", ())]
    out += [("guid", m.group(0)) for m in re.finditer(LEAK_GUID, text)
            if not GUID_OK.fullmatch(m.group(0).lower()) and m.group(0).lower() not in allow.get("guid", ())]
    out += [h for h in private_hits(text) if h[1].lower() not in allow.get(h[0], ())]
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
    team: str = ""  # '' when the root names none


class RootError(Exception):
    """A root whose ROOT_FILE is missing, malformed or clashes with another root; the message names it."""


def _meta(text):
    """`key: value` pairs of a ROOT_FILE's front matter."""
    lines = (text or "").lstrip("\ufeff").replace("\r\n", "\n").split("\n")
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
        why = f"id_prefix {prefix!r} is reserved for {RESERVED_FOR[prefix]}: " if prefix in RESERVED_FOR else ""
        raise RootError(f"{path}/{ROOT_FILE}: {why}`id_prefix` must be 1-4 capital letters, not one of "
                        f"{', '.join(sorted(RESERVED_PREFIXES))}; got {prefix!r}")
    vis = meta.get("visibility", "internal")
    if vis not in ("public", "internal"):
        raise RootError(f"{path}/{ROOT_FILE}: `visibility` must be public or internal, got {vis!r}")
    team = meta.get("team", "")
    if team and not TEAM.fullmatch(team):
        raise RootError(f"{path}/{ROOT_FILE}: `team` must be a lowercase name (a-z, 0-9, -), got {team!r}")
    return Root(name, path, prefix, vis, meta.get("description", ""), team)


class Pointer(NamedTuple):
    """A remote root's pointer file POINTERS_DIR/<name>.md: the root's name, prefix and visibility as its own ROOT_FILE
    holds them, and where it is kept."""
    name: str
    id_prefix: str
    visibility: str
    team: str
    url: str
    ref: str  # a branch ('' follows the remote's default branch)
    pin: str  # a commit ('' follows ref)
    access: str  # one of ACCESS
    description: str
    path: str  # absolute path of the pointer file


class MissingRoot(NamedTuple):
    """A pointer whose root is not served here, and why (a pointer that cannot be read is listed too, by its file name)."""
    name: str
    id_prefix: str  # '' when the pointer holds none
    visibility: str
    access: str
    path: str  # the pointer file
    reason: str
    defect: bool  # the pointer or the root is wrong (check.py reports it), not just absent on disk


def _pointer_files():
    d = os.path.join(KB_DIR, POINTERS_DIR)
    return sorted(os.path.join(d, f) for f in os.listdir(d) if f.endswith(".md")) if os.path.isdir(d) else []


def _pointer_stem(path):
    return os.path.basename(path)[:-len(".md")]


def url_holds_credential(url):
    """Whether a repository `url` carries a secret: a `user:password@` part, or, for http and https, any `user@` part
    (a bare token is the credential). `ssh://git@host` and `git@host:path` hold none."""
    m = re.match(r"([a-z][a-z0-9+.-]*)://([^/?#]*)", url.strip(), re.I)
    if not m:
        return bool(re.match(r"[^/@\s]*:[^/@\s]*@", url.strip()))  # scp-style `user:password@host:path`
    if "@" not in m.group(2):
        return False
    userinfo = m.group(2).rsplit("@", 1)[0]
    return ":" in userinfo or (m.group(1).lower() in ("http", "https") and bool(userinfo))


def pointer_problems(path):
    """What is wrong with the pointer file at `path`, one message each ([] when it is sound; it never raises):
    unreadable, no front matter, a `root` that is not the file's name, a bad or reserved `id_prefix`, a `visibility`
    other than public or internal, a `team` that is no lowercase name, a `url` missing or holding a credential
    (url_holds_credential; the message never repeats the url), an `access` other than submodule or fetch, a `pin`
    that is no commit hash."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except (OSError, UnicodeDecodeError) as e:
        return [f"unreadable pointer ({getattr(e, 'strerror', None) or e})"]
    meta = _meta(text)
    if not meta:
        return ["malformed pointer: no front matter (`---` lines around `key: value` pairs)"]
    out, stem = [], _pointer_stem(path)
    name, prefix = meta.get("root", ""), meta.get("id_prefix", "")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name) or name == "kb":
        out.append(f"malformed pointer: `root` must be a lowercase name (a-z, 0-9, -), got {name!r}")
    elif name != stem:
        out.append(f"malformed pointer: `root` {name!r} must be the file's name {stem!r}")
    if not PREFIX.fullmatch(prefix) or prefix in RESERVED_PREFIXES:
        out.append(f"malformed pointer: `id_prefix` must be 1-4 capital letters, not one of "
                   f"{', '.join(sorted(RESERVED_PREFIXES))}; got {prefix!r}")
    vis = meta.get("visibility", "internal")
    if vis not in ("public", "internal"):
        out.append(f"malformed pointer: `visibility` must be public or internal, got {vis!r}")
    if not meta.get("url"):
        out.append("malformed pointer: `url` (the root's repository) is missing")
    elif url_holds_credential(meta["url"]):
        out.append("malformed pointer: `url` holds a credential (a user:password@ or token@ part); name the repository "
                   "without it and let git's credential helper or an ssh key supply it")
    access = meta.get("access", "")
    if access not in ACCESS:
        out.append(f"`access` must be {' or '.join(ACCESS)}, got {access!r}")
    if meta.get("team") and not TEAM.fullmatch(meta["team"]):
        out.append(f"malformed pointer: `team` must be a lowercase name (a-z, 0-9, -), got {meta['team']!r}")
    if meta.get("pin") and not re.fullmatch(r"[0-9a-f]{7,40}", meta["pin"]):
        out.append(f"malformed pointer: `pin` must be a commit hash (7-40 hex digits) or empty, got {meta['pin']!r}")
    return out


def read_pointer(path):
    """The Pointer of the file at `path`; RootError, naming the file and its problems, when it is unsound."""
    problems = pointer_problems(path)
    if problems:
        raise RootError(f"{os.path.relpath(path, HOME)}: {'; '.join(problems)}")
    with open(path, encoding="utf-8") as f:
        m = _meta(f.read())
    return Pointer(m["root"], m["id_prefix"], m.get("visibility", "internal"), m.get("team", ""), m["url"],
                   m.get("ref", ""), m.get("pin", ""), m["access"], m.get("description", ""), path)


def pointers():
    """[Pointer] of every sound pointer file, by name (an unsound one is left to check.py and missing_roots())."""
    return [read_pointer(f) for f in _pointer_files() if not pointer_problems(f)]


def plugin_hosted():
    """True when this copy runs as the plugin: CLAUDE_PLUGIN_DATA is set and CLAUDE_PLUGIN_ROOT is this copy (read-only)."""
    data, root = os.environ.get("CLAUDE_PLUGIN_DATA"), os.environ.get("CLAUDE_PLUGIN_ROOT")
    try:
        return bool(data and root and os.path.samefile(root, HOME))
    except OSError:
        return False


def roots_cache_dir():
    """Where fetch roots are cloned: ${CLAUDE_PLUGIN_DATA}/roots when this copy runs as the plugin (CLAUDE_PLUGIN_ROOT is
    this copy: the copy itself is read-only), else _cache/roots of this repository. Never under kb/."""
    if plugin_hosted():
        return os.path.join(os.environ["CLAUDE_PLUGIN_DATA"], "roots")
    return os.path.join(HOME, "_cache", "roots")


def pointer_root_dir(p):
    """Where the root of Pointer `p` is kept: a submodule at kb/<name>/, a fetched clone in roots_cache_dir()/<name>/."""
    return os.path.join(KB_DIR, p.name) if p.access == "submodule" else os.path.join(roots_cache_dir(), p.name)


def fetch_error_path(name):
    """The file that holds why the last `kbroot.py fetch` of root `name` failed (beside its clone, not inside it)."""
    return os.path.join(roots_cache_dir(), name + ".fetch-error")


def _fetch_error(name):
    """The one-line reason the last fetch of root `name` failed, '' when it did not or none was made."""
    try:
        with open(fetch_error_path(name), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def _resolve_pointer(p):
    """(Root, '', False) of a pointer whose root is on disk and agrees with it, else (None, why it is missing, whether
    that is a defect: a root that is there but unusable or disagrees, not one that is merely absent)."""
    d = pointer_root_dir(p)
    where = os.path.relpath(d, HOME).replace(os.sep, "/") if d.startswith(HOME + os.sep) else "roots/" + p.name
    if not os.path.isfile(os.path.join(d, ROOT_FILE)):
        if p.access == "submodule":
            return None, f"submodule not initialised: no {where}/{ROOT_FILE}", False
        failed = _fetch_error(p.name)
        return None, f"not fetched: no {where}/{ROOT_FILE}" + (f"; {failed}" if failed else ""), False
    try:
        r = load_root(d)
    except RootError as e:
        return None, f"the root at {where} is unusable: {str(e).replace(os.path.abspath(d), where)}", True
    diff = [f"{k} {a!r} in the root, {b!r} in the pointer" for k, a, b in
            (("name", r.name, p.name), ("id_prefix", r.id_prefix, p.id_prefix), ("visibility", r.visibility, p.visibility))
            if a != b]
    if r.team and p.team and r.team != p.team:
        diff.append(f"team {r.team!r} in the root, {p.team!r} in the pointer")
    if diff:
        return None, f"the pointer and the root at {where} disagree: {'; '.join(diff)}", True
    return r._replace(team=r.team or p.team), "", False


_ROOTS = []  # every root, loaded once
_MISSING = []  # the pointers whose roots are not served, loaded with _ROOTS
_SERVED = []  # serve_only's names; empty: every root


def _load():
    """Fill _ROOTS and _MISSING. RootError when a local root's ROOT_FILE is malformed, or two local roots share a
    name or an id prefix; a pointer never raises: its root is served when it resolves, else listed as missing."""
    if _ROOTS:
        return
    pointers, missing = [], []
    for f in _pointer_files():
        problems = pointer_problems(f)
        if problems:
            try:
                with open(f, encoding="utf-8", errors="replace") as fh:
                    meta = _meta(fh.read())
            except OSError:
                meta = {}
            missing.append(MissingRoot(_pointer_stem(f), meta.get("id_prefix", ""), meta.get("visibility", ""),
                                       meta.get("access", ""), f, "; ".join(problems), True))
        else:
            pointers.append(read_pointer(f))
    claimed = {p.name for p in pointers if p.access == "submodule"}  # their kb/<name>/ is the pointer's, not a local root
    dirs = [PUBLIC] + sorted(os.path.join(KB_DIR, d) for d in os.listdir(KB_DIR) if not d.startswith((".", "_"))
                             and os.path.join(KB_DIR, d) != PUBLIC and d not in claimed
                             and os.path.isfile(os.path.join(KB_DIR, d, ROOT_FILE)))
    dirs += [d for d in os.environ.get("KB_ROOTS", "").split(os.pathsep) if d.strip()]
    out, names, prefixes, holder = [], {}, {}, {}  # holder: the root name that holds a name or prefix
    for d in dirs:
        if not os.path.isfile(os.path.join(os.path.abspath(os.path.expanduser(d)), ROOT_FILE)):
            missing.append(MissingRoot(os.path.basename(os.path.normpath(d)) or d, "", "", "KB_ROOTS", os.path.abspath(os.path.expanduser(d)),
                                       f"no readable {ROOT_FILE} in the KB_ROOTS directory", False))
            continue
        r = load_root(d)
        for seen, key, what in ((names, r.name, "name"), (prefixes, r.id_prefix, "id_prefix")):
            if key in seen:
                raise RootError(f"roots {seen[key]} and {r.path} share the {what} {key!r}")
            seen[key] = r.path
            holder[what, key] = r.name
        out.append(r)
    for p in pointers:  # an earlier root or pointer keeps a name or prefix, resolved or not
        clash = [f"{what} {key!r} is already the {what} of root {holder[what, key]}"
                 for seen, key, what in ((names, p.name, "name"), (prefixes, p.id_prefix, "id_prefix")) if key in seen]
        if clash:
            missing.append(MissingRoot(p.name, p.id_prefix, p.visibility, p.access, p.path, "; ".join(clash), True))
            continue
        names[p.name] = prefixes[p.id_prefix] = p.path
        holder["name", p.name] = holder["id_prefix", p.id_prefix] = p.name
        r, reason, defect = _resolve_pointer(p)
        if r is None:
            missing.append(MissingRoot(p.name, p.id_prefix, p.visibility, p.access, p.path, reason, defect))
        else:
            out.append(r)
    _MISSING[:] = sorted(missing, key=lambda m: m.name)
    _ROOTS[:] = out


def _all_roots():
    """Every root served, in order: public first, then kb/<name>/ by name, then the KB_ROOTS directories, then the roots
    pointers name (kb/_roots/<name>.md) that are on disk and agree with their pointer, by name."""
    _load()
    return list(_ROOTS)


def missing_roots():
    """[MissingRoot] by name: the pointers whose roots are not served (not fetched, submodule not initialised, the
    pointer and the root disagree, the name or prefix taken by another root or pointer, the pointer unsound) and the
    KB_ROOTS directories with no readable ROOT_FILE; only the named ones after serve_only."""
    _load()
    return [m for m in _MISSING if not _SERVED or m.name in _SERVED]


def missing_note():
    """`roots missing: NAME (reason), ...` for the roots a lookup could not read, '' when every root resolves. The
    reasons name no absolute path, so a server limited to named roots may print it."""
    return "roots missing: " + ", ".join(f"{m.name} ({m.reason})" for m in missing_roots()) if missing_roots() else ""


def with_missing_note(text):
    """`text` of a lookup with the missing_note() line after its first block of lines (a pack's verdict lines), else at
    its end; `text` unchanged when no root is missing."""
    note = missing_note()
    if not note:
        return text
    head, sep, rest = text.partition("\n\n")
    return f"{head}\n{note}{sep}{rest}" if sep else f"{text}\n{note}"


def roots():
    """The roots the tools serve, in _all_roots() order: every root, or only those serve_only() named."""
    return [r for r in _all_roots() if not _SERVED or r.name in _SERVED]


def repo_roots():
    """The roots inside this repository's kb/ (KB_ROOTS roots live in other repositories): what fix, sync, fetch and the
    trailers work on, public first."""
    kbd = os.path.realpath(KB_DIR)
    return [r for r in roots() if os.path.dirname(os.path.realpath(r.path)) == kbd]


def serve_only(names):
    """Limit roots(), and every tool built on it, to the named roots for the rest of this process (a server started
    for one team's roots). RootError, naming every root, when a name is no root; an empty list serves every root."""
    names = [n.strip() for n in names if n and n.strip()]
    known = [r.name for r in _all_roots()] + [m.name for m in missing_roots()]
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


SHARED_HOST = re.compile(r"(?i)(?:^|\.)(?:example\.(?:com|org|net)|localhost|github\.com|gitlab\.com|bitbucket\.org|dev\.azure\.com)$")
_PRIVATE = {}  # the compiled private-name patterns, keyed by the registry they were built from


def _url_host_path(url):
    """(host, path) of a pointer's `url`: `scheme://[user@]host[:port]/path`, `[user@]host:path` or a local path (no host)."""
    m = re.fullmatch(r"[a-z][a-z0-9+.-]*://(?:[^/@]*@)?([^/:]*)(?::\d+)?(/.*)?", url, re.I)
    if not m:
        m = re.fullmatch(r"(?:[^/@:]+@)?([A-Za-z0-9.-]+):(?!//)(.*)", url)
    host, path = (m.group(1), m.group(2) or "") if m else ("", url)
    return host, re.sub(r"\.git$", "", path.strip("/"))


def _raw_internal_roots():
    """{(name, id_prefix)} of the internal roots read straight from their ROOT_FILE front matter, with no registry:
    every kb/<name>/ and KB_ROOTS directory that has one. A file that cannot be read is skipped; a malformed value is
    taken as written when it is a root name or prefix, so a registry that does not load still hides these names."""
    dirs = [os.path.join(KB_DIR, d) for d in os.listdir(KB_DIR) if not d.startswith((".", "_"))]
    dirs += [os.path.abspath(os.path.expanduser(d)) for d in os.environ.get("KB_ROOTS", "").split(os.pathsep) if d.strip()]
    out = set()
    for d in dirs:
        try:
            with open(os.path.join(d, ROOT_FILE), encoding="utf-8", errors="replace") as fh:
                meta = _meta(fh.read())
        except OSError:
            continue
        if meta.get("visibility", "internal") == "public":
            continue
        name, prefix = meta.get("root", ""), meta.get("id_prefix", "")
        out.add((name if re.fullmatch(r"[a-z0-9][a-z0-9-]*", name) and name != "kb" else "",
                 prefix if PREFIX.fullmatch(prefix) and prefix not in RESERVED_PREFIXES else ""))
    return out


_FROZEN = []  # [patterns] while private_patterns_frozen() is active


@contextlib.contextmanager
def private_patterns_frozen():
    """Within the block, `private_hits` reads the registry and the pointer files once instead of on every text: a
    scan of many texts that cannot change them (the query log store check) skips the directory stats per text."""
    if _FROZEN:
        yield
        return
    _FROZEN.append(_private_patterns())
    try:
        yield
    finally:
        _FROZEN.clear()


def _private_patterns():
    """[(kind, compiled pattern)] for the internal roots and pointers the registry holds (served, missing or unsound):
    their source ids by prefix, the hosts and paths of their pointers' urls, and their qualified paths. A registry
    that does not load (RootError: two roots share a prefix) is replaced by the roots' ROOT_FILEs read directly, so
    the scan never passes a name for want of a registry; none of it raises."""
    if _FROZEN:
        return _FROZEN[0]
    internal = set()
    try:
        _load()
        internal = {(r.name, r.id_prefix) for r in _ROOTS if r.visibility != "public"}
        internal |= {(m.name, m.id_prefix) for m in _MISSING if m.visibility != "public"}
    except (RootError, OSError):
        try:
            internal = _raw_internal_roots()
        except OSError:
            pass
    files, urls = (), []
    try:
        files = tuple((f, os.stat(f).st_mtime_ns) for f in _pointer_files())
    except OSError:
        pass
    for f, _ in files:
        try:
            with open(f, encoding="utf-8", errors="replace") as fh:
                meta = _meta(fh.read())
        except OSError:
            continue
        if meta.get("visibility", "internal") != "public":
            internal.add((_pointer_stem(f), meta.get("id_prefix", "")))
            urls.append(meta.get("url", ""))
    key = (frozenset(internal), tuple(urls), files)
    if key not in _PRIVATE:
        names = sorted({n for n, _ in internal if n}, key=lambda n: (-len(n), n))
        prefixes = sorted({p for _, p in internal if p})
        hosts, paths = set(), set()
        for host, path in map(_url_host_path, filter(None, urls)):
            if host and not SHARED_HOST.search(host):
                hosts.add(host)
            if path.count("/") >= 1 and all(path.split("/")):
                paths.add(path)
        out = []
        if prefixes:
            out.append(("private-id", re.compile(r"(?<![\w-])(?:%s)-[a-z2-7]{8}(?![\w-])" % "|".join(map(re.escape, prefixes)))))
        if hosts:
            out.append(("private-host", re.compile(r"(?i)(?<![\w.-])(?:%s)(?![\w-])" % "|".join(map(re.escape, sorted(hosts))))))
        if paths:
            out.append(("private-path", re.compile(r"(?<![\w.-])(?:%s)(?![\w-])" % "|".join(map(re.escape, sorted(paths))))))
        if names:
            out.append(("private-path", re.compile(r"(?:(?<![\w./-])|(?<=\bkb/))(?:%s)(?:/\w[\w.-]*)+" % "|".join(map(re.escape, names)))))
        _PRIVATE[key] = out
    return _PRIVATE[key]


def private_hits(text):
    """[(kind, value)] of the private names the registry knows, in `text`: `private-id` (a source id with an internal
    root's prefix), `private-host` (the host of an internal pointer's url, unless it is a placeholder or a public git
    host), `private-path` (the path of such a url, or a qualified path `<internal root>/<domain>/...`). A bare root or
    team name, a shared root's id or path and a placeholder host pass."""
    return [(kind, m.group(0).rstrip(".-")) for kind, rx in _private_patterns() for m in rx.finditer(text)]


def read_sources():
    """The rows of _sources.csv in file order (OSError when it cannot be read)."""
    with open(os.path.join(KB, "_sources.csv"), encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def source_rows():
    """{id: row} of _sources.csv."""
    return {r["id"]: r for r in read_sources()}
