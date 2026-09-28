"""Stress and robustness tests of the kb tools (marker `stress`): `python3 _tools/stress_test.py` runs them.

Every case runs against a throwaway copy of the kb in a temporary directory; the kb itself is never modified. A case
fails if the tool's exit code is not the expected one, if its output misses an expected string, or if it prints a
Python traceback (a crash is never an acceptable way to report bad input).

  BASE_CASES      the pristine kb passes every tool; hostile arguments; the tokenizer finds compounds by their parts
  MUTATIONS       malformed kb content, collision-free ids: each mutation on a fresh copy, then every tool call
  HAND_EDITS      hand edits of the generated index files: build_index.py --check catches them, a build repairs them
  flows           concurrency and determinism, corpus scaling (KB_STRESS_SCALE, default 5), build_index.py extras,
                  kbgit.py fix after a union-style merge, fetch.py --diff/--status against a local web server
"""
import concurrent.futures as cf, csv, functools, http.server, io, json, os, random, shutil, subprocess, sys, threading

import pytest

import kbid
from conftest import D, KB, P, Q

pytestmark = pytest.mark.stress
TIMEOUT = 300
SCALE = int(os.environ.get("KB_STRESS_SCALE") or 5)
random.seed(7)


COV = P("_coverage.md")  # the public root's coverage page (build_index.py prints it qualified: public/_coverage.md)
SKIP = shutil.ignore_patterns(".git", "__pycache__", ".venv", ".pytest_cache", ".ruff_cache", "_private")


def skip(src, names):
    """Everything in _cache but the pack index (census clones there reach gigabytes: 14 workers' copies filled a
    disk on 2026-09-26)."""
    if os.path.abspath(src) == os.path.join(KB, "_cache"):  # the repository's cache, whatever the layout
        return {n for n in names if not n.startswith("kbindex-")}
    return SKIP(src, names)


def copy_kb(tmp, name):
    """A copy with the kb's pack index from _cache (so a copy reuses it until a mutation changes a file)."""
    d = os.path.join(str(tmp), name)
    shutil.copytree(KB, d, ignore=skip, symlinks=True)
    return d


def run(kb, tool, *args):
    p = subprocess.run([sys.executable, os.path.join(kb, "_tools", tool), *args],
                       capture_output=True, text=True, errors="replace", timeout=TIMEOUT)
    return p.returncode, p.stdout, p.stderr


def problems(kb, tool, args, rc, expect="", check=None):
    """(what is wrong with one tool call, its stdout)."""
    try:
        got, out, err = run(kb, tool, *args)
    except subprocess.TimeoutExpired:
        return [f"timeout after {TIMEOUT} s"], ""
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
    return why, out


def call(kb, tool, args, rc, expect="", check=None):
    """One step of a flow: fails at once, naming the call."""
    why, out = problems(kb, tool, args, rc, expect, check)
    assert not why, f"{tool} {' '.join(args)}: " + "; ".join(why)
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


def add_sources(d, new=(), patch=None):
    """Append rows (dicts) to a copy's _sources.csv and apply `patch` {id: {column: value}} to existing rows."""
    rows = list(csv.DictReader(io.StringIO(read(d, P("_sources.csv")))))
    for r in rows:
        r.update((patch or {}).get(r["id"], {}))
    buf = io.StringIO()
    w = csv.DictWriter(buf, list(rows[0].keys()), lineterminator="\n")
    w.writeheader()
    w.writerows(rows + [{**dict.fromkeys(rows[0], ""), **r} for r in new])
    write(d, P("_sources.csv"), buf.getvalue())


def without_column(d, col):
    """Drop one column from a copy's _sources.csv."""
    rows = list(csv.reader(io.StringIO(read(d, P("_sources.csv")))))
    i = rows[0].index(col)
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows(r[:i] + r[i + 1:] for r in rows)
    write(d, P("_sources.csv"), buf.getvalue())


def ids(cases):
    return [c[0] for c in cases]


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    d = copy_kb(tmp_path_factory.mktemp("kb-stress"), "base")
    yield d
    shutil.rmtree(d, ignore_errors=True)


# ---------------------------------------------------------------- the pristine kb, hostile arguments, the tokenizer

