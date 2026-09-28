#!/usr/bin/env python3
"""Fact diff: turn "a source changed" into "these facts still hold, these changed, these are gone" (stdlib only).

  factdiff.py [--root NAME] anchor [SELECTION] [--refetch] [--max-age DAYS] [--dry-run]
      locate each fact's backing sentence in the current text of its sources and write its anchor
  factdiff.py [--root NAME] snapshot [SELECTION] [--refetch] [--max-age DAYS] [--dry-run]
      write the normalized text of the root's live copy sources, with attribution, to <root>/_snapshots/<id>.txt
  factdiff.py [--root NAME] calibrate history --repo DIR [--path P] [--since D] [--pairs N] | soft404 [--hosts N]
      measure the cut-offs of _tools/factdiff.toml on real history (consecutive page versions in a documentation
      repository) or on live hosts (made-up sibling urls); prints JSON with the suggested cut and its accuracy
  factdiff.py [--root NAME] anchors [--unlocated] [--stale] [--source ID]
      list anchors: counts by status, the unlocated facts, or the anchors whose fact text is gone (exit 1 when any)

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
--max-age days (default 7); --refetch ignores them.
Exit: 0 ok; 1 anchors --stale found stale anchors; 2 bad arguments.
"""
import argparse, collections, concurrent.futures as cf, datetime, hashlib, json, math, os, re, sys, unicodedata, urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kbcommon, kbfacts, kbid, provider  # noqa: E402

ANCHORS, COLS, REASONS, QUOTE_WORDS = kbcommon.ANCHORS, kbcommon.ANCHOR_COLS, kbcommon.ANCHOR_REASONS, kbcommon.QUOTE_WORDS
CACHE = os.path.join(kbcommon.HOME, "_cache", "factdiff")
TERMS = 8
CONFIG = os.path.join(kbcommon.TOOLS, "factdiff.toml")  # the calibrated cut-offs (kb/_self/reports/fact-diff.md)


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
MODIFIED_MIN = _CFG.get("resolve", {}).get("modified_min", 0.6)  # unit_sim: an edited passage, below: not found
SOFT404_MIN = _CFG.get("dead", {}).get("soft404_min", 0.8)  # jaccard to a made-up sibling url's page: a soft 404
ZOMBIE_MAX = _CFG.get("dead", {}).get("zombie_max", 0.6)  # simhash_sim to the previous version: replaced content
ROOT = None  # kbcommon.Root under work


def today():
    return datetime.date.today().isoformat()


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


def units(text):
    """[(heading path, unit text)] of a document text: sentences of prose lines, list items, table rows (cells joined
    by ` | `), code lines; heading lines set the path and are units too."""
    out, path, fenced = [], [], False
    for ln in (text or "").splitlines():
        s = ln.strip()
        if s.startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if not s:
            continue
        if fenced:
            out.append((" > ".join(path), s))
            continue
        m = re.match(r"^(#{1,6})\s+(.*)", s)
        if m:
            level, title = len(m.group(1)), m.group(2).strip("# ").strip()
            path = path[:level - 1] + [title]
            out.append((" > ".join(path[:-1]), title))
            continue
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) or not c for c in cells):
                continue
            out.append((" > ".join(path), " | ".join(cells)))
            continue
        if re.match(r"<(?:img|source|video|picture|iframe)\b", s, re.I):
            continue  # an embedded image or video is markup, not a statement
        s = LIST.sub("", s).lstrip("> ").strip()
        for part in SENT.split(s):
            if part.strip():
                out.append((" > ".join(path), part.strip()))
    return out


NUM = re.compile(r"(?<![\w.])\d[\d,.]*\d(?![\w])|(?<![\w.])\d(?![\w.])")


def numbers(text):
    return {n.replace(",", "") for n in NUM.findall(text) if len(n.replace(",", "")) > 1}


def fact_text(text):
    """A fact's claim: its text without tags, `SNIPPET:` framing and the `context:`/`checked:` notes."""
    t = kbfacts.TAG.sub(" ", text)
    t = re.sub(r"^SNIPPET:\s*", "", t.strip())
    t = re.sub(r";\s*(?:context|checked):.*$", "", t)
    return " ".join(t.split())


def term_set(text):
    return {t for t in kbfacts.terms(text) if len(t) > 2 and not t.isdigit()}


