"""The checks the kb's content lives by, over the live kb: check.py (sources, citations, tags), build_index.py --check
(the generated index), the lookup eval (rag.py eval), and the pack format. Each gate also fails on a planted input. The pack index's unit cache is pinned on
a planted fixture root, not on the live kb."""
import csv, os, re, sqlite3, subprocess, sys


import pytest

import kbcommon, kbfacts, kbid
from conftest import TOOLS, tool

EVAL_CSV = os.path.join(kbcommon.PUBLIC, kbcommon.DATA_DIR, "lookup_eval.csv")
SID = "FXT-" + "a" * 8  # not a source of the fixture root's _sources.csv


def eval_rows():
    with open(EVAL_CSV, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def good_row():
    """A live eval row that expects one article and a good verdict."""
    return next(r for r in eval_rows() if r["expect_verdict"] == "good" and r["expect_paths"].count(";") == 0
                and r["expect_paths"] and not r["allow_weak"])


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def fixture_root(path, cited):
    """The smallest root check.py accepts: one article citing `cited`, an empty source ledger."""
    write(path / "_root.md", "---\nroot: fixture\nid_prefix: FXT\nvisibility: internal\ndescription: a test root\n---\n")
    write(path / "print" / "queues.md",
          "---\ntopic: print/queues\npriority: P1\napplies_to: \"PL-SRV-0042 print servers\"\nretrieved_utc: 2026-09-26\n"
          f"sources: [{cited}]\nstatus: partial\n---\n\n# Print queues\n\n## Summary\nKept 14 days.\n\n## Facts\n"
          f"- Finished jobs are kept for 14 days. [DOC {cited}]\n\n## Reference\n\n## Examples\n")
    write(path / "_sources.csv", "id,url,title,publisher,licence,reuse,retrieved_utc,version_or_date,artifact_sha256,"
                                 "used_in,superseded_by\n")
    for name in ("_answers.md", "_conflicts.md"):
        write(path / name, "# " + name + "\n")
    write(path / "_gaps.md", "# Gaps\n")


def test_check_py_passes_on_the_live_kb():
    code, out = tool("check.py")
    assert code == 0, out[-3000:]


def test_check_py_names_an_article_citing_an_unknown_source(tmp_path):
    root = tmp_path / "root"
    fixture_root(root, SID)
    env = {**os.environ, "KB_ROOTS": str(root)}
    code, out = tool("check.py", "--root", "fixture", env=env)
    assert code == 1 and "print/queues.md" in out and f"cites unknown source {SID}" in out, out[-2000:]


def test_lint_names_a_facts_line_with_a_second_bullet_after_its_tag(tmp_path):
    root = tmp_path / "root"
    fixture_root(root, SID)
    art = root / "print" / "queues.md"
    joined = f"- Held jobs stay until released. [DOC {SID}]- Paused queues keep their jobs. [DOC {SID}]"
    write(art, art.read_text(encoding="utf-8").replace(
        "## Reference", f"- Queues 1 - 3 are shared. [DOC {SID}]\n{joined}\n\n## Reference"))
    at = art.read_text(encoding="utf-8").split("\n").index(joined) + 1
    env = {**os.environ, "KB_ROOTS": str(root)}
    code, out = tool("build_index.py", "--root", "fixture", env=env)
    assert code == 0, out[-2000:]
    code, out = tool(os.path.join("..", ".claude", "skills", "kb-verify", "lint.py"), "fixture/", env=env)
    flagged = re.findall(r"^ERROR (\S+): Facts line holds a second bullet", out, re.M)
    assert code == 1 and flagged == [f"fixture/print/queues.md:{at}"], out[-2000:]


def test_build_index_check_passes_on_the_live_kb():
    code, out = tool("build_index.py", "--check")
    assert code == 0, out[-3000:]


def test_lookup_eval_passes_on_the_live_kb():
    code, out = tool("rag.py", "eval")
    m = re.search(r"^questions=(\d+) passed=(\d+) verdict_ok=\d+ found_ok=\d+", out, re.M)
    assert m, out[-1500:]
    assert code == 0 and int(m.group(1)) > 0 and m.group(1) == m.group(2), out[-3000:]


def test_lookup_eval_fails_on_a_wrong_expected_article(tmp_path):
    row = good_row()
    wrong = dict(row, id="EV-planted-wrong-article",
                 expect_paths="dsc/what-if.md" if row["expect_paths"] != "dsc/what-if.md" else "auth/kerberos.md")
    bad = tmp_path / "lookup_eval.csv"
    with open(bad, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row), lineterminator="\n")
        w.writeheader()
        w.writerows([wrong, row])
    code, out = tool("rag.py", "eval", "--file", str(bad))
    assert code == 1 and f"FAIL {wrong['id']}" in out and "questions=2 passed=1" in out, out[-1500:]
    assert f" {row['id']} " not in out, out[-1500:]  # a passing row is printed only with --all
    code, out = tool("rag.py", "eval", "--file", str(bad), "--min", "1", "--all")  # the held-out rate's form: at least N pass
    assert code == 0 and "questions=2 passed=1" in out and f"ok   {row['id']} " in out, out[-1500:]


