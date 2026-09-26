#!/usr/bin/env python3
"""Census: confirm that every source in _sources.csv is still current (stdlib only). /kb-census drives it.

  census.py check [--date D] [--out PATH] [--jobs N] [--source ID ...]   phases 0-1: one mechanical verdict per source
  census.py record LOG --from RESULTS.json | --id ID --outcome O [--note T]   phase 2: what reading decided
  census.py confirm LOG [--date D] [--dry-run]     phase 3: dates and evidence for the confirmed sources and articles
  census.py sample LOG [--changed 0.10] [--ok 0.05] [--seed N]   phase 4: the sources an independent check re-reads
  census.py summary LOG                            counts per bucket and outcome

check (no judgment, network read-only) writes the verdict log LOG, by default _census/<D>.csv, one row per source:
  id,url,kind,repo,pin,path,retrieved_utc,http_status,bucket,evidence,proof,note,used_in,outcome,outcome_note
kind: raw-pin / raw-ref (a raw file at a commit / at a branch or tag), gh-pin / gh-ref (github.com blob or tree), release,
  gh-page, api-* (api.github.com), learn (learn.microsoft.com), live (anything else).
bucket:
  OK            nothing changed since retrieval: the pinned file is byte-identical at the branch tip (content compared,
                so a shallow clone's boundary commit is no change); a recorded release is still the newest of its own
                series (same tag shape, created later); a Learn page's source file in its public MicrosoftDocs repo
                (LEARN_MAP) has no commit since retrieval; a live page's sitemap lastmod or page date is not after it
  CHANGED       the file or page changed since retrieval (evidence: commits or date)
  GONE          404/410, the file was deleted, the commit or tag vanished
  NEWER-VERSION a newer release of the pinned one exists and the cited file differs there
  NEEDS-READING nothing mechanical decides it: no date on the page, an HTTP error, or the host is denied here
                (note `blocked`), or MicrosoftDocs/memdocs (archived: re-source to the live Learn page)
Git work uses bare blobless clones in _cache/census/repos/ (git over https; api.github.com is never called).

record fills outcome/outcome_note after phase 2 read a source in full:
  confirmed (the facts still hold), updated (facts rewritten, same source), superseded (a new row replaced it; the note
  names the new id), gone (facts marked [UNK], logged in _gaps.md), unconfirmed (could not be read; left as it was).
RESULTS.json: [{"id": "S123", "outcome": "confirmed", "note": "..."}, ...].

confirm (phase 3) treats as confirmed: bucket OK with no outcome, and outcome confirmed or updated. For each it sets
_sources.csv retrieved_utc to D and ends version_or_date with `confirmed D: <proof>` (replacing an earlier such suffix),
and sets checked_utc in _fetch_state.csv (fetch columns untouched: the census compared, it did not snapshot). Then
every article (front matter with sources:) whose listed sources were all confirmed, or added by the census (rows not
in LOG with retrieved_utc D), gets retrieved_utc D.
Superseded, gone, unconfirmed and unread sources keep their dates: a date is only moved by real confirmation.

sample (phase 4) prints a CSV of ids for the independent re-check: a fraction of the sources whose facts phase 2
changed (updated/superseded/gone) and of the confirmed ones (bucket OK or outcome confirmed), seeded, at least one each.

Exit: 0 ok; 1 check could not write, or confirm/record found an unknown id; 2 bad arguments.
"""
import argparse, concurrent.futures as cf, csv, datetime, functools, io, json, os, random, re, ssl, subprocess, sys, threading
import urllib.error, urllib.request
from collections import Counter, defaultdict
from urllib.parse import unquote, urlparse

KB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_index, kbcommon, kbid  # noqa: E402

REPOS = os.path.join(KB, "_cache", "census", "repos")
COLS = ["id", "url", "kind", "repo", "pin", "path", "retrieved_utc", "http_status", "bucket", "evidence", "proof", "note",
        "used_in", "outcome", "outcome_note"]
BUCKETS = ("OK", "CHANGED", "GONE", "NEWER-VERSION", "NEEDS-READING")
OUTCOMES = ("confirmed", "updated", "superseded", "gone", "unconfirmed")
SHA = re.compile(r"[0-9a-f]{40}")
BLOCKED = "blocked"
UA = "it-ops-kb-census/1.0 (read-only link check)"
# Learn url path (after /en-us/) -> (public source repo, path prefix): the page is <prefix><rest>.md or <rest>/index.md
LEARN_MAP = [
    ("entra/", "MicrosoftDocs/entra-docs", "docs/"),
    ("windows-server/", "MicrosoftDocs/windowsserverdocs", "WindowsServerDocs/"),
    ("sql/", "MicrosoftDocs/sql-docs", "docs/"),
    ("powershell/dsc/", "MicrosoftDocs/PowerShell-Docs-DSC", "dsc/docs-conceptual/"),
    ("graph/api/", "microsoftgraph/microsoft-graph-docs-contrib", "api-reference/v1.0/api/"),
]
SHALLOW = ("sql-docs", "entra-docs", "windowsserverdocs")  # large doc repos: history since SHALLOW_SINCE is enough
SHALLOW_SINCE = "2026-01-01"


