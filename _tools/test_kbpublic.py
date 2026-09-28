"""The public home (`python3 _tools/tests.py -k kbpublic`): kbgit.py publish's projection, check-public and the push guard.

  TestProjection   (marker git) a small repository whose history adds, edits and removes kb/_querylog: the projection
                   drops it from every tree, keeps the commits before it and their hashes, drops store-only commits,
                   keeps authors and messages, and is the same when computed twice.
  TestPublish      (marker git) publish to a bare public remote: a note without one, a first push, a fast-forward, a
                   refusal when the public branch is not an ancestor, and --rewrite.
  TestGuard        (marker git) guard_push and sync refuse a history with kb/_querylog only when the remote is the
                   public home (git config kb.publishRemote); a clone without one pushes it; the pre-push hook of a kb
                   clone refuses a plain push to the public home.
"""
import argparse, os

import pytest

import kbpublic
from conftest import Repo, requires_git

pytestmark = [pytest.mark.git, requires_git]


def commit(repo, files, msg, remove=()):
    for rel, text in files.items():
        repo.write(rel, text)
    for rel in remove:
        repo.git("rm", "-q", rel)
    repo.git("add", "-A")
    repo.git("commit", "-q", "--allow-empty", "-m", msg)
    return repo.rev("HEAD")


@pytest.fixture
def src(tmp_path):
    """A repository: two public commits, then one adding the store, one mixed, one store-only, one public."""
    r = Repo(tmp_path / "src")
    os.makedirs(r.path)
    r.git("init", "-q", "-b", "main")
    shas = [commit(r, {"README.md": "a\n"}, "one"),
            commit(r, {"kb/public/a.md": "fact\n"}, "two"),
            commit(r, {"kb/_querylog/2026-09/r1.jsonl": "{}\n"}, "store only"),
            commit(r, {"kb/_querylog/2026-09/r2.jsonl": "{}\n", "kb/public/a.md": "fact 2\n"}, "mixed"),
            commit(r, {}, "remove store", remove=["kb/_querylog/2026-09/r1.jsonl"]),
            commit(r, {"kb/public/b.md": "b\n"}, "public")]
    return r, shas


def ns(**kw):
    base = {"remote": None, "source": "origin/main", "branch": "main", "dry_run": False, "rewrite": False}
    return argparse.Namespace(**{**base, **kw})


class TestProjection:
    def test_projection(self, src):
        r, shas = src
        p = kbpublic.project(shas[-1], r.path)
        assert p != shas[-1] and kbpublic.project(shas[-1], r.path) == p
        assert kbpublic.private_commits(p, r.path) == []
        assert kbpublic.private_commits(shas[-1], r.path)
        subjects = r.git("log", "--format=%s", p).split("\n")[:-1]
        assert subjects == ["public", "mixed", "two", "one"]  # the store-only commits are gone
        assert r.git("rev-list", p).split()[-2:] == [shas[1], shas[0]]  # the history before the store keeps its hashes
        assert r.git("diff", "--name-only", shas[-1], p).split() == ["kb/_querylog/2026-09/r2.jsonl"]
        assert r.git("log", "-1", "--format=%an %ae %ad", p) == r.git("log", "-1", "--format=%an %ae %ad", shas[-1])

    def test_clean_history_is_its_own(self, src):
        r, shas = src
        assert kbpublic.project(shas[1], r.path) == shas[1]


