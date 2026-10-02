"""The public home (`python3 _tools/tests.py -k kbpublic`): kbgit.py publish's projection, check-public and the push guard.

  TestProjection   (marker git) a small repository whose history adds, edits and removes kb/_querylog: the projection
                   drops it from every tree, keeps the commits before it and their hashes, drops store-only commits,
                   keeps authors and messages, and is the same when computed twice.
                   The ops sidecar (kb/_querylog/ops/) is part of that path: the projection drops it, check-public and
                   the push guard name it, and kbgit.py's gate treats it as the query log store (`-k ops_sidecar`).
  TestProjectionReuse (marker git) the projection cache: a second projection of a longer source rewrites only the
                   new commits and gives the shas a projection from scratch gives; a corrupt cache is the full walk; a
                   cached projected commit missing from the object store is computed again.
  TestPublish      (marker git) publish to a bare public remote: a note without one, a first push, a fast-forward, a
                   refusal when the public branch is not an ancestor, and --rewrite.
  TestPublishHookLongRange (marker git) publish --hook prints one line and checks and pushes nothing when more than
                   HOOK_BOUND commits have no cached verdict; a second run scans only the uncached commits; a corrupt
                   cache is recomputed.
  TestPublishSafety (marker git) publish refuses, exit 1 and pushes nothing (a dry run reports the same), on a red, a
                   pending, an unreadable or a missing CI verdict of the source commit (a stubbed run), an internal
                   root, a _private path and a leaked address in a changed file; a value the public tip holds in
                   another file passes, a value new to the public home is refused.
  TestPublishHistory (marker git) the same refusals for a commit of the range that adds what a later commit deletes,
                   named by its hash, on a first publish too; a clean range and a value the parent's version holds pass.
  TestLogsCsv      (marker git) every `_logs.csv` (a root's observed signals, any directory, kb/_self's too) is left out of
                   the projection, a commit of nothing else is gone, a file that only ends alike stays; publish pushes
                   none of them, and check-public, the push guard and the bridge's range name a history that holds one.
  TestGuard        (marker git) guard_push and sync refuse a history with kb/_querylog only when the remote is the
                   public home (git config kb.publishRemote); a clone without one pushes it; the pre-push hook of a kb
                   clone refuses a plain push to the public home.
"""
import argparse, ast, hashlib, json, os, shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

import kbgit, kbpublic, kg_sync
from conftest import TOOLS, Repo, git_env, requires_git
from test_sync import RECORD_OPTIONS, SyncScenario, clones
from conftest import P
import kbid

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


def ci_stub(state=None, signed_in=True):
    """A command runner for the CI check that answers as glab does: the newest pipeline of the commit is in STATE
    (None: no pipeline), its gate jobs succeeded; signed_in False: glab is not signed in."""
    def run(argv):
        if argv[1:3] == ["auth", "status"]:
            return (0, "", "") if signed_in else (1, "", "not signed in")
        if "/jobs" in argv[-1]:
            return 0, json.dumps([{"name": n, "status": "success"} for n in ("kb-tests", "kb-trailers")]), ""
        return 0, json.dumps([] if state is None else [{"id": 7, "status": state, "web_url": "u"}]), ""
    return run


def ns(**kw):
    base = {"remote": None, "source": "origin/main", "branch": "main", "dry_run": False, "rewrite": False,
            "ci_run": ci_stub("success")}
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

    def test_ops_sidecar_cut_from_publish(self, tmp_path):
        """an ops sidecar is under kb/_querylog/, so it never reaches the public home: it is in no projected tree, a
        commit of nothing else is gone, one that also holds public content keeps the content and drops the sidecar"""
        r = Repo(tmp_path / "ops")
        os.makedirs(r.path)
        r.git("init", "-q", "-b", "main")
        ops = "kb/_querylog/ops/2026-10/20261002T100000Z-0000abcd.jsonl"
        shas = [commit(r, {"kb/public/a.md": "fact\n"}, "public"),
                commit(r, {ops: "{}\n"}, "ops only"),
                commit(r, {ops.replace("0000abcd", "0000abce"): "{}\n", "kb/public/b.md": "b\n"}, "mixed")]
        p = kbpublic.project(shas[-1], r.path)
        assert [x for x in r.git("ls-tree", "-r", "--name-only", p).split() if "_querylog" in x] == []
        assert r.git("log", "--format=%s", p).split("\n")[:-1] == ["mixed", "public"]  # the ops-only commit is gone
        assert r.git("show", f"{p}:kb/public/b.md") == "b\n"
        assert kbpublic.private_commits(p, r.path) == []
        assert kbpublic.private_commits(shas[-1], r.path) and kbpublic.private_commits(shas[1], r.path)
        r.git("remote", "add", "pub", str(tmp_path / "x.git"))
        r.git("config", "kb.publishRemote", "pub")
        assert kbpublic.guard_push("pub", None, [("refs/heads/main", shas[1])], r.path)
        assert kbpublic.guard_push("pub", None, [("refs/heads/main", shas[0])], r.path) == []
        needs = kg_sync.gate_needs([ops])  # kg_sync.py's gate: the query log store's check, no kb content or doc check
        assert needs["querylog"] and not any(needs[k] for k in ("check", "fetch", "doc2query", "selfdoc", "backlog")), needs
        assert kg_sync.gate_needs(["kb/_querylog/work/2026-10/x.jsonl"])["querylog"]  # the same as its sibling sidecars

    def test_clean_history_is_its_own(self, src):
        r, shas = src
        assert kbpublic.project(shas[1], r.path) == shas[1]