def today():
    return datetime.date.today().isoformat()


def run(args, cwd=None, timeout=300):
    try:
        p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except (subprocess.TimeoutExpired, OSError) as e:
        return 124, "", str(e)


def g(d, *args, timeout=300):
    return run(["git", *args], cwd=d, timeout=timeout)


def verdict(bucket, evidence, proof="", note=""):
    return {"bucket": bucket, "evidence": evidence, "proof": proof, "note": note}


# ---------------------------------------------------------------- phase 0: classify

def classify(url):
    u = urlparse(url)
    host, parts = u.netloc.lower(), [unquote(p) for p in u.path.split("/")]
    d = {"kind": "live", "host": host, "repo": "", "pin": "", "path": "", "refparts": []}
    if host == "raw.githubusercontent.com" and len(parts) > 4:
        d.update(repo=f"github.com/{parts[1]}/{parts[2]}", pin=parts[3], path="/".join(parts[4:]), refparts=parts[3:])
        d["kind"] = "raw-pin" if SHA.fullmatch(parts[3]) else "raw-ref"
    elif host == "gitlab.com" and "/-/raw/" in u.path:
        pre, _, rest = u.path.partition("/-/raw/")
        ref, _, path = rest.partition("/")
        d.update(repo="gitlab.com" + pre, pin=ref, path=unquote(path), refparts=unquote(rest).split("/"),
                 kind="raw-pin" if SHA.fullmatch(ref) else "raw-ref")
    elif host == "github.com" and len(parts) >= 3:
        d["repo"] = f"github.com/{parts[1]}/{parts[2]}"
        sub = parts[3:]
        if sub[:2] in (["releases", "download"], ["releases", "tag"]) and len(sub) > 2:
            d.update(kind="release", pin=sub[2])
        elif sub[:1] in (["blob"], ["tree"]) and len(sub) > 1:
            d.update(kind="gh-pin" if SHA.fullmatch(sub[1]) else "gh-ref", pin=sub[1], path="/".join(sub[2:]), refparts=sub[1:])
        else:
            d.update(kind="gh-page", repo="")  # repository home, issues, wiki: github.com pages, not a checkout
    elif host == "api.github.com" and len(parts) > 3 and parts[1] == "repos":
        d["repo"] = f"github.com/{parts[2]}/{parts[3]}"
        rest = [p for p in parts[4:] if p]
        if rest[:1] == ["releases"]:
            d["kind"] = "api-releases"
        elif rest[:3] == ["git", "refs", "tags"] and len(rest) > 3:
            d.update(kind="api-tagref", pin=rest[3])
        elif rest[:1] == ["contents"]:
            ref = re.search(r"[?&]ref=([^&]+)", url)
            d.update(kind="api-contents", pin=ref.group(1) if ref else "", path="/".join(rest[1:]))
        elif rest[:1] == ["commits"]:
            p = re.search(r"[?&]path=([^&]+)", url)
            d.update(kind="api-commits", path=unquote(p.group(1)) if p else "")
        elif not rest:
            d["kind"] = "api-repo"
        else:
            d.update(kind="api-other", repo="")
    elif host == "learn.microsoft.com":
        d["kind"] = "learn"
        rest = "/".join(parts[2:])
        for pre, repo, rpre in LEARN_MAP:
            if rest.startswith(pre):
                d.update(repo="github.com/" + repo, path=rpre + rest[len(pre):].rstrip("/"))
                break
    return d


# ---------------------------------------------------------------- git checks

_clone_locks = defaultdict(threading.Lock)
_ready = {}


def repo_dir(repo, base=None):
    """(bare blobless clone of https://<repo>, error). `repo` may also be a local path (tests)."""
    base = base or REPOS
    local = os.path.isdir(repo)
    d = os.path.join(base, re.sub(r"[^\w.-]+", "__", repo.strip("/")) + ".git")
    with _clone_locks[d]:
        if d in _ready:
            return _ready[d]
        if not os.path.isdir(d):
            os.makedirs(base, exist_ok=True)
            since = [f"--shallow-since={SHALLOW_SINCE}"] if repo.endswith(SHALLOW) else []
            code, _, err = run(["git", "clone", "-q", "--bare", "--filter=blob:none", *since,
                                repo if local else f"https://{repo}", d], timeout=1800)
            if code:
                _ready[d] = (None, f"clone failed: {err.splitlines()[-1][:120] if err else code}")
                return _ready[d]
        g(d, "fetch", "-q", "--tags", "--force", "origin", "+refs/heads/*:refs/heads/*", timeout=900)
        _ready[d] = (d, "")
    return _ready[d]


