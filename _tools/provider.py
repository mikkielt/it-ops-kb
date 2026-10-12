#!/usr/bin/env python3
"""Knowledge providers: which documentation host serves a source, and its cheapest reliable change signal (stdlib only).

  provider.py [--root NAME] list                          the merged registry, one line per provider
  provider.py [--root NAME] show URL                      the provider row that serves URL, and the form fetched
  provider.py [--root NAME] probe NAME [--url URL] [--write] [--json]
                                                          live requests and deterministic checks of one provider;
                                                          --write stores the measured columns and probed_utc
  provider.py [--root NAME] read URL [--grep WORDS] [--context N] [--max N] [--from LINE] [--refresh]
                                                          the page in its provider's raw form, with the lines that
                                                          hold every word of WORDS and the url to cite

Registry. _tools/providers.csv holds the public providers, shared by every root; a root may add its own
<root>/_providers.csv for internal providers (a team wiki, an internal git host). They are merged at read time: a root
row with the name of a shared row replaces it. A url is served by the row whose `match` prefix is the longest one
that starts the url (scheme dropped); the row with match `*` serves the rest. In a prefix `*` stands for one or more
characters but `/` (a path segment, or part of one) and a trailing `$` ends the match at the url's end, so a row can
serve one page kind of a host (`github.com/*/*/issues/*$`: an issue, not the pages under it).

Columns (one row per provider):
  provider        name (lowercase)
  match           space-separated url prefixes without scheme (`learn.microsoft.com/`), or `*`
  signals         the change signals fetch tools try, cheapest first, `;`-separated:
                    pin     the url is pinned (a commit or tag in the path): its text never changes; upstream moves are
                            a new source row (census.py compares the pin with the branch tip); its repository is asked
                            once a run whether it still answers (repository_state)
                    etag    a conditional GET with the stored ETag; 304 = unchanged
                    lastmod a conditional GET with the stored Last-Modified; 304 = unchanged
                    version the page's own version id (`version_meta`); the same id = unchanged
                    git     the page is a file of a git repository the census's bare clone cache holds (a wiki page in
                            `<repo>.wiki`, a repository's README at its default branch): the blob ids there, with the
                            licence blob, the release tags and the archived banner for a repository home, are its version
                            id (census.gh_page_id); census.py check asks git for a commit since retrieval instead
                    hash    sha256 of the normalized document text (always last); where it decides, factdiff.py also
                            compares the document's heading sections (its `sections` column)
  etag            none | stable | per-request (changes on every request) | weak (W/ prefix; stable)
  lastmod         none | stable (If-Modified-Since answers 304) | stable-no-304 | request-time (the header is the
                  time of the request: useless)
  version_meta    comma-separated keys read from the raw form's front matter or the HTML <meta> tags, first = the
                  content version (`git_commit_id,updated_at,document_id`), or `-`; the key `timeline` is the latest
                  timestamp (`2026-04-21T14:53:50Z`) in the page's markup, a `datetime` attribute or a `...At` value of
                  its embedded data: an issue or a discussion carries one for each event of its timeline
  stable_id       the key of an id that survives moves and renames (`document_id`), or `-`
  raw_form        how the text is fetched: `-` (the url itself), `query:accept=text/markdown` (added query),
                  `suffix:.md` (added to the path), `header:text/markdown` (Accept header), `blob-to-raw` (a GitHub
                  or GitLab blob page read as the raw file at the same ref), `arxiv-api` (an arXiv abstract page
                  read as its entry of the export API, an Atom feed that doc_text reduces to lines)
  sitemap         sitemap index url, or `-`
  sitemap_lastmod per-page (usable per page) | added-removed (only to list added and removed urls) | none | -
  redirects       where moves are recorded (redirection files, 301 chains)
  history         where old text comes from (public repository at a commit, git at the pin, Wayback CDX)
  search_api      a search url template with {q}, or `-`
  mcp_freshness   what the provider's MCP server says about a page's version
  not_found       hard-404 (a made-up sibling url answers 404/410) | soft-404 (it answers 200) | status-<code>
                  (another code, e.g. 403) | unknown
  rate_limit      the documented or observed request limit
  reuse           the usual reuse class of the provider's pages (kbcommon.REUSE; the source row decides)
  probed_utc      when `probe --write` last measured the row (YYYY-MM-DD)
  notes           free text: what the probe could not decide

probe measures signals, etag, lastmod, version_meta, raw_form, sitemap and not_found on one sample url (the first
source of the root that the provider serves, or --url): the page twice (ETag stability), a conditional GET with the
ETag and one with Last-Modified (304?), each raw form (text/markdown answer?), the version keys in the text (`timeline`
only for a row that names it), robots.txt Sitemap lines, a made-up sibling url, `git ls-remote` of the repository a
row with the `git` signal names, and search_api with the page's title when the row has one. The other columns are
curated from the provider's documentation and kept. The `*` row serves many hosts: its probe records only probed_utc
and a note naming the sample host. Exit: 0 ok, 1 the sample could not be fetched, 2 bad arguments.

read fetches URL by its provider's raw form (`show` names it), keeps a 200 for READ_AGE days under
_cache/provider-read/ (--refresh fetches again) and prints `cite:` (the url to cite), `read:` (the url fetched, its
status and the day of the fetch) and the lines that hold every word of --grep (case-insensitive), numbered as
`N:line`, with --context lines either side as `N-line`; a repository file (raw.githubusercontent.com, /-/raw/) is
numbered by the file's own lines, any other page by the reduced text. Without --grep the text is printed from line
--from, --max lines at a time (a long line is cut around its first word). Exit: 0 text read (and a line matched),
1 the page did not answer 200, is not text (a PDF: left to the Read tool) or no line holds every word, 2 bad arguments.

Library use (factdiff.py, census.py): providers(), for_url(), document(), doc_text(), repository_state(), and for a
lookup that must answer in time (factdiff.revalidate): budget() bounds every request of a block to a total, pacing()
is the seconds a row's rate limit asks between two requests and new_run() forgets the answers of an earlier run.
"""
import argparse, contextlib, datetime, email.utils, hashlib, json, os, random, re, ssl, string, subprocess, sys, threading, time
import urllib.error, urllib.parse, urllib.request, zlib
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kbcommon  # noqa: E402

