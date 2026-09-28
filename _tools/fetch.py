#!/usr/bin/env python3
"""Re-download and verify every kb artifact (stdlib only).

Inputs (paths relative to the root, see Roots):
  _sources.csv    id,url,title,publisher,licence,reuse,retrieved_utc,version_or_date,artifact_sha256,used_in,superseded_by
                  A row with artifact_sha256 is an artifact source: the bytes at `url` must hash to it.
  _artifacts.csv  path,source_id,sha256,zip_member
                  A local file in the repository, where it came from, and its own sha256. With zip_member, the file
                  was extracted from the zip at the source's url. Without, it is a copy or an excerpt.

Modes:
  --verify    download every artifact source (1 request / 1.1 s per host), compare sha256; check every
              local artifact's sha256 on disk; for zip members, compare the member bytes too.
              Nothing is written. Exit 1 on any mismatch or failed download.
  --refresh   like --verify, but (re)write local files whose source is a verbatim copy or a zip member.
              Excerpts (local sha differs from source sha, no zip_member) are only reported.
  --offline   check local files only (no network).
  --diff      fetch the selected sources (any source, not only artifacts), compare each with its previous
              fetch and record the fetch date. Default output is a summary per source (partial diff); --full
              adds a unified diff of the page text, --max-lines N caps it per source. Exit 0 = no change,
              1 = something changed, 2 = a fetch failed (as diff(1)).
  --status    offline: when each selected source was last fetched, last changed, and its last error.

Roots: every path above is relative to a root (kb/<root>/). --root NAME picks one of this repository's roots;
without it --diff and --status work on the public root, and --verify, --refresh and --offline on every root with
artifacts (their output names a non-public root's files `<root>/<path>`).

Selection (for --diff and --status; repeatable, combined as a union; none = every source):
  --topic auth/kerberos     sources cited by the topic's files (per _coverage.csv) or listed in their used_in
  --dir auth                ... by every .md/.csv under a directory
  --file auth/kerberos.md   ... by one file
  --source S1208            one source id (legacy S1208 or hash id S-k3f7q2zd)
  --older-than DAYS         then keep only sources not fetched within DAYS (never-fetched included)

State: _fetch_state.csv (committed) keeps per source the last check, last successful fetch, last change,
sha256 of the bytes and of the normalized text. _cache/snapshots/<id>.txt (not committed) keeps the
normalized text of the last fetch, so --full can show what changed; without a snapshot, a change is still
detected from the stored hash. The first fetch of a source is `new`; if its _sources.csv row recorded a
"sha256 at retrieval <hash>", that hash is the baseline. --no-save leaves state and snapshots untouched.
HTML is reduced to the text of <main> (or the whole body) before hashing, so page chrome does not count.

A failed download is reported as `unknown`, never as a match.

Every request writes one query log spool row (kb/_self/querylog.md, Capture): host, path and outcome class, never the
query string or the body.
"""
import argparse, datetime, difflib, hashlib, html.parser, io, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request, zipfile
import kbcommon, kbid, querylog

KB = kbcommon.PUBLIC  # the root being checked (--root; the public root by default); the cache stays in the repository
STATE = "_fetch_state.csv"
STATE_COLS = kbcommon.STATE_COLS
SNAPSHOTS = os.path.join(kbcommon.HOME, "_cache", "snapshots")
DELAY, TIMEOUT = 1.1, 180
_last = {}