def test_lookup_eval_fails_on_a_phrase_the_self_docs_do_not_hold(tmp_path):
    with open(os.path.join(kbcommon.SELF, kbcommon.DATA_DIR, "lookup_eval.csv"), encoding="utf-8", newline="") as f:
        row = next(csv.DictReader(f))
    bad = tmp_path / "lookup_eval.csv"
    with open(bad, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row), lineterminator="\n")
        w.writeheader()
        w.writerow(dict(row, expect_text="a phrase no rule doc holds"))
    code, out = tool("rag.py", "eval", "--file", str(bad), "--root", "_self")
    assert code == 1 and f"FAIL {row['id']}" in out and "failed=anchor" in out, out[-1500:]


def test_pack_prints_coverage_and_fact_lines_with_path_line_and_tag():
    code, out = tool("rag.py", "pack", good_row()["question"])
    assert code == 0, out[-1500:]
    assert re.search(r"^coverage: good\b", out, re.M), out[:1500]
    assert re.search(r"\S+\.md:\d+.*\[(DOC|CODE|DER|COMMUNITY|UNK)\b", out), out[:1500]


# rag.py pack on the fixture root alone (serve_only), so a cold index weighs one article and not the live kb
PACK_FIXTURE = ("import sys; sys.path.insert(0, sys.argv[1]); import kbcommon; kbcommon.serve_only(['fixture']); "
                "import rag; sys.argv = ['rag.py', 'pack', sys.argv[2]]; rag.main()")


def variant(orig):
    """A function that does what `orig` does with other code: _weigh_code() digests the code, not the behaviour."""
    def v(*args, **kwargs):
        return orig(*args, **kwargs)
    return v


