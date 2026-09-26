#!/usr/bin/env python3
"""Facts, fact tags and ledger entries of the kb, parsed one way for every tool (stdlib only).

rag.py (pack, facts, audit, src --cited, eval), kb_mcp.py, check.py and the kb-verify lint all read the kb through
this module, so a count or a join gives the same answer whichever tool asks.

Tag grammar. A tag is `[PART; PART ...]`; a PART is `KIND[/KIND] [from] [IDS] [NOTE]`:
  KIND  DOC | DER | COMMUNITY | UNK
  IDS   source ids (S123, S-k3f7q2zd) separated by commas or spaces
  NOTE  free text after `:`, ` - `, ` — ` or `,` (a derivation, a pointer to _gaps.md, ...)
A `;` or `,` directly followed by a KIND starts the next part, so `[DOC S1208, COMMUNITY S1209]` has two parts and
`[DER S328,S329: different property; Type has no table]` has one. Canonical form: `[DOC S1, S2]`, `[DER S1: how]`,
`[UNK]` or `[UNK: why]`. DOC and COMMUNITY parts must name at least one source id (kb-verify lint reports those
that do not).

Fact units. In an article (a .md with `topic:` front matter): a bullet with its continuation lines, a table row, or
a paragraph line that carries at least one tag. In a data .csv: a row. Each unit has its path, first line, section,
text and parsed tags.

Ledger entries. `_gaps.md` and `_conflicts.md` are split into entries: a top-level `- ` bullet with its
continuation lines, or a `### ` block. An entry is linked to a topic explicitly (a `topic: <domain>/<slug>` marker,
a path of an existing topic file in its text, or a `## <domain>/<slug>` section heading) or through its sources
(a source id in the entry whose `used_in` names the topic's files). New entries carry an explicit
`topic: <domain>/<slug>` marker.

The pack index. `store()` holds the pack corpus as postings lists (per term: the units that hold it). A process
that finds an index file for the current fingerprint (sha1 over path, mtime and size of every file the tools read)
reads only the postings of the question's words from it (stdlib sqlite3); otherwise it builds the corpus, answers
from memory and saves the index for the next process. Output is identical either way: scores are summed in the same
term order per unit and ties keep corpus order. Where the file goes: `index_path()`.
"""
import array, csv, functools, hashlib, io, json, math, os, re, sqlite3, sys, tempfile, threading, time
from collections import Counter, defaultdict

TOOLS = os.path.dirname(os.path.abspath(__file__))
KB = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import kbid  # noqa: E402

KINDS = ("DOC", "DER", "COMMUNITY", "UNK")
SKIP_DIRS = {"_tools", "_private", "_cache", "_census", "artifacts"}
TAG = re.compile(r"\[(?:DOC|DER|COMMUNITY|UNK)\b[^\]]*\]")
ID = re.compile(r"\bS-[a-z2-7]{8}\b|\bS\d{3,4}\b")
_PART_SPLIT = re.compile(r"\s*[;,]\s*(?=(?:DOC|DER|COMMUNITY|UNK)\b)")
_PART = re.compile(r"(DOC|DER|COMMUNITY|UNK)(?:/(DOC|DER|COMMUNITY|UNK))?\b\s*(?:from\s+)?"
                   r"((?:S-[a-z2-7]{8}|S\d{3,4})(?:[\s,]+(?:S-[a-z2-7]{8}|S\d{3,4})\b)*)?(.*)", re.S)
TOPIC_MARK = re.compile(r"\btopic:\s*`?([a-z0-9-]+/[a-z0-9./-]+?)`?(?=[\s,;.)\]]|$)")
csv.field_size_limit(2**31 - 1)


# ---------------------------------------------------------------- tags