SHARED = os.path.join(kbcommon.TOOLS, "providers.csv")
ROOT_FILE = "_providers.csv"
COLS = ["provider", "match", "signals", "etag", "lastmod", "version_meta", "stable_id", "raw_form", "sitemap",
        "sitemap_lastmod", "redirects", "history", "search_api", "mcp_freshness", "not_found", "rate_limit", "reuse",
        "probed_utc", "notes"]
MEASURED = ("signals", "etag", "lastmod", "version_meta", "raw_form", "sitemap", "not_found", "probed_utc")
SIGNALS = ("pin", "etag", "lastmod", "version", "git", "hash")
UA = "it-ops-kb-fetch/1.0 (read-only change check)"
DELAY, TIMEOUT = 1.1, 30
VERSION_KEYS = ("git_commit_id", "updated_at", "document_id", "ms.date", "dateModified", "article:modified_time",
                "last-modified", "revised")
TIMELINE = "timeline"  # a version key that is no meta tag: the latest ISO timestamp in the page (version_of)
STAMP = re.compile(r"\b\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ")
PINNED = re.compile(r"(?:^|/)(?:[0-9a-f]{40})(?:/|$)|/-/raw/v?\d+\.\d+|/releases/download/|raw\.githubusercontent\.com/[^/]+/[^/]+/"
                    r"(?:refs/tags/)?v?\d+\.\d+[^/]*/")
_last, _ctx = {}, [None]
_budget = {"until": None}  # time.monotonic() at which the block under budget() ends
_failed = [0]  # requests that got no HTTP answer (network error, timeout, budget used up): failures() counts them


# ---------------------------------------------------------------- the registry

def _read(path):
    try:
        return kbcommon.load_csv(path, ("provider", "match"))[1]
    except kbcommon.CsvError:
        return []


def providers(root=None):
    """The merged registry: the shared rows, a root's own rows replacing or adding (root: a kbcommon.Root or None =
    every root of kbcommon.roots())."""
    rows = {r["provider"]: r for r in _read(SHARED)}
    for r in ([root] if root else kbcommon.roots()):
        p = os.path.join(r.path, ROOT_FILE)
        if os.path.exists(p):
            for row in _read(p):
                rows[row["provider"]] = {**row, "_root": r.name}
    return list(rows.values())


def _bare(url):
    u = urllib.parse.urlsplit(url)
    return (u.netloc.lower() + u.path) if u.netloc else url


def _served(pattern, bare):
    """Whether the `match` prefix `pattern` starts `bare` (`*`: one or more characters but `/`; a trailing `$`: ends it)."""
    if "*" not in pattern and not pattern.endswith("$"):
        return bare.startswith(pattern)
    end = pattern.endswith("$")
    rx = re.escape(pattern[:-1] if end else pattern).replace(r"\*", "[^/]+")
    return re.match(rx + (r"/?\Z" if end else ""), bare) is not None


def for_url(url, rows=None):
    """The provider row serving `url`: the longest matching prefix, else the `*` row, else None."""
    rows = providers() if rows is None else rows
    b, best, fallback = _bare(url), None, None
    for r in rows:
        for m in (r.get("match") or "").split():
            if m == "*":
                fallback = fallback or r
            elif _served(m, b) and (best is None or len(m) > best[0]):
                best = (len(m), r)
    return best[1] if best else fallback


def is_pinned(url):
    """A url whose text cannot change: a commit sha or a release tag in its path."""
    return bool(PINNED.search(url))


GH_NOT_OWNER = ("orgs", "topics", "sponsors", "marketplace", "settings", "features", "collections", "users", "apps", "enterprise",
                "search", "explore", "trending", "notifications", "login", "about", "pricing", "readme", "security")


def github_page(url):
    """(kind, repo, name) of a github.com page whose signal is not its text, else ("", "", ""). `home`: a repository's
    front page (repo `github.com/OWNER/REPO`); `wiki`: a page of its wiki (repo `github.com/OWNER/REPO.wiki`, name the
    page's title, `Home` for the wiki's front page); `wiki-repo`: the wiki's own git url (name ""); `issue`: an issue
    and `discussion`: a discussion, of a repository or of an organisation (repo "", name the number)."""
    u = urllib.parse.urlsplit(url.split("#")[0])
    p = [urllib.parse.unquote(x) for x in u.path.split("/") if x]
    if u.netloc.lower() != "github.com" or len(p) < 2:
        return "", "", ""
    if p[0] == "orgs":
        return ("discussion", "", p[3]) if len(p) == 4 and p[2] == "discussions" and p[3].isdigit() else ("", "", "")
    if p[0] in GH_NOT_OWNER:
        return "", "", ""
    repo = f"github.com/{p[0]}/{p[1]}"
    if len(p) == 2 and p[1].endswith((".wiki.git", ".wiki")):
        return "wiki-repo", repo[:-4] if repo.endswith(".git") else repo, ""
    if len(p) == 2:
        return "home", repo[:-4] if repo.endswith(".git") else repo, ""
    if p[2] == "wiki" and len(p) <= 4:
        return "wiki", repo + ".wiki", p[3] if len(p) == 4 else "Home"
    if p[2] in ("issues", "discussions") and len(p) == 4 and p[3].isdigit():
        return p[2][:-1], repo, p[3]
    return "", "", ""


def signals(row, url=""):
    """The row's signals in order; `pin` only for a pinned url, and `hash` always last."""
    out = [s.strip() for s in (row.get("signals") or "").split(";") if s.strip() in SIGNALS]
    out = [s for s in out if s != "pin" or is_pinned(url)] if url else out
    return [s for s in out if s != "hash"] + ["hash"]