class TestProjectionReuse:
    @staticmethod
    def spy(monkeypatch):
        """The source commits Projector.rewrite projects, in order."""
        done, rewrite = [], kbpublic.Projector.rewrite
        monkeypatch.setattr(kbpublic.Projector, "rewrite", lambda self, sha, parents: (done.append(sha), rewrite(self, sha, parents))[1])
        return done

    @staticmethod
    def full(tip, cwd):
        """The projection of TIP computed from scratch, without the cache."""
        p = kbpublic.Projector(cwd)
        try:
            return p.project(tip)
        finally:
            p.close()

    @staticmethod
    def cache_file(r):
        return Path(r.path, *kbpublic.CACHE_DIR, kbpublic.projection_cache(len(r.rev("HEAD"))))

    def test_longer_source_projects_only_new_commits(self, src, monkeypatch):
        r, shas = src
        kbpublic.project(shas[3], r.path)
        assert self.cache_file(r).exists()
        done, sources = self.spy(monkeypatch), {}
        res = kbpublic.project(shas[-1], r.path, sources)
        assert done == shas[4:]
        assert res == self.full(shas[-1], r.path) and kbpublic.private_commits(res, r.path) == []
        assert sources[res] == shas[-1] and sources[shas[1]] == shas[1]
        done.clear()
        assert kbpublic.project(shas[-1], r.path) == res and done == []

    def test_corrupt_cache_is_the_full_walk(self, src, monkeypatch):
        r, shas = src
        kbpublic.project(shas[-1], r.path)
        self.cache_file(r).write_text("{corrupt", encoding="utf-8")
        want, done = self.full(shas[-1], r.path), self.spy(monkeypatch)
        assert kbpublic.project(shas[-1], r.path) == want and done == shas

    def test_missing_projected_commit_is_recomputed(self, src, monkeypatch):
        r, shas = src
        res = kbpublic.project(shas[-1], r.path)
        f = self.cache_file(r)
        cached = json.loads(f.read_text(encoding="utf-8"))
        cached[shas[3]] = hashlib.new("sha1" if len(shas[3]) == 40 else "sha256", b"no such commit").hexdigest()
        f.write_text(json.dumps(cached), encoding="utf-8")
        done = self.spy(monkeypatch)
        assert kbpublic.project(shas[-1], r.path) == res and done == [shas[3]]
        assert json.loads(f.read_text(encoding="utf-8"))[shas[3]] != cached[shas[3]]


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


class TestPublishHook:
    setup = TestPublish.setup

    def hook(self, r, **kw):
        return kbpublic.cmd_publish_hook(ns(hook=True, **kw), r.path)

    def test_no_remote_is_silent(self, src, tmp_path, capsys):
        r, pub, origin = self.setup(src, tmp_path)
        assert self.hook(r) == 0
        assert capsys.readouterr().out == "" and pub.run_git("rev-parse", "main").returncode

    def test_publishes_silently_when_ahead(self, src, tmp_path, capsys):
        r, pub, origin = self.setup(src, tmp_path)
        r.git("config", "kb.publishRemote", "pub")
        assert self.hook(r) == 0
        assert capsys.readouterr().out == ""
        assert kbpublic.private_commits(pub.rev("main"), pub.path) == []
        assert self.hook(r) == 0 and capsys.readouterr().out == ""  # nothing to do: still silent

    def test_refusal_and_failed_push_print_and_exit_0(self, src, tmp_path, capsys):
        r, pub, origin = self.setup(src, tmp_path)
        r.git("config", "kb.publishRemote", "pub")
        assert self.hook(r, ci_run=ci_stub("failed")) == 0
        out = capsys.readouterr().out
        assert "refused:" in out and "verdict" in out and "source:" not in out
        assert pub.run_git("rev-parse", "main").returncode  # nothing was pushed
        hooks = Path(pub.path) / "hooks"
        hooks.mkdir(exist_ok=True)
        (hooks / "pre-receive").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        (hooks / "pre-receive").chmod(0o755)
        assert self.hook(r) == 0
        assert "push failed:" in capsys.readouterr().out


