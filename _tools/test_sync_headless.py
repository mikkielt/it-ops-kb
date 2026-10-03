"""A headless sprint run (KB_HEADLESS_RUNNER, set by autopilot.py runner start) syncs only to the integration remote's
main: `kbgit.py sync --push` with `--branch` other than main or with `--remote` is refused, exit 2, nothing pushed;
without the variable the same commands are unchanged (kb/_self/git.md)."""
import argparse, os

import pytest

import kbpublic, kg_sync
from conftest import Repo, git_env
from test_sync import clones

HEADLESS = {kbpublic.HEADLESS_ENV: "1"}


@pytest.fixture(scope="module")
def world(tmp_path_factory, kb_seed):
    tmp = str(tmp_path_factory.mktemp("kb-sync-headless"))
    env = git_env(KB_SYNC_NO_TESTS="1")
    remote, (a,), _ = clones(kb_seed, tmp, env, ("a",))
    second = os.path.join(tmp, "second.git")
    Repo(tmp, env).git("init", "-q", "--bare", second)
    a.git("remote", "add", "second", second)
    return {"a": a, "remote": Repo(remote, env), "second": Repo(second, env), "env": env}


def refs(repo):
    return repo.git("for-each-ref", "--format=%(refname)").split()


@pytest.mark.parametrize("args, named", [(["--branch", "scratch"], "--branch scratch"),
                                         (["--remote", "second"], "--remote second")])
def test_headless_sync_pushes_only_the_integration_main(world, args, named):
    a, remote, second = world["a"], world["remote"], world["second"]
    before = (refs(remote), remote.rev("main"), refs(second))
    p = a.tool("kbgit.py", "sync", "--push", *args, env=HEADLESS)
    assert p.returncode == 2 and "refused: a headless run" in p.stdout and named in p.stdout, p.stdout + p.stderr
    assert (refs(remote), remote.rev("main"), refs(second)) == before  # nothing pushed anywhere


@pytest.mark.parametrize("args", [["--branch", "scratch"], ["--remote", "second"]])
def test_headless_sync_pushes_only_the_integration_main_unchanged_without_the_variable(world, args):
    p = world["a"].tool("kbgit.py", "sync", "--push", "--dry-run", *args)
    assert "headless" not in p.stdout, p.stdout  # the planted contrast: an interactive sync is not refused for it


def test_headless_sync_pushes_only_the_integration_main_plain_sync_is_not_refused(monkeypatch):
    monkeypatch.setenv(kbpublic.HEADLESS_ENV, "1")
    plain = argparse.Namespace(remote=None, branch="main")
    assert kg_sync.headless_target_refusal(plain) is None  # sync --push of main: the runner's own push
    both = argparse.Namespace(remote="public", branch="x")
    assert "--remote public --branch x" in kg_sync.headless_target_refusal(both)
    monkeypatch.delenv(kbpublic.HEADLESS_ENV)
    assert kg_sync.headless_target_refusal(both) is None