def fetch(url):
    """(bytes, content-type) of `url`, at most one request per DELAY seconds per host."""
    if urllib.parse.urlparse(url).scheme not in ("http", "https"):
        raise ValueError(f"not an http(s) url: {url}")
    host = urllib.parse.urlparse(url).hostname
    wait = DELAY - (time.time() - _last.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    _last[host] = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": "it-ops-kb-fetch/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read()
            querylog.record_request(url, querylog.request_outcome(r.status, None, len(body), url, r.geturl()),
                                    body)
            return body, r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        querylog.record_request(url, f"http-{e.code}")
        raise
    except Exception:
        querylog.record_request(url, "error")
        raise


def get(url):
    return fetch(url)[0]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def read_csv(name, required):
    """Rows of a kb index CSV; exit 1 if it is missing or lacks a required column (never a silent pass)."""
    try:
        return kbcommon.load_csv(os.path.join(KB, name), required)[1]
    except kbcommon.CsvError as e:
        sys.exit(str(e))


def repo_roots():
    """The roots in this repository's kb/ (KB_ROOTS roots are other repositories' to fetch)."""
    kbd = os.path.realpath(kbcommon.KB_DIR)
    return [r for r in kbcommon.roots() if os.path.dirname(os.path.realpath(r.path)) == kbd]


class _PageText(html.parser.HTMLParser):
    """Visible text of an HTML page, one block per line; <main> only when the page has one. `headings` starts each
    h1-h6 line with Markdown `#` marks (provider.py's document text; the hash text of --diff has none)."""
    SKIP = {"script", "style", "noscript", "svg", "template", "head", "nav", "footer", "button", "form", "aside"}
    BLOCK = {"p", "div", "li", "tr", "br", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "table", "section", "article", "dd", "dt"}

    def __init__(self, headings=False):
        super().__init__(convert_charrefs=True)
        self.skip = self.main = 0
        self.headings = headings
        self.all, self.in_main, self.saw_main = [], [], False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag == "main":
            self.main += 1
            self.saw_main = True
        if tag in self.BLOCK:
            self._emit("\n")
        if self.headings and not self.skip and re.fullmatch(r"h[1-6]", tag):
            self._emit("#" * int(tag[1]) + " ")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        elif tag == "main" and self.main:
            self.main -= 1
        if tag in self.BLOCK:
            self._emit("\n")

    def handle_data(self, data):
        if not self.skip:
            self._emit(data)

    def _emit(self, t):
        self.all.append(t)
        if self.main:
            self.in_main.append(t)

    def text(self):
        raw = "".join(self.in_main if self.saw_main else self.all)
        return "\n".join(ln for ln in (" ".join(x.split()) for x in raw.splitlines()) if ln)


def to_text(body, ctype):
    """Normalized text for diffing, or None for binary content (zip, pdf, images)."""
    head = body[:1024]
    if b"\0" in head or re.search(r"zip|pdf|octet-stream|image/", ctype or ""):
        return None
    t = body.decode("utf-8", errors="replace")
    if "html" in (ctype or "") or head.lstrip()[:15].lower().startswith((b"<!doctype html", b"<html")):
        p = _PageText()
        p.feed(t)
        text = p.text()
        if len(text) < 500:  # client-rendered page: the content sits in JSON <script> blocks
            text = "\n".join(filter(None, [text, _json_text(t)]))
        return text + "\n"
    return t.replace("\r\n", "\n")


def _json_text(page):
    """Long strings from a page's JSON <script> blocks (e.g. Next.js __NEXT_DATA__), HTML reduced to text."""
    out, seen = [], set()

    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, str) and len(x) > 200 and x not in seen:
            seen.add(x)
            if "<" in x:
                p = _PageText()
                p.feed(x)
                x = html.unescape(p.text()).replace("\xa0", " ")
            if len(x) > 200:
                out.append(x)
    for m in re.finditer(r"<script[^>]*type=[\"']application/(?:ld\+)?json[\"'][^>]*>(.*?)</script>", page, re.S | re.I):
        try:
            walk(json.loads(m.group(1)))
        except ValueError:
            pass
    return "\n".join(out)


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_state():
    p = os.path.join(KB, STATE)
    if not os.path.exists(p):
        return {}
    return {r["id"]: r for r in read_csv(STATE, ("id", "fetched_utc"))}


def write_state(state):
    kbcommon.write_csv(os.path.join(KB, STATE), STATE_COLS, sorted(
        state.values(), key=lambda r: kbid.sort_key(r["id"]) if kbid.is_source_id(r["id"]) else (2, 0, r["id"])), atomic=True)