class TestPublishHookLongRange:
    """The hook leaves a range with more uncached commits than kbpublic.HOOK_BOUND to a publish by hand; a publish
    caches each commit's leak verdict, so a range is scanned once."""

    def long_range(self, src, tmp_path, monkeypatch, n=6):
        r, pub = TestPublishSafety().prepare(src, tmp_path)
        for i in range(n):
            commit(r, {f"kb/public/n{i}.md": f"n {i}\n"}, f"n{i}")
        r.git("push", "-q", "--no-verify", "origin", "HEAD:main")
        monkeypatch.setattr(kbpublic, "HOOK_BOUND", 3)
        return r, pub

    def test_hook_leaves_a_long_range_to_a_publish_by_hand(self, src, tmp_path, monkeypatch, capsys):
        r, pub = self.long_range(src, tmp_path, monkeypatch)
        n = len(r.git("rev-list", kbpublic.project(r.rev("HEAD"), r.path)).split())  # no tip: every projected commit
        scanned = []
        monkeypatch.setattr(kbpublic, "leak_verdicts", lambda written, *a: scanned.append(written) or {})
        assert kbpublic.cmd_publish_hook(ns(hook=True), r.path) == 0
        assert capsys.readouterr().out == f"kb publish: publish by hand: {n} commits to check (python3 _tools/kbgit.py publish)\n"
        assert pub.run_git("rev-parse", "main").returncode and not scanned  # nothing checked, nothing pushed
        assert kbpublic.cmd_publish(ns(), r.path) == 0 and pub.rev("main")  # by hand: no bound

    def test_second_run_uses_the_cache(self, src, tmp_path, monkeypatch, capsys):
        r, pub = self.long_range(src, tmp_path, monkeypatch)
        real, scanned = kbpublic.leak_verdicts, []
        monkeypatch.setattr(kbpublic, "leak_verdicts", lambda written, *a: scanned.append({w[0] for w in written}) or real(written, *a))
        assert kbpublic.cmd_publish(ns(dry_run=True), r.path) == 0 and len(scanned) == 1 and len(scanned[0]) > 3
        capsys.readouterr()
        assert kbpublic.cmd_publish_hook(ns(hook=True), r.path) == 0  # every verdict cached: under the bound, pushed
        assert capsys.readouterr().out == "" and pub.rev("main") and len(scanned) == 1
        tip = pub.rev("main")
        head = commit(r, {"kb/public/late.md": "late\n"}, "late")
        r.git("push", "-q", "--no-verify", "origin", "HEAD:main")
        assert kbpublic.cmd_publish(ns(), r.path) == 0 and scanned[1] == {kbpublic.project(head, r.path)}
        names = sorted(x.name for x in Path(r.path, *kbpublic.CACHE_DIR).glob("verdicts-*.json"))
        assert len(names) == 1 and names[0].startswith(f"verdicts-{tip}-"), names  # the file of no tip went

    def test_corrupt_cache_is_recomputed(self, src, tmp_path, monkeypatch):
        r, pub = self.long_range(src, tmp_path, monkeypatch)
        leak = ".".join(("192", "168", "4", "9"))
        commit(r, {"kb/public/leak.md": f"host at {leak}\n"}, "leak")
        r.git("push", "-q", "--no-verify", "origin", "HEAD:main")
        assert kbpublic.cmd_publish(ns(dry_run=True), r.path) == 1
        for f in Path(r.path, *kbpublic.CACHE_DIR).glob("verdicts-*.json"):
            f.write_text("{corrupt", encoding="utf-8")
        assert kbpublic.cmd_publish(ns(), r.path) == 1 and pub.run_git("rev-parse", "main").returncode