def have_commit(d, sha):
    if g(d, "cat-file", "-e", sha + "^{commit}")[0] == 0:
        return True
    g(d, "fetch", "-q", "--filter=blob:none", "origin", sha, timeout=900)
    return g(d, "cat-file", "-e", sha + "^{commit}")[0] == 0


def head(d):
    return g(d, "rev-parse", "HEAD")[1]


def tip_for(d, pin):
    """(tip, name): HEAD when the pin is on the default branch, else the newest branch tip containing it."""
    h = head(d)
    if g(d, "merge-base", "--is-ancestor", pin, h)[0] == 0:
        return h, "HEAD"
    out = g(d, "for-each-ref", "--contains", pin, "--sort=-committerdate", "--format=%(refname:short) %(objectname)", "refs/heads")[1]
    if out:
        name, sha = out.splitlines()[0].split()
        return sha, name
    return h, "HEAD"


def check_pin(d, pin, path):
    """A file at a commit: compared by content with the branch tip."""
    if not have_commit(d, pin):
        return verdict("GONE", f"pin {pin[:12]} can no longer be fetched")
    tip, branch = tip_for(d, pin)
    ev = f"{branch}@{tip[:12]}"
    out = g(d, "log", "--format=%H %cs", f"{pin}..{tip}", "--", path)[1]
    commits = [ln.split() for ln in out.splitlines() if ln.strip()]
    if g(d, "cat-file", "-e", f"{tip}:{path}")[0] == 0:
        if g(d, "diff", "--quiet", pin, tip, "--", path, timeout=900)[0] == 0:
            return verdict("OK", f"file identical at the pin and at {ev}", ev)
        latest = commits[0] if commits else [tip, "?"]
        return verdict("CHANGED", f"file differs at {ev}; latest change {latest[0][:12]} {latest[1]}", ev, f"latest={latest[0]}")
    out = g(d, "diff", "-M", "--diff-filter=R", "--name-status", pin, tip, timeout=900)[1]  # whole tree: renames need both paths
    for ln in out.splitlines():
        f = ln.split("\t")
        if f[0].startswith("R") and len(f) == 3 and f[1] == path:
            return verdict("CHANGED", f"renamed to {f[2]} at {ev}", ev, f"renamed={f[2]}")
    return verdict("GONE", f"file deleted upstream (not at {ev})", ev)


VER = re.compile(r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:\.(\d+))?([-.+]?.*)?$")


def ver_key(s):
    m = VER.match(s)
    return (tuple(int(x or 0) for x in m.groups()[:4]), (m.group(5) or "").strip("-.+")) if m else None


def is_pre(suffix):
    return bool(re.search(r"(?i)alpha|beta|rc|preview|pre|dev", suffix or ""))


def split_tag(tag):
    m = re.match(r"^(.*?)(v?\d.*)$", tag)
    return (m.group(1), m.group(2)) if m else (None, None)


def newer_tags(tag, tags, when):
    """Tags in `tags` that are newer releases than `tag`: same prefix (monorepo families), same shape for a stable
    tag (no fork suffixes, date tags or 4-part numbers), created no earlier; a stable tag ignores pre-releases."""
    prefix, rest = split_tag(tag)
    k = ver_key(rest) if rest else None
    if not k:
        return None
    shape = lambda s: re.sub(r"\d+", "9", s)  # noqa: E731
    out = []
    for t in tags:
        p, r = split_tag(t)
        if t == tag or p != prefix or not r:
            continue
        kt = ver_key(r)
        if not kt or (is_pre(kt[1]) and not is_pre(k[1])) or (not is_pre(k[1]) and shape(r) != shape(rest)):
            continue
        if when.get(t, "") < when.get(tag, ""):
            continue
        if kt[0] > k[0] or (kt[0] == k[0] and is_pre(k[1]) and (not is_pre(kt[1]) or kt[1] > k[1])):
            out.append((kt, t))
    return [t for _, t in sorted(out)]


@functools.lru_cache(maxsize=None)
def repo_tags(d):
    """([tag], {tag: creator date}) of a repository clone; read once per run (the clones do not change during one)."""
    out = g(d, "for-each-ref", "--format=%(refname:short) %(creatordate:iso-strict)", "refs/tags")[1]
    when = dict(ln.split(" ", 1) for ln in out.splitlines() if " " in ln)
    return list(when), when