def parse_tag(tag):
    """`[DOC S1, S2; UNK: why]` -> [{"kind": "DOC", "ids": ["S1", "S2"], "note": ""}, {"kind": "UNK", ...}]."""
    inner = " ".join(tag.strip()[1:-1].split())
    parts = []
    for seg in _PART_SPLIT.split(inner):
        m = _PART.match(seg)
        if not m:  # a `;` inside a note: belongs to the previous part
            if parts:
                parts[-1]["note"] = (parts[-1]["note"] + "; " + seg).strip("; ")
            continue
        parts.append({"kind": m.group(1), "ids": ID.findall(m.group(3) or ""),
                      "note": m.group(4).strip().lstrip(":,—–- ").strip()})
    return parts


def tags_in(text):
    """Every tag in a text as parsed parts, flattened."""
    return [p for t in TAG.findall(text) for p in parse_tag(t)]


def kinds_of(parts):
    return sorted({p["kind"] for p in parts}, key=KINDS.index)


# ---------------------------------------------------------------- files

def read(rel):
    try:
        with open(os.path.join(KB, rel), encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


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


def kb_files(exts=(".md", ".csv")):
    """Domain files (not the root index files), sorted."""
    for root, dirs, files in os.walk(KB):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        if root == KB:
            continue
        for f in sorted(files):
            if f.endswith(exts):
                yield os.path.relpath(os.path.join(root, f), KB).replace(os.sep, "/")


_CACHE = {}
FP_MEMO = 2.0  # seconds: one command computes the fingerprint once; a long-running server sees an edit on its next call
_FP = [0.0, None]


def fingerprint():
    """sha1 over (path, mtime_ns, size) of every file the tools read (domain .md/.csv, _sources.csv, the ledgers,
    aliases.csv, signals.csv, doc2query/expansions.csv, this module and kbid.py) and KB_DOC2QUERY: any edit gives a
    new value. Replaces a time-to-live cache: nothing is rebuilt while no file changed, however long a server idles."""
    now = time.monotonic()
    if _FP[1] is not None and now - _FP[0] < FP_MEMO:
        return _FP[1]
    h = hashlib.sha1(f"{INDEX_VERSION}|{os.environ.get('KB_DOC2QUERY', '')}".encode())
    extra = ["_sources.csv", "_gaps.md", "_conflicts.md", "_answers.md", "_tools/aliases.csv", "_tools/signals.csv",
             "_tools/doc2query/expansions.csv", "_tools/kbfacts.py", "_tools/kbid.py"]
    for rel in list(kb_files()) + extra:
        try:
            st = os.stat(os.path.join(KB, rel))
            h.update(f"{rel}\0{st.st_mtime_ns}\0{st.st_size}\n".encode())
        except OSError:
            h.update(f"{rel}\0-\n".encode())
    _FP[:] = [now, h.hexdigest()]
    return _FP[1]


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
    out = {}
    for rel in kb_files((".md",)):
        text = read(rel)
        if text and is_article(text):
            out[rel] = front_matter(text)
    return out


def topic_files():
    """{topic: [files]}: an article's own .md, its `files:` list, and same-stem data files beside it."""
    out = {}
    for rel, meta in articles().items():
        topic = meta.get("topic") or rel[:-3]
        files = [rel] + [f.strip() for f in meta.get("files", "").strip("[]").split(",") if f.strip()]
        stem = rel[:-3]
        files += [f for f in (stem + ".csv",) if os.path.exists(os.path.join(KB, f))]
        out[topic] = sorted(set(files))
    return out


# ---------------------------------------------------------------- fact units

def md_units(rel, text, untagged=False):
    """Fact units of one article: bullets (with continuation lines), table rows and tagged paragraph lines. With
    `untagged`, also the bullets and table rows that carry no tag (Summary, Reference and Examples content; table
    header and separator rows excluded) and each fenced code block as one unit (line = its first line), with
    tags=[]: pack searches them, fact counts never include them."""
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
                             if cells.get(c, "").strip().upper() in KINDS), None)
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
    """`auth` matches auth/..., `auth/kerberos` matches auth/kerberos.md and auth/kerberos.csv, never authz/..."""
    p = prefix.strip("/")
    return rel == p or rel.startswith(p + "/") or ("/" in p and rel.startswith(p))