VOCAB = [w for w in read(KB, "README.md").lower().split() if w.isalpha() and len(w) > 3]
top5 = lambda want: lambda out: want in [x["path"] for x in json.loads(out)]  # noqa: E731
BASE_CASES = [  # (name, tool, args, rc, expect, check)
    ("baseline check.py", "check.py", [], 0, "", None),
    ("baseline fetch.py --offline", "fetch.py", ["--offline"], 0, "", None),
    ("baseline rag topics", "rag.py", ["topics"], 0, "", None),
    ("baseline rag search -u", "rag.py", ["search", "kerberos", "-u"], 0, "->", None),
    ("baseline rag src", "rag.py", ["src", "S100"], 0, "S100", None),
    ("baseline rag show", "rag.py", ["show", "README.md:1", "-n", "3"], 0, "it-ops-kb", None),
    ("search 10k-word query", "rag.py", ["search", " ".join(random.choices(VOCAB, k=10000))], 0, "", None),
    ("search 120k-char single token", "rag.py", ["search", "a" * 120000], 1, "no match", None),  # Linux caps one argv string at 128 KiB
    ("search regex and shell characters", "rag.py", ["search", r".*[](){}^$|\?+ %s %n ' \" ; rm -rf /"], (0, 1), "", None),
    ("search unicode, emoji, RTL, zero-width", "rag.py", ["search", "zażółć 🔐 ключ 密钥 ‮kerberos​"], (0, 1), "", None),
    ("search -k 0 rejected", "rag.py", ["search", "kerberos", "-k", "0"], 2, "must be >= 1", None),
    ("search -k -5 rejected", "rag.py", ["search", "kerberos", "-k", "-5"], 2, "must be >= 1", None),
    ("search -k abc rejected", "rag.py", ["search", "kerberos", "-k", "abc"], 2, "", None),
    ("search -k 10000000 --json -u", "rag.py", ["--json", "search", "the", "-k", "10000000", "-u"], 0, "", is_json),
    ("search -d ../..", "rag.py", ["search", "kerberos", "-d", "../.."], 1, "no domain", None),
    ("src 5000 ids", "rag.py", ["src", *[f"S{i}" for i in range(5000)]], 0, "", None),
    ("src junk ids", "rag.py", ["src", "'; DROP TABLE", "S", "S-1", "s0100"], 0, "UNKNOWN id", None),
    ("show -n 100000000", "rag.py", ["show", "_answers.md", "-n", "100000000"], 0, "", None),
    ("show line 0", "rag.py", ["show", "README.md:0", "-n", "1"], 0, "", None),
    ("show line -5 rejected", "rag.py", ["show", "README.md:-5"], 1, "positive number", None),
    ("show line abc rejected", "rag.py", ["show", "README.md:abc"], 1, "positive number", None),
    ("show -n -1 rejected", "rag.py", ["show", "README.md", "-n", "-1"], 2, "must be >= 1", None),
    ("show missing file", "rag.py", ["show", "nope.md"], 1, "no such file", None),
    ("show directory", "rag.py", ["show", "dsc"], 1, "no such file", None),
    ("show absolute path outside kb", "rag.py", ["show", "/etc/hosts"], 1, "outside the kb", None),
    ("show ../ traversal", "rag.py", ["show", "../" * 12 + "etc/hosts"], 1, "outside the kb", None),
    ("topics unknown domain", "rag.py", ["topics", "zzz"], 1, "no domain", None),
    # hyphen/dot compounds are searchable by their parts, and parts find the compound
    ("search part of compound: gmsa", "rag.py", ["--json", "search", "gmsa", "-k", "5"], 0, "", top5(Q("auth/gmsa-dmsa.md"))),
    ("search spaced form of compound: what if", "rag.py", ["--json", "search", "what", "if", "-k", "5"], 0, "", top5(Q("dsc/what-if.md"))),
    ("search file-name token: openssh", "rag.py", ["--json", "search", "openssh", "-k", "5"], 0, "", top5(Q("windows/openssh-server.md"))),
]


@pytest.mark.parametrize("name,tool,args,rc,expect,check", BASE_CASES, ids=ids(BASE_CASES))
def test_base(base, name, tool, args, rc, expect, check):
    call(base, tool, args, rc, expect, check)


def test_parallel_searches(base):
    qs = [" ".join(random.sample(VOCAB, 3)) for _ in range(48)]
    with cf.ThreadPoolExecutor(16) as ex:
        outs = list(ex.map(lambda q: run(base, "rag.py", "--json", "search", q, "-u"), qs))
    bad = [o for o in outs if o[0] not in (0, 1) or "Traceback" in o[2] or (o[0] == 0 and not is_json(o[1]))]
    assert not bad, f"{len(bad)} of 48 searches (16 in parallel) failed"


def test_search_is_deterministic(base):
    outs = {run(base, "rag.py", "--json", "search", "gmsa kerberos delegation", "-k", "20")[1] for _ in range(5)}
    assert len(outs) == 1, f"{len(outs)} distinct outputs over 5 runs"