def snapshot(sid, text=None):
    """Read (text=None) or write the normalized text snapshot of a source."""
    p = os.path.join(KB, SNAPSHOTS, f"{sid}.txt")
    if text is None:
        try:
            with open(p, encoding="utf-8") as f:
                return f.read()
        except OSError:
            return None
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def select(a, sources, state):
    """Source ids chosen by --topic/--dir/--file/--source (union; none = all), then filtered by --older-than."""
    files, ids = set(), set()
    cov = {r["topic"]: r for r in read_csv("_coverage.csv", ("topic", "files"))} if a.topic else {}
    for t in a.topic:
        t = t.strip("/").removesuffix(".md")
        fs = [f for f in (cov[t]["files"].split(";") if t in cov else [t + ".md"]) if f]
        found = [f for f in fs if os.path.isfile(os.path.join(KB, f))]
        if not found:
            sys.exit(f"no topic {t!r} (not in _coverage.csv and no {t}.md)")
        files.update(found)
    for d in a.dir:
        d = os.path.normpath(d)
        if not os.path.isdir(os.path.join(KB, d)):
            sys.exit(f"no directory {d!r}")
        for root, _, fs in os.walk(os.path.join(KB, d)):
            files.update(os.path.relpath(os.path.join(root, f), KB) for f in fs if f.endswith((".md", ".csv")))
    for f in a.file:
        f = os.path.normpath(f)
        if not os.path.isfile(os.path.join(KB, f)):
            sys.exit(f"no file {f!r}")
        files.add(f)
    for f in files:
        with open(os.path.join(KB, f), encoding="utf-8", errors="replace") as fh:
            ids.update(kbid.SOURCE_ID.findall(fh.read()))
        ids.update(sid for sid, r in sources.items() if f in (r.get("used_in") or "").split(";"))
    for sid in a.source:
        if kbid.canonical_id(sid) not in sources:
            sys.exit(f"unknown source id {sid!r}")
        ids.add(kbid.canonical_id(sid))
    chosen = [sid for sid in sources if sid in ids] if (files or a.source) else list(sources)
    if a.older_than is not None:
        cut = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=a.older_than)).strftime("%Y-%m-%dT%H:%M:%SZ")
        chosen = [sid for sid in chosen if (state.get(sid, {}).get("fetched_utc") or "") < cut]
    return chosen


def diff_sources(a, sources):
    state = read_state()
    chosen = select(a, sources, state)
    results, stamp = [], now_utc()
    for sid in chosen:
        src, prev = sources[sid], state.get(sid)
        if prev and prev.get("url") != src["url"]:
            prev = None  # the source now points elsewhere: start a new baseline
        res = {"id": sid, "url": src["url"], "used_in": [f for f in (src.get("used_in") or "").split(";") if f],
               "previous_fetched_utc": (prev or {}).get("fetched_utc") or None, "fetched_utc": None,
               "status": None, "added": 0, "removed": 0}
        try:
            body, ctype = fetch(src["url"])
        except Exception as e:  # noqa: BLE001
            res.update(status="error", error=str(e)[:300])
            if not a.no_save:
                state[sid] = {**(prev or {"id": sid, "url": src["url"]}), "checked_utc": stamp, "error": str(e)[:300]}
            results.append(res)
            continue
        text = to_text(body, ctype)
        raw_sha, text_sha = sha(body), sha(text.encode("utf-8")) if text is not None else sha(body)
        res["fetched_utc"] = stamp
        old = snapshot(sid) if prev else None
        if prev and prev.get("text_sha256"):
            res["status"] = "unchanged" if prev["text_sha256"] == text_sha else "changed"
        else:
            m = re.search(r"sha256 at retrieval ([0-9a-f]{64})", src.get("version_or_date") or "")
            want = (src.get("artifact_sha256") or "").strip().lower() or (m.group(1) if m else "")
            res["status"] = "new" if not want else ("unchanged" if want == raw_sha else "changed")
            res["baseline"] = "_sources.csv hash" if want else None
        if res["status"] == "changed" and text is not None:
            if old is None:
                res["diff_unavailable"] = "no earlier snapshot in _cache/snapshots"
            else:
                lines = list(difflib.unified_diff(old.splitlines(), text.splitlines(), f"{sid}@{res['previous_fetched_utc']}",
                                                  f"{sid}@{stamp}", n=a.context, lineterm=""))
                res["added"] = sum(1 for ln in lines if ln.startswith("+") and not ln.startswith("+++"))
                res["removed"] = sum(1 for ln in lines if ln.startswith("-") and not ln.startswith("---"))
                if a.full:
                    res["diff"] = lines[:a.max_lines] if a.max_lines else lines
                    res["diff_truncated"] = bool(a.max_lines and len(lines) > a.max_lines)
        if not a.no_save:
            changed = res["status"] in ("changed", "new") or not prev
            state[sid] = {**(prev or {}), "id": sid, "url": src["url"], "checked_utc": stamp, "fetched_utc": stamp,
                          "changed_utc": stamp if changed else prev.get("changed_utc", stamp),
                          "sha256": raw_sha, "text_sha256": text_sha, "bytes": len(body), "error": ""}
            if text is not None:
                snapshot(sid, text)
        results.append(res)
    if not a.no_save and chosen:
        write_state(state)
    counts = {k: sum(1 for r in results if r["status"] == k) for k in ("new", "unchanged", "changed", "error")}
    if a.json:
        print(json.dumps({"fetched_utc": stamp, "selected": len(chosen), **counts, "sources": results}, indent=1))
    else:
        for r in results:
            extra = f"+{r['added']} -{r['removed']}" if r["status"] == "changed" and "diff_unavailable" not in r else r.get("error") or r.get("diff_unavailable") or ""
            print(f"{r['status'].upper():<9} {r['id']:<10} {r['previous_fetched_utc'] or 'never':<20} {extra:<14} {r['url']}")
            for ln in r.get("diff", []):
                print("    " + ln)
            if r.get("diff_truncated"):
                print(f"    ... (diff cut at --max-lines {a.max_lines})")
        print(f"selected={len(chosen)} " + " ".join(f"{k}={v}" for k, v in counts.items()) + ("" if not a.no_save else " (not saved)"))
    sys.exit(2 if counts["error"] else 1 if counts["changed"] else 0)