class TestPublishSafety:
    def prepare(self, src, tmp_path, files=None):
        r, shas = src
        pub = Repo(tmp_path / "pub.git")
        Repo(tmp_path).git("init", "-q", "--bare", "-b", "main", pub.path)
        origin = Repo(tmp_path / "origin.git")
        Repo(tmp_path).git("clone", "-q", "--bare", r.path, origin.path)
        r.git("remote", "add", "origin", origin.path)
        r.git("remote", "add", "pub", pub.path)
        r.git("config", "kb.publishRemote", "pub")
        if files:
            commit(r, files, "planted")
            r.git("push", "-q", "--no-verify", "origin", "HEAD:main")
        return r, pub

    def refused(self, r, pub, capsys, cause, **kw):
        """Every mode refuses with CAUSE, exit 1, and pushes nothing."""
        for dry in (True, False):
            assert kbpublic.cmd_publish(ns(dry_run=dry, **kw), r.path) == 1
            text = capsys.readouterr().out
            assert "refused: " in text and cause in text and "nothing pushed" in text
            assert pub.run_git("rev-parse", "main").returncode

    @pytest.mark.parametrize("state, cause", [("failed", "is red"), ("running", "is pending"), (None, "is none")])
    def test_ci_verdict(self, src, tmp_path, capsys, state, cause):
        r, pub = self.prepare(src, tmp_path)
        self.refused(r, pub, capsys, cause, ci_run=ci_stub(state))

    def test_ci_unreadable(self, src, tmp_path, capsys):
        r, pub = self.prepare(src, tmp_path)
        self.refused(r, pub, capsys, "is skip", ci_run=ci_stub("success", signed_in=False))

    def test_ci_ok_publishes(self, src, tmp_path):
        r, pub = self.prepare(src, tmp_path)
        assert kbpublic.cmd_publish(ns(), r.path) == 0 and pub.rev("main")

    def test_internal_root(self, src, tmp_path, capsys):
        r, pub = self.prepare(src, tmp_path, {"kb/team/_root.md": "---\nroot: team\nid_prefix: T\nvisibility: internal\n---\n"})
        self.refused(r, pub, capsys, "the internal root kb/team")

    def test_public_root_passes(self, src, tmp_path):
        r, pub = self.prepare(src, tmp_path, {"kb/open/_root.md": "---\nroot: open\nid_prefix: O\nvisibility: public\n---\n"})
        assert kbpublic.cmd_publish(ns(), r.path) == 0

    @pytest.mark.parametrize("path", ["kb/public/_private/n.md", "tools/_cache/x.json"])
    def test_private_and_cache_paths(self, src, tmp_path, capsys, path):
        r, pub = self.prepare(src, tmp_path, {path: "x\n"})
        self.refused(r, pub, capsys, f"holds {path}")

    def test_leaked_address(self, src, tmp_path, capsys):
        leak = ".".join(("192", "168", "4", "9"))  # built here so this file has no address of its own
        r, pub = self.prepare(src, tmp_path, {"kb/public/leak.md": f"host at {leak}\n"})
        self.refused(r, pub, capsys, "kb/public/leak.md has a leak-scan hit (ip)")

    def test_leak_in_unchanged_file_and_allowlist(self, src, tmp_path):
        leak = ".".join(("192", "168", "4", "9"))
        r, pub = self.prepare(src, tmp_path, {"kb/public/leak.md": f"host at {leak}\n",
                                              "_tools/tests_allowlist.txt": f"ip {leak}  # reviewed\n"})
        assert kbpublic.cmd_publish(ns(), r.path) == 0  # allowed
        commit(r, {"kb/public/other.md": "fine\n"}, "later", remove=[])
        r.git("push", "-q", "--no-verify", "origin", "HEAD:main")
        r.git("rm", "-q", "_tools/tests_allowlist.txt")
        r.git("commit", "-q", "-m", "drop allowlist")
        r.git("push", "-q", "--no-verify", "origin", "HEAD:main")
        assert kbpublic.cmd_publish(ns(), r.path) == 0  # leak.md is not changed against the public tip: not scanned

    def published_leak(self, src, tmp_path):
        """A public tip whose _tools/test_x.py holds a GUID, published under an allowlist that is then dropped."""
        guid = "-".join(("3f2a4c1e", "0000", "4000", "8000", "00000000abcd"))  # built here so this file has none
        r, pub = self.prepare(src, tmp_path, {"_tools/test_x.py": f"QID = '{guid}'\n",
                                              "_tools/tests_allowlist.txt": f"guid {guid}  # reviewed\n"})
        assert kbpublic.cmd_publish(ns(), r.path) == 0
        r.git("rm", "-q", "_tools/tests_allowlist.txt")
        r.git("commit", "-q", "-m", "drop allowlist")
        r.git("push", "-q", "--no-verify", "origin", "HEAD:main")
        return r, pub, guid

    def test_leak_already_public_passes(self, src, tmp_path):
        r, pub, guid = self.published_leak(src, tmp_path)
        commit(r, {"_tools/test_x.py": f"QID = '{guid}'\nOTHER = 1\n"}, "change the file", remove=[])
        r.git("push", "-q", "--no-verify", "origin", "HEAD:main")
        assert kbpublic.cmd_publish(ns(), r.path) == 0  # the tip's version of the file holds the GUID already

    def test_new_leak_in_public_file_refused(self, src, tmp_path, capsys):
        r, pub, guid = self.published_leak(src, tmp_path)
        tip = pub.rev("main")
        new = "-".join(("5b1d7e2a", "0000", "4000", "8000", "00000000abcd"))
        commit(r, {"_tools/test_x.py": f"QID = '{guid}'\nNEW = '{new}'\n"}, "add a GUID", remove=[])
        r.git("push", "-q", "--no-verify", "origin", "HEAD:main")
        for dry in (True, False):
            assert kbpublic.cmd_publish(ns(dry_run=dry), r.path) == 1
            text = capsys.readouterr().out
            assert "_tools/test_x.py has a leak-scan hit (guid)" in text and "nothing pushed" in text
            assert pub.rev("main") == tip

    def test_value_public_elsewhere_passes(self, src, tmp_path, capsys):
        r, pub, guid = self.published_leak(src, tmp_path)
        commit(r, {"kb/_self/backlog/BG-x.json": f'{{"repro": "{guid}"}}\n'}, "quote the id elsewhere")
        r.git("push", "-q", "--no-verify", "origin", "HEAD:main")
        assert kbpublic.cmd_publish(ns(), r.path) == 0, capsys.readouterr().out  # _tools/test_x.py holds it publicly
        assert list(Path(r.path, *kbpublic.CACHE_DIR).glob("public-*.json"))
        assert not r.git("status", "--porcelain").strip()  # the cache ignores itself

    def test_value_new_to_public_home_refused(self, src, tmp_path, capsys):
        r, pub, guid = self.published_leak(src, tmp_path)
        tip = pub.rev("main")
        new = ".".join(("192", "168", "4", "9"))
        commit(r, {"kb/_self/backlog/BG-x.json": f'{{"repro": "{guid} {new}"}}\n'}, "quote a new address")
        r.git("push", "-q", "--no-verify", "origin", "HEAD:main")
        Path(r.path, *kbpublic.CACHE_DIR).mkdir(parents=True, exist_ok=True)
        Path(r.path, *kbpublic.CACHE_DIR, f"public-{tip}.json").write_text("{corrupt", encoding="utf-8")  # recomputed
        for dry in (True, False):
            assert kbpublic.cmd_publish(ns(dry_run=dry), r.path) == 1
            text = capsys.readouterr().out
            assert "kb/_self/backlog/BG-x.json has a leak-scan hit (ip)" in text and "nothing pushed" in text  # not guid
            assert pub.rev("main") == tip

    def test_leak_without_tip_refused(self, src, tmp_path, capsys):
        guid = "-".join(("3f2a4c1e", "0000", "4000", "8000", "00000000abcd"))
        r, pub = self.prepare(src, tmp_path, {"_tools/test_x.py": f"QID = '{guid}'\n"})
        self.refused(r, pub, capsys, "_tools/test_x.py has a leak-scan hit (guid)")


