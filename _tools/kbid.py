#!/usr/bin/env python3
"""Collision-free kb ids (stdlib only). Several writers can add sources in parallel and merge without clashes.

  kbid.py url URL [URL ...] [--root NAME]   print the source id of each url in a root (default public), and the
                                            id already in the root's _sources.csv, if any
  kbid.py answer "QUESTION" [--root NAME]   suggest a QK-<slug> answer id for the root's _answers.md (and say if it
                                            is taken)
  kbid.py eval "QUESTION" [--root NAME]     the EV-<slug> id for a row of the root's _retrieval/lookup_eval.csv
  kbid.py check                             every root's _sources.csv: hash-id collisions, ids that do not match
                                            their url or do not carry the root's prefix

Source ids. Each root has its own id prefix (`id_prefix` in its _root.md; public's is `S`), so ids are unique
across roots and a citation names its root. Legacy ids `S<digits>` (S100 ... S2204) are the public root's, stay
valid forever and are never renumbered. Every new source gets `<prefix>-` + the first 8 characters of the lowercase
RFC 4648 base32 (a-z2-7, no padding) of the sha256 of its normalized url, e.g. `S-k3f7q2zd`. Same url in the same
root => same id, so two writers adding it converge.

URL normalization (conservative; nothing that could point at a different resource is changed):
  - surrounding whitespace is stripped;
  - scheme and host are lowercased; user info, path, query and their case and %-escapes are kept as-is;
  - the default port is dropped (:80 for http, :443 for https);
  - the fragment (#...) is dropped;
  - an empty path becomes "/"; a trailing "/" on a non-root path is dropped;
  - an empty query ("?" with nothing after it) is dropped.

Answer ids. New research answers in _answers.md are headed `## QK-<slug>. <question>`: lowercase words
joined by hyphens. Existing Q/QA/QS/QR/QG/R headings stay.
"""
import argparse, base64, csv, functools, hashlib, os, re, sys, urllib.parse
import kbcommon
from kbcommon import read_sources  # noqa: F401  (kbgit and the tests call kbid.read_sources)

def _prefixes():
    """The roots' id prefixes (public's `S` first); only `S` when a ROOT_FILE is broken (check.py reports it)."""
    try:
        return [r.id_prefix for r in kbcommon.roots()]
    except (kbcommon.RootError, OSError):
        return ["S"]


PREFIXES = _prefixes()
_P = "|".join(map(re.escape, PREFIXES))
LEGACY_ID = r"S\d+"  # the public root's numbered ids; no other root has them
HASH_ID = rf"(?:{_P})-[a-z2-7]{{8}}"  # <prefix>-<8 base32 characters> of a known root
ID_PATTERN = rf"{HASH_ID}|S\d{{3,4}}"  # a cited id, for building other patterns (no \b)
SOURCE_ID = re.compile(rf"\b{HASH_ID}\b|\bS\d{{3,4}}\b")  # an id cited in text: legacy ids are S100-S2204, so prose like S3 never matches
# anything that claims to be an id (in fact tags): `S-` with any suffix, another root's prefix with an 8-character
# suffix (so a word like TGT-issuance is not one unless TGT is a root's prefix), or S<digits>
_OTHER = "|".join(re.escape(p) for p in PREFIXES if p != "S")
ANY_ID = re.compile(r"\bS-[A-Za-z0-9]+|S\d+" + (rf"|\b(?:{_OTHER})-[A-Za-z0-9]{{8}}\b" if _OTHER else ""))
ANSWER_HEAD = re.compile(r"^## ([A-Za-z][A-Za-z0-9-]*)\. ", re.M)
QK_ID = re.compile(r"QK-[a-z0-9]+(?:-[a-z0-9]+)*")
EV_ID = re.compile(r"EV-[a-z0-9]+(?:-[a-z0-9]+)*")
EVAL_FILLER = {"i", "you", "me", "my", "there", "s", "much", "many", "happens", "happen", "long", "big"}
DEFAULT_PORTS = {"http": 80, "https": 443}
STOP = {"a", "an", "the", "and", "or", "of", "for", "to", "in", "on", "with", "is", "are", "be", "can", "how", "what",
        "which", "when", "where", "why", "does", "do", "it", "its", "by", "from", "as", "at", "we", "our", "should"}


