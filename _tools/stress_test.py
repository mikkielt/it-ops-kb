#!/usr/bin/env python3
"""Stress and robustness tests for the kb tools (stdlib only). Exit 1 on any failure.

  stress_test.py                 run every case (about 45 s)
  stress_test.py --scale 20      also search a corpus copied 20 times (default 5)
  stress_test.py -k search       run only cases whose name contains "search"

Every case runs against a throwaway copy of the kb in a temporary directory; the kb itself is never
modified. A case fails if the tool's exit code is not the expected one, if its output misses an expected
string, or if it prints a Python traceback (a crash is never an acceptable way to report bad input).
"""
import argparse, concurrent.futures as cf, csv, functools, http.server, io, json, os, random, shutil, subprocess, sys, tempfile, threading, time

KB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TIMEOUT = 300
results = []


def copy_kb(tmp, name):
    d = os.path.join(tmp, name)
    shutil.copytree(KB, d, ignore=shutil.ignore_patterns(".git", "__pycache__"), symlinks=True)
    return d


def run(kb, tool, *args):
    t = time.perf_counter()
    p = subprocess.run([sys.executable, os.path.join(kb, "_tools", tool), *args],
                       capture_output=True, text=True, errors="replace", timeout=TIMEOUT)
    return p.returncode, p.stdout, p.stderr, time.perf_counter() - t


def case(name, kb, tool, args, rc, expect="", check=None):
    """Run one tool call and record PASS/FAIL. `expect` must appear in stdout+stderr; `check(stdout)` must be true."""
    if FILTER and FILTER not in name:
        return None
    try:
        got, out, err, dt = run(kb, tool, *args)
    except subprocess.TimeoutExpired:
        results.append((False, name, f"timeout after {TIMEOUT} s"))
        return None
    why = []
    if "Traceback (most recent call last)" in err:
        why.append("crashed: " + err.strip().splitlines()[-1][:120])
    if got not in (rc if isinstance(rc, tuple) else (rc,)):
        why.append(f"exit {got}, want {rc}")
    if expect and expect not in out + err:
        why.append(f"output lacks {expect!r}")
    if check and not why:
        try:
            if not check(out):
                why.append("output check failed")
        except Exception as e:  # noqa: BLE001
            why.append(f"output check raised {type(e).__name__}")
    results.append((not why, name, "; ".join(why) or f"{dt * 1000:.0f} ms"))
    return out