# ---------------------------------------------------------------- http

def ssl_ctx():
    if _ctx[0] is None:
        cafile = os.environ.get("SSL_CERT_FILE") or ("/root/.ccr/ca-bundle.crt" if os.path.exists("/root/.ccr/ca-bundle.crt") else None)
        _ctx[0] = ssl.create_default_context(cafile=cafile)
    return _ctx[0]


class _Chain(urllib.request.HTTPRedirectHandler):
    """Follows redirects and records each hop (status, target)."""
    def __init__(self):
        self.hops = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.hops.append((code, newurl))
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def decode_body(body, encoding, limit=20_000_000):
    """`body` with its Content-Encoding (gzip, x-gzip, deflate; a list is undone last to first) taken off, at most
    `limit` bytes. urllib does not decode, and some servers (www.python.org) send gzip unasked. An unknown coding or
    a body that does not decode is returned as it came."""
    for coding in reversed([c.strip().lower() for c in (encoding or "").split(",") if c.strip()]):
        if coding == "identity":
            continue
        if coding in ("gzip", "x-gzip"):
            tries = (16 + zlib.MAX_WBITS,)
        elif coding == "deflate":
            tries = (zlib.MAX_WBITS, -zlib.MAX_WBITS)  # zlib-wrapped as the RFC says, or raw as some servers send
        else:
            return body
        for wbits in tries:
            try:
                d = zlib.decompressobj(wbits)
                out = d.decompress(body, limit)
            except zlib.error:
                continue
            body = out
            break
        else:
            return body
    return body


BUDGET_ERROR = "time budget used up"


@contextlib.contextmanager
def budget(seconds):
    """Bound every request of the block to `seconds` in all: one that could not finish in the time left is not sent and
    answers status 0 with error BUDGET_ERROR, a started one is cut at the time left. For a lookup that must answer
    within its caller's timeout; one block at a time (the budget is the process's)."""
    _budget["until"] = time.monotonic() + seconds
    try:
        yield
    finally:
        _budget["until"] = None


def failures():
    """How many requests so far got no HTTP answer: a caller that must tell an absent page from an unreachable one
    compares the count before and after its requests."""
    return _failed[0]


def spent():
    """Whether the block under budget() has used its time up."""
    return _budget["until"] is not None and time.monotonic() >= _budget["until"]


def pacing(row):
    """Seconds between two requests to one provider that its `rate_limit` column asks for: the hour over a documented
    `N requests/hour` or `N requests per hour`, never under DELAY; DELAY for a row that documents no hourly count."""
    m = re.search(r"(\d[\d,]*)\s+requests?\s*(?:/|per)\s*hour", (row or {}).get("rate_limit") or "")
    return max(DELAY, 3600 / max(1, int(m.group(1).replace(",", "")))) if m else DELAY


def request(url, headers=None, limit=20_000_000, method="GET"):
    """{status, headers (lowercase keys), body (bytes), final, hops, error}; one request per DELAY seconds per host.
    A Content-Encoding body is decoded (decode_body); the headers stay as the server sent them.
    Never raises for HTTP or network errors: status is the code, or 0 with `error`."""
    host = urllib.parse.urlsplit(url).netloc
    wait = DELAY - (time.time() - _last.get(host, 0))
    until = _budget["until"]
    if until is not None and time.monotonic() + max(wait, 0) >= until:  # under budget(): no request that cannot finish
        _failed[0] += 1
        return {"status": 0, "headers": {}, "body": b"", "final": url, "hops": [], "error": BUDGET_ERROR}
    if wait > 0:
        time.sleep(wait)
    _last[host] = time.time()
    chain = _Chain()
    opener = urllib.request.build_opener(chain, urllib.request.HTTPSHandler(context=ssl_ctx()))
    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA, "Accept": "*/*", **(headers or {})})
    out = {"status": 0, "headers": {}, "body": b"", "final": url, "hops": chain.hops, "error": ""}
    try:
        with opener.open(req, timeout=TIMEOUT if until is None else max(0.5, min(TIMEOUT, until - time.monotonic()))) as r:
            out.update(status=r.status, headers={k.lower(): v for k, v in r.headers.items()}, body=r.read(limit), final=r.geturl())
    except urllib.error.HTTPError as e:
        out.update(status=e.code, headers={k.lower(): v for k, v in (e.headers or {}).items()}, final=e.geturl() or url)
        try:
            out["body"] = e.read(limit)
        except Exception:  # noqa: BLE001
            pass
    except Exception as e:  # noqa: BLE001 - a change check must never stop a run
        out["error"] = f"{type(e).__name__}: {str(getattr(e, 'reason', e))[:120]}"
    if out["error"]:
        _failed[0] += 1
    if out["body"] and out["headers"].get("content-encoding"):
        out["body"] = decode_body(out["body"], out["headers"]["content-encoding"], limit)
    return out


# ---------------------------------------------------------------- the repository of a pinned url

GH_API_MAX, GH_API_RESERVE = 50, 5  # GitHub REST requests one run asks; the remaining count it stops at (the limit is 60 an hour)
_repos, _repo_locks, _repo_guard, _gh_api = {}, {}, threading.Lock(), {"asked": 0, "left": None, "seen": 0.0}


def new_run():
    """Begin a run in a process that lives on (the kb MCP server): the repositories already asked and the requests
    counted are forgotten; the remaining count GitHub last reported stands for the hour it was reported in."""
    with _repo_guard:
        _repos.clear()
        _repo_locks.clear()
        _gh_api["asked"] = 0