def units(prefix=None, with_csv=True, untagged=False):
    """Every fact unit under a path prefix (`auth`, `auth/kerberos`, `auth/kerberos.md`); `untagged` adds the
    untagged bullets and table rows of articles (csv rows are always all included, tagged or not)."""
    out = []
    exts = (".md", ".csv") if with_csv else (".md",)
    for rel in kb_files(exts):
        if prefix and not in_prefix(rel, prefix):
            continue
        text = read(rel)
        if text is None:
            continue
        if rel.endswith(".md"):
            if is_article(text):
                out += md_units(rel, text, untagged)
        elif with_csv:
            out += csv_units(rel, text)
    return out


# ---------------------------------------------------------------- ledgers

def ledger_entries(name):
    """Entries of `_gaps.md` or `_conflicts.md`: {file, line, end, section, text}. A `### ` line followed directly
    by bullets is a sub-heading, not an entry."""
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
    for e in entries:
        named = set()
        for m in TOPIC_MARK.finditer(e["text"]):
            named.add(m.group(1).removesuffix(".md").removesuffix(".csv"))
        for t in tfiles:
            if re.search(rf"(?<![\w/-]){re.escape(t)}(?:\.md|\.csv)?(?![\w-])", e["text"]):
                named.add(t)
        if e["section"] in tfiles:
            named.add(e["section"])
        e["ids"] = sorted(set(ID.findall(e["text"])), key=kbid.sort_key)
        via = set()
        for sid in e["ids"]:
            for f in filter(None, (sources.get(sid, {}).get("used_in") or "").split(";")):
                if f.strip() in file_topic:
                    via.add(file_topic[f.strip()])
        e["explicit"], e["via_sources"] = sorted(named), sorted(via - named)
    return entries


def source_rows():
    return cached("sources", _source_rows)


def _source_rows():
    with open(os.path.join(KB, "_sources.csv"), encoding="utf-8-sig", newline="") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


# ---------------------------------------------------------------- audit

def audit(prefix=None, status=None):
    """One row per article under a prefix: status, dates, fact counts by kind (a fact counts once per kind it
    carries) and the gap/conflict entries linked to it."""
    tfiles = topic_files()
    srcs = source_rows()
    ledgers = {n: link_entries(ledger_entries(n), tfiles, srcs) for n in ("_gaps.md", "_conflicts.md")}
    rows = []
    for rel, meta in sorted(articles().items()):
        if prefix and not in_prefix(rel, prefix):
            continue
        if status and meta.get("status") != status:
            continue
        topic = meta.get("topic") or rel[:-3]
        us = [u for f in tfiles.get(topic, [rel]) for u in
              (md_units(f, read(f) or "") if f.endswith(".md") else csv_units(f, read(f) or ""))]
        counts = Counter(k for u in us for k in kinds_of(u["tags"]))
        row = {"path": rel, "topic": topic, "status": meta.get("status", ""), "priority": meta.get("priority", ""),
               "retrieved_utc": meta.get("retrieved_utc", ""), "facts": sum(1 for u in us if u["tags"]),
               **{k: counts.get(k, 0) for k in KINDS}}
        for n, key in (("_gaps.md", "gaps"), ("_conflicts.md", "conflicts")):
            row[key] = [e for e in ledgers[n] if topic in e["explicit"]]
            row[key + "_via_sources"] = [e for e in ledgers[n] if topic in e["via_sources"]]
        rows.append(row)
    return rows


# ---------------------------------------------------------------- pack (fact-level retrieval)

STOP = kbid.STOP | {"about", "after", "all", "any", "also", "been", "but", "did", "has", "have", "into", "kb", "much",
                    "long", "more", "not", "only", "same", "than", "that", "their", "then", "there", "these", "they",
                    "this", "those", "was", "were", "will", "would", "you", "your", "who", "whom", "whose", "why",
                    "there", "does", "doing", "get", "set", "use", "used", "using", "via", "per", "say", "says"}