def write(kb, rel, data):
    p = os.path.join(kb, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb" if isinstance(data, bytes) else "w", **({} if isinstance(data, bytes) else {"encoding": "utf-8"})) as f:
        f.write(data)


def read(kb, rel):
    with open(os.path.join(kb, rel), encoding="utf-8") as f:
        return f.read()


def is_json(out):
    json.loads(out)
    return True


def main():
    global FILTER
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scale", type=int, default=5, help="corpus multiplier for the scaling case (default 5)")
    ap.add_argument("-k", dest="filter", default="", help="run only cases whose name contains this text")
    a = ap.parse_args()
    FILTER = a.filter
    random.seed(7)

    with tempfile.TemporaryDirectory(prefix="kb-stress-") as tmp:
        base = copy_kb(tmp, "base")

        # 1. the pristine kb passes every tool
        case("baseline check.py", base, "check.py", [], 0)
        case("baseline fetch.py --offline", base, "fetch.py", ["--offline"], 0)
        case("baseline rag topics", base, "rag.py", ["topics"], 0)
        case("baseline rag search -u", base, "rag.py", ["search", "kerberos", "-u"], 0, "->")
        case("baseline rag src", base, "rag.py", ["src", "S100"], 0, "S100")
        case("baseline rag show", base, "rag.py", ["show", "README.md:1", "-n", "3"], 0, "it-ops-kb")

        # 2. hostile arguments
        vocab = [w for w in read(base, "README.md").lower().split() if w.isalpha() and len(w) > 3]
        case("search 10k-word query", base, "rag.py", ["search", " ".join(random.choices(vocab, k=10000))], 0)
        case("search 120k-char single token", base, "rag.py", ["search", "a" * 120000], 1, "no match")  # Linux caps one argv string at 128 KiB
        case("search regex and shell characters", base, "rag.py", ["search", r".*[](){}^$|\?+ %s %n ' \" ; rm -rf /"], (0, 1))
        case("search unicode, emoji, RTL, zero-width", base, "rag.py", ["search", "zażółć 🔐 ключ 密钥 ‮kerberos​"], (0, 1))
        case("search -k 0 rejected", base, "rag.py", ["search", "kerberos", "-k", "0"], 2, "must be >= 1")
        case("search -k -5 rejected", base, "rag.py", ["search", "kerberos", "-k", "-5"], 2, "must be >= 1")
        case("search -k abc rejected", base, "rag.py", ["search", "kerberos", "-k", "abc"], 2)
        case("search -k 10000000 --json -u", base, "rag.py", ["--json", "search", "the", "-k", "10000000", "-u"], 0, check=is_json)
        case("search -d ../..", base, "rag.py", ["search", "kerberos", "-d", "../.."], 1, "no match")
        case("src 5000 ids", base, "rag.py", ["src", *[f"S{i}" for i in range(5000)]], 0)
        case("src junk ids", base, "rag.py", ["src", "'; DROP TABLE", "S", "S-1", "s0100"], 0, "UNKNOWN id")
        case("show -n 100000000", base, "rag.py", ["show", "_answers.md", "-n", "100000000"], 0)
        case("show line 0", base, "rag.py", ["show", "README.md:0", "-n", "1"], 0)
        case("show line -5 rejected", base, "rag.py", ["show", "README.md:-5"], 1, "positive number")
        case("show line abc rejected", base, "rag.py", ["show", "README.md:abc"], 1, "positive number")
        case("show -n -1 rejected", base, "rag.py", ["show", "README.md", "-n", "-1"], 2, "must be >= 1")
        case("show missing file", base, "rag.py", ["show", "nope.md"], 1, "no such file")
        case("show directory", base, "rag.py", ["show", "dsc"], 1, "no such file")
        case("show absolute path outside kb", base, "rag.py", ["show", "/etc/hosts"], 1, "outside the kb")
        case("show ../ traversal", base, "rag.py", ["show", "../" * 12 + "etc/hosts"], 1, "outside the kb")
        case("topics unknown domain", base, "rag.py", ["topics", "zzz"], 1, "no domain")

        # 2b. tokenizer: hyphen/dot compounds are searchable by their parts, and parts find the compound
        top5 = lambda want: lambda out: want in [x["path"] for x in json.loads(out)]  # noqa: E731
        case("search part of compound: gmsa", base, "rag.py", ["--json", "search", "gmsa", "-k", "5"], 0,
             check=top5("auth/gmsa-dmsa.md"))
        case("search spaced form of compound: what if", base, "rag.py", ["--json", "search", "what", "if", "-k", "5"], 0,
             check=top5("dsc/what-if.md"))
        case("search file-name token: openssh", base, "rag.py", ["--json", "search", "openssh", "-k", "5"], 0,
             check=top5("windows/openssh-server.md"))

        # 3. concurrency and determinism
        if not FILTER or FILTER in "concurrency determinism":
            qs = [" ".join(random.sample(vocab, 3)) for _ in range(48)]
            with cf.ThreadPoolExecutor(16) as ex:
                outs = list(ex.map(lambda q: run(base, "rag.py", "--json", "search", q, "-u"), qs))
            bad = [o for o in outs if o[0] not in (0, 1) or "Traceback" in o[2] or (o[0] == 0 and not is_json(o[1]))]
            results.append((not bad, "48 searches, 16 in parallel", f"{len(bad)} failed" if bad else "ok"))
            outs = {run(base, "rag.py", "--json", "search", "gmsa kerberos delegation", "-k", "20")[1] for _ in range(5)}
            results.append((len(outs) == 1, "search deterministic over 5 runs", f"{len(outs)} distinct outputs"))

        # 4. corpus scaling
        if a.scale > 1 and (not FILTER or FILTER in "scaling"):
            d = copy_kb(tmp, "scale")
            doms = [x for x in os.listdir(d) if os.path.isdir(os.path.join(d, x)) and not x.startswith(("_", "."))]
            for i in range(1, a.scale):
                for dom in doms:
                    shutil.copytree(os.path.join(d, dom), os.path.join(d, f"{dom}-copy{i}"))
            case(f"scaling: search corpus x{a.scale}", d, "rag.py", ["search", "kerberos", "delegation", "-k", "5"], 0)
            case(f"scaling: check.py corpus x{a.scale}", d, "check.py", [], 0)
            shutil.rmtree(d)

        # 5. malformed kb content: each mutation gets a fresh copy
        def mutated(name, mutate, calls):
            if FILTER and FILTER not in name and not any(FILTER in f"{name} :: {c[0]}" for c in calls):
                return
            d = copy_kb(tmp, "mut")
            mutate(d)
            for tool, args, rc, *rest in calls:
                case(f"{name} :: {tool} {' '.join(args)}".strip(), d, tool, args, rc, *rest)
            shutil.rmtree(d)

        mutated("invalid UTF-8 .md", lambda d: write(d, "ad/bad.md", b"---\ntopic: ad/bad\n---\n# x \xff\xfe kerberos\n"), [
            ("rag.py", ["search", "kerberos"], 0), ("rag.py", ["topics", "ad"], 0),
            ("check.py", [], 1, "ad/bad.md is unreadable")])
        mutated("binary blob named .md", lambda d: write(d, "ad/blob.md", random.randbytes(200000)), [
            ("rag.py", ["search", "kerberos"], 0), ("rag.py", ["topics", "ad"], 0), ("check.py", [], 1, "unreadable")])
        mutated("20 MB single-line .md", lambda d: write(d, "ad/huge.md", "kerberos " * 2_300_000), [
            ("rag.py", ["--json", "search", "kerberos", "-k", "1"], 0, "", lambda o: len(o) < 10000),
            ("check.py", [], 0)])
        mutated("CSV cell over 131072 chars", lambda d: write(d, "ad/wide.csv", 'a,b\n"' + "x" * 200000 + '",kerberos\n'), [
            ("rag.py", ["search", "kerberos"], 0)])
        mutated("CSV with NUL byte", lambda d: write(d, "ad/nul.csv", b"a,b\nkerberos\x00,1\n"), [
            ("rag.py", ["search", "kerberos"], 0)])
        mutated("empty and header-only CSV", lambda d: (write(d, "ad/empty.csv", ""), write(d, "ad/hdr.csv", "a,b\n")), [
            ("rag.py", ["search", "kerberos"], 0), ("check.py", [], 0)])
        mutated("CSV row with an unquoted comma", lambda d: write(d, "ad/ragged.csv", "a,b\nx,y\nx,y, z\n"), [
            ("check.py", [], 1, "ad/ragged.csv has 1 row(s)")])
        mutated("unclosed front matter", lambda d: write(d, "ad/open.md", "---\ntopic: ad/open\nstatus: complete\n# kerberos\n"), [
            ("rag.py", ["search", "kerberos"], 0), ("rag.py", ["topics", "ad"], 0), ("check.py", [], 1, "front matter lacks")])
        mutated("front matter is only '---'", lambda d: write(d, "ad/dash.md", "---\n"), [
            ("rag.py", ["search", "kerberos"], 0), ("rag.py", ["topics", "ad"], 0), ("check.py", [], 0)])
        mutated("UTF-8 BOM in _sources.csv", lambda d: write(d, "_sources.csv", "﻿" + read(d, "_sources.csv")), [
            ("rag.py", ["src", "S100"], 0, "S100"), ("rag.py", ["search", "kerberos", "-u"], 0, "->"),
            ("check.py", [], 0), ("fetch.py", ["--offline"], 0)])
        mutated("_sources.csv without url column", lambda d: write(d, "_sources.csv", read(d, "_sources.csv").replace("id,url,", "id,link,", 1)), [
            ("rag.py", ["src", "S100"], 1, "lacks"), ("rag.py", ["search", "kerberos", "-u"], 1, "lacks"),
            ("check.py", [], 1, "lacks column"), ("fetch.py", ["--offline"], 1, "lacks column")])
        mutated("_sources.csv deleted", lambda d: os.remove(os.path.join(d, "_sources.csv")), [
            ("rag.py", ["search", "kerberos"], 0), ("rag.py", ["src", "S100"], 1, "cannot read"),
            ("check.py", [], 1, "cannot read"), ("fetch.py", ["--offline"], 1, "cannot read")])
        mutated("_artifacts.csv deleted", lambda d: os.remove(os.path.join(d, "_artifacts.csv")), [
            ("check.py", [], 1, "cannot read"), ("fetch.py", ["--offline"], 1, "cannot read")])
        mutated("_artifacts.csv header only", lambda d: write(d, "_artifacts.csv", "path,source_id,sha256,zip_member\n"), [
            ("fetch.py", ["--offline"], 1, "no artifacts")])
        mutated("pinned artifact tampered", lambda d: write(d, "sqlserver/mssql-server-tags.json", "{}"), [
            ("fetch.py", ["--offline"], 1, "MISMATCH"), ("check.py", [], 0)])

        def to_dir(d):
            p = os.path.join(d, "sqlserver/mssql-server-tags.json")
            os.remove(p)
            os.makedirs(p)
        mutated("pinned artifact replaced by a directory", to_dir, [
            ("fetch.py", ["--offline"], 1, "is a directory"), ("check.py", [], 1, "is missing")])
        mutated("symlink loop", lambda d: os.symlink(os.path.join(d, "ad"), os.path.join(d, "ad", "loop")), [
            ("rag.py", ["search", "kerberos"], 0), ("rag.py", ["topics"], 0), ("check.py", [], 0)])
        mutated("symlink to /etc", lambda d: os.symlink("/etc", os.path.join(d, "ad", "etc")), [
            ("rag.py", ["search", "kerberos"], 0), ("rag.py", ["show", "ad/etc/hosts"], 1, "outside the kb")])
        if os.name == "posix" and os.geteuid() != 0:  # root can read a chmod 000 file
            def unreadable(d):
                write(d, "ad/secret.md", "kerberos")
                os.chmod(os.path.join(d, "ad/secret.md"), 0)
            mutated("unreadable .md", unreadable, [
                ("rag.py", ["search", "kerberos"], 0, "skipped ad/secret.md"), ("rag.py", ["topics", "ad"], 0),
                ("check.py", [], 1, "unreadable")])
        mutated("3000 extra topic files", lambda d: [write(d, f"bulk/t{i}.md", (
            f"---\ntopic: bulk/t{i}\npriority: P3\nretrieved_utc: 2026-09-25\nsources: [S100]\nstatus: complete\n---\n"
            f"# t{i}\n## Facts\n- kerberos {i} [DOC S100]\n")) for i in range(3000)], [
            ("rag.py", ["search", "kerberos"], 0), ("rag.py", ["topics", "bulk"], 0), ("check.py", [], 0)])
        mutated("citation to unknown source", lambda d: write(d, "ad/cite.md", "x [DOC S999999] y\n"), [
            ("check.py", [], 1, "cites unknown source S999999")])
        mutated("100k citations in one file", lambda d: write(d, "ad/many.md", "".join(f"- f [DOC S{100 + i % 900}]\n" for i in range(100000))), [
            ("check.py", [], (0, 1)), ("rag.py", ["search", "f", "-u"], 0)])

        # 5b. collision-free ids: hash source ids, superseded_by, answer ids
        id_cases(mutated)

        # 5c. generated index files: build_index.py
        index_cases(tmp)

        # 5d. post-merge cleanup: kbgit.py fix / fmt (git merges themselves: test_merge.py)
        kbgit_cases(tmp)

        # 6. fetch.py --diff / --status against a local web server (no internet needed)
        if not FILTER or "diff" in FILTER or "status" in FILTER:
            fetch_diff_cases(tmp)

    failed = [r for r in results if not r[0]]
    for ok, name, note in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name:<60} {note}")
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed")
    sys.exit(1 if failed else 0)