def repository(url):
    """(key, api, raw) of the repository a pinned url names, or ("", "", "") for a host with no route here. `key` is
    `github.com/OWNER/REPO` (lowercase); `api` the forge's own route to it (GitHub's REST API, GitLab's projects API:
    GitLab's web raw path redirects to sign-in); `raw` a raw file of the url's own pinned path on GitHub, which is not
    the REST API and costs none of its 60 requests an hour, or "" when the url names none (a tree, a release, a commit)."""
    u = urllib.parse.urlsplit(url.split("#")[0])
    host, p = u.netloc.lower(), [urllib.parse.unquote(x) for x in u.path.split("/") if x]
    if host == "raw.githubusercontent.com" and len(p) >= 4:
        return f"github.com/{p[0]}/{p[1]}".lower(), f"https://api.github.com/repos/{p[0]}/{p[1]}", url.split("#")[0].split("?")[0]
    if host == "github.com" and len(p) >= 3 and p[0] not in GH_NOT_OWNER:
        raw = raw_url(url, {"raw_form": "blob-to-raw"})[0] if p[2] == "blob" and len(p) >= 5 else ""
        return f"github.com/{p[0]}/{p[1]}".lower(), f"https://api.github.com/repos/{p[0]}/{p[1]}", raw
    if host == "api.github.com" and len(p) >= 3 and p[0] == "repos":
        return f"github.com/{p[1]}/{p[2]}".lower(), f"https://api.github.com/repos/{p[1]}/{p[2]}", ""
    if host == "gitlab.com" and "/-/" in u.path:
        project = "/".join(urllib.parse.unquote(x) for x in u.path.split("/-/")[0].split("/") if x)
        return f"gitlab.com/{project}".lower(), f"https://gitlab.com/api/v4/projects/{urllib.parse.quote(project, safe='')}", ""
    return "", "", ""


def _ask_repository(key, api, raw):
    """(state, evidence) from one repository's route: `gone` when it answers 404, `answers` when it answers, "" when
    it could not be asked (no budget left, rate limited, a network error). A raw file's 404 may be the file or its ref,
    not the repository, so it is confirmed once by the API; a private repository answers 404 as a deleted one does."""
    if raw:
        r = request(raw, limit=1)
        if r["status"] == 200:
            return "answers", f"{raw} answers 200"
        if r["status"] != 404:
            return "", f"{raw}: {r['status'] or r['error']}"
    github = key.startswith("github.com/")
    if github:
        with _repo_guard:
            fresh = _gh_api["left"] is not None and time.time() - _gh_api.get("seen", 0.0) < 3600
            spent = _gh_api["asked"] >= GH_API_MAX or (fresh and _gh_api["left"] <= GH_API_RESERVE)
            _gh_api["asked"] += not spent
        if spent:
            return "", f"{key}: the run's GitHub REST requests are used up (60 an hour unauthenticated)"
    r = request(api, limit=1)
    left = r["headers"].get("x-ratelimit-remaining", "")
    if github and left.isdigit():
        _gh_api["left"], _gh_api["seen"] = int(left), time.time()
    if r["status"] == 404:
        return "gone", f"repository {api} answers 404"
    if r["status"] == 200:
        return "answers", f"{api} answers 200"
    if github and r["status"] in (403, 429) and left == "0":
        return "", f"{key}: GitHub's unauthenticated limit of 60 REST requests an hour is used up"
    return "", f"{api}: {r['status'] or r['error']}"


def repository_state(url):
    """(state, evidence) of the repository of a pinned url (`repository`), asked once per repository and run: `gone`
    when it answers 404, `answers`, or "" for a url with no route here or one that could not be asked. Safe to call
    from several threads."""
    key, api, raw = repository(url)
    if not key:
        return "", ""
    with _repo_guard:
        lock = _repo_locks.setdefault(key, threading.Lock())
    with lock:
        if key not in _repos:
            _repos[key] = _ask_repository(key, api, raw)
    return _repos[key]


# ---------------------------------------------------------------- the document text

def raw_url(url, row):
    """(url, extra headers) of the provider's raw form of `url`."""
    form = (row or {}).get("raw_form") or "-"
    kind, _, val = form.partition(":")
    base = url.split("#")[0]
    if kind == "query":
        return base + ("&" if "?" in base else "?") + val, {}
    if kind == "suffix":
        u = urllib.parse.urlsplit(base)
        path = u.path.rstrip("/")
        return urllib.parse.urlunsplit((u.scheme, u.netloc, path if path.endswith(val) else path + val, u.query, "")), {}
    if kind == "header":
        return base, {"Accept": val}
    if kind == "blob-to-raw":  # a GitHub or GitLab blob page -> the raw file at the same ref
        m = re.match(r"https://github\.com/([^/]+)/([^/]+)/blob/([^?]+)", base)
        if m:
            return f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2)}/{m.group(3)}", {}
        return base.replace("/-/blob/", "/-/raw/"), {}
    if kind == "arxiv-api":  # an arXiv abstract page -> its entry of the export API (an Atom feed)
        m = re.match(r"https?://(?:www\.)?arxiv\.org/abs/([^?]+?)/?(?:\?.*)?$", base)
        if m:
            return f"https://export.arxiv.org/api/query?id_list={m.group(1)}", {}
    return base, {}


FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def front_matter(text):
    """{key: value} of a Markdown document's YAML front matter (flat `key: value` lines only)."""
    m = FRONT.match(text)
    out = {}
    for ln in (m.group(1).splitlines() if m else []):
        k, sep, v = ln.partition(":")
        if sep and k and not k.startswith((" ", "-")):
            out[k.strip()] = v.strip().strip("'\"")
    return out


def version_of(text, keys):
    """{key: value} of the version keys found in a raw form's front matter or an HTML page's <meta> tags; `timeline` is
    the latest ISO timestamp anywhere in the text (an issue's events carry theirs in `datetime` attributes and in its
    embedded data)."""
    fm = front_matter(text)
    out = {}
    for k in keys:
        if k == TIMELINE:
            stamps = STAMP.findall(text)
            if stamps:
                out[k] = max(stamps)
            continue
        if fm.get(k):
            out[k] = fm[k]
            continue
        m = re.search(rf'<meta\s+(?:name|property)="{re.escape(k)}"\s+content="([^"]*)"', text)
        if m:
            out[k] = m.group(1)
    return out


