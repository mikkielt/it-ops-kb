"""The leak scan: tracked files hold no secret, authored files hold placeholders only, and the scan the push guards
run (kbpublic.file_hits) reports each kind of planted leak. The planted values are assembled at run time, so this
file holds none of them whole. The patterns are the production ones (kbcommon); none is kept here."""
import csv, functools, json, os, re, subprocess, sys

import kbcommon
import kbpublic
from conftest import TOOLS, text, tracked

def planted():
    """One leak of each kind, built from parts."""
    return {
        "secret": "gh" + "p_" + "a" * 36,
        "home": "/".join(("", "Users", "realperson", "docs")),
        "ip": ".".join(("10", "77", "88", "99")),
        "email": "@".join(("real.person", "corp-mail.net")),
        "guid": "-".join(("1a2b3c4d", "5e6f", "7a8b", "9c0d", "1e2f3a4b5c6d")),
    }


def allowlist():
    return kbpublic.parse_allowlist(text(kbpublic.ALLOWLIST_PATH) or "")


def pinned():
    out = set()
    for r in kbcommon.roots():
        with open(os.path.join(r.path, kbcommon.ARTIFACTS), encoding="utf-8-sig", newline="") as f:
            out |= {kbcommon.repo_rel(x["path"], r.path) for x in csv.DictReader(f)}
    return out


@functools.lru_cache(maxsize=None)
def scan():
    """[(file, kind, value)] the tracked files hold, as the push guards read them (kbpublic.file_hits) with the
    reviewed allowlist. Vendor exports, snapshots, pinned artifacts and the query log store are read for secrets only
    and files of internal roots are left out of the placeholders rule. One pass over the text finds the files that
    may hold a hit; file_hits then gives the verdict, so the test and the guards agree."""
    allow, pins = allowlist(), pinned()
    internal = tuple(kbcommon.repo_rel(".", r.path) + "/" for r in kbcommon.roots() if r.visibility != "public")
    secrets = re.compile(kbcommon.secrets_rx())
    out = []
    for f in tracked():
        t = text(f)
        if t is None:
            continue
        vendored = f in pins or "/artifacts/" in f or f"/{kbcommon.SNAPSHOTS}/" in f or f.startswith("kb/_querylog/")
        if vendored:
            if not secrets.search(t):
                continue
        elif not kbcommon.leak_hits(t, allow):
            continue
        out += [(f, k, v) for k, v in kbpublic.file_hits(f, t, allow, pins) if k == "secret" or not f.startswith(internal)]
    return out


def test_tracked_files_hold_no_secret():
    found = [h for h in scan() if h[1] == "secret"]
    assert not found, "possible secrets (file only):\n" + "\n".join(f"  {f}" for f, _, _ in found[:20])


def test_authored_files_hold_placeholders_only():
    found = [h for h in scan() if h[1] != "secret"]
    assert not found, "real-looking values (placeholders only, or allowlist with a reason):\n" + "\n".join(
        f"  {f}: {k} {v}" for f, k, v in found[:20])


def test_scan_reports_each_planted_leak_and_honours_the_allowlist():
    values = planted()
    for kind, value in values.items():
        assert kind in [k for k, _ in kbpublic.file_hits("notes.md", f"see {value} here", {})], kind
    # the placeholders pass, an allowlisted value passes
    ok = "jan.kowalski t@example.com 00000000-0000-0000-0000-000000000000 192.0.2.7"
    assert kbpublic.file_hits("notes.md", ok, {}) == []
    allow = kbpublic.parse_allowlist("\n".join(f"{k} {v}  # reviewed" for k, v in values.items() if k != "home"))
    assert [k for k, _ in kbpublic.file_hits("notes.md", " ".join(values.values()), allow)] == ["home"]
    # vendor exports are read for secrets only
    assert [k for k, _ in kbpublic.file_hits("kb/x/artifacts/a.txt", " ".join(values.values()), {})] == ["secret"]


def test_backlog_check_refuses_leak_in_item_text(tmp_path):
    def backlog(*args):
        p = subprocess.run([sys.executable, os.path.join(TOOLS, "backlog.py"), "--root", str(tmp_path), *args],
                           cwd=tmp_path, capture_output=True, text=True, encoding="utf-8")
        return p.returncode, p.stdout + p.stderr

    assert backlog("new", "epic", "--title", "Epic", "--goal", "outcome")[0] == 0
    assert backlog("check")[0] == 0
    (path,) = tmp_path.rglob("EP-*.json")
    item = json.loads(path.read_text(encoding="utf-8"))
    value = planted()["ip"]
    item["goal"] = f"see {value} here"
    path.write_text(json.dumps(item, indent=2) + "\n", encoding="utf-8", newline="\n")
    code, out = backlog("check")
    assert code == 1 and "field goal has a leak-scan hit (ip" in out and value not in out, out
