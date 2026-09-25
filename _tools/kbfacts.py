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
"""
import csv, io, math, os, re, sys
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
TTL = 30  # seconds: a long-running kb MCP server re-reads the kb at most this often


def cached(key, build):
    import time
    hit = _CACHE.get(key)
    if hit and time.monotonic() - hit[0] < TTL:
        return hit[1]
    val = build()
    _CACHE[key] = (time.monotonic(), val)
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

def md_units(rel, text):
    """Fact units of one article: bullets (with continuation lines), table rows and tagged paragraph lines."""
    lines = text.splitlines()
    body = lines.index("---", 1) + 1 if lines[:1] == ["---"] and "---" in lines[1:] else 0
    section, cur, fenced = "", None, False
    units = []

    def flush():
        if cur and TAG.search(cur["text"]):
            cur["tags"] = tags_in(cur["text"])
            units.append(cur)

    for n, ln in enumerate(lines, start=1):
        if n <= body:
            continue
        s = ln.strip()
        if s.startswith(("```", "~~~")):
            fenced = not fenced
        if fenced:
            continue
        if ln.startswith("#"):
            flush()
            cur = None
            section = ln.lstrip("#").strip()
            continue
        if re.match(r"\s*[-*] ", ln) or s.startswith("|"):
            flush()
            cur = {"path": rel, "line": n, "section": section, "text": s[2:] if not s.startswith("|") else s}
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


def units(prefix=None, with_csv=True):
    """Every fact unit under a path prefix (`auth`, `auth/kerberos`, `auth/kerberos.md`)."""
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
                out += md_units(rel, text)
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


def terms(text):
    out = []
    for t in WORD.findall(text.lower()):
        parts = [t] + ([p for p in re.split(r"[.\-]", t) if p] if ("-" in t or "." in t) else [])
        out += [stem(p) for p in parts if p not in STOP and len(p) > 1]
    return out


ALIASES = os.path.join(TOOLS, "aliases.csv")
ALIAS_WEIGHT = 0.5  # an alias the question did not use counts half as much as a word it did
TITLE_WEIGHT = 2    # the article title counts twice in each of its units
SUMMARY_WEIGHT = 0.1  # the article's Summary text is indexed into each of its units at this weight


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
    """Fact units plus each article's title and Summary bullets as searchable units (cached for TTL seconds)."""
    return cached(("corpus", domain or ""), lambda: _corpus(domain))


def summary_text(rel):
    """The text of an article's `## Summary` section, or ''."""
    m = re.search(r"(?ms)^## Summary[^\n]*\n(.*?)(?=^#{1,2} |\Z)", read(rel) or "")
    return m.group(1) if m else ""


def _corpus(domain):
    metas = articles()
    us = [u for u in units(domain) if u["tags"] or u["path"].endswith(".md")]
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
        u["tf"] = tf
    return us


def pack(question, budget=1200, domain=None, max_articles=4, fmt="detailed", footer=True):
    """Rank fact units for a question and return {verdict, missing, weak_words, groups, sources, text}.

    verdict (counted on whole query words, not hyphen parts): `none` when a third or more of the named words
    (with a capital or a digit: products, ids) or half or more of the informative words occur nowhere in the kb, or
    the best article matches under a third of the known ones; `weak` under 60% (or any named word missing); else
    `good`. A word that is a product alias (_tools/aliases.csv) counts as present where any alias of the product is;
    the other aliases rank at a lower weight but never count as key words. `budget` is in tokens (about 3.5
    characters each) and bounds the text. fmt `concise` drops the article flags and the source url footer;
    footer=False leaves the footer out of the text (pack_many prints one shared footer)."""
    us = corpus(domain)
    q = sorted(set(terms(question)))
    extra, variants = expand(question)
    weight = {**extra, **{t: 1.0 for t in q}}
    df = Counter(t for u in us for t in u["own"] if t in weight)
    n = max(len(us), 1)
    avg = sum(u["len"] for u in us) / n
    keys = sorted(set(key_terms(question)))

    def has(u, t):
        return t in u["own"] or any(all(x in u["own"] for x in v) for v in variants.get(t, ()))

    kdf = {t: sum(1 for u in us if has(u, t)) if t in variants or t not in df else df[t] for t in keys}
    informative = [t for t in keys if kdf[t] < 0.2 * n]
    missing = [t for t in informative if not kdf[t]]
    scored = []
    for u in us:
        s = 0.0
        for t, w in weight.items():
            tf = u["tf"].get(t)
            if tf and df[t]:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                s += w * idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * u["len"] / avg))
        if s:
            if u["section"].startswith("Summary"):
                s *= 1.15
            scored.append((s, u))
    scored.sort(key=lambda x: -x[0])
    # verdict: named words (product names, ids: a capital or a digit, not the question's first word) that the kb
    # never mentions mean it does not cover the question; else the share of the kb-known key words that the best
    # article's units match
    named = {stem(w.lower()) for w in WORD.findall(question) if re.search(r"[A-Z0-9]", w) and w.lower() not in STOP}
    named = {t for t in named if t in kdf}
    named_missing = sorted(t for t in named if not kdf[t])
    known = [t for t in informative if kdf[t]]
    best_art = scored[0][1]["path"] if scored else None
    hit = {t for s_, u in scored[:40] if u["path"] == best_art for t in known if has(u, t)}
    share = len(hit) / len(known) if known else 0.0
    if not scored or (named and len(named_missing) * 3 >= len(named)) or (informative and len(missing) * 2 >= len(informative)):
        verdict = "none"
    elif share >= 0.6 and not named_missing:
        verdict = "good"
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
            text = u["text"] if len(u["text"]) <= 420 else u["text"][:420].rsplit(" ", 1)[0] + " ..."
            line = f"- {u['path']}:{u['line']} {text}"
            new_ids = [i for p in u["tags"] for i in p["ids"]] + ID.findall(text)
            cost = len(line) + url_cost * len(set(new_ids) - set(cited))
            if used + cost > limit and (items or groups):
                used = limit
                break
            items.append(line)
            used += cost
            cited += new_ids
        if items:
            meta = articles().get(art, {})
            head = f"## {art}" + (f"  {meta.get('title', '')}" if meta else "")
            flags = ", ".join(filter(None, (meta.get("status"), f"retrieved {meta['retrieved_utc']}" if meta.get("retrieved_utc") else "")))
            groups.append((head + (f"  [{flags}]" if flags and not concise else ""), items))
            paths.append(art)
            used += len(head) + 40
        if used >= limit:
            break
    rows = source_rows()
    seen, srcs = set(), []
    for i in cited:
        if i not in seen:
            seen.add(i)
            r = rows.get(i, {})
            srcs.append((i, r.get("url") or "UNKNOWN id", (r.get("superseded_by") or "").strip()))
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