MD_LINK = re.compile(r"!\[[^\]]*\]\([^)]*\)|\[([^\]]*)\]\([^)]*\)")


def doc_text(body, ctype, url=""):
    """The normalized document text of a response: Markdown keeps its headings and loses its front matter, link
    targets, images and HTML comments; HTML is reduced to its main text with `#` headings (fetch._PageText); other
    text (code, JSON, YAML) is kept with `\\n` line ends. None for binary content."""
    import fetch  # the reducer is shared with fetch.py --diff
    head = body[:1024]
    if b"\0" in head or re.search(r"zip|pdf|octet-stream|image/", ctype or ""):
        return None
    t = body.decode("utf-8", errors="replace").replace("\r\n", "\n")
    if "html" in (ctype or "") or head.lstrip()[:15].lower().startswith((b"<!doctype html", b"<html")):
        p = fetch._PageText(headings=True)
        p.feed(t)
        return p.text() + "\n"
    if "markdown" in (ctype or "") or url.split("?")[0].endswith((".md", ".mdx")) or FRONT.match(t):
        t = FRONT.sub("", t, count=1)
        t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
        t = MD_LINK.sub(lambda m: m.group(1) or "", t)
        t = "\n".join(ln.rstrip() for ln in t.splitlines())
        return re.sub(r"\n{3,}", "\n\n", t).strip() + "\n"
    if "json" in (ctype or "") or t.lstrip()[:1] in ("{", "["):
        try:  # one value per line, so a fact can be located in it
            return json.dumps(json.loads(t), indent=1, ensure_ascii=False) + "\n"
        except ValueError:
            pass
    if "<feed" in t[:600] and "http://www.w3.org/2005/Atom" in t[:600]:
        feed = atom_text(t)
        if feed is not None:
            return feed
    if ("xml" in (ctype or "") or t.lstrip().startswith("<?xml")) and len(t) > 500 * (t.count("\n") + 1):
        return re.sub(r">\s*<", ">\n<", t)
    return t


ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"


def atom_text(xml):
    """An Atom feed as lines, one block for each entry: `# title`, then `key: value` lines (id, authors, published,
    updated, categories and the arXiv extension keys) and the summary one sentence a line, so a passage can be
    located by line. None when the text is not a well-formed feed."""
    try:
        feed = ET.fromstring(xml)
    except ET.ParseError:
        return None
    blocks = []
    for e in feed.findall(ATOM + "entry"):
        def one(tag, ns=ATOM):
            node = e.find(ns + tag)
            return " ".join((node.text or "").split()) if node is not None else ""
        lines = ["# " + (one("title") or "(no title)")]
        keys = [("id", one("id")),
                ("authors", "; ".join(" ".join((a.findtext(ATOM + "name") or "").split()) for a in e.findall(ATOM + "author"))),
                ("published", one("published")), ("updated", one("updated")),
                ("categories", "; ".join(c.get("term", "") for c in e.findall(ATOM + "category"))),
                ("comment", one("comment", ARXIV)), ("journal_ref", one("journal_ref", ARXIV)), ("doi", one("doi", ARXIV))]
        lines += [f"{k}: {v}" for k, v in keys if v]
        summary = one("summary")
        if summary:
            lines += [""] + re.split(r"(?<=[.!?])\s+(?=[A-Z$\\(])", summary)
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n" if blocks else None


def document(url, row=None, etag="", lastmod=""):
    """Fetch a source's document by its provider's raw form, conditionally when a validator is given.
    {status, final, hops, not_modified, etag, lastmod, version (dict), text, sha, bytes, error, limited}; `limited`
    is True for a 403 or 429 that says the request limit is used up (x-ratelimit-remaining 0, or Retry-After)."""
    row = row if row is not None else for_url(url) or {}
    rurl, hdr = raw_url(url, row)
    sig = signals(row, url)
    if etag and "etag" in sig:
        hdr["If-None-Match"] = etag
    elif lastmod and "lastmod" in sig:
        hdr["If-Modified-Since"] = lastmod
    r = request(rurl, hdr)
    out = {"status": r["status"], "final": r["final"], "hops": r["hops"], "not_modified": r["status"] == 304,
           "etag": r["headers"].get("etag", ""), "lastmod": r["headers"].get("last-modified", ""), "version": {},
           "text": None, "sha": "", "bytes": len(r["body"]), "error": r["error"], "ctype": r["headers"].get("content-type", ""),
           "limited": r["status"] in (403, 429) and (r["headers"].get("x-ratelimit-remaining") == "0" or "retry-after" in r["headers"])}
    if r["status"] == 200 and r["body"]:
        raw = r["body"].decode("utf-8", errors="replace")
        out["raw"] = raw if doc_text(r["body"], out["ctype"], rurl) is not None else None
        out["raw_url"] = rurl
        keys = [k for k in (row.get("version_meta") or "").split(",") if k.strip() and k != "-"]
        out["version"] = version_of(raw, keys)
        out["text"] = doc_text(r["body"], out["ctype"], rurl)
        out["sha"] = hashlib.sha256((out["text"] or "").encode() if out["text"] is not None else r["body"]).hexdigest()
    return out


# ---------------------------------------------------------------- read: a page by its route, its matching lines

READ_CACHE = os.path.join(kbcommon.HOME, "_cache", "provider-read")  # beside _cache/factdiff, never committed
READ_AGE, READ_LINES, READ_WIDTH = 7, 60, 400  # days a fetch is reused; lines printed; characters of a line printed
NOT_TEXT = "not text: download it with curl into _cache/ and read it with the Read tool (pdf: by page range)"


def read_cache_path(url):
    return os.path.join(READ_CACHE, hashlib.sha256(url.split("#")[0].encode("utf-8")).hexdigest()[:24] + ".json")