class Doc:
    """A source document split into units, with term rarity (idf) over its units and the hashes of every window of
    1 to SPAN consecutive units (a fact often condenses two or three sentences)."""

    def __init__(self, text):
        self.units = units(text)
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

    def window(self, i, k):
        return " ".join(u for _, u in self.units[i:i + k])

    def score(self, fact):
        """(best window (i, k) or None, cover, anchor unit cover, shared terms rarest first)."""
        want = term_set(fact)
        known = {t for t in want if t in self.idf}
        if not known:
            return None, 0.0, 0.0, []
        w = {t: self.idf[t] for t in known}
        total = sum(w.values()) + 0.5 * len(want - known)  # a fact term the page lacks entirely still counts against
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

    def locate(self, fact):
        """(window (i, k), cover, shared terms) of the fact's backing passage, or (None, cover, shared) below the cut."""
        win, cover, own, shared = self.score(fact)
        need = min(MIN_SHARED, max(2, len(term_set(fact) & set(self.idf))))
        if win is None or cover < MIN_COVER or len(shared) < need:
            return None, cover, shared
        return win, cover, shared


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


def cache_path(sid):
    return os.path.join(CACHE, ROOT.name, re.sub(r"[^\w.-]", "_", sid) + ".json")


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

def read_anchors():
    p = root_path(ANCHORS)
    if not os.path.exists(p):
        return {}
    return {(r["fact"], r["path"], r["source_id"]): r for r in kbcommon.load_csv(p, COLS)[1]}


def write_anchors(rows):
    key = lambda r: (r["path"], r["fact"], kbid.sort_key(r["source_id"]) if kbid.is_source_id(r["source_id"]) else (9, 0, r["source_id"]))  # noqa: E731
    kbcommon.write_csv(root_path(ANCHORS), COLS, sorted(rows.values(), key=key), atomic=True)


def anchor_rows(sid, facts, doc, reuse, when):
    """The anchor rows of one source's facts against its fetched document."""
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
            win, _cover, shared = d.locate(fact_text(text))
            if win is None:
                row["status"] = "unlocated:no-match"
            else:
                passage = d.window(*win)
                row.update(status="located", heading=d.units[win[0]][0][:200], terms=";".join(shared[:TERMS]),
                           sha=sha(passage), quote=quote_of(passage, reuse))
        out.append(row)
    return out


def cmd_anchor(a):
    srcs = sources()
    facts = cited_facts()
    ids = select_ids(a, srcs)
    ids = [i for i in ids if i in facts and i in srcs]
    docs = fetch_all(ids, srcs, a.max_age, a.refetch)
    anchors = read_anchors()
    when = today()
    counts = collections.Counter()
    for sid in ids:
        for row in anchor_rows(sid, facts[sid], docs.get(sid), (srcs[sid].get("reuse") or "").strip(), when):
            k = (row["fact"], row["path"], row["source_id"])
            old = anchors.get(k)
            if old and old["status"] == "located" and row["status"].startswith("unlocated:fetch"):
                counts["kept (fetch failed)"] += 1
                continue  # a failed fetch never erases a located anchor
            anchors[k] = row
            counts[row["status"]] += 1
    live = {(k, rel, sid) for sid, fs in facts.items() for k, rel, _, _ in fs}
    stale = [k for k in anchors if k not in live and (not ids or k[2] in ids or not a.selected)]
    for k in stale:
        del anchors[k]
    print(f"anchor: sources={len(ids)} " + " ".join(f"{k}={v}" for k, v in sorted(counts.items())) + f" pruned_stale={len(stale)}")
    if a.dry_run:
        print("dry run: nothing written")
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
    return {"id": sid, "url": url, "etag": d.get("etag", ""), "last_modified": d.get("lastmod", ""),
            "version": (d.get("version") or {}).get(keys[0], "") if keys else "",
            "doc_sha256": hashlib.sha256(d["text"].encode()).hexdigest(),
            "final_url": d["final"] if (d.get("final") or "").split("?")[0] != provider.raw_url(url, row)[0].split("?")[0] else "",
            "http_status": "200", "simhash": simhash(d["text"]), "detected_utc": (stamp + "Z") if stamp else ""}


# ---------------------------------------------------------------- snapshots of copy sources