@pytest.mark.skipif(SCALE < 2, reason="KB_STRESS_SCALE < 2")
def test_corpus_scaling(tmp_path):
    d = copy_kb(tmp_path, "scale")
    pub = os.path.join(d, P("."))
    doms = [x for x in os.listdir(pub) if os.path.isdir(os.path.join(pub, x)) and not x.startswith(("_", "."))]
    for i in range(1, SCALE):
        for dom in doms:
            shutil.copytree(os.path.join(pub, dom), os.path.join(pub, f"{dom}-copy{i}"))
    call(d, "rag.py", ["search", "kerberos", "delegation", "-k", "5"], 0)
    call(d, "check.py", [], 0)


# ---------------------------------------------------------------- malformed kb content: each mutation on a fresh copy

def to_dir(d):
    p = os.path.join(d, P("sqlserver/mssql-server-tags.json"))
    os.remove(p)
    os.makedirs(p)


def unreadable(d):
    write(d, P("ad/secret.md"), "kerberos")
    os.chmod(os.path.join(d, P("ad/secret.md")), 0)


MUTATIONS = [  # (name, mutate(copy), [(tool, args, rc[, expect[, check]]), ...])
    ("invalid UTF-8 .md", lambda d: write(d, P("ad/bad.md"), b"---\ntopic: ad/bad\n---\n# x \xff\xfe kerberos\n"), [
        ("rag.py", ["search", "kerberos"], 0), ("rag.py", ["topics", "ad"], 0),
        ("check.py", [], 1, "ad/bad.md is unreadable")]),
    ("binary blob named .md", lambda d: write(d, P("ad/blob.md"), random.Random(7).randbytes(200000)), [
        ("rag.py", ["search", "kerberos"], 0), ("rag.py", ["topics", "ad"], 0), ("check.py", [], 1, "unreadable")]),
    ("20 MB single-line .md", lambda d: write(d, P("ad/huge.md"), "kerberos " * 2_300_000), [
        ("rag.py", ["--json", "search", "kerberos", "-k", "1"], 0, "", lambda o: len(o) < 10000),
        ("check.py", [], 0)]),
    ("CSV cell over 131072 chars", lambda d: write(d, P("ad/wide.csv"), 'a,b\n"' + "x" * 200000 + '",kerberos\n'), [
        ("rag.py", ["search", "kerberos"], 0)]),
    ("CSV with NUL byte", lambda d: write(d, P("ad/nul.csv"), b"a,b\nkerberos\x00,1\n"), [
        ("rag.py", ["search", "kerberos"], 0)]),
    ("empty and header-only CSV", lambda d: (write(d, P("ad/empty.csv"), ""), write(d, P("ad/hdr.csv"), "a,b\n")), [
        ("rag.py", ["search", "kerberos"], 0), ("check.py", [], 0)]),
    ("CSV row with an unquoted comma", lambda d: write(d, P("ad/ragged.csv"), "a,b\nx,y\nx,y, z\n"), [
        ("check.py", [], 1, "ad/ragged.csv has 1 row(s)")]),
    ("unclosed front matter", lambda d: write(d, P("ad/open.md"), "---\ntopic: ad/open\nstatus: complete\n# kerberos\n"), [
        ("rag.py", ["search", "kerberos"], 0), ("rag.py", ["topics", "ad"], 0), ("check.py", [], 1, "front matter lacks")]),
    ("front matter is only '---'", lambda d: write(d, P("ad/dash.md"), "---\n"), [
        ("rag.py", ["search", "kerberos"], 0), ("rag.py", ["topics", "ad"], 0), ("check.py", [], 0)]),
    ("UTF-8 BOM in _sources.csv", lambda d: write(d, P("_sources.csv"), "﻿" + read(d, P("_sources.csv"))), [
        ("rag.py", ["src", "S100"], 0, "S100"), ("rag.py", ["search", "kerberos", "-u"], 0, "->"),
        ("check.py", [], 0), ("fetch.py", ["--offline"], 0)]),
    ("_sources.csv without url column", lambda d: write(d, P("_sources.csv"), read(d, P("_sources.csv")).replace("id,url,", "id,link,", 1)), [
        ("rag.py", ["src", "S100"], 1, "lacks"), ("rag.py", ["search", "kerberos", "-u"], 1, "lacks"),
        ("check.py", [], 1, "lacks column"), ("fetch.py", ["--offline"], 1, "lacks column")]),
    ("_sources.csv deleted", lambda d: os.remove(os.path.join(d, P("_sources.csv"))), [
        ("rag.py", ["search", "kerberos"], 0), ("rag.py", ["src", "S100"], 1, "cannot read"),
        ("check.py", [], 1, "cannot read"), ("fetch.py", ["--offline"], 1, "cannot read")]),
    ("_artifacts.csv deleted", lambda d: os.remove(os.path.join(d, P("_artifacts.csv"))), [
        ("check.py", [], 1, "cannot read"), ("fetch.py", ["--offline"], 1, "cannot read")]),
    ("_artifacts.csv header only", lambda d: write(d, P("_artifacts.csv"), "path,source_id,sha256,zip_member\n"), [
        ("fetch.py", ["--offline"], 1, "no artifacts")]),
    ("pinned artifact tampered", lambda d: write(d, P("sqlserver/mssql-server-tags.json"), "{}"), [
        ("fetch.py", ["--offline"], 1, "MISMATCH"), ("check.py", [], 0)]),
    ("pinned artifact replaced by a directory", to_dir, [
        ("fetch.py", ["--offline"], 1, "is a directory"), ("check.py", [], 1, "is missing")]),
    ("symlink loop", lambda d: os.symlink(os.path.join(d, P("ad")), os.path.join(d, P("ad"), "loop")), [
        ("rag.py", ["search", "kerberos"], 0), ("rag.py", ["topics"], 0), ("check.py", [], 0)]),
    ("symlink to /etc", lambda d: os.symlink("/etc", os.path.join(d, P("ad"), "etc")), [
        ("rag.py", ["search", "kerberos"], 0), ("rag.py", ["show", "ad/etc/hosts"], 1, "outside the kb")]),
    pytest.param("unreadable .md", unreadable, [
        ("rag.py", ["search", "kerberos"], 0, "skipped " + Q("ad/secret.md")), ("rag.py", ["topics", "ad"], 0),
        ("check.py", [], 1, "unreadable")],
        marks=pytest.mark.skipif(os.name != "posix" or os.geteuid() == 0, reason="root can read a chmod 000 file"),
        id="unreadable .md"),
    ("3000 extra topic files", lambda d: [write(d, P(f"bulk/t{i}.md"), (
        f"---\ntopic: bulk/t{i}\npriority: P3\nretrieved_utc: 2026-09-25\nsources: [S100]\nstatus: complete\n---\n"
        f"# t{i}\n## Facts\n- kerberos {i} [DOC S100]\n")) for i in range(3000)], [
        ("rag.py", ["search", "kerberos"], 0), ("rag.py", ["topics", "bulk"], 0), ("check.py", [], 0)]),
    ("citation to unknown source", lambda d: write(d, P("ad/cite.md"), "x [DOC S999999] y\n"), [
        ("check.py", [], 1, "cites unknown source S999999")]),
    ("100k citations in one file", lambda d: write(d, P("ad/many.md"), "".join(f"- flood [DOC S{100 + i % 900}]\n" for i in range(100000))), [
        ("check.py", [], (0, 1)), ("rag.py", ["search", "flood", "-u"], 0)]),
]

