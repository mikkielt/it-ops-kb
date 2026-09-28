#!/usr/bin/env python3
"""Knowledge providers: which documentation host serves a source, and its cheapest reliable change signal (stdlib only).

  provider.py [--root NAME] list                          the merged registry, one line per provider
  provider.py [--root NAME] show URL                      the provider row that serves URL, and the form fetched
  provider.py [--root NAME] probe NAME [--url URL] [--write] [--json]
                                                          live requests and deterministic checks of one provider;
                                                          --write stores the measured columns and probed_utc

Registry. _tools/providers.csv holds the public providers, shared by every root; a root may add its own
<root>/_providers.csv for internal providers (a team wiki, an internal git host). They are merged at read time: a root
row with the name of a shared row replaces it. A url is served by the row whose `match` prefix is the longest one
that starts the url (scheme dropped); the row with match `*` serves the rest.

Columns (one row per provider):
  provider        name (lowercase)
  match           space-separated url prefixes without scheme (`learn.microsoft.com/`), or `*`
  signals         the change signals fetch tools try, cheapest first, `;`-separated:
                    pin     the url is pinned (a commit or tag in the path): its text never changes; upstream moves are
                            a new source row (census.py compares the pin with the branch tip)
                    etag    a conditional GET with the stored ETag; 304 = unchanged
                    lastmod a conditional GET with the stored Last-Modified; 304 = unchanged
                    version the page's own version id (`version_meta`); the same id = unchanged
                    hash    sha256 of the normalized document text (always last)
  etag            none | stable | per-request (changes on every request) | weak (W/ prefix; stable)
  lastmod         none | stable (If-Modified-Since answers 304) | stable-no-304 | request-time (the header is the
                  time of the request: useless)
  version_meta    comma-separated keys read from the raw form's front matter or the HTML <meta> tags, first = the
                  content version (`git_commit_id,updated_at,document_id`), or `-`
  stable_id       the key of an id that survives moves and renames (`document_id`), or `-`
  raw_form        how the text is fetched: `-` (the url itself), `query:accept=text/markdown` (added query),
                  `suffix:.md` (added to the path), `header:text/markdown` (Accept header), `blob-to-raw` (a GitHub
                  or GitLab blob page read as the raw file at the same ref)
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
ETag and one with Last-Modified (304?), each raw form (text/markdown answer?), the version keys in the text, robots.txt
Sitemap lines, a made-up sibling url, and search_api with the page's title when the row has one. The other columns are
curated from the provider's documentation and kept. The `*` row serves many hosts: its probe records only probed_utc
and a note naming the sample host. Exit: 0 ok, 1 the sample could not be fetched, 2 bad arguments.

Library use (factdiff.py, census.py): providers(), for_url(), document() and doc_text().
"""
import argparse, datetime, email.utils, hashlib, json, os, random, re, ssl, string, sys, time, urllib.error
import urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kbcommon  # noqa: E402

SHARED = os.path.join(kbcommon.TOOLS, "providers.csv")
ROOT_FILE = "_providers.csv"
COLS = ["provider", "match", "signals", "etag", "lastmod", "version_meta", "stable_id", "raw_form", "sitemap",
        "sitemap_lastmod", "redirects", "history", "search_api", "mcp_freshness", "not_found", "rate_limit", "reuse",
        "probed_utc", "notes"]
MEASURED = ("signals", "etag", "lastmod", "version_meta", "raw_form", "sitemap", "not_found", "probed_utc")
SIGNALS = ("pin", "etag", "lastmod", "version", "hash")
UA = "it-ops-kb-fetch/1.0 (read-only change check)"
DELAY, TIMEOUT = 1.1, 30
VERSION_KEYS = ("git_commit_id", "updated_at", "document_id", "ms.date", "dateModified", "article:modified_time",
                "last-modified", "revised")
PINNED = re.compile(r"(?:^|/)(?:[0-9a-f]{40})(?:/|$)|/-/raw/v?\d+\.\d+|/releases/download/|raw\.githubusercontent\.com/[^/]+/[^/]+/"
                    r"(?:refs/tags/)?v?\d+\.\d+[^/]*/")
_last, _ctx = {}, [None]


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


def for_url(url, rows=None):
    """The provider row serving `url`: the longest matching prefix, else the `*` row, else None."""
    rows = providers() if rows is None else rows
    b, best, fallback = _bare(url), None, None
    for r in rows:
        for m in (r.get("match") or "").split():
            if m == "*":
                fallback = fallback or r
            elif b.startswith(m) and (best is None or len(m) > best[0]):
                best = (len(m), r)
    return best[1] if best else fallback


def is_pinned(url):
    """A url whose text cannot change: a commit sha or a release tag in its path."""
    return bool(PINNED.search(url))


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