def add_sources(d, new=(), patch=None):
    """Append rows (dicts) to a copy's _sources.csv and apply `patch` {id: {column: value}} to existing rows."""
    rows = list(csv.DictReader(io.StringIO(read(d, "_sources.csv"))))
    for r in rows:
        r.update((patch or {}).get(r["id"], {}))
    buf = io.StringIO()
    w = csv.DictWriter(buf, list(rows[0].keys()), lineterminator="\n")
    w.writeheader()
    w.writerows(rows + [{**dict.fromkeys(rows[0], ""), **r} for r in new])
    write(d, "_sources.csv", buf.getvalue())


def id_cases(mutated):
    """Hash ids (S-xxxxxxxx) work next to legacy ids in every tool; check.py rejects bad ids, supersession and answer ids."""
    sys.path.insert(0, os.path.join(KB, "_tools"))
    import kbid
    url = "https://learn.microsoft.com/en-us/windows/example-hash-id-page"
    hid = kbid.source_id(url)
    row = {"id": hid, "url": url, "title": "hash id test page", "publisher": "Microsoft", "licence": "test",
           "retrieved_utc": "2026-09-25", "version_or_date": "test", "used_in": "ad/hashid.md"}

    def with_hash(d):
        add_sources(d, [row])
        write(d, "ad/hashid.md", f"---\ntopic: ad/hashid\npriority: P3\nretrieved_utc: 2026-09-25\nsources: [{hid}, S100]\n"
                                 f"status: complete\n---\n# t\n## Facts\n- zanzibarquux fact [DOC {hid}, S100]\n")
    hits = lambda o: json.loads(o)[0]["sources"] == ["S100", hid]  # noqa: E731
    n_hash = sum(1 for r in kbid.read_sources() if kbid.is_hash_id(r.get("id") or ""))  # the kb's own, before the row
    mutated("hash id cited next to a legacy id", with_hash, [
        ("check.py", [], 0), ("kbid.py", ["check"], 0, f"hash_ids={n_hash + 1}"),
        ("rag.py", ["src", hid, "S100"], 0, "hash id test page"),
        ("rag.py", ["src", hid.upper()], 0, "hash id test page"),
        ("rag.py", ["--json", "search", "zanzibarquux", "-u"], 0, "", hits),
        ("fetch.py", ["--status", "--source", hid], 0, "selected=1"),
        ("fetch.py", ["--status", "--json", "--file", "ad/hashid.md"], 0, "",
         lambda o: {x["id"] for x in json.loads(o)} == {hid, "S100"}),
        ("kbid.py", ["url", url], 0, f"already in _sources.csv as {hid}")])
    mutated("superseded_by names a known id", lambda d: add_sources(d, [row], {"S100": {"superseded_by": hid}}), [
        ("check.py", [], 0), ("rag.py", ["src", "S100"], 0, f"superseded by {hid}")])
    mutated("superseded_by names an unknown id", lambda d: add_sources(d, patch={"S100": {"superseded_by": "S-aaaaaaaa"}}), [
        ("check.py", [], 1, "S100 superseded_by unknown source S-aaaaaaaa")])
    mutated("superseded_by cycle", lambda d: add_sources(d, patch={"S100": {"superseded_by": "S101"}, "S101": {"superseded_by": "S102"},
                                                                   "S102": {"superseded_by": "S100"}}), [
        ("check.py", [], 1, "forms a cycle")])
    mutated("superseded_by itself", lambda d: add_sources(d, patch={"S100": {"superseded_by": "S100"}}), [
        ("check.py", [], 1, "forms a cycle")])
    mutated("hand-typed hash id", lambda d: add_sources(d, [{**row, "id": "S-abcdefgh"}]), [
        ("check.py", [], 1, "S-abcdefgh does not match its url"), ("kbid.py", ["check"], 1, "does not match")])
    a, b = "https://example.com/c/266794", "https://example.com/c/514424"  # a real 40-bit collision
    mutated("hash id collision", lambda d: add_sources(d, [{**row, "id": kbid.source_id(a), "url": a},
                                                           {**row, "id": "S99990", "url": b}]), [
        ("check.py", [], 1, f"hash id collision {kbid.source_id(a)}"), ("kbid.py", ["check"], 1, "collision")])
    mutated("malformed id in _sources.csv", lambda d: add_sources(d, [{**row, "id": "S-12"}]), [
        ("check.py", [], 1, "malformed source id")])
    mutated("malformed hash id cited", lambda d: write(d, "ad/badid.md", "x [DOC S-ZZZZ] y\n"), [
        ("check.py", [], 1, "cites unknown source S-ZZZZ")])
    mutated("_sources.csv without superseded_by column", lambda d: write(d, "_sources.csv", "\n".join(
        ln.rpartition(",")[0] for ln in read(d, "_sources.csv").splitlines()) + "\n"), [
        ("check.py", [], 1, "lacks column(s) superseded_by"), ("rag.py", ["src", "S100"], 0, "S100"),
        ("fetch.py", ["--offline"], 0)])
    dup = "\n## QK-dup-answer. first\n- x [UNK]\n\n## QK-dup-answer. second\n- y [UNK]\n"
    mutated("duplicate QK answer id", lambda d: write(d, "_answers.md", read(d, "_answers.md") + dup), [
        ("check.py", [], 1, "duplicate answer id QK-dup-answer"), ("kbid.py", ["answer", "dup answer"], 0, "already used")])
    mutated("numbered QK answer id", lambda d: write(d, "_answers.md", read(d, "_answers.md") + "\n## QK7. q\n- x [UNK]\n"), [
        ("check.py", [], 1, "QK ids are QK-<slug>")])
    mutated("slug QK answer id", lambda d: write(d, "_answers.md", read(d, "_answers.md") + "\n## QK-dataverse-onprem-sync. q\n- x [UNK]\n"), [
        ("check.py", [], 0)])


