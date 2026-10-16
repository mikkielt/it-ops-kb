"""`kbgit.py sync --push` end to end in a throwaway clone and bare origin: a commit the gate rejects does not reach main,
and a code commit goes to a code/ branch while main stays."""
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