def request(url, headers=None, limit=20_000_000, method="GET"):
    """{status, headers (lowercase keys), body (bytes), final, hops, error}; one request per DELAY seconds per host.
    Never raises for HTTP or network errors: status is the code, or 0 with `error`."""
    host = urllib.parse.urlsplit(url).netloc
    wait = DELAY - (time.time() - _last.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    _last[host] = time.time()
    chain = _Chain()
    opener = urllib.request.build_opener(chain, urllib.request.HTTPSHandler(context=ssl_ctx()))
    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA, "Accept": "*/*", **(headers or {})})
    out = {"status": 0, "headers": {}, "body": b"", "final": url, "hops": chain.hops, "error": ""}
    try:
        with opener.open(req, timeout=TIMEOUT) as r:
            out.update(status=r.status, headers={k.lower(): v for k, v in r.headers.items()}, body=r.read(limit), final=r.geturl())
    except urllib.error.HTTPError as e:
        out.update(status=e.code, headers={k.lower(): v for k, v in (e.headers or {}).items()}, final=e.geturl() or url)
        try:
            out["body"] = e.read(limit)
        except Exception:  # noqa: BLE001
            pass
    except Exception as e:  # noqa: BLE001 - a change check must never stop a run
        out["error"] = f"{type(e).__name__}: {str(getattr(e, 'reason', e))[:120]}"
    return out


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
        m = re.match(r"https://github\.com/([^/]+)/([^/]+)/blob/(.+)$", base)
        if m:
            return f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2)}/{m.group(3)}", {}
        return base.replace("/-/blob/", "/-/raw/"), {}
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
    """{key: value} of the version keys found in a raw form's front matter or an HTML page's <meta> tags."""
    fm = front_matter(text)
    out = {}
    for k in keys:
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
    if ("xml" in (ctype or "") or t.lstrip().startswith("<?xml")) and len(t) > 500 * (t.count("\n") + 1):
        return re.sub(r">\s*<", ">\n<", t)
    return t


def document(url, row=None, etag="", lastmod=""):
    """Fetch a source's document by its provider's raw form, conditionally when a validator is given.
    {status, final, hops, not_modified, etag, lastmod, version (dict), text, sha, bytes, error}."""
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
           "text": None, "sha": "", "bytes": len(r["body"]), "error": r["error"], "ctype": r["headers"].get("content-type", "")}
    if r["status"] == 200 and r["body"]:
        raw = r["body"].decode("utf-8", errors="replace")
        out["raw"] = raw if doc_text(r["body"], out["ctype"], rurl) is not None else None
        out["raw_url"] = rurl
        keys = [k for k in (row.get("version_meta") or "").split(",") if k.strip() and k != "-"]
        out["version"] = version_of(raw, keys)
        out["text"] = doc_text(r["body"], out["ctype"], rurl)
        out["sha"] = hashlib.sha256((out["text"] or "").encode() if out["text"] is not None else r["body"]).hexdigest()
    return out


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
    return urllib.parse.urlunsplit((u.scheme, u.netloc, f"{parent}/{junk}", "", ""))


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
        ok = r["status"] == 200 and len(r["body"]) > 200 and ("markdown" in ct or (form == "blob-to-raw" and "html" not in ct))
        ev.append(f"raw form {form}: {r['status'] or r['error']} {r['headers'].get('content-type', '')}")
        if ok:
            raw_forms.append((form, r))
    ctype = a["headers"].get("content-type", "")
    curated = [f for f in raw_forms if f[0] == row.get("raw_form")]  # the documented form wins when it works
    if curated or raw_forms:
        form, rr = (curated or raw_forms)[0]
    elif row.get("raw_form") == "blob-to-raw" or "html" not in ctype:
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
    keys = version_of(raw, VERSION_KEYS)
    order = [k for k in ("git_commit_id", "updated_at", "document_id", "dateModified", "article:modified_time", "ms.date",
                         "last-modified", "revised") if k in keys]
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
        ok = s["status"] == 200 and s["body"][:1] in (b"{", b"[")
        ev.append(f"search_api {q!r}: {s['status']}" + (", lastUpdatedDate present" if b"lastUpdatedDate" in s["body"] else ""))
        if not ok:
            found["notes_search"] = f"search_api answered {s['status']}"
    pin = is_pinned(url) or "pin" in (row.get("signals") or "").split(";")  # pin is a url pattern, kept from the row
    sig = (["pin"] if pin else []) + (["etag"] if etag_ok else []) + (["lastmod"] if lm_ok else []) \
        + (["version"] if order and order[0] in ("git_commit_id", "updated_at", "dateModified", "article:modified_time") else []) + ["hash"]
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
    a = ap.parse_args()
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