def coverage(d):
    return {r["topic"]: r for r in csv.DictReader(io.StringIO(read(d, "_coverage.csv")))}


def index_cases(tmp):
    """build_index.py: files: extras, topics without an article, hand edits caught by --check, idempotency."""
    if FILTER and FILTER not in "index build_index":
        return
    B = "build_index.py"
    GEN = ("_coverage.csv", "README.md", "_sources.csv")
    d = copy_kb(tmp, "index")
    case("index: pristine kb is up to date", d, B, ["--check"], 0, "out_of_date=0")
    art = lambda topic, extra="": (f"---\ntopic: {topic}\npriority: P3\nretrieved_utc: 2026-09-25\nsources: [S100, S101]\n"  # noqa: E731
                                   f"status: partial\n{extra}---\n# t\n## Summary\n## Facts\n- quux [DOC S100, S101]\n## Reference\n## Examples\n")
    write(d, "ad/extras.md", art("ad/extras", "files: [ad/extras-data/, ad/extras-data/digest.md]\n"))
    write(d, "ad/extras.csv", "a,b\nx,S102\n")
    write(d, "ad/extras-data/digest.md", art("ad/extras-data/digest"))
    write(d, "ad/table-only.csv", "op,sources\nx,S100;S101\ny,S101;S999999\n")
    write(d, "_tools/index_extra.csv", read(d, "_tools/index_extra.csv") + "ad/table-only,P3,partial,ad/table-only.csv\n")
    case("index: new article and extra row are detected", d, B, ["--check"], 1, "_coverage.csv: ad/extras row missing")
    case("index: build writes the three files", d, B, [], 0, "written=3")
    cov = coverage(d)
    ok = cov.get("ad/extras", {}).get("files") == "ad/extras.md;ad/extras.csv;ad/extras-data/;ad/extras-data/digest.md" \
        and cov["ad/extras"]["n_sources"] == "2" and "ad/extras-data/digest" not in cov
    results.append((ok, "index: files: extras follow the md and its stem siblings; a listed digest is no row", str(cov.get("ad/extras"))))
    ok = cov.get("ad/table-only", {}).get("n_sources") == "2" and cov["ad/table-only"]["files"] == "ad/table-only.csv"
    results.append((ok, "index: topic without an article from index_extra.csv (known ids only)", str(cov.get("ad/table-only"))))
    topics = list(cov)
    ok = topics == sorted(topics, key=lambda t: (t.split("/")[0], cov[t]["priority"], t))
    results.append((ok, "index: rows ordered by domain, priority, topic", "ok" if ok else "out of order"))
    ok = "| `ad/extras` | P3 | partial | `ad/extras.md`, `ad/extras.csv`, `ad/extras-data/`, `ad/extras-data/digest.md` | 2 |" in read(d, "README.md")
    results.append((ok, "index: README row rendered between the markers", "ok" if ok else "row missing"))
    src = {r["id"]: r for r in csv.DictReader(io.StringIO(read(d, "_sources.csv")))}
    ok = "ad/extras.csv" in src["S102"]["used_in"].split(";") and "ad/table-only.csv" in src["S101"]["used_in"].split(";") \
        and not any(u.startswith(("_", ".")) or "/" not in u for r in src.values() for u in r["used_in"].split(";") if u)
    results.append((ok, "index: used_in cites csv files, never root or tool files", "ok" if ok else src["S102"]["used_in"]))
    before = {f: read(d, f) for f in GEN}
    case("index: second build writes nothing", d, B, [], 0, "written=0")
    ok = all(read(d, f) == before[f] for f in GEN) and all("\r" not in before[f] for f in GEN)
    results.append((ok, "index: idempotent, \\n line endings", "ok" if ok else "files changed on rebuild"))
    case("index: --check after build", d, B, ["--check"], 0, "out_of_date=0")
    case("index: check.py accepts the new files", d, "check.py", [], 0)
    shutil.rmtree(d)

    def hand_edit(name, mutate, rc, expect, fixes=True):
        d = copy_kb(tmp, "index")
        mutate(d)
        case(f"index: {name} :: --check", d, B, ["--check"], rc, expect)
        if fixes:
            case(f"index: {name} :: build repairs it", d, B, [], 0)
            case(f"index: {name} :: --check after build", d, B, ["--check"], 0, "out_of_date=0")
        shutil.rmtree(d)
    t0 = next(iter(csv.DictReader(io.StringIO(read(KB, "_coverage.csv")))))["topic"]
    hand_edit("hand-edited n_sources", lambda d: write(d, "_coverage.csv", "\n".join(
        ln.rpartition(",")[0] + ",999" if ln.startswith(t0 + ",") else ln for ln in read(d, "_coverage.csv").split("\n"))),
        1, f"_coverage.csv: {t0}: n_sources")
    hand_edit("hand-added coverage row", lambda d: write(d, "_coverage.csv", read(d, "_coverage.csv") + "zz/ghost,P0,complete,zz/ghost.md,1\n"),
              1, "zz/ghost is not a topic")
    hand_edit("rows swapped", lambda d: write(d, "_coverage.csv", (lambda ls: "\n".join([ls[0], ls[2], ls[1]] + ls[3:]))(
        read(d, "_coverage.csv").split("\n"))), 1, "row order")
    hand_edit("CRLF _coverage.csv", lambda d: write(d, "_coverage.csv", read(d, "_coverage.csv").replace("\n", "\r\n")), 1, "_coverage.csv")
    hand_edit("hand-edited README row", lambda d: write(d, "README.md", read(d, "README.md").replace(f"| `{t0}` |", f"| `{t0}` | P9 |", 1)),
              1, "README.md: coverage table differs")
    hand_edit("hand-edited used_in", lambda d: add_sources(d, patch={"S100": {"used_in": "dsc/nothing.md"}}), 1, "S100 used_in")
    hand_edit("front matter changed, index not rebuilt", lambda d: write(d, t0 + ".md", read(d, t0 + ".md").replace(
        "\nstatus: ", "\nstatus: unknown\nold_status: ", 1)), 1, f"_coverage.csv: {t0}: status")
    hand_edit("README without markers", lambda d: write(d, "README.md", read(d, "README.md").replace("<!-- coverage:start -->", "")),
              2, "lacks the", fixes=False)
    hand_edit("files: names a missing path (warned, lint errors)", lambda d: write(d, t0 + ".md", read(d, t0 + ".md").replace(
        "\nstatus: ", "\nfiles: [ad/nope.csv]\nstatus: ", 1)), 1, "files: lists missing ad/nope.csv")
    hand_edit("_sources.csv deleted", lambda d: os.remove(os.path.join(d, "_sources.csv")), 2, "cannot read _sources.csv", fixes=False)