# collision-free ids: hash source ids work next to legacy ids in every tool; check.py rejects bad ids, supersession
# and answer ids
URL = "https://learn.microsoft.com/en-us/windows/example-hash-id-page"
HID = kbid.source_id(URL)
ROW = {"id": HID, "url": URL, "title": "hash id test page", "publisher": "Microsoft", "licence": "test",
       "reuse": "quote", "retrieved_utc": "2026-09-25", "version_or_date": "test", "used_in": "ad/hashid.md"}
N_HASH = sum(1 for r in kbid.read_sources() if kbid.is_hash_id(r.get("id") or ""))  # the kb's own, before the row
COLL_A, COLL_B = "https://example.com/c/266794", "https://example.com/c/514424"  # a real 40-bit collision
DUP = "\n## QK-dup-answer. first\n- x [UNK]\n\n## QK-dup-answer. second\n- y [UNK]\n"


def with_hash(d):
    add_sources(d, [ROW])
    write(d, P("ad/hashid.md"), f"---\ntopic: ad/hashid\npriority: P3\nretrieved_utc: 2026-09-25\nsources: [{HID}, S100]\n"
                             f"status: complete\n---\n# t\n## Facts\n- zanzibarquux fact [DOC {HID}, S100]\n")


MUTATIONS += [
    ("hash id cited next to a legacy id", with_hash, [
        ("check.py", [], 0), ("kbid.py", ["check"], 0, f"hash_ids={N_HASH + 1}"),
        ("rag.py", ["src", HID, "S100"], 0, "hash id test page"),
        ("rag.py", ["src", HID.upper()], 0, "hash id test page"),
        ("rag.py", ["--json", "search", "zanzibarquux", "-u"], 0, "", lambda o: json.loads(o)[0]["sources"] == ["S100", HID]),
        ("fetch.py", ["--status", "--source", HID], 0, "selected=1"),
        ("fetch.py", ["--status", "--json", "--file", "ad/hashid.md"], 0, "",
         lambda o: {x["id"] for x in json.loads(o)} == {HID, "S100"}),
        ("kbid.py", ["url", URL], 0, f"already in public/_sources.csv as {HID}")]),
    ("superseded_by names a known id", lambda d: add_sources(d, [ROW], {"S100": {"superseded_by": HID}}), [
        ("check.py", [], 0), ("rag.py", ["src", "S100"], 0, f"superseded by {HID}")]),
    ("superseded_by names an unknown id", lambda d: add_sources(d, patch={"S100": {"superseded_by": "S-aaaaaaaa"}}), [
        ("check.py", [], 1, "S100 superseded_by unknown source S-aaaaaaaa")]),
    ("superseded_by cycle", lambda d: add_sources(d, patch={"S100": {"superseded_by": "S101"}, "S101": {"superseded_by": "S102"},
                                                            "S102": {"superseded_by": "S100"}}), [
        ("check.py", [], 1, "forms a cycle")]),
    ("superseded_by itself", lambda d: add_sources(d, patch={"S100": {"superseded_by": "S100"}}), [
        ("check.py", [], 1, "forms a cycle")]),
    ("reuse class not in the list", lambda d: add_sources(d, patch={"S100": {"reuse": "free"}}), [
        ("check.py", [], 1, "S100 reuse 'free' is not one of copy, quote, paraphrase, unknown")]),
    ("reuse class missing", lambda d: add_sources(d, patch={"S100": {"reuse": ""}}), [
        ("check.py", [], 1, "S100 has no reuse class")]),
    ("licence missing", lambda d: add_sources(d, patch={"S100": {"licence": " "}}), [
        ("check.py", [], 1, "S100 has no licence")]),
    ("new source row without a reuse class", lambda d: add_sources(d, [{**ROW, "reuse": ""}]), [
        ("check.py", [], 1, f"{HID} has no reuse class")]),
    ("_sources.csv without reuse column", lambda d: without_column(d, "reuse"), [
        ("check.py", [], 1, "lacks column(s) reuse")]),
    ("hand-typed hash id", lambda d: add_sources(d, [{**ROW, "id": "S-abcdefgh"}]), [
        ("check.py", [], 1, "S-abcdefgh does not match its url"), ("kbid.py", ["check"], 1, "does not match")]),
    ("hash id collision", lambda d: add_sources(d, [{**ROW, "id": kbid.source_id(COLL_A), "url": COLL_A},
                                                    {**ROW, "id": "S99990", "url": COLL_B}]), [
        ("check.py", [], 1, f"hash id collision {kbid.source_id(COLL_A)}"), ("kbid.py", ["check"], 1, "collision")]),
    ("malformed id in _sources.csv", lambda d: add_sources(d, [{**ROW, "id": "S-12"}]), [
        ("check.py", [], 1, "malformed source id")]),
    ("malformed hash id cited", lambda d: write(d, P("ad/badid.md"), "x [DOC S-ZZZZ] y\n"), [
        ("check.py", [], 1, "cites unknown source S-ZZZZ")]),
    ("_sources.csv without superseded_by column", lambda d: write(d, P("_sources.csv"), "\n".join(
        ln.rpartition(",")[0] for ln in read(d, P("_sources.csv")).splitlines()) + "\n"), [
        ("check.py", [], 1, "lacks column(s) superseded_by"), ("rag.py", ["src", "S100"], 0, "S100"),
        ("fetch.py", ["--offline"], 0)]),
    ("duplicate QK answer id", lambda d: write(d, P("_answers.md"), read(d, P("_answers.md")) + DUP), [
        ("check.py", [], 1, "duplicate answer id QK-dup-answer"), ("kbid.py", ["answer", "dup answer"], 0, "already used")]),
    ("numbered QK answer id", lambda d: write(d, P("_answers.md"), read(d, P("_answers.md")) + "\n## QK7. q\n- x [UNK]\n"), [
        ("check.py", [], 1, "QK ids are QK-<slug>")]),
    ("slug QK answer id", lambda d: write(d, P("_answers.md"), read(d, P("_answers.md")) + "\n## QK-dataverse-onprem-sync. q\n- x [UNK]\n"), [
        ("check.py", [], 0)]),
]