WORD = re.compile(r"\w+(?:[.\-]\w+)*")


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


def terms(text, camel=True):
    """Stems of the words, plus the parts of compounds: hyphen/dot parts (what-if -> what, if) and identifier parts
    (approximateLastSignInDateTime -> approximate, last, sign, in, date, time; US_NPI -> us, npi)."""
    out = []
    for w in WORD.findall(text):
        t = w.lower()
        parts = [t] + ([p for p in re.split(r"[.\-]", t) if p] if ("-" in t or "." in t) else [])
        if camel and ("_" in w or re.search(r"[a-z][A-Z]", w)):
            parts += [p.lower() for seg in re.split(r"[_.\-]", w) for p in CAMEL.findall(seg)]
        out += [stem(p) for p in dict.fromkeys(parts) if p not in STOP and len(p) > 1]
    return out


ALIASES = os.path.join(TOOLS, "aliases.csv")
ALIAS_WEIGHT = 0.5  # an alias the question did not use counts half as much as a word it did
TITLE_WEIGHT = 2    # the article title counts twice in each of its units
SUMMARY_WEIGHT = 0.1  # the article's Summary text is indexed into each of its units at this weight
PART_WEIGHT = 0.2  # a part of a compound identifier the question used (US_NPI -> npi): helps, never dominates
EXPANSION_WEIGHT = 1.0  # words of the generated questions a fact answers (doc2query, _tools/doc2query/)
UNTAGGED_WEIGHT = 0.8  # an untagged row or line (reference data, Summary, Examples) ranks below a tagged fact


def aliases():
    """{canonical: [alias word tuples]} from _tools/aliases.csv (`term,canonical`, one row per alias)."""
    return cached("aliases", _aliases)