SNAP_NOTE = ("normalized to text by _tools/provider.py (raw form; front matter, link targets, images and page chrome "
             "removed); not the publisher's formatting")


def snapshot_path(sid):
    return root_path(os.path.join(kbcommon.SNAPSHOTS, re.sub(r"[^\w.-]", "_", sid) + ".txt"))


SNAPSHOT_MAX = _CFG.get("snapshot", {}).get("max_bytes", 500_000)
# a private key header in a page (a vendor's sample key, or only the marker in a format note) trips the leak test
# (test_kb.py, TestLeaks) and secret scanners on push: such a page keeps only its hash, like an oversized one
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
        old, new = _git(repo, "show", f"{commit}^:{path}"), _git(repo, "show", f"{commit}:{path}")
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
DATE_KEYS = ("updated_at", "dateModified", "article:modified_time")  # a version key that is the content's own date


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
VERDICTS = ("unchanged", "changed", "new", "moved", "gone", "soft-404", "replaced", "error", "pinned")
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


def prev_path(sid):
    return cache_path(sid)[:-5] + ".prev.json"


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


def madeup_text(url):
    """The text a made-up sibling url of `url` returns with 200 (None for a real 404), once per host and run."""
    host = urllib.parse.urlsplit(url).netloc
    if host not in _madeup:
        r = provider.request(provider._sibling(url))
        _madeup[host] = provider.doc_text(r["body"], r["headers"].get("content-type", ""), url) if r["status"] == 200 else None
    return _madeup[host]


def page_doc(url, rows):
    """(Doc, text) of any url fetched by its provider's raw form, once per run (search and redirect targets)."""
    if url not in _pages:
        d = provider.document(url, provider.for_url(url, rows) or {})
        _pages[url] = (Doc(d["text"]), d["text"]) if d.get("status") == 200 and d.get("text") else (None, None)
    return _pages[url]


