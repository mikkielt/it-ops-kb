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
  provider.py [--root NAME] search NAME TERMS... [--max N] [--refresh]
                                                          the hits (date, title, url) of the search_api of provider NAME

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
  search_api      a search url template with {q}, or `-`; `search` knows the response of each in SEARCH_SHAPES (Learn's
                  api/search, the arXiv export API, GitHub's repository search on `github` and code search on
                  `github-blob`, PyPI's JSON of a project name)
  mcp_freshness   what the provider's MCP server says about a page's version
  not_found       hard-404 (a made-up sibling url answers 404/410) | soft-404 (it answers 200) | status-<code>
                  (another code, e.g. 403) | unknown
  rate_limit      the documented or observed request limit
  reuse           the usual reuse class of the provider's pages (kbcommon.REUSE; the source row decides)
  lifetime_days   days a source of the provider counts as fresh when neither its recorded changes nor its page date give
                  a lifetime (lifetime); curated, never measured by probe; a row without it takes the `*` row's, else
                  DEFAULT_LIFETIME_DAYS
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

search asks the row's search_api once (the terms joined as the API reads them: spaces, `all:` terms for arXiv, `-` for
a PyPI project name; no credential is read and no Authorization header is sent, so GitHub's code search answers 401),
keeps a 200 for SEARCH_AGE days under _cache/provider-search/ (--refresh asks again) and prints `search:` (the request
and the day of its answer), then `N. DATE  TITLE` and the url of each of the first --max hits (default 5). Exit: 0 hits
printed, 1 the API did not answer 200 or holds no hit, 2 a provider with no search_api.

read_licence(url) (kbid.py add) reads the licence and reuse class from the source's own record: an arXiv abstract
page's licence link, a GitHub or GitLab repository's licence through the forge's API, a Learn page's public mirror
(the page's github_feedback_content_git_url; archived, private or with conflicting licence files it is `quote`) and
the fixed pair of code.claude.com and anthropic.com. It returns `copy` only for an open licence (an SPDX id that is
no NC, ND or source-available one, CC BY, CC BY-SA, CC0) and leaves licence and reuse empty, with a `note`, for any
other host or a record it cannot use; a GitHub request is unauthenticated (60 an hour; a Learn page asks two).

Library use (factdiff.py, census.py): providers(), for_url(), document(), doc_text(), repository_state(), and for a
lookup that must answer in time (factdiff.revalidate): budget() bounds every request of a block to a total, pacing()
is the seconds a row's rate limit asks between two requests and new_run() forgets the answers of an earlier run;
host_seen() and host_down() keep, in the process and under _cache/provider-down/, a host that did not accept a
connection for a window that doubles with each failure in a row (DOWN_BASE_S up to DOWN_CAP_S), so a lookup asks it no
more until the window is over: under down_window(), gated_request() (the requests of a source's page, a search, a
candidate page, a made-up sibling and a pinned url's repository) reads and records it for the host each request went to.
lifetimes() gives each source a freshness lifetime with no request (the section "freshness lifetime"): the factdiff
revalidation at question time and fetch.py --status read it.
"""
import argparse, calendar, collections, contextlib, csv, datetime, email.utils, hashlib, io, json, math, os, random, re, ssl, string, subprocess, sys, threading, time
import urllib.error, urllib.parse, urllib.request, zlib
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kbcommon  # noqa: E402

SHARED = os.path.join(kbcommon.TOOLS, "providers.csv")
ROOT_FILE = "_providers.csv"
COLS = ["provider", "match", "signals", "etag", "lastmod", "version_meta", "stable_id", "raw_form", "sitemap",
        "sitemap_lastmod", "redirects", "history", "search_api", "mcp_freshness", "not_found", "rate_limit", "reuse",
        "lifetime_days", "probed_utc", "notes"]
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


# ---------------------------------------------------------------- freshness lifetime

FRACTION = 0.1  # RFC 9111 4.2.2: a heuristic lifetime is a fraction of the time since the last change, "typically 10%"
DEFAULT_LIFETIME_DAYS = 30  # a provider row that holds no `lifetime_days`, with no `*` row to give one
WINDOW_DAYS = 365  # the span of a docs file's commits read for its change rate
DAY = 86400.0
CONFIRMED = re.compile(r"confirmed (\d{4}-\d\d-\d\d)")  # the census's suffix of a source row's version_or_date
PAGE_DATE = re.compile(r"(?:updated_at|updated|lastmod|modified) (\d{4}-\d\d-\d\d)")  # a page's own date there
LEARN_FILES = (".md", "/index.md", ".yml", "/index.yml")  # the files a Learn page can be built from (census.check_learn)
LEARN_MEMO_S = 3600  # a long-lived server asks git about a page's file once an hour
_learn_memo = {}  # url -> (time, [commit epochs])


def stamp_epoch(stamp):
    """Seconds since the epoch of a `YYYY-MM-DDTHH:MM:SSZ` or `YYYY-MM-DD` stamp (UTC); None when it is neither."""
    m = re.match(r"(\d{4})-(\d\d)-(\d\d)(?:T(\d\d):(\d\d):(\d\d))?", stamp or "")
    if not m:
        return None
    try:
        return float(calendar.timegm(tuple(int(x or 0) for x in m.groups())))
    except (ValueError, OverflowError):
        return None


def _git(cwd, *args):
    """stdout of `git -C cwd ARGS`, "" when git fails. Never a request: an object a partial clone lacks is not fetched."""
    try:
        p = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=120, env={**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0"})
    except (OSError, subprocess.SubprocessError):
        return ""
    return p.stdout if p.returncode == 0 else ""


def state_history(root, home=None):
    """{source id: {checks: [epoch], changes: [epoch]}} from the git history of the root's `_fetch_state.csv`, with no
    request: every `fetched_utc`, `detected_utc` and `changed_utc` a committed revision held is a successful check of
    that source, every `changed_utc` a change it saw (the file keeps only the latest of each, so the history is the
    only record of the earlier ones). {} outside a git repository. The result is kept under _cache/lifetime/ and
    extended by the revisions committed since, as long as the ones it read are still the file's oldest."""
    home = home or kbcommon.HOME
    rel = os.path.relpath(os.path.join(root.path, kbcommon.STATE), home).replace(os.sep, "/")
    revs = _git(home, "log", "--format=%H", "--", rel).split()[::-1]  # oldest first
    if not revs:
        return {}
    cache = os.path.join(home, "_cache", "lifetime", f"history-{root.name}.json")
    data, done = {}, []
    try:
        with open(cache, encoding="utf-8") as f:
            got = json.load(f)
        if got["rel"] == rel and revs[:len(got["revs"])] == got["revs"]:
            data, done = got["data"], got["revs"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    if len(revs) > len(done):
        sets = {sid: {k: set(v) for k, v in rec.items()} for sid, rec in data.items()}
        for rev in revs[len(done):]:
            try:
                rows = kbcommon.parse_csv(rel, _git(home, "show", f"{rev}:{rel}"), ("id",))[1]
            except kbcommon.CsvError:
                continue
            for r in rows:
                rec = sets.setdefault(r["id"], {"checks": set(), "changes": set()})
                for col in ("fetched_utc", "detected_utc", "changed_utc"):
                    t = stamp_epoch(r.get(col))
                    if t is not None:
                        rec["checks"].add(t)
                        if col == "changed_utc":
                            rec["changes"].add(t)
        data = {sid: {k: sorted(v) for k, v in rec.items()} for sid, rec in sets.items()}
        try:
            os.makedirs(os.path.dirname(cache), exist_ok=True)
            with open(cache + ".tmp", "w", encoding="utf-8", newline="\n") as f:
                json.dump({"rel": rel, "revs": revs, "data": data}, f)
            os.replace(cache + ".tmp", cache)
        except OSError:
            pass
    return data


def modified_interval(checks, changes):
    """Mean days between the changes of one source by Cho and Garcia-Molina's modified estimator, from the times of its
    successful checks (the first only sets the baseline) and of the changes they saw: with n check intervals of mean
    length I and X changes seen, I / -ln((n - X + 0.5) / (n + 0.5)). The 0.5 terms keep it finite when every check saw
    a change, where the plain rate is infinite, and it corrects the bias of counting at most one change per check.
    None under two changes seen (or two checks): the change rate is then not known."""
    checks = sorted(set(checks))
    seen = len({c for c in changes if checks and c > checks[0]})
    if len(checks) < 2 or seen < 2:
        return None
    n = len(checks) - 1
    return (checks[-1] - checks[0]) / n / -math.log((n - min(seen, n) + 0.5) / (n + 0.5)) / DAY


def clone_dir(repo):
    """The bare clone of a docs repository in the census's cache (this checkout's, else the clone's main worktree's)."""
    import census, kbfacts  # not at load: the census brings the detection tools a lookup with no Learn source never needs
    name = census.clone_name(repo) + ".git"
    for base in (census.REPOS, os.path.join(kbfacts.clone_home(), "_cache", "census", "repos")):
        if os.path.isdir(os.path.join(base, name)):
            return os.path.join(base, name)
    return None


def learn_commits(urls, now=None, days=WINDOW_DAYS):
    """{url: [commit epoch]} of the Learn pages among `urls` whose source file (census.learn_source) has commits in the
    last `days`, read from the census's clone cache with one git walk per repository and no request; a page that maps to
    no repository, or whose repository is not in the cache, is left out."""
    now = now or time.time()
    out, want = {}, []
    for u in urls:
        memo = _learn_memo.get(u)
        if memo and now - memo[0] < LEARN_MEMO_S:
            out[u] = memo[1]
        elif urllib.parse.urlsplit(u).netloc.lower() == "learn.microsoft.com":
            want.append(u)
    if not want:
        return out
    import census
    by_repo = collections.defaultdict(dict)
    for u in want:
        repo, path = census.learn_source(u)
        for suffix in LEARN_FILES if repo else ():
            by_repo[repo][path + suffix] = u
    since = datetime.datetime.fromtimestamp(now - days * DAY, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for repo, files in by_repo.items():
        d = clone_dir(repo)
        if d is None:
            continue
        times, paths, t = collections.defaultdict(set), sorted(files), None
        for i in range(0, len(paths), 1000):
            for ln in _git(d, "log", f"--since={since}", "--format=%ct", "--name-only", "HEAD", "--", *paths[i:i + 1000]).splitlines():
                if re.fullmatch(r"\d{9,11}", ln.strip()):
                    t = float(ln)
                elif ln in files and t is not None:
                    times[files[ln]].add(t)
        for u in set(files.values()):
            out[u] = sorted(times[u])
            _learn_memo[u] = (now, out[u])
    return out


def page_date(st, src, row):
    """Epoch of a source's own content date from files only: the newest `updated_at`, `updated`, `lastmod` or `modified`
    date of its version_or_date, else the state row's Last-Modified when its provider's header is a stable one."""
    days = [stamp_epoch(d) for d in PAGE_DATE.findall((src or {}).get("version_or_date") or "")]
    if any(d is not None for d in days):
        return max(d for d in days if d is not None)
    if ((row or {}).get("lastmod") or "").startswith("stable") and (st or {}).get("last_modified"):
        try:
            return email.utils.parsedate_to_datetime(st["last_modified"]).timestamp()
        except (TypeError, ValueError):
            pass
    return None


def default_days(row, rows):
    """(days, provider name) a provider row's `lifetime_days` gives, else the `*` row's, else DEFAULT_LIFETIME_DAYS."""
    star = next((r for r in rows or () if (r.get("match") or "").split() == ["*"]), None)
    for r in (row, star):
        try:
            if r and float(r.get("lifetime_days") or 0) > 0:
                return float(r["lifetime_days"]), r.get("provider", "")
        except ValueError:
            pass
    return float(DEFAULT_LIFETIME_DAYS), ""


def lifetime(sid, src, st, hist, commits, row, rows, now):
    """{days, basis, changes} of one source: how long its facts count as fresh after a check, with no request. `days` is
    FRACTION of the mean time between its changes, estimated from the first evidence there is: its recorded changes in
    the git history of the state file when it has two or more (modified_interval); else its Learn file's commits in the
    last WINDOW_DAYS when it has two or more; else the time since its page date (RFC 9111's heuristic); else its
    provider's `lifetime_days`. None for a pinned url: its text cannot change."""
    url = (src.get("url") or "").strip()
    if is_pinned(url) or "pin" in signals(row or {}, url):
        return {"days": None, "basis": "pinned: its text cannot change", "changes": 0}
    h = hist.get(sid) or {"checks": [], "changes": []}
    mean = modified_interval(h["checks"], h["changes"])
    if mean:
        seen = len({c for c in h["changes"] if c > min(h["checks"])})
        return {"days": FRACTION * mean, "changes": seen,
                "basis": f"{seen} changes in {len(set(h['checks'])) - 1} checks, one every {mean:.0f} days (Poisson)"}
    got = commits.get(url) or []
    if len(got) >= 2:
        return {"days": FRACTION * WINDOW_DAYS / len(got), "changes": len(got),
                "basis": f"{len(got)} commits of its file in {WINDOW_DAYS} days"}
    d = page_date(st, src, row)
    if d is not None and d < now:
        age = (now - d) / DAY
        return {"days": FRACTION * age, "changes": 0, "basis": f"{FRACTION:.0%} of the {age:.0f} days since its page date"}
    days, name = default_days(row, rows)
    return {"days": days, "changes": 0, "basis": f"provider default ({name or 'built in'})"}


def lifetimes(sources, state, rows, root, now=None, home=None):
    """{source id: lifetime()} for `sources` {id: _sources.csv row}, `state` {id: _fetch_state.csv row}, `rows` the
    provider registry and `root` the kbcommon.Root they belong to, with no request: the state file's git history, the
    census's clone cache and the files' own dates."""
    now = time.time() if now is None else now
    hist = state_history(root, home)
    rowof = {sid: for_url((s.get("url") or "").strip(), rows) for sid, s in sources.items()}
    need = [s["url"].strip() for sid, s in sources.items() if not is_pinned(s.get("url") or "")
            and modified_interval((hist.get(sid) or {}).get("checks", []), (hist.get(sid) or {}).get("changes", [])) is None]
    commits = learn_commits(need, now) if need else {}
    return {sid: lifetime(sid, s, state.get(sid) or {}, hist, commits, rowof[sid], rows, now) for sid, s in sources.items()}


def last_check(st, src):
    """Epoch of the last check of a source known from files with no request: the newest of the state row's checked_utc,
    fetched_utc and detected_utc and the census's `confirmed DAY` of its version_or_date; None when none dates it."""
    days = [stamp_epoch((st or {}).get(c)) for c in ("checked_utc", "fetched_utc", "detected_utc")]
    days += [stamp_epoch(d) for d in CONFIRMED.findall((src or {}).get("version_or_date") or "")]
    return max((d for d in days if d is not None), default=None)


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


# ---------------------------------------------------------------- hosts that did not accept a connection

DOWN_BASE_S, DOWN_CAP_S = 60, 300  # first window; doubled with each failure in a row, up to the cap
DOWN_PREFIX = "host did not accept a connection"
DOWN_DIR = os.path.join(kbcommon.HOME, "_cache", "provider-down")  # beside the read and search caches, never committed
_down = {}  # host -> {until, at, count, error}: this process's copy of the files under DOWN_DIR


def _down_path(host):
    return os.path.join(DOWN_DIR, re.sub(r"[^\w.-]", "_", host) + ".json")


def _down_end(rec, now):
    """`rec` with its end cut to DOWN_CAP_S after its `at` and after `now`: no window runs longer than the cap, so a
    record that says otherwise (a corrupt or hand-edited one) still holds the host for at most the cap."""
    until = min(rec["until"], rec["at"] + DOWN_CAP_S, now + DOWN_CAP_S)
    return rec if until == rec["until"] else dict(rec, until=until)


def _down_rec(host, now=None):
    """The record of `host` with the later end, the process's or the file's (another process may have extended it), or
    None; an end past the cap is read as the cap's (_down_end)."""
    now = time.time() if now is None else now
    best = _down.get(host)
    if best is not None:
        best = _down_end(best, now)
    try:
        with open(_down_path(host), encoding="utf-8") as f:
            rec = json.load(f)
    except (OSError, ValueError):
        return best
    ok = isinstance(rec, dict) and all(isinstance(rec.get(k), (int, float)) for k in ("until", "at", "count"))
    if ok:
        rec = _down_end(rec, now)
    return rec if ok and (best is None or rec["until"] > best["until"]) else best


def host_down(url, now=None):
    """The record {until, at, count, error} of the host of `url` while its window runs (it did not accept a connection
    at `at`, and is not asked until `until`), else None."""
    now = time.time() if now is None else now
    rec = _down_rec(urllib.parse.urlsplit(url).netloc.lower(), now)
    return rec if rec and rec["at"] <= now < rec["until"] else None


def down_why(rec, now=None):
    """The reason a source of a host in its window is not asked: how long ago the host failed and for how long more it is
    left alone."""
    now = time.time() if now is None else now
    return (f"{DOWN_PREFIX} {max(0, round(now - rec['at']))} s ago ({rec.get('error', '')}); "
            f"not asked again for {max(0, round(rec['until'] - now))} s")


def host_seen(url, error, now=None):
    """Record what a request to the host of `url` showed: `error` is the answer's `error` ("" for an HTTP answer of any
    status). A connection that was not made (a URLError: refused, a name that did not resolve, a timeout of the
    connect) starts the host's window, doubled when the host failed again after the earlier window ended; the time
    budget used up shows nothing; anything else (the host answered, or accepted the connection) ends the window. A record
    that cannot be written is kept in the process only."""
    if error == BUDGET_ERROR:
        return
    host, now = urllib.parse.urlsplit(url).netloc.lower(), time.time() if now is None else now
    if not error.startswith("URLError:"):
        _down.pop(host, None)
        try:
            os.remove(_down_path(host))
        except OSError:
            pass
        return
    old = _down_rec(host, now)
    if old is not None and old["at"] <= now < old["until"]:  # no request was made within the window: no new failure
        return
    count = old["count"] + 1 if old is not None and now - old["until"] < DOWN_CAP_S else 1  # a long quiet time starts over
    rec = _down[host] = {"at": now, "until": now + min(DOWN_CAP_S, DOWN_BASE_S * 2 ** (count - 1)), "count": count,
                         "error": error[:120]}
    try:
        os.makedirs(DOWN_DIR, exist_ok=True)
        tmp = f"{_down_path(host)}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(rec, f)
        os.replace(tmp, _down_path(host))
    except OSError:
        pass


_down_gate = [False]  # whether gated_request reads and records the windows: set by down_window() (a lookup)


@contextlib.contextmanager
def down_window():
    """Under the block, gated_request leaves a host in its window alone and records what each of its answers shows of
    the hosts the request went through. For a lookup (factdiff.revalidate); a detection run or a census asks every host."""
    _down_gate[0] = True
    try:
        yield
    finally:
        _down_gate[0] = False


def gated_request(url, *args, **kwargs):
    """request() for a source's page, a search, a candidate page, a made-up sibling and a repository: under down_window()
    a host in its window gets no request (status 0, the reason of down_why as `error`, counted in failures()), and the
    answer of any other request is recorded with host_seen for every host it went through: the hosts a redirect was
    followed through answered, and a connection that was not made is the window of the host it was made to, the last
    hop's, not of the url that was asked. Outside the block it is request()."""
    if not _down_gate[0]:
        return request(url, *args, **kwargs)
    rec = host_down(url)
    if rec:
        _failed[0] += 1
        return {"status": 0, "headers": {}, "body": b"", "final": url, "hops": [], "error": down_why(rec)}
    r = request(url, *args, **kwargs)
    chain = [url] + [hop[1] for hop in r.get("hops") or []]
    for hop in chain[:-1]:
        host_seen(hop, "")
    host_seen(chain[-1], r.get("error") or "")
    return r


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
        r = gated_request(raw, limit=1)
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
    r = gated_request(api, limit=1)
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
    text (code, JSON, YAML) is kept with `\\n` line ends. None for binary content. A `str` body is taken as UTF-8."""
    import fetch  # the reducer is shared with fetch.py --diff
    if isinstance(body, str):
        body = body.encode("utf-8")
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
    r = gated_request(rurl, hdr)
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


# ---------------------------------------------------------------- search: a provider's own search API

SEARCH_CACHE = os.path.join(kbcommon.HOME, "_cache", "provider-search")  # beside the read cache, never committed
SEARCH_AGE, SEARCH_MAX = 7, 5  # days an answer is reused; hits printed (the API's first page holds at most 10)


def _day(stamp):
    return (stamp or "")[:10] or "-"


def _hits_learn(body):
    return [{"title": x.get("title", ""), "url": x.get("url", ""), "date": _day(x.get("lastUpdatedDate"))}
            for x in json.loads(body).get("results", []) if x.get("url")]


def _hits_arxiv(body):
    feed = ET.fromstring(body)
    out = []
    for e in feed.findall(ATOM + "entry"):
        one = lambda tag: " ".join((e.findtext(ATOM + tag) or "").split())  # noqa: E731
        link = one("id").replace("http://arxiv.org/", "https://arxiv.org/")
        if link:
            out.append({"title": one("title"), "url": link, "date": _day(one("updated") or one("published"))})
    return out


def _hits_github_repositories(body):
    out = []
    for x in json.loads(body).get("items", []):
        words = " ".join((x.get("description") or "").split())
        out.append({"title": x.get("full_name", "") + (f": {words[:100]}" if words else ""), "url": x.get("html_url", ""),
                    "date": _day(x.get("pushed_at"))})
    return [h for h in out if h["url"]]


def _hits_github_code(body):
    return [{"title": f"{(x.get('repository') or {}).get('full_name', '')}: {x.get('path', '')}", "url": x.get("html_url", ""),
             "date": "-"} for x in json.loads(body).get("items", []) if x.get("html_url")]


def _hits_pypi(body):
    d = json.loads(body)
    info = d.get("info") or {}
    if not info.get("name"):
        return []
    stamps = [f.get("upload_time_iso_8601") or f.get("upload_time") or "" for f in d.get("urls") or []]
    summary = " ".join((info.get("summary") or "").split())
    return [{"title": f"{info['name']} {info.get('version', '')}".strip() + (f": {summary[:100]}" if summary else ""),
             "url": info.get("package_url") or f"https://pypi.org/project/{info['name']}/", "date": _day(max(stamps, default=""))}]


# (host, path prefix) of a search_api template -> its response parser and how the terms become the {q} of the request
SEARCH_SHAPES = {
    ("learn.microsoft.com", "/api/search"): (_hits_learn, " ".join),
    ("export.arxiv.org", "/api/query"): (_hits_arxiv, " AND all:".join),  # the template's `all:` leads the first word
    ("api.github.com", "/search/repositories"): (_hits_github_repositories, " ".join),
    ("api.github.com", "/search/code"): (_hits_github_code, " ".join),
    ("pypi.org", "/pypi/"): (_hits_pypi, "-".join),
}


def search_shape(template):
    """(parser, joiner) for a search_api template, or None when no response shape is known for its host and path."""
    u = urllib.parse.urlsplit(template.replace("{q}", "q"))
    return next((v for (host, path), v in SEARCH_SHAPES.items() if u.netloc == host and u.path.startswith(path)), None)


def search_path(url):
    return os.path.join(SEARCH_CACHE, hashlib.sha256(url.encode("utf-8")).hexdigest()[:24] + ".json")


def search(name, terms, rows=None, refresh=False, now=None):
    """The hits of the search_api of provider `name` for `terms` (a list of words): {status, error, url (the request),
    hits ([{title, url, date}] in the API's order), fetched_utc, cached}. A 200 is kept SEARCH_AGE days under
    SEARCH_CACHE (`refresh` asks again). ValueError when the provider has no row, no search_api or no known response
    shape for it."""
    rows = rows if rows is not None else providers()
    row = next((r for r in rows if r["provider"] == name), None)
    if row is None:
        raise ValueError(f"no provider {name!r}; `provider.py list` shows them")
    tpl = (row.get("search_api") or "-").strip()
    if tpl in ("-", "") or "{q}" not in tpl:
        have = ", ".join(r["provider"] for r in rows if "{q}" in (r.get("search_api") or ""))
        raise ValueError(f"provider {name!r} has no search_api; those that have one: {have}")
    shape = search_shape(tpl)
    if shape is None:
        raise ValueError(f"search_api of {name!r} has a host or path with no known response shape (provider.SEARCH_SHAPES)")
    parse, join = shape
    url = tpl.replace("{q}", urllib.parse.quote(join(terms), safe=":"))
    now = now or datetime.datetime.now(datetime.timezone.utc)
    d = None
    if not refresh:
        try:
            with open(search_path(url), encoding="utf-8") as f:
                d = json.load(f)
            d = d if (now - datetime.datetime.fromisoformat(d["fetched_utc"])).days < SEARCH_AGE else None
        except (OSError, ValueError, KeyError):
            d = None
    if d is not None:
        return {**d, "cached": True}
    r = request(url)
    d = {"status": r["status"], "error": r["error"], "url": url, "hits": [], "fetched_utc": now.isoformat(), "cached": False}
    if r["status"] == 200:
        try:
            d["hits"] = parse(r["body"])
        except (ValueError, ET.ParseError, AttributeError, TypeError):
            d.update(status=0, error="the answer is not in the shape of this search_api")
    elif r["status"] == 404 and urllib.parse.urlsplit(url).netloc == "pypi.org":
        d["status"] = 200  # PyPI answers a project name that does not exist with 404: no hit, not a failure
    if d["status"] == 200:
        os.makedirs(SEARCH_CACHE, exist_ok=True)
        with open(search_path(url), "w", encoding="utf-8", newline="\n") as f:
            json.dump({k: v for k, v in d.items() if k != "cached"}, f)
    return d


def cmd_search(a, rows):
    """Print the hits of the search_api of provider a.name for a.terms, `N date title` and the url under it (exit 1
    when the API did not answer 200 or holds no hit, 2 for a provider with no search_api)."""
    terms = [w for t in a.terms for w in t.split()]
    try:
        d = search(a.name, terms, rows, refresh=a.refresh)
    except ValueError as e:
        print(str(e))
        return 2
    print(f"search: {a.name} {' '.join(terms)!r} ({d['url']}; " + ("cache of " if d["cached"] else "fetched ") + f"{d['fetched_utc'][:10]})")
    if d["status"] != 200:
        why = d["status"] or d["error"]
        print(f"not searched: {why}" + ("; the API's rate limit, ask again later" if d["status"] in (403, 429) else "") +
              ("; GitHub code search needs authentication, which provider.py does not send: use WebSearch" if d["status"] == 401 else ""))
        return 1
    if not d["hits"]:
        print("no hit")
        return 1
    for i, h in enumerate(d["hits"][:a.limit], 1):
        print(f"{i}. {h['date']}  {h['title']}\n   {h['url']}")
    if len(d["hits"]) > a.limit:
        print(f"{len(d['hits']) - a.limit} more: raise --max")
    return 0


# ---------------------------------------------------------------- the licence of a source

ANTHROPIC_TERMS = "Anthropic terms (no open licence)"
ANTHROPIC_HOSTS = ("code.claude.com", "anthropic.com", "www.anthropic.com")
ARXIV_HOSTS = ("arxiv.org", "www.arxiv.org", "export.arxiv.org", "ar5iv.org", "ar5iv.labs.arxiv.org")
ARXIV_ID = re.compile(r"^/(?:abs|pdf|html)/(.+?)(?:\.pdf)?/?$")
ABS_LICENSE = re.compile(r'class="abs-license"[^>]*>\s*<a[^>]*\bhref="([^"]+)"', re.I)
CC_LINK = re.compile(r"creativecommons\.org/(licenses|publicdomain)/([a-z-]+)/(\d\.\d)", re.I)
CC_SPDX = re.compile(r"^CC-(BY(?:-(?:NC|SA|ND))*)-(\d\.\d)$")
NO_REUSE = re.compile(r"(?:^|-)(?:NC|ND)(?:-|$)|^(?:BUSL|SSPL|Elastic|FSL|PolyForm|Commons-Clause)", re.I)  # NC, ND, source-available
LICENCE_FILE = re.compile(r"^(?:LICEN[CS]E|COPYING)(?:[.-].*)?$", re.I)
CODE_LICENCE = re.compile(r"[-_.]code\b", re.I)  # LICENSE-CODE: the licence of the repository's code, beside its content's
CC_TITLE = re.compile(  # the first line of a Creative Commons legal-code file: the licence's name, or CC0's
    r"^(?:#+\s*)?(?:Creative Commons\s+)?(?:CC0\s+(?P<zero>\d\.\d)\s+Universal"
    r"|Attribution(?P<terms>(?:-(?:NonCommercial|ShareAlike|NoDerivatives))*)\s+(?P<ver>\d\.\d)\s+International)\s*$", re.I)
CC_TITLE_WORDS = {"noncommercial": "NC", "sharealike": "SA", "noderivatives": "ND"}
REPO_PAGES = ("blob", "tree", "raw", "blame")  # the path words after OWNER/REPO that are files of the repository
GITLAB_SPDX = {k.lower(): k for k in (  # GitLab names a licence by its lowercase SPDX id; the ids not here are upper-cased
    "Apache-2.0", "Artistic-2.0", "BSD-2-Clause", "BSD-3-Clause", "BSL-1.0", "MIT", "MPL-2.0", "Unlicense", "Zlib")}
META_FEEDBACK = re.compile(r"<meta\b[^>]*\bname=\"github_feedback_content_git_url\"[^>]*>", re.I)


def _found(family, licence, reuse, evidence):
    return {"family": family, "licence": licence, "reuse": reuse, "evidence": evidence, "note": ""}


def _unread(family, why):
    return {"family": family, "licence": "", "reuse": "", "evidence": "", "note": why}


def spdx_words(spdx):
    """An SPDX id in the words the rows use: `CC-BY-SA-4.0` -> `CC BY-SA 4.0`, `CC0-1.0` -> `CC0 1.0`, the rest as it is."""
    m = CC_SPDX.match(spdx)
    if m:
        return f"CC {m.group(1)} {m.group(2)}"
    return "CC0 " + spdx[4:] if spdx.startswith("CC0-") else spdx


def _arxiv_licence(u):
    m = ARXIV_ID.match(u.path)
    if not m or u.hostname.lower() not in ARXIV_HOSTS:
        return _unread("arxiv", "not an arXiv abstract, PDF or HTML url")
    page = f"https://arxiv.org/abs/{m.group(1)}"
    r = request(page, limit=2_000_000)
    if r["status"] != 200:
        return _unread("arxiv", f"{page} did not answer 200 ({r['status'] or r['error']})")
    text = r["body"].decode("utf-8", "replace")
    link = ABS_LICENSE.search(text)
    if not link:
        return _unread("arxiv", f"{page} has no licence link")
    href, words = link.group(1), "licence link on the arXiv abstract page"
    if "arxiv.org/licenses/nonexclusive-distrib" in href:
        return _found("arxiv", "arXiv non-exclusive distribution licence (no reuse grant)", "quote", page)
    cc = CC_LINK.search(href)
    if cc and re.fullmatch(r"by(?:-(?:nc|sa|nd))*|zero", cc.group(2).lower()):
        kind = cc.group(2).lower()
        name = f"CC0 {cc.group(3)}" if kind == "zero" else f"CC {kind.upper()} {cc.group(3)}"
        return _found("arxiv", f"{name} ({words})", "quote" if re.search(r"-(?:nc|nd)\b", kind) else "copy", page)
    return _unread("arxiv", f"{page} links a licence this tool does not know: {href}")


def _repository_of(u):
    """(forge, `owner/repo`, api url) of the repository a GitHub or GitLab page is a file of or the front page of, or None."""
    host = (u.hostname or "").lower()
    p = [urllib.parse.unquote(x) for x in u.path.split("/") if x]
    if host == "raw.githubusercontent.com":
        ok = len(p) >= 4  # owner, repository, ref, path
    else:
        ok = host in ("github.com", "www.github.com") and len(p) >= 2 and p[0] not in GH_NOT_OWNER and (len(p) == 2 or p[2] in REPO_PAGES)
    if ok:
        slug = f"{p[0]}/{re.sub(r'[.]git$', '', p[1])}"
        return "GitHub", slug, f"https://api.github.com/repos/{slug}"
    if host == "gitlab.com":
        head, dash, rest = u.path.partition("/-/")
        if dash and rest.split("/")[0] not in REPO_PAGES:  # an issue, a merge request, a wiki: not the repository's files
            return None
        parts = [urllib.parse.unquote(x) for x in head.split("/") if x]
        if len(parts) >= 2:
            slug = re.sub(r"[.]git$", "", "/".join(parts))
            return "GitLab", slug, f"https://gitlab.com/api/v4/projects/{urllib.parse.quote(slug, safe='')}?license=true"
    return None


def _repository_licence(forge, api):
    """(status, spdx, archived, note) of one repository from its forge's API. `spdx` is "" when the repository has no
    licence the forge recognised (none, NOASSERTION, GitLab's `other`); `status` the HTTP status (0: no answer)."""
    r = request(api, limit=2_000_000)
    if r["status"] != 200:
        return r["status"], "", False, f"{api} answered {r['status'] or r['error']}" + (
            " (GitHub's unauthenticated limit is 60 REST requests an hour)" if r["status"] in (403, 429) else "")
    try:
        d = json.loads(r["body"].decode("utf-8", "replace"))
        lic = d.get("license") or {}
        if forge == "GitHub":
            spdx = lic.get("spdx_id") or ""
        else:
            key = (lic.get("key") or "").lower()
            spdx = GITLAB_SPDX.get(key, key.upper()) if key and key != "other" else ""
        return 200, "" if spdx == "NOASSERTION" else spdx, bool(d.get("archived")), ""
    except (ValueError, AttributeError, TypeError):
        return 0, "", False, f"{api} answered a body that is not the forge's JSON"


def _spdx_reuse(spdx):
    return "quote" if NO_REUSE.search(spdx) else "copy"


def _repo_licence(u):
    got = _repository_of(u)
    if got is None:
        return _unread("repository", "not a file or the front page of a GitHub or GitLab repository")
    forge, slug, api = got
    status, spdx, _, note = _repository_licence(forge, api)
    if status != 200:
        return _unread("repository", note)
    if not spdx or spdx.startswith("LicenseRef-"):
        return _unread("repository", f"{forge} recognises no licence of {slug}: read its licence file")
    reuse = _spdx_reuse(spdx)
    tail = f"repository licence of {slug}, from the {forge} API" + ("" if reuse == "copy" else "; NC, ND or source-available terms: no reuse grant")
    return _found("repository", f"{spdx_words(spdx)} ({tail})", reuse, api)


def _licence_files(slug):
    """The names of the licence files at a GitHub repository's root, its code licence (`LICENSE-CODE`) left out; None
    when the listing could not be read."""
    r = request(f"https://api.github.com/repos/{slug}/contents/", limit=2_000_000)
    if r["status"] != 200:
        return None
    try:
        names = [x.get("name", "") for x in json.loads(r["body"].decode("utf-8", "replace")) if x.get("type") == "file"]
    except (ValueError, AttributeError, TypeError):
        return None
    return sorted(n for n in names if LICENCE_FILE.match(n) and not CODE_LICENCE.search(n))


def _licence_file_spdx(slug, name):
    """(spdx, url) of a licence file at a GitHub repository's root whose first line is a Creative Commons legal-code
    title (`# Attribution 4.0 International`, `CC0 1.0 Universal`); spdx is "" when the file could not be read or is
    another text. For a mirror whose licence files GitHub's API reads as NOASSERTION."""
    url = f"https://raw.githubusercontent.com/{slug}/HEAD/{urllib.parse.quote(name)}"
    r = request(url, limit=4096)
    if r["status"] != 200:
        return "", url
    head = next((x.strip() for x in r["body"].decode("utf-8-sig", "replace").splitlines() if x.strip()), "")
    m = CC_TITLE.match(head)
    if not m:
        return "", url
    if m.group("zero"):
        return f"CC0-{m.group('zero')}", url
    kinds = [CC_TITLE_WORDS[k.lower()] for k in m.group("terms").split("-") if k]
    return "-".join(["CC-BY", *kinds, m.group("ver")]), url


def _learn_licence(u):
    page = urllib.parse.urlunsplit((u.scheme, u.netloc, u.path, u.query, ""))
    r = request(page, limit=5_000_000)
    if r["status"] != 200:
        return _unread("learn", f"{page} did not answer 200 ({r['status'] or r['error']})")
    tag = META_FEEDBACK.search(r["body"].decode("utf-8", "replace"))
    content = re.search(r"\bcontent=\"([^\"]*)\"", tag.group(0)) if tag else None
    repo = _repository_of(urllib.parse.urlsplit(content.group(1))) if content else None
    if repo is None or repo[0] != "GitHub":
        return _unread("learn", f"{page} names no GitHub mirror in its github_feedback_content_git_url")
    _, slug, api = repo
    terms = "Microsoft Learn terms of use"
    status, spdx, archived, note = _repository_licence("GitHub", api)
    if status == 404:
        return _found("learn", f"{terms} (source repository {slug} is not public: the GitHub API answers 404)", "quote", api)
    if status != 200:
        return _unread("learn", note)
    if archived:
        return _found("learn", f"{terms} (public mirror {slug} archived: its licence covers only the archived text)", "quote", api)
    files = _licence_files(slug)
    if files is None:
        return _unread("learn", f"the licence files of {slug} could not be listed (GitHub's unauthenticated limit is 60 requests an hour)")
    if len(files) > 1:
        return _found("learn", f"{terms} (public mirror {slug}: licence files {', '.join(files)} conflict)", "quote", api)
    if not spdx or spdx.startswith("LicenseRef-"):  # none or NOASSERTION (a LICENSE.md beside a LICENSE-CODE.md): read the one file
        file_spdx, evidence = _licence_file_spdx(slug, files[0]) if files else ("", api)
        if not file_spdx:
            return _unread("learn", f"GitHub recognises no licence of the mirror {slug}: read its licence file")
        spdx, api = file_spdx, evidence
    if _spdx_reuse(spdx) == "quote":
        return _found("learn", f"{terms} (public mirror {slug}, {spdx_words(spdx)}: no reuse grant)", "quote", api)
    return _found("learn", f"{spdx_words(spdx)} (public mirror {slug})", "copy", api)


def read_licence(url):
    """What the source's own licence record gives a `kbid.py add` row: {family, licence, reuse, evidence, note}. `family`
    names how it was read (`arxiv`: the licence link of the abstract page; `repository`: the GitHub or GitLab API;
    `learn`: the public mirror the page's github_feedback_content_git_url names, by kb/_self/content-rules.md,
    Licensing and privacy, its one licence file's Creative Commons title where the API gives no id; `anthropic`: the fixed pair of code.claude.com and anthropic.com; "" for any other host).
    `licence` and `reuse` are "" when nothing was read, and `note` says why. A reuse of `copy` is only an open licence
    (SPDX id, CC BY or CC BY-SA); NC, ND, source-available, non-exclusive and a recognised-nowhere licence are `quote` or
    unread. No credential is read and no Authorization header sent: GitHub's REST API allows 60 requests an hour."""
    u = urllib.parse.urlsplit(url.strip())
    host = (u.hostname or "").lower()
    if host in ANTHROPIC_HOSTS:
        return _found("anthropic", ANTHROPIC_TERMS, "quote", f"fixed pair of {host}")
    if host in ARXIV_HOSTS:
        return _arxiv_licence(u)
    if host == "learn.microsoft.com":
        return _learn_licence(u)
    if _repository_of(u) is not None:
        return _repo_licence(u)
    return _unread("", f"no licence record is read for the host {host or url!r}")


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
    q = sub.add_parser("search", help="query a provider's own search API: title, url and date of each hit")
    q.add_argument("name", help="a provider row with a search_api (`list` shows them)")
    q.add_argument("terms", nargs="+", metavar="TERMS", help="the search words")
    q.add_argument("--max", type=int, default=SEARCH_MAX, metavar="N", dest="limit", help=f"hits printed (default {SEARCH_MAX})")
    q.add_argument("--refresh", action="store_true", help=f"ask again although the cache holds the answer ({SEARCH_AGE} days)")
    a = ap.parse_args()
    if a.cmd == "read" and (a.context < 0 or a.limit < 1 or a.start < 1):
        ap.error("--context must be 0 or more, --max and --from 1 or more")
    if a.cmd == "search" and a.limit < 1:
        ap.error("--max must be 1 or more")
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
    if a.cmd == "search":
        return cmd_search(a, rows)
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