class TestPublishHistory:
    """Every commit to be pushed is checked, not only the projection's tree: a commit A that adds what a later commit
    B deletes is refused, named by its short hash."""
    prepare = TestPublishSafety.prepare

    def planted(self, src, tmp_path, files, first=True):
        """A published public home, then commit A adding FILES and commit B deleting them (A's hash). With FIRST
        False nothing is published first: the whole history is walked."""
        r, pub = self.prepare(src, tmp_path)
        if first:
            assert kbpublic.cmd_publish(ns(), r.path) == 0
        a = commit(r, files, "add")
        commit(r, {}, "delete", remove=list(files))
        r.git("push", "-q", "--no-verify", "origin", "HEAD:main")
        return r, pub, a

    def refused_at(self, r, pub, capsys, a, cause):
        tip = pub.run_git("rev-parse", "main").stdout.strip()
        for dry in (True, False):
            assert kbpublic.cmd_publish(ns(dry_run=dry), r.path) == 1
            text = capsys.readouterr().out
            assert f"refused: commit {a[:12]}" in text and cause in text and "nothing pushed" in text, text
            assert pub.run_git("rev-parse", "main").stdout.strip() == tip

    @pytest.mark.parametrize("first", [True, False])
    def test_internal_root_deleted_later(self, src, tmp_path, capsys, first):
        meta = "---\nroot: team\nid_prefix: T\nvisibility: internal\n---\n"  # the same blob for both roots
        r, pub, a = self.planted(src, tmp_path, {"kb/team/_root.md": meta, "kb/team/notes.md": "internal\n",
                                                 "kb/ops/_root.md": meta, "kb/ops/n.md": "internal\n"}, first)
        self.refused_at(r, pub, capsys, a, "under the internal root kb/team")
        self.refused_at(r, pub, capsys, a, "under the internal root kb/ops")

    def test_private_path_deleted_later(self, src, tmp_path, capsys):
        r, pub, a = self.planted(src, tmp_path, {"kb/public/_private/n.md": "x\n"})
        self.refused_at(r, pub, capsys, a, "holds kb/public/_private/n.md")

    def test_leak_removed_later(self, src, tmp_path, capsys):
        leak = ".".join(("192", "168", "4", "9"))  # built here so this file has no address of its own
        r, pub = self.prepare(src, tmp_path, {"kb/public/l.md": "host\n"})
        assert kbpublic.cmd_publish(ns(), r.path) == 0
        a = commit(r, {"kb/public/l.md": f"host {leak}\n"}, "add")
        commit(r, {"kb/public/l.md": "host\n"}, "remove")
        r.git("push", "-q", "--no-verify", "origin", "HEAD:main")
        self.refused_at(r, pub, capsys, a, "kb/public/l.md has a leak-scan hit (ip)")

    def test_clean_range_publishes(self, src, tmp_path):
        r, pub = self.prepare(src, tmp_path)
        assert kbpublic.cmd_publish(ns(), r.path) == 0
        commit(r, {"kb/public/c.md": "c\n"}, "add")
        head = commit(r, {}, "delete", remove=["kb/public/c.md"])
        r.git("push", "-q", "--no-verify", "origin", "HEAD:main")
        assert kbpublic.cmd_publish(ns(), r.path) == 0 and pub.rev("main") == kbpublic.project(head, r.path)

    def test_value_in_parent_version_passes(self, src, tmp_path):
        guid = "-".join(("3f2a4c1e", "0000", "4000", "8000", "00000000abcd"))  # built here so this file has none
        r, pub = self.prepare(src, tmp_path, {"_tools/test_x.py": f"QID = '{guid}'\n",
                                              "_tools/tests_allowlist.txt": f"guid {guid}  # reviewed\n"})
        r.git("rm", "-q", "_tools/tests_allowlist.txt")
        r.git("commit", "-q", "-m", "drop allowlist")
        head = commit(r, {"_tools/test_x.py": f"QID = '{guid}'\nOTHER = 1\n"}, "change the file")
        r.git("push", "-q", "--no-verify", "origin", "HEAD:main")
        # nothing published yet: the whole history is walked; the GUID was allowlisted when it was added, and the
        # later commit keeps a value its parent's version holds
        assert kbpublic.cmd_publish(ns(), r.path) == 0 and pub.rev("main") == kbpublic.project(head, r.path)