def split_ref(d, parts):
    """(ref, path) from `ref/with/slashes/path/to/file`: the longest prefix naming a branch or tag here."""
    for n in range(len(parts), 0, -1):
        ref = "/".join(parts[:n])
        if any(g(d, "rev-parse", "-q", "--verify", f"refs/{k}/{ref}")[0] == 0 for k in ("heads", "tags")):
            return ref, "/".join(parts[n:])
    return parts[0], "/".join(parts[1:])


def check_ref(d, ref, path, since):
    """A file (or the whole tree) at a branch or tag name."""
    if g(d, "rev-parse", "-q", "--verify", f"refs/tags/{ref}")[0] == 0:
        tags, when = repo_tags(d)
        newer = newer_tags(ref, tags, when) or []
        if not newer:
            return verdict("OK", f"tag {ref} is the newest release of its series", f"tag {ref} newest")
        if path and g(d, "diff", "--quiet", ref, newer[-1], "--", path, timeout=900)[0] == 0:
            return verdict("OK", f"newer release {newer[-1]}; the file is identical there", f"identical in {newer[-1]}")
        return verdict("NEWER-VERSION", f"newer release {newer[-1]}; the file differs from {ref}", "", f"newer={newer[-1]}")
    branch = head(d) if ref == "HEAD" else g(d, "rev-parse", "-q", "--verify", f"refs/heads/{ref}")[1]
    if not branch:
        return verdict("GONE", f"no branch or tag {ref!r}")
    if path and g(d, "cat-file", "-e", f"{branch}:{path}")[0] != 0:
        return verdict("GONE", f"{path} is not on {ref}")
    out = g(d, "log", "--format=%H %cs", f"--since={since}T00:00:00Z", branch, "--", path or ".")[1]
    commits = [ln.split() for ln in out.splitlines() if ln.strip()]
    ev = f"{ref}@{branch[:12]}"
    if not commits:
        return verdict("OK", f"no commit on {ref} touches it since {since}; {ev}", ev)
    return verdict("CHANGED", f"{len(commits)} commit(s) on {ref} since {since}, latest {commits[0][0][:12]} {commits[0][1]}", ev)


def check_release(d, tag):
    if g(d, "rev-parse", "-q", "--verify", f"refs/tags/{tag}")[0] != 0:
        return verdict("GONE", f"tag {tag} no longer exists")
    tags, when = repo_tags(d)
    newer = newer_tags(tag, tags, when)
    if newer is None:
        return verdict("NEEDS-READING", f"cannot compare release tag {tag}")
    if newer:
        return verdict("NEWER-VERSION", f"newer release(s): {', '.join(newer[-3:])}", "", f"newer={newer[-1]}")
    return verdict("OK", f"{tag} is still the newest release of its series", f"release {tag} newest")


RECORDED = re.compile(r"(?<![\w.])(v?\d+\.\d+(?:\.\d+)*(?:[-.][0-9A-Za-z.]+)?)")


def check_api_release(d, kind, rec, since):
    m = RECORDED.search(rec)
    if m and g(d, "rev-parse", "-q", "--verify", f"refs/tags/{m.group(1)}")[0] == 0:
        tags, when = repo_tags(d)
        newer = newer_tags(m.group(1), tags, when) or []
        if not newer:
            return verdict("OK", f"recorded release {m.group(1)} is still the newest of its series", f"release {m.group(1)} newest")
        return verdict("NEWER-VERSION", f"newer than the recorded {m.group(1)}: {', '.join(newer[-3:])}", "", f"newer={newer[-1]}")
    if kind == "api-repo":
        return verdict("NEEDS-READING", "repository metadata; no recorded release to compare (api.github.com is not called)")
    out = g(d, "for-each-ref", "--sort=-creatordate", "--format=%(refname:short) %(creatordate:short)", "refs/tags")[1]
    after = [ln.split()[0] for ln in out.splitlines() if len(ln.split()) == 2 and ln.split()[1] > since
             and re.fullmatch(r"v?\d+\.\d+(\.\d+)?([-.][0-9A-Za-z.]+)?", ln.split()[0])]
    if not after:
        return verdict("OK", f"no release tagged after retrieval {since}", f"no release after {since}")
    return verdict("NEWER-VERSION", f"release(s) tagged after retrieval {since}: {', '.join(after[:3])}", "", f"newer={after[0]}")