@pytest.mark.parametrize("name,mutate,calls", MUTATIONS, ids=[c[0] if isinstance(c, tuple) else c.id for c in MUTATIONS])
def test_mutation(tmp_path, name, mutate, calls):
    d = copy_kb(tmp_path, "mut")
    mutate(d)
    failed = []
    for tool, args, rc, *rest in calls:
        why, _ = problems(d, tool, args, rc, *rest)
        if why:
            failed.append(f"{tool} {' '.join(args)[:80]}: {'; '.join(why)}")
    assert not failed, "\n".join(failed)


# ---------------------------------------------------------------- generated index files: build_index.py

def coverage(d):
    return {r["topic"]: r for r in csv.DictReader(io.StringIO(read(d, P("_coverage.csv"))))}


def test_index_extras_flow(tmp_path):
    """build_index.py: files: extras, topics without an article, ordering, the coverage page row, used_in, idempotency."""
    B, GEN = "build_index.py", (P("_coverage.csv"), COV, P("_sources.csv"))
    d = copy_kb(tmp_path, "index")
    call(d, B, ["--check"], 0, "out_of_date=0")
    art = lambda topic, extra="": (f"---\ntopic: {topic}\npriority: P3\nretrieved_utc: 2026-09-25\nsources: [S100, S101]\n"  # noqa: E731
                                   f"status: partial\n{extra}---\n# t\n## Summary\n## Facts\n- quux [DOC S100, S101]\n## Reference\n## Examples\n")
    write(d, P("ad/extras.md"), art("ad/extras", "files: [ad/extras-data/, ad/extras-data/digest.md]\n"))
    write(d, P("ad/extras.csv"), "a,b\nx,S102\n")
    write(d, P("ad/extras-data/digest.md"), art("ad/extras-data/digest"))
    write(d, P("ad/table-only.csv"), "op,sources\nx,S100;S101\ny,S101;S999999\n")
    write(d, D("index_extra.csv"), read(d, D("index_extra.csv")) + "ad/table-only,P3,partial,ad/table-only.csv\n")
    call(d, B, ["--check"], 1, "_coverage.csv: ad/extras row missing")  # the new article and extra row are detected
    call(d, B, [], 0, "written=3")
    cov = coverage(d)
    assert cov.get("ad/extras", {}).get("files") == "ad/extras.md;ad/extras.csv;ad/extras-data/;ad/extras-data/digest.md" \
        and cov["ad/extras"]["n_sources"] == "2" and "ad/extras-data/digest" not in cov, \
        f"files: extras follow the md and its stem siblings; a listed digest is no row: {cov.get('ad/extras')}"
    assert cov.get("ad/table-only", {}).get("n_sources") == "2" and cov["ad/table-only"]["files"] == "ad/table-only.csv", \
        f"topic without an article from index_extra.csv (known ids only): {cov.get('ad/table-only')}"
    topics = list(cov)
    assert topics == sorted(topics, key=lambda t: (t.split("/")[0], cov[t]["priority"], t)), "rows not ordered by domain, priority, topic"
    assert "| `ad/extras` | P3 | partial | `ad/extras.md`, `ad/extras.csv`, `ad/extras-data/`, `ad/extras-data/digest.md` | 2 |" \
        in read(d, COV), "coverage page row missing between the markers"
    src = {r["id"]: r for r in csv.DictReader(io.StringIO(read(d, P("_sources.csv"))))}
    assert "ad/extras.csv" in src["S102"]["used_in"].split(";") and "ad/table-only.csv" in src["S101"]["used_in"].split(";") \
        and not any(u.startswith(("_", ".")) or "/" not in u for r in src.values() for u in r["used_in"].split(";") if u), \
        f"used_in must cite csv files, never root or tool files: {src['S102']['used_in']}"
    before = {f: read(d, f) for f in GEN}
    call(d, B, [], 0, "written=0")
    assert all(read(d, f) == before[f] for f in GEN), "files changed on rebuild"
    assert all("\r" not in before[f] for f in GEN), "\\r in a generated file"
    call(d, B, ["--check"], 0, "out_of_date=0")
    # build_index counts known ids only; check.py reports the unknown one in the data file's sources column
    call(d, "check.py", [], 1, "ad/table-only.csv:3 cites unknown source S999999")