LOGS_FILES = ("kb/_self/_logs.csv", "kb/team/_logs.csv", "kb/public/_logs.csv", "kb/public/deep/er/_logs.csv")


@pytest.fixture
def logs_src(tmp_path):
    """A repository: a public commit, one adding a _logs.csv at four depths beside files that only end alike, one
    holding nothing else, one editing a _logs.csv and a public file, one deleting them all, and a public commit."""
    r = Repo(tmp_path / "logs")
    os.makedirs(r.path)
    r.git("init", "-q", "-b", "main")
    shas = [commit(r, {"kb/public/a.md": "fact\n"}, "public"),
            commit(r, {**{x: "id,observation\nL-aaaaaaaa,Median 12\n" for x in LOGS_FILES},
                       "kb/public/my_logs.csv": "a\n", "kb/public/logs.csv": "b\n", "kb/public/_logs.csv.md": "c\n"}, "logs"),
            commit(r, {"kb/other/_logs.csv": "x\n"}, "logs only"),
            commit(r, {"kb/_self/_logs.csv": "changed\n", "kb/public/b.md": "b\n"}, "mixed"),
            commit(r, {}, "remove logs", remove=[*LOGS_FILES, "kb/other/_logs.csv"]),
            commit(r, {"kb/public/c.md": "c\n"}, "public again")]
    return r, shas


