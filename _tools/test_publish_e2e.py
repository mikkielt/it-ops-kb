"""End to end: `kbgit.py publish` pushes the projection of the integration main to the public home, refuses a leak
anywhere in the range and a CI verdict that is not ok; `check-public` tells the projection from the history.

`publish` has no command-line hook for the CI verdict (a local origin has no forge), so these tests run
`kbpublic.cmd_publish` in-process with a command runner that answers as glab does."""
import argparse, json, shutil

import pytest

import kbpublic
from conftest import TOOLS, Repo, git_env, requires_git

pytestmark = [pytest.mark.git, requires_git]

STORE = "kb/_querylog/2026-09/r1.jsonl"
LOGS = "kb/public/_logs.csv"


def ci_runner(state):
    """A runner that answers as glab does: signed in, the commit's newest pipeline is in STATE, its gate jobs succeeded."""
    def run(argv):
        if argv[1:3] == ["auth", "status"]:
            return 0, "", ""
        if "/jobs" in argv[-1]:
            return 0, json.dumps([{"name": n, "status": "success"} for n in ("kb-tests", "kb-trailers")]), ""
        return 0, json.dumps([{"id": 7, "status": state, "web_url": "u"}]), ""
    return run


def publish(clone, state="success"):
    args = argparse.Namespace(remote=None, source="origin/main", branch="main", dry_run=False, rewrite=False, hook=False,
                              ci_run=ci_runner(state))
    return kbpublic.cmd_publish(args, clone.path)


@pytest.fixture
def world(scenario, monkeypatch):
    """(a clone with the empty public home `public.git` configured, that home): the in-process git sees the scenario's env."""
    for k, v in git_env(KB_SYNC_NO_TESTS="1").items():
        monkeypatch.setenv(k, v)
    Repo(scenario.tmp).git("init", "-q", "--bare", "-b", "main", "public.git")  # the seed's own history is not projected
    pub = Repo(scenario.tmp / "public.git")
    clone = scenario.clone(hooks=False)
    # a small kb in place of the seed's: the leak scan reads every file of every commit of the range
    clone.git("checkout", "-q", "--orphan", "small")
    clone.git("rm", "-rfq", ".")
    clone.write("README.md", "# kb\n")
    clone.write("kb/public/index.md", "fact\n")
    clone.commit("base")
    clone.git("push", "-q", "--force", "origin", "HEAD:main")
    clone.git("remote", "add", "pub", pub.path)
    clone.git("config", kbpublic.CONFIG_KEY, "pub")
    return clone, pub


def pub_empty(pub):
    return pub.run_git("rev-parse", "--verify", "--quiet", "main").returncode != 0


def push_commit(clone, message, files):
    for rel, body in files.items():
        clone.write(rel, body)
    clone.commit(message)
    clone.git("push", "-q", "origin", "HEAD:main")


def test_publish_sends_the_projection_and_check_public_tells_it_apart(world, capsys):
    clone, pub = world
    push_commit(clone, "store", {STORE: "{}\n", LOGS: "a,b\n", "kb/public/note.md": "fact\n"})
    assert clone.git("log", "--format=%H", "--", STORE).strip()  # the integration history holds the store
    assert publish(clone) == 0, capsys.readouterr().out
    files = pub.git("ls-tree", "-r", "--name-only", "main").split()
    assert {"README.md", "kb/public/index.md", "kb/public/note.md"} <= set(files)
    assert not [f for f in files if f.startswith("kb/_querylog/") or f.endswith("_logs.csv")]
    assert not pub.git("log", "--format=%H", "main", "--", STORE, LOGS).strip()  # nor in any commit of its history
    assert pub.rev("main") == clone.rev("refs/kb/published")
    # check-public: the integration history fails, the projection passes (the clone needs its own copy of the tools)
    shutil.copytree(TOOLS, clone.file("_tools"), ignore=shutil.ignore_patterns("__pycache__", "fixtures"))
    bad = clone.kbgit("check-public", "origin/main")
    assert bad.returncode == 1 and "FAILED" in bad.stdout
    good = clone.kbgit("check-public", "refs/kb/published")
    assert good.returncode == 0, good.stdout + good.stderr


def test_publish_refuses_a_leak_in_any_commit_of_the_range(world, capsys):
    clone, pub = world
    leak = ".".join(("10", "20", "30", "40"))  # assembled here: this file holds no address
    push_commit(clone, "leak", {"kb/public/leak.md": f"host at {leak}\n"})
    push_commit(clone, "unleak", {"kb/public/leak.md": "host at corp.example.com\n"})
    assert publish(clone) == 1
    assert "refused:" in capsys.readouterr().out
    assert pub_empty(pub)  # the final tree is clean, the history is not


def test_publish_follows_the_ci_verdict(world, capsys):
    clone, pub = world
    push_commit(clone, "next", {"kb/public/next.md": "fact\n"})
    assert publish(clone, "failed") == 1
    assert "CI verdict" in capsys.readouterr().out and pub_empty(pub)
    assert publish(clone, "success") == 0
    assert not pub_empty(pub)
