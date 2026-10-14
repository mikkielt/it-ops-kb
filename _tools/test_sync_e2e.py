"""`kbgit.py sync --push` end to end in a throwaway clone and bare origin: a content commit reaches main, a commit the
gate rejects does not, a held-out row that rewords a tuned row is refused (and a changed expansions.csv runs that check),
a passing gate test run is reused for the same tree, and a code commit goes to a code/ branch while main stays."""
import json, os, re

import pytest

from conftest import requires_git

pytestmark = [pytest.mark.git, requires_git]

ENV = {"KB_SYNC_NO_TESTS": "1"}


def clone(scenario):
    # the seed copies files without their exec bit, and install-hooks sets it: that is no change to sync
    c = scenario.clone()
    c.git("config", "core.fileMode", "false")
    return c


def sync(repo):
    return repo.kbgit("sync", "--push", env=ENV)


def article(c, name, sid, hooks=True):
    """A small kb article citing the source `sid`, then the index rebuilt, committed (`hooks` False: past the commit
    hooks, for a scenario that tests the gate and not them)."""
    c.write(f"kb/public/windows/sync-e2e-{name}.md",
            f"---\ntopic: windows/sync-e2e-{name}\npriority: P3\napplies_to: [test]\nretrieved_utc: 2026-09-26\n"
            f"sources: [{sid}]\nstatus: partial\n---\n# Sync e2e {name}\n\n## Summary\n\nTest.\n\n## Facts\n\n"
            f"- A probe fact. [DOC {sid}]\n\n## Reference\n\n## Examples\n")
    p = c.tool("build_index.py")
    assert p.returncode == 0, p.stdout + p.stderr
    if hooks:
        c.commit(f"docs(kb): sync e2e {name}")
    else:
        c.git("add", "-A")
        c.git("commit", "-q", "--no-verify", "-m", f"docs(kb): sync e2e {name}")


def gate_tests_reuse(c, monkeypatch, capsys):
    """The gate's tests.py (KB_TESTS_FAST=1 --changed) in clone `c`, pytest faked: a passing run is reused for the same
    tree, never after a tracked test file's edit (the planted failure), with an untracked test file, with --no-reuse
    or after a failing run."""
    import tests as kbtests
    monkeypatch.setattr(kbtests, "KB", c.path)
    monkeypatch.setattr(kbtests, "TOOLS", c.file("_tools"))
    monkeypatch.setattr(kbtests, "compile_report", lambda tools=None: 0)
    monkeypatch.setenv("KB_TESTS_FAST", "1")
    runs, rows, outcome = [], [], [0]
    monkeypatch.setattr(kbtests, "run_pytest", lambda args: runs.append(args) or {"exit": outcome[0], "ms": 1, "files": {}})
    monkeypatch.setattr(kbtests, "record_run", lambda mode, entry, args, workers=None, reused=False: rows.append(
        (mode, entry["exit"], reused)))

    def run(*extra):
        code = kbtests.run_main(["--changed", "HEAD", *extra])
        return code, len(runs), capsys.readouterr().out

    probe, stray = "_tools/test_sync_e2e.py", "_tools/test_sync_e2e_stray.py"
    c.append(probe, "\n# edited\n")
    assert run()[:2] == (0, 1)
    code, n, out = run()
    assert (code, n) == (0, 1) and re.search(r"^reused: [0-9a-f]{16} from \d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$", out, re.M), out
    assert rows[-1] == ("changed", 0, True), rows
    assert run(kbtests.NO_REUSE)[:2] == (0, 2)
    c.append(probe, "# edited after the passing run\n")  # planted: a tracked test file's edit changes the key
    assert run()[:2] == (0, 3)
    c.write(stray, "")
    code, n, out = run()
    assert (code, n) == (0, 4) and f"no reuse: untracked {stray}" in out, out
    assert run()[:2] == (0, 5)
    os.unlink(c.file(stray))
    outcome[0] = 1
    c.append(probe, "# failing\n")
    assert run()[:2] == (1, 6) and run()[:2] == (1, 7)  # a failing run records no key
    assert ("changed", 1, False) in rows and json.loads(c.read("_cache/tests/results.json"))["runs"]


def test_content_commit_reaches_main_and_a_red_gate_stops_the_next(scenario):
    c = clone(scenario)
    article(c, "content", "S100")
    r = sync(c)
    assert r.returncode == 0, r.stdout + r.stderr
    pushed = c.rev("HEAD")
    assert scenario.origin.rev("main") == pushed
    assert "KB-Topics:" in c.git("log", "-1", "--format=%B")