class TestLogsCsv:
    def test_publish_omits_logs_csv(self, logs_src, tmp_path, capsys):
        """the projection holds no _logs.csv at any depth in any commit, keeps what only ends alike, drops the commit that
        held nothing else, and `publish` pushes that projection: the public home has none of them in its history"""
        r, shas = logs_src
        p = kbpublic.project(shas[-1], r.path)
        assert kbpublic.private_commits(p, r.path) == []
        assert kbpublic.project(shas[-1], r.path) == p  # the same commits when computed twice
        assert r.git("log", "--format=%s", p).split("\n")[:-1] == ["public again", "mixed", "logs", "public"]  # the two commits of _logs.csv only are gone
        for sha in (shas[1], shas[3]):
            tree = r.git("ls-tree", "-r", "--name-only", kbpublic.project(sha, r.path)).split()
            assert not [x for x in tree if x.endswith("/_logs.csv")], tree
        tree = r.git("ls-tree", "-r", "--name-only", kbpublic.project(shas[1], r.path)).split()
        assert {"kb/public/my_logs.csv", "kb/public/logs.csv", "kb/public/_logs.csv.md", "kb/public/a.md"} <= set(tree)
        assert not [x for x in tree if x.startswith(("kb/team", "kb/public/deep"))]  # a directory of nothing else is gone
        assert r.git("rev-list", p).split()[-1] == shas[0]  # the history before the first one keeps its hashes
        assert kbpublic.private_commits(shas[-1], r.path) and kbpublic.private_commits(shas[2], r.path)
        pub = Repo(tmp_path / "pub.git")
        Repo(tmp_path).git("init", "-q", "--bare", "-b", "main", pub.path)
        origin = Repo(tmp_path / "origin.git")
        Repo(tmp_path).git("clone", "-q", "--bare", r.path, origin.path)
        r.git("remote", "add", "origin", origin.path)
        r.git("remote", "add", "pub", pub.path)
        r.git("config", "kb.publishRemote", "pub")
        assert kbpublic.cmd_publish(ns(), r.path) == 0
        assert "published" in capsys.readouterr().out
        assert pub.git("log", "--all", "--format=%H", "--", ":(glob)**/_logs.csv") == ""  # no commit of the public home touched one
        assert kbpublic.private_commits("main", pub.path) == []

    def test_logs_csv_refused_in_a_pushed_range(self, logs_src, tmp_path, capsys):
        """check-public, the push guard and the bridge's range name a history that holds a _logs.csv (planted: one that
        does not), and the refusal names the file"""
        r, shas = logs_src
        assert kbpublic.cmd_check_public(argparse.Namespace(rev=shas[0]), r.path) == 0
        assert kbpublic.cmd_check_public(argparse.Namespace(rev=shas[2]), r.path) == 1
        out = capsys.readouterr().out
        assert "_logs.csv (in any directory)" in out and "FAILED" in out, out
        r.git("remote", "add", "pub", str(tmp_path / "x.git"))
        r.git("config", "kb.publishRemote", "pub")
        assert kbpublic.guard_push("pub", None, [("refs/heads/main", shas[0])], r.path) == []
        bad = kbpublic.guard_push("pub", None, [("refs/heads/main", shas[-1])], r.path)
        assert bad and "_logs.csv" in bad[0][1], bad
        assert kbpublic.private_commits(f"{shas[0]}..{shas[-1]}", r.path)  # the range the bridge reads
        assert kbpublic.private_commits(f"{shas[3]}..{shas[-1]}", r.path)  # the commit that deletes them is one too
        assert kbpublic.private_commits(f"{shas[4]}..{shas[-1]}", r.path) == []


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
    "bench_core.py": "a fixture clone's remote",
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
        assert "origin" not in p.stdout + p.stderr, p.stdout + p.stderr
        if public:  # a local url has no forge to read the CI verdict from: the safety check refuses after naming the source
            assert p.returncode == 1 and "source: integ/main" in p.stdout and "the CI verdict" in p.stdout, p.stdout
        else:
            assert p.returncode == 0 and "no public remote" in p.stdout

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


