"""The pre-push hook end to end: a plain `git push origin main` in a clone with the hooks installed.

Main path (a content commit is pushed), the planted red gate (a citation of an unknown source), the lane guard (a
code-lane commit straight to main), and the public-home guard (a history that holds kb/_querylog/). The clone is built
once; each case starts from a hard reset to origin/main."""
import pytest
from conftest import Scenario, git_env, requires_git

import kbpublic

pytestmark = [pytest.mark.git, requires_git]

ARTICLE = "kb/public/python/ruff.md"


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


def test_content_commit_is_pushed(world):
    sc, c = world
    before = origin_main(sc)
    c.append(ARTICLE, "\nA closing line added by a content commit.\n")
    c.commit("docs: a content line", ARTICLE)
    p = push_main(c)
    assert p.returncode == 0, p.stdout + p.stderr
    assert origin_main(sc) == c.rev("HEAD") != before


def test_unknown_source_citation_is_refused(world):
    sc, c = world
    fresh(c)
    before = origin_main(sc)
    c.write(ARTICLE, c.read(ARTICLE).replace("[DOC S-y3zhzpmv,", "[DOC S-zzzzzzzz,", 1))
    c.commit("docs: cite a source the ledger lacks", ARTICLE)
    p = push_main(c)
    assert p.returncode != 0, p.stdout + p.stderr
    assert "kb pre-push check.py: FAILED" in p.stderr and "nothing pushed" in p.stderr, p.stderr
    assert origin_main(sc) == before


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