class TestRedGate:
    def test_a_red_gate_leaves_main_where_the_last_push_put_it(self, scenario):
        # the commit before it reaches main by a plain push, so the one sync here is the red one
        c = clone(scenario)
        article(c, "content", "S100", hooks=False)
        c.git("push", "-q", "--no-verify", "origin", "HEAD:main")
        pushed = c.rev("HEAD")
        assert scenario.origin.rev("main") == pushed
        article(c, "planted", "S999999", hooks=False)  # a source id the table lacks: check.py fails
        r = sync(c)
        assert r.returncode == 1, r.stdout + r.stderr
        assert "check.py" in r.stdout and "ok: sources" not in r.stdout, r.stdout
        assert scenario.origin.rev("main") == pushed


class TestGateTestsReuse:
    def test_a_passing_gate_test_run_is_reused_for_the_same_tree_and_not_after_an_edit(self, scenario, monkeypatch, capsys):
        gate_tests_reuse(clone(scenario), monkeypatch, capsys)


def test_heldout_reword_is_refused_at_the_gate(scenario):
    c = clone(scenario)
    article(c, "heldout", "S100")
    expect = "windows/sync-e2e-heldout.md"
    tuned = "How does the sync gate treat the probe fact of the sync end to end article?"
    rows = {"lookup_eval.csv": ("EV-sync-e2e-heldout", tuned),
            "lookup_heldout.csv": ("HO-sync-e2e-heldout", tuned.replace("How does the sync gate", "How does the gate"))}
    for name, (rid, question) in rows.items():
        c.append(f"kb/public/_retrieval/{name}", f"{rid},{question},{expect},good,\n")
    c.commit("docs(kb): sync e2e held-out probe")
    before = scenario.origin.rev("main")
    r = sync(c)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "REWORD HO-sync-e2e-heldout ~ EV-sync-e2e-heldout" in r.stdout, r.stdout
    assert scenario.origin.rev("main") == before
    # a range that changes only a root's doc2query expansions, or only one of its articles, runs the same check on
    # that root's held-out file; a ledger of the root is no article
    import kg_sync
    held = ["kb/public/_retrieval/lookup_heldout.csv"]
    paths = ["kb/public/_retrieval/doc2query/expansions.csv", "kb/public/windows/sync-e2e-heldout.md"]
    assert [p for p, _ in kg_sync.heldout_checks(paths)] == held
    assert [p for p, _ in kg_sync.heldout_checks(paths[1:])] == held
    assert kg_sync.heldout_checks(["kb/public/_answers.md", "kb/_self/git.md"]) == []


def test_code_commit_goes_to_a_branch(scenario):
    c = clone(scenario)
    before = scenario.origin.rev("main")
    c.write("_tools/sync_e2e_probe.txt", "code\n")
    c.git("add", "_tools/sync_e2e_probe.txt")
    c.git("commit", "-q", "-m", "chore(tools): sync end-to-end probe\n\nSelf-Reviewed: kb/_self/git.md\nKB-Auto: querylog")
    head = c.rev("HEAD")
    r = sync(c)
    assert r.returncode == 0, r.stdout + r.stderr
    assert scenario.origin.rev("main") == before
    branches = scenario.origin.git("for-each-ref", "--format=%(refname:short) %(objectname)", "refs/heads/code/")
    assert [ln.split()[1] for ln in branches.splitlines()] == [head], branches


class TestStrayTrailer:
    def test_a_code_commit_with_no_trailer_git_reads_is_refused(self, scenario):
        c = clone(scenario)
        before = scenario.origin.rev("main")
        c.write("_tools/sync_e2e_probe.txt", "code\n")
        # a code change needs a KB-Work or KB-Auto trailer (check-trailers); the scenario has no sprint to name. A
        # Self-Reviewed line above a blank line is no trailer git reads: the commit-msg hook warns, sync refuses the push
        c.git("add", "_tools/sync_e2e_probe.txt")
        stray = "not a trailer: 'Self-Reviewed: kb/_self/git.md'"
        p = c.run_git("commit", "-q", "-m", "chore(tools): sync end-to-end probe", "-m", "Self-Reviewed: kb/_self/git.md",
                      "-m", "KB-Auto: querylog")
        assert p.returncode == 0 and stray in p.stderr, p.stdout + p.stderr
        r = sync(c)
        assert r.returncode == 1 and stray in r.stdout, r.stdout + r.stderr
        assert scenario.origin.rev("main") == before
