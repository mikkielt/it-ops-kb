#!/usr/bin/env python3
"""Collision-free kb ids (stdlib only). Several writers can add sources in parallel and merge without clashes.

  kbid.py url URL [URL ...]      print the source id of each url (and the id already in _sources.csv, if any)
  kbid.py answer "QUESTION"      suggest a QK-<slug> answer id for _answers.md (and say if it is taken)
  kbid.py eval "QUESTION"        the EV-<slug> id for a _tools/lookup_eval.csv row (and say if it is taken)
  kbid.py check                  hash ids in _sources.csv: collisions and ids that do not match their url

Source ids. Legacy ids `S<digits>` (S100 ... S2204) stay valid forever and are never renumbered. Every new
source gets `S-` + the first 8 characters of the lowercase RFC 4648 base32 (a-z2-7, no padding) of the
sha256 of its normalized url, e.g. `S-k3f7q2zd`. Same url => same id, so two writers adding it converge.

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

KB = kbcommon.KB  # KB_ROOT, else this repository
LEGACY_ID = r"S\d+"
HASH_ID = r"S-[a-z2-7]{8}"
SOURCE_ID = re.compile(rf"\b{HASH_ID}\b|\bS\d{{3,4}}\b")  # an id cited in text: legacy ids are S100-S2204, so prose like S3 never matches
ANY_ID = re.compile(r"\bS-[A-Za-z0-9]+|S\d+")               # anything that claims to be an id (in fact tags)
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


def source_id(url):
    """`S-` + 8 lowercase base32 characters of sha256(normalize_url(url))."""
    digest = hashlib.sha256(normalize_url(url).encode("utf-8")).digest()
    return "S-" + base64.b32encode(digest).decode("ascii").lower()[:8]


def is_hash_id(sid):
    return re.fullmatch(HASH_ID, sid) is not None


def is_source_id(sid):
    return re.fullmatch(rf"{HASH_ID}|{LEGACY_ID}", sid) is not None


def canonical_id(sid):
    """User input to the stored spelling: `s0100` -> `S0100`, `s-K3F7Q2ZD` -> `S-k3f7q2zd`."""
    sid = sid.strip()
    return "S-" + sid[2:].lower() if sid[:2].upper() == "S-" else sid.upper()


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


def check_sources(rows):
    """Errors for hash ids in _sources.csv rows: (a) two different normalized urls with the same hash id,
    (b) a hash id that is not the hash of its row's url (typed by hand or copied from another row)."""
    errors, by_hash = [], {}
    for r in rows:
        url = (r.get("url") or "").strip()
        if url:
            by_hash.setdefault(source_id(url), set()).add(normalize_url(url))
        sid = r.get("id") or ""
        if is_hash_id(sid) and source_id(url) != sid:
            errors.append(f"source id {sid} does not match its url (the url hashes to {source_id(url)}; "
                          f"get ids with `python3 _tools/kbid.py url <URL>`)")
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
    sub.add_parser("check", help="hash-id collisions and ids that do not match their url")
    a = ap.parse_args()
    try:
        rows = read_sources()
    except (OSError, csv.Error) as e:
        if a.cmd == "check":
            sys.exit(f"cannot read _sources.csv: {e}")
        rows = []
    if a.cmd == "url":
        have = {}
        for r in rows:
            if r.get("url"):
                have.setdefault(normalize_url(r["url"]), []).append(r.get("id", ""))
        for url in a.urls:
            old = have.get(normalize_url(url))
            print(f"{source_id(url)}\t{url}" + (f"\talready in _sources.csv as {', '.join(old)} (reuse it)" if old else ""))
    elif a.cmd == "answer":
        aid = answer_id(" ".join(a.question))
        try:
            with open(os.path.join(KB, "_answers.md"), encoding="utf-8") as f:
                taken = aid in answer_ids(f.read())
        except OSError:
            taken = False
        print(aid + ("\talready used in _answers.md: pick a more specific slug" if taken else ""))
    elif a.cmd == "eval":
        question = " ".join(a.question)
        eid = eval_id(question)
        try:
            with open(kbcommon.data_path("lookup_eval.csv"), encoding="utf-8", newline="") as f:
                have = {r["id"]: r["question"] for r in csv.DictReader(f)}
        except OSError:
            have = {}
        same = have.get(eid, "").strip().lower() == question.strip().lower()
        print(eid + ("\tthis question is already in lookup_eval.csv" if same else
                     "\ttaken by another question: use " + eid + "-2" if eid in have else ""))
    else:
        errors = check_sources(rows)
        print(f"sources={len(rows)} hash_ids={sum(1 for r in rows if is_hash_id(r.get('id') or ''))} errors={len(errors)}")
        for e in errors:
            print("ERROR", e)
        sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
