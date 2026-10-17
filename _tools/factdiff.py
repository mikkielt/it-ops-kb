#!/usr/bin/env python3
"""Fact diff: turn "a source changed" into "these facts still hold, these changed, these are gone" (stdlib only).

  factdiff.py [--root NAME] anchor [SELECTION] [--refetch] [--max-age DAYS] [--dry-run] [--quotes CSV | --propose]
      locate each fact's backing sentence in the current text of its sources and write its anchor; --quotes CSV
      (header `line,quote` or `line,source,quote`; needs one --file F) gives the quote each new fact of F rests on, at
      most QUOTE_WORDS words, by the fact's line, and in the three-column form by the one cited source the quote is
      from (a fact that cites several pages needs a quote of each; a row with no source serves every source it
      cites): the anchor is the passage that holds the quote word for word (case, markup, quotes and punctuation
      apart), and a fact whose quote the page lacks is anchored by its own words as any other; --propose (needs one
      --file F, no --quotes) prints a `line,source,quote` line for each fact of F that holds no located anchor and
      each page it cites: the words of that page that best hold the fact, a header first, and writes nothing;
      --file takes a path in the root, `<root>/<path>` or `kb/<root>/<path>`;
      with --file and no other selector only the facts of those files that hold no anchor row (a new or reworded
      fact), whose row is unlocated:fetch-error, not-text or gone (its source fetched again, past the cache) and the
      lines the quote CSV names are anchored, the rows of other facts and files are kept and _fetch_state.csv is not
      written
  factdiff.py [--root NAME] snapshot [SELECTION] [--refetch] [--max-age DAYS] [--dry-run]
      write the normalized text of the root's live copy sources, with attribution, to <root>/_snapshots/<id>.txt
  factdiff.py [--root NAME] calibrate history --repo DIR [--path P] [--since D] [--pairs N] | soft404 [--hosts N]
      measure the cut-offs of _tools/factdiff.toml on real history (consecutive page versions in a documentation
      repository) or on live hosts (made-up sibling urls); prints JSON with the suggested cut and its accuracy
  factdiff.py [--root NAME] anchors [--unlocated] [--stale] [--breakdown] [--source ID]
      list anchors: counts by status, the unlocated facts, the anchors whose fact text is gone (exit 1 when any), or
      the no-match and located pairs by provider host and tag kind

SELECTION is fetch.py's: --topic T, --dir D, --file F, --source ID (repeatable, a union); none = every source.

Anchors. <root>/_anchors.csv holds one row per (fact, file, source id) that a fact's tag cites (DOC, CODE, DER and
COMMUNITY parts; UNK cites nothing):
  fact         kbfacts.fact_key of the fact text (12 hex; the doc2query key: rewording a fact orphans its anchor)
  path         the file of the fact, relative to the root
  source_id    the cited source
  status       located | unlocated:<reason> (fetch-error, not-text, no-match, gone)
  heading      the heading path above the backing sentence in the source (` > `-joined): a ranking hint, never a
               constraint when matching
  terms        the fact's key terms found in that sentence, rarest first (`;`-joined stems, at most TERMS)
  sha          sha256 of the normalized backing passage (1 to SPAN consecutive units), 16 hex (norm(): case,
               markup, quotes, spacing)
  quote        the backing passage's first QUOTE_WORDS words, only when the source's reuse class is copy or quote
  verified_utc when the anchor was last found (YYYY-MM-DD)
check.py enforces the format. Anchoring is deterministic: the source's document (provider.document: the provider's raw
form, normalized) is split into units (sentences, list items, table rows, code lines) under their headings; the unit
window of 1 to SPAN consecutive units whose terms cover the most of the fact's terms, weighted by rarity in that
document (WINDOW_COST less per extra unit, half when the fact's number is on the page but not in the window), is the
backing passage when it covers at least MIN_COVER of the weight and holds at least MIN_SHARED terms. Otherwise the fact is listed as unlocated, never guessed.

Cache: documents fetched here are kept in _cache/factdiff/<root>/<id>.json (never committed) and reused for
--max-age days (default 7); --refetch ignores them. census.py confirm takes a source's detection baseline from
such a document when the source holds none.

Sections. A page whose only signal is the text hash is compared per heading section: `_fetch_state.csv` keeps in
`sections` the hash of each section's normalized units (`sections()`), beside doc_sha256 and bound to it. detect
reads a located fact whose passage lies in sections that all hash the same as at the baseline as `verbatim` with the
row signal `section`, and resolves only the facts of edited sections; the sections are those of every unit of the
passage's window (a window that starts at a heading line spans its parent's section and its own), else the anchor's
`heading` section and those below it; the source's evidence counts the sections.

detect, apply and review (apply --dry-run: no row) each append one ops row `census.phase` to the query log (phase, date,
ms, exit and the counts per verdict, fact outcome or review outcome; kb/_self/querylog.md): the census's own phases write
the same.

  factdiff.py [--root NAME] review LOG [--source ID] [--json] [--judge [--model M] [--batch-size N] [--max-budget-usd USD] [--dry-run]]
      --judge sends the review items that have a new passage, in batches, to one model call each with no tools
      (`claude -p --output-format json --json-schema`, `--max-budget-usd`; the judge's constants are JUDGE_*): per item
      supported, contradicted or not enough information with the sentence of the new passage that decides it; a
      `supported` whose sentence is not in the new passage is not believed. The calls' total_cost_usd and tokens go to
      the review row; --dry-run prints the batches and the estimated tokens and USD and calls nothing.
      `census.py judge` applies it to a census log's queue and confirms a source whose every fact is supported.
Exit: 0 ok; 1 anchors --stale found stale anchors; 2 bad arguments.
"""
import argparse, collections, concurrent.futures as cf, csv, datetime, hashlib, json, math, os, re, shutil, subprocess, sys, tempfile
import threading, time, unicodedata, urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kbcommon, kbfacts, kbid, kbusage, provider, ql_capture  # noqa: E402

ANCHORS, COLS, REASONS, QUOTE_WORDS = kbcommon.ANCHORS, kbcommon.ANCHOR_COLS, kbcommon.ANCHOR_REASONS, kbcommon.QUOTE_WORDS
CACHE = os.path.join(kbcommon.HOME, "_cache", "factdiff")
TERMS = 8
PROPOSE_SHARED = 2  # anchor --propose offers a window below the anchoring cut only when it shares this many of the fact's terms
QUOTE_MIN_WORDS = 3  # a given quote shorter than this holds too little to locate a passage by
CONFIG =os.path.join(kbcommon.TOOLS, "factdiff.toml")  # the calibrated cut-offs (kb/_self/reports/fact-diff.md)


def _config():
    import tomllib
    try:
        with open(CONFIG, "rb") as f:
            return tomllib.load(f)
    except OSError:
        return {}


_CFG = _config()
MIN_COVER = _CFG.get("anchor", {}).get("min_cover", 0.4)  # share of the fact's term weight the passage must hold
MIN_SHARED = _CFG.get("anchor", {}).get("min_shared", 3)  # and at least this many of its terms
SPAN = _CFG.get("anchor", {}).get("span", 3)  # a backing passage is 1 to SPAN consecutive units
WINDOW_COST = _CFG.get("anchor", {}).get("window_cost", 0.05)  # cover an extra unit of the window must earn
ROW_DENSITY = _CFG.get("anchor", {}).get("row_min_density", 0.35)  # second look at a data row: the window's own weight
ROW_IDENTITY = _CFG.get("anchor", {}).get("row_min_identity", 0.75)  # ... and the share of its first cells' terms found
MODIFIED_MIN = _CFG.get("resolve", {}).get("modified_min", 0.6)  # unit_sim: an edited passage, below: not found
SOFT404_MIN = _CFG.get("dead", {}).get("soft404_min", 0.8)  # jaccard to a made-up sibling url's page: a soft 404
ZOMBIE_MAX = _CFG.get("dead", {}).get("zombie_max", 0.6)  # simhash_sim to the previous version: replaced content
ROOT = None  # kbcommon.Root under work


def today():
    """The UTC date, the day every `checked_utc` stamp of a run names, whatever the host's time zone."""
    return kbcommon.today()


# ---------------------------------------------------------------- text units

QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "\xa0": " "})
SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9`\"'(\[])")
LIST = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")


def norm(s):
    """The normalized form of a unit: NFKC, straight quotes, no Markdown emphasis or code marks, lower case, single
    spaces, no trailing punctuation. Two texts that differ only in these are the same sentence."""
    s = unicodedata.normalize("NFKC", s).translate(QUOTES)
    s = re.sub(r"[*_`~]+", "", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s.rstrip(" .:;,")


def sha(s):
    return hashlib.sha256(norm(s).encode()).hexdigest()[:16]


def words_key(s):
    """The words of a text in the form two spellings of one sentence share: norm()'s, then word characters only."""
    return " ".join(re.findall(r"\w+", norm(s)))


def scan(text):
    """[(heading path, unit text, own path)] of a document text: sentences of prose lines, list items, table rows (cells
    joined by ` | `), code lines; heading lines set the path and are units too. The own path of a heading line is the
    path of the section it opens; None for any other unit."""
    out, path, fenced = [], [], False
    for ln in (text or "").splitlines():
        s = ln.strip()
        if s.startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if not s:
            continue
        if fenced:
            out.append((" > ".join(path), s, None))
            continue
        m = re.match(r"^(#{1,6})\s+(.*)", s)
        if m:
            level, title = len(m.group(1)), m.group(2).strip("# ").strip()
            path = path[:level - 1] + [title]
            out.append((" > ".join(path[:-1]), title, " > ".join(path)))
            continue
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) or not c for c in cells):
                continue
            out.append((" > ".join(path), " | ".join(cells), None))
            continue
        if re.match(r"<(?:img|source|video|picture|iframe)\b", s, re.I):
            continue  # an embedded image or video is markup, not a statement
        s = LIST.sub("", s).lstrip("> ").strip()
        for part in SENT.split(s):
            if part.strip():
                out.append((" > ".join(path), part.strip(), None))
    return out


def units(text):
    """[(heading path, unit text)] of a document text (scan without the own paths)."""
    return [(p, u) for p, u, _ in scan(text)]


NUM = re.compile(r"(?<![\w.])\d[\d,.]*\d(?![\w])|(?<![\w.])\d(?![\w.])")


def numbers(text):
    return {n.replace(",", "") for n in NUM.findall(text) if len(n.replace(",", "")) > 1}


ROW_CELL = re.compile(r"[A-Za-z_]\w*=")
ROW_SPLIT = re.compile(r";\s+(?=[A-Za-z_]\w*=)")


def row_parts(text):
    """(values, identity) of a data-row fact, `column=value; column=value` as kbfacts.csv_units writes a CSV row: the
    cells' values without their column names, source columns and source ids (none of them is page text), and the first
    two cells' values, which name what the row is about. None for any other fact."""
    cells = ROW_SPLIT.split(text)
    if len(cells) < 3 or not all(ROW_CELL.match(c) for c in cells):
        return None
    pairs = [c.split("=", 1) for c in cells]
    values = " ; ".join(kbid.SOURCE_ID.sub(" ", v) for k, v in pairs if "source" not in k.lower())
    return values, kbid.SOURCE_ID.sub(" ", " ; ".join(v for _, v in pairs[:2]))


def fact_text(text):
    """A fact's claim: its text without tags, `SNIPPET:` framing and the `context:`/`checked:` notes."""
    t = kbfacts.TAG.sub(" ", text)
    t = re.sub(r"^SNIPPET:\s*", "", t.strip())
    t = re.sub(r";\s*(?:context|checked):.*$", "", t)
    return " ".join(t.split())


def term_set(text):
    return {t for t in kbfacts.terms(text) if len(t) > 2 and not t.isdigit()}


SECTION_KEY = 8  # hex digits of a heading path's key
SECTION_HASH = 12  # ... and of its section's content hash (also the share of the document hash that binds a stored set to it)
SECTION_SIGNAL = "section"  # the signal of a fact row whose section hashes the same as at the baseline


def section_key(heading):
    """The key of a heading path, cut at 200 characters as an anchor row's `heading` column is."""
    return hashlib.sha256(norm(heading[:200]).encode()).hexdigest()[:SECTION_KEY]


def sections(text):
    """{section key: hash} of a document text: the units under one heading path, hashed in order (a heading line's own
    unit sits under its parent's path), so an edit changes the hash of its section only; the units are normalized, so
    a change of markup or case moves none."""
    grouped = collections.defaultdict(list)
    for path, unit in units(text):
        grouped[section_key(path)].append(norm(unit))
    return {k: hashlib.sha256("\n".join(us).encode()).hexdigest()[:SECTION_HASH] for k, us in grouped.items()}


def sections_column(text, doc_sha):
    """The `sections` value of a _fetch_state.csv row: the first digits of the document hash it belongs to, then each
    section's `key:hash`, `;`-separated. The hash prefix binds the set to its text: a merge that takes the row's other
    columns from another detection leaves a set that stored_sections ignores."""
    return ";".join([(doc_sha or "")[:SECTION_HASH]] + [f"{k}:{h}" for k, h in sorted(sections(text or "").items())])


def stored_sections(st, prev):
    """{key: hash} of the text a state row's doc_sha256 hashes: the row's `sections` value when it names that hash,
    else those of `prev`, the cached document of the previous fetch, when its text hashes to doc_sha256; {} when
    neither (a baseline taken before sections were kept, with its cached text gone)."""
    want = st.get("doc_sha256") or ""
    if not want:
        return {}
    head, _, rest = (st.get("sections") or "").partition(";")
    if rest and head == want[:SECTION_HASH]:
        return dict(p.split(":", 1) for p in rest.split(";") if ":" in p)
    if prev and prev.get("text") and hashlib.sha256(prev["text"].encode()).hexdigest() == want:
        return sections(prev["text"])
    return {}


def section_counts(old, new):
    """(changed, unchanged) sections of two sets: a section only one holds counts as changed."""
    keys = set(old) | set(new)
    same = sum(1 for k in keys if k in old and k in new and old[k] == new[k])
    return len(keys) - same, same


def _ancestor(path, head):
    """Whether `path` is a proper ancestor of the heading path `head` (the root path '' included)."""
    return bool(head) and (not path or head.startswith(path + " > "))


def window_sections(anchor, doc, prev):
    """(required, optional): the keys of the sections that hold an anchor's passage, for section_unchanged. A heading
    line's own unit sits under its parent's path, whose section hashes every sibling heading of the page, so a heading
    line stands for the section it opens (its parent's when that section is empty), never its parent's: a heading added,
    renamed or removed elsewhere moves none of them, and an edit to the line itself moves the section it opens. With
    the previous text holding the passage, the window is known: the sections of its units (required), and its
    `heading` section unless the window starts at a heading line, where that is the parent's. Else (an anchor placed on
    an earlier text) the window is not: the `heading` section is required only where it holds a body unit (a window can
    start there), and optional are every section below it in the current text and those of the SPAN - 1 units that
    follow a unit of that path, which holds any section the window can enter (a window that runs from a body into the
    next heading and its body); a following unit under an ancestor of that path is a sibling's heading line or the
    parent's body, left out, as the section of the sibling's body that the window then enters names the sibling by its
    heading."""
    head = (anchor or {}).get("heading") or ""
    if prev is not None and anchor.get("sha") in prev.shas:
        i, k = prev.shas[anchor["sha"]]
        have = {section_key(p) for p, _ in prev.units}
        req = {_unit_key(prev.units[j][0], prev.own[j], have) for j in range(i, i + k)}
        return req if prev.own[i] is not None else req | {section_key(head)}, set()
    us = doc.units if doc is not None else []
    own = doc.own if doc is not None else []
    have = {section_key(p) for p, _ in us}
    req = {section_key(head)}
    opt = set()
    for i, (p, _) in enumerate(us):
        if not head or p[:200] == head or p[:200].startswith(head + " > "):
            opt.add(_unit_key(p, own[i], have))
        if p[:200] == head:
            opt.update(_unit_key(q, own[j], have) for j, (q, _) in enumerate(us[i + 1:i + SPAN], i + 1)
                       if not _ancestor(q[:200], head))
    if section_key(head) in have and all(own[i] is not None for i, (p, _) in enumerate(us) if p[:200] == head):
        req = set()  # the section holds heading lines only: a window there starts at one of them
    return req, opt - req


def _unit_key(path, own, have):
    """The section key of a unit: for a heading line the section it opens, when that holds any unit (`have` the keys
    of the sections that do), else the unit's own path as for any other unit."""
    return section_key(own) if own is not None and section_key(own) in have else section_key(path)


def section_unchanged(keys, old, new):
    """Whether the sections of `keys` (window_sections) hash the same in both sets: every required one, and every
    optional one the baseline has (a section the baseline lacks is a new one, which no passage of the baseline sat in),
    with a baseline section among them when none is required."""
    req, opt = keys
    known = {k for k in opt if k in old}
    return bool(req or known) and all(k in old and old[k] == new.get(k) for k in req | known)