def _aliases():
    out = defaultdict(list)
    try:
        with open(ALIASES, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                words = tuple(WORD.findall((r.get("term") or "").lower()))
                if words and (r.get("canonical") or "").strip():
                    out[r["canonical"].strip().lower()].append(words)
    except OSError:
        pass
    return dict(out)


def expand(question):
    """Product aliases in a question: ({stem: weight} to add to the ranking, {key stem: [variant stem tuples]}).
    A key word that belongs to an alias found in the question also counts as present where any other alias of that
    product is (all words of a multi-word alias). Expansions never become key words of their own, so they cannot
    raise the coverage verdict on words the question did not use."""
    toks = WORD.findall(question.lower())
    extra, variants = {}, defaultdict(set)
    for canon, forms in aliases().items():
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
    """{fact key: [generated questions]} from _tools/doc2query/expansions.csv; {} when absent or KB_DOC2QUERY=0."""
    path = os.path.join(TOOLS, "doc2query", "expansions.csv")
    if os.environ.get("KB_DOC2QUERY") == "0" or not os.path.exists(path):
        return {}
    out = defaultdict(list)
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            out[r["key"]].append(r["question"])
    return out


def fact_key(text):
    """The doc2query key of a fact: sha256 of its whitespace-collapsed text, 12 hex digits."""
    return hashlib.sha256(" ".join(text.split()).encode()).hexdigest()[:12]


def _corpus(domain):
    metas = articles()
    exps = expansions()
    us = units(domain, untagged=True)  # untagged rows and lines too: a word the kb has is never "not in the kb"
    summaries = {}
    for u in us:
        art = u["path"] if u["path"] in metas else u["path"][:-4] + ".md"
        meta = metas.get(art) or {}
        u["title"] = meta.get("title", "")
        tf = Counter(terms(f"{u['path']} {u['title']} {u['section']} {u['text']}"))
        u["len"], u["own"] = sum(tf.values()), frozenset(tf)  # own: words the unit itself has (verdict, df)
        for t in terms(u["title"]):
            tf[t] += TITLE_WEIGHT - 1
        if meta and not u["section"].startswith("Summary"):
            if art not in summaries:
                summaries[art] = Counter(terms(summary_text(art)))
            for t, c in summaries[art].items():
                tf[t] += SUMMARY_WEIGHT * c
        for q in exps.get(fact_key(u["text"]), ()) if exps and u["tags"] else ():
            for t in terms(q):
                tf[t] += EXPANSION_WEIGHT  # ranks the fact for other wordings; never a verdict word (not in own)
        u["tf"] = tf
    return us


# ---------------------------------------------------------------- the pack index (postings; persisted with sqlite3)

INDEX_VERSION = 1  # bump when the index layout or what goes into a unit's tf/own changes


class Store:
    """The pack corpus as postings lists. A unit's id is its position in corpus order, so ties in the ranking keep
    the order a full scan would give. `own(t)`: ids of the units whose own words hold t (verdict, df); `tf(t)`:
    [(id, weighted tf)] in id order (ranking). Per unit: `lens`, `summ` (a Summary unit), `tagged` and `paths`.
    Units, article metadata and source urls are read only for what a pack prints."""

    def __init__(self, fp, lens, summ, tagged, paths, arts, srcs):
        self.fp, self.lens, self.summ, self.tagged, self.paths = fp, lens, summ, tagged, paths
        self.arts, self.srcs = arts, srcs
        self.n, self.lensum = len(lens), sum(lens)
        self._own, self._tf = {}, {}

    def own(self, t):
        if t not in self._own:
            self._own[t] = self._load_own(t)
        return self._own[t]

    def tf(self, t):
        if t not in self._tf:
            self._tf[t] = self._load_tf(t)
        return self._tf[t]

    def view(self, domain):
        return self if not domain else Subset(self, domain)


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
        metas, rows = articles(), source_rows()
        srcs = {k: [r.get("url") or "", (r.get("superseded_by") or "").strip()] for k, r in rows.items()}
        super().__init__(fp, [u["len"] for u in us], [u["section"].startswith("Summary") for u in us],
                         [bool(u["tags"]) for u in us], [u["path"] for u in us],
                         {k: dict(v) for k, v in metas.items()}, srcs)

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
                    "flags": bytes(1 * s + 2 * t for s, t in zip(self.summ, self.tagged)),
                    "pathix": array.array("I", (pix[p] for p in self.paths)).tobytes(),
                    "paths": json.dumps(pathlist), "arts": json.dumps(self.arts), "srcs": json.dumps(self.srcs)}
            con.executemany("INSERT INTO meta VALUES (?, ?)", meta.items())
            terms_ = set(self.own_lists) | set(self.tf_lists)
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
                         [pathlist[i] for i in pix], json.loads(m["arts"]), json.loads(m["srcs"]))
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
    as a pack over corpus(domain) computes them."""

    def __init__(self, base, domain):
        self.base, self.keep = base, {i for i, p in enumerate(base.paths) if in_prefix(p, domain)}
        ids = sorted(self.keep)
        super().__init__(base.fp, base.lens, base.summ, base.tagged, base.paths, base.arts, base.srcs)
        self.n, self.lensum = len(ids), sum(base.lens[i] for i in ids)

    def _load_own(self, t):
        return self.base.own(t) & self.keep

    def _load_tf(self, t):
        return [(i, v) for i, v in self.base.tf(t) if i in self.keep]

    def unit(self, i):
        return self.base.unit(i)


def index_path(fp):
    """Where the index for fingerprint `fp` lives, or None when KB_INDEX=0: KB_INDEX (a directory), else the
    plugin's data directory (CLAUDE_PLUGIN_DATA, survives plugin updates), else _cache/ in the kb, else a temp
    directory. One file per fingerprint and doc2query mode, so a new index never replaces a file a server has open."""
    where = os.environ.get("KB_INDEX", "")
    if where == "0":
        return None
    if not where:
        where = os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.join(KB, "_cache")
        if not _writable(where):
            where = os.path.join(tempfile.gettempdir(), "it-ops-kb-" + hashlib.sha1(KB.encode()).hexdigest()[:8])
    return os.path.join(where, f"kbindex-{fp[:16]}.sqlite")


def _writable(d):
    if os.path.isdir(d):
        return os.access(d, os.W_OK)
    return os.access(os.path.dirname(d) or ".", os.W_OK)


_STORE = [None]
_STORE_LOCK = threading.Lock()


def store(domain=None):
    """The pack index for the current kb: the one this process holds, else the index file for the current
    fingerprint, else built from corpus() now and saved for the next process (a process that cannot write keeps
    it in memory). Rebuilt only when a kb file changed."""
    fp = fingerprint()
    with _STORE_LOCK:
        st = _STORE[0]
        if st is None or st.fp != fp:
            st = None
            path = index_path(fp)
            if path and os.path.exists(path):
                try:
                    st = SqlStore(path)
                except (sqlite3.Error, ValueError, KeyError):
                    st = None
            if st is None:
                st = MemStore(fp, corpus())
                if path:
                    try:
                        st.save(path)
                        for f in os.listdir(os.path.dirname(path)):
                            if f.startswith("kbindex-") and f.endswith(".sqlite") and f != os.path.basename(path):
                                try:
                                    os.remove(os.path.join(os.path.dirname(path), f))
                                except OSError:
                                    pass
                    except (OSError, sqlite3.Error):
                        pass
            _STORE[0] = st
    return st.view(domain)


def pack(question, budget=1200, domain=None, max_articles=4, fmt="detailed", footer=True):
    """Rank fact units for a question and return {verdict, missing, weak_words, groups, sources, text}.

    The corpus is every fact unit plus the untagged bullets, table rows and data rows (Summary, Reference, Examples,
    untagged csv rows), which rank at UNTAGGED_WEIGHT and print with `(no tag)`: a word the kb has anywhere is never
    reported as "not in the kb".

    verdict (counted on whole query words, not hyphen parts), on the top-ranked article that matches the most key
    words: `none` when a third or more of the named words (with a capital or a digit: products, ids) occur nowhere in
    the kb (unless it is one name among 75%+ matched words, like AV or PC), when half or more of the informative
    words occur nowhere, or when that article matches under a third of the known ones; `good` when a tagged-fact
    article matches 60% or more (80% if some word is unknown), no named word is missing, and every informative name
    appears in a top-ranked tagged fact; else `weak`. Untagged content alone never makes a question `good`. A word that is a product alias (_tools/aliases.csv) counts as present where any alias of the product is;
    the other aliases rank at a lower weight but never count as key words. `budget` is in tokens (about 3.5
    characters each) and bounds the text. fmt `concise` drops the article flags and the source url footer;
    footer=False leaves the footer out of the text (pack_many prints one shared footer)."""
    st = store(domain)
    q = sorted(set(terms(question)))
    extra, variants = expand(question)
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
    informative = [t for t in keys if kdf[t] < 0.2 * n]
    missing = [t for t in informative if not kdf[t]]
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
    scored = [(s, st.unit(i)) for s, i in ranked[:40]]

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
    lone_name = len(named_missing) == 1 and share >= 0.75  # one unknown abbreviation (AV, PC) among well-matched words
    if not scored or (named and len(named_missing) * 3 >= len(named) and not lone_name) or (informative and len(missing) * 2 >= len(informative)):
        verdict = "none"
    elif fact_share >= 0.6 and not named_missing and (not missing or fact_share >= 0.8) and not (named & set(known)) - set().union(*arts_fact.values()):
        verdict = "good"  # and every informative name the question uses (Okta, SCIM) is in a top-ranked fact
    elif share >= 0.34:
        verdict = "weak"
    else:
        verdict = "none"
    # group the best units by article, strongest article first
    by_art, order = defaultdict(list), []
    for s, u in scored[:40]:
        art = u["path"]
        if art not in by_art:
            order.append(art)
        by_art[art].append((s, u))
    best = scored[0][0] if scored else 0
    order = [a for a in order if by_art[a][0][0] >= (0.5 if a.endswith(".md") else 0.65) * best][:max_articles]
    concise = fmt == "concise"
    url_cost = 0 if concise else 110  # a source footer line is about 110 characters
    limit, used, groups, cited, paths = int(budget * 3.5), 0, [], [], []
    for art in order:
        items, picked = [], sorted(sorted((x for x in by_art[art] if x[0] >= 0.4 * best), key=lambda x: -x[0])[:6],
                                   key=lambda x: x[1]["line"])
        for s, u in picked:
            text = clip(u["text"], 420)
            line = f"- {u['path']}:{u['line']} {text}" + ("" if u["tags"] else " (no tag)")
            new_ids = [i for p in u["tags"] for i in p["ids"]] + ID.findall(text)
            cost = len(line) + url_cost * len(set(new_ids) - set(cited))
            if used + cost > limit and (items or groups):
                used = limit
                break
            items.append(line)
            used += cost
            cited += new_ids
        if items:
            more = sum(1 for x in ranked if st.paths[x[1]] == art and x[0] >= 0.4 * best) - len(items)
            if more > 0:  # e.g. hundreds of similar rows in a data file: the answer may be one of these
                items.append(f"  (+{more} more matching lines in {art}: kb_search with more words, or kb_show)")
            meta = st.arts.get(art, {})
            head = f"## {art}" + (f"  {meta.get('title', '')}" if meta else "")
            flags = ", ".join(filter(None, (meta.get("status"), f"retrieved {meta['retrieved_utc']}" if meta.get("retrieved_utc") else "")))
            groups.append((head + (f"  [{flags}]" if flags and not concise else ""), items))
            paths.append(art)
            used += len(head) + 40
        if used >= limit:
            break
    seen, srcs = set(), []
    for i in cited:
        if i not in seen:
            seen.add(i)
            url, sup = st.srcs.get(i, ("", ""))
            srcs.append((i, url or "UNKNOWN id", sup))
    head = f"coverage: {verdict}"
    if known:
        head += f" (best article matches {len(hit)} of {len(known)} key words: {', '.join(sorted(hit)) or '-'})"
    if missing:
        head += f"; not in the kb: {', '.join(missing)}"
    out = [head]
    if verdict == "none":
        out.append("The kb does not cover this. Do not answer from the hits below; say so, or research it with /kb-research.")
    for h, items in groups if verdict != "none" else [(g[0], g[1][:2]) for g in groups[:1]]:
        out += ["", h] + items
    if verdict == "none":
        srcs = []
    if srcs and footer and not concise:
        out += ["", "sources:"] + format_sources(srcs)
    return {"verdict": verdict, "missing": missing, "matched": sorted(hit), "informative": informative, "known": known,
            "paths": paths, "sources": [s[0] for s in srcs], "source_rows": srcs,
            "text": "\n".join(out)}


def clip(text, n):
    """Cut a fact at about n characters, keeping its tags visible: `start ... [DOC S1]`."""
    if len(text) <= n:
        return text
    head = text[:n].rsplit(" ", 1)[0]
    tags = [m.group(0) for m in TAG.finditer(text) if m.end() > len(head)]  # tags cut off, straddling ones included
    return head + " ..." + ("" if TAG.search(head) or not tags else " " + " ".join(tags))


def format_sources(srcs):
    return [f"  -> {i}  {u}" + (f"  (superseded by {s})" if s else "") for i, u, s in srcs]


MAX_QUESTIONS = 6


def pack_many(questions, budget=1200, domain=None, fmt="detailed"):
    """One pack per question (1-6), each with its own coverage verdict, and one shared source footer:
    {verdict (the worst), results, text}. A single question gives exactly pack()'s text."""
    qs = [q.strip() for q in questions if q and q.strip()][:MAX_QUESTIONS]
    if len(qs) == 1:
        res = pack(qs[0], budget, domain, fmt=fmt)
        return {"verdict": res["verdict"], "results": [res], "text": res["text"]}
    results = [pack(q, budget, domain, fmt=fmt, footer=False) for q in qs]
    out, seen, srcs = [], set(), []
    for i, (q, res) in enumerate(zip(qs, results), start=1):
        out += [f"# Q{i}: {q}", res["text"], ""]
        for row in res["source_rows"]:
            if row[0] not in seen:
                seen.add(row[0])
                srcs.append(row)
    if srcs and fmt != "concise":
        out += ["sources:"] + format_sources(srcs)
    order = ("none", "weak", "good")
    return {"verdict": min((r["verdict"] for r in results), key=order.index), "results": results,
            "text": "\n".join(out).rstrip()}