def detect_source(sid, src, st, rows):
    """(verdict, signal, evidence, new state, doc, prev doc) of one source against its stored state."""
    url, row = src["url"], provider.for_url(src["url"], rows) or {}
    sig = provider.signals(row, url)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if "pin" in sig:
        return "pinned", "pin", "pinned url: its text cannot change (census.py compares the pin with upstream)", None, None, None
    prev = load_json(cache_path(sid))
    d = provider.document(url, row, etag=st.get("etag", ""), lastmod=st.get("last_modified", ""))
    new = {**st, "id": sid, "url": url, "checked_utc": stamp, "detected_utc": stamp, "http_status": str(d["status"] or "")}
    if d["status"] == 304:
        new.update(error="")
        via = "etag" if st.get("etag") and "etag" in sig else "lastmod"
        return "unchanged", via, "304 Not Modified", new, prev, prev
    if not d["status"] or d["error"] or d["status"] not in (200, 404, 410):
        new["error"] = (d["error"] or f"HTTP {d['status']}")[:200]
        return "error", "", new["error"], new, None, prev
    if d["status"] in (404, 410):
        new.update(error=f"HTTP {d['status']}")
        return "gone", "status", f"HTTP {d['status']}", new, None, prev
    save_doc(sid, {**d, "id": sid, "url": url, "fetched_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()})
    keys = [k for k in (row.get("version_meta") or "").split(",") if k.strip() and k != "-"]
    version = d["version"].get(keys[0], "") if keys else ""
    d["sha"] = hashlib.sha256((d["text"] or "").encode()).hexdigest()
    new.update(etag=d["etag"], last_modified=d["lastmod"], version=version, doc_sha256=d["sha"], error="",
               final_url=d["final"] if d["hops"] else "", simhash=simhash(d["text"] or ""))
    raw_url = provider.raw_url(url, row)[0]
    moved = bool(d["hops"]) and d["final"].split("?")[0].rstrip("/") != raw_url.split("?")[0].rstrip("/")
    text = d["text"] or ""
    if row.get("not_found") != "hard-404" and text:
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


def search_urls(fact, anchor, row, src_url, title=""):
    """Candidate pages for a passage that left its page, from the provider's search (search_api): first the old page's
    title (a moved page keeps it), then the anchor's quote, then the fact's words; SEARCH_TOP pages per query."""
    tpl = (row.get("search_api") or "-").strip()
    if tpl in ("-", "") or "{q}" not in tpl:
        return []
    queries = [re.split(r"\s+[|:-]\s+(?:Microsoft Learn|Microsoft Entra|Microsoft Intune|Configuration Manager)", title)[0]] if title else []
    if anchor and anchor.get("quote"):
        queries.append(" ".join(anchor["quote"].split()[:12]))
    queries.append(" ".join([w for w in re.findall(r"[A-Za-z][\w.-]+", fact_text(fact)) if w.lower() not in kbfacts.STOP][:8]))
    out = []
    for q in queries:
        if not q.strip():
            continue
        if q not in _searches:
            r = provider.request(tpl.replace("{q}", urllib.parse.quote(q)))
            try:
                res = json.loads(r["body"]).get("results", []) if r["status"] == 200 else []
            except ValueError:
                res = []
            _searches[q] = [x["url"] for x in res if x.get("url")]
        hits = [u for u in _searches[q] if urllib.parse.urlsplit(u).path.rstrip("/") != urllib.parse.urlsplit(src_url).path.rstrip("/")
                and not urllib.parse.urlsplit(u).path.endswith("/")]  # a hub or landing page holds no passage
        seg = [x for x in urllib.parse.urlsplit(src_url).path.split("/") if x and x != "en-us"][:1]
        hits.sort(key=lambda u: 0 if seg and f"/{seg[0]}/" in u else 1)  # the source's own docset first
        out += [u for u in hits[:SEARCH_TOP] if u not in out]
    return out


def elsewhere(fact, anchor, cands, rows):
    """(outcome, target url, note) of a passage searched on other pages: moved when its anchor is found word for word,
    else not-found (with the page where the fact's terms best match, for review)."""
    best = (None, 0.0)
    for u in cands:
        d, _ = page_doc(u, rows)
        if d is None:
            continue
        if anchor and anchor.get("sha") and anchor["sha"] in d.shas:
            return "moved", u, "anchor found word for word"
        win, cover, _ = d.locate(fact_text(fact))
        if win is not None and cover > best[1]:
            best = (u, cover)
    return "not-found", best[0] or "", f"best candidate cover {best[1]:.2f}" if best[0] else "no candidate page"


def linked(src, doc, row):
    """Pages a moved passage may have gone to, before any search: the redirect target, then the pages added to the
    provider's sitemap in this run nearest the source's path."""
    out = [doc["final"]] if doc and doc.get("final") and doc["final"] != src["url"] and doc.get("hops") else []
    seg = urllib.parse.urlsplit(src["url"]).path.strip("/").split("/")
    segs = [x for x in seg[:2] if x and x != "en-us"][:1]
    return out + near(src["url"], sitemap_added(row, segs))


def resolve(sid, src, verdict, doc, prev, facts, anchors, rows):
    """Log rows, one per fact of a source whose text changed, moved or died."""
    out = []
    row = provider.for_url(src["url"], rows) or {}
    d = Doc(doc["text"]) if doc and doc.get("text") else None
    pd = Doc(prev["text"]) if prev and prev.get("text") else None
    found = 0
    for key, rel, line, text in facts:
        a = anchors.get((key, rel, sid))
        located = a is not None and a.get("status") == "located"
        rec = {"fact": key, "path": rel, "line": line, "outcome": "", "target": "", "note": ""}
        if d is not None and located and a["sha"] in d.shas:
            rec["outcome"] = "verbatim"
            found += 1
        elif d is not None and verdict not in ("soft-404", "replaced"):
            win, cover, _ = d.locate(fact_text(text))
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
                o, t, note = elsewhere(text, a, linked(src, doc, row) + search_urls(text, a, row, src["url"], src.get("title", "")), rows)
                rec.update(outcome=o, target=t, note=note)
        else:
            cands = linked(src, doc, row) + search_urls(text, a, row, src["url"], src.get("title", ""))
            o, t, note = elsewhere(text, a if located else None, cands, rows)
            rec.update(outcome=o if o == "moved" else "dead", target=t, note=note)
        out.append(rec)
    return out, found


def cmd_detect(a):
    """Detection for the selected sources, then resolution per fact; the log goes to _census/factdiff-<date>.csv."""
    srcs, facts, anchors, state = sources(), cited_facts(), read_anchors(), read_state()
    rows = provider.providers(ROOT)
    ids = [i for i in select_ids(a, srcs) if i in facts and not (srcs[i].get("superseded_by") or "").strip()]
    date = a.date or today()
    by_host = collections.defaultdict(list)
    for sid in ids:
        by_host[urllib.parse.urlsplit(srcs[sid]["url"]).netloc].append(sid)
    print(f"detect: {len(ids)} source(s) on {len(by_host)} host(s)", file=sys.stderr, flush=True)

    def host_job(host):
        res = []
        for sid in by_host[host]:
            try:
                v = detect_source(sid, srcs[sid], state.get(sid, {}), rows)
            except Exception as e:  # noqa: BLE001 - one source must never stop the run
                v = ("error", "", f"{type(e).__name__}: {e}"[:200], None, None, None)
            res.append((sid, v))
        return res

    results = {}
    with cf.ThreadPoolExecutor(max(1, min(16, len(by_host)))) as ex:
        for part in ex.map(host_job, list(by_host)):
            results.update(part)
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
    log, counts, outc = [], collections.Counter(), collections.Counter()
    for sid in ids:
        verdict, signal, ev, new, doc, prev = results[sid]
        rows_f = []
        if verdict in ("changed", "new", "moved", "gone", "soft-404", "replaced"):
            rows_f, found = resolve(sid, srcs[sid], verdict, doc, prev, facts[sid], anchors, rows)
            if verdict == "replaced" and found:
                verdict, ev = "changed", ev + "; anchors still found: an edit, not a replacement"
        counts[verdict] += 1
        base = {"source_id": sid, "url": srcs[sid]["url"], "verdict": verdict, "signal": signal, "evidence": ev,
                "baseline_utc": state.get(sid, {}).get("detected_utc", "") if verdict != "new" else "",
                "content_date": content_date(doc) or content_date(prev)}
        log.append({**base, "fact": "", "path": "", "line": "", "outcome": "", "target": "", "note": ""})
        for r in rows_f:
            log.append({**base, **r})
            outc[r["outcome"]] += 1
        if new is not None and not a.no_save:
            state[sid] = new
        if doc is not None and wants_snapshot(srcs[sid], doc) and not a.no_save:
            write_snapshot(srcs[sid], doc["text"], date)
    out = a.out or root_path(os.path.join(kbcommon.CENSUS_DIR, f"factdiff-{date}.csv"))
    if not a.no_save:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        kbcommon.write_csv(out, LOG_COLS, log, atomic=True)
        write_state(state)
    print("detect: " + " ".join(f"{k}={counts[k]}" for k in VERDICTS if counts[k]) + "; facts: "
          + " ".join(f"{k}={outc[k]}" for k in OUTCOMES if outc[k]) + ("" if a.no_save else f"; wrote {os.path.relpath(out, kbcommon.HOME)}"))
    return 1 if any(outc[k] for k in REVIEW) else 0


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


def old_passage(sid, anchor, fact, src):
    """(passage, where) the fact rested on before the change: the snapshot at HEAD (copy sources), the previous
    cached document, a Wayback capture from the anchor's date, or the anchor's quote; (None, why) when none has it."""
    rel = os.path.relpath(snapshot_path(sid), kbcommon.HOME)
    head = _git(kbcommon.HOME, "show", f"HEAD:{rel}")
    tries = []
    if head:
        tries.append((head.partition("\n---\n")[2], "snapshot at HEAD"))
    prev = load_json(prev_path(sid))
    if prev and prev.get("text"):
        tries.append((prev["text"], "previous fetch (_cache)"))
    for text, where in tries:
        d = Doc(text)
        if anchor and anchor.get("sha") in d.shas:
            return d.window(*d.shas[anchor["sha"]]), where
    if anchor and anchor.get("verified_utc"):
        text, cap = _wayback_text(src["url"], anchor["verified_utc"])
        if text:
            d = Doc(text)
            if anchor.get("sha") in d.shas:
                return d.window(*d.shas[anchor["sha"]]), cap
            win, _, _ = d.locate(fact_text(fact))
            if win:
                return d.window(*win), cap + " (best match)"
    if anchor and anchor.get("quote"):
        return anchor["quote"], "anchor quote"
    return None, "no old text: not a copy source, no cached or archived version"


def review_items(log, srcs, only=None):
    facts = {(k, rel, sid): (line, t) for sid, fs in cited_facts().items() for k, rel, line, t in fs}
    anchors = read_anchors()
    rows = provider.providers(ROOT)
    for r in log:
        if r["outcome"] not in REVIEW or (only and r["source_id"] not in only):
            continue
        k = (r["fact"], r["path"], r["source_id"])
        line, text = facts.get(k, (r["line"], ""))
        a = anchors.get(k)
        src = srcs.get(r["source_id"], {"url": r["url"]})
        old, where = old_passage(r["source_id"], a, text, src)
        new, new_where = None, ""
        url = r["target"] or (src["url"] if r["verdict"] in ("changed", "new", "moved") else "")
        if url:
            cur = load_json(cache_path(r["source_id"])) if url == src["url"] else None
            d = Doc(cur["text"]) if cur and cur.get("text") else page_doc(url, rows)[0]
            if d is not None:
                win, cover, _ = d.locate(fact_text(text)) if text else (None, 0, [])
                if win is None and text:
                    win = d.score(fact_text(text))[0]
                new, new_where = (d.window(*win), url) if win else (None, url)
        yield {"outcome": r["outcome"], "source_id": r["source_id"], "url": src["url"], "verdict": r["verdict"],
               "note": r["note"], "fact": text, "where": f"{ROOT.name}/{r['path']}:{line}", "key": r["fact"], "path": r["path"],
               "old": old, "old_from": where, "new": new, "new_from": new_where}


def cmd_review(a):
    items = list(review_items(read_log(a.log), sources(), set(a.source) or None))
    if a.json:
        print(json.dumps(items, indent=1))
        return 0
    for n, it in enumerate(items, 1):
        print(f"## {n}. {it['outcome']} {it['source_id']} {it['where']}\n- fact: {fact_text(it['fact'])}\n"
              f"- source: {it['url']} ({it['verdict']}; {it['note']})\n- old ({it['old_from']}): {it['old'] or '-'}\n"
              f"- new ({it['new_from'] or '-'}): {it['new'] or '-'}\n- decide: supported | contradicted | not enough info\n")
    print(f"review items={len(items)}")
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


def cmd_apply(a):
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
        if head["verdict"] == "unchanged":
            if not confirmable(head, retrieved):
                held += 1
                continue
            confirmed[sid] = f"fact diff: unchanged ({head['signal']})"
            for k, rel, _, _ in facts.get(sid, []):
                if (k, rel, sid) in anchors:
                    anchors[(k, rel, sid)]["verified_utc"] = date
        elif head["verdict"] in ("changed", "new", "moved") and fr and all(r["outcome"] == "verbatim" for r in fr) \
                and len(fr) == len(facts.get(sid, [])) and all(anchors[(r["fact"], r["path"], sid)]["verified_utc"][:10]
                                                                <= retrieved[:10] for r in fr):
            confirmed[sid] = f"fact diff: {len(fr)} anchor(s) verbatim"
        for r in fr:
            if r["outcome"] == "verbatim" and anchors[(r["fact"], r["path"], sid)]["verified_utc"][:10] <= retrieved[:10]:
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
                    out.append(f"{p['kind']} {', '.join(ids)}" + (f": {p['note']}" if p["note"] else "") if ids else f"UNK: {why}")
                else:
                    out.append(f"{p['kind']} {', '.join(p['ids'])}".strip() + (f": {p['note']}" if p["note"] else ""))
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
    a.selected = bool(a.topic or a.dir or a.file or a.source)
    ns = argparse.Namespace(topic=a.topic, dir=a.dir, file=a.file, source=a.source, older_than=None)
    return fetch.select(ns, srcs, {})


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
    sn = sub.add_parser("snapshot", help="write the normalized text of the root's live copy sources to _snapshots/")
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
    ls.add_argument("--source", action="append", default=[])
    a = ap.parse_args()
    try:
        ROOT = kbcommon.root(a.root)
    except (KeyError, kbcommon.RootError):
        ap.error(f"--root {a.root}: no such root")
    kbcommon.KB = ROOT.path
    if a.cmd == "calibrate" and a.what == "history" and not a.repo:
        ap.error("calibrate history needs --repo")
    return {"anchor": cmd_anchor, "anchors": cmd_anchors, "snapshot": cmd_snapshot, "calibrate": cmd_calibrate,
            "detect": cmd_detect, "review": cmd_review, "apply": cmd_apply, "dead": cmd_dead}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