def kbgit_cases(tmp):
    """kbgit.py: the pristine kb is clean; a union-style merge result (repeated header, duplicate and split rows,
    markers) is fixed in one run and the next run changes nothing; what needs a human exits 2 and writes nothing."""
    if FILTER and FILTER not in "kbgit fix fmt merge":
        return
    G = "kbgit.py"
    d = copy_kb(tmp, "kbgit")
    case("kbgit: pristine kb needs no fix", d, G, ["fix", "--check"], 0, "changed=0")
    case("kbgit: pristine kb is formatted", d, G, ["fmt", "--check"], 0, "changed=0")
    src = read(d, "_sources.csv")
    head, body = src.split("\n", 1)
    lines = body.splitlines()
    newer = lines[0].replace(",2026-", ",2027-", 1)
    write(d, "_sources.csv", head + "\n" + "\n".join(lines[::-1]) + "\n" + "<<<<<<< ours\n" + lines[1] + "\n=======\n"
          + head + "\n" + newer + "\n>>>>>>> theirs\n")
    write(d, "_answers.md", read(d, "_answers.md") + read(d, "_answers.md").split("\n## ", 2)[1].join(["\n## ", ""]))
    case("kbgit: fmt refuses conflict markers", d, G, ["fmt"], 2, "conflict markers")
    case("kbgit: merged ledgers :: --check", d, G, ["fix", "--check"], 1, "WOULD CHANGE _sources.csv")
    case("kbgit: merged ledgers :: fix", d, G, ["fix"], 0, "removed 1 repeated header")
    case("kbgit: merged ledgers :: second fix changes nothing", d, G, ["fix", "--check"], 0, "changed=0")
    ok = read(d, "_sources.csv") == src.replace(lines[0], newer) and read(d, "_answers.md") == read(KB, "_answers.md")
    results.append((ok, "kbgit: rows back in canonical order, newer duplicate merged, repeated answer dropped", "ok" if ok else "differs"))
    case("kbgit: check.py after fix", d, "check.py", [], 0)
    shutil.rmtree(d)

    d = copy_kb(tmp, "kbgit")
    add_sources(d, [{"id": "S100", "url": "https://collision.example.com/other"}])
    case("kbgit: legacy id collision without --base", d, G, ["fix"], 2, "rerun with --base")
    case("kbgit: --base outside a git clone", d, G, ["fix", "--base", "HEAD~1"], 2, "not a commit")
    shutil.rmtree(d)
    d = copy_kb(tmp, "kbgit")
    write(d, "_answers.md", read(d, "_answers.md") + "\n## QK-dup. a\n\none\n\n## QK-dup. a\n\ntwo\n")
    write(d, "_gaps.md", read(d, "_gaps.md") * 2)
    before = read(d, "_gaps.md")
    case("kbgit: answer id clash is reported", d, G, ["fix"], 2, "QK-dup appears 2 times")
    results.append((read(d, "_gaps.md") == before, "kbgit: nothing written when a human is needed", "ok"))
    shutil.rmtree(d)


