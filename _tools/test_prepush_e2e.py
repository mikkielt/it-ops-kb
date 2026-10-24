"""The pre-push hook end to end: a plain `git push origin main` in a clone with the hooks installed.

The lane guard (a code-lane commit straight to main) and the public-home guard (a history that holds kb/_querylog/).
The clone is built once; each case starts from a hard reset to origin/main."""
import os

import pytest
from conftest import Scenario, git_env, requires_git

import kbpublic

pytestmark = [pytest.mark.git, requires_git]


@pytest.fixture(scope="module")
def world(tmp_path_factory, kb_seed):
    sc = Scenario(tmp_path_factory.mktemp("prepush-e2e"), *kb_seed)
    c = sc.clone(env=git_env(KB_SYNC_NO_TESTS="1"))
    c.git("config", "core.fileMode", "false")  # install-hooks' chmod is no change of the tree the gate reads
    return sc, c


def push_main(c, remote="origin"):
    c.git("fetch", "-q", "origin")
    return c.run_git("push", "-q", remote, "main")


def fresh(c):
    """Back to origin/main; the reset drops the hooks' executable bit, so install them again."""
    c.git("reset", "-q", "--hard", "origin/main")
    assert c.kbgit("install-hooks").returncode == 0


def origin_main(sc):
    return sc.origin.rev("main")


def test_code_commit_straight_to_main_is_refused(world):
    sc, c = world
    fresh(c)
    before = origin_main(sc)
    c.write("_tools/zz_lane_probe.py", "PROBE = 1\n")
    c.commit("chore: a tool file on main", "_tools/zz_lane_probe.py")
    p = push_main(c)
    assert p.returncode != 0 and "code-lane commit" in p.stderr, p.stdout + p.stderr
    assert origin_main(sc) == before


def test_public_home_refuses_a_history_with_the_query_log(world):
    sc, c = world
    fresh(c)
    pub = sc.bare("public.git")
    before = pub.rev("main")
    c.git("remote", "add", "pub", pub.path)
    c.git("config", kbpublic.CONFIG_KEY, "pub")
    c.write("kb/_querylog/probe.csv", "a,b\n")
    c.commit("chore: a query log file", "kb/_querylog/probe.csv")
    p = push_main(c, "pub")
    assert p.returncode != 0 and "_querylog" in p.stderr, p.stdout + p.stderr
    assert pub.rev("main") == before


def test_upstream_push_refused(world):
    sc, c = world
    fresh(c)
    up = sc.bare("fetchonly.git")
    before = up.rev("main")
    c.git("remote", "add", "up", up.path)
    c.git("config", kbpublic.UPSTREAM_KEY, "up")
    c.write("kb/_self/zz_upstream_probe.md", "probe\n")
    c.commit("docs: a content file", "kb/_self/zz_upstream_probe.md")
    stem = up.path[:-len(".git")]
    spellings = ["up", up.path, up.path + "/", "file://" + up.path, stem, stem + "/"]
    if os.path.exists(up.path.swapcase()):  # a case-insensitive filesystem
        spellings.append(up.path.swapcase())
    for target in spellings:
        p = push_main(c, target)  # by name and by each way git reaches the repository: a guessed .git, a case spelling
        assert p.returncode != 0 and "upstream remote" in p.stderr, target + p.stdout + p.stderr
    assert up.rev("main") == before
    sync = c.kbgit("sync", "--remote", "up")
    assert sync.returncode == 2 and "only fetched from" in sync.stdout, sync.stdout + sync.stderr
    sibling = sc.bare("fetchonly2.git")  # a different repository sharing the prefix is not the upstream
    assert not kbpublic.is_upstream(sibling.path, c.path) and not kbpublic.is_upstream(stem + "2", c.path)
    c.git("remote", "set-url", "up", "https://example.com/org/repo.git")  # git connects before it runs the hook
    for target in ("git@example.com:org/repo.git", "https://example.com/org/repo", "ssh://git@example.com/org/repo.git",
                   "http://EXAMPLE.com/org/repo.git/", "deploy@example.com:org/repo", "git@example.com:/org/repo.git",
                   "example.com:/org/repo"):  # so the guard is asked directly
        assert kbpublic.guard_upstream(target, target, [("refs/heads/main", "")], c.path), target
    assert kbpublic.location("C:/work/repo", c.path)[0] == "path" and kbpublic.location("c:\\work\\repo", c.path)[0] == "path"
    bad = "https://[::1/x"  # urllib cannot parse it: the text stands for it, so the hook still judges the push
    assert kbpublic.location(bad, c.path) == ("text", bad) and not kbpublic.is_upstream(bad, c.path)
    c.git("remote", "set-url", "up", bad)
    assert kbpublic.guard_upstream(bad, bad, [("refs/heads/main", "")], c.path)
    assert not kbpublic.is_upstream("https://example.com/org/repo2.git", c.path)
    assert not kbpublic.is_upstream("git@example.com:org2/repo.git", c.path)