def check_learn(d, path, since):
    cands = (path + ".md", path + "/index.md", path + ".yml", path + "/index.yml")
    have = set(g(d, "ls-tree", "-z", "--name-only", "HEAD", "--", *cands)[1].split("\0"))  # one call for the four probes
    for cand in cands:
        if cand in have:
            out = g(d, "log", "--format=%H %cs", f"--since={since}T00:00:00Z", "HEAD", "--", cand)[1]
            commits = [ln.split() for ln in out.splitlines() if ln.strip()]
            h = head(d)
            if not commits:
                return verdict("OK", f"source file {cand} has no commit since {since} (HEAD {h[:12]})", f"git_commit_id {h[:12]}")
            return verdict("CHANGED", f"source file {cand}: {len(commits)} commit(s) since {since}, latest "
                                      f"{commits[0][0][:12]} {commits[0][1]}", f"git_commit_id {commits[0][0][:12]}")
    return None


# ---------------------------------------------------------------- http checks

_host_sem = defaultdict(lambda: threading.Semaphore(2))
_sitemaps, _sitemap_lock = {}, threading.Lock()
_ctx = None


def ssl_ctx():
    global _ctx
    if _ctx is None:
        cafile = os.environ.get("SSL_CERT_FILE") or ("/root/.ccr/ca-bundle.crt" if os.path.exists("/root/.ccr/ca-bundle.crt") else None)
        _ctx = ssl.create_default_context(cafile=cafile)
    return _ctx


def fetch(url, timeout=25, limit=1_000_000):
    """(status or 'blocked' or 'error: ...', text, final url)."""
    with _host_sem[urlparse(url).netloc]:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ssl_ctx()) as resp:
                return resp.status, resp.read(limit).decode("utf-8", "replace"), resp.geturl()
        except urllib.error.HTTPError as e:
            return e.code, "", url
        except (urllib.error.URLError, OSError) as e:
            msg = str(getattr(e, "reason", e))
            return (BLOCKED if re.search(r"(?i)tunnel|403 forbidden", msg) else f"error: {msg[:60]}"), "", url
        except Exception as e:  # noqa: BLE001 - a link check must never stop the census
            return f"error: {type(e).__name__}", "", url


def sitemap_lastmod(url):
    u = urlparse(url)
    with _sitemap_lock:
        if u.netloc not in _sitemaps:
            m = {}
            for sm in ("/docs/sitemap.xml", "/sitemap.xml"):
                st, body, _ = fetch(f"{u.scheme}://{u.netloc}{sm}", limit=30_000_000)
                if st == 200:
                    m.update({loc.rstrip("/"): lm for loc, lm in
                              re.findall(r"<loc>\s*([^<]+?)\s*</loc>\s*<lastmod>\s*([^<]+?)\s*</lastmod>", body)})
            _sitemaps[u.netloc] = m
    base = url.split("#")[0].rstrip("/")
    return _sitemaps[u.netloc].get(base) or _sitemaps[u.netloc].get(base[:-3] if base.endswith(".md") else "")


DATE_PATTERNS = [
    r'property="article:modified_time"\s+content="([^"]+)"', r'"dateModified"\s*:\s*"([^"]+)"',
    r'name="(?:last-modified|updated_at|ms\.date|revised)"\s+content="([^"]+)"',
    r'itemprop="dateModified"\s+(?:content|datetime)="([^"]+)"',
    r"(?i)last (?:updated|modified|revised)(?: on)?[:\s]+([A-Z][a-z]+ \d{1,2},? \d{4}|\d{4}-\d{2}-\d{2})",
]


def norm_date(s):
    s = (s or "").strip()
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    if m:
        return m.group(1)
    for fmt in ("%B %d, %Y", "%B %d %Y", "%b %d, %Y"):
        try:
            return datetime.datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def check_pypi(url, rec):
    m = re.match(r"https://pypi\.org/(?:pypi|project)/([^/?#]+)", url)
    st, body, _ = fetch(f"https://pypi.org/pypi/{m.group(1)}/json")
    if st != 200:
        return st, None
    try:
        ver = json.loads(body)["info"]["version"]
    except (ValueError, KeyError, TypeError):
        return st, None
    if re.search(rf"(?<![\w.]){re.escape(ver)}(?![\w.])", rec):
        return st, verdict("OK", f"PyPI latest {ver} matches the recorded version", f"PyPI {ver}")
    if not RECORDED.search(rec):
        return st, verdict("NEEDS-READING", f"PyPI latest {ver}; no version recorded to compare")
    return st, verdict("NEWER-VERSION", f"PyPI latest {ver}; recorded: {rec[:60]}", "", f"newer={ver}")