class TestPublish:
    def setup(self, src, tmp_path):
        r, shas = src
        pub = Repo(tmp_path / "pub.git")
        Repo(tmp_path).git("init", "-q", "--bare", "-b", "main", pub.path)
        origin = Repo(tmp_path / "origin.git")
        Repo(tmp_path).git("clone", "-q", "--bare", r.path, origin.path)
        r.git("remote", "add", "origin", origin.path)
        r.git("remote", "add", "pub", pub.path)
        return r, pub, origin

    def test_publish(self, src, tmp_path, capsys):
        r, pub, origin = self.setup(src, tmp_path)
        assert kbpublic.cmd_publish(ns(), r.path) == 0
        assert "no public remote" in capsys.readouterr().out
        r.git("config", "kb.publishRemote", "pub")
        assert kbpublic.cmd_publish(ns(dry_run=True), r.path) == 0
        assert pub.run_git("rev-parse", "main").returncode  # a dry run pushes nothing
        assert kbpublic.cmd_publish(ns(), r.path) == 0
        first = pub.rev("main")
        assert kbpublic.private_commits(first, pub.path) == []
        assert kbpublic.cmd_publish(ns(), r.path) == 0
        assert "nothing to do" in capsys.readouterr().out
        commit(r, {"kb/_querylog/2026-09/r3.jsonl": "{}\n", "kb/public/c.md": "c\n"}, "next")
        r.git("push", "-q", "--no-verify", "origin", "HEAD:main")
        assert kbpublic.cmd_publish(ns(), r.path) == 0
        assert "fast-forward" in capsys.readouterr().out
        assert pub.rev("main^") == first and kbpublic.private_commits("main", pub.path) == []

    def test_not_ancestor(self, src, tmp_path, capsys):
        r, pub, origin = self.setup(src, tmp_path)
        r.git("config", "kb.publishRemote", "pub")
        r.git("push", "-q", "--no-verify", "pub", "HEAD:main")  # the old history, store included
        assert kbpublic.cmd_publish(ns(), r.path) == 1
        assert "not an ancestor" in capsys.readouterr().out
        assert kbpublic.private_commits("main", pub.path)
        assert kbpublic.cmd_publish(ns(rewrite=True), r.path) == 0
        assert kbpublic.private_commits("main", pub.path) == []

    def test_check_public(self, src, capsys):
        r, shas = src
        assert kbpublic.cmd_check_public(argparse.Namespace(rev=shas[1]), r.path) == 0
        assert kbpublic.cmd_check_public(argparse.Namespace(rev=shas[-1]), r.path) == 1
        assert "FAILED" in capsys.readouterr().out


class TestGuard:
    def test_guard_push(self, src, tmp_path):
        r, shas = src
        r.git("remote", "add", "pub", str(tmp_path / "x.git"))
        refs = [("refs/heads/main", shas[-1])]
        assert kbpublic.guard_push("pub", None, refs, r.path) == []  # no public home: a production clone pushes it
        r.git("config", "kb.publishRemote", "pub")
        assert kbpublic.guard_push("pub", None, refs, r.path)
        assert kbpublic.guard_push(str(tmp_path / "x.git"), str(tmp_path / "x.git"), refs, r.path)  # by url
        assert kbpublic.guard_push("pub", None, [("refs/heads/main", shas[1])], r.path) == []
        assert kbpublic.guard_push("pub", None, [("refs/heads/gone", "0" * 40)], r.path) == []
        assert kbpublic.guard_push("origin", None, refs, r.path) == []

    def test_hook_and_sync(self, kb_seed, tmp_path):
        bare, _ = kb_seed
        c = Repo(tmp_path / "c")
        Repo(tmp_path).git("clone", "-q", str(bare), c.path)
        c.git("config", "core.hooksPath", ".githooks")
        commit(c, {"kb/_querylog/2026-09/r1.jsonl": "{}\n"}, "chore: store")
        pub = tmp_path / "pub.git"
        Repo(tmp_path).git("init", "-q", "--bare", "-b", "main", str(pub))
        c.git("remote", "add", "pub", str(pub))
        c.git("config", "kb.publishRemote", "pub")
        p = c.run_git("push", "pub", "HEAD:refs/heads/main", env={"KB_GATE_DONE": "1"})
        assert p.returncode and "public home" in p.stderr, p.stderr
        s = c.kbgit("sync", "--push", "--remote", "pub")
        assert s.returncode == 2 and "public home" in s.stdout, s.stdout
        c.git("config", "--unset", "kb.publishRemote")
        p = c.run_git("push", "pub", "HEAD:refs/heads/main", env={"KB_GATE_DONE": "1"})
        assert p.returncode == 0, p.stderr
