"""`kbgit.py sync --push` end to end in a throwaway clone and bare origin: a content commit reaches main, a commit the
gate rejects does not, and a code commit goes to a code/ branch while main stays."""
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


def article(c, name, sid):
    """A small kb article citing the source `sid`, then the index rebuilt, committed."""
    c.write(f"kb/public/windows/sync-e2e-{name}.md",
            f"---\ntopic: windows/sync-e2e-{name}\npriority: P3\napplies_to: [test]\nretrieved_utc: 2026-09-26\n"
            f"sources: [{sid}]\nstatus: partial\n---\n# Sync e2e {name}\n\n## Summary\n\nTest.\n\n## Facts\n\n"
            f"- A probe fact. [DOC {sid}]\n\n## Reference\n\n## Examples\n")
    p = c.tool("build_index.py")
    assert p.returncode == 0, p.stdout + p.stderr
    c.commit(f"docs(kb): sync e2e {name}")


def test_content_commit_reaches_main_and_a_red_gate_stops_the_next(scenario):
    c = clone(scenario)
    article(c, "content", "S100")
    r = sync(c)
    assert r.returncode == 0, r.stdout + r.stderr
    pushed = c.rev("HEAD")
    assert scenario.origin.rev("main") == pushed
    assert "KB-Topics:" in c.git("log", "-1", "--format=%B")
    article(c, "planted", "S999999")  # a source id the table lacks: check.py fails
    r = sync(c)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "check.py" in r.stdout and "ok: sources" not in r.stdout, r.stdout
    assert scenario.origin.rev("main") == pushed


def test_code_commit_goes_to_a_branch(scenario):
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
    c.git("commit", "-q", "--amend", "-m", "chore(tools): sync end-to-end probe\n\nSelf-Reviewed: kb/_self/git.md\n"
          "KB-Auto: querylog")
    head = c.rev("HEAD")
    r = sync(c)
    assert r.returncode == 0, r.stdout + r.stderr
    assert scenario.origin.rev("main") == before
    branches = scenario.origin.git("for-each-ref", "--format=%(refname:short) %(objectname)", "refs/heads/code/")
    assert [ln.split()[1] for ln in branches.splitlines()] == [head], branches
