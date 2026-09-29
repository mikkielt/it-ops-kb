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
import argparse, ast, os, shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

import kbgit, kbpublic
from conftest import TOOLS, Repo, requires_git

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


# ---- the integration remote by role: a clone whose integration remote is not named origin

ROLE_SKIP = {  # _tools files that may hold the string constant 'origin', each with its reason
    "kbpublic.py": "resolves the role: CLONE_REMOTE is git's name for a clone's source",
    "census.py": "the remote of a source repository's own clone, not this repository's",
    "kbingest.py": "the remote of an ingested repository's own clone, not this repository's",
    "benchmarks.py": "a fixture clone's remote",
    "kb_mcp.py": "upstream() falls back to origin/HEAD: BG-kpv2cxxw",
}


def origin_constants(text):
    """[(line, value)] of the string constants of the module text that are `origin` or start with `origin/`."""
    return sorted((n.lineno, n.value) for n in ast.walk(ast.parse(text))
                  if isinstance(n, ast.Constant) and isinstance(n.value, str) and (n.value == "origin" or n.value.startswith("origin/")))


class TestRemoteRoles:
    @pytest.fixture
    def clone(self, tmp_path):
        """A repository with a copy of _tools whose only remotes are `integ` (bare, its integration remote) and `pub`."""
        top = Repo(tmp_path)
        integ, pub = Repo(tmp_path / "integ.git"), Repo(tmp_path / "pub.git")
        top.git("init", "-q", "--bare", "-b", "main", integ.path)
        top.git("init", "-q", "--bare", "-b", "main", pub.path)
        r = Repo(tmp_path / "work")
        shutil.copytree(TOOLS, r.file("_tools"), ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        r.git("init", "-q", "-b", "main")
        commit(r, {"README.md": "a\n", "kb/public/a.md": "fact\n"}, "one")
        r.git("remote", "add", "integ", integ.path)
        r.git("remote", "add", "pub", pub.path)
        r.git("push", "-q", "--no-verify", "integ", "HEAD:main")
        r.git("config", "kb.integrationRemote", "integ")
        return r

    def test_role_resolution(self, clone):
        assert kbpublic.integration_remote(clone.path) == "integ"
        clone.git("config", "--unset", "kb.integrationRemote")
        assert kbpublic.integration_remote(clone.path) == "origin"

    def test_sync_names_the_integration_remote(self, clone):
        p = clone.kbgit("sync", "--dry-run")
        assert "integ/main" in p.stdout and "origin" not in p.stdout + p.stderr, p.stdout + p.stderr
        p = clone.kbgit("sync", "--dry-run", "--remote", "pub")  # --remote still overrides
        assert "pub/main" in p.stdout, p.stdout + p.stderr

    @pytest.mark.parametrize("public", [True, False])
    def test_publish_names_the_integration_remote(self, clone, public):
        if public:
            clone.git("config", "kb.publishRemote", "pub")
        p = clone.kbgit("publish", "--dry-run")
        assert p.returncode == 0 and "origin" not in p.stdout + p.stderr, p.stdout + p.stderr
        if public:
            assert "source: integ/main" in p.stdout
        else:
            assert "no public remote" in p.stdout

    def test_red_pipeline_names_the_integration_remote(self, clone, monkeypatch, capsys):
        import backlog
        calls = []

        def fake(argv, cwd=None):
            calls.append(argv)
            return 1, "", "stub"

        monkeypatch.setattr(backlog, "run", fake)
        backlog.cmd_red_pipeline(SimpleNamespace(root=clone.path), argparse.Namespace(status=False))
        assert ["git", "fetch", "-q", "integ", "main"] in calls
        assert "no integ remote" in capsys.readouterr().out
        assert not any("origin" in " ".join(c) for c in calls)

    def test_pusher_and_hook_resolve_the_role(self, clone, monkeypatch):
        import ql_deliver
        p = ql_deliver.Pusher(clone.path, Path(clone.path) / "q", lambda argv, cwd=None: (1, "", ""), None, print, cloud=False)
        assert p.remote == "integ" and p.up == "refs/remotes/integ/main"
        monkeypatch.setattr(kbgit, "KB", clone.path)
        assert kbpublic.integration_remote(kbgit.KB) == "integ"

    def test_no_tool_holds_the_string_origin(self):
        found = {}
        for f in sorted(Path(TOOLS).glob("*.py")):
            if f.name.startswith(("test_", "conftest")) or f.name in ROLE_SKIP:
                continue
            hits = origin_constants(f.read_text(encoding="utf-8"))
            if hits:
                found[f.name] = hits
        assert not found, f"a tool names the remote origin instead of asking kbpublic.integration_remote: {found}"

    def test_scan_reports_a_planted_origin(self):
        assert origin_constants('x = ["git", "fetch", "origin"]\ny = "origin/main"\nz = "origins"\n') == [(1, "origin"), (2, "origin/main")]
        assert origin_constants('"""origin is fine in a docstring about origin/main"""\nremote = kbpublic.integration_remote(cwd)\n') == []
        for name, why in ROLE_SKIP.items():
            assert (Path(TOOLS) / name).exists() and why, name  # a skip names a file that exists, with its reason
