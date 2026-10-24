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


def test_pool_gate_refuses_only_the_defects_a_landing_adds(monkeypatch):
    """The gate's `pool check` fails on the pool's old defects too: a defect line the base also prints is shown and not
    refused, one the landing adds (the entry a gap row names closed) refuses; the route the pack prints is not part of
    a defect."""
    import kg_sync
    old = "pool check: BP-00000001: expected route web but the pack prints split for its question (gap: Q1)"
    new = "pool check: BP-00000002: its entry _gaps.md#12345678 is no longer open in _gaps.md (closed, narrowed or gone)"
    warn = "pool check: BP-00000003: warning: its pack cites no source past its freshness lifetime now"
    monkeypatch.setattr(kg_sync, "base_tool", lambda rev, name, *a: (1, old.replace("split", "good") + "\n" + warn))
    code, out = kg_sync.pool_gate(1, "\n".join([old, warn]), "abc")
    assert code == 0 and "refused=0 old=1" in out, out
    code, out = kg_sync.pool_gate(1, "\n".join([old, new, warn]), "abc")
    assert code == 1 and f"added by the landing: {new[len('pool check: '):]}" in out and "refused=1 old=1" in out, out
    assert kg_sync.pool_gate(1, new, None)[0] == 0  # no base: printed, nothing told apart


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


@pytest.mark.parametrize("scope", ["me", "team", "org"])
def test_upstream_merge(scenario, scope):
    """`kbgit.py upstream` per scope: the dry run plans and changes nothing, `me` rebases the local commits (a commit the
    upstream main holds drops out), `team` and `org` merge and keep every local commit; only the upstream is fetched."""
    public = scenario.bare("upstream.git")
    u = scenario.clone(hooks=False)
    u.write("probe/a.txt", "base\n")
    u.write("probe/b.txt", "base\n")
    u.commit("chore: probe files")
    u.git("push", "-q", "origin", "HEAD:main")
    u.git("push", "-q", public.path, "HEAD:main")
    c = scenario.clone(hooks=False)
    c.git("config", "core.fileMode", "false")
    c.git("remote", "add", "upstream", public.path)
    c.git("remote", "set-url", "--push", "upstream", "DISABLED")
    c.git("config", "kb.upstreamRemote", "upstream")
    c.git("config", "kb.scope", scope)
    c.write("probe/a.txt", "local\n")
    held = c.commit("chore: local a")
    c.write("probe/b.txt", "mine\n")
    kept = c.commit("chore: local b")
    c.write("local/own.txt", "own\n")
    c.commit("chore: local own file")
    c.git("push", "-q", "origin", "HEAD:main")  # the integration remote holds these three
    pushed = c.rev("HEAD")
    u.write("probe/a.txt", "local\n")  # the upstream main now holds the change of the first local commit
    u.write("probe/new.txt", "new\n")
    u.commit("chore: upstream moves")
    u.git("push", "-q", public.path, "HEAD:main")
    w = scenario.clone(hooks=False)  # origin moves too: only the upstream may be fetched
    w.write("probe/elsewhere.txt", "x\n")
    w.commit("chore: origin moves")
    w.git("push", "-q", "origin", "HEAD:main")
    origin_seen = c.rev("refs/remotes/origin/main")

    r = c.kbgit("upstream", "--dry-run")
    assert r.returncode == 0, r.stdout + r.stderr
    lines = r.stdout.splitlines()
    assert any(held[:9] in ln and "resolved upstream" in ln for ln in lines), r.stdout
    assert any(kept[:9] in ln and "probe/b.txt" in ln and "resolved" not in ln for ln in lines), r.stdout
    assert "own.txt" not in r.stdout and "dry run: nothing" in r.stdout, r.stdout
    assert (c.rev("HEAD"), c.git("status", "--porcelain")) == (pushed, ""), r.stdout

    r = c.kbgit("upstream")
    assert r.returncode == 0, r.stdout + r.stderr
    assert c.rev("refs/remotes/origin/main") == origin_seen and c.rev("refs/remotes/upstream/main") == u.rev("HEAD")
    assert c.read("probe/a.txt") == "local\n" and c.read("probe/b.txt") == "mine\n" and c.read("probe/new.txt") == "new\n"
    assert scenario.origin.rev("main") == w.rev("HEAD") and public.rev("main") == u.rev("HEAD"), "nothing is pushed"
    if scope == "me":
        assert "the rebase drops it" in r.stdout and "git revert" not in r.stdout, r.stdout
        assert c.rev("upstream/main") == c.rev("HEAD~2") and c.run_git("merge-base", "--is-ancestor", kept, "HEAD").returncode == 1  # rewritten
    else:
        assert f"git revert --no-edit {held[:9]}" in r.stdout, r.stdout
        assert c.git("rev-list", "--parents", "-1", "HEAD").split()[1:] == [pushed, c.rev("upstream/main")]