T0 = next(iter(csv.DictReader(io.StringIO(read(KB, P("_coverage.csv"))))))["topic"]
HAND_EDITS = [  # (name, mutate(copy), --check exit, expect, a build repairs it)
    ("hand-edited n_sources", lambda d: write(d, P("_coverage.csv"), "\n".join(
        ln.rpartition(",")[0] + ",999" if ln.startswith(T0 + ",") else ln for ln in read(d, P("_coverage.csv")).split("\n"))),
     1, f"_coverage.csv: {T0}: n_sources", True),
    ("hand-added coverage row", lambda d: write(d, P("_coverage.csv"), read(d, P("_coverage.csv")) + "zz/ghost,P0,complete,zz/ghost.md,1\n"),
     1, "zz/ghost is not a topic", True),
    ("rows swapped", lambda d: write(d, P("_coverage.csv"), (lambda ls: "\n".join([ls[0], ls[2], ls[1]] + ls[3:]))(
        read(d, P("_coverage.csv")).split("\n"))), 1, "row order", True),
    ("CRLF _coverage.csv", lambda d: write(d, P("_coverage.csv"), read(d, P("_coverage.csv")).replace("\n", "\r\n")), 1, "_coverage.csv", True),
    ("hand-edited coverage page row", lambda d: write(d, COV, read(d, COV).replace(
        f"| `{T0}` |", f"| `{T0}` | P9 |", 1)), 1, "public/_coverage.md: coverage table differs", True),
    ("hand-edited used_in", lambda d: add_sources(d, patch={"S100": {"used_in": "dsc/nothing.md"}}), 1, "S100 used_in", True),
    ("front matter changed, index not rebuilt", lambda d: write(d, P(T0 + ".md"), read(d, P(T0 + ".md")).replace(
        "\nstatus: ", "\nstatus: unknown\nold_status: ", 1)), 1, f"_coverage.csv: {T0}: status", True),
    ("coverage page without markers", lambda d: write(d, COV, read(d, COV).replace(
        "<!-- coverage:start -->", "")), 2, "public/_coverage.md lacks the", False),
    ("files: names a missing path (warned, lint errors)", lambda d: write(d, P(T0 + ".md"), read(d, P(T0 + ".md")).replace(
        "\nstatus: ", "\nfiles: [ad/nope.csv]\nstatus: ", 1)), 1, "files: lists missing ad/nope.csv", True),
    ("_sources.csv deleted", lambda d: os.remove(os.path.join(d, P("_sources.csv"))), 2, "cannot read _sources.csv", False),
]