@functools.lru_cache(maxsize=None)
def normalize_url(url):
    """The url in the canonical form that source ids are hashed from (rules in the module docstring)."""
    p = urllib.parse.urlsplit(url.strip())
    scheme = p.scheme.lower()
    host = (p.hostname or "").lower()
    if ":" in host:  # IPv6 literal
        host = f"[{host}]"
    try:
        port = p.port
    except ValueError:  # not a number: keep the netloc untouched apart from case
        port = None
        host = p.netloc.rpartition("@")[2].lower()
    netloc = (p.netloc.rpartition("@")[0] + "@" if "@" in p.netloc else "") + host
    if port is not None and port != DEFAULT_PORTS.get(scheme):
        netloc += f":{port}"
    path = p.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/") or "/"
    return urllib.parse.urlunsplit((scheme, netloc, path, p.query, ""))


def source_id(url, prefix="S"):
    """`<prefix>-` + 8 lowercase base32 characters of sha256(normalize_url(url)); the prefix is the root's."""
    digest = hashlib.sha256(normalize_url(url).encode("utf-8")).digest()
    return f"{prefix}-" + base64.b32encode(digest).decode("ascii").lower()[:8]


def id_prefix(sid):
    """The root prefix of a source id (`S` for a legacy id), or None when it is not shaped like one."""
    m = re.fullmatch(r"([A-Z]{1,4})-[a-z2-7]{8}|S\d+", sid or "")
    return (m.group(1) or "S") if m else None


def is_hash_id(sid):
    return re.fullmatch(r"[A-Z]{1,4}-[a-z2-7]{8}", sid) is not None


def is_source_id(sid):
    return re.fullmatch(rf"{HASH_ID}|{LEGACY_ID}", sid) is not None


def canonical_id(sid):
    """User input to the stored spelling: `s0100` -> `S0100`, `s-K3F7Q2ZD` -> `S-k3f7q2zd`, `i-ABC...` -> `I-abc...`."""
    sid = sid.strip()
    m = re.fullmatch(r"([A-Za-z]{1,4})-(\w+)", sid)
    return f"{m.group(1).upper()}-{m.group(2).lower()}" if m else sid.upper()


def sort_key(sid):
    """Legacy ids in numeric order, then hash ids alphabetically."""
    return (0, int(sid[1:]), "") if re.fullmatch(LEGACY_ID, sid) else (1, 0, sid)


def answer_id(question):
    """A QK-<slug> id from a question: up to 6 informative lowercase words, hyphenated."""
    words = [w for w in re.findall(r"[a-z0-9]+", question.lower()) if w not in STOP] or ["answer"]
    return "QK-" + "-".join(words[:6])


def eval_id(question):
    """An EV-<slug> id for a lookup_eval.csv row, the same rule as answer_id: two writers adding the same question
    get the same id (union merge then keeps one line), and different questions rarely collide (tests.py checks)."""
    words = [w for w in re.findall(r"[a-z0-9]+", question.lower()) if w not in STOP | EVAL_FILLER] or ["question"]
    return "EV-" + "-".join(words[:6])


def answer_ids(text):
    return ANSWER_HEAD.findall(text)