def status(a, sources):
    state = read_state()
    now = datetime.datetime.now(datetime.timezone.utc)
    out = []
    for sid in select(a, sources, state):
        st = state.get(sid, {})
        age = None
        if st.get("fetched_utc"):
            age = (now - datetime.datetime.strptime(st["fetched_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)).days
        out.append({"id": sid, "url": sources[sid]["url"], "fetched_utc": st.get("fetched_utc") or None, "age_days": age,
                    "changed_utc": st.get("changed_utc") or None, "checked_utc": st.get("checked_utc") or None,
                    "error": st.get("error") or None, "retrieved_utc": sources[sid].get("retrieved_utc")})
    if a.json:
        return print(json.dumps(out, indent=1))
    for r in out:
        print(f"{r['id']:<10} fetched {r['fetched_utc'] or 'never':<20} changed {r['changed_utc'] or '-':<20} "
              f"{'age ' + str(r['age_days']) + 'd' if r['age_days'] is not None else '':<9} {('ERROR ' + r['error']) if r['error'] else ''}")
    print(f"selected={len(out)} never_fetched={sum(1 for r in out if not r['fetched_utc'])} with_error={sum(1 for r in out if r['error'])}")


def main():
    global DELAY, TIMEOUT
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--verify", action="store_true")
    g.add_argument("--refresh", action="store_true")
    g.add_argument("--offline", action="store_true")
    g.add_argument("--diff", action="store_true", help="fetch selected sources and compare with their previous fetch")
    g.add_argument("--status", action="store_true", help="offline: last fetch/change dates of selected sources")
    sel = ap.add_argument_group("selection (--diff, --status)")
    sel.add_argument("--topic", action="append", default=[])
    sel.add_argument("--dir", action="append", default=[])
    sel.add_argument("--file", action="append", default=[])
    sel.add_argument("--source", action="append", default=[])
    sel.add_argument("--older-than", type=float, metavar="DAYS")
    out = ap.add_argument_group("output (--diff)")
    out.add_argument("--full", action="store_true", help="include the unified diff of each changed source")
    out.add_argument("--max-lines", type=int, default=0, metavar="N", help="cap each diff at N lines (0 = no cap)")
    out.add_argument("--context", type=int, default=3, metavar="N", help="context lines around each change (default 3)")
    out.add_argument("--no-save", action="store_true", help="do not update _fetch_state.csv or snapshots")
    out.add_argument("--json", action="store_true", help="machine output (--diff, --status)")
    ap.add_argument("--delay", type=float, default=DELAY, help="seconds between requests to one host (default 1.1)")
    ap.add_argument("--timeout", type=float, default=30, help="per-request timeout in seconds for --diff (default 30)")
    ap.add_argument("--root", metavar="NAME", help="the root to work on (default: public for --diff/--status, every "
                                                   "root with artifacts for --verify/--refresh/--offline)")
    a = ap.parse_args()
    DELAY = max(a.delay, 0)
    if (a.topic or a.dir or a.file or a.source or a.older_than is not None) and not (a.diff or a.status):
        ap.error("--topic/--dir/--file/--source/--older-than need --diff or --status")
    try:
        roots = repo_roots()
    except kbcommon.RootError as e:
        sys.exit(str(e))
    if a.root:
        roots = [r for r in roots if r.name == a.root]
        if not roots:
            ap.error(f"--root {a.root}: no such root in {kbcommon.repo_rel(kbcommon.KB_DIR)}/")
    if a.diff or a.status:
        TIMEOUT = a.timeout
        use_root(roots[0])
        try:  # a usage or input error is exit 2 here, so it cannot be mistaken for exit 1 = "changed"
            sources = {r["id"]: r for r in read_csv("_sources.csv", ("id", "url"))}
            return diff_sources(a, sources) if a.diff else status(a, sources)
        except SystemExit as e:
            if isinstance(e.code, str):
                print(e.code, file=sys.stderr)
                sys.exit(2)
            raise
    total = [0, 0, 0, 0, 0]  # ok, fails, unknown, sources with sha, artifacts
    for r in roots:
        use_root(r)
        if not a.root and r.name != "public" and not os.path.exists(os.path.join(KB, "_artifacts.csv")):
            continue  # a team root without artifacts has nothing to verify; the public root must have its list
        for i, n in enumerate(verify_root(a, "" if r.name == "public" else r.name + "/")):
            total[i] += n
    if not total[4]:
        sys.exit("_artifacts.csv lists no artifacts; nothing to verify")
    ok, fails, unknown, with_sha, n_arts = total
    print(f"ok={ok} mismatch={fails} unknown={unknown} sources_with_sha={with_sha} artifacts={n_arts}")
    sys.exit(1 if fails or unknown else 0)


def use_root(r):
    global KB
    KB = r.path


def verify_root(a, shown):
    """--verify/--refresh/--offline of the current root: (ok, fails, unknown, sources with sha, artifacts). `shown`
    prefixes the paths it prints (a non-public root's name)."""
    sources = {r["id"]: r for r in read_csv("_sources.csv", ("id", "url", "artifact_sha256"))}
    arts = read_csv("_artifacts.csv", ("path", "source_id", "sha256"))
    fails = unknown = ok = 0
    blobs = {}

    if not a.offline:
        for sid, r in sources.items():
            want = (r.get("artifact_sha256") or "").strip().lower()
            if not want:
                continue
            try:
                b = get(r["url"])
            except Exception as e:  # noqa: BLE001
                print(f"UNKNOWN {sid} {r['url']}: {e}")
                unknown += 1
                continue
            got = sha(b)
            if got == want:
                ok += 1
                blobs[sid] = b
            else:
                print(f"MISMATCH {sid} {r['url']}: want {want[:12]} got {got[:12]}")
                fails += 1

    for r in arts:
        path = os.path.join(KB, r["path"])
        name = shown + r["path"]
        want = r["sha256"].strip().lower()
        sid, member = r["source_id"], (r.get("zip_member") or "").strip()
        src = sources.get(sid)
        if src is None:
            print(f"NOSOURCE {name}: {sid} not in _sources.csv")
            fails += 1
            continue
        fresh = None
        if sid in blobs:
            b = blobs[sid]
            if member:
                try:
                    fresh = zipfile.ZipFile(io.BytesIO(b)).read(member)
                except KeyError:
                    print(f"MISMATCH {name}: {member} not in zip {sid}")
                    fails += 1
                    continue
            elif sha(b) == want:
                fresh = b
        if fresh is not None and sha(fresh) != want:
            print(f"MISMATCH {name}: upstream member differs from recorded sha256")
            fails += 1
            continue
        if a.refresh and fresh is not None:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(fresh)
        if not os.path.isfile(path):
            print(f"MISSING {name}" + (" (is a directory)" if os.path.isdir(path) else ""))
            fails += 1
            continue
        try:
            with open(path, "rb") as f:
                got = sha(f.read())
        except OSError as e:
            print(f"UNREADABLE {name}: {e.strerror}")
            fails += 1
            continue
        if got != want:
            print(f"MISMATCH {name}: local file changed ({got[:12]} vs {want[:12]})")
            fails += 1
        else:
            ok += 1
    return ok, fails, unknown, sum(1 for r in sources.values() if r.get("artifact_sha256")), len(arts)


if __name__ == "__main__":
    main()
