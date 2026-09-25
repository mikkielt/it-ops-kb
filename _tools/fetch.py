#!/usr/bin/env python3
"""Re-download and verify every kb artifact (stdlib only).

Inputs (paths relative to kb/):
  _sources.csv    id,url,title,publisher,licence,retrieved_utc,version_or_date,artifact_sha256,used_in
                  A row with artifact_sha256 is an artifact source: the bytes at `url` must hash to it.
  _artifacts.csv  path,source_id,sha256,zip_member
                  A local file in kb/, where it came from, and its own sha256. With zip_member, the file
                  was extracted from the zip at the source's url. Without, it is a copy or an excerpt.

Modes:
  --verify    download every artifact source (1 request / 1.1 s per host), compare sha256; check every
              local artifact's sha256 on disk; for zip members, compare the member bytes too.
              Nothing is written. Exit 1 on any mismatch or failed download.
  --refresh   like --verify, but (re)write local files whose source is a verbatim copy or a zip member.
              Excerpts (local sha differs from source sha, no zip_member) are only reported.
  --offline   check local files only (no network).

A failed download is reported as `unknown`, never as a match.
"""
import argparse, csv, hashlib, io, os, sys, time, urllib.parse, urllib.request, zipfile

KB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_last = {}


def get(url):
    host = urllib.parse.urlparse(url).hostname
    wait = 1.1 - (time.time() - _last.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    _last[host] = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": "it-ops-kb-fetch/1.0"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def sha(b):
    return hashlib.sha256(b).hexdigest()


def read_csv(name):
    p = os.path.join(KB, name)
    if not os.path.exists(p):
        return []
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--verify", action="store_true")
    g.add_argument("--refresh", action="store_true")
    g.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    sources = {r["id"]: r for r in read_csv("_sources.csv")}
    arts = read_csv("_artifacts.csv")
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
        want = r["sha256"].strip().lower()
        sid, member = r["source_id"], (r.get("zip_member") or "").strip()
        src = sources.get(sid)
        if src is None:
            print(f"NOSOURCE {r['path']}: {sid} not in _sources.csv")
            fails += 1
            continue
        fresh = None
        if sid in blobs:
            b = blobs[sid]
            if member:
                try:
                    fresh = zipfile.ZipFile(io.BytesIO(b)).read(member)
                except KeyError:
                    print(f"MISMATCH {r['path']}: {member} not in zip {sid}")
                    fails += 1
                    continue
            elif sha(b) == want:
                fresh = b
        if fresh is not None and sha(fresh) != want:
            print(f"MISMATCH {r['path']}: upstream member differs from recorded sha256")
            fails += 1
            continue
        if a.refresh and fresh is not None:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(fresh)
        if not os.path.exists(path):
            print(f"MISSING {r['path']}")
            fails += 1
            continue
        with open(path, "rb") as f:
            got = sha(f.read())
        if got != want:
            print(f"MISMATCH {r['path']}: local file changed ({got[:12]} vs {want[:12]})")
            fails += 1
        else:
            ok += 1

    print(f"ok={ok} mismatch={fails} unknown={unknown} sources_with_sha={sum(1 for r in sources.values() if r.get('artifact_sha256'))} artifacts={len(arts)}")
    sys.exit(1 if fails or unknown else 0)


if __name__ == "__main__":
    main()