def check_sources(rows, prefix="S", name="public"):
    """Errors for the ids in one root's _sources.csv rows (the root's id prefix and name): (a) two different
    normalized urls with the same hash id, (b) a hash id that is not the hash of its row's url (typed by hand or
    copied from another row), (c) an id without the root's prefix (legacy S<digits> ids are the public root's)."""
    errors, by_hash = [], {}
    for r in rows:
        url = (r.get("url") or "").strip()
        if url:
            by_hash.setdefault(source_id(url, prefix), set()).add(normalize_url(url))
        sid = r.get("id") or ""
        if id_prefix(sid) is None:
            errors.append(f"malformed source id {sid!r} (want {prefix}-<8 base32>"
                          + (" or S<digits>" if prefix == "S" else "") + ")")
        elif id_prefix(sid) != prefix:
            errors.append(f"source id {sid} is not an id of root {name} (its ids are {prefix}-<8 base32 characters>"
                          + (" or legacy S<digits>" if prefix == "S" else "") + ")")
        elif is_hash_id(sid) and source_id(url, prefix) != sid:
            errors.append(f"source id {sid} does not match its url (the url hashes to {source_id(url, prefix)}; "
                          f"get ids with `python3 _tools/kbid.py url <URL>" + ("" if prefix == "S" else f" --root {name}")
                          + "`)")
    for h, urls in sorted(by_hash.items()):
        if len(urls) > 1:
            errors.append(f"hash id collision {h}: {' | '.join(sorted(urls))}")
    return errors


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("url", help="print the source id of each url"); u.add_argument("urls", nargs="+")
    q = sub.add_parser("answer", help="suggest a QK-<slug> answer id"); q.add_argument("question", nargs="+")
    e = sub.add_parser("eval", help="the EV-<slug> id for a lookup_eval.csv row"); e.add_argument("question", nargs="+")
    for p in (u, q, e):
        p.add_argument("--root", default="public", help="the root the id is for (default public)")
    sub.add_parser("check", help="every root: hash-id collisions, ids that do not match their url or their root's prefix")
    a = ap.parse_args()
    if a.cmd == "check":
        sys.exit(cmd_check())
    try:
        root = kbcommon.root(a.root)
    except KeyError:
        sys.exit(f"no root {a.root!r} (python3 _tools/kbroot.py list)")
    except kbcommon.RootError as e:
        sys.exit(str(e))
    try:
        rows = read_rows(root)
    except (OSError, csv.Error):
        rows = []
    if a.cmd == "url":
        have = {}
        for r in rows:
            if r.get("url"):
                have.setdefault(normalize_url(r["url"]), []).append(r.get("id", ""))
        for url in a.urls:
            old = have.get(normalize_url(url))
            print(f"{source_id(url, root.id_prefix)}\t{url}"
                  + (f"\talready in {root.name}/_sources.csv as {', '.join(old)} (reuse it)" if old else ""))
    elif a.cmd == "answer":
        aid = answer_id(" ".join(a.question))
        try:
            with open(os.path.join(root.path, kbcommon.ANSWERS), encoding="utf-8") as f:
                taken = aid in answer_ids(f.read())
        except OSError:
            taken = False
        print(aid + ("\talready used in _answers.md: pick a more specific slug" if taken else ""))
    elif a.cmd == "eval":
        question = " ".join(a.question)
        eid = eval_id(question)
        try:
            with open(os.path.join(root.path, kbcommon.DATA_DIR, "lookup_eval.csv"), encoding="utf-8", newline="") as f:
                have = {r["id"]: r["question"] for r in csv.DictReader(f)}
        except OSError:
            have = {}
        same = have.get(eid, "").strip().lower() == question.strip().lower()
        print(eid + ("\tthis question is already in lookup_eval.csv" if same else
                     "\ttaken by another question: use " + eid + "-2" if eid in have else ""))



def read_rows(root):
    """The rows of one root's _sources.csv, in file order."""
    with open(os.path.join(root.path, kbcommon.SOURCES), encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def cmd_check():
    """kbid.py check over every root: the exit code."""
    try:
        roots = kbcommon.roots()
    except kbcommon.RootError as e:
        print("ERROR", e)
        return 1
    n = hashes = 0
    errors = []
    for root in roots:
        try:
            rows = read_rows(root)
        except (OSError, csv.Error) as e:
            errors.append(f"cannot read {root.name}/{kbcommon.SOURCES}: {e}")
            continue
        n += len(rows)
        hashes += sum(1 for r in rows if is_hash_id(r.get("id") or ""))
        errors += [f"{root.name}/{kbcommon.SOURCES}: {e}" for e in check_sources(rows, root.id_prefix, root.name)]
    print(f"roots={len(roots)} sources={n} hash_ids={hashes} errors={len(errors)}")
    for e in errors:
        print("ERROR", e)
    return 1 if errors else 0


if __name__ == "__main__":
    main()