def fetch_diff_cases(tmp):
    """--diff/--status: baseline, change detection, text diff, no-save, errors, selection, HTML normalization."""
    www = os.path.join(tmp, "www")
    os.makedirs(www, exist_ok=True)
    page = lambda body, nav="menu": f"<html><head><title>t</title></head><body><nav>{nav}</nav><main><h1>Doc</h1>{body}</main></body></html>"  # noqa: E731
    write(www, "a.html", page("<p>line one</p><p>line two</p>"))
    write(www, "b.txt", "plain text\n")
    handler = functools.partial(type("Quiet", (http.server.SimpleHTTPRequestHandler,), {"log_message": lambda *x: None}), directory=www)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        d = copy_kb(tmp, "diff")
        rows = list(csv.DictReader(io.StringIO(read(d, "_sources.csv"))))
        for r in rows:  # S100 -> html page, S101 -> text file, S102 -> dead port, S103 -> not http
            r["url"] = {"S100": f"{url}/a.html", "S101": f"{url}/b.txt", "S102": "http://127.0.0.1:9/x", "S103": "file:///etc/hosts"}.get(r["id"], r["url"])
            if r["id"] in ("S100", "S101"):
                r["version_or_date"], r["artifact_sha256"] = "test", ""
        buf = io.StringIO()
        w = csv.DictWriter(buf, list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
        write(d, "_sources.csv", buf.getvalue())
        F = ["--delay", "0", "--timeout", "5"]
        two = ["--source", "S100", "--source", "S101"]
        case("diff: status before any fetch", d, "fetch.py", ["--status", *two], 0, "never_fetched=2")
        case("diff: first fetch is new", d, "fetch.py", ["--diff", *two, *F], 0, "new=2")
        case("diff: state and snapshots saved", d, "fetch.py", ["--status", *two, "--json"], 0,
             check=lambda o: all(x["fetched_utc"] for x in json.loads(o)) and os.path.isfile(os.path.join(d, "_cache/snapshots/S100.txt")))
        case("diff: refetch unchanged", d, "fetch.py", ["--diff", *two, *F], 0, "unchanged=2")
        write(www, "a.html", page("<p>line one</p><p>line two</p>", nav="other menu"))
        case("diff: change outside <main> ignored", d, "fetch.py", ["--diff", "--source", "S100", *F], 0, "unchanged=1")
        write(www, "a.html", page("<p>line one</p><p>line 2 edited</p><p>added line</p>"))
        case("diff: --no-save shows change", d, "fetch.py", ["--diff", "--source", "S100", "--no-save", *F], 1, "changed=1")
        case("diff: --no-save kept the baseline", d, "fetch.py", ["--diff", "--source", "S100", "--no-save", *F], 1, "(not saved)")
        case("diff: --max-lines caps diff", d, "fetch.py", ["--diff", "--source", "S100", "--full", "--max-lines", "2", "--no-save", *F], 1, "cut at --max-lines 2")
        case("diff: --json full diff", d, "fetch.py", ["--diff", "--source", "S100", "--full", "--json", *F], 1,
             check=lambda o: (lambda j: j["changed"] == 1 and "+added line" in j["sources"][0]["diff"]
                              and j["sources"][0]["added"] == 2 and j["sources"][0]["removed"] == 1)(json.loads(o)))
        case("diff: change is now the baseline", d, "fetch.py", ["--diff", "--source", "S100", *F], 0, "unchanged=1")
        write(www, "b.txt", "plain text\nmore\n")
        case("diff: text file change with --full", d, "fetch.py", ["--diff", *two, "--full", *F], 1, "+more")
        case("diff: dead host is an error (exit 2)", d, "fetch.py", ["--diff", "--source", "S102", *F], 2, "ERROR")
        case("diff: non-http url refused (exit 2)", d, "fetch.py", ["--diff", "--source", "S103", *F], 2, "not an http(s) url")
        case("diff: error recorded in state", d, "fetch.py", ["--status", "--source", "S102"], 0, "with_error=1")
        case("diff: --older-than skips fresh sources", d, "fetch.py", ["--diff", *two, "--older-than", "1", *F], 0, "selected=0")
        case("diff: unknown topic is exit 2", d, "fetch.py", ["--diff", "--topic", "nope/nothing", *F], 2, "no topic")
        case("diff: unknown source is exit 2", d, "fetch.py", ["--status", "--source", "S99999999"], 2, "unknown source")
        case("diff: selection flag without mode", d, "fetch.py", ["--file", "README.md"], 2, "need --diff or --status")
        n = lambda o: len(json.loads(o))  # noqa: E731
        f_ = case("status: --file selection", d, "fetch.py", ["--status", "--json", "--file", "dsc/what-if.md"], 0, check=lambda o: n(o) > 0)
        case("status: --topic selection", d, "fetch.py", ["--status", "--json", "--topic", "dsc/what-if"], 0, check=lambda o: n(o) > 0)
        case("status: --dir is a superset of --file", d, "fetch.py", ["--status", "--json", "--dir", "dsc"], 0,
             check=lambda o: f_ is not None and {x["id"] for x in json.loads(f_)} <= {x["id"] for x in json.loads(o)})
        case("status: no selection = every source", d, "fetch.py", ["--status", "--json"], 0, check=lambda o: n(o) == len(rows))
        shutil.rmtree(d)
    finally:
        srv.shutdown()


FILTER = ""
if __name__ == "__main__":
    main()