def test_unit_cache_equals_a_fresh_weighing_re_weighs_on_each_key_input_and_finds_an_edited_fact(tmp_path, monkeypatch):
    cache = tmp_path / "idx" / kbfacts.UNIT_CACHE
    monkeypatch.setenv("KB_INDEX", str(cache.parent))
    monkeypatch.delenv("KB_DOC2QUERY", raising=False)
    monkeypatch.setattr(kbfacts, "UNIT_CACHE_SLACK", 1000)  # no pruning: a key that did not change is still a row
    summary = ["Kept 14 days."]
    monkeypatch.setattr(kbfacts, "summary_text", lambda rel: summary[0])
    base = dict(path="public/print/queues.md", section="Facts", text="Finished jobs are kept for 14 days.",
                tags=[{"kind": "DOC"}], lead="", anchors=[])
    metas = {base["path"]: {"title": "Print queues"}}
    exps = {kbfacts.fact_key(base["text"]): ["how long are print jobs kept"]}

    def weigh(unit=None, metas=metas, exps=exps):
        return kbfacts.weighed([dict(base, **(unit or {}))], metas, exps)[0]

    def keys():
        con = sqlite3.connect(cache)
        try:
            return {k for (k,) in con.execute("SELECT k FROM u")}
        finally:
            con.close()

    kbfacts._weigh_code.cache_clear()
    first = weigh()
    assert len(keys()) == 1 and first["tf"] and first["own"]
    with monkeypatch.context() as m:  # a hit weighs nothing, and equals a weighing with no cache (KB_INDEX=0)
        m.setattr(kbfacts, "_weigh", lambda *a: pytest.fail("the unit was weighed again"))
        hit = weigh()
    with monkeypatch.context() as m:
        m.setenv("KB_INDEX", "0")
        fresh = weigh()
    assert [hit[k] for k in ("len", "own", "tf")] == [fresh[k] for k in ("len", "own", "tf")]
    assert len(keys()) == 1

    cases = {  # each input _unit_key hashes: a change must make a new key, so the unit is weighed again
        "INDEX_VERSION": lambda m: m.setattr(kbfacts, "INDEX_VERSION", kbfacts.INDEX_VERSION + 1),
        "KB_DOC2QUERY": lambda m: m.setenv("KB_DOC2QUERY", "1"),
        "TITLE_WEIGHT": lambda m: m.setattr(kbfacts, "TITLE_WEIGHT", kbfacts.TITLE_WEIGHT + 1),
        "SUMMARY_WEIGHT": lambda m: m.setattr(kbfacts, "SUMMARY_WEIGHT", kbfacts.SUMMARY_WEIGHT + 1),
        "EXPANSION_WEIGHT": lambda m: m.setattr(kbfacts, "EXPANSION_WEIGHT", kbfacts.EXPANSION_WEIGHT + 1),
        "STOP": lambda m: m.setattr(kbfacts, "STOP", kbfacts.STOP | {"zzstop"}),
        "kbid.STOP": lambda m: m.setattr(kbid, "STOP", kbid.STOP | {"zzstop"}),
    }
    for name in ("WORD", "CAMEL", "NUMBER"):
        cases[name] = lambda m, name=name: m.setattr(kbfacts, name, re.compile(getattr(kbfacts, name).pattern + "|zz"))
    for name in ("_weigh", "terms", "stem", "bare"):
        cases[name + " code"] = lambda m, name=name: m.setattr(kbfacts, name, variant(getattr(kbfacts, name)))
    inputs = {
        "path": {"unit": {"path": "public/print/other.md"}},
        "title": {"metas": {base["path"]: {"title": "Print queue"}}},
        "lead": {"unit": {"lead": "Jobs"}},
        "section": {"unit": {"section": "Reference"}},
        "text": {"unit": {"text": base["text"] + " Held jobs wait."}},
        "expansions": {"exps": {kbfacts.fact_key(base["text"]): ["how long are queued jobs kept"]}},
        "anchors": {"unit": {"anchors": [(1, "how long are print jobs kept")]}},
    }
    cases["summary"] = lambda m: summary.__setitem__(0, "Kept 21 days.")
    for name in sorted(cases) + sorted(inputs):
        before = keys()
        with monkeypatch.context() as m:
            try:
                if name in cases:
                    cases[name](m)
                    kbfacts._weigh_code.cache_clear()  # the digest is computed once: recompute it for the changed code
                weigh(**inputs.get(name, {}))
            finally:
                summary[0] = "Kept 14 days."
                kbfacts._weigh_code.cache_clear()
        assert keys() - before, f"a change to {name} reused the cached weighing"

    # an edited fact is found by rag.py pack: the unit cache holds the unit weighed before the edit
    root = tmp_path / "root"
    fixture_root(root, SID)
    art = root / "print" / "queues.md"
    env = {**os.environ, "KB_ROOTS": str(root), "KB_INDEX": str(tmp_path / "packidx")}
    env.pop("KB_DOC2QUERY", None)

    def pack():
        p = subprocess.run([sys.executable, "-c", PACK_FIXTURE, TOOLS, "which sweeper purges finished jobs"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
        assert p.returncode == 0, p.stdout[-1500:] + p.stderr[-1500:]
        return p.stdout

    assert not re.search(r"^coverage: good\b", pack(), re.M)
    write(art, art.read_text(encoding="utf-8").replace(
        "kept for 14 days.", "kept for 14 days, then purged by the sweeper."))
    out = pack()
    assert re.search(r"^coverage: good\b", out, re.M) and re.search(r"queues\.md:\d+ .*sweeper.*\[DOC ", out), out[:1500]