class TestBridge(SyncScenario):
    """kbgit.py bridge against local bare remotes: a branch of the public home to the integration remote, by lane."""

    @pytest.fixture
    def world(self, tmp_path, kb_seed):
        env = git_env(KB_SYNC_NO_TESTS="1")
        remote, (a, b), base = clones(kb_seed, str(tmp_path), env, ("a", "b"))
        w = type("World", (), {})()
        w.env, w.remote, w.a, w.b, w.base, w.bare = env, remote, a, b, base, Repo(remote, env)
        pub = os.path.join(str(tmp_path), "pub.git")
        Repo(str(tmp_path), env).git("clone", "-q", "--bare", remote, pub)
        w.pub = Repo(pub, env)
        a.git("remote", "add", "pub", pub)
        a.git("config", "kb.publishRemote", "pub")
        w.c = Repo(os.path.join(str(tmp_path), "c"), env)  # a contributor's clone of the public home
        Repo(str(tmp_path), env).git("clone", "-q", pub, w.c.path)
        w.c.git("checkout", "-q", "-b", "feature")
        return w

    @staticmethod
    def advertise(w):
        w.bare.git("config", "receive.advertisePushOptions", "true")
        hook = Path(w.remote) / "hooks" / "pre-receive"
        hook.write_text(RECORD_OPTIONS, encoding="utf-8", newline="\n")
        hook.chmod(0o755)

    @staticmethod
    def refs(repo):
        return repo.git("for-each-ref", "--format=%(refname) %(objectname)")

    def push_feature(self, w):
        w.c.git("push", "-q", "--no-verify", "origin", "feature")

    def test_content_branch_goes_to_main(self, world):
        w = world
        self.advertise(w)
        self.add_source(w.c, "S-", "https://learn.microsoft.com/en-us/sync-test/bridge1", "bridge1")
        self.article(w.c, "bridge1", [kbid.source_id("https://learn.microsoft.com/en-us/sync-test/bridge1")], ["Bridge fact."])
        self.commit(w.c, "docs(kb): bridge test")
        self.push_feature(w)
        before = self.refs(w.pub)
        d = w.a.kbgit("bridge", "feature", "--dry-run")
        assert d.returncode == 0 and "lane: content" in d.stdout and w.bare.rev("main") == w.base, d.stdout + d.stderr
        r = w.a.kbgit("bridge", "feature", "--push")
        assert r.returncode == 0, r.stdout + r.stderr
        assert w.bare.git("show", "main:" + P("windows/sync-test-bridge1.md")).count("Bridge fact.") == 1
        assert "docs(kb): bridge test" in w.bare.git("log", "-3", "--format=%s", "main")  # a fix commit may follow it
        assert "public branch: pub/feature" in r.stdout and w.bare.rev("main")[:7] in r.stdout
        assert "closed by a person" in r.stdout
        assert self.refs(w.pub) == before  # the public home was only read
        assert w.a.git("branch", "--show-current").strip() == "main" and "bridge/feature" not in w.a.git("branch")

    def test_code_branch_goes_to_a_code_branch(self, world):
        w = world
        self.advertise(w)
        w.c.write("_tools/bridge_test.txt", "code\n")
        w.c.git("add", "-A")
        w.c.git("commit", "-q", "-m", "chore(tools): bridge test")
        self.push_feature(w)
        before = self.refs(w.pub)
        r = w.a.kbgit("bridge", "feature", "--push")
        assert r.returncode == 0, r.stdout + r.stderr
        branches = w.bare.git("for-each-ref", "--format=%(refname:short)", "refs/heads/").split()
        assert w.bare.rev("main") == w.base and len(branches) == 2 and any(b.startswith("code/") for b in branches)
        assert "merge_request.create" in (Path(w.remote) / "pushed-options.txt").read_text(encoding="utf-8")
        assert self.refs(w.pub) == before

    def test_conflict_exits_3_with_the_rebase_in_progress(self, world):
        w = world
        w.c.write("README.md", "contributor\n")
        w.c.git("add", "-A")
        w.c.git("commit", "-q", "-m", "docs: contributor readme")
        self.push_feature(w)
        w.b.write("README.md", "integration\n")
        w.b.git("add", "-A")
        w.b.git("commit", "-q", "-m", "docs: integration readme")
        w.b.git("push", "-q", "--no-verify", "origin", "HEAD:main")
        before, main = self.refs(w.pub), w.bare.rev("main")
        r = w.a.kbgit("bridge", "feature", "--push")
        assert r.returncode == 3, r.stdout + r.stderr
        assert "CONFLICT" in r.stdout and "needs-human: README.md" in r.stdout
        assert os.path.isdir(os.path.join(w.a.path, ".git", "rebase-merge"))
        assert w.bare.rev("main") == main and self.refs(w.pub) == before

    def test_query_log_store_is_refused(self, world):
        w = world
        w.c.write("kb/_querylog/2026-09/r1.jsonl", "{}\n")
        w.c.git("add", "-A")
        w.c.git("commit", "-q", "-m", "chore(kb): store")
        self.push_feature(w)
        before, main = self.refs(w.pub), w.bare.rev("main")
        r = w.a.kbgit("bridge", "feature", "--push")
        assert r.returncode == 1 and "kb/_querylog" in r.stdout, r.stdout + r.stderr
        assert w.bare.rev("main") == main and self.refs(w.pub) == before
        assert w.a.git("branch", "--show-current").strip() == "main"

    def test_bad_arguments(self, world):
        w = world
        r = w.a.kbgit("bridge", "no-such-branch")
        assert r.returncode == 2, r.stdout + r.stderr
        w.a.git("config", "--unset", "kb.publishRemote")
        r = w.a.kbgit("bridge", "feature")
        assert r.returncode == 2 and "no public remote" in r.stdout
        w.a.git("config", "kb.publishRemote", "pub")
        w.a.write("README.md", "dirty\n")
        r = w.a.kbgit("bridge", "feature", "--push")
        assert r.returncode == 2 and "uncommitted changes" in r.stdout
