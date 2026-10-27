"""The pack index and the pack's ranking over it: postings lists (`Store`, `MemStore`, `SqlStore` and the views `Subset`
and `Prefix`), the index file's place and pruning, `store()`, `rank`, `search` and `pack` with the weighing of a unit
that feeds them (stdlib only; kb/_self/tools.md, "How the lookup tools decide").

`kbfacts.py` is the facade: it imports this module at its end, so every name here stays importable from it, and this
module reads the ground (units, tags, ledgers, decisions, aliases, the index directory) from it. Import `kbfacts`;
imported first, this module has the facade load it, so every module still holds the one copy `kbfacts` loads."""
import sys
if "kbfacts" not in sys.modules:  # imported first: the facade loads this stage under its name, then this copy reads it
    sys.modules.pop(__name__, None)
    import kbfacts
import array, bisect, functools, hashlib, json, marshal, math, os, re, sqlite3, tempfile, threading, time
from collections import Counter, defaultdict

import kbcommon, kbid
from kbfacts import (
    CAMEL, CLAUSE_CHARS, CONTEXT_SEP, EXPANSION_WEIGHT, ID, ITEM_DECISIONS, LOG_LABEL, MAX_DECISIONS, MAX_FLAGS,
    MAX_LOGS, NONE_SENTENCE, NUMBER, PARENT_CHARS, PART_WEIGHT, PASSAGES_PER_LINE, PASSAGE_CHARS, SELF_ROOT, STOP,
    SUMMARY_WEIGHT, TITLE_WEIGHT, UNTAGGED_WEIGHT, VERSION_ID, VPREFIX, WORD, aliases, articles, bare, clip,
    clip_around, corpus, decision_block, decision_label, decision_rows, decisions_for, eval_phrases, expand,
    fact_key, fingerprint, flags_in, home_label, in_prefix, index_dir, item_decisions, key_terms, log_line,
    logs_for, read, remove_file, scope, self_eval_rows, self_places, source_rows, stem, summary_text, terms,
    tied_decisions, window_ended, windows_in
)
from kf_fresh import format_sources, fresh_mark, fresh_state, ledger_rows, printed_lines


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
    patterns = (WORD.pattern, CAMEL.pattern, NUMBER.pattern, VERSION_ID.pattern, VPREFIX.pattern)
    wdata = _weigh_data(frozenset(STOP), frozenset(kbid.STOP), patterns)
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
    its size (kb/public/python/stdlib-sqlite3-csv.md "keeps its size"). The prune runs only after the rows have
    doubled, so the VACUUM's rewrite of the file is rare. It runs after the `with con` block has committed: the
    module's default connection keeps a transaction open after the DELETE until then and a VACUUM inside one is
    refused (kb/public/python/stdlib-sqlite3-csv.md "default legacy mode"). Best effort: another process may hold
    the file."""
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
            remove_file(os.path.join(d, f))
    found.sort(reverse=True)
    for mtime, f in found[KEEP_INDEXES:]:
        if now - mtime > PRUNE_GRACE:
            remove_file(os.path.join(d, f))


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


def informative_words(keys, kdf, n, shares=None):
    """The key words that tell units apart: those held by under COMMON_SHARE of the n searched units, and always
    those held by at most one, since a word one unit holds is never common. Without that floor a small index (a
    root of one article: 3 units, cut below 0.6) keeps no word at all and every question is `none`. `shares`
    ({key word: share of the units}, rag.py eval's re-judge against its baseline file) stands in for the count of the
    words it names."""
    shares = shares or {}
    return [t for t in keys if (shares[t] * n if t in shares else kdf[t]) < max(COMMON_SHARE * n, 2)]


def key_shares(question, root=None):
    """{key word: share of the searched units that hold it} of a question, over the units a pack for `root` searches
    (the root's own for `_self`, else every root's)."""
    st = store(scope(None, root))
    _, keys, _, kdf = rank(st, question)
    n = max(st.n, 1)
    return {t: kdf[t] / n for t in keys}


def drifted_words(question, baseline, root=None):
    """{key word: (share now, share in `baseline`)} of the question's key words that the baseline ({word: share}) holds
    and whose share is on the other side of COMMON_SHARE than the baseline's: the words that tip a verdict."""
    now = key_shares(question, root)
    return {t: (s, baseline[t]) for t, s in now.items()
            if t in baseline and (s >= COMMON_SHARE) != (baseline[t] >= COMMON_SHARE)}
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


SCATTER_ARTICLES = 3  # the best articles whose domains the scatter note compares
SCATTER_DOMAINS = 2  # a `good` whose best articles lie in this many domains or more, and
SCATTER_SCORE = 15  # whose best unit scores under this, gets the scatter `check:` note; rag.scatter_calibration fits it
PASSING_UNITS = 5  # a plain key word the kb holds in this many units or fewer, in no article about it, is mentioned in passing
PASSING_MISSING = 0.25  # and the lead's printed facts miss at least this share of the key words, the rare word itself included
_QUANTITY = r"(?:memory|ram|data|storage|disk|space|bandwidth|traffic|cpu|throughput|capacity)"  # what a `how much` may count
PRICE_ASK = re.compile(  # a question for a price; a cost counted in units (`in resource units`, `how many units ... cost`) or a
    # memory or data quantity (`how much memory per device`) is no money; a licence word asks for money whatever is counted;
    # `how much is OneDrive storage per user` names a product, so a quantity word asks for none only right after `how much`
    # or, with no `is`/`are` verb after it, anywhere in the line; a line of its own is read alone (a cost asked on a later one)
    r"(?im)\b(?:price|prices|pricing)\b"
    r"|^(?!.*\bhow many\s+(?:\w+\s+){0,2}(?:units?|points?|tokens?|requests?|calls?)\b).*?"
    r"\bcosts?\b(?!.*\bin\s+(?:\w+\s+){0,2}(?:units?|points?|tokens?|requests?|calls?)\b)"
    r"|\bhow much\b(?=.*\b(?:licen[cs]es?|subscriptions?|seats?)\b)"
    r"|\bhow much\b"
    r"(?!\s+(?:(?:extra|more|additional|total|free|local|available)\s+)?" + _QUANTITY + r"\b)"
    r"(?!(?!\s+(?:is|are|was|were|will|would)\b).*\b" + _QUANTITY + r"\b)"
    r"(?=.*\bper\s+(?:user|device|month|year)\b)")
AMOUNT = re.compile(r"(?i)[$€£]\s?\d|\b\d[\d,.]*\s?(?:usd|eur|gbp|pln|dollars?|euros?)\b|\b(?:usd|eur|gbp|pln)\s?\d")  # an amount


def article_domain(qpath):
    """The domain directory of a qualified article path (`public/intune/x.md`: `intune`); a file at the root of its
    kb root is its own domain."""
    return bare(qpath).split("/")[0]


def name_apart(question, known, held):
    """The multi-word names of the question (two or more capitalised words in a row after its first word, each a key
    word the kb holds: `Exchange Online`) that none of the lead article's printed facts holds beside any of the
    question's lower-case key words: the name sits in some facts and what is asked about it in others. `held` is the
    set of key words each printed fact holds. [(stems of the name, stems of the lower-case key words)]"""
    words, run, runs = WORD.findall(question), [], []
    for i, w in enumerate(words + [""]):
        if i and w.istitle() or w[:1].isdigit() and run:
            run.append(stem(w.lower()))
        else:
            runs += [run] if len(run) > 1 else []
            run = []
    plain = {stem(w) for w in words if w.islower()} & set(known)
    return [(name, plain) for name in runs if plain and set(name) <= set(known)
            and not any(set(name) <= h and h & plain for h in held)]


ENDED_MARK = "  no longer valid (validity window ended, not current):"  # above a pack's facts whose window has ended
AS_OF_SHARE = 0.4  # the share of the best score a fact needs to count among those an as-of pack leaves out (as pack's own cut)


def valid_on(text, as_of):
    """Whether a fact's validity window holds the date `as_of` (YYYY-MM-DD, both ends included): a fact with no window,
    an open end or a commit window (no date to compare) holds every date it is not dated out of."""
    for w in windows_in(text):
        if w["error"] or w["kind"] != "date":
            continue
        if w["start"] > as_of or (w["end"] and w["end"] < as_of):
            return False
    return True


def pack(question, budget=1200, domain=None, max_articles=4, fmt="detailed", footer=True, root=None, invalidated=False,
         item=None, st=None, shares=None, as_of=None):
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
    `check:` note (verdict unchanged) when a name the question uses is nowhere in the lead article, when no tagged
    fact among the top hits holds half of 4+ key words, or when its best SCATTER_ARTICLES articles span
    SCATTER_DOMAINS or more domains and its best unit scores under SCATTER_SCORE (`scatter`; `top_score` and
    `top_domains` are the two values, None and [] when the pack is not a `good` the note applies to; the note
    changes no route). Two notes read the lead article's printed facts and do set the route (`split`): `passing`
    (a plain alphabetic word of the question that the kb holds in at most PASSING_UNITS units, that is no word of the
    lead article's title or applies_to, while those facts miss another key word and, with the rare word itself, at
    least PASSING_MISSING of the key words: a tempdb file count against the one line that names tempdb) and `priced`
    (a question for a price, PRICE_ASK: a cost in a unit of measure is none, and no printed fact of the lead holds an
    AMOUNT); `passing` is the list of words, `priced` a bool. A word that is a product alias (_tools/aliases.csv) counts as present where any alias of the product is;
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
    (self_store), else the index's. `shares` ({key word: share}) judges the words it names informative by that share
    instead of their count: the one argument `rag.py eval` re-judges a failing row with, against its baseline file;
    no lookup passes it.
    Observed signals: a kb that keeps `_logs.csv` rows adds, after the decisions, `observed signal (LOG, not a fact):`
    and the active rows whose context is a printed article or fact (logs_for: at most MAX_LOGS lines, newest first, each
    with the dates it covers), paid from what budget the facts leave, so a small budget drops them first. They are
    computed after the verdict, the route and the `check:` lines and change none of them, nor any fact line; a `none`
    that routes web prints none. Under the same label follow at most MAX_FLAGS `flagged (feedback, not a fact):` lines,
    one per printed fact line that a committed feedback report flags (flags_in), paid from the same budget and as little
    a part of the verdict. A kb with none prints what it always did, byte for byte.
    Validity: with `as_of` (YYYY-MM-DD) only the facts whose window holds the date (valid_on) rank, so the verdict reads
    over the facts valid then, and a line under the coverage names how many of the best-ranked matching facts (the top
    40 at AS_OF_SHARE of the best score) the date left out. With none, a fact whose window has ended (window_ended)
    prints after the article's others under ENDED_MARK, never among the current facts. fmt
    `concise` drops the article flags and the source url footer; footer=False leaves the footer out of the text (pack_many prints one shared footer). `domain` (bare `intune`
    or qualified `public/intune`) and `root` narrow the units (scope()); paths print qualified (`public/intune/x.md`)."""
    rules = scope(domain, root) == SELF_ROOT  # the kb's own rule docs: facts without sources, no web route
    st = st or store(scope(domain, root))
    ranked, keys, holders, kdf = rank(st, question)
    left_out, kdf_kb, dropped = None, kdf, 0
    if as_of and not rules:
        # the facts valid on the date are the corpus: the words' counts and the unit count that judge which words tell
        # units apart are read over them, so a word the dated-out facts alone held counts as lacking, not as common
        top = ranked[0][0] if ranked else 0
        out = {i for i in {x[1] for x in ranked}.union(*holders.values()) if not valid_on(st.unit(i)["text"], as_of)}
        left_out = sum(1 for k, x in enumerate(ranked[:40]) if x[1] in out and x[0] >= AS_OF_SHARE * top)
        ranked = [x for x in ranked if x[1] not in out]
        holders = {t: ids - out for t, ids in holders.items()}
        kdf = {t: len(ids) for t, ids in holders.items()}
        dropped = len(out)
    if item:
        ranked = [x for x in ranked if st.paths[x[1]] in item["docs"]]
    n = max(st.n - dropped, 1)
    informative = informative_words(keys, kdf, n, shares)
    missing = [t for t in informative if not kdf_kb[t]]  # a word the kb never holds, whatever the date
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
    order = [a for a in order if by_art[a][0][0] >= (0.5 if a.endswith(".md") else 0.65) * best]
    # the article whose one unit holds the most informative key words leads, the others keep their score order: a data
    # row that holds the question's words (a model's row of models.csv) outranks prose facts that each hold a rare
    # word or two, and no tie or lead of the score changes
    held = {a: max(sum(1 for t in informative if has(u, t)) for s, u in by_art[a] if s >= 0.4 * best) for a in order}
    if order:
        lead = max(order, key=lambda a: held[a])
        order = ([lead] + [a for a in order if a != lead])[:max_articles]
    # an off-domain question (VMware Horizon, SAP GUI): its product is a rare name the kb mentions in passing, and no
    # line the pack could print holds it, whatever the other words match; a line holds it as a word of its own, not
    # as the part of a hyphenated common word (Horizon in "long-horizon tasks")
    if verdict != "none":
        cand = [u for a in order for _, u in sorted((x for x in by_art[a] if x[0] >= 0.4 * best), key=lambda x: -x[0])[:6]]

        # the words the question spells (a one-letter part, the V of Hyper V, included; a stop word excluded)
        spelled = {stem(p) for p in re.findall(r"\w+", question.lower()) if p not in STOP}

        def holds_name(u, t):
            if not has(u, t):
                return False
            words = WORD.findall(u["text"].lower())
            compounds = [[stem(p) for p in w.split("-")] for w in words if "-" in w]
            # a hyphen part holds the name when another part of its compound is a word of the question too
            # (Hyper V finds hyper-v, Invoke WebRequest finds Invoke-WebRequest; "long-horizon" stays no VMware Horizon)
            if (t in key_terms(u["text"]) or not any(t in c for c in compounds)
                    or any(t in c and any(o in spelled for o in c if o != t) for c in compounds)):
                return True  # a word of its own, or held through the title, section, an alias or a dotted or camel part
            meta = st.arts.get(u["path"], {})
            return t in key_terms(f"{meta.get('title', '')} {u['section']}")
        if any(len(t) > 2 and kdf[t] < RARE_NAME * n and not any(holds_name(u, t) for u in cand) for t in named & set(known)):
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
    taken, rows = defaultdict(list), {}
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
    else:
        for art in order:
            taken[art] = sorted((x for x in by_art[art] if x[0] >= 0.4 * best), key=lambda x: -x[0])[:6]
            if not art.endswith(".csv"):  # facts read in article order; rows of a table go by score, so the budget cuts the weakest
                taken[art].sort(key=lambda x: x[1]["line"])
        # the marks of these lines read the ledgers once, for the sources they cite and no other
        rows = ledger_rows({i for g in taken.values() for _, u in g
                            for i in [*(i for p in u["tags"] for i in p["ids"]), *ID.findall(u["text"])]})
        fresh_state(rows)
    for art in order:
        picked = taken[art]
        lines = []  # (line, whether its window has ended), in article order
        one_section = len({u["section"] for _, u in picked}) == 1  # rule docs: the heading once, else on each line
        for s, u in picked:
            if rules:
                text = clip_around(u["text"], PASSAGE_CHARS + PARENT_CHARS + CLAUSE_CHARS,
                                   anchor_phrases.get(u.get("tested"), ()), set(informative))
            else:
                text = clip(u["text"], 420)
            where = f" § {u['section']}:" if rules and u["section"] and not one_section else ""
            mark = f" [tested {u['tested']}]" if u.get("tested") else ""
            if not rules and (fresh := fresh_mark(u, rows)):
                mark += f" [{fresh}]"
            line = f"- {u['path']}:{u['line']}{mark}{where} {text}" + ("" if u["tags"] else " (no tag)")
            line += ("\n" + snippet_code(u)) if snippet_code(u) else ""
            new_ids = [i for p in u["tags"] for i in p["ids"]] + ID.findall(text)
            # the root prefix of the path (`public/`) is not counted: a pack chooses the same lines in any layout
            cost = len(line) - (len(u["path"]) - len(bare(u["path"]))) + url_cost * len(set(new_ids) - set(cited))
            if used + cost > limit and (lines or groups):
                used = limit
                break
            lines.append((line, not (rules or as_of) and window_ended(u["text"])))
            printed.append(u)
            used += cost
            cited += new_ids
        if lines:
            more = sum(1 for x in ranked if st.paths[x[1]] == art and x[0] >= 0.4 * best) - len(lines)
            # a fact whose window has ended is not current: it follows the others, under its own mark
            tail = [(f"  (+{more} more matching lines in {art}: kb_search with more words, or kb_show)", False)] if more > 0 else []
            # e.g. hundreds of similar rows in a data file: the answer may be one of these
            arrange = lambda ls: [l for l, e in ls if not e] + ([ENDED_MARK] if any(e for _, e in ls) else []) + [l for l, e in ls if e]
            items = arrange(lines + tail)
            short = arrange((lines + tail)[:2])
            meta = st.arts.get(art, {})
            head = f"## {art}" + (f"  {meta.get('title', '')}" if meta else "")
            if rules and one_section and picked[0][1]["section"]:
                head += f"  § {picked[0][1]['section']}"
            flags = ", ".join(filter(None, (meta.get("status"), f"retrieved {meta['retrieved_utc']}" if meta.get("retrieved_utc") else "")))
            groups.append((head + (f"  [{flags}]" if flags and not concise else ""), items, short))
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
    # a `good` whose three best articles lie in separate domains and whose best unit scores low: the words matched a
    # little in each of several topics, none of them the one asked about. A query performance prediction signal fitted
    # to this kb's labelled questions (rag.scatter_calibration), a note and never a verdict or route change: it flags
    # a few true `good` packs too.
    top_score, top_domains, scatter = None, [], None
    if verdict == "good" and not lifted and not rules:
        top_score = best
        top_domains = list(dict.fromkeys(article_domain(a) for a in list(by_art)[:SCATTER_ARTICLES]))
        if len(top_domains) >= SCATTER_DOMAINS and top_score < SCATTER_SCORE:
            scatter = (top_score, top_domains)
    # a `good` whose question's subject the kb only touches: its words are spread over articles of other topics, and
    # the lead's printed facts hold most of them, but (passing) one plain word the kb holds in a few units and no article
    # about it is the question's subject, and another key word is missing from them, together a quarter of the key words
    # (tempdb in a line on encryption at rest, for a count of tempdb data files; one word of ten missing is a paraphrase,
    # an eval row about `noqa`), or (priced) the question asks for a price and no printed fact of the lead states an
    # amount. Notes that route `split`, never a verdict change: a lexical rule cannot tell which word is the subject.
    passing, priced, parted = [], False, []
    lead_units = [u for u in printed if paths and u["path"] == paths[0]]
    if verdict == "good" and lead_units and not lifted and not rules:
        lead_meta = st.arts.get(paths[0], {})
        lead_own = set(key_terms(f"{lead_meta.get('title', '')} {lead_meta.get('applies_to', '')}"))
        lead_has = set().union(*({t for t in known if has(u, t)} for u in lead_units))
        plain = {stem(w.lower()) for w in WORD.findall(question) if w.isalpha() and (w.islower() or w.istitle())}
        rare = sorted(t for t in plain & set(known) if kdf[t] <= PASSING_UNITS and t not in lead_own)
        absent = [t for t in known if t not in lead_has]
        if rare and any(t not in rare for t in absent) and len(absent) >= PASSING_MISSING * len(known):
            passing = rare
        priced = bool(PRICE_ASK.search(question)) and not any(AMOUNT.search(u["text"]) for u in lead_units)
        parted = name_apart(question, known, [{t for t in known if has(u, t)} for u in lead_units])
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
    if left_out is not None:
        out.append(f"as of {as_of}: {left_out} matching fact{'' if left_out == 1 else 's'} left out as not yet valid or "
                   "no longer valid then")
    if unmatched:
        names = {stem(w.lower()): w for w in WORD.findall(question)}
        out.append(f"check: {paths[0]} never mentions {', '.join(names.get(t, t) for t in unmatched)}; the facts may be "
                   "about something related. Answer only if a cited line answers the question itself.")
    if spread:
        out.append(f"check: no single fact holds half the key words (at most {spread[0]} of {spread[1]}); the facts may "
                   "be about something related. Answer only if a cited line answers the question itself.")
    if scatter:
        out.append(f"check: the best articles lie in {len(top_domains)} domains ({', '.join(top_domains)}) and the best "
                   f"fact scores only {top_score:.1f}; the facts may be about something related. Answer only if a cited "
                   "line answers the question itself.")
    if passing:
        said = own_words(question, passing)
        out.append(f"check: {', '.join(said)} {'is' if len(said) == 1 else 'are'} held by only a few lines of the kb, "
                   f"in no article about {'it' if len(said) == 1 else 'them'}, and the lead article's facts miss other "
                   "key words; the facts may be about something related. Answer only if a cited line answers the "
                   "question itself.")
    together = [f"{' '.join(own_words(question, name))} beside {', '.join(own_words(question, plain))}"
                for name, plain in parted]
    if parted:
        out.append(f"check: no fact of the lead article holds {', '.join(together)}; the facts may be about "
                   "something related. Answer only if a cited line answers the question itself.")
    if priced:
        out.append("check: the question asks for a price and no fact of the lead article states an amount; the facts "
                   "may be about something related. Answer only if a cited line answers the question itself.")
    fresh = freshness(question, missing, st.arts.get(paths[0] if paths else (order[0] if order else ""), {}))
    if fresh:
        out.append(fresh)
    route = None if rules and verdict == "none" else route_of(verdict, unmatched, spread, missing,
                                                                   passing or priced or parted)
    # a near miss (a `none` that routes split: only a language or format name is nowhere in the kb) prints what a
    # `weak` pack would, its facts and source footer, and no none sentence, so the reader answers the part the kb has
    # (sp_getapplock for the T-SQL question) and looks up only the rest
    shut = verdict == "none" and (rules or route != "split") and not item  # an item's brief prints its passages whatever the verdict
    if shut and not rules:
        out.append(NONE_SENTENCE)
    has = own_words(question, set(hit) | dheld)
    lacks = own_words(question, [t for t in informative if t not in hit and t not in dheld]) + together
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
    for h, items, short in groups if not shut else [(g[0], g[2], None) for g in groups[:1]]:
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
    flagged = []  # lines of the printed facts that a committed feedback report flags: never a fact, never in the verdict
    if not (shut or rules):
        for path in dict.fromkeys(u["path"] for u in printed):
            flagged += flags_in(path, [u["line"] for u in printed if u["path"] == path])
    fshown = []
    for line in flagged[:MAX_FLAGS]:
        if used + lused + len(line) + 1 > limit:
            break
        llines.append(line)
        fshown.append(line)
        lused += len(line) + 1
    if llines:
        out += ["", LOG_LABEL] + llines
    if shut or rules:
        srcs = []
    if srcs and footer and not concise:
        out += ["", "sources:"] + format_sources(srcs, rows)
    return {"verdict": verdict, "missing": missing, "matched": sorted(hit), "informative": informative, "known": known,
            "unmatched": unmatched, "spread": spread, "scatter": scatter, "passing": passing, "priced": priced,
            "top_score": top_score, "parted": together,
            "top_domains": top_domains, "route": route, "has": has, "lacks": lacks, "paths": paths,
            "tested": [t[0] for t in tested], "pinned": sum(1 for u in printed if u.get("tested")),
            "printed": [] if rules else printed_lines(printed, rows),
            "key_missing": own_words(question, unheld),
            "sources": [s[0] for s in srcs], "source_rows": srcs, "text": "\n".join(out),
            "decisions": [{"id": d["id"], "status": d["status"], "label": decision_label(d), "path": d["path"],
                           "line": d["line"], "text": d["text"], "answers": d["answers"]} for d in kept],
            "logs": [{"id": r["id"], "path": r["path"], "line": r["line"], "observed_from": r["observed_from"],
                      "observed_to": r["observed_to"], "text": r["text"]} for r in lshown],
            "flags": fshown}


# language and format names: a question asking for a topic the kb covers in one of them (T-SQL for sp_getapplock) is a
# near miss when they are the only words the kb lacks, not a topic it does not cover
LANGUAGE_NAMES = frozenset(("t-sql", "tsql", "powershell", "python", "bash", "kql", "json", "yaml", "xml", "csv"))


def route_of(verdict, unmatched, spread, missing, noted=False):
    """Where a question goes after the pack: None (answer from the pack), `split` (the kb has part of it: answer what
    the pack holds, look up what it lacks in the live docs) or `web` (the kb does not cover it). A `good` pack is
    flagged, and routes `split`, when it has a `check:` line (`unmatched`, `spread`, `noted`: a word held in passing
    or a price asked with no amount) or a word nowhere in the kb (`missing`); a clean `good` routes nowhere. A `none`
    pack routes `web`, except a near miss: when every word nowhere in the kb is a language or format name
    (LANGUAGE_NAMES) it routes `split`."""
    if verdict == "none":
        return "split" if missing and all(t in LANGUAGE_NAMES for t in missing) else "web"
    if verdict == "weak" or unmatched or spread or missing or noted:
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