def check_live(url, since, rec):
    if url.startswith(("https://pypi.org/pypi/", "https://pypi.org/project/")):
        st, res = check_pypi(url, rec)
        if res:
            return st, res
    st, body, final = fetch(url)
    if st == BLOCKED:
        return st, verdict("NEEDS-READING", "host denied by this environment's network policy", "", "blocked")
    if st in (404, 410):
        return st, verdict("GONE", f"HTTP {st}")
    if st != 200:
        return st, verdict("NEEDS-READING", f"HTTP {st}")
    date, how = norm_date(sitemap_lastmod(url)), "sitemap lastmod"
    if not date:
        for pat in DATE_PATTERNS:
            m = re.search(pat, body)
            if m and norm_date(m.group(1)):
                date, how = norm_date(m.group(1)), "page date"
                break
    moved = f"; redirected to {final}" if final.rstrip("/") != url.rstrip("/") else ""
    if not date:
        return st, verdict("NEEDS-READING", f"HTTP 200, no last-updated date{moved}")
    if date > since:
        return st, verdict("CHANGED", f"{how} {date} is after retrieval {since}{moved}", f"{how} {date}")
    return st, verdict("OK", f"{how} {date}, not after retrieval {since}{moved}", f"{how} {date}")


# ---------------------------------------------------------------- check (phases 0-1)

def check_one(r, c):
    since = (r.get("retrieved_utc") or today())[:10]
    kind = c["kind"]
    if kind == "gh-page" or kind == "api-other":
        return "", verdict("NEEDS-READING", "a github.com page (issues, wiki, home) or API call; read it", "", "github page")
    if c["repo"]:
        d, err = repo_dir(c["repo"])
        if not d:
            if kind == "learn":
                return "", verdict("NEEDS-READING", f"source repo not readable ({err}); read the Learn page", "", "learn")
            return "", verdict("NEEDS-READING", err)
        if kind in ("raw-pin", "gh-pin"):
            res = check_pin(d, c["pin"], c["path"])
            if "MicrosoftDocs/memdocs" in c["repo"]:
                res = verdict("NEEDS-READING", res["evidence"] + "; MicrosoftDocs/memdocs is archived: re-source to the live "
                              "Learn page", "", "memdocs")
        elif kind in ("raw-ref", "gh-ref"):
            res = check_ref(d, *split_ref(d, c["refparts"]), since)
        elif kind == "release":
            res = check_release(d, c["pin"])
        elif kind in ("api-releases", "api-repo"):
            res = check_api_release(d, kind, r.get("version_or_date", ""), since)
        elif kind == "api-tagref":
            sha = g(d, "rev-parse", "-q", "--verify", f"refs/tags/{c['pin']}^{{commit}}")[1]
            obj = g(d, "rev-parse", "-q", "--verify", f"refs/tags/{c['pin']}")[1]
            rec = r.get("version_or_date", "")
            res = (verdict("OK", f"tag {c['pin']} still points to {sha[:12]}", f"tag {c['pin']}={sha[:12]}")
                   if sha and (sha[:12] in rec or obj[:12] in rec) else
                   verdict("CHANGED" if sha else "GONE", f"tag {c['pin']} -> {sha[:12] or 'missing'}; recorded {rec[:40]}"))
        elif kind == "api-contents":
            res = check_ref(d, c["pin"] or "HEAD", c["path"], since)
        elif kind == "api-commits":
            res = check_ref(d, "HEAD", c["path"], since)
        else:  # learn with a mapped source repo
            res = check_learn(d, c["path"], since) or verdict("NEEDS-READING", f"no source file for the page in {c['repo']}", "", "learn")
        st = fetch(r["url"])[0] if kind in ("raw-pin", "raw-ref") else ""
        return st, res
    if kind == "learn":
        st, _, _ = fetch(r["url"])
        note = "blocked" if st == BLOCKED else "learn"
        return st, verdict("NEEDS-READING", "a Learn page without a public source repo; read it (microsoft_docs_fetch)", "", note)
    return check_live(r["url"], since, r.get("version_or_date", ""))


read_sources = kbcommon.read_sources