def cited_lines(ids):
    """{id: [(path, line)]}: every kb file line (domain files and root ledgers, not _sources.csv) naming the id."""
    want = {kbid.canonical_id(i) for i in ids}
    out = defaultdict(list)
    files = list(kb_files((".md", ".csv"))) + [f for f in ("_answers.md", "_gaps.md", "_conflicts.md") if os.path.exists(os.path.join(KB, f))]
    for rel in files:
        text = read(rel)
        if not text or not any(i in text for i in want):
            continue
        for n, ln in enumerate(text.splitlines(), start=1):
            for i in set(ID.findall(ln)) & want:
                out[i].append((rel, n))
    return out


# ---------------------------------------------------------------- topics for code (host workspace signals)

SIGNALS = os.path.join(TOOLS, "signals.csv")
SKIP_CODE_DIRS = {".git", "node_modules", "dist", "build", "out", "coverage", "target", "vendor", "__pycache__", ".venv",
                  "venv", ".next", ".turbo", ".cache"}
MAX_FILES, MAX_FILE_BYTES = 500, 1_000_000


def signals():
    """[(signal, topic, regex)] from _tools/signals.csv (`signal,topic`): code words that point at a kb topic,
    matched case-insensitively as whole words (a signal that starts or ends with punctuation matches there as is)."""
    return cached("signals", _signals)