def _read_text(d):
    """The text a read greps: a repository file (raw.githubusercontent.com, `/-/raw/`) exactly as it is, so a line
    number is the file's own (`#L12`); any other page as doc_text reduces it. None for a binary or a PDF."""
    raw = d.get("raw")
    if raw is None or raw.startswith("%PDF-"):
        return None
    ru = d.get("raw_url") or d["url"]
    if urllib.parse.urlsplit(ru).netloc.lower() == "raw.githubusercontent.com" or "/-/raw/" in ru:
        return raw.replace("\r\n", "\n")
    return doc_text(raw.encode("utf-8"), d.get("ctype", ""), ru)


def read(url, rows=None, refresh=False, now=None):
    """The document of `url` in its provider's raw form, from the read cache when a fetch of it is under READ_AGE days
    old (`refresh` fetches again): {status, error, url (without fragment), raw_url, raw_form, ctype, bytes, final,
    moved (the url a redirect ended at when it is not the raw url, else ""), fetched_utc, cached, text (None for a
    binary, a PDF or a page that did not answer 200)}. Only a 200 is kept in the cache."""
    base = url.split("#")[0]
    path = read_cache_path(base)
    now = now or datetime.datetime.now(datetime.timezone.utc)
    d = None
    if not refresh:
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            when = datetime.datetime.fromisoformat(d["fetched_utc"])
            d = d if (now - when).days < READ_AGE else None
        except (OSError, ValueError, KeyError):
            d = None
    if d is not None:
        d["cached"] = True
    else:
        row = for_url(base, rows) or {}
        got = document(base, row)
        raw_url_ = got.get("raw_url") or raw_url(base, row)[0]
        d = {k: got.get(k) for k in ("status", "error", "ctype", "bytes", "final", "raw")}
        d.update(url=base, raw_url=raw_url_, raw_form=row.get("raw_form") or "-", fetched_utc=now.isoformat(), cached=False,
                 moved=got["final"] if got["hops"] and got["final"].split("?")[0].rstrip("/") != raw_url_.split("?")[0].rstrip("/") else "")
        if d["status"] == 200:
            os.makedirs(READ_CACHE, exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                json.dump({k: v for k, v in d.items() if k != "cached"}, f)
    d["text"] = _read_text(d) if d["status"] == 200 else None
    return d


def grep_lines(text, words, context=0, start=1, limit=READ_LINES):
    """(blocks, total, shown): the lines of `text` that hold every word of `words` (case-insensitive; all lines from
    line `start` when `words` is empty), each with `context` lines either side, as groups of (number, line, matched);
    at most `limit` matching lines are shown of `total`."""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    low = [w.lower() for w in words]
    hit = [i for i, ln in enumerate(lines) if i + 1 >= start and all(w in ln.lower() for w in low)]
    shown = hit[:limit]
    groups, near = [], set(shown)
    for i in shown:
        lo, hi = max(0, i - context), min(len(lines) - 1, i + context)
        if groups and lo <= groups[-1][-1] + 1:
            groups[-1].extend(range(groups[-1][-1] + 1, hi + 1))
        else:
            groups.append(list(range(lo, hi + 1)))
    return [[(i + 1, lines[i], i in near) for i in g] for g in groups], len(hit), len(shown)


def excerpt(line, words, width=READ_WIDTH):
    """`line`, cut to a window of `width` characters around its first word when it is longer."""
    if len(line) <= width:
        return line
    at = min((line.lower().find(w.lower()) for w in words if w.lower() in line.lower()), default=0)
    lo = max(0, min(at - width // 4, len(line) - width))
    return ("... " if lo else "") + line[lo:lo + width] + (" ..." if lo + width < len(line) else "")


def cmd_read(a, rows):
    """Print the page of a.url by its provider's raw form (exit 1 when it is not read as text or no line holds every
    word of a.grep, 0 otherwise)."""
    d = read(a.url, rows, refresh=a.refresh)
    print(f"cite: {d['url']}")
    got = f"{d['status'] or d['error']}" + (f", {d['ctype']}" if d.get("ctype") else "") + f", {d['bytes'] or 0} bytes"
    print(f"read: {d['raw_url']} ({got}; " + ("cache of " if d["cached"] else "fetched ") + f"{d['fetched_utc'][:10]})")
    if d["moved"]:
        print(f"moved: {d['moved']}")
    if d["status"] != 200:
        print(f"not read: {d['status'] or d['error']}")
        return 1
    if d["text"] is None:
        print(NOT_TEXT)
        return 1
    text, words = d["text"], (a.grep or "").split()
    nlines = len(text.split("\n")) - text.endswith("\n")
    groups, total, shown = grep_lines(text, words, a.context, a.start, a.limit)
    if words and not total:
        each = [(w, sum(w.lower() in ln.lower() for ln in text.split("\n"))) for w in words]
        print(f"no line holds every word of {' '.join(words)!r}; lines holding each: " + ", ".join(f"{w} {n}" for w, n in each))
        return 1
    print(f"lines: {total} of {nlines} " + (f"hold every word of {' '.join(words)!r}" if words else f"from line {a.start}"))
    for i, g in enumerate(groups):
        if i:
            print("--")
        for n, ln, matched in g:
            print(f"{n}{':' if matched else '-'}{excerpt(ln, words)}")
    if shown < total:
        print(f"{total - shown} more: raise --max" + (" or add words to --grep" if words else f", or --from {groups[-1][-1][0] + 1}"))
    return 0


# ---------------------------------------------------------------- probe

def _sample(name, rows, root):
    row = next((r for r in rows if r["provider"] == name), None)
    for s in kbcommon.load_csv(os.path.join(root.path, kbcommon.SOURCES), ("id", "url"))[1]:
        if for_url(s["url"], rows) is row and not (s.get("superseded_by") or "").strip():
            return s["url"]
    return None


def _sibling(url):
    u = urllib.parse.urlsplit(url.split("#")[0].split("?")[0])
    parent = u.path.rstrip("/").rsplit("/", 1)[0]
    rng = random.Random(url)  # the same made-up path for the same url: a probe is repeatable
    junk = "".join(rng.choice(string.ascii_lowercase + string.digits) for _ in range(25))
    if u.path.rstrip("/").rsplit("/", 1)[-1].isdigit():  # a numbered page (an issue): a made-up word is a search, a number is a miss
        junk = "".join(rng.choice(string.digits) for _ in range(12))
    return urllib.parse.urlunsplit((u.scheme, u.netloc, f"{parent}/{junk}", "", ""))


def _git_answers(url):
    """Whether `git ls-remote` of a repository url answers (no prompt for credentials)."""
    try:
        p = subprocess.run(["git", "ls-remote", "--exit-code", url, "HEAD"], capture_output=True, text=True, encoding="utf-8",
                           timeout=60, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    except (subprocess.TimeoutExpired, OSError):
        return False
    return p.returncode == 0


def probe(row, url):
    """The measured columns of a provider row from live requests on `url` (dict), plus `evidence` lines."""
    ev, found = [], {}
    a = request(url)
    ev.append(f"GET {url}: {a['status'] or a['error']}" + (f" -> {a['final']}" if a["final"] != url else ""))
    if a["status"] != 200:
        return None, ev
    b = request(url)
    tag_b = b["headers"].get("etag", "")
    lm = a["headers"].get("last-modified", "")
    raw_forms = []
    forms = ["query:accept=text/markdown", "suffix:.md", "header:text/markdown"]
    forms += [row["raw_form"]] if row.get("raw_form") not in forms + ["-", "", None] else []
    for form in forms:
        ru, hdr = raw_url(url, {"raw_form": form})
        if ru == url.split("#")[0] and not hdr:  # the url is already in this form (a `.md` source)
            if "markdown" in a["headers"].get("content-type", ""):
                raw_forms.append((form, a))
            continue
        r = request(ru, hdr)
        ct = r["headers"].get("content-type", "")
        ok = r["status"] == 200 and len(r["body"]) > 200 and ("markdown" in ct or (form in ("blob-to-raw", "arxiv-api") and "html" not in ct))
        ev.append(f"raw form {form}: {r['status'] or r['error']} {r['headers'].get('content-type', '')}")
        if ok:
            raw_forms.append((form, r))
    ctype = a["headers"].get("content-type", "")
    curated = [f for f in raw_forms if f[0] == row.get("raw_form")]  # the documented form wins when it works
    if curated or raw_forms:
        form, rr = (curated or raw_forms)[0]
    elif row.get("raw_form") in ("blob-to-raw", "arxiv-api") or "html" not in ctype:
        form, rr = (row.get("raw_form") or "-", a) if "html" not in ctype else ("-", a)
    else:
        form, rr = "-", a
    found["raw_form"] = form
    # validators on the form that will be fetched
    t1 = rr["headers"].get("etag", "")
    t2 = request(raw_url(url, {"raw_form": form})[0], raw_url(url, {"raw_form": form})[1])["headers"].get("etag", "") if form != "-" else tag_b
    if not t1:
        found["etag"] = "none"
    elif t1 != t2:
        found["etag"] = "per-request"
    else:
        found["etag"] = "weak" if t1.startswith("W/") else "stable"
    etag_ok = False
    if found["etag"] in ("stable", "weak"):
        ru, hdr = raw_url(url, {"raw_form": form})
        c = request(ru, {**hdr, "If-None-Match": t1})
        etag_ok = c["status"] == 304
        ev.append(f"If-None-Match {t1[:40]}: {c['status']}")
    lm = rr["headers"].get("last-modified", "") or lm
    lm_ok = False
    if lm:
        when = email.utils.parsedate_to_datetime(lm)
        age = abs((datetime.datetime.now(datetime.timezone.utc) - when).total_seconds())
        if age < 120:
            found["lastmod"] = "request-time"
        else:
            ru, hdr = raw_url(url, {"raw_form": form})
            c = request(ru, {**hdr, "If-Modified-Since": lm})
            lm_ok = c["status"] == 304
            found["lastmod"] = "stable" if lm_ok else "stable-no-304"
            ev.append(f"If-Modified-Since {lm}: {c['status']}")
    else:
        found["lastmod"] = "none"
    raw = rr["body"].decode("utf-8", "replace")
    named = [TIMELINE] if TIMELINE in (row.get("version_meta") or "").split(",") else []  # a page-wide scan: only where curated
    keys = version_of(raw, VERSION_KEYS + tuple(named))
    order = [k for k in ("git_commit_id", "updated_at", "document_id", "dateModified", "article:modified_time", "ms.date",
                         "last-modified", "revised", TIMELINE) if k in keys]
    found["version_meta"] = ",".join(order) or "-"
    ev.append("version keys: " + (", ".join(f"{k}={keys[k][:24]}" for k in order) or "none"))
    # robots.txt sitemap
    u = urllib.parse.urlsplit(url)
    rb = request(f"{u.scheme}://{u.netloc}/robots.txt")
    sm = re.findall(r"(?im)^sitemap:\s*(\S+)", rb["body"].decode("utf-8", "replace")) if rb["status"] == 200 else []
    found["sitemap"] = sm[0] if sm else "-"
    ev.append(f"robots.txt: {rb['status']}, sitemap {found['sitemap']}")
    # soft 404
    sib = request(_sibling(url))
    found["not_found"] = ("hard-404" if sib["status"] in (404, 410) else "soft-404" if sib["status"] == 200 else
                          f"status-{sib['status']}" if sib["status"] else "unknown")
    ev.append(f"sibling {_sibling(url)}: {sib['status'] or sib['error']}")
    # search api
    tpl = (row.get("search_api") or "-").strip()
    if tpl != "-" and "{q}" in tpl:
        title = re.search(r"(?im)^title:\s*(.+)$|<title>([^<]+)</title>", raw)
        q = ((title.group(1) or title.group(2)) if title else "overview").split("|")[0].split(" - ")[0].strip()
        s = request(tpl.replace("{q}", urllib.parse.quote(q)))
        ok = s["status"] == 200 and (s["body"][:1] in (b"{", b"[") or s["body"][:5] == b"<?xml")
        ev.append(f"search_api {q!r}: {s['status']}" + (", lastUpdatedDate present" if b"lastUpdatedDate" in s["body"] else ""))
        if not ok:
            found["notes_search"] = f"search_api answered {s['status']}"
    pin = is_pinned(url) or "pin" in (row.get("signals") or "").split(";")  # pin is a url pattern, kept from the row
    git_ok = False
    if "git" in (row.get("signals") or "").split(";"):  # kept only where the page's repository answers
        kind, repo, _ = github_page(url)
        git_ok = bool(repo) and _git_answers(f"https://{repo}")
        ev.append(f"git ls-remote https://{repo or '-'}: {'answers' if git_ok else 'no answer'} ({kind or 'not a github page'})")
    sig = (["pin"] if pin else []) + (["etag"] if etag_ok else []) + (["lastmod"] if lm_ok else []) \
        + (["version"] if order and order[0] in ("git_commit_id", "updated_at", "dateModified", "article:modified_time", TIMELINE) else []) \
        + (["git"] if git_ok else []) + ["hash"]
    found["signals"] = ";".join(sig)
    found["probed_utc"] = datetime.date.today().isoformat()
    return found, ev


def write_row(path, row):
    rows = _read(path) if os.path.exists(path) else []
    rows = [row if r["provider"] == row["provider"] else r for r in rows]
    if not any(r["provider"] == row["provider"] for r in rows):
        rows.append(row)
    kbcommon.write_csv(path, COLS, rows, atomic=True)


def main():
    global DELAY
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default="public", help="the root whose providers and sources are used (default public)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="the merged registry")
    s = sub.add_parser("show", help="the provider serving a url")
    s.add_argument("url")
    p = sub.add_parser("probe", help="measure a provider's signals with live requests")
    p.add_argument("name")
    p.add_argument("--url", help="sample url (default: the root's first source the provider serves)")
    p.add_argument("--write", action="store_true", help="store the measured columns and probed_utc in the row's file")
    p.add_argument("--json", action="store_true")
    p.add_argument("--delay", type=float, default=DELAY, help="seconds between requests to one host (default 1.1)")
    r = sub.add_parser("read", help="read a page by its provider's raw form and print the lines that hold every word")
    r.add_argument("url")
    r.add_argument("--grep", metavar="WORDS", help="print only the lines that hold every one of these words (any case)")
    r.add_argument("--context", type=int, default=0, metavar="N", help="lines of context either side of a match (default 0)")
    r.add_argument("--max", type=int, default=READ_LINES, metavar="N", dest="limit", help=f"lines printed (default {READ_LINES})")
    r.add_argument("--from", type=int, default=1, metavar="LINE", dest="start", help="first line considered (default 1)")
    r.add_argument("--refresh", action="store_true", help=f"fetch again although the cache holds the page ({READ_AGE} days)")
    a = ap.parse_args()
    if a.cmd == "read" and (a.context < 0 or a.limit < 1 or a.start < 1):
        ap.error("--context must be 0 or more, --max and --from 1 or more")
    try:
        root = kbcommon.root(a.root)
    except (KeyError, kbcommon.RootError) as e:
        ap.error(f"--root {a.root}: no such root ({e})")
    rows = providers(root)
    if a.cmd == "list":
        for r in rows:
            print(f"{r['provider']:<12} {r['match']:<40} signals={r.get('signals', '')} not_found={r.get('not_found', '')} "
                  f"probed={r.get('probed_utc') or 'never'}" + (f" (root {r['_root']})" if r.get("_root") else ""))
        return 0
    if a.cmd == "read":
        return cmd_read(a, rows)
    if a.cmd == "show":
        r = for_url(a.url, rows)
        if not r:
            print("no provider (and no `*` row)")
            return 1
        ru, hdr = raw_url(a.url, r)
        print(json.dumps({k: v for k, v in r.items() if not k.startswith("_")}, indent=1))
        print(f"fetch: {ru}" + (f" with {hdr}" if hdr else "") + f"; signals: {', '.join(signals(r, a.url))}")
        return 0
    DELAY = max(a.delay, 0)
    row = next((r for r in rows if r["provider"] == a.name), None)
    if not row:
        ap.error(f"no provider {a.name!r}; `provider.py list` shows them")
    url = a.url or _sample(a.name, rows, root)
    if not url:
        ap.error(f"no source of root {root.name} is served by {a.name}: give --url")
    found, ev = probe(row, url)
    if a.json:
        print(json.dumps({"provider": a.name, "url": url, "found": found, "evidence": ev}, indent=1))
    else:
        print("\n".join(ev))
    if found is None:
        print(f"probe failed: the sample {url} did not answer 200")
        return 1
    new = {c: row.get(c, "") for c in COLS}
    note = found.pop("notes_search", "")
    if row.get("match", "").split() == ["*"]:  # the fallback serves many hosts: one sample host must not set its columns
        host = urllib.parse.urlsplit(url).netloc
        note = f"last sample {host}: etag {found['etag']}, lastmod {found['lastmod']}, not_found {found['not_found']}"
        new["notes"] = re.sub(r";? ?last sample [^;]*", "", new["notes"]).strip("; ")
        found = {"probed_utc": found["probed_utc"]}
    new.update({k: v for k, v in found.items() if k in MEASURED})
    if note and note not in new["notes"]:
        new["notes"] = (new["notes"] + "; " if new["notes"] else "") + note
    if not a.json:
        for c in MEASURED:
            if row.get(c, "") != new[c]:
                print(f"  {c}: {row.get(c, '') or '-'} -> {new[c]}")
    if a.write:
        path = os.path.join(root.path, ROOT_FILE) if row.get("_root") else SHARED
        write_row(path, new)
        print(f"wrote {a.name} to {os.path.relpath(path, kbcommon.HOME)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