class Doc:
    """A source document split into units, with term rarity (idf) over its units and the hashes of every window of
    1 to SPAN consecutive units (a fact often condenses two or three sentences)."""

    def __init__(self, text):
        scanned = scan(text)
        self.units = [(p, u) for p, u, _ in scanned]
        self.own = [o for _, _, o in scanned]
        self.terms = [term_set(u) for _, u in self.units]
        df = collections.Counter(t for ts in self.terms for t in ts)
        n = len(self.units) or 1
        self.idf = {t: math.log((n + 1) / (c + 0.5)) for t, c in df.items()}
        self.shas = {}
        for i in range(len(self.units)):
            for k in range(1, SPAN + 1):
                if i + k <= len(self.units):
                    self.shas.setdefault(sha(self.window(i, k)), (i, k))
        self.nums = numbers(text or "")
        self.words = None  # words_key of each unit, made on the first locate_quote

    def window(self, i, k):
        return " ".join(u for _, u in self.units[i:i + k])

    def score(self, fact, unknown=0.5):
        """(best window (i, k) or None, cover, anchor unit cover, shared terms rarest first). `unknown` is the weight of a
        fact term the page lacks entirely."""
        want = term_set(fact)
        known = {t for t in want if t in self.idf}
        if not known:
            return None, 0.0, 0.0, []
        w = {t: self.idf[t] for t in known}
        total = sum(w.values()) + unknown * len(want - known)  # a fact term the page lacks entirely still counts against
        nums = numbers(fact) & self.nums
        best = (None, 0.0, 0.0, [])
        for i, ts in enumerate(self.terms):
            if not (known & ts):
                continue
            shared = set()
            for k in range(1, SPAN + 1):
                if i + k > len(self.units):
                    break
                shared |= known & self.terms[i + k - 1]
                cover = sum(w[t] for t in shared) / total
                if nums and not any(numbers(u) & nums for _, u in self.units[i:i + k]):
                    cover *= 0.5  # the fact's number is on the page but not in this window
                if k > 1:
                    cover -= WINDOW_COST * (k - 1)  # a longer window must earn its extra sentences
                if cover > best[1] + 1e-9:
                    own = sum(w[t] for t in known & ts) / total
                    best = ((i, k), cover, own, sorted(shared, key=lambda t: (-w[t], t)))
        return best

    def density(self, win, shared):
        """The share of the window's term weight that the fact's shared terms hold: a long blob of unrelated sentences
        (a package feed, a JSON listing) holds any fact's terms and a small share of its own."""
        held = set().union(*self.terms[win[0]:win[0] + win[1]])
        return sum(self.idf[t] for t in shared) / (sum(self.idf[t] for t in held) or 1.0)

    def locate_quote(self, quote):
        """The window (i, k) of 1 to SPAN consecutive units that holds the quote's words in a row (words_key: case,
        markup, quotes and punctuation apart), the shortest and then the first; None when no window does, or the
        quote is shorter than QUOTE_MIN_WORDS words."""
        want = words_key(quote)
        if len(want.split()) < QUOTE_MIN_WORDS:
            return None
        if self.words is None:
            self.words = [words_key(u) for _, u in self.units]
        want = f" {want} "
        for k in range(1, SPAN + 1):
            for i in range(len(self.units) - k + 1):
                if want in f" {' '.join(self.words[i:i + k])} ":
                    return i, k
        return None

    def locate(self, fact, cites=1):
        """(window (i, k), cover, shared terms) of the fact's backing passage, or (None, cover, shared) below the cut.
        A data row the cut leaves unlocated gets a second look, since its column names and source ids are not page text
        and its page may back only some of its cells (`cites`, the sources the row cites: a term the page lacks counts
        1/cites): scored on its values alone, accepted where the window is dense in the row's terms and holds its first
        two cells' terms."""
        win, cover, own, shared = self.score(fact)
        need = min(MIN_SHARED, max(2, len(term_set(fact) & set(self.idf))))
        if win is not None and cover >= MIN_COVER and len(shared) >= need:
            return win, cover, shared
        row = row_parts(fact)
        if row is None:
            return None, cover, shared
        win2, cover2, _, shared2 = self.score(row[0], 0.5 / max(1, cites))
        need2 = min(MIN_SHARED, max(2, len(term_set(row[0]) & set(self.idf))))
        if win2 is None or cover2 < MIN_COVER or len(shared2) < need2 or self.density(win2, shared2) < ROW_DENSITY:
            return None, cover, shared
        ident = term_set(row[1])
        seen = set().union(*self.terms[win2[0]:win2[0] + win2[1]]) | term_set(self.units[win2[0]][0])
        if ident and len(ident & seen) < ROW_IDENTITY * len(ident):
            return None, cover, shared
        return win2, cover2, shared2


# ---------------------------------------------------------------- similarity

def shingles(text, n=3):
    words = norm(text).split()
    return {" ".join(words[i:i + n]) for i in range(max(1, len(words) - n + 1))} if words else set()


def jaccard(a, b):
    """Jaccard similarity of two texts' 3-word shingle sets (1.0 for two empty texts)."""
    x, y = shingles(a), shingles(b)
    return len(x & y) / len(x | y) if x | y else 1.0


def simhash(text):
    """Charikar's 64-bit simhash over 3-word shingles, as 16 hex digits (stored per source to compare versions)."""
    v = [0] * 64
    for sh in shingles(text):
        h = int(hashlib.sha1(sh.encode()).hexdigest()[:16], 16)
        for b in range(64):
            v[b] += 1 if h >> b & 1 else -1
    return f"{sum(1 << b for b in range(64) if v[b] > 0):016x}"


def simhash_sim(a, b):
    """1 - Hamming distance / 64 of two simhash values (hex)."""
    return 1 - bin(int(a, 16) ^ int(b, 16)).count("1") / 64


def unit_sim(a, b):
    """Similarity of two units: difflib's ratio of their normalized text."""
    import difflib
    return difflib.SequenceMatcher(None, norm(a), norm(b), autojunk=False).ratio()


# a quote is vendor text in a public file: one that looks like an address, a home path, a token or a private network
# is left out (the anchor keeps its sha and terms), as the leak tests require of every authored file
LEAKY = re.compile(r"[\w.%+-]+@[\w-]+\.[\w.-]+|(?:/Users/|/home/|[A-Za-z]:\\+Users\\+)\w|[?&]sig=|\b(?:password|secret|"
                   r"api_?key|pwd)\b\s*[:=]|(?<![\w.])(?:10|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d+\.\d+|"
                   r"\b[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}\b", re.I)


def quote_of(unit, reuse):
    if reuse not in ("copy", "quote"):
        return ""
    words = re.sub(r"[*_`]+", "", unit.translate(QUOTES)).split()
    q = " ".join(words[:QUOTE_WORDS])
    return "" if LEAKY.search(q) else q


# ---------------------------------------------------------------- sources, facts and the cache

def root_path(rel):
    return os.path.join(ROOT.path, rel)


def sources():
    return {r["id"]: r for r in kbcommon.load_csv(root_path(kbcommon.SOURCES), ("id", "url", "reuse"))[1]}


def cited_facts(prefix=None):
    """{source id: [(fact key, root-relative path, line, fact text)]} for every tagged fact of the root."""
    out = collections.defaultdict(list)
    seen = set()
    for u in kbfacts.units(prefix or ROOT.name):
        rel = kbfacts.bare(u["path"])
        key = kbfacts.fact_key(u["text"])
        for part in u["tags"]:
            if part["kind"] == "UNK":
                continue
            for sid in part["ids"]:
                if (key, rel, sid) not in seen:
                    seen.add((key, rel, sid))
                    out[sid].append((key, rel, u["line"], u["text"]))
    return out


def cite_counts(facts):
    """{(fact key, path): the number of sources the fact cites} of `facts` (cited_facts()): what Doc.locate takes as
    `cites` of every fact, so that anchoring and each later look at the page weigh a data row's cells alike."""
    return collections.Counter((k, rel) for fs in facts.values() for k, rel, _, _ in fs)


def cache_path(sid, shared=False):
    """The cache file of a source's document. `shared` (a read with no network: queue and review --offline) falls back to
    the cache of the clone's main worktree when this worktree holds none, as the query index is shared."""
    name = os.path.join(ROOT.name, re.sub(r"[^\w.-]", "_", sid) + ".json")
    path = os.path.join(CACHE, name)
    if shared and not os.path.exists(path):
        other = os.path.join(kbfacts.clone_home(), "_cache", "factdiff", name)
        if os.path.exists(other):
            return other
    return path