def _signals():
    out = []
    try:
        with open(SIGNALS, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                sig, topic = (r.get("signal") or "").strip(), (r.get("topic") or "").strip()
                if sig and topic:
                    rx = (r"(?<!\w)" if sig[0].isalnum() else "") + re.escape(sig) + (r"(?!\w)" if sig[-1].isalnum() else "")
                    out.append((sig, topic, re.compile(rx, re.I)))
    except OSError:
        pass
    return out


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


def topics_for(paths=(), text="", base=None):
    """Rank kb topics for code: every signal found in the files (or in `text`) adds to its topic. Returns
    {"topics": [{topic, signals: {signal: count}, where: {signal: "path:line"}}], "files": n, "text": bool,
    "skipped": [...]}."""
    sources, skipped = [], []
    if text:
        sources.append(("text", text))
    files, skipped = code_files(paths, base) if paths else ([], [])
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
        sources.append((shown, raw.decode("utf-8", errors="replace")))
    hits = defaultdict(lambda: {"signals": Counter(), "where": {}})
    for shown, body in sources:
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
    out = [f"kb topics for {res['files']} file(s)" + (" and the given text" if res.get("text") else "") + ":"]
    for x in res["topics"][:limit]:
        sigs = ", ".join(f"{s} ({n}, {x['where'][s]})" for s, n in x["signals"].items())
        out.append(f"- {x['topic']}  {sigs}")
    if not res["topics"]:
        out.append("no kb signal found: the code touches none of the curated topics (_tools/signals.csv)")
    elif len(res["topics"]) > limit:
        out.append(f"... +{len(res['topics']) - limit} more topics")
    out += [f"skipped: {s}" for s in res["skipped"][:10]]
    out.append("next: kb_facts or kb_pack per topic (response_format detailed) for the facts to check the code against")
    return "\n".join(out)