@pytest.mark.parametrize("name,mutate,rc,expect,fixes", HAND_EDITS, ids=ids(HAND_EDITS))
def test_index_hand_edit(tmp_path, name, mutate, rc, expect, fixes):
    d = copy_kb(tmp_path, "index")
    mutate(d)
    call(d, "build_index.py", ["--check"], rc, expect)
    if fixes:
        call(d, "build_index.py", [], 0)
        call(d, "build_index.py", ["--check"], 0, "out_of_date=0")


# ---------------------------------------------------------------- post-merge cleanup: kbgit.py fix / fmt (git merges: test_merge.py)

def test_kbgit_fixes_union_merged_ledgers(tmp_path):
    """A union-style merge result (repeated header, duplicate and split rows, markers) is fixed in one run and the next
    run changes nothing."""
    G = "kbgit.py"
    d = copy_kb(tmp_path, "kbgit")
    call(d, G, ["fix", "--check"], 0, "changed=0")
    call(d, G, ["fmt", "--check"], 0, "changed=0")
    src = read(d, P("_sources.csv"))
    head, body = src.split("\n", 1)
    lines = body.splitlines()
    newer = lines[0].replace(",2026-", ",2027-", 1)
    write(d, P("_sources.csv"), head + "\n" + "\n".join(lines[::-1]) + "\n" + "<<<<<<< ours\n" + lines[1] + "\n=======\n"
          + head + "\n" + newer + "\n>>>>>>> theirs\n")
    write(d, P("_answers.md"), read(d, P("_answers.md")) + read(d, P("_answers.md")).split("\n## ", 2)[1].join(["\n## ", ""]))
    call(d, G, ["fmt"], 2, "conflict markers")
    call(d, G, ["fix", "--check"], 1, "WOULD CHANGE " + P("_sources.csv"))
    call(d, G, ["fix"], 0, "removed 1 repeated header")
    call(d, G, ["fix", "--check"], 0, "changed=0")
    assert read(d, P("_sources.csv")) == src.replace(lines[0], newer), "rows not back in canonical order with the newer duplicate merged"
    assert read(d, P("_answers.md")) == read(KB, P("_answers.md")), "the repeated answer was not dropped"
    call(d, "check.py", [], 0)


def test_kbgit_collision_needs_a_git_base(tmp_path):
    d = copy_kb(tmp_path, "kbgit")
    add_sources(d, [{"id": "S100", "url": "https://collision.example.com/other"}])
    call(d, "kbgit.py", ["fix"], 2, "rerun with --base")
    call(d, "kbgit.py", ["fix", "--base", "HEAD~1"], 2, "not a commit")  # a copy outside a git clone


def test_kbgit_needs_a_human_writes_nothing(tmp_path):
    d = copy_kb(tmp_path, "kbgit")
    write(d, P("_answers.md"), read(d, P("_answers.md")) + "\n## QK-dup. a\n\none\n\n## QK-dup. a\n\ntwo\n")
    write(d, P("_gaps.md"), read(d, P("_gaps.md")) * 2)
    before = read(d, P("_gaps.md"))
    call(d, "kbgit.py", ["fix"], 2, "QK-dup appears 2 times")
    assert read(d, P("_gaps.md")) == before


# ---------------------------------------------------------------- fetch.py --diff / --status against a local web server