def cached_doc(sid, max_age):
    try:
        with open(cache_path(sid), encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    when = datetime.datetime.fromisoformat(d.get("fetched_utc", "1970-01-01T00:00:00+00:00").replace("Z", "+00:00"))
    age = (datetime.datetime.now(datetime.timezone.utc) - when).days
    if age > max_age:
        return None
    if d.get("raw") is not None:  # the text is re-derived, so a change to the reducer needs no refetch
        d["text"] = provider.doc_text(d["raw"].encode("utf-8"), d.get("ctype", ""), d.get("raw_url", d["url"]))
    return d


def fetch_doc(sid, url, rows):
    d = provider.document(url, provider.for_url(url, rows) or {})
    d = {k: v for k, v in d.items() if k != "hops"} | {"id": sid, "url": url,
                                                       "fetched_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    os.makedirs(os.path.dirname(cache_path(sid)), exist_ok=True)
    with open(cache_path(sid), "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f)
    return d


def fetch_all(ids, srcs, max_age=7, refetch=False, log=True):
    """{id: cached document} for the ids, fetching the missing ones in parallel, one thread per host."""
    rows = provider.providers(ROOT)
    docs, todo = {}, collections.defaultdict(list)
    for sid in ids:
        d = None if refetch else cached_doc(sid, max_age)
        if d is not None and d.get("url") == srcs[sid]["url"]:
            docs[sid] = d
        else:
            todo[urllib.parse.urlsplit(srcs[sid]["url"]).netloc].append(sid)
    n = sum(len(v) for v in todo.values())
    if log and n:
        print(f"fetching {n} source(s) from {len(todo)} host(s); {len(docs)} from the cache", file=sys.stderr, flush=True)
    done = [0]

    def host_job(host):
        out = {}
        for sid in todo[host]:
            out[sid] = fetch_doc(sid, srcs[sid]["url"], rows)
            done[0] += 1
            if log and done[0] % 100 == 0:
                print(f"  {done[0]}/{n}", file=sys.stderr, flush=True)
        return out

    with cf.ThreadPoolExecutor(max(1, min(16, len(todo)))) as ex:
        for part in ex.map(host_job, list(todo)):
            docs.update(part)
    return docs


# ---------------------------------------------------------------- anchors file

# rows a fetch that failed or returned no text left: `anchor --file` tries their facts again (no-match rows stay as they are)
RETRY_STATUS = ("unlocated:fetch-error", "unlocated:not-text", "unlocated:gone")
GONE_BACKOFF_DAYS = 7  # a gone row (404/410) is fetched again by `anchor --file` only once its `verified_utc` is this old (at once under --refetch)


def backing_off(row, when):
    """Whether `row` is a gone row verified fewer than GONE_BACKOFF_DAYS days before the date `when`."""
    if row is None or row["status"] != "unlocated:gone":
        return False
    try:
        age = (datetime.date.fromisoformat(when[:10]) - datetime.date.fromisoformat((row.get("verified_utc") or "")[:10])).days
    except ValueError:
        return False
    return age < GONE_BACKOFF_DAYS

def read_anchors():
    p = root_path(ANCHORS)
    if not os.path.exists(p):
        return {}
    return {(r["fact"], r["path"], r["source_id"]): r for r in kbcommon.load_csv(p, COLS)[1]}


def write_anchors(rows):
    key = lambda r: (r["path"], r["fact"], kbid.sort_key(r["source_id"]) if kbid.is_source_id(r["source_id"]) else (9, 0, r["source_id"]))  # noqa: E731
    kbcommon.write_csv(root_path(ANCHORS), COLS, sorted(rows.values(), key=key), atomic=True)


def anchor_rows(sid, facts, doc, reuse, when, cites=None):
    """The anchor rows of one source's facts against its fetched document. `cites` is {(fact key, path): the number of
    sources the fact cites} (Doc.locate)."""
    out = []
    status = None
    if doc is None or doc.get("error") or not doc.get("status"):
        status = "unlocated:fetch-error"
    elif doc["status"] in (404, 410):
        status = "unlocated:gone"
    elif doc["status"] != 200:
        status = "unlocated:fetch-error"
    elif doc.get("text") is None:
        status = "unlocated:not-text"
    d = Doc(doc["text"]) if status is None else None
    for key, rel, _line, text in facts:
        row = {"fact": key, "path": rel, "source_id": sid, "status": status or "", "heading": "", "terms": "", "sha": "",
               "quote": "", "verified_utc": when}
        if d is not None:
            win, _cover, shared = d.locate(fact_text(text), (cites or {}).get((key, rel), 1))
            if win is None:
                row["status"] = "unlocated:no-match"
            else:
                passage = d.window(*win)
                row.update(status="located", heading=d.units[win[0]][0][:200], terms=";".join([t for t in shared if not LEAKY.search(t)][:TERMS]),
                           sha=sha(passage), quote=quote_of(passage, reuse))
        out.append(row)
    return out


def root_rel(path):
    """`path` (an argument of --file) as a path in the root: one already in the root, `<root>/<path>`, `kb/<root>/<path>`
    from the repository, or an absolute one under the root. A path that names no file of the root is returned
    normalized as given, so that its caller reports it."""
    p = os.path.normpath(path).replace(os.sep, "/")
    if ROOT is None or (not os.path.isabs(p) and os.path.isfile(root_path(p))):
        return p
    cands = [p[len(pre):] for pre in (f"kb/{ROOT.name}/", f"{ROOT.name}/") if p.startswith(pre)]
    try:
        under = os.path.relpath(p, ROOT.path).replace(os.sep, "/")
        cands += [] if under == ".." or under.startswith("../") else [under]
    except ValueError:  # another drive
        pass
    return next((c for c in cands if os.path.isfile(root_path(c))), p)


def quote_for(quotes, line, sid):
    """The quote given for the fact at `line` as cited from the source `sid`: its own row, else the one that names no
    source (`quotes` is read_quotes' {(line, source id or ""): quote})."""
    return quotes.get((line, sid)) or quotes.get((line, ""))


def read_quotes(path, rel, facts):
    """({(fact line, source id): quote}, problems) of a --quotes CSV (header `line,quote` or `line,source,quote`) for the
    file `rel` (root-relative): each line must be a tagged fact of the file, each source one that fact cites (the
    two-column form's source is "", every source the fact cites) and each quote at most QUOTE_WORDS words; `facts` is
    cited_facts()."""
    out, bad = {}, []
    cited = collections.defaultdict(set)  # {fact line: the source ids it cites}
    for sid, fs in facts.items():
        for _k, r, line, _t in fs:
            if r == rel:
                cited[line].add(sid)
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
    except OSError as e:
        return {}, [f"--quotes {path}: {e.strerror or e}"]
    head = [c.strip().lower() for c in rows[0]] if rows else []
    if head not in (["line", "quote"], ["line", "source", "quote"]):
        return {}, [f"--quotes {path}: the header must be `line,quote` or `line,source,quote`"]
    width = len(head)
    for n, r in enumerate(rows[1:], start=2):
        if not any(c.strip() for c in r):
            continue
        if len(r) != width or not r[0].strip().isdigit():
            bad.append(f"--quotes {path}:{n}: want `{','.join(head)}` (the fact's line number{', its source' if width == 3 else ''}, "
                       "then its quote)")
            continue
        line, sid, quote = int(r[0]), (kbid.canonical_id(r[1].strip()) if width == 3 else ""), r[-1].strip()
        if line not in cited:
            bad.append(f"--quotes {path}:{n}: {rel}:{line} is no tagged fact of the file")
        elif sid and sid not in cited[line]:
            bad.append(f"--quotes {path}:{n}: {rel}:{line} cites no source {r[1].strip()}")
        elif len(quote.split()) > QUOTE_WORDS:
            bad.append(f"--quotes {path}:{n}: the quote of {rel}:{line} is over {QUOTE_WORDS} words")
        elif (line, sid) in out:
            bad.append(f"--quotes {path}:{n}: {rel}:{line}{' ' + sid if sid else ''} is quoted twice")
        else:
            out[(line, sid)] = quote
    return out, bad


def quote_rows(rows, facts, doc, reuse, quotes):
    """Anchors each fact the researcher quoted by its quote, in `rows` (anchor_rows' rows of `facts`, one source; changed
    in place), when the page holds it: the passage that holds the quote word for word, its terms those the fact shares with it (else
    the quote's), and the quote kept as the anchor's `quote` where the source's reuse allows. `quotes` is read_quotes':
    a fact's quote of this row's source (quote_for). A row whose quote the page lacks, or whose terms come out empty,
    stays as it was. Returns ([fact lines anchored by their quote], [fact lines whose quote the page lacks]); a page
    that is no text holds neither."""
    if not quotes or doc is None or doc.get("error") or doc.get("status") != 200 or doc.get("text") is None:
        return [], []
    d, found, lost = Doc(doc["text"]), [], []
    for row, (key, _rel, line, text) in zip(rows, facts):
        quote = quote_for(quotes, line, row["source_id"])
        if quote is None:
            continue
        win = d.locate_quote(quote)
        if win is not None:
            held = set().union(*d.terms[win[0]:win[0] + win[1]])
            order = lambda t: (-d.idf.get(t, 0.0), t)  # noqa: E731
            terms = sorted(term_set(fact_text(text)) & held, key=order) or sorted(term_set(quote) & held, key=order)
            terms = [t for t in terms if not LEAKY.search(t)][:TERMS]
        if win is None or not terms:
            lost.append(line)
            continue
        row.update(status="located", heading=d.units[win[0]][0][:200], terms=";".join(terms), sha=sha(d.window(*win)),
                   quote=quote_of(quote, reuse))
        found.append(line)
    return found, lost


def propose_quote(d, fact, win):
    """The quote of at most QUOTE_WORDS words that best holds `fact` in the window `win` of the Doc `d`: the run of words,
    in the one unit of the window that shares most of the fact's term weight, that shares most of it; "" when the page
    lacks a run that locate_quote finds again or the run looks like private data (LEAKY)."""
    want = term_set(fact)
    best = (0.0, "")
    for _head, unit in d.units[win[0]:win[0] + win[1]]:
        words = re.sub(r"[*_`]+", "", unit.translate(QUOTES)).split()
        weight = [sum(d.idf.get(t, 0.0) for t in term_set(w) & want) for w in words]
        for i in range(max(1, len(words) - QUOTE_WORDS + 1)):
            span = words[i:i + QUOTE_WORDS]
            score = sum(weight[i:i + QUOTE_WORDS]) - 1e-6 * i  # the first run among equals
            if len(span) >= QUOTE_MIN_WORDS and score > best[0] + 1e-9:
                best = (score, " ".join(span))
    q = best[1]
    return q if q and not LEAKY.search(q) and d.locate_quote(q) is not None else ""


def cmd_propose(a, srcs, facts, anchors, rel):
    """`anchor --file F --propose`: a `line,source,quote` CSV on stdout of the passage each cited page holds of each fact
    of F that has no located anchor; what finds none is named on stderr. Writes no ledger and no state."""
    cites = cite_counts(facts)
    todo = {sid: [f for f in fs if f[1] == rel and (anchors.get((f[0], f[1], sid)) or {}).get("status") != "located"]
            for sid, fs in facts.items() if sid in srcs}
    ids = [i for i, fs in todo.items() if fs]
    docs = fetch_all(ids, srcs, a.max_age, a.refetch)
    got, n, none = [], 0, 0
    for sid in sorted(ids, key=lambda s: kbid.sort_key(s) if kbid.is_source_id(s) else (9, 0, s)):
        doc = docs.get(sid)
        if doc is None or doc.get("error") or doc.get("status") != 200 or doc.get("text") is None:
            for _k, _r, line, _t in todo[sid]:
                print(f"no page text: {rel}:{line} {sid}", file=sys.stderr)
                none += 1
            continue
        d = Doc(doc["text"])
        for key, _r, line, text in sorted(todo[sid], key=lambda f: f[2]):
            fact = fact_text(text)
            win = d.locate(fact, cites.get((key, rel), 1))[0]
            if win is None:  # below the anchoring cut: still the page's best window when it shares terms with the fact
                best, _cover, _own, shared = d.score(fact)
                win = best if best is not None and len(shared) >= PROPOSE_SHARED else None
            quote = propose_quote(d, fact, win) if win is not None else ""
            if quote:
                got.append((line, sid, quote))
                n += 1
            else:
                print(f"no passage: {rel}:{line} {sid}", file=sys.stderr)
                none += 1
    out = csv.writer(sys.stdout, lineterminator="\n")
    out.writerow(["line", "source", "quote"])
    out.writerows(sorted(got))
    print(f"propose: sources={len(ids)} proposed={n} no_passage={none}; nothing written", file=sys.stderr)
    return 0


def cmd_anchor(a):
    srcs = sources()
    facts = cited_facts()
    quotes, rel = {}, None
    a.file = [root_rel(f) for f in a.file]
    propose = getattr(a, "propose", False)
    if (getattr(a, "quotes", None) or propose) and len(a.file) != 1:
        print(f"anchor: {'--propose' if propose else '--quotes'} needs exactly one --file", file=sys.stderr)
        return 2
    if propose and (getattr(a, "quotes", None) or a.topic or a.dir or a.source):
        print("anchor: --propose takes one --file and no other selector or --quotes", file=sys.stderr)
        return 2
    if a.file:
        rel = a.file[0]
    if propose:
        if not any(f[1] == rel for fs in facts.values() for f in fs):
            print(f"anchor: {rel} holds no tagged fact", file=sys.stderr)
            return 2
        return cmd_propose(a, srcs, facts, read_anchors(), rel)
    if getattr(a, "quotes", None):
        quotes, bad = read_quotes(a.quotes, rel, facts)
        if bad:
            print("\n".join(bad), file=sys.stderr)
            return 2
    ids = select_ids(a, srcs)
    ids = [i for i in ids if i in facts and i in srcs]
    anchors = read_anchors()
    before = dict(anchors)
    # --file alone: only the facts of those files that hold no anchor row (a new or reworded fact: its key is new), whose
    # row a failed or non-text fetch left (RETRY_STATUS: fetched again past the cache, a gone row once GONE_BACKOFF_DAYS
    # old, or at once under --refetch) or that the quote CSV names; no other row of the ledger and no `_fetch_state.csv` row is written, and a retry
    # that fails the same way leaves its row as it was
    when = today()
    only = {os.path.normpath(f).replace(os.sep, "/") for f in a.file} if a.file and not (a.topic or a.dir or a.source) else None
    todo, retry = facts, set()
    if only is not None:
        def wanted(f, sid):
            row = anchors.get((f[0], f[1], sid))
            again = row is not None and row["status"] in RETRY_STATUS and (a.refetch or not backing_off(row, when))
            if again:
                retry.add(sid)
            return row is None or again or (f[1] == rel and quote_for(quotes, f[2], sid) is not None)
        todo = {sid: [f for f in fs if f[1] in only and wanted(f, sid)] for sid, fs in facts.items()}
        ids = [i for i in ids if todo.get(i)]
    docs = fetch_all([i for i in ids if i not in retry], srcs, a.max_age, a.refetch)
    if retry & set(ids):
        docs.update(fetch_all([i for i in ids if i in retry], srcs, a.max_age, True))
    counts = collections.Counter()
    cites = cite_counts(facts)
    for sid in ids:
        reuse = (srcs[sid].get("reuse") or "").strip()
        rows = anchor_rows(sid, todo[sid], docs.get(sid), reuse, when, cites)
        if quotes:
            mine = [(i, f) for i, f in enumerate(todo[sid]) if f[1] == rel and quote_for(quotes, f[2], sid) is not None]
            if mine:
                found, lost = quote_rows([rows[i] for i, _ in mine], [f for _, f in mine], docs.get(sid), reuse, quotes)
                counts["quote found"] += len(found)
                counts["quote not held"] += len(lost)
                for line in lost:
                    print(f"quote not held: {rel}:{line} {sid}", file=sys.stderr)
        for row in rows:
            k = (row["fact"], row["path"], row["source_id"])
            old = anchors.get(k)
            if old and old["status"] == "located" and row["status"].startswith("unlocated:fetch"):
                counts["kept (fetch failed)"] += 1
                continue  # a failed fetch never erases a located anchor
            if only is not None and old and old["status"] in RETRY_STATUS and row["status"] == old["status"]:
                counts["kept (still " + old["status"].split(":")[1] + ")"] += 1
                continue  # the retry failed the same way: the row stays as it was, so the ledger is not rewritten
            anchors[k] = row
            counts[row["status"]] += 1
    live = {(k, rel_, sid) for sid, fs in facts.items() for k, rel_, _, _ in fs}
    if only is not None:
        stale = [k for k in anchors if k not in live and k[1] in only]
    else:
        stale = [k for k in anchors if k not in live and (not ids or k[2] in ids or not a.selected)]
    for k in stale:
        del anchors[k]
    print(f"anchor: sources={len(ids)} " + " ".join(f"{k}={v}" for k, v in sorted(counts.items())) + f" pruned_stale={len(stale)}")
    if a.dry_run:
        print("dry run: nothing written")
        return 0
    if only is not None:
        if anchors != before:
            write_anchors(anchors)
        return 0
    write_anchors(anchors)
    state, rows = read_state(), provider.providers(ROOT)
    for sid in ids:  # the anchors' document is detect's baseline: the next detect compares with it
        d = docs.get(sid)
        if d and d.get("status") == 200 and d.get("text"):
            state[sid] = {**state.get(sid, {}), **baseline(sid, srcs[sid]["url"], d, rows)}
    write_state(state)
    return 0


def baseline(sid, url, d, rows):
    """The detection columns of _fetch_state.csv for a fetched document."""
    row = provider.for_url(url, rows) or {}
    keys = [k for k in (row.get("version_meta") or "").split(",") if k.strip() and k != "-"]
    stamp = (d.get("fetched_utc") or "")[:19].replace("+00:00", "")
    doc_sha = hashlib.sha256(d["text"].encode()).hexdigest()
    return {"id": sid, "url": url, "etag": d.get("etag", ""), "last_modified": d.get("lastmod", ""),
            "version": (d.get("version") or {}).get(keys[0], "") if keys else "",
            "doc_sha256": doc_sha, "sections": sections_column(d["text"], doc_sha),
            "final_url": d["final"] if (d.get("final") or "").split("?")[0] != provider.raw_url(url, row)[0].split("?")[0] else "",
            "http_status": "200", "simhash": simhash(d["text"]), "detected_utc": (stamp + "Z") if stamp else ""}


BASELINE_KEYS = ("etag", "last_modified", "version", "doc_sha256")  # what detect compares a fetched page with


def has_baseline(row):
    """Whether a _fetch_state.csv row holds a detection baseline: a validator, a version id or a text hash."""
    return any((row or {}).get(k) for k in BASELINE_KEYS)


def live_unpinned(srcs):
    """{id: row} of the sources that are not superseded and whose url can change (no commit sha or release tag in it)."""
    return {sid: s for sid, s in srcs.items() if not (s.get("superseded_by") or "").strip() and not provider.is_pinned(s["url"])}


def baseline_gap(srcs, state):
    """The ids, in id order, of the live unpinned sources of `srcs` whose `state` row holds no detection baseline:
    detect has nothing to compare their next fetch with, so a page with no date goes to a reader."""
    return sorted((sid for sid in live_unpinned(srcs) if not has_baseline(state.get(sid))), key=kbid.sort_key)


def census_baseline(sid, url, since, until, rows):
    """The detection columns for a source a census confirmed, from the document factdiff fetched and kept in the cache,
    or {} when it holds none a census compared: the document is a 200 with text, of this url, fetched from `since` (the
    census log's date) to `until` (the confirmation date). A text fetched before the census or after its confirmation is
    one nobody compared with the facts, so it is no baseline (the next detect takes one and census confirms the source)."""
    d = load_json(cache_path(sid, shared=True))
    if not d or d.get("status") != 200 or not d.get("text") or d.get("url") != url:
        return {}
    day = (d.get("fetched_utc") or "")[:10]
    return baseline(sid, url, d, rows) if since <= day <= until else {}


# ---------------------------------------------------------------- snapshots of copy sources

SNAP_NOTE = ("normalized to text by _tools/provider.py (raw form; front matter, link targets, images and page chrome "
             "removed); not the publisher's formatting")


def snapshot_path(sid):
    return root_path(os.path.join(kbcommon.SNAPSHOTS, re.sub(r"[^\w.-]", "_", sid) + ".txt"))


SNAPSHOT_MAX = _CFG.get("snapshot", {}).get("max_bytes", 500_000)
# a private key header in a page (a vendor's sample key, or only the marker in a format note) trips the leak test
# (`_tools/test_leaks.py`) and secret scanners on push: such a page keeps only its hash, like an oversized one
KEY_BLOCK = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP |ENCRYPTED )?PRIVATE KEY(?: BLOCK)?-----")


def wants_snapshot(src, doc=None):
    """A source whose text the kb keeps: reuse class copy, a live url (a pinned file is its upstream at the pin), not
    superseded; with its document, also a document (not a JSON API answer) of at most SNAPSHOT_MAX bytes that holds
    no private key header."""
    if (src.get("reuse") or "").strip() != "copy" or provider.is_pinned(src["url"]) or (src.get("superseded_by") or "").strip():
        return False
    if doc is not None:
        return (bool(doc.get("text")) and "json" not in (doc.get("ctype") or "")
                and len(doc["text"].encode()) <= SNAPSHOT_MAX and not KEY_BLOCK.search(doc["text"]))
    return True


def read_snapshot(sid):
    """({header key: value}, body text) of a source's snapshot, or (None, None)."""
    try:
        with open(snapshot_path(sid), encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return None, None
    head, sep, body = text.partition("\n---\n")
    if not sep:
        return None, None
    return dict(ln.split(": ", 1) for ln in head.splitlines() if ": " in ln), body


def write_snapshot(src, text, when):
    """Write a source's snapshot when its text differs from the stored one; True when written."""
    _, old = read_snapshot(src["id"])
    if old == text:
        return False
    head = [("source", src["id"]), ("url", src["url"]), ("title", src.get("title", "")),
            ("publisher", src.get("publisher", "")), ("licence", src.get("licence", "")), ("retrieved", when),
            ("changes", SNAP_NOTE)]
    os.makedirs(os.path.dirname(snapshot_path(src["id"])), exist_ok=True)
    with open(snapshot_path(src["id"]), "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(f"{k}: {' '.join(str(v).split())}\n" for k, v in head) + "---\n" + text)
    return True


def cmd_snapshot(a):
    srcs = sources()
    facts = cited_facts()
    ids = [i for i in select_ids(a, srcs) if i in srcs and i in facts and wants_snapshot(srcs[i])]
    docs = fetch_all(ids, srcs, a.max_age, a.refetch)
    when, n, size, skipped = today(), 0, 0, collections.Counter()
    for sid in ids:
        d = docs.get(sid) or {}
        if d.get("status") != 200 or not d.get("text"):
            skipped["no text" if d.get("status") == 200 else f"HTTP {d.get('status') or d.get('error', '')[:30]}"] += 1
            continue
        if not wants_snapshot(srcs[sid], d):
            skipped["JSON answer, over max_bytes or key block"] += 1
            continue
        if a.dry_run:
            size += len(d["text"].encode())
            n += 1
            continue
        if write_snapshot(srcs[sid], d["text"], when):
            n += 1
        size += os.path.getsize(snapshot_path(sid))
    print(f"snapshot: copy sources={len(ids)} written={n} bytes={size}" + "".join(f" skipped[{k}]={v}" for k, v in skipped.items())
          + (" (dry run: nothing written)" if a.dry_run else ""))
    return 0


# ---------------------------------------------------------------- calibration

def _git(repo, *args):
    import subprocess
    p = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    return p.stdout if p.returncode == 0 else None


def best_cut(pos, neg, grid, above=True):
    """(cut, balanced accuracy, tpr, tnr): the grid value that best separates pos (>= cut when `above`) from neg."""
    best = None
    for c in grid:
        tp = sum(1 for x in pos if (x >= c) == above) / (len(pos) or 1)
        tn = sum(1 for x in neg if (x >= c) != above) / (len(neg) or 1)
        if best is None or (tp + tn) / 2 > best[1] + 1e-9:
            best = (round(c, 2), round((tp + tn) / 2, 3), round(tp, 3), round(tn, 3))
    return best


def calibrate_history(repo, prefixes, since, pairs, seed):
    """Cut-offs from a documentation repository's own history: consecutive versions of changed pages. A unit that
    difflib pairs 1:1 with an edited unit is `modified` (its similarity to the edit is a positive), a deleted unit is
    `removed` (its best similarity to any unit of the new version is a negative); page-level, a page against its next
    version is `same page`, against another changed page `other page`."""
    import random
    rnd = random.Random(seed)
    log = _git(repo, "log", f"--since={since}", "--diff-filter=M", "--format=@%H", "--name-only", "--", *prefixes) or ""
    cands, cur = [], None
    for ln in log.splitlines():
        if ln.startswith("@"):
            cur = ln[1:]
        elif ln.strip().endswith(".md") and cur:
            cands.append((cur, ln.strip()))
    rnd.shuffle(cands)
    import difflib
    pos, neg, verb, tot, same, other, texts = [], [], 0, 0, [], [], []
    for commit, path in cands[:pairs]:
        # cat-file, not show: `git show REV:PATH` checks its argument as a file name ("Filename too long" on Windows)
        old, new = _git(repo, "cat-file", "blob", f"{commit}^:{path}"), _git(repo, "cat-file", "blob", f"{commit}:{path}")
        if old is None or new is None:
            continue
        ot, nt = provider.doc_text(old.encode(), "text/markdown", path), provider.doc_text(new.encode(), "text/markdown", path)
        texts.append((ot, nt))
        same.append(simhash_sim(simhash(ot), simhash(nt)))
        ou, nd = [u for _, u in units(ot)], Doc(nt)
        nu = [u for _, u in nd.units]
        on, nn = [norm(u) for u in ou], [norm(u) for u in nu]
        for u in ou:
            tot += 1
            verb += sha(u) in nd.shas
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, on, nn, autojunk=False).get_opcodes():
            if tag == "replace" and i2 - i1 == j2 - j1:
                pos += [unit_sim(ou[i1 + k], nu[j1 + k]) for k in range(i2 - i1)]
            elif tag == "delete":
                for i in range(i1, i2):
                    if sha(ou[i]) in nd.shas:
                        continue  # moved, not removed
                    ts = term_set(ou[i])
                    ranked = sorted(range(len(nu)), key=lambda j: -len(ts & nd.terms[j]))[:5]
                    neg.append(max((unit_sim(ou[i], nu[j]) for j in ranked), default=0.0))
    for i in range(len(texts)):
        j = (i + 1 + rnd.randrange(max(1, len(texts) - 1))) % len(texts) if len(texts) > 1 else i
        if j != i:
            other.append(simhash_sim(simhash(texts[i][0]), simhash(texts[j][1])))
    grid = [x / 100 for x in range(20, 100, 5)]
    return {"repo": os.path.basename(repo), "since": since, "pages": len(texts), "units": tot,
            "verbatim_share": round(verb / (tot or 1), 3), "modified": len(pos), "removed": len(neg),
            "modified_min": best_cut(pos, neg, grid), "same_page": len(same), "other_page": len(other),
            "zombie_max": best_cut(other, same, grid, above=False),
            "quantiles": {k: [round(sorted(v)[int(q * (len(v) - 1))], 3) for q in (0.05, 0.25, 0.5, 0.75, 0.95)] if v else []
                          for k, v in (("modified", pos), ("removed", neg), ("same_page", same), ("other_page", other))}}


def calibrate_soft404(srcs, hosts, seed):
    """Per host of the root's sources: a real page and two made-up sibling urls. Positives: the two made-up pages
    of a host that answers 200 to them (both error or landing pages); negatives: a real page against its host's
    made-up page. Returns the counts of hard and soft hosts and the cut."""
    import random
    rnd = random.Random(seed)
    by_host = collections.defaultdict(list)
    for s in srcs.values():
        if not (s.get("superseded_by") or "").strip() and not provider.is_pinned(s["url"]):
            by_host[urllib.parse.urlsplit(s["url"]).netloc].append(s["url"])
    names = sorted(h for h in by_host if h != "api.github.com")  # its unauthenticated limit is 60 requests an hour
    rnd.shuffle(names)
    names = names[:hosts]

    def one(host):
        url = rnd.choice(by_host[host])
        out = []
        for u in (url, provider._sibling(url), provider._sibling(url + "x")):
            r = provider.request(u)
            out.append((r["status"], provider.doc_text(r["body"], r["headers"].get("content-type", ""), u) or "" if r["body"] else ""))
        return host, out

    pos, neg, statuses = [], [], collections.Counter()
    with cf.ThreadPoolExecutor(16) as ex:
        for host, ((s0, real), (s1, f1), (s2, f2)) in ex.map(one, names):
            statuses[s1 if s1 in (200, 404, 410) else "other"] += 1
            if s0 == 200 and s1 == 200 and s2 == 200:
                pos.append(jaccard(f1, f2))
                neg.append(jaccard(real, f1))
    grid = [x / 100 for x in range(10, 100, 5)]
    return {"hosts": len(names), "made_up_url_status": dict(statuses), "soft_hosts": len(pos),
            "soft404_min": best_cut(pos, neg, grid),
            "quantiles": {k: [round(sorted(v)[int(q * (len(v) - 1))], 3) for q in (0.05, 0.25, 0.5, 0.75, 0.95)] if v else []
                          for k, v in (("made_up_pair", pos), ("real_vs_made_up", neg))}}


def cmd_calibrate(a):
    if a.what == "history":
        out = calibrate_history(a.repo, a.path or ["."], a.since, a.pairs, a.seed)
    else:
        out = calibrate_soft404(sources(), a.hosts, a.seed)
    print(json.dumps(out, indent=1))
    return 0


# ---------------------------------------------------------------- detection

LOG_COLS = ["source_id", "url", "verdict", "signal", "evidence", "baseline_utc", "content_date", "fact", "path", "line", "outcome",
            "target", "note"]
DATE_KEYS = ("updated_at", "dateModified", "article:modified_time", "timeline")  # a version key that is the content's own date


def content_date(doc):
    """The page's own content date (YYYY-MM-DD) from its version keys, or ''."""
    v = (doc or {}).get("version") or {}
    return next((v[k][:10] for k in DATE_KEYS if re.match(r"\d{4}-\d{2}-\d{2}", v.get(k, ""))), "")


def confirmable(head, retrieved):
    """Whether a source's `unchanged` (or all-verbatim) verdict proves its facts still hold: the text it was compared
    with is no newer than the source's last confirmation (retrieved_utc), by the detection baseline's date or by the
    page's own content date. A baseline taken after the last confirmation proves only that nothing changed since."""
    r = (retrieved or "")[:10]
    return bool(r) and any(d and d[:10] <= r for d in (head.get("baseline_utc", ""), head.get("content_date", "")))


def baseline_head(st, doc, prev):
    """The `head` of confirmable() for a source's stored state row `st` and the documents of one detection: the
    baseline's date and the page's own content date, as the log's head row holds them."""
    return {"baseline_utc": (st or {}).get("detected_utc", ""), "content_date": content_date(doc) or content_date(prev)}


VERDICTS = ("unchanged", "changed", "new", "moved", "gone", "soft-404", "replaced", "error", "pinned", "hinted")
CHANGE_VERDICTS = ("changed", "replaced", "moved")  # a change detect saw: the state row's changed_utc is its check time
OUTCOMES = ("verbatim", "moved", "modified", "not-found", "unanchored", "dead")
AUTO = ("verbatim", "moved")  # applied with no model: the anchor's passage found word for word
REVIEW = ("modified", "not-found", "unanchored", "dead")
SEARCH_TOP = 3  # pages of a provider search fetched per fact


def read_state():
    p = root_path(kbcommon.STATE)
    return {r["id"]: r for r in kbcommon.load_csv(p, ("id",))[1]} if os.path.exists(p) else {}


def write_state(state):
    key = lambda r: kbid.sort_key(r["id"]) if kbid.is_source_id(r["id"]) else (2, 0, r["id"])  # noqa: E731
    kbcommon.write_csv(root_path(kbcommon.STATE), kbcommon.STATE_COLS, sorted(state.values(), key=key), atomic=True)


def prev_path(sid, shared=False):
    return cache_path(sid, shared)[:-5] + ".prev.json"


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    if d.get("raw") is not None:
        d["text"] = provider.doc_text(d["raw"].encode("utf-8"), d.get("ctype", ""), d.get("raw_url", d.get("url", "")))
    return d


def save_doc(sid, d):
    """Keep the fetched document as the cache entry, the one before it as .prev.json (the old text of a diff)."""
    os.makedirs(os.path.dirname(cache_path(sid)), exist_ok=True)
    if os.path.exists(cache_path(sid)):
        os.replace(cache_path(sid), prev_path(sid))
    with open(cache_path(sid), "w", encoding="utf-8", newline="\n") as f:
        json.dump({k: v for k, v in d.items() if k not in ("hops", "text")}, f)


_madeup, _pages = {}, {}
_unanswered, _unanswered_uses = {}, []  # request url -> "HTTP 503 ..." of a search or candidate page that gave no answer; one entry per use


def _http_error(url, status, what):
    """Record that the search or candidate page `url` answered `status`, an HTTP error, or no HTTP answer at all (status
    0: a network error, the time budget): no answer to the passage's search, whoever leans on it later (a 404 or 410 of
    a candidate page is an absent page, no error). Returns True when it was recorded."""
    if status == 200 or (what == "candidate page" and status in (404, 410)):
        return False
    _unanswered[url] = f"{f'HTTP {status}' if status else 'no HTTP answer'} from the {what} {url.split('?')[0]}"
    return True


def _used_unanswered(url):
    """Count one use of the answer of `url`, cached or fresh: a passage whose search leaned on it is not known lost."""
    if url in _unanswered:
        _unanswered_uses.append(_unanswered[url])


def search_lost(failed, used):
    """Why the search for a passage did not finish, or "": the time budget, the HTTP errors of a search or candidate page
    used since `used` (named), or a network error since `failed` (provider.failures() then). A request that answered
    an HTTP error counts as a failure as one that got no answer does."""
    if provider.spent():
        return provider.BUDGET_ERROR
    why = list(dict.fromkeys(_unanswered_uses[used:]))
    if provider.failures() > failed:
        why.append("network error during the search for the passage")
    return "; ".join(why)[:300]


def madeup_text(url):
    """The text a made-up sibling url of `url` returns with 200 (None for a real 404), once per host and run; an answer
    with no HTTP status is not kept, so a network failure leaves soft-404 detection on for the host's other sources."""
    host = urllib.parse.urlsplit(url).netloc
    if host not in _madeup:
        r = provider.gated_request(provider._sibling(url))
        if not r["status"]:
            return None  # no answer is no 404: a later source of the host asks again
        _madeup[host] = provider.doc_text(r["body"], r["headers"].get("content-type", ""), url) if r["status"] == 200 else None
    return _madeup[host]


def page_doc(url, rows):
    """(Doc, text) of any url fetched by its provider's raw form, once per run (search and redirect targets)."""
    if url not in _pages:
        d = provider.document(url, provider.for_url(url, rows) or {})
        _pages[url] = (Doc(d["text"]), d["text"]) if d.get("status") == 200 and d.get("text") else (None, None)
        _http_error(url, d.get("status"), "candidate page")
    _used_unanswered(url)
    return _pages[url]


def gh_page_id(url, text):
    """census.gh_page_id: the version id of a github.com page held in a git repository, or '' (census imports this module,
    so the import waits for the call)."""
    import census
    return census.gh_page_id(url, text)


def gh_page_quiet_since(url, text, day):
    """census.gh_page_quiet_since: whether the page's repository holds nothing newer than `day` for it."""
    import census
    return census.gh_page_quiet_since(url, text, day)


def learn_git_verdict(url, since):
    """census.learn_git_verdict: the verdict of a Learn page that maps to a file of a public docs repository, from that
    file's commits since `since` in the shared clone, or None (census imports this module, so the import waits for the call)."""
    import census
    return census.learn_git_verdict(url, since)


def learn_repos(urls):
    """census.learn_repos: the docs repositories the Learn urls map to, cloned or fetched once, in parallel."""
    import census
    return census.learn_repos(urls)


def git_quiet(sid, url, st, stamp):
    """(evidence, new state) of a Learn page whose source file in its public docs repository (census.LEARN_MAP) has no
    commit since the day of the stored baseline, so it is `unchanged` with no request to Learn; None when the page maps to
    no repository, the state holds no baseline or a commit is there (the page is then asked, as every other source)."""
    since = (st.get("detected_utc") or "")[:10]
    if not since or not has_baseline(st) or not url.startswith("https://learn.microsoft.com/"):
        return None
    res = learn_git_verdict(url, since)
    if not res or res["bucket"] != "OK":
        return None
    return res["evidence"], {**st, "id": sid, "url": url, "checked_utc": stamp, "detected_utc": stamp, "error": ""}


def detect_source(sid, src, st, rows, lookup=False):
    """(verdict, signal, evidence, new state, doc, prev doc) of one source against its stored state. `lookup` (a
    revalidation at question time, revalidate): no clone of a git repository is made or fetched (the page itself is asked
    instead) and the fetched document is not written to the cache of the detection runs."""
    url, row = src["url"], provider.for_url(src["url"], rows) or {}
    sig = provider.signals(row, url)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if "pin" in sig:  # its text cannot change; its repository, once per run, may be gone (a 404: deleted or private)
        state, ev = provider.repository_state(url)
        if state == "gone":
            return "gone", "repository", ev, None, None, None  # no state row: checked_utc would stamp it confirmed
        return "pinned", "pin", "pinned url: its text cannot change (census.py compares the pin with upstream)", None, None, None
    prev = load_json(cache_path(sid))
    quiet = None if lookup else git_quiet(sid, url, st, stamp)
    if quiet:
        return "unchanged", "git", quiet[0], quiet[1], prev, prev
    d = provider.document(url, row, etag=st.get("etag", ""), lastmod=st.get("last_modified", ""))
    new = {**st, "id": sid, "url": url, "checked_utc": stamp, "detected_utc": stamp, "http_status": str(d["status"] or "")}
    if d["status"] == 304:
        new.update(error="")
        via = "etag" if st.get("etag") and "etag" in sig else "lastmod"
        return "unchanged", via, "304 Not Modified", new, prev, prev
    if not d["status"] or d["error"] or d["status"] not in (200, 404, 410):
        new["error"] = (d["error"] or ("rate limited: " if d.get("limited") else "") + f"HTTP {d['status']}")[:200]
        return "error", "", new["error"], new, None, prev
    if d["status"] in (404, 410):
        new.update(error=f"HTTP {d['status']}")
        return "gone", "status", f"HTTP {d['status']}", new, None, prev
    if not lookup:
        save_doc(sid, {**d, "id": sid, "url": url, "fetched_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()})
    keys = [k for k in (row.get("version_meta") or "").split(",") if k.strip() and k != "-"]
    version = d["version"].get(keys[0], "") if keys else ""
    gid = gh_page_id(url, d.get("raw") or "") if "git" in sig and not lookup else ""
    if gid:  # a wiki page or a repository home: its file's blob ids in the clone cache are its version id
        keys, version = ["git"], gid
    d["sha"] = hashlib.sha256((d["text"] or "").encode()).hexdigest()
    new.update(etag=d["etag"], last_modified=d["lastmod"], version=version, doc_sha256=d["sha"], error="",
               final_url=d["final"] if d["hops"] else "", simhash=simhash(d["text"] or ""),
               sections=sections_column(d["text"], d["sha"]))
    raw_url = provider.raw_url(url, row)[0]
    moved = bool(d["hops"]) and d["final"].split("?")[0].rstrip("/") != raw_url.split("?")[0].rstrip("/")
    text = d["text"] or ""
    if row.get("not_found") != "hard-404" and words_key(text):  # no words (a client-rendered page) match any made-up page
        mu = madeup_text(raw_url)
        was = prev.get("text") if prev else None
        if mu is not None and jaccard(text, mu) >= SOFT404_MIN and not (was and jaccard(was, mu) >= SOFT404_MIN):
            return "soft-404", "made-up url", f"text matches a made-up sibling url's page (jaccard >= {SOFT404_MIN})", new, None, prev
    if moved:
        return "moved", "redirect", f"redirected to {d['final']}", new, d, prev
    if not st.get("doc_sha256") and not st.get("version"):
        return "new", "", "no earlier detection: anchors decide", new, d, prev
    if version and st.get("version") == version:
        return "unchanged", "version", f"{keys[0]} {version[:40]}", new, d, prev
    since = st.get("detected_utc") or ""
    if version and not st.get("version") and st.get("doc_sha256") and since:  # a baseline of the text only: date it against the signal
        if keys == ["timeline"] and version <= since:
            return "unchanged", "version", f"timeline {version} is not after the baseline {since}", new, d, prev
        if keys == ["git"] and not lookup and gh_page_quiet_since(url, d.get("raw") or "", since[:10]):
            return "unchanged", "git", f"no commit of the page's file, licence or release since the baseline {since[:10]}", new, d, prev
    if st.get("doc_sha256") == d["sha"]:
        return "unchanged", "hash", "document text identical", new, d, prev
    if st.get("simhash") and simhash_sim(st["simhash"], new["simhash"]) <= ZOMBIE_MAX:
        return "replaced", "simhash", f"simhash similarity to the previous version <= {ZOMBIE_MAX}", new, d, prev
    return "changed", "version" if version else "hash", (f"{keys[0]} {st.get('version', '')[:12]} -> {version[:12]}" if version
                                                          else "document text differs"), new, d, prev


SITEMAP_FILES = 40  # sitemap files read per provider and run
_added = {}


def sitemap_urls(row, segments):
    """{url: lastmod} of a provider's sitemap; for an index, only the files named after the sources' first path
    segments (`intune_en-us_1.xml`) or, when none is, those of the en-us locale, at most SITEMAP_FILES."""
    sm = (row.get("sitemap") or "-").strip()
    if sm in ("-", ""):
        return {}
    r = provider.request(sm)
    body = r["body"].decode("utf-8", "replace") if r["status"] == 200 else ""
    locs = re.findall(r"<loc>\s*([^<]+?)\s*</loc>(?:\s*<lastmod>\s*([^<]+?)\s*</lastmod>)?", body)
    if "<sitemapindex" not in body:
        return {u: lm for u, lm in locs}
    files = [u for u, _ in locs if any(u.rsplit("/", 1)[-1].startswith(seg + "_") for seg in segments)] or \
        [u for u, _ in locs if "en-us" in u]
    out = {}
    for f in files[:SITEMAP_FILES]:
        r = provider.request(f)
        if r["status"] == 200:
            out.update({u: lm for u, lm in re.findall(r"<loc>\s*([^<]+?)\s*</loc>(?:\s*<lastmod>\s*([^<]+?)\s*</lastmod>)?",
                                                     r["body"].decode("utf-8", "replace"))})
    return out


def sitemap_added(row, segments, save=True):
    """Urls added to a provider's sitemap since the last run (none on the first); the url set is kept in _cache."""
    name = row.get("provider", "")
    if name in _added:
        return _added[name]
    cur = sitemap_urls(row, segments)
    path = os.path.join(CACHE, "sitemaps", f"{name}.json")
    try:
        with open(path, encoding="utf-8") as f:
            old = set(json.load(f))
    except (OSError, ValueError):
        old = None
    _added[name] = sorted(set(cur) - old) if old is not None and cur else []
    if save and cur:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(sorted(cur), f)
    return _added[name]


def near(url, urls, n=5):
    """The n urls sharing the most path segments with url (same host)."""
    u = urllib.parse.urlsplit(url)
    segs = set(u.path.strip("/").split("/"))
    same = [x for x in urls if urllib.parse.urlsplit(x).netloc == u.netloc]
    return sorted(same, key=lambda x: -len(segs & set(urllib.parse.urlsplit(x).path.strip("/").split("/"))))[:n]


_searches = {}


def _search_hits(parse, body):
    """The urls of a provider's 200 search answer read by its shape (`parse`: provider.search_shape's); ValueError (or the
    parser's own error) for a body outside it: a sign-in page, a JSON list, an object holding no list at all (an error
    object). An empty list of the shape is an answer with no hits."""
    urls = [h["url"] for h in parse(body) if h.get("url")]
    if not urls:
        try:
            obj = json.loads(body)
        except ValueError:  # an Atom feed: the parser read it
            return urls
        if isinstance(obj, dict) and not any(isinstance(v, list) for v in obj.values()):
            raise ValueError("no list in the answer")
    return urls


def search_urls(fact, anchor, row, src_url, title=""):
    """Candidate pages for a passage that left its page, from the provider's search (search_api): first the old page's
    title (a moved page keeps it), then the anchor's quote, then the fact's words; SEARCH_TOP pages per query."""
    tpl = (row.get("search_api") or "-").strip()
    if tpl in ("-", "") or "{q}" not in tpl:
        return []
    shape = provider.search_shape(tpl)
    if shape is None:  # an answer this module cannot read is no answer worth a request
        return []
    parse = shape[0]
    queries = [re.split(r"\s+[|:-]\s+(?:Microsoft Learn|Microsoft Entra|Microsoft Intune|Configuration Manager)", title)[0]] if title else []
    if anchor and anchor.get("quote"):
        queries.append(" ".join(anchor["quote"].split()[:12]))
    queries.append(" ".join([w for w in re.findall(r"[A-Za-z][\w.-]+", fact_text(fact)) if w.lower() not in kbfacts.STOP][:8]))
    out = []
    for q in queries:
        if not q.strip():
            continue
        req = tpl.replace("{q}", urllib.parse.quote(q))
        if req not in _searches:  # by the request: two providers' searches of one query are two answers
            r = provider.gated_request(req)
            res = None  # the urls of the provider's result list, read by its shape; None for an answer outside it (a sign-in page)
            if r["status"] == 200:
                try:
                    res = _search_hits(parse, r["body"])
                except (ValueError, SyntaxError, AttributeError, TypeError):  # SyntaxError: the Atom feed's ParseError
                    res = None
            _searches[req] = res or []
            if not _http_error(req, r["status"], "search") and res is None:
                _unanswered[req] = f"no result list from the search {req.split('?')[0]}"
        _used_unanswered(req)
        hits = [u for u in _searches[req] if urllib.parse.urlsplit(u).path.rstrip("/") != urllib.parse.urlsplit(src_url).path.rstrip("/")
                and not urllib.parse.urlsplit(u).path.endswith("/")]  # a hub or landing page holds no passage
        seg = [x for x in urllib.parse.urlsplit(src_url).path.split("/") if x and x != "en-us"][:1]
        hits.sort(key=lambda u: 0 if seg and f"/{seg[0]}/" in u else 1)  # the source's own docset first
        out += [u for u in hits[:SEARCH_TOP] if u not in out]
    return out


def elsewhere(fact, anchor, cands, rows, cites=1):
    """(outcome, target url, note) of a passage searched on other pages: moved when its anchor is found word for word,
    else not-found (with the page where the fact's terms best match, for review). `cites`: Doc.locate's."""
    best = (None, 0.0)
    for u in cands:
        d, _ = page_doc(u, rows)
        if d is None:
            continue
        if anchor and anchor.get("sha") and anchor["sha"] in d.shas:
            return "moved", u, "anchor found word for word"
        win, cover, _ = d.locate(fact_text(fact), cites)
        if win is not None and cover > best[1]:
            best = (u, cover)
    return "not-found", best[0] or "", f"best candidate cover {best[1]:.2f}" if best[0] else "no candidate page"


def linked(src, doc, row, sitemaps=True):
    """Pages a moved passage may have gone to, before any search: the redirect target, then the pages added to the
    provider's sitemap in this run nearest the source's path (not for a lookup: reading a sitemap rewrites the set
    that the next detection compares with)."""
    out = [doc["final"]] if doc and doc.get("final") and doc["final"] != src["url"] and doc.get("hops") else []
    if not sitemaps:
        return out
    seg = urllib.parse.urlsplit(src["url"]).path.strip("/").split("/")
    segs = [x for x in seg[:2] if x and x != "en-us"][:1]
    return out + near(src["url"], sitemap_added(row, segs))


def resolve(sid, src, verdict, doc, prev, facts, anchors, rows, secs=None, lookup=False, head=None, cites=None):
    """Log rows, one per fact of a source whose text changed, moved or died. `secs` is the (baseline, current) pair of
    section sets of a page only its text hash found changed: a located fact whose passage's sections (every unit of
    its window, window_sections) hash the same in both is `verbatim` with the signal `section`, not resolved (no
    passage search, no other page). `head` (baseline_head), given by a revalidation at question time, is the baseline
    the sections were hashed at: a fact whose anchor was confirmed before that baseline is resolved, as apply's kept()
    leaves it, since the baseline proves only that nothing changed since. `lookup`: the
    provider's sitemap is not read (linked). `cites` is cite_counts' {(fact key, path): sources cited} of the whole root
    (a source's `facts` alone lack the other sources a row cites); a fact it lacks counts 1."""
    out = []
    row = provider.for_url(src["url"], rows) or {}
    d = Doc(doc["text"]) if doc and doc.get("text") else None
    pd = Doc(prev["text"]) if prev and prev.get("text") else None
    found = 0
    for key, rel, line, text in facts:
        a = anchors.get((key, rel, sid))
        located = a is not None and a.get("status") == "located"
        rec = {"fact": key, "path": rel, "line": line, "outcome": "", "target": "", "note": ""}
        n_cites = (cites or {}).get((key, rel), 1)
        if d is not None and located and a["sha"] in d.shas:
            rec["outcome"] = "verbatim"
            found += 1
        elif d is not None and located and secs and (head is None or confirmable(head, a.get("verified_utc"))) \
                and section_unchanged(window_sections(a, d, pd), *secs):
            rec.update(outcome="verbatim", signal=SECTION_SIGNAL, note="the section of its passage hashes the same as at the baseline")
            found += 1
        elif d is not None and verdict not in ("soft-404", "replaced"):
            win, cover, _ = d.locate(fact_text(text), n_cites)
            old = None
            if located and pd is not None and a["sha"] in pd.shas:
                old = pd.window(*pd.shas[a["sha"]])
            new_p = d.window(*win) if win else None
            if not located:
                rec.update(outcome="unanchored", note=f"new candidate cover {cover:.2f}" if win else "no candidate on the page")
            elif new_p is not None and (old is None or unit_sim(old, new_p) >= MODIFIED_MIN):
                sim = f"similarity {unit_sim(old, new_p):.2f}" if old else "old passage not in the cache"
                n_old, n_new = (numbers(old) if old else set()), numbers(new_p)
                changed = f"; numbers {','.join(sorted(n_old - n_new))} -> {','.join(sorted(n_new - n_old))}" if old and n_old != n_new else ""
                rec.update(outcome="modified", note=sim + changed)
                found += 1
            else:
                o, t, note = elsewhere(text, a, linked(src, doc, row, not lookup) + search_urls(text, a, row, src["url"], src.get("title", "")),
                                       rows, n_cites)
                rec.update(outcome=o, target=t, note=note)
        else:
            cands = linked(src, doc, row, not lookup) + search_urls(text, a, row, src["url"], src.get("title", ""))
            o, t, note = elsewhere(text, a if located else None, cands, rows, n_cites)
            rec.update(outcome=o if o == "moved" else "dead", target=t, note=note)
        out.append(rec)
    return out, found


def detect_pass(ids, srcs, state, rows, lookup=False):
    """{source id: detect_source's result} of the sources `ids`: one thread per host, a host's sources in turn (its
    pacing), one source's failure an `error` verdict and never the end of the run. `lookup` (revalidate, under
    provider.down_window): a host that did not accept a connection (provider.host_seen) is not asked again while its
    window runs, here or in a later lookup of this or another process, by any request of the lookup (provider.gated_request):
    a source of it is `error` with the reason and no request."""
    by_host = collections.defaultdict(list)
    for sid in ids:
        by_host[urllib.parse.urlsplit(srcs[sid]["url"]).netloc].append(sid)

    def host_job(host):
        res = []
        for sid in by_host[host]:
            try:
                v = detect_source(sid, srcs[sid], state.get(sid, {}), rows, lookup)
            except Exception as e:  # noqa: BLE001 - one source must never stop the run
                v = ("error", "", f"{type(e).__name__}: {e}"[:200], None, None, None)
            res.append((sid, v))
        return res

    results = {}
    with cf.ThreadPoolExecutor(max(1, min(16, len(by_host)))) as ex:
        for part in ex.map(host_job, list(by_host)):
            results.update(part)
    return results


def resolve_source(sid, src, res, state, facts, anchors, rows, lookup=False, cites=None):
    """(verdict, evidence, fact rows, (changed, unchanged) section counts or None) of one source's detect_source result
    `res` and its `facts`: a page that changed, is new, moved, is gone, is a soft 404 or was replaced has its facts
    resolved (resolve), one only its text hash found changed is compared per heading section first, and a `replaced`
    page whose anchors are still found is an edit, `changed`. An unchanged or pinned source has no fact rows. `lookup`:
    a fact kept by its section needs the baseline to be no newer than its anchor's last confirmation (resolve). `cites`:
    resolve's."""
    verdict, signal, ev, _, doc, prev = res
    rows_f, secs, counts = [], None, None
    if verdict == "changed" and signal == "hash" and doc and doc.get("text"):
        # the text hash is the only signal: the sections hashed at the baseline tell which part of the page changed
        old = stored_sections(state.get(sid, {}), prev)
        if old:
            secs = (old, sections(doc["text"]))
            counts = section_counts(*secs)
            ev += f"; sections: {counts[0]} changed, {counts[1]} unchanged"
    if verdict in ("changed", "new", "moved", "gone", "soft-404", "replaced"):
        head = baseline_head(state.get(sid), doc, prev) if lookup and verdict != "new" else None
        rows_f, found = resolve(sid, src, verdict, doc, prev, facts, anchors, rows, secs, lookup, head, cites)
        if verdict == "replaced" and found:
            verdict, ev = "changed", ev + "; anchors still found: an edit, not a replacement"
    return verdict, ev, rows_f, counts


def cmd_detect(a, tally):
    """Detection for the selected sources, then resolution per fact; the log goes to _census/factdiff-<date>.csv."""
    srcs, facts, anchors, state = sources(), cited_facts(), read_anchors(), read_state()
    rows = provider.providers(ROOT)
    ids = [i for i in select_ids(a, srcs) if i in facts and not (srcs[i].get("superseded_by") or "").strip()]
    date = a.date or today()
    hosts = {urllib.parse.urlsplit(srcs[sid]["url"]).netloc for sid in ids}
    print(f"detect: {len(ids)} source(s) on {len(hosts)} host(s)", file=sys.stderr, flush=True)
    hints = lookup_hints(ids, srcs, rows)
    if hints:
        print(f"detect: {len(hints)} source(s) a lookup revalidated within its provider's pacing are not asked", file=sys.stderr, flush=True)
    ask = [i for i in ids if i not in hints]
    learn = learn_repos([srcs[i]["url"] for i in ask if has_baseline(state.get(i)) and state[i].get("detected_utc")])
    if learn:
        print(f"detect: {len(learn)} docs repositor{'y' if len(learn) == 1 else 'ies'} of Learn pages fetched into the clone cache",
              file=sys.stderr, flush=True)
    results = detect_pass(ask, srcs, state, rows)
    results.update({sid: hinted_result(h) for sid, h in hints.items()})
    if a.sitemaps:  # the site-level diff: record every involved provider's sitemap, so the next run sees additions
        segs = collections.defaultdict(set)
        for sid in ids:
            row = provider.for_url(srcs[sid]["url"], rows) or {}
            parts = [x for x in urllib.parse.urlsplit(srcs[sid]["url"]).path.strip("/").split("/")[:2] if x and x != "en-us"]
            segs[row.get("provider", "")].update(parts[:1])
        for row in rows:
            if row["provider"] in segs and (row.get("sitemap") or "-") != "-":
                print(f"sitemap {row['provider']}: {len(sitemap_added(row, sorted(segs[row['provider']]), not a.no_save))} url(s) added "
                      "since the last run", file=sys.stderr, flush=True)
    log, counts, outc, secn = [], collections.Counter(), collections.Counter(), collections.Counter()
    cites = cite_counts(facts)
    for sid in ids:
        _, signal, _, new, doc, prev = results[sid]
        verdict, ev, rows_f, sec = resolve_source(sid, srcs[sid], results[sid], state, facts[sid], anchors, rows, cites=cites)
        if sec:
            secn.update(changed=sec[0], unchanged=sec[1])
        counts[verdict] += 1
        base = {"source_id": sid, "url": srcs[sid]["url"], "verdict": verdict, "signal": signal, "evidence": ev,
                "baseline_utc": state.get(sid, {}).get("detected_utc", "") if verdict != "new" else "",
                "content_date": content_date(doc) or content_date(prev)}
        log.append({**base, "fact": "", "path": "", "line": "", "outcome": "", "target": "", "note": ""})
        for r in rows_f:
            log.append({**base, **r})
            outc[r["outcome"]] += 1
            secn["facts"] += r.get("signal") == SECTION_SIGNAL
        if new is not None and not a.no_save:
            state[sid] = {**new, "changed_utc": new["detected_utc"]} if verdict in CHANGE_VERDICTS else new
        if doc is not None and wants_snapshot(srcs[sid], doc) and not a.no_save:
            write_snapshot(srcs[sid], doc["text"], date)
    out = a.out or root_path(os.path.join(kbcommon.CENSUS_DIR, f"factdiff-{date}.csv"))
    if not a.no_save:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        kbcommon.write_csv(out, LOG_COLS, log, atomic=True)
        write_state(state)
    tally.update(counts)
    tally.update({f"fact-{k}": n for k, n in outc.items()})
    tally.update({f"sections-{k}": n for k, n in secn.items() if n})
    print("detect: " + " ".join(f"{k}={counts[k]}" for k in VERDICTS if counts[k]) + "; facts: "
          + " ".join(f"{k}={outc[k]}" for k in OUTCOMES if outc[k])
          + (f"; sections: changed={secn['changed']} unchanged={secn['unchanged']} (facts kept by section={secn['facts']})"
             if secn["changed"] or secn["unchanged"] else "")
          + ("" if a.no_save else f"; wrote {os.path.relpath(out, kbcommon.HOME)}"))
    return 1 if any(outc[k] for k in REVIEW) else 0


# ---------------------------------------------------------------- revalidation at question time

REVALIDATE_BUDGET_S = 90  # all the requests of one revalidation together: far under the MCP client's idle timeout (5 minutes)
PASSAGE_CHARS = 280  # the new passage a moved fact prints, cut here
LOOKUP_ORDER = ("current", "source-dated only", "moved", "not found")  # best first: a line citing several sources prints the worst
_lookup_guard = threading.Lock()


def lookup_cache_path(sid):
    """The stored result of a source's last revalidation: under _cache/, beside the detection runs' document cache and
    never in a committed ledger (a lookup writes no anchors, state or source rows)."""
    return os.path.join(os.path.dirname(CACHE), "revalidate", ROOT.name, re.sub(r"[^\w.-]", "_", sid) + ".json")


def lookup_cached(sid, keys, pace, now):
    """The stored result of an earlier revalidation of a source when it is younger than `pace` seconds and holds every
    line of `keys`, else None."""
    try:
        with open(lookup_cache_path(sid), encoding="utf-8") as f:
            rec = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(rec, dict) or not isinstance(rec.get("lines"), dict):
        return None
    age = now - (rec.get("checked") if isinstance(rec.get("checked"), (int, float)) else 0)
    return rec if 0 <= age < pace and all(k in rec["lines"] for k in keys) else None


def lookup_store(sid, rec, pace=provider.DELAY):
    """Keep a revalidation's result; a cache that cannot be written never stops a lookup. The lines of the stored result
    of an earlier revalidation of the source still younger than `pace` seconds (lookup_cached's window) with the same
    verdict are kept beside `rec`'s, its own winning, and the record keeps that earlier `checked` and `checked_utc`: a
    line is reused no longer than `pace` after the request that checked it. An older result, or one with another
    verdict, is replaced."""
    old = lookup_cached(sid, [], pace, rec["checked"])
    if old is not None and old.get("verdict") == rec.get("verdict"):
        rec = {**rec, "checked": old["checked"], "checked_utc": old.get("checked_utc", rec.get("checked_utc", "")),
               "lines": {**old["lines"], **rec["lines"]}}
    path = lookup_cache_path(sid)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as f:
            json.dump(rec, f)
        os.replace(path + ".tmp", path)
    except OSError:
        pass


def lookup_hints(ids, srcs, rows, now=None):
    """{source id: {checked_utc, lines, outcomes}} of the sources of `ids` whose last revalidation at question time
    (lookup_cache_path: fact key, outcome, date) is younger than their provider's pacing and found the page unchanged,
    each line it checked `current` or `source-dated only`. A hint only spares a request: it confirms nothing, so detect
    and census.py check never date a source on it. A source a lookup found changed, moved or gone is not a hint, and
    neither is a pinned url (census.py compares its pin with upstream) or one no lookup asked."""
    now = time.time() if now is None else now
    out = {}
    for sid in ids:
        rec = lookup_cached(sid, [], provider.pacing(provider.for_url(srcs[sid]["url"], rows)), now)
        if rec is None or rec.get("verdict") != "unchanged" or not rec["lines"]:
            continue
        outcomes = collections.Counter(v.get("outcome") for v in rec["lines"].values() if isinstance(v, dict))
        if set(outcomes) <= {"current", "source-dated only"}:
            out[sid] = {"checked_utc": rec.get("checked_utc", ""), "lines": len(rec["lines"]), "outcomes": dict(outcomes)}
    return out


def hinted_result(hint):
    """detect_source's result tuple for a source a lookup's stored result spared (lookup_hints): verdict `hinted`, no
    state, document or fact rows, so nothing of it is written or dated."""
    kinds = ", ".join(f"{k}={n}" for k, n in sorted(hint["outcomes"].items()))
    return "hinted", "lookup", f"a lookup revalidated it {hint['checked_utc']} ({kinds}); no request", None, None, None


def line_key(rel, key):
    return f"{rel}|{key}"


def new_passage(text, doc, cites=1):
    """The passage of `doc` (a Doc) that backs a fact now, one line, cut at PASSAGE_CHARS; "" when none does. `cites`:
    Doc.locate's."""
    win, _, _ = doc.locate(fact_text(text), cites)
    if win is None:
        return ""
    p = " ".join(doc.window(*win).split())
    return p if len(p) <= PASSAGE_CHARS else p[:PASSAGE_CHARS].rsplit(" ", 1)[0] + " ..."


def lookup_outcomes(src, rows_f, facts, doc, lost, rows, cites=None):
    """{line key: outcome} of the fact rows `rows_f` of resolve (lookup_source's outcomes) for `facts`, whose current
    document is `doc`; `lost`: why the search for a passage did not finish (search_lost's), "" when it did; `cites`: resolve's."""
    text_of = {(key, rel): text for key, rel, _line, text in facts}
    cur = Doc(doc["text"]) if doc and doc.get("text") else None
    out = {}
    for r in rows_f:
        key, rel = r["fact"], r["path"]
        rec = {"outcome": "", "target": "", "passage": "", "note": r["note"]}
        o = r["outcome"]
        if o == "verbatim":
            rec.update(outcome="current", note="passage word for word" + (" (its section is unchanged)" if r.get("signal") == SECTION_SIGNAL else ""))
        elif o == "modified" and cur is not None:
            rec.update(outcome="moved", target=src["url"], passage=new_passage(text_of[(key, rel)], cur, (cites or {}).get((key, rel), 1)),
                       note="edited in place: " + r["note"])
        elif o == "moved":
            d, _ = page_doc(r["target"], rows)
            rec.update(outcome="moved", target=r["target"],
                       passage=new_passage(text_of[(key, rel)], d, (cites or {}).get((key, rel), 1)) if d is not None else "")
        elif o == "unanchored":
            rec.update(outcome="source-dated only", note="source changed; no located anchor")
        elif o in ("not-found", "dead"):
            if lost:  # the search for the passage did not finish: nothing is known of it
                rec.update(note=lost)
            else:
                rec.update(outcome="not found", note="source gone or replaced" if o == "dead" else r["note"])
        else:
            rec.update(outcome="not found")
        out[line_key(rel, key)] = rec
    return out


def lookup_source(sid, src, res, facts, state, anchors, rows, cites=None):
    """({line key: outcome}, live verdict, why not checked) of one source's detect_source result `res`, for the printed
    `facts` [(fact key, path, line, text)] only. An outcome is {outcome, target, passage, note}: `current` (the source is
    unchanged, or pinned, and the fact has a located anchor confirmed no earlier than the baseline, or its passage is
    found word for word), `moved` (its passage is found on another page, or edited in place: the new passage is kept),
    `not found`, or `source-dated only` (the fact has no located anchor, or an unchanged source's baseline is newer than
    its anchor's last confirmation and no text is at hand to resolve it from, so only its source's state is known; so
    is every fact of a source whose fetched page has no words, as a client-rendered page's is: no passage is
    resolved on it and no other page is searched). A baseline newer than the last confirmation proves only that nothing changed since (confirmable): such a fact is
    resolved against the page as a changed one is. A source that could not be asked has no outcomes and a reason; a fact
    whose search for its passage was cut short by the time budget or a network error has outcome "" and the reason as
    its note. `cites`: resolve's."""
    verdict, signal, ev, _, doc, prev = res
    if verdict == "error":  # a network error, the time budget, a limit or a status that is no answer
        return None, verdict, ev if ev == provider.BUDGET_ERROR or ev.startswith(("HTTP ", "rate limited", provider.DOWN_PREFIX)) else f"network error: {ev}"
    if verdict == "pinned":
        st, why = provider.repository_state(src["url"])
        if st == "" and why:  # the text cannot change, but whether its repository still answers could not be asked
            return None, verdict, f"pinned; its repository was not asked: {why}"
    out = {}
    if verdict == "gone" and signal == "repository":
        return {line_key(rel, key): {"outcome": "not found", "target": "", "passage": "", "note": f"its repository is gone: {ev}"}
                for key, rel, _line, _text in facts}, verdict, ""
    blank = doc is not None and not words_key(doc.get("text") or "")  # a client-rendered page's fetch: no text to resolve against
    if blank and verdict != "unchanged":  # no passage to find on it and none to search for elsewhere: only its state is known
        return {line_key(rel, key): {"outcome": "source-dated only", "target": "", "passage": "",
                                     "note": f"source {verdict}; its page has no words to resolve the passage from"}
                for key, rel, _line, _text in facts}, verdict, ""
    if verdict in ("pinned", "unchanged"):
        head, stale = baseline_head(state.get(sid), doc, prev), []
        for fact in facts:
            key, rel = fact[0], fact[1]
            a = anchors.get((key, rel, sid))
            located = a is not None and a.get("status") == "located"
            # a pinned source with no baseline has none to be newer: its text cannot change
            if located and not (verdict == "pinned" and not head["baseline_utc"]) and not confirmable(head, a.get("verified_utc")):
                stale.append(fact)
                continue
            out[line_key(rel, key)] = {"outcome": "current" if located else "source-dated only", "target": "", "passage": "",
                                       "note": "source unchanged" + ("" if located else "; no located anchor")}
        if stale and doc and doc.get("text") and not blank:
            failed, used = provider.failures(), len(_unanswered_uses)
            rows_f, _ = resolve(sid, src, verdict, doc, prev, stale, anchors, rows, None, True, None, cites)
            out.update(lookup_outcomes(src, rows_f, stale, doc, search_lost(failed, used), rows, cites))
        for key, rel, _line, _text in stale:
            out.setdefault(line_key(rel, key), {"outcome": "source-dated only", "target": "", "passage": "",
                                                "note": "source unchanged; its baseline is newer than the anchor's last confirmation"})
        return out, verdict, ""
    failed, used = provider.failures(), len(_unanswered_uses)
    verdict, ev, rows_f, _ = resolve_source(sid, src, res, state, facts, anchors, rows, lookup=True, cites=cites)
    return lookup_outcomes(src, rows_f, facts, doc, search_lost(failed, used), rows, cites), verdict, ""


def lookup_root(items, out, day, now, reuse=None):
    """revalidate's work for the printed lines of one root (the module's ROOT). `reuse` {source id: seconds}: a stored
    result younger than that is reused, where the provider's pacing alone would ask again."""
    srcs, state, anchors = kbfacts.source_rows(), read_state(), read_anchors()
    rows = provider.providers(ROOT)
    wanted = collections.defaultdict(dict)  # source id -> {(fact key, path): (line, text)}
    cites = {}  # (fact key, path) -> the sources the printed line cites, as cite_counts counts them for the root
    for p in items:
        cites[(p["key"], kbfacts.bare(p["path"]))] = p.get("cites", len(set(p["ids"])))
        for sid in p["ids"]:
            wanted[sid][(p["key"], kbfacts.bare(p["path"]))] = (p["line"], p["text"])
    got, ask, paces = {}, [], {}
    for sid in sorted(wanted):
        src = srcs.get(sid)
        if src is None or not src.get("url"):
            continue
        facts = [(k, rel, ln, text) for (k, rel), (ln, text) in wanted[sid].items()]
        if (src.get("superseded_by") or "").strip():
            out["sources"][sid] = {"state": "offline", "verdict": "", "why": f"superseded by {src['superseded_by'].strip()}"}
            continue
        paces[sid] = pace = max(provider.pacing(provider.for_url(src["url"], rows)), (reuse or {}).get(sid, 0))
        rec = lookup_cached(sid, [line_key(rel, k) for k, rel, _, _ in facts], pace, now)
        if rec is not None:
            got[sid] = (rec["lines"], rec.get("verdict", ""), "", rec.get("checked_utc", day), "cached")
        else:
            ask.append((sid, src, facts))
    results = detect_pass([sid for sid, _, _ in ask], srcs, state, rows, lookup=True) if ask else {}
    for sid, src, facts in ask:
        res = results.get(sid) or ("error", "", provider.BUDGET_ERROR, None, None, None)
        try:
            lines, verdict, why = lookup_source(sid, src, res, facts, state, anchors, rows, cites)
        except Exception as e:  # noqa: BLE001 - one source must never stop a lookup
            lines, verdict, why = None, "error", f"{type(e).__name__}: {e}"[:200]
        if lines is None:
            got[sid] = (None, verdict, why, day, "offline")
            continue
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        lookup_store(sid, {"checked": now, "checked_utc": stamp, "verdict": verdict, "signal": res[1],
                           "lines": {k: v for k, v in lines.items() if v["outcome"]}},
                     paces[sid])
        got[sid] = (lines, verdict, "", stamp, "live")
    for sid, (lines, verdict, why, stamp, how) in got.items():
        out["sources"][sid] = {"state": how, "verdict": verdict, "why": why, "checked_utc": stamp}
    for p in items:
        rel, found, unchecked = kbfacts.bare(p["path"]), [], {}
        for sid in p["ids"]:
            if sid not in got:
                continue
            lines, verdict, why, stamp, how = got[sid]
            rec = (lines or {}).get(line_key(rel, p["key"]))
            if rec is None or not rec["outcome"]:
                unchecked[sid] = why or (rec or {}).get("note") or "not checked"
            else:
                found.append({**rec, "id": sid, "checked_utc": stamp})
        best = max(found, key=lambda r: LOOKUP_ORDER.index(r["outcome"]), default=None)
        out["lines"][(p["path"], p["line"])] = {**(best or {"outcome": ""}), "unchecked": unchecked}


def revalidate(printed, budget=REVALIDATE_BUDGET_S, reuse=None):
    """Check the sources the printed fact lines of a pack cite against their pages now, for the lines printed only:
    `printed` is [{path (qualified), line, key (fact key), text, ids (the cited non-UNK source ids to check), cites
    (optional: the sources the row cites in all, as anchoring counts them, where `ids` holds only some of them)}]. Detection is
    `detect` with no save (detect_source in lookup mode, resolve_source): only the cited sources are asked and only the
    printed facts' anchors are resolved, the requests of all of it within `budget` seconds in all (provider.budget).
    A source asked within its provider's pacing (provider.pacing) is answered from the stored result of that check
    (lookup_cache_path), so a repeated pack asks nothing; `reuse` {source id: seconds} lengthens that for a source to
    its freshness lifetime (provider.lifetime), so a source whose last live check is younger is not asked again.
    Writes only under _cache/ (the stored results; the detection
    cache's documents are left as they are); no anchor, state row, source row or log. Returns {date, lines: {(path, line):
    {outcome (current | moved | not found | source-dated only, "" when no cited source could be checked), id, target,
    passage, note, checked_utc, unchecked: {source id: why}}}, sources: {id: {state: live | cached | offline, verdict,
    why, checked_utc}}}. A source that could not be checked (a network error, the time budget, GitHub's unauthenticated
    limit, a page that did not answer) is `offline` with its reason, and its lines keep the offline stamp."""
    global ROOT
    day = today()
    out = {"date": day, "lines": {}, "sources": {}}
    by_root = collections.defaultdict(list)
    for p in printed:
        if p["ids"]:
            by_root[kbfacts.root_name(p["path"])].append(p)
    if not by_root:
        return out
    with _lookup_guard:
        keep = ROOT
        for cache in (_pages, _searches, _added, _madeup, _unanswered, _unanswered_uses):  # a long-lived process (kb_mcp): no answer of an earlier run
            cache.clear()
        provider.new_run()
        try:
            with provider.budget(budget), provider.down_window():
                for name, items in by_root.items():
                    try:
                        ROOT = kbcommon.root(name or "")
                    except (KeyError, kbcommon.RootError):
                        continue
                    lookup_root(items, out, day, time.time(), reuse)
        finally:
            ROOT = keep
            for cache in (_pages, _searches, _added, _madeup, _unanswered, _unanswered_uses):
                cache.clear()
    return out


# ---------------------------------------------------------------- review and apply

def read_log(path):
    return kbcommon.load_csv(os.path.abspath(path), LOG_COLS)[1]


def _wayback_text(url, before):
    """The text of the last 200 capture of url up to `before` (YYYY-MM-DD) in the Wayback Machine (CDX API), or
    (None, None)."""
    q = (f"https://web.archive.org/cdx/search/cdx?url={urllib.parse.quote(url, safe='')}&output=json&fl=timestamp"
         f"&filter=statuscode:200&to={before.replace('-', '')}&limit=-1")
    r = provider.request(q)
    try:
        rows = json.loads(r["body"]) if r["status"] == 200 else []
    except ValueError:
        rows = []
    if len(rows) < 2:
        return None, None
    ts = rows[-1][0]
    cap = f"https://web.archive.org/web/{ts}id_/{url}"
    c = provider.request(cap)
    if c["status"] != 200:
        return None, None
    return provider.doc_text(c["body"], c["headers"].get("content-type", ""), url), f"https://web.archive.org/web/{ts}/{url}"


def old_passage(sid, anchor, fact, src, offline=False, cites=1):
    """(passage, where) the fact rested on before the change: the snapshot at HEAD (copy sources), the previous
    cached document, a Wayback capture from the anchor's date, or the anchor's quote; (None, why) when none has it.
    `offline`: no Wayback capture is asked for, and the cache of the clone's main worktree is read too. `cites`:
    Doc.locate's."""
    rel = os.path.relpath(snapshot_path(sid), kbcommon.HOME).replace(os.sep, "/")  # git matches tree paths with /
    head = _git(kbcommon.HOME, "cat-file", "blob", f"HEAD:{rel}")  # not `git show` (see calibrate_history)
    tries = []
    if head:
        tries.append((head.partition("\n---\n")[2], "snapshot at HEAD"))
    prev = load_json(prev_path(sid, offline))
    if prev and prev.get("text"):
        tries.append((prev["text"], "previous fetch (_cache)"))
    for text, where in tries:
        d = Doc(text)
        if anchor and anchor.get("sha") in d.shas:
            return d.window(*d.shas[anchor["sha"]]), where
    if anchor and anchor.get("verified_utc") and not offline:
        text, cap = _wayback_text(src["url"], anchor["verified_utc"])
        if text:
            d = Doc(text)
            if anchor.get("sha") in d.shas:
                return d.window(*d.shas[anchor["sha"]]), cap
            win, _, _ = d.locate(fact_text(fact), cites)
            if win:
                return d.window(*win), cap + " (best match)"
    if anchor and anchor.get("quote"):
        return anchor["quote"], "anchor quote"
    return None, "no old text: not a copy source, no cached or archived version"


def review_items(log, srcs, only=None, offline=False):
    """The items of `log` a model must read, each with its old and new passage. `offline`: no request is made (no
    Wayback capture, no page fetch): a passage only the network could give is None."""
    cited = cited_facts()
    facts = {(k, rel, sid): (line, t) for sid, fs in cited.items() for k, rel, line, t in fs}
    cites = cite_counts(cited)
    anchors = read_anchors()
    rows = provider.providers(ROOT)
    for r in log:
        if r["outcome"] not in REVIEW or (only and r["source_id"] not in only):
            continue
        k = (r["fact"], r["path"], r["source_id"])
        line, text = facts.get(k, (r["line"], ""))
        a = anchors.get(k)
        src = srcs.get(r["source_id"], {"url": r["url"]})
        n_cites = cites.get((r["fact"], r["path"]), 1)
        old, where = old_passage(r["source_id"], a, text, src, offline, n_cites)
        new, new_where = None, ""
        url = r["target"] or (src["url"] if r["verdict"] in ("changed", "new", "moved") else "")
        if url:
            cur = load_json(cache_path(r["source_id"], offline)) if url == src["url"] else None
            d = Doc(cur["text"]) if cur and cur.get("text") else None if offline else page_doc(url, rows)[0]
            if d is not None:
                win, cover, _ = d.locate(fact_text(text), n_cites) if text else (None, 0, [])
                if win is None and text:
                    win = d.score(fact_text(text))[0]
                new, new_where = (d.window(*win), url) if win else (None, url)
        yield {"outcome": r["outcome"], "source_id": r["source_id"], "url": src["url"], "verdict": r["verdict"],
               "note": r["note"], "fact": text, "where": f"{ROOT.name}/{r['path']}:{line}", "key": r["fact"], "path": r["path"],
               "old": old, "old_from": where, "new": new, "new_from": new_where}


# ---------------------------------------------------------------- judge: review items in batches, one tool-less call each

JUDGE_MODEL = "claude-haiku-5-5"  # the default model of `review --judge`, the one census.STEP_MODELS["judge"] names; --model overrides it
JUDGE_VERDICTS = ("supported", "contradicted", "not enough information")
JUDGE_BATCH = 20  # items one call judges
JUDGE_BATCH_CHARS = 24_000  # characters of passages one call holds (about 6k tokens); an item alone over it is a batch
JUDGE_PRICE = {"claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}  # USD per MTok in, out (S2131)
JUDGE_CALL_TOKENS = 9_000  # input a tool-less claude -p reads besides the batch (system prompt, schema, task), per call
JUDGE_REPLY_TOKENS = 435  # output per item, thinking tokens included, a failed call's output counted
# Both measured on Haiku 5.5 in the logs census's judge run (kb/_self/reports/fact-diff.md, "Estimate against run"): 4 calls
# read 44,436 tokens, about 8,200 of them passages, and wrote 19,592 for 45 items; the earlier 4_000 and 80 priced it 4.7 times low.
JUDGE_CAP_FACTOR, JUDGE_CAP_FLOOR_USD = 3, 0.05  # a call's --max-budget-usd: this many times its estimate, at least this
JUDGE_TIMEOUT_S = 600
JUDGE_USAGE = (("input_tokens", "input-tokens"), ("cache_creation_input_tokens", "cache-write-tokens"),
               ("cache_read_input_tokens", "cache-read-tokens"), ("output_tokens", "output-tokens"))
JUDGE_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["verdicts"],
    "properties": {"verdicts": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["n", "verdict", "sentence"],
        "properties": {"n": {"type": "integer", "minimum": 1}, "verdict": {"type": "string", "enum": list(JUDGE_VERDICTS)},
                       "sentence": {"type": "string"}}}}}}
JUDGE_TASK = """\
You judge whether facts of a knowledge base still hold after their source changed. Each numbered item gives a fact, the \
passage of its source before the change (old) and the passage now (new). Judge from these passages only; you have no \
other source and no tool.
- supported: the new passage states the fact: the same claim, wording may differ.
- contradicted: the new passage states something that conflicts with the fact.
- not enough information: the new passage neither states nor contradicts the fact, or you cannot settle it from it. \
When in doubt choose this: a wrong `supported` is the one error that costs.
`sentence` is the one sentence of the new passage that decides the item, copied exactly; empty when the new passage has \
none. Return JSON only: {"verdicts": [{"n": 1, "verdict": "supported", "sentence": "..."}]}, one entry per item."""


def judge_candidates(items):
    """The indexes of `items` a model call can judge: those with a new passage (one with none is undecided with no call)."""
    return [i for i, it in enumerate(items) if (it.get("new") or "").strip()]


def judge_text(it):
    return fact_text(it["fact"]) + (it.get("old") or "") + (it.get("new") or "")


def judge_batches(items, size=JUDGE_BATCH, chars=JUDGE_BATCH_CHARS):
    """`items` split in order into batches of at most `size` items and `chars` characters of passages (an item alone
    over `chars` is a batch of its own); each batch a list of items. Deterministic, with no model."""
    out, cur, used = [], [], 0
    for it in items:
        n = len(judge_text(it))
        if cur and (len(cur) >= size or used + n > chars):
            out.append(cur)
            cur, used = [], 0
        cur.append(it)
        used += n
    return out + ([cur] if cur else [])


def judge_prompt(batch):
    """The call's whole input: the task, then each item as `### n`, its fact, old and new passage."""
    parts = [JUDGE_TASK]
    for n, it in enumerate(batch, 1):
        parts.append(f"### {n}\nfact: {fact_text(it['fact'])}\nold: {it.get('old') or '-'}\nnew: {it['new']}")
    return "\n\n".join(parts)


def judge_estimate(batches, model=JUDGE_MODEL):
    """What a judge run reads and costs, with no network and no model: {batches, items, input_tokens, output_tokens,
    usd, cap_usd}; usd and cap_usd None when JUDGE_PRICE has no rate for `model`. cap_usd is the --max-budget-usd of
    the dearest call."""
    cpt = kbusage.CHARS_PER_TOKEN
    ins = [len(judge_prompt(b)) // cpt + JUDGE_CALL_TOKENS for b in batches]
    outs = [len(b) * JUDGE_REPLY_TOKENS for b in batches]
    rate = JUDGE_PRICE.get(model)
    cost = [(i * rate[0] + o * rate[1]) / 1e6 for i, o in zip(ins, outs)] if rate else []
    return {"batches": len(batches), "items": sum(len(b) for b in batches), "input_tokens": sum(ins),
            "output_tokens": sum(outs), "usd": round(sum(cost), 4) if rate else None,
            "cap_usd": call_cap(max(cost)) if cost else None}


def call_cap(usd):
    """The --max-budget-usd of a call whose estimated cost is `usd`: JUDGE_CAP_FACTOR times it, at least the floor."""
    return round(max(JUDGE_CAP_FLOOR_USD, usd * JUDGE_CAP_FACTOR), 2)


def judge_argv(model, cap_usd):
    """The `claude -p` argument list of one call: no tools (`--tools ""`), no hooks, user plugins or MCP servers (as
    redact.names_argv), the verdicts as `structured_output` of a JSON result (`--json-schema` with `--output-format
    json`, claude/ci-and-headless.md) and the call's spend capped (`--max-budget-usd`). The prompt goes on stdin."""
    return [shutil.which("claude") or "claude", "-p", "--model", model, "--tools", "", *kbcommon.NO_HOOKS,
            "--setting-sources", "project,local", "--strict-mcp-config", "--no-session-persistence",
            "--output-format", "json", "--json-schema", json.dumps(JUDGE_SCHEMA, separators=(",", ":")),
            "--max-budget-usd", f"{cap_usd:.2f}"]


def judge_result(stdout):
    """{verdicts: list or None, cost_usd, usage: {name: tokens}, error} of a `claude -p --output-format json` result:
    `structured_output` (else the JSON object in `result`), `total_cost_usd` and the `usage` counts; an error result or
    stdout that is no result names why in `error` and has no verdicts."""
    out = {"verdicts": None, "cost_usd": 0.0, "usage": {}, "error": ""}
    try:
        r = json.loads(stdout)
    except ValueError:
        out["error"] = "stdout is no JSON result"
        return out
    if not isinstance(r, dict):
        out["error"] = "stdout is no JSON result"
        return out
    cost = r.get("total_cost_usd")
    out["cost_usd"] = float(cost) if isinstance(cost, (int, float)) and not isinstance(cost, bool) else 0.0
    use = r.get("usage") if isinstance(r.get("usage"), dict) else {}
    out["usage"] = {name: use[key] for key, name in JUDGE_USAGE
                    if isinstance(use.get(key), int) and not isinstance(use.get(key), bool) and use[key] > 0}
    if r.get("is_error") or str(r.get("subtype", "")).startswith("error"):
        errs = r.get("errors")
        errs = "; ".join(str(e) for e in errs) if isinstance(errs, list) else errs
        out["error"] = str(errs or r.get("result") or r.get("subtype") or "claude -p failed")[:200]
        return out
    got = r.get("structured_output")
    if got is None and isinstance(r.get("result"), str):
        a, b = r["result"].find("{"), r["result"].rfind("}")
        try:
            got = json.loads(r["result"][a:b + 1]) if 0 <= a < b else None
        except ValueError:
            got = None
    if isinstance(got, dict) and isinstance(got.get("verdicts"), list):
        out["verdicts"] = got["verdicts"]
    else:
        out["error"] = "the result holds no verdicts"
    return out


def judge_call(prompt, model, cap_usd):
    """One tool-less model call, in an empty directory so no project instructions load: the `judge_result` of its
    output. The suite replaces this function: no test makes a paid call."""
    with tempfile.TemporaryDirectory() as cwd:
        try:
            p = subprocess.run(judge_argv(model, cap_usd), input=prompt, cwd=cwd, capture_output=True, text=True,
                               encoding="utf-8", timeout=JUDGE_TIMEOUT_S)
        except (OSError, subprocess.SubprocessError) as e:
            return {"verdicts": None, "cost_usd": 0.0, "usage": {}, "error": f"{type(e).__name__}: {e}"[:200]}
    got = judge_result(p.stdout)
    if got["error"] and not p.stdout.strip():
        got["error"] = (p.stderr.strip().splitlines() or [f"claude -p exited {p.returncode}"])[-1][:200]
    return got


def judge_verdicts(batch, verdicts):
    """{index in batch: {verdict, sentence, note}} of a reply's `verdicts`. An entry that is malformed, names an item
    outside the batch or a verdict outside JUDGE_VERDICTS, or repeats an item, is left out (the item stays
    unjudged). A `supported` whose sentence is not in the item's new passage (normalized) is not believed: it is `not
    enough information`, noted."""
    out = {}
    for v in verdicts:
        n = v.get("n") if isinstance(v, dict) else None
        if not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= len(batch) or n - 1 in out:
            continue
        verdict, sentence = v.get("verdict"), v.get("sentence")
        if verdict not in JUDGE_VERDICTS or not isinstance(sentence, str):
            continue
        note = ""
        if verdict == "supported" and not (norm(sentence) and norm(sentence) in norm(batch[n - 1]["new"])):
            verdict, note = "not enough information", "supported without a sentence of the new passage"
        out[n - 1] = {"verdict": verdict, "sentence": " ".join(sentence.split()), "note": note}
    return out


def judge_items(items, model=JUDGE_MODEL, size=JUDGE_BATCH, jobs=4, cap_usd=None, call=None):
    """(verdicts, calls) of the judgeable `items` (those with a new passage), in batches of one call each: `verdicts`
    is {index in `items`: {verdict, sentence, note}} for the items a reply judged, `calls` one record per batch
    ({items, cost_usd, usage, error}). `cap_usd` is each call's --max-budget-usd (else from its estimate); `call`
    replaces judge_call."""
    call = call or judge_call
    idx, batches, at = judge_candidates(items), [], 0
    for b in judge_batches([items[i] for i in idx], size):
        batches.append(idx[at:at + len(b)])
        at += len(b)
    caps = [cap_usd or judge_estimate([[items[i] for i in b]], model)["cap_usd"] or JUDGE_CAP_FLOOR_USD for b in batches]

    def one(job):
        b, cap = job
        return call(judge_prompt([items[i] for i in b]), model, cap)

    with cf.ThreadPoolExecutor(max(1, min(jobs, len(batches) or 1))) as ex:
        replies = list(ex.map(one, zip(batches, caps)))
    verdicts, calls = {}, []
    for b, reply in zip(batches, replies):
        got = judge_verdicts([items[i] for i in b], reply["verdicts"] or [])
        verdicts.update({b[k]: v for k, v in got.items()})
        calls.append({"items": len(b), "cost_usd": reply["cost_usd"], "usage": reply["usage"],
                      "error": reply["error"] or ("" if got or not b else "no entry matched an item")})
    return verdicts, calls


def judge_tally(tally, verdicts, calls):
    """Add a judge run's counts to `tally` (the census.phase row): the verdicts, the calls and failed calls, the
    tokens of each kind and the spend in millionths of a dollar (a row's count is an integer)."""
    tally.update(v["verdict"] for v in verdicts.values())
    tally["calls"] += len(calls)
    tally["failed"] += sum(1 for c in calls if c["error"])
    for c in calls:
        tally.update(c["usage"])
    tally["cost-usd-micro"] += round(sum(c["cost_usd"] for c in calls) * 1e6)


def judge_lines(calls):
    """The summary lines of a judge run: calls, failures, tokens and the spend its results report."""
    toks = collections.Counter()
    for c in calls:
        toks.update(c["usage"])
    spent = sum(c["cost_usd"] for c in calls)
    out = [f"judge calls={len(calls)} failed={sum(1 for c in calls if c['error'])} " + " ".join(
        f"{name}={toks[name]}" for _, name in JUDGE_USAGE) + f" total_cost_usd={spent:.4f}"]
    out += [f"  call {n} failed: {c['error']}" for n, c in enumerate(calls, 1) if c["error"]]
    return out


def estimate_lines(est, model, what):
    """The dry run's lines: the batches and the tokens and USD they would cost, as `queue_lines` counts a queue."""
    cap = f" cap per call=${est['cap_usd']:.2f}" if est["cap_usd"] is not None else ""
    usd = f"usd~{est['usd']:.4f}{cap}" if est["usd"] is not None else f"usd unknown (no rate for {model}: pass --max-budget-usd)"
    return [f"judge dry run (no network, no model): {what}: model={model} batches={est['batches']} items={est['items']} "
            f"input tokens~{est['input_tokens']} output tokens~{est['output_tokens']} {usd}"]


def cmd_review(a, tally):
    items = list(review_items(read_log(a.log), sources(), set(a.source) or None))
    tally.update(it["outcome"] for it in items)
    if a.json and not a.judge:
        print(json.dumps(items, indent=1))
        return 0
    if a.judge and a.dry_run:
        size = a.batch_size or JUDGE_BATCH
        batches = judge_batches([items[i] for i in judge_candidates(items)], size)
        print("\n".join(estimate_lines(judge_estimate(batches, a.model), a.model, f"{len(items)} review item(s)")))
        return 0
    verdicts, calls = judge_items(items, a.model, a.batch_size or JUDGE_BATCH, cap_usd=a.max_budget_usd) if a.judge else ({}, [])
    if a.judge:
        judge_tally(tally, verdicts, calls)
        if a.json:
            print(json.dumps([{**it, "judge": verdicts.get(i)} for i, it in enumerate(items)], indent=1))
            return 1 if any(c["error"] for c in calls) else 0
    for n, it in enumerate(items, 1):
        got = verdicts.get(n - 1)
        decide = (f"{got['verdict']}" + (f" ({got['sentence']})" if got["sentence"] else "") + (f" [{got['note']}]" if got["note"] else "")
                  if got else "supported | contradicted | not enough info")
        print(f"## {n}. {it['outcome']} {it['source_id']} {it['where']}\n- fact: {fact_text(it['fact'])}\n"
              f"- source: {it['url']} ({it['verdict']}; {it['note']})\n- old ({it['old_from']}): {it['old'] or '-'}\n"
              f"- new ({it['new_from'] or '-'}): {it['new'] or '-'}\n- {'judged' if got else 'decide'}: {decide}\n")
    print(f"review items={len(items)}")
    if a.judge:
        print("\n".join(judge_lines(calls)))
        return 1 if any(c["error"] for c in calls) else 0
    return 0


SUFFIX = re.compile(r"(?:;\s*)?confirmed \d{4}-\d{2}-\d{2}: [^;]*$")


def repoint(path, key, old_id, new_id):
    """Replace old_id by new_id in the tags of the fact whose key is `key` in a root file; True when done."""
    full = root_path(path)
    text = kbcommon.read(full, newline="")
    if text is None:
        return False
    for u in kbfacts.units(kbcommon.qualify(ROOT, path)):
        if kbfacts.fact_key(u["text"]) != key or kbfacts.bare(u["path"]) != path:
            continue
        lines = text.split("\n")
        i = u["line"] - 1
        j = i
        while j < len(lines) and old_id not in lines[j] and j < i + 30:
            j += 1
        if j >= len(lines) or old_id not in lines[j]:
            return False
        lines[j] = re.sub(rf"(?<![\w-]){re.escape(old_id)}(?![\w-])", new_id, lines[j])
        for k, ln in enumerate(lines[:40]):  # an article lists its sources in its front matter
            if k and ln == "---":
                break
            if ln.startswith("sources:") and new_id not in ln:
                lines[k] = re.sub(r"\]\s*$", f", {new_id}]", ln)
        with open(full, "w", encoding="utf-8", newline="") as f:
            f.write("\n".join(lines))
        return True
    return False


def cmd_apply(a, tally):
    """Apply what needs no model: sources whose facts were all found word for word (or that did not change) are
    confirmed and re-dated, their anchors dated; a fact found word for word on another page is re-pointed to a new
    source row for that page. The rest waits for review (factdiff.py review). A confirmation needs the compared text
    to be no newer than the source's last confirmation (confirmable(); an anchor found word for word counts when it
    was placed no later than that): the first baseline after a census proves nothing about the days between, so those
    sources are `held back` until a census or refresh confirms them."""
    import build_index
    log, srcs = read_log(a.log), sources()
    date = a.date or today()
    anchors = read_anchors()
    facts = cited_facts()
    by_src = collections.defaultdict(list)
    for r in log:
        by_src[r["source_id"]].append(r)
    confirmed, moved_to, n_verbatim, n_moved, held = {}, collections.defaultdict(list), 0, 0, 0
    for sid, rs in by_src.items():
        head = rs[0]
        fr = [r for r in rs if r["fact"]]
        retrieved = srcs.get(sid, {}).get("retrieved_utc", "")
        # a fact kept by its section is as old as the baseline the section was hashed at: it needs that baseline to be
        # no newer than the last confirmation, as an unchanged source does
        kept = lambda r: r["outcome"] == "verbatim" and (r["signal"] != SECTION_SIGNAL or confirmable(head, retrieved))  # noqa: E731
        if head["verdict"] == "unchanged":
            if not confirmable(head, retrieved):
                held += 1
                continue
            confirmed[sid] = f"fact diff: unchanged ({head['signal']})"
            for k, rel, _, _ in facts.get(sid, []):
                if (k, rel, sid) in anchors:
                    anchors[(k, rel, sid)]["verified_utc"] = date
        elif head["verdict"] in ("changed", "new", "moved") and fr and all(kept(r) for r in fr) \
                and len(fr) == len(facts.get(sid, [])) and all(anchors[(r["fact"], r["path"], sid)]["verified_utc"][:10]
                                                                <= retrieved[:10] for r in fr):
            confirmed[sid] = f"fact diff: {len(fr)} anchor(s) verbatim"
        for r in fr:
            if kept(r) and anchors[(r["fact"], r["path"], sid)]["verified_utc"][:10] <= retrieved[:10]:
                anchors[(r["fact"], r["path"], sid)]["verified_utc"] = date
                n_verbatim += 1
            elif r["outcome"] == "moved" and r["target"]:
                moved_to[sid].append(r)
    new_rows = {}
    for sid, rs in moved_to.items():
        for r in rs:
            nid = kbid.source_id(r["target"], ROOT.id_prefix)
            if nid not in srcs and nid not in new_rows:
                old = srcs[sid]
                new_rows[nid] = {**{c: "" for c in old}, "id": nid, "url": r["target"], "title": f"moved from {sid}: {old.get('title', '')}"[:200],
                                 "publisher": old.get("publisher", ""), "licence": old.get("licence", ""), "reuse": old.get("reuse", ""),
                                 "retrieved_utc": date, "version_or_date": f"fact diff {date}: passage of {sid} found word for word"}
            if not a.dry_run and repoint(r["path"], r["fact"], sid, nid):
                a_old = anchors.pop((r["fact"], r["path"], sid), None)
                if a_old:
                    anchors[(r["fact"], r["path"], nid)] = {**a_old, "source_id": nid, "verified_utc": date}
                n_moved += 1
        targets = {r["target"] for r in rs}
        if len(targets) == 1 and len(rs) == len(facts.get(sid, [])):
            srcs[sid]["superseded_by"] = kbid.source_id(next(iter(targets)), ROOT.id_prefix)
    hdr, rows = kbcommon.load_csv(root_path(kbcommon.SOURCES), ("id",))
    for r in rows:
        if r["id"] in confirmed:
            vod = SUFFIX.sub("", r["version_or_date"]).rstrip("; ")
            r["version_or_date"] = (vod + "; " if vod else "") + f"confirmed {date}: {confirmed[r['id']]}"
            r["retrieved_utc"] = date
        if srcs.get(r["id"], {}).get("superseded_by") and not r.get("superseded_by"):
            r["superseded_by"] = srcs[r["id"]]["superseded_by"]
    rows += list(new_rows.values())
    dated = {r["id"] for r in rows if r["retrieved_utc"][:10] == date}
    articles = []
    for dirpath, dirs, files in os.walk(ROOT.path):
        dirs[:] = [d for d in dirs if not d.startswith(("_", "."))]
        for fn in files:
            if not fn.endswith(".md") or dirpath == ROOT.path:
                continue
            full = os.path.join(dirpath, fn)
            text = kbcommon.read(full, newline="")
            fm = build_index.front_matter(text) or {}
            ids = kbid.SOURCE_ID.findall(str(fm.get("sources", "")))
            if ids and "retrieved_utc" in fm and all(i in dated for i in ids) and str(fm["retrieved_utc"])[:10] != date \
                    and any(i in confirmed for i in ids):
                articles.append((full, re.sub(r"(?m)^retrieved_utc:.*$", f"retrieved_utc: {date}", text, count=1)))
    tally.update({"confirmed": len(confirmed), "held-back": held, "verbatim": n_verbatim, "moved": n_moved,
                  "new-rows": len(new_rows), "articles": len(articles)})
    print(f"apply {date}: sources confirmed={len(confirmed)} held back={held} facts verbatim={n_verbatim} facts moved={n_moved} "
          f"new source rows={len(new_rows)} articles re-dated={len(articles)}" + (" (dry run: nothing written)" if a.dry_run else ""))
    if a.dry_run:
        return 0
    kbcommon.write_csv(root_path(kbcommon.SOURCES), hdr, rows, atomic=True)
    write_anchors(anchors)
    for full, text in articles:
        with open(full, "w", encoding="utf-8", newline="") as f:
            f.write(text)
    if a.commit and (confirmed or n_moved):
        paths = [root_path(kbcommon.SOURCES), root_path(ANCHORS), root_path(kbcommon.STATE), os.path.abspath(a.log),
                 root_path(kbcommon.SNAPSHOTS)] + [f for f, _ in articles] + sorted({root_path(r["path"]) for rs in moved_to.values() for r in rs})
        paths = [p for p in paths if os.path.exists(p)]
        if _git(kbcommon.HOME, "add", "--", *paths) is None:
            print("git add failed; nothing committed")
            return 1
        msg = (f"docs(kb): fact diff {date}: confirm {len(confirmed)} source(s)\n\nfactdiff.py apply --auto on "
               f"{os.path.relpath(os.path.abspath(a.log), kbcommon.HOME)}: {n_verbatim} fact(s) found word for word, {n_moved} "
               f"moved to another page; no model read them.\n")
        if _git(kbcommon.HOME, "commit", "-q", "-m", msg, "--trailer", f"KB-Verified: {date}") is None:
            print("git commit failed (hooks or nothing to commit)")
            return 1
        print("committed with KB-Verified: " + date)
    return 0


def last_capture(url):
    """The Wayback url of the last 200 capture of `url` (CDX API), or ''."""
    q = (f"https://web.archive.org/cdx/search/cdx?url={urllib.parse.quote(url, safe='')}&output=json&fl=timestamp"
         f"&filter=statuscode:200&limit=-1")
    r = provider.request(q)
    try:
        rows = json.loads(r["body"]) if r["status"] == 200 else []
    except ValueError:
        rows = []
    return f"https://web.archive.org/web/{rows[-1][0]}/{url}" if len(rows) > 1 else ""


def part_text(p, ids=None):
    """One parsed tag part as it is written: its kind, then its source ids (`ids` replaces them), or the id of its
    DECISION or LOG (kept apart from `ids` by parse_tag), then `: note`."""
    refs = p["ids"] if ids is None else ids
    ident = ", ".join(refs) or p.get("decision") or p.get("log") or ""
    return f"{p['kind']} {ident}".strip() + (f": {p['note']}" if p["note"] else "")


def drop_citation(path, key, sid, why):
    """In the fact `key` of a root file: remove `sid` from its tag, or turn the part into `UNK: why` when `sid` was its
    only id. True when the file changed."""
    full = root_path(path)
    text = kbcommon.read(full, newline="")
    for u in kbfacts.units(kbcommon.qualify(ROOT, path)):
        if kbfacts.fact_key(u["text"]) != key or kbfacts.bare(u["path"]) != path:
            continue
        lines = text.split("\n")
        for j in range(u["line"] - 1, min(len(lines), u["line"] + 30)):
            m = next((t for t in kbfacts.TAG.findall(lines[j]) if re.search(rf"(?<![\w-]){re.escape(sid)}(?![\w-])", t)), None)
            if not m:
                continue
            parts = kbfacts.parse_tag(m)
            out = []
            for p in parts:
                if sid in p["ids"]:
                    ids = [i for i in p["ids"] if i != sid]
                    out.append(part_text(p, ids) if ids else f"UNK: {why}")
                else:
                    out.append(part_text(p))
            lines[j] = lines[j].replace(m, "[" + "; ".join(out) + "]")
            with open(full, "w", encoding="utf-8", newline="") as f:
                f.write("\n".join(lines))
            return True
    return False


def cmd_dead(a):
    """A source gone with no successor (after review): its facts lose the citation (UNK when it was their only one),
    each topic gets a _gaps.md entry, and the source row is marked dead with its last Wayback capture."""
    log, srcs = read_log(a.log), sources()
    date = a.date or today()
    sid = kbid.canonical_id(a.source)
    rs = [r for r in log if r["source_id"] == sid and r["fact"]]
    if not rs or sid not in srcs:
        print(f"no fact rows for {sid} in the log")
        return 2
    cap = last_capture(srcs[sid]["url"]) if not a.no_archive else ""
    why = f"source {sid} gone {date}" + (f", last capture {cap}" if cap else "")
    changed, topics = 0, collections.defaultdict(list)
    for r in rs:
        if drop_citation(r["path"], r["fact"], sid, why):
            changed += 1
            topics[r["path"].rsplit(".", 1)[0]].append(r["line"])
    hdr, rows = kbcommon.load_csv(root_path(kbcommon.SOURCES), ("id",))
    for row in rows:
        if row["id"] == sid:
            row["version_or_date"] = (row["version_or_date"] + "; " if row["version_or_date"] else "") + \
                f"dead {date}: {rs[0]['verdict']} ({rs[0]['evidence']})" + (f", last capture {cap}" if cap else ", no Wayback capture")
    kbcommon.write_csv(root_path(kbcommon.SOURCES), hdr, rows, atomic=True)
    gaps = root_path(kbcommon.GAPS)
    with open(gaps, "a", encoding="utf-8", newline="") as f:
        for topic, lines in sorted(topics.items()):
            f.write(f"\n- Source {sid} ({srcs[sid]['url']}) is gone ({rs[0]['verdict']}, {date}) and no page holds its passages "
                    f"(fact diff: provider search and redirects checked); facts at lines {', '.join(map(str, lines))} lost it"
                    + (f"; last capture {cap}" if cap else "") + f". (topic: {topic})\n")
    anchors = read_anchors()
    for r in rs:
        if (r["fact"], r["path"], sid) in anchors:
            anchors[(r["fact"], r["path"], sid)].update(status="unlocated:gone", heading="", terms="", sha="", quote="")
    write_anchors(anchors)
    print(f"dead {sid}: {changed} fact(s) lost the citation, {len(topics)} gap entr(ies)" + (f", last capture {cap}" if cap else ""))
    return 0


def select_ids(a, srcs):
    """Source ids of fetch.py's selection flags (every source when none is given)."""
    import fetch
    fetch.KB = ROOT.path
    a.file = [root_rel(f) for f in a.file]
    a.selected = bool(a.topic or a.dir or a.file or a.source)
    ns = argparse.Namespace(topic=a.topic, dir=a.dir, file=a.file, source=a.source, older_than=None)
    return fetch.select(ns, srcs, {})


def print_breakdown(anchors):
    """Located and no-match pairs by provider host and by tag kind (the pairs whose source returned text), most
    no-match first: where an anchoring rule has most to gain."""
    srcs = sources()
    kinds = collections.defaultdict(set)
    for u in kbfacts.units(ROOT.name):
        for part in u["tags"]:
            for sid in part["ids"] if part["kind"] != "UNK" else ():
                kinds[(kbfacts.fact_key(u["text"]), kbfacts.bare(u["path"]), sid)].add(part["kind"])
    by = {"host": collections.defaultdict(collections.Counter), "kind": collections.defaultdict(collections.Counter)}
    for k, r in anchors.items():
        if r["status"] not in ("located", "unlocated:no-match") or k[2] not in srcs:
            continue
        status = "located" if r["status"] == "located" else "no-match"
        by["host"][urllib.parse.urlsplit(srcs[k[2]]["url"]).netloc][status] += 1
        by["kind"]["+".join(sorted(kinds.get(k, {"?"})))][status] += 1
    for name, groups in by.items():
        print(f"by {name}: no-match, located, located share")
        for g, c in sorted(groups.items(), key=lambda kv: (-kv[1]["no-match"], kv[0]))[:25 if name == "host" else None]:
            print(f"  {g:<40} {c['no-match']:>5} {c['located']:>5} {100 * c['located'] // (c['located'] + c['no-match']):>3}%")
    return 0


def cmd_anchors(a):
    anchors = read_anchors()
    if a.source:
        anchors = {k: v for k, v in anchors.items() if k[2] in {kbid.canonical_id(s) for s in a.source}}
    if a.stale:
        live = {(k, rel, sid) for sid, fs in cited_facts().items() for k, rel, _, _ in fs}
        stale = [k for k in anchors if k not in live]
        for k in stale:
            print(f"STALE {k[1]} {k[0]} {k[2]}")
        print(f"stale={len(stale)}")
        return 1 if stale else 0
    if a.breakdown:
        return print_breakdown(anchors)
    if a.unlocated:
        facts = cited_facts()
        text = {(k, rel, sid): (line, t) for sid, fs in facts.items() for k, rel, line, t in fs}
        n = 0
        for k, r in sorted(anchors.items(), key=lambda kv: (kv[0][1], kv[0][2])):
            if r["status"] != "located":
                line, t = text.get(k, ("?", ""))
                print(f"{r['status']:<22} {ROOT.name}/{k[1]}:{line} {k[2]}  {t[:100]}")
                n += 1
        print(f"unlocated={n}")
        return 0
    c = collections.Counter(r["status"] for r in anchors.values())
    facts = cited_facts()
    pairs = sum(len(v) for v in facts.values())
    print(f"anchors={len(anchors)} of {pairs} fact-source pairs; " + " ".join(f"{k}={v}" for k, v in sorted(c.items())))
    return 0


PHASES = {"detect": cmd_detect, "review": cmd_review, "apply": cmd_apply}  # each writes a census.phase ops row


def main():
    global ROOT
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default="public", help="the root to work on (default public)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    an = sub.add_parser("anchor", help="locate facts in their sources and write _anchors.csv")
    for p in (an,):
        p.add_argument("--topic", action="append", default=[])
        p.add_argument("--dir", action="append", default=[])
        p.add_argument("--file", action="append", default=[])
        p.add_argument("--source", action="append", default=[])
    an.add_argument("--refetch", action="store_true", help="ignore cached documents")
    an.add_argument("--max-age", type=float, default=7, help="reuse cached documents up to DAYS old (default 7)")
    an.add_argument("--dry-run", action="store_true")
    an.add_argument("--quotes", metavar="CSV", help=f"the quote each new fact of the one --file rests on, at most {QUOTE_WORDS} "
                                                     "words, as a CSV of `line,quote` or, for a fact that cites several sources, `line,source,quote`")
    an.add_argument("--propose", action="store_true", help="print, for each fact of the one --file that holds no located anchor, the "
                                                           "passage of each cited page that best holds it as a `line,source,quote` "
                                                           "CSV line; writes nothing")
    sn =sub.add_parser("snapshot", help="write the normalized text of the root's live copy sources to _snapshots/")
    for p in (sn,):
        p.add_argument("--topic", action="append", default=[])
        p.add_argument("--dir", action="append", default=[])
        p.add_argument("--file", action="append", default=[])
        p.add_argument("--source", action="append", default=[])
    sn.add_argument("--refetch", action="store_true", help="ignore cached documents")
    sn.add_argument("--max-age", type=float, default=7, help="reuse cached documents up to DAYS old (default 7)")
    sn.add_argument("--dry-run", action="store_true", help="count and size only")
    de = sub.add_parser("detect", help="detect changed sources, resolve each fact, write _census/factdiff-<date>.csv")
    for p in (de,):
        p.add_argument("--topic", action="append", default=[])
        p.add_argument("--dir", action="append", default=[])
        p.add_argument("--file", action="append", default=[])
        p.add_argument("--source", action="append", default=[])
    de.add_argument("--date", help="log date (default today)")
    de.add_argument("--out", help="log path (default _census/factdiff-<date>.csv)")
    de.add_argument("--no-save", action="store_true", help="write no log, state or snapshot")
    de.add_argument("--sitemaps", action="store_true", help="also diff each involved provider's sitemap (added urls)")
    rv = sub.add_parser("review", help="the facts a model must read: old and new passage each, never whole pages")
    rv.add_argument("log")
    rv.add_argument("--source", action="append", default=[])
    rv.add_argument("--json", action="store_true")
    rv.add_argument("--judge", action="store_true", help=f"judge each item with a tool-less model call (batches of {JUDGE_BATCH}): "
                                                         "supported, contradicted or not enough information")
    rv.add_argument("--model", default=JUDGE_MODEL, help=f"the model of --judge (default {JUDGE_MODEL})")
    rv.add_argument("--batch-size", type=int, metavar="N", help=f"items per call of --judge (default {JUDGE_BATCH})")
    rv.add_argument("--max-budget-usd", type=float, metavar="USD", help="--judge: each call's cap (default from its estimate)")
    rv.add_argument("--dry-run", action="store_true", help="--judge: print the batches and the estimated tokens and USD, call nothing")
    ap_ = sub.add_parser("apply", help="apply what needs no model: confirm, re-date, re-point moved facts")
    ap_.add_argument("log")
    ap_.add_argument("--date", help="confirmation date (default today)")
    ap_.add_argument("--dry-run", action="store_true")
    ap_.add_argument("--commit", action="store_true", help="commit the result with a KB-Verified trailer")
    dd = sub.add_parser("dead", help="after review: a gone source with no successor: facts to UNK, gaps, dead marker")
    dd.add_argument("log")
    dd.add_argument("--source", required=True)
    dd.add_argument("--date", help="default today")
    dd.add_argument("--no-archive", action="store_true", help="do not look up the last Wayback capture")
    ca = sub.add_parser("calibrate", help="measure cut-offs: history (a docs repository's versions) or soft404 (live)")
    ca.add_argument("what", choices=("history", "soft404"))
    ca.add_argument("--repo", help="history: a git repository of documentation (a bare clone is fine)")
    ca.add_argument("--path", action="append", default=[], help="history: path prefixes in the repository (repeatable)")
    ca.add_argument("--since", default="2025-09-01", help="history: commits since this date (default 2025-09-01)")
    ca.add_argument("--pairs", type=int, default=150, help="history: page versions sampled (default 150)")
    ca.add_argument("--hosts", type=int, default=60, help="soft404: hosts sampled (default 60)")
    ca.add_argument("--seed", type=int, default=1)
    ls = sub.add_parser("anchors", help="list anchors: counts, --unlocated, --stale")
    ls.add_argument("--unlocated", action="store_true")
    ls.add_argument("--stale", action="store_true")
    ls.add_argument("--breakdown", action="store_true", help="no-match and located pairs by provider host and tag kind")
    ls.add_argument("--source", action="append", default=[])
    a = ap.parse_args()
    try:
        ROOT = kbcommon.root(a.root)
    except (KeyError, kbcommon.RootError):
        ap.error(f"--root {a.root}: no such root")
    kbcommon.KB = ROOT.path
    if a.cmd == "anchor" and (a.quotes or a.propose) and len(a.file) != 1:
        ap.error(f"{'--quotes' if a.quotes else '--propose'} needs exactly one --file: its lines are that file's")
    if a.cmd == "anchor" and a.propose and (a.quotes or a.topic or a.dir or a.source):
        ap.error("--propose takes one --file and no other selector and no --quotes")
    if a.cmd == "calibrate" and a.what == "history" and not a.repo:
        ap.error("calibrate history needs --repo")
    if a.cmd == "review" and not a.judge and (a.dry_run or a.batch_size or a.max_budget_usd):
        ap.error("--dry-run, --batch-size and --max-budget-usd need --judge")
    if a.cmd in PHASES:
        run = lambda tally: PHASES[a.cmd](a, tally)  # noqa: E731
        if getattr(a, "dry_run", False):
            return run(collections.Counter())
        return ql_capture.census_phase(a.cmd, run, ql_capture.phase_date(getattr(a, "date", None), getattr(a, "log", None)))
    return {"anchor": cmd_anchor, "anchors": cmd_anchors, "snapshot": cmd_snapshot, "calibrate": cmd_calibrate,
            "dead": cmd_dead}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