def cmd_check(a):
    date = a.date or today()
    out = a.out or os.path.join(KB, "_census", f"{date}.csv")
    rows = [r for r in read_sources() if not a.source or r["id"] in a.source]
    if not rows:
        print("no source selected")
        return 2
    work = [(r, classify(r["url"])) for r in rows]
    print(f"phase 0: {len(work)} sources; " + ", ".join(f"{k}={n}" for k, n in sorted(Counter(c["kind"] for _, c in work).items())), flush=True)
    repos = sorted({c["repo"] for _, c in work if c["repo"]})
    with cf.ThreadPoolExecutor(8) as ex:
        for repo, (d, err) in zip(repos, ex.map(repo_dir, repos)):
            if not d:
                print(f"  {repo}: {err}", flush=True)

    def one(item):
        r, c = item
        try:
            st, res = check_one(r, c)
        except Exception as e:  # noqa: BLE001
            st, res = "", verdict("NEEDS-READING", f"census error: {type(e).__name__}: {e}")
        return r, c, st, res

    results = []
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        for n, item in enumerate(ex.map(one, work), 1):
            results.append(item)
            if n % 200 == 0:
                print(f"  {n}/{len(work)}", flush=True)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, COLS, lineterminator="\n")
        w.writeheader()
        for r, c, st, res in results:
            w.writerow({"id": r["id"], "url": r["url"], "kind": c["kind"], "repo": c["repo"], "pin": c["pin"], "path": c["path"],
                        "retrieved_utc": r["retrieved_utc"], "http_status": st, **res, "used_in": r.get("used_in", ""),
                        "outcome": "", "outcome_note": ""})
    counts = Counter(res["bucket"] for _, _, _, res in results)
    print("phase 1: " + ", ".join(f"{b}={counts[b]}" for b in BUCKETS) + f"; wrote {os.path.relpath(out, KB)}")
    return 0


# ---------------------------------------------------------------- record, confirm, sample, summary