@pytest.fixture
def www(tmp_path):
    root = str(tmp_path / "www")
    os.makedirs(root)
    handler = functools.partial(type("Quiet", (http.server.SimpleHTTPRequestHandler,), {"log_message": lambda *x: None}), directory=root)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield root, f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_fetch_diff_and_status_flow(tmp_path, www):
    """--diff/--status: baseline, change detection, text diff, no-save, errors, selection, HTML normalization."""
    root, url = www
    page = lambda body, nav="menu": f"<html><head><title>t</title></head><body><nav>{nav}</nav><main><h1>Doc</h1>{body}</main></body></html>"  # noqa: E731
    write(root, "a.html", page("<p>line one</p><p>line two</p>"))
    write(root, "b.txt", "plain text\n")
    d = copy_kb(tmp_path, "diff")
    rows = list(csv.DictReader(io.StringIO(read(d, P("_sources.csv")))))
    for r in rows:  # S100 -> html page, S101 -> text file, S102 -> dead port, S103 -> not http
        r["url"] = {"S100": f"{url}/a.html", "S101": f"{url}/b.txt", "S102": "http://127.0.0.1:9/x", "S103": "file:///etc/hosts"}.get(r["id"], r["url"])
        if r["id"] in ("S100", "S101"):
            r["version_or_date"], r["artifact_sha256"] = "test", ""
    buf = io.StringIO()
    w = csv.DictWriter(buf, list(rows[0].keys()), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    write(d, P("_sources.csv"), buf.getvalue())
    F = ["--delay", "0", "--timeout", "5"]
    two = ["--source", "S100", "--source", "S101"]
    call(d, "fetch.py", ["--status", *two], 0, "never_fetched=2")
    call(d, "fetch.py", ["--diff", *two, *F], 0, "new=2")
    call(d, "fetch.py", ["--status", *two, "--json"], 0,  # state and snapshots saved
         check=lambda o: all(x["fetched_utc"] for x in json.loads(o)) and any(os.path.isfile(os.path.join(d, c, "_cache/snapshots/S100.txt")) for c in (".", P("."))))
    call(d, "fetch.py", ["--diff", *two, *F], 0, "unchanged=2")
    write(root, "a.html", page("<p>line one</p><p>line two</p>", nav="other menu"))
    call(d, "fetch.py", ["--diff", "--source", "S100", *F], 0, "unchanged=1")  # a change outside <main> is ignored
    write(root, "a.html", page("<p>line one</p><p>line 2 edited</p><p>added line</p>"))
    call(d, "fetch.py", ["--diff", "--source", "S100", "--no-save", *F], 1, "changed=1")
    call(d, "fetch.py", ["--diff", "--source", "S100", "--no-save", *F], 1, "(not saved)")  # --no-save kept the baseline
    call(d, "fetch.py", ["--diff", "--source", "S100", "--full", "--max-lines", "2", "--no-save", *F], 1, "cut at --max-lines 2")
    call(d, "fetch.py", ["--diff", "--source", "S100", "--full", "--json", *F], 1,
         check=lambda o: (lambda j: j["changed"] == 1 and "+added line" in j["sources"][0]["diff"]
                          and j["sources"][0]["added"] == 2 and j["sources"][0]["removed"] == 1)(json.loads(o)))
    call(d, "fetch.py", ["--diff", "--source", "S100", *F], 0, "unchanged=1")  # the change is now the baseline
    write(root, "b.txt", "plain text\nmore\n")
    call(d, "fetch.py", ["--diff", *two, "--full", *F], 1, "+more")
    call(d, "fetch.py", ["--diff", "--source", "S102", *F], 2, "ERROR")  # a dead host is an error
    call(d, "fetch.py", ["--diff", "--source", "S103", *F], 2, "not an http(s) url")
    call(d, "fetch.py", ["--status", "--source", "S102"], 0, "with_error=1")  # the error is recorded in the state
    call(d, "fetch.py", ["--diff", *two, "--older-than", "1", *F], 0, "selected=0")
    call(d, "fetch.py", ["--diff", "--topic", "nope/nothing", *F], 2, "no topic")
    call(d, "fetch.py", ["--status", "--source", "S99999999"], 2, "unknown source")
    call(d, "fetch.py", ["--file", "README.md"], 2, "need --diff or --status")
    n = lambda o: len(json.loads(o))  # noqa: E731
    f_ = call(d, "fetch.py", ["--status", "--json", "--file", "dsc/what-if.md"], 0, check=lambda o: n(o) > 0)
    call(d, "fetch.py", ["--status", "--json", "--topic", "dsc/what-if"], 0, check=lambda o: n(o) > 0)
    call(d, "fetch.py", ["--status", "--json", "--dir", "dsc"], 0,  # --dir is a superset of --file
         check=lambda o: {x["id"] for x in json.loads(f_)} <= {x["id"] for x in json.loads(o)})
    call(d, "fetch.py", ["--status", "--json"], 0, check=lambda o: n(o) == len(rows))  # no selection = every source