def read_log(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_log(path, rows):
    kbcommon.write_csv(path, COLS, rows, atomic=True)


def cmd_record(a):
    rows = read_log(a.log)
    by_id = {r["id"]: r for r in rows}
    if a.from_json:
        with open(a.from_json, encoding="utf-8") as f:
            items = json.load(f)
    else:
        items = [{"id": a.id, "outcome": a.outcome, "note": a.note or ""}]
    bad = 0
    for it in items:
        if it.get("id") not in by_id or it.get("outcome") not in OUTCOMES:
            print(f"skipped {it!r}: unknown id or outcome (outcomes: {', '.join(OUTCOMES)})")
            bad += 1
            continue
        by_id[it["id"]]["outcome"] = it["outcome"]
        by_id[it["id"]]["outcome_note"] = (it.get("note") or "").replace("\n", " ")[:300]
    write_log(a.log, rows)
    print(f"recorded {len(items) - bad} outcome(s)" + (f", skipped {bad}" if bad else ""))
    return 1 if bad else 0


def confirmed(r):
    return (r["bucket"] == "OK" and not r["outcome"]) or r["outcome"] in ("confirmed", "updated")


SUFFIX = re.compile(r"(?:;\s*)?confirmed \d{4}-\d{2}-\d{2}: [^;]*$")


def cmd_confirm(a):
    date = a.date or today()
    log = {r["id"]: r for r in read_log(a.log)}
    srcs_text = kbcommon.read("_sources.csv", newline="", strict=True)
    reader = csv.DictReader(io.StringIO(srcs_text))
    header, rows = reader.fieldnames, list(reader)
    known = {r["id"] for r in rows}
    unknown = sorted(set(log) - known)
    if unknown:
        print(f"log ids not in _sources.csv: {', '.join(unknown[:10])}")
        return 1
    n_src = 0
    for r in rows:
        lr = log.get(r["id"])
        if not lr or not confirmed(lr):
            continue
        proof = (lr["proof"] or lr["outcome_note"] or lr["evidence"]).replace(";", ",")[:120]
        vod = SUFFIX.sub("", r["version_or_date"]).rstrip("; ")
        r["version_or_date"] = (vod + "; " if vod else "") + f"confirmed {date}: {proof}"
        r["retrieved_utc"] = date
        n_src += 1
    # confirmed by this census, or a row it added (phase 2 read those in full); a row merely retrieved on the same
    # day by other work, or left unconfirmed, does not count
    fresh = {sid for sid, lr in log.items() if confirmed(lr)} | {r["id"] for r in rows if r["id"] not in log and r["retrieved_utc"][:10] == date}
    articles = []
    for rel in build_index.content_files():
        if not rel.endswith(".md"):
            continue
        path = os.path.join(KB, rel)
        text = kbcommon.read(path, newline="", strict=True)
        fm = build_index.front_matter(text)
        if not fm or not fm.get("sources") or "retrieved_utc" not in fm:
            continue
        ids = kbid.SOURCE_ID.findall(str(fm["sources"]))
        if ids and all(i in fresh for i in ids) and str(fm["retrieved_utc"])[:10] != date:
            new = re.sub(r"(?m)^retrieved_utc:.*$", f"retrieved_utc: {date}", text, count=1)
            articles.append((path, new))
    state_path = os.path.join(KB, "_fetch_state.csv")
    state_cols = ["id", "url", "checked_utc", "fetched_utc", "changed_utc", "sha256", "text_sha256", "bytes", "error"]
    state = {}
    if os.path.exists(state_path):
        with open(state_path, encoding="utf-8", newline="") as f:
            state = {r["id"]: r for r in csv.DictReader(f)}
    stamp = f"{date}T00:00:00Z"
    urls = {r["id"]: r["url"] for r in rows}
    for sid, lr in log.items():
        if confirmed(lr):
            state[sid] = {**state.get(sid, {"id": sid}), "id": sid, "url": urls[sid], "checked_utc": stamp, "error": ""}
    print(f"confirm {date}: {n_src} source(s) confirmed, {len(fresh) - n_src} row(s) added by the census, {len(articles)} article(s) re-dated")
    if a.dry_run:
        print("dry run: nothing written")
        return 0
    kbcommon.write_csv(os.path.join(KB, "_sources.csv"), header, rows, atomic=True)
    for path, new in articles:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(new)
    kbcommon.write_csv(state_path, state_cols, sorted(state.values(), key=lambda r: kbid.sort_key(r["id"])), atomic=True)
    return 0


def cmd_sample(a):
    rows = read_log(a.log)
    rnd = random.Random(a.seed)
    changed = [r for r in rows if r["outcome"] in ("updated", "superseded", "gone")]
    ok = [r for r in rows if (r["bucket"] == "OK" and not r["outcome"]) or r["outcome"] == "confirmed"]
    pick = lambda xs, rate: rnd.sample(xs, min(len(xs), max(1, round(len(xs) * rate)))) if xs else []  # noqa: E731
    w = csv.writer(sys.stdout, lineterminator="\n")
    w.writerow(["group", "id", "url", "bucket", "outcome", "evidence", "outcome_note", "used_in"])
    for group, xs in (("changed", pick(changed, a.changed)), ("ok", pick(ok, a.ok))):
        for r in sorted(xs, key=lambda r: r["id"]):
            w.writerow([group, r["id"], r["url"], r["bucket"], r["outcome"], r["evidence"], r["outcome_note"], r["used_in"]])
    return 0


def cmd_summary(a):
    rows = read_log(a.log)
    b = Counter(r["bucket"] for r in rows)
    o = Counter(r["outcome"] or "-" for r in rows)
    nr = Counter(r["note"] or "-" for r in rows if r["bucket"] == "NEEDS-READING")
    print(f"sources={len(rows)} " + " ".join(f"{k}={b[k]}" for k in BUCKETS))
    print("outcomes: " + " ".join(f"{k}={v}" for k, v in sorted(o.items())))
    print("needs-reading by note: " + " ".join(f"{k}={v}" for k, v in sorted(nr.items())))
    print(f"confirmed (phase 3 would date): {sum(1 for r in rows if confirmed(r))}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="phases 0-1: a mechanical verdict per source, written to the census log")
    c.add_argument("--date", help="census date (default today)")
    c.add_argument("--out", help="log path (default _census/<date>.csv)")
    c.add_argument("--jobs", type=int, default=16, help="parallel checks (default 16)")
    c.add_argument("--source", action="append", default=[], help="only these source ids (repeatable)")
    r = sub.add_parser("record", help="phase 2: record what reading a source decided")
    r.add_argument("log")
    r.add_argument("--from", dest="from_json", help="JSON list of {id, outcome, note}")
    r.add_argument("--id")
    r.add_argument("--outcome", choices=OUTCOMES)
    r.add_argument("--note")
    f = sub.add_parser("confirm", help="phase 3: date the confirmed sources and the articles whose sources all are")
    f.add_argument("log")
    f.add_argument("--date", help="confirmation date (default today)")
    f.add_argument("--dry-run", action="store_true", help="report, write nothing")
    s = sub.add_parser("sample", help="phase 4: the ids an independent check re-reads, as CSV")
    s.add_argument("log")
    s.add_argument("--changed", type=float, default=0.10, help="fraction of the changed sources (default 0.10)")
    s.add_argument("--ok", type=float, default=0.05, help="fraction of the confirmed sources (default 0.05)")
    s.add_argument("--seed", type=int, default=1)
    m = sub.add_parser("summary", help="counts per bucket and outcome")
    m.add_argument("log")
    a = ap.parse_args()
    if a.cmd == "record" and not a.from_json and not (a.id and a.outcome):
        ap.error("record needs --from FILE, or --id and --outcome")
    sys.exit({"check": cmd_check, "record": cmd_record, "confirm": cmd_confirm, "sample": cmd_sample, "summary": cmd_summary}[a.cmd](a))


if __name__ == "__main__":
    main()
